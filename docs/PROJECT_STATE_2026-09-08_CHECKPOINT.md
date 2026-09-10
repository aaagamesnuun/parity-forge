> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Project state — preserved 2026-09-08 checkpoint

Historical snapshot, superseded by PROJECT_STATE.md. All former contents are
retained below, including unrelated dialogue notes and prior no-retry boundaries.

## Current phase

Plan0032 — ACTIVE / STAGE0_IMPLEMENTATION / DISCOVERY_NOT_REGISTERED /
DISCOVERY_GAME_COUNT_ZERO / HUMAN_REVIEW_FALSE. The user approved the strategy
with 「それで続けて」 on2026-09-08. Sole active plan:
[finite-space discovery loop](plans/active/0032-finite-space-discovery-loop.md).
See D-065. Plan31 is superseded before registration, not resumed or evaluated.

Current work is a new, isolated finite-space DSL/engine for TILE placement and
TRAIL movement with permanent origin closure. Both strictly consume empty
capacity; `NO_LEGAL_ACTION_LOSES` is explicit, no draw or rule-level ply cap.
Only six new Python files are allowed; historical source/fixtures/runs remain
unchanged. Core, bounded search and data-driven batch plus tests are the scope.
Stage0 has a4-active-hour/3-work-session boundary and one separate full suite.
The first stage1 cohort is at most8 definitions, frozen in a manifest before
discovery execution. No candidate, fairness or human-play claim exists yet.

## Prior strategic-planning checkpoint (superseded by Current phase)

2026-09-08 latest user direction: plan a wider discovery process, system
self-improvement and human/AI division. Mechanical asymmetry and D-055 are hard
constraints; the user explicitly reaffirmed no draws. Board size and extreme
rule simplicity are not hard constraints. See D-064 and the
[Japanese strategy and bounded roadmap](reviews/2026-09-08-discovery-reset-and-human-ai-loop-ja.md).
This is a planning-only checkpoint: no new implementation, experiment,
registration, solver call, candidate game or regression is authorized by it.
Older execution instructions below are historical and do not override this pause.

Plan0031 — PAUSED_FOR_STRATEGIC_REPLAN / NOT_REGISTERED /
PRODUCTION_COUNT_ZERO / HUMAN_REVIEW_FALSE /
FREEZE_METADATA_AUDIT_INCOMPLETE. Sole plan retained in the active directory:
[low-branching complete short screen](plans/completed/0031-low-branching-complete-short-screen.md).
Plan numbers are chronological frozen research units, not game versions, retry
counts or success counts; definition/protocol suffixes such as `v0` and `v1` are
separate artifact versions.

Plan31 fixed two existing-DSL structures and at most two data-only drafts per
structure. Three definitions were attempted with no replacement or backfill.
CELL-1 `zigzag-hop-two-hunters-v0`, hash
`8c07cc4a89981b2b1533cfafd12081f71c72c0f79835172765fa4b9a3fa8600a`,
passed canonical/freshness, D-055, goal/effect and branching checks in primary
and independent lanes. Its potential starts47 and strictly decreases, so every
legal play ends decisively before `max_plies=48`; all-reachable maximum branching
is5. Four A-goal/B-goal/HOP/capture prefixes were replayed once in each lane,
eight replays and68 transitions total. This is static admission only, not a
short-screen pass or fairness, hardness, fun or human-review evidence.

CELL-2 draft1 has a universal A win byply5 and both explicit goals are dead.
Its sole data-only draft2 repairs goal liveness but has a universal A win byply9.
Both were source-rejected before prefix replay, and the fourth possible draft was
never generated. Design-stage game, exact, solver, selection and BFS calls are0.
The previously recorded design SHA256 was
`b047936221304388f8c5b52dce94ed2274ab5c0492f0bfdadefb21e54b074555`.
A pre-registration metadata correction changed the design record bytes to
`ebd031581f37c6840a6e2d83a49f2d4d6d2bcf3fa03531b43f641039c9bbd850`;
the prospective proposal still pins the earlier digest. Cross-artifact freeze
acceptance is therefore incomplete. No production occurred under either digest.
Do not repair this by executing or silently treating the old pin as accepted.

The sole admitted definition is frozen unchanged in prospective proposal
`plan0031-low-branching-complete-short-screen-v0.json`, SHA256
`267bc27da094bc4e73babda31ee400538474e25cfe5d2cf2cc814d474b15a489`.
It fixes exactly11 slots: complete A7/B8 queries at97,655/488,280 nodes, one
exact100,000-state probe, then four T3/T3 and four T4/T4 games only if exact is
UNKNOWN. Ten seeds, order, gates and resource ceilings were prospectively fixed.
Runner implementation and registration are now paused at production count zero.
The remaining paragraph describes the old contract, not execution authority. UNKNOWN stays
unresolved, and every possible draw, PLY_LIMIT or winnerless result is technical
failure. See [design review](reviews/2026-09-08-plan0031-design-stage-ja.md).

Plan30 is COMPLETED / ACCEPTED as technical evidence and `NO_SELECTION /
HUMAN_REVIEW_FALSE` as its scientific outcome. Its sole run performed five short
queries, four UNKNOWN100k and one COMPLETE false at95,704, with51 gate closures
and no game/exact/replay/BFS. The sole full regression passed1,403 tests in
5,398.474s, `OK (skipped=2)`, exit0; log SHA256 is
`482a027b9db48e9605fc79c6cb5829275669cc9b88208142d0a73b9fb1d885bd`.
Independent closeout matched193 source pins,16 direct pins,114 publication
hashes and all116 isolated/main files. Never rerun or supplement Plan30. See
[technical closeout](../experiments/reports/0030-acceptance-closeout-ja.md).

