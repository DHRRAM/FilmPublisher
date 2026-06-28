"""Domain models for publishable assets, dependencies, and publish history."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Asset:
    """A publishable asset persisted by the application."""

    id: int
    name: str
    created_date: str


@dataclass(frozen=True, slots=True)
class AssetDependency:
    """A directed relationship from one asset to another asset it references."""

    id: int
    asset_id: int
    depends_on_asset_id: int
    dependency_type: str
    created_date: str
    metadata_json: str | None = None


@dataclass(frozen=True, slots=True)
class PublishRecord:
    """A persisted published version of an asset."""

    id: int
    asset_id: int
    version: int
    publish_date: str
    file_path: str
    thumbnail_path: str | None = None
