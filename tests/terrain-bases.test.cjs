const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const terrain = require('../viz/dist/terrain.js');
const space = readFileSync(path.join(__dirname, '../viz/dist/space.js'), 'utf8');

function runtime() {
  const requests = [];
  const c = vm.createContext({TextDecoder, Blob, console: {warn() {}},
    createImageBitmap: async () => ({}),
    fetch: async url => {
      requests.push(url);
      const bytes = readFileSync(path.join(__dirname, '../viz/dist', url));
      return {ok: true, arrayBuffer: async () => bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength)};
    },
  });
  c.window = c;
  c.terrainHeight = terrain.height;
  vm.runInContext(readFileSync(path.join(__dirname, '../viz/dist/three.min.js'), 'utf8'), c);
  vm.runInContext(readFileSync(path.join(__dirname, '../viz/dist/relic-loader.js'), 'utf8'), c);
  vm.runInContext(`var layoutGeneration = 1; var TATerrain = {textureName: null, height: terrainHeight}; var terrainCenter = {x: 11, z: -7};
    var reflected = 0; function reflectMaterials() { reflected++; }
    ${space.slice(space.indexOf('  function disposeRelicClone('), space.indexOf('  function clearAtlasMapRoot('))}
    ${space.slice(space.indexOf('  function mountTerrainBase('), space.indexOf('  function labelTexture('))}`, c);
  return {c, requests};
}

test('every assigned terrain loads its matching GLB, settles into the terrain and reuses textures', async () => {
  const {c, requests} = runtime(), T = c.THREE, root = new T.Group(), assignments = {};
  for (let i = 0; i < 10; i++) {
    const name = terrain.assignTexture(`walk-${i}`, assignments);
    c.TATerrain.textureName = name;
    const group = new T.Group(); group.position.set(i * 2, 0, -i * 3); root.add(group);
    const pending = c.mountTerrainBase(group, {width: 3.6, top: .12});
    // A later surface selection must never recolor this already requested chamber.
    c.TATerrain.textureName = 'different-walk';
    await pending;
    assert.equal(group.userData.terrainBase, name);
    assert.equal(group.userData.terrainBaseReady, true, group.userData.terrainBaseError);
    const base = group.children[0], bounds = new T.Box3().setFromObject(base);
    assert.ok(Math.abs(Math.max(bounds.getSize(new T.Vector3()).x, bounds.getSize(new T.Vector3()).z) - 3.6) < 1e-6);
    const relativeHeights = [];
    base.traverse(part => {
      if (!part.isMesh) return;
      const points = part.geometry.attributes.position;
      for (let j = 0; j < points.count; j++) {
        const ground = terrain.height(group.position.x + points.getX(j), group.position.z + points.getZ(j), c.terrainCenter)
          - terrain.height(group.position.x, group.position.z, c.terrainCenter);
        relativeHeights.push(points.getY(j) - ground);
      }
    });
    assert.ok(Math.abs(Math.max(...relativeHeights) - .12) < 1e-6);
    assert.ok(Math.abs(Math.min(...relativeHeights) + .18) < 1e-6);
    assert.ok(relativeHeights.filter(y => y < 0).length > relativeHeights.length * .7);
    let mesh; base.traverse(part => { if (part.isMesh) mesh = part; });
    assert.ok(mesh.material.map && mesh.material.normalMap && mesh.material.roughnessMap);
    c.TATerrain.textureName = name;
    const ghost = new T.Group(); root.add(ghost); ghost.userData.reflecting = true;
    await c.mountTerrainBase(ghost, {width: 2.4, top: .12, ghost: true});
    let ghostMesh; ghost.traverse(part => { if (part.isMesh) ghostMesh = part; });
    assert.notEqual(ghostMesh.geometry, mesh.geometry);
    assert.equal(ghostMesh.material.map, mesh.material.map);
    assert.notEqual(ghostMesh.material, mesh.material);
    assert.equal(ghostMesh.material.opacity, mesh.material.opacity * .55);
    assert.equal(ghostMesh.material.depthWrite, false);
    assert.equal(base.userData.sharedRelicResources, true);
    let geometryDisposed = false, textureDisposed = false;
    mesh.geometry.addEventListener('dispose', () => {geometryDisposed = true;});
    mesh.material.map.addEventListener('dispose', () => {textureDisposed = true;});
    c.disposeAtlasObject(base);
    assert.equal(geometryDisposed, true);
    assert.equal(textureDisposed, false);

  }
  assert.equal(requests.length, 10);
  assert.equal(c.reflected, 10);
});

test('late base loads do not attach to a disposed or superseded layout', async () => {
  const {c} = runtime(), T = c.THREE;
  let finish;
  c.RelicGLBLoader.load = () => new Promise(resolve => { finish = resolve; });
  for (const stale of ['disposed', 'generation']) {
    const group = new T.Group(); new T.Group().add(group);
    const mesh = new T.Mesh(new T.BoxGeometry(), new T.MeshStandardMaterial());
    let disposed = false; mesh.material.addEventListener('dispose', () => {disposed = true;});
    const pending = c.mountTerrainBase(group, {width: 3.6, top: .12});
    if (stale === 'disposed') group.userData.disposed = true;
    else c.layoutGeneration++;
    finish(mesh); await pending;
    assert.equal(group.children.length, 0);
    assert.equal(disposed, true);
    assert.equal(group.userData.terrainBaseReady, false);
  }
});


test('model-space tilt is removed and the base fits uneven ground over its whole footprint', () => {
  const {c} = runtime(), T = c.THREE;
  const slope = new T.Quaternion().setFromUnitVectors(new T.Vector3(0, 1, 0), new T.Vector3(.00971, .857551, .514307).normalize());
  const source = new T.Mesh(new T.BoxGeometry(1, .2, 1).applyQuaternion(slope), new T.MeshStandardMaterial());
  const original = Array.from(source.geometry.attributes.position.array);
  const group = new T.Group(); group.position.set(24, 0, -31);
  const base = c.settleTerrainBase(source, group, 4, .12);
  const points = base.children[0].geometry.attributes.position;
  for (let i = 0; i < points.count; i++) {
    const ground = terrain.height(24 + points.getX(i), -31 + points.getZ(i), c.terrainCenter) - terrain.height(24, -31, c.terrainCenter);
    const elevation = points.getY(i) - ground;
    assert.ok(Math.min(Math.abs(elevation - .12), Math.abs(elevation + .18)) < 1e-6);
  }
  assert.deepEqual(Array.from(source.geometry.attributes.position.array), original);
});
