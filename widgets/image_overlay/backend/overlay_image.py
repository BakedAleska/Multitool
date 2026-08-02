"""Always-on-top borderless window that displays a single image.

No picture-viewer chrome, no taskbar entry, nothing but the image itself
pinned to a screen corner (or the center), the same borderless/topmost
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

POSITIONS = ("top-left", "top-right", "bottom-left", "bottom-right", "center")


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


def _anchor(position: str, margin: int, screen_w: int, screen_h: int, w: int, h: int):
    """Top-left (x, y) to place a w x h image per the chosen anchor."""
    if position == "top-left":
        return margin, margin
    if position == "top-right":
        return screen_w - w - margin, margin
    if position == "bottom-left":
        return margin, screen_h - h - margin
    if position == "bottom-right":
        return screen_w - w - margin, screen_h - h - margin
    return (screen_w - w) // 2, (screen_h - h) // 2


def main() -> None:
    """Parse arguments, load and place the image, then block on the window.

    Exits with status 1 and one `{"error": "..."}` line if the image
    can't be decoded as PNG or GIF. On success, prints `{"ready": true}`
    once the window is showing and then blocks in `mainloop()` until the
    parent process kills it.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--position", choices=POSITIONS, default="top-right")
    parser.add_argument("--margin", type=int, default=24)
    parser.add_argument("--opacity", type=float, default=0.85)
    parser.add_argument("--click-through", action="store_true")
    args = parser.parse_args()

    root = tk.Tk()
    root.withdraw()

    try:
        image = tk.PhotoImage(file=args.image)
    except tk.TclError as e:
        _print({"error": f"Couldn't load this image as PNG or GIF. {e}"})
        sys.exit(1)

    root.overrideredirect(True)
    root.attributes("-topmost", True)
    try:
        root.attributes("-alpha", max(0.05, min(1.0, args.opacity)))
    except tk.TclError:
        pass

    width, height = image.width(), image.height()
    screen_w, screen_h = root.winfo_screenwidth(), root.winfo_screenheight()
    x, y = _anchor(args.position, args.margin, screen_w, screen_h, width, height)
    root.geometry(f"{width}x{height}+{x}+{y}")

    label = tk.Label(root, image=image, borderwidth=0, highlightthickness=0)
    label.pack()
    root.deiconify()

    if args.click_through and sys.platform == "win32":
        root.after(50, lambda: _make_click_through_windows(root))

    _print({"ready": True})
    root.mainloop()


if __name__ == "__main__":
    main()
