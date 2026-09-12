import {launchRecords,acceptanceRecords} from './expeditions.js';
// Inert, reviewed transport over the existing Capsule schema; no graph writes.
import validate from '../dist/validate-capsule.js';
import {parse} from 'lossless-json';
import {canonical, sha, fail} from './publication.js';
const now = () => Math.floor(Date.now()/1000);
const hash = /^[a-f0-9]{64}$/;
const blockedSQL = `NOT EXISTS(SELECT 1 FROM blocks b WHERE
 (b.owner_id=d.owner_id AND b.blocked_owner_id=?) OR (b.owner_id=? AND b.blocked_owner_id=d.owner_id))`;
const columns = `SELECT d.*,o.login,o.kind,r.received_at,r.decision,r.decided_at
 FROM capsule_deliveries d JOIN owners o ON o.id=d.owner_id
 LEFT JOIN capsule_receipts r ON r.delivery_id=d.id AND r.owner_id=CASE WHEN d.owner_id=? THEN d.recipient_id ELSE ? END`;
const brief = r => ({id:r.id,sequence:r.seq,capsule_id:r.capsule_id,title:r.title,intent:r.intent,
 sender:{id:r.owner_id,login:r.login,verified:r.kind==='github'}, audience:r.audience,recipient_id:r.recipient_id,
 source_publication_id:r.source_publication_id,reply_delivery_id:r.reply_delivery_id,reply_publication_id:r.reply_publication_id,target_publication_id:r.target_publication_id,
 created_at:r.created_at,withdrawn:!!r.withdrawn_at,received_at:r.received_at,decision:r.decision,decided_at:r.decided_at});
