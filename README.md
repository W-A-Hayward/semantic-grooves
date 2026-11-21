# Semantic Grooves

**Discover music by how it feels, not by what it's called.** A search engine over 18,389 Pitchfork album reviews: type a mood in plain language, get the records critics described that way, whatever their genre.

## The idea

Music discovery runs on genre labels and "fans also like", which only work if you already know what to ask for. People think in feelings: *"something warm and unhurried"*, *"music for a long drive after a breakup"*. Critics already write about records in exactly those terms, so we search the writing instead of the labels.

*"the feeling of a quiet Sunday morning, warm and unhurried"* (real output, first run):

| # | Album | Tags the LLM extracted (abbreviated) |
|---|---|---|
| 1 | Wilco &ndash; *The Whole Love* | nostalgia, longing, tranquility, piano, indie folk |
| 2 | Blue Daisy &ndash; *The Sunday Gift* | relaxing, wistful, cinematic, house |
| 3 | Sachiko M, Otomo Yoshihide, Toshimaru Nakamura &ndash; *Good Morning Good Night* | peacefulness, tranquility, ambient, experimental |
| 4 | The Innocence Mission &ndash; *Befriended* | bucolic, wistfulness, acoustic guitars, folk |

Indie folk, house, ambient and experimental sit in one list because they share a feeling. A genre filter cannot produce that.

**Status: proof of concept.** One publication (1999&ndash;2017) and no human-judged quality evaluation yet. See [What is and isn't proven](#what-is-and-isnt-proven).

## How it works

```
BUILD (once, ~20 h)   review → 400-char chunks → LLM mood tags → BGE-large embedding → SQLite file
QUERY (≈0.5 s)        text → embed ─→ vector top 200 ─┐
                           └────────→ BM25 top 200  ──┴→ RRF → group by album → top N
```

**Chunk and tag.** A review's mood shifts, so each review is cut into 400-character chunks (50 overlap): 217,152 chunks, about 12 per review. A local LLM (`qwen2.5:7b`) tags each chunk with emotions, instruments, genres and effects. The embedded text is `"Tags: …\nReview: …"`, so the vector leans toward feeling.

**Retrieve two ways.** *Vector:* an exact cosine scan (dot product on L2-normalised 1024-d vectors, `BAAI/bge-large-en-v1.5`, via `sqlite-vec`). Queries carry BGE's recommended retrieval instruction prefix. *Lexical:* SQLite FTS5 with BM25. Query terms are tokenised, stopword-filtered, quoted (so punctuation can't break it) and AND-ed.

**Fuse ranks, not scores.** Vector distances and BM25 scores are on different scales, so Reciprocal Rank Fusion combines positions:

```
chunk score   s(c) = Σ over retrievers  1 / (k + rank + 1)             k = 20, rank counted from 0
album score   S(a) = sum of the best 3 chunk scores of album a
upper bound         2 · (1/(k+1) + 1/(k+2) + 1/(k+3)) = 0.2731          (used to scale the UI score)
```

An album matched by several passages outranks one matched by a single passage. Higher is better; ties break deterministically.

**By the numbers**

| | |
|---|---|
| Corpus | 18,389 reviews (the Kaggle dataset lists 4 of them twice; `sg prepare-db` removes the duplicates), 217,152 chunks (389 characters on average) |
| Index | one 1.2 GB SQLite file: metadata, tags, vectors, full-text index |
| Latency | about 0.5 s per warm query on an AMD GPU (ROCm); 23 s cold start; CPU not measured |
| Stack | Python 3.12 &middot; Flask &middot; sentence-transformers &middot; sqlite-vec &middot; React + Vite |

**Why one SQLite file:** no vector database to run, trivially copyable, joins are plain SQL. The cost is a brute-force scan that won't scale to many millions of chunks, and a 1.2 GB file to ship.

## What is and isn't proven

No labelled quality data exists yet, so every change below was checked against a **weak proxy**: the share of the top 10 whose LLM tags contain a term relevant to the query, over 9 hand-written queries. It is partly circular, because the tags are inside the embedded text, so treat it as a smoke test.

| Change | What we measured | Verdict |
|---|---|---|
| BGE query prefix | Top 10 changes by 1&ndash;8 albums per query; proxy 0.74 &rarr; 0.77, with single queries swinging by up to 0.4 either way | Kept (it is the model's documented usage); **not shown to help** |
| Album scoring + 200-candidate pool | Albums matched by 1.1 &rarr; 1.4 chunks on average; proxy flat at 0.74&ndash;0.77; about +40 ms | Kept; **effect not measurable yet** |
| OR-ing lexical terms | Surfaced keyword hits (*Daydream Nation* for "dream pop") that displaced better vector results | Rejected |
| MMR re-ranking | Offline: swaps 2&ndash;5 of 10 albums, lowers list similarity by 0.02&ndash;0.07, costs at most 0.008 query similarity | **Not implemented**; relevance of the new list unjudged |

## Known limitations

- **The lexical half rarely contributes to mood queries.** A sentence-length query gets zero BM25 hits (AND semantics), so it is effectively vector-only. The full-text index covers tags and chunk text, not artist or album names.
- **Tag noise in the current data.** The tagging model used to echo the prompt's category names as tags: 20% of the stored chunks (43,860) carry *"Emotions"*, *"Feelings"*, *"Genres: ..."* and the like, and those words are embedded with the real tags. New builds cannot produce this: the prompt no longer reads like an output template (echoes fell from 25% to 0% on 60 real chunks, and from 19% to 0% in a 20-review end-to-end run) and every answer is cleaned before it is stored. Existing tags are unchanged, and cleaning them takes a re-tag or a re-embed.
- **Corpus bias:** Pitchfork only, 1999&ndash;2017.
- **No evaluation set.** The next step is about 30 judged mood queries to settle the open questions above.
- **Rebuilding is heavy:** tagging needs Ollama (about 20 hours) and embedding wants a GPU. The prebuilt database is not distributed yet, and `npm run build` fails on a type error in `components/ui/calendar.tsx` (`npm run dev` works).

## Run it

```bash
uv sync --extra dev --extra build        # or: pip install -e '.[dev,build]'   (Python 3.10+)
sg serve                                 # API on :5000, needs database.sqlite in the repo root (or SG_DB_PATH)
sg search "warm and unhurried"           # same search from the terminal
cd frontend && npm install && npm run dev    # UI on :3000

pytest                                   # 133 tests, no database, model or Ollama needed
```

**Rebuild the database from scratch** (tagging alone takes about 20 hours: it ran at 0.25 reviews/s with `qwen2.5:7b` on an AMD GPU; needs [Ollama](https://ollama.com) running with `qwen2.5:7b` pulled):

```bash
sg fetch-data      # download the Pitchfork dataset from Kaggle (and remove its duplicate rows)
sg build-tags      # chunk reviews + LLM mood tags (resumable; --limit N to try it out)
sg build-index     # embeddings + full-text index (incremental; --rebuild starts over)

sg prepare-db      # upgrade an existing database: drop duplicate reviews and chunks, add indexes (safe to repeat)
```

`POST /api/search {"query": "...", "top_n": 20, "k": 20}` returns `{"results": [{reviewid, artist, title, score, url, tags, relevance}], "max_relevance": 0.2731}`. `SG_DB_PATH` points at another database, and `SG_QUERY_PREFIX=""` disables the query prefix. `uv sync` installs the default PyPI torch; on ROCm or CPU-only machines install the matching torch wheel first.
