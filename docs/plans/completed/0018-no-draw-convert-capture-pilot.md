> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan 0018 — No-draw-certified conversion/capture pilot

## Status and question

COMPLETED / ACCEPTED as computation and evidence, not as a qualified game.
The original preregistration is preserved at `d1364e81b`. User says 「進めて」
after confirming D-055. Plans 0016/0017 have passed their shared 1,219-test
regression; the separate acceptance report preserves their raw provisional bytes.

Can a small, structurally decisive conversion-versus-capture region retain
meaningful shallow-policy choices? This is exploratory generator restriction,
not a comparison claiming improvement over the outcome-informed previous pilot.
Keep the existing DSL4, 3×3/18 compiler, static predicates, seven primitives,
three goals, symmetric vector profiles, engine and agents unchanged. No placement
role, new primitive, arbitrary timeout winner, cycle analysis or huge census.

The new product gate is proved before membership/gameplay. Restrict the new
generator to one CONVERT role and one MOVE_CAPTURE role. Do not change old gates
or reinterpret an old DRAW as a win. Exact forced winner is not a rejection by
itself. This region is known to be very short: current compiler initial counts
are at most three per side, so its universal natural length bound is six plies.
This is a deliberately small test, not a claim of deep or human-fair games.

## Structural certificate — all legal play, not minimax

Call the converter C and the capturer N, independent of A/B labels. Use the
strict public wire normalizer and then require schema4, board3, cap18, precisely
these two action kinds, different owned action piece kinds, all initial pieces
of their owner's action kind, positive initial counts, spatial goals on the
owner's kind and ELIMINATE on the other's kind. Candidate static eligibility is
a separate unchanged requirement. Reject inputs outside this proof's scope.

Let m be N's initial total piece count. Each legal C action changes exactly one
N piece into a C piece. Each N action moves an N piece and may remove C, but
cannot add an N piece. Consequently C can act at most m times. Alternation
and lack of pass give at most 2m−1 plies with C first, or 2m with N first.
After the final N piece is converted, N has no action; earlier goals or
immobility only shorten play. If C loses all pieces, its immobility also ends
play early. Initial/actor goal priority is the existing engine's unique-winner
rule, not a newly assigned tie breaker.

Require the computed bound STRICTLY BELOW 18 because the engine checks the
ply cap before post-action immobility. Positive counts plus 3×3 imply at most
16 plies even for the wider certificate envelope; compiler-selected m≤3 gives
at most six. Thus no legal path reaches PLY_LIMIT; every path is finite with
one A/B winner. Store both first-player certificates with definition hashes.
Zero counts, other action pairs or unsupported wires fail closed, not UNKNOWN
or proof-pass. A production draw/bound violation is a proof-integrity failure,
not a candidate's ordinary draw-rate observation.

## Fixed selection and history boundary

Input: the already saved Plan-0015 compact report, 17,284,867 bytes, SHA-256
`fa7daf48992f2b186fd980d42f670beda651b1adc7fe4c1fb62b67d1fdc05f97`.
Authenticate and reconstruct it once for this new selection. Never call the
census builder. Authenticate the Plan-0016 manifest, raw SHA-256
`3c54f7b753ce56d2d6fc28e77c6d8eddc0a5ebd8df11d151bc15a6068cb6814b`;
read its definitions only, not its outcomes, to exclude all 46 earlier members.

The ordered goal pair is (C goal, N goal). Use CONNECT_EDGES, ELIMINATE,
REACH_EDGE in lexicographic order, except ELIMINATE/ELIMINATE, which lies in
the public old-six semantic exclusion. This yields eight pairs × two slots =
16-carrier ceiling. All slots require CONTACT: a legal initial conversion
requires vector contact, so SEPARATED cannot pass the unchanged initial gates.
Record this known absence rather than allocating futile separated slots.

Pre-membership source deduction (before opening/reconstructing the production
report for this plan): with C first, C's count is at least its positive initial
count after each complete pair of turns (+1 by conversion, at most−1 by capture),
so N cannot achieve ELIMINATE. Its two goal pairs are also unreachable in the
existing count-lattice gate. After the first conversion N has at most two pieces
and cannot CONNECT across a3×3 board from a nonterminal initial state. However,
the frozen optimistic gate can use a ply0 count witness when initial N=3 without
requiring an actually connected initial board. Do NOT equate this latter
rule-level impossibility with STATIC_ZERO in the saved report. Preserve the
fixed eight-pair schedule and separate the goal-unreachability deduction from
both actual static support and game outcomes. N might still win by C immobility;
an unreachable stated goal is a distinct simplicity/validity diagnostic.
Do not silently fix the frozen gate, change material, or backfill a slot.

For each goal-pair/slot, hash-rank saved positive-contact skeletons using new
Plan-0018 domains and exact canonical UTF-8 tie bytes frozen in reviewed code.
Cycle ranked skeletons; within each skeleton cycle its sorted positive-contact
initial count pairs. Deterministically rank nine cells using goal pair, slot,
attempt, skeleton hash and cell; canonicalize under that skeleton's stabilizer.
At most 64 attempts per slot. Require unchanged static eligibility, contact,
the no-draw certificates and no exact/D4/global-alpha-role duplicate against
the prior 46 definitions or any accepted member here. Preserve every rejection,
duplicate and vacancy; no backfill, budget increase or outcome-based reranking.

