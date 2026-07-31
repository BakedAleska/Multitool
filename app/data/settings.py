import json
from app.config import DATA_DIR

SETTINGS_FILE = DATA_DIR / "settings.json"

DEFAULTS = {
    "sidebar_pos": "left"
}

def load() -> dict:
    if not SETTINGS_FILE.exists():
        return DEFAULTS.copy()

    try:
        return {**DEFAULTS, **json.loads(SETTINGS_FILE.read_text())}
    except (json.JSONDecodeError, OSError):
        return DEFAULTS.copy()

def save(settings: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2))