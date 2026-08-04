"""Autohotkey: store, browse, enable, and suspend AutoHotkey scripts.

Each macro is a plain `.ahk` file kept under `<DATA_DIR>/ahk_macros/` - the
file itself is the store, there's no separate index kept alongside it.

v1.0 modeled "running a macro" as a one-shot Play/Stop action, closer to a
media file than to how AutoHotkey scripts actually behave. A real AHK
script isn't something that "plays": launching it starts AutoHotkey's own
interpreter as a resident process with its own system tray icon, and it
stays there - registering its hotkeys - until something exits it. The
script's own tray icon exposes two distinct actions, and this widget now
mirrors both of them instead of only the first:

- **Enable / Disable** - start or terminate the interpreter process for
  that macro, exactly like double-clicking the script or choosing Exit
  from its tray icon. This is still done via
  `toolblox/widgets/process.py::start_process`, the same "external
  process" pattern Autoclicker uses for its own backend.
- **Suspend / Resume hotkeys** - toggle the script's hotkeys on and off
  *without* exiting it, exactly like choosing "Suspend Hotkeys" from its
  tray icon. This matters most for this widget's main use case: a macro
  that remaps keybinds usually needs to be flipped on and off often,
  and re-launching AutoHotkey each time is slower and throws away
  anything the script is tracking in memory. Suspend is triggered by
  posting the tray menu's own WM_COMMAND message (id 65404) to the
  script's hidden main window - `ahk_class AutoHotkey`, titled with the
  script's own full path, the same lookup AutoHotkey's `#SingleInstance`
  directive relies on internally - rather than through any separate
  documented API, since AutoHotkey doesn't expose one. Because of that,
  this widget's own suspended/not-suspended tracking is best-effort: it
  reflects the last toggle *this widget* sent, and can drift if a
  script's own hotkey (see `_MACRO_TEMPLATE`) or its tray icon is used
  to suspend it instead.

A macro marked "Start with Toolblox" is auto-enabled by
`_start_on_app_launch`, wired up as `Widget.on_app_start`, the same
mechanism Autoclicker uses for its own "Start on launch" toggle - this
mirrors adding a keybind-remap script to Windows startup so it's always
resident, rather than something pressed by hand every session.

AutoHotkey only exists on Windows, so Enable/Disable and Suspend/Resume
are Windows-only features; storing, searching, importing, and deleting
macros are plain file operations and work on any platform.
"""

import asyncio
import ctypes
import json
import os
import re
import shutil
import sys
from ctypes import wintypes
from pathlib import Path
from typing import Optional

import flet as ft

from toolblox.config import DATA_DIR
from toolblox.state import get_widget_setting, set_widget_setting
from toolblox.ui.layout import build_layout, widget_route
from toolblox.ui.style import (
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
    SPACE_XS,
    SWITCH_SCALE,
    card_border,
    radius_card,
    scroll_margin,
    text_caption,
    text_label,
    text_title,
)
from toolblox.ui.toast import show_confirm_toast, show_toast
from toolblox.widgets.api import Widget
from toolblox.widgets.process import WidgetProcess, start_process, stop_process

WIDGET_ID = "ahk"
MACROS_DIR = DATA_DIR / "ahk_macros"

_RUNNING_KEY = f"_{WIDGET_ID}_running"
_SUSPENDED_KEY = f"_{WIDGET_ID}_suspended"

_WM_COMMAND = 0x0111
_ID_FILE_SUSPEND = 65404
"""AutoHotkey's own tray-menu command id for "Suspend Hotkeys". IDs
65300-65399 are the standard tray menu range and 65400-65534 are the
main menu range; 65404 is Suspend in both AutoHotkey v1 and v2. There is
no documented alternative to posting this id - AutoHotkey has no public
API for toggling suspend from another process."""

_PICK_EDITOR_SCRIPT = Path(__file__).parent / "backend" / "pick_editor.py"

_AHK_CANDIDATES = [
    r"C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe",
    r"C:\Program Files\AutoHotkey\v2\AutoHotkey32.exe",
    r"C:\Program Files\AutoHotkey\AutoHotkeyU64.exe",
    r"C:\Program Files\AutoHotkey\AutoHotkeyU32.exe",
    r"C:\Program Files\AutoHotkey\AutoHotkey.exe",
    r"C:\Program Files (x86)\AutoHotkey\AutoHotkey.exe",
]

