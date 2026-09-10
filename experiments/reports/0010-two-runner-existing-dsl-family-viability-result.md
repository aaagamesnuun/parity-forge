> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Report 0010 — Two-runner existing-DSL family viability result

Adding a second ordinary B runner does **not** produce candidate-shaped play in
the frozen 3×3 schema-v1 family. The setup change is mechanically active: 31
exact principal variations expose a two-runner decision, 54 treatment profiles
contain a same-game engagement trace, and the fixed strong frontier contains 46
cases across all 16 strata and all four structural cells. However, every one of
those 46 frontier cases is role-dominant: 24 are exact A wins with `A_DOMINANT`
profiles and 22 are exact B wins with `B_DOMINANT` profiles. Candidate shape is
therefore empty.

All exact and depth-5 evidence completed without state censoring, node censoring,
`PLY_LIMIT`, direction mismatch, or failure evidence. Under the frozen Plan 0010
priority, the formal result is `NOT_SUPPORTED_TWO_RUNNER_SETUP` and the next
branch is `FAMILY_REASSESSMENT`. The two-runner setup is not authorized as a
generator substrate or as a candidate mechanic.

## Evidence chain

The reviewed outcome-free implementation, protocol, and 330-test checkpoint was
frozen at `9fb504bfd2481f31c039db15ae1be577b71c54d9`. The one-shot manifest was
created from that clean commit without solver or agent calls and archived at
`eb0e032a436144187be7f5efc2f523e59cf2c404`:

- manifest ID: `two-runner-v1-64-pair-manifest`;
- manifest SHA-256:
  `3b7757ade9bd745eb1aff838455927115005dd8efe4d96ebaef51af213d228b9`;
- exclusion-ledger SHA-256:
  `b38b2d1e2bd5b3faa0c5cdb86580e408547faa4bef819eeb9c3feb5143b440a0`;
- exclusion-ledger bytes: 131,707;
- closed projection bundle root:
  `755b5a5d8ae35d8222873275e87860effbdf7ec2266de3799814d20385b12ca3`;
- 36,720 raw definitions, 4,776 D4 orbits, 1,016 relevant source orbits,
  907 unused relevant source orbits, 738 paired-gate-valid pairs, 477
  treatment-unique pairs, 16 strata, and four selected pairs per stratum;
- 8,128 D4-equivariance checks, 503 evaluated source orbits, and zero selected
  full-history collision;
- representative-choice root:
  `62ffa9c07ae84c7566330310f9029599b0c8d4e929a39272a583a2d5e4f4f859`;
- eligible-pool root:
  `73dcda3d2845c01113b41ecf8d46b923f044e4ec11c1d80c205644de0028b706`;
- selection fingerprint:
  `8bb8feb104ce58e92729d593464acb6e08e2de9c59154440c15580a66db9eb91`;
- both treatment-outcome-computed and membership-outcome-consulted selection
  flags are false.

Paired exact ran once from manifest commit `eb0e032` as
`20260831T042721207815Z-two-runner-exact-3b7757ad`. Its 1,333,308-byte
`run.json` has SHA-256
`2353bfb8dbf545d6c3430a998b5fe60c5db9822c28c965f7a2adbacce0844e39`.
Its reservation, attempt, and result were archived unchanged at
`345094764242a555b8fe27abcd5601414d8a2f97`.

Fixed depth 5 then ran once from exact-artifact commit `3450947` as
`20260831T043600138223Z-two-runner-depth5-2353bfb8`. Its 27,597,646-byte
`run.json` has SHA-256
`dd77cfbd1cb76763ed394d767ce5c296191d25f2589d0a48819de242526f8cda`.
Its reservation, attempt, and result were archived unchanged at
`d430e83666e4a25b21a538ac46fb9b767426bb0e`.

Post-commit public reconstruction authenticated the complete manifest and exact
source chains, rebuilt all 128 exact slots and 128 depth profiles from retained
actions, lineage, and node ledgers, matched every aggregate, assessment,
inspection row, and narrative, and found no failure sidecar or dirty byte.
Independent scientific and provenance audits repeated these checks and found no
P0–P3 defect. The strict lineage is
`9fb504b -> eb0e032 -> 3450947 -> d430e83`.

