# Image Overlay

Pins an image on top of everything else on screen, by default while Roblox
is open. `widget.py` builds the UI with Flet, but the overlay itself is a
separate always-on-top, borderless window (`backend/overlay_image.py`) it
starts and stops, the same any-language-backend pattern `widgets/autoclicker`
uses. That window has no picture-viewer chrome and no taskbar entry, so
nothing about it looks like a window was opened at all.

By default, pressing Start doesn't show the image immediately. It arms a
background poll (`multitool/roblox/detect.py::is_roblox_running`, checked
every few seconds) that starts the overlay window only while Roblox is
running, and stops it the moment Roblox closes. Press Stop to disarm it
entirely.

## Watching for an app

Settings has two controls for this:

- **"Only show while an app is open"**, on by default. Turn it off and the
  overlay shows as soon as Start is pressed and stays up until Stop,
  regardless of what else is running.
- With that on, **"Choose a different app..."** picks an `.exe` (Windows) or
  app bundle (macOS) to watch for instead of Roblox. "Use Roblox instead"
  clears the choice back to the default.

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
screen...", which opens a fullscreen picker: the whole screen dims, and
you click and drag to draw a rectangle, highlighted in cyan with corner
handles and a live width x height label. Press Enter to confirm it (or
Escape to cancel). Either way the area is saved immediately, so it's
still there next time the app opens.

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
