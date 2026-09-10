> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan0027 — Three-currents SWAP/PUSH existing-agent screen

## Status and dependency

COMPLETED / ACCEPTED_TECHNICAL_EVIDENCE / GAME_NO_FLAG. Plan26
passed technical closeout with game disposition NO_FLAG. The fixed definition,
proof, bounded exposure, candidate screen/test and source/protocol boundaries
passed independent review. Registered source and output are immutable. Do not
start a duplicate, change the isolated checkout, or interpret partial artifacts.

## One fixed question and candidate

Question: after retiring Plan24–26's coordinate-only runner/hunter adjustments,
can one structurally different but existing-DSL SWAP/PUSH race survive the same
bounded human-attention screen without an obvious short universal strategy?

Use only
`experiments/proposals/three-currents-swap-push-v0.json` definitions[0], fixed
before analysis at commit`1da2eadca`, definition hash
`aa3079277a9089aa8758fa04f0d81be09544af39ba9338524cf97e6f98490209`.
The later proposal-only metadata edit discloses bounded/goal-line exposure and
does not change that definition; current proposal file SHA256 is
`24429c2c3f703367b0a1361f98eddf3c762c91f57e847518323968f2f5cc7269`.
5×5/A-first, three A and three B pieces. A moves right/down with SWAP and reaches
BOTTOM; B moves up/left with PUSH and reaches TOP. This is public-trace-guided
development after Plans24–26, not untouched confirmation or a rescue of them.

## Static admissibility and disclosed analysis

Require exact canonical roundtrip/hash and the proposal's frozen top-level keys,
status and exposure. Initial goals are false and initial-board mobility is A5/B5.
Two fixed cooperative engine lines establish functional goals: A wins at7ply and
B at8ply. A's last goal move is an actual SWAP. A separate fixed4ply prefix
verifies an actual B PUSH. The public old-six predicate is false in both role
orders without member access.

The exact required exposure is
`SOURCE_DESIGNED_AFTER_PLAN0024_0026_PUBLIC_TRACE_DIAGNOSIS_AND_`
`PREREGISTRATION_GOAL_EFFECT_AND_SHADOW_COUNTERLINES_AND_TWO_BOUNDED_`
`AND_OR_TRAVERSALS_EXPOSED_NOT_CONFIRMATION`; `TWO` names the root and
independent traversal implementations, each queried once per target.

For A at`(r,c)`, let`qA=(4-r)+(4-c)`; for B let`qB=r+c`; define
`Phi=sum(qA)+2sum(qB)`. It starts54. A empty move/SWAP decreases it1/3; B empty
move/PUSH decreases it2/1. Thus every legal play ends with exactly one A/B winner
by54ply, strictly before cap55. PLY_LIMIT/draw are unreachable; goal/no-action
precedence is decisive.

Each role has at most6 actions. A depth4 selection costs at most1554 nodes without
cache reuse. Each role is selected at most27 times, giving41958 nodes/role/game,
below the fixed100000 cap. This is a resource proof, not hardness evidence.

Root's disclosed bounded AND/OR used one successful query per target, logical
short-circuiting, cached`(state,target,horizon)` and100000 misses/target. Neither
A by13ply nor B by14ply can force a win: A false at28639 misses/13184 hits; B
false at12681 misses/3429 hits. Two prior coding attempts stopped before recursion.
An independent implementation used salted-SHA256 action order and reproduced
A13 false at25883 misses/12344 hits and B14 false at15895 misses/5736 hits.
Successful queries total2/target; the result says nothing beyond each role's
first7 turns and is not a fairness/depth/fun result.

Manual source challenge refuted each single-piece straight race. It also fixed
and refuted two reproducible natural B policies: committed home-file shadow with
no horizontal reassignment, and eager nearest-right queue reassignment. Their
legal A counterlines win at13 and15ply; root checked each fixed line through the
engine once. A7ply nonterminal prefix also realizes horizontal B-PUSH followed by
horizontal A-SWAP. This excludes only those pure policies and proves liveness,
not the absence of conditional hybrids or longer winning strategies.
The review document is authoritative for their complete deterministic tie rules,
two exact counterline action arrays and the seven-action effect prefix.

## Prospective implementation boundary

