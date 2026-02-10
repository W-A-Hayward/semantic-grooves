from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import sqlite_vec
import numpy as np
import torch
from sentence_transformers import SentenceTransformer
import os
import re

app = Flask(__name__)
CORS(app)

# Initialize model and database connection
device = "cuda" if torch.cuda.is_available() else "cpu"
model = SentenceTransformer("BAAI/bge-large-en-v1.5", device=device)
DB_PATH = os.path.join(os.path.dirname(__file__), "database.sqlite")

def get_db_connection():
    """Create a new database connection for each request."""
    db = sqlite3.connect(DB_PATH)
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    return db

def hybrid_search(cursor, query_text, query_vector, top_n=10, k=60):
    """Perform hybrid search combining vector and lexical search."""
    # 1. Get Vector Results (Ranked by distance)
    vec_results = cursor.execute("""
        SELECT rowid FROM reviews_vec 
        WHERE embedding MATCH ? AND k = 50 
        ORDER BY distance
    """, (query_vector.tobytes(),)).fetchall()
    
    # 2. Get Lexical Results (Ranked by BM25 score)
    # Sanitize FTS5 query to prevent syntax errors
    # FTS5 interprets "column:value" as column filters, so we need to escape colons
    # Also escape other FTS5 special characters
    fts_query = query_text.strip()
    if not fts_query:
        fts_results = []
    else:
        # Replace colons and other special FTS5 operators that might cause issues
        # Replace "word:word" patterns (which FTS5 interprets as column:value)
        fts_query = re.sub(r'(\w+):(\w+)', r'\1 \2', fts_query)
        # Escape remaining special FTS5 characters
        fts_query = fts_query.replace('"', ' ').replace("'", ' ')
        # Clean up multiple spaces
        fts_query = ' '.join(fts_query.split())
        
        try:
            fts_results = cursor.execute("""
                SELECT rowid FROM review_text_fts 
                WHERE review_text_fts MATCH ? 
                ORDER BY rank LIMIT 50
            """, (fts_query,)).fetchall()
        except sqlite3.OperationalError as e:
            # If FTS5 query fails, skip FTS search and log the error
            print(f"FTS5 query error: {e}, query: {fts_query}")
            fts_results = []
    
    # 3. Combine using RRF
    scores = {}
    
    for rank, (rowid,) in enumerate(vec_results):
        scores[rowid] = scores.get(rowid, 0) + 1.0 / (k + rank + 1)
        
    for rank, (rowid,) in enumerate(fts_results):
        scores[rowid] = scores.get(rowid, 0) + 1.0 / (k + rank + 1)
    
    # Sort by the new combined RRF score (ascending - lower is better)
    sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=False)[:top_n]
    return sorted_ids

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
        query_embedded = model.encode(
            query_text, 
            convert_to_numpy=True, 
            normalize_embeddings=True
        )
        
        # Perform search
        db = get_db_connection()
        cursor = db.cursor()
        
        sorted_ids = hybrid_search(cursor, query_text, query_embedded, top_n=top_n, k=k)
        
        if not sorted_ids:
            db.close()
            return jsonify({'results': []})
        
        # Fetch review details
        placeholders = ', '.join(['?'] * len(sorted_ids))
        rowids = [r[0] for r in sorted_ids]
        
        query = f"""
            SELECT 
                rt.tags,
                r.artist,
                r.title,
                r.score,
                r.url
            FROM review_tags rt
            INNER JOIN reviews r ON rt.reviewid = r.reviewid
            WHERE rt.rowid IN ({placeholders})
            ORDER BY CASE rt.rowid 
                { ' '.join([f"WHEN ? THEN {i}" for i in range(len(rowids))]) } 
            END
        """
        
        cursor.execute(query, rowids + rowids)
        rows = cursor.fetchall()
        
        # Format results
        results = []
        for i, row in enumerate(rows):
            tags, artist, title, score, url = row
            accuracy = sorted_ids[i][1] if i < len(sorted_ids) else 0
            
            results.append({
                'tags': tags,
                'artist': artist,
                'title': title,
                'score': score,
                'url': url,
                'relevance': round(accuracy, 4)
            })
        
        db.close()
        return jsonify({'results': results})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)

