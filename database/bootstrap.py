"""SQLite database initialization."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path


SCHEMA_VERSION = 6


def bootstrap_database(database_path: Path | str) -> Path:
    """Create the SQLite database and baseline schema if needed."""

    resolved_path = Path(database_path).expanduser()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)

    with closing(sqlite3.connect(resolved_path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON;")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_version (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                version INTEGER NOT NULL,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            INSERT OR IGNORE INTO schema_version (id, version)
            VALUES (1, 1);

            CREATE TABLE IF NOT EXISTS assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS publishes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id INTEGER NOT NULL,
                version INTEGER NOT NULL,
                publish_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                file_path TEXT NOT NULL,
                thumbnail_path TEXT,
                FOREIGN KEY (asset_id) REFERENCES assets (id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_publishes_asset_id
            ON publishes (asset_id);

            CREATE INDEX IF NOT EXISTS idx_publishes_asset_version
            ON publishes (asset_id, version DESC);

            CREATE TABLE IF NOT EXISTS asset_dependencies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id INTEGER NOT NULL,
                depends_on_asset_id INTEGER NOT NULL,
                dependency_type TEXT NOT NULL DEFAULT 'reference',
                created_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                metadata_json TEXT,
                CHECK (asset_id != depends_on_asset_id),
                FOREIGN KEY (asset_id) REFERENCES assets (id) ON DELETE CASCADE,
                FOREIGN KEY (depends_on_asset_id)
                    REFERENCES assets (id) ON DELETE CASCADE,
                UNIQUE (asset_id, depends_on_asset_id, dependency_type)
            );

            CREATE INDEX IF NOT EXISTS idx_asset_dependencies_asset_id
            ON asset_dependencies (asset_id, dependency_type);

            CREATE INDEX IF NOT EXISTS idx_asset_dependencies_depends_on_asset_id
            ON asset_dependencies (depends_on_asset_id, dependency_type);
            """
        )
        publish_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(publishes);")
        }
        if "thumbnail_path" not in publish_columns:
            connection.execute(
                "ALTER TABLE publishes ADD COLUMN thumbnail_path TEXT;"
            )
        asset_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(assets);")
        }
        if "asset_type" in asset_columns:
            connection.execute("ALTER TABLE assets DROP COLUMN asset_type;")
        connection.execute(
            "UPDATE schema_version SET version = ? WHERE id = 1;",
            (SCHEMA_VERSION,),
        )
        connection.commit()

    return resolved_path
