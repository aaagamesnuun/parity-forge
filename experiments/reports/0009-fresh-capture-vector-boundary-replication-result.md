> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Report 0009 — Fresh capture vector-boundary replication result

The fresh, outcome-blind replication does **not** support the proposed
three-versus-four-vector boundary. Capture-on-entry again produced substantial,
non-horizon counterplay, but treatment exact outcomes were identical in the two
vector halves: A/B = 3/29 at both three and four vectors. Only one of eight matched
structural cells increased its B-win count, rather than the preregistered five, and
the B-win difference was 0 rather than at least 8.

All exact and depth-5 evidence completed without censoring, horizon outcomes, or
direction errors. The 52-case mechanical interaction frontier contained six A wins
and 46 B wins, but every one of the 64 treatment profiles was 30–0 in its exact
direction. Candidate-shaped interaction therefore had zero cases. Under the frozen
priority, the formal result is `NOT_SUPPORTED_VECTOR_BOUNDARY` and the next branch
is `FAMILY_REASSESSMENT`. Unrestricted capture is rejected as the next discovery
substrate; this result does not authorize a capture-aware generator.

## Evidence chain

The implementation and protocol were committed before any fresh schema-v3 outcome
at `33a735ec0e474de00100bc1adfa67249045097b2`; the clean pre-outcome checkpoint was
recorded at `249b69ac87e0cf97fc5bb416a8b8c221b5e98eb4`. All 261 tests passed, and two
independent pre-outcome reviews found no unresolved P0–P3 defect.

The one-shot outcome-free manifest chain was generated from that checkpoint and
archived at `b52fbd4cc588655dad6e68cff8575a8986d701df`:

- manifest ID: `capture-boundary-v1-64-pair-manifest`;
- manifest SHA-256:
  `e1b0f6a7aed05264133964954380e6d59b200cfe903888b2d279f2a626ebd78f`;
- exclusion-ledger SHA-256:
  `841789e168baf7446072d189ca272783c944d36d71630421f9fe70ec6a3865ea`;
- 36,720 raw definitions, 4,776 D4 orbits, 724 fresh relevant orbits, 563
  paired-analysis-valid orbits, 16 strata, and four selected pairs per stratum;
- coverage-projection root:
  `aff92eed1ff9b218431d2a92432597c10b37ddd0445fbea74c497d97f5b89164`;
- exclusion-ledger root:
  `d257fb039ec8bd8c77ca1f955fcc94dc19658d527047983740eb72772eb36889`;
- eligible-pool root:
  `f739887b3f86f2e3652b8e526f1709efc706983329994f46afed4460843c1fcc`;
- selection fingerprint:
  `8df3570000911a0d2c2ee3d052e5863f29fa2a72e64c33ccb7b9b544daa0ee56`;
- both treatment-outcome-computed and membership-outcome-consulted provenance
  flags are false.

Paired exact ran once from clean manifest commit `b52fbd4` as
`20260831T012026857459Z-capture-boundary-exact-e1b0f6a7`. Its `run.json` SHA-256 is
`cbf2ccc3235c92990d6d42377c7c81b77d4463c28b6a97a15d2ce4c0d109f5f4`, and its
reservation, attempt, and result were archived at
`ec1492b1a399a515ef46904877d09337ac70a72f`.

Fixed depth 5 then ran once from clean exact commit `ec1492b` as
`20260831T012251133134Z-capture-boundary-depth5-cbf2ccc3`. Its `run.json` SHA-256 is
`40a800b1d9f4537d7c3c783136230471adfa71ec75938d3aa0289592972d5782`, and its
reservation, attempt, and result were archived at
`1145de20c417bff2b693e52a87f60f0955cf4345`.

A post-commit read-only reconstruction authenticated the complete manifest and
exact source chains, rebuilt all 128 exact slots and all 128 depth-5 profiles from
their retained traces, matched the completed narratives, and reconstructed the
44-row inspection union. An independent post-outcome audit repeated the public
manifest, exact, depth, inspection, artifact-chain, ancestry, and assessment
checks and found no P0–P3 defect. The canonical exact aggregate, depth aggregate, and final
inspection SHA-256 values are respectively
`668e93aaa3c738f4f418ff3a8a8db1612941929cc0155937e0826df428945e39`,
`180ab4ebf5f12e1835b2b2d0850f684c6cb62598916a886887cce6ca175b023e`, and
`634a5824a0f36787f16b3154d5c86e609ff5bcb3e671eb0927e0109af90434e0`.

