"""File-based logging shared by every part of the app.

Every module gets its own logger via `get_logger(__name__)`. All loggers
write to a single rotating file at ``<DATA_DIR>/logs/toolblox.log``.
"""

import logging
import logging.handlers

from toolblox.config import DATA_DIR

LOG_DIR = DATA_DIR / "logs"
LOG_FILE = LOG_DIR / "toolblox.log"

_ROOT_LOGGER_NAME = "toolblox"
_configured = False


def _configure() -> None:
    """Set up the root "toolblox" logger. Runs once, on first use.

    Propagation to Python's root logger is disabled. toolblox/roblox/login.py
    runs as a subprocess and prints a single JSON line to stdout as its
    protocol back to the main app. That line must stay clean.
    """
    global _configured
    if _configured:
        return
    _configured = True

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger(_ROOT_LOGGER_NAME)
    root.setLevel(logging.DEBUG)
    root.propagate = False

    handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """A logger that writes to <data dir>/logs/toolblox.log.

    Safe to call from anywhere, including the standalone
    toolblox/roblox/login.py subprocess. Configuration happens lazily on
    first use.

    `name` is almost always `__name__`, which is already dotted under
    `toolblox` for any regularly imported module (e.g. `toolblox.state`).
    The one exception is a module run directly as a script, such as the
    login subprocess, where `__name__` is `"__main__"` instead - that case
    still needs the root prefix added so it lands under the same logger tree.
    """
    _configure()
    if name != _ROOT_LOGGER_NAME and not name.startswith(f"{_ROOT_LOGGER_NAME}."):
        name = f"{_ROOT_LOGGER_NAME}.{name}"
    return logging.getLogger(name)
