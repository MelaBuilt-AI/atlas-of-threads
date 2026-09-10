"""Private local continuations and reviewed, inert return-path offers."""
from __future__ import annotations

import json
import re

from thought_archaeology import portable
from thought_archaeology.continuation import continuation_request
from thought_archaeology.ids import is_ulid, new_ulid, now_iso
from thought_archaeology.models import SCHEMA_VERSION, ModelInfo, ThoughtGraph, ThoughtNode, Turn
from thought_archaeology.store import Store, StoreError, _mkdir, _write_private_json_atomic


def preview(store: Store, inquiry_id: str, graph_id: str, node_id: str, question: str) -> dict:
    if not isinstance(question, str) or not 1 <= len(question.strip()) <= 400:
        raise StoreError("Enter a question of 1–400 characters")
    bundle, _ = portable.imported_inquiry(store, inquiry_id)
    record = next((r for r in bundle['content']['graphs'] if r['graph']['id'] == graph_id), None)
    if record is None:
        raise StoreError("Choose a graph in this imported inquiry")
    node = next((n for n in record['graph']['nodes'] if n['id'] == node_id), None)
    if node is None:
        raise StoreError("Choose a thought in this imported inquiry")
    source = {"inquiry_id": inquiry_id, "origin_id": bundle['content']['origin_id'],
              "session_id": bundle['content']['session']['id'], "graph_id": graph_id,
              "node_id": node_id, "source_sha256": record['source_sha256'],
              "shared_sha256": record['shared_sha256'], "author": bundle['content']['author']}
    context = {"source": source, "thought": node, "answer": record['graph']['prose']}
    if len(portable.canonical(context)) > 64 * 1024:
        raise StoreError("Selected answer exceeds the 64 KiB private continuation context limit")
    return {"question": question.strip(), "context": context}


def begin(store: Store, reviewed: dict) -> dict:
    """Queue one explicit human question through the existing local worker."""
    source = reviewed['context']['source']
    current = preview(store, source['inquiry_id'], source['graph_id'], source['node_id'], reviewed['question'])
    if reviewed != current:
        raise StoreError("The selected source changed; review the context again")
    with store.continuation_inbox_lock():
        if list(store.iter_continuation_requests(pending=True)):
            raise StoreError("Finish or cancel the current response before continuing this inquiry")
        question = current['question']
        session = store.init_session(question[:80], origin="external-inquiry:private-continuation")
        now = now_iso()
        node = ThoughtNode(id=new_ulid(), kind="uncertainty", text=question, status="uncertain",
                           agent="human", created_at=now, source="human", notes="private continuation")
        graph = ThoughtGraph(SCHEMA_VERSION, new_ulid(), session.id, new_ulid(), now, question,
                             (node,), (), ModelInfo("none", "human inquiry", "posthoc"),
                             metadata={"workspace_origin": True, "external_inquiry": current['context']})
        store.write_graph(graph)
        store.append_turn(Turn(SCHEMA_VERSION, graph.turn_id, session.id, 0, "user", now,
                               question, graph.id, None, None, "none"))
        store.update_session_head(session.id, graph_id=graph.id, turn_id=graph.turn_id)
        # Saved before the request becomes visible to the worker.
        _write_private_json_atomic(store.session_dir(session.id) / 'external-source.json',
                                   {"source": source, "question": question, "seed_graph_id": graph.id})
        request = continuation_request(graph, node, prompt=question, source="workspace")
        store.write_continuation_request(request)
    return {"session_id": session.id, "request_id": request.id,
            "url": f"/#/g/{graph.id}/n/{node.id}"}


def private_paths(store: Store) -> list[dict]:
    if not store.exists():
        return []
    paths = []
    for path in sorted(store.sessions_dir.glob('*/external-source.json')):
        record = json.loads(path.read_text(encoding='utf-8'))
        session = store.load_session(path.parent.name)
        graph = store.load_graph(session.head_graph_id)
        paths.append({**record, "session_id": session.id, "title": session.title,
                      "url": f"/#/g/{graph.id}/n/{graph.nodes[0].id}"})
    return paths


def export_offer(store: Store, session_id: str, *, author: str) -> dict:
    if not is_ulid(session_id):
        raise StoreError("Choose a private continuation")
    path = store.session_dir(session_id) / 'external-source.json'
    if not path.is_file():
        raise StoreError("This Threadwalk does not continue an imported inquiry")
    record = json.loads(path.read_text(encoding='utf-8'))
    bundle = portable.export_inquiry(store, session_id, author=author)
    if not any(r['graph']['id'] != record['seed_graph_id'] and r['role'] == 'assistant'
               for r in bundle['content']['graphs']):
        raise StoreError("Wait for a completed collaborator response before offering this path")
    content = {"source": record['source'], "question": record['question'], "inquiry": bundle}
    offer = {"format": "atlas-return-path", "version": 1, "id": portable.digest(content), "content": content}
    validate_offer(offer)
    return offer


