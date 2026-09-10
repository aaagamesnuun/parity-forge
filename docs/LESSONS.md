> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Lessons

Append only after implementation or experiment evidence exists. Each entry records
an observation, failed assumption, evidence, and resulting change.

## L-001 — The minimal DSL is enough for an end-to-end engine contract

- **Observation:** Four primitives exercised strict parsing, canonical hashing,
  placement, movement, both goals, no-action loss, ply-limit draw, and replay.
- **Failed assumption:** Configurable terminal callbacks or a generic rule AST might
  be needed to make the first architecture slice complete.
- **Evidence:** Seventeen tests pass; frozen static run
  `20260830T153256441950Z-static-4ad81a40` matched all seven expected cases.
- **Change:** Keep DSL v1 narrow and direct the next experiment toward agent-strength
  sensitivity rather than adding mechanics.

## L-002 — Nominally stronger same-family self-play can reverse the truth

- **Observation:** Random self-play favored A 76%, while goal-directed self-play
  favored B 83.5%; exact minimax proved A can force a win.
- **Failed assumption:** A one-ply goal-directed policy would be a uniformly more
  trustworthy fairness signal than random play for both asymmetric goals.
- **Evidence:** Runs `20260830T153616787888Z-play-1c478ea4` and
  `20260830T153746479973Z-solve-1c478ea4` on the identical definition hash.
- **Change:** Treat policy differences as distinct evaluator families, flag their
  disagreement, and exact-solve tractable finalists instead of averaging profiles.

## L-003 — Opposite-edge starts trade triviality for reachability and duration

- **Observation:** Conditioning B's start opposite its target removed all 25
  trivial-start failures and increased play-evaluated cases from 47 to 57, but
  increased unreachable goals from 19 to 29, excessive draws from 15 to 26, and
  long games from 8 to 28; neither 100-case batch had a survivor.
- **Failed assumption:** Increasing B's travel distance might be sufficient to
  produce a provisional fairness frontier.
- **Evidence:** Generator-v1 run `20260830T154155824053Z-batch-g20260831` versus
  generator-v2 run `20260830T154309225370Z-batch-g20260831` under frozen evaluators.
- **Change:** Stop generator tuning and resolve evaluator reliability first.

## L-004 — Search depth corrected the frozen direction errors

- **Observation:** Direction accuracy rose from goal-directed 12/20 to minimax
  depth-3 16/20 and depth-5 20/20 on the same exact corpus.
- **Failed assumption:** The remaining depth-3 B bias necessarily required a new
  heuristic; additional lookahead alone corrected it on this corpus.
- **Evidence:** Runs `20260830T154624122230Z-calibrate-f27833e8` and
  `20260830T154733530838Z-calibrate-f27833e8` against the unchanged exact audit.
- **Change:** Promote depth 5 to a late strong profile, retain exact audits, and
  measure cost before applying it to larger boards.

## L-005 — Ply-limit draws did not identify a cascade-v2 discovery frontier

- **Observation:** All 26 held-out admissions came from weak-random high draws, all
  783 weak-random draws ended at the ply limit, and every admitted definition
  already had a cheap shape failure that the finalizer could not remove.
- **Failed assumption:** In cascade-v2, high cheap-policy draw rates would
  concentrate strong evaluation on a plausible fairness frontier.
- **Evidence:** Run `20260830T184008717197Z-strong-g20260901`; admitted cases were
  1/14 of play-evaluated 3×3, 12/28 of 4×4, and 13/21 of 5×5, with zero admissions
  among the 20 cases using the quadratic `2n²` ply cap.
- **Change:** Separate discovery eligibility from evaluator diagnostics, treat
  ply-limit draws as censoring, and never spend strong-search compute on candidates
  that are already ineligible under an immutable final gate.

## L-006 — Perfect held-out forced-direction matches can remain incomplete evidence

- **Observation:** Admission-blind depth 5 matched all 14 held-out exact forced
  directions without budget exhaustion, but the exact set had no draws and the
  preregistered audit required at least 15 completed cases.
