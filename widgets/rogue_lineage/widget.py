"""Rogue Lineage: track characters, their class, race, notes, and items.

A character's username is always typed in by hand. If it's similar to one
of Toolblox's own tracked accounts, pressing Tab while the field is
focused autofills the full match - and once it's an exact match, the
character starts syncing with that account automatically (see
storage.sync_with_accounts): its username and avatar follow the account
from then on, kept in sync automatically, and it falls back to standalone
again if the account is later removed. Every screen build starts a
background loop that re-checks the roster against the current account
list every few seconds, so this happens without reopening the widget.

Class, race, and item choices come from a bundled reference.json, editable
by hand - see reference.py's docstring. Every dropdown built from that
list also offers "Other...", so an incomplete list never blocks entering
real data.
"""

import asyncio

import flet as ft

from toolblox.data import accounts as accounts_store
from toolblox.ui.layout import build_layout, widget_route
from toolblox.ui.style import (
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
    SPACE_XS,
    card_border,
    radius_card,
    scroll_margin,
    text_caption,
    text_label,
    text_section,
    text_title,
)
from toolblox.ui.toast import show_confirm_toast, show_toast
from toolblox.widgets.api import Widget

from . import reference, storage

WIDGET_ID = "rogue_lineage"
_GENERATION_KEY = f"_{WIDGET_ID}_generation"
_DIALOG_OPEN_KEY = f"_{WIDGET_ID}_dialog_open"
_SYNC_INTERVAL_SECONDS = 10

_OTHER_KEY = "__other__"

_USERNAME_TEXT_SIZE = 16
"""Shared text size for the username field and its ghost-completion text
behind it, so typed characters and the gray suggestion line up. The field
uses border=NONE and no built-in label (a plain Text above it stands in
for one instead) specifically so both layers share the same padding-only
box - Flutter's OutlineInputBorder and floating label both add their own
internal offsets that a plain Text sitting behind the field can't predict
or match."""
_TS_KW = {"size": _USERNAME_TEXT_SIZE}
_USERNAME_TEXT_STYLE = ft.TextStyle(**_TS_KW)
_USERNAME_PADDING = ft.Padding.symmetric(horizontal=8, vertical=10)


def _dropdown_options(values: list[str]) -> list[ft.dropdown.Option]:
    return [ft.dropdown.Option(key=v, text=v) for v in values] + [
        ft.dropdown.Option(key=_OTHER_KEY, text="Other...")
    ]


def _resolve_choice(dropdown: ft.Dropdown, other_field: ft.TextField) -> str:
    """The chosen class/race/item name, from either the dropdown or its
    "Other..." text field."""
    if dropdown.value == _OTHER_KEY:
        return (other_field.value or "").strip()
    return dropdown.value or ""


def _build_choice_row(label: str, options: list[str], current_value: str) -> tuple:
    """A Dropdown plus a paired "Other..." TextField, pre-selecting
    Other and filling the text field if current_value isn't in options.
    """
    is_custom = bool(current_value) and current_value not in options
    dropdown = ft.Dropdown(
        label=label,
        options=_dropdown_options(options),
        value=_OTHER_KEY if is_custom else (current_value or None),
        dense=True,
        expand=True,
    )
    other_field = ft.TextField(
        label=f"{label} (custom)",
        value=current_value if is_custom else "",
        visible=is_custom,
        dense=True,
        expand=True,
    )

    def on_change(e: ft.Event[ft.Dropdown]):
        other_field.visible = dropdown.value == _OTHER_KEY
        other_field.update()

    dropdown.on_change = on_change
    return dropdown, other_field


def _best_username_match(accounts: list[dict], typed: str) -> str | None:
    """The first tracked account username that starts with typed text, for
    the Tab-to-autofill hint - or None if nothing matches or typed is
    empty.
    """
    query = (typed or "").strip().lower()
    if not query:
        return None
    for account in accounts:
        name = account.get("name", "")
        if name.lower() != query and name.lower().startswith(query):
            return name
    return None


