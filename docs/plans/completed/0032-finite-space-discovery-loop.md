> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan0032 — Finite-space discovery loop, first bounded campaign

## Status

COMPLETED_AUTONOMOUS_UNIT / TECHNICAL_ACCEPTANCE_PASS / EPISODE1_COMPLETE /
UNSCORED_EXPLORATORY_HANDOFF_READY / OPTIONAL_HUMAN_REVIEW_NOT_REQUIRED.

2026-09-08: the user requested verification of six ideas in a separate existing
chat. Plan0033 now owns that bounded source audit. Archive this completed unit
without changing its experiments, budgets or optional handoff. Earlier wording
about keeping this plan active is a historical checkpoint, not current routing.

2026-09-08 user approved the strategy with 「それで続けて」. This authorizes
the minimum implementation/calibration and subsequent bounded exploration in
the agreed roadmap, not old Plan31 execution. Plan31 is superseded before
registration and preserved without a candidate-quality conclusion. D-064's
planning-only hold is lifted for this new unit. D-055 remains mandatory.

## Question and exit

### Current exit — 2026-09-08 06:40 JST

The autonomous implementation/diagnostic unit is finished. Full suite81830
completed1,437 tests/5,386.118s/OK(skipped=2)/actual exit0. Independent final
technical audit PASS for190 source pins,9 manifest pins, all34 final-version
new tests, both exit receipts and byte-identical permanent evidence copies.
Both workers are finished: never poll, restart or rerun them.

Two exact registered TILE wires (7/B-first and9/A-first) now have a derived
Japanese guide and optional paper/local-terminal entry points. Static handoff
review PASS. This makes a short unscored exploratory review possible, not a
fairness/depth/fun or human-UX certificate. Raw human flags remainfalse;
the separate [handoff record](../../../experiments/reports/0032-human-handoff.json)
records presentation readiness only. Actual human games0, no website/publication.
See [acceptance](../../../experiments/reports/0032-acceptance-and-handoff-ja.md)
and [guide](../../reviews/2026-09-08-finite-space-play-guide-ja.md).

The same-task heartbeat was deleted via the app at2026-09-07T21:40:10Z:
the workers and finite handoff are complete, and there is no external event to
poll before voluntary user feedback. No replacement or automatic episode2.
At most20 minutes of optional human review is suggested; none is launched.
Keep this sole plan as the active handoff/feedback record. A later user response
can guide a bounded new unit, but unused episode capacity is not a to-do list.
D-066 records this endpoint. Earlier running checkpoints below are historical.

Can two mechanically different finite-space skeletons run through one
data-driven, token-free verification path, distinguish known faults from
incomplete evidence, and supply a small set of concrete rules worth further
human consideration? Stage0 success means working expression/calibration,
not a game-quality finding. Stage1 has at most8 new definitions from the two
implemented skeletons, not12 coordinate variants or an unbounded generator.

First skeleton: free placement of straight versus bent triominoes.
Second: few long-range pieces versus more short-range pieces, permanently
closing the origin after moving. The shared termination measure is remaining
empty/open capacity, not forward progress. Actual definitions, seeds and
production node limits will be frozen in a separate manifest before discovery.
No source-review or calibration result is retroactively selection evidence.

## Source boundary, fixed before code changes

Only these six new Python files are allowed:

- `src/parity_forge/finite_space.py`
- `src/parity_forge/finite_space_search.py`
- `src/parity_forge/finite_space_batch.py`
- `tests/test_finite_space.py`
- `tests/test_finite_space_search.py`
- `tests/test_finite_space_batch.py`

No edits to historical source, tests, fixtures, proposals or raw runs. Shared
old imports are `Player` and `DefinitionError` only. No dependencies, callbacks,
model training, framework migration, website build/deployment or new scheduler.
The new schema is independent, so old source/definition hashes stay meaningful.
Initial combined source+test target is at most2,000 physical lines; if that
ceiling or the work limit prevents completion, preserve the partial work and
stop rather than silently add a new component. Documentation and prospective
JSON/immutable generated evidence have separate filenames and are not hidden code.

Semantics and10 calibration propositions are fixed in
[finite-space-v1](../../designs/finite-space-v1.md). The new terminal rule is
explicitly `NO_LEGAL_ACTION_LOSES`: the player with no move loses. No rule-level
ply cap, draw, pass, cycling, score tiebreak or arbitrary callback is present.
All legal TILE/TRAIL transitions strictly reduce empty capacity. Dimensions
1..32 are an initial implementation resource guard, not a permanent product cap.

