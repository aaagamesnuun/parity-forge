> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan0038 — Bounded, scheduled new-game discovery

2026-09-10 JST. CLOSED / SUPERSEDED_BY_PRODUCT_EXCLUSION (D-080).
Episode2 remains technically complete and reviewed. The user's new prohibition
of placement-exhaustion loss cancels the proposed episode3 search-strength branch.
No episode3 manifest/claim/run exists at this closure. Unused capacity is not an
instruction to launch a substitute exhaustion game. Preserve all saved evidence;
this is a user-preference exclusion, not a new empirical or mathematical result.
Plan39 is the sole active plan. All continuation/launch text below is historical.
Authority: user requests「このままゲームのアイデアを探索していって　定期実行で。」
D-079 supersedes the completed Plan37's no-next-research boundary for new research,
not its frozen evidence, publication or no-rerun obligations.

## Objective and boundaries

Find mechanically asymmetric, deterministic two-player games worth a human trial.
Every legal play must terminate with exactly one winner: no draws; computational
exhaustion is UNKNOWN. Balance, depth and simplicity remain evaluation goals,
not consequences of software correctness or equal sampled wins. Boards may grow
when a specific hypothesis justifies it; 7x7 here is an inexpensive first probe.

Keep the public game Site and the code-only analysis GitHub repository unchanged.
No deployment, external tester recruitment, paid resources, account/access change,
private-research upload or old Plan34/35 query retry. Preserve all immutable runs,
fixtures and episode claims; do not access protected Plan13/14 membership/evidence.

## First prospective experiment: episode 2

- Manifest: `experiments/proposals/plan0038-finite-space-episode2-v0.json`.
- SHA256: `77a30650c8c84dea5390d0f4eb3279923534798ebaf9524d45916d5bdf93f751`.
- Empty 7x7, T4 versus L4 and O4 versus I4, each with A-first and B-first:
  four definitions. Only the allowed rotations in the DSL; no extra reflections.
- All placements consume four empty cells; at most 12 placements, then a player
  unable to move loses. This finite-capacity argument covers every legal play.
  Different role shape sets provide mechanical asymmetry, not proven balance.
- Research variable: game shape sets, including area3→4 and orientation counts.
  These geometry effects are not individually isolated. Generator/agent/evaluator/
  search code and profiles remain unchanged from the accepted finite-space engine.
- Same profiles and seeds as Plan32: two deny self-play, two search self-play,
  two crossed deny/search and two crossed random/search games per definition.
  Maximum32 games, not32 independent equal-strength fairness observations.
- Search: max512 actual transitions/decision, depth2, 50,000/game.
  Short-win queries: both roles, max3 plies and50,000 nodes/query. New shapes need
  their own queries; do not reuse old I3/L3 negative results. Limited FALSE or
  UNKNOWN is not absence of a general winning strategy or evidence of depth.
- CPU cap14,400 seconds; output cap16MiB. No cap escalation or retry on exhaustion.
- Independent read-only preregistration audit PASS: four hashes, nine source pins,
  exact policy/search/proof registration, schedule and shapes checked; validator
  actualexit0. No gameplay/proof search has run at this checkpoint.

Before launch verify manifest hash, current source pins, previous episode1's
completed receipt, absence of episode2 claim and absence of a duplicate worker.
Run exactly once using the existing engine:

```sh
PYTHONPATH=src python3 -m parity_forge.finite_space_batch \
  --manifest experiments/proposals/plan0038-finite-space-episode2-v0.json \
  --output experiments/runs/finite-space-campaign-v1/plan0038-finite-space-episode2-v0
```

Record the actual process/session identity, log and exit status. Retain failed
claims and partial evidence. Never launch again to recover missing or bad results.
The runner's replay validation is part of this run, not another set of samples.

## Review, improve, then choose the next unit

Read saved results without rerunning games. Report role wins separately from
first-player wins, split by policy pairing and strength; include completed search
depth, fallback, budget use and UNKNOWN. Compare only matched conditions. Preserve
raw labels and false human/fairness/depth/fun flags; no aggregate 50/50 promotion.
Cheap tactical defects or dominant roles eliminate a candidate, while shallow
policy disagreement identifies an evaluation uncertainty, not a fair candidate.

Episode3 is conditional on this review and must be registered before its results:
change either one game hypothesis OR the search/evaluation component, not both.
Maximum four definitions × eight games =32 additional games, CPU at most14,400s,
output16MiB, using the existing campaign's last episode slot. No automatic identical
screening loop. If selected games are revisited at a new search strength, record
the selection and matching explicitly; deterministic repeated proof checks are
calibration, not independent evidence. Do not replay the old Plan32 I3/L3 cohort.

This first block has at most64 new games, two batches and8 CPU-hours total.
After either useful candidate evidence or exhausted/non-informative screening,
write an evidence-backed review. At episode3 stop launching this campaign. Do not
delete/relabel episode claims or rename a run root to evade its ceiling. A later
bounded phase needs a distinct preregistered question and plan, with an explicit
explanation of what changes and why. The user's continuing research instruction
permits routine technical planning, not silent budget enlargement of this block.
If genuinely new resources, publication authority or human taste are necessary,
ask only for that choice. A limited candidate may be reported for optional trial;
do not certify fairness, depth or fun, or silently replace the currently live game.