The canonical exact aggregate, exact inspection, depth aggregate, and final
inspection SHA-256 values are respectively:

```text
1faeb5bb45c35113345867f9fd39104631b0df4c789119017b3aff2083358120
1773e5ce94ce478d40e42003416f1fb411d9bfb94aa5eaa06b268e814e600f82
47202c85ee7545e3a40b8d333ae52060837992a4ef8355f91c70cc02e1811fea
76ac7c68f4090d82315e12ab3ed086a14aa749e4b13d22a65e8391080dd8b4a1
```

## Predeclared assessments

| Dimension | Observation | Formal outcome |
|---|---|---|
| Integrity and provenance | Membership, D4 identities, one-variable pairs, ancestry, locks, schedules, actions, lineages, state/node ledgers, aggregates, and inspection reconstructed | passed |
| Exact completion | 128/128 slots; no censor or `PLY_LIMIT`; source maximum 2,980/43,776 states and treatment maximum 4,665/69,120 | complete |
| Containment response | Zero source `A_WIN/NO_LEGAL_ACTION` cases became treatment `B_WIN/GOAL` | `NOT_SUPPORTED` |
| Exact engagement response | 31 treatment PVs across 12 strata both moved `ADDED` and exposed a both-lineage decision | `SUPPORTED` |
| Strong evidence | 128/128 profiles and 3,840/3,840 games; no node censor or direction mismatch | `COMPLETE` |
| Same-game sampled engagement | 54 treatment cases have one completed game satisfying both engagement conditions | descriptive prerequisite |
| Strong frontier | 46 cases across 16 strata and four structural cells; exact A/B = 24/22 | `PRESENT` |
| Candidate shape | All 46 frontier cases are role-dominant; zero qualifying cases | `NOT_SUPPORTED` |
| Overall | Complete strong evidence plus zero candidate-shaped cases | `NOT_SUPPORTED_TWO_RUNNER_SETUP` |
| Next branch | Do not generate toward the setup; compare one bounded 4×4 evaluator-calibration lane with retiring the narrow family | `FAMILY_REASSESSMENT` |

The exact engagement assessment is deliberately separate from candidate shape.
An optimal retained PV can show that both runners matter mechanically, but it
cannot substitute for non-dominant sampled play. The stronger same-game condition
was met in 54 treatments, yet the candidate gate still failed because dominance
was universal on the 46 cases that also passed direction and shape requirements.

## Paired exact response

All 64 sources completed before the source evidence seal, after which all 64
treatments completed. Source outcomes were A/B = 35/29 and treatment outcomes
were A/B = 34/30:

| Source -> treatment | Cases |
|---|---:|
| `A_WIN -> A_WIN` | 34 |
| `A_WIN -> B_WIN` | 1 |
| `B_WIN -> B_WIN` | 29 |

The only value change was pair 064, `A_WIN/GOAL -> B_WIN/GOAL`, with its retained
PV shortening from 14 plies to 3. The added runner did not move on that treatment
PV, so this change is not an exact engagement response. Its source terminal was
not `NO_LEGAL_ACTION`, so it is not a containment response either.

Source solving searched 106,051 states and treatment solving searched 149,798.
The maxima were 2,980 and 4,665 states, both on pair 046 and far below the proved
bounds. Cache hits were 125,761 and 177,802. Exact play found 31 engagement
responses, including 26/32 aligned cases and 5/32 orthogonal cases.

| Breakdown | Source A/B | Treatment A/B | Value changes | Exact engagement |
|---|---:|---:|---:|---:|
| first player A | 22/10 | 22/10 | 0 | 15 |
| first player B | 13/19 | 12/20 | 1 | 16 |
| aligned goals | 19/13 | 19/13 | 0 | 26 |
| orthogonal goals | 16/16 | 15/17 | 1 | 5 |
| vectors 1–3 | 14/2 | 14/2 | 0 | 7 |
| vectors 4 | 12/4 | 12/4 | 0 | 8 |
| vectors 5 | 5/11 | 5/11 | 0 | 7 |
| vectors 6–7 | 4/12 | 3/13 | 1 | 9 |

