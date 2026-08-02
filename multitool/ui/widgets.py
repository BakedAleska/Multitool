"""The Widgets screen: the Catalogue banner and the grid of installed widgets."""

import asyncio

import flet as ft

from multitool.state import get_disabled_widgets, set_widget_enabled
from multitool.ui.layout import build_layout
from multitool.ui.style import card_border, radius_card
from multitool.ui.toast import show_toast
from multitool.widgets.catalog import (
    CatalogEntry,
    fetch_registry,
    get_cached_registry,
    set_cached_registry,
)
from multitool.widgets.installer import (
    WidgetInstallError,
    install_widget,
    is_installing,
    mark_installing,
    unmark_installing,
)
from multitool.widgets.loader import discover_widgets

_CATALOGUE_FETCHED_KEY = "_widget_catalogue_fetched"
_CATALOGUE_ERROR_KEY = "_widget_catalogue_error"
_SETTINGS_FOCUS_WIDGET_KEY = "_settings_focus_widget_id"


def WidgetsView(page: ft.Page) -> ft.View:
    """The Widgets screen.

    The Catalogue is fetched once per session, on the first build. The
    fetched flag is read fresh at the top of every build and set inside
    background_refresh_catalogue itself, before it calls refresh(). This
    guard matters: refresh() rebuilds this view, so an unconditional
    fetch here would trigger another fetch on every rebuild, without end.
    """

    def refresh():
        """Rebuild this view in place, if it's still the one on screen."""
        if not page.views or page.views[-1].route != "/widgets":
            return
        page.views[-1] = WidgetsView(page)
        page.update()

    def on_toggle(widget_id: str, enable: bool):
        """Enable or disable one installed widget."""
        set_widget_enabled(page, widget_id, enable)
        refresh()

    async def open_widget_settings(widget_id: str):
        """Jump to Settings -> Widgets, focused on one widget's section."""
        page.session.store.set(_SETTINGS_FOCUS_WIDGET_KEY, widget_id)
        await page.push_route("/settings")

    async def on_install(entry: CatalogEntry):
        """Download and install one Catalogue entry."""
        mark_installing(page, entry.id)
        refresh()
        try:
            await asyncio.to_thread(install_widget, entry)
            set_widget_enabled(page, entry.id, True)
        except WidgetInstallError as e:
            show_toast(page, str(e))
        finally:
            unmark_installing(page, entry.id)
            refresh()

    async def background_refresh_catalogue():
        """Fetch the Catalogue, then refresh this view.

        See WidgetsView's docstring for the guard that keeps this from
        running more than once per session.
        """
        entries, error = await asyncio.to_thread(fetch_registry)
        if error is None:
            set_cached_registry(page, entries)
        page.session.store.set(_CATALOGUE_FETCHED_KEY, True)
        page.session.store.set(_CATALOGUE_ERROR_KEY, error)
        refresh()

    widgets, load_errors = discover_widgets()
    disabled_ids = set(get_disabled_widgets(page))
    local_ids = {w.id for w in widgets}

    def build_installed_square(widget) -> ft.Control:
        """Build one installed widget's square. Click to toggle enabled.

        A widget with `build_settings` set gets a small settings button in
        the corner that jumps to its section under Settings -> Widgets,
        instead of opening settings embedded on this square.
        """
        enabled = widget.id not in disabled_ids
        status = "enabled" if enabled else "disabled"
        tooltip = f"{widget.name}: {status}"
        if widget.description:
            tooltip = f"{widget.name} ({status}): {widget.description}"

        logo = (
            ft.Image(src=widget.logo, width=28, height=28, fit=ft.BoxFit.CONTAIN)
            if widget.logo
            else ft.Icon(widget.icon or ft.Icons.EXTENSION, size=28)
        )

        square = ft.Container(
            content=ft.Column(
                [
                    logo,
                    ft.Text(
                        widget.name,
                        size=10,
                        text_align=ft.TextAlign.CENTER,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=4,
            ),
            width=76,
            height=76,
            padding=8,
            border=card_border(),
            border_radius=radius_card(page),
            opacity=1.0 if enabled else 0.4,
            tooltip=tooltip,
            on_click=lambda e, wid=widget.id, was_on=enabled: on_toggle(wid, not was_on),
        )

        if widget.build_settings is None:
            return square

        settings_button = ft.Container(
            content=ft.IconButton(
                icon=ft.Icons.SETTINGS,
                icon_size=14,
                tooltip=f"{widget.name} settings",
                on_click=lambda e, wid=widget.id: page.run_task(open_widget_settings, wid),
            ),
            top=-4,
            right=-4,
        )
        return ft.Stack([square, settings_button], width=76, height=76)

    def build_catalogue_square(entry: CatalogEntry) -> ft.Control:
        """Build one Catalogue entry's square. Click to install it."""
        installing = is_installing(page, entry.id)
        icon = (getattr(ft.Icons, entry.icon, None) if entry.icon else None) or ft.Icons.EXTENSION
        return ft.Container(
            content=ft.Column(
                [
                    ft.ProgressRing(width=20, height=20, stroke_width=2)
                    if installing
                    else ft.Icon(icon, size=28),
                    ft.Text(
                        entry.name,
                        size=10,
                        text_align=ft.TextAlign.CENTER,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=4,
            ),
            width=76,
            height=76,
            padding=8,
            border=card_border(),
            border_radius=radius_card(page),
            opacity=0.5 if installing else 1.0,
            tooltip="Installing…" if installing else f"{entry.name}: {entry.description}",
            on_click=(
                None if installing else (lambda e, ent=entry: page.run_task(on_install, ent))
            ),
        )

    catalogue_fetched = page.session.store.get(_CATALOGUE_FETCHED_KEY)
    catalogue_error = page.session.store.get(_CATALOGUE_ERROR_KEY)
    catalogue_entries = [e for e in get_cached_registry(page) if e.id not in local_ids]

    if not catalogue_fetched:
        catalogue_content: ft.Control = ft.Text(
            "Loading…", italic=True, size=12, color=ft.Colors.ON_SURFACE_VARIANT
        )
    elif catalogue_error:
        catalogue_content = ft.Text(
            f"Couldn't reach the catalogue. Is your connection working? ({catalogue_error})",
            size=12,
            color=ft.Colors.ERROR,
        )
    elif catalogue_entries:
        catalogue_content = ft.Row(
            [build_catalogue_square(e) for e in catalogue_entries],
            scroll=ft.ScrollMode.AUTO,
            spacing=8,
        )
    else:
        catalogue_content = ft.Text(
            "No new widgets available.", italic=True, size=12, color=ft.Colors.ON_SURFACE_VARIANT
        )

    catalogue_banner = ft.Column(
        [
            ft.Text("Catalogue", size=14, weight=ft.FontWeight.W_600),
            catalogue_content,
        ],
        spacing=8,
    )

    body: list[ft.Control] = [catalogue_banner, ft.Divider()]

    if widgets:
        body.append(
            ft.Row(
                [build_installed_square(w) for w in widgets],
                wrap=True,
                spacing=8,
                run_spacing=8,
            )
        )
    else:
        body.append(
            ft.Text(
                "No widgets installed. Install one from the Catalogue above, or add one "
                "manually from Settings.",
                italic=True,
                color=ft.Colors.ON_SURFACE_VARIANT,
            )
        )

    if load_errors:
        for folder_name, error in load_errors:
            body.append(
                ft.Text(
                    f"{folder_name} failed to load. Did you edit its widget.py recently? ({error})",
                    size=12,
                    color=ft.Colors.ERROR,
                )
            )

    content = ft.Column(
        [
            ft.Text("Widgets", size=24, weight=ft.FontWeight.BOLD),
            *body,
        ],
        spacing=16,
        expand=True,
    )

    if not catalogue_fetched:
        page.run_task(background_refresh_catalogue)

    return ft.View(
        route="/widgets",
        padding=0,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[build_layout(page, content)],
    )
