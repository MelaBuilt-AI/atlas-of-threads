/* Tab-local experienced route and stable positions. Graphs remain server-owned. */
(function (scope) {
  const key = (ref) => `${ref.graphId}/${ref.nodeId}`;
  const same = (a, b) => Boolean(a && b && key(a) === key(b));

  function create(saved = {}) {
    let path = saved.path || [];
    let cursor = saved.cursor ?? path.length - 1;
    let reflecting = Boolean(saved.reflecting);
    const positions = new Map(saved.positions || []);
    const visited = new Map(saved.visited || []);
    const segments = new Map(saved.segments || []);
    const connections = new Map(saved.connections || []);
    return {
      get path() { return path; },
      get cursor() { return cursor; },
      get reflecting() { return reflecting; },
      get current() { return path[cursor]; },
      get anchor() { return path[path.length - 1]; },
      get previous() { return path[cursor - 1]; },
      get visited() { return [...visited.values()]; },
      get segments() { return [...segments.values()]; },
      get connections() { return [...connections.values()]; },
      connect(from, to) { connections.set(`${key(from)}>${key(to)}`, [from, to]); },
      position(ref) { return positions.get(key(ref)); },
      place(ref, proposed) {
        if (!positions.has(key(ref))) {
          const point = { ...proposed };
          while ([...positions.values()].some((p) => Math.hypot(p.x - point.x, p.z - point.z) < 3)) {
            point.x += 3.5;
          }
          positions.set(key(ref), point);
        }
        return positions.get(key(ref));
      },
      beginReflect() { reflecting = true; },
      accept(ref, origin = "walk") {
        // Commit only after the canonical chamber request has succeeded.
        const previous = path[cursor];
        if (origin === "reflect-step" && reflecting && same(ref, path[cursor - 1])) {
          cursor -= 1;
        } else if (origin === "reflect-return" && reflecting && same(ref, path[path.length - 1])) {
          cursor = path.length - 1;
          reflecting = false;
        } else {
          if (previous && !same(previous, ref)) segments.set(`${key(previous)}>${key(ref)}`, [previous, ref]);
          if (reflecting) path = path.slice(0, cursor + 1);
          reflecting = false;
          const prior = path.findLastIndex((item) => same(item, ref));
          if ((origin === "return" || origin === "back") && prior >= 0) path = path.slice(0, prior + 1);
          else if (!same(path[path.length - 1], ref)) path.push(ref);
          cursor = path.length - 1;
        }
        visited.set(key(ref), ref);
      },
      residents(limit = 16) {
        // Only nearby references become scenery; long history stays lightweight metadata.
        const center = positions.get(key(path[cursor]));
        if (!center) return path.slice(Math.max(0, cursor - limit + 1), cursor + 1);
        const refs = new Map([...connections.values()].map(([, to]) => [key(to), to]));
        visited.forEach((ref, id) => refs.set(id, ref));
        const distance = (ref) => {
          const point = positions.get(key(ref));
          return point ? Math.hypot(point.x - center.x, point.z - center.z) : Infinity;
        };
        return [...refs.values()].filter((ref) => distance(ref) < 65)
          .sort((a, b) => distance(a) - distance(b)).slice(0, limit);
      },
      save() { return { path, cursor, reflecting, positions: [...positions], visited: [...visited], segments: [...segments], connections: [...connections] }; },
    };
  }
  const api = { create, key, same };
  if (typeof module !== "undefined") module.exports = api;
  else scope.TAWalk = api;
})(globalThis);
