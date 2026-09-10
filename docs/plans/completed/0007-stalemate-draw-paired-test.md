> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan 0007 — Stalemate-draw paired terminal-semantics test

## Objective

Test the smallest rule change that can create a non-horizon exact draw in the
current place-versus-move family: when the next player has no legal action, end in
a draw instead of awarding the acting player a win. Preserve every other v1 rule
and compare the treatment on a fixed, baseline-informed but treatment-outcome-free
set of paired definitions.

## Hypothesis

On the 128 frozen landscape cases with `max_plies=18`, the stalemate-draw treatment
will create at least four static-valid, post-action exact `NO_LEGAL_ACTION` draws
spanning at least two of the 32 structural strata, and at least one will pass the
frozen provisional shape gates under both cheap and depth-5 play. If it does not,
adding this terminal policy is lower value than testing one direct B-counterplay
primitive.

## Expected result

All 128 treatment definitions solve exactly within 100,000 states, with no
`PLY_LIMIT` terminal because natural 3×3 exhaustion precedes ply 18. At least 15
static-valid exact treatment draws enter a separately sealed depth-5 diagnostic.
If no more than 32 are eligible and all finish, the general draw-handling assessment
can become conclusive; more than 32 remains explicit candidate-cap censoring.
Paired transition counts distinguish new stalemate draws from unchanged goal wins
without estimating generator-v2 prevalence.

## Definition of done

- [x] Add strict schema-v2 parsing for one explicit
  `terminal_policy.no_legal_action = DRAW` treatment while preserving canonical
  schema-v1 bytes, hashes, prose, and engine behavior.
- [x] Derive prose, symmetry identity, static analysis, play, and exact solving from
  the authoritative schema-v2 definition; add regression tests for goal, ply-cap,
  and no-legal-action precedence. Preserve `NO_LEGAL_MOVE_AT_START` as a static
  failure under schema v2 even though its terminal outcome becomes a draw.
- [x] Prove and test that this 3×3 one-runner, monotone-placement family terminates
  naturally by ply 16, so the paired 18-ply corpus cannot create horizon draws.
- [x] Build a deterministic treatment-outcome-free paired manifest from all and
  only the 128 `max_plies=18` cases in the frozen landscape manifest.
- [x] Re-evaluate every paired v1 baseline under the new parser and engine before
  any treatment solve; require deterministic exact, principal-variation, static,
  and cheap evidence to match the frozen raw landscape record.
- [x] Add fail-closed one-shot manifest, raw paired-evaluation, and adaptive draw-
  stress runners with separate reservations, attempt evidence, byte locks, and Git
  provenance.
- [x] Commit implementation and protocol before computing any schema-v2 corpus
  outcome.
- [x] Freeze and commit the paired manifest from a clean implementation commit.
- [x] Run and commit the raw paired corpus once from the clean manifest commit.
- [x] Run and commit the predeclared treatment-draw stress once from the committed
  raw record.
- [x] Inspect the frozen qualitative sample, report every predeclared assessment,
  and choose the next branch without changing thresholds.

## Single treatment

Schema v1 is immutable. Schema v2 adds exactly one required machine-readable
terminal-policy object for this experiment:

```json
"terminal_policy": {"no_legal_action": "DRAW"}
```

The treatment changes both initial immobility and next-player immobility from a
loss for the immobile player to a draw. Goal completion keeps first precedence and
the existing ply cap keeps second precedence. No action, goal, board, setup, first-
player, movement-vector, or maximum-ply field changes. Treatment definitions retain
the same display name; schema version and the terminal-policy field provide distinct
canonical DSL identities. Capture, push, jumping, repetition, scoring, generator
weights, and evaluator thresholds remain out of scope.

## Paired corpus

The sole case-membership source is the outcome-free landscape manifest with SHA-256
`f407aefb5fdb8c926db282ff90d2feb1a8666cda3fdbd6925b9f5cc07abd87b1`.
Select every case whose declared stratum has `max_plies=18`: four representatives
in each of 32 remaining strata, 128 pairs total. The original membership of each
stratum was outcome-blind, and the new manifest is treatment-outcome-free. The
choice to restrict this experiment to the 18-ply strata is explicitly informed by
the completed baseline observation of zero horizon draws and 68 principal
variations ending in `NO_LEGAL_ACTION`; it is not presented as outcome-independent.
The freezer must not read the raw landscape to select, rank, replace, or transform
a case. It must also fail closed unless every selected definition has board size
three, exactly one initial B runner and no other initial piece, A using `PLACE`, B
using `MOVE`, unchanged single-runner movement semantics, and `max_plies=18`.

For every selected v1 definition, create one v2 treatment definition differing
only in `schema_version` and the required terminal-policy object. Record source
case ID, source definition hash, source D4 hash, treatment definition hash,
treatment D4 hash, stratum, pair fingerprint, source-manifest byte hash, and frozen
executable fingerprints. The manifest contains no evaluation result.

