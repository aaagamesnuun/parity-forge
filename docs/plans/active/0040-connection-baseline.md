> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan0040 — Bounded connection-game implementation and first diagnostic

2026-09-10 JST. ACTIVE / DIAGNOSTIC_RUNNING. D-080–D-085.

## Fixed question and registration

Implement only「架橋と転色」and measure this new family's first bounded baseline.
Can the implementation faithfully realize the connection objective, and what
role/first-player/policy effects appear under the registered limited agents?
This is not a fairness, depth, fun, novelty or human-readiness certification.
It is not a causal improvement comparison with the old exhaustion games.

Authoritative prospective registration:
`experiments/proposals/plan0040-connection-baseline-v0.json`
SHA256 c9ba6db6b00425d014a2a695f46d1552e5d8969c78a626fa27a2d14b34d6d060.
Implementation contract: `docs/designs/connection-v1.md`
SHA256 a481b1223a181a1a46305802099a087476a6c0623898253829ee6b70f991d73a.
Both independently audited PASS; receipt `experiments/reports/0040-registration-ja.md`.
Do not edit these frozen inputs to fit observed play or implementation convenience.

Two empty9x9 Hex conditions have identical A3 bridge/B2 conversion resources and
actions; only first-player A/B differs. A connects left/right, B top/bottom.
Every atomic action fills at least1empty cell; the Hex coloring property supplies
a unique connection winner within81moves. No pass/removal/exhaustion loss or
arbitrary winner override. Standard Hex strategy or hardness is not inherited.
The rejected courier sketch and old TILE/TRAIL families remain closed.

## Completed unit — implementation and technical acceptance

Create only these six Python files; preserve all206 old Python source pins:

- `src/parity_forge/connection.py` and `tests/test_connection.py`
- `src/parity_forge/connection_search.py` and `tests/test_connection_search.py`
- `src/parity_forge/connection_batch.py` and `tests/test_connection_batch.py`

Core must recompute connectivity after conversion and reject invalid terminal
states instead of inventing a winner. Search uses the frozen distance evaluator,
canonical traversal and deterministic role RNG. Only a complete root iteration
may replace the selected action; root children use full windows for valid ties.
Runner requires source/test acceptance, exclusive one-shot claim, complete budget
accounting and an independent set-based replay, once per completed game.

Parallel implementation may split these three module/test pairs with explicit
ownership. Root owns integration and the global budget: at most3 integrated
focused test invocations, including any delegated executions. Read-only source
review is distinct from a suite invocation. Tests use small/synthetic fixtures,
injection and temporary output; never the real cohort or production claim.

After focused PASS, independently review and freeze the six source files, verify
old206 pins, then start exactly one mandatory full regression:
`PYTHONPATH=src python3 -m unittest discover -s tests -v`.
Save command/log/session identifiers and actual process exit; neither a running
log nor Plan37's old result accepts the new sources. If work spans activations,
resume the existing worker and ledger; do not start duplicate suites. Failure
requires an explicit corrective decision before any new budget, not a quiet retry.

## Current unit — follow the single running diagnostic

Only after actual full-regression success, seal a separate executable manifest
containing the unchanged registration object/byte hash and all six source hashes.
Do not turn the prospective file into a post-hoc run manifest. Preflight old/new
pins and acceptance, then exclusively claim the registered fixed paths:

- Claim: `experiments/runs/connection-campaign-v1/batch-1.json`
- Output: `experiments/runs/connection-campaign-v1/plan0040-connection-baseline-v0`

Exactly16 scheduled games, eight per first-player condition. Preserve registered
profile/seed/definition order. One worker/batch; cumulative CPU14,400seconds and
raw output16MiB including claim, plus cooperative limits and OS hard backstop.
Per decision32,768 speculative transitions/depth3; per game3,000,000transitions.
No initial exact queries. CPU/budget interruption is UNKNOWN, never a game loss.
Preserve partial/failed claims and outputs; no replacement run or changed name.

## Final unit — saved-only information review and close

Record actual exit and review saved results without additional games or queries.
Separate role wins, first-player wins, policy pairings, seeds and interruptions;
report actual completed depths, costs, fallbacks, plies and resource use. Paired
seeds are not independent fairness samples. All quality/human flags remain false.
Close after this one cohort and review, even on technical failure or UNKNOWN.
Any later question needs an explicit next plan within existing user authority;
no automatic extra seeds, parameter tuning, candidate or replacement batch.

## Preservation, continuation and ledger

