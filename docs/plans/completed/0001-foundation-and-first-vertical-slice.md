> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan 0001 — Foundation and first vertical slice (completed)

## Objective

Make the research architecture real with a minimal authoritative DSL, deterministic
engine, frozen degeneracy corpus, and transparent simplicity measurements.

## Hypothesis

A four-primitive schema can satisfy the complete first technical target and expose
useful invalid/trivial examples without general scripting or premature mechanics.

## Outcome

- [x] Operating documents and repository structure exist.
- [x] Definitions parse strictly, serialize canonically, and hash reproducibly.
- [x] Initial state, legal actions, transitions, goals, terminal states, and replay work.
- [x] Determinism and invalid-input behavior have regression tests.
- [x] Seven frozen fixtures cover six static failure categories and one survivor.
- [x] Separate simplicity dimensions are reported and tested.
- [x] Seventeen tests pass on Python 3.9.6.
- [x] Immutable run `20260830T153256441950Z-static-4ad81a40` matched 7/7 cases.

## Interpretation

The restricted vocabulary is sufficient for the first engine boundary and initial
static diagnostics. This is evidence about implementation coherence only. It does
not show that Crossing Seeds is balanced, deep, or enjoyable.

## Decision

Freeze the static-v1 corpus and advance to seeded play-based evaluation. Keep DSL
v1 unchanged until play evidence exposes a concrete limitation.
