> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan0030 — Admission-first four-structure preselection

## Status and dependency

COMPLETED / ACCEPTED / REGISTERED / PRESELECTION_COMPLETE / NO_SELECTION /
SAVED_ONLY_AUDITS_PASS / FULL_REGRESSION_PASS / HUMAN_REVIEW_FALSE.

Plan29 closed before registration because its third structural slot overlapped
the public old-six firewall, its attempted fourth definition drifted from the
contracted slot, and its own contract prohibited an in-Plan replacement. No
registered production game, exact solve, replay or selection query occurred.
Plan0030 is the next chronological research unit, not a retry number or new
version of a Plan29 result.

## One question and claim boundary

Can this Plan-specific admission-first, fixed four-structure cohort select at
most one structurally small no-draw DSL definition for a fresh-seed
existing-agent play screen, while rejecting bad drafts before expensive
computation?

This Plan ends at preselection. It cannot establish fairness, practical
hardness, depth, fun, learning value or human eligibility. UNKNOWN and a
100,001-state prefix are never positive quality evidence. Only a later Plan may
run a larger candidate play screen or ask the user to play.

## Bounded design stage

Rank and action/goal structures are fixed now:

1. `five-thread-hop-swap-connect-v0`, HOP/CONNECT_EDGES versus
   SWAP/CONNECT_EDGES, hash
   `a6de32c2b481614901caeabd2f2414815088a2b60992a3c4a55b7041aa2b7908`;
2. `five-thread-push-capture-triad-v0`, PUSH/CONNECT_EDGES versus
   MOVE_CAPTURE/ELIMINATE, hash
   `641c04d91572f4b748e927fe45490233a1ff71eb61cd5ab030a0e54c57bef4be`;
3. `five-thread-capture-swap-bridge-v0`, MOVE_CAPTURE/CONNECT_EDGES versus
   SWAP/REACH_EDGE, hash
   `247adb1bd139def5650fdfe0f8e0f9a78bc36147b08a505ab27e64d9fa8b03be`;
4. `full-rank-hop-capture-thread-v0`, HOP/CONNECT_EDGES versus
   MOVE_CAPTURE/REACH_EDGE, hash
   `5b5b5c4c88fcabe0017c8ecc2749a74c639ab6dd35a03cca8455106f416fca11`.

CELL-1 carries one exact definition from a never-registered, production-unexecuted
Plan29 draft forward unchanged. Its
unregistered source-led goal/effect, short-AND/OR and state-prefix observations
are disclosed development exposure, not Plan0030 evidence. Do not alter or
replace it. Plan0030 is therefore outcome-exposed development, not confirmation,
an unbiased comparison among candidates or evidence that one search method
improved over another. Draft rejection counts or elapsed speed cannot establish
that admission-first screening is generally better or more efficient.

CELL-1 passed a new Plan0030 primary lane and an independent audit. Its D-055
potential is40<cap41, `b=15`, `t<=20`, T3 is72,300, and its four fixed
goal/effect prefixes consumed96 transitions across the two lanes. Plan29
observations did not satisfy or replace these checks.

CELL-2 draft1 passed its bounded individual static lane and independent replay audit;
draft2 is permanently `NOT_INSPECTED_STATIC_GATE_PASSED`. Its potential starts
at52 and strictly decreases, so every legal play ends before cap53. Both GOAL
prefixes and actual PUSH/capture were replayed from the initial state without an
earlier terminal. `b=15`, `t<=26` and the per-role T3 bound is93,990. No game,
exact, selection AND/OR or state-prefix enumeration was used.
CELL-3 draft1 `five-thread-capture-swap-bridge-v0`, hash
`247adb1bd139def5650fdfe0f8e0f9a78bc36147b08a505ab27e64d9fa8b03be`,
and CELL-4 draft1 `full-rank-hop-capture-thread-v0`, hash
`5b5b5c4c88fcabe0017c8ecc2749a74c639ab6dd35a03cca8455106f416fca11`,
also passed their primary and independent lanes. Each has potential40<cap41,
`b=15`, `t<=20` and T3 bound72,300. Their saved goal/effect prefixes consumed
54 and64 transitions respectively across both lanes. Their second drafts are
permanently uninspected. Four-way structural comparison and aggregate resource
arithmetic passed an independent read-only audit, so final cohort admission is
complete.

