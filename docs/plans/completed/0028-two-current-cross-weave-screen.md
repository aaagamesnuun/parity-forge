> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan0028 — Two-current cross-weave existing-agent screen

## Status and dependency

COMPLETED / REGISTERED / PILOT_COMPLETE / BASE_GATE_CLOSED / GAME_NO_FLAG /
TECHNICAL_ACCEPTANCE_FAILED / FULL_REGRESSION_INTERRUPTED_BY_HOST_REBOOT.
Registered at `b0d9b4b7840833ecbe564cbf81eba7ed4ad79a9e`. The one pilot
completed without technical failure; exact was UNKNOWN100000 and all32 base
games were decisive, but T3/T3 missed its A-win lower gate by one and explicit
GOAL wins were A0/B1. Final48 are gate-closed. Do not rerun, supplement or rescue
this wire. The exactly one registered full regression was interrupted by a host
reboot before a final summary or exit code was saved. The preregistered no-retry
rule makes technical acceptance fail; do not infer a test assertion failure.

## One fixed question and candidate

Can one mechanically asymmetric connection game with mandatory directional
progress, frequent HOP/PUSH contact and no placement action survive a bounded
existing-agent screen closely enough to merit the user's own playtest?

Use only
`experiments/proposals/two-current-cross-weave-v0.json` definitions[0]. Its
definition hash is
`c84f8cf6c01adb1e13f0668dd97cfc75112f63c4e5b0dbae89a22ea8e6e3100a` and
the prospective proposal SHA256 is
`eb4adfdab51b5441fae5c72af9d548884537665e74f978249d07a0866bc9582a`.
It is5×5/A-first/5v5: A HOPs right/right-down and connects TOP–BOTTOM; B
PUSHes up/up-left and connects LEFT–RIGHT. The complete Japanese source review
is `docs/reviews/2026-09-06-two-current-cross-weave-ja.md`.

## Fixed admissibility and claim boundary

Require exact proposal keys/status/exposure, canonical parser roundtrip and hash.
Initial goals are false and mobility is A8/B7. Fixed engine lines establish both
GOALs and actual HOP/PUSH. Public old-six exclusion is false in both role orders.

`Phi=sum_A(4-column)+2*sum_B(row)` starts50 and decreases by1 or2 on every
legal action, so every play is decisive by50<cap51. Each role has at most10
actions; depth3 costs at most1110 nodes/decision and27750 nodes/role/game.
Apply the existing schema-v4 terminal order unchanged: the actor's goal, then
the opponent's goal, then no-action loss. An exact UNKNOWN must save replay0.
Authoritative bounded AND/OR completes false for A13 at44704 misses and B14 at
30661. An authoritative reachable-state prefix contains100001 distinct states by
ply8. These facts prove only their stated finite scopes. Exact UNKNOWN, large
state count, mixed AI wins or action effects never establish hardness, fairness,
learning value or fun.

## Prospective minimal implementation

Plan27 acceptance passed. Add only:

- `scripts/plan0028_play.py`: a trace-preserving copy of the accepted Plan22
  adapter, limited to existing `T2/T3/H2/H3/G` agents;
- `scripts/plan0028_screen.py`: one candidate-specific fixed cascade;
- `tests/test_plan0028_play.py` and `tests/test_plan0028_screen.py`, using only
  mocks or mechanically separated tiny fixtures.

Do not edit src/, research/, DSL, engine, solver, agents, old adapters, tests,
runs or plans. H means the existing goal-progress minimax-v1; T means the
existing terminal-only-minimax-v1; G is the existing one-ply goal agent. The
new adapter changes no algorithm. It must record the complete pre-action state,
canonical choices, selected/applied action, nodes, prefix and exactly one replay.
Tests must not play, solve or replay this5×5 production candidate.

The candidate screen derives actual A-HOP only when the displacement is exactly
twice a declared vector and the saved intermediate cell was occupied. It derives
actual B-PUSH only when the saved destination held an A piece. Count only
selected/applied actions in COMPLETE games and at most once per game/category.

## Prospective fixed cascade

Use protocol/output `plan0028-two-current-cross-weave-v1`, MAX_STATES=100000,
MAX_NODES=100000 and fresh seeds1100/1200. Publish the complete81-attempt
schedule before computation.

1. Existing exact solver once at100000 states. COMPLETE means
   `TOO_EASILY_SOLVED`; UNKNOWN alone opens base and is not hardness evidence.
