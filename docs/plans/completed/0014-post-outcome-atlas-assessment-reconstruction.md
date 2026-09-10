> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan 0014 — Post-outcome atlas assessment reconstruction

## Status

Completed, post-outcome, report-only. Plan 0013 remains terminally closed with
five `COMPLETED` parent stages and one `FAILED` assessment stage. Plan 0014 did
not reopen, rerun, replace, or complete that V2 stage. It created one separately
versioned and independently audited attestation of the report that the unchanged
frozen scientific rules compute from the already immutable parent evidence.

## Objective

Produce one authenticated 144-pair/six-family report and deterministic
inspection selection from the five completed Plan-0013 parents, while preserving
the failed V2 assessment as failed. Correct only two demonstrated
producer/consumer integration defects, generate no new gameplay evidence, and
read, allocate, export, or evaluate no confirmation-candidate member.

The result will be a post-failure mechanical reconstruction. It may recover the
formal calculation defined before outcomes, but it is not a rerun of Plan 0013,
not new confirmation evidence, and not evidence that any game is enjoyable.

## Observation

Plan 0013 completed and independently validated its manifest, exact, random,
terminal-only depth-1, and replay-telemetry stages. Its assessment was then
invoked exactly once and sealed `FAILED` before any completed body, report, or
inspection artifact existed. The evidence lifecycle behaved correctly; the
failure was in the assessment integration code.

Two independent read-only audits isolated exactly two blocking defects:

1. the trusted assessment caller constructed telemetry admissible and
   nonadmissible slot IDs as tuples, while the strict JSON-array reconciler
   correctly accepts only built-in lists; and
2. assessment required all legal-count bins to sum to `decision_count`, although
   authoritative replay telemetry records a zero-legal-action terminal
   observation in `legal_observation_count` and bin `0`, not as a decision.

All and only 2,296 records have that terminal observation shape: 912 random and
1,384 depth-1 games, exactly the `NO_LEGAL_ACTION` terminals. With the
authoritative identities applied, all remaining telemetry checks pass
36,864/36,864. No parent-evidence corruption was found.

## Slice-1 result

The corrected calculation is now isolated in a read/validation core; the old
Plan-0013 `run|recover` module remains a separate lifecycle facade. The V2 store
is opened through a no-create reader bound directly to a directory descriptor
obtained by traversing every repository and store path component with
`openat`/`O_NOFOLLOW`. It neither requires nor creates operational locks or an
empty contradiction directory, and a path swap after authentication cannot
redirect the reader.

The real-parent integration test reconstructed every formal input, including all
36,864 telemetry records, in 541.990 seconds. The complete V2 filesystem
inventory contained 152,716 files/directories and was identical before and
after, including type, mode, link count, size, and file SHA-256. The result was:

- inner report root
  `2a873b0b1d11e9ffb617792d41c870e1fb0fe32f4f2c7b6aa5fdfeb5d215484d`;
- status `FORMAL_COMPLETE` and claim level
  `FAMILY_FRONTIER_SIGNAL_NOT_FAIR_GAME`;
- 14 pair-frontier signals, all `FIRST_PLAYER_DOMINANT`;
- push-hop-race 9 pairs / 6 strata and convert-push-front 3 / 3 under the
  frozen positive family-count rule; push-swap-networks 2 / 1 and all other
  families under the frozen not-supported rule; and
- inspection selection 98 pairs / 118 class groups / 104,458 canonical bytes,
  SHA-256
  `0fc525939d67cbf426704e28b7383fa1b92aa14d6f497cbaaf7d136be3803c7e`.

These are deterministic test-time reconstruction values, not a Plan-0013
completion and not yet a Plan-0014 evidence attestation. Independent review of
the repair, core split, read-only boundary, path-race defense, and unchanged V2
tree found no P0-P3 issue. No Plan-0014 evidence store exists yet.

The slice-1 implementation boundary passed the complete dependency-free suite:
799 tests in 1,044.068 seconds, with only the deliberately opt-in real-parent
test skipped. That same real-parent test had already passed separately at the
values above.

