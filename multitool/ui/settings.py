"""The Settings screen."""

import asyncio

import flet as ft

from multitool.config import WIDGETS_DIR
from multitool.roblox.join import extract_place_id
from multitool.state import (
    BUILT_IN_THEME_MODES,
    get_active_theme,
    get_compact_mode,
    get_installed_themes,
    get_nav_position,
    get_place_id,
    get_show_avatars,
    get_sort_order,
    get_theme_mode,
    install_theme,
    remove_theme,
    resolve_theme_mode,
    set_compact_mode,
    set_nav_position,
    set_place_id,
    set_show_avatars,
    set_sort_order,
    set_theme_mode,
)
from multitool.theme import build_theme, parse_theme_input
from multitool.ui.layout import build_layout
from multitool.ui.style import card_border, radius_card
from multitool.ui.toast import show_toast
from multitool.widgets.loader import discover_widgets

_SETTINGS_FOCUS_WIDGET_KEY = "_settings_focus_widget_id"


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
        """Switch Appearance between System, Light, Dark, or an installed theme."""
        if e.control.value is not None:
            set_theme_mode(page, e.control.value)
            page.theme_mode = resolve_theme_mode(page)
            page.theme = build_theme(get_active_theme(page))
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

    async def on_install_theme(e: ft.Event[ft.FilledButton]):
        """Parse the pasted theme or link and install it, using its "name"
        field, as the active appearance.

        Installing a theme also switches Appearance to it, since pasting
        one and installing it means the user wants to see it now.
        """
        raw_input = (theme_field.value or "").strip()
        if not raw_input:
            show_toast(page, "Paste a theme's JSON, or a link to one, before installing.")
            return

        theme, error = await asyncio.to_thread(parse_theme_input, raw_input)
        if error:
            show_toast(page, error)
            return

        theme_id = install_theme(page, theme, raw_input)
        set_theme_mode(page, theme_id)
        page.theme_mode = resolve_theme_mode(page)
        page.theme = build_theme(theme)
        page.views[-1] = SettingsView(page)
        page.update()
        show_toast(page, f'"{theme["name"]}" installed and applied.')

    def on_remove_theme(theme_id: str):
        def handler(e: ft.Event[ft.IconButton]):
            was_active = get_theme_mode(page) == theme_id
            remove_theme(page, theme_id)
            if was_active:
                page.theme_mode = resolve_theme_mode(page)
                page.theme = build_theme(None)
            page.views[-1] = SettingsView(page)
            page.update()
            show_toast(page, "Theme removed.")

        return handler

    theme_field = ft.TextField(
        hint_text=(
            '{"name": "Seafoam", "accent_color": "#7C3AED", '
            '"secondary_color": "#22D3AA", "corner_radius": 4, '
            '"brightness": "dark", '
            '"background_image": "https://example.com/bg.png", '
            '"background_opacity": 0.4}'
        ),
        hint_style=ft.TextStyle(
            color=ft.Colors.with_opacity(0.4, ft.Colors.ON_SURFACE_VARIANT), italic=True
        ),
        multiline=True,
        min_lines=2,
        max_lines=6,
        expand=True,
    )

    installed_themes = get_installed_themes(page)

    appearance_options = [
        ft.Radio(value="system", label="System"),
        ft.Radio(value="light", label="Light"),
        ft.Radio(value="dark", label="Dark"),
    ]
    for theme in installed_themes:
        appearance_options.append(ft.Radio(value=theme["id"], label=theme["name"]))

    installed_theme_rows: list[ft.Control] = []
    for theme in installed_themes:
        installed_theme_rows.append(
            ft.Row(
                [
                    ft.Text(theme["name"], expand=True),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        icon_size=18,
                        tooltip=f'Remove "{theme["name"]}"',
                        on_click=on_remove_theme(theme["id"]),
                    ),
                ]
            )
        )

    valid_appearance_values = BUILT_IN_THEME_MODES.keys() | {t["id"] for t in installed_themes}
    appearance_value = get_theme_mode(page) if get_theme_mode(page) in valid_appearance_values \
        else "system"

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
                value=appearance_value,
                on_change=on_theme_mode_change,
                content=ft.Row(appearance_options, wrap=True),
            ),
            *(
                [
                    ft.Text("Installed Themes", weight=ft.FontWeight.W_500),
                    ft.Column(installed_theme_rows, spacing=4),
                ]
                if installed_theme_rows
                else []
            ),
            ft.Text("Install a Theme", weight=ft.FontWeight.W_500),
            ft.Text(
                "Paste a theme's JSON, or a link to one, to set a name, colors, "
                "corner rounding, a font, and a background image. Installing "
                "adds it to Appearance above.",
                size=12,
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
            theme_field,
            ft.FilledButton("Install", on_click=on_install_theme),
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

    focus_widget_id = page.session.store.get(_SETTINGS_FOCUS_WIDGET_KEY)
    if page.session.store.contains_key(_SETTINGS_FOCUS_WIDGET_KEY):
        page.session.store.remove(_SETTINGS_FOCUS_WIDGET_KEY)

    installed_widgets, _load_errors = discover_widgets()

    widget_settings_sections: list[ft.Control] = []
    for widget in installed_widgets:
        if widget.build_settings is None:
            continue
        widget_settings_sections.append(
            ft.Container(
                content=ft.Column(
                    [
                        ft.Text(widget.name, size=16, weight=ft.FontWeight.W_600),
                        widget.build_settings(page),
                    ],
                    spacing=12,
                ),
                padding=12,
                border=(
                    ft.Border.all(2, ft.Colors.PRIMARY)
                    if widget.id == focus_widget_id
                    else card_border()
                ),
                border_radius=radius_card(page),
            )
        )

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
            *widget_settings_sections,
        ],
        spacing=16,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        scroll=ft.ScrollMode.AUTO,
    )

    content = ft.Column(
        [
            ft.Text("Settings", size=24, weight=ft.FontWeight.BOLD),
            ft.Tabs(
                length=3,
                selected_index=2 if focus_widget_id else 0,
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
