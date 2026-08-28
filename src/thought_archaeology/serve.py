from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from thought_archaeology.fork import ForkError
from thought_archaeology.inhabit import inhabit
from thought_archaeology.store import Store, StoreError

DEFAULT_PORT = 7462
DEFAULT_BIND = "127.0.0.1"


class ServeError(Exception):
    """Read-only HTTP adapter failure."""


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


def bootstrap_payload(store: Store) -> dict:
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
                claim = next((n for n in graph.nodes if n.kind == "claim"), graph.nodes[0])
                spawn = {
                    "graph_id": graph.id,
                    "node_id": claim.id,
                    "node": _node_brief(claim),
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
                self._json(200, {"ok": True, "write": False})
                return
            if path == "/api/sessions":
                self._json(200, bootstrap_payload(self.store))
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
                self._json(200, view.to_dict())
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

    def do_POST(self) -> None:  # noqa: N802
        self._json(405, {"error": "Inhabit Space v0 is read-only"})

    def do_PUT(self) -> None:  # noqa: N802
        self._json(405, {"error": "Inhabit Space v0 is read-only"})

    def do_DELETE(self) -> None:  # noqa: N802
        self._json(405, {"error": "Inhabit Space v0 is read-only"})

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
    return ThreadingHTTPServer((bind, port), Bound)


def serve_forever(
    store: Store,
    *,
    bind: str = DEFAULT_BIND,
    port: int = DEFAULT_PORT,
    dist: Path | None = None,
) -> None:
    httpd = make_server(store, bind=bind, port=port, dist=dist)
    print(f"Inhabit Space  http://{bind}:{port}/  (read-only, story graph)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()
