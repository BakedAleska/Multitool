"""Fetch and cache the Catalogue: the list of widgets available to install."""

from dataclasses import dataclass
from typing import Optional

import flet as ft
import httpx

from multitool.config import WIDGET_REGISTRY_URL
from multitool.logs import get_logger

logger = get_logger(__name__)

_REGISTRY_CACHE_KEY = "_widget_catalog_cache"


@dataclass
class WidgetSource:
    """Where one Catalogue entry's code lives, pinned to an exact commit."""

    owner: str
    repo: str
    ref: str
    path: str


@dataclass
class CatalogEntry:
    """One widget listed in the Catalogue, as read from registry.json."""

    id: str
    name: str
    description: str
    author: str
    version: str
    icon: Optional[str]
    source: WidgetSource
    sha256: str
    homepage: str


def fetch_registry() -> tuple[list[CatalogEntry], Optional[str]]:
    """Fetch and parse the widget Catalogue.

    Never raises. Returns ([], error_message) on any failure, following
    the same (list, errors) convention as
    multitool.widgets.loader.discover_widgets(). A malformed entry is skipped
    rather than failing the whole fetch.
    """
    try:
        response = httpx.get(WIDGET_REGISTRY_URL, timeout=15)
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError) as e:
        logger.warning("Couldn't fetch widget registry from %s: %s", WIDGET_REGISTRY_URL, e)
        return [], str(e)

    entries: list[CatalogEntry] = []
    for raw in data.get("widgets", []):
        try:
            source_raw = raw["source"]
            entries.append(
                CatalogEntry(
                    id=raw["id"],
                    name=raw["name"],
                    description=raw.get("description", ""),
                    author=raw.get("author", ""),
                    version=raw.get("version", ""),
                    icon=raw.get("icon"),
                    source=WidgetSource(
                        owner=source_raw["owner"],
                        repo=source_raw["repo"],
                        ref=source_raw["ref"],
                        path=source_raw["path"],
                    ),
                    sha256=raw["sha256"],
                    homepage=raw.get("homepage", ""),
                )
            )
        except (KeyError, TypeError) as e:
            logger.warning("Skipped malformed registry entry: %s", e)
            continue

    return entries, None


def get_cached_registry(page: ft.Page) -> list[CatalogEntry]:
    """The Catalogue entries cached for this page, or an empty list."""
    return page.session.store.get(_REGISTRY_CACHE_KEY) or []


def set_cached_registry(page: ft.Page, entries: list[CatalogEntry]) -> None:
    """Cache the Catalogue entries for this page."""
    page.session.store.set(_REGISTRY_CACHE_KEY, entries)
