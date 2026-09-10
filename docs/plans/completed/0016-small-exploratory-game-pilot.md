> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan 0016 — Small exploratory game pilot

## Status and purpose

Preregistered implementation and calibration scope, 2026-09-05. The user asked
to accelerate discovery. Plan 0015 is closed as `BREADTH_FLOOR_NOT_MET`, with
its partition unexecuted and its 1,177-test history checkpoint accepted at
`1fe53927c`. This is the sole active plan.

Question: in a small outcome-blind sample spanning different goals and initial
contact, are there fixed-first-player games where both roles win under both
depth-1 and depth-2 equal-policy play? Which apparent balance instead vanishes
with greater or one-sided search? This is exploratory diagnosis, not a fairness,
human-skill, strategic-quality, novelty, or enjoyment certification.

Do not implement the all-strata partition, a standalone TABLE framework, a new
DSL/agent family, terminal-blind BFS, or generic evidence infrastructure. Reuse
the frozen public compiler, initial predicates, engine, random policy, and
terminal-only depth-1/2 search. Add only a small selector, trace-preserving game
loop/summary, runner, and focused tests outside frozen `src` and pure `research`.

## Fixed population and selection

Reuse the single saved Plan-0015 compact report, authenticating its raw SHA-256
`fa7daf48992f2b186fd980d42f670beda651b1adc7fe4c1fb62b67d1fdc05f97`
and publicly reconstructing it once. Never rerun its census builder. Retain
all 109 semantic classes in coverage accounting, including zero supply. The
new sample is conditional on already observed static counts, not a new census
or an independent confirmation of that static evidence.

The 24-carrier ceiling derives from six unordered goal pairs (from
CONNECT_EDGES, ELIMINATE, REACH_EDGE) × two contact classes × two slots. Traverse
goal pairs lexically, CONTACT before SEPARATED, and slots 0 then 1. Eligible
means exactly the unchanged Plan-0015 initial predicate and target contact.

Within each macro stratum, collect all semantic classes with positive saved
eligible supply there. Order them by the semantic rank below; assign the first
two to the two slots. If only one exists, assign it to both slots; if none,
retain both vacancies as STATIC_ZERO. Never choose another class because the
assigned class's bounded sampling fails.

For each slot, order its positive-supply skeletons by the skeleton rank below
and visit them round-robin for at most 64 attempts. On the kth visit to a
skeleton, cycle through its positive-supply resource pairs in lexical order.
Visits are zero-based: skeleton index = attempt % S; resource index =
floor(attempt / S) % R_s for S skeletons and R_s pairs on that skeleton.
Order the nine cells by the cell rank below, take the first A_count cells for
A and the next B_count for B, sorting each owner's coordinates. Canonicalize
under the authenticated skeleton's exact D4 stabilizer using canonical setup
bytes, not hashes. Use only public compiler and prepared snapshot APIs.

All ranks use SHA-256(domain UTF-8 ending in one NUL byte || canonical JSON
UTF-8), canonical JSON with sorted keys, compact separators, ensure_ascii=False,
allow_nan=False, no newline. Domains and exact object keys are:

| Domain suffix after `parity-forge:plan0016:pilot:` | Object |
| --- | --- |
| `semantic:v1\0` | goal_pair, contact_class, semantic_hash |
| `skeleton:v1\0` | goal_pair, contact_class, slot, semantic_hash, skeleton_hash |
| `cell:v1\0` | goal_pair, contact_class, slot, attempt, skeleton_hash, cell |

Goal_pair is the sorted two-string array; cell is row-major integer 0–8;
slot/attempt are zero-based exact integers. Skeleton_hash is the saved canonical
role-neutral skeleton identity; semantic_hash is the saved role-neutral
semantic identity. Break hash ties by the canonical object bytes.

Accept the first static-eligible, target-contact, nonduplicate carrier in each
slot. Compare exact/D4/global-alpha-role identities of both first-player members
against earlier accepted carriers; duplicates consume attempts. Keep every
attempt's source coordinates, static reasons/contact, and disposition. Missing
after 64 attempts is BOUNDED_SAMPLE_EMPTY, not proof of absent supply. Do not
backfill vacancies, add attempts, rank by supply magnitude, or inspect outcomes
while selecting. Maxima: 1,536 static judgments and 48 accepted base DSL wires.

## Exposure boundary

The old six Plan-0013 semantic regions and all their role images remain excluded
by the frozen compiler; its candidate/evidence members remain unopened.
The accepted 66-source legacy projection has only schemas 1–3; the seven pinned
calibration fixtures and separately pinned eighth fixture have horizons 1–4.
The new compiler fixes schema 4 and horizon 18. D4, role exchange, and global
piece-label normalization preserve these fields, so these named regions cannot
be mechanically identical. Verify these invariants and fixture separation in
tests; record the accepted history projection root
`00973dcc6447697fae4639442bfe2fa93a5d0ff7c62f279688fa38dac1e2e3c9`.

This is exclusion relative to the named historical boundary, not a new exhaustive
runtime/source-fixture cutoff. Static/compiler exposure already exists and is
disclosed. Do not call this sample wholly unexposed, novel, or confirmation.
New integration tests use the existing short-horizon fixtures, not actual pilot
members. The pilot manifest is fixed and persisted before any selected game is
played. Future outcome-informed iterations require another recorded version and
cannot overwrite this one; future confirmation needs its own exposure boundary.

## Fixed gameplay schedule and finite work

For every selected carrier, retain A-first and B-first as separate definitions.
For each, use all eight existing D4 transforms in the frozen enum order, seeds
0 and 1, and these ordered A/B policies in this order:

