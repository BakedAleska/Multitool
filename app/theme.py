"""Parse and apply a user-supplied custom theme.

A theme is a small JSON object, either pasted directly into Settings or
fetched from a link, for example a raw GitHub URL. Recognized fields:

- "accent_color": a hex string, such as "#7C3AED".
- "corner_radius": a non-negative number.
- "font_family": a font name already available on the system.
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

from app.logs import get_logger

logger = get_logger(__name__)

MAX_THEME_BYTES = 100_000

_HEX_COLOR_PATTERN = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

BACKGROUND_FIT_MAP = {
    "cover": ft.BoxFit.COVER,
    "contain": ft.BoxFit.CONTAIN,
    "fill": ft.BoxFit.FILL,
    "none": ft.BoxFit.NONE,
}


def _looks_like_url(text: str) -> bool:
    return text.startswith(("http://", "https://"))


def _validate(raw: dict) -> dict:
    """Keep only the known, well-formed fields from a raw theme dict."""
    theme = {}

    accent_color = raw.get("accent_color")
    if isinstance(accent_color, str) and _HEX_COLOR_PATTERN.match(accent_color):
        theme["accent_color"] = accent_color

    corner_radius = raw.get("corner_radius")
    if isinstance(corner_radius, (int, float)) and corner_radius >= 0:
        theme["corner_radius"] = corner_radius

    font_family = raw.get("font_family")
    if isinstance(font_family, str) and font_family.strip():
        theme["font_family"] = font_family.strip()

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
    if not theme:
        return None, "None of the theme's fields were recognized. Did you use the right key names?"

    return theme, None


def build_theme(custom_theme: Optional[dict]) -> ft.Theme:
    """Build the app's Theme, applying a custom theme's overrides if any.

    Page transitions are always disabled, regardless of any custom
    theme: instant view switches are a deliberate choice for this app,
    not something a theme should be able to turn back on.
    """
    kwargs: dict = {
        "page_transitions": ft.PageTransitionsTheme(
            windows=ft.PageTransitionTheme.NONE,
            macos=ft.PageTransitionTheme.NONE,
            linux=ft.PageTransitionTheme.NONE,
            android=ft.PageTransitionTheme.NONE,
            ios=ft.PageTransitionTheme.NONE,
        )
    }

    if custom_theme:
        if "accent_color" in custom_theme:
            kwargs["color_scheme_seed"] = custom_theme["accent_color"]
        if "font_family" in custom_theme:
            kwargs["font_family"] = custom_theme["font_family"]

    return ft.Theme(**kwargs)
