/* Explicit contribution links, separate from geographic roads. */
(() => {
 'use strict';
 const el=(tag,text,parent)=>{const n=document.createElement(tag);if(text)n.textContent=text;if(parent)parent.append(n);return n;};
 const api=async(path,data)=>{const r=await fetch(path,data===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}),d=await r.json();if(!r.ok)throw Error(d.error||'Doorway unavailable');return d;};
 const dialog=el('dialog','',document.body);dialog.id='shared-doorways';dialog.className='return-path-dialog';
 const header=el('header','',dialog);el('h2','Returned doorways',header);const status=el('p','',dialog),content=el('div','',dialog);status.setAttribute('role','status');
 const run=async fn=>{status.textContent='';try{await fn();}catch(e){status.textContent=e.message;}};
 const button=(label,parent,fn)=>{const b=el('button',label,parent);b.onclick=()=>run(fn);return b;};
 button('Close',header,()=>dialog.close());dialog.addEventListener('keydown',e=>e.stopPropagation());
 const exact=value=>{const d=el('details','',content);el('summary','Inspect exact contents',d);el('pre',JSON.stringify(value,null,2),d);};
 function consent(label,action,fn){const l=el('label','',content),c=el('input','',l);c.type='checkbox';l.append(document.createTextNode(label));const b=button(action,content,async()=>{if(!c.checked||b.disabled)return;b.disabled=true;try{await fn();}finally{b.disabled=!c.checked;}});b.disabled=true;c.onchange=()=>b.disabled=!c.checked;}
 async function read(id){
  const d=await api('/api/doorways/'+id),me=(await api('/api/me')).owner,offer=JSON.parse(d.offer_json);content.replaceChildren();
  el('h3',`${d.review.projection.source.title} → ${d.review.projection.target.title}`,content);
  el('p',`State: ${d.decision||'pending'}. This full returned inquiry is already published. Accepting shares the exact chamber connection publicly.`,content);
  for(const r of offer.content.inquiry.content.graphs){el('h4',r.graph.model.name,content);el('pre',r.graph.prose,content);for(const n of r.graph.nodes)el('p',n.text,content);}
  el('p',`Original source chamber: ${d.review.projection.source.thought}`,content);
  el('p',`Returned entry: ${d.review.projection.target.thought}`,content);
  exact(d.review.projection);exact(offer);
  if(me.id===d.review.recipient_id&&!d.decision){
   consent('I reviewed both endpoints and this complete return. Make the exact doorway public.','Accept public doorway',async()=>{await api('/api/doorways/'+id+'/decide',{reviewed:true,review:d.review,decision:'accepted',public_consent:true});await read(id);});
   consent('Decline this doorway proposal.','Decline doorway',async()=>{await api('/api/doorways/'+id+'/decide',{reviewed:true,review:d.review,decision:'declined'});await read(id);});
  }
  button('Download exact returned path',content,()=>{const url=URL.createObjectURL(new Blob([d.offer_json],{type:'application/json'})),a=el('a');a.href=url;a.download=offer.id.slice(0,12)+'.atlas-return.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
  el('p','Download or use connected Personal Atlas to receive and accept locally. Reading here never imports graphs or calls an agent.',content);
  consent('Withdraw this online doorway. Existing imports remain available.','Withdraw doorway',async()=>{await api('/api/doorways/'+id+'/withdraw',{reviewed:true});await list();});
  button('Back to doorways',content,()=>list());
 }
 async function list(after=0){content.replaceChildren();el('p','Violet connections join explicitly accepted contributions. Geographic roads remain separate. Prepare a full returned path in Personal Atlas to offer a doorway.',content);
  const shared=await api('/api/doorways/public?after='+after);
  for(const d of shared.doorways){const row=el('section','',content);el('h3',`${d.source.title} → ${d.target.title}`,row);el('p',`${d.source.thought} → ${d.target.thought}`,row);
   button('Enter source chamber',row,()=>{dialog.close();window.AtlasDoorwayWorld.enter(d.source);});
   button('Enter returned chamber',row,()=>{dialog.close();window.AtlasDoorwayWorld.enter(d.target,d.id);});}
  if(!shared.doorways.length)el('p','No shared doorways on this page.',content);
  if(shared.next)button('More shared doorways',content,()=>list(shared.next));
  const me=(await api('/api/me')).owner;if(me)button('My proposals and decisions',content,()=>mine());
 }
 async function mine(after=0){const data=await api('/api/doorways?after='+after);content.replaceChildren();for(const d of data.doorways){const row=el('section','',content);el('p',`${d.source.title} → ${d.target.title} · ${d.withdrawn?'withdrawn':d.decision||'pending'}`,row);if(!d.withdrawn)button('Review doorway',row,()=>read(d.id));}if(!data.doorways.length)el('p','No doorway proposals on this page.',content);if(data.next)button('Next page',content,()=>mine(data.next));button('Shared doorways',content,()=>list());}
 document.getElementById('doorways-toggle').onclick=()=>{dialog.showModal();run(()=>list());};
 window.AtlasContributionLines=(scene,items,height)=>{
  const lines=new Map();
  function clear(id){const mesh=lines.get(id);scene.remove(mesh);mesh.geometry.dispose();mesh.material.dispose();lines.delete(id);}
  return {sync(data){const active=new Set();for(const d of data){const s=items.get(d.source.threadwalk_id),t=items.get(d.target.threadwalk_id);if(!s||!t)continue;active.add(d.id);if(lines.has(d.id))continue;
   const a=new THREE.Vector3(s.x,height(s.x,s.z)+3,s.z),b=new THREE.Vector3(t.x,height(t.x,t.z)+3,t.z),mid=a.clone().lerp(b,.5);mid.y+=12;
   const curve=new THREE.QuadraticBezierCurve3(a,mid,b),mesh=new THREE.Mesh(new THREE.TubeGeometry(curve,40,.16,6,false),new THREE.MeshBasicMaterial({color:0xc2a0ff,transparent:true,opacity:.7}));scene.add(mesh);lines.set(d.id,mesh);
  }for(const id of lines.keys())if(!active.has(id))clear(id);},dispose(){for(const id of lines.keys())clear(id);},lines};
 };
})();
