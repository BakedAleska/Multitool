"""Helpers behind Developer Mode: a small "DEV" badge in the nav rail's
corner (see toolblox/ui/layout.py) plus a couple of tools in Settings ->
General -> Danger Zone, all of it automatic rather than a setting.

Developer Mode exists so widget and fork development doesn't need a
commit-and-push round trip to see a change working. It turns itself on
by detecting a source checkout (see is_dev_environment) rather than
needing a switch flipped or a path typed in by hand: run the app from
this repo and widgets/ and registry.json are read from the repo
directly; run a packaged build and none of this is present.
"""

import os
import sys
from pathlib import Path
from typing import Optional

from toolblox.logs import LOG_FILE

REPO_ROOT = Path(__file__).resolve().parent.parent
CANARY_OPT_IN_NAME = "TOOLBLOX_ENABLE_CANARY"
CANARY_OPT_IN_VALUE = "i-understand-this-is-unvetted"


def is_dev_environment() -> bool:
    """Whether the app is running from a source checkout, not a packaged build.

    A frozen build (see toolblox/startup.py, which uses the same
    sys.frozen check for its own purposes) sets sys.frozen; running via
    `python main.py` from an IDE or a repo checkout does not. This one
    check is what Developer Mode gates on everywhere - there's nothing
    to configure, and nothing here can accidentally ship turned on,
    since a packaged build is never running from source.
    """
    return not getattr(sys, "frozen", False)


def _dotenv_value(key: str) -> Optional[str]:
    """Read a single key from a `.env` file at the repo root, if present.

    A minimal, dependency-free stand-in for python-dotenv - this is the
    only value this project currently needs from a `.env` file. `.env`
    is gitignored, so this never reads anything committed to the repo.
    """
    env_path = REPO_ROOT / ".env"
    if not env_path.is_file():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        if name.strip() == key:
            return value.strip().strip('"').strip("'")
    return None


def has_canary_access() -> bool:
    """Whether TOOLBLOX_ENABLE_CANARY is set to its exact opt-in phrase.

    This isn't a real access control - the repo is public, so anyone
    who reads this check can satisfy it. The point is deliberateness:
    running from source alone (is_dev_environment()) used to be enough
    to land on Canary, which meant a plain `git clone` + `python
    main.py` got you the Catalogue and unvetted widgets by accident.
    Requiring an exact phrase, rather than any truthy value, means
    landing on Canary takes finding this check and typing it in on
    purpose, not just setting some env var on a hunch. Deliberately not
    documented anywhere outside this module - if someone finds it by
    reading the source, that's fine.
    """
    value = os.environ.get(CANARY_OPT_IN_NAME) or _dotenv_value(CANARY_OPT_IN_NAME)
    return value == CANARY_OPT_IN_VALUE


def release_channel() -> str:
    """The build's release channel: "beta" or "canary".

    A packaged build is always "beta" - the curated, publicly
    advertised release with no Catalogue. Running from a source
    checkout is "canary" only with a deliberate opt-in (see
    has_canary_access); otherwise a source checkout is "beta" too, same
    as a packaged build. There's no separate packaged Canary build.
    """
    return "canary" if is_dev_environment() and has_canary_access() else "beta"


def dev_widgets_dir() -> Optional[Path]:
    """This repo's widgets/ folder, if running from source, else None.

    Passed straight to toolblox.widgets.loader.discover_widgets() as
    its extra_dir, so editing a widget's source under widgets/ shows up
    without installing it into WIDGETS_DIR first.
    """
    if not is_dev_environment():
        return None
    candidate = REPO_ROOT / "widgets"
    return candidate if candidate.is_dir() else None


def dev_registry_path() -> Optional[Path]:
    """This repo's registry.json, if running from source, else None.

    Lets the Catalogue be exercised against the repo's own registry
    (including any local: true entries added for testing) instead of
    the one published on GitHub.
    """
    if not is_dev_environment():
        return None
    candidate = REPO_ROOT / "registry.json"
    return candidate if candidate.is_file() else None


def reload_current_view(page) -> None:
    """Force the view currently on screen to rebuild from scratch.

    Replays the page's own route-change handler against its current
    route, which is exactly what a real navigation does - and since
    toolblox.widgets.loader.discover_widgets() always reimports widget
    code fresh, this is what makes an edit to a widget's source show up
    immediately instead of waiting for the next real navigation.
    """
    if page.on_route_change is not None:
        page.on_route_change(page.route)


def tail_log(lines: int = 300) -> str:
    """The last `lines` lines of the app's log file.

    Lets Developer Mode show recent log activity in-app, without
    needing to go find <DATA_DIR>/logs/toolblox.log on disk.
    """
    if not LOG_FILE.exists():
        return "No log file yet."
    try:
        content = LOG_FILE.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return f"Couldn't read the log file: {e}"
    return "\n".join(content.splitlines()[-lines:]) or "Log file is empty."
