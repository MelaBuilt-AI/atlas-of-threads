import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const source=readFileSync('web/expeditions.js','utf8');
function runtime(){let time=1000;const c=vm.createContext({console,performance:{now:()=>time}});c.window=c;vm.runInContext(source,c);return {c,setTime:v=>time=v};}
test('live observer skips initial history, deduplicates and resets across hidden/offline/slow gaps and viewer changes',async()=>{
 const {c,setTime}=runtime(),seen=[],snapshots=[];let visible=true,offline=false,response={viewer:'a',cursor:10,server_time:100,events:[{seq:10,event_at:100}],ports:[]};
 const observer=c.AtlasExpeditionObserver(async()=>{if(offline)throw Error('synthetic offline');return response;},s=>snapshots.push(s),e=>seen.push(e.seq),()=>visible);
 await observer.poll([]);assert.deepEqual(seen,[]);
 setTime(3500);response={...response,cursor:11,events:[{seq:11,event_at:100}]};await observer.poll([]);assert.deepEqual(seen,[11]);
 setTime(6000);await observer.poll([]);assert.deepEqual(seen,[11]);
 visible=false;await observer.poll([]);visible=true;response={...response,cursor:12,events:[{seq:12,event_at:100}]};setTime(7000);await observer.poll([]);assert.deepEqual(seen,[11]);
 offline=true;await observer.poll([]);offline=false;response={...response,cursor:13,events:[{seq:13,event_at:100}]};await observer.poll([]);assert.deepEqual(seen,[11]);
 setTime(17000);response={...response,cursor:14,events:[{seq:14,event_at:100}]};await observer.poll([]);assert.deepEqual(seen,[11]);
 setTime(18000);response={...response,viewer:'b',cursor:15,events:[{seq:15,event_at:100}]};await observer.poll([]);assert.deepEqual(seen,[11]);
 setTime(20000);response={...response,cursor:16,server_time:200,events:[{seq:16,event_at:100}]};await observer.poll([]);assert.deepEqual(seen,[11]);
 assert.ok(snapshots.some(s=>s.unavailable));
});
test('hidden transition invalidates an in-flight response and does not consume new baseline as live',async()=>{
 const {c}=runtime();let resolve;const seen=[],snapshots=[];
 const observer=c.AtlasExpeditionObserver(()=>new Promise(r=>resolve=r),s=>snapshots.push(s),e=>seen.push(e),()=>true);
 const first=observer.poll([]);observer.reset();resolve({viewer:'a',cursor:5,events:[{seq:5,event_at:1}],ports:[]});await first;assert.equal(snapshots.length,0);assert.equal(seen.length,0);
});
test('renderer uses supplied relics, follows crown-first curves, preserves camera state, bounds flights and disposes generated effects',async()=>{
 const {c}=runtime();vm.runInContext(readFileSync('../viz/dist/three.min.js','utf8'),c);const T=c.THREE,models=[];
 c.RelicGLBLoader={load:async name=>{models.push(name);return new T.Mesh(new T.BoxGeometry(1,2,1),new T.MeshBasicMaterial());}};
 const sounds=[];c.TASound={expedition:(...args)=>sounds.push(args)};
 const scene=new T.Scene(),items=new Map([['a',{x:0,z:0,threadwalk_id:'a'}],['b',{x:30,z:30,threadwalk_id:'b'}]]);
 let reduced=false;const renderer=c.AtlasExpeditions(scene,items,()=>0,()=>reduced,()=>{}),state={x:0,z:0,span:80},saved={...state};
 renderer.sync([{id:'a',open:1,pending:0,accepted:0},{id:'b',open:0,pending:1,accepted:0}]);renderer.update(1000,state);
 const event={seq:1,kind:'launch',source_threadwalk_id:'a',target_threadwalk_id:'b',source:{x:0,z:0},target:{x:30,z:30}};
 renderer.witness(event,state);assert.equal(renderer.flights.length,1);assert.equal(sounds[0][0],'charge');
 renderer.update(4000,state);const f=renderer.flights[0];assert.equal(f.launched,true);assert.ok(f.group.position.y>2);
 assert.ok(new T.Vector3(0,1,0).applyQuaternion(f.group.quaternion).dot(f.curve.getTangent((3-1.6)/6.4))>.999);
 assert.ok(f.trail.geometry.attributes.position.array.every(Number.isFinite));assert.deepEqual(state,saved);
 const sparkPositions=Array.from(f.sparks.cores.geometry.attributes.position.array);
 assert.equal(f.sparks.cores.parent,f.group);assert.equal(f.sparks.tips.parent,f.group);assert.equal(f.sparks.branches.parent,f.group);
 renderer.update(4500,state);assert.notDeepEqual(Array.from(f.sparks.cores.geometry.attributes.position.array),sparkPositions);
 assert.ok(f.sparks.tips.geometry.attributes.position.array.every(v=>Number.isFinite(v)&&Math.abs(v)<4));
 let sparksDisposed=false;f.sparks.cores.geometry.addEventListener('dispose',()=>sparksDisposed=true);
 for(let i=0;i<20;i++)renderer.witness({...event,seq:2+i},state);assert.equal(renderer.flights.length,8);
 let disposed=false;f.trail.geometry.addEventListener('dispose',()=>disposed=true);renderer.update(15000,state);assert.ok(disposed);assert.ok(sparksDisposed);assert.equal(renderer.flights.length,0);
 reduced=true;renderer.witness(event,state);assert.equal(renderer.flights.length,0);
 renderer.sync([]);assert.equal(renderer.ports.size,0);assert.equal(renderer.picks.length,0);
 await Promise.resolve();assert.ok(models.some(m=>m.includes('charged-knowledge-capsule')));assert.ok(models.some(m=>m.includes('knowledge-ark-launcher-hologram')));
 const near=c.AtlasExpeditionSound({x:0,z:0},state),far=c.AtlasExpeditionSound({x:120,z:0},state),zoomed=c.AtlasExpeditionSound({x:0,z:0},{...state,span:260});
 assert.ok(near.gain>far.gain&&near.gain>zoomed.gain);assert.equal(c.AtlasExpeditionSound({x:200,z:0},state).gain,0);assert.ok(far.pan>0);
});
