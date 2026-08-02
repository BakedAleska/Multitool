"""Read and write app settings for the current page.

Each setting has a get and a set function below. Both go through
_get_settings, which caches the loaded settings dict on the page's
session so repeated reads in one build don't hit disk each time. Never
read or write app.data.settings directly from UI code.
"""

from typing import Optional

import flet as ft

from app.data import settings as settings_store

NAV_POSITION_KEY = "sidebar_pos"
DEFAULT_NAV_POSITION = settings_store.DEFAULTS[NAV_POSITION_KEY]

THEME_MODE_KEY = "theme_mode"
DEFAULT_THEME_MODE = settings_store.DEFAULTS[THEME_MODE_KEY]
THEME_MODE_MAP = {
    "system": ft.ThemeMode.SYSTEM,
    "light": ft.ThemeMode.LIGHT,
    "dark": ft.ThemeMode.DARK,
    "custom": ft.ThemeMode.SYSTEM,
}
"""Maps the theme_mode setting to Flet's ThemeMode. "custom" has no
ThemeMode of its own, so it renders at system brightness while
app.theme.build_theme layers the saved custom theme on top.
"""

SHOW_AVATARS_KEY = "show_avatars"
DEFAULT_SHOW_AVATARS = settings_store.DEFAULTS[SHOW_AVATARS_KEY]

SORT_ORDER_KEY = "sort_order"
DEFAULT_SORT_ORDER = settings_store.DEFAULTS[SORT_ORDER_KEY]

COMPACT_MODE_KEY = "compact_mode"
DEFAULT_COMPACT_MODE = settings_store.DEFAULTS[COMPACT_MODE_KEY]

PLACE_ID_KEY = "place_id"
DEFAULT_PLACE_ID = settings_store.DEFAULTS[PLACE_ID_KEY]

DISABLED_WIDGETS_KEY = "disabled_widgets"
DEFAULT_DISABLED_WIDGETS = settings_store.DEFAULTS[DISABLED_WIDGETS_KEY]

CUSTOM_THEME_KEY = "custom_theme"
DEFAULT_CUSTOM_THEME = settings_store.DEFAULTS[CUSTOM_THEME_KEY]

CUSTOM_THEME_SOURCE_KEY = "custom_theme_source"
DEFAULT_CUSTOM_THEME_SOURCE = settings_store.DEFAULTS[CUSTOM_THEME_SOURCE_KEY]

_SETTINGS_CACHE_KEY = "_settings_cache"


def _get_settings(page: ft.Page) -> dict:
    """Return the settings dict for this page, loading it once and caching
    it in the page's session for later calls.
    """
    cached = page.session.store.get(_SETTINGS_CACHE_KEY)
    if cached is None:
        cached = settings_store.load()
        page.session.store.set(_SETTINGS_CACHE_KEY, cached)
    return cached


def get_nav_position(page: ft.Page) -> str:
    return _get_settings(page).get(NAV_POSITION_KEY, DEFAULT_NAV_POSITION)


def set_nav_position(page: ft.Page, position: str) -> None:
    current = _get_settings(page)
    current[NAV_POSITION_KEY] = position
    page.session.store.set(_SETTINGS_CACHE_KEY, current)
    settings_store.save(current)


def get_theme_mode(page: ft.Page) -> str:
    return _get_settings(page).get(THEME_MODE_KEY, DEFAULT_THEME_MODE)


def set_theme_mode(page: ft.Page, mode: str) -> None:
    current = _get_settings(page)
    current[THEME_MODE_KEY] = mode
    page.session.store.set(_SETTINGS_CACHE_KEY, current)
    settings_store.save(current)


def get_show_avatars(page: ft.Page) -> bool:
    return _get_settings(page).get(SHOW_AVATARS_KEY, DEFAULT_SHOW_AVATARS)


def set_show_avatars(page: ft.Page, value: bool) -> None:
    current = _get_settings(page)
    current[SHOW_AVATARS_KEY] = value
    page.session.store.set(_SETTINGS_CACHE_KEY, current)
    settings_store.save(current)


def get_sort_order(page: ft.Page) -> str:
    return _get_settings(page).get(SORT_ORDER_KEY, DEFAULT_SORT_ORDER)


def set_sort_order(page: ft.Page, value: str) -> None:
    current = _get_settings(page)
    current[SORT_ORDER_KEY] = value
    page.session.store.set(_SETTINGS_CACHE_KEY, current)
    settings_store.save(current)


def get_compact_mode(page: ft.Page) -> bool:
    return _get_settings(page).get(COMPACT_MODE_KEY, DEFAULT_COMPACT_MODE)


def set_compact_mode(page: ft.Page, value: bool) -> None:
    current = _get_settings(page)
    current[COMPACT_MODE_KEY] = value
    page.session.store.set(_SETTINGS_CACHE_KEY, current)
    settings_store.save(current)


def get_place_id(page: ft.Page) -> str:
    return _get_settings(page).get(PLACE_ID_KEY, DEFAULT_PLACE_ID)


def set_place_id(page: ft.Page, value: str) -> None:
    current = _get_settings(page)
    current[PLACE_ID_KEY] = value
    page.session.store.set(_SETTINGS_CACHE_KEY, current)
    settings_store.save(current)


def get_disabled_widgets(page: ft.Page) -> list[str]:
    return _get_settings(page).get(DISABLED_WIDGETS_KEY, DEFAULT_DISABLED_WIDGETS)


def set_widget_enabled(page: ft.Page, widget_id: str, enabled: bool) -> None:
    current = _get_settings(page)
    disabled = list(current.get(DISABLED_WIDGETS_KEY, DEFAULT_DISABLED_WIDGETS))
    if enabled and widget_id in disabled:
        disabled.remove(widget_id)
    elif not enabled and widget_id not in disabled:
        disabled.append(widget_id)
    current[DISABLED_WIDGETS_KEY] = disabled
    page.session.store.set(_SETTINGS_CACHE_KEY, current)
    settings_store.save(current)


def get_custom_theme(page: ft.Page) -> Optional[dict]:
    return _get_settings(page).get(CUSTOM_THEME_KEY, DEFAULT_CUSTOM_THEME)


def get_custom_theme_source(page: ft.Page) -> str:
    return _get_settings(page).get(CUSTOM_THEME_SOURCE_KEY, DEFAULT_CUSTOM_THEME_SOURCE)


def set_custom_theme(page: ft.Page, theme: Optional[dict], source: str) -> None:
    """Save a parsed custom theme, along with the raw input it came from.

    The raw source is kept only so Settings can show back what's active.
    theme is what actually gets applied, via app.theme.build_theme.
    """
    current = _get_settings(page)
    current[CUSTOM_THEME_KEY] = theme
    current[CUSTOM_THEME_SOURCE_KEY] = source
    page.session.store.set(_SETTINGS_CACHE_KEY, current)
    settings_store.save(current)


def is_custom_theme_active(page: ft.Page) -> bool:
    """Whether "Custom" is the selected appearance and a theme is saved.

    A saved custom theme stays on disk even while System, Light, or Dark
    is selected. It only takes effect when the mode is actually "custom".
    """
    return get_theme_mode(page) == "custom" and get_custom_theme(page) is not None
