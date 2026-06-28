"""Central registry for asset file classification and destination paths."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True, slots=True)
class AssetFileType:
    """A supported file type and its location within an asset folder."""

    key: str
    section: str
    format_name: str
    extensions: tuple[str, ...]

    @property
    def relative_directory(self) -> Path:
        return Path(self.section) / self.format_name

    @property
    def display_name(self) -> str:
        return f"{self.section} / {self.format_name}"


# Add new formats here. Folder generation and all publishing destinations are
# derived from this registry, so consumers do not need format-specific logic.
FILE_TYPE_REGISTRY = (
    AssetFileType("blender", "DCC", "Blender", (".blend",)),
    AssetFileType("houdini", "DCC", "Houdini", (".hip", ".hipnc", ".hiplc")),
    AssetFileType("maya", "DCC", "Maya", (".ma", ".mb")),
    AssetFileType("substance", "DCC", "Substance", (".spp",)),
    AssetFileType("photoshop", "DCC", "Photoshop", (".psd",)),
    AssetFileType("usd", "Publish", "USD", (".usd", ".usda", ".usdc")),
    AssetFileType("alembic", "Publish", "Alembic", (".abc",)),
    AssetFileType("fbx", "Publish", "FBX", (".fbx",)),
    AssetFileType("obj", "Publish", "OBJ", (".obj",)),
    AssetFileType("materialx", "Publish", "MaterialX", (".mtlx",)),
    AssetFileType(
        "texture",
        "Resources",
        "Textures",
        (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".exr", ".tx"),
    ),
)


def _build_extension_registry() -> Mapping[str, AssetFileType]:
    registry: dict[str, AssetFileType] = {}
    for file_type in FILE_TYPE_REGISTRY:
        for extension in file_type.extensions:
            normalized = extension.casefold()
            if normalized in registry:
                raise RuntimeError(f"Duplicate asset extension registered: {extension}")
            registry[normalized] = file_type
    return MappingProxyType(registry)


EXTENSION_REGISTRY = _build_extension_registry()
ASSET_DIRECTORIES = tuple(
    dict.fromkeys(file_type.relative_directory for file_type in FILE_TYPE_REGISTRY)
) + (Path("Thumbnails"),)
SUPPORTED_EXTENSIONS = tuple(EXTENSION_REGISTRY)
THUMBNAIL_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png"})


def classify_asset_file(file_path: Path | str) -> AssetFileType:
    """Return the registered classification for a file or extension."""

    value = str(file_path)
    extension = value if value.startswith(".") and "/" not in value and "\\" not in value else Path(value).suffix
    file_type = EXTENSION_REGISTRY.get(extension.casefold())
    if file_type is None:
        supported = ", ".join(SUPPORTED_EXTENSIONS)
        raise ValueError(
            f"Unsupported asset file extension '{extension or '<none>'}'. "
            f"Supported extensions: {supported}."
        )
    return file_type
