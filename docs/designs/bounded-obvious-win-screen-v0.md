> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Bounded obvious-win screen — discussion draft v0

2026-09-05. Design only, for the separate new-system planning dialogue.
No implementation, gameplay, solver invocation or production budget is registered.
This does not alter Plan20, past criteria, frozen fixtures or immutable outcomes.

2026-09-06 dialogue update: first articulate rule-structure hypotheses that
could defeat simple universal strategies, then refine the policy library from
those hypotheses. This is a generator-design pre-step, not a new quality gate
or implementation authorization. See the
[fourth dialogue exchange](../reviews/2026-09-05-game-generation-planning-dialogue-ja.md).
Termination potential and competitive advantage need not be the same quantity.

## Purpose and scope

The user wants mathematical/analytical/statistical screening for obvious forced
wins within a finite scope, followed by their own playtesting. Personal-experience
elicitation, learning-curve tests, transfer-to-unseen-opponent tests and exact
50/50 are not required screening gates. Whether depth automatically produces
enjoyable learning is left unproved and need not be settled to build this screen.

The screen reports finite propositions, not an absolute depth/fun score. Cover
both short winning play and long winning play described by a simple policy.
Do not require every move in every reachable state to be nonobvious: immediate
wins and forced replies can occur in otherwise worthwhile games.

Input is an authoritative canonical DSL definition, fixed initial state and
first player, a structural all-legal finite-decisive certificate, and a versioned
finite verification configuration. Treat different initial/first-player
conditions separately. No D4/role aggregation can replace their results.
Missing/invalid D-055 evidence makes the definition ineligible for this lane.
Verification horizons never modify game rules or turn unfinished play into draws.

## 1. Short forced wins

For role p, state s and remaining horizon h (one action is one ply), define:

```
W_p(s,h) = (winner(s) == p)                     if terminal(s)
           false                              if h == 0 and nonterminal(s)
           OR_a  W_p(T(s,a),h-1)               if to_move(s) == p
           AND_a W_p(T(s,a),h-1)               otherwise
```

Legal actions and terminal priority come from the existing engine. A correctly
admitted nonterminal state always has an action; an engine inconsistency is an
error, not a vacuous universal proof. Terminal handling precedes the horizon
test, so a win on exactly ply h counts. Horizon exhaustion is false only for
the proposition "can force a win within h"; it is not a loss/draw game result.

Compute both role propositions, or an equivalent completed three-valued
terminal-utility minimax. A verified witness for one role suffices for rejection.
If neither has such a strategy and the required computation finishes, record
NO_FORCED_WIN_WITHIN_H. This excludes all contingent winning strategies within
that horizon, not merely those played by a chosen opponent AI. Deeper wins can
still exist. Budget interruption without a validated proof yields UNKNOWN.
Deterministically valid AND/OR short-circuiting is allowed; numerical estimates
and sampled opponent responses cannot discharge an unproved branch.

Retain the highest completed horizon if a later horizon is interrupted. The
later UNKNOWN does not erase that smaller finite-scope result or turn it into a
completed larger-horizon check.

## 2. Simple policies with unrestricted opponent responses

For each frozen candidate policy pi for role p, check:

```
for every legal opponent policy tau:
    winner(s0, pi, tau) == p
```

At p's turns apply exactly pi's legal action; at the opponent's turns consider
every legal action. The D-055 termination argument covers this restricted game
too. A complete proof gives SIMPLE_POLICY_FORCED_WIN. One complete legal losing
continuation refutes that particular pi. Exhaustion is UNKNOWN.

Policies use a small, explicitly versioned data representation, with an AST
size bound, bounded numerical constants, permitted features, legal fallback and
deterministic tie handling. No embedded solver, unbounded lookahead or large
position table may be hidden behind a short function name. Policy evaluation
work must also be metered. Examples to specify during calibration: always
advance the closest piece, immediate goal progress, greedy capture, immediate
mobility preference. Unsupported features are disclosed, not silently replaced.

Astra can propose an easy-looking strategy with each rule idea, within that
same representation and finite slot limit. A short prose description is a
hypothesis until its executable meaning and proof are checked. Exhaustively
refuting the supplied policies means only THESE_POLICIES_REFUTED. It does not
establish absence of every policy describable in a few words, or enumerate all
programs shorter than some universal description length.

## 3. Cheap complete solve — retained D-057 screen

Keep a separately budgeted call to the unchanged exact solver for new eligible
definitions. Correct completion within the declared easy-solving allowance
rejects under D-057, even if winning play is longer than the short horizon.
Budget exhaustion remains UNKNOWN. This is a supplementary easy-solve probe,
not a requirement to solve every game before human review.

