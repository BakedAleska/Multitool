"""Image Overlay: pins a picture to the screen, on top of everything else.

Its UI is Flet, like any widget. What actually shows the image is a
separate always-on-top, borderless window (backend/overlay_image.py),
started and stopped the same way widgets/autoclicker starts and stops
its click loop backend, via multitool/widgets/process.py. That backend
window has no picture-viewer chrome and no taskbar entry, so nothing
about it looks like "a window" was opened at all.

Only PNG and GIF are supported. The backend uses tkinter's own image
decoder rather than adding Pillow as a dependency, and tkinter can't
decode JPEG on its own.

Pressing Start doesn't show the image right away. It arms a background
poll (multitool/roblox/detect.py::is_roblox_running) that starts the
backend window only while a Roblox game client process exists, and stops
it the moment Roblox closes, so the overlay never lingers on the desktop
after the game it belongs to has closed.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import flet as ft

from multitool.roblox.detect import is_roblox_running
from multitool.state import get_widget_setting, set_widget_setting
from multitool.ui.layout import build_layout, widget_route
from multitool.widgets.api import Widget
from multitool.widgets.process import WidgetProcess, start_process, stop_process

BACKEND_SCRIPT = Path(__file__).parent / "backend" / "overlay_image.py"
AREA_PICKER_SCRIPT = Path(__file__).parent / "backend" / "area_picker.py"

WIDGET_ID = "image_overlay"
_PROCESS_KEY = f"_{WIDGET_ID}_process"
_POLL_STATE_KEY = f"_{WIDGET_ID}_poll_state"

DEFAULT_AREA = {"x": 100, "y": 100, "width": 300, "height": 300}
DEFAULT_CLICK_THROUGH = True
POLL_INTERVAL_SECONDS = 3.0


def _backend_command(image_path: str, area: dict, click_through: bool) -> list[str]:
    """The command that starts `backend/overlay_image.py` with these options."""
    command = [
        sys.executable,
        str(BACKEND_SCRIPT),
        "--image",
        image_path,
        "--x",
        str(area["x"]),
        "--y",
        str(area["y"]),
        "--width",
        str(area["width"]),
        "--height",
        str(area["height"]),
    ]
    if click_through:
        command.append("--click-through")
    return command


async def _pick_area() -> Optional[dict]:
    """Run the fullscreen area picker and return the rectangle it chose.

    Spawns `backend/area_picker.py` as a one-shot subprocess and reads
    the single JSON line it prints, the same pattern
    multitool/roblox/login.py uses for its own subprocess. Returns None
    if the user cancelled, closed the picker some other way, or it
    printed nothing at all.
    """
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        str(AREA_PICKER_SCRIPT),
        stdout=asyncio.subprocess.PIPE,
    )
    line = await proc.stdout.readline()
    await proc.wait()
    if not line:
        return None
    try:
        data = json.loads(line)
    except ValueError:
        return None
    if "x" not in data:
        return None
    return {"x": data["x"], "y": data["y"], "width": data["width"], "height": data["height"]}


def _parse_area(x_field: ft.TextField, y_field: ft.TextField, w_field: ft.TextField,
                 h_field: ft.TextField, fallback: dict) -> dict:
    """Read the four area fields, falling back to `fallback` per-field on
    a bad or empty value, and clamping width/height to at least 1.
    """

    def _int(value: Optional[str], default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    x = _int(x_field.value, fallback["x"])
    y = _int(y_field.value, fallback["y"])
    width = max(1, _int(w_field.value, fallback["width"]))
    height = max(1, _int(h_field.value, fallback["height"]))
    return {"x": x, "y": y, "width": width, "height": height}


def build_view(page: ft.Page) -> ft.View:
    """The Image Overlay's own screen: pick an image, place it, pin it."""
    area = get_widget_setting(page, WIDGET_ID, "area", DEFAULT_AREA)
    default_click_through = get_widget_setting(
        page, WIDGET_ID, "default_click_through", DEFAULT_CLICK_THROUGH
    )

    image_path_text = ft.Text("No image selected.", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
    status_text = ft.Text("Stopped", weight=ft.FontWeight.W_600)
    pick_button = ft.OutlinedButton("Choose image (PNG or GIF)")
    x_field = ft.TextField(label="X", value=str(area["x"]), width=90)
    y_field = ft.TextField(label="Y", value=str(area["y"]), width=90)
    width_field = ft.TextField(label="Width", value=str(area["width"]), width=90)
    height_field = ft.TextField(label="Height", value=str(area["height"]), width=90)
    pick_area_button = ft.OutlinedButton("Pick area on screen...")
    click_through_checkbox = ft.Checkbox(
        label="Click-through (Windows only)", value=default_click_through
    )
    start_button = ft.FilledButton("Start", disabled=True)
    stop_button = ft.FilledButton("Stop", disabled=True)

    file_picker = ft.FilePicker()

    def set_state(armed: bool, active: bool):
        """Reflect the current arm/active state in the status text and
        control disabled-states.

        `armed` means Start has been pressed and the poll loop is
        watching for Roblox; `active` means Roblox is currently open and
        the overlay window is actually showing. `active` implies `armed`.
        """
        if not armed:
            status_text.value = "Stopped"
        elif active:
            status_text.value = "Running"
        else:
            status_text.value = "Waiting for Roblox..."
        start_button.disabled = armed or not image_path_text.data
        stop_button.disabled = not armed
        pick_button.disabled = armed
        x_field.disabled = armed
        y_field.disabled = armed
        width_field.disabled = armed
        height_field.disabled = armed
        pick_area_button.disabled = armed
        click_through_checkbox.disabled = armed
        page.update()

    def save_area() -> dict:
        """Read the area fields, persist them, and write the parsed
        values back into the fields so an out-of-range entry is
        visibly corrected.
        """
        current = _parse_area(x_field, y_field, width_field, height_field, area)
        x_field.value = str(current["x"])
        y_field.value = str(current["y"])
        width_field.value = str(current["width"])
        height_field.value = str(current["height"])
        set_widget_setting(page, WIDGET_ID, "area", current)
        return current

    async def on_pick(e: ft.Event[ft.OutlinedButton]):
        """Open the file picker and store the chosen image's path.

        The path is stashed on `image_path_text.data` rather than a
        separate variable, since it needs to survive past this closure
        into on_start() without adding another piece of session state.
        """
        files = await file_picker.pick_files(
            allow_multiple=False, allowed_extensions=["png", "gif"]
        )
        if not files:
            return
        picked = files[0]
        image_path_text.value = picked.name
        image_path_text.data = picked.path
        start_button.disabled = False
        page.update()

    async def on_pick_area(e: ft.Event[ft.OutlinedButton]):
        """Run the fullscreen area picker and apply the rectangle it
        returns to the area fields, saving it immediately.
        """
        pick_area_button.disabled = True
        page.update()
        picked = await _pick_area()
        pick_area_button.disabled = False
        if picked is not None:
            x_field.value = str(picked["x"])
            y_field.value = str(picked["y"])
            width_field.value = str(picked["width"])
            height_field.value = str(picked["height"])
            set_widget_setting(page, WIDGET_ID, "area", picked)
        page.update()

    def on_area_field_blur(e: ft.Event[ft.TextField]):
        save_area()
        page.update()

    def _disarm():
        """Stop the poll loop and clear armed state, without touching
        whatever the caller has already put in status_text/image_path_text.
        """
        poll_state = page.session.store.get(_POLL_STATE_KEY)
        if poll_state is not None:
            poll_state["armed"] = False
        page.session.store.set(_POLL_STATE_KEY, None)

    def on_line(data: dict):
        """Surface a backend startup error, if the process reported one.

        An error disarms the poll loop entirely rather than letting it
        keep retrying, since a bad image or area won't fix itself on the
        next Roblox open. A clean `{"ready": true}` line needs no UI
        change here, since the poll loop already flipped to "Running"
        before this fires.
        """
        error = data.get("error")
        if error:
            status_text.value = "Error"
            image_path_text.value = error
            page.session.store.set(_PROCESS_KEY, None)
            _disarm()
            set_state(armed=False, active=False)

    def on_exit(code: int):
        """Reflect an overlay window's exit, whether the poll loop closed
        it because Roblox closed, or it crashed on its own.

        If the poll loop is still armed, this just means Roblox isn't
        open right now - fall back to "Waiting for Roblox...", the poll
        loop keeps running. If it's not armed, Stop or on_line already
        set the final state, so this is a no-op.
        """
        page.session.store.set(_PROCESS_KEY, None)
        poll_state = page.session.store.get(_POLL_STATE_KEY)
        if poll_state is not None and poll_state["armed"]:
            set_state(armed=True, active=False)

    async def _poll_roblox(command: list[str], poll_state: dict):
        """While armed, start the overlay backend when Roblox is running
        and stop it when Roblox isn't, checking every
        POLL_INTERVAL_SECONDS.

        `poll_state["armed"]` is a plain dict rather than a variable so
        on_stop/on_line can flip it from outside this coroutine and have
        the next wake-up see it.
        """
        while poll_state["armed"]:
            roblox_open = await asyncio.to_thread(is_roblox_running)
            if not poll_state["armed"]:
                break
            current_process: WidgetProcess | None = page.session.store.get(_PROCESS_KEY)
            if roblox_open and current_process is None:
                widget_process = await start_process(
                    page, *command, on_line=on_line, on_exit=on_exit
                )
                if not poll_state["armed"]:
                    stop_process(widget_process)
                    break
                page.session.store.set(_PROCESS_KEY, widget_process)
                set_state(armed=True, active=True)
            elif not roblox_open and current_process is not None:
                stop_process(current_process)
                page.session.store.set(_PROCESS_KEY, None)
                set_state(armed=True, active=False)
            await asyncio.sleep(POLL_INTERVAL_SECONDS)

    async def on_start(e: ft.Event[ft.FilledButton]):
        image_path = image_path_text.data
        if not image_path:
            return
        current_area = save_area()

        command = _backend_command(
            image_path,
            current_area,
            click_through_checkbox.value or False,
        )
        poll_state = {"armed": True}
        page.session.store.set(_POLL_STATE_KEY, poll_state)
        set_state(armed=True, active=False)
        page.run_task(_poll_roblox, command, poll_state)

    def on_stop(e: ft.Event[ft.FilledButton]):
        _disarm()
        widget_process: WidgetProcess | None = page.session.store.get(_PROCESS_KEY)
        if widget_process is not None:
            stop_process(widget_process)
        page.session.store.set(_PROCESS_KEY, None)
        set_state(armed=False, active=False)

    pick_button.on_click = on_pick
    pick_area_button.on_click = on_pick_area
    for field in (x_field, y_field, width_field, height_field):
        field.on_blur = on_area_field_blur
    start_button.on_click = on_start
    stop_button.on_click = on_stop

    content = ft.Column(
        [
            ft.Text("Image Overlay", size=24, weight=ft.FontWeight.BOLD),
            ft.Text(
                "Pins an image on top of everything else on screen, inside "
                "the area below, with no window chrome or taskbar entry. "
                "Shows only while Roblox is open, and hides automatically "
                "once it closes.",
                size=12,
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
            ft.Row([pick_button, image_path_text]),
            ft.Text("Area", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            ft.Row([x_field, y_field, width_field, height_field]),
            pick_area_button,
            click_through_checkbox,
            ft.Row([start_button, stop_button]),
            status_text,
        ],
        spacing=12,
    )

    return ft.View(
        route=widget_route("image_overlay"),
        padding=0,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[build_layout(page, content)],
        services=[file_picker],
    )


def build_settings(page: ft.Page) -> ft.Control:
    """The Image Overlay's Settings section: defaults for a fresh screen."""

    area = get_widget_setting(page, WIDGET_ID, "area", DEFAULT_AREA)
    x_field = ft.TextField(label="X", value=str(area["x"]), width=90)
    y_field = ft.TextField(label="Y", value=str(area["y"]), width=90)
    width_field = ft.TextField(label="Width", value=str(area["width"]), width=90)
    height_field = ft.TextField(label="Height", value=str(area["height"]), width=90)

    def on_area_field_blur(e: ft.Event[ft.TextField]):
        current = _parse_area(x_field, y_field, width_field, height_field, area)
        x_field.value = str(current["x"])
        y_field.value = str(current["y"])
        width_field.value = str(current["width"])
        height_field.value = str(current["height"])
        e.control.update()
        set_widget_setting(page, WIDGET_ID, "area", current)

    for field in (x_field, y_field, width_field, height_field):
        field.on_blur = on_area_field_blur

    def on_click_through_change(e: ft.Event[ft.Checkbox]):
        set_widget_setting(page, WIDGET_ID, "default_click_through", e.control.value)

    default_click_through = get_widget_setting(
        page, WIDGET_ID, "default_click_through", DEFAULT_CLICK_THROUGH
    )

    return ft.Column(
        [
            ft.Text(
                "These are the values the Image Overlay screen starts with "
                "each time it opens. The area is also editable, and saved "
                "immediately, from the Image Overlay screen itself.",
                size=12,
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
            ft.Text("Area", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            ft.Row([x_field, y_field, width_field, height_field]),
            ft.Checkbox(
                label="Click-through by default (Windows only)",
                value=default_click_through,
                on_change=on_click_through_change,
            ),
        ],
        spacing=8,
    )


WIDGET = Widget(
    id=WIDGET_ID,
    name="Image Overlay",
    description="Pins an image on top of everything else on screen while Roblox is open.",
    build_view=build_view,
    build_settings=build_settings,
    icon=ft.Icons.IMAGE_OUTLINED,
    selected_icon=ft.Icons.IMAGE,
)
