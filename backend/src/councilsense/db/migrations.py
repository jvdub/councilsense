from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


MIGRATIONS_DIR = Path(__file__).with_name("migrations")
MIGRATIONS_TABLE = "schema_migrations"


@dataclass(frozen=True)
class MigrationStatus:
    applied: tuple[str, ...]
    pending: tuple[str, ...]


def _ensure_migrations_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {MIGRATIONS_TABLE} (
            name TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def _migration_names() -> tuple[str, ...]:
    return tuple(path.name for path in sorted(MIGRATIONS_DIR.glob("*.sql")))


def _applied_migration_names(connection: sqlite3.Connection) -> tuple[str, ...]:
    rows = connection.execute(f"SELECT name FROM {MIGRATIONS_TABLE} ORDER BY name").fetchall()
    return tuple(str(row[0]) for row in rows)


def get_migration_status(connection: sqlite3.Connection) -> MigrationStatus:
    _ensure_migrations_table(connection)
    all_migrations = _migration_names()
    applied = _applied_migration_names(connection)
    applied_set = set(applied)
    pending = tuple(name for name in all_migrations if name not in applied_set)
    return MigrationStatus(applied=applied, pending=pending)


def apply_migrations(connection: sqlite3.Connection) -> tuple[str, ...]:
    _ensure_migrations_table(connection)
    status = get_migration_status(connection)
    applied_now: list[str] = []

    for migration_name in status.pending:
        migration_path = MIGRATIONS_DIR / migration_name
        sql = migration_path.read_text(encoding="utf-8")

        with connection:
            connection.executescript(sql)
            connection.execute(
                f"INSERT INTO {MIGRATIONS_TABLE} (name) VALUES (?)",
                (migration_name,),
            )

        applied_now.append(migration_name)

    return tuple(applied_now)
