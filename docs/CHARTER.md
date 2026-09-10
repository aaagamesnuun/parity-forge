> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Project charter

## Placement-exhaustion exclusion — user confirmed 2026-09-10 (D-080)

The user finds "最後に置けなかったほうが負け" uninteresting and prohibits it in
future games. Exclude definitions in which inability to make another legal
placement itself determines the loser, including equivalent last-placement-wins
wording. This is a product eligibility condition, not a fairness result and not
something stronger AI or a larger board can override.

Do not ban placement as an action. Investigate distinct victory objectives such
as capture, connection or reaching a goal, subject to mechanical asymmetry and
finite, exactly-one-winner termination for every legal play. These are directions,
not automatically approved rules. Exhaustion without an objective outcome needs
a real rule/termination review; do not silently add the prohibited loss rule,
an arbitrary tiebreak or a reversed-winner variant. Renaming the same exhaustion
game as movement is not a substantive response to the feedback.

Plan38's T4/L4 and O4/I4 follow-up is cancelled before episode3 registration.
The current finite-space engine's fixed NO_LEGAL_ACTION_LOSES terminal rule is
historical infrastructure, not an admissible default for new candidates. Retain
old experiments, results and software fixtures; do not relabel empirical findings
as mathematical rejection. The existing public game and code-only GitHub remain
unchanged; this instruction does not request withdrawal or a replacement release.

## Current scope override — user confirmed 2026-09-08 (D-064)

For future planning, mechanical asymmetry is mandatory, not merely an exploration
hypothesis. The user also explicitly reaffirmed D-055: every legal play must end
finitely with exactly one winner. Board size and extreme rule simplicity are
not product hard constraints. Depth, practical solving resistance, balance and
ease of learning remain design goals, without an absolute AI-hardness or exact
50/50 certificate before personal exploratory playtesting.

This latest clarification takes precedence over conflicting historical mission,
initial-universe and simplicity statements below. It does not change any frozen
definition, threshold, result or no-retry commitment. The user now requests
planning for discovery-system improvement and human/AI division in this task;
the earlier separate-task limitation does not prevent that planning. Plan31 is
paused before registration; this is not permission to launch a new experiment.
See the [bounded discovery and collaboration plan](reviews/2026-09-08-discovery-reset-and-human-ai-loop-ja.md).

## Mission

Continuously discover simple two-player abstract strategy games with enough
depth to make acquiring skill enjoyable. Explore mechanical asymmetry as a
promising underexplored rule space, and measure balance without making exact
50/50 a necessary condition.

## New-system planning clarification — user confirmed 2026-09-05

The user aspires to depth that professional shogi players could enjoy, with
depth sufficient for the user and friends as an acceptable fallback. They want
a verifiable operational definition of depth; that definition, thresholds and
AI/resource requirements are still under joint discussion. Human enjoyment and
professional-level depth cannot be certified by solver exhaustion or an AI's
nominal search budget.

Asymmetry is an exploration hypothesis, not a requirement that the two roles
produce different subjective judgments or experiences. Claimed underexploration
has not been established by a novelty survey. Exact 50/50 is optional; disclose
role/first-player imbalance and investigate trivial dominance independently.
The assistant's earlier role-experience framing is not a user requirement.

This clarification supersedes the old fairness-first priority for future
new-system planning. It does not alter any frozen experiment criteria, results,
or current Plan20 registration. D-055 and the existing D-057 easy-solving screen
remain in force. See the
[planning dialogue](reviews/2026-09-05-game-generation-planning-dialogue-ja.md).

Further clarification in that dialogue: the user chooses bounded mathematical/
analytical screening for obvious forced wins, then personal playtesting of the
remaining candidates. Personal-experience elicitation, learning-curve tests and
transfer-to-unseen-opponent tests are not required gates. Their hypothesized
connection to depth remains unproved without blocking this narrower scope.
The [bounded-screen draft](designs/bounded-obvious-win-screen-v0.md) proposes
short-horizon and simple-policy proofs; its thresholds are not yet registered.
Finite-scope absence and UNKNOWN must remain distinct from absolute depth claims.

## Mandatory decisive termination — user confirmed 2026-09-05

The user explicitly requires games in which draws do not exist (D-055).
Every legal play from an admitted initial state must terminate in finite play
with exactly one winner, A or B. No draw, winnerless ending, or indefinite
cycling is allowed. This is a hard qualification condition before fairness,
not a soft draw-rate preference or merely an optimal-play/sampled-play check.
A legal draw witness excludes that unchanged definition; observing zero draws
does not prove conformance. Unknown termination/search exhaustion is not a win
or draw and cannot qualify a game.

Historical DSLs, tests and experiment results retain their original semantics.
New termination or tiebreak rules require a separately reviewed definition and
evaluation; do not silently relabel old draws or award an arbitrary winner.
The Plan-0017 DRAW definition is ineligible under this requirement, and its
proposed draw-preserving continuation is cancelled as a discovery next step.

Finite deterministic perfect-information games without draws necessarily have
an optimal-play forced winner. Therefore exact A_WIN/B_WIN alone is not an
unfairness rejection. Fairness still concerns comparably capable players;
trivial forced strategies, role dominance and poor interaction remain separate
failure modes. Equal A/B win counts across matches are not a drawn game.

## Practical solving resistance — user clarified 2026-09-05 (D-057)

The user requires simple rules with enough computational complexity that AI
cannot easily solve the game completely. This is distinct from the existence
of an optimal-play forced winner. Easily solved definitions are not product
finalists, even when they meet no-draw, fairness and simplicity diagnostics.
Operational tests must preregister solver versions, the meaning of "solved"
and finite compute budgets; no claim covers every possible AI or unlimited
resources. Budget exhaustion alone proves neither difficulty nor quality.
Simple rules plus practical solving resistance is the user's game-design
hypothesis, not an established sufficient condition for enjoyment.

Spend model tokens on reusable development, design proposals and bounded batch
review. Candidate-level play, deterministic checks and aggregation should run
as ordinary programs without per-game LLM calls. Bound both compute batches and
the outer model-review loop; do not automatically expand budgets on failure.

## Initial universe

- deterministic, finite, perfect information, alternating turns
- square boards of size 3×3 through 5×5
- A primarily places; B primarily moves
- no chance, hidden information, executable rule callbacks, or network services

## Initial lexicographic priorities — historical planning baseline

The list below records the earlier objective ordering. New-system planning
follows the clarification above: simple rules and enjoyable skill development
are central, exact balance is optional, and the depth measurement is pending.
Preserve the original ordering in already registered experiments.

1. Reject invalid, draw-capable, nonterminating and degenerate definitions.
2. Require credible fairness across agent strengths; report draws separately.
3. Require meaningful mechanical asymmetry.
4. Minimize structural, descriptive, and operational complexity.
5. Diagnose strategic richness.
6. Preserve novelty.
7. Prefer human enjoyment once human evidence exists.

Scores are not proofs. Estimated balance is not proven fairness, and a strategic
proxy is not fun. Simplicity is a scientific objective rather than cosmetic
polish. New mechanics must be justified by experiments.

## Early success

- **0.1:** reproducibly generate and evaluate a large batch and explain failures.
- **0.2:** find multiple provisional fairness/asymmetry/simplicity qualifiers.
- **0.3:** demonstrate directed search beating frozen naive random generation.
- **0.4:** remove rules while retaining measured candidate properties.
- **0.5:** produce games human testers voluntarily replay.