## Slice-2 result

At the slice-2 checkpoint, the complete report-only production edge was
implemented but had not been invoked. The first implementation checkpoint,
commit/tree
`37d95eb94bb50db5e3876c7e949a9cb1c47d58ee` /
`87e470042a98696347d4314a4668201f01aecdfb`, was rejected before production.
Its protocol root
`5424b2d066843f5e52d70e8395ed594dda1760c3447080e7b515dbccb78f8458`
and 14,339-byte canonical SHA-256
`adb409bac1bdc2eb80e8331b29238b89f41fe3705b9137947d90b0bbb4f6fa88`
are retained only as the superseded pre-run contract. Three independent audits
found one P2 liveness defect: opening an expected FIFO with blocking
`O_RDONLY` could stop before the subsequent regular-file check. No Plan-0014
evidence root, reservation, attempt, report, or terminal existed.

The defect is closed in the separately versioned non-scientific reader-
hardening checkpoint, commit/tree
`bcec70193963da8f88fff7d4dc34133cf31ed057` /
`69553e0798d8b229bd3ce8522a77ef83fff44cb0`. Its exact nine-path change surface
contains five production readers and four regression-test modules. Expected
artifacts, operational locks, pending linked publications, archived source
files, and current source paths now use nonblocking no-follow opens before type
validation. Reads are exact-size and bounded, current source is traversed by
directory descriptors, and lock cleanup records whether `flock` actually
succeeded. FIFO, Unix-socket, device, symlink-ancestor, hardlink, size, and path-
swap probes fail closed under two-second subprocess timeouts. This adds zero
assessment integration corrections and zero scientific-rule changes; the two
allowed assessment repairs remain the only repairs.

The hardening checkpoint passed 80 focused tests in 19.453 seconds and the
complete dependency-free suite passed 873 tests in 1,102.015 seconds, with only
the two deliberately opt-in real-data tests skipped. The final protocol now
records the rejected checkpoint and hardening checkpoint as a direct source
chain. Its fixed root is
`b412e0af7f36850f06199a3d21897195b26d1eb4ef417616debca57a3185d38d`,
with 16,880 canonical bytes at SHA-256
`0aeb2bf4a3e6d0caa048f4e4238981738ebfb0287c63f938e86b47d9984ecfd1`.
The exact recursive production closure remains 13 allow-listed source paths. It
requires production equality for three scientific repair/facade blobs, four
non-protocol reader-hardening blobs, and six unchanged pre-existing scientific
dependencies. The final protocol module is the sole intentional self-reference
exception and is bound by its final production-closure record. Reflective or
dynamic local imports remain forbidden, and there is no solver, agent,
gameplay, telemetry-generation, selector, or candidate-block execution path.

The real archived source binding independently matched twice at identity
`f763bad5ca0c0d1a82aa879aa0cc08fb47b0920effe27899ef85b0dac21e5157`.
Archive and live inventories each contain 152,680 tracked artifacts and
601,787,372 bytes at inventory root
`773941af8b9982f3ca365e6d26c5e7967eb2b3f5fc0fecc212c255e6e15cd612`.
Operational lock files and the empty contradiction directory are excluded from
that identity but, when present, are still strictly validated. The full
source-binding, inner-report, and outer-attestation integration test then passed
read-only in 765.274 seconds, preserving the slice-1 report and inspection
goldens.

The new evidence primitive has a single bootstrap/reservation/attempt/terminal
chain, descriptor-bound publication, exclusive empty locks, atomic pending-file
reconciliation, and completed-body precedence over any later exception.
Recovery never resumes a calculation. Create-intent directory adoption fsyncs
the child and parent even when an earlier creator left the directory behind,
and the exact Plan-0014 lock-only ignore rule permits an operational-only crash
to re-enter the real clean-HEAD preflight. The earlier 68-test, 867-test, and
real-data results remain historical implementation evidence, but the superseded
checkpoint was not authorized for production. The final-source verification and
production result are recorded below; no evidence was created from either
superseded checkpoint.

## Production result

