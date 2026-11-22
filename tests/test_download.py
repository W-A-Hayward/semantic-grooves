import hashlib
import http.server
import shutil
import sqlite3
import threading

import pytest

from conftest import build_kaggle_db
from semantic_grooves import download
from semantic_grooves.download import ChecksumError, download_database


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


@pytest.fixture
def release(db_path, tmp_path):
    """A published database: file, its file:// URL and its checksum."""
    published = tmp_path / "published" / "database.sqlite"
    published.parent.mkdir()
    shutil.copy(db_path, published)
    return {"path": published, "url": published.as_uri(), "sha256": sha(published)}


def test_downloads_verifies_and_installs(release, tmp_path):
    dest = tmp_path / "data" / "database.sqlite"
    assert download_database(release["url"], dest, sha256=release["sha256"], progress=lambda m: None) == dest
    assert sha(dest) == release["sha256"]
    assert not (tmp_path / "data" / "database.sqlite.part").exists()


def test_the_checksum_is_case_and_whitespace_insensitive(release, tmp_path):
    dest = tmp_path / "database.sqlite"
    download_database(release["url"], dest, sha256=f"  {release['sha256'].upper()}\n", progress=lambda m: None)
    assert dest.exists()


def test_a_wrong_checksum_is_rejected_and_nothing_is_installed(release, tmp_path):
    dest = tmp_path / "database.sqlite"
    with pytest.raises(ChecksumError, match="checksum mismatch"):
        download_database(release["url"], dest, sha256="0" * 64, progress=lambda m: None)
    assert not dest.exists()
    assert not (tmp_path / "database.sqlite.part").exists()


def test_a_failed_download_never_replaces_a_good_database(release, tmp_path):
    dest = tmp_path / "database.sqlite"
    dest.write_bytes(b"the good one")
    with pytest.raises(ChecksumError):
        download_database(release["url"], dest, sha256="0" * 64, force=True, progress=lambda m: None)
    assert dest.read_bytes() == b"the good one"


def test_refuses_to_overwrite_without_force(release, tmp_path):
    dest = tmp_path / "database.sqlite"
    dest.write_bytes(b"hours of embeddings")
    with pytest.raises(FileExistsError, match="--force"):
        download_database(release["url"], dest, sha256=release["sha256"])
    assert dest.read_bytes() == b"hours of embeddings"

    download_database(release["url"], dest, sha256=release["sha256"], force=True, progress=lambda m: None)
    assert sha(dest) == release["sha256"]


def test_a_file_that_is_not_sqlite_is_rejected(tmp_path):
    junk = tmp_path / "junk.bin"
    junk.write_bytes(b"this is not a database " * 100)
    dest = tmp_path / "database.sqlite"
    with pytest.raises(ValueError, match="not a usable SQLite database"):
        download_database(junk.as_uri(), dest, sha256=sha(junk), progress=lambda m: None)
    assert not dest.exists() and not (tmp_path / "database.sqlite.part").exists()


def test_a_sqlite_file_without_our_tables_is_rejected(tmp_path):
    other = build_kaggle_db(tmp_path / "kaggle.sqlite")      # reviews + content only: no tags, no vectors
    dest = tmp_path / "database.sqlite"
    with pytest.raises(ValueError, match="missing: .*review_tags.*reviews_vec"):
        download_database(tmp_path.joinpath("kaggle.sqlite").as_uri(), dest, sha256=sha(other),
                          progress=lambda m: None)
    assert not dest.exists()


def test_it_works_over_http_and_reports_progress(release, tmp_path, monkeypatch):
    directory = release["path"].parent

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(directory), **k)

        def log_message(self, *a):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(download, "CHUNK", 4096)               # several reads, so progress is reported
    messages = []
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/database.sqlite"
        dest = tmp_path / "out.sqlite"
        download_database(url, dest, sha256=release["sha256"], progress=messages.append)
    finally:
        server.shutdown()
    assert sha(dest) == release["sha256"]
    assert messages and messages[-1].endswith("(100%)")


def test_an_unreachable_url_fails_cleanly(tmp_path):
    dest = tmp_path / "database.sqlite"
    with pytest.raises(OSError):
        download_database((tmp_path / "does-not-exist").as_uri(), dest)
    assert not dest.exists() and not (tmp_path / "database.sqlite.part").exists()


def test_the_downloaded_database_opens_in_the_api(release, tmp_path, monkeypatch):
    from semantic_grooves import api
    dest = tmp_path / "database.sqlite"
    download_database(release["url"], dest, sha256=release["sha256"], progress=lambda m: None)
    monkeypatch.setenv("SG_DB_PATH", str(dest))
    assert api.app.test_client().get("/api/health").get_json() == {"status": "ok"}
