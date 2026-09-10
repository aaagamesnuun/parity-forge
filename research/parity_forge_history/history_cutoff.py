"""Pure cutoff-tree classifier for the Plan-0015 history firewall.

This module accepts path names and already-authenticated Git coordinates only.
It never accepts or reads artifact bytes, so candidate, journal, trace, result,
and outcome content cannot cross this boundary.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Sequence


HISTORY_CUTOFF_COMMIT_V1 = "0d041629bb584f47e7f10f1358f89e6920fee299"
HISTORY_CUTOFF_TREE_V1 = "4adb84cf439f07fad579d4a6a9999c07bb6f4853"
HISTORY_JSON_PATH_COUNT_V1 = 152_749
HISTORY_JSON_PATH_ROOT_V1 = (
    "0f0c50fcbdf6760d612afdd3923dbfe39763d04b176eabf06195ca66080bbf24"
)

LEGACY_HISTORY_CUTOFF_COMMIT_V1 = (
    "6910b6cc03c03701c56bc44d98bb9cf8ac5bf03c"
)
LEGACY_HISTORY_CUTOFF_TREE_V1 = "6bc44b1d51fcf67f691e5cc8106b1b1140947007"
LEGACY_HISTORY_PATH_COUNT_V1 = 66
LEGACY_HISTORY_PATH_ROOT_V1 = (
    "a572e32c6d10d2402a00780a37a4ae156778b02b85244f76ab0fbcbe50734801"
)

PLAN0013_PREFIX_V1 = (
    "experiments/runs/plan0013-atlas-development-evidence-v2/"
)
PLAN0013_PATH_COUNT_V1 = 152_678
PLAN0013_SUBTREE_V1 = "40f4b65f913a842a43e1b3a092a40cbb9933e489"

PLAN0014_PREFIX_V1 = (
    "experiments/runs/plan0014-plan0013-assessment-reconstruction-evidence-v1/"
)
PLAN0014_PATH_COUNT_V1 = 5
PLAN0014_SUBTREE_V1 = "beaed7c4bb82d0aa8d3e8e3d1a8f1d942de03f96"

_PATH_DOMAIN_V1 = b"parity-forge:plan0015:history-json-paths:v1\0"
_LEGACY_PATH_DOMAIN_V1 = b"parity-forge:plan0015:history-legacy-paths:v1\0"


class HistoryCutoffError(ValueError):
    """The supplied cutoff inventory escaped the fixed firewall."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _root(domain: bytes, value: Any) -> str:
    return hashlib.sha256(domain + _canonical_bytes(value)).hexdigest()


def _require_hex40(value: Any, expected: str, label: str) -> str:
    if type(value) is not str or value != expected:
        raise HistoryCutoffError("{} mismatch".format(label))
    return value


def classify_history_cutoff_paths_v1(
    paths: Sequence[str],
    *,
    cutoff_commit: str,
    cutoff_tree: str,
    plan0013_subtree: str,
    plan0014_subtree: str,
) -> Dict[str, Any]:
    """Validate and classify the complete fixed experiment-JSON path inventory."""

    _require_hex40(cutoff_commit, HISTORY_CUTOFF_COMMIT_V1, "history cutoff commit")
    _require_hex40(cutoff_tree, HISTORY_CUTOFF_TREE_V1, "history cutoff tree")
    _require_hex40(plan0013_subtree, PLAN0013_SUBTREE_V1, "Plan-0013 subtree")
    _require_hex40(plan0014_subtree, PLAN0014_SUBTREE_V1, "Plan-0014 subtree")
    if type(paths) not in (list, tuple):
        raise TypeError("history paths must be an exact list or tuple")
    if any(type(path) is not str for path in paths):
        raise TypeError("history paths must contain only strings")
    ordered = list(paths)
    if ordered != sorted(set(ordered)):
        raise HistoryCutoffError("history paths must be unique and lexically ordered")
    if len(ordered) != HISTORY_JSON_PATH_COUNT_V1:
        raise HistoryCutoffError("history JSON path count mismatch")
    if any(
        not path.startswith("experiments/") or not path.endswith(".json")
        for path in ordered
    ):
        raise HistoryCutoffError("history path escaped experiments JSON scope")
    if _root(_PATH_DOMAIN_V1, ordered) != HISTORY_JSON_PATH_ROOT_V1:
        raise HistoryCutoffError("history JSON path root mismatch")

    plan0013 = [path for path in ordered if path.startswith(PLAN0013_PREFIX_V1)]
    plan0014 = [path for path in ordered if path.startswith(PLAN0014_PREFIX_V1)]
    legacy = [
        path
        for path in ordered
        if not path.startswith(PLAN0013_PREFIX_V1)
        and not path.startswith(PLAN0014_PREFIX_V1)
    ]
    if len(plan0013) != PLAN0013_PATH_COUNT_V1:
        raise HistoryCutoffError("Plan-0013 path count mismatch")
    if len(plan0014) != PLAN0014_PATH_COUNT_V1:
        raise HistoryCutoffError("Plan-0014 path count mismatch")
    if len(legacy) != LEGACY_HISTORY_PATH_COUNT_V1:
        raise HistoryCutoffError("legacy history path count mismatch")
    if _root(_LEGACY_PATH_DOMAIN_V1, legacy) != LEGACY_HISTORY_PATH_ROOT_V1:
        raise HistoryCutoffError("legacy history path root mismatch")

    return {
        "history_cutoff_version": 1,
        "cutoff_commit": HISTORY_CUTOFF_COMMIT_V1,
        "cutoff_tree": HISTORY_CUTOFF_TREE_V1,
        "json_path_count": HISTORY_JSON_PATH_COUNT_V1,
        "json_path_root": HISTORY_JSON_PATH_ROOT_V1,
        "legacy": {
            "classification": "IDENTITY_SOURCE_SCAN_REQUIRED",
            "cutoff_commit": LEGACY_HISTORY_CUTOFF_COMMIT_V1,
            "cutoff_tree": LEGACY_HISTORY_CUTOFF_TREE_V1,
            "path_count": LEGACY_HISTORY_PATH_COUNT_V1,
            "path_root": LEGACY_HISTORY_PATH_ROOT_V1,
        },
        "plan0013": {
            "classification": "OLD_SIX_SEMANTIC_REGION_ALREADY_EXCLUDED",
            "path_count": PLAN0013_PATH_COUNT_V1,
            "subtree": PLAN0013_SUBTREE_V1,
            "artifacts_opened": 0,
        },
        "plan0014": {
            "classification": "DEFINITION_FREE_RECONSTRUCTION_EVIDENCE",
            "path_count": PLAN0014_PATH_COUNT_V1,
            "subtree": PLAN0014_SUBTREE_V1,
            "artifacts_opened": 0,
        },
    }


__all__ = [
    "HISTORY_CUTOFF_COMMIT_V1",
    "HISTORY_CUTOFF_TREE_V1",
    "HISTORY_JSON_PATH_COUNT_V1",
    "HISTORY_JSON_PATH_ROOT_V1",
    "HistoryCutoffError",
    "LEGACY_HISTORY_CUTOFF_COMMIT_V1",
    "LEGACY_HISTORY_CUTOFF_TREE_V1",
    "LEGACY_HISTORY_PATH_COUNT_V1",
    "LEGACY_HISTORY_PATH_ROOT_V1",
    "PLAN0013_PATH_COUNT_V1",
    "PLAN0013_SUBTREE_V1",
    "PLAN0014_PATH_COUNT_V1",
    "PLAN0014_SUBTREE_V1",
    "classify_history_cutoff_paths_v1",
]
