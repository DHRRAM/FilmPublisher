"""SQLite database initialization."""

from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_VERSION = 1


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
            """
        )
        connection.execute(
            "UPDATE schema_version SET version = ? WHERE id = 1;",
            (SCHEMA_VERSION,),
        )

    return resolved_path
