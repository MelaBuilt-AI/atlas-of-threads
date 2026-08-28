from __future__ import annotations

import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from thought_archaeology.inhabit import inhabit
from thought_archaeology.serve import ServeError, make_server, viz_dist_path
from thought_archaeology.store import Store

from tests.helpers import FIXTURES
from tests.test_cli import run


def _compile_simple(store: Path) -> tuple[str, str]:
    code, out, err = run(["init", "--title", "s"], store=store)
    assert code == 0, err
    sid = out.strip()
    code, out, err = run(
        [
            "compile",
            "--session",
            sid,
            "--mode",
            "posthoc",
            "--transcript",
            str(FIXTURES / "transcripts" / "simple-freeform.jsonl"),
            "--from-graph",
            str(FIXTURES / "graphs" / "simple.gold.json"),
        ],
        store=store,
    )
    assert code == 0, err
    return sid, out.strip()


@pytest.fixture
def httpd_url(tmp_path: Path):
    store_path = tmp_path / "data"
    _compile_simple(store_path)
    dist = viz_dist_path()
    httpd = make_server(Store(store_path), port=0, dist=dist)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host, port = httpd.server_address[:2]
    yield f"http://{host}:{port}"
    httpd.shutdown()
    httpd.server_close()


def _get(url: str) -> tuple[int, str, str]:
    try:
        with urlopen(url, timeout=5) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, body, resp.headers.get_content_type()
    except HTTPError as exc:
        return exc.code, exc.read().decode("utf-8"), "application/json"


def test_health_and_static_shell(httpd_url: str):
    code, body, ctype = _get(httpd_url + "/api/health")
    assert code == 200
    assert json.loads(body)["ok"] is True
    assert json.loads(body)["write"] is False
    code, body, ctype = _get(httpd_url + "/")
    assert code == 200
    assert "Inhabit Space" in body
    assert "not a circuit trace" in body
    assert "dashboard" not in body.lower() or "not a dashboard" in body.lower()


def test_inhabit_json_matches_cli(httpd_url: str, tmp_path: Path):
    store_path = tmp_path / "data"
    st = Store(store_path)
    sessions = json.loads(_get(httpd_url + "/api/sessions")[1])
    spawn = sessions["sessions"][0]["spawn"]
    nid = spawn["node_id"]
    gid = spawn["graph_id"]
    code, body, _ = _get(httpd_url + f"/api/inhabit/{nid}?graph={gid}")
    assert code == 200
    payload = json.loads(body)
    view = inhabit(st, nid, graph_id=gid)
    assert payload["graph_id"] == view.graph.id
    assert payload["node"]["id"] == view.node.id
    assert payload["caption"] == "story graph, not a circuit trace"
    assert {n["text"] for n in payload["shaped"]} == {n.text for n in view.shaped}
    assert {n["text"] for n in payload["rejected_siblings"]} == {
        n.text for n in view.rejected_siblings
    }
    assert "feature_ids" not in body
    assert "hidden_reasoning" not in body


def test_writes_rejected(httpd_url: str):
    req = Request(httpd_url + "/api/sessions", method="POST", data=b"{}")
    try:
        urlopen(req, timeout=5)
        raise AssertionError("POST should fail")
    except HTTPError as exc:
        assert exc.code == 405


def test_serve_refuses_non_localhost():
    with pytest.raises(ServeError, match="localhost"):
        make_server(Store("/tmp"), bind="0.0.0.0", port=0)


def test_cli_serve_bad_bind(tmp_path: Path):
    store = tmp_path / "data"
    run(["init", "--title", "t"], store=store)
    code, _, err = run(["serve", "--bind", "0.0.0.0"], store=store)
    assert code == 2
    assert "localhost" in err
