const assert = require("node:assert/strict");
const { test } = require("node:test");
const { create, same } = require("../viz/dist/walk.js");
const ref = (i, graphId = "graph") => ({ graphId, nodeId: String(i), text: `Stop ${i}` });

test("Reflect traverses more than 80 visits with bounded residency and an exact return", () => {
  const walk = create();
  for (let i = 0; i < 120; i++) {
    walk.place(ref(i), { x: 0, z: -i * 6 });
    walk.accept(ref(i));
  }
  walk.beginReflect();
  for (let i = 118; i >= 0; i--) {
    assert(same(walk.previous, ref(i)));
    walk.accept(ref(i), "reflect-step");
    assert(walk.residents().length <= 16);
  }
  assert.equal(walk.path.length, 120);
  assert.equal(walk.previous, undefined);
  assert(same(walk.anchor, ref(119)));
  walk.accept(ref(119), "reflect-return");
  assert.equal(walk.cursor, 119);
  assert(!walk.reflecting);
});

test("an exact-stand reload preserves Reflect and its departure", () => {
  const walk = create();
  [0, 1, 2].forEach((i) => walk.accept(ref(i)));
  walk.beginReflect();
  walk.accept(ref(1), "reflect-step");
  const restored = create(JSON.parse(JSON.stringify(walk.save())));
  assert(restored.reflecting);
  assert(same(restored.current, ref(1)));
  assert(same(restored.anchor, ref(2)));
  restored.accept(ref(2), "reflect-return");
  assert.equal(restored.path.length, 3);
});

test("a branch from Reflect retains prior traveled segments and distinct graph provenance", () => {
  const walk = create();
  [0, 1, 2].forEach((i) => walk.accept(ref(i)));
  walk.beginReflect();
  walk.accept(ref(1), "reflect-step");
  walk.accept(ref(1, "another-graph"));
  assert(!walk.reflecting);
  assert.deepEqual(walk.path, [ref(0), ref(1), ref(1, "another-graph")]);
  assert(walk.visited.some((item) => same(item, ref(2))));
  assert(walk.segments.some(([a, b]) => same(a, ref(1)) && same(b, ref(2))));
});

test("revisiting loops preserves experienced order and fixed, non-overlapping placement", () => {
  const walk = create();
  const first = walk.place(ref(0), { x: 0, z: 0 });
  const branch = walk.place(ref(1), { x: 0, z: 0 });
  assert(Math.hypot(branch.x - first.x, branch.z - first.z) >= 3);
  assert.deepEqual(walk.place(ref(0), { x: 50, z: 50 }), first);
  [0, 1, 0, 2].forEach((i) => walk.accept(ref(i)));
  walk.beginReflect();
  assert(same(walk.previous, ref(0)));
  walk.accept(ref(0), "reflect-step");
  assert(same(walk.previous, ref(1)));
});

test("discovering a new continuation during Reflect leaves the departure and cursor intact", () => {
  const walk = create();
  [0, 1, 2].forEach((i) => walk.accept(ref(i)));
  walk.beginReflect();
  walk.accept(ref(1), "reflect-step");
  walk.place(ref(3, "new-head"), { x: 10, z: -20 });
  walk.connect(ref(2), ref(3, "new-head"));
  assert(same(walk.current, ref(1)));
  assert(same(walk.anchor, ref(2)));
  walk.accept(ref(2), "reflect-return");
  assert(same(walk.current, ref(2)));
});
