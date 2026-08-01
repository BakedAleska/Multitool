import asyncio
import json
import sys
import time
from pathlib import Path

import flet as ft
import httpx

from app.data import accounts as accounts_store
from app.logs import get_logger
from app.roblox.join import get_join_url
from app.state import get_compact_mode, get_place_id, get_show_avatars, get_sort_order
from app.ui.layout import build_layout
from app.ui.toast import show_confirm_toast, show_toast

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

AVATAR_SIZE = 56
COMPACT_AVATAR_SIZE = 28

USER_URL = "https://users.roblox.com/v1/users/{user_id}"
THUMBNAIL_URL = "https://thumbnails.roblox.com/v1/users/avatar-headshot"


def fetch_profile(user_id: int) -> dict:
    profile = {}

    try:
        response = httpx.get(USER_URL.format(user_id=user_id), timeout=10)
        response.raise_for_status()
        data = response.json()
        profile["display_name"] = data.get("displayName") or data.get("name")
    except (httpx.HTTPError, ValueError) as e:
        logger.warning("Couldn't fetch display name for user %s: %s", user_id, e)

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
        if data:
            profile["avatar_url"] = data[0]["imageUrl"]
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
        logger.warning("Couldn't fetch avatar for user %s: %s", user_id, e)

    return profile


def sort_accounts(accounts: list[dict], sort_order: str) -> list[dict]:
    if sort_order == "alphabetical":
        return sorted(accounts, key=lambda a: (a.get("display_name") or a["name"]).lower())
    if sort_order == "manual":
        return list(accounts)
    return sorted(accounts, key=lambda a: a.get("added_at", 0))


