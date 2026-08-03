"""Always-on-top borderless window that displays a single image.

No picture-viewer chrome, no taskbar entry, nothing but the image itself
pinned inside a user-chosen screen area, the same borderless/topmost
pattern widgets/autoclicker/backend/overlay.py already uses for its
"running" indicator.

Uses tkinter's own `PhotoImage`, which decodes PNG and GIF without any
extra dependency (Tk 8.6+). No JPEG support without Pillow, which this
project doesn't otherwise depend on, so PNG/GIF is what the widget's UI
offers.

Exits after printing one JSON line: `{"ready": true}` once the window is
up, or `{"error": "..."}` if the image couldn't be loaded. It has no
further stdout protocol after that, and no stdin protocol at all; the
widget stops it by terminating the process, same as the Autoclicker
indicator.
"""

import argparse
import json
import sys
import tkinter as tk

TRANSPARENT_KEY = "#010101"
"""Near-black fill color for the space in the area not covered by the
image. On Windows this is set as the window's transparent color, so
that space is see-through. There's no tkinter equivalent on macOS, so
it shows as a solid near-black box there instead.
"""


def _print(data: dict) -> None:
    print(json.dumps(data), flush=True)


def _make_click_through_windows(root: tk.Tk) -> None:
    """Best-effort: let clicks pass through the overlay on Windows."""
    try:
        import ctypes

        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        GWL_EXSTYLE = -20
        WS_EX_LAYERED = 0x80000
        WS_EX_TRANSPARENT = 0x20
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(
            hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT
        )
    except Exception:
        pass


def main() -> None:
    """Parse arguments, load and place the image, then block on the window.

    Exits with status 1 and one `{"error": "..."}` line if the image
    can't be decoded as PNG or GIF. On success, prints `{"ready": true}`
    once the window is showing and then blocks in `mainloop()` until the
    parent process kills it.

    The image is anchored to the area's top-left corner at its native
    size. An area smaller than the image clips it, since a tkinter
    Canvas doesn't draw past its own bounds; an area larger than the
    image leaves the remaining space as TRANSPARENT_KEY.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--x", type=int, default=0)
    parser.add_argument("--y", type=int, default=0)
    parser.add_argument("--width", type=int, default=0)
    parser.add_argument("--height", type=int, default=0)
    parser.add_argument("--click-through", action="store_true")
    args = parser.parse_args()

    root = tk.Tk()
    root.withdraw()

    try:
        image = tk.PhotoImage(file=args.image)
    except tk.TclError as e:
        _print({"error": f"Couldn't load this image as PNG or GIF. {e}"})
        sys.exit(1)

    width = args.width if args.width > 0 else image.width()
    height = args.height if args.height > 0 else image.height()

    root.overrideredirect(True)
    root.attributes("-topmost", True)

    root.geometry(f"{width}x{height}+{args.x}+{args.y}")

    canvas = tk.Canvas(
        root, width=width, height=height, bg=TRANSPARENT_KEY, highlightthickness=0
    )
    canvas.pack(fill="both", expand=True)
    canvas.create_image(0, 0, image=image, anchor="nw")
    root.deiconify()

    if sys.platform == "win32":
        try:
            root.attributes("-transparentcolor", TRANSPARENT_KEY)
        except tk.TclError:
            pass

    if args.click_through and sys.platform == "win32":
        root.after(50, lambda: _make_click_through_windows(root))

    _print({"ready": True})
    root.mainloop()


if __name__ == "__main__":
    main()