## Scheduled operating loop and cost control

Use a same-task hourly heartbeat; installation/actual ID is recorded below.
Each wake reads state → this sole active plan → backlog and performs at most one
bounded unit: prospective review, launch, saved-output review or next-plan review.
If a worker is active, check it once and do not start another or wait repeatedly.
Do not re-read all history or repeat unchanged full test suites. Local deterministic
programs conduct games/search; no model calls per move. Source changes, if later
justified as a separate unit, require the mandated full regression once after
freeze; JSON/docs-only work does not require another 90-minute regression.

Every batch must answer what uncertainty decreased and what to change next.
Stay quiet on unchanged/non-actionable state. Notify only a materially promising
candidate, important finding/failure, completed research-block review or required
user action. No routine hourly report. At an actual impasse or deliberate research
pause, update/pause the heartbeat through the app; do not spend tokens on repeated
blocked turns. Do not alter unrelated automations.

## Progress

- [x] Archive completed Plan37; preserve Site, GitHub, sources and previous results.
- [x] Generate two geometry hypotheses and four deterministic DSL definitions.
- [x] Validate manifest and obtain independent prospective audit PASS.
- [x] Install the hourly same-task heartbeat and record actual ID.
- [x] Launch episode2 once after required preflight.
- [x] Obtain actual episode2 exit and independently audit saved results.
- [x] Review informativeness; episode3 CANCELLED by the new product exclusion.
- [x] Deliver episode2 limitations; close this branch and route to Plan39.

At the historical setup checkpoint, no gameplay, solver execution or quality result.

Scheduler: native app creation confirmed `automationId=parity-forge`, status ACTIVE,
name「Parity Forge 新ゲーム探索」, same-task every hour; subsequent native view succeeded.
Confirmation observed2026-09-09T22:02:53Z. No other automation changed. First
scheduled action is the one-time episode2 preflight/launch, not another plan-only
loop. Local automations require the computer and Codex app to remain running.

## First activation — 2026-09-09T23:05:02Z launch observation

PreflightPASS: proposal hash and nine manifest pins match, all206 accepted Python
pins unchanged; independent saved-only prior-episode claim/registration/result/
runtime auditPASS/COMPLETED. Episode2 claim/output absent before launch; no duplicate
worker observed. Started the registered command exactly once, zsh pipefail with tee
to `/tmp/parity-forge-plan0038.Mg1sXh/episode2.log`.

Session99989 (chunka4d9ee), shell96535, Python worker96538, tee96539. At the launch
observation the worker is RUNNING; actual exit is not yet available. The atomic
episode2 claim and registration now exist; do not start again. Canonical runner
registration hash is7d055213f04918e1045bc295d9e58ff96b202453b332d0a9913373946c7a095e;
the proposal hash above covers different JSON formatting of the same object.
Preserved receipt: `experiments/reports/0038-episode2-launch-receipt.json`.

This activation completed only the launch work unit. Next hourly unit checks the
existing session once and, if finished, records actual exit and independently audits
saved output. No polling loop, next episode, source change, full-suite rerun,
publication or fairness/depth/fun claim. Initial block still has a32-game reservation
for episode2 and at most32 additional games conditional on future episode3 review.

## Second activation — saved-result review, 2026-09-10T00:04:25Z observation

The one existing-session check returned actualexit0/chunkd391c5; worker96538,
shell96535 and tee96539 are absent. No rerun. RuntimeCOMPLETED, CPU45.483659s,
32/32games COMPLETE,7..10plies/267moves,0censor/draw/not-started/fallback.
Independent saved-only auditPASS: proposal/registration,9currentpins, claim/runtime
hashes, registered schedule and decision/proof/flag accounting. All206 Python pins
unchanged. No independent legal-move/winner/proof recomputation; runner replay267
was part of the original run, not new samples. Log copied once to permanent evidence
and byte-compared; launch checkpoint remains unchanged.

See `experiments/reports/0038-episode2-exit-receipt.json` and
`experiments/reports/0038-episode2-findings-ja.md`. T/L A-first/B-first eachA2:B6;
O/I A-firstA2:B6, B-firstA1:B7. T/L search-self each1:1, deny-self each0:2;
O/I bothselftypes allB. Search139 decisions:52onlydepth1/87depth2;52budget hits.
Eight new3-ply queries COMPLETE/false,22,683transitions, no general depth claim.
All four rawFURTHER_REVIEW and false human/quality flags preserved.

This unit reduced uncertainty about new geometries under the existing weak policies,
but did not separate role advantage from evaluator/search weakness. No candidate
promotion. Next unit considers one preregistered search-strength change on fixed
new rules, with explicit target selection/control, expected information and stop
conditions; no new geometry at the same time. This is a question for registration,
not an episode3 manifest or launch. At most32 remaining games/14,400CPU seconds;
do not poll finished99989, replay episode2 or bypass its consumed claim.
