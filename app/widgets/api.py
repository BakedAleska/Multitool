from dataclasses import dataclass
from typing import Any, Callable, Optional

import flet as ft


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


def get_widget_data(account: dict, widget_id: str) -> dict:
    """Read this widget's namespaced data out of an account dict.

    Returns {} if nothing has been stored yet.
    """
    return account.get("widget_data", {}).get(widget_id, {})


def set_widget_data(account: dict, widget_id: str, data: dict) -> None:
    """Write this widget's namespaced data into an account dict, in place.

    Caller is still responsible for saving the account list back out via
    app.data.accounts.save(...) — this only mutates the dict in memory.
    """
    account.setdefault("widget_data", {})[widget_id] = data
