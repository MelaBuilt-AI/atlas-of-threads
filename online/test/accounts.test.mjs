// Isolated synthetic identities only; no live authorization, stores or data.
import {test,before,after} from 'node:test';
import assert from 'node:assert/strict';
import {readFile,readdir} from 'node:fs/promises';
import {createHmac} from 'node:crypto';
import {Miniflare} from 'miniflare';
import {sha} from '../src/publication.js';
let mf,db,bucket;
const origin='https://atlas.example', secret='synthetic-webhook-secret';
const now=()=>Math.floor(Date.now()/1000);
async function request(path,data,owner='42',device=false){return mf.dispatchFetch(origin+path,{headers:{...(owner?(device?{Authorization:'Bearer device-'+owner}:{Cookie:'atlas_session=session-'+owner}):{}),...(data===undefined?{}:{Origin:origin,'Content-Type':'application/json'})},...(data===undefined?{}:{method:'POST',body:JSON.stringify(data)})});}
async function seed(id){
 await db.prepare('INSERT INTO owners VALUES(?,?,?,?) ON CONFLICT DO NOTHING').bind(id,'synthetic-'+id,'github',1).run();
 await db.prepare('INSERT INTO sessions VALUES(?,?,?)').bind(await sha('session-'+id),id,now()+3600).run();
 await db.prepare('INSERT INTO instances VALUES(?,?,?,?,?,NULL)').bind('device-'+id,id,'Synthetic device',await sha('device-'+id),1).run();
}
async function webhook(id,delivery='synthetic-'+id,options={}){
 const raw=options.raw??JSON.stringify({action:'revoked',sender:{id:Number(id),login:'ignored-display-login'}});
 const signature=options.signature??'sha256='+createHmac('sha256',secret).update(raw).digest('hex');
 return mf.dispatchFetch(origin+'/api/github/webhook',{method:'POST',headers:{'X-Hub-Signature-256':signature,'X-GitHub-Event':options.event||'github_app_authorization','X-GitHub-Delivery':delivery},body:raw});
}
before(async()=>{
 mf=new Miniflare({modules:true,scriptPath:'dist/worker.js',compatibilityDate:'2026-05-15',d1Databases:['DB'],r2Buckets:['INQUIRIES'],bindings:{SITE_ORIGIN:origin,GITHUB_CLIENT_ID:'synthetic',GITHUB_CLIENT_SECRET:'synthetic',GITHUB_WEBHOOK_SECRET:secret,MODERATOR_GITHUB_IDS:'7'},outboundService:async r=>new URL(r.url).hostname==='github.com'?Response.json({access_token:'synthetic'}):Response.json({id:42,login:'synthetic-42'})});
 db=await mf.getD1Database('DB');bucket=await mf.getR2Bucket('INQUIRIES');
 for(const file of (await readdir('migrations')).filter(f=>f.endsWith('.sql')).sort())for(const sql of (await readFile('migrations/'+file,'utf8')).split(';').map(s=>s.trim()).filter(Boolean))await db.prepare(sql).run();
 for(const id of ['42','43','7','44','45'])await seed(id);
});
after(async()=>mf?.dispose());
test('signed GitHub deauthorization revokes only its numeric owner, cancels pending auth and pairing, and preserves publications',async()=>{
 const artifact=JSON.parse(await readFile('test/fixtures/1.json','utf8'));
 const published=await request('/api/publications',{artifact,reviewed:true});assert.equal(published.status,201,await published.clone().text());const {id}=await published.json();
 await request('/api/activity',{enabled:true});
 const pairing=await (await request('/api/pairings',{name:'Synthetic pending'})).json();
 const start=await mf.dispatchFetch(origin+'/auth/login',{redirect:'manual'});const state=new URL(start.headers.get('Location')).searchParams.get('state');
 assert.equal((await webhook('42','invalid',{signature:'sha256='+'0'.repeat(64)})).status,403);
 assert.equal((await request('/api/me')).status,200);
 const revoked=await webhook('42');assert.equal(revoked.status,200,await revoked.clone().text());
 assert.equal((await (await request('/api/me')).json()).owner,null);
 assert.equal((await request('/api/mine',undefined,'42',true)).status,401);
 assert.equal((await request('/api/pairings/exchange',{code:pairing.code},null)).status,403);
 assert.equal((await request('/api/mine',undefined,'43',true)).status,200);
 assert.equal((await request('/api/publications/'+id,undefined,null)).status,200);
 assert.equal((await db.prepare('SELECT enabled FROM activity WHERE owner_id=?').bind('42').first()).enabled,0);
 const callback=origin+'/auth/callback?state='+state+'&code=synthetic';
 assert.equal((await mf.dispatchFetch(callback,{headers:{Cookie:'atlas_state='+state},redirect:'manual'})).status,403);
 // A new OAuth flow can reconnect; a retry of the old delivery cannot revoke it.
 const restart=await mf.dispatchFetch(origin+'/auth/login',{redirect:'manual'}),fresh=new URL(restart.headers.get('Location')).searchParams.get('state');
 const auth=await mf.dispatchFetch(origin+'/auth/callback?state='+fresh+'&code=synthetic',{headers:{Cookie:'atlas_state='+fresh},redirect:'manual'});assert.equal(auth.status,302,await auth.clone().text());
 assert.equal((await (await webhook('42')).json()).reused,true);
 assert.equal((await db.prepare('SELECT count(*) n FROM sessions WHERE owner_id=?').bind('42').first()).n,1);
});
test('webhook rejects tampering, malformed identities, oversized bodies; signed ping is inert and concurrent retries converge',async()=>{
 assert.equal((await webhook('43','bad',{raw:'{'})).status,400);
 assert.equal((await webhook('43','bad',{raw:JSON.stringify({action:'revoked',sender:{id:'43'}})})).status,400);
 assert.equal((await webhook('43','bad',{raw:'x'.repeat(65537)})).status,413);
 assert.deepEqual(await (await webhook('43','ping',{event:'ping'})).json(),{ok:true});
 assert.equal((await request('/api/mine',undefined,'43',true)).status,200);
 const duplicates=await Promise.all([webhook('44'),webhook('44')]);
 assert.deepEqual((await Promise.all(duplicates.map(r=>r.json()))).map(r=>r.reused).sort(),[false,true]);
});
test('activity is off by default, explicit, expiring, account-scoped and cannot be renewed by a device or after off',async()=>{
 assert.deepEqual(await (await request('/api/activity',undefined,'43')).json(),{enabled:false,active:false});
 assert.equal((await request('/api/activity',{enabled:true},'43',true)).status,403);
 assert.equal((await request('/api/activity',{enabled:true},null)).status,401);
 assert.deepEqual(await (await request('/api/activity',{enabled:true},'43')).json(),{enabled:true,active:true});
 await db.prepare('UPDATE activity SET expires_at=? WHERE owner_id=?').bind(now()-1,'43').run();
 assert.deepEqual(await (await request('/api/activity',undefined,'43')).json(),{enabled:true,active:false});
 assert.equal((await (await request('/api/activity',{action:'heartbeat'},'43')).json()).active,true);
 await request('/api/activity',{enabled:false},'43');
 assert.equal((await (await request('/api/activity',{action:'heartbeat'},'43')).json()).active,false);
 await request('/api/activity',{enabled:true},'45');await request('/api/account/revoke',{},'45');
 assert.equal((await db.prepare('SELECT enabled FROM activity WHERE owner_id=?').bind('45').first()).enabled,0);
});
test('moderation is browser-only and allowlisted; decisions are audited, idempotent and withdraw only the exact snapshot',async()=>{
 const artifact=JSON.parse(await readFile('test/fixtures/2.json','utf8'));
 const pub=await request('/api/publications',{artifact,reviewed:true},'43');assert.equal(pub.status,201,await pub.clone().text());const {id}=await pub.json();
 assert.equal((await request('/api/publications/'+id+'/report',{reason:'Synthetic review concern'},'7')).status,200);
 for(const who of [null,'43'])assert.ok((await request('/api/reports',undefined,who)).status>=400);
 assert.equal((await request('/api/reports',undefined,'7',true)).status,403);
 const report=(await (await request('/api/reports',undefined,'7')).json()).reports[0];assert.equal(report.reason,'Synthetic review concern');
 const data={publication_id:id,reporter_id:'7',status:'withdrawn',note:'Synthetic decision'};
 assert.equal((await request('/api/reports/review',data,'7')).status,400);
 assert.equal((await request('/api/reports/review',{...data,confirm_withdrawal:true},'43')).status,403);
 const decision=await request('/api/reports/review',{...data,confirm_withdrawal:true},'7');assert.equal(decision.status,200,await decision.clone().text());
 assert.equal((await request('/api/publications/'+id,undefined,null)).status,410);
 assert.equal((await request('/api/publications/'+id+'/bundle',undefined,null)).status,410);
 assert.equal((await (await request('/api/reports/review',{...data,confirm_withdrawal:true},'7')).json()).reused,true);
 const saved=(await (await request('/api/reports?status=withdrawn',undefined,'7')).json()).reports[0];assert.equal(saved.reviewed_by,'7');assert.equal(saved.review_note,'Synthetic decision');
 assert.equal(await bucket.get((await db.prepare('SELECT object_key FROM publications WHERE id=?').bind(id).first()).object_key),null);
 const world=await (await request('/api/world',undefined,null)).json();assert.equal(world.publications.length,1);
});
