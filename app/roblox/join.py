import re
import time
import uuid
from urllib.parse import quote

import httpx

PLACE_URL_PATTERN = re.compile(r"/games/(\d+)")
DIGITS_PATTERN = re.compile(r"\d+")

AUTH_TICKET_URL = "https://auth.roblox.com/v1/authentication-ticket"
PLACE_LAUNCHER_URL = "https://assetgame.roblox.com/game/PlaceLauncher.ashx"
GAME_URL_TEMPLATE = "https://www.roblox.com/games/{place_id}"


def extract_place_id(text: str) -> str:
    text = text.strip()

    match = PLACE_URL_PATTERN.search(text)
    if match:
        return match.group(1)

    match = DIGITS_PATTERN.search(text)
    return match.group(0) if match else ""


def get_join_url(security_cookie: str, place_id: str) -> str:
    referer = GAME_URL_TEMPLATE.format(place_id=place_id)
    headers = {"Referer": referer, "Origin": "https://www.roblox.com"}

    with httpx.Client(cookies={".ROBLOSECURITY": security_cookie}, timeout=10) as client:
        response = client.post(AUTH_TICKET_URL, headers=headers, json={})
        csrf_token = response.headers.get("x-csrf-token")
        if not csrf_token:
            raise RuntimeError("Could not get a CSRF token — the account may be signed out.")

        headers["X-CSRF-TOKEN"] = csrf_token
        response = client.post(AUTH_TICKET_URL, headers=headers, json={})
        if response.status_code != 200:
            raise RuntimeError(f"Roblox rejected the request (status {response.status_code}).")

        ticket = response.headers.get("rbx-authentication-ticket")
        if not ticket:
            raise RuntimeError("Roblox didn't return an authentication ticket.")

    browser_tracker_id = uuid.uuid4().int & 0xFFFFFFFF
    launch_time = int(time.time() * 1000)
    place_launcher_url = (
        f"{PLACE_LAUNCHER_URL}?request=RequestGame"
        f"&browserTrackerId={browser_tracker_id}"
        f"&placeId={place_id}"
        f"&isPlayTogetherGame=false"
    )

    return (
        "roblox-player:1"
        "+launchmode:play"
        f"+gameinfo:{ticket}"
        f"+launchtime:{launch_time}"
        f"+placelauncherurl:{quote(place_launcher_url, safe='')}"
        f"+browsertrackerid:{browser_tracker_id}"
        "+robloxLocale:en_us"
        "+gameLocale:en_us"
        "+channel:"
    )
