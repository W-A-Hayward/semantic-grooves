"""Make a reviews database clean and fast: drop duplicate rows, add indexes.

Idempotent and safe to run on a database that has already been prepared. It is
applied automatically by `fetch-data`, `build-tags` and `build-index`, and can be
run on its own with `sg prepare-db` to upgrade an existing database.
"""

# Tables copied from the Kaggle dataset. The dataset lists a few reviews twice
# (exact duplicate rows), which makes `reviewid` unusable as a key.
_UNIQUE_BY_REVIEWID = ("reviews", "content")


def _table_exists(db, name):
    return db.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)).fetchone() is not None


def remove_duplicate_reviews(db):
    """Delete repeated rows (same reviewid), keeping the first; returns rows removed."""
    removed = 0
    for table in _UNIQUE_BY_REVIEWID:
        if _table_exists(db, table):
            removed += db.execute(
                f"DELETE FROM {table} WHERE rowid NOT IN (SELECT MIN(rowid) FROM {table} GROUP BY reviewid)"
            ).rowcount
    return removed


def create_indexes(db):
    """Index the join keys. Without them SQLite builds a temporary index on every search."""
    for table in _UNIQUE_BY_REVIEWID:
        if _table_exists(db, table):
            db.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS {table}_reviewid ON {table}(reviewid)")
    if _table_exists(db, "review_tags"):
        db.execute("CREATE INDEX IF NOT EXISTS review_tags_reviewid ON review_tags(reviewid)")


def prepare_database(db):
    """Dedupe, then index; returns the number of duplicate rows removed."""
    removed = remove_duplicate_reviews(db)
    create_indexes(db)
    db.commit()
    return removed
