> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan0022 — Existing-method screen before human attention

## Status and purpose

COMPLETED / ACCEPTED_AS_TECHNICAL_EVIDENCE / NO_HUMAN_CANDIDATE. Plan21 is completed
and technically accepted, its proposed human trial rejected by a direct7-ply
winning strategy. The latest user asks for rules worth human evaluation, not
an unfinished fairness check packaged as a website. Site work remains paused.
Do not alter previous schedules, raw labels, budgets, source or archived fixtures.

Question: can a concrete new, simple no-draw definition survive diverse existing
agent tests, show two-sided benefit from search, and justify spending human time?
This is a designed development screen, not untouched confirmation, proof of
human fairness, proof of hardness, or automatic fun certification. No new
generator platform, evaluation algorithm, agent or DSL primitive.

## One fixed candidate and disclosed design exposure

Use only experiments/proposals/link-hop-three-guards-v0.json definitions[0].
Canonical hash2ce75c6ef9e4abd5ab4401469a4a3be62a22b29a9e7c314be75bc324015ffc4e.
5x5, A-first. A PLACE anywhere empty, CONNECT_TOP_BOTTOM through orthogonal
adjacency, anchors(0,2),(4,2). B has three HOP pieces(1,0),(2,0),(3,0), all eight
one-step directions, REACH_RIGHT. Hop over exactly one adjacent occupied piece
to empty landing; no capture or chains. max_plies40. DSL remains authoritative.

A consumes one empty cell each turn; B preserves occupancy. Initial empties20.
At latest A's20th placement fills the board atply39 and B has no legal action.
Thus every legal play ends decisively by39<40, regardless of B backward moves.
Both goals are initially false and have legal cooperative constructions. No
claim that either has a winning strategy follows from goal functionality.

Source-led precursors were rejected before any gameplay: singleB(2,0) allows
A-first win byA4 through forced blocker departure, or B-first win byB4 through
an early right-edge fork. With3 B, a blocker may remain while another piece
moves; B can stop A's earliest3-placement central connection. This refutes
the old proof, not all simple strategies. B-first remains excluded by the
single-middle-piece B4 strategy, with the other two B stationary. An informal
two-B alternative was considered but not executed or claimed solved.
The separate Japanese source review records these exposures and limitations.
No Plan13/14 members/outcomes were accessed. PLACE/CONNECT versus HOP/REACH
is outside all public old-six signatures and their role swaps; the public
predicate was checked statically. Static canonical parse/hash checks occurred
before registration, not production game/solve/replay execution.

## Frozen prospective schedule and stopping

Publish all129 potential attempts in the manifest before any execution:

1. Existing exact_one once at100,000 states. COMPLETE means TOO_EASILY_SOLVED
   and closes all game gates. UNKNOWN permits the next stage, not qualification.
2. Base: T4/T4 and H4/H4, each seeds100..115,32 games total. Each cell must
   have16 complete decisive games and A wins4..12. Otherwise close later gates.
3. If base passes, run all96 remaining games without result-selected additions:
   - confirmation T4/T4, H4/H4, seeds200..215:32 games;
   - cross-family T4/H4, H4/T4, seeds200..207:16 games;
   - search sensitivity T4/T2,T2/T4,H4/H2,H2/H4, seeds200..207:32 games;
   - simple-policy challenge T4/G,G/T4, seeds200..207:16 games.

T2/T4 are unchanged TerminalOnlyMinimaxAgent depth2/4. H2/H4 are unchanged
MinimaxAgent depth2/4 with the normalized goal-progress leaf heuristic.
G is unchanged GoalDirectedAgent. Fresh agents per role/game, persistent seeded
Random per game,100,000 cumulative cache-miss nodes per search role/game.
G leaf work is unmetered, explicitly not zero compute; engine game bound and
finite legal choices bound it. Maximum128 games/25,600,000 charged search nodes
and1 exact/100,000 states. No LLM call inside the computation loop.

Any completed initial T4 selection with nonzero best terminal-only value proves
a short forced result within four plies: label SHORT_FORCED_RESULT and close
all remaining gates immediately. Valid game censor is insufficient evidence,
never a draw or winner. Any exception, source/publication mismatch, actual draw,
illegal prefix or bound violation saves failure evidence and stops. A closed
gate is NOT_STARTED_GATE_CLOSED, not an attempted failure or completed result.
No rerun, resume, seed backfill, cap increase, deeper retry, or extra PV replay.

## Human-attention gate

HUMAN_REVIEW_ELIGIBLE requires all of the following, fixed before production:

- All128 games complete with one winner; no censor/failure or closed gate.
- Each separate confirmation self-play cell has A wins5..11 of16.
- Cross-family cells together have A wins4..12 of16; report each ordered cell
  too. This paired diagnostic must never be pooled into self-play fairness.
- The deeper role wins at least6/8 in EACH of four search-sensitivity cells.
  T4 also wins at least6/8 in EACH simple-policy challenge role.
- Existing T4 audit values show both+1 and−1 alternatives in at least2 distinct
  games for EACH acting role. These are bounded tactical-choice witnesses,
  not proof of depth, strategic diversity or voluntary replay.
- No known direct short universal win, dead goal, or other structural failure.
- Independent saved/source review and the new full regression succeed before
  asking the user to evaluate the game. Limited source/trace review is not a
  proof that no simple strategy exists.

Report counts, node use and Wilson95 intervals for each relevant cell. These
intervals are descriptive over specified seeded policies, not uncertainty over
human players or minimax balance. Policies share full-width minimax and are
not independent algorithm families; terminal-only versus heuristic provides
limited evaluation diversity only. Equal depths/caps do not imply equal skill.
All fairness_established/hardness_established/fun_established fields remain false.
The gate is an operational reason to ask for human judgment, not all-project success.
Failure or insufficiency closes this fixed screen; never relax it to manufacture
a finalist. Decide a distinct next design or task from the actual failure.

