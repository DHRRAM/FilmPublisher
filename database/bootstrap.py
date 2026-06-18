"""SQLite database initialization."""

from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_VERSION = 2


def bootstrap_database(database_path: Path | str) -> Path:
    """Create the SQLite database and baseline schema if needed."""

    resolved_path = Path(database_path).expanduser()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(resolved_path) as connection:
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
                asset_type TEXT NOT NULL,
                created_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS publishes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id INTEGER NOT NULL,
                version INTEGER NOT NULL,
                publish_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                file_path TEXT NOT NULL,
                FOREIGN KEY (asset_id) REFERENCES assets (id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_publishes_asset_id
            ON publishes (asset_id);
            """
        )
        connection.execute(
            "UPDATE schema_version SET version = ? WHERE id = 1;",
            (SCHEMA_VERSION,),
        )

    return resolved_path
