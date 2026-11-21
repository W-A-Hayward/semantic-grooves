import asyncio
import sqlite3

import pytest

from conftest import SOURCE_CONTENT, StubOllama
from semantic_grooves.pipeline import tagging


# --- chunking ---

def test_short_text_stays_one_chunk():
    assert tagging.chunk_text("short") == [(0, "short")]
    assert tagging.chunk_text("x" * 400) == [(0, "x" * 400)]


def test_long_text_slides_by_size_minus_overlap():
    chunks = tagging.chunk_text("x" * 1000, chunk_size=400, overlap=50)
    assert [start for start, _ in chunks] == [0, 350, 700]
    assert [len(chunk) for _, chunk in chunks] == [400, 400, 300]


def test_chunks_overlap():
    text = "".join(chr(97 + i % 26) for i in range(1000))
    (_, first), (_, second), _ = tagging.chunk_text(text, 400, 50)
    assert first[-50:] == second[:50]


def test_trailing_chunk_shorter_than_min_tail_is_dropped():
    # 420 chars: the second window (start 350) would be 70 chars long.
    assert [start for start, _ in tagging.chunk_text("x" * 420)] == [0]


def test_full_overlap_still_terminates():
    assert len(tagging.chunk_text("x" * 130, chunk_size=100, overlap=100)) > 1


# --- tagging one chunk / one review ---

def test_get_tags_strips_the_response():
    assert asyncio.run(tagging.get_tags(StubOllama(), "text")) == "calm, piano"


def test_get_tags_returns_none_when_the_call_fails(capsys):
    assert asyncio.run(tagging.get_tags(StubOllama(fail_on=["text"]), "text")) is None
    assert "Error calling Ollama" in capsys.readouterr().out


def test_the_same_error_is_only_printed_once(capsys):
    tagging._reported.clear()
    client = StubOllama(fail_on=["text"])
    for _ in range(5):
        asyncio.run(tagging.get_tags(client, "text"))
    assert capsys.readouterr().out.count("Error calling Ollama") == 1


def test_prompt_contains_the_chunk_and_asks_for_tags_only():
    client = StubOllama()
    asyncio.run(tagging.get_tags(client, "THE CHUNK"))
    prompt = client.prompts[0]
    assert "THE CHUNK" in prompt
    assert "ONLY the tags" in prompt
    assert "Never write the words Emotions, Feelings, Instruments, Genres or Effects" in prompt


def test_the_prompt_is_not_an_output_template():
    """The old wording ('a comma-separated list of: Emotions, Feelings, ...') made the
    model echo the category names back as tags in about a quarter of its answers."""
    assert "list of:" not in tagging.PROMPT
    assert "wistful" not in tagging.PROMPT          # example tags get copied into unrelated answers


def test_get_tags_cleans_the_model_answer():
    class Noisy(StubOllama):
        async def generate(self, model, prompt, options):
            return {"response": "Emotions, Feelings, Genres - calm,flashes_of_bravado, folk, none"}

    assert asyncio.run(tagging.get_tags(Noisy(), "text")) == "calm, flashes of bravado, folk"


def test_an_answer_with_nothing_left_after_cleaning_is_treated_as_a_failure():
    class OnlyLabels(StubOllama):
        async def generate(self, model, prompt, options):
            return {"response": "Emotions, Feelings, Instruments, Genres, Effects"}

    assert asyncio.run(tagging.get_tags(OnlyLabels(), "text")) is None


def test_tag_review_keeps_only_chunks_that_were_tagged():
    content = "A" * 400 + "B" * 400 + "C" * 400   # 4 windows at 0, 350, 700, 1050
    client = StubOllama(fail_on=["B" * 100 + "C"])    # fails the window straddling B and C
    tagged = asyncio.run(tagging.tag_review(client, content))
    assert 0 < len(tagged) < len(tagging.chunk_text(content))


# --- full run ---

@pytest.fixture
def source_db(source_db_path):
    db = sqlite3.connect(source_db_path)
    yield db
    db.close()


def test_run_tags_every_review_and_creates_the_table(source_db):
    client = StubOllama()
    result = asyncio.run(tagging.run(source_db, client=client, progress=lambda m: None))

    assert result == tagging.Result(tagged=3, failed=0)
    rows = source_db.execute("SELECT reviewid, chunk, tags FROM review_tags").fetchall()
    assert len(rows) == 5                                    # 3 + 1 + 1 chunks
    assert {tags for _, _, tags in rows} == {"calm, piano"}
    assert {rid for rid, _, _ in rows} == set(SOURCE_CONTENT)
    assert len(client.prompts) == 5


def test_stored_chunks_are_the_review_text(source_db):
    asyncio.run(tagging.run(source_db, client=StubOllama(), progress=lambda m: None))
    chunks = [c for (c,) in source_db.execute(
        "SELECT chunk FROM review_tags WHERE reviewid = 2")]
    assert chunks == [SOURCE_CONTENT[2]]


def test_run_is_resumable(source_db):
    asyncio.run(tagging.run(source_db, client=StubOllama(), limit=1, progress=lambda m: None))
    assert source_db.execute("SELECT COUNT(DISTINCT reviewid) FROM review_tags").fetchone()[0] == 1

    client = StubOllama()
    result = asyncio.run(tagging.run(source_db, client=client, progress=lambda m: None))
    assert result.tagged == 2                                 # only the remaining reviews
    assert source_db.execute("SELECT COUNT(DISTINCT reviewid) FROM review_tags").fetchone()[0] == 3

    assert asyncio.run(tagging.run(source_db, client=StubOllama(), progress=lambda m: None)) == (0, 0)


