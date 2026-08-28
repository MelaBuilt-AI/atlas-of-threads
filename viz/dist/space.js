/* Inhabit Space v0 — stand at a node. Not a dashboard. */
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
  const elMeta = document.getElementById("meta");
  const elEmpty = document.getElementById("empty");
  const elHelp = document.getElementById("help");

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setClearColor(0x12100e, 1);

  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x12100e, 0.045);

  const camera = new THREE.PerspectiveCamera(55, 1, 0.1, 80);
  camera.position.set(0, 2.4, 7.2);

  const clock = new THREE.Clock();
  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();

  let view = null;
  let targets = [];
  let cycle = [];
  let cycleIndex = 0;
  let dragging = false;
  let lastX = 0;
  let yaw = 0.18;
  let pitch = 0.22;
  let helpOn = true;

  const root = new THREE.Group();
  scene.add(root);

  scene.add(new THREE.AmbientLight(0x3a342c, 0.55));
  const key = new THREE.PointLight(0xc8f26a, 1.4, 28, 2);
  key.position.set(0, 3.2, 1.5);
  scene.add(key);
  const fill = new THREE.PointLight(0xb08d57, 0.7, 22, 2);
  fill.position.set(-4, 1.4, 3);
  scene.add(fill);

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

  async function api(path) {
    const res = await fetch(path);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: res.statusText }));
      throw new Error(err.error || res.statusText);
    }
    return res.json();
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
    g.userData = { id: node.id, kind: node.kind };

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
    const m = new THREE.Mesh(
      new THREE.CircleGeometry(18, 48),
      stoneMat(0x1a1713, 1)
    );
    m.rotation.x = -Math.PI / 2;
    m.receiveShadow = true;
    return m;
  }

  function clearRoot() {
    while (root.children.length) {
      const ch = root.children[0];
      root.remove(ch);
    }
    targets = [];
  }

  function layout(payload) {
    clearRoot();
    root.add(floor());
    const here = chamberMesh(payload.node, { x: 0, z: 0, scale: 1, ghost: false });
    root.add(here);

    const shaped = payload.shaped || [];
    shaped.forEach((n, i) => {
      const t = (i - (shaped.length - 1) / 2) * 0.55;
      const mesh = chamberMesh(n, {
        x: Math.sin(t) * 6.2,
        z: -6.8 - Math.cos(t) * 0.4,
        scale: 0.72,
        ghost: false,
      });
      root.add(mesh);
      targets.push(mesh);
    });

    const rejected = payload.rejected_siblings || [];
    rejected.forEach((n, i) => {
      const side = i % 2 === 0 ? -1 : 1;
      const row = Math.floor(i / 2);
      const mesh = chamberMesh(n, {
        x: side * (7.4 + row * 0.4),
        z: 1.2 + row * 2.4,
        scale: 0.62,
        ghost: true,
      });
      root.add(mesh);
      targets.push(mesh);
    });

    const forks = payload.fork_children || [];
    forks.forEach((f, i) => {
      const geo = new THREE.TorusGeometry(0.7, 0.07, 10, 32);
      const mat = new THREE.MeshStandardMaterial({
        color: 0xb08d57,
        emissive: 0x5a3c18,
        emissiveIntensity: 0.4,
        metalness: 0.7,
        roughness: 0.3,
      });
      const ring = new THREE.Mesh(geo, mat);
      ring.position.set((i - (forks.length - 1) / 2) * 2.2, 0.9, 5.4);
      ring.rotation.x = Math.PI / 2;
      ring.userData = { id: null, forkGraph: f.id };
      root.add(ring);
    });

    cycle = [payload.node, ...shaped, ...rejected];
    cycleIndex = 0;
    plate(payload);
  }

  function plate(payload) {
    const n = payload.node;
    elKind.textContent = `${n.kind} · ${n.status} · ${n.agent}`;
    elText.textContent = n.text;
    const bits = [
      `graph ${payload.graph_id}`,
      `${(payload.shaped || []).length} shaped`,
      `${(payload.rejected_siblings || []).length} negative space`,
      `${(payload.fork_children || []).length} forks`,
    ];
    elMeta.textContent = bits.join("  ·  ");
  }

  async function inhabit(graphId, nodeId) {
    const q = new URLSearchParams();
    if (graphId) q.set("graph", graphId);
    const payload = await api(`/api/inhabit/${nodeId}?${q.toString()}`);
    view = payload;
    hashTo(payload.graph_id, payload.node.id);
    layout(payload);
  }

  async function boot() {
    try {
      const fromHash = parseHash();
      if (fromHash) {
        await inhabit(fromHash.graphId, fromHash.nodeId);
        return;
      }
      const boot = await api("/api/sessions");
      const spawn = (boot.sessions || []).map((s) => s.spawn).find(Boolean);
      if (!spawn) {
        elEmpty.classList.add("visible");
        return;
      }
      await inhabit(spawn.graph_id, spawn.node_id);
    } catch (err) {
      elEmpty.classList.add("visible");
      elEmpty.querySelector("p").textContent = String(err.message || err);
    }
  }

  canvas.addEventListener("pointerdown", (e) => {
    dragging = true;
    lastX = e.clientX;
  });
  window.addEventListener("pointerup", () => {
    dragging = false;
  });
  window.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    yaw -= (e.clientX - lastX) * 0.005;
    lastX = e.clientX;
  });

  canvas.addEventListener("click", (e) => {
    const rect = canvas.getBoundingClientRect();
    pointer.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    pointer.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(pointer, camera);
    const hits = raycaster.intersectObjects(targets, true);
    const hit = hits.find((h) => {
      let o = h.object;
      while (o) {
        if (o.userData && o.userData.id) return true;
        o = o.parent;
      }
      return false;
    });
    if (!hit) return;
    let o = hit.object;
    while (o && !(o.userData && o.userData.id)) o = o.parent;
    if (o && o.userData.id && view) inhabit(view.graph_id, o.userData.id);
  });

  window.addEventListener("keydown", (e) => {
    if (e.key === "h") {
      helpOn = !helpOn;
      elHelp.style.opacity = helpOn ? "1" : "0";
    }
    if (e.key === "[" || e.key === "]") {
      if (!cycle.length || !view) return;
      cycleIndex = (cycleIndex + (e.key === "]" ? 1 : -1) + cycle.length) % cycle.length;
      inhabit(view.graph_id, cycle[cycleIndex].id);
    }
  });

  window.addEventListener("hashchange", () => {
    const h = parseHash();
    if (!h || !view) return;
    if (h.nodeId !== view.node.id) inhabit(h.graphId, h.nodeId);
  });

  function tick() {
    const t = clock.getElapsedTime();
    const r = 8.2;
    camera.position.x = Math.sin(yaw) * r;
    camera.position.z = Math.cos(yaw) * r;
    camera.position.y = 2.6 + Math.sin(pitch) * 0.4 + Math.sin(t * 0.4) * 0.05;
    camera.lookAt(0, 1.4, 0);
    key.intensity = 1.25 + Math.sin(t * 1.3) * 0.15;
    renderer.render(scene, camera);
    requestAnimationFrame(tick);
  }

  boot();
  tick();
})();
