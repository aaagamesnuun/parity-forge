> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan0024 — Two-orthogonal-hunters existing-agent screen

## Status and purpose

COMPLETED / ACCEPTED_TECHNICAL_EVIDENCE / NO_FLAG. Historical final status.
Plan23 was
rejected before registration by an independently verified universal A6 win.
Site work remains paused. The user asks us to continue until rules merit human
review.

Question: does one source-repaired, no-draw runner/hunter definition survive a
bounded screen using unchanged existing random and terminal-only minimax agents?
This plan adds an audit adapter and experiment runner only. It changes no agent,
evaluator, search algorithm, DSL primitive or generic discovery method.

Separate system-planning dialogue on2026-09-06 considers rule structures that
could make simple forced strategies fail before refining its verifier draft.
See docs/reviews/2026-09-05-game-generation-planning-dialogue-ja.md. Those
untested hypotheses do not alter this registration or its fixed result gates.

## One fixed candidate and exposure

Use only
experiments/proposals/three-runners-two-orthogonal-hunters-v0.json definitions[0],
hashba966ffe27f3a9ceeccba083ecc23cfb25cb4ade831c206392eacd7de4219b76.
5x5/A-first. A has3 forward-diagonal-or-straight MOVE runners and wins by
REACH_BOTTOM. B has2 orthogonal MOVE_CAPTURE hunters and wins by ELIMINATE A.
Initial positions and full rules are in the canonical wire.

Remaining runner-distance starts12, decreases on every A move and B capture,
and is preserved only by B ordinary movement. Every legal play is decisive
by23<cap25. Initial goals are false and each has a cooperative legal route.
A has at most9 legal actions, B at most8. Existing depth4 cumulative
cache-miss bounds are A70956/B64240, below100000 per role/game without assuming
cache reuse.

The one-hunter A6 proof no longer transfers because separate orthogonal hunters
can intercept both edge runners. Permanent dual camping is not itself universal
because B cannot pass. A bounded source review through six turns found no
universal winner, but did not prove absence. Full-Moore two-hunter, straight-only
runner, dense CONVERT and one-hunter alternatives were exposed and rejected
before this plan. This is source-designed development, not untouched confirmation.
The signature is outside the public old-six and role swaps; do not access old
candidate members or evidence.

## Adapter qualification

New ownership only scripts/plan0024_play.py, scripts/plan0024_screen.py and their
focused tests. The play adapter wraps unchanged public play_game and unchanged
RandomAgent or TerminalOnlyMinimaxAgent depths2/3/4. Policies R,T2,T3,T4.
Fresh agents per role/game, one persistent seeded Random per game,100000
cumulative cache-miss nodes per search role. Random work is explicitly unmetered,
not zero compute. Preserve canonical choices, input states, decisions, nodes,
selected-versus-applied prefix, censors and failures. Replay each observed prefix
at most once. Calibration uses synthetic3x3 definitions only and never executes
the5x5 candidate.

## Frozen prospective schedule and stopping

Publish all81 potential attempts before production:

1. Existing exact solver once at100000 states. COMPLETE is TOO_EASILY_SOLVED and
   closes every game gate. UNKNOWN permits the base, not qualification.
2. Base T4/T4 and T3/T3, each seeds300..315:32 games. All must complete
   decisively. T4/T4 requires A wins5..11; T3/T3 requires A wins4..12.
   Otherwise close the later gates.
3. If base passes, run all48 remaining games:
   - confirmation T4/T4 seeds400..415:16;
   - sensitivity T4/T2 and T2/T4 seeds400..407:16;
   - simple challenge T4/R and R/T4 seeds400..407:16.

Maximum80 games plus1 exact call, at most16,000,000 charged search nodes.
No LLM inside computation. Valid censor is UNKNOWN. Any exception, draw,
PLY_LIMIT, source/publication drift, invalid prefix/replay or natural-bound
violation saves FAILED and stops. Closed gates are NOT_STARTED_GATE_CLOSED.
No retry, resume, backfill, cap increase, deeper search or extra PV replay.
Exact COMPLETE has one external PV replay; exact UNKNOWN has none.

Any completed T4 initial selection at ply0 with nonzero best terminal-only value
is SHORT_FORCED_RESULT and closes later gates. Fixed-first and ordered-policy
conditions remain separate.

## Human-attention gate

HUMAN_REVIEW_ELIGIBLE requires prospectively:

- exact UNKNOWN100000 and all80 games complete with one A/B winner;
- A wins5..11 in EACH base/confirmation T4/T4 cell;
- T3/T3 A wins4..12;
- T4 role wins at least6/8 in EACH ordered T4/T2 cell;
- T4 wins at least7/8 in EACH ordered T4/R cell;
- T4 has both+1 and-1 legal alternatives in at least2 distinct games for EACH
  acting role;
