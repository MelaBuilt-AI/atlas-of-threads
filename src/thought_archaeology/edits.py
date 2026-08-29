from __future__ import annotations

import time
from dataclasses import dataclass

from thought_archaeology.fork import fork_from, veto_from
from thought_archaeology.ids import new_ulid, now_iso
from thought_archaeology.inhabit import resolve_standing
from thought_archaeology.models import SCHEMA_VERSION, ModelInfo, ThoughtGraph, ThoughtNode, Turn
from thought_archaeology.schema import validate_graph
from thought_archaeology.store import Store


@dataclass(frozen=True)
class EditPlan:
    g0: ThoughtGraph
    node: ThoughtNode
    g1: ThoughtGraph
    warnings: list[str]
    now: str
    turn_id: str
    role: str
    provider: str | None
    op: str
    t0: float


def append_op_turn(
    store: Store,
    *,
    session_id: str,
    turn_id: str,
    now: str,
    role: str,
    prose: str,
    graph_id: str,
    fork_of_node_id: str,
    provider: str | None,
    parent_turn_id: str | None = None,
) -> None:
    existing = list(store.iter_turns(session_id))
    seq = len(existing)
    session = store.load_session(session_id)
    parent_id = parent_turn_id if parent_turn_id is not None else session.head_turn_id
    if parent_id is None and existing:
        parent_id = existing[-1].id
    turn = Turn(
        schema_version=SCHEMA_VERSION,
        id=turn_id,
        session_id=session_id,
        seq=seq,
        role=role,  # type: ignore[arg-type]
        created_at=now,
        prose=prose,
        graph_id=graph_id,
        parent_turn_id=parent_id,
        fork_of_node_id=fork_of_node_id,
        provider=provider,  # type: ignore[arg-type]
    )
    store.append_turn(turn)
    store.update_session_head(session_id, graph_id=graph_id, turn_id=turn_id)


def commit(store: Store, plan: EditPlan) -> ThoughtGraph:
    validate_graph(plan.g1)
    path = store.write_graph(plan.g1)
    append_op_turn(
        store,
        session_id=plan.g1.session_id,
        turn_id=plan.turn_id,
        now=plan.now,
        role=plan.role,
        prose=plan.g1.prose,
        graph_id=plan.g1.id,
        fork_of_node_id=plan.node.id,
        provider=plan.provider,
    )
    store.log(
        plan.op,
        session_id=plan.g1.session_id,
        graph_id=plan.g1.id,
        path=str(path),
        duration_ms=round((time.perf_counter() - plan.t0) * 1000, 3),
        warnings=plan.warnings,
    )
    return plan.g1


def plan_fork(
    store: Store,
    node_id: str,
    *,
    session_id: str,
    graph_id: str | None = None,
    reason: str | None = None,
    model: ModelInfo | None = None,
    regen_text: str | None = None,
) -> EditPlan:
    t0 = time.perf_counter()
    g0, node = resolve_standing(
        store, node_id, graph_id=graph_id, session_id=session_id
    )
    now = now_iso()
    turn_id = new_ulid()
    if model is None:
        model = ModelInfo(
            provider="none",
            name=g0.model.name or "unknown",
            compile_mode=g0.model.compile_mode,
        )
    g1, warnings = fork_from(
        g0,
        node,
        session_id=session_id,
        turn_id=turn_id,
        now=now,
        model=model,
        reason=reason,
        regen_text=regen_text,
    )
    return EditPlan(
        g0=g0,
        node=node,
        g1=g1,
        warnings=warnings,
        now=now,
        turn_id=turn_id,
        role="assistant" if regen_text else "human_edit",
        provider=model.provider if regen_text else None,
        op="fork",
        t0=t0,
    )


def plan_veto(
    store: Store,
    node_id: str,
    *,
    session_id: str,
    reason: str,
    graph_id: str | None = None,
) -> EditPlan:
    t0 = time.perf_counter()
    g0, node = resolve_standing(
        store, node_id, graph_id=graph_id, session_id=session_id
    )
    now = now_iso()
    turn_id = new_ulid()
    g1, warnings = veto_from(
        g0,
        node,
        session_id=session_id,
        turn_id=turn_id,
        now=now,
        reason=reason,
    )
    return EditPlan(
        g0=g0,
        node=node,
        g1=g1,
        warnings=warnings,
        now=now,
        turn_id=turn_id,
        role="human_edit",
        provider=None,
        op="veto",
        t0=t0,
    )
