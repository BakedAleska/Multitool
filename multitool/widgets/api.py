"""The contract a widget must implement, and shared helpers for it."""

from dataclasses import dataclass
from typing import Any, Callable, Optional

import flet as ft


@dataclass
class DashboardTile:
    """A single at-a-glance module a widget contributes to the Dashboard.

    `build` returns only the tile's inner content, such as an icon and a
    line of text. The Dashboard wraps it in the standard card chrome, so
    widget tiles look consistent with the built-in ones.
    """

    id: str
    """Unique (per-widget) id for this tile, e.g. "playtime"."""

    build: Callable[[ft.Page], ft.Control]
    """Given the page, return the tile's inner content."""

    wide: bool = False
    """If True, the tile spans two grid columns instead of one."""


@dataclass
class Widget:
    """The contract a widget module must satisfy.

    A widget lives at `<widgets folder>/<your_folder>/widget.py` and must
    expose a module-level `WIDGET` variable holding one of these.
    """

    id: str
    """Short, unique, filesystem-and-route-safe id, e.g. "rogue_lineage"."""

    name: str
    """Display name shown in the nav rail and Settings, e.g. "Rogue Lineage"."""

    build_view: Callable[[ft.Page], ft.View]
    """Same shape as the built-in views (DashboardView, AccountsView, ...):
    given the page, return the ft.View shown when this widget's nav item is
    selected."""

    icon: Optional[Any] = None
    """A ft.Icons value for the nav item. Defaults to ft.Icons.EXTENSION."""

    selected_icon: Optional[Any] = None
    """A ft.Icons value used when this widget's nav item is selected.
    Falls back to `icon` if not given."""

    dashboard_tiles: Optional[Callable[[ft.Page], list[DashboardTile]]] = None
    """Optional: given the page, return the tiles this widget contributes
    to the Dashboard. Called fresh on every Dashboard build, so tiles can
    reflect current state. Omit, or return [], to contribute nothing."""


def get_widget_data(account: dict, widget_id: str) -> dict:
    """Read this widget's namespaced data out of an account dict.

    Returns {} if nothing has been stored yet.
    """
    return account.get("widget_data", {}).get(widget_id, {})


def set_widget_data(account: dict, widget_id: str, data: dict) -> None:
    """Write this widget's namespaced data into an account dict, in place.

    This only mutates the dict in memory. The caller must still save the
    account list with multitool.data.accounts.save(...).
    """
    account.setdefault("widget_data", {})[widget_id] = data
