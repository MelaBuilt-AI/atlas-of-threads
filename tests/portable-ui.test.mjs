/* Execute the browser adapter with synthetic DOM/network boundaries. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
const source = readFileSync(new URL('../viz/dist/portable.js', import.meta.url), 'utf8');
const inquiryJSON = JSON.parse(readFileSync(new URL('../online/test/fixtures/1.json', import.meta.url), 'utf8')).inquiry_json;
const bundle = JSON.parse(inquiryJSON);
const summary = {id:bundle.id,title:'Synthetic inquiry',author:'Synthetic publisher',graph_count:1,
  thought_count:3,evidence_count:0,excluded:[],omitted_evidence_count:0,description:'Synthetic import'};
function setup({inquiryId=null, privatePath=false}={}) {
  const nodes=[], events=new Map(), intervals=[], calls=[];
  function element(tag='div') {
    const n={tag,children:[],dataset:{},hidden:false,options:[],files:[],value:'',textContent:'',classList:{add(){}},
      append(...children){for(const c of children){c.parentElement=this;this.children.push(c);if(c.tag==='option')this.options.push(c);}},
      prepend(c){c.parentElement=this;this.children.unshift(c);},
      replaceChildren(){this.children=[];this.options=[];},
      setAttribute(k,v){this[k]=v;},getAttribute(k){return this[k];},addEventListener(k,fn){this[k]=fn;},focus(){this.focused=true;},
      scrollIntoView(){},showModal(){this.open=true;},close(){this.open=false;},click(){return this.onclick?.();}};
    nodes.push(n);return n;
  }
  const body=element(), workspace=element();workspace.id='workspace-menu';
  const state={saved:true,reachable:true,revoked:false,imports:0,destination:null};
  const document={body,hidden:false,createElement:element,createTextNode:text=>({textContent:text}),
    getElementById:id=>nodes.find(n=>n.id===id),addEventListener:(k,fn)=>events.set(k,fn)};
  const fetch=async(path,options={})=>{
    calls.push({path,body:options.body});
    let data={};
    if(path==='/api/online/connection')data={connected:state.saved,service:'https://synthetic.invalid',device:{owner:{login:'synthetic'},name:'Synthetic'}};
    else if(path==='/api/online/check'){
      if(!state.reachable||state.revoked)return {ok:false,json:async()=>({error:'Synthetic offline/revoked'})};
      data={connected:state.saved,verified_now:state.saved};
    } else if(path==='/api/online/disconnect'){state.saved=false;data={connected:false};}
    else if(path==='/api/inquiries/inspect'||path==='/api/inquiries/import'){
      assert.equal(options.body,inquiryJSON,'transport must preserve original numeric representation');
      if(path.endsWith('import')){state.imports++;data={url:'/synthetic-import'};}else data=summary;
    } else if(path==='/api/inquiries/preview')data={bundle,summary,inquiry_json:inquiryJSON};
    else if(path==='/api/online/prepare'){assert.equal(options.body,inquiryJSON);data={inquiry_json:inquiryJSON};}
    else if(path==='/api/sessions')data={sessions:[]};
    else if(path==='/api/inquiries')data={inquiries:[]};
    else if(path.startsWith('/api/return-paths/at'))data={arrivals:[],private_path:privatePath?{source:{author:'Synthetic publisher',inquiry_id:'synthetic-inquiry',graph_id:'source-graph',node_id:'source-thought'}}:null};
    else if(path.endsWith('/info'))data={title:'Synthetic inquiry',author:'Synthetic publisher',description:'Synthetic'};
    return {ok:true,json:async()=>data};
  };
  const blobs=[];
  const storage=new Map();
  const context=vm.createContext({document,fetch,navigator:{onLine:true},ResizeObserver:class{observe(){}},
    sessionStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)},URLSearchParams,
    addEventListener:(k,fn)=>events.set(k,fn),setInterval:fn=>intervals.push(fn),setTimeout:()=>{},
    location:{hash:'#/g/current-graph/n/current-thought',search:'',assign:url=>state.destination=url},Blob:class{constructor(parts){blobs.push(parts.join(''));}},
    URL:{createObjectURL:()=>'/synthetic-blob',revokeObjectURL(){}},console});
  context.window=context;context.TA_INQUIRY_ID=inquiryId;vm.runInContext(source,context);
  return {nodes,state,events,intervals,calls,context,blobs,find:text=>nodes.find(n=>n.textContent===text),
    settle:()=>new Promise(resolve=>setImmediate(resolve))};
}
test('file review and explicit import preserve canonical bytes instead of JS number conversion',async()=>{
  assert.notEqual(JSON.stringify(bundle),inquiryJSON);
  const ui=setup();await ui.settle();
  const file=ui.nodes.find(n=>n.type==='file');file.files=[{size:inquiryJSON.length,text:async()=>inquiryJSON}];
  await file.onchange();
  assert.ok(ui.find('Review import · Synthetic inquiry'));
  assert.equal(ui.state.imports,0);
  const commit=ui.find('Import and visit');assert.equal(commit.disabled,true);
  const consent=ui.nodes.find(n=>n.type==='checkbox');consent.checked=true;consent.onchange();
  await commit.onclick();assert.equal(ui.state.imports,1);assert.equal(ui.state.destination,'/synthetic-import');
});
test('export download and online preparation preserve the server canonical text',async()=>{
  const ui=setup();await ui.settle();
  const form=ui.find('Review export').parentElement;
  await form.onsubmit({preventDefault(){}});await ui.settle();
  const consent=ui.nodes.find(n=>n.type==='checkbox');consent.checked=true;consent.onchange();
  await ui.find('Save inquiry file').onclick();assert.equal(ui.blobs[0],inquiryJSON);
  await ui.find('Save online publication file').onclick();
  assert.equal(JSON.parse(ui.blobs[1]).inquiry_json,inquiryJSON);
});
test('both connection controls follow verification, offline recovery and revocation',async()=>{
  const ui=setup();await ui.settle();
  const buttons=()=>ui.nodes.filter(n=>n.dataset.connected!==undefined);
  assert.equal(buttons().length,2);assert.ok(buttons().every(n=>n.textContent==='You are connected to the Atlas'));
  ui.context.navigator.onLine=false;ui.events.get('offline')();
  assert.ok(buttons().every(n=>n.textContent==='Connect to the Atlas'));
  ui.context.navigator.onLine=true;await ui.events.get('online')();
  assert.ok(buttons().every(n=>n.dataset.connected==='true'));
  ui.state.revoked=true;await ui.intervals[0]();assert.ok(buttons().every(n=>n.dataset.connected==='false'));
  ui.state.revoked=false;await ui.intervals[0]();
  ui.find('You are connected to the Atlas').onclick();await ui.settle();
  await ui.find('Disconnect this Personal Atlas').onclick();
  assert.ok(buttons().every(n=>n.textContent==='Connect to the Atlas'));
});

test('Atlas menu starts stowed, toggles accessibly, and Escape returns focus to its handle',async()=>{
  const ui=setup();await ui.settle();
  const toggle=ui.nodes.find(n=>n.id==='atlas-menu-toggle');
  const panel=ui.nodes.find(n=>n.className==='atlas-menu-panel');
  assert.equal(toggle['aria-expanded'],'false');assert.equal(panel.inert,true);
  toggle.onclick();assert.equal(toggle['aria-expanded'],'true');assert.equal(panel.inert,false);
  assert.equal(ui.context.sessionStorage.getItem('atlas.menu.expanded.v1'),'true');
  ui.nodes.find(n=>n.id==='atlas-menu').keydown({key:'Escape',stopPropagation(){}});
  assert.equal(toggle['aria-expanded'],'false');assert.equal(panel.inert,true);assert.ok(toggle.focused);
});
test('private source return is in the stowable menu and the imported destination offers Return to my Atlas',async()=>{
  const returns=readFileSync(new URL('../viz/dist/return-paths.js',import.meta.url),'utf8');
  const local=setup({privatePath:true});vm.runInContext(returns,local.context);local.events.get('DOMContentLoaded')();await local.settle();
  const link=local.find('Return to Source: Synthetic publisher');
  assert.equal(link.hidden,false);assert.equal(link.parentElement.id,'portable-bar');
  assert.equal(link.href,'/inquiries/synthetic-inquiry/#/g/source-graph/n/source-thought');
  assert.equal(local.nodes.find(n=>n.id==='return-path-doors').children.length,0);
  const imported=setup({inquiryId:'synthetic-inquiry'});await imported.settle();
  const home=imported.find('Return to my Atlas');assert.equal(home.href,'/');assert.equal(home.parentElement.id,'portable-bar');
});
