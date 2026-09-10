> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan0034 — One bounded adaptive cut-and-choose proof diagnostic

## Status and authority

COMPLETE / TECHNICALLY_ACCEPTED / DIAGNOSTIC_UNKNOWN.
Full regression1,475 tests/5,385.538s/OK(skipped2)/actual exit0; new38 allok.
Independent saved-only evidence audit PASS; both sessions4672/46747 finished.
Archived on2026-09-09 when the user requested continuation into separate Plan35.
User: 「どんどん進めて」, 2026-09-08 JST.
This approves the next minimal diagnostic for unchanged 架ける者、断つ者 after
Plan33's completed source audit. No other original is repaired or researched.

## Question and exit

Can a deterministic budgeted exact solver settle the original16-vertex24-edge
initial game and supply an independently checked adaptive strategy certificate?
An exact forced winner is not by itself unfairness; a small, understandable
strategy may expose a practical-depth defect. UNKNOWN proves neither depth nor
fun. Keep the graph's six boundary-parallel edges, both roles and terminal rules.

The new implementation is separate from all accepted source. Canonical interface
and proof obligations are in [cut-choose-v1](../../designs/cut-choose-v1.md).
Exactly six new files are allowed: cut_choose.py, cut_choose_search.py,
cut_choose_batch.py under src/parity_forge/ and matching test_*.py under tests/.
Combined physical line ceiling1,800; no dependencies, symmetry reduction,
graph simplification, old-code edits, generic generator, website or model per move.
At most one4-hour development unit excluding the one full-suite machine wait.

## Calibration and regression

Four nonterminal solving calibrations only: 2-edge chain(A), direct edge plus padding(B),
4-edge diamond(A), direct edge plus 3 padding/other edges(B). Exact expected
winners follow from hand proofs, not original-game search. Tests may inspect
invalid/initial-terminal rule fixtures separately; they are not solver supply.
Tests may inspect
original dimensions/initial actions, but must not play or solve that candidate.
Each calibration solve at most10,000 expansions/100,000 transitions.
Core owner at most2 focused invocations; main integrated at most3 invocations.
Freeze after independent source review, then run exactly one
`PYTHONPATH=src python3 -m unittest discover -s tests -v` with saved source pins,
log and actual exit receipt. No acceptance claim before it finishes successfully.
If repairs consume the declared unit, report incomplete rather than expand it.

## One prospective candidate invocation

Before production, freeze a JSON manifest with exact original wire/hash,
source snapshot hash, source pins, query, budgets and run ID. Production count0
until registered. No self-play, seeds, policy tuning or more boards in this unit.
Original query: exact adaptive winner from empty round state.
Ceilings:300,000 uncached nonterminal round-state expansions;6,000,000 generated
choice transitions;1,000,000 proof-arc slots;16 MiB serialized result;
1,800 CPU seconds for the whole diagnostic, including proof extraction/checking
and serialization. Proof checking has the same arc cap and nodes<=arcs+1 guard.
First exhausted ceiling returns UNKNOWN, not a game result. No retry/resume or
larger budget in this unit. Serialization overflow is RESULT_BYTE_LIMIT; actual
external interruption is preserved as failure/incomplete, not invented UNKNOWN.
Fixed lexicographic pair/choice ordering, no symmetry.

Output uses exclusive-create claim/registration before computation and separate
immutable result or failure. A decisive result needs the independent proof checker
to pass. The registered diagnostic may execute during the frozen full-suite wait,
but neither new-code nor game acceptance bypasses full regression. Preserve raw
UNKNOWN/failure even if later methods change. Small proof != enjoyable game.

## Next and preservation

Implementation, synthetic calibration, source review, one full regression and
one registered query are complete. Preserve the accepted source and UNKNOWN.
Closeout-record audit PASS; the app confirmed deletion of the finite follow-up
at2026-09-08T01:17:33Z. No pending worker or further computation.
Any future unit needs a separate scope; do not begin one
from this timer or retry the original query with extra resources.
No automatic fairness tournament or human trial. Plan32 optional I/L handoff stays
available; no episode2 and no campaign-budget reset. Old studies/fixtures and
protected Plan13/14 membership remain untouched. No external publication/payment.
No new scheduler is created by this plan document.

## Checklist

- [x] User continuation; source-only Plan33 archived.
- [x] Scope, original rules, budgets and calibration truths fixed before code.
- [x] Implement the six allowed files and calibrate.
- [x] Independent source review; freeze all source/test pins.
- [x] Start and receive actual completion of the single full regression.
- [x] Freeze original manifest from production count0; run once.
- [x] Accept actual full-suite exit and independently verify saved evidence.
- [x] Update Japanese findings/state/backlog with explicit result boundaries.
- [x] Independently verify permanent copies/closeout records and delete follow-up.

## Source freeze and first execution checkpoint — historical

2026-09-07T23:09:26Z: six new files1,299 lines. Core owner focused1/2:
14 tests/0.005s/OK/exit0. Main focused2/3: first32/0.077s, second38/0.096s,
bothOK/actual exit0. The second includes fixes for the independent audit's CPU
handoff boundary and temporary proof-arc accounting. Final read-only source
audit PASS for core/search/independent checker/runner and all matching tests.
No source/test edits after freeze; unused focused capacity is not a new task.

