> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan0036 — Deliver a playable private trial, not another exact-solver loop

## Authority and outcome

2026-09-10 user explicitly asks to continue regularly until they can play a game.
COMPLETE / TECHNICALLY_ACCEPTED / PUBLIC_TRIAL_AVAILABLE.
Plan35 is accepted and archived, UNKNOWN preserved.
This new authority permits implementation, bounded validation, private Site
delivery and same-thread scheduled continuation through that actual delivery.
It does not require solving a finite perfect-information game before a trial.

### Access follow-up — 2026-09-10, D-074

User explicitly requests current and future game URLs work without login.
This supersedes the initial owner-only/publication restriction for the game Site,
not for private research, secrets or unrelated Sites. Native access changed from
custom to public (revision2), read-back confirmed. The same version1 and URL are
retained; fresh unauthenticated page/JS/CSS requests return200 without login.
Independent limited source review found no application auth gate or private-user
data read path. No code/build/redeploy/test-suite rerun or scheduler change.
Preference saved in AGENTS.md; actual record0036-public-access-receipt.json.
The private-only instructions/checkpoints below describe the original delivery.

Default: unchanged registered TILE7/B-first (A straight3, B L3); optional9/A.
Read-only independent readiness audit PASS for a clearly unvalidated short trial,
not fairness/depth/fun. No trivial universal strategy was found in the previous
limited review; absence of an optimal winning strategy is not claimed.
Every legal move consumes3 cells; no legal move loses. At most16/27 placements,
one winner, no pass/draw. Preserve exact DSL files and separate first-player rules.

## Delivery slice and acceptance

Reuse the unpublished private `sites/catch-and-jump` checkout and its project_id;
do not replace accepted Python or publish old withdrawn capture-hop candidates.
Title remains キャッチアンドジャンプ, clearly identify the trial as 直線とL字.
Build one Japanese touch/keyboard-friendly play screen: orientation, placement
preview/confirmation, legal-only moves, current role/turn, automatic unique winner,
restart, AI as either role, and local shared-device two-player play. Keep AI local,
deterministic and computationally bounded, without model calls per move.
Explain experimental status and that no optimal/fairness claim is made.
Online friend play remains a later feature, not a requirement for this first
user-playable milestone; do not imply it exists or contact external testers.

Acceptance requires DSL parity, terminal/illegal-move tests and complete bounded
functional traces, independent review, TypeScript/build success, and the required
project full unittest regression actual success (not merely started).
UI trace tests are implementation validation, not new fairness samples or an
episode2 replay. Record their explicit scope and preserve old raw labels.
No code source change after final source freeze; docs may record results.
If an actual bug requires changes, label the old validation version historical
and rerun only relevant checks plus required final regression; never mask failures.

Use Sites building/hosting skills faithfully. No browser interaction/visual QA
without an explicit user request for browser testing; non-browser tests/build
and first meaningful preview are allowed. No illustrative images needed for this
functional grid game. Private owner-only deployment only; changed/shared access
requires user authority. Reuse Site credentials safely; no paid upgrades/domains.

## Bounded work loop

Every30 minutes resume the same current task, read state/sole plan/backlog, inspect
existing work before starting anything, and complete the next concrete delivery
step. Prefer programmatic checks, no model-per-game research, no duplicate workers.
Complete useful work immediately in foreground too; the timer is continuity,
not a reason to delay or merely report status. Each active pass is a bounded
implementation/review step, normally<=20 minutes; long regression runs once and
is tracked across passes without busy polling. No arbitrary candidate expansion.
Do not stop just because a plan step or test finishes: continue through private
deployment, verified successful status, Japanese rules and usable URL handoff.
Notify only playable completion, a meaningful change/failure, or needed human
authority; remain quiet on unchanged machine waits. Delete this follow-up only
at the actual delivery endpoint, user stop, or a documented outside-authority
blocker. Do not create replacement schedules or repeat unchanged failure work.

## Checklist

- [x] Read current evidence; independent short-trial readiness review.
- [x] Preserve/close Plan35 and define this separate delivery authority.
- [x] Implement trial interface and local deterministic AI.
- [x] Rule parity / bounded functionality tests / independent source review.
- [x] Freeze source, build/typecheck and receive actual full regression success.
- [x] Save exact source, private deploy, verify terminal deployment status.
- [x] Deliver URL/rules/limitations; update records and delete continuation.

No old query retry, larger proof budget, hidden role/tiebreak repair, protected
Plan13/14 access, public publication, outside testers, usage reset or purchases.
The optional human's actual play and taste feedback are never fabricated.

