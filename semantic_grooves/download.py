"""Download a prebuilt database (reviews + tags + vectors + full-text index)."""
import hashlib
import sqlite3
import urllib.request
from pathlib import Path

from .config import db_path

# What a database must contain to be usable by the API.
REQUIRED_TABLES = {"reviews", "review_tags", "reviews_vec", "review_text_fts"}
CHUNK = 1024 * 1024


class ChecksumError(ValueError):
    """The downloaded file does not match the expected SHA-256."""


def _validate(path):
    """Raise ValueError unless `path` is an SQLite file holding the tables the API needs."""
    try:
        db = sqlite3.connect(f"{Path(path).resolve().as_uri()}?mode=ro", uri=True)
        try:
            names = {n for (n,) in db.execute("SELECT name FROM sqlite_master")}
        finally:
            db.close()
    except sqlite3.DatabaseError as e:
        raise ValueError(f"the downloaded file is not a usable SQLite database: {e}") from e
    missing = REQUIRED_TABLES - names
    if missing:
        raise ValueError("the downloaded file is not a Semantic Grooves database "
                         f"(missing: {', '.join(sorted(missing))})")


def download_database(url, dest=None, sha256=None, force=False, progress=print):
    """Stream `url` to `dest` (default: config.db_path()), verify it, then move it into place.

    The file is written to `<dest>.part` first and only renamed once its SHA-256
    matches `sha256` (when given) and it looks like a Semantic Grooves database, so
    a failed or tampered download never replaces a good file. Refuses to overwrite an
    existing database unless `force` is set. Returns the destination path.
    """
    dest = Path(dest) if dest else db_path()
    if dest.exists() and not force:
        raise FileExistsError(f"{dest} already exists (use --force to overwrite it)")
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_name(dest.name + ".part")

    digest = hashlib.sha256()
    request = urllib.request.Request(url, headers={"User-Agent": "semantic-grooves"})
    try:
        with urllib.request.urlopen(request) as response, open(partial, "wb") as out:
            total = int(response.headers.get("Content-Length") or 0)
            done = next_report = 0
            while True:
                block = response.read(CHUNK)
                if not block:
                    break
                out.write(block)
                digest.update(block)
                done += len(block)
                if total and done >= next_report:
                    progress(f"  {done / 1e6:,.0f} / {total / 1e6:,.0f} MB ({100 * done // total}%)")
                    next_report = done + max(total // 20, CHUNK)
        if sha256 and digest.hexdigest() != sha256.strip().lower():
            raise ChecksumError(
                f"checksum mismatch: expected {sha256.strip().lower()}, got {digest.hexdigest()}")
        _validate(partial)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    partial.replace(dest)
    return dest
