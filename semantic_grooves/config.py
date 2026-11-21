"""Paths and model names shared across the package."""
import os
from pathlib import Path

# Repository root when running from a checkout.
ROOT = Path(__file__).resolve().parent.parent

# Sentence-embedding model used for both queries and documents (1024 dimensions).
MODEL_NAME = "BAAI/bge-large-en-v1.5"


def db_path():
    """Path of the SQLite database: $SG_DB_PATH, else <repo>/database.sqlite."""
    return Path(os.environ.get("SG_DB_PATH", ROOT / "database.sqlite"))
