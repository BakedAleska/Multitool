"""Thin launcher for Toolblox. Run with ``python main.py``.

The app itself lives in `toolblox.app`; this just calls it, so
``python -m toolblox.app`` works the same way.

A frozen build's own exe is relaunched with `toolblox.roblox.login.LOGIN_ARG`
to open the Roblox login window (see that module's docstring and
toolblox/ui/accounts.py) instead of the normal app.
"""

import sys

from toolblox.app import run
from toolblox.roblox.login import LOGIN_ARG
from toolblox.roblox.login import main as run_login

if __name__ == "__main__":
    if LOGIN_ARG in sys.argv[1:]:
        run_login()
    else:
        run()
