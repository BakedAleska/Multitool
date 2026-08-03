"""Autoclicker: clicks repeatedly at the cursor.

Its UI is built with Flet, same as any widget: Flet can only render
controls from Python code running on its own event loop, so that part
stays Python no matter what. The actual clicking, though, runs entirely
outside Python, as a platform-native script this file starts, stops, and
reads status from over stdout (see multitool/widgets/process.py).

- Windows: backend/click_windows.ps1, a PowerShell script that calls
  user32.dll's mouse_event directly. No extra dependencies.
- macOS: backend/click_macos.sh, a shell script that shells out to
  cliclick (`brew install cliclick`), since AppleScript/System Events
  can't post synthetic clicks at an arbitrary screen position without it.

Two more backends run alongside the click loop, both cross-platform
Python scripts started the same "external process, JSON over stdout"
way:

- backend/keybind_listener.py, using pynput to listen system-wide for
  configured start/stop hotkeys, so clicking can be toggled without
  switching focus back to Multitool. The same key can be bound as both
  the start and the stop keybind for one Autoclicker instance: pressing
  it then acts like a NOT gate on the running state, on if it was off
  and off if it was on, rather than needing separate keys for each
  direction.
- backend/overlay.py, a small always-on-top tkinter window shown while
  clicking is active, so it's visible even when Multitool itself is in
  the background.

To try this widget locally, copy this folder into WIDGETS_DIR (the path
shown in Settings -> Widgets).
"""

import json
import re
import sys
from pathlib import Path

import flet as ft

from multitool.state import get_widget_setting, set_widget_setting
from multitool.ui.layout import build_layout, widget_route
from multitool.ui.toast import show_toast
from multitool.widgets.api import Widget
from multitool.widgets.process import WidgetProcess, start_process, stop_process

BACKEND_DIR = Path(__file__).parent / "backend"

WIDGET_ID = "autoclicker"
_CLICK_PROCESS_KEY = f"_{WIDGET_ID}_click_process"
_LISTENER_PROCESS_KEY = f"_{WIDGET_ID}_listener_process"
_LISTENER_CONFIG_KEY = f"_{WIDGET_ID}_listener_config"
_OVERLAY_PROCESS_KEY = f"_{WIDGET_ID}_overlay_process"

DEFAULT_CPS = 10
CPS_MIN = 1
CPS_MAX = 20
"""Honest bounds for clicks-per-second, not just a round number.

20 CPS is a 50ms interval, which stays comfortably above the ~15.6ms
tick Windows' default scheduler resolution allows, so the backend script
can actually hit the rate it's asked for (it also raises the timer
resolution to 1ms itself, but that's a best-effort request, not a
guarantee). Higher than this and the reported click count starts
drifting from the requested rate rather than reflecting a real limit
worth exposing in the UI.
"""

DEFAULT_BUTTON = "left"
RANDOMIZE_PERCENT = 15
"""Jitter applied per click when "Randomize timing" is on, as a percent
of the base interval in either direction."""

DEFAULT_SHOW_INDICATOR = True
DEFAULT_RANDOMIZE_TIMING = True

_FUNCTION_KEY_RE = re.compile(r"^F([1-9]|1[0-9]|2[0-4])$")

_SPECIAL_KEY_MAP = {
    "Escape": "esc",
    "Enter": "enter",
    "Space": "space",
    "Tab": "tab",
    "Backspace": "backspace",
    "Delete": "delete",
    "Insert": "insert",
    "Home": "home",
    "End": "end",
    "Page Up": "page_up",
    "Page Down": "page_down",
    "Arrow Up": "up",
    "Arrow Down": "down",
    "Arrow Left": "left",
    "Arrow Right": "right",
}


