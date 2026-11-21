"""Hybrid search: vector + lexical retrieval fused with RRF, scored per album."""
import re
import sqlite3

# Number of candidate chunks fetched from each retriever (vector and lexical).
# A larger pool lets several chunks of the same album show up, which is what
# album-level scoring needs.
CANDIDATES = 200

# An album's score is the sum of its best ALBUM_CHUNKS chunk scores.
ALBUM_CHUNKS = 3


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


def max_relevance(k):
    """Upper bound of an album score: its best ALBUM_CHUNKS chunks ranked 1st,
    2nd, ... in both retrievers. Use it to scale `relevance` to 0-1."""
    return 2 * sum(1.0 / (k + i) for i in range(1, ALBUM_CHUNKS + 1))


def rank_albums(ranked, details, top_n):
    """Group ranked chunks into albums and return the top_n albums.

    `ranked` is [(rowid, rrf_score)] best first; `details` maps a chunk rowid to
    (reviewid, tags, artist, title, score, url). An album's relevance is the sum
    of its best ALBUM_CHUNKS chunk scores, so an album described consistently
    across several passages beats one that matched a single passage. Its tags
    come from its best chunk. Chunks without a review row are skipped.
    """
    albums = {}  # reviewid -> {'chunks': [(score, rowid)], ...}
    for rowid, rrf_score in ranked:
        if rowid not in details:
            continue  # orphan chunk with no matching review
        reviewid = details[rowid][0]
        albums.setdefault(reviewid, []).append((rrf_score, rowid))

    scored = []
    for reviewid, chunks in albums.items():
        chunks.sort(key=lambda c: (-c[0], c[1]))  # best chunk first (ranked order already)
        relevance = sum(score for score, _ in chunks[:ALBUM_CHUNKS])
        scored.append((relevance, chunks[0][1], reviewid))
    # Best album first; the best chunk's rowid breaks ties deterministically.
    scored.sort(key=lambda item: (-item[0], item[1]))

    results = []
    for relevance, best_rowid, reviewid in scored[:top_n]:
        _, tags, artist, title, score, url = details[best_rowid]
        results.append({
            'reviewid': reviewid,
            'tags': tags,
            'artist': artist,
            'title': title,
            'score': score,
            'url': url,
            'relevance': round(relevance, 4),
        })
    return results


def search_albums(cursor, query_text, query_vector, top_n=20, k=20):
    """Hybrid search returning one result per album, scored over its chunks."""
    # Rank every candidate chunk first; top_n counts albums, not chunks.
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
    return rank_albums(ranked, details, top_n)
