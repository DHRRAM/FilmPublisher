"""Folder structure generation for local and synchronized assets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from services.asset_classification import ASSET_DIRECTORIES, AssetFileType


ASSET_SUBFOLDERS = tuple(path.as_posix() for path in ASSET_DIRECTORIES)


@dataclass(frozen=True, slots=True)
class AssetFolderStructure:
    """Paths created for a published asset."""

    root: Path
    thumbnails: Path

    def destination_for(self, file_type: AssetFileType) -> Path:
        """Return the leaf destination for a classified file type."""

        return self.root / file_type.relative_directory


def create_asset_folder_structure(
    asset_root: Path | str,
    asset_name: str,
) -> AssetFolderStructure:
    """Create and return the standard folder structure for an asset.

    The operation is idempotent, so publishing another version of an existing
    asset preserves the current folders and their contents.
    """

    clean_asset_name = _validate_asset_name(asset_name)
    root = Path(asset_root).expanduser() / clean_asset_name

    folders = AssetFolderStructure(
        root=root,
        thumbnails=root / "Thumbnails",
    )
    for relative_directory in ASSET_DIRECTORIES:
        (root / relative_directory).mkdir(parents=True, exist_ok=True)

    return folders


def _validate_asset_name(asset_name: str) -> str:
    if not isinstance(asset_name, str) or not asset_name.strip():
        raise ValueError("Asset name must be a non-empty string.")

    clean_name = asset_name.strip()
    if clean_name in {".", ".."} or Path(clean_name).name != clean_name:
        raise ValueError("Asset name must be a single folder name.")
    if "/" in clean_name or "\\" in clean_name:
        raise ValueError("Asset name must be a single folder name.")

    return clean_name
