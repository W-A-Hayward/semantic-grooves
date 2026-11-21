import sqlite3

import pytest

from conftest import AMBIENT_QUERY, CHUNKS, StubEmbedder
from semantic_grooves import search
from semantic_grooves.db import connect
from semantic_grooves.pipeline import indexing


@pytest.fixture
def db(tagged_db_path):
    db = connect(tagged_db_path)
    yield db
    db.close()


def quiet(message):
    pass


def vector_rowids(db):
    return sorted(r for (r,) in db.execute("SELECT rowid FROM reviews_vec"))


def test_document_text_puts_tags_before_the_review():
    assert indexing.document_text("calm, piano", "some text") == "Tags: calm, piano\nReview: some text"
    assert indexing.document_text(None, "x") == "Tags: \nReview: x"


def test_build_index_embeds_every_chunk(db):
    model = StubEmbedder()
    added = indexing.build_index(db, model=model, progress=quiet)

    assert added == len(CHUNKS)
    assert vector_rowids(db) == [rowid for rowid, *_ in CHUNKS]
    texts = model.calls[0]
    assert texts[0] == indexing.document_text(CHUNKS[0][2], CHUNKS[0][3])


def test_build_index_creates_a_working_full_text_index(db):
    indexing.build_index(db, model=StubEmbedder(), progress=quiet)
    hits = {r for (r,) in db.execute(
        "SELECT rowid FROM review_text_fts WHERE review_text_fts MATCH 'saxophone'")}
    assert hits == {4}


def test_the_built_index_is_searchable(db):
    indexing.build_index(db, model=StubEmbedder(), progress=quiet)
    results = search.search_albums(db.cursor(), "ambient", AMBIENT_QUERY, top_n=5)
    assert results and results[0]["artist"] in {"alpha", "beta", "gamma"}


def test_second_run_is_a_no_op(db):
    indexing.build_index(db, model=StubEmbedder(), progress=quiet)
    model = StubEmbedder()
    messages = []
    assert indexing.build_index(db, model=model, progress=messages.append) == 0
    assert model.calls == []
    assert any("up to date" in m for m in messages)


def test_only_new_chunks_are_embedded_and_reach_the_full_text_index(db):
    indexing.build_index(db, model=StubEmbedder(), progress=quiet)
    db.execute("INSERT INTO review_tags(reviewid, chunk, tags) VALUES (1, 'a brand new trombone solo', 'brass')")
    db.commit()

    model = StubEmbedder()
    assert indexing.build_index(db, model=model, progress=quiet) == 1
    assert len(model.calls) == 1 and len(model.calls[0]) == 1
    assert "trombone" in model.calls[0][0]
    assert len(vector_rowids(db)) == len(CHUNKS) + 1
    assert db.execute(
        "SELECT COUNT(*) FROM review_text_fts WHERE review_text_fts MATCH 'trombone'").fetchone()[0] == 1


def test_an_interrupted_run_resumes(db):
    class Interrupted(StubEmbedder):
        def encode(self, texts, **kwargs):
            if self.calls:
                raise KeyboardInterrupt
            return super().encode(texts, **kwargs)

    original = indexing.COMMIT_EVERY
    indexing.COMMIT_EVERY = 2
    try:
        with pytest.raises(KeyboardInterrupt):
            indexing.build_index(db, model=Interrupted(), progress=quiet)
        assert len(vector_rowids(db)) == 2                    # the first commit survived

        assert indexing.build_index(db, model=StubEmbedder(), progress=quiet) == len(CHUNKS) - 2
    finally:
        indexing.COMMIT_EVERY = original
    assert len(vector_rowids(db)) == len(CHUNKS)


def test_rebuild_embeds_everything_again(db):
    indexing.build_index(db, model=StubEmbedder(), progress=quiet)
    model = StubEmbedder()
    assert indexing.build_index(db, model=model, rebuild=True, progress=quiet) == len(CHUNKS)
    assert vector_rowids(db) == [rowid for rowid, *_ in CHUNKS]


def test_vector_dimension_follows_the_model(db):
    indexing.build_index(db, model=StubEmbedder(), progress=quiet)
    blob = db.execute("SELECT embedding FROM reviews_vec LIMIT 1").fetchone()[0]
    assert len(blob) == 4 * 4                                 # 4 float32 values
