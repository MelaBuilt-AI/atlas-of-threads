"""Reviewed excerpt Capsules. Offline artifacts, not a second thought-graph store."""
from __future__ import annotations

import hashlib
import json
import re

from thought_archaeology import portable, return_paths
from thought_archaeology.continuation import continuation_request
from thought_archaeology.ids import is_ulid, new_ulid, now_iso
from thought_archaeology.models import SCHEMA_VERSION, ModelInfo, ThoughtGraph, ThoughtNode, Turn
from thought_archaeology.schema import validate_schema
from thought_archaeology.store import Store, StoreError, _mkdir, _write_private_atomic, _write_private_json_atomic

MAX_BYTES = 256 * 1024
INTENTS = {'invitation': 'Invite perspectives', 'offering': 'Share a finding', 'return': 'Return a contribution'}


def _path(store: Store, category: str, capsule_id: str):
    if not isinstance(capsule_id, str) or not re.fullmatch('[0-9a-f]{64}', capsule_id):
        raise StoreError('Choose a saved Capsule')
    return store.root / 'capsules' / category / (capsule_id + '.json')


def load(store: Store, category: str, capsule_id: str) -> dict:
    path = _path(store, category, capsule_id)
    if not path.is_file():
        raise StoreError('Keep or receive this Capsule first')
    capsule = json.loads(path.read_text(encoding='utf-8'))
    validate(capsule)
    return capsule


def validate(capsule: dict) -> None:
    try:
        if len(portable.canonical(capsule)) > MAX_BYTES:
            raise StoreError('Capsule exceeds 256 KiB; select fewer excerpts')
    except (ValueError, TypeError, RecursionError) as exc:
        raise StoreError('Choose an ordinary Capsule JSON file') from exc
    validate_schema('shared-capsule.schema.json', capsule)
    c = capsule['content']
    if portable.digest(c) != capsule['id']:
        raise StoreError('Capsule checksum does not match its contents')
    if (c['intent'] == 'return') != (c['reply_to'] is not None):
        raise StoreError('Return intent requires an exact incoming Capsule or inquiry reference')
    graphs = set()
    for excerpt in c['excerpts']:
        source = excerpt['source']
        if source['graph_id'] in graphs or source['origin_id'] != c['origin_id'] or source['session_id'] != c['home_session_id']:
            raise StoreError('Capsule excerpts must be unique selections from its home Threadwalk')
        graphs.add(source['graph_id'])
        ids = [n['id'] for n in excerpt['thoughts']]
        if len(set(ids)) != len(ids) or any('probe_ids' in n or 'sensor_ids' in n for n in excerpt['thoughts']):
            raise StoreError('Capsule repeats thoughts or contains private sensor references')
        evidence_ids = set()
        for evidence in excerpt['evidence']:
            if (evidence['id'] in evidence_ids or evidence['graph_id'] != source['graph_id'] or evidence['node_id'] not in ids
                or not evidence['artifact_refs'] or not all(portable._public_url(r) for r in evidence['artifact_refs'])):
                raise StoreError('Capsule evidence must name selected thoughts and public web references')
            evidence_ids.add(evidence['id'])


def graph_choices(store: Store, session_id: str) -> list[dict]:
    store.load_session(session_id)
    return [{'id': g.id, 'model': g.model.name, 'created_at': g.created_at, 'thought_count': len(g.nodes)}
            for g in sorted(store.iter_graphs(session_id), key=lambda g: (g.created_at, g.id))]


def context(store: Store, graph_id: str) -> dict:
    graph = store.load_graph(graph_id)
    public = portable.project_graph(graph)
    question = None
    completion = next((c for c in store.iter_continuation_completions() if c.graph_id == graph_id), None)
    if completion:
        request = store.load_continuation_request(completion.request_id)
        question = {'question': request.prompt, 'graph_id': request.graph_id, 'node_id': request.node_id,
                    'author': completion.agent_name or completion.harness}
    else:
        bridge = graph.metadata.get('agent_bridge', {})
        if bridge.get('source_graph_id') and bridge.get('source_node_id'):
            question = {'question': bridge.get('question', ''), 'graph_id': bridge['source_graph_id'],
                        'node_id': bridge['source_node_id'], 'author': bridge.get('harness') or bridge.get('client_family') or 'Agent'}
    evidence = []
    for binding in store.iter_evidence(graph.session_id):
        if (binding['graph_id'] == graph_id and binding.get('artifact_refs')
            and all(portable._public_url(ref) for ref in binding['artifact_refs'])):
            evidence.append({k: binding[k] for k in ('schema_version','id','graph_id','node_id','kind','result','summary','artifact_refs','created_at')})
    return {'graph_id': graph.id, 'session_id': graph.session_id, 'model': public['model'],
            'thoughts': public['nodes'], 'answer': graph.prose, 'question': question,
            'evidence': sorted(evidence, key=lambda e: e['id']), 'source_sha256': store.graph_sha256(graph_id),
            'shared_sha256': portable.digest(public)}


