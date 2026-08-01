import hashlib
import io
import shutil
import uuid
import zipfile

import flet as ft
import httpx

from app.config import WIDGETS_DIR
from app.logs import get_logger
from app.widgets.catalog import CatalogEntry

logger = get_logger(__name__)

MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024

_INSTALLING_KEY = "_widget_installer_installing"


class WidgetInstallError(Exception):
    """Raised when a shop widget can't be downloaded, verified, or extracted."""


def install_widget(entry: CatalogEntry) -> None:
    """Download, verify, and extract a catalog entry into WIDGETS_DIR.

    Blocking/sync — call via asyncio.to_thread from UI code. Raises
    WidgetInstallError with a user-facing message on any failure; never
    leaves a partial/broken folder at WIDGETS_DIR/<id> (extraction happens
    in a dot-prefixed staging dir that app.widgets.loader.discover_widgets()
    already ignores, and is only moved into place after fully succeeding).
    """
    url = f"https://github.com/{entry.source.owner}/{entry.source.repo}/archive/{entry.source.ref}.zip"

    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=30) as response:
            response.raise_for_status()
            chunks = []
            total = 0
            for chunk in response.iter_bytes():
                total += len(chunk)
                if total > MAX_DOWNLOAD_BYTES:
                    logger.warning("Install of '%s' aborted: exceeded size limit", entry.id)
                    raise WidgetInstallError("Download exceeded the size limit.")
                chunks.append(chunk)
            data = b"".join(chunks)
    except httpx.HTTPError as e:
        logger.warning("Install of '%s' failed to download from %s: %s", entry.id, url, e)
        raise WidgetInstallError(f"Couldn't download the widget: {e}") from e

    digest = hashlib.sha256(data).hexdigest()
    if digest != entry.sha256:
        logger.warning(
            "Install of '%s' aborted: checksum mismatch (expected %s, got %s)",
            entry.id,
            entry.sha256,
            digest,
        )
        raise WidgetInstallError("Downloaded file didn't match the expected checksum.")

    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        logger.warning("Install of '%s' got an invalid archive: %s", entry.id, e)
        raise WidgetInstallError(f"Downloaded file wasn't a valid archive: {e}") from e

    names = archive.namelist()
    if not names:
        logger.warning("Install of '%s' got an empty archive", entry.id)
        raise WidgetInstallError("Downloaded archive was empty.")

    top_level = names[0].split("/", 1)[0]
    path = entry.source.path.strip("/")
    prefix = f"{top_level}/{path}/" if path else f"{top_level}/"

    members = [n for n in names if n.startswith(prefix) and n != prefix]
    if not members:
        logger.warning("Install of '%s' found nothing at path '%s' in archive", entry.id, path)
        raise WidgetInstallError(f"Archive had nothing at '{entry.source.path}'.")

    WIDGETS_DIR.mkdir(parents=True, exist_ok=True)
    staging_dir = WIDGETS_DIR / f".tmp_{entry.id}_{uuid.uuid4().hex}"
    staging_dir.mkdir()

    try:
        for member in members:
            relative = member[len(prefix) :]
            target = staging_dir / relative
            if member.endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(member))

        if not (staging_dir / "widget.py").exists():
            logger.warning("Install of '%s' has no widget.py at its root", entry.id)
            raise WidgetInstallError("Downloaded widget has no widget.py.")

        final_dir = WIDGETS_DIR / entry.id
        if final_dir.exists():
            shutil.rmtree(final_dir)
        shutil.move(str(staging_dir), str(final_dir))
        logger.info("Installed widget '%s' (version %s)", entry.id, entry.version)
    finally:
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)


def is_installing(page: ft.Page, widget_id: str) -> bool:
    return widget_id in (page.session.store.get(_INSTALLING_KEY) or set())


def mark_installing(page: ft.Page, widget_id: str) -> None:
    installing = set(page.session.store.get(_INSTALLING_KEY) or set())
    installing.add(widget_id)
    page.session.store.set(_INSTALLING_KEY, installing)


def unmark_installing(page: ft.Page, widget_id: str) -> None:
    installing = set(page.session.store.get(_INSTALLING_KEY) or set())
    installing.discard(widget_id)
    page.session.store.set(_INSTALLING_KEY, installing)
