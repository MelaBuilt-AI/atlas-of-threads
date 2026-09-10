/* Atmospheric scenery carries no relationship or presence data. */
(() => {
  "use strict";
  const palette = [0x35cfff, 0x427aff, 0xa06aff, 0xf9b955, 0x36e4ef];
  window.AtlasWeave = function (scene, renderer, reduced) {
    let seed = 72831;
    const random = () => { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return seed / 4294967296; };
    const clock = { value: 0 }, scale = { value: 10 };
    const ribbonMaterials = palette.map(hex => new THREE.ShaderMaterial({
      uniforms: { time: clock, tint: { value: new THREE.Color(hex) } },
      transparent: true, depthWrite: false, side: THREE.DoubleSide, blending: THREE.AdditiveBlending,
      vertexShader: `varying vec2 vUv; void main() { vUv = uv;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
      fragmentShader: `uniform float time; uniform vec3 tint; varying vec2 vUv;
        void main() {
          float edge = abs(vUv.y * 2.0 - 1.0);
          float halo = exp(-edge * edge * 5.0) * .16;
          float core = exp(-edge * edge * 240.0);
          float pulse = pow(.5 + .5 * sin(vUv.x * 55.0 - time * .65), 14.0);
          float fade = smoothstep(0.0, .06, vUv.x) * (1.0 - smoothstep(.94, 1.0, vUv.x));
          gl_FragColor = vec4(mix(tint, vec3(.85, .96, 1.0), core * .5),
            (halo + core * .65) * (.7 + pulse * .65) * fade);
        }`,
    }));
    // Soft additive ribbons retain luminous width independently of WebGL lines.
    function ribbon(points, width, material, parent = scene) {
      const positions = [], uvs = [], indices = [];
      for (let i = 0; i < points.length; i++) {
        const p = points[i], a = points[Math.max(0, i - 1)], b = points[Math.min(points.length - 1, i + 1)];
        const dx = b.x - a.x, dz = b.z - a.z, length = Math.hypot(dx, dz) || 1;
        for (const side of [-1, 1]) {
          positions.push(p.x - dz / length * width * side, p.y, p.z + dx / length * width * side);
          uvs.push(i / (points.length - 1), (side + 1) / 2);
        }
        if (i) { const n = i * 2; indices.push(n - 2, n - 1, n, n - 1, n + 1, n); }
      }
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
      geometry.setAttribute("uv", new THREE.Float32BufferAttribute(uvs, 2));
      geometry.setIndex(indices);
      const mesh = new THREE.Mesh(geometry, material); parent.add(mesh); return mesh;
    }
    function stars(positions, colors, sizes, parent = scene) {
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
      geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
      geometry.setAttribute("size", new THREE.Float32BufferAttribute(sizes, 1));
      const material = new THREE.ShaderMaterial({
        uniforms: { time: clock, scale }, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
        vertexShader: `attribute float size; attribute vec3 color;
          uniform float scale; uniform float time; varying vec3 tint; varying float glint;
          void main() {
            tint = color; glint = .78 + .22 * sin(time * .7 + position.x * 3.0 + position.z);
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
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
      const points = new THREE.Points(geometry, material); parent.add(points); return points;
    }
    const dust = [], colors = [], sizes = [];
    function point(p, color, size) { dust.push(p.x, p.y, p.z); colors.push(color.r, color.g, color.b); sizes.push(size); }
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
      ribbon(points, lane % 8 === 0 ? .65 : .23, ribbonMaterials[index]);
    }
    for (let i = 0; i < 5500; i++) point(new THREE.Vector3((random() - .5) * 1100,
      -8 + random() * 38, (random() - .5) * 1100), new THREE.Color(palette[i % 5]), .06 + random() * .22);
    stars(dust, colors, sizes);
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
    return { locale, update(time, span) {
      clock.value = reduced ? 0 : time * .001;
      scale.value = innerHeight * renderer.getPixelRatio() / span;
      for (const item of locales) {
        item.orbits.rotation.y = reduced ? 0 : time * .000025 * (item.phase % 2 ? 1 : -1);
        item.detail.visible = span < 260; item.beacon.visible = span >= 160;
        item.glow.scale.setScalar(reduced ? 1 : 1 + Math.sin(time * .0006 + item.phase) * .035);
      }
    } };
  };
})();
