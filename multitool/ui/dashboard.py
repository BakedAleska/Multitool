"""The Dashboard: a Roblox-style continue card, an account row, and stats."""

import time

import flet as ft

from multitool.data import accounts as accounts_store
from multitool.logs import get_logger
from multitool.state import get_compact_mode, get_show_avatars, get_sort_order
from multitool.ui.accounts import sort_accounts
from multitool.ui.join_action import join_with_account
from multitool.ui.layout import build_layout
from multitool.ui.style import card_border, radius_hero
from multitool.widgets.loader import get_enabled_widgets

logger = get_logger(__name__)

HERO_AVATAR_SIZE = 72
ROW_AVATAR_SIZE = 48
COMPACT_ROW_AVATAR_SIZE = 36
ROW_CARD_WIDTH = 72


def _relative_time(timestamp: float) -> str:
    """Format a past Unix timestamp as a short relative string, like "2h ago"."""
    delta = time.time() - timestamp
    if delta < 60:
        return "just now"
    if delta < 3600:
        return f"{int(delta // 60)}m ago"
    if delta < 86400:
        return f"{int(delta // 3600)}h ago"
    return f"{int(delta // 86400)}d ago"


def _display_name(account: dict) -> str:
    """The name to show for an account: display name, or username."""
    return account.get("display_name") or account["name"]


def _avatar(account: dict, size: int) -> ft.Control:
    """A circular avatar image, or a placeholder icon if none is set."""
    avatar_url = account.get("avatar_url")
    content = (
        ft.Image(src=avatar_url, width=size, height=size, fit=ft.BoxFit.COVER)
        if avatar_url
        else ft.Icon(ft.Icons.PERSON, size=size * 0.6)
    )
    return ft.Container(
        content=content,
        width=size,
        height=size,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        border_radius=size / 2,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        alignment=ft.Alignment.CENTER,
    )