def _reply(store: Store, chosen: dict | None) -> dict | None:
    if chosen is None:
        return None
    if not isinstance(chosen, dict):
        raise StoreError('Choose a received Capsule or imported inquiry to return to')
    if chosen.get('kind') == 'capsule':
        incoming = load(store, 'received', chosen.get('id'))
        return {'kind': 'capsule', 'id': incoming['id'], 'origin_id': incoming['content']['origin_id']}
    if chosen.get('kind') == 'inquiry':
        try:
            selected = return_paths.preview(store, chosen.get('inquiry_id', ''), chosen.get('graph_id', ''), chosen.get('node_id', ''), 'Prepare a return Capsule')
        except FileNotFoundError as exc:
            raise StoreError('Import the source inquiry before preparing its return') from exc
        return {'kind': 'inquiry', 'source': selected['context']['source']}
    raise StoreError('Return intent needs a real incoming source')


def prepare(store: Store, draft: dict, *, created_at: str | None = None) -> dict:
    """Resolve explicit selections from canonical artifacts, never a whole-session export."""
    if not isinstance(draft, dict):
        raise StoreError('Prepare a Capsule first')
    intent = draft.get('intent')
    if intent not in INTENTS:
        raise StoreError('Choose what your Capsule is for')
    fields = {}
    for name, limit, required in [('title',240,True),('author',120,True),('message',4000,True),('interpretation',8000,False)]:
        value = draft.get(name, '')
        if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
            raise StoreError(f'Enter {name} of {1 if required else 0}–{limit} characters')
        fields[name] = value.strip()
    reply = _reply(store, draft.get('reply_to'))
    if (intent == 'return') != (reply is not None):
        raise StoreError('Choose return intent only from a received Capsule or imported inquiry')
    session_id = draft.get('session_id') or None
    if session_id:
        if not is_ulid(session_id):
            raise StoreError('Choose a local Threadwalk')
        store.load_session(session_id)
    choices = draft.get('selections', [])
    if not isinstance(choices, list) or len(choices) > 64:
        raise StoreError('Choose up to 64 graph excerpts')
    excerpts = []
    for choice in choices:
        if not isinstance(choice, dict):
            raise StoreError('Choose thoughts from an available graph')
        current = context(store, choice.get('graph_id', ''))
        if current['session_id'] != session_id:
            raise StoreError('Selected thoughts must belong to the chosen Threadwalk')
        node_ids, evidence_ids = choice.get('node_ids', []), choice.get('evidence_ids', [])
        if (not isinstance(node_ids, list) or not node_ids or not all(isinstance(i,str) for i in node_ids)
            or len(set(node_ids)) != len(node_ids) or not set(node_ids) <= {n['id'] for n in current['thoughts']}):
            raise StoreError('Select distinct thoughts from this graph')
        if (not isinstance(evidence_ids, list) or not all(isinstance(i,str) for i in evidence_ids)
            or len(set(evidence_ids)) != len(evidence_ids) or not set(evidence_ids) <= {e['id'] for e in current['evidence']}):
            raise StoreError('Choose the available public evidence explicitly')
        for flag in ('include_answer', 'include_question'):
            if type(choice.get(flag, False)) is not bool:
                raise StoreError('Choose optional answer and question text explicitly')
        excerpts.append({'source': {'origin_id': portable._origin(store), 'session_id': session_id,
                         'graph_id': current['graph_id'], 'source_sha256': current['source_sha256'],
                         'shared_sha256': current['shared_sha256'], 'model': current['model']},
                         'thoughts': [n for n in current['thoughts'] if n['id'] in node_ids],
                         'answer': current['answer'] if choice.get('include_answer') else None,
                         'question': current['question'] if choice.get('include_question') else None,
                         'evidence': [e for e in current['evidence'] if e['id'] in evidence_ids]})
    c = {'origin_id': portable._origin(store), 'home_session_id': session_id, 'created_at': created_at or now_iso(),
         'intent': intent, **fields, 'reply_to': reply, 'excerpts': excerpts}
    capsule = {'format': 'atlas-capsule', 'version': 1, 'id': portable.digest(c), 'content': c}
    validate(capsule)
    return capsule