## Predeclared assessments

| Dimension | Observation | Formal outcome |
|---|---|---|
| Integrity and provenance | Membership, exclusions, D4 identities, one-variable pairs, ancestry, locks, schedules, traces, state bounds, monotonicity, and aggregates reconstructed | passed |
| Exact completion | 128/128 slots completed; no censor or horizon; maximum 16,135 states below the proved 43,776 bound | complete |
| Primary response | 26 valid A-containment wins became non-horizon B-goal wins across 15 strata | `SUPPORTED` |
| Realized response | 32 valid treatment PVs captured across 14 strata | `SUPPORTED` |
| Cycling dominance | 0 horizon changes versus 26 non-horizon B wins in the declared pool | `NOT_DOMINANT` |
| Strong evidence | 128/128 profiles and 3,840/3,840 games completed; no node censor or direction mismatch | `COMPLETE` |
| Mechanical boundary | B3 = 29, B4 = 29, increase 0, one improving cell, v3 A frontier 3 cases across 2 cells | `NOT_SUPPORTED_VECTOR_BOUNDARY` |
| Broad B overcorrection | 58 total B wins and 46 B-frontier cases, but six A-frontier cases exceed the maximum of three | `NOT_MET` |
| Interaction frontier | 52 cases; exact A/B = 6/46 | descriptive mechanical frontier |
| Candidate shape | Every treatment profile was role-dominant; zero qualifying cases | `NOT_SUPPORTED` |
| Overall | Explicitly unsupported vector boundary has priority after the other complete assessments | `NOT_SUPPORTED_VECTOR_BOUNDARY` |
| Next branch | Reject unrestricted capture as the next discovery substrate | `FAMILY_REASSESSMENT` |

This is not a threshold-adjacent result. The explicit negative boundary rule fires
because `B4 <= B3` and the v4 B frontier does not exceed the v3 B frontier. Broad
B overcorrection is separately not met under its stricter frozen definition, so it
must not replace the registered overall category.

## Paired exact response

All 64 source solves completed before the source evidence seal, after which all 64
treatments completed. Source outcomes were A/B = 49/15; treatment outcomes were
A/B = 6/58:

| Source → treatment | Cases |
|---|---:|
| `A_WIN → A_WIN` | 6 |
| `A_WIN → B_WIN` | 43 |
| `B_WIN → B_WIN` | 15 |

All monotonicity checks passed, and all treatment terminals were `GOAL`. Source
solving used 63,925 searched states and treatment used 419,537; the largest solve
used 16,135 states. Treatment PVs executed 82 captures in 32 cases. Seventeen
additional pairs had a capture threat without a capture in the selected treatment
PV. Seven PVs repeated a board-plus-side position, 12 contained replacement
recapture, and seven met the strict capture/replace-cycle definition, but none
ended at the horizon.

The vector split directly contradicts the proposed boundary:

| Vector count | Source A/B | Treatment A/B | A→B changes | Primary response | Realized response |
|---:|---:|---:|---:|---:|---:|
| 3 | 25/7 | 3/29 | 22 | 15 | 12 |
| 4 | 24/8 | 3/29 | 21 | 11 | 20 |

The v3 side did not retain the preregistered eight A wins; it retained three. The
v4 side met its B-win floor, but had no increase over v3. Cell-level counts were
`2→4`, `3→2`, `4→4`, `4→3`, and four instances of `4→4`; only the first cell
increased.

## Fixed depth-5 evidence

All 64 source profiles were completed and sealed before treatment play. All 64
treatment profiles then completed over the same seeds `0..29`. The run expanded
3,578,881 nodes: 1,365,849 on source games and 2,213,032 on treatments. The largest
profile used 78,946 nodes, far below the 5,000,000-node definition cap.

