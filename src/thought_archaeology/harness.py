from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Self

from thought_archaeology.compile_common import CompileError
from thought_archaeology.compile_structured import compile_structured
from thought_archaeology.continuation import (
    ContinuationFailureReason,
    ContinuationRequest,
    continuation_attempt,
    continuation_completion,
    continuation_failure,
)
from thought_archaeology.ids import new_ulid, now_iso
from thought_archaeology.inhabit import inhabit
from thought_archaeology.models import ModelInfo, SCHEMA_VERSION, ThoughtGraph, Turn
from thought_archaeology.schema import ValidationError, validate_graph
from thought_archaeology.store import Store

HARNESS_CONFIG_VERSION = 1
HARNESS_PROTOCOL_VERSION = "1"
HARNESS_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class HarnessError(Exception):
    """Harness configuration, protocol, or adapter failure."""


def resolve_harness_config_path() -> Path:
    override = os.environ.get("TA_HARNESS_CONFIG")
    if override:
        return Path(override).expanduser().resolve()
    xdg = os.environ.get("XDG_CONFIG_HOME")
    app_data = os.environ.get("APPDATA")
    if sys.platform == "win32" and app_data:
        return (
            Path(app_data)
            / "MelaBuilt AI"
            / "Atlas of Threads"
            / "harnesses.json"
        ).resolve()
    root = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    return (root / "thought-archaeology" / "harnesses.json").resolve()


@dataclass(frozen=True)
class HarnessSpec:
    name: str
    argv: tuple[str, ...]
    registered_at: str
    model: str | None = None
    model_refreshed_at: str | None = None
    cli_version: str | None = None

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> Self:
        argv = data.get("argv")
        if not isinstance(argv, list) or not argv or not all(
            isinstance(item, str) and item for item in argv
        ):
            raise HarnessError(f"harness {name!r} has invalid argv")
        registered_at = data.get("registered_at")
        if not isinstance(registered_at, str) or not registered_at:
            raise HarnessError(f"harness {name!r} has invalid registered_at")
        optional = {
            key: data.get(key)
            for key in ("model", "model_refreshed_at", "cli_version")
        }
        if any(
            value is not None and not isinstance(value, str)
            for value in optional.values()
        ):
            raise HarnessError(f"harness {name!r} has invalid model metadata")
        return cls(
            name=name,
            argv=tuple(argv),
            registered_at=registered_at,
            **optional,
        )

    def to_dict(self) -> dict[str, Any]:
        data = {"argv": list(self.argv), "registered_at": self.registered_at}
        if self.model is not None:
            data["model"] = self.model
        if self.model_refreshed_at is not None:
            data["model_refreshed_at"] = self.model_refreshed_at
        if self.cli_version is not None:
            data["cli_version"] = self.cli_version
        return data


