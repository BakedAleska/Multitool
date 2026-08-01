import json

from app.config import DATA_DIR
from app.logs import get_logger

logger = get_logger(__name__)

SETTINGS_FILE = DATA_DIR / "settings.json"

DEFAULTS = {
    "sidebar_pos": "left",
    "theme_mode": "system",
    "show_avatars": True,
    "sort_order": "date_added",
    "compact_mode": False,
    "place_id": "",
    "disabled_widgets": [],
}


def load() -> dict:
    if not SETTINGS_FILE.exists():
        return DEFAULTS.copy()

    try:
        return {**DEFAULTS, **json.loads(SETTINGS_FILE.read_text())}
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Couldn't read %s, falling back to defaults: %s", SETTINGS_FILE, e)
        return DEFAULTS.copy()


def save(settings: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2))
