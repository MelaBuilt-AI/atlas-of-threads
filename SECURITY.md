# Security policy

Atlas of Threads `0.x` is a local-first Personal Atlas powered by the Thought
Archaeology Framework. It has no hosted account, public graph service, or
shared Atlas connection.

## Supported versions

Security fixes currently target the latest `0.x` release on the default branch.
There is no long-term-support branch during the Public Local Preview.

## Reporting a vulnerability

Use the repository's private GitHub security-advisory flow. Do not open a
public issue containing credentials, private graph content, local paths, model
transcripts, or an exported Knowledge Capsule.

Include the smallest reproduction that demonstrates the issue. Synthetic data
is preferred. Never attach a real Personal Atlas store when a reduced fixture
can reproduce the problem.

## Local security boundary

- `ta serve` accepts loopback binds only (`127.0.0.1`, `localhost`, or `::1`).
- The local browser surface can write forks, vetoes, continuation requests,
  Field Notes, and Knowledge Capsules to the selected store. Treat access to an
  unlocked desktop session as access to that Personal Atlas.
- Graphs and source artifacts are append-only. Private exports are created with
  owner-only permissions where the platform supports them.
- Provider credentials are owned by provider CLIs and are not stored in the
  Thought Archaeology store.
- A Knowledge Capsule launch writes a private local Markdown projection. It
  does not upload or publish the Capsule.

The future Atlas shared layer will require a separate network threat model,
identity design, consent boundary, and security review before it is enabled.