def AccountsView(page: ft.Page) -> ft.View:
    def refresh():
        if not page.views or page.views[-1].route != "/accounts":
            return
        page.views[-1] = AccountsView(page)
        page.update()

    async def backfill_missing_profiles():
        current = accounts_store.load()
        missing = [a for a in current if not a.get("avatar_url") or not a.get("display_name")]
        if not missing:
            return

        changed = False
        for account in missing:
            profile = await asyncio.to_thread(fetch_profile, account["id"])
            if profile.get("display_name") and not account.get("display_name"):
                account["display_name"] = profile["display_name"]
                changed = True
            if profile.get("avatar_url") and not account.get("avatar_url"):
                account["avatar_url"] = profile["avatar_url"]
                changed = True

        if changed:
            accounts_store.save(current)
            refresh()

    def add_account(payload: dict):
        current = accounts_store.load()
        if not any(a["id"] == payload["id"] for a in current):
            current.append(
                {
                    "id": payload["id"],
                    "name": payload["name"],
                    "display_name": payload.get("display_name") or payload["name"],
                    "avatar_url": payload.get("avatar_url"),
                    "notes": "",
                    "added_at": time.time(),
                    "security_cookie": payload.get("security_cookie"),
                }
            )
            accounts_store.save(current)
        refresh()

    def remove_account(user_id: int):
        current = accounts_store.load()
        current = [a for a in current if a["id"] != user_id]
        accounts_store.save(current)
        refresh()

    def save_notes(user_id: int, notes: str):
        current = accounts_store.load()
        for a in current:
            if a["id"] == user_id:
                a["notes"] = notes
                break
        accounts_store.save(current)

    async def open_add_account(e: ft.Event[ft.IconButton]):
        add_button.disabled = True
        page.update()

        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "app.roblox.login",
                cwd=PROJECT_ROOT,
                stdout=asyncio.subprocess.PIPE,
            )
            line = await proc.stdout.readline()
            await proc.wait()
        finally:
            add_button.disabled = False
            page.update()

        if not line:
            return

        try:
            payload = json.loads(line)
        except json.JSONDecodeError as e:
            logger.warning("Couldn't parse login subprocess output %r: %s", line, e)
            return

        add_account(payload)

    async def join_with_account(account: dict):
        place_id = get_place_id(page)
        if not place_id:
            show_toast(page, "Set a place ID in Settings first.")
            return

        security_cookie = account.get("security_cookie")
        if not security_cookie:
            show_toast(page, "No saved session for this account — remove and re-add it.")
            return

        try:
            join_url = await asyncio.to_thread(get_join_url, security_cookie, place_id)
        except Exception as ex:
            logger.warning("Join failed for account %s: %s", account.get("id"), ex)
            show_toast(page, f"Couldn't join: {ex}")
            return

        launcher = ft.UrlLauncher()
        not_installed_message = "Couldn't launch Roblox — is it installed on this computer?"

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

    def build_account_card(account: dict, sort_order: str) -> ft.Control:
        username = account["name"]
        display_name = account.get("display_name") or username
        if display_name and display_name != username:
            header_text = f"({display_name}) {username}"
        else:
            header_text = username

        compact = get_compact_mode(page)
        avatar_size = COMPACT_AVATAR_SIZE if compact else AVATAR_SIZE
        show_avatars = get_show_avatars(page)

        row_controls: list[ft.Control] = []

        if show_avatars:
            avatar_url = account.get("avatar_url")
            avatar_content = (
                ft.Image(src=avatar_url, width=avatar_size, height=avatar_size, fit=ft.BoxFit.COVER)
                if avatar_url
                else ft.Icon(ft.Icons.PERSON, size=avatar_size * 0.6)
            )

            row_controls.append(
                ft.Container(
                    content=avatar_content,
                    width=avatar_size,
                    height=avatar_size,
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    alignment=ft.Alignment.CENTER,
                )
            )

        column_controls: list[ft.Control] = [ft.Text(header_text, weight=ft.FontWeight.W_500)]

        if not compact:
            column_controls.append(
                ft.TextField(
                    value=account.get("notes", ""),
                    hint_text="Notes...",
                    multiline=True,
                    dense=True,
                    border=ft.InputBorder.NONE,
                    content_padding=ft.Padding.symmetric(vertical=4, horizontal=0),
                    text_size=12,
                    hint_style=ft.TextStyle(color=ft.Colors.ON_SURFACE_VARIANT, size=12),
                    on_blur=lambda e, uid=account["id"]: save_notes(uid, e.control.value),
                )
            )

        is_manual = sort_order == "manual"
        # In the compact 3-icon row, order left-to-right as: play, remove, move.
        compact_row = compact and is_manual

        row_controls.append(ft.Column(column_controls, expand=True, spacing=2))

        card_padding = 8 if compact else 12
        button_clearance = 100 if compact_row else 64
        card = ft.Container(
            content=ft.Row(
                row_controls,
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
                if compact
                else ft.CrossAxisAlignment.START,
            ),
            padding=ft.Padding.only(
                left=card_padding,
                top=card_padding,
                bottom=card_padding,
                right=card_padding + button_clearance,
            ),
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=8,
        )

        stack_controls = [card]

        drag_handle_widget = None
        handle_box_size = 0

        if is_manual:
            handle_icon_size = 18
            handle_padding = 8  # matches IconButton's default padding, for a flush look
            handle_box_size = handle_icon_size + handle_padding * 2

            def on_handle_hover(e: ft.Event[ft.Container]):
                e.control.opacity = 1.0 if e.data == "true" else 0.4
                e.control.update()

            drag_handle_widget = ft.ReorderableDragHandle(
                content=ft.Container(
                    content=ft.Icon(
                        ft.Icons.DRAG_INDICATOR,
                        size=handle_icon_size,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    alignment=ft.Alignment.CENTER,
                    padding=handle_padding,
                    border_radius=handle_box_size / 2,
                    opacity=0.4,
                    animate_opacity=150,
                    on_hover=on_handle_hover,
                ),
                mouse_cursor=ft.MouseCursor.GRAB,
            )

        play_button = ft.IconButton(
            icon=ft.Icons.PLAY_CIRCLE_OUTLINE,
            icon_size=18,
            tooltip="Join place",
            on_click=lambda e, a=account: page.run_task(join_with_account, a),
        )

        remove_button = ft.IconButton(
            icon=ft.Icons.REMOVE_CIRCLE_OUTLINE,
            icon_size=18,
            tooltip="Remove account",
            on_click=lambda e, uid=account["id"], label=header_text: show_confirm_toast(
                page, f"Remove {label}?", lambda: remove_account(uid)
            ),
        )

        if compact_row:
            # Lay these out together in a real Row so Flet centers them
            # against each other's actual rendered size, rather than us
            # guessing pixel offsets that never quite matched IconButton's.
            # top+bottom (both set, no explicit height) stretches this
            # wrapper to the card's full height, so the row can be
            # vertically centered within it instead of hugging the top.
            stack_controls.append(
                ft.Container(
                    content=ft.Row(
                        [play_button, remove_button, drag_handle_widget],
                        spacing=0,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    top=0,
                    bottom=0,
                    right=0,
                    alignment=ft.Alignment.CENTER_RIGHT,
                )
            )
        else:
            play_button.top = 2
            play_button.right = 34
            remove_button.top = 2
            remove_button.right = 2
            stack_controls.extend([play_button, remove_button])

            if drag_handle_widget is not None:
                if compact:
                    handle_top = 2
                else:
                    # Bottom of the handle lines up with the bottom of the
                    # avatar frame (a fixed, known offset), regardless of
                    # card height.
                    handle_top = (
                        card_padding + avatar_size - handle_box_size if show_avatars else 2
                    )
                stack_controls.append(
                    ft.Container(content=drag_handle_widget, top=handle_top, right=2)
                )

        return ft.Stack(
            stack_controls,
            key=str(account["id"]),
        )

    sort_order = get_sort_order(page)
    accounts = sort_accounts(accounts_store.load(), sort_order)
    list_spacing = 4 if get_compact_mode(page) else 8

    if sort_order == "manual":

        def on_reorder(e: ft.OnReorderEvent):
            current = accounts_store.load()
            item = current.pop(e.old_index)
            current.insert(e.new_index, item)
            accounts_store.save(current)
            refresh()

        account_list: ft.Control = ft.ReorderableListView(
            controls=[build_account_card(a, sort_order) for a in accounts],
            expand=True,
            spacing=list_spacing,
            show_default_drag_handles=False,
            on_reorder=on_reorder,
        )
    else:
        account_list = ft.ListView(
            controls=[build_account_card(a, sort_order) for a in accounts],
            expand=True,
            spacing=list_spacing,
        )

    add_button = ft.IconButton(
        icon=ft.Icons.ADD,
        tooltip="Add account",
        on_click=open_add_account,
    )

    content = ft.Column(
        [
            ft.Row(
                [
                    ft.Text("Accounts", size=24, weight=ft.FontWeight.BOLD),
                    add_button,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            account_list,
        ],
        expand=True,
    )

    page.run_task(backfill_missing_profiles)

    return ft.View(
        route="/accounts",
        padding=0,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[build_layout(page, content)],
    )
