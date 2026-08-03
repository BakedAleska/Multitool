"""The Accounts screen: list, add, remove, join, and reorder tracked accounts."""

import asyncio
import json
import sys
import time
from pathlib import Path

import flet as ft
import httpx

from multitool.data import accounts as accounts_store
from multitool.logs import get_logger
from multitool.roblox import status as status_tracker
from multitool.roblox.process_watch import running_pids
from multitool.state import get_compact_mode, get_show_avatars, get_sort_order
from multitool.ui.join_action import join_with_account
from multitool.ui.layout import build_layout
from multitool.ui.style import (
    SPACE_MD,
    card_border,
    radius_card,
    scroll_padding,
    text_label,
    text_title,
)
from multitool.ui.toast import show_confirm_toast

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

AVATAR_SIZE = 56
COMPACT_AVATAR_SIZE = 28

USER_URL = "https://users.roblox.com/v1/users/{user_id}"
THUMBNAIL_URL = "https://thumbnails.roblox.com/v1/users/avatar-headshot"

_GENERATION_KEY = "_accounts_view_generation"

STATUS_COLORS = {
    status_tracker.GREY: ft.Colors.OUTLINE_VARIANT,
    status_tracker.RED: ft.Colors.ERROR,
    status_tracker.GREEN: ft.Colors.GREEN,
}
STATUS_LABELS = {
    status_tracker.GREY: "Not in a place",
    status_tracker.RED: "Roblox may have crashed",
    status_tracker.GREEN: "In a place",
}


def fetch_profile(user_id: int) -> dict:
    """Fetch a user's display name and avatar URL from Roblox's public APIs.

    Missing pieces are left out of the result instead of raising. Used
    to backfill accounts added before these fields were tracked.
    """
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
    """Sort accounts for display, according to the given sort order.

    "manual" returns the list as stored. Drag reordering writes the new
    order to disk directly, so no sorting is needed here for that case.
    "last_played" puts the most recently played account first, falling
    back to an account's added_at if it's never been played.
    """
    if sort_order == "alphabetical":
        return sorted(accounts, key=lambda a: (a.get("display_name") or a["name"]).lower())
    if sort_order == "manual":
        return list(accounts)
    return sorted(
        accounts,
        key=lambda a: a.get("last_played_at") or a.get("added_at", 0),
        reverse=True,
    )


