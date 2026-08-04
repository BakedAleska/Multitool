"""Registers or unregisters Toolblox as a per-user startup app.

Windows: a value in ``HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run``
pointing at the app's own executable. macOS: a LaunchAgent plist in
``~/Library/LaunchAgents``, loaded with ``RunAtLoad``. Both are per-user and
need no elevated privileges. Any other platform is unsupported and every
function here is a no-op on it.
"""

import subprocess
import sys
from pathlib import Path

from toolblox.logs import get_logger

logger = get_logger(__name__)

_APP_NAME = "Toolblox"
_LAUNCH_AGENT_LABEL = "com.bakedaleska.toolblox"
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

_PLIST_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" \
"http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{label}</string>
    <key>ProgramArguments</key>
    <array>
{args}
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
"""


def is_supported() -> bool:
    """Whether this platform has a startup mechanism implemented at all."""
    return sys.platform in ("win32", "darwin")


def _launch_command() -> list[str]:
    """The command that relaunches the app, for a frozen build or a source checkout.

    A frozen build's ``sys.executable`` is the app itself. Running from a
    source checkout, it's the interpreter, so main.py's path is appended
    the same way `python main.py` is normally invoked.
    """
    if getattr(sys, "frozen", False):
        return [sys.executable]
    main_py = Path(__file__).resolve().parent.parent / "main.py"
    return [sys.executable, str(main_py)]


def is_enabled() -> bool:
    """Whether the app is currently registered to start on login."""
    if sys.platform == "win32":
        return _windows_is_enabled()
    if sys.platform == "darwin":
        return _macos_plist_path().exists()
    return False


def set_enabled(enabled: bool) -> None:
    """Register or unregister the app as a startup app. A no-op elsewhere."""
    if sys.platform == "win32":
        _windows_set_enabled(enabled)
    elif sys.platform == "darwin":
        _macos_set_enabled(enabled)


def _windows_is_enabled() -> bool:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.QueryValueEx(key, _APP_NAME)
        return True
    except OSError:
        return False


def _windows_set_enabled(enabled: bool) -> None:
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            if enabled:
                command = subprocess.list2cmdline(_launch_command())
                winreg.SetValueEx(key, _APP_NAME, 0, winreg.REG_SZ, command)
            else:
                try:
                    winreg.DeleteValue(key, _APP_NAME)
                except FileNotFoundError:
                    pass
    except OSError as e:
        logger.error("Couldn't update the startup registry value: %s", e)


def _macos_plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{_LAUNCH_AGENT_LABEL}.plist"


def _macos_set_enabled(enabled: bool) -> None:
    plist_path = _macos_plist_path()
    if not enabled:
        plist_path.unlink(missing_ok=True)
        return
    args = "\n".join(f"        <string>{arg}</string>" for arg in _launch_command())
    try:
        plist_path.parent.mkdir(parents=True, exist_ok=True)
        plist_path.write_text(_PLIST_TEMPLATE.format(label=_LAUNCH_AGENT_LABEL, args=args))
    except OSError as e:
        logger.error("Couldn't write the LaunchAgent plist: %s", e)
