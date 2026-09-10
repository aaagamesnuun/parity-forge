> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan 0002 — Basic play evaluation (completed)

## Objective

Measure complete games reproducibly under two different cheap policies and report
role outcomes without conflating draws with balance.

## Outcome

- [x] Random and goal-directed agents choose only engine-produced actions.
- [x] Complete games record actions, result, length, agents, and seed.
- [x] Reports separate wins/draws and give decisive-share Wilson intervals.
- [x] Two profiles evaluated the frozen static survivor over seeds 0–199.
- [x] Seeded candidate-level output has repeatability tests.
- [x] Exact minimax was introduced early to resolve the observed disagreement.
- [x] Twenty-five tests pass.

Random play gave A 152/200 wins (76%, 95% decisive Wilson interval 69.6–81.4%).
Goal-directed play gave A 33/200 wins (16.5%, interval 12.0–22.3%). Neither
profile drew. Exact search over 1,314 states proved a forced A win.

## Interpretation

The candidate is not fair. More importantly, the medium heuristic confidently
favored the role that loses under optimal play. This is a concrete evaluator false
positive and evidence that same-family self-play at a nominal “stronger” level is
not a monotone competence scale.

## Decision

Reject Crossing Seeds as a candidate but preserve it as the first play evaluator
regression. Add explicit mechanical-asymmetry measurement and a structured batch
pipeline before designing a new candidate by hand.
