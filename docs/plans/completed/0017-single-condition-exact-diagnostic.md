> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan 0017 — One bounded exact diagnostic

## Status

Preregistered 2026-09-05; now COMPLETED / ACCEPTED (see final closeout below).
The following registration preserves its original provisional procedure. Plan 0016 is execution-complete,
replay-verified, and archived byte-identically with ACCEPTANCE_PENDING.
Its full regression continues against unchanged source/tests at `eb9e53fcc`.
Decision D-054 records a pre-execution procedural amendment: this one diagnostic
may run concurrently using the unchanged, previously accepted solver/engine,
but both studies' formal acceptance still requires the pending suite to pass.
No source/test changes are proposed. This permission does not add work to the
closed Plan-0016 schedule or allow a repeat of either study.

## Question and selection

What is the optimal-play result of the one remaining shallow-play diagnostic
condition? This is an outcome-informed follow-up, not held-out confirmation.
The 3,680-game pilot produced four raw flags; separate rule-level proofs closed
three as short forced wins. Preserve those raw flags and deductions separately.

The only member is Plan-0016 carrier index 7, B-first, original/base orientation:

- Carrier: `d78d8cba17e4bd6d867604a50d82d41902a1751621198d1f25c5fb0547023cdf`.
- Definition: `2f0620edf6d1bd921e32befda6a84ee4c62f565c109fe1bca58be3a47cd948fb`.
- Source manifest:
  `experiments/runs/plan0016-exploratory-pilot-v1/manifest.json`.
- Exact manifest-file SHA-256:
  `3c54f7b753ce56d2d6fc28e77c6d8eddc0a5ebd8df11d151bc15a6068cb6814b`.
- Select exactly `selection.selected[7].definitions[1]`, validate both identities
  and canonical DSL equality, never hand-transcribe or regenerate the member.

Frozen schema 4, board 3×3, horizon 18, B first. A has one king-step piece aiming
for the bottom edge; B has three diagonal move/push pieces aiming for an
orthogonal top-to-bottom connection. No rule, setup, horizon, side, orientation,
or member changes; no additional sampled games or historical candidate access.

## Finite work proof

MOVE and PUSH preserve A1/B3, their kinds, and distinct in-board occupancy.
The three B pieces have no individual identifiers. Thus there are at most
`9 × C(8,3) = 504` canonical placements. There are 19 ply layers, 0 through 18.
With B fixed first, the side to move follows ply parity. The frozen engine's
ordered goal checks, then ply cap, then next-player immobility check make the
outcome a function of placement and ply (the previous actor also follows parity).
No repetition-history field or alternate terminal metadata multiplies the bound.

The existing solver caches the complete immutable GameState and charges one
searched state per cache miss. Every edge increases ply, so a key cannot be
re-entered before its current recursive evaluation finishes. The bound on the
actual solver's counter is therefore `504 × 19 = 9,576` searched states.
Use exactly `max_states=9576`, never the unlimited default. There is exactly
one solver invocation and at most one external 18-action principal-variation
verification replay. The solver's internal PV extraction also traverses at
most 18 actions; it does not invoke another search.
Do not tighten/raise the cap or repeat the solve after seeing a result.

## Minimal execution and evidence

Reuse public `solve_game`, `SolveResult.to_dict`, and `replay_dicts`; use the
accepted Plan-0016 canonical reader and atomic no-overwrite publisher for data.
No new CLI, solver, agent, evaluator library, test fixture, or persistent Python
module is needed. The computation itself is simply:

```python
result = solve_game(definition, max_states=9576)
wire = result.to_dict()
terminal = replay_dicts(definition, wire["principal_variation"])
```

The existing CLI `solve` is not used: it does not expose a state cap, and its
legacy `run_exact_solve` record text hard-codes DSL-v1 claims and auto-rejects
non-draws. Do not edit this frozen historical path to execute one diagnosis.

Before the call, require unchanged previously accepted solver/engine bytes,
reviewed provisional record-helper bytes at `eb9e53fcc`, a committed
active plan, and no existing attempt for protocol `plan0017-carrier7-exact-v1`.
Exclusively create `experiments/runs/plan0017-carrier7-exact-v1/`.
Persist attempt metadata first: protocol/UTC start/host/Python, Git commit and
clean status, source-file hashes, active-plan hash, parent manifest raw hash,
definition hash and full canonical DSL, the one-member schedule, cap, question,
exposure disclosure, and this decision rule. Keep the exact invocation in the
execution record/tool log. Any existing output blocks a repeated attempt.

Persist separate result or failure/censor metadata, UTC finish, and timing as
environmental observations. On success, save the unmodified SolveResult fields,
verify searched_states <=9576, and replay the saved principal variation through
the unchanged engine. Require terminal, winner/value/forced-result consistency,
matching terminal reason, and matching recorded length <=18. Check input and
source hashes unchanged afterwards. A PV replay verifies its legal terminal
path, not a second independent proof of all minimax branches.