The authorized production source is commit/tree
`3fa9f6bed5afd92130a294a3e2b4e33abfb3f992` /
`f491a361e1b933a7a36cc816e29701d871296a50`, the exact single child of the
reader-hardening checkpoint. Its 13-path production closure is
`975541c35d63e8d75448e0dd26ab99dfa2f00b37380729218a76451e5cbe57d7`.
The final dependency-free suite passed 874 tests in 1,125.663 seconds with the
two deliberately opt-in real-data tests skipped. Those tests then passed
separately in 577.119 and 736.578 seconds. Three independent pre-run audits of
the closure, source/semantic boundary, and lifecycle/filesystem boundary each
reported P0=P1=P2=P3=0.

The production stage was invoked exactly once and sealed `COMPLETED`:

- bootstrap `94d7016f45cf6194c57db4807a5bda7937e6f87a425675a1ad29ea330cc3a860`;
- reservation `8f16dbc697af54a03f624ce69e0ddca7be3814d6f5d5a91e4b37ccc915e880f2`;
- attempt `bb392260ff7852bbbc6943eee2d0583fa5b9372662d924ed1dcce415dcfe133c`;
- completed body
  `aafdee21947865a3249513e11b87f5387d91bf9f64d346dacb32fcdc8ebc699f`;
  and
- terminal seal
  `9272adcd93a9929861bae6d9b7caa00f3ce2e9502096b056e23ed207d832b5ae`.

Public recovery was invoked once and returned `VERIFIED_NO_OP` for the same
terminal. The immutable store contains five canonical `0400` JSON artifacts,
334,180 bytes in total, with no failure, orphan, contradiction, or pending
artifact. The operational lock is zero-byte `0600` state excluded by the exact
lock-only ignore rule.

The sealed result preserves inner report root
`2a873b0b1d11e9ffb617792d41c870e1fb0fe32f4f2c7b6aa5fdfeb5d215484d`,
inspection root
`279b0459ef50a69940e33dae14f18a576dbd452d3c59cab2840138c8232a86b6`,
and outer attestation root
`9ca2d719fa2ab686d33480b0d75b0860777f666da6497ab759d6f7fd8a52590d`.
All 14 frontier pairs are `FIRST_PLAYER_DOMINANT`. The frozen family-count rule
labels push-hop-race 9/6 and convert-push-front 3/3 as supported family-frontier
signals, but this does not identify a fair standalone game. The other family
counts are 0/0, 0/0, 0/0, and 2/1, with no candidate allocation.

Three independent post-run audits again reported P0=P1=P2=P3=0. The semantic
audit rebuilt the complete saved result from the 601,787,372-byte old evidence
in 750.529 seconds; the chain audit matched 175 independent facts; and the
filesystem audit matched all identities, canonical bytes, modes, links, and
allowed paths. A post-run focused suite passed 74 tests in 26.687 seconds with
the one real-data opt-in skipped. Candidate access, outcome generation, sampled
game generation, telemetry generation, and solver invocation all remained zero.

## Hypothesis

A separately versioned exact-list producer and correct zero-observation
interpreter will reconstruct the original frozen report without changing any
pair label, family threshold, metric definition, inspection rule, or raw result.
If any further semantic repair, discretionary choice, parent mutation, gameplay
work, or candidate access is required, this plan fails closed instead of
expanding scope.

## Frozen source chain

The reconstruction must bind these Plan-0013 V2 terminals in this order and at
their fixed repository paths:

1. manifest `5ee92d2b…e46` — `COMPLETED`;
2. exact `6c575e50…a6c45` — `COMPLETED`;
3. random `bafc4a52…e9b6` — `COMPLETED`;
4. terminal depth-1 `f5d1e937…be226` — `COMPLETED`;
5. replay telemetry `2869fc55…f670` — `COMPLETED`; and
6. original assessment `812b8c4b…e889` — `FAILED`.

