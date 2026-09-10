> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Report 0001 — Static foundation baseline

## Hypothesis

The v1 parser, static diagnostics, and simplicity evaluator reproduce all expected
labels in the manually frozen static-v1 corpus.

## Result

Run `20260830T153256441950Z-static-4ad81a40` matched all 7 cases. The histogram
contained one each of `INVALID_DEFINITION`, `NO_LEGAL_MOVE_AT_START`,
`UNREACHABLE_WIN_CONDITION`, `TRIVIAL_FORCED_RESULT`, `TOO_SYMMETRIC`, and
`TOO_COMPLEX`; one fixture survived.

## Interpretation

This demonstrates consistency with the small authored contract, not external
validity. The corpus is too small and too static to establish game quality. The
surviving `Crossing Seeds` fixture is suitable as a frozen subject for the first
play evaluator precisely because no balance claim has been made about it.

## Decision

Freeze this baseline. Compare seeded random and goal-directed agents on the same
definition before expanding the DSL or generating candidates.

Raw record: [`../runs/20260830T153256441950Z-static-4ad81a40/run.json`](../runs/20260830T153256441950Z-static-4ad81a40/run.json).
