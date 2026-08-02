"""Persistence for the tracked Roblox account list.

Accounts are stored as a JSON list at ``<DATA_DIR>/accounts.json``. Each
record holds a Roblox session cookie, so that field is never written to
disk as plaintext: ``multitool.data.crypto`` protects it with DPAPI on
Windows and the login Keychain on macOS. ``load()``/``save()`` do this
transparently, so callers always see a plaintext ``security_cookie`` in
memory.
"""

import json
import os
import stat
import time

from multitool.config import DATA_DIR
from multitool.data import crypto
from multitool.logs import get_logger

logger = get_logger(__name__)

ACCOUNTS_FILE = DATA_DIR / "accounts.json"


def load() -> list[dict]:
    """Read the account list from disk, with cookies decrypted in place.

    Returns an empty list if the file is missing or can't be parsed.
    A bad file shouldn't crash the app.
    """
    if not ACCOUNTS_FILE.exists():
        return []

    try:
        accounts = json.loads(ACCOUNTS_FILE.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Couldn't read %s, falling back to empty: %s", ACCOUNTS_FILE, e)
        return []

    for account in accounts:
        stored = account.get("security_cookie")
        if stored:
            account["security_cookie"] = crypto.unprotect(account["id"], stored)

    return accounts


def save(accounts: list[dict]) -> None:
    """Write the account list to disk, replacing whatever was there.

    Each record's cookie is protected via ``multitool.data.crypto`` before
    it's written, so ``accounts.json`` never holds one in plaintext.
    Accounts present in the previous save but missing from this one have
    their stored cookie forgotten too. On platforms with POSIX permission
    bits (all but Windows), the file itself is also restricted to the
    current user.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    previous_ids = set()
    if ACCOUNTS_FILE.exists():
        try:
            previous_ids = {a["id"] for a in json.loads(ACCOUNTS_FILE.read_text())}
        except (json.JSONDecodeError, OSError):
            pass
    current_ids = {a["id"] for a in accounts}
    for removed_id in previous_ids - current_ids:
        crypto.forget(removed_id)

    to_write = []
    for account in accounts:
        record = dict(account)
        cookie = record.get("security_cookie")
        if cookie:
            record["security_cookie"] = crypto.protect(record["id"], cookie)
        to_write.append(record)

    ACCOUNTS_FILE.write_text(json.dumps(to_write, indent=2))

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