_NAME_SANITIZE_RE = re.compile(r'[<>:"/\\|?*]')

_MACRO_TEMPLATE = (
    "; New macro created in Toolblox.\n"
    "; Toolblox can Enable/Disable this script (start/stop it entirely)\n"
    "; and Suspend/Resume it (turn its hotkeys on and off without exiting).\n"
    "; A script can also toggle its own suspend state from a hotkey, the\n"
    "; usual way to flip a keybind remap on and off without leaving\n"
    "; Toolblox - for example:\n"
    "; F12::Suspend\n"
)


def _sanitize_name(name: str) -> str:
    """Turn a user-entered macro name into a safe filename stem."""
    cleaned = _NAME_SANITIZE_RE.sub("", name).strip()
    return cleaned or "macro"


def _unique_path(name: str) -> Path:
    """A `.ahk` path under MACROS_DIR for name, deduped if it already exists."""
    stem = _sanitize_name(name)
    candidate = MACROS_DIR / f"{stem}.ahk"
    suffix = 2
    while candidate.exists():
        candidate = MACROS_DIR / f"{stem} ({suffix}).ahk"
        suffix += 1
    return candidate


def _list_macros() -> list[Path]:
    """Every `.ahk` file in MACROS_DIR, sorted by name."""
    if not MACROS_DIR.is_dir():
        return []
    return sorted(MACROS_DIR.glob("*.ahk"), key=lambda p: p.stem.lower())


def _find_autohotkey() -> Optional[str]:
    """Locate an AutoHotkey interpreter, or None if none is found.

    Checks the PATH first, then a list of common install locations. A
    user can always override this from Settings -> Widgets -> Autohotkey
    if their install lives somewhere else.
    """
    for name in ("AutoHotkeyU64", "AutoHotkey64", "AutoHotkey"):
        found = shutil.which(name)
        if found:
            return found
    for candidate in _AHK_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    return None


def _post_suspend_toggle(script_path: str) -> bool:
    """Toggle Suspend Hotkeys on a running script, the same as its own
    tray icon's "Suspend Hotkeys" menu item, without exiting it.

    Finds the script's hidden main window - class "AutoHotkey", titled
    with the script's own full path - and posts it the tray menu's own
    WM_COMMAND message. Returns False if no such window was found, which
    usually means the macro isn't currently enabled.

    Windows only. FindWindowW's return type is explicitly declared as a
    HWND (pointer-sized): ctypes' default return type is a 32-bit int,
    which would silently truncate a 64-bit window handle.
    """
    user32 = ctypes.windll.user32
    user32.FindWindowW.restype = wintypes.HWND
    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]

    hwnd = user32.FindWindowW("AutoHotkey", script_path)
    if not hwnd:
        return False
    user32.PostMessageW(hwnd, _WM_COMMAND, _ID_FILE_SUSPEND, 0)
    return True


def _find_vscode_path() -> Optional[str]:
    """The path to a VS Code executable/launcher script, or None if it
    isn't installed. Checks the PATH first, then a common install
    location per platform.
    """
    which = shutil.which("code")
    if which:
        return which
    if sys.platform == "win32":
        candidates = [
            Path(os.environ.get("LOCALAPPDATA", ""))
            / "Programs"
            / "Microsoft VS Code"
            / "Code.exe",
            Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft VS Code" / "Code.exe",
        ]
    elif sys.platform == "darwin":
        candidates = [Path("/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code")]
    else:
        candidates = []
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


def _find_notepad_path() -> Optional[str]:
    """The path to Notepad, or None outside Windows (there's no direct
    equivalent to offer as a quick pick on macOS/Linux)."""
    if sys.platform != "win32":
        return None
    return shutil.which("notepad") or r"C:\Windows\notepad.exe"


def _launch_editor_command(executable: str, target: Path) -> list[str]:
    """The command to open target with a chosen editor executable.

    A `.cmd`/`.bat` launcher (VS Code's own `code.cmd` on Windows, found
    via `_find_vscode_path`) can't be run directly - Windows' CreateProcess
    fails with WinError 193 without going through cmd.exe - so that case
    is wrapped in "cmd /c".
    """
    if sys.platform == "win32" and executable.lower().endswith((".cmd", ".bat")):
        return ["cmd", "/c", executable, str(target)]
    return [executable, str(target)]


