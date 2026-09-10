> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Report 0006 — Three-by-three exact-outcome landscape result

The outcome-independent landscape protocol completed all three immutable stages.
The selected sample contains no diagnostic-frontier case. This makes blind
generator-v2 reweighting a low-value next step under the preregistered decision
rule and advances a minimal terminal-semantics test.

## Evidence chain

The executable protocol was frozen at commit
`02174d904cdd27367d22e3d6aadcc9e197b0816e`. From that clean state, the manifest
was generated without calling an evaluator or solver and then archived at commit
`d7ddc04b3d4a918ea50ca86971cc8a9ddc201910`:

- manifest ID: `generator-v2-3x3-landscape-v1`;
- manifest SHA-256:
  `f407aefb5fdb8c926db282ff90d2feb1a8666cda3fdbd6925b9f5cc07abd87b1`;
- 36,720 enumerated definitions, 4,776 D4 orbits, 4,702 eligible orbits after
  known-orbit and eight-vector exclusions;
- 384 selected definitions: four outcome-blind representatives in each of 96
  declared strata.

The raw evaluation ran once from that manifest commit as
`20260830T200230881318Z-landscape-f407aefb`. Its `run.json` SHA-256 is
`1edf571bc140a0cd586340eafee2306bccf6ca3a0816f8809b07edc9ef1a9fa4`; the
reservation, attempt, and result were archived at commit
`da867573710ba2dc0b064aeb6bc79bdf2cfcb869`.

The adaptive stress lane then ran once from that committed raw record as
`20260830T200513661140Z-draw-stress-1edf571b`. Its `run.json` SHA-256 is
`172c36f733ba4ba7cf214369141700d6af17b4c58365d16bb90bcbdd76af3588`; the
reservation, attempt, and result were archived at commit
`0b72ec60caba459eb686245247f806fcd93f9f2c`. Both outcome runs report a clean
source commit. No replacement,
rerun, or source-code change occurred between their reserved stages.

A post-run read-only audit in the closeout session used the frozen public
generator, evaluator, engine, and solver functions to reconstruct the 384-case
manifest without consulting outcomes, rerun all 384 exact solves and principal
variations, rerun 610 cheap profiles comprising 18,300 games, and recompute every
raw aggregate. It found no byte, provenance, selection, replay, or aggregate
mismatch. This was an audit of the archived evidence, not a separately archived
experiment run.

## Predeclared assessments

| Dimension | Observation | Outcome |
|---|---|---|
| Exact completion | 384/384 completed; no state-cap censoring | `SUPPORTED` |
| General draw stress | 13/13 selected draws completed with no node or candidate-cap censoring and no decisive error, but the declared minimum was 15 | `INCONCLUSIVE` (`FEWER_THAN_15_COMPLETIONS`) |
| Frontier completeness | The sole shape-clean exact draw was selected and completed; no exact or depth-5 censoring and no unselected shape-clean draw | `COMPLETE` |
| Diagnostic frontier | 0 cases | `DESIGN_MINIMAL_MECHANIC_TEST` |

The general stress assessment and the frontier-completeness assessment answer
different questions. The small number of exact draws prevents a confirmatory claim
about depth-5 draw handling, but it cannot hide a qualifying frontier case because
every shape-clean draw was tested without censoring.

## Structural and exact landscape

All 384 definitions passed the frozen asymmetry and simplicity gates. Static
analysis passed 305; the diagnostic histogram contained 79
`UNREACHABLE_WIN_CONDITION` and 10 `NO_LEGAL_MOVE_AT_START` codes, with overlap.
All 79 static-rejected cases were exact A wins, leaving 177 A wins, 115 B wins,
and 13 draws among the 305 static-valid cases.

Exact solving searched 405,771 states in total, at most 2,975 for one definition,
and took 28.24 seconds of the 35.53-second raw run. The full exact result was 256 A
wins, 115 B wins, and 13 draws. These counts describe the equal-stratum sample;
they are not generator-v2 prevalence estimates.

| Dimension | Value | Cases | A win | B win | Draw |
|---|---:|---:|---:|---:|---:|
| First player | A | 192 | 162 | 25 | 5 |
|  | B | 192 | 94 | 90 | 8 |
| Goal-axis relation | aligned | 192 | 126 | 53 | 13 |
|  | orthogonal | 192 | 130 | 62 | 0 |
| Runner start | corner | 192 | 132 | 53 | 7 |
|  | edge midpoint | 192 | 124 | 62 | 6 |
| Maximum plies | 6 | 128 | 80 | 37 | 11 |
|  | 9 | 128 | 83 | 43 | 2 |
|  | 18 | 128 | 93 | 35 | 0 |
| Vector-count band | 1–3 | 96 | 94 | 2 | 0 |
|  | 4 | 96 | 73 | 20 | 3 |
|  | 5 | 96 | 55 | 38 | 3 |
|  | 6–7 | 96 | 34 | 55 | 7 |

The required exact-vector-count breakdown was:

