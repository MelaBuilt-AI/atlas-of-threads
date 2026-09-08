/* A curved local patch. Absolute samples keep the land fixed as the walk moves. */
(function (scope) {
  const TEXTURES = [
    "01-neural-basalt", "02-memory-silt", "03-amber-palimpsest", "04-verdant-synapse",
    "05-violet-schist", "06-woven-regolith", "07-porcelain-ash", "08-obsidian-tesserae",
    "09-silver-contour", "10-dreamstone",
  ];
  const TEXTURE_MEMORY = "thought-archaeology.terrain.v1";
  let assignments = {};
  let activeTexture = null;
  let activeName = null;
  let textureReady = false;

  // Random among the least-used surfaces: the first ten walks each get a different place.
  function assignTexture(session, saved, random = Math.random) {
    if (TEXTURES.includes(saved[session])) return saved[session];
    const counts = TEXTURES.map((name) => Object.values(saved).filter((value) => value === name).length);
    const least = Math.min(...counts);
    const available = TEXTURES.filter((_, i) => counts[i] === least);
    return saved[session] = available[Math.floor(random() * available.length)];
  }

  function texture(session, anisotropy) {
    try {
      const saved = localStorage.getItem(TEXTURE_MEMORY);
      if (saved) assignments = JSON.parse(saved);
    } catch (_) { /* In-memory assignments still work without browser storage. */ }
    const existing = assignments[session];
    const name = assignTexture(session, assignments);
    if (existing !== name) {
      try { localStorage.setItem(TEXTURE_MEMORY, JSON.stringify(assignments)); } catch (_) {}
    }
    if (name !== activeName) {
      if (activeTexture) activeTexture.dispose();
      activeName = name;
      textureReady = false;
      activeTexture = new THREE.TextureLoader().load(`./assets/terrain/${name}-4k.png`, (loaded) => {
        if (loaded === activeTexture) textureReady = true;
      });
      activeTexture.wrapS = activeTexture.wrapT = THREE.MirroredRepeatWrapping;
      activeTexture.colorSpace = THREE.SRGBColorSpace;
      activeTexture.anisotropy = anisotropy;
      activeTexture.userData.terrain = true; // Owned here; retained across chamber rebuilds.
    }
    return activeTexture;
  }

  function pointAlong(from, to, u) {
    const dx = to.x - from.x, dz = to.z - from.z;
    const distance = Math.hypot(dx, dz);
    // The same bend in either traversal direction, including Reflect.
    const orientation = from.x < to.x || (from.x === to.x && from.z < to.z) ? 1 : -1;
    const bend = Math.sin(u * Math.PI) * Math.min(distance * .08, 1.5) * orientation;
    return {
      x: from.x + dx * u + (distance ? dz / distance * bend : 0),
      z: from.z + dz * u - (distance ? dx / distance * bend : 0),
    };
  }

  function relief(x, z) {
    return Math.sin(x * .075) * Math.cos(z * .058) * .9 +
      Math.sin(x * .21 + z * .13) * .22 + Math.sin(x * .63 + z * .44) * .12;
  }
  function height(x, z, center) {
    return relief(center.x + x, center.z + z) - relief(center.x, center.z) -
      (x * x + z * z) / 620 - .06;
  }
  function surface(center, session, anisotropy = 4) {
    const group = new THREE.Group();
    const geometry = new THREE.PlaneGeometry(160, 160, 80, 80);
    geometry.rotateX(-Math.PI / 2);
    const points = geometry.attributes.position;
    const uv = geometry.attributes.uv;
    for (let i = 0; i < points.count; i++) {
      const x = points.getX(i), z = points.getZ(i);
      points.setY(i, height(x, z, center));
      // Absolute UVs keep the ground texture fixed while the local patch recenters.
      uv.setXY(i, (center.x + x) / 12, (center.z + z) / 12);
    }
    geometry.computeVertexNormals();
    const land = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({
      map: texture(session, anisotropy), roughness: .94, metalness: .02, flatShading: true,
      side: THREE.DoubleSide,
    }));
    land.receiveShadow = true;
    group.add(land);
    // Faint dashed filaments are landscape decoration, never selectable destinations.
    for (let lane = -3; lane <= 3; lane++) {
      const vertices = [];
      for (let step = 0; step < 40; step++) {
        const z = -12 - step * 1.5;
        const x = lane * 8 + Math.sin((center.z + z) * .055 + lane) * (4 + step * .13);
        vertices.push(new THREE.Vector3(x, height(x, z, center) + .09, z));
      }
      const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(vertices),
        new THREE.LineDashedMaterial({ color: 0x64928a, transparent: true, opacity: .23, dashSize: .28, gapSize: .8 }));
      line.computeLineDistances();
      group.add(line);
    }
    return group;
  }
  function path(from, to, center, traveled = true) {
    const vertices = [];
    const dx = to.x - from.x, dz = to.z - from.z;
    const distance = Math.hypot(dx, dz);
    const steps = Math.max(4, Math.ceil(distance * 2));
    if (distance > 150) return null; // Map jumps have no invented terrain connection.
    for (let i = 0; i <= steps; i++) {
      const u = i / steps;
      const point = pointAlong(from, to, u);
      const x = point.x - center.x, z = point.z - center.z;
      vertices.push(new THREE.Vector3(x, height(x, z, center) + .09, z));
    }
    const group = new THREE.Group();
    if (traveled) {
      const ribbon = [], indices = [];
      const sideX = distance ? dz / distance * .13 : .13;
      const sideZ = distance ? -dx / distance * .13 : 0;
      vertices.forEach((p, i) => {
        ribbon.push(p.x - sideX, p.y, p.z - sideZ, p.x + sideX, p.y, p.z + sideZ);
        if (i) indices.push(i * 2 - 2, i * 2, i * 2 - 1, i * 2 - 1, i * 2, i * 2 + 1);
      });
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.Float32BufferAttribute(ribbon, 3));
      geometry.setIndex(indices);
      group.add(new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({
        color: 0xf5d795, side: THREE.DoubleSide, transparent: true, opacity: .65,
      })));
    } else {
    const material = new THREE.LineDashedMaterial({ color: 0x7cbbb6, transparent: true, opacity: .65, dashSize: .55, gapSize: .32 });
    const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(vertices), material);
    line.computeLineDistances();
    group.add(line);
    }
    const ribbon = [], uv = [], indices = [];
    vertices.forEach((p, i) => {
      const before = vertices[Math.max(0, i - 1)], after = vertices[Math.min(steps, i + 1)];
      const length = Math.hypot(after.x - before.x, after.z - before.z) || 1;
      const sx = (after.z - before.z) / length * .48;
      const sz = -(after.x - before.x) / length * .48;
      ribbon.push(p.x - sx, p.y + .035, p.z - sz, p.x + sx, p.y + .035, p.z + sz);
      uv.push(i / steps, 0, i / steps, 1);
      if (i) indices.push(i * 2 - 2, i * 2, i * 2 - 1, i * 2 - 1, i * 2, i * 2 + 1);
    });
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(ribbon, 3));
    geometry.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2));
    geometry.setIndex(indices);
    const material = new THREE.ShaderMaterial({
      uniforms: {
        time: { value: 0 }, direction: { value: 1 }, strength: { value: 1 },
        routeLength: { value: distance }, color: { value: new THREE.Color(traveled ? 0xffdf9d : 0x8ce8e1) },
      },
      vertexShader: `varying vec2 vUv;
        void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
      fragmentShader: `varying vec2 vUv;
        uniform float time, direction, strength, routeLength;
        uniform vec3 color;
        void main() {
          float along = direction > 0.0 ? vUv.x : 1.0 - vUv.x;
          float phase = fract((along * routeLength - time * 6.0) / 7.5);
          float pulse = exp(-(1.0 - phase) * 13.0);
          float edge = pow(max(0.0, 1.0 - abs(vUv.y * 2.0 - 1.0)), 2.0);
          float ends = smoothstep(0.0, .025, vUv.x) * smoothstep(0.0, .025, 1.0 - vUv.x);
          gl_FragColor = vec4(mix(color, vec3(1.0), pulse * .65), pulse * edge * ends * strength);
        }`,
      transparent: true, depthWrite: false, side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending,
    });
    group.add(new THREE.Mesh(geometry, material));
    group.userData.flow = { uniforms: material.uniforms, dx, dz, traveled, base: group.children[0].material };
    return group;
  }
  // A bounded branching neuron corona for one remembered chamber; no extra lights/shadows.
  function echo() {
    const group = new THREE.Group();
    const edges = [];
    for (let arm = 0; arm < 7; arm++) {
      const angle = arm / 7 * Math.PI * 2;
      const start = new THREE.Vector3(Math.cos(angle) * .55, 1.4, Math.sin(angle) * .55);
      const joint = new THREE.Vector3(Math.cos(angle) * 1.1, 2.8 + (arm % 3) * .3, Math.sin(angle) * 1.1);
      edges.push([start, joint]);
      for (const side of [-1, 1]) {
        const endAngle = angle + side * .3;
        const end = new THREE.Vector3(Math.cos(endAngle) * 2.1, 4 + (arm % 2) * .7, Math.sin(endAngle) * 2.1);
        edges.push([joint, end]);
      }
    }
    const branches = new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(edges.flat()),
      new THREE.LineBasicMaterial({ color: 0xb780ff, transparent: true, opacity: .38,
        blending: THREE.AdditiveBlending, depthWrite: false }));
    group.add(branches);
    const halo = new THREE.Mesh(new THREE.RingGeometry(1.35, 1.65, 48),
      new THREE.MeshBasicMaterial({ color: 0x8c62ff, transparent: true, opacity: .65,
        side: THREE.DoubleSide, blending: THREE.AdditiveBlending, depthWrite: false }));
    halo.rotation.x = -Math.PI / 2;
    halo.position.y = .1;
    group.add(halo);
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(new Float32Array(edges.length * 4 * 3), 3));
    const colors = [];
    for (const _edge of edges) for (let tail = 0; tail < 4; tail++) {
      const color = new THREE.Color(0x94f3ff).multiplyScalar(1 - tail * .22);
      colors.push(color.r, color.g, color.b);
    }
    geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
    const sparks = new THREE.Points(geometry, new THREE.ShaderMaterial({
      vertexColors: true, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
      vertexShader: `varying vec3 sparkColor;
        void main() {
          sparkColor = color;
          vec4 p = modelViewMatrix * vec4(position, 1.0);
          gl_PointSize = clamp(120.0 / -p.z, 2.0, 14.0);
          gl_Position = projectionMatrix * p;
        }`,
      fragmentShader: `varying vec3 sparkColor;
        void main() {
          float glow = max(0.0, 1.0 - length(gl_PointCoord - .5) * 2.0);
          gl_FragColor = vec4(sparkColor, glow * glow);
        }`,
    }));
    group.add(sparks);
    group.userData = { edges, sparks, branches, halo };
    return group;
  }

  function tickEcho(group, t) {
    const { edges, sparks, branches, halo } = group.userData;
    const positions = sparks.geometry.attributes.position;
    edges.forEach(([from, to], i) => {
      for (let tail = 0; tail < 4; tail++) {
        const u = ((t * .7 + i * .173 - tail * .045) % 1 + 1) % 1;
        positions.setXYZ(i * 4 + tail,
          from.x + (to.x - from.x) * u, from.y + (to.y - from.y) * u, from.z + (to.z - from.z) * u);
      }
    });
    positions.needsUpdate = true;
    branches.material.opacity = .32 + Math.sin(t * 1.8) * .1;
    halo.material.opacity = .65 + Math.sin(t * 2.1) * .15;
  }

  const api = { height, surface, path, pointAlong, assignTexture, TEXTURES, echo, tickEcho,
    get textureName() { return activeName; }, get textureReady() { return textureReady; } };
  if (typeof module !== "undefined") module.exports = api;
  else scope.TATerrain = api;
})(globalThis);
