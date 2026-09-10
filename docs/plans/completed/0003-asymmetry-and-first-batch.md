> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan 0003 — Asymmetry and first batch (completed)

## Objective

Generate reproducible DSL-v1 batches, cheaply explain rejections, and identify
whether any definition merits stronger analysis.

## Outcome

- [x] Six mechanical-asymmetry dimensions and a mandatory action-space gate exist.
- [x] Generator v1 and v2 are seeded, canonical, unique, and regression-tested.
- [x] Static failures prevent play simulation.
- [x] Weak and medium outcomes remain separate.
- [x] Immutable batch records contain failure histograms and stage counts.
- [x] Repeated small batches reproduce candidate-level semantic output.
- [x] Near-survivors, random cases, and disagreements were inspected.
- [x] Twenty tractable v2 cases were exactly audited.

Generator v1 produced 100 unique definitions, sent 47 to play, and had no
survivor. Generator v2 changed only the runner start distribution to the edge
opposite its target. It eliminated 25 trivial-start failures and sent 57 to play,
but still had no survivor; draw, long-game, unreachable-goal, and agent-disagreement
failures increased.

The exact audit found 11 forced A wins, 7 forced B wins, and 2 forced draws among
20 play-evaluated 3×3 definitions. This became a frozen evaluator corpus.

## Decision

Do not tune the generator again against unreliable sampled profiles. Improve and
calibrate a stronger evaluator on the frozen exact corpus first.
