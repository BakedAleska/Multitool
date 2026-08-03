"""Bundled Rogue Lineage class/race/item lists, used to populate dropdowns.

Loaded from reference.json in this same folder. This is a starting list
assembled from the Rogue Lineage Fandom wiki, not a full scrape - it's a
plain, hand-editable JSON file so anyone can extend it later without
touching code. Every dropdown that uses these lists also offers an
"Other..." option for a value that isn't in the list yet, so an
incomplete list never blocks entering real data.
"""

import json
from pathlib import Path

_REFERENCE_FILE = Path(__file__).parent / "reference.json"


def _load() -> dict:
    try:
        return json.loads(_REFERENCE_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


_data = _load()

CLASSES: list[str] = _data.get("classes", [])
RACES: list[str] = _data.get("races", [])
ITEMS: list[str] = _data.get("items", [])
