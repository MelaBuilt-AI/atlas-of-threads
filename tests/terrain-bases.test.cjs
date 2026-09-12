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
  vm.runInContext(readFileSync(path.join(__dirname, '../viz/dist/three.min.js'), 'utf8'), c);
  vm.runInContext(readFileSync(path.join(__dirname, '../viz/dist/relic-loader.js'), 'utf8'), c);
  vm.runInContext(`var layoutGeneration = 1; var TATerrain = {textureName: null};
    var reflected = 0; function reflectMaterials() { reflected++; }
    ${space.slice(space.indexOf('  function disposeRelicClone('), space.indexOf('  function disposeAtlasObject('))}
    ${space.slice(space.indexOf('  function mountTerrainBase('), space.indexOf('  function labelTexture('))}`, c);
  return {c, requests};
}

test('every assigned terrain loads its matching GLB, seats below the object and reuses model resources', async () => {
  const {c, requests} = runtime(), T = c.THREE, root = new T.Group(), assignments = {};
  for (let i = 0; i < 10; i++) {
    const name = terrain.assignTexture(`walk-${i}`, assignments);
    c.TATerrain.textureName = name;
    const group = new T.Group(); root.add(group);
    const pending = c.mountTerrainBase(group, {width: 3.6, top: .42});
    // A later surface selection must never recolor this already requested chamber.
    c.TATerrain.textureName = 'different-walk';
    await pending;
    assert.equal(group.userData.terrainBase, name);
    assert.equal(group.userData.terrainBaseReady, true, group.userData.terrainBaseError);
    const base = group.children[0], bounds = new T.Box3().setFromObject(base);
    assert.ok(Math.abs(bounds.max.y - .42) < 1e-6);
    assert.ok(Math.abs(bounds.min.y + .22) < 1e-6);
    assert.ok(Math.abs(bounds.getSize(new T.Vector3()).x - 3.6) < 1e-6);
    assert.ok(Math.abs(bounds.getCenter(new T.Vector3()).x) < 1e-6);
    let mesh; base.traverse(part => { if (part.isMesh) mesh = part; });
    assert.ok(mesh.material.map && mesh.material.normalMap && mesh.material.roughnessMap);
    c.TATerrain.textureName = name;
    const ghost = new T.Group(); root.add(ghost); ghost.userData.reflecting = true;
    await c.mountTerrainBase(ghost, {width: 2.4, top: .38, ghost: true});
    let ghostMesh; ghost.traverse(part => { if (part.isMesh) ghostMesh = part; });
    assert.equal(ghostMesh.geometry, mesh.geometry);
    assert.equal(ghostMesh.material.map, mesh.material.map);
    assert.notEqual(ghostMesh.material, mesh.material);
    assert.equal(ghostMesh.material.opacity, mesh.material.opacity * .55);
    assert.equal(ghostMesh.material.depthWrite, false);
    assert.equal(base.userData.sharedRelicResources, true);
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
    const pending = c.mountTerrainBase(group, {width: 3.6, top: .42});
    if (stale === 'disposed') group.userData.disposed = true;
    else c.layoutGeneration++;
    finish(mesh); await pending;
    assert.equal(group.children.length, 0);
    assert.equal(disposed, true);
    assert.equal(group.userData.terrainBaseReady, false);
  }
});
