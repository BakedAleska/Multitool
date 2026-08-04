"""Check GitHub Releases for a newer build and hand off to the installer.

Windows only: the app ships through installer/Toolblox.iss's Inno Setup
installer, which downloads a build from a GitHub release and extracts it
over the existing installation. Updating is the same installer flow again,
just triggered from inside the running app instead of by hand: download the
latest release's installer exe, launch it, and close so it can replace
files that are currently in use.

.github/workflows/release.yml publishes a `<installer>.sha256` text file
alongside every installer exe. download_installer() fetches that companion
file and checks the downloaded exe's digest against it before returning,
so a tampered or corrupted asset never reaches run_installer(). This
doesn't replace code signing (the release itself could still be
compromised at the source), but it does mean the exe that runs is
byte-for-byte what the release published, not something altered in
transit or by a bad mirror.
"""

import hashlib
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

from toolblox.logs import get_logger
from toolblox.version import APP_VERSION

logger = get_logger(__name__)

GITHUB_RELEASES_API = "https://api.github.com/repos/BakedAleska/Toolblox/releases/latest"
INSTALLER_ASSET_PATTERN = re.compile(r"^ToolbloxSetup-.*\.exe$")
MAX_DOWNLOAD_BYTES = 200 * 1024 * 1024


class UpdateError(Exception):
    """Raised when checking for or downloading an update fails."""


@dataclass
class UpdateInfo:
    """One available update, as read from GitHub's latest release."""

    version: str
    download_url: str
    release_notes: str
    sha256_url: Optional[str] = None


def _version_key(raw: str) -> tuple:
    """An ordering key for versions like "0.1.0-beta", "1.2.0", or "v1.0.0".

    Splits the dot-separated numeric part into ints and treats a
    "-suffix" (e.g. "beta", "rc1") as older than the same numbers with no
    suffix, so "1.0.0" outranks "1.0.0-beta". Not a full semver parser,
    but enough to order this project's own release tags.
    """
    raw = raw.lstrip("vV")
    numeric, _, suffix = raw.partition("-")
    parts = tuple(int(p) if p.isdigit() else 0 for p in numeric.split("."))
    return (parts, 0 if suffix else 1, suffix)


def is_newer(candidate: str, current: str) -> bool:
    """Whether `candidate` outranks `current` under _version_key()."""
    return _version_key(candidate) > _version_key(current)


def check_for_update() -> Optional[UpdateInfo]:
    """Check GitHub's latest release for a newer Windows installer.

    Blocking. Call via asyncio.to_thread. Returns None on Windows if
    already up to date, and unconditionally on any other platform since
    there's no installer to hand off to there yet. Raises UpdateError
    with a user-facing message if the release can't be read.
    """
    if sys.platform != "win32":
        return None

    try:
        response = httpx.get(
            GITHUB_RELEASES_API,
            timeout=15,
            headers={"Accept": "application/vnd.github+json"},
        )
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError) as e:
        logger.warning("Couldn't check for updates: %s", e)
        raise UpdateError(f"Couldn't reach GitHub to check for updates. ({e})") from e

    tag = str(data.get("tag_name") or "").strip()
    if not tag:
        raise UpdateError("The latest release on GitHub has no version tag.")

    if not is_newer(tag, APP_VERSION):
        return None

    download_url = None
    sha256_url = None
    for asset in data.get("assets") or []:
        name = asset.get("name") or ""
        if INSTALLER_ASSET_PATTERN.match(name):
            download_url = asset.get("browser_download_url")
        elif name.endswith(".sha256") and INSTALLER_ASSET_PATTERN.match(name[: -len(".sha256")]):
            sha256_url = asset.get("browser_download_url")

    if not download_url:
        raise UpdateError(
            f"Version {tag} is out, but its release has no Windows installer attached."
        )

    return UpdateInfo(
        version=tag.lstrip("vV"),
        download_url=download_url,
        release_notes=str(data.get("body") or ""),
        sha256_url=sha256_url,
    )


def _fetch_expected_sha256(sha256_url: str) -> str:
    """Fetch and parse the plain-text sha256 digest published alongside an installer.

    Raises UpdateError with a user-facing message on any failure.
    """
    try:
        response = httpx.get(sha256_url, timeout=15)
        response.raise_for_status()
    except httpx.HTTPError as e:
        logger.warning("Couldn't download update checksum: %s", e)
        raise UpdateError(f"Couldn't verify the update. Is your connection working? ({e})") from e

    digest = response.text.strip().split()[0].lower()
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise UpdateError("The update's published checksum looks malformed.")
    return digest


def download_installer(update: UpdateInfo) -> Path:
    """Download an update's installer exe to a temp file. Blocking.

    Call via asyncio.to_thread. Raises UpdateError with a user-facing
    message on any failure, including a checksum mismatch against the
    `<installer>.sha256` file released alongside the exe - see this
    module's docstring. If the release has no checksum asset at all
    (shouldn't happen for a release built by release.yml, but could for
    a hand-crafted one), the download is rejected rather than silently
    trusted. The caller owns the returned path and should hand it to
    run_installer() or clean it up itself.
    """
    if not update.sha256_url:
        raise UpdateError(
            "This release has no published checksum for its installer. "
            "Refusing to run it - was it published outside the normal release workflow?"
        )
    expected_sha256 = _fetch_expected_sha256(update.sha256_url)

    fd, tmp_name = tempfile.mkstemp(prefix="ToolbloxSetup-", suffix=".exe")
    tmp_path = Path(tmp_name)

    try:
        hasher = hashlib.sha256()
        with open(fd, "wb") as f:
            try:
                with httpx.stream(
                    "GET", update.download_url, follow_redirects=True, timeout=60
                ) as response:
                    response.raise_for_status()
                    total = 0
                    for chunk in response.iter_bytes():
                        total += len(chunk)
                        if total > MAX_DOWNLOAD_BYTES:
                            raise UpdateError("The installer download exceeded the size limit.")
                        f.write(chunk)
                        hasher.update(chunk)
            except httpx.HTTPError as e:
                logger.warning("Couldn't download update installer: %s", e)
                raise UpdateError(
                    f"Couldn't download the update. Is your connection working? ({e})"
                ) from e

        digest = hasher.hexdigest()
        if digest != expected_sha256:
            logger.warning(
                "Update installer checksum mismatch (expected %s, got %s)",
                expected_sha256,
                digest,
            )
            raise UpdateError(
                "The downloaded update didn't match its published checksum. "
                "Try again, or download it directly from the Releases page."
            )
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise

    return tmp_path


def run_installer(installer_path: Path) -> None:
    """Launch a downloaded installer as a detached process.

    Doesn't wait for it or exit the app itself - the installer's own
    CloseApplications setting closes this app when it needs to replace
    files that are in use. Call this, then let the caller close the
    window on its own terms (see UI code) so the shutdown looks
    intentional rather than like a crash.
    """
    subprocess.Popen([str(installer_path)], close_fds=True)
