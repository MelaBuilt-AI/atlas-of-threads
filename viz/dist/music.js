/* Atlas album and browser-local music player. One streaming element, no uploads. */
(function () {
  const controls = document.getElementById("music-controls");
  const audio = document.getElementById("atlas-music");
  const toggle = document.getElementById("music-toggle");
  const tracks = document.getElementById("music-track");
  const volume = document.getElementById("music-volume");
  const status = document.getElementById("music-status");
  const sourceLabel = document.getElementById("music-source");
  const files = document.getElementById("music-files");
  const folder = document.getElementById("music-folder");
  const STORAGE_KEY = "atlas.music.v1";
  const ALBUM = [
    ["01-atlas-of-threads-title", "Atlas of Threads — Main Title"],
    ["02-the-cartographer-of-dreams", "The Cartographer of Dreams"],
    ["03-lanterns-between-ideas", "Lanterns Between Ideas"],
    ["04-the-whispering-stacks", "The Whispering Stacks"],
    ["05-a-doorway-that-remembers", "A Doorway That Remembers"],
    ["06-sparks-with-secrets", "Sparks with Secrets"],
    ["07-the-blue-unwritten", "The Blue Unwritten"],
    ["08-green-filament", "Green Filament"],
    ["09-ink-becomes-stone", "Ink Becomes Stone"],
    ["10-the-violet-return", "The Violet Return"],
    ["11-the-loom-beneath", "The Loom Beneath"],
    ["12-capsule-of-small-infinities", "Capsule of Small Infinities"],
    ["13-where-the-threads-begin-again", "Where the Threads Begin Again"],
  ].map(([file, title]) => ({ src: `./assets/audio/music/${file}.ogg`, title }));

  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}") || {}; } catch (_) { /* optional */ }
  // Each fresh Atlas launch welcomes the listener; pause lasts for this tab.
  let paused = false;
  let queue = ALBUM;
  let index = 0;
  let waitingForGesture = false;
  let playVersion = 0;
  let importVersion = 0;
  let objectURLs = [];
  let currentThreadwalk = null;
  audio.volume = Number.isFinite(saved.volume) ? Math.max(0, Math.min(1, saved.volume)) : 0.38;
  volume.value = String(Math.round(audio.volume * 100));

  function save() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify({ volume: audio.volume })); } catch (_) { /* optional */ }
  }

  function render() {
    toggle.textContent = paused || waitingForGesture ? "Play music" : "Pause music";
    toggle.setAttribute("aria-pressed", String(!paused && !waitingForGesture));
    document.querySelectorAll("[data-open-audio]").forEach((button) => {
      button.title = waitingForGesture ? "Click to start music and open audio controls" : "Open music and sound controls";
    });
    const startupHint = document.getElementById("startup-music-status");
    if (startupHint) {
      startupHint.hidden = !waitingForGesture;
      startupHint.textContent = waitingForGesture ? "Click anywhere to start the music" : "";
    }
    tracks.value = String(index);
    document.getElementById("music-volume-value").textContent = `${Math.round(audio.volume * 100)}%`;
  }

  async function play() {
    if (paused) return;
    const version = ++playVersion;
    try {
      await audio.play();
      if (version !== playVersion) return;
      waitingForGesture = false;
      status.textContent = "Playing";
    } catch (error) {
      if (version !== playVersion || error.name === "AbortError") return;
      waitingForGesture = error.name === "NotAllowedError";
      if (waitingForGesture) status.textContent = "Music starts with your first click or key press.";
      else {
        paused = true;
        status.textContent = "This track could not play. Try another track or file.";
      }
    }
    render();
  }

  function select(next) {
    ++playVersion;
    audio.pause();
    index = (next + queue.length) % queue.length;
    audio.autoplay = !paused;
    audio.src = queue[index].src;
    status.textContent = paused ? "Paused" : "Loading…";
    render();
    if (!paused) play();
  }

  function setQueue(next, label) {
    queue = next;
    sourceLabel.textContent = label;
    tracks.replaceChildren();
    queue.forEach((track, i) => {
      const option = document.createElement("option");
      option.value = String(i);
      option.textContent = `${i + 1} · ${track.title}`;
      tracks.append(option);
    });
    select(0);
  }

  function releaseFiles() {
    objectURLs.forEach((url) => URL.revokeObjectURL(url));
    objectURLs = [];
  }

  const isPlaylist = (name) => /\.(m3u8?|pls)$/i.test(name);
  const isAudio = (file) => file.type.startsWith("audio/") || /\.(mp3|ogg|oga|opus|wav|flac|m4a|aac|mp4|webm)$/i.test(file.name);
  const normalize = (path) => path.replace(/\\/g, "/").replace(/^\.\//, "");
  const basename = (path) => normalize(path).split("/").pop();

  function playlistEntries(text, name) {
    const lines = text.replace(/^\uFEFF/, "").split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
    if (/\.pls$/i.test(name)) {
      const entries = new Map();
      for (const line of lines) {
        const match = /^(File|Title)(\d+)=(.*)$/i.exec(line);
        if (!match) continue;
        const entry = entries.get(Number(match[2])) || {};
        entry[match[1].toLowerCase()] = match[3];
        entries.set(Number(match[2]), entry);
      }
      return [...entries].sort((a, b) => a[0] - b[0]).map(([, entry]) => ({ path: entry.file, title: entry.title })).filter((entry) => entry.path);
    }
    let title = "";
    const entries = [];
    for (const line of lines) {
      if (line.startsWith("#EXTINF:")) title = line.slice(line.indexOf(",") + 1);
      else if (!line.startsWith("#")) { entries.push({ path: line, title }); title = ""; }
    }
    return entries;
  }

  async function importFiles(selected) {
    const version = ++importVersion;
    const playlist = selected.find((file) => isPlaylist(file.name));
    const songs = selected.filter(isAudio);
    const urls = new Map();
    const localTrack = (file, title) => {
      if (!urls.has(file)) urls.set(file, URL.createObjectURL(file));
      return { src: urls.get(file), title: title || file.name.replace(/\.[^.]+$/, "") };
    };
    let next = [];
    let missing = 0;
    try {
      if (playlist) {
        const entries = playlistEntries(await playlist.text(), playlist.name);
        const parent = normalize(playlist.webkitRelativePath || playlist.name).replace(/[^/]+$/, "");
        for (const entry of entries) {
          let path = normalize(entry.path);
          try { path = decodeURIComponent(path); } catch (_) { /* literal filename */ }
          const relative = parent + path;
          let file = songs.find((song) => normalize(song.webkitRelativePath || song.name) === relative);
          if (!file) {
            const matches = songs.filter((song) => song.name === basename(path));
            if (matches.length === 1) file = matches[0];
          }
          if (file) next.push(localTrack(file, entry.title));
          else if (/^https?:\/\//i.test(entry.path)) next.push({ src: entry.path, title: entry.title || basename(path) });
          else missing += 1;
        }
      } else next = songs.map((file) => localTrack(file));
      if (version !== importVersion) { urls.forEach((url) => URL.revokeObjectURL(url)); return; }
      if (!next.length) {
        urls.forEach((url) => URL.revokeObjectURL(url));
        document.getElementById("music-import-status").textContent = "No playable tracks found. Select the playlist and its audio files together, or load their folder.";
        return;
      }
      const oldURLs = objectURLs;
      objectURLs = [...urls.values()];
      setQueue(next, playlist ? playlist.name : "Your music");
      oldURLs.forEach((url) => URL.revokeObjectURL(url));
      document.getElementById("music-import-status").textContent = `${next.length} tracks loaded${missing ? ` · ${missing} missing local files skipped` : ""}.`;
    } catch (_) {
      urls.forEach((url) => URL.revokeObjectURL(url));
      document.getElementById("music-import-status").textContent = "Could not read this playlist. Choose an M3U or PLS file with its music files.";
    }
  }

  toggle.addEventListener("click", () => {
    paused = waitingForGesture ? false : !paused;
    waitingForGesture = false;
    if (paused) { ++playVersion; audio.autoplay = false; audio.pause(); status.textContent = "Paused"; }
    else play();
    save();
    render();
  });
  document.getElementById("music-previous").addEventListener("click", () => select(index - 1));
  document.getElementById("music-next").addEventListener("click", () => select(index + 1));
  tracks.addEventListener("change", () => select(Number(tracks.value)));
  audio.addEventListener("ended", () => { if (!paused) select(index + 1); });
  audio.addEventListener("error", () => {
    ++playVersion;
    paused = true;
    waitingForGesture = false;
    status.textContent = "This track could not play. Try another track or file.";
    render();
  });
  volume.addEventListener("input", () => { audio.volume = Number(volume.value) / 100; save(); render(); });
  document.getElementById("music-load").addEventListener("click", () => files.click());
  document.getElementById("music-load-folder").addEventListener("click", () => folder.click());
  for (const input of [files, folder]) input.addEventListener("change", () => {
    if (input.files.length) importFiles([...input.files]);
    input.value = "";
  });
  document.getElementById("music-album").addEventListener("click", () => {
    ++importVersion;
    setQueue(ALBUM, "The Unwritten Atlas · 13 tracks");
    releaseFiles();
    document.getElementById("music-import-status").textContent = "";
  });
  function awaken(event) {
    if (paused || !audio.paused || controls.contains(event.target)) return;
    play();
  }
  // Click works for touch activation too, and retries if pointerdown was too early.
  window.addEventListener("pointerdown", awaken, { capture: true });
  window.addEventListener("click", awaken, { capture: true });
  window.addEventListener("keydown", awaken, { capture: true });
  window.TAMusic = {
    enterThreadwalk(sessionId, resuming = false) {
      if (sessionId === currentThreadwalk && !resuming) return;
      currentThreadwalk = sessionId;
      // Pick another starting point, then keep the listener's playlist order.
      const offset = queue.length > 1 ? 1 + Math.floor(Math.random() * (queue.length - 1)) : 0;
      select(index + offset);
    },
  };
  setQueue(ALBUM, "The Unwritten Atlas · 13 tracks");
})();
