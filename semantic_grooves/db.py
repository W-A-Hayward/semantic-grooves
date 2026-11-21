"""SQLite connections with the sqlite-vec extension loaded."""
import sqlite3

import sqlite_vec

from .config import db_path


def connect(path=None):
    """Open a connection to the search database (default: config.db_path())."""
    db = sqlite3.connect(path or db_path())
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    return db