def validate_offer(offer: dict) -> None:
    """Validate the transport envelope before any recipient writes."""
    try:
        if len(portable.canonical(offer)) > portable.MAX_BYTES:
            raise StoreError("Return-path file exceeds 8 MiB")
        if set(offer) != {'format', 'version', 'id', 'content'} or offer['format'] != 'atlas-return-path' or offer['version'] != 1:
            raise StoreError("Choose a supported Atlas return-path file")
        content = offer['content']
        if set(content) != {'source', 'question', 'inquiry'} or portable.digest(content) != offer['id']:
            raise StoreError("Return-path checksum or contents are invalid")
        source = content['source']
        if set(source) != {'inquiry_id', 'origin_id', 'session_id', 'graph_id', 'node_id', 'source_sha256', 'shared_sha256', 'author'}:
            raise StoreError("Return path has invalid source fields")
        if not all(isinstance(source[k], str) and re.fullmatch('[0-9a-f]{64}', source[k])
                   for k in ('inquiry_id', 'source_sha256', 'shared_sha256')):
            raise StoreError("Return path has invalid source checksums")
        if not all(isinstance(source[k], str) and is_ulid(source[k]) for k in ('origin_id', 'session_id', 'graph_id', 'node_id')):
            raise StoreError("Return path has invalid source identities")
        if not isinstance(source['author'], str) or not 1 <= len(source['author']) <= 120:
            raise StoreError("Return path has invalid source attribution")
        if not isinstance(content['question'], str) or not 1 <= len(content['question'].strip()) <= 400:
            raise StoreError("Return path has an invalid question")
        portable.validate_bundle(content['inquiry'])
    except (KeyError, TypeError, ValueError, RecursionError) as exc:
        raise StoreError("Choose a valid Atlas return-path JSON file") from exc


def inspect_source(store: Store, source: dict) -> None:
    """Match the canonical exact-source reference shared by returns and Capsules."""
    origin_path = store.root / 'portable-origin.json'
    if not origin_path.is_file() or json.loads(origin_path.read_text(encoding='utf-8'))['id'] != source['origin_id']:
        raise StoreError("This offer is addressed to a different Atlas origin")
    graph = store.load_graph(source['graph_id'])
    if graph.session_id != source['session_id'] or source['node_id'] not in {n.id for n in graph.nodes}:
        raise StoreError("The offered path does not name a source chamber in this Atlas")
    if store.graph_sha256(graph.id) != source['source_sha256'] or portable.digest(portable.project_graph(graph)) != source['shared_sha256']:
        raise StoreError("The offered path does not match the exact source graph")


def inspect_offer(store: Store, offer: dict) -> dict:
    validate_offer(offer)
    source = offer['content']['source']
    inspect_source(store, source)
    return {"id": offer['id'], "source": source, "question": offer['content']['question'],
            "inquiry": portable.summary(offer['content']['inquiry'])}


def receive(store: Store, offer: dict) -> dict:
    info = inspect_offer(store, offer)
    with store.continuation_inbox_lock():
        directory = store.root / 'return-paths' / 'offers'
        _mkdir(directory)
        path = directory / f"{offer['id']}.json"
        if path.exists():
            if json.loads(path.read_text(encoding='utf-8')) != offer:
                raise StoreError("Existing offer has different contents")
        else:
            _write_private_json_atomic(path, offer)
    return info


def inbox(store: Store) -> list[dict]:
    result = []
    for path in sorted((store.root / 'return-paths' / 'offers').glob('*.json')):
        offer = json.loads(path.read_text(encoding='utf-8'))
        info = inspect_offer(store, offer)
        decision = store.root / 'return-paths' / 'decisions' / path.name
        info['status'] = json.loads(decision.read_text(encoding='utf-8'))['decision'] if decision.is_file() else 'pending'
        result.append(info)
    return result


def load_offer(store: Store, offer_id: str) -> dict:
    if not isinstance(offer_id, str) or not re.fullmatch('[0-9a-f]{64}', offer_id):
        raise StoreError("Choose a received return path")
    path = store.root / 'return-paths' / 'offers' / f'{offer_id}.json'
    if not path.is_file():
        raise StoreError("Receive and review this offer first")
    offer = json.loads(path.read_text(encoding='utf-8'))
    inspect_offer(store, offer)
    return offer


def decide(store: Store, offer_id: str, decision: str) -> dict:
    if not isinstance(offer_id, str) or not re.fullmatch('[0-9a-f]{64}', offer_id):
        raise StoreError("Choose a received return path")
    if decision not in {'accepted', 'declined'}:
        raise StoreError("Choose accept or decline")
    with store.continuation_inbox_lock():
        offer = load_offer(store, offer_id)
        info = inspect_offer(store, offer)
        directory = store.root / 'return-paths' / 'decisions'
        target = directory / f'{offer_id}.json'
        if target.is_file():
            existing = json.loads(target.read_text(encoding='utf-8'))
            if existing['decision'] != decision:
                raise StoreError("This offer already has a different decision")
            return {**info, "status": decision}
        if decision == 'accepted':
            portable.import_inquiry(store, offer['content']['inquiry'])
        _mkdir(directory)
        _write_private_json_atomic(target, {"offer_id": offer_id, "decision": decision, "created_at": now_iso()})
    return {**info, "status": decision}


def arrivals(store: Store, graph_id: str, node_id: str) -> list[dict]:
    return [item for item in inbox(store) if item['status'] == 'accepted'
            and item['source']['graph_id'] == graph_id and item['source']['node_id'] == node_id]
