# Autohotkey

Store, browse, enable, and suspend [AutoHotkey](https://www.autohotkey.com/)
macros. `widget.py` builds the UI with Flet, but every macro is just a plain
`.ahk` file kept under `<DATA_DIR>/ahk_macros/` - that folder is the store,
there's no separate index alongside it.

## Enable vs. Suspend (target version 1.1.0)

A real AutoHotkey script isn't something that "plays" - launching it starts
AutoHotkey's own interpreter as a resident process with its own system tray
icon, and it stays there, registering its hotkeys, until something exits it.
This widget mirrors the two actions its tray icon actually exposes, instead
of the one-shot Play/Stop the first version of this widget had:

- **Enable / Disable** - start or terminate the interpreter process for
  that macro (`multitool/widgets/process.py`, the same "external process"
  pattern Autoclicker uses for its own backend). Equivalent to launching
  the script, or choosing Exit from its tray icon.
- **Suspend / Resume hotkeys** - toggle the script's hotkeys on and off
  *without* exiting it, equivalent to its tray icon's own "Suspend
  Hotkeys" item. This is the important one for this widget's main use
  case - a macro that remaps keybinds usually needs to be flipped on and
  off often, and relaunching AutoHotkey each time is slower and throws
  away anything the script tracks in memory.

Suspend is triggered by posting AutoHotkey's own tray-menu WM_COMMAND
message (id `65404`) to the script's hidden main window - class
`AutoHotkey`, titled with the script's own full path, the same lookup
`#SingleInstance` relies on internally - since AutoHotkey has no separate
documented API for it. Because of that, this widget's suspended/not
tracking is best-effort: it reflects the last toggle *this widget* sent,
and can drift if the script's own hotkey or its tray icon is used to
suspend it instead. `_MACRO_TEMPLATE` includes an example of a script
toggling its own suspend state (`F12::Suspend`), the usual pattern for
flipping a keybind remap on and off without leaving Multitool.

A macro can also be marked "Start with Multitool", auto-enabled by
`_start_on_app_launch` (`Widget.on_app_start`) - the same mechanism
Autoclicker uses for its own "Start on launch" toggle - mirroring adding a
keybind-remap script to Windows startup instead of pressing Enable by hand
every session.

AutoHotkey only exists on Windows, so Enable/Disable and Suspend/Resume are
Windows-only; storing, searching, importing, and deleting macros are plain
file operations and work on any platform.

`_find_autohotkey()` checks the PATH first (`AutoHotkeyU64`, `AutoHotkey64`,
`AutoHotkey`), then a handful of common install locations. Settings ->
Widgets -> Autohotkey lets a user override the path directly if their
install lives somewhere else.

## Editing

This widget never edits a macro's text itself. Pressing Edit always hands
the file off to an external editor - and, like Windows' own "Open with",
Settings -> Widgets -> Autohotkey lets you pick literally any app on your
system for that, not a fixed shortlist:

- **Automatic** (the default, an empty `editor_path` setting) - VS Code if
  it's installed (`code` found on the PATH, or a common install location),
  otherwise Notepad (`open -e` / TextEdit on macOS).
- **Notepad** / **VS Code** quick-pick buttons, shown only if each is
  actually found on the system.
- **Choose another app...**, a file picker for any executable, exactly
  like clicking "Look for another app on this PC" in Windows' own dialog.
  If the chosen path stops existing later (the app was uninstalled), Edit
  falls back to Automatic and shows a toast rather than failing silently.

`code` is a `.cmd` shim on Windows, which Windows can't launch directly
without going through `cmd.exe` - a plain exec attempt fails with WinError
193 - so that case (however the path was chosen) is wrapped in `cmd /c`.

## Trying it locally

Copy this `ahk` folder into the widgets folder shown in Settings ->
Widgets, then enable it from the Widgets screen. In Developer Mode
(running from a source checkout), it's already visible with no copying
needed - see this repo's `widgets/` folder.

## See also

`multitool/widgets/process.py` is the shared helper this widget uses to
start and stop the AutoHotkey process a macro's Enable/Disable button
controls.
