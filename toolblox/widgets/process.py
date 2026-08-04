"""Helper for widgets whose actual logic runs as an external process.

Flet can only render UI from Python code running on its own event loop,
so a widget's `build_view`/`build_settings` always stays Python. What
that Python code *does*, though, doesn't have to be Python: this module
starts, talks to, and stops an external process (a compiled binary, a
shell script, a PowerShell script, a Node script, anything runnable),
exchanging newline-delimited JSON over its stdin/stdout. This mirrors
the IPC pattern toolblox/roblox/login.py already uses for its own subprocess.

Every process started through here is also registered on the page's
session, so app-level shutdown can stop anything a widget left running
rather than orphaning it.
"""

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import flet as ft

from toolblox.logs import get_logger

logger = get_logger(__name__)

_REGISTRY_KEY = "_widget_processes"


@dataclass
class WidgetProcess:
    """A running external process started by a widget."""

    process: asyncio.subprocess.Process
    _read_task: "asyncio.Task[None]" = field(repr=False)


async def start_process(
    page: ft.Page,
    *args: str,
    on_line: Optional[Callable[[dict[str, Any]], None]] = None,
    on_exit: Optional[Callable[[int], None]] = None,
) -> WidgetProcess:
    """Start an external process and stream its stdout as JSON lines.

    `args` is passed straight to `asyncio.create_subprocess_exec`, so any
    executable works. Each stdout line is parsed as JSON and handed to
    `on_line`; lines that aren't valid JSON are logged and skipped rather
    than crashing the reader. `on_exit` is called once with the
    process's exit code when it terminates, including when `stop_process`
    causes that.

    `on_line`/`on_exit` run on the calling coroutine's event loop, so
    it's safe for them to touch `page` state directly.
    """
    process = await asyncio.create_subprocess_exec(
        *args,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    async def _read_stdout():
        assert process.stdout is not None
        async for raw_line in process.stdout:
            if not on_line:
                continue
            try:
                data = json.loads(raw_line)
            except ValueError:
                logger.warning("Widget process printed a non-JSON line: %r", raw_line)
                continue
            on_line(data)
        code = await process.wait()
        registry = page.session.store.get(_REGISTRY_KEY) or []
        page.session.store.set(_REGISTRY_KEY, [wp for wp in registry if wp.process is not process])
        if on_exit:
            on_exit(code)

    read_task = asyncio.ensure_future(_read_stdout())
    widget_process = WidgetProcess(process=process, _read_task=read_task)

    registry = page.session.store.get(_REGISTRY_KEY) or []
    page.session.store.set(_REGISTRY_KEY, [*registry, widget_process])

    return widget_process


async def send_line(widget_process: WidgetProcess, data: dict[str, Any]) -> None:
    """Write one JSON line to the process's stdin."""
    if widget_process.process.stdin is None:
        raise RuntimeError("This process has no stdin pipe to write to.")
    widget_process.process.stdin.write((json.dumps(data) + "\n").encode())
    await widget_process.process.stdin.drain()


def stop_process(widget_process: WidgetProcess) -> None:
    """Terminate the process. Its stdout reader (and `on_exit`) still runs."""
    if widget_process.process.returncode is None:
        widget_process.process.terminate()


def stop_all_processes(page: ft.Page) -> None:
    """Terminate every process any widget has started on this page.

    Wired up to the window's close event in toolblox/app.py, so a widget
    backend (e.g. Autoclicker's click loop) never keeps running after the
    app window closes.
    """
    registry: list[WidgetProcess] = page.session.store.get(_REGISTRY_KEY) or []
    for widget_process in registry:
        stop_process(widget_process)
