/* Thought Archaeology procedural sound field. No sampled or stock audio. */
(function () {
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  const toggle = document.getElementById("sound-toggle");
  const volume = document.getElementById("sound-volume");
  const volumeValue = document.getElementById("sound-volume-value");
  const STORAGE_KEY = "thought-archaeology.sound.v1";

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
  let ambienceStarted = false;
  let workingLayer = null;
  let beamLayer = null;
  let desiredWorking = false;
  let desiredBeam = null;
  let neuralTimer = null;
  let sparkTimer = null;
  let burstNoise = null;

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
    return muted ? "sound muted · s" : "sound on · s";
  }

  function renderControl() {
    if (!toggle || !volume) return;
    toggle.textContent = statusText();
    toggle.setAttribute("aria-pressed", muted ? "true" : "false");
    toggle.dataset.state = !context ? "asleep" : muted ? "muted" : "on";
    volume.value = String(Math.round(level * 100));
    volume.setAttribute("aria-valuetext", `${Math.round(level * 100)} percent`);
    volume.disabled = !AudioContextClass;
    if (volumeValue) {
      volumeValue.textContent = `${Math.round(level * 100)}%${muted ? " · muted" : ""}`;
    }
  }

  function audibleLevel() {
    if (muted || level <= 0) return 0;
    return Math.pow(level, 1.35) * 1.75;
  }

  function applyMaster(fast = false) {
    if (!context || !master) return;
    const now = context.currentTime;
    master.gain.cancelScheduledValues(now);
    master.gain.setTargetAtTime(audibleLevel(), now, fast ? 0.012 : 0.06);
  }

  function makeNoiseBuffer(seconds = 2.8) {
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

  function connectPanned(source, destination, pan = 0) {
    if (!context.createStereoPanner) {
      source.connect(destination);
      return destination;
    }
    const panner = context.createStereoPanner();
    panner.pan.value = Math.max(-1, Math.min(1, pan));
    source.connect(panner).connect(destination);
    return panner;
  }

  function tone({
    from,
    to = from,
    duration = 0.25,
    gain = 0.08,
    type = "sine",
    pan = 0,
    delay = 0,
  }) {
    if (!context || muted) return;
    const now = context.currentTime + delay;
    const oscillator = context.createOscillator();
    const envelope = context.createGain();
    oscillator.type = type;
    oscillator.frequency.setValueAtTime(Math.max(1, from), now);
    oscillator.frequency.exponentialRampToValueAtTime(Math.max(1, to), now + duration);
    envelope.gain.setValueAtTime(0.0001, now);
    envelope.gain.exponentialRampToValueAtTime(gain, now + Math.min(0.035, duration * 0.2));
    envelope.gain.exponentialRampToValueAtTime(0.0001, now + duration);
    oscillator.connect(envelope);
    connectPanned(envelope, cueBus, pan);
    oscillator.start(now);
    oscillator.stop(now + duration + 0.03);
  }

  function noiseBurst({
    duration = 0.18,
    gain = 0.06,
    from = 1200,
    to = from,
    type = "bandpass",
    q = 3,
    pan = 0,
    delay = 0,
  } = {}) {
    if (!context || muted) return;
    const now = context.currentTime + delay;
    const source = context.createBufferSource();
    const filter = context.createBiquadFilter();
    const envelope = context.createGain();
    if (!burstNoise) burstNoise = makeNoiseBuffer(1.1);
    source.buffer = burstNoise;
    filter.type = type;
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

  function stopLayer(layer, seconds = 0.35) {
    if (!layer || !context) return;
    const now = context.currentTime;
    layer.gain.gain.cancelScheduledValues(now);
    layer.gain.gain.setTargetAtTime(0.0001, now, Math.max(0.02, seconds / 3));
    window.setTimeout(() => {
      layer.nodes.forEach((node) => {
        try { node.stop(); } catch (_error) { /* already stopped */ }
      });
      layer.gain.disconnect();
    }, Math.ceil(seconds * 1000 + 120));
  }

  function startAmbience() {
    if (!context || ambienceStarted) return;
    ambienceStarted = true;
    const bed = context.createGain();
    const bedFilter = context.createBiquadFilter();
    bed.gain.value = 0.22;
    bedFilter.type = "lowpass";
    bedFilter.frequency.value = 310;
    bedFilter.Q.value = 0.7;
    bed.connect(bedFilter).connect(ambienceBus);

    [36.4, 43.1, 57.7].forEach((frequency, index) => {
      const oscillator = context.createOscillator();
      const voice = context.createGain();
      const drift = context.createOscillator();
      const driftDepth = context.createGain();
      oscillator.type = index === 1 ? "triangle" : "sine";
      oscillator.frequency.value = frequency;
      voice.gain.value = [0.42, 0.24, 0.13][index];
      drift.frequency.value = [0.017, 0.023, 0.031][index];
      driftDepth.gain.value = [0.9, 1.3, 1.7][index];
      drift.connect(driftDepth).connect(oscillator.detune);
      oscillator.connect(voice).connect(bed);
      oscillator.start();
      drift.start();
    });

    const air = context.createBufferSource();
    const airFilter = context.createBiquadFilter();
    const airGain = context.createGain();
    const airDrift = context.createOscillator();
    const airDepth = context.createGain();
    air.buffer = makeNoiseBuffer(5.3);
    air.loop = true;
    airFilter.type = "bandpass";
    airFilter.frequency.value = 680;
    airFilter.Q.value = 0.34;
    airGain.gain.value = 0.055;
    airDrift.frequency.value = 0.041;
    airDepth.gain.value = 260;
    airDrift.connect(airDepth).connect(airFilter.frequency);
    air.connect(airFilter).connect(airGain).connect(ambienceBus);
    air.start();
    airDrift.start();
    scheduleNeuralPulse();
  }

  function scheduleNeuralPulse() {
    window.clearTimeout(neuralTimer);
    neuralTimer = window.setTimeout(() => {
      if (context && context.state === "running" && !muted) {
        const pan = Math.random() * 1.5 - 0.75;
        noiseBurst({
          duration: 0.23,
          gain: 0.014,
          from: 260 + Math.random() * 480,
          to: 90 + Math.random() * 180,
          q: 5.4,
          pan,
        });
        tone({
          from: 52 + Math.random() * 32,
          to: 31 + Math.random() * 14,
          duration: 0.48,
          gain: 0.012,
          type: "triangle",
          pan: -pan * 0.6,
        });
      }
      scheduleNeuralPulse();
    }, 1800 + Math.random() * 4300);
  }

  function startWorkingLayer() {
    if (!context || workingLayer) return;
    const layerGain = context.createGain();
    const noise = context.createBufferSource();
    const filter = context.createBiquadFilter();
    const scan = context.createOscillator();
    const scanDepth = context.createGain();
    const carrier = context.createOscillator();
    const carrierGain = context.createGain();
    layerGain.gain.setValueAtTime(0.0001, context.currentTime);
    layerGain.gain.exponentialRampToValueAtTime(0.16, context.currentTime + 0.9);
    layerGain.connect(ambienceBus);
    noise.buffer = makeNoiseBuffer(3.7);
    noise.loop = true;
    filter.type = "bandpass";
    filter.frequency.value = 520;
    filter.Q.value = 4.8;
    scan.frequency.value = 0.19;
    scanDepth.gain.value = 360;
    scan.connect(scanDepth).connect(filter.frequency);
    noise.connect(filter).connect(layerGain);
    carrier.type = "sawtooth";
    carrier.frequency.value = 31.7;
    carrierGain.gain.value = 0.1;
    carrier.connect(carrierGain).connect(layerGain);
    [noise, scan, carrier].forEach((node) => node.start());
    workingLayer = { gain: layerGain, nodes: [noise, scan, carrier] };
  }

  function startBeamLayer(phase) {
    if (!context) return;
    const layerGain = context.createGain();
    const noise = context.createBufferSource();
    const filter = context.createBiquadFilter();
    const hum = context.createOscillator();
    const humGain = context.createGain();
    const tremolo = context.createOscillator();
    const tremoloDepth = context.createGain();
    layerGain.gain.setValueAtTime(0.0001, context.currentTime);
    layerGain.gain.exponentialRampToValueAtTime(
      phase === "waiting" ? 0.13 : 0.1,
      context.currentTime + 0.18
    );
    layerGain.connect(ambienceBus);
    noise.buffer = makeNoiseBuffer(2.3);
    noise.loop = true;
    filter.type = "bandpass";
    filter.frequency.value = phase === "waiting" ? 1900 : 2850;
    filter.Q.value = phase === "waiting" ? 2.8 : 4.1;
    noise.connect(filter).connect(layerGain);
    hum.type = phase === "waiting" ? "sawtooth" : "triangle";
    hum.frequency.value = phase === "waiting" ? 73.6 : 112.3;
    humGain.gain.value = phase === "waiting" ? 0.11 : 0.07;
    hum.connect(humGain).connect(layerGain);
    tremolo.frequency.value = phase === "waiting" ? 8.7 : 12.4;
    tremoloDepth.gain.value = phase === "waiting" ? 0.018 : 0.012;
    tremolo.connect(tremoloDepth).connect(layerGain.gain);
    [noise, hum, tremolo].forEach((node) => node.start());
    beamLayer = { gain: layerGain, nodes: [noise, hum, tremolo], phase };
    scheduleSpark();
  }

  function scheduleSpark() {
    window.clearTimeout(sparkTimer);
    if (!desiredBeam) return;
    sparkTimer = window.setTimeout(() => {
      if (context && !muted && desiredBeam) {
        const blue = desiredBeam === "arrival";
        noiseBurst({
          duration: 0.025 + Math.random() * 0.055,
          gain: blue ? 0.018 : 0.023,
          from: blue ? 3100 + Math.random() * 2200 : 1700 + Math.random() * 2800,
          to: blue ? 1250 : 760,
          q: 7 + Math.random() * 6,
          pan: Math.random() * 1.6 - 0.8,
        });
      }
      scheduleSpark();
    }, 75 + Math.random() * 240);
  }

  function syncLayers() {
    if (!context) return;
    if (desiredWorking && !workingLayer) startWorkingLayer();
    if (!desiredWorking && workingLayer) {
      stopLayer(workingLayer, 0.65);
      workingLayer = null;
    }
    if (beamLayer && beamLayer.phase !== desiredBeam) {
      stopLayer(beamLayer, 0.18);
      beamLayer = null;
    }
    if (desiredBeam && !beamLayer) startBeamLayer(desiredBeam);
    if (!desiredBeam) window.clearTimeout(sparkTimer);
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
      ambienceBus.gain.value = 1.35;
      cueBus.gain.value = 1.65;
      ambienceBus.connect(master);
      cueBus.connect(master);
      master.connect(compressor).connect(context.destination);
      master.gain.value = 0;
      startAmbience();
      syncLayers();
    }
    if (context.state === "suspended") await context.resume();
    applyMaster();
    renderControl();
    return true;
  }

  function cycle(role = "story", direction = 1) {
    if (!context || muted) return;
    const pan = direction > 0 ? 0.42 : -0.42;
    if (role === "return") {
      tone({ from: 128, to: 54, duration: 0.31, gain: 0.075, type: "sawtooth", pan });
      noiseBurst({ duration: 0.2, gain: 0.04, from: 480, to: 110, q: 6, pan: -pan });
      return;
    }
    if (role === "new-path") {
      tone({ from: 164, to: 391, duration: 0.26, gain: 0.06, type: "triangle", pan });
      noiseBurst({ duration: 0.17, gain: 0.028, from: 1900, to: 3900, q: 9, pan: -pan });
      return;
    }
    const base = role === "rejected" ? 91 : role === "fork" ? 118 : 146;
    noiseBurst({ duration: 0.09, gain: 0.028, from: base * 8, to: base * 3.1, q: 8, pan });
    tone({ from: base * 1.03, to: base * 0.79, duration: 0.12, gain: 0.025, type: "triangle", pan: -pan * 0.35 });
  }

  function traverse(direction = "forward", role = "story") {
    if (!context || muted) return;
    if (role === "return") {
      noiseBurst({ duration: 0.7, gain: 0.09, from: 920, to: 68, type: "lowpass", q: 2.4 });
      tone({ from: 116, to: 29, duration: 0.82, gain: 0.085, type: "sawtooth" });
      tone({ from: 71, to: 42, duration: 0.66, gain: 0.055, type: "triangle", pan: -0.45, delay: 0.08 });
      return;
    }
    if (role === "new-path") {
      noiseBurst({ duration: 0.56, gain: 0.075, from: 860, to: 5400, q: 5.5 });
      tone({ from: 84, to: 286, duration: 0.62, gain: 0.07, type: "triangle", pan: 0.28 });
      tone({ from: 139, to: 512, duration: 0.54, gain: 0.04, type: "sine", pan: -0.32, delay: 0.06 });
      return;
    }
    const back = direction === "back";
    noiseBurst({
      duration: back ? 0.5 : 0.43,
      gain: 0.063,
      from: back ? 1700 : 240,
      to: back ? 130 : 2600,
      q: back ? 2.8 : 3.8,
      pan: back ? -0.24 : 0.22,
    });
    tone({
      from: back ? 174 : 61,
      to: back ? 48 : 183,
      duration: back ? 0.58 : 0.47,
      gain: 0.055,
      type: back ? "sawtooth" : "triangle",
      pan: back ? 0.25 : -0.2,
    });
  }

  function cameraShift(overhead) {
    if (!context || muted) return;
    noiseBurst({
      duration: 0.48,
      gain: 0.052,
      from: overhead ? 290 : 2300,
      to: overhead ? 2800 : 180,
      q: 2.1,
      pan: overhead ? 0.36 : -0.36,
    });
    tone({
      from: overhead ? 46 : 214,
      to: overhead ? 192 : 51,
      duration: 0.52,
      gain: 0.042,
      type: "triangle",
      pan: overhead ? -0.3 : 0.3,
    });
  }

  function surface(kind, opening = true) {
    if (!context || muted) return;
    const down = kind === "evidence";
    const fracture = kind === "fork" || kind === "veto";
    noiseBurst({
      duration: fracture ? 0.21 : 0.36,
      gain: fracture ? 0.045 : 0.032,
      from: down && opening ? 760 : 1750,
      to: down && opening ? 92 : opening ? 520 : 2100,
      q: fracture ? 9 : 3.5,
      pan: kind === "veto" ? -0.25 : kind === "fork" ? 0.25 : 0,
    });
    if (fracture) {
      tone({ from: kind === "veto" ? 83 : 112, to: 47, duration: 0.28, gain: 0.035, type: "square" });
    }
  }

  function edit(kind) {
    if (!context || muted) return;
    if (kind === "fork") {
      noiseBurst({ duration: 0.42, gain: 0.075, from: 2100, to: 96, q: 11, pan: 0.35 });
      noiseBurst({ duration: 0.3, gain: 0.04, from: 3800, to: 170, q: 13, pan: -0.35, delay: 0.08 });
    } else {
      tone({ from: 97, to: 38, duration: 0.52, gain: 0.072, type: "square", pan: -0.24 });
      noiseBurst({ duration: 0.46, gain: 0.055, from: 720, to: 78, q: 5, pan: 0.28 });
    }
  }

  function setWorking(active) {
    desiredWorking = Boolean(active);
    syncLayers();
  }

  function setBeam(phase, announce = false) {
    const changed = desiredBeam !== phase;
    desiredBeam = phase || null;
    syncLayers();
    if (!context || muted || !announce || !changed) return;
    if (phase === "waiting") {
      noiseBurst({ duration: 0.36, gain: 0.08, from: 170, to: 4100, q: 6.5 });
      tone({ from: 41, to: 104, duration: 0.48, gain: 0.055, type: "sawtooth", pan: 0.18 });
    }
  }

  function arrivalSplash() {
    if (!context || muted) return;
    noiseBurst({ duration: 0.72, gain: 0.105, from: 6100, to: 740, q: 4.2 });
    noiseBurst({ duration: 0.45, gain: 0.064, from: 920, to: 4200, q: 8.5, pan: 0.4, delay: 0.05 });
    tone({ from: 47, to: 238, duration: 0.74, gain: 0.08, type: "sawtooth", pan: -0.3 });
    tone({ from: 151, to: 427, duration: 0.58, gain: 0.052, type: "triangle", pan: 0.32, delay: 0.09 });
  }

  function cancel() {
    if (!context || muted) return;
    noiseBurst({ duration: 0.42, gain: 0.055, from: 1300, to: 64, q: 2.3 });
    tone({ from: 91, to: 27, duration: 0.48, gain: 0.045, type: "triangle" });
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
      if (volume.hasPointerCapture(event.pointerId)) {
        volume.releasePointerCapture(event.pointerId);
      }
    });
  }
  window.addEventListener("pointerdown", (event) => {
    if (
      (toggle && toggle.contains(event.target)) ||
      (volume && volume.contains(event.target))
    ) return;
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