## Stage0 work and tests

Implementation session1 begins2026-09-07T18:21:25Z (2026-09-08 JST).
At most3 outer work sessions and4 active work hours total, with a conservative
wall-time check; the one full-regression machine wait is accounted separately.
Bounded independent design/implementation reviews occur inside that stage;
they consume model work too and are not reported as free tokens. Exact model
token usage is unavailable here; do not infer it from conversation-turn counts.

- Main owns plan, search/batch and integration.
- Implementation reviewer owns the new core and its tests.
- Independent read-only design and source reviews check no-draw and evidence
  boundaries. Do not use model calls per simulated move or game.
- At most10 distinct synthetic calibration definitions; invalid encodings and
  renamed/rotated representations are fault cases, not extra discovery supply.
- Aggregate exhaustive calibration ceiling100,000 states per invocation and
  focused test invocation ceiling3 in the main lane before source freeze.
  Tiny fixtures only; no historical protected corpus or candidate evaluation.
- After focused tests and review, freeze source+tests before exactly one
  `PYTHONPATH=src python3 -m unittest discover -s tests -v` full regression.
  New-code completion requires actual successful summary and exit status.
  Preserve log and source pins. Do not call a running suite passed. Failure or
  interruption returns an incomplete checkpoint, not automatic unlimited repair.

### Source-freeze checkpoint

2026-09-07T19:26:18Z: six new files total1,899 physical lines. Three main
focused invocations were consumed; last34 tests/0.143s/OK/exit0. Subsequently,
the JSON reader's saved-artifact limit was aligned with the16 MiB output limit
and corresponding assertions added. No fourth focused invocation; this final
version is covered by the one full suite now running. Independent core/search
and batch static audits PASS within their declared scopes.

Full regression session81830/PID48556; log and190 Python-source pins are in
`/tmp/parity-forge-plan0032.yFsHOq/`. A pending suite is not technical acceptance.
After prospective review, the single registered diagnostic may run concurrently
with this machine wait; no scientific/human acceptance bypasses the test result.
Source/test bytes remain frozen throughout both executions.

### Episode1 execution checkpoint

Independent prospective static review PASS:8 semantic hashes,9 source pins,
64 schedule slots, provenance, no-draw and mechanical asymmetry. The reviewer
confirmed that concurrent unaccepted raw diagnostics are permitted, with
technical acceptance/human promotion waiting for actual full-suite success.
See [registration record](../../../experiments/reports/0032-episode1-registration-ja.md).
The sole batch started2026-09-07T19:40:11Z, session99158/PID52027; pilot.log
shares the full-suite temporary directory. Canonical run root is
`experiments/runs/finite-space-campaign-v1/plan0032-finite-space-episode1-v0/`.
Claim/registration are saved; no retry or extra invocation. Runtime and results
are pending. All8 candidates have a source-proved absence of any3-ply terminal;
thus the short query is a consistency check, not a discriminating quality gate.

Checkpoint2026-09-07T19:43:36Z: both workers remain active,190 source pins
rechecked PASS/exit0, no full-suite summary or episode results yet. Stage0
implementation session1 elapsed at most83 minutes so far, conservatively
including short waits, below4 hours; main focused budget3/3 remains exhausted.
Existing same-task30-minute heartbeat was updated in place to this scope.
Next action is saved-result/actual-exit acceptance, not new implementation or
another experiment while these executions run.

### Saved-result checkpoint — 2026-09-08 05:16–05:25 JST

Episode1 session99158 completed exit0; PID52027 gone.64/64 games COMPLETE /
NO_LEGAL_ACTION,11..40 plies, no game UNKNOWN/draw/not-started/fallback.
CPU308.365877s, below4-hour cap. Proofs15 COMPLETE false /1 UNKNOWN50k;
raw disposition7 FURTHER_REVIEW/1 INSUFFICIENT_EVIDENCE, human flags allfalse.
Source pins190 matched again with exit0; frozen final-version34 tests are now
ok inside the still-running full suite, not a whole-suite success claim.

