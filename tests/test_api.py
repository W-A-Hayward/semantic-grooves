from conftest import AMBIENT_QUERY
from semantic_grooves import api, embedding, search


def test_health(client):
    assert client.get("/api/health").get_json() == {"status": "ok"}


def test_search_returns_ranked_unique_albums(client):
    resp = client.post("/api/search", json={"query": "ambient", "top_n": 10, "k": 20})
    assert resp.status_code == 200

    results = resp.get_json()["results"]
    assert results[0]["artist"] == "alpha"
    assert set(results[0]) == {"reviewid", "tags", "artist", "title", "score", "url", "relevance"}
    relevances = [r["relevance"] for r in results]
    assert relevances == sorted(relevances, reverse=True)
    reviewids = [r["reviewid"] for r in results]
    assert len(reviewids) == len(set(reviewids))


def test_defaults_apply(client):
    assert client.post("/api/search", json={"query": "ambient"}).status_code == 200


def test_missing_or_blank_query(client):
    assert client.post("/api/search", json={}).status_code == 400
    assert client.post("/api/search", json={"query": "   "}).status_code == 400
    assert client.post("/api/search", json={"query": 42}).status_code == 400


def test_non_json_body(client):
    assert client.post("/api/search", data="nope").status_code == 400
    assert client.post("/api/search", json=["a"]).status_code == 400


def test_invalid_numeric_params(client):
    for body in ({"top_n": 0}, {"top_n": 10_000}, {"top_n": "5"}, {"k": 0}, {"k": True}):
        resp = client.post("/api/search", json={"query": "ambient", **body})
        assert resp.status_code == 400, body


def test_db_connection_is_closed_when_search_fails(client, monkeypatch):
    closed = []

    class FakeDb:
        def cursor(self):
            return None

        def close(self):
            closed.append(True)

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(api, "get_db_connection", lambda: FakeDb())
    monkeypatch.setattr(api, "search_albums", boom)

    resp = client.post("/api/search", json={"query": "ambient"})
    assert resp.status_code == 500
    assert closed == [True]


def test_response_includes_max_relevance_for_scaling(client):
    body = client.post("/api/search", json={"query": "ambient", "k": 20}).get_json()
    assert body["max_relevance"] == round(search.max_relevance(20), 4)
    assert all(0 < r["relevance"] <= body["max_relevance"] for r in body["results"])


def test_search_embeds_the_query_with_the_prefix(client, monkeypatch):
    seen = []

    class Model:
        def encode(self, text, **kwargs):
            seen.append(text)
            return AMBIENT_QUERY

    monkeypatch.setattr(embedding, "get_model", lambda: Model())
    client.post("/api/search", json={"query": "ambient"})
    assert seen == [embedding.QUERY_PREFIX + "ambient"]


# --- read-only access ---

def test_the_api_opens_the_database_read_only(client):
    import sqlite3
    import pytest
    db = api.get_db_connection()
    try:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            db.execute("DELETE FROM review_tags")
    finally:
        db.close()
