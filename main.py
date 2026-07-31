import flet as ft

from app.ui.dashboard import DashboardView
from app.ui.settings import SettingsView


def main(page: ft.Page):
    page.title = "Multitool"
    page.theme_mode = ft.ThemeMode.SYSTEM
    page.theme = ft.Theme(
        page_transitions=ft.PageTransitionsTheme(
            windows=ft.PageTransitionTheme.NONE,
            macos=ft.PageTransitionTheme.NONE,
            linux=ft.PageTransitionTheme.NONE,
            android=ft.PageTransitionTheme.NONE,
            ios=ft.PageTransitionTheme.NONE,
        )
    )
    page.window.width = 700
    page.window.height = 500
    page.window.resizable = True
    page.padding = 0

    def route_change(route):
        page.views.clear()

        if page.route == "/":
            page.views.append(DashboardView(page))
        elif page.route == "/settings":
            page.views.append(SettingsView(page))

        page.update()

    def view_pop(view):
        page.views.pop()
        top_view = page.views[-1]
        page.go(top_view.route)

    page.on_route_change = route_change
    page.on_view_pop = view_pop

    page.route = "/"
    route_change(page.route)


if __name__ == "__main__":
    ft.run(main, view=ft.AppView.FLET_APP)