"""Utilities for parsing and selecting versioned publish files."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TypeAlias


VERSION_PADDING = 3
_VERSION_PATTERN = re.compile(
    r"^(?P<name>.+)_v(?P<version>\d{3})(?P<extension>\.[^.]+)$",
    re.IGNORECASE,
)


class HasVersion(Protocol):
    """A database or domain record containing an integer version."""

    version: int


VersionSource: TypeAlias = Path | str | HasVersion


@dataclass(frozen=True, slots=True)
class ParsedVersion:
    """Components extracted from a versioned filename."""

    path: Path
    name: str
    version: int
    extension: str

    @property
    def filename(self) -> str:
        return self.path.name


def parse_version(file_path: Path | str) -> ParsedVersion | None:
    """Parse ``name_vNNN.ext`` and return its components.

    Only positive, three-digit versions are accepted. Non-versioned filenames
    return ``None`` so directory scans can safely ignore unrelated files.
    """

    path = Path(file_path)
    match = _VERSION_PATTERN.fullmatch(path.name)
    if match is None:
        return None

    version = int(match.group("version"))
    if version < 1:
        return None

    return ParsedVersion(
        path=path,
        name=match.group("name"),
        version=version,
        extension=match.group("extension"),
    )


def format_versioned_filename(
    name: str,
    version: int,
    extension: str,
) -> str:
    """Build a filename such as ``dragon_v003.blend``."""

    if not name or Path(name).name != name:
        raise ValueError("Versioned filename name must be a non-empty basename.")
    if version < 1 or version > 999:
        raise ValueError("Version must be between 1 and 999.")

    normalized_extension = extension if extension.startswith(".") else f".{extension}"
    if normalized_extension == "." or Path(normalized_extension).name != normalized_extension:
        raise ValueError("Extension must identify a single file type.")

    return f"{name}_v{version:0{VERSION_PADDING}d}{normalized_extension}"


def get_latest_version(
    sources: VersionSource | Iterable[VersionSource],
    name: str | None = None,
    extension: str | None = None,
) -> int | None:
    """Return the highest version found in files or database records.

    A directory path is scanned non-recursively. An iterable may contain file
    paths or records such as ``PublishRecord``. Optional name and extension
    filters apply to filename sources.
    """

    normalized_extension = _normalize_extension(extension)
    versions: list[int] = []

    for source in _iter_sources(sources):
        record_version = getattr(source, "version", None)
        if isinstance(record_version, int):
            if record_version > 0:
                versions.append(record_version)
            continue

        parsed = parse_version(source)
        if parsed is None:
            continue
        if name is not None and parsed.name != name:
            continue
        if (
            normalized_extension is not None
            and parsed.extension.lower() != normalized_extension.lower()
        ):
            continue
        versions.append(parsed.version)

    return max(versions) if versions else None


def get_next_version(
    sources: VersionSource | Iterable[VersionSource],
    name: str | None = None,
    extension: str | None = None,
) -> int:
    """Return one more than the latest version, starting at version 1."""

    latest = get_latest_version(sources, name=name, extension=extension)
    next_version = 1 if latest is None else latest + 1
    if next_version > 999:
        raise ValueError("Version limit of 999 has been reached.")
    return next_version


def _iter_sources(
    sources: VersionSource | Iterable[VersionSource],
) -> Iterable[VersionSource]:
    if isinstance(sources, (str, Path)):
        path = Path(sources)
        if path.is_dir():
            yield from path.iterdir()
        else:
            yield path
        return

    yield from sources


def _normalize_extension(extension: str | None) -> str | None:
    if extension is None:
        return None
    return extension if extension.startswith(".") else f".{extension}"
