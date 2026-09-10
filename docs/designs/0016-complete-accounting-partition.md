> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Proposed Plan 0016 — Complete accounting and prospective blind partition

## Status and exposure disclosure

Deferred design option. Plan 0015 is closed; the actual Plan 0016 is the smaller
integrated exploratory pilot. This document
authorizes no implementation, member
selection, production run, transition, solver, or game-quality claim.

Plan 0015's scientific result remains `BREADTH_FLOOR_NOT_MET`, its production
census remains `COMPLETED`, and its partition remains `NOT_STARTED`. This
proposal does not revise that criterion or complete its skipped partition.

This methodological choice is informed by the already observed static result:
109 classes, 9 empty classes, 100 nonempty classes, 1,518 skeletons, and 3,036
strata. It is not a blind test of whether all classes are supported, and it must
not be called a new census, an independent replication, or confirmation.
Prospective blindness applies to member choice and later gameplay, not to the
static aggregates already known.

The [strategic review](../reviews/2026-09-05-astra-strategic-review.md) adds an
important activation constraint: complete accounting does not justify evaluating
every allocated carrier. The proposed two-per-supported-stratum rule permits up
to 4,502 development carriers / 9,004 separate first-player games before history
exclusion. It remains a reviewed allocation option, not a required next run.
First define the [single-game diagnostic question](single-game-diagnostic-contract.md)
and its synthetic conformance checks, then justify and freeze an actual small
evaluation budget and its general
sampling rule. Do not silently substitute an arbitrary 24-member cap or promote
this allocation option to an active plan while that purpose is unresolved.

## Question and minimal change

Can the complete declared grammar be accounted for using general exclusion
rules, and can every supported stratum receive the same deterministic blind
development/reserve allocation without selecting a preferred family subset?

The primary change is the coverage contract: **complete accounting** replaces
the previous research question of **universal support**. This is a new question,
not evidence that the old question had a positive answer. Keep the DSL, board,
18-ply envelope, roles, setup domain, static gates, seven actions, three goals,
profiles, old-six exclusion, and first-player semantics unchanged. Do not add
`REMOVE_ADJACENT`, `SURROUND`, or the proposed 48-spec removal audit.

The input is the whole grammar derived by its frozen general rules, never a
hand-written allow-list of the known 100 nonempty classes. Every derived class,
skeleton, stratum, and rejected member remains in the accounting denominator.

## Required inputs and history boundary

- Authenticate and publicly reconstruct the existing Plan-0015 compact report
  at SHA-256 `fa7daf48992f2b186fd980d42f670beda651b1adc7fe4c1fb62b67d1fdc05f97`.
  Do not rerun its production builder or replace its terminal seal.
- Reuse the frozen grammar/compiler/initial-structure authorities without source
  modification. Any read-only member adjudication for selection must be
  declared as a new selection calculation, not a second census attempt.
- Consume only the detached fixed history projection, never raw historical
  artifacts or access to the Plan-0013 candidate-bearing tree. Preserve the
  old-six semantic exclusion across all frames, profiles, setups, and role
  exchanges, not just previously selected members.
- The existing projection authenticates its named Plan-0015 cutoff. It does
  **not** silently become a complete later cutoff. Before activation, account
  for intervening exposure using content-free inventory and source-only
  classification. Distinguish static/calibration exposure from gameplay-bearing
  exposure. Unresolved additions stop the process; do not assume zero.
- The [static-exposure addendum](0016-static-exposure-addendum.md) classifies the
  six added experiment JSON paths through commit `9fdbdd1f9` and separately
  reviews the new static/calibration source. It is a source-and-Git audit, not a
  runtime exposure ledger or later-cutoff attestation. No later member may be
  called wholly unexposed merely because it is outside the gameplay projection.
- A proof of zero historical intersection may avoid exhaustive member/hash
  comparison only if its domain separation and every source identity are
  independently authenticated. The old schema labels alone are not a substitute
  for checking the projection's actual semantics. This proof is not yet made.

## Complete accounting, not universal support

Enumerate all 1,518 canonical profiled skeletons and both `CONTACT` and
`SEPARATED`, including empty strata. The contact definition is unchanged and is
not a quality score.

For each stratum let T be its master representative count, E its static-eligible
count, H the number of eligible carriers excluded by historical collision, and
F = E − H its remaining supply. Count each carrier once even if several of its
identities or both first-player members collide.

| Classification | Exact condition | Allocation |
| --- | --- | --- |
| `STATIC_ZERO` | E = 0 | None |
| `HISTORY_EXCLUDED` | E > 0 and F = 0 | None |
| `SUPPLY_SHORTFALL` | 1 ≤ F ≤ 4 | All fresh members untouched |
| `SUPPORTED` | F ≥ 5 | Development 2, reserve 2, remaining untouched |

Require `0 <= F <= E <= T` and, separately for representative and weighted
mass, `T = static_rejected + history_excluded + development + reserve + untouched`.
Retain the original overlapping static reasons, historical counts, and all
resource-count-pair/contact breakdowns. Unknown, missing, unauthenticated, or
unfinished work is an integrity failure, never one of these four categories.

