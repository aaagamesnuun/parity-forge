> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan0035 — Cut-potential certificate, one unchanged-original diagnostic

Archived2026-09-10 on new user authority for Plan36 playable delivery.

## Status and authority

COMPLETE / TECHNICALLY_ACCEPTED / DIAGNOSTIC_UNKNOWN.
Accepted2026-09-10 JST; started2026-09-09 JST. User: 「続けて」 after accepted Plan34.
Full regression1,503 tests/5,374.197s/OK(skipped2)/actual exit0. All28 new tests ok.
Independent saved-evidence and final copy/receipt/report audits PASS. No pending
computation; finite follow-up deleted2026-09-09T15:53:16Z. See final checkpoint.
Plan34 is closed and archived; its query/result/pins remain immutable UNKNOWN.
This new unit changes only the search/certificate method, not generator, DSL,
agent policy, rules, original graph, order or registered resource ceilings.

## Question and analytic gate

Can an exact cut-potential B certificate eliminate enough game-tree expansion
to settle the original24-edge game within the previous resource ceilings?
No conclusion is promised. A direct two-spanning-tree invariant was considered
and rejected: local choose/delete need not preserve it (two K4s joined at one
vertex). Do not import a different Shannon/Picker-Chooser game's winner theorem.

Fixed family F: all inclusion-minimal original L–R edge cuts, not just smallest
cardinality cuts. In a round state with secured S, removed D and unresolved U,
Phi=sum over C in F with C intersect S empty of 2^(-|C intersect U|).
For either offer, the two resulting potentials average at most current Phi:
an active cut contains0/1/2 offered edges, with average contribution w/w/0.
B can keep Phi nonincreasing. If Phi<1, a wholly removed cut (contribution1)
is impossible; finite unique termination implies B win. Phi=1 does not suffice.
Independent read-only mathematical review PASS before implementation. No original
enumeration, play or solver invocation has occurred in this unit's analytic gate.

## Implementation boundary

Four new files only: src/parity_forge/cut_choose_potential.py and
src/parity_forge/cut_choose_potential_batch.py, plus matching tests/test_*.py.
Combined ceiling1,400 physical lines, stdlib Python3.9, one4-hour development
unit excluding mandatory full-suite machine wait. Reuse frozen Plan34 core and
budget helpers; do not edit accepted Python, fixtures, original wire or old runs.
No dependencies, graph-state quotient, symmetry, ordering or value-cache rewrite.
Exact DFS retains the prior proof-arc accounting; the only shortcut is a
separately checked strict cut-potential B leaf. All24 legal edge IDs remain.

Enumerate cuts by assigning every nonboundary vertex a side; left all inside,
right all outside. Maximum10 nonboundary vertices (<=1,024 assignments), fail
unsupported larger inputs rather than search unboundedly. Dedupe cut masks and
retain inclusion-minimal cuts. This is complete because every L–R separating
edge set contains some such cut. Boundary-parallel edges are absent from cuts,
not from legal offers. Compare integer weights scaled by2^edge_count.
Independent checker reconstructs cut candidates and verifies minimality using
graph disconnection plus reconnecting each removed edge, not solver cut/cache.

Proof format parity-forge:cut-choose-potential-proof:v1, graph hash bound,
root0:0, winner, nodes. Node keys winner/kind/replies, kind TERMINAL,
CUT_POTENTIAL or BRANCH. Potential leaf must be nonterminal B, replies[], and
independently computed Phi<1. Branch quantifiers remain one offer/both responses
for A, every legal offer/one response for B. TERMINAL independently checked.
No claimed weight or cached winner is trusted. Reject orphan/false/illegal proof.

solve/verify_proof API and baseline result keys match Plan34, with result counters
cut_count,potential_checks,potential_leaves added. Charge1 expanded node before
each uncached nonterminal potential check. Count potential leaves actually saved
by search, not as games. CPU covers cut generation, search, extraction, checking
and runner serialization. Checker returns potential_leaves count too.

## Calibration and freeze

Same four hand-solved synthetic nonterminal graphs as Plan34 only; rule fault
fixtures separately. No original play/solve/cut-family computation in tests.
Each synthetic solve <=10,000 nodes/100,000 transitions. Search owner focused
ceiling2 invocations; runner owner0; main integrated3. Existing source freeze
pins checked, independent new source review, then exactly one full regression
PYTHONPATH=src python3 -m unittest discover -s tests -v with source pins/log/exit.
No technical acceptance before actual successful completion. Repairs must remain
inside this unit; failure or exhaustion is recorded without budget expansion.

## One prospective production query

Fresh manifest and exclusive run id plan0035-original-cut-potential-v1 bind the
unchanged full24-edge wire/hash, sourcechat, four new files plus three imported
Plan34 core/search/batch source pins. Exact initial-state winner, lexical DFS.
Ceilings unchanged:300,000 uncached nonterminal states,6,000,000 generated choice
transitions,1,000,000 peak retained proof arcs,16 MiB total saved output,1,800
process-CPU seconds across full diagnostic. Separate format and raw run namespace.
First exhausted limit UNKNOWN with null winner/proof; external interrupt failure.
Complete result requires independent certificate verification before persistence.
Exclusive claim/registration/result-or-failure/receipt; no reuse/overwrite/retry.
May run during the frozen full-suite wait; still not accepted before regression.

This is a new search-method experiment, not a rerun/resume of Plan34 or extra
capacity for it. Count1 max; no additional boards, policy tournaments or further
potential tuning based on the result. Future work must keep both observations.

## Exit and preservation

