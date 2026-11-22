import sqlite3

import pytest

from conftest import AMBIENT_QUERY, CHUNKS, REVIEWS, SOURCE_CONTENT, build_kaggle_db
from semantic_grooves import search
from semantic_grooves.db import connect
from semantic_grooves.pipeline.prepare import prepare_database, use_rollback_journal


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

    removed = prepare_database(db).duplicate_rows

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
    assert prepare_database(db) == (0, 0)
    assert db.execute("SELECT COUNT(*) FROM reviews").fetchone()[0] == len(REVIEWS)


def test_indexes_are_created_and_reviewid_becomes_unique(db):
    prepare_database(db)
    assert {"reviews_reviewid", "content_reviewid", "review_tags_reviewid"} <= index_names(db)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO reviews VALUES (?, ?, ?, ?, ?)", REVIEWS[0])


def test_it_works_on_a_database_without_the_optional_tables(tmp_path):
    db = sqlite3.connect(tmp_path / "bare.sqlite")
    db.execute("CREATE TABLE reviews (reviewid INTEGER, title TEXT)")
    assert prepare_database(db) == (0, 0)
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


# --- chunks stored twice (a duplicated review is tagged twice) ---

def add_duplicate_of_chunk_1(path):
    """Copy chunk 1 (review 1) as rowid 6 into review_tags, reviews_vec and the FTS index."""
    db = connect(path)
    rowid, reviewid, tags, chunk, vector = CHUNKS[0]
    db.execute("INSERT INTO review_tags(rowid, reviewid, chunk, tags) VALUES (6, ?, ?, ?)", (reviewid, chunk, tags))
    db.execute("INSERT INTO reviews_vec(rowid, embedding) VALUES (6, ?)", (vector.tobytes(),))
    db.execute("INSERT INTO review_text_fts(rowid, tags, chunk) VALUES (6, ?, ?)", (tags, chunk))
    db.commit()
    return db


def test_duplicate_chunks_are_removed_from_all_three_tables(db_path):
    db = add_duplicate_of_chunk_1(db_path)

    assert prepare_database(db) == (0, 1)

    assert db.execute("SELECT COUNT(*) FROM review_tags WHERE chunk = ?", (CHUNKS[0][3],)).fetchone()[0] == 1
    assert sorted(r for (r,) in db.execute("SELECT rowid FROM reviews_vec")) == [1, 2, 3, 4, 5]
    assert sorted(r for (r,) in db.execute("SELECT rowid FROM review_tags")) == [1, 2, 3, 4, 5]
    hits = {r for (r,) in db.execute("SELECT rowid FROM review_text_fts WHERE review_text_fts MATCH 'drone'")}
    assert hits == {1}                                          # the FTS index no longer knows rowid 6
    db.close()


def test_removing_duplicate_chunks_keeps_search_working_and_stops_double_counting(db_path):
    db = add_duplicate_of_chunk_1(db_path)
    before = search.search_albums(db.cursor(), "ambient drone", AMBIENT_QUERY, top_n=3)[0]["relevance"]

    prepare_database(db)
    after = search.search_albums(db.cursor(), "ambient drone", AMBIENT_QUERY, top_n=3)[0]["relevance"]

    assert after < before                                       # chunk 1 was counted twice before
    db.close()


def test_duplicate_chunk_removal_is_idempotent(db_path):
    db = add_duplicate_of_chunk_1(db_path)
    prepare_database(db)
    assert prepare_database(db) == (0, 0)
    db.close()


def test_the_same_text_under_different_reviews_is_not_a_duplicate(db):
    db.executemany("INSERT INTO review_tags VALUES (?, 'identical text', 'tag')", [(1,), (2,)])
    assert prepare_database(db).duplicate_chunks == 0
    assert db.execute("SELECT COUNT(*) FROM review_tags").fetchone()[0] == 2


# --- leaving WAL mode (needed to open a database from a read-only location) ---

def test_use_rollback_journal_leaves_wal_mode(tmp_path):
    from semantic_grooves.db import is_wal
    path = tmp_path / "wal.sqlite"
    db = sqlite3.connect(path)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("CREATE TABLE t (x)")
    db.commit()
    assert is_wal(path)

    assert use_rollback_journal(db) == "delete"
    assert not is_wal(path)
    assert use_rollback_journal(db) == "delete"              # idempotent
    db.close()
    assert not any(p.name.endswith(("-wal", "-shm")) for p in tmp_path.iterdir())
