"""Domain models for publishable assets and their publish history."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Asset:
    """A publishable asset persisted by the application."""

    id: int
    name: str
    asset_type: str
    created_date: str


@dataclass(frozen=True, slots=True)
class PublishRecord:
    """A persisted published version of an asset."""

    id: int
    asset_id: int
    version: int
    publish_date: str
    file_path: str