Adding a runner therefore barely changed which role can force a win across this
fixed sample. Its clearer effect is within-line counterplay and extra occupancy,
not across-definition value calibration.

## Fixed depth-5 evidence

All 64 source profiles were completed and sealed before any treatment profile.
Each definition used one fresh depth-5 agent and one cumulative 5,000,000-node
budget over seeds `0..29`. The run completed 3,840 games and expanded 5,027,783
nodes: 1,956,338 on sources and 3,071,445 on treatments. The largest profile used
117,030 nodes, only 2.34% of its cap.

| Side | Profiles | Games | A/B/draw | Mean plies | Engaged games | Too short |
|---|---:|---:|---:|---:|---:|---:|
| Source | 64 | 1,920 | 1,050/870/0 | 5.77 | 0 | 17 |
| Treatment | 64 | 1,920 | 1,020/900/0 | 6.30 | 1,182 | 10 |

Every source and treatment profile was 30–0 in its exact direction. Treatment
games moved the added runner in 1,229 games, offered both lineages at a B decision
in 1,606 games, moved both lineages in 807 games, and met the same-game engagement
condition in 1,182 games. This is substantial mechanical use of the second runner,
but no evidence of within-definition balance.

The strong frontier excludes ten treatment `TOO_SHORT` cases and ten treatments
without a same-game engagement witness, with two cases overlapping. The remaining
46 cases are distributed broadly but remain uniformly dominant:

| Breakdown | Frontier | Exact A/B | Engaged treatments | Candidate-shaped |
|---|---:|---:|---:|---:|
| first player A | 26 | 16/10 | 26 | 0 |
| first player B | 20 | 8/12 | 28 | 0 |
| aligned goals | 22 | 13/9 | 26 | 0 |
| orthogonal goals | 24 | 11/13 | 28 | 0 |
| vectors 1–3 | 9 | 8/1 | 10 | 0 |
| vectors 4 | 9 | 9/0 | 13 | 0 |
| vectors 5 | 12 | 4/8 | 15 | 0 |
| vectors 6–7 | 16 | 3/13 | 16 | 0 |
| first-A aligned | 11 | 7/4 | 11 | 0 |
| first-A orthogonal | 15 | 9/6 | 15 | 0 |
| first-B aligned | 11 | 6/5 | 15 | 0 |
| first-B orthogonal | 9 | 2/7 | 13 | 0 |

The across-definition role mix shifts with vector count, but each individual
profile remains completely one-sided. As in the capture experiments, a mixed A/B
frontier is not a fairness frontier.

## Frozen inspection

The final manifest-ordered union contains 56 unique pairs: all 46 strong-frontier
cases, all 31 exact-engagement responses, the sole outcome change, 16 unchanged
controls, and the rank-zero pair in every stratum, with overlaps retained. There
were no exact/node censors, direction mismatches, containment responses, or
candidate-shaped cases to add.

The change pools had sizes 0, 0, 0, and 1 for vector bands `v1_3`, `v4`, `v5`,
and `v6_7`, producing shortfalls 4, 4, 4, and 3 under their separate four-case
quotas. Each unchanged-control pool met its four-case quota. Shortfalls are
descriptive and were neither borrowed across bands nor used to alter the result.

Notation: `eng`, `front`, `chg`, `ctl`, and `floor` are the frozen inclusion
reasons. Treatment depth-5 is A/B/draw wins, mean plies, and failure codes.

