> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Report 0008 — B move-capture paired counterplay result

Capture-on-entry produced substantial direct counterplay without exact censoring or
`PLY_LIMIT` outcomes. It changed 61 baseline A wins into B wins, met both
predeclared raw-response thresholds, and executed captures in 86 exact principal
variations. The adaptive stress stage also completed every selected case without a
node censor or directional error.

The formal experiment result nevertheless remains `INCONCLUSIVE`. Eighty-eight
cases were stress-eligible, so the frozen 32-case cap left 56 eligible cases
untested. The interaction-frontier `category` is therefore `null`, its
`descriptive_category` is only `ROLE_DIVERSE`, and
`overall_interaction_response` is `INCONCLUSIVE`. The selected strong evidence
also carries a severe dominance warning: all 32 profiles were 30–0, with 29
`B_DOMINANT` and three `A_DOMINANT` cases.

## Evidence chain

The schema-v3 implementation and protocol were committed before any treatment
outcome at `c90ec9a` and recorded as the clean pre-outcome checkpoint `e92bc03`.
The outcome-free paired manifest was then generated from that checkpoint and
archived at `c33496f`:

- manifest ID: `generator-v2-3x3-capture-paired-v1`;
- manifest SHA-256:
  `6bc466453f60bc4ae2a6401fc76a77eebe4a7ebee82111e53ac4463400588f4f`;
- 128 pairs: all four `max_plies=18` representatives in each of 32 structural
  strata;
- source landscape-manifest SHA-256:
  `f407aefb5fdb8c926db282ff90d2feb1a8666cda3fdbd6925b9f5cc07abd87b1`;
- source landscape raw SHA-256:
  `1edf571bc140a0cd586340eafee2306bccf6ca3a0816f8809b07edc9ef1a9fa4`;
- manifest provenance records that no capture-treatment outcome or
  case-membership outcome field was consulted.

The raw paired stage executed once from clean manifest commit `c33496f` as
`20260830T225920216640Z-capture-6bc46645`. Its `run.json` SHA-256 is
`e4fc6e97d6307d025784487956911c9e0af7ea41365cb5955520f2a31c3f21af`,
and its reservation, attempt, and result were archived at `9656d59`. The fresh
baseline replay and pinned baseline each retained 128 ordered case digests and the
same attestation root,
`3408634dd0648244a9f24ca6049adc9dcc9d390288c33beef0676b0fe672b65d`.

The adaptive stress stage then executed once from committed raw commit `9656d59`
as `20260830T230308952280Z-capture-stress-e4fc6e97`. Its `run.json` SHA-256 is
`9d12a317a25d2393a0174272bfa1e858592f240f9211f5fb7d3e4a5408d4f742`,
and its reservation, attempt, and result were archived at `034759a`. Both outcome
stages report clean source commits. No failure replacement or rerun exists.

A read-only closeout reconstruction matched the source and archive byte hashes,
Git ancestry, reservations, attempts, frozen fingerprints, raw selection, stress
selection scores and order, final reason union, all exact evidence, and all 960
strong-game traces. It found no P0, P1, or P2 evidence defect. The canonical raw
aggregate, stress aggregate, and final inspection SHA-256 values are respectively
`1c1a487e4dcb3fe05eb9abece28af32ae198c756debc8e75f8ca8a45ae727601`,
`dab460036935c0f9b2102ca1ec96511b009f144574feed2643ed3301b2359a41`,
and `ba518379f0e102578e11bb0f40a194eed633802a29b0c66e89e7e818405f7b16`.

## Predeclared assessments

| Dimension | Observation | Formal outcome |
|---|---|---|
| Integrity and provenance | Replay, pair identity, ancestry, locks, action traces, aggregates, state bound, and monotonicity matched | passed |
| Exact completion | 128/128 completed; no state censor; maximum 19,158 states below the 43,776 structural bound | `SUPPORTED` |
| Primary counterplay response | 37 paired-valid baseline A containment wins became non-horizon B goal wins across 23 strata | `SUPPORTED` |
| Realized-capture response | 74 paired-valid non-horizon treatment PVs executed a capture across 26 strata | `SUPPORTED` |
| Cycling dominance | 0 `PLY_LIMIT` outcomes versus 37 non-horizon B wins in the declared pool | `NOT_DOMINANT` |
| Adaptive-stress disposition | No exact censor or integrity stop | `ELIGIBLE` |
| General strong response | 32 completions, no node censor or direction error, but 56 eligible cases exceeded the candidate cap | `INCONCLUSIVE` (`CANDIDATE_CAP_CENSORING`) |
| Interaction frontier | 32 cases in 17 strata; exact A/B = 3/29 | status `INCONCLUSIVE`; `category=null`; descriptive only `ROLE_DIVERSE` |
| Overall interaction response | Frontier completeness is censored by the candidate cap | `INCONCLUSIVE` |
| Next branch | No complete-evidence validation or rejection branch fires | `INCONCLUSIVE` |