Plan26 acceptance and the independent prospective review passed. Reuse
`scripts/plan0024_play.py` byte-for-byte. Mechanically retarget the reviewed
Plan26 screen into`scripts/plan0027_screen.py` and add only
`tests/test_plan0027_screen.py`. Change candidate/plan/protocol/hash, BOUND54,
PLY_LIMIT55, fresh seed bands and exposure text. Preserve all evaluator, gate,
stop, censor, replay, pin and publication semantics. The protocol/output id is
`plan0027-three-currents-swap-push-v1`.

The unchanged adapter executes and replays SWAP/PUSH correctly but action kind
alone does not distinguish empty movement from a realized conditional effect.
In the candidate-specific screen only, derive from each saved input state and
selected action whether A entered an opponent cell (real SWAP) or B entered an
opponent cell (real PUSH). Also count T4-selected horizontal actions. Add mocked/
synthetic tests for the derivation; do not change the adapter or shared source.

Only COMPLETE games count. Each counted decision must have
`selection_status=SELECTED`, and its selected action must equal the applied
action at that ply. A real effect requires an opponent piece at the destination
in the saved input state; effect counts include every scheduled policy. A
horizontal T4 selection requires that actor's scheduled policy to be T4 and
displacement`(0,+1)` for A or`(0,-1)` for B. Count each game at most once per
actor/evidence category and report distinct-game counts.

Do not change src/, research/, DSL, engine, solver, agents, terminal-only values,
tie-breaking or shared framework. Tests stay mocked or synthetic3×3 and must not
execute this5×5 candidate. Expected registration pins after the two Python files
are184 tracked Python plus active plan/proposal=186; recompute rather than trust.

## Prospective fixed schedule

Publish all81 attempts before production computation:

1. Existing exact solver once at100000 states. COMPLETE closes all game gates as
   TOO_EASILY_SOLVED. UNKNOWN only opens base and is not hardness evidence.
2. Base T4/T4 and T3/T3, seeds900..915:32 games. All must be decisive. T4/T4
   requires A wins5..11; T3/T3 requires A wins4..12. A miss/censor closes final48.
3. Only after base pass, run all final48:
   - T4/T4 confirmation seeds1000..1015:16, A wins5..11;
   - T4/T2 and T2/T4 seeds1000..1007:16, T4 role wins at least6/8 each;
   - T4/R and R/T4 seeds1000..1007:16, T4 role wins at least7/8 each.

Maximum80 games, one production exact call and16,000,000 charged search nodes.
No LLM is used inside computation. Game censor is UNKNOWN_CENSORED, never a game
result. Any draw, PLY_LIMIT, exception, source/publication drift, invalid prefix/
replay,54ply-bound violation or initial T4 nonzero terminal-only best value stops
as specified. Once final48 opens, ordinary numerical misses/censors do not select
which remaining attempts run; hard failure/short-force still stops.

No retry, resume, backfill, seed substitution, threshold relaxation, cap/depth
increase, mirrored duplicate, added policy/game or extra replay.

Exact COMPLETE receives exactly one external PV replay; exact UNKNOWN receives
zero. Each observed game prefix is replayed exactly once inside its original
attempt. Saved-only audits never invoke another replay.

## Human-attention and acceptance gates

HUMAN_REVIEW_ELIGIBLE requires exact UNKNOWN100000, all80 games complete with one
winner, every fixed cell threshold, T4 legal alternatives of both+1 and-1 in at
least2 complete games for each acting role, at least2 distinct complete games
with a realized A-SWAP and at least2 with a realized B-PUSH, and at least2
distinct complete games where T4 selects a horizontal move for each acting role.
It also requires no known short/simple universal win, dead goal/option or proof
defect, independent saved/source audit and exactly one registered full regression
pass.

This only permits human triage. Keep fairness_established, hardness_established
and fun_established false. Do not call mixed AI wins, exact UNKNOWN or tactical
witnesses, realized effects or horizontal selections proof of human fairness,
depth, replayability or fun. No Site work,
publication, paid resource, outside tester or compulsory human question.

## Activation checkpoint

Plan26's registered full regression finished exit0 with1,335 tests in5,416.084s,
`OK (skipped=2)`. Two independent closeout checks matched184 source pins,68
publication hashes,70 canonical envelopes and all70 isolated/main run files.
Plan26 is archived as accepted technical evidence; its game remains NO_FLAG and
must not be rerun or supplemented.

The fixed current Plan27 proposal/plan/review bytes passed independent prospective
review for their limited definition, proof, exposure, schedule, telemetry, pin
and claim-boundary assertions. Candidate production game/exact/replay/output
counts remain zero.

