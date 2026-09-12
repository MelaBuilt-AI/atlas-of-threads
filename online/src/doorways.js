// Public links require an explicit offer by the contributor and acceptance by the source owner.
// Full graphs remain ordinary reviewed publication objects; no second graph store.
import {canonical,sha,fail} from './publication.js';
import {parse} from 'lossless-json';
const hash=/^[a-f0-9]{64}$/;
const now=()=>Math.floor(Date.now()/1000);
const live=`d.withdrawn_at IS NULL AND s.withdrawn_at IS NULL AND t.withdrawn_at IS NULL AND NOT EXISTS(SELECT 1 FROM blocks b WHERE (b.owner_id=d.owner_id AND b.blocked_owner_id=d.recipient_id) OR (b.owner_id=d.recipient_id AND b.blocked_owner_id=d.owner_id))`;
const rows=`SELECT d.*,s.threadwalk_id AS source_threadwalk_id,t.threadwalk_id AS target_threadwalk_id FROM doorways d JOIN publications s ON s.id=d.source_publication_id JOIN publications t ON t.id=d.target_publication_id`;
async function publication(env,id){if(!hash.test(id||''))fail('Choose an exact published inquiry');const p=await env.DB.prepare('SELECT * FROM publications WHERE id=? AND withdrawn_at IS NULL').bind(id).first();if(!p)fail('Published inquiry unavailable',404);const object=await env.INQUIRIES.get(p.object_key);if(!object)fail('Published inquiry unavailable',503);return {row:p,bundle:parse((await object.json()).inquiry_json)};}
function endpoint(p,graph,node){const record=p.bundle.content.graphs.find(r=>r.graph.id===graph),thought=record?.graph.nodes.find(n=>n.id===node);if(!thought)fail('Choose a chamber in this exact publication');return {publication_id:p.row.id,threadwalk_id:p.row.threadwalk_id,inquiry_id:p.row.inquiry_id,graph_id:graph,node_id:node,title:p.row.title,author:p.row.author,thought:thought.text};}
async function review(env,who,data){
 const s=data.source;
 if(!s||Object.keys(s).sort().join(',')!=='author,graph_id,inquiry_id,node_id,origin_id,session_id,shared_sha256,source_sha256')fail('Review the exact return source');
 if(typeof data.question!=='string'||!data.question.trim()||data.question.length>400||!hash.test(data.offer_id||''))fail('Choose a valid return-path offer');
 const source=await publication(env,data.source_publication_id),target=await publication(env,data.target_publication_id);
 if(target.row.owner_id!==who.id)fail('Publish the returned inquiry from your own Atlas account first',403);
 if(source.row.owner_id===who.id)fail('Choose another inhabitant’s source inquiry');
 const blocked=await env.DB.prepare('SELECT 1 FROM blocks WHERE (owner_id=? AND blocked_owner_id=?) OR (owner_id=? AND blocked_owner_id=?)').bind(who.id,source.row.owner_id,source.row.owner_id,who.id).first();if(blocked)fail('Exchange unavailable between these accounts',403);
 const c=source.bundle.content,g=c.graphs.find(r=>r.graph.id===s.graph_id);
 if(source.row.inquiry_id!==s.inquiry_id||c.origin_id!==s.origin_id||c.session.id!==s.session_id||c.author!==s.author||!g||g.source_sha256!==s.source_sha256||g.shared_sha256!==s.shared_sha256)fail('Return does not match the exact source snapshot');
 const offer={source:s,question:data.question,inquiry:target.bundle};
 if(await sha(canonical(offer))!==data.offer_id)fail('Published returned inquiry differs from the reviewed offer');
 const sourceEndpoint=endpoint(source,s.graph_id,s.node_id),targetEndpoint=endpoint(target,data.entry?.graph_id,data.entry?.node_id);
 return {offer_id:data.offer_id,source:s,question:data.question,source_publication_id:source.row.id,target_publication_id:target.row.id,entry:data.entry,recipient_id:source.row.owner_id,
  projection:{source:sourceEndpoint,target:targetEndpoint,audience:'public'},sender_id:who.id};
}
const projection=r=>({id:r.id,...JSON.parse(r.review_json).projection,accepted_at:r.decided_at});
export async function doorwayGet(env,u,who){
 if(u.pathname==='/api/doorways/public'){
  const after=Math.max(0,Math.floor(Number(u.searchParams.get('after'))||0));
  const pub=u.searchParams.get('publication');if(pub&&!hash.test(pub))fail('Choose a publication');
  const {results}=await env.DB.prepare(rows+` WHERE ${live} AND d.decision='accepted' AND d.seq>? AND (? IS NULL OR d.source_publication_id=? OR d.target_publication_id=?) ORDER BY d.seq LIMIT 100`).bind(after,pub,pub,pub).all();
  return {doorways:results.map(projection),next:results.length===100?results.at(-1).seq:null};
 }
 if(!who)fail('Sign in to review returned paths',401);
 if(u.pathname==='/api/doorways/sources'){
  const id=u.searchParams.get('inquiry');if(!hash.test(id||''))fail('Choose an inquiry');
  const {results}=await env.DB.prepare('SELECT p.id,p.title,o.login FROM publications p JOIN owners o ON o.id=p.owner_id WHERE p.inquiry_id=? AND p.withdrawn_at IS NULL').bind(id).all();return {publications:results};
 }
 if(u.pathname==='/api/doorways'){
  const after=Math.max(0,Math.floor(Number(u.searchParams.get('after'))||0));
  const {results}=await env.DB.prepare(rows+` WHERE (d.owner_id=? OR d.recipient_id=?) AND d.seq>? ORDER BY d.seq LIMIT 50`).bind(who.id,who.id,after).all();
  return {doorways:results.map(r=>({id:r.id,offer_id:r.offer_id,owner_id:r.owner_id,recipient_id:r.recipient_id,decision:r.decision,withdrawn:!!r.withdrawn_at,...JSON.parse(r.review_json).projection})),next:results.length===50?results.at(-1).seq:null};
 }
 const id=u.pathname.split('/')[3];if(!hash.test(id||''))fail('Choose a doorway',404);
 const r=await env.DB.prepare(rows+` WHERE d.id=? AND (d.owner_id=? OR d.recipient_id=?) AND ${live}`).bind(id,who.id,who.id).first();if(!r)fail('Doorway unavailable',404);
 const t=await publication(env,r.target_publication_id),content={source:JSON.parse(r.source_json),question:r.question,inquiry:t.bundle};
 return {id:r.id,decision:r.decision,review:JSON.parse(r.review_json),offer_json:canonical({format:'atlas-return-path',version:1,id:r.offer_id,content})};
}
export async function doorwayPost(env,path,who,data){
 if(path==='/api/doorways/review')return {review:await review(env,who,data)};
 if(data.reviewed!==true)fail('Review this exact doorway and its public audience');
 if(path==='/api/doorways/send'){
  const proposed=data.review,current=await review(env,who,proposed||{});if(canonical(current)!==canonical(proposed))fail('Doorway changed; review it again',409);
  const id=await sha(who.id+':doorway:'+current.offer_id);
  await env.DB.prepare(`INSERT INTO doorways(id,owner_id,recipient_id,source_publication_id,target_publication_id,offer_id,source_json,question,entry_json,review_json,created_at)
   SELECT ?,?,?,?,?,?,?,?,?,?,? WHERE (SELECT count(*) FROM doorways WHERE owner_id=?)<200
   AND EXISTS(SELECT 1 FROM publications WHERE id=? AND withdrawn_at IS NULL) AND EXISTS(SELECT 1 FROM publications WHERE id=? AND withdrawn_at IS NULL)
   AND NOT EXISTS(SELECT 1 FROM blocks WHERE (owner_id=? AND blocked_owner_id=?) OR (owner_id=? AND blocked_owner_id=?)) ON CONFLICT DO NOTHING`)
   .bind(id,who.id,current.recipient_id,current.source_publication_id,current.target_publication_id,current.offer_id,canonical(current.source),current.question,canonical(current.entry),canonical(current),now(),who.id,current.source_publication_id,current.target_publication_id,who.id,current.recipient_id,current.recipient_id,who.id).run();
  const saved=await env.DB.prepare('SELECT review_json,withdrawn_at FROM doorways WHERE id=?').bind(id).first();if(!saved||saved.withdrawn_at||saved.review_json!==canonical(current))fail('Offer unavailable, changed or preview limit reached',409);return {id};
 }
 const m=path.match(/^\/api\/doorways\/([a-f0-9]{64})\/(decide|withdraw)$/);if(!m)fail('Unknown doorway action',404);
 const r=await env.DB.prepare('SELECT * FROM doorways WHERE id=? AND (owner_id=? OR recipient_id=?)').bind(m[1],who.id,who.id).first();if(!r)fail('Doorway unavailable',404);
 if(m[2]==='withdraw'){await env.DB.prepare('UPDATE doorways SET withdrawn_at=COALESCE(withdrawn_at,?) WHERE id=?').bind(now(),r.id).run();return {withdrawn:true};}
 if(who.id!==r.recipient_id||!['accepted','declined'].includes(data.decision))fail('Only the original source owner decides',403);
 if(canonical(data.review)!==r.review_json)fail('Review the exact source, return and public connection');
 if(data.decision==='accepted'&&data.public_consent!==true)fail('Explicit public doorway consent is required');
 if(r.decision&&r.decision!==data.decision)fail('This offer already has a different decision',409);
 await env.DB.prepare(`UPDATE doorways SET decision=?,decided_at=? WHERE id=? AND decision IS NULL AND withdrawn_at IS NULL
  AND EXISTS(SELECT 1 FROM publications WHERE id=? AND withdrawn_at IS NULL) AND EXISTS(SELECT 1 FROM publications WHERE id=? AND withdrawn_at IS NULL)
  AND NOT EXISTS(SELECT 1 FROM blocks WHERE (owner_id=? AND blocked_owner_id=?) OR (owner_id=? AND blocked_owner_id=?))`)
 .bind(data.decision,now(),r.id,r.source_publication_id,r.target_publication_id,r.owner_id,r.recipient_id,r.recipient_id,r.owner_id).run();
 const result=await doorwayGet(env,new URL('/api/doorways/'+r.id,env.SITE_ORIGIN),who);if(result.decision!==data.decision)fail('Doorway is unavailable',409);return {id:r.id,decision:result.decision};
}
