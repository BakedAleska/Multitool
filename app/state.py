import flet as ft

from app.data import settings as settings_store

NAV_POSITION_KEY = "sidebar_pos"
DEFAULT_NAV_POSITION = settings_store.DEFAULTS[NAV_POSITION_KEY]

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