The existing raw landscape record is used only after selection is frozen, to join
the 128 paired baseline labels and terminal reasons. Its required run ID is
`20260830T200230881318Z-landscape-f407aefb` and its byte SHA-256 is
`1edf571bc140a0cd586340eafee2306bccf6ca3a0816f8809b07edc9ef1a9fa4`.

### Why 18 plies is nonbinding

The selected family starts with one B runner and eight empty cells. Only A places,
and placed seeds are never removed; B's move preserves the number of empty cells.
After at most eight A turns, no empty cell remains; the ninth cell is occupied by
the runner. A goal or next-player immobility has therefore already terminated play.
With A first this occurs by ply 15 and with B first by ply 16. A treatment result
ending at `PLY_LIMIT` is therefore a semantic or provenance failure, not a draw
observation.

## Raw paired evaluation

Before computing a treatment outcome, reparse and re-evaluate all 128 v1 baseline
definitions with the new code. Their exact value, result, terminal reason,
principal variation, searched states, cache hits, static/asymmetry/simplicity
reports, cheap profiles, and cheap failures must reproduce the frozen raw record;
elapsed time is excluded. Any mismatch is an integrity failure. Then attempt exact
solving on all 128 treatment definitions with the frozen 100,000-state cap,
independent of all gates. Recompute the existing static, asymmetry, and simplicity
reports. For every structurally valid case, run weak-random and medium-goal-directed
over seeds `0..29` under the unchanged play gates.

Report:

- exact completion, state and time budgets;
- baseline-to-treatment exact transition matrix;
- treatment result and terminal-reason distributions by every stratum dimension
  and exact vector count;
- changes in principal-variation length and terminal reason, separating initial
  immobility (`PV=0`) from post-action stalemate (`PV>0`);
- sampled-play length both under the frozen `max_plies`-relative gate and as a
  fraction of the natural 15- or 16-ply exhaustion bound;
- static, simplicity, asymmetry, cheap failure, and agent/exact confusion counts;
- all exact stalemate draws and all shape-clean exact stalemate draws.

A shape-clean treatment draw passes static, asymmetry, and simplicity gates, has an
exact `DRAW` with terminal reason `NO_LEGAL_ACTION` after at least one action, and
has none of `EXCESSIVE_DRAWS`, `TOO_SHORT`, or `TOO_LONG` under frozen cheap play.
Dominance and agent disagreement remain visible diagnostics but do not prevent
entry to the strong stress lane. Because `TOO_LONG` is relative to the unchanged
18-ply field while natural exhaustion occurs by ply 15 or 16, passing it is only a
frozen protocol label—not a claim of acceptable human duration. Natural-bound
fractions remain a separate descriptive diagnostic and cannot change selection.

## Adaptive draw stress

Commit the raw record before stress. Select at most 32 shape-clean exact stalemate
draws by `sha256("stalemate-stress-clean-v1:" + treatment_definition_hash)`, then
fill unused slots with other structurally valid exact stalemate draws ordered by
`sha256("stalemate-stress-other-v1:" + treatment_definition_hash)`. Use
minimax-v1-depth5, seeds `0..29`, and a cumulative 5,000,000-node cap per treatment
definition. No replacement is allowed.

A diagnostic-frontier case is a shape-clean exact stalemate draw that completes
depth 5, remains non-decisive, and has no frozen strong-play failure code.
`Non-decisive` retains the frozen `sampled_direction` rule: no decisive games or an
exact A/B tie among decisive games yields `DRAW_OR_BALANCED`; any unequal A/B count
is conservatively directional even when its Wilson interval overlaps 0.5. Report
the interval and dominance codes separately. A depth-5 directional label is an
evaluator error, never a treatment success.

General draw-stress support requires at least 15 completed cases, no node or
candidate-cap censoring, and no decisive error. Frontier completeness is separate:
it requires every shape-clean treatment draw to be selected and completed without
decisive error. The 32-case cap may therefore leave an absence conclusion
inconclusive even when positive selected cases remain informative.

## Predeclared assessments and decisions

Apply these assessment rules in order; an earlier blocker takes precedence over
later positive counts:

1. Any source, v1 replay, pair, executable, lock, ancestry, reservation, or
   aggregate mismatch is an integrity failure and stops before treatment
   interpretation.
2. Any completed treatment exact result ending at `PLY_LIMIT` makes the clean
   non-horizon assessment and overall treatment-discovery hypothesis
   `NOT_SUPPORTED`, even if another case is censored. Audit semantics and the
   exhaustion proof before continuing.
3. Otherwise, any exact state-cap censor makes exact completion, semantic response,
   frontier response, and overall treatment-discovery `INCONCLUSIVE`. Improve exact
   search rather than infer a missing label.
