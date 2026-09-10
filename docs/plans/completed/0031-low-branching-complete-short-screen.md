> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan0031 — Low-branching complete short screen

## Status and dependency

SUPERSEDED_BEFORE_REGISTRATION / NOT_REGISTERED / PRODUCTION_COUNT_ZERO /
HUMAN_REVIEW_FALSE / FREEZE_METADATA_AUDIT_INCOMPLETE.
Archived after the user approved the broader strategy with 「それで続けて」.
Plan0032 is now the sole active plan. No candidate or proposal is rerun.

2026-09-08 user direction pauses the old workflow for a wider discovery,
self-improvement and human/AI-division plan. Mechanical asymmetry and D-055
remain hard requirements; board size and extreme rule simplicity do not.
See D-064 and the [Japanese strategy review](../../reviews/2026-09-08-discovery-reset-and-human-ai-loop-ja.md).
Do not implement, register or execute this Plan from earlier continuation or
heartbeat instructions. Everything below is its preserved pre-pause design,
not current execution authority. CELL-1 remains unexecuted and unqualified;
the pause is not a scientific rejection of it.

Pre-registration freeze audit is incomplete: a metadata correction changed
`plan0031-design-drafts-v0.json` to SHA256
`ebd031581f37c6840a6e2d83a49f2d4d6d2bcf3fa03531b43f641039c9bbd850`,
while the prospective proposal still pins the earlier `b0479362...e54b074555`
digest reproduced below. The canonical candidate definition is unchanged.
Do not represent cross-artifact freeze acceptance as complete. This strategy
review preserves both files without editing, replaying or promoting them.

Plan30 is `COMPLETED / ACCEPTED` as technical evidence and `NO_SELECTION` as a
scientific result. Its four 100,000-node short censors are immutable and are not
promoted, supplemented or rerun. Plan0031 is the next chronological research
unit, not a Plan30 retry, candidate version or reserved survivor branch.

## One question and claim boundary

Can a fixed cohort of at most two fresh, simple existing-DSL definitions combine
a strict all-legal no-draw proof with low enough branching to *complete* the
A-by-ply7 and B-by-ply8 obvious-win checks, then survive a cheap exact probe and
a small deterministic policy diagnostic well enough to justify human rule
review?

Human rule review is exploratory. It does not establish fairness, general AI
hardness, strategic depth, fun or replayability. A completed finite short screen
means only no forced win inside its named horizon. Exact budget exhaustion stays
UNKNOWN. Sampled mixed wins are diagnostics, not fairness evidence.

## Fixed bounded design batch

Rank and exact first-draft structures are fixed before any candidate execution:

1. `zigzag-hop-two-hunters-v0`: 5x5, A first; A has five downward HOP pieces
   connecting LEFT–RIGHT from rows0/2; B has two up/left MOVE_CAPTURE hunters
   eliminating A from the lower-right corner. Proposed potential starts47,
   `max_plies=48`, and global maximum branching is5. Its primary and independent
   static lanes passed, including four prefix replays in each lane; it is the
   sole admitted definition, not yet production evidence.
2. `interleaved-push-step-bridges-v0`: 5x5, A first; A has five downward PUSH
   pieces and B five upward MOVE pieces, both connecting LEFT–RIGHT from
   interleaved rows. Proposed weighted potential starts46, `max_plies=47`, and
   global maximum branching is5. Source inspection proved a universal A win by
   ply5 and both explicit goals dead, so draft1 was rejected before replay. Its
   only data-only draft2 repaired goal liveness but exposed a universal A win by
   ply9 and was also rejected before replay. No third draft or replacement exists.

The machine-readable design drafts belong in
`experiments/proposals/plan0031-design-drafts-v0.json` and are authoritative.
Source-only reasoning before activation exposed both ideas, their proposed
potentials and hand-authored lines. That is disclosed development exposure, not
Plan31 selection evidence or confirmation.

Each structure permits at most two named data-only drafts in fixed order. Freeze
all pieces, coordinates, vectors, goals, first player, potential and `max_plies`
before checking a draft. A failed draft may inform only its same-structure second
draft through the recorded static failure. Do not inspect draft2 after draft1
passes. No third draft, replacement structure, backfill or cross-cell coordinate
tuning is allowed. Thus at most four definitions enter design checks.

## Static admission before implementation

For every attempted draft, run the following fixed checks in order, once in a
primary lane and once in an independent read-only audit where stated:

1. canonical schema4 parse, roundtrip and definition hash;
2. public old-six exclusion in both role orders, plus role-neutral exact
   action/goal noncollision with Plans20–30 and the other final cell;
