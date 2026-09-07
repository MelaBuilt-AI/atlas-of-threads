/* A curved local patch. Absolute samples keep the land fixed as the walk moves. */
(function () {
  function relief(x, z) {
    return Math.sin(x * .075) * Math.cos(z * .058) * .9 +
      Math.sin(x * .21 + z * .13) * .22 + Math.sin(x * .63 + z * .44) * .12;
  }
  function height(x, z, center) {
    return relief(center.x + x, center.z + z) - relief(center.x, center.z) -
      (x * x + z * z) / 620 - .06;
  }
  function surface(center) {
    const group = new THREE.Group();
    const geometry = new THREE.PlaneGeometry(160, 160, 80, 80);
    geometry.rotateX(-Math.PI / 2);
    const points = geometry.attributes.position;
    const colors = [];
    const low = new THREE.Color(0x203e42);
    const high = new THREE.Color(0x56756a);
    for (let i = 0; i < points.count; i++) {
      const x = points.getX(i), z = points.getZ(i);
      points.setY(i, height(x, z, center));
      const color = low.clone().lerp(high, (relief(center.x + x, center.z + z) + 1.2) / 2.4);
      colors.push(color.r, color.g, color.b);
    }
    geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
    geometry.computeVertexNormals();
    const land = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({
      vertexColors: true, roughness: .94, metalness: .06, flatShading: true,
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
      const bend = Math.sin(u * Math.PI) * Math.min(distance * .08, 1.5);
      const x = from.x + dx * u - center.x + (distance ? dz / distance * bend : 0);
      const z = from.z + dz * u - center.z - (distance ? dx / distance * bend : 0);
      vertices.push(new THREE.Vector3(x, height(x, z, center) + .09, z));
    }
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
      return new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({
        color: 0xf5d795, side: THREE.DoubleSide, transparent: true, opacity: .85,
      }));
    }
    const material = new THREE.LineDashedMaterial({ color: 0x7cbbb6, transparent: true, opacity: .65, dashSize: .55, gapSize: .32 });
    const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(vertices), material);
    line.computeLineDistances();
    return line;
  }
  window.TATerrain = { height, surface, path };
})();
