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
}

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

_SETTINGS_CACHE_KEY = "_settings_cache"


def _get_settings(page: ft.Page) -> dict:
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
