from __future__ import annotations

import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from thought_archaeology.inhabit import inhabit
from thought_archaeology.serve import (
    ServeError,
    bootstrap_payload,
    make_server,
    viz_dist_path,
)
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


def _get_bytes(url: str) -> tuple[int, bytes, str]:
    with urlopen(url, timeout=5) as resp:
        return resp.status, resp.read(), resp.headers.get_content_type()


def _post(url: str, payload: dict) -> tuple[int, str]:
    raw = json.dumps(payload).encode("utf-8")
    req = Request(
        url,
        data=raw,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(req, timeout=5) as resp:
            return resp.status, resp.read().decode("utf-8")
    except HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


def test_health_and_static_shell(httpd_url: str):
    code, body, ctype = _get(httpd_url + "/api/health")
    assert code == 200
    assert json.loads(body)["ok"] is True
    assert json.loads(body)["write"] is True
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
    assert "read" in payload
    assert payload["evidence"] == []
    assert "does not erase" in payload["read"]["fork_line"]
    assert "human no" in payload["read"]["veto_line"]
    assert {n["text"] for n in payload["shaped"]} == {n.text for n in view.shaped}
    assert {n["text"] for n in payload["rejected_siblings"]} == {
        n.text for n in view.rejected_siblings
    }
    assert "feature_ids" not in body
    assert "hidden_reasoning" not in body


def test_inhabit_json_carries_evidence_without_javascript_inference(
    httpd_url: str, tmp_path: Path
):
    from thought_archaeology.evidence import EvidenceBinding
    from thought_archaeology.ids import new_ulid, now_iso
    from thought_archaeology.models import SCHEMA_VERSION

    store_path = tmp_path / "data"
    store = Store(store_path)
    sessions = json.loads(_get(httpd_url + "/api/sessions")[1])
    spawn = sessions["sessions"][0]["spawn"]
    graph = store.load_graph(spawn["graph_id"])
    binding = EvidenceBinding(
        SCHEMA_VERSION,
        new_ulid(),
        graph.id,
        spawn["node_id"],
        "behavioral_intervention",
        "inconclusive",
        "The intervention did not settle this thought.",
        ("probe:test",),
        now_iso(),
    )
    store.write_evidence(graph.session_id, binding.to_dict())
    code, body, _ = _get(
        httpd_url + f"/api/inhabit/{spawn['node_id']}?graph={graph.id}"
    )
    assert code == 200
    payload = json.loads(body)
    assert payload["evidence"] == [binding.to_dict()]
    assert "does not settle" in payload["read"]["evidence_line"]
    js = (viz_dist_path() / "space.js").read_text(encoding="utf-8")
    assert "read.evidence_line" in js
    assert "supports this thought" not in js
    assert "contradicts this thought" not in js


def test_unknown_post_rejected(httpd_url: str):
    code, body = _post(httpd_url + "/api/sessions", {})
    assert code == 405


def test_fork_from_space_keeps_g0(httpd_url: str, tmp_path: Path):
    store_path = tmp_path / "data"
    st = Store(store_path)
    sessions = json.loads(_get(httpd_url + "/api/sessions")[1])
    spawn = sessions["sessions"][0]["spawn"]
    sid = sessions["sessions"][0]["id"]
    gid = spawn["graph_id"]
    graph = st.load_graph(gid)
    target = next(n for n in graph.nodes if n.kind == "judgment_call")
    before = (store_path / "sessions" / sid / "graphs" / f"{gid}.json").read_bytes()
    code, body = _post(
        httpd_url + "/api/fork",
        {
            "node": target.id,
            "graph": gid,
            "session": sid,
            "reason": "accept chain except this cut",
        },
    )
    assert code == 200, body
    payload = json.loads(body)
    assert payload["ok"] is True
    assert payload["op"] == "fork"
    assert payload["from_graph_id"] == gid
    assert payload["stand"]["graph_id"] == gid
    assert payload["stand"]["node_id"] == target.id
    assert payload["graph_id"] != gid
    after = (store_path / "sessions" / sid / "graphs" / f"{gid}.json").read_bytes()
    assert after == before
    g1 = st.load_graph(payload["graph_id"])
    assert target.id not in {n.id for n in g1.nodes}
    view = json.loads(
        _get(httpd_url + f"/api/inhabit/{target.id}?graph={gid}")[1]
    )
    child_ids = {f["id"] for f in view["fork_children"]}
    assert payload["graph_id"] in child_ids
    child = next(f for f in view["fork_children"] if f["id"] == payload["graph_id"])
    assert child["spawn_node_id"]
    assert "feature_ids" not in body


def test_veto_from_space_requires_reason_then_follows(httpd_url: str, tmp_path: Path):
    store_path = tmp_path / "data"
    sessions = json.loads(_get(httpd_url + "/api/sessions")[1])
    spawn = sessions["sessions"][0]["spawn"]
    sid = sessions["sessions"][0]["id"]
    gid = spawn["graph_id"]
    nid = spawn["node_id"]
    code, body = _post(
        httpd_url + "/api/veto",
        {"node": nid, "graph": gid, "session": sid},
    )
    assert code == 400
    assert "reason" in json.loads(body)["error"]
    code, body = _post(
        httpd_url + "/api/veto",
        {
            "node": nid,
            "graph": gid,
            "session": sid,
            "reason": "this judgment call is the wrong cut",
        },
    )
    assert code == 200, body
    payload = json.loads(body)
    assert payload["stand"]["graph_id"] == payload["graph_id"]
    assert payload["stand"]["node_id"] == nid
    view = json.loads(
        _get(
            httpd_url
            + f"/api/inhabit/{nid}?graph={payload['graph_id']}"
        )[1]
    )
    assert view["parent"]["graph_id"] == gid
    assert any(v["status"] == "vetoed" for v in view["vetoes"])
    g0 = Store(store_path).load_graph(gid)
    assert nid in {n.id for n in g0.nodes}


def test_space_shell_mentions_gestures(httpd_url: str):
    code, body, _ = _get(httpd_url + "/")
    assert code == 200
    assert "preview a path" in body
    assert "overhead" in body
    assert "shift+c home" in body
    assert "human no" in body
    assert 'id="topbar"' in body
    assert 'id="relic-index"' in body
    assert 'id="evidence-descent"' in body
    assert 'id="story-path"' in body
    assert "relic-loader.js" in body
    js = _get(httpd_url + "/space.js")[1]
    assert "/api/fork" in js
    assert "/api/veto" in js
    assert "omit_set" not in js
    assert "applyClimate" in js
    assert "model_judgments" not in js
    assert "ArrowUp" in js
    assert "CELL" in js
    assert "starTexture" in js
    assert "markRise" in js
    assert "trail" in js
    assert "selectFocus" in js
    assert "CHOICE_STRIDE" in js
    assert "overhead" in js
    assert "overheadLook" in js
    assert "overSun" in js
    assert "shiftKey" in js
    assert "--plate-height" in js
    assert "RelicGLBLoader.load" in js
    assert "EVIDENCE_RELIC" in js
    assert "openRelicIndex" in js
    assert "openEvidenceDescent" in js
    assert "read.story_path" in js
    assert "assets/previews" in js
    assert "selectionSpot" in js
    assert "standingMesh" in js
    assert "updateNavigationLights" in js
    css = _get(httpd_url + "/theme.css")[1]
    assert "calc(2.25rem + var(--plate-height" in css
    assert "grid-template-columns: max-content minmax(0, 1fr)" in css
    assert "cycleChoice" in js
    assert "inhabit(view.graph_id, cycle[" not in js

    code, loader, _ = _get(httpd_url + "/relic-loader.js")
    assert code == 200
    assert "MeshPhysicalMaterial" in loader
    code, model, ctype = _get_bytes(
        httpd_url + "/assets/models/narrated-claim.glb"
    )
    assert code == 200
    assert ctype == "model/gltf-binary"
    assert model.startswith(b"glTF")


def test_evidence_descent_is_a_static_server_authored_read_surface():
    dist = viz_dist_path()
    html = (dist / "index.html").read_text(encoding="utf-8")
    js = (dist / "space.js").read_text(encoding="utf-8")
    assert 'id="evidence-descent"' in html
    assert 'id="story-path"' in html
    assert "read.evidence_layers" in js
    assert "read.story_path" in js
    assert "group.heading_line" in js
    assert "entry.text" in js
    assert "layer.heading_line" in js
    assert "layer.summary" in js
    assert "supports this thought" not in js
    assert "contradicts this thought" not in js


def test_live_companion_uses_finalized_store_heads_as_optional_doorways(tmp_path: Path):
    store_path = tmp_path / "data"
    session_id, graph_id = _compile_simple(store_path)
    payload = bootstrap_payload(Store(store_path))
    session = next(item for item in payload["sessions"] if item["id"] == session_id)
    assert session["head_graph_id"] == graph_id
    assert session["spawn"]["graph_id"] == graph_id

    js = (viz_dist_path() / "space.js").read_text(encoding="utf-8")
    assert "knownHeads" in js
    assert "pollLiveCompanion" in js
    assert 'api("/api/sessions")' in js
    assert 'arrival.seen ? "recent thought" : "new thought"' in js
    assert '"recent thought"' in js
    assert "rememberCompanion" in js
    assert "window.localStorage" in js
    assert "COMPANION_MEMORY_KEY" in js
    assert 'relicKey: "thought-graph-reliquary"' in js
    assert "setInterval(pollLiveCompanion" in js
    assert "restart ta serve, then refresh" in js


def test_inhabit_climate_none_without_fingerprint(httpd_url: str):
    sessions = json.loads(_get(httpd_url + "/api/sessions")[1])
    spawn = sessions["sessions"][0]["spawn"]
    code, body, _ = _get(
        httpd_url + f"/api/inhabit/{spawn['node_id']}?graph={spawn['graph_id']}"
    )
    assert code == 200
    payload = json.loads(body)
    assert payload["climate"] is None


def test_serve_port_in_use(tmp_path: Path):
    store = Store(tmp_path / "data")
    store.init_session("t")
    first = make_server(store, port=0)
    _host, port = first.server_address[:2]
    try:
        with pytest.raises(ServeError, match="already in use"):
            make_server(store, port=port)
    finally:
        first.server_close()


def test_serve_refuses_non_localhost():
    with pytest.raises(ServeError, match="localhost"):
        make_server(Store("/tmp"), bind="0.0.0.0", port=0)


def test_cli_serve_bad_bind(tmp_path: Path):
    store = tmp_path / "data"
    run(["init", "--title", "t"], store=store)
    code, _, err = run(["serve", "--bind", "0.0.0.0"], store=store)
    assert code == 2
    assert "localhost" in err
