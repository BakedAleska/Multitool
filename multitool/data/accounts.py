"""Persistence for the tracked Roblox account list.

Accounts are stored as a plain JSON list at ``<DATA_DIR>/accounts.json``.
Each record holds a Roblox session cookie, so ``save()`` locks the file
down to the current user wherever the platform supports it.
"""

import json
import os
import stat
import time

from multitool.config import DATA_DIR
from multitool.logs import get_logger

logger = get_logger(__name__)

ACCOUNTS_FILE = DATA_DIR / "accounts.json"


def load() -> list[dict]:
    """Read the account list from disk.

    Returns an empty list if the file is missing or can't be parsed.
    A bad file shouldn't crash the app.
    """
    if not ACCOUNTS_FILE.exists():
        return []

    try:
        return json.loads(ACCOUNTS_FILE.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Couldn't read %s, falling back to empty: %s", ACCOUNTS_FILE, e)
        return []


def save(accounts: list[dict]) -> None:
    """Write the account list to disk, replacing whatever was there.

    Each record includes a Roblox session cookie. On platforms with
    POSIX permission bits (all but Windows), the file is restricted to
    the current user.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ACCOUNTS_FILE.write_text(json.dumps(accounts, indent=2))

    if os.name != "nt":
        os.chmod(ACCOUNTS_FILE, stat.S_IRUSR | stat.S_IWUSR)


def record_play(user_id: int) -> None:
    """Bump play_count and stamp last_played_at for an account.

    Called after a successful game launch. Used by the Dashboard to
    show the last played and most used accounts.
    """
    current = load()
    for account in current:
        if account["id"] == user_id:
            account["play_count"] = account.get("play_count", 0) + 1
            account["last_played_at"] = time.time()
            break
    save(current)