def AccountsView(page: ft.Page) -> ft.View:
    """The Accounts screen.

    Every mutation, such as add, remove, reorder, or edit notes, reads
    the current list from disk with accounts_store.load(), applies the
    change, writes it back, and calls refresh() to rebuild the view.
    There is no in-memory account store beyond that load and save pair.
    """

    def refresh():
        """Rebuild this view in place, if it's still the one on screen."""
        if not page.views or page.views[-1].route != "/accounts":
            return
        page.views[-1] = AccountsView(page)
        page.update()

    search_field = ft.TextField(
        hint_text="Search",
        prefix_icon=ft.Icons.SEARCH,
        dense=True,
        expand=True,
        on_change=lambda e: render_account_list(),
    )

    def account_matches(account: dict) -> bool:
        query = (search_field.value or "").strip().lower()
        if not query:
            return True
        haystack = " ".join(
            [account.get("name", ""), account.get("display_name") or "", account.get("notes") or ""]
        ).lower()
        return query in haystack

    async def backfill_missing_profiles():
        """Fill in display_name and avatar_url for older accounts.

        Runs once per view build and calls refresh() only if something
        changed.
        """
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

    async def poll_status_loop(generation: int):
        """Repeatedly refresh every account's status dot from presence.

        Runs on a timer for as long as this exact view build is the one
        on screen, tracked by generation rather than route alone - a
        route match isn't enough, since refresh() replaces this view
        with a new build (and a new loop) that would otherwise run
        alongside this one, doubling up forever.
        """
        while True:
            if (
                not page.views
                or page.views[-1].route != "/accounts"
                or page.session.store.get(_GENERATION_KEY) != generation
            ):
                return
            await status_tracker.poll_presence(page, accounts_store.load(), refresh)
            await asyncio.sleep(status_tracker.AMBIENT_POLL_SECONDS)

    async def do_join(account: dict):
        """Join with one account, then watch for a crash or an in-place status.

        Snapshots running Roblox processes before the join dispatches, so
        watch_join can tell a newly launched process apart from one that
        was already open for another account.
        """
        before_pids = await asyncio.to_thread(running_pids)
        cookie = account.get("security_cookie")
        launched = await join_with_account(page, account)
        if launched and cookie:
            page.run_task(
                status_tracker.watch_join, page, account["id"], before_pids, cookie, refresh
            )

    def add_account(payload: dict):
        """Add a newly logged in account, unless it's already tracked."""
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
        """Remove one account by id."""
        current = accounts_store.load()
        current = [a for a in current if a["id"] != user_id]
        accounts_store.save(current)
        refresh()

    def save_notes(user_id: int, notes: str):
        """Save an edited notes field for one account."""
        current = accounts_store.load()
        for a in current:
            if a["id"] == user_id:
                a["notes"] = notes
                break
        accounts_store.save(current)

    async def open_add_account(e: ft.Event[ft.IconButton]):
        """Run the Roblox login flow and add the resulting account.

        Spawns ``python -m multitool.roblox.login`` as a subprocess and reads
        the JSON line it prints to stdout on success. See that module's
        docstring for why it must run separately.
        """
        add_button.disabled = True
        page.update()

        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "multitool.roblox.login",
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

    def build_account_card(account: dict, sort_order: str) -> ft.Control:
        """Build one account row, with its play, remove, and drag controls.

        The controls are placed as Stack overlays with fixed top and
        right offsets. The one exception is compact mode with manual
        sort, where play, remove, and the drag handle sit together in a
        real Row instead, so Flet can center them against each other's
        actual size instead of relying on fixed offsets. In that row the
        order is play, remove, then drag handle.

        Outside compact mode, the drag handle's top offset lines up with
        the bottom of the avatar frame. The handle's own padding is set
        to match IconButton's default padding, so it sits flush with the
        play and remove buttons next to it.

        The status dot sits below the drag handle, centered on the same
        column as the play/remove buttons and drag handle rather than
        tucked into the raw corner. When avatars are shown outside
        compact mode, its vertical center lines up with the bottom edge
        of the avatar frame instead of the card's bottom edge.
        """
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

        dot_size = 8 if compact else 10
        account_status = status_tracker.get_status(page, account["id"])
        status_dot = ft.Container(
            width=dot_size,
            height=dot_size,
            bgcolor=STATUS_COLORS[account_status],
            border=ft.Border.all(2, ft.Colors.SURFACE),
            border_radius=dot_size / 2,
            tooltip=STATUS_LABELS[account_status],
        )

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

        column_controls: list[ft.Control] = [text_label(header_text)]

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

        is_manual = sort_order == "manual" and not (search_field.value or "").strip()
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
            border=card_border(),
            border_radius=radius_card(page),
        )

        stack_controls = [card]

        handle_icon_size = 18
        handle_padding = 8
        handle_box_size = handle_icon_size + handle_padding * 2

        status_dot.right = 2 + (handle_box_size - dot_size) / 2
        if show_avatars and not compact:
            avatar_bottom = card_padding + avatar_size
            status_dot.top = avatar_bottom - dot_size / 2
        else:
            status_dot.bottom = 2

        drag_handle_widget = None

        if is_manual:

            def on_handle_hover(e: ft.Event[ft.Container]):
                """Fade the drag handle in and out on hover."""
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
            on_click=lambda e, a=account: page.run_task(do_join, a),
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
                    handle_top = (
                        card_padding + avatar_size - handle_box_size - 4 if show_avatars else 2
                    )
                stack_controls.append(
                    ft.Container(content=drag_handle_widget, top=handle_top, right=2)
                )

        stack_controls.append(status_dot)

        return ft.Stack(stack_controls)

    sort_order = get_sort_order(page)
    list_spacing = 8 if get_compact_mode(page) else 14

    def render_account_list(mounted: bool = True):
        """Recompute the filtered, sorted account list in place.

        Only the list control's own contents change here - the search
        field itself is never rebuilt, so typing doesn't lose focus or
        reset what's been typed the way a full AccountsView(page) rebuild
        would.
        """
        sorted_accounts = sort_accounts(accounts_store.load(), sort_order)
        accounts = [a for a in sorted_accounts if account_matches(a)]
        if sort_order == "manual":
            account_list.controls = [
                ft.Container(
                    content=build_account_card(a, sort_order),
                    key=str(a["id"]),
                    margin=ft.Margin.only(bottom=list_spacing),
                )
                for a in accounts
            ]
        else:
            account_list.controls = [build_account_card(a, sort_order) for a in accounts]
        if mounted:
            account_list.update()

    if sort_order == "manual":

        def on_reorder(e: ft.OnReorderEvent):
            """Move one account to its new position and save the order.

            Only reachable while unfiltered: build_account_card hides the
            drag handle whenever a search is active, since the displayed
            indices then no longer line up with accounts_store.load()'s
            raw order, which this handler assumes.
            """
            current = accounts_store.load()
            item = current.pop(e.old_index)
            current.insert(e.new_index, item)
            accounts_store.save(current)
            refresh()

        account_list: ft.Control = ft.ReorderableListView(
            controls=[],
            expand=True,
            show_default_drag_handles=False,
            on_reorder=on_reorder,
            padding=scroll_padding(),
        )
    else:
        account_list = ft.ListView(
            controls=[], expand=True, spacing=list_spacing, padding=scroll_padding()
        )

    render_account_list(mounted=False)

    add_button = ft.IconButton(
        icon=ft.Icons.ADD,
        tooltip="Add account",
        on_click=open_add_account,
    )

    content = ft.Column(
        [
            ft.Row(
                [
                    text_title("Accounts"),
                    search_field,
                    add_button,
                ],
                spacing=SPACE_MD,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            account_list,
        ],
        expand=True,
    )

    page.run_task(backfill_missing_profiles)

    generation = (page.session.store.get(_GENERATION_KEY) or 0) + 1
    page.session.store.set(_GENERATION_KEY, generation)
    page.run_task(poll_status_loop, generation)

    return ft.View(
        route="/accounts",
        padding=0,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[build_layout(page, content)],
    )
