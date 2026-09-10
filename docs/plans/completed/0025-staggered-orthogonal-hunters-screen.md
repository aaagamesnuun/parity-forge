> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan0025 — Staggered orthogonal hunters existing-agent screen

## Status and purpose

COMPLETED / ACCEPTED_TECHNICAL_EVIDENCE / GAME_NO_FLAG. Archived plan. Plan24 is
also completed and accepted as technical evidence with game disposition NO_FLAG.
Site work remains paused. The user asks us to continue until rules merit human
review.

Question: does the smallest fixed setup repair of Plan24 survive the same strict
human-attention screen with fresh seeds and unchanged agents? This is a
candidate-specific continuation, not a generic search method. It changes no
agent, evaluator, search algorithm, DSL primitive or shared engine.

## One fixed candidate and exposure

Use only experiments/proposals/
three-runners-two-staggered-orthogonal-hunters-v0.json definitions[0], hash
90b7f9e8f763183e8034b9c387ed8fa46f2150be21d044a135d8f3fefa3745ab.
5x5/A-first. A has3 forward-diagonal-or-straight MOVE runners and wins by
REACH_BOTTOM. B has2 orthogonal MOVE_CAPTURE hunters at(2,3),(3,1) and wins by
ELIMINATE A. Compared with Plan24, only the higher-column B starts one row
farther forward.

This is outcome-guided development after Plan24's aggregate and the two R/T4
loss traces. It is not independent confirmation and does not prove that B was
monotonically strengthened. The horizontally reflected setup is game-tree
isomorphic, but seeded random choices and canonical tie ordering need not be
reflection-equivariant. Before any Plan25 execution, the fixed convention is
to advance the higher-column hunter. The mirror is disclosed but must not be
run, substituted or used as backfill. Claims apply only to this exact wire.

Remaining runner-distance starts12, decreases on every A move and B capture,
and is preserved only by B ordinary movement. Every legal play is decisive by
23<cap25. Initial goals are false and each has a cooperative legal route.
A has at most9 legal actions, B at most8. Existing depth4 cumulative
cache-miss bounds remain A70956/B64240, below100000 per role/game without
assuming cache reuse.

Canonical parser/hash and the public old-region predicate in both role orders
passed. Independent limited source review confirmed the proof, goals, bounds and
documented legal response/counterline. It found no short universal result or dead
goal, but this is not an absence proof. See
docs/reviews/2026-09-06-three-runners-staggered-hunters-ja.md.

## Implementation boundary

Reuse scripts/plan0024_play.py byte-for-byte and pin it. Add only
scripts/plan0025_screen.py and tests/test_plan0025_screen.py for execution.
The screen wraps the unchanged adapter, public play_game, RandomAgent and
TerminalOnlyMinimaxAgent depths2/3/4. Policies R,T2,T3,T4; fresh agents per
role/game; one persistent seeded Random per game;100000 cumulative cache-miss
nodes per search role. Random work stays explicitly unmetered, not zero compute.
Preserve choices, input states, decisions, nodes, selected/applied prefix,
censors and failures. Replay each observed prefix at most once. Focused tests
use synthetic3x3 definitions and mocks only, never this5x5 candidate.

Do not add a Plan25 adapter, refactor a generic framework, or change src/,
research/, DSL, engine, agents, evaluator, solver or search.

## Frozen prospective schedule and stopping

Publish all81 potential attempts before production:

1. Existing exact solver once at100000 states. COMPLETE is TOO_EASILY_SOLVED and
   closes every game gate. UNKNOWN permits the base, not qualification.
2. Base T4/T4 and T3/T3, each seeds500..515:32 games. All must complete
   decisively. T4/T4 requires A wins5..11; T3/T3 requires A wins4..12.
   Otherwise close the later gates.
3. If base passes, run all48 remaining games:
   - confirmation T4/T4 seeds600..615:16;
   - sensitivity T4/T2 and T2/T4 seeds600..607:16;
   - simple challenge T4/R and R/T4 seeds600..607:16.

Fresh bands avoid reusing the Plan24 development seeds. Maximum80 games plus1
exact call, at most16,000,000 charged search nodes. No LLM inside computation.
Valid censor is UNKNOWN. Any exception, draw, PLY_LIMIT, source/publication
drift, invalid prefix/replay or natural-bound violation saves FAILED and stops.
Closed gates are NOT_STARTED_GATE_CLOSED. No retry, resume, backfill, cap
increase, deeper search, mirror run, seed substitution or extra PV replay.
Exact COMPLETE has one external PV replay; exact UNKNOWN has none.

