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

`viz/dist` is the committed static build. Node/Vite is optional and only needed if you change the scene sources. `ta serve` must work with Python alone.