3. initial state nonterminal with a canonical nonempty legal-action tuple;
4. a nonnegative integer potential with initial natural bound `40<=L<=80`,
   strict decrease by at least1 on every legal transition, and
   `max_plies=L+1`; coefficients must be justified by actual conditional effects,
   not padding;
5. complete alternating legal prefixes for each role's explicit GOAL and every
   conditional action effect, with no earlier terminal; at most four prefixes per
   draft and at most one primary plus one independent replay per prefix;
6. all-reachable nonterminal maximum branching `b<=6`, with a source proof and
   an attaining state when the claimed maximum is exact;
7. exact tree arithmetic
   `S_h(b)=sum(b^k for k=1..h)`, fixing A7 and B8 node caps at `S_7(b)` and
   `S_8(b)`. For the worst allowed `b=6`, these are335,922 and2,015,538;
8. with at most40 decisions per role,
   `40*S_4(b)<=100000`; at `b=6` this is62,160, so T3/T4 game censor is
   structurally impossible.

At most32 design-prefix replays and2,560 transitions exist across four drafts.
Do not call the exact solver, selection search, gameplay or state-space BFS in
the design stage. A complete source proof of a simple universal strategy is an
immediate fail-close: reject the draft and mark its remaining checks and prefix
replays `NOT_STARTED_STATIC_GATE_CLOSED`. Failure to find one is only a bounded
negative review, never a pass claim by itself.

The previously discussed fixed-ply `2^17` state-layer floor is not a Plan31 hard
condition. Independent review showed it mathematically impossible for one
otherwise coherent first draft, while the user requirement is completed bounded
obvious-win screening rather than a particular layer cardinality. Do not replace
it with an easier timeout score or call exact UNKNOWN positive evidence.

If both structures lack an admitted draft, close Plan31 in design stage without
a runner, production call or full regression. If at least one passes, freeze at
most two exact definitions, rank, fresh seeds, adapter identities and all limits
before implementation and registration.

## Frozen one-candidate cohort

The bounded design batch attempted three definitions. CELL-1 draft1 passed;
CELL-2 drafts1/2 were source-rejected by universal A wins at ply5/9, and its
unused fourth definition was never generated. The immutable design record is
`experiments/proposals/plan0031-design-drafts-v0.json`, SHA256
`b047936221304388f8c5b52dce94ed2274ab5c0492f0bfdadefb21e54b074555`.
Its eight allowed prefix replays consumed68 transitions; design-stage game,
exact, solver, selection and BFS calls remain zero.

The sole unchanged cohort member is `zigzag-hop-two-hunters-v0`, definition hash
`8c07cc4a89981b2b1533cfafd12081f71c72c0f79835172765fa4b9a3fa8600a`.
The frozen prospective proposal is
`experiments/proposals/plan0031-low-branching-complete-short-screen-v0.json`,
SHA256 `267bc27da094bc4e73babda31ee400538474e25cfe5d2cf2cc814d474b15a489`.
It fixes short seeds31001/31002, game seeds31100..31103 and31110..31113,
stage/policy order, exact gates and all limits. No candidate, coordinate, seed,
threshold or cap may change after this point.

## Prospective production cascade

The frozen one-candidate runner has exactly11 slots. Materialize the complete
schedule before computation and execute stage barriers in fixed rank order.

1. **Completed short screen:** query A at ply7 and B at ply8 with fresh
   `TerminalOnlyMinimaxAgent` instances, fixed seeds and the candidate's exact
   `S_h(b)` caps. Root actor is A, so A force is `max(values)==+1`; B force is
   `max(values)==-1`, not `min(values)==-1`. A completed force rejects as
   `NOT_SELECTED_SHORT_FORCED_WIN`. Censor contradicts the admitted branching
   bound and is `FAILED_TECHNICAL`.
2. **Cheap exact probe:** call the accepted exact adapter once at100,000 states.
   Valid COMPLETE decisive output is replayed only by that adapter and rejects as
   `NOT_SELECTED_TOO_EASILY_SOLVED`. Valid UNKNOWN uses zero replay and proceeds
   only as unresolved evidence; it earns no score and proves no hardness. A draw,
   PLY_LIMIT, winnerless result or D-055 bound violation is technical failure.
3. **Small policy diagnostic:** run four T3/T3 and four T4/T4 games with fresh
   fixed seeds and100,000 cumulative nodes per searched role per game. All eight
   must complete decisively. Across the combined eight, each role must win at
   least once; at least four endings must be explicit GOAL, including at least one
   A GOAL and one B GOAL; every conditional action effect named for the candidate
   must be realized in at least one matching saved pre-action state (both an
   actual HOP and an actual capture for the admitted CELL-1). A miss is
   `NOT_SELECTED_POLICY_DIAGNOSTIC`, not proof of universal imbalance.

