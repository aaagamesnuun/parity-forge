> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Report 0004 — Strong cascade held-out preregistration

This protocol was written before generating or inspecting seed `20260901`.

## Hypothesis

Cascade-v2 will route no more than half of cheap-play candidates to discovery
admission, complete at least 90% of attempted depth-5 work within its deterministic
budget, and exactly solve every eligible 3×3 candidate. It will retain every
held-out exact draw if at least two such draws occur.

## Frozen treatment

- generator-v2 seed `20260901`, exactly 100 unique definitions
- random-v1 and goal-directed-v1: seeds 0–29
- admission: not `TOO_SHORT` and (`weak-random draw_rate >= 0.50` or no dominance)
- exact lane: every cheap-play 3×3 case, 100,000-state cap per definition
- strong lane: admitted 4×4 cases plus exact 3×3 draws, minimax-v1-depth5,
  seeds 0–29, 5,000,000-node cumulative cap per definition
- admitted 5×5 cases: `DEFERRED_BUDGET`, not rejected
- development definition hashes from seed `20260831`: excluded without replacement
- generator seed `20260902`: untouched replication reserve
- one-shot enforcement: exact config/source fingerprints, clean commits, canonical
  run directory, and immutable attempt evidence written before either held-out stage

Candidate corpus is the sole primary experimental variable. Reusing play seeds
prevents simultaneous stochastic-resampling changes.

## Interpretation declared in advance

- **Compute support:** admission ≤50% of novel cheap-play entrants, no depth-5
  candidate-cap exhaustion, and at least 90% of selected depth-5 attempts complete.
  Node-budget exhaustion is an incomplete attempt. Admitted 5×5 cases are outside
  this denominator because the treatment predeclares them as board-size deferrals.
- **Compute failure:** admission >50%, any depth-5 candidate-cap exhaustion, or
  depth-5 attempt completion below 90%. Zero selected attempts is inconclusive.
- **Exact-completion support:** every novel cheap-play 3×3 case completes exact
  solving. Candidate-cap and state-cap censoring are both inconclusive; zero
  eligible cases is also inconclusive.
- **Admission support:** at least two exact draws complete and all were admitted.
  With at least two, any missed draw is failure; fewer than two or incomplete exact
  coverage is inconclusive.
- **Primary precedence:** compute, exact completion, and admission recall are
  reported independently. Overall is failure if any dimension fails, otherwise
  inconclusive if any dimension is inconclusive, otherwise supported.
- **Candidate outcome:** zero finalists is allowed and does not falsify the cascade
  hypothesis.
- **Strong-evaluator support:** the blind audit completes at least 15 cases,
  matches exact direction on at least 90%, and calls no exact draw decisive.
- **Strong-evaluator failure:** completed direction accuracy is below 90% or any
  exact draw is called decisive.
- **Strong-evaluator inconclusive:** fewer than 15 cases complete or any case is
  censored on node budget, unless an exact-draw decisive error was already observed.

Decision precedence is conservative: any observed exact-draw decisive error is a
strong-evaluator failure even when another blind-audit case is censored or fewer
than 15 cases complete. Otherwise censoring/low support is inconclusive before the
90% direction threshold is interpreted.

A separate blind depth-5 audit of every exactly solved held-out 3×3 case will test
direction accuracy after primary admission is sealed. It cannot alter primary
admission or candidate status.

Likewise, the exact lane and any draw diagnostic may expose an admission false
negative, but cannot convert that definition into a primary survivor.

Qualitative follow-up is exploratory and cannot change these outcomes. It will
inspect every primary survivor, every deferral, every exact draw, every available
cheap/strong direction disagreement, and ten otherwise non-late-stage novel cases
with the smallest `sha256("inspection-v1:" + definition_hash)` values.
