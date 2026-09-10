"""Pure outcome-free construction for the Plan-0011 4x4 calibration.

The module accepts only authenticated bytes and detached JSON projections.  It
does not read the filesystem, inspect Git, solve games, simulate play, or import
agent/evaluator modules.  Membership is reconstructed from the complete native
generator-v2 4x4/max-8 vocabulary, frozen definition gates, and a closed set of
historical artifact bytes.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from functools import lru_cache
from typing import Any, Dict, Iterable, Mapping, Sequence, Set, Tuple

from .analysis import analyze_definition
from .asymmetry import evaluate_asymmetry
from .dsl import (
    ActionKind,
    DefinitionError,
    Edge,
    GameDefinition,
    GoalKind,
    Player,
    definition_hash,
    parse_definition,
)
from .generator import enumerate_v2_four_by_four_max8
from .simplicity import evaluate_simplicity, exceeds_limits
from .symmetry import canonicalize_d4, d4_canonical_hash, mechanical_json


FOUR_BY_FOUR_CALIBRATION_MANIFEST_VERSION = 1
FOUR_BY_FOUR_CALIBRATION_MANIFEST_ID = (
    "four-by-four-calibration-v1-32-case-manifest"
)
FOUR_BY_FOUR_CALIBRATION_MANIFEST_PROTOCOL_ID = (
    "four-by-four-calibration-v1-manifest-freeze"
)
FOUR_BY_FOUR_HISTORY_PROJECTION_VERSION = 1
FOUR_BY_FOUR_RAW_DEFINITION_COUNT = 16_320
FOUR_BY_FOUR_RAW_D4_ORBIT_COUNT = 2_040
FOUR_BY_FOUR_GATE_VALID_D4_COUNT = 1_592
FOUR_BY_FOUR_HISTORICAL_NATIVE_D4_COUNT = 22
FOUR_BY_FOUR_HISTORICAL_GATE_VALID_D4_COUNT = 14
FOUR_BY_FOUR_HISTORICAL_GATE_INVALID_D4_COUNT = 8
FOUR_BY_FOUR_FRESH_GATE_VALID_D4_COUNT = 1_578
FOUR_BY_FOUR_STRATUM_COUNT = 32
FOUR_BY_FOUR_CASE_COUNT = 32
FOUR_BY_FOUR_QUOTA_PER_STRATUM = 1

FOUR_BY_FOUR_A_FIRST_STATE_BOUND = 62_096
FOUR_BY_FOUR_B_FIRST_STATE_BOUND = 40_272
FOUR_BY_FOUR_EXACT_MAX_STATES = 100_000
FOUR_BY_FOUR_FIXED_CORPUS_STATE_BOUND = 1_637_888

FOUR_BY_FOUR_LEDGER_PATH = (
    "experiments/corpora/two-runner-v1/exclusion-ledger.json"
)
FOUR_BY_FOUR_LEDGER_SHA256 = (
    "b38b2d1e2bd5b3faa0c5cdb86580e408547faa4bef819eeb9c3feb5143b440a0"
)
FOUR_BY_FOUR_LEDGER_BYTES = 131_707
FOUR_BY_FOUR_LEDGER_BUNDLE_ROOT = (
    "755b5a5d8ae35d8222873275e87860effbdf7ec2266de3799814d20385b12ca3"
)
FOUR_BY_FOUR_PLAN0010_MANIFEST_PATH = (
    "experiments/corpora/two-runner-v1/manifest.json"
)
FOUR_BY_FOUR_PLAN0010_MANIFEST_SHA256 = (
    "3b7757ade9bd745eb1aff838455927115005dd8efe4d96ebaef51af213d228b9"
)
FOUR_BY_FOUR_PLAN0010_MANIFEST_BYTES = 272_179

FOUR_BY_FOUR_LEDGER_SOURCE_COUNT = 21
FOUR_BY_FOUR_CLOSED_SOURCE_COUNT = 22
FOUR_BY_FOUR_HISTORICAL_DEFINITION_OCCURRENCE_COUNT = 2_243
FOUR_BY_FOUR_HISTORICAL_UNIQUE_DEFINITION_COUNT = 1_172
FOUR_BY_FOUR_HISTORICAL_UNIQUE_D4_COUNT = 1_168
FOUR_BY_FOUR_HISTORICAL_MAX8_UNIQUE_D4_COUNT = 31

# Reconstructed entirely from definition-only inputs before any selected exact
# outcome existed.  Production manifest construction remains separately gated on
# reviewed provenance.
FOUR_BY_FOUR_CLOSED_HISTORY_PROJECTION_ROOT = (
    "b576e88bee320df83d4e2aa73c981e5f2a20e8db8b2b88744b832a0e6f50f3ae"
)
FOUR_BY_FOUR_RAW_D4_ROOT = (
    "5c0c68af5838a37a25e0e398560211288d72a85567f260f7d8efaa8e4fce2757"
)
FOUR_BY_FOUR_GATE_VALID_D4_ROOT = (
    "d0e79b3c4b752cdf99fd29ee5554de0b42b36a0e2f8d94ee04a9441088369672"
)
FOUR_BY_FOUR_FRESH_GATE_VALID_D4_ROOT = (
    "cfa925c12b142c01804cea40ba126b5b004924a0f70600608bf0ef2c2a76c814"
)
FOUR_BY_FOUR_NATIVE_HISTORY_D4_ROOT = (
    "10120dc33cc46e94e2a0faee906ade7ae34a39e13579461bd91e8b3281a65151"
)
FOUR_BY_FOUR_GATE_VALID_HISTORY_D4_ROOT = (
    "66fb497235ce9661df1c9dbbb0de9831b14fd9e9ad2ac7412a42e78ba24aa29f"
)
FOUR_BY_FOUR_ELIGIBLE_POOL_ROOT = (
    "963ab02ee731c8f4d42574f92d98bd2f5772e1e380b2e4c5bff1b95adba44e99"
)
FOUR_BY_FOUR_SELECTION_FINGERPRINT = (
    "bcf9992cd2479536da193b7a206f5988e993f5eb700f1e421c7b453480bce834"
)

FOUR_BY_FOUR_MANIFEST_EXECUTABLE_FINGERPRINT_PATHS = (
    "src/parity_forge/__init__.py",
    "src/parity_forge/analysis.py",
    "src/parity_forge/asymmetry.py",
    "src/parity_forge/dsl.py",
    "src/parity_forge/engine.py",
    "src/parity_forge/four_by_four_calibration.py",
    "src/parity_forge/generator.py",
    "src/parity_forge/simplicity.py",
    "src/parity_forge/symmetry.py",
)

_EXPECTED_STRATUM_COUNTS = {
    "fA-aligned-corner-v1_3": 55,
    "fA-aligned-corner-v4": 60,
    "fA-aligned-corner-v5": 54,
    "fA-aligned-corner-v6_7": 36,
    "fA-aligned-edge_inner-v1_3": 45,
    "fA-aligned-edge_inner-v4": 57,
    "fA-aligned-edge_inner-v5": 53,
    "fA-aligned-edge_inner-v6_7": 35,
    "fA-orthogonal-corner-v1_3": 55,
    "fA-orthogonal-corner-v4": 61,
    "fA-orthogonal-corner-v5": 54,
    "fA-orthogonal-corner-v6_7": 35,
    "fA-orthogonal-edge_inner-v1_3": 45,
    "fA-orthogonal-edge_inner-v4": 56,
    "fA-orthogonal-edge_inner-v5": 53,
    "fA-orthogonal-edge_inner-v6_7": 35,
    "fB-aligned-corner-v1_3": 56,
    "fB-aligned-corner-v4": 60,
    "fB-aligned-corner-v5": 54,
    "fB-aligned-corner-v6_7": 36,
    "fB-aligned-edge_inner-v1_3": 45,
    "fB-aligned-edge_inner-v4": 57,
    "fB-aligned-edge_inner-v5": 53,
    "fB-aligned-edge_inner-v6_7": 35,
    "fB-orthogonal-corner-v1_3": 55,
    "fB-orthogonal-corner-v4": 61,
    "fB-orthogonal-corner-v5": 53,
    "fB-orthogonal-corner-v6_7": 35,
    "fB-orthogonal-edge_inner-v1_3": 45,
    "fB-orthogonal-edge_inner-v4": 57,
    "fB-orthogonal-edge_inner-v5": 52,
    "fB-orthogonal-edge_inner-v6_7": 35,
}

_EXPECTED_GATE_VALID_HISTORY_CARRIERS = {
    "experiments/runs/20260830T154155824053Z-batch-g20260831/run.json": 1,
    "experiments/runs/20260830T154309225370Z-batch-g20260831/run.json": 5,
    "experiments/runs/20260830T184008717197Z-strong-g20260901/run.json": 9,
}

_DEFINITION_BASE_KEYS = frozenset(
    (
        "schema_version",
        "name",
        "board_size",
        "first_player",
        "max_plies",
        "roles",
        "initial_pieces",
    )
)
_PROJECTION_RECORD_KEYS = frozenset(
    (
        "json_path",
        "definition_hash",
        "d4_canonical_hash",
        "schema_version",
        "board_size",
        "definition",
    )
)

_DEFINITION_PROJECTION_DOMAIN = (
    b"capture-boundary-v1-definition-projection-v1"
)
_HISTORICAL_SOURCE_D4_DOMAIN = b"two-runner-v1-historical-source-d4-v1"
_HISTORICAL_D4_DOMAIN = b"two-runner-v1-historical-d4-v1"
_HISTORICAL_PROJECTION_DOMAIN = b"two-runner-v1-historical-projection-v1"
_CLOSED_LEDGER_DOMAIN = b"two-runner-v1-closed-projection-bundle-v1"

_CLOSED_HISTORY_D4_DOMAIN = b"four-by-four-calibration-v1-history-d4-v1"
_CLOSED_HISTORY_MAX8_D4_DOMAIN = (
    b"four-by-four-calibration-v1-history-max8-d4-v1"
)
_CLOSED_HISTORY_PROJECTION_DOMAIN = (
    b"four-by-four-calibration-v1-closed-history-v1"
)
_RAW_D4_DOMAIN = b"four-by-four-calibration-v1-raw-d4-v1"
_GATE_VALID_D4_DOMAIN = b"four-by-four-calibration-v1-gate-valid-d4-v1"
_FRESH_GATE_VALID_D4_DOMAIN = (
    b"four-by-four-calibration-v1-fresh-gate-valid-d4-v1"
)
_NATIVE_HISTORY_D4_DOMAIN = (
    b"four-by-four-calibration-v1-native-history-d4-v1"
)
_GATE_VALID_HISTORY_D4_DOMAIN = (
    b"four-by-four-calibration-v1-gate-valid-history-d4-v1"
)
_SELECTION_SCORE_DOMAIN = b"four-by-four-calibration-v1-selection-score-v1"
_STRATUM_POOL_DOMAIN = b"four-by-four-calibration-v1-stratum-pool-v1"
_ELIGIBLE_POOLS_DOMAIN = b"four-by-four-calibration-v1-eligible-pools-v1"
_SELECTION_FINGERPRINT_DOMAIN = (
    b"four-by-four-calibration-v1-selection-fingerprint-v1"
)
_CASE_FINGERPRINT_DOMAIN = b"four-by-four-calibration-v1-case-v1"

_PLAN_PATH = (
    "docs/plans/active/0011-four-by-four-evaluator-transfer-calibration.md"
)
_SELECTION_INPUT_ATTESTATION = "authenticated-definition-projections-only"

_GENERATOR_VECTORS = frozenset(
    (
        (-1, -1),
        (-1, 0),
        (-1, 1),
        (0, -1),
        (0, 1),
        (1, -1),
        (1, 0),
        (1, 1),
    )
)


def _canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ValueError("value must be finite JSON") from error


def _json_copy(value: Any, label: str) -> Any:
    try:
        return json.loads(_canonical_bytes(value))
    except (TypeError, ValueError) as error:
        raise ValueError("{} must be finite JSON".format(label)) from error


def _domain_digest(domain: bytes, value: Any) -> str:
    return hashlib.sha256(domain + b"\0" + _canonical_bytes(value)).hexdigest()


def _exact_keys(
    value: Any, expected: Iterable[str], label: str
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("{} must be an object".format(label))
    expected_set = set(expected)
    if set(value) != expected_set:
        raise ValueError(
            "{} keys must be exactly {}".format(label, sorted(expected_set))
        )
    return value


def _require_int(value: Any, expected: int | None, label: str) -> int:
    if type(value) is not int:
        raise ValueError("{} must be an integer".format(label))
    if expected is not None and value != expected:
        raise ValueError("{} mismatch".format(label))
    return value


def _require_sha256(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError("{} must be a canonical lowercase SHA-256".format(label))
    return value


def _require_sorted_hashes(value: Any, label: str) -> Tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError("{} must be an array".format(label))
    hashes = tuple(_require_sha256(item, label) for item in value)
    if list(hashes) != sorted(set(hashes)):
        raise ValueError("{} must be unique and lexically ordered".format(label))
    return hashes


def _load_authenticated_json_bytes(
    value: Any,
    *,
    expected_sha256: str,
    expected_bytes: int | None,
    label: str,
) -> Any:
    if type(value) is not bytes:
        raise TypeError("{} must be immutable bytes".format(label))
    if expected_bytes is not None and len(value) != expected_bytes:
        raise ValueError("{} byte length mismatch".format(label))
    if hashlib.sha256(value).hexdigest() != expected_sha256:
        raise ValueError("{} SHA-256 mismatch".format(label))
    try:
        text = value.decode("utf-8")
        return json.loads(
            text,
            parse_constant=lambda token: (_ for _ in ()).throw(
                ValueError("non-finite JSON constant {}".format(token))
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError("{} must contain strict UTF-8 JSON".format(label)) from error


def _pointer_token(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _project_definitions(value: Any) -> Dict[str, Any]:
    """Project exact DSL objects while ignoring all surrounding evidence fields."""

    detached = _json_copy(value, "definition projection source")
    records = []

    def visit(item: Any, path: str) -> None:
        if isinstance(item, dict):
            if _DEFINITION_BASE_KEYS <= set(item):
                definition = parse_definition(item)
                records.append(
                    {
                        "json_path": path,
                        "definition_hash": definition_hash(definition),
                        "d4_canonical_hash": d4_canonical_hash(definition),
                        "schema_version": definition.schema_version,
                        "board_size": definition.board_size,
                        "definition": definition.to_dict(),
                    }
                )
                return
            for key in sorted(item):
                if not isinstance(key, str):
                    raise ValueError(
                        "definition projection object keys must be strings"
                    )
                visit(item[key], path + "/" + _pointer_token(key))
        elif isinstance(item, list):
            for index, child in enumerate(item):
                visit(child, path + "/" + str(index))

    visit(detached, "")
    records.sort(key=lambda record: record["json_path"])
    projection = {
        "projection_version": 1,
        "occurrence_count": len(records),
        "projection_root": _domain_digest(_DEFINITION_PROJECTION_DOMAIN, records),
        "records": records,
    }
    _validate_definition_projection(projection)
    return projection


def _validate_definition_projection(
    value: Any,
) -> Tuple[Dict[str, Any], ...]:
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
    for raw_record in top["records"]:
        record = _exact_keys(
            raw_record, _PROJECTION_RECORD_KEYS, "definition projection record"
        )
        path = record["json_path"]
        if not isinstance(path, str):
            raise ValueError("definition projection path must be a string")
        definition = parse_definition(record["definition"])
        if _canonical_bytes(record["definition"]) != _canonical_bytes(
            definition.to_dict()
        ):
            raise ValueError("projected definition must use canonical DSL bytes")
        if (
            _require_sha256(
                record["definition_hash"], "projected definition hash"
            )
            != definition_hash(definition)
            or _require_sha256(record["d4_canonical_hash"], "projected D4 hash")
            != d4_canonical_hash(definition)
        ):
            raise ValueError("projected definition identity mismatch")
        _require_int(
            record["schema_version"],
            definition.schema_version,
            "projected schema version",
        )
        _require_int(
            record["board_size"], definition.board_size, "projected board size"
        )
        paths.append(path)
        records.append(_json_copy(record, "definition projection record"))
    if paths != sorted(set(paths)):
        raise ValueError("definition projection paths must be unique and ordered")
    _require_int(
        top["occurrence_count"], len(records), "definition occurrence count"
    )
    if _require_sha256(
        top["projection_root"], "definition projection root"
    ) != _domain_digest(_DEFINITION_PROJECTION_DOMAIN, records):
        raise ValueError("definition projection root mismatch")
    return tuple(records)


def _project_static_corpus(value: Any) -> Dict[str, Any]:
    """Reproduce the reviewed adapter for six valid and one invalid fixture."""

    top = _exact_keys(
        value, ("corpus_id", "frozen", "purpose", "cases"), "static corpus"
    )
    if top["corpus_id"] != "static-v1-2026-08-31" or top["frozen"] is not True:
        raise ValueError("static corpus identity or frozen marker mismatch")
    if not isinstance(top["purpose"], str) or not top["purpose"]:
        raise ValueError("static corpus purpose must be nonempty")
    expected_failures = {
        "healthy-crossing-seeds": [],
        "full-board-no-opening": ["NO_LEGAL_MOVE_AT_START"],
        "missing-runner": ["UNREACHABLE_WIN_CONDITION"],
        "initial-connection": ["TRIVIAL_FORCED_RESULT"],
        "same-action-roles": ["TOO_SYMMETRIC"],
        "over-parameterized-movement": ["TOO_COMPLEX"],
        "invalid-board-size": ["INVALID_DEFINITION"],
    }
    if not isinstance(top["cases"], list) or len(top["cases"]) != len(
        expected_failures
    ):
        raise ValueError("static corpus case census mismatch")
    valid_definitions = []
    observed_ids = []
    for raw_case in top["cases"]:
        case = _exact_keys(
            raw_case,
            ("id", "expected_failures", "definition"),
            "static corpus case",
        )
        case_id = case["id"]
        if not isinstance(case_id, str) or case_id not in expected_failures:
            raise ValueError("static corpus case identity mismatch")
        observed_ids.append(case_id)
        if _canonical_bytes(case["expected_failures"]) != _canonical_bytes(
            expected_failures[case_id]
        ):
            raise ValueError("static corpus expected-failure contract mismatch")
        if case_id == "invalid-board-size":
            try:
                parse_definition(case["definition"])
            except DefinitionError:
                continue
            raise ValueError("static invalid-board fixture unexpectedly parsed")
        valid_definitions.append(parse_definition(case["definition"]).to_dict())
    if observed_ids != list(expected_failures):
        raise ValueError("static corpus cases must retain frozen order")
    projection = _project_definitions(valid_definitions)
    records = _validate_definition_projection(projection)
    if len(records) != 6 or len(
        {record["d4_canonical_hash"] for record in records}
    ) != 6:
        raise ValueError("static corpus valid-definition projection census mismatch")
    return projection


def _validated_artifact(value: Any, label: str) -> Dict[str, str]:
    top = _exact_keys(
        value, ("path", "sha256", "identity_kind", "identity"), label
    )
    path = top["path"]
    if (
        not isinstance(path, str)
        or not path
        or path.startswith("/")
        or ".." in path.split("/")
    ):
        raise ValueError("{} path must be canonical and repository-relative".format(label))
    if not isinstance(top["identity_kind"], str) or not top["identity_kind"]:
        raise ValueError("{} identity kind must be nonempty".format(label))
    if not isinstance(top["identity"], str) or not top["identity"]:
        raise ValueError("{} identity must be nonempty".format(label))
    return {
        "path": path,
        "sha256": _require_sha256(top["sha256"], label + " SHA"),
        "identity_kind": top["identity_kind"],
        "identity": top["identity"],
    }


def _validate_reviewed_ledger(
    ledger: Any,
) -> Tuple[Mapping[str, Any], Tuple[Mapping[str, Any], ...]]:
    top = _exact_keys(
        ledger,
        (
            "base_coverage_root",
            "base_exclusion_ledger_root",
            "bundle_root",
            "bundle_version",
            "evaluated_orbit_projection",
            "historical_artifact_count",
            "historical_artifact_paths",
            "historical_definition_projection",
            "plan0009_full_definition_projection_root",
            "plan0009_manifest_artifact",
            "plan0009_source_projection_root",
        ),
        "reviewed closed ledger",
    )
    _require_int(top["bundle_version"], 1, "closed ledger version")
    unsigned = dict(top)
    bundle_root = unsigned.pop("bundle_root")
    if (
        _require_sha256(bundle_root, "closed ledger bundle root")
        != _domain_digest(_CLOSED_LEDGER_DOMAIN, unsigned)
        or bundle_root != FOUR_BY_FOUR_LEDGER_BUNDLE_ROOT
    ):
        raise ValueError("reviewed closed ledger bundle root mismatch")
    _require_int(
        top["historical_artifact_count"],
        FOUR_BY_FOUR_LEDGER_SOURCE_COUNT,
        "closed ledger artifact count",
    )
    historical = _exact_keys(
        top["historical_definition_projection"],
        (
            "definition_occurrence_count",
            "projection_root",
            "projection_version",
            "source_count",
            "sources",
            "unique_d4_count",
            "unique_d4_hashes",
            "unique_d4_root",
            "unique_definition_count",
        ),
        "reviewed historical projection",
    )
    if not isinstance(historical["sources"], list):
        raise ValueError("reviewed historical sources must be an array")
    sources = tuple(historical["sources"])
    _require_int(
        historical["source_count"],
        FOUR_BY_FOUR_LEDGER_SOURCE_COUNT,
        "reviewed historical source count",
    )
    if len(sources) != FOUR_BY_FOUR_LEDGER_SOURCE_COUNT:
        raise ValueError("reviewed historical source array count mismatch")
    paths = [
        _validated_artifact(source["artifact"], "reviewed historical artifact")[
            "path"
        ]
        for source in sources
        if isinstance(source, Mapping) and "artifact" in source
    ]
    if len(paths) != len(sources) or paths != sorted(set(paths)):
        raise ValueError("reviewed historical source paths mismatch")
    if top["historical_artifact_paths"] != paths:
        raise ValueError("closed ledger historical path list mismatch")
    return historical, sources


def _rebuild_reviewed_historical_projection(
    source_records: Sequence[Tuple[Mapping[str, Any], Mapping[str, Any]]],
) -> Dict[str, Any]:
    summaries = []
    all_definition_hashes: Set[str] = set()
    all_d4_hashes: Set[str] = set()
    occurrence_count = 0
    for source, projection in source_records:
        artifact = _validated_artifact(
            source["artifact"], "reviewed historical artifact"
        )
        records = _validate_definition_projection(projection)
        definition_hashes = sorted(
            {record["definition_hash"] for record in records}
        )
        d4_hashes = sorted({record["d4_canonical_hash"] for record in records})
        occurrence_count += len(records)
        all_definition_hashes.update(definition_hashes)
        all_d4_hashes.update(d4_hashes)
        summaries.append(
            {
                "artifact": artifact,
                "definition_projection_root": projection["projection_root"],
                "definition_occurrence_count": len(records),
                "unique_definition_count": len(definition_hashes),
                "unique_d4_count": len(d4_hashes),
                "unique_d4_root": _domain_digest(
                    _HISTORICAL_SOURCE_D4_DOMAIN, d4_hashes
                ),
            }
        )
    summaries.sort(key=lambda record: record["artifact"]["path"])
    d4_hashes = sorted(all_d4_hashes)
    result = {
        "projection_version": 1,
        "source_count": len(summaries),
        "definition_occurrence_count": occurrence_count,
        "unique_definition_count": len(all_definition_hashes),
        "unique_d4_count": len(d4_hashes),
        "unique_d4_hashes": d4_hashes,
        "unique_d4_root": _domain_digest(_HISTORICAL_D4_DOMAIN, d4_hashes),
        "sources": summaries,
    }
    result["projection_root"] = _domain_digest(
        _HISTORICAL_PROJECTION_DOMAIN, result
    )
    return result


def build_four_by_four_closed_history_projection(
    ledger_bytes: bytes,
    historical_artifact_bytes: Mapping[str, bytes],
    plan0010_manifest_bytes: bytes,
) -> Dict[str, Any]:
    """Reconstruct the closed definition history from exactly pinned bytes.

    ``historical_artifact_bytes`` must contain the 21 paths named by the reviewed
    Plan-0010 ledger, no fewer and no more.  The Plan-0010 outcome-free manifest
    is authenticated and added as the twenty-second source.  No directory scan,
    admission decision, result field, or caller-supplied source metadata can
    influence the projection.
    """

    ledger = _load_authenticated_json_bytes(
        ledger_bytes,
        expected_sha256=FOUR_BY_FOUR_LEDGER_SHA256,
        expected_bytes=FOUR_BY_FOUR_LEDGER_BYTES,
        label="reviewed Plan-0010 closed ledger",
    )
    reviewed_history, reviewed_sources = _validate_reviewed_ledger(ledger)
    if not isinstance(historical_artifact_bytes, Mapping):
        raise TypeError("historical artifact bytes must be a path-to-bytes mapping")
    expected_paths = tuple(
        source["artifact"]["path"] for source in reviewed_sources
    )
    if set(historical_artifact_bytes) != set(expected_paths):
        raise ValueError(
            "historical artifact bytes must match the reviewed 21-path graph exactly"
        )

    rebuilt_inputs = []
    detailed_sources = []
    all_records = []
    for raw_source in reviewed_sources:
        source = _exact_keys(
            raw_source,
            (
                "artifact",
                "definition_projection_root",
                "definition_occurrence_count",
                "unique_definition_count",
                "unique_d4_count",
                "unique_d4_root",
            ),
            "reviewed historical source",
        )
        artifact = _validated_artifact(
            source["artifact"], "reviewed historical artifact"
        )
        path = artifact["path"]
        document = _load_authenticated_json_bytes(
            historical_artifact_bytes[path],
            expected_sha256=artifact["sha256"],
            expected_bytes=None,
            label="historical artifact " + path,
        )
        if (
            not isinstance(document, Mapping)
            or document.get(artifact["identity_kind"]) != artifact["identity"]
        ):
            raise ValueError("historical artifact identity mismatch for " + path)
        projection = (
            _project_static_corpus(document)
            if path == "experiments/corpora/static-v1/corpus.json"
            else _project_definitions(document)
        )
        rebuilt_inputs.append((source, projection))
        records = _validate_definition_projection(projection)
        all_records.extend(records)
        max8_records = [
            record
            for record in records
            if record["schema_version"] == 1
            and record["board_size"] == 4
            and record["definition"]["max_plies"] == 8
        ]
        max8_hashes = sorted(
            {record["d4_canonical_hash"] for record in max8_records}
        )
        detailed_sources.append(
            {
                "artifact": artifact,
                "definition_projection_root": projection["projection_root"],
                "definition_occurrence_count": len(records),
                "unique_definition_count": len(
                    {record["definition_hash"] for record in records}
                ),
                "unique_d4_count": len(
                    {record["d4_canonical_hash"] for record in records}
                ),
                "max8_definition_occurrence_count": len(max8_records),
                "max8_unique_d4_count": len(max8_hashes),
                "max8_unique_d4_hashes": max8_hashes,
            }
        )

    rebuilt_reviewed = _rebuild_reviewed_historical_projection(rebuilt_inputs)
    if _canonical_bytes(rebuilt_reviewed) != _canonical_bytes(reviewed_history):
        raise ValueError(
            "reviewed historical projection does not match authenticated sources"
        )

    plan0010 = _load_authenticated_json_bytes(
        plan0010_manifest_bytes,
        expected_sha256=FOUR_BY_FOUR_PLAN0010_MANIFEST_SHA256,
        expected_bytes=FOUR_BY_FOUR_PLAN0010_MANIFEST_BYTES,
        label="Plan-0010 outcome-free manifest",
    )
    if (
        not isinstance(plan0010, Mapping)
        or plan0010.get("manifest_id") != "two-runner-v1-64-pair-manifest"
        or plan0010.get("status") != "FROZEN"
    ):
        raise ValueError("Plan-0010 manifest identity or status mismatch")
    selection_protocol = plan0010.get("selection_protocol")
    if (
        not isinstance(selection_protocol, Mapping)
        or selection_protocol.get("case_membership_outcome_fields_consulted")
        is not False
        or selection_protocol.get("treatment_outcomes_computed") is not False
    ):
        raise ValueError("Plan-0010 manifest is not outcome-free")
    plan0010_projection = _project_definitions(plan0010)
    plan0010_records = _validate_definition_projection(plan0010_projection)
    if (
        len(plan0010_records) != 128
        or len({record["definition_hash"] for record in plan0010_records}) != 128
        or len({record["d4_canonical_hash"] for record in plan0010_records}) != 128
    ):
        raise ValueError("Plan-0010 definition projection census mismatch")
    plan0010_max8 = [
        record
        for record in plan0010_records
        if record["schema_version"] == 1
        and record["board_size"] == 4
        and record["definition"]["max_plies"] == 8
    ]
    if plan0010_max8:
        raise ValueError("Plan-0010 manifest unexpectedly intersects 4x4/max-8")
    plan0010_artifact = {
        "path": FOUR_BY_FOUR_PLAN0010_MANIFEST_PATH,
        "sha256": FOUR_BY_FOUR_PLAN0010_MANIFEST_SHA256,
        "identity_kind": "manifest_id",
        "identity": "two-runner-v1-64-pair-manifest",
    }
    detailed_sources.append(
        {
            "artifact": plan0010_artifact,
            "definition_projection_root": plan0010_projection["projection_root"],
            "definition_occurrence_count": len(plan0010_records),
            "unique_definition_count": 128,
            "unique_d4_count": 128,
            "max8_definition_occurrence_count": 0,
            "max8_unique_d4_count": 0,
            "max8_unique_d4_hashes": [],
        }
    )
    all_records.extend(plan0010_records)
    detailed_sources.sort(key=lambda source: source["artifact"]["path"])

    all_definition_hashes = sorted(
        {record["definition_hash"] for record in all_records}
    )
    all_d4_hashes = sorted(
        {record["d4_canonical_hash"] for record in all_records}
    )
    max8_records = [
        record
        for record in all_records
        if record["schema_version"] == 1
        and record["board_size"] == 4
        and record["definition"]["max_plies"] == 8
    ]
    max8_hashes = sorted(
        {record["d4_canonical_hash"] for record in max8_records}
    )
    projection = {
        "projection_version": 1,
        "closed_ledger": {
            "path": FOUR_BY_FOUR_LEDGER_PATH,
            "sha256": FOUR_BY_FOUR_LEDGER_SHA256,
            "bytes": FOUR_BY_FOUR_LEDGER_BYTES,
            "bundle_root": FOUR_BY_FOUR_LEDGER_BUNDLE_ROOT,
        },
        "plan0010_manifest": {
            "path": FOUR_BY_FOUR_PLAN0010_MANIFEST_PATH,
            "sha256": FOUR_BY_FOUR_PLAN0010_MANIFEST_SHA256,
            "bytes": FOUR_BY_FOUR_PLAN0010_MANIFEST_BYTES,
            "manifest_id": "two-runner-v1-64-pair-manifest",
            "definition_projection_root": plan0010_projection["projection_root"],
        },
        "source_count": len(detailed_sources),
        "definition_occurrence_count": len(all_records),
        "unique_definition_count": len(all_definition_hashes),
        "unique_d4_count": len(all_d4_hashes),
        "unique_d4_hashes": all_d4_hashes,
        "unique_d4_root": _domain_digest(
            _CLOSED_HISTORY_D4_DOMAIN, all_d4_hashes
        ),
        "max8_definition_occurrence_count": len(max8_records),
        "max8_unique_d4_count": len(max8_hashes),
        "max8_unique_d4_hashes": max8_hashes,
        "max8_unique_d4_root": _domain_digest(
            _CLOSED_HISTORY_MAX8_D4_DOMAIN, max8_hashes
        ),
        "sources": detailed_sources,
    }
    projection["projection_root"] = _domain_digest(
        _CLOSED_HISTORY_PROJECTION_DOMAIN, projection
    )
    validate_four_by_four_closed_history_projection(projection)
    return _json_copy(projection, "4x4 closed history projection")


def validate_four_by_four_closed_history_projection(
    value: Any,
    ledger_bytes: bytes | None = None,
    historical_artifact_bytes: Mapping[str, bytes] | None = None,
    plan0010_manifest_bytes: bytes | None = None,
) -> Tuple[str, ...]:
    """Validate the closed projection and optionally replay every source byte."""

    top = _exact_keys(
        value,
        (
            "projection_version",
            "closed_ledger",
            "plan0010_manifest",
            "source_count",
            "definition_occurrence_count",
            "unique_definition_count",
            "unique_d4_count",
            "unique_d4_hashes",
            "unique_d4_root",
            "max8_definition_occurrence_count",
            "max8_unique_d4_count",
            "max8_unique_d4_hashes",
            "max8_unique_d4_root",
            "sources",
            "projection_root",
        ),
        "4x4 closed history projection",
    )
    _require_int(top["projection_version"], 1, "closed history version")
    expected_ledger = {
        "path": FOUR_BY_FOUR_LEDGER_PATH,
        "sha256": FOUR_BY_FOUR_LEDGER_SHA256,
        "bytes": FOUR_BY_FOUR_LEDGER_BYTES,
        "bundle_root": FOUR_BY_FOUR_LEDGER_BUNDLE_ROOT,
    }
    if _canonical_bytes(top["closed_ledger"]) != _canonical_bytes(
        expected_ledger
    ):
        raise ValueError("closed history ledger seal mismatch")
    plan0010 = _exact_keys(
        top["plan0010_manifest"],
        (
            "path",
            "sha256",
            "bytes",
            "manifest_id",
            "definition_projection_root",
        ),
        "closed history Plan-0010 manifest",
    )
    if (
        plan0010["path"] != FOUR_BY_FOUR_PLAN0010_MANIFEST_PATH
        or plan0010["sha256"] != FOUR_BY_FOUR_PLAN0010_MANIFEST_SHA256
        or _require_int(
            plan0010["bytes"],
            FOUR_BY_FOUR_PLAN0010_MANIFEST_BYTES,
            "Plan-0010 manifest bytes",
        )
        != FOUR_BY_FOUR_PLAN0010_MANIFEST_BYTES
        or plan0010["manifest_id"] != "two-runner-v1-64-pair-manifest"
    ):
        raise ValueError("closed history Plan-0010 manifest seal mismatch")
    _require_sha256(
        plan0010["definition_projection_root"],
        "Plan-0010 definition projection root",
    )
    if not isinstance(top["sources"], list):
        raise ValueError("closed history sources must be an array")
    _require_int(
        top["source_count"],
        FOUR_BY_FOUR_CLOSED_SOURCE_COUNT,
        "closed history source count",
    )
    if len(top["sources"]) != FOUR_BY_FOUR_CLOSED_SOURCE_COUNT:
        raise ValueError("closed history source array count mismatch")
    paths = []
    source_occurrence_sum = 0
    max8_occurrence_sum = 0
    max8_union: Set[str] = set()
    for raw_source in top["sources"]:
        source = _exact_keys(
            raw_source,
            (
                "artifact",
                "definition_projection_root",
                "definition_occurrence_count",
                "unique_definition_count",
                "unique_d4_count",
                "max8_definition_occurrence_count",
                "max8_unique_d4_count",
                "max8_unique_d4_hashes",
            ),
            "closed history source",
        )
        artifact = _validated_artifact(
            source["artifact"], "closed history source artifact"
        )
        paths.append(artifact["path"])
        _require_sha256(
            source["definition_projection_root"],
            "closed source definition projection root",
        )
        occurrence = _require_int(
            source["definition_occurrence_count"],
            None,
            "closed source definition occurrence count",
        )
        unique_definition_count = _require_int(
            source["unique_definition_count"],
            None,
            "closed source unique-definition count",
        )
        unique_d4_count = _require_int(
            source["unique_d4_count"], None, "closed source unique-D4 count"
        )
        max8_occurrence = _require_int(
            source["max8_definition_occurrence_count"],
            None,
            "closed source max8 occurrence count",
        )
        max8_hashes = _require_sorted_hashes(
            source["max8_unique_d4_hashes"], "closed source max8 D4 hashes"
        )
        _require_int(
            source["max8_unique_d4_count"],
            len(max8_hashes),
            "closed source max8 D4 count",
        )
        if (
            min(
                occurrence,
                unique_definition_count,
                unique_d4_count,
                max8_occurrence,
            )
            < 0
            or unique_definition_count > occurrence
            or unique_d4_count > occurrence
            or max8_occurrence > occurrence
            or len(max8_hashes) > max8_occurrence
        ):
            raise ValueError("closed history source counts are inconsistent")
        max8_occurrence_sum += max8_occurrence
        source_occurrence_sum += occurrence
        max8_union.update(max8_hashes)
    if paths != sorted(set(paths)):
        raise ValueError("closed history source paths must be unique and ordered")
    if FOUR_BY_FOUR_PLAN0010_MANIFEST_PATH not in paths:
        raise ValueError("closed history omits the Plan-0010 manifest")

    _require_int(
        top["definition_occurrence_count"],
        FOUR_BY_FOUR_HISTORICAL_DEFINITION_OCCURRENCE_COUNT,
        "closed history definition occurrence count",
    )
    if source_occurrence_sum != FOUR_BY_FOUR_HISTORICAL_DEFINITION_OCCURRENCE_COUNT:
        raise ValueError("closed history source occurrence sum mismatch")
    _require_int(
        top["unique_definition_count"],
        FOUR_BY_FOUR_HISTORICAL_UNIQUE_DEFINITION_COUNT,
        "closed history unique-definition count",
    )
    hashes = _require_sorted_hashes(
        top["unique_d4_hashes"], "closed history D4 hashes"
    )
    _require_int(
        top["unique_d4_count"],
        FOUR_BY_FOUR_HISTORICAL_UNIQUE_D4_COUNT,
        "closed history unique-D4 count",
    )
    if len(hashes) != FOUR_BY_FOUR_HISTORICAL_UNIQUE_D4_COUNT:
        raise ValueError("closed history D4 array count mismatch")
    if top["unique_d4_root"] != _domain_digest(
        _CLOSED_HISTORY_D4_DOMAIN, list(hashes)
    ):
        raise ValueError("closed history D4 root mismatch")
    max8_hashes = _require_sorted_hashes(
        top["max8_unique_d4_hashes"], "closed history max8 D4 hashes"
    )
    _require_int(
        top["max8_unique_d4_count"],
        FOUR_BY_FOUR_HISTORICAL_MAX8_UNIQUE_D4_COUNT,
        "closed history max8 D4 count",
    )
    if (
        len(max8_hashes) != FOUR_BY_FOUR_HISTORICAL_MAX8_UNIQUE_D4_COUNT
        or set(max8_hashes) != max8_union
        or not set(max8_hashes) <= set(hashes)
    ):
        raise ValueError("closed history max8 D4 union mismatch")
    _require_int(
        top["max8_definition_occurrence_count"],
        max8_occurrence_sum,
        "closed history max8 occurrence count",
    )
    if top["max8_unique_d4_root"] != _domain_digest(
        _CLOSED_HISTORY_MAX8_D4_DOMAIN, list(max8_hashes)
    ):
        raise ValueError("closed history max8 D4 root mismatch")
    unsigned = dict(top)
    projection_root = unsigned.pop("projection_root")
    if _require_sha256(
        projection_root, "closed history projection root"
    ) != _domain_digest(_CLOSED_HISTORY_PROJECTION_DOMAIN, unsigned):
        raise ValueError("closed history projection root mismatch")
    if (
        FOUR_BY_FOUR_CLOSED_HISTORY_PROJECTION_ROOT
        and projection_root != FOUR_BY_FOUR_CLOSED_HISTORY_PROJECTION_ROOT
    ):
        raise ValueError("closed history projection differs from frozen root")

    reconstruction = (
        ledger_bytes,
        historical_artifact_bytes,
        plan0010_manifest_bytes,
    )
    if any(item is None for item in reconstruction) and not all(
        item is None for item in reconstruction
    ):
        raise ValueError("closed history replay requires every authenticated input")
    if all(item is not None for item in reconstruction):
        expected = build_four_by_four_closed_history_projection(
            ledger_bytes,  # type: ignore[arg-type]
            historical_artifact_bytes,  # type: ignore[arg-type]
            plan0010_manifest_bytes,  # type: ignore[arg-type]
        )
        if _canonical_bytes(top) != _canonical_bytes(expected):
            raise ValueError("closed history projection differs from byte replay")
    return max8_hashes


def _coerce_definition(value: Any) -> GameDefinition:
    if isinstance(value, GameDefinition):
        try:
            return parse_definition(value.to_dict())
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError(
                "GameDefinition must round-trip through the strict DSL parser"
            ) from error
    if isinstance(value, Mapping):
        return parse_definition(value)
    raise TypeError("definition must be a GameDefinition or mapping")


def _opposite_edge_positions(
    size: int, target: Edge
) -> Tuple[Tuple[int, int], ...]:
    if target is Edge.TOP:
        return tuple((size - 1, column) for column in range(size))
    if target is Edge.BOTTOM:
        return tuple((0, column) for column in range(size))
    if target is Edge.LEFT:
        return tuple((row, size - 1) for row in range(size))
    return tuple((row, 0) for row in range(size))


def _validate_four_by_four_family(definition: GameDefinition) -> None:
    if (
        definition.schema_version != 1
        or definition.board_size != 4
        or definition.max_plies != 8
        or definition.terminal_policy is not None
    ):
        raise ValueError(
            "calibration definitions must use schema v1 on 4x4 with max_plies 8"
        )
    role_a = definition.role(Player.A)
    role_b = definition.role(Player.B)
    if (
        role_a.action.kind is not ActionKind.PLACE
        or role_a.action.piece != "seed"
        or role_a.goal.kind is not GoalKind.CONNECT_EDGES
        or role_a.goal.piece != "seed"
        or role_b.action.kind is not ActionKind.MOVE
        or role_b.action.piece != "runner"
        or not 1 <= len(role_b.action.vectors) <= 8
        or not set(role_b.action.vectors) <= _GENERATOR_VECTORS
        or role_b.goal.kind is not GoalKind.REACH_EDGE
        or role_b.goal.piece != "runner"
        or role_b.goal.edge is None
    ):
        raise ValueError("definition is outside the native place-versus-move family")
    if (
        len(definition.initial_pieces) != 1
        or definition.initial_pieces[0].owner is not Player.B
        or definition.initial_pieces[0].piece != "runner"
        or definition.initial_pieces[0].position
        not in _opposite_edge_positions(4, role_b.goal.edge)
    ):
        raise ValueError(
            "definition must contain one B runner on the edge opposite its target"
        )


def validate_four_by_four_calibration_definition(
    definition_value: Any,
) -> GameDefinition:
    """Return one strictly validated native 4x4/max-8 family definition."""

    definition = _coerce_definition(definition_value)
    _validate_four_by_four_family(definition)
    return definition


def four_by_four_state_proof(definition_value: Any) -> Dict[str, Any]:
    """Return the public ply-layer proof for one exact-calibration case."""

    definition = _coerce_definition(definition_value)
    _validate_four_by_four_family(definition)
    seed_counts = (
        (0, 1, 1, 2, 2, 3, 3, 4, 4)
        if definition.first_player is Player.A
        else (0, 0, 1, 1, 2, 2, 3, 3, 4)
    )
    layer_bounds = tuple(16 * math.comb(15, count) for count in seed_counts)
    state_bound = sum(layer_bounds)
    expected = (
        FOUR_BY_FOUR_A_FIRST_STATE_BOUND
        if definition.first_player is Player.A
        else FOUR_BY_FOUR_B_FIRST_STATE_BOUND
    )
    if state_bound != expected:
        raise AssertionError("4x4 state-bound derivation drifted")
    return {
        "board_cells": 16,
        "non_runner_cells": 15,
        "first_player": definition.first_player.value,
        "ply_layers": list(range(9)),
        "a_seed_counts": list(seed_counts),
        "layer_state_bounds": list(layer_bounds),
        "state_bound": state_bound,
        "exact_max_states": FOUR_BY_FOUR_EXACT_MAX_STATES,
        "cap_margin": FOUR_BY_FOUR_EXACT_MAX_STATES - state_bound,
    }


def build_four_by_four_state_bound_proof() -> Dict[str, Any]:
    """Build the definition-independent A/B ply-layer and fixed-corpus proof."""

    seed_counts = {
        "A": (0, 1, 1, 2, 2, 3, 3, 4, 4),
        "B": (0, 0, 1, 1, 2, 2, 3, 3, 4),
    }
    first_player_proofs = {}
    for first, counts in seed_counts.items():
        layers = tuple(16 * math.comb(15, count) for count in counts)
        first_player_proofs[first] = {
            "a_seed_counts": list(counts),
            "layer_state_bounds": list(layers),
            "state_bound": sum(layers),
            "cap_margin": FOUR_BY_FOUR_EXACT_MAX_STATES - sum(layers),
        }
    proof = {
        "proof_version": 1,
        "board_cells": 16,
        "non_runner_cells": 15,
        "ply_layers": list(range(9)),
        "exact_max_states": FOUR_BY_FOUR_EXACT_MAX_STATES,
        "first_player_proofs": first_player_proofs,
        "fixed_case_counts": {"A": 16, "B": 16},
        "fixed_corpus_state_bound": (
            16 * first_player_proofs["A"]["state_bound"]
            + 16 * first_player_proofs["B"]["state_bound"]
        ),
    }
    validate_four_by_four_state_bound_proof(proof)
    return _json_copy(proof, "4x4 state-bound proof")


def validate_four_by_four_state_bound_proof(value: Any) -> Dict[str, Any]:
    """Recompute the fixed combinatorial proof and reject derived-field drift."""

    expected_counts = {
        "A": (0, 1, 1, 2, 2, 3, 3, 4, 4),
        "B": (0, 0, 1, 1, 2, 2, 3, 3, 4),
    }
    top = _exact_keys(
        value,
        (
            "proof_version",
            "board_cells",
            "non_runner_cells",
            "ply_layers",
            "exact_max_states",
            "first_player_proofs",
            "fixed_case_counts",
            "fixed_corpus_state_bound",
        ),
        "4x4 state-bound proof",
    )
    _require_int(top["proof_version"], 1, "state proof version")
    _require_int(top["board_cells"], 16, "state proof board cells")
    _require_int(top["non_runner_cells"], 15, "state proof non-runner cells")
    if (
        not isinstance(top["ply_layers"], list)
        or any(type(item) is not int for item in top["ply_layers"])
        or top["ply_layers"] != list(range(9))
    ):
        raise ValueError("state proof ply layers mismatch")
    _require_int(
        top["exact_max_states"],
        FOUR_BY_FOUR_EXACT_MAX_STATES,
        "state proof exact cap",
    )
    if not isinstance(top["first_player_proofs"], Mapping) or set(
        top["first_player_proofs"]
    ) != {"A", "B"}:
        raise ValueError("state proof must contain exactly A and B first")
    bounds = {}
    for first, counts in expected_counts.items():
        record = _exact_keys(
            top["first_player_proofs"][first],
            ("a_seed_counts", "layer_state_bounds", "state_bound", "cap_margin"),
            "{}-first state proof".format(first),
        )
        if (
            not isinstance(record["a_seed_counts"], list)
            or any(type(item) is not int for item in record["a_seed_counts"])
            or record["a_seed_counts"] != list(counts)
        ):
            raise ValueError("{}-first seed-count layers mismatch".format(first))
        expected_layers = [16 * math.comb(15, count) for count in counts]
        if (
            not isinstance(record["layer_state_bounds"], list)
            or any(
                type(item) is not int for item in record["layer_state_bounds"]
            )
            or record["layer_state_bounds"] != expected_layers
        ):
            raise ValueError("{}-first layer bounds mismatch".format(first))
        bound = sum(expected_layers)
        expected_bound = (
            FOUR_BY_FOUR_A_FIRST_STATE_BOUND
            if first == "A"
            else FOUR_BY_FOUR_B_FIRST_STATE_BOUND
        )
        _require_int(record["state_bound"], expected_bound, "state bound")
        _require_int(
            record["cap_margin"],
            FOUR_BY_FOUR_EXACT_MAX_STATES - bound,
            "state cap margin",
        )
        if bound >= FOUR_BY_FOUR_EXACT_MAX_STATES:
            raise ValueError("state proof does not fit the frozen exact cap")
        bounds[first] = bound
    fixed_counts = _exact_keys(
        top["fixed_case_counts"], ("A", "B"), "fixed state-proof case counts"
    )
    for first in ("A", "B"):
        _require_int(
            fixed_counts[first], 16, "fixed {}-first case count".format(first)
        )
    fixed_bound = 16 * bounds["A"] + 16 * bounds["B"]
    _require_int(
        top["fixed_corpus_state_bound"],
        FOUR_BY_FOUR_FIXED_CORPUS_STATE_BOUND,
        "fixed corpus state bound",
    )
    if fixed_bound != FOUR_BY_FOUR_FIXED_CORPUS_STATE_BOUND:
        raise AssertionError("fixed corpus state proof drifted")
    return _json_copy(top, "validated 4x4 state-bound proof")


def four_by_four_state_upper_bound(definition_value: Any) -> int:
    """Return the conservative exact-state bound for one fixed-horizon case."""

    return four_by_four_state_proof(definition_value)["state_bound"]


def validate_four_by_four_searched_states(
    searched_states: Any, definition_value: Any
) -> int:
    """Reject booleans, nonpositive counts, and violations of the public proof."""

    if type(searched_states) is not int or searched_states < 1:
        raise ValueError("searched states must be a positive integer")
    bound = four_by_four_state_upper_bound(definition_value)
    if searched_states > bound:
        raise ValueError("searched states exceed the 4x4 structural bound")
    return searched_states


@lru_cache(maxsize=1)
def _four_by_four_orbit_representatives() -> Tuple[Tuple[str, GameDefinition], ...]:
    definitions = enumerate_v2_four_by_four_max8()
    if len(definitions) != FOUR_BY_FOUR_RAW_DEFINITION_COUNT:
        raise AssertionError("4x4 raw definition census drifted")
    representatives: Dict[str, GameDefinition] = {}
    representative_hashes: Dict[str, str] = {}
    observed_orbits = set()
    for definition in definitions:
        _validate_four_by_four_family(definition)
        canonical = canonicalize_d4(definition)
        orbit_hash = canonical.canonical_hash
        observed_orbits.add(orbit_hash)
        if mechanical_json(definition) != canonical.mechanical_json:
            continue
        exact_hash = definition_hash(definition)
        if (
            orbit_hash not in representatives
            or exact_hash < representative_hashes[orbit_hash]
        ):
            representatives[orbit_hash] = definition
            representative_hashes[orbit_hash] = exact_hash
    if len(observed_orbits) != FOUR_BY_FOUR_RAW_D4_ORBIT_COUNT:
        raise AssertionError("4x4 raw D4 census drifted")
    if set(representatives) != observed_orbits:
        raise AssertionError("a 4x4 D4 orbit lacks a native canonical orientation")
    return tuple(sorted(representatives.items()))


def _passes_gates(definition: GameDefinition) -> bool:
    return (
        analyze_definition(definition).passes
        and evaluate_asymmetry(definition).qualifies
        and not exceeds_limits(evaluate_simplicity(definition))
    )


def _vector_band(vector_count: int) -> str:
    if 1 <= vector_count <= 3:
        return "v1_3"
    if vector_count == 4:
        return "v4"
    if vector_count == 5:
        return "v5"
    if 6 <= vector_count <= 7:
        return "v6_7"
    raise ValueError("eligible calibration definitions require one to seven vectors")


def four_by_four_stratum(definition_value: Any) -> Dict[str, Any]:
    """Return the four outcome-free structural dimensions for one case."""

    definition = _coerce_definition(definition_value)
    _validate_four_by_four_family(definition)
    role_a = definition.role(Player.A)
    role_b = definition.role(Player.B)
    if role_b.goal.edge is None:
        raise AssertionError("validated reach-edge goal lacks an edge")
    relation = (
        "ALIGNED" if role_b.goal.edge in role_a.goal.edges else "ORTHOGONAL"
    )
    row, column = definition.initial_pieces[0].position
    start_class = (
        "CORNER"
        if row in (0, definition.board_size - 1)
        and column in (0, definition.board_size - 1)
        else "EDGE_INTERIOR"
    )
    return {
        "first_player": definition.first_player.value,
        "goal_axis_relation": relation,
        "runner_start_class": start_class,
        "vector_band": _vector_band(len(role_b.action.vectors)),
    }


def four_by_four_calibration_stratum(definition_value: Any) -> Dict[str, Any]:
    """Named public alias for the fixed calibration stratum projection."""

    return four_by_four_stratum(definition_value)


def _stratum_id(stratum: Mapping[str, Any]) -> str:
    start = {
        "CORNER": "corner",
        "EDGE_INTERIOR": "edge_inner",
    }.get(stratum.get("runner_start_class"))
    relation = {
        "ALIGNED": "aligned",
        "ORTHOGONAL": "orthogonal",
    }.get(stratum.get("goal_axis_relation"))
    first = stratum.get("first_player")
    band = stratum.get("vector_band")
    if first not in ("A", "B") or relation is None or start is None or band not in (
        "v1_3",
        "v4",
        "v5",
        "v6_7",
    ):
        raise ValueError("invalid 4x4 structural stratum")
    return "f{}-{}-{}-{}".format(first, relation, start, band)


def _ordered_strata() -> Tuple[Tuple[str, Dict[str, Any]], ...]:
    records = []
    for first in ("A", "B"):
        for relation in ("ALIGNED", "ORTHOGONAL"):
            for start_class in ("CORNER", "EDGE_INTERIOR"):
                for vector_band in ("v1_3", "v4", "v5", "v6_7"):
                    stratum = {
                        "first_player": first,
                        "goal_axis_relation": relation,
                        "runner_start_class": start_class,
                        "vector_band": vector_band,
                    }
                    records.append((_stratum_id(stratum), stratum))
    if len(records) != FOUR_BY_FOUR_STRATUM_COUNT:
        raise AssertionError("4x4 stratum product drifted")
    return tuple(records)


def _selection_score(stratum: Mapping[str, Any], orbit_hash: str) -> str:
    return _domain_digest(
        _SELECTION_SCORE_DOMAIN,
        {"stratum": stratum, "d4_canonical_hash": orbit_hash},
    )


def _case_fingerprint(case: Mapping[str, Any]) -> str:
    payload = dict(case)
    payload.pop("case_fingerprint", None)
    return _domain_digest(_CASE_FINGERPRINT_DOMAIN, payload)


@lru_cache(maxsize=4)
def _selection_snapshot_json(
    history_projection_root: str,
    historical_max8_hashes: Tuple[str, ...],
    source_max8_hashes: Tuple[Tuple[str, Tuple[str, ...]], ...],
) -> str:
    representatives = dict(_four_by_four_orbit_representatives())
    raw_hashes = set(representatives)
    gate_valid_hashes = {
        orbit_hash
        for orbit_hash, definition in representatives.items()
        if _passes_gates(definition)
    }
    if len(gate_valid_hashes) != FOUR_BY_FOUR_GATE_VALID_D4_COUNT:
        raise ValueError("4x4 gate-valid D4 census mismatch")

    historical = set(historical_max8_hashes)
    native_history = raw_hashes & historical
    gate_valid_history = gate_valid_hashes & historical
    gate_invalid_history = native_history - gate_valid_history
    fresh_gate_valid = gate_valid_hashes - historical
    if len(native_history) != FOUR_BY_FOUR_HISTORICAL_NATIVE_D4_COUNT:
        raise ValueError("native 4x4 historical intersection mismatch")
    if len(gate_valid_history) != FOUR_BY_FOUR_HISTORICAL_GATE_VALID_D4_COUNT:
        raise ValueError("gate-valid historical exclusion count mismatch")
    if len(gate_invalid_history) != FOUR_BY_FOUR_HISTORICAL_GATE_INVALID_D4_COUNT:
        raise ValueError("gate-invalid historical intersection count mismatch")
    if len(fresh_gate_valid) != FOUR_BY_FOUR_FRESH_GATE_VALID_D4_COUNT:
        raise ValueError("fresh 4x4 gate-valid D4 census mismatch")

    carrier_records = []
    for path, hashes in source_max8_hashes:
        carried = sorted(set(hashes) & gate_valid_history)
        if carried:
            carrier_records.append(
                {
                    "path": path,
                    "gate_valid_exclusion_count": len(carried),
                    "gate_valid_exclusion_d4_hashes": carried,
                }
            )
    observed_carriers = {
        record["path"]: record["gate_valid_exclusion_count"]
        for record in carrier_records
    }
    if observed_carriers != _EXPECTED_GATE_VALID_HISTORY_CARRIERS:
        raise ValueError("gate-valid historical carrier census mismatch")
    carried_occurrences = sum(observed_carriers.values())
    if carried_occurrences - len(gate_valid_history) != 1:
        raise ValueError("historical exclusion overlap count mismatch")

    by_stratum: Dict[
        str, list[Tuple[str, str, str, GameDefinition, Dict[str, Any]]]
    ] = defaultdict(list)
    for orbit_hash in sorted(fresh_gate_valid):
        definition = representatives[orbit_hash]
        stratum = four_by_four_stratum(definition)
        stratum_id = _stratum_id(stratum)
        exact_hash = definition_hash(definition)
        score = _selection_score(stratum, orbit_hash)
        by_stratum[stratum_id].append(
            (score, orbit_hash, exact_hash, definition, stratum)
        )
    for candidates in by_stratum.values():
        candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    observed_counts = {
        stratum_id: len(candidates)
        for stratum_id, candidates in sorted(by_stratum.items())
    }
    if observed_counts != _EXPECTED_STRATUM_COUNTS:
        raise ValueError("eligible 4x4 per-stratum census mismatch")

    eligible_pool_payload = []
    eligible_pools = []
    cases = []
    selection_payload = []
    for stratum_id, stratum in _ordered_strata():
        candidates = by_stratum[stratum_id]
        ordered_identities = [
            {
                "selection_score": candidate[0],
                "d4_canonical_hash": candidate[1],
                "definition_hash": candidate[2],
            }
            for candidate in candidates
        ]
        pool_root = _domain_digest(_STRATUM_POOL_DOMAIN, ordered_identities)
        score, orbit_hash, exact_hash, definition, selected_stratum = candidates[0]
        if mechanical_json(definition) != canonicalize_d4(definition).mechanical_json:
            raise ValueError("selected 4x4 definition is not D4 canonical")
        proof = four_by_four_state_proof(definition)
        case_id = "four-by-four-calibration-v1-" + stratum_id
        case = {
            "case_id": case_id,
            "stratum_id": stratum_id,
            "stratum": _json_copy(selected_stratum, "selected stratum"),
            "selection_rank": 1,
            "selection_score": score,
            "definition_hash": exact_hash,
            "d4_canonical_hash": orbit_hash,
            "vector_count": len(definition.role(Player.B).action.vectors),
            "definition": definition.to_dict(),
            "state_bound": proof["state_bound"],
        }
        case["case_fingerprint"] = _case_fingerprint(case)
        cases.append(case)
        selection_payload.append(
            {
                "stratum_id": stratum_id,
                "d4_canonical_hash": orbit_hash,
                "definition_hash": exact_hash,
            }
        )
        eligible_pool_payload.append(
            {
                "stratum_id": stratum_id,
                "stratum": stratum,
                "ordered_candidate_identities": ordered_identities,
            }
        )
        eligible_pools.append(
            {
                "stratum_id": stratum_id,
                "stratum": stratum,
                "eligible_count": len(candidates),
                "ordered_candidate_root": pool_root,
                "quota": FOUR_BY_FOUR_QUOTA_PER_STRATUM,
                "selected_case_ids": [case_id],
            }
        )
    if len(cases) != FOUR_BY_FOUR_CASE_COUNT:
        raise ValueError("selected 4x4 case census mismatch")
    if (
        len({case["definition_hash"] for case in cases}) != len(cases)
        or len({case["d4_canonical_hash"] for case in cases}) != len(cases)
        or any(case["d4_canonical_hash"] in historical for case in cases)
    ):
        raise ValueError("selected 4x4 identities are not unique and fresh")
    first_counts = defaultdict(int)
    for case in cases:
        first_counts[case["definition"]["first_player"]] += 1
    if dict(first_counts) != {"A": 16, "B": 16}:
        raise ValueError("fixed 4x4 first-player balance mismatch")
    fixed_bound = sum(case["state_bound"] for case in cases)
    if fixed_bound != FOUR_BY_FOUR_FIXED_CORPUS_STATE_BOUND:
        raise ValueError("fixed 4x4 corpus state-bound sum mismatch")

    snapshot = {
        "snapshot_version": 1,
        "history_projection_root": history_projection_root,
        "census": {
            "raw_definition_count": FOUR_BY_FOUR_RAW_DEFINITION_COUNT,
            "raw_d4_orbit_count": len(raw_hashes),
            "gate_valid_d4_orbit_count": len(gate_valid_hashes),
            "historical_max8_d4_count": len(historical),
            "native_historical_d4_count": len(native_history),
            "historical_gate_valid_exclusion_count": len(gate_valid_history),
            "historical_gate_invalid_intersection_count": len(
                gate_invalid_history
            ),
            "fresh_gate_valid_d4_orbit_count": len(fresh_gate_valid),
            "stratum_count": len(by_stratum),
            "minimum_eligible_d4_orbits_per_stratum": min(
                observed_counts.values()
            ),
            "maximum_eligible_d4_orbits_per_stratum": max(
                observed_counts.values()
            ),
            "quota_per_stratum": FOUR_BY_FOUR_QUOTA_PER_STRATUM,
            "selected_case_count": len(cases),
            "historical_collision_count": 0,
        },
        "state_proof": {
            "A_first_state_bound": FOUR_BY_FOUR_A_FIRST_STATE_BOUND,
            "B_first_state_bound": FOUR_BY_FOUR_B_FIRST_STATE_BOUND,
            "exact_max_states": FOUR_BY_FOUR_EXACT_MAX_STATES,
            "A_first_case_count": first_counts["A"],
            "B_first_case_count": first_counts["B"],
            "fixed_corpus_state_bound": fixed_bound,
        },
        "history_exclusions": {
            "native_history_d4_root": _domain_digest(
                _NATIVE_HISTORY_D4_DOMAIN, sorted(native_history)
            ),
            "gate_valid_history_d4_root": _domain_digest(
                _GATE_VALID_HISTORY_D4_DOMAIN, sorted(gate_valid_history)
            ),
            "gate_valid_exclusion_d4_hashes": sorted(gate_valid_history),
            "gate_valid_source_occurrence_count": carried_occurrences,
            "gate_valid_overlap_count": carried_occurrences
            - len(gate_valid_history),
            "gate_valid_carrier_count": len(carrier_records),
            "gate_valid_carriers": carrier_records,
            "plan0010_manifest_max8_intersection_count": 0,
        },
        "raw_d4_root": _domain_digest(_RAW_D4_DOMAIN, sorted(raw_hashes)),
        "gate_valid_d4_root": _domain_digest(
            _GATE_VALID_D4_DOMAIN, sorted(gate_valid_hashes)
        ),
        "fresh_gate_valid_d4_root": _domain_digest(
            _FRESH_GATE_VALID_D4_DOMAIN, sorted(fresh_gate_valid)
        ),
        "eligible_pool_root": _domain_digest(
            _ELIGIBLE_POOLS_DOMAIN, eligible_pool_payload
        ),
        "selection_fingerprint": _domain_digest(
            _SELECTION_FINGERPRINT_DOMAIN, selection_payload
        ),
        "eligible_pools": eligible_pools,
        "cases": cases,
    }
    return _canonical_bytes(snapshot).decode("utf-8")


def build_four_by_four_planning_snapshot(
    historical_projection: Mapping[str, Any],
) -> Dict[str, Any]:
    """Reproduce the complete census and one-per-stratum blind selection."""

    historical_hashes = validate_four_by_four_closed_history_projection(
        historical_projection
    )
    source_items = tuple(
        (
            source["artifact"]["path"],
            tuple(source["max8_unique_d4_hashes"]),
        )
        for source in historical_projection["sources"]
    )
    snapshot = json.loads(
        _selection_snapshot_json(
            historical_projection["projection_root"],
            historical_hashes,
            source_items,
        )
    )
    frozen = (
        (
            "closed history projection root",
            FOUR_BY_FOUR_CLOSED_HISTORY_PROJECTION_ROOT,
            historical_projection["projection_root"],
        ),
        ("raw D4 root", FOUR_BY_FOUR_RAW_D4_ROOT, snapshot["raw_d4_root"]),
        (
            "gate-valid D4 root",
            FOUR_BY_FOUR_GATE_VALID_D4_ROOT,
            snapshot["gate_valid_d4_root"],
        ),
        (
            "fresh gate-valid D4 root",
            FOUR_BY_FOUR_FRESH_GATE_VALID_D4_ROOT,
            snapshot["fresh_gate_valid_d4_root"],
        ),
        (
            "native history D4 root",
            FOUR_BY_FOUR_NATIVE_HISTORY_D4_ROOT,
            snapshot["history_exclusions"]["native_history_d4_root"],
        ),
        (
            "gate-valid history D4 root",
            FOUR_BY_FOUR_GATE_VALID_HISTORY_D4_ROOT,
            snapshot["history_exclusions"]["gate_valid_history_d4_root"],
        ),
        (
            "eligible pool root",
            FOUR_BY_FOUR_ELIGIBLE_POOL_ROOT,
            snapshot["eligible_pool_root"],
        ),
        (
            "selection fingerprint",
            FOUR_BY_FOUR_SELECTION_FINGERPRINT,
            snapshot["selection_fingerprint"],
        ),
    )
    for label, expected, observed in frozen:
        if expected and observed != expected:
            raise ValueError("{} differs from frozen value".format(label))
    return _json_copy(snapshot, "4x4 planning snapshot")


def validate_four_by_four_planning_snapshot(
    value: Any, historical_projection: Mapping[str, Any]
) -> Tuple[Dict[str, Any], ...]:
    """Publicly reconstruct every count, root, pool, and selected definition."""

    expected = build_four_by_four_planning_snapshot(historical_projection)
    detached = _json_copy(value, "4x4 planning snapshot")
    if _canonical_bytes(detached) != _canonical_bytes(expected):
        raise ValueError("4x4 planning snapshot differs from reconstruction")
    return tuple(_json_copy(case, "4x4 selected case") for case in expected["cases"])


def _validate_manifest_provenance(value: Any) -> Dict[str, Any]:
    top = _exact_keys(
        value,
        (
            "freezer_git_commit",
            "freezer_git_dirty",
            "created_at",
            "protocol_id",
            "protocol_plan",
            "protocol_fingerprints",
            "executable_fingerprints",
            "closed_history",
            "selection_inputs",
            "independent_review",
        ),
        "4x4 manifest provenance",
    )
    commit = top["freezer_git_commit"]
    if (
        not isinstance(commit, str)
        or len(commit) != 40
        or any(character not in "0123456789abcdef" for character in commit)
    ):
        raise ValueError("4x4 freezer commit must be a full lowercase Git SHA")
    if top["freezer_git_dirty"] is not False:
        raise ValueError("4x4 freezer must record a clean Git state")
    created_at = top["created_at"]
    if not isinstance(created_at, str) or not created_at.endswith("Z"):
        raise ValueError("4x4 provenance created_at must be UTC")
    if top["protocol_id"] != FOUR_BY_FOUR_CALIBRATION_MANIFEST_PROTOCOL_ID:
        raise ValueError("4x4 manifest protocol identifier mismatch")
    plan = _exact_keys(
        top["protocol_plan"],
        ("path", "sha256", "git_blob_sha"),
        "4x4 protocol plan",
    )
    if plan["path"] != _PLAN_PATH:
        raise ValueError("4x4 protocol plan path mismatch")
    plan_sha = _require_sha256(plan["sha256"], "4x4 protocol plan SHA-256")
    git_blob_sha = plan["git_blob_sha"]
    if (
        not isinstance(git_blob_sha, str)
        or len(git_blob_sha) != 40
        or any(character not in "0123456789abcdef" for character in git_blob_sha)
    ):
        raise ValueError("4x4 protocol plan Git blob must be lowercase SHA-1")
    protocol_fingerprints = top["protocol_fingerprints"]
    if (
        not isinstance(protocol_fingerprints, Mapping)
        or set(protocol_fingerprints) != {_PLAN_PATH}
        or protocol_fingerprints.get(_PLAN_PATH) != plan_sha
    ):
        raise ValueError("4x4 protocol fingerprints mismatch the plan")
    executable_fingerprints = top["executable_fingerprints"]
    if (
        not isinstance(executable_fingerprints, Mapping)
        or set(executable_fingerprints)
        != set(FOUR_BY_FOUR_MANIFEST_EXECUTABLE_FINGERPRINT_PATHS)
        or list(executable_fingerprints)
        != list(FOUR_BY_FOUR_MANIFEST_EXECUTABLE_FINGERPRINT_PATHS)
    ):
        raise ValueError("4x4 executable fingerprint closure mismatch")
    normalized_executables = {
        path: _require_sha256(
            executable_fingerprints[path], "4x4 executable fingerprint"
        )
        for path in FOUR_BY_FOUR_MANIFEST_EXECUTABLE_FINGERPRINT_PATHS
    }
    history = _exact_keys(
        top["closed_history"],
        (
            "projection_root",
            "ledger_path",
            "ledger_sha256",
            "ledger_bytes",
            "ledger_bundle_root",
            "plan0010_manifest_path",
            "plan0010_manifest_sha256",
            "plan0010_manifest_bytes",
        ),
        "4x4 closed-history provenance",
    )
    expected_history = {
        "projection_root": FOUR_BY_FOUR_CLOSED_HISTORY_PROJECTION_ROOT,
        "ledger_path": FOUR_BY_FOUR_LEDGER_PATH,
        "ledger_sha256": FOUR_BY_FOUR_LEDGER_SHA256,
        "ledger_bytes": FOUR_BY_FOUR_LEDGER_BYTES,
        "ledger_bundle_root": FOUR_BY_FOUR_LEDGER_BUNDLE_ROOT,
        "plan0010_manifest_path": FOUR_BY_FOUR_PLAN0010_MANIFEST_PATH,
        "plan0010_manifest_sha256": FOUR_BY_FOUR_PLAN0010_MANIFEST_SHA256,
        "plan0010_manifest_bytes": FOUR_BY_FOUR_PLAN0010_MANIFEST_BYTES,
    }
    if _canonical_bytes(history) != _canonical_bytes(expected_history):
        raise ValueError("4x4 closed-history provenance mismatch")
    if top["selection_inputs"] != _SELECTION_INPUT_ATTESTATION:
        raise ValueError("4x4 selection input attestation mismatch")
    if top["independent_review"] != "PASSED":
        raise ValueError("4x4 manifest requires passed independent review")
    return {
        "freezer_git_commit": commit,
        "freezer_git_dirty": False,
        "created_at": created_at,
        "protocol_id": FOUR_BY_FOUR_CALIBRATION_MANIFEST_PROTOCOL_ID,
        "protocol_plan": {
            "path": _PLAN_PATH,
            "sha256": plan_sha,
            "git_blob_sha": git_blob_sha,
        },
        "protocol_fingerprints": {_PLAN_PATH: plan_sha},
        "executable_fingerprints": normalized_executables,
        "closed_history": expected_history,
        "selection_inputs": _SELECTION_INPUT_ATTESTATION,
        "independent_review": "PASSED",
    }


def _require_frozen_manifest_roots() -> None:
    roots = {
        "closed history projection root": FOUR_BY_FOUR_CLOSED_HISTORY_PROJECTION_ROOT,
        "raw D4 root": FOUR_BY_FOUR_RAW_D4_ROOT,
        "gate-valid D4 root": FOUR_BY_FOUR_GATE_VALID_D4_ROOT,
        "fresh gate-valid D4 root": FOUR_BY_FOUR_FRESH_GATE_VALID_D4_ROOT,
        "native history D4 root": FOUR_BY_FOUR_NATIVE_HISTORY_D4_ROOT,
        "gate-valid history D4 root": FOUR_BY_FOUR_GATE_VALID_HISTORY_D4_ROOT,
        "eligible pool root": FOUR_BY_FOUR_ELIGIBLE_POOL_ROOT,
        "selection fingerprint": FOUR_BY_FOUR_SELECTION_FINGERPRINT,
    }
    for label, value in roots.items():
        if not value:
            raise ValueError(
                "4x4 manifest construction is disabled until {} is frozen".format(
                    label
                )
            )
        _require_sha256(value, label)


def _construct_four_by_four_calibration_manifest(
    historical_projection: Mapping[str, Any],
    provenance: Mapping[str, Any],
) -> Dict[str, Any]:
    _require_frozen_manifest_roots()
    snapshot = build_four_by_four_planning_snapshot(historical_projection)
    proof = build_four_by_four_state_bound_proof()
    return {
        "manifest_id": FOUR_BY_FOUR_CALIBRATION_MANIFEST_ID,
        "manifest_version": FOUR_BY_FOUR_CALIBRATION_MANIFEST_VERSION,
        "protocol_id": FOUR_BY_FOUR_CALIBRATION_MANIFEST_PROTOCOL_ID,
        "status": "FROZEN",
        "source": {
            "closed_history_projection_root": historical_projection[
                "projection_root"
            ],
            "closed_ledger_bundle_root": FOUR_BY_FOUR_LEDGER_BUNDLE_ROOT,
            "plan0010_manifest_sha256": FOUR_BY_FOUR_PLAN0010_MANIFEST_SHA256,
        },
        "selection_protocol": {
            "outcome_blind": True,
            "case_membership_outcome_fields_consulted": False,
            "selected_outcomes_computed": False,
            "source_orientation": "canonical D4 mechanical orientation",
            "membership": "one lowest domain-separated definition-only identity score per ordered stratum",
            "selection_order": "selection score, then D4 hash, then exact definition hash",
            "quota_per_stratum": FOUR_BY_FOUR_QUOTA_PER_STRATUM,
            "raw_d4_root": snapshot["raw_d4_root"],
            "gate_valid_d4_root": snapshot["gate_valid_d4_root"],
            "fresh_gate_valid_d4_root": snapshot[
                "fresh_gate_valid_d4_root"
            ],
            "eligible_pool_root": snapshot["eligible_pool_root"],
            "selection_fingerprint": snapshot["selection_fingerprint"],
        },
        "census": _json_copy(snapshot["census"], "4x4 manifest census"),
        "history_exclusions": _json_copy(
            snapshot["history_exclusions"], "4x4 manifest history exclusions"
        ),
        "state_bound_proof": proof,
        "eligible_pools": _json_copy(
            snapshot["eligible_pools"], "4x4 manifest eligible pools"
        ),
        "cases": _json_copy(snapshot["cases"], "4x4 manifest cases"),
        "provenance": _json_copy(provenance, "4x4 manifest provenance"),
    }


def build_four_by_four_calibration_manifest(
    historical_projection: Mapping[str, Any], provenance: Mapping[str, Any]
) -> Dict[str, Any]:
    """Build the deterministic production-shaped manifest without writing it."""

    validate_four_by_four_closed_history_projection(historical_projection)
    normalized_provenance = _validate_manifest_provenance(provenance)
    manifest = _construct_four_by_four_calibration_manifest(
        historical_projection, normalized_provenance
    )
    validate_four_by_four_calibration_manifest(manifest, historical_projection)
    return _json_copy(manifest, "4x4 calibration manifest")


def validate_four_by_four_calibration_manifest(
    value: Any, historical_projection: Mapping[str, Any]
) -> Tuple[Dict[str, Any], ...]:
    """Reconstruct the complete outcome-free manifest from its closed source."""

    top = _exact_keys(
        value,
        (
            "manifest_id",
            "manifest_version",
            "protocol_id",
            "status",
            "source",
            "selection_protocol",
            "census",
            "history_exclusions",
            "state_bound_proof",
            "eligible_pools",
            "cases",
            "provenance",
        ),
        "4x4 calibration manifest",
    )
    if top["manifest_id"] != FOUR_BY_FOUR_CALIBRATION_MANIFEST_ID:
        raise ValueError("4x4 manifest identifier mismatch")
    _require_int(
        top["manifest_version"],
        FOUR_BY_FOUR_CALIBRATION_MANIFEST_VERSION,
        "4x4 manifest version",
    )
    if (
        top["protocol_id"] != FOUR_BY_FOUR_CALIBRATION_MANIFEST_PROTOCOL_ID
        or top["status"] != "FROZEN"
    ):
        raise ValueError("4x4 manifest protocol or status mismatch")
    validate_four_by_four_closed_history_projection(historical_projection)
    normalized_provenance = _validate_manifest_provenance(top["provenance"])
    expected = _construct_four_by_four_calibration_manifest(
        historical_projection, normalized_provenance
    )
    if _canonical_bytes(top) != _canonical_bytes(expected):
        raise ValueError("4x4 calibration manifest differs from reconstruction")
    validate_four_by_four_state_bound_proof(top["state_bound_proof"])
    return tuple(_json_copy(case, "4x4 manifest case") for case in top["cases"])
