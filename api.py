from flask import Flask, request, jsonify
from flask_cors import CORS
from sqlite_vec import serialize_float32
import numpy as np
import torch
from sentence_transformers import SentenceTransformer
import os
from dotenv import load_dotenv
import re
from libsql_client import create_client_sync

app = Flask(__name__)
CORS(app)
load_dotenv()

# Initialize model and database connection
device = "cuda" if torch.cuda.is_available() else "cpu"
model = SentenceTransformer("BAAI/bge-large-en-v1.5", device=device)
url = os.getenv("TURSO_DATABASE_URL")
auth_token = os.getenv("TURSO_AUTH_TOKEN")
huggingface_token = os.getenv("HUGGINGFACE_TOKEN")
if not url or not auth_token:
    print(url, "\n", auth_token)
    exit(1)
client = create_client_sync(url, auth_token=auth_token)

import requests

def get_embedding(text):
    api_url = "https://api-inference.huggingface.co/models/mixedbread-ai/mxbai-embed-large-v1"
    headers = {"Authorization": f"Bearer {huggingface_token}"}
    payload = {
        "inputs": text,
        "parameters": {
            "normalize": True
        }
    }
    response = requests.post(api_url, headers=headers, json=payload)
    return response.json() 

def hybrid_search(client, query_text, query_vector, top_n=10, k=60):
    # 1. Vector Search using Turso Native Index
    # Note: Turso returns 'id' and 'distance'
    vec_query = """
        SELECT id, distance 
        FROM vector_top_k('movies_idx', ?, 50)
    """
    # Serialize the numpy array to the float32 blob format Turso expects
    vec_results = client.execute(vec_query, [serialize_float32(query_vector)]).rows
    
    # 2. Lexical Search (FTS5 is supported in Turso)
    fts_results = []
    if query_text.strip():
        # Sanitize query (keep your existing regex/logic)
        fts_query = re.sub(r'(\w+):(\w+)', r'\1 \2', query_text).replace('"', ' ')
        try:
            fts_res = client.execute("""
                SELECT rowid FROM review_text_fts 
                WHERE review_text_fts MATCH ? 
                LIMIT 50
            """, [fts_query])
            fts_results = fts_res.rows
        except Exception as e:
            print(f"FTS error: {e}")

    # 3. RRF Combination
    scores = {}
    for rank, row in enumerate(vec_results):
        rowid = row[0]
        scores[rowid] = scores.get(rowid, 0) + 1.0 / (k + rank + 1)
        
    for rank, row in enumerate(fts_results):
        rowid = row[0]
        scores[rowid] = scores.get(rowid, 0) + 1.0 / (k + rank + 1)
    
    # Sort by RRF score descending (higher is more relevant)
    sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_n]
    return sorted_ids

@app.route('/api/search', methods=['POST'])
def search():
    try:
        data = request.json
        query_text = data.get('query', '')
        top_n = data.get('top_n', 20)
        k_rrf = data.get('k', 60) # Renamed to avoid confusion with top_k
        
        if not query_text:
            return jsonify({'error': 'Query is required'}), 400
        
        # 1. Encode query (BGE Large outputs 1024 dims)
        query_embedded = get_embedding(query_text)
        
        # 2. Hybrid Search - Pass the global 'client' (renamed from cursor)
        sorted_ids = hybrid_search(client, query_text, query_embedded, top_n=top_n, k=k_rrf)
        
        if not sorted_ids:
            return jsonify({'results': []})
        
        # 3. Fetch details
        rowids = [r[0] for r in sorted_ids]
        placeholders = ', '.join(['?'] * len(rowids))
        
        # We use a JOIN to get details based on the rowids from our RRF
        # Turso doesn't need a manually closed connection per request
        res = client.execute(f"""
            SELECT rt.rowid, rt.tags, r.artist, r.title, r.score, r.url
            FROM review_tags rt
            INNER JOIN reviews r ON rt.reviewid = r.reviewid
            WHERE rt.rowid IN ({placeholders})
        """, rowids)
        
        # 4. Map results back to sorted order
        row_map = {row[0]: row[1:] for row in res.rows}
        results = []
        for rid, score in sorted_ids:
            if rid in row_map:
                tags, artist, title, val_score, url = row_map[rid]
                results.append({
                    'tags': tags,
                    'artist': artist,
                    'title': title,
                    'score': val_score,
                    'url': url,
                    'relevance': round(score, 4)
                })
        
        return jsonify({'results': results})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)

