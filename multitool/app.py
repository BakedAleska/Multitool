"""Multitool's entrypoint: window setup and the top-level view router.

Run with ``python main.py`` at the repo root, or ``python -m multitool.app``.
Views are plain functions, such as `multitool.ui.dashboard.DashboardView`,
that take the `ft.Page` and return an `ft.View`. `route_change` below picks
which one to build for a route.
"""

import sys

sys.dont_write_bytecode = True

import flet as ft  # noqa: E402

from multitool.logs import get_logger  # noqa: E402
from multitool.state import get_active_theme, resolve_theme_mode  # noqa: E402
from multitool.theme import build_theme  # noqa: E402
from multitool.ui.accounts import AccountsView  # noqa: E402
from multitool.ui.dashboard import DashboardView  # noqa: E402
from multitool.ui.settings import SettingsView  # noqa: E402
from multitool.ui.widgets import WidgetsView  # noqa: E402
from multitool.widgets.loader import get_enabled_widgets  # noqa: E402
from multitool.widgets.process import stop_all_processes  # noqa: E402

logger = get_logger(__name__)


def main(page: ft.Page):
    """Configure the window and wire up routing for a new Flet session."""

    def handle_loop_exception(loop, context):
        """Log exceptions raised by `page.run_task`-scheduled background work.

        `page.run_task` surfaces a background task's exception by
        re-raising it inside a done-callback, which routes here rather
        than crashing anything visibly. Without this handler, a bug in a
        background task (e.g. a Catalogue refresh) fails completely
        silently.
        """
        exception = context.get("exception")
        message = context.get("message", "Unhandled error in a background task")
        logger.error(message, exc_info=exception)

    page.session.connection.loop.set_exception_handler(handle_loop_exception)

    def on_window_event(e: ft.WindowEvent):
        """Stop any process a widget started before the window closes.

        Without this, a widget backend such as an autoclicker's click
        loop would keep running as an orphaned process after the app
        window closes.
        """
        if e.type == ft.WindowEventType.CLOSE:
            stop_all_processes(page)

    page.window.on_event = on_window_event

    page.title = "Multitool"
    page.theme_mode = resolve_theme_mode(page)
    page.theme = build_theme(get_active_theme(page))
    page.window.width = 900
    page.window.height = 500
    page.window.resizable = True
    page.padding = 0

    def route_change(route):
        """Rebuild the view stack for the current route.

        Each navigation replaces the whole stack with one view, rather
        than pushing and popping. Falls back to the Dashboard if a view
        fails to build, so one broken route can't take down the app.
        """
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
        """Handle a back-navigation: drop the top view and re-sync the route."""
        page.views.pop()
        top_view = page.views[-1]
        page.go(top_view.route)

    page.on_route_change = route_change
    page.on_view_pop = view_pop

    page.route = "/"
    route_change(page.route)


def run():
    """Launch the Flet app."""
    ft.run(main, view=ft.AppView.FLET_APP)


if __name__ == "__main__":
    run()
