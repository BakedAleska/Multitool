"""Standalone Roblox login window, run as a subprocess.

pywebview needs to own the main thread. Flet's own event loop already
occupies the main thread in the parent process, so this module is
launched separately (see toolblox/ui/accounts.py) instead of being
embedded in the main app. Running from source, that's `python -m
toolblox.roblox.login`, since `sys.executable` is a real interpreter
there. A frozen build has no such interpreter to invoke - its
`sys.executable` is the packaged app itself - so accounts.py instead
relaunches that same executable with the `LOGIN_ARG` flag, which
main.py checks for and dispatches to `main()` here instead of the
normal app.

IPC with the parent process is a single JSON line on stdout. This
process never prints anything else.
"""

import json
import time
from typing import Optional

import httpx
import webview

from toolblox.logs import get_logger

logger = get_logger(__name__)

LOGIN_URL = "https://www.roblox.com/login"
AUTH_URL = "https://users.roblox.com/v1/users/authenticated"
THUMBNAIL_URL = "https://thumbnails.roblox.com/v1/users/avatar-headshot"
SECURITY_COOKIE_NAME = ".ROBLOSECURITY"

LOGIN_ARG = "--roblox-login"
"""CLI flag that tells a frozen build's relaunched exe to run this
module's main() instead of the normal app. See this module's
docstring and main.py."""

POLL_INTERVAL_SECONDS = 1.0


def get_security_cookie(window: "webview.Window") -> Optional[str]:
    """Read the Roblox session cookie via pywebview's native cookie jar.

    Not `window.evaluate_js()`. Roblox's CSP blocks `unsafe-eval`, so
    JS injection silently fails on roblox.com pages.
    """
    for cookie in window.get_cookies():
        if SECURITY_COOKIE_NAME in cookie:
            return cookie[SECURITY_COOKIE_NAME].value
    return None


def get_avatar_url(user_id: int) -> Optional[str]:
    """Fetch a user's avatar headshot URL. Returns None on any failure."""
    try:
        response = httpx.get(
            THUMBNAIL_URL,
            params={
                "userIds": user_id,
                "size": "150x150",
                "format": "Png",
                "isCircular": "false",
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json().get("data") or []
        return data[0]["imageUrl"] if data else None
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
        logger.warning("Couldn't fetch avatar for user %s: %s", user_id, e)
        return None


def poll_for_login(window: "webview.Window"):
    """Poll the login window for a session cookie until one appears.

    Once found and validated, prints the resulting account as a single
    JSON line to stdout and closes the window.
    """
    while not window.events.closed.is_set():
        time.sleep(POLL_INTERVAL_SECONDS)

        if window.events.closed.is_set():
            return

        try:
            security_cookie = get_security_cookie(window)
        except Exception as e:
            logger.warning("Cookie check failed: %s", e)
            continue

        if not security_cookie:
            continue

        try:
            response = httpx.get(
                AUTH_URL,
                cookies={SECURITY_COOKIE_NAME: security_cookie},
                timeout=10,
            )
        except httpx.HTTPError as e:
            logger.warning("Auth check request failed: %s", e)
            continue

        if response.status_code != 200:
            continue

        payload = response.json()
        account = {
            "id": payload["id"],
            "name": payload["name"],
            "display_name": payload.get("displayName") or payload["name"],
            "avatar_url": get_avatar_url(payload["id"]),
            "security_cookie": security_cookie,
        }
        print(json.dumps(account), flush=True)
        window.destroy()
        return


def main():
    """Open the Roblox login window and block until a session is captured."""
    window = webview.create_window("Sign in to Roblox", LOGIN_URL, width=480, height=640)
    webview.start(poll_for_login, (window,))


if __name__ == "__main__":
    main()
