"""Persistence for app settings, as a plain JSON dict at
``<DATA_DIR>/settings.json``.
"""

import json

from toolblox.config import DATA_DIR
from toolblox.logs import get_logger

logger = get_logger(__name__)

SETTINGS_FILE = DATA_DIR / "settings.json"

DEFAULTS = {
    "sidebar_pos": "left",
    "theme_mode": "system",
    "show_avatars": True,
    "sort_order": "last_played",
    "compact_mode": False,
    "place_id": "",
    "disabled_widgets": [],
    "installed_themes": [],
    "widget_settings": {},
    "multi_instance": False,
    "open_on_launch": False,
    "run_in_background": True,
    "widgets_start_on_launch": [],
}


def _migrate_legacy_custom_theme(data: dict) -> dict:
    """Fold a pre-multi-theme single ``custom_theme`` into ``installed_themes``.

    Older settings files stored one theme directly as ``custom_theme`` /
    ``custom_theme_source``, selected via ``theme_mode: "custom"``. This
    converts that into a single installed theme named "Custom" with id
    "custom", so upgrading doesn't drop a saved theme.
    """
    legacy_theme = data.pop("custom_theme", None)
    legacy_source = data.pop("custom_theme_source", "")
    if not legacy_theme:
        return data

    if not any(t.get("id") == "custom" for t in data.get("installed_themes", [])):
        data.setdefault("installed_themes", []).append(
            {"id": "custom", "name": "Custom", "source": legacy_source, **legacy_theme}
        )
    return data


def load() -> dict:
    """Read settings from disk, merged over DEFAULTS.

    Falls back to DEFAULTS if the file is missing or can't be parsed.
    """
    if not SETTINGS_FILE.exists():
        return DEFAULTS.copy()

    try:
        data = {**DEFAULTS, **json.loads(SETTINGS_FILE.read_text())}
        return _migrate_legacy_custom_theme(data)
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Couldn't read %s, falling back to defaults: %s", SETTINGS_FILE, e)
        return DEFAULTS.copy()


def save(settings: dict) -> None:
    """Write the full settings dict to disk, replacing whatever was there."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2))