- **Failed assumption:** A fresh 100-definition generator batch would likely provide
  enough exact cases and draw positives to assess both direction accuracy and draw
  handling.
- **Evidence:** Blind run `20260830T184737002247Z-blind-depth5-cdf26f22` was 14/14;
  the primary exact lane was 6 A wins, 8 B wins, and 0 draws. The two development
  exact draws both terminated at a six-ply cap.
- **Change:** Preserve the result as promising observational evidence, keep seed
  `20260902` untouched, and map exact outcomes with an outcome-independent
  structural sample before choosing a new generator or solver test.

## L-007 — Broad exact coverage found only horizon draws

- **Observation:** Exact solving completed all 384 outcome-independent landscape
  cases and found 13 draws, but every draw ended at a six- or nine-ply cap. Depth 5
  completed all 13 without decisive error, yet every profile was 30/30 ply-limit
  draws and failed both excessive-draw and long-game gates. Frontier coverage was
  complete and the diagnostic-frontier count was zero.
- **Failed assumption:** Broad structural coverage might reveal at least one sampled
  exact draw whose acceptable duration and draw shape survived stronger play.
- **Evidence:** Raw run `20260830T200230881318Z-landscape-f407aefb`, stress run
  `20260830T200513661140Z-draw-stress-1edf571b`, and report 0006. Independent replay
  reproduced the manifest, exact solutions, principal variations, cheap games, and
  aggregates without mismatch.
- **Change:** Do not reweight generator v2 or optimize exact draw labels. Preserve
  schema v1 and test one non-horizon terminal policy on a fixed paired corpus before
  considering a new interaction primitive.

## L-008 — Relabeling containment as a draw does not create counterplay

- **Observation:** Stalemate-as-draw changed 20 of 128 exact A wins into natural
  draws, but 18 definitions were static rejects. The two valid cases both became
  30/30 depth-5 stalemates and retained excessive-draw failures; one was also a
  two-ply block.
- **Failed assumption:** A natural draw terminal might turn enough A containment
  wins into strategically usable balance without changing either role's actions.
- **Evidence:** Runs `20260830T214033891685Z-stalemate-ed9a9b93` and
  `20260830T214159802995Z-stalemate-stress-239ad79d`; frozen inspection of 16
  changed and 16 unchanged pairs; report 0007.
- **Change:** Preserve the terminal-policy result but do not adopt it. Test one
  direct B counterplay primitive that contests A seeds, with the old terminal
  semantics restored and no simultaneous generator or evaluator change.

## L-009 — A replay gate also needs a sealed replay attestation

- **Observation:** The paired runner correctly blocked treatment until a fresh
  128-case v1 replay matched the frozen source, but the raw result stored only
  replay timing and a derived match count. Its candidate evidence or digest cannot
  be reconstructed from the raw artifact alone.
- **Failed assumption:** Frozen control flow plus source-code and Git attestations
  were sufficient artifact-level evidence of a completed replay boundary.
- **Evidence:** Independent closeout validation accepted every raw and stress value
  but identified the missing replay column as an evidence-completeness limitation.
  A separate pre-outcome replay had matched all 128 cases.
- **Change:** Future paired protocols must seal timing-free candidate-level replay
  evidence or an ordered digest derived from it, and validators must recompute that
  attestation from the pinned baseline rather than infer a match from treatment
  denominator size.

## L-010 — Capture creates counterplay, but mobility controls which role dominates

- **Observation:** B capture-on-entry changed 61/128 exact values from A wins to B
  wins with no horizon result. Treatment outcomes were A/B = 24/8 in the one-to-
  three-vector band, 4/28 at four vectors, 4/28 at five, and 0/32 at six or seven.
  Every one of the 32 depth-5 profiles was 30–0 in its exact direction.
- **Failed assumption:** A single local capture permission might open a broadly
  useful counterplay frontier without simply moving the existing role imbalance.
- **Evidence:** Raw run `20260830T225920216640Z-capture-6bc46645`, stress run
  `20260830T230308952280Z-capture-stress-e4fc6e97`, and the frozen 58-case
  inspection in report 0008.
