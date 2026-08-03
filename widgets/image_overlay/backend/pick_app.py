"""One-shot native "choose an app" dialog for the Image Overlay widget.

Prints exactly one JSON line and exits, the same one-shot subprocess
pattern widgets/image_overlay/backend/area_picker.py and
widgets/ahk/backend/pick_editor.py use for their own dialogs:
`{"path": "..."}` if a file was chosen, or `{"path": null}` if the dialog
was cancelled. Run as a subprocess rather than importing tkinter directly
into Multitool's own process, since tkinter needs its own mainloop and
Flet's asyncio event loop already occupies the main thread.
"""

import json
import sys
import tkinter as tk
from tkinter import filedialog


def main() -> None:
    root = tk.Tk()
    root.withdraw()
    filetypes = [("Applications", "*.exe")] if sys.platform == "win32" else [("All files", "*.*")]
    path = filedialog.askopenfilename(
        title="Choose an app to watch for", filetypes=filetypes
    )
    root.destroy()
    print(json.dumps({"path": path or None}), flush=True)


if __name__ == "__main__":
    main()