Plan29 is COMPLETED / DESIGN_STAGE_CLOSED / OLD_SIX_OVERLAP / CELL4_SLOT_DRIFT /
NOT_REGISTERED / PRODUCTION_COUNT_ZERO / NO_SELECTION. Its materialized CELL-3 signature,
PUSH/REACH_EDGE versus HOP/REACH_EDGE, is in the public role-neutral old-six
closure. Its attempted CELL-4 also used HOP/CONNECT instead of the contracted
HOP/REACH slot. Root and independent checks agreed. Its own no-substitution
rule therefore closed the Plan before any registered production game, exact
solve, replay, AND/OR/BFS, script/test or full regression. The rejected definitions and
hashes are preserved; none is Plan29 selection evidence.

Plan28 is COMPLETED / GAME_NO_FLAG / TECHNICAL_ACCEPTANCE_FAILED /
FULL_REGRESSION_INTERRUPTED_BY_HOST_REBOOT. Its one pilot completed exit0: exact
UNKNOWN100k/replay0 and32 decisive games A7/B25; T3/T3 and explicit-GOAL gates
failed, so final48 stayed closed. Two saved-only audits remain valid. The only
registered full regression was still in progress at22:50:38 (1:06:32 elapsed,
1,103 log lines); the host rebooted at22:55:35, and no final `Ran`/`OK`/exit was
saved. The fixed no-retry rule closes technical acceptance without alleging a
test assertion failure. See [technical closeout](../experiments/reports/0028-technical-closeout-ja.md).
Latest user instruction (2026-09-06) pauses the requested website and returns to
research until rules merit human playtesting. A simple universal A-first win by
ply7 has now been found and independently verified from source only. See
[proof and rejection](../experiments/reports/0021-short-win-proof-ja.md).
Do not request human play or spend more game/solve budget on this rejected wire.
Raw Plan21 UNKNOWN and TRIAL_REVIEW_ONLY remain unchanged as historical outputs.
Plan22 is COMPLETED / ACCEPTED as technical evidence, with no human candidate.
Registered atfb55b2a24c867bf3978f8a45479e6cf2bed320c6. The single pilot68381/PID4885
and full regression1843/PID4889 started01:22:57–58 JST on2026-09-06 in
/tmp/parity-forge-plan0022.z3IT62/checkout. Logs: pilot.log and full-suite.log
in its parent directory. Pilot68381 has finished exit0. Never restart or poll it.
32 games:10 complete(A2/B8),22 UNKNOWN, all22 at A's100k role cap. Each base
cell is A1/B4/11censors. Exact UNKNOWN100k,0 replay. INSUFFICIENT_EVIDENCE,
33 of129 attempts;96 remaining gate-closed.
Saved-only independent auditPASS:70 envelopes,68 publication hashes,176 pins,
all12cells/schedule/replay/source checked. Main has one byte-identical raw copy.
See [Japanese findings](../experiments/reports/0022-link-hop-findings-ja.md).
No inference of unfairness/hardness from censors, no added budget or replay.
Full suite1843 finished exit0:1298 tests/5269.359s/OK(skipped=2),PID4889gone.
Log SHA25645ce388eee4302adeadeeea498d349dcbd7ffa9507be7bd2a3d97ae1b8af544f.
Independent registered-source/log/main-run auditPASS. Never poll/restart any
Plan22 execution. See [acceptance](../experiments/reports/0022-acceptance-closeout-ja.md).
Independent frozen pipeline reviewPASS. Bounded source-only5-move detour/race
review found neither proposed universal conclusion valid; not an absence proof.
Candidate: link-hop-three-guards-v0.json, A-first5x5 PLACE/CONNECT
versus3 HOP/REACH_RIGHT, hash2ce75c6ef9e4abd5ab4401469a4a3be62a22b29a9e7c314be75bc324015ffc4e.
Empty-cell consumption proves decisive termination by39<cap40. Static
parse/hash/public-region checks and bounded source review passed before the first
production execution. Known short single-B predecessors were rejected.
See [design exposure](reviews/2026-09-06-link-hop-three-guards-ja.md).
Plan22 allows at most1 exact100k and128 games,100k nodes/role/game, with fixed
gates for self-play bias, cross-policy robustness, both-role search benefit,
simple-policy resistance and bounded tactical-choice witnesses. Not a human
fairness/hardness/fun certificate. Do not promote shallow mixed wins or UNKNOWN.
Combined13 focused tests passed in2.142s, exit0. Root final source review and
independent recorder/protocol review passed; the four new Python files are frozen.
The existing30-minute same-task heartbeat remains ACTIVE and was updated through
the app to this latest instruction, no duplicate and no stale Plan16/replay scope.

Plan23's source-designed three-runners-one-hunter-v0.json,
hash1fc21f944747c73dc3cea82a5099849901068171331a49d152e69c37b527bd4b.
5x5/A-first,3 forward MOVE/REACH_BOTTOM vs1 all-direction MC/ELIM. It is outside
the public old-six signatures; no oldmember access. Root+independent proof:
decisive≤23<25, both goals functional, neither role can force a4-turn win.
Depth4 node upper bounds70956/64240 per role are below the existing100k cap.
was rejected before registration: two independent source reviews proved a
universal A win byA6. No production game/solve/replay/run/full regression.
See [proof](../experiments/reports/0023-short-win-proof-ja.md). Never execute it.

