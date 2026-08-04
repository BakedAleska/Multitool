"""The system tray icon shown when "Run in background" is on.

pystray runs its own blocking loop on a background thread, since it isn't
asyncio-aware. Its menu callbacks fire on that thread too, so they must
never touch `page` state directly - they hand off to the page's event
loop via `page.run_task`, which is safe to call from another thread
(it wraps `asyncio.run_coroutine_threadsafe`).
"""

import sys
import threading
from typing import Optional

import flet as ft
from PIL import Image, ImageDraw, ImageFont

from toolblox.logs import get_logger
from toolblox.widgets.process import stop_all_processes

try:
    import pystray
except ImportError:
    pystray = None

logger = get_logger(__name__)

_icon: Optional["pystray.Icon"] = None
_icon_lock = threading.Lock()


def _build_icon_image() -> Image.Image:
    """Draw the tray icon: a rounded square with a white "T" on it.

    Drawn with PIL instead of loading a bundled .ico file, since a
    packaged build only ships the `assets/` folder, not the repo's
    other directories, and this way there's no bundled-path resolution
    to get wrong across dev vs. packaged runs.
    """
    size = 64
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((2, 2, size - 2, size - 2), radius=14, fill=(0x62, 0x4C, 0xF5, 255))
    try:
        font = ImageFont.truetype("arialbd.ttf", 38)
    except OSError:
        font = ImageFont.load_default()
    draw.text((size / 2, size / 2 + 2), "T", fill="white", font=font, anchor="mm")
    return image


def is_supported() -> bool:
    """Whether a tray icon can be shown on this platform."""
    return pystray is not None and sys.platform in ("win32", "darwin", "linux")


def is_showing() -> bool:
    return _icon is not None


def show(page: ft.Page) -> None:
    """Show the tray icon, if it isn't already showing.

    Safe to call repeatedly; a no-op while the icon is already up.
    """
    global _icon
    if not is_supported():
        return

    with _icon_lock:
        if _icon is not None:
            return

        def on_open(icon, item):
            page.run_task(_restore, page)

        def on_quit(icon, item):
            page.run_task(_quit, page)

        image = _build_icon_image()
        menu = pystray.Menu(
            pystray.MenuItem("Open Toolblox", on_open, default=True),
            pystray.MenuItem("Quit", on_quit),
        )
        _icon = pystray.Icon("toolblox", image, "Toolblox", menu)
        threading.Thread(target=_icon.run, daemon=True).start()


def hide() -> None:
    """Remove the tray icon, if one is showing."""
    global _icon
    with _icon_lock:
        if _icon is None:
            return
        _icon.stop()
        _icon = None


async def _restore(page: ft.Page) -> None:
    """Bring the window back from the tray."""
    hide()
    page.window.skip_task_bar = False
    page.window.visible = True
    await page.window.to_front()
    page.update()


async def _quit(page: ft.Page) -> None:
    """Fully exit the app from the tray menu, bypassing prevent_close."""
    hide()
    stop_all_processes(page)
    page.window.prevent_close = False
    await page.window.destroy()
