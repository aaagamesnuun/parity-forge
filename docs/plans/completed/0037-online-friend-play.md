> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan0037 — Login-free online friend play

Archived 2026-09-10 on the user's new scheduled-research request (D-079).
The completed delivery and its historical stop boundary below remain unchanged.

2026-09-10 user explicitly requests online friend matches.
COMPLETE / TECHNICALLY_ACCEPTED / PUBLIC_ONLINE_DELIVERED.
Preserve accepted TILE7/B and optional9/A, AI and shared-device modes, public
login-free URL, existing source baseline and all research results. Archive Plan36.

## Scope

Create a private-by-link room on the public Site; share an invite URL; a friend
claims the other fixed role. No accounts, lobby, chat, ranking, payments or rule
changes. D1 is authoritative for seats and moves. Strong random seat capabilities
are separate from invitation capabilities; store hashes server-side, no token in
query/referrer/logs. Device-local credentials only; never store authoritative
game state solely in the browser. Validate every move on the server using the
unchanged game engine, enforce turn/role and optimistic revision atomically.
Bound rooms and retention; expiry/disconnection is an interruption, not a draw or
new winner. Reconnect, duplicate requests and polling must not rewind state or
apply one action twice. Preserve local AI and no-draw semantics.

## Work and acceptance

- [x] Implement D1 schema/migration, room API and online UI.
- [x] Focused server/client race, authorization and rule tests, typecheck/build.
- [x] Independent review and immutable source/evidence.
- [x] Receive and accept actual full research regression success.
- [x] Save/publish same existing public Site and verify real deployment success.
- [x] Verify login-free two-client flow without browser UI QA; deliver URL/guide.
- [x] New request: public GitHub handoff of only game rules/code, no research history.

Only root edits Site or operates Sites. Independent agents perform bounded
read-only review. Use Sites building then hosting, reuse installed components,
existing D1 binding and dependency versions. No browser interaction testing unless
explicitly requested. No experiments/fairness tournaments or old query reruns.
Python is unchanged; run the mandated full regression once while Site work runs,
pin Python separately and verify final Site source with its own final tests/build.
Do not claim completion before the actual results and working hosted room flow.

## Current publication — 2026-09-10 JST

D-076 follows explicit「オンラインで公開して」: release tested frozen Site version2
separately from pending regression of unchanged Python. Actual deployment succeeded
2026-09-09T20:15:35.158999+00:00, public/revision2 confirmed before deployment.
One hosted check completed2rooms42moves/46,926ms/actualexit0/session22520. Anonymous
page and online JS200. Independent postpublication saved-only auditPASS:103/206pins,
10 original/copy pairs, new hosted log/exit/receipt. No browser/human QA.
See experiments/reports/0037-online-publication-ja.md and publication receipt.
Dev52627 stopped actualexit0; public URL handoff queued. Do not restart dev52627,
poll finished22520, resave/redeploy2 or repeat hosted traces.

Full suite80276/PID80326 completed1,503tests/5,387.722s/OK(skipped2)/actualexit0,
chunk1928bc. At21:36:38Z the completed log/shell marker/session response agree;
PID absent. Observation timestamp is not process end time. No rerun.
Independent final saved-only auditPASS for12copies,206Python/103Site pins,
frozen SitecleanHEAD and saved/deployed/GitHub receipts. New full-suite receipt
and0037-acceptance-ja.md are saved. No pending computation or implementation.
The same30-minute tracker「Parity Forge 公開後の全回帰確認」fulfilled its purpose.
The app confirmed deleteStatus=deleted at2026-09-09T21:41:04Z. Task and evidence
remain. No replacement or new research. Keep this completed plan as the sole
current record until a separately scoped next unit is requested.

New user requests public GitHub rules/code-only repository for another analyst.
Prepare six-file standalone export with exact3 game source/DSL files plus derived
rules/API guide, executable example and unit-test code. No research/logs/history,
hosted DB/settings/credentials, app infrastructure or added license. No change to
frozen source. User confirmed public and completed browser login. Created
https://github.com/aaagamesnuun/catch-and-jump-analysis under aaagamesnuun.
Main581d9acebf5e6d8377953dc62b9847a68b3eefdc, exactly6files/2new commits; no old
history. Export8tests/example actualexit0, exact3game files unchanged; remote
tree and anonymous6raw-byte comparison PASS, UI Public/README/files verified.
Local-only receipt: experiments/reports/0037-github-code-only-handoff.json.

User fairness-method explanation uses existing records only: Plan32 I/L32games,
first-role strata and mixed-policy/weak-search limitations. No new evaluation,
GitHub research upload or change to this plan's full-regression task.
That remaining regression and independent acceptance are now complete above.

## Historical saved-only checkpoint — superseded by current publication above

Independent final source review PASS after fixing old poll404 overwriting a
successful activation and restoring saved pending guest through room-only URL.
Pure lifecycle/routing tests, not React/browser execution. Final28tests/build/
typecheck PASS, session18389 actualexit0,542.35525ms. Existing6 Python-matching
traces107transitions/production worker still pass. Local actualD1 HTTP2rooms,
7/B16moves and9/A26moves,42transitions,1,699ms/exit0. That check predates only
final client-only repairs; server/DSL/migration identical. No fairness samples.

19 Site files changed,786 additions25deletions. Dedicated frozencommit
7642e98a4fafa30821ac4c2dbf5f9dd6d9e98f6e;103Site pins and206unchangedPython pins.
Current sources match; Site clean. The source was pushed with actualexit0 and
saved version2, exact IDs in experiments/reports/0037-saved-site-version.json.
Local archive /tmp/parity-forge-plan0037.Vr5Mt5/site.tar.gz includes generated
drizzle migration/schema metadata. LiveDB native overview:zero user tables.
At this saved-only checkpoint no deploy yet; productionURL still served version1.

Full Python regression session80276/PID80326 started once and is running;
raw log/exit/pins /tmp/parity-forge-plan0037.Vr5Mt5/. Never duplicate/poll finished
Sitevalidation18389. Receive actual full completion; permanent evidence dir
experiments/reports/plan0037-acceptance-evidence/ currently has8 matching copies.
The original ordering (superseded by D-076) was: after full acceptance recheck
public access and deploy saved version2. On actual
succeeded run scripts/check-online.mjs at https://catch-and-jump.realnuun.chatgpt.site
once (only2 own test rooms, no token output) and anonymouspage, then provide guide.
No credential in URLs except invite fragment; never log seat/invite tokens.

The app created same-task30-minute `parity-forge` ACTIVE through actual online
handoff, following prior user scheduling preference and new feature request.
Quiet on unchanged waits; delete after actual hosted verification/URL or user
stop/outside-authority blocker. No next research unit or replacement timer.
dev server52627 remains through hosting then teardown. No browser interaction QA.
See experiments/reports/0037-online-delivery-checkpoint-ja.md and D-075.

Final independent checkpoint audit PASS:103/206pins,8copies,log/exit/DSL/source/
archive and saved2 receipt agree. No remote re-query by reviewer. At20:05:10Z
fullsuite PID80326 still running29:37, public master-domain test; no final exit.
No additional source edits or games. Same finite continuation remains active.