1. random/random;
2. terminal-depth1/terminal-depth1;
3. terminal-depth2/terminal-depth2;
4. terminal-depth2/terminal-depth1;
5. terminal-depth1/terminal-depth2.

Use fresh agents per game and one `random.Random(seed)` shared in ply order,
matching the frozen play_game convention. Terminal search has a cumulative
5,000-node cap per controlled role per game. The fixed 18-ply DSL cap remains
unchanged; no production exact solver runs in this pilot. Thus at most 3,840
games, 69,120 played plies, and 30,720,000 charged search nodes are scheduled.
These are work ceilings, not predicted runtime or independent sample counts.
All five policies run on the same set; weak outcomes never gate deeper cells.
Manifest order is carrier selection order, A-first then B-first, D4 enum order,
seed 0 then 1, then the five policy pairs above (innermost). Give every game an
ordinal before execution; a stopped suffix is therefore unambiguously not-started.

Preserve seed/orientation/policy/definition/first-player identity, actions, per-role
nodes, decision legal counts, distinct one-ply successor-position counts, and
terminal reason/winner. Compute distinct successor positions using side-to-move
and canonical pieces, excluding ply/terminal metadata; retain the actual terminal
result separately. At most 40 legal actions per position gives an additional
2,764,800 successor calculations, without depth-2 telemetry or new policy calls.
This counts decision-starts including a censored decision, not just played
plies; there are at most 18 decision-starts per game.

Search-budget exhaustion retains the action prefix, censor role/reason, node
accounting, and no winner; it is SEARCH_CENSORED, never a draw. Replay every
completed or censored prefix through the unchanged engine. An illegal action,
replay mismatch, input drift, or unexpected error stops the run with its partial
ledger retained. Do not replace a case or add seeds after a censor or failure.

## Summary and follow-up signal

Keep fixed first player × ordered policy × orientation rows, plus explicitly
descriptive across-orientation summaries. Report A/B wins, natural draws,
PLY_LIMIT draws, censors, not-started slots, lengths, choice/reconvergence
descriptors, and every denominator. Shared seeds/orientations are not independent
evidence; publish no inferential confidence interval or fairness score here.

A fixed-first-player condition is FURTHER_DIAGNOSIS only if all its scheduled
games complete, and both roles have at least one decisive win in each of the
d1/d1 and d2/d2 profiles. Keep draw rates and crossed-policy changes visible.
This flag is a deliberately permissive triage signal, not qualification. All
other conditions retain their complete observations; a negative sample result
says nothing decisive about unsampled classes or human enjoyment. Never pool
the two first players to satisfy this signal.

Finish when the fixed schedule finishes, even with zero flags. Produce a concise
Japanese report with DSL-derived rules and initial boards for at most three
flagged conditions (manifest order), or representative failure examples if none.
Do not tune/replenish inside this run. Any next strengthening or simplification
study must name the uncertainty revealed by these actual observations.

## Calibration, implementation, and acceptance

Before member selection or gameplay, focused tests and independent review must
cover the actual selector/runner/summary path. Reuse frozen tiny DSL fixtures
for known winning actions, depth sensitivity, GOAL at the last permitted ply,
PLY_LIMIT/repetition, initial no-action terminals, reconvergence, and censor
prefix preservation. Compare successful traces with public play_game and replay.
Include small count-table assertions for first-player pooled false balance,
all-draw, partial completion, role relabeling, and a nontrivial control; no
separate synthetic framework is required.

Preserve frozen src/research bytes. Proposed implementation paths are
`scripts/plan0016_selection.py`, `scripts/plan0016_play.py`, and
`scripts/plan0016_pilot.py`, plus three matching unittest files. No installation
or external dependency is required. Freeze source hashes and Git commit in the
manifest. The output path is exclusively created under
`experiments/runs/plan0016-exploratory-pilot-v1/`; never overwrite an existing
manifest, game record, or final summary. Interrupted work remains partial and
is not silently repeated. No new generic one-shot lifecycle is required.

Run the complete repository unittest command before accepting the code change.
After focused tests and review, the exploratory pilot may execute concurrently
with that full regression against unchanged committed code; its findings stay
provisional until the full regression passes. A later code defect requires a
documented correction/version, never a rewrite of the observed pilot records.

## Definition of done

- [x] Independent review of this fixed sampling/schedule/claim boundary; no
  unresolved P0–P2. Decision-start counting and exact iteration order clarified.
- [x] Minimal public-API selector, runner, and summaries implemented and reviewed.
- [x] Focused integration, arithmetic, censoring, and source-separation tests pass.
- [ ] Selected membership and complete intended schedule persist before gameplay.
- [ ] Fixed pilot finishes or preserves an explicit failed/incomplete record.
- [ ] Full tests pass before code/results acceptance; no frozen source changed.
- [ ] Japanese diagnostic report, state, backlog, and next evidence-based step.

## Pre-execution checkpoint — 2026-09-05

The three scripts and three focused test modules are implemented. All 42
focused tests pass. Independent selector, play, and runner reviews have no
remaining P0–P2 findings. Review caught and closed failed-decision node-counter
accounting and acceptance of a shortened saved schedule; regression tests cover
both. Read-only inspection reconstructs the exact registered manifest and
replays saved action prefixes without selecting members or calling a policy.
The runner also checks committed source pins after execution. No frozen src or
research file changed. Selection and gameplay have not yet run at this checkpoint.

Next: commit this source/plan, start one new full regression with a durable log,
and execute the fixed provisional pilot concurrently against those same bytes.
Do not edit source, tests, or this pinned plan while either process is running.
Track process/log locations and later observations in PROJECT_STATE.md; update
this plan after execution. The old 1,177-test regression is already completed
and must not be restarted or polled.
