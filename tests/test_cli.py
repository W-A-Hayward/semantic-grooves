import sqlite3

import pytest

from conftest import CHUNKS, StubEmbedder, StubModel, StubOllama
from semantic_grooves import cli, embedding, search
from semantic_grooves.pipeline import dataset, tagging


def test_version(capsys):
    with pytest.raises(SystemExit) as e:
        cli.main(["--version"])
    assert e.value.code == 0
    assert "sg " in capsys.readouterr().out


def test_a_command_is_required():
    with pytest.raises(SystemExit):
        cli.main([])


# --- search ---

def test_search_prints_ranked_albums(db_path, monkeypatch, capsys):
    monkeypatch.setenv("SG_DB_PATH", db_path)
    monkeypatch.setattr(embedding, "get_model", lambda: StubModel())

    assert cli.main(["search", "slow", "ambient", "music", "-n", "2"]) == 0

    out = capsys.readouterr().out
    assert " 1. alpha - album one" in out
    assert "ambient" in out                      # the tags line
    assert " 3. " not in out                     # -n 2 limits the list


def test_search_without_results(db_path, monkeypatch, capsys):
    monkeypatch.setenv("SG_DB_PATH", db_path)
    monkeypatch.setattr(embedding, "get_model", lambda: StubModel())
    monkeypatch.setattr(search, "search_albums", lambda *a, **k: [])
    assert cli.main(["search", "anything"]) == 0
    assert "No results." in capsys.readouterr().out


# --- serve ---

def test_serve_passes_host_port_and_debug_to_flask(monkeypatch):
    from semantic_grooves import api
    calls = []
    monkeypatch.setattr(api.app, "run", lambda **kw: calls.append(kw))

    assert cli.main(["serve", "--host", "0.0.0.0", "--port", "8080"]) == 0
    assert cli.main(["serve", "--debug"]) == 0
    assert calls == [
        {"host": "0.0.0.0", "port": 8080, "debug": False},
        {"host": "127.0.0.1", "port": 5000, "debug": True},
    ]


# --- fetch-data ---

@pytest.fixture
def fake_kaggle(tmp_path, monkeypatch):
    folder = tmp_path / "kaggle-cache"
    folder.mkdir()
    (folder / "database.sqlite").write_bytes(b"downloaded")
    monkeypatch.setattr(dataset, "download_dataset", lambda: folder)


def test_fetch_data_copies_the_database(fake_kaggle, tmp_path, capsys):
    dest = tmp_path / "out" / "database.sqlite"
    assert cli.main(["fetch-data", "--dest", str(dest)]) == 0
    assert dest.read_bytes() == b"downloaded"
    assert not (tmp_path / "out" / "database.sqlite.part").exists()
    assert "Saved" in capsys.readouterr().out


def test_fetch_data_uses_sg_db_path_by_default(fake_kaggle, tmp_path, monkeypatch):
    dest = tmp_path / "from-env.sqlite"
    monkeypatch.setenv("SG_DB_PATH", str(dest))
    assert cli.main(["fetch-data"]) == 0
    assert dest.exists()


def test_fetch_data_never_overwrites_without_force(fake_kaggle, tmp_path, capsys):
    dest = tmp_path / "database.sqlite"
    dest.write_bytes(b"hours of embeddings")

    assert cli.main(["fetch-data", "--dest", str(dest)]) == 1
    assert dest.read_bytes() == b"hours of embeddings"
    assert "--force" in capsys.readouterr().err

    assert cli.main(["fetch-data", "--dest", str(dest), "--force"]) == 0
    assert dest.read_bytes() == b"downloaded"


def test_fetch_data_explains_a_missing_kagglehub(tmp_path, monkeypatch, capsys):
    import builtins
    real_import = builtins.__import__

    def no_kaggle(name, *args, **kwargs):
        if name == "kagglehub":
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_kaggle)
    assert cli.main(["fetch-data", "--dest", str(tmp_path / "x.sqlite")]) == 1
    assert "semantic-grooves[build]" in capsys.readouterr().err


# --- build-tags / build-index ---

def test_build_tags_tags_pending_reviews(source_db_path, monkeypatch, capsys):
    monkeypatch.setenv("SG_DB_PATH", source_db_path)
    monkeypatch.setattr(tagging, "make_client", lambda: StubOllama())

    assert cli.main(["build-tags", "--limit", "2"]) == 0

    assert "Tagged 2 reviews." in capsys.readouterr().out
    db = sqlite3.connect(source_db_path)
    assert db.execute("SELECT COUNT(DISTINCT reviewid) FROM review_tags").fetchone()[0] == 2


def test_build_tags_reports_reviews_that_got_no_tags(source_db_path, monkeypatch, capsys):
    monkeypatch.setenv("SG_DB_PATH", source_db_path)
    monkeypatch.setattr(tagging, "make_client", lambda: StubOllama(fail_on=["short and sweet"]))

    assert cli.main(["build-tags"]) == 0
    assert "Tagged 2 reviews. 1 got no tags and will be retried" in capsys.readouterr().out


def test_build_tags_fails_when_ollama_is_unreachable(source_db_path, monkeypatch, capsys):
    db = sqlite3.connect(source_db_path)
    db.executemany("INSERT INTO content VALUES (?, ?)", [(100 + i, f"filler {i}") for i in range(15)])
    db.commit()
    db.close()
    monkeypatch.setenv("SG_DB_PATH", source_db_path)
    monkeypatch.setattr(tagging, "make_client", lambda: StubOllama(fail_on=[""]))

    assert cli.main(["build-tags"]) == 1
    assert "ollama serve" in capsys.readouterr().err


def test_build_tags_reports_a_missing_ollama(source_db_path, monkeypatch, capsys):
    def missing():
        raise RuntimeError("ollama is not installed")

    monkeypatch.setenv("SG_DB_PATH", source_db_path)
    monkeypatch.setattr(tagging, "make_client", missing)
    assert cli.main(["build-tags"]) == 1
    assert "ollama is not installed" in capsys.readouterr().err


def test_build_index_indexes_the_tagged_chunks(tagged_db_path, monkeypatch, capsys):
    monkeypatch.setenv("SG_DB_PATH", tagged_db_path)
    monkeypatch.setattr(embedding, "get_model", lambda: StubEmbedder())

    assert cli.main(["build-index"]) == 0
    assert f"Indexed {len(CHUNKS)} new chunks." in capsys.readouterr().out

    assert cli.main(["build-index"]) == 0
    assert "Indexed 0 new chunks." in capsys.readouterr().out
