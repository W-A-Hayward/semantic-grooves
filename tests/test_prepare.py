import sqlite3

import pytest

from conftest import REVIEWS, SOURCE_CONTENT, build_kaggle_db
from semantic_grooves.pipeline.prepare import prepare_database


@pytest.fixture
def db(tmp_path):
    db = sqlite3.connect(build_kaggle_db(tmp_path / "dup.sqlite"))
    db.execute("CREATE TABLE review_tags (reviewid INTEGER, chunk NVARCHAR, tags NVARCHAR)")
    yield db
    db.close()


def index_names(db):
    return {name for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type = 'index'")}


def test_duplicate_rows_are_removed_and_one_copy_is_kept(db):
    assert db.execute("SELECT COUNT(*) FROM reviews").fetchone()[0] == len(REVIEWS) + 1

    removed = prepare_database(db)

    assert removed == 2                                         # one row each in reviews and content
    assert db.execute("SELECT COUNT(*) FROM reviews WHERE reviewid = 2").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM content WHERE reviewid = 2").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM reviews").fetchone()[0] == len(REVIEWS)


def test_nothing_else_is_touched(db):
    before = db.execute("SELECT * FROM reviews WHERE reviewid != 2 ORDER BY reviewid").fetchall()
    prepare_database(db)
    assert db.execute("SELECT * FROM reviews WHERE reviewid != 2 ORDER BY reviewid").fetchall() == before
    assert dict(db.execute("SELECT reviewid, content FROM content")) == SOURCE_CONTENT


def test_it_is_idempotent(db):
    prepare_database(db)
    assert prepare_database(db) == 0
    assert db.execute("SELECT COUNT(*) FROM reviews").fetchone()[0] == len(REVIEWS)


def test_indexes_are_created_and_reviewid_becomes_unique(db):
    prepare_database(db)
    assert {"reviews_reviewid", "content_reviewid", "review_tags_reviewid"} <= index_names(db)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO reviews VALUES (?, ?, ?, ?, ?)", REVIEWS[0])


def test_it_works_on_a_database_without_the_optional_tables(tmp_path):
    db = sqlite3.connect(tmp_path / "bare.sqlite")
    db.execute("CREATE TABLE reviews (reviewid INTEGER, title TEXT)")
    assert prepare_database(db) == 0
    assert index_names(db) == {"reviews_reviewid"}
    db.close()


def test_the_search_join_uses_the_indexes(db):
    """Without an index SQLite builds a temporary one on every search (about 20 ms)."""
    prepare_database(db)
    plan = " | ".join(row[3] for row in db.execute("""
        EXPLAIN QUERY PLAN
        SELECT rt.rowid, rt.reviewid, rt.tags, r.artist, r.title, r.score, r.url
        FROM review_tags rt INNER JOIN reviews r ON rt.reviewid = r.reviewid
        WHERE rt.rowid IN (1, 2, 3)"""))
    assert "reviews_reviewid" in plan
    assert "AUTOMATIC" not in plan
