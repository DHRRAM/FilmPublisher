"""Local and Box Drive asset publishing workflow."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Protocol

from core.models import Asset, PublishRecord
from services.asset_classification import (
    THUMBNAIL_EXTENSIONS,
    classify_asset_file,
)
from services.folder_structure import create_asset_folder_structure
from services.versioning import format_versioned_filename, get_next_version


class PublishRepository(Protocol):
    """Database operations required by the publisher service."""

    def get_asset(self, asset_id: int) -> Asset | None: ...

    def list_publishes(self, asset_id: int | None = None) -> list[PublishRecord]: ...

    def create_publish(
        self,
        asset_id: int,
        version: int,
        file_path: Path | str,
        publish_date: str | None = None,
        thumbnail_path: Path | str | None = None,
    ) -> PublishRecord: ...


class PublisherService:
    """Classify and publish asset files locally and to Box Drive."""

    def __init__(
        self,
        repository: PublishRepository,
        asset_root: Path | str,
        box_root: Path | str,
    ) -> None:
        self._repository = repository
        self._asset_root = Path(asset_root).expanduser()
        self._box_root = Path(box_root).expanduser()

    def publish(self, source_file: Path | str, asset_id: int) -> PublishRecord:
        """Publish a new version of ``source_file`` for an existing asset."""

        source = Path(source_file).expanduser().resolve()
        if not source.is_file():
            raise FileNotFoundError(f"Publish source file does not exist: {source}")
        if not source.suffix:
            raise ValueError("Publish source files must have a file extension.")

        asset = self._repository.get_asset(asset_id)
        if asset is None:
            raise ValueError(f"Asset {asset_id} does not exist.")

        file_type = classify_asset_file(source)
        folders = create_asset_folder_structure(
            self._asset_root,
            asset.name,
        )
        box_folders = create_asset_folder_structure(
            self._box_root,
            asset.name,
        )
        destination = folders.destination_for(file_type)
        box_destination = box_folders.destination_for(file_type)
        version_sources = [
            *self._repository.list_publishes(asset.id),
            *destination.iterdir(),
        ]
        version = get_next_version(version_sources)
        filename = format_versioned_filename(asset.name, version, source.suffix)
        version_path = destination / filename

        shutil.copy2(source, version_path)

        box_version_path = box_destination / filename
        shutil.copy2(version_path, box_version_path)

        thumbnail_path = None
        thumbnail_source = self._find_thumbnail(source)
        if thumbnail_source is not None:
            thumbnail_filename = format_versioned_filename(
                asset.name,
                version,
                thumbnail_source.suffix,
            )
            thumbnail_path = folders.thumbnails / thumbnail_filename
            shutil.copy2(thumbnail_source, thumbnail_path)
            shutil.copy2(
                thumbnail_source,
                box_folders.thumbnails / thumbnail_filename,
            )

        return self._repository.create_publish(
            asset_id=asset.id,
            version=version,
            file_path=version_path,
            thumbnail_path=thumbnail_path,
        )

    @staticmethod
    def _find_thumbnail(source: Path) -> Path | None:
        """Return a deterministic supported image next to the source asset."""

        candidates = sorted(
            (
                path
                for path in source.parent.iterdir()
                if path != source
                and path.is_file()
                and path.suffix.casefold() in THUMBNAIL_EXTENSIONS
            ),
            key=lambda path: (path.stem.casefold() != source.stem.casefold(), path.name.casefold()),
        )
        return candidates[0] if candidates else None
