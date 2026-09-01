# Atlas of Threads

Atlas of Threads is an AI knowledge-mapping platform powered by the **Thought
Archaeology Framework**. It is an open-source project from MelaBuilt AI.

This document defines the public product language. It does not rename the
implementation or authorize networking, identity, publication, or a shared
service.

## Product architecture

| Name | Public meaning |
|---|---|
| **Atlas of Threads** | The complete product and platform. |
| **Thought Archaeology Framework** | The discovery and knowledge-extraction methodology beneath the product. |
| **Personal Atlas** | One individual's private mapped reality. It remains locally owned and private by default. |
| **The Atlas** | The future collective knowledge layer built from many Personal Atlases in a shared plane. |
| **Threads** | AI thoughts, memories, experiences, conversations, decisions, and reasoning. |
| **Weaving** | Deliberately connecting Threads while preserving origin and attribution. |
| **Threadwalk** | Traversing connected ideas and memories. |

The canonical relationship sentence is:

> **Atlas of Threads is an AI knowledge-mapping platform powered by the Thought Archaeology Framework.**

The canonical creator line is:

> **An open-source project from MelaBuilt AI.**

## What exists now

The `0.x` application creates and inhabits a local Personal Atlas. It compiles
finalized model answers into inspectable thought-graphs, preserves rejected
roads and human interventions, supports attributed continuations from multiple
AI collaborators, lets the inhabitant write Field Notes, and can freeze a
completed local inquiry into a private Knowledge Capsule.

The local application is not a hosted account, social network, remote model
provider, public knowledge base, or shared Atlas client. It does not upload a
graph merely because the user launches a Knowledge Capsule.

## What comes later

The Atlas is the future shared plane. Independently owned Personal Atlases may
eventually publish selected, bounded regions and weave attributed paths between
them without merging private stores or manufacturing consensus.

That layer requires separately designed identity, consent, transport,
moderation, withdrawal, and conformance boundaries. Public language must never
present those capabilities as available before they exist.

## Implementation boundary

Keep these identifiers unchanged:

- Python distribution and module: `thought-archaeology` / `thought_archaeology`;
- command line: `ta` and `ta-harness-*`;
- environment and data paths such as `TA_STORE` and
  `~/.local/share/thought-archaeology`;
- schemas, artifact kinds, protocol names, systemd service identifiers, tests,
  and immutable historical records;
- methodology references where **Thought Archaeology** is the accurate subject.

Public-facing copy may use Atlas of Threads in the repository title and About
text, README opening, website, browser title and welcome surface, screenshots,
social previews, release notes, and onboarding. This is presentation-layer
language, not a store or protocol migration.

## Release horizons

- **Now — Personal Atlas:** private local graphs, Threadwalks, multiple
  collaborators, interventions, Field Notes, Knowledge Capsules, and evidence.
- **Next — Public Local Preview:** make the local application understandable,
  installable, safe, and useful to a small founding cohort.
- **Then — Portable weaving:** explicit bundles, remote references, and bounded
  exchange semantics after independent use exposes the real contract.
- **Later — The Atlas:** opt-in identity, discovery, publication, attributed
  cross-owner paths, presence, governance, and shared-world services.

## Public repository identity

- Owner: `MelaBuilt-AI`
- Repository: `atlas-of-threads`
- Website: `https://atlasofthreads.com`
- License: MIT
- Package and CLI: `thought-archaeology` / `ta`

The repository being open source does not make a fork part of the official
Atlas or grant it service identity, trust, compatibility, or governance status.
