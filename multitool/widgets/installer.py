"""Download, verify, and install a widget from the Catalogue."""

import hashlib
import io
import json
import shutil
import uuid
import zipfile
from pathlib import Path
from typing import Optional

import flet as ft
import httpx

from multitool.config import WIDGETS_DIR
from multitool.logs import get_logger
from multitool.widgets.catalog import CatalogEntry

logger = get_logger(__name__)

MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024

INSTALL_MANIFEST_NAME = ".installed.json"
"""Filename of the small JSON manifest install_widget() drops inside each
widget it installs, recording the version and sha256 it came from. Dot-
prefixed like the staging directories, for the same reason: nothing else
in the codebase treats a leading-dot name as widget content. has_update()
reads it back to tell whether a newer Catalogue entry has shipped since.
"""

_INSTALLING_KEY = "_widget_installer_installing"


class WidgetInstallError(Exception):
    """Raised when a shop widget can't be downloaded, verified, or extracted."""


def install_widget(entry: CatalogEntry) -> None:
    """Download, verify, and extract a Catalogue entry into WIDGETS_DIR.

    Blocking. Call this via asyncio.to_thread from UI code. Raises
    WidgetInstallError with a user-facing message on any failure.

    Extraction happens in a dot-prefixed staging directory, which
    multitool.widgets.loader.discover_widgets() ignores. The staging directory
    is only moved into place after the install fully succeeds, so a
    failed install never leaves a broken folder at WIDGETS_DIR/<id>.

    A local: true entry (Developer Mode only, see WidgetSource) skips
    all of this and copies straight from disk instead - see
    _install_local.
    """
    if entry.source.local:
        _install_local(entry)
        return

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
                    raise WidgetInstallError(
                        "The download exceeded the size limit. "
                        "Did the registry point at the wrong repository?"
                    )
                chunks.append(chunk)
            data = b"".join(chunks)
    except httpx.HTTPError as e:
        logger.warning("Install of '%s' failed to download from %s: %s", entry.id, url, e)
        raise WidgetInstallError(
            f"Couldn't download the widget. Is your connection working? ({e})"
        ) from e

    digest = hashlib.sha256(data).hexdigest()
    if digest != entry.sha256:
        logger.warning(
            "Install of '%s' aborted: checksum mismatch (expected %s, got %s)",
            entry.id,
            entry.sha256,
            digest,
        )
        raise WidgetInstallError(
            "The downloaded file didn't match the expected checksum. "
            "Did the widget's source change after it was listed?"
        )

    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        logger.warning("Install of '%s' got an invalid archive: %s", entry.id, e)
        raise WidgetInstallError(
            f"The downloaded file wasn't a valid archive. Did the download get interrupted? ({e})"
        ) from e

    names = archive.namelist()
    if not names:
        logger.warning("Install of '%s' got an empty archive", entry.id)
        raise WidgetInstallError(
            "The downloaded archive was empty. Is the repository empty at that reference?"
        )

    top_level = names[0].split("/", 1)[0]
    path = entry.source.path.strip("/")
    prefix = f"{top_level}/{path}/" if path else f"{top_level}/"

    members = [n for n in names if n.startswith(prefix) and n != prefix]
    if not members:
        logger.warning("Install of '%s' found nothing at path '%s' in archive", entry.id, path)
        raise WidgetInstallError(
            f"The archive had nothing at '{entry.source.path}'. "
            "Did the widget move to a different path?"
        )

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
            raise WidgetInstallError(
                "The downloaded widget has no widget.py. Is this the correct folder for it?"
            )

        manifest = {"id": entry.id, "version": entry.version, "sha256": entry.sha256}
        (staging_dir / INSTALL_MANIFEST_NAME).write_text(json.dumps(manifest, indent=2))

        final_dir = WIDGETS_DIR / entry.id
        if final_dir.exists():
            shutil.rmtree(final_dir)
        shutil.move(str(staging_dir), str(final_dir))
        logger.info("Installed widget '%s' (version %s)", entry.id, entry.version)
    finally:
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)


