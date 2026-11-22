"""Flask API: POST /api/search and GET /api/health."""
from flask import Flask, request, jsonify
from flask_cors import CORS

from .db import connect
from .embedding import embed_query
from .search import max_relevance, search_albums

app = Flask(__name__)
CORS(app)

MAX_TOP_N = 100


def get_db_connection():
    """Create a new read-only database connection for each request."""
    return connect(read_only=True)


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
        return jsonify({'results': results, 'max_relevance': round(max_relevance(k), 4)})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health():
    """200 when the database can be opened and read, 503 otherwise."""
    try:
        db = get_db_connection()
        try:
            db.execute("SELECT 1 FROM review_tags LIMIT 1").fetchone()
        finally:
            db.close()
    except Exception as e:
        return jsonify({'status': 'unavailable', 'error': str(e)}), 503
    return jsonify({'status': 'ok'})
