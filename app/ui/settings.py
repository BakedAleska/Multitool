"""The Settings screen."""

import asyncio

import flet as ft

from app.config import WIDGETS_DIR
from app.roblox.join import extract_place_id
from app.state import (
    THEME_MODE_MAP,
    get_compact_mode,
    get_custom_theme,
    get_custom_theme_source,
    get_nav_position,
    get_place_id,
    get_show_avatars,
    get_sort_order,
    get_theme_mode,
    set_compact_mode,
    set_custom_theme,
    set_nav_position,
    set_place_id,
    set_show_avatars,
    set_sort_order,
    set_theme_mode,
)
from app.theme import build_theme, parse_theme_input
from app.ui.layout import build_layout
from app.ui.toast import show_toast


def SettingsView(page: ft.Page) -> ft.View:
    """The Settings screen: General, Accounts, and Widgets tabs.

    The Widgets tab only shows the manual install path. Browsing and
    installing widgets happens on the Widgets screen itself.
    """

    def on_position_change(e: ft.Event[ft.RadioGroup]):
        if e.control.value is not None:
            set_nav_position(page, e.control.value)
        page.views[-1] = SettingsView(page)
        page.update()

    def on_theme_mode_change(e: ft.Event[ft.RadioGroup]):
        """Switch between System, Light, Dark, and a saved Custom theme."""
        if e.control.value is not None:
            mode = e.control.value
            set_theme_mode(page, mode)
            page.theme_mode = THEME_MODE_MAP[mode]
            page.theme = build_theme(get_custom_theme(page) if mode == "custom" else None)
        page.views[-1] = SettingsView(page)
        page.update()

    def on_show_avatars_change(e: ft.Event[ft.Switch]):
        set_show_avatars(page, e.control.value)

    def on_sort_order_change(e: ft.Event[ft.RadioGroup]):
        if e.control.value is not None:
            set_sort_order(page, e.control.value)

    def on_compact_mode_change(e: ft.Event[ft.Switch]):
        set_compact_mode(page, e.control.value)

    def on_place_id_blur(e: ft.Event[ft.TextField]):
        """Parse a pasted place URL or id, and save the extracted id."""
        place_id = extract_place_id(e.control.value or "")
        if not place_id:
            show_toast(
                page,
                "Couldn't find a place ID in the pasted text. Did you include the full game link?",
            )
            return
        set_place_id(page, place_id)
        e.control.value = place_id
        e.control.update()

    async def copy_widgets_path(e: ft.Event[ft.IconButton]):
        """Copy the manual widget install path to the clipboard."""
        await page.clipboard.set(str(WIDGETS_DIR))
        show_toast(page, "Copied.")

    async def on_apply_theme(e: ft.Event[ft.FilledButton]):
        """Parse the pasted theme or link, save it, and select Custom.

        Applying a theme also switches Appearance to Custom, since
        pasting one and applying it means the user wants to see it now.
        """
        raw_input = (theme_field.value or "").strip()
        if not raw_input:
            _reset_theme()
            show_toast(page, "Theme cleared.")
            return

        theme, error = await asyncio.to_thread(parse_theme_input, raw_input)
        if error:
            show_toast(page, error)
            return

        set_custom_theme(page, theme, raw_input)
        set_theme_mode(page, "custom")
        page.theme_mode = THEME_MODE_MAP["custom"]
        page.theme = build_theme(theme)
        page.views[-1] = SettingsView(page)
        page.update()
        show_toast(page, "Theme applied.")

    def on_clear_theme(e: ft.Event[ft.TextButton]):
        """Remove the saved theme and go back to the default look."""
        _reset_theme()

    def _reset_theme():
        """Clear the saved theme and fall back to System appearance."""
        set_custom_theme(page, None, "")
        set_theme_mode(page, "system")
        page.theme_mode = THEME_MODE_MAP["system"]
        page.theme = build_theme(None)
        page.views[-1] = SettingsView(page)
        page.update()

    theme_field = ft.TextField(
        value=get_custom_theme_source(page),
        hint_text=(
            '{"accent_color": "#7C3AED", "corner_radius": 4, '
            '"background_image": "https://example.com/bg.png", '
            '"background_opacity": 0.4}'
        ),
        hint_style=ft.TextStyle(
            color=ft.Colors.with_opacity(0.4, ft.Colors.ON_SURFACE_VARIANT), italic=True
        ),
        multiline=True,
        min_lines=2,
        max_lines=6,
        width=320,
    )

    appearance_options = [
        ft.Radio(value="system", label="System"),
        ft.Radio(value="light", label="Light"),
        ft.Radio(value="dark", label="Dark"),
    ]
    if get_custom_theme(page) is not None:
        appearance_options.append(ft.Radio(value="custom", label="Custom"))

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
                content=ft.Row(appearance_options, wrap=True),
            ),
            ft.Text("Custom Theme", weight=ft.FontWeight.W_500),
            ft.Text(
                "Paste a theme's JSON, or a link to one, to set an accent color, "
                "corner rounding, a font, and a background image. Applying a "
                "theme selects Custom above. Leave it blank to clear it.",
                size=12,
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
            theme_field,
            ft.Row(
                [
                    ft.FilledButton("Apply", on_click=on_apply_theme),
                    ft.TextButton("Clear", on_click=on_clear_theme),
                ]
            ),
        ],
        spacing=12,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        scroll=ft.ScrollMode.AUTO,
    )

    accounts_tab = ft.Column(
        [
            ft.Row(
                [
                    ft.Column(
                        [
                            ft.Text("Show avatars", weight=ft.FontWeight.W_500),
                            ft.Text(
                                "Show each account's avatar in the list.",
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
                                "Hide notes in the accounts list for a more compact view.",
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
                "The place that opens when you press Join. Paste a roblox.com game "
                "link, or just the numeric ID.",
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
        scroll=ft.ScrollMode.AUTO,
    )

    WIDGETS_DIR.mkdir(parents=True, exist_ok=True)

    widgets_tab = ft.Column(
        [
            ft.Text(
                "Widgets are optional and not bundled with the app. To add one "
                "manually, place its folder here. Install and enable them from the "
                "Widgets screen.",
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
        scroll=ft.ScrollMode.AUTO,
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
