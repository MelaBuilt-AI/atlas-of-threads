import {fail,position} from './publication.js';
// Visibility is inherited from the actual delivery, including on followed updates.
export const expeditionVisible = `(d.owner_id=? OR d.recipient_id=? OR (d.audience='public' AND d.withdrawn_at IS NULL))
 AND NOT EXISTS(SELECT 1 FROM blocks b WHERE (b.owner_id=d.owner_id AND b.blocked_owner_id=?) OR (b.owner_id=? AND b.blocked_owner_id=d.owner_id))`;
export const expeditionBindings = who => [who.id,who.id,who.id,who.id];
const target = 'COALESCE(d.target_publication_id,d.reply_publication_id,parent.source_publication_id)';
const joins = `FROM capsule_deliveries d
 LEFT JOIN capsule_deliveries parent ON parent.id=d.reply_delivery_id
 LEFT JOIN publications p ON p.id=d.source_publication_id
 LEFT JOIN publications t ON t.id=${target}
 LEFT JOIN capsule_receipts receipt ON receipt.delivery_id=d.id AND receipt.owner_id=d.recipient_id`;
const fields = `d.id,d.title,d.intent,d.audience,d.created_at,d.withdrawn_at,d.owner_id,d.recipient_id,
 p.threadwalk_id AS source_threadwalk_id,t.threadwalk_id AS target_threadwalk_id,
 receipt.received_at,receipt.decision,receipt.decided_at`;
