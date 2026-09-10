"""Outcome-free cohort construction for the capture vector-boundary replication.

This module is deliberately pure: it performs no filesystem, Git, solving, or
play-agent work.  Callers authenticate and load bytes at the experiment edge,
then pass detached JSON values here for projection, cohort construction, and
public reconstruction.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from functools import lru_cache
from typing import Any, Dict, Iterable, Mapping, Sequence, Set, Tuple

from .analysis import analyze_definition
from .asymmetry import evaluate_asymmetry
from .capture import (
    CAPTURE_EXACT_MAX_STATES,
    CAPTURE_STATE_BOUND,
    _capture_treatment,
    _validate_source_family,
    _validate_treatment_pair,
    validate_capture_paired_manifest,
)
from .dsl import ActionKind, GameDefinition, InitialPiece, Player, definition_hash, parse_definition
from .engine import GameState, apply_action, legal_actions
from .landscape import RAW_D4_ORBIT_COUNT, RAW_DEFINITION_COUNT, _canonical_orbit_representatives
from .simplicity import evaluate_simplicity, exceeds_limits
from .symmetry import canonicalize_d4, d4_canonical_hash, mechanical_json


CAPTURE_BOUNDARY_MANIFEST_VERSION = 1
CAPTURE_BOUNDARY_MANIFEST_ID = "capture-boundary-v1-64-pair-manifest"
CAPTURE_BOUNDARY_MANIFEST_PROTOCOL_ID = "capture-boundary-v1-manifest-freeze"
CAPTURE_BOUNDARY_CUTOFF_COMMIT = "034759a"
CAPTURE_BOUNDARY_CUTOFF_COMMIT_FULL = "034759a0f8072db7462b009b3f160ec176212fd1"
CAPTURE_BOUNDARY_PAIR_COUNT = 64
CAPTURE_BOUNDARY_STRATUM_COUNT = 16
CAPTURE_BOUNDARY_QUOTA_PER_STRATUM = 4
CAPTURE_BOUNDARY_UNUSED_RELEVANT_ORBIT_COUNT = 724
CAPTURE_BOUNDARY_ELIGIBLE_ORBIT_COUNT = 563
CAPTURE_BOUNDARY_MIN_STRATUM_COUNT = 16

# Short aliases are kept for experiment-edge code that names the artifact rather
# than the experiment family.
BOUNDARY_MANIFEST_ID = CAPTURE_BOUNDARY_MANIFEST_ID
BOUNDARY_MANIFEST_PROTOCOL_ID = CAPTURE_BOUNDARY_MANIFEST_PROTOCOL_ID

CAPTURE_BOUNDARY_RUN_REGISTRY_COUNT = 16
CAPTURE_BOUNDARY_RUN_REGISTRY_ROOT = (
    "e85f0360182efcfcb7abf90fccafba912c440c8923883b1362031006724828a7"
)
CAPTURE_BOUNDARY_COVERAGE_OCCURRENCE_COUNT = 1_085
CAPTURE_BOUNDARY_COVERAGE_SCHEMA1_OCCURRENCE_COUNT = 827
CAPTURE_BOUNDARY_COVERED_D4_COUNT = 439
CAPTURE_BOUNDARY_COVERED_D4_ROOT = (
    "c3b49aa15300ea632acc2428073153c329f731b711078228537895342933e555"
)
CAPTURE_BOUNDARY_COVERAGE_ROOT = (
    "aff92eed1ff9b218431d2a92432597c10b37ddd0445fbea74c497d97f5b89164"
)
CAPTURE_BOUNDARY_DECLARED_EXCLUSION_COUNT = 650
CAPTURE_BOUNDARY_PRIOR_DEFINITION_OCCURRENCE_COUNT = 300
CAPTURE_BOUNDARY_PRIOR_UNIQUE_DEFINITION_COUNT = 270
CAPTURE_BOUNDARY_PRIOR_UNIQUE_D4_COUNT = 266
CAPTURE_BOUNDARY_PRIOR_BOARD3_D4_COUNT = 77
CAPTURE_BOUNDARY_PRIOR_MATCHED_D4_COUNT = 55
CAPTURE_BOUNDARY_LANDSCAPE_D4_COUNT = 384

CAPTURE_BOUNDARY_ELIGIBLE_POOL_ROOT = (
    "f739887b3f86f2e3652b8e526f1709efc706983329994f46afed4460843c1fcc"
)
CAPTURE_BOUNDARY_SELECTION_FINGERPRINT = (
    "8df3570000911a0d2c2ee3d052e5863f29fa2a72e64c33ccb7b9b544daa0ee56"
)
CAPTURE_BOUNDARY_SELECTION_PREFIX = "capture-boundary-v1:"
CAPTURE_BOUNDARY_LEDGER_ROOT = (
    "d257fb039ec8bd8c77ca1f955fcc94dc19658d527047983740eb72772eb36889"
)

CAPTURE_BOUNDARY_PRIOR_SOURCES = (
    (
        "experiments/runs/20260830T154155824053Z-batch-g20260831/run.json",
        "b664e133cda42b494d7222735999f0d7b490d9e0108e13743cef8dd20824bb97",
    ),
    (
        "experiments/runs/20260830T154309225370Z-batch-g20260831/run.json",
        "374bfc58030f0acce32a3edd7ff3d10764fb001d130eda4b1da086550b7cb0f5",
    ),
    (
        "experiments/runs/20260830T184008717197Z-strong-g20260901/run.json",
        "cdf26f22c93a95f70e413e28257a6afddfaecf21008507a6557e019f2c5357dc",
    ),
)
CAPTURE_BOUNDARY_LANDSCAPE_SOURCE = (
    "experiments/corpora/landscape-v1/manifest.json",
    "f407aefb5fdb8c926db282ff90d2feb1a8666cda3fdbd6925b9f5cc07abd87b1",
)
CAPTURE_BOUNDARY_LANDSCAPE_RAW_SHA256 = (
    "1edf571bc140a0cd586340eafee2306bccf6ca3a0816f8809b07edc9ef1a9fa4"
)
CAPTURE_BOUNDARY_PLAN0008_CHAIN = {
    "reservation_sha256": "3f67d49fe50e2c6897a689c9c3b9bd8bfbd1154c961a6e49b4608aa7fd7c2cbe",
    "attempt_sha256": "5f65911bc875495b81f5a9032c1ea218d7214402eb40f8ac814a54861b197c8f",
    "manifest_sha256": "6bc466453f60bc4ae2a6401fc76a77eebe4a7ebee82111e53ac4463400588f4f",
    "lock_sha256": "496a87ac1f169d7d6b19c29bf176a7af6f11ddc481578fcdab889b46f79b429f",
}

_EXPECTED_STRATUM_COUNTS = {
    "fA-aligned-corner-p18-v3": 37,
    "fA-aligned-corner-p18-v4": 57,
    "fA-aligned-edge_midpoint-p18-v3": 16,
    "fA-aligned-edge_midpoint-p18-v4": 29,
    "fA-orthogonal-corner-p18-v3": 39,
    "fA-orthogonal-corner-p18-v4": 56,
    "fA-orthogonal-edge_midpoint-p18-v3": 18,
    "fA-orthogonal-edge_midpoint-p18-v4": 28,
    "fB-aligned-corner-p18-v3": 39,
    "fB-aligned-corner-p18-v4": 57,
    "fB-aligned-edge_midpoint-p18-v3": 19,
    "fB-aligned-edge_midpoint-p18-v4": 28,
    "fB-orthogonal-corner-p18-v3": 38,
    "fB-orthogonal-corner-p18-v4": 57,
    "fB-orthogonal-edge_midpoint-p18-v3": 18,
    "fB-orthogonal-edge_midpoint-p18-v4": 27,
}

_PROJECTION_DOMAIN = b"capture-boundary-v1-definition-projection-v1"
_RUN_REGISTRY_DOMAIN = b"capture-boundary-v1-evaluated-run-registry-v1"
_RUN_COVERAGE_DOMAIN = b"capture-boundary-v1-run-coverage-v1"
_COVERED_D4_DOMAIN = b"capture-boundary-v1-evaluated-orbits-v1"
_COVERAGE_DOMAIN = b"capture-boundary-v1-coverage-projection-v1"
_DECLARED_EXCLUSION_DOMAIN = b"capture-boundary-v1-declared-exclusions-v1"
_MATCHED_EXCLUSION_DOMAIN = b"capture-boundary-v1-vocabulary-exclusions-v1"
_LEDGER_DOMAIN = b"capture-boundary-v1-exclusion-ledger-v1"
_ELIGIBLE_POOL_DOMAIN = b"capture-boundary-v1-eligible-pool-v1"
_ELIGIBLE_POOLS_DOMAIN = b"capture-boundary-v1-eligible-pools-v1"
_SELECTED_SOURCES_DOMAIN = b"capture-boundary-v1-selected-sources-v1"
_PAIR_DOMAIN = b"capture-boundary-v1-pair-v1"

_DEFINITION_BASE_KEYS = frozenset(
    ("schema_version", "name", "board_size", "first_player", "max_plies", "roles", "initial_pieces")
)
_PROJECTION_RECORD_KEYS = frozenset(
    ("json_path", "definition_hash", "d4_canonical_hash", "schema_version", "board_size", "definition")
)

_FROZEN_COVERAGE_TYPES = {
    "experiments/runs/20260830T153256441950Z-static-4ad81a40/run.json": "frozen-static-corpus",
    "experiments/runs/20260830T153616787888Z-play-1c478ea4/run.json": "frozen-definition-agent-comparison",
    "experiments/runs/20260830T153746479973Z-solve-1c478ea4/run.json": "exact-finite-game-solve",
    "experiments/runs/20260830T154155824053Z-batch-g20260831/run.json": "structured-random-generation-screening",
    "experiments/runs/20260830T154309225370Z-batch-g20260831/run.json": "structured-random-generation-screening",
    "experiments/runs/20260830T154446539528Z-audit-374bfc58/run.json": "exact-audit-of-sampled-batch",
    "experiments/runs/20260830T154624122230Z-calibrate-f27833e8/run.json": "agent-calibration-on-frozen-exact-corpus",
    "experiments/runs/20260830T154733530838Z-calibrate-f27833e8/run.json": "agent-calibration-on-frozen-exact-corpus",
    "experiments/runs/20260830T184008717197Z-strong-g20260901/run.json": "strong-cascade-held-out-generation",
    "experiments/runs/20260830T184737002247Z-blind-depth5-cdf26f22/run.json": "blind-depth5-audit-of-strong-heldout",
    "experiments/runs/20260830T200230881318Z-landscape-f407aefb/run.json": "frozen-3x3-exact-outcome-landscape",
    "experiments/runs/20260830T200513661140Z-draw-stress-1edf571b/run.json": "exact-draw-depth5-landscape-stress",
    "experiments/runs/20260830T214033891685Z-stalemate-ed9a9b93/run.json": "stalemate-draw-v1-v2-paired-exact",
    "experiments/runs/20260830T214159802995Z-stalemate-stress-239ad79d/run.json": "stalemate-draw-depth5-stress",
    "experiments/runs/20260830T225920216640Z-capture-6bc46645/run.json": "capture-v1-v3-paired-exact",
    "experiments/runs/20260830T230308952280Z-capture-stress-e4fc6e97/run.json": "capture-v1-depth5-interaction-stress",
}

_STATIC_CORPUS_DEPENDENCY = {
    "path": "experiments/corpora/static-v1/corpus.json",
    "sha256": "4ad81a4019f072a6f47d88e86f1761c0f55ef792f647d1348d292085496ce208",
    "identity_kind": "corpus_id",
    "identity": "static-v1-2026-08-31",
}
_LANDSCAPE_MANIFEST_DEPENDENCY = {
    "path": CAPTURE_BOUNDARY_LANDSCAPE_SOURCE[0],
    "sha256": CAPTURE_BOUNDARY_LANDSCAPE_SOURCE[1],
    "identity_kind": "manifest_id",
    "identity": "generator-v2-3x3-landscape-v1",
}
_STALEMATE_MANIFEST_DEPENDENCY = {
    "path": "experiments/corpora/stalemate-v1/manifest.json",
    "sha256": "ed9a9b93ad234f4375ded0e135f5436c82fb127988784a86aa33ab4f776ff176",
    "identity_kind": "manifest_id",
    "identity": "generator-v2-3x3-stalemate-paired-v1",
}
_CAPTURE_MANIFEST_DEPENDENCY = {
    "path": "experiments/corpora/capture-v1/manifest.json",
    "sha256": CAPTURE_BOUNDARY_PLAN0008_CHAIN["manifest_sha256"],
    "identity_kind": "manifest_id",
    "identity": "generator-v2-3x3-capture-paired-v1",
}
_SUPPORTING_CANONICAL_SHA256 = {
    _STATIC_CORPUS_DEPENDENCY["path"]: "fdb941261f382099c80c4091aec47dd298fe6dbb90477d84ed41cd470d23ccc2",
    _STALEMATE_MANIFEST_DEPENDENCY["path"]: "ce0823cb524da4ec8e14a2eaf65e7db52110dea1c91e6adcf2f20f4a5e83e2be",
    _CAPTURE_MANIFEST_DEPENDENCY["path"]: "c7621fd5056262f181b5003cada7971549a23726e85473b191e2428832962291",
}

_STATIC_PATH = "experiments/runs/20260830T153256441950Z-static-4ad81a40/run.json"
_PLAY_PATH = "experiments/runs/20260830T153616787888Z-play-1c478ea4/run.json"
_SOLVE_PATH = "experiments/runs/20260830T153746479973Z-solve-1c478ea4/run.json"
_GENERATOR_V1_PATH = CAPTURE_BOUNDARY_PRIOR_SOURCES[0][0]
_GENERATOR_V2_PATH = CAPTURE_BOUNDARY_PRIOR_SOURCES[1][0]
_AUDIT_PATH = "experiments/runs/20260830T154446539528Z-audit-374bfc58/run.json"
_CALIBRATION3_PATH = "experiments/runs/20260830T154624122230Z-calibrate-f27833e8/run.json"
_CALIBRATION5_PATH = "experiments/runs/20260830T154733530838Z-calibrate-f27833e8/run.json"
_HELDOUT_PATH = CAPTURE_BOUNDARY_PRIOR_SOURCES[2][0]
_BLIND_PATH = "experiments/runs/20260830T184737002247Z-blind-depth5-cdf26f22/run.json"
_LANDSCAPE_RUN_PATH = "experiments/runs/20260830T200230881318Z-landscape-f407aefb/run.json"
_LANDSCAPE_STRESS_PATH = "experiments/runs/20260830T200513661140Z-draw-stress-1edf571b/run.json"
_STALEMATE_RUN_PATH = "experiments/runs/20260830T214033891685Z-stalemate-ed9a9b93/run.json"
_STALEMATE_STRESS_PATH = "experiments/runs/20260830T214159802995Z-stalemate-stress-239ad79d/run.json"
_CAPTURE_RUN_PATH = "experiments/runs/20260830T225920216640Z-capture-6bc46645/run.json"
_CAPTURE_STRESS_PATH = "experiments/runs/20260830T230308952280Z-capture-stress-e4fc6e97/run.json"

_EXPECTED_PROJECTION_KINDS = {
    _STATIC_PATH: "OUTSIDE_VOCABULARY_STATIC_FIXTURE",
    _PLAY_PATH: "OUTSIDE_VOCABULARY_SINGLE_PLAY_FIXTURE",
    _SOLVE_PATH: "OUTSIDE_VOCABULARY_SINGLE_EXACT_FIXTURE",
    _GENERATOR_V1_PATH: "DIRECT_CANDIDATE_DEFINITIONS",
    _GENERATOR_V2_PATH: "DIRECT_CANDIDATE_DEFINITIONS",
    _AUDIT_PATH: "REFERENCE_GENERATOR_V2_DEVELOPMENT",
    _CALIBRATION3_PATH: "REFERENCE_GENERATOR_V2_DEVELOPMENT",
    _CALIBRATION5_PATH: "REFERENCE_GENERATOR_V2_DEVELOPMENT",
    _HELDOUT_PATH: "DIRECT_CANDIDATE_DEFINITIONS",
    _BLIND_PATH: "REFERENCE_HELDOUT_DEFINITIONS",
    _LANDSCAPE_RUN_PATH: "REFERENCE_LANDSCAPE_MANIFEST",
    _LANDSCAPE_STRESS_PATH: "REFERENCE_LANDSCAPE_RAW",
    _STALEMATE_RUN_PATH: "REFERENCE_STALEMATE_SOURCE_CLOSURE",
    _STALEMATE_STRESS_PATH: "REFERENCE_STALEMATE_SOURCE_CLOSURE",
    _CAPTURE_RUN_PATH: "REFERENCE_CAPTURE_SOURCE_CLOSURE",
    _CAPTURE_STRESS_PATH: "REFERENCE_CAPTURE_SOURCE_CLOSURE",
}
_FORBIDDEN_SELECTION_KEYS = frozenset(
    (
        "actual_result",
        "result",
        "results",
        "outcome",
        "winner",
        "terminal_reason",
        "value_for_a",
        "forced_result",
        "principal_variation",
        "evaluation",
        "evaluations",
        "analysis_gate_passes",
        "cheap_profiles",
        "cheap_failure_codes",
        "failure_codes",
        "play_profiles",
        "solve",
        "exact",
        "assessment",
        "assessments",
        "timing",
        "elapsed_seconds",
    )
)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _json_copy(value: Any, label: str) -> Any:
    try:
        return json.loads(_canonical_bytes(value))
    except (TypeError, ValueError) as error:
        raise ValueError("{} must be JSON-serializable".format(label)) from error


def _domain_digest(domain: bytes, value: Any) -> str:
    return hashlib.sha256(domain + b"\0" + _canonical_bytes(value)).hexdigest()


def _exact_keys(value: Any, expected: Iterable[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("{} must be an object".format(label))
    if not all(isinstance(key, str) for key in value):
        raise ValueError("{} keys must be strings".format(label))
    if set(value) != set(expected):
        raise ValueError(
            "{} fields mismatch: expected {}, observed {}".format(
                label, sorted(expected), sorted(value)
            )
        )
    return value


def _require_int(value: Any, expected: int, label: str) -> int:
    if type(value) is not int or value != expected:
        raise ValueError("{} must equal integer {}".format(label, expected))
    return value


def _require_sha256(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError("{} must be a lowercase SHA-256 hex digest".format(label))
    return value


def _require_sorted_hashes(value: Any, label: str) -> Tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError("{} must be an array".format(label))
    hashes = tuple(_require_sha256(item, label + " item") for item in value)
    if list(hashes) != sorted(set(hashes)):
        raise ValueError("{} must contain unique hashes in lexical order".format(label))
    return hashes


def _validated_dependencies(value: Any, label: str) -> Tuple[Dict[str, str], ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError("{} must be an array".format(label))
    dependencies = []
    for raw_dependency in value:
        dependency = _exact_keys(
            raw_dependency,
            ("path", "sha256", "identity_kind", "identity"),
            label + " item",
        )
        path = dependency["path"]
        if (
            not isinstance(path, str)
            or path.startswith("/")
            or ".." in path.split("/")
            or not path.startswith("experiments/")
        ):
            raise ValueError("{} paths must be repository-relative".format(label))
        identity_kind = dependency["identity_kind"]
        identity = dependency["identity"]
        if identity_kind not in ("run_id", "manifest_id", "corpus_id"):
            raise ValueError("{} identity_kind is invalid".format(label))
        if not isinstance(identity, str) or not identity:
            raise ValueError("{} identity must be a nonempty string".format(label))
        dependencies.append(
            {
                "path": path,
                "sha256": _require_sha256(dependency["sha256"], label + " SHA"),
                "identity_kind": identity_kind,
                "identity": identity,
            }
        )
    if [item["path"] for item in dependencies] != sorted({item["path"] for item in dependencies}):
        raise ValueError("{} must be unique and lexically ordered".format(label))
    return tuple(dependencies)


def _expected_direct_dependencies(
    path: str, registry_by_path: Mapping[str, Mapping[str, Any]]
) -> Tuple[Dict[str, str], ...]:
    def run_dependency(run_path: str) -> Dict[str, str]:
        entry = registry_by_path.get(run_path)
        if not isinstance(entry, Mapping):
            raise ValueError("coverage dependency is missing from the frozen registry")
        return {
            "path": run_path,
            "sha256": _require_sha256(entry.get("sha256"), "dependency run SHA"),
            "identity_kind": "run_id",
            "identity": run_path.split("/")[-2],
        }

    dependencies: list[Dict[str, str]]
    if path in (_STATIC_PATH, _PLAY_PATH, _SOLVE_PATH):
        dependencies = [dict(_STATIC_CORPUS_DEPENDENCY)]
    elif path in (_GENERATOR_V1_PATH, _GENERATOR_V2_PATH):
        dependencies = []
    elif path == _AUDIT_PATH:
        dependencies = [run_dependency(_GENERATOR_V2_PATH)]
    elif path in (_CALIBRATION3_PATH, _CALIBRATION5_PATH):
        dependencies = [run_dependency(_AUDIT_PATH), run_dependency(_GENERATOR_V2_PATH)]
    elif path == _HELDOUT_PATH:
        # The development batch is authenticated because it defines the held-out
        # novelty set, but the projection itself contains only held-out candidates.
        dependencies = [run_dependency(_GENERATOR_V2_PATH)]
    elif path == _BLIND_PATH:
        dependencies = [run_dependency(_HELDOUT_PATH)]
    elif path == _LANDSCAPE_RUN_PATH:
        dependencies = [dict(_LANDSCAPE_MANIFEST_DEPENDENCY)]
    elif path == _LANDSCAPE_STRESS_PATH:
        dependencies = [
            dict(_LANDSCAPE_MANIFEST_DEPENDENCY),
            run_dependency(_LANDSCAPE_RUN_PATH),
        ]
    elif path == _STALEMATE_RUN_PATH:
        dependencies = [dict(_STALEMATE_MANIFEST_DEPENDENCY), run_dependency(_LANDSCAPE_RUN_PATH)]
    elif path == _STALEMATE_STRESS_PATH:
        dependencies = [
            dict(_STALEMATE_MANIFEST_DEPENDENCY),
            run_dependency(_STALEMATE_RUN_PATH),
        ]
    elif path == _CAPTURE_RUN_PATH:
        dependencies = [dict(_CAPTURE_MANIFEST_DEPENDENCY), run_dependency(_LANDSCAPE_RUN_PATH)]
    elif path == _CAPTURE_STRESS_PATH:
        dependencies = [
            dict(_CAPTURE_MANIFEST_DEPENDENCY),
            run_dependency(_CAPTURE_RUN_PATH),
        ]
    else:
        raise ValueError("unknown frozen coverage path")
    return tuple(sorted(dependencies, key=lambda item: item["path"]))


def resolve_boundary_dependency_closure(
    direct_dependencies: Mapping[str, Sequence[Mapping[str, Any]]],
    known_dependencies: Sequence[Mapping[str, Any]],
) -> Dict[str, list[Dict[str, str]]]:
    """Resolve an authenticated dependency DAG or reject unknowns and cycles."""

    if not isinstance(direct_dependencies, Mapping):
        raise ValueError("direct dependency graph must be an object")
    known = _validated_dependencies(known_dependencies, "known dependencies")
    known_by_path = {dependency["path"]: dependency for dependency in known}
    if set(direct_dependencies) != set(known_by_path):
        raise ValueError("direct dependency graph must define every known artifact exactly once")
    graph: Dict[str, Tuple[Dict[str, str], ...]] = {}
    for path, raw_items in direct_dependencies.items():
        if path not in known_by_path:
            raise ValueError("direct dependency graph contains an unknown node")
        items = _validated_dependencies(raw_items, "direct dependencies for " + path)
        for item in items:
            expected = known_by_path.get(item["path"])
            if expected is None:
                raise ValueError("dependency graph contains an unresolved artifact")
            if _canonical_bytes(item) != _canonical_bytes(expected):
                raise ValueError("dependency graph artifact identity mismatch")
        graph[path] = items

    complete: Dict[str, Tuple[Dict[str, str], ...]] = {}
    active: Set[str] = set()

    def visit(path: str) -> Tuple[Dict[str, str], ...]:
        if path in complete:
            return complete[path]
        if path in active:
            raise ValueError("dependency graph contains a cycle")
        active.add(path)
        closure_by_path: Dict[str, Dict[str, str]] = {}
        for dependency in graph[path]:
            closure_by_path[dependency["path"]] = dependency
            for inherited in visit(dependency["path"]):
                closure_by_path[inherited["path"]] = inherited
        active.remove(path)
        closure = tuple(
            closure_by_path[candidate] for candidate in sorted(closure_by_path)
        )
        complete[path] = closure
        return closure

    for path in sorted(graph):
        visit(path)
    return {path: [dict(item) for item in complete[path]] for path in sorted(complete)}


def _contains_forbidden_selection_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            key in _FORBIDDEN_SELECTION_KEYS or _contains_forbidden_selection_key(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_forbidden_selection_key(item) for item in value)
    return False


def _pointer_token(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def project_boundary_definitions(value: Any) -> Dict[str, Any]:
    """Recursively project only exact DSL definitions from an arbitrary JSON value.

    Object keys are traversed lexically and arrays by index.  All surrounding
    values, including outcomes, timings, and evaluator fields, are ignored.
    Definition-like objects with malformed or extended schemas are rejected so a
    source cannot evade projection by adding one field.
    """

    detached = _json_copy(value, "definition projection source")
    records = []

    def visit(item: Any, path: str) -> None:
        if isinstance(item, dict):
            if _DEFINITION_BASE_KEYS <= set(item):
                definition = parse_definition(item)
                canonical = definition.to_dict()
                records.append(
                    {
                        "json_path": path,
                        "definition_hash": definition_hash(definition),
                        "d4_canonical_hash": d4_canonical_hash(definition),
                        "schema_version": definition.schema_version,
                        "board_size": definition.board_size,
                        "definition": canonical,
                    }
                )
                return
            for key in sorted(item):
                if not isinstance(key, str):
                    raise ValueError("definition projection object keys must be strings")
                visit(item[key], path + "/" + _pointer_token(key))
        elif isinstance(item, list):
            for index, child in enumerate(item):
                visit(child, path + "/" + str(index))

    visit(detached, "")
    records.sort(key=lambda record: record["json_path"])
    projection = {
        "projection_version": 1,
        "occurrence_count": len(records),
        "projection_root": _domain_digest(_PROJECTION_DOMAIN, records),
        "records": records,
    }
    validate_boundary_definition_projection(projection)
    return projection


def validate_boundary_definition_projection(value: Any) -> Tuple[Dict[str, Any], ...]:
    """Strictly validate a detached definition-only projection."""

    top = _exact_keys(
        value,
        ("projection_version", "occurrence_count", "projection_root", "records"),
        "definition projection",
    )
    _require_int(top["projection_version"], 1, "definition projection version")
    if not isinstance(top["records"], list):
        raise ValueError("definition projection records must be an array")
    records = []
    paths = []
    for index, raw_record in enumerate(top["records"]):
        record = _exact_keys(raw_record, _PROJECTION_RECORD_KEYS, "definition projection record")
        path = record["json_path"]
        if not isinstance(path, str):
            raise ValueError("definition projection path must be a string")
        definition = parse_definition(record["definition"])
        if _canonical_bytes(record["definition"]) != _canonical_bytes(definition.to_dict()):
            raise ValueError("projected definition must use canonical DSL bytes")
        if (
            _require_sha256(record["definition_hash"], "projected definition hash")
            != definition_hash(definition)
            or _require_sha256(record["d4_canonical_hash"], "projected D4 hash")
            != d4_canonical_hash(definition)
        ):
            raise ValueError("projected definition identity mismatch")
        _require_int(record["schema_version"], definition.schema_version, "projected schema version")
        _require_int(record["board_size"], definition.board_size, "projected board size")
        paths.append(path)
        records.append(_json_copy(record, "definition projection record"))
    if paths != sorted(set(paths)):
        raise ValueError("definition projection paths must be unique and ordered")
    _require_int(top["occurrence_count"], len(records), "definition occurrence count")
    if (
        _require_sha256(top["projection_root"], "definition projection root")
        != _domain_digest(_PROJECTION_DOMAIN, records)
    ):
        raise ValueError("definition projection root mismatch")
    return tuple(records)


def _validated_registry_entries(value: Any) -> Tuple[Dict[str, str], ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError("evaluated-run registry must be an array")
    entries = []
    for raw_entry in value:
        entry = _exact_keys(raw_entry, ("path", "sha256"), "evaluated-run registry entry")
        path = entry["path"]
        if (
            not isinstance(path, str)
            or not path.startswith("experiments/runs/")
            or not path.endswith("/run.json")
            or path.startswith("/")
            or ".." in path.split("/")
        ):
            raise ValueError("evaluated-run path must be canonical and repository-relative")
        entries.append({"path": path, "sha256": _require_sha256(entry["sha256"], "run SHA")})
    if [entry["path"] for entry in entries] != sorted({entry["path"] for entry in entries}):
        raise ValueError("evaluated-run registry must be unique and lexically ordered")
    if len(entries) != CAPTURE_BOUNDARY_RUN_REGISTRY_COUNT:
        raise ValueError("evaluated-run registry count mismatch")
    if _domain_digest(_RUN_REGISTRY_DOMAIN, entries) != CAPTURE_BOUNDARY_RUN_REGISTRY_ROOT:
        raise ValueError("evaluated-run registry root mismatch")
    return tuple(entries)


def build_boundary_coverage_projection(
    registry_entries: Sequence[Mapping[str, Any]],
    run_projections: Mapping[str, Mapping[str, Any]],
    resolution_records: Mapping[str, Mapping[str, Any]],
    dependency_artifacts: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Build the frozen definition-only coverage witness for the 16-run registry."""

    entries = _validated_registry_entries(registry_entries)
    if not isinstance(run_projections, Mapping) or set(run_projections) != {
        entry["path"] for entry in entries
    }:
        raise ValueError("run projections must map every registry path exactly once")
    vocabulary = set(dict(_canonical_orbit_representatives()))
    records = []
    covered: Set[str] = set()
    total_occurrences = 0
    schema1_occurrences = 0
    for entry in entries:
        path = entry["path"]
        projected_records = validate_boundary_definition_projection(run_projections[path])
        total_occurrences += len(projected_records)
        schema1_records = [record for record in projected_records if record["schema_version"] == 1]
        schema1_occurrences += len(schema1_records)
        inline_hashes = sorted(
            {
                record["d4_canonical_hash"]
                for record in schema1_records
                if record["d4_canonical_hash"] in vocabulary
            }
        )
        if not isinstance(resolution_records, Mapping) or set(resolution_records) != {
            candidate["path"] for candidate in entries
        }:
            raise ValueError("coverage resolution records must cover every registry path")
        resolution = _exact_keys(
            resolution_records[path],
            ("projection_kind", "direct_dependencies", "dependencies", "projected_d4_hashes"),
            "coverage resolution record",
        )
        projection_kind = resolution["projection_kind"]
        if not isinstance(projection_kind, str) or not projection_kind:
            raise ValueError("coverage projection kind must be a nonempty string")
        direct_dependencies = list(
            _validated_dependencies(resolution["direct_dependencies"], "coverage direct dependencies")
        )
        dependencies = list(_validated_dependencies(resolution["dependencies"], "coverage dependencies"))
        projected_hashes = list(
            _require_sorted_hashes(resolution["projected_d4_hashes"], "resolved projected D4 hashes")
        )
        if not set(inline_hashes) <= set(projected_hashes):
            raise ValueError("coverage resolution omits an embedded in-vocabulary definition")
        covered.update(projected_hashes)
        record = {
            "path": path,
            "sha256": entry["sha256"],
            "projection_kind": projection_kind,
            "direct_dependencies": direct_dependencies,
            "dependencies": dependencies,
            "definition_projection_root": run_projections[path]["projection_root"],
            "definition_occurrence_count": len(projected_records),
            "schema1_occurrence_count": len(schema1_records),
            "projected_d4_count": len(projected_hashes),
            "projected_d4_hashes": projected_hashes,
            "projected_d4_root": _domain_digest(_RUN_COVERAGE_DOMAIN, projected_hashes),
        }
        records.append(record)
    covered_hashes = sorted(covered)
    artifacts = list(_validated_dependencies(dependency_artifacts, "coverage dependency artifacts"))
    coverage = {
        "coverage_version": 1,
        "cutoff_commit": CAPTURE_BOUNDARY_CUTOFF_COMMIT,
        "registry_count": len(entries),
        "registry_root": _domain_digest(_RUN_REGISTRY_DOMAIN, list(entries)),
        "dependency_artifacts": artifacts,
        "definition_occurrence_count": total_occurrences,
        "schema1_occurrence_count": schema1_occurrences,
        "covered_vocabulary_d4_count": len(covered_hashes),
        "covered_vocabulary_d4_hashes": covered_hashes,
        "covered_vocabulary_d4_root": _domain_digest(_COVERED_D4_DOMAIN, covered_hashes),
        "records": records,
    }
    coverage["coverage_root"] = _domain_digest(_COVERAGE_DOMAIN, coverage)
    validate_boundary_coverage_projection(coverage)
    return coverage


