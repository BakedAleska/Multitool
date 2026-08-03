"""Detects whether a Roblox game client process is currently running.

Used by widgets, such as Image Overlay, that should only act while Roblox
itself is open. This is plain OS process-list inspection, unrelated to the
account/login/join flow the rest of `multitool/roblox/` handles.
"""

import subprocess
import sys

WINDOWS_PROCESS_NAME = "RobloxPlayerBeta.exe"
MACOS_PROCESS_NAME = "RobloxPlayer"


def is_roblox_running() -> bool:
    """Return True if a Roblox game client process is currently running.

    Shells out to the OS's own process listing (`tasklist` on Windows,
    `pgrep` on macOS) rather than adding a dependency like psutil. Pure
    and blocking, so callers on the Flet event loop should run it via
    `asyncio.to_thread` rather than calling it directly. Never raises;
    any failure to read the process list is treated as "not running".
    """
    try:
        if sys.platform == "win32":
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {WINDOWS_PROCESS_NAME}", "/NH"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return WINDOWS_PROCESS_NAME.lower() in result.stdout.lower()
        if sys.platform == "darwin":
            result = subprocess.run(
                ["pgrep", "-x", MACOS_PROCESS_NAME],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        return False
    except (OSError, subprocess.TimeoutExpired):
        return False
