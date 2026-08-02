# Autoclicker

Clicks repeatedly at the cursor. `widget.py` builds the UI with Flet, since
Flet can only render controls from Python code running in-process, but the
actual clicking runs as a separate platform script it starts and stops —
proof that Multitool widgets aren't limited to Python:

- `backend/click_windows.ps1`, a PowerShell script calling `user32.dll`
  directly. No extra dependencies.
- `backend/click_macos.sh`, a shell script that shells out to
  [cliclick](https://github.com/BlueM/cliclick) (`brew install cliclick`).

Both scripts speak the same tiny protocol: one JSON line per click on
stdout (`{"count": N}`), or `{"error": "..."}` if something's wrong. The
Python side never parses their internals, just their stdout.

## Trying it locally

Copy this `autoclicker` folder into the widgets folder shown in
Settings -> Widgets, then enable it from the Widgets screen.

## See also

`multitool/widgets/process.py` is the shared helper any widget can use to start,
message, and stop a non-Python backend process like this one.
