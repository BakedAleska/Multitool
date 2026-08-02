"""Global keybind listener backend for the Autoclicker widget.

Listens system-wide (not just while the app window has focus) for any of
a configured set of "start" hotkeys or "stop" hotkeys, and prints one
JSON line to stdout each time one fires: {"event": "start"} or
{"event": "stop"}. widget.py starts and stops the actual click backend
in response, the same way it does for its manual Start/Stop buttons.

A hotkey listed in both the start and stop lists gets a third event,
{"event": "toggle"}, instead of being bound to either directly. This
process has no idea whether clicking is currently running - only
widget.py does - so it can't decide on its own whether a shared key
should mean start or stop; it just reports that the key fired and lets
widget.py apply it against the real state.

This is a Python script rather than a platform-native one, unlike the
click backends, because global hotkey capture needs a real keyboard hook
and pynput already wraps the platform APIs for that on both Windows and
macOS. It still follows the same "external process talking newline JSON
over stdout" pattern as every other widget backend in this project.

Usage: keybind_listener.py <start_hotkeys_json> <stop_hotkeys_json>
Each argument is a JSON list of pynput hotkey strings, e.g.
'["<f6>", "<ctrl>+<f7>"]'. An empty list ("[]") means no hotkeys are
bound for that action.

On macOS this requires the process running it (effectively the Python
interpreter) to be granted Accessibility permission in System Settings,
the same requirement any global-hotkey tool has there.
"""

import json
import sys

from pynput import keyboard


def _print_event(event: str) -> None:
    print(json.dumps({"event": event}), flush=True)


def main() -> None:
    """Parse the hotkey arguments and block listening for them until killed.

    Any failure, missing arguments, no hotkeys at all, or pynput itself
    failing to start, is reported as one `{"error": "..."}` line rather
    than a traceback, since the parent process only reads stdout.
    """
    if len(sys.argv) != 3:
        print(json.dumps({"error": "keybind_listener.py needs start and stop hotkey lists."}))
        sys.exit(1)

    start_hotkeys = set(json.loads(sys.argv[1]))
    stop_hotkeys = set(json.loads(sys.argv[2]))
    toggle_hotkeys = start_hotkeys & stop_hotkeys

    bindings = {
        hotkey: (lambda: _print_event("start")) for hotkey in start_hotkeys - toggle_hotkeys
    }
    bindings.update(
        {hotkey: (lambda: _print_event("stop")) for hotkey in stop_hotkeys - toggle_hotkeys}
    )
    bindings.update({hotkey: (lambda: _print_event("toggle")) for hotkey in toggle_hotkeys})

    if not bindings:
        print(json.dumps({"error": "No keybinds were configured."}))
        sys.exit(1)

    try:
        with keyboard.GlobalHotKeys(bindings) as listener:
            listener.join()
    except Exception as exc:
        print(json.dumps({"error": f"Keybind listener failed to start: {exc}"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
