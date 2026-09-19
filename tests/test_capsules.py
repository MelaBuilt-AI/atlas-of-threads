"""Synthetic, offline Capsule exchanges over the canonical local store/worker."""
import copy
import hashlib
import json
import stat
import threading
from pathlib import Path

import pytest
from thought_archaeology import capsules, portable
from thought_archaeology.harness import HarnessRegistry, continuation_envelope, process_continuation
from thought_archaeology.knowledge_capsules import construct_knowledge_capsule, launch_knowledge_capsule
from thought_archaeology.schema import ValidationError
from thought_archaeology.serve import make_server, viz_dist_path
from thought_archaeology.store import Store, StoreError
from tests.test_harness import _register
from tests.test_knowledge_capsules import _capsule_study
from tests.test_portable import inquiry, files
from tests.test_serve import _get, _post, _compile_simple


def draft_for(bundle, **changes):
    graph = bundle['content']['graphs'][0]['graph']
    return dict(intent='invitation', title='Synthetic evidence invitation', author='Synthetic author',
                message='What evidence would change this selected claim?', interpretation='A synthetic human interpretation.',
                session_id=bundle['content']['session']['id'], reply_to=None,
                selections=[{'graph_id':graph['id'],'node_ids':[graph['nodes'][0]['id']],
                             'include_answer':False,'include_question':False,
                             'evidence_ids':[e['id'] for e in bundle['content']['evidence'] if e['node_id']==graph['nodes'][0]['id']]}]) | changes


def saved_capsule(inquiry):
    source, bundle = inquiry
    draft = draft_for(bundle)
    capsule = capsules.prepare(source,draft)
    capsules.freeze(source,draft,capsule)
    return source, draft, capsule


def test_exact_selection_excludes_unselected_content_and_freezes_once(inquiry):
    source,bundle=inquiry
    draft=draft_for(bundle);before=files(source.root)
    capsule=capsules.prepare(source,draft)
    assert files(source.root)==before
    c=capsule['content'];assert len(c['excerpts'])==1
    excerpt=c['excerpts'][0]
    assert len(excerpt['thoughts'])==1 and excerpt['answer'] is None and excerpt['question'] is None
    assert len(excerpt['evidence'])==1
    assert excerpt['source']['source_sha256']==source.graph_sha256(excerpt['source']['graph_id'])
    text=json.dumps(capsule)
    assert 'SYNTHETIC PRIVATE' not in text and 'file:///' not in text
    assert bundle['content']['graphs'][1]['graph']['id'] not in text
    assert capsules.prepare(source,draft,created_at=c['created_at'])==capsule
    assert not capsules.freeze(source,draft,capsule)['already_saved']
    path=capsules._path(source,'prepared',capsule['id'])
    assert stat.S_IMODE(path.stat().st_mode)==0o600
    assert capsules.freeze(source,draft,capsule)['already_saved']
    assert all((source.root/p).read_bytes()==data for p,data in before.items())
    assert len(capsules.library(source)['prepared'])==1


def test_optional_source_question_and_full_answer_are_explicit(inquiry):
    source,bundle=inquiry;child=bundle['content']['graphs'][1]
    draft=draft_for(bundle,selections=[{'graph_id':child['graph']['id'],'node_ids':[child['graph']['nodes'][0]['id']],
                                     'include_answer':True,'include_question':True,'evidence_ids':[]}])
    capsule=capsules.prepare(source,draft);excerpt=capsule['content']['excerpts'][0]
    assert excerpt['answer']==child['graph']['prose']
    assert excerpt['question']==child['source']
    assert 'SYNTHETIC PRIVATE' not in json.dumps(capsule)


def test_stale_or_tampered_local_review_is_rejected(inquiry):
    source,bundle=inquiry;draft=draft_for(bundle);capsule=capsules.prepare(source,draft)
    before=files(source.root)
    changed=copy.deepcopy(draft);changed['selections'][0]['include_answer']=True
    with pytest.raises(StoreError,match='review'):capsules.freeze(source,changed,capsule)
    forged=copy.deepcopy(capsule);forged['content']['excerpts'][0]['thoughts'][0]['text']='Unreviewed substitute'
    forged['id']=portable.digest(forged['content'])
    with pytest.raises(StoreError,match='review'):capsules.freeze(source,draft,forged)
    assert files(source.root)==before


