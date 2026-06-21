"""JSON-backed project configuration management."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any


APP_HOME = Path.home() / ".film_publisher"
DEFAULT_CONFIG_PATH = APP_HOME / "config.json"
DEFAULT_DATABASE_PATH = APP_HOME / "film_publisher.sqlite3"
DEFAULT_PROJECT_ROOT = APP_HOME / "projects" / "default"
LEGACY_LOCAL_BOX_ROOT = APP_HOME / "box"
DEFAULT_BOX_ROOT = Path.home() / "Box"
DEFAULT_ASSET_ROOT = DEFAULT_PROJECT_ROOT / "assets"

REQUIRED_SETTINGS = ("project_name", "project_root", "box_root", "asset_root")


class ConfigValidationError(ValueError):
    """Raised when a configuration file contains invalid settings."""


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Validated runtime configuration for a publishing project."""

    project_name: str = "Film Publisher"
    project_root: Path = DEFAULT_PROJECT_ROOT
    box_root: Path = DEFAULT_BOX_ROOT
    asset_root: Path = DEFAULT_ASSET_ROOT

    @property
    def database_path(self) -> Path:
        """Return the application database location."""

        return DEFAULT_DATABASE_PATH


class ConfigManager:
    """Load, validate, and persist application configuration."""

    def __init__(self, config_path: Path | str | None = None) -> None:
        self.config_path = Path(config_path).expanduser() if config_path else DEFAULT_CONFIG_PATH

    def load(self) -> AppConfig:
        """Load configuration and write defaults when the file or keys are missing."""

        if not self.config_path.exists():
            config = AppConfig()
            self.save(config)
            return config

        try:
            with self.config_path.open("r", encoding="utf-8") as handle:
                raw_config = json.load(handle)
        except json.JSONDecodeError as exc:
            raise ConfigValidationError(
                f"Configuration file is not valid JSON: {self.config_path}"
            ) from exc

        if not isinstance(raw_config, dict):
            raise ConfigValidationError("Configuration must be a JSON object.")

        config = self._from_dict(raw_config)
        migrate_legacy_box_root = (
            config.box_root == LEGACY_LOCAL_BOX_ROOT.resolve()
            and DEFAULT_BOX_ROOT.exists()
        )
        if migrate_legacy_box_root:
            config = replace(config, box_root=DEFAULT_BOX_ROOT.resolve())

        if (
            any(setting not in raw_config for setting in REQUIRED_SETTINGS)
            or migrate_legacy_box_root
        ):
            self.save(config)

        return config

    def save(self, config: AppConfig) -> None:
        """Validate and persist configuration to disk."""

        self._validate(config)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with self.config_path.open("w", encoding="utf-8") as handle:
            json.dump(self._to_dict(config), handle, indent=2)
            handle.write("\n")

    def _from_dict(self, raw_config: dict[str, Any]) -> AppConfig:
        defaults = AppConfig()
        project_name = self._string_setting(
            raw_config, "project_name", defaults.project_name
        )

        config = AppConfig(
            project_name=project_name,
            project_root=self._path_setting(
                raw_config, "project_root", defaults.project_root
            ),
            box_root=self._path_setting(raw_config, "box_root", defaults.box_root),
            asset_root=self._path_setting(
                raw_config, "asset_root", defaults.asset_root
            ),
        )
        self._validate(config)
        return config

    def _string_setting(
        self, raw_config: dict[str, Any], name: str, default: str
    ) -> str:
        value = raw_config.get(name, default)
        if not isinstance(value, str) or not value.strip():
            raise ConfigValidationError(f"'{name}' must be a non-empty string.")
        return value.strip()

    def _path_setting(
        self, raw_config: dict[str, Any], name: str, default: Path
    ) -> Path:
        value = raw_config.get(name, str(default))
        if not isinstance(value, str) or not value.strip():
            raise ConfigValidationError(f"'{name}' must be a non-empty path string.")

        path = Path(value).expanduser()
        if not path.is_absolute():
            path = self.config_path.parent / path
        return path.resolve()

    def _validate(self, config: AppConfig) -> None:
        if not isinstance(config.project_name, str) or not config.project_name.strip():
            raise ConfigValidationError("'project_name' must be a non-empty string.")

        for name in ("project_root", "box_root", "asset_root"):
            value = getattr(config, name)
            if not isinstance(value, Path):
                raise ConfigValidationError(f"'{name}' must be a path.")

    def _to_dict(self, config: AppConfig) -> dict[str, str | None]:
        return {
            "project_name": config.project_name,
            "project_root": str(config.project_root),
            "box_root": str(config.box_root),
            "asset_root": str(config.asset_root),
        }
