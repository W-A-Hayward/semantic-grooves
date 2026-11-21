"""Step 2: embed tagged chunks and build the vector and full-text indexes.

Reads `review_tags` and writes `reviews_vec` (sqlite-vec) and `review_text_fts`
(FTS5). Incremental: only chunks that have no vector yet are embedded, so an
interrupted run resumes where it stopped. Use rebuild=True to start from scratch.
"""
from .. import embedding

BATCH_SIZE = 128   # sentences per model call (tune to GPU memory)
COMMIT_EVERY = 4096  # chunks embedded between commits


def document_text(tags, chunk):
    """The text that is embedded for a chunk: its mood tags, then the review text."""
    return f"Tags: {tags or ''}\nReview: {chunk}"


def _table_exists(db, name):
    return db.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (name,)).fetchone() is not None


def _rebuild_fts(db):
    db.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS review_text_fts USING fts5(
            tags, chunk, content='review_tags', content_rowid='rowid'
        )
    """)
    db.execute("INSERT INTO review_text_fts(review_text_fts) VALUES ('rebuild')")
    db.commit()


def build_index(db, model=None, batch_size=BATCH_SIZE, rebuild=False, progress=print):
    """Embed chunks that have no vector yet and refresh the FTS index.

    Returns the number of chunks newly embedded.
    """
    model = model or embedding.get_model()
    if rebuild:
        db.execute("DROP TABLE IF EXISTS reviews_vec")
        db.execute("DROP TABLE IF EXISTS review_text_fts")
        db.commit()

    dim = model.get_sentence_embedding_dimension()
    db.execute(f"CREATE VIRTUAL TABLE IF NOT EXISTS reviews_vec USING vec0(embedding float[{dim}])")

    done = {rowid for (rowid,) in db.execute("SELECT rowid FROM reviews_vec")}
    pending = [row for row in db.execute("SELECT rowid, tags, chunk FROM review_tags ORDER BY rowid")
               if row[0] not in done]

    if pending:
        progress(f"Embedding {len(pending)} chunks...")
    for start in range(0, len(pending), COMMIT_EVERY):
        part = pending[start:start + COMMIT_EVERY]
        vectors = model.encode(
            [document_text(tags, chunk) for _, tags, chunk in part],
            batch_size=batch_size,
            convert_to_numpy=True,
            show_progress_bar=True,
            normalize_embeddings=True,
        )
        db.executemany(
            "INSERT INTO reviews_vec(rowid, embedding) VALUES (?, ?)",
            [(rowid, vector.tobytes()) for (rowid, _, _), vector in zip(part, vectors)],
        )
        db.commit()

    if pending or rebuild or not _table_exists(db, "review_text_fts"):
        _rebuild_fts(db)
    if not pending:
        progress("Everything is up to date. No new embeddings needed.")
    return len(pending)
