from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from thought_archaeology.edits import commit, plan_fork, plan_veto
from thought_archaeology.continuation import (
    continuation_cancellation,
    continuation_request,
)
from thought_archaeology.fork import ForkError
from thought_archaeology.inhabit import entry_node, inhabit
from thought_archaeology.schema import ValidationError
from thought_archaeology.store import Store, StoreError

DEFAULT_PORT = 7462
DEFAULT_BIND = "127.0.0.1"


class ServeError(Exception):
    """HTTP adapter failure."""


def viz_dist_path() -> Path:
    env = os.environ.get("TA_VIZ")
    if env:
        return Path(env).expanduser().resolve()
    here = Path(__file__).resolve()
    repo = here.parents[2] / "viz" / "dist"
    return repo


def _node_brief(node) -> dict:
    return {
        "id": node.id,
        "kind": node.kind,
        "text": node.text,
        "status": node.status,
    }


def _harness_by_graph(store: Store) -> dict[str, str]:
    return {
        completion.graph_id: completion.harness
        for completion in store.iter_continuation_completions()
    }


def _attempt_by_request(store: Store) -> dict[str, dict]:
    return {
        attempt.request_id: attempt.to_dict()
        for attempt in store.iter_continuation_attempts()
    }


def _continuation_source(store: Store, graph_id: str) -> dict | None:
    for completion in store.iter_continuation_completions():
        if completion.graph_id != graph_id:
            continue
        request = store.load_continuation_request(completion.request_id)
        graph = store.load_graph(request.graph_id)
        node = next(item for item in graph.nodes if item.id == request.node_id)
        session = store.load_session(request.session_id)
        return {
            "graph_id": request.graph_id,
            "node_id": request.node_id,
            "session_id": request.session_id,
            "title": session.title,
            "node": _node_brief(node),
            "model": graph.model.to_dict(),
            "prompt": request.prompt,
            "harness": completion.harness,
        }
    return None


def bootstrap_payload(store: Store) -> dict:
    harness_by_graph = _harness_by_graph(store)
    sessions = []
    for sid in store.iter_session_ids():
        session = store.load_session(sid)
        spawn = None
        if session.head_graph_id:
            try:
                graph = store.load_graph(session.head_graph_id)
            except StoreError:
                graph = None
            if graph is not None and graph.nodes:
                spawn_node = entry_node(graph)
                if spawn_node is None:
                    continue
                spawn = {
                    "graph_id": graph.id,
                    "node_id": spawn_node.id,
                    "node": _node_brief(spawn_node),
                    "model": graph.model.to_dict(),
                    "continuation_harness": harness_by_graph.get(graph.id),
                }
        sessions.append(
            {
                "id": session.id,
                "title": session.title,
                "head_graph_id": session.head_graph_id,
                "head_turn_id": session.head_turn_id,
                "spawn": spawn,
            }
        )
    return {"sessions": sessions}