Plan24 fixed data-only repair adds a second orthogonal hunter:
three-runners-two-orthogonal-hunters-v0.json,
hashba966ffe27f3a9ceeccba083ecc23cfb25cb4ade831c206392eacd7de4219b76.
The≤23 no-draw and depth4 node bounds remain; the A6 split proof is blocked.
Bounded six-turn source review found no universal winner, not an absence proof.
Full-Moore two-hunter exceeds the fixed node guarantee; straight-only runners
give B a simple B5 win. Neither was executed. See
[design note](reviews/2026-09-06-three-runners-two-hunters-ja.md).
Independent prospective plan/wire and a second bounded strategy reviewPASS within
their limited claims. The latter refuted a simple permanent B-coverage invariant,
not B winning generally. Adapter7 synthetic tests/0.100s/OK; semantics reviewPASS.
Screen10 synthetic tests/2.194s/OK and independent static reviewPASS. Root
combined adapter/screen17 tests/2.290s/OK. All four files were frozen with no
candidate execution, then registered at
10919fb9ccc4a03bafd408f172f69e61ac84e290. The single pilot session60252/PID19945
and exactly one full regression session13168/PID19946 started03:53:02 JST on
2026-09-06 in /tmp/parity-forge-plan0024.YBi3xF/checkout; logs are in its parent.
Pilot60252 finished exit0. Exact UNKNOWN100k; all80 games completed decisively,
no censor/failure, observed7..19plies. Ordered A wins: T4/T4 base10/16,
T3/T3 12/16, T4/T4 confirm6/16, T4/T2 8/8, T2/T4 2/8, T4/R 8/8,
R/T4 2/8. Only the final cell failed: B-side T4 won6/8 against random versus
the fixed7/8 requirement. All other numerical/witness gates passed. Disposition
NO_FLAG; no human candidate and no rerun/additional evidence. See
[findings](../experiments/reports/0024-two-orthogonal-hunters-findings-ja.md).
Independent saved-only auditPASS:166 envelopes,164 publication hashes,180 pins,
all81 attempts/cells/nodes/replays/bounds matched without drift. Full regression
13168 finished exit0:1315 tests/5452.647s/OK(skipped=2), log SHA256
59f567ea1cc056f725f930e0dc7699ae76f5e5050b2f29c310606e9ab6c893cc.
Independent registered-source/log/main-run auditPASS; all17 Plan24 tests passed,
180 pins unchanged and166 files byte-match. Plan24 is COMPLETED/ACCEPTED as
technical evidence, game NO_FLAG. Never rerun. See
[acceptance](../experiments/reports/0024-acceptance-closeout-ja.md).
Do not call this a fair/deep game or reopen rejected/censored wires.

The completed Plan25 candidate was:
three-runners-two-staggered-orthogonal-hunters-v0.json,
hash90b7f9e8f763183e8034b9c387ed8fa46f2150be21d044a135d8f3fefa3745ab.
It moves only one B hunter from(3,3) to(2,3), targeting Plan24's sole weak-side
gate miss without changing rules or bounds. Canonical/hash/public-region checks
and independent limited wire/strategy auditPASS:≤23, goals, A9/B8,
70956/64240, documented lines legal; no short universal result/dead goal found,
not an absence proof. It is outcome-guided development after aggregate and two
failed-cell traces. No game/solve/replay/test. See
[draft note](reviews/2026-09-06-three-runners-staggered-hunters-ja.md).
Fresh fixed seeds500/600 retain Plan24's exact same81-attempt gate. Reuse the
frozen Plan24 adapter; add only a candidate-specific screen/test. No generic
framework or shared source change. Prospective plan reviewPASS. Screen10
synthetic/mock tests/2.212s/OK, py_compile and independent static reviewPASS.
Root mechanical diff review and combined reused-adapter/screen17 tests/2.372s/OK.
Both new files were frozen with no candidate execution, then registered at
8b15e1ea44831e5af45d73f27f3c7c4af4be3e3b. The single pilot session16352/
PID35739 and exactly one new full regression session68935/PID35740 started
06:04:26 JST on2026-09-06 in /tmp/parity-forge-plan0025.gvR2Wy/checkout;
logs are in its parent. Pilot16352 finished exit0. Exact UNKNOWN100k; all32 base
games completed, no censor/failure, observed7..19ply/all GOAL. T4/T4 A7/B9
passed; T3/T3 A15/B1 failed the fixed A4..12 gate. Final48 are
NOT_STARTED_GATE_CLOSED. NO_FLAG; no human candidate, rerun, added seed, mirror
or threshold relaxation. Independent saved-only auditPASS:70 envelopes,
68 publication hashes,182 pins and all schedule/results/replays/nodes/bounds.
See [findings](../experiments/reports/0025-staggered-hunters-findings-ja.md).
Full regression68935 finished exit0:1325 tests/5160.407s/OK(skipped2), PID35740
gone. Log SHA256 is
93bd4ca03d2f9296ed1c96ebe191537df420ce4ba6430e06a3d33593eb5fbefb.
Independent registered-source/log/main-run auditPASS: all10 Plan25 screen tests
and7 reused adapter tests passed,182 pins and68 publication hashes matched, and
all70 isolated/main files were byte-identical. Plan25 is COMPLETED/ACCEPTED as
technical evidence only; game disposition remains NO_FLAG. Never rerun its
pilot, exact, games, replays or suite. See
[acceptance](../experiments/reports/0025-acceptance-closeout-ja.md).

The completed Plan26 data-only candidate was
three-runners-two-forward-orthogonal-hunters-v0.json, hash
aed723e270cacd8bdfe3c87db22299d8ccf1045e63c0cebbd638d900d0491b94. It moves only
the remaining B hunter from(3,1) to(2,1), restoring horizontal setup symmetry.
Before execution, independent static review confirmed decisive≤23, both goals
functional, initial A9/B8, cumulative depth4≤70956/64240 and public old-six
exclusion. The disclosed bounded AND/OR check found no universal winner within
either role's first7 turns; this is not an absence, fairness or depth proof.
Focused17 tests and independent implementation/source/protocol audits passed.

