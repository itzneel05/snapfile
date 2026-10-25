"""End-to-end tests for the local web server: no model needed, no hangs allowed.

The deadlock regression these cover is real: /api/apply once called
serialise() while holding the same non-reentrant lock, which froze the whole
server. Every request here carries a timeout so a reintroduced lock bug fails
the suite instead of hanging it.
"""

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest
from PIL import Image

from snapfile import filer, web
from snapfile.web import Handler, PlanState

TIMEOUT = 5


def _shot_png(path: Path, text: str) -> None:
    img = Image.new("RGB", (64, 48), "#202020")
    from PIL import ImageDraw
    ImageDraw.Draw(img).text((4, 4), text, fill="#ffffff")
    img.save(path)


@pytest.fixture()
def graveyard(tmp_path: Path) -> Path:
    folder = tmp_path / "shots"
    folder.mkdir()
    _shot_png(folder / "a.png", "one")
    _shot_png(folder / "b.png", "two")
    (folder / "secret.txt").write_text("not an image")
    return folder


@pytest.fixture()
def server(graveyard, monkeypatch):
    """Real HTTP server with the model stubbed out to return instant verdicts."""

    def fake_judge(shot, host=None, model=None):
        shot.kind = "ui"
        shot.title = "Stub verdict"
        shot.keep = shot.path.name != "b.png"
        shot.reason = "stubbed"
        return shot

    monkeypatch.setattr(filer, "judge", fake_judge)
    # no Ollama in the test environment — model resolution must not hit the network
    monkeypatch.setattr(web, "pick_model", lambda host=None, preferred=None: "stub-model")

    state = PlanState()
    state.folder = graveyard
    state.out_root = graveyard / "sorted"
    handler = type("H", (Handler,), {"state": state, "html": b"<html></html>"})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    httpd.daemon_threads = True
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    yield base, state, graveyard
    httpd.shutdown()
    httpd.server_close()


def _get(base: str, path: str) -> tuple[int, bytes]:
    with urllib.request.urlopen(base + path, timeout=TIMEOUT) as resp:
        return resp.status, resp.read()


def _post(base: str, path: str, payload: dict) -> tuple[int, dict]:
    req = urllib.request.Request(
        base + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.status, json.loads(resp.read().decode())


def test_root_serves_html(server):
    status, body = _get(server[0], "/")
    assert status == 200
    assert b"<html" in body


def test_favicon_is_204(server):
    status, _ = _get(server[0], "/favicon.ico")
    assert status == 204


def test_results_reports_plan_state(server):
    base, state, folder = server
    state.plan(folder, folder / "sorted", "stub-model", None)
    status, body = _get(base, "/api/results")
    data = json.loads(body)
    assert status == 200
    assert data["state"] == "done"
    assert data["total"] == 2 and data["done"] == 2
    assert len(data["shots"]) == 2
    assert all(s["thumb"].startswith("/thumb?f=") for s in data["shots"])
    keeps = [s for s in data["shots"] if s["keep"]]
    assert keeps and keeps[0]["dest"].endswith(".png")


def test_apply_moves_keeps_and_reports(server):
    base, state, folder = server
    state.plan(folder, folder / "sorted", "stub-model", None)
    status, data = _post(base, "/api/apply", {"mode": "move"})
    assert status == 200
    assert data["applied"] is True
    assert data["moved"] == 1          # b.png is junk, never moved
    assert data["junk"] == 1
    assert (folder / "sorted" / "ui").exists()
    assert not (folder / "a.png").exists()
    assert (folder / "b.png").exists()  # junk untouched


def test_apply_is_idempotent(server):
    base, state, folder = server
    state.plan(folder, folder / "sorted", "stub-model", None)
    _, first = _post(base, "/api/apply", {"mode": "move"})
    _, second = _post(base, "/api/apply", {"mode": "move"})
    assert first["applied"] is second["applied"] is True
    assert second["moved"] == 0


def test_thumb_rejects_traversal(server):
    base, _state, _folder = server
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(base, "/thumb?f=../secret.txt")
    assert exc.value.code in (400, 403)


def test_thumb_serves_inside_folder(server):
    base, _state, folder = server
    status, body = _get(base, "/thumb?f=a.png")
    assert status == 200
    assert body[:8] == b"\x89PNG\r\n\x1a\n"