2. Base H3/H3 and T3/T3, seeds1100..1115:32 games. Every game must end with
   exactly A or B. Each cell requires A wins4..12. Base also requires at least
   four distinct games each with actual A-HOP and actual B-PUSH, and at least
   two GOAL wins for each role. A numerical miss closes final48. A game censor
   is a technical proof-integrity failure and stops the run.
3. Only after base pass, execute all final48:
   - H3/H3 confirmation seeds1200..1215:16, A wins4..12;
   - H3/H2 and H2/H3 seeds1200..1207:16, the depth3 role wins at least6/8;
   - H3/G and G/H3 seeds1200..1207:16, H3 wins at least6/8.

Maximum80 games, one exact call and16,000,000 configured charged search nodes;
the structural depth3 bound is much smaller. No LLM is used per game. The
adapter preserves a game censor as `UNKNOWN_CENSORED`, but the fixed structural
bound makes one impossible under this wire; the screen therefore records a
technical `FAILED`, never a result, difficulty observation or ordinary
insufficient-evidence label. Any draw, PLY_LIMIT, exception, source or
publication drift, invalid prefix/replay, Phi violation, >50ply result, or
initial T3 forced terminal value stops. Once final opens, ordinary numerical
misses do not select which remaining final attempts run.

No retry, resume, backfill, seed substitution, threshold relaxation, cap/depth
increase, D4 duplicate, alternative first player, setup adjustment, added policy,
game, exact call or replay.

## Operational resource policy

Under D-008/D-057, host-dependent wall seconds and RSS bytes are observations,
not scientific gates or censor labels. Reproducible time/memory proxies are fixed
before registration: exact expands/caches at most100,000 GameStates through
depth51 and at most10 children/state; every game has at most50 decisions,10 legal
actions/decision and100,000 cache misses/role. Decision caches are discarded
after each selection. Across the full schedule there are128 depth3 role-games,
16 depth2 role-games and16 unmetered-G role-games, so the structural charged-node
bound is `128*27750 + 16*2750 = 3,596,000`, below the configured16,000,000.
There are at most168 immutable output files, conservatively including distinct
failure and fallback-summary records if two final publications each fail after
creating their destinations; the existing publisher caps each at64MiB. Per-game
elapsed seconds remain descriptive only.

A `MemoryError`, OS kill, manual interruption or other operational exception is
`FAILED`, never UNKNOWN, hardness evidence or a game result. The attempt record
published before computation remains immutable. Catchable exceptions are
finalized by the runner; after an uncatchable termination, closeout derives the
same `FAILED`/`NOT_STARTED_FAILURE` classification from the saved attempt and
missing result. The runner does not claim that an OS-killed process can publish
its own summary. Do not retry or resume.

## Human-attention and acceptance gates

`HUMAN_REVIEW_ELIGIBLE` requires exact UNKNOWN100000, all80 games complete and
decisive, every fixed numerical gate, at least8 distinct complete games each with
actual A-HOP and actual B-PUSH across the full schedule, at least4 GOAL wins for
each role, no known short/simple universal win or dead goal/option, independent
saved/source audit and exactly one registered full-regression pass.

This permits only the user's first playtest. Keep `fairness_established`,
`hardness_established` and `fun_established` false. Do not resume the website,
publish, use paid resources or ask outside testers. If a scientific gate fails,
preserve `NO_FLAG`/`INSUFFICIENT_EVIDENCE`; if evidence integrity or execution
fails, preserve `FAILED`. In either case close the wire and choose a structurally
new question in the next Plan number.

## Activation checklist

- [x] Plan27 full regression and closeout accepted; Plan27 archived unchanged.
- [x] Two independent definition/proof/short-screen/node/schedule reviews PASS.
- [x] Minimal adapter/screen and focused synthetic tests PASS.
- [x] Final source/pin review; one registration commit while execution count=0.
- [x] Exactly one pilot and exactly one full-regression launch from the registered
  clean commit; the regression did not complete before the host reboot.
- [x] Saved-only audit, Japanese findings, technical closeout and honest game label.

## Activation checkpoint