- **Change:** Do not adopt capture or combine another exception with it. Test the
  fresh three-versus-four-vector boundary before considering a capture-aware
  generator, and require strong within-definition balance rather than treating
  role diversity across definitions as candidate fairness.

## L-011 — An adaptive cap can censor an unexpectedly broad response

- **Observation:** Plan 0008 expected at most 32 useful stress cases, but 88 were
  eligible. All selected 32 completed cleanly and showed interaction, yet 56
  unselected cases forced the general, frontier, and overall labels to remain
  `INCONCLUSIVE`.
- **Failed assumption:** A 32-case adaptive diagnostic lane would be large enough
  to classify the complete interaction frontier after exact response filtering.
- **Evidence:** The frozen stress selection records 50 clean and 38 other eligible
  cases, 32 selected clean cases, and a 56-case candidate-cap shortfall.
- **Change:** Do not extend a cap after seeing outcomes. For the next bounded
  replication, freeze a smaller outcome-blind membership and run every selected
  case through exact and depth-5 evaluation without adaptive eligibility sampling.

## L-012 — A prior-informed mobility separator did not replicate

- **Observation:** On a fresh, disjoint, equal-stratum sample, capture treatment
  produced A/B = 3/29 at both three and four vectors. `B4 - B3` was zero, only one
  of eight cells increased, the interaction frontier was A/B = 6/46, and all 64
  treatment profiles were 30–0 role-dominant.
- **Failed assumption:** Plan 0008's one-to-three versus four-vector contrast might
  identify a reproducible capture-strength boundary with a usable A side.
- **Evidence:** Exact run `20260831T012026857459Z-capture-boundary-exact-e1b0f6a7`,
  depth run `20260831T012251133134Z-capture-boundary-depth5-cbf2ccc3`, frozen
  44-case inspection, and report 0009. All public reconstructions and an
  independent post-outcome audit passed.
- **Change:** Reject vector-count tuning and unrestricted capture as discovery
  directions. Before adding another action concept, test whether the existing DSL
  can relieve the one-runner bottleneck through one simple setup change.

## L-013 — Mechanical engagement can coexist with universal role dominance

- **Observation:** The second B runner was used in many retained traces: 31 exact
  PVs met the strict engagement definition, 54 treatment profiles contained a
  same-game engagement witness, and 46 cases entered the complete strong frontier
  across every stratum and structural cell. Nevertheless, every frontier profile
  was 30–0 in its exact direction, split into 24 A-dominant and 22 B-dominant
  cases, and candidate shape was empty.
- **Failed assumption:** Alternate routes, simultaneous legal choices between two
  movers, and a broad across-definition A/B frontier might be sufficient for at
  least a small non-dominant setup frontier without changing actions or terminals.
- **Evidence:** Exact run
  `20260831T042721207815Z-two-runner-exact-3b7757ad`, depth run
  `20260831T043600138223Z-two-runner-depth5-2353bfb8`, the frozen 56-case
  inspection, report 0010, and independent raw-evidence reconstruction.
- **Change:** Keep mechanical engagement as a prerequisite rather than a fairness
  proxy. Reject the two-runner setup as a discovery substrate, and evaluate any
  4×4 continuation first as an evaluator-calibration problem because exact 3×3
  ground truth no longer transfers automatically.

## L-014 — Branching and contact are not single measures of agency

- **Observation:** Synthetic schema-v4 traces contain distinct false positives:
  two legal CONVERT actions can reach the same immediate position, equal
  next-action counts can conceal different exact legal sets, a HOP can depend on
  an opponent without changing it, and both roles can realize opponent effects
  without proving a reciprocal causal exchange.
- **Failed assumption:** Legal-action count or a generic contact flag could serve
  as a faithful cross-family proxy for consequential choice and interaction.
- **Evidence:** Replay-telemetry-v1's seven frozen calculation fixtures, all D4
  metric projections, role-swap oracle, and ordered benchmark root
  `6789f97e7f0948df9fa66f75933c061a08e029ce49e9d9da33ae57a7b4a59a33`.
