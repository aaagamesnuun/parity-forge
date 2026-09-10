> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan0039 — Victory-objective discovery after the placement-exhaustion ban

2026-09-10 JST. COMPLETE / DESIGN_AND_REGISTRATION_COMPLETE. D-080/D-081/D-082.

The historical bounded units below are finished. Only「架橋と転色」advances to
`docs/plans/active/0040-connection-baseline.md`; do not repeat sketches/reviews.

## Authority and hard gate

The user prohibits "最後に置けなかったほうが負け" in future games. Their existing
instruction to continue discovery hourly remains in force. Retire Plan38's TILE
follow-up, including stronger-AI episode3; do not spend its unused capacity.

Reject future candidates where running out of legal placements itself loses the
game, even if disguised as last-placement-wins. Placement actions remain allowed.
Do not evade the feedback by renaming the same exhaustion mechanic as movement
or silently reversing the winner. Seek substantive objectives, not another board
shape under the same terminal rule. Mechanical asymmetry and every-legal-play
finite termination with exactly one A/B winner remain mandatory; no draws.
Board size and extreme simplicity are not hard limits. Fairness/depth/fun remain
separate evaluation goals, never inferred from sampled wins or solver exhaustion.

## Next bounded unit: design review, not an experiment

1. Propose at most three mechanically distinct, objective-based rule sketches.
   Capture, connection, goal arrival/defence are possible directions, not adopted
   rules. Do not resume old Plan34/35 queries or alter old definitions to fit.
2. For each specify roles/actions, initial state, actual win/loss objective,
   simultaneous-objective precedence, and what happens if progress is exhausted.
   Establish finite, unique decisive termination for every legal continuation;
   unresolved ties, cycles or implicit no-placement-loses fail the design gate.
3. Independently review the small set for rule completeness, asymmetry, the new
   exclusion, obvious strategic defects and plausibility of meaningful choices.
   Select at most one for a separate implementation/experiment registration,
   or record a concrete design obstacle and next question. Do not equate absence
   of a found defect with quality. No infinite additional sketch batches.

This unit permits at most three sketches and one independent review, zero matches,
zero proof-search launches and zero engine changes. Its output must state a finite
implementation/test/experiment budget before subsequent execution. The old
finite_space engine accepts only NO_LEGAL_ACTION_LOSES; it is not a ready engine
for the new objectives. Reuse only compatible primitives, and keep later engine,
agent and evaluation changes separately attributable. No per-move model calls.

## Preservation and schedule

Preserve old DSLs, fixtures, raw results, episode claims, public Site and code-only
GitHub. No deletion, redeployment, research upload, paid resources or external
tester recruitment. All previous no-retry/protected-evidence restrictions remain.
Plan38 session99989 is finished; never poll/restart it. No old episode3 launch.

Keep the existing same-task hourly heartbeat, ID `parity-forge`, name
「Parity Forge 新ゲーム探索」. Update its prompt to this plan and the new hard gate;
preserve frequency, target and notification preference. Each activation advances
one bounded unit, updates state/plan/backlog, and stays quiet on unchanged status.
Notify meaningful candidates/findings or actual need for a human choice. Routine
technical planning is autonomous. Do not perform a redundant full regression for
this documentation-only exclusion; later source changes must satisfy AGENTS tests.

## Progress

- [x] Persist exclusion in AGENTS, charter and D-080; preserve historical records.
- [x] Cancel Plan38 episode3 and archive its plan, without changing raw labels.
- [x] Update existing hourly heartbeat and verify retained settings.
- [x] Produce and independently review at most three objective-based sketches.
- [x] Select at most one and preregister a finite next unit, or report the obstacle.

No new game rules have been adopted or executed during this policy update.

Native update confirmed `parity-forge` ACTIVE at the observation
2026-09-10T00:21:00Z. Saved configuration retains the same name, hourly schedule,
target thread and original creation timestamp; no notification-policy override.
The prompt now enforces D-080, cancels old episode3 and starts Plan39 design review.
OpenAI Docs informed updating the existing same-task continuation rather than
creating a duplicate. No other timer changed.

## First design activation — 2026-09-10 JST

Two sketches/one independent review DONE; no third sketch or correction loop.
Fixed design-only JSON: `experiments/proposals/plan0039-objective-designs-v0.json`,
SHA2563f7d7cf470dfe8ba4aec462423ddd9e3410631c07dd59d422f5e2f9cc1b7ffdc.
Not implemented or accepted by an existing engine; matches/search/source changes0.

Select only「架橋と転色」for registration. Independent structural gatePASS:
9x9 Hex, A3 pair-placement credits/B2 conversion credits; each action fills≥1cell,
and Hex coloring geometry supplies a unique connection winner by81actions.
This transfers no standard Hex strategy, complexity or quality claim. Resources
are uncalibrated; no human-review promotion.
「突破と迎撃」fails by a simple B strategy: fix(2,3)/(2,5), oscillate third guard
(2,1)↔(2,0), capture any row2 crossing; otherwise the12round arrival goal fails.
No program search or repaired design. Review and primary theorem source:
`experiments/reports/0039-objective-design-review-ja.md`.

Next unit registers an isolated implementation/diagnostic:≤6newPython files,
3integrated focused invocations, one postfreeze full suite; one cohort≤16games/
14,400CPU seconds/16MiB, perdecision≤32,768transitions/depth3/pergame≤3m;
zero initial exact queries. Same9x9 rules/resources, separately registered firstA/B.
No parameter search or old campaign continuation. DSL/evaluator/schedule/source
pins are not ready, so no implementation or experiment starts in this activation.
Do not repeat the used design-review unit just because the persistent heartbeat
still describes its original starting step. Routine next registration is autonomous.

## Registration acceptance — 2026-09-10 JST

Prospective registration and API contract independently audited PASS; original
selected mechanics preserved, only first-player A/B differs, exactly16games.
Registration SHA256 c9ba6db6b00425d014a2a695f46d1552e5d8969c78a626fa27a2d14b34d6d060.
Contract SHA256 a481b1223a181a1a46305802099a087476a6c0623898253829ee6b70f991d73a.
Evidence: `experiments/reports/0040-registration-ja.md`. Old206 source pins and
Plan38 raw results unchanged; new6source files, claim and output are absent.
No implementation, test suite, policy game or proof search in this activation.
Plan40 is REGISTERED_NOT_IMPLEMENTED, not an executable or human-ready game.