- no known direct short universal win, dead goal or proof defect;
- independent saved/source audit and exactly one new full regression pass before
  asking the human to play.

This gate only justifies human attention. It does not establish perfect-play or
human fairness, calibrated equal skill, hardness, replayability or fun. T agents
share one algorithm family; R is a simple challenge only. Report all denominators,
ordered cells, censors, node counts and descriptive Wilson95 intervals.
fairness_established, hardness_established and fun_established remain false.
Never relax a failed gate to create a finalist.

## Registration and acceptance

Focused synthetic tests and independent source/protocol review must pass first.
Register plan, proposal, adapter, runner and tests in one commit. Execute the
single pilot and exactly one full regression from a clean isolated worktree at
the full40-hex registration. Pin all tracked Python plus this plan/proposal
before and after attempts. Exclusive output:
experiments/runs/plan0024-two-orthogonal-hunters-v1.

Preserve raw outputs and audit without new game/solver/replay calls. Update
PROJECT_STATE, this plan and BACKLOG at checkpoints. No Site work, publication,
outside testers, paid services, automatic usage reset or compulsory question.

## Preparation checkpoint

Canonical parser/hash and public old-region checks passed without gameplay.
Independent prospective plan/wire reviewPASS:81 schedule, ordinal32 base stop,
ordered thresholds,23-ply proof, depth4 caps, provenance and claim limits.
A second independent six-turn source check confirmed that the old A6 split is
blocked and supplied a legal counterexample to a tempting permanent B-coverage
strategy; it found no complete winner and makes no absence claim.

The R/T2/T3/T4 audit adapter was mechanically retargeted to Plan24 and its7
synthetic3x3 tests passed in0.100s. Independent source review of the identical
pre-retarget semantics passed. The fixed screen runner's10 synthetic tests
passed in2.194s and its independent static review found no blocker. Root then
ran all17 adapter/screen tests together:17 passed in2.290s. All four files are
frozen. Candidate game/solve/replay count was zero through registration.

The fixed source was registered at
10919fb9ccc4a03bafd408f172f69e61ac84e290. The single pilot (session60252,
PID19945) and exactly one full regression (session13168, PID19946) started at
03:53:02 JST on2026-09-06 from the clean detached worktree
/tmp/parity-forge-plan0024.YBi3xF/checkout. Logs are pilot.log and
full-suite.log in its parent. Do not start duplicates, edit that worktree or
interpret partial artifacts.

Pilot session60252 finished exit0. Exact was UNKNOWN at100000 states and all80
games completed decisively without censor/failure: total descriptive A48/B32,
observed7..19plies. Ordered A wins were T4/T4 base10/16, T3/T3 12/16,
T4/T4 confirm6/16, T4/T2 8/8, T2/T4 2/8, T4/R 8/8 and R/T4 2/8.
The last cell means B-side T4 won6/8 against random, below its fixed7/8 gate;
all other numerical and tactical-witness gates passed. Final disposition is
NO_FLAG, never human-review eligible. Do not rerun or add evidence. Independent
saved-only auditPASS:166 envelopes,164 publication hashes,180 pins, all81
attempts/cells/nodes/replays/bounds matched without drift. The already-running
full regression remains pending. See
experiments/reports/0024-two-orthogonal-hunters-findings-ja.md.

While that fixed regression runs, a follow-on data-only draft was prepared
without game/solve/replay: move only one B hunter from(3,3) to(2,3). Canonical
hash90b7f9e8f763183e8034b9c387ed8fa46f2150be21d044a135d8f3fefa3745ab.
Parser/hash/public-region checks and independent limited proof reviewPASS;
the≤23 and node bounds remain. This outcome-guided draft is not active,
registered or confirmed. Do not execute it before Plan24 technical closeout and
a new prospective plan. See docs/reviews/2026-09-06-three-runners-staggered-hunters-ja.md.

## Final acceptance

Full regression session13168 finished exit0:1315 tests in5452.647s,
OK(skipped=2). Log SHA256
59f567ea1cc056f725f930e0dc7699ae76f5e5050b2f29c310606e9ab6c893cc.
Independent registered-source/log auditPASS: registration HEAD and180 pins
unchanged, all17 Plan24 tests passed, PID gone, and all166 isolated/main run
files are byte-identical. The computation and evidence are accepted. Raw
provisional fields remain immutable; the game stays NO_FLAG and ineligible for
human review. Never restart its pilot, exact, games, replays or full regression.
See experiments/reports/0024-acceptance-closeout-ja.md.