Registered source is0bf342f04f833505706a8564755d29217cb3f6ff with184 pins. The
single pilot99923/PID50883 and full regression80914/PID50884 started08:20:11 JST
on2026-09-06 in /tmp/parity-forge-plan0026.JdpTKU/checkout. Pilot exit0: exact
UNKNOWN100k/replay0; all32 base games decisively ended by GOAL in7..19ply, with
no game censor/draw/failure. T4/T4 A12/B4 failed A5..11 and T3/T3 A13/B3 failed
A4..12, each by one A win. Thus `base_pass=false`, final48 are gate-closed and
disposition is NO_FLAG; no retry/addition/relaxation. Independent saved-only
auditPASS:70 envelopes,68 publication hashes,184 pins and all schedule/results/
replays/nodes/bounds matched. Main has one byte-identical raw copy. See
[findings](../experiments/reports/0026-two-forward-hunters-findings-ja.md).
Full regression80914 finished exit0:1335 tests/5416.084s/OK(skipped2), PID50884
gone. Log SHA256 is701b5dcbbca4b36dfe5c3fe47f74363271a8134ed8863230728b3c7c8f151597.
Two independent registered-source/log/main-run closeout checks PASS:184 pins,
68 publication hashes,70 canonical envelopes and70 isolated/main files matched;
tree digest9fa3ef1340b86d500435f8711aac4f000137b50a7487fd32d32f17de09e1128c.
Plan26 is archived as accepted technical evidence only; game remains NO_FLAG.
See [acceptance](../experiments/reports/0026-acceptance-closeout-ja.md). Never
restart or supplement its pilot, games, exact call, replays or suite.

A read-only public trace review before Plan26 closeout found Plan24–26's coordinate-only
runner/hunter adjustments dominated by three-runner relay behavior and strong
T3/T4 horizon parity; that narrow setup-tuning lineage is retired without a
claim that every runner/hunter game is impossible. The completed structurally
separate Plan27 candidate was:
three-currents-swap-push-v0.json, definition hash
aa3079277a9089aa8758fa04f0d81be09544af39ba9338524cf97e6f98490209, proposal
SHA256 24429c2c3f703367b0a1361f98eddf3c762c91f57e847518323968f2f5cc7269.
It is5x5/A-first/3v3: A SWAPs right/down to reach BOTTOM; B PUSHes up/left to
reach TOP. The integer potential starts54 and decreases by1..3 on every legal
action, proving one winner by54<cap55. Initial mobility is A5/B5, both goals and
both conditional effects have checked legal lines, and the public old-six test
is false in both role orders. Root bounded AND/OR found no A force by13ply or B
force by14 at28639/12681 misses; an independent salted action order reproduced
both false at25883/15895 misses. This covers only each role's first7 turns.
Two fixed pure B shadow policies have legal A counterlines at13/15ply; hybrids
remain unexcluded. Before registration, production game/exact/replay count was0.
The registered plan retained
the existing exact/base/final screen with fresh900/1000 seeds and added candidate-only
gates for realized SWAP/PUSH and T4 horizontal selections. Its prospective
definition/proof/protocol review passed. Candidate screen/test are implemented;
they derive effect evidence only from matching saved pre-action state and
selected/applied actions, count distinct COMPLETE games and leave every existing
cascade/gate intact. Root combined adapter/screen20 tests passed in2.342s;
independent runs passed20/20 in2.381s and2.318s. Implementation/protocol/source
audits PASS. Frozen hashes: screen1001a5d50cc23c22f3b436e2c5c5898dea88f33b6315cb54dc64f5826b3a7ac6,
test29edbcb7a69dcef17597ddac4202b0ec12ceca2f04d8744ab4d0d7f6255f8918,
reused adapter146342883ee512ea16f3b96da3cd4258323360217ffe724327906521633e9758.
Expected registration pins186. The source was registered at
ca3451bb478aed518e34ff5e69ad362f64771d69 and a clean re-read matched all186.
The detached worktree is `/tmp/parity-forge-plan0027.mTxbu8/checkout`.

A first shell command at18:27:31 JST failed at module import before `run_pilot`,
candidate load, output reservation or any exact/game/replay call. Two independent
reviews classify it as a preflight launcher failure, not a production attempt;
the preserved `pilot-launcher-failure.log` SHA256 is
63b0dfefcf188ac891442e6cd9e84a1ecd5673ae64920b7487ddc837066358e6. The first
and only production pilot session67283/PID71418 then started correctly at18:32:30
JST and finished exit0. Exact is UNKNOWN at100k with0 replay; all32 base games
completed decisively by GOAL in7..22ply with no game censor/draw/failure.
T4/T4 wasA12/B4 and missed its fixed A5..11 gate by one; T3/T3 wasA12/B4 and
passed at the A4..12 upper edge. Thus `base_pass=false`, final48 are gate-closed
and disposition is NO_FLAG. No retry, supplemental run or threshold change is
allowed. Independent saved-only auditPASS:70 canonical envelopes,68 publication
hashes,186 pins, the full81-attempt schedule, all33 saved attempts,48 closures,
495 state transitions and new interaction telemetry match. Main has one
byte-identical70-file raw copy. See
[findings](../experiments/reports/0027-three-currents-findings-ja.md).
The exactly one full regression session78528/PID70567 finished exit0:
1,348 tests/5,351.812s/`OK (skipped=2)`; PID70567 is gone. Log SHA256 is
107af4476fa1e6b6d2beaa1509cf47aa43ee2e56a53862838085b600fcbb7253.
Independent closeout audits PASS:186 pins,68 publication hashes,70 envelopes
and all70 isolated/main files matched; normalized tree digest is
11af60946eeb862387ffd820bd80b029ffbcafcc933ef6de57aeb6b109b7e7ab.
Plan27 is archived and must never be rerun or supplemented. See
[completed Plan27](plans/completed/0027-three-currents-swap-push-screen.md),
[acceptance](../experiments/reports/0027-acceptance-closeout-ja.md), and
[source review](reviews/2026-09-06-three-currents-swap-push-ja.md).