async def _open_in_editor(page: ft.Page, path: Path) -> None:
    """Open a macro file in the user's chosen external editor.

    Never opens an editor embedded in this widget - AutoHotkey scripts
    are plain text, and any real text editor already does that job well.
    Settings -> Widgets -> Autohotkey lets a user pick any app on their
    system, the same way Windows' own "Open with" does. Left on
    Automatic (the default, an empty "editor_path" setting), this opens
    VS Code if it's installed, falling back to Notepad/TextEdit/whatever
    the OS treats a text file's default app as.
    """
    editor_path = get_widget_setting(page, WIDGET_ID, "editor_path", "")
    if editor_path:
        if Path(editor_path).is_file():
            await asyncio.create_subprocess_exec(*_launch_editor_command(editor_path, path))
            return
        show_toast(
            page,
            f'The chosen editor wasn\'t found at "{editor_path}". Opening automatically '
            "instead. Is it still installed at that path?",
        )

    vscode_path = _find_vscode_path()
    if vscode_path:
        await asyncio.create_subprocess_exec(*_launch_editor_command(vscode_path, path))
        return

    if sys.platform == "win32":
        await asyncio.create_subprocess_exec("notepad.exe", str(path))
    elif sys.platform == "darwin":
        await asyncio.create_subprocess_exec("open", "-e", str(path))
    else:
        await asyncio.create_subprocess_exec("xdg-open", str(path))


async def _open_macros_folder(page: ft.Page) -> None:
    """Reveal MACROS_DIR in the OS file browser, creating it if needed."""
    MACROS_DIR.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(MACROS_DIR)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        await asyncio.create_subprocess_exec("open", str(MACROS_DIR))
    else:
        await asyncio.create_subprocess_exec("xdg-open", str(MACROS_DIR))


async def _start_on_app_launch(page: ft.Page) -> None:
    """Auto-enable every macro marked "Start with Toolblox".

    Wired up as Widget.on_app_start, so it only runs if the user turned
    on this widget's "Start on launch" toggle under Settings -> Widgets,
    mirroring how a keybind-remap script is normally added to Windows
    startup so it's always resident rather than something started by
    hand each session. build_view's own already-running check picks up
    whatever this starts the next time the Autohotkey screen is opened.
    """
    if sys.platform != "win32":
        return
    autostart: list[str] = get_widget_setting(page, WIDGET_ID, "autostart_macros", [])
    if not autostart:
        return
    ahk_path = get_widget_setting(page, WIDGET_ID, "ahk_path", "") or _find_autohotkey()
    if not ahk_path or not Path(ahk_path).is_file():
        return

    running: dict[str, WidgetProcess] = page.session.store.get(_RUNNING_KEY) or {}
    for name in autostart:
        macro_path = MACROS_DIR / name
        if not macro_path.is_file() or name in running:
            continue

        def on_exit(code: int, name=name):
            current = page.session.store.get(_RUNNING_KEY) or {}
            current.pop(name, None)
            page.session.store.set(_RUNNING_KEY, current)

        widget_process = await start_process(page, ahk_path, str(macro_path), on_exit=on_exit)
        running[name] = widget_process
    page.session.store.set(_RUNNING_KEY, running)


