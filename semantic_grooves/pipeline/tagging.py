"""Step 1: split reviews into chunks and tag each chunk's mood with a local LLM.

Reads `content` (reviewid, content) and writes `review_tags` (reviewid, chunk,
tags). Safe to interrupt and re-run: reviews that already have chunks are skipped.
"""
import asyncio
import re
import time
from collections import namedtuple

from .prepare import prepare_database

DEFAULT_MODEL = "qwen2.5:7b"
CHUNK_SIZE = 400
OVERLAP = 50
BATCH_SIZE = 10
MIN_TAIL = 100  # a trailing chunk shorter than this is dropped
MAX_CONSECUTIVE_FAILURES = 10  # abort when this many reviews in a row get no tags

SCHEMA = """
    CREATE TABLE IF NOT EXISTS review_tags (
        reviewid INTEGER REFERENCES reviews(reviewid),
        chunk NVARCHAR,
        tags NVARCHAR
    )
"""

# The previous wording ("Return ONLY a comma-separated list of: Emotions, Feelings,
# Instruments, Genres and effects") read like an output template, and in about a
# quarter of answers the model echoed those category names back as tags. This
# wording asks for descriptive tags and forbids the labels. No example tags are
# given on purpose: the model copies them into unrelated answers.
PROMPT = (
    "Read this excerpt from a music review and write short descriptive tags for it: the moods and "
    "feelings it conveys, the instruments and genres it mentions or implies, and any notable sound "
    "qualities. Answer with ONLY the tags on a single line, separated by commas. Never write the "
    "words Emotions, Feelings, Instruments, Genres or Effects as labels or headings.\n\n"
    "Excerpt: {text}"
)


_reported = set()


def report_error(message):
    """Print an error once; a dead model would otherwise print it for every chunk."""
    if message not in _reported:
        _reported.add(message)
        print(message)


# The model sometimes echoes the category names from the prompt instead of (or
# around) the tags: "Emotions, Feelings, Genres - calm, folk", "Genres: rock",
# "instruments(piano)". These words are never real tags.
_LABEL = r"(?:emotions?|feelings?|instruments?|genres?|effects?)"
_LABELS_ONLY = re.compile(rf"{_LABEL}(?:\s*(?:,|&|/|and)\s*{_LABEL})*", re.I)
# "Genres: x", "Genres - x" (spaces required: "genre-bending" is a real word), "Genres(x)"
_LABEL_PREFIX = re.compile(
    rf"^{_LABEL}(?:\s*(?:,|&|/|and)\s*{_LABEL})*(?::\s*|\s+[\-\u2013\u2014]\s+|\s*\(\s*)", re.I)


# Whole tags that say nothing: "none", "not specified", "instruments not mentioned", ...
_FILLER = re.compile(
    rf"(?:none|n/?a|unknown|unclear|unspecified|not applicable"
    rf"|(?:{_LABEL}\s+)?not\s+(?:explicitly\s+|specifically\s+)?(?:mentioned|specified|stated|applicable|provided)"
    rf"(?:\s+but\s+implied)?"
    rf"|no\s+(?:specific\s+)?{_LABEL}\s+(?:mentioned|specified))",
    re.I)


def clean_tags(raw):
    """Normalise a model answer into a clean comma-separated tag list.

    Removes echoed category names (whole-tag "Emotions", "Genres: " prefixes,
    "Instruments(...)" wrappers) and filler ("none", "not specified"), turns underscores into spaces, flattens
    line breaks and bullets, drops empty and duplicate tags (case-insensitively)
    and keeps the original casing and order. Returns None when nothing is left, so the chunk is retried later.
    """
    if not raw:
        return None
    tags, seen = [], set()
    for tag in re.split(r"[,\n;]", raw):
        tag = tag.replace("_", " ").strip().strip("\"'`*").strip()
        tag = re.sub(r"^(?:[-\u2022*]|\d+[.)])\s+", "", tag)
        while True:                               # "Genres: Instruments: rock" -> "rock"
            stripped = _LABEL_PREFIX.sub("", tag, count=1)
            if stripped == tag:
                break
            tag = stripped
        tag = tag.strip().strip("\"'`*").rstrip(".").strip()
        if tag.endswith(")") and "(" not in tag:  # leftover of "genres(rap, jazz)"
            tag = tag.rstrip(")").strip()
        if not tag or _LABELS_ONLY.fullmatch(tag) or _FILLER.fullmatch(tag):
            continue
        key = tag.lower()
        if key not in seen:
            seen.add(key)
            tags.append(tag)
    return ", ".join(tags) or None