It must additionally bind the V2 bootstrap root `96c7e239…ea22`, protocol root
`8126c33f…f04c`, protocol canonical SHA-256 `b732f174…9229`, manifest root
`ffbb2256…f7c3`, source commit/tree `5e6a865…5ec1` / `17468fd2…fad`, failed
assessment reservation `91138600…a6d`, attempt `bffac6f2…9c96`, failure-body
SHA-256 `9db7d724…385d` with 504 bytes, production closure
`f7792895…b2e4`, every terminal body reference, and the Git commit that archives
the complete V2 evidence store.

The old store is a read-only input. Its unknown paths, missing artifacts,
symlinks, hardlinks, contradictions, lifecycle drift, body-reference drift,
parent substitution, or absence of the exact failed exception must stop the new
stage before report construction.

## Allowed repair surface

The scientific calculation may change in exactly two ways:

1. produce `admissible` and `nonadmissible` as exact built-in lists at the
   telemetry-ledger reconciliation boundary; and
2. validate, for each telemetry role,

   ```text
   sum(legal_count_bins) == legal_observation_count
   bin["1"] + bin["2+"] == decision_count
   legal_observation_count == decision_count + bin["0"]
   ```

The strict list consumer remains strict. Bin `0` never contributes to the
forced-decision numerator or decision denominator. The original V2 entrypoint,
store, stage identity, terminal, and historical Git blob remain unchanged.

No other assessor arithmetic, status priority, denominator, exact truth table,
weak-balance threshold, family rule, inspection quota, score order, tie break,
schedule, seed, cap, definition, telemetry value, or raw outcome may change.

## Epistemic boundary

The completed parents already expose a raw three-way intersection of 14 pairs
across 10 strata: push-hop-race 9/6, convert-push-front 3/3, and
push-swap-networks 2/1. The other three families have zero. All 14 pairs are
exact first-player-dominant. Those observed facts motivated no repair choice and
may not alter the frozen calculation.

The new artifact must say both:

- `original_stage_lifecycle = FAILED`; and
- `epistemic_status = POST_FAILURE_MECHANICAL_RECONSTRUCTION_NOT_CONFIRMATION`.

It must never claim that the Plan-0013 V2 assessment completed. A family count
signal is not single-game fairness, strategic depth, replay desire, or fun, and
cannot by itself allocate the confirmation block.

## Implementation slices

### 1. Corrected pure reconstruction

- Preserve the old strict ledger consumer and add production-path regression
  coverage across the completed parent join.
- Implement only the two allowed fixes in the existing assessment calculation
  path, with explicit versioned public reconstruction entrypoint.
- Validate `GOAL`, `PLY_LIMIT`, and `NO_LEGAL_ACTION` telemetry shapes, all three
  count identities, strict integer types, and zero-decision edge cases.
- Reconstruct all 36,864 real telemetry inputs read-only before any production
  attestation is authorized.

### 2. Cross-store source binding

- Add a pure fixed source-binding builder and validator for the six old
  terminals, their bodies, bootstrap, protocol, manifest, failure chain, source
  commit/tree, fixed paths, and archive commit.
- Authenticate the five old parents through their existing public evidence
  readers, then independently reconstruct the old assessment reservation,
  attempt, failure, and terminal chain.
- Require the parent terminals embedded in the failed reservation to be
  canonical-byte identical to the fixed-path parent terminals.
- Read no selection artifact or candidate-block definition.

### 3. Outer report attestation

- Keep the frozen Plan-0013 assessment report as an unmodified inner value.
- Wrap it in a new Plan-0014 attestation containing the source-binding root,
  repair protocol identity, two closed defect IDs, scientific-rule change count
  zero, outcome-generation count zero, candidate access/export/allocation counts
  zero, original failed lifecycle, inner report body reference, and inspection
  selection root.
- Public validation must rebuild the inner report and every outer claim from the
  old raw evidence rather than trust stored summaries.

### 4. New one-shot evidence edge

Use a separate evidence store, provisionally
`experiments/runs/plan0014-plan0013-assessment-reconstruction-evidence-v1`, with
one stage only:

- protocol ID `plan0014-plan0013-assessment-reconstruction-protocol-v1`;
- evidence ID `plan0014-plan0013-assessment-reconstruction-evidence-v1`;
- stage ID `PLAN0013_ASSESSMENT_RECONSTRUCTION`; and
- stage protocol ID
  `plan0014-plan0013-assessment-reconstruction-stage-v1`.