def _keyboard_event_to_hotkey(e: ft.KeyboardEvent) -> tuple[str, str] | None:
    """Convert a Flet key press into a (label, pynput hotkey string) pair.

    Returns None if the key alone isn't a usable hotkey, e.g. a modifier
    pressed on its own with nothing else, or "+" (see below).

    Letters and digits are lowercased into the token and their case
    restored separately via an explicit "<shift>" token, so the token
    itself stays canonical regardless of whether the key was typed with
    Shift held. Punctuation and symbol keys such as "/" or "~" have no
    such canonical unshifted form to fall back on, so they're passed
    through as-is instead: pynput's hotkey parser treats any single
    character literally (matched against the character the OS actually
    produced), which is exactly what `e.key` already reports, whether or
    not Shift changed it. "+" is the one character that can't be used,
    since it's the separator this module's own hotkey strings are joined
    with, not a limitation of pynput's format.
    """
    key = e.key
    if key in ("Shift", "Control", "Alt", "Meta"):
        return None

    if len(key) == 1 and key.isalnum():
        main_token = key.lower()
        main_label = key.upper()
    elif len(key) == 1 and key.isprintable() and not key.isspace():
        if key == "+":
            return None
        main_token = key
        main_label = key
    elif _FUNCTION_KEY_RE.match(key):
        main_token = key.lower()
        main_label = key
    elif key in _SPECIAL_KEY_MAP:
        main_token = _SPECIAL_KEY_MAP[key]
        main_label = key
    else:
        return None

    tokens = []
    labels = []
    if e.ctrl:
        tokens.append("<ctrl>")
        labels.append("Ctrl")
    if e.alt:
        tokens.append("<alt>")
        labels.append("Alt")
    if e.shift:
        tokens.append("<shift>")
        labels.append("Shift")
    if e.meta:
        tokens.append("<cmd>")
        labels.append("Win" if sys.platform == "win32" else "Cmd")

    tokens.append(main_token if len(main_token) == 1 else f"<{main_token}>")
    labels.append(main_label)

    return "+".join(labels), "+".join(tokens)


def _click_backend_command(cps: int, button: str, randomize: bool) -> list[str]:
    """The platform-specific command that runs the click loop."""
    interval_ms = round(1000 / cps)
    randomize_percent = RANDOMIZE_PERCENT if randomize else 0
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
            "-RandomizePercent",
            str(randomize_percent),
        ]
    return [
        "/bin/bash",
        str(BACKEND_DIR / "click_macos.sh"),
        str(interval_ms),
        button,
        str(randomize_percent),
    ]


def _keybind_listener_command(start_hotkeys: list[str], stop_hotkeys: list[str]) -> list[str]:
    """The command that starts `backend/keybind_listener.py`.

    Each hotkey list is passed as a JSON-encoded argument, matching what
    that script expects to parse from `sys.argv`.
    """
    return [
        sys.executable,
        str(BACKEND_DIR / "keybind_listener.py"),
        json.dumps(start_hotkeys),
        json.dumps(stop_hotkeys),
    ]


def _overlay_command() -> list[str]:
    """The command that starts the on-screen "running" indicator process."""
    return [sys.executable, str(BACKEND_DIR / "overlay.py")]


async def _start_on_app_launch(page: ft.Page) -> None:
    """Start clicking automatically at app launch, using saved defaults.

    Wired up as Widget.on_app_start, so it only runs if the user turned
    on this widget's "Start on launch" toggle under Settings -> Widgets.
    Mirrors build_view's start_clicking(), but runs before any view
    exists to read live field values from, so it reads the same saved
    defaults build_view itself initializes those fields from. build_view
    picks up the already-running process the next time it's opened (see
    its own already_running check) instead of showing a stale "Stopped".
    """
    if page.session.store.get(_CLICK_PROCESS_KEY) is not None:
        return
    default_cps = get_widget_setting(page, WIDGET_ID, "default_cps", DEFAULT_CPS)
    cps = max(CPS_MIN, min(CPS_MAX, int(default_cps)))
    button = get_widget_setting(page, WIDGET_ID, "default_button", DEFAULT_BUTTON)
    randomize_timing = get_widget_setting(
        page, WIDGET_ID, "randomize_timing", DEFAULT_RANDOMIZE_TIMING
    )
    show_indicator = get_widget_setting(page, WIDGET_ID, "show_indicator", DEFAULT_SHOW_INDICATOR)

    def on_exit(code: int):
        page.session.store.set(_CLICK_PROCESS_KEY, None)

    command = _click_backend_command(cps, button, randomize_timing)
    widget_process = await start_process(page, *command, on_exit=on_exit)
    page.session.store.set(_CLICK_PROCESS_KEY, widget_process)

    if show_indicator:
        overlay_process = await start_process(page, *_overlay_command())
        page.session.store.set(_OVERLAY_PROCESS_KEY, overlay_process)