For each of CELL-2..4, allow at most two explicitly named source drafts, in
order. Fail fast in the fixed sequence: canonical parse/hash; public old-six
predicate; algebraic D-055 proof fixing `L_d`; direct replay of hand-authored
goal/effect prefixes; then static resource arithmetic. A draft may undergo only
these checks. Do not play a game, call
the exact solver, run selection AND/OR or enumerate a state prefix during this
design stage. Stop at the first statically admitted draft per slot; do not inspect
the second. If both drafts fail, close Plan0030 without filling that slot.

Before creating a draft, freeze its board size, first player, pieces, vectors,
goal targets and potential form. A failed first draft may inform the second only
through the stated static failure; disclose the dependency. This caps the entire
design stage at seven definitions including CELL-1 and prevents an open-ended
model/design loop.

Each draft may contain at most four named hand-authored prefixes. Replay each
prefix once in the primary check and at most once in an independent audit lane;
an illegal prefix in either lane rejects that draft immediately, with no
corrected same-draft prefix or replay in either lane. Save every attempted draft, canonical hash and both static/
replay results. With `L_d` defined as that draft's proved maximum natural ply
count, the design stage permits at most56 prefix replays and
`8*sum(L_d)` replayed transitions, separate from all production limits below.
Reject any serialized prefix longer than `L_d` before calling the engine, so a
malformed witness cannot exceed the transition ceiling.
DSL schema4 caps `max_plies` at1,000 and admission requires `L_d<max_plies`.
Thus the general seven-draft ceiling was55,944 transitions, and the known
CELL-1 `L=40` tightened this Plan's before-drafting ceiling to48,272. Only four
drafts were attempted: their `8*sum(L_d)` ceiling is1,376, while22 actual
primary/audit prefix replays consumed exactly280 transitions.

## Static admission

Every final cell must have one exact canonical JSON/hash and pass independently:

- public old-six exclusion in both role orders and structural distinction from
  the other three final cells and Plans20–28, plus Plan29's other three drafts;
  the explicitly inherited CELL-1 is exempt only from comparison with its own
  unchanged Plan29 copy;
- a nonterminal fixed initial state with a legal first action;
- a nonnegative integer potential that strictly decreases on every legal action,
  with its initial value strictly below `max_plies`, proving all legal play ends
  finitely with exactly one A/B winner;
- from the fixed initial state, an alternating-turn complete legal prefix for
  each role's explicit GOAL and each special action effect, with no earlier
  terminal state;
- maximum branching `b`, decisions per role `t`, and
  `t*(b+b^2+b^3) <= 100000` for the unchanged T3 accounting;
- exact ceilings for the schedule, short-search misses, T2/T3 node proxies,
  exact states, actual game plies, BFS transitions, adapter-internal replay
  transitions, memory, files and publication bytes. These are named deterministic
  proxies, not a claim to count every internal `apply_action` call.

Zero sampled draws, PLY_LIMIT behavior or capped search cannot replace the
all-legal D-055 proof. A source proof or witness defect rejects only that design
draft before cohort freeze; no production evidence exists at this stage.

## Cohort freeze and minimal implementation

All four cells passed static admission. The immutable design record is
`experiments/proposals/plan0030-design-drafts-v0.json`; the fixed prospective
cohort is `experiments/proposals/plan0030-four-structure-preselection-v0.json`.
It lists all definitions, hashes, rank, thresholds, policy/stage order, unique
seeds and exposure; its independently verified SHA256 is
`d547bc5dee706f2a5480f4f2e8c7ac021e8ba2eec9abbda6fbac2a0ab48fcd15`.
From this freeze until closeout, no definition, rank, seed, cap or threshold
changes and no backfill are allowed.

Add only `scripts/plan0030_preselection.py` and
`tests/test_plan0030_preselection.py`. The test must use static checks, mocks or
mechanically separate tiny fixtures and must not play, solve, replay or enumerate
the four production definitions. Do not edit `src/`, DSL, engine, solver, agents
or accepted adapters.