The candidate-specific screen/test are now implemented without changing the
reused Plan24 adapter or any shared source. Besides Plan27 constants, Phi54/cap55,
fresh900/1000 seeds and the exact exposure, the screen adds only fail-closed
derivation of realized A-SWAP/B-PUSH and scheduled-T4 horizontal selections from
the saved pre-action state and the selected/applied action. Only COMPLETE games
count, once per actor/category/game. All prior exact/base/final, censor, stop,
replay, publication and numerical gates remain unchanged.

Pycompile passed. Root's reused-adapter plus screen run passed20 tests in2.342s:
7 adapter and13 Plan27 screen. Independent reruns passed20/20 in2.381s and
2.318s; separate implementation, protocol and pre-registration source audits
all PASS with no blocker. Frozen SHA256: screen
1001a5d50cc23c22f3b436e2c5c5898dea88f33b6315cb54dc64f5826b3a7ac6, test
29edbcb7a69dcef17597ddac4202b0ec12ceca2f04d8744ab4d0d7f6255f8918, reused
adapter146342883ee512ea16f3b96da3cd4258323360217ffe724327906521633e9758.
Expected registration pins were184 tracked Python plus active plan/proposal=186.
Through the pre-registration review, no Plan27 output or running process existed;
the two new Python files were then frozen for the single registration commit.

The fixed source was registered at
ca3451bb478aed518e34ff5e69ad362f64771d69. Its clean detached worktree is
`/tmp/parity-forge-plan0027.mTxbu8/checkout`; source re-read matched186 pins
(184 tracked Python plus active plan/proposal), the proposal and canonical
definition hashes, and the configured54/55 bounds.

One initial shell command at18:27:31 JST exited1 before importing this module:
`PYTHONPATH=src python3 scripts/plan0027_screen.py` could not resolve the
`scripts` package. It never entered `run_pilot`, reserved output, loaded the
candidate or called exact/game/replay, so two independent reviews classify it
as a preserved preflight launcher failure, not a production attempt. Its log is
`/tmp/parity-forge-plan0027.mTxbu8/pilot-launcher-failure.log`, SHA256
63b0dfefcf188ac891442e6cd9e84a1ecd5673ae64920b7487ddc837066358e6.

The first and only production pilot (session67283, PID71418) started correctly
as a module at18:32:30 JST and finished exit0. Exact was UNKNOWN_CENSORED at
100,000 states with0 replay. All32 base games completed by GOAL, A24/B8 overall,
with zero game censor/draw/failure and7..22ply. T4/T4 was A12/B4, outside its
fixed A5..11 gate by one A win; T3/T3 was A12/B4 and passed at its A4..12 upper
edge. Thus `base_pass=false`, disposition `NO_FLAG`, and the final48 are exactly
`NOT_STARTED_GATE_CLOSED`. No retry or supplemental execution is permitted.

Realized-effect distinct games were A-SWAP9/B-PUSH5; scheduled-T4 horizontal
selection games A15/B16; tactical witnesses A8/B3. These observed gates cannot
rescue the base miss. Charged nodes were A37,321/B33,260. Independent saved-only
audit PASS:70 canonical envelopes,68 publication hashes,186 registered source
pins, the complete81-attempt schedule, all33 saved attempts,48 gate closures,
all decisions/legal choices/nodes/replays/Phi and new telemetry match. The
isolated70-file run was copied byte-identically to main. See
experiments/reports/0027-three-currents-findings-ja.md.

The exactly one full regression (session78528, PID70567) finished exit0:
1,348 tests in5,351.812s, `OK (skipped=2)`; PID70567 is gone. Log SHA256 is
`107af4476fa1e6b6d2beaa1509cf47aa43ee2e56a53862838085b600fcbb7253`.
Independent closeout audits matched186 source pins,68 publication hashes,
70 canonical envelopes and all70 isolated/main files byte-for-byte, with no
symlink or drift. Normalized run-tree SHA256 is
`11af60946eeb862387ffd820bd80b029ffbcafcc933ef6de57aeb6b109b7e7ab`.
Plan27 is accepted as technical evidence only; its game remains NO_FLAG. See
`experiments/reports/0027-acceptance-closeout-ja.md`. Never start, resume,
replace or supplement its pilot, exact call, games, replays or full regression.
