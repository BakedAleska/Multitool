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

import sys
from pathlib import Path

import flet as ft

from multitool.state import get_widget_setting, set_widget_setting
from multitool.ui.layout import build_layout, widget_route
from multitool.widgets.api import Widget
from multitool.widgets.process import WidgetProcess, start_process, stop_process

BACKEND_SCRIPT = Path(__file__).parent / "backend" / "overlay_image.py"

WIDGET_ID = "image_overlay"
_PROCESS_KEY = f"_{WIDGET_ID}_process"

POSITIONS = [
    ("top-left", "Top left"),
    ("top-right", "Top right"),
    ("bottom-left", "Bottom left"),
    ("bottom-right", "Bottom right"),
    ("center", "Center"),
]
DEFAULT_POSITION = "top-right"
DEFAULT_MARGIN = 24
DEFAULT_OPACITY = 0.85
DEFAULT_CLICK_THROUGH = True


def _backend_command(
    image_path: str, position: str, margin: int, opacity: float, click_through: bool
) -> list[str]:
    """The command that starts `backend/overlay_image.py` with these options."""
    command = [
        sys.executable,
        str(BACKEND_SCRIPT),
        "--image",
        image_path,
        "--position",
        position,
        "--margin",
        str(margin),
        "--opacity",
        str(opacity),
    ]
    if click_through:
        command.append("--click-through")
    return command


def build_view(page: ft.Page) -> ft.View:
    """The Image Overlay's own screen: pick an image, place it, pin it."""
    default_position = get_widget_setting(page, WIDGET_ID, "default_position", DEFAULT_POSITION)
    default_margin = get_widget_setting(page, WIDGET_ID, "default_margin", DEFAULT_MARGIN)
    default_opacity = get_widget_setting(page, WIDGET_ID, "default_opacity", DEFAULT_OPACITY)
    default_click_through = get_widget_setting(
        page, WIDGET_ID, "default_click_through", DEFAULT_CLICK_THROUGH
    )

    image_path_text = ft.Text("No image selected.", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
    status_text = ft.Text("Stopped", weight=ft.FontWeight.W_600)
    pick_button = ft.OutlinedButton("Choose image (PNG or GIF)")
    position_dropdown = ft.Dropdown(
        label="Position",
        value=default_position,
        options=[ft.dropdown.Option(key=key, text=label) for key, label in POSITIONS],
        width=180,
    )
    margin_field = ft.TextField(label="Margin (px)", value=str(default_margin), width=120)
    opacity_slider = ft.Slider(
        min=0.1, max=1.0, divisions=18, value=default_opacity, label="{value}"
    )
    click_through_checkbox = ft.Checkbox(
        label="Click-through (Windows only)", value=default_click_through
    )
    start_button = ft.FilledButton("Start", disabled=True)
    stop_button = ft.FilledButton("Stop", disabled=True)

    file_picker = ft.FilePicker()
    page.services.append(file_picker)

    def set_running(running: bool):
        status_text.value = "Running" if running else "Stopped"
        start_button.disabled = running or not image_path_text.data
        stop_button.disabled = not running
        pick_button.disabled = running
        position_dropdown.disabled = running
        margin_field.disabled = running
        opacity_slider.disabled = running
        click_through_checkbox.disabled = running
        page.update()

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
        try:
            margin = max(0, int(margin_field.value or DEFAULT_MARGIN))
        except ValueError:
            margin = DEFAULT_MARGIN
        margin_field.value = str(margin)

        command = _backend_command(
            image_path,
            position_dropdown.value or DEFAULT_POSITION,
            margin,
            opacity_slider.value,
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
    start_button.on_click = on_start
    stop_button.on_click = on_stop

    content = ft.Column(
        [
            ft.Text("Image Overlay", size=24, weight=ft.FontWeight.BOLD),
            ft.Text(
                "Pins an image on top of everything else on screen, at its "
                "native size, with no window chrome or taskbar entry.",
                size=12,
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
            ft.Row([pick_button, image_path_text]),
            ft.Row([position_dropdown, margin_field]),
            ft.Text("Opacity", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            opacity_slider,
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
    )


def build_settings(page: ft.Page) -> ft.Control:
    """The Image Overlay's Settings section: defaults for a fresh screen."""

    def on_position_change(e: ft.Event[ft.Dropdown]):
        set_widget_setting(page, WIDGET_ID, "default_position", e.control.value)

    def on_margin_blur(e: ft.Event[ft.TextField]):
        try:
            value = max(0, int(e.control.value or DEFAULT_MARGIN))
        except ValueError:
            value = DEFAULT_MARGIN
        e.control.value = str(value)
        e.control.update()
        set_widget_setting(page, WIDGET_ID, "default_margin", value)

    def on_opacity_change(e: ft.Event[ft.Slider]):
        set_widget_setting(page, WIDGET_ID, "default_opacity", e.control.value)

    def on_click_through_change(e: ft.Event[ft.Checkbox]):
        set_widget_setting(page, WIDGET_ID, "default_click_through", e.control.value)

    default_position = get_widget_setting(page, WIDGET_ID, "default_position", DEFAULT_POSITION)
    default_margin = get_widget_setting(page, WIDGET_ID, "default_margin", DEFAULT_MARGIN)
    default_opacity = get_widget_setting(page, WIDGET_ID, "default_opacity", DEFAULT_OPACITY)
    default_click_through = get_widget_setting(
        page, WIDGET_ID, "default_click_through", DEFAULT_CLICK_THROUGH
    )

    return ft.Column(
        [
            ft.Text(
                "These are the values the Image Overlay screen starts with "
                "each time it opens.",
                size=12,
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
            ft.Dropdown(
                label="Default position",
                value=default_position,
                options=[ft.dropdown.Option(key=key, text=label) for key, label in POSITIONS],
                width=180,
                on_select=on_position_change,
            ),
            ft.TextField(
                label="Default margin (px)",
                value=str(default_margin),
                width=200,
                on_blur=on_margin_blur,
            ),
            ft.Text("Default opacity", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            ft.Slider(
                min=0.1,
                max=1.0,
                divisions=18,
                value=default_opacity,
                label="{value}",
                on_change=on_opacity_change,
            ),
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