Budget exhaustion means UNKNOWN/CENSORED, not draw or rejection. Unexpected
error, illegal replay, source drift, or interrupted execution retains attempt
evidence and is not silently retried. No new production exact call is authorized
merely because this proposal exists or a wrapper failed.

## Interpretation and closure

Record A_WIN, B_WIN, or DRAW exactly as computed. Do not automatically equate a
non-draw exact value with an unfair or uninteresting human game. In a deterministic
perfect-information game, a forced result and useful finite-skill balance are
different questions. A short forced strategy needs a separate valid argument.

The solver breaks equal-value ties by existing legal-action order. Its principal
variation is one optimal-value line, NOT the shortest forced win, maximal
resistance, a complete contingent strategy, or every optimal line's terminal
reason. If DRAW, its replayed terminal reason describes this line only.

Finish after the single computation or explicit failure/censor. Produce a short
Japanese result with the actual rules, computed value, searched-state count,
replayed line and its limits. Select the next smallest research question from
that observation without reopening/replenishing Plan 0016. Do not build a play
UI, enlarge the generator, modify primitives, or launch another solve here.

## Readiness

- [x] Exact member and parent manifest bytes pinned without another game.
- [x] Independent source-level review verifies the 9,576 bound and public-API route.
- [x] Independent review of the complete contract; no unresolved P0–P2.
- [x] Separate process review accepts provisional concurrency with unchanged code;
  pre-execution D-054 records the amendment and preserves the prior registered bytes.
- [x] Commit this sole active plan before execution (`dc63a5dfb`).
- [x] One attempt/result retained, external replay/source verification and Japanese report.
- [x] Pending Plan-0016 full regression passes; both studies' acceptance is recorded
  separately without rewriting their provisional raw records.

## Execution checkpoint — 2026-09-05 08:42:36 UTC

Exactly one capped call completed, session `46795` exit 0. Result `DRAW`,
1,381 searched states / 2,028 cache hits, below cap 9,576. One external replay
confirmed the 18-action PV terminates as `PLY_LIMIT` with no winner. Input,
registered-plan and source hashes matched after execution. The result remains
PROVISIONAL_UNTIL_PLAN0016_FULL_REGRESSION; no code/test bytes changed.

The independent saved-artifact audit found no hash/provenance/interpretation
inconsistency and made no additional solver, policy, or replay call. The PV
repeats the same four-action sequence on plies 7–10, 11–14 and 15–18. Its
concrete B-connect threat / A-block motif is supported by the DSL, but this
one line does not establish whether a draw-preserving alternative leaves the
cycle or which replies are essential. That proposal is now cancelled by D-055,
not authority for another call here. The current plan now only awaits the
existing regression and separate formal-acceptance closeout.

Report: `experiments/reports/0017-single-condition-exact-ja.md`.
Immutable result raw SHA-256:
`378da30af6bb4762b6ce9a4286d13c2aede2c9cf8c614d2d3c9b3e4c1cc0b13b`.
The execution-preregistered plan remains exactly retrievable at `dc63a5dfb`;
these appended execution notes do not change its prior rules or raw evidence.

## User clarification checkpoint — draw termination

The user asks whether draw endings are unacceptable. Founding directive §8
does not categorically ban all draws; it requires separate reporting and says
all-match-draw play is not a successful fair game. The current exact DRAW is
not qualification. Correct the ambiguous Japanese phrase "not a cutoff": the
solver did not exhaust its search budget, but the game ends at its ply limit.

This question was subsequently resolved explicitly by the user; see the
confirmed requirement below. Keep the original experiment interpretation and
raw evidence intact rather than rewriting its prior DRAW label.

## Confirmed product requirement — 2026-09-05, D-055

User: 「引き分けが存在しないゲームを作る必要があることを覚えておいて。」
Every legal play of an admitted game must terminate finitely with exactly one
A/B winner. No draws or indefinite continuations; sampled zero draws or an
optimal-play decisive value alone do not prove this universal requirement.
The current unchanged carrier-7 definition is ineligible because a legal DRAW
exists. Cancel its proposed draw-preserving cycle follow-up, not merely pause
it for further clarification. No human answer remains outstanding.

Preserve historical DSLs, tests, and raw results, including this exact DRAW.
No code, rule, timeout winner, or experiment change is made in this recording
task. This plan may finish only its existing regression/evidence acceptance
closeout; computational acceptance does not make the game product-eligible.
The next separately registered discovery scope must start from finite decisive
termination and retain finite-skill fairness, asymmetry and simplicity.

## Final closeout — 2026-09-05

The existing suite completed: `Ran 1219 tests in 5123.653s`, `OK (skipped=2)`;
session 43957 exited 0. Independent audit found no FAIL/ERROR and no source/test
change from `eb9e53fcc`. The two intended opt-in archive reconstructions remain
skipped. Both studies' computation/evidence are accepted, not their games as
products. Raw provisional labels and all experiment bytes remain unchanged.
See `experiments/reports/0016-0017-acceptance-closeout-ja.md`. No further call,
replay, candidate rescue or draw-cycle investigation is authorized here.
