import json
import time
from typing import Optional

import httpx
import webview

from app.logs import get_logger

# Never print() anything other than the final JSON line below — stdout is
# a strict single-line IPC protocol read by app/ui/accounts.py. Logging is
# safe here regardless (app.logs only ever writes to a file), but keep this
# in mind before adding any other diagnostics to this file.
logger = get_logger(__name__)

LOGIN_URL = "https://www.roblox.com/login"
AUTH_URL = "https://users.roblox.com/v1/users/authenticated"
THUMBNAIL_URL = "https://thumbnails.roblox.com/v1/users/avatar-headshot"
SECURITY_COOKIE_NAME = ".ROBLOSECURITY"

POLL_INTERVAL_SECONDS = 1.0


def get_security_cookie(window: "webview.Window") -> Optional[str]:
    for cookie in window.get_cookies():
        if SECURITY_COOKIE_NAME in cookie:
            return cookie[SECURITY_COOKIE_NAME].value
    return None


def get_avatar_url(user_id: int) -> Optional[str]:
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
    window = webview.create_window("Sign in to Roblox", LOGIN_URL, width=480, height=640)
    webview.start(poll_for_login, (window,))


if __name__ == "__main__":
    main()
