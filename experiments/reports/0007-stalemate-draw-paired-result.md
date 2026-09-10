> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Report 0007 — Stalemate-draw paired terminal-semantics result

The single schema-v2 treatment behaved exactly as specified, but it did not open a
discovery frontier. It converted 20 baseline A wins into natural stalemate draws;
18 of those definitions were already static rejects, and the two static-valid
draws both collapsed to all-draw depth-5 play with frozen shape failures. The
predeclared overall treatment-discovery result is `NOT_SUPPORTED`, and the next
branch is one separately versioned direct-interaction test.

## Evidence chain

The implementation and protocol were frozen before any treatment outcome at commit
`e8bac6d` and recorded as the clean pre-outcome checkpoint `e475463`. The paired
manifest was then generated without evaluating schema-v2 cases and archived at
commit `23abc90`:

- manifest ID: `generator-v2-3x3-stalemate-paired-v1`;
- manifest SHA-256:
  `ed9a9b93ad234f4375ded0e135f5436c82fb127988784a86aa33ab4f776ff176`;
- selection fingerprint:
  `a5392b176481a72db5eea6dfe0c470f310e7413ca2a0005f09afd51eb674c426`;
- 128 pairs: all four representatives in each of the 32 `max_plies=18`
  strata from the frozen landscape manifest;
- source landscape-manifest SHA-256:
  `f407aefb5fdb8c926db282ff90d2feb1a8666cda3fdbd6925b9f5cc07abd87b1`.

The raw paired run executed once from the clean manifest commit as
`20260830T214033891685Z-stalemate-ed9a9b93`. Its `run.json` SHA-256 is
`239ad79d8009be95362efa956cbd356130faa3cd0223df5e897de0fa9d04335c`.
The run and attempt were archived at `253004d`; its one-shot reservation was fully
archived at `787ecd1`.

The adaptive stress stage then executed once from that committed raw chain as
`20260830T214159802995Z-stalemate-stress-239ad79d`. Its `run.json` SHA-256 is
`c05175254b16386f6c8c060f8c43a925ffd8f30a52f5a78d3d0cc0c6b95bb88f`,
and its reservation, attempt, and result were archived together at `e81d2b4`.
Both outcome stages report clean source commits and the frozen executable
fingerprints. No failure evidence, replacement, or rerun exists.

An independent read-only closeout audit checked source and archive byte hashes,
Git ancestry, reservations, attempts, canonical paths, public result validators,
runner-side provenance validators, candidate-derived aggregates, and inspection
selection. It found no result or assessment mismatch. The reconstructed raw
aggregate, stress aggregate, and inspection-selection SHA-256 prefixes were
`e8c272a1`, `7d3e7c7d`, and `f7fbe9c6` respectively.

There is one evidence-completeness limitation. The runner could not enter treatment
evaluation until an in-memory fresh v1 replay matched all 128 frozen baseline cases,
and an independent pre-outcome replay also matched exact, static, and cheap evidence.
However, the sealed raw JSON retains only the replay timing and a derived match
count, not the timing-free replay candidates or their digest. The run remains a
valid result because its frozen control flow and attestations are intact, but the
fresh replay event cannot be reconstructed from the raw artifact alone. Future
paired protocols must preserve a candidate-level replay attestation.

## Predeclared assessments

| Dimension | Observation | Outcome |
|---|---|---|
| Exact completion | 128/128 completed; no state-cap censoring | `SUPPORTED` |
| Clean non-horizon response | 0 treatment `PLY_LIMIT` results; every draw ended by `NO_LEGAL_ACTION` | `SUPPORTED` |
| Semantic response | 2 static-valid post-action stalemate draws in 2 strata; the threshold was 4 draws in at least 2 strata | `INCONCLUSIVE` (`FEWER_THAN_4_DRAWS_OR_2_STRATA`) |
| General draw stress | 2/2 eligible cases completed, but the declared minimum was 15 | `INCONCLUSIVE` (`FEWER_THAN_15_COMPLETIONS`) |
| Frontier completeness | No shape-clean draw, exact censor, node censor, unselected eligible draw, or directional error | `COMPLETE` |
| Frontier response | 0 diagnostic-frontier cases | `NOT_SUPPORTED` |
| Overall treatment discovery | Complete frontier evidence contains no qualifying case | `NOT_SUPPORTED` |
| Next branch | Reject stalemate draw as the next discovery direction | `DESIGN_DIRECT_INTERACTION_TEST` |

The general stress assessment and frontier completeness answer different questions.
Two cases cannot validate draw handling generally, but no untested shape-clean case
can conceal a positive frontier in this corpus.

## Paired exact response

