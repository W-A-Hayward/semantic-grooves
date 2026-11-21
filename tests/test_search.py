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


def test_one_result_per_album(cursor):
    results = api.search_albums(cursor, "ambient", AMBIENT_QUERY, top_n=10)
    reviewids = [r["reviewid"] for r in results]
    assert len(reviewids) == len(set(reviewids))
    # Chunks 1 and 2 both belong to album 1; only the best one is kept.
    assert reviewids.count(1) == 1


def test_orphan_chunks_are_skipped_and_scores_stay_aligned(cursor):
    ranked = dict(api.hybrid_search(cursor, "ambient", AMBIENT_QUERY, k=20))
    assert 5 in ranked  # the orphan chunk really is a candidate
    results = api.search_albums(cursor, "ambient", AMBIENT_QUERY, top_n=10, k=20)

    assert 99 not in [r["reviewid"] for r in results]
    # Chunk 5 (orphan) sits between chunks 1 and 4 in the ranking. Every
    # returned relevance must be the score of the album's own best chunk.
    best_chunk = {1: 1, 3: 4, 2: 3}
    for r in results:
        assert r["relevance"] == pytest.approx(ranked[best_chunk[r["reviewid"]]], abs=1e-4)


def test_results_sorted_best_first_with_expected_albums(cursor):
    results = api.search_albums(cursor, "ambient", AMBIENT_QUERY, top_n=10)
    relevances = [r["relevance"] for r in results]
    assert relevances == sorted(relevances, reverse=True)
    assert results[0]["artist"] == "alpha"


def test_top_n_limits_albums(cursor):
    assert len(api.search_albums(cursor, "ambient", AMBIENT_QUERY, top_n=1)) == 1
