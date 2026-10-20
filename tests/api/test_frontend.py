"""Tests for fin_tracker.api.frontend."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from fin_tracker.api.frontend import mount_frontend


def build_dist(path_dist):
    """Minimal built frontend: an index and one asset."""
    (path_dist / "assets").mkdir(parents=True)
    (path_dist / "index.html").write_text("<html>app</html>", encoding="utf-8")
    (path_dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (path_dist.parent / "secret.txt").write_text("nope", encoding="utf-8")


def test_mount_frontend_without_build_does_nothing(tmp_path):
    assert mount_frontend(FastAPI(), tmp_path / "dist") is False


def test_mount_frontend_serves_files_and_spa_routes(tmp_path):
    path_dist = tmp_path / "dist"
    build_dist(path_dist)
    app = FastAPI()
    assert mount_frontend(app, path_dist) is True
    client = TestClient(app)

    assert client.get("/assets/app.js").text == "console.log(1)"
    # Client-side routes and the root get the app shell
    assert client.get("/movimientos").text == "<html>app</html>"
    assert client.get("/").text == "<html>app</html>"
    # Never files outside dist, and unknown API paths are real 404s
    assert client.get("/../secret.txt").text != "nope"
    assert client.get("/api/unknown").status_code == 404
