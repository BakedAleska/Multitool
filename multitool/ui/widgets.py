"""The Widgets screen: the Catalogue banner and the grid of installed widgets."""

import asyncio

import flet as ft

from multitool.state import get_disabled_widgets, remove_widget_settings, set_widget_enabled
from multitool.ui.layout import build_layout, widget_route
from multitool.ui.style import SWITCH_SCALE, card_border, radius_card, scroll_margin, scroll_padding
from multitool.ui.toast import show_confirm_toast, show_toast
from multitool.widgets.catalog import (
    CatalogEntry,
    fetch_registry,
    get_cached_registry,
    set_cached_registry,
)
from multitool.widgets.installer import (
    WidgetInstallError,
    has_update,
    install_widget,
    is_installing,
    mark_installing,
    uninstall_widget,
    unmark_installing,
)
from multitool.widgets.loader import discover_widgets

_CATALOGUE_FETCHED_KEY = "_widget_catalogue_fetched"
_CATALOGUE_ERROR_KEY = "_widget_catalogue_error"
_SETTINGS_FOCUS_WIDGET_KEY = "_settings_focus_widget_id"

INSTALLED_PER_ROW = 4
"""Installed widgets are laid out in a GridView with this many columns, so
each card's size is however wide 1/4 of the available row is, rather than a
fixed pixel size. That keeps the grid flush against both edges with even
gaps, instead of leaving leftover space before the row wraps when there
aren't enough widgets installed to fill a fixed-size row exactly."""

CATALOGUE_SIZE = 104
"""Catalogue tiles are app-icon-style: tap to install, no controls, so
they read like a smaller, denser shop shelf next to the installed grid."""

CARD_PADDING = 14
ICON_CHIP_SIZE = 40
BADGE_SIZE = 18


def _icon_chip(icon: object, logo: str | None, *, active: bool, size: int) -> ft.Control:
    """A rounded, tinted square holding a widget's icon or logo.

    `active` drives the tint: the accent-tinted PRIMARY_CONTAINER for an
    installable or enabled widget, a neutral SURFACE_CONTAINER_HIGHEST for
    a disabled one. This is how card state is shown instead of dimming
    the whole card, which made text hard to read.
    """
    fg = ft.Colors.ON_PRIMARY_CONTAINER if active else ft.Colors.ON_SURFACE_VARIANT
    bg = ft.Colors.PRIMARY_CONTAINER if active else ft.Colors.SURFACE_CONTAINER_HIGHEST
    icon_size = round(size * 0.5)
    inner = (
        ft.Image(src=logo, width=icon_size, height=icon_size, fit=ft.BoxFit.CONTAIN)
        if logo
        else ft.Icon(icon or ft.Icons.EXTENSION, size=icon_size, color=fg)
    )
    return ft.Container(
        content=inner,
        width=size,
        height=size,
        bgcolor=bg,
        border_radius=12,
        alignment=ft.Alignment.CENTER,
    )


