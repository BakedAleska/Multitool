import importlib
import sys

import flet as ft

from app.config import WIDGETS_DIR
from app.logs import get_logger
from app.state import get_disabled_widgets
from app.widgets.api import Widget

logger = get_logger(__name__)


def discover_widgets() -> tuple[list[Widget], list[tuple[str, str]]]:
    """Scan WIDGETS_DIR for widget folders and import each one fresh.

    Each subfolder of WIDGETS_DIR containing a widget.py is treated as a
    package (so widget code can freely split into multiple files and use
    relative imports, e.g. `from . import constants`).

    Returns (widgets, errors). errors is a list of
    (folder_name, error_message) for anything that failed to import or
    doesn't expose a WIDGET variable — a broken widget is skipped, not
    fatal to the rest of the app.
    """
    widgets: list[Widget] = []
    errors: list[tuple[str, str]] = []

    if not WIDGETS_DIR.exists():
        return widgets, errors

    if str(WIDGETS_DIR) not in sys.path:
        sys.path.insert(0, str(WIDGETS_DIR))

    for entry in sorted(WIDGETS_DIR.iterdir()):
        if not entry.is_dir() or entry.name.startswith((".", "_")):
            continue
        if not (entry / "widget.py").exists():
            continue

        module_name = f"{entry.name}.widget"
        try:
            if module_name in sys.modules:
                module = importlib.reload(sys.modules[module_name])
            else:
                module = importlib.import_module(module_name)
        except Exception as e:
            logger.exception("Widget '%s' failed to import", entry.name)
            errors.append((entry.name, str(e)))
            continue

        widget = getattr(module, "WIDGET", None)
        if widget is None:
            message = "widget.py has no module-level WIDGET variable"
            logger.warning("Widget '%s' skipped: %s", entry.name, message)
            errors.append((entry.name, message))
            continue

        widgets.append(widget)

    return widgets, errors


def get_enabled_widgets(page: ft.Page) -> list[Widget]:
    """Discovered widgets, minus whatever's been disabled in Settings."""
    widgets, _errors = discover_widgets()
    disabled = set(get_disabled_widgets(page))
    return [w for w in widgets if w.id not in disabled]