| Side | Profiles | Games | A/B/draw | Mean plies | Dominance failures | Too short |
|---|---:|---:|---:|---:|---|---:|
| Source | 64 | 1,920 | 1,470/450/0 | 6.26 | 49 A, 15 B | 13 |
| Treatment | 64 | 1,920 | 180/1,740/0 | 4.84 | 6 A, 58 B | 12 |

Every profile was exactly 30–0 in its exact direction. Treatment games executed
903 captures in 750/1,920 games. Eight games repeated a board-plus-side position,
six contained replacement recapture, and three met the strict cycle definition.
These are real motifs but neither censoring nor a fairness signal.

Each vector half contributed the same strong result: three A-frontier and 23
B-frontier cases, for 26 interaction-frontier cases and zero candidate-shaped
cases. The remaining 12 treatment profiles were excluded from the mechanical
frontier by `TOO_SHORT`; dominance itself was deliberately retained for frontier
diagnosis and then excluded all 64 cases from candidate shape.

## Frozen inspection

The final union contains 44 unique pairs. It includes 16 outcome-change samples,
16 unchanged controls, the 16 stratum-floor cases, and all six A-frontier cases,
with overlaps retained. There were no exact/node censors, horizons, direction
mismatches, or candidate-shaped cases to add. The four independent pools had no
shortfall: v3 change 8/22, v3 control 8/10, v4 change 8/21, and v4 control 8/11.

Notation: `chg`, `ctl`, `floor`, and `A-front` are the registered inclusion
reasons. `A/G9→B/G8` records source and treatment result, terminal reason, and PV
length; `N` means `NO_LEGAL_ACTION`. PV-capture suffix `R` denotes replacement
recapture and `C` the strict repeated capture/replace cycle. Strong treatment is
A/B/draw wins, mean plies, games with capture, and failures.

