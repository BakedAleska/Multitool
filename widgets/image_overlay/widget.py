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
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import flet as ft

from multitool.state import get_widget_setting, set_widget_setting
from multitool.ui.layout import build_layout, widget_route
from multitool.widgets.api import Widget
from multitool.widgets.process import WidgetProcess, start_process, stop_process

BACKEND_SCRIPT = Path(__file__).parent / "backend" / "overlay_image.py"
AREA_PICKER_SCRIPT = Path(__file__).parent / "backend" / "area_picker.py"

WIDGET_ID = "image_overlay"
_PROCESS_KEY = f"_{WIDGET_ID}_process"

DEFAULT_AREA = {"x": 100, "y": 100, "width": 300, "height": 300}
DEFAULT_CLICK_THROUGH = True


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

    def set_running(running: bool):
        status_text.value = "Running" if running else "Stopped"
        start_button.disabled = running or not image_path_text.data
        stop_button.disabled = not running
        pick_button.disabled = running
        x_field.disabled = running
        y_field.disabled = running
        width_field.disabled = running
        height_field.disabled = running
        pick_area_button.disabled = running
        click_through_checkbox.disabled = running
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

    def on_line(data: dict):
        """Surface a backend startup error, if the process reported one.

        A clean `{"ready": true}` line needs no UI change here, since the
        Start button already flipped the running state before this fires.
        """
        error = data.get("error")
        if error:
            status_text.value = "Error"
            image_path_text.value = error
            page.session.store.set(_PROCESS_KEY, None)
            set_running(False)

    def on_exit(code: int):
        page.session.store.set(_PROCESS_KEY, None)
        set_running(False)

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
        widget_process = await start_process(page, *command, on_line=on_line, on_exit=on_exit)
        page.session.store.set(_PROCESS_KEY, widget_process)
        set_running(True)

    def on_stop(e: ft.Event[ft.FilledButton]):
        widget_process: WidgetProcess | None = page.session.store.get(_PROCESS_KEY)
        if widget_process is not None:
            stop_process(widget_process)
        page.session.store.set(_PROCESS_KEY, None)
        set_running(False)

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
                "the area below, with no window chrome or taskbar entry.",
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
    description="Pins an image on top of everything else on screen.",
    build_view=build_view,
    build_settings=build_settings,
    icon=ft.Icons.IMAGE_OUTLINED,
    selected_icon=ft.Icons.IMAGE,
)
