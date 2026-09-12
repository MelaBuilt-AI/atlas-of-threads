import {fail} from './publication.js';

const now = () => Math.floor(Date.now()/1000);
export const moderator = (env, who) => !!who && !who.instance_id &&
  (env.MODERATOR_GITHUB_IDS || '').split(',').map(id => id.trim()).includes(who.id);

export function revokeAccount(env, id) {
  return [
    env.DB.prepare('DELETE FROM sessions WHERE owner_id=?').bind(id),
    env.DB.prepare('DELETE FROM pairings WHERE owner_id=?').bind(id),
    env.DB.prepare('UPDATE instances SET revoked_at=COALESCE(revoked_at,?) WHERE owner_id=?').bind(now(),id),
    env.DB.prepare('UPDATE activity SET enabled=0,expires_at=0 WHERE owner_id=?').bind(id),
  ];
}

export async function githubWebhook(r, env) {
  if (r.method !== 'POST') fail('Method not allowed',405);
  if (!env.GITHUB_WEBHOOK_SECRET) fail('GitHub webhook is not configured',503);
  const signature=r.headers.get('X-Hub-Signature-256') || '';
  if (!/^sha256=[a-f0-9]{64}$/.test(signature)) fail('Invalid webhook signature',403);
  // Verify the exact bytes, with a bounded read, before interpreting any payload.
  const reader=r.body?.getReader();
  if (!reader) fail('Missing webhook body');
  let length=0; const chunks=[];
  while (true) {
    const {done,value}=await reader.read(); if(done)break;
    length+=value.length;
    if(length>65536){await reader.cancel();fail('Webhook exceeds 64 KiB',413);}
    chunks.push(value);
  }
  const bytes=new Uint8Array(length); let offset=0;
  for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.length;}
  const key=await crypto.subtle.importKey('raw',new TextEncoder().encode(env.GITHUB_WEBHOOK_SECRET),{name:'HMAC',hash:'SHA-256'},false,['verify']);
  const digest=Uint8Array.from(signature.slice(7).match(/../g),pair=>parseInt(pair,16));
  if(!await crypto.subtle.verify('HMAC',key,digest,bytes))fail('Invalid webhook signature',403);
  let data;
  try { data=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes)); }
  catch { fail('Invalid webhook JSON'); }
  const event=r.headers.get('X-GitHub-Event');
  if(event==='ping')return {ok:true};
  if(event!=='github_app_authorization')return {ignored:true};
  if(data.action!=='revoked'||!Number.isSafeInteger(data.sender?.id)||data.sender.id<=0)fail('Invalid deauthorization event');
  const delivery=r.headers.get('X-GitHub-Delivery');
  if(!delivery||delivery.length>100)fail('Missing webhook delivery identity');
  const id=String(data.sender.id), time=Date.now();
  // All invalidation and the delivery receipt commit together. Replays are inert,
  // including after a new sign-in; only the numeric sender identifies the owner.
  const unseen='NOT EXISTS(SELECT 1 FROM github_deliveries WHERE id=?)';
  const result=await env.DB.batch([
    env.DB.prepare(`INSERT INTO github_revocations SELECT ?,? WHERE ${unseen} ON CONFLICT(owner_id) DO UPDATE SET revoked_at=excluded.revoked_at`).bind(id,time,delivery),
    env.DB.prepare(`DELETE FROM sessions WHERE owner_id=? AND ${unseen}`).bind(id,delivery),
    env.DB.prepare(`DELETE FROM pairings WHERE owner_id=? AND ${unseen}`).bind(id,delivery),
    env.DB.prepare(`UPDATE instances SET revoked_at=COALESCE(revoked_at,?) WHERE owner_id=? AND ${unseen}`).bind(now(),id,delivery),
    env.DB.prepare(`UPDATE activity SET enabled=0,expires_at=0 WHERE owner_id=? AND ${unseen}`).bind(id,delivery),
    env.DB.prepare('INSERT INTO github_deliveries VALUES(?,?) ON CONFLICT DO NOTHING').bind(delivery,now()),
  ]);
  return {revoked:true,reused:!result.at(-1).meta.changes};
}

