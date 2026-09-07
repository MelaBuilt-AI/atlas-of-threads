/* Agent Spark: a camera-near 3D companion with a separate, tethered HUD. */
window.TAAgentSpark = function ({ scene, camera, sound, getView, canShow, isOverhead, navigate, askCollaborator, onWorkspace }) {
  const el = (id) => document.getElementById(id);
  const hud = el('agent-spark');
  const ring = el('spark-ring');
  const input = el('spark-question');
  const thread = el('spark-conversation');
  const status = el('spark-status');
  const hint = el('spark-hint');
  const contextLabel = el('spark-context');
  const NS = 'http://www.w3.org/2000/svg';
  let guide = null, opened = false, source = null, turns = [], pending = false;
  let category = null, focusAt = 0, buttons = [], lastPoll = 0, polling = false;
  let lastChirp = 0, muted = localStorage.getItem('atlas.spark.muted') === 'true';
  let hudX = 0, hudY = 0, request = null, lastRendered = '';
  let exchangeIndex = -1, followLatest = true;
  const categoryNames = ['Discuss', 'Context', 'Handoffs', 'History', 'Sound', 'Settings', 'Help', 'Close'];
  const questionBubble = el('spark-question-bubble'), answerBubble = el('spark-answer-bubble');
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const group = new THREE.Group();
  const core = new THREE.Mesh(new THREE.IcosahedronGeometry(0.13, 3), new THREE.MeshStandardMaterial({color:0xb8f9f3, emissive:0x61e8d4, emissiveIntensity:2.2, roughness:0.2, metalness:0.3}));
  core.castShadow=true;
  core.receiveShadow=true;
  group.add(core);
  const shell = new THREE.Mesh(new THREE.IcosahedronGeometry(0.19, 1), new THREE.MeshBasicMaterial({color:0x9ae9db,wireframe:true,transparent:true,opacity:0.3}));
  group.add(shell);
  const glowCanvas=document.createElement('canvas'); glowCanvas.width=128; glowCanvas.height=128;
  const ctx=glowCanvas.getContext('2d'); const grad=ctx.createRadialGradient(64,64,0,64,64,64);
  grad.addColorStop(0,'rgba(188,255,244,0.9)');grad.addColorStop(0.18,'rgba(101,245,215,0.4)');grad.addColorStop(1,'rgba(49,189,189,0)');
  ctx.fillStyle=grad;ctx.fillRect(0,0,128,128);
  const glow=new THREE.Sprite(new THREE.SpriteMaterial({map:new THREE.CanvasTexture(glowCanvas),transparent:true,blending:THREE.AdditiveBlending,depthWrite:false}));
  glow.scale.set(1.25,1.25,1.25);group.add(glow);
  const light=new THREE.PointLight(0x76ffe6,125,18,2);
  light.castShadow=true;
  light.shadow.mapSize.set(512,512);
  light.shadow.bias=-0.0005;
  light.shadow.normalBias=0.025;
  light.shadow.camera.far=18;
  group.add(light);
  // A soft floor shadow keeps the emissive guide grounded even where its own
  // light fills the scene's ordinary shadow maps.
  const shadowCanvas=document.createElement('canvas');shadowCanvas.width=128;shadowCanvas.height=128;
  const shadowCtx=shadowCanvas.getContext('2d');
  const shadowGradient=shadowCtx.createRadialGradient(64,64,0,64,64,64);
  shadowGradient.addColorStop(0,'rgba(0,0,0,0.48)');
  shadowGradient.addColorStop(0.35,'rgba(0,0,0,0.3)');
  shadowGradient.addColorStop(1,'rgba(0,0,0,0)');
  shadowCtx.fillStyle=shadowGradient;shadowCtx.fillRect(0,0,128,128);
  const floorShadow=new THREE.Mesh(new THREE.PlaneGeometry(2,2),new THREE.MeshBasicMaterial({map:new THREE.CanvasTexture(shadowCanvas),transparent:true,depthWrite:false}));
  floorShadow.rotation.x=-Math.PI/2;floorShadow.visible=false;scene.add(floorShadow);
  const branches=[];
  for(let i=0;i<9;i++) {
    const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.BufferAttribute(new Float32Array(18),3));
    const line=new THREE.Line(geometry,new THREE.LineBasicMaterial({color:i%2?0xc2fff1:0x89bffe,transparent:true,opacity:0.6,blending:THREE.AdditiveBlending}));
    group.add(line);branches.push(line);
  }
  scene.add(group);group.visible=false;
  const world=new THREE.Vector3(), projected=new THREE.Vector3();
  const ray=new THREE.Raycaster();
  let positioned=false;
  function cue(kind) { if (!muted) sound.spark?.(kind); }
  function pinHere() {
    const v=getView();
    if(v) { source={graph_id:v.graph_id,node_id:v.node.id,session_id:v.session_id,text:v.node.text}; renderContext(); }
  }
  function renderContext() { contextLabel.textContent=source?`Selected thought · ${source.text}`:'Select a thought to discuss.';contextLabel.title=source?.text||''; }
  function open() {
    if(!guide || !canShow())return;
    pinHere();opened=true;category=null;focusAt=0;hud.hidden=false;document.body.dataset.agentSpark='true';
    el('spark-title').textContent=guide.display_name;el('spark-model').textContent=guide.model||'Connected guide';
    renderRing();cue('open');poll();buttons[0]?.focus();
  }
  function close() {
    opened=false;hud.hidden=true;delete document.body.dataset.agentSpark;cue('close');
    el('c').focus({preventScroll:true});
  }
  function toggle() {opened?close():open();}
  hint.onclick=toggle;
  function svg(name, attrs={}) { const n=document.createElementNS(NS,name);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,v);return n; }
  function segmentButton(label, action, index, count, inner, outer, outerRing=false) {
    const angle=-Math.PI/2+index*Math.PI*2/count, half=Math.PI/count-0.022;
    const point=(r,a)=>`${300+Math.cos(a)*r},${300+Math.sin(a)*r}`;
    const g=svg('g',{role:'button',tabindex:'-1','aria-label':label,class:'spark-segment'+(outerRing?' spark-outer':'')});
    if (!outerRing && ['Context','Handoffs','History','Sound','Settings'].includes(label)) {
      g.setAttribute('aria-expanded', String(category === label));
      if (category === label) g.classList.add('spark-category-open');
    }
    // Two radial sides and two concentric arcs keep every button on its ring.
    g.append(svg('path',{class:'spark-sector',d:`M ${point(inner,angle-half)} L ${point(outer,angle-half)} A ${outer} ${outer} 0 0 1 ${point(outer,angle+half)} L ${point(inner,angle+half)} A ${inner} ${inner} 0 0 0 ${point(inner,angle-half)} Z`}));
    const radius=(inner+outer)/2, reverse=Math.sin(angle)>0.05;
    const start=reverse?angle+half:angle-half, end=reverse?angle-half:angle+half;
    const pathId=`spark-label-${buttons.length}`;
    const defs=svg('defs');
    defs.append(svg('path',{id:pathId,d:`M ${point(radius,start)} A ${radius} ${radius} 0 0 ${reverse?0:1} ${point(radius,end)}`}));
    const t=svg('text',{'text-anchor':'middle',dy:'4'});
    const textPath=svg('textPath',{href:`#${pathId}`,startOffset:'50%'});textPath.textContent=label;t.append(textPath);
    g.append(defs,t);
    g.onclick=()=>{cue('click');action();};g.onfocus=()=>{focusAt=buttons.indexOf(g);};ring.append(g);buttons.push(g);
  }

  const draft=(text)=>{input.value=text;input.focus();status.textContent='Draft only · edit it, then Send when ready.';};
  const lastAnswer=()=>turns[exchangeIndex]?.status === 'completed' ? turns[exchangeIndex] : null;
  async function handoff() {
    const answer=lastAnswer();
    if(!answer){status.textContent='Discuss a thought first, then choose a response to hand off.';return;}
    const chosen=answer.source;
    close();await askCollaborator(chosen,answer.response);
  }
  async function copyAnswer() {
    const answer=lastAnswer();if(!answer){status.textContent='No completed response yet.';return;}
    try {await navigator.clipboard.writeText(`${answer.response}\n\nAgent: ${answer.agent.display_name} · ${answer.model}\nAtlas: ${location.origin}/#/g/${answer.source.graph_id}/n/${answer.source.node_id}`);status.textContent='Response and source link copied.';}catch(_){status.textContent='Copy unavailable. Select and copy the response text below.';}
  }
  function renderRing() {
    ring.replaceChildren();buttons=[];
    const actions=[['Discuss',()=>input.focus()],['Context',()=>expand('Context')],['Handoffs',()=>expand('Handoffs')],['History',()=>expand('History')],['Sound',()=>expand('Sound')],['Settings',()=>expand('Settings')],['Help',()=>{status.textContent='← / → select · ↑ / Enter activate · ↓ back · Esc / G close. Tab reaches the conversation. Ctrl+Enter sends. Questions stay pinned to the selected thought.';}],['Close',close]];
    actions.forEach(([label,action],i)=>segmentButton(label,action,i,8,190,240));
    const categories={
      Context:[['This thought',pinHere],['Open selected',async()=>{const selected=source;close();if(selected)await navigate(selected.graph_id,selected.node_id);}],['Draft objection',()=>draft('Help me examine an objection to this thought. What assumptions would change the conclusion?')],],
      Handoffs:[['Ask collaborator',handoff],['Draft Field Note',()=>draft('Help me draft a short Field Note about this thought. Label it as agent-assisted draft text for my review; do not save it.')],['Draft memory',()=>draft('Draft a concise memory note from our discussion with exact Atlas references. Do not claim it has been saved to your native memory.')],['Copy response',copyAnswer]],
      Sound:[['Quiet orb',()=>{muted=true;localStorage.setItem('atlas.spark.muted','true');status.textContent='Agent Spark sounds muted.';}],['Spark sound',()=>{muted=false;localStorage.setItem('atlas.spark.muted','false');cue('open');status.textContent='Soft Agent Spark sounds on; master sound controls still apply.';}],],
      History:[['Earlier exchange',()=>showExchange(-1)],['Later exchange',()=>showExchange(1)],['Latest exchange',()=>{followLatest=true;renderTurns();}]],
      Settings:[['Clear discussion',()=>{el('spark-clear-review').hidden=false;}],]
    };
    const outer = categories[category] || [];
    const anchor = Math.round(actions.findIndex(([label]) => label === category) * 1.5);
    outer.forEach(([label,action],i)=>segmentButton(label,action,i + anchor - Math.floor(outer.length / 2),12,249,294,true));
    buttons.forEach((b,i)=>b.setAttribute('tabindex',i===focusAt?'0':'-1'));
  }
  function expand(name) {
    const previous = category;
    category = name && name !== category ? name : null;
    focusAt = Math.max(0, categoryNames.indexOf(name || previous));
    renderRing();buttons[focusAt]?.focus();
  }
  function showExchange(direction) {
    if (!turns.length) {status.textContent='Your conversation bubbles will appear after you send a question.';return;}
    exchangeIndex=Math.max(0,Math.min(turns.length-1,exchangeIndex+direction));
    followLatest=exchangeIndex===turns.length-1;renderTurns();
  }
  el('spark-clear-cancel').onclick=()=>{el('spark-clear-review').hidden=true;};
  el('spark-clear-confirm').onclick=async()=>{
    try {const data=await post('/api/guide/clear',{});turns=data.turns;renderTurns();status.textContent='Local discussion cleared. Your agent’s own conversation and memory are separate.';el('spark-clear-review').hidden=true;}catch(error){status.textContent=error.message;}
  };
  async function post(url,body) {const res=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await res.json();if(!res.ok)throw Error(data.error||'Request failed.');return data;}
  function materialize(bubble, key) {
    const fresh=bubble.hidden || bubble.dataset.turn !== key;
    bubble.hidden=false;bubble.dataset.turn=key;
    if(fresh && !reducedMotion) bubble.animate([{opacity:0,filter:'blur(8px)'},{opacity:1,filter:'blur(0)'}],{duration:650,easing:'ease-out'});
  }
  function renderTurns() {
    pending=turns.some(t=>t.status==='pending');el('spark-send').disabled=pending;el('spark-clear-confirm').disabled=pending;
    if(followLatest) exchangeIndex=turns.length-1;
    exchangeIndex=Math.min(exchangeIndex,turns.length-1);
    const fingerprint=JSON.stringify([turns,exchangeIndex]);if(fingerprint===lastRendered)return;lastRendered=fingerprint;
    const turn=turns[exchangeIndex];
    if(!turn){questionBubble.hidden=true;answerBubble.hidden=true;return;}
    materialize(questionBubble,turn.id);
    el('spark-question-heading').textContent=`Your question · ${exchangeIndex+1} of ${turns.length}`;
    el('spark-question-text').textContent=turn.prompt;
    el('spark-question-meta').textContent=turn.status==='pending'?'Your guide is thinking…':'Private conversation';
    if(turn.status==='pending'){answerBubble.hidden=true;return;}
    materialize(answerBubble,turn.id);
    el('spark-answer-heading').textContent=turn.agent.display_name;
    el('spark-answer-text').textContent=turn.response||turn.error;
    el('spark-answer-meta').textContent=`${turn.model||turn.agent.model||'guide'} · ${turn.status}`;
    el('spark-bubble-source').title=turn.source.text;
  }
  el('spark-bubble-source').onclick=()=>{
    const turn=turns[exchangeIndex];if(!turn)return;
    source={...turn.source};renderContext();status.textContent='This exchange’s thought is selected for your next question.';
  };

  async function poll() {
    if(polling||!guide)return;polling=true;
    try{const res=await fetch('/api/guide');if(!res.ok)throw Error('Guide connection unavailable.');const data=await res.json();if(data.guide?.name!==guide?.name)return;turns=data.turns;renderTurns();}
    catch(error){if(opened)status.textContent=error.message;}finally{polling=false;}
  }
  async function send(event) {
    event?.preventDefault();if(pending||!source||!input.value.trim())return;
    const prompt=input.value.trim();
    if(!request||request.prompt!==prompt||request.graph_id!==source.graph_id||request.node_id!==source.node_id)request={request_id:crypto.randomUUID(),prompt,graph_id:source.graph_id,node_id:source.node_id};
    pending=true;el('spark-send').disabled=true;status.textContent='Sending to your guide…';
    try {await post('/api/guide/discuss',request);input.value='';request=null;followLatest=true;cue('click');status.textContent='Saved privately in this Atlas. Discussion does not create graphs.';await poll();}
    catch(error){pending=false;el('spark-send').disabled=false;status.textContent=error.message;}
  }
  el('spark-form').onsubmit=send;
  window.addEventListener('keydown',(event)=>{
    if(!opened){if(guide&&canShow()&&!event.repeat&&event.key.toLowerCase()==='g'&&!/INPUT|TEXTAREA|SELECT/.test(event.target.tagName)&&!event.target.isContentEditable){event.preventDefault();event.stopImmediatePropagation();open();}return;}
    event.stopImmediatePropagation();
    const editing=/INPUT|TEXTAREA|SELECT/.test(event.target.tagName)||event.target.isContentEditable;
    if(event.key==='Escape'){event.preventDefault();if(category)expand(null);else close();return;}
    if(editing){if(event.key==='Enter'&&(event.ctrlKey||event.metaKey)){event.preventDefault();send();}return;}
    if(event.key.toLowerCase()==='g'){event.preventDefault();close();return;}
    if(event.key==='Enter' && !event.target.closest('.spark-segment')) return;
    if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Enter'].includes(event.key)){
      event.preventDefault();
      if(event.key==='ArrowDown'){expand(null);return;}
      if(event.key==='Enter'||event.key==='ArrowUp'){buttons[focusAt]?.dispatchEvent(new MouseEvent('click'));return;}
      focusAt=(focusAt+(event.key==='ArrowRight'?1:-1)+buttons.length)%buttons.length;
      buttons.forEach((b,i)=>b.setAttribute('tabindex',i===focusAt?'0':'-1'));buttons[focusAt]?.focus();
    }
    if(event.key==='Tab'){
      const nodes=[...hud.querySelectorAll('button:not([disabled]),textarea,[tabindex="0"]')].filter(n=>!n.closest('[hidden]'));
      if(!nodes.length)return;const i=nodes.indexOf(document.activeElement);event.preventDefault();nodes[(i+(event.shiftKey?-1:1)+nodes.length)%nodes.length].focus();
    }
  },true);
  function setWorkspace(payload) {
    const previous=guide?.name;guide=payload.guide||null;
    if(previous!==guide?.name){turns=[];lastRendered='';exchangeIndex=-1;followLatest=true;source=null;if(opened)close();}
    const candidates=payload.agent_candidates||payload.harnesses||[];
    const assigned=new Set((payload.harnesses||[]).map(h=>h.name));
    el('workspace-guide-status').textContent=guide?`${guide.display_name} · ${guide.model||'model not reported'} · guide connected`:'No guide connected. Assign an agent below.';
    const list=el('workspace-agent-roles');list.replaceChildren();
    for(const agent of candidates){
      const row=document.createElement('div');row.className='agent-role-row';
      const label=document.createElement('strong');label.textContent=`${agent.agent_name||agent.name} · ${agent.model||'model not reported'}`;row.append(label);
      const makeCheck=(text,checked)=>{const l=document.createElement('label'),c=document.createElement('input');c.type='checkbox';c.checked=checked;l.append(c,document.createTextNode(text));row.append(l);return c;};
      const collaborator=makeCheck('Agent as collaborator',assigned.has(agent.name)),asGuide=makeCheck('Agent as guide',guide?.name===agent.name);
      const apply=document.createElement('button');apply.type='button';apply.textContent='Apply roles';apply.onclick=async()=>{
        apply.disabled=true;el('workspace-action-status').textContent='Connecting agent roles…';
        try{const result=await post('/api/agent/roles',{harness:agent.name,collaborator:collaborator.checked,guide:asGuide.checked});onWorkspace(result.workspace);el('workspace-action-status').textContent='Agent roles saved.';}
        catch(error){el('workspace-action-status').textContent=error.message;}finally{apply.disabled=false;}
      };row.append(apply);list.append(row);
    }
  }
  function tick(t) {
    const visible=Boolean(guide&&canShow());group.visible=visible;floorShadow.visible=visible;hint.hidden=!visible||opened;
    if(opened&&!visible)close();if(!visible)return;
    const motion=reducedMotion?0:1;
    // Keep the guide near the floor in overhead view, with the same apparent size.
    const depth=isOverhead()?Math.max(5.3,camera.position.y-3.2):5.3;
    const apparentScale=depth/5.3;
    group.scale.setScalar(apparentScale);
    // Start the point-light shadow camera outside its own luminous core.
    light.shadow.camera.near=0.18*apparentScale;
    light.shadow.camera.updateProjectionMatrix();
    light.intensity=125*(1+Math.sin(t*2.2)*0.045*motion);
    const half=Math.tan(THREE.MathUtils.degToRad(camera.fov/2))*depth;
    world.set(half*camera.aspect*(0.72+Math.sin(t*0.71)*0.035*motion),half*(0.54+Math.cos(t*0.9)*0.047*motion),-depth);
    camera.updateMatrixWorld();camera.localToWorld(world);
    if(!positioned){group.position.copy(world);positioned=true;}else group.position.lerp(world,0.13);
    const height=Math.max(0,group.position.y);
    floorShadow.position.set(group.position.x-height*8/42,0.005,group.position.z-height*10/42);
    floorShadow.scale.setScalar(0.13*apparentScale+height*0.16);
    core.rotation.y=t*0.5*motion;shell.rotation.set(t*0.4*motion,t*0.23*motion,0.4);core.scale.setScalar(1+Math.sin(t*3)*0.07*motion);
    branches.forEach((line,i)=>{const p=line.geometry.attributes.position;const angle=i*Math.PI*2/branches.length+t*0.18*motion;for(let j=0;j<6;j++){const d=0.12+j*0.052;const flicker=motion*Math.sin(t*17+i*4+j*3)*0.026;p.setXYZ(j,Math.cos(angle)*d+flicker,Math.sin(angle)*d-flicker,Math.sin(i*2+j*0.7+t)*0.07);}p.needsUpdate=true;line.material.opacity=0.25+Math.max(0,Math.sin(t*6+i*3))*0.6;});
    projected.copy(group.position).project(camera);
    const x=(projected.x+1)*innerWidth/2,y=(1-projected.y)*innerHeight/2;
    hint.style.left=`${Math.min(innerWidth-205,Math.max(12,x-95))}px`;hint.style.top=`${y+37}px`;
    if(!muted&&!document.hidden&&t-lastChirp>5.5){cue('idle');lastChirp=t;}
    if(opened){
      // Reserve a separate right-hand lane for the two floating message bubbles.
      const size=Math.min(600,innerHeight-40,(innerWidth-40)*0.60),scale=size/600;
      const bubbleWidth=Math.min(380,innerWidth-size-44);
      const stageWidth=size+24+bubbleWidth;
      const baseX=(innerWidth-stageWidth)/2;
      const targetX=baseX+Math.sin(t*0.63)*4*motion;
      const baseY=Math.max(20,Math.min(innerHeight-size-20,y-size*0.22));
      const targetY=baseY+Math.cos(t*0.77)*4*motion;
      if(!hudX){hudX=targetX;hudY=targetY;}
      hudX+=(targetX-hudX)*0.045;hudY+=(targetY-hudY)*0.045;
      el('spark-dial').style.transform=`translate(${hudX}px,${hudY}px) scale(${scale})`;
      const bubbleX=hudX+size+22;
      const bubbleY=Math.max(85,Math.min(y+72,innerHeight-300));
      const bubbleSpace=innerHeight-bubbleY-26;
      thread.style.left=`${bubbleX}px`;thread.style.top=`${bubbleY}px`;thread.style.width=`${bubbleWidth}px`;
      questionBubble.style.maxHeight=`${Math.max(90,bubbleSpace*0.43)}px`;
      answerBubble.style.maxHeight=`${Math.max(110,bubbleSpace*0.57-22)}px`;
      questionBubble.style.transform=`translate(${Math.sin(t*0.8+1)*4*motion}px,${Math.cos(t*0.67)*4*motion}px)`;
      answerBubble.style.transform=`translate(${Math.sin(t*0.66+3)*4*motion}px,${Math.cos(t*0.81+2)*5*motion}px)`;
      const endX=hudX+size*0.78,endY=hudY+size*0.18;
      el('spark-tether').setAttribute('viewBox',`0 0 ${innerWidth} ${innerHeight}`);
      const trail=(id,from,to,visible=true)=>{
        const path=el(id);path.style.display=visible?'':'none';if(!visible)return;
        const mx=(from.x+to.x)/2,my=(from.y+to.y)/2;
        const flicker=Math.sin(t*9)*3*motion;
        path.setAttribute('d',`M ${from.x} ${from.y} Q ${mx} ${from.y} ${mx-4} ${my+flicker} L ${mx+4} ${my-flicker} Q ${mx} ${to.y} ${to.x} ${to.y}`);
      };
      trail('spark-tether-line',{x,y},{x:endX,y:endY});
      const sendRect=el('spark-send').getBoundingClientRect();
      const qr=questionBubble.getBoundingClientRect(), ar=answerBubble.getBoundingClientRect();
      trail('spark-question-send-trail',{x:sendRect.right,y:sendRect.top+sendRect.height/2},{x:qr.left,y:qr.top+qr.height*.55},!questionBubble.hidden);
      trail('spark-question-orb-trail',{x,y},{x:qr.left+qr.width*.72,y:qr.top},!questionBubble.hidden);
      trail('spark-answer-orb-trail',{x,y},{x:ar.right,y:ar.top+ar.height*.45},!answerBubble.hidden);
      if(t-lastPoll>1.5){lastPoll=t;poll();}
    }
  }
  function pick(event) {
    if(opened)return true;if(!group.visible)return false;
    ray.setFromCamera(new THREE.Vector2(event.clientX/innerWidth*2-1,1-event.clientY/innerHeight*2),camera);
    if(ray.intersectObject(glow).length||ray.intersectObject(shell).length||ray.intersectObject(core).length){toggle();return true;}return false;
  }
  return {setWorkspace,tick,pick,get opened(){return opened;}};
};
