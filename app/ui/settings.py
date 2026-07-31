import flet as ft

from app.state import get_nav_position, set_nav_position
from app.ui.layout import build_layout


def SettingsView(page: ft.Page) -> ft.View:
    def on_position_change(e: ft.ControlEvent):
        set_nav_position(page, e.control.value)
        page.views[-1] = SettingsView(page)
        page.update()

    content = ft.Column(
        [
            ft.Text("Settings", size=24, weight=ft.FontWeight.BOLD),
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
        ]
    )

    return ft.View(
        route="/settings",
        padding=0,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[build_layout(page, content, selected_index=1)],
    )
