"""Flask API: POST /api/search and GET /api/health, optionally serving the built frontend."""
from pathlib import Path

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from .config import db_path, static_dir
from .db import connect, is_wal
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
        error = str(e)
        if is_wal(db_path()):
            error += (" (the database is in WAL mode, which cannot be opened from a read-only "
                      "location: run `sg prepare-db` on it, or mount its folder read-write)")
        return jsonify({'status': 'unavailable', 'error': error}), 503
    return jsonify({'status': 'ok'})


def register_frontend(flask_app, directory):
    """Serve a built single-page frontend (e.g. frontend/dist) from `flask_app`.

    Real files are served as they are (hashed files under assets/ with a long
    cache lifetime); any other path returns index.html so client-side routes
    work. Unknown /api/ paths stay a JSON 404 instead of falling back to the page.
    """
    root = Path(directory).resolve()
    if not (root / "index.html").is_file():
        raise FileNotFoundError(f"no index.html in {root} (run `npm run build` in frontend/)")

    @flask_app.get("/", defaults={"path": ""})
    @flask_app.get("/<path:path>")
    def frontend(path):
        if path == "api" or path.startswith("api/"):
            return jsonify({'error': 'Not found'}), 404
        if path and (root / path).is_file():
            return send_from_directory(root, path, max_age=31536000 if path.startswith("assets/") else 0)
        return send_from_directory(root, "index.html", max_age=0)


if static_dir():
    register_frontend(app, static_dir())