Once a cell is rejected, its later slots are `NOT_STARTED_GATE_CLOSED`. A
technical failure closes every later slot as `NOT_STARTED_FAILURE`. Do not retry,
resume, replace, add seeds, relax thresholds, increase depth/caps or rerank from
wins, nodes, width or wall time. If multiple cells survive, retain only the
lowest fixed rank.

## UNKNOWN and human-review decision table

- missing D-055, goal/effect, history or branching evidence: static rejection;
- A7/B8 UNKNOWN: technical contradiction, never candidate evidence;
- game censor/draw/PLY_LIMIT: technical failure;
- exact COMPLETE decisive: easy-solve rejection;
- exact UNKNOWN100k: `UNRESOLVED_WITHIN_BUDGET`, no credit and no penalty;
- mixed bounded games: descriptive policy evidence only;
- every production gate plus saved/source audit and full regression pass:
  `HUMAN_RULE_REVIEW_ELIGIBLE`, while fairness/hardness/fun remain false.

This matches the user's chosen division: finish a meaningful bounded obvious-win
screen, disclose the unresolved remainder, then let the human decide whether the
rules are worth personally trying. It does not claim that no longer simple policy
or stronger solver can win.

## Minimal implementation and ceilings

After cohort freeze, add only one Plan31-specific runner and one test. Reuse and
pin the accepted Plan24 `play_one`, Plan20 `exact_one`, canonical publisher,
engine/DSL and terminal-only agent. Do not edit `src/`, DSL, engine, solver,
agents, accepted adapters or build a generic search platform. Tests use mocks or
separate tiny fixtures and never execute the frozen production definitions.

Frozen `b=5`, `L=47` one-candidate ceilings:

- short-search structural and configured nodes:585,935;
- exact searched states:100,000;
- configured game-agent nodes:1,600,000;
- T3/T4 structural game nodes:299,200;
- configured engine ply-cap slots:384, with D-055 natural plies at most376;
- adapter-internal replay transitions:at most432 using the conservative engine
  caps;
- attempts:11; immutable attempt/result pairs plus six global paths:28 files;
- at2MiB per envelope:58,720,256 bytes;
- one full-regression log outside those files:16MiB.

Implementation/fault tests, independent source/protocol review and focused
dependency tests precede one clean registration from production count zero.
Launch exactly one production cascade and exactly one full regression, preferably
in parallel clean registered worktrees. Technical acceptance requires saved-only
audit plus actual full-suite `Ran`/`OK`/exit0. Interruption or failure is not
retried. Only then may a surviving rule set be shown to the user; Site work stays
paused.

## Activation checklist

- [x] Plan30 archived as technically accepted `NO_SELECTION` with no human
  candidate and no continuation survivor.
- [x] Next chronological number established as independent Plan0031.
- [x] Two first-draft structures and a bounded no-backfill design process fixed.
- [x] Save authoritative design-draft JSON; run canonical/D-055/goal/effect/
  history/branching checks within the design ceilings. CELL-1 passed; both
  CELL-2 drafts were source-rejected without replay.
- [x] Freeze the sole admitted definition, ten unique seeds, gates and exact
  resource totals in the prospective proposal.
- [ ] PAUSED: resolve the strategic workflow before any implementation or
  registration; cross-artifact freeze audit is also incomplete.
- [ ] PAUSED: no production cascade or full regression has been launched.

## 2026-09-08 strategic-planning checkpoint

- [x] Read project state, this plan, backlog, original directive and relevant
  saved reports/source; independent read-only records and architecture reviews.
- [x] Confirm the user's no-draw requirement while relaxing size/simplicity.
- [x] Record the bounded discovery/self-improvement/human-division proposal,
  evidence distinctions, resource and stopping rules in the linked review.
- [x] Update project state, backlog, charter scope, operating contract and D-064.
- [x] Preserve all candidate/protocol bytes and old results. No new code,
  candidate games, solver calls or regression runs in this planning checkpoint.

Plan0032 is a proposed next research unit only, not an active or registered
experiment. Implementation begins only after the user next directs work to
proceed; it must not be inferred from a scheduled heartbeat.

## 2026-09-08 advisory discussion

The user asked about Lean's applicability. A future small verification layer
could formalize the decreasing-potential/no-draw argument and check strategy
certificates, with explicit correspondence to the authoritative DSL and Python
semantics. This feasibility discussion adds no implementation, admission gate,
production call or evidence to Plan31; its frozen proposal remains unchanged.
