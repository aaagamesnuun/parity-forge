> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan 0004 — Minimax calibration (completed)

## Objective

Test whether depth-limited zero-sum search points toward exact forced results more
reliably than the role-local goal-directed policy on an unchanged corpus.

## Outcome

- [x] Minimax-v1 uses terminal utility and normalized A-minus-B goal progress.
- [x] Depth, candidates, evaluator, and seeds are explicit.
- [x] Seeded complete-game output remains reproducible.
- [x] Depth 3 matched 16/20 exact directions (80%).
- [x] Depth 5 matched 20/20 exact directions (100%).
- [x] All 31 tests pass after the evaluator addition.

## Interpretation

Depth alone corrected the remaining four depth-3 direction errors on this small
corpus. This is evidence of perfect classification only for these 20 cases, not a
general guarantee or proof that depth 5 estimates fairness on larger boards. The
depth-5 run took about 29 seconds for 600 games and belongs late in the cascade.

## Decision

Promote minimax-v1-depth5 as a distinct strong diagnostic after cheap profiles.
Retain exact solving for tractable 3×3 finalists and preserve profile disagreement.
