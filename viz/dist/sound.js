/* Thought Archaeology cinematic sound field. Owner-supplied cinematic OGG pack. */
(function () {
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  const toggle = document.getElementById("sound-toggle");
  const volume = document.getElementById("sound-volume");
  const volumeValue = document.getElementById("sound-volume-value");
  const STORAGE_KEY = "thought-archaeology.sound.v1";
  const AUDIO_ROOT = "./assets/audio/";

  // The supplied cues are already mastered; preserve their full spectrum.
  // Continuous layers share one effects compressor, separate from music.
  const PACK = {
    evidenceOpen: { file: "evidence-open.ogg", gain: 0.5 },
    evidenceClose: { file: "evidence-close.ogg", gain: 0.5 },
    relic: { file: "relic-inspect.ogg", gain: 0.5 },
    veto: { file: "veto-inspect.ogg", gain: 0.5 },
    fork: { file: "thread-fork.ogg", gain: 0.55 },
    cut: { file: "thread-cut.ogg", gain: 0.55 },
    cancel: { file: "cancel.ogg", gain: 0.5 },
    fieldNoteEligible: { file: "field-note-eligible.ogg", gain: 0.5 },
    sparkIdle: { file: "spark-idle.ogg", gain: 0.12 },
    sparkOpen: { file: "spark-open.ogg", gain: 0.4 },
    sparkClose: { file: "spark-close.ogg", gain: 0.4 },
    sparkClick: { file: "spark-click.ogg", gain: 0.35 },
    atmosphere: { file: "neural-atmosphere-loop.ogg", gain: 0.29, loop: true },
    cycle: { file: "object-cycle.ogg", gain: 0.253125 },
    forward: { file: "traversal-forward.ogg", gain: 0.32625 },
    back: { file: "traversal-back.ogg", gain: 0.32625 },
    redReturn: { file: "red-return-activate.ogg", gain: 0.3375 },
    blueActivate: { file: "blue-new-path-activate.ogg", gain: 0.56 },
    blueEnter: { file: "blue-new-path-enter.ogg", gain: 0.62 },
    working: { file: "ai-working-loop.ogg", gain: 0.18, loop: true },
    greenActivate: { file: "green-beam-activate.ogg", gain: 0.56 },
    greenSparks: { file: "green-beam-sparks-loop.ogg", gain: 0.16, loop: true },
    blueSplash: { file: "blue-path-complete-splash.ogg", gain: 0.66 },
    camera: { file: "camera-cycle-transition.ogg", gain: 0.253125 },
    fieldNoteWriting: { file: "field-notes-writing-loop.ogg", gain: 0.15, loop: true },
    fieldNoteConstruction: { file: "field-notes-monument-construction-loop.ogg", gain: 0.2, loop: true },
    fieldNoteComplete: { file: "field-notes-monument-complete.ogg", gain: 0.62 },
    fieldNoteEntry: { file: "field-notes-scribe-entry.ogg", gain: 0.54 },
    capsuleEarned: { file: "knowledge-capsule-launcher-earned.ogg", gain: 0.58 },
    capsuleConstruction: { file: "launcher-construction-loop.ogg", gain: 0.2, loop: true },
    capsuleComplete: { file: "launcher-build-complete.ogg", gain: 0.62 },
    capsuleReady: { file: "launcher-ready-hum-loop.ogg", gain: 0.15, loop: true },
    capsuleLaunch: { file: "charged-capsule-launch.ogg", gain: 0.7 },
  };

  let saved = {};
  try {
    saved = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "{}");
  } catch (_error) {
    saved = {};
  }

  let muted = Boolean(saved.muted);
  let level = Number.isFinite(saved.level) ? Math.max(0, Math.min(1, saved.level)) : 0.58;
  let context = null;
  let master = null;
  let ambienceBus = null;
  let cueBus = null;
  let packState = "asleep";
  let packLoad = null;
  let packError = null;
  let desiredWorking = false;
  let desiredBeam = null;
  let desiredFieldNoteWriting = false;
  let desiredFieldNoteConstruction = false;
  let desiredCapsuleConstruction = false;
  let desiredCapsuleReady = false;
  let pendingFieldNoteEligible = false;
  const buffers = new Map();
  const loopLayers = new Map();
  const pendingCues = [];

  // Fetching is allowed before a user gesture; decoding and playback begin only
  // after that gesture creates/resumes the AudioContext.
  const prefetchedPack = Promise.all(
    Object.entries(PACK).map(async ([key, item]) => {
      const response = await window.fetch(AUDIO_ROOT + item.file);
      if (!response.ok) throw new Error(`sound asset ${item.file}: ${response.status}`);
      return [key, await response.arrayBuffer()];
    })
  ).catch((error) => {
    packError = error;
    return [];
  });

  function save() {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ muted, level }));
    } catch (_error) {
      // Sound preferences remain optional browser-local state.
    }
  }

  function statusText() {
    if (!AudioContextClass) return "sound unavailable";
    if (!context) return muted ? "effects paused · s" : "effects ready · interact to awaken";
    if (packState === "loading") return muted ? "effects paused · loading" : "cinematic sound waking…";
    if (packState === "error") return "sound pack unavailable";
    return muted ? "Resume effects · S" : "Pause effects · S";
  }

  function renderControl() {
    if (!toggle || !volume) return;
    toggle.textContent = statusText();
    toggle.setAttribute("aria-pressed", muted ? "true" : "false");
    toggle.dataset.state = packState === "error"
      ? "error"
      : !context
        ? "asleep"
        : muted
          ? "muted"
          : packState === "ready"
            ? "on"
            : packState;
    volume.value = String(Math.round(level * 100));
    volume.setAttribute("aria-valuetext", `${Math.round(level * 100)} percent`);
    volume.disabled = !AudioContextClass;
    if (volumeValue) {
      volumeValue.textContent = `${Math.round(level * 100)}%${muted ? " · muted" : ""}`;
    }
  }

  function audibleLevel() {
    if (muted || level <= 0) return 0;
    return Math.pow(level, 1.3) * 1.15;
  }

  function applyMaster(fast = false) {
    if (!context || !master) return;
    const now = context.currentTime;
    master.gain.cancelScheduledValues(now);
    master.gain.setTargetAtTime(audibleLevel(), now, fast ? 0.012 : 0.06);
  }

  function connectPanned(source, destination, pan = 0) {
    if (!context.createStereoPanner || pan === 0) {
      source.connect(destination);
      return destination;
    }
    const panner = context.createStereoPanner();
    panner.pan.value = Math.max(-1, Math.min(1, pan));
    source.connect(panner).connect(destination);
    return panner;
  }

  async function ensurePack() {
    if (!context || packState === "ready") return packState === "ready";
    if (packLoad) return packLoad;
    packState = "loading";
    renderControl();
    packLoad = (async () => {
      const encoded = await prefetchedPack;
      if (packError || encoded.length !== Object.keys(PACK).length) {
        throw packError || new Error("incomplete cinematic sound pack");
      }
      await Promise.all(encoded.map(async ([key, bytes]) => {
        buffers.set(key, await context.decodeAudioData(bytes.slice(0)));
      }));
      packState = "ready";
      startLoop("atmosphere", 0.5);
      syncLayers();
      while (pendingCues.length) {
        const cue = pendingCues.shift();
        playOneShot(cue.key, cue.pan, false);
      }
      if (pendingFieldNoteEligible) playFieldNoteEligible();
      renderControl();
      return true;
    })().catch((error) => {
      packError = error;
      packState = "error";
      pendingCues.length = 0;
      renderControl();
      window.console.error("Thought Archaeology sound pack could not load", error);
      return false;
    });
    return packLoad;
  }

  function playOneShot(key, pan = 0, queue = true) {
    if (!context || muted) return;
    const item = PACK[key];
    const buffer = buffers.get(key);
    if (!item || !buffer) {
      if (queue && packState !== "error" && pendingCues.length < 8) {
        pendingCues.push({ key, pan });
        ensurePack();
      }
      return;
    }
    const source = context.createBufferSource();
    const gain = context.createGain();
    source.buffer = buffer;
    gain.gain.value = item.gain;
    source.connect(gain);
    connectPanned(gain, cueBus, pan);
    source.start();
  }

  function startLoop(key, fadeSeconds = 0.35) {
    if (!context || packState !== "ready" || loopLayers.has(key)) return;
    const item = PACK[key];
    const buffer = buffers.get(key);
    if (!item || !item.loop || !buffer) return;
    const source = context.createBufferSource();
    const gain = context.createGain();
    const now = context.currentTime;
    source.buffer = buffer;
    source.loop = true;
    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(item.gain, now + fadeSeconds);
    source.connect(gain).connect(ambienceBus);
    source.start();
    source.onended = () => {
      if (loopLayers.get(key)?.source === source) loopLayers.delete(key);
    };
    loopLayers.set(key, { source, gain });
  }

  function stopLoop(key, fadeSeconds = 0.35) {
    if (!context) return;
    const layer = loopLayers.get(key);
    if (!layer) return;
    loopLayers.delete(key);
    const now = context.currentTime;
    layer.gain.gain.cancelScheduledValues(now);
    layer.gain.gain.setTargetAtTime(0.0001, now, Math.max(0.02, fadeSeconds / 3));
    window.setTimeout(() => {
      try { layer.source.stop(); } catch (_error) { /* already stopped */ }
      layer.gain.disconnect();
    }, Math.ceil(fadeSeconds * 1000 + 120));
  }

  function syncLayers() {
    if (!context || packState !== "ready") return;
    if (desiredWorking) startLoop("working", 0.5);
    else stopLoop("working", 0.45);
    if (desiredBeam === "waiting") startLoop("greenSparks", 0.22);
    else stopLoop("greenSparks", 0.3);
    if (desiredFieldNoteWriting) startLoop("fieldNoteWriting", 0.28);
    else stopLoop("fieldNoteWriting", 0.35);
    if (desiredFieldNoteConstruction) startLoop("fieldNoteConstruction", 0.18);
    else stopLoop("fieldNoteConstruction", 0.45);
    if (desiredCapsuleConstruction) startLoop("capsuleConstruction", 0.18);
    else stopLoop("capsuleConstruction", 0.45);
    if (desiredCapsuleReady) startLoop("capsuleReady", 0.7);
    else stopLoop("capsuleReady", 0.35);
  }

  async function awaken() {
    if (!AudioContextClass) return false;
    if (!context) {
      context = new AudioContextClass();
      master = context.createGain();
      ambienceBus = context.createGain();
      cueBus = context.createGain();
      const compressor = context.createDynamicsCompressor();
      compressor.threshold.value = -18;
      compressor.knee.value = 18;
      compressor.ratio.value = 4;
      compressor.attack.value = 0.006;
      compressor.release.value = 0.28;
      ambienceBus.connect(master);
      cueBus.connect(master);
      master.connect(compressor).connect(context.destination);
      master.gain.value = 0;
    }
    if (context.state === "suspended") await context.resume();
    applyMaster();
    renderControl();
    await ensurePack();
    return packState === "ready";
  }

  function cycle(role = "story", direction = 1) {
    if (role === "return") playOneShot("redReturn", direction > 0 ? 0.2 : -0.2);
    else if (role === "new-path") playOneShot("blueActivate", direction > 0 ? 0.2 : -0.2);
    else playOneShot("cycle", direction > 0 ? 0.34 : -0.34);
  }

  function traverse(direction = "forward", role = "story") {
    if (role === "return") playOneShot("redReturn");
    else if (role === "new-path") playOneShot("blueEnter");
    else playOneShot(direction === "back" ? "back" : "forward");
  }

  function cameraShift(overhead) {
    playOneShot("camera", overhead ? 0.16 : -0.16);
  }

  function surface(kind, opening = true) {
    playOneShot(kind === "evidence" ? (opening ? "evidenceOpen" : "evidenceClose")
      : kind === "veto" ? "veto" : "relic");
  }

  function edit(kind) {
    playOneShot(kind === "fork" ? "fork" : "cut");
  }

  function setWorking(active) {
    desiredWorking = Boolean(active);
    syncLayers();
  }

  function setBeam(phase, announce = false) {
    const changed = desiredBeam !== phase;
    desiredBeam = phase || null;
    syncLayers();
    if (phase === "waiting" && announce && changed) playOneShot("greenActivate");
  }

  function arrivalSplash() {
    playOneShot("blueSplash");
  }

  function playFieldNoteEligible() {
    if (!context || muted) return;
    pendingFieldNoteEligible = false;
    playOneShot("fieldNoteEligible");
  }

  function fieldNoteEligible() {
    pendingFieldNoteEligible = true;
    if (context && packState === "ready") playFieldNoteEligible();
  }

  function setFieldNoteWriting(active) {
    desiredFieldNoteWriting = Boolean(active);
    syncLayers();
  }

  function setFieldNoteConstruction(active) {
    desiredFieldNoteConstruction = Boolean(active);
    syncLayers();
  }

  function fieldNoteComplete() {
    playOneShot("fieldNoteComplete");
  }

  function fieldNoteEntry() {
    playOneShot("fieldNoteEntry");
  }

  function capsuleEarned() {
    playOneShot("capsuleEarned");
  }

  function setCapsuleConstruction(active) {
    desiredCapsuleConstruction = Boolean(active);
    syncLayers();
  }

  function setCapsuleReady(active) {
    desiredCapsuleReady = Boolean(active);
    syncLayers();
  }

  function capsuleComplete() {
    playOneShot("capsuleComplete");
  }

  function capsuleLaunch() {
    desiredCapsuleReady = false;
    syncLayers();
    playOneShot("capsuleLaunch");
  }

  function cancel() {
    playOneShot("cancel");
  }

  function toggleMuted() {
    awaken();
    muted = !muted;
    applyMaster(true);
    save();
    renderControl();
    if (!muted && pendingFieldNoteEligible && packState === "ready") {
      playFieldNoteEligible();
    }
  }

  function setVolume(next) {
    level = Math.max(0, Math.min(1, Number(next) / 100));
    muted = level === 0;
    applyMaster(true);
    save();
    renderControl();
  }

  async function activateToggle() {
    if (!context) {
      await awaken();
      if (muted) {
        muted = false;
        applyMaster(true);
        save();
        renderControl();
      }
      return;
    }
    toggleMuted();
  }

  if (toggle) toggle.addEventListener("click", activateToggle);
  if (volume) {
    let pointerAdjusting = false;
    const setVolumeFromPointer = (event) => {
      const rect = volume.getBoundingClientRect();
      const ratio = (event.clientX - rect.left) / Math.max(1, rect.width);
      setVolume(Math.round(Math.max(0, Math.min(1, ratio)) * 100));
    };
    volume.addEventListener("input", () => {
      awaken();
      setVolume(volume.value);
    });
    volume.addEventListener("keydown", (event) => {
      const steps = {
        ArrowLeft: -1,
        ArrowDown: -1,
        ArrowRight: 1,
        ArrowUp: 1,
        PageDown: -10,
        PageUp: 10,
      };
      if (event.key === "Home" || event.key === "End") {
        event.preventDefault();
        setVolume(event.key === "Home" ? 0 : 100);
      } else if (steps[event.key]) {
        event.preventDefault();
        setVolume(Number(volume.value) + steps[event.key]);
      }
    });
    volume.addEventListener("pointerdown", (event) => {
      awaken();
      pointerAdjusting = true;
      volume.setPointerCapture(event.pointerId);
      setVolumeFromPointer(event);
      event.preventDefault();
    });
    volume.addEventListener("pointermove", (event) => {
      if (pointerAdjusting) setVolumeFromPointer(event);
    });
    volume.addEventListener("pointerup", (event) => {
      pointerAdjusting = false;
      if (volume.hasPointerCapture(event.pointerId)) volume.releasePointerCapture(event.pointerId);
    });
  }
  window.addEventListener("pointerdown", (event) => {
    if ((toggle && toggle.contains(event.target)) || (volume && volume.contains(event.target))) return;
    awaken();
  }, { once: true, capture: true });
  window.addEventListener("keydown", awaken, { once: true, capture: true });
  renderControl();

  function spark(kind) {
    if (document.hidden) return;
    playOneShot({ idle: "sparkIdle", open: "sparkOpen", close: "sparkClose", click: "sparkClick" }[kind], 0.4);
  }

  // Live expedition cues are never queued for later playback after loading/reconnect.
  function expedition(phase, attenuation, pan) {
    if (!context || muted || document.hidden || packState !== "ready") return;
    const key = phase === "charge" ? "capsuleConstruction" : "capsuleLaunch";
    const buffer = buffers.get(key);
    if (!buffer) return;
    const source = context.createBufferSource(), gain = context.createGain();
    const duration = phase === "charge" ? 1.6 : Math.min(5, buffer.duration);
    source.buffer = buffer; source.loop = phase === "charge";
    gain.gain.setValueAtTime(PACK[key].gain * Math.max(0, Math.min(1, attenuation)), context.currentTime);
    gain.gain.setTargetAtTime(.0001, context.currentTime + duration - .2, .06);
    source.connect(gain); connectPanned(gain, cueBus, pan);
    source.start(); source.stop(context.currentTime + duration);
    source.onended = () => gain.disconnect();
  }

  window.TASound = {
    expedition,
    spark,
    awaken,
    toggleMuted,
    cycle,
    traverse,
    cameraShift,
    surface,
    edit,
    setWorking,
    setBeam,
    arrivalSplash,
    fieldNoteEligible,
    setFieldNoteWriting,
    setFieldNoteConstruction,
    fieldNoteComplete,
    fieldNoteEntry,
    capsuleEarned,
    setCapsuleConstruction,
    setCapsuleReady,
    capsuleComplete,
    capsuleLaunch,
    cancel,
  };
})();
