# Contributing

Schema and operations are specified in `docs/DESIGN.md`. Implement that document; do not invent a parallel schema, CLI, or store.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

Python 3.11+.

## Rules

- JSON is canonical. Graphs and `turns.jsonl` are write-once.
- Depth-1 graphs are the *story*, not a circuit trace. No weight access in v1.
- Tests assert `(kind, text, status)` and edge triples, never compiled ULIDs (except canvas/inhabit fixtures that fix ids on purpose).
- Do not add a `personality` node kind.
- Do not write `wiki/index.md` or `wiki/log.md` from `ta`.
- Inhabit Space may fork/veto, but omit-set lives in Python. Do not reimplement it in JavaScript. Gestures POST to `/api/fork` and `/api/veto`.

## Visual layer

Portable inquiry tests use separate synthetic publisher/recipient stores.
Preserve the read-only imported boundary and exact source identities described
in [portable inquiries](docs/PORTABLE_INQUIRIES.md).

`viz/dist` is the committed static build. Node/Vite is optional and only needed if you change the scene sources. `ta serve` must work with Python alone.


The online preview lives in `online/`; run `npm ci`, `npm run build`, and
`npm test` there. It compiles the same portable and shared Capsule schemas and copies the committed
Atlas renderer/media. Python prepares chamber semantics; do not implement a
second fork/veto engine in the Worker. Synthetic fixture generation is explicit
and never reads a user store. Deployment is separate from tests and requires
scoped Cloudflare credentials; never commit local deployment configuration.

Connected Capsule tests use synthetic accounts and the real local D1 runtime.
Keep receipt, explicit source-owner decisions and graph import distinct. Add
numbered migrations rather than rewriting deployed tables; transport must preserve
canonical JSON strings and retry the original delivery identity. Never seed real
Capsules or invoke a real collaborator for a transport test.

Expedition events must commit with delivery/acceptance and inherit delivery visibility.
Preserve edition update sequences in migrations. Test observer watermarks and hidden/
offline gaps without replaying historical deliveries or taking control of the camera.


Returned doorways reuse full portable snapshots and exact source references.
Keep contributor publication, connection offering, public acceptance, local import
and browser visit state separate. Do not derive links from graph resemblance or
publish a private Capsule decision as a shared relationship. Exercise the shared
and native entry-return paths without mutating source graphs or calling real agents.
