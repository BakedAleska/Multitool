"""Shared visual constants and theme-aware helpers, so every card and
container uses the same corner rounding and border style.
"""

import flet as ft

from app.state import get_custom_theme, is_custom_theme_active

RADIUS_CARD = 12
"""Default radius for bordered cards and list items. Used by account
cards, widget squares, dashboard account tiles, and the nav rail's
widget rows.
"""

RADIUS_HERO = 16
"""Default radius for large, single prominent containers, such as the
Dashboard's hero card.
"""

RADIUS_PILL = 999
"""Radius for fully rounded chip and pill elements. Flutter clamps this
to half the container's shorter side, so it always produces a full pill.
Not affected by a custom theme: pills stay fully round regardless of
corner_radius.
"""


def radius_card(page: ft.Page) -> float:
    """The card radius, using the active custom theme's corner_radius if set."""
    if is_custom_theme_active(page):
        theme = get_custom_theme(page)
        if theme and "corner_radius" in theme:
            return theme["corner_radius"]
    return RADIUS_CARD


def radius_hero(page: ft.Page) -> float:
    """The hero radius, keeping the same offset above the card radius."""
    return radius_card(page) + (RADIUS_HERO - RADIUS_CARD)


def card_border() -> ft.Border:
    """The standard 1px outline used on every bordered card.

    Returns a fresh Border on each call. Flet controls shouldn't share
    one mutable property object.
    """
    return ft.Border.all(1, ft.Colors.OUTLINE_VARIANT)