| Pair | Inclusion | Structure | Exact transition | PV capture | Strong treatment | Frontier |
|---:|---|---|---|---:|---|:---:|
| 001 | chg+floor | fA-aligned-corner/v3 | `A/G9→B/G8` | `1` | `0/30/0; p5.3; cap19; B_DOMINANT` | Y |
| 002 | A-front+ctl | fA-aligned-corner/v3 | `A/N1→A/G7` | `1` | `30/0/0; p6.5; cap12; A_DOMINANT` | Y |
| 004 | A-front+ctl | fA-aligned-corner/v3 | `A/N1→A/G17` | `6C` | `30/0/0; p8.5; cap14; A_DOMINANT` | Y |
| 005 | floor | fA-aligned-corner/v4 | `A/N7→B/G10` | `1` | `0/30/0; p4.1; cap13; B_DOMINANT` | Y |
| 006 | chg | fA-aligned-corner/v4 | `A/G9→B/G10` | `1` | `0/30/0; p5.0; cap16; B_DOMINANT` | Y |
| 007 | chg | fA-aligned-corner/v4 | `A/G7→B/G14` | `3R` | `0/30/0; p4.7; cap14; B_DOMINANT` | Y |
| 008 | chg | fA-aligned-corner/v4 | `A/N7→B/G8` | `1` | `0/30/0; p4.8; cap14; B_DOMINANT` | Y |
| 009 | A-front+ctl+floor | fA-aligned-edge_midpoint/v3 | `A/N7→A/G5` | `0` | `30/0/0; p6.1; cap4; A_DOMINANT` | Y |
| 010 | ctl | fA-aligned-edge_midpoint/v3 | `B/G4→B/G4` | `0` | `0/30/0; p4.0; cap17; B_DOMINANT` | Y |
| 013 | floor | fA-aligned-edge_midpoint/v4 | `A/N7→B/G4` | `0` | `0/30/0; p5.2; cap18; B_DOMINANT` | Y |
| 014 | A-front+ctl | fA-aligned-edge_midpoint/v4 | `A/N7→A/G5` | `0` | `30/0/0; p6.1; cap4; A_DOMINANT` | Y |
| 016 | A-front | fA-aligned-edge_midpoint/v4 | `A/G9→A/G17` | `6C` | `30/0/0; p7.1; cap9; A_DOMINANT` | Y |
| 017 | floor | fA-orthogonal-corner/v3 | `A/N1→B/G4` | `1` | `0/30/0; p4.0; cap9; B_DOMINANT` | Y |
| 019 | chg | fA-orthogonal-corner/v3 | `A/N1→B/G16` | `7C` | `0/30/0; p4.0; cap9; B_DOMINANT` | Y |
| 021 | floor | fA-orthogonal-corner/v4 | `A/G5→B/G6` | `1` | `0/30/0; p4.3; cap12; B_DOMINANT` | Y |
| 025 | floor | fA-orthogonal-edge_midpoint/v3 | `B/G4→B/G4` | `0` | `0/30/0; p4.0; cap17; B_DOMINANT` | Y |
| 026 | chg | fA-orthogonal-edge_midpoint/v3 | `A/N3→B/G4` | `0` | `0/30/0; p4.0; cap12; B_DOMINANT` | Y |
| 027 | chg | fA-orthogonal-edge_midpoint/v3 | `A/N3→B/G6` | `1` | `0/30/0; p5.0; cap15; B_DOMINANT` | Y |
| 029 | floor | fA-orthogonal-edge_midpoint/v4 | `A/G7→B/G4` | `0` | `0/30/0; p4.5; cap15; B_DOMINANT` | Y |
| 030 | chg | fA-orthogonal-edge_midpoint/v4 | `A/N5→B/G6` | `1` | `0/30/0; p4.5; cap13; B_DOMINANT` | Y |
| 031 | A-front+ctl | fA-orthogonal-edge_midpoint/v4 | `A/G5→A/G17` | `6C` | `30/0/0; p7.6; cap10; A_DOMINANT` | Y |
| 033 | ctl+floor | fB-aligned-corner/v3 | `B/G3→B/G3` | `0` | `0/30/0; p3.5; cap5; B_DOMINANT,TOO_SHORT` | N |
| 035 | ctl | fB-aligned-corner/v3 | `B/G3→B/G3` | `0` | `0/30/0; p3.4; cap5; B_DOMINANT,TOO_SHORT` | N |
| 036 | chg | fB-aligned-corner/v3 | `A/N6→B/G13` | `2` | `0/30/0; p5.6; cap15; B_DOMINANT` | Y |
| 037 | floor | fB-aligned-corner/v4 | `A/G6→B/G11` | `1` | `0/30/0; p5.9; cap11; B_DOMINANT` | Y |
| 038 | chg | fB-aligned-corner/v4 | `A/N8→B/G11` | `2R` | `0/30/0; p3.8; cap6; B_DOMINANT,TOO_SHORT` | N |
| 039 | chg | fB-aligned-corner/v4 | `A/N6→B/G11` | `2` | `0/30/0; p4.1; cap10; B_DOMINANT` | Y |
| 041 | floor | fB-aligned-edge_midpoint/v3 | `B/G3→B/G3` | `0` | `0/30/0; p3.0; cap3; B_DOMINANT,TOO_SHORT` | N |
| 042 | chg | fB-aligned-edge_midpoint/v3 | `A/G6→B/G7` | `1` | `0/30/0; p4.2; cap10; B_DOMINANT` | Y |
| 043 | chg | fB-aligned-edge_midpoint/v3 | `A/G6→B/G7` | `0` | `0/30/0; p6.1; cap14; B_DOMINANT` | Y |
| 045 | chg+floor | fB-aligned-edge_midpoint/v4 | `A/N4→B/G15` | `4R` | `0/30/0; p4.6; cap11; B_DOMINANT` | Y |
| 046 | ctl | fB-aligned-edge_midpoint/v4 | `B/G5→B/G5` | `0` | `0/30/0; p3.9; cap5; B_DOMINANT,TOO_SHORT` | N |
| 049 | floor | fB-orthogonal-corner/v3 | `A/N8→B/G3` | `0` | `0/30/0; p3.9; cap10; B_DOMINANT,TOO_SHORT` | N |
| 052 | ctl | fB-orthogonal-corner/v3 | `B/G3→B/G7` | `1` | `0/30/0; p5.1; cap13; B_DOMINANT` | Y |
| 053 | chg+floor | fB-orthogonal-corner/v4 | `A/G14→B/G15` | `6C` | `0/30/0; p4.9; cap11; B_DOMINANT` | Y |
| 054 | ctl | fB-orthogonal-corner/v4 | `B/G3→B/G3` | `0` | `0/30/0; p3.3; cap7; B_DOMINANT,TOO_SHORT` | N |
| 055 | ctl | fB-orthogonal-corner/v4 | `B/G3→B/G5` | `0` | `0/30/0; p3.9; cap7; B_DOMINANT,TOO_SHORT` | N |
| 056 | ctl | fB-orthogonal-corner/v4 | `B/G3→B/G11` | `3R` | `0/30/0; p3.9; cap10; B_DOMINANT,TOO_SHORT` | N |
| 057 | floor | fB-orthogonal-edge_midpoint/v3 | `A/N2→B/G3` | `0` | `0/30/0; p3.3; cap5; B_DOMINANT,TOO_SHORT` | N |
| 058 | chg | fB-orthogonal-edge_midpoint/v3 | `A/G8→B/G5` | `0` | `0/30/0; p6.2; cap16; B_DOMINANT` | Y |
| 059 | ctl | fB-orthogonal-edge_midpoint/v3 | `B/G3→B/G5` | `0` | `0/30/0; p3.7; cap7; B_DOMINANT,TOO_SHORT` | N |
| 061 | floor | fB-orthogonal-edge_midpoint/v4 | `A/G8→B/G5` | `0` | `0/30/0; p5.9; cap14; B_DOMINANT` | Y |
| 063 | ctl | fB-orthogonal-edge_midpoint/v4 | `B/G3→B/G3` | `0` | `0/30/0; p3.0; cap3; B_DOMINANT,TOO_SHORT` | N |
| 064 | ctl | fB-orthogonal-edge_midpoint/v4 | `B/G3→B/G5` | `0` | `0/30/0; p4.7; cap7; B_DOMINANT` | Y |