Any completed T4 initial selection at ply0 with nonzero best terminal-only value
is SHORT_FORCED_RESULT and closes later gates. Once the base passes, run the
whole final48; do not stop selectively because a later threshold looks unlikely.
Fixed-first and ordered-policy conditions remain separate.

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

This is unchanged from Plan24. It only justifies human attention. It does not
establish perfect-play or human fairness, calibrated equal skill, hardness,
replayability or fun. T agents share one algorithm family; R is a simple
challenge. Report all denominators, ordered cells, censors, node counts and
descriptive Wilson95 intervals. fairness_established, hardness_established and
fun_established remain false. Never relax a failed gate to create a finalist.

## Registration and acceptance

Mechanically retarget the reviewed Plan24 screen only, then pass focused
synthetic tests and independent source/protocol review. Register this plan,
proposal, new screen/test and the reused adapter's pinned bytes in one clean
commit. Execute the single pilot and exactly one new full regression concurrently
from a clean isolated worktree at the full40-hex registration. Pin all tracked
Python plus this plan/proposal before and after attempts. Exclusive output:
experiments/runs/plan0025-staggered-orthogonal-hunters-v1.

Preserve raw outputs and audit without new game/solver/replay calls. A regression
failure prevents technical acceptance. Human eligibility waits for both the
regression and independent saved/source audits. Update PROJECT_STATE, this plan
and BACKLOG at checkpoints. No Site work, publication, outside testers, paid
services, automatic usage reset or compulsory question.

## Preparation checkpoint

The canonical data-only wire was fixed before Plan25 gameplay. Static and
independent limited reviews passed as described above. Independent prospective
plan reviewPASS: schedule, fresh seeds, unchanged gates/stops, bounds, orientation,
reuse boundary, provenance and claims are consistent.

The candidate-specific screen is a mechanical Plan24 retarget; only plan/data/
protocol/hash constants and seed bands changed. Its10 synthetic/mock tests passed
in2.212s and py_compile passed. Independent static implementation reviewPASS.
Root diff review confirmed the mechanical delta and then ran the reused adapter's
7 tests plus the10 screen tests together:17 passed in2.372s. Both new files are
frozen; Plan24 adapter is unchanged. Plan25 candidate game/solve/replay count was
zero through registration.

The fixed source was registered at
8b15e1ea44831e5af45d73f27f3c7c4af4be3e3b. The single pilot (session16352,
PID35739) and exactly one new full regression (session68935, PID35740) started
at06:04:26 JST on2026-09-06 from the clean detached worktree
/tmp/parity-forge-plan0025.gvR2Wy/checkout. Logs are pilot.log and full-suite.log
in its parent. Do not start duplicates, edit that worktree or interpret partial
artifacts. Await actual exits, then audit saved bytes.

Pilot session16352 finished exit0. Exact was UNKNOWN at100000 states. All32
base games completed decisively without censor/failure, observed7..19plies and
all GOAL. T4/T4 was A7/B9 and passed its5..11 gate; T3/T3 was A15/B1 and failed
its4..12 gate. The fixed final48 were not started and are gate-closed. Final
disposition is NO_FLAG, never human-review eligible. Do not rerun or add evidence.
Independent saved-only auditPASS:70 envelopes,68 publication hashes,182 pins,
all schedule/results/replays/nodes/bounds matched. See
experiments/reports/0025-staggered-hunters-findings-ja.md.

While the isolated regression runs, a separate data-only next draft was fixed
with production game/exact/replay count zero. It moves the remaining rear hunter to
row2 and records the Plan25 trace/horizon exposure explicitly. Independent
static review passed for the limited no-draw, goal, branching and bounded
short-result claims. This is not Plan25 evidence and cannot be registered or run
until Plan25's full suite and independent audit pass its technical closeout. See
docs/reviews/2026-09-06-three-runners-forward-hunters-ja.md.

Full regression session68935 finished exit0:1325 tests in5160.407s,
`OK (skipped=2)`. Log SHA256 is
93bd4ca03d2f9296ed1c96ebe191537df420ce4ba6430e06a3d33593eb5fbefb; PID35740 is
gone. Independent registered-source/log/main-run auditPASS: all10 Plan25 screen
tests and7 reused adapter tests passed,182 pins and68 publication hashes matched,
and all70 isolated/main run files were byte-identical. Plan25 is accepted as
technical evidence only; its game remains NO_FLAG and must not be rerun. See
experiments/reports/0025-acceptance-closeout-ja.md.