export async function activityGet(env, who) {
  const row=await env.DB.prepare('SELECT enabled,expires_at FROM activity WHERE owner_id=?').bind(who.id).first();
  return {enabled:!!row?.enabled,active:!!row?.enabled && row.expires_at>now()};
}

export async function activityPost(env, who, data, sessionHash) {
  if(who.instance_id)fail('Choose activity sharing in your signed-in browser',403);
  if(data.action==='heartbeat') {
    await env.DB.prepare('UPDATE activity SET expires_at=? WHERE owner_id=? AND enabled=1 AND EXISTS(SELECT 1 FROM sessions WHERE hash=? AND owner_id=? AND expires_at>?)').bind(now()+90,who.id,sessionHash,who.id,now()).run();
  } else {
    if(typeof data.enabled!=='boolean')fail('Choose whether to share activity');
    await env.DB.prepare('INSERT INTO activity SELECT ?,?,? WHERE EXISTS(SELECT 1 FROM sessions WHERE hash=? AND owner_id=? AND expires_at>?) ON CONFLICT(owner_id) DO UPDATE SET enabled=excluded.enabled,expires_at=excluded.expires_at')
      .bind(who.id,Number(data.enabled),data.enabled?now()+90:0,sessionHash,who.id,now()).run();
  }
  return activityGet(env,who);
}

export async function reportsGet(env, who, url) {
  if(!moderator(env,who))fail('Report review requires a moderator browser session',403);
  const status=url.searchParams.get('status') || 'open';
  if(!['open','dismissed','withdrawn'].includes(status))fail('Unknown report status');
  const after=Math.max(0,Math.floor(Number(url.searchParams.get('after'))||0));
  const {results}=await env.DB.prepare(`SELECT r.rowid AS cursor,r.*,p.title,p.owner_id AS publisher_id,p.withdrawn_at,o.login AS reporter_login
    FROM reports r JOIN publications p ON p.id=r.publication_id JOIN owners o ON o.id=r.owner_id
    WHERE r.status=? AND r.rowid>? ORDER BY r.rowid LIMIT 50`).bind(status,after).all();
  return {reports:results,next:results.length===50?results.at(-1).cursor:null};
}

export async function reportsPost(env,who,data) {
  if(!moderator(env,who))fail('Report review requires a moderator browser session',403);
  if(!['dismissed','withdrawn'].includes(data.status)||typeof data.note!=='string'||!data.note.trim()||data.note.length>2000)fail('Choose a decision and record its reason');
  const row=await env.DB.prepare('SELECT r.*,p.object_key FROM reports r JOIN publications p ON p.id=r.publication_id WHERE r.publication_id=? AND r.owner_id=?')
    .bind(data.publication_id || '',data.reporter_id || '').first();
  if(!row)fail('Report not found',404);
  if(row.status!=='open'){
    if(row.status!==data.status)fail('This report already has a different decision',409);
    if(row.status==='withdrawn')await env.INQUIRIES.delete(row.object_key);
    return {reviewed:true,reused:true};
  }
  const statements=[];
  if(data.status==='withdrawn') {
    if(data.confirm_withdrawal!==true)fail('Confirm removal of this exact public snapshot');
    statements.push(env.DB.prepare(`UPDATE publications SET withdrawn_at=COALESCE(withdrawn_at,?) WHERE id=?
      AND EXISTS(SELECT 1 FROM reports WHERE publication_id=? AND owner_id=? AND status='open')`)
      .bind(now(),row.publication_id,row.publication_id,row.owner_id));
  }
  statements.push(env.DB.prepare("UPDATE reports SET status=?,reviewed_by=?,reviewed_at=?,review_note=? WHERE publication_id=? AND owner_id=? AND status='open'")
    .bind(data.status,who.id,now(),data.note.trim(),row.publication_id,row.owner_id));
  await env.DB.batch(statements);
  const saved=await env.DB.prepare('SELECT status FROM reports WHERE publication_id=? AND owner_id=?').bind(row.publication_id,row.owner_id).first();
  if(saved.status!==data.status)fail('Another moderator already decided this report',409);
  if(data.status==='withdrawn')await env.INQUIRIES.delete(row.object_key);
  return {reviewed:true};
}
