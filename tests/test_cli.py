import hashlib
import shutil
import sqlite3

import pytest

from conftest import CHUNKS, StubEmbedder, StubModel, StubOllama, build_kaggle_db
from semantic_grooves import cli, embedding, search
from semantic_grooves.pipeline import dataset, tagging


def test_version(capsys):
    with pytest.raises(SystemExit) as e:
        cli.main(["--version"])
    assert e.value.code == 0
    assert "sg " in capsys.readouterr().out


def test_a_command_is_required():
    with pytest.raises(SystemExit):
        cli.main([])


# --- search ---

def test_search_prints_ranked_albums(db_path, monkeypatch, capsys):
    monkeypatch.setenv("SG_DB_PATH", db_path)
    monkeypatch.setattr(embedding, "get_model", lambda: StubModel())

    assert cli.main(["search", "slow", "ambient", "music", "-n", "2"]) == 0

    out = capsys.readouterr().out
    assert " 1. alpha - album one" in out
    assert "ambient" in out                      # the tags line
    assert " 3. " not in out                     # -n 2 limits the list


def test_search_without_results(db_path, monkeypatch, capsys):
    monkeypatch.setenv("SG_DB_PATH", db_path)
    monkeypatch.setattr(embedding, "get_model", lambda: StubModel())
    monkeypatch.setattr(search, "search_albums", lambda *a, **k: [])
    assert cli.main(["search", "anything"]) == 0
    assert "No results." in capsys.readouterr().out


# --- serve ---

def test_serve_passes_host_port_and_debug_to_flask(monkeypatch):
    from semantic_grooves import api
    calls = []
    monkeypatch.setattr(api.app, "run", lambda **kw: calls.append(kw))

    assert cli.main(["serve", "--host", "0.0.0.0", "--port", "8080"]) == 0
    assert cli.main(["serve", "--debug"]) == 0
    assert calls == [
        {"host": "0.0.0.0", "port": 8080, "debug": False},
        {"host": "127.0.0.1", "port": 5000, "debug": True},
    ]


# --- fetch-data ---

@pytest.fixture
def fake_kaggle(tmp_path, monkeypatch):
    folder = tmp_path / "kaggle-cache"
    folder.mkdir()
    build_kaggle_db(folder / "database.sqlite")          # contains one duplicated review
    monkeypatch.setattr(dataset, "download_dataset", lambda: folder)


def count_reviews(path):
    db = sqlite3.connect(path)
    try:
        return db.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
    finally:
        db.close()


def test_fetch_data_copies_and_cleans_the_database(fake_kaggle, tmp_path, capsys):
    dest = tmp_path / "out" / "database.sqlite"
    assert cli.main(["fetch-data", "--dest", str(dest)]) == 0

    assert count_reviews(dest) == 3                      # the duplicate row is gone
    assert not (tmp_path / "out" / "database.sqlite.part").exists()
    out = capsys.readouterr().out
    assert "Saved" in out and "Removed 2 duplicate review rows." in out


def test_fetch_data_uses_sg_db_path_by_default(fake_kaggle, tmp_path, monkeypatch):
    dest = tmp_path / "from-env.sqlite"
    monkeypatch.setenv("SG_DB_PATH", str(dest))
    assert cli.main(["fetch-data"]) == 0
    assert count_reviews(dest) == 3


def test_fetch_data_never_overwrites_without_force(fake_kaggle, tmp_path, capsys):
    dest = tmp_path / "database.sqlite"
    dest.write_bytes(b"hours of embeddings")

    assert cli.main(["fetch-data", "--dest", str(dest)]) == 1
    assert dest.read_bytes() == b"hours of embeddings"
    assert "--force" in capsys.readouterr().err

    assert cli.main(["fetch-data", "--dest", str(dest), "--force"]) == 0
    assert count_reviews(dest) == 3


def test_fetch_data_rejects_a_file_that_is_not_a_database(tmp_path, monkeypatch, capsys):
    folder = tmp_path / "kaggle-cache"
    folder.mkdir()
    (folder / "database.sqlite").write_bytes(b"this is not sqlite, " * 100)
    monkeypatch.setattr(dataset, "download_dataset", lambda: folder)
    dest = tmp_path / "database.sqlite"

    assert cli.main(["fetch-data", "--dest", str(dest)]) == 1
    assert "not a usable SQLite database" in capsys.readouterr().err
    assert not dest.exists() and not (tmp_path / "database.sqlite.part").exists()


