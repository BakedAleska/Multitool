"""Parse and apply a user-supplied theme.

A theme is a small JSON object, either pasted directly into Settings or
fetched from a link, for example a raw GitHub URL. A user can install
several themes at once and switch between them (or System / Light /
Dark) from Settings. Recognized fields:

- "name": the theme's display name, shown in Appearance and the
  Installed Themes list. Required.
- "accent_color": a hex string, such as "#7C3AED".
- "secondary_color": a hex string for secondary accents (buttons,
  highlights that aren't the primary accent).
- "background_color": a hex string used as the page's solid background.
- "card_color": a hex string used as the background of cards and
  bordered containers.
- "divider_color": a hex string used for dividers and outlines.
- "corner_radius": a non-negative number.
- "font_family": a font name already available on the system.
- "brightness": "light" or "dark". Forces the app to render at that
  brightness while this theme is active, instead of following System
  Light/Dark.
- "background_image": a URL or a local file path.
- "background_fit": how the image fills the window. One of "cover",
  "contain", "fill", or "none". Defaults to "cover".
- "background_opacity": a number from 0 to 1. Defaults to 1.

Unknown fields are ignored, and a missing field just leaves that part
of the app at its default. background_fit and background_opacity only
matter if background_image is also set.
"""

import json
import re
from typing import Optional

import flet as ft
import httpx

from multitool.logs import get_logger

logger = get_logger(__name__)

MAX_THEME_BYTES = 100_000

_HEX_COLOR_PATTERN = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

BACKGROUND_FIT_MAP = {
    "cover": ft.BoxFit.COVER,
    "contain": ft.BoxFit.CONTAIN,
    "fill": ft.BoxFit.FILL,
    "none": ft.BoxFit.NONE,
}

BRIGHTNESS_MAP = {
    "light": ft.ThemeMode.LIGHT,
    "dark": ft.ThemeMode.DARK,
}


def _looks_like_url(text: str) -> bool:
    return text.startswith(("http://", "https://"))


def _validate(raw: dict) -> dict:
    """Keep only the known, well-formed fields from a raw theme dict."""
    theme = {}

    name = raw.get("name")
    if isinstance(name, str) and name.strip():
        theme["name"] = name.strip()

    for key in ("accent_color", "secondary_color", "background_color", "card_color",
                "divider_color"):
        value = raw.get(key)
        if isinstance(value, str) and _HEX_COLOR_PATTERN.match(value):
            theme[key] = value

    corner_radius = raw.get("corner_radius")
    if isinstance(corner_radius, (int, float)) and corner_radius >= 0:
        theme["corner_radius"] = corner_radius

    font_family = raw.get("font_family")
    if isinstance(font_family, str) and font_family.strip():
        theme["font_family"] = font_family.strip()

    brightness = raw.get("brightness")
    if isinstance(brightness, str) and brightness.lower() in BRIGHTNESS_MAP:
        theme["brightness"] = brightness.lower()

    background_image = raw.get("background_image")
    if isinstance(background_image, str) and background_image.strip():
        theme["background_image"] = background_image.strip()

    background_fit = raw.get("background_fit")
    if isinstance(background_fit, str) and background_fit.lower() in BACKGROUND_FIT_MAP:
        theme["background_fit"] = background_fit.lower()

    background_opacity = raw.get("background_opacity")
    if isinstance(background_opacity, (int, float)) and 0 <= background_opacity <= 1:
        theme["background_opacity"] = background_opacity

    return theme


def parse_theme_input(raw_input: str) -> tuple[Optional[dict], Optional[str]]:
    """Parse pasted theme JSON, or fetch and parse it from a link.

    Never raises. Returns (theme, None) on success, or (None, error) on
    failure. Blocking: call this via asyncio.to_thread from UI code.
    """
    raw_input = raw_input.strip()
    if not raw_input:
        return None, "No theme was provided."

    if _looks_like_url(raw_input):
        try:
            response = httpx.get(raw_input, timeout=15, follow_redirects=True)
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning("Couldn't fetch theme from %s: %s", raw_input, e)
            return None, f"Couldn't fetch the theme. Is the link correct? ({e})"
        text = response.text
    else:
        text = raw_input

    if len(text.encode("utf-8")) > MAX_THEME_BYTES:
        return None, "The theme is too large. Is the link pointing at the right file?"

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None, "The pasted theme isn't valid JSON. Did you copy the whole file?"

    if not isinstance(data, dict):
        return None, "The pasted theme isn't a JSON object. Did you paste the right file?"

    theme = _validate(data)
    if "name" not in theme:
        return None, 'The theme is missing a "name" field. What should it be called?'
    if len(theme) == 1:
        return None, "None of the theme's fields were recognized. Did you use the right key names?"

    return theme, None


SCROLLBAR_THICKNESS = 6
"""Width of every scrollbar in the app, in logical pixels. Kept slim and
uniform (see build_theme's scrollbar_theme) so a scrollbar reads as a
quiet edge detail rather than competing with the content next to it.
"""


def _scrollbar_theme(theme: Optional[dict]) -> ft.ScrollbarTheme:
    """The app-wide scrollbar look: a thin, fully rounded thumb with no
    visible track, so every scrollable list, grid, and column shares one
    consistent style. Falls back to the theme's outline/divider color if
    it sets one, otherwise Material's default outline color.
    """
    thumb_color = (theme or {}).get("divider_color")
    return ft.ScrollbarTheme(
        thickness=SCROLLBAR_THICKNESS,
        radius=SCROLLBAR_THICKNESS / 2,
        thumb_color=thumb_color or ft.Colors.OUTLINE_VARIANT,
        track_color=ft.Colors.TRANSPARENT,
        track_visibility=False,
        thumb_visibility=False,
        interactive=True,
        cross_axis_margin=2,
        main_axis_margin=2,
    )


def build_theme(theme: Optional[dict]) -> ft.Theme:
    """Build the app's Theme, applying an installed theme's overrides if any.

    Page transitions are always disabled, regardless of any theme:
    instant view switches are a deliberate choice for this app, not
    something a theme should be able to turn back on.
    """
    kwargs: dict = {
        "page_transitions": ft.PageTransitionsTheme(
            windows=ft.PageTransitionTheme.NONE,
            macos=ft.PageTransitionTheme.NONE,
            linux=ft.PageTransitionTheme.NONE,
            android=ft.PageTransitionTheme.NONE,
            ios=ft.PageTransitionTheme.NONE,
        ),
        "scrollbar_theme": _scrollbar_theme(theme),
    }

    if theme:
        if "accent_color" in theme:
            kwargs["color_scheme_seed"] = theme["accent_color"]
        if "secondary_color" in theme:
            kwargs["color_scheme"] = ft.ColorScheme(secondary=theme["secondary_color"])
        if "font_family" in theme:
            kwargs["font_family"] = theme["font_family"]
        if "background_color" in theme:
            kwargs["scaffold_bgcolor"] = theme["background_color"]
        if "card_color" in theme:
            kwargs["card_bgcolor"] = theme["card_color"]
        if "divider_color" in theme:
            kwargs["divider_color"] = theme["divider_color"]

    return ft.Theme(**kwargs)


def theme_brightness_mode(theme: Optional[dict]) -> Optional[ft.ThemeMode]:
    """The ThemeMode a theme's "brightness" field forces, or None if unset."""
    if not theme:
        return None
    return BRIGHTNESS_MAP.get(theme.get("brightness"))