def _build_hero(page: ft.Page, account: dict, show_avatars: bool) -> ft.Control:
    """The "Continue as" card for one account, with a Join button."""
    last_played = account.get("last_played_at")
    subtitle = (
        f"Last played {_relative_time(last_played)}"
        if last_played
        else "No sessions yet"
    )

    row_controls: list[ft.Control] = []
    if show_avatars:
        row_controls.append(_avatar(account, HERO_AVATAR_SIZE))

    row_controls.append(
        ft.Column(
            [
                ft.Text("Continue as", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Text(_display_name(account), size=20, weight=ft.FontWeight.BOLD),
                ft.Text(subtitle, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            ],
            spacing=2,
            expand=True,
        )
    )

    row_controls.append(
        ft.FilledButton(
            "Join",
            icon=ft.Icons.PLAY_ARROW,
            on_click=lambda e, a=account: page.run_task(join_with_account, page, a),
        )
    )

    return ft.Container(
        content=ft.Row(row_controls, spacing=16, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=20,
        border=card_border(),
        border_radius=radius_hero(page),
    )


def _build_empty_hero(page: ft.Page) -> ft.Control:
    """The hero card shown when there are no accounts yet."""

    async def go_to_accounts():
        await page.push_route("/accounts")

    return ft.Container(
        content=ft.Row(
            [
                ft.Column(
                    [
                        ft.Text("No accounts added yet", size=20, weight=ft.FontWeight.BOLD),
                        ft.Text(
                            "Add a Roblox account to get started.",
                            size=12,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ],
                    spacing=2,
                    expand=True,
                ),
                ft.FilledButton(
                    "Add Account",
                    icon=ft.Icons.ADD,
                    on_click=lambda e: page.run_task(go_to_accounts),
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=20,
        border=card_border(),
        border_radius=radius_hero(page),
    )


def _build_account_row_card(
    page: ft.Page, account: dict, show_avatars: bool, avatar_size: int
) -> ft.Control:
    """One entry in the "Your Accounts" row. Click to join with it.

    No border or background: the avatar and spacing between entries are
    enough to separate them, without adding another boxed element next
    to the hero card.
    """
    column_controls: list[ft.Control] = []
    if show_avatars:
        column_controls.append(_avatar(account, avatar_size))
    column_controls.append(
        ft.Text(
            _display_name(account),
            size=12,
            weight=ft.FontWeight.W_500,
            text_align=ft.TextAlign.CENTER,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
    )

    return ft.Container(
        content=ft.Column(
            column_controls, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6
        ),
        width=ROW_CARD_WIDTH,
        padding=ft.Padding.symmetric(vertical=6),
        tooltip=f"Join as {_display_name(account)}",
        on_click=lambda e, a=account: page.run_task(join_with_account, page, a),
    )


def _widget_chip(page: ft.Page, widget_id: str, tile) -> ft.Control:
    """Wrap one widget-contributed DashboardTile with spacing, no chrome."""
    try:
        content = tile.build(page)
    except Exception:
        logger.exception("Widget '%s' dashboard tile '%s' failed to build", widget_id, tile.id)
        return ft.Container(width=0, height=0)

    return ft.Container(content=content, padding=ft.Padding.symmetric(horizontal=4))


def _stat_chip(text: str) -> ft.Control:
    """Muted, unboxed text, for the account and widget counts."""
    return ft.Text(text, size=12, color=ft.Colors.ON_SURFACE_VARIANT)


def DashboardView(page: ft.Page) -> ft.View:
    """The Dashboard screen.

    Shows a "Continue as" card for the most recently played account, or
    the most recently added one if none has been played yet. Below that,
    a scrollable row of all accounts, then a strip of stat chips for
    account and widget counts plus any widget-contributed tiles.
    """
    accounts = accounts_store.load()
    show_avatars = get_show_avatars(page)
    enabled_widgets = get_enabled_widgets(page)

    body: list[ft.Control] = [ft.Text("Dashboard", size=24, weight=ft.FontWeight.BOLD)]

    if not accounts:
        body.append(_build_empty_hero(page))
    else:
        played = [a for a in accounts if a.get("last_played_at")]
        continue_account = (
            max(played, key=lambda a: a["last_played_at"])
            if played
            else max(accounts, key=lambda a: a.get("added_at", 0))
        )
        body.append(_build_hero(page, continue_account, show_avatars))

        row_avatar_size = COMPACT_ROW_AVATAR_SIZE if get_compact_mode(page) else ROW_AVATAR_SIZE
        sorted_accounts = sort_accounts(accounts, get_sort_order(page))
        body.append(ft.Text("Your Accounts", size=14, weight=ft.FontWeight.W_600))
        body.append(
            ft.Row(
                [
                    _build_account_row_card(page, a, show_avatars, row_avatar_size)
                    for a in sorted_accounts
                ],
                scroll=ft.ScrollMode.AUTO,
                spacing=10,
            )
        )

    account_count = len(accounts)
    widget_count = len(enabled_widgets)
    stat_chips: list[ft.Control] = [
        _stat_chip(f"{account_count} account{'s' if account_count != 1 else ''}"),
        _stat_chip(f"{widget_count} widget{'s' if widget_count != 1 else ''} installed"),
    ]

    for widget in enabled_widgets:
        if widget.dashboard_tiles is None:
            continue
        try:
            tiles = widget.dashboard_tiles(page) or []
        except Exception:
            logger.exception("Widget '%s' dashboard_tiles() failed", widget.id)
            continue
        stat_chips.extend(_widget_chip(page, widget.id, tile) for tile in tiles)

    body.append(ft.Divider())
    body.append(ft.Row(stat_chips, spacing=4, wrap=True, run_spacing=4))

    content = ft.Column(body, spacing=16, expand=True)

    return ft.View(
        route="/",
        padding=0,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[build_layout(page, content)],
    )
