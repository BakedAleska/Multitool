"""Per-platform protection for sensitive values stored in accounts.json.

Windows: DPAPI (via ctypes, current-user scope, no extra dependency)
encrypts the value. The ciphertext, base64-encoded, is what accounts.json
actually stores.

macOS: the value never touches accounts.json at all. It's stored in the
login Keychain via the `security` command-line tool, keyed by account id,
and accounts.json holds an empty string in its place.

Values written before this protection existed are still readable:
`unprotect` falls back to treating unrecognized input as an
already-plaintext legacy value.
"""

import base64
import binascii
import ctypes
import subprocess
import sys
from ctypes import wintypes

from toolblox.logs import get_logger

logger = get_logger(__name__)

_KEYCHAIN_SERVICE = "Toolblox"


class _DataBlob(ctypes.Structure):
    """Mirrors Windows' DATA_BLOB struct, used by CryptProtectData/Unprotect."""

    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def protect(account_id: int, plaintext: str) -> str:
    """Return the string `accounts.json` should store in place of `plaintext`.

    On Windows this is the DPAPI ciphertext, base64-encoded. On macOS the
    value is written to the login Keychain instead and an empty string is
    returned, so `accounts.json` never holds it at all. On any other
    platform the value is returned unchanged, since there's no OS-level
    secure storage to protect it with.
    """
    if not plaintext:
        return plaintext
    if sys.platform == "win32":
        return _dpapi_protect(plaintext)
    if sys.platform == "darwin":
        _keychain_set(account_id, plaintext)
        return ""
    return plaintext


def unprotect(account_id: int, stored: str) -> str:
    """Recover the plaintext value from what's stored in `accounts.json`.

    On Windows, `stored` is decrypted with DPAPI. On macOS, `stored` is
    ignored and the value is looked up in the login Keychain by
    `account_id` instead, falling back to `stored` itself if nothing is
    found there. On any other platform `stored` is returned unchanged.
    """
    if sys.platform == "win32":
        return _dpapi_unprotect(stored) if stored else stored
    if sys.platform == "darwin":
        return _keychain_get(account_id) or stored
    return stored


def forget(account_id: int) -> None:
    """Remove a value from platform secure storage, if any is kept there.

    Called when an account is removed, so the Keychain doesn't accumulate
    entries for accounts that no longer exist.
    """
    if sys.platform == "darwin":
        _keychain_delete(account_id)


def _dpapi_protect(plaintext: str) -> str:
    """Encrypt with DPAPI, scoped to the current Windows user."""
    data_in = plaintext.encode("utf-8")
    buf_in = ctypes.create_string_buffer(data_in, len(data_in))
    blob_in = _DataBlob(len(data_in), ctypes.cast(buf_in, ctypes.POINTER(ctypes.c_char)))
    blob_out = _DataBlob()
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    ):
        raise ctypes.WinError()
    try:
        ciphertext = ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)
    return base64.b64encode(ciphertext).decode("ascii")


def _dpapi_unprotect(stored: str) -> str:
    """Decrypt a DPAPI blob, falling back to legacy plaintext on failure."""
    try:
        ciphertext = base64.b64decode(stored, validate=True)
    except (ValueError, binascii.Error):
        return stored

    buf_in = ctypes.create_string_buffer(ciphertext, len(ciphertext))
    blob_in = _DataBlob(len(ciphertext), ctypes.cast(buf_in, ctypes.POINTER(ctypes.c_char)))
    blob_out = _DataBlob()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    ):
        logger.warning("CryptUnprotectData failed, treating value as legacy plaintext")
        return stored
    try:
        plaintext = ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)
    return plaintext.decode("utf-8")


def _keychain_account(account_id: int) -> str:
    """Build the Keychain "account" field used to key an entry to one Roblox account id."""
    return f"account-{account_id}"


def _keychain_set(account_id: int, secret: str) -> None:
    """Store or overwrite a secret in the login Keychain for this account id.

    Shells out to `security add-generic-password`. `-U` updates the entry in
    place if one already exists, instead of failing with a duplicate error.
    Failures are silent (`check=False`): a Keychain write failing shouldn't
    crash the app, and there's nothing more useful to do here than leave the
    old entry, if any, as it was.
    """
    subprocess.run(
        [
            "security",
            "add-generic-password",
            "-a",
            _keychain_account(account_id),
            "-s",
            _KEYCHAIN_SERVICE,
            "-w",
            secret,
            "-U",
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def _keychain_get(account_id: int) -> str | None:
    """Read a secret back from the login Keychain for this account id.

    Shells out to `security find-generic-password`. Returns `None` if the
    command fails, which covers both "no entry exists" and any other
    Keychain access error.
    """
    result = subprocess.run(
        [
            "security",
            "find-generic-password",
            "-a",
            _keychain_account(account_id),
            "-s",
            _KEYCHAIN_SERVICE,
            "-w",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _keychain_delete(account_id: int) -> None:
    """Remove this account id's entry from the login Keychain, if any.

    Shells out to `security delete-generic-password`. Failures are silent
    (`check=False`): a missing entry is the common case, not an error.
    """
    subprocess.run(
        [
            "security",
            "delete-generic-password",
            "-a",
            _keychain_account(account_id),
            "-s",
            _KEYCHAIN_SERVICE,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
