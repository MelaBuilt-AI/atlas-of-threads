# Inhabit Space

You stand at a thought-node. This is not a dashboard.

`ta serve` serves `viz/dist/` (committed). Python only; no Node required to inhabit.

Gestures from the chamber:

- `f` fork — cut a continuation; you stay at the discarded chamber; a bronze ring is the path you kept
- `v` veto — the chamber remains, with a human no; you follow into the vetoed graph
- `b` back — walk to the parent cut
- arrows: left/right **preview** a path in front (no walk). Enter walks the focused path. No paths → keys do nothing. Up deeper, down/`b` retrace.
- `c` cycles camera: overhead map of the grid, then back behind the chamber. Drag pans the map overhead. Shift+c returns behind the home chamber. Overhead gets extra sun/hemisphere light.
- click a ring to enter that graph

The sky is a starfield (not the floor). The floor is a grid whose cell is the default claim chamber footprint (1.4). Path chambers sit on that grid at a stride of 3 cells so they do not overlap. Chambers rise when they spawn.

Writes go through `/api/fork` and `/api/veto`. Do not compute the omit-set in `space.js`.

Fingerprint is **climate**: fog and light at the standing node (recurring taste, human no, divergence). Not a chart of clusters. Python scores; JS paints.

Dev with Node is optional — edit `viz/dist/space.js` directly.
