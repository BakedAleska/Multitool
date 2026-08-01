import sys

sys.dont_write_bytecode = True

import flet as ft  # noqa: E402

from app.logs import get_logger  # noqa: E402
from app.state import THEME_MODE_MAP, get_theme_mode  # noqa: E402
from app.ui.accounts import AccountsView  # noqa: E402
from app.ui.dashboard import DashboardView  # noqa: E402
from app.ui.settings import SettingsView  # noqa: E402
from app.ui.widgets import WidgetsView  # noqa: E402
from app.widgets.loader import get_enabled_widgets  # noqa: E402

logger = get_logger(__name__)


def main(page: ft.Page):
    def handle_loop_exception(loop, context):
        # page.run_task surfaces a background task's exception by re-raising
        # it inside a done-callback, which routes here rather than crashing
        # anything visibly — without this handler, a bug in a background
        # task (e.g. a widget shop refresh) fails completely silently.
        exception = context.get("exception")
        message = context.get("message", "Unhandled error in a background task")
        logger.error(message, exc_info=exception)

    page.session.connection.loop.set_exception_handler(handle_loop_exception)

    page.title = "Multitool"
    page.theme_mode = THEME_MODE_MAP[get_theme_mode(page)]
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

        try:
            if page.route == "/":
                page.views.append(DashboardView(page))
            elif page.route == "/accounts":
                page.views.append(AccountsView(page))
            elif page.route == "/widgets":
                page.views.append(WidgetsView(page))
            elif page.route == "/settings":
                page.views.append(SettingsView(page))
            elif page.route.startswith("/widgets/"):
                widget_id = page.route.removeprefix("/widgets/")
                widget = next((w for w in get_enabled_widgets(page) if w.id == widget_id), None)
                page.views.append(widget.build_view(page) if widget else DashboardView(page))
        except Exception:
            logger.exception("Failed to build view for route '%s'", page.route)
            page.views.clear()
            page.views.append(DashboardView(page))

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