Pin and reuse accepted `scripts.plan0024_play.play_one` for T2/T3 games and its
one internal completed-prefix replay, `scripts.plan0020_pilot.exact_one` for
exact plus its one internal COMPLETE-PV replay, the accepted canonical publisher,
and `TerminalOnlyMinimaxAgent` for bounded queries. Each design-stage prefix lane
uses exactly one stepwise `action_from_dict` + `legal_actions` + `apply_action`
chain, constructing and checking every intermediate state and authoritative
action tuple in lane-local memory. The durable design record stores the complete
input action list, lane count and terminal/effect summary rather than duplicating
every derived state and legal tuple. This clarifies the evidence format and does
not authorize a third replay. Do not also call `replay_dicts` or add another
game-prefix or exact-PV replay. Implement only the Plan-specific manifest/cascade and a FIFO BFS that
counts the initial state as state1, uses exact `GameState` identity, asserts the
canonical engine action tuple, stores no edges and stops immediately after adding
state100,001. Its result contains unique64-hex state digests and one rolling
transition digest, without copying the large list into the summary. Freeze exact
hashes for `plan0024_play.play_one`, `plan0020_pilot.exact_one/_publish/_utc`,
`TerminalOnlyMinimaxAgent`, engine and DSL at registration. Plan28's adapter and
screen are not imported dependencies. The authoritative source snapshot pins all
tracked Python, including transitive Plan16 publisher, solver, play and agent
dependencies; the manifest additionally names every directly reused entry point.

### Preregistration implementation evidence

The Plan-specific runner and test are now frozen. Their preregistration SHA256
values are respectively
`1c77d335c97b683f32ed52c47977b1af408031a70157b94ec1017054dc31d127` and
`8c1df20038c129173a7cca39796269681cb0723917ee44c42f3b5aed69f67a32`.
The34 Plan0030 tests pass, including a mechanically separate tiny fixture using
the accepted Plan20 exact and Plan24 play adapters. A combined65-test run with
the relevant accepted dependency suites also passes; `py_compile` and
`git diff --check` pass.

Two independent read-only reviews pass with no remaining registration blocker.
They checked the A-root B-force rule, strict integer versus boolean evidence,
nonzero decisive exact PVs, draw/PLY_LIMIT/winnerless BFS rejection, complete
56-slot closure, saved-only gate/resource/summary reconstruction, source and
manifest pins, publication hashes and byte/file ceilings. Synthetic fault tests
cover pre- and post-write exceptions at bootstrap, attempt/result, failure,
source-verification, summary and fallback publication; an exception before the
run timestamp leaves no immutable output, while a later one-shot fault closes
without repeating any game/search/solve/BFS call. Exception text is bounded by
UTF-8 bytes and retains original length and SHA256 when truncated. A persistent
storage fault that also defeats the one in-process evidence-write recovery can
only end with a nonzero CLI exception and incomplete artifacts; it never
authorizes rerunning production computation.

These tests and reviews used only mocks, static checks and the separate tiny
fixture. None played, solved, replayed or BFS-enumerated any of the four frozen
production definitions. Production count remains zero.

## Prospective fixed cascade

The proposal freezes unique RNG/game seeds before registration: short-four
`30001..30008`; CELL-1 games `30100..30103` then `30110..30113`; CELL-2
`30200..30203` then `30210..30213`; CELL-3 `30300..30303` then
`30310..30313`; CELL-4 `30400..30403` then `30410..30413`; and short-seven
`30501..30508`. Policy order is T2/T2 then T3/T3. Execute once, in rank order
and with stage barriers:

1. For each cell/target, query the first four target decisions, ply7/8 for the
   first/second player, with a fresh terminal-search agent and100,000 misses per
   target. A force is `NOT_SELECTED_SHORT_FORCED_WIN`; cap exhaustion is
   `NOT_SELECTED_EVIDENCE_INCOMPLETE`. Freeze one RNG seed per target query,
   pass the initial canonical `legal_actions` tuple unchanged, and after normal
   return derive the root value from all `last_action_values`. The fixed root
   actor is A, so use `max(values)` for both target queries: A force requires+1
   and B force requires-1, meaning every legal A root action has value-1. Never
   use `min(values)` for the B query; that would show only one losing A choice.
2. Each survivor plays separate T2/T2 and T3/T3 four-game cells. Each must be
   4/4 decisive with A wins1..3. Across the eight games, at least four must end
   by GOAL, including at least one A GOAL and one B GOAL. These are functional-
   goal and shallow-policy screens, not fairness evidence. A fixed gate miss is
   `NOT_SELECTED_POLICY_GATE`. A game censor contradicts the static T3 bound and
   is `FAILED_TECHNICAL`, stopping the whole Plan. Once this stage opens for a
   cell, call `play_one(..., max_nodes=100000)`, meaning100,000 cumulative nodes
   per searched role per game, and finish both four-game cells despite an
   ordinary numerical miss.
