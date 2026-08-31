from __future__ import annotations

import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from thought_archaeology.continuation import (
    continuation_attempt,
    continuation_completion,
    continuation_request,
)
from thought_archaeology.inhabit import inhabit
from thought_archaeology.serve import (
    InhabitHandler,
    ServeError,
    _continuation_source,
    bootstrap_payload,
    make_server,
    thread_payload,
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


def test_thread_compass_is_server_authored_generation_lineage(
    httpd_url: str, tmp_path: Path
):
    store = Store(tmp_path / "data")
    sessions = json.loads(_get(httpd_url + "/api/sessions")[1])
    session = sessions["sessions"][0]
    graph = store.load_graph(session["head_graph_id"])
    target = graph.nodes[0]
    code, body = _post(
        httpd_url + "/api/veto",
        {
            "node": target.id,
            "graph": graph.id,
            "session": session["id"],
            "reason": "keep this visible as a human no",
        },
    )
    assert code == 200, body
    child_id = json.loads(body)["graph_id"]

    code, body, ctype = _get(httpd_url + f"/api/thread/{session['id']}")
    assert code == 200
    assert ctype == "application/json"
    lineage = json.loads(body)
    assert lineage == thread_payload(store, session["id"])
    assert lineage["head_graph_id"] == child_id
    assert lineage["latest_ai_graph_id"] is None
    assert [entry["kind"] for entry in lineage["entries"]] == ["origin", "veto"]
    assert lineage["entries"][1]["depth"] == 1
    assert lineage["entries"][1]["label"] == "human no"
    assert lineage["entries"][1]["reason"] == "keep this visible as a human no"
    assert lineage["entries"][1]["node_id"]
    assert "hidden_reasoning" not in body


def test_thread_compass_and_legend_controls_are_chamber_overlays():
    dist = viz_dist_path()
    html = (dist / "index.html").read_text(encoding="utf-8")
    css = (dist / "theme.css").read_text(encoding="utf-8")
    js = (dist / "space.js").read_text(encoding="utf-8")

    assert 'id="legend-trigger"' in html
    assert "press L for Legend and controls" in html
    assert 'id="banner"' not in html
    assert 'id="help"' not in html
    assert 'id="legend-menu"' in html
    assert html.index('id="legend-menu"') < html.index('id="sound-controls"')
    assert html.index('id="threshold"') < html.index('id="legend-menu"')
    assert html.index('id="legend-menu"') < html.index('id="composer"')
    assert "Blue ring" in html and "new AI path" in html
    assert "Red ring" in html and "return to conversation origin" in html
    assert "Green beam" in html and "AI request in flight" in html
    assert "Blue beam" in html and "completed path waiting for entry" in html

    assert 'id="thread-compass"' in html
    assert "Thread Compass" in html
    assert "backdrop-filter: blur(10px)" in css
    assert ".thread-panel" in css
    assert ".thread-entry.current" in css
    assert 'api(`/api/thread/${view.session_id}`)' in js
    assert "openThreadCompass" in js
    assert 'e.key === "t"' in js
    assert "openLegendMenu" in js
    assert 'e.key === "l"' in js
    assert 'if (kind !== "continuation" && elLegendMenu.hidden)' in js


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
    assert payload["model"] == view.graph.model.to_dict()
    assert payload["continuation_harness"] is None
    assert payload["continuation_source"] is None
    assert payload["node"]["id"] == view.node.id
    assert payload["origin"]["id"]
    assert payload["forward"] == [
        {"id": n.id, "kind": n.kind, "text": n.text, "status": n.status, "agent": n.agent}
        for n in view.forward
    ]
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
    assert "counterclockwise" in body
    assert "cycle counterclockwise / clockwise" in body
    assert "walk the selected / north path" in body
    assert "overhead" in body
    assert "overhead view / camera home" in body
    assert "human no" in body
    assert "mute or wake chamber sound" in body
    assert 'id="topbar"' in body
    assert 'id="legend-menu"' in body
    assert 'id="thread-compass"' in body
    assert 'id="sound-controls"' in body
    assert 'id="sound-toggle"' in body
    assert 'id="sound-volume"' in body
    assert 'id="sound-volume-value"' in body
    assert 'id="relic-index"' in body
    assert 'id="evidence-descent"' in body
    assert 'id="story-path"' in body
    assert "relic-loader.js" in body
    assert "sound.js" in body
    js = _get(httpd_url + "/space.js")[1]
    assert "/api/fork" in js
    assert "/api/veto" in js
    assert "omit_set" not in js
    assert "applyClimate" in js
    assert "model_judgments" not in js
    assert "ArrowUp" in js
    assert "CELL" in js
    assert "makeNeuralSky" in js
    assert "updateNeuralSky" in js
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
    assert "payload.forward" in js
    assert "conversation doors wait at the graph origin or a path ending" in js
    assert 'post(endpoint' in js
    assert '"/api/continuation"' in js
    assert 'id="threshold"' in body
    css = _get(httpd_url + "/theme.css")[1]
    assert "width: min(31rem, 92vw)" in css
    assert "grid-template-columns: 6.4rem minmax(0, 1fr)" in css
    assert "cycleChoice" in js
    assert "if (focusIndex < 0)" in js
    assert "walkDeeper();" in js
    assert "clockwiseChoices" in js
    assert "Math.atan2(position.x, -position.z)" in js
    assert js.count("addClockChoice(") == 6
    assert "sparkColors" in js
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

    code, audio, ctype = _get_bytes(
        httpd_url + "/assets/audio/neural-atmosphere-loop.ogg"
    )
    assert code == 200
    assert ctype == "audio/ogg"
    assert audio.startswith(b"OggS")


def test_space_sound_field_uses_cinematic_pack_and_is_event_bound():
    dist = viz_dist_path()
    html = (dist / "index.html").read_text(encoding="utf-8")
    js = (dist / "space.js").read_text(encoding="utf-8")
    sound = (dist / "sound.js").read_text(encoding="utf-8")
    audio = dist / "assets" / "audio"
    expected = {
        "ai-working-loop.ogg",
        "blue-new-path-activate.ogg",
        "blue-new-path-enter.ogg",
        "blue-path-complete-splash.ogg",
        "camera-cycle-transition.ogg",
        "green-beam-activate.ogg",
        "green-beam-sparks-loop.ogg",
        "neural-atmosphere-loop.ogg",
        "object-cycle.ogg",
        "red-return-activate.ogg",
        "traversal-back.ogg",
        "traversal-forward.ogg",
    }
    assert '<script src="./sound.js"></script>' in html
    assert "AudioContext" in sound
    assert "decodeAudioData" in sound
    assert "window.fetch(AUDIO_ROOT + item.file)" in sound
    assert "startLoop(\"atmosphere\"" in sound
    assert "startLoop(\"working\"" in sound
    assert "startLoop(\"greenSparks\"" in sound
    assert "stopLoop(\"working\"" in sound
    assert "stopLoop(\"greenSparks\"" in sound
    assert "pendingCues" in sound
    assert "createOscillator" in sound
    assert "createBuffer" in sound
    assert "new Audio(" not in sound
    assert ".mp3" not in sound
    assert ".wav" not in sound
    assert "audibleLevel" in sound
    assert "setVolumeFromPointer" in sound
    assert 'volume.addEventListener("keydown"' in sound
    assert "arrivalSplash" in sound
    assert "cameraShift" in sound
    assert 'gain: 0.253125, submerged: true' in sound
    assert 'gain: 0.32625, submerged: true' in sound
    assert 'red-return-activate.ogg", gain: 0.3375, submerged: true' in sound
    assert sound.count("submerged: true") == 5
    assert "function connectSubmerged" in sound
    assert 'lowpass.frequency.value = 420' in sound
    assert 'firstDelay.delayTime.value = 0.24' in sound
    assert 'secondDelay.delayTime.value = 0.48' in sound
    assert {path.name for path in audio.glob("*.ogg")} == expected
    for name in expected:
        assert (audio / name).read_bytes().startswith(b"OggS")
    assert "sound.cycle" in js
    assert "sound.traverse" in js
    assert 'sound.setBeam("waiting"' in js
    assert 'sound.setBeam("arrival")' in js
    assert "sound.arrivalSplash()" in js
    assert "sound.setWorking(Boolean(ready))" in js
    assert "sound.cameraShift(overhead)" in js
    assert "sound.edit(kind)" in js
    assert "if (!elLegendMenu.hidden)" in js


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


def test_terminal_traversal_separates_story_and_conversation_routes():
    dist = viz_dist_path()
    html = (dist / "index.html").read_text(encoding="utf-8")
    js = (dist / "space.js").read_text(encoding="utf-8")
    css = (dist / "theme.css").read_text(encoding="utf-8")
    assert 'id="threshold"' in html
    assert 'id="threshold-origin"' in html
    assert 'id="threshold-continue"' in html
    assert 'id="threshold-ask"' in html
    assert 'id="threshold-ask-box"' in html
    assert 'id="threshold-ask-input"' in html
    assert "payload.forward" in js
    assert 'via: "story ahead"' in js
    assert "atThreshold" in js
    assert 'sideSlot(i, sideNodes.length, -1)' in js
    assert "arrivalSlot(i)" in js
    assert '"conversation return"' in js
    assert "renderThreshold" in js
    assert "walkOrigin" in js
    assert "markContinuationReady" in js
    assert "cancelContinuationReady" in js
    assert 'post("/api/continuation/cancel"' in js
    assert 'elThresholdContinue.addEventListener("click", toggleContinuationReady)' in js
    assert 'elThresholdAsk.addEventListener("click", toggleContinuationComposer)' in js
    assert 'elThreshold.dataset.ask = "true"' in js
    assert 'elThreshold.dataset.ask = "false"' in js
    assert "#threshold-ask-box" in css
    assert "width: min(32rem, calc(50vw - 1.875rem))" in css
    assert "bottom: calc(2.25rem + var(--plate-height, 9rem))" in css
    assert "#legend-menu" in css
    assert "#thread-compass" in css
    assert "marking inhabitant ready" in js
    assert 'elThreshold.dataset.ready = ready ? "working" : "false"' in js
    assert '"AI working…"' in js
    assert "continuation_attempt" in js
    assert "is responding from this chamber" in js
    assert '"cancel response · q"' in js
    assert '#threshold[data-ready="working"]' in css
    assert "working-text" in css
    assert 'openComposer("continuation")' in js
    assert "#threshold" in css


def test_live_companion_uses_finalized_store_heads_as_optional_doorways(tmp_path: Path):
    store_path = tmp_path / "data"
    session_id, graph_id = _compile_simple(store_path)
    store = Store(store_path)
    payload = bootstrap_payload(store)
    session = next(item for item in payload["sessions"] if item["id"] == session_id)
    assert session["head_graph_id"] == graph_id
    assert session["spawn"]["graph_id"] == graph_id
    assert session["spawn"]["model"]["name"] == "unknown"
    assert session["spawn"]["continuation_harness"] is None

    source = store.load_graph(graph_id)
    request = continuation_request(source, source.nodes[0], source="inhabit_space")
    store.write_continuation_request(request)
    answer_session_id, answer_graph_id = _compile_simple(store_path)
    store.write_continuation_completion(
        continuation_completion(request.id, answer_graph_id, "grok")
    )
    payload = bootstrap_payload(store)
    answer = next(
        item for item in payload["sessions"] if item["id"] == answer_session_id
    )
    assert answer["spawn"]["continuation_harness"] == "grok"
    source_payload = _continuation_source(store, answer_graph_id)
    assert source_payload is not None
    assert source_payload["graph_id"] == graph_id
    assert source_payload["node_id"] == source.nodes[0].id
    assert source_payload["prompt"] == ""
    assert source_payload["harness"] == "grok"

    dist = viz_dist_path()
    html = (dist / "index.html").read_text(encoding="utf-8")
    js = (dist / "space.js").read_text(encoding="utf-8")
    assert "knownHeads" in js
    assert "pollLiveCompanion" in js
    assert 'api("/api/sessions")' in js
    assert '"conversation return"' in js
    assert '"new companion thought"' in js
    assert '"conversation return"' in js
    assert "rememberCompanion" in js
    assert "companionFromSession" in js
    assert "companionAttribution" in js
    assert "graphAttribution" in js
    assert "inside the ${attribution} graph" in js
    assert "visibleArrivals" in js
    assert "continuationSourceArrival" in js
    assert "arrival.anchorGraphId === payload.graph_id" in js
    assert "arrival.graphId !== source.graphId || arrival.nodeId !== source.nodeId" in js
    assert 'text: "Return to conversation origin"' in js
    assert 'labelKind: "conversation origin"' in js
    assert 'relicKey: arrival.returnOrigin' in js
    assert "RETURN_COLOR" in js
    assert "NEW_PATH_SELECTION_COLOR" in js
    assert "choice.selectionColor || DEFAULT_SELECTION_COLOR" in js
    assert "WAITING_BEAM_COLOR" in js
    assert "visibleNeuronIndex" in js
    assert "neuronAtOrAboveMesh" in js
    assert "world.y < minimumY" in js
    assert "visibleNeuronIndex(standingMesh)" in js
    assert "makeContinuationLightning" in js
    assert "beginContinuationCircuit(ready)" in js
    assert "completeContinuationCircuit(ring, arrival)" in js
    assert 'continuationCircuit.phase = "arrival"' in js
    completed_circuit = js[
        js.index("function completeContinuationCircuit") :
        js.index("function restoreArrivalCircuit")
    ]
    assert "visibleNeuronIndex" not in completed_circuit
    assert "neuronIndex: continuationCircuit.neuronIndex" in completed_circuit
    assert "CIRCUIT_MEMORY_KEY" in js
    assert "window.localStorage" in js
    assert "restoreArrivalCircuit(ring, arrival)" in js
    assert "clearContinuationCircuit();" in js
    assert "updateContinuationCircuit(t)" in js
    assert '<canvas id="c"></canvas>' in html
    assert 'tabindex="0"' not in html
    assert 'window.addEventListener("pointercancel", stopDragging)' in js
    assert 'window.addEventListener("blur", stopDragging)' in js
    assert "revealWaitingArrivals" in js
    reveal = js[
        js.index("async function revealWaitingArrivals") :
        js.index("async function refreshContinuationState")
    ]
    assert "addArrivalPortal(arrival, i)" in reveal
    assert "layout(" not in reveal
    assert "clearRoot" not in reveal
    assert "refreshContinuationState" in js
    refresh = js[js.index("async function refreshContinuationState") : js.index("async function pollLiveCompanion")]
    assert "renderThreshold(payload)" in refresh
    assert "layout(payload)" not in refresh
    assert "arrivingFocus" in js
    assert "choice.autoFocus" in js
    waiting = js[js.index("function showWaitingArrivals") : js.index("async function pollLiveCompanion")]
    assert "focusIndex >= 0" not in waiting
    assert "revealWaitingArrivals()" in waiting
    assert "item.anchorGraphId === arrival.anchorGraphId" in js
    assert "currentSession.head_graph_id !== view.graph_id" in js
    assert "new companion thought · ${attribution}" in js
    assert "window.localStorage" in js
    assert "COMPANION_MEMORY_KEY" in js
    assert '"counterfactual-shard-gate"' in js
    assert '"thought-graph-reliquary"' in js
    assert "setInterval(pollLiveCompanion" in js
    assert "restart ta serve, then refresh" in js


def test_continuation_endpoint_writes_harness_neutral_request(
    httpd_url: str, tmp_path: Path
):
    store_path = tmp_path / "data"
    sessions = json.loads(_get(httpd_url + "/api/sessions")[1])
    spawn = sessions["sessions"][0]["spawn"]
    code, body = _post(
        httpd_url + "/api/continuation",
        {
            "node": spawn["node_id"],
            "graph": spawn["graph_id"],
            "session": sessions["sessions"][0]["id"],
            "prompt": "Continue from here.",
        },
    )
    assert code == 200, body
    request = json.loads(body)["request"]
    assert request["source"] == "inhabit_space"
    assert request["prompt"] == "Continue from here."
    assert Store(store_path).load_continuation_request(request["id"]).to_dict() == request

    code, body, _ = _get(httpd_url + "/api/continuations")
    assert code == 200
    assert json.loads(body)["requests"] == [request]
    code, body, _ = _get(
        httpd_url
        + f"/api/inhabit/{spawn['node_id']}?graph={spawn['graph_id']}"
    )
    assert code == 200
    assert json.loads(body)["continuation"] == request
    assert json.loads(body)["continuation_attempt"] is None

    attempt = continuation_attempt(request["id"], "grok")
    Store(store_path).write_continuation_attempt(attempt)
    code, body, _ = _get(
        httpd_url
        + f"/api/inhabit/{spawn['node_id']}?graph={spawn['graph_id']}"
    )
    assert code == 200
    assert json.loads(body)["continuation_attempt"] == attempt.to_dict()

    code, body = _post(
        httpd_url + "/api/continuation/cancel", {"request": request["id"]}
    )
    assert code == 200, body
    cancellation = json.loads(body)["cancellation"]
    assert cancellation["request_id"] == request["id"]
    code, body, _ = _get(httpd_url + "/api/continuations")
    assert code == 200
    assert json.loads(body)["requests"] == []
    code, body, _ = _get(
        httpd_url
        + f"/api/inhabit/{spawn['node_id']}?graph={spawn['graph_id']}"
    )
    assert code == 200
    assert json.loads(body)["continuation"] is None


def test_continuation_handler_without_socket(tmp_path: Path):
    store_path = tmp_path / "data"
    session_id, graph_id = _compile_simple(store_path)
    store = Store(store_path)
    graph = store.load_graph(graph_id)
    node = graph.nodes[0]
    replies = []
    handler = object.__new__(InhabitHandler)
    handler.store = store
    handler._read_json = lambda: {
        "node": node.id,
        "graph": graph.id,
        "session": session_id,
        "prompt": "Continue from this ending.",
    }
    handler._json = lambda code, body: replies.append((code, body))
    handler._continuation_ready()
    assert replies[-1][0] == 200
    request = replies[-1][1]["request"]
    assert request["prompt"] == "Continue from this ending."

    handler.path = "/api/continuations"
    handler.do_GET()
    assert replies[-1] == (200, {"requests": [request]})

    attempt = continuation_attempt(request["id"], "grok")
    store.write_continuation_attempt(attempt)
    handler.path = f"/api/inhabit/{node.id}?graph={graph.id}"
    handler.do_GET()
    assert replies[-1][0] == 200
    assert replies[-1][1]["continuation_attempt"] == attempt.to_dict()

    handler._read_json = lambda: {"request": request["id"]}
    handler._continuation_cancel()
    assert replies[-1][0] == 200
    cancellation = replies[-1][1]["cancellation"]
    assert cancellation["request_id"] == request["id"]
    assert cancellation["source"] == "inhabit_space"

    handler.path = "/api/continuations"
    handler.do_GET()
    assert replies[-1] == (200, {"requests": []})


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
