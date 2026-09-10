> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Proposed contract — Single-game diagnostic conformance

## Status and purpose

Design only: this document activates no plan and authorizes no implementation,
fixture execution, DSL game, agent, solver, candidate selection, or experiment.
It neither replaces nor activates the proposed Plan-0016 accounting contract.
All prior evaluation policies, frozen fixtures, results, and failure decisions
remain unchanged; a future diagnostic would have its own version and scope.
This design follows the [strategic review](../reviews/2026-09-05-astra-strategic-review.md)
while preserving the [existing evaluation contract](../EVALUATION.md).

The founding directive, sections 1 and 8, asks for approximately equal role
strength for comparably capable players, measurement across strengths, and
separate draw reporting; an all-draw game is not a successful fair game.
Its interim operational question can therefore be:

> Can a small diagnostic preserve fixed-first-player, finite-policy evidence
> without promoting aggregation, weak policies, or unfinished play into fairness?

This is summary conformance, not evidence that any game is fair or that two
agents are equally capable. Equal depth or budget does not establish equal
human skill, equal role difficulty, or a calibrated strength ladder.

## Measurement and claim boundary

Keep each condition separate: fixed game/start identity, first player, the
ordered A/B policy pair, policy versions, and budgets. Preserve orientation and
seed/block identifiers when supplied. An alternate first player is another
single-game condition; a role/first-player exchange match is a separate unit.
Neither may silently replace a fixed-condition result by its pooled average.

For each condition retain A wins, B wins, natural draws, ply-limit outcomes,
unfinished/censored slots, planned slots, and completed slots. Compute decisive
A share only as A/(A+B), or undefined when there are no decisive results.
Report that conditional share alongside every denominator; it does not remove
draws or unfinished slots from the accounting. Never count censoring as a draw.
Require planned = completed + unfinished and completed = A wins + B wins +
natural draws + ply-limit outcomes. These terminal categories are disjoint.
Ply-limit means the terminal reason, not merely reaching the last permitted ply:
a goal reached on that ply remains decisive.

An exact A/B/draw value concerns perfect play of one fixed initial condition.
It does not overwrite finite-policy observations. A scalar exact `DRAW` does
not itself identify a terminal reason: retain `NOT_PROVIDED` unless separate
evidence establishes a reason and its scope. One illustrative line ending at
the ply cap is not proof that all optimal continuations end that way. Preserve
mixed reasons and incomplete solves without forcing either into a natural-draw
or horizon-draw label. A supplied exact-label example is illustrative data here,
not a solver proof.

Do not attach inferential confidence to invented examples. Their uncertainty
field is `NOT_ESTIMATED_SYNTHETIC_INPUT`. Later sampled evidence needs a declared
sampling model; shared seeds, orientations, or policies are not automatically
independent observations. No fairness tolerance or acceptance interval is fixed
by this contract.

## Eight proposed TABLE/TRACE examples

These are hand-specified records, not playable DSL definitions. TABLE means
stipulated condition/count rows. TRACE means abstract decision, alternative,
successor, and terminal identifiers; it is not an engine-validated action trace.
Freeze exact records and expected fields before implementing their consumer.

| ID | Synthetic input | Required distinction |
| --- | --- | --- |
| T1 | Same policy pair: A-first has A/B = 8/0; B-first has 0/8. | Two within-condition sweeps; pooled 8/8 cannot support single-game balance. |
| T2 | A-first and B-first both have A/B = 8/0. | Role-A sweep differs from T1's first-player pattern; complete role relabeling must produce the corresponding B pattern. |
| T3 | Twenty completed natural draws, zero decisive games. | Decisive share undefined; all-natural-draw pattern remains visible, never a fair-game qualification. |
| T4 | An abstract repeated-position prefix ends at a declared ply limit. | Repetition and horizon ending remain separate facts; this is neither natural-draw evidence nor proof of infinite play. |
| T5 | Twenty planned slots: four A wins, four B wins, twelve censored. | The completed decisive prefix is 1/2, but twelve slots remain unresolved; no completed-study or fairness claim follows. |
| T6 | One decision has a single legal alternative; another has several alternatives that immediately share a successor. | Forcedness and immediate reconvergence receive different descriptors; action count alone cannot establish meaningful choice. |
| T7 | At one fixed first-player condition, stipulated A/B rows are 8/8 for p0/p0, 16/0 for p1/p0, 0/16 for p0/p1, and 12/4 for p1/p1. | Preserve ordered-policy sensitivity and the unequal p1/p1 row; do not average it away or infer that p1 is a calibrated stronger player. |
| T8 | One complete fixed-condition table has A/B = 8/8 and no draws/censors; abstract decisions for both roles have distinct successors, with a declared differing opponent-response set. | Reproduce the equal observed-count pattern and the distinct-choice descriptors without inventing T1–T7 failures; fairness, strategic quality, and enjoyment remain unestablished. |

T8 is a calculation control, not a positive game-quality example. A consumer
that marks every record invalid, every decision forced, or every successor
identical cannot pass by refusing all fairness claims. Likewise, the abstract
opponent-response labels establish only equality/difference of supplied sets,
not real-game causality or enjoyable interaction.

The exact-label channel must also be checked independently of the count table:
changing an illustrative exact label must not change the table's counts or
decisive share. Supplied natural/horizon reason evidence, absent or mixed reason
evidence, and incomplete solves must stay distinct.
Role relabeling, row order, and display-name changes provide transformations of
these eight examples, not additional sampled games or independent evidence.

## Conformance gate and bounded follow-up

The proposed gate is exact agreement with all prewritten required fields and
transform relations, explicit treatment of unsupported/missing input, and zero
misclassification of the distinctions above. All eight examples, including T8,
remain in the denominator. Changing an expected answer after inspection creates
a documented revision; it does not repair a frozen example retrospectively.

Permitted conclusions of a later run would be `CONFORMANT_ON_SYNTHETIC_RECORDS`,
`CONFORMANCE_DEFECT`, or `INCOMPLETE`, with the failing fields retained. There
is no candidate-admission field and no automatic gameplay authorization.

Before any candidate evaluation, a reviewed DSL/engine vertical slice must
connect canonical definitions, real policy execution, retained
traces, terminal reasons, budgets, and the summary. It must test the same
distinctions against independent calculation, preserve legacy behavior, and
establish fixture/exposure separation. TABLE/TRACE conformance cannot substitute
for that integration or for agent-strength/human calibration.
Both layers may belong to one small preregistered diagnostic study; this document
does not require another generic framework or a separate plan for every layer.

This contract allocates neither every supported stratum nor a chosen 24-carrier
pilot. After conformance, justify any exact small gameplay schedule from a
specific remaining diagnostic question: the necessary fixtures, comparison
cells, seeds/orientations, deterministic caps, and stop rules. Freeze that
budget separately before execution; do not infer it from available supply.

## Human purpose still open

The intended mastery level and tolerance for a discoverable deep forced win
remain product judgments. Novice balance, balance after repeated study, and
perfect-play non-defeat symmetry are different ambitions. Do not silently select
one, set a human fairness/draw tolerance, or treat synthetic policy labels as
human ability. These choices do not block this narrowly defined diagnostic;
they matter before measured profiles become product qualification criteria.
