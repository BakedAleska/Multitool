"""Discover and import installed widgets from WIDGETS_DIR."""

import importlib
import sys
from pathlib import Path

import flet as ft

from toolblox.config import WIDGETS_DIR
from toolblox.devtools import dev_widgets_dir
from toolblox.logs import get_logger
from toolblox.state import get_disabled_widgets
from toolblox.widgets.api import Widget

logger = get_logger(__name__)


def _purge_package(package_name: str) -> None:
    """Drop package_name and every submodule of it from sys.modules.

    A plain importlib.reload() only re-executes the named module, not
    anything it imports with a relative import - so editing a widget's
    other files wouldn't show up until the app restarted. Purging the
    whole package first and reimporting from scratch picks up edits to
    every file in a multi-file widget, not just widget.py.
    """
    prefix = f"{package_name}."
    for name in [n for n in sys.modules if n == package_name or n.startswith(prefix)]:
        del sys.modules[name]


def _discover_in(directory: Path, seen_ids: set[str]) -> tuple[list[Widget], list[tuple[str, str]]]:
    """Scan one directory for widget folders, skipping ids already in seen_ids.

    seen_ids is mutated as widgets are found, so callers can scan
    multiple directories and let an earlier one take precedence over a
    later one sharing the same folder name.
    """
    widgets: list[Widget] = []
    errors: list[tuple[str, str]] = []

    if not directory.exists():
        return widgets, errors

    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

    for entry in sorted(directory.iterdir()):
        if not entry.is_dir() or entry.name.startswith((".", "_")):
            continue
        if not (entry / "widget.py").exists():
            continue
        if entry.name in seen_ids:
            continue

        module_name = f"{entry.name}.widget"
        _purge_package(entry.name)
        try:
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
        seen_ids.add(entry.name)

    return widgets, errors


def discover_widgets(extra_dir: Path | None = None) -> tuple[list[Widget], list[tuple[str, str]]]:
    """Scan for widget folders and import each one fresh.

    Each subfolder containing a widget.py is treated as a package, so
    widget code can split into multiple files and use relative imports.
    Always re-scans, and always reimports from scratch (see
    _purge_package), so this is safe to call every time a view builds -
    there's no caching to go stale between calls.

    extra_dir, when given, is scanned first and takes precedence over
    WIDGETS_DIR for any id found in both - meant for a developer's
    in-repo widgets/ folder during Developer Mode, so editing a
    widget's source there shows up without installing it first. See
    toolblox.devtools.dev_widgets_dir.

    Returns (widgets, errors). errors is a list of
    (folder_name, error_message) for anything that failed to import or
    has no WIDGET variable. A broken widget is skipped, not fatal to the
    rest of the app.
    """
    seen_ids: set[str] = set()
    widgets: list[Widget] = []
    errors: list[tuple[str, str]] = []

    if extra_dir is not None:
        w, e = _discover_in(extra_dir, seen_ids)
        widgets.extend(w)
        errors.extend(e)

    w, e = _discover_in(WIDGETS_DIR, seen_ids)
    widgets.extend(w)
    errors.extend(e)

    return widgets, errors


def get_enabled_widgets(page: ft.Page) -> list[Widget]:
    """Discovered widgets, minus whatever's been disabled in Settings."""
    widgets, _errors = discover_widgets(dev_widgets_dir())
    disabled = set(get_disabled_widgets(page))
    return [w for w in widgets if w.id not in disabled]
