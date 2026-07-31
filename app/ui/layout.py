import flet as ft

from app.state import get_nav_position

ROUTES = ["/", "/settings"]

DESTINATIONS = [
    ft.NavigationRailDestination(
        icon=ft.Icons.DASHBOARD_OUTLINED,
        selected_icon=ft.Icons.DASHBOARD,
        label="Dashboard",
    ),
    ft.NavigationRailDestination(
        icon=ft.Icons.SETTINGS_OUTLINED,
        selected_icon=ft.Icons.SETTINGS,
        label="Settings",
    ),
]


def build_layout(page: ft.Page, content: ft.Control, selected_index: int) -> ft.Control:
    async def on_change(e: ft.ControlEvent):
        await page.push_route(ROUTES[e.control.selected_index])

    nav_rail = ft.NavigationRail(
        selected_index=selected_index,
        label_type=ft.NavigationRailLabelType.ALL,
        destinations=DESTINATIONS,
        on_change=on_change,
    )

    content_area = ft.Container(content=content, expand=True, padding=20)
    divider = ft.VerticalDivider(width=1)

    if get_nav_position(page) == "right":
        row_controls = [content_area, divider, nav_rail]
    else:
        row_controls = [nav_rail, divider, content_area]

    return ft.Row(row_controls, expand=True, spacing=0)
