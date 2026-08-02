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

## Positioning

The image shows at its native size, anchored to one of five presets (the
four corners or center) with a configurable margin in pixels. There's no
resizing; pick an image that's already the size you want on screen.

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
