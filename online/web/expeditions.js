/* Live observation is separate from durable expedition history. */
(() => {
 'use strict';
 window.AtlasExpeditionObserver = (fetchSnapshot, snapshot, witness, visible) => {
  let cursor=null, viewer=null, generation=0, busy=false, lastSuccess=0;
  const reset=()=>{generation++;cursor=null;lastSuccess=0;};
  async function poll(ports) {
   if(!visible()){reset();return;}
   if(busy)return;
   const stamp=generation, previous=cursor, started=performance.now();busy=true;
   try {
    const data=await fetchSnapshot(ports,cursor);
    if(stamp!==generation||!visible())return;
    const continuous=previous!==null&&viewer===data.viewer&&started-lastSuccess<8000&&performance.now()-started<8000;
    snapshot({...data,viewer_changed:viewer!==data.viewer});
    // A reload, hidden tab, interrupted connection or slow backlog starts a fresh baseline.
    if(continuous)for(const e of data.events.slice(-8))if(e.seq>previous&&data.server_time-e.event_at<=8)witness(e);
    viewer=data.viewer;cursor=data.cursor;lastSuccess=performance.now();
   } catch {reset();snapshot({ports:[],events:[],viewer:null,unavailable:true});}
   finally{busy=false;}
  }
  return {poll,reset};
 };
 window.AtlasExpeditionSound = (point,state) => {
  const dx=point.x-state.x,dz=point.z-state.z,distance=Math.hypot(dx,dz);
  return {gain:Math.max(0,1-distance/140)*Math.min(1,55/state.span)*.7,pan:Math.max(-1,Math.min(1,(dx-dz)/(state.span*1.4)))};
 };
 window.AtlasExpeditions = (scene,items,height,reduced,openHistory) => {
  const T=THREE, ports=new Map(),flights=[],picks=[],up=new T.Vector3(0,1,0);
  let latest=[],time=0;
  function dispose(group) {
   group.parent?.remove(group);
   group.traverse(o=>{o.userData.disposed=true;if(!o.userData.sharedRelic)o.geometry?.dispose();if(o.material)for(const m of Array.isArray(o.material)?o.material:[o.material])m.dispose();});
  }
  function mount(parent,name,size) {
   RelicGLBLoader.load(`./assets/models/${name}.glb`).then(model=>{
    if(!parent.parent||parent.userData.disposed){model.traverse(o=>o.material?.dispose());return;}
    model.traverse(o=>{o.userData.sharedRelic=true;});
    const box=new T.Box3().setFromObject(model),dim=box.getSize(new T.Vector3()),center=box.getCenter(new T.Vector3()),scale=size/Math.max(dim.x,dim.y,dim.z);
    model.scale.setScalar(scale);model.position.set(-center.x*scale,-box.min.y*scale,-center.z*scale);parent.add(model);
   }).catch(()=>{}); // The geometric port remains selectable when a model cannot load.
  }
  function createPort(item,data) {
   const group=new T.Group();group.position.set(item.x+6,height(item.x,item.z)+.4,item.z+4);scene.add(group);
   const pad=new T.Mesh(new T.CylinderGeometry(3,3.6,.6,32),new T.MeshStandardMaterial({color:0x384a61,metalness:.65,roughness:.4}));group.add(pad);
   const ring=new T.Mesh(new T.TorusGeometry(2.8,.13,8,48),new T.MeshBasicMaterial({color:0xffc473,transparent:true,opacity:.85}));ring.rotation.x=Math.PI/2;ring.position.y=.5;group.add(ring);
   const beacon=new T.Mesh(new T.CylinderGeometry(.13,.35,8,12),new T.MeshBasicMaterial({color:0xffc473,transparent:true,opacity:.65,depthWrite:false,blending:T.AdditiveBlending}));beacon.position.y=4;group.add(beacon);
   const hit=new T.Mesh(new T.CylinderGeometry(3.5,3.5,7,12),new T.MeshBasicMaterial({visible:false}));hit.position.y=3;hit.userData.expeditionPort=item.threadwalk_id;group.add(hit);picks.push(hit);
   const model=new T.Group();model.position.y=.3;group.add(model);
   const result={group,ring,beacon,hit,model,data,loaded:false,modelKind:null,pulse:0};ports.set(item.threadwalk_id,result);return result;
  }
  function sync(data) {
   latest=data;const active=new Set(data.map(p=>p.id));
   for(const [id,p] of ports)if(!active.has(id)||!items.has(id)){picks.splice(picks.indexOf(p.hit),1);dispose(p.group);ports.delete(id);}
   for(const d of data){const item=items.get(d.id);if(!item)continue;const p=ports.get(d.id)||createPort(item,d);p.data=d;p.beacon.visible=!!(d.open||d.pending);p.ring.material.color.setHex(d.accepted?0x87e9bc:0xffc473);}
  }
  function sound(phase,position,state) {
   const {gain,pan}=AtlasExpeditionSound(position,state);if(gain>.01)window.TASound?.expedition(phase,gain,pan);
  }
  function witness(event,state) {
   if(reduced())return;
   if(event.kind==='accepted'){const p=ports.get(event.target_threadwalk_id);if(p)p.pulse=time+1800;return;}
   if(!event.source||!items.has(event.source_threadwalk_id)||flights.length>=8)return;
   const s=event.source,end=event.target;
   // No source port means no invented launch from an unrelated Threadwalk.
   if(Math.hypot(s.x-state.x,s.z-state.z)>state.span*1.4+30)return;
   const start=new T.Vector3(s.x+6,height(s.x,s.z)+2,s.z+4);
   const target=end?new T.Vector3(end.x+6,height(end.x,end.z)+3,end.z+4):start.clone().add(new T.Vector3(14,24,-18));
   const lift=Math.min(35,12+start.distanceTo(target)*.22);
   const curve=new T.CubicBezierCurve3(start,start.clone().add(new T.Vector3(0,lift,0)),target.clone().add(new T.Vector3(0,end?lift:5,0)),target);
   const group=new T.Group();scene.add(group);group.position.copy(start);
   const capsule=new T.Group();group.add(capsule);mount(capsule,'charged-knowledge-capsule',2.4);
   const core=new T.Mesh(new T.OctahedronGeometry(.35),new T.MeshBasicMaterial({color:0xffe4a1}));group.add(core);
   const flame=new T.Mesh(new T.ConeGeometry(.28,2.2,12,1,true),new T.MeshBasicMaterial({color:0xffac45,transparent:true,opacity:.85,depthWrite:false,blending:T.AdditiveBlending,side:T.DoubleSide}));flame.rotation.z=Math.PI;flame.position.y=-1.2;group.add(flame);
   const trail=new T.Points(new T.BufferGeometry().setAttribute('position',new T.BufferAttribute(new Float32Array(96*3),3)),new T.PointsMaterial({color:0xffbd66,size:.85,transparent:true,opacity:.8,depthWrite:false,blending:T.AdditiveBlending}));trail.visible=false;scene.add(trail);
   const charge=new T.Group();scene.add(charge);charge.position.copy(start).add(new T.Vector3(0,-1,0));mount(charge,'knowledge-ark-launcher-hologram',4);
   const halo=new T.Mesh(new T.TorusGeometry(3,.2,8,48),new T.MeshBasicMaterial({color:0xffcf87,transparent:true,opacity:.8,blending:T.AdditiveBlending}));halo.rotation.x=Math.PI/2;charge.add(halo);
   flights.push({event,group,flame,trail,charge,halo,curve,born:time,launched:false});sound('charge',start,state);
  }
  function clearFlights(){for(const f of flights){dispose(f.group);dispose(f.trail);dispose(f.charge);}flights.length=0;}
  function update(now,state) {
   time=now;if(reduced())clearFlights();
   for(const [id,p] of ports){const item=items.get(id);if(!item)continue;const distance=Math.hypot(item.x-state.x,item.z-state.z),near=state.span<190&&distance<state.span;
    const modelKind=p.data.open||p.data.pending?'knowledge-ark-launcher':'knowledge-ark-launcher-post-launch';
    if(near&&p.modelKind!==modelKind){dispose(p.model);p.model=new T.Group();p.model.position.y=.3;p.group.add(p.model);p.modelKind=modelKind;mount(p.model,modelKind,4.5);}
    p.model.visible=near;p.group.visible=distance<state.span*1.5;
    p.ring.material.opacity=reduced()?.85:p.pulse>now?.6+Math.sin(now*.015)*.4:.7+Math.sin(now*.002)*.15;
    p.beacon.material.opacity=reduced()?.65:.48+Math.sin(now*.003)*.2;
   }
   for(let i=flights.length-1;i>=0;i--){const f=flights[i],age=(now-f.born)/1000;
    if(age>=10){dispose(f.group);dispose(f.trail);dispose(f.charge);flights.splice(i,1);continue;}
    const progress=Math.max(0,Math.min(1,(age-1.6)/6.4));
    if(age>=1.6&&!f.launched){f.launched=true;sound('launch',f.curve.v0,state);dispose(f.charge);const port=ports.get(f.event.source_threadwalk_id);if(port)port.pulse=now+1500;}
    f.group.visible=age>=1.6&&age<8;f.trail.visible=age>=1.6;
    if(!f.launched){f.halo.scale.setScalar(.7+age*.35);continue;}
    f.group.position.copy(f.curve.getPoint(progress));f.group.quaternion.setFromUnitVectors(up,f.curve.getTangent(progress).normalize());f.flame.scale.y=.8+Math.sin(now*.04)*.2;
    const positions=f.trail.geometry.attributes.position;
    for(let j=0;j<96;j++){const u=Math.max(0,progress-j*.003),point=f.curve.getPoint(u),spread=j*.012;point.x+=Math.sin(j*2.17+age)*spread;point.z+=Math.cos(j*1.61+age)*spread;positions.setXYZ(j,point.x,point.y,point.z);}
    positions.needsUpdate=true;f.trail.material.opacity=age>8?.8*(10-age)/2:.8;
   }
  }
  return {sync,witness,update,clearFlights,picks,ports,flights,history:id=>openHistory(id),dispose:()=>{clearFlights();sync([]);},refresh:()=>sync(latest)};
 };
})();
