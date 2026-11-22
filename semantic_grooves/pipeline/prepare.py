"""Make a reviews database clean and fast: drop duplicate rows, add indexes.

Idempotent and safe to run on a database that has already been prepared. It is
applied automatically by `fetch-data`, `build-tags` and `build-index`, and can be
run on its own with `sg prepare-db` to upgrade an existing database.

It also removes chunks that were stored twice (a duplicated review gets tagged
twice), together with their vectors and full-text entries.
"""
from collections import namedtuple

# duplicate_rows: repeated review/content rows; duplicate_chunks: repeated chunks removed
Prepared = namedtuple("Prepared", "duplicate_rows duplicate_chunks")

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


def remove_duplicate_chunks(db):
    """Delete chunks stored twice for a review (keeping the first), plus their
    vectors and full-text entries; returns how many were removed.

    The connection must have sqlite-vec loaded when `reviews_vec` exists.
    """
    if not _table_exists(db, "review_tags"):
        return 0
    extra = [rowid for (rowid,) in db.execute("""
        SELECT rowid FROM review_tags
        WHERE rowid NOT IN (SELECT MIN(rowid) FROM review_tags GROUP BY reviewid, chunk)""")]
    if not extra:
        return 0
    db.executemany("DELETE FROM review_tags WHERE rowid = ?", [(r,) for r in extra])
    if _table_exists(db, "reviews_vec"):
        db.executemany("DELETE FROM reviews_vec WHERE rowid = ?", [(r,) for r in extra])
    if _table_exists(db, "review_text_fts"):  # external-content index: rebuild from review_tags
        db.execute("INSERT INTO review_text_fts(review_text_fts) VALUES ('rebuild')")
    return len(extra)


def create_indexes(db):
    """Index the join keys. Without them SQLite builds a temporary index on every search."""
    for table in _UNIQUE_BY_REVIEWID:
        if _table_exists(db, table):
            db.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS {table}_reviewid ON {table}(reviewid)")
    if _table_exists(db, "review_tags"):
        db.execute("CREATE INDEX IF NOT EXISTS review_tags_reviewid ON review_tags(reviewid)")


def use_rollback_journal(db):
    """Switch the database out of WAL mode; returns the journal mode it ends up in.

    A WAL database cannot be opened from a read-only location (a `:ro` Docker mount, a
    read-only file system): SQLite must create a `-shm` file next to it. The default
    rollback journal has no such need. Needs exclusive access, so the result is still
    "wal" if another process has the database open.
    """
    return db.execute("PRAGMA journal_mode=DELETE").fetchone()[0]


def prepare_database(db):
    """Dedupe, then index; returns Prepared(duplicate_rows, duplicate_chunks)."""
    duplicate_rows = remove_duplicate_reviews(db)
    duplicate_chunks = remove_duplicate_chunks(db)
    create_indexes(db)
    db.commit()
    return Prepared(duplicate_rows, duplicate_chunks)
