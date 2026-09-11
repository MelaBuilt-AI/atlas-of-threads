/* Shared Atlas: stable server placements, existing relics and one continuous score. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id),
    state = { x: 0, z: 0, span: 100 },
    items = new Map(),
    reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const el = (tag, text, parent) => {
    const n = document.createElement(tag);
    if (text) n.textContent = text;
    if (parent) parent.append(n);
    return n;
  };
  const api = async (path, data) => {
    const r = await fetch(
      path,
      data === undefined
        ? {}
        : {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data),
          },
    );
    const d = await r.json();
    if (!r.ok) throw Error(d.error || "Atlas request failed");
    return d;
  };
  const reportError = (e) => ($("world-status").textContent = e.message);
  let selected = null,
    owner = null,
    collection = "all",
    libraryData = { publications: [], subscriptions: [], updates: [] },
    next = null,
    loading = false,
    worldReady = false,
    scene,
    camera,
    renderer,
    weave,
    spotlight,
    expeditions,
    expeditionObserver,
    contributionLines,
    transition = null,
    returnState = null,
    lastSound = 0,
    expeditionNoticeUntil = 0;
  try {
    const saved = JSON.parse(sessionStorage.getItem("atlas.world.camera.v1"));
    if (saved && ["x", "z", "span"].every((k) => Number.isFinite(saved[k])))
      Object.assign(state, saved);
  } catch {}
  const ownerLabel = (item) =>
    item.owner.verified
      ? "@" + item.owner.login
      : item.owner.login + " · synthetic preview";
  const save = () => {
    try {
      sessionStorage.setItem("atlas.world.camera.v1", JSON.stringify(state));
    } catch {}
  };
  const sound = (name, ...args) => {
    if (performance.now() - lastSound > 220) {
      window.TASound?.[name](...args);
      lastSound = performance.now();
    }
  };
  const terrainHeight = (x, z) =>
    Math.sin(x * 0.026) * Math.cos(z * 0.032) * 1.5 +
    Math.sin(x * 0.077 + z * 0.036) * 0.4;
  function choose(item, focus = true) {
    selected = item;
    $("selection").hidden = false;
    $("library").hidden = true;
    $("selection-title").textContent = item.title;
    $("selection-owner").textContent =
      `Published by ${ownerLabel(item)} · snapshot credit: ${item.author}`;
    $("selection-description").textContent = item.description;
    $("selection-counts").textContent =
       `Edition ${item.edition} · ${item.graph_count} ${item.graph_count === 1 ? "generation" : "generations"} · ${item.thought_count} thoughts`;
    $("download").href = `/api/publications/${item.id}/bundle`;
    $("download").download =
      `${item.inquiry_id.slice(0, 12)}.atlas-inquiry.json`;
    connectedPaths(item);
    $("expedition-history").onclick=()=>showExpeditions(item.threadwalk_id,item.title);
    paintSubscription();
    if (spotlight) {
      const height = terrainHeight(item.x, item.z);
      spotlight.position.set(item.x, height + 30, item.z);
      spotlight.target.position.set(item.x, height, item.z);
      spotlight.visible = true;
    }
    if (focus) moveTo({ ...state, x: item.x, z: item.z });
    sound("cycle");
  }
  function moveTo(target, then) {
    transition = {
      start: performance.now(),
      from: { ...state },
      to: target,
      then,
      duration: reduced ? 0 : 700,
    };
  }
  function zoom(factor) {
    state.span = Math.min(350, Math.max(18, state.span * factor));
    save();
    sound("cameraShift", factor > 1);
  }
  function add(item) {
    const existing = items.get(item.threadwalk_id);
    if (existing) {
      const changed = existing.id !== item.id;
      Object.assign(existing, item);
      if (existing.label) existing.label.textContent = mapTitle(existing);
      if (changed && selected === existing) choose(existing, false);
      return;
    }
    items.set(item.threadwalk_id, item);
    if (!scene) return;
    const group = new THREE.Group();
    group.position.set(item.x, terrainHeight(item.x, item.z), item.z);
    scene.add(group);
    item.group = group;
    item.aura = weave.locale(group, item.sequence - 1);
    const rayTarget = new THREE.Mesh(
      new THREE.CylinderGeometry(4, 4, 8, 12),
      new THREE.MeshBasicMaterial({ visible: false }),
    );
    rayTarget.position.y = 3;
    rayTarget.userData.item = item;
    group.add(rayTarget);
    item.pick = rayTarget;
    const relics = [
      "narrated-claim",
      "thought-graph-reliquary",
      "shared-mind-chamber",
      "tacit-claim",
      "two-whys-vessel",
      "gray-box-prism",
    ];
    item.loadRelic = () => {
      item.loadRelic = null;
      return RelicGLBLoader.load(
        `./assets/models/${relics[parseInt(item.id.slice(0, 4), 16) % relics.length]}.glb`,
      )
        .then((model) => {
          const box = new THREE.Box3().setFromObject(model),
            size = box.getSize(new THREE.Vector3()),
            center = box.getCenter(new THREE.Vector3());
          const scale = 4.5 / Math.max(size.x, size.y, size.z);
          model.scale.setScalar(scale);
          model.position.set(
            -center.x * scale,
            0.7 - box.min.y * scale,
            -center.z * scale,
          );
          group.add(model);
          item.model = model;
        })
        .catch(() => {
          item.aura.beacon.visible = true;
        });
    };
    item.label = el("div", mapTitle(item), $("labels"));
    item.label.className = "locale-label";
  }
  function connectedPaths(item) {
    $("connected-paths").replaceChildren();
    for (const road of weave?.roads.values() || []) {
      const target = road.edge.source.id === item.id ? road.edge.target
        : road.edge.target.id === item.id ? road.edge.source : null;
      if (!target) continue;
      const button = el("button", "Follow path · " + target.title, $("connected-paths"));
      button.onclick = () => followRoad(road, target);
    }
  }
  function followRoad(road, target) {
    const from = target.id === road.edge.target.id ? road.edge.source : road.edge.target;
    $("selection").hidden = true;
    sound("traverse");
    moveTo({ x: from.x, z: from.z, span: Math.min(state.span, 65) }, () => {
      transition = {
        start: performance.now(), duration: reduced ? 0 : 2800,
        from: { ...state }, to: { ...state, x: target.x, z: target.z },
        curve: road.curve, reverse: target.id === road.edge.source.id,
        then: () => choose(target),
      };
    });
  }
  function remove(item) {
    items.delete(item.threadwalk_id); item.label?.remove();
    if (item.group) {
      scene.remove(item.group);
      weave.removeLocale(item.aura);
      item.group.traverse(object => object.geometry?.dispose());
    }
    if (selected === item) { if (spotlight) spotlight.visible = false; selected = null; $("selection").hidden = true; }
  }
  async function loadWorld(more = false) {
    if (loading) return;
    loading = true;
    try {
      const maxLoaded = Math.max(0, ...[...items.values()].map(item => item.sequence));
      let cursor = more ? next : null, result;
      const received = [];
      do {
        result = await api("/api/world" + (cursor ? "?after=" + cursor : ""));
        received.push(...result.publications);
        cursor = result.next;
        // Refresh the loaded prefix; leave further pages under Load more.
      } while (!more && cursor && (cursor < maxLoaded || (next === null && cursor === maxLoaded)));
      if (!more) {
        const active = new Set(received.map(item => item.threadwalk_id));
        for (const item of items.values()) if (!active.has(item.threadwalk_id)) remove(item);
      }
      for (const item of received) add(item);
      next = result.next;
      renderLibrary();
      if (weave) weave.syncRoads(AtlasRoadMap(items.values()));
      if (selected) connectedPaths(selected);
      await loadDoorways();
      $("more").hidden = !next;
      $("world-status").textContent = items.size
        ? `${items.size} published ${items.size === 1 ? "inquiry" : "inquiries"} · choose a light to explore`
        : "The Atlas is ready for its first published inquiry.";
    } finally { loading = false; }
  }
  const subscriptionFor = item => libraryData.subscriptions.find(s => s.threadwalk_id === item?.threadwalk_id);
  const mapTitle = item => (subscriptionFor(item)?.starred ? "★ " : "") + item.title +
    (libraryData.updates.some(u => u.threadwalk_id === item.threadwalk_id) ? " · new" : "");
  function paintSubscription() {
    const saved = subscriptionFor(selected);
    $("star").textContent = saved?.starred ? "★ Starred" : "☆ Star";
    $("star").setAttribute("aria-pressed", String(!!saved?.starred));
    $("follow").checked = !!saved?.following;
    $("follow").disabled = !owner;
    $("follow-hint").textContent = owner ? "Optional in-app updates" : "Connect with GitHub to save and follow";
  }
  async function loadLibrary() {
    if (!owner) return;
    libraryData = await api("/api/library");
    for (const item of items.values()) if (item.label) item.label.textContent = mapTitle(item);
    $("updates-open").textContent = libraryData.updates.length ? `Updates · ${libraryData.updates.length}` : "Updates";
    paintSubscription(); renderLibrary();
  }
  function renderLibrary() {
    $("inquiry-list").replaceChildren();
    const list = collection === "all" ? [...items.values()] : libraryData.publications.filter(item => {
      const saved = subscriptionFor(item);
      return collection === "starred" ? saved?.starred : saved?.following;
    });
    $("library-title").textContent = { all: "Published inquiries", starred: "Starred", following: "Following" }[collection];
    if (!list.length) el("p", collection === "all" ? "No inquiries loaded yet." : owner ? "Your saved Threadwalks will appear here." : "Connect with GitHub to save Threadwalks across devices.", $("inquiry-list"));
    for (const item of list) {
      const entry = el("button", "", $("inquiry-list"));
      el("span", mapTitle(item), entry);
      el("small", `${ownerLabel(item)} · edition ${item.edition}${item.withdrawn ? " · withdrawn" : ""}`, entry);
      entry.disabled = item.withdrawn;
      entry.onclick = () => {
        add(item); weave?.syncRoads(AtlasRoadMap(items.values()));
        choose(items.get(item.threadwalk_id));
      };
    }
    $("more").hidden = collection !== "all" || !next;
  }
  async function saveSubscription(starred, following) {
    if (!owner) { location.assign("/auth/login"); return; }
    if (!selected) return;
    try {
      await api(`/api/threadwalks/${selected.threadwalk_id}/subscription`, { starred, following });
      await loadLibrary();
    } catch (e) { reportError(e); paintSubscription(); }
  }
  async function showUpdates() {
    try {
      await loadLibrary();
      $("updates-content").replaceChildren();
      if (!libraryData.updates.length) el("p", "You’re caught up. Follow a Threadwalk for editions and Capsule updates you can access.", $("updates-content"));
      for (const update of libraryData.updates) {
        const item = libraryData.publications.find(p => p.threadwalk_id === update.threadwalk_id);
        const row = el("article", "", $("updates-content"));
        const caption={"capsule-invitation":"New invitation","capsule-offering":"New offering","capsule-return":"Returned contribution","capsule-accepted":"Accepted return"}[update.kind] || "New edition";
        el("p", `${caption} · ${item?.title || "Threadwalk"}`, row);
        const open = el("button", update.delivery_id ? "Read Capsule" : "Read this edition", row);
        open.onclick = () => update.delivery_id ? window.AtlasCapsules.open(update.delivery_id) : read(update.publication_id, item?.title);
        const seen = el("button", "Mark seen", row);
        seen.onclick = async () => {
          try {
            await api(`/api/threadwalks/${update.threadwalk_id}/seen`, { through: update.seq });
            await showUpdates();
          } catch (e) { reportError(e); }
        };
      }
      $("updates-dialog").showModal();
    } catch (e) { reportError(e); }
  }
  async function editions() {
    if (!selected) return;
    try {
      const data = await api(`/api/threadwalks/${selected.threadwalk_id}`);
      $("editions-content").replaceChildren();
      for (const item of data.publications) {
        const row = el("article", "", $("editions-content"));
        el("h3", `Edition ${item.edition} · ${item.title}`, row);
        if (item.withdrawn) { el("p", "Withdrawn", row); continue; }
        const open = el("button", "Read snapshot", row); open.onclick = () => read(item.id, item.title);
        const download = el("a", "Download inquiry", row); download.href = `/api/publications/${item.id}/bundle`;
      }
      $("editions-dialog").showModal();
    } catch (e) { reportError(e); }
  }
  async function showExpeditions(id,title=items.get(id)?.title,before=0) {
    const dialog=$("expedition-dialog"),content=$("expedition-content");
    if(!dialog.open)dialog.showModal();content.replaceChildren();$("expedition-title").textContent=`Capsule port · ${title||"Threadwalk"}`;
    if(!owner){el("p","Sign in to see open expeditions and your directed deliveries.",content);return;}
    try {
      const data=await api(`/api/expeditions/history?threadwalk=${id}&before=${before}`);
      el("p","Open Capsules are visible to signed-in visitors. Directed deliveries and return decisions are shown only to their participants. History is not replayed as a live flight.",content);
      if(!data.deliveries.length)el("p","No expeditions available to this account yet.",content);
      for(const d of data.deliveries){const row=el("article","",content);
        el("h3",d.title,row);el("p",`${d.intent} · ${d.source_threadwalk_id===id?"outbound":"incoming"} · ${d.withdrawn_at?"withdrawn":d.decision|| (d.received_at?"received":d.audience==="public"?"open":"sent")} · ${new Date(d.created_at*1000).toLocaleString()}`,row);
        if(!d.withdrawn_at){const b=el("button","Review Capsule",row);b.onclick=()=>window.AtlasCapsules.open(d.id);}}
      if(data.next){const b=el("button","Earlier expeditions",content);b.onclick=()=>showExpeditions(id,title,data.next);}
    }catch(e){el("p",e.message,content);}
  }
  function suspendExpeditions(){expeditionObserver?.reset();expeditions?.clearFlights();}
  function pollExpeditions(){
    const nearby=[...items.values()].sort((a,b)=>Math.hypot(a.x-state.x,a.z-state.z)-Math.hypot(b.x-state.x,b.z-state.z)).slice(0,100).map(p=>p.threadwalk_id);
    return expeditionObserver?.poll(nearby);
  }
  function setupScene() {
    renderer = new THREE.WebGLRenderer({
      canvas: $("world"),
      antialias: true,
      alpha: true,
      powerPreference: "high-performance",
    });
    renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.setClearColor(0x02040d, 0);
    scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x02040d, 0.001);
    scene.add(new THREE.HemisphereLight(0x8acbff, 0x161130, 2.5));
    const sun = new THREE.DirectionalLight(0xf1d5ab, 2);
    sun.position.set(-60, 100, 40);
    scene.add(sun);
    camera = new THREE.OrthographicCamera(-50, 50, 50, -50, 0.1, 1200);
    const rim = new THREE.DirectionalLight(0x8b60ff, 2.3);
    rim.position.set(60, 25, -70);
    scene.add(rim);
    weave = AtlasWeave(scene, renderer, reduced);
    expeditions = AtlasExpeditions(scene,items,terrainHeight,()=>matchMedia("(prefers-reduced-motion: reduce)").matches,id=>showExpeditions(id));
    expeditionObserver = AtlasExpeditionObserver(
      (ports,after)=>api(`/api/expeditions?ports=${ports.join(",")}${after===null?"":"&after="+after}`),
      data=>{expeditions.sync(data.ports);if(!data.viewer||data.viewer_changed)expeditions.clearFlights();if(!data.viewer||Date.now()>expeditionNoticeUntil)$("expedition-status").textContent=data.unavailable?"Expedition connection paused":data.viewer?"Capsule ports · gold beacons hold invitations and arrivals":"Sign in to witness Capsule expeditions";},
      event=>{expeditionNoticeUntil=Date.now()+10000;expeditions.witness(event,state);$("expedition-status").textContent=event.kind==="accepted"?"A returned contribution was accepted":`${event.intent==="return"?"Return":"Capsule"} departing · ${event.source?.title||"private source"}`;},
      ()=>!document.hidden&&$("visit").hidden);
    document.addEventListener("visibilitychange",()=>{suspendExpeditions();if(!document.hidden)pollExpeditions();});
    spotlight = new THREE.SpotLight(0xc9eaff, 180, 65, Math.PI / 9, .75, 1);
    spotlight.visible = false;
    scene.add(spotlight, spotlight.target);
    const beam = new THREE.Mesh(new THREE.ConeGeometry(8, 30, 48, 1, true),
      new THREE.ShaderMaterial({ transparent: true, depthWrite: false, side: THREE.DoubleSide,
        blending: THREE.AdditiveBlending,
        vertexShader: 'varying vec2 vUv; void main(){ vUv=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.); }',
        fragmentShader: 'varying vec2 vUv; void main(){ float a=pow(sin(vUv.y*3.14159),2.)*.085; gl_FragColor=vec4(.53,.77,1.,a); }' }));
    beam.position.y = -15;
    spotlight.add(beam);
    const resize = () => {
      renderer.setSize(innerWidth, innerHeight, false);
    };
    addEventListener("resize", resize);
    resize();
    const ray = new THREE.Raycaster(),
      cursor = new THREE.Vector2(),
      keys = new Set(),
      pointers = new Map();
    let drag = null,
      pinch = null,
      previous = performance.now();
    const screenPan = (dx, dy) => {
      const factor = state.span / innerHeight;
      state.x -= dx * factor * 0.707 + dy * factor * 0.707;
      state.z += dx * factor * 0.707 - dy * factor * 0.707;
    };
    $("world").addEventListener("pointerdown", (e) => {
      transition = null;
      $("world").setPointerCapture(e.pointerId);
      pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
      drag = { x: e.clientX, y: e.clientY, distance: 0 };
      if (pointers.size === 2) {
        const [a, b] = [...pointers.values()];
        pinch = Math.hypot(a.x - b.x, a.y - b.y);
      }
    });
    $("world").addEventListener("pointermove", (e) => {
      if (!pointers.has(e.pointerId)) return;
      const old = pointers.get(e.pointerId);
      pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
      if (pointers.size === 2) {
        const [a, b] = [...pointers.values()],
          distance = Math.hypot(a.x - b.x, a.y - b.y);
        if (pinch) zoom(pinch / distance);
        pinch = distance;
        if (drag) drag.distance = 100;
        return;
      }
      screenPan(e.clientX - old.x, e.clientY - old.y);
      if (drag)
        drag.distance += Math.hypot(e.clientX - old.x, e.clientY - old.y);
    });
    const release = (e) => {
      pointers.delete(e.pointerId);
      pinch = null;
      if (drag && drag.distance < 6) {
        cursor.set(
          (e.clientX / innerWidth) * 2 - 1,
          (-e.clientY / innerHeight) * 2 + 1,
        );
        ray.setFromCamera(cursor, camera);
        const hit = ray.intersectObjects(
          [...items.values()].map((x) => x.pick).filter(Boolean).concat(expeditions?.picks||[]),
        )[0];
        if(hit?.object.userData.expeditionPort)showExpeditions(hit.object.userData.expeditionPort);
        else if (hit?.object.userData.item) choose(hit.object.userData.item);
      }
      drag = null;
      save();
    };
    $("world").addEventListener("pointerup", release);
    $("world").addEventListener("pointercancel", () => {
      pointers.clear();
      drag = null;
      pinch = null;
    });
    $("world").addEventListener(
      "wheel",
      (e) => {
        e.preventDefault();
        transition = null;
        zoom(Math.exp(Math.max(-100, Math.min(100, e.deltaY)) * 0.002));
      },
      { passive: false },
    );
    addEventListener("keydown", (e) => {
      if (
        !worldReady ||
        document.querySelector("dialog[open]") ||
        !$("visit").hidden ||
        e.target.closest("input,textarea,select,button,a")
      )
        return;
      if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(e.key)) {
        e.preventDefault();
        keys.add(e.key);
        transition = null;
        sound("traverse");
      }
      if (e.key === "+" || e.key === "=") zoom(0.8);
      if (e.key === "-") zoom(1.25);
      if (e.key === "Enter" && selected) enter();
      if (e.key.toLowerCase() === "s") window.TASound?.toggleMuted();
    });
    addEventListener("keyup", (e) => {
      keys.delete(e.key);
      save();
    });
    addEventListener("blur", () => keys.clear());
    function frame(time) {
      requestAnimationFrame(frame);
      const dt = Math.min(0.05, (time - previous) / 1000);
      previous = time;
      if (document.hidden || !$("visit").hidden) return;
      if (keys.size)
        screenPan(
          ((keys.has("ArrowLeft") ? 1 : 0) - (keys.has("ArrowRight") ? 1 : 0)) *
            dt *
            innerHeight *
            0.4,
          ((keys.has("ArrowUp") ? 1 : 0) - (keys.has("ArrowDown") ? 1 : 0)) *
            dt *
            innerHeight *
            0.4,
        );
      if (transition) {
        const t = transition.duration
            ? Math.min(1, (time - transition.start) / transition.duration)
            : 1,
          u = t * t * (3 - 2 * t);
        for (const k of ["x", "z", "span"])
          state[k] =
            transition.from[k] + (transition.to[k] - transition.from[k]) * u;
        if (transition.curve) {
          const point = transition.curve.getPointAt(transition.reverse ? 1 - u : u);
          state.x = point.x; state.z = point.z;
        }
        if (t === 1) {
          const done = transition.then;
          transition = null;
          save();
          done?.();
        }
      }
      const aspect = innerWidth / innerHeight;
      camera.left = (-state.span * aspect) / 2;
      camera.right = -camera.left;
      camera.top = state.span / 2;
      camera.bottom = -camera.top;
      camera.updateProjectionMatrix();
      camera.position.set(state.x + 150, 180, state.z + 150);
      camera.lookAt(state.x, 0, state.z);
      for (const item of items.values()) {
        const distance = Math.hypot(item.x - state.x, item.z - state.z);
        if (item.loadRelic && state.span < 260 && distance < state.span * 1.1) item.loadRelic();
        if (item.model) item.model.visible = state.span < 260 && distance < state.span * 1.3;
        item.aura.selection.visible = item === selected;
        const p = new THREE.Vector3(
          item.x,
          terrainHeight(item.x, item.z) + 7,
          item.z,
        ).project(camera);
        item.label.hidden =
          (state.span > 145 && item !== selected) || Math.abs(p.x) > 1.1 || Math.abs(p.y) > 1.1;
        item.label.style.left = `${((p.x + 1) * innerWidth) / 2}px`;
        item.label.style.top = `${((-p.y + 1) * innerHeight) / 2}px`;
        item.label.classList.toggle("selected", item === selected);
      }
      expeditions?.update(time,state);
      weave.update(time, state.span);
      renderer.render(scene, camera);
    }
    requestAnimationFrame(frame);
  }
  async function loadDoorways() {
    if(!scene||!window.AtlasContributionLines)return;
    const links=[];let after=0;
    do {const page=await api('/api/doorways/public?after='+after);links.push(...page.doorways);after=page.next;}while(after);
    contributionLines ||= AtlasContributionLines(scene,items,terrainHeight);
    contributionLines.sync(links);
  }
  window.AtlasDoorwayWorld={enter:async(endpoint,arrival)=>{
    try {
      await api('/api/publications/'+endpoint.publication_id);
      if($('visit').hidden)returnState={...state};
      suspendExpeditions();$('visit').hidden=false;$('labels').hidden=true;
      $('threadwalk').src='/player/?publication='+endpoint.publication_id+(arrival?'&arrival='+arrival:'')+'#/g/'+endpoint.graph_id+'/n/'+endpoint.node_id;
      $('threadwalk').focus();
    }catch(e){reportError(e);}
  }};
  async function enter() {
    if (!selected) return;
    try {
      await api("/api/publications/" + selected.id);
      returnState = { ...state };
      const id = selected.id;
      sound("traverse");
      moveTo({ x: selected.x, z: selected.z, span: 18 }, () => {
        suspendExpeditions();
        $("visit").hidden = false;
        $("labels").hidden = true;
        $("threadwalk").src = "/player/?publication=" + id;
        $("threadwalk").focus();
      });
    } catch (e) {
      reportError(e);
    }
  }
  function leave() {
    $("visit").hidden = true;
    suspendExpeditions(); pollExpeditions();
    $("threadwalk").src = "about:blank";
    $("labels").hidden = false;
    sound("traverse", "back");
    if (returnState)
      moveTo(returnState, () => {
        $("world").focus();
      });
  }
  window.addEventListener("message", (e) => {
    if (
      e.origin === location.origin &&
      e.source === $("threadwalk").contentWindow &&
      e.data?.type === "atlas-return"
    )
      leave();
  });
  window.AtlasWorldAudio = { sound: window.TASound };
  async function read(id = selected?.id, title = selected?.title) {
    if (!id) return;
    try {
      const b = await api("/api/publications/" + id + "/bundle");
      $("reader-title").textContent = title || "Published edition";
      $("reader-content").replaceChildren();
      for (const record of b.content.graphs) {
        const article = el("article", "", $("reader-content"));
        el("h3", record.graph.model.name, article);
        el("p", record.graph.prose, article).className = "prose";
        for (const n of record.graph.nodes)
          el("p", n.kind + " · " + n.text, article).className = "thought";
      }
      if (b.content.evidence.length) {
        el("h3", "Evidence links", $("reader-content"));
        for (const e of b.content.evidence) {
          el("p", e.summary, $("reader-content"));
          for (const ref of e.artifact_refs) {
            const a = el("a", ref, el("p", "", $("reader-content")));
            a.href = ref;
            a.target = "_blank";
            a.rel = "noopener noreferrer";
          }
        }
      }
      $("reader").showModal();
    } catch (e) {
      reportError(e);
    }
  }
  async function account() {
    try {
      const [{ publications }, devices] = await Promise.all([api("/api/mine"), api("/api/instances")]);
      $("account-content").replaceChildren();
      $("devices-content").replaceChildren();
      for (const device of devices.results) {
        if (device.revoked_at) continue;
        const row = el("p", device.name + " ", $("devices-content"));
        const revoke = el("button", "Disconnect device", row);
        revoke.onclick = async () => {
          try { await api(`/api/instances/${device.id}/revoke`, {}); await account(); }
          catch (e) { $("pairing-status").textContent = e.message; }
        };
      }
      for (const item of publications) {
        const row = el("div", "", $("account-content"));
        el("h3", `${item.title} · edition ${item.edition}`, row);
        if (item.withdrawn) el("p", "Withdrawn", row);
        else {
          const button = el("button", "Withdraw this publication", row);
          button.onclick = () => {
            const label = el("label", "", row),
              check = el("input", "", label);
            check.type = "checkbox";
            label.append(
              document.createTextNode(
                "Remove this snapshot from the online Atlas. Downloaded copies remain with their recipients.",
              ),
            );
            button.textContent = "Confirm withdrawal";
            button.disabled = true;
            check.onchange = () => (button.disabled = !check.checked);
            button.onclick = async () => {
              try {
                await api("/api/publications/" + item.id + "/withdraw", {});
                location.reload();
              } catch (e) {
                reportError(e);
              }
            };
          };
        }
      }
      $("account-dialog").showModal();
    } catch (e) {
      reportError(e);
    }
  }
  $("publication-file").onchange = async () => {
    const file = $("publication-file").files[0];
    $("publication-review").replaceChildren();
    if (!file) return;
    try {
      if (file.size > 8 * 1024 * 1024) throw Error("Publication exceeds 8 MiB");
      const artifact = JSON.parse(await file.text());
      if (artifact.format !== "atlas-publication")
        throw Error(
          "Choose the online publication file saved by Personal Atlas",
        );
      const bundle = JSON.parse(artifact.inquiry_json),
        c = bundle.content,
        review = $("publication-review");
      const { publication: head } = await api(`/api/edition-head?origin=${encodeURIComponent(c.origin_id)}&session=${encodeURIComponent(c.session.id)}`);
      el("p", head ? `This becomes edition ${head.edition + 1} of ${head.title}. Its map location, stars and followers stay with it. The previous snapshot remains available unless withdrawn.` : "This starts a new Threadwalk in the shared Atlas.", review);
      el("h3", c.session.title, review);
      el(
        "p",
        `Publicly attributed to @${owner?.login || "your GitHub account"}. Snapshot sharing name: ${c.author}.`,
        review,
      );
      el("p", c.description, review);
      el(
        "p",
        "Every generation below and its evidence links will be public. Private guides, agent memory, Field Notes, Capsules and local settings are excluded by the Personal Atlas exporter. Review the text for anything else private.",
        review,
      );
      for (const r of c.graphs) {
        const d = el("details", "", review);
        el(
          "summary",
          r.graph.model.name + " · " + r.graph.nodes[0].text.slice(0, 100),
          d,
        );
        el("pre", r.graph.prose, d);
        for (const n of r.graph.nodes) el("p", n.kind + " · " + n.text, d);
      }
      const exact = el("details", "", review);
      el("summary", "Inspect all shared data, links and display text", exact);
      el(
        "pre",
        JSON.stringify(
          { inquiry: bundle, player: JSON.parse(artifact.player_json) },
          null,
          2,
        ),
        exact,
      );
      const label = el("label", "", review),
        check = el("input", "", label);
      check.type = "checkbox";
      label.append(
        document.createTextNode(
          "I reviewed this complete snapshot and want to publish it publicly.",
        ),
      );
      const publish = el("button", "Publish into the Atlas", review);
      publish.className = "primary";
      publish.disabled = true;
      check.onchange = () => (publish.disabled = !check.checked);
      publish.onclick = async () => {
        publish.disabled = true;
        $("publication-status").textContent = "Publishing…";
        try {
          await api("/api/publications", { artifact, reviewed: check.checked, previous_id: head?.id || null });
          location.reload();
        } catch (e) {
          $("publication-status").textContent = e.message;
          publish.disabled = false;
        }
      };
      $("publication-status").textContent = "";
    } catch (e) {
      $("publication-status").textContent = e.message;
    }
  };
  for (const b of document.querySelectorAll("[data-close]"))
    b.onclick = () => b.closest("dialog").close();
  $("publish-open").onclick = () => {
    if (!owner) {
      location.assign("/auth/login");
      return;
    }
    $("publication-dialog").showModal();
  };
  $("star").onclick = () => saveSubscription(!subscriptionFor(selected)?.starred, !!subscriptionFor(selected)?.following);
  $("follow").onchange = () => saveSubscription(!!subscriptionFor(selected)?.starred, $("follow").checked);
  $("editions").onclick = editions;
  $("updates-open").onclick = () => owner ? showUpdates() : location.assign("/auth/login");
  $("collection").onchange = () => { collection = $("collection").value; renderLibrary(); };
  $("pairing-form").onsubmit = async e => {
    e.preventDefault();
    try {
      const result = await api("/api/pairings", { name: $("device-name").value });
      $("pairing-code").value = result.code;
      $("pairing-result").hidden = false;
      $("pairing-status").textContent = "Paste this code into Personal Atlas → Connect to the Atlas. It expires in ten minutes and works once. Creating a new code replaces the previous one.";
    } catch (e) { $("pairing-status").textContent = e.message; }
  };
  $("revoke-all-check").onchange = () => { $("revoke-all").disabled = !$("revoke-all-check").checked; };
  $("revoke-all").onclick = async () => {
    try { await api("/api/account/revoke", {}); location.reload(); }
    catch (e) { $("pairing-status").textContent = e.message; }
  };
  $("account-dialog").addEventListener("close", () => {
    $("pairing-code").value = ""; $("pairing-result").hidden = true;
  });
  $("library-toggle").onclick = () => {
    $("library").hidden = !$("library").hidden;
    $("selection").hidden = true;
  };
  $("library-close").onclick = () => ($("library").hidden = true);
  $("selection-close").onclick = () => ($("selection").hidden = true);
  $("audio-toggle").onclick = () => $("audio-dialog").showModal();
  $("zoom-in").onclick = () => zoom(0.8);
  $("zoom-out").onclick = () => zoom(1.25);
  $("home").onclick = () => moveTo({ x: 0, z: 0, span: 100 });
  $("enter").onclick = enter;
  $("read").onclick = () => read();
  $("world-return").onclick = leave;
  $("more").onclick = () => loadWorld(true).catch(reportError);
  $("logout").onclick = async () => {
    await api("/api/logout", {});
    location.reload();
  };
  try {
    setupScene();
  } catch (e) {
    $("world-status").textContent =
      "The 3D view is unavailable. Open Inquiries to read and download every Threadwalk.";
    $("library").hidden = false;
  }
  async function prepareWorld() {
    try {
      await loadWorld();
      await pollExpeditions();
      if (scene) {
        const nearby = [...items.values()].filter(item => state.span < 260 && Math.hypot(item.x-state.x,item.z-state.z) < state.span*1.1);
        await Promise.allSettled([weave.ready, ...nearby.map(item => item.loadRelic?.())]);
        await RelicGLBLoader.ready();
        // Warm the first complete frame behind the veil, including GPU texture uploads.
        scene.updateMatrixWorld(true);
        const textures = new Set();
        scene.traverse(object => {
          for (const material of Array.isArray(object.material) ? object.material : [object.material]) {
            if (material) for (const value of Object.values(material)) if (value?.isTexture) textures.add(value);
          }
        });
        for (const texture of textures) renderer.initTexture(texture);
        await renderer.compileAsync(scene, camera);
        renderer.render(scene, camera);
        await new Promise(requestAnimationFrame);
      }
    } catch (error) {
      reportError(error);
      $("library").hidden = false;
    } finally {
      worldReady = true;
      $("world-loading").hidden = true;
    }
  }
  prepareWorld();
  setInterval(() => { if (worldReady) pollExpeditions(); },2500);
  setInterval(() => {
    if (worldReady && !document.hidden && $("visit").hidden && !transition)
      Promise.all([loadWorld(), loadLibrary()]).catch(reportError);
  }, 30000);
  api("/api/me")
    .then((data) => {
      owner = data.owner;
      if (owner) {
        loadLibrary().catch(reportError);
        $("login").textContent = "@" + owner.login;
        $("login").href = "#account";
        $("login").onclick = (e) => {
          e.preventDefault();
          account();
        };
      }
    })
    .catch(reportError);
})();
