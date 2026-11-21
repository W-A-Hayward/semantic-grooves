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


def get_db_connection():
    """Create a new database connection for each request."""
    db = sqlite3.connect(DB_PATH)
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    return db


def sanitize_fts_query(query_text):
    """Make free text safe for FTS5 MATCH (colons would be read as column filters)."""
    fts_query = re.sub(r'(\w+):(\w+)', r'\1 \2', query_text.strip())
    fts_query = fts_query.replace('"', ' ').replace("'", ' ')
    return ' '.join(fts_query.split())


def hybrid_search(cursor, query_text, query_vector, top_n=None, k=60):
    """Perform hybrid search combining vector and lexical search."""
    # 1. Get Vector Results (Ranked by distance)
    vec_results = cursor.execute("""
        SELECT rowid FROM reviews_vec 
        WHERE embedding MATCH ? AND k = 50 
        ORDER BY distance
    """, (query_vector.tobytes(),)).fetchall()
    
    # 2. Get Lexical Results (Ranked by BM25 score)
    fts_results = []
    fts_query = sanitize_fts_query(query_text)
    if fts_query:
        try:
            fts_results = cursor.execute("""
                SELECT rowid FROM review_text_fts 
                WHERE review_text_fts MATCH ? 
                ORDER BY rank LIMIT 50
            """, (fts_query,)).fetchall()
        except sqlite3.OperationalError as e:
            # If FTS5 query fails, skip FTS search and log the error
            print(f"FTS5 query error: {e}, query: {fts_query}")
    
    # 3. Combine using RRF
    scores = {}
    
    for rank, (rowid,) in enumerate(vec_results):
        scores[rowid] = scores.get(rowid, 0) + 1.0 / (k + rank + 1)
        
    for rank, (rowid,) in enumerate(fts_results):
        scores[rowid] = scores.get(rowid, 0) + 1.0 / (k + rank + 1)
    
    # Best score first (RRF: a higher score is a better match); rowid breaks
    # ties so the order is deterministic.
    sorted_ids = sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:top_n]
    return sorted_ids


def search_albums(cursor, query_text, query_vector, top_n=20, k=20):
    """Hybrid search returning at most one result (the best chunk) per album."""
    # Rank every candidate chunk first; top_n counts albums, not chunks.
    ranked = hybrid_search(cursor, query_text, query_vector, k=k)
    if not ranked:
        return []

    # Fetch review details, keyed by chunk rowid so each result keeps the RRF
    # score of its own chunk (a chunk without a matching review is skipped).
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
            'relevance': round(rrf_score, 4)
        })
        if len(results) == top_n:
            break
    return results


@app.route('/api/search', methods=['POST'])
def search():
    try:
        data = request.json
        query_text = data.get('query', '')
        top_n = data.get('top_n', 20)
        k = data.get('k', 20)
        
        if not query_text:
            return jsonify({'error': 'Query is required'}), 400
        
        # Encode query
        query_embedded = get_model().encode(
            query_text, 
            convert_to_numpy=True, 
            normalize_embeddings=True
        )
        
        # Perform search
        db = get_db_connection()
        cursor = db.cursor()

        results = search_albums(cursor, query_text, query_embedded, top_n=top_n, k=k)

        db.close()
        return jsonify({'results': results})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