def summary(capsule: dict) -> dict:
    c = capsule['content']
    return {k: c[k] for k in ('title','author','intent','created_at','home_session_id','reply_to')} | {
        'id': capsule['id'], 'thought_count': sum(len(e['thoughts']) for e in c['excerpts']),
        'evidence_count': sum(len(e['evidence']) for e in c['excerpts'])}


def _keep(store: Store, category: str, capsule: dict) -> dict:
    with store.continuation_inbox_lock():
        path = _path(store, category, capsule['id'])
        reused = path.exists()
        if reused:
            if load(store, category, capsule['id']) != capsule:
                raise StoreError('Saved Capsule differs from these contents')
        else:
            _mkdir(path.parent)
            _write_private_json_atomic(path, capsule)
    return {**summary(capsule), 'already_saved': reused}


def freeze(store: Store, draft: dict, capsule: dict) -> dict:
    validate(capsule)
    current = prepare(store, draft, created_at=capsule['content']['created_at'])
    if current != capsule:
        raise StoreError('Capsule contents changed; review the exact payload again')
    return _keep(store, 'prepared', capsule)


def inspect_incoming(store: Store, capsule: dict) -> dict:
    validate(capsule)
    reply = capsule['content']['reply_to']
    if reply:
        if reply['kind'] == 'capsule':
            original = load(store, 'prepared', reply['id'])
            if original['content']['origin_id'] != reply['origin_id']:
                raise StoreError('Return Capsule names a different Atlas origin')
        else:
            return_paths.inspect_source(store, reply['source'])
    return summary(capsule)


def receive(store: Store, capsule: dict) -> dict:
    inspect_incoming(store, capsule)
    return _keep(store, 'received', capsule)


def markdown(capsule: dict) -> str:
    """A readable, inert projection of exactly the frozen payload."""
    c = capsule['content']
    lines = ['# '+c['title'], '', f"{INTENTS[c['intent']]} · shared by {c['author']}", '',
             'Publisher-supplied attribution. Checksums identify this payload, not verified authorship.', '',
             '## Question or finding', '', c['message'], '', '## Human interpretation', '', c['interpretation'] or '(None included)', '']
    if c['reply_to']:
        lines += ['## Return source', '', '```json', json.dumps(c['reply_to'], ensure_ascii=False, indent=2), '```', '']
    for excerpt in c['excerpts']:
        source = excerpt['source']
        lines += ['## Selected thoughts · '+source['model']['name'], '']
        for n in excerpt['thoughts']:
            lines += [f"### {n['kind']} · {n['status']}", '', n['text'], '']
            if n.get('notes'): lines += ['Notes: '+n['notes'], '']
        if excerpt['question'] is not None:
            lines += ['### Included source question', '', excerpt['question']['question'], '']
        if excerpt['answer'] is not None:
            lines += ['### Included full answer', '', excerpt['answer'], '']
        for evidence in excerpt['evidence']:
            lines += ['### Selected evidence', '', evidence['summary'], *evidence['artifact_refs'], '']
        lines += ['Source references (full source graphs are not included):', '```json', json.dumps(source, indent=2), '```', '']
    lines += ['## Exact frozen payload', '', 'The structured JSON includes all selected thought fields and evidence metadata.', '',
              '```json', portable.canonical(capsule).decode().rstrip(), '```', '',
              'No unselected graphs, private guides, local evidence files, credentials or legacy Capsule history are included.', '']
    return '\n'.join(lines)


