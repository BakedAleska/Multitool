"""Windows-only bypass for Roblox's singleton-instance check.

Runs the native helper at native/multi_instance_helper/multi_instance_helper.exe
(see its README for how the bypass works) so a second account's Join can
open its own Roblox window instead of just activating whichever one is
already running. Only meaningful on Windows, since Roblox doesn't enforce
the same single-instance restriction on macOS.
"""

import subprocess
import sys
from pathlib import Path

from toolblox.logs import get_logger

logger = get_logger(__name__)

HELPER_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "native"
    / "multi_instance_helper"
    / "multi_instance_helper.exe"
)


def clear_singleton_instance() -> None:
    """Best-effort: close any Roblox singleton handle already held.

    Does nothing on non-Windows platforms, or if the helper binary hasn't
    been built. Never raises: a failed bypass just means Join behaves like
    it did before this feature existed, which is safe to fall back to.
    """
    if sys.platform != "win32":
        return
    if not HELPER_PATH.exists():
        logger.warning("Multi-instance helper not found at %s", HELPER_PATH)
        return
    try:
        subprocess.run([str(HELPER_PATH)], timeout=5, capture_output=True, check=False)
    except (OSError, subprocess.TimeoutExpired) as e:
        logger.warning("Multi-instance helper failed: %s", e)