def WidgetsView(page: ft.Page) -> ft.View:
    """The Widgets screen.

    The Catalogue is fetched once per session, on the first build. The
    fetched flag is read fresh at the top of every build and set inside
    background_refresh_catalogue itself, before it calls refresh(). This
    guard matters: refresh() rebuilds this view, so an unconditional
    fetch here would trigger another fetch on every rebuild, without end.

    The installed-widgets section is wrapped in a container held to the
    full window height, even when it only has one short row of widgets
    in it. That's deliberate: it guarantees there's always enough room
    to scroll the Catalogue completely out of view above it, so the
    first row of installed widgets can reach the top of the screen,
    rather than the page only scrolling as far as its actual content.
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

    async def go_to_widget(widget_id: str):
        """Open an installed widget's own view, same as clicking it in the nav rail."""
        await page.push_route(widget_route(widget_id))

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

    async def on_uninstall(widget_id: str):
        """Remove an installed widget's folder and its stored settings."""
        await asyncio.to_thread(uninstall_widget, widget_id)
        remove_widget_settings(page, widget_id)
        refresh()

    async def on_update(entry: CatalogEntry):
        """Reinstall a Catalogue entry over its currently installed copy.

        Unlike on_install, this leaves the widget's enabled state alone -
        updating a disabled widget shouldn't silently re-enable it.
        """
        mark_installing(page, entry.id)
        refresh()
        try:
            await asyncio.to_thread(install_widget, entry)
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
        """Build one installed widget's card.

        Clicking anywhere on the card opens the widget's own view, same as
        clicking it in the nav rail. The Switch, settings button, and
        delete button sit in a separate overlay layer on top (a sibling in
        the Stack, not a descendant of the clickable card) so their own
        clicks are handled by them instead of by the card's on_click -
        the same layering trick this file already used for the old
        settings-button overlay.

        The icon chip's tint mirrors the enabled state instead of dimming
        the whole card, so the name and description stay legible either
        way. A widget with `build_settings` set also gets a settings
        button that jumps to its section under Settings -> Widgets. The
        delete button uninstalls it after a confirmation prompt, removing
        its folder from disk.

        The description sits in its own scrollable area that expands to
        fill the space up to the footer, instead of a fixed line count
        with an ellipsis - a long description scrolls in place rather
        than getting cut short.

        A widget whose Catalogue entry has a different sha256 than the
        one recorded at install time gets an update button in place of
        its settings/uninstall row, swapped for a progress ring while
        the update is running - see has_update() and on_update().
        """
        enabled = widget.id not in disabled_ids
        registry_entry = registry_by_id.get(widget.id)
        updatable = registry_entry is not None and has_update(registry_entry)
        updating = is_installing(page, widget.id)

        trailing_actions: list[ft.Control] = []
        if updating:
            trailing_actions.append(
                ft.Container(
                    content=ft.ProgressRing(width=14, height=14, stroke_width=2),
                    padding=8,
                )
            )
        elif updatable:
            trailing_actions.append(
                ft.IconButton(
                    icon=ft.Icons.SYSTEM_UPDATE_ALT,
                    icon_size=16,
                    icon_color=ft.Colors.PRIMARY,
                    tooltip=(
                        f"Update {widget.name} to version {registry_entry.version}"
                        if registry_entry.version
                        else f"Update {widget.name}"
                    ),
                    on_click=lambda e, ent=registry_entry: page.run_task(on_update, ent),
                )
            )
        if widget.build_settings is not None:
            trailing_actions.append(
                ft.IconButton(
                    icon=ft.Icons.SETTINGS_OUTLINED,
                    icon_size=16,
                    tooltip=f"{widget.name} settings",
                    on_click=lambda e, wid=widget.id: page.run_task(open_widget_settings, wid),
                )
            )
        trailing_actions.append(
            ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE,
                icon_size=16,
                tooltip=f"Uninstall {widget.name}",
                on_click=lambda e, wid=widget.id, name=widget.name: show_confirm_toast(
                    page,
                    f"Uninstall {name}? This removes it from your computer.",
                    lambda wid=wid: page.run_task(on_uninstall, wid),
                    confirm_label="Uninstall",
                ),
            )
        )

        card_body = ft.Container(
            content=ft.Column(
                [
                    _icon_chip(widget.icon, widget.logo, active=enabled, size=ICON_CHIP_SIZE),
                    ft.Text(
                        widget.name,
                        size=13,
                        weight=ft.FontWeight.W_600,
                        text_align=ft.TextAlign.CENTER,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Column(
                        [
                            ft.Text(
                                widget.description or "No description provided.",
                                size=11,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                                text_align=ft.TextAlign.CENTER,
                            )
                        ],
                        scroll=ft.ScrollMode.AUTO,
                        expand=True,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(height=42),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
            ),
            expand=True,
            padding=CARD_PADDING,
            border=card_border(),
            border_radius=radius_card(page),
            tooltip=f"Open {widget.name}",
            on_click=lambda e, wid=widget.id: page.run_task(go_to_widget, wid),
        )

        footer_overlay = ft.Container(
            content=ft.Column(
                [
                    ft.Divider(height=1, thickness=1, color=ft.Colors.OUTLINE_VARIANT),
                    ft.Row(
                        [
                            ft.Switch(
                                value=enabled,
                                scale=SWITCH_SCALE,
                                tooltip="Enabled" if enabled else "Disabled",
                                on_change=lambda e, wid=widget.id: on_toggle(
                                    wid, e.control.value
                                ),
                            ),
                            ft.Row(trailing_actions, spacing=0),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                ],
                spacing=8,
            ),
            left=CARD_PADDING,
            right=CARD_PADDING,
            bottom=CARD_PADDING,
        )

        return ft.Stack([card_body, footer_overlay], expand=True)

    def build_catalogue_square(entry: CatalogEntry) -> ft.Control:
        """Build one Catalogue entry's tile.

        The logo (or, absent one, a placeholder Material icon) sits at a
        fixed glyph size on a neutral background, the same area either
        way, so a tile with a real logo and one still on the placeholder
        look consistent side by side instead of the real ones jumping out
        as bigger. A single tap anywhere installs it. The name sits at
        the bottom in plain black text, and an "add" badge sits in the
        top-right corner. No separate button or description on the tile
        itself - that detail lives in the tooltip instead.

        The clip and the border live on two separate, nested containers
        rather than one: putting `clip_behavior` and `border` on the
        same container clips the border itself away at the rounded
        corners, leaving the tile looking square and borderless. The
        inner container clips the logo/icon content to the rounded
        shape; the outer one, unclipped, is what actually draws the
        visible border.
        """
        installing = is_installing(page, entry.id)
        icon = (getattr(ft.Icons, entry.icon, None) if entry.icon else None) or ft.Icons.WIDGETS
        glyph_size = round(CATALOGUE_SIZE * 0.35)

        logo_fill: ft.Control = ft.Container(
            content=(
                ft.Image(
                    src=entry.logo,
                    width=glyph_size,
                    height=glyph_size,
                    fit=ft.BoxFit.CONTAIN,
                )
                if entry.logo
                else ft.Icon(icon, size=glyph_size, color=ft.Colors.ON_SURFACE_VARIANT)
            ),
            width=CATALOGUE_SIZE,
            height=CATALOGUE_SIZE,
            bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
            alignment=ft.Alignment.CENTER,
        )

        badge = ft.Container(
            content=(
                ft.ProgressRing(width=10, height=10, stroke_width=2, color=ft.Colors.ON_PRIMARY)
                if installing
                else ft.Icon(ft.Icons.ADD, size=14, color=ft.Colors.ON_PRIMARY)
            ),
            width=BADGE_SIZE,
            height=BADGE_SIZE,
            bgcolor=ft.Colors.PRIMARY,
            border=ft.Border.all(2, ft.Colors.SURFACE_CONTAINER_LOW),
            border_radius=BADGE_SIZE / 2,
            alignment=ft.Alignment.CENTER,
        )

        name_overlay = ft.Container(
            content=ft.Text(
                entry.name,
                size=12,
                weight=ft.FontWeight.W_600,
                color=ft.Colors.BLACK,
                text_align=ft.TextAlign.CENTER,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
            padding=ft.Padding(6, 0, 6, 8),
            left=0,
            right=0,
            bottom=0,
        )

        tooltip = entry.name
        if entry.description:
            tooltip = f"{entry.name}: {entry.description}"
        if installing:
            tooltip = f"Installing {entry.name}…"

        clipped_content = ft.Container(
            content=ft.Stack(
                [
                    logo_fill,
                    name_overlay,
                    ft.Container(content=badge, top=6, right=6),
                ],
                width=CATALOGUE_SIZE,
                height=CATALOGUE_SIZE,
            ),
            width=CATALOGUE_SIZE,
            height=CATALOGUE_SIZE,
            border_radius=radius_card(page),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )

        return ft.Container(
            content=clipped_content,
            width=CATALOGUE_SIZE,
            height=CATALOGUE_SIZE,
            border=card_border(),
            border_radius=radius_card(page),
            opacity=0.7 if installing else 1.0,
            tooltip=tooltip,
            on_click=(
                None if installing else (lambda e, ent=entry: page.run_task(on_install, ent))
            ),
        )

    catalogue_fetched = page.session.store.get(_CATALOGUE_FETCHED_KEY)
    catalogue_error = page.session.store.get(_CATALOGUE_ERROR_KEY)
    all_entries = get_cached_registry(page)
    registry_by_id = {e.id: e for e in all_entries}
    catalogue_entries = [e for e in all_entries if e.id not in local_ids]

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
            spacing=12,
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

    if widgets:
        installed_content: ft.Control = ft.GridView(
            [build_installed_square(w) for w in widgets],
            runs_count=INSTALLED_PER_ROW,
            child_aspect_ratio=1.0,
            spacing=12,
            run_spacing=12,
            expand=True,
            padding=scroll_padding(),
        )
    else:
        installed_content = ft.Text(
            "No widgets installed. Install one from the Catalogue above, or add one "
            "manually from Settings.",
            italic=True,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )

    installed_section = ft.Container(
        content=installed_content,
        height=page.height or 600,
        alignment=ft.Alignment.TOP_LEFT,
    )

    body: list[ft.Control] = [catalogue_banner, ft.Divider(), installed_section]

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
        scroll=ft.ScrollMode.AUTO,
        margin=scroll_margin(),
    )

    if not catalogue_fetched:
        page.run_task(background_refresh_catalogue)

    return ft.View(
        route="/widgets",
        padding=0,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[build_layout(page, content)],
    )