| Pair | Reasons | Stratum | Exact | Treatment depth-5 | Frontier |
|---:|---|---|---|---|:---:|
| 001 | floor | fA-aligned-v1_3 | `A/NO_LEGAL_ACTION->A/NO_LEGAL_ACTION` | `30/0/0; p7.2; A_DOMINANT` | N |
| 002 | eng+front+ctl | fA-aligned-v1_3 | `A/NO_LEGAL_ACTION->A/NO_LEGAL_ACTION` | `30/0/0; p10.3; A_DOMINANT` | Y |
| 004 | eng+front+ctl | fA-aligned-v1_3 | `A/GOAL->A/GOAL` | `30/0/0; p8.1; A_DOMINANT` | Y |
| 005 | eng+front+floor | fA-aligned-v4 | `A/NO_LEGAL_ACTION->A/NO_LEGAL_ACTION` | `30/0/0; p10.3; A_DOMINANT` | Y |
| 006 | eng+ctl | fA-aligned-v4 | `A/NO_LEGAL_ACTION->A/NO_LEGAL_ACTION` | `30/0/0; p7.8; A_DOMINANT` | N |
| 007 | ctl | fA-aligned-v4 | `A/NO_LEGAL_ACTION->A/NO_LEGAL_ACTION` | `30/0/0; p6.6; A_DOMINANT` | N |
| 008 | eng+front | fA-aligned-v4 | `A/GOAL->A/NO_LEGAL_ACTION` | `30/0/0; p9.5; A_DOMINANT` | Y |
| 009 | ctl+floor | fA-aligned-v5 | `A/NO_LEGAL_ACTION->A/NO_LEGAL_ACTION` | `30/0/0; p1.0; A_DOMINANT,TOO_SHORT` | N |
| 010 | eng+front | fA-aligned-v5 | `A/NO_LEGAL_ACTION->A/GOAL` | `30/0/0; p8.9; A_DOMINANT` | Y |
| 011 | eng+front+ctl | fA-aligned-v5 | `B/GOAL->B/GOAL` | `0/30/0; p4.6; B_DOMINANT` | Y |
| 012 | eng+front+ctl | fA-aligned-v5 | `A/GOAL->A/GOAL` | `30/0/0; p11.1; A_DOMINANT` | Y |
| 013 | eng+front+ctl+floor | fA-aligned-v6_7 | `A/GOAL->A/GOAL` | `30/0/0; p10.2; A_DOMINANT` | Y |
| 014 | eng+front | fA-aligned-v6_7 | `B/GOAL->B/GOAL` | `0/30/0; p5.3; B_DOMINANT` | Y |
| 015 | eng+front | fA-aligned-v6_7 | `B/GOAL->B/GOAL` | `0/30/0; p4.9; B_DOMINANT` | Y |
| 016 | eng+front+ctl | fA-aligned-v6_7 | `B/GOAL->B/GOAL` | `0/30/0; p4.6; B_DOMINANT` | Y |
| 017 | eng+front+floor | fA-orthogonal-v1_3 | `A/NO_LEGAL_ACTION->A/NO_LEGAL_ACTION` | `30/0/0; p6.7; A_DOMINANT` | Y |
| 018 | eng+front | fA-orthogonal-v1_3 | `A/NO_LEGAL_ACTION->A/GOAL` | `30/0/0; p8.0; A_DOMINANT` | Y |
| 019 | front+ctl | fA-orthogonal-v1_3 | `A/GOAL->A/NO_LEGAL_ACTION` | `30/0/0; p6.3; A_DOMINANT` | Y |
| 021 | front+ctl+floor | fA-orthogonal-v4 | `A/GOAL->A/GOAL` | `30/0/0; p8.1; A_DOMINANT` | Y |
| 022 | front | fA-orthogonal-v4 | `A/GOAL->A/GOAL` | `30/0/0; p5.2; A_DOMINANT` | Y |
| 023 | front | fA-orthogonal-v4 | `A/NO_LEGAL_ACTION->A/NO_LEGAL_ACTION` | `30/0/0; p7.6; A_DOMINANT` | Y |
| 024 | front | fA-orthogonal-v4 | `A/GOAL->A/GOAL` | `30/0/0; p6.8; A_DOMINANT` | Y |
| 025 | front+floor | fA-orthogonal-v5 | `A/GOAL->A/GOAL` | `30/0/0; p7.1; A_DOMINANT` | Y |
| 026 | front+ctl | fA-orthogonal-v5 | `B/GOAL->B/GOAL` | `0/30/0; p5.6; B_DOMINANT` | Y |
| 027 | front | fA-orthogonal-v5 | `B/GOAL->B/GOAL` | `0/30/0; p5.4; B_DOMINANT` | Y |
| 028 | front | fA-orthogonal-v5 | `B/GOAL->B/GOAL` | `0/30/0; p4.9; B_DOMINANT` | Y |
| 029 | front+floor | fA-orthogonal-v6_7 | `B/GOAL->B/GOAL` | `0/30/0; p5.6; B_DOMINANT` | Y |
| 030 | front | fA-orthogonal-v6_7 | `B/GOAL->B/GOAL` | `0/30/0; p5.7; B_DOMINANT` | Y |
| 031 | eng+front | fA-orthogonal-v6_7 | `A/GOAL->A/GOAL` | `30/0/0; p7.5; A_DOMINANT` | Y |
| 032 | front+ctl | fA-orthogonal-v6_7 | `B/GOAL->B/GOAL` | `0/30/0; p5.7; B_DOMINANT` | Y |
| 033 | ctl+floor | fB-aligned-v1_3 | `A/NO_LEGAL_ACTION->A/NO_LEGAL_ACTION` | `30/0/0; p4.1; A_DOMINANT` | N |
| 035 | eng+front | fB-aligned-v1_3 | `A/NO_LEGAL_ACTION->A/NO_LEGAL_ACTION` | `30/0/0; p10.7; A_DOMINANT` | Y |
| 036 | eng+front | fB-aligned-v1_3 | `A/GOAL->A/NO_LEGAL_ACTION` | `30/0/0; p11.3; A_DOMINANT` | Y |
| 037 | eng+front+floor | fB-aligned-v4 | `A/GOAL->A/GOAL` | `30/0/0; p11.1; A_DOMINANT` | Y |
| 038 | eng+front | fB-aligned-v4 | `A/GOAL->A/NO_LEGAL_ACTION` | `30/0/0; p10.0; A_DOMINANT` | Y |
| 039 | eng | fB-aligned-v4 | `B/GOAL->B/GOAL` | `0/30/0; p3.8; B_DOMINANT,TOO_SHORT` | N |
| 040 | eng+ctl | fB-aligned-v4 | `B/GOAL->B/GOAL` | `0/30/0; p3.6; B_DOMINANT,TOO_SHORT` | N |
| 041 | eng+front+floor | fB-aligned-v5 | `B/GOAL->B/GOAL` | `0/30/0; p4.5; B_DOMINANT` | Y |
| 042 | eng+front | fB-aligned-v5 | `A/GOAL->A/NO_LEGAL_ACTION` | `30/0/0; p10.3; A_DOMINANT` | Y |
| 043 | eng | fB-aligned-v5 | `B/GOAL->B/GOAL` | `0/30/0; p3.8; B_DOMINANT,TOO_SHORT` | N |
| 044 | eng+front | fB-aligned-v5 | `B/GOAL->B/GOAL` | `0/30/0; p4.2; B_DOMINANT` | Y |
| 045 | eng+front+floor | fB-aligned-v6_7 | `B/GOAL->B/GOAL` | `0/30/0; p4.3; B_DOMINANT` | Y |
| 046 | eng+front | fB-aligned-v6_7 | `B/GOAL->B/GOAL` | `0/30/0; p4.4; B_DOMINANT` | Y |
| 047 | eng+front | fB-aligned-v6_7 | `B/GOAL->B/GOAL` | `0/30/0; p4.5; B_DOMINANT` | Y |
| 048 | eng+front | fB-aligned-v6_7 | `A/GOAL->A/GOAL` | `30/0/0; p12.1; A_DOMINANT` | Y |
| 049 | eng+front+floor | fB-orthogonal-v1_3 | `A/NO_LEGAL_ACTION->A/NO_LEGAL_ACTION` | `30/0/0; p9.6; A_DOMINANT` | Y |
| 052 | front | fB-orthogonal-v1_3 | `B/GOAL->B/GOAL` | `0/30/0; p4.1; B_DOMINANT` | Y |
| 053 | floor | fB-orthogonal-v4 | `A/NO_LEGAL_ACTION->A/NO_LEGAL_ACTION` | `30/0/0; p4.2; A_DOMINANT` | N |
| 054 | eng+front | fB-orthogonal-v4 | `A/NO_LEGAL_ACTION->A/NO_LEGAL_ACTION` | `30/0/0; p9.7; A_DOMINANT` | Y |
| 057 | floor | fB-orthogonal-v5 | `B/GOAL->B/GOAL` | `0/30/0; p3.8; B_DOMINANT,TOO_SHORT` | N |
| 059 | front | fB-orthogonal-v5 | `B/GOAL->B/GOAL` | `0/30/0; p4.1; B_DOMINANT` | Y |
| 060 | front | fB-orthogonal-v5 | `B/GOAL->B/GOAL` | `0/30/0; p4.1; B_DOMINANT` | Y |
| 061 | front+ctl+floor | fB-orthogonal-v6_7 | `B/GOAL->B/GOAL` | `0/30/0; p4.3; B_DOMINANT` | Y |
| 062 | front | fB-orthogonal-v6_7 | `B/GOAL->B/GOAL` | `0/30/0; p4.9; B_DOMINANT` | Y |
| 063 | front | fB-orthogonal-v6_7 | `B/GOAL->B/GOAL` | `0/30/0; p4.5; B_DOMINANT` | Y |
| 064 | front+chg | fB-orthogonal-v6_7 | `A/GOAL->B/GOAL` | `0/30/0; p4.2; B_DOMINANT` | Y |

