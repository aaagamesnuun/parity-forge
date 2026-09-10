> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan0026 — Two forward orthogonal hunters existing-agent screen

## Status and purpose

COMPLETED / ACCEPTED_TECHNICAL_EVIDENCE / GAME_NO_FLAG. Archived plan. The
registered full regression and independent registered-source/log/main-run
closeout audits passed. This candidate is not eligible for human playtesting.
Plan25 passed its full suite, independent registered-source/log/main-run audit
and formal technical acceptance. Site work remains paused. No Plan26 game,
production exact call, replay or output is authorized before the registration
specified below.

Question: does moving Plan25's remaining rear hunter forward by one row change
the observed T3 gate failure associated with the horizon pattern without making
the passing T4 balance B-dominant? This is one candidate-specific, data-only
continuation using the existing evaluator and agents. It is not a generic
discovery method.

## One fixed candidate and disclosed exposure

Use only experiments/proposals/
three-runners-two-forward-orthogonal-hunters-v0.json definitions[0], canonical
definition hash
aed723e270cacd8bdfe3c87db22299d8ccf1045e63c0cebbd638d900d0491b94.
5x5/A-first. A has three forward-diagonal-or-straight MOVE runners at
(0,1),(0,2),(0,3) and wins by REACH_BOTTOM. B has two orthogonal MOVE_CAPTURE
hunters at(2,1),(2,3) and wins by ELIMINATE A. Compared with Plan25, only
(3,1) moves to(2,1); the setup regains horizontal reflection symmetry.

This is outcome-and-trace-guided development after Plan25, not a retry,
backfill, rescue, independent confirmation or monotone-strength claim. Plan25
T4/T4 was A7/B9 but T3/T3 was A15/B1. Saved traces are consistent with an
odd-depth terminal-horizon effect: on B turns, T3 stops before an A runner's
next two-A-move finish, while T4 can distinguish some capture replies. The
causal share and perfect-play value remain unknown. Advancing B may overcorrect
the T4 cell and must fail honestly if so.

Production game/exact/replay count is zero. A disclosed pre-registration,
solver-like bounded AND/OR analysis used existing engine transitions and
logical short-circuiting. It queried horizons13/14 for both target roles and
incurred cumulative153753 cache misses over distinct
(state,target,horizon) argument tuples.
Neither role could force a win within its first seven turns. It does not cover
later forced wins, and is not fairness, hardness or depth evidence.

## Static admissibility

The final fixed wire parses and satisfies
`json.loads(canonical_json(parse_definition(raw))) == raw`; its hash, unique
in-board setup, A-first and cap25 are fixed above. Initial goals are both false.
Each goal has a legal cooperative route. The public old-six semantic predicate
is false in both role orders.

For every nonterminal state let D be the sum, over surviving A pieces, of
4-row. Initially D=12. Every A move decreases D by exactly1. Every B capture
removes a positive term. Only an ordinary B move preserves D. With alternating
A-first turns, A can act at most12 times and B at most11 times, so every legal
play has exactly one winner by23ply, strictly below cap25. PLY_LIMIT and draw
are unreachable; earlier no-legal-action is also decisive.

A has at most9 legal actions and B at most8. Without cache reuse, a depth4
selection visits at most A5913 or B5840 nodes. Over at most12/11 selections,
the role totals are A70956 and B64240, each below100000 per role/game. These
bounds justify the fixed computation cap, not game hardness.

Before registration, independently reread the fixed proposal bytes and recheck
canonical/hash, public-region exclusion, no-draw proof, goal lines and bounds.
Reject before registration if a direct short universal win, dead goal or proof
defect is found. The bounded seven-turn result is not an absence proof beyond
its horizon.

## Implementation boundary

The Plan25 closeout dependency has passed. Reuse scripts/plan0024_play.py
byte-for-byte and pin it. Mechanically retarget the
reviewed Plan25 screen into scripts/plan0026_screen.py and add only
tests/test_plan0026_screen.py. Change candidate/plan/protocol/hash constants,
fresh seed bands and exposure labels only, plus a fail-closed check that the
proposal has exactly the frozen top-level keys, status and exposure. Focused
tests remain synthetic3x3 and mocked; they must never execute this5x5 candidate.

