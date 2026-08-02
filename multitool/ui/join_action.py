"""Shared join flow, used by both the Accounts screen and the Dashboard."""

import asyncio

import flet as ft

from multitool.data import accounts as accounts_store
from multitool.logs import get_logger
from multitool.roblox.join import get_join_url
from multitool.roblox.multi_instance import clear_singleton_instance
from multitool.state import get_multi_instance, get_place_id
from multitool.ui.toast import show_toast

logger = get_logger(__name__)


async def join_with_account(page: ft.Page, account: dict) -> None:
    """Join the configured place with one account's saved session.

    Shows a toast on any failure, such as a missing place id, a missing
    session, or Roblox not being installed. Records the play on success.
    """
    place_id = get_place_id(page)
    if not place_id:
        show_toast(page, "No place ID is set. Did you configure one in Settings?")
        return

    security_cookie = account.get("security_cookie")
    if not security_cookie:
        show_toast(page, "This account has no saved session. Would removing and re-adding it help?")
        return

    try:
        join_url = await asyncio.to_thread(get_join_url, security_cookie, place_id)
    except Exception as ex:
        logger.warning("Join failed for account %s: %s", account.get("id"), ex)
        show_toast(page, f"Couldn't join. {ex}")
        return

    if get_multi_instance(page):
        await asyncio.to_thread(clear_singleton_instance)

    launcher = ft.UrlLauncher()
    not_installed_message = "Couldn't launch Roblox. Is it installed on this computer?"

    try:
        can_launch = await launcher.can_launch_url(join_url)
    except Exception as e:
        logger.warning("can_launch_url check failed, assuming true: %s", e)
        can_launch = True

    if not can_launch:
        show_toast(page, not_installed_message)
        return

    try:
        await launcher.launch_url(join_url)
    except Exception as e:
        logger.warning("launch_url failed: %s", e)
        show_toast(page, not_installed_message)
        return

    accounts_store.record_play(account["id"])