def export_files(store: Store, capsule_id: str) -> dict:
    capsule = load(store, 'prepared', capsule_id)
    payload, readable = portable.canonical(capsule), markdown(capsule).encode('utf-8')
    with store.continuation_inbox_lock():
        folder = store.root / 'exports' / 'capsules' / capsule_id
        paths = [('capsule.atlas-capsule.json', payload), ('capsule.md', readable)]
        for filename, data in paths:
            path = folder / filename
            if path.exists() and path.read_bytes() != data:
                raise StoreError('Existing Capsule export differs from its frozen contents')
        _mkdir(folder)
        for filename, data in paths:
            if not (folder/filename).exists():
                _write_private_atomic(folder/filename, data)
        receipt = _path(store, 'exports', capsule_id)
        if not receipt.exists():
            _mkdir(receipt.parent)
            _write_private_json_atomic(receipt, {'capsule_id': capsule_id, 'created_at': now_iso(),
                'json_sha256': hashlib.sha256(payload).hexdigest(), 'markdown_sha256': hashlib.sha256(readable).hexdigest()})
    return {'id': capsule_id, 'json_path': str(folder/paths[0][0]), 'markdown_path': str(folder/paths[1][0])}


def library(store: Store) -> dict:
    result = {}
    for category in ('prepared', 'received'):
        result[category] = [summary(load(store, category, p.stem)) for p in sorted((store.root/'capsules'/category).glob('*.json'))]
    result['workspaces'] = []
    for path in sorted(store.sessions_dir.glob('*/capsule-source.json')):
        receipt = json.loads(path.read_text(encoding='utf-8'))
        session = store.load_session(path.parent.name)
        graph = store.load_graph(session.head_graph_id)
        result['workspaces'].append({**receipt, 'session_id':session.id, 'title':session.title,
                                    'url':f'/#/g/{graph.id}/n/{graph.nodes[0].id}'})
    result['legacy'] = [{'id':c.id,'title':c.session_title,'created_at':c.created_at}
                        for c in store.iter_knowledge_capsules()]
    return result


def work_preview(store: Store, capsule_id: str, question: str, excerpts: list[int]) -> dict:
    capsule = load(store, 'received', capsule_id)
    if not isinstance(question, str) or not 1 <= len(question.strip()) <= 400:
        raise StoreError('Enter a private question of 1–400 characters')
    available = capsule['content']['excerpts']
    if (not isinstance(excerpts, list) or any(type(i) is not int or not 0 <= i < len(available) for i in excerpts)
        or len(set(excerpts)) != len(excerpts)):
        raise StoreError('Choose the Capsule excerpts for your collaborator')
    context = {'capsule_id': capsule_id, 'origin_id': capsule['content']['origin_id'],
               **{k:capsule['content'][k] for k in ('title','author','intent','message','interpretation')},
               'excerpts': [available[i] for i in excerpts]}
    if len(portable.canonical(context)) > 64*1024:
        raise StoreError('Private context exceeds 64 KiB; include fewer excerpts')
    return {'question': question.strip(), 'excerpt_indices': excerpts, 'context': context}


def begin_work(store: Store, reviewed: dict) -> dict:
    capsule_id = reviewed.get('context', {}).get('capsule_id', '')
    current = work_preview(store, capsule_id, reviewed.get('question', ''), reviewed.get('excerpt_indices', []))
    if reviewed != current:
        raise StoreError('Private Capsule context changed; review it again')
    with store.continuation_inbox_lock():
        if list(store.iter_continuation_requests(pending=True)):
            raise StoreError('Finish or cancel the current response first')
        question, now = current['question'], now_iso()
        session = store.init_session(question[:80], origin='external-capsule:private-continuation')
        node = ThoughtNode(id=new_ulid(), kind='uncertainty', text=question, status='uncertain', agent='human', created_at=now, source='human')
        graph = ThoughtGraph(SCHEMA_VERSION, new_ulid(), session.id, new_ulid(), now, question, (node,), (),
                             ModelInfo('none', 'human inquiry', 'posthoc'),
                             metadata={'workspace_origin': True, 'external_capsule': current['context']})
        store.write_graph(graph)
        store.append_turn(Turn(SCHEMA_VERSION, graph.turn_id, session.id, 0, 'user', now, question, graph.id, None, None, 'none'))
        store.update_session_head(session.id, graph_id=graph.id, turn_id=graph.turn_id)
        _write_private_json_atomic(store.session_dir(session.id)/'capsule-source.json',
                                   {'capsule_id':capsule_id, 'seed_graph_id':graph.id, 'question':question})
        request = continuation_request(graph, node, prompt=question, source='workspace')
        store.write_continuation_request(request)
    return {'session_id':session.id, 'request_id':request.id, 'url':f'/#/g/{graph.id}/n/{node.id}'}