| Exact movement vectors | Cases | A win | B win | Draw |
|---:|---:|---:|---:|---:|
| 1 | 10 | 10 | 0 | 0 |
| 2 | 28 | 28 | 0 | 0 |
| 3 | 58 | 56 | 2 | 0 |
| 4 | 96 | 73 | 20 | 3 |
| 5 | 96 | 55 | 38 | 3 |
| 6 | 78 | 30 | 41 | 7 |
| 7 | 18 | 4 | 14 | 0 |

Exact search cost rose with movement vocabulary: median searched states were 9,
45, 265, 632.5, 1,232.5, 2,062, and 2,086 for exact vector counts one through
seven. This cost gradient did not approach the 100,000-state cap.

Every exact draw ended at `PLY_LIMIT`. All 13 used aligned goals, 11 used the
six-ply cap, two used the nine-ply cap, and none used the nonbinding 18-ply cap.
Draws occurred only with four through six movement vectors. The concentration is a
descriptive hypothesis about horizon interaction, not proof that unsampled orbits
contain no other behavior.

## Cheap-versus-exact diagnostics

Cheap play ran on all 305 static-valid cases and took 7.18 seconds. Only three had
no cheap failure code; exact solving proved all three were A wins. Failure counts
were `B_DOMINANT` 240, `AGENT_DISAGREEMENT` 180, `TOO_SHORT` 186,
`EXCESSIVE_DRAWS` 49, `TOO_LONG` 47, and `A_DOMINANT` 45.

On the 292 cheap-evaluated forced results, weak random play pointed in the exact
direction 182 times (62.3%), while medium goal-directed play did so 151 times
(51.7%). Weak random classified 216/305 profiles toward B; medium goal-directed
classified 255/305 toward B and classified every exact draw toward B. This
reconfirms that the current goal-directed policy has a strong B-role bias and is
not a monotone strength proxy.

The full sampled-direction-to-exact confusion counts were:

| Profile | Sampled direction | Exact A win | Exact B win | Exact draw |
|---|---|---:|---:|---:|
| weak random | A | 72 | 3 | 1 |
|  | B | 94 | 110 | 12 |
|  | balanced | 11 | 2 | 0 |
| medium goal-directed | A | 38 | 2 | 0 |
|  | B | 129 | 113 | 13 |
|  | balanced | 10 | 0 | 0 |

The one exact draw without a frozen cheap duration or draw-rate failure was
`01459238c14b`. It was not a candidate: weak play produced A/B/draw counts
1/21/8, goal-directed play produced 0/29/1, and both profiles assigned B dominance.
It entered stress only as the protocol's sole shape-clean draw diagnostic.

## Draw stress

Depth-5 evaluated all 13 exact draws over seeds 0–29. It expanded 412,498 nodes in
total, at most 68,298 for one definition, and took 19.71 seconds. Every profile was
30/30 draws ending at `PLY_LIMIT`; no exact draw was called decisive. Every case
received both `EXCESSIVE_DRAWS` and `TOO_LONG`, including `01459238c14b`.
Consequently the diagnostic-frontier set is empty.

This is useful negative evidence, not evidence that depth 5 is generally validated
on draws. The preregistered sample-size requirement keeps that claim inconclusive.

## Frozen exploratory inspection

The stress record froze 29 inspection cases: all 13 exact draws and 16 otherwise
ordinary definitions selected by the declared hash rule. There were no censored or
frontier cases to add. `D30` below means depth-5 produced 30/30 ply-limit draws;
ordinary cases were not adaptively stressed.

