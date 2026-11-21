from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import sqlite_vec
import os
import re

app = Flask(__name__)
CORS(app)

MODEL_NAME = "BAAI/bge-large-en-v1.5"
DB_PATH = os.environ.get(
    "SG_DB_PATH", os.path.join(os.path.dirname(__file__), "database.sqlite")
)

# Number of candidate chunks fetched from each retriever (vector and lexical).
CANDIDATES = 50
MAX_TOP_N = 100

# BGE retrieval models are trained to embed short queries with this
# instruction in front. Set SG_QUERY_PREFIX="" to disable it.
QUERY_PREFIX = os.environ.get(
    "SG_QUERY_PREFIX", "Represent this sentence for searching relevant passages: "
)

_model = None


def get_model():
    """Load the embedding model on first use (keeps imports and tests cheap)."""
    global _model
    if _model is None:
        import torch
        from sentence_transformers import SentenceTransformer

        device = "cuda" if torch.cuda.is_available() else "cpu"
        _model = SentenceTransformer(MODEL_NAME, device=device)
    return _model


def embed_query(text):
    """Embed a search query (with the BGE retrieval instruction prefix)."""
    return get_model().encode(
        QUERY_PREFIX + text,
        convert_to_numpy=True,
        normalize_embeddings=True
    )


def get_db_connection():
    """Create a new database connection for each request."""
    db = sqlite3.connect(DB_PATH)
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    return db


# Words that carry no mood or style information. Dropping them keeps the
# implicit AND of the lexical query from failing on filler like "the" or "of".
FTS_STOPWORDS = frozenset(
    "a an and are as at be been but by for from had has have i if in into is it "
    "its me my of on or our so than that the their them then these they this "
    "those to was we were what when where which while who will with you your".split()
)


def sanitize_fts_query(query_text):
    """Turn free text into a safe FTS5 MATCH expression.

    Every term is split on non-word characters and double-quoted, so commas,
    colons, quotes, parentheses and FTS5 operators (AND, OR, NOT, NEAR, *, -)
    in user input are inert instead of raising a syntax error. Quoted terms
    are implicitly AND-ed. Returns "" when no usable term remains.
    """
    terms = []
    for term in re.findall(r"\w+", query_text.lower()):
        if len(term) > 1 and term not in FTS_STOPWORDS and term not in terms:
            terms.append(term)
    return ' '.join(f'"{term}"' for term in terms)


def hybrid_search(cursor, query_text, query_vector, top_n=None, k=60, candidates=CANDIDATES):
    """Rank review chunks by combining vector and lexical search with RRF.

    Returns a list of (rowid, rrf_score) sorted best first. A chunk's score is
    the sum of 1 / (k + rank + 1) over the retrievers that returned it, so a
    HIGHER score is a better match. `top_n` truncates the list when given.
    """
    # 1. Vector results (ranked by distance)
    vec_results = cursor.execute("""
        SELECT rowid FROM reviews_vec
        WHERE embedding MATCH ? AND k = ?
        ORDER BY distance
    """, (query_vector.tobytes(), candidates)).fetchall()

    # 2. Lexical results (ranked by BM25)
    fts_results = []
    fts_query = sanitize_fts_query(query_text)
    if fts_query:
        try:
            fts_results = cursor.execute("""
                SELECT rowid FROM review_text_fts
                WHERE review_text_fts MATCH ?
                ORDER BY rank LIMIT ?
            """, (fts_query, candidates)).fetchall()
        except sqlite3.OperationalError as e:
            # Malformed FTS5 query: fall back to vector-only results.
            print(f"FTS5 query error: {e}, query: {fts_query}")

    # 3. Reciprocal Rank Fusion
    scores = {}
    for results in (vec_results, fts_results):
        for rank, (rowid,) in enumerate(results):
            scores[rowid] = scores.get(rowid, 0) + 1.0 / (k + rank + 1)

    # Best score first; rowid breaks ties so the order is deterministic.
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return ranked[:top_n] if top_n is not None else ranked


def search_albums(cursor, query_text, query_vector, top_n=20, k=20):
    """Hybrid search returning at most one result (the best chunk) per album."""
    ranked = hybrid_search(cursor, query_text, query_vector, k=k)
    if not ranked:
        return []

    placeholders = ', '.join(['?'] * len(ranked))
    rows = cursor.execute(f"""
        SELECT rt.rowid, rt.reviewid, rt.tags, r.artist, r.title, r.score, r.url
        FROM review_tags rt
        INNER JOIN reviews r ON rt.reviewid = r.reviewid
        WHERE rt.rowid IN ({placeholders})
    """, [rowid for rowid, _ in ranked]).fetchall()
    details = {row[0]: row[1:] for row in rows}

    results = []
    seen_reviews = set()
    for rowid, rrf_score in ranked:
        if rowid not in details:
            continue  # orphan chunk with no matching review
        reviewid, tags, artist, title, score, url = details[rowid]
        if reviewid in seen_reviews:
            continue  # a better chunk of this album was already returned
        seen_reviews.add(reviewid)
        results.append({
            'reviewid': reviewid,
            'tags': tags,
            'artist': artist,
            'title': title,
            'score': score,
            'url': url,
            'relevance': round(rrf_score, 4),
        })
        if len(results) == top_n:
            break
    return results


def parse_int(data, key, default, minimum, maximum):
    """Read an integer request field, raising ValueError when out of range."""
    value = data.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"'{key}' must be an integer between {minimum} and {maximum}")
    return value


@app.route('/api/search', methods=['POST'])
def search():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'error': 'A JSON object body is required'}), 400

    query_text = data.get('query', '')
    if not isinstance(query_text, str) or not query_text.strip():
        return jsonify({'error': 'Query is required'}), 400

    try:
        top_n = parse_int(data, 'top_n', 20, 1, MAX_TOP_N)
        k = parse_int(data, 'k', 20, 1, 1000)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    try:
        query_embedded = embed_query(query_text)

        db = get_db_connection()
        try:
            results = search_albums(db.cursor(), query_text, query_embedded, top_n=top_n, k=k)
        finally:
            db.close()
        return jsonify({'results': results})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    app.run(debug=True, port=5000)
