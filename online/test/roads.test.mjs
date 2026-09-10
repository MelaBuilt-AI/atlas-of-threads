import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const context = vm.createContext({ console, innerHeight: 900 });
context.window = context;
vm.runInContext(readFileSync("web/roads.js", "utf8"), context);
const node = (id, sequence, x, z) => ({ id, sequence, x, z });
const a = node("a", 1, 0, 0), b = node("b", 2, 30, 0), c = node("c", 3, 28, 20);
const links = (items) => Array.from(context.AtlasRoadMap(items), edge => [edge.source.id, edge.target.id]);

test("map roads choose the nearest earlier publication regardless of input order", () => {
  assert.deepEqual(links([c, a, b]), [["a", "b"], ["b", "c"]]);
  assert.deepEqual(links([a]), []);
  assert.deepEqual(links([]), []);
  const tied = node("tie", 4, 15, 0);
  assert.equal(context.AtlasRoadMap([tied, c, b, a]).at(-1).source.id, "a");
});

test("new arrivals add one road without rewiring existing roads; withdrawal reconnects survivors", () => {
  const d = node("d", 4, 29, 22);
  assert.deepEqual(links([a, b, c, d]), [["a", "b"], ["b", "c"], ["c", "d"]]);
  assert.deepEqual(links([a, c, d]), [["a", "c"], ["c", "d"]]);
});

test("road bundles form toward the new locale, retain existing meshes, and dispose obsolete routes", () => {
  vm.runInContext(readFileSync("../viz/dist/three.min.js", "utf8"), context);
  const T = context.THREE;
  T.TextureLoader.prototype.load = () => new T.Texture();
  vm.runInContext(readFileSync("web/weave.js", "utf8"), context);
  const scene = new T.Scene();
  const renderer = { capabilities: { getMaxAnisotropy: () => 4 }, getPixelRatio: () => 1 };
  const weave = context.AtlasWeave(scene, renderer, false);
  for (const item of [a, b, c]) { item.group = new T.Group(); item.group.position.set(item.x, 0, item.z); }
  weave.syncRoads(context.AtlasRoadMap([a, b]));
  const first = weave.roads.get("b");
  assert.equal(first.group.children.filter(object => object.isMesh).length, 3); // Two light meshes and a pick surface.
  weave.update(1000, 100);
  assert.equal(first.growth.value, 0);
  weave.update(2200, 100);
  assert.equal(first.growth.value, .5);
  weave.update(4000, 100);
  assert.equal(first.growth.value, 1.03);
  weave.syncRoads(context.AtlasRoadMap([a, b, c]));
  assert.equal(weave.roads.get("b"), first);
  const arrival = weave.roads.get("c");
  assert.equal(arrival.birth, null);
  assert.ok(Math.abs(arrival.curve.getPointAt(0).x - b.x) < 1e-9);
  assert.ok(Math.abs(arrival.curve.getPointAt(1).x - c.x) < 1e-9);
  assert.ok(Math.abs(arrival.curve.getPointAt(1).z - c.z) < 1e-9);
  for (const road of weave.roads.values()) road.group.traverse(object => {
    if (!object.geometry) return;
    const p = object.geometry.attributes.position;
    assert.ok(p.array.every(Number.isFinite));
    if (object.geometry.index) assert.ok(object.geometry.index.array.every(index => index < p.count));
  });
  let disposed = false;
  first.pick.geometry.addEventListener("dispose", () => { disposed = true; });
  weave.syncRoads(context.AtlasRoadMap([a, c]));
  assert.ok(disposed);
  assert.equal(first.group.parent, null);
  assert.equal(weave.roads.get("c").edge.source.id, "a");
  const quiet = context.AtlasWeave(new T.Scene(), renderer, true);
  quiet.syncRoads(context.AtlasRoadMap([a, b]));
  quiet.update(1000, 100);
  assert.equal(quiet.roads.get("b").growth.value, 1.03);
  quiet.update(9000, 100);
  assert.equal(quiet.roads.get("b").growth.value, 1.03);
});

test("open-world refresh discovers arrivals, removes withdrawals and preserves loaded pagination", async () => {
  const elements = new Map(), intervals = [];
  const element = () => ({
    children: [], hidden: false, textContent: "",
    addEventListener() {}, setAttribute() {},
    append(child) { child.parent = this; this.children.push(child); },
    remove() { this.parent.children = this.parent.children.filter(child => child !== this); },
    replaceChildren() { this.children = []; },
  });
  const $ = id => {
    if (!elements.has(id)) elements.set(id, element());
    return elements.get(id);
  };
  $("visit").hidden = true;
  const entry = n => ({ id: String(n), threadwalk_id: String(n), edition: 1, sequence: n, x: n * 10, z: 0,
    title: `Synthetic ${n}`, owner: { login: "Synthetic publisher", verified: false },
    inquiry_id: "synthetic", thought_count: 1 });
  let published = [entry(1), entry(2), entry(3)];
  const requests = [];
  const ui = vm.createContext({
    console, performance, setInterval: fn => intervals.push(fn),
    matchMedia: () => ({ matches: true }),
    sessionStorage: { getItem: () => null }, addEventListener() {},
    document: { hidden: false, getElementById: $, createElement: element, querySelectorAll: () => [] },
    fetch: async path => {
      requests.push(path);
      if (path === "/api/me") return { ok: true, json: async () => ({ owner: null }) };
      const after = Number(new URL(path, "http://atlas.test").searchParams.get("after")) || 0;
      const page = published.filter(item => item.sequence > after).slice(0, 2);
      return { ok: true, json: async () => ({ publications: page, next: page.length === 2 ? page.at(-1).sequence : null }) };
    },
  });
  ui.window = ui;
  vm.runInContext(readFileSync("web/world.js", "utf8"), ui);
  const settle = () => new Promise(resolve => setImmediate(resolve));
  const titles = () => $("inquiry-list").children.map(button => button.children[0].textContent);
  await settle();
  assert.deepEqual(titles(), ["Synthetic 1", "Synthetic 2"]);
  $("more").onclick(); await settle();
  assert.deepEqual(titles(), ["Synthetic 1", "Synthetic 2", "Synthetic 3"]);
  published = [entry(1), entry(3), entry(4)];
  intervals[0](); await settle();
  assert.deepEqual(titles(), ["Synthetic 1", "Synthetic 3", "Synthetic 4"]);
  const count = requests.length;
  ui.document.hidden = true;
  intervals[0](); await settle();
  assert.equal(requests.length, count);
});