4. With complete exact evidence, the semantic response is `SUPPORTED` if at least
   four static-valid, post-action exact stalemate draws span at least two
   predeclared strata, `NOT_SUPPORTED` if none occurs, and otherwise
   `INCONCLUSIVE`. Static-rejected initial immobility draws are reported but never
   count toward support or enter stress.
5. Any completed exact draw called directional by the frozen depth-5 rule makes
   draw stress `NOT_SUPPORTED`. It makes frontier and overall treatment-discovery
   `INCONCLUSIVE` with reason `EVALUATOR_ERROR`, rather than blaming the terminal
   treatment, and prioritizes an independent solver or leaf-evaluator family.
6. Otherwise, a node-censored or unselected shape-clean draw makes frontier response
   and overall treatment-discovery `INCONCLUSIVE`. Any node censoring, or candidate-
   cap censoring by an unselected structurally valid exact draw, also keeps general
   draw stress `INCONCLUSIVE` even when frontier coverage is complete.
7. With complete frontier evidence, the frontier response is `SUPPORTED` when at
   least one diagnostic-frontier case exists and `NOT_SUPPORTED` when the count is
   zero. The overall treatment-discovery hypothesis is `SUPPORTED` only when both
   semantic and frontier responses are supported; it is `NOT_SUPPORTED` when
   either is not supported, and otherwise `INCONCLUSIVE`.

These labels only govern the frozen discovery pipeline; semantic support alone is
not evidence of a good game. Exact draws that all retain shape failures must not
become a generator objective. After the ordered assessments:

- Four or more diagnostic-frontier cases spanning at least two strata trigger a
  separately frozen, outcome-blind validation corpus; the treatment is not adopted
  from this discovery sample alone.
- Four or more frontier cases confined to one stratum trigger a single-stratum
  validation corpus. One to three trigger a focused outcome-blind validation.
- Zero frontier cases with complete exact and frontier evidence rejects this
  stalemate policy as the next discovery direction and advances one separately
  versioned direct-interaction test. Capture is a candidate hypothesis, not a
  preauthorized implementation.
- Zero selected frontier cases with untested shape-clean draws remains
  `INCONCLUSIVE`; do not reject the policy or silently raise the cap.

## Frozen exploratory inspection

After raw and stress statuses are sealed, freeze and inspect every exact or
depth-5 censor, every diagnostic-frontier case, all stress-selected cases, 16
additional baseline-to-treatment outcome changes ordered by
`sha256("stalemate-inspection-change-v1:" + treatment_definition_hash)`, and 16
unchanged cases ordered by
`sha256("stalemate-inspection-control-v1:" + treatment_definition_hash)`. Inclusion
can overlap and is recorded per case. Inspection cannot change an outcome,
threshold, or branch.

## Outcome

The treatment-outcome-free manifest froze all 128 pairs across 32 strata. Exact
solving completed 128/128 treatment cases without censoring or `PLY_LIMIT`: 73 A
wins, 35 B wins, and 20 `NO_LEGAL_ACTION` draws. All 20 changes were baseline A
wins becoming draws. Four were initial immobility and 16 were post-action
stalemates, but only two post-action draws were static-valid, spanning two strata.
This missed the declared four-case semantic threshold. No treatment draw was
shape-clean.

Depth 5 completed both eligible static-valid draws without node censoring or a
directional error. Both profiles were 30/30 `NO_LEGAL_ACTION` draws and failed
`EXCESSIVE_DRAWS`; one also failed `TOO_SHORT`. General draw stress remained
`INCONCLUSIVE` at two completions, frontier response was `NOT_SUPPORTED`, and the
overall treatment-discovery result was `NOT_SUPPORTED`.

## Interpretation

Changing the terminal label created formal non-horizon draws but not counterplay.
Eighteen of 20 draws merely relabeled already-invalid low-mobility definitions;
the two valid cases rewarded short obstruction and became certain stalemates under
stronger play. The negative frontier result is complete even though the general
draw-handling sample is too small for confirmation.

The archived raw record proves that the frozen runner could not enter treatment
until a full v1 replay passed, and independent replay also matched all 128 cases.
It does not retain the timing-free replay candidates or a digest, so future paired
protocols must preserve replay attestation rather than only a derived match count.

## Decision

Follow `DESIGN_DIRECT_INTERACTION_TEST`. Do not adopt schema v2, optimize toward
sparse movement, or change a threshold. Test exactly one B-side capture-on-entry
primitive under schema-v1 terminal semantics on the same frozen 18-ply membership
without consulting capture-treatment outcomes. This is a counterplay-response
diagnostic, not a fairness-discovery claim; any treatment draw remains
finite-horizon non-resolution.

Result report:
[`../../../experiments/reports/0007-stalemate-draw-paired-result.md`](../../../experiments/reports/0007-stalemate-draw-paired-result.md).
