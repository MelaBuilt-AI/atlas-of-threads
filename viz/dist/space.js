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
    ["field-notes-monument", "Field Notes Monument", "human inscription · what mattered across exact paths"],
    ["knowledge-ark-launcher", "Knowledge Ark Launcher", "outbound knowledge · one frozen milestone ready to launch"],
    ["knowledge-ark-launcher-post-launch", "Knowledge Ark Launcher — Post Launch", "outbound knowledge · a carried milestone"],
    ["charged-knowledge-capsule", "Charged Knowledge Capsule", "portable context · a private human-reviewed dossier"],
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
  const elKind = document.getElementById("kind");
  const elText = document.getElementById("text");
  const elHere = document.getElementById("here");
  const elMeta = document.getElementById("meta");
  const elPlate = document.getElementById("plate");
  const elEmpty = document.getElementById("empty");
  const elLegendTrigger = document.getElementById("legend-trigger");
  const elLegendScrim = document.getElementById("legend-scrim");
  const elLegendMenu = document.getElementById("legend-menu");
  const elLegendClose = document.getElementById("legend-close");
  const elWorkspaceScrim = document.getElementById("workspace-scrim");
  const elWorkspaceMenu = document.getElementById("workspace-menu");
  const elWorkspaceClose = document.getElementById("workspace-close");
  const elWorkspaceHarnessStatus = document.getElementById("workspace-harness-status");
  const elWorkspaceHarnesses = document.getElementById("workspace-harnesses");
  const elWorkspaceParallelSection = document.getElementById("workspace-parallel-section");
  const elWorkspaceParallelForm = document.getElementById("workspace-parallel-form");
  const elWorkspaceParallelHarnesses = document.getElementById("workspace-parallel-harnesses");
  const elWorkspaceParallelPrompt = document.getElementById("workspace-parallel-prompt");
  const elWorkspaceParallelSubmit = document.getElementById("workspace-parallel-submit");
  const elWorkspaceParallelProgress = document.getElementById("workspace-parallel-progress");
  const elWorkspaceParallelCancel = document.getElementById("workspace-parallel-cancel");
  const elWorkspaceNewToggle = document.getElementById("workspace-new-toggle");
  const elWorkspaceNewForm = document.getElementById("workspace-new-form");
  const elWorkspaceNewPrompt = document.getElementById("workspace-new-prompt");
  const elWorkspaceActionStatus = document.getElementById("workspace-action-status");
  const elWorkspaceHistory = document.getElementById("workspace-history");
  const elThreadCompass = document.getElementById("thread-compass");
  const elThreadPanel = elThreadCompass.querySelector(".thread-panel");
  const elThreadClose = document.getElementById("thread-close");
  const elThreadTitle = document.getElementById("thread-title");
  const elThreadSubtitle = document.getElementById("thread-subtitle");
  const elThreadLatest = document.getElementById("thread-latest");
  const elThreadStatus = document.getElementById("thread-status");
  const elThreadList = document.getElementById("thread-list");
  const elComposer = document.getElementById("composer");
  const elComposerLabel = document.getElementById("composer-label");
  const elComposerInput = document.getElementById("composer-input");
  const elThreshold = document.getElementById("threshold");
  const elThresholdKind = document.getElementById("threshold-kind");
  const elThresholdText = document.getElementById("threshold-text");
  const elThresholdOrigin = document.getElementById("threshold-origin");
  const elThresholdContinue = document.getElementById("threshold-continue");
  const elThresholdAsk = document.getElementById("threshold-ask");
  const elThresholdParallel = document.getElementById("threshold-parallel");
  const elThresholdAskBox = document.getElementById("threshold-ask-box");
  const elThresholdAskInput = document.getElementById("threshold-ask-input");
  const elFieldNoteEligible = document.getElementById("field-note-eligible");
  const elKnowledgeCapsuleEligible = document.getElementById("knowledge-capsule-eligible");
  const elRelicIndex = document.getElementById("relic-index");
  const elRelicGrid = document.getElementById("relic-grid");
  const elRelicClose = document.getElementById("relic-close");
  const elEvidenceDescent = document.getElementById("evidence-descent");
  const elEvidenceSurfaceKind = document.getElementById("evidence-surface-kind");
  const elEvidenceSurfaceSummary = document.getElementById("evidence-surface-summary");
  const elStoryPath = document.getElementById("story-path");
  const elStorySectionLabel = document.getElementById("story-section-label");
  const elStoryIntro = document.getElementById("story-intro");
  const elStoryGroups = document.getElementById("story-groups");
  const elEvidenceIntro = document.getElementById("evidence-intro");
  const elEvidenceSectionLabel = document.getElementById("evidence-section-label");
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
  let fieldNoteTargets = [];
  let capsuleTargets = [];
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
  let activeFieldNote = null;
  let activeCapsule = null;
  let fieldNoteConstruction = null;
  let capsuleConstruction = null;
  let capsuleFlight = null;
  let eligibilityKey = null;
  let capsuleEligibilityKey = null;
  const COMPANION_MEMORY_KEY = "thought-archaeology.companions.v1";
  const CIRCUIT_MEMORY_KEY = "thought-archaeology.continuation-circuits.v2";
  const FIELD_NOTE_MEMORY_KEY = "thought-archaeology.field-notes-entered.v1";
  const CAPSULE_EARNED_MEMORY_KEY = "thought-archaeology.knowledge-capsules-earned.v1";
  const knownHeads = new Map();
  const sessionTitles = new Map();
  let liveArrivals = loadCompanionThoughts();
  let arrivalsDirty = false;
  let arrivingFocus = null;
  let rememberedCircuits = loadContinuationCircuits();
  const continuationCircuits = new Map();
  let companionPolling = false;
  let companionReady = false;
  let workspaceBusy = false;
  let parallelComposerOpen = false;
  let parallelProgress = null;
  const parallelJobStates = new Map();
  let workspaceState = null;
  const enteredFieldNotes = loadEnteredFieldNotes();
  const announcedCapsuleMilestones = loadAnnouncedCapsuleMilestones();

  function loadAnnouncedCapsuleMilestones() {
    try {
      const saved = JSON.parse(
        window.localStorage.getItem(CAPSULE_EARNED_MEMORY_KEY) || "[]"
      );
      return new Set(Array.isArray(saved) ? saved.filter((item) => typeof item === "string") : []);
    } catch (_error) {
      return new Set();
    }
  }

  function rememberCapsuleMilestone(key) {
    announcedCapsuleMilestones.add(key);
    try {
      window.localStorage.setItem(
        CAPSULE_EARNED_MEMORY_KEY,
        JSON.stringify([...announcedCapsuleMilestones].slice(-240))
      );
    } catch (_error) {
      // The earned cue remains optional browser-local atmosphere.
    }
  }

  function loadEnteredFieldNotes() {
    try {
      const saved = JSON.parse(
        window.localStorage.getItem(FIELD_NOTE_MEMORY_KEY) || "[]"
      );
      return new Set(Array.isArray(saved) ? saved.filter((item) => typeof item === "string") : []);
    } catch (_error) {
      return new Set();
    }
  }

  function rememberFieldNoteEntry(noteId) {
    enteredFieldNotes.add(noteId);
    try {
      window.localStorage.setItem(
        FIELD_NOTE_MEMORY_KEY, JSON.stringify([...enteredFieldNotes].slice(-240))
      );
    } catch (_error) {
      // First-entry atmosphere remains optional browser-local memory.
    }
  }

  function loadCompanionThoughts() {
    try {
      const saved = JSON.parse(window.localStorage.getItem(COMPANION_MEMORY_KEY) || "[]");
      if (!Array.isArray(saved)) return [];
      return saved.filter(
        (item) => item && item.graphId && item.nodeId && item.text && item.title
      ).slice(-240);
    } catch (_error) {
      return [];
    }
  }

  function saveCompanionThoughts() {
    try {
      window.localStorage.setItem(
        COMPANION_MEMORY_KEY,
        JSON.stringify(liveArrivals.slice(-240))
      );
    } catch (_error) {
      // Browser memory is optional; the graph store remains canonical.
    }
  }

  function loadContinuationCircuits() {
    try {
      const saved = JSON.parse(window.localStorage.getItem(CIRCUIT_MEMORY_KEY) || "[]");
      if (!Array.isArray(saved)) return [];
      return saved.filter((item) =>
        item && item.requestId && Number.isInteger(item.neuronIndex) &&
        (item.phase === "waiting" || item.phase === "arrival")
      );
    } catch (_error) {
      return [];
    }
  }

  function saveContinuationCircuits() {
    try {
      if (rememberedCircuits.length) {
        window.localStorage.setItem(
          CIRCUIT_MEMORY_KEY, JSON.stringify(rememberedCircuits)
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
    liveArrivals = liveArrivals.slice(-240);
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

  function openLegendMenu() {
    if (!elThreadCompass.hidden) closeThreadCompass();
    if (!elWorkspaceMenu.hidden) closeWorkspaceMenu();
    elLegendScrim.hidden = false;
    elLegendMenu.hidden = false;
    elLegendClose.focus();
  }

  function closeLegendMenu() {
    if (composing) closeComposer();
    elLegendScrim.hidden = true;
    elLegendMenu.hidden = true;
    if (document.activeElement && document.activeElement.blur) {
      document.activeElement.blur();
    }
    showWaitingArrivals();
  }

  function toggleLegendMenu() {
    if (elLegendMenu.hidden) openLegendMenu();
    else closeLegendMenu();
  }

  function workspaceName(name) {
    return name ? name.charAt(0).toUpperCase() + name.slice(1) : "Unknown";
  }

  function renderParallelProgress(progress) {
    elWorkspaceParallelProgress.replaceChildren();
    if (!progress) {
      elWorkspaceParallelCancel.hidden = true;
      return;
    }
    for (const job of progress.jobs || []) {
      const line = document.createElement("div");
      line.className = "workspace-parallel-job";
      line.dataset.status = job.status;
      line.textContent = [
        job.display_name || workspaceName(job.harness),
        job.status,
        job.public_summary,
      ].filter(Boolean).join(" · ");
      if (job.public_summary) line.title = job.public_summary;
      elWorkspaceParallelProgress.append(line);
    }
    elWorkspaceParallelCancel.hidden = Boolean(progress.terminal);
  }

  function updateParallelSubmitCopy() {
    const count = elWorkspaceParallelHarnesses.querySelectorAll("input:checked").length;
    elWorkspaceParallelSubmit.disabled = workspaceBusy || count < 2;
    elWorkspaceParallelSubmit.textContent = count < 2
      ? "select at least one more collaborator"
      : `send ${count} requests · uses provider quota`;
  }

  function renderParallelComposer(payload) {
    const progress = view && view.parallel_continuation
      ? view.parallel_continuation
      : parallelProgress;
    const live = progress && !progress.terminal;
    const visible = parallelComposerOpen || live;
    elWorkspaceParallelSection.hidden = !visible;
    if (!visible) return;
    elWorkspaceParallelForm.hidden = Boolean(live);
    elWorkspaceParallelHarnesses.replaceChildren();
    for (const harness of payload.harnesses || []) {
      const label = document.createElement("label");
      label.className = "workspace-parallel-choice";
      const input = document.createElement("input");
      input.type = "checkbox";
      input.name = "parallel-harness";
      input.value = harness.name;
      input.checked = Boolean(harness.selected);
      input.disabled = Boolean(harness.selected || live || workspaceBusy);
      input.addEventListener("change", updateParallelSubmitCopy);
      const name = document.createElement("span");
      name.textContent = workspaceName(harness.name);
      const model = document.createElement("small");
      model.textContent = harness.model || "model not refreshed";
      label.append(input, name, model);
      elWorkspaceParallelHarnesses.append(label);
    }
    updateParallelSubmitCopy();
    renderParallelProgress(progress);
  }

  function renderWorkspace(payload) {
    workspaceState = payload;
    const service = payload.service || {};
    const watcherActive = service.active === "active" || service.active === "activating";
    const pending = payload.pending || [];
    const active = payload.active_harness;
    if (!active) {
      elWorkspaceHarnessStatus.textContent = "No collaborator is registered.";
    } else if (pending.length) {
      const responding = pending.find((item) => item.harness);
      elWorkspaceHarnessStatus.textContent = responding
        ? `${workspaceName(responding.harness)} is responding now · switching waits until it finishes`
        : `A continuation is queued for ${workspaceName(active)} · switching waits until it finishes`;
    } else if (watcherActive) {
      elWorkspaceHarnessStatus.textContent =
        `${workspaceName(active)} will author future continuations. Existing graphs keep their recorded authorship.`;
    } else {
      elWorkspaceHarnessStatus.textContent =
        `${workspaceName(active)} is selected, but the background watcher is ${service.active || "not active"}.`;
    }
    if (service.error) {
      elWorkspaceHarnessStatus.textContent += ` ${service.error}`;
    }

    elWorkspaceHarnesses.replaceChildren();
    for (const harness of payload.harnesses || []) {
      const row = document.createElement("div");
      row.className = "workspace-harness-row";
      const button = document.createElement("button");
      button.type = "button";
      button.className = "workspace-harness";
      const isActive = harness.selected && watcherActive;
      if (isActive) button.classList.add("active");
      const action = document.createElement("strong");
      action.textContent = isActive
        ? `${workspaceName(harness.name)} · active`
        : `Activate ${workspaceName(harness.name)}`;
      const model = document.createElement("small");
      model.textContent = harness.model
        ? `model · ${harness.model}`
        : "model · refresh to read";
      button.append(action, model);
      button.disabled = workspaceBusy || isActive || pending.length > 0;
      button.addEventListener("click", () => activateWorkspaceHarness(harness.name));
      const refresh = document.createElement("button");
      refresh.type = "button";
      refresh.className = "workspace-model-refresh";
      refresh.textContent = "↻ Refresh";
      refresh.setAttribute("aria-label", `Refresh ${workspaceName(harness.name)} model`);
      refresh.title = `Refresh ${workspaceName(harness.name)} model`;
      refresh.disabled = workspaceBusy;
      refresh.addEventListener("click", () => refreshWorkspaceHarnessModel(harness.name));
      row.append(button, refresh);
      elWorkspaceHarnesses.append(row);
    }

    elWorkspaceNewToggle.disabled = workspaceBusy || pending.length > 0 || !active;
    elWorkspaceHistory.replaceChildren();
    for (const session of payload.history || []) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "workspace-history-entry";
      if (view && session.id === view.session_id) button.classList.add("current");
      button.disabled = !session.spawn;
      const title = document.createElement("strong");
      title.textContent = session.title;
      const meta = document.createElement("small");
      const updated = session.updated_at.replace("T", " ").replace("Z", " UTC");
      meta.textContent = `${session.graph_count} ${session.graph_count === 1 ? "generation" : "generations"} · ${session.author_label} · ${updated}`;
      button.append(title, meta);
      if (session.spawn) {
        button.addEventListener("click", () => {
          closeWorkspaceMenu();
          inhabit(session.spawn.graph_id, session.spawn.node_id);
        });
      }
      elWorkspaceHistory.append(button);
    }
    renderParallelComposer(payload);
  }

  async function submitParallelContinuation(event) {
    event.preventDefault();
    if (workspaceBusy || !view) return;
    const prompt = elWorkspaceParallelPrompt.value.trim();
    const harnesses = [...elWorkspaceParallelHarnesses.querySelectorAll("input:checked")]
      .map((input) => input.value);
    if (!prompt) {
      elWorkspaceActionStatus.textContent = "Write one shared prompt first.";
      elWorkspaceParallelPrompt.focus();
      return;
    }
    if (harnesses.length < 2) {
      elWorkspaceActionStatus.textContent = "Select at least two collaborators.";
      return;
    }
    workspaceBusy = true;
    elWorkspaceActionStatus.textContent = "opening parallel paths…";
    try {
      const result = await post("/api/parallel", {
        graph_id: view.graph_id,
        node_id: view.node.id,
        prompt,
        harnesses,
      });
      parallelProgress = result.progress;
      view.parallel_continuation = parallelProgress;
      elWorkspaceParallelPrompt.value = "";
      syncParallelProgress(parallelProgress);
      renderParallelComposer(workspaceState || { harnesses: [] });
      elWorkspaceActionStatus.textContent = "Parallel continuation queued in collaborator order.";
    } catch (error) {
      elWorkspaceActionStatus.textContent = String(error.message || error);
    } finally {
      workspaceBusy = false;
    }
  }

  async function cancelParallelContinuation() {
    const progress = (view && view.parallel_continuation) || parallelProgress;
    if (workspaceBusy || !progress || progress.terminal) return;
    workspaceBusy = true;
    try {
      const result = await post(`/api/parallel/${progress.id}/cancel`, {});
      parallelProgress = result.progress;
      if (view) view.parallel_continuation = parallelProgress;
      syncParallelProgress(parallelProgress);
      renderParallelComposer(workspaceState || { harnesses: [] });
      elWorkspaceActionStatus.textContent = "Remaining parallel requests canceled.";
    } catch (error) {
      elWorkspaceActionStatus.textContent = String(error.message || error);
    } finally {
      workspaceBusy = false;
    }
  }

  async function activateWorkspaceHarness(name) {
    if (workspaceBusy) return;
    workspaceBusy = true;
    elWorkspaceActionStatus.textContent = `activating ${workspaceName(name)}…`;
    for (const button of elWorkspaceHarnesses.querySelectorAll("button")) {
      button.disabled = true;
    }
    try {
      const result = await post("/api/workspace/harness", { harness: name });
      elWorkspaceActionStatus.textContent = `${workspaceName(name)} is active for future continuations.`;
      workspaceBusy = false;
      renderWorkspace(result.workspace);
    } catch (error) {
      elWorkspaceActionStatus.textContent = String(error.message || error);
      workspaceBusy = false;
      const payload = await api("/api/workspace").catch(() => null);
      if (payload) renderWorkspace(payload);
    } finally {
      workspaceBusy = false;
    }
  }

  async function refreshWorkspaceHarnessModel(name) {
    if (workspaceBusy) return;
    workspaceBusy = true;
    elWorkspaceActionStatus.textContent = `refreshing ${workspaceName(name)} model…`;
    for (const button of elWorkspaceHarnesses.querySelectorAll("button")) {
      button.disabled = true;
    }
    try {
      const result = await post("/api/workspace/harness/model", { harness: name });
      const refreshed = (result.workspace.harnesses || []).find((item) => item.name === name);
      elWorkspaceActionStatus.textContent = refreshed && refreshed.model
        ? `${workspaceName(name)} model refreshed · ${refreshed.model}`
        : `${workspaceName(name)} model refreshed.`;
      workspaceBusy = false;
      renderWorkspace(result.workspace);
    } catch (error) {
      elWorkspaceActionStatus.textContent = String(error.message || error);
      workspaceBusy = false;
      const payload = await api("/api/workspace").catch(() => null);
      if (payload) renderWorkspace(payload);
    } finally {
      workspaceBusy = false;
    }
  }

  async function submitWorkspaceInquiry(event) {
    event.preventDefault();
    if (workspaceBusy) return;
    const prompt = elWorkspaceNewPrompt.value.trim();
    if (!prompt) {
      elWorkspaceActionStatus.textContent = "Write an opening inquiry first.";
      elWorkspaceNewPrompt.focus();
      return;
    }
    workspaceBusy = true;
    elWorkspaceActionStatus.textContent = "opening a clean graph…";
    try {
      const result = await post("/api/workspace/inquiry", { prompt });
      elWorkspaceNewPrompt.value = "";
      closeWorkspaceMenu();
      await inhabit(result.stand.graph_id, result.stand.node_id);
    } catch (error) {
      elWorkspaceActionStatus.textContent = String(error.message || error);
    } finally {
      workspaceBusy = false;
    }
  }

  function closeWorkspaceMenu() {
    elWorkspaceScrim.hidden = true;
    elWorkspaceMenu.hidden = true;
    elWorkspaceNewForm.hidden = true;
    elWorkspaceNewToggle.setAttribute("aria-expanded", "false");
    parallelComposerOpen = false;
    elWorkspaceParallelSection.hidden = true;
    if (document.activeElement && document.activeElement.blur) {
      document.activeElement.blur();
    }
    showWaitingArrivals();
  }

  async function openWorkspaceMenu(parallel = false) {
    if (composing || busy) return;
    if (!elLegendMenu.hidden) closeLegendMenu();
    if (!elThreadCompass.hidden) closeThreadCompass();
    elWorkspaceScrim.hidden = false;
    elWorkspaceMenu.hidden = false;
    parallelComposerOpen = parallel;
    elWorkspaceActionStatus.textContent = "";
    elWorkspaceHarnessStatus.textContent = "reading registered collaborators…";
    elWorkspaceHarnesses.replaceChildren();
    elWorkspaceHistory.replaceChildren();
    elWorkspaceClose.focus();
    try {
      renderWorkspace(await api("/api/workspace"));
      if (parallel && !elWorkspaceParallelForm.hidden) {
        elWorkspaceParallelPrompt.focus();
      }
    } catch (error) {
      elWorkspaceHarnessStatus.textContent = String(error.message || error);
    }
  }

  function toggleWorkspaceMenu() {
    if (elWorkspaceMenu.hidden) openWorkspaceMenu();
    else closeWorkspaceMenu();
  }

  let threadLineage = null;
  let threadComparison = null;
  let threadNote = null;
  let threadCapsule = null;
  let threadComposer = false;
  let threadReturnFocus = null;

  function closeThreadCompass(restoreFocus = true) {
    sound.setFieldNoteWriting(false);
    elThreadCompass.hidden = true;
    threadLineage = null;
    threadComparison = null;
    threadNote = null;
    threadCapsule = null;
    threadComposer = false;
    elThreadTitle.textContent = "Thread Compass";
    elThreadClose.textContent = "close · T / esc";
    if (restoreFocus) {
      const target = threadReturnFocus && threadReturnFocus.isConnected
        ? threadReturnFocus
        : canvas;
      target.focus({ preventScroll: true });
    }
    threadReturnFocus = null;
    showWaitingArrivals();
  }

  function visitThreadEntry(entry) {
    closeThreadCompass(false);
    inhabit(entry.graph_id, entry.node_id);
  }

  function renderThreadEntry(entry, insideGroup = false) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "thread-entry";
    button.dataset.kind = entry.kind;
    button.style.setProperty(
      "--thread-depth", String(insideGroup ? 0 : (entry.depth || 0))
    );
    if (insideGroup) button.classList.add("parallel-member");
    if (entry.graph_id === view.graph_id) button.classList.add("current");
    if (entry.graph_id === threadLineage.head_graph_id) button.classList.add("head");
    button.disabled = !entry.node_id;

    const label = document.createElement("span");
    label.className = "thread-entry-label";
    label.textContent = entry.label;
    const summary = document.createElement("span");
    summary.className = "thread-entry-summary";
    summary.textContent = entry.summary;
    const meta = document.createElement("span");
    meta.className = "thread-entry-meta";
    const details = [];
    if (entry.graph_id === view.graph_id) details.push("you are here");
    if (entry.prompt) details.push(`question: ${entry.prompt}`);
    else if (entry.kind === "continuation") details.push("continued without a new question");
    if (entry.reason) details.push(`reason: ${entry.reason}`);
    details.push(entry.created_at.replace("T", " ").replace("Z", " UTC"));
    meta.textContent = details.join(" · ");
    button.append(label, summary, meta);
    button.addEventListener("click", () => visitThreadEntry(entry));
    return button;
  }

  function renderParallelGroup(group) {
    const section = document.createElement("section");
    section.className = "thread-parallel-group";
    section.setAttribute("role", "listitem");
    section.style.setProperty("--thread-depth", String(group.depth || 0));
    if (group.graph_ids.includes(view.graph_id)) section.classList.add("current");
    if (group.graph_ids.includes(threadLineage.head_graph_id)) section.classList.add("head");

    const compare = document.createElement("button");
    compare.type = "button";
    compare.className = "thread-parallel-compare";
    compare.dataset.requestId = group.representative_request_id;
    const prompt = group.prompt || "continued without a new question";
    compare.setAttribute(
      "aria-label",
      `Compare ${group.completed_count} same-question paths. Exact question: ${prompt}`
    );
    const question = document.createElement("span");
    question.className = "thread-parallel-question";
    question.textContent = prompt;
    const names = group.harnesses.map((item) => item.display_name).join(" · ");
    const meta = document.createElement("span");
    meta.className = "thread-parallel-meta";
    const counts = group.counts || {};
    meta.textContent = [
      `${counts.completed || 0} completed`,
      `${counts.failed || 0} failed`,
      `${counts.canceled || 0} canceled`,
      `${counts.pending || 0} pending`,
      names,
    ].join(" · ");
    const action = document.createElement("span");
    action.className = "thread-parallel-action";
    action.textContent = `Compare ${group.completed_count} paths`;
    compare.append(question, meta, action);
    compare.addEventListener(
      "click", () => openParallelComparison(group.representative_request_id)
    );
    section.append(compare);

    const members = document.createElement("div");
    members.className = "thread-parallel-members";
    for (const entry of group.entries || []) {
      members.append(renderThreadEntry(entry, true));
    }
    section.append(members);
    appendFieldNoteCards(
      section,
      group.field_notes || [],
      "Human Field Notes · connective inscriptions",
      group.knowledge_capsules || []
    );
    return section;
  }

  function renderThreadCompass(lineage, focusRequestId = null) {
    threadLineage = lineage;
    threadComparison = null;
    threadNote = null;
    threadCapsule = null;
    threadComposer = false;
    const entries = lineage.entries || [];
    const parallelGroups = lineage.parallel_groups || [];
    const groupByGraph = new Map();
    for (const group of parallelGroups) {
      for (const graphId of group.graph_ids) groupByGraph.set(graphId, group);
    }
    const renderedGroups = new Set();
    const latestAi = entries.find(
      (entry) => entry.graph_id === lineage.latest_ai_graph_id
    );
    elThreadTitle.textContent = "Thread Compass";
    elThreadClose.textContent = "close · T / esc";
    elThreadSubtitle.textContent =
      `${lineage.title} · ${entries.length} graph ${entries.length === 1 ? "generation" : "generations"}`;
    elThreadStatus.textContent =
      "Select any generation to re-enter its first chamber. The graph store remains unchanged.";
    elThreadList.replaceChildren();

    appendFieldNoteCards(
      elThreadList,
      lineage.standing_field_notes || [],
      "Field Notes from this chamber"
    );

    if (latestAi && latestAi.node_id && latestAi.graph_id !== view.graph_id) {
      elThreadLatest.hidden = false;
      elThreadLatest.textContent = `jump to latest AI response · ${latestAi.label}`;
      elThreadLatest.onclick = () => visitThreadEntry(latestAi);
    } else {
      elThreadLatest.hidden = true;
      elThreadLatest.onclick = null;
    }

    let focusTarget = null;
    for (const entry of entries) {
      const group = groupByGraph.get(entry.graph_id);
      if (group) {
        if (renderedGroups.has(group.representative_request_id)) continue;
        renderedGroups.add(group.representative_request_id);
        const groupElement = renderParallelGroup(group);
        elThreadList.append(groupElement);
        const groupFocus = groupElement.querySelector(".thread-parallel-compare");
        if (focusRequestId === group.representative_request_id) focusTarget = groupFocus;
        else if (!focusTarget && group.graph_ids.includes(view.graph_id)) {
          focusTarget = groupElement.querySelector(".thread-entry.current") || groupFocus;
        }
        continue;
      }
      const button = renderThreadEntry(entry);
      if (!focusTarget && entry.graph_id === view.graph_id) focusTarget = button;
      elThreadList.append(button);
    }
    const firstFocus = focusTarget || (
      elThreadLatest.hidden ? elThreadList.firstElementChild : elThreadLatest
    ) || elThreadClose;
    firstFocus.focus();
  }

  function appendParallelTexts(parent, label, items, emptyText = "none recorded") {
    const row = document.createElement("div");
    row.className = "parallel-path-row";
    const heading = document.createElement("div");
    heading.className = "parallel-path-label";
    heading.textContent = label;
    const body = document.createElement("div");
    body.className = "parallel-path-value";
    if (!items.length) {
      body.textContent = emptyText;
    } else {
      const list = document.createElement("ul");
      for (const item of items) {
        const li = document.createElement("li");
        li.textContent = item.text;
        list.append(li);
      }
      body.append(list);
    }
    row.append(heading, body);
    parent.append(row);
  }

  function renderParallelComparison(comparison) {
    sound.setFieldNoteWriting(false);
    threadComparison = comparison;
    threadNote = null;
    threadCapsule = null;
    threadComposer = false;
    elThreadTitle.textContent = "Parallel continuations";
    elThreadSubtitle.textContent =
      `${comparison.completed_count} answers from the same chamber. No vote or winner is inferred.`;
    elThreadClose.textContent = "back to lineage · esc";
    elThreadStatus.textContent = "Each reading uses only recorded graph fields and structural checks.";
    elThreadLatest.hidden = true;
    elThreadList.replaceChildren();

    const context = document.createElement("section");
    context.className = "parallel-context";
    const sourceLabel = document.createElement("div");
    sourceLabel.className = "parallel-context-label";
    sourceLabel.textContent = "Exact source thought";
    const source = document.createElement("p");
    source.textContent = comparison.source_thought.text;
    const promptLabel = document.createElement("div");
    promptLabel.className = "parallel-context-label";
    promptLabel.textContent = "Exact shared question";
    const prompt = document.createElement("p");
    prompt.textContent = comparison.prompt || "continued without a new question";
    const counts = document.createElement("p");
    counts.textContent = [
      `${comparison.counts.completed} completed`,
      `${comparison.counts.failed} failed`,
      `${comparison.counts.canceled} canceled`,
      `${comparison.counts.pending} pending`,
    ].join(" · ");
    context.append(sourceLabel, source, promptLabel, prompt, counts);
    elThreadList.append(context);

    appendFieldNoteCards(
      elThreadList,
      comparison.field_notes || [],
      "Human Field Notes",
      comparison.knowledge_capsules || []
    );

    const noteAction = document.createElement("button");
    noteAction.type = "button";
    noteAction.className = "field-note-write";
    const existingNote = (comparison.field_notes || [])[0] || null;
    noteAction.textContent = existingNote
      ? "Edit Field Note · appends a revision"
      : "Write Field Note";
    noteAction.addEventListener("click", () => {
      if (existingNote) {
        openFieldNoteEditor(existingNote.id, comparison);
        return;
      }
      const standingPath = (comparison.paths || []).find((path) =>
        path.graph_id === view.graph_id &&
        (path.selectable_thoughts || []).some((thought) => thought.id === view.node.id)
      );
      renderFieldNoteComposer(
        comparison,
        standingPath
          ? {
              session_id: comparison.session_id,
              graph_id: view.graph_id,
              node_id: view.node.id,
            }
          : null
      );
    });
    elThreadList.append(noteAction);

    for (const path of comparison.paths || []) {
      const article = document.createElement("article");
      article.className = "parallel-path";
      if (path.graph_id === view.graph_id) article.classList.add("current");
      const heading = document.createElement("h3");
      heading.textContent = `${path.harness_display_name} · ${path.model}`;
      article.append(heading);
      const entry = path.entry_node;
      appendParallelTexts(
        article,
        entry && entry.kind === "claim" ? "Entry claim" : "Entry thought",
        entry ? [entry] : []
      );
      appendParallelTexts(article, "Judgment", path.judgment_calls || []);
      appendParallelTexts(article, "Uncertainty", path.uncertainties || []);

      const roads = document.createElement("div");
      roads.className = "parallel-path-row";
      const roadsLabel = document.createElement("div");
      roadsLabel.className = "parallel-path-label";
      roadsLabel.textContent = "Roads not taken";
      const roadsValue = document.createElement("div");
      roadsValue.className = "parallel-path-value";
      roadsValue.textContent = String((path.rejected_alternatives || []).length);
      roads.append(roadsLabel, roadsValue);
      article.append(roads);

      const recorded = (path.recorded_warnings || []).map(
        (text) => ({ text: `Recorded at compile · ${text}` })
      );
      const current = (path.current_policy_warnings || []).map(
        (text) => ({ text: `Current policy · ${text}` })
      );
      appendParallelTexts(article, "Structural notes", [...recorded, ...current], "none");

      const graphMeta = document.createElement("div");
      graphMeta.className = "parallel-path-meta";
      graphMeta.textContent =
        `${path.node_count} nodes · ${path.edge_count} edges · ${path.created_at.replace("T", " ").replace("Z", " UTC")}`;
      const enter = document.createElement("button");
      enter.type = "button";
      enter.className = "parallel-path-enter";
      enter.textContent = "Enter this path";
      enter.disabled = !entry;
      enter.addEventListener("click", () => {
        if (entry) visitThreadEntry({ graph_id: path.graph_id, node_id: entry.id });
      });
      article.append(graphMeta, enter);
      elThreadList.append(article);
    }
    elThreadPanel.scrollTop = 0;
    elThreadClose.focus({ preventScroll: true });
  }

  async function openParallelComparison(requestId) {
    elThreadStatus.textContent = "reading same-question paths…";
    elThreadList.replaceChildren();
    try {
      const comparison = await api(`/api/parallel/${requestId}`);
      if (!elThreadCompass.hidden) renderParallelComparison(comparison);
    } catch (error) {
      elThreadStatus.textContent = String(error.message || error);
      if (threadLineage) renderThreadCompass(threadLineage, requestId);
    }
  }

  function appendFieldNoteCards(parent, notes, headingText, capsules = []) {
    if (!notes.length) return;
    const section = document.createElement("section");
    section.className = "field-note-list";
    const heading = document.createElement("h3");
    heading.textContent = headingText;
    section.append(heading);
    for (const note of notes) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "field-note-card";
      const label = document.createElement("span");
      label.className = "field-note-label";
      label.textContent = `Human Field Note · ${note.kind_label}`;
      const body = document.createElement("span");
      body.className = "field-note-card-text";
      body.textContent = note.text;
      const meta = document.createElement("span");
      meta.className = "field-note-meta";
      meta.textContent = [
        `${note.reference_count} exact thoughts`,
        `${note.revision_count || 1} ${(note.revision_count || 1) === 1 ? "revision" : "revisions"}`,
        note.integrity === "verified" ? "source integrity verified" : "source integrity failed",
      ].join(" · ");
      button.append(label, body, meta);
      button.addEventListener("click", () => openFieldNote(note.id));
      section.append(button);
      const nested = capsules.filter((capsule) => capsule.field_note_id === note.id);
      if (nested.length) {
        const capsuleList = document.createElement("div");
        capsuleList.className = "knowledge-capsule-list";
        for (const capsule of nested) {
          const capsuleButton = document.createElement("button");
          capsuleButton.type = "button";
          capsuleButton.className = "knowledge-capsule-card";
          const capsuleLabel = document.createElement("span");
          capsuleLabel.className = "knowledge-capsule-label";
          capsuleLabel.textContent = `Knowledge Capsule · ${capsule.state}`;
          const capsuleMeta = document.createElement("span");
          capsuleMeta.className = "knowledge-capsule-meta";
          capsuleMeta.textContent =
            `pinned revision ${capsule.field_note_revision_id} · head ${capsule.head_graph_id}`;
          capsuleButton.append(capsuleLabel, capsuleMeta);
          capsuleButton.addEventListener("click", () => openThreadCapsule(capsule.id));
          capsuleList.append(capsuleButton);
        }
        section.append(capsuleList);
      }
    }
    parent.append(section);
  }

  async function openThreadCapsule(capsuleId) {
    elThreadStatus.textContent = "reading the frozen Knowledge Capsule…";
    try {
      const capsule = await api(`/api/knowledge-capsules/${capsuleId}`);
      if (!elThreadCompass.hidden) renderThreadCapsule(capsule);
    } catch (error) {
      elThreadStatus.textContent = String(error.message || error);
    }
  }

  function renderThreadCapsule(capsule) {
    threadCapsule = capsule;
    threadNote = null;
    threadComposer = false;
    elThreadTitle.textContent = "Knowledge Capsule";
    elThreadSubtitle.textContent =
      `${capsule.state} · frozen human milestone · ${capsule.artifact_count} exact artifacts`;
    elThreadClose.textContent = "back to comparison · esc";
    elThreadLatest.hidden = true;
    elThreadStatus.textContent = capsule.integrity === "verified"
      ? "Frozen source integrity verified."
      : "Frozen source integrity failed.";
    elThreadList.replaceChildren();
    const article = document.createElement("article");
    article.className = "field-note-reading";
    const label = document.createElement("div");
    label.className = "knowledge-capsule-label";
    label.textContent = `Knowledge Capsule · ${capsule.state}`;
    const text = document.createElement("p");
    text.textContent = capsule.state === "launched"
      ? "This one-shot milestone has been carried outward as a private Markdown dossier."
      : "The frozen Capsule is charged and waiting for its one spatial launch.";
    const meta = document.createElement("div");
    meta.className = "knowledge-capsule-meta";
    meta.textContent = [
      `capsule ${capsule.id}`,
      `session head ${capsule.head_graph_id}`,
      `Field Note revision ${capsule.field_note_revision_id}`,
      `source integrity ${capsule.integrity}`,
      capsule.markdown_path ? `Markdown ${capsule.markdown_path}` : "Markdown is written only at launch",
    ].join(" · ");
    article.append(label, text, meta);
    elThreadList.append(article);
    elThreadPanel.scrollTop = 0;
    elThreadClose.focus({ preventScroll: true });
  }

  async function openFieldNote(noteId, revisionId = null) {
    elThreadStatus.textContent = "reading the human Field Note…";
    try {
      const suffix = revisionId
        ? `?revision=${encodeURIComponent(revisionId)}`
        : "";
      const note = await api(`/api/field-notes/${noteId}${suffix}`);
      if (!elThreadCompass.hidden) renderFieldNote(note);
    } catch (error) {
      elThreadStatus.textContent = String(error.message || error);
    }
  }

  async function openFieldNoteEditor(noteId, comparison = null) {
    elThreadStatus.textContent = "opening the Field Note revision editor…";
    try {
      const note = await api(`/api/field-notes/${noteId}`);
      const targetComparison = comparison || threadComparison || (
        note.comparison_request_id
          ? await api(`/api/parallel/${note.comparison_request_id}`)
          : null
      );
      if (!targetComparison) throw new Error("Field Note comparison is unavailable");
      threadComparison = targetComparison;
      renderFieldNoteComposer(targetComparison, null, note);
    } catch (error) {
      elThreadStatus.textContent = String(error.message || error);
    }
  }

  function renderFieldNote(note) {
    threadNote = note;
    threadComposer = false;
    elThreadTitle.textContent = "Human Field Note";
    const revisionIndex = Math.max(
      0,
      (note.revision_history || []).findIndex(
        (item) => item.revision_id === note.revision_id
      )
    );
    elThreadSubtitle.textContent =
      `${note.kind_label} · written by the inhabitant · revision ${revisionIndex + 1}/${note.revision_count || 1} · ${note.reference_count} exact thoughts`;
    elThreadClose.textContent = threadComparison
      ? "back to comparison · esc"
      : "back to lineage · esc";
    elThreadLatest.hidden = true;
    elThreadStatus.textContent =
      note.integrity === "verified" ? "Source integrity verified." : "Source integrity failed.";
    elThreadList.replaceChildren();

    const article = document.createElement("article");
    article.className = "field-note-reading";
    const label = document.createElement("div");
    label.className = "field-note-label";
    label.textContent = `Human Field Note · ${note.kind_label}`;
    const text = document.createElement("p");
    text.textContent = note.text;
    article.append(label, text);
    elThreadList.append(article);

    const edit = document.createElement("button");
    edit.type = "button";
    edit.className = "field-note-write";
    edit.textContent = "Edit this Field Note · preserve the earlier revision";
    edit.addEventListener("click", () => openFieldNoteEditor(note.id));
    elThreadList.append(edit);

    if ((note.revision_history || []).length > 1) {
      const history = document.createElement("section");
      history.className = "field-note-list";
      const heading = document.createElement("h3");
      heading.textContent = "Revision history · nothing overwritten";
      history.append(heading);
      for (const [index, revision] of note.revision_history.entries()) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "field-note-card";
        if (revision.revision_id === note.revision_id) button.disabled = true;
        const revisionLabel = document.createElement("span");
        revisionLabel.className = "field-note-label";
        revisionLabel.textContent =
          `Revision ${index + 1}/${note.revision_count} · ${revision.kind_label}${revision.current ? " · current" : ""}`;
        const body = document.createElement("span");
        body.className = "field-note-card-text";
        body.textContent = revision.text;
        const meta = document.createElement("span");
        meta.className = "field-note-meta";
        meta.textContent =
          `${revision.created_at.replace("T", " ").replace("Z", " UTC")} · ${revision.reference_count} exact thoughts`;
        button.append(revisionLabel, body, meta);
        button.addEventListener("click", () =>
          openFieldNote(note.id, revision.revision_id)
        );
        history.append(button);
      }
      elThreadList.append(history);
    }

    for (const reference of note.references || []) {
      const source = document.createElement("article");
      source.className = "field-note-reference";
      const sourceLabel = document.createElement("div");
      sourceLabel.className = "field-note-label";
      sourceLabel.textContent = "Exact referenced thought";
      const attribution = document.createElement("div");
      attribution.className = "field-note-meta";
      const harness = reference.harness
        ? reference.harness.replace(/(^|-)([a-z])/g, (_match, dash, letter) => `${dash ? " " : ""}${letter.toUpperCase()}`)
        : "Human or imported graph";
      attribution.textContent = reference.thought
        ? `${harness} · ${reference.model.name} · ${reference.thought.kind.replace(/_/g, " ")} · ${reference.thought.status}`
        : `${reference.session_id}/${reference.graph_id}/${reference.node_id}`;
      const thought = document.createElement("p");
      thought.textContent = reference.thought
        ? reference.thought.text
        : "Referenced source is unavailable.";
      const integrity = document.createElement("div");
      integrity.className = "field-note-integrity";
      integrity.textContent = reference.integrity === "verified"
        ? "Source integrity verified"
        : `Source integrity ${reference.integrity}`;
      const enter = document.createElement("button");
      enter.type = "button";
      enter.className = "field-note-enter";
      enter.textContent = "Enter this thought";
      enter.disabled = !reference.entry || reference.integrity !== "verified";
      enter.addEventListener("click", () => {
        if (reference.entry) visitThreadEntry(reference.entry);
      });
      source.append(sourceLabel, attribution, thought, integrity, enter);
      elThreadList.append(source);
    }
    elThreadPanel.scrollTop = 0;
    elThreadClose.focus({ preventScroll: true });
  }

  function renderFieldNoteComposer(
    comparison,
    initialReference = null,
    existingNote = null
  ) {
    threadComposer = true;
    threadNote = existingNote;
    elThreadTitle.textContent = existingNote ? "Edit Field Note" : "Write Field Note";
    elThreadSubtitle.textContent =
      "Select exact thoughts from at least two paths, then decide what mattered in your own words.";
    elThreadClose.textContent = "back to comparison · esc";
    elThreadLatest.hidden = true;
    elThreadStatus.textContent = existingNote
      ? "Saving appends a human revision. Earlier text and source selections remain intact."
      : "No provider will be called. Source graphs will not change.";
    elThreadList.replaceChildren();
    sound.setFieldNoteWriting(true);

    const form = document.createElement("form");
    form.className = "field-note-form";
    const selectionStatus = document.createElement("div");
    selectionStatus.className = "field-note-selection-status";
    const selectedReview = document.createElement("ol");
    selectedReview.className = "field-note-review";
    const existingSelections = new Set(
      (existingNote?.references || []).map((reference) =>
        `${reference.session_id}:${reference.graph_id}:${reference.node_id}`
      )
    );

    for (const path of comparison.paths || []) {
      const fieldset = document.createElement("fieldset");
      fieldset.className = "field-note-path";
      const legend = document.createElement("legend");
      legend.textContent = `${path.harness_display_name} · ${path.model}`;
      fieldset.append(legend);
      for (const thought of path.selectable_thoughts || []) {
        const label = document.createElement("label");
        label.className = "field-note-thought";
        const input = document.createElement("input");
        input.type = "checkbox";
        input.dataset.sessionId = comparison.session_id;
        input.dataset.graphId = path.graph_id;
        input.dataset.nodeId = thought.id;
        input.dataset.attribution = `${path.harness_display_name} · ${path.model}`;
        input.dataset.kind = thought.kind.replace(/_/g, " ");
        input.dataset.text = thought.text;
        input.checked = existingSelections.has(
          `${comparison.session_id}:${path.graph_id}:${thought.id}`
        ) || Boolean(
          !existingNote &&
          initialReference &&
          initialReference.session_id === comparison.session_id &&
          initialReference.graph_id === path.graph_id &&
          initialReference.node_id === thought.id
        );
        const copy = document.createElement("span");
        const kind = document.createElement("span");
        kind.className = "field-note-thought-kind";
        kind.textContent = `${thought.kind.replace(/_/g, " ")} · ${thought.status}`;
        const words = document.createElement("span");
        words.textContent = thought.text;
        copy.append(kind, words);
        label.append(input, copy);
        fieldset.append(label);
      }
      form.append(fieldset);
    }

    const kinds = document.createElement("fieldset");
    kinds.className = "field-note-kinds";
    const kindsLegend = document.createElement("legend");
    kindsLegend.textContent = "note kind";
    kinds.append(kindsLegend);
    for (const [value, visible] of [
      ["conclusion", "conclusion"],
      ["unresolved_question", "unresolved question"],
      ["observation", "observation"],
    ]) {
      const label = document.createElement("label");
      const input = document.createElement("input");
      input.type = "radio";
      input.name = "field-note-kind";
      input.value = value;
      input.checked = existingNote
        ? value === existingNote.kind
        : value === "observation";
      label.append(input, document.createTextNode(visible));
      kinds.append(label);
    }
    const textLabel = document.createElement("label");
    textLabel.className = "field-note-text-label";
    textLabel.textContent = "what mattered";
    const textarea = document.createElement("textarea");
    textarea.maxLength = 4000;
    textarea.rows = 7;
    textarea.placeholder = "Write the conclusion, unresolved question, or observation in your own words.";
    textarea.value = existingNote ? existingNote.text : "";
    textLabel.append(textarea);
    const textHint = document.createElement("span");
    textHint.className = "field-note-selection-status";
    textHint.textContent = existingNote
      ? "enter saves a revision · shift+enter adds a new line · esc preserves the current revision"
      : "enter commits · shift+enter adds a new line · esc returns without writing";
    textLabel.append(textHint);
    const reviewLabel = document.createElement("div");
    reviewLabel.className = "field-note-review-label";
    reviewLabel.textContent = "selected exact thoughts";
    const actions = document.createElement("div");
    actions.className = "field-note-actions";
    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.textContent = existingNote
      ? "back without revising"
      : "back without writing";
    cancel.addEventListener("click", () => {
      if (existingNote) renderFieldNote(existingNote);
      else renderParallelComparison(comparison);
    });
    const submit = document.createElement("button");
    submit.type = "submit";
    submit.textContent = existingNote ? "Save Revision" : "Commit Field Note";
    submit.disabled = true;
    actions.append(cancel, submit);
    form.append(kinds, textLabel, reviewLabel, selectedReview, selectionStatus, actions);
    elThreadList.append(form);

    function selectedInputs() {
      return [...form.querySelectorAll('.field-note-thought input[type="checkbox"]:checked')];
    }

    function syncSelection(changed = null) {
      let selected = selectedInputs();
      if (selected.length > 12 && changed) {
        changed.checked = false;
        selected = selectedInputs();
      }
      const graphs = new Set(selected.map((item) => item.dataset.graphId));
      selectionStatus.textContent =
        `${selected.length} of 12 thoughts selected · ${graphs.size} paths represented`;
      selectedReview.replaceChildren();
      for (const input of selected) {
        const item = document.createElement("li");
        item.textContent =
          `${input.dataset.attribution} · ${input.dataset.kind} — ${input.dataset.text}`;
        selectedReview.append(item);
      }
      submit.disabled = selected.length < 2 || graphs.size < 2 || !textarea.value.trim();
    }

    form.addEventListener("change", (event) => {
      const changed = event.target instanceof HTMLInputElement && event.target.type === "checkbox"
        ? event.target
        : null;
      syncSelection(changed);
    });
    textarea.addEventListener("input", () => syncSelection());
    textarea.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" || event.shiftKey) return;
      event.preventDefault();
      if (!submit.disabled) form.requestSubmit();
    });
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const selected = selectedInputs();
      const kind = form.querySelector('input[name="field-note-kind"]:checked');
      if (!kind || selected.length < 2 || new Set(selected.map((item) => item.dataset.graphId)).size < 2) return;
      submit.disabled = true;
      selectionStatus.textContent = existingNote
        ? "appending one immutable human revision…"
        : "committing one immutable human Field Note…";
      try {
        const endpoint = existingNote
          ? `/api/field-notes/${existingNote.id}/revisions`
          : "/api/field-notes";
        const result = await post(endpoint, {
          kind: kind.value,
          text: textarea.value,
          comparison_request_id: comparison.representative_request_id,
          references: selected.map((input) => ({
            session_id: input.dataset.sessionId,
            graph_id: input.dataset.graphId,
            node_id: input.dataset.nodeId,
          })),
        });
        sound.setFieldNoteWriting(false);
        const summary = fieldNoteSummary(result.note);
        if (existingNote) {
          comparison.field_notes = (comparison.field_notes || []).map((note) =>
            note.id === summary.id ? summary : note
          );
          if (view) {
            const alreadyProjected = (view.field_notes || []).some(
              (note) => note.id === summary.id
            );
            const newlyReferencedHere = (result.note.references || []).some(
              (reference) =>
                reference.session_id === view.session_id &&
                reference.graph_id === view.graph_id &&
                reference.node_id === view.node.id
            );
            if (alreadyProjected) {
              view.field_notes = view.field_notes.map((note) =>
                note.id === summary.id ? summary : note
              );
            } else if (newlyReferencedHere) {
              view.field_notes = [...(view.field_notes || []), summary];
            }
            if (activeFieldNote && activeFieldNote.id === summary.id) {
              activeFieldNote = result.note;
              layoutFieldNote(result.note);
            } else if (alreadyProjected || newlyReferencedHere) {
              layout(view);
            }
          }
          renderFieldNote(result.note);
          return;
        }
        if (!(comparison.field_notes || []).some((note) => note.id === summary.id)) {
          comparison.field_notes = [...(comparison.field_notes || []), summary];
        }
        const anchoredHere = (result.note.references || []).some((reference) =>
          reference.session_id === view.session_id &&
          reference.graph_id === view.graph_id &&
          reference.node_id === view.node.id
        );
        if (anchoredHere) {
          closeThreadCompass(false);
          beginFieldNoteConstruction(result.note);
        } else {
          renderFieldNote(result.note);
        }
      } catch (error) {
        syncSelection();
        selectionStatus.textContent = String(error.message || error);
      }
    });
    syncSelection();
    elThreadPanel.scrollTop = 0;
    const initialInput = form.querySelector('.field-note-thought input[type="checkbox"]:checked');
    if (existingNote) textarea.focus();
    else (initialInput || form.querySelector('.field-note-thought input[type="checkbox"]'))?.focus();
  }

  async function openEligibleFieldNoteComposer() {
    const eligibility = view && view.field_note_eligibility;
    if (!eligibility || composing || busy || activeFieldNote) return;
    if (!elLegendMenu.hidden) closeLegendMenu();
    if (!elWorkspaceMenu.hidden) closeWorkspaceMenu();
    threadReturnFocus = elFieldNoteEligible;
    elThreadCompass.hidden = false;
    elThreadLatest.hidden = true;
    elThreadList.replaceChildren();
    elThreadStatus.textContent = "opening the eligible human inscription…";
    elThreadClose.focus();
    try {
      const [lineage, comparison] = await Promise.all([
        api(`/api/thread/${view.session_id}?graph=${view.graph_id}&node=${view.node.id}`),
        api(`/api/parallel/${eligibility.comparison_request_id}`),
      ]);
      if (elThreadCompass.hidden) return;
      threadLineage = lineage;
      threadComparison = comparison;
      renderFieldNoteComposer(comparison, eligibility.standing_reference);
    } catch (error) {
      sound.setFieldNoteWriting(false);
      elThreadStatus.textContent = String(error.message || error);
    }
  }

  function threadBackOrClose() {
    if (threadCapsule) {
      threadCapsule = null;
      if (threadComparison) renderParallelComparison(threadComparison);
      else if (threadLineage) renderThreadCompass(threadLineage);
      return;
    }
    if (threadComposer && threadComparison) {
      renderParallelComparison(threadComparison);
      return;
    }
    if (threadNote) {
      if (threadComparison) renderParallelComparison(threadComparison);
      else if (threadLineage) renderThreadCompass(threadLineage);
      return;
    }
    if (threadComparison && threadLineage) {
      const requestId = threadComparison.representative_request_id;
      renderThreadCompass(threadLineage, requestId);
      return;
    }
    closeThreadCompass();
  }

  async function openThreadCompass() {
    if (!view || composing || busy) return;
    if (!elLegendMenu.hidden) closeLegendMenu();
    if (!elWorkspaceMenu.hidden) closeWorkspaceMenu();
    threadReturnFocus = document.activeElement && document.activeElement !== document.body
      ? document.activeElement
      : canvas;
    elThreadCompass.hidden = false;
    elThreadLatest.hidden = true;
    elThreadList.replaceChildren();
    elThreadStatus.textContent = "reading the session lineage…";
    elThreadClose.focus();
    try {
      const lineage = await api(
        `/api/thread/${view.session_id}?graph=${view.graph_id}&node=${view.node.id}`
      );
      if (!elThreadCompass.hidden) renderThreadCompass(lineage);
    } catch (error) {
      elThreadStatus.textContent =
        "Thread Compass is unavailable from the running server · restart ta serve, then press T again";
    }
  }

  function toggleThreadCompass() {
    if (elThreadCompass.hidden) openThreadCompass();
    else closeThreadCompass();
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

  function visibleNeuronIndex(sourceMesh, excluded = new Set()) {
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
      if (excluded.has(index)) return;
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

  function disposeContinuationCircuit(circuit) {
    if (circuit) {
      const lightning = circuit.lightning;
      scene.remove(lightning.group);
      lightning.geometry.dispose();
      lightning.sparkGeometry.dispose();
      lightning.jointGeometry.dispose();
      lightning.materials.forEach((material) => material.dispose());
    }
  }

  function clearContinuationCircuit(requestId = null) {
    const ids = requestId ? [requestId] : [...continuationCircuits.keys()];
    ids.forEach((id) => {
      disposeContinuationCircuit(continuationCircuits.get(id));
      continuationCircuits.delete(id);
    });
    rememberedCircuits = requestId
      ? rememberedCircuits.filter((item) => item.requestId !== requestId)
      : [];
    saveContinuationCircuits();
    if (!continuationCircuits.size) sound.setBeam(null);
  }

  function beginContinuationCircuit(request, activity = "responding") {
    if (!request || !request.id || !standingMesh || !neuralSky) return;
    const existing = continuationCircuits.get(request.id);
    if (existing) {
      existing.targetMesh = standingMesh;
      existing.activity = activity;
      return;
    }
    const saved = rememberedCircuits.find((item) => item.requestId === request.id);
    const used = new Set(
      [...continuationCircuits.values()].map((item) => item.neuronIndex)
    );
    const retained = saved &&
      saved.requestId === request.id &&
      saved.phase === "waiting" &&
      !used.has(saved.neuronIndex) &&
      neuronAtOrAboveMesh(saved.neuronIndex, standingMesh)
      ? saved.neuronIndex
      : -1;
    const neuronIndex = retained >= 0 && retained < neuralSky.nodes.length
      ? retained
      : visibleNeuronIndex(standingMesh, used);
    if (neuronIndex < 0) return;
    const circuit = {
      requestId: request.id,
      sourceGraphId: request.graph_id || (view && view.graph_id),
      sourceNodeId: request.node_id || (view && view.node.id),
      neuronIndex,
      phase: "waiting",
      activity,
      parallel: Boolean(request.parallel),
      targetGraphId: null,
      targetNodeId: null,
      targetMesh: standingMesh,
      lightning: makeContinuationLightning(WAITING_BEAM_COLOR),
    };
    continuationCircuits.set(request.id, circuit);
    const remembered = {
      requestId: request.id,
      sourceGraphId: circuit.sourceGraphId,
      sourceNodeId: circuit.sourceNodeId,
      neuronIndex,
      phase: "waiting",
      parallel: Boolean(request.parallel),
      targetGraphId: null,
      targetNodeId: null,
    };
    rememberedCircuits = rememberedCircuits
      .filter((item) => item.requestId !== request.id)
      .concat(remembered);
    saveContinuationCircuits();
    if (continuationCircuits.size === 1) sound.setBeam("waiting", retained < 0);
  }

  function completeContinuationCircuit(requestId, mesh, arrival) {
    const circuit = requestId
      ? continuationCircuits.get(requestId)
      : [...continuationCircuits.values()].find((item) => item.phase === "waiting");
    if (!circuit || circuit.phase !== "waiting") return;
    const firstArrival = ![...continuationCircuits.values()].some(
      (item) => item.phase === "arrival"
    );
    circuit.phase = "arrival";
    circuit.targetGraphId = arrival.graphId;
    circuit.targetNodeId = arrival.nodeId;
    circuit.targetMesh = mesh;
    setContinuationLightningColor(
      circuit.lightning, NEW_PATH_SELECTION_COLOR
    );
    const remembered = {
      requestId: circuit.requestId,
      sourceGraphId: circuit.sourceGraphId,
      sourceNodeId: circuit.sourceNodeId,
      neuronIndex: circuit.neuronIndex,
      phase: "arrival",
      parallel: Boolean(circuit.parallel),
      targetGraphId: arrival.graphId,
      targetNodeId: arrival.nodeId,
    };
    rememberedCircuits = rememberedCircuits
      .filter((item) => item.requestId !== circuit.requestId)
      .concat(remembered);
    saveContinuationCircuits();
    sound.setWorking(false);
    sound.setBeam("arrival");
    if (firstArrival) sound.arrivalSplash();
  }

  function restoreArrivalCircuit(mesh, arrival) {
    const current = [...continuationCircuits.values()].find(
      (item) => item.phase === "arrival" &&
        item.targetGraphId === arrival.graphId && item.targetNodeId === arrival.nodeId
    );
    if (current) {
      current.targetMesh = mesh;
      return;
    }
    const saved = rememberedCircuits.find(
      (item) => item.phase === "arrival" &&
        item.targetGraphId === arrival.graphId && item.targetNodeId === arrival.nodeId
    );
    if (
      !saved || continuationCircuits.has(saved.requestId) ||
      saved.neuronIndex < 0 || saved.neuronIndex >= neuralSky.nodes.length
    ) return;
    const used = new Set(
      [...continuationCircuits.values()].map((item) => item.neuronIndex)
    );
    const neuronIndex = neuronAtOrAboveMesh(saved.neuronIndex, standingMesh)
      && !used.has(saved.neuronIndex)
      ? saved.neuronIndex
      : visibleNeuronIndex(standingMesh, used);
    if (neuronIndex < 0) return;
    const circuit = {
      ...saved,
      neuronIndex,
      targetMesh: mesh,
      lightning: makeContinuationLightning(NEW_PATH_SELECTION_COLOR),
    };
    continuationCircuits.set(saved.requestId, circuit);
    rememberedCircuits = rememberedCircuits.map((item) =>
      item.requestId === saved.requestId ? { ...item, neuronIndex } : item
    );
    saveContinuationCircuits();
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
    continuationCircuits.forEach((circuit) => updateOneContinuationCircuit(circuit, t));
  }

  function updateOneContinuationCircuit(circuit, t) {
    if (!circuit) return;
    const visible = Boolean(
      view &&
      view.graph_id === circuit.sourceGraphId &&
      view.node.id === circuit.sourceNodeId &&
      circuit.targetMesh &&
      circuit.targetMesh.parent
    );
    circuit.lightning.group.visible = visible;
    if (!visible) return;
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
    const strength = circuit.activity === "queued" ? 0.42 : 1;
    lightning.materials[0].opacity = strength * (0.16 + Math.abs(Math.sin(t * 11)) * 0.2);
    lightning.materials[1].opacity = strength * (0.76 + Math.abs(Math.sin(t * 19)) * 0.24);
    lightning.materials[2].opacity = strength * (0.55 + Math.abs(Math.sin(t * 13)) * 0.4);
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

  function mountFieldNoteRelic(group, { hologram, scale, placeholder, generation }) {
    const model = hologram
      ? "./assets/models/field-notes-monument-hologram.glb"
      : "./assets/models/field-notes-monument.glb";
    const mountToken = (group.userData.fieldNoteMountToken || 0) + 1;
    group.userData.fieldNoteMountToken = mountToken;
    RelicGLBLoader.load(model)
      .then((object) => {
        if (
          !group.parent ||
          generation !== layoutGeneration ||
          mountToken !== group.userData.fieldNoteMountToken
        ) return;
        if (group.userData.relicObject) group.remove(group.userData.relicObject);
        const box = new THREE.Box3().setFromObject(object);
        const size = box.getSize(new THREE.Vector3());
        const center = box.getCenter(new THREE.Vector3());
        const fit = (2.55 * scale) /
          Math.max(size.y, size.x * 0.76, size.z * 0.76, 0.001);
        object.scale.setScalar(fit);
        object.position.set(-center.x * fit, 0.38 - box.min.y * fit, -center.z * fit);
        object.userData.fieldNoteRestY = object.position.y;
        if (hologram) {
          object.traverse((part) => {
            if (!part.material) return;
            part.material.transparent = true;
            part.material.opacity = Math.min(0.72, part.material.opacity);
            part.material.depthWrite = false;
            part.material.emissiveIntensity = Math.max(
              part.material.emissiveIntensity || 0, 0.35
            );
          });
        }
        placeholder.visible = false;
        group.userData.relicObject = object;
        group.add(object);
      })
      .catch((error) => {
        placeholder.material.color.setHex(0x6b3540);
        placeholder.userData.loadError = String(error.message || error);
      });
  }

  function mountCapsuleRelic(group, { state, scale, placeholder, generation }) {
    const model = state === "constructing"
      ? "./assets/models/knowledge-ark-launcher-hologram.glb"
      : state === "launched"
        ? "./assets/models/knowledge-ark-launcher-post-launch.glb"
        : "./assets/models/knowledge-ark-launcher.glb";
    const mountToken = (group.userData.capsuleMountToken || 0) + 1;
    group.userData.capsuleMountToken = mountToken;
    RelicGLBLoader.load(model)
      .then((object) => {
        if (
          !group.parent || generation !== layoutGeneration ||
          mountToken !== group.userData.capsuleMountToken
        ) return;
        if (group.userData.relicObject) group.remove(group.userData.relicObject);
        const box = new THREE.Box3().setFromObject(object);
        const size = box.getSize(new THREE.Vector3());
        const center = box.getCenter(new THREE.Vector3());
        const fit = (3.35 * scale) /
          Math.max(size.y, size.x * 0.72, size.z * 0.72, 0.001);
        object.scale.setScalar(fit);
        object.position.set(-center.x * fit, 0.52 - box.min.y * fit, -center.z * fit);
        object.userData.capsuleRestY = object.position.y;
        if (state === "constructing") {
          object.traverse((part) => {
            if (!part.material) return;
            part.material.transparent = true;
            part.material.opacity = Math.min(0.7, part.material.opacity);
            part.material.depthWrite = false;
            part.material.emissiveIntensity = Math.max(
              part.material.emissiveIntensity || 0, 0.42
            );
          });
        }
        placeholder.visible = false;
        group.userData.relicObject = object;
        group.add(object);
      })
      .catch((error) => {
        placeholder.material.color.setHex(0x6b3540);
        placeholder.userData.loadError = String(error.message || error);
      });
  }

  function addCapsuleOrbit(group) {
    if (group.userData.capsuleOrbit) return;
    const count = 66;
    const positions = new Float32Array(count * 3);
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    const material = new THREE.PointsMaterial({
      color: 0xffa43d,
      map: neuralSky && neuralSky.glow,
      size: 0.11,
      transparent: true,
      opacity: 0.9,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    const points = new THREE.Points(geometry, material);
    points.position.y = 1.7;
    group.add(points);
    group.userData.capsuleOrbit = { points, count, dissipatingAt: null };
  }

  function capsuleLauncher(
    capsule,
    { x, z, scale = 0.82, state = capsule.state, standing = false }
  ) {
    const group = new THREE.Group();
    group.position.set(x, 0.72, z);
    group.userData = {
      capsuleId: capsule.id,
      capsule,
      capsuleState: state,
      focusScale: 1,
      ghost: false,
    };
    const terrace = new THREE.Mesh(
      new THREE.CylinderGeometry(1.72 * scale, 2.05 * scale, 0.64, 12),
      stoneMat(0x2d2418, 1)
    );
    terrace.position.y = 0.32;
    group.add(terrace);
    const placeholder = new THREE.Mesh(
      new THREE.OctahedronGeometry(0.58 * scale),
      new THREE.MeshStandardMaterial({
        color: state === "constructing" ? 0x8dc7f3 : 0xffa43d,
        emissive: state === "constructing" ? 0x315f8a : 0x8a4312,
        emissiveIntensity: 0.9,
        transparent: true,
        opacity: 0.68,
      })
    );
    placeholder.position.y = 1.8 * scale;
    group.add(placeholder);
    mountCapsuleRelic(group, {
      state,
      scale,
      placeholder,
      generation: layoutGeneration,
    });
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(1.52 * scale, 0.07, 10, 36),
      new THREE.MeshStandardMaterial({
        color: state === "launched" ? 0x9a6b42 : 0xffa43d,
        emissive: state === "launched" ? 0x382316 : 0x8a4312,
        emissiveIntensity: state === "launched" ? 0.38 : 0.95,
        metalness: 0.58,
        roughness: 0.28,
      })
    );
    ring.rotation.x = Math.PI / 2;
    ring.position.y = 0.68;
    group.add(ring);
    group.userData.capsuleRing = ring;
    const lantern = new THREE.PointLight(
      state === "launched" ? 0xb06f36 : 0xffa43d,
      state === "launched" ? 320 : 760,
      10,
      2
    );
    lantern.position.set(0, 3.1 * scale, 1.15 * scale);
    group.add(lantern);
    group.userData.capsuleLantern = lantern;
    const board = new THREE.Mesh(
      new THREE.PlaneGeometry(3.25 * scale, 1.2 * scale),
      new THREE.MeshBasicMaterial({
        map: labelTexture(
          state === "constructing"
            ? "Knowledge Capsule constructing"
            : state === "launched"
              ? "Knowledge Capsule launched"
              : "Launch Capsule",
          state === "launched"
            ? `frozen milestone ${capsule.id}`
            : `Field Note revision ${capsule.field_note_revision_id}`
        ),
        transparent: true,
      })
    );
    board.position.set(0, 3.75 * scale, 1.1 * scale);
    group.add(board);
    group.userData.capsuleBoard = board;
    group.userData.capsulePlaceholder = placeholder;
    const hit = new THREE.Mesh(
      new THREE.SphereGeometry(2.05 * scale),
      new THREE.MeshBasicMaterial({ visible: false })
    );
    hit.position.y = 1.65 * scale;
    hit.userData = { capsuleId: capsule.id };
    group.add(hit);
    capsuleTargets.push(group);
    if (state === "ready" && !standing) addCapsuleOrbit(group);
    if (!standing) {
      addClockChoice(group, {
        via: "outbound knowledge",
        kind: "knowledge_capsule",
        text: state === "launched"
          ? `spent Knowledge Ark Launcher · ${capsule.id}`
          : state === "constructing"
            ? "Knowledge Ark Launcher construction is in progress"
            : `Launch Capsule · ${capsule.id}`,
        description: state === "launched"
          ? `Knowledge Capsule launched · select to inspect ${capsule.id}`
          : state === "constructing"
            ? "Knowledge Ark Launcher construction is still in progress"
            : "Launch Capsule · write the frozen Markdown, then spend this launcher once",
        selectionColor: 0xffa43d,
        audioRole: "capsule",
        walk: () => {
          if (state === "ready") launchCapsule(capsule.id, group);
          else if (state === "launched") enterCapsule(capsule.id);
        },
      });
    }
    return group;
  }

  function addFieldNoteSwirl(group) {
    if (group.userData.fieldNoteSwirl || enteredFieldNotes.has(group.userData.fieldNoteId)) {
      return;
    }
    const count = 54;
    const positions = new Float32Array(count * 3);
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    const material = new THREE.PointsMaterial({
      color: 0xffcc72,
      size: 0.075,
      transparent: true,
      opacity: 0.88,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    const points = new THREE.Points(geometry, material);
    points.position.y = 1.3;
    group.add(points);
    group.userData.fieldNoteSwirl = {
      points,
      phases: Array.from({ length: count }, (_item, index) =>
        (index / count) * Math.PI * 2 + (index % 7) * 0.13
      ),
      count,
      dissipatingAt: null,
    };
  }

  function fieldNoteMonument(note, { x, z, scale = 0.78, constructing = false, standing = false }) {
    const group = new THREE.Group();
    group.position.set(x, 0, z);
    group.userData = {
      fieldNoteId: note.id,
      note,
      constructing,
      focusScale: 1,
      ghost: false,
    };
    const plinth = new THREE.Mesh(
      new THREE.CylinderGeometry(1.2 * scale, 1.48 * scale, 0.38, 12),
      stoneMat(0x29231b, 1)
    );
    plinth.position.y = 0.19;
    group.add(plinth);
    const placeholder = new THREE.Mesh(
      new THREE.OctahedronGeometry(0.52 * scale),
      new THREE.MeshStandardMaterial({
        color: constructing ? 0x6ca9df : 0xe2c48a,
        emissive: constructing ? 0x244e78 : 0x70461a,
        emissiveIntensity: constructing ? 0.8 : 0.45,
        transparent: true,
        opacity: 0.62,
      })
    );
    placeholder.position.y = 1.4 * scale;
    group.add(placeholder);
    mountFieldNoteRelic(group, {
      hologram: constructing,
      scale,
      placeholder,
      generation: layoutGeneration,
    });
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(1.15 * scale, 0.055, 10, 32),
      new THREE.MeshStandardMaterial({
        color: constructing ? 0x79b9ef : 0xffcc72,
        emissive: constructing ? 0x285f91 : 0x81511d,
        emissiveIntensity: constructing ? 0.95 : 0.72,
        metalness: 0.45,
        roughness: 0.3,
      })
    );
    ring.rotation.x = Math.PI / 2;
    ring.position.y = 0.42;
    group.add(ring);
    group.userData.fieldNoteRing = ring;
    const board = new THREE.Mesh(
      new THREE.PlaneGeometry(2.75 * scale, 1.3 * scale),
      new THREE.MeshBasicMaterial({
        map: labelTexture(
          constructing ? "field note constructing" : `human field note · ${note.kind_label}`,
          note.text
        ),
        transparent: true,
      })
    );
    board.position.set(0, 2.95 * scale, 0.88 * scale);
    group.add(board);
    group.userData.fieldNoteBoard = board;
    group.userData.fieldNotePlaceholder = placeholder;
    const hit = new THREE.Mesh(
      new THREE.SphereGeometry(1.75 * scale),
      new THREE.MeshBasicMaterial({ visible: false })
    );
    hit.position.y = 1.3 * scale;
    hit.userData = { fieldNoteId: note.id };
    group.add(hit);
    fieldNoteTargets.push(group);
    if (!constructing && !standing) addFieldNoteSwirl(group);
    if (!standing) {
      addClockChoice(group, {
        via: constructing ? "human inscription forming" : "human inscription",
        kind: note.kind,
        text: note.text,
        description: constructing
          ? "Field Notes Monument construction is still in progress"
          : `human Field Note · ${note.kind_label} — ${note.text}`,
        audioRole: "field-note",
        walk: () => {
          if (!group.userData.constructing) enterFieldNote(note.id, group);
        },
      });
    }
    return group;
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
    fieldNoteTargets = [];
    capsuleTargets = [];
    if (capsuleFlight) {
      scene.remove(capsuleFlight.group);
      scene.remove(capsuleFlight.trail);
      capsuleFlight = null;
    }
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

  function fieldNoteSlot(i, occupiedSideCount) {
    const firstRow = Math.ceil(occupiedSideCount / 5);
    const row = firstRow + Math.floor(i / 5);
    const offsets = [0, -1, 1, -2, 2];
    return {
      x: -(CHOICE_ROW + row * CHOICE_ROW_GAP),
      z: offsets[i % 5] * CHOICE_STRIDE,
    };
  }

  function capsuleSlot(index = 0) {
    return {
      x: CHOICE_ROW + index * CHOICE_STRIDE,
      z: -CHOICE_ROW * 1.25 - index * CHOICE_ROW_GAP,
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
    if (arrival.requestId) {
      completeContinuationCircuit(arrival.requestId, ring, arrival);
    } else if (autoFocus) {
      completeContinuationCircuit(null, ring, arrival);
    }
    const retainedArrival = rememberedCircuits.find((item) =>
      item.phase === "arrival" && item.targetGraphId === arrival.graphId &&
      item.targetNodeId === arrival.nodeId
    );
    if (retainedArrival && arrival.seen) {
      clearContinuationCircuit(retainedArrival.requestId);
    }
    else if (retainedArrival) restoreArrivalCircuit(ring, arrival);
    addClockChoice(ring, {
      via,
      kind: arrival.kind,
      text: `${companionTitle(arrival)} — ${arrival.text}`,
      description: arrival.description,
      selectionColor: arrival.returnOrigin
        ? RETURN_COLOR
        : !arrival.seen ? NEW_PATH_SELECTION_COLOR : null,
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
    activeFieldNote = null;
    activeCapsule = null;
    elEvidenceDescent.hidden = true;
    elKnowledgeCapsuleEligible.hidden = true;
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
    const fieldNotes = payload.field_notes || [];
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

    fieldNotes.forEach((note, i) => {
      const slot = fieldNoteSlot(i, sideNodes.length);
      const constructing = Boolean(
        fieldNoteConstruction && fieldNoteConstruction.id === note.id
      );
      const monument = fieldNoteMonument(note, {
        x: slot.x,
        z: slot.z,
        constructing,
      });
      root.add(monument);
      if (constructing) fieldNoteConstruction.group = monument;
      markRise(monument, 0.16 + i * 0.08);
    });

    const capsules = payload.knowledge_capsules || [];
    capsules.forEach((capsule, i) => {
      const slot = capsuleSlot(i);
      const constructing = Boolean(
        capsuleConstruction && capsuleConstruction.id === capsule.id
      );
      const state = constructing ? "constructing" : capsule.state;
      const launcher = capsuleLauncher(capsule, {
        x: slot.x,
        z: slot.z,
        state,
      });
      root.add(launcher);
      if (constructing) capsuleConstruction.group = launcher;
      markRise(launcher, 0.2 + i * 0.08);
    });
    sound.setCapsuleReady(capsules.some((item) => item.state === "ready") && !capsuleConstruction);

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
    renderFieldNoteEligibility(payload);
    renderKnowledgeCapsuleEligibility(payload);
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
      read.field_note_line,
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
      bits.push("spotlit preview");
    } else {
      const shownRelic = RELIC_BY_KEY[manualRelicKey || mappedRelicKey];
      if (shownRelic) {
        bits.push(
          manualRelicKey
            ? `relic preview: ${shownRelic.name}`
            : `form: ${shownRelic.name}`
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
      const noteCount = (payload.field_notes || []).length;
      if (noteCount) {
        bits.push(
          `${noteCount} human Field ${noteCount === 1 ? "Note monument" : "Note monuments"} in the left inscription alcove`
        );
      }
      const capsuleCount = (payload.knowledge_capsules || []).length;
      if (capsuleCount) {
        const states = payload.knowledge_capsules.map((item) => item.state);
        bits.push(states.includes("ready")
          ? "one charged Knowledge Ark Launcher waits on the rear-right terrace"
          : states.includes("launched")
            ? "one spent Knowledge Ark Launcher marks a carried milestone"
            : "one Knowledge Ark Launcher is constructing on the rear-right terrace");
      }
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
    }
    if (overhead) bits.push("overhead view");
    elMeta.textContent = bits.join("  ·  ");
    requestAnimationFrame(resize);
    applyClimate(payload.climate);
  }

  function renderFieldNoteEligibility(payload) {
    const eligibility = payload && payload.field_note_eligibility;
    const visible = Boolean(
      eligibility && !activeFieldNote && !fieldNoteConstruction
    );
    elFieldNoteEligible.hidden = !visible;
    if (!visible) {
      if (!eligibility) eligibilityKey = null;
      return;
    }
    const nextKey = [
      eligibility.comparison_request_id,
      payload.graph_id,
      payload.node.id,
    ].join(":");
    if (nextKey !== eligibilityKey) {
      eligibilityKey = nextKey;
      sound.fieldNoteEligible();
    }
  }

  function renderKnowledgeCapsuleEligibility(payload) {
    const eligibility = payload && payload.knowledge_capsule_eligibility;
    const visible = Boolean(
      eligibility && !activeFieldNote && !activeCapsule && !capsuleConstruction
    );
    elKnowledgeCapsuleEligible.hidden = !visible;
    if (!visible) {
      if (!eligibility) capsuleEligibilityKey = null;
      return;
    }
    const nextKey = `${eligibility.comparison_request_id}:${eligibility.field_note_id}`;
    capsuleEligibilityKey = nextKey;
    if (!announcedCapsuleMilestones.has(nextKey)) {
      rememberCapsuleMilestone(nextKey);
      sound.capsuleEarned();
    }
  }

  function fieldNoteSummary(note) {
    return {
      id: note.id,
      created_at: note.created_at,
      updated_at: note.updated_at || note.created_at,
      author: note.author,
      kind: note.kind,
      kind_label: note.kind_label,
      text: note.text,
      reference_count: note.reference_count,
      referenced_graph_count: note.referenced_graph_count,
      integrity: note.integrity,
      revision_count: note.revision_count || 1,
    };
  }

  function beginFieldNoteConstruction(note) {
    if (!view) return;
    const summary = fieldNoteSummary(note);
    if (!(view.field_notes || []).some((item) => item.id === note.id)) {
      view.field_notes = [...(view.field_notes || []), summary];
    }
    fieldNoteConstruction = {
      id: note.id,
      note: summary,
      startedAt: clock.getElapsedTime(),
      duration: 18,
      group: null,
    };
    sound.setFieldNoteConstruction(true);
    layout(view);
  }

  function finishFieldNoteConstruction() {
    const construction = fieldNoteConstruction;
    if (!construction) return;
    fieldNoteConstruction = null;
    sound.setFieldNoteConstruction(false);
    sound.fieldNoteComplete();
    const group = construction.group;
    if (group && group.parent) {
      group.userData.constructing = false;
      const ring = group.userData.fieldNoteRing;
      if (ring && ring.material) {
        ring.material.color.setHex(0xffcc72);
        ring.material.emissive.setHex(0x81511d);
        ring.material.emissiveIntensity = 0.72;
      }
      const board = group.userData.fieldNoteBoard;
      if (board && board.material) {
        board.material.map = labelTexture(
          `human field note · ${construction.note.kind_label}`,
          construction.note.text
        );
        board.material.needsUpdate = true;
      }
      mountFieldNoteRelic(group, {
        hologram: false,
        scale: 0.78,
        placeholder: group.userData.fieldNotePlaceholder,
        generation: layoutGeneration,
      });
      addFieldNoteSwirl(group);
      const choice = choices.find((item) => item.mesh === group);
      if (choice) {
        choice.choice.via = "human inscription";
        choice.choice.description =
          `human Field Note · ${construction.note.kind_label} — ${construction.note.text}`;
      }
    }
    if (view && !activeFieldNote) {
      renderFieldNoteEligibility(view);
      plate(view);
    }
  }

  function dissipateFieldNoteSwirl(group) {
    const swirl = group && group.userData.fieldNoteSwirl;
    if (swirl && swirl.dissipatingAt === null) {
      swirl.dissipatingAt = clock.getElapsedTime();
    }
  }

  function plateFieldNote(note) {
    elKind.textContent = `human field note — ${note.kind_label}`;
    elText.textContent = note.text;
    const revisionCount = note.revision_count || 1;
    elHere.textContent =
      `inside a durable human inscription · revision ${revisionCount} of ${revisionCount} · ${note.reference_count} exact thoughts across ${note.referenced_graph_count} paths · e reveals the selected sources`;
    elMeta.textContent = [
      `created ${note.created_at.replace("T", " ").replace("Z", " UTC")}`,
      revisionCount > 1
        ? `revised ${note.updated_at.replace("T", " ").replace("Z", " UTC")}`
        : "original inscription",
      note.integrity === "verified" ? "source integrity verified" : "source integrity failed",
      "b returns to the referenced chamber",
    ].join("  ·  ");
    requestAnimationFrame(resize);
    applyClimate(null);
  }

  function layoutFieldNote(note) {
    layoutGeneration += 1;
    elEvidenceDescent.hidden = true;
    elFieldNoteEligible.hidden = true;
    elThreshold.hidden = true;
    clearRoot();
    root.add(floor());
    const monument = fieldNoteMonument(note, {
      x: 0,
      z: 0,
      scale: 1,
      standing: true,
    });
    root.add(monument);
    standingMesh = monument;
    markRise(monument, 0);
    plateFieldNote(note);
  }

  async function enterFieldNote(noteId, monument = null) {
    if (busy || activeFieldNote || (fieldNoteConstruction && fieldNoteConstruction.id === noteId)) {
      return;
    }
    busy = true;
    try {
      const note = await api(`/api/field-notes/${noteId}`);
      sound.fieldNoteEntry();
      if (!enteredFieldNotes.has(noteId)) {
        dissipateFieldNoteSwirl(monument);
        await new Promise((resolve) => window.setTimeout(resolve, 1050));
        rememberFieldNoteEntry(noteId);
      }
      activeFieldNote = note;
      layoutFieldNote(note);
    } finally {
      busy = false;
    }
  }

  function leaveFieldNote() {
    if (!activeFieldNote) return false;
    activeFieldNote = null;
    if (view) layout(view);
    return true;
  }

  function capsuleSummary(capsule) {
    return {
      id: capsule.id,
      created_at: capsule.created_at,
      author: capsule.author,
      state: capsule.state,
      comparison_request_id: capsule.comparison_request_id,
      session_id: capsule.session_id,
      session_title: capsule.session_title,
      source_graph_id: capsule.source_graph_id,
      source_node_id: capsule.source_node_id,
      head_graph_id: capsule.head_graph_id,
      head_turn_id: capsule.head_turn_id,
      field_note_id: capsule.field_note_id,
      field_note_revision_id: capsule.field_note_revision_id,
      artifact_count: capsule.artifact_count,
      launched_at: capsule.launched_at || (capsule.launch && capsule.launch.launched_at) || null,
    };
  }

  async function constructKnowledgeCapsule() {
    const eligibility = view && view.knowledge_capsule_eligibility;
    if (!eligibility || busy || activeFieldNote || activeCapsule || capsuleConstruction) return;
    busy = true;
    elKnowledgeCapsuleEligible.disabled = true;
    try {
      const result = await post("/api/knowledge-capsules", {
        comparison_request_id: eligibility.comparison_request_id,
      });
      const capsule = capsuleSummary(result.capsule);
      view.knowledge_capsule_eligibility = null;
      view.knowledge_capsules = [...(view.knowledge_capsules || []), capsule];
      capsuleConstruction = {
        id: capsule.id,
        capsule,
        startedAt: clock.getElapsedTime(),
        duration: 18,
        group: null,
      };
      sound.setCapsuleConstruction(true);
      sound.setCapsuleReady(false);
      layout(view);
    } catch (error) {
      elKind.textContent = "Knowledge Capsule was not constructed";
      elHere.textContent = String(error.message || error);
    } finally {
      busy = false;
      elKnowledgeCapsuleEligible.disabled = false;
    }
  }

  function finishCapsuleConstruction() {
    const construction = capsuleConstruction;
    if (!construction) return;
    capsuleConstruction = null;
    sound.setCapsuleConstruction(false);
    sound.capsuleComplete();
    sound.setCapsuleReady(true);
    const capsule = construction.capsule;
    const group = construction.group;
    if (group && group.parent) {
      group.userData.capsuleState = "ready";
      const ring = group.userData.capsuleRing;
      if (ring && ring.material) {
        ring.material.color.setHex(0xffa43d);
        ring.material.emissive.setHex(0x8a4312);
        ring.material.emissiveIntensity = 0.95;
      }
      const board = group.userData.capsuleBoard;
      if (board && board.material) {
        board.material.map = labelTexture(
          "Launch Capsule",
          `Field Note revision ${capsule.field_note_revision_id}`
        );
        board.material.needsUpdate = true;
      }
      mountCapsuleRelic(group, {
        state: "ready",
        scale: 0.82,
        placeholder: group.userData.capsulePlaceholder,
        generation: layoutGeneration,
      });
      addCapsuleOrbit(group);
      const choice = choices.find((item) => item.mesh === group);
      if (choice) {
        choice.choice.text = `Launch Capsule · ${capsule.id}`;
        choice.choice.description =
          "Launch Capsule · write the frozen Markdown, then spend this launcher once";
        choice.choice.walk = () => launchCapsule(capsule.id, group);
      }
    }
    if (view && !activeCapsule) {
      renderKnowledgeCapsuleEligibility(view);
      plate(view);
    }
  }

  function beginCapsuleFlight(group) {
    if (!group || !neuralSky) return;
    const neuronIndex = visibleNeuronIndex(group);
    if (neuronIndex < 0) return;
    scene.updateMatrixWorld(true);
    const start = new THREE.Vector3();
    group.getWorldPosition(start);
    start.y += 2.25;
    const end = neuralSky.nodes[neuronIndex].clone();
    neuralSky.group.localToWorld(end);
    const flight = new THREE.Group();
    flight.position.copy(start);
    scene.add(flight);
    const placeholder = new THREE.Mesh(
      new THREE.OctahedronGeometry(0.35),
      new THREE.MeshStandardMaterial({
        color: 0xffc15a,
        emissive: 0xff7b20,
        emissiveIntensity: 2.4,
      })
    );
    flight.add(placeholder);
    RelicGLBLoader.load("./assets/models/charged-knowledge-capsule.glb")
      .then((object) => {
        if (!capsuleFlight || capsuleFlight.group !== flight) return;
        const box = new THREE.Box3().setFromObject(object);
        const size = box.getSize(new THREE.Vector3());
        const center = box.getCenter(new THREE.Vector3());
        const fit = 1.25 / Math.max(size.x, size.y, size.z, 0.001);
        object.scale.setScalar(fit);
        object.position.set(-center.x * fit, -center.y * fit, -center.z * fit);
        placeholder.visible = false;
        flight.add(object);
      });
    const flash = new THREE.PointLight(0xffa43d, 3800, 24, 2);
    flight.add(flash);
    const trailGeometry = new THREE.BufferGeometry();
    const trailPositions = new Float32Array(42 * 3);
    trailGeometry.setAttribute("position", new THREE.BufferAttribute(trailPositions, 3));
    const trail = new THREE.Points(
      trailGeometry,
      new THREE.PointsMaterial({
        color: 0xffa43d,
        map: neuralSky.glow,
        size: 0.28,
        transparent: true,
        opacity: 0.88,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      })
    );
    scene.add(trail);
    capsuleFlight = {
      group: flight,
      trail,
      trailPositions,
      points: [],
      start,
      control1: start.clone().add(new THREE.Vector3(0, 13, 0)),
      control2: end.clone().lerp(start, 0.32).add(new THREE.Vector3(8, 7, 0)),
      end,
      startedAt: clock.getElapsedTime(),
      duration: 7.0,
      flash,
    };
  }

  function spendCapsuleLauncher(group, capsule) {
    group.userData.capsuleState = "launched";
    group.userData.capsule = capsule;
    sound.setCapsuleReady(false);
    const orbit = group.userData.capsuleOrbit;
    if (orbit && orbit.dissipatingAt === null) orbit.dissipatingAt = clock.getElapsedTime();
    const lantern = group.userData.capsuleLantern;
    if (lantern) {
      lantern.color.setHex(0xb06f36);
      lantern.intensity = 320;
    }
    mountCapsuleRelic(group, {
      state: "launched",
      scale: 0.82,
      placeholder: group.userData.capsulePlaceholder,
      generation: layoutGeneration,
    });
    const board = group.userData.capsuleBoard;
    if (board && board.material) {
      board.material.map = labelTexture(
        "Knowledge Capsule launched",
        `frozen milestone ${capsule.id}`
      );
      board.material.needsUpdate = true;
    }
    const choice = choices.find((item) => item.mesh === group);
    if (choice) {
      choice.choice.text = `spent Knowledge Ark Launcher · ${capsule.id}`;
      choice.choice.description = `Knowledge Capsule launched · select to inspect ${capsule.id}`;
      choice.choice.walk = () => enterCapsule(capsule.id);
    }
  }

  async function launchCapsule(capsuleId, group) {
    if (busy || !group || group.userData.capsuleState !== "ready") return;
    busy = true;
    try {
      const result = await post(`/api/knowledge-capsules/${capsuleId}/launch`, {});
      const capsule = capsuleSummary(result.capsule);
      view.knowledge_capsules = (view.knowledge_capsules || []).map((item) =>
        item.id === capsuleId ? capsule : item
      );
      spendCapsuleLauncher(group, capsule);
      sound.capsuleLaunch();
      beginCapsuleFlight(group);
      plate(view);
    } catch (error) {
      elKind.textContent = "Knowledge Capsule launch failed";
      elHere.textContent = `${String(error.message || error)} · the launcher remains ready`;
    } finally {
      busy = false;
    }
  }

  function plateCapsule(capsule) {
    elKind.textContent = "outbound knowledge — launched Knowledge Capsule";
    elText.textContent = `Private, human-reviewed inquiry milestone ${capsule.id}`;
    elHere.textContent = [
      `session ${capsule.session_title || capsule.session_id}`,
      `comparison ${capsule.comparison_request_id}`,
      `pinned Field Note revision ${capsule.field_note_revision_id}`,
      `frozen head ${capsule.head_graph_id}/${capsule.head_turn_id}`,
    ].join(" · ");
    const path = capsule.markdown_path || (capsule.launch && capsule.launch.markdown_path) || "local Markdown path unavailable";
    elMeta.textContent = [
      capsule.launched_at ? `launched ${capsule.launched_at.replace("T", " ").replace("Z", " UTC")}` : "launch receipt present",
      `source integrity ${capsule.integrity || "not read"}`,
      `Markdown integrity ${capsule.markdown_integrity || "not read"}`,
      path,
      "b returns to the source chamber",
    ].join("  ·  ");
    requestAnimationFrame(resize);
    applyClimate(null);
  }

  function layoutCapsule(capsule) {
    layoutGeneration += 1;
    elEvidenceDescent.hidden = true;
    elFieldNoteEligible.hidden = true;
    elKnowledgeCapsuleEligible.hidden = true;
    elThreshold.hidden = true;
    sound.setCapsuleReady(false);
    clearRoot();
    root.add(floor());
    const launcher = capsuleLauncher(capsule, {
      x: 0,
      z: 0,
      scale: 1,
      state: "launched",
      standing: true,
    });
    root.add(launcher);
    standingMesh = launcher;
    markRise(launcher, 0);
    plateCapsule(capsule);
  }

  async function enterCapsule(capsuleId) {
    if (busy || activeCapsule) return;
    busy = true;
    try {
      activeCapsule = await api(`/api/knowledge-capsules/${capsuleId}`);
      layoutCapsule(activeCapsule);
    } finally {
      busy = false;
    }
  }

  function leaveCapsule() {
    if (!activeCapsule) return false;
    activeCapsule = null;
    if (view) layout(view);
    return true;
  }

  function syncParallelProgress(progress) {
    parallelProgress = progress || null;
    const anchored = Boolean(
      progress && view && progress.graph_id === view.graph_id &&
      progress.node_id === view.node.id
    );
    if (!anchored) {
      [...continuationCircuits.values()]
        .filter((item) => item.parallel && item.phase === "waiting")
        .forEach((item) => clearContinuationCircuit(item.requestId));
      return;
    }
    let addedArrival = false;
    for (const job of progress.jobs || []) {
      const previousStatus = parallelJobStates.get(job.request_id);
      const newlyCompleted = previousStatus !== undefined &&
        previousStatus !== "completed" && job.status === "completed";
      parallelJobStates.set(job.request_id, job.status);
      if (job.status === "queued" || job.status === "responding") {
        beginContinuationCircuit(
          {
            id: job.request_id,
            graph_id: progress.graph_id,
            node_id: progress.node_id,
            parallel: true,
          },
          job.status
        );
      } else if (job.status === "failed" || job.status === "canceled") {
        clearContinuationCircuit(job.request_id);
      }
      if (job.status !== "completed" || !job.arrival) continue;
      const arrival = {
        sessionId: progress.session_id,
        graphId: job.arrival.graph_id,
        nodeId: job.arrival.node_id,
        anchorGraphId: progress.graph_id,
        kind: job.arrival.node.kind,
        text: job.arrival.node.text,
        title: `${job.display_name} parallel path`,
        harness: job.harness,
        modelName: job.arrival.model && job.arrival.model.name,
        requestId: job.request_id,
        seen: !newlyCompleted,
      };
      const existing = liveArrivals.find(
        (item) => item.graphId === arrival.graphId &&
          item.nodeId === arrival.nodeId && item.anchorGraphId === arrival.anchorGraphId
      );
      const retainedUnreadCircuit = rememberedCircuits.some(
        (item) => item.requestId === job.request_id && item.phase === "arrival"
      );
      if (existing) arrival.seen = existing.seen;
      else if (retainedUnreadCircuit) arrival.seen = false;
      rememberCompanion(arrival);
      if (!existing) addedArrival = true;
    }
    if (addedArrival) arrivalsDirty = true;
    if (!elWorkspaceMenu.hidden && parallelComposerOpen) {
      renderParallelProgress(progress);
    }
  }

  function renderThreshold(payload) {
    if (activeFieldNote || activeCapsule) {
      elThreshold.hidden = true;
      return;
    }
    const traversal = (payload.read && payload.read.traversal) || {};
    if (!traversal.terminal) {
      elThreshold.hidden = true;
      sound.setWorking(false);
      requestAnimationFrame(resize);
      return;
    }
    syncParallelProgress(payload.parallel_continuation || null);
    const batch = payload.parallel_continuation || null;
    const batchLive = Boolean(batch && !batch.terminal);
    const ready = payload.continuation || null;
    if (ready) beginContinuationCircuit(ready);
    sound.setWorking(Boolean(ready || (batchLive && batch.counts.responding)));
    const attempt = payload.continuation_attempt || null;
    const harness = attempt && attempt.harness
      ? attempt.harness.charAt(0).toUpperCase() + attempt.harness.slice(1)
      : null;
    const workingLabel = "AI working…";
    elThreshold.hidden = false;
    elThreshold.dataset.ready = ready || batchLive ? "working" : "false";
    elThresholdKind.textContent = ready
      ? `${workingLabel}${harness ? ` · ${harness}` : ""}`
      : batchLive
        ? "parallel continuation"
      : "end of this graph path";
    elThresholdText.textContent = ready
      ? harness
        ? `${harness} is responding from this chamber. The new path will arrive automatically.`
        : "The continuation is queued. This chamber will update when a harness begins responding."
      : batchLive
        ? `${batch.counts.responding} responding · ${batch.counts.queued} queued · ${batch.counts.completed} completed · ${batch.counts.failed} failed · ${batch.counts.canceled} canceled`
        : traversal.state_line;
    elThresholdOrigin.disabled = Boolean(
      payload.origin && payload.origin.id === payload.node.id
    );
    elThresholdContinue.disabled = batchLive;
    elThresholdAsk.disabled = Boolean(ready || batchLive);
    elThresholdParallel.disabled = Boolean(ready || !payload.parallel_available);
    elThresholdParallel.textContent = batchLive
      ? "parallel progress · p"
      : "parallel continuation · p";
    elThresholdContinue.textContent = ready
      ? "cancel response · q"
      : batchLive ? "parallel batch in progress" : "ready for continuation · q";
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
    const enteredCircuit = [...continuationCircuits.values()].find(
      (item) => item.phase === "arrival" && item.targetGraphId === next.graphId &&
        item.targetNodeId === next.nodeId
    );
    if (enteredCircuit) clearContinuationCircuit(enteredCircuit.requestId);
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
      activeFieldNote ||
      activeCapsule ||
      composing ||
      !elWorkspaceMenu.hidden ||
      !elRelicIndex.hidden ||
      !elEvidenceDescent.hidden
    ) return;
    arrivalsDirty = false;
    revealWaitingArrivals().catch(() => {
      arrivalsDirty = true;
    });
  }

  async function revealWaitingArrivals() {
    if (!view || activeFieldNote || activeCapsule) return;
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
    if (!view) return;
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
      if (view && view.parallel_continuation) {
        await refreshContinuationState();
      }
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
      if (!added && view) {
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
    const capsuleHit = pickUserData(
      raycaster.intersectObjects(capsuleTargets, true),
      (data) => data.capsuleId
    );
    if (capsuleHit) {
      const launcher = capsuleTargets.find(
        (item) => item.userData.capsuleId === capsuleHit.capsuleId
      );
      if (launcher && launcher.userData.capsuleState === "ready") {
        launchCapsule(capsuleHit.capsuleId, launcher);
      } else if (launcher && launcher.userData.capsuleState === "launched") {
        enterCapsule(capsuleHit.capsuleId);
      }
      return;
    }
    const fieldNoteHit = pickUserData(
      raycaster.intersectObjects(fieldNoteTargets, true),
      (data) => data.fieldNoteId
    );
    if (fieldNoteHit) {
      const monument = fieldNoteTargets.find(
        (item) => item.userData.fieldNoteId === fieldNoteHit.fieldNoteId
      );
      enterFieldNote(fieldNoteHit.fieldNoteId, monument);
      return;
    }
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
    if (kind !== "continuation" && elLegendMenu.hidden) openLegendMenu();
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
    if (role === "field-note" || role === "capsule") {
      choices[focusIndex].choice.walk();
      return;
    }
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
    if (activeFieldNote) {
      elEvidenceSurfaceKind.textContent = "Field Note source selections";
      elEvidenceSurfaceSummary.textContent =
        "Exact thoughts selected by the inhabitant; this is source context, not causal evidence.";
      elStoryPath.hidden = true;
      elEvidenceSectionLabel.textContent = "selected exact thoughts · human interpretation";
      elEvidenceIntro.textContent =
        `${activeFieldNote.reference_count} selections preserved in commit order. The Field Note does not alter or rank them.`;
      elEvidenceStrata.replaceChildren();
      for (const [index, reference] of (activeFieldNote.references || []).entries()) {
        const stratum = document.createElement("article");
        stratum.className = "evidence-stratum";
        const position = document.createElement("div");
        position.className = "evidence-position";
        position.textContent = `selection ${index + 1} of ${activeFieldNote.reference_count}`;
        const heading = document.createElement("div");
        heading.className = "evidence-heading";
        const harness = reference.harness
          ? reference.harness.replace(/(^|-)([a-z])/g, (_match, dash, letter) =>
            `${dash ? " " : ""}${letter.toUpperCase()}`
          )
          : "Human or imported graph";
        heading.textContent = reference.thought
          ? `${harness} · ${reference.model.name} · ${reference.thought.kind.replace(/_/g, " ")}`
          : "referenced source unavailable";
        const summary = document.createElement("p");
        summary.className = "evidence-summary";
        summary.textContent = reference.thought
          ? reference.thought.text
          : `${reference.session_id}/${reference.graph_id}/${reference.node_id}`;
        const origin = document.createElement("div");
        origin.className = "evidence-origin";
        origin.textContent =
          `${reference.graph_id} · ${reference.node_id} · source integrity ${reference.integrity}`;
        stratum.append(position, heading, summary, origin);
        elEvidenceStrata.append(stratum);
      }
      return;
    }
    elEvidenceSurfaceKind.textContent = "archaeological record";
    elEvidenceSurfaceSummary.textContent =
      "Why the answer took this path, then what has tested it.";
    elStoryPath.hidden = false;
    elStorySectionLabel.textContent = "why this path · story graph";
    elEvidenceSectionLabel.textContent = "evidence beneath this thought";
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
  elFieldNoteEligible.addEventListener("click", openEligibleFieldNoteComposer);
  elKnowledgeCapsuleEligible.addEventListener("click", constructKnowledgeCapsule);
  elThresholdOrigin.addEventListener("click", walkOrigin);
  elThresholdContinue.addEventListener("click", toggleContinuationReady);
  elThresholdAsk.addEventListener("click", toggleContinuationComposer);
  elThresholdParallel.addEventListener("click", () => openWorkspaceMenu(true));
  elLegendTrigger.addEventListener("click", toggleLegendMenu);
  elLegendClose.addEventListener("click", closeLegendMenu);
  elLegendScrim.addEventListener("click", closeLegendMenu);
  elWorkspaceClose.addEventListener("click", closeWorkspaceMenu);
  elWorkspaceScrim.addEventListener("click", closeWorkspaceMenu);
  elWorkspaceNewToggle.addEventListener("click", () => {
    elWorkspaceNewForm.hidden = !elWorkspaceNewForm.hidden;
    elWorkspaceNewToggle.setAttribute(
      "aria-expanded", String(!elWorkspaceNewForm.hidden)
    );
    if (!elWorkspaceNewForm.hidden) elWorkspaceNewPrompt.focus();
  });
  elWorkspaceNewForm.addEventListener("submit", submitWorkspaceInquiry);
  elWorkspaceParallelForm.addEventListener("submit", submitParallelContinuation);
  elWorkspaceParallelCancel.addEventListener("click", cancelParallelContinuation);
  elThreadClose.addEventListener("click", threadBackOrClose);
  elThreadCompass.addEventListener("click", (event) => {
    if (event.target === elThreadCompass) closeThreadCompass();
  });

  function textEntryOwnsKey(target) {
    return target instanceof HTMLInputElement ||
      target instanceof HTMLTextAreaElement ||
      target instanceof HTMLSelectElement ||
      (target instanceof HTMLElement && target.isContentEditable);
  }

  window.addEventListener("keydown", (e) => {
    if (!elThreadCompass.hidden) {
      if (textEntryOwnsKey(e.target) && e.key !== "Escape") return;
      if (e.key === "Escape") {
        e.preventDefault();
        threadBackOrClose();
      } else if (e.key === "t" || e.key === "T") {
        e.preventDefault();
        closeThreadCompass();
      } else if (e.key === "l" || e.key === "L") {
        e.preventDefault();
        closeThreadCompass();
        openLegendMenu();
      } else if (e.key === "m" || e.key === "M") {
        e.preventDefault();
        closeThreadCompass();
        openWorkspaceMenu();
      }
      return;
    }
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
    if (textEntryOwnsKey(e.target) && e.key !== "Escape") return;
    if (!elWorkspaceMenu.hidden) {
      if (e.key === "Escape" || e.key === "m" || e.key === "M") {
        e.preventDefault();
        closeWorkspaceMenu();
      } else if (e.key === "l" || e.key === "L") {
        e.preventDefault();
        closeWorkspaceMenu();
        openLegendMenu();
      } else if (e.key === "t" || e.key === "T") {
        e.preventDefault();
        closeWorkspaceMenu();
        openThreadCompass();
      }
      return;
    }
    if (!elLegendMenu.hidden) {
      if (e.key === "Escape" || e.key === "l" || e.key === "L") {
        e.preventDefault();
        closeLegendMenu();
      } else if (e.key === "t" || e.key === "T") {
        e.preventDefault();
        closeLegendMenu();
        openThreadCompass();
      } else if (e.key === "m" || e.key === "M") {
        e.preventDefault();
        closeLegendMenu();
        openWorkspaceMenu();
      }
      return;
    }
    if (!elEvidenceDescent.hidden) {
      if (e.key === "Escape" || e.key === "e" || e.key === "E") {
        e.preventDefault();
        closeEvidenceDescent();
      } else if (e.key === "m" || e.key === "M") {
        e.preventDefault();
        closeEvidenceDescent();
        openWorkspaceMenu();
      }
      return;
    }
    if (!elRelicIndex.hidden) {
      if (e.key === "Escape" || e.key === "r" || e.key === "R") {
        e.preventDefault();
        closeRelicIndex();
      } else if (e.key === "m" || e.key === "M") {
        e.preventDefault();
        closeRelicIndex();
        openWorkspaceMenu();
      }
      return;
    }
    if (e.key === "t" || e.key === "T") {
      e.preventDefault();
      openThreadCompass();
      return;
    }
    if (e.key === "l" || e.key === "L") {
      e.preventDefault();
      openLegendMenu();
      return;
    }
    if (e.key === "m" || e.key === "M") {
      e.preventDefault();
      openWorkspaceMenu();
      return;
    }
    if (activeCapsule) {
      if (e.key === "Escape" || e.key === "b" || e.key === "B" || e.key === "ArrowDown") {
        e.preventDefault();
        leaveCapsule();
      }
      return;
    }
    if (activeFieldNote) {
      if (e.key === "e" || e.key === "E") {
        e.preventDefault();
        openEvidenceDescent();
        return;
      }
      if (e.key === "Escape" || e.key === "b" || e.key === "B" || e.key === "ArrowDown") {
        e.preventDefault();
        leaveFieldNote();
        return;
      }
      if (!["c", "C", "s", "S"].includes(e.key)) return;
    }
    if (e.key === "w" || e.key === "W") {
      if (view && view.field_note_eligibility) {
        e.preventDefault();
        openEligibleFieldNoteComposer();
      }
      return;
    }
    if (e.key === "k" || e.key === "K") {
      if (view && view.knowledge_capsule_eligibility) {
        e.preventDefault();
        constructKnowledgeCapsule();
      }
      return;
    }
    if (e.key === "p" || e.key === "P") {
      const traversal = view && view.read && view.read.traversal;
      if (traversal && traversal.terminal && view.parallel_available) {
        e.preventDefault();
        openWorkspaceMenu(true);
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
      const batchLive = view && view.parallel_continuation &&
        !view.parallel_continuation.terminal;
      if (traversal && traversal.terminal && !batchLive) {
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

  function updateFieldNoteAtmosphere(t) {
    if (
      fieldNoteConstruction &&
      t - fieldNoteConstruction.startedAt >= fieldNoteConstruction.duration
    ) {
      finishFieldNoteConstruction();
    }
    for (const group of fieldNoteTargets) {
      if (group.userData.constructing) {
        const relic = group.userData.relicObject;
        if (relic) {
          relic.position.y = relic.userData.fieldNoteRestY + Math.sin(t * 2.1) * 0.035;
          relic.traverse((part) => {
            if (part.material && part.material.transparent) {
              part.material.opacity = 0.5 + Math.sin(t * 3.4) * 0.14;
            }
          });
        }
      }
      const swirl = group.userData.fieldNoteSwirl;
      if (!swirl) continue;
      const dissipation = swirl.dissipatingAt === null
        ? 0
        : Math.max(0, t - swirl.dissipatingAt);
      const fade = swirl.dissipatingAt === null
        ? 1
        : Math.max(0, 1 - dissipation / 1.05);
      if (fade <= 0) {
        group.remove(swirl.points);
        delete group.userData.fieldNoteSwirl;
        continue;
      }
      const position = swirl.points.geometry.attributes.position.array;
      for (let index = 0; index < swirl.count; index += 1) {
        const phase = swirl.phases[index];
        const radius = (1.2 + (index % 9) * 0.055) * (1 + dissipation * 1.45);
        const angle = phase + t * (0.46 + (index % 5) * 0.018);
        position[index * 3] = Math.cos(angle) * radius;
        position[index * 3 + 1] =
          -0.25 + ((index * 7) % 31) * 0.085 + Math.sin(t * 1.2 + phase) * 0.16;
        position[index * 3 + 2] = Math.sin(angle) * radius * 0.72;
      }
      swirl.points.geometry.attributes.position.needsUpdate = true;
      swirl.points.material.opacity = 0.88 * fade;
      swirl.points.material.size = 0.075 + dissipation * 0.08;
    }
  }

  function updateCapsuleAtmosphere(t) {
    if (
      capsuleConstruction &&
      t - capsuleConstruction.startedAt >= capsuleConstruction.duration
    ) {
      finishCapsuleConstruction();
    }
    for (const group of capsuleTargets) {
      if (group.userData.capsuleState === "constructing") {
        const relic = group.userData.relicObject;
        if (relic) {
          relic.position.y = relic.userData.capsuleRestY + Math.sin(t * 2.35) * 0.045;
          relic.traverse((part) => {
            if (part.material && part.material.transparent) {
              part.material.opacity = 0.5 + Math.sin(t * 3.8) * 0.13;
            }
          });
        }
      }
      const orbit = group.userData.capsuleOrbit;
      if (!orbit) continue;
      const dissipation = orbit.dissipatingAt === null
        ? 0
        : Math.max(0, t - orbit.dissipatingAt);
      const fade = orbit.dissipatingAt === null
        ? 1
        : Math.max(0, 1 - dissipation / 1.1);
      if (fade <= 0) {
        group.remove(orbit.points);
        delete group.userData.capsuleOrbit;
        continue;
      }
      const positions = orbit.points.geometry.attributes.position.array;
      for (let index = 0; index < orbit.count; index += 1) {
        const band = index % 3;
        const angle = (index / orbit.count) * Math.PI * 2 + t * (0.48 + band * 0.08);
        const radius = (1.35 + (index % 11) * 0.035) * (1 + dissipation * 1.2);
        positions[index * 3] = Math.cos(angle) * radius;
        positions[index * 3 + 1] = (band - 1) * 0.42 + Math.sin(angle * 2.2) * 0.22;
        positions[index * 3 + 2] = Math.sin(angle) * radius * 0.72;
      }
      orbit.points.geometry.attributes.position.needsUpdate = true;
      orbit.points.material.opacity = 0.9 * fade;
    }

    if (!capsuleFlight) return;
    const flight = capsuleFlight;
    const u = Math.min(1, Math.max(0, (t - flight.startedAt) / flight.duration));
    const one = 1 - u;
    flight.group.position.set(0, 0, 0)
      .addScaledVector(flight.start, one * one * one)
      .addScaledVector(flight.control1, 3 * one * one * u)
      .addScaledVector(flight.control2, 3 * one * u * u)
      .addScaledVector(flight.end, u * u * u);
    flight.group.rotation.y = t * 2.8;
    flight.group.rotation.z = Math.sin(u * Math.PI) * 0.24;
    flight.flash.intensity = u < 0.12
      ? 3800 * (1 - u / 0.12)
      : u > 0.9 ? 1500 * ((u - 0.9) / 0.1) : 80;
    flight.points.unshift(flight.group.position.clone());
    flight.points = flight.points.slice(0, 42);
    for (let index = 0; index < 42; index += 1) {
      const point = flight.points[index] || flight.points[flight.points.length - 1] || flight.start;
      point.toArray(flight.trailPositions, index * 3);
    }
    flight.trail.geometry.attributes.position.needsUpdate = true;
    flight.trail.material.opacity = 0.88 * (1 - Math.max(0, u - 0.82) / 0.18);
    if (u >= 1) {
      scene.remove(flight.group);
      scene.remove(flight.trail);
      capsuleFlight = null;
    }
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
    updateFieldNoteAtmosphere(t);
    updateCapsuleAtmosphere(t);
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