## Interpretation

Plan 0008's prior-informed separator did not replicate. In its mixed one-to-three
vector band, capture left 24 A wins out of 32, whereas the fresh three-vector-only
sample left three. The new fixed membership shows that vector count alone is not a
usable tuning lever: capture is already overwhelmingly B-favored at three vectors,
and moving to four changes neither the exact census nor the strong frontier census.

The response itself is trustworthy and mechanically real. Forty-three values
changed, both registered response thresholds were supported, capture occurred in
exact and sampled play, and there was no horizon or evaluator-censor explanation.
The failure is product-facing: capture transforms one role imbalance into another
without producing any non-dominant strong profile. The six surviving exact A cases
are not evidence of within-game fairness; every one was 30–0 for A.

The result is not the frozen broad-overcorrection category because its six
A-frontier cases exceed that category's maximum of three. It is also not the
anticipated dominance-cliff category because no vector boundary exists. The
correct formal statement is narrower and stronger than a vague inconclusive
result: the proposed vector boundary is explicitly unsupported.

## Decision

Close Plan 0009 as `NOT_SUPPORTED_VECTOR_BOUNDARY` with next branch
`FAMILY_REASSESSMENT`. Do not adopt schema v3, build a capture-aware generator,
combine capture with stalemate draw, tune vector counts against this result, run
Plan 0008's 56 unselected cases, or add cases to this replication. Preserve all
three evidence stages as immutable negative evidence.

Before implementing another primitive, reassess the place-versus-move family and
compare the information value and complexity of a single alternative interaction
against pivoting the initial search universe. Any later mechanic must be a separate
one-variable hypothesis with outcome-blind membership; it may not stack on
capture to rescue this result.

Evidence:

- [`../corpora/capture-boundary-v1/manifest.json`](../corpora/capture-boundary-v1/manifest.json)
- [`../runs/20260831T012026857459Z-capture-boundary-exact-e1b0f6a7/run.json`](../runs/20260831T012026857459Z-capture-boundary-exact-e1b0f6a7/run.json)
- [`../runs/20260831T012251133134Z-capture-boundary-depth5-cbf2ccc3/run.json`](../runs/20260831T012251133134Z-capture-boundary-depth5-cbf2ccc3/run.json)
