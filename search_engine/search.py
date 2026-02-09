import sqlite3
import sqlite_vec
import numpy as np
import torch
from sentence_transformers import SentenceTransformer

db = sqlite3.connect("../db/database.sqlite")
db.enable_load_extension(True)
sqlite_vec.load(db)
cursor = db.cursor()

device = "cuda" if torch.cuda.is_available() else "cpu"
model = SentenceTransformer("BAAI/bge-large-en-v1.5", device=device)
usr_query = input("Enter a query for an album you'd like, focus on the emotions : \n")
while True:
    try:
        usr_query = str(usr_query)
        break
    except:
        print("Please enter a string")

query_embedded = model.encode(usr_query, convert_to_numpy=True, normalize_embeddings=True)

def hybrid_search(query_text, query_vector, top_n=10, k=60):
    # 1. Get Vector Results (Ranked by distance)
    vec_results = cursor.execute("""
        SELECT rowid FROM reviews_vec 
        WHERE embedding MATCH ? AND k = 50 
        ORDER BY distance
    """, (query_vector.tobytes(),)).fetchall()
    
    # 2. Get Lexical Results (Ranked by BM25 score)
    fts_results = cursor.execute("""
        SELECT rowid FROM review_text_fts 
        WHERE review_text_fts MATCH ? 
        ORDER BY rank LIMIT 50
    """, (query_text,)).fetchall()
    
    # 3. Combine using RRF
    scores = {}
    
    for rank, (rowid,) in enumerate(vec_results):
        scores[rowid] = scores.get(rowid, 0) + 1.0 / (k + rank + 1)
        
    for rank, (rowid,) in enumerate(fts_results):
        scores[rowid] = scores.get(rowid, 0) + 1.0 / (k + rank + 1)
    
    # Sort by the new combined RRF score
    sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_n]
    return sorted_ids

sorted_ids = hybrid_search(usr_query, query_embedded, top_n=20, k=20)
print(sorted_ids)

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

# We repeat rowids twice: once for the IN clause, once for the CASE sorting
cursor.execute(query, rowids + rowids)

rows = cursor.fetchall()
for i in range(len(rows)):
    row = rows[i]
    accuracy = sorted_ids[i][1]
    print(accuracy, row)

db.close()  # Added: close the connection
