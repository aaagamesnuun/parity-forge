> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan0033 — Audit the six requested cut-and-choose originals

## Status and authority

SOURCE_AUDIT_COMPLETE / SIX_ORIGINALS_REVIEWED / NO_NEW_ENGINE_OR_GAMES.
Archived when the user requested further progress; Plan0034 owns implementation.
Scope was saved by 2026-09-07T21:54:35Z (2026-09-08 JST).
User: 「『cut and choose アブストラクト』というchatで出されたアイデア群も検証してみて」.
The exact retrieved title is `cut and chooseアブストラクト`, task ID
`6a9f0036-6500-83ee-ad82-3e750a1c27f4`. The complete single-turn source is
[snapshotted](../../../experiments/proposals/plan0033-cut-choose-chat-source.json).
Source recommendations are proposals, not overrides of D-055/D-064.

## Question and fixed boundaries

Which originals satisfy mechanical asymmetry and universal finite single-winner
termination? Can a cheap, explicit strategy certificate settle the original
4-by-4-point edge game before building another engine?

- Exactly six original proposals; no additional boards, tie rules, role fixes,
  seeds or initial-position search. Do not silently turn missing rules into wins.
- Distinguish permanent player-role differences from alternating proposal/choice
  phases. Do not call a hard-gate mismatch evidence that the game is unfun.
- Three preselected constructive score checks: 分水嶺 checkerboard (16 blocks),
  国境 checkerboard setup allowed by its incomplete description, and 欠片 eight
  identical I3/I3 cuts with a symmetric 24/24-cell final allocation.
- The original 架ける者、断つ者 graph has 16 vertices and ALL 24 edges, including
  six boundary-parallel edges. Both roles stay fixed, and exactly two unresolved
  edges are resolved per round. No artificial ply winner or odd-edge rule.
- First-proposer omission is recorded, not hidden. Draw counterexamples and
  termination arguments must work for either first proposer where relevant.
- At most one 45-minute source-review work session and two independent bounded
  read-only reviews. No model call per move, no production/self-play campaign.
- Optional arithmetic/graph witness verification: at most three one-off local
  invocations, each at most 60 seconds. Three fixed score traces plus at most two
  analytically supplied fixed edge-pairing certificates, at most 4,096 chooser
  allocations each. This is verification of exposed witnesses, not a prospective
  quality sample, adaptive strategy search or complete minimax solving.
- If no strategy certificate is obtained, record strategy UNKNOWN. Do not add
  node budget, retry, call absence of a certificate depth, or replace the game.

## Implementation and preservation

Documentation/source snapshot and static diagnostic data only; no product,
test, fixture, agent, evaluator, DSL, runner or dependency edits. Existing
TILE/TRAIL cannot faithfully encode these two-stage allocation/edge rules;
do not reinterpret an original through its NO_LEGAL_ACTION_LOSES terminal.
No full-suite rerun is needed for a documentation-only unit. If implementation
becomes necessary, defer it to a separately scoped unit with the mandatory full
regression rather than hide code in this source audit.

Plan32 is archived as technically accepted and its two optional TILE handoffs
remain available. Its episode1 is not retried and its episode2 is not launched.
This audit is not a reset or consumption of extra finite-space game episodes.
Preserve all old studies, protected Plan13/14 membership and unrelated changes.
No website deployment, human trial, external message or new automation.

## Exit

A six-row Japanese disposition report with explicit counterexamples/proofs,
source/method limitations and one prioritized next action. A no-draw proof is
not balance/depth/fun certification. Save any diagnostic output separately;
update project state and backlog, then stop this finite unit without automatic
engine construction or additional game discovery.

## Checklist

- [x] Retrieve the complete requested source and preserve exact originals.
- [x] Freeze the static-review scope before any diagnostic execution.
- [x] Independent rule/strategy review.
- [x] Verify three fixed score witnesses; no fixed edge certificate supplied/needed.
- [x] Record all six dispositions and evidence limits.
- [x] Update current state/backlog and hand off the bounded result.

## Completion checkpoint — 2026-09-08 JST

[Japanese findings](../../../experiments/reports/0033-cut-and-choose-audit-ja.md).
The source snapshot is complete and pinned. One optional diagnostic invocation
at2026-09-07T21:56:17Z completed exit0, checking the three exposed constructions;
no retries or second/third diagnostic. Independent saved-evidence audit PASS.
No fixed pairing enumeration or minimax was launched and no game sample exists.

Only 架ける者、断つ者 directly satisfies the two hard constraints as written.
Its all-legal termination/unique winner has a source proof. A bounded reviewer
derived a proof excluding all pre-fixed12-pair Cutter strategies; main and a
second reviewer checked the cases independently, PASS. Adaptive Cutter/Builder
forced winner remains UNKNOWN. A successful no-draw proof or failed fixed-pair
approach is not a fairness/depth/fun finding.

Product/test Python edits0; all190 existing pins match/exit0. The old regression
was not rerun and is not claimed as acceptance of an unimplemented new engine.
No UI, human session, scheduler or external source-chat write. Keep this plan as
the current result/next-action record. The next unit, if begun, must first scope
one faithful24-edge adaptive-strategy diagnostic, not broaden to all six ideas
or retroactively repair the originals. No immediate human question is needed.