The production CLI accepts only `run|recover` and `--repository`. It freezes its
own protocol, active-plan bytes, recursive source closure, clean implementation
commit, source binding, reservation, attempt, failure/completion body, and
terminal seal. It writes nothing to the V2 store.

Recovery may validate and seal an already published failure or completion, or
mark an interrupted reservation/attempt orphaned. It must never resume report
calculation from an attempt. A terminal run returns verified no-op and can never
replace its result.

## Execution order

1. Archive and commit the complete V2 evidence chain and Plan-0013 failure
   record, excluding only its operational lock files.
2. Implement the corrected pure reconstruction and real-parent integration
   tests; run the focused and complete dependency-free suites.
3. Implement the source binding, outer attestation, and one-shot evidence edge.
4. Independently audit the two-hunk repair boundary, source-chain authenticity,
   lifecycle/recovery, candidate neutrality, and forbidden capability imports.
5. Commit all implementation and protocol inputs at a clean pre-run checkpoint.
6. Freeze and record the new recursive production closure from that commit.
7. Run the reconstruction stage exactly once.
8. Publicly recover, independently reconstruct and audit the new terminal, then
   commit its immutable evidence and update project records.
9. Close Plan 0014 whether reconstruction succeeds or fails. Only a successful,
   audited report may inform a separately planned next discovery decision.

## Definition of done

- [x] The complete V2 evidence and Plan-0013 closure are archived at the plan
  transition boundary, excluding only operational locks, and must remain
  byte-for-byte unchanged afterward.
- [x] The two allowed assessment fixes have production-path regression tests;
  the strict list boundary remains strict.
- [x] All 36,864 parent telemetry records and all formal raw inputs reconstruct
  read-only under the authoritative contracts.
- [x] The six fixed source terminals, failed exception chain, body references,
  protocol, manifest, source commit/tree, and archive commit are authenticated.
- [x] The inner report preserves every frozen Plan-0013 scientific rule and the
  outer attestation makes the post-failure status explicit.
- [x] The new single-stage run/recover lifecycle is immutable, noninjectable,
  crash-safe, and independently reviewed before production.
- [x] AST/import and execution tests prove zero solver, agent, game,
  telemetry-generation, selection, and candidate-block access.
- [x] The full dependency-free suite passes at every committed implementation
  boundary.
- [x] The new stage runs exactly once, reaches one terminal lifecycle, and public
  recovery is a verified no-op.
- [x] Independent post-run reconstruction matches every report, inspection,
  source-binding, closure, and evidence root with no unresolved P0–P3 defect.
- [x] Project state, backlog, decisions, and the next bounded research plan are
  updated without relabeling the artifact as confirmation.

## Non-goals

- Do not rerun or complete the V2 assessment.
- Do not recompute any solver result, select any action, play any game, or derive
  new telemetry.
- Do not change or extend the 144 development pairs, 288 definitions, six
  families, schedules, strengths, seeds, caps, labels, thresholds, or inspection
  rules.
- Do not read, allocate, export, evaluate, replenish, or replace the disjoint
  confirmation candidate block.
- Do not tune the repair after observing the reconstructed report.
- Do not call the result confirmation, replication, independent evidence,
  fairness proof, strategic-quality proof, or human-play evidence.

## Expected interpretation

The mechanical report is likely to encode the already visible 14-pair
intersection and the frozen family-count rule. Even if two families receive a
positive count status, all 14 underlying pairs remain first-player-dominant and
therefore do not establish a fair standalone game. The report's value is to
close the preregistered calculation honestly and recover its deterministic
inspection sample, not to rescue an attractive conclusion.

## Next action

Preserve this report-only attestation and the original failed V2 lifecycle as
immutable history. Continue under Plan 0015 with an outcome-free,
transition-free exhaustive typed occupancy-v4 universe and blind partition;
do not spend the Plan-0013 confirmation candidate block.
