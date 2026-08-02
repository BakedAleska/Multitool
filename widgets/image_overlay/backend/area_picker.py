"""Fullscreen click-and-drag rectangle picker for the Image Overlay widget.

A borderless, topmost, red-bordered window covering the whole screen.
Click and drag to draw a rectangle; press Enter to confirm it or Escape
to cancel. Prints exactly one JSON line and exits, the same one-shot
subprocess pattern multitool/roblox/login.py uses: `{"x", "y", "width",
"height"}` on confirm, or `{"cancelled": true}` on cancel. Printing
nothing at all (e.g. the window was closed some other way) is treated
by the caller the same as a cancel.
"""

import json
import tkinter as tk

INSTRUCTIONS = "Click and drag to select an area. Enter to confirm, Esc to cancel."


def _print(data: dict) -> None:
    print(json.dumps(data), flush=True)


def main() -> None:
    """Show the picker and block until the user confirms or cancels."""
    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    try:
        root.attributes("-alpha", 0.35)
    except tk.TclError:
        pass

    screen_w, screen_h = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"{screen_w}x{screen_h}+0+0")

    canvas = tk.Canvas(root, width=screen_w, height=screen_h, bg="black", highlightthickness=0)
    canvas.pack(fill="both", expand=True)

    border = 4
    canvas.create_rectangle(
        border // 2,
        border // 2,
        screen_w - border // 2,
        screen_h - border // 2,
        outline="red",
        width=border,
    )
    canvas.create_text(
        screen_w // 2, 32, text=INSTRUCTIONS, fill="red", font=("Segoe UI", 14, "bold")
    )

    state = {"start": None, "current": None, "rect": None}

    def on_press(event):
        state["start"] = (event.x, event.y)
        state["current"] = (event.x, event.y)
        if state["rect"] is not None:
            canvas.delete(state["rect"])
            state["rect"] = None

    def on_drag(event):
        if state["start"] is None:
            return
        state["current"] = (event.x, event.y)
        if state["rect"] is not None:
            canvas.delete(state["rect"])
        x0, y0 = state["start"]
        state["rect"] = canvas.create_rectangle(
            x0, y0, event.x, event.y, outline="red", width=2, dash=(6, 4)
        )

    def on_confirm(event=None):
        if state["start"] is None or state["current"] is None:
            return
        x0, y0 = state["start"]
        x1, y1 = state["current"]
        x, y = min(x0, x1), min(y0, y1)
        width, height = abs(x1 - x0), abs(y1 - y0)
        if width < 4 or height < 4:
            return
        _print({"x": x, "y": y, "width": width, "height": height})
        root.destroy()

    def on_cancel(event=None):
        _print({"cancelled": True})
        root.destroy()

    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<B1-Motion>", on_drag)
    root.bind("<Return>", on_confirm)
    root.bind("<KP_Enter>", on_confirm)
    root.bind("<Escape>", on_cancel)
    root.focus_force()

    root.mainloop()


if __name__ == "__main__":
    main()
