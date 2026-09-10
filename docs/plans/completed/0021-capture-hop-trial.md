> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan0021 — Small capture/hop trial

Completed2026-09-06: technical evidence ACCEPTED, game REJECTED. Actual full
regression1285 tests/5162.002s/OK(skipped=2),28226 exit0,PID90340gone; independent
172-pin/source/log auditPASS. See experiments/reports/0021-acceptance-closeout-ja.md.
Earlier checkpoint text below is historical, not a current instruction to wait.

## Status

2026-09-06 latest user direction supersedes the Site extension below: continue
research until a rule set merits human attention; Site work and human promotion
are PAUSED. A source-only universal A-first win by ply7 was found and independently
verified. See experiments/reports/0021-short-win-proof-ja.md. The provisional
trial recommendation is WITHDRAWN; raw flags/UNKNOWN remain immutable. No more
sampling or exact budget for this rejected A-first definition. Next bounded
source-only work considers at most two distinct next designs before registration.

User-authorized product extension (2026-09-05): build a mobile-friendly website
titled キャッチアンドジャンプ with local AI, shared-device friend play, and
online friend rooms. This supersedes the earlier no-additional-interface/network
restriction for this product work only; the registered scientific schedule and
raw results remain frozen. Site source has a separate Git root at
sites/catch-and-jump, excluded from the research repository. Web rule parity,
bounded AI and concurrent-room correctness are product tests, not new discovery
evidence. No added sampling, exact budget or quality claim. Public audience
requires a distinct access approval before changing the private default.

PILOT_COMPLETE / FULL_REGRESSION_RUNNING / TRIAL_RECOMMENDATION_WITHDRAWN.
Immutable registration is the version at
07baa83445f8ecd4ec045490054e328549a66593. Later progress notes do not amend it.
Plan20's1274-test full suite and independent source/evidence
checks succeeded; its acceptance closeout is recorded. The fixed capture/hop
pilot and saved-only audit are complete; the new full regression is pending.
No new platform, engine or agent algorithm.
The user requests continued existing-method work until a game is available.
Human trial availability and evidence of deep/enjoyable play remain distinct.

## Fixed definitions and hypothesis

Use exactly the two canonical wires in
experiments/proposals/capture-hop-full-ranks-v0.json:5×5, A5 on row0/all columns,
B5 on row4/all columns. A uses forward three-vector MOVE_CAPTURE/REACH_BOTTOM;
B uses opposing forward three-vector HOP/REACH_TOP. A-first and B-first are
separate conditions, never pooled. No generated extra setups, retries/backfill.

Expected definition hashes, in order:

- A-first a5e674e625aa0d2cac9858ef288e96d68ca68799801d7a4e8d12dc29139efe4c.
- B-first 699e3053d0e44615c0e41031097ae26b89deeb09128596c1039736fb5498a639.

The existing HOP steps into an adjacent empty cell or jumps one adjacent
friendly/enemy piece into an empty in-bounds cell; it neither captures nor
chains jumps. A capture versus B overtaking can require different responses
without Plan20's immediate pusher recapture. This is a designed development
pilot, not untouched confirmation or a causal comparison against Plan20.
Definitions were exposed by source reasoning/static parser checks before this
registration. Mechanical pair/goals are outside the public old-six regions,
including role swap; no old Plan13/14 member or evidence was consulted.

## Universal termination and known limits

Phi=sum_A(n−1−row)+sum_B(row) is nonnegative. A step lowers it by1; capture
also removes a nonnegative B distance. B step/hop lowers it by1/2 and moves no
other piece. Phi0=40, DSL cap41 strictly exceeds the natural bound. Every legal
path therefore has one finite A/B winner, never PLY_LIMIT. Independent
source-only review confirmed the theorem, semantics and the documented B-hop
response to a single advancing A. That response is not a universal B strategy.

B cannot remove A. A's foremost piece can always advance/capture in a
nonterminal position, so A cannot lose through immobility; B needs REACH_TOP.
Both goals and capture/hop are functional, but no claim is made that this
asymmetry is balanced, difficult or enjoyable. There is no known general
short-win proof for these two5×5 conditions; absence of a found proof is not
hardness certification. Do not treat solver exhaustion as passing D-057.

## Fixed, token-free computation

For A-first then B-first:

1. One existing exact solve at100,000 states.
2. Profiles(0,0),(2,2),(3,3), each seeds0..3, using unchanged random or
   terminal-only minimax:12 games per first. Fresh agents each game with
   100,000 cumulative nodes per role/game.

Total26 attempts:2 exact/200,000 states maximum and24 games/3,200,000 charged
search nodes maximum. Run the fixed schedule even after an easy exact result;
no added seeds, deeper retries, cap increases or result-selected definitions.
Preserve each attempt before execution and each result/prefix afterward.
Existing play_one/exact_one provide one game-prefix replay each, one external
PV replay per successful exact, zero PV replay for censors. No extra replay
is needed in the new wrapper or saved-artifact audit. Censors are UNKNOWN;
unexpected errors, source drift, draws or theorem-bound violations preserve
the failed record/prefix and stop the remaining schedule. Started failed
attempts are distinct from unstarted; failed publication is never completion.