Independent saved-only audit PASS for registration/claim/runtime/results/source
hashes, all schedules, counters, budgets, outcomes and policy-depth limits.
Bounded independent source strategy review found no simple direct mirror,
fixed-terminal-parity or action-containment proof making TILE7/B-first and
TILE9/A-first meaningless for a short exploratory trial. This is not proof of
no optimal winning strategy. Observed4:4 on9/A is policy-dependent, not fairness.
TILE remains shallow:175/286 search decisions retained depth1. TRAIL is B-heavy
in each separate first-player cell, not source-rejected. Review scope did not
perform any new game/solver/enumeration/replay/test or code edit.

See [findings](../../../experiments/reports/0032-episode1-findings-ja.md).
At most2 provisional usability priorities, no human approval or trial yet.
The remaining action is actual full-suite summary/exit and acceptance, then
the limited usability handoff; no second episode or source expansion during wait.
At2026-09-07T20:26:41Z full-suite PID48556 remained running after60:23,
without a final summary. This heartbeat added no code, test, game, solver or
replay execution. Existing monitoring remains useful and unchanged.

## Stage1 pre-execution obligations

Freeze at most4 TILE and4 TRAIL definitions, origin/variant description, canonical
hashes, first player, seeds, policy versions, schedule, source hashes, node and
transition caps in a manifest before the first new discovery game. The manifest
is the registration record, even if unrelated user work keeps the main Git tree
dirty. Protect output with exclusive creation and refuse duplicate run IDs.
Do not silently run variants from tests or fill failed slots.

The implemented first exploratory diagnostic has at most8 games per definition.
The strategy's optional extra16-game diagnostics are deferred in this episode;
unused budget is not authority to add them. The initial
two different policy approaches are goal-directed denial and bounded search
with a mobility evaluation; random is a control, not a human proxy. Policies
must pass synthetic counterexamples before use. A finite proof probe answers
only its stated short-horizon proposition and returns UNKNOWN on exhaustion.

After calibration, exact per-decision/per-game work caps must be set in the
manifest without outcome-guided budget tuning. Per-episode CPU ceiling4 hours;
calibration CPU ceiling2 hours. Search budget is external to game rules.
No win-rate boundary from8/16 games is a fairness certificate or decisive
game rejection; retain raw observations and uncertainty separately.

Disposition vocabulary: INVALID_DEFINITION, PROVED_DEFECT,
INSUFFICIENT_EVIDENCE, FURTHER_REVIEW. Conservative asymmetry NOT_ESTABLISHED is
INSUFFICIENT_EVIDENCE, not INVALID_DEFINITION. None implies human approval or fun.
The same module includes an unscored coordinate-input terminal prototype; no
automatic human game or website is launched. Human-play eligibility requires verified decisive termination, mechanical
asymmetry, completed declared short-defect checks, a usable UI and explicit
known weaknesses. No human trial is automatically launched by stage0/1.

## Campaign scope and stopping

This is at most episode1 of the approved maximum3 episodes/36 new definitions.
Later episode manifests are separate development revisions, not reruns of a
frozen confirmation. Change one research component at a time and compare it
against the prior version with matched declared resources; hold back fresh
confirmation examples. Do not label every old NO_FLAG as a bad game.

At most2 trial suggestions and one20-minute user session per episode, maximum
3 sessions/60 minutes for the campaign. No fourth episode or automatic budget
increase. If representation cannot be made useful inside stage0's source/work
cap, stop with a specific cause. If no usable rule reaches the human exit after
three episodes, return the method decision rather than continue infrastructure.

## Checklist

- [x] User continuation authority and fixed no-draw/asymmetry scope recorded.
- [x] Plan31 preserved and superseded before registration.
- [x] Two skeletons, API, new-source allowlist and calibration claims fixed.
- [x] Implement core/search/batch and their focused tests.
- [x] Independent source and semantics review; fix within current boundary.
- [x] Freeze source; launch one full regression.
- [x] Accept its actual successful full-suite summary and exit status.
- [x] Freeze stage1 manifest from discovery count zero.
- [x] Execute the bounded diagnostic once; preserve evidence and classify it.
- [x] Report diagnostic results, unresolved issues and next finite action.
- [x] Prepare at most2 exact-rule unscored handoffs, disclose limits and audit instructions.
- [x] End obsolete periodic continuation without launching a human trial or episode2.
- [ ] Optional later user feedback; not an autonomous completion requirement.