The descriptive presence of both exact roles cannot be promoted to the formal
`ROLE_DIVERSE` category. Likewise, the observed 29-to-3 B skew cannot be promoted
to `ONE_SIDED_B` while 56 eligible cases remain untested.

## Paired exact response

The replayed baseline contained 93 A wins and 35 B wins. Treatment exact solving
completed all 128 cases with 1,288,816 searched states in total and at most 19,158,
producing 32 A wins and 96 B wins:

| Baseline → treatment | Cases |
|---|---:|
| `A_WIN → A_WIN` | 32 |
| `A_WIN → B_WIN` | 61 |
| `B_WIN → B_WIN` | 35 |

All 128 monotonicity checks passed. Treatment terminals were 106 `GOAL` and 22
`NO_LEGAL_ACTION`; there were no draws, exact censors, or `PLY_LIMIT` results.
One hundred pairs were valid under both baseline and treatment analysis gates.

Capture was mechanically consequential:

- 86/128 treatment PVs executed at least one capture;
- 14 value-changing cases had no realized PV capture, demonstrating a capture-
  threat effect rather than merely counting the new action kind;
- 53 PVs contained replacement recapture;
- 45 contained both replacement recapture and a repeated board-plus-side position;
- all 45 capture/replace-cycle PVs still reached a non-horizon terminal.

The strongest structural separator was B vector count:

| Vector band | Paired-valid | Primary response | Realized capture | A wins | B wins |
|---|---:|---:|---:|---:|---:|
| 1–3 | 10 | 4 | 3 | 24 | 8 |
| 4 | 28 | 12 | 20 | 4 | 28 |
| 5 | 30 | 12 | 22 | 4 | 28 |
| 6–7 | 32 | 9 | 29 | 0 | 32 |

Capture therefore countered A containment, but increasing B mobility rapidly
changed the family from A-favored obstruction to B-favored reachability.

Cheap play ran on all 100 analysis-gate-valid treatments. Weak random play executed
3,076 captures in 1,791/3,000 games and produced 28 capture/replace-cycle games.
Medium goal-directed play executed 791 captures in 755/3,000 games and produced no
capture cycle. The treatment failure census was `B_DOMINANT` 96,
`AGENT_DISAGREEMENT` 72, `TOO_SHORT` 47, and `A_DOMINANT` 7.

## Adaptive interaction stress

Eighty-eight paired-valid, exact-completed, non-horizon cases were eligible. Fifty
were in the frozen clean tier and 38 in the other tier; the first 32 clean cases by
the registered hash order were evaluated. All 32 completed 30 seeds at depth 5,
expanding 2,197,025 nodes in total and at most 120,596. There was no node censor and
every sampled direction matched the exact result.

All selected cases qualified descriptively for the interaction frontier because
they completed, matched exact direction, avoided frozen duration and draw failures,
and executed at least one capture. Their exact census was 29 B wins and three A
wins across 17 strata.

The 960 strong games were not balanced within any definition:

- 870 B wins and 90 A wins, all by `GOAL`;
- every definition was 30–0 in its exact direction;
- failure codes were exactly 29 `B_DOMINANT` and three `A_DOMINANT`;
- no `TOO_SHORT`, `TOO_LONG`, `EXCESSIVE_DRAWS`, or directional-error code
  occurred;
- 469/960 games executed a capture, with 595 captures in total;
- mean length was 5.45 plies, median 4, and range 4–16;
- 522/960 games ended at ply 4 and 761/960 by ply 6;
- sampled traces contained six replacement-recapture games, four repeated-position
  games, and two capture/replace-cycle games.

`CLEAN` refers only to the pre-stress duration/draw selection tier. Dominance was
deliberately retained as an observation and did not exclude a diagnostic
interaction-frontier case. Thus `CLEAN`, `INTERACTION_FRONTIER`, and `B_DOMINANT`
may coexist without an integrity contradiction.

## Frozen exploratory inspection

