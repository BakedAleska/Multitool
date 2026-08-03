"""Fetch Roblox presence for a batch of user ids.

Used to tell whether a tracked account is currently in a Roblox place, for
the status dot shown on the Accounts screen.
"""

import httpx

from multitool.logs import get_logger

logger = get_logger(__name__)

PRESENCE_URL = "https://presence.roblox.com/v1/presence/users"

IN_GAME = 2
"""The userPresenceType value Roblox's presence API uses for "currently
playing a place". Other values cover offline, online (browsing the site),
and in Studio.
"""


def fetch_presence(cookie: str, user_ids: list[int]) -> dict[int, int]:
    """Return {user_id: userPresenceType} for the given ids.

    Any account's session cookie can be used to look up presence for any
    user id, not just its own. The endpoint rejects a request missing a
    CSRF token with a 403 that carries the token in its headers, so the
    first call doubles as a way to fetch one. Never raises: returns an
    empty dict if the request fails at any point, leaving status
    unresolved rather than crashing the caller.
    """
    if not user_ids:
        return {}

    try:
        with httpx.Client(cookies={".ROBLOSECURITY": cookie}, timeout=10) as client:
            response = client.post(PRESENCE_URL, json={"userIds": user_ids})
            if response.status_code == 403:
                csrf_token = response.headers.get("x-csrf-token")
                if not csrf_token:
                    return {}
                response = client.post(
                    PRESENCE_URL,
                    headers={"X-CSRF-TOKEN": csrf_token},
                    json={"userIds": user_ids},
                )
            response.raise_for_status()
            presences = response.json().get("userPresences", [])
    except (httpx.HTTPError, ValueError) as e:
        logger.warning("Couldn't fetch presence: %s", e)
        return {}

    return {p["userId"]: p["userPresenceType"] for p in presences if "userId" in p}