- **Change:** Keep branching, successor positions, state effects, immediate
  outcomes, exact next-player legal sets, dependency, and realized effects as
  separate descriptive evidence. Use `BOTH_ROLES` as a neutral observation, not
  a reciprocity claim, and calibrate no universal agency or fun threshold from
  hand-authored traces.

## L-015 — Broad mechanical support exists, but common setup support must be explicit

- **Observation:** All six provisional non-`PLACE`/`MOVE` family cells have
  nonempty outcome-free 3×3 support, totaling 24,208 eligible D4 orbits. Yet 32
  of 176 strata are structurally impossible: every 2+2 fixed-count connection
  setup in swap-versus-hop and push-versus-swap. The remaining common 3+3 core
  spans all families, goal frames, vector pairs, and first players; its smallest
  stratum still contains 12 eligible D4 orbits.
- **Failed assumption:** A balanced piece count and equal raw parameter grid are
  enough to make heterogeneous action/goal families comparably feasible.
- **Evidence:** Plan 0012's complete 214,368-input census, 102,336 raw D4 orbits,
  exact rejection-reason combinations, 144 supported strata, evidence digest
  `ade64ebaaf9892848e03c2312786a6ef3825f3c82f4311e16a9c810711d035d2`,
  and independent implementation/output reviews.
- **Change:** Freeze later cross-family pilots only over explicitly shared
  structural support. Preserve unsupported cells as named exclusions, equalize
  nominal family exposure rather than raw domain volume, keep a disjoint unused
  orbit reserve, and continue reporting state/work/branching differences because
  equal quotas do not imply equal difficulty.

## L-016 — Paired selection needs explicit correspondence and explicit deferral

- **Observation:** First-player toggling produced equal aggregate counts and D4
  multiplicities, but those summaries alone did not prove which exact A-first
  setup corresponded to which exact B-first setup. Likewise, selecting only the
  common 3+3 band could have made 7,740 eligible 2+2 exact setup pairs disappear
  behind a prose statement. Historical exact collision also required all eight
  representative orientation hashes, including duplicates and orientations
  outside the goal-frame quotient, rather than only the canonical member hash.
- **Failed assumption:** Equal member populations, matching neutral descriptors,
  and one representative D4 identity were sufficient evidence for a matched
  experimental unit and for a complete account of the parent search space.
- **Evidence:** Adversarial review could permute B-first exact witnesses while
  preserving member sets and could inject an exact collision through an R90
  representative outside the domain's canonical goal-frame orientations. The
  repaired universe binds a first-player-free setup identity to ordered A/B case
  and definition hashes, retains all eight exact orientation slots, and rejects
  a re-signed permutation. The envelope independently reconstructs 33,264 raw,
  7,740 eligible exact, and 3,250 eligible paired-D4 2+2 setup pairs plus the 16
  unsupported paired strata, then reconciles them with the active 3+3 band and
  the full Plan-0012 census.
- **Change:** Treat paired exact correspondence, complete symmetry collision
  carriers, and excluded/deferred domain density as first-class rooted evidence.
  Every future paired selector must report both pair and member-definition counts
  and must reconstruct valid deferred regions instead of letting a chosen common
  support envelope erase them.

## L-017 — A common agent contract includes lifecycle and hostile boundaries

- **Observation:** A mathematically simple terminal-only minimax was not fully
  specified by “terminal utility plus zero cutoff.” Its observable result also
  depended on A=max/B=min at both recursive and root nodes, canonical tie order,
  unique-best RNG nonuse, cache-key and cache-lifetime rules, root charging,
  cumulative role-slot budgets, agent reuse across seeds, reset timing, and exact
  state/action/identity validation. A benchmark that created a fresh agent for
  every game did not test the lifecycle promised for production.
- **Failed assumption:** Correct values on a few A-first roots were enough to
  validate a family-neutral search and authorize it for a heterogeneous atlas.
