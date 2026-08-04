"""List running Roblox client processes.

Used alongside toolblox.roblox.presence to tell a crashed Join attempt
apart from one that's still connecting: if no Roblox process ever appears
after a Join, or the one that did dies before presence confirms the
account made it into a place, that Join is treated as crashed.
"""

import subprocess
import sys

from toolblox.logs import get_logger

logger = get_logger(__name__)

PROCESS_NAME = "RobloxPlayerBeta.exe" if sys.platform == "win32" else "RobloxPlayer"


def running_pids() -> set[int]:
    """The pids of every currently running Roblox client process.

    Returns an empty set on any failure, or on a platform this doesn't
    support process listing for.
    """
    try:
        if sys.platform == "win32":
            output = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {PROCESS_NAME}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW,
            ).stdout
            pids = set()
            for line in output.splitlines():
                fields = [f.strip('"') for f in line.split('","')]
                if len(fields) >= 2 and fields[0] == PROCESS_NAME and fields[1].isdigit():
                    pids.add(int(fields[1]))
            return pids
        if sys.platform == "darwin":
            output = subprocess.run(
                ["pgrep", "-x", PROCESS_NAME], capture_output=True, text=True, timeout=5
            ).stdout
            return {int(pid) for pid in output.split() if pid.isdigit()}
    except (OSError, subprocess.TimeoutExpired, ValueError) as e:
        logger.warning("Couldn't list Roblox processes: %s", e)
    return set()
