import flet as ft


def show_toast(page: ft.Page, message: str, *, duration_ms: int = 4000) -> None:
    page.show_dialog(
        ft.SnackBar(
            content=ft.Text(message),
            duration=ft.Duration(milliseconds=duration_ms),
            behavior=ft.SnackBarBehavior.FLOATING,
        )
    )


def show_confirm_toast(
    page: ft.Page,
    message: str,
    on_confirm,
    *,
    confirm_label: str = "Confirm",
    cancel_label: str = "Cancel",
    duration_ms: int = 8000,
) -> None:
    def handle_confirm(e: ft.Event[ft.TextButton]):
        page.pop_dialog()
        on_confirm()

    def handle_cancel(e: ft.Event[ft.TextButton]):
        page.pop_dialog()

    page.show_dialog(
        ft.SnackBar(
            content=ft.Row(
                [
                    ft.Text(message, expand=True),
                    ft.TextButton(cancel_label, on_click=handle_cancel),
                    ft.TextButton(confirm_label, on_click=handle_confirm),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            duration=ft.Duration(milliseconds=duration_ms),
            behavior=ft.SnackBarBehavior.FLOATING,
        )
    )