Plan27 is archived as accepted technical evidence with game disposition NO_FLAG.
Its single full regression passed1,348 tests in5,351.812s, `OK (skipped=2)`,
and independent closeout audits matched186 source pins,68 publication hashes,
70 canonical envelopes and all70 isolated/main run files. See
`experiments/reports/0027-acceptance-closeout-ja.md`. At that checkpoint this
satisfied only the Plan27 dependency; Plan28 was still unregistered and its
production execution count was0.

The Plan28 adapter/screen and synthetic tests are now implemented without any
change to `src/`, the DSL, engine, solver or existing agents. The adapter requires
the engine's complete canonical legal-action tuple, preserves full pre-action
states and node deltas, verifies policy-specific censor scope and performs the
single allowed prefix replay. The screen adds no engine replay: it checks adjacent
saved states with a separate candidate-local HOP/PUSH transition, authoritative
legal actions, schema-v4 terminal order and strict Phi decrease. A structurally
impossible game censor, any evidence failure or late publication failure closes
as `FAILED`; pilot output alone always keeps human eligibility false.

Pycompile and root's combined focused run passed21 tests in10.399s. Independent
adapter and screen/protocol reviews PASS after their findings were fixed. Frozen
SHA256 values are adapter
`50fb22c5977835b56cbdf474cd8497b0b0460fee498afe771de212dc228a282e`,
screen `fdb7b45f2b8918d131ba3cb801b9ba29f012b3fe0199973f7828e7b6fa402e41`,
adapter test
`d95d71f70ed1c4e1573d166c6d6e60b477462bec707ef4a689cf71e0923e3184`
and screen test
`47bbd7c09957b2bdc4eb6ba78cca8c11d2ccbee1dd6a1ff460674ca86f1ee51a`.
The final pre-registration checkpoint expected188 tracked Python files plus this
active plan and the proposal,190 pins total. At that checkpoint no Plan28 output
or process existed; the clean source/pin review was therefore permitted to open
the one registration commit below.

Registration completed at
`b0d9b4b7840833ecbe564cbf81eba7ed4ad79a9e`, tree
`ed9cd2c98ea7c93b82221d1b399cdf628b71a72f`. Root and two independent
preflight checks matched190 pins and pin-map SHA256
`a21478ba8a66288790f7abcaa7cc42e9530ba6578e230c56a067f8ffb33f7e33`
in the clean detached worktree `/tmp/parity-forge-plan0028.0JISrP/checkout`.

The first and only pilot session42229/PID94917 started21:43:47 JST and finished
exit0. Exact is UNKNOWN at100,000 states/replay0. All32 base games are COMPLETE
and decisive with no draw, game censor or failure: H3/H3 A4/B12 passes at the
fixed lower edge; T3/T3 A3/B13 misses A4..12 by one. Only one game ended by GOAL
(B);31 ended by NO_LEGAL_ACTION, so the separate base GOAL gate also fails at
A0/B1. Actual HOP/PUSH appeared in31/22 distinct games, passing the interaction
gate. Games lasted12..29ply; charged nodes were A70,960/B61,902. Consequently
`base_pass=false`, final48 are `NOT_STARTED_GATE_CLOSED`, disposition is
`NO_FLAG` and every human/fairness/hardness/fun flag is false.

Two independent saved-only audits PASS without game, solver or replay calls:
70 canonical envelopes,68 publication hashes,190 source pins and all799 saved
transitions matched. Raw-SHA-map digest is
`dff88e07f4f741f44817f461a944a94146b8594e98b2c147697d9b08eec01dd0`;
normalized tree digest is
`2ad8bc4220d6389bc19a24d6274c22483d4e4c5300812bc5f6e68df6dc2e80e8`.
The main raw copy is byte-identical. See
`experiments/reports/0028-two-current-cross-weave-findings-ja.md`.

The exactly one full regression session24610/PID94928 started21:43:55 JST from
the same registered worktree. The last saved observation at22:50:38 showed the
Python process still alive after1:06:32, a1,103-line log, and
`test_selected_five_stabilizer_shards_match_independent_oracles` still running;
there was no final `Ran`, `OK`, or exit code. The host boot record is22:55:35,
4m57s later. After that reboot, the processes, unified session, temporary
worktree and log were gone. An independent session-record audit reproduced this
sequence. Under the fixed operational-failure and no-retry rules, Plan28 closes
as technical acceptance failed without rerunning the suite. This does not alter
the immutable pilot or its `NO_FLAG` game result. See
`experiments/reports/0028-technical-closeout-ja.md`.