def test_prepare_db_cleans_an_existing_database(tmp_path, monkeypatch, capsys):
    path = build_kaggle_db(tmp_path / "old.sqlite")
    monkeypatch.setenv("SG_DB_PATH", path)

    assert cli.main(["prepare-db"]) == 0
    assert "Removed 2 duplicate rows and 0 duplicate chunks. Indexes are in place." in capsys.readouterr().out
    assert count_reviews(path) == 3

    assert cli.main(["prepare-db"]) == 0                 # safe to repeat
    assert "Removed 0 duplicate rows and 0 duplicate chunks." in capsys.readouterr().out


def test_fetch_data_explains_a_missing_kagglehub(tmp_path, monkeypatch, capsys):
    import builtins
    real_import = builtins.__import__

    def no_kaggle(name, *args, **kwargs):
        if name == "kagglehub":
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_kaggle)
    assert cli.main(["fetch-data", "--dest", str(tmp_path / "x.sqlite")]) == 1
    assert "semantic-grooves[build]" in capsys.readouterr().err


# --- build-tags / build-index ---

def test_build_tags_tags_pending_reviews(source_db_path, monkeypatch, capsys):
    monkeypatch.setenv("SG_DB_PATH", source_db_path)
    monkeypatch.setattr(tagging, "make_client", lambda: StubOllama())

    assert cli.main(["build-tags", "--limit", "2"]) == 0

    assert "Tagged 2 reviews." in capsys.readouterr().out
    db = sqlite3.connect(source_db_path)
    assert db.execute("SELECT COUNT(DISTINCT reviewid) FROM review_tags").fetchone()[0] == 2


def test_build_tags_reports_reviews_that_got_no_tags(source_db_path, monkeypatch, capsys):
    monkeypatch.setenv("SG_DB_PATH", source_db_path)
    monkeypatch.setattr(tagging, "make_client", lambda: StubOllama(fail_on=["short and sweet"]))

    assert cli.main(["build-tags"]) == 0
    assert "Tagged 2 reviews. 1 got no tags and will be retried" in capsys.readouterr().out


def test_build_tags_fails_when_ollama_is_unreachable(source_db_path, monkeypatch, capsys):
    db = sqlite3.connect(source_db_path)
    db.executemany("INSERT INTO content VALUES (?, ?)", [(100 + i, f"filler {i}") for i in range(15)])
    db.commit()
    db.close()
    monkeypatch.setenv("SG_DB_PATH", source_db_path)
    monkeypatch.setattr(tagging, "make_client", lambda: StubOllama(fail_on=[""]))

    assert cli.main(["build-tags"]) == 1
    assert "ollama serve" in capsys.readouterr().err


def test_build_tags_reports_a_missing_ollama(source_db_path, monkeypatch, capsys):
    def missing():
        raise RuntimeError("ollama is not installed")

    monkeypatch.setenv("SG_DB_PATH", source_db_path)
    monkeypatch.setattr(tagging, "make_client", missing)
    assert cli.main(["build-tags"]) == 1
    assert "ollama is not installed" in capsys.readouterr().err


def test_build_index_indexes_the_tagged_chunks(tagged_db_path, monkeypatch, capsys):
    monkeypatch.setenv("SG_DB_PATH", tagged_db_path)
    monkeypatch.setattr(embedding, "get_model", lambda: StubEmbedder())

    assert cli.main(["build-index"]) == 0
    assert f"Indexed {len(CHUNKS)} new chunks." in capsys.readouterr().out

    assert cli.main(["build-index"]) == 0
    assert "Indexed 0 new chunks." in capsys.readouterr().out


# --- serve --static ---

def test_serve_can_serve_a_built_frontend(tmp_path, monkeypatch):
    from flask import Flask
    from semantic_grooves import api
    site = tmp_path / "dist"
    site.mkdir()
    (site / "index.html").write_text("<html>hi</html>")
    registered, ran = [], []
    monkeypatch.setattr(api, "register_frontend", lambda app, d: registered.append(str(d)))
    monkeypatch.setattr(api.app, "run", lambda **kw: ran.append(kw))

    assert cli.main(["serve", "--static", str(site)]) == 0
    assert registered == [str(site)] and ran


def test_serve_reports_a_missing_frontend_build(tmp_path, capsys):
    assert cli.main(["serve", "--static", str(tmp_path / "nope")]) == 1
    assert "index.html" in capsys.readouterr().err


