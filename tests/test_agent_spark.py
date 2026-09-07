"""Synthetic guide discussions: role independence and graph-authority boundaries."""
import json
import sys
import time
from dataclasses import replace
from pathlib import Path

import pytest

from thought_archaeology import agent_spark as spark
from thought_archaeology.adapters.opencode import _prompt, _validate_envelope
from thought_archaeology.harness import HarnessError, HarnessRegistry, _agent_call_lock
from thought_archaeology.store import Store
from tests.test_serve import _compile_simple


def setup(tmp_path, monkeypatch):
    registry_path = tmp_path / 'config' / 'harnesses.json'
    monkeypatch.setenv('TA_HARNESS_CONFIG', str(registry_path))
    registry = HarnessRegistry()
    registry.register('synthetic-guide', sys.executable, model='synthetic/model')
    monkeypatch.setattr(spark, 'describe_harness', lambda *a, **k: {
        'capabilities': ['continue', 'discuss'], 'default_model': 'synthetic/model'})
    _, graph_id = _compile_simple(tmp_path / 'store')
    store = Store(tmp_path / 'store')
    graph = store.load_graph(graph_id)
    spark.assign_roles(store, {'harness': 'synthetic-guide', 'collaborator': True, 'guide': True})
    body = {'prompt': 'Examine this synthetic thought.', 'request_id': 'synthetic-request',
            'graph_id': graph_id, 'node_id': graph.nodes[0].id}
    return store, registry, body


def wait(store):
    until = time.monotonic() + 3
    while time.monotonic() < until:
        data = spark.discussion_payload(store)
        if all(t['status'] != 'pending' for t in data['turns']):
            return data
        time.sleep(.01)
    pytest.fail('Guide response did not complete')


def canonical(store):
    return {str(p.relative_to(store.root)): p.read_bytes() for p in store.root.rglob('*')
            if p.is_file() and 'guide-discussions' not in p.parts}


def test_prose_is_pinned_private_duplicate_safe_and_does_not_create_graphs(tmp_path, monkeypatch):
    store, registry, body = setup(tmp_path, monkeypatch)
    before = canonical(store)
    calls = []
    def respond(spec, operation, payload, **kwargs):
        calls.append(payload)
        assert operation == payload['operation'] == 'discuss'
        assert payload['standing']['node']['id'] == body['node_id']
        assert payload['graph']['id'] == body['graph_id']
        assert 'hidden_reasoning' not in payload['graph']
        return {'response': 'A synthetic guide response.', 'model_name': 'synthetic/serving-model'}
    monkeypatch.setattr(spark, '_adapter_call', respond)
    spark.begin_discussion(store, body)
    result = wait(store)
    assert result['turns'][0]['model'] == 'synthetic/serving-model'
    assert spark.begin_discussion(store, body)['id'] == body['request_id']
    assert len(calls) == 1
    with pytest.raises(HarnessError, match='different question'):
        spark.begin_discussion(store, {**body, 'prompt': 'changed'})
    # New request supplies prior visible conversation, not hidden model reasoning.
    spark.begin_discussion(store, {**body, 'request_id': 'synthetic-second'})
    wait(store)
    assert calls[-1]['discussion'][0]['response'] == 'A synthetic guide response.'
    assert canonical(store) == before
    assert spark.discussion_payload(Store(store.root))['turns'][-1]['status'] == 'completed'
    assert (store.root / 'guide-discussions/synthetic-guide.json').stat().st_mode & 0o777 == 0o600
    spark.clear_discussion(store)
    assert spark.discussion_payload(store)['turns'] == []
    assert canonical(store) == before


def test_roles_independent_and_five_slots_enforced(tmp_path, monkeypatch):
    store, registry, body = setup(tmp_path, monkeypatch)
    spark.assign_roles(store, {'harness': 'synthetic-guide', 'collaborator': False, 'guide': True})
    assert registry.default_name() is None
    assert registry.collaborator_names() == ()
    assert registry.guide_name() == 'synthetic-guide'
    for i in range(5):
        registry.register(f'collaborator-{i}', sys.executable)
    with pytest.raises(HarnessError, match='five'):
        registry.set_agent_roles('synthetic-guide', collaborator=True, guide=True)
    registry.set_agent_roles('collaborator-0', collaborator=False, guide=False)
    registry.set_agent_roles('synthetic-guide', collaborator=True, guide=True)
    assert len(registry.collaborator_names()) == 5
    assert registry.guide_name() == 'synthetic-guide'
    monkeypatch.setattr(spark, 'describe_harness', lambda *a, **k: {'capabilities': ['continue']})
    with pytest.raises(HarnessError, match='does not support'):
        spark.assign_roles(store, {'harness': 'collaborator-1', 'collaborator': True, 'guide': True})
    assert registry.guide_name() == 'synthetic-guide'


def test_failed_and_interrupted_requests_remain_visible(tmp_path, monkeypatch):
    store, registry, body = setup(tmp_path, monkeypatch)
    monkeypatch.setattr(spark, '_adapter_call', lambda *a, **k: (_ for _ in ()).throw(HarnessError('private stderr')))
    spark.begin_discussion(store, body)
    result = wait(store)
    assert result['turns'][0]['status'] == 'failed'
    assert 'private stderr' not in json.dumps(result)
    path = store.root / 'guide-discussions/synthetic-guide.json'
    data = json.loads(path.read_text());data['turns'][0]['status'] = 'pending';path.write_text(json.dumps(data))
    assert spark.discussion_payload(store)['turns'][0]['status'] == 'interrupted'


def test_discussion_prompt_and_shared_session_exclusion(tmp_path, monkeypatch):
    store, registry, body = setup(tmp_path, monkeypatch)
    envelope = {'protocol_version': '1', 'operation': 'discuss', 'request': {'prompt': 'A question'},
                'graph': {}, 'standing': {}, 'discussion': [{'prompt': 'Prior question', 'response': 'Prior prose'}]}
    prompt = _prompt(_validate_envelope(envelope))
    assert 'ordinary prose' in prompt
    assert 'Prior prose' in prompt
    assert 'exactly one fenced' not in prompt
    spec = replace(registry.get(), session_state=str(tmp_path/'agent-state.json'))
    with _agent_call_lock(spec):
        with pytest.raises(HarnessError, match='already responding'):
            with _agent_call_lock(spec):
                pass