At skeleton and semantic-class level, report the full distribution of descendant
strata. A summary may say `HAS_SUPPORTED_STRATUM`, `ALL_STATIC_ZERO`, or
`NO_SUPPORTED_STRATUM_WITH_NONZERO_STATIC_SUPPLY`; it may not hide a short or
historically excluded descendant. No minimum number of successful classes is
inferred from the known count of 100.

## Prospective rank and identity separation

Fix the rank domain before computing any selected membership:

```text
parity-forge:all-supported-strata-partition:rank:v1\0
```

The displayed `\0` denotes one trailing NUL byte, not backslash plus zero.
Rank is the lowercase hex digest of
`SHA-256(domain_bytes || canonical_JSON_UTF8)`. The JSON object has exactly
`skeleton_identity`, `contact_class`, and `setup_identity`. Serialize with
`sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False`,
then UTF-8 without BOM or trailing newline. Identity fields are lowercase
SHA-256 strings; contact is exactly `CONTACT` or `SEPARATED`.

- `skeleton_identity` is
  `typed_occupancy.role_neutral_profiled_skeleton_hash`, domain
  `parity-forge:typed-occupancy:role-neutral-skeleton:v1\0`.
- `setup_identity` is `schema_v4_compiler.typed_setup_hash_v1` of the exact
  stabilizer-canonical setup in that canonical skeleton's role/frame order,
  domain `parity-forge:plan0015:typed-setup:v1\0`.
- `canonical_setup_bytes` is the UTF-8 result of
  `schema_v4_compiler.canonical_typed_setup_json_v1` for that same setup.

These are the unchanged frozen APIs, not a new anonymous tuple hash. Define the
total order as `(rank_hash, canonical_setup_bytes)`; raw canonical bytes break
a hash tie. Duplicate canonical setup bytes in a stratum are an integrity error.

Names, first player, history root, resource counts, complexity, branching,
contact magnitude, and outcomes are not rank inputs. Define the rank on all
static-eligible carriers first; historical exclusion then takes a subsequence of
that fixed order. It cannot reseed, rerank, or backfill another stratum.

If either first-player member collides with historical exact, D4, or complete
role-neutral identity, exclude the whole carrier. Partition identity must also
be disjoint under all three relations; carrier labels or unequal names are not
evidence of novelty.

## Joint resource diversity and deterministic choice

Resource type is the ordered `(A_count, B_count)` in the canonical skeleton's
role order. It is invariant under first-player toggle and is not a score.

For F = n >= 5, let m be the largest resource-type frequency. Fix the target
pair `(development_is_diverse, reserve_is_diverse)` as:

```text
n - m >= 2  => (1, 1)
n - m == 1  => (1, 0)
n - m == 0  => (0, 0)
```

Among all disjoint two-development/two-reserve allocations attaining that target,
sort the members inside each pair by their total rank, then choose the smallest
lexicographic tuple `(D_low, D_high, R_low, R_high)`. This gives development
priority without destroying achievable reserve diversity.

For resource supply `(3,1,1)` and ranked types `b,c,a,a,a`, the allocation is
development ranks `(0,2)`, reserve `(1,3)`, untouched `(4)`. Choosing `(0,1)`
for development would needlessly eliminate reserve diversity and is forbidden.
The target has an independent matching condition: both pairs can be diverse
exactly when `sum(min(type_frequency, 2)) >= 4` for n >= 5.

### General proof and synthetic check

Two disjoint diverse pairs require two members outside a largest resource type.
Conversely, when `n - m >= 2` and `m >= 2`, choose two members of that largest
type and two outsiders, pairing one of each. If `m = 1`, any four are sufficient.
With exactly one outsider only development can be diverse; with none, neither
pair can be. This proves the target for every `n >= 5` and the matching condition.

Index the fresh subsequence from zero for this explanation only; this does not
change any hash, seed, or original total order. An optimal assignment can always
include its minimum element in development. For target `(1,1)`, start with any
feasible assignment. If the minimum is in reserve, exchange the two pairs. If
it is unselected, replace an endpoint of the development pair whose retained
partner has a different type from the minimum; such a partner always exists.
For `(1,0)`, pair the minimum with a member of the other type. For `(0,0)`, all
members have the same type.

Thus set `D_low = 0`, choose the smallest `D_high` attaining the development
target while leaving a feasible reserve, then the smallest remaining `R_low`
and the smallest compatible `R_high`. An unlike-type condition applies only
when that pair's diversity target is 1. These successive choices minimize the
declared tuple, not a proxy objective.

Retaining the first four fresh members of each resource type is sufficient for
selection. If an optimum used the fifth or later member of a type, at least one
of its four earlier same-type members would be unselected. Replacing the later
member preserves feasibility and improves the tuple, a contradiction. Four is
also the minimum uniform per-type prefix cap: all-same-type supply needs the
first four. With at most 15 types, this retains at most 60 selection candidates.
This is not a memory lower bound for every possible algorithm and does not
eliminate tail classification, total accounting, or direct member-root work.