Do not change src/, research/, DSL, engine, evaluator, solver, terminal-search
semantics, agent depths or tie-breaking. Do not add a Plan26 adapter or generic
framework. Policies remain R,T2,T3,T4, with fresh agents per role/game, one
persistent seeded Random per game, and100000 cumulative cache-miss nodes per
search role. Random remains explicitly unmetered, not zero compute. Save
choices, states, values, selected/applied prefixes, censors, failures and at
most one replay of each observed prefix.

## Prospective schedule and stopping

Before any production computation, publish all81 potential attempts:

1. Existing exact solver once at100000 states. COMPLETE is TOO_EASILY_SOLVED
   and closes all game gates. UNKNOWN only permits the base; it is not evidence
   of hardness or qualification.
2. Base T4/T4 and T3/T3, each seeds700..715:32 games. Every game must finish
   decisively. T4/T4 requires A wins5..11; T3/T3 requires A wins4..12.
   Otherwise the final48 remain NOT_STARTED_GATE_CLOSED.
3. Only if base passes, run the whole final48:
   - confirmation T4/T4 seeds800..815:16;
   - sensitivity T4/T2 and T2/T4 seeds800..807:16;
   - simple challenge T4/R and R/T4 seeds800..807:16.

These bands are fresh relative to Plans24/25. Maximum80 games plus one exact
call and16,000,000 charged search nodes. No LLM is used inside computation.
Any exception, draw, PLY_LIMIT, source/publication drift, invalid prefix/replay
or23ply-bound violation saves FAILED and stops. Exact COMPLETE gets one
external PV replay; exact UNKNOWN gets none. Any completed T4 initial selection
with nonzero best terminal-only value is SHORT_FORCED_RESULT and closes later
gates. Once base passes, do not selectively stop the final48 for an emerging
numerical miss; hard failures and short-forced evidence still stop as specified.

Game search-budget exhaustion is UNKNOWN_CENSORED, never a result or draw. Any
base censor prevents the all-complete base and closes final48 after the whole
fixed base is saved. If final48 has opened, a game censor is saved and the
remaining fixed final attempts continue; eligibility is nevertheless impossible
because all80 must complete. UNKNOWN never becomes evidence of difficulty.

No retry, resume, backfill, seed substitution, threshold relaxation, cap
increase, deeper search, mirrored duplicate, extra policy, extra game or extra
PV replay. Fixed-first and ordered-policy cells remain separate.

## Human-attention gate

HUMAN_REVIEW_ELIGIBLE requires all of the following, unchanged from Plans24/25:

- exact UNKNOWN100000 and all80 games complete with one A/B winner;
- A wins5..11 in each base and confirmation T4/T4 cell;
- T3/T3 A wins4..12;
- T4 role wins at least6/8 in each ordered T4/T2 cell;
- T4 role wins at least7/8 in each ordered T4/R cell;
- T4 has both+1 and-1 legal alternatives in at least2 distinct complete games
  for each acting role;
- no known direct short universal win, dead goal or proof defect;
- independent saved/source audit and exactly one new full regression pass.

This gate permits human attention only. It does not establish perfect play,
human fairness, equal skill, practical hardness, replayability or fun. Report
all denominators, ordered cells, censors, node counts and descriptive Wilson95
intervals. T agents share one algorithm family and R is only a simple challenge.
Keep fairness_established, hardness_established and fun_established false. Never
reinterpret a failed threshold to manufacture a finalist.

## Activation, registration and acceptance

Plan25 was accepted only after its actual full-regression exit0/Ran/OK and an
independent registered-source/log/main-run auditPASS. This plan was activated
without changing the candidate or schedule. The final static audit, mechanical
screen/test, focused synthetic tests and independent source/protocol reviews
described below are complete and frozen. Register the active plan, proposal,
screen/test and reused adapter pin in one clean commit.

