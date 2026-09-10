> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan 0015 — Static breadth floor is not met

Date: 2026-09-05. This is a read-only analysis of the existing sealed census,
not a new census run, partition, gameplay result, or replacement terminal seal.

## Conclusion and scope

The preregistered scientific decision is `BREADTH_FLOOR_NOT_MET`.
Nine of the 109 fresh role-neutral semantic classes contain **zero**
static-eligible carriers across all their profiled skeletons and both contact
classes. Historical exclusion can only remove carriers. Therefore no ranking,
history projection, or resource-diversity allocation can make all 109 classes
have a supported stratum of five fresh eligible carriers.

The static-census stage remains `COMPLETED`. Partition execution is
`NOT_STARTED`: no development, future-reserve, or untouched membership has been
allocated or published. This report must not be described as a completed
partition or as an additional machine-sealed execution lifecycle.

The negative breadth criterion was preregistered. Omitting the now-irrelevant
partition calculation is a closeout execution decision made after this
necessary-condition proof, not a previously registered early-stop procedure.
It neither relaxes the criterion nor selects a replacement subset.

This does **not** prove that the existing language lacks fair or enjoyable
games. The other 100 classes have static supply; their fairness and strategic
quality are unmeasured here. No action was applied and no outcome was computed.

## Authenticated evidence

The sole data source is
`experiments/runs/plan0015-factorized-static-census-evidence-v1/stages/plan0015-factorized-static-census-stage-v1/static-census-report.json`.

- Whole-file length: 17,284,867 bytes.
- SHA-256: `fa7daf48992f2b186fd980d42f670beda651b1adc7fe4c1fb62b67d1fdc05f97`.
- Report digest: `5da9d30090cfeb36fdcc4d78b1608c8adb381f6ea7a8579f1ed2717ef6bab68d`.
- Ordered shard root: `024d842ca744b49b475d87e5aaad80222fe4cce5db74e9f7e5c86b79239e2d87`.
- Existing terminal seal: `299a76910ee7fa072c0ec1b8cadb31d13714b922d0dcfa7c65c06e96e2306e34`.

The public compact reconstructor accepted the stored bytes, including all
1,518 shard commitments and aggregate roots. This did not revisit the
5,111,055 carrier leaves or repeat the one-shot production builder.
An independent reviewer also reproduced the counts both from recorded semantic
hashes and directly from unordered action/goal role-program pairs, and checked
all 3,036 contact totals against their 15 resource-count-pair rows.

## Necessary-condition calculation

Let E(s,c) be the recorded `eligible_representative_count` for skeleton s and
contact class c. Let F(s,c) be the number after historical exclusion.
The selection contract implies `0 <= F(s,c) <= E(s,c)`. A supported stratum
requires `F(s,c) >= 5`. Each missing class has `E(s,c) = 0` for every member s,c,
so its support is impossible independently of the unresolved partition.

Use representative carriers, not D4-weighted mass or paired first-player DSL
member counts. Contact classes are reported separately and are not combined to
reach the five-carrier floor.

| Unit | Zero eligible | 1–4 eligible | At least one eligible stratum with 5+ |
| --- | ---: | ---: | ---: |
| Semantic class | 9 | 0 | 100 |
| Profiled skeleton | 51 | 0 | 1,467 |

| Stratum class | Zero eligible | 1–4 eligible | 5+ eligible |
| --- | ---: | ---: | ---: |
| CONTACT | 51 | 0 | 1,467 |
| SEPARATED | 653 | 81 | 784 |
| Total | 704 | 81 | 2,251 |

The 2,251 rows with at least five are **potentially** supported before history
exclusion, not selected or confirmed fresh strata. Total static eligibility
remains 880,986 representatives.

## Nine zero-supply classes

Each row is a role-neutral action/goal pair; role labels and representative
vector profiles do not change its semantic identity. CONNECT abbreviates the
existing `CONNECT_EDGES` goal and REACH abbreviates `REACH_EDGE`.

