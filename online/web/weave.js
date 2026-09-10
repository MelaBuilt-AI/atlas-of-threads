/* Atmospheric scenery carries no relationship or presence data. */
(() => {
  "use strict";
  const palette = [0x35cfff, 0x427aff, 0xa06aff, 0xf9b955, 0x36e4ef];
  window.AtlasWeave = function (scene, renderer, reduced) {
    let seed = 72831;
    const random = () => { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return seed / 4294967296; };
    const clock = { value: 0 }, scale = { value: 10 };
    // One continuous displacement field keeps forks joined while the web breathes.
    const displacement = `vec3 drift(vec3 p, float t) {
      return vec3(sin(p.z * .035 + p.x * .014 + t * .23) * 1.6,
        sin(p.x * .026 - p.z * .02 + t * .32) * .65,
        cos(p.x * .03 - p.z * .017 + t * .19) * 1.6);
    }`;
    const batches = new Map();
    const ribbonMaterials = palette.map(hex => new THREE.ShaderMaterial({
      uniforms: { time: clock, tint: { value: new THREE.Color(hex) } },
      transparent: true, depthWrite: false, side: THREE.DoubleSide, blending: THREE.AdditiveBlending,
      vertexShader: `attribute float motion; attribute float strength;
        uniform float time; varying vec2 vUv; varying float energy;
        ${displacement}
        void main() { vUv = uv; energy = strength;
          vec3 p = position + drift(position, time) * motion;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0); }`,
      fragmentShader: `uniform float time; uniform vec3 tint;
        varying vec2 vUv; varying float energy;
        void main() {
          float edge = abs(vUv.y * 2.0 - 1.0);
          float travel = fract(vUv.x * 3.0 - time * .075);
          float head = exp(-pow((travel - .5) * 28.0, 2.0));
          float trail = exp(-max(0.0, .5 - travel) * 14.0) * step(travel, .5);
          float breathe = .78 + .22 * sin(time * .85 + vUv.x * 18.0);
          float halo = exp(-edge * edge * 4.5) * (.16 + trail * .2 + head * .35);
          float core = exp(-edge * edge * 95.0);
          float fade = smoothstep(0.0, .025, vUv.x) * (1.0 - smoothstep(.975, 1.0, vUv.x));
          vec3 color = mix(tint, vec3(.85, .97, 1.0), core * (.25 + head * .55));
          gl_FragColor = vec4(color, (halo + core * (.55 + trail + head)) * breathe * fade * energy);
        }`,
    }));
    // Soft additive ribbons retain luminous width independently of WebGL lines.
    function ribbon(points, width, material, parent = scene, strength = 1, batchTarget = parent === scene ? batches : null) {
      const batched = !!batchTarget;
      let data = batched ? batchTarget.get(material) : null;
      if (!data) {
        data = { positions: [], uvs: [], indices: [], motion: [], strength: [] };
        if (batched) batchTarget.set(material, data);
      }
      const start = data.positions.length / 3;
      for (let i = 0; i < points.length; i++) {
        const p = points[i], a = points[Math.max(0, i - 1)], b = points[Math.min(points.length - 1, i + 1)];
        const dx = b.x - a.x, dz = b.z - a.z, length = Math.hypot(dx, dz) || 1;
        for (const side of [-1, 1]) {
          data.positions.push(p.x - dz / length * width * side, p.y, p.z + dx / length * width * side);
          data.uvs.push(i / (points.length - 1), (side + 1) / 2);
          data.motion.push(batched ? 1 : 0); data.strength.push(strength);
        }
        if (i) { const n = start + i * 2; data.indices.push(n - 2, n - 1, n, n - 1, n + 1, n); }
      }
      if (!batched) parent.add(new THREE.Mesh(ribbonGeometry(data), material));
    }
    function ribbonGeometry(data) {
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.Float32BufferAttribute(data.positions, 3));
      geometry.setAttribute("uv", new THREE.Float32BufferAttribute(data.uvs, 2));
      geometry.setAttribute("motion", new THREE.Float32BufferAttribute(data.motion, 1));
      geometry.setAttribute("strength", new THREE.Float32BufferAttribute(data.strength, 1));
      geometry.setIndex(data.indices);
      // Allow for the small shader displacement at the edges of the view.
      geometry.computeBoundingSphere(); geometry.boundingSphere.radius += 3;
      return geometry;
    }
    function stars(positions, colors, sizes, parent = scene) {
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
      geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
      geometry.setAttribute("size", new THREE.Float32BufferAttribute(sizes, 1));
      const material = new THREE.ShaderMaterial({
        uniforms: { time: clock, scale, motion: { value: parent === scene ? 1 : 0 } }, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
        vertexShader: `attribute float size; attribute vec3 color;
          uniform float scale; uniform float time; uniform float motion;
          varying vec3 tint; varying float glint;
          ${displacement}
          void main() {
            tint = color; glint = .6 + .4 * sin(time * 1.1 + position.x * .2 + position.z);
            vec3 p = position + drift(position, time) * motion;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0);
            gl_PointSize = clamp(size * scale, 1.2, 100.0);
          }`,
        fragmentShader: `varying vec3 tint; varying float glint;
          void main() {
            vec2 p = gl_PointCoord * 2.0 - 1.0; float r = length(p);
            float core = exp(-r * r * 100.0);
            float halo = exp(-r * r * 6.0) * .3;
            float rays = pow(max(0.0, 1.0 - abs(p.x * p.y)), 100.0) * pow(max(0.0, 1.0 - r), 3.0) * .28;
            gl_FragColor = vec4(mix(tint, vec3(1.0), core * .8), (core + halo + rays) * glint);
          }`,
      });
      geometry.computeBoundingSphere(); geometry.boundingSphere.radius += 3;
      const points = new THREE.Points(geometry, material); parent.add(points); return points;
    }
    const dust = [], colors = [], sizes = [];
    function point(p, color, size) { dust.push(p.x, p.y, p.z); colors.push(color.r, color.g, color.b); sizes.push(size); }
    const currents = [];
    function curve(points, width, material, strength = 1) {
      const path = new THREE.CatmullRomCurve3(points);
      const sampled = path.getPoints(40);
      ribbon(sampled, width, material, scene, strength);
      return sampled;
    }
    // The distant neural lattice is real animated geometry beneath the world.
    // Jittered junctions and curved forks avoid a flat grid or a photographic sky.
    const distant = [];
    for (let z = 0; z < 22; z++) {
      const row = [];
      for (let x = 0; x < 22; x++) row.push(new THREE.Vector3(
        (x - 10.5) * 48 + (random() - .5) * 32,
        -48 + Math.sin(x * .5 + z * .4) * 15,
        (z - 10.5) * 48 + (random() - .5) * 32));
      distant.push(row);
    }
    for (let z = 0; z < 22; z++) for (let x = 0; x < 22; x++) {
      const a = distant[z][x], index = (x + z) % 4;
      point(a, new THREE.Color(palette[index]).multiplyScalar(.6), 1.2 + random() * 1.5);
      const neighbors = [];
      if (x < 21) neighbors.push(distant[z][x + 1]);
      if (z < 21) neighbors.push(distant[z + 1][x]);
      if (x < 21 && z < 21 && random() > .58) neighbors.push(distant[z + 1][x + 1]);
      for (const b of neighbors) {
        const mid = a.clone().lerp(b, .5);
        mid.x += (random() - .5) * 18; mid.z += (random() - .5) * 18;
        curve([a, mid, b], .35, ribbonMaterials[index], .24);
      }
    }
    // Crossing currents are independent of publications, never inferred edges.
    for (let lane = 0; lane < 96; lane++) {
      const family = lane % 3, offset = (Math.floor(lane / 3) - 15.5) * 7.3;
      const index = lane % 13 === 0 ? 3 : [0, 1, 2, 4][lane % 4];
      const color = new THREE.Color(palette[index]), points = [], phase = random() * Math.PI * 2;
      for (let i = 0; i <= 220; i++) {
        const x = (i / 220 - .5) * 900;
        const z = offset + Math.sin(x * .012 + family * 2.1) * (20 + family * 14) + Math.sin(x * .032 + phase) * 3.5;
        const angle = family * 1.04 - .45;
        const p = new THREE.Vector3(x * Math.cos(angle) - z * Math.sin(angle),
          -2.7 + Math.sin(x * .017 + phase) * 1.4, x * Math.sin(angle) + z * Math.cos(angle));
        points.push(p);
        if (i % 2 === 0) point(new THREE.Vector3(p.x + (random() - .5) * 5, p.y + random() * 2,
          p.z + (random() - .5) * 5), color, random() < .012 ? 2.8 : .12 + random() * .24);
      }
      ribbon(points, lane % 8 === 0 ? 1.2 : .42, ribbonMaterials[index], scene, .65);
      currents.push({ points, color });
      // Dendrites leave the trunk, spread, and subdivide into fine reaching tips.
      for (let fork = 0; fork < 5; fork++) {
        const start = 30 + fork * 35 + Math.floor(random() * 10), a = points[start];
        const direction = points[start + 8].clone().sub(a).normalize();
        const side = fork % 2 ? 1 : -1;
        const normal = new THREE.Vector3(-direction.z, .15, direction.x).multiplyScalar(side);
        const end = a.clone().addScaledVector(direction, 10 + random() * 14)
          .addScaledVector(normal, 7 + random() * 17);
        const mid = a.clone().lerp(end, .5).addScaledVector(direction, 5);
        mid.y += 1.8;
        const branch = curve([a, mid, end], .3, ribbonMaterials[index], .65);
        if (fork % 2 === 0) {
          point(branch[23], color, 1.8);
          const tip = branch[23].clone().addScaledVector(normal, 8).addScaledVector(direction, 5);
          curve([branch[15], branch[23], tip], .18, ribbonMaterials[index], .45);
        }
      }
      // A few braided strands wrap each main current without moving its anchors.
      if (lane % 4 === 0) for (let strand = 0; strand < 3; strand++) {
        const braid = points.map((p, i) => {
          const q = p.clone(), phase = i * .16 + strand * 2.1;
          q.x += Math.sin(phase) * 1.3; q.z += Math.cos(phase) * 1.3;
          q.y += Math.sin(phase) * .8;
          return q;
        });
        ribbon(braid, .2, ribbonMaterials[(index + strand) % palette.length], scene, .65);
      }
    }
    for (let i = 0; i < 5500; i++) point(new THREE.Vector3((random() - .5) * 1100,
      -8 + random() * 38, (random() - .5) * 1100), new THREE.Color(palette[i % 5]), .06 + random() * .22);
    stars(dust, colors, sizes);
    for (const [material, data] of batches) scene.add(new THREE.Mesh(ribbonGeometry(data), material));
    batches.clear();
    // Bright knots travel along the same paths, surrounded by elongated afterglow.
    const pulsePositions = new Float32Array(currents.length * 3 * 3);
    const pulseColors = [], pulseSizes = [];
    for (const { color } of currents) for (let n = 0; n < 3; n++) {
      pulseColors.push(color.r, color.g, color.b); pulseSizes.push(n === 0 ? 4 : 2.3);
    }
    const pulses = stars(pulsePositions, pulseColors, pulseSizes);
    pulses.frustumCulled = false;
    const pulseAttribute = pulses.geometry.attributes.position;
    const glowMaterial = new THREE.ShaderMaterial({
      uniforms: { tint: { value: new THREE.Color(0x35cfff) } },
      transparent: true, depthWrite: false, side: THREE.DoubleSide, blending: THREE.AdditiveBlending,
      vertexShader: `varying vec2 vUv; void main() { vUv = uv;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
      fragmentShader: `uniform vec3 tint; varying vec2 vUv;
        void main() { float r = length(vUv - .5) * 2.0;
          float halo = exp(-r * r * 5.0) * .24; float center = exp(-r * r * 150.0) * .65;
          gl_FragColor = vec4(tint, (halo + center) * (1.0 - smoothstep(.7, 1.0, r))); }`,
    });
    const locales = [];
    const terrain = new THREE.TextureLoader().load("./assets/terrain/01-neural-basalt-4k.png");
    terrain.colorSpace = THREE.SRGBColorSpace;
    terrain.anisotropy = Math.min(4, renderer.capabilities.getMaxAnisotropy());
    function locale(group, sequence) {
      const index = sequence % palette.length, color = new THREE.Color(palette[index]);
      const detail = new THREE.Group(); group.add(detail);
      const surface = new THREE.Mesh(new THREE.CylinderGeometry(3.7, 4.3, .28, 64),
        new THREE.MeshStandardMaterial({ color: 0x192e4a, map: terrain, metalness: .65,
          roughness: .5, emissive: color, emissiveIntensity: .09 }));
      surface.position.y = .15; detail.add(surface);
      const glow = new THREE.Mesh(new THREE.PlaneGeometry(23, 23), glowMaterial.clone());
      glow.material.uniforms.tint.value.copy(color);
      glow.rotation.x = -Math.PI / 2; glow.position.y = .33; group.add(glow);
      const orbits = new THREE.Group(); detail.add(orbits);
      const starPositions = [0, 4.8, 0], starColors = [color.r, color.g, color.b], starSizes = [4.5];
      for (let n = 0; n < 9; n++) {
        const points = [], radius = 3.9 + n * .49;
        for (let i = 0; i <= 128; i++) {
          const a = i / 128 * Math.PI * 2;
          points.push(new THREE.Vector3(Math.cos(a) * radius,
            .42 + (n > 5 ? (1 + Math.sin(a + n)) * (n - 5) * .55 : n * .055),
            Math.sin(a) * radius * (n > 5 ? .68 : 1)));
        }
        ribbon(points, n % 3 === 0 ? .13 : .065, ribbonMaterials[index], orbits);
        if (n % 2 === 0) {
          const p = points[(n * 17 + sequence * 11) % 128];
          starPositions.push(p.x, p.y, p.z); starColors.push(color.r, color.g, color.b); starSizes.push(1.1);
        }
      }
      for (let n = 0; n < 70; n++) {
        const a = random() * Math.PI * 2, r = 3 + random() * 5;
        starPositions.push(Math.cos(a) * r, .4 + random() * .6, Math.sin(a) * r);
        starColors.push(color.r, color.g, color.b); starSizes.push(.09 + random() * .15);
      }
      stars(starPositions, starColors, starSizes, detail);
      const beacon = stars([0, .8, 0], [color.r, color.g, color.b], [5], group);
      const selection = new THREE.Mesh(new THREE.TorusGeometry(8.6, .035, 4, 96),
        new THREE.MeshBasicMaterial({ color: 0xffdd98, transparent: true, opacity: .85 }));
      selection.rotation.x = Math.PI / 2; selection.position.y = .48; selection.visible = false; group.add(selection);
      const entry = { detail, orbits, glow, beacon, selection, phase: sequence }; locales.push(entry); return entry;
    }
    const roads = new Map();
    function syncRoads(edges) {
      const wanted = new Map(edges.map(edge => [edge.id, edge]));
      for (const [id, road] of roads) {
        if (wanted.get(id)?.source.id === road.edge.source.id) continue;
        scene.remove(road.group);
        road.group.traverse(object => { object.geometry?.dispose(); });
        for (const material of road.materials) material.dispose();
        road.pick.material.dispose();
        roads.delete(id);
      }
      for (const edge of edges) {
        if (roads.has(edge.id)) continue;
        const from = edge.source.group.position.clone(), to = edge.target.group.position.clone();
        from.y += .45; to.y += .45;
        const direction = to.clone().sub(from), length = Math.hypot(direction.x, direction.z);
        const normal = new THREE.Vector3(-direction.z / length, 0, direction.x / length);
        const bend = Math.min(7, length * .15) * (edge.target.sequence % 2 ? 1 : -1);
        const curve = new THREE.CatmullRomCurve3([from,
          from.clone().lerp(to, .33).addScaledVector(normal, bend),
          from.clone().lerp(to, .67).addScaledVector(normal, bend), to]);
        const group = new THREE.Group(), batch = new Map(), growth = { value: reduced ? 1 : 0 };
        const materials = [0, 3].map(index => {
          const material = ribbonMaterials[index].clone();
          material.uniforms.time = clock; material.uniforms.growth = growth;
          material.vertexShader = material.vertexShader.replace(
            'drift(position, time) * motion',
            'drift(position, time) * motion * sin(uv.x * 3.14159265) * .3');
          material.fragmentShader = 'uniform float growth;\n' + material.fragmentShader;
          material.fragmentShader = material.fragmentShader.replace('float fade =',
            'float reveal = 1.0 - smoothstep(growth - .025, growth, vUv.x);\n          float fade = reveal *');
          return material;
        });
        const samples = curve.getPoints(100);
        // A broad luminous bed and 27 converging filaments make one readable road.
        ribbon(samples, 3.2, materials[0], group, .23, batch);
        for (let strand = 0; strand < 27; strand++) {
          const lane = (strand - 13) / 13;
          const points = samples.map((point, i) => {
            const t = i / 100, envelope = Math.pow(Math.sin(Math.PI * t), .4);
            const spread = (1.75 + 3 * Math.pow(Math.abs(t * 2 - 1), 4)) * envelope;
            const braid = Math.sin(t * 22 + strand * 1.7) * .3 * envelope;
            const p = point.clone().addScaledVector(normal, lane * spread + braid);
            p.y += Math.cos(t * 18 + strand) * .15 * envelope;
            return p;
          });
          ribbon(points, strand % 5 ? .14 : .26, materials[strand % 7 === 0 ? 1 : 0], group, 1.1, batch);
        }
        for (const [material, data] of batch) group.add(new THREE.Mesh(ribbonGeometry(data), material));
        const pick = new THREE.Mesh(new THREE.TubeGeometry(curve, 48, 2.7, 6, false),
          new THREE.MeshBasicMaterial({ visible: false }));
        pick.userData.road = edge.id; group.add(pick); scene.add(group);
        roads.set(edge.id, { edge, group, curve, pick, materials, growth, birth: null });
      }
      return roads;
    }
    return { locale, syncRoads, roads, removeLocale(item) {
      const index = locales.indexOf(item);
      if (index >= 0) locales.splice(index, 1);
      item.glow.material.dispose(); item.selection.material.dispose(); item.beacon.material.dispose();
      item.detail.traverse(object => {
        if (object.material && !ribbonMaterials.includes(object.material)) object.material.dispose();
      });
    }, update(time, span) {
      for (const road of roads.values()) {
        if (road.birth === null) road.birth = time;
        road.growth.value = reduced ? 1.03 : Math.min(1.03, (time - road.birth) / 2400);
      }

      clock.value = reduced ? 0 : time * .001;
      scale.value = innerHeight * renderer.getPixelRatio() / span;
      for (let lane = 0; lane < currents.length; lane++) {
        const path = currents[lane].points;
        for (let n = 0; n < 3; n++) {
          const t = ((clock.value * (.016 + lane % 4 * .002) + lane * .137 + n / 3) % 1) * (path.length - 1);
          const i = Math.floor(t), a = path[i], b = path[Math.min(i + 1, path.length - 1)], u = t - i;
          pulseAttribute.setXYZ(lane * 3 + n, a.x + (b.x - a.x) * u,
            a.y + (b.y - a.y) * u, a.z + (b.z - a.z) * u);
        }
      }
      pulseAttribute.needsUpdate = true;
      for (const item of locales) {
        item.orbits.rotation.y = reduced ? 0 : time * .000025 * (item.phase % 2 ? 1 : -1);
        item.detail.visible = span < 260; item.beacon.visible = span >= 160;
        item.glow.scale.setScalar(reduced ? 1 : 1 + Math.sin(time * .0006 + item.phase) * .035);
      }
    } };
  };
})();
