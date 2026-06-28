"""CRUD operations for Film Publisher's SQLite records."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from core.models import Asset, AssetDependency, PublishRecord
from database.bootstrap import bootstrap_database
from services.versioning import parse_version


class SQLiteRepository:
    """Provide CRUD access to assets, publishes, and dependencies."""

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
        created_date: str | None = None,
    ) -> Asset:
        """Create and return an asset."""

        with self._connect() as connection:
            if created_date is None:
                cursor = connection.execute(
                    "INSERT INTO assets (name) VALUES (?);",
                    (name,),
                )
            else:
                cursor = connection.execute(
                    """
                    INSERT INTO assets (name, created_date)
                    VALUES (?, ?);
                    """,
                    (name, created_date),
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
        created_date: str | None = None,
    ) -> Asset | None:
        """Update supplied asset fields and return the updated record."""

        changes = {
            "name": name,
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

    def add_dependency(
        self,
        asset_id: int,
        depends_on_asset_id: int,
        dependency_type: str = "reference",
        metadata_json: str | None = None,
        created_date: str | None = None,
    ) -> AssetDependency:
        """Create a directed dependency from one asset to another."""

        dependency_type = self._validate_dependency_type(dependency_type)
        if asset_id == depends_on_asset_id:
            raise ValueError("An asset cannot depend on itself.")

        with self._connect() as connection:
            existing_assets = {
                row["id"]
                for row in connection.execute(
                    "SELECT id FROM assets WHERE id IN (?, ?);",
                    (asset_id, depends_on_asset_id),
                ).fetchall()
            }
            missing_assets = [
                str(candidate)
                for candidate in (asset_id, depends_on_asset_id)
                if candidate not in existing_assets
            ]
            if missing_assets:
                raise ValueError(
                    f"Asset(s) do not exist: {', '.join(missing_assets)}."
                )

            existing_dependency = connection.execute(
                """
                SELECT * FROM asset_dependencies
                WHERE asset_id = ?
                    AND depends_on_asset_id = ?
                    AND dependency_type = ?;
                """,
                (asset_id, depends_on_asset_id, dependency_type),
            ).fetchone()
            if existing_dependency is not None:
                raise ValueError(
                    "Dependency already exists for this asset pair and type."
                )

            if created_date is None:
                cursor = connection.execute(
                    """
                    INSERT INTO asset_dependencies
                        (asset_id, depends_on_asset_id, dependency_type, metadata_json)
                    VALUES (?, ?, ?, ?);
                    """,
                    (
                        asset_id,
                        depends_on_asset_id,
                        dependency_type,
                        metadata_json,
                    ),
                )
            else:
                cursor = connection.execute(
                    """
                    INSERT INTO asset_dependencies
                        (
                            asset_id,
                            depends_on_asset_id,
                            dependency_type,
                            created_date,
                            metadata_json
                        )
                    VALUES (?, ?, ?, ?, ?);
                    """,
                    (
                        asset_id,
                        depends_on_asset_id,
                        dependency_type,
                        created_date,
                        metadata_json,
                    ),
                )
            row = connection.execute(
                "SELECT * FROM asset_dependencies WHERE id = ?;",
                (cursor.lastrowid,),
            ).fetchone()
        return self._dependency_from_row(row)

    def remove_dependency(
        self,
        asset_id: int,
        depends_on_asset_id: int,
        dependency_type: str | None = None,
    ) -> bool:
        """Remove dependency records between two assets."""

        with self._connect() as connection:
            if dependency_type is None:
                cursor = connection.execute(
                    """
                    DELETE FROM asset_dependencies
                    WHERE asset_id = ? AND depends_on_asset_id = ?;
                    """,
                    (asset_id, depends_on_asset_id),
                )
            else:
                dependency_type = self._validate_dependency_type(dependency_type)
                cursor = connection.execute(
                    """
                    DELETE FROM asset_dependencies
                    WHERE asset_id = ?
                        AND depends_on_asset_id = ?
                        AND dependency_type = ?;
                    """,
                    (asset_id, depends_on_asset_id, dependency_type),
                )
        return cursor.rowcount > 0

    def delete_dependency(self, dependency_id: int) -> bool:
        """Delete a dependency by ID, returning whether it existed."""

        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM asset_dependencies WHERE id = ?;",
                (dependency_id,),
            )
        return cursor.rowcount > 0

    def list_dependencies(
        self,
        asset_id: int,
        dependency_type: str | None = None,
    ) -> list[AssetDependency]:
        """Return assets referenced by the supplied asset as dependency records."""

        with self._connect() as connection:
            if dependency_type is None:
                rows = connection.execute(
                    """
                    SELECT * FROM asset_dependencies
                    WHERE asset_id = ?
                    ORDER BY id;
                    """,
                    (asset_id,),
                ).fetchall()
            else:
                dependency_type = self._validate_dependency_type(dependency_type)
                rows = connection.execute(
                    """
                    SELECT * FROM asset_dependencies
                    WHERE asset_id = ? AND dependency_type = ?
                    ORDER BY id;
                    """,
                    (asset_id, dependency_type),
                ).fetchall()
        return [self._dependency_from_row(row) for row in rows]

    def list_dependents(
        self,
        asset_id: int,
        dependency_type: str | None = None,
    ) -> list[AssetDependency]:
        """Return assets that reference the supplied asset as dependency records."""

        with self._connect() as connection:
            if dependency_type is None:
                rows = connection.execute(
                    """
                    SELECT * FROM asset_dependencies
                    WHERE depends_on_asset_id = ?
                    ORDER BY id;
                    """,
                    (asset_id,),
                ).fetchall()
            else:
                dependency_type = self._validate_dependency_type(dependency_type)
                rows = connection.execute(
                    """
                    SELECT * FROM asset_dependencies
                    WHERE depends_on_asset_id = ? AND dependency_type = ?
                    ORDER BY id;
                    """,
                    (asset_id, dependency_type),
                ).fetchall()
        return [self._dependency_from_row(row) for row in rows]

    def list_dependency_assets(
        self,
        asset_id: int,
        dependency_type: str | None = None,
    ) -> list[Asset]:
        """Return assets referenced by the supplied asset."""

        with self._connect() as connection:
            if dependency_type is None:
                rows = connection.execute(
                    """
                    SELECT DISTINCT assets.* FROM asset_dependencies
                    JOIN assets
                        ON assets.id = asset_dependencies.depends_on_asset_id
                    WHERE asset_dependencies.asset_id = ?
                    ORDER BY assets.id;
                    """,
                    (asset_id,),
                ).fetchall()
            else:
                dependency_type = self._validate_dependency_type(dependency_type)
                rows = connection.execute(
                    """
                    SELECT DISTINCT assets.* FROM asset_dependencies
                    JOIN assets
                        ON assets.id = asset_dependencies.depends_on_asset_id
                    WHERE asset_dependencies.asset_id = ?
                        AND asset_dependencies.dependency_type = ?
                    ORDER BY assets.id;
                    """,
                    (asset_id, dependency_type),
                ).fetchall()
        return [self._asset_from_row(row) for row in rows]

    def list_dependent_assets(
        self,
        asset_id: int,
        dependency_type: str | None = None,
    ) -> list[Asset]:
        """Return assets that reference the supplied asset."""

        with self._connect() as connection:
            if dependency_type is None:
                rows = connection.execute(
                    """
                    SELECT DISTINCT assets.* FROM asset_dependencies
                    JOIN assets ON assets.id = asset_dependencies.asset_id
                    WHERE asset_dependencies.depends_on_asset_id = ?
                    ORDER BY assets.id;
                    """,
                    (asset_id,),
                ).fetchall()
            else:
                dependency_type = self._validate_dependency_type(dependency_type)
                rows = connection.execute(
                    """
                    SELECT DISTINCT assets.* FROM asset_dependencies
                    JOIN assets ON assets.id = asset_dependencies.asset_id
                    WHERE asset_dependencies.depends_on_asset_id = ?
                        AND asset_dependencies.dependency_type = ?
                    ORDER BY assets.id;
                    """,
                    (asset_id, dependency_type),
                ).fetchall()
        return [self._asset_from_row(row) for row in rows]

    def create_publish(
        self,
        asset_id: int,
        version: int,
        file_path: Path | str,
        publish_date: str | None = None,
        thumbnail_path: Path | str | None = None,
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
                    INSERT INTO publishes
                        (asset_id, version, file_path, thumbnail_path)
                    VALUES (?, ?, ?, ?);
                    """,
                    (
                        asset_id,
                        version,
                        str(file_path),
                        str(thumbnail_path) if thumbnail_path is not None else None,
                    ),
                )
            else:
                cursor = connection.execute(
                    """
                    INSERT INTO publishes
                        (asset_id, version, publish_date, file_path, thumbnail_path)
                    VALUES (?, ?, ?, ?, ?);
                    """,
                    (
                        asset_id,
                        version,
                        publish_date,
                        str(file_path),
                        str(thumbnail_path) if thumbnail_path is not None else None,
                    ),
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
        thumbnail_path: Path | str | None = None,
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
            thumbnail_path=thumbnail_path,
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
        thumbnail_path: Path | str | None = None,
    ) -> PublishRecord | None:
        """Update supplied publish fields and return the updated record."""

        changes: dict[str, object | None] = {
            "asset_id": asset_id,
            "version": version,
            "publish_date": publish_date,
            "file_path": str(file_path) if file_path is not None else None,
            "thumbnail_path": (
                str(thumbnail_path) if thumbnail_path is not None else None
            ),
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
            created_date=row["created_date"],
        )

    @staticmethod
    def _dependency_from_row(row: sqlite3.Row) -> AssetDependency:
        return AssetDependency(
            id=row["id"],
            asset_id=row["asset_id"],
            depends_on_asset_id=row["depends_on_asset_id"],
            dependency_type=row["dependency_type"],
            created_date=row["created_date"],
            metadata_json=row["metadata_json"],
        )

    @staticmethod
    def _publish_from_row(row: sqlite3.Row) -> PublishRecord:
        return PublishRecord(
            id=row["id"],
            asset_id=row["asset_id"],
            version=row["version"],
            publish_date=row["publish_date"],
            file_path=row["file_path"],
            thumbnail_path=row["thumbnail_path"],
        )

    @staticmethod
    def _validate_dependency_type(dependency_type: str) -> str:
        if not isinstance(dependency_type, str) or not dependency_type.strip():
            raise ValueError("Dependency type must bee a non-empty string.")
        return dependency_type.strip()
