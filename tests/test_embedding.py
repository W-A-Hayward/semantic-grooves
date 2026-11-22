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


def test_device_can_be_forced_with_an_environment_variable(monkeypatch):
    monkeypatch.setenv("SG_DEVICE", "cpu")
    assert embedding.resolve_device() == "cpu"
    monkeypatch.setenv("SG_DEVICE", "cuda:1")
    assert embedding.resolve_device() == "cuda:1"


def test_device_defaults_to_whatever_torch_reports(monkeypatch):
    import sys
    import types
    fake = types.SimpleNamespace(cuda=types.SimpleNamespace(is_available=lambda: True))
    monkeypatch.delenv("SG_DEVICE", raising=False)
    monkeypatch.setitem(sys.modules, "torch", fake)
    assert embedding.resolve_device() == "cuda"
    fake.cuda.is_available = lambda: False
    assert embedding.resolve_device() == "cpu"
