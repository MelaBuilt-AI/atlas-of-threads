"""Synthetic A → B → A exchanges using the canonical continuation worker."""
import copy
import json
import threading

import pytest

from thought_archaeology import portable, return_paths
from thought_archaeology.harness import HarnessRegistry, continuation_envelope, process_continuation
from thought_archaeology.schema import ValidationError
from thought_archaeology.serve import make_server, viz_dist_path
from thought_archaeology.store import Store, StoreError
from tests.test_harness import _register
from tests.test_portable import inquiry, files
from tests.test_serve import _compile_simple, _get, _post


@pytest.fixture
def exchange(inquiry, tmp_path, monkeypatch):
    publisher, bundle = inquiry
    target = Store(tmp_path/'recipient')
    _compile_simple(target.root)
    portable.import_inquiry(target, bundle)
    _register(monkeypatch, tmp_path, target.root)
    graph = bundle['content']['graphs'][0]['graph']
    reviewed = return_paths.preview(target, bundle['id'], graph['id'], graph['nodes'][0]['id'],
                                    'What would distinguish these possibilities?')
    return publisher, bundle, target, reviewed


def complete(target, reviewed):
    started = return_paths.begin(target, reviewed)
    registry = HarnessRegistry()
    result = process_continuation(target, registry.get(), request_id=started['request_id'], registry=registry)
    assert result['status'] == 'completed', result
    return started, return_paths.export_offer(target, started['session_id'], author='Synthetic visitor')


def test_full_return_loop_keeps_sources_heads_and_discussions_private(exchange):
    publisher, bundle, target, reviewed = exchange
    before_a = files(publisher.root)
    before_b = files(target.sessions_dir)
    _, imported = portable.imported_inquiry(target, bundle['id'])
    before_import = files(imported.root)
    started, offer = complete(target, reviewed)
    request = target.load_continuation_request(started['request_id'])
    envelope = continuation_envelope(target, request)
    assert envelope['graph']['metadata']['external_inquiry'] == reviewed['context']
    assert envelope['request']['prompt'] == reviewed['question']
    assert 'external_inquiry' not in json.dumps(offer)
    assert 'SYNTHETIC PRIVATE' not in json.dumps(offer)
    assert files(imported.root) == before_import
    assert all((target.sessions_dir/p).read_bytes() == data for p, data in before_b.items())
    assert target.validate_session(started['session_id']) == []
    assert files(publisher.root) == before_a
    info = return_paths.inspect_offer(publisher, offer)
    assert files(publisher.root) == before_a
    assert info['inquiry']['author'] == 'Synthetic visitor'
    return_paths.receive(publisher, offer)
    assert return_paths.inbox(publisher)[0]['status'] == 'pending'
    source = reviewed['context']['source']
    assert return_paths.arrivals(publisher, source['graph_id'], source['node_id']) == []
    assert portable.list_inquiries(publisher) == []
    return_paths.receive(publisher, offer)
    accepted = return_paths.decide(publisher, offer['id'], 'accepted')
    assert accepted['status'] == 'accepted'
    assert return_paths.decide(publisher, offer['id'], 'accepted') == accepted
    assert len(return_paths.arrivals(publisher, source['graph_id'], source['node_id'])) == 1
    assert len(portable.list_inquiries(publisher)) == 1
    assert all((publisher.root/p).read_bytes() == data for p, data in before_a.items())
    assert list(publisher.iter_continuation_requests(pending=True)) == []
    with pytest.raises(StoreError, match='different decision'):
        return_paths.decide(publisher, offer['id'], 'declined')


def test_decline_never_imports_or_creates_arrival(exchange):
    publisher, _, target, reviewed = exchange
    _, offer = complete(target, reviewed)
    return_paths.receive(publisher, offer)
    return_paths.decide(publisher, offer['id'], 'declined')
    return_paths.receive(publisher, offer)
    assert return_paths.inbox(publisher)[0]['status'] == 'declined'
    assert portable.list_inquiries(publisher) == []