async function row(env,id,who) {
 if(!hash.test(id)) fail('Choose a Capsule delivery',404);
 const r=await env.DB.prepare(columns+` WHERE d.id=? AND (d.owner_id=? OR d.recipient_id=? OR d.audience='public')
 AND (d.owner_id=? OR ${blockedSQL})`).bind(who.id,who.id,id,who.id,who.id,who.id,who.id,who.id).first();
 if(!r) fail('Capsule unavailable to this account',404);
 return r;
}
async function available(env,id,who) {
 const r=await row(env,id,who);
 if(r.withdrawn_at) fail('This Capsule was withdrawn',410);
 return r;
}
export async function inspectCapsule(raw) {
 if(typeof raw!=='string' || new TextEncoder().encode(raw).length>256*1024) fail('Choose a Capsule of at most 256 KiB');
 let c,lossless;
 try {c=JSON.parse(raw);lossless=parse(raw);} catch {fail('Invalid Capsule JSON');}
 if(!validate(c)) fail('Capsule does not match the shared schema');
 if(await sha(canonical(lossless.content))!==c.id) fail('Capsule checksum does not match');
 const content=c.content;
 if((content.intent==='return')!==(content.reply_to!==null)) fail('A return needs an exact source');
 const graphs=new Set();
 for(const e of content.excerpts) {
  const s=e.source, nodes=new Set(e.thoughts.map(n=>n.id)), evidence=new Set();
  if(graphs.has(s.graph_id)||s.origin_id!==content.origin_id||s.session_id!==content.home_session_id||nodes.size!==e.thoughts.length||e.thoughts.some(n=>'probe_ids' in n||'sensor_ids' in n)) fail('Invalid Capsule selections');
  graphs.add(s.graph_id);
  for(const b of e.evidence) {
   if(evidence.has(b.id)||b.graph_id!==s.graph_id||!nodes.has(b.node_id)||!b.artifact_refs.length) fail('Invalid selected evidence');
   evidence.add(b.id);
   for(const ref of b.artifact_refs) {let u;try{u=new URL(ref);}catch{fail('Invalid evidence URL');}
    if(!['http:','https:'].includes(u.protocol)||u.username||u.password) fail('Evidence requires public web links');}
  }
 }
 return c;
}
async function publication(env,id) {
 if(!hash.test(id||'')) fail('Choose an exact published inquiry');
 const p=await env.DB.prepare('SELECT * FROM publications WHERE id=? AND withdrawn_at IS NULL').bind(id).first();
 if(!p) fail('Published inquiry unavailable',404);
 return p;
}
async function review(env,who,data) {
 const c=await inspectCapsule(data.capsule_json), choice=data.destination;
 if(!choice||!['directed','public'].includes(choice.audience)) fail('Choose an explicit audience');
 const d={audience:choice.audience,recipient_id:choice.recipient_id||null,source_publication_id:choice.source_publication_id||null,
  reply_delivery_id:choice.reply_delivery_id||null,reply_publication_id:choice.reply_publication_id||null,target_publication_id:choice.target_publication_id||null};
 let recipient=null,source=null,replySource=null,targetPort=null;
 if(d.source_publication_id) {
  const p=await publication(env,d.source_publication_id);
  if(p.owner_id!==who.id||p.origin_id!==c.content.origin_id||p.session_id!==c.content.home_session_id) fail('Launch source must be your Capsule’s published home Threadwalk',403);
  source={id:p.id,title:p.title,threadwalk_id:p.threadwalk_id};
 }
 if(d.audience==='public' && (!source||d.recipient_id)) fail('Open Capsules need a published source and no private recipient');
  if(d.audience==='directed' && !d.recipient_id && typeof choice.recipient_login==='string') {
   const found=await env.DB.prepare('SELECT id FROM owners WHERE login=? COLLATE NOCASE').bind(choice.recipient_login.trim()).first();
   if(!found)fail('Recipient has not connected to this Atlas',404);
   d.recipient_id=found.id;
  }
 const reply=c.content.reply_to;
 if(reply) {
  if(d.audience!=='directed') fail('Return contributions are directed to their original author');
  if(reply.kind==='capsule') {
   if(!d.reply_delivery_id||d.reply_publication_id) fail('Choose the original Capsule delivery');
   const parent=await available(env,d.reply_delivery_id,who), original=JSON.parse(parent.capsule_json);
   if(parent.capsule_id!==reply.id||original.content.origin_id!==reply.origin_id) fail('Return differs from its exact source Capsule');
   if(parent.owner_id!==d.recipient_id) fail('Return must go to the original Capsule sender');
   replySource={kind:'capsule',id:parent.id,title:parent.title,capsule_json:parent.capsule_json};
  } else {
   if(!d.reply_publication_id||d.reply_delivery_id) fail('Choose the exact source publication');
   const p=await publication(env,d.reply_publication_id), s=reply.source;
   const obj=await env.INQUIRIES.get(p.object_key);if(!obj) fail('Source temporarily unavailable',503);
   const b=JSON.parse((await obj.json()).inquiry_json), g=b.content.graphs.find(g=>g.graph.id===s.graph_id);
   if(p.owner_id!==d.recipient_id||p.inquiry_id!==s.inquiry_id||p.origin_id!==s.origin_id||p.session_id!==s.session_id||!g||g.source_sha256!==s.source_sha256||g.shared_sha256!==s.shared_sha256||!g.graph.nodes.some(n=>n.id===s.node_id)||s.author!==b.content.author) fail('Return differs from its exact published source');
   replySource={kind:'inquiry',id:p.id,title:p.title,source:s,thought:g.graph.nodes.find(n=>n.id===s.node_id)};
  }
 } else if(d.reply_delivery_id||d.reply_publication_id) fail('Only a contextual return may name a return destination');
 if(d.audience==='directed') {
  if(typeof d.recipient_id!=='string'||d.recipient_id===who.id) fail('Choose another Atlas owner');
  const owner=await env.DB.prepare('SELECT id,login,kind FROM owners WHERE id=?').bind(d.recipient_id).first();
  if(!owner) fail('Recipient has not connected to this Atlas',404);
  const blocked=await env.DB.prepare('SELECT 1 FROM blocks WHERE (owner_id=? AND blocked_owner_id=?) OR (owner_id=? AND blocked_owner_id=?)').bind(who.id,owner.id,owner.id,who.id).first();
  if(blocked) fail('Delivery is unavailable between these accounts',403);
  recipient={id:owner.id,login:owner.login,verified:owner.kind==='github'};
 }
 if(d.target_publication_id) {
  const target=await publication(env,d.target_publication_id);
  if(d.audience!=='directed'||target.owner_id!==d.recipient_id)fail('Choose a published destination owned by the recipient');
  if(reply)fail('A return uses its original source port as its destination');
  targetPort={id:target.id,title:target.title,threadwalk_id:target.threadwalk_id};
 }
 return {capsule_json:data.capsule_json,destination:d,sender:{id:who.id,login:who.login},recipient,source,target:targetPort,reply_source:replySource};
}
export async function capsuleGet(env,u,who) {
 const path=u.pathname;
 if(path==='/api/blocks') return {blocks:(await env.DB.prepare('SELECT b.blocked_owner_id AS id,o.login FROM blocks b JOIN owners o ON o.id=b.blocked_owner_id WHERE b.owner_id=?').bind(who.id).all()).results};
 if(path==='/api/capsules') {
  const mode=u.searchParams.get('view')||'inbox', after=Math.max(0,Math.floor(Number(u.searchParams.get('after'))||0));
  if(!['inbox','sent','public'].includes(mode)) fail('Choose inbox, sent or public');
  const condition=mode==='sent'?'d.owner_id=?':mode==='inbox'?'(d.recipient_id=? OR r.owner_id=?)':"d.audience='public' AND d.withdrawn_at IS NULL";
  const bindings=[who.id,who.id,after,...(mode==='inbox'?[who.id,who.id]:mode==='sent'?[who.id]:[]),who.id,who.id];
  const {results}=await env.DB.prepare(columns+` WHERE d.seq>? AND ${condition} AND ${blockedSQL} ORDER BY d.seq LIMIT 50`).bind(...bindings).all();
  return {deliveries:results.map(brief),next:results.length===50?results.at(-1).seq:null};
 }
 if(path==='/api/capsules/destinations') {
  const login=u.searchParams.get('recipient');
  const recipient=login?await env.DB.prepare('SELECT id,login FROM owners WHERE login=? COLLATE NOCASE').bind(login.trim()).first():who;
  if(!recipient)fail('Recipient has not connected to this Atlas',404);
  const {results}=await env.DB.prepare('SELECT id,title,origin_id,session_id FROM publications WHERE owner_id=? AND withdrawn_at IS NULL AND seq=(SELECT max(p.seq) FROM publications p WHERE p.threadwalk_id=publications.threadwalk_id) ORDER BY seq DESC').bind(recipient.id).all();
  return {publications:results};
 }
 const match=path.match(/^\/api\/capsules\/([a-f0-9]{64})$/);
 if(match) {
  const r=await available(env,match[1],who), c=JSON.parse(r.capsule_json);
  // Source review is resolved anew so withdrawal/blocking cannot be bypassed by a cached review.
  let source=null;
  if(c.content.reply_to) {
   if(r.reply_delivery_id) {const p=await available(env,r.reply_delivery_id,who);source={kind:'capsule',id:p.id,capsule_json:p.capsule_json};}
   else {const p=await publication(env,r.reply_publication_id),obj=await env.INQUIRIES.get(p.object_key);if(!obj)fail('Source temporarily unavailable',503);
    const b=JSON.parse((await obj.json()).inquiry_json),s=c.content.reply_to.source;
    source={kind:'inquiry',id:p.id,source:s,thought:b.content.graphs.find(g=>g.graph.id===s.graph_id).graph.nodes.find(n=>n.id===s.node_id)};}
  }
  return {...brief(r),capsule_json:r.capsule_json,source};
 }
 fail('Unknown Capsule resource',404);
}
export async function capsulePost(env,path,who,data) {
 if(path==='/api/blocks') {
  if(typeof data.owner_id!=='string'||data.owner_id===who.id||typeof data.blocked!=='boolean') fail('Choose an account to block or unblock');
  if(!await env.DB.prepare('SELECT 1 FROM owners WHERE id=?').bind(data.owner_id).first())fail('Owner unavailable',404);
  if(data.blocked)await env.DB.prepare('INSERT INTO blocks VALUES(?,?) ON CONFLICT DO NOTHING').bind(who.id,data.owner_id).run();
  else await env.DB.prepare('DELETE FROM blocks WHERE owner_id=? AND blocked_owner_id=?').bind(who.id,data.owner_id).run();
  return {blocked:data.blocked};
 }
 if(path==='/api/capsules/review')return {review:await review(env,who,data)};
 if(data.reviewed!==true)fail('Review the complete Capsule and destination before this action');
 if(path==='/api/capsules/send') {
  const proposed=data.review;
  if(!proposed)fail('Review the delivery first');
  const c=await inspectCapsule(proposed.capsule_json), id=await sha(who.id+':'+c.id);
  // Lost response retries recover the original launch, even after source withdrawal.
  const existing=await env.DB.prepare('SELECT * FROM capsule_deliveries WHERE id=?').bind(id).first();
  if(existing) {if(existing.review_json!==canonical(proposed))fail('This Capsule already launched to another reviewed destination',409);return {id,reused:true,withdrawn:!!existing.withdrawn_at};}
  const current=await review(env,who,proposed);
  if(canonical(current)!==canonical(proposed))fail('Audience or source changed; review delivery again',409);
  const d=current.destination;
  await env.DB.batch([env.DB.prepare(`INSERT INTO capsule_deliveries(id,owner_id,instance_id,capsule_id,capsule_json,title,intent,audience,recipient_id,source_publication_id,reply_delivery_id,reply_publication_id,review_json,created_at,target_publication_id)
   SELECT ?,?,?,?,?,?,?,?,?,?,?,?,?,?,? WHERE (SELECT count(*) FROM capsule_deliveries WHERE owner_id=?)<200
   AND NOT EXISTS(SELECT 1 FROM blocks WHERE (owner_id=? AND blocked_owner_id=?) OR (owner_id=? AND blocked_owner_id=?))
   AND (? IS NULL OR EXISTS(SELECT 1 FROM publications WHERE id=? AND withdrawn_at IS NULL))
   AND (? IS NULL OR EXISTS(SELECT 1 FROM publications WHERE id=? AND withdrawn_at IS NULL))
   AND (? IS NULL OR EXISTS(SELECT 1 FROM capsule_deliveries WHERE id=? AND withdrawn_at IS NULL)) ON CONFLICT DO NOTHING`)
   .bind(id,who.id,who.instance_id||null,c.id,current.capsule_json,c.content.title,c.content.intent,d.audience,d.recipient_id,d.source_publication_id,d.reply_delivery_id,d.reply_publication_id,canonical(current),now(),d.target_publication_id,who.id,who.id,d.recipient_id,d.recipient_id,who.id,d.source_publication_id,d.source_publication_id,d.reply_publication_id,d.reply_publication_id,d.reply_delivery_id,d.reply_delivery_id),...launchRecords(env,id)]);
  const saved=await env.DB.prepare('SELECT review_json FROM capsule_deliveries WHERE id=?').bind(id).first();
  if(!saved)fail('Delivery unavailable or preview limit reached',409);
  if(saved.review_json!==canonical(current))fail('This Capsule already launched to another destination',409);
  return {id,reused:false};
 }
 const match=path.match(/^\/api\/capsules\/([a-f0-9]{64})\/(receive|decide|withdraw)$/);
 if(!match)fail('Unknown Capsule action',404);
 const r=await row(env,match[1],who), action=match[2];
 if(action==='withdraw') {
  if(r.owner_id!==who.id)fail('Only the sender can withdraw a Capsule',403);
  await env.DB.prepare('UPDATE capsule_deliveries SET withdrawn_at=COALESCE(withdrawn_at,?) WHERE id=?').bind(now(),r.id).run();
  return {withdrawn:true};
 }
 if(r.withdrawn_at)fail('This Capsule was withdrawn',410);
 if(r.owner_id===who.id)fail('Choose a received Capsule');
 if(action==='decide') {
  if(r.intent!=='return'||r.recipient_id!==who.id||!['accepted','declined'].includes(data.decision))fail('Only the source owner may accept or decline a returned contribution',403);
  if(!r.received_at)fail('Receive and review this return first');
  const detail=await capsuleGet(env,new URL(env.SITE_ORIGIN+'/api/capsules/'+r.id),who);
  if(canonical(data.source)!==canonical(detail.source)||data.capsule_id!==r.capsule_id)fail('Review this exact return and its original source');
  if(r.decision){if(r.decision!==data.decision)fail('This return already has a different decision',409);return {decision:r.decision,decided_at:r.decided_at};}
  await env.DB.batch([env.DB.prepare(`UPDATE capsule_receipts SET decision=?,decided_at=? WHERE delivery_id=? AND owner_id=? AND decision IS NULL
   AND EXISTS(SELECT 1 FROM capsule_deliveries d WHERE d.id=? AND d.withdrawn_at IS NULL AND ${blockedSQL}
   AND (d.reply_delivery_id IS NULL OR EXISTS(SELECT 1 FROM capsule_deliveries p WHERE p.id=d.reply_delivery_id AND p.withdrawn_at IS NULL))
   AND (d.reply_publication_id IS NULL OR EXISTS(SELECT 1 FROM publications p WHERE p.id=d.reply_publication_id AND p.withdrawn_at IS NULL)))`)
   .bind(data.decision,now(),r.id,who.id,r.id,who.id,who.id),...acceptanceRecords(env,r.id,who.id)]);
  const saved=await env.DB.prepare('SELECT decision,decided_at FROM capsule_receipts WHERE delivery_id=? AND owner_id=?').bind(r.id,who.id).first();
  if(saved.decision!==data.decision)fail('This return already has a different decision or is unavailable',409);
  return saved;
 }
 await env.DB.prepare(`INSERT INTO capsule_receipts SELECT id,?,?,NULL,NULL FROM capsule_deliveries d
  WHERE id=? AND withdrawn_at IS NULL AND ${blockedSQL} ON CONFLICT DO NOTHING`).bind(who.id,now(),r.id,who.id,who.id).run();
 const saved=await env.DB.prepare('SELECT received_at,decision,decided_at FROM capsule_receipts WHERE delivery_id=? AND owner_id=?').bind(r.id,who.id).first();
 if(!saved)fail('This delivery is no longer available',409);
 return saved;
}
