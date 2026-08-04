"""Thin launcher for Toolblox. Run with ``python main.py``.

The app itself lives in `toolblox.app`; this just calls it, so
``python -m toolblox.app`` works the same way.
"""

from toolblox.app import run

if __name__ == "__main__":
    run()
