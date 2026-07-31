import flet as ft

from app.ui.layout import build_layout


def DashboardView(page: ft.Page) -> ft.View:
    content = ft.Column(
        [
            ft.Text("Dashboard", size=24, weight=ft.FontWeight.BOLD),
        ]
    )

    return ft.View(
        route="/",
        padding=0,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[build_layout(page, content, selected_index=0)],
    )