The fresh v1 baseline was 93 A wins and 35 B wins. Its optimal terminals were 60
`GOAL` and 68 `NO_LEGAL_ACTION`. Treatment exact solving completed all 128 cases
with 192,059 searched states in total and at most 2,975, producing 73 A wins, 35 B
wins, and 20 draws:

| Baseline → treatment | Cases |
|---|---:|
| `A_WIN → A_WIN` | 73 |
| `A_WIN → DRAW` | 20 |
| `B_WIN → B_WIN` | 35 |

No A win became a B win, and no B win changed. The policy therefore isolated one
mechanism: it removed A wins awarded for immobilizing B. Of the 20 new draws, four
were initial immobility (`PV=0`) and 16 were post-action stalemates. Eighteen were
static rejects with `UNREACHABLE_WIN_CONDITION`; the four initial cases also had
`NO_LEGAL_MOVE_AT_START`. Only two were static-valid.

The draws were concentrated in sparse B movement: exact vector counts one through
five contributed 4, 6, 8, 1, and 1 draws respectively; counts six and seven
contributed none. The treatment draw PV histogram was four at ply 0, eight at ply
1, five at ply 2, and three at ply 4. This is short obstruction, not delayed
strategic equilibrium.

The policy also changed optimal lines without changing the winner. Forty-eight
baseline `NO_LEGAL_ACTION` terminals rerouted to treatment `GOAL` wins, while 60
goal terminals stayed goals and 20 no-action terminals became draws. Principal
variations grew in 47 pairs, shrank in 2, and were unchanged in 79.

## Cheap and strong play

Cheap play ran on all 100 static-valid definitions. Its failure histogram was
`B_DOMINANT` 84, `AGENT_DISAGREEMENT` 68, `TOO_SHORT` 53,
`A_DOMINANT` 7, and `EXCESSIVE_DRAWS` 2. The known B-role bias of the sampled
agents therefore remains visible and cannot be interpreted as exact fairness.

The two static-valid exact draws were:

- pair 083: B moves from the corner to the adjacent row and A immediately blocks
  B's only forward destination. The identical two-ply line changed from an A win
  to a draw. Weak and medium play were both 0/26/4 A/B/draw and failed
  `B_DOMINANT` and `TOO_SHORT`. Depth 5 found 30/30 two-ply stalemate draws,
  expanded 930 nodes, and failed `EXCESSIVE_DRAWS` plus `TOO_SHORT`.
- pair 119: the baseline forced A win took 12 plies, but treatment gave B a
  four-ply drawing line after the first two shared actions. Weak play was 5/9/16,
  medium play 3/27/0, and the cheap result failed disagreement, B dominance,
  excessive draws, and short duration. Depth 5 found 30/30 four-ply stalemate
  draws, expanded 17,220 nodes, and retained `EXCESSIVE_DRAWS`.

Both strong profiles were `DRAW_OR_BALANCED`, so there was no evaluator-direction
error. Stronger play did not rescue shape; it converged on a short certain block.

## Frozen exploratory inspection

The stress record froze 32 unique inspection cases: 16 of the 20 outcome changes
and 16 of the 108 unchanged controls. Stress-selected pairs 083 and 119 overlap
the changed sample. There were no censors or frontier cases to add. Every row below
was joined back to its manifest definition, raw candidate, exact PV, static report,
and available cheap or strong profiles.

Notation: `A/N7→D/N1` means baseline A win by `NO_LEGAL_ACTION` at ply 7 became a
draw by `NO_LEGAL_ACTION` at ply 1. `G` means `GOAL`; `U` is static unreachable,
`I` initial immobility, `BD` B dominance, `AD` A dominance, `DG` agent
disagreement, `ED` excessive draws, and `TS` too short.

