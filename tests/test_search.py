import pytest

from conftest import AMBIENT_QUERY
import api


def test_rrf_ranks_best_match_first(cursor):
    ranked = api.hybrid_search(cursor, "ambient", AMBIENT_QUERY, k=20)
    scores = [score for _, score in ranked]

    assert scores == sorted(scores, reverse=True)
    # Chunk 1 is the nearest vector AND a lexical hit for "ambient".
    assert ranked[0][0] == 1


def test_rrf_top_score_is_two_first_ranks(cursor):
    k = 20
    (rowid, score), *_ = api.hybrid_search(cursor, "ambient", AMBIENT_QUERY, k=k)
    # Rank 0 in the vector list: 1/(k+1). Lexical rank depends on BM25, so only
    # bound it: the best possible fused score is 2/(k+1).
    assert 1 / (k + 1) < score <= 2 / (k + 1)


def test_top_n_truncates_after_ranking(cursor):
    full = api.hybrid_search(cursor, "ambient", AMBIENT_QUERY)
    top2 = api.hybrid_search(cursor, "ambient", AMBIENT_QUERY, top_n=2)
    assert top2 == full[:2]


def test_vector_only_when_query_has_no_lexical_terms(cursor):
    ranked = api.hybrid_search(cursor, "   ", AMBIENT_QUERY)
    assert ranked  # vector results still come back
    assert ranked[0][0] == 1


@pytest.mark.parametrize("query", ['foo:bar', '"unbalanced', "it's", "AND", "(("])
def test_malformed_fts_queries_do_not_raise(cursor, query):
    api.hybrid_search(cursor, query, AMBIENT_QUERY)


# Album (artist) each fixture chunk belongs to; chunk 5 is an orphan.
ALBUM_OF_CHUNK = {1: "alpha", 2: "alpha", 3: "beta", 4: "gamma"}


def test_orphan_chunks_are_skipped_and_scores_stay_aligned(cursor):
    ranked = api.hybrid_search(cursor, "ambient", AMBIENT_QUERY, top_n=10, k=20)
    assert 5 in [rowid for rowid, _ in ranked]  # the orphan chunk really is a candidate

    results = api.search_albums(cursor, "ambient", AMBIENT_QUERY, top_n=10, k=20)

    # Every result keeps the score of its own chunk, even though the orphan
    # sitting in the middle of the ranking has no row to return.
    expected = [(ALBUM_OF_CHUNK[rowid], round(score, 4))
                for rowid, score in ranked if rowid != 5]
    assert [(r["artist"], r["relevance"]) for r in results] == expected
