"""JSON-backed configuration manager."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


APP_HOME = Path.home() / ".film_publisher"
DEFAULT_CONFIG_PATH = APP_HOME / "config.json"
DEFAULT_DATABASE_PATH = APP_HOME / "film_publisher.sqlite3"


@dataclass(slots=True)
class AppConfig:
    """Runtime configuration for the desktop client."""

    app_name: str = "Film Publisher"
    database_path: Path = DEFAULT_DATABASE_PATH
    box_drive_root: Path | None = None


class ConfigManager:
    """Load and persist application configuration."""

    def __init__(self, config_path: Path | str | None = None) -> None:
        self.config_path = Path(config_path).expanduser() if config_path else DEFAULT_CONFIG_PATH

    def load(self) -> AppConfig:
        """Load configuration, creating defaults on first run."""

        if not self.config_path.exists():
            config = AppConfig()
            self.save(config)
            return config

        with self.config_path.open("r", encoding="utf-8") as handle:
            raw_config = json.load(handle)

        return self._from_dict(raw_config)

    def save(self, config: AppConfig) -> None:
        """Persist configuration to disk."""

        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with self.config_path.open("w", encoding="utf-8") as handle:
            json.dump(self._to_dict(config), handle, indent=2)
            handle.write("\n")

    def _from_dict(self, raw_config: dict[str, Any]) -> AppConfig:
        database_path = raw_config.get("database_path") or str(DEFAULT_DATABASE_PATH)
        box_drive_root = raw_config.get("box_drive_root")

        return AppConfig(
            app_name=raw_config.get("app_name", "Film Publisher"),
            database_path=Path(database_path).expanduser(),
            box_drive_root=Path(box_drive_root).expanduser() if box_drive_root else None,
        )

    def _to_dict(self, config: AppConfig) -> dict[str, str | None]:
        return {
            "app_name": config.app_name,
            "database_path": str(config.database_path),
            "box_drive_root": str(config.box_drive_root) if config.box_drive_root else None,
        }