def _repository_json_bytes(value: Any) -> bytes:
    try:
        return (
            json.dumps(
                value,
                indent=2,
                sort_keys=True,
                ensure_ascii=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ValueError("authenticated source must be canonical JSON") from error


def _recorded_path_matches(value: Any, expected: str) -> bool:
    return isinstance(value, str) and (
        value == expected or value.endswith("/" + expected)
    )


def _validate_run_dependency_configuration(
    path: str,
    raw_record: Mapping[str, Any],
    direct_dependencies: Sequence[Mapping[str, Any]],
) -> None:
    """Match every frozen direct dependency to the authenticated run config."""

    configuration = raw_record.get("configuration")
    if not isinstance(configuration, Mapping):
        raise ValueError("coverage run configuration must be an object")
    by_path = {dependency["path"]: dependency for dependency in direct_dependencies}

    def require_reference(
        dependency_path: str,
        recorded_path: Any = None,
        recorded_identity: Any = None,
        recorded_sha256: Any = None,
    ) -> None:
        dependency = by_path.get(dependency_path)
        if dependency is None:
            raise ValueError("run configuration dependency is absent from its direct ledger")
        if recorded_path is not None and not _recorded_path_matches(recorded_path, dependency_path):
            raise ValueError("run configuration dependency path mismatch")
        if recorded_identity is not None and recorded_identity != dependency["identity"]:
            raise ValueError("run configuration dependency identity mismatch")
        if recorded_sha256 is not None and recorded_sha256 != dependency["sha256"]:
            raise ValueError("run configuration dependency SHA mismatch")

    if path == _STATIC_PATH:
        require_reference(
            _STATIC_CORPUS_DEPENDENCY["path"],
            configuration.get("corpus_path"),
            recorded_sha256=configuration.get("corpus_sha256"),
        )
    elif path in (_PLAY_PATH, _SOLVE_PATH):
        source = configuration.get("source")
        if not isinstance(source, Mapping):
            raise ValueError("single-definition fixture source must be an object")
        require_reference(
            _STATIC_CORPUS_DEPENDENCY["path"], source.get("corpus_path")
        )
    elif path in (_GENERATOR_V1_PATH, _GENERATOR_V2_PATH):
        if direct_dependencies:
            raise ValueError("direct generator carriers must have no dependency")
    elif path == _AUDIT_PATH:
        require_reference(
            _GENERATOR_V2_PATH,
            configuration.get("source_batch_path"),
            configuration.get("source_batch_run_id"),
            configuration.get("source_batch_sha256"),
        )
    elif path in (_CALIBRATION3_PATH, _CALIBRATION5_PATH):
        require_reference(
            _AUDIT_PATH,
            recorded_identity=configuration.get("source_audit_run_id"),
        )
        if configuration.get("source_sha256") != (
            "f27833e8641e26f229d785f021ef3bcb0ff477c623e1fe5e2889de0511713411"
        ):
            raise ValueError("calibration frozen source projection SHA mismatch")
        require_reference(
            _GENERATOR_V2_PATH,
            recorded_identity=configuration.get("source_batch_run_id"),
        )
    elif path == _HELDOUT_PATH:
        source = configuration.get("development_source")
        if not isinstance(source, Mapping):
            raise ValueError("held-out development source must be an object")
        require_reference(
            _GENERATOR_V2_PATH,
            source.get("path"),
            source.get("run_id"),
            source.get("sha256"),
        )
    elif path == _BLIND_PATH:
        require_reference(
            _HELDOUT_PATH,
            configuration.get("source_strong_run_path"),
            configuration.get("source_strong_run_id"),
            configuration.get("source_strong_run_sha256"),
        )
    elif path == _LANDSCAPE_RUN_PATH:
        require_reference(
            _LANDSCAPE_MANIFEST_DEPENDENCY["path"],
            configuration.get("manifest_path"),
            configuration.get("manifest_id"),
            configuration.get("manifest_sha256"),
        )
    elif path == _LANDSCAPE_STRESS_PATH:
        require_reference(
            _LANDSCAPE_RUN_PATH,
            configuration.get("source_raw_run_path"),
            configuration.get("source_raw_run_id"),
            configuration.get("source_raw_run_sha256"),
        )
        require_reference(
            _LANDSCAPE_MANIFEST_DEPENDENCY["path"],
            recorded_sha256=configuration.get("manifest_sha256"),
        )
    elif path in (_STALEMATE_RUN_PATH, _CAPTURE_RUN_PATH):
        manifest_dependency = (
            _STALEMATE_MANIFEST_DEPENDENCY
            if path == _STALEMATE_RUN_PATH
            else _CAPTURE_MANIFEST_DEPENDENCY
        )
        require_reference(
            manifest_dependency["path"],
            configuration.get("manifest_path"),
            configuration.get("manifest_id"),
            configuration.get("manifest_sha256"),
        )
        require_reference(
            _LANDSCAPE_RUN_PATH,
            configuration.get("source_landscape_raw_path"),
            configuration.get("source_landscape_raw_run_id"),
            configuration.get("source_landscape_raw_sha256"),
        )
    elif path in (_STALEMATE_STRESS_PATH, _CAPTURE_STRESS_PATH):
        manifest_dependency = (
            _STALEMATE_MANIFEST_DEPENDENCY
            if path == _STALEMATE_STRESS_PATH
            else _CAPTURE_MANIFEST_DEPENDENCY
        )
        source_path = (
            _STALEMATE_RUN_PATH if path == _STALEMATE_STRESS_PATH else _CAPTURE_RUN_PATH
        )
        require_reference(
            manifest_dependency["path"],
            configuration.get("manifest_path"),
            configuration.get("manifest_id"),
            configuration.get("manifest_sha256"),
        )
        require_reference(
            source_path,
            configuration.get("source_raw_path"),
            configuration.get("source_raw_run_id"),
            configuration.get("source_raw_sha256"),
        )
    else:
        raise ValueError("unknown closed-world run dependency adapter")


def build_boundary_projection_bundle(
    source_projections: Sequence[Mapping[str, Any]],
    registry_entries: Sequence[Mapping[str, Any]],
    run_projections: Mapping[str, Mapping[str, Any]],
    resolution_records: Mapping[str, Mapping[str, Any]],
    dependency_artifacts: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Build selection inputs from detached definition/identity projections only.

    Unlike :func:`project_boundary_exclusion_sources`, this capability boundary
    cannot accept full run records: every source value must satisfy the strict
    definition-projection schema before census or cohort construction begins.
    """

    if not isinstance(source_projections, (list, tuple)) or len(source_projections) != 4:
        raise ValueError("pure boundary projection requires four source projections")
    for projection in source_projections:
        validate_boundary_definition_projection(projection)
    coverage_projection = build_boundary_coverage_projection(
        registry_entries,
        run_projections,
        resolution_records,
        dependency_artifacts,
    )
    exclusion_ledger = build_boundary_exclusion_ledger(
        source_projections[:3], source_projections[3], coverage_projection
    )
    bundle = {
        "exclusion_ledger": exclusion_ledger,
        "coverage_projection": coverage_projection,
    }
    if _contains_forbidden_selection_key(bundle):
        raise AssertionError("pure projection bundle exposed outcome/timing fields")
    return _json_copy(bundle, "pure boundary projection bundle")


def project_boundary_exclusion_sources(
    source_records: Sequence[Mapping[str, Any]],
    source_metadata: Sequence[Mapping[str, Any]],
    supporting_dependency_records: Sequence[Mapping[str, Any]],
    supporting_dependency_metadata: Sequence[Mapping[str, Any]],
    coverage_records: Sequence[Mapping[str, Any]],
    coverage_registry: Mapping[str, Any],
) -> Dict[str, Any]:
    """Edge adapter: authenticate full runner inputs, then discard outcome data.

    The closed-world adapter recognizes only the 16 experiment types and paths at
    the evaluated cutoff.  Direct carriers project their candidate definitions;
    reference-only records inherit an authenticated dependency projection.  An
    unknown type, unresolved dependency, or in-vocabulary embedded definition
    outside that resolved set is rejected.  Only detached definition/identity
    projections cross into :func:`build_boundary_projection_bundle`.
    """

    if not isinstance(source_records, (list, tuple)) or len(source_records) != 4:
        raise ValueError("exclusion projection requires four ordered source records")
    if not isinstance(source_metadata, (list, tuple)) or len(source_metadata) != 4:
        raise ValueError("exclusion projection requires four ordered source metadata records")
    expected_metadata = (
        {
            "label": "generator-v1-development",
            "path": CAPTURE_BOUNDARY_PRIOR_SOURCES[0][0],
            "sha256": CAPTURE_BOUNDARY_PRIOR_SOURCES[0][1],
            "run_id": "20260830T154155824053Z-batch-g20260831",
        },
        {
            "label": "generator-v2-development",
            "path": CAPTURE_BOUNDARY_PRIOR_SOURCES[1][0],
            "sha256": CAPTURE_BOUNDARY_PRIOR_SOURCES[1][1],
            "run_id": "20260830T154309225370Z-batch-g20260831",
        },
        {
            "label": "generator-v2-heldout-20260901",
            "path": CAPTURE_BOUNDARY_PRIOR_SOURCES[2][0],
            "sha256": CAPTURE_BOUNDARY_PRIOR_SOURCES[2][1],
            "run_id": "20260830T184008717197Z-strong-g20260901",
        },
        {
            "label": "landscape-v1-manifest",
            "path": CAPTURE_BOUNDARY_LANDSCAPE_SOURCE[0],
            "sha256": CAPTURE_BOUNDARY_LANDSCAPE_SOURCE[1],
            "manifest_id": "generator-v2-3x3-landscape-v1",
        },
    )
    if _canonical_bytes(source_metadata) != _canonical_bytes(expected_metadata):
        raise ValueError("pinned exclusion source metadata mismatch")
    source_projections = []
    for index, (raw_record, metadata) in enumerate(zip(source_records, expected_metadata)):
        if not isinstance(raw_record, Mapping):
            raise ValueError("pinned exclusion source must be an object")
        if hashlib.sha256(_repository_json_bytes(raw_record)).hexdigest() != metadata["sha256"]:
            raise ValueError("pinned exclusion source canonical-byte SHA mismatch")
        identity_key = "manifest_id" if index == 3 else "run_id"
        expected_status = "FROZEN" if index == 3 else "COMPLETED"
        if raw_record.get(identity_key) != metadata[identity_key] or raw_record.get("status") != expected_status:
            raise ValueError("pinned exclusion source identity or status mismatch")
        if index < 3 and raw_record.get("experiment_type") != _FROZEN_COVERAGE_TYPES[metadata["path"]]:
            raise ValueError("pinned exclusion source experiment type mismatch")
        source_projections.append(project_boundary_definitions(raw_record))

    expected_supporting_metadata = (
        dict(_STATIC_CORPUS_DEPENDENCY),
        dict(_STALEMATE_MANIFEST_DEPENDENCY),
        dict(_CAPTURE_MANIFEST_DEPENDENCY),
    )
    if (
        not isinstance(supporting_dependency_records, (list, tuple))
        or len(supporting_dependency_records) != 3
        or not isinstance(supporting_dependency_metadata, (list, tuple))
        or _canonical_bytes(supporting_dependency_metadata)
        != _canonical_bytes(expected_supporting_metadata)
    ):
        raise ValueError("supporting dependency records or metadata mismatch")
    supporting_by_path: Dict[str, Mapping[str, Any]] = {}
    for raw_record, metadata in zip(
        supporting_dependency_records, expected_supporting_metadata
    ):
        if not isinstance(raw_record, Mapping):
            raise ValueError("supporting dependency must be an object")
        canonical_sha = hashlib.sha256(_canonical_bytes(raw_record)).hexdigest()
        if canonical_sha != _SUPPORTING_CANONICAL_SHA256[metadata["path"]]:
            raise ValueError("supporting dependency canonical JSON identity mismatch")
        # Exact file-byte SHA is authenticated by the edge loader and is pinned
        # independently in metadata; the pure layer additionally authenticates
        # the detached JSON value above because custom static-corpus formatting
        # cannot be reconstructed from a parsed mapping.
        _require_sha256(metadata["sha256"], "supporting dependency file SHA")
        if raw_record.get(metadata["identity_kind"]) != metadata["identity"]:
            raise ValueError("supporting dependency identity mismatch")
        supporting_by_path[metadata["path"]] = raw_record
    static_record = supporting_by_path[_STATIC_CORPUS_DEPENDENCY["path"]]
    if static_record.get("frozen") is not True:
        raise ValueError("static corpus must be explicitly frozen")
    stalemate_manifest = supporting_by_path[_STALEMATE_MANIFEST_DEPENDENCY["path"]]
    if (
        stalemate_manifest.get("protocol_id") != "stalemate-v1-paired-manifest-freeze"
        or stalemate_manifest.get("source_manifest_id")
        != _LANDSCAPE_MANIFEST_DEPENDENCY["identity"]
        or stalemate_manifest.get("source_manifest_sha256")
        != _LANDSCAPE_MANIFEST_DEPENDENCY["sha256"]
    ):
        raise ValueError("stalemate supporting manifest protocol or landscape source mismatch")
    capture_manifest = supporting_by_path[_CAPTURE_MANIFEST_DEPENDENCY["path"]]
    capture_source = capture_manifest.get("source")
    if (
        capture_manifest.get("protocol_id") != "capture-v1-paired-manifest-freeze"
        or capture_manifest.get("status") != "FROZEN"
        or not isinstance(capture_source, Mapping)
        or capture_source.get("manifest_id") != _LANDSCAPE_MANIFEST_DEPENDENCY["identity"]
        or capture_source.get("manifest_sha256") != _LANDSCAPE_MANIFEST_DEPENDENCY["sha256"]
    ):
        raise ValueError("capture supporting manifest protocol or landscape source mismatch")

    if isinstance(coverage_registry, Mapping):
        registry = _exact_keys(
            coverage_registry,
            ("cutoff_commit", "run_count", "root_sha256", "entries"),
            "coverage registry",
        )
    elif isinstance(coverage_registry, (list, tuple)):
        # Compatibility with a loader that returns the already authenticated
        # ordered payload directly.  The same count/root are recomputed below.
        registry = {
            "cutoff_commit": CAPTURE_BOUNDARY_CUTOFF_COMMIT_FULL,
            "run_count": len(coverage_registry),
            "root_sha256": _domain_digest(_RUN_REGISTRY_DOMAIN, list(coverage_registry)),
            "entries": list(coverage_registry),
        }
    else:
        raise ValueError("coverage registry must be an object or ordered entry array")
    if registry["cutoff_commit"] != CAPTURE_BOUNDARY_CUTOFF_COMMIT_FULL:
        raise ValueError("coverage registry cutoff commit mismatch")
    _require_int(registry["run_count"], CAPTURE_BOUNDARY_RUN_REGISTRY_COUNT, "coverage registry run count")
    if _require_sha256(registry["root_sha256"], "coverage registry root") != CAPTURE_BOUNDARY_RUN_REGISTRY_ROOT:
        raise ValueError("coverage registry root mismatch")
    entries = _validated_registry_entries(registry["entries"])
    if [entry["path"] for entry in entries] != list(_FROZEN_COVERAGE_TYPES):
        raise ValueError("coverage registry paths do not match the frozen closed world")
    if not isinstance(coverage_records, (list, tuple)) or len(coverage_records) != len(entries):
        raise ValueError("coverage records must match the frozen registry cardinality")
    run_projections: Dict[str, Mapping[str, Any]] = {}
    raw_by_path: Dict[str, Mapping[str, Any]] = {}
    for raw_record, entry in zip(coverage_records, entries):
        if not isinstance(raw_record, Mapping):
            raise ValueError("coverage run record must be an object")
        path = entry["path"]
        if hashlib.sha256(_repository_json_bytes(raw_record)).hexdigest() != entry["sha256"]:
            raise ValueError("coverage run canonical-byte SHA mismatch for {}".format(path))
        expected_run_id = path.split("/")[-2]
        if (
            raw_record.get("run_id") != expected_run_id
            or raw_record.get("status") != "COMPLETED"
            or raw_record.get("experiment_type") != _FROZEN_COVERAGE_TYPES[path]
        ):
            raise ValueError("coverage run identity, status, or experiment type mismatch for {}".format(path))
        raw_by_path[path] = raw_record
        run_projections[path] = project_boundary_definitions(raw_record)
    for index, (path, _) in enumerate(CAPTURE_BOUNDARY_PRIOR_SOURCES):
        if _canonical_bytes(raw_by_path[path]) != _canonical_bytes(source_records[index]):
            raise ValueError("pinned source and cutoff registry bytes disagree for {}".format(path))

    vocabulary = set(dict(_canonical_orbit_representatives()))

    def schema1_vocabulary_hashes(projection: Mapping[str, Any]) -> Tuple[str, ...]:
        return tuple(
            sorted(
                {
                    record["d4_canonical_hash"]
                    for record in validate_boundary_definition_projection(projection)
                    if record["schema_version"] == 1 and record["d4_canonical_hash"] in vocabulary
                }
            )
        )

    inline = {path: schema1_vocabulary_hashes(projection) for path, projection in run_projections.items()}
    landscape_hashes = schema1_vocabulary_hashes(source_projections[3])
    resolved: Dict[str, Tuple[str, ...]] = {}
    for path in ( _STATIC_PATH, _PLAY_PATH, _SOLVE_PATH ):
        resolved[path] = ()
    for path in (_GENERATOR_V1_PATH, _GENERATOR_V2_PATH, _HELDOUT_PATH):
        resolved[path] = inline[path]
    resolved[_AUDIT_PATH] = resolved[_GENERATOR_V2_PATH]
    resolved[_CALIBRATION3_PATH] = resolved[_GENERATOR_V2_PATH]
    resolved[_CALIBRATION5_PATH] = resolved[_GENERATOR_V2_PATH]
    resolved[_BLIND_PATH] = resolved[_HELDOUT_PATH]
    resolved[_LANDSCAPE_RUN_PATH] = landscape_hashes
    resolved[_LANDSCAPE_STRESS_PATH] = resolved[_LANDSCAPE_RUN_PATH]
    resolved[_STALEMATE_RUN_PATH] = resolved[_LANDSCAPE_RUN_PATH]
    resolved[_STALEMATE_STRESS_PATH] = resolved[_LANDSCAPE_RUN_PATH]
    resolved[_CAPTURE_RUN_PATH] = resolved[_LANDSCAPE_RUN_PATH]
    resolved[_CAPTURE_STRESS_PATH] = resolved[_LANDSCAPE_RUN_PATH]
    if set(resolved) != set(_FROZEN_COVERAGE_TYPES):
        raise AssertionError("closed-world coverage adapter is incomplete")
    for path in resolved:
        extra = set(inline[path]) - set(resolved[path])
        if extra:
            raise ValueError(
                "coverage run embeds an in-vocabulary definition outside its resolved source set: {}".format(path)
            )
    registry_by_path = {entry["path"]: entry for entry in entries}
    dependency_artifacts = sorted(
        (
            dict(_STATIC_CORPUS_DEPENDENCY),
            dict(_LANDSCAPE_MANIFEST_DEPENDENCY),
            dict(_STALEMATE_MANIFEST_DEPENDENCY),
            dict(_CAPTURE_MANIFEST_DEPENDENCY),
        ),
        key=lambda item: item["path"],
    )
    run_artifacts = [
        {
            "path": entry["path"],
            "sha256": entry["sha256"],
            "identity_kind": "run_id",
            "identity": entry["path"].split("/")[-2],
        }
        for entry in entries
    ]
    known_artifacts = sorted(
        dependency_artifacts + run_artifacts, key=lambda item: item["path"]
    )
    direct_graph: Dict[str, Sequence[Mapping[str, Any]]] = {
        artifact["path"]: () for artifact in known_artifacts
    }
    direct_graph[_STALEMATE_MANIFEST_DEPENDENCY["path"]] = (
        dict(_LANDSCAPE_MANIFEST_DEPENDENCY),
    )
    direct_graph[_CAPTURE_MANIFEST_DEPENDENCY["path"]] = (
        dict(_LANDSCAPE_MANIFEST_DEPENDENCY),
    )
    for path in sorted(raw_by_path):
        direct = _expected_direct_dependencies(path, registry_by_path)
        _validate_run_dependency_configuration(path, raw_by_path[path], direct)
        direct_graph[path] = direct
    dependency_closures = resolve_boundary_dependency_closure(
        direct_graph, known_artifacts
    )
    resolution_records = {
        path: {
            "projection_kind": _EXPECTED_PROJECTION_KINDS[path],
            "direct_dependencies": list(direct_graph[path]),
            "dependencies": dependency_closures[path],
            "projected_d4_hashes": list(resolved[path]),
        }
        for path in sorted(resolved)
    }
    return build_boundary_projection_bundle(
        source_projections,
        entries,
        run_projections,
        resolution_records,
        dependency_artifacts,
    )


def validate_boundary_coverage_projection(
    value: Any,
    registry_entries: Sequence[Mapping[str, Any]] | None = None,
    run_projections: Mapping[str, Mapping[str, Any]] | None = None,
    resolution_records: Mapping[str, Mapping[str, Any]] | None = None,
    dependency_artifacts: Sequence[Mapping[str, Any]] | None = None,
) -> Tuple[Dict[str, Any], ...]:
    """Validate a coverage witness, optionally reconstructing it from projections."""

    top = _exact_keys(
        value,
        (
            "coverage_version",
            "cutoff_commit",
            "registry_count",
            "registry_root",
            "dependency_artifacts",
            "definition_occurrence_count",
            "schema1_occurrence_count",
            "covered_vocabulary_d4_count",
            "covered_vocabulary_d4_hashes",
            "covered_vocabulary_d4_root",
            "records",
            "coverage_root",
        ),
        "coverage projection",
    )
    _require_int(top["coverage_version"], 1, "coverage version")
    if top["cutoff_commit"] != CAPTURE_BOUNDARY_CUTOFF_COMMIT:
        raise ValueError("coverage cutoff commit mismatch")
    _require_int(top["registry_count"], CAPTURE_BOUNDARY_RUN_REGISTRY_COUNT, "coverage registry count")
    if _require_sha256(top["registry_root"], "coverage registry root") != CAPTURE_BOUNDARY_RUN_REGISTRY_ROOT:
        raise ValueError("coverage registry root mismatch")
    artifacts = _validated_dependencies(
        top["dependency_artifacts"], "coverage dependency artifacts"
    )
    expected_artifacts = tuple(
        sorted(
            (
                dict(_STATIC_CORPUS_DEPENDENCY),
                dict(_LANDSCAPE_MANIFEST_DEPENDENCY),
                dict(_STALEMATE_MANIFEST_DEPENDENCY),
                dict(_CAPTURE_MANIFEST_DEPENDENCY),
            ),
            key=lambda item: item["path"],
        )
    )
    if _canonical_bytes(artifacts) != _canonical_bytes(expected_artifacts):
        raise ValueError("coverage dependency artifact identities mismatch")
    _require_int(
        top["definition_occurrence_count"],
        CAPTURE_BOUNDARY_COVERAGE_OCCURRENCE_COUNT,
        "coverage definition occurrence count",
    )
    _require_int(
        top["schema1_occurrence_count"],
        CAPTURE_BOUNDARY_COVERAGE_SCHEMA1_OCCURRENCE_COUNT,
        "coverage schema-v1 occurrence count",
    )
    hashes = _require_sorted_hashes(top["covered_vocabulary_d4_hashes"], "covered vocabulary hashes")
    _require_int(top["covered_vocabulary_d4_count"], len(hashes), "covered vocabulary count")
    if len(hashes) != CAPTURE_BOUNDARY_COVERED_D4_COUNT:
        raise ValueError("covered vocabulary census mismatch")
    if (
        _require_sha256(top["covered_vocabulary_d4_root"], "covered vocabulary root")
        != _domain_digest(_COVERED_D4_DOMAIN, list(hashes))
        or top["covered_vocabulary_d4_root"] != CAPTURE_BOUNDARY_COVERED_D4_ROOT
    ):
        raise ValueError("covered vocabulary root mismatch")
    if not isinstance(top["records"], list) or len(top["records"]) != CAPTURE_BOUNDARY_RUN_REGISTRY_COUNT:
        raise ValueError("coverage records census mismatch")
    records = []
    paths = []
    union: Set[str] = set()
    occurrence_sum = 0
    schema1_sum = 0
    for raw_record in top["records"]:
        record = _exact_keys(
            raw_record,
            (
                "path",
                "sha256",
                "projection_kind",
                "direct_dependencies",
                "dependencies",
                "definition_projection_root",
                "definition_occurrence_count",
                "schema1_occurrence_count",
                "projected_d4_count",
                "projected_d4_hashes",
                "projected_d4_root",
            ),
            "coverage record",
        )
        if not isinstance(record["path"], str):
            raise ValueError("coverage path must be a string")
        paths.append(record["path"])
        _require_sha256(record["sha256"], "coverage source SHA")
        if not isinstance(record["projection_kind"], str) or not record["projection_kind"]:
            raise ValueError("coverage projection kind must be a nonempty string")
        _validated_dependencies(record["direct_dependencies"], "coverage direct dependencies")
        _validated_dependencies(record["dependencies"], "coverage dependencies")
        _require_sha256(record["definition_projection_root"], "coverage definition projection root")
        if type(record["definition_occurrence_count"]) is not int or record["definition_occurrence_count"] < 0:
            raise ValueError("coverage definition occurrence count must be nonnegative integer")
        if type(record["schema1_occurrence_count"]) is not int or not 0 <= record["schema1_occurrence_count"] <= record["definition_occurrence_count"]:
            raise ValueError("coverage schema-v1 occurrence count is invalid")
        projected = _require_sorted_hashes(record["projected_d4_hashes"], "run projected D4 hashes")
        _require_int(record["projected_d4_count"], len(projected), "run projected D4 count")
        if _require_sha256(record["projected_d4_root"], "run projected D4 root") != _domain_digest(
            _RUN_COVERAGE_DOMAIN, list(projected)
        ):
            raise ValueError("run projected D4 root mismatch")
        occurrence_sum += record["definition_occurrence_count"]
        schema1_sum += record["schema1_occurrence_count"]
        union.update(projected)
        records.append(_json_copy(record, "coverage record"))
    if paths != sorted(set(paths)):
        raise ValueError("coverage records must be unique and lexically ordered")
    if set(paths) != set(_FROZEN_COVERAGE_TYPES):
        raise ValueError("coverage records do not match the frozen closed-world registry")
    records_by_path = {record["path"]: record for record in records}
    registry_entries_from_records = [
        {"path": path, "sha256": records_by_path[path]["sha256"]}
        for path in sorted(records_by_path)
    ]
    if (
        _domain_digest(_RUN_REGISTRY_DOMAIN, registry_entries_from_records)
        != top["registry_root"]
    ):
        raise ValueError("coverage registry root does not match record paths and SHAs")
    registry_by_path = {entry["path"]: entry for entry in registry_entries_from_records}
    run_artifacts = [
        {
            "path": entry["path"],
            "sha256": entry["sha256"],
            "identity_kind": "run_id",
            "identity": entry["path"].split("/")[-2],
        }
        for entry in registry_entries_from_records
    ]
    known_artifacts = sorted(list(artifacts) + run_artifacts, key=lambda item: item["path"])
    direct_graph: Dict[str, Sequence[Mapping[str, Any]]] = {
        artifact["path"]: () for artifact in known_artifacts
    }
    direct_graph[_STALEMATE_MANIFEST_DEPENDENCY["path"]] = (
        dict(_LANDSCAPE_MANIFEST_DEPENDENCY),
    )
    direct_graph[_CAPTURE_MANIFEST_DEPENDENCY["path"]] = (
        dict(_LANDSCAPE_MANIFEST_DEPENDENCY),
    )
    for path, record in records_by_path.items():
        if record["projection_kind"] != _EXPECTED_PROJECTION_KINDS[path]:
            raise ValueError("coverage projection kind mismatch for {}".format(path))
        expected_direct = _expected_direct_dependencies(path, registry_by_path)
        if _canonical_bytes(record["direct_dependencies"]) != _canonical_bytes(expected_direct):
            raise ValueError("coverage direct dependency list mismatch for {}".format(path))
        direct_graph[path] = expected_direct
    closures = resolve_boundary_dependency_closure(direct_graph, known_artifacts)
    for path, record in records_by_path.items():
        if _canonical_bytes(record["dependencies"]) != _canonical_bytes(closures[path]):
            raise ValueError("coverage transitive dependency closure mismatch for {}".format(path))
    empty_paths = (_STATIC_PATH, _PLAY_PATH, _SOLVE_PATH)
    if any(records_by_path[path]["projected_d4_hashes"] for path in empty_paths):
        raise ValueError("outside-vocabulary fixtures must project no D4 orbit")
    inherited_targets = {
        _AUDIT_PATH: _GENERATOR_V2_PATH,
        _CALIBRATION3_PATH: _GENERATOR_V2_PATH,
        _CALIBRATION5_PATH: _GENERATOR_V2_PATH,
        _BLIND_PATH: _HELDOUT_PATH,
        _LANDSCAPE_STRESS_PATH: _LANDSCAPE_RUN_PATH,
        _STALEMATE_RUN_PATH: _LANDSCAPE_RUN_PATH,
        _STALEMATE_STRESS_PATH: _LANDSCAPE_RUN_PATH,
        _CAPTURE_RUN_PATH: _LANDSCAPE_RUN_PATH,
        _CAPTURE_STRESS_PATH: _LANDSCAPE_RUN_PATH,
    }
    for path, target in inherited_targets.items():
        if records_by_path[path]["projected_d4_hashes"] != records_by_path[target]["projected_d4_hashes"]:
            raise ValueError("reference-only coverage projection mismatch for {}".format(path))
    if occurrence_sum != top["definition_occurrence_count"] or schema1_sum != top["schema1_occurrence_count"]:
        raise ValueError("coverage per-run occurrence totals mismatch")
    if sorted(union) != list(hashes):
        raise ValueError("coverage per-run union mismatch")
    unsigned = dict(top)
    coverage_root = unsigned.pop("coverage_root")
    observed_coverage_root = _domain_digest(_COVERAGE_DOMAIN, unsigned)
    if _require_sha256(coverage_root, "coverage root") != observed_coverage_root:
        raise ValueError("coverage root mismatch")
    if CAPTURE_BOUNDARY_COVERAGE_ROOT and coverage_root != CAPTURE_BOUNDARY_COVERAGE_ROOT:
        raise ValueError("coverage root differs from the frozen production root")
    if (registry_entries is None) != (run_projections is None):
        raise ValueError("coverage reconstruction requires registry entries and run projections together")
    if registry_entries is not None and run_projections is not None:
        if resolution_records is None:
            resolution_records = {
                record["path"]: {
                    "projection_kind": record["projection_kind"],
                    "direct_dependencies": record["direct_dependencies"],
                    "dependencies": record["dependencies"],
                    "projected_d4_hashes": record["projected_d4_hashes"],
                }
                for record in records
            }
        if dependency_artifacts is None:
            dependency_artifacts = list(artifacts)
        vocabulary = set(dict(_canonical_orbit_representatives()))
        for path, projection in run_projections.items():
            inline = {
                record["d4_canonical_hash"]
                for record in validate_boundary_definition_projection(projection)
                if record["schema_version"] == 1
                and record["d4_canonical_hash"] in vocabulary
            }
            resolved = set(records_by_path[path]["projected_d4_hashes"])
            if not inline <= resolved:
                raise ValueError("coverage reconstruction found an embedded orbit outside the resolved source set")
        expected = build_boundary_coverage_projection(
            registry_entries,
            run_projections,
            resolution_records,
            dependency_artifacts,
        )
        if _canonical_bytes(top) != _canonical_bytes(expected):
            raise ValueError("coverage projection does not match public reconstruction")
    return tuple(records)


def _projection_identities(projection: Mapping[str, Any]) -> Tuple[Tuple[str, ...], Tuple[str, ...], Tuple[str, ...]]:
    records = validate_boundary_definition_projection(projection)
    definition_hashes = tuple(sorted({record["definition_hash"] for record in records}))
    d4_hashes = tuple(sorted({record["d4_canonical_hash"] for record in records}))
    board3_d4_hashes = tuple(
        sorted({record["d4_canonical_hash"] for record in records if record["board_size"] == 3})
    )
    return definition_hashes, d4_hashes, board3_d4_hashes


def _construct_boundary_exclusion_ledger(
    prior_source_projections: Sequence[Mapping[str, Any]],
    landscape_projection: Mapping[str, Any],
    coverage_projection: Mapping[str, Any],
) -> Dict[str, Any]:
    if not isinstance(prior_source_projections, (list, tuple)) or len(prior_source_projections) != 3:
        raise ValueError("exclusion ledger requires exactly three prior-run projections")
    validate_boundary_coverage_projection(coverage_projection)
    vocabulary = set(dict(_canonical_orbit_representatives()))
    source_records = []
    all_prior_definitions: Set[str] = set()
    all_prior_d4: Set[str] = set()
    all_prior_board3_d4: Set[str] = set()
    prior_occurrences = 0
    for (path, sha256), projection in zip(CAPTURE_BOUNDARY_PRIOR_SOURCES, prior_source_projections):
        records = validate_boundary_definition_projection(projection)
        definition_hashes, d4_hashes, board3_d4_hashes = _projection_identities(projection)
        prior_occurrences += len(records)
        all_prior_definitions.update(definition_hashes)
        all_prior_d4.update(d4_hashes)
        all_prior_board3_d4.update(board3_d4_hashes)
        vocabulary_hashes = tuple(sorted(set(d4_hashes) & vocabulary))
        source_records.append(
            {
                "source_kind": "PINNED_RUN",
                "path": path,
                "sha256": sha256,
                "definition_projection_root": projection["projection_root"],
                "definition_occurrence_count": len(records),
                "unique_definition_count": len(definition_hashes),
                "unique_definition_hashes": list(definition_hashes),
                "unique_d4_count": len(d4_hashes),
                "unique_d4_hashes": list(d4_hashes),
                "vocabulary_d4_count": len(vocabulary_hashes),
                "vocabulary_d4_hashes": list(vocabulary_hashes),
            }
        )
    landscape_records = validate_boundary_definition_projection(landscape_projection)
    landscape_definitions, landscape_d4, _ = _projection_identities(landscape_projection)
    landscape_vocabulary = tuple(sorted(set(landscape_d4) & vocabulary))
    source_records.append(
        {
            "source_kind": "LANDSCAPE_MANIFEST",
            "path": CAPTURE_BOUNDARY_LANDSCAPE_SOURCE[0],
            "sha256": CAPTURE_BOUNDARY_LANDSCAPE_SOURCE[1],
            "raw_evidence_sha256": CAPTURE_BOUNDARY_LANDSCAPE_RAW_SHA256,
            "definition_projection_root": landscape_projection["projection_root"],
            "definition_occurrence_count": len(landscape_records),
            "unique_definition_count": len(landscape_definitions),
            "unique_definition_hashes": list(landscape_definitions),
            "unique_d4_count": len(landscape_d4),
            "unique_d4_hashes": list(landscape_d4),
            "vocabulary_d4_count": len(landscape_vocabulary),
            "vocabulary_d4_hashes": list(landscape_vocabulary),
        }
    )
    if prior_occurrences != CAPTURE_BOUNDARY_PRIOR_DEFINITION_OCCURRENCE_COUNT:
        raise ValueError("prior-run definition occurrence census mismatch")
    if len(all_prior_definitions) != CAPTURE_BOUNDARY_PRIOR_UNIQUE_DEFINITION_COUNT:
        raise ValueError("prior-run unique definition census mismatch")
    if len(all_prior_d4) != CAPTURE_BOUNDARY_PRIOR_UNIQUE_D4_COUNT:
        raise ValueError("prior-run unique D4 census mismatch")
    if len(all_prior_board3_d4) != CAPTURE_BOUNDARY_PRIOR_BOARD3_D4_COUNT:
        raise ValueError("prior-run board-size-three D4 census mismatch")
    if len(set(all_prior_d4) & vocabulary) != CAPTURE_BOUNDARY_PRIOR_MATCHED_D4_COUNT:
        raise ValueError("prior-run vocabulary intersection census mismatch")
    if len(landscape_d4) != CAPTURE_BOUNDARY_LANDSCAPE_D4_COUNT or set(landscape_d4) != set(landscape_vocabulary):
        raise ValueError("landscape D4 census or vocabulary membership mismatch")
    if set(all_prior_d4) & set(landscape_d4):
        raise ValueError("prior-run and landscape D4 exclusions must be disjoint")
    declared = sorted(set(all_prior_d4) | set(landscape_d4))
    matched = sorted(set(declared) & vocabulary)
    coverage_hashes = coverage_projection["covered_vocabulary_d4_hashes"]
    if matched != coverage_hashes:
        raise ValueError("evaluated coverage and exclusion intersection differ")
    if len(declared) != CAPTURE_BOUNDARY_DECLARED_EXCLUSION_COUNT or len(matched) != CAPTURE_BOUNDARY_COVERED_D4_COUNT:
        raise ValueError("exclusion union census mismatch")
    ledger = {
        "ledger_version": 1,
        "cutoff_commit": CAPTURE_BOUNDARY_CUTOFF_COMMIT,
        "sources": source_records,
        "census": {
            "prior_definition_occurrences": prior_occurrences,
            "prior_unique_definition_hashes": len(all_prior_definitions),
            "prior_unique_d4_hashes": len(all_prior_d4),
            "prior_board3_d4_hashes": len(all_prior_board3_d4),
            "prior_vocabulary_d4_hashes": len(set(all_prior_d4) & vocabulary),
            "landscape_d4_hashes": len(landscape_d4),
            "declared_exclusion_d4_hashes": len(declared),
            "vocabulary_intersection_d4_hashes": len(matched),
        },
        "declared_exclusion_d4_hashes": declared,
        "declared_exclusion_root": _domain_digest(_DECLARED_EXCLUSION_DOMAIN, declared),
        "vocabulary_intersection_d4_hashes": matched,
        "vocabulary_intersection_root": _domain_digest(_MATCHED_EXCLUSION_DOMAIN, matched),
        "evaluated_coverage": {
            "registry_count": coverage_projection["registry_count"],
            "registry_root": coverage_projection["registry_root"],
            "covered_vocabulary_d4_count": coverage_projection["covered_vocabulary_d4_count"],
            "covered_vocabulary_d4_root": coverage_projection["covered_vocabulary_d4_root"],
            "coverage_root": coverage_projection["coverage_root"],
        },
    }
    ledger["ledger_root"] = _domain_digest(_LEDGER_DOMAIN, ledger)
    return ledger


def build_boundary_exclusion_ledger(
    prior_source_projections: Sequence[Mapping[str, Any]],
    landscape_projection: Mapping[str, Any],
    coverage_projection: Mapping[str, Any],
) -> Dict[str, Any]:
    """Build the exact four-source, cutoff-closed evaluated-orbit ledger."""

    ledger = _construct_boundary_exclusion_ledger(
        prior_source_projections, landscape_projection, coverage_projection
    )
    validate_boundary_exclusion_ledger(ledger)
    return ledger


def validate_boundary_exclusion_ledger(
    value: Any,
    prior_source_projections: Sequence[Mapping[str, Any]] | None = None,
    landscape_projection: Mapping[str, Any] | None = None,
    coverage_projection: Mapping[str, Any] | None = None,
) -> Tuple[str, ...]:
    """Validate the ledger, optionally reconstructing all four source projections."""

    top = _exact_keys(
        value,
        (
            "ledger_version",
            "cutoff_commit",
            "sources",
            "census",
            "declared_exclusion_d4_hashes",
            "declared_exclusion_root",
            "vocabulary_intersection_d4_hashes",
            "vocabulary_intersection_root",
            "evaluated_coverage",
            "ledger_root",
        ),
        "boundary exclusion ledger",
    )
    _require_int(top["ledger_version"], 1, "exclusion ledger version")
    if top["cutoff_commit"] != CAPTURE_BOUNDARY_CUTOFF_COMMIT:
        raise ValueError("exclusion ledger cutoff mismatch")
    if not isinstance(top["sources"], list) or len(top["sources"]) != 4:
        raise ValueError("exclusion ledger must contain four sources")
    # The source records are large identity lists.  Requiring canonical rebuilding
    # when projections are supplied catches every field; the standalone path still
    # validates all roots, cardinalities, and pinned byte identities.
    expected_identities = list(CAPTURE_BOUNDARY_PRIOR_SOURCES) + [CAPTURE_BOUNDARY_LANDSCAPE_SOURCE]
    for index, (record, (path, sha256)) in enumerate(zip(top["sources"], expected_identities)):
        if not isinstance(record, Mapping) or record.get("path") != path or record.get("sha256") != sha256:
            raise ValueError("exclusion source identity mismatch at index {}".format(index))
        _require_sha256(record.get("definition_projection_root"), "source projection root")
        unique_definitions = _require_sorted_hashes(record.get("unique_definition_hashes"), "source definition hashes")
        unique_d4 = _require_sorted_hashes(record.get("unique_d4_hashes"), "source D4 hashes")
        vocabulary_d4 = _require_sorted_hashes(record.get("vocabulary_d4_hashes"), "source vocabulary hashes")
        if not set(vocabulary_d4) <= set(unique_d4):
            raise ValueError("source vocabulary hashes must be a subset of its D4 hashes")
        for field, count in (
            ("unique_definition_count", len(unique_definitions)),
            ("unique_d4_count", len(unique_d4)),
            ("vocabulary_d4_count", len(vocabulary_d4)),
        ):
            _require_int(record.get(field), count, "source " + field)
        if type(record.get("definition_occurrence_count")) is not int or record["definition_occurrence_count"] < len(unique_definitions):
            raise ValueError("source definition occurrence count is invalid")
        if index < 3:
            _exact_keys(
                record,
                (
                    "source_kind", "path", "sha256", "definition_projection_root",
                    "definition_occurrence_count", "unique_definition_count", "unique_definition_hashes",
                    "unique_d4_count", "unique_d4_hashes", "vocabulary_d4_count", "vocabulary_d4_hashes",
                ),
                "prior exclusion source",
            )
            if record["source_kind"] != "PINNED_RUN":
                raise ValueError("prior exclusion source kind mismatch")
        else:
            _exact_keys(
                record,
                (
                    "source_kind", "path", "sha256", "raw_evidence_sha256", "definition_projection_root",
                    "definition_occurrence_count", "unique_definition_count", "unique_definition_hashes",
                    "unique_d4_count", "unique_d4_hashes", "vocabulary_d4_count", "vocabulary_d4_hashes",
                ),
                "landscape exclusion source",
            )
            if record["source_kind"] != "LANDSCAPE_MANIFEST" or record["raw_evidence_sha256"] != CAPTURE_BOUNDARY_LANDSCAPE_RAW_SHA256:
                raise ValueError("landscape exclusion source kind or raw SHA mismatch")
    census = _exact_keys(
        top["census"],
        (
            "prior_definition_occurrences", "prior_unique_definition_hashes", "prior_unique_d4_hashes",
            "prior_board3_d4_hashes", "prior_vocabulary_d4_hashes", "landscape_d4_hashes",
            "declared_exclusion_d4_hashes", "vocabulary_intersection_d4_hashes",
        ),
        "exclusion census",
    )
    expected_census = {
        "prior_definition_occurrences": CAPTURE_BOUNDARY_PRIOR_DEFINITION_OCCURRENCE_COUNT,
        "prior_unique_definition_hashes": CAPTURE_BOUNDARY_PRIOR_UNIQUE_DEFINITION_COUNT,
        "prior_unique_d4_hashes": CAPTURE_BOUNDARY_PRIOR_UNIQUE_D4_COUNT,
        "prior_board3_d4_hashes": CAPTURE_BOUNDARY_PRIOR_BOARD3_D4_COUNT,
        "prior_vocabulary_d4_hashes": CAPTURE_BOUNDARY_PRIOR_MATCHED_D4_COUNT,
        "landscape_d4_hashes": CAPTURE_BOUNDARY_LANDSCAPE_D4_COUNT,
        "declared_exclusion_d4_hashes": CAPTURE_BOUNDARY_DECLARED_EXCLUSION_COUNT,
        "vocabulary_intersection_d4_hashes": CAPTURE_BOUNDARY_COVERED_D4_COUNT,
    }
    if _canonical_bytes(census) != _canonical_bytes(expected_census):
        raise ValueError("exclusion census mismatch")
    declared = _require_sorted_hashes(top["declared_exclusion_d4_hashes"], "declared exclusion hashes")
    matched = _require_sorted_hashes(top["vocabulary_intersection_d4_hashes"], "matched exclusion hashes")
    if len(declared) != CAPTURE_BOUNDARY_DECLARED_EXCLUSION_COUNT or len(matched) != CAPTURE_BOUNDARY_COVERED_D4_COUNT:
        raise ValueError("exclusion hash census mismatch")
    if not set(matched) <= set(declared):
        raise ValueError("matched exclusions must be a subset of declared exclusions")
    if _require_sha256(top["declared_exclusion_root"], "declared exclusion root") != _domain_digest(_DECLARED_EXCLUSION_DOMAIN, list(declared)):
        raise ValueError("declared exclusion root mismatch")
    if _require_sha256(top["vocabulary_intersection_root"], "matched exclusion root") != _domain_digest(_MATCHED_EXCLUSION_DOMAIN, list(matched)):
        raise ValueError("matched exclusion root mismatch")
    coverage = _exact_keys(
        top["evaluated_coverage"],
        (
            "registry_count",
            "registry_root",
            "covered_vocabulary_d4_count",
            "covered_vocabulary_d4_root",
            "coverage_root",
        ),
        "ledger coverage reference",
    )
    expected_coverage = {
        "registry_count": CAPTURE_BOUNDARY_RUN_REGISTRY_COUNT,
        "registry_root": CAPTURE_BOUNDARY_RUN_REGISTRY_ROOT,
        "covered_vocabulary_d4_count": CAPTURE_BOUNDARY_COVERED_D4_COUNT,
        "covered_vocabulary_d4_root": CAPTURE_BOUNDARY_COVERED_D4_ROOT,
        "coverage_root": (
            CAPTURE_BOUNDARY_COVERAGE_ROOT
            if CAPTURE_BOUNDARY_COVERAGE_ROOT
            else coverage["coverage_root"]
        ),
    }
    if _canonical_bytes(coverage) != _canonical_bytes(expected_coverage):
        raise ValueError("ledger coverage reference mismatch")
    unsigned = dict(top)
    ledger_root = unsigned.pop("ledger_root")
    if _require_sha256(ledger_root, "exclusion ledger root") != _domain_digest(_LEDGER_DOMAIN, unsigned):
        raise ValueError("exclusion ledger root mismatch")
    if CAPTURE_BOUNDARY_LEDGER_ROOT and ledger_root != CAPTURE_BOUNDARY_LEDGER_ROOT:
        raise ValueError("exclusion ledger root differs from the frozen production root")
    supplied = (prior_source_projections, landscape_projection, coverage_projection)
    if any(item is None for item in supplied) and not all(item is None for item in supplied):
        raise ValueError("ledger reconstruction requires all source and coverage projections")
    if all(item is not None for item in supplied):
        expected = _construct_boundary_exclusion_ledger(
            prior_source_projections,  # type: ignore[arg-type]
            landscape_projection,  # type: ignore[arg-type]
            coverage_projection,  # type: ignore[arg-type]
        )
        if _canonical_bytes(top) != _canonical_bytes(expected):
            raise ValueError("exclusion ledger does not match public reconstruction")
    return matched


def derive_capture_boundary_treatment(source_value: Any) -> GameDefinition:
    """Derive the schema-v3 treatment and prove the frozen two-field edit."""

    source = source_value if isinstance(source_value, GameDefinition) else parse_definition(source_value)
    _validate_source_family(source)
    vector_count = len(source.role(Player.B).action.vectors)
    if vector_count not in (3, 4):
        raise ValueError("capture-boundary sources require exactly three or four B vectors")
    return _capture_treatment(source)


def validate_capture_boundary_pair(source_value: Any, treatment_value: Any) -> None:
    """Validate source family, vector boundary, and exact one-variable treatment."""

    source = source_value if isinstance(source_value, GameDefinition) else parse_definition(source_value)
    treatment = treatment_value if isinstance(treatment_value, GameDefinition) else parse_definition(treatment_value)
    _validate_source_family(source)
    if len(source.role(Player.B).action.vectors) not in (3, 4):
        raise ValueError("capture-boundary pair requires three or four B vectors")
    _validate_treatment_pair(source, treatment)
    if _canonical_bytes(treatment.to_dict()) != _canonical_bytes(derive_capture_boundary_treatment(source).to_dict()):
        raise ValueError("capture-boundary treatment derivation mismatch")


def capture_boundary_state_upper_bound(definition_value: Any) -> int:
    """Return the shared 43,776-state structural bound for source or treatment."""

    definition = definition_value if isinstance(definition_value, GameDefinition) else parse_definition(definition_value)
    if definition.schema_version == 1:
        _validate_source_family(definition)
        if len(definition.role(Player.B).action.vectors) not in (3, 4):
            raise ValueError("capture-boundary state proof requires three or four B vectors")
    elif definition.schema_version == 3:
        mapping = definition.to_dict()
        mapping["schema_version"] = 1
        mapping["roles"]["B"]["action"]["kind"] = "MOVE"
        validate_capture_boundary_pair(mapping, definition)
    else:
        raise ValueError("capture-boundary state proof applies only to schema v1 or v3")
    board_arrangements = definition.board_size ** 2 * (2 ** (definition.board_size ** 2 - 1))
    bound = (definition.max_plies + 1) * board_arrangements
    if bound != CAPTURE_STATE_BOUND:
        raise AssertionError("capture-boundary state proof drifted")
    return bound


def capture_boundary_stratum(definition_value: Any) -> Dict[str, Any]:
    """Return the exact four-field Plan-0009 stratum for a source definition."""

    definition = definition_value if isinstance(definition_value, GameDefinition) else parse_definition(definition_value)
    _validate_source_family(definition)
    role_a = definition.role(Player.A)
    role_b = definition.role(Player.B)
    vector_count = len(role_b.action.vectors)
    if vector_count not in (3, 4):
        raise ValueError("capture-boundary strata require vector count three or four")
    assert role_b.goal.edge is not None
    row, column = definition.initial_pieces[0].position
    return {
        "first_player": definition.first_player.value,
        "goal_axis_relation": "ALIGNED" if role_b.goal.edge in role_a.goal.edges else "ORTHOGONAL",
        "runner_start_class": (
            "CORNER"
            if row in (0, definition.board_size - 1) and column in (0, definition.board_size - 1)
            else "EDGE_MIDPOINT"
        ),
        "vector_count": vector_count,
    }


def _stratum_id(stratum: Mapping[str, Any]) -> str:
    _exact_keys(stratum, ("first_player", "goal_axis_relation", "runner_start_class", "vector_count"), "boundary stratum")
    if stratum["first_player"] not in ("A", "B"):
        raise ValueError("boundary stratum first player mismatch")
    if stratum["goal_axis_relation"] not in ("ALIGNED", "ORTHOGONAL"):
        raise ValueError("boundary stratum goal-axis relation mismatch")
    if stratum["runner_start_class"] not in ("CORNER", "EDGE_MIDPOINT"):
        raise ValueError("boundary stratum runner start class mismatch")
    if type(stratum["vector_count"]) is not int or stratum["vector_count"] not in (3, 4):
        raise ValueError("boundary stratum vector count mismatch")
    return "f{}-{}-{}-p18-v{}".format(
        stratum["first_player"],
        stratum["goal_axis_relation"].lower(),
        stratum["runner_start_class"].lower(),
        stratum["vector_count"],
    )


def _selection_score(source_d4_hash: str) -> str:
    return hashlib.sha256((CAPTURE_BOUNDARY_SELECTION_PREFIX + source_d4_hash).encode("ascii")).hexdigest()


def _passes_boundary_gates(definition: GameDefinition) -> bool:
    return (
        analyze_definition(definition).passes
        and evaluate_asymmetry(definition).qualifies
        and not exceeds_limits(evaluate_simplicity(definition))
    )


@lru_cache(maxsize=8)
def _selection_snapshot(excluded_hashes: Tuple[str, ...]) -> Tuple[Any, ...]:
    excluded = set(excluded_hashes)
    relevant = []
    eligible_by_stratum: Dict[str, list[Tuple[str, str, GameDefinition, GameDefinition, Dict[str, Any]]]] = defaultdict(list)
    gate_disagreements = 0
    for orbit_hash, definition in _canonical_orbit_representatives():
        if orbit_hash in excluded or definition.schema_version != 1 or definition.board_size != 3 or definition.max_plies != 18:
            continue
        if len(definition.role(Player.B).action.vectors) not in (3, 4):
            continue
        try:
            _validate_source_family(definition)
        except ValueError:
            continue
        relevant.append(orbit_hash)
        treatment = derive_capture_boundary_treatment(definition)
        source_passes = _passes_boundary_gates(definition)
        treatment_passes = _passes_boundary_gates(treatment)
        if source_passes != treatment_passes:
            gate_disagreements += 1
        if not (source_passes and treatment_passes):
            continue
        stratum = capture_boundary_stratum(definition)
        stratum_id = _stratum_id(stratum)
        eligible_by_stratum[stratum_id].append(
            (_selection_score(orbit_hash), orbit_hash, definition, treatment, stratum)
        )
    for candidates in eligible_by_stratum.values():
        candidates.sort(key=lambda item: (item[0], item[1]))
    frozen = tuple(
        (stratum_id, tuple(candidates))
        for stratum_id, candidates in sorted(eligible_by_stratum.items())
    )
    return (tuple(sorted(relevant)), gate_disagreements, frozen)


def _pair_fingerprint(pair: Mapping[str, Any]) -> str:
    payload = dict(pair)
    payload.pop("pair_fingerprint", None)
    return _domain_digest(_PAIR_DOMAIN, payload)


def _validate_plan0008_freshness(manifest: Mapping[str, Any]) -> Tuple[Set[str], Set[str]]:
    pairs = validate_capture_paired_manifest(manifest)
    sources = {pair["source_d4_canonical_hash"] for pair in pairs}
    treatments = {pair["treatment_d4_canonical_hash"] for pair in pairs}
    if len(sources) != 128 or len(treatments) != 128:
        raise ValueError("Plan-0008 manifest D4 census mismatch")
    return sources, treatments


def _construct_capture_boundary_manifest(
    exclusion_ledger: Mapping[str, Any],
    coverage_projection: Mapping[str, Any],
    plan0008_manifest: Mapping[str, Any],
    provenance: Any,
    plan0008_manifest_sha256: str,
) -> Dict[str, Any]:
    excluded = validate_boundary_exclusion_ledger(exclusion_ledger)
    validate_boundary_coverage_projection(coverage_projection)
    if list(excluded) != coverage_projection["covered_vocabulary_d4_hashes"]:
        raise ValueError("manifest exclusion and coverage projections differ")
    if plan0008_manifest_sha256 != CAPTURE_BOUNDARY_PLAN0008_CHAIN["manifest_sha256"]:
        raise ValueError("Plan-0008 manifest byte SHA mismatch")
    plan8_sources, plan8_treatments = _validate_plan0008_freshness(plan0008_manifest)
    provenance_copy = _json_copy(provenance, "capture-boundary provenance")
    if _contains_forbidden_selection_key(provenance_copy):
        raise ValueError("capture-boundary provenance must be recursively outcome- and timing-free")
    relevant, gate_disagreements, frozen_pools = _selection_snapshot(tuple(excluded))
    if len(relevant) != CAPTURE_BOUNDARY_UNUSED_RELEVANT_ORBIT_COUNT:
        raise ValueError("unused relevant-orbit census mismatch")
    if gate_disagreements != 0:
        raise ValueError("source/treatment static-gate disagreement")
    if len(frozen_pools) != CAPTURE_BOUNDARY_STRATUM_COUNT:
        raise ValueError("eligible stratum census mismatch")
    observed_counts = {stratum_id: len(candidates) for stratum_id, candidates in frozen_pools}
    if observed_counts != _EXPECTED_STRATUM_COUNTS:
        raise ValueError("eligible per-stratum census mismatch")
    if sum(observed_counts.values()) != CAPTURE_BOUNDARY_ELIGIBLE_ORBIT_COUNT:
        raise ValueError("eligible-orbit census mismatch")

    pool_payload = []
    eligible_pools = []
    pairs = []
    selected_source_hashes = []
    seen_treatment_hashes: Set[str] = set()
    prior_plan8_hashes = plan8_sources | plan8_treatments
    for stratum_id, candidates in frozen_pools:
        stratum = _json_copy(candidates[0][4], "eligible-pool stratum")
        lexical_hashes = sorted(item[1] for item in candidates)
        pool_entry = {
            "stratum": _json_copy(stratum, "pool-root stratum"),
            "ordered_source_d4_hashes": lexical_hashes,
        }
        pool_payload.append(pool_entry)
        selected_pair_ids = []
        for rank, (score, source_d4, source, treatment, candidate_stratum) in enumerate(
            candidates[:CAPTURE_BOUNDARY_QUOTA_PER_STRATUM]
        ):
            if source_d4 in prior_plan8_hashes:
                raise ValueError("selected source reuses a Plan-0008 source/treatment orbit")
            treatment_d4 = d4_canonical_hash(treatment)
            if treatment_d4 in prior_plan8_hashes:
                raise ValueError("derived treatment reuses a Plan-0008 source/treatment orbit")
            if treatment_d4 in seen_treatment_hashes:
                raise ValueError("derived treatments must occupy unique D4 orbits")
            if mechanical_json(source) != canonicalize_d4(source).mechanical_json:
                raise ValueError("selected source is not in canonical mechanical orientation")
            if mechanical_json(treatment) != canonicalize_d4(treatment).mechanical_json:
                raise ValueError("derived treatment is not in canonical mechanical orientation")
            validate_capture_boundary_pair(source, treatment)
            capture_boundary_state_upper_bound(source)
            capture_boundary_state_upper_bound(treatment)
            index = len(pairs) + 1
            pair_id = "capture-boundary-v1-pair-{:03d}".format(index)
            pair = {
                "pair_id": pair_id,
                "source_case_id": "capture-boundary-v1-source-{:03d}".format(index),
                "stratum_id": stratum_id,
                "stratum": _json_copy(candidate_stratum, "pair stratum"),
                "vector_count": candidate_stratum["vector_count"],
                "selection_rank": rank,
                "selection_score": score,
                "source_definition_hash": definition_hash(source),
                "source_d4_canonical_hash": source_d4,
                "source_definition": source.to_dict(),
                "treatment_definition_hash": definition_hash(treatment),
                "treatment_d4_canonical_hash": treatment_d4,
                "treatment_definition": treatment.to_dict(),
            }
            pair["pair_fingerprint"] = _pair_fingerprint(pair)
            pairs.append(pair)
            selected_pair_ids.append(pair_id)
            selected_source_hashes.append(source_d4)
            seen_treatment_hashes.add(treatment_d4)
        eligible_pools.append(
            {
                "stratum_id": stratum_id,
                "stratum": _json_copy(stratum, "eligible-pool record stratum"),
                "eligible_count": len(candidates),
                "ordered_source_d4_root": _domain_digest(_ELIGIBLE_POOL_DOMAIN, lexical_hashes),
                "quota": CAPTURE_BOUNDARY_QUOTA_PER_STRATUM,
                "selected_pair_ids": selected_pair_ids,
            }
        )
    pool_root = _domain_digest(_ELIGIBLE_POOLS_DOMAIN, pool_payload)
    selection_fingerprint = _domain_digest(_SELECTED_SOURCES_DOMAIN, selected_source_hashes)
    if pool_root != CAPTURE_BOUNDARY_ELIGIBLE_POOL_ROOT:
        raise ValueError("frozen eligible-pool root mismatch")
    if selection_fingerprint != CAPTURE_BOUNDARY_SELECTION_FINGERPRINT:
        raise ValueError("frozen source-selection fingerprint mismatch")
    manifest = {
        "manifest_version": CAPTURE_BOUNDARY_MANIFEST_VERSION,
        "manifest_id": CAPTURE_BOUNDARY_MANIFEST_ID,
        "protocol_id": CAPTURE_BOUNDARY_MANIFEST_PROTOCOL_ID,
        "status": "FROZEN",
        "source": {
            "cutoff_commit": CAPTURE_BOUNDARY_CUTOFF_COMMIT,
            "exclusion_ledger_root": exclusion_ledger["ledger_root"],
            "declared_exclusion_root": exclusion_ledger["declared_exclusion_root"],
            "vocabulary_intersection_root": exclusion_ledger["vocabulary_intersection_root"],
            "evaluated_run_registry_root": coverage_projection["registry_root"],
            "evaluated_vocabulary_root": coverage_projection["covered_vocabulary_d4_root"],
            "evaluated_coverage_root": coverage_projection["coverage_root"],
            "prior_sources": [
                {"path": path, "sha256": sha256} for path, sha256 in CAPTURE_BOUNDARY_PRIOR_SOURCES
            ],
            "landscape_source": {
                "path": CAPTURE_BOUNDARY_LANDSCAPE_SOURCE[0],
                "sha256": CAPTURE_BOUNDARY_LANDSCAPE_SOURCE[1],
                "raw_evidence_sha256": CAPTURE_BOUNDARY_LANDSCAPE_RAW_SHA256,
            },
            "plan0008_manifest_chain": dict(CAPTURE_BOUNDARY_PLAN0008_CHAIN),
        },
        "selection_protocol": {
            "membership": "first four by selection score then source D4 hash within each ordered stratum",
            "selection_score_prefix": CAPTURE_BOUNDARY_SELECTION_PREFIX,
            "eligible_pool_root": pool_root,
            "selection_fingerprint": selection_fingerprint,
            "treatment_change": "schema_version 1->3 and roles.B.action.kind MOVE->MOVE_CAPTURE only",
            "prior_capture_outcomes_informed_protocol_design": True,
            "case_membership_outcome_fields_consulted": False,
            "capture_boundary_treatment_outcomes_computed": False,
        },
        "state_bound": {
            "board_arrangements_per_ply": 2_304,
            "ply_layers": 19,
            "maximum_states": CAPTURE_STATE_BOUND,
            "exact_execution_cap": CAPTURE_EXACT_MAX_STATES,
        },
        "census": {
            "raw_definition_count": RAW_DEFINITION_COUNT,
            "raw_d4_orbit_count": RAW_D4_ORBIT_COUNT,
            "declared_exclusion_d4_count": CAPTURE_BOUNDARY_DECLARED_EXCLUSION_COUNT,
            "matched_exclusion_d4_count": CAPTURE_BOUNDARY_COVERED_D4_COUNT,
            "unused_relevant_d4_count": len(relevant),
            "paired_analysis_valid_d4_count": sum(observed_counts.values()),
            "source_treatment_gate_disagreement_count": gate_disagreements,
            "stratum_count": len(frozen_pools),
            "minimum_eligible_stratum_count": min(observed_counts.values()),
            "quota_per_stratum": CAPTURE_BOUNDARY_QUOTA_PER_STRATUM,
            "pair_count": len(pairs),
        },
        "eligible_pools": eligible_pools,
        "provenance": provenance_copy,
        "pairs": pairs,
    }
    if _contains_forbidden_selection_key(manifest):
        raise AssertionError("capture-boundary manifest accidentally contains an outcome/timing field")
    return _json_copy(manifest, "capture-boundary manifest")


def build_capture_boundary_manifest(
    exclusion_ledger: Mapping[str, Any],
    coverage_projection: Mapping[str, Any],
    plan0008_manifest: Mapping[str, Any],
    provenance: Any,
    *,
    plan0008_manifest_sha256: str = CAPTURE_BOUNDARY_PLAN0008_CHAIN["manifest_sha256"],
) -> Dict[str, Any]:
    """Build the deterministic frozen 64-pair outcome-free manifest."""

    manifest = _construct_capture_boundary_manifest(
        exclusion_ledger,
        coverage_projection,
        plan0008_manifest,
        provenance,
        plan0008_manifest_sha256,
    )
    validate_capture_boundary_manifest(
        manifest,
        exclusion_ledger,
        coverage_projection,
        plan0008_manifest,
        plan0008_manifest_sha256=plan0008_manifest_sha256,
    )
    return manifest


def validate_capture_boundary_manifest(
    manifest: Any,
    exclusion_ledger: Mapping[str, Any],
    coverage_projection: Mapping[str, Any],
    plan0008_manifest: Mapping[str, Any],
    *,
    plan0008_manifest_sha256: str = CAPTURE_BOUNDARY_PLAN0008_CHAIN["manifest_sha256"],
) -> Tuple[Dict[str, Any], ...]:
    """Publicly reconstruct the full cohort and return detached ordered pairs."""

    top = _exact_keys(
        manifest,
        (
            "manifest_version", "manifest_id", "protocol_id", "status", "source",
            "selection_protocol", "state_bound", "census", "eligible_pools", "provenance", "pairs",
        ),
        "capture-boundary manifest",
    )
    _require_int(top["manifest_version"], CAPTURE_BOUNDARY_MANIFEST_VERSION, "manifest version")
    if top["manifest_id"] != CAPTURE_BOUNDARY_MANIFEST_ID or top["protocol_id"] != CAPTURE_BOUNDARY_MANIFEST_PROTOCOL_ID or top["status"] != "FROZEN":
        raise ValueError("capture-boundary manifest identity or status mismatch")
    if _contains_forbidden_selection_key(top):
        raise ValueError("capture-boundary manifest contains an outcome or timing field")
    expected = _construct_capture_boundary_manifest(
        exclusion_ledger,
        coverage_projection,
        plan0008_manifest,
        top["provenance"],
        plan0008_manifest_sha256,
    )
    if _canonical_bytes(top) != _canonical_bytes(expected):
        raise ValueError("capture-boundary manifest does not match public reconstruction")
    return tuple(_json_copy(pair, "capture-boundary pair") for pair in top["pairs"])


@lru_cache(maxsize=128)
def _validate_containment_pair_cached(
    source: GameDefinition, treatment: GameDefinition
) -> None:
    validate_capture_boundary_pair(source, treatment)


def validate_capture_boundary_move_containment(
    source_value: Any,
    treatment_value: Any,
    state: GameState,
) -> None:
    """Prove source B moves are contained and only opponent entries are added.

    This checks one arbitrary valid common board state.  Exhaustive callers can
    enumerate all 2,304 arrangements; no solver or play policy is involved.
    """

    source = source_value if isinstance(source_value, GameDefinition) else parse_definition(source_value)
    treatment = treatment_value if isinstance(treatment_value, GameDefinition) else parse_definition(treatment_value)
    _validate_containment_pair_cached(source, treatment)
    if not isinstance(state, GameState) or state.terminal or state.to_move is not Player.B:
        raise ValueError("move-containment state must be a nonterminal B-to-move GameState")
    if type(state.ply) is not int or not 0 <= state.ply < source.max_plies:
        raise ValueError("move-containment state ply is invalid")
    if any(not isinstance(piece, InitialPiece) for piece in state.pieces):
        raise ValueError("move-containment pieces must be InitialPiece values")
    positions = [piece.position for piece in state.pieces]
    if len(positions) != len(set(positions)) or any(
        not (0 <= row < source.board_size and 0 <= column < source.board_size)
        for row, column in positions
    ):
        raise ValueError("move-containment pieces must occupy unique in-bounds cells")
    runners = [piece for piece in state.pieces if piece.owner is Player.B and piece.piece == "runner"]
    if len(runners) != 1 or any(
        not (piece.owner is Player.A and piece.piece == "seed")
        for piece in state.pieces
        if piece not in runners
    ):
        raise ValueError("move-containment state requires one B runner and only A seeds")
    occupied = {piece.position: piece for piece in state.pieces}
    source_actions = legal_actions(source, state)
    treatment_actions = legal_actions(treatment, state)
    source_by_coordinates = {(action.from_position, action.to_position): action for action in source_actions}
    treatment_by_coordinates = {(action.from_position, action.to_position): action for action in treatment_actions}
    if not set(source_by_coordinates) <= set(treatment_by_coordinates):
        raise ValueError("capture treatment removed a source move")
    for coordinates, treatment_action in treatment_by_coordinates.items():
        destination = coordinates[1]
        occupant = occupied.get(destination)
        if coordinates not in source_by_coordinates:
            if occupant is None or occupant.owner is not Player.A:
                raise ValueError("capture treatment added a move not entering an A seed")
            continue
        if occupant is not None:
            raise ValueError("a common source/treatment move must enter an empty cell")
        source_action = source_by_coordinates[coordinates]
        if source_action.kind is not ActionKind.MOVE or treatment_action.kind is not ActionKind.MOVE_CAPTURE:
            raise ValueError("common action kinds do not match the intervention")
        if apply_action(source, state, source_action) != apply_action(treatment, state, treatment_action):
            raise ValueError("common empty-destination moves do not produce identical states")
