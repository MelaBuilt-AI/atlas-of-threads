/* Geographic map roads, independent of thought-graph relationships. */
(() => {
  "use strict";
  window.AtlasRoadMap = (publications) => {
    const ordered = [...publications].sort((a, b) => a.sequence - b.sequence);
    return ordered.slice(1).map((target, index) => {
      let source = ordered[0], distance = Infinity;
      for (let i = 0; i <= index; i++) {
        const candidate = ordered[i];
        const d = (candidate.x - target.x) ** 2 + (candidate.z - target.z) ** 2;
        // Sequence order breaks exact distance ties, independent of fetch order.
        if (d < distance) { source = candidate; distance = d; }
      }
      return { id: target.threadwalk_id || target.id, source, target };
    });
  };
})();