@pytest.mark.parametrize('damage', ['hash', 'origin', 'source_hash', 'shared_hash', 'node', 'private_graph', 'traversal', 'malformed'])
def test_damaged_or_misaddressed_offer_writes_nothing(exchange, damage):
    publisher, _, target, reviewed = exchange
    _, original = complete(target, reviewed)
    offer = copy.deepcopy(original)
    source = offer['content']['source']
    if damage == 'hash': offer['id'] = '0'*64
    elif damage == 'origin': source['origin_id'] = '0'*26
    elif damage == 'source_hash': source['source_sha256'] = '0'*64
    elif damage == 'shared_hash': source['shared_sha256'] = '0'*64
    elif damage == 'node': source['node_id'] = '0'*26
    elif damage == 'private_graph': offer['content']['inquiry']['content']['graphs'][0]['graph']['hidden_reasoning'] = 'PRIVATE'
    elif damage == 'traversal': source['inquiry_id'] = '../../outside'
    elif damage == 'malformed': offer['content'] = []
    if damage != 'hash': offer['id'] = portable.digest(offer['content'])
    before = files(publisher.root)
    with pytest.raises((StoreError, ValidationError)):
        return_paths.receive(publisher, offer)
    assert files(publisher.root) == before


def test_preview_is_inert_and_changed_review_does_not_queue(exchange):
    _, bundle, target, reviewed = exchange
    before = files(target.root)
    graph = bundle['content']['graphs'][0]['graph']
    return_paths.preview(target, bundle['id'], graph['id'], graph['nodes'][0]['id'], 'Another question?')
    assert files(target.root) == before
    changed = copy.deepcopy(reviewed)
    changed['context']['answer'] = 'Unreviewed substitute'
    with pytest.raises(StoreError, match='changed'):
        return_paths.begin(target, changed)
    assert files(target.root) == before
    started = return_paths.begin(target, reviewed)
    with pytest.raises(StoreError, match='completed'):
        return_paths.export_offer(target, started['session_id'], author='Synthetic visitor')
    with pytest.raises(StoreError, match='Finish or cancel'):
        return_paths.begin(target, reviewed)


def test_http_review_queue_and_acceptance(exchange, monkeypatch):
    publisher, _, target, reviewed = exchange
    import thought_archaeology.serve as serve
    monkeypatch.setattr(serve, 'ensure_application_worker', lambda *a, **k: None)
    servers = []
    def start(store):
        server = make_server(store, port=0, dist=viz_dist_path())
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return f'http://127.0.0.1:{server.server_port}'
    a, b = start(publisher), start(target)
    try:
        source = reviewed['context']['source']
        code, body = _post(b+'/api/return-paths/preview', {**source, 'question': reviewed['question']})
        assert code == 200, body
        review = json.loads(body)
        assert review['reviewed'] == reviewed
        code, body = _post(b+'/api/return-paths/begin', review)
        assert code == 202, body
        started = json.loads(body)
        registry = HarnessRegistry()
        process_continuation(target, registry.get(), request_id=started['request_id'], registry=registry)
        code, body = _post(b+'/api/return-paths/export', {'session_id': started['session_id'], 'author': 'Synthetic visitor'})
        assert code == 200, body
        offer = json.loads(body)
        for action in ('inspect', 'receive'):
            code, body = _post(a+'/api/return-paths/'+action, offer)
            assert code == 200, body
        assert _post(a+'/api/return-paths/decide', {'id': offer['id'], 'decision': 'accepted'})[0] == 200
        code, body, _ = _get(a+f"/api/return-paths/at?graph={source['graph_id']}&node={source['node_id']}")
        assert code == 200, body
        assert len(json.loads(body)['arrivals']) == 1
        assert len(json.loads(_get(b+'/api/return-paths')[1])['private_paths']) == 1
    finally:
        for server in servers:
            server.shutdown(); server.server_close()
