import json
import os
import stat

from app.config import DATA_DIR
from app.logs import get_logger

logger = get_logger(__name__)

ACCOUNTS_FILE = DATA_DIR / "accounts.json"


def load() -> list[dict]:
    if not ACCOUNTS_FILE.exists():
        return []

    try:
        return json.loads(ACCOUNTS_FILE.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Couldn't read %s, falling back to empty: %s", ACCOUNTS_FILE, e)
        return []


def save(accounts: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ACCOUNTS_FILE.write_text(json.dumps(accounts, indent=2))

    # Account records now include Roblox session cookies, so keep the file
    # readable/writable only by the current user.
    if os.name != "nt":
        os.chmod(ACCOUNTS_FILE, stat.S_IRUSR | stat.S_IWUSR)
