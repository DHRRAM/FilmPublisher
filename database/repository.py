"""CRUD operations for Film Publisher's SQLite records."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from core.models import Asset, PublishRecord
from database.bootstrap import bootstrap_database
from services.versioning import parse_version


class SQLiteRepository:
    """Provide CRUD access to assets and publishes in a SQLite database."""

    def __init__(self, database_path: Path | str) -> None:
        self.database_path = bootstrap_database(database_path)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON;")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def create_asset(
        self,
        name: str,
        asset_type: str,
        created_date: str | None = None,
    ) -> Asset:
        """Create and return an asset."""

        with self._connect() as connection:
            if created_date is None:
                cursor = connection.execute(
                    "INSERT INTO assets (name, asset_type) VALUES (?, ?);",
                    (name, asset_type),
                )
            else:
                cursor = connection.execute(
                    """
                    INSERT INTO assets (name, asset_type, created_date)
                    VALUES (?, ?, ?);
                    """,
                    (name, asset_type, created_date),
                )
            row = connection.execute(
                "SELECT * FROM assets WHERE id = ?;",
                (cursor.lastrowid,),
            ).fetchone()
        return self._asset_from_row(row)

    def get_asset(self, asset_id: int) -> Asset | None:
        """Return an asset by ID, or None when it does not exist."""

        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM assets WHERE id = ?;",
                (asset_id,),
            ).fetchone()
        return self._asset_from_row(row) if row is not None else None

    def list_assets(self) -> list[Asset]:
        """Return all assets in insertion order."""

        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM assets ORDER BY id;").fetchall()
        return [self._asset_from_row(row) for row in rows]

    def update_asset(
        self,
        asset_id: int,
        *,
        name: str | None = None,
        asset_type: str | None = None,
        created_date: str | None = None,
    ) -> Asset | None:
        """Update supplied asset fields and return the updated record."""

        changes = {
            "name": name,
            "asset_type": asset_type,
            "created_date": created_date,
        }
        return self._update_record("assets", asset_id, changes, self._asset_from_row)

    def delete_asset(self, asset_id: int) -> bool:
        """Delete an asset and its publishes, returning whether it existed."""

        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM assets WHERE id = ?;",
                (asset_id,),
            )
        return cursor.rowcount > 0

    def create_publish(
        self,
        asset_id: int,
        version: int,
        file_path: Path | str,
        publish_date: str | None = None,
    ) -> PublishRecord:
        """Create a publish whose version matches its versioned filename."""

        parsed = parse_version(file_path)
        if parsed is None:
            raise ValueError(
                "Publish filenames must use the '<name>_vNNN.<ext>' format."
            )
        if parsed.version != version:
            raise ValueError(
                f"Publish version {version} does not match filename version "
                f"{parsed.version}."\
            )

        with self._connect() as connection:
            existing = connection.execute(
                """
                SELECT 1 FROM publishes
                WHERE asset_id = ? AND version = ?;
                """,
                (asset_id, version),
            ).fetchone()
            if existing is not None:
                raise ValueError(
                    f"Asset {asset_id} already has publish version {version}."
                )

            if publish_date is None:
                cursor = connection.execute(
                    """
                    INSERT INTO publishes (asset_id, version, file_path)
                    VALUES (?, ?, ?);
                    """,
                    (asset_id, version, str(file_path)),
                )
            else:
                cursor = connection.execute(
                    """
                    INSERT INTO publishes
                        (asset_id, version, publish_date, file_path)
                    VALUES (?, ?, ?, ?);
                    """,
                    (asset_id, version, publish_date, str(file_path)),
                )
            row = connection.execute(
                "SELECT * FROM publishes WHERE id = ?;",
                (cursor.lastrowid,),
            ).fetchone()
        return self._publish_from_row(row)

    def create_versioned_publish(
        self,
        asset_id: int,
        file_path: Path | str,
        publish_date: str | None = None,
    ) -> PublishRecord:
        """Parse the file version and create the corresponding database record."""

        parsed = parse_version(file_path)
        if parsed is None:
            raise ValueError(
                "Publish filenames must use the '<name>_vNNN.<ext>' format."
            )
        return self.create_publish(
            asset_id=asset_id,
            version=parsed.version,
            file_path=file_path,
            publish_date=publish_date,
        )

    def get_publish(self, publish_id: int) -> PublishRecord | None:
        """Return a publish by ID, or None when it does not exist."""

        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM publishes WHERE id = ?;",
                (publish_id,),
            ).fetchone()
        return self._publish_from_row(row) if row is not None else None

    def list_publishes(self, asset_id: int | None = None) -> list[PublishRecord]:
        """Return all publishes, optionally restricted to one asset."""

        with self._connect() as connection:
            if asset_id is None:
                rows = connection.execute(
                    "SELECT * FROM publishes ORDER BY id;"
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM publishes
                    WHERE asset_id = ?
                    ORDER BY id;
                    """,
                    (asset_id,),
                ).fetchall()
        return [self._publish_from_row(row) for row in rows]

    def get_latest_publish(self, asset_id: int) -> PublishRecord | None:
        """Return the highest-versioned publish for an asset."""

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM publishes
                WHERE asset_id = ?
                ORDER BY version DESC, id DESC
                LIMIT 1;
                """,
                (asset_id,),
            ).fetchone()
        return self._publish_from_row(row) if row is not None else None

    def get_latest_version(self, asset_id: int) -> int | None:
        """Return the latest recorded version for an asset."""

        latest = self.get_latest_publish(asset_id)
        return latest.version if latest is not None else None

    def get_next_version(self, asset_id: int) -> int:
        """Return the next publish version for an asset, starting at 1."""

        latest = self.get_latest_version(asset_id)
        next_version = 1 if latest is None else latest + 1
        if next_version > 999:
            raise ValueError("Version limit of 999 has been reached.")
        return next_version

    def update_publish(
        self,
        publish_id: int,
        *,
        asset_id: int | None = None,
        version: int | None = None,
        publish_date: str | None = None,
        file_path: Path | str | None = None,
    ) -> PublishRecord | None:
        """Update supplied publish fields and return the updated record."""

        changes: dict[str, object | None] = {
            "asset_id": asset_id,
            "version": version,
            "publish_date": publish_date,
            "file_path": str(file_path) if file_path is not None else None,
        }
        return self._update_record(
            "publishes", publish_id, changes, self._publish_from_row
        )

    def delete_publish(self, publish_id: int) -> bool:
        """Delete a publish, returning whether it existed."""

        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM publishes WHERE id = ?;",
                (publish_id,),
            )
        return cursor.rowcount > 0

    def _update_record(self, table, record_id, changes, row_factory):
        supplied = {name: value for name, value in changes.items() if value is not None}
        with self._connect() as connection:
            if supplied:
                assignments = ", ".join(f"{name} = ?" for name in supplied)
                connection.execute(
                    f"UPDATE {table} SET {assignments} WHERE id = ?;",
                    (*supplied.values(), record_id),
                )
            row = connection.execute(
                f"SELECT * FROM {table} WHERE id = ?;",
                (record_id,),
            ).fetchone()
        return row_factory(row) if row is not None else None

    @staticmethod
    def _asset_from_row(row: sqlite3.Row) -> Asset:
        return Asset(
            id=row["id"],
            name=row["name"],
            asset_type=row["asset_type"],
            created_date=row["created_date"],
        )

    @staticmethod
    def _publish_from_row(row: sqlite3.Row) -> PublishRecord:
        return PublishRecord(
            id=row["id"],
            asset_id=row["asset_id"],
            version=row["version"],
            publish_date=row["publish_date"],
            file_path=row["file_path"],
        )