@pytest.mark.parametrize('damage',['checksum','format','unknown','private','evidence','duplicate','return','source','too_large','nan'])
def test_bad_incoming_capsules_have_no_side_effects(inquiry,tmp_path,damage):
    _,_,original=saved_capsule(inquiry);capsule=copy.deepcopy(original);c=capsule['content']
    if damage=='checksum':capsule['id']='0'*64
    elif damage=='format':capsule['format']='atlas-inquiry'
    elif damage=='unknown':c['credential']='forbidden'
    elif damage=='private':c['excerpts'][0]['thoughts'][0]['sensor_ids']=[]
    elif damage=='evidence':c['excerpts'][0]['evidence'][0]['artifact_refs']=['file:///private/source']
    elif damage=='duplicate':c['excerpts'].append(copy.deepcopy(c['excerpts'][0]))
    elif damage=='return':c['intent']='return'
    elif damage=='source':c['excerpts'][0]['source']['origin_id']='00000000000000000000000000'
    elif damage=='too_large':c['excerpts'][0]['answer']='x'*(capsules.MAX_BYTES+1)
    elif damage=='nan':c['excerpts'][0]['thoughts'][0]['confidence']=float('nan')
    if damage not in {'checksum','nan'}:capsule['id']=portable.digest(c)
    target=Store(tmp_path/'receiver');target.initialize();before=files(target.root)
    with pytest.raises((StoreError,ValidationError)):capsules.receive(target,capsule)
    assert files(target.root)==before


def test_export_receipts_are_retryable_and_never_launch_legacy_capsules(inquiry,monkeypatch):
    source,_,capsule=saved_capsule(inquiry)
    original=capsules._write_private_atomic
    def fail_markdown(path,data):
        if path.suffix=='.md':raise OSError('synthetic interrupted export')
        original(path,data)
    with monkeypatch.context() as m:
        m.setattr(capsules,'_write_private_atomic',fail_markdown)
        with pytest.raises(OSError):capsules.export_files(source,capsule['id'])
    assert not capsules._path(source,'exports',capsule['id']).exists()
    result=capsules.export_files(source,capsule['id'])
    before=files(source.root)
    assert capsules.export_files(source,capsule['id'])==result
    assert files(source.root)==before
    assert Path(result['json_path']).read_bytes()==portable.canonical(capsule)
    assert capsule['id'] in Path(result['markdown_path']).read_text()
    receipt=json.loads(capsules._path(source,'exports',capsule['id']).read_text())
    assert receipt['json_sha256']==hashlib.sha256(Path(result['json_path']).read_bytes()).hexdigest()
    assert not list(source.iter_knowledge_capsules())
    assert not list(source.iter_knowledge_capsule_launchers())


def test_offline_round_trip_private_worker_and_return_preserve_source(inquiry,tmp_path,monkeypatch):
    source,draft,capsule=saved_capsule(inquiry);before_source=files(source.root)
    target=Store(tmp_path/'receiver');_compile_simple(target.root);before_sessions=files(target.sessions_dir)
    _register(monkeypatch,tmp_path,target.root)
    assert not capsules.receive(target,capsule)['already_saved']
    assert capsules.receive(target,capsule)['already_saved']
    assert portable.list_inquiries(target)==[]
    assert list(target.iter_continuation_requests())==[]
    received_before=files(target.root/'capsules'/'received')
    reviewed=capsules.work_preview(target,capsule['id'],'How can I test this selected claim?', [0])
    start=capsules.begin_work(target,reviewed)
    request=target.load_continuation_request(start['request_id'])
    envelope=continuation_envelope(target,request)
    assert envelope['graph']['metadata']['external_capsule']==reviewed['context']
    registry=HarnessRegistry()
    result=process_continuation(target,registry.get(),request_id=start['request_id'],registry=registry)
    assert result['status']=='completed',result
    assert target.validate_session(start['session_id'])==[]
    assert all((target.sessions_dir/p).read_bytes()==data for p,data in before_sessions.items())
    assert files(target.root/'capsules'/'received')==received_before
    graph=target.load_graph(target.load_session(start['session_id']).head_graph_id)
    reply_draft=draft_for(inquiry[1],intent='return',title='Synthetic return',author='Synthetic recipient',
                        session_id=start['session_id'],reply_to={'kind':'capsule','id':capsule['id']},
                        selections=[{'graph_id':graph.id,'node_ids':[graph.nodes[0].id],'evidence_ids':[]}])
    reply=capsules.prepare(target,reply_draft);capsules.freeze(target,reply_draft,reply)
    assert reply['content']['reply_to']=={'kind':'capsule','id':capsule['id'],'origin_id':capsule['content']['origin_id']}
    assert 'external_capsule' not in json.dumps(reply)
    capsules.receive(source,reply)
    assert len(capsules.library(source)['received'])==1
    assert all((source.root/p).read_bytes()==data for p,data in before_source.items())
    assert not list(source.iter_continuation_requests(pending=True))
    unrelated=Store(tmp_path/'unrelated');unrelated.initialize();before=files(unrelated.root)
    with pytest.raises(StoreError):capsules.receive(unrelated,reply)
    assert files(unrelated.root)==before


