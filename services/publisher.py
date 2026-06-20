"""Local asset publishing workflow."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Protocol

from core.models import Asset, PublishRecord
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
    ) -> PublishRecord: ...


class PublisherService:
    """Publish source files into the local asset library."""

    def __init__(
        self,
        repository: PublishRepository,
        asset_root: Path | str,
    ) -> None:
        self._repository = repository
        self._asset_root = Path(asset_root).expanduser()

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

        folders = create_asset_folder_structure(
            self._asset_root,
            asset.asset_type,
            asset.name,
        )
        version_sources = [
            *self._repository.list_publishes(asset.id),
            *folders.versions.iterdir(),
        ]
        version = get_next_version(version_sources)
        filename = format_versioned_filename(asset.name, version, source.suffix)
        version_path = folders.versions / filename

        shutil.copy2(source, version_path)
        self._update_latest(version_path, folders.latest)

        return self._repository.create_publish(
            asset_id=asset.id,
            version=version,
            file_path=version_path,
        )

    @staticmethod
    def _update_latest(version_path: Path, latest_folder: Path) -> None:
        """Replace the current local latest file with the new version."""

        latest_path = latest_folder / version_path.name
        temporary_path = latest_folder / f".{version_path.name}.tmp"
        shutil.copy2(version_path, temporary_path)

        for existing_path in latest_folder.iterdir():
            if existing_path != temporary_path and (
                existing_path.is_file() or existing_path.is_symlink()
            ):
                existing_path.unlink()

        temporary_path.replace(latest_path)
