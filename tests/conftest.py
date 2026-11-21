"""Shared fixtures: a tiny hand-built database and a stub embedding model.

Vectors are 4-dimensional (vec0 accepts any dimension) so the tests need
neither the 1.2 GB production database nor the BGE model.
"""
import sqlite3

import numpy as np
import pytest
import sqlite_vec

from semantic_grooves import embedding

DIM = 4


def vec(*values):
    """Unit-length float32 vector."""
    v = np.array(values, dtype=np.float32)
    return v / np.linalg.norm(v)


# (rowid, reviewid, tags, chunk, vector)
CHUNKS = [
    (1, 1, "ambient, drone", "slow ambient drone with warm synth pads", vec(1, 0, 0, 0)),
    (2, 1, "ambient, piano", "ambient textures and quiet piano", vec(0.9, 0.1, 0, 0)),
    (3, 2, "punk, guitar", "aggressive punk guitar riffs", vec(0, 1, 0, 0)),
    (4, 3, "jazz, saxophone", "ambient jazz saxophone", vec(0.3, 0, 1, 0)),
    # Chunk whose review is missing from `reviews`: must never surface.
    (5, 99, "orphan", "chunk whose review row is missing", vec(0.95, 0.05, 0, 0)),
]

REVIEWS = [
    (1, "album one", "alpha", "http://example.com/1", 8.1),
    (2, "album two", "beta", "http://example.com/2", 6.5),
    (3, "album three", "gamma", "http://example.com/3", 7.4),
]

# Query vector that is closest to the "ambient" chunks above.
AMBIENT_QUERY = vec(1, 0, 0, 0)


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "fixture.sqlite"
    db = sqlite3.connect(path)
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    db.execute("""CREATE TABLE reviews (
        reviewid INTEGER, title TEXT, artist TEXT, url TEXT, score REAL)""")
    db.execute("""CREATE TABLE review_tags (
        reviewid INTEGER REFERENCES reviews(reviewid), chunk NVARCHAR, tags NVARCHAR)""")
    db.execute(f"CREATE VIRTUAL TABLE reviews_vec USING vec0(embedding float[{DIM}])")
    db.execute("""CREATE VIRTUAL TABLE review_text_fts USING fts5(
        tags, chunk, content='review_tags', content_rowid='rowid')""")

    db.executemany("INSERT INTO reviews VALUES (?, ?, ?, ?, ?)", REVIEWS)
    for rowid, reviewid, tags, chunk, vector in CHUNKS:
        db.execute("INSERT INTO review_tags(rowid, reviewid, chunk, tags) VALUES (?, ?, ?, ?)",
                   (rowid, reviewid, chunk, tags))
        db.execute("INSERT INTO reviews_vec(rowid, embedding) VALUES (?, ?)",
                   (rowid, vector.tobytes()))
    db.execute("INSERT INTO review_text_fts(rowid, tags, chunk) "
               "SELECT rowid, tags, chunk FROM review_tags")
    db.commit()
    db.close()
    return str(path)


@pytest.fixture
def cursor(db_path):
    db = sqlite3.connect(db_path)
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    yield db.cursor()
    db.close()


class StubModel:
    """Stands in for SentenceTransformer: every query embeds to AMBIENT_QUERY."""

    def encode(self, text, **kwargs):
        return AMBIENT_QUERY


@pytest.fixture
def client(db_path, monkeypatch):
    from semantic_grooves import api

    monkeypatch.setenv("SG_DB_PATH", db_path)
    monkeypatch.setattr(embedding, "get_model", lambda: StubModel())
    api.app.config["TESTING"] = True
    return api.app.test_client()


# ---- build-pipeline fixtures -------------------------------------------------

# reviewid -> review text. Chunked at 400/50 these give 3 + 1 + 1 chunks:
# review 1 is long, review 2 is short, review 3 ends in a tail under 100 chars.
SOURCE_CONTENT = {
    1: ("slow ambient drone. " * 45)[:900],
    2: "short and sweet punk blast",
    3: ("quiet piano and sax. " * 20)[:420],
}


@pytest.fixture
def source_db_path(tmp_path):
    """A database as downloaded from Kaggle: reviews + content, nothing built yet."""
    path = tmp_path / "source.sqlite"
    db = sqlite3.connect(path)
    db.execute("""CREATE TABLE reviews (
        reviewid INTEGER, title TEXT, artist TEXT, url TEXT, score REAL)""")
    db.execute("CREATE TABLE content (reviewid INTEGER, content TEXT)")
    db.executemany("INSERT INTO reviews VALUES (?, ?, ?, ?, ?)", REVIEWS)
    db.executemany("INSERT INTO content VALUES (?, ?)", SOURCE_CONTENT.items())
    db.commit()
    db.close()
    return str(path)


@pytest.fixture
def tagged_db_path(tmp_path):
    """A database after `build-tags`: reviews + review_tags, no indexes yet."""
    path = tmp_path / "tagged.sqlite"
    db = sqlite3.connect(path)
    db.execute("""CREATE TABLE reviews (
        reviewid INTEGER, title TEXT, artist TEXT, url TEXT, score REAL)""")
    db.execute("""CREATE TABLE review_tags (
        reviewid INTEGER REFERENCES reviews(reviewid), chunk NVARCHAR, tags NVARCHAR)""")
    db.executemany("INSERT INTO reviews VALUES (?, ?, ?, ?, ?)", REVIEWS)
    for rowid, reviewid, tags, chunk, _ in CHUNKS:
        db.execute("INSERT INTO review_tags(rowid, reviewid, chunk, tags) VALUES (?, ?, ?, ?)",
                   (rowid, reviewid, chunk, tags))
    db.commit()
    db.close()
    return str(path)


class StubOllama:
    """Stands in for ollama.AsyncClient: every chunk is tagged 'calm, piano'."""

    def __init__(self, fail_on=()):
        self.prompts = []
        self.fail_on = fail_on

    async def generate(self, model, prompt, options):
        self.prompts.append(prompt)
        if any(text in prompt for text in self.fail_on):
            raise RuntimeError("model unavailable")
        return {"response": "  calm, piano  "}


class StubEmbedder:
    """Stands in for SentenceTransformer: deterministic 4-d vectors from the text."""

    def __init__(self):
        self.calls = []

    def get_sentence_embedding_dimension(self):
        return DIM

    def encode(self, texts, **kwargs):
        import zlib
        self.calls.append(list(texts))
        rows = []
        for text in texts:
            h = zlib.crc32(text.encode())
            rows.append(vec(1 + h % 7, 1 + (h >> 3) % 7, 1 + (h >> 6) % 7, 1 + (h >> 9) % 7))
        return np.array(rows, dtype=np.float32)
