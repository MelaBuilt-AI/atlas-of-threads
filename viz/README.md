# Inhabit Space

You stand at a thought-node. This is not a dashboard.

`ta serve` serves `viz/dist/` (committed). Python only; no Node required to inhabit.

Gestures from the chamber:

- `f` fork — cut a continuation; you stay at the discarded chamber; a bronze ring is the path you kept
- `v` veto — the chamber remains, with a human no; you follow into the vetoed graph
- `b` back — walk to the parent cut
- arrows: left/right **preview** a path in front (no walk). Enter walks the focused path. No paths → keys do nothing. Up deeper, down/`b` retrace.
- `e` descends through the typed evidence strata beneath the standing thought. When nothing is attached, the descent says that absence is not evidence.
- `c` cycles camera: overhead map of the grid, then back behind the chamber. Drag pans the map overhead. Shift+c returns behind the home chamber. Overhead gets extra sun/hemisphere light.
- `r` opens the relic index. Its 24 PNG cards document the vocabulary of forms. Choosing one previews its matching GLB at the standing chamber without changing graph data; Escape restores the semantic mapping.
- click a ring to enter that graph

The chamber also polls the local store for newly finalized graph heads. A graph
written by `ta compile` while the space is open rises as a teal doorway beside
the current thought; it never teleports the inhabitant. Walking through marks
that arrival seen but keeps a quieter recent-thought doorway in both directions.
The bounded companion memory survives refreshes in the browser; graph data stays
canonical in the local store. This is turn-level companionship after an answer
is complete, not token streaming or hidden chain-of-thought access.

The sky is a starfield (not the floor). The floor is a grid whose cell is the default claim chamber footprint (1.4). Path chambers sit on that grid at a stride of 3 cells so they do not overlap. Chambers rise when they spawn.

The inhabited relic keeps a key spotlight in both over-the-shoulder and overhead
views. Left/right selection moves a second spotlight from path to path. Enter
walks into the preview, where the newly inhabited relic takes over the key light.

Writes go through `/api/fork` and `/api/veto`. Do not compute the omit-set in `space.js`.

Fingerprint is **climate**: fog and light at the standing node (recurring judgment, human no, divergence). Not a chart of clusters. Python scores; JS paints.

## Relics

Thought chambers use the generated GLBs under `dist/assets/models/`. The small
loader in `dist/relic-loader.js` reads their embedded base-color,
metallic/roughness, normal, specular, and volume properties into Three.js
physical materials. A procedural environment map supplies the reflections.

The default form follows the thought kind. Evidence on the standing node takes
precedence: provenance becomes the lens, behavioral intervention the intervened
claim, activation correlation the scanner, neural intervention the key,
recurrence the crucible, and checkpoint emergence the stratigraphic core.
Fork and return portals use the compass and counterfactual gate.

Pressing `e` opens one archaeological record with a strict boundary: a
server-authored **why this path** section shows the story graph's recorded
supports, judgments, analogies, qualifications, descendants, and rejected
roads; separate strata below show what evidence has actually tested.
Because path relations are authored by Python, restart `ta serve` after updating
the project code; refreshing alone updates the static surface but not an already
running server process. A mismatched surface says this explicitly instead of
showing an unexplained empty story section.

Regenerate the runtime assets from a source folder of matching `.glb`/`.png`
pairs with:

```bash
python tools/import_relic_assets.py SOURCE_DIR viz/dist/assets
```

The importer keeps geometry and PBR channels intact, resizes embedded runtime
textures to 1K, and creates 360px PNG index cards. The chamber remains local and
requires no CDN or Node build.

Dev with Node is optional — edit `viz/dist/space.js` directly.

## Cinematic capture

For an event recording, open an isolated store with `?cinematic=1` appended to
the Inhabit Space URL. Press `x` to begin an 11-second, HUD-free WebM recording
of the WebGL canvas, then trigger the real event. The capture camera tracks a
ready Knowledge Capsule and its flight; ordinary sessions retain the normal
camera and renderer behavior.

## Sound

The twelve runtime files under `dist/assets/audio/` are the browser-ready
48 kHz OGG/Opus derivatives from the original Thought Archaeology cinematic
sound pack. The archival 24-bit WAV masters remain outside the repository in
the shared project vault. `dist/sound.js` prefetches the OGGs, waits for a user
gesture before creating its `AudioContext`, queues a first interaction cue while
decoding, and fades the atmosphere, AI-working, and green-spark loops through a
shared compressor. Do not layer the replaced procedural beds under these files;
their low-frequency energy is intentionally designed to combine only at the
documented conservative gains.
