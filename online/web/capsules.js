/* Read and explicitly receive online Capsules; prepared content comes from Personal Atlas. */
(() => {
 'use strict';
 const el=(tag,text,parent)=>{const n=document.createElement(tag);if(text)n.textContent=text;if(parent)parent.append(n);return n;};
 const dialog=el('dialog','',document.body),header=el('header','',dialog);dialog.id='online-capsules';el('h2','Capsules',header);
 const button=(text,parent,fn)=>{const b=el('button',text,parent);b.type='button';b.onclick=()=>run(fn);return b;};
 const status=el('p','',dialog);status.setAttribute('role','status');const content=el('div','',dialog);
 const run=async fn=>{status.textContent='';try{await fn();}catch(e){status.textContent=e.message;}};
 const api=async(path,data)=>{const r=await fetch(path,data===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}),d=await r.json();if(!r.ok)throw Error(d.error||'Capsule request failed');return d;};
 const reset=()=>{content.replaceChildren();dialog.scrollTop=0;};
 button('Close',header,()=>dialog.close());
 function consent(label,action,fn) {
  const row=el('label','',content),check=el('input','',row);check.type='checkbox';row.append(document.createTextNode(label));
  const b=button(action,content,async()=>{if(!check.checked||b.disabled)return;b.disabled=true;try{await fn();}finally{b.disabled=!check.checked;}});
  b.disabled=true;check.onchange=()=>{b.disabled=!check.checked;};
 }
 function exact(value){const d=el('details','',content);el('summary','Read every included field',d);el('pre',JSON.stringify(value,null,2),d);}
 function render(raw) {
  const c=JSON.parse(raw).content;el('h3',c.title,content);el('p',`${c.intent} · sharing name: ${c.author} (sender-supplied)`,content);
  el('pre',c.message,content);if(c.interpretation)el('pre',c.interpretation,content);
  for(const e of c.excerpts){for(const n of e.thoughts){el('p',n.kind,content);el('pre',n.text,content);if(n.notes)el('pre',n.notes,content);}
   if(e.answer!==null){el('h4','Included full answer',content);el('pre',e.answer,content);}if(e.question)el('pre',e.question.question,content);
   for(const b of e.evidence){el('p',b.summary,content);for(const ref of b.artifact_refs)el('pre',ref,content);}}
  exact(JSON.parse(raw));
 }
 async function read(id) {
  const d=await api('/api/capsules/'+id),me=(await api('/api/me')).owner;reset();button('Back to deliveries',content,()=>list());render(d.capsule_json);
  el('p',`Atlas sender: ${d.sender.login} · ${d.sender.verified?'GitHub verified':'synthetic'} · account ${d.sender.id}. Audience: ${d.audience}.`,content);
  if(d.source){el('h3','Original return source',content);if(d.source.capsule_json)render(d.source.capsule_json);else exact(d.source);}
  if(d.decision)el('p',`Source owner decision: ${d.decision}`,content);
  if(me.id===d.sender.id){consent('Withdraw from further online access. Existing copies remain.','Withdraw Capsule',async()=>{await api('/api/capsules/'+id+'/withdraw',{reviewed:true});await list('sent');});return;}
  el('p','Receipt keeps this in your account inbox. Download and import it into Personal Atlas to choose a private collaborator and prepare a return. No agent runs here.',content);
  consent('Keep this Capsule in my account inbox.','Acknowledge receipt',async()=>{await api('/api/capsules/'+id+'/receive',{reviewed:true});await read(id);});
  if(d.received_at) {
   button('Download exact Capsule JSON',content,()=>{const url=URL.createObjectURL(new Blob([d.capsule_json],{type:'application/json'})),a=el('a','',content);a.href=url;a.download=d.capsule_id.slice(0,12)+'.atlas-capsule.json';a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);});
   if(d.intent==='return'&&!d.decision){el('p','Acceptance records a private contribution relationship to this exact source. World doorways and shared contribution links are still being built.',content);
    for(const decision of ['accepted','declined'])consent(`I reviewed this return and its original source: ${decision}.`,decision==='accepted'?'Accept contribution':'Decline contribution',async()=>{await api('/api/capsules/'+id+'/decide',{reviewed:true,decision,source:d.source,capsule_id:d.capsule_id});await read(id);});}
  }
  el('p','Original online delivery ID (for a contextual return):',content);el('pre',id,content);
  consent(`Block further exchanges with ${d.sender.login}.`,'Block sender',async()=>{await api('/api/blocks',{owner_id:d.sender.id,blocked:true});await list();});
 }
 async function list(view='inbox',after=0) {
  reset();const me=(await api('/api/me')).owner;if(!me){el('p','Sign in with GitHub to read or receive Capsules.',content);const a=el('a','Sign in',content);a.href='/auth/login';return;}
  const nav=el('nav','',content);for(const [v,label] of [['inbox','Inbox'],['sent','Sent'],['public','Open invitations & offerings']])button(label,nav,()=>list(v));
  el('p','Prepare and send reviewed Capsules in your connected Personal Atlas. Check this inbox after reconnecting; receipt and acceptance are separate choices.',content);
  const data=await api(`/api/capsules?view=${view}&after=${after}`);if(!data.deliveries.length)el('p','No deliveries on this page.',content);
  for(const d of data.deliveries){const row=el('section','',content);el('p',`${d.title} · ${d.sender.login} · ${d.withdrawn?'withdrawn':d.decision||(d.received_at?'received':'awaiting receipt')}`,row);if(!d.withdrawn)button('Review Capsule',row,()=>read(d.id));}
  if(data.next)button('Next page',content,()=>list(view,data.next));
  const blocked=await api('/api/blocks');if(blocked.blocks.length){el('h3','Blocked accounts',content);for(const b of blocked.blocks)button(`Unblock ${b.login}`,content,async()=>{await api('/api/blocks',{owner_id:b.id,blocked:false});await list(view);});}
 }
 window.AtlasCapsules={open:id=>{if(!dialog.open)dialog.showModal();return run(()=>read(id));}};
 const trigger=document.getElementById('capsules-toggle');trigger.onclick=()=>{dialog.showModal();run(()=>list());};
 dialog.addEventListener('keydown',e=>e.stopPropagation());
})();
