> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan 0020 — Existing-method directional race pilot

## Status and purpose

COMPLETED / ACCEPTED as computation and evidence. No game qualified.
The immutable preregistration is the version at637c9ae144be5353343234697120e631d1a64d4e;
execution uses its isolated worktree. Later status notes here do not amend it.
User assigns new-method development to a separate task and asks this task to
improve existing methods toward a playable game quickly (D-058).
No generic batch platform, new primitive, new agent algorithm, or UI is needed.
Use the existing DSL4 parser/engine, random/terminal-only minimax and exact solver.
Plan19 is superseded here without implementation. Plan18 is accepted and closed.

The separate new-method task has begun a user-led planning dialogue, recorded in
[the discussion note](../../reviews/2026-09-05-game-generation-planning-dialogue-ja.md).
Those proposals do not amend this pilot's definitions, budget or execution gates.
Subsequent user clarification makes enjoyable skill development central and
exact50/50 optional for future new-system planning; asymmetry is a search-space
hypothesis. These preferences and proposed depth measures are recorded in that
note and the charter; this registered pilot's criteria and raw labels stay fixed.
The later separate dialogue focuses on a bounded obvious-win verifier followed
by the user's playtesting; its [draft](../../designs/bounded-obvious-win-screen-v0.md)
does not activate work or amend this pilot. Learning/transfer tests are not
requirements of that new verifier.

## Hypothesis and fixed definitions

Forward capture versus opposing forward push on4×4/5×5 can retain more useful
choices than the former six-ply conversion region while preserving no draws.
This is an openly designed development pilot, not an untouched confirmation or
a causal comparison of generator/evaluator improvements over earlier studies.

- A uses MOVE_CAPTURE with vectors (1,−1),(1,0),(1,1), goal REACH_EDGE/BOTTOM.
- B uses PUSH with vectors (−1,−1),(−1,0),(−1,1), goal REACH_EDGE/TOP.
- Only canonical owned piece types a/b, no pass, existing goal/immobility rules.
- Board n in(4,5), initial counts(A,B) in((2,3),(2,4),(3,4)): six carriers.
  A starts on row0, B on row n−1. For each role, rank columns by SHA256 of
  canonical ["plan0020",n,[a_count,b_count],role,column], with column tie-break;
  choose the first count columns. B starts in all six fixed definitions.
- No selection retries, backfill, result-conditioned setup changes or D4 game
  multiplication. Static builder tests may expose these definitions; disclose it.

## All-legal decisive-termination proof

Phi = sum_A(n−1−row) + 2 sum_B(row) is a nonnegative integer. An A step lowers
Phi by1; capture additionally removes a nonnegative B term. A B empty step
lowers it by2. A B push moves A backward one row (+1) and B forward (−2), net−1.
Every legal action therefore strictly decreases Phi. Set DSL max_plies=Phi0+1,
strictly beyond the natural bound Phi0, so PLY_LIMIT cannot be reached.
Existing goal/immobility semantics then yield one winner on every legal path.
Both edge goals can function in this mechanism, but their liveness in each
selected configuration and human fairness/interest are not thereby established.
Known risk: the pushed A can immediately capture the pusher; B may need extra
material to make the tempo sacrifice useful. Do not hide this potential dominance.

Before registration or production play, a direct proof (independently checked)
excluded all six A-first counterparts. Advance one A straight; after a push,
capture the pusher with the inverse vector, returning to the previous position.
Other A pieces stay on row0, so these actions never meet friendly blockers;
row0 pieces cannot be pushed outside the board. Delete each B-push/A-recapture
pair: the advancing A is unchanged and that B is gone. The remaining turns are
still A-first. A reaches BOTTOM in n−1 forward steps; a surviving B also needs
n−1 ordinary steps and cannot arrive first. B immobility only ends earlier.
This rejects A-first as trivially solved, not merely because a forced winner
exists. It does not prove the remaining B-first definitions good or unsolved.
The draft was narrowed from12 to6 before its first registration; no outcomes
were sampled to make this change.

