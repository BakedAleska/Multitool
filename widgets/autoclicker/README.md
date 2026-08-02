# Autoclicker

Clicks repeatedly at the cursor. `widget.py` builds the UI with Flet, since
Flet can only render controls from Python code running in-process, but the
actual clicking runs as a separate platform script it starts and stops —
proof that Multitool widgets aren't limited to Python:

- `backend/click_windows.ps1`, a PowerShell script calling `user32.dll`
  directly. No extra dependencies. Left, middle, and right click.
- `backend/click_macos.sh`, a shell script that shells out to
  [cliclick](https://github.com/BlueM/cliclick) (`brew install cliclick`).
  Left and right click only — cliclick has no middle-click command.

Both scripts speak the same tiny protocol: one JSON line per click on
stdout (`{"count": N}`), or `{"error": "..."}` if something's wrong. The
Python side never parses their internals, just their stdout.

Clicking speed is set as clicks per second (1-20), not a raw interval.
That upper bound isn't arbitrary: at 20 CPS the wait between clicks is
50ms, comfortably above the ~15.6ms tick Windows' default scheduler
resolution allows, so the reported click count can actually track the
requested rate. An optional "Randomize timing" setting jitters each
click's wait by up to 15% so the pattern isn't perfectly periodic.

Two more backends run alongside the click loop, both cross-platform
Python scripts using the same "external process, JSON over stdout"
pattern instead of a platform script:

- `backend/keybind_listener.py`, using [pynput](https://pynput.readthedocs.io/)
  to listen system-wide for hotkeys, so clicking can be started or
  stopped without switching focus back to Multitool. Any number of
  keybinds can be bound to start, and any number to stop, set from the
  Autoclicker screen by pressing "Add keybind" and then the key
  combination itself. On macOS this needs Accessibility permission
  granted to the process running it, the same requirement any
  global-hotkey tool has there.
- `backend/overlay.py`, a small always-on-top tkinter window shown in
  the corner of the screen while clicking is active, so it stays
  visible even when Multitool itself is in the background. Optional,
  toggled from the Autoclicker screen. Click-through on Windows; on
  macOS it's topmost but not click-through, tkinter has no equivalent
  there.

## Ban risk

Roblox's ToS and Rogue Lineage's own community norms are strict about
automation, particularly anything touching combat. Using this widget in
Rogue Lineage risks the account it's running on.

## Trying it locally

Copy this `autoclicker` folder into the widgets folder shown in
Settings -> Widgets, then enable it from the Widgets screen.

## See also

`multitool/widgets/process.py` is the shared helper any widget can use to start,
message, and stop a non-Python backend process like this one.