def build_view(page: ft.Page) -> ft.View:
    """The Autoclicker's own screen: CPS, button, keybinds, indicator."""
    default_cps = get_widget_setting(page, WIDGET_ID, "default_cps", DEFAULT_CPS)
    default_button = get_widget_setting(page, WIDGET_ID, "default_button", DEFAULT_BUTTON)
    show_indicator = get_widget_setting(page, WIDGET_ID, "show_indicator", DEFAULT_SHOW_INDICATOR)
    randomize_timing = get_widget_setting(
        page, WIDGET_ID, "randomize_timing", DEFAULT_RANDOMIZE_TIMING
    )
    start_keybinds: list[dict] = get_widget_setting(page, WIDGET_ID, "start_keybinds", [])
    stop_keybinds: list[dict] = get_widget_setting(page, WIDGET_ID, "stop_keybinds", [])

    already_running = page.session.store.get(_CLICK_PROCESS_KEY) is not None
    """Whether a click process is already running when this view builds.

    True when the "Start on launch" hook (_start_on_app_launch, below)
    already started one before the user ever opened this screen. Every
    control below starts from this instead of always assuming "Stopped",
    so the screen doesn't show a stale Start button for a loop that's
    actually already running.
    """

    status_text = ft.Text("Running" if already_running else "Stopped", weight=ft.FontWeight.W_600)
    count_text = ft.Text("Clicks: 0", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
    cps_field = ft.TextField(
        label="Clicks per second",
        value=str(default_cps),
        width=160,
        helper=f"{CPS_MIN}-{CPS_MAX}",
        disabled=already_running,
    )
    button_group = ft.RadioGroup(
        value=default_button,
        disabled=already_running,
        content=ft.Row(
            [
                ft.Radio(value="left", label="Left click"),
                ft.Radio(value="middle", label="Middle click"),
                ft.Radio(value="right", label="Right click"),
            ]
        ),
    )
    indicator_checkbox = ft.Checkbox(
        label="Show on-screen indicator while running", value=show_indicator
    )
    randomize_checkbox = ft.Checkbox(
        label=f"Randomize timing slightly (±{RANDOMIZE_PERCENT}%)", value=randomize_timing
    )
    start_button = ft.FilledButton("Start", disabled=already_running)
    stop_button = ft.FilledButton("Stop", disabled=not already_running)

    start_chips_row = ft.Row(wrap=True, spacing=6)
    stop_chips_row = ft.Row(wrap=True, spacing=6)
    add_start_button = ft.OutlinedButton("Add keybind", icon=ft.Icons.ADD)
    add_stop_button = ft.OutlinedButton("Add keybind", icon=ft.Icons.ADD)
    capture_hint = ft.Text(
        "", size=12, weight=ft.FontWeight.W_600, color=ft.Colors.PRIMARY, visible=False
    )

    def clamp_cps(raw: str) -> int:
        try:
            value = int(raw)
        except ValueError:
            value = DEFAULT_CPS
        return max(CPS_MIN, min(CPS_MAX, value))

    def set_running(running: bool):
        status_text.value = "Running" if running else "Stopped"
        start_button.disabled = running
        stop_button.disabled = not running
        cps_field.disabled = running
        button_group.disabled = running
        page.update()

    def on_click_line(data: dict):
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

    def on_click_exit(code: int):
        page.session.store.set(_CLICK_PROCESS_KEY, None)
        set_running(False)

    async def stop_overlay():
        """Stop the running indicator process, if one is active."""
        overlay_process: WidgetProcess | None = page.session.store.get(_OVERLAY_PROCESS_KEY)
        if overlay_process is not None:
            stop_process(overlay_process)
        page.session.store.set(_OVERLAY_PROCESS_KEY, None)

    async def start_clicking():
        """Start the click backend, and the overlay indicator if enabled.

        A no-op if a click process is already running, so this is safe to
        call from both the Start button and the keybind listener without
        double-starting.
        """
        if page.session.store.get(_CLICK_PROCESS_KEY) is not None:
            return
        cps = clamp_cps(cps_field.value)
        cps_field.value = str(cps)
        button = button_group.value or DEFAULT_BUTTON
        command = _click_backend_command(cps, button, randomize_checkbox.value)
        widget_process = await start_process(
            page, *command, on_line=on_click_line, on_exit=on_click_exit
        )
        page.session.store.set(_CLICK_PROCESS_KEY, widget_process)
        if indicator_checkbox.value:
            overlay_process = await start_process(page, *_overlay_command())
            page.session.store.set(_OVERLAY_PROCESS_KEY, overlay_process)
        set_running(True)

    async def stop_clicking():
        """Stop the click backend and its overlay indicator, if running."""
        widget_process: WidgetProcess | None = page.session.store.get(_CLICK_PROCESS_KEY)
        if widget_process is not None:
            stop_process(widget_process)
        page.session.store.set(_CLICK_PROCESS_KEY, None)
        await stop_overlay()
        set_running(False)

    async def on_start(e: ft.Event[ft.FilledButton]):
        await start_clicking()

    async def on_stop(e: ft.Event[ft.FilledButton]):
        await stop_clicking()

    start_button.on_click = on_start
    stop_button.on_click = on_stop

    def on_listener_line(data: dict):
        """Route a keybind listener event to the click start/stop path.

        The listener process only ever reports which action fired; it
        doesn't drive the click backend itself, so this dispatches to the
        same start_clicking()/stop_clicking() coroutines the Start/Stop
        buttons use.

        A "toggle" event means the pressed key is bound as both a start
        and a stop keybind for this action - the listener can't tell on
        its own which one that should mean, since it has no idea whether
        clicking is currently running, so it defers that decision here,
        where the real state (_CLICK_PROCESS_KEY) is available.
        """
        event = data.get("event")
        if event == "start":
            page.run_task(start_clicking)
        elif event == "stop":
            page.run_task(stop_clicking)
        elif event == "toggle":
            if page.session.store.get(_CLICK_PROCESS_KEY) is not None:
                page.run_task(stop_clicking)
            else:
                page.run_task(start_clicking)
        elif data.get("error"):
            show_toast(page, data["error"])

    def make_on_listener_exit(process_box: dict):
        """A listener may be replaced (keybinds changed) before its old
        process actually finishes exiting. Only clear the tracked process
        if it's still the one this particular exit belongs to, so a
        stale exit callback can't wipe out a newer listener's state.
        """

        def on_listener_exit(code: int):
            if page.session.store.get(_LISTENER_PROCESS_KEY) is process_box.get("process"):
                page.session.store.set(_LISTENER_PROCESS_KEY, None)
                page.session.store.set(_LISTENER_CONFIG_KEY, None)

        return on_listener_exit

    async def sync_listener():
        """(Re)start the global keybind listener if the bound keys changed.

        Runs on every view build and after every keybind add/remove, so
        the listener always matches what's currently configured. It's
        deliberately not tied to this view's own lifecycle beyond that:
        once started, it keeps listening even after navigating away, the
        same way the click process itself is allowed to keep running.
        """
        start_hotkeys = [kb["hotkey"] for kb in start_keybinds]
        stop_hotkeys = [kb["hotkey"] for kb in stop_keybinds]
        config = json.dumps([start_hotkeys, stop_hotkeys])

        existing_process: WidgetProcess | None = page.session.store.get(_LISTENER_PROCESS_KEY)
        existing_config = page.session.store.get(_LISTENER_CONFIG_KEY)
        if existing_config == config:
            return

        if existing_process is not None:
            stop_process(existing_process)
            page.session.store.set(_LISTENER_PROCESS_KEY, None)

        if not start_hotkeys and not stop_hotkeys:
            page.session.store.set(_LISTENER_CONFIG_KEY, None)
            return

        process_box: dict = {}
        command = _keybind_listener_command(start_hotkeys, stop_hotkeys)
        listener_process = await start_process(
            page, *command, on_line=on_listener_line, on_exit=make_on_listener_exit(process_box)
        )
        process_box["process"] = listener_process
        page.session.store.set(_LISTENER_PROCESS_KEY, listener_process)
        page.session.store.set(_LISTENER_CONFIG_KEY, config)

    def render_chips(mounted: bool = True):
        """Rebuild the start/stop keybind chip rows from current state.

        A keybind bound in both lists gets "(toggle)" appended to its
        chip label in each - see the module docstring's note on shared
        start/stop keybinds for what that means at runtime.

        `mounted=False` skips calling `.update()` on the rows, for use
        during initial view construction before the page has rendered
        them yet.
        """
        shared_hotkeys = {kb["hotkey"] for kb in start_keybinds} & {
            kb["hotkey"] for kb in stop_keybinds
        }

        def chip_for(keybind: dict, keybinds: list[dict], setting_key: str):
            def on_delete(e: ft.Event[ft.Chip]):
                keybinds.remove(keybind)
                set_widget_setting(page, WIDGET_ID, setting_key, keybinds)
                render_chips()
                page.run_task(sync_listener)

            label = keybind["label"]
            if keybind["hotkey"] in shared_hotkeys:
                label = f"{label} (toggle)"
            return ft.Chip(label=label, on_delete=on_delete)

        start_chips_row.controls = [
            chip_for(kb, start_keybinds, "start_keybinds") for kb in start_keybinds
        ]
        stop_chips_row.controls = [
            chip_for(kb, stop_keybinds, "stop_keybinds") for kb in stop_keybinds
        ]
        if mounted:
            start_chips_row.update()
            stop_chips_row.update()

    capture: dict = {"keybinds": None, "setting_key": None}
    """Which list a captured key should go into, or both None when no
    capture is armed. A plain dict instead of separate variables so
    on_page_keyboard_event (a closure defined once, below) can read
    whatever start_capture() last wrote to it.
    """

    def cancel_capture():
        """Disarm capture and restore both "Add keybind" buttons."""
        capture["keybinds"] = None
        capture["setting_key"] = None
        add_start_button.disabled = False
        add_stop_button.disabled = False
        add_start_button.text = "Add keybind"
        add_stop_button.text = "Add keybind"
        capture_hint.value = ""
        capture_hint.visible = False

    def on_page_keyboard_event(e: ft.KeyboardEvent):
        """The page's one and only keyboard handler, registered once below.

        start_capture() doesn't assign a fresh `page.on_keyboard_event`
        of its own for each capture - Flet doesn't reliably swap out a
        dynamically-reassigned page-level handler, so a second capture
        could end up silently ignored, or both the old and new handler
        firing together. Registering a single handler up front and
        gating its behavior on the `capture` dict sidesteps that
        entirely: nothing about the handler itself ever changes, only
        the state it reads.

        A no-op whenever no capture is armed (`capture["keybinds"] is
        None`), which is the normal case.
        """
        if capture["keybinds"] is None:
            return

        if e.key == "Escape":
            cancel_capture()
            page.update()
            return

        keybinds = capture["keybinds"]
        setting_key = capture["setting_key"]
        cancel_capture()

        captured = _keyboard_event_to_hotkey(e)
        if captured is None:
            show_toast(page, "That key can't be used as a keybind. Try a different one.")
            page.update()
            return

        label, hotkey = captured
        if any(kb["hotkey"] == hotkey for kb in keybinds):
            show_toast(page, f'"{label}" is already used for this action.')
            page.update()
            return

        keybinds.append({"label": label, "hotkey": hotkey})
        set_widget_setting(page, WIDGET_ID, setting_key, keybinds)
        render_chips()
        page.update()
        page.run_task(sync_listener)

    page.on_keyboard_event = on_page_keyboard_event

    def start_capture(keybinds: list[dict], setting_key: str, add_button: ft.OutlinedButton):
        """Arm on_page_keyboard_event to capture the next key press.

        Disables both "Add keybind" buttons, relabels the one that was
        pressed, and shows an explicit "Press a key…" hint next to them -
        a button label change alone is easy to miss, especially since
        both buttons briefly go from enabled to disabled at the same
        moment the pressed one's own label changes.

        The same start and stop keybind can be captured here without
        conflict - see the module docstring.
        """
        capture["keybinds"] = keybinds
        capture["setting_key"] = setting_key
        add_start_button.disabled = True
        add_stop_button.disabled = True
        add_button.text = "Press a key…"
        capture_hint.value = "Press any key… (Esc to cancel)"
        capture_hint.visible = True
        page.update()

    add_start_button.on_click = lambda e: start_capture(
        start_keybinds, "start_keybinds", add_start_button
    )
    add_stop_button.on_click = lambda e: start_capture(
        stop_keybinds, "stop_keybinds", add_stop_button
    )

    def on_indicator_change(e: ft.Event[ft.Checkbox]):
        set_widget_setting(page, WIDGET_ID, "show_indicator", e.control.value)

    def on_randomize_change(e: ft.Event[ft.Checkbox]):
        set_widget_setting(page, WIDGET_ID, "randomize_timing", e.control.value)

    indicator_checkbox.on_change = on_indicator_change
    randomize_checkbox.on_change = on_randomize_change

    render_chips(mounted=False)
    page.run_task(sync_listener)

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
            ft.Row([cps_field, button_group]),
            ft.Row([indicator_checkbox, randomize_checkbox]),
            ft.Row([start_button, stop_button]),
            status_text,
            count_text,
            ft.Divider(),
            capture_hint,
            ft.Text("Turn on with", weight=ft.FontWeight.W_600),
            ft.Text(
                "Any of these keys works globally, even while another window "
                "has focus.",
                size=12,
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
            ft.Row([start_chips_row, add_start_button], wrap=True, spacing=8),
            ft.Text("Turn off with", weight=ft.FontWeight.W_600),
            ft.Row([stop_chips_row, add_stop_button], wrap=True, spacing=8),
        ],
        spacing=12,
        scroll=ft.ScrollMode.AUTO,
    )

    return ft.View(
        route=widget_route("autoclicker"),
        padding=0,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[build_layout(page, content)],
    )


