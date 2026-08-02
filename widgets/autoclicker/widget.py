"""Autoclicker: clicks repeatedly at the cursor.

Its UI is built with Flet, same as any widget: Flet can only render
controls from Python code running on its own event loop, so that part
stays Python no matter what. The actual clicking, though, runs entirely
outside Python, as a platform-native script this file starts, stops, and
reads status from over stdout (see multitool/widgets/process.py). This is
the first widget built against that any-language-backend pattern.

- Windows: backend/click_windows.ps1, a PowerShell script that calls
  user32.dll's mouse_event directly. No extra dependencies.
- macOS: backend/click_macos.sh, a shell script that shells out to
  cliclick (`brew install cliclick`), since AppleScript/System Events
  can't post synthetic clicks at an arbitrary screen position without it.

To try this widget locally, copy this folder into WIDGETS_DIR (the path
shown in Settings -> Widgets).
"""

import sys
from pathlib import Path

import flet as ft

from multitool.state import get_widget_setting, set_widget_setting
from multitool.ui.layout import build_layout, widget_route
from multitool.widgets.api import Widget
from multitool.widgets.process import WidgetProcess, start_process, stop_process

BACKEND_DIR = Path(__file__).parent / "backend"

WIDGET_ID = "autoclicker"
_PROCESS_KEY = f"_{WIDGET_ID}_process"

DEFAULT_INTERVAL_MS = 100


def _backend_command(interval_ms: int, button: str) -> list[str]:
    """The platform-specific command that runs the click loop."""
    if sys.platform == "win32":
        return [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(BACKEND_DIR / "click_windows.ps1"),
            "-IntervalMs",
            str(interval_ms),
            "-Button",
            button,
        ]
    return [
        "/bin/bash",
        str(BACKEND_DIR / "click_macos.sh"),
        str(interval_ms),
    ]


def build_view(page: ft.Page) -> ft.View:
    """The Autoclicker's own screen: interval, mouse button, start/stop."""
    default_interval = get_widget_setting(
        page, WIDGET_ID, "default_interval_ms", DEFAULT_INTERVAL_MS
    )

    status_text = ft.Text("Stopped", weight=ft.FontWeight.W_600)
    count_text = ft.Text("Clicks: 0", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
    interval_field = ft.TextField(label="Interval (ms)", value=str(default_interval), width=140)
    button_group = ft.RadioGroup(
        value="left",
        content=ft.Row(
            [
                ft.Radio(value="left", label="Left click"),
                ft.Radio(value="right", label="Right click"),
            ]
        ),
    )
    start_button = ft.FilledButton("Start")
    stop_button = ft.FilledButton("Stop", disabled=True)

    def set_running(running: bool):
        status_text.value = "Running" if running else "Stopped"
        start_button.disabled = running
        stop_button.disabled = not running
        interval_field.disabled = running
        page.update()

    def on_line(data: dict):
        error = data.get("error")
        if error:
            status_text.value = "Error"
            count_text.value = error
            page.update()
            return
        count = data.get("count")
        if count is not None:
            count_text.value = f"Clicks: {count}"
            page.update()

    def on_exit(code: int):
        page.session.store.set(_PROCESS_KEY, None)
        set_running(False)

    async def on_start(e: ft.Event[ft.FilledButton]):
        try:
            interval_ms = max(1, int(interval_field.value or DEFAULT_INTERVAL_MS))
        except ValueError:
            interval_ms = DEFAULT_INTERVAL_MS
        interval_field.value = str(interval_ms)

        command = _backend_command(interval_ms, button_group.value or "left")
        widget_process = await start_process(page, *command, on_line=on_line, on_exit=on_exit)
        page.session.store.set(_PROCESS_KEY, widget_process)
        set_running(True)

    def on_stop(e: ft.Event[ft.FilledButton]):
        widget_process: WidgetProcess | None = page.session.store.get(_PROCESS_KEY)
        if widget_process is not None:
            stop_process(widget_process)
        page.session.store.set(_PROCESS_KEY, None)
        set_running(False)

    start_button.on_click = on_start
    stop_button.on_click = on_stop

    content = ft.Column(
        [
            ft.Text("Autoclicker", size=24, weight=ft.FontWeight.BOLD),
            ft.Text(
                "Repeatedly clicks at the current cursor position. Its click "
                "loop runs as a separate platform script, not Python. Move "
                "the cursor to where you want it clicking before pressing Start.",
                size=12,
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
            ft.Row([interval_field, button_group]),
            ft.Row([start_button, stop_button]),
            status_text,
            count_text,
        ],
        spacing=12,
    )

    return ft.View(
        route=widget_route("autoclicker"),
        padding=0,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[build_layout(page, content)],
    )


def build_settings(page: ft.Page) -> ft.Control:
    """The Autoclicker's Settings section: just its default interval."""

    def on_blur(e: ft.Event[ft.TextField]):
        try:
            value = max(1, int(e.control.value or DEFAULT_INTERVAL_MS))
        except ValueError:
            value = DEFAULT_INTERVAL_MS
        e.control.value = str(value)
        e.control.update()
        set_widget_setting(page, WIDGET_ID, "default_interval_ms", value)

    default_interval = get_widget_setting(
        page, WIDGET_ID, "default_interval_ms", DEFAULT_INTERVAL_MS
    )

    return ft.Column(
        [
            ft.Text(
                "The interval field on the Autoclicker screen starts at this "
                "value each time it opens.",
                size=12,
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
            ft.TextField(
                label="Default interval (ms)",
                value=str(default_interval),
                width=200,
                on_blur=on_blur,
            ),
        ],
        spacing=8,
    )


WIDGET = Widget(
    id=WIDGET_ID,
    name="Autoclicker",
    description="Clicks repeatedly at the cursor. Backend runs outside Python.",
    build_view=build_view,
    build_settings=build_settings,
    icon=ft.Icons.MOUSE_OUTLINED,
    selected_icon=ft.Icons.MOUSE,
)
