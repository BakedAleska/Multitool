import flet as ft

from app.config import WIDGETS_DIR
from app.roblox.join import extract_place_id
from app.state import (
    THEME_MODE_MAP,
    get_compact_mode,
    get_nav_position,
    get_place_id,
    get_show_avatars,
    get_sort_order,
    get_theme_mode,
    set_compact_mode,
    set_nav_position,
    set_place_id,
    set_show_avatars,
    set_sort_order,
    set_theme_mode,
)
from app.ui.layout import build_layout
from app.ui.toast import show_toast


def SettingsView(page: ft.Page) -> ft.View:
    def on_position_change(e: ft.Event[ft.RadioGroup]):
        if e.control.value is not None:
            set_nav_position(page, e.control.value)
        page.views[-1] = SettingsView(page)
        page.update()

    def on_theme_mode_change(e: ft.Event[ft.RadioGroup]):
        if e.control.value is not None:
            set_theme_mode(page, e.control.value)
            page.theme_mode = THEME_MODE_MAP[e.control.value]
        page.update()

    def on_show_avatars_change(e: ft.Event[ft.Switch]):
        set_show_avatars(page, e.control.value)

    def on_sort_order_change(e: ft.Event[ft.RadioGroup]):
        if e.control.value is not None:
            set_sort_order(page, e.control.value)

    def on_compact_mode_change(e: ft.Event[ft.Switch]):
        set_compact_mode(page, e.control.value)

    def on_place_id_blur(e: ft.Event[ft.TextField]):
        place_id = extract_place_id(e.control.value or "")
        if not place_id:
            show_toast(page, "Couldn't find a place ID in that text.")
            return
        set_place_id(page, place_id)
        e.control.value = place_id
        e.control.update()

    async def copy_widgets_path(e: ft.Event[ft.IconButton]):
        await page.clipboard.set(str(WIDGETS_DIR))
        show_toast(page, "Copied.")

    general_tab = ft.Column(
        [
            ft.Text("Sidebar position", weight=ft.FontWeight.W_500),
            ft.RadioGroup(
                value=get_nav_position(page),
                on_change=on_position_change,
                content=ft.Row(
                    [
                        ft.Radio(value="left", label="Left"),
                        ft.Radio(value="right", label="Right"),
                    ]
                ),
            ),
            ft.Text("Appearance", weight=ft.FontWeight.W_500),
            ft.RadioGroup(
                value=get_theme_mode(page),
                on_change=on_theme_mode_change,
                content=ft.Row(
                    [
                        ft.Radio(value="system", label="System"),
                        ft.Radio(value="light", label="Light"),
                        ft.Radio(value="dark", label="Dark"),
                    ]
                ),
            ),
        ],
        spacing=12,
    )

    accounts_tab = ft.Column(
        [
            ft.Row(
                [
                    ft.Column(
                        [
                            ft.Text("Show avatars", weight=ft.FontWeight.W_500),
                            ft.Text(
                                "Display each account's avatar in the accounts list.",
                                size=12,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    ft.Switch(
                        value=get_show_avatars(page),
                        on_change=on_show_avatars_change,
                    ),
                ],
            ),
            ft.Row(
                [
                    ft.Column(
                        [
                            ft.Text("Compact mode", weight=ft.FontWeight.W_500),
                            ft.Text(
                                "Hide notes in the accounts list for a denser view.",
                                size=12,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    ft.Switch(
                        value=get_compact_mode(page),
                        on_change=on_compact_mode_change,
                    ),
                ],
            ),
            ft.Text("Sort order", weight=ft.FontWeight.W_500),
            ft.RadioGroup(
                value=get_sort_order(page),
                on_change=on_sort_order_change,
                content=ft.Row(
                    [
                        ft.Radio(value="date_added", label="Date added"),
                        ft.Radio(value="alphabetical", label="Alphabetical"),
                        ft.Radio(value="manual", label="Manual"),
                    ]
                ),
            ),
            ft.Text("Place ID", weight=ft.FontWeight.W_500),
            ft.Text(
                "The place the play button on the accounts list joins. Paste a full "
                "roblox.com link or just the numeric ID.",
                size=12,
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
            ft.TextField(
                value=get_place_id(page),
                hint_text="https://www.roblox.com/games/1818/... or 1818",
                on_blur=on_place_id_blur,
            ),
        ],
        spacing=12,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )

    WIDGETS_DIR.mkdir(parents=True, exist_ok=True)

    widgets_tab = ft.Column(
        [
            ft.Text(
                "Widgets are optional extensions that add their own section to "
                "the app. They aren't bundled — to manually add one, place its "
                "folder here (see the Widgets section to install/enable it):",
                size=12,
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
            ft.Row(
                [
                    ft.Text(str(WIDGETS_DIR), size=12, selectable=True, expand=True),
                    ft.IconButton(
                        icon=ft.Icons.COPY,
                        icon_size=16,
                        tooltip="Copy path",
                        on_click=copy_widgets_path,
                    ),
                ]
            ),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )

    content = ft.Column(
        [
            ft.Text("Settings", size=24, weight=ft.FontWeight.BOLD),
            ft.Tabs(
                length=3,
                expand=True,
                content=ft.Column(
                    expand=True,
                    controls=[
                        ft.TabBar(
                            tabs=[
                                ft.Tab(label="General"),
                                ft.Tab(label="Accounts"),
                                ft.Tab(label="Widgets"),
                            ]
                        ),
                        ft.TabBarView(
                            expand=True,
                            controls=[
                                ft.Container(content=general_tab, padding=ft.Padding.only(top=16)),
                                ft.Container(content=accounts_tab, padding=ft.Padding.only(top=16)),
                                ft.Container(content=widgets_tab, padding=ft.Padding.only(top=16)),
                            ],
                        ),
                    ],
                ),
            ),
        ],
        expand=True,
    )

    return ft.View(
        route="/settings",
        padding=0,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[build_layout(page, content)],
    )