## Bounded unchanged-algorithm measurements

For all6 definitions, execute ordered profiles (0,0),(2,2),(3,3),(3,2),(2,3),
each seed0..3:120 games. 0=random;2/3=existing terminal-only minimax depths.
Fresh agents per role/game,20,000 cumulative nodes per role/game. At most
3,840,000 charged search nodes across search-bearing profiles. Preserve legal
action prefixes, results, nodes, censors and elapsed time; each game prefix
gets one replay check. Do not reuse the old depth0/1/2-only adapter by changing it.

Then solve every base definition once at100,000 states:6 calls/600,000 states
maximum. Each successful exact record gets one external PV replay; the saved PV
is not a complete contingent strategy. Exact completion means TOO_EASILY_SOLVED
under D-057. Exhaustion is UNKNOWN, not hardness-pass or a reason to raise caps.
No repeat/resume, more seeds or solver retry. Algorithm/engine code stays fixed;
the depth profiles are measurement axes within this pilot, not an agent improvement claim.

Summarize every fixed-first/ordered-profile cell separately. A REVIEW_ONLY flag
may identify a fully completed schedule with both roles winning at equal depth2
and3 and an exact censor. It is neither fairness nor hardness/fun qualification.
Report actual candidate weaknesses even when no flag survives. No automatic
promotion, preference model, confidence claim from four seeds, or new method search.

## Implementation, evidence and acceptance

Only scripts/plan0020_candidates.py, scripts/plan0020_pilot.py and their new
focused tests belong to this task. Reuse existing atomic canonical publication,
agents, engine and solver; do not edit frozen older scripts/src/research/tests.
New calibration that executes gameplay uses only tiny3×3 artificial examples,
outside this production board domain. Test the termination inequality over all
reachable small calibration branches and runner failure/censor boundaries.

After focused tests and independent review, commit the completed registration
and code before production gameplay. The single runner requires that exact clean
commit. Exclusively create experiments/runs/plan0020-directional-race-v1; persist
attempt, canonical definitions/certificates and schedules before any play.
Pin tracked Python source/tests and this plan. Verify saved records by readback
and hashes; retain failure/partial prefixes and stop on unexpected exception,
source drift, draw or bound violation. Censors continue only the fixed schedule.
No new heavyweight inspect/reconstruction framework; a read-only saved-summary
audit must not call an engine, agent, solver or replay again.

Start exactly one full regression and the registered exploratory pilot from
the same reviewed committed bytes; results remain provisional until actual
Ran/OK and evidence/source checks. Keep those source/test bytes fixed during
execution. All previous suites are already complete; do not restart them.
No paid compute, publication, external participants or automatic usage reset.
Execute from a clean isolated worktree of the registered commit so concurrent
new-method documentation in the shared checkout cannot alter the tested bytes.
Preserve those unrelated files; do not stage them as experiment implementation.

## Preservation and completion

No Plan15 census, Plan13/14 membership access, or reopening prior runs.
MC/PUSH is outside the public old-six action-pair regions (including role swap),
and these4×4/5×5 definitions differ from Plan16/18's3×3 members. Do not claim a
global novelty census. Preserve historical pins, fixtures and raw labels.
Done: fixed attempt complete or explicitly failed, focused/full verification,
concise Japanese rules/findings and an honest next candidate decision. Keep
new-method development in the separate task; do not wait on it to run this pilot.

## Pre-execution checkpoint — 2026-09-05

The four narrow files are implemented. Root's combined focused suite passed
15 tests in0.914s, OK (session17889 exit0). All executed calibration was tiny3×3
or mocked;4×4/5×5 production was only exposed statically by builder tests.
Independent review checked the termination/A-first arguments and runner failure
accounting. The identified publication/adapter-exception denominator issue was
fixed: an executed failed attempt is not reported as unstarted or complete.
No production games, solver calls, or run directory have been created yet.
Registration is the subsequent commit containing this checkpoint and the four
reviewed Python files. Pass its full40-hex hash explicitly to the sole run.

