import flet as ft

from app.state import get_nav_position
from app.widgets.loader import get_enabled_widgets

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
    return f"/widgets/{widget_id}"


def build_layout(page: ft.Page, content: ft.Control) -> ft.Control:
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
        # Divider + one row per widget, rendered via NavigationRail's
        # `trailing` slot — which (pin_trailing_to_bottom defaults to
        # False) flows directly after the destination list rather than
        # being pinned to the window's bottom edge. This is what actually
        # produces "default items, then a line, then installed widgets."
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
                    border_radius=8,
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

    return ft.Row(row_controls, expand=True, spacing=0)