- [x] User continuation; archive accepted Plan34, fix new method and budgets.
- [x] Independent mathematical gate for strict potential and cut completeness.
- [x] Implement four new files and calibrate.
- [x] Independent source review, freeze; start one full regression.
- [x] Freeze/independently check manifest from production count0; execute once.
- [x] Receive actual exits; saved-only audit and Japanese findings/state/backlog.

Winning proof is not automatically fairness, fun or human readiness. No silent
tie rules, paid resources, site/UI, human trial, episode2 or scheduler created
by this plan. Preserve TILE handoff and protected Plan13/14 membership boundaries.

## Historical source freeze and execution checkpoint — 2026-09-09

Four new files974 lines. Source owner focused1/2:13 tests/0.017s/OK/actual exit0;
main integrated1/3:28 tests/0.101s/OK/actual exit0. Independent mathematical and
full source review PASS. Old202 pins unchanged;206 current Python pins frozen.
No source/test edits after freeze. Unused focused capacity is not a new task.
The only full regression started by13:44:39Z: session45358/PID38300.
Log/exit/pins under `/tmp/parity-forge-plan0035.myFUCn/`; actual finish pending.

Prospective manifest `experiments/proposals/plan0035-original-cut-potential-v1.json`
validated from production count0 and independently reviewed PASS before query.
Full definition, query and five ceilings match Plan34 exactly; sourcechat pin
unchanged. Only method format, new run id and the new seven-source pin inventory
change. Dedicated root `experiments/runs/cut-choose-potential-v1/` used once.

Query session27571/PID38366 finished actual exit0, recorded completion
13:46:38.413837+00:00. UNKNOWN/PROOF_ARC_LIMIT;229,343 nodes=potential checks,
1,301,149 transitions;peak1m proof arcs;95 cuts;68,218 potential leaves;
CPU19.913648s. Raw4 files/2,359 bytes, winner/proof/check null. Those leaves are
aggregate shortcuts, not saved individual proofs or an initial-state B proof.
Saved-only independent result audit PASS; no query replay or proof re-execution.
Old query UNKNOWN and source pins unchanged. Never poll/restart finished27571.

[Findings](../../../experiments/reports/0035-cut-potential-findings-ja.md),
[exit receipt](../../../experiments/reports/0035-diagnostic-exit-receipt.json),
[method record](../../../experiments/reports/0035-method-registration-ja.md).
Permanent query logs/exits and206 pins: `experiments/reports/plan0035-acceptance-evidence/`.
The new method did not resolve the initial game within the unchanged ceilings;
no general efficiency, fairness, depth, fun or human-readiness conclusion follows.

To honor continuous-work intent, a same-task30-minute heartbeat
`parity-forge-plan35` was created through the app after source/query checks.
It follows only pending full-suite completion and saved-evidence acceptance or
failure, stays quiet while unchanged, then deletes itself. OpenAI Docs informed
setup; local PC/app must remain on. No new experiment/source edit/query retry or
replacement scheduler is authorized by this finite follow-up. The earlier
"no scheduler created by this plan" excludes implicit creation; this is the
subsequent explicit execution mechanism for the user's continuing-work intent.

## Historical quiet monitoring checkpoint — 2026-09-09T14:24Z

Full-suite PID38300 is still running at39:33 elapsed, with no actual final
summary or exit marker. Log has reached the public master-domain differential
test. All206 frozen Python pins matched, verification exit0. No test, solver,
cut enumeration, game, proof replay or source/test change was launched. Technical
acceptance remains pending; continue the same finite follow-up without an
unchanged-status notification. Completed query27571 was not polled or rerun.

## Historical quiet monitoring checkpoint — 2026-09-09T14:55Z

Full-suite PID38300 is still running at1:10:39 elapsed; no final summary or
exit marker. Log has progressed to typed-occupancy canonical-skeleton tests.
All206 frozen Python pins match, verification exit0. No test, solver, cut
enumeration, game, proof replay or source/test change was launched. Acceptance
remains pending; keep the same quiet finite follow-up. Finished query27571
was not polled or rerun.

## Final acceptance — 2026-09-10 JST

The single full suite45358/PID38300 completed1,503 tests/5,374.197s/OK(skipped2),
actual session and shell exit0. All28 new tests ok (potential13/batch15; expected
CLI fixture error followed by next-line ok). No rerun or source/test edit.
Current206 pins, old202 pins, manifest7/chat/wire/registration/result/receipt
match. Independent saved-only evidence audit and final copy/receipt/report audit
PASS. Five permanent evidence files byte-match their originals. Old Plan34 is
unchanged. No solver, cut enumeration, proof replay or game was added at closeout.

[Acceptance](../../../experiments/reports/0035-acceptance-ja.md),
[full-suite receipt](../../../experiments/reports/0035-full-suite-exit-receipt.json).
Full-suite SHA25611afb2f547c8efb20b6377b78c602b164bd1643644b11ddd03ddfd498221243e.
15:49:00Z is the completed-evidence observation checkpoint, not process end time.
Original result remains UNKNOWN/PROOF_ARC_LIMIT;68,218 is an aggregate only.
The fixed-budget resolution target was not met; no general method/game-quality
claim, silent winner rule or fairness/depth certificate is made.

Both45358 and27571 are finished; never poll/restart them. The app confirmed
deletion of `parity-forge-plan35` at2026-09-09T15:53:16Z after final record audit.
Only the completed follow-up was deleted; task/evidence remain. OpenAI Docs
informed closure. No new research unit, budget, query, UI, human trial or scheduler
is launched. Keep this completed plan as the sole current record until a separately
scoped unit exists. Historical pending statements above do not override completion.