Full suite session4672 started once; no completion/acceptance yet.
Log and actual shell exit marker will be in `/tmp/parity-forge-plan0034.Wd3XH6/`.
`source-pins.sha256` there pins202 current project Python files (including source
outside src/tests); old190 accepted pins were independently checked unchanged.
Do not confuse a broader new pin inventory with altered historical source.

The prospective original manifest is saved at
`experiments/proposals/plan0034-original-adaptive-proof-v1.json`, wire hash
`e9d4174b4d1f7b58ea485a1e5614a7dd119033c93bd3c4fc0dd4a874d131bc02`.
Validation only, production count0. Independent prospective review is pending;
after PASS execute the one query, then preserve result without retry.

## Saved-result checkpoint — 2026-09-08 JST, historical

Independent prospective review PASS before the one query. Session46747 started
by2026-09-07T23:11:57Z and completed with actual exit0; saved completion timestamp
23:12:04.387464Z. UNKNOWN/PROOF_ARC_LIMIT,57,071 expanded round states,
1,000,009 choice transitions, peak1,000,000 retained proof arcs, CPU6.545418s.
Winner/proof/check null. Saved root has exactly4 immutable files/2,147 bytes.
Result SHA256 b6699a0782d2d507cf1e17282f6a259b20382e4d96aba282e9b22978ac0987d5.
Independent saved-only audit PASS for registration/manifest/pins/claims/counters/
hash/actual exit and evidence limits. No query replay, extra solve or game.

[Findings](../../../experiments/reports/0034-adaptive-proof-findings-ja.md).
The fixed proof-storage cap bound before CPU/node/transition limits; this does
not establish intrinsic game difficulty. Future storage architecture is an
untested improvement hypothesis, not permission to expand this query's budget.
Permanent query log/exit/pins: `experiments/reports/plan0034-acceptance-evidence/`.
Full suite4672/PID70948 remains running; code acceptance still pending.

The user's continuing-work request is now backed by a same-task30-minute
heartbeat `parity-forge`, display name `Parity Forge 検証完了の追跡`, created via
the app after no matching automation remained. It follows only actual full-suite
completion and evidence acceptance/failure, stays quiet while unchanged, and
deletes itself at that finite endpoint. No original retry, source edit, paid
resource or next experiment is authorized by the follow-up. OpenAI Docs and
the app's current tool schema were used for setup. Local PC/app must stay on.

## Quiet monitoring checkpoint — 2026-09-07T23:49Z

Full-suite PID70948 is still running at39:52 elapsed, with no exit marker or
final summary. The log has progressed to the master-domain differential test.
All202 frozen Python pins matched again, actual verification exit0. No test,
query, game, proof replay or source change was launched. Acceptance remains
pending; keep the same finite follow-up without notifying on unchanged status.

## Quiet monitoring checkpoint — 2026-09-08T00:23Z

Full-suite PID70948 is still running at1:13:43 elapsed, with no exit marker or
final summary. The log has progressed to typed-occupancy canonical-skeleton
tests. All202 frozen Python pins matched, actual verification exit0. No test,
query, game, proof replay or source change was launched. Acceptance remains
pending; the same finite follow-up continues without an unchanged-status notice.

## Technical acceptance — 2026-09-08 JST

Observed by01:11:06Z, not asserted as process end time: the original session4672
returned actual exit0, shell exit marker0, no running PID70948. Its only full
regression completed1,475 tests/5,385.538s/OK(skipped2). New38 tests allok,
including the CLI failure fixture whose ok is on its next log line.
Independent saved-only audit PASS: current202 pins, old190 pins, six manifest
pins, source chat, independent original-wire hash, registration, four raw query
files/2,147 bytes, result/receipt/log/exit and UNKNOWN budgets all match.
No source/test edit, full-suite retry, query/game/proof replay or protected
candidate access in this acceptance step.

Permanent full-suite and query logs/exits plus source pins are in
`experiments/reports/plan0034-acceptance-evidence/`; copies match original bytes.
Full-suite log SHA256
f4bb7f3d98300c613a02bda88018d5bd512b725c4e389fc35150d1f0a8498f97.
[Exit receipt](../../../experiments/reports/0034-full-suite-exit-receipt.json),
[Japanese acceptance](../../../experiments/reports/0034-acceptance-ja.md).
Raw result remains UNKNOWN/PROOF_ARC_LIMIT, winner/proof/check null. Technical
acceptance is not fairness, practical depth, fun or human readiness. No further
research unit or replacement scheduler is launched by this finite closeout.

Final closeout-record audit PASS: all five permanent evidence files byte-match
their originals; exit receipt hashes/counts/time/scope and Japanese acceptance
agree. The app returned `deleteStatus=deleted` for `parity-forge`, observed at
2026-09-08T01:17:33Z. Only that completed follow-up was removed; source, experiment
evidence and this task remain. No replacement scheduler or new research unit.