class InhabitHandler(BaseHTTPRequestHandler):
    store: Store
    dist: Path

    def log_message(self, fmt: str, *args: object) -> None:
        if os.environ.get("TA_SERVE_LOG"):
            super().log_message(fmt, *args)

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj: object) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._send(code, body, "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        try:
            if path == "/api/health":
                self._json(200, {"ok": True, "write": True, "bind": "localhost"})
                return
            if path == "/api/sessions":
                self._json(200, bootstrap_payload(self.store))
                return
            if path == "/api/continuations":
                self._json(
                    200,
                    {
                        "requests": [
                            item.to_dict()
                            for item in self.store.iter_continuation_requests(
                                pending=True
                            )
                        ]
                    },
                )
                return
            if path.startswith("/api/graphs/"):
                gid = path[len("/api/graphs/") :].strip("/")
                graph = self.store.load_graph(gid)
                payload = graph.to_dict()
                payload.pop("hidden_reasoning", None)
                self._json(200, payload)
                return
            if path.startswith("/api/inhabit/"):
                nid = path[len("/api/inhabit/") :].strip("/")
                session = (qs.get("session") or [None])[0]
                graph_id = (qs.get("graph") or [None])[0]
                view = inhabit(
                    self.store, nid, graph_id=graph_id, session_id=session
                )
                payload = view.to_dict()
                payload["continuation_harness"] = _harness_by_graph(
                    self.store
                ).get(view.graph.id)
                payload["continuation_source"] = _continuation_source(
                    self.store, view.graph.id
                )
                if view.continuation:
                    payload["continuation_attempt"] = _attempt_by_request(
                        self.store
                    ).get(view.continuation["id"])
                else:
                    payload["continuation_attempt"] = None
                self._json(200, payload)
                return
            self._static(path)
        except ForkError as exc:
            self._json(404, {"error": str(exc)})
        except StoreError as exc:
            self._json(404, {"error": str(exc)})
        except FileNotFoundError as exc:
            self._json(404, {"error": str(exc)})
        except OSError as exc:
            self._json(500, {"error": str(exc)})

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length > 100_000:
            raise ServeError("payload too large")
        raw = self.rfile.read(length) if length else b"{}"
        if not raw:
            return {}
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ServeError("JSON object required")
        return data

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path == "/api/fork":
                self._edit_fork()
                return
            if path == "/api/veto":
                self._edit_veto()
                return
            if path == "/api/continuation":
                self._continuation_ready()
                return
            if path == "/api/continuation/cancel":
                self._continuation_cancel()
                return
            self._json(405, {"error": "unknown write"})
        except ServeError as exc:
            self._json(400, {"error": str(exc)})
        except ForkError as exc:
            self._json(404, {"error": str(exc)})
        except StoreError as exc:
            self._json(404, {"error": str(exc)})
        except ValidationError as exc:
            self._json(400, {"error": "; ".join(exc.messages)})
        except json.JSONDecodeError as exc:
            self._json(400, {"error": str(exc)})

    def _standing_args(self, body: dict) -> tuple[str, str | None, str]:
        node_id = body.get("node") or body.get("node_id")
        if not node_id:
            raise ServeError("node is required")
        graph_id = body.get("graph") or body.get("graph_id")
        session_id = body.get("session") or body.get("session_id")
        if not session_id and graph_id:
            session_id = self.store.load_graph(str(graph_id)).session_id
        if not session_id:
            raise ServeError("session is required")
        return str(node_id), (str(graph_id) if graph_id else None), str(session_id)

    def _edit_fork(self) -> None:
        body = self._read_json()
        node_id, graph_id, session_id = self._standing_args(body)
        reason = body.get("reason")
        reason_s = str(reason).strip() if reason else None
        plan = plan_fork(
            self.store,
            node_id,
            session_id=session_id,
            graph_id=graph_id,
            reason=reason_s or None,
        )
        commit(self.store, plan)
        # Stay in G0 at the cut. The continuation is a ring, not a teleport.
        self._json(
            200,
            {
                "ok": True,
                "op": "fork",
                "graph_id": plan.g1.id,
                "from_graph_id": plan.g0.id,
                "from_node_id": plan.node.id,
                "warnings": plan.warnings,
                "stand": {"graph_id": plan.g0.id, "node_id": plan.node.id},
            },
        )

    def _edit_veto(self) -> None:
        body = self._read_json()
        node_id, graph_id, session_id = self._standing_args(body)
        reason = body.get("reason")
        reason_s = str(reason).strip() if reason else ""
        if not reason_s:
            self._json(400, {"error": "veto requires a reason"})
            return
        plan = plan_veto(
            self.store,
            node_id,
            session_id=session_id,
            graph_id=graph_id,
            reason=reason_s,
        )
        commit(self.store, plan)
        # Follow into G1: the chamber remains, now with a human no.
        self._json(
            200,
            {
                "ok": True,
                "op": "veto",
                "graph_id": plan.g1.id,
                "from_graph_id": plan.g0.id,
                "from_node_id": plan.node.id,
                "warnings": plan.warnings,
                "stand": {"graph_id": plan.g1.id, "node_id": plan.node.id},
            },
        )

    def _continuation_ready(self) -> None:
        body = self._read_json()
        node_id, graph_id, _session_id = self._standing_args(body)
        if graph_id is None:
            raise ServeError("graph is required")
        view = inhabit(self.store, node_id, graph_id=graph_id)
        graph, node = view.graph, view.node
        prompt = str(body.get("prompt") or "").strip()
        request = continuation_request(
            graph, node, prompt=prompt, source="inhabit_space"
        )
        path = self.store.write_continuation_request(request)
        self.store.log(
            "continuation_ready",
            session_id=graph.session_id,
            graph_id=graph.id,
            node_id=node.id,
            request_id=request.id,
            path=str(path),
            warnings=[],
        )
        self._json(200, {"ok": True, "request": request.to_dict()})

    def _continuation_cancel(self) -> None:
        body = self._read_json()
        request_id = str(body.get("request") or body.get("request_id") or "").strip()
        if not request_id:
            raise ServeError("request is required")
        request = self.store.load_continuation_request(request_id)
        cancellation = continuation_cancellation(
            request.id, source="inhabit_space"
        )
        path = self.store.write_continuation_cancellation(cancellation)
        self.store.log(
            "continuation_cancel",
            session_id=request.session_id,
            graph_id=request.graph_id,
            node_id=request.node_id,
            request_id=request.id,
            cancellation_id=cancellation.id,
            path=str(path),
            warnings=[],
        )
        self._json(200, {"ok": True, "cancellation": cancellation.to_dict()})

    def do_PUT(self) -> None:  # noqa: N802
        self._json(405, {"error": "PUT is not a gesture"})

    def do_DELETE(self) -> None:  # noqa: N802
        self._json(405, {"error": "DELETE is not a gesture"})

    def _static(self, path: str) -> None:
        dist = self.dist.resolve()
        rel = path.lstrip("/") or "index.html"
        if rel.startswith("api/"):
            self._json(404, {"error": "not found"})
            return
        target = (dist / rel).resolve()
        if dist != target and dist not in target.parents:
            self._json(403, {"error": "forbidden"})
            return
        if target.is_dir():
            target = target / "index.html"
        if not target.is_file():
            index = dist / "index.html"
            if index.is_file() and "." not in Path(rel).name:
                target = index
            else:
                self._send(404, b"not found\n", "text/plain; charset=utf-8")
                return
        data = target.read_bytes()
        types = {
            ".html": "text/html; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".map": "application/json; charset=utf-8",
            ".svg": "image/svg+xml",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".glb": "model/gltf-binary",
            ".woff2": "font/woff2",
        }
        ctype = types.get(target.suffix, "application/octet-stream")
        self._send(200, data, ctype)


def make_server(
    store: Store,
    *,
    bind: str = DEFAULT_BIND,
    port: int = DEFAULT_PORT,
    dist: Path | None = None,
) -> ThreadingHTTPServer:
    if bind not in ("127.0.0.1", "localhost", "::1"):
        raise ServeError("ta serve binds localhost only")

    class Bound(InhabitHandler):
        pass

    Bound.store = store
    Bound.dist = dist or viz_dist_path()
    try:
        return ThreadingHTTPServer((bind, port), Bound)
    except OSError as exc:
        err = str(exc).lower()
        if "address already in use" in err or getattr(exc, "errno", None) == 98:
            raise ServeError(
                f"port {port} already in use — stop the other ta serve "
                f"(ss -ltnp | grep {port})"
            ) from exc
        raise ServeError(str(exc)) from exc


def serve_forever(
    store: Store,
    *,
    bind: str = DEFAULT_BIND,
    port: int = DEFAULT_PORT,
    dist: Path | None = None,
) -> None:
    httpd = make_server(store, bind=bind, port=port, dist=dist)
    print(
        f"Inhabit Space  http://{bind}:{port}/  "
        "(localhost · fork/veto/continuation from the chamber)"
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()