The fixed Plan28 candidate is
two-current-cross-weave-v0, definition hash
c84f8cf6c01adb1e13f0668dd97cfc75112f63c4e5b0dbae89a22ea8e6e3100a.
It is5x5/A-first/5v5: A right/right-down HOP with TOP-BOTTOM connection
versus B up/up-left PUSH with LEFT-RIGHT connection. Phi50 strictly decreases,
so every play has exactly one winner by50<cap51. Authoritative and independent
bounded AND/OR both found no A force through13ply and no B force through14;
reachable-state enumeration exceeded100,000 byply8. These remain limited source
screens, not fairness, hardness or fun findings. The implementation and190 pins
were registered at `b0d9b4b7840833ecbe564cbf81eba7ed4ad79a9e` after independent
review. The single pilot then produced exact UNKNOWN100k and32 decisive games,
A7/B25. H3/H3 passed A4/B12, but T3/T3 failed at A3/B13; explicit GOAL endings
also failed at A0/B1, while actual HOP/PUSH interaction passed. Therefore final48
are gate-closed and the game is NO_FLAG with no human candidate. Independent
saved-only audits matched70 envelopes,68 publication hashes,190 pins and all799
transitions. The exactly one full regression did not finish before the22:55:35
host reboot; no final summary or exit code survived. It is not retried, and
technical acceptance failed without changing the pilot result. Plan28 is
archived; Plan29 later closed at its own static admission gate, and Plan30 is
the current structurally varied design stage. See
[Plan28](plans/completed/0028-two-current-cross-weave-screen.md),
[findings](../experiments/reports/0028-two-current-cross-weave-findings-ja.md) and
[technical closeout](../experiments/reports/0028-technical-closeout-ja.md).

Plan21 is COMPLETED / ACCEPTED as technical evidence, game REJECTED. Actual
1285 tests/5162.002s/OK(skipped=2),28226 exit0,PID90340gone. Independent172-pin,
source/log auditPASS. [Closeout](../experiments/reports/0021-acceptance-closeout-ja.md).
Never poll or restart its finished pilot82592 or fullsuite28226. The new suite1843
covers the registered Plan22 bytes, not a repeated Plan21 regression.

Website preparation is preserved, unpublished and paused at sites/catch-and-jump
(ignored by the research Git). Site ID appgprj_6a9c2e806c8c8191a09aa182921017e4 is
saved in its .openai/hosting.json; reuse it if later authorized, never recreate.
Only the generated scaffold exists. No site build, source push, version or
deployment occurred. Install session91752 ended1 on dependency build-script
approval policy; do not bypass or continue it while Site work is paused.
Terminal trial46437 was closed with q at0 plies, exit0; no human game occurred.

The following Plan21 pilot checkpoint predates the independent rejection and
technical closeout. Its [archived plan](plans/completed/0021-capture-hop-trial.md)
is historical; running/wait instructions below are superseded by the current phase.
Plan20 is COMPLETED / ACCEPTED as computation/evidence:1274 tests/5150.027s,
OK(skipped=2), session80972 exit0, PID79233 gone, independent source/raw checks
passed. See [closeout](../experiments/reports/0020-acceptance-closeout-ja.md).
Never restart its suite, pilot, games, exact calls or replays.
Registered at07baa83445f8ecd4ec045490054e328549a66593. Pilot82592 exited0;
full suite28226/PID90340 remains running. They started23:29:16–18 JST in
/tmp/parity-forge-plan0021.xObcys/checkout. Logs are pilot.log and full-suite.log
in its parent directory. Do not poll the finished pilot or duplicate any run.
All24 games were decisive; both exact calls are UNKNOWN at100,000 states.
A-first is TRIAL_REVIEW_ONLY (A3:B1 in each4-game depth0/2/3 cell); B-first is
NO_FLAG. Independent saved-only audit passed56 envelopes,172 pins,26 attempts,
single-prefix replay accounting and all6 cells. Limited source/trace review
found no new short universal-win proof or dead goal, not a proof of their absence.
See [findings](../experiments/reports/0021-capture-hop-findings-ja.md) and
[playable Japanese guide](PLAY_CAPTURE_HOP_JA.md).
At23:44 JST the A-first/human-A terminal was launched to the initial input
prompt (session46437),13 legal choices,0 plies/0 AI decisions. No automatic demo
or extra research game. App-panel opening is queued, not confirmed visible;
the guide includes the standalone command. Trial is unsaved and unquantified.
Immediate next action: let the same full suite28226 finish, inspect actual
Ran/OK/exit and registered bytes, then record technical acceptance. At23:44 JST
PID90340 was still active, elapsed15:21; no final test result yet.
Combined11 focused tests passed in0.280s, OK; independent code review is clean.
Do not equate trial availability or censored exact analysis with certified depth,
fairness, fun, or fulfillment of every project condition. No added fixed games,
solver calls, replays, higher caps, new platform or compulsory human feedback.

