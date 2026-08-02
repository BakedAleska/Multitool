"""Read and write app settings for the current page.

Each setting has a get and a set function below. Both go through
_get_settings, which caches the loaded settings dict on the page's
session so repeated reads in one build don't hit disk each time. Never
read or write multitool.data.settings directly from UI code.
"""

import re
from typing import Optional

import flet as ft

from multitool.data import settings as settings_store
from multitool.theme import theme_brightness_mode

NAV_POSITION_KEY = "sidebar_pos"
DEFAULT_NAV_POSITION = settings_store.DEFAULTS[NAV_POSITION_KEY]

THEME_MODE_KEY = "theme_mode"
DEFAULT_THEME_MODE = settings_store.DEFAULTS[THEME_MODE_KEY]
BUILT_IN_THEME_MODES = {
    "system": ft.ThemeMode.SYSTEM,
    "light": ft.ThemeMode.LIGHT,
    "dark": ft.ThemeMode.DARK,
}
"""The always-available appearance choices. Anything else in theme_mode
is the id of an installed theme, resolved via get_installed_themes.
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

INSTALLED_THEMES_KEY = "installed_themes"
DEFAULT_INSTALLED_THEMES = settings_store.DEFAULTS[INSTALLED_THEMES_KEY]

WIDGET_SETTINGS_KEY = "widget_settings"
DEFAULT_WIDGET_SETTINGS = settings_store.DEFAULTS[WIDGET_SETTINGS_KEY]

MULTI_INSTANCE_KEY = "multi_instance"
DEFAULT_MULTI_INSTANCE = settings_store.DEFAULTS[MULTI_INSTANCE_KEY]

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


def get_widget_setting(page: ft.Page, widget_id: str, key: str, default=None):
    """Read one persisted setting for a widget's own Settings section.

    Namespaced per widget id so two widgets can use the same key name
    without colliding.
    """
    widget_settings = _get_settings(page).get(WIDGET_SETTINGS_KEY, DEFAULT_WIDGET_SETTINGS)
    return widget_settings.get(widget_id, {}).get(key, default)


def set_widget_setting(page: ft.Page, widget_id: str, key: str, value) -> None:
    current = _get_settings(page)
    widget_settings = dict(current.get(WIDGET_SETTINGS_KEY, DEFAULT_WIDGET_SETTINGS))
    widget_settings[widget_id] = {**widget_settings.get(widget_id, {}), key: value}
    current[WIDGET_SETTINGS_KEY] = widget_settings
    page.session.store.set(_SETTINGS_CACHE_KEY, current)
    settings_store.save(current)


def get_multi_instance(page: ft.Page) -> bool:
    return _get_settings(page).get(MULTI_INSTANCE_KEY, DEFAULT_MULTI_INSTANCE)


def set_multi_instance(page: ft.Page, value: bool) -> None:
    current = _get_settings(page)
    current[MULTI_INSTANCE_KEY] = value
    page.session.store.set(_SETTINGS_CACHE_KEY, current)
    settings_store.save(current)


def get_installed_themes(page: ft.Page) -> list[dict]:
    """All installed themes, each a dict with at least "id" and "name"."""
    return _get_settings(page).get(INSTALLED_THEMES_KEY, DEFAULT_INSTALLED_THEMES)


def get_theme_by_id(page: ft.Page, theme_id: str) -> Optional[dict]:
    return next((t for t in get_installed_themes(page) if t.get("id") == theme_id), None)


def _unique_theme_id(page: ft.Page, name: str) -> str:
    """A slug id for name, deduped against already-installed theme ids."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-") or "theme"
    existing_ids = {t.get("id") for t in get_installed_themes(page)}
    candidate = slug
    suffix = 2
    while candidate in existing_ids:
        candidate = f"{slug}-{suffix}"
        suffix += 1
    return candidate


def install_theme(page: ft.Page, theme: dict, source: str) -> str:
    """Add a newly parsed theme to the installed list and return its id.

    theme's "name" field is what the theme is displayed as, and what its
    id is derived from. The raw source is kept only so Settings can show
    back what was pasted. theme is what actually gets applied, via
    multitool.theme.build_theme.
    """
    current = _get_settings(page)
    themes = list(current.get(INSTALLED_THEMES_KEY, DEFAULT_INSTALLED_THEMES))
    theme_id = _unique_theme_id(page, theme["name"])
    themes.append({"id": theme_id, "source": source, **theme})
    current[INSTALLED_THEMES_KEY] = themes
    page.session.store.set(_SETTINGS_CACHE_KEY, current)
    settings_store.save(current)
    return theme_id


def remove_theme(page: ft.Page, theme_id: str) -> None:
    """Uninstall a theme. Falls back to System if it was the active one."""
    current = _get_settings(page)
    themes = [t for t in current.get(INSTALLED_THEMES_KEY, DEFAULT_INSTALLED_THEMES)
              if t.get("id") != theme_id]
    current[INSTALLED_THEMES_KEY] = themes
    if current.get(THEME_MODE_KEY) == theme_id:
        current[THEME_MODE_KEY] = "system"
    page.session.store.set(_SETTINGS_CACHE_KEY, current)
    settings_store.save(current)


def get_active_theme(page: ft.Page) -> Optional[dict]:
    """The installed theme currently selected in Appearance, or None if
    System, Light, or Dark is selected instead.
    """
    mode = get_theme_mode(page)
    if mode in BUILT_IN_THEME_MODES:
        return None
    return get_theme_by_id(page, mode)


def is_named_theme_active(page: ft.Page) -> bool:
    return get_active_theme(page) is not None


def resolve_theme_mode(page: ft.Page) -> ft.ThemeMode:
    """The ft.ThemeMode to render at, given the current Appearance choice.

    System/Light/Dark map directly. An installed theme renders at System
    brightness, unless it sets its own "brightness" field.
    """
    mode = get_theme_mode(page)
    if mode in BUILT_IN_THEME_MODES:
        return BUILT_IN_THEME_MODES[mode]
    return theme_brightness_mode(get_active_theme(page)) or ft.ThemeMode.SYSTEM