| Pair | Inclusion | Structure: first/axis/start/vectors | Exact transition | Static / play note |
|---|---|---|---|---|
| 004 | control | A/aligned/edge/3 | `A/N7→A/G9` | BD; optimal line reroutes |
| 010 | control | A/aligned/edge/5 | `A/N5→A/G5` | DG, BD; terminal changes at equal length |
| 014 | control | A/aligned/edge/6 | `A/N3→A/G9` | DG, BD; longer goal line |
| 017 | changed | A/aligned/corner/1 | `A/N1→D/N1` | U; same one-ply PV |
| 018 | control | A/aligned/corner/3 | `A/N7→A/G9` | DG, BD, TS |
| 019 | changed | A/aligned/corner/3 | `A/N1→D/N1` | U; same one-ply PV |
| 020 | control | A/aligned/corner/3 | `A/N1→A/G9` | DG, AD, ED; weak/medium reversal |
| 022 | control | A/aligned/corner/4 | `A/N1→A/G9` | DG, BD, TS |
| 024 | control | A/aligned/corner/4 | `A/G11→A/G11` | BD; identical PV |
| 025 | control | A/aligned/corner/5 | `A/G7→A/G7` | DG, BD; identical PV |
| 027 | control | A/aligned/corner/5 | `B/G4→B/G4` | BD, TS; identical PV |
| 036 | changed | A/orthogonal/edge/3 | `A/N1→D/N1` | U; same one-ply PV |
| 046 | control | A/orthogonal/edge/7 | `B/G4→B/G4` | DG, BD; identical PV |
| 049 | changed | A/orthogonal/corner/3 | `A/N1→D/N1` | U; same one-ply PV |
| 050 | changed | A/orthogonal/corner/3 | `A/N1→D/N1` | U; same one-ply PV |
| 052 | changed | A/orthogonal/corner/2 | `A/N1→D/N1` | U; same one-ply PV |
| 060 | changed | A/orthogonal/corner/5 | `A/N1→D/N1` | U; same one-ply PV |
| 064 | control | A/orthogonal/corner/6 | `A/N5→A/G11` | DG; longer goal line |
| 066 | changed | B/aligned/edge/2 | `A/N2→D/N2` | U; same two-ply PV |
| 068 | changed | B/aligned/edge/2 | `A/N2→D/N2` | U; same two-ply PV |
| 083 | changed + stress | B/aligned/corner/2 | `A/N2→D/N2` | BD, TS; strong 0/0/30, ED+TS |
| 084 | changed | B/aligned/corner/3 | `A/N0→D/N0` | I+U; empty PV |
| 085 | control | B/aligned/corner/4 | `A/N6→A/G8` | DG, BD, TS |
| 092 | control | B/aligned/corner/5 | `A/N6→A/G12` | DG, BD, TS |
| 094 | control | B/aligned/corner/6 | `B/G9→B/G9` | DG, BD, TS; identical PV |
| 098 | changed | B/orthogonal/edge/1 | `A/N0→D/N0` | I+U; empty PV |
| 100 | changed | B/orthogonal/edge/1 | `A/N0→D/N0` | I+U; empty PV |
| 113 | changed | B/orthogonal/corner/2 | `A/N4→D/N4` | U; same four-ply PV |
| 115 | control | B/orthogonal/corner/2 | `A/N8→A/G12` | U, but A still forces a goal |
| 116 | changed | B/orthogonal/corner/3 | `A/N0→D/N0` | I+U; empty PV |
| 119 | changed + stress | B/orthogonal/corner/4 | `A/N12→D/N4` | DG, BD, ED, TS; strong 0/0/30, ED |
| 126 | control | B/orthogonal/corner/6 | `B/G5→B/G5` | DG, BD, TS; identical PV |

Fifteen of the 16 changed inspection PVs were identical action sequences whose
terminal value was merely relabeled. Pair 119 was the only changed inspected case
where the policy altered optimal strategy before the old terminal. Among controls,
all four B wins and two A goal wins retained identical PVs; ten A containment wins
instead found an A goal line. Static rejection alone did not force a draw: pair 115
remained an A win because A could force its own goal.

The changed and control columns are fixed qualitative samples, not equal-weight
prevalence strata. The population result is 20 changes among all 128 pairs, not
16/32.

## Interpretation and decision

Schema v2 demonstrated a valid non-horizon draw mechanism, but almost all response
came from definitions already known to be structurally invalid. The two remaining
cases rewarded immediate containment. Their exact values were draws, yet weak and
medium play were strongly B-skewed and depth 5 made every game a short stalemate.
This is precisely the distinction between formal balance and a useful game shape.

Do not adopt schema v2, reweight generator v2 toward sparse movement, or relax the
four-case semantic threshold. Preserve this treatment and its negative result.
Follow the frozen `DESIGN_DIRECT_INTERACTION_TEST` branch with one B-side primitive
that directly contests A's placed seeds, while restoring schema-v1 terminal
semantics and changing no evaluator or generator variable in the same experiment.
The next test is a counterplay-response diagnostic, not a fairness-discovery claim:
with v1 terminal semantics, any exact draw still means the finite horizon bound.

Evidence:

- [`../corpora/stalemate-v1/manifest.json`](../corpora/stalemate-v1/manifest.json)
- [`../runs/20260830T214033891685Z-stalemate-ed9a9b93/run.json`](../runs/20260830T214033891685Z-stalemate-ed9a9b93/run.json)
- [`../runs/20260830T214159802995Z-stalemate-stress-239ad79d/run.json`](../runs/20260830T214159802995Z-stalemate-stress-239ad79d/run.json)