def build_view(page: ft.Page) -> ft.View:
    """The Autohotkey screen: a searchable list of stored macros, each
    with Enable/Disable, Suspend/Resume, Edit, and Delete, plus
    create/import above it.
    """
    can_run = sys.platform == "win32"

    new_name_field = ft.TextField(label="New macro name", expand=True, dense=True)
    create_button = ft.FilledButton("Create", icon=ft.Icons.ADD)
    import_button = ft.OutlinedButton("Import .ahk files", icon=ft.Icons.FILE_UPLOAD_OUTLINED)
    open_folder_button = ft.OutlinedButton("Open macros folder", icon=ft.Icons.FOLDER_OPEN)
    search_field = ft.TextField(label="Search macros", prefix_icon=ft.Icons.SEARCH, dense=True)
    list_column = ft.Column(spacing=SPACE_SM)
    file_picker = ft.FilePicker()

    def get_running() -> dict[str, WidgetProcess]:
        return page.session.store.get(_RUNNING_KEY) or {}

    def set_running(running: dict[str, WidgetProcess]) -> None:
        page.session.store.set(_RUNNING_KEY, running)

    def get_suspended() -> set[str]:
        return page.session.store.get(_SUSPENDED_KEY) or set()

    def set_suspended(suspended: set[str]) -> None:
        page.session.store.set(_SUSPENDED_KEY, suspended)

    def get_autostart() -> list[str]:
        return get_widget_setting(page, WIDGET_ID, "autostart_macros", [])

    def matches(path: Path) -> bool:
        query = (search_field.value or "").strip().lower()
        return query in path.stem.lower()

    def macro_row(path: Path, running: dict[str, WidgetProcess], suspended: set[str]) -> ft.Control:
        is_enabled = path.name in running
        is_suspended = path.name in suspended and is_enabled
        is_autostart = path.name in get_autostart()

        async def on_toggle_enable(e: ft.Event[ft.IconButton]):
            if is_enabled:
                await disable_macro(path)
            else:
                await enable_macro(path)

        async def on_toggle_suspend(e: ft.Event[ft.IconButton]):
            posted = await asyncio.to_thread(_post_suspend_toggle, str(path))
            if not posted:
                show_toast(
                    page,
                    f'Couldn\'t reach "{path.stem}". Is it still enabled?',
                )
                return
            current = get_suspended()
            if path.name in current:
                current.discard(path.name)
            else:
                current.add(path.name)
            set_suspended(current)
            render_list()

        async def on_edit(e: ft.Event[ft.IconButton]):
            await _open_in_editor(page, path)

        def on_delete_confirmed():
            delete_macro(path)

        def on_delete(e: ft.Event[ft.IconButton]):
            show_confirm_toast(
                page,
                f'Delete "{path.stem}"? This can\'t be undone.',
                on_delete_confirmed,
                confirm_label="Delete",
            )

        def on_autostart_change(e: ft.Event[ft.Switch]):
            autostart = get_autostart()
            if e.control.value and path.name not in autostart:
                autostart = [*autostart, path.name]
            elif not e.control.value and path.name in autostart:
                autostart = [n for n in autostart if n != path.name]
            set_widget_setting(page, WIDGET_ID, "autostart_macros", autostart)

        name_row = ft.Row(
            [
                text_label(path.stem, expand=True),
                ft.Container(
                    content=ft.Text("Suspended", size=10, color=ft.Colors.ON_ERROR_CONTAINER),
                    bgcolor=ft.Colors.ERROR_CONTAINER,
                    padding=ft.Padding.symmetric(horizontal=SPACE_SM, vertical=SPACE_XS / 2),
                    border_radius=6,
                    visible=is_suspended,
                ),
            ],
            spacing=SPACE_SM,
        )

        actions_row = ft.Row(
            [
                ft.Row(
                    [
                        text_caption("Start with Toolblox"),
                        ft.Switch(
                            value=is_autostart,
                            scale=SWITCH_SCALE,
                            disabled=not can_run,
                            on_change=on_autostart_change,
                        ),
                    ],
                    spacing=SPACE_XS,
                ),
                ft.Row(
                    [
                        ft.IconButton(
                            icon=ft.Icons.TOGGLE_ON if is_enabled else ft.Icons.TOGGLE_OFF_OUTLINED,
                            tooltip=(
                                ("Disable" if is_enabled else "Enable")
                                if can_run
                                else "AutoHotkey requires Windows"
                            ),
                            disabled=not can_run,
                            on_click=on_toggle_enable,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.PAUSE_CIRCLE_OUTLINED
                            if not is_suspended
                            else ft.Icons.PLAY_CIRCLE_OUTLINE,
                            tooltip="Resume hotkeys" if is_suspended else "Suspend hotkeys",
                            disabled=not can_run or not is_enabled,
                            on_click=on_toggle_suspend,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.EDIT_OUTLINED, tooltip="Edit", on_click=on_edit
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE, tooltip="Delete", on_click=on_delete
                        ),
                    ],
                    spacing=0,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            wrap=True,
        )

        return ft.Container(
            content=ft.Column([name_row, actions_row], spacing=SPACE_XS),
            padding=ft.Padding.symmetric(horizontal=SPACE_MD, vertical=SPACE_SM),
            border=card_border(),
            border_radius=radius_card(page),
        )

    def render_list(mounted: bool = True):
        running = get_running()
        suspended = get_suspended()
        macros = [p for p in _list_macros() if matches(p)]
        if not macros:
            list_column.controls = [
                text_caption(
                    "No macros stored yet."
                    if not (search_field.value or "").strip()
                    else "No macros match your search."
                )
            ]
        else:
            list_column.controls = [macro_row(p, running, suspended) for p in macros]
        if mounted:
            list_column.update()

    async def enable_macro(path: Path):
        ahk_path = get_widget_setting(page, WIDGET_ID, "ahk_path", "") or _find_autohotkey()
        if not ahk_path or not Path(ahk_path).is_file():
            show_toast(
                page,
                "AutoHotkey wasn't found. Is it installed, and set correctly under "
                "Settings -> Widgets -> Autohotkey?",
            )
            return

        def on_exit(code: int):
            running = get_running()
            running.pop(path.name, None)
            set_running(running)
            suspended = get_suspended()
            suspended.discard(path.name)
            set_suspended(suspended)
            render_list()

        widget_process = await start_process(page, ahk_path, str(path), on_exit=on_exit)
        running = get_running()
        running[path.name] = widget_process
        set_running(running)
        render_list()

    async def disable_macro(path: Path):
        running = get_running()
        widget_process = running.pop(path.name, None)
        if widget_process is not None:
            stop_process(widget_process)
        set_running(running)
        suspended = get_suspended()
        suspended.discard(path.name)
        set_suspended(suspended)
        render_list()

    def delete_macro(path: Path):
        running = get_running()
        widget_process = running.pop(path.name, None)
        if widget_process is not None:
            stop_process(widget_process)
        set_running(running)
        suspended = get_suspended()
        suspended.discard(path.name)
        set_suspended(suspended)
        autostart = [n for n in get_autostart() if n != path.name]
        set_widget_setting(page, WIDGET_ID, "autostart_macros", autostart)
        try:
            path.unlink()
        except OSError as e:
            show_toast(page, f"Couldn't delete \"{path.stem}\". {e}")
            return
        render_list()

    async def on_create(e: ft.Event[ft.FilledButton]):
        name = (new_name_field.value or "").strip()
        if not name:
            show_toast(page, "Give the macro a name first.")
            return
        MACROS_DIR.mkdir(parents=True, exist_ok=True)
        target = _unique_path(name)
        target.write_text(_MACRO_TEMPLATE, encoding="utf-8")
        new_name_field.value = ""
        new_name_field.update()
        render_list()
        await _open_in_editor(page, target)

    async def on_import(e: ft.Event[ft.OutlinedButton]):
        files = await file_picker.pick_files(allow_multiple=True, allowed_extensions=["ahk"])
        if not files:
            return
        MACROS_DIR.mkdir(parents=True, exist_ok=True)
        for picked in files:
            target = _unique_path(Path(picked.name).stem)
            shutil.copy(picked.path, target)
        render_list()

    async def on_open_folder(e: ft.Event[ft.OutlinedButton]):
        await _open_macros_folder(page)

    create_button.on_click = on_create
    import_button.on_click = on_import
    open_folder_button.on_click = on_open_folder
    search_field.on_change = lambda e: render_list()

    render_list(mounted=False)

    banners: list[ft.Control] = []
    if not can_run:
        banners.append(
            text_caption(
                "Enabling, disabling, and suspending a macro requires AutoHotkey, "
                "which only exists on Windows. You can still store, browse, and "
                "edit macros here."
            )
        )

    content = ft.Column(
        [
            text_title("Autohotkey"),
            text_caption(
                "Enable a macro to start it, the same as opening it in "
                "AutoHotkey - it keeps running in the background afterward. "
                "Suspend turns its hotkeys off without exiting it. Edit always "
                "opens an external editor - Notepad by default, VS Code if "
                "it's installed - rather than editing here."
            ),
            *banners,
            ft.Row([new_name_field, create_button], spacing=SPACE_MD),
            ft.Row([import_button, open_folder_button], spacing=SPACE_MD),
            ft.Divider(),
            search_field,
            list_column,
        ],
        spacing=SPACE_LG,
        scroll=ft.ScrollMode.AUTO,
        margin=scroll_margin(),
    )

    return ft.View(
        route=widget_route(WIDGET_ID),
        padding=0,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[build_layout(page, content)],
        services=[file_picker],
    )


async def _pick_editor_path() -> Optional[str]:
    """Run backend/pick_editor.py and return the app path it chose, or
    None if the dialog was cancelled.

    build_settings() only returns a Control embedded inside the Settings
    tabs, not a View of its own, so it has no `services=[...]` slot to
    attach a `ft.FilePicker` to the way build_view() does for this
    widget's own screen - and `page.services`/`page.overlay` both proxy
    to the page's current root view, which `toolblox/app.py`'s
    route_change() clears before rebuilding, so touching either while a
    view is still under construction raises "views list is empty."
    Running the same tkinter-based subprocess pattern
    widgets/image_overlay/backend/area_picker.py uses for its own
    fullscreen picker sidesteps all of that.
    """
    proc = await asyncio.create_subprocess_exec(
        sys.executable, str(_PICK_EDITOR_SCRIPT), stdout=asyncio.subprocess.PIPE
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


def build_settings(page: ft.Page) -> ft.Control:
    """The Autohotkey widget's Settings section: which app Edit opens a macro in,
    and the AutoHotkey executable to run macros with.
    """
    editor_path = get_widget_setting(page, WIDGET_ID, "editor_path", "")
    ahk_path = get_widget_setting(page, WIDGET_ID, "ahk_path", "") or _find_autohotkey() or ""

    def editor_label(path: str) -> str:
        if path:
            return Path(path).stem
        vscode_path = _find_vscode_path()
        return "VS Code (detected)" if vscode_path else "Notepad"

    current_editor_text = ft.Text(editor_label(editor_path), size=13, weight=ft.FontWeight.W_600)
    reset_button = ft.TextButton("Use automatic", visible=bool(editor_path))

    def apply_editor_path(new_path: str):
        set_widget_setting(page, WIDGET_ID, "editor_path", new_path)
        current_editor_text.value = editor_label(new_path)
        reset_button.visible = bool(new_path)
        current_editor_text.update()
        reset_button.update()

    async def on_browse(e: ft.Event[ft.OutlinedButton]):
        picked = await _pick_editor_path()
        if not picked:
            return
        apply_editor_path(picked)

    def on_reset(e: ft.Event[ft.TextButton]):
        apply_editor_path("")

    reset_button.on_click = on_reset

    quick_picks: list[ft.Control] = []
    notepad_path = _find_notepad_path()
    if notepad_path:
        quick_picks.append(
            ft.OutlinedButton(
                "Notepad",
                icon=ft.Icons.NOTES,
                on_click=lambda e: apply_editor_path(notepad_path),
            )
        )
    vscode_path = _find_vscode_path()
    if vscode_path:
        quick_picks.append(
            ft.OutlinedButton(
                "VS Code",
                icon=ft.Icons.CODE,
                on_click=lambda e: apply_editor_path(vscode_path),
            )
        )

    path_field = ft.TextField(label="AutoHotkey executable", value=ahk_path, expand=True)
    detect_button = ft.OutlinedButton("Auto-detect")

    def on_path_blur(e: ft.Event[ft.TextField]):
        set_widget_setting(page, WIDGET_ID, "ahk_path", path_field.value or "")

    def on_detect(e: ft.Event[ft.OutlinedButton]):
        found = _find_autohotkey()
        if not found:
            show_toast(page, "No AutoHotkey install found. Enter its path manually.")
            return
        path_field.value = found
        path_field.update()
        set_widget_setting(page, WIDGET_ID, "ahk_path", found)

    path_field.on_blur = on_path_blur
    detect_button.on_click = on_detect

    return ft.Column(
        [
            text_caption(
                "The app macros open in when you press Edit, the same as Windows' "
                'own "Open with" - never edited inline in this widget.'
            ),
            ft.Row(
                [
                    text_caption("Opens with:"),
                    current_editor_text,
                ],
                spacing=SPACE_SM,
            ),
            ft.Row(
                [
                    *quick_picks,
                    ft.OutlinedButton(
                        "Choose another app...", icon=ft.Icons.APPS, on_click=on_browse
                    ),
                    reset_button,
                ],
                wrap=True,
                spacing=SPACE_SM,
            ),
            ft.Divider(),
            text_caption(
                "AutoHotkey executable (Windows only). Auto-detected on the PATH "
                "or a common install location if left blank."
            ),
            ft.Row([path_field, detect_button], spacing=SPACE_MD),
        ],
        spacing=SPACE_SM,
    )


WIDGET = Widget(
    id=WIDGET_ID,
    name="Autohotkey",
    description="Enable, suspend, and edit AutoHotkey macros, mirroring their own tray icon.",
    build_view=build_view,
    build_settings=build_settings,
    on_app_start=_start_on_app_launch,
    icon=ft.Icons.INTEGRATION_INSTRUCTIONS_OUTLINED,
    selected_icon=ft.Icons.INTEGRATION_INSTRUCTIONS,
)