| Semantic hash prefix | Role program pair | Skeletons | Carriers, all rejected |
| --- | --- | ---: | ---: |
| `01d91d729203` | CONVERT/ELIMINATE — PLACE/REACH | 3 | 10,533 |
| `0b3c1738502e` | CONVERT/REACH — MOVE_CAPTURE/ELIMINATE | 9 | 31,599 |
| `ae75a1c45575` | MOVE_CAPTURE/ELIMINATE — PLACE/CONNECT | 3 | 5,481 |
| `b11fe1010fc1` | CONVERT/ELIMINATE — CONVERT/REACH | 9 | 31,599 |
| `bb723b23d462` | CONVERT/CONNECT — MOVE_CAPTURE/ELIMINATE | 9 | 16,443 |
| `bc1e63d8fa1f` | CONVERT/ELIMINATE — CONVERT/ELIMINATE | 3 | 2,910 |
| `d0ea598081ed` | CONVERT/ELIMINATE — PLACE/CONNECT | 3 | 5,481 |
| `d356f1c410c3` | MOVE_CAPTURE/ELIMINATE — PLACE/REACH | 3 | 10,533 |
| `ea5f3539afa6` | CONVERT/CONNECT — CONVERT/ELIMINATE | 9 | 16,443 |

These 51 skeletons contain 131,022 factorized carriers. Their complete rejection
combinations are already committed in the census. A count-lattice failure
appears on 130,668 of them; the other 354 are rejected by other static gates.
Reasons overlap: these are descriptive counts, not a causal attribution or a
reason to retune a gate.

## Reproduction

From the repository root, the following read-only check authenticates the saved
report, verifies the per-stratum supply reconciliation, and derives the
negative necessary condition. It imports no legacy game package or engine.

```sh
PYTHONPATH=src python3 - <<'PY'
from collections import Counter, defaultdict
from pathlib import Path
from parity_forge_universe.static_census_reconstruction import (
    reconstruct_static_census_report_artifact_v1,
)

path = Path("experiments/runs/plan0015-factorized-static-census-evidence-v1/"
            "stages/plan0015-factorized-static-census-stage-v1/"
            "static-census-report.json")
checked = reconstruct_static_census_report_artifact_v1(path.read_bytes())
assert checked["report_ref"] == {
    "byte_count": 17284867,
    "sha256": "fa7daf48992f2b186fd980d42f670beda651b1adc7fe4c1fb62b67d1fdc05f97",
}
report = checked["report"]
by_semantic = defaultdict(list)
strata = Counter()
total = 0
for shard in report["skeleton_shards"]:
    supply = []
    for contact in ("CONTACT", "SEPARATED"):
        count = shard["contact"][contact]["eligible_representative_count"]
        assert count == sum(
            row["representative_count"]
            for row in shard["eligible_supply_by_count_pair_and_contact"]
            if row["contact_class"] == contact
        )
        supply.append(count)
        strata[(contact, "zero" if count == 0 else "short" if count < 5
                else "potential")] += 1
        total += count
    by_semantic[shard["skeleton"]["role_neutral_semantic_hash"]].append(supply)
missing = sorted(
    key for key, rows in by_semantic.items()
    if not any(count >= 5 for row in rows for count in row)
)
assert len(by_semantic) == 109 and len(missing) == 9
assert all(count == 0 for key in missing
           for row in by_semantic[key] for count in row)
assert sum(len(by_semantic[key]) for key in missing) == 51
assert total == 880986
assert strata == Counter({
    ("CONTACT", "zero"): 51, ("CONTACT", "potential"): 1467,
    ("SEPARATED", "zero"): 653, ("SEPARATED", "short"): 81,
    ("SEPARATED", "potential"): 784,
})
print("BREADTH_FLOOR_NOT_MET", "missing_semantic_classes=9", "partition=NOT_STARTED")
for key in missing:
    print(key)
PY
```

## Follow-through

Preserve the completed census, the historical identities, the old six-semantic-
region exclusion, and the unopened Plan-0013 candidate block. Do not rank or
backfill the 100 remaining classes inside Plan 0015. A later plan must register
its own hypothesis and scope before any new selection or rule change. Adding a
new primitive would not make the nine unchanged old classes supported and must
not be presented as repairing this breadth criterion.
