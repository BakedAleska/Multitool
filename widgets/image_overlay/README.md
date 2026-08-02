# Image Overlay

Pins an image on top of everything else on screen. `widget.py` builds the UI
with Flet, but the overlay itself is a separate always-on-top, borderless
window (`backend/overlay_image.py`) it starts and stops, the same
any-language-backend pattern `widgets/autoclicker` uses. That window has no
picture-viewer chrome and no taskbar entry, so nothing about it looks like a
window was opened at all.

Only PNG and GIF are supported. The backend decodes images with tkinter's
own `PhotoImage`, so it needs no extra dependency, but tkinter can't decode
JPEG on its own.

The backend prints one JSON line on startup: `{"ready": true}`, or
`{"error": "..."}` if the image couldn't be loaded. It has no further stdout
protocol and no stdin protocol at all; the widget stops it by terminating
the process, same as the Autoclicker indicator.

## Area

The image shows at its native size, anchored to the top-left corner of a
rectangular area (X, Y, Width, Height in screen pixels). There's no
resizing; pick an image that's already the size you want on screen. If
the area is smaller than the image, the image is clipped to it; if it's
larger, the extra space is transparent on Windows (a solid near-black
box on macOS, which has no equivalent transparency trick).

The area can be typed in directly, or set by clicking "Pick area on
screen...", which opens a fullscreen picker: the screen's edges are
outlined in red, and you click and drag to draw a rectangle, then press
Enter to confirm it (or Escape to cancel). Either way the area is saved
immediately, so it's still there next time the app opens.

## Click-through

On Windows, "Click-through" makes the overlay pass clicks to whatever's
under it, via the same Win32 extended style flag `widgets/autoclicker`'s
indicator uses. There's no tkinter equivalent on macOS, so the checkbox has
no effect there.

## Trying it locally

Copy this `image_overlay` folder into the widgets folder shown in
Settings -> Widgets, then enable it from the Widgets screen.

## See also

`multitool/widgets/process.py` is the shared helper any widget can use to
start, message, and stop a non-Python backend process like this one.