- **Evidence:** Independent mutation review showed that the initial fixtures did
  not distinguish B minimization, Python bool equality could bypass dataclass
  identity/action comparisons, unbounded depth could reach interpreter recursion,
  state-piece membership could reject valid PLACE-created pieces, and untrusted
  validation paths could amplify memory. The repaired SWAP/CONNECT fixture
  distinguishes root and recursive B minimization; slot replays exercise the
  exact production lifecycle; exact-type, depth-64, JSON resource, and
  separation-first probes fail closed. The final benchmark root is
  `340e928d…15da0`, with 635/635 tests and no remaining P0–P2 finding.
- **Change:** Freeze evaluator algorithm, work unit, cache, RNG, lifecycle,
  strict-input, and resource semantics together. Synthetic benchmarks validate
  calculations and protocol conformance only; keep them structurally disjoint
  from selected games and prove that separation before any outcome-producing
  call. Do not confuse D4-covariant action values with D4-equivariant seeded tie
  selection; retain the complete orientation schedule unless the latter is
  separately proved.

## L-018 — Regular-file validation must make the open itself nonblocking

- **Observation:** The first complete Plan-0014 implementation validated file
  type, link count, mode, size, and same-descriptor metadata after opening each
  expected artifact. An attacker could nevertheless replace an allowed path
  with a FIFO: `O_RDONLY` could then wait forever before `fstat` reached the
  otherwise correct regular-file check. The same class existed in the shared
  old-store reader, the new attestation inventory reader, the new evidence
  store, its lock and linked-publication paths, and current-source resealing.
- **Failed assumption:** `O_NOFOLLOW` followed by immediate `fstat` was enough to
  make a fixed-path reader fail closed for every non-regular filesystem object.
- **Evidence:** Three independent pre-run audits rejected implementation
  checkpoint `37d95eb…d58ee` with the same P2 liveness defect before any
  Plan-0014 production evidence existed. Isolated two-second subprocess probes
  reproduced FIFO blocking at the old and new reader boundaries. Checkpoint
  `bcec701…ed057` adds `O_NONBLOCK`, bounded exact-size reads, descriptor-walked
  current-source paths, a lock-acquired guard, and FIFO/socket/device/size/race
  regressions. Its focused boundary was 80/80 and its full dependency-free
  suite passed 873 tests in 1,102.015 seconds with the two intended real-data
  tests skipped.
- **Change:** Any authenticated local reader must arrange for `open` itself to
  return on special files before it relies on post-open type validation. Use
  `O_NONBLOCK|O_NOFOLLOW`, descriptor-relative ancestor traversal, bounded
  reads tied to authenticated sizes, same-descriptor before/after metadata,
  and cleanup state that never masks the original integrity failure. Treat
  this as operational/type hardening, not as a scientific-rule repair.

## L-019 — A pure module is not capability-minimal if importing its package is not pure

- **Observation:** The first Plan-0015 placement put an outcome-free grammar
  module beneath `parity_forge`, but ordinary Python import necessarily executed
  that package's frozen initializer and eagerly loaded the engine. The module's
  own import list was pure while its real import path was not.
- **Failed assumption:** Reviewing only a leaf module's source imports was enough
  to prove that consumers could load it without transition or gameplay
  capability.
- **Evidence:** The legacy initializer is a frozen historical checkpoint and
  cannot be changed without invalidating prior byte identities. Moving the same
  grammar boundary into docstring-only sibling package `parity_forge_universe`
  preserved that blob exactly and made a clean-process forbidden-capability test
  meaningful.
- **Change:** Capability audits must cover the complete executable import path,
  including package initializers and registration side effects. When a frozen
  eager package conflicts with a new pure boundary, prefer a narrow sibling
  package over modifying history or using an import bypass.

## L-020 — A finite-universe seal must anchor meaning, not self-consistent carriers

- **Observation:** Counts, roots, Enum maps, and semantic lookup tables could all
  remain mutually consistent after coordinated mutation. Exact-type Enum members
  with the same string payload could also replace original singletons unless the
  original identities themselves were retained independently.