def _install_local(entry: CatalogEntry) -> None:
    """Copy a local: true Catalogue entry straight from disk.

    Developer Mode only: lets a widget's Catalogue install/update flow
    be tested against a working copy on disk, uncommitted, rather than
    a pushed commit. There's no archive to verify a checksum against, so
    this skips hashing entirely - the whole point is to try code that
    hasn't been pushed yet.
    """
    source_dir = Path(entry.source.path)
    if not source_dir.is_dir():
        raise WidgetInstallError(
            f"Local widget source not found at {source_dir}. Did the path move?"
        )
    if not (source_dir / "widget.py").exists():
        raise WidgetInstallError(f"{source_dir} has no widget.py. Is this the right folder?")

    WIDGETS_DIR.mkdir(parents=True, exist_ok=True)
    staging_dir = WIDGETS_DIR / f".tmp_{entry.id}_{uuid.uuid4().hex}"

    try:
        shutil.copytree(
            source_dir, staging_dir, ignore=shutil.ignore_patterns(".git", "__pycache__")
        )

        manifest = {"id": entry.id, "version": entry.version, "sha256": entry.sha256}
        (staging_dir / INSTALL_MANIFEST_NAME).write_text(json.dumps(manifest, indent=2))

        final_dir = WIDGETS_DIR / entry.id
        if final_dir.exists():
            shutil.rmtree(final_dir)
        shutil.move(str(staging_dir), str(final_dir))
        logger.info("Installed local widget '%s' from %s", entry.id, source_dir)
    finally:
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)


def uninstall_widget(widget_id: str) -> None:
    """Remove an installed widget's folder from WIDGETS_DIR.

    Blocking. Call this via asyncio.to_thread from UI code. A no-op if
    the widget isn't installed.
    """
    target = WIDGETS_DIR / widget_id
    if target.exists():
        shutil.rmtree(target)
        logger.info("Uninstalled widget '%s'", widget_id)


def get_installed_manifest(widget_id: str) -> Optional[dict]:
    """The install manifest for a widget installed via the Catalogue.

    Returns None if the widget isn't installed, or was added manually
    (a folder copied straight into WIDGETS_DIR) instead of through
    install_widget(), so there's no manifest to read.
    """
    manifest_path = WIDGETS_DIR / widget_id / INSTALL_MANIFEST_NAME
    if not manifest_path.exists():
        return None
    try:
        return json.loads(manifest_path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Couldn't read install manifest for '%s': %s", widget_id, e)
        return None


def has_update(entry: CatalogEntry) -> bool:
    """Whether a Catalogue entry's sha256 differs from what's installed.

    Compares against the installed sha256 rather than the version
    string, since a registry entry's source can change without its
    version field being bumped to match. Always False for a widget
    with no install manifest (installed manually, not via the
    Catalogue), since there's nothing to compare against.
    """
    manifest = get_installed_manifest(entry.id)
    if manifest is None:
        return False
    return manifest.get("sha256") != entry.sha256


def is_installing(page: ft.Page, widget_id: str) -> bool:
    """Whether an install is in progress for this widget id."""
    return widget_id in (page.session.store.get(_INSTALLING_KEY) or set())


def mark_installing(page: ft.Page, widget_id: str) -> None:
    """Mark a widget id as installing, for is_installing() to see."""
    installing = set(page.session.store.get(_INSTALLING_KEY) or set())
    installing.add(widget_id)
    page.session.store.set(_INSTALLING_KEY, installing)


def unmark_installing(page: ft.Page, widget_id: str) -> None:
    """Clear the installing mark for a widget id."""
    installing = set(page.session.store.get(_INSTALLING_KEY) or set())
    installing.discard(widget_id)
    page.session.store.set(_INSTALLING_KEY, installing)
