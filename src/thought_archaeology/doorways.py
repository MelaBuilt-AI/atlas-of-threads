"""Paired returned-path transport and exact native doorway projections."""
from __future__ import annotations

import json
import re
from urllib.parse import urlencode

from thought_archaeology import capsule_delivery, online, portable, return_paths
from thought_archaeology.store import StoreError


def _call(store, path, body=None):
    return capsule_delivery._call(store, '/api/doorways' + path, body)


def _id(value):
    if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value):
        raise StoreError('Choose a returned doorway')
    return value


def browse(store, after=0):
    return _call(store, '?' + urlencode({'after': after}))


def prepare(store, offer):
    return_paths.validate_offer(offer)
    current = return_paths.export_offer(store, offer['content']['inquiry']['content']['session']['id'],
                                      author=offer['content']['inquiry']['content']['author'])
    if current != offer:
        raise StoreError('The private path changed; review the complete offer again')
    sources = _call(store, '/sources?' + urlencode({'inquiry': offer['content']['source']['inquiry_id']}))
    return {'sources': sources['publications'], 'artifact': online.prepare_publication(offer['content']['inquiry']),
            'entry': portable.summary(offer['content']['inquiry'])['spawn']}


def publish(store, offer, artifact):
    current = prepare(store, offer)
    if current['artifact'] != artifact:
        raise StoreError('Review the complete returned inquiry before publishing')
    # Existing publication contract enforces exact snapshot retries and edition consent.
    return capsule_delivery._call(store, '/api/publications', {'artifact': artifact, 'reviewed': True})


def review(store, offer, source_id, target_id):
    prepared = prepare(store, offer)
    return _call(store, '/review', {'offer_id': offer['id'], 'source': offer['content']['source'],
                 'question': offer['content']['question'], 'entry': prepared['entry'],
                 'source_publication_id': source_id, 'target_publication_id': target_id})


def send(store, reviewed):
    # The service revalidates the exact frozen review and both publication owners.
    return _call(store, '/send', {'reviewed': True, 'review': reviewed})


def read(store, doorway_id):
    detail = _call(store, '/' + _id(doorway_id))
    offer = json.loads(detail['offer_json'])
    return_paths.validate_offer(offer)
    if offer['id'] != detail['review']['offer_id']:
        raise StoreError('Doorway differs from its returned path')
    return detail


def receive(store, doorway_id):
    detail = read(store, doorway_id)
    return return_paths.receive(store, json.loads(detail['offer_json']))


def decide(store, doorway_id, reviewed, decision, public_consent=False):
    detail = read(store, doorway_id)
    if detail['review'] != reviewed:
        raise StoreError('Review the original source and public doorway again')
    if decision == 'accepted' and public_consent is not True:
        raise StoreError('Explicit public doorway consent is required')
    offer = json.loads(detail['offer_json'])
    if return_paths.load_offer(store, offer['id']) != offer:
        raise StoreError('Receive the complete returned path first')
    if detail['decision'] and detail['decision'] != decision:
        raise StoreError('This offer already has a different online decision')
    # Materialize locally before recording a shared doorway. If the network fails,
    # the private import remains usable; retry the separately consented public action.
    local = return_paths.decide(store, offer['id'], decision)
    result = _call(store, '/' + doorway_id + '/decide', {'reviewed': True, 'review': reviewed,
                   'decision': decision, 'public_consent': public_consent})
    return {**result, 'local': local}


def withdraw(store, doorway_id):
    return _call(store, '/' + _id(doorway_id) + '/withdraw', {'reviewed': True})


def native(store, graph_id, node_id, inquiry_id=None):
    """Use validated accepted artifacts; do not infer relationships from graph similarity."""
    doors = []
    for item in return_paths.inbox(store):
        if item['status'] != 'accepted':
            continue
        source, target = item['source'], item['inquiry']
        common = {'id': item['id'], 'scope': 'native', 'kind': 'claim', 'anchorGraphId': graph_id,
                  'description': 'An explicitly accepted returned path. Enter to mark it visited.'}
        if inquiry_id is None and (source['graph_id'], source['node_id']) == (graph_id, node_id):
            doors.append({**common, 'graphId': target['spawn']['graph_id'], 'nodeId': target['spawn']['node_id'],
                'title': target['title'], 'text': target['author'], 'labelKind': 'accepted contribution',
                'href': target['url'].replace('/#', f'/?arrival={item["id"]}#')})
        if inquiry_id == target['id']:
            doors.append({**common, 'graphId': source['graph_id'], 'nodeId': source['node_id'],
                'title': 'Return to source chamber', 'text': source['author'], 'labelKind': 'source return',
                'returnOrigin': True, 'entry': target['spawn'],
                'href': f'/?doorway={item["id"]}#/g/{source["graph_id"]}/n/{source["node_id"]}'})
    return doors
