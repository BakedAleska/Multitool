import os
import sys
from pathlib import Path

if sys.platform == "win32":
    base_dir = os.getenv("LOCALAPPDATA") or Path.home() / "AppData" / "Local"
elif sys.platform == "darwin":
    base_dir = Path.home() / "Library" / "Application Support"
else:
    base_dir = os.getenv("XDG_DATA_HOME") or Path.home() / ".local" / "share"

DATA_DIR = Path(base_dir) / "Multitool"
WIDGETS_DIR = DATA_DIR / "widgets"

WIDGET_REGISTRY_URL = "https://raw.githubusercontent.com/BakedAleska/Multitool/main/registry.json"
