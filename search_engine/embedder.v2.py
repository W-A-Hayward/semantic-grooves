import sqlite3
import sqlite_vec
import torch
import numpy as np
from sentence_transformers import SentenceTransformer

# --- Configuration ---
DB_PATH = "../database.sqlite"
MODEL_NAME = "BAAI/bge-large-en-v1.5"
BATCH_SIZE = 128  # Optimized for 6800 XT VRAM
CHUNK_LIMIT = 1200

# --- Database & Extension Setup ---
db = sqlite3.connect(DB_PATH)
db.enable_load_extension(True)
sqlite_vec.load(db)
cursor = db.cursor()

# --- Hardware Check ---
print(f"ROCm/CUDA Available: {torch.cuda.is_available()}")
device = "cuda" if torch.cuda.is_available() else "cpu"
model = SentenceTransformer(MODEL_NAME, device=device)

# --- Table Initialization ---
cursor.execute("""DROP TABLE IF EXISTS reviews_vec""")
cursor.execute("""DROP TABLE IF EXISTS review_text_fts""")
db.commit()
cursor.execute("""
    CREATE VIRTUAL TABLE reviews_vec USING vec0(
        embedding float[1024]
    )
""")

# --- Fetch Unprocessed Chunks ---
cursor.execute("""
    SELECT rowid, tags, chunk 
    FROM review_tags 
    WHERE rowid NOT IN (SELECT rowid FROM reviews_vec)
""")
rows = cursor.fetchall()

if not rows:
    print("Everything is up to date. No new embeddings needed.")
    db.close()
    exit()

print(f"Processing {len(rows)} new chunks...")

# --- Embedding Generation ---
# Note: For BGE, we use a specific instruction for 'search documents'
# although BGE often works fine with raw text for the index side.
texts_to_embed = [
    f"Tags: {r[1]}\nReview: {r[2]}" for r in rows
]

vectors = model.encode(
    texts_to_embed,
    batch_size=BATCH_SIZE,
    convert_to_numpy=True,
    show_progress_bar=True,
    normalize_embeddings=True
)

# --- Batch Insertion ---
# We use the rowid from review_tags as the rowid for reviews_vec
data_to_insert = [
    (rows[i][0], vectors[i].tobytes()) 
    for i in range(len(rows))
]

try:
    cursor.executemany(
        "INSERT INTO reviews_vec(rowid, embedding) VALUES (?, ?)", 
        data_to_insert
    )
    db.commit()
    print(f"Successfully indexed {len(data_to_insert)} vectors.")
except Exception as e:
    print(f"Error during insertion: {e}")
    db.rollback()
finally:
# Clear existing table 
    cursor.execute("""
                   CREATE VIRTUAL TABLE IF NOT EXISTS review_text_fts USING fts5(
                        tags, 
                        chunk, 
                        content='review_tags', 
                        content_rowid='rowid'
                    );
                   """)
    cursor.execute("""
                    INSERT INTO review_text_fts(rowid, tags, chunk) 
                    SELECT rowid, tags, chunk FROM review_tags;
                   """)

    db.commit()
    db.close()
