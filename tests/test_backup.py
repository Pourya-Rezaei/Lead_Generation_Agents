import sqlite3

import pytest

from src.backup import backup_database, restore_database, verify_database
from src.migrations import migrate


def test_backup_and_restore_verify_sqlite(tmp_path):
    source = tmp_path / "source.db"
    backup = tmp_path / "backup.db"
    restored = tmp_path / "restored.db"
    with sqlite3.connect(source) as connection:
        migrate(connection)
        connection.execute("INSERT INTO schema_metadata(key, value) VALUES ('test', 'ok')")
    backup_database(source, backup)
    restore_database(backup, restored)
    verify_database(restored)
    with sqlite3.connect(restored) as connection:
        assert connection.execute("SELECT value FROM schema_metadata WHERE key = 'test'").fetchone()[0] == "ok"


def test_backup_rejects_same_path(tmp_path):
    source = tmp_path / "source.db"
    with sqlite3.connect(source) as connection:
        migrate(connection)
    with pytest.raises(ValueError):
        backup_database(source, source)
