"""Native doorway and paired return transport checks use isolated synthetic stores."""
import json

import pytest

from thought_archaeology import doorways, portable, return_paths
from thought_archaeology.store import StoreError
from tests.test_return_paths import exchange, complete
from tests.test_portable import inquiry, files


def test_native_exact_source_entry_return_and_inert_receipt(exchange):
    owner, _, visitor, reviewed = exchange
    _, offer = complete(visitor, reviewed)
    source = reviewed['context']['source']
    before = files(owner.sessions_dir)
    return_paths.receive(owner, offer)
    assert doorways.native(owner, source['graph_id'], source['node_id']) == []
    return_paths.decide(owner, offer['id'], 'accepted')
    [door] = doorways.native(owner, source['graph_id'], source['node_id'])
    info = portable.summary(offer['content']['inquiry'])
    assert (door['graphId'], door['nodeId']) == tuple(info['spawn'].values())
    assert '?arrival=' + offer['id'] in door['href']
    assert doorways.native(owner, source['graph_id'], '0' * 26) == []
    [back] = doorways.native(owner, door['graphId'], door['nodeId'], info['id'])
    assert back['returnOrigin'] is True
    assert back['href'] == f'/?doorway={offer["id"]}#/g/{source["graph_id"]}/n/{source["node_id"]}'
    assert files(owner.sessions_dir) == before
    assert not list(owner.iter_continuation_requests(pending=True))


def test_paired_full_offer_validates_before_receive_and_explicit_public_decision(exchange, monkeypatch):
    owner, _, visitor, reviewed = exchange
    _, offer = complete(visitor, reviewed)
    proposed = {'offer_id': offer['id'], 'projection': {'audience': 'public'}}
    detail = {'id': 'a' * 64, 'offer_json': portable.canonical(offer).decode(), 'review': proposed, 'decision': None}
    calls = []
    def remote(store, path, body=None):
        calls.append((path, body))
        return {'decision': body['decision']} if body else detail
    monkeypatch.setattr(doorways, '_call', remote)
    before = files(owner.root)
    doorways.read(owner, detail['id'])
    assert files(owner.root) == before
    with pytest.raises(StoreError, match='public doorway consent'):
        doorways.decide(owner, detail['id'], proposed, 'accepted')
    assert files(owner.root) == before
    doorways.receive(owner, detail['id'])
    assert portable.list_inquiries(owner) == []
    result = doorways.decide(owner, detail['id'], proposed, 'accepted', True)
    assert result['local']['status'] == 'accepted'
    assert len(portable.list_inquiries(owner)) == 1
    assert calls[-1][1]['public_consent'] is True
    assert not list(owner.iter_continuation_requests(pending=True))


def test_network_failure_after_local_acceptance_is_retryable(exchange, monkeypatch):
    owner, _, visitor, reviewed = exchange
    _, offer = complete(visitor, reviewed)
    review = {'offer_id': offer['id']}
    detail = {'offer_json': portable.canonical(offer).decode(), 'review': review, 'decision': None}
    attempts = []
    def remote(store, path, body=None):
        if body:
            attempts.append(body)
            if len(attempts) == 1:
                raise StoreError('offline')
            return {'decision': 'accepted'}
        return detail
    monkeypatch.setattr(doorways, '_call', remote)
    doorways.receive(owner, 'a' * 64)
    with pytest.raises(StoreError, match='offline'):
        doorways.decide(owner, 'a' * 64, review, 'accepted', True)
    assert len(portable.list_inquiries(owner)) == 1
    doorways.decide(owner, 'a' * 64, review, 'accepted', True)
    assert len(portable.list_inquiries(owner)) == 1
    assert return_paths.inbox(owner)[0]['status'] == 'accepted'