# --- download-db ---

@pytest.fixture
def published(db_path, tmp_path):
    path = tmp_path / "published" / "database.sqlite"
    path.parent.mkdir()
    shutil.copy(db_path, path)
    return path.as_uri(), hashlib.sha256(path.read_bytes()).hexdigest()


def test_download_db_installs_a_verified_database(published, tmp_path, capsys):
    url, digest = published
    dest = tmp_path / "data" / "database.sqlite"
    assert cli.main(["download-db", "--url", url, "--sha256", digest, "--dest", str(dest)]) == 0
    assert "Saved" in capsys.readouterr().out
    assert hashlib.sha256(dest.read_bytes()).hexdigest() == digest


def test_download_db_reads_url_and_checksum_from_the_environment(published, tmp_path, monkeypatch):
    url, digest = published
    dest = tmp_path / "database.sqlite"
    monkeypatch.setenv("SG_DB_URL", url)
    monkeypatch.setenv("SG_DB_SHA256", digest)
    monkeypatch.setenv("SG_DB_PATH", str(dest))
    assert cli.main(["download-db"]) == 0
    assert dest.exists()


def test_download_db_needs_a_url(monkeypatch, capsys):
    monkeypatch.delenv("SG_DB_URL", raising=False)
    assert cli.main(["download-db"]) == 1
    assert "no URL" in capsys.readouterr().err


def test_download_db_needs_a_checksum_unless_told_otherwise(published, tmp_path, monkeypatch, capsys):
    url, _ = published
    monkeypatch.delenv("SG_DB_SHA256", raising=False)
    dest = tmp_path / "database.sqlite"

    assert cli.main(["download-db", "--url", url, "--dest", str(dest)]) == 1
    assert "no checksum" in capsys.readouterr().err
    assert not dest.exists()

    assert cli.main(["download-db", "--url", url, "--dest", str(dest), "--no-verify"]) == 0
    assert "skipping checksum" in capsys.readouterr().err
    assert dest.exists()


def test_download_db_rejects_a_tampered_file(published, tmp_path, capsys):
    url, _ = published
    dest = tmp_path / "database.sqlite"
    assert cli.main(["download-db", "--url", url, "--sha256", "f" * 64, "--dest", str(dest)]) == 1
    assert "checksum mismatch" in capsys.readouterr().err
    assert not dest.exists()


# --- read-only deployment (WAL databases cannot be opened from a read-only directory) ---

import os

needs_non_root = pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file permissions")


def wal_database(tmp_path, source):
    """A copy of the fixture database in WAL mode, inside a directory we can lock down."""
    folder = tmp_path / "data"
    folder.mkdir()
    path = folder / "database.sqlite"
    shutil.copy(source, path)
    db = sqlite3.connect(path)
    db.execute("PRAGMA journal_mode=WAL")
    db.commit()
    db.close()
    for leftover in folder.iterdir():
        if leftover.name != "database.sqlite":
            leftover.unlink()
    return path


def lock_down(path):
    os.chmod(path, 0o444)
    os.chmod(path.parent, 0o555)


def unlock(path):
    os.chmod(path.parent, 0o755)
    os.chmod(path, 0o644)


def test_prepare_db_takes_the_database_out_of_wal_mode(db_path, tmp_path, monkeypatch, capsys):
    from semantic_grooves.db import is_wal
    path = wal_database(tmp_path, db_path)
    monkeypatch.setenv("SG_DB_PATH", str(path))
    assert is_wal(path)

    assert cli.main(["prepare-db"]) == 0

    assert "Journal mode: delete." in capsys.readouterr().out
    assert not is_wal(path)


@needs_non_root
def test_a_wal_database_cannot_be_served_read_only_until_prepared(db_path, tmp_path, monkeypatch):
    from semantic_grooves import api
    path = wal_database(tmp_path, db_path)
    monkeypatch.setenv("SG_DB_PATH", str(path))
    client = api.app.test_client()

    lock_down(path)
    try:
        resp = client.get("/api/health")
        assert resp.status_code == 503
        assert "WAL mode" in resp.get_json()["error"] and "sg prepare-db" in resp.get_json()["error"]
    finally:
        unlock(path)

    assert cli.main(["prepare-db"]) == 0
    lock_down(path)
    try:
        assert client.get("/api/health").get_json() == {"status": "ok"}
    finally:
        unlock(path)
