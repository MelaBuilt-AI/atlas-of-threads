"""Prepare reviewed online snapshots using the canonical local renderer semantics.

This module does not contact a server, invoke a collaborator or read a live store.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from thought_archaeology import portable
from thought_archaeology.store import Store, StoreError

MAX_PUBLICATION_BYTES = 8 * 1024 * 1024


def prepare_publication(bundle: dict) -> dict:
    from thought_archaeology.serve import bootstrap_payload, thread_payload, inhabit_payload

    portable.validate_bundle(bundle)
    with tempfile.TemporaryDirectory(prefix="atlas-publication-") as directory:
        staging = Store(Path(directory))
        staging.initialize()
        info = portable.import_inquiry(staging, bundle)
        _, imported = portable.imported_inquiry(staging, bundle['id'])
        player = {'sessions': bootstrap_payload(imported), 'threads': {}, 'inhabit': {}}
        for record in bundle['content']['graphs']:
            graph = record['graph']
            thread = thread_payload(imported, info['session_id'], graph_id=graph['id'])
            records = {r['graph']['id']: r for r in bundle['content']['graphs']}
            for entry in thread['entries']:
                source = records[entry['graph_id']]['source']
                if source:
                    entry.update(kind='continuation', label=source['author'], prompt=source['question'],
                                 source_graph_id=source['graph_id'], source_node_id=source['node_id'])
            continued = [entry for entry in thread['entries'] if entry['kind'] == 'continuation']
            thread['latest_ai_graph_id'] = max(continued, key=lambda entry: (entry['created_at'], entry['graph_id']))['graph_id'] if continued else None
            player['threads'][graph['id']] = thread
            for node in graph['nodes']:
                payload = inhabit_payload(imported, node['id'], graph_id=graph['id'])
                payload.update(parallel_available=False, field_note_eligibility=None,
                               knowledge_capsule_eligibility=None, stored_knowledge_capsule_launcher=None,
                               shared_arrivals=portable.arrivals(bundle, graph['id']))
                payload['read']['traversal']['continuation_line'] = 'Published inquiry · download to continue privately in your Personal Atlas'
                source = record['source']
                if source:
                    parent = records[source['graph_id']]['graph']
                    parent_node = next(n for n in parent['nodes'] if n['id'] == source['node_id'])
                    payload['continuation_harness'] = source['author']
                    payload['continuation_source'] = {'session_id': info['session_id'], 'graph_id': parent['id'],
                        'node_id': parent_node['id'], 'node': {k: parent_node[k] for k in ('id','kind','text','status','agent')},
                        'title': info['title'], 'model': parent['model'], 'prompt': source['question'], 'harness': source['author']}
                player['inhabit'][graph['id'] + ':' + node['id']] = payload
        # Strings retain Python's exact canonical numeric representation across JS clients.
        artifact = {'format': 'atlas-publication', 'version': 1,
                    'inquiry_json': portable.canonical(bundle).decode('utf-8'),
                    'player_json': portable.canonical(player).decode('utf-8')}
        if len(portable.canonical(artifact)) > MAX_PUBLICATION_BYTES:
            raise StoreError('Online preview supports publication files up to 8 MiB; this inquiry remains portable locally')
        return artifact


def main() -> None:
    parser = argparse.ArgumentParser(description='Prepare a reviewed inquiry for the online Atlas; sends nothing.')
    parser.add_argument('inquiry', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    artifact = prepare_publication(portable.read_bundle(args.inquiry))
    with args.output.open('x', encoding='utf-8') as stream:
        args.output.chmod(0o600)
        stream.write(portable.canonical(artifact).decode('utf-8'))


if __name__ == '__main__':
    main()