Retain all 109 original class coverage records, distinguishing OUT_OF_SCOPE,
in-scope static zero, assigned and represented; preserve contact supply and
attempt reasons. This is not full-grammar gameplay coverage. Keep all six old
semantic regions/role exchanges excluded without opening Plan13/14 members.
The prior history boundary plus source fixtures (horizons1–4) remains disclosed;
do not claim an exhaustive later exposure cutoff or untouched confirmation.
Plan17's member is already contained in the prior46 exclusion.
All new calibration definitions actually traversed by an engine/policy/solver
must be mechanically separated from production membership. Use the excluded
CONVERT/ELIMINATE versus MOVE_CAPTURE/ELIMINATE semantic region for new cap18
gameplay or all-legal-branch oracles; test its semantic-firewall membership.
Other nonexecuted selector fixtures are disclosed static exposure only.

## Immutable execution and fixed work

Only new scripts/tests may be added; no frozen source edits. Reuse accepted
Plan0016 play_one/summarize_games and atomic canonical persistence helpers,
not its selector, protocol-specific manifest, runner or triage. New code must
have focused synthetic tests and independent review before committing this
plan and the implementation. Never generate/play production members in tests.

Protocol/output: `plan0018-no-draw-convert-capture-v1` under experiments/runs/.
Exclusively create it and persist attempt metadata BEFORE selection: UTC,
host/Python, clean Git commit, all tracked source/test hashes, plan hash and
input hashes. Any existing directory blocks repeat/resume, even after failure.
Save the entire selected DSL set, certificates and both schedules before play.
Verify source/input bytes after selection and after execution.

Gameplay schedule is carrier order → A-first/B-first → existing eight D4
orientations → seeds0,1 → ordered profiles (0,0),(1,1),(2,2),(2,1),(1,2),
where 0=random and 1/2=existing terminal-only minimax depths. Fresh agents per
role/game, shared per-game seeded RNG; cumulative 5,000 nodes per role/game.
At most 2,560 games, 20,480,000 charged search nodes (four search-bearing
profiles × both roles as a conservative bound), and 15,360 played plies for
compiler members. Keep fixed-first/ordered-profile/orientation cells separate.
Persist each game's observed actions, decision counts, node/censor metadata
and replay verification. Do not treat orientations/seeds as independent people.

After the fixed gameplay schedule finishes (search-censored games allowed),
solve EVERY selected base definition, carrier order then A-first/B-first, once
at max_states=100000 using unchanged public solve_game, never the legacy CLI.
At most 32 exact calls /3,200,000 searched states. Persist an exact attempt
before each call; retain unmodified result.to_dict, timing and exactly one
external legal PV replay on success. The cap is operational, not a guarantee
that every search will complete. SolveBudgetExceeded = UNKNOWN/CENSORED;
do not raise caps or repeat. Exact DRAW contradicts the certificate and stops
the run as PROOF_INTEGRITY_FAILURE. A decisive exact value is neither a no-draw
proof nor, alone, proof of unfairness. A selected equal-value PV is not a
shortest forced strategy or a complete contingent strategy.

Unexpected exception/source drift/bound violation preserves the prefix and
failure record and stops all remaining work. Search budget censors retain
prefixes and continue the fixed schedule; unstarted slots remain explicit.
One read-only inspect may reconstruct schedule/certificates/summaries and replay
saved gameplay prefixes once, but must not call selector, policy or solver or
reopen a run. Exact records are checked against their persisted external replay
result without another exact-PV replay; the total remains one per successful call.

## Interpretation, review and acceptance

Report all results including zero supply/censors/failures. A FURTHER_DIAGNOSIS
flag requires a complete 80-game first-player condition, A and B each winning
at least once at both equal-depth1 and equal-depth2, and its completed decisive
exact label. This is only a shallow-policy sensitivity diagnostic: no fairness,
human-skill, depth or fun qualification. Do not manufacture a positive result
if none survives. Do not rescue individual definitions by changing goals/setup.

After focused tests and review, start exactly one new full regression and this
registered exploratory run from the same clean committed source. Provisional
parallel execution is permitted; source/tests stay unchanged until the suite
ends. Docs and separate result commits may change. Acceptance requires actual
full-suite Ran/OK, a source-match record and read-only evidence inspection.
No duplicate suite or automatic resource increase. Paid/external work remains
unauthorized. Finish the fixed study, then select a separate next question;
the proved directional MOVE_CAPTURE/PUSH weighted-distance option is deferred,
not automatic follow-up work inside this plan.

## Checklist

- [x] Independent structural proof and complete-plan review, no unresolved P0–P2.
- [x] Minimal selector/certificate and runner plus focused synthetic tests pass.
- [x] This registration commit freezes reviewed plan/code before membership;
  execution must verify the commit succeeded and the repository is clean.
