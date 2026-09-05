# Atlas of Threads

<p align="center">
  <a href="https://atlasofthreads.com">
    <img src="https://atlasofthreads.com/og.png" alt="Atlas of Threads — enter an idea and walk its architecture" width="900">
  </a>
</p>

<p align="center">
  <strong>A local-first AI knowledge-mapping platform.</strong><br>
  Turn model answers into traversable thought-graphs, challenge paths, compare
  collaborators, and preserve what matters.
</p>

<p align="center">
  <a href="https://github.com/MelaBuilt-AI/atlas-of-threads/actions/workflows/test.yml"><img src="https://github.com/MelaBuilt-AI/atlas-of-threads/actions/workflows/test.yml/badge.svg" alt="Tests"></a>
  <a href="https://github.com/MelaBuilt-AI/atlas-of-threads/releases/tag/v0.2.0"><img src="https://img.shields.io/badge/release-v0.2.0-35d5e8" alt="Release v0.2.0"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-ffb455" alt="MIT license"></a>
</p>

<p align="center">
  <a href="https://atlasofthreads.com/threadwalk/filiolae"><strong>Threadwalk now — Make Equivalence Visible</strong></a>
  ·
  <a href="https://atlasofthreads.com"><strong>Visit the Atlas</strong></a>
  ·
  <a href="https://app.atlasofthreads.com"><strong>How to play</strong></a>
  ·
  <a href="https://downloads.atlasofthreads.com/releases/latest/AtlasOfThreadsSetup.exe"><strong>Download for Windows</strong></a>
  ·
  <a href="https://github.com/MelaBuilt-AI/atlas-of-threads/releases/tag/v0.2.0"><strong>Release notes</strong></a>
</p>

---

## An answer is terrain, not a verdict

Most AI conversations flatten a question, an answer, and all the roads not
taken into a scrolling transcript. Atlas of Threads turns the public structure
of an answer into a place you can inhabit.

Each answer becomes a graph of thought-objects:

- claims;
- premises;
- analogies;
- judgment calls;
- uncertainties; and
- rejected alternatives.

You can walk between them, return to their origin, cut a path, inscribe a human
objection, ask another collaborator to continue from an exact chamber, and
preserve your own interpretation without manufacturing consensus.

Atlas does **not** expose hidden chain-of-thought or pretend that a model's
explanation is a neural trace. The graph is the inspectable story of the answer.
When causal evidence exists, it occupies a separate evidence layer with an
explicitly bounded claim.

## What ships in v0.2.0

The current release creates a private **Personal Atlas** on your computer.

- **Inhabit Space** — move through answers as spatial chambers instead of a
  transcript or dashboard.
- **Provider-neutral continuations** — continue an exact thought through Claude
  Code, Codex CLI, Grok Build, OpenCode, or Prime Agent.
- **Parallel Continuations** — ask multiple collaborators the same question
  from the same chamber and inspect their paths separately.
- **Cuts and human vetoes** — create append-only forks that preserve the source
  graph and make disagreement visible.
- **Thread Compass** — read the complete generation lineage of one inquiry.
- **Atlas Map** — move across a stable top-down projection of the Threadwalk.
- **Human Field Notes** — select exact thoughts and record what mattered in your
  own words, with append-only revisions.
- **Knowledge Capsules** — freeze a completed, human-interpreted milestone into
  a private, integrity-verifiable Markdown dossier.
- **Evidence descents and relics** — keep story structure, provenance,
  behavioral tests, and causal evidence distinct.
- **Release-only updates** — update only to deliberate, tagged GitHub Releases;
  ordinary commits never become client updates.