- **Failed assumption:** Recomputing a descriptor from the currently visible
  registries and comparing internally consistent names and values was sufficient
  to prove that the original finite vocabulary was unchanged.
- **Evidence:** Adversarial tests successively exposed mutable expected tables,
  registry aliases, non-Enum members, coherent member permutations, and
  same-payload exact-type singleton replacements. The final boundary retains
  original singleton tuples at definition time and independently checks class
  bindings, intrinsic payloads, every Enum registry, code-literal semantics,
  ordered endpoints, domain hashes, arithmetic, and the descriptor root.
- **Change:** For small closed languages, keep authorities one-way and immutable:
  anchor original identities, derive semantics from code, and compare redundant
  independent invariants. Do not let expected values and observed values share
  the same mutable carrier, even when a final cryptographic digest is present.

## L-021 — Validation must not dispatch through the object being validated

- **Observation:** The first slice-2 compiler passed all 33 exhaustive and
  boundary tests, yet an exact dataclass instance could acquire an
  `_assert_unchanged` attribute through `object.__setattr__`. Normalization then
  invoked that instance attribute and skipped the expected-field, snapshot, and
  nested-source checks. The same bypass reproduced at member, carrier, setup,
  and skeleton layers.
- **Failed assumption:** A frozen dataclass and an exact outer type check were
  sufficient before calling `value._assert_unchanged()` dynamically.
- **Evidence:** Independent review reproduced four accepting paths on compiler
  blob `d91340f0…89b9`; one could emit wire outside the authoritative parser and
  inverse image. Compiler blob `95bb7581…251a` instead preflights exact fields at
  every nested skeleton node, invokes definition-time anchored validation
  methods, and rejects class/method/payload rebinding. The added regressions and
  358-path independent check pass, and two final reviews report no P0-P3 issue.
- **Change:** At strict trust boundaries, validate object shape before any
  overridable instance lookup and invoke a retained class/function authority.
  Apply this rule recursively to nested typed values; a frozen dataclass is a
  mutation deterrent, not by itself a validation dispatch boundary.

## L-022 — Opponent actions belong in a schema-v4 impossibility proof

- **Observation:** A role-local vector closure can say that a diagonal-moving
  role cannot form an orthogonal connection, while an opponent PUSH or SWAP can
  relocate one of its pieces across the parity boundary. Schema v4 then checks
  that opponent goal after the action. Initial ELIMINATE targets can likewise
  move under any opponent movement action before a later capture or conversion.
- **Failed assumption:** A goal role's own action profile was the only spatial
  mechanism relevant to an optimistic necessary-condition test.
- **Evidence:** Independent transition analysis produced both an
  opponent-assisted CONNECT counterexample to the weak closure and a moving-
  target ELIMINATE counterexample to testing only initial target positions. The
  corrected induction contains every actual owned-piece position in a support
  closed under own motion plus opponent PUSH/SWAP displacement, and contains
  every surviving initial target in its own opponent-action lineage support.
- **Change:** Static impossibility gates must model every primitive that can
  change the tested predicate's inputs, including effects caused by the other
  role. Keep this as a monotone over-approximation and prove containment per
  transition; never promote a successful relaxation to dynamic reachability.

## L-023 — A streaming bridge must detach inputs without becoming an authority

- **Observation:** Repeated census derivation needs a fast path, but a caller can
  mutate even frozen dataclass fields through low-level assignment while nested
  validation or serialization is in progress. Returning a trusted result object
  through the full public parser on every row would instead repeat complete
  rederivation and make a multi-million-carrier stream impractical.
- **Failed assumption:** Validating a caller-owned carrier and prepared token
  once, then continuing to read those same objects, was enough to define one
  coherent row snapshot; alternatively, a faster serializer could safely double
  as a public validation boundary.