Report every fixed-first/profile cell separately. Exact completion is
TOO_EASILY_SOLVED. TRIAL_REVIEW_ONLY requires all12 games completed decisively,
both roles winning in the strongest depth3 cell, and an exact censor. This
prospective trial triage no longer requires mixed depth2 results: Plan20's
easy B-win/d2 A-sweep demonstrated that the shallow requirement was a poor
necessary condition. Do not revise any prior flags or claim improved fairness
measurement from changing candidate and triage together. Four seeds and
timeouts cannot establish fairness, depth or fun.

## Implementation and acceptance

Reuse the immutable Plan20 play_one/exact_one and atomic publication helpers.
New code is only scripts/plan0021_pilot.py, scripts/plan0021_play.py and their
two focused test files. Do not edit frozen src/research/old scripts/tests.
Tiny3×3 synthetic all-branch/censor/I/O tests execute outside the5×5 production
domain; static production load/hash checks are disclosed development exposure.
The console also uses a synthetic draw-capable3×3 control solely to verify that
an abnormal terminal is not reported as a win; that control is not a candidate.

Commit code, this active plan and the proposal data before execution. Run from
a clean isolated worktree of that commit, passing the full registration hash.
Pin all tracked Python plus this plan and the proposal JSON. Create exactly
experiments/runs/plan0021-capture-hop-v1 exclusively; read back canonical hashed
records. Source checks occur before/after each attempt and at completion.
Old Plan20 worktree stays unchanged. Run one new full regression from the same
Plan21 bytes; formal technical acceptance waits for its actual Ran/OK and
saved/source checks. Do not confuse Plan20's completed suite with Plan21 coverage.

## Conditional local trial, not a discovery certificate

After the fixed pilot and saved-only audit, manually inspect any trial flags
for known short wins or dead goals. If one remains, expose its terminal
interface to the user, choosing A-first first if both qualify. Use
PYTHONPATH=src python3 -m scripts.plan0021_play --first A|B --human A|B.
Default human roleA; first must be explicit. The existing depth3 AI gets a
fresh20,000-node budget per decision and deterministic seed0. This per-decision
trial budget is different from the experimental per-game allowance and must
not be mixed into the fixed scientific schedule. The interactive trial is
unsaved, unquantified exposure; no automatic demonstration games are added.
Opening at a user's input prompt is allowed while full regression is pending
only with an explicit provisional label. q, EOF or budget failure is an
interruption, not a game draw or recorded winner. No network, outside
participants, publication, paid resources, or additional generic interface.

If no flag survives, report that honestly and close this bounded study after
verification; do not weaken its conditions to manufacture a game. New distinct
ideas need their own small fixed scope. A surviving trial is not a claim that
professional-level depth, lasting enjoyment or all project conditions are met.

## Preparation checkpoint (historical, before registration)

Root's combined11 focused tests passed in0.280s, OK. Independent review found
no blocking runner issues; root reviewed the console and tests. No production
game/solve/replay or console initialization has occurred. Registration and
execution remain gated on Plan20 acceptance.
That prerequisite has now been satisfied. The subsequent commit containing
these reviewed files and this active plan is the Plan21 registration. Pass its
full40-hex hash explicitly; only one production run is authorized.

## Execution checkpoint — 2026-09-05 23:29 JST (historical start)

Clean isolated worktree /tmp/parity-forge-plan0021.xObcys/checkout at
07baa83445f8ecd4ec045490054e328549a66593. Pilot session82592/PID90336 and new
full suite28226/PID90340 started23:29:16–18 JST. Logs:
/tmp/parity-forge-plan0021.xObcys/pilot.log and full-suite.log. Both are running.
No acceptance or new game quality claim. Do not modify this worktree's source,
tests, plan or proposal data, and do not restart or duplicate either command.
Plan20 suite80972 is complete and must not be polled again.

## Current checkpoint — 2026-09-05 23:44 JST

Pilot82592 exited0. All26 scheduled attempts completed:24 decisive GOAL games
and2 exact UNKNOWN at100,000 states, no unstarted attempts. A-first has A3:B1
in each depth0/2/3 cell and TRIAL_REVIEW_ONLY; B-first has2:2/4:0/4:0 and NO_FLAG.
No schedule, threshold, raw label or budget was changed after registration.
Independent saved-only audit passed56 envelope hashes,172 registered/source
pins, copied-run bytes,26 attempt/result pairs,24 single-prefix replays and
2 zero-replay censors, all6 cells/flags. No engine, solver or replay rerun.
Limited source/saved-trace review found no new short universal win or dead goal;
absence is not proved. Both goals, A capture and B hops are observed in records.

The A-first trial is available through docs/PLAY_CAPTURE_HOP_JA.md. Its actual
console was started with humanA, reaching13 legal choices and the input prompt,
session46437,0 plies/0 AI decisions. App-panel opening returned queued; display
is not yet confirmed. No automated demonstration or recorded human game.
Trial availability is provisional and is not D-057/fairness/fun certification.

Full suite28226/PID90340 is still active (elapsed15:21 at23:44 JST). Await this
one suite's actual Ran/OK/exit and a final registered-byte check before technical
acceptance. Never restart the pilot, add games/solves/replays or edit the isolated
registered worktree. Findings: experiments/reports/0021-capture-hop-findings-ja.md.
