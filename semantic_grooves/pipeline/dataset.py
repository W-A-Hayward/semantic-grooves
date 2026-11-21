"""Step 0: fetch the Pitchfork reviews database from Kaggle."""
import shutil
import sqlite3
from collections import namedtuple
from pathlib import Path

from ..config import db_path
from .prepare import prepare_database

KAGGLE_DATASET = "nolanbconaway/pitchfork-data"

# path: where the database was written; duplicates_removed: repeated review rows dropped
Fetched = namedtuple("Fetched", "path duplicates_removed")


def download_dataset():
    """Download the Kaggle dataset (cached by kagglehub); returns its directory."""
    try:
        import kagglehub
    except ImportError as e:
        raise RuntimeError(
            "kagglehub is not installed. Run: pip install 'semantic-grooves[build]'"
        ) from e
    return Path(kagglehub.dataset_download(KAGGLE_DATASET))


def fetch_data(dest=None, force=False):
    """Copy the dataset's database.sqlite to `dest` (default: config.db_path()).

    The copy is cleaned (duplicate reviews removed, indexes added) before it is
    moved into place. Refuses to overwrite an existing file unless `force` is
    set, because the destination may hold hours of generated tags and embeddings.
    Returns Fetched(path, duplicates_removed).
    """
    dest = Path(dest) if dest else db_path()
    if dest.exists() and not force:
        raise FileExistsError(f"{dest} already exists (use --force to overwrite it)")

    source = download_dataset() / "database.sqlite"
    if not source.exists():
        raise FileNotFoundError(f"database.sqlite not found in the downloaded dataset ({source.parent})")

    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_name(dest.name + ".part")
    shutil.copyfile(source, partial)
    try:
        db = sqlite3.connect(partial)
        try:
            removed = prepare_database(db)
        finally:
            db.close()
    except sqlite3.DatabaseError as e:
        partial.unlink(missing_ok=True)
        raise RuntimeError(f"the downloaded file is not a usable SQLite database: {e}") from e
    partial.replace(dest)
    return Fetched(dest, removed)