- **Evidence:** The final `initial_structure` boundary first converts each strict
  carrier to canonical JSON and a detached exact payload, copies every prepared
  field into a new exact token, and validates that copy before deriving. Race
  regressions that replace a carrier setup, a prepared bundle, or a compiler
  canonicalizer can therefore produce only a self-consistent pre-mutation
  snapshot or a closed failure. The output-only snapshot bridge matches the
  ordinary result bytes and hash, while the public parser, serializer, hash, and
  validator still perform full rederivation. Source/test blobs
  `c7d806aa…38c1` / `18ff5274…7b`, the focused 30-test run, the 33-test file
  inside the 989-test full suite, and two independent final audits close the
  boundary at P0=P1=P2=P3=0.
- **Change:** For a high-volume pure calculation, canonicalize and detach every
  caller-owned input before consuming it, and make the fast return explicitly
  output-only. Keep all public parse and trust boundaries fully rederivable;
  never let a digest, cached token, or streaming shortcut become accepted
  authority merely because it is faster.

## L-024 — Exact hashes do not replace exact nested types

- **Observation:** The first complete static-census implementation could retain
  the expected digest while accepting semantically different Python carriers.
  Private helper rebinding could hide a changed table, an embedded descriptor
  root was compared without rebuilding its body, standalone shard validation
  trusted derived skeleton fields, and Python's `False == 0` / `True == 1`
  equality plus tuple subclasses crossed nested setup, weight, snapshot, shard,
  and report boundaries.
- **Failed assumption:** Recomputing a final hash and checking an exact outer
  dataclass or tuple was sufficient when inner records compared equal and all
  honest outputs were canonical.
- **Evidence:** Targeted adversarial probes altered nested `(ordinal, weight)`
  and count records, numeric zero/version fields, stabilizer tuples, and report
  bodies while retaining old digests. Each attack was first reproduced, then
  fixed with a regression. The final source/test blobs
  `fd5fb486…1058` / `93aa6d42…5bae` pass 36 dedicated tests, the 1,025-test
  complete suite, and two independent P0-P3-free reviews.
- **Change:** At every accepted proof boundary, anchor helpers at definition
  time, strictly parse and rederive embedded identities, require `type(x) is
  int` where booleans are invalid, require exact tuples and exact element types
  recursively, and compare canonical bytes of the actual body with the
  independently reconstructed expected body. A digest authenticates bytes; it
  does not decide which runtime values are allowed to denote those bytes.

## L-025 — Complete role exchange includes global piece-label correspondence

- **Observation:** An initial history adapter transformed owner, role program,
  and first player, but distinguished a compiler role-exchange image when the
  compiler also exchanged its `a`/`b` piece labels.
- **Failed assumption:** Exchanging role ownership alone fully specified the
  role-neutral identity, or labels could be normalized independently per owner.
  Labels can be shared across owners and referenced by elimination goals.
- **Evidence:** The independent counterexample becomes identical after global
  first-occurrence alpha normalization in each D4/role image. All 1,179 frozen
  definitions then agree with the independent neutral-identity oracle, while
  exact and historical D4 hashes remain unchanged.
- **Change:** Preserve the equality relationship of piece kinds globally, not
  just the owner's local label. Keep the new neutral identity separate from
  frozen DSL/D4 identity, and test actual compiler exchange images as well as
  hand-written owner swaps.

## L-026 — Check a monotone breadth obstruction before building a selector

- **Observation:** Plan 0015's complete saved census contains nine semantic
  classes with no eligible setup. A small read-only grouping of 1,518 shard
  summaries proves that the all-109 support requirement cannot be met.
- **Failed assumption:** Completing history exclusion and ranking was the next
  necessary step before learning whether the breadth floor was feasible.
- **Evidence:** The public reconstructor and independent role-program grouping
  agree on nine empty classes, 51 empty skeletons, and the complete 3,036-stratum
  supply distribution. For each stratum, fresh supply is at most eligible
  supply, making the negative conclusion independent of ranking.
- **Change:** Apply registered monotone necessary conditions before expensive
  selection work. Record an unregistered early-stop execution decision openly;
  do not claim skipped work completed or silently relax the original criterion.
  Distinguish failure of a universal breadth requirement from failure of every
  game in the language.