def _open_character_dialog(page: ft.Page, existing: dict | None, on_saved) -> None:
    """Show the add/edit character form as a modal dialog.

    Only one instance of this dialog can be open at a time, tracked via
    _DIALOG_OPEN_KEY - callers should check that flag before calling this,
    to avoid stacking a second dialog on top of one already open.
    """
    page.session.store.set(_DIALOG_OPEN_KEY, True)
    accounts = accounts_store.load()

    username_field = ft.TextField(
        value=(existing.get("username") or "") if existing else "",
        border=ft.InputBorder.NONE,
        content_padding=_USERNAME_PADDING,
        text_style=_USERNAME_TEXT_STYLE,
        autofocus=True,
        expand=True,
    )
    username_ghost_field = ft.TextField(
        value=username_field.value,
        border=ft.InputBorder.NONE,
        content_padding=_USERNAME_PADDING,
        text_style=ft.TextStyle(color=ft.Colors.ON_SURFACE_VARIANT, **_TS_KW),
        read_only=True,
        disabled=True,
        show_cursor=False,
        expand=True,
    )
    username_box = ft.Container(
        content=ft.Stack([username_ghost_field, username_field]),
        border=ft.Border.all(1, ft.Colors.OUTLINE),
        border_radius=4,
    )
    username_group = ft.Column(
        [
            text_caption("Username"),
            username_box,
        ],
        spacing=SPACE_XS,
    )
    username_focused = False
    current_suggestion: str | None = None

    def update_suggestion(mounted: bool = True):
        """Recompute the Tab-completion ghost text.

        The ghost field's value is set to the typed text plus the
        suggested remainder, in a gray TextField stacked directly behind
        the real one. Both fields share the same border/padding/text
        style, so Flutter lays out their text identically - the typed
        characters in the real field land exactly on top of the same
        characters in the ghost field, and only the untyped suggested
        tail shows through beyond them. This is why the ghost value
        includes the literal typed prefix (not the account's own casing
        for it) - if the two fields' prefixes were different strings,
        different glyph shapes could show through at the edges.
        """
        nonlocal current_suggestion
        typed = username_field.value or ""
        current_suggestion = _best_username_match(accounts, typed)
        suffix = current_suggestion[len(typed) :] if current_suggestion else ""
        username_ghost_field.value = typed + suffix
        if mounted:
            username_ghost_field.update()

    def on_username_change(e: ft.Event[ft.TextField]):
        update_suggestion()

    def on_username_focus(e: ft.Event[ft.TextField]):
        nonlocal username_focused
        username_focused = True

    def on_username_blur(e: ft.Event[ft.TextField]):
        nonlocal username_focused
        username_focused = False

    username_field.on_change = on_username_change
    username_field.on_focus = on_username_focus
    username_field.on_blur = on_username_blur

    previous_keyboard_handler = page.on_keyboard_event

    def on_keyboard_event(e: ft.KeyboardEvent):
        if username_focused and e.key == "Tab" and current_suggestion:
            username_field.value = current_suggestion
            username_field.update()
            update_suggestion()
            return
        if previous_keyboard_handler:
            previous_keyboard_handler(e)

    page.on_keyboard_event = on_keyboard_event

    def close_dialog():
        page.on_keyboard_event = previous_keyboard_handler
        page.session.store.set(_DIALOG_OPEN_KEY, False)
        page.pop_dialog()

    class_dropdown, class_other = _build_choice_row(
        "Class", reference.CLASSES, existing.get("class_name", "") if existing else ""
    )
    race_dropdown, race_other = _build_choice_row(
        "Race", reference.RACES, existing.get("race", "") if existing else ""
    )
    notes_field = ft.TextField(
        label="Notes",
        value=(existing.get("notes") or "") if existing else "",
        multiline=True,
        min_lines=2,
        max_lines=5,
        dense=True,
    )

    items_state: list[dict] = list(existing.get("items", [])) if existing else []
    items_column = ft.Column(spacing=SPACE_XS)

    def render_items(mounted: bool = True):
        if not items_state:
            items_column.controls = [text_caption("No items added yet.")]
        else:
            items_column.controls = [
                _item_chip(index, item) for index, item in enumerate(items_state)
            ]
        if mounted:
            items_column.update()

    def _item_chip(index: int, item: dict) -> ft.Control:
        label = item["name"]
        quantity = item.get("quantity", 1)
        if quantity and quantity > 1:
            label = f"{label} ×{quantity}"

        def on_remove(e: ft.Event[ft.IconButton]):
            items_state.pop(index)
            render_items()

        return ft.Container(
            content=ft.Row(
                [
                    ft.Text(label, size=12, expand=True),
                    ft.IconButton(icon=ft.Icons.CLOSE, icon_size=14, on_click=on_remove),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.symmetric(horizontal=SPACE_SM, vertical=2),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border_radius=999,
        )

    item_dropdown = ft.Dropdown(
        label="Item", options=_dropdown_options(reference.ITEMS), dense=True, expand=True
    )
    item_other_field = ft.TextField(
        label="Item name (custom)", visible=False, dense=True, expand=True
    )
    item_quantity_field = ft.TextField(
        label="Quantity (optional)",
        dense=True,
        width=140,
        keyboard_type=ft.KeyboardType.NUMBER,
    )

    def on_item_dropdown_change(e: ft.Event[ft.Dropdown]):
        item_other_field.visible = item_dropdown.value == _OTHER_KEY
        item_other_field.update()

    item_dropdown.on_change = on_item_dropdown_change

    def on_add_item(e: ft.Event[ft.IconButton]):
        name = _resolve_choice(item_dropdown, item_other_field)
        if not name:
            show_toast(page, "Pick or type an item name first.")
            return
        raw_quantity = (item_quantity_field.value or "").strip()
        quantity = 1
        if raw_quantity:
            try:
                quantity = max(1, int(raw_quantity))
            except ValueError:
                show_toast(page, "Quantity has to be a whole number.")
                return
        items_state.append({"name": name, "quantity": quantity})
        item_dropdown.value = None
        item_other_field.value = ""
        item_other_field.visible = False
        item_quantity_field.value = ""
        item_dropdown.update()
        item_other_field.update()
        item_quantity_field.update()
        render_items()

    render_items(mounted=False)
    update_suggestion(mounted=False)

    def on_save(e: ft.Event[ft.FilledButton]):
        username = (username_field.value or "").strip()
        if not username:
            show_toast(page, "Enter a username first.")
            return

        class_name = _resolve_choice(class_dropdown, class_other)
        race = _resolve_choice(race_dropdown, race_other)
        if not class_name or not race:
            show_toast(page, "Pick or type a class and race first.")
            return

        current = storage.load_roster()
        if existing:
            for character in current:
                if character["char_id"] == existing["char_id"]:
                    character.update(
                        username=username,
                        class_name=class_name,
                        race=race,
                        notes=(notes_field.value or "").strip(),
                        items=list(items_state),
                    )
                    break
        else:
            current.append(
                storage.new_character(
                    account_id=None,
                    username=username,
                    display_name=None,
                    avatar_url=None,
                    class_name=class_name,
                    race=race,
                    notes=(notes_field.value or "").strip(),
                    items=list(items_state),
                )
            )
        storage.save_roster(current)
        close_dialog()
        on_saved()

    def on_cancel(e: ft.Event[ft.TextButton]):
        close_dialog()

    dialog = ft.AlertDialog(
        modal=True,
        scrollable=True,
        title=ft.Text("Edit character" if existing else "Add character"),
        content=ft.Container(
            content=ft.Column(
                [
                    username_group,
                    ft.Row([class_dropdown, class_other], spacing=SPACE_MD),
                    ft.Row([race_dropdown, race_other], spacing=SPACE_MD),
                    notes_field,
                    ft.Divider(),
                    text_section("Items"),
                    items_column,
                    ft.Row([item_dropdown, item_other_field], spacing=SPACE_MD),
                    ft.Row(
                        [
                            item_quantity_field,
                            ft.IconButton(
                                icon=ft.Icons.ADD, tooltip="Add item", on_click=on_add_item
                            ),
                        ],
                        spacing=SPACE_MD,
                    ),
                ],
                spacing=SPACE_MD,
            ),
            width=440,
        ),
        actions=[
            ft.TextButton("Cancel", on_click=on_cancel),
            ft.FilledButton("Save", on_click=on_save),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.show_dialog(dialog)


def build_view(page: ft.Page) -> ft.View:
    """The Rogue Lineage screen: a searchable roster of characters, each
    with class, race, notes, and items, plus add/edit/delete.
    """

    list_column = ft.Column(spacing=SPACE_SM)

    def delete_character(char_id: str):
        current = storage.load_roster()
        current = [c for c in current if c["char_id"] != char_id]
        storage.save_roster(current)
        render_list()

    def character_card(character: dict) -> ft.Control:
        username = character.get("username", "")
        display_name = character.get("display_name")
        header_text = (
            f"({display_name}) {username}"
            if display_name and display_name != username
            else username
        )

        avatar_url = character.get("avatar_url")
        avatar = (
            ft.Image(src=avatar_url, width=40, height=40, fit=ft.BoxFit.COVER)
            if avatar_url
            else ft.Icon(ft.Icons.PERSON, size=24)
        )

        subtitle = " • ".join(
            part for part in (character.get("class_name"), character.get("race")) if part
        )

        def on_open(e: ft.Event[ft.Container]):
            if page.session.store.get(_DIALOG_OPEN_KEY):
                return
            _open_character_dialog(page, character, render_list)

        def on_delete(e: ft.Event[ft.IconButton]):
            show_confirm_toast(
                page,
                f'Delete "{username}"? This can\'t be undone.',
                lambda: delete_character(character["char_id"]),
                confirm_label="Delete",
            )

        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        content=avatar,
                        width=40,
                        height=40,
                        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                        border_radius=20,
                        alignment=ft.Alignment.CENTER,
                    ),
                    ft.Row(
                        [
                            text_label(header_text),
                            text_caption(subtitle or "No class or race set"),
                            _info_chip("Not linked")
                            if character.get("account_id") is None
                            else ft.Container(),
                        ],
                        expand=True,
                        spacing=SPACE_MD,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE, tooltip="Delete", on_click=on_delete
                    ),
                ],
                spacing=SPACE_MD,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            on_click=on_open,
            ink=True,
            padding=ft.Padding.symmetric(horizontal=SPACE_MD, vertical=SPACE_SM),
            border=card_border(),
            border_radius=radius_card(page),
        )

    def render_list(mounted: bool = True):
        characters = sorted(storage.load_roster(), key=lambda c: c.get("username", "").lower())
        if not characters:
            list_column.controls = [text_caption("No characters added yet.")]
        else:
            list_column.controls = [character_card(c) for c in characters]
        if mounted:
            list_column.update()

    def on_add(e: ft.Event[ft.FilledButton]):
        if page.session.store.get(_DIALOG_OPEN_KEY):
            return
        _open_character_dialog(page, None, render_list)

    async def sync_loop(generation: int):
        """Reconcile the roster against tracked accounts on a timer, for
        as long as this exact view build is the one on screen.
        """
        while True:
            if (
                not page.views
                or page.views[-1].route != widget_route(WIDGET_ID)
                or page.session.store.get(_GENERATION_KEY) != generation
            ):
                return
            current = storage.load_roster()
            updated, changed = storage.sync_with_accounts(current, accounts_store.load())
            if changed:
                storage.save_roster(updated)
                render_list()
            await asyncio.sleep(_SYNC_INTERVAL_SECONDS)

    render_list(mounted=False)

    generation = (page.session.store.get(_GENERATION_KEY) or 0) + 1
    page.session.store.set(_GENERATION_KEY, generation)
    page.run_task(sync_loop, generation)

    content = ft.Column(
        [
            ft.Row(
                [
                    text_title("Rogue Lineage"),
                    ft.FilledButton("Add character", icon=ft.Icons.ADD, on_click=on_add),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            text_caption(
                "Track characters, their class, race, notes, and items. Type a "
                "username similar to a tracked account and press Tab to "
                "autofill it - an exact match starts syncing automatically."
            ),
            list_column,
        ],
        spacing=SPACE_LG,
        scroll=ft.ScrollMode.AUTO,
        margin=scroll_margin(),
    )

    return ft.View(
        route=widget_route(WIDGET_ID),
        padding=0,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[build_layout(page, content)],
    )


def _info_chip(text: str) -> ft.Control:
    return ft.Container(
        content=ft.Text(text, size=11),
        padding=ft.Padding.symmetric(horizontal=SPACE_SM, vertical=2),
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        border_radius=999,
    )


WIDGET = Widget(
    id=WIDGET_ID,
    name="Rogue Lineage",
    description="Track Rogue Lineage characters: class, race, notes, and items.",
    build_view=build_view,
    icon=ft.Icons.SHIELD_OUTLINED,
    selected_icon=ft.Icons.SHIELD,
)
