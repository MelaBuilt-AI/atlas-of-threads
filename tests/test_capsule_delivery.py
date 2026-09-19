"""Synthetic paired transport exercises local persistence/retry and consent boundaries."""
import copy
import json
import threading

import pytest
from thought_archaeology import capsule_delivery as delivery, capsules, online_connection as connection, portable
from thought_archaeology.serve import make_server, viz_dist_path
from thought_archaeology.store import Store, StoreError, _write_private_json_atomic
from tests.test_capsules import saved_capsule
from tests.test_portable import inquiry, files
from tests.test_serve import _get, _post


@pytest.fixture
def service(monkeypatch):
    state = {'calls': [], 'deliveries': {}, 'fail': None}

    def request(path, data=None, token=None):
        state['calls'].append((path, data, token))
        assert token == 'synthetic-private-token'
        if state['fail'] == path:
            raise StoreError('Synthetic connection interruption')
        if path == '/api/capsules/review':
            return {'review': {**data, 'sender': {'id': 'a', 'login': 'synthetic-a'},
                               'recipient': {'id': 'b', 'login': 'synthetic-b'}, 'source': None, 'reply_source': None}}
        if path == '/api/capsules/send':
            capsule = json.loads(data['review']['capsule_json'])
            id = portable.digest({'capsule': capsule['id']})
            reused = id in state['deliveries']
            state['deliveries'][id] = {'id': id, 'capsule_id': capsule['id'], 'capsule_json': data['review']['capsule_json'],
                                       'sender': {'id': 'a', 'login': 'synthetic-a'}, 'source': None}
            return {'id': id, 'reused': reused}
        if path.endswith('/receive'):
            return {'received_at': 123, 'decision': None}
        if path.endswith('/decide'):
            return {'decision': data['decision'], 'decided_at': 124}
        return copy.deepcopy(state['deliveries'][path.split('/')[-1]])

    monkeypatch.setattr(connection, '_request', request)
    return state


def pair(store, owner='a'):
    _write_private_json_atomic(store.root / connection.CONNECTION_FILE,
                              {'id': 'synthetic-device', 'name': 'Synthetic Atlas', 'owner': {'id': owner, 'login': 'synthetic-'+owner},
                               'token': 'synthetic-private-token', 'service': connection.SERVICE})


def test_send_only_frozen_reviewed_capsule_lost_local_receipt_reuses_launch(inquiry, service, monkeypatch):
    store, _, capsule = saved_capsule(inquiry); pair(store)
    assert service['calls'] == []
    review = delivery.review(store, capsule['id'], {'audience': 'directed', 'recipient_id': 'b'})['review']
    assert 'synthetic-private-token' not in json.dumps(review)
    record = delivery._record
    monkeypatch.setattr(delivery, '_record', lambda *_: (_ for _ in ()).throw(OSError('Synthetic disk interruption')))
    with pytest.raises(OSError): delivery.send(store, review)
    monkeypatch.setattr(delivery, '_record', record)
    sent = delivery.send(Store(store.root), review)
    assert sent['reused'] and len(service['deliveries']) == 1
    assert delivery.receipts(store)['deliveries'][0]['sent']
    assert 'synthetic-private-token' not in json.dumps(delivery.receipts(store))
    bad = copy.deepcopy(capsule); bad['content']['message'] = 'Changed payload'; bad['id'] = portable.digest(bad['content'])
    with pytest.raises(StoreError): delivery.send(store, {**review, 'capsule_json': portable.canonical(bad).decode()})
    assert len(service['deliveries']) == 1