The eight unlisted pairs are ordinary nonfrontier cases not selected by any
inspection reason. Their complete exact and sampled evidence remains in the final
artifact; inspection never filtered execution or the reported aggregate.

## Interpretation

The second runner is neither inert nor a useful calibration lever. It frequently
creates alternate legal moves and both-lineage decisions, and it expands sampled
search cost by roughly 57% relative to source play. Nevertheless, exact value
changes in only one of 64 fixed pairs, while every strong profile remains 30–0.
The setup changes tactical route structure without repairing the family's
within-definition role imbalance.

This separates two ideas that earlier evidence could not: meaningful mechanical
use of an added piece is not sufficient for candidate fairness, and a broad A/B
mix across definitions is not evidence that any one definition is balanced. The
negative result is complete rather than threshold-adjacent: there is no candidate
case to extend, retune, or inspect into qualification.

## Decision

Close Plan 0010 as `NOT_SUPPORTED_TWO_RUNNER_SETUP` and preserve all three stages
as immutable negative evidence. Do not build a two-runner generator, add a third
runner, combine two runners with capture or stalemate draw, relax the candidate
threshold, add cases, or tune vector bands against this result.

Before adding a new action primitive, compare one bounded 4×4 evaluator-
calibration lane against retiring the narrow 3×3 place-versus-move family. A 4×4
lane may test whether the current strong evaluator can produce trustworthy,
non-horizon discrimination outside the exactly solved 3×3 domain; it must not be
called a family-viability result without independent ground truth. If that bounded
calibration cannot establish a trustworthy signal at fixed cost, retire this
family and pivot the initial game universe rather than stacking exceptions.

Evidence:

- [`../corpora/two-runner-v1/manifest.json`](../corpora/two-runner-v1/manifest.json)
- [`../runs/20260831T042721207815Z-two-runner-exact-3b7757ad/run.json`](../runs/20260831T042721207815Z-two-runner-exact-3b7757ad/run.json)
- [`../runs/20260831T043600138223Z-two-runner-depth5-2353bfb8/run.json`](../runs/20260831T043600138223Z-two-runner-depth5-2353bfb8/run.json)
