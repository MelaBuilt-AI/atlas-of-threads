/* Inhabit Space — stand at a node. Fork/veto are gestures. Not a dashboard. */
(function () {
  const KIND_COLOR = {
    claim: 0xe8d5a3,
    premise: 0x8fa9c4,
    analogy: 0xd4a0b0,
    judgment_call: 0xf0a35e,
    uncertainty: 0x5c8a7b,
    rejected_alternative: 0x8a7396,
  };

  const RELICS = [
    ["archaeology-scanner", "Archaeology Scanner", "activation correlation · measured internal activity"],
    ["causal-test-crucible", "Causal Test Crucible", "recurring circuit · repeated causal tests"],
    ["commit-tablet", "Commit Tablet", "judgment call · a committed cut"],
    ["counterfactual-shard-gate", "Counterfactual Shard Gate", "return path · the cut behind you"],
    ["fork-compass", "Fork Compass", "continuation · a navigable fork"],
    ["forked-claim", "Forked Claim", "forked status · a claim on another path"],
    ["gray-box-prism", "Gray-Box Prism", "uncertainty · bounded unknowns"],
    ["intervened-claim", "Intervened Claim", "behavioral evidence · a tested thought"],
    ["intervention-key", "Intervention Key", "neural intervention · a causal internal edit"],
    ["named-parts-astrolabe", "Named-Parts Astrolabe", "analogy · a mapping used to think"],
    ["narrated-claim", "Narrated Claim", "claim · the answer's stated story"],
    ["provenance-lens", "Provenance Lens", "context provenance · an earlier artifact"],
    ["shared-mind-chamber", "Shared-Mind Chamber", "inhabitable medium · a shared thought object"],
    ["source-mapped-claim", "Source-Mapped Claim", "source map · story bound to evidence"],
    ["story-mask", "Story Mask", "rejected alternative · visible negative space"],
    ["stratigraphic-thought-core", "Stratigraphic Thought Core", "checkpoint emergence · change through layers"],
    ["tacit-claim", "Tacit Claim", "premise · a supporting belief"],
    ["tacit-knowledge-fossil", "Tacit-Knowledge Fossil", "unspoken premise · preserved assumption"],
    ["thought-graph-reliquary", "Thought-Graph Reliquary", "thought graph · the inspectable object"],
    ["two-whys-vessel", "Two-Whys Vessel", "story and machinery · held apart, then bound"],
  ].map(([key, name, role]) => ({
    key,
    name,
    role,
    model: `./assets/models/${key}.glb`,
    preview: `./assets/previews/${key}.png`,
  }));
  const RELIC_BY_KEY = Object.fromEntries(RELICS.map((relic) => [relic.key, relic]));
  const KIND_RELIC = {
    claim: "narrated-claim",
    premise: "tacit-claim",
    analogy: "named-parts-astrolabe",
    judgment_call: "commit-tablet",
    taste_call: "commit-tablet",
    uncertainty: "gray-box-prism",
    rejected_alternative: "story-mask",
  };
  const EVIDENCE_RELIC = {
    story_report: "narrated-claim",
    context_provenance: "provenance-lens",
    behavioral_intervention: "intervened-claim",
    activation_correlation: "archaeology-scanner",
    neural_intervention: "intervention-key",
    recurring_circuit: "causal-test-crucible",
    checkpoint_emergence: "stratigraphic-thought-core",
    training_provenance: "source-mapped-claim",
    training_influence: "source-mapped-claim",
  };

  const canvas = document.getElementById("c");
  const elBanner = document.getElementById("banner");
  const elKind = document.getElementById("kind");
  const elText = document.getElementById("text");
  const elHere = document.getElementById("here");
  const elMeta = document.getElementById("meta");
  const elPlate = document.getElementById("plate");
  const elEmpty = document.getElementById("empty");
  const elHelp = document.getElementById("help");
  const elComposer = document.getElementById("composer");
  const elComposerLabel = document.getElementById("composer-label");
  const elComposerInput = document.getElementById("composer-input");
  const elThreshold = document.getElementById("threshold");
  const elThresholdKind = document.getElementById("threshold-kind");
  const elThresholdText = document.getElementById("threshold-text");
  const elThresholdOrigin = document.getElementById("threshold-origin");
  const elThresholdContinue = document.getElementById("threshold-continue");
  const elThresholdAsk = document.getElementById("threshold-ask");
  const elThresholdAskBox = document.getElementById("threshold-ask-box");
  const elThresholdAskInput = document.getElementById("threshold-ask-input");
  const elRelicIndex = document.getElementById("relic-index");
  const elRelicGrid = document.getElementById("relic-grid");
  const elRelicClose = document.getElementById("relic-close");
  const elEvidenceDescent = document.getElementById("evidence-descent");
  const elStoryIntro = document.getElementById("story-intro");
  const elStoryGroups = document.getElementById("story-groups");
  const elEvidenceIntro = document.getElementById("evidence-intro");
  const elEvidenceStrata = document.getElementById("evidence-strata");
  const elEvidenceClose = document.getElementById("evidence-close");
  const elSoundControls = document.getElementById("sound-controls");
  const sound = window.TASound;

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setClearColor(0x12100e, 1);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x12100e, 0.045);

  const CELL = 1.4; // default claim box footprint
  const FLOOR_CELLS = 30;
  const FLOOR_SPAN = CELL * FLOOR_CELLS;
  const CHOICE_STRIDE = CELL * 3; // equal cells; clears scaled boards (~1.8)
  const CHOICE_ROW = CELL * 4;
  const CHOICE_ROW_GAP = CELL * 3;
  const CHOICE_COLS = 7;
  const DEFAULT_SELECTION_COLOR = 0xe2c48a;
  const NEW_PATH_SELECTION_COLOR = 0x4f8fd6;
  const WAITING_BEAM_COLOR = 0x5df58a;
  const RETURN_COLOR = 0xc94f4f;
  const RETURN_EMISSIVE = 0x641818;

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
  let neuralSky = null;
  let trail = [];
  let overhead = false;
  let manualRelicKey = null;
  let mappedRelicKey = "narrated-claim";
  let layoutGeneration = 0;
  let standingMesh = null;
  const COMPANION_MEMORY_KEY = "thought-archaeology.companions.v1";
  const CIRCUIT_MEMORY_KEY = "thought-archaeology.continuation-circuit.v1";
  const knownHeads = new Map();
  const sessionTitles = new Map();
  let liveArrivals = loadCompanionThoughts();
  let arrivalsDirty = false;
  let arrivingFocus = null;
  let rememberedCircuit = loadContinuationCircuit();
  let continuationCircuit = null;
  let companionPolling = false;
  let companionReady = false;

  function loadCompanionThoughts() {
    try {
      const saved = JSON.parse(window.localStorage.getItem(COMPANION_MEMORY_KEY) || "[]");
      if (!Array.isArray(saved)) return [];
      return saved.filter(
        (item) => item && item.graphId && item.nodeId && item.text && item.title
      ).slice(-12);
    } catch (_error) {
      return [];
    }
  }

  function saveCompanionThoughts() {
    try {
      window.localStorage.setItem(
        COMPANION_MEMORY_KEY,
        JSON.stringify(liveArrivals.slice(-12))
      );
    } catch (_error) {
      // Browser memory is optional; the graph store remains canonical.
    }
  }

  function loadContinuationCircuit() {
    try {
      const saved = JSON.parse(window.localStorage.getItem(CIRCUIT_MEMORY_KEY));
      if (
        !saved || !saved.requestId || !Number.isInteger(saved.neuronIndex) ||
        (saved.phase !== "waiting" && saved.phase !== "arrival")
      ) return null;
      return saved;
    } catch (_error) {
      return null;
    }
  }

  function saveContinuationCircuit() {
    try {
      if (rememberedCircuit) {
        window.localStorage.setItem(
          CIRCUIT_MEMORY_KEY, JSON.stringify(rememberedCircuit)
        );
      } else {
        window.localStorage.removeItem(CIRCUIT_MEMORY_KEY);
      }
    } catch (_error) {
      // The animation remains functional without tab-scoped memory.
    }
  }

  function rememberCompanion(entry) {
    const previous = liveArrivals.find(
      (item) =>
        item.graphId === entry.graphId &&
        item.nodeId === entry.nodeId &&
        item.anchorGraphId === entry.anchorGraphId
    );
    const remembered = previous
      ? { ...previous, ...entry, seen: Boolean(previous.seen || entry.seen) }
      : entry;
    liveArrivals = liveArrivals.filter(
      (item) =>
        item.graphId !== entry.graphId ||
        item.nodeId !== entry.nodeId ||
        item.anchorGraphId !== entry.anchorGraphId
    );
    liveArrivals.push(remembered);
    liveArrivals = liveArrivals.slice(-12);
    saveCompanionThoughts();
  }

  function companionFromSession(session, seen = false, anchorGraphId = null) {
    if (!session || !session.head_graph_id || !session.spawn) return null;
    const entry = {
      sessionId: session.id,
      graphId: session.head_graph_id,
      nodeId: session.spawn.node_id,
      kind: session.spawn.node.kind,
      text: session.spawn.node.text,
      title: session.title || "untitled thought",
      seen,
    };
    if (anchorGraphId) entry.anchorGraphId = anchorGraphId;
    if (session.spawn.continuation_harness) {
      entry.harness = session.spawn.continuation_harness;
    }
    if (session.spawn.model && session.spawn.model.name !== "unknown") {
      entry.modelName = session.spawn.model.name;
    }
    return entry;
  }

  function companionAttribution(arrival) {
    const harness = arrival.harness
      ? arrival.harness.charAt(0).toUpperCase() + arrival.harness.slice(1)
      : "";
    return [harness, arrival.modelName].filter(Boolean).join(" · ");
  }

  function companionTitle(arrival) {
    const attribution = companionAttribution(arrival);
    return attribution ? `${attribution} · ${arrival.title}` : arrival.title;
  }

  function graphAttribution(payload) {
    const harness = payload.continuation_harness
      ? payload.continuation_harness.charAt(0).toUpperCase() +
        payload.continuation_harness.slice(1)
      : "";
    const modelName = payload.model && payload.model.name !== "unknown"
      ? payload.model.name
      : "";
    return [harness, modelName].filter(Boolean).join(" · ");
  }

  function continuationSourceArrival(payload) {
    const source = payload.continuation_source;
    if (!source || source.graph_id === payload.graph_id) return null;
    const entry = {
      sessionId: source.session_id,
      graphId: source.graph_id,
      nodeId: source.node_id,
      anchorGraphId: payload.graph_id,
      kind: "return",
      text: "Return to conversation origin",
      title: "Return to conversation origin",
      seen: true,
      via: "conversation origin",
      labelKind: "conversation origin",
      description: "Return to conversation origin",
      returnOrigin: true,
    };
    if (source.model && source.model.name !== "unknown") {
      entry.modelName = source.model.name;
    }
    return entry;
  }

  function visibleArrivals(payload) {
    let arrivals = liveArrivals.filter(
      (arrival) =>
        arrival.anchorGraphId === payload.graph_id &&
        arrival.graphId !== payload.graph_id
    );
    const source = continuationSourceArrival(payload);
    if (source) {
      arrivals = arrivals.filter(
        (arrival) =>
          arrival.graphId !== source.graphId || arrival.nodeId !== source.nodeId
      );
      arrivals.unshift(source);
    }
    return arrivals;
  }

  const root = new THREE.Group();
  scene.add(root);

  scene.add(new THREE.AmbientLight(0x3a342c, 0.55));
  const keyTarget = new THREE.Object3D();
  scene.add(keyTarget);
  const key = new THREE.SpotLight(0xc8f26a, 950, 32, Math.PI / 5, 0.62, 1.5);
  key.position.set(3, 5.8, 3.5);
  key.target = keyTarget;
  key.castShadow = true;
  key.shadow.mapSize.set(1024, 1024);
  key.shadow.bias = -0.0008;
  scene.add(key);
  const selectionTarget = new THREE.Object3D();
  scene.add(selectionTarget);
  const selectionSpot = new THREE.SpotLight(
    DEFAULT_SELECTION_COLOR,
    0,
    30,
    Math.PI / 7,
    0.72,
    1.45
  );
  selectionSpot.position.set(-2.5, 5.2, 2.8);
  selectionSpot.target = selectionTarget;
  scene.add(selectionSpot);
  const fill = new THREE.PointLight(0xb08d57, 0.7, 22, 2);
  fill.position.set(-4, 1.4, 3);
  scene.add(fill);
  const neuralFill = new THREE.AmbientLight(0x1a2240, 0.22);
  scene.add(neuralFill);
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
    document.documentElement.style.setProperty(
      "--plate-height", `${Math.ceil(elPlate.getBoundingClientRect().height)}px`
    );
    const thresholdHeight = elThreshold.hidden
      ? 0
      : Math.ceil(elThreshold.getBoundingClientRect().height) + 12;
    document.documentElement.style.setProperty(
      "--threshold-stack-height", `${thresholdHeight}px`
    );
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

  function ambientTexture() {
    const c = document.createElement("canvas");
    c.width = c.height = 1024;
    const ctx = c.getContext("2d");
    const g = ctx.createRadialGradient(512, 590, 40, 512, 512, 700);
    g.addColorStop(0, "#12203a");
    g.addColorStop(0.22, "#0a1428");
    g.addColorStop(0.55, "#060b18");
    g.addColorStop(1, "#02040a");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, 1024, 1024);
    const tex = new THREE.CanvasTexture(c);
    if (THREE.SRGBColorSpace) tex.colorSpace = THREE.SRGBColorSpace;
    tex.needsUpdate = true;
    return tex;
  }

  function neuronTexture() {
    const c = document.createElement("canvas");
    c.width = c.height = 64;
    const ctx = c.getContext("2d");
    const g = ctx.createRadialGradient(32, 32, 1, 32, 32, 31);
    g.addColorStop(0, "rgba(240,255,214,1)");
    g.addColorStop(0.16, "rgba(200,242,106,0.95)");
    g.addColorStop(0.48, "rgba(92,196,182,0.45)");
    g.addColorStop(1, "rgba(42,105,112,0)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, 64, 64);
    const tex = new THREE.CanvasTexture(c);
    if (THREE.SRGBColorSpace) tex.colorSpace = THREE.SRGBColorSpace;
    return tex;
  }

  function makeNeuralSky(texture) {
    const group = new THREE.Group();
    const geo = new THREE.SphereGeometry(120, 48, 32);
    const mat = new THREE.MeshBasicMaterial({
      map: texture,
      side: THREE.BackSide,
      fog: false,
      depthWrite: false,
    });
    group.add(new THREE.Mesh(geo, mat));

    let seed = 19;
    function rnd() {
      seed = (seed * 16807) % 2147483647;
      return (seed - 1) / 2147483646;
    }
    const nodes = [];
    const count = 170;
    const goldenAngle = Math.PI * (3 - Math.sqrt(5));
    for (let i = 0; i < count; i++) {
      const y = 1 - (i / (count - 1)) * 2;
      const radius = Math.sqrt(1 - y * y);
      const theta = goldenAngle * i;
      const shell = 64 + rnd() * 12;
      nodes.push(new THREE.Vector3(
        Math.cos(theta) * radius * shell,
        y * shell,
        Math.sin(theta) * radius * shell
      ));
    }

    const nodePositions = new Float32Array(nodes.length * 3);
    nodes.forEach((node, i) => node.toArray(nodePositions, i * 3));
    const nodeGeometry = new THREE.BufferGeometry();
    nodeGeometry.setAttribute("position", new THREE.BufferAttribute(nodePositions, 3));
    const glow = neuronTexture();
    group.add(new THREE.Points(nodeGeometry, new THREE.PointsMaterial({
      color: 0xb9f5c9,
      map: glow,
      size: 1.2,
      transparent: true,
      opacity: 0.78,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      fog: false,
    })));

    const edges = [];
    for (let i = 0; i < nodes.length; i++) {
      const candidates = [];
      for (let j = i + 1; j < nodes.length; j++) {
        candidates.push({ j, distance: nodes[i].distanceToSquared(nodes[j]) });
      }
      candidates.sort((a, b) => a.distance - b.distance);
      for (const candidate of candidates.slice(0, i % 4 === 0 ? 3 : 2)) {
        edges.push([nodes[i], nodes[candidate.j]]);
      }
    }
    const linePositions = new Float32Array(edges.length * 6);
    edges.forEach(([start, end], i) => {
      start.toArray(linePositions, i * 6);
      end.toArray(linePositions, i * 6 + 3);
    });
    const lineGeometry = new THREE.BufferGeometry();
    lineGeometry.setAttribute("position", new THREE.BufferAttribute(linePositions, 3));
    group.add(new THREE.LineSegments(lineGeometry, new THREE.LineBasicMaterial({
      color: 0x438f99,
      transparent: true,
      opacity: 0.2,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      fog: false,
    })));

    const pulses = Array.from({ length: 54 }, (_, i) => ({
      edge: edges[(i * 17) % edges.length],
      phase: rnd(),
      speed: 0.035 + rnd() * 0.065,
    }));
    const pulsePositions = new Float32Array(pulses.length * 3);
    const pulseGeometry = new THREE.BufferGeometry();
    pulseGeometry.setAttribute("position", new THREE.BufferAttribute(pulsePositions, 3));
    group.add(new THREE.Points(pulseGeometry, new THREE.PointsMaterial({
      color: 0xc8f26a,
      map: glow,
      size: 1.8,
      transparent: true,
      opacity: 0.95,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      fog: false,
    })));
    const sparksPerPulse = 3;
    const sparkPositions = new Float32Array(pulses.length * sparksPerPulse * 3);
    const sparkColors = new Float32Array(sparkPositions.length);
    const sparkGeometry = new THREE.BufferGeometry();
    sparkGeometry.setAttribute("position", new THREE.BufferAttribute(sparkPositions, 3));
    sparkGeometry.setAttribute("color", new THREE.BufferAttribute(sparkColors, 3));
    group.add(new THREE.Points(sparkGeometry, new THREE.PointsMaterial({
      color: 0xffffff,
      map: glow,
      vertexColors: true,
      size: 0.9,
      transparent: true,
      opacity: 0.95,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      fog: false,
    })));
    group.userData.sky = true;
    return {
      group,
      nodes,
      glow,
      pulses,
      pulsePositions,
      pulseGeometry,
      sparksPerPulse,
      sparkPositions,
      sparkColors,
      sparkGeometry,
    };
  }

  function updateNeuralSky(t) {
    if (!neuralSky) return;
    neuralSky.pulses.forEach((pulse, i) => {
      const u = (pulse.phase + t * pulse.speed) % 1;
      const [start, end] = pulse.edge;
      neuralSky.pulsePositions[i * 3] = THREE.MathUtils.lerp(start.x, end.x, u);
      neuralSky.pulsePositions[i * 3 + 1] = THREE.MathUtils.lerp(start.y, end.y, u);
      neuralSky.pulsePositions[i * 3 + 2] = THREE.MathUtils.lerp(start.z, end.z, u);
      const px = neuralSky.pulsePositions[i * 3];
      const py = neuralSky.pulsePositions[i * 3 + 1];
      const pz = neuralSky.pulsePositions[i * 3 + 2];
      const flicker = Math.max(
        0,
        (Math.sin(t * 13 + i * 2.17 + u * 24) - 0.45) / 0.55
      );
      const junction = u > 0.9 ? (u - 0.9) * 10 : 0;
      const energy = Math.max(flicker, junction);
      for (let j = 0; j < neuralSky.sparksPerPulse; j++) {
        const at = (i * neuralSky.sparksPerPulse + j) * 3;
        const angle = t * (5 + j) + i * 1.7 + j * Math.PI * 0.67;
        const reach = 0.16 + energy * (0.35 + j * 0.1);
        neuralSky.sparkPositions[at] = px + Math.cos(angle) * reach;
        neuralSky.sparkPositions[at + 1] = py + Math.sin(angle * 1.3) * reach;
        neuralSky.sparkPositions[at + 2] = pz + Math.sin(angle) * reach;
        neuralSky.sparkColors[at] = energy;
        neuralSky.sparkColors[at + 1] = energy * 0.95;
        neuralSky.sparkColors[at + 2] = energy * 0.42;
      }
    });
    neuralSky.pulseGeometry.attributes.position.needsUpdate = true;
    neuralSky.sparkGeometry.attributes.position.needsUpdate = true;
    neuralSky.sparkGeometry.attributes.color.needsUpdate = true;
    neuralSky.group.rotation.y = t * 0.0045;
  }

  function neuronAtOrAboveMesh(index, mesh) {
    if (!neuralSky || !mesh || index < 0 || index >= neuralSky.nodes.length) {
      return false;
    }
    const sourceTop = new THREE.Box3().setFromObject(mesh).max.y;
    const world = neuralSky.nodes[index].clone();
    neuralSky.group.localToWorld(world);
    return world.y >= sourceTop;
  }

  function visibleNeuronIndex(sourceMesh) {
    if (!neuralSky || !neuralSky.nodes.length) return -1;
    scene.updateMatrixWorld(true);
    camera.updateMatrixWorld(true);
    const visible = [];
    const highEnough = [];
    const world = new THREE.Vector3();
    const projected = new THREE.Vector3();
    const minimumY = sourceMesh
      ? new THREE.Box3().setFromObject(sourceMesh).max.y
      : -Infinity;
    neuralSky.nodes.forEach((node, index) => {
      world.copy(node);
      neuralSky.group.localToWorld(world);
      if (world.y < minimumY) return;
      highEnough.push(index);
      projected.copy(world).project(camera);
      if (
        projected.z > -1 && projected.z < 1 &&
        Math.abs(projected.x) > 0.2 && Math.abs(projected.x) < 0.82 &&
        projected.y > 0.32 && projected.y < 0.88
      ) visible.push(index);
    });
    const candidates = visible.length
      ? visible
      : highEnough;
    if (!candidates.length) return -1;
    return candidates[Math.floor(Math.random() * candidates.length)];
  }

  function makeContinuationLightning(color) {
    const segments = 42;
    const positions = new Float32Array((segments + 1) * 3);
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    const haloMaterial = new THREE.LineBasicMaterial({
      color,
      transparent: true,
      opacity: 0.22,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      fog: false,
    });
    const coreMaterial = new THREE.LineBasicMaterial({
      color,
      transparent: true,
      opacity: 0.96,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      fog: false,
    });
    const group = new THREE.Group();
    group.add(new THREE.Line(geometry, haloMaterial));
    group.add(new THREE.Line(geometry, coreMaterial));

    const sparkCount = 34;
    const sparkPositions = new Float32Array(sparkCount * 3);
    const sparkGeometry = new THREE.BufferGeometry();
    sparkGeometry.setAttribute(
      "position", new THREE.BufferAttribute(sparkPositions, 3)
    );
    const sparkMaterial = new THREE.PointsMaterial({
      color,
      map: neuralSky.glow,
      size: 0.72,
      transparent: true,
      opacity: 0.95,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      fog: false,
    });
    group.add(new THREE.Points(sparkGeometry, sparkMaterial));

    const jointPositions = new Float32Array(6);
    const jointGeometry = new THREE.BufferGeometry();
    jointGeometry.setAttribute(
      "position", new THREE.BufferAttribute(jointPositions, 3)
    );
    const jointMaterial = new THREE.PointsMaterial({
      color,
      map: neuralSky.glow,
      size: 2.1,
      transparent: true,
      opacity: 0.95,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      fog: false,
    });
    group.add(new THREE.Points(jointGeometry, jointMaterial));
    group.renderOrder = 8;
    scene.add(group);
    return {
      group,
      segments,
      positions,
      geometry,
      sparkCount,
      sparkPositions,
      sparkGeometry,
      jointPositions,
      jointGeometry,
      materials: [haloMaterial, coreMaterial, sparkMaterial, jointMaterial],
      seed: Math.random() * 1000,
    };
  }

  function setContinuationLightningColor(lightning, color) {
    lightning.materials.forEach((material) => material.color.setHex(color));
  }

  function clearContinuationCircuit() {
    if (continuationCircuit) {
      const lightning = continuationCircuit.lightning;
      scene.remove(lightning.group);
      lightning.geometry.dispose();
      lightning.sparkGeometry.dispose();
      lightning.jointGeometry.dispose();
      lightning.materials.forEach((material) => material.dispose());
    }
    continuationCircuit = null;
    rememberedCircuit = null;
    saveContinuationCircuit();
    sound.setBeam(null);
  }

  function beginContinuationCircuit(request) {
    if (!request || !request.id || !standingMesh || !neuralSky) return;
    if (continuationCircuit && continuationCircuit.requestId === request.id) {
      continuationCircuit.targetMesh = standingMesh;
      return;
    }
    const saved = rememberedCircuit;
    clearContinuationCircuit();
    const retained = saved &&
      saved.requestId === request.id &&
      saved.phase === "waiting" &&
      neuronAtOrAboveMesh(saved.neuronIndex, standingMesh)
      ? saved.neuronIndex
      : -1;
    const neuronIndex = retained >= 0 && retained < neuralSky.nodes.length
      ? retained
      : visibleNeuronIndex(standingMesh);
    if (neuronIndex < 0) return;
    continuationCircuit = {
      requestId: request.id,
      sourceGraphId: request.graph_id || (view && view.graph_id),
      sourceNodeId: request.node_id || (view && view.node.id),
      neuronIndex,
      phase: "waiting",
      targetGraphId: null,
      targetNodeId: null,
      targetMesh: standingMesh,
      lightning: makeContinuationLightning(WAITING_BEAM_COLOR),
    };
    rememberedCircuit = {
      requestId: request.id,
      sourceGraphId: continuationCircuit.sourceGraphId,
      sourceNodeId: continuationCircuit.sourceNodeId,
      neuronIndex,
      phase: "waiting",
      targetGraphId: null,
      targetNodeId: null,
    };
    saveContinuationCircuit();
    sound.setBeam("waiting", retained < 0);
  }

  function completeContinuationCircuit(mesh, arrival) {
    if (!continuationCircuit || continuationCircuit.phase !== "waiting") return;
    continuationCircuit.phase = "arrival";
    continuationCircuit.targetGraphId = arrival.graphId;
    continuationCircuit.targetNodeId = arrival.nodeId;
    continuationCircuit.targetMesh = mesh;
    setContinuationLightningColor(
      continuationCircuit.lightning, NEW_PATH_SELECTION_COLOR
    );
    rememberedCircuit = {
      requestId: continuationCircuit.requestId,
      sourceGraphId: continuationCircuit.sourceGraphId,
      sourceNodeId: continuationCircuit.sourceNodeId,
      neuronIndex: continuationCircuit.neuronIndex,
      phase: "arrival",
      targetGraphId: arrival.graphId,
      targetNodeId: arrival.nodeId,
    };
    saveContinuationCircuit();
    sound.setWorking(false);
    sound.setBeam("arrival");
    sound.arrivalSplash();
  }

  function restoreArrivalCircuit(mesh, arrival) {
    const saved = rememberedCircuit;
    if (
      continuationCircuit && continuationCircuit.phase === "arrival" &&
      continuationCircuit.targetGraphId === arrival.graphId &&
      continuationCircuit.targetNodeId === arrival.nodeId
    ) {
      continuationCircuit.targetMesh = mesh;
      return;
    }
    if (
      continuationCircuit || !saved || saved.phase !== "arrival" ||
      saved.targetGraphId !== arrival.graphId ||
      saved.targetNodeId !== arrival.nodeId ||
      saved.neuronIndex < 0 || saved.neuronIndex >= neuralSky.nodes.length
    ) return;
    const neuronIndex = neuronAtOrAboveMesh(saved.neuronIndex, standingMesh)
      ? saved.neuronIndex
      : visibleNeuronIndex(standingMesh);
    if (neuronIndex < 0) return;
    continuationCircuit = {
      ...saved,
      neuronIndex,
      targetMesh: mesh,
      lightning: makeContinuationLightning(NEW_PATH_SELECTION_COLOR),
    };
    rememberedCircuit = { ...saved, neuronIndex };
    saveContinuationCircuit();
    sound.setBeam("arrival");
  }

  const circuitBox = new THREE.Box3();
  const circuitStart = new THREE.Vector3();
  const circuitEnd = new THREE.Vector3();
  const circuitDirection = new THREE.Vector3();
  const circuitSide = new THREE.Vector3();
  const circuitLift = new THREE.Vector3();
  const circuitPoint = new THREE.Vector3();
  const circuitNeuron = new THREE.Vector3();

  function meshTop(mesh, out) {
    circuitBox.setFromObject(mesh);
    circuitBox.getCenter(out);
    out.y = circuitBox.max.y + 0.08;
    return out;
  }

  function updateContinuationCircuit(t) {
    const circuit = continuationCircuit;
    if (!circuit || !circuit.targetMesh || !circuit.targetMesh.parent) return;
    neuralSky.group.updateMatrixWorld(true);
    circuitNeuron.copy(neuralSky.nodes[circuit.neuronIndex]);
    neuralSky.group.localToWorld(circuitNeuron);
    if (circuit.phase === "waiting") {
      meshTop(circuit.targetMesh, circuitStart);
      circuitEnd.copy(circuitNeuron);
    } else {
      circuitStart.copy(circuitNeuron);
      meshTop(circuit.targetMesh, circuitEnd);
    }

    circuitDirection.subVectors(circuitEnd, circuitStart).normalize();
    circuitSide.crossVectors(circuitDirection, camera.up).normalize();
    if (circuitSide.lengthSq() < 0.01) circuitSide.set(1, 0, 0);
    circuitLift.crossVectors(circuitDirection, circuitSide).normalize();
    const lightning = circuit.lightning;
    for (let i = 0; i <= lightning.segments; i++) {
      const u = i / lightning.segments;
      const envelope = Math.sin(Math.PI * u);
      const crackle =
        Math.sin(i * 8.37 + t * 31 + lightning.seed) * 0.68 +
        Math.sin(i * 3.11 - t * 47 + lightning.seed * 0.37) * 0.32;
      const fork = Math.sin(i * 5.19 + t * 23 + lightning.seed * 1.7);
      circuitPoint.lerpVectors(circuitStart, circuitEnd, u)
        .addScaledVector(circuitSide, crackle * envelope * 0.28)
        .addScaledVector(circuitLift, fork * envelope * 0.18);
      circuitPoint.toArray(lightning.positions, i * 3);
    }
    lightning.geometry.attributes.position.needsUpdate = true;

    for (let i = 0; i < lightning.sparkCount; i++) {
      const u = (i * 0.61803398875 + t * (0.34 + (i % 5) * 0.025)) % 1;
      const at = Math.min(
        lightning.segments,
        Math.floor(u * lightning.segments)
      );
      circuitPoint.fromArray(lightning.positions, at * 3);
      const flare = 0.08 + 0.28 * Math.abs(
        Math.sin(t * 17 + i * 2.7 + lightning.seed)
      );
      circuitPoint
        .addScaledVector(circuitSide, Math.sin(i * 4.1 + t * 29) * flare)
        .addScaledVector(circuitLift, Math.cos(i * 3.3 - t * 37) * flare);
      circuitPoint.toArray(lightning.sparkPositions, i * 3);
    }
    lightning.sparkGeometry.attributes.position.needsUpdate = true;
    circuitStart.toArray(lightning.jointPositions, 0);
    circuitEnd.toArray(lightning.jointPositions, 3);
    lightning.jointGeometry.attributes.position.needsUpdate = true;
    lightning.materials[0].opacity = 0.16 + Math.abs(Math.sin(t * 11)) * 0.2;
    lightning.materials[1].opacity = 0.76 + Math.abs(Math.sin(t * 19)) * 0.24;
    lightning.materials[2].opacity = 0.55 + Math.abs(Math.sin(t * 13)) * 0.4;
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

  function relicForNode(node, evidence) {
    const latest = evidence && evidence.length ? evidence[evidence.length - 1] : null;
    if (latest && EVIDENCE_RELIC[latest.kind]) return EVIDENCE_RELIC[latest.kind];
    if (node.status === "vetoed") return "story-mask";
    const text = (node.text || "").toLowerCase();
    if (/source map|source-map/.test(text)) return "source-mapped-claim";
    if (/story.*machinery|machinery.*story|two whys/.test(text)) return "two-whys-vessel";
    if (/thought.graph|inspectable object/.test(text)) return "thought-graph-reliquary";
    if (/shared.*mind|inhabit|medium/.test(text) && node.kind === "claim") {
      return "shared-mind-chamber";
    }
    if (/tacit|unspoken/.test(text) && node.kind === "premise") {
      return "tacit-knowledge-fossil";
    }
    return KIND_RELIC[node.kind] || "thought-graph-reliquary";
  }

  function mountRelic(group, key, { scale, ghost, placeholder, generation }) {
    const relic = RELIC_BY_KEY[key] || RELIC_BY_KEY["thought-graph-reliquary"];
    group.userData.relicKey = relic.key;
    RelicGLBLoader.load(relic.model)
      .then((object) => {
        if (!group.parent || generation !== layoutGeneration) return;
        const box = new THREE.Box3().setFromObject(object);
        const size = box.getSize(new THREE.Vector3());
        const center = box.getCenter(new THREE.Vector3());
        const fit = (2.25 * scale) / Math.max(size.y, size.x * 0.72, size.z * 0.72, 0.001);
        object.scale.setScalar(fit);
        object.position.set(-center.x * fit, 0.42 - box.min.y * fit, -center.z * fit);
        object.traverse((part) => {
          if (!part.material) return;
          if (ghost) {
            part.material.transparent = true;
            part.material.opacity *= 0.38;
            part.material.depthWrite = false;
          }
        });
        placeholder.visible = false;
        group.add(object);
      })
      .catch((error) => {
        placeholder.material.color.setHex(0x6b3540);
        placeholder.userData.loadError = String(error.message || error);
      });
  }

  function chamberMesh(node, { x, z, scale, ghost, relicKey, evidence }) {
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

    const placeholder = new THREE.Mesh(
      new THREE.OctahedronGeometry(0.48 * scale),
      new THREE.MeshStandardMaterial({
        color,
        emissive: color,
        emissiveIntensity: 0.12,
        metalness: 0.35,
        roughness: 0.55,
        transparent: true,
        opacity: ghost ? 0.24 : 0.5,
      })
    );
    placeholder.position.y = 1.35 * scale;
    g.add(placeholder);
    mountRelic(g, relicKey || relicForNode(node, evidence), {
      scale,
      ghost,
      placeholder,
      generation: layoutGeneration,
    });

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
    standingMesh = null;
    selectionSpot.intensity = 0;
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

  function sideSlot(i, n, side) {
    const row = Math.floor(i / 5);
    const rowCount = Math.min(5, n - row * 5);
    const col = i % 5;
    return {
      x: side * (CHOICE_ROW + row * CHOICE_ROW_GAP),
      z: (col - (rowCount - 1) / 2) * CHOICE_STRIDE,
    };
  }

  function arrivalSlot(i) {
    const row = Math.floor(i / 5);
    const offsets = [0, -1, 1, -2, 2];
    return {
      x: CHOICE_ROW + row * CHOICE_ROW_GAP,
      z: offsets[i % 5] * CHOICE_STRIDE,
    };
  }

  function arrivalKey(arrival) {
    return `${arrival.graphId}:${arrival.nodeId}:${arrival.anchorGraphId || ""}`;
  }

  function addClockChoice(mesh, choice) {
    mesh.userData.choice = choice;
    mesh.userData.focusScale = 1;
    choices.push({ mesh, choice });
  }

  function addArrivalPortal(arrival, i, rise = true) {
    const slot = arrivalSlot(i);
    const attribution = companionAttribution(arrival);
    const via = arrival.via || (arrival.seen
      ? "conversation return"
      : "new companion thought");
    const autoFocus = arrivingFocus &&
      arrival.graphId === arrivingFocus.graphId &&
      arrival.nodeId === arrivingFocus.nodeId &&
      arrival.anchorGraphId === arrivingFocus.anchorGraphId;
    const audioRole = arrival.returnOrigin
      ? "return"
      : (autoFocus || !arrival.seen) ? "new-path" : "companion";
    const ring = portalRing({
      x: slot.x,
      z: slot.z,
      color: arrival.returnOrigin
        ? RETURN_COLOR
        : arrival.seen ? 0x496e68 : 0x5c8a7b,
      emissive: arrival.returnOrigin
        ? RETURN_EMISSIVE
        : arrival.seen ? 0x102a28 : 0x183c38,
      portal: { graphId: arrival.graphId, nodeId: arrival.nodeId },
      relicKey: arrival.returnOrigin
        ? "counterfactual-shard-gate"
        : "thought-graph-reliquary",
      labelKind: arrival.labelKind || (arrival.seen
        ? "conversation return"
        : attribution
          ? `new companion thought · ${attribution}`
          : "new companion thought"),
      labelText: arrival.title,
      audioRole,
    });
    root.add(ring);
    portals.push(ring);
    if (autoFocus) completeContinuationCircuit(ring, arrival);
    const retainedArrival = rememberedCircuit &&
      rememberedCircuit.phase === "arrival" &&
      rememberedCircuit.targetGraphId === arrival.graphId &&
      rememberedCircuit.targetNodeId === arrival.nodeId;
    if (retainedArrival && arrival.seen) clearContinuationCircuit();
    else if (retainedArrival) restoreArrivalCircuit(ring, arrival);
    addClockChoice(ring, {
      via,
      kind: arrival.kind,
      text: `${companionTitle(arrival)} — ${arrival.text}`,
      description: arrival.description,
      selectionColor: arrival.returnOrigin
        ? RETURN_COLOR
        : autoFocus ? NEW_PATH_SELECTION_COLOR : null,
      autoFocus,
      audioRole,
      arrivalKey: arrivalKey(arrival),
      walk: () => inhabit(arrival.graphId, arrival.nodeId),
    });
    if (rise) markRise(ring, 0.24 + i * 0.08);
    return { autoFocus, choiceIndex: choices.length - 1 };
  }

  function layout(payload) {
    layoutGeneration += 1;
    elEvidenceDescent.hidden = true;
    clearRoot();
    root.add(floor());
    mappedRelicKey = relicForNode(payload.node, payload.evidence || []);
    if (
      payload.parent_graph_id &&
      payload.node.kind === "claim" &&
      !(payload.evidence || []).length &&
      mappedRelicKey === "narrated-claim"
    ) {
      mappedRelicKey = "forked-claim";
    }
    const here = chamberMesh(payload.node, {
      x: 0,
      z: 0,
      scale: 1,
      ghost: false,
      relicKey: manualRelicKey || mappedRelicKey,
      evidence: payload.evidence || [],
    });
    root.add(here);
    standingMesh = here;
    markRise(here, 0);

    const forward = payload.forward || payload.shaped || [];
    const rejected = payload.rejected_siblings || [];
    const vetoes = payload.vetoes || [];
    const forks = payload.fork_children || [];
    const traversal = (payload.read && payload.read.traversal) || {};
    const atOrigin = payload.origin && payload.origin.id === payload.node.id;
    const atThreshold = Boolean(traversal.terminal || atOrigin);
    const arrivals = atThreshold ? visibleArrivals(payload) : [];
    const storyNodes = forward.map((node) => ({
      node,
      ghost: false,
      via: "story ahead",
    }));
    const sideNodes = [
      ...rejected.map((n) => ({ node: n, ghost: true, via: "not taken" })),
      ...vetoes.map((n) => ({ node: n, ghost: true, via: "human no" })),
    ];
    const pathCount = storyNodes.length + forks.length;

    storyNodes.forEach((item, i) => {
      const slot = choiceSlot(i, pathCount);
      const mesh = chamberMesh(item.node, {
        x: slot.x,
        z: slot.z,
        scale: 0.7,
        ghost: item.ghost,
        evidence: [],
      });
      root.add(mesh);
      targets.push(mesh);
      addClockChoice(mesh, {
        via: item.via,
        kind: item.node.kind,
        text: item.node.text,
        audioRole: "story",
        walk: () => inhabit(payload.graph_id, item.node.id),
      });
      markRise(mesh, 0.08 + i * 0.07);
    });

    sideNodes.forEach((item, i) => {
      const slot = sideSlot(i, sideNodes.length, -1);
      const mesh = chamberMesh(item.node, {
        x: slot.x,
        z: slot.z,
        scale: 0.7,
        ghost: item.ghost,
        evidence: [],
      });
      root.add(mesh);
      targets.push(mesh);
      addClockChoice(mesh, {
        via: item.via,
        kind: item.node.kind,
        text: item.node.text,
        audioRole: "rejected",
        walk: () => inhabit(payload.graph_id, item.node.id),
      });
      markRise(mesh, 0.12 + i * 0.07);
    });

    forks.forEach((f, i) => {
      const slot = choiceSlot(storyNodes.length + i, pathCount);
      const ring = portalRing({
        x: slot.x,
        z: slot.z,
        color: 0xb08d57,
        emissive: 0x5a3c18,
        portal: { graphId: f.id, nodeId: f.spawn_node_id },
        relicKey: "fork-compass",
        labelKind: "story fork",
        labelText: f.reason || "continuation without this chamber",
        audioRole: "fork",
      });
      root.add(ring);
      portals.push(ring);
      addClockChoice(ring, {
        via: "continuation",
        kind: "fork",
        text: f.reason || "a path that omitted this chamber",
        audioRole: "fork",
        walk: () => inhabit(f.id, f.spawn_node_id),
      });
      markRise(ring, 0.18 + i * 0.08);
    });

    arrivals.forEach((arrival, i) => addArrivalPortal(arrival, i));

    const parent = payload.parent;
    if (parent && parent.graph_id && parent.node_id) {
      const back = portalRing({
        x: 0,
        z: CHOICE_ROW,
        color: 0x8a7396,
        emissive: 0x3a2040,
        portal: { graphId: parent.graph_id, nodeId: parent.node_id },
        relicKey: "counterfactual-shard-gate",
        labelKind: "fork return",
        labelText: "back to the chamber where this path was cut",
        audioRole: "back",
      });
      root.add(back);
      portals.push(back);
      addClockChoice(back, {
        via: "fork return",
        kind: "fork",
        text: "back to the chamber where this path was cut",
        audioRole: "back",
        walk: () => inhabit(parent.graph_id, parent.node_id),
      });
      markRise(back, 0.28);
    }

    const autoFocusIndex = choices.findIndex((item) => item.choice.autoFocus);
    if (autoFocusIndex >= 0) {
      focusIndex = autoFocusIndex;
      arrivingFocus = null;
      showFocus();
    } else {
      plate(payload);
    }
    renderThreshold(payload);
  }

  function portalRing({
    x,
    z,
    color,
    emissive,
    portal,
    relicKey,
    labelKind = "doorway",
    labelText = "another thought",
    audioRole = "story",
  }) {
    const group = new THREE.Group();
    group.position.set(x, 0, z);
    group.userData = { portal, ghost: false, audioRole };
    const geo = new THREE.TorusGeometry(0.7, 0.07, 10, 32);
    const mat = new THREE.MeshStandardMaterial({
      color,
      emissive,
      emissiveIntensity: 0.4,
      metalness: 0.7,
      roughness: 0.3,
    });
    const ring = new THREE.Mesh(geo, mat);
    ring.position.set(0, 0.9, 0);
    ring.rotation.x = Math.PI / 2;
    ring.userData = { portal };
    group.add(ring);
    const placeholder = new THREE.Mesh(
      new THREE.OctahedronGeometry(0.24),
      new THREE.MeshStandardMaterial({ color, metalness: 0.5, roughness: 0.35 })
    );
    placeholder.position.y = 1.1;
    group.add(placeholder);
    const board = new THREE.Mesh(
      new THREE.PlaneGeometry(2.5, 0.9),
      new THREE.MeshBasicMaterial({
        map: labelTexture(labelKind, labelText),
        transparent: true,
      })
    );
    board.position.set(0, 2.3, 0.7);
    group.add(board);
    mountRelic(group, relicKey, {
      scale: 0.48,
      ghost: false,
      placeholder,
      generation: layoutGeneration,
    });
    const hit = new THREE.Mesh(
      new THREE.TorusGeometry(0.7, 0.22, 8, 24),
      new THREE.MeshBasicMaterial({ visible: false })
    );
    hit.rotation.x = Math.PI / 2;
    hit.userData = { portal, audioRole };
    group.add(hit);
    return group;
  }

  function plate(payload) {
    const n = payload.node;
    const read = payload.read || {};
    const traversal = read.traversal || {};
    const attribution = graphAttribution(payload);
    elBanner.textContent = attribution
      ? `${attribution} · story graph · not a circuit trace`
      : "story graph · not a circuit trace";
    elKind.textContent = read.kind_line || `${n.kind} · ${n.status}`;
    elText.textContent = n.text;
    const hereBits = [
      attribution ? `inside the ${attribution} graph` : null,
      payload.continuation_source
        ? payload.continuation_source.prompt
          ? `continued from question: ${payload.continuation_source.prompt}`
          : "continued from a source chamber without a new question"
        : null,
      read.here_line,
      traversal.terminal ? traversal.state_line : null,
      read.climate_line,
      read.evidence_line,
    ].filter(Boolean);
    elHere.textContent = hereBits.join(" · ");
    const bits = [];
    if (focusIndex >= 0 && choices[focusIndex]) {
      const c = choices[focusIndex].choice;
      const kind = (c.kind || "").replace(/_/g, " ");
      elHere.textContent = c.description || (
        c.via === "new companion thought" || c.via === "conversation return"
          ? `${c.via} · ${kind} — ${c.text}`
          : `path ${focusIndex + 1}/${choices.length} · ${c.via} · ${kind} — ${c.text}`
      );
      bits.push("spotlit preview · enter inhabits and makes this the key light · esc clears");
    } else {
      if (traversal.look_line || read.look_line) {
        bits.push(traversal.look_line || read.look_line);
      }
      if (read.evidence_action_line) bits.push(read.evidence_action_line);
      const shownRelic = RELIC_BY_KEY[manualRelicKey || mappedRelicKey];
      if (shownRelic) {
        bits.push(
          manualRelicKey
            ? `relic preview: ${shownRelic.name} · esc restores mapped form`
            : `form: ${shownRelic.name} · r opens relic index`
        );
      }
      const storyCount =
        (payload.forward || payload.shaped || []).length +
        (payload.fork_children || []).length;
      const sideCount =
        (payload.rejected_siblings || []).length +
        (payload.vetoes || []).length;
      if (storyCount) bits.push(`${storyCount} direct story ${storyCount === 1 ? "path" : "paths"} ahead`);
      if (sideCount) bits.push(`${sideCount} ${sideCount === 1 ? "road" : "roads"} not taken to the left`);
      if ((payload.fork_children || []).length) bits.push("bronze ring: continuation");
      if (payload.parent && payload.parent.graph_id) bits.push("violet ring: back to the cut");
      const nearbyArrivals = visibleArrivals(payload);
      const atOrigin = payload.origin && payload.origin.id === payload.node.id;
      const atThreshold = Boolean(traversal.terminal || atOrigin);
      const newArrivals = nearbyArrivals.filter((arrival) => !arrival.seen);
      if (atThreshold && newArrivals.length) {
        bits.push(
          `${newArrivals.length} new companion ${newArrivals.length === 1 ? "door" : "doors"} to the right`
        );
      } else if (atThreshold && nearbyArrivals.length) {
        bits.push(
          `${nearbyArrivals.length} conversation return ${nearbyArrivals.length === 1 ? "door" : "doors"} to the right`
        );
      } else if (nearbyArrivals.length) {
        bits.push("conversation doors wait at the graph origin or a path ending");
      }
      if (trail.length) bits.push("b retraces your walk");
    }
    if (overhead) bits.push("drag to pan · c behind · shift+c home");
    elMeta.textContent = bits.join("  ·  ");
    requestAnimationFrame(resize);
    applyClimate(payload.climate);
  }

  function renderThreshold(payload) {
    const traversal = (payload.read && payload.read.traversal) || {};
    if (!traversal.terminal) {
      elThreshold.hidden = true;
      sound.setWorking(false);
      requestAnimationFrame(resize);
      return;
    }
    const ready = payload.continuation || null;
    if (ready) beginContinuationCircuit(ready);
    sound.setWorking(Boolean(ready));
    const attempt = payload.continuation_attempt || null;
    const harness = attempt && attempt.harness
      ? attempt.harness.charAt(0).toUpperCase() + attempt.harness.slice(1)
      : null;
    const workingLabel = "AI working…";
    elThreshold.hidden = false;
    elThreshold.dataset.ready = ready ? "working" : "false";
    elThresholdKind.textContent = ready
      ? `${workingLabel}${harness ? ` · ${harness}` : ""}`
      : "end of this graph path";
    elThresholdText.textContent = ready
      ? harness
        ? `${harness} is responding from this chamber. The new path will arrive automatically.`
        : "The continuation is queued. This chamber will update when a harness begins responding."
      : traversal.state_line;
    elThresholdOrigin.disabled = Boolean(
      payload.origin && payload.origin.id === payload.node.id
    );
    elThresholdContinue.disabled = false;
    elThresholdAsk.disabled = Boolean(ready);
    elThresholdContinue.textContent = ready
      ? "cancel response · q"
      : "ready for continuation · q";
    requestAnimationFrame(resize);
  }

  function sameStand(a, b) {
    return a && b && a.graphId === b.graphId && a.nodeId === b.nodeId;
  }

  async function inhabit(graphId, nodeId, origin = "walk") {
    const q = new URLSearchParams();
    if (graphId) q.set("graph", graphId);
    const payload = await api(`/api/inhabit/${nodeId}?${q.toString()}`);
    const next = { graphId: payload.graph_id, nodeId: payload.node.id };
    if (
      continuationCircuit &&
      continuationCircuit.phase === "arrival" &&
      continuationCircuit.targetGraphId === next.graphId &&
      continuationCircuit.targetNodeId === next.nodeId
    ) clearContinuationCircuit();
    const prev = view
      ? { graphId: view.graph_id, nodeId: view.node.id }
      : null;
    const enteredCompanion = view && visibleArrivals(view).some(
      (arrival) =>
        arrival.graphId === next.graphId && arrival.nodeId === next.nodeId
    );
    if (enteredCompanion) {
      liveArrivals = liveArrivals.map((arrival) =>
        arrival.graphId === next.graphId &&
        arrival.nodeId === next.nodeId &&
        arrival.anchorGraphId === view.graph_id
          ? { ...arrival, seen: true }
          : arrival
      );
      saveCompanionThoughts();
      if (origin === "walk" && view && prev) {
        rememberCompanion({
          sessionId: view.session_id,
          graphId: prev.graphId,
          nodeId: prev.nodeId,
          kind: view.node.kind,
          text: view.node.text,
          title: sessionTitles.get(view.session_id) || "earlier thought",
          seen: true,
          anchorGraphId: next.graphId,
        });
      }
    }
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
      const boot = await api("/api/sessions");
      for (const session of boot.sessions || []) {
        knownHeads.set(session.id, session.head_graph_id || null);
        sessionTitles.set(session.id, session.title || "untitled thought");
      }
      companionReady = true;
      const fromHash = parseHash();
      if (fromHash) {
        await inhabit(fromHash.graphId, fromHash.nodeId, "boot");
        const currentSession = (boot.sessions || []).find(
          (session) => view && session.id === view.session_id
        );
        if (
          currentSession &&
          currentSession.head_graph_id &&
          currentSession.head_graph_id !== view.graph_id
        ) {
          const arrival = companionFromSession(
            currentSession, false, view.graph_id
          );
          if (arrival) {
            rememberCompanion(arrival);
            layout(view);
          }
        }
        return;
      }
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

  function showWaitingArrivals() {
    if (
      !arrivalsDirty ||
      !view ||
      composing ||
      !elRelicIndex.hidden ||
      !elEvidenceDescent.hidden
    ) return;
    arrivalsDirty = false;
    revealWaitingArrivals().catch(() => {
      arrivalsDirty = true;
    });
  }

  async function revealWaitingArrivals() {
    if (!view) return;
    const graphId = view.graph_id;
    const nodeId = view.node.id;
    const q = new URLSearchParams({ graph: graphId });
    const payload = await api(`/api/inhabit/${nodeId}?${q.toString()}`);
    if (!view || view.graph_id !== graphId || view.node.id !== nodeId) return;
    view = payload;
    const traversal = (payload.read && payload.read.traversal) || {};
    const atOrigin = payload.origin && payload.origin.id === payload.node.id;
    const arrivals = traversal.terminal || atOrigin
      ? visibleArrivals(payload)
      : [];
    const existing = new Set(
      choices.map((item) => item.choice.arrivalKey).filter(Boolean)
    );
    let newFocus = -1;
    arrivals.forEach((arrival, i) => {
      if (existing.has(arrivalKey(arrival))) return;
      const added = addArrivalPortal(arrival, i);
      if (added.autoFocus) newFocus = added.choiceIndex;
    });
    if (newFocus >= 0) {
      focusIndex = newFocus;
      arrivingFocus = null;
      showFocus();
    } else {
      plate(payload);
    }
    renderThreshold(payload);
  }

  async function refreshContinuationState() {
    if (!view || !view.continuation) return;
    const graphId = view.graph_id;
    const nodeId = view.node.id;
    const q = new URLSearchParams({ graph: graphId });
    const payload = await api(`/api/inhabit/${nodeId}?${q.toString()}`);
    if (!view || view.graph_id !== graphId || view.node.id !== nodeId) return;
    view = payload;
    renderThreshold(payload);
  }

  async function pollLiveCompanion() {
    if (!companionReady || companionPolling) return;
    companionPolling = true;
    try {
      const state = await api("/api/sessions");
      let added = false;
      for (const session of state.sessions || []) {
        const head = session.head_graph_id || null;
        const changed = !knownHeads.has(session.id) || knownHeads.get(session.id) !== head;
        knownHeads.set(session.id, head);
        sessionTitles.set(session.id, session.title || "untitled thought");
        if (!head || !session.spawn) continue;
        if (view && head === view.graph_id) continue;
        if (
          view &&
          (view.fork_children || []).some((child) => child.id === head)
        ) continue;
        const arrival = companionFromSession(
          session, false, view && view.graph_id
        );
        if (!arrival) continue;
        const existing = liveArrivals.find(
          (item) =>
            item.graphId === head &&
            item.nodeId === arrival.nodeId &&
            item.anchorGraphId === arrival.anchorGraphId
        );
        if (existing) {
          if (
            (!existing.harness && arrival.harness) ||
            (!existing.modelName && arrival.modelName)
          ) {
            rememberCompanion(arrival);
            added = true;
          }
          continue;
        }
        if (!changed) continue;
        rememberCompanion(arrival);
        arrivingFocus = {
          graphId: arrival.graphId,
          nodeId: arrival.nodeId,
          anchorGraphId: arrival.anchorGraphId,
        };
        added = true;
      }
      if (added) {
        arrivalsDirty = true;
      }
      if (!added && view && view.continuation) {
        await refreshContinuationState();
      }
    } catch (_error) {
      // The chamber remains usable if its local companion poll misses a beat.
    } finally {
      companionPolling = false;
      showWaitingArrivals();
    }
  }

  canvas.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    dragging = true;
    canvas.dataset.dragging = "true";
    dragMoved = false;
    lastX = e.clientX;
    lastY = e.clientY;
  });
  function stopDragging() {
    dragging = false;
    delete canvas.dataset.dragging;
  }
  window.addEventListener("pointerup", stopDragging);
  window.addEventListener("pointercancel", stopDragging);
  window.addEventListener("blur", stopDragging);
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
      sound.traverse(
        portalHit.audioRole === "back" ? "back" : "forward",
        portalHit.audioRole || "story"
      );
      inhabit(portalHit.portal.graphId, portalHit.portal.nodeId);
      return;
    }
    const nodeHit = pickUserData(
      raycaster.intersectObjects(targets, true),
      (d) => d.id
    );
    if (nodeHit && view) {
      sound.traverse("forward", "story");
      inhabit(view.graph_id, nodeHit.id);
    }
  });

  function openComposer(kind) {
    if (!view || busy) return;
    composing = kind;
    sound.surface(kind);
    if (kind === "continuation") {
      elThreshold.dataset.ask = "true";
      elThresholdAsk.setAttribute("aria-pressed", "true");
      elThresholdAskBox.hidden = false;
      elThresholdAskInput.value = "";
      elThresholdAskInput.focus();
      requestAnimationFrame(resize);
      return;
    }
    elComposer.hidden = false;
    const read = (view && view.read) || {};
    elComposerLabel.textContent = kind === "fork"
      ? read.fork_line || "fork · accept the chain except this cut"
      : read.veto_line || "veto · this stays, with a human no";
    elComposerInput.value = "";
    elComposerInput.placeholder = kind === "fork"
      ? "why this cut (optional)"
      : "why this is the wrong cut";
    elComposerInput.focus();
    requestAnimationFrame(resize);
  }

  function closeComposer() {
    composing = null;
    elComposer.hidden = true;
    elComposerInput.blur();
    elThreshold.dataset.ask = "false";
    elThresholdAsk.setAttribute("aria-pressed", "false");
    elThresholdAskBox.hidden = true;
    elThresholdAskInput.blur();
    requestAnimationFrame(resize);
    showWaitingArrivals();
  }

  function toggleContinuationComposer() {
    if (busy || (composing && composing !== "continuation")) return;
    if (composing === "continuation") closeComposer();
    else openComposer("continuation");
  }

  async function commitGesture() {
    if (!composing || !view || busy) return;
    const kind = composing;
    const input = kind === "continuation" ? elThresholdAskInput : elComposerInput;
    const text = input.value.trim();
    if (kind === "veto" && !text) {
      elComposerLabel.textContent = "veto · a reason is required";
      return;
    }
    if (kind === "continuation") {
      closeComposer();
      await markContinuationReady(text);
      return;
    }
    busy = true;
    try {
      const endpoint = kind === "fork"
        ? "/api/fork"
        : "/api/veto";
      const result = await post(endpoint, {
        node: view.node.id,
        graph: view.graph_id,
        session: view.session_id,
        reason: text || undefined,
      });
      closeComposer();
      const stand = result.stand;
      sound.edit(kind);
      await inhabit(stand.graph_id, stand.node_id);
    } catch (err) {
      elComposerLabel.textContent = String(err.message || err);
    } finally {
      busy = false;
    }
  }

  async function markContinuationReady(prompt = "") {
    if (!view || view.continuation || busy) return;
    busy = true;
    elThreshold.dataset.ready = "pending";
    elThresholdKind.textContent = "marking inhabitant ready…";
    elThresholdText.textContent = "Writing the append-only handoff for an AI harness.";
    elThresholdContinue.disabled = true;
    elThresholdAsk.disabled = true;
    elThresholdContinue.textContent = "marking ready…";
    try {
      const result = await post("/api/continuation", {
        node: view.node.id,
        graph: view.graph_id,
        session: view.session_id,
        prompt: prompt || undefined,
      });
      view.continuation = result.request;
      plate(view);
      renderThreshold(view);
    } catch (err) {
      elThreshold.dataset.ready = "false";
      elThresholdKind.textContent = "continuation was not marked";
      elThresholdText.textContent = String(err.message || err);
      elThresholdContinue.disabled = false;
      elThresholdAsk.disabled = false;
      elThresholdContinue.textContent = "try ready for continuation again · q";
    } finally {
      busy = false;
    }
  }

  async function cancelContinuationReady() {
    if (!view || !view.continuation || busy) return;
    const request = view.continuation;
    busy = true;
    elThreshold.dataset.ready = "pending";
    elThresholdKind.textContent = "canceling continuation…";
    elThresholdText.textContent = "Writing an append-only cancellation receipt.";
    elThresholdContinue.disabled = true;
    elThresholdAsk.disabled = true;
    elThresholdContinue.textContent = "canceling…";
    try {
      await post("/api/continuation/cancel", { request: request.id });
      clearContinuationCircuit();
      sound.setWorking(false);
      sound.cancel();
      view.continuation = null;
      plate(view);
      renderThreshold(view);
      elThreshold.dataset.ready = "canceled";
      elThresholdKind.textContent = "continuation canceled";
      elThresholdText.textContent =
        "The request was withdrawn. You can mark ready again or ask from here.";
    } catch (err) {
      renderThreshold(view);
      elThresholdKind.textContent = "continuation could not be canceled";
      elThresholdText.textContent = String(err.message || err);
    } finally {
      busy = false;
    }
  }

  function toggleContinuationReady() {
    if (!view || busy) return;
    if (view.continuation) cancelContinuationReady();
    else markContinuationReady();
  }

  function walkBack() {
    if (trail.length) {
      const prev = trail.pop();
      sound.traverse("back", "story");
      inhabit(prev.graphId, prev.nodeId, "back");
      return;
    }
    if (view && view.parent && view.parent.graph_id && view.parent.node_id) {
      sound.traverse("back", "back");
      inhabit(view.parent.graph_id, view.parent.node_id, "back");
    }
  }

  function walkDeeper() {
    if (!view) return;
    const forward = view.forward || view.shaped || [];
    if (forward.length) {
      sound.traverse("forward", "story");
      inhabit(view.graph_id, forward[0].id);
      return;
    }
    const forks = view.fork_children || [];
    const first = forks.find((f) => f.id && f.spawn_node_id);
    if (first) {
      sound.traverse("forward", "fork");
      inhabit(first.id, first.spawn_node_id);
    }
  }

  function walkOrigin() {
    if (!view || !view.origin || view.origin.id === view.node.id) return;
    if (composing) closeComposer();
    sound.traverse("back", "return");
    inhabit(view.graph_id, view.origin.id);
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
    if (focusIndex < 0) selectionSpot.intensity = 0;
    if (view) plate(view);
  }

  function clockwiseChoices() {
    scene.updateMatrixWorld(true);
    return choices.map((choice, index) => {
      const position = new THREE.Vector3();
      choice.mesh.getWorldPosition(position);
      const angle = (Math.atan2(position.x, -position.z) + Math.PI * 2)
        % (Math.PI * 2);
      return { index, angle, radius: Math.hypot(position.x, position.z) };
    }).sort((a, b) => a.angle - b.angle || a.radius - b.radius || a.index - b.index);
  }

  function cycleChoice(dir) {
    if (!choices.length) return;
    const clock = clockwiseChoices();
    if (focusIndex < 0) {
      focusIndex = dir > 0 ? clock[0].index : clock[clock.length - 1].index;
    } else {
      const at = clock.findIndex((choice) => choice.index === focusIndex);
      const next = (at + dir + clock.length) % clock.length;
      focusIndex = clock[next].index;
    }
    showFocus();
    sound.cycle(choices[focusIndex].choice.audioRole || "story", dir);
  }

  function selectFocus() {
    if (focusIndex < 0) {
      walkDeeper();
      return;
    }
    if (!choices[focusIndex]) return;
    const role = choices[focusIndex].choice.audioRole || "story";
    sound.traverse(role === "back" ? "back" : "forward", role);
    choices[focusIndex].choice.walk();
  }

  function clearFocus() {
    if (focusIndex < 0) return;
    focusIndex = -1;
    showFocus();
    showWaitingArrivals();
  }

  function renderRelicIndex() {
    elRelicGrid.replaceChildren();
    for (const relic of RELICS) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "relic-card";
      if (relic.key === (manualRelicKey || mappedRelicKey)) button.classList.add("mapped");
      const preview = document.createElement("img");
      preview.src = relic.preview;
      preview.alt = "";
      preview.loading = "lazy";
      const copy = document.createElement("span");
      copy.className = "relic-card-copy";
      const name = document.createElement("strong");
      name.textContent = relic.name;
      const role = document.createElement("small");
      role.textContent = relic.role;
      copy.append(name, role);
      button.append(preview, copy);
      button.addEventListener("click", () => {
        manualRelicKey = relic.key;
        elRelicIndex.hidden = true;
        if (view) layout(view);
      });
      elRelicGrid.append(button);
    }
  }

  function openRelicIndex() {
    if (!view || composing) return;
    sound.surface("relic");
    renderRelicIndex();
    elRelicIndex.hidden = false;
    const selected = elRelicGrid.querySelector(".mapped") || elRelicGrid.firstElementChild;
    if (selected) selected.focus();
  }

  function closeRelicIndex() {
    elRelicIndex.hidden = true;
    if (document.activeElement && document.activeElement.blur) {
      document.activeElement.blur();
    }
    showWaitingArrivals();
  }

  elRelicClose.addEventListener("click", closeRelicIndex);

  function renderEvidenceDescent() {
    const read = (view && view.read) || {};
    const story = read.story_path || {};
    const layers = read.evidence_layers || [];
    elStoryIntro.textContent = Object.prototype.hasOwnProperty.call(read, "story_path")
      ? story.intro_line || story.empty_line || ""
      : "path relations are unavailable from the running server · restart ta serve, then refresh";
    elStoryGroups.replaceChildren();
    for (const group of story.groups || []) {
      const section = document.createElement("section");
      section.className = "story-group";
      const heading = document.createElement("div");
      heading.className = "story-heading";
      heading.textContent = group.heading_line;
      const description = document.createElement("p");
      description.className = "story-description";
      description.textContent = group.description_line;
      const items = document.createElement("div");
      items.className = "story-items";
      for (const entry of group.items || []) {
        const item = document.createElement("article");
        item.className = "story-item";
        const kind = document.createElement("div");
        kind.className = "story-kind";
        kind.textContent = entry.kind_line;
        const text = document.createElement("p");
        text.textContent = entry.text;
        item.append(kind, text);
        items.append(item);
      }
      section.append(heading, description, items);
      elStoryGroups.append(section);
    }
    elEvidenceIntro.textContent = read.evidence_line || read.evidence_empty_line || "";
    elEvidenceStrata.replaceChildren();
    for (const layer of layers) {
      const stratum = document.createElement("article");
      stratum.className = "evidence-stratum";

      const position = document.createElement("div");
      position.className = "evidence-position";
      position.textContent = layer.position_line;
      const heading = document.createElement("div");
      heading.className = "evidence-heading";
      heading.textContent = layer.heading_line;
      const summary = document.createElement("p");
      summary.className = "evidence-summary";
      summary.textContent = layer.summary;
      stratum.append(position, heading, summary);

      if (layer.origin_line) {
        const origin = document.createElement("div");
        origin.className = "evidence-origin";
        origin.textContent = layer.origin_line;
        stratum.append(origin);
      }
      if (layer.follows_line) {
        const follows = document.createElement("div");
        follows.className = "evidence-follows";
        follows.textContent = layer.follows_line;
        stratum.append(follows);
      }
      if ((layer.artifact_lines || []).length) {
        const artifacts = document.createElement("ul");
        artifacts.className = "evidence-artifacts";
        for (const line of layer.artifact_lines) {
          const item = document.createElement("li");
          item.textContent = line;
          artifacts.append(item);
        }
        stratum.append(artifacts);
      }
      elEvidenceStrata.append(stratum);
    }
  }

  function openEvidenceDescent() {
    if (!view || composing) return;
    sound.surface("evidence");
    renderEvidenceDescent();
    elEvidenceDescent.hidden = false;
    elEvidenceClose.focus();
  }

  function closeEvidenceDescent() {
    sound.surface("evidence", false);
    elEvidenceDescent.hidden = true;
    if (document.activeElement && document.activeElement.blur) {
      document.activeElement.blur();
    }
    showWaitingArrivals();
  }

  elEvidenceClose.addEventListener("click", closeEvidenceDescent);
  elThresholdOrigin.addEventListener("click", walkOrigin);
  elThresholdContinue.addEventListener("click", toggleContinuationReady);
  elThresholdAsk.addEventListener("click", toggleContinuationComposer);

  window.addEventListener("keydown", (e) => {
    if (elSoundControls.contains(e.target)) return;
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
    if (!elEvidenceDescent.hidden) {
      if (e.key === "Escape" || e.key === "e" || e.key === "E") {
        e.preventDefault();
        closeEvidenceDescent();
      }
      return;
    }
    if (!elRelicIndex.hidden) {
      if (e.key === "Escape" || e.key === "r" || e.key === "R") {
        e.preventDefault();
        closeRelicIndex();
      }
      return;
    }
    if (e.key === "e" || e.key === "E") {
      e.preventDefault();
      openEvidenceDescent();
      return;
    }
    if (e.key === "r" || e.key === "R") {
      e.preventDefault();
      openRelicIndex();
      return;
    }
    if (e.key === "Escape") {
      e.preventDefault();
      if (manualRelicKey) {
        manualRelicKey = null;
        if (view) layout(view);
        return;
      }
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
      sound.cameraShift(overhead);
      if (view) plate(view);
    }
    if (e.key === "s" || e.key === "S") {
      e.preventDefault();
      sound.toggleMuted();
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
    if (e.key === "o" || e.key === "O") {
      e.preventDefault();
      walkOrigin();
    }
    if (e.key === "q" || e.key === "Q") {
      const traversal = view && view.read && view.read.traversal;
      if (traversal && traversal.terminal) {
        e.preventDefault();
        toggleContinuationReady();
      }
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

  const lightAim = new THREE.Vector3();

  function aimSpot(light, target, mesh, x, y, z) {
    mesh.getWorldPosition(lightAim);
    target.position.copy(lightAim);
    target.position.y += 1.15;
    light.position.set(lightAim.x + x, lightAim.y + y, lightAim.z + z);
  }

  function updateNavigationLights(t) {
    // Three r160 uses physical light units. At this chamber's 6–9 unit throw,
    // single-digit candela values disappear after inverse-distance falloff.
    if (standingMesh) {
      aimSpot(key, keyTarget, standingMesh, 3, overhead ? 7 : 5.8, 3.5);
      key.intensity = overhead
        ? 1250
        : 950 + Math.sin(t * 1.3) * 35;
    } else key.intensity = 0;

    const focused = focusIndex >= 0 && choices[focusIndex]
      ? choices[focusIndex].mesh
      : null;
    if (focused) {
      aimSpot(selectionSpot, selectionTarget, focused, -2.5, overhead ? 7.5 : 5.2, 2.8);
      const choice = choices[focusIndex].choice;
      selectionSpot.color.setHex(
        choice.selectionColor || DEFAULT_SELECTION_COLOR
      );
      selectionSpot.intensity = overhead ? 1500 : 1200;
    } else selectionSpot.intensity = 0;
  }

  function tick() {
    const t = clock.getElapsedTime();
    if (overhead) {
      camera.up.set(0, 0, -1);
      camera.position.set(overheadLook.x, 26, overheadLook.z);
      camera.lookAt(overheadLook.x, 0, overheadLook.z);
      overSun.intensity = 1.15;
      overHemi.intensity = 0.5;
      fill.intensity = 0.2;
      neuralFill.intensity = 0.55;
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
      fill.intensity = 0.7;
      neuralFill.intensity = 0.22;
      scene.fog.density = climateFog;
    }
    updateNeuralSky(t);
    updateContinuationCircuit(t);
    tickRise(t);
    updateNavigationLights(t);
    renderer.render(scene, camera);
    requestAnimationFrame(tick);
  }

  const skyMap = ambientTexture();
  const environmentMap = skyMap.clone();
  environmentMap.mapping = THREE.EquirectangularReflectionMapping;
  environmentMap.needsUpdate = true;
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromEquirectangular(environmentMap).texture;
  pmrem.dispose();
  neuralSky = makeNeuralSky(skyMap);
  scene.add(neuralSky.group);
  boot();
  window.setInterval(pollLiveCompanion, 2500);
  tick();
})();
