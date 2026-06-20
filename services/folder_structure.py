"""Folder structure generation for published assets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


SUPPORTED_CATEGORIES = ("Characters", "Props", "Environment")
ASSET_SUBFOLDERS = ("Versions", "Latest", "Thumbnails")


@dataclass(frozen=True, slots=True)
class AssetFolderStructure:
    """Paths created for a published asset."""

    root: Path
    versions: Path
    latest: Path
    thumbnails: Path


def create_asset_folder_structure(
    asset_root: Path | str,
    category: str,
    asset_name: str,
) -> AssetFolderStructure:
    """Create and return the standard folder structure for an asset.

    The operation is idempotent, so publishing another version of an existing
    asset preserves the current folders and their contents.
    """

    canonical_category = _canonical_category(category)
    clean_asset_name = _validate_asset_name(asset_name)
    root = Path(asset_root).expanduser() / canonical_category / clean_asset_name

    folders = AssetFolderStructure(
        root=root,
        versions=root / "Versions",
        latest=root / "Latest",
        thumbnails=root / "Thumbnails",
    )
    for folder in (folders.versions, folders.latest, folders.thumbnails):
        folder.mkdir(parents=True, exist_ok=True)

    return folders


def _canonical_category(category: str) -> str:
    if not isinstance(category, str) or not category.strip():
        raise ValueError("Asset category must be a non-empty string.")

    normalized = category.strip().casefold()
    for supported_category in SUPPORTED_CATEGORIES:
        if supported_category.casefold() == normalized:
            return supported_category

    supported = ", ".join(SUPPORTED_CATEGORIES)
    raise ValueError(
        f"Unsupported asset category '{category}'. Supported categories: {supported}."
    )


def _validate_asset_name(asset_name: str) -> str:
    if not isinstance(asset_name, str) or not asset_name.strip():
        raise ValueError("Asset name must be a non-empty string.")

    clean_name = asset_name.strip()
    if clean_name in {".", ".."} or Path(clean_name).name != clean_name:
        raise ValueError("Asset name must be a single folder name.")
    if "/" in clean_name or "\\" in clean_name:
        raise ValueError("Asset name must be a single folder name.")

    return clean_name