3. Each survivor receives one existing exact call at100,000 states. COMPLETE is
   replayed exactly once inside `exact_one`; require replay_count1 and never add
   another replay. If its value is decisive, terminal reason is GOAL or
   NO_LEGAL_ACTION and PV length is at most `L_i`, close it as
   `NOT_SELECTED_TOO_EASILY_SOLVED`. The accepted raw cap wire is
   `status=UNKNOWN_CENSORED`, `actual_result=null`, counters under `error` and
   replay_count0; keep Plan-level UNKNOWN terminology distinct. COMPLETE
   draw/winnerless/PLY_LIMIT or an
   overlong PV contradicts D-055 and is `FAILED_TECHNICAL`. UNKNOWN must report
   exactly100,000 searched/max states and replay0; otherwise it also fails
   technically. A valid UNKNOWN merely opens the next stage.
4. Enumerate the deterministic100,001-state canonical prefix. If it exhausts at
   or below100,000 after exact reported UNKNOWN on the same state model, classify
   the contradiction as `FAILED_TECHNICAL`, not a small-game result. Require the
   same definition hash and source pins as exact. Identity is the full
   `(ply,to_move,pieces,outcome)` `GameState`; terminal states count toward seen
   and digests but are never expanded.
5. For each survivor/target, query its first seven decisions, ply13/14 for the
   first/second player, at100,000 misses. Only COMPLETE false for both survives;
   force and cap labels match stage1.

Materialize the complete potential56-attempt schedule before computation, in
fixed stage, cell-rank and target order. At short-query stages, stop the second
target query for a cell after the first closes it by proved force or cap
exhaustion, and publish it as `NOT_STARTED_GATE_CLOSED`; later stage barriers
use the same label. After a technical failure, every remaining slot is instead
`NOT_STARTED_FAILURE`.

If multiple definitions survive, preselect only the lowest fixed rank and label
it `PRESELECTED_TECHNICAL_ACCEPTANCE_PENDING`; label all later survivors
`NOT_SELECTED_FIXED_RANK`. Never rerank from wins, nodes, width or wall time.
The production runner must not emit `SELECTED_FOR_PLAN0031`: that promotion is
allowed only after the separately launched full regression and saved/source
audit both pass.

## Fixed ceiling template and failure policy

At most56 attempts exist: eight short-four queries,32 games, four exact calls,
four BFS prefixes and eight short-seven queries. These are maximum schedule
slots; publish one immutable attempt and one result or gate-closure record for
every slot. The conservative publication
ceiling is118 immutable run-artifact files: attempt/result pairs plus six
named global/failure paths: run-attempt, manifest, source-verification, failure,
summary and summary-publication-failure. Before registration, cap each of four BFS result
envelopes at8MiB and each other complete publisher envelope at2MiB, checked
before `_publish`, for at most272,629,760 published bytes. The summary must not
copy a BFS digest list. Also instantiate, with `L_i` meaning cell `i`'s proved
maximum natural ply count (its initial potential bound):

- BFS transitions `<= 100001 * sum(b_i) = 6,000,060`;
- internal production replay transitions `<= 9 * sum(M_i) = 1,584`, with `M_i` equal to
  cell `i`'s `max_plies`, covering eight completed or failed game-prefix replays
  per cell plus at most one exact PV replay per cell;
- actual production-game plies `<= 8 * sum(M_i) = 1,408`;
- short-query misses `<=1,600,000`, exact searched states `<=400,000`, and
  configured game-agent nodes `<=6,400,000`, with tighter structural T3 totals
  instantiated from the four final `b_i,t_i` values;
- sequential memory proxy, one cell at a time: each of unique GameStates, queue
  references and state digests is `<=100001`, with zero stored graph edges;
- candidate-specific T3 per-role values are72,300,93,990,72,300,72,300.
  The actual T2 schedule structural bound is165,120, the T3 schedule bound is
  2,487,120, and their combined bound is2,652,240. Treating every game-role
  call as T3 gives a separate conservative4,974,240 bound. Here
  `sum(b_i)=60`, `sum(L_i)=172`, `sum(M_i)=176`, and
  `sum(T3_i)=310,890`.

Use a durable main-workspace log destination for the one full regression, capped
separately at16MiB with a saved SHA256; do not put the only log in the isolated
`/tmp` worktree. It is outside the118 run-artifact count. Wall seconds and RSS
remain descriptive. Any exception, draw, PLY_LIMIT, proof violation, invalid replay,
source/hash/publication drift or impossible censor is `FAILED_TECHNICAL` and
stops the Plan. No retry, resume, replacement, seed substitution, threshold
relaxation, cap/depth increase or extra attempt.

## Registration, acceptance and closeout