def test_inert_receive_saves_before_ack_and_recovers_after_disconnect(inquiry, service, tmp_path):
    a, _, capsule = saved_capsule(inquiry); pair(a)
    review = delivery.review(a, capsule['id'], {'audience': 'directed', 'recipient_id': 'b'})['review']
    sent = delivery.send(a, review)
    b = Store(tmp_path / 'recipient'); b.initialize(); pair(b, 'b')
    initial = files(b.root)
    delivery.read(b, sent['id'])
    assert files(b.root) == initial
    service['fail'] = '/api/capsules/' + sent['id'] + '/receive'
    with pytest.raises(StoreError, match='interruption'): delivery.receive(b, sent['id'])
    assert capsules.load(b, 'received', capsule['id']) == capsule
    assert list(b.iter_continuation_requests()) == []
    assert list(b.iter_session_ids()) == []
    service['fail'] = None
    result = delivery.receive(Store(b.root), sent['id'])
    assert result['received_at'] == 123
    assert len(capsules.library(b)['received']) == 1
    assert len(delivery.receipts(b)['deliveries']) == 1
    pair(b, 'c')
    assert delivery.receipts(b)['deliveries'] == []
    pair(b, 'b')
    assert len(delivery.receipts(b)['deliveries']) == 1


def test_wrong_local_source_rejected_before_receive_or_ack(inquiry, service, tmp_path):
    a, _, original = saved_capsule(inquiry); pair(a)
    pending_before = list(a.iter_continuation_requests())
    b = Store(tmp_path / 'b'); b.initialize(); capsules.receive(b, original)
    draft = {'intent': 'return', 'title': 'Synthetic return', 'author': 'Synthetic B', 'message': 'A finding', 'reply_to': {'kind': 'capsule', 'id': original['id']}}
    ret = capsules.prepare(b, draft)
    id = 'a' * 64
    service['deliveries'][id] = {'id': id, 'capsule_id': ret['id'], 'capsule_json': portable.canonical(ret).decode(), 'source': None}
    wrong = Store(tmp_path / 'wrong'); wrong.initialize(); pair(wrong)
    before = files(wrong.root)
    with pytest.raises(StoreError): delivery.receive(wrong, id)
    assert files(wrong.root) == before
    assert not any(p.endswith('/receive') for p, _, _ in service['calls'])
    received = delivery.receive(a, id)
    assert received['received_at'] == 123
    with pytest.raises(StoreError, match='original source'): delivery.decide(a, id, 'accepted', {'wrong': True}, ret['id'])
    assert delivery.decide(a, id, 'accepted', None, ret['id'])['decision'] == 'accepted'
    assert list(a.iter_continuation_requests()) == pending_before


def test_offline_and_unpaired_status_do_not_send_existing_capsules(inquiry, service):
    store, _, capsule = saved_capsule(inquiry)
    assert delivery.receipts(store) == {'deliveries': []}
    with pytest.raises(StoreError, match='Connect'): delivery.review(store, capsule['id'], {})
    assert service['calls'] == []
    pair(store)
    assert delivery.receipts(store) == {'deliveries': []}
    assert service['calls'] == []
    service['fail'] = '/api/capsules/review'
    before = files(store.root)
    with pytest.raises(StoreError): delivery.review(store, capsule['id'], {'audience': 'directed'})
    assert files(store.root) == before
    assert capsules.export_files(store, capsule['id'])['id'] == capsule['id']


def test_local_http_transport_requires_origin_and_review(inquiry, service):
    store, _, capsule = saved_capsule(inquiry); pair(store)
    server = make_server(store, port=0, dist=viz_dist_path())
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        code, review = _post(base+'/api/capsules/online-review', {'id': capsule['id'], 'destination': {'audience': 'directed', 'recipient_id': 'b'}})
        assert code == 200
        review = json.loads(review)
        code, _ = _post(base+'/api/capsules/online-send', {'review': review['review']})
        assert code == 404
        code, sent = _post(base+'/api/capsules/online-send', {'review': review['review'], 'reviewed': True})
        assert code == 200
        sent = json.loads(sent)
        code, text, _ = _get(base+'/api/capsules/online-receipts')
        receipts = json.loads(text)
        assert code == 200 and receipts['deliveries'][0]['id'] == sent['id']
        assert 'synthetic-private-token' not in json.dumps(receipts)
    finally:
        server.shutdown(); server.server_close()