class HarnessRegistry:
    """User-owned adapter registry. It contains executable argv, never secrets."""

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path).expanduser().resolve() if path else resolve_harness_config_path()

    def _load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {"version": HARNESS_CONFIG_VERSION, "default": None, "harnesses": {}}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise HarnessError(f"cannot read harness config {self.path}: {exc}") from exc
        if not isinstance(raw, dict) or raw.get("version") != HARNESS_CONFIG_VERSION:
            raise HarnessError(
                f"unsupported harness config version in {self.path} "
                f"(want {HARNESS_CONFIG_VERSION})"
            )
        harnesses = raw.get("harnesses")
        if not isinstance(harnesses, dict):
            raise HarnessError(f"harness config {self.path} has invalid harnesses")
        default = raw.get("default")
        if default is not None and (
            not isinstance(default, str) or default not in harnesses
        ):
            raise HarnessError(f"harness config {self.path} has invalid default")
        for name, data in harnesses.items():
            if not isinstance(name, str) or not HARNESS_NAME.fullmatch(name):
                raise HarnessError(f"harness config contains invalid name {name!r}")
            if not isinstance(data, dict):
                raise HarnessError(f"harness {name!r} has invalid configuration")
            HarnessSpec.from_dict(name, data)
        return raw

    def _save(self, raw: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(self.path.parent, 0o700)
        fd, temp_name = tempfile.mkstemp(
            prefix=".harnesses-", suffix=".json", dir=self.path.parent
        )
        temp = Path(temp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(raw, fh, indent=2, ensure_ascii=False)
                fh.write("\n")
            os.chmod(temp, 0o600)
            os.replace(temp, self.path)
            os.chmod(self.path, 0o600)
        finally:
            if temp.exists():
                temp.unlink()

    def register(
        self,
        name: str,
        adapter: str,
        *,
        args: tuple[str, ...] = (),
        make_default: bool = False,
    ) -> HarnessSpec:
        if not HARNESS_NAME.fullmatch(name):
            raise HarnessError(
                "harness name must start with a letter or digit and contain only "
                "letters, digits, dot, underscore, or hyphen"
            )
        executable = shutil.which(adapter)
        if executable is None:
            candidate = Path(adapter).expanduser()
            if candidate.is_file() and os.access(candidate, os.X_OK):
                executable = str(candidate.resolve())
        if executable is None:
            raise HarnessError(f"adapter executable not found or not executable: {adapter}")
        spec = HarnessSpec(
            name=name,
            # Keep an absolute executable path without dereferencing symlinks.
            # A venv's python symlink must retain its venv location to activate
            # that environment when the adapter is launched.
            argv=(str(Path(executable).absolute()), *args),
            registered_at=now_iso(),
        )
        raw = self._load()
        harnesses = dict(raw["harnesses"])
        if name in harnesses:
            raise HarnessError(f"harness {name!r} is already registered")
        harnesses[name] = spec.to_dict()
        raw["harnesses"] = harnesses
        if make_default or raw.get("default") is None:
            raw["default"] = name
        self._save(raw)
        return spec

    def remove(self, name: str) -> None:
        raw = self._load()
        harnesses = dict(raw["harnesses"])
        if name not in harnesses:
            raise HarnessError(f"harness {name!r} is not registered")
        del harnesses[name]
        raw["harnesses"] = harnesses
        if raw.get("default") == name:
            raw["default"] = sorted(harnesses)[0] if harnesses else None
        self._save(raw)

    def use(self, name: str) -> HarnessSpec:
        raw = self._load()
        if name not in raw["harnesses"]:
            raise HarnessError(f"harness {name!r} is not registered")
        raw["default"] = name
        self._save(raw)
        return HarnessSpec.from_dict(name, raw["harnesses"][name])

    def record_model(
        self, name: str, model: str, *, cli_version: str | None = None
    ) -> HarnessSpec:
        model = model.strip()
        if not model:
            raise HarnessError(f"harness {name!r} returned an empty default_model")
        raw = self._load()
        if name not in raw["harnesses"]:
            raise HarnessError(f"harness {name!r} is not registered")
        data = dict(raw["harnesses"][name])
        data["model"] = model
        data["model_refreshed_at"] = now_iso()
        if cli_version:
            data["cli_version"] = cli_version.strip()
        raw["harnesses"] = {**raw["harnesses"], name: data}
        self._save(raw)
        return HarnessSpec.from_dict(name, data)

    def specs(self) -> tuple[HarnessSpec, ...]:
        raw = self._load()
        return tuple(
            HarnessSpec.from_dict(name, raw["harnesses"][name])
            for name in sorted(raw["harnesses"])
        )

    def default_name(self) -> str | None:
        return self._load().get("default")

    def get(self, name: str | None = None) -> HarnessSpec:
        raw = self._load()
        selected = name or raw.get("default")
        if not selected:
            raise HarnessError(
                "no default harness is configured; run 'ta harness register' first"
            )
        data = raw["harnesses"].get(selected)
        if data is None:
            raise HarnessError(f"harness {selected!r} is not registered")
        return HarnessSpec.from_dict(selected, data)


def _adapter_call(
    spec: HarnessSpec,
    operation: str,
    payload: dict[str, Any] | None,
    *,
    timeout: float,
) -> dict[str, Any]:
    if timeout <= 0:
        raise HarnessError("adapter timeout must be greater than zero")
    try:
        proc = subprocess.run(
            [*spec.argv, operation],
            input=(json.dumps(payload, ensure_ascii=False) + "\n") if payload else None,
            capture_output=True,
            text=True,
            shell=False,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise HarnessError(
            f"harness {spec.name!r} timed out during {operation} after {timeout:g}s"
        ) from exc
    except OSError as exc:
        raise HarnessError(f"cannot run harness {spec.name!r}: {exc}") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip() or "no output"
        raise HarnessError(
            f"harness {spec.name!r} exited {proc.returncode} during {operation}: {detail}"
        )
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise HarnessError(
            f"harness {spec.name!r} returned invalid JSON during {operation}: {exc}"
        ) from exc
    if not isinstance(result, dict):
        raise HarnessError(
            f"harness {spec.name!r} must return a JSON object during {operation}"
        )
    if result.get("protocol_version") != HARNESS_PROTOCOL_VERSION:
        raise HarnessError(
            f"harness {spec.name!r} protocol mismatch "
            f"(got {result.get('protocol_version')!r}, want {HARNESS_PROTOCOL_VERSION!r})"
        )
    return result


def describe_harness(spec: HarnessSpec, *, timeout: float = 10) -> dict[str, Any]:
    result = _adapter_call(spec, "describe", None, timeout=timeout)
    capabilities = result.get("capabilities")
    if not isinstance(capabilities, list) or "continue" not in capabilities:
        raise HarnessError(
            f"harness {spec.name!r} does not advertise the 'continue' capability"
        )
    return result


def continuation_envelope(store: Store, request: ContinuationRequest) -> dict[str, Any]:
    graph = store.load_graph(request.graph_id)
    session = store.load_session(request.session_id)
    public_graph = graph.to_dict()
    public_graph.pop("hidden_reasoning", None)
    standing = inhabit(store, request.node_id, graph_id=request.graph_id).to_dict()
    return {
        "protocol_version": HARNESS_PROTOCOL_VERSION,
        "operation": "continue",
        "request": request.to_dict(),
        "session": session.to_dict(),
        "graph": public_graph,
        "standing": standing,
        "response_contract": {
            "protocol_version": HARNESS_PROTOCOL_VERSION,
            "response": (
                "final prose followed by exactly one fenced thought-graph JSON block"
            ),
            "model_name": "non-empty model or harness model identifier",
        },
    }


def _is_pending(store: Store, request_id: str) -> bool:
    return any(
        request.id == request_id
        for request in store.iter_continuation_requests(pending=True)
    )


def _select_request(
    store: Store, request_id: str | None = None
) -> ContinuationRequest | None:
    pending = list(store.iter_continuation_requests(pending=True))
    if request_id is None:
        return pending[0] if pending else None
    for request in pending:
        if request.id == request_id:
            return request
    store.load_continuation_request(request_id)
    raise HarnessError(f"continuation request {request_id} is not pending")


def _continuation_turns(
    store: Store,
    request: ContinuationRequest,
    graph: ThoughtGraph,
    *,
    created_at: str,
) -> tuple[Turn, ...]:
    existing = list(store.iter_turns(request.session_id))
    seq = len(existing)
    parent_turn_id = store.load_graph(request.graph_id).turn_id
    turns: list[Turn] = []
    if request.prompt and request.source != "workspace":
        prompt_turn = Turn(
            schema_version=SCHEMA_VERSION,
            id=new_ulid(),
            session_id=request.session_id,
            seq=seq,
            role="user",
            created_at=request.created_at,
            prose=request.prompt,
            graph_id=None,
            parent_turn_id=parent_turn_id,
            fork_of_node_id=None,
            provider=None,
        )
        turns.append(prompt_turn)
        seq += 1
        parent_turn_id = prompt_turn.id
    turns.append(
        Turn(
            schema_version=SCHEMA_VERSION,
            id=graph.turn_id,
            session_id=request.session_id,
            seq=seq,
            role="assistant",
            created_at=created_at,
            prose=graph.prose,
            graph_id=graph.id,
            parent_turn_id=parent_turn_id,
            fork_of_node_id=None,
            provider="shell",
        )
    )
    return tuple(turns)


def _failure_details(
    exc: BaseException,
) -> tuple[ContinuationFailureReason, str]:
    detail = str(exc).lower()
    if isinstance(exc.__cause__, subprocess.TimeoutExpired) or "timed out" in detail:
        return (
            "timeout",
            "The collaborator timed out before returning a usable continuation.",
        )
    if (
        "invalid json" in detail
        or "must return a json object" in detail
        or "protocol mismatch" in detail
    ):
        return (
            "invalid_response",
            "The collaborator returned a response that could not be compiled.",
        )
    if any(
        marker in detail
        for marker in (
            "not authenticated",
            "authentication",
            "sign in",
            "sign-in",
            "login",
            "unauthorized",
        )
    ):
        return (
            "adapter_error",
            "The collaborator needs sign-in in the same CLI environment shown in Workspace.",
        )
    if any(
        marker in detail
        for marker in (
            "unknown argument",
            "unexpected argument",
            "unrecognized argument",
            "unknown option",
            "unrecognized option",
        )
    ):
        return (
            "adapter_error",
            "The installed collaborator CLI rejected the request options. Update it, then retry.",
        )
    if "model" in detail and any(
        marker in detail for marker in ("not found", "unavailable", "access")
    ):
        return (
            "adapter_error",
            "The selected collaborator model is unavailable for this account.",
        )
    return "adapter_error", "The collaborator could not complete this continuation."


def _record_failure(
    store: Store,
    request: ContinuationRequest,
    harness: str,
    reason: ContinuationFailureReason,
    summary: str,
) -> dict[str, Any]:
    failure = continuation_failure(request.id, harness, reason, summary)
    with store.continuation_inbox_lock():
        if not _is_pending(store, request.id):
            return {
                "status": "canceled",
                "harness": harness,
                "request_id": request.id,
            }
        store.write_continuation_failure(failure)
    store.log(
        "harness_failure",
        session_id=request.session_id,
        graph_id=request.graph_id,
        request_id=request.id,
        failure_id=failure.id,
        harness=harness,
        reason_code=reason,
        warnings=[],
    )
    return {
        "status": "failed",
        "harness": harness,
        "request_id": request.id,
        "failure_id": failure.id,
        "reason_code": reason,
    }


def process_continuation(
    store: Store,
    spec: HarnessSpec,
    *,
    request_id: str | None = None,
    timeout: float = 900,
    registry: HarnessRegistry | None = None,
) -> dict[str, Any] | None:
    with store.continuation_inbox_lock():
        request = _select_request(store, request_id)
        if request is None:
            return None
        prior = [
            item
            for item in store.iter_continuation_attempts()
            if item.request_id == request.id
        ]
        if prior:
            interrupted_harness = request.requested_harness or prior[-1].harness
            failure = continuation_failure(
                request.id,
                interrupted_harness,
                "interrupted",
                "The watcher restarted after this job began; it was not invoked again.",
            )
            store.write_continuation_failure(failure)
            return {
                "status": "failed",
                "harness": interrupted_harness,
                "request_id": request.id,
                "failure_id": failure.id,
                "reason_code": failure.reason_code,
            }
        target_spec = spec
        if request.requested_harness:
            if request.parallel_batch_id is None:
                raise HarnessError("routed continuation request has no parallel batch")
            try:
                target_spec = (registry or HarnessRegistry()).get(
                    request.requested_harness
                )
            except HarnessError:
                failure = continuation_failure(
                    request.id,
                    request.requested_harness,
                    "unavailable_harness",
                    "The requested collaborator is no longer registered.",
                )
                store.write_continuation_failure(failure)
                return {
                    "status": "failed",
                    "harness": request.requested_harness,
                    "request_id": request.id,
                    "failure_id": failure.id,
                    "reason_code": failure.reason_code,
                }
        attempt = continuation_attempt(request.id, target_spec.name)
        store.write_continuation_attempt(attempt)
    store.log(
        "harness_responding",
        session_id=request.session_id,
        graph_id=request.graph_id,
        request_id=request.id,
        attempt_id=attempt.id,
        harness=target_spec.name,
        warnings=[],
    )
    try:
        result = _adapter_call(
            target_spec,
            "continue",
            continuation_envelope(store, request),
            timeout=timeout,
        )
    except HarnessError as exc:
        reason, summary = _failure_details(exc)
        return _record_failure(
            store, request, target_spec.name, reason, summary
        )
    if not _is_pending(store, request.id):
        if request.parallel_batch_id is not None:
            return {
                "status": "canceled",
                "harness": target_spec.name,
                "request_id": request.id,
            }
        raise HarnessError(
            f"continuation request {request.id} closed while {target_spec.name!r} was responding; "
            "the response was discarded"
        )
    try:
        response = result.get("response")
        model_name = result.get("model_name")
        if not isinstance(response, str) or not response.strip():
            raise HarnessError(
                f"harness {target_spec.name!r} returned an empty response"
            )
        if not isinstance(model_name, str) or not model_name.strip():
            raise HarnessError(
                f"harness {target_spec.name!r} returned an empty model_name"
            )
        created_at = now_iso()
        turn_id = new_ulid()
        graph, warnings = compile_structured(
            response,
            session_id=request.session_id,
            turn_id=turn_id,
            model=ModelInfo(
                provider="shell",
                name=model_name.strip(),
                compile_mode="structured_emit",
            ),
            now=created_at,
            parent_graph_id=request.graph_id,
        )
        validate_graph(graph)
    except (CompileError, HarnessError, ValidationError, ValueError):
        return _record_failure(
            store,
            request,
            target_spec.name,
            "invalid_response",
            "The collaborator returned a response that could not be compiled.",
        )
    with store.continuation_inbox_lock():
        if not _is_pending(store, request.id):
            if request.parallel_batch_id is not None:
                return {
                    "status": "canceled",
                    "harness": target_spec.name,
                    "request_id": request.id,
                }
            raise HarnessError(
                f"continuation request {request.id} closed before its response could be stored; "
                "the response was discarded"
            )
        turns = _continuation_turns(
            store, request, graph, created_at=created_at
        )
        store.write_graph(graph)
        for turn in turns:
            store.append_turn(turn)
        completion = continuation_completion(request.id, graph.id, target_spec.name)
        completion_path = store.write_continuation_completion(completion)
        store.update_session_head(
            request.session_id, graph_id=graph.id, turn_id=graph.turn_id
        )
    store.log(
        "harness_continue",
        session_id=request.session_id,
        graph_id=graph.id,
        request_id=request.id,
        completion_id=completion.id,
        harness=target_spec.name,
        path=str(completion_path),
        warnings=warnings,
    )
    return {
        "status": "completed",
        "harness": target_spec.name,
        "request_id": request.id,
        "graph_id": graph.id,
        "completion_id": completion.id,
        "warnings": warnings,
    }


def watch_continuations(
    store: Store,
    spec: HarnessSpec,
    *,
    interval: float = 2,
    timeout: float = 900,
    registry: HarnessRegistry | None = None,
) -> Iterator[dict[str, Any]]:
    if interval <= 0:
        raise HarnessError("watch interval must be greater than zero")
    while True:
        outcome = process_continuation(
            store, spec, timeout=timeout, registry=registry
        )
        if outcome is None:
            time.sleep(interval)
            continue
        yield outcome