Independent definition/proof/protocol review and focused tests must pass before
one clean registration at production count zero. Launch exactly one registered
preselection and one registered full regression. Saved/source audit must match
the manifest, pins, schedule, transition/resource bounds and every published
hash without new game/solver/replay calls.

Technical acceptance requires the full suite's actual final `Ran`, `OK` and
exit0. An interruption fails acceptance and is not retried. Scientific
selection and technical acceptance are orthogonal labels. If zero candidates
survive, close with `NO_SELECTION`. Only if at least one candidate survives and
technical acceptance passes may the lowest fixed-rank survivor move unchanged to
a separately registered Plan0031 with fresh seeds. In every other case Plan0031
does not open as that unchanged-survivor continuation. This does not reserve a
permanent gap: if research continues after a no-selection closeout, the next
unused chronological research unit is an independently scoped Plan0031, not a
retry, supplement, promotion or reclassification of Plan0030. Plan0030 itself
never authorizes human play.

### Registered execution and closeout

Registration commit is
`27b5138fe3dddc22c4e1c24d261746f036174598`; both detached worktrees re-read
clean with the frozen runner/test hashes. The first shell form at00:28:39 JST on
2026-09-08 failed at module import before `main`, `run_pilot`, proposal load or
output reservation. Its257-byte log SHA256 is
`76b12b9e58521d36fb296b6cbfc9e85b6ceea9169dfb7e29eea35e6cbfa25e10`.
Two independent reviews classify this as the same non-production launcher
preflight shape already recorded for Plan27: all production call counts were0.

The first and only production invocation then started through the correct module
entry at00:31:05.688764 JST and completed at00:34:02 JST with exit0. It saved
56 records in116 files/161,182 bytes. Five short queries ran: CELL-1 A7,
CELL-2 B8, CELL-3 A7 and CELL-4 A7 each censored at100,000 misses; CELL-2 A7
completed at95,704 misses with root value0 and no forced win. The other51 slots
are `NOT_STARTED_GATE_CLOSED`. Thus all four cells are
`NOT_SELECTED_EVIDENCE_INCOMPLETE`, final disposition is `NO_SELECTION`, and
game/exact/replay/BFS counts are all0. UNKNOWN is only non-certification under
the fixed cap; it is not evidence of balance, depth, unfairness or poor play.

Root and two independent saved-only audits pass without production calls:
193 source pins,16 direct entry points,114 publication hashes, schedule,
envelopes, gates, resource totals and limits all match. Short misses total495,704
with no resource violation. Summary SHA256 is
`8ebbd7d298ef437a2a3a24b90eb125e3930e22c79548f54cafd211dafd9c01b3`.
The single full regression session50297/PID19792 started at00:28:39 JST in
`/tmp/parity-forge-plan0030-regression.rhcvdY/checkout` and finished exit0:
1,403 tests in5,398.474s, `OK (skipped=2)`. Its durable main-workspace log is
163,602 bytes with SHA256
`482a027b9db48e9605fc79c6cb5829275669cc9b88208142d0a73b9fb1d885bd`.
PID19792 is gone, the registered worktree is clean at tree
`c3425bfe4bc76e9fa570b5ff1950bfcd3fb564b2`, all34 Plan30 tests pass in the
log, and FAIL/ERROR count is0. Plan30 is technically accepted while its
scientific result remains `NO_SELECTION`; never restart or supplement either
execution. See
[technical closeout](../../../experiments/reports/0030-acceptance-closeout-ja.md).

## Activation checklist

- [x] Plan29 closed at design-stage static failure with production count zero.
- [x] CELL-1 frozen unchanged and three new non-old-six structural slots ranked.
- [x] CELL-1..4 admitted under Plan0030 evidence limits; all primary and
  independent prefix lanes PASS, and CELL-2..4 draft2 are closed uninspected.
- [x] Four hashes, proofs, witnesses, seeds, policy order and all exact resource
  totals frozen in the prospective proposal; final freeze audit PASS.
- [x] Plan-specific script/test implemented;34 focused and65 combined dependency
  tests, two independent implementation audits, `py_compile` and diff check PASS.
- [x] Register from production count zero; complete the single preselection and
  launch the single full regression with a durable main-workspace log.
- [x] Root and two independent saved/source audits PASS; Japanese preselection
  findings saved with `NO_SELECTION` and human-review false.
- [x] Record the full regression's actual `Ran`/`OK`/exit and log SHA256; close
  technical acceptance without retry.
- [x] Archive Plan0030. Continuing research uses the next independent
  chronological Plan0031, never a Plan30 retry or promotion.