## Execution status — 2026-09-05 21:53 JST

Registered commit637c9ae144be5353343234697120e631d1a64d4e is checked out clean at
/tmp/parity-forge-plan0020.q9qwHS/checkout. Both commands started21:52:57–59 JST.
Pilot: session99694, PID79224, /tmp/parity-forge-plan0020.q9qwHS/pilot.log.
Full suite: session80972, PID79233, /tmp/parity-forge-plan0020.q9qwHS/full-suite.log.
Both are running; no completion or acceptance claimed. Do not launch duplicates
or edit registered worktree source/tests/plan. Output is inside that worktree at
experiments/runs/plan0020-directional-race-v1. Audit saved records without a new
game/solve/replay after the pilot ends; preserve the immutable run in the shared
checkout. Keep the one full regression running until actual Ran/OK or failure.

## Pilot result and next action — 2026-09-05 22:05 JST

Pilot session99694 exited0. All120 games completed decisively, zero failure/
censor/unstarted;1,173 plies/117,427 nodes. Exact: two B_WIN completions
(20,123/91,487 states), four UNKNOWN at100,000 states. REVIEW_ONLY0; no game
qualified. The registered schedule is closed to extra gameplay/solve/replay.
Independent saved-only audit passed256 envelope hashes,166 Python+plan pins,
all schedules, replay-count records and30 summary cells. Completed raw output
was copied once to the shared checkout and all bytes compared equal.
See [Japanese findings](../../../experiments/reports/0020-directional-race-findings-ja.md).

A post-run direct proof also rejects index3: B's unobstructed left-side route
wins on total ply7. Its raw exact UNKNOWN remains unchanged; this separate
diagnosis used no additional engine, solver or replay execution. Other censored
definitions are not thereby proved bad; shallow AI results are role-sensitive.
Do not relax this run's flag threshold after outcomes or raise its budget.

Full suite80972/PID79233 remains running; actual Ran/OK is still pending.
Preserve the registered worktree until completion. Next: obtain the existing
suite's actual result and source checks, accept or investigate, then archive
this plan and register a small next candidate study. Prioritize simple-win/
undefended-route checks and interaction; use existing AI depth settings, not a
new platform. No new production schedule is activated by these intentions.

## Waiting-period preparation — 2026-09-05 22:38 JST

Full suite80972/PID79233 still runs (elapsed45:41), now at schema-v4 exhaustive
compiler tests; registered Python/plan bytes are unchanged. No final Ran/OK.
Do not duplicate or interrupt it. A source-only next-candidate proposal was
saved as [capture/hop full ranks](../../reviews/2026-09-05-capture-hop-next-candidate-ja.md),
with2 fixed-first5×5 DSL data definitions. Static parser/canonical/hash/potential
and public old-six-region checks passed. No candidate was played or solved,
no replay was called, no Python source/tests changed, and no new schedule was
registered. The short rules and all-legal termination argument are drafts;
independent pre-execution review is still pending. Finish Plan20 acceptance
before registering the next small pilot. Keep the separate new-method work out.

## Next-study preparation authority — 2026-09-05

User now explicitly requests continuation until a game is available. While this
suite stays immutable in its isolated worktree, prepare separate Plan21 files
using existing play/solve/publish functions. Only tiny3×3 calibration may execute
before the new registration; no production capture/hop play yet. No old source
or registered worktree changes. Plan21 code needs its own full regression.
A small local terminal interface may accompany a surviving trial candidate;
it is a way to play, not a new discovery platform or a quality certificate.

## Acceptance — 2026-09-05 23:21 JST

The original full suite finished1274 tests/5150.027s/OK(skipped=2), session80972
exit0, PID79233 gone. Independent log/source/raw-byte checks passed. See
[acceptance closeout](../../../experiments/reports/0020-acceptance-closeout-ja.md).
Do not restart any completed Plan20 execution. Plan21 becomes the sole active
plan, using separate registration and a new regression for its new code.
