"""Thin launcher for Multitool. Run with ``python main.py``.

The app itself lives in `multitool.app`; this just calls it, so
``python -m multitool.app`` works the same way.
"""

from multitool.app import run

if __name__ == "__main__":
    run()
