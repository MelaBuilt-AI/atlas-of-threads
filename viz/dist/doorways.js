/* Presentation-only visit state. Acceptance and exact endpoints come from the server. */
(() => {
 'use strict';
 const key=d=>`atlas-doorway-visited:${d.scope}:${d.id}`;
 function arrivals(payload) {
  return (payload.external_doors||[]).map(door=>{
   const d={...door},entry=d.entry;
   try {
    if(d.returnOrigin&&new URLSearchParams(location.search).get('arrival')===d.id&&entry?.graph_id===payload.graph_id&&entry.node_id===payload.node.id)localStorage.setItem(key(d),'1');
    d.seen=d.returnOrigin||localStorage.getItem(key(d))==='1';
   }catch{d.seen=!!d.returnOrigin;}
   d.via=d.returnOrigin?'return to source':d.seen?'accepted path · visited':'accepted path · unvisited';
   d.labelKind=d.via;return d;
  });
 }
 function follow(door){
  const u=new URL(door.href,location.href);
  if(u.origin!==location.origin||!/^\/(?:inquiries\/[a-f0-9]{64}\/|player\/)?$/.test(u.pathname))return;
  location.assign(u.href);
 }
 window.TADoorways={arrivals,follow};
})();