## Plan20 completed background
User moved new-method work to another task (D-058). Plan19 is superseded here,
without implementation. This task prioritizes concrete playable candidates using
existing algorithms, not a generic workflow or method-comparison platform.
Registered at637c9ae144be5353343234697120e631d1a64d4e. The fixed pilot and exactly
one full regression started21:52:57–59 JST in a clean isolated worktree.
Root's combined15 focused tests passed in0.914s, OK; independent review is clean.
Pilot99694 finished exit0; saved-only independent audit passed. No qualified
game:120 decisive games, exact2 complete/4 UNKNOWN, REVIEW_ONLY0. A separate
short-strategy proof also rejects one UNKNOWN. See
[Japanese findings](../experiments/reports/0020-directional-race-findings-ja.md).
Its suite and acceptance have now completed; older running-status paragraphs
below are historical checkpoints, not instructions to poll or restart it.
During that completed wait, a data-only next candidate was prepared:
[capture versus hop, full home ranks](reviews/2026-09-05-capture-hop-next-candidate-ja.md).
Two5×5 fixed-first drafts passed static DSL/hash/potential/public-region checks.
No new source/test code, games, exact calls or replays were executed for them.
Independent pre-execution review passed before Plan21 registration. Those
unplayed-draft descriptions are historical; current Plan21 status is above.
Termination is proved but depth is not.
Plan18 is COMPLETED / ACCEPTED as computation/evidence and archived. See
[acceptance closeout](../experiments/reports/0018-acceptance-closeout-ja.md).

D-055 is mandatory: every legal play must terminate finitely with exactly one
A/B winner. No draw, indefinite play or winnerless ending is allowed. This is
not zero sampled draws or a decisive minimax value. No human clarification is
pending. Historical draw-capable records remain unchanged and ineligible.

Plans 0016 and 0017 are now COMPLETED / ACCEPTED as computation and evidence,
not as games. The existing full regression ended: 1,219 tests in 5,123.653s,
OK (skipped=2), session43957 exit0, PID49691 gone. Independent review confirmed
no failures or source/test changes from eb9e53fcc. Do not restart it.
See [separate acceptance closeout](../experiments/reports/0016-0017-acceptance-closeout-ja.md).

## Objective and next action

Implement and test Plan32's minimum two-skeleton interface under its fixed new
source allowlist. Review semantics independently, freeze source, run the one
full regression and register stage1 data/budgets before any discovery game.
Use the [strategy review](reviews/2026-09-08-discovery-reset-and-human-ai-loop-ja.md)
as campaign context, not the old planning-only pause as an execution instruction.
Do not resume Plan31, old candidate studies or enlarge the agreed campaign.
The user needs no new routine technical clarification. D-055 remains mandatory.

The following Plan18–20 material is preserved historical objective context, not
the current queue.

The fixed run completed at registration d1364e81b:12 carriers/24 base definitions,
1,920 games,24 exact results, zero draw/censor/failure/unstarted. No further
selection, game, solver call or replay is authorized inside this schedule.
Root's40 focused tests passed in15.444s; independent code reviews are clean.
One registered read-only inspect passed (session14150 exit0). An independent
saved-artifact audit confirmed the registered plan,162 Python pins and24 exact
records, each with one external PV replay. Full regression passed1,259 tests
in5,171.636s, OK(skipped=2), session44075 exit0; independent checks are clean.
See [Japanese findings](../experiments/reports/0018-no-draw-game-findings-ja.md).

The user's strategic-review request is recorded in the
[continuation review](reviews/2026-09-05-continuation-review-ja.md).
User now endorses the small calibration/design/playtest direction and adds
D-057: simple rules must resist easy complete AI analysis. Use preregistered
solvers/finite budgets; exhaustion is UNKNOWN, not difficulty or quality proof.
Spend tokens on reusable development/design/batch review, not per-game play.
Existing Python core and legacy batch commands are operational, but old batches
use DSL1/old draw gates. Integration for current candidates, D-055/D-057 and
bounded review/method-efficiency evaluation is not yet implemented. No new
production schedule is authorized before the Plan21 registration succeeds. Plan19's
generic work will not be implemented here; its separate-task destination is
user-managed and has not been created or messaged by this task.

Plan20: A forward MOVE_CAPTURE versus B opposing PUSH, both reach the opposite
edge.4×4/5×5 × counts(2,3),(2,4),(3,4), B-first =6 fixed definitions.
Weighted distance strictly decreases on every legal action; cap=initial bound+1.
120 fixed games (depth0/2/3 profiles),20,000 nodes/role/game,6 exact calls at
100,000 states. No retries. Easy exact completion fails D-057; censor is UNKNOWN.
Known risk: pushing leaves B capturable by the pushed A. The fixed pilot is done;
no additional game, exact call or replay is allowed within its schedule.
Direct independently reviewed reasoning rejected all A-first counterparts
before registration: one A advances, immediately recaptures any pusher, and
arrives first. No production outcomes were used to narrow the draft.

C = CONVERT role, N = MOVE_CAPTURE role. Each C turn removes one N piece;
N cannot replace it. With m initial N pieces, natural play lasts at most
2m−1 plies with C first or 2m with N first, strictly below the18-ply cap.
Current compiler m≤3 means every selected game ends by ply6. This is a known
depth limitation, not a discovered fairness or fun result.

The fixed scope is eight ordered goal pairs (all three goals except excluded
E/E) × two outcome-blind setup slots: at most16 carriers. All CONTACT, at most
64 static attempts/slot, no backfill. Preserve all109 class accounting.
Exclude prior Plan16's46 definitions through exact/D4/global-alpha-role
identity and keep the whole old-six semantic firewall. New engine-executed
calibration fixtures use excluded E/E, not potential production members.

At most2,560 shallow-policy games and32 capped exact calls; all fixed-first
and ordered-policy results remain separate. The structural proof, exact winner,
finite-skill balance and human enjoyment are four different claims.
No new primitive or generic termination framework is needed for this pilot.

