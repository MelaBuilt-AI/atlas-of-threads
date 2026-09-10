"""Online preparation is deterministic and reads only a reviewed portable bundle."""
import json
from thought_archaeology.online import prepare_publication
from tests.test_portable import inquiry, files


def test_online_projection_preserves_sources_and_no_local_data(inquiry):
    store, bundle = inquiry
    before = files(store.root)
    prepared = prepare_publication(bundle)
    assert files(store.root) == before
    assert prepare_publication(bundle) == prepared
    assert json.loads(prepared['inquiry_json']) == bundle
    text = json.dumps(prepared)
    assert 'SYNTHETIC PRIVATE' not in text
    assert 'file:///' not in text
    player = json.loads(prepared['player_json'])
    assert set(player['threads']) == {r['graph']['id'] for r in bundle['content']['graphs']}
    assert all(t['latest_ai_graph_id'] == bundle['content']['graphs'][1]['graph']['id'] for t in player['threads'].values())
    for record in bundle['content']['graphs']:
        graph = record['graph']
        for node in graph['nodes']:
            view = player['inhabit'][graph['id']+':'+node['id']]
            assert view['node']['text'] == node['text']
            assert view['parallel_available'] is False
            assert view['knowledge_capsule_eligibility'] is None