The full end-to-end experience is documented in the
[inhabitant's field guide](https://app.atlasofthreads.com).

## Install Atlas

Atlas is distributed as a self-contained local application. You do not need
Python, Git, a virtual environment, or `pip` for the packaged experience.

### Windows

[Download the current per-user installer][windows-installer], run it, and
finish setup. Atlas starts and opens its local browser view automatically.

The current package is unsigned, so Windows or a browser may show an
unrecognized-publisher warning. The installer does not require administrator
access. See [installer and signing details](docs/INSTALLERS.md#windows-download-trust).

### Linux

```bash
curl -fsSL https://atlasofthreads.com/install.sh | sh
```

The installer downloads the current tagged binary and matching SHA-256 file,
verifies it, installs it in the user's XDG data directory, starts Atlas, and
prints the local URL.

[windows-installer]: https://downloads.atlasofthreads.com/releases/latest/AtlasOfThreadsSetup.exe

## Your first Threadwalk

1. Open Atlas and choose **Set up collaborators**.
2. Select a supported provider CLI already configured on the machine. On
   Windows, Atlas can open the official installer and provider-owned sign-in
   flow for Claude Code, Codex, or Grok.
3. Complete authentication with the provider, then choose **Check again**.
4. Activate one ready collaborator.
5. Write a real opening inquiry and choose **Start a Threadwalk**.
6. Enter the blue arrival when the collaborator's path completes.

From a chamber:

| Move | Control |
|---|---|
| Cycle among paths | `←` / `→` or `[` / `]` |
| Enter the selected path | `Enter` or `↑` |
| Retrace | `↓` or `B` |
| Return to this answer's start | `O` |
| Continue this ending | `Q` or **Ask from here…** |
| Request parallel paths | `P` |
| Open Thread Compass | `T` |
| Open Atlas Map | `A` |
| Open Workspace | `M` |
| Open legend and all controls | `L` |

The standing thought and selected destination have separate cards. Click a path
to preview it before entering. The top wayfinder names your retrace destination
and offers a recent trail; collaborator answers also name their source thought.
The Atlas Map opens exact thoughts and can switch to **All answers**. Select an
answer, then **Thoughts in this answer** to inspect its internal paths without
losing your place. Current and previously visited locations are marked.

The [field guide](https://app.atlasofthreads.com) covers every control, visual
signal, lifecycle, and troubleshooting path.

## Collaborators remain independent

Atlas provides thin bridges to model-provider command-line tools. It does not
bundle provider executables, receive credentials, choose billing routes, or
change subscription eligibility.

| Collaborator | Packaged bridge | Guided native Windows setup |
|---|---:|---:|
| Claude Code | Yes | Yes |
| Codex CLI | Yes | Yes |
| Grok Build | Yes | Yes |
| OpenCode | Yes | No — configure its CLI first |
| Prime Agent | Yes | No — configure its CLI first |

The adapter's `describe` handshake confirms that a CLI can answer and reports
its current public model/version. A desktop chat application alone is not a
bridge. Native Windows and WSL authentication may also be separate.

Atlas records the provider and exact model reported for each completed graph.
Switching the active collaborator affects future continuations only; it never
rewrites stored attribution.

For the protocol and provider-specific boundaries, read
[Harness adapters](docs/HARNESS_ADAPTERS.md).

## Local-first ownership

The packaged application binds only to `127.0.0.1`. The browser is a view into
the application running on your machine; closing the tab does not delete data
or necessarily quit the local process.

- Graphs, turns, continuations, failures, cancellations, Field Notes, and
  Capsules live in the user's local store.
- Provider authentication remains in each provider's own configuration,
  keychain, or login session.
- Atlas has no account, cloud sync, remote publication, or shared-world service
  in this release.
- Knowledge Capsule exports are private local Markdown files. Creating one is
  not a publication action.
- The small release check reads only the anonymous public release manifest.

On Windows, three idle `AtlasOfThreads.exe` processes are normal: the packaged
application parent and child plus the collaborator worker. Use
**Workspace → Quit Atlas** to stop the server and worker cleanly.

## The language of the Atlas

| Term | Meaning |
|---|---|
| **Atlas of Threads** | The product and platform. |
| **Thought Archaeology Framework** | The discovery and knowledge-extraction methodology powering Atlas. |
| **Personal Atlas** | One person's private mapped reality on their machine. |
| **The Atlas** | A future shared layer connecting deliberately published paths from independently owned Personal Atlases. It is not part of v0.2.0. |
| **Threads** | AI thoughts, memories, conversations, decisions, and reasoning. |
| **Weaving** | Connecting Threads without erasing their origins. |
| **Threadwalk** | Traversing connected thoughts and graph generations. |

The implementation intentionally retains the `thought-archaeology` Python
package, `ta` command, schemas, protocols, and store paths. Those names identify
the framework and local tooling; they are not legacy aliases awaiting a rename.
See [the product boundary and release horizons](docs/ATLAS_OF_THREADS.md).

## Thought Archaeology Framework

Thought Archaeology keeps the human-readable graph and the evidence attached to
it in distinct layers:

```text
human inquiry
    └── public model answer
            └── thought-graph (story structure)
                    ├── continuations, cuts, and vetoes
                    ├── human Field Notes
                    └── evidence bindings
                            ├── context provenance
                            ├── behavioral interventions
                            ├── activation correlations
                            ├── neural interventions
                            └── checkpoint provenance
```

The same thought-objects remain the coordinate system at every depth. Evidence
bindings state whether a concrete artifact supports, contradicts, or is
inconclusive about one bounded claim. Missing evidence remains missing.

The complete technical and scientific boundary lives in
[DESIGN.md](docs/DESIGN.md).

## Develop from source

Requirements:

- Python 3.11 or 3.12;
- `jsonschema` at runtime; and
- `pytest` and the other declared development dependencies for contribution.

```bash
git clone https://github.com/MelaBuilt-AI/atlas-of-threads.git
cd atlas-of-threads
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest -q
```

Start a minimal local graph:

```bash
ta init --title demo
ta compile --session <SESSION_ID> --mode posthoc \
  --transcript fixtures/transcripts/simple-freeform.jsonl \
  --from-graph fixtures/graphs/simple.gold.json
ta show <SESSION_ID> --format tree
ta serve
```

Then open `http://127.0.0.1:7462/`.

`atlas-of-threads` and `ta launch` start the same local application and open the
default browser. `ta launch --no-browser` prints the URL without opening it.

### Store location

The first matching location wins:

1. `--store PATH`;
2. `TA_STORE`;
3. `./data` when that directory already exists; or
4. `$XDG_DATA_HOME/thought-archaeology`, falling back to
   `~/.local/share/thought-archaeology`.

Source graphs and durable receipts are immutable. Session head metadata moves
forward as new append-only generations arrive. The browser renders
server-authored read models and does not become the authority for graph or
evidence semantics.

### Useful CLI surfaces

```bash
# inspect and validate
ta show ID --format tree
ta validate PATH_OR_ID
ta log SESSION_ID

# graph operations
ta inhabit NODE --session SESSION_ID
ta fork NODE --session SESSION_ID --reason "why this path is cut"
ta veto NODE --session SESSION_ID --reason "human objection"

# continuations and comparisons
ta continuation pending --format json
ta continuation compare NODE --graph GRAPH_ID
ta harness configure
ta harness doctor
ta harness watch

# human interpretation and export
ta field-note list --format table
ta capsule list --format table
ta capsule show CAPSULE_ID
```

Run `ta --help` and `ta <command> --help` for the complete command surface.
Provider-neutral continuation is an append-only JSON/filesystem/local-HTTP
contract; no vendor SDK or callback URL is required by the core.

### Validation and policy

```bash
pytest -q
node --check viz/dist/space.js
node --check viz/dist/sound.js
```

The test workflow runs on Python 3.11 and 3.12. Package workflows build and
smoke-test Windows and Linux artifacts for private acceptance, but only a stable
`vMAJOR.MINOR.PATCH` GitHub Release may advance the public update channel.

CLI exit codes are `0` for success, `1` for validation or strict-policy failure,
`2` for usage, `3` for I/O, and `4` for a deliberately unsupported operation.

## Documentation map

| Document | Purpose |
|---|---|
| [How to play](https://app.atlasofthreads.com) | Complete end-user journey and controls |
| [Atlas of Threads](docs/ATLAS_OF_THREADS.md) | Product language, boundaries, and release horizons |
| [Installers](docs/INSTALLERS.md) | Windows/Linux packaging, signing, releases, and updates |
| [Harness adapters](docs/HARNESS_ADAPTERS.md) | Provider-neutral adapter protocol and worker behavior |
| [Parallel Continuations](docs/PARALLEL_CONTINUATIONS.md) | Exact-source comparison and routed requests |
| [Human Field Notes](docs/FIELD_NOTES.md) | Human authorship, exact references, and revision rules |
| [Knowledge Capsules](docs/KNOWLEDGE_CAPSULES.md) | Eligibility, frozen manifests, launch, and privacy |
| [Technical design](docs/DESIGN.md) | Data model, evidence layers, architecture, and guardrails |
| [Public-release audit](docs/PUBLIC_PREVIEW.md) | Publication record and repeatable release checks |
| [Third-party notices](THIRD_PARTY_NOTICES.md) | Vendored-code and generated-asset provenance |

## Current boundary

Atlas of Threads v0.2.0 is a local Personal Atlas, not a hosted knowledge
network. **The Atlas**—a shared world connecting only what inhabitants
deliberately publish—is the long-term direction. This repository does not add
accounts, upload local graphs, infer consensus, or claim that the shared layer
already exists.

## License

[MIT](LICENSE). Atlas of Threads is a project from MelaBuilt AI. See the
[third-party and generated-asset notices](THIRD_PARTY_NOTICES.md).
