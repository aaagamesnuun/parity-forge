> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan0023 — Runner/hunter existing-agent screen

## Status and purpose

COMPLETED / REJECTED_BEFORE_REGISTRATION / NOT_EXECUTED. Plan22 is
completed and technically accepted, with no human candidate. Site work remains
paused. The latest user asks us to continue until rules merit human review.

Question: can one concrete no-draw runner/hunter game survive a bounded screen
using only existing random and terminal-only minimax agents, without the
branch-budget censor that made Plan22 inconclusive? This plan adds an audit
adapter and experiment runner, not a new agent, evaluator, search algorithm,
DSL primitive or generic discovery framework. Do not change frozen agent v1
semantics or add ELIMINATE goal-progress yet.

## One fixed candidate and disclosed exposure

Use only experiments/proposals/three-runners-one-hunter-v0.json definitions[0],
canonical hash1fc21f944747c73dc3cea82a5099849901068171331a49d152e69c37b527bd4b.
5x5, A first. A has three runners at(0,1),(0,2),(0,3), moves one exactly one
row forward and at most one column sideways, and wins when one reaches BOTTOM.
B has one hunter at(3,2), moves one Moore-neighbor step, captures an A on its
destination, and wins by eliminating all A. No pass.

The sum of remaining runner row-distances starts12, decreases on every A move
and every B capture, and is preserved only on B ordinary moves. Therefore all
legal play is decisive by23<cap25. Both goals are initially false and have
source-constructed cooperative legal routes. Independent source review proved
that each side has a response preventing the opponent from forcing a win within
its first four turns. It did not prove the longer winner or absence of another
simple strategy.

A always has at most9 legal actions and B at most8. For full-width depth4,
even without cache benefit, one A choice charges at most5913 successor nodes
and one B choice5840. At most12 A and11 B selections give conservative cumulative
bounds70956/64240, below100000 per role/game. Independent source review checked
these bounds against the existing node accounting. This is a completion bound,
not evidence of depth, fairness or wall-clock speed.

The central-three setup was chosen after source consideration of an unexecuted
edge-spread setup and a dense CONVERT draft; disclose this as designed
development, not untouched confirmation. The MOVE/REACH versus
MOVE_CAPTURE/ELIM signature is outside the public old-six signatures including
role swaps. Do not access Plan13/14 members or evidence.

## Minimal adapter qualification

New ownership only scripts/plan0023_play.py, scripts/plan0023_screen.py and their
focused tests. The play adapter wraps unchanged public play_game and unchanged
RandomAgent or TerminalOnlyMinimaxAgent depths2/3/4. Policies are R,T2,T3,T4.
Fresh agents per role/game, one persistent seeded Random per game,100000
cumulative cache-miss nodes per search role. Random selection work is explicitly
unmetered, not zero compute. Preserve decisions, canonical legal choices,
selected/applied prefix distinction, nodes, failures and censors. Replay each
observed prefix at most once. Synthetic3x3 tests only before registration;
never execute this5x5 candidate during calibration.

## Frozen prospective schedule and stopping

Before production, publish the complete81-attempt schedule:

1. Existing exact solver once at100000 states. COMPLETE is
   TOO_EASILY_SOLVED and closes every game gate. UNKNOWN permits the base only.
2. Base: T4/T4 and T3/T3, each seeds300..315:32 games. Every game must complete
   decisively. T4/T4 must have A wins5..11 and T3/T3 A wins4..12; otherwise
   close later gates. These match the final gate, so a known-ineligible base
   never spends the remaining48 games.
3. If base passes, run all48 remaining fixed games:
   - confirmation T4/T4, seeds400..415:16;
   - search sensitivity T4/T2 and T2/T4, seeds400..407:16;
   - simple challenge T4/R and R/T4, seeds400..407:16.

Maximum80 games and1 exact call. Conservative charged ceiling16,000,000 search
nodes, although R roles and structural bounds make actual possible use lower.
No LLM call inside computation. Any valid censor is UNKNOWN and closes human
eligibility. Any exception, draw/PLY_LIMIT, source/publication drift, invalid
prefix, replay mismatch or natural-bound violation saves FAILED evidence and
stops. Closed gates remain NOT_STARTED_GATE_CLOSED. No retry, resume, seed
backfill, cap increase, deeper search or extra PV replay. Exact COMPLETE gets
one external PV replay; exact UNKNOWN gets none.

An initial completed T4 choice with a nonzero best terminal-only value is a
SHORT_FORCED_RESULT and closes remaining gates. It proves only a forced terminal
within the search horizon. Keep fixed-first and ordered-policy cells separate.

## Human-attention gate

HUMAN_REVIEW_ELIGIBLE requires all prospectively:

- exact UNKNOWN at100000 and all80 games complete with exactly one winner;
- A wins5..11 in EACH of the base and confirmation T4/T4 cells;
- T3/T3 A wins4..12;
- the depth4 role wins at least6/8 in EACH ordered T4/T2 cell;
- T4 wins at least7/8 in EACH ordered T4/R cell;
- T4 recorded both+1 and-1 legal alternatives in at least2 distinct games for
  EACH acting role;
- no known direct short universal strategy, dead goal or proof defect;
- independent saved/source review and exactly one new full regression pass
  before asking the human to play.

These gates are an operational reason to spend human attention, not proof of
perfect-play fairness, human skill equivalence, hardness, replayability or fun.
T2/T3/T4 share one algorithm family; deeper observed wins do not by themselves
calibrate skill. R is only a simple-policy challenge. Report every denominator,
ordered cell, censor, node count and descriptive Wilson95 interval. Keep
fairness_established, hardness_established and fun_established false even on
eligibility. Failure closes this fixed screen; choose a distinct design from the
actual failure rather than loosening thresholds.

## Registration and acceptance

Focused tests and independent source/protocol review must pass first. Register
plan, proposal, adapter, runner and tests in one commit. Execute the single
pilot and exactly one full regression from a clean isolated worktree at that
full40-hex commit. Pin all tracked Python plus this plan and proposal before and
after every attempt. Exclusive output:
experiments/runs/plan0023-three-runners-one-hunter-v1.

Preserve the immutable raw run and audit it without new game/solver/replay calls.
Update PROJECT_STATE, this plan and BACKLOG at checkpoints. No Site work,
network publication, outside testing, paid services, automatic usage reset or
compulsory human question.

## Pre-registration rejection

The candidate is rejected without production execution. Two independent
source-only reviews verified a universal A-first win by A6: A establishes
runners at(1,0) and(1,4) on A1/A2, then chooses the edge the single hunter
cannot reach after B2. If the hunter remains central, A first advances the
right runner and switches to the left when B commits right. Full cases are in
experiments/reports/0023-short-win-proof-ja.md.

This invalidates the human-attention purpose before registration. No exact
call, candidate game, candidate replay, manifest, run directory or full
regression was started. The partially prepared generic R/T audit adapter passed
synthetic focused tests but remains unregistered and is not accepted production
source. Do not execute this candidate, complete the candidate-specific runner,
or reinterpret the source proof as sampled evidence.
