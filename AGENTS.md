# Atlas of Threads contributor instructions

Atlas of Threads is a local-first application built on the Thought Archaeology
Framework. Keep changes aligned with `docs/DESIGN.md`; do not invent a parallel
schema, CLI, store, or browser authority.

## Development rules

- Prefer direct, idiomatic code and a flat architecture.
- Keep JSON canonical and stored graph and turn records append-only.
- Treat Depth-1 graphs as an inspectable story layer, never hidden
  chain-of-thought or a faithful neural trace.
- Keep semantic decisions in Python. Browser adapters should remain thin, and
  provider credentials must stay isolated from rendered content.
- Preserve documented compatibility behavior unless a deliberate migration is
  part of the change.
- Networking, accounts, and a shared Atlas remain future work unless explicitly
  requested.

## Verification

Run the focused tests for the area you changed, then the complete suite before a
release:

```bash
pytest -q
node --check viz/dist/space.js
node --check viz/dist/sound.js
```

Packaging and release changes must also exercise the standalone application and
the relevant installer workflow.

## Public repository safety

- Never commit credentials, live user data, local knowledge-base contents, or
  private conversation exports.
- Fixtures must be synthetic and clearly documented as such.
- Preserve third-party and generated-asset notices when assets change.
- Keep `SECURITY.md`, `CONTRIBUTING.md`, and `docs/PUBLIC_PREVIEW.md`
  current with the product.
