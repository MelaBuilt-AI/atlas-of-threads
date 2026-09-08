const { test } = require('node:test');
const assert = require('node:assert/strict');
const terrain = require('../viz/dist/terrain.js');

test('ten Threadwalks receive distinct surfaces; revisits and reload retain their place', () => {
  const saved = {};
  const names = Array.from({length: 10}, (_, i) => terrain.assignTexture(`thread-${i}`, saved));
  assert.equal(new Set(names).size, 10);
  const restored = JSON.parse(JSON.stringify(saved));
  names.forEach((name, i) => assert.equal(terrain.assignTexture(`thread-${i}`, restored), name));
  for (let i = 10; i < 30; i++) terrain.assignTexture(`thread-${i}`, restored);
  for (const name of terrain.TEXTURES) assert.equal(Object.values(restored).filter(x => x === name).length, 3);
});

test('travel and Reflect trace the same terrain curve in opposite directions', () => {
  const from = {x: -8, z: 14}, to = {x: 12, z: -24};
  assert.deepEqual(terrain.pointAlong(from, to, 0), from);
  const end = terrain.pointAlong(from, to, 1);
  assert.ok(Math.hypot(end.x-to.x, end.z-to.z) < 1e-10);
  for (let i = 0; i <= 20; i++) {
    const a = terrain.pointAlong(from, to, i/20);
    const b = terrain.pointAlong(to, from, 1-i/20);
    assert.ok(Math.hypot(a.x-b.x, a.z-b.z) < 1e-10);
  }
  assert.deepEqual(terrain.pointAlong(from, from, .5), from);
});
