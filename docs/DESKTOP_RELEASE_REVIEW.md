# Desktop release review

Prepared September 17, 2026. PR #5 remains draft. Stable v0.3.1 remains current;
no merge, version change, tag or stable publication has occurred.

## Proposed release

The combined milestone adds the connected Atlas to Linux and Windows Personal
Atlas. Visitors can publish a reviewed immutable inquiry, explore its Threadwalk,
continue an exact chamber privately and offer a reviewed contribution back.
Source-owner acceptance of a full returned inquiry creates an exact shared/native
doorway. Private excerpt acceptance does not publish a doorway.

It includes GitHub identity and device pairing, account revocation, reviewed
Capsule delivery, moderation, optional expiring activity and the shared overworld.
Audio follows the active tab; the connected score continues into a Threadwalk and
back. Saved Personal Atlas reading/navigation works offline.

Desktop scope is owner-approved. Mobile remains experimental, with a small notice
on narrow screens/touch devices. Touch controls, collapsible reading panels,
orientation and physical-device performance belong to a later milestone in this
same codebase. iPhone Safari runtime/audio passed the owner's observation; mobile
usability did not.

## Evidence

- Desktop runtime/package revision: `a3d95d19def80586351a6a97cae81000ad910fbd`.
  [Candidate package workflow](https://github.com/MelaBuilt-AI/atlas-of-threads/actions/runs/35245324106)
  passed Linux/Windows standalone and installer checks. Both dedicated test
  installations now run this candidate. The subsequent scope change affects only
  the connected-world notice and documentation; desktop payloads are unchanged.
- 441 Python and 60 online/audio tests passed at the audio revision. The 60 tests
  and online build also pass after the scope change. [Push CI](https://github.com/MelaBuilt-AI/atlas-of-threads/actions/runs/35245312069)
  and [PR CI](https://github.com/MelaBuilt-AI/atlas-of-threads/actions/runs/35245316266)
  provide the prior exact-runtime checks.
- Physical Linux/Windows Capsule exchange, private continuation, return
  acceptance, doorway navigation and Windows restart were accepted. Windows
  Ethernet-off reload, saved reading/navigation and reconnection were accepted.
- The owner accepted repaired Windows tab isolation, effects/music in Personal
  and connected Atlas, and continuous overworld/Threadwalk music. Updating the
  test installations preserved all 20 Windows and 42 Linux saved JSON files and
  their pairings. Linux's served assets match the verified package source.
- Live GitHub revocation/reconnection and inert duplicate webhook delivery passed.
  Hosted pagination/concurrency and larger publication/Capsule/doorway checks
  passed under the adopted Workers Paid plan. These are bounded checks, not
  sustained-load guarantees; details are in [online readiness](ONLINE_READINESS.md).
- The current preview preserves eight publications, all 16 download hashes and
  the accepted public doorway. The notice was visually checked at 390 × 844 and
  confirmed hidden at desktop width; this does not close mobile usability work.

## Outstanding observations and release decision

Specific live Capsule departure/return audio has not been physically confirmed
since the audio repair. Production cue/renderer paths have automated coverage,
and normal effects have physical acceptance; these are distinct observations.
Do not resend an accepted delivery to test it. Any further end-to-end audition
should use a separately agreed new test exchange or isolated synthetic scene.

Representative desktop smoothness still needs an explicit owner observation.
No measured frame-rate or broad GPU compatibility claim is made. The owner should
either complete these observations or explicitly accept their limits before
approving release. Windows installers remain unsigned.

After that review, select the release version, align version metadata and prepare
fresh Linux/Windows packages at the versioned revision. Complete the documented
public-release checks, including package/version consistency, before stable
publication. The current candidate binaries still report v0.3.1; they must not be
presented as a newly versioned stable release. Keep PR #5 draft until the owner's
release decision.