The raw record selected 16 of 61 outcome changes and 16 of 67 unchanged controls.
The stress record added all 32 stress-selected interaction-frontier cases. Six
stress cases overlapped the raw outcome-change sample, yielding 58 unique rows:

| Inclusion-reason combination | Cases |
|---|---:|
| `OUTCOME_CHANGE_SAMPLE` only | 10 |
| `OUTCOME_UNCHANGED_CONTROL` only | 16 |
| `INTERACTION_FRONTIER` + `STRESS_SELECTED` | 26 |
| all three non-control reasons | 6 |

There was no raw-selection shortfall. The final inspection retained the declared
56-case stress shortfall. Forty-nine of the 58 rows were paired-valid; the nine
paired-invalid rows were unchanged raw controls and did not enter a response or
frontier conclusion. The selected exact outcomes were 12 A wins and 46 B wins.

Forty-one selected PVs executed 168 captures. Seventeen executed none, including
seven value-changing capture-threat cases. Twenty-two selected PVs met the strict
capture/replace-cycle definition; every such PV lasted 16–18 plies, and 15 lasted
the full 18 plies before reaching a `GOAL`. These lines commonly alternated
replacement and recapture over two canonical cells. They are a real long-line
structural warning, but they are not `PLY_LIMIT` outcomes and therefore do not
satisfy the registered cycling-dominance condition.

Notation below: inclusion is `chg`, `ctl`, or `S+F` for the frozen changed sample,
unchanged control, or stress-selected interaction frontier. `A/G9→B/G18` is the
baseline-to-treatment exact result/reason/PV length. Capture-PV suffix `R` means
replacement recapture and `C` means the strict repeated capture/replace cycle.
Strong entries are A/B/draw wins, mean plies, games with capture, and failures.