Only after that registration, launch one pilot and exactly one new full
regression concurrently from a clean isolated worktree at the full40-hex
registration commit. Exclusive output:
experiments/runs/plan0026-two-forward-orthogonal-hunters-v1. Preserve raw
artifacts and audit them without new candidate calls. A regression failure
prevents technical acceptance. Human eligibility waits for all gates, audits
and the full suite. Update PROJECT_STATE, active plan and BACKLOG at each
checkpoint. No Site work, publication, outside tester, paid service, automatic
usage reset or compulsory human question.

## Activation checkpoint

Plan25 passed its single full regression and independent closeout audit and is
archived as accepted technical evidence with game disposition NO_FLAG. This
plan was activated without changing its fixed candidate, fresh seeds, gates or
stops. Root and independent static audits reconfirmed the canonical definition
hash, initial goals/mobility, public old-six exclusion and the stated proof/
node bounds. The bounded seven-turn AND/OR result was independently reproduced
with the disclosed153753 cumulative cache misses. Production Plan26 game,
exact, replay and output counts remain zero.

The candidate-specific screen/test are now implemented. Compared with Plan25,
the screen changes only plan/data/protocol/hash, fresh700/800 seeds, the complete
exposure label, and fail-closed proposal metadata validation. All gate, stop,
censor, replay, pin, publication and summary logic is otherwise unchanged. The
test changes only the corresponding constants/seeds/mock edges and metadata
assertions; every fixture remains mocked or synthetic3x3.

Pycompile passed. Root's reused-adapter plus screen run passed17 tests in2.168s:
7 adapter and10 screen. Independent implementation and source/protocol audits
PASS with no blocker. Frozen SHA256: screen
3cfbd504673c1d8ea57e1e851716d53671a8472cce66ef61cb927ae9d0099771, test
c8ba77da5d275323e9834b3d58621b2ded5d3a8a05e232caf9bde5e99fb71cfd, reused
adapter146342883ee512ea16f3b96da3cd4258323360217ffe724327906521633e9758.
Expected registration pins are182 tracked Python plus active plan/proposal=184.
Plan26 production game/exact/replay/output counts were zero through registration.

The fixed source was registered at
0bf342f04f833505706a8564755d29217cb3f6ff. Registered static re-readPASS with184
pins. The single pilot (session99923, PID50883) and exactly one full regression
(session80914, PID50884) started concurrently at08:20:11 JST on2026-09-06 from
the clean detached worktree /tmp/parity-forge-plan0026.JdpTKU/checkout. Logs are
pilot.log and full-suite.log in its parent. Do not start duplicates, edit that
worktree or interpret partial artifacts.

The pilot finished exit0. Exact was `UNKNOWN_CENSORED` at exactly100,000 states
with0 replay. All32 base games completed by `GOAL`, A25/B7 overall, with zero
game censor/draw/failure and7..19ply. T4/T4 was A12/B4, outside its fixed A5..11
gate; T3/T3 was A13/B3, outside its fixed A4..12 gate. Both miss their upper
bound by one A win, so `base_pass=false`, disposition `NO_FLAG`, and the final48
are exactly `NOT_STARTED_GATE_CLOSED`. No retry or supplemental execution is
permitted. Tactical witness counts were A3/B4; no T4 initial short-forced value
was observed. Charged nodes were A91626/B84212.

Independent saved-only auditPASS:70 canonical envelopes,68 publication hashes,
184 registered source pins, the complete81-attempt schedule, all33 saved
attempts,48 gate closures, node/replay/prefix accounting and23ply bounds match.
The isolated70-file run was copied byte-identically to main. See
experiments/reports/0026-two-forward-hunters-findings-ja.md. The one registered
full regression finished: session80914 exit0, PID50884 gone,1335 tests in
5416.084s, OK(skipped2). Log SHA256 is
701b5dcbbca4b36dfe5c3fe47f74363271a8134ed8863230728b3c7c8f151597.
Two independent closeout checks PASS:184/184 source pins,68/68 publication
hashes,70/70 canonical envelopes and all70 isolated/main files matched; the
normalized run-tree SHA256 is
9fa3ef1340b86d500435f8711aac4f000137b50a7487fd32d32f17de09e1128c. Plan26 is
accepted as technical evidence only; its game remains NO_FLAG. See
experiments/reports/0026-acceptance-closeout-ja.md. Never restart or supplement
the pilot, exact call, games, replays or suite.