The current solver enumerates all successors before selecting a best value;
its failure to complete is compatible with a simple winning argument. Its PV is
one illustrative line, not a contingent strategy against all replies. Do not
rerun previous UNKNOWN cases to develop this screen.

## Illustrative finite calibration configuration — not registered

| Lane | Proposed ceiling per fixed definition |
| --- | --- |
| Short-win check | Horizons 2,4,6,8 plies; 100,000 charged expansions cumulatively across all attempts/roles |
| Simple-policy check | At most 4 policies per role; 50,000 charged expansions per policy, at most 400,000 total |
| Cheap complete solve | One call; 100,000 searched states |

These are separate work units, not equal-cost algorithms or a human-depth
threshold. Fix accounting for caches, policy evaluation, proof checking, wall
time, memory and output limits in the implementation specification. No unlimited
default, automatic retry, extra policy slot or cap increase is allowed.
Once a validated rejection is found, stop later discovery lanes and record them
as NOT_RUN_AFTER_REJECTION. Errors preserve partial evidence and stop the batch.
This table bounds a proposed per-definition calibration; no outer production
candidate count or review-loop schedule has been activated.

Before gameplay, freeze at most eight independent small calibration controls
and their expected propositions. Include: immediate win; a contingent short
win requiring different replies; a cooperative winning line with a defeating
response; a win exactly at the horizon; a simple win beyond the short horizon;
a refutable simple policy; forced budget interruption; invalid termination
evidence. Logical controls and engine-executed DSL controls must be explicitly
distinguished. Respect existing fixture/membership firewalls and do not build a
general synthetic-game platform to express them. A control can validate a scoped
negative without being a good game or a product-level positive example.

## Evidence and human handoff

Store definition/configuration/policy identities, component pins, charged work,
per-check propositions, validated certificates or counterexamples, errors and
uncompleted checks. A winning certificate must cover opponent branches; a PV
alone is insufficient. For v0, exported independently checked branch certificates
are proposed for the new short-win/simple-policy lanes. The unchanged exact lane
instead uses the accepted, version-pinned implementation's completed calculation
and existing run checks; label this COMPUTED_EXACT_RESULT, not an exported
independently checked strategy proof. Its PV does not supply the missing branches.
Reuse existing record publication and engine semantics.
Any independent certificate validation consumes a declared verification budget;
an unverified claimed proof is not a rejection certificate.

Human-review packets contain complete DSL-derived rules, D-055 evidence,
highest completed short horizon, which simple policies were refuted, exact
probe status, and all omissions. The ordinary screened lane requires the target
short horizon completed and all mandatory simple policies refuted, with no
validated rejection. A cheap exact UNKNOWN can coexist with those scoped facts
and remains explicitly unresolved. Short/policy UNKNOWN does not count as
screen completion; the user may still choose to inspect the incomplete packet.
Neither path is an automated depth/fairness/fun qualification or a reason to
relabel mathematical UNKNOWN. No automatic "best timeout" ranking.

Statistical matches can later find candidate counterexamples or prioritize
manual inspection, but are optional diagnostics. No observed winning percentage
proves a universal forced win. Any future inference needs its opponent/sampling
model and uncertainty stated; repeated deterministic traces are not independent
evidence. Learning/transfer tests do not return as hidden required gates.

## Minimal implementation direction and next design step

Reuse the existing DSL, engine, terminal-only search and capped exact solver.
The current terminal-only minimax already supports the short-horizon semantics
when its computation completes: root +/-1 proves a bounded win; root 0 is not
DRAW. Its public output does not expose a complete branch certificate, so an
output-only adapter cannot supply one. A small separate bounded recursion that
records necessary proof branches, plus a fixed-policy checker, may therefore be
needed outside frozen modules. Reuse engine semantics without modifying frozen
agents/solver or calling their scalar output an exported strategy proof.

Next specify the finite policy representation and certificate/work accounting;
then review the expected calibration outcomes before any implementation/run.
No new general playing AI, reinforcement-learning pipeline, fun model, UI or
statistical tournament is a prerequisite for this first screen.

Related primary sources: [proof-number search overview](https://cris.maastrichtuniversity.nl/en/publications/game-tree-search-using-proof-numbers-the-first-twenty-years/)
on established proof-oriented game-tree search, and
[bounded-model-checking completeness](https://www.cs.cmu.edu/~modelcheck/onr/pubs/threshold03.pdf)
on limits of finite-horizon absence claims. These motivate the distinctions;
this draft does not import a BMC/SAT/PN implementation or claim its game-specific
quantifiers are supplied by an ordinary path-existence checker.
