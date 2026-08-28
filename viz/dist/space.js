/* Inhabit Space — stand at a node. Fork/veto are gestures. Not a dashboard. */
(function () {
  const KIND_COLOR = {
    claim: 0xe8d5a3,
    premise: 0x8fa9c4,
    analogy: 0xd4a0b0,
    taste_call: 0xf0a35e,
    uncertainty: 0x5c8a7b,
    rejected_alternative: 0x8a7396,
  };

  const canvas = document.getElementById("c");
  const elKind = document.getElementById("kind");
  const elText = document.getElementById("text");
  const elHere = document.getElementById("here");
  const elMeta = document.getElementById("meta");
  const elEmpty = document.getElementById("empty");
  const elHelp = document.getElementById("help");
  const elComposer = document.getElementById("composer");
  const elComposerLabel = document.getElementById("composer-label");
  const elComposerInput = document.getElementById("composer-input");

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setClearColor(0x12100e, 1);

  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x12100e, 0.045);

  const CELL = 1.4; // default claim box footprint
  const FLOOR_CELLS = 30;
  const FLOOR_SPAN = CELL * FLOOR_CELLS;
  const CHOICE_STRIDE = CELL * 3; // equal cells; clears scaled boards (~1.8)
  const CHOICE_ROW = CELL * 4;
  const CHOICE_ROW_GAP = CELL * 3;
  const CHOICE_COLS = 7;

  const camera = new THREE.PerspectiveCamera(55, 1, 0.2, 200);
  camera.position.set(0, 2.4, 7.2);

  const clock = new THREE.Clock();
  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();

  let view = null;
  let targets = [];
  let portals = [];
  let choices = [];
  let focusIndex = -1;
  const HOME_YAW = 0.18;
  const HOME_PITCH = 0.22;
  let dragging = false;
  let dragMoved = false;
  let lastX = 0;
  let lastY = 0;
  let yaw = HOME_YAW;
  let pitch = HOME_PITCH;
  let overheadLook = { x: 0, z: 0 };
  let climateFog = 0.045;
  let helpOn = true;
  let composing = null;
  let busy = false;
  let risers = [];
  let sky = null;
  let trail = [];
  let overhead = false;

  const root = new THREE.Group();
  scene.add(root);

  scene.add(new THREE.AmbientLight(0x3a342c, 0.55));
  const key = new THREE.PointLight(0xc8f26a, 1.4, 28, 2);
  key.position.set(0, 3.2, 1.5);
  scene.add(key);
  const fill = new THREE.PointLight(0xb08d57, 0.7, 22, 2);
  fill.position.set(-4, 1.4, 3);
  scene.add(fill);
  const starFill = new THREE.AmbientLight(0x1a2240, 0.22);
  scene.add(starFill);
  const overSun = new THREE.DirectionalLight(0xe8f2ff, 0);
  overSun.position.set(8, 42, 10);
  scene.add(overSun);
  const overHemi = new THREE.HemisphereLight(0xb8d4ff, 0x1a2438, 0);
  scene.add(overHemi);

  const CLIMATE = {
    divergence: { fog: 0x2a1828, density: 0.07, key: 0xb08d57, fill: 0x8a7396, clear: 0x1a1018 },
    veto: { fog: 0x1a1420, density: 0.058, key: 0x8a7396, fill: 0x5c4060, clear: 0x141018 },
    recurring: { fog: 0x1c1810, density: 0.036, key: 0xe2c48a, fill: 0xf0a35e, clear: 0x16140e },
    emerging: { fog: 0x12100e, density: 0.045, key: 0xc8f26a, fill: 0xb08d57, clear: 0x12100e },
    calm: { fog: 0x12100e, density: 0.04, key: 0xc8f26a, fill: 0xb08d57, clear: 0x12100e },
  };

  function applyClimate(climate) {
    const kind = (climate && climate.kind) || "calm";
    const c = CLIMATE[kind] || CLIMATE.calm;
    scene.fog.color.setHex(c.fog);
    climateFog = c.density;
    scene.fog.density = overhead ? 0.006 : c.density;
    key.color.setHex(c.key);
    fill.color.setHex(c.fill);
    renderer.setClearColor(overhead ? 0x03050c : c.clear, 1);
    document.body.dataset.climate = kind;
  }

  function resize() {
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / Math.max(h, 1);
    camera.updateProjectionMatrix();
  }
  window.addEventListener("resize", resize);
  resize();

  function hashTo(graphId, nodeId) {
    location.hash = `#/g/${graphId}/n/${nodeId}`;
  }

  function parseHash() {
    const m = location.hash.match(/^#\/g\/([^/]+)\/n\/([^/]+)/);
    if (!m) return null;
    return { graphId: m[1], nodeId: m[2] };
  }

  async function api(path, opts) {
    const res = await fetch(path, opts || {});
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: res.statusText }));
      throw new Error(err.error || res.statusText);
    }
    return res.json();
  }

  async function post(path, body) {
    return api(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  }

  function starTexture() {
    const c = document.createElement("canvas");
    c.width = c.height = 2048;
    const ctx = c.getContext("2d");
    const g = ctx.createRadialGradient(1024, 1180, 80, 1024, 1024, 1400);
    g.addColorStop(0, "#12203a");
    g.addColorStop(0.22, "#0a1428");
    g.addColorStop(0.55, "#060b18");
    g.addColorStop(1, "#02040a");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, 2048, 2048);
    ctx.save();
    ctx.translate(1024, 1080);
    ctx.rotate(-0.35);
    const band = ctx.createLinearGradient(0, -180, 0, 180);
    band.addColorStop(0, "rgba(80, 120, 200, 0)");
    band.addColorStop(0.5, "rgba(90, 160, 220, 0.14)");
    band.addColorStop(1, "rgba(80, 120, 200, 0)");
    ctx.fillStyle = band;
    ctx.fillRect(-1400, -160, 2800, 320);
    ctx.restore();
    let seed = 7;
    function rnd() {
      seed = (seed * 16807) % 2147483647;
      return (seed - 1) / 2147483646;
    }
    for (let i = 0; i < 1800; i++) {
      const x = rnd() * 2048;
      const y = rnd() * 2048;
      const r = rnd() < 0.08 ? 1.6 + rnd() * 1.4 : 0.4 + rnd() * 0.9;
      const a = 0.35 + rnd() * 0.65;
      const tint = rnd();
      ctx.fillStyle =
        tint > 0.92
          ? `rgba(200,242,106,${a})`
          : tint > 0.78
            ? `rgba(170,210,255,${a})`
            : `rgba(230,236,255,${a})`;
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fill();
    }
    const tex = new THREE.CanvasTexture(c);
    if (THREE.SRGBColorSpace) tex.colorSpace = THREE.SRGBColorSpace;
    tex.needsUpdate = true;
    return tex;
  }

  function makeSky() {
    const geo = new THREE.SphereGeometry(120, 48, 32);
    const mat = new THREE.MeshBasicMaterial({
      map: starTexture(),
      side: THREE.BackSide,
      fog: false,
      depthWrite: false,
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.userData.sky = true;
    return mesh;
  }

  function stoneMat(color, opacity) {
    return new THREE.MeshStandardMaterial({
      color,
      roughness: 0.82,
      metalness: 0.08,
      transparent: opacity < 1,
      opacity,
    });
  }

  function labelTexture(title, body) {
    const c = document.createElement("canvas");
    c.width = 1024;
    c.height = 512;
    const ctx = c.getContext("2d");
    ctx.fillStyle = "rgba(18,16,14,0.15)";
    ctx.fillRect(0, 0, c.width, c.height);
    ctx.fillStyle = "#c8f26a";
    ctx.font = "600 36px ui-monospace, monospace";
    ctx.fillText(title.toUpperCase(), 40, 70);
    ctx.fillStyle = "#ece6d8";
    ctx.font = "500 42px Palatino, serif";
    wrap(ctx, body, 40, 140, 940, 52);
    const tex = new THREE.CanvasTexture(c);
    tex.needsUpdate = true;
    return tex;
  }

  function wrap(ctx, text, x, y, maxW, lh) {
    const words = (text || "").split(/\s+/);
    let line = "";
    let row = 0;
    for (const w of words) {
      const test = line ? line + " " + w : w;
      if (ctx.measureText(test).width > maxW) {
        ctx.fillText(line, x, y + row * lh);
        line = w;
        row += 1;
        if (row > 5) {
          ctx.fillText(line + "…", x, y + row * lh);
          return;
        }
      } else line = test;
    }
    if (line) ctx.fillText(line, x, y + row * lh);
  }

  function chamberMesh(node, { x, z, scale, ghost }) {
    const color = KIND_COLOR[node.kind] || 0xb08d57;
    const g = new THREE.Group();
    g.position.set(x, 0, z);
    g.userData = { id: node.id, kind: node.kind, ghost: !!ghost };

    const plinth = new THREE.Mesh(
      new THREE.CylinderGeometry(1.1 * scale, 1.35 * scale, 0.35, 8),
      stoneMat(ghost ? 0x3a3238 : 0x2a2620, ghost ? 0.55 : 1)
    );
    plinth.position.y = 0.18;
    g.add(plinth);

    const core = new THREE.Mesh(
      new THREE.BoxGeometry(1.4 * scale, 2.2 * scale, 1.4 * scale),
      stoneMat(color, ghost ? 0.45 : 0.92)
    );
    core.position.y = 1.35 * scale;
    g.add(core);

    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(1.05 * scale, 0.04, 8, 24),
      new THREE.MeshStandardMaterial({
        color: ghost ? 0x8a7396 : 0xc8f26a,
        emissive: ghost ? 0x3a2040 : 0x6a8a30,
        emissiveIntensity: ghost ? 0.2 : 0.55,
        metalness: 0.4,
        roughness: 0.35,
      })
    );
    ring.rotation.x = Math.PI / 2;
    ring.position.y = 0.4;
    g.add(ring);

    const board = new THREE.Mesh(
      new THREE.PlaneGeometry(2.6 * scale, 1.3 * scale),
      new THREE.MeshBasicMaterial({
        map: labelTexture(node.kind.replace("_", " "), node.text),
        transparent: true,
      })
    );
    board.position.set(0, 2.7 * scale, 0.85 * scale);
    g.add(board);

    const hit = new THREE.Mesh(
      new THREE.SphereGeometry(1.6 * scale),
      new THREE.MeshBasicMaterial({ visible: false })
    );
    hit.position.y = 1.2;
    hit.userData = g.userData;
    g.add(hit);
    return g;
  }

  function floor() {
    const g = new THREE.Group();
    const slab = new THREE.Mesh(
      new THREE.PlaneGeometry(FLOOR_SPAN, FLOOR_SPAN),
      new THREE.MeshStandardMaterial({
        color: 0x0c1018,
        roughness: 0.92,
        metalness: 0.18,
        emissive: 0x05070e,
        emissiveIntensity: 0.4,
      })
    );
    slab.rotation.x = -Math.PI / 2;
    slab.position.y = -0.01;
    slab.receiveShadow = true;
    g.add(slab);
    const grid = new THREE.GridHelper(
      FLOOR_SPAN,
      FLOOR_CELLS,
      0x3a5a40,
      0x1a3048
    );
    grid.position.y = 0.002;
    const mats = [].concat(grid.material);
    mats.forEach((m) => {
      m.transparent = true;
      m.opacity = 0.7;
    });
    g.add(grid);
    return g;
  }

  function markRise(obj, delay) {
    obj.userData.restY = obj.position.y;
    obj.userData.riseDelay = delay;
    obj.userData.riseDur = 0.58;
    obj.userData.riseT0 = clock.getElapsedTime();
    obj.position.y = obj.userData.restY - CELL;
    obj.scale.setScalar(0.12);
    obj.visible = false;
    risers.push(obj);
  }

  function clearRoot() {
    while (root.children.length) {
      const ch = root.children[0];
      root.remove(ch);
    }
    targets = [];
    portals = [];
    risers = [];
    choices = [];
    focusIndex = -1;
  }

  function choiceSlot(i, n) {
    const cols = Math.min(n, CHOICE_COLS);
    const row = Math.floor(i / cols);
    const col = i % cols;
    const rowCount = Math.min(cols, n - row * cols);
    const x = (col - (rowCount - 1) / 2) * CHOICE_STRIDE;
    const z = -(CHOICE_ROW + row * CHOICE_ROW_GAP);
    return { x, z };
  }

  function addChoice(mesh, choice) {
    mesh.userData.choice = choice;
    mesh.userData.focusScale = 1;
    choices.push({ mesh, choice });
  }

  function layout(payload) {
    clearRoot();
    root.add(floor());
    const here = chamberMesh(payload.node, { x: 0, z: 0, scale: 1, ghost: false });
    root.add(here);
    markRise(here, 0);

    const shaped = payload.shaped || [];
    const rejected = payload.rejected_siblings || [];
    const vetoes = payload.vetoes || [];
    const forks = payload.fork_children || [];
    const pathNodes = [
      ...shaped.map((n) => ({ node: n, ghost: false, via: "made" })),
      ...rejected.map((n) => ({ node: n, ghost: true, via: "not taken" })),
      ...vetoes.map((n) => ({ node: n, ghost: true, via: "human no" })),
    ];
    const pathCount = pathNodes.length + forks.length;

    pathNodes.forEach((item, i) => {
      const slot = choiceSlot(i, pathCount);
      const mesh = chamberMesh(item.node, {
        x: slot.x,
        z: slot.z,
        scale: 0.7,
        ghost: item.ghost,
      });
      root.add(mesh);
      targets.push(mesh);
      addChoice(mesh, {
        via: item.via,
        kind: item.node.kind,
        text: item.node.text,
        walk: () => inhabit(payload.graph_id, item.node.id),
      });
      markRise(mesh, 0.08 + i * 0.07);
    });

    forks.forEach((f, i) => {
      const slot = choiceSlot(pathNodes.length + i, pathCount);
      const ring = portalRing({
        x: slot.x,
        z: slot.z,
        color: 0xb08d57,
        emissive: 0x5a3c18,
        portal: { graphId: f.id, nodeId: f.spawn_node_id },
      });
      root.add(ring);
      portals.push(ring);
      addChoice(ring, {
        via: "continuation",
        kind: "fork",
        text: f.reason || "a path that omitted this chamber",
        walk: () => inhabit(f.id, f.spawn_node_id),
      });
      markRise(ring, 0.18 + i * 0.08);
    });

    const parent = payload.parent;
    if (parent && parent.graph_id && parent.node_id) {
      const back = portalRing({
        x: 0,
        z: CHOICE_ROW,
        color: 0x8a7396,
        emissive: 0x3a2040,
        portal: { graphId: parent.graph_id, nodeId: parent.node_id },
      });
      root.add(back);
      portals.push(back);
      markRise(back, 0.28);
    }

    plate(payload);
  }

  function portalRing({ x, z, color, emissive, portal }) {
    const geo = new THREE.TorusGeometry(0.7, 0.07, 10, 32);
    const mat = new THREE.MeshStandardMaterial({
      color,
      emissive,
      emissiveIntensity: 0.4,
      metalness: 0.7,
      roughness: 0.3,
    });
    const ring = new THREE.Mesh(geo, mat);
    ring.position.set(x, 0.9, z);
    ring.rotation.x = Math.PI / 2;
    ring.userData = { portal };
    const hit = new THREE.Mesh(
      new THREE.TorusGeometry(0.7, 0.22, 8, 24),
      new THREE.MeshBasicMaterial({ visible: false })
    );
    hit.rotation.x = Math.PI / 2;
    hit.userData = { portal };
    ring.add(hit);
    return ring;
  }

  function plate(payload) {
    const n = payload.node;
    const read = payload.read || {};
    elKind.textContent = read.kind_line || `${n.kind} · ${n.status}`;
    elText.textContent = n.text;
    const hereBits = [read.here_line, read.climate_line].filter(Boolean);
    elHere.textContent = hereBits.join(" · ");
    const bits = [];
    if (focusIndex >= 0 && choices[focusIndex]) {
      const c = choices[focusIndex].choice;
      const kind = (c.kind || "").replace(/_/g, " ");
      elHere.textContent = `path ${focusIndex + 1}/${choices.length} · ${c.via} · ${kind} — ${c.text}`;
      bits.push("enter walks this path · esc clears");
    } else {
      if (read.look_line) bits.push(read.look_line);
      if (choices.length) bits.push(`${choices.length} paths in front`);
      if ((payload.fork_children || []).length) bits.push("bronze ring: continuation");
      if (payload.parent && payload.parent.graph_id) bits.push("violet ring: back to the cut");
      if (trail.length) bits.push("b retraces your walk");
    }
    if (overhead) bits.push("drag to pan · c behind · shift+c home");
    elMeta.textContent = bits.join("  ·  ");
    applyClimate(payload.climate);
  }

  function sameStand(a, b) {
    return a && b && a.graphId === b.graphId && a.nodeId === b.nodeId;
  }

  async function inhabit(graphId, nodeId, origin = "walk") {
    const q = new URLSearchParams();
    if (graphId) q.set("graph", graphId);
    const payload = await api(`/api/inhabit/${nodeId}?${q.toString()}`);
    const next = { graphId: payload.graph_id, nodeId: payload.node.id };
    const prev = view
      ? { graphId: view.graph_id, nodeId: view.node.id }
      : null;
    if (origin === "walk" && prev && !sameStand(prev, next)) {
      trail.push(prev);
      if (trail.length > 80) trail.shift();
    }
    if (origin === "hash" || origin === "back") {
      while (trail.length && sameStand(trail[trail.length - 1], next)) {
        trail.pop();
      }
    }
    view = payload;
    if (origin !== "hash") hashTo(payload.graph_id, payload.node.id);
    layout(payload);
  }

  async function boot() {
    try {
      const fromHash = parseHash();
      if (fromHash) {
        await inhabit(fromHash.graphId, fromHash.nodeId, "boot");
        return;
      }
      const boot = await api("/api/sessions");
      const spawn = (boot.sessions || []).map((s) => s.spawn).find(Boolean);
      if (!spawn) {
        elEmpty.classList.add("visible");
        return;
      }
      await inhabit(spawn.graph_id, spawn.node_id, "boot");
    } catch (err) {
      elEmpty.classList.add("visible");
      elEmpty.querySelector("p").textContent = String(err.message || err);
    }
  }

  canvas.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    dragging = true;
    dragMoved = false;
    lastX = e.clientX;
    lastY = e.clientY;
  });
  window.addEventListener("pointerup", () => {
    dragging = false;
  });
  window.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    const dx = e.clientX - lastX;
    const dy = e.clientY - lastY;
    if (Math.abs(dx) + Math.abs(dy) > 3) dragMoved = true;
    lastX = e.clientX;
    lastY = e.clientY;
    if (overhead) {
      const k = 0.045;
      const lim = FLOOR_SPAN * 0.42;
      overheadLook.x -= dx * k;
      overheadLook.z += dy * k;
      overheadLook.x = Math.max(-lim, Math.min(lim, overheadLook.x));
      overheadLook.z = Math.max(-lim, Math.min(lim, overheadLook.z));
    } else {
      yaw -= dx * 0.005;
    }
  });

  function pickUserData(hits, pred) {
    for (const h of hits) {
      let o = h.object;
      while (o) {
        if (o.userData && pred(o.userData)) return o.userData;
        o = o.parent;
      }
    }
    return null;
  }

  canvas.addEventListener("click", (e) => {
    if (composing || dragMoved) return;
    const rect = canvas.getBoundingClientRect();
    pointer.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    pointer.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(pointer, camera);
    const portalHit = pickUserData(
      raycaster.intersectObjects(portals, true),
      (d) => d.portal && d.portal.graphId && d.portal.nodeId
    );
    if (portalHit) {
      inhabit(portalHit.portal.graphId, portalHit.portal.nodeId);
      return;
    }
    const nodeHit = pickUserData(
      raycaster.intersectObjects(targets, true),
      (d) => d.id
    );
    if (nodeHit && view) inhabit(view.graph_id, nodeHit.id);
  });

  function openComposer(kind) {
    if (!view || busy) return;
    composing = kind;
    elComposer.hidden = false;
    const read = (view && view.read) || {};
    elComposerLabel.textContent =
      kind === "fork"
        ? read.fork_line || "fork · accept the chain except this cut"
        : read.veto_line || "veto · this stays, with a human no";
    elComposerInput.value = "";
    elComposerInput.placeholder =
      kind === "fork" ? "why this cut (optional)" : "why this is the wrong cut";
    elComposerInput.focus();
  }

  function closeComposer() {
    composing = null;
    elComposer.hidden = true;
    elComposerInput.blur();
  }

  async function commitGesture() {
    if (!composing || !view || busy) return;
    const kind = composing;
    const reason = elComposerInput.value.trim();
    if (kind === "veto" && !reason) {
      elComposerLabel.textContent = "veto · a reason is required";
      return;
    }
    busy = true;
    try {
      const result = await post(kind === "fork" ? "/api/fork" : "/api/veto", {
        node: view.node.id,
        graph: view.graph_id,
        session: view.session_id,
        reason: reason || undefined,
      });
      closeComposer();
      const stand = result.stand;
      await inhabit(stand.graph_id, stand.node_id);
    } catch (err) {
      elComposerLabel.textContent = String(err.message || err);
    } finally {
      busy = false;
    }
  }

  function walkBack() {
    if (trail.length) {
      const prev = trail.pop();
      inhabit(prev.graphId, prev.nodeId, "back");
      return;
    }
    if (view && view.parent && view.parent.graph_id && view.parent.node_id) {
      inhabit(view.parent.graph_id, view.parent.node_id, "back");
    }
  }

  function walkDeeper() {
    if (!view) return;
    const shaped = view.shaped || [];
    if (shaped.length) {
      inhabit(view.graph_id, shaped[0].id);
      return;
    }
    const forks = view.fork_children || [];
    const first = forks.find((f) => f.id && f.spawn_node_id);
    if (first) inhabit(first.id, first.spawn_node_id);
  }

  function applyFocusVisual(mesh, on) {
    mesh.userData.focusScale = on ? 1.18 : 1;
    mesh.traverse((o) => {
      if (!o.material || !o.material.emissive) return;
      if (o.geometry && o.geometry.type === "TorusGeometry") {
        const rest = mesh.userData.ghost ? 0.2 : 0.5;
        o.material.emissiveIntensity = on ? 1.45 : rest;
      }
    });
  }

  function showFocus() {
    choices.forEach((c, i) => applyFocusVisual(c.mesh, i === focusIndex));
    if (view) plate(view);
  }

  function cycleChoice(dir) {
    if (!choices.length) return;
    if (focusIndex < 0) focusIndex = dir > 0 ? 0 : choices.length - 1;
    else focusIndex = (focusIndex + dir + choices.length) % choices.length;
    showFocus();
  }

  function selectFocus() {
    if (focusIndex < 0 || !choices[focusIndex]) return;
    choices[focusIndex].choice.walk();
  }

  function clearFocus() {
    if (focusIndex < 0) return;
    focusIndex = -1;
    showFocus();
  }

  window.addEventListener("keydown", (e) => {
    if (composing) {
      if (e.key === "Escape") {
        e.preventDefault();
        closeComposer();
      }
      if (e.key === "Enter") {
        e.preventDefault();
        commitGesture();
      }
      return;
    }
    if (e.key === "Escape") {
      e.preventDefault();
      clearFocus();
    }
    if (e.key === "Enter") {
      e.preventDefault();
      selectFocus();
    }
    if (e.key === "c" || e.key === "C") {
      e.preventDefault();
      if (e.shiftKey) {
        overhead = false;
        yaw = HOME_YAW;
        pitch = HOME_PITCH;
        overheadLook.x = 0;
        overheadLook.z = 0;
      } else {
        overhead = !overhead;
      }
      if (view) plate(view);
    }
    if (e.key === "h") {
      helpOn = !helpOn;
      elHelp.style.opacity = helpOn ? "1" : "0";
    }
    if (e.key === "f") {
      e.preventDefault();
      openComposer("fork");
    }
    if (e.key === "v") {
      e.preventDefault();
      openComposer("veto");
    }
    if (e.key === "b" || e.key === "ArrowDown") {
      e.preventDefault();
      walkBack();
    }
    if (e.key === "ArrowLeft" || e.key === "[") {
      e.preventDefault();
      cycleChoice(-1);
    }
    if (e.key === "ArrowRight" || e.key === "]") {
      e.preventDefault();
      cycleChoice(1);
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      walkDeeper();
    }
  });

  window.addEventListener("hashchange", () => {
    const h = parseHash();
    if (!h || !view) return;
    if (h.nodeId !== view.node.id || h.graphId !== view.graph_id) {
      inhabit(h.graphId, h.nodeId, "hash");
    }
  });

  function tickRise(t) {
    for (const o of risers) {
      const u = o.userData;
      const k = (t - u.riseT0 - u.riseDelay) / u.riseDur;
      if (k < 0) {
        o.visible = false;
        continue;
      }
      o.visible = true;
      const e = 1 - Math.pow(1 - Math.min(k, 1), 3);
      const bounce = k > 1 ? 1 : e;
      o.position.y = u.restY - CELL * (1 - bounce);
      const dest = o.userData.focusScale || 1;
      o.scale.setScalar(0.12 + (dest - 0.12) * bounce);
    }
  }

  function tick() {
    const t = clock.getElapsedTime();
    if (overhead) {
      camera.up.set(0, 0, -1);
      camera.position.set(overheadLook.x, 26, overheadLook.z);
      camera.lookAt(overheadLook.x, 0, overheadLook.z);
      overSun.intensity = 2.35;
      overHemi.intensity = 1.05;
      key.intensity = 0.35;
      fill.intensity = 0.2;
      starFill.intensity = 0.55;
      scene.fog.density = 0.005;
    } else {
      camera.up.set(0, 1, 0);
      const r = 8.2;
      camera.position.x = Math.sin(yaw) * r;
      camera.position.z = Math.cos(yaw) * r;
      camera.position.y = 2.6 + Math.sin(pitch) * 0.4 + Math.sin(t * 0.4) * 0.05;
      camera.lookAt(0, 1.4, 0);
      overSun.intensity = 0;
      overHemi.intensity = 0;
      key.intensity = 1.25 + Math.sin(t * 1.3) * 0.15;
      fill.intensity = 0.7;
      starFill.intensity = 0.22;
      scene.fog.density = climateFog;
    }
    if (sky) sky.rotation.y = t * 0.0045;
    tickRise(t);
    renderer.render(scene, camera);
    requestAnimationFrame(tick);
  }

  sky = makeSky();
  scene.add(sky);
  boot();
  tick();
})();
