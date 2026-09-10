> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan 0005 — Strong cascade integration (completed)

## Objective

Integrate calibrated search into batch screening without spending depth-5 compute
on definitions that cheap checks already reject.

## Hypothesis

A staged policy—static/asymmetry, cheap sampled play, exact audit of every tractable
3×3 case, and depth-5 only for admitted 4×4 cases plus exact 3×3 draws—will reduce
false classifications while keeping compute concentrated on informative games.

## Expected result

The next frozen batch reports time and candidate counts per stage, retains all
profile outcomes separately, and produces either exact-rejected candidates or a
small frontier whose uncertainty is explicit.

## Definition of done

- [x] Define the late-stage admission rule without using one weighted score.
- [x] Add minimax-v1-depth5 summaries without overwriting weak/medium evidence.
- [x] Route every cheap-play 3×3 candidate to budgeted exact solving.
- [x] Record per-stage candidate counts, elapsed time, and deterministic budgets.
- [x] Implement the separate admission-blind depth-5 audit before held-out data.
- [x] Make both held-out attempts fail closed and preserve start/failure evidence.
- [x] Run a frozen evaluator on a new generator batch or a held-out seed.
- [x] Inspect finalists, random cases, and evaluator disagreements.

## Frozen components

DSL/engine/generator-v2/static/simplicity/asymmetry/play/minimax-v1 and all current
thresholds. Cascade-v2 is frozen by commit before the held-out generation run.

## Predeclared admission rule

A cheap-play candidate is admitted when it is not `TOO_SHORT` and either:

- weak-random draw rate is at least 0.50 (inclusive), or
- neither `A_DOMINANT` nor `B_DOMINANT` was assigned.

On development evidence this admitted 25/57, retained 2/2 exact draws, and admitted
only 1/18 forced results. These are tuning facts, not held-out performance claims.

Every cheap-play 3×3 case is exact-audited independently of admission. This avoids
verification bias and was substantially cheaper than depth-5 play on development
data. Exact labels do not affect admission, and audit-only results cannot rescue a
definition that was not admitted.

## Held-out protocol

- Generator v2 seed `20260901`; 100 unique definitions. Seed `20260902` remains
  untouched for later replication.
- Random-v1, goal-directed-v1, and minimax-v1-depth5 use seeds `0..29`.
- Development-seed definition overlaps are excluded without replacement.
- Every cheap-play 3×3 case receives up to 100,000 exact states.
- Admitted 4×4 cases and exact 3×3 draws receive up to 5,000,000 depth-5 nodes
  across 30 games. Admitted 5×5 cases are explicitly budget-deferred.
- Budget exhaustion is uncertainty, never rejection or survival.
- Wall time is observational and never controls eligibility.

Primary compute support requires admission of no more than 50% of novel cheap-play
cases, no depth-5 candidate-cap exhaustion, and at least 90% completion among
selected depth-5 attempts; node-cap cases are incomplete, while predeferred 5×5
cases are outside that denominator. Zero depth-5 attempts is inconclusive. Exact
completion is assessed against every novel cheap-play 3×3 case. Admission recall is
assessed only if at least two held-out exact draws occur; otherwise it is
inconclusive. The three dimensions are reported independently, with any failure
taking precedence over inconclusive evidence. Zero finalists is not experiment
failure.

After primary statuses are sealed, the admission-blind audit evaluates every
exact-completed 3×3 case. Strong-evaluator support requires at least 15 completed
cases, at least 90% direction accuracy, and zero exact draws called decisive. Any
node-budget deferral or fewer than 15 cases makes that audit inconclusive.
An observed exact-draw decisive error takes precedence and fails the strong
evaluator even if another case is censored or fewer than 15 cases complete.

Post-run qualitative inspection is exploratory: every survivor, deferral, exact
draw, and cheap/strong direction disagreement, plus ten otherwise non-late-stage
novel cases selected by the smallest
`sha256("inspection-v1:" + definition_hash)` values. It cannot change the
predeclared outcomes.

## Outcome

Run `20260830T184008717197Z-strong-g20260901` evaluated the held-out seed once
from clean commit `179fe0b`. Of 99 novel definitions, 63 reached cheap play and 26
were admitted. Exact solving completed all 14 eligible 3×3 cases; depth 5 completed
all 12 admitted 4×4 cases. There were no survivors. Thirteen admitted 5×5 cases
received the predeclared board-size deferral.

The compute and exact-completion hypotheses were supported. Admission draw recall
was inconclusive because the exact set contained 6 A wins, 8 B wins, and no draws.
The blind audit matched all 14 forced directions, but its predeclared minimum was
15, so that result was also inconclusive. Full results are recorded in report 0005.

## Interpretation

The bounded cascade worked operationally, but the admission signal failed as a
discovery heuristic. Every admission came from weak-random high draws, all such
draws were ply-limit terminations, and every admitted candidate already carried a
non-rescuable cheap shape failure. Strong search therefore had diagnostic value but
could not discover a survivor under the frozen finalizer.

## Decision

Preserve cascade-v2 and its held-out evidence unchanged. Do not evaluate the
deferred 5×5 cases, retune on seed `20260901`, or spend seed `20260902` merely to
chase the audit sample threshold. Separate outcome-independent landscape discovery
from evaluator stress testing in the next plan.
