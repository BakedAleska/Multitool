import logging
import logging.handlers

from app.config import DATA_DIR

LOG_DIR = DATA_DIR / "logs"
LOG_FILE = LOG_DIR / "multitool.log"

_ROOT_LOGGER_NAME = "multitool"
_configured = False


def _configure() -> None:
    global _configured
    if _configured:
        return
    _configured = True

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger(_ROOT_LOGGER_NAME)
    root.setLevel(logging.DEBUG)
    # Don't propagate to Python's root logger — app/roblox/login.py runs as
    # a standalone subprocess that prints a JSON line to stdout as its IPC
    # protocol, and we never want stray log output anywhere near stdout.
    root.propagate = False

    handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """A logger that writes to <data dir>/logs/multitool.log.

    Safe to call from anywhere, including the standalone app/roblox/login.py
    subprocess — configuration happens lazily on first use, so there's no
    explicit setup call required at startup.
    """
    _configure()
    return logging.getLogger(f"{_ROOT_LOGGER_NAME}.{name}")