On 2026-09-05, an in-memory check exhausted every resource-type equality pattern
of lengths 5–8 (52 + 203 + 877 + 4,140 = 5,272 patterns). The independent oracle
considered 1,942,800 disjoint pair allocations and minimized
`(-D_diverse, -R_diverse, D_low, D_high, R_low, R_high)`; the proposed procedure
matched in every case. This used synthetic integer labels only, no game member,
engine, or saved census rerun. The general proof and prefix bound were reviewed
independently. The finite check is supporting evidence, not the all-n proof or
a replacement for implementation tests. Production work remains to be bounded.

## Outputs and separate terminal questions

Report full grammar/stratum accounting, actual coverage, each exclusion count,
resource diversity, and separately the development, reserve, and untouched
counts/commitments. Reserve definitions must not be available to a future probe;
untouched membership must remain committed without exporting every definition.
Any intensional set commitment must explicitly define its predicate, exclusion
sets, source authorities, and membership verification; do not label it a direct
sorted-member hash.

In particular, define `untouched = fresh_eligible - (development union reserve)`.
A predicate commitment must bind the frozen grammar/setup/compiler/static-gate
authorities, authenticated census and history roots, exposure policy, predicate
version, exact canonical exclusion sets, identity relations, and representative
and weighted counts. Membership verification reconstructs a queried carrier,
checks its static/history predicates and canonical identity, and checks exclusion
from both selected sets. Comparing predicate roots alone is not proof of set
disjointness. Its concrete wire and computational bounds remain an activation
gate, not an invented already-sealed artifact.

`ACCOUNTING_COMPLETE` means every declared member is explained and all
commitments reconstruct. It is neither `READY_FOR_TERMINAL_BLIND_PROBE` under
Plan 0015 nor a fairness result. A second field reports actual development
availability, including `NO_DEVELOPMENT_SUPPORT` if all strata lack support.
Neither field authorizes an automatic game run.

Always retain the 109-class denominator and report action, goal-frame, vector-
profile, and contact coverage even when some values have no development supply.
Do not infer a minimum-coverage success rule after seeing the selected set.
Any later dynamic probe must preregister its own scope and coverage gate first.

Identity-only derivation for both first-player values is permitted before
partition solely for history matching, unless an authenticated whole-domain
nonintersection proof replaces it. Persist/export selected DSL definitions only
after the carrier's partition role is fixed. A-first and B-first are two separate
games; their combined results cannot be called fairness of a single definition.

## Activation gate and bounded next slice

Before this proposal becomes the sole active plan:

1. Accept the existing full regression and preserve Plan 0015's negative closeout.
2. Independently review the methodological change and rank/allocation contract.
3. Close intervening exposure and the computational work/commitment protocol.
4. Close the diagnostic purpose and evaluation-size question above; an allocation
   ceiling is not permission to evaluate every member.
5. Freeze the exact next slice and its failure conditions before implementation.

This coverage component's first implementation slice, if activated, is pure
accounting plus the
synthetic allocation primitive. It receives no historical raw bytes, game
engine, solver, agent, or candidate access. Complete production membership,
evidence lifecycle, and any dynamic probe require subsequent explicit reviewed
slices; they are not authorized by a permissive helper API or this draft.

## Reproduce the synthetic allocation check

This command consumes only integer-label equality patterns. It neither imports
project code nor reads or produces game/experiment artifacts.

```sh
python3 - <<'PY'
from collections import Counter
from itertools import combinations

def patterns(n, prefix=(0,)):
    if len(prefix) == n:
        yield prefix
    else:
        for kind in range(max(prefix) + 2):
            yield from patterns(n, prefix + (kind,))

def choose(types):
    n = len(types)
    outside = n - max(Counter(types).values())
    target = (int(outside >= 1), int(outside >= 2))
    assert bool(target[1]) == (sum(min(c, 2) for c in Counter(types).values()) >= 4)
    for hi in range(1, n):
        if int(types[0] != types[hi]) != target[0]:
            continue
        rest = [i for i in range(n) if i not in (0, hi)]
        for rhi in rest[1:]:
            if int(types[rest[0]] != types[rhi]) == target[1]:
                return (0, hi, rest[0], rhi)
    raise AssertionError("target has no allocation")

pattern_count = allocation_count = 0
for n in range(5, 9):
    count = 0
    for types in patterns(n):
        best = None
        for d in combinations(range(n), 2):
            for r in combinations([i for i in range(n) if i not in d], 2):
                key = (-int(types[d[0]] != types[d[1]]),
                       -int(types[r[0]] != types[r[1]]), *d, *r)
                best = key if best is None else min(best, key)
                allocation_count += 1
        assert choose(types) == best[2:]
        count += 1
    pattern_count += count
    print("n", n, "resource-type patterns", count)
assert choose((1, 2, 0, 0, 0)) == (0, 2, 1, 3)
assert (pattern_count, allocation_count) == (5272, 1942800)
print("patterns_checked", pattern_count, "oracle_allocations", allocation_count, "mismatches=0")
PY
```