## Minimal implementation and acceptance

New ownership only scripts/plan0022_play.py, scripts/plan0022_screen.py and
their focused tests. Reuse public play_game with thin audit wrappers, existing
agents/exact_one and canonical publication helpers. Preserve the input state,
selected actions and charged nodes across exceptions. If apply fails after
selection, keep that last action unconfirmed, not in the applied prefix.
Each observed game prefix is replayed at most once. Exact success gets one
external PV replay; exact censor gets zero. Audit saved records without reruns.

Calibrate on3x3 synthetic cases and mocks, never this5x5 production definition.
Test schedule/cascade/gates, valid censors, failure and publication accounting,
no overwrite, source drift, no-draw certificate and agent-wrapper equivalence.
Register source/tests/plan/data in one commit before execution; run from its
clean isolated worktree, passing full40-hex hash. Pin all tracked Python plus
this plan and input data before/after attempts. Output directory exclusively
experiments/runs/plan0022-link-hop-v1. Preserve every attempted record and the
complete skipped-attempt accounting. Run exactly one full regression from the
registered new bytes; do not confuse completed Plan21 coverage with this code.

No Site work, network audience changes, outside testers, paid services, automatic
usage reset, or compulsory human questions. Existing same-task heartbeat follows
the latest state and this plan, stays quiet on unchanged non-actionable state,
and never duplicates the fixed computation or regression.

## Preparation checkpoint

Recorder and its7 synthetic focused tests passed independently and under root
in0.121s. Root and independent source review found no blocking issue in the
recorder or this plan. Initial T4 proof means ply0, never B's first decision.
The25.6M node bound is conservative: the16 single-search-role G games reduce
the actual scheduled search-node maximum to24.0M. Keep the stated upper bound.
Pipeline and recorder are complete and frozen. Root reviewed the final pipeline;
independent recorder/protocol review passed. Combined13 synthetic focused tests
passed in2.142s, exit0. No production game, solve or replay has occurred.
Next register these bytes and execute the fixed pilot and exactly one new full
regression from the clean isolated registration worktree.

## Execution checkpoint (supersedes preparation)

Registered atfb55b2a24c867bf3978f8a45479e6cf2bed320c6. Pilot68381/PID4885 and
full suite1843/PID4889 started01:22:57–58 JST on2026-09-06 from
/tmp/parity-forge-plan0022.z3IT62/checkout. Logs in its parent: pilot.log and
full-suite.log. The following interim checkpoint is superseded by the final pilot
checkpoint below. Do not restart or duplicate either process;
inspect saved artifacts without more gameplay or replay. The registered plan
copy remains unchanged in that isolated worktree; this is the progress ledger.

At01:37 JST saved-only interim inspection found16 T4/T4 games: A1/B4 completed,
11 UNKNOWN at the fixed100k role cap. Thus the human-attention gate is already
unattainable; let the registered32-game base stage finish and close the remaining
96 slots as designed. This is insufficient evidence, not proof of unfairness or
hardness. Exact is UNKNOWN100k,0 replay,33.973s. No retry/cap increase.
Independent frozen pipeline reviewPASS. A bounded source-only detour/race branch
review is unresolved, recorded separately in the candidate design note.
The existing30-minute same-task heartbeat was updated through the app to follow
this latest scope and preserve saved-only auditing (no extra replay), instead of
its obsolete Plan16-specific instructions. It remains ACTIVE, no duplicate.

## Final pilot checkpoint; regression still pending

Pilot68381 exit0.33 attempted of129;32 games include10 COMPLETE(A2/B8) and22
UNKNOWN (all A role cap100k), plus1 exact UNKNOWN100k. Both base cells separately
show A1/B4/11censors.96 later slots are gate-closed. INSUFFICIENT_EVIDENCE;
no human eligibility.5,315,088 total charged game nodes. Raw labels preserved.
Independent saved-only auditPASS:70 envelopes,68 publication hashes,176 pins,
registered source/worktree,12 cells, schedule, bounds and one-replay accounting.
The main raw directory was copied once and byte-compared equal to the run.
Report: experiments/reports/0022-link-hop-findings-ja.md. No extra replay/compute.
At02:20 JST suite1843/PID4889 still runs,elapsed57:30. Await actual Ran/OK/exit,
then source/log audit and formal technical closeout. Never poll finished pilot.

While waiting, a distinct data-only source draft was preserved:
experiments/proposals/three-runners-one-hunter-v0.json, canonical hash
1fc21f944747c73dc3cea82a5099849901068171331a49d152e69c37b527bd4b.
See docs/reviews/2026-09-06-three-runners-one-hunter-ja.md. Independent proof
checks passed for termination, goals, no4-turn forced winner and depth4 node
ceiling below100k/role. ELIM is unsupported by current H/G; no execution and no
new code. This is the next concrete design, not extra cases in this fixed screen.

## Final acceptance closeout

The single full regression1843 completed exit0:1298 tests in5269.359s,
OK(skipped=2). PID4889 is gone. Log SHA256:
45ce388eee4302adeadeeea498d349dcbd7ffa9507be7bd2a3d97ae1b8af544f.
Independent audit matched the registered HEAD, all176 pins, the isolated
worktree, the log and all70 main/run bytes. The two skips are unchanged explicit
opt-in reconstructions, not omitted Plan22 coverage. Plan22 is technically
accepted and complete; its game remains INSUFFICIENT_EVIDENCE and is not
human-review eligible. Never restart its pilot, suite, games, exact call or
replays. The separate acceptance report is authoritative.
