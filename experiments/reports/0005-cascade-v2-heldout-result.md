> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Report 0005 — Cascade-v2 held-out result

The preregistered seed `20260901` experiment ran once from clean commit
`179fe0b3e165ac59124f2a1be8e9e2e161ea50ea`. Its attempt and completed record are
immutable under run `20260830T184008717197Z-strong-g20260901` (`run.json` SHA-256
`cdf26f22c93a95f70e413e28257a6afddfaecf21008507a6557e019f2c5357dc`). The
separate admission-blind audit ran from clean commit
`77c747d6a34196f3254c84ec2ab8412f22aa1964` as
`20260830T184737002247Z-blind-depth5-cdf26f22`.

## Predeclared outcomes

| Dimension | Observation | Outcome |
|---|---|---|
| Compute | 26/63 novel cheap-play cases admitted (41.27%); depth 5 completed 12/12; no candidate- or node-cap exhaustion | `SUPPORTED` |
| Exact completion | All 14 novel eligible 3×3 cases completed within 100,000 states | `SUPPORTED` |
| Admission draw recall | Exact results were 6 A wins, 8 B wins, and 0 draws | `INCONCLUSIVE` |
| Primary overall | One required dimension lacked two draw positives | `INCONCLUSIVE` |
| Blind depth-5 direction | 14/14 matched exact, with no deferral, but fewer than the required 15 cases completed | `INCONCLUSIVE` |
| Candidate outcome | Zero strong survivors | Allowed; not a hypothesis failure |

One of the 100 generated definitions overlapped the development corpus and was
excluded without replacement, leaving 99 novel definitions. Final primary statuses
were 36 static rejects, 37 not admitted, 1 exact reject, 12 strong rejects, 13
predeclared 5×5 board-size deferrals, and no survivor.

## Compute observation

- Cheap screening: 5.64 seconds.
- Exact solving: 14 cases, 20,158 total states, maximum 2,849 states, 1.19 seconds.
- 4×4 depth 5: 12 cases, 4,719,607 total nodes, maximum 567,420 nodes,
  402.91 seconds.
- Blind 3×3 depth 5: 14 cases, 443,877 total nodes, maximum 61,850 nodes,
  no budget deferral.

The deterministic budgets were ample for the attempted sizes. This does not
establish 5×5 feasibility because those cases were deliberately not attempted.

## False-positive analysis

The admission signal did not identify a discovery frontier.

- Every one of the 26 admissions used `WEAK_RANDOM_HIGH_DRAW`; the
  no-dominance branch added no candidate by itself.
- All 783 weak-random draws among the 63 novel cheap-play cases ended at
  `PLY_LIMIT`. Mean weak draw rate rose with board size: 19.5% on 3×3, 39.6% on
  4×4, and 58.4% on 5×5.
- All admissions used a linear ply cap (`2n` or `3n`); none used `2n²`.
- Every admitted definition already had a cheap shape failure retained by the
  finalizer: 25 had `EXCESSIVE_DRAWS`, 25 had `TOO_LONG`, and 24 had both. Thus
  none could survive regardless of later search.
- The sole admitted 3×3 case had exactly 50% weak draws and avoided the excessive-
  draw code, but exact solving proved an A win after 1,757 states.

The 12 attempted 4×4 searches therefore had diagnostic rather than discovery
value. Weak random play drew 278/360 games, while depth 5 drew only 63/360. Depth 5
classified six cases toward A, four toward B, and two as all draws; all still
failed because cheap shape evidence remained. At least one cheap profile disagreed
with the strong direction in 7/12 cases, and both cheap profiles disagreed in 5/12.
This pattern is consistent with weak high-draw behavior being largely agent and
horizon sensitivity; the observed draws are not credible fairness evidence.

All 13 deferred 5×5 cases already had both `EXCESSIVE_DRAWS` and `TOO_LONG`.
Running depth 5 on them cannot produce a survivor under the frozen final gate, so
increasing their compute budget would have no candidate-discovery information.

## Exact and blind evidence

The held-out exact set contained 6 forced A wins and 8 forced B wins. Only one case
was admitted, so the rule filtered 13/14 forced results, but zero exact draws means
false-negative recall was not tested. Blind depth 5 matched all 14 forced directions
and used only 443,877 nodes, but the preregistered minimum was 15. This is promising
observational evidence, not confirmatory support.

The two development exact draws were also inspected. Both principal variations end
at the six-ply cap. They are horizon draws rather than evidence that the game
resolves fairly, so enriching future generation for `DRAW` alone risks optimizing
non-resolution.

## Frozen exploratory inspection

The preregistered hash rule selected ten of 60 novel cases that entered no exact,
depth-5, or deferral lane. Their hash prefixes were:

`32914a4b855a`, `77e16c790af7`, `0da413d51104`, `b65037fa4a1e`,
`eb32b5e6000f`, `6d372ad06fe5`, `850d65cbd2ed`, `ab3e188d0adf`,
`777c68be6c63`, and `f8e08ed6c3b3`.

The sample contained three unreachable definitions, one complexity reject, four
same-direction cheap dominance classifications, and two agent-sensitive cases; its
recorded static and cheap evidence contained no obvious missed frontier. Across all
99 novel definitions, 27 were unreachable, 9 exceeded the complexity gate (all
used eight movement vectors), and every one of 63 cheap-play cases had at least one
failure. Medium goal-directed play produced 539 A wins, 1,344 B wins, and 7 draws,
showing a strong B-role bias under that policy even after stratifying by first
player.

A post-run D4 symmetry census found that the predeclared exact-hash overlap rule
was narrower than mechanical novelty: the development and held-out runs shared four
spatial-isomorphism classes rather than one exact definition hash, and the held-out
run contained one additional internal mirror pair. One newly recognized overlap had
entered the exact and blind lanes. This does not change the sealed primary or blind
outcomes, but future spatial-generator protocols will exclude known D4 orbits before
selection.

## Interpretation and decision

The compute cascade worked as bounded software, but its high-draw admission rule
confounded short ply-cap censoring with fairness and sent compute to candidates
that the final gate could never accept. Cascade-v2 remains preserved evidence and
must not be retuned on this run.

Do not spend depth-5 compute on the deferred 5×5 cases, do not optimize a generator
for exact draws, and keep seed `20260902` untouched. The next experiment will map an
outcome-independent, symmetry-deduplicated, structurally stratified 3×3 sample from
the existing v2 vocabulary. Exact results will guide whether to validate a sampled
structure, change generator weights, or test a minimal mechanic expansion; the
finite sample cannot prove the unsampled vocabulary empty.