export function launchRecords(env,id) {
 return [env.DB.prepare(`INSERT INTO expedition_events(delivery_id,kind,created_at)
  SELECT id,'launch',created_at FROM capsule_deliveries WHERE id=? ON CONFLICT DO NOTHING`).bind(id),
 env.DB.prepare(`INSERT INTO updates(threadwalk_id,publication_id,kind,created_at,capsule_event_id)
  SELECT p.threadwalk_id,p.id,'capsule-'||d.intent,e.created_at,e.seq FROM expedition_events e
  JOIN capsule_deliveries d ON d.id=e.delivery_id JOIN publications p ON p.id=d.source_publication_id
  WHERE d.id=? AND e.kind='launch' ON CONFLICT DO NOTHING`).bind(id)];
}
export function acceptanceRecords(env,id,owner) {
 return [env.DB.prepare(`INSERT INTO expedition_events(delivery_id,kind,created_at)
  SELECT delivery_id,'accepted',decided_at FROM capsule_receipts WHERE delivery_id=? AND owner_id=? AND decision='accepted' ON CONFLICT DO NOTHING`).bind(id,owner),
 env.DB.prepare(`INSERT INTO updates(threadwalk_id,publication_id,kind,created_at,capsule_event_id)
  SELECT t.threadwalk_id,t.id,'capsule-accepted',e.created_at,e.seq FROM expedition_events e
  JOIN capsule_deliveries d ON d.id=e.delivery_id LEFT JOIN capsule_deliveries parent ON parent.id=d.reply_delivery_id
  JOIN publications t ON t.id=${target} WHERE d.id=? AND e.kind='accepted' ON CONFLICT DO NOTHING`).bind(id)];
}
export async function expeditions(env,u,who) {
 if(!who)return {viewer:null,cursor:0,events:[],ports:[],deliveries:[],next:null};
 if(u.pathname==='/api/expeditions/history') {
  const id=u.searchParams.get('threadwalk');if(!/^[a-f0-9]{64}$/.test(id||''))fail('Choose a Threadwalk port');
  const before=Math.max(0,Math.floor(Number(u.searchParams.get('before'))||0));
  const {results}=await env.DB.prepare(`SELECT d.seq,${fields} ${joins} WHERE ${expeditionVisible}
   AND (p.threadwalk_id=? OR t.threadwalk_id=?) AND (?=0 OR d.seq<?) ORDER BY d.seq DESC LIMIT 50`)
   .bind(...expeditionBindings(who),id,id,before,before).all();
  return {deliveries:results,next:results.length===50?results.at(-1).seq:null};
 }
 const ids=(u.searchParams.get('ports')||'').split(',').filter(Boolean);
 if(ids.length>100||ids.some(id=>!/^[a-f0-9]{64}$/.test(id)))fail('Choose up to 100 visible ports');
 const cursor=(await env.DB.prepare('SELECT COALESCE(max(seq),0) seq FROM expedition_events').first()).seq;
 const after=u.searchParams.has('after')?Number(u.searchParams.get('after')):null;
 if(after!==null&&(!Number.isSafeInteger(after)||after<0||after>cursor))fail('Refresh the expedition stream');
 let events=[];
 if(after!==null) {
  const result=await env.DB.prepare(`SELECT e.seq,e.kind,e.created_at AS event_at,${fields} ${joins}
   JOIN expedition_events e ON e.delivery_id=d.id WHERE e.seq>? AND e.seq<=? AND ${expeditionVisible}
   AND d.withdrawn_at IS NULL ORDER BY e.seq LIMIT 100`).bind(after,cursor,...expeditionBindings(who)).all();events=result.results;
 }
 // Only publications that are still visible as an ongoing locale supply map endpoints.
 const wanted=[...new Set([...ids,...events.flatMap(e=>[e.source_threadwalk_id,e.target_threadwalk_id]).filter(Boolean)])];
 const {results:places}=wanted.length?await env.DB.prepare(`SELECT p.threadwalk_id,p.title,
  (SELECT min(seq) FROM publications first WHERE first.threadwalk_id=p.threadwalk_id) AS world_seq
  FROM publications p WHERE p.threadwalk_id IN (SELECT value FROM json_each(?)) AND p.withdrawn_at IS NULL AND p.seq=(SELECT max(seq) FROM publications last WHERE last.threadwalk_id=p.threadwalk_id)`).bind(JSON.stringify(wanted)).all():{results:[]};
 const locations=new Map(places.map(p=>[p.threadwalk_id,{id:p.threadwalk_id,title:p.title,...position(p.world_seq)}]));
 events=events.map(e=>({...e,source:locations.get(e.source_threadwalk_id)||null,target:locations.get(e.target_threadwalk_id)||null}));
 const ports=[];
 if(ids.length) {
  const selection="SELECT value FROM json_each(?)";
  const {results}=await env.DB.prepare(`WITH visible AS (SELECT ${fields} ${joins} WHERE ${expeditionVisible}
   AND (p.threadwalk_id IN (${selection}) OR t.threadwalk_id IN (${selection})))
   SELECT first.threadwalk_id AS id,count(*) AS visible_expeditions,
    sum(CASE WHEN v.source_threadwalk_id=first.threadwalk_id AND v.withdrawn_at IS NULL AND v.audience='public' AND v.intent='invitation' THEN 1 ELSE 0 END) AS open,
    sum(CASE WHEN v.target_threadwalk_id=first.threadwalk_id AND v.withdrawn_at IS NULL AND v.received_at IS NULL THEN 1 ELSE 0 END) AS pending,
    sum(CASE WHEN v.target_threadwalk_id=first.threadwalk_id AND v.decision='accepted' THEN 1 ELSE 0 END) AS accepted
   FROM publications first JOIN visible v ON v.source_threadwalk_id=first.threadwalk_id OR v.target_threadwalk_id=first.threadwalk_id
   WHERE first.id=first.threadwalk_id AND first.threadwalk_id IN (${selection}) GROUP BY first.threadwalk_id`)
   .bind(...expeditionBindings(who),JSON.stringify(ids),JSON.stringify(ids),JSON.stringify(ids)).all();
  ports.push(...results.filter(p=>locations.has(p.id)));
 }
 return {viewer:who.id,cursor:events.length===100?events.at(-1).seq:cursor,server_time:Math.floor(Date.now()/1000),events,ports};
}