D-055 no draws and D-080 placement-exhaustion exclusion remain mandatory.
Preserve all frozen fixtures/runs, protected Plan13/14 evidence and old no-retry
boundaries. No old worker polling, unrequested Site/GitHub changes or public research upload,
external human trial, paid resources, model calls per move or deployment.
Keep current public game login-free and unchanged; this new candidate is not it.

Existing same-task hourly `parity-forge` remains ACTIVE. Each wake reads current
state, this sole active plan, then backlog. This next unit supersedes the timer's
historical Plan39 starting step; do not regenerate already-reviewed sketches.
Advance one bounded unit per wake, preserve in-flight work, notify meaningful
findings/completion/failure/required choice only. Routine unchanged ticks stay quiet.

- [x] Prospective registration and independent registration audit PASS.
- [x] Six-file implementation and final focused PASS (invocations2/3;49tests/0.129s).
- [x] Independent source review/freeze and old206 pins PASS for new code.
- [x] Mandatory full regression actual PASS (starts1/1,1552tests/5382.233s/exit0).
- [x] Separate executable manifest sealed (CLI exit0, no scientific run).
- [ ] One cohort completed (claims1/1, session29306 RUNNING,16scheduled games).
- [ ] Actual exit receipt, saved-only information review and closure.

Registration activation changed only local proposal/documentation records. New
source files, run claim and output absent; games/exact queries/test suites0.

Implementation activation2026-09-10T03:08:50Z underway. Ownership: core/test pair
plan31_records_audit; search/test pair plan34_runner; runner/test pair root.
playable_candidate_audit read-only. Root alone starts integrated suites.
Focused1: `experiments/reports/plan0040-acceptance-evidence/focused-1.log`,48tests/
0.146s/actualexit0, chunk82406c. Independent review found inheritedCPUhard<14400
must reject before claim; source fixed and mock fixture added, no budget change.
Whole-source read-only review found no remaining blocking issues. Focused2 PASS
49tests/0.129s/actualexit0, chunk41e8c8. Six-hash source pins saved
under `experiments/reports/plan0040-acceptance-evidence/connection-source-pins.sha256`.
Final hash-bound source audit PASS; freeze receipt `experiments/reports/0040-source-freeze.json`.
Full regression1/1 COMPLETE session54037/actualexit0/chunkc9f5f0,1552tests/
5382.233s/OK(skip2). Root observed saved completion10:27:48Z; both PIDs absent.
Completion receipt `experiments/reports/0040-full-suite-exit-receipt.json` matches
the runner acceptance contract; independent saved-evidence audit PASS. Old206/
new6/frozen registration and contract unchanged. Preserve RUNNING launch receipt.
Technical report `experiments/reports/0040-technical-acceptance-ja.md`.
Never poll/restart54037, consume the unused third focused run or edit frozen code.
This activation performed acceptance only, no seal/claim/game. Next activation
may seal via `PYTHONPATH=src python3 -m parity_forge.connection_batch --seal`,
then launch the same module without --seal once; fixed paths and budgets above.
Record actual launch/session and preserve failed claims; no replacement run.

Current launch activation: read-only preflight PASS (chunk0f7d76), seal CLI exit0
(be6769). `experiments/proposals/plan0040-connection-baseline-sealed-v0.json`
SHA256 bc7a10e72a9f19ea8e95807ddeb76e02a06aa2f745b0cdf54a9415987e4c420a.
Independent sealed-input check PASS (f176a2); do not reseal or alter frozen inputs.
One worker RUNNING session29306/shell29458/Python29459 (launchb8068c), observed
2026-09-10T11:43:48Z: CPU97.5%, claim1/1 and saved registration match the seal.
No game records/final results/runtime/failure yet at that observation. Exclusive
`diagnostic-worker.log`/`.exit` in `experiments/reports/plan0040-acceptance-evidence/`.
Launch receipt `experiments/reports/0040-diagnostic-launch-receipt.json` preserves
this RUNNING checkpoint. Next activation resumes only this worker once; do not
reseal, rerun, change sources/parameters or add queries. Preserve partial/failed
claims. After actual exit create a separate completion receipt and saved-only
information review; do not mutate the launch checkpoint or rerun reference replay.

## Separate user-requested team handoff (D-086)

The user requested the system plus intent/philosophy/research history on a new
GitHub repository for teammates. This is a scoped documentation/export task,
not another scientific experiment or permission to modify the existing public
game/code-only repo. Prepare a selected snapshot with clone-specific no-retry
instructions and portable synthetic checks. Preserve all frozen source hashes,
inputs, claims, worker and this plan's scientific ledger. Snapshot-only checks
of unchanged code are portability checks, not new Plan40 acceptance attempts.
At preparation checkpoint, GitHub repo creation returned403; the user was asked
to create an empty separate repository. No external upload completed yet.