| Hash prefix | Inclusion | Exact result and terminal | Gate/cheap failures | Inspection note |
|---|---|---|---|---|
| `f1f5c41772c8` | exact draw | draw, `PLY_LIMIT`, PV 6 | disagreement, B dominant, excessive draws | D30; long unresolved line |
| `de4723be3acc` | exact draw | draw, `PLY_LIMIT`, PV 6 | disagreement, B dominant, excessive draws, too long | D30; long unresolved line |
| `de4a19d28f44` | exact draw | draw, `PLY_LIMIT`, PV 6 | B dominant, excessive draws, too long | D30; long unresolved line |
| `411d0e7e4c15` | exact draw | draw, `PLY_LIMIT`, PV 6 | B dominant, excessive draws, too long | D30; long unresolved line |
| `045a59213029` | hash ordinary | A win, `NO_LEGAL_ACTION`, PV 7 | B dominant, too short | cheap direction is wrong |
| `2219ef8b6ddf` | hash ordinary | A win, `GOAL`, PV 9 | disagreement, A dominant, too short | decisive, not a frontier |
| `43810bd9ce3d` | hash ordinary | B win, `GOAL`, PV 4 | B dominant | decisive, not a frontier |
| `01459238c14b` | exact draw | draw, `PLY_LIMIT`, PV 6 | B dominant | D30; sole cheap-shape-clean draw still fails strong shape |
| `4ec97b9950d7` | hash ordinary | A win, `NO_LEGAL_ACTION`, PV 5 | disagreement, A dominant, too short | decisive, not a frontier |
| `33f24b477315` | hash ordinary | B win, `GOAL`, PV 6 | B dominant, too long | decisive, not a frontier |
| `7673935e47ce` | hash ordinary | A win, `NO_LEGAL_ACTION`, PV 1 | static unreachable | rejected before cheap play |
| `a358c5faf60d` | hash ordinary | A win, `GOAL`, PV 11 | disagreement, B dominant | cheap direction is wrong |
| `d6e37b41032e` | hash ordinary | A win, `GOAL`, PV 9 | disagreement, B dominant | cheap direction is wrong |
| `2be74d556653` | hash ordinary | A win, `NO_LEGAL_ACTION`, PV 2 | static unreachable | rejected before cheap play |
| `df37969ccf6b` | exact draw | draw, `PLY_LIMIT`, PV 6 | disagreement, B dominant, too short | D30; short under medium play, long under strong play |
| `af661dcb006a` | exact draw | draw, `PLY_LIMIT`, PV 6 | B dominant, excessive draws, too short, too long | weak play draw-heavy; medium B-decisive; D30 |
| `31c43eb7a4aa` | hash ordinary | A win, `NO_LEGAL_ACTION`, PV 2 | B dominant, excessive draws, too long | cheap direction is wrong |
| `ff2849555efe` | exact draw | draw, `PLY_LIMIT`, PV 6 | disagreement, B dominant, too short | D30; short under medium play, long under strong play |
| `dc65c4b88237` | exact draw | draw, `PLY_LIMIT`, PV 6 | B dominant, excessive draws, too short, too long | weak play draw-heavy; medium B-decisive; D30 |
| `867b4eb7e2ce` | exact draw | draw, `PLY_LIMIT`, PV 6 | disagreement, B dominant, excessive draws, too short, too long | weak play draw-heavy; medium mostly B-decisive; D30 |
| `333c9f9692f3` | exact draw | draw, `PLY_LIMIT`, PV 6 | B dominant, excessive draws, too short, too long | weak play draw-heavy; medium B-decisive; D30 |
| `44f06308add3` | exact draw | draw, `PLY_LIMIT`, PV 9 | disagreement, B dominant, too short | D30; strong play reaches the longer cap every time |
| `fb211062c21b` | exact draw | draw, `PLY_LIMIT`, PV 9 | disagreement, B dominant, too short | D30; strong play reaches the longer cap every time |
| `b0ae9cc0d07e` | hash ordinary | A win, `NO_LEGAL_ACTION`, PV 4 | disagreement, B dominant, excessive draws, too short | cheap direction is wrong |
| `5957dfb73191` | hash ordinary | B win, `GOAL`, PV 5 | B dominant, too short | decisive, not a frontier |
| `ee3341aae850` | hash ordinary | A win, `NO_LEGAL_ACTION`, PV 6 | B dominant, too short | cheap direction is wrong |
| `d997153d0aec` | hash ordinary | A win, `NO_LEGAL_ACTION`, PV 0 | static no move and unreachable | rejected before cheap play |
| `ebb8065fab88` | hash ordinary | B win, `GOAL`, PV 3 | disagreement, B dominant, too short | decisive, not a frontier |
| `98c80bc41a54` | hash ordinary | B win, `GOAL`, PV 3 | disagreement, B dominant, too short | decisive, not a frontier |

The ordinary sample contained 11 A wins and five B wins, split evenly between
`GOAL` and `NO_LEGAL_ACTION` terminal reasons. Three definitions were already
static rejects. The remaining evidence exposed familiar dominance, duration, and
agent-direction failures; no additional candidate pattern appeared within the
frozen inspected set.

## Interpretation and decision

Broad, outcome-independent coverage did not reveal a sampled generator-v2
frontier. Every observed exact-draw label, its recorded principal variation, and
its strong self-play profile ended at a binding finite horizon; stronger play made
all 13 maximally draw-heavy and maximally long. This does not prove that the same
definitions resolve under a longer paired horizon, but optimizing generation for
the observed labels would reward non-resolution.

The 128 cases with `max_plies=18` are the cleanest paired substrate for the next
test: on this 3×3 one-runner, monotone-placement family, natural exhaustion occurs
before that cap. The baseline has 68 exact principal variations ending in
`NO_LEGAL_ACTION`: 40 are static-valid and 28 are static rejects, including four
initial immobility cases. Preserve DSL v1 unchanged and test exactly one versioned
counterfactual: next-player immobility produces a draw instead of an acting-player
win. The choice of the 18-ply subset is baseline-informed; within it, take all 128
cases from the outcome-free manifest without case-level outcome filtering, freeze
their treatment definitions before computing any treatment outcome, and keep
capture or other movement changes out of the same experiment.

This terminal policy is a diagnostic treatment, not an adopted game rule. A
separate preregistered result must show non-horizon exact draws with acceptable play
shape before it can justify validation or generator work.

Evidence:

- [`../corpora/landscape-v1/manifest.json`](../corpora/landscape-v1/manifest.json)
- [`../runs/20260830T200230881318Z-landscape-f407aefb/run.json`](../runs/20260830T200230881318Z-landscape-f407aefb/run.json)
- [`../runs/20260830T200513661140Z-draw-stress-1edf571b/run.json`](../runs/20260830T200513661140Z-draw-stress-1edf571b/run.json)