def test_return_to_offline_imported_inquiry_requires_exact_source(inquiry,tmp_path):
    source,bundle=inquiry;target=Store(tmp_path/'receiver');target.initialize();portable.import_inquiry(target,bundle)
    graph=bundle['content']['graphs'][0]['graph']
    reply={'kind':'inquiry','inquiry_id':bundle['id'],'graph_id':graph['id'],'node_id':graph['nodes'][0]['id']}
    draft=draft_for(bundle,intent='return',session_id=None,selections=[],reply_to=reply)
    capsule=capsules.prepare(target,draft)
    assert capsules.inspect_incoming(source,capsule)['reply_to']['source']['inquiry_id']==bundle['id']
    capsules.receive(source,capsule)
    forged=copy.deepcopy(capsule);forged['content']['reply_to']['source']['source_sha256']='0'*64;forged['id']=portable.digest(forged['content'])
    with pytest.raises(StoreError,match='exact source'):capsules.inspect_incoming(source,forged)
    with pytest.raises(StoreError):capsules.prepare(source,draft)


def test_new_message_capsules_do_not_need_earned_legacy_launcher(tmp_path):
    store=Store(tmp_path/'empty');store.initialize()
    draft={'intent':'invitation','title':'New question','author':'Synthetic human','message':'What should we explore?',
           'interpretation':'','session_id':None,'selections':[],'reply_to':None}
    capsule=capsules.prepare(store,draft);capsules.freeze(store,draft,capsule)
    assert capsule['content']['excerpts']==[]
    assert not list(store.iter_knowledge_capsules())


def test_legacy_capsule_manifests_receipts_and_dossiers_remain_unchanged(tmp_path):
    store,_,request,comparison,_,_= _capsule_study(tmp_path/'legacy')
    manifest=construct_knowledge_capsule(store,comparison_request_id=request)
    launch_knowledge_capsule(store,manifest.id)
    before=files(store.root)
    draft={'intent':'offering','title':'New offering','author':'Synthetic human','message':'A selected finding.',
           'interpretation':'','session_id':comparison['session_id'],'selections':[],'reply_to':None}
    capsule=capsules.prepare(store,draft);capsules.freeze(store,draft,capsule);capsules.export_files(store,capsule['id'])
    assert capsules.library(store)['legacy'][0]['id']==manifest.id
    assert all((store.root/p).read_bytes()==data for p,data in before.items())


def test_http_review_gates_download_and_foreign_origin(inquiry,tmp_path):
    store,bundle=inquiry;server=make_server(store,port=0,dist=viz_dist_path())
    threading.Thread(target=server.serve_forever,daemon=True).start();base=f'http://127.0.0.1:{server.server_port}'
    try:
        draft=draft_for(bundle);code,text=_post(base+'/api/capsules/prepare',draft);assert code==200,text
        capsule=json.loads(text)['capsule']
        body={'draft':draft,'capsule':capsule,'destination':'file'}
        assert _post(base+'/api/capsules/freeze',body)[0]==404
        code,text=_post(base+'/api/capsules/freeze',{**body,'reviewed':True});assert code==200,text
        assert json.loads(_get(base+f'/api/capsules/download/{capsule["id"]}/json')[1])==capsule
        assert capsule['content']['message'] in _get(base+f'/api/capsules/download/{capsule["id"]}/markdown')[1]
        from urllib.request import Request,urlopen
        from urllib.error import HTTPError
        request=Request(base+'/api/capsules/receive',json.dumps({'capsule':capsule,'reviewed':True}).encode(),headers={'Content-Type':'application/json','Origin':'https://foreign.example'})
        with pytest.raises(HTTPError):urlopen(request)
        assert capsules.library(store)['received']==[]
        assert _post(base+'/api/capsules/receive',{'capsule':capsule})[0]==404
    finally:server.shutdown();server.server_close()


def test_http_canonical_capsule_text_survives_browser_freeze_and_receive(inquiry):
    from urllib.request import Request, urlopen
    store, bundle = inquiry
    server = make_server(store, port=0, dist=viz_dist_path())
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        draft = draft_for(bundle)
        code, text = _post(base+'/api/capsules/prepare', draft)
        assert code == 200
        prepared = json.loads(text)
        canonical = prepared['capsule_json']
        assert canonical == portable.canonical(prepared['capsule']).decode()
        body = {'draft':draft, 'capsule':canonical, 'destination':'file', 'reviewed':True}
        code, text = _post(base+'/api/capsules/freeze', body)
        assert code == 200, text
        cid = prepared['capsule']['id']
        assert _get(base+f'/api/capsules/download/{cid}/json')[1] == canonical
        request = Request(base+'/api/capsules/inspect', canonical.encode(),
                          headers={'Content-Type':'application/json','Origin':base})
        with urlopen(request) as response:
            assert response.status == 200
        assert capsules.library(store)['received'] == []
        code, text = _post(base+'/api/capsules/receive', {'capsule':canonical,'reviewed':True})
        assert code == 200, text
        assert portable.canonical(capsules.load(store,'received',cid)).decode() == canonical
        forged = canonical.replace('Synthetic author', 'Forged author')
        assert _post(base+'/api/capsules/receive', {'capsule':forged,'reviewed':True})[0] != 200
    finally:
        server.shutdown(); server.server_close()
