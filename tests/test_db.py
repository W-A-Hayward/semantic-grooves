import sqlite3

import pytest

from semantic_grooves.db import connect


def test_read_only_connection_can_search_but_not_write(db_path):
    db = connect(db_path, read_only=True)
    try:
        assert db.execute("SELECT COUNT(*) FROM review_tags").fetchone()[0] == 5
        assert db.execute("SELECT vec_version()").fetchone()[0]          # sqlite-vec is loaded
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            db.execute("CREATE TABLE should_fail (x)")
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            db.execute("DELETE FROM reviews")
    finally:
        db.close()


def test_read_only_connection_does_not_create_a_missing_file(tmp_path):
    missing = tmp_path / "nope.sqlite"
    with pytest.raises(sqlite3.OperationalError):
        connect(missing, read_only=True)
    assert not missing.exists()


def test_read_only_works_for_paths_with_spaces_and_unicode(tmp_path, db_path):
    import shutil
    odd = tmp_path / "my data" / "basé #1.sqlite"
    odd.parent.mkdir()
    shutil.copy(db_path, odd)
    db = connect(odd, read_only=True)
    assert db.execute("SELECT COUNT(*) FROM reviews").fetchone()[0] == 3
    db.close()


def test_default_connection_is_writable(tmp_path):
    db = connect(tmp_path / "new.sqlite")
    db.execute("CREATE TABLE t (x)")
    db.close()


def test_connect_uses_sg_db_path(db_path, monkeypatch):
    monkeypatch.setenv("SG_DB_PATH", db_path)
    db = connect(read_only=True)
    assert db.execute("SELECT COUNT(*) FROM reviews").fetchone()[0] == 3
    db.close()
