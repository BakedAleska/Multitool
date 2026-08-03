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

By default, pressing Start doesn't show the image right away. It arms a
background poll (multitool/roblox/detect.py::is_roblox_running) that
starts the backend window only while Roblox is running, and stops it the
moment Roblox closes, so the overlay never lingers on the desktop after
the game it belongs to has closed. Settings can point that same poll at
a different app instead, or turn watching off entirely so the image
shows immediately on Start and stays up until Stop.
"""

import asyncio
import json
import subprocess
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
PICK_APP_SCRIPT = Path(__file__).parent / "backend" / "pick_app.py"

WIDGET_ID = "image_overlay"
_PROCESS_KEY = f"_{WIDGET_ID}_process"
_POLL_STATE_KEY = f"_{WIDGET_ID}_poll_state"

DEFAULT_AREA = {"x": 100, "y": 100, "width": 300, "height": 300}
DEFAULT_CLICK_THROUGH = True
DEFAULT_WATCH_ENABLED = True
POLL_INTERVAL_SECONDS = 3.0


def _is_app_running(exe_path: str) -> bool:
    """Return True if a process matching `exe_path`'s file name is running.

    Same OS process-list shelling as `multitool.roblox.detect.is_roblox_running`,
    generalized to an arbitrary executable so the overlay can watch for a
    user-chosen app instead of only Roblox. Blocking; callers on the Flet
    event loop should run it via `asyncio.to_thread`. Never raises; any
    failure to read the process list is treated as "not running".
    """
    exe_name = Path(exe_path).name
    if not exe_name:
        return False
    try:
        if sys.platform == "win32":
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {exe_name}", "/NH"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return exe_name.lower() in result.stdout.lower()
        if sys.platform == "darwin":
            result = subprocess.run(
                ["pgrep", "-x", Path(exe_name).stem],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        return False
    except (OSError, subprocess.TimeoutExpired):
        return False


async def _is_watch_target_running(watch_app_path: str) -> bool:
    """Whether the app the overlay is currently armed to watch for is running.

    An empty `watch_app_path` means the default target, Roblox.
    """
    if watch_app_path:
        return await asyncio.to_thread(_is_app_running, watch_app_path)
    return await asyncio.to_thread(is_roblox_running)


async def _pick_app_path() -> Optional[str]:
    """Run backend/pick_app.py and return the app path it chose, or None
    if the dialog was cancelled.

    Same native-dialog-in-a-subprocess pattern as
    widgets/ahk/widget.py::_pick_editor_path, for the same reason: tkinter
    needs its own mainloop, which would conflict with Flet's.
    """
    proc = await asyncio.create_subprocess_exec(
        sys.executable, str(PICK_APP_SCRIPT), stdout=asyncio.subprocess.PIPE
    )
    assert proc.stdout is not None
    line = await proc.stdout.readline()
    await proc.wait()
    if not line:
        return None
    try:
        data = json.loads(line)
    except ValueError:
        return None
    return data.get("path")


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
    """The Image Overlay's own screen: pick an image, place it, pin it.

    Click-through isn't a control here - it's Windows compositing
    behavior, not something worth re-deciding per session, so it lives
    only in Settings (build_settings) and is read fresh from there each
    time Start runs.
    """
    area = get_widget_setting(page, WIDGET_ID, "area", DEFAULT_AREA)

    image_path_text = ft.Text("No image selected.", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
    status_text = ft.Text("Stopped", weight=ft.FontWeight.W_600)
    pick_button = ft.OutlinedButton("Choose image (PNG or GIF)")
    x_field = ft.TextField(label="X", value=str(area["x"]), width=90)
    y_field = ft.TextField(label="Y", value=str(area["y"]), width=90)
    width_field = ft.TextField(label="Width", value=str(area["width"]), width=90)
    height_field = ft.TextField(label="Height", value=str(area["height"]), width=90)
    pick_area_button = ft.OutlinedButton("Pick area on screen...")
    pick_area_hint = ft.Text(
        "Opens a full-screen picker. Click and drag to draw the area, then "
        "press Enter to save it or Esc to leave the area unchanged.",
        size=12,
        color=ft.Colors.ON_SURFACE_VARIANT,
    )
    revert_area_button = ft.TextButton(
        "Revert",
        icon=ft.Icons.UNDO,
        visible=False,
        tooltip="Restore the area from before your last change.",
    )
    start_button = ft.FilledButton("On", disabled=True)
    stop_button = ft.FilledButton("Off", disabled=True)

    file_picker = ft.FilePicker()
    watch_label = {"text": "Roblox"}

    def set_state(armed: bool, active: bool):
        """Reflect the current arm/active state in the status text and
        control disabled-states.

        `armed` means Start has been pressed and the poll loop is
        watching for whichever app `watch_label` names; `active` means
        that app is currently running and the overlay window is actually
        showing. `active` implies `armed`.
        """
        if not armed:
            status_text.value = "Stopped"
        elif active:
            status_text.value = "Running"
        else:
            status_text.value = f"Waiting for {watch_label['text']}..."
        start_button.disabled = armed or not image_path_text.data
        stop_button.disabled = not armed
        pick_button.disabled = armed
        x_field.disabled = armed
        y_field.disabled = armed
        width_field.disabled = armed
        height_field.disabled = armed
        pick_area_button.disabled = armed
        revert_area_button.disabled = armed
        page.update()

    committed_area = dict(area)
    previous_area: Optional[dict] = None

    def _apply_area(new_area: dict):
        """Persist `new_area` as the committed area, remembering whatever
        was committed before it so Revert can restore it.

        A no-op change (new_area equal to what's already committed)
        doesn't overwrite the remembered previous value, so pressing
        Start or blurring an untouched field doesn't erase an available
        revert.
        """
        nonlocal committed_area, previous_area
        if new_area != committed_area:
            previous_area = dict(committed_area)
            revert_area_button.visible = True
        committed_area = dict(new_area)
        set_widget_setting(page, WIDGET_ID, "area", committed_area)

    def _set_area_fields(values: dict):
        x_field.value = str(values["x"])
        y_field.value = str(values["y"])
        width_field.value = str(values["width"])
        height_field.value = str(values["height"])

    def save_area() -> dict:
        """Read the area fields, persist them, and write the parsed
        values back into the fields so an out-of-range entry is
        visibly corrected.
        """
        current = _parse_area(x_field, y_field, width_field, height_field, committed_area)
        _set_area_fields(current)
        _apply_area(current)
        return current

    def on_revert_area(e: ft.Event[ft.TextButton]):
        """Restore the area committed just before the last change.

        Only one step of history is kept - this is a quick undo for an
        accidental pick or typo, not a full history stack.
        """
        nonlocal committed_area, previous_area
        if previous_area is None:
            return
        restored = dict(previous_area)
        _set_area_fields(restored)
        set_widget_setting(page, WIDGET_ID, "area", restored)
        committed_area = restored
        previous_area = None
        revert_area_button.visible = False
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

    async def on_pick_area(e: ft.Event[ft.OutlinedButton]):
        """Run the fullscreen area picker and apply the rectangle it
        returns to the area fields, saving it immediately.
        """
        pick_area_button.disabled = True
        page.update()
        picked = await _pick_area()
        pick_area_button.disabled = False
        if picked is not None:
            _set_area_fields(picked)
            _apply_area(picked)
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
        it because the watched app closed, or it crashed on its own.

        If the poll loop is still armed and watching, this just means the
        watched app isn't open right now - fall back to "Waiting for ...",
        the poll loop keeps running. Otherwise (watching turned off, or
        Stop/on_line already handled it) there's nothing to wait for, so
        this disarms the widget entirely.
        """
        page.session.store.set(_PROCESS_KEY, None)
        poll_state = page.session.store.get(_POLL_STATE_KEY)
        if poll_state is not None and poll_state["armed"] and poll_state["watch_enabled"]:
            set_state(armed=True, active=False)
        elif poll_state is not None and poll_state["armed"]:
            _disarm()
            set_state(armed=False, active=False)

    async def _poll_target(command: list[str], poll_state: dict, watch_app_path: str):
        """While armed, start the overlay backend when the watched app is
        running and stop it when it isn't, checking every
        POLL_INTERVAL_SECONDS.

        `poll_state["armed"]` is a plain dict rather than a variable so
        on_stop/on_line can flip it from outside this coroutine and have
        the next wake-up see it.
        """
        while poll_state["armed"]:
            target_open = await _is_watch_target_running(watch_app_path)
            if not poll_state["armed"]:
                break
            current_process: WidgetProcess | None = page.session.store.get(_PROCESS_KEY)
            if target_open and current_process is None:
                widget_process = await start_process(
                    page, *command, on_line=on_line, on_exit=on_exit
                )
                if not poll_state["armed"]:
                    stop_process(widget_process)
                    break
                page.session.store.set(_PROCESS_KEY, widget_process)
                set_state(armed=True, active=True)
            elif not target_open and current_process is not None:
                stop_process(current_process)
                page.session.store.set(_PROCESS_KEY, None)
                set_state(armed=True, active=False)
            await asyncio.sleep(POLL_INTERVAL_SECONDS)

    async def on_start(e: ft.Event[ft.FilledButton]):
        """Arm the overlay. If watching is turned off in Settings, the
        image shows immediately and stays up until Stop; otherwise it
        only shows while the watched app (Roblox by default, or a chosen
        app) is open.
        """
        image_path = image_path_text.data
        if not image_path:
            return
        current_area = save_area()
        click_through = get_widget_setting(
            page, WIDGET_ID, "click_through", DEFAULT_CLICK_THROUGH
        )
        watch_enabled = get_widget_setting(page, WIDGET_ID, "watch_enabled", DEFAULT_WATCH_ENABLED)
        watch_app_path = get_widget_setting(page, WIDGET_ID, "watch_app_path", "")
        watch_label["text"] = Path(watch_app_path).stem if watch_app_path else "Roblox"

        command = _backend_command(image_path, current_area, click_through)
        poll_state = {"armed": True, "watch_enabled": watch_enabled}
        page.session.store.set(_POLL_STATE_KEY, poll_state)

        if not watch_enabled:
            widget_process = await start_process(page, *command, on_line=on_line, on_exit=on_exit)
            if not poll_state["armed"]:
                stop_process(widget_process)
                return
            page.session.store.set(_PROCESS_KEY, widget_process)
            set_state(armed=True, active=True)
            return

        set_state(armed=True, active=False)
        page.run_task(_poll_target, command, poll_state, watch_app_path)

    def on_stop(e: ft.Event[ft.FilledButton]):
        _disarm()
        widget_process: WidgetProcess | None = page.session.store.get(_PROCESS_KEY)
        if widget_process is not None:
            stop_process(widget_process)
        page.session.store.set(_PROCESS_KEY, None)
        set_state(armed=False, active=False)

    pick_button.on_click = on_pick
    pick_area_button.on_click = on_pick_area
    revert_area_button.on_click = on_revert_area
    for field in (x_field, y_field, width_field, height_field):
        field.on_blur = on_area_field_blur
    start_button.on_click = on_start
    stop_button.on_click = on_stop

    content = ft.Column(
        [
            ft.Text("Image Overlay", size=24, weight=ft.FontWeight.BOLD),
            ft.Text(
                "Pins an image on top of everything else on screen, inside "
                "the area below, with no window chrome or taskbar entry. By "
                "default it shows only while Roblox is open, and hides once "
                "it closes; change what it watches for, or turn that off "
                "entirely, in Settings.",
                size=12,
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
            ft.Row([pick_button, image_path_text]),
            ft.Text("Area", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            ft.Row([x_field, y_field, width_field, height_field]),
            ft.Row([pick_area_button, revert_area_button], wrap=True, spacing=8),
            pick_area_hint,
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
    """The Image Overlay's Settings section: whether it watches for an app
    at all, which app that is, and click-through.

    The area (position and size) is already fully editable, and saved
    immediately, on the Image Overlay screen itself - duplicating it
    here would just be a second place for the same value to go stale in.
    Click-through and the watch target are the opposite case: neither is
    something to reconsider each time the screen opens, so they live only
    here instead of as controls on that screen.
    """
    watch_enabled = get_widget_setting(page, WIDGET_ID, "watch_enabled", DEFAULT_WATCH_ENABLED)
    watch_app_path = get_widget_setting(page, WIDGET_ID, "watch_app_path", "")

    def watch_label(app_path: str) -> str:
        return Path(app_path).stem if app_path else "Roblox"

    current_watch_text = ft.Text(watch_label(watch_app_path), size=13, weight=ft.FontWeight.W_600)
    watch_row = ft.Row(
        [
            ft.Text("Watching for:", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            current_watch_text,
        ],
        spacing=6,
        visible=watch_enabled,
    )
    browse_button = ft.OutlinedButton(
        "Choose a different app...", visible=watch_enabled
    )
    reset_button = ft.TextButton(
        "Use Roblox instead",
        icon=ft.Icons.UNDO,
        visible=watch_enabled and bool(watch_app_path),
    )

    async def on_browse(e: ft.Event[ft.OutlinedButton]):
        picked = await _pick_app_path()
        if not picked:
            return
        set_widget_setting(page, WIDGET_ID, "watch_app_path", picked)
        current_watch_text.value = watch_label(picked)
        reset_button.visible = True
        current_watch_text.update()
        reset_button.update()

    def on_reset(e: ft.Event[ft.TextButton]):
        set_widget_setting(page, WIDGET_ID, "watch_app_path", "")
        current_watch_text.value = watch_label("")
        reset_button.visible = False
        current_watch_text.update()
        reset_button.update()

    browse_button.on_click = on_browse
    reset_button.on_click = on_reset

    def on_watch_enabled_change(e: ft.Event[ft.Checkbox]):
        enabled = e.control.value
        set_widget_setting(page, WIDGET_ID, "watch_enabled", enabled)
        watch_row.visible = enabled
        browse_button.visible = enabled
        reset_button.visible = enabled and bool(watch_app_path)
        watch_row.update()
        browse_button.update()
        reset_button.update()

    def on_click_through_change(e: ft.Event[ft.Checkbox]):
        set_widget_setting(page, WIDGET_ID, "click_through", e.control.value)

    click_through = get_widget_setting(page, WIDGET_ID, "click_through", DEFAULT_CLICK_THROUGH)

    return ft.Column(
        [
            ft.Text(
                "By default, the overlay only shows while Roblox is open, "
                "and hides once it closes. Turn this off to have it show "
                "as soon as you press Start and stay up until you press "
                "Stop, regardless of what's open.",
                size=12,
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
            ft.Checkbox(
                label="Only show while an app is open",
                value=watch_enabled,
                on_change=on_watch_enabled_change,
            ),
            watch_row,
            ft.Row([browse_button, reset_button], wrap=True, spacing=8),
            ft.Divider(),
            ft.Text(
                "Whether clicks pass through the overlay to whatever's "
                "underneath it, instead of landing on the overlay itself. "
                "Windows only.",
                size=12,
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
            ft.Checkbox(
                label="Click-through",
                value=click_through,
                on_change=on_click_through_change,
            ),
        ],
        spacing=8,
    )


WIDGET = Widget(
    id=WIDGET_ID,
    name="Image Overlay",
    description=(
        "Pins an image on top of everything else on screen, by default while Roblox is open."
    ),
    build_view=build_view,
    build_settings=build_settings,
    icon=ft.Icons.IMAGE_OUTLINED,
    selected_icon=ft.Icons.IMAGE,
)
