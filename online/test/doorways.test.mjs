// Exact published returns and public consent on a real local D1/R2 runtime.
import {test,before,after} from 'node:test';
import assert from 'node:assert/strict';
import {readFile,readdir} from 'node:fs/promises';
import {Miniflare} from 'miniflare';
import {canonical,sha} from '../src/publication.js';
import {parse} from 'lossless-json';
import vm from 'node:vm';
let mf,db,sourceId,targetId,source,target,proposal;
const req=(path,data,who='a')=>mf.dispatchFetch('http://localhost:7490'+path,{method:data===undefined?'GET':'POST',headers:{'Content-Type':'application/json',...(who?{Authorization:'Bearer synthetic-'+who}:{Origin:'http://localhost:7490'})},...(data===undefined?{}:{body:JSON.stringify(data)})});
const ok=async r=>{assert.ok(r.ok,await r.clone().text());return r.json();};
before(async()=>{
 mf=new Miniflare({modules:true,scriptPath:'dist/worker.js',compatibilityDate:'2026-05-15',d1Databases:['DB'],r2Buckets:['INQUIRIES'],bindings:{SITE_ORIGIN:'http://localhost:7490'}});db=await mf.getD1Database('DB');
 for(const f of (await readdir('migrations')).filter(f=>f.endsWith('.sql')).sort())for(const sql of (await readFile('migrations/'+f,'utf8')).split(';').map(s=>s.trim()).filter(Boolean))await db.prepare(sql).run();
 for(const id of ['a','b','c']){await db.prepare("INSERT INTO owners VALUES(?,?,'synthetic',1)").bind(id,'synthetic-'+id).run();await db.prepare('INSERT INTO instances VALUES(?,?,?,?,1,NULL)').bind(id,id,id,await sha('synthetic-'+id)).run();}
 const a=JSON.parse(await readFile('test/fixtures/1.json','utf8')),b=JSON.parse(await readFile('test/fixtures/2.json','utf8'));
 source=parse(a.inquiry_json);target=parse(b.inquiry_json);
 sourceId=(await ok(await req('/api/publications',{artifact:a,reviewed:true}))).id;
 targetId=(await ok(await req('/api/publications',{artifact:b,reviewed:true},'b'))).id;
 const g=source.content.graphs[0],s={inquiry_id:source.id,origin_id:source.content.origin_id,session_id:source.content.session.id,graph_id:g.graph.id,node_id:g.graph.nodes[1].id,source_sha256:g.source_sha256,shared_sha256:g.shared_sha256,author:source.content.author};
 const content={source:s,question:'Synthetic returned inquiry question',inquiry:target};
 proposal={source:s,question:content.question,offer_id:await sha(canonical(content)),source_publication_id:sourceId,target_publication_id:targetId,entry:{graph_id:target.content.graphs[0].graph.id,node_id:target.content.graphs[0].graph.nodes[0].id}};
});
after(async()=>mf?.dispose());
let delivered,review;
test('proposal verifies exact source and complete returned snapshot; unreviewed and foreign writes remain inert',async()=>{
 assert.equal((await req('/api/doorways/review',proposal,null)).status,401);
 assert.equal((await req('/api/doorways/review',proposal,'c')).status,403);
 assert.equal((await req('/api/doorways/review',{...proposal,source:{...proposal.source,node_id:'0'.repeat(26)}},'b')).status,400);
 assert.equal((await req('/api/doorways/review',{...proposal,source:{...proposal.source,source_sha256:'0'.repeat(64)}},'b')).status,400);
 assert.equal((await req('/api/doorways/review',{...proposal,offer_id:'0'.repeat(64)},'b')).status,400);
 review=(await ok(await req('/api/doorways/review',proposal,'b'))).review;
 assert.equal((await req('/api/doorways/send',{review},'b')).status,400);
 assert.equal((await db.prepare('SELECT count(*) n FROM doorways').first()).n,0);
 const [a,b]=await Promise.all([req('/api/doorways/send',{review,reviewed:true},'b'),req('/api/doorways/send',{review,reviewed:true},'b')]);
 delivered=(await ok(a)).id;assert.equal((await ok(b)).id,delivered);
 assert.equal((await db.prepare('SELECT count(*) n FROM doorways').first()).n,1);
 assert.deepEqual((await ok(await req('/api/doorways/public',undefined,null))).doorways,[]);
 assert.equal((await req('/api/doorways/'+delivered,undefined,'c')).status,404);
});
test('only exact source-owner public acceptance opens a reversible doorway; full canonical return downloads unchanged',async()=>{
 const detail=await ok(await req('/api/doorways/'+delivered));
 const offer=parse(detail.offer_json);assert.equal(await sha(canonical(offer.content)),proposal.offer_id);assert.equal(canonical(offer.content.inquiry),canonical(target));
 const decide={reviewed:true,review,decision:'accepted'};
 assert.equal((await req('/api/doorways/'+delivered+'/decide',decide)).status,400);
 assert.equal((await req('/api/doorways/'+delivered+'/decide',{...decide,public_consent:true},'b')).status,403);
 assert.equal((await req('/api/doorways/'+delivered+'/decide',{...decide,review:{...review,question:'tampered'},public_consent:true})).status,400);
 const accepted=await ok(await req('/api/doorways/'+delivered+'/decide',{...decide,public_consent:true}));
 assert.deepEqual(await ok(await req('/api/doorways/'+delivered+'/decide',{...decide,public_consent:true})),accepted);
 const shared=(await ok(await req('/api/doorways/public',undefined,null))).doorways;
 assert.equal(shared.length,1);assert.equal(shared[0].source.node_id,proposal.source.node_id);assert.equal(shared[0].target.publication_id,targetId);
 assert.ok(!JSON.stringify(shared).includes('Synthetic returned inquiry question'));assert.ok(!('offer_id' in shared[0]));
 await ok(await req('/api/blocks',{owner_id:'b',blocked:true}));
 assert.deepEqual((await ok(await req('/api/doorways/public',undefined,null))).doorways,[]);
 assert.equal((await req('/api/doorways/'+delivered,undefined,'b')).status,404);
 await ok(await req('/api/blocks',{owner_id:'b',blocked:false}));
 assert.equal((await ok(await req('/api/doorways/public?publication='+sourceId,undefined,null))).doorways.length,1);
 await ok(await req('/api/doorways/'+delivered+'/withdraw',{reviewed:true},'b'));
 assert.deepEqual((await ok(await req('/api/doorways/public',undefined,null))).doorways,[]);
 assert.equal((await req('/api/doorways/send',{review,reviewed:true},'b')).status,409);
});
test('decline never creates a public link and publication withdrawal hides accepted links',async()=>{
 for(const decision of ['declined','accepted']){
  const question='Synthetic '+decision,content={source:proposal.source,question,inquiry:target};
  const r=(await ok(await req('/api/doorways/review',{...proposal,question,offer_id:await sha(canonical(content))},'b'))).review;
  const d=await ok(await req('/api/doorways/send',{review:r,reviewed:true},'b'));
  await ok(await req('/api/doorways/'+d.id+'/decide',{reviewed:true,review:r,decision,public_consent:true}));
  const links=(await ok(await req('/api/doorways/public',undefined,null))).doorways;
  assert.equal(links.length,decision==='accepted'?1:0);
  assert.equal((await req('/api/doorways/'+d.id+'/decide',{reviewed:true,review:r,decision:decision==='accepted'?'declined':'accepted',public_consent:true})).status,409);
 }
 await ok(await req('/api/publications/'+targetId+'/withdraw',{reviewed:true},'b'));
 assert.deepEqual((await ok(await req('/api/doorways/public',undefined,null))).doorways,[]);
});
test('native and hosted unread state changes only after arrival at the exact accepted target',async()=>{
 const saved=new Map(),navigated=[],context={window:{},URL,URLSearchParams,location:{origin:'http://localhost',href:'http://localhost/inquiries/'+'a'.repeat(64)+'/?arrival=door',search:'?arrival=door',assign:u=>navigated.push(u)},localStorage:{getItem:k=>saved.get(k),setItem:(k,v)=>saved.set(k,v)}};
 vm.runInNewContext(await readFile('../viz/dist/doorways.js','utf8'),context);
 const helper=context.window.TADoorways,door={id:'door',scope:'native',graphId:'source',nodeId:'sourceNode',returnOrigin:true,entry:{graph_id:'target',node_id:'targetNode'},href:'/#/g/source/n/sourceNode'};
 helper.arrivals({graph_id:'wrong',node:{id:'targetNode'},external_doors:[door]});assert.equal(saved.size,0);
 helper.arrivals({graph_id:'target',node:{id:'targetNode'},external_doors:[door]});assert.equal(saved.size,1);
 assert.equal(helper.arrivals({external_doors:[{...door,returnOrigin:false} ]})[0].seen,true);
 helper.follow(door);assert.equal(navigated[0],'http://localhost/#/g/source/n/sourceNode');
 helper.follow({...door,href:'https://attacker.invalid/'});assert.equal(navigated.length,1);
});
