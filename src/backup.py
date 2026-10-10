"""SQLite backup and restore helpers with integrity verification."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def backup_database(source_path: str | Path, destination_path: str | Path) -> None:
    source = Path(source_path).expanduser().resolve()
    destination = Path(destination_path).expanduser().resolve()
    if source == destination:
        raise ValueError("backup destination must differ from source")
    if not source.exists():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as source_db, sqlite3.connect(destination) as destination_db:
        source_db.backup(destination_db)
    verify_database(destination)


def verify_database(path: str | Path) -> None:
    database = Path(path).expanduser().resolve()
    if not database.exists():
        raise FileNotFoundError(database)
    with sqlite3.connect(database) as connection:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchone()
    if integrity != ("ok",):
        raise ValueError("database integrity check failed")
    if foreign_keys is not None:
        raise ValueError("database foreign key check failed")


def restore_database(backup_path: str | Path, destination_path: str | Path) -> None:
    backup = Path(backup_path).expanduser().resolve()
    destination = Path(destination_path).expanduser().resolve()
    verify_database(backup)
    if backup == destination:
        raise ValueError("restore destination must differ from backup")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(backup) as source_db, sqlite3.connect(destination) as destination_db:
        source_db.backup(destination_db)
    verify_database(destination)