def test_a_review_whose_tagging_fails_is_retried_next_run(source_db):
    broken = StubOllama(fail_on=["short and sweet"])
    result = asyncio.run(tagging.run(source_db, client=broken, progress=lambda m: None))
    assert result == tagging.Result(tagged=2, failed=1)
    stored = {r for (r,) in source_db.execute("SELECT DISTINCT reviewid FROM review_tags")}
    assert stored == {1, 3}

    assert asyncio.run(tagging.run(source_db, client=StubOllama(), progress=lambda m: None)).tagged == 1
    assert source_db.execute("SELECT COUNT(DISTINCT reviewid) FROM review_tags").fetchone()[0] == 3


def test_limit_and_batch_size(source_db):
    messages = []
    asyncio.run(tagging.run(source_db, client=StubOllama(), batch_size=1, limit=2,
                            progress=messages.append))
    assert len(messages) == 2                                 # two batches of one review
    assert source_db.execute("SELECT COUNT(DISTINCT reviewid) FROM review_tags").fetchone()[0] == 2


def test_run_aborts_when_the_model_is_unreachable(source_db):
    source_db.executemany("INSERT INTO content VALUES (?, ?)",
                          [(100 + i, f"filler review number {i}") for i in range(15)])
    source_db.commit()
    down = StubOllama(fail_on=[""])                           # every call fails

    with pytest.raises(tagging.TaggingError, match="ollama serve"):
        asyncio.run(tagging.run(source_db, client=down, batch_size=5, progress=lambda m: None))

    assert len(down.prompts) < 18                             # stopped early, not all 18 reviews
    assert source_db.execute("SELECT COUNT(*) FROM review_tags").fetchone()[0] == 0


def test_an_isolated_failure_does_not_abort_the_run(source_db):
    result = asyncio.run(tagging.run(source_db, client=StubOllama(fail_on=["short and sweet"]),
                                     progress=lambda m: None))
    assert result.failed == 1 and result.tagged == 2


# --- clean_tags ---

@pytest.mark.parametrize("raw, expected", [
    # echoed category header, in the shapes found in a real database
    ("Emotions, Feelings, Instruments, Genres, Effects - upbeat, energetic", "upbeat, energetic"),
    ("Emotions, Feelings, Instruments, Genres, Effects: strange, folk rock", "strange, folk rock"),
    ("Emotions, Feelings, Intensity, Instruments, Drums, Genres, Death Metal, Effects, Thrashing",
     "Intensity, Drums, Death Metal, Thrashing"),
    ("Genres: rock, pop", "rock, pop"),
    ("Genres: Instruments: rock", "rock"),
    ("instruments(piano), genres(jazz)", "piano, jazz"),
    ("Emotions, Feelings: Retched\nInstruments: Drums (programmed)\nGenres: jazz",
     "Retched, Drums (programmed), jazz"),
    # filler
    ("calm, none, Instruments: not explicitly mentioned, Genres not specified, folk", "calm, folk"),
    ("calm, N/A, unknown, unclear", "calm"),
    # formatting
    ("dry,manic,bent synth", "dry, manic, bent synth"),
    ("flashes_of_bravado, chamber_pop", "flashes of bravado, chamber pop"),
    ("- calm\n- serene\n1. folk", "calm, serene, folk"),
    ('"calm", \'serene\', folk.', "calm, serene, folk"),
    ("calm, Calm, CALM, folk", "calm, folk"),                  # case-insensitive dedupe keeps the first
    # real words that merely start like a label or filler must survive
    ("genre-bending, effects-heavy, emotional, instrumental", "genre-bending, effects-heavy, emotional, instrumental"),
    ("none-of-your-business, unknowable, nonetheless", "none-of-your-business, unknowable, nonetheless"),
    ("Special Effects, Sound Effects, Genres Blend", "Special Effects, Sound Effects, Genres Blend"),
    # casing and order are preserved
    ("Sadness, Piano, ambient", "Sadness, Piano, ambient"),
])
def test_clean_tags(raw, expected):
    assert tagging.clean_tags(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "   ", "Emotions, Feelings", "Genres and Effects", "none", "Instruments:"])
def test_clean_tags_returns_none_when_nothing_is_left(raw):
    assert tagging.clean_tags(raw) is None


def test_clean_tags_is_idempotent():
    once = tagging.clean_tags("Emotions, Feelings - calm,flashes_of_bravado, Genres: folk, none")
    assert tagging.clean_tags(once) == once


# --- the preparation step runs as part of tagging ---

def test_run_dedupes_the_source_and_indexes_review_tags(tmp_path):
    from conftest import build_kaggle_db
    db = sqlite3.connect(build_kaggle_db(tmp_path / "dup.sqlite"))

    result = asyncio.run(tagging.run(db, client=StubOllama(), progress=lambda m: None))

    assert result.tagged == 3                                  # review 2 is tagged once, not twice
    chunks_of_2 = db.execute("SELECT COUNT(*) FROM review_tags WHERE reviewid = 2").fetchone()[0]
    assert chunks_of_2 == 1
    names = {n for (n,) in db.execute("SELECT name FROM sqlite_master WHERE type = 'index'")}
    assert "review_tags_reviewid" in names
    db.close()
