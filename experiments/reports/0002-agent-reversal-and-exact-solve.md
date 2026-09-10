> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Report 0002 — Agent reversal and exact solve

## Observation

On definition `1c478ea40b8c950ab23e6eb31d46a21b247a2f44d01adcb7adb418022ea0e465`,
200 seeded random games gave A 152 wins and B 48. Two hundred seeded
goal-directed games gave A 33 and B 167. Neither profile drew. Average lengths
were 8.51 and 4.465 plies respectively.

## Exact result

Memoized full-width minimax searched 1,314 distinct states and proved A can force
a goal win. The canonical principal variation takes 13 plies; it is one optimal
line, not necessarily the fastest win.

## Interpretation

The random profile points toward the correct role but does not prove it. The
goal-directed evaluator is confidently wrong because locally advancing B's reach
goal is much easier than valuing A's slower connection threat. Averaging the two
would obscure a known false positive.

## Decision

Reject the candidate, retain it as an agent-disagreement regression, and exact-solve
tractable future finalists. Expand candidate coverage before tuning the heuristic.

Raw records:

- [`../runs/20260830T153616787888Z-play-1c478ea4/run.json`](../runs/20260830T153616787888Z-play-1c478ea4/run.json)
- [`../runs/20260830T153746479973Z-solve-1c478ea4/run.json`](../runs/20260830T153746479973Z-solve-1c478ea4/run.json)
