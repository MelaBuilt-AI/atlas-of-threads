/* Thought Archaeology cinematic sound field. Original, sample-free OGG pack. */
(function () {
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  const toggle = document.getElementById("sound-toggle");
  const volume = document.getElementById("sound-volume");
  const volumeValue = document.getElementById("sound-volume-value");
  const STORAGE_KEY = "thought-archaeology.sound.v1";
  const AUDIO_ROOT = "./assets/audio/";

  // Conservative values from the sound-pack handoff. Continuous layers share
  // low-frequency energy and are routed through one master compressor. The
  // five navigation cues are 25% below the preceding submerged mix (56.25%
  // of their original gains) and use only that path; every other chamber
  // sound remains unchanged.
  const PACK = {
    atmosphere: { file: "neural-atmosphere-loop.ogg", gain: 0.29, loop: true },
    cycle: { file: "object-cycle.ogg", gain: 0.253125, submerged: true },
    forward: { file: "traversal-forward.ogg", gain: 0.32625, submerged: true },
    back: { file: "traversal-back.ogg", gain: 0.32625, submerged: true },
    redReturn: { file: "red-return-activate.ogg", gain: 0.3375, submerged: true },
    blueActivate: { file: "blue-new-path-activate.ogg", gain: 0.56 },
    blueEnter: { file: "blue-new-path-enter.ogg", gain: 0.62 },
    working: { file: "ai-working-loop.ogg", gain: 0.18, loop: true },
    greenActivate: { file: "green-beam-activate.ogg", gain: 0.56 },
    greenSparks: { file: "green-beam-sparks-loop.ogg", gain: 0.16, loop: true },
    blueSplash: { file: "blue-path-complete-splash.ogg", gain: 0.66 },
    camera: { file: "camera-cycle-transition.ogg", gain: 0.253125, submerged: true },
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
  let burstNoise = null;
  let desiredWorking = false;
  let desiredBeam = null;
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
    if (!context) return muted ? "sound muted · s" : "sound asleep · interact to awaken";
    if (packState === "loading") return muted ? "sound muted · loading" : "cinematic sound waking…";
    if (packState === "error") return "sound pack unavailable";
    return muted ? "sound muted · s" : "cinematic sound on · s";
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

  function connectSubmerged(source, destination, pan = 0) {
    const lowpass = context.createBiquadFilter();
    const dry = context.createGain();
    const firstDelay = context.createDelay(0.75);
    const firstEchoFilter = context.createBiquadFilter();
    const firstWet = context.createGain();
    const secondDelay = context.createDelay(0.75);
    const secondEchoFilter = context.createBiquadFilter();
    const secondWet = context.createGain();
    const output = context.createGain();
    lowpass.type = "lowpass";
    lowpass.frequency.value = 420;
    lowpass.Q.value = 1.3;
    dry.gain.value = 0.65;
    firstDelay.delayTime.value = 0.24;
    firstEchoFilter.type = "lowpass";
    firstEchoFilter.frequency.value = 340;
    firstWet.gain.value = 0.23;
    secondDelay.delayTime.value = 0.48;
    secondEchoFilter.type = "lowpass";
    secondEchoFilter.frequency.value = 280;
    secondWet.gain.value = 0.12;
    source.connect(lowpass);
    lowpass.connect(dry).connect(output);
    lowpass.connect(firstDelay).connect(firstEchoFilter).connect(firstWet).connect(output);
    lowpass.connect(secondDelay).connect(secondEchoFilter).connect(secondWet).connect(output);
    connectPanned(output, destination, pan);
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
    if (item.submerged) connectSubmerged(gain, cueBus, pan);
    else connectPanned(gain, cueBus, pan);
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

  // Evidence, relic inspection, cut/veto, and cancellation were useful extras
  // in the first pass but have no asset in this pack. Keep their small original
  // procedural gestures without layering the old continuous sound field.
  function makeNoiseBuffer(seconds = 1.1) {
    const frames = Math.floor(context.sampleRate * seconds);
    const buffer = context.createBuffer(1, frames, context.sampleRate);
    const data = buffer.getChannelData(0);
    let slow = 0;
    for (let i = 0; i < frames; i++) {
      slow = slow * 0.986 + (Math.random() * 2 - 1) * 0.014;
      data[i] = slow * 0.76 + (Math.random() * 2 - 1) * 0.24;
    }
    return buffer;
  }

  function tone({ from, to = from, duration = 0.25, gain = 0.035, type = "sine", pan = 0 }) {
    if (!context || muted) return;
    const now = context.currentTime;
    const oscillator = context.createOscillator();
    const envelope = context.createGain();
    oscillator.type = type;
    oscillator.frequency.setValueAtTime(Math.max(1, from), now);
    oscillator.frequency.exponentialRampToValueAtTime(Math.max(1, to), now + duration);
    envelope.gain.setValueAtTime(0.0001, now);
    envelope.gain.exponentialRampToValueAtTime(gain, now + Math.min(0.025, duration * 0.2));
    envelope.gain.exponentialRampToValueAtTime(0.0001, now + duration);
    oscillator.connect(envelope);
    connectPanned(envelope, cueBus, pan);
    oscillator.start(now);
    oscillator.stop(now + duration + 0.03);
  }

  function noiseBurst({ duration = 0.24, gain = 0.03, from = 1200, to = from, q = 3, pan = 0 } = {}) {
    if (!context || muted) return;
    const now = context.currentTime;
    const source = context.createBufferSource();
    const filter = context.createBiquadFilter();
    const envelope = context.createGain();
    if (!burstNoise) burstNoise = makeNoiseBuffer();
    source.buffer = burstNoise;
    filter.type = "bandpass";
    filter.Q.value = q;
    filter.frequency.setValueAtTime(Math.max(20, from), now);
    filter.frequency.exponentialRampToValueAtTime(Math.max(20, to), now + duration);
    envelope.gain.setValueAtTime(0.0001, now);
    envelope.gain.exponentialRampToValueAtTime(gain, now + Math.min(0.018, duration * 0.18));
    envelope.gain.exponentialRampToValueAtTime(0.0001, now + duration);
    source.connect(filter).connect(envelope);
    connectPanned(envelope, cueBus, pan);
    source.start(now, Math.random() * Math.max(0.01, 1 - duration));
    source.stop(now + duration + 0.04);
  }

  function surface(kind, opening = true) {
    if (kind === "evidence") {
      noiseBurst({ duration: 0.34, gain: 0.028, from: opening ? 760 : 120, to: opening ? 92 : 1800, q: 3.5 });
    } else {
      noiseBurst({ duration: 0.2, gain: 0.027, from: 1650, to: 480, q: 6, pan: kind === "veto" ? -0.2 : 0.2 });
    }
  }

  function edit(kind) {
    noiseBurst({ duration: 0.4, gain: 0.045, from: kind === "fork" ? 2100 : 720, to: 78, q: 7, pan: kind === "fork" ? 0.3 : -0.25 });
    tone({ from: kind === "fork" ? 112 : 97, to: 38, duration: 0.46, gain: 0.04, type: "square" });
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

  function cancel() {
    noiseBurst({ duration: 0.4, gain: 0.038, from: 1300, to: 64, q: 2.3 });
    tone({ from: 91, to: 27, duration: 0.45, gain: 0.032, type: "triangle" });
  }

  function toggleMuted() {
    awaken();
    muted = !muted;
    applyMaster(true);
    save();
    renderControl();
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

  window.TASound = {
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
    cancel,
  };
})();
