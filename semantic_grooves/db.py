"""SQLite connections with the sqlite-vec extension loaded."""
import sqlite3
from pathlib import Path

import sqlite_vec

from .config import db_path


def is_wal(path):
    """True when the SQLite file at `path` is in WAL journal mode (read from its header)."""
    try:
        with open(path, "rb") as f:
            header = f.read(20)
    except OSError:
        return False
    return len(header) == 20 and header[:16] == b"SQLite format 3\x00" and header[18] == 2


def connect(path=None, read_only=False):
    """Open a connection to the search database (default: config.db_path()).

    With read_only=True the file is opened with `mode=ro`: writes fail, and the
    database can live on a read-only volume. Serving and searching only read.
    """
    path = path or db_path()
    if read_only:
        db = sqlite3.connect(f"{Path(path).resolve().as_uri()}?mode=ro", uri=True)
    else:
        db = sqlite3.connect(path)
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    return db
