import pytest
from flask import Flask

from semantic_grooves.api import register_frontend


@pytest.fixture
def site(tmp_path):
    root = tmp_path / "dist"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text("<html>home</html>")
    (root / "assets" / "app-123.js").write_text("console.log(1)")
    (root / "favicon.svg").write_text("<svg/>")
    (tmp_path / "secret.txt").write_text("outside the site")
    app = Flask("test")
    register_frontend(app, root)

    @app.route("/api/ping")
    def ping():
        return {"pong": True}

    return app.test_client()


def test_root_serves_the_page(site):
    resp = site.get("/")
    assert resp.status_code == 200 and b"home" in resp.data
    assert "no-cache" in resp.headers["Cache-Control"]      # a new build must show up at once


def test_files_are_served_and_assets_are_cached_for_a_year(site):
    assert site.get("/favicon.svg").data == b"<svg/>"
    resp = site.get("/assets/app-123.js")
    assert resp.data == b"console.log(1)"
    assert "max-age=31536000" in resp.headers["Cache-Control"]


def test_unknown_paths_fall_back_to_the_page_for_client_side_routes(site):
    resp = site.get("/some/client/route")
    assert resp.status_code == 200 and b"home" in resp.data


def test_api_routes_still_win_and_unknown_api_paths_are_a_json_404(site):
    assert site.get("/api/ping").get_json() == {"pong": True}
    resp = site.get("/api/nope")
    assert resp.status_code == 404 and resp.get_json() == {"error": "Not found"}
    assert site.get("/api").status_code == 404


@pytest.mark.parametrize("path", ["/../secret.txt", "/%2e%2e/secret.txt", "/assets/../../secret.txt",
                                  "/..%2fsecret.txt", "//etc/passwd"])
def test_paths_cannot_escape_the_site_folder(site, path):
    resp = site.get(path)
    assert b"outside the site" not in resp.data
    assert b"root:" not in resp.data


def test_a_folder_without_index_html_is_rejected(tmp_path):
    with pytest.raises(FileNotFoundError, match="npm run build"):
        register_frontend(Flask("x"), tmp_path)
