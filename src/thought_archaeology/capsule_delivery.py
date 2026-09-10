"""Deliberate paired-device Capsule delivery and inert local reconnect receipts."""
from __future__ import annotations

import json
from urllib.parse import urlencode

from thought_archaeology import capsules, online_connection, portable
from thought_archaeology.store import Store, StoreError, _mkdir, _write_private_json_atomic


def _connection(store):
    saved = online_connection._saved(store)
    if not saved:
        raise StoreError('Connect this Personal Atlas before using online delivery')
    return saved


def _call(store, path, data=None):
    return online_connection._request(path, data, _connection(store)['token'])


def _receipt_path(store, delivery_id):
    owner = _connection(store)['owner']['id']
    # Hash the account scope so even synthetic identities cannot become paths.
    scope = portable.digest({'service': online_connection.SERVICE, 'owner_id': owner})
    return capsules._path(store, 'online/' + scope, delivery_id)


def _record(store, detail):
    with store.continuation_inbox_lock():
        path = _receipt_path(store, detail['id'])
        _mkdir(path.parent)
        _write_private_json_atomic(path, detail)
    return detail


def browse(store, view='inbox', after=0):
    if view not in {'inbox', 'sent', 'public'} or type(after) is not int or after < 0:
        raise StoreError('Choose an online Capsule collection')
    return _call(store, '/api/capsules?' + urlencode({'view': view, 'after': after}))


def destinations(store, recipient=None):
    query = '?' + urlencode({'recipient': recipient}) if recipient else ''
    return _call(store, '/api/capsules/destinations' + query)


def review(store, capsule_id, destination):
    capsule = capsules.load(store, 'prepared', capsule_id)
    return _call(store, '/api/capsules/review', {
        'capsule_json': portable.canonical(capsule).decode(), 'destination': destination})


def send(store, reviewed):
    if not isinstance(reviewed, dict):
        raise StoreError('Review the complete delivery first')
    try:
        capsule = json.loads(reviewed['capsule_json'])
    except (KeyError, TypeError, ValueError):
        raise StoreError('Review a saved Capsule first') from None
    if capsules.load(store, 'prepared', capsule.get('id')) != capsule:
        raise StoreError('The delivery differs from the frozen Capsule')
    result = _call(store, '/api/capsules/send', {'reviewed': True, 'review': reviewed})
    _record(store, {'id': result['id'], 'sent': True, 'capsule_id': capsule['id'], 'review': reviewed, **result})
    return result


def read(store, delivery_id):
    capsules._path(store, 'online', delivery_id)  # Validate before using an ID in a URL.
    detail = _call(store, '/api/capsules/' + delivery_id)
    capsule = json.loads(detail['capsule_json'])
    capsules.validate(capsule)
    if detail['capsule_id'] != capsule['id']:
        raise StoreError('Delivery does not match its Capsule')
    return detail


def receive(store, delivery_id):
    detail = read(store, delivery_id)
    capsule = json.loads(detail['capsule_json'])
    # Exact local source checks happen before any writes or acknowledgement.
    # Another paired computer without the original source can read online, but
    # cannot accept that return as a local source match.
    capsules.receive(store, capsule)
    _record(store, detail)
    receipt = _call(store, '/api/capsules/' + delivery_id + '/receive', {'reviewed': True})
    return _record(store, {**detail, **receipt})


def decide(store, delivery_id, decision, source, capsule_id):
    if decision not in {'accepted', 'declined'}:
        raise StoreError('Choose accept or decline')
    detail = read(store, delivery_id)
    capsule = json.loads(detail['capsule_json'])
    capsules.inspect_incoming(store, capsule)
    if source != detail['source'] or capsule_id != capsule['id']:
        raise StoreError('Review the exact return and its original source again')
    if capsules.load(store, 'received', capsule['id']) != capsule:
        raise StoreError('Receive this Capsule before deciding')
    receipt = _call(store, '/api/capsules/' + delivery_id + '/decide', {
        'reviewed': True, 'decision': decision, 'source': source, 'capsule_id': capsule_id})
    return _record(store, {**detail, **receipt})


def withdraw(store, delivery_id):
    capsules._path(store, 'online', delivery_id)
    result = _call(store, '/api/capsules/' + delivery_id + '/withdraw', {'reviewed': True})
    path = _receipt_path(store, delivery_id)
    if path.exists():
        _record(store, {**json.loads(path.read_text(encoding='utf-8')), **result})
    return result


def blocks(store, owner_id=None, blocked=None):
    data = None if owner_id is None else {'owner_id': owner_id, 'blocked': blocked}
    return _call(store, '/api/blocks', data)


def receipts(store):
    if not online_connection.status(store)['connected']:
        return {'deliveries': []}
    directory = _receipt_path(store, '0' * 64).parent
    return {'deliveries': [json.loads(p.read_text(encoding='utf-8')) for p in sorted(directory.glob('*.json'))]}