def build_settings(page: ft.Page) -> ft.Control:
    """The Autoclicker's Settings section: defaults for CPS and button."""

    def on_cps_blur(e: ft.Event[ft.TextField]):
        try:
            value = max(CPS_MIN, min(CPS_MAX, int(e.control.value or DEFAULT_CPS)))
        except ValueError:
            value = DEFAULT_CPS
        e.control.value = str(value)
        e.control.update()
        set_widget_setting(page, WIDGET_ID, "default_cps", value)

    def on_button_change(e: ft.Event[ft.RadioGroup]):
        set_widget_setting(page, WIDGET_ID, "default_button", e.control.value)

    default_cps = get_widget_setting(page, WIDGET_ID, "default_cps", DEFAULT_CPS)
    default_button = get_widget_setting(page, WIDGET_ID, "default_button", DEFAULT_BUTTON)

    return ft.Column(
        [
            ft.Text(
                "The Autoclicker screen starts at these values each time it "
                "opens.",
                size=12,
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
            ft.TextField(
                label=f"Default CPS ({CPS_MIN}-{CPS_MAX})",
                value=str(default_cps),
                width=200,
                on_blur=on_cps_blur,
            ),
            ft.RadioGroup(
                value=default_button,
                on_change=on_button_change,
                content=ft.Row(
                    [
                        ft.Radio(value="left", label="Left click"),
                        ft.Radio(value="middle", label="Middle click"),
                        ft.Radio(value="right", label="Right click"),
                    ]
                ),
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
    on_app_start=_start_on_app_launch,
    icon=ft.Icons.MOUSE_OUTLINED,
    selected_icon=ft.Icons.MOUSE,
)
