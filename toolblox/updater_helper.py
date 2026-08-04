"""Toolblox's own in-place updater, run as a separate small executable.

Windows only. Replacing a running app's own exe and DLLs from inside
that same running process doesn't work - Windows won't let a process
overwrite its own currently-mapped image, which is exactly why
toolblox/updater.py used to hand the whole job off to the Inno Setup
installer (a genuinely separate exe) instead. That still had its own
problems: the installer re-downloaded the build from GitHub a second
time, ran through its full wizard UI for what should be a quiet
background update, and gave no control over exactly when file
replacement started relative to the old process actually exiting.

This module is that "genuinely separate exe" instead, purpose-built
for updating rather than borrowing an installer for it. It ships as
`ToolbloxUpdater.exe`, bundled alongside `Toolblox.exe` in every
install (see release/build.py's --add-binary for it, the same pattern
used for native/multi_instance_helper), so applying an update never
needs a second download of anything beyond the new build's own zip.
toolblox/updater.py spawns it, passing the already-downloaded and
sha256-verified update zip, then exits the main app; this process
waits for that exit, extracts the new build into a fresh staging
directory next to the install (so a failed/interrupted extraction
never corrupts a working install), swaps it in with two directory
renames, and relaunches Toolblox.exe.

IPC is just argv - see main()'s argparse setup - and this process's
own stdout/stderr, logged to <DATA_DIR>/logs/toolblox.log via
toolblox.logs like every other part of the app.
"""

import argparse
import shutil
import subprocess
import sys
import time
import uuid
import zipfile
from pathlib import Path

from toolblox.logs import get_logger

logger = get_logger(__name__)

PID_WAIT_TIMEOUT_SECONDS = 30
FILE_RETRY_ATTEMPTS = 10
FILE_RETRY_DELAY_SECONDS = 0.5


def _wait_for_exit(pid: int, timeout_seconds: float) -> None:
    """Block until process `pid` exits, or `timeout_seconds` passes.

    Windows only, via ctypes - the same approach toolblox/data/crypto.py
    already uses for DPAPI rather than adding a dependency like psutil
    just for this one wait. If OpenProcess fails outright, the process
    is already gone (or never existed), so there's nothing to wait for.
    """
    import ctypes

    PROCESS_SYNCHRONIZE = 0x00100000
    WAIT_TIMEOUT = 0x00000102

    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_SYNCHRONIZE, False, pid)
    if not handle:
        return
    try:
        result = ctypes.windll.kernel32.WaitForSingleObject(handle, int(timeout_seconds * 1000))
        if result == WAIT_TIMEOUT:
            logger.warning("Timed out waiting for pid %s to exit before updating", pid)
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def _extract_zip(zip_path: Path, dest_dir: Path) -> None:
    """Extract `zip_path` into `dest_dir`, rejecting any path-traversal member.

    dest_dir is a fresh staging directory this process just created, not
    the live install, so this never touches a real install directly -
    see apply_update()'s staging-then-swap sequence. Mirrors the same
    zip-slip guard toolblox/widgets/installer.py uses for widget
    archives, duplicated here rather than imported since this module
    ships in its own separate, minimal PyInstaller build.
    """
    dest_root = dest_dir.resolve()
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            target = (dest_dir / member).resolve()
            if dest_root not in target.parents and target != dest_root:
                raise RuntimeError(f"Update archive member '{member}' escapes the staging directory")
        zf.extractall(dest_dir)


def _rename_with_retry(src: Path, dst: Path) -> None:
    """os.rename with a short retry loop for a just-freed file still settling.

    A process exiting doesn't always release every file handle the
    instant WaitForSingleObject returns - antivirus real-time scanning
    in particular can hold one open a little longer. Retrying beats
    failing the whole update over a race that resolves itself within a
    second or two.
    """
    last_error: Exception = RuntimeError("unreachable")
    for attempt in range(FILE_RETRY_ATTEMPTS):
        try:
            src.rename(dst)
            return
        except OSError as e:
            last_error = e
            if attempt < FILE_RETRY_ATTEMPTS - 1:
                time.sleep(FILE_RETRY_DELAY_SECONDS)
    raise last_error


def apply_update(pid: int, install_dir: Path, zip_path: Path, exe_name: str) -> None:
    """Wait for `pid` to exit, then swap `install_dir`'s contents for `zip_path`'s.

    Staging-then-swap rather than extracting straight over the live
    install: the new build is fully extracted and verified-present in a
    sibling directory first, then two directory renames put it in
    place, so a failure partway through extraction never leaves a
    half-updated app behind. The old directory is renamed aside rather
    than deleted outright, then removed on a best-effort basis - if
    that last delete fails, it's leftover debris, not a broken install.
    """
    _wait_for_exit(pid, PID_WAIT_TIMEOUT_SECONDS)

    token = uuid.uuid4().hex
    staging_dir = install_dir.parent / f".toolblox_update_{token}"
    old_dir = install_dir.parent / f".toolblox_old_{token}"

    staging_dir.mkdir()
    try:
        _extract_zip(zip_path, staging_dir)
        _rename_with_retry(install_dir, old_dir)
        try:
            _rename_with_retry(staging_dir, install_dir)
        except OSError:
            _rename_with_retry(old_dir, install_dir)
            raise
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)

    shutil.rmtree(old_dir, ignore_errors=True)

    subprocess.Popen([str(install_dir / exe_name)], close_fds=True)


def main() -> None:
    """Parse argv and run apply_update(). See this module's docstring."""
    parser = argparse.ArgumentParser(description="Toolblox in-place updater")
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--install-dir", type=Path, required=True)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--exe-name", default="Toolblox.exe")
    args = parser.parse_args()

    try:
        apply_update(args.pid, args.install_dir, args.zip, args.exe_name)
    except Exception:
        logger.exception("Update failed")
        raise


if __name__ == "__main__":
    main()