- [x] One attempt/manifest/gameplay/exact sequence, or explicit preserved failure.
- [x] Read-only inspection, source checks and concise Japanese report.
- [x] One full regression passes; separate formal acceptance recorded.

## Pre-execution review checkpoint

Root's combined focused command passed40 tests in15.444 seconds:
`PYTHONPATH=src python3 -m unittest tests.test_plan0018_selection tests.test_plan0018_pilot -v`.
Independent source reviews found and closed partial-selection preservation,
post-selection/pre-manifest failure preservation, accurate global Git-clean
provenance, and immediate exact-record validation before the next call.
These repairs changed neither the selection order nor the fixed schedules.
All actual calibration play/solver calls remain in excluded E/E semantics.
Source checks confirm no frozen src/research, prior scripts/tests, old runs or
Plan16 archive change. No production selection/solve/game has occurred yet.

## Execution checkpoint — 2026-09-05 10:33:03 UTC

One run, session24296 exit0, at source `d1364e81b`: 12carriers/24definitions,
1,920games COMPLETE, zero draw/censor/failure/unstarted. Static31 attempts:
12accepted/19rejected, four STATIC_ZERO slots, no replacements. All109 classes
remain accounted for (8in scope/101outside). Exact24 COMPLETE: A_WIN7/B_WIN17,
850states, zeroDRAW/censor. Total play3,695plies /11,853charged search nodes.
Each exact success has its one external PV replay. The one registered inspection
(session14150 exit0) reconstructed all schedules/certificates/summaries and
replayed only the saved gameplay, with no selector/solver/exact-PV repeat.
Input/source checks matched. Raw provisional records remain immutable.

Four shallow diagnostic flags are carrier1/A-first,B-first and carrier4/A-first,
B-first. Both carriers' B/CONNECT goal is in fact unreachable for either first
player: with A first B immediately drops from3 to2; with B first it cannot align
its three pieces in the first move because either remaining pair has different
columns (carrier1 vertical goal) or rows (carrier4 horizontal goal), then A's
conversion leaves at most2. If A is stuck, the game already ends. Root and an
independent reviewer checked this directly from saved DSLs without new play.
This is a dead-goal-rule diagnosis, not rejection merely because exact saysB_WIN.
The raw flags are preserved; no game is qualified. Further sampling of this
short region is not authorized inside this plan.

Japanese report: `experiments/reports/0018-no-draw-game-findings-ja.md`.
Manifest SHA `a16c4ca84d8bc1bf88e528218b6ec5e622c68e73146a49c230931e8d0f943c64`;
summary SHA `8f1b1028031fed19c7ffc60222b766aeedd0e425533ca7b0c1e3093c5481ba62`.

Only the shared acceptance closeout remains: full regression session44075,
PID64445, started19:32:38 JST, log
`/tmp/parity-forge-plan0018.JxQbr8/full-suite.log`, source `d1364e81b`.
Do not start another full suite, pilot, exact call or replay. Keep all source/tests
unchanged until actual Ran/OK. Docs and separate evidence commits may change.
After acceptance, separately register the next finite-decisive region; no paid
resources, new primitive or production follow-up is authorized by this closeout.

## Strategic-review checkpoint — 2026-09-05 20:18 JST

The user requested reflection on how and whether the project should continue
while testing. See [the advisory review](../../reviews/2026-09-05-continuation-review-ja.md)
before selecting the next plan. It recommends bounded diagnostic calibration
and a few constructive rule families, not automatic expansion of this schedule.
It changes no registered definitions, outcome labels, acceptance gate or mission.
Current source/scripts/tests still match d1364e81b; session44075/PID64445 is
running without a final Ran/OK. No second suite, new game/solve/replay was started
for this review. Only documentation changed; formal acceptance remains pending.

## User clarification checkpoint — 2026-09-05 20:41 JST

D-057 records the user's token-bounded verification architecture and requirement
for simple rules that resist easy complete AI analysis. They endorse the short
calibration/design/playtest direction. Plan18's24 already solved conditions
(850 total states) do not establish this complexity. No raw result is relabeled.
The next study needs a defined solving target, calibrated finite allowances and
a bounded LLM-free batch path; exhaustion remains UNKNOWN, never hardness-pass.
The existing full suite remains active (session44075/PID64445), no final Ran/OK.
No source/test change, new experiment or duplicate test run occurs in this
documentation checkpoint. Formal acceptance of this plan remains the next action.

Human-attention checkpoint: the user asks what they should consider. No technical
decision or clarification of D-055/D-057 is needed. Optional replay-desire taste
input may guide later design; it does not block acceptance or activate new work.

## Acceptance closeout — 2026-09-05

The full regression ended:1,259 tests/5,171.636s/OK(skipped=2), session44075
exit0, PID64445 gone. Independent read-only confirmation found no failure,
tracked source drift from d1364e81b or raw-run drift from ebaeb054a.
See experiments/reports/0018-acceptance-closeout-ja.md for the log hash.
No additional game/solve/replay/inspect was performed. This final checkpoint
supersedes earlier pending-status observations without changing raw evidence.
User's replay-desire preference is saved in HUMAN_PLAYTESTING.md; simple rules
and depth are sufficient to guide the next search, with no new taste gate.