class TaggingError(RuntimeError):
    """Tagging cannot continue (typically the LLM is unreachable)."""


# tagged: reviews stored; failed: reviews that got no tags (retried on the next run)
Result = namedtuple("Result", "tagged failed")


def make_client():
    """An async Ollama client (needs `ollama serve` running)."""
    try:
        from ollama import AsyncClient
    except ImportError as e:
        raise RuntimeError("ollama is not installed. Run: pip install 'semantic-grooves[build]'") from e
    return AsyncClient()


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=OVERLAP):
    """Split a review into overlapping chunks; returns [(start_index, chunk)].

    Text that fits in one chunk stays whole. Otherwise a window of `chunk_size`
    characters slides by `chunk_size - overlap`, and a trailing window shorter
    than MIN_TAIL characters is dropped.
    """
    if len(text) <= chunk_size:
        return [(0, text)]
    step = max(1, chunk_size - overlap)
    chunks = []
    for start in range(0, len(text), step):
        chunk = text[start:start + chunk_size]
        if len(chunk) < MIN_TAIL and start > 0:
            break
        chunks.append((start, chunk))
    return chunks


async def get_tags(client, text, model=DEFAULT_MODEL):
    """Ask the LLM for the mood tags of one chunk, cleaned; None when the call fails or yields nothing."""
    try:
        response = await client.generate(
            model=model,
            prompt=PROMPT.format(text=text),
            options={"temperature": 0, "num_ctx": 4096},
        )
        return clean_tags(response['response'])
    except Exception as e:
        report_error(f"Error calling Ollama: {e}")
        return None


async def tag_review(client, content, model=DEFAULT_MODEL, chunk_size=CHUNK_SIZE, overlap=OVERLAP):
    """Tag every chunk of a review; returns [(tags, chunk)] for the chunks that succeeded."""
    rows = []
    for _, chunk in chunk_text(content, chunk_size, overlap):
        tags = await get_tags(client, chunk, model)
        if tags:
            rows.append((tags, chunk))
    return rows


async def process_review(client, db, row, **options):
    """Tag one review and store its chunks; returns how many chunks were stored.

    A review with no usable tags stores nothing (0), so it is retried next run.
    """
    review_id, content = row
    tagged = await tag_review(client, content, **options)
    if tagged:
        db.executemany(
            "INSERT INTO review_tags (reviewid, tags, chunk) VALUES (?, ?, ?)",
            [(review_id, tags, chunk) for tags, chunk in tagged],
        )
        db.commit()
    return len(tagged)


def pending_batches(db, batch_size=BATCH_SIZE, limit=None):
    """Yield batches of (reviewid, content) for reviews that have no chunks yet."""
    cursor = db.cursor()
    cursor.execute("""
        SELECT reviewid, content FROM content
        WHERE reviewid NOT IN (SELECT DISTINCT reviewid FROM review_tags)
    """)
    remaining = limit
    while remaining is None or remaining > 0:
        rows = cursor.fetchmany(batch_size if remaining is None else min(batch_size, remaining))
        if not rows:
            break
        if remaining is not None:
            remaining -= len(rows)
        yield rows


async def run(db, client=None, model=DEFAULT_MODEL, batch_size=BATCH_SIZE,
              chunk_size=CHUNK_SIZE, overlap=OVERLAP, limit=None, progress=print):
    """Tag all pending reviews (up to `limit`); returns Result(tagged, failed).

    Raises TaggingError after MAX_CONSECUTIVE_FAILURES reviews in a row got no
    tags, which means the model is unreachable rather than one review being odd.
    """
    db.execute(SCHEMA)
    prepare_database(db)
    _reported.clear()
    client = client or make_client()
    options = dict(model=model, chunk_size=chunk_size, overlap=overlap)
    tagged = failed = streak = 0
    for batch in pending_batches(db, batch_size, limit):
        started = time.perf_counter()
        stored = await asyncio.gather(*(process_review(client, db, row, **options) for row in batch))
        for chunks_stored in stored:
            if chunks_stored:
                tagged += 1
                streak = 0
            else:
                failed += 1
                streak += 1
        elapsed = max(time.perf_counter() - started, 1e-9)
        progress(f"Batch done | tagged: {tagged} | failed: {failed} | {len(batch) / elapsed:.2f} reviews/s")
        if streak >= MAX_CONSECUTIVE_FAILURES:
            raise TaggingError(
                f"{streak} reviews in a row got no tags. Is `ollama serve` running and "
                f"is the model pulled (`ollama pull {model}`)?"
            )
    return Result(tagged, failed)
