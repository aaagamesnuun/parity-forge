> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan 0019 — Token-bounded verification calibration

## Status and immediate action

SUPERSEDED_IN_THIS_TASK by the user's division of work. No implementation or
gameplay was executed under this plan. New-method development belongs in a
separate user-managed task; no destination task was created or messaged here.
Plan18 is technically accepted and archived; no qualified game was found.
Immediate action: specify the smallest reusable calibration/batch contract
using existing components, then review it before any implementation or play.

## Question and hypothesis

Can existing deterministic components reject easy failures and easily solved
games under fixed budgets without per-candidate LLM calls or another bespoke
runner per idea? Reusable bounded execution should lower model intervention
per useful experiment. This is not yet a measured efficiency improvement.

## Design boundary and completion gate

- Inventory reuse first: existing batch/cascade uses DSL1 and historical draw
  gates; recent DSL4 pilots have capped execution but study-specific selection.
  Specify a thin connection, not a new engine/platform or broad refactor.
- Define solving target, positive deterministic node/state allowances, safety
  stops, fixed candidate attempts and finite outer review rounds before play.
  Logs stay local; the model receives a compact summary. Token limits are not
  yet measured/enforced; fewer review calls do not guarantee an exact quota.
- Select at most eight outcome-labeled calibration controls, with both obvious
  failures and genuine contingent-choice controls. Define expected diagnoses
  before executing them. Reuse allowed fixtures and respect old-study firewalls.
- D-055 remains universal finite decisive play; D-057 rejects easy solving.
  Solver exhaustion remains UNKNOWN, not complexity/quality-pass. Keep simple
  winning arguments distinct from brute-force tree size and fairness evidence.
- Freeze the comparison criteria for later search-method assessment; do not
  optimize a new generator and its evaluator together or reward timeout rate.
- Done for this design checkpoint: one reviewed implementation/calibration
  specification with finite budgets and stop conditions. No automatic expansion
  to production sampling, paid resources, UI, or human recruitment.

## Preservation and human input

No rerun of Plan15 or completed pilots/exact/replays. Do not open Plan13/14
candidate/evidence membership. Preserve frozen sources, fixtures and raw runs.
Any code change needs focused tests and one full regression before completion.
The user prioritizes simple rules and depth, with possible replay desire from
improvable decisions. This is recorded taste, not a new gate or a blocker.
No human decision is needed for the immediate design task.

## Scope closeout — 2026-09-05

User: 「新しい方法を作るのは別チャットで進める。このチャットでは既存の手法を
改良しながら、遊べるゲームがなるだけ早くできるように進めて」.
Preserve this design as context, but do not implement the generic workflow or
search-method comparison in this task. Plan20 uses existing game/agent APIs for
a small concrete candidate pilot instead.
