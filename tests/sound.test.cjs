const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const code = fs.readFileSync(path.join(__dirname, '../viz/dist/sound.js'), 'utf8');
const flush = () => new Promise(resolve => setImmediate(resolve));

function effects(saved = {}) {
  class Events {
    constructor() { this.listeners = {}; this.attributes = {}; this.dataset = {}; }
    addEventListener(event, handler) { (this.listeners[event] ||= []).push(handler); }
    fire(event, props = {}) { for (const fn of this.listeners[event] || []) fn({target:this, ...props}); }
    setAttribute(key, value) { this.attributes[key] = value; }
    contains(target) { return target === this; }
  }
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Events()); return elements.get(id); };
  const document = new Events();
  document.getElementById = get; document.hidden = false; document.focused = true;
  document.hasFocus = () => document.focused;
  const param = (value = 1) => ({value, cancelScheduledValues(){},
    setTargetAtTime(v){this.value=v;}, setValueAtTime(v){this.value=v;}, exponentialRampToValueAtTime(v){this.value=v;}});
  const node = () => ({connections:[], connect(to){this.connections.push(to);return to;}, disconnect(){}});
  let context;
  class Context extends Events {
    constructor() { super(); context=this; this.state='suspended'; this.currentTime=0;
      this.destination=node(); this.gains=[]; this.sources=[]; this.canResume=true; this.resumeCalls=0; }
    async resume() { this.resumeCalls++; if(this.canResume) this.state='running'; this.fire('statechange'); }
    createGain() { const n={...node(),gain:param()};this.gains.push(n);return n; }
    createStereoPanner() { return {...node(),pan:param(0)}; }
    createDynamicsCompressor() { return {...node(),threshold:param(),knee:param(),ratio:param(),attack:param(),release:param()}; }
    createBufferSource() { const n={...node(),start(){this.started=true;},stop(){}};this.sources.push(n);return n; }
    async decodeAudioData() { return {duration:1}; }
  }
  const storage = {'thought-archaeology.sound.v1':JSON.stringify(saved)};
  const window = new Events(); Object.assign(window, { AudioContext:Context,
    fetch:async()=>({ok:true,arrayBuffer:async()=>new ArrayBuffer(2)}),
    localStorage:{getItem:key=>storage[key],setItem:(key,value)=>{storage[key]=value;}}, console, setTimeout });
  vm.runInNewContext(code, {window,document});
  return {window,document,get,storage,context:()=>context};
}

test('effects decode and route a test cue through audible master to destination', async () => {
  const p=effects();
  p.window.fire('click'); await flush();
  const ctx=p.context();
  assert.equal(ctx.state,'running');
  assert.equal(p.get('sound-toggle').textContent,'Pause effects · S');
  const master=ctx.gains[0];
  assert.ok(master.gain.value > 0);
  assert.equal(master.connections[0].connections[0],ctx.destination);
  const before=ctx.sources.length;
  p.get('sound-test').fire('click'); await flush();
  assert.equal(ctx.sources.length,before+1);
  const cue=ctx.sources.at(-1);
  assert.equal(cue.started,true);
  assert.ok(cue.connections[0].gain.value>0);
  assert.equal(cue.connections[0].connections[0],ctx.gains[2]);
  assert.equal(ctx.gains[2].connections[0],master);
});

test('native effects slider input retains the new value after awaken renders controls', async () => {
  const p=effects();await p.window.TASound.awaken();
  p.get('sound-volume').value='30';p.get('sound-volume').fire('input');await flush();
  assert.equal(p.get('sound-volume').value,'30');
  assert.equal(JSON.parse(p.storage['thought-archaeology.sound.v1']).level,.3);
  assert.ok(p.context().gains[0].gain.value>0);
});

test('effects retry interrupted/suspended context on later gestures and display actual readiness', async () => {
  const p=effects();await p.window.TASound.awaken();
  const ctx=p.context();ctx.state='interrupted';ctx.canResume=false;ctx.fire('statechange');
  assert.equal(p.get('sound-toggle').textContent,'Start effects · S');
  p.window.fire('pointerdown');await flush();
  assert.equal(ctx.state,'interrupted');
  ctx.canResume=true;p.window.fire('click');await flush();
  assert.equal(ctx.state,'running');
  assert.equal(p.get('sound-toggle').textContent,'Pause effects · S');
  ctx.state='suspended';p.window.fire('keydown');await flush();
  assert.equal(ctx.state,'running');
});

test('background effects are silent and returning preserves user mute and volume', async () => {
  const p=effects();await p.window.TASound.awaken();
  const master=p.context().gains[0];const original=master.gain.value;
  p.document.hidden=true;p.document.fire('visibilitychange');assert.equal(master.gain.value,0);
  p.document.hidden=false;p.document.fire('visibilitychange');assert.equal(master.gain.value,original);
  p.window.TASound.toggleMuted();await flush();
  p.document.focused=false;p.window.fire('blur');p.document.focused=true;p.window.fire('focus');
  assert.equal(master.gain.value,0);
  assert.equal(p.get('sound-volume').value,'58');
  const before=p.context().sources.length;p.get('sound-test').fire('click');await flush();
  assert.equal(p.context().sources.length,before);
  assert.match(p.get('sound-status').textContent,/Resume effects/);
});
