import asyncio

import flet as ft

from app.state import get_disabled_widgets, set_widget_enabled
from app.ui.layout import build_layout
from app.ui.toast import show_toast
from app.widgets.catalog import (
    CatalogEntry,
    fetch_registry,
    get_cached_registry,
    set_cached_registry,
)
from app.widgets.installer import (
    WidgetInstallError,
    install_widget,
    is_installing,
    mark_installing,
    unmark_installing,
)
from app.widgets.loader import discover_widgets

_SHOP_FETCHED_KEY = "_widget_shop_fetched"
_SHOP_ERROR_KEY = "_widget_shop_error"


def WidgetsView(page: ft.Page) -> ft.View:
    def refresh():
        if not page.views or page.views[-1].route != "/widgets":
            return
        page.views[-1] = WidgetsView(page)
        page.update()

    def on_toggle(widget_id: str, enable: bool):
        set_widget_enabled(page, widget_id, enable)
        refresh()

    async def on_install(entry: CatalogEntry):
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

    async def background_refresh_shop():
        entries, error = await asyncio.to_thread(fetch_registry)
        if error is None:
            set_cached_registry(page, entries)
        page.session.store.set(_SHOP_FETCHED_KEY, True)
        page.session.store.set(_SHOP_ERROR_KEY, error)
        refresh()

    widgets, load_errors = discover_widgets()
    disabled_ids = set(get_disabled_widgets(page))
    local_ids = {w.id for w in widgets}

    def build_widget_card(widget) -> ft.Control:
        installed = widget.id not in disabled_ids
        return ft.Container(
            content=ft.Column(
                [
                    ft.Icon(widget.icon or ft.Icons.EXTENSION, size=32),
                    ft.Text(
                        widget.name,
                        weight=ft.FontWeight.W_500,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.FilledButton(
                        "Installed" if installed else "Download",
                        icon=ft.Icons.CHECK if installed else ft.Icons.DOWNLOAD,
                        on_click=lambda e, wid=widget.id, was_on=installed: on_toggle(
                            wid, not was_on
                        ),
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
            ),
            width=140,
            padding=16,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=12,
        )

    def build_shop_card(entry: CatalogEntry) -> ft.Control:
        installing = is_installing(page, entry.id)
        icon = (getattr(ft.Icons, entry.icon, None) if entry.icon else None) or ft.Icons.EXTENSION
        return ft.Container(
            content=ft.Column(
                [
                    ft.Icon(icon, size=32),
                    ft.Text(
                        entry.name,
                        weight=ft.FontWeight.W_500,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        entry.description,
                        size=11,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.FilledButton(
                        "Installing…" if installing else "Install",
                        icon=None if installing else ft.Icons.DOWNLOAD,
                        disabled=installing,
                        on_click=(
                            None
                            if installing
                            else (lambda e, ent=entry: page.run_task(on_install, ent))
                        ),
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=6,
            ),
            width=140,
            padding=16,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=12,
        )

    body: list[ft.Control] = [ft.Text("Your Widgets", size=16, weight=ft.FontWeight.W_600)]

    if widgets:
        body.append(
            ft.Row(
                [build_widget_card(w) for w in widgets],
                wrap=True,
                spacing=12,
                run_spacing=12,
            )
        )
    else:
        body.append(
            ft.Text(
                "No widgets found. See Settings → Widgets for where to add one.",
                italic=True,
                color=ft.Colors.ON_SURFACE_VARIANT,
            )
        )

    if load_errors:
        for folder_name, error in load_errors:
            body.append(
                ft.Text(
                    f"{folder_name}: failed to load — {error}",
                    size=12,
                    color=ft.Colors.ERROR,
                )
            )

    body.append(ft.Divider())
    body.append(ft.Text("Widget Shop", size=16, weight=ft.FontWeight.W_600))

    shop_fetched = page.session.store.get(_SHOP_FETCHED_KEY)
    shop_error = page.session.store.get(_SHOP_ERROR_KEY)
    shop_entries = [e for e in get_cached_registry(page) if e.id not in local_ids]

    if not shop_fetched:
        body.append(
            ft.Text("Loading shop…", italic=True, color=ft.Colors.ON_SURFACE_VARIANT)
        )
    else:
        if shop_entries:
            body.append(
                ft.Row(
                    [build_shop_card(e) for e in shop_entries],
                    wrap=True,
                    spacing=12,
                    run_spacing=12,
                )
            )
        elif not shop_error:
            body.append(
                ft.Text(
                    "Nothing new in the shop right now.",
                    italic=True,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                )
            )
        if shop_error:
            body.append(
                ft.Text(
                    f"Couldn't reach the widget shop — {shop_error}",
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

    page.run_task(background_refresh_shop)

    return ft.View(
        route="/widgets",
        padding=0,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[build_layout(page, content)],
    )