| Pair | Inclusion | Structure | Valid | Exact transition | Capture PV | Cheap failures | Strong profile |
|---:|---|---|:---:|---|---:|---|---|
| 001 | chg | A/aligned/edge/v3 | Y | `A/G9→B/G18` | `7C` | disagreement, B-dom | — |
| 002 | S+F | A/aligned/edge/v3 | Y | `A/G9→A/G17` | `6C` | — | `30/0/0; p6.9; cap9; A-dom` |
| 004 | S+F | A/aligned/edge/v3 | Y | `A/N7→B/G4` | `0` | disagreement, B-dom | `0/30/0; p4.3; cap11; B-dom` |
| 005 | S+F | A/aligned/edge/v4 | Y | `A/N9→B/G6` | `1` | disagreement, B-dom | `0/30/0; p4.5; cap14; B-dom` |
| 007 | S+F | A/aligned/edge/v4 | Y | `B/G4→B/G8` | `1` | B-dom | `0/30/0; p4.3; cap12; B-dom` |
| 009 | S+F | A/aligned/edge/v5 | Y | `B/G4→B/G6` | `1` | B-dom | `0/30/0; p5.1; cap18; B-dom` |
| 011 | S+F | A/aligned/edge/v5 | Y | `A/N3→B/G18` | `7C` | disagreement, B-dom | `0/30/0; p5.3; cap18; B-dom` |
| 013 | S+F | A/aligned/edge/v6 | Y | `B/G4→B/G10` | `2R` | disagreement, B-dom | `0/30/0; p5.2; cap14; B-dom` |
| 014 | S+F | A/aligned/edge/v6 | Y | `A/N3→B/G18` | `7C` | disagreement, B-dom | `0/30/0; p6.0; cap17; B-dom` |
| 015 | ctl | A/aligned/edge/v6 | Y | `B/G4→B/G18` | `6C` | B-dom | — |
| 016 | S+F | A/aligned/edge/v6 | Y | `A/N9→B/G18` | `7C` | disagreement, B-dom | `0/30/0; p5.7; cap19; B-dom` |
| 017 | ctl | A/aligned/corner/v1 | N | `A/N1→A/N1` | `0` | — | — |
| 018 | chg+S+F | A/aligned/corner/v3 | Y | `A/N7→B/G4` | `0` | disagreement, B-dom | `0/30/0; p4.1; cap13; B-dom` |
| 019 | ctl | A/aligned/corner/v3 | N | `A/N1→A/N1` | `0` | — | — |
| 020 | S+F | A/aligned/corner/v3 | Y | `A/N1→A/G7` | `1` | disagreement, A-dom | `30/0/0; p7.2; cap9; A-dom` |
| 022 | chg+S+F | A/aligned/corner/v4 | Y | `A/N1→B/G18` | `6C` | disagreement, B-dom | `0/30/0; p4.5; cap10; B-dom` |
| 023 | chg+S+F | A/aligned/corner/v4 | Y | `A/G9→B/G8` | `1` | disagreement, B-dom | `0/30/0; p5.5; cap19; B-dom` |
| 024 | S+F | A/aligned/corner/v4 | Y | `A/G11→B/G18` | `7C` | disagreement, B-dom | `0/30/0; p6.1; cap19; B-dom` |
| 025 | S+F | A/aligned/corner/v5 | Y | `A/G7→B/G18` | `7C` | disagreement, B-dom | `0/30/0; p5.7; cap15; B-dom` |
| 026 | chg+S+F | A/aligned/corner/v5 | Y | `A/N7→B/G8` | `1` | B-dom | `0/30/0; p4.7; cap15; B-dom` |
| 028 | S+F | A/aligned/corner/v5 | Y | `A/N1→B/G10` | `1` | disagreement, B-dom | `0/30/0; p4.5; cap10; B-dom` |
| 029 | chg+S+F | A/aligned/corner/v6 | Y | `A/G7→B/G18` | `7C` | disagreement, B-dom | `0/30/0; p5.8; cap16; B-dom` |
| 030 | chg | A/aligned/corner/v6 | Y | `A/G7→B/G14` | `3R` | disagreement, B-dom | — |
| 032 | S+F | A/aligned/corner/v6 | Y | `A/G7→B/G18` | `7C` | disagreement, B-dom | `0/30/0; p5.7; cap16; B-dom` |
| 034 | ctl | A/orthogonal/edge/v1 | N | `A/N1→A/N1` | `0` | — | — |
| 036 | ctl | A/orthogonal/edge/v3 | N | `A/N1→A/N3` | `1` | — | — |
| 037 | S+F | A/orthogonal/edge/v4 | Y | `A/G7→B/G6` | `1` | disagreement, B-dom | `0/30/0; p5.3; cap18; B-dom` |
| 039 | S+F | A/orthogonal/edge/v4 | Y | `A/N7→B/G4` | `0` | disagreement, B-dom | `0/30/0; p4.1; cap12; B-dom` |
| 040 | ctl | A/orthogonal/edge/v4 | N | `A/N3→A/N5` | `1` | — | — |
| 041 | S+F | A/orthogonal/edge/v5 | Y | `A/N5→B/G6` | `1` | B-dom | `0/30/0; p4.7; cap14; B-dom` |
| 043 | chg | A/orthogonal/edge/v5 | Y | `A/G5→B/G18` | `7C` | disagreement, B-dom | — |
| 044 | ctl | A/orthogonal/edge/v5 | Y | `B/G4→B/G4` | `0` | B-dom | — |
| 045 | S+F | A/orthogonal/edge/v6 | Y | `A/N3→B/G18` | `7C` | disagreement, B-dom | `0/30/0; p5.9; cap15; B-dom` |
| 046 | S+F | A/orthogonal/edge/v7 | Y | `B/G4→B/G18` | `7C` | disagreement, B-dom | `0/30/0; p5.0; cap13; B-dom` |
| 047 | chg | A/orthogonal/edge/v7 | Y | `A/N3→B/G18` | `7C` | disagreement, B-dom | — |
| 050 | ctl | A/orthogonal/corner/v3 | N | `A/N1→A/N1` | `0` | — | — |
| 051 | ctl | A/orthogonal/corner/v3 | N | `A/N9→A/G17` | `5C` | — | — |
| 053 | S+F | A/orthogonal/corner/v4 | Y | `A/N1→B/G16` | `7C` | disagreement, B-dom | `0/30/0; p4.0; cap9; B-dom` |
| 054 | chg | A/orthogonal/corner/v4 | Y | `A/N9→B/G10` | `2R` | disagreement, B-dom | — |
| 055 | S+F | A/orthogonal/corner/v4 | Y | `A/G11→B/G16` | `7C` | disagreement, B-dom | `0/30/0; p5.3; cap16; B-dom` |
| 056 | chg | A/orthogonal/corner/v4 | Y | `A/G9→B/G4` | `1` | disagreement, B-dom | — |
| 058 | S+F | A/orthogonal/corner/v5 | Y | `A/N5→B/G4` | `1` | disagreement, B-dom | `0/30/0; p5.4; cap16; B-dom` |
| 061 | S+F | A/orthogonal/corner/v6 | Y | `A/N7→B/G16` | `7C` | disagreement, B-dom | `0/30/0; p5.7; cap16; B-dom` |
| 064 | S+F | A/orthogonal/corner/v6 | Y | `A/N5→B/G4` | `1` | disagreement, B-dom | `0/30/0; p5.6; cap16; B-dom` |
| 074 | S+F | B/aligned/edge/v5 | Y | `A/N2→B/G9` | `0` | disagreement, A-dom, B-dom | `0/30/0; p6.8; cap19; B-dom` |
| 079 | ctl | B/aligned/edge/v6 | Y | `B/G5→B/G9` | `1` | disagreement, B-dom, short | — |
| 085 | chg | B/aligned/corner/v4 | Y | `A/N6→B/G17` | `6C` | B-dom, short | — |
| 086 | chg | B/aligned/corner/v4 | Y | `A/N6→B/G7` | `1` | B-dom, short | — |
| 087 | chg | B/aligned/corner/v4 | Y | `A/G6→B/G9` | `0` | disagreement, B-dom, short | — |
| 098 | ctl | B/orthogonal/edge/v1 | N | `A/N0→A/N0` | `0` | — | — |
| 100 | ctl | B/orthogonal/edge/v1 | N | `A/N0→A/N0` | `0` | — | — |
| 104 | chg+S+F | B/orthogonal/edge/v4 | Y | `A/G8→B/G5` | `0` | disagreement, A-dom, B-dom | `0/30/0; p6.4; cap16; B-dom` |
| 108 | ctl | B/orthogonal/edge/v5 | Y | `B/G5→B/G5` | `0` | B-dom, short | — |
| 109 | ctl | B/orthogonal/edge/v6 | Y | `B/G5→B/G17` | `6C` | disagreement, B-dom, short | — |
| 111 | chg | B/orthogonal/edge/v6 | Y | `A/N2→B/G5` | `0` | disagreement, A-dom, B-dom | — |
| 117 | ctl | B/orthogonal/corner/v4 | Y | `B/G3→B/G5` | `0` | disagreement, B-dom, short | — |
| 121 | S+F | B/orthogonal/corner/v5 | Y | `A/N12→A/G18` | `5C` | A-dom | `30/0/0; p9.3; cap15; A-dom` |
| 127 | ctl | B/orthogonal/corner/v6 | Y | `B/G3→B/G3` | `0` | B-dom, short | — |

