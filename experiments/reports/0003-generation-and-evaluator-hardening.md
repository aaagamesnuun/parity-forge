> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Report 0003 — Generation and evaluator hardening

## Generator experiment

Generator v1 produced 100 unique definitions; 47 reached sampled play and none
survived. Changing only runner start policy in v2 eliminated 25 trivial-start
failures and raised play admissions to 57, but no game survived. Unreachable,
excessive-draw, and long-game counts increased. The treatment changed failure shape,
not candidate yield.

## Exact false-positive audit

All 20 play-evaluated 3×3 v2 cases were exactly solved: 11 forced A wins, 7 forced
B wins, and 2 forced draws. Random-v1 pointed toward the forced winner in 9/20;
goal-directed-v1 in 12/20. The goal-directed errors included six forced A games it
called B-favored.

## Frozen evaluator change

On the unchanged cases and seeds, minimax-v1-depth3 matched 16/20 forced directions.
Depth 5 matched 20/20. This supports late-stage promotion on this corpus, not a
universal accuracy claim. The depth-5 calibration took about 29 seconds for 600
games, so cascade admission is the next experiment.

## Decision

Freeze generator v2 and all evaluator components. Design a versioned late-stage
admission rule, then test on a held-out generator seed before changing mechanics.

Raw records:

- [`../runs/20260830T154155824053Z-batch-g20260831/run.json`](../runs/20260830T154155824053Z-batch-g20260831/run.json)
- [`../runs/20260830T154309225370Z-batch-g20260831/run.json`](../runs/20260830T154309225370Z-batch-g20260831/run.json)
- [`../runs/20260830T154446539528Z-audit-374bfc58/run.json`](../runs/20260830T154446539528Z-audit-374bfc58/run.json)
- [`../runs/20260830T154624122230Z-calibrate-f27833e8/run.json`](../runs/20260830T154624122230Z-calibrate-f27833e8/run.json)
- [`../runs/20260830T154733530838Z-calibrate-f27833e8/run.json`](../runs/20260830T154733530838Z-calibrate-f27833e8/run.json)