Actual selection:12 SELECTED/4 STATIC_ZERO slots;31 static attempts comprise
12 accepted/19 rejected. All109 class records remain present. Exact labels:
A_WIN7/B_WIN17,850 states. Gameplay:3,695 plies/11,853 search nodes;
655 GOAL endings/1,265 NO_LEGAL_ACTION, zero PLY_LIMIT.
Four raw shallow flags (carriers1 and4, each first player) remain immutable.
Both carriers' B/CONNECT goal is unreachable under either first player, proved
directly and independently from their initial row/column pattern plus declining
B count. These are dead-goal diagnostics, not rejection merely for exactB_WIN.
Do not promote a flag as fair or continue sampling this short region here.

## What is accepted and preserved

- Plan15: single census5,111,055 carriers /880,986 static-eligible.
  Nine of109 classes have no eligible supply. Scientific result
  BREADTH_FLOOR_NOT_MET; census COMPLETED; partition NOT_STARTED.
  Accepted checkpoint1fe53927c. Never repeat its census.
- History: 66 legacy blobs +7 fixture wires, 2,250 occurrences, 1,179 exact /
  1,175 D4 /1,175 neutral identities. Projection root
  00973dcc6447697fae4639442bfe2fa93a5d0ff7c62f279688fa38dac1e2e3c9;
  identity root e26fbd0d5a0db4a6e1cf462e0d3bc16385a769c647b35bdfdcbe6fc573d26b93.
  Old full regression1,177 tests/5,148.015s/OK(skipped=2) is also DONE.
- Plan16: 23 carriers /3,680 games, zero censor/failure/not-started;
  19,144 plies /112,438 charged nodes. Its one replay inspection and source
  verification passed. The archived preregistration remains byte-identical,
  SHA e689592ce9f279c4c3cb9089d88b979ea3c317cc912d5752583543d35b48e0aa.
- Plan17: one exact call at dc63a5dfb, DRAW/1,381 states/2,028 cache hits,
  one external PV replay18/PLY_LIMIT. Artifact/input/source audits passed.
  Result SHA378da30af6bb4762b6ce9a4286d13c2aede2c9cf8c614d2d3c9b3e4c1cc0b13b.
  No additional solve/replay is allowed; the draw-cycle continuation is cancelled.
- Their original PROVISIONAL raw strings are historical and must not be edited.
  The separate closeout records subsequent technical acceptance.

## Current best candidates

None qualified for human attention. Plan31 CELL-1
`zigzag-hop-two-hunters-v0` is preserved as an unexecuted candidate during the
strategic pause and has only
static admission; it has not passed the complete short screen, exact probe,
policy diagnostic, saved audit or full regression. Do not present it as a game
recommendation yet. Plan21 capture/hop A-first now has a simple
universal A win by ply7 and is rejected; its executable terminal is an archived
prototype, not a recommendation. D-055 holds but D-057 fails by direct strategy.
B-first never passed the initial trial triage and is not promoted.

Plan20's six conditions produced no preregistered review flag:
two easy exact completions, four exact UNKNOWN. One UNKNOWN (index3) has a
separately proved straight-line B win by ply7. The remaining three are uncertain,
not proved uninteresting or unfair; shallow AI shows substantial role sensitivity.
Plan18 satisfies the no-draw condition but does not establish
a fair, strategically rich, simple game. Its four raw flags have an unreachable
B goal. Plan16 raw triage flagged four first-player conditions.
Separate direct proofs rejected carrier0/A-first (A wins by ply5) and
carrier2/either first (B wins by ply3 or4). Carrier7/B-first legally draws
and fails D-055. These are preserved diagnostic failures, not games to rescue.
Other sampled classes are not thereby proved incapable of good games.

## Execution and process status

Completed Plan20 runs (do not duplicate or poll):

- Registered isolated worktree /tmp/parity-forge-plan0020.q9qwHS/checkout,
  commit637c9ae144be5353343234697120e631d1a64d4e. Its source/tests/plan stay fixed.
- Pilot session99694 exited0; /tmp/parity-forge-plan0020.q9qwHS/pilot.log.
- Full suite session80972 exit0, PID79233 gone;1274 tests/5150.027s/OK(skipped=2).
  /tmp/parity-forge-plan0020.q9qwHS/full-suite.log,
  SHA74221e31227edf347bcae9730eebf51a769a7cbb0e32140113dd06a7a9f17c81.
- Both started21:52:57–59 JST; only full suite is still running at22:05 JST.
  No acceptance yet. Do not poll the completed pilot or start a duplicate suite.
- Raw output experiments/runs/plan0020-directional-race-v1 was copied once from
  the worktree to shared checkout, diff -qr equal. Independent saved-only audit
  passed256 hashes,166 Python+plan pins,120games/6exact and30cells; no replays.
- Do not change or remove this worktree while its suite runs. Shared checkout
  documentation from the separate task remains untouched and does not affect it.
- Historical mid-run checkpoint: at22:38 JST PID79233 remained active at45:41.
  The run later completed as recorded above; never continue, poll or restart it.

The Plan18 full regression is DONE, started2026-09-05 19:32:38 JST:

- Source: d1364e81b775e1f693d8804719acf099a24154fc.
- Session44075, PID64445; /tmp/parity-forge-plan0018.JxQbr8/full-suite.log.
- Actual1,259 tests/5,171.636s/OK(skipped=2), session exit0, PID gone.
  Independent checks found no source or raw-run drift. Never restart or poll it.
