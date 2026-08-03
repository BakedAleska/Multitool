"""Shared visual constants and theme-aware helpers, so every card and
container uses the same corner rounding and border style.
"""

import flet as ft

from multitool.state import get_active_theme

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

SWITCH_SCALE = 0.8
"""Scale for every ft.Switch in the app, so on/off toggles read as a
compact control next to a settings row instead of Flutter's oversized
default."""

SPACE_XS = 4
"""Spacing between a label and its own caption directly beneath it."""

SPACE_SM = 8
"""Spacing between closely related controls in a row, or list item
spacing in compact mode."""

SPACE_MD = 12
"""Default row/column spacing. The most common gap in the app - reach
for this first."""

SPACE_LG = 16
"""Spacing between distinct sections on the same screen."""

SPACE_XL = 24
"""Spacing for a hero card's internal breathing room. Rare - most
spacing should use a smaller step."""


def text_title(value: str, **kwargs: object) -> ft.Text:
    """A view's own title, e.g. "Dashboard" or "Settings". One per screen,
    always the first thing on it.
    """
    return ft.Text(value, size=24, weight=ft.FontWeight.BOLD, **kwargs)


def text_section(value: str, **kwargs: object) -> ft.Text:
    """A titled group inside a screen, e.g. "Appearance" or "Danger Zone"."""
    return ft.Text(value, size=14, weight=ft.FontWeight.W_600, **kwargs)


def text_label(value: str, **kwargs: object) -> ft.Text:
    """A single control's own name, e.g. "Show avatars" next to its switch."""
    return ft.Text(value, size=14, weight=ft.FontWeight.W_500, **kwargs)


def text_caption(value: str, **kwargs: object) -> ft.Text:
    """Muted helper or secondary text under a label or section."""
    return ft.Text(value, size=12, color=ft.Colors.ON_SURFACE_VARIANT, **kwargs)

FORM_FIELD_HEIGHT = 120
"""Height for a settings screen's larger text input boxes, such as the
Install a Theme paste box and the Place ID field, so the two read as
the same size instead of one dwarfing the other.
"""

SCROLL_GUTTER = 12
"""Space reserved on the trailing edge of every vertically scrolling
list or column, so the scrollbar rendered there never sits on top of a
button, switch, or other edge-aligned control. Paired with the app-wide
ScrollbarTheme built in multitool.theme.build_theme, which sets the
scrollbar's own thickness and color. Applied via scroll_padding() for
controls with a padding property (ListView, GridView) and
scroll_margin() for controls that only have margin (Column, Row).
"""


def scroll_padding() -> ft.Padding:
    """Trailing-edge clearance for a scrollable control that has its own
    padding property, such as ListView or GridView. See SCROLL_GUTTER.
    """
    return ft.Padding.only(right=SCROLL_GUTTER)


def scroll_margin() -> ft.Margin:
    """Trailing-edge clearance for a scrollable control that only has
    margin, such as Column or Row. See SCROLL_GUTTER.
    """
    return ft.Margin.only(right=SCROLL_GUTTER)


def thin_button_style() -> ft.ButtonStyle:
    """A shorter button, for buttons sitting in a settings form instead
    of standing alone as a primary call to action.

    Returns a fresh ButtonStyle on each call, matching card_border's
    no-shared-mutable-property convention.
    """
    return ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=16, vertical=8))


def radius_card(page: ft.Page) -> float:
    """The card radius, using the active theme's corner_radius if set."""
    theme = get_active_theme(page)
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
