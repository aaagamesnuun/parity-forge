> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan-0016 design support — intervening static exposure

Status: source-only audit record, 2026-09-05. This supports the
[complete-accounting draft](0016-complete-accounting-partition.md); it is not an
executed attestation, a prospective freeze, a new history cutoff, or permission
to select or play games.

## Fixed boundary and inspected snapshot

The authoritative [history cutoff source](../../research/parity_forge_history/history_cutoff.py)
retains these coordinates:

- Cutoff commit: `0d041629bb584f47e7f10f1358f89e6920fee299`.
- Cutoff tree: `4adb84cf439f07fad579d4a6a9999c07bb6f4853`.
- Cutoff experiment-JSON inventory: 152,749 paths; path root
  `0f0c50fcbdf6760d612afdd3923dbfe39763d04b176eabf06195ca66080bbf24`.

This audit inspected Git metadata through HEAD
`9fdbdd1f96688ecac46d16ee409ee182425fac44`, tree
`817bf5d5f202275bdbf7af2d107146404a3dd2f7`, plus the then-uncommitted history
source/test additions described below. Those worktree files are not part of
the target Git tree.

The target contains 152,755 experiment JSON paths: exactly six additions and
no modified, deleted, or renamed prior JSON paths. Intervening commit path
metadata contains the same six additions and no transient extra JSON paths.
The original legacy files remain unchanged. The unopened legacy subtrees retain
their cutoff roots:

| Subtree under `experiments/runs/` | Git tree |
| --- | --- |
| `plan0013-atlas-development-evidence-v2` | `40f4b65f913a842a43e1b3a092a40cbb9933e489` |
| `plan0014-plan0013-assessment-reconstruction-evidence-v1` | `beaed7c4bb82d0aa8d3e8e3d1a8f1d942de03f96` |

## Exact additional experiment paths

All additions are regular Git blobs, mode `100644`, below
`experiments/runs/plan0015-factorized-static-census-evidence-v1/`. That subtree
has tree `ef2d0552040ec026895fd95c3dd578f20ecb09bb`; its
`stages/plan0015-factorized-static-census-stage-v1/` directory has tree
`7f290bd6400cdfc880ad2763179e19108b921aa0`.

In the following table, `stage/` abbreviates exactly
`stages/plan0015-factorized-static-census-stage-v1/` within that prefix.

| Relative path | Git blob | Bytes |
| --- | --- | ---: |
| `bootstrap.json` | `dfa32dc3e61466adf25e967a2fbe52dde7b23048` | 13,414 |
| `stage/attempt.json` | `a7bb5ddf2d67b922b484310e2347cfd6302e50fb` | 566 |
| `stage/completed.json` | `4ae1e1c993bf8a02b99aa6ebe04e6c2c7121588e` | 1,273 |
| `stage/reservation.json` | `85a3b2a7022f26595bc5288194505080956b8d1e` | 667 |
| `stage/static-census-report.json` | `612592a6b26c7e8e90014e5ad7fb2b5dd8af0cfe` | 17,284,867 |
| `stage/terminal-seal.json` | `0616ef3b3d90b1ecf0e0a3b9d5eb7c204c759c56` | 733 |

These are classified as static-census aggregate or lifecycle evidence, relying
on the previously accepted sealed provenance and the
[fixed production source closure](../../src/parity_forge_universe/static_census_protocol.py).
Its nine source files remain unchanged from evidence implementation commit
`e0f370c9e` through the inspected HEAD and worktree. The calculation derives
static initial structure; its contract excludes applying actions, computing
game outcomes, solver/agent/replay/telemetry execution, and candidate access.
Lifecycle words such as `completed` and `terminal-seal` describe the census
execution record, not a game's terminal result.

## Source and calibration exposure

The committed code delta adds nine universe modules, nine tests, and three
research classifier/package files. Legacy `src/parity_forge/` and the existing
agency benchmark test have no intervening changes.

The added compiler/universe tests inspect definitions and transformations.
The added initial-structure differential tests construct boards with `ply=0`
and `outcome=None`, call `legal_actions`, and compare goal predicates through
`goal_satisfied`; they do not apply moves. Static report and evidence tests
use static aggregates or synthetic lifecycle fixtures. These are static or
calibration exposures, not newly derived gameplay results.

The separately inspected uncommitted additions are
`research/parity_forge_history/{history_identity,history_pins,wire_identity}.py`
and `tests/test_history_{capability_boundary,identity,wire_identity}.py`.
They add parser-admission, normalization, D4/role/alpha-identity, malformed-input,
and compiler-exclusion fixtures. The existing benchmark fixture loader does
not invoke its gameplay test methods or telemetry functions. Invented `winner`
fields test independence from surrounding results; they are not game results.
No new gameplay execution call was found in these additions.

The separately pinned Plan-0013 synthetic fixture remains a pre-cutoff source
exposure with an outside-compiler witness. It neither becomes an eighth member
of the seven-fixture projection nor creates new gameplay evidence here.

## Limits and prospective obligation

This audit opened no experiment artifact or candidate, ran no test, census,
solver, replay, or game, and made no source change. Git path/type metadata alone
cannot prove artifact semantics; the six-path classification depends on the
already accepted production provenance. Source inspection is not an exhaustive
runtime exposure ledger and cannot establish what unrecorded work occurred.

No newly introduced gameplay-derived evidence requiring an additional history
identity was found in the inspected delta. Static exposure remains real and
must be disclosed separately. The frozen 66+7 projection and its original cutoff
remain unchanged; this record does not establish a complete later cutoff.

Before a prospective selection freeze, account for every subsequent tracked
and worktree source, test, fixture, and experiment change. Authenticate the
eventual source snapshot, classify static/calibration versus gameplay exposure,
and resolve any unknown or gameplay-bearing source through a reviewed identity
projection or a justified scope exclusion. Unresolved exposure blocks a claim
of complete history accounting; it must not be silently covered by this audit.
