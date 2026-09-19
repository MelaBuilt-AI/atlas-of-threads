// Synthetic accounts and excerpts only; real local D1 exercises delivery transactions.
import {test,before,after} from 'node:test';
import assert from 'node:assert/strict';
import {readFile,readdir} from 'node:fs/promises';
import {Miniflare} from 'miniflare';
import {sha,canonical} from '../src/publication.js';
import {inspectCapsule} from '../src/capsules.js';
let mf,db;
const req=(path,data,owner='a')=>mf.dispatchFetch('http://localhost:7490'+path,{method:data===undefined?'GET':'POST',headers:{'Content-Type':'application/json',...(owner?{Authorization:'Bearer synthetic-'+owner}:{Origin:'http://localhost:7490'})},...(data===undefined?{}:{body:JSON.stringify(data)})});
const ok=async response=>{assert.equal(response.status,200,await response.clone().text());return response.json();};
const artifact=JSON.parse(await readFile('test/fixtures/1.json','utf8')), bundle=JSON.parse(artifact.inquiry_json);
async function capsule(changes={}) {
 const content={origin_id:'01AAAAAAAAAAAAAAAAAAAAAAA1',home_session_id:null,created_at:'2026-09-10T12:00:00Z',intent:'invitation',title:'Synthetic invitation',author:'Unverified sharing name',message:'What changes this claim?',interpretation:'',reply_to:null,excerpts:[],...changes};
 return {format:'atlas-capsule',version:1,id:await sha(canonical(content)),content};
}
const directed=(id='b')=>({audience:'directed',recipient_id:id});
async function reviewed(c,d,owner='a') {return (await ok(await req('/api/capsules/review',{capsule_json:canonical(c),destination:d},owner))).review;}
async function send(c,d,owner='a') {const review=await reviewed(c,d,owner);return ok(await req('/api/capsules/send',{review,reviewed:true},owner));}
before(async()=>{
 mf=new Miniflare({modules:true,scriptPath:'dist/worker.js',compatibilityDate:'2026-05-15',d1Databases:['DB'],r2Buckets:['INQUIRIES'],bindings:{SITE_ORIGIN:'http://localhost:7490'}});db=await mf.getD1Database('DB');
 for(const f of (await readdir('migrations')).filter(f=>f.endsWith('.sql')).sort())for(const sql of (await readFile('migrations/'+f,'utf8')).split(';').map(s=>s.trim()).filter(Boolean))await db.prepare(sql).run();
 for(const id of ['a','b','c']) {await db.prepare("INSERT INTO owners(id,login,kind,created_at) VALUES(?,?,'synthetic',1)").bind(id,'synthetic-'+id).run();await db.prepare('INSERT INTO instances VALUES(?,?,?,?,1,NULL)').bind(id,id,id,await sha('synthetic-'+id)).run();}
});
after(async()=>mf?.dispose());
test('reject malformed, tampered, unreviewed and anonymous deliveries before writes',async()=>{
 const c=await capsule();await inspectCapsule(canonical(c));
 await assert.rejects(()=>inspectCapsule(canonical({...c,id:'0'.repeat(64)})),/checksum/);
 await assert.rejects(()=>inspectCapsule(canonical(awaitCapsuleBad(c))),/schema/);
 assert.equal((await req('/api/capsules/review',{capsule_json:canonical(c),destination:directed()},null)).status,401);
 assert.equal((await req('/api/capsules/send',{review:await reviewed(c,directed())})).status,400);
 assert.equal((await db.prepare('SELECT count(*) n FROM capsule_deliveries').first()).n,0);
});
function awaitCapsuleBad(c){return {...c,content:{...c.content,secret:'unsupported'}};}
test('directed launch pins verified account independently of sharing name, one audience and one launch under retries',async()=>{
 const c=await capsule(), review=await reviewed(c,{audience:'directed',recipient_login:'synthetic-b'});
 assert.equal(review.recipient.id,'b');assert.equal(review.recipient.verified,false);
 const results=await Promise.all([req('/api/capsules/send',{review,reviewed:true}),req('/api/capsules/send',{review,reviewed:true})]);
 const [a,b]=await Promise.all(results.map(ok));assert.equal(a.id,b.id);
 assert.equal((await db.prepare('SELECT count(*) n FROM capsule_deliveries').first()).n,1);
 const changed=await reviewed(c,directed('c'));assert.equal((await req('/api/capsules/send',{review:changed,reviewed:true})).status,409);
 assert.equal((await req('/api/capsules/'+a.id,undefined,'c')).status,404);
 assert.equal((await req('/api/capsules/'+a.id,undefined,null)).status,401);
 const inbox=await ok(await req('/api/capsules',undefined,'b'));assert.equal(inbox.deliveries.length,1);assert.equal(inbox.deliveries[0].received_at,null);
 await ok(await req('/api/capsules/'+a.id,undefined,'b'));
 assert.equal((await db.prepare('SELECT count(*) n FROM capsule_receipts').first()).n,0);
 const receipt=await ok(await req('/api/capsules/'+a.id+'/receive',{reviewed:true},'b'));
 assert.deepEqual(await ok(await req('/api/capsules/'+a.id+'/receive',{reviewed:true},'b')),receipt);
 assert.equal((await ok(await req('/api/capsules?view=sent'))).deliveries[0].received_at,receipt.received_at);
});
test('A → B → A return is inert until exact-source review and immutable explicit source-owner decision',async()=>{
 const original=await capsule(), launch=await send(original,directed());
 const returned=await capsule({origin_id:'01AAAAAAAAAAAAAAAAAAAAAAA2',intent:'return',title:'Synthetic return',reply_to:{kind:'capsule',id:original.id,origin_id:original.content.origin_id}});
 const dest={...directed('a'),reply_delivery_id:launch.id};
 assert.equal((await req('/api/capsules/review',{capsule_json:canonical(returned),destination:{...dest,recipient_id:'c'}},'b')).status,400);
 const back=await send(returned,dest,'b'), detail=await ok(await req('/api/capsules/'+back.id));
 assert.equal(JSON.parse(detail.source.capsule_json).id,original.id);
 const decision={reviewed:true,capsule_id:returned.id,source:detail.source,decision:'accepted'};
 assert.equal((await req('/api/capsules/'+back.id+'/decide',decision)).status,400);
 await ok(await req('/api/capsules/'+back.id+'/receive',{reviewed:true}));
 assert.equal((await req('/api/capsules/'+back.id+'/decide',{...decision,source:null})).status,400);
 assert.equal((await req('/api/capsules/'+back.id+'/decide',decision,'b')).status,400);
 const accepted=await ok(await req('/api/capsules/'+back.id+'/decide',decision));assert.equal(accepted.decision,'accepted');
 assert.deepEqual(await ok(await req('/api/capsules/'+back.id+'/decide',decision)),accepted);
 assert.equal((await req('/api/capsules/'+back.id+'/decide',{...decision,decision:'declined'})).status,409);
 assert.equal((await ok(await req('/api/capsules/'+back.id,undefined,'b'))).decision,'accepted');
});
test('published exact chamber returns require snapshot, source/shared hashes and selected node',async()=>{
 const published=await req('/api/publications',{artifact,reviewed:true});assert.equal(published.status,201,await published.clone().text());const {id}=await published.json();
 const g=bundle.content.graphs[0], source={inquiry_id:bundle.id,origin_id:bundle.content.origin_id,session_id:bundle.content.session.id,graph_id:g.graph.id,node_id:g.graph.nodes[0].id,source_sha256:g.source_sha256,shared_sha256:g.shared_sha256,author:bundle.content.author};
 const c=await capsule({intent:'return',title:'Published source return',reply_to:{kind:'inquiry',source}}),dest={...directed('a'),reply_publication_id:id};
 const sent=await send(c,dest,'b');const detail=await ok(await req('/api/capsules/'+sent.id));assert.equal(detail.source.thought.id,source.node_id);
 const bad=await capsule({intent:'return',reply_to:{kind:'inquiry',source:{...source,source_sha256:'0'.repeat(64)}}});
 assert.equal((await req('/api/capsules/review',{capsule_json:canonical(bad),destination:dest},'b')).status,400);
});
test('open offerings require owned matching publication; strangers may deliberately receive, but cannot forge a return source',async()=>{
 const p=await db.prepare('SELECT id FROM publications LIMIT 1').first();
 const c=await capsule({origin_id:bundle.content.origin_id,home_session_id:bundle.content.session.id,title:'Open synthetic offering',intent:'offering'});
 const destination={audience:'public',source_publication_id:p.id};
 assert.equal((await req('/api/capsules/review',{capsule_json:canonical(c),destination},'b')).status,403);
 const sent=await send(c,destination);
 const open=await ok(await req('/api/capsules?view=public',undefined,'c'));assert.equal(open.deliveries.length,1);assert.equal(open.deliveries[0].id,sent.id);
 await ok(await req('/api/capsules/'+sent.id+'/receive',{reviewed:true},'c'));
 const fake=await capsule({intent:'return',reply_to:{kind:'capsule',id:'0'.repeat(64),origin_id:c.content.origin_id}});
 assert.equal((await req('/api/capsules/review',{capsule_json:canonical(fake),destination:{...directed('a'),reply_delivery_id:sent.id}},'c')).status,400);
});
test('directed destination ownership and accepted-return events remain participant-only and exactly once',async()=>{
 const p=await db.prepare('SELECT id,threadwalk_id FROM publications WHERE owner_id=? LIMIT 1').bind('a').first();
 const published=await req('/api/publications',{artifact,reviewed:true},'b');assert.equal(published.status,201);const q=await published.json();
 const original=await capsule({title:'Port invitation',origin_id:bundle.content.origin_id,home_session_id:bundle.content.session.id});
 const dest={...directed(),source_publication_id:p.id,target_publication_id:q.id};
 assert.equal((await req('/api/capsules/review',{capsule_json:canonical(original),destination:{...dest,target_publication_id:p.id}})).status,400);
 const out=await send(original,dest);
 const r=await capsule({title:'Port return',intent:'return',origin_id:bundle.content.origin_id,home_session_id:bundle.content.session.id,reply_to:{kind:'capsule',id:original.id,origin_id:original.content.origin_id}});
 const back=await send(r,{...directed('a'),source_publication_id:q.id,reply_delivery_id:out.id},'b');
 await ok(await req('/api/threadwalks/'+p.threadwalk_id+'/subscription',{starred:false,following:true},'b'));
 const base=await ok(await req('/api/expeditions',undefined,'a'));
 const detail=await ok(await req('/api/capsules/'+back.id));await ok(await req('/api/capsules/'+back.id+'/receive',{reviewed:true}));
 const decision={reviewed:true,decision:'accepted',capsule_id:r.id,source:detail.source};
 await ok(await req('/api/capsules/'+back.id+'/decide',decision));await ok(await req('/api/capsules/'+back.id+'/decide',decision));
 const events=await ok(await req('/api/expeditions?after='+base.cursor+'&ports='+p.threadwalk_id,undefined,'b'));
 assert.equal(events.events.length,1);assert.equal(events.events[0].kind,'accepted');assert.equal(events.events[0].target.id,p.threadwalk_id);assert.ok(events.ports[0].accepted>=1);
 assert.equal((await ok(await req('/api/expeditions?after='+base.cursor,undefined,'c'))).events.length,0);
 assert.equal((await ok(await req('/api/library',undefined,'b'))).updates[0].kind,'capsule-accepted');
 assert.equal((await db.prepare("SELECT count(*) n FROM expedition_events WHERE delivery_id=? AND kind='accepted'").bind(back.id).first()).n,1);
});
test('expedition stream starts at a watermark, inherits audiences, preserves history and follows real events only',async()=>{
 const p=await db.prepare('SELECT id,threadwalk_id FROM publications LIMIT 1').first();
 const baseline=await ok(await req('/api/expeditions?ports='+p.threadwalk_id,undefined,'c'));
 assert.deepEqual(baseline.events,[]);assert.ok(baseline.cursor>0);
 assert.deepEqual((await ok(await req('/api/expeditions',undefined,null))).events,[]);
 await ok(await req('/api/threadwalks/'+p.threadwalk_id+'/subscription',{starred:false,following:true},'c'));
 const c=await capsule({title:'Visible invitation event',origin_id:bundle.content.origin_id,home_session_id:bundle.content.session.id});
 const launch=await send(c,{audience:'public',source_publication_id:p.id});
 const stream=await ok(await req('/api/expeditions?after='+baseline.cursor+'&ports='+p.threadwalk_id,undefined,'c'));
 assert.equal(stream.events.length,1);assert.equal(stream.events[0].id,launch.id);assert.equal(stream.events[0].source.id,p.threadwalk_id);assert.equal(stream.events[0].target,null);
 assert.ok(stream.ports[0].open>=1);
 await send(c,{audience:'public',source_publication_id:p.id});
 assert.equal((await ok(await req('/api/expeditions?after='+stream.cursor,undefined,'c'))).events.length,0);
 const privateCapsule=await capsule({title:'Private flight',origin_id:bundle.content.origin_id,home_session_id:bundle.content.session.id});
 const hidden=await send(privateCapsule,{...directed(),source_publication_id:p.id});
 assert.equal((await ok(await req('/api/expeditions?after='+stream.cursor,undefined,'c'))).events.length,0);
 assert.equal((await ok(await req('/api/expeditions?after='+stream.cursor,undefined,'b'))).events[0].id,hidden.id);
 const library=await ok(await req('/api/library',undefined,'c'));assert.equal(library.updates.length,1);assert.equal(library.updates[0].delivery_id,launch.id);
 const history=await ok(await req('/api/expeditions/history?threadwalk='+p.threadwalk_id,undefined,'c'));
 assert.ok(history.deliveries.some(d=>d.id===launch.id));assert.ok(!history.deliveries.some(d=>d.id===hidden.id));
 await ok(await req('/api/blocks',{owner_id:'a',blocked:true},'c'));
 assert.equal((await ok(await req('/api/library',undefined,'c'))).updates.length,0);
 assert.equal((await ok(await req('/api/expeditions?ports='+p.threadwalk_id,undefined,'c'))).ports.length,0);
 await ok(await req('/api/blocks',{owner_id:'a',blocked:false},'c'));
 await ok(await req('/api/capsules/'+launch.id+'/withdraw',{reviewed:true}));
 assert.equal((await ok(await req('/api/library',undefined,'c'))).updates.length,0);
 const count=(await db.prepare("SELECT count(*) n FROM expedition_events WHERE delivery_id=?").bind(launch.id).first()).n;assert.equal(count,1);
});
test('withdrawal, blocking, decline and revoked devices preserve inert receipts and prevent further delivery',async()=>{
 const c=await capsule({title:'Withdraw me'}), review=await reviewed(c,directed()), launch=await ok(await req('/api/capsules/send',{review,reviewed:true}));
 await ok(await req('/api/capsules/'+launch.id+'/receive',{reviewed:true},'b'));
 assert.equal((await req('/api/capsules/'+launch.id+'/withdraw',{reviewed:true},'b')).status,403);
 await ok(await req('/api/capsules/'+launch.id+'/withdraw',{reviewed:true}));
 assert.equal((await req('/api/capsules/'+launch.id,undefined,'b')).status,410);
 assert.equal((await ok(await req('/api/capsules/send',{review,reviewed:true}))).reused,true);
 await ok(await req('/api/blocks',{owner_id:'a',blocked:true},'b'));
 assert.equal((await ok(await req('/api/capsules',undefined,'b'))).deliveries.length,0);
 assert.equal((await req('/api/capsules/review',{capsule_json:canonical(await capsule({title:'Blocked'})),destination:directed()})).status,403);
 await ok(await req('/api/blocks',{owner_id:'a',blocked:false},'b'));
 const original=await capsule({title:'Decline source'}), orig=await send(original,directed());
 const ret=await capsule({title:'Decline return',intent:'return',reply_to:{kind:'capsule',id:original.id,origin_id:original.content.origin_id}});
 const back=await send(ret,{...directed('a'),reply_delivery_id:orig.id},'b'), detail=await ok(await req('/api/capsules/'+back.id));
 await ok(await req('/api/capsules/'+back.id+'/receive',{reviewed:true}));
 assert.equal((await ok(await req('/api/capsules/'+back.id+'/decide',{reviewed:true,capsule_id:ret.id,source:detail.source,decision:'declined'}))).decision,'declined');
 await db.prepare('UPDATE instances SET revoked_at=1 WHERE id=?').bind('c').run();assert.equal((await req('/api/capsules',undefined,'c')).status,401);
});
