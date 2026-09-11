"""Synthetic two-party snapshots; no user store, network provider or live memory."""
import copy
import json
import threading
from dataclasses import replace

import pytest

from thought_archaeology import agent_spark as spark, portable
from thought_archaeology.continuation import continuation_request, continuation_completion
from thought_archaeology.ids import new_ulid
from thought_archaeology.models import SCHEMA_VERSION
from thought_archaeology.schema import ValidationError
from thought_archaeology.serve import make_server, viz_dist_path
from thought_archaeology.store import Store, StoreError
from tests.test_cli import run
from tests.test_serve import _compile_simple, _get, _post
from tests.test_agent_spark import setup as guide_setup, wait


def files(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


@pytest.fixture
def inquiry(tmp_path):
    sid, gid = _compile_simple(tmp_path/'publisher')
    store = Store(tmp_path/'publisher'); graph = store.load_graph(gid)
    child = replace(graph, id=new_ulid(), turn_id=new_ulid(), parent_graph_id=gid,
                    hidden_reasoning='SYNTHETIC PRIVATE REASONING',
                    metadata={'private_note':'SYNTHETIC PRIVATE METADATA'})
    store.write_graph(child)
    request = continuation_request(graph, graph.nodes[0], prompt='What would change this conclusion?', source='inhabit_space')
    store.write_continuation_request(request)
    store.write_continuation_completion(continuation_completion(request.id, child.id, 'synthetic-agent'))
    for ref in ('https://example.org/synthetic-evidence', 'file:///private/synthetic.txt'):
        store.write_evidence(sid, {'schema_version':SCHEMA_VERSION, 'id':new_ulid(), 'graph_id':gid,
            'node_id':graph.nodes[0].id, 'kind':'context_provenance', 'result':'supports',
            'summary':'Synthetic evidence', 'artifact_refs':[ref], 'created_at':graph.created_at})
    (store.root/'guide-discussions').mkdir()
    (store.root/'guide-discussions/private.json').write_text('SYNTHETIC PRIVATE DISCUSSION')
    bundle=portable.export_inquiry(store,sid,author='Synthetic publisher',description='Two generations for acceptance testing.')
    return store,bundle


def test_projection_is_reviewable_deterministic_and_private(inquiry):
    source,bundle=inquiry; before=files(source.root)
    assert portable.export_inquiry(source,bundle['content']['session']['id'],author='Synthetic publisher',description=bundle['content']['description']) == bundle
    assert files(source.root) == before
    text=json.dumps(bundle)
    assert 'SYNTHETIC PRIVATE' not in text and 'file:///' not in text
    assert bundle['content']['omitted_evidence_count'] == 1
    assert len(bundle['content']['evidence']) == 1
    child=bundle['content']['graphs'][1]
    assert child['source']['question'] == 'What would change this conclusion?'
    assert child['source_sha256'] == source.graph_sha256(child['graph']['id'])
    assert child['source_sha256'] != child['shared_sha256']
    assert portable.arrivals(bundle,child['source']['graph_id'])[0]['graphId'] == child['graph']['id']


def test_import_keeps_local_identity_collisions_separate_and_is_idempotent(inquiry,tmp_path):
    source,bundle=inquiry
    # A recipient may already possess these exact session/graph identities.
    import shutil
    shutil.copytree(source.root,tmp_path/'recipient')
    target=Store(tmp_path/'recipient');before=files(target.root)
    result=portable.import_inquiry(target,bundle)
    assert not result['already_imported']
    assert all((target.root/p).read_bytes()==data for p,data in before.items())
    imported_bundle, imported=portable.imported_inquiry(target,bundle['id'])
    assert imported_bundle == bundle
    assert imported.validate_session(result['session_id']) == []
    imported_before=files(imported.root)
    assert portable.import_inquiry(target,bundle)['already_imported']
    assert files(imported.root)==imported_before
    assert len(portable.list_inquiries(target))==1


@pytest.mark.parametrize('damage', ['checksum','graph_checksum','external_parent','cycle','source_node','hidden','unknown','metadata','duplicate','fork','evidence_url','nonfinite'])
def test_invalid_import_has_no_store_side_effects(inquiry,tmp_path,damage):
    _,original=inquiry;bundle=copy.deepcopy(original);records=bundle['content']['graphs'];graph=records[0]['graph']
    if damage=='checksum': bundle['id']='0'*64
    elif damage=='graph_checksum': graph['prose']='Changed'
    elif damage=='external_parent': graph['parent_graph_id']=new_ulid()
    elif damage=='cycle': graph['parent_graph_id']=records[1]['graph']['id']
    elif damage=='source_node': records[1]['source']['node_id']=new_ulid()
    elif damage=='hidden': graph['hidden_reasoning']='Unshared'
    elif damage=='unknown': bundle['version']=999
    elif damage=='metadata': graph['metadata']={'secret':'private'}
    elif damage=='duplicate': records.append(copy.deepcopy(records[0]))
    elif damage=='fork': graph['fork']={'from_graph_id':new_ulid(),'from_node_id':new_ulid()}
    elif damage=='evidence_url': bundle['content']['evidence'][0]['artifact_refs']=['javascript:alert(1)']
    elif damage=='nonfinite': graph['metadata']={'workspace_origin':float('nan')}
    if damage not in {'checksum','nonfinite'}:
        if damage!='graph_checksum':
            for record in records: record['shared_sha256']=portable.digest(record['graph'])
        bundle['id']=portable.digest(bundle['content'])
    recipient=Store(tmp_path/'recipient');recipient.initialize();before=files(recipient.root)
    with pytest.raises((StoreError,ValidationError)):
        portable.import_inquiry(recipient,bundle)
    assert files(recipient.root)==before


def test_failed_materialization_is_atomic(inquiry,tmp_path,monkeypatch):
    _,bundle=inquiry;target=Store(tmp_path/'recipient');target.initialize()
    monkeypatch.setattr(Store,'validate_session',lambda *a:['synthetic failure'])
    with pytest.raises(StoreError,match='synthetic failure'): portable.import_inquiry(target,bundle)
    assert list((target.root/'imported-inquiries').iterdir())==[]


def test_http_visit_is_read_only_and_guide_keeps_exact_private_source(inquiry,tmp_path,monkeypatch):
    _,bundle=inquiry;target,_,_=guide_setup(tmp_path/'guide',monkeypatch)
    calls=[]
    def respond(spec,operation,payload,**kw):
        calls.append(payload)
        return {'response':'Synthetic visitor discussion.','model_name':'synthetic-guide-model'}
    monkeypatch.setattr(spark,'_adapter_call',respond)
    before=files(target.root)
    server=make_server(target,port=0,dist=viz_dist_path())
    threading.Thread(target=server.serve_forever,daemon=True).start()
    base=f'http://127.0.0.1:{server.server_port}'
    try:
        assert _post(base+'/api/inquiries/inspect',bundle)[0]==200
        assert files(target.root)==before and not calls
        status,body=_post(base+'/api/inquiries/import',bundle);assert status==200,body
        info=json.loads(body);prefix=f'/api/inquiries/{info["id"]}'
        assert 'window.TA_INQUIRY_ID' in _get(base+info['url'].split('#')[0])[1]
        _,imported=portable.imported_inquiry(target,info['id']);imported_before=files(imported.root)
        thread=json.loads(_get(base+prefix+'/thread/'+info['session_id'])[1])
        assert thread['latest_ai_graph_id']==bundle['content']['graphs'][1]['graph']['id']
        for record in bundle['content']['graphs']:
            graph=record['graph'];node=graph['nodes'][0]
            code,text,_=_get(base+prefix+f'/inhabit/{node["id"]}?graph={graph["id"]}')
            assert code==200,text
            assert json.loads(text)['shared_inquiry']['id']==bundle['id']
        assert _get(base+prefix+'/graphs/'+new_ulid())[0]==404
        for action in ('fork','veto','continuation/ready','workspace/new','guide/roles','harness/use'):
            assert _post(base+prefix+'/'+action,{})[0]==403
        assert not calls
        graph=bundle['content']['graphs'][1]['graph']
        body={'request_id':'synthetic-visitor','prompt':'Discuss this shared thought.', 'graph_id':graph['id'],'node_id':graph['nodes'][0]['id']}
        code,text=_post(base+prefix+'/guide/discuss',body);assert code==202,text
        local=Store(target.root/'inquiry-discussions'/bundle['id']);result=wait(local)
        source=result['turns'][0]['source']
        assert source['graph_id']==graph['id']
        assert source['inquiry']['source_sha256']==bundle['content']['graphs'][1]['source_sha256']
        assert calls[0]['standing']['shared_inquiry']==source['inquiry']
        assert files(imported.root)==imported_before
        assert all((target.root/p).read_bytes()==data for p,data in before.items())
        assert spark.discussion_payload(target)['turns']==[]
    finally:
        server.shutdown();server.server_close()


def test_cli_export_inspect_import(inquiry,tmp_path):
    source,bundle=inquiry;path=tmp_path/'test.atlas-inquiry.json'
    code,out,err=run(['inquiry','export','--session',bundle['content']['session']['id'],'--author','Synthetic CLI','--output',str(path)],store=source.root)
    assert code==0,err
    assert run(['inquiry','export','--session',bundle['content']['session']['id'],'--author','Synthetic CLI','--output',str(path)],store=source.root)[0]!=0
    assert run(['inquiry','inspect',str(path)],store=source.root)[0]==0
    recipient=Store(tmp_path/'recipient');recipient.initialize()
    code,out,err=run(['inquiry','import',str(path)],store=recipient.root);assert code==0,err
    assert json.loads(out)['title']==bundle['content']['session']['title']


def test_browser_export_and_downloaded_fixture_keep_exact_numeric_checksums(inquiry, tmp_path):
    from pathlib import Path
    from urllib.request import Request, urlopen
    source, bundle = inquiry
    server = make_server(source, port=0, dist=viz_dist_path())
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        code, text = _post(base+'/api/inquiries/preview', {
            'session_id':bundle['content']['session']['id'], 'author':'Synthetic publisher'})
        assert code == 200
        preview = json.loads(text)
        portable.validate_bundle(json.loads(preview['inquiry_json']))
        assert preview['inquiry_json'].encode() == portable.canonical(preview['bundle'])
        fixture = Path(__file__).parents[1] / 'online/test/fixtures/1.json'
        raw = json.loads(fixture.read_text())['inquiry_json']
        original = json.loads(raw)
        portable.validate_bundle(original)
        before = files(source.root)
        for action in ('inspect', 'import'):
            request = Request(base+'/api/inquiries/'+action, data=raw.encode(),
                              headers={'Content-Type':'application/json','Origin':base})
            with urlopen(request) as response:
                result = json.load(response)
            assert result['id'] == original['id']
            if action == 'inspect':
                assert files(source.root) == before
        stored, _ = portable.imported_inquiry(source, original['id'])
        assert portable.canonical(stored) == raw.encode()
        assert all((source.root/p).read_bytes() == content for p,content in before.items())
    finally:
        server.shutdown(); server.server_close()