- Log SHA256 1c7ed6d2e63a362a4fc4093e286a066c7a604646faf54a2bbfb40cd984d36fc7.
- Pilot session24296 exited0 at19:33:03 JST; log
  /tmp/parity-forge-plan0018.JxQbr8/pilot.log. Inspect session14150 exited0;
  /tmp/parity-forge-plan0018.JxQbr8/inspect.log. Neither is a current wait.
- Output experiments/runs/plan0018-no-draw-convert-capture-v1 is immutable.
  Manifest SHA a16c4ca84d8bc1bf88e528218b6ec5e622c68e73146a49c230931e8d0f943c64;
  summary SHA 8f1b1028031fed19c7ffc60222b766aeedd0e425533ca7b0c1e3093c5481ba62.

The prior completed log is
/tmp/parity-forge-plan0016-tests.VsEzwh/full-suite.log,
SHA a51d8d15b1d59230af5030a0fba399646ee74af83c67f0be535592fa37370c8b.
The older completed log is
/tmp/parity-forge-history-tests.ku8hkt/full-suite.log.
Do not poll or restart either completed session.

Historical pre-Plan22 checkpoint, superseded by Current phase: all earlier full
regressions through Plan21 were complete and Plan22 was not yet registered.
Never restart or poll old completed suites.
No duplicate runs, retries, cap increases
or new games/replays inside completed schedules. Raw provisional labels remain
unchanged. Plan18 acceptance/archive is complete; Plan19 was superseded unexecuted.
At that checkpoint, new-code ownership was only scripts/plan0022_* and
tests/test_plan0022_*. Preserve unrelated work from the separate task.

Same-task heartbeat Parity Forge 研究継続 (ID parity-forge), every30minutes,
must follow this latest state and sole active plan. It stays quiet on unchanged
non-actionable state. Follow Plan32's current stage and remaining budget; do not
resume Plan31 or duplicate a running/full completed suite or batch. The user's
continuation lifted the strategy-planning pause, not old-study no-retry rules.
No duplicate automation or automatic usage reset.
The computer and Codex app must remain running for scheduled follow-up.

## Boundaries, risks and human decisions

2026-09-08 current override (D-064): mechanical asymmetry and all-legal decisive
termination are hard requirements; the user explicitly retains no draws. Board
size and extreme simplicity are no longer hard limits. The strategy request
includes system-improvement and human/AI-division planning in this task. Older
separate-task, tiny-board and complexity-first wording below is historical where
it conflicts. Preserve all frozen studies and the protected Plan13/14 boundary.
No source, tests, proposal bytes or raw run data changed in this strategy review.

2026-09-08 Lean feasibility discussion: the user asked whether Lean could help
Parity Forge. Advisory recommendation is a small Lean4 verification layer beside
Python, first formalizing all-legal termination and decisive outcomes from a
decreasing potential, then possibly checking bounded-strategy certificates.
This is a proposal, not an adopted implementation or new candidate evidence.
Lean-model/authoritative-DSL/Python correspondence remains a separate obligation;
fun, practical hardness and UNKNOWN are not resolved by adding a proof checker.
No Lean code, dependency installation or candidate execution occurred in this
discussion; Plan31's frozen proposal, gates and production count remain unchanged.

Parallel new-method planning: the user requests iterative joint discussion of
an Astra idea/verification system. The [dialogue record](reviews/2026-09-05-game-generation-planning-dialogue-ja.md)
now records the user's clarified purpose: enjoyable skill development is central;
professional-shogi-player depth is aspirational, user/friends depth acceptable.
Asymmetry is an underexplored-space hypothesis, not a required role experience;
exact50/50 is optional. Operational depth metrics/AI budgets remain proposals.
Latest dialogue narrows the new verifier to bounded obvious-win screening, then
the user's own playtesting. Personal-taste elicitation and learning/transfer tests
are not required. A [discussion-only verifier draft](designs/bounded-obvious-win-screen-v0.md)
specifies short-win/simple-policy propositions and separate UNKNOWN results;
illustrative budgets are unregistered. Next discuss policy/evidence/work bounds.
2026-09-06 dialogue steering adds a prior design step: identify rule structures
that defeat simple universal strategies, keeping termination potential separate
from competitive advantage. These are untested generator hypotheses in the
dialogue record, not new gates or changes to the registered Plan24 study.
This updates future planning, not the existing-method Plan20 schedule or labels;
no implementation is performed by that dialogue. D-055/D-057 remain in force.

No human/resource blocker. Ask only for taste, paid resources, permission,
external publication/playtesting or irreversible choices, not routine research.
User answered the optional taste question: losing through one's own decisions
can invite replay because learning may allow a win next time. For now simple
rules and depth suffice as design direction. Raw wording is in HUMAN_PLAYTESTING.
This is tentative preference, not a playtest result or a new automated gate.
The chance-game example does not introduce randomness or relax D-055/D-057.
No further taste clarification is needed now.

Do not read Plan13/14 candidate/evidence membership. Do not rerun a census,
reopen old studies or change frozen src/research/fixtures. New scripts belong
outside the six-file pure research capability boundary.
Keep UNKNOWN censors distinct; exact A/B wins alone are not unfairness.
Under D-057 an easily obtained exact solution is a separate complexity failure.
Plan18's24 solved definitions/850 states do not meet the intended solving resistance.
Avoid shallow-policy false balance and combining two first-player conditions.

Directional forward-capture versus backward-push has a weighted-distance
termination proof and remains a possible separate next generator region,
not the default next step without considering the strategic review.
It is not authorized gameplay inside Plan18. TABLE frameworks, all-strata
allocation, new primitives, deeper agents, UI and human playtests remain deferred.

Earlier details are preserved in completed plans, immutable reports,
PROJECT_STATE_HISTORY.md, BACKLOG_HISTORY.md and decisions D-053–D-058.
