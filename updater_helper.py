"""Thin launcher for Toolblox's in-place updater helper.

The real logic lives in `toolblox.updater_helper`; this is PyInstaller's
entry point for the separate `ToolbloxUpdater.exe` build (see
release/build.py), the same split main.py uses for the main app.
"""

from toolblox.updater_helper import main

if __name__ == "__main__":
    main()
