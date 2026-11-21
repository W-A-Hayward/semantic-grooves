from conftest import AMBIENT_QUERY
from semantic_grooves import embedding


class RecordingModel:
    def __init__(self):
        self.texts = []

    def encode(self, text, **kwargs):
        self.texts.append(text)
        return AMBIENT_QUERY


def test_embed_query_adds_the_bge_instruction_prefix(monkeypatch):
    model = RecordingModel()
    monkeypatch.setattr(embedding, "get_model", lambda: model)
    embedding.embed_query("warm and unhurried")
    assert model.texts == [embedding.QUERY_PREFIX + "warm and unhurried"]
    assert embedding.QUERY_PREFIX.startswith("Represent this sentence for searching relevant passages")


def test_embed_query_prefix_can_be_disabled(monkeypatch):
    model = RecordingModel()
    monkeypatch.setattr(embedding, "get_model", lambda: model)
    monkeypatch.setattr(embedding, "QUERY_PREFIX", "")
    embedding.embed_query("warm and unhurried")
    assert model.texts == ["warm and unhurried"]
