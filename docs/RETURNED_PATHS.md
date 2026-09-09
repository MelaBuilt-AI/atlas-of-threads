# Private continuations and returned paths

Development increment in the [combined online milestone](ONLINE_ATLAS.md).
This is a local two-store loop, not hosted delivery or a released feature.

## Use it

While visiting an imported inquiry, choose **Continue privately**, write a
question, and review the exact answer/thought/source context and currently
selected collaborator. Confirming creates a separate local Threadwalk and queues
the ordinary local worker. The imported inquiry and existing session heads stay
unchanged. Use the local Workspace to choose a different collaborator first.

In your own Atlas, **Returned paths** lists private continuations. Once a response
has completed, enter a sharing name, review every graph and exact JSON, and save
an `.atlas-return.json` offer. Sharing is a separate action; saving does not send
the file anywhere. Private guide conversations and source-context metadata are
not included. As with portable inquiries, review graph prose for private text.

The original source inhabitant chooses the offer file, inspects its contents,
and receives it into a pending inbox. **Review path** reopens the saved contents;
accepting imports the offered snapshot and exposes an entry link at the exact
source chamber. Declining leaves it inert. Accepted paths offer **Return to source
chamber**. Repeated receipt/acceptance reuses the same offer and snapshot. A
decision is final for that exact offer in this initial increment.

## Contract

- Ordinary Store sessions/graphs/turns and continuation requests/completions own
  the private continuation. The initial human question graph carries the exact
  selected public answer, thought and source references in `metadata.external_inquiry`.
  Existing adapters treat that graph context as quoted data, not instructions.
- Context is limited to 64 KiB; the question uses the existing 400-character
  limit. Larger source context is rejected for review rather than silently cut.
- A local `sessions/<id>/external-source.json` receipt pins the seed graph,
  source and question. It is not added to the portable inquiry format.
- A version-1 `atlas-return-path` envelope contains a content hash, source
  reference, question and ordinary portable inquiry bundle. Its entire serialized
  size is bounded to 8 MiB. Returned graph bundles retain the portable validator.
- Sources identify origin, inquiry snapshot, session, graph and node, and both
  original graph-file and shared-projection hashes. Receipt checks the target's
  local origin, exact immutable source bytes and selected node before writing.
- Offers live under `return-paths/offers/`; decisions under `return-paths/decisions/`.
  Atomic files and the existing local continuation lock serialize mutations.
  Acceptance materializes a separate imported inquiry before publishing its
  decision. No receive/accept action queues an agent request.
- Portable sharing names and offers are publisher assertions, not signatures.
  Matching source hashes prove which source is named, not verified authorship
  or that the offered reasoning follows from it. Network identity comes later.

Local HTTP actions use `/api/return-paths/{preview,begin,export,inspect,receive,decide}`
and the existing same-origin JSON checks. Read APIs list private paths/offers,
retrieve saved offers for review and expose source links/accepted arrivals at an
exact chamber. These are local APIs; the existing server remains loopback-only.

## Verification and remaining work

Synthetic tests exercise the actual continuation worker, exact prompt context,
unchanged source graphs/heads/imports, sanitized export, malformed/misaddressed
offers with zero writes, duplicate receipt/acceptance, decline, and HTTP use.
Browser checks cover context review, local worker completion, saved-offer review,
explicit acceptance, entry and exact-source return. The test adapter is synthetic;
these checks do not claim a new real provider response or physical Windows
returned-path acceptance. The earlier portable two-PC acceptance is separate.

Native 3D arrival doors/unread traversal, revising a decision, offer withdrawal,
delivery receipts across a network, official identity and hosted routing remain
in the combined milestone. No graph schema or portable version bump is needed
for this local increment.
