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
    next = null,
    scene,
    camera,
    renderer,
    weave,
    transition = null,
    returnState = null,
    lastSound = 0;
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
  function choose(item, focus = false) {
    selected = item;
    $("selection").hidden = false;
    $("library").hidden = true;
    $("selection-title").textContent = item.title;
    $("selection-owner").textContent =
      `Published by ${ownerLabel(item)} · snapshot credit: ${item.author}`;
    $("selection-description").textContent = item.description;
    $("selection-counts").textContent =
      `${item.graph_count} generations · ${item.thought_count} thoughts`;
    $("download").href = `/api/publications/${item.id}/bundle`;
    $("download").download =
      `${item.inquiry_id.slice(0, 12)}.atlas-inquiry.json`;
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
    if (items.has(item.id)) return;
    items.set(item.id, item);
    const entry = el("button", "", $("inquiry-list"));
    el("span", item.title, entry);
    el("small", `${ownerLabel(item)} · ${item.thought_count} thoughts`, entry);
    entry.onclick = () => choose(item, true);
    if (!scene) return;
    const group = new THREE.Group();
    group.position.set(item.x, terrainHeight(item.x, item.z), item.z);
    scene.add(group);
    item.group = group;
    item.aura = weave.locale(group, items.size - 1);
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
      RelicGLBLoader.load(
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
    item.label = el("div", item.title, $("labels"));
    item.label.className = "locale-label";
  }
  async function loadWorld(reset = false) {
    if (reset) {
      location.reload();
      return;
    }
    const result = await api("/api/world" + (next ? "?after=" + next : ""));
    for (const item of result.publications) add(item);
    next = result.next;
    $("more").hidden = !next;
    $("world-status").textContent = items.size
      ? `${items.size} published ${items.size === 1 ? "inquiry" : "inquiries"} · choose a light to enter`
      : "The Atlas is ready for its first published inquiry.";
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
          [...items.values()].map((x) => x.pick).filter(Boolean),
        )[0];
        if (hit) choose(hit.object.userData.item);
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
      weave.update(time, state.span);
      renderer.render(scene, camera);
    }
    requestAnimationFrame(frame);
  }
  async function enter() {
    if (!selected) return;
    try {
      await api("/api/publications/" + selected.id);
      returnState = { ...state };
      const id = selected.id;
      sound("traverse");
      moveTo({ x: selected.x, z: selected.z, span: 18 }, () => {
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
  async function read() {
    if (!selected) return;
    try {
      const b = await api("/api/publications/" + selected.id + "/bundle");
      $("reader-title").textContent = selected.title;
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
      const { publications } = await api("/api/mine");
      $("account-content").replaceChildren();
      for (const item of publications) {
        const row = el("div", "", $("account-content"));
        el("h3", item.title, row);
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
          await api("/api/publications", { artifact, reviewed: check.checked });
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
  $("read").onclick = read;
  $("world-return").onclick = leave;
  $("more").onclick = () => loadWorld().catch(reportError);
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
  loadWorld().catch(reportError);
  api("/api/me")
    .then((data) => {
      owner = data.owner;
      if (owner) {
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
