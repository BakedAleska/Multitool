"""The shared page shell: nav rail plus content area, used by every view."""

import flet as ft

from multitool.state import get_active_theme, get_nav_position, is_named_theme_active
from multitool.theme import BACKGROUND_FIT_MAP
from multitool.ui.style import radius_card
from multitool.widgets.loader import get_enabled_widgets

CORE_ROUTES = ["/", "/accounts", "/widgets", "/settings"]

CORE_DESTINATIONS = [
    ft.NavigationRailDestination(
        icon=ft.Icons.DASHBOARD_OUTLINED,
        selected_icon=ft.Icons.DASHBOARD,
        label="Dashboard",
    ),
    ft.NavigationRailDestination(
        icon=ft.Icons.PEOPLE_OUTLINE,
        selected_icon=ft.Icons.PEOPLE,
        label="Accounts",
    ),
    ft.NavigationRailDestination(
        icon=ft.Icons.EXTENSION_OUTLINED,
        selected_icon=ft.Icons.EXTENSION,
        label="Widgets",
    ),
    ft.NavigationRailDestination(
        icon=ft.Icons.SETTINGS_OUTLINED,
        selected_icon=ft.Icons.SETTINGS,
        label="Settings",
    ),
]


def widget_route(widget_id: str) -> str:
    """The route a widget's own view is built at."""
    return f"/widgets/{widget_id}"


def build_layout(page: ft.Page, content: ft.Control) -> ft.Control:
    """Wrap page content in the shared nav rail and content area.

    Every view calls this to get the same nav rail, so a new view only
    needs to build its own content.

    Enabled widgets are listed below the core destinations, separated by
    a divider, using NavigationRail's trailing slot. By default that
    slot flows directly after the destination list instead of pinning to
    the bottom of the window, which is what gives the "core items, then
    a line, then installed widgets" layout.
    """
    current_route = page.route
    core_selected = CORE_ROUTES.index(current_route) if current_route in CORE_ROUTES else None

    async def on_core_change(e: ft.Event[ft.NavigationRail]):
        if e.control.selected_index is not None:
            await page.push_route(CORE_ROUTES[e.control.selected_index])

    async def go_to_widget(widget_id: str):
        await page.push_route(widget_route(widget_id))

    widgets_section = None
    widgets = get_enabled_widgets(page)
    if widgets:
        rows: list[ft.Control] = [ft.Divider(height=1)]
        for widget in widgets:
            selected = current_route == widget_route(widget.id)
            icon = (widget.selected_icon if selected else None) or widget.icon or ft.Icons.EXTENSION
            rows.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Icon(icon),
                            ft.Text(widget.name, size=12),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=4,
                    ),
                    padding=ft.Padding.symmetric(vertical=8),
                    border_radius=radius_card(page),
                    bgcolor=ft.Colors.SECONDARY_CONTAINER if selected else None,
                    on_click=lambda e, wid=widget.id: page.run_task(go_to_widget, wid),
                )
            )
        widgets_section = ft.Column(rows, spacing=4)

    nav_rail = ft.NavigationRail(
        selected_index=core_selected,
        label_type=ft.NavigationRailLabelType.ALL,
        destinations=CORE_DESTINATIONS,
        trailing=widgets_section,
        on_change=on_core_change,
    )

    content_area = ft.Container(content=content, expand=True, padding=20)
    divider = ft.VerticalDivider(width=1)

    if get_nav_position(page) == "right":
        row_controls = [content_area, divider, nav_rail]
    else:
        row_controls = [nav_rail, divider, content_area]

    row = ft.Row(row_controls, expand=True, spacing=0)

    background_image = _background_image(page)
    if background_image is None:
        return row

    return ft.Stack([background_image, row], expand=True)


def _background_image(page: ft.Page) -> ft.Control | None:
    """The active theme's background image, or None if it has none."""
    if not is_named_theme_active(page):
        return None

    theme = get_active_theme(page)
    src = theme.get("background_image") if theme else None
    if not src:
        return None

    return ft.Container(
        image=ft.DecorationImage(
            src=src,
            fit=BACKGROUND_FIT_MAP.get(theme.get("background_fit"), ft.BoxFit.COVER),
            opacity=theme.get("background_opacity", 1.0),
        ),
        expand=True,
    )