## Completed delivery — 2026-09-10 JST

One full regression completed1,503 tests/5,289.039s/OK(skipped2)/actual exit0.
Independent final saved-only audit PASS:8 byte-matching permanent copies, receipt,
90Site/206Python current pins and old Python pins, DSLs, Site source/archive.
Both test workers are finished; no source change or rerun. Saved version1's exact
source was privately deployed after a fresh owner-only access check. Native
deployment status succeeded at2026-09-09T18:31:28.279853+00:00, actual URL:
https://catch-and-jump.realnuun.chatgpt.site .

Japanese rules/limits and URL were delivered. AI and same-device2-player, not
online friends; not fairness/depth/fun/human-UX certified. Background execution
skipped browser opening per Sites hosting. Dev server8279 stopped after hosting.
The app confirmed heartbeat `parity-forge` deletion at2026-09-09T18:31:58Z after
the actual URL handoff was ready. Task/source/evidence preserved. No replacement
schedule, next research unit, policy game or automatic human session started.
See experiments/reports/0036-acceptance-and-play-ja.md,
0036-full-suite-exit-receipt.json and0036-private-deployment-receipt.json.
Keep this completed plan as the sole current result/next-action record until
a separately scoped unit exists. The checkpoints below are historical.

## Historical execution checkpoint — 2026-09-10 JST

Same-task30-minute heartbeat created through the app: id `parity-forge`, name
`Parity Forge 試遊版を届けるまで継続`, ACTIVE. No duplicate remained. Keep it
through actual playable URL delivery, not merely full-suite acceptance.

Site source frozen at dedicated Git commit9f5dcc8e0de21235f6bea191133ee1b456d35ab3,
90 tracked source pins. Parent206 Python pins unchanged. Independent final source
review and saved-only source/log/6copy audit PASS. Typecheck/build/12 final Site
tests allpass, session42701 actual exit0,6 functional traces/107 transitions
matching Python legal sets/occupancy/turn/winner. Actual production worker bundle
tested non-browser. These are implementation checks, not fairness/self-play research.
Runtime24.19.0, existing package versions/lockfile retained; unfinished scaffold
allowBuilds choices resolved for its existing esbuild/sharp/workerd dependencies.
Local previewHTTP200; app opening returnedqueued, no stable visible tab id yet.
dev server8279 remains alive for hosting. No browser interaction/visual QA claimed.

The only required full regression78275/PID60198 started by2026-09-09T16:32:14Z,
logs/exit/pid/sourcepins `/tmp/parity-forge-plan0036.iiP5fd/`. Actual summary/exit
pending. Do not restart it. No source edit during freeze; receive actual result,
copy final log/exit, check both90 Site and206 Python pins and audit saved evidence.
Permanent6 completed logs/pins in experiments/reports/plan0036-acceptance-evidence/.

Site source push actualexit0 and save_site_version succeeded. Project
`appgprj_6a9c2e806c8c8191a09aa182921017e4`, saved version1 id
`appgprj_6a9c2e806c8c8191a09aa182921017e4~appgver_8eb312ab93b881919634348eb0607220`.
No deployment yet. Root's actual tool receipt is saved separately; the independent
local audit does not claim a separate remote query. Owner-only access verified
(owner/custom/1 account/0 external/0 groups); recheck before private deployment.
After full acceptance, use that exact saved version, verify deployment terminal
success and actualURL, provide Japanese handoff and delete this heartbeat. Do not
stop at the test boundary or silently promote saved-version status to deployed.
See experiments/reports/0036-playable-delivery-checkpoint-ja.md and
0036-saved-site-version.json. Existing non-browser Site does not add WebMCP tools.

## Quiet checkpoint — 2026-09-09T17:14:08Z

Full-suite PID60198 remains running at41:56 elapsed; log is in the public
master-domain differential test. No actual final summary or exit marker.
206 Python and90 Site source pins match, Site HEAD unchanged/working tree clean.
No new test/solver/game, source edit, deployment or scheduler mutation. Acceptance
is pending; continue the existing follow-up through actual private URL delivery.
No unchanged-status notification and no duplicate work during this machine wait.

## Quiet checkpoint — 2026-09-09T17:45:25Z

Full-suite PID60198 remains running at1:13:13 elapsed, now in typed-carrier
boundary tests. No actual final summary or exit marker.206 Python and90 Site
pins match (both hash checks exit0); Site HEAD unchanged/working tree clean.
No source edit, new execution, deployment or scheduler mutation. Continue the
same finite follow-up through completed regression and verified private URL;
the saved Site version is still not a deployed/handed-off game.