The inspection sample is outcome- and stress-selected rather than prevalence
weighted. Its 46/58 B result and 44/58 A-first composition must not be treated as
population estimates; the full 128-case raw aggregate remains authoritative.

## Interpretation and decision

Capture-on-entry passed the narrow counterplay test. It directly broke A
containment in many strata, changed exact value even through capture threat alone,
and did not produce a single horizon outcome. This is materially different from
the stalemate-label treatment.

It did not establish a useful or fair discovery substrate. Exact response became
strongly B-skewed above three movement vectors, and stronger sampled play produced
no internally balanced case: every evaluated definition was a 30–0 role-dominant
profile. Long replacement-recapture motifs also remain visible in exact optimal
lines even though they did not become sampled or exact horizon draws.

The formal result remains `INCONCLUSIVE`. Candidate-cap censoring prevents a
complete frontier category, so neither the descriptive `ROLE_DIVERSE` observation
nor the 29-to-3 B skew may be converted into a registered validation or
`ONE_SIDED_B` rejection branch. Do not raise the cap, rerun the frozen stage,
change thresholds, stack stalemate draw onto capture, or promote an inspected case
as a candidate.

Close Plan 0008 as `CLOSE_INCONCLUSIVE_WITHOUT_CAP_EXTENSION`. No registered
capture-validation branch fired. Preserve capture as evidence that direct
interaction can move exact value, together with the severe dominance warning. A
separate outcome-blind boundary-replication plan may test fresh D4 orbits without
changing this result or completing the 56 unselected cases post hoc.

Evidence:

- [`../corpora/capture-v1/manifest.json`](../corpora/capture-v1/manifest.json)
- [`../runs/20260830T225920216640Z-capture-6bc46645/run.json`](../runs/20260830T225920216640Z-capture-6bc46645/run.json)
- [`../runs/20260830T230308952280Z-capture-stress-e4fc6e97/run.json`](../runs/20260830T230308952280Z-capture-stress-e4fc6e97/run.json)
