> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Project state

## Current — 2026-09-10 JST

Plan40 ACTIVE / DIAGNOSTIC_RUNNING. Plan39 archived.
[Active plan](plans/active/0040-connection-baseline.md).
Two sketches and one independent design review are finished. Only「架橋と転色」
has an accepted implementation registration; no human/fairness/depth/fun pass.
9x9 Hex: A connects left/right, with3 optional adjacent-pair placements; B connects
top/bottom, with2 optional placement-plus-conversion actions. Connection wins,
not inability to place. Every action fills at least1cell; Hex coloring geometry
gives finite unique termination within81actions. Standard Hex strategy/hardness
is not inherited. Source: [design review](../experiments/reports/0039-objective-design-review-ja.md).
「突破と迎撃」was rejected by a simple B row2 wall/oscillation strategy; no repair.

## Implementation accepted; the single diagnostic is running

Prospective Plan40 registration and implementation contract independently PASS:

- `experiments/proposals/plan0040-connection-baseline-v0.json`
- `docs/designs/connection-v1.md`

Only the initial player differs between two fixed9x9/A3/B2 conditions. Six profile
pairings/eight games per condition,16 total; fixed connection-distance evaluation,
seeded deterministic policies, transition/depth/credit/fallback logs.
Ceilings:6newPython files,3integrated focused invocations, one postfreeze full
regression; one batch/16games/14,400CPU seconds/16MiB; perdecision32,768transitions/
depth3/pergame3m; zero initial exact queries. Acceptance/hashes:
[registration receipt](../experiments/reports/0040-registration-ja.md).
All six files implemented; final focused49tests/0.129s/actualexit0, independent
source/hash auditPASS. Prefreeze CPU-environment guard fixed; rules/agent/budgets
unchanged. Old206 source pins remain intact. Sources frozen; no further edits/tests.
[Checkpoint](../experiments/reports/0040-implementation-checkpoint-ja.md) and
[freeze receipt](../experiments/reports/0040-source-freeze.json).
Full regression COMPLETE:1552tests/5382.233s/OK(skip2)/actualexit0, session54037,
completion chunkc9f5f0. Saved-evidence audit and runner acceptance gate PASS;
old206/new6 pins and frozen inputs unchanged. Regression finished; never poll/restart54037.
[Technical acceptance](../experiments/reports/0040-technical-acceptance-ja.md) and
[actual exit receipt](../experiments/reports/0040-full-suite-exit-receipt.json).
This activation sealed the unchanged registration, six source hashes and actual
acceptance via the accepted CLI (exit0). Independent sealed-input audit PASS. Manifest:
`experiments/proposals/plan0040-connection-baseline-sealed-v0.json`, SHA256
bc7a10e72a9f19ea8e95807ddeb76e02a06aa2f745b0cdf54a9415987e4c420a.
Diagnostic RUNNING session29306, shell29458/Python29459, observed11:43:48Z.
Claim confirmed1/1 and saved registration byte-matches the seal. At observation
0game records saved/16scheduled; no final results/runtime or failure yet.
[Launch receipt](../experiments/reports/0040-diagnostic-launch-receipt.json).
Log/exit: `experiments/reports/plan0040-acceptance-evidence/diagnostic-worker.log`
and `diagnostic-worker.exit`. Next wake resumes this same worker once; no restart,
reseal, code/test/tuning/seed/extra query. Actual completion requires observed exit.
Ledger: focused2/3, full1/1, claims1/1,16scheduled games in flight, exact queries0.
All quality flags false. After completion perform saved-only review and close.

## Persistent constraints

- Mechanically asymmetric, deterministic perfect-information two-player games.
  D-055: every legal play finitely ends with exactly one A/B winner. No draws.
- D-080: prohibit placement-exhaustion loss and semantic relabeling. Placement
  itself allowed; no arbitrary winner/tiebreak repair. Search exhaustion is UNKNOWN.
- Balance/depth/simplicity are goals; board size/extreme simplicity not hard limits.
  No fairness/depth/fun or novelty certification from weak agents/solver exhaustion.
- Preserve all immutable runs/fixtures and old206 source pins:
  `experiments/reports/plan0037-acceptance-evidence/python-source-pins.sha256`.
  No old query/worker retries. Protected Plan13/14 membership/evidence stays closed.
- Plan38 episode2 finished99989/exit0,32games/CPU45.483659s. Its episode3 is cancelled
  by D-080 before registration; do not consume leftover capacity or reopen TILE/TRAIL.
  Plan34/35 UNKNOWN diagnostics and all historical no-retry boundaries stay intact.
- No model per simulated move, paid resources, external tester recruitment,
  unrequested private-research upload or source/history publication. D-086 adds
  only the user-requested separate team system/context snapshot described below.

## User-requested team system handoff — preparing

D-086: user explicitly requested a separate GitHub repository containing the
Parity Forge system and context (intent/philosophy/trial-and-error) for members
and their Codex agents. Prepare a selected, fresh-history export; exclude raw
runs, protected Plan13/14 evidence, credentials, host receipts and Site state.
README and `docs/team/` are the onboarding entry. No frozen Python or scientific
input/output changed; Plan40's worker and budget remain as recorded above.
New-repository creation is blocked: existing GitHub authentication identifies
the owner but POST repository creation returned403 (insufficient permission).
User was asked to create the empty separate repository and provide its URL.
No repository was created and no system files uploaded at this checkpoint.
Private visibility is the conservative proposed default, pending user's choice.

## Existing public game/code-only export — unchanged

[キャッチアンドジャンプ](https://catch-and-jump.realnuun.chatgpt.site/) remains login-free
with AI/shared-device/online-friend play. It is the old I/L trial, not this new
candidate. D-080 does not authorize withdrawal or silent replacement.
[Code-only public GitHub](https://github.com/aaagamesnuun/catch-and-jump-analysis)
remains exactly the separate six-file export. Do not update it with research.
Plan37 accepted:1,503tests/5,387.722s/OK(skip2)/actualexit0;206Python/103Site pins,
saved/deployed version2 and export audited. No pending old computation or deploy.

## Continuation and preserved history

Same-task hourly `parity-forge`, name「Parity Forge 新ゲーム探索」, ACTIVE;
last native update2026-09-10T00:21:00Z. Follow the latest active plan over stale
starting-step wording. One bounded unit per wake, quiet on unchanged/non-actionable
state; notify meaningful findings/completion/failure/required human choice only.
No timer setting changed in this seal-and-launch activation. Latest
active Plan40 sequence supersedes the timer's historical Plan39 starting step.

Complete former startup records are preserved byte-for-byte:
[state checkpoint](PROJECT_STATE_2026-09-10_CHECKPOINT.md) and
[backlog checkpoint](BACKLOG_2026-09-10_CHECKPOINT.md). They are history, not the
current action queue. Do not reread them on each wake unless evidence retrieval
requires it. See [index](INDEX.md) for earlier plans/receipts; no evidence was deleted.
