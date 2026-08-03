"""The shared page shell: nav rail plus content area, used by every view."""

from typing import NamedTuple

import flet as ft

from multitool.devtools import is_dev_environment
from multitool.state import get_active_theme, get_nav_position, is_named_theme_active
from multitool.theme import BACKGROUND_FIT_MAP
from multitool.ui.style import SPACE_MD, SPACE_SM, SPACE_XS, radius_card
from multitool.widgets.loader import get_enabled_widgets

GITHUB_BAR_HEIGHT = 48
"""Height of the fixed GitHub-link bar pinned to the bottom of the nav sidebar."""

_SCROLL_OFFSET_KEY = "_nav_widgets_scroll_offset"
_SCROLL_CONTROL_KEY = "_nav_widgets_scroll_control"


class _CoreDestination(NamedTuple):
    route: str
    icon: str
    selected_icon: str
    label: str


CORE_DESTINATIONS = [
    _CoreDestination("/", ft.Icons.DASHBOARD_OUTLINED, ft.Icons.DASHBOARD, "Dashboard"),
    _CoreDestination("/accounts", ft.Icons.PEOPLE_OUTLINE, ft.Icons.PEOPLE, "Accounts"),
    _CoreDestination("/widgets", ft.Icons.EXTENSION_OUTLINED, ft.Icons.EXTENSION, "Widgets"),
    _CoreDestination("/settings", ft.Icons.SETTINGS_OUTLINED, ft.Icons.SETTINGS, "Settings"),
]

CORE_ROUTES = [d.route for d in CORE_DESTINATIONS]


def widget_route(widget_id: str) -> str:
    """The route a widget's own view is built at."""
    return f"/widgets/{widget_id}"


async def restore_nav_scroll(page: ft.Page) -> None:
    """Reapply the widget nav list's saved scroll offset after a route rebuild.

    Every navigation rebuilds the whole page.views stack from scratch, which
    creates a brand new scrollable control with no memory of where the user
    had scrolled to. `build_layout` stores the live control and its last
    reported offset in `page.session.store` as it builds; this replays that
    offset once the new control has actually been added to the page, so
    clicking a widget doesn't visually reset the list to the top. Call this
    after `page.update()` in the route change handler.
    """
    control = page.session.store.get(_SCROLL_CONTROL_KEY)
    offset = page.session.store.get(_SCROLL_OFFSET_KEY)
    if control is None or not offset:
        return
    try:
        await control.scroll_to(offset=offset, duration=0)
    except Exception:
        pass


def build_layout(page: ft.Page, content: ft.Control) -> ft.Control:
    """Wrap page content in the shared nav rail and content area.

    Every view calls this to get the same nav rail, so a new view only
    needs to build its own content.

    Core destinations and enabled widgets are both rendered as plain
    clickable rows in a single scrollable `Column`, rather than using
    `ft.NavigationRail`. NavigationRail requires a bounded height and can't
    be nested as a shrink-to-content sibling of another scrollable control
    (a plain `Column` gives non-expanding children unbounded height, which
    NavigationRail rejects), and it exposes no scroll controller or
    `on_scroll` either way. A hand-rendered list sidesteps both problems and
    lets its scroll position be tracked and restored (see
    `restore_nav_scroll`) across the full-tree rebuild every navigation
    already does.
    """
    current_route = page.route

    async def go_to_route(route: str):
        await page.push_route(route)

    async def go_to_widget(widget_id: str):
        await page.push_route(widget_route(widget_id))

    def on_nav_scroll(e: ft.OnScrollEvent):
        page.session.store.set(_SCROLL_OFFSET_KEY, e.pixels)

    def nav_row(icon: str, label: str, selected: bool, on_click) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                [ft.Icon(icon), ft.Text(label, size=12)],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=4,
            ),
            padding=ft.Padding.symmetric(vertical=SPACE_SM, horizontal=SPACE_XS),
            border_radius=radius_card(page),
            bgcolor=ft.Colors.SECONDARY_CONTAINER if selected else None,
            on_click=on_click,
        )

    rows: list[ft.Control] = []
    for dest in CORE_DESTINATIONS:
        selected = current_route == dest.route
        rows.append(
            nav_row(
                dest.selected_icon if selected else dest.icon,
                dest.label,
                selected,
                lambda e, route=dest.route: page.run_task(go_to_route, route),
            )
        )

    widgets = get_enabled_widgets(page)
    if widgets:
        rows.append(
            ft.Container(
                width=48,
                height=1,
                bgcolor=ft.Colors.OUTLINE_VARIANT,
                margin=ft.Margin.symmetric(horizontal=SPACE_MD, vertical=SPACE_SM),
            )
        )
        for widget in widgets:
            selected = current_route == widget_route(widget.id)
            icon = (widget.selected_icon if selected else None) or widget.icon or ft.Icons.EXTENSION
            rows.append(
                nav_row(
                    icon,
                    widget.name,
                    selected,
                    lambda e, wid=widget.id: page.run_task(go_to_widget, wid),
                )
            )
    rows.append(ft.Container(height=GITHUB_BAR_HEIGHT))

    nav_list = ft.Column(
        rows,
        spacing=4,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        scroll=ft.ScrollMode.ALWAYS,
        on_scroll=on_nav_scroll,
    )
    page.session.store.set(_SCROLL_CONTROL_KEY, nav_list)

    github_button = ft.IconButton(
        icon=ft.Image(
            src="github.svg",
            width=20,
            height=20,
            color=ft.Colors.ON_SURFACE,
            color_blend_mode=ft.BlendMode.SRC_IN,
        ),
        tooltip="Open the Multitool repo on GitHub",
        url="https://github.com/BakedAleska",
    )

    nav_sidebar = ft.Stack(
        [
            nav_list,
            ft.Container(
                content=github_button,
                left=0,
                right=0,
                bottom=0,
                height=GITHUB_BAR_HEIGHT,
                alignment=ft.Alignment.CENTER,
                bgcolor=ft.Colors.SURFACE,
            ),
        ]
    )

    content_area = ft.Container(content=content, expand=True, padding=20)
    divider = ft.VerticalDivider(width=1)

    if get_nav_position(page) == "right":
        row_controls = [content_area, divider, nav_sidebar]
    else:
        row_controls = [nav_sidebar, divider, content_area]

    row = ft.Row(row_controls, expand=True, spacing=0)

    background_image = _background_image(page)
    root: ft.Control = ft.Stack([background_image, row], expand=True) if background_image else row

    if not is_dev_environment():
        return root

    dev_badge = ft.Container(
        content=ft.Container(
            content=ft.Text(
                "DEV",
                size=10,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.ON_ERROR,
            ),
            bgcolor=ft.Colors.ERROR,
            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
            border_radius=6,
            tooltip=(
                "Running from a source checkout: widgets and the Catalogue "
                "load straight from this repo instead of an installed copy. "
                "See CLAUDE.md's Developer mode section."
            ),
        ),
        right=8,
        bottom=8,
    )

    return ft.Stack([root, dev_badge], expand=True)


def _background_image(page: ft.Page) -> ft.Control | None:
    """The active custom theme's background image, or None if it has none."""
    if not is_named_theme_active(page):
        return None

    theme = get_active_theme(page)
    src = theme.get("background_image") if theme else None
    if not src:
        return None

    return ft.Container(
        image=ft.DecorationImage(
            src=src,
            fit=BACKGROUND_FIT_MAP.get(theme.get("background_fit"), ft.BoxFit.COVER),
            opacity=theme.get("background_opacity", 1.0),
        ),
        expand=True,
    )
