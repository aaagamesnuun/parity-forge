"""Outcome-free Plan-0015 identity projection over the fixed history sources.

The adapter accepts only the already-classified cutoff witness, the 66 frozen
legacy JSON blobs, and all seven canonical synthetic definition wires.
It emits identities and source provenance; raw definitions and surrounding
experiment fields never cross the returned boundary.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from typing import Any, Dict, Mapping, Sequence, Tuple

from . import history_cutoff, history_pins as legacy, wire_identity as wire


HISTORY_IDENTITY_PROJECTION_VERSION_V1 = 1
HISTORY_IDENTITY_PROJECTION_ID_V1 = "plan0015-complete-history-identity-v1"

HISTORY_UNIQUE_DEFINITION_COUNT_V1 = 1_179
HISTORY_UNIQUE_D4_COUNT_V1 = 1_175
HISTORY_UNIQUE_ROLE_NEUTRAL_COUNT_V1 = 1_175
HISTORY_SCHEMA_UNIQUE_COUNTS_V1 = ((1, 852), (2, 128), (3, 192), (4, 7))
HISTORY_DEFINITION_OCCURRENCE_COUNT_V1 = 2_250
HISTORY_MALFORMED_DEFINITION_LIKE_COUNT_V1 = 1
HISTORY_SOURCE_COUNT_V1 = 73

HISTORY_CARRIER_ROOT_V1 = (
    "51b7416d77ed78190d6c87ce626e0bda1af40f86a44941cd56d4daa00792c40f"
)
HISTORY_IDENTITY_ROOT_V1 = (
    "e26fbd0d5a0db4a6e1cf462e0d3bc16385a769c647b35bdfdcbe6fc573d26b93"
)
HISTORY_PROJECTION_ROOT_V1 = (
    "00973dcc6447697fae4639442bfe2fa93a5d0ff7c62f279688fa38dac1e2e3c9"
)

_CARRIER_DOMAIN_V1 = b"parity-forge:plan0015:history-source-carrier:v1\0"
_CARRIER_ROOT_DOMAIN_V1 = b"parity-forge:plan0015:history-source-carriers:v1\0"
_IDENTITY_ROOT_DOMAIN_V1 = b"parity-forge:plan0015:history-identities:v1\0"
_PROJECTION_ROOT_DOMAIN_V1 = b"parity-forge:plan0015:history-projection:v1\0"
_MAX_PROJECTION_JSON_NODES_V1 = 100_000
_MAX_PROJECTION_JSON_DEPTH_V1 = 16
_MAX_PROJECTION_BYTES_V1 = 2 * 1024 * 1024

_DEFINITION_REQUIRED_KEYS = frozenset(
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
_FORBIDDEN_OUTPUT_KEYS = frozenset(
    (
        "action",
        "actions",
        "agent",
        "candidate",
        "definition",
        "metric",
        "outcome",
        "principal_variation",
        "result",
        "results",
        "score",
        "status",
        "timing",
        "trace",
        "winner",
    )
)

# The producer requires the seven canonical source wires; no constant-only mode.
PLAN0012_SYNTHETIC_IDENTITIES_V1 = legacy.PLAN0012_SYNTHETIC_FIXTURE_IDENTITIES_V1


class HistoryIdentityError(ValueError):
    """The history source or detached identity projection failed closed."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _digest(domain: bytes, value: Any) -> str:
    return hashlib.sha256(domain + _canonical_bytes(value)).hexdigest()


def _expected_cutoff_classification() -> Dict[str, Any]:
    return {
        "history_cutoff_version": 1,
        "cutoff_commit": history_cutoff.HISTORY_CUTOFF_COMMIT_V1,
        "cutoff_tree": history_cutoff.HISTORY_CUTOFF_TREE_V1,
        "json_path_count": history_cutoff.HISTORY_JSON_PATH_COUNT_V1,
        "json_path_root": history_cutoff.HISTORY_JSON_PATH_ROOT_V1,
        "legacy": {
            "classification": "IDENTITY_SOURCE_SCAN_REQUIRED",
            "cutoff_commit": history_cutoff.LEGACY_HISTORY_CUTOFF_COMMIT_V1,
            "cutoff_tree": history_cutoff.LEGACY_HISTORY_CUTOFF_TREE_V1,
            "path_count": history_cutoff.LEGACY_HISTORY_PATH_COUNT_V1,
            "path_root": history_cutoff.LEGACY_HISTORY_PATH_ROOT_V1,
        },
        "plan0013": {
            "classification": "OLD_SIX_SEMANTIC_REGION_ALREADY_EXCLUDED",
            "path_count": history_cutoff.PLAN0013_PATH_COUNT_V1,
            "subtree": history_cutoff.PLAN0013_SUBTREE_V1,
            "artifacts_opened": 0,
        },
        "plan0014": {
            "classification": "DEFINITION_FREE_RECONSTRUCTION_EVIDENCE",
            "path_count": history_cutoff.PLAN0014_PATH_COUNT_V1,
            "subtree": history_cutoff.PLAN0014_SUBTREE_V1,
            "artifacts_opened": 0,
        },
    }


def _require_cutoff_classification(value: Any) -> Dict[str, Any]:
    if type(value) is not dict:
        raise TypeError("cutoff classification must be an exact object")
    _validate_json_tree(value)
    try:
        entry = _canonical_bytes(value)
        detached = json.loads(entry)
    except (TypeError, ValueError) as error:
        raise HistoryIdentityError(
            "cutoff classification must be finite JSON"
        ) from error
    if entry != _canonical_bytes(_expected_cutoff_classification()):
        raise HistoryIdentityError("HISTORY_PROJECTION_INCOMPLETE: cutoff mismatch")
    if entry != _canonical_bytes(value):
        raise HistoryIdentityError("cutoff classification changed during validation")
    return detached


def _require_sha256(value: Any, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise HistoryIdentityError("{} must be a lowercase SHA-256".format(label))
    return value


def _require_nonnegative_int(value: Any, label: str) -> int:
    if type(value) is not int or value < 0:
        raise HistoryIdentityError("{} must be a nonnegative integer".format(label))
    return value


def _exact_keys(value: Any, expected: Sequence[str], label: str) -> Dict[str, Any]:
    if type(value) is not dict:
        raise TypeError("{} must be an exact object".format(label))
    if set(value) != set(expected):
        raise HistoryIdentityError("{} keys mismatch".format(label))
    return value


def _validate_json_tree(value: Any) -> None:
    active = set()
    nodes = 0
    string_bytes = 0

    def visit(item: Any, depth: int) -> None:
        nonlocal nodes, string_bytes
        nodes += 1
        if nodes > _MAX_PROJECTION_JSON_NODES_V1:
            raise HistoryIdentityError("history projection exceeds JSON node cap")
        if depth > _MAX_PROJECTION_JSON_DEPTH_V1:
            raise HistoryIdentityError("history projection exceeds JSON depth cap")
        if type(item) is str:
            if len(item) > 4096:
                raise HistoryIdentityError("history string exceeds byte cap")
            string_bytes += len(item.encode("utf-8"))
            if string_bytes > _MAX_PROJECTION_BYTES_V1:
                raise HistoryIdentityError("history projection exceeds byte cap")
            return
        if type(item) is int:
            if item.bit_length() > 64:
                raise HistoryIdentityError("history integer exceeds bound")
            return
        if item is None or type(item) is bool:
            return
        if type(item) not in (dict, list):
            raise TypeError("history projection must contain exact JSON values")
        identity = id(item)
        if identity in active:
            raise HistoryIdentityError("history projection cannot contain a cycle")
        active.add(identity)
        try:
            if type(item) is dict:
                if any(type(key) is not str for key in item):
                    raise TypeError("history projection keys must be strings")
                for key, child in item.items():
                    visit(key, depth + 1)
                    visit(child, depth + 1)
            else:
                for child in item:
                    visit(child, depth + 1)
        finally:
            active.remove(identity)

    visit(value, 0)
    if len(_canonical_bytes(value)) > _MAX_PROJECTION_BYTES_V1:
        raise HistoryIdentityError("history projection exceeds byte cap")


def role_neutral_definition_hash_v1(value: Mapping[str, Any]) -> str:
    """Canonical D4/role/alpha identity of a strict wire definition."""
    return wire.role_neutral_definition_hash_v1(value)


def _strict_json(raw: bytes) -> Any:
    def object_pairs(pairs):
        result = {}
        for key, child in pairs:
            if key in result:
                raise HistoryIdentityError("duplicate JSON key")
            result[key] = child
        return result

    def finite_float(token):
        value = float(token)
        if not math.isfinite(value):
            raise HistoryIdentityError("nonfinite JSON number")
        return value

    def invalid_constant(token):
        raise HistoryIdentityError("nonfinite JSON constant")

    return json.loads(
        raw.decode("utf-8"), object_pairs_hook=object_pairs,
        parse_float=finite_float, parse_constant=invalid_constant,
    )


def _authenticate_sources(value: Any, inventory: Sequence[Tuple[str, str, int]]):
    if type(value) is not dict or any(type(key) is not str for key in value):
        raise TypeError("source bytes must be an exact string-keyed object")
    snapshot = dict(value)
    if sorted(snapshot) != [row[0] for row in inventory]:
        raise HistoryIdentityError("HISTORY_PROJECTION_INCOMPLETE: path set mismatch")
    for source, digest, byte_count in inventory:
        raw = snapshot[source]
        if type(raw) is not bytes:
            raise TypeError("source values must be exact immutable bytes")
        if len(raw) != byte_count:
            raise HistoryIdentityError("source byte count mismatch")
        if hashlib.sha256(raw).hexdigest() != digest:
            raise HistoryIdentityError("source SHA-256 mismatch")
    return snapshot


def _scan_document(value: Any, source_id: str):
    definitions, malformed, exact_refs, d4_refs = [], [], [], []

    def visit(item, pointer):
        if type(item) is dict:
            if _DEFINITION_REQUIRED_KEYS <= set(item):
                try:
                    definitions.append(wire.normalize_definition_v1(item))
                except (TypeError, ValueError):
                    malformed.append(source_id + "#" + pointer)
                return
            for key in sorted(item):
                child = item[key]
                if key.endswith("definition_hash") and child is not None:
                    exact_refs.append(_require_sha256(child, "definition reference"))
                if key.endswith("d4_canonical_hash"):
                    d4_refs.append(_require_sha256(child, "D4 reference"))
                visit(child, pointer + "/" + key.replace("~", "~0").replace("/", "~1"))
        elif type(item) is list:
            for index, child in enumerate(item):
                visit(child, pointer + "/" + str(index))

    visit(value, "")
    return definitions, malformed, exact_refs, d4_refs


def _carrier_record(source: Mapping[str, Any]) -> Dict[str, Any]:
    payload = {
        "carrier_id": source["carrier_id"],
        "carrier_kind": source["carrier_kind"],
        "source_digest": source["source_digest"],
        "source_bytes": source["source_bytes"],
        "definition_occurrence_count": source["definition_occurrence_count"],
        "malformed_definition_like_count": source[
            "malformed_definition_like_count"
        ],
    }
    payload["carrier_identity"] = _digest(_CARRIER_DOMAIN_V1, payload)
    return payload


def _identity_rows(definitions_by_carrier):
    accumulated = {}
    for carrier_id, carrier_identity, definitions in definitions_by_carrier:
        for definition in definitions:
            exact_hash = hashlib.sha256(_canonical_bytes(definition)).hexdigest()
            if exact_hash not in accumulated:
                accumulated[exact_hash] = {
                    "definition_hash": exact_hash,
                    "d4_canonical_hash": wire.d4_definition_hash_v1(definition),
                    "role_neutral_hash": role_neutral_definition_hash_v1(definition),
                    "schema_version": definition["schema_version"],
                    "occurrence_count": 0,
                    "source_carrier_ids": set(),
                    "source_carrier_identities": set(),
                }
            record = accumulated[exact_hash]
            record["occurrence_count"] += 1
            record["source_carrier_ids"].add(carrier_id)
            record["source_carrier_identities"].add(carrier_identity)
    rows = []
    for _, record in sorted(accumulated.items()):
        row = dict(record)
        row["source_carrier_ids"] = sorted(record["source_carrier_ids"])
        row["source_carrier_identities"] = sorted(record["source_carrier_identities"])
        rows.append(row)
    return rows


def _prior_projection_root(carriers, synthetic):
    """Reconstruct both frozen parent identities from extracted identities only."""
    def digest(kind, value):
        return _digest(
            ("parity-forge:plan0013:" + kind + ":v1\0").encode("ascii"), value
        )
    normalized = []
    for carrier in carriers:
        row = dict(carrier)
        row["carrier_root"] = digest("identity-carrier", row)
        normalized.append(row)
    exact = sorted({
        pair["definition_hash"] for row in normalized for pair in row["identity_pairs"]
    })
    d4 = sorted({
        pair["d4_canonical_hash"] for row in normalized for pair in row["identity_pairs"]
    })
    metadata = [
        {key: row[key] for key in
         ("carrier_id", "carrier_kind", "source_digest", "source_bytes")}
        for row in normalized
    ]
    result = {
        "projection_version": 1,
        "projection_id": (
            legacy.ATLAS_SYNTHETIC_PROJECTION_ID_V1 if synthetic
            else legacy.ATLAS_HISTORY_PROJECTION_ID_V1
        ),
        "exposure_kind": (
            "SYNTHETIC_EVALUATOR_FIXTURE_EXPOSURE" if synthetic
            else "PRIOR_GAMEPLAY_EXPOSURE"
        ),
        "cutoff_id": (
            legacy.ATLAS_SYNTHETIC_CUTOFF_ID_V1 if synthetic
            else legacy.ATLAS_HISTORY_CUTOFF_ID_V1
        ),
        "source_attestation_root": digest("source-attestation", metadata),
        "source_count": len(normalized),
        "definition_occurrence_count": sum(
            row["definition_occurrence_count"] for row in normalized
        ),
        "malformed_definition_like_count": sum(
            row["malformed_definition_like_count"] for row in normalized
        ),
        "unique_definition_count": len(exact),
        "unique_definition_hashes": exact,
        "unique_definition_root": digest("identity-exact", exact),
        "unique_d4_count": len(d4),
        "unique_d4_hashes": d4,
        "unique_d4_root": digest("identity-d4", d4),
        "carriers": normalized,
    }
    root = digest("identity-projection", result)
    expected = (
        legacy.ATLAS_SYNTHETIC_PROJECTION_ROOT_V1 if synthetic
        else legacy.ATLAS_HISTORY_PROJECTION_ROOT_V1
    )
    if root != expected:
        raise HistoryIdentityError("HISTORY_PROJECTION_INCOMPLETE: parent root mismatch")
    return root


def _assert_output_boundary(value: Any) -> None:
    def visit(item: Any) -> None:
        if type(item) is dict:
            if set(item) & _FORBIDDEN_OUTPUT_KEYS:
                raise AssertionError("outcome-bearing field crossed identity boundary")
            for child in item.values():
                visit(child)
        elif type(item) is list:
            for child in item:
                visit(child)

    visit(value)


def validate_history_identity_projection_v1(value: Any) -> Dict[str, Any]:
    """Strictly reconstruct, authenticate, and detach the fixed projection."""

    _validate_json_tree(value)
    entry = _canonical_bytes(value)
    detached = json.loads(entry)
    top = _exact_keys(
        detached,
        (
            "projection_version",
            "projection_id",
            "cutoff",
            "parents",
            "source_count",
            "definition_occurrence_count",
            "malformed_definition_like_count",
            "unique_definition_count",
            "unique_d4_count",
            "unique_role_neutral_count",
            "schema_unique_counts",
            "carriers",
            "carrier_root",
            "identities",
            "identity_root",
            "projection_root",
        ),
        "history identity projection",
    )
    if (
        type(top["projection_version"]) is not int
        or top["projection_version"] != HISTORY_IDENTITY_PROJECTION_VERSION_V1
        or type(top["projection_id"]) is not str
        or top["projection_id"] != HISTORY_IDENTITY_PROJECTION_ID_V1
    ):
        raise HistoryIdentityError("history identity projection version mismatch")
    _require_cutoff_classification(top["cutoff"])
    parents = _exact_keys(
        top["parents"],
        (
            "legacy_projection_root",
            "synthetic_projection_root",
            "synthetic_benchmark_root",
        ),
        "history projection parents",
    )
    if parents != {
        "legacy_projection_root": legacy.ATLAS_HISTORY_PROJECTION_ROOT_V1,
        "synthetic_projection_root": legacy.ATLAS_SYNTHETIC_PROJECTION_ROOT_V1,
        "synthetic_benchmark_root": legacy.PLAN0012_SYNTHETIC_BENCHMARK_ROOT_V1,
    }:
        raise HistoryIdentityError("history parent projection mismatch")

    if type(top["carriers"]) is not list:
        raise TypeError("history carriers must be an array")
    carriers = []
    carrier_identity_by_id = {}
    for index, raw in enumerate(top["carriers"]):
        carrier = _exact_keys(
            raw,
            (
                "carrier_id",
                "carrier_kind",
                "source_digest",
                "source_bytes",
                "definition_occurrence_count",
                "malformed_definition_like_count",
                "carrier_identity",
            ),
            "history carrier[{}]".format(index),
        )
        if type(carrier["carrier_id"]) is not str or not carrier["carrier_id"]:
            raise HistoryIdentityError("history carrier ID must be a string")
        if type(carrier["carrier_kind"]) is not str or not carrier["carrier_kind"]:
            raise HistoryIdentityError("history carrier kind must be a string")
        _require_sha256(carrier["source_digest"], "history carrier source digest")
        _require_nonnegative_int(carrier["source_bytes"], "history carrier bytes")
        _require_nonnegative_int(
            carrier["definition_occurrence_count"],
            "history carrier definition occurrence count",
        )
        _require_nonnegative_int(
            carrier["malformed_definition_like_count"],
            "history carrier malformed count",
        )
        unsigned = dict(carrier)
        observed_identity = unsigned.pop("carrier_identity")
        if _require_sha256(
            observed_identity, "history carrier identity"
        ) != _digest(_CARRIER_DOMAIN_V1, unsigned):
            raise HistoryIdentityError("history carrier identity mismatch")
        carriers.append(carrier)
        carrier_identity_by_id[carrier["carrier_id"]] = observed_identity
    carrier_ids = [carrier["carrier_id"] for carrier in carriers]
    if carrier_ids != sorted(set(carrier_ids)):
        raise HistoryIdentityError("history carrier IDs must be unique and ordered")
    if len(carrier_identity_by_id) != len(carriers):
        raise HistoryIdentityError("history carrier identity map is incomplete")

    if type(top["identities"]) is not list:
        raise TypeError("history identities must be an array")
    identities = []
    for index, raw in enumerate(top["identities"]):
        row = _exact_keys(
            raw,
            (
                "definition_hash",
                "d4_canonical_hash",
                "role_neutral_hash",
                "schema_version",
                "occurrence_count",
                "source_carrier_ids",
                "source_carrier_identities",
            ),
            "history identity[{}]".format(index),
        )
        _require_sha256(row["definition_hash"], "history exact definition hash")
        _require_sha256(row["d4_canonical_hash"], "history D4 hash")
        _require_sha256(row["role_neutral_hash"], "history role-neutral hash")
        if type(row["schema_version"]) is not int or row["schema_version"] not in (
            1,
            2,
            3,
            4,
        ):
            raise HistoryIdentityError("history schema version mismatch")
        occurrence_count = _require_nonnegative_int(
            row["occurrence_count"], "history identity occurrence count"
        )
        if type(row["source_carrier_ids"]) is not list or any(
            type(item) is not str for item in row["source_carrier_ids"]
        ):
            raise TypeError("history source carrier IDs must be a string array")
        if type(row["source_carrier_identities"]) is not list or any(
            type(item) is not str for item in row["source_carrier_identities"]
        ):
            raise TypeError("history source carrier identities must be a string array")
        source_ids = row["source_carrier_ids"]
        source_identities = row["source_carrier_identities"]
        if (
            not source_ids
            or source_ids != sorted(set(source_ids))
            or source_identities != sorted(set(source_identities))
            or occurrence_count < len(source_ids)
            or any(item not in carrier_identity_by_id for item in source_ids)
            or sorted(carrier_identity_by_id[item] for item in source_ids)
            != source_identities
        ):
            raise HistoryIdentityError("history source carrier linkage mismatch")
        identities.append(row)
    exact_hashes = [row["definition_hash"] for row in identities]
    if exact_hashes != sorted(set(exact_hashes)):
        raise HistoryIdentityError("history exact identities must be unique and ordered")

    schema_counts = Counter(row["schema_version"] for row in identities)
    expected_schema_rows = [
        {"schema_version": version, "unique_definition_count": count}
        for version, count in sorted(schema_counts.items())
    ]
    if top["schema_unique_counts"] != expected_schema_rows:
        raise HistoryIdentityError("history schema census mismatch")
    observed_scalars = (
        len(carriers),
        sum(row["definition_occurrence_count"] for row in carriers),
        sum(row["malformed_definition_like_count"] for row in carriers),
        len(identities),
        len({row["d4_canonical_hash"] for row in identities}),
        len({row["role_neutral_hash"] for row in identities}),
    )
    scalar_keys = (
        "source_count",
        "definition_occurrence_count",
        "malformed_definition_like_count",
        "unique_definition_count",
        "unique_d4_count",
        "unique_role_neutral_count",
    )
    for key, observed in zip(scalar_keys, observed_scalars):
        if _require_nonnegative_int(top[key], key) != observed:
            raise HistoryIdentityError("{} mismatch".format(key))
    if sum(row["occurrence_count"] for row in identities) != top[
        "definition_occurrence_count"
    ]:
        raise HistoryIdentityError("history identity occurrence total mismatch")

    if _require_sha256(top["carrier_root"], "history carrier root") != _digest(
        _CARRIER_ROOT_DOMAIN_V1, carriers
    ):
        raise HistoryIdentityError("history carrier root mismatch")
    if _require_sha256(top["identity_root"], "history identity root") != _digest(
        _IDENTITY_ROOT_DOMAIN_V1, identities
    ):
        raise HistoryIdentityError("history identity root mismatch")
    unsigned = dict(top)
    projection_root = unsigned.pop("projection_root")
    if _require_sha256(
        projection_root, "history projection root"
    ) != _digest(_PROJECTION_ROOT_DOMAIN_V1, unsigned):
        raise HistoryIdentityError("history projection root mismatch")
    if (
        top["carrier_root"] != HISTORY_CARRIER_ROOT_V1
        or top["identity_root"] != HISTORY_IDENTITY_ROOT_V1
        or projection_root != HISTORY_PROJECTION_ROOT_V1
        or observed_scalars
        != (
            HISTORY_SOURCE_COUNT_V1,
            HISTORY_DEFINITION_OCCURRENCE_COUNT_V1,
            HISTORY_MALFORMED_DEFINITION_LIKE_COUNT_V1,
            HISTORY_UNIQUE_DEFINITION_COUNT_V1,
            HISTORY_UNIQUE_D4_COUNT_V1,
            HISTORY_UNIQUE_ROLE_NEUTRAL_COUNT_V1,
        )
        or tuple(sorted(schema_counts.items())) != HISTORY_SCHEMA_UNIQUE_COUNTS_V1
    ):
        raise HistoryIdentityError("history projection differs from frozen roots")
    _assert_output_boundary(top)
    if entry != _canonical_bytes(value):
        raise HistoryIdentityError("history projection changed during validation")
    return json.loads(entry)


def _derive_history_identity_projection(
    cutoff_classification, legacy_raw_bytes_by_path, synthetic_raw_bytes_by_id
):
    cutoff = _require_cutoff_classification(cutoff_classification)
    raw_sources = _authenticate_sources(
        legacy_raw_bytes_by_path, legacy.ATLAS_HISTORY_INVENTORY_V1
    )
    fixture_inventory = tuple(
        (fixture_id, exact, byte_count)
        for fixture_id, exact, _, byte_count in PLAN0012_SYNTHETIC_IDENTITIES_V1
    )
    raw_fixtures = _authenticate_sources(synthetic_raw_bytes_by_id, fixture_inventory)
    all_definitions = []
    parent_carriers = [[], []]
    carriers = []
    exact_references, d4_references, malformed_locations = [], [], []
    for group, inventory, raw_by_id in (
        (0, legacy.ATLAS_HISTORY_INVENTORY_V1, raw_sources),
        (1, fixture_inventory, raw_fixtures),
    ):
        for source_id, digest, byte_count in inventory:
            document = _strict_json(raw_by_id[source_id])
            if group:
                definition = wire.normalize_definition_v1(document)
                if _canonical_bytes(definition) != raw_by_id[source_id]:
                    raise HistoryIdentityError("fixture wire is not canonical")
                definitions, malformed, exact_refs, d4_refs = [definition], [], [], []
            else:
                definitions, malformed, exact_refs, d4_refs = _scan_document(
                    document, source_id
                )
                malformed_locations.extend(malformed)
                exact_references.extend(exact_refs)
                d4_references.extend(d4_refs)
            pairs = sorted({
                (
                    hashlib.sha256(_canonical_bytes(item)).hexdigest(),
                    wire.d4_definition_hash_v1(item),
                )
                for item in definitions
            })
            parent = {
                "carrier_id": source_id,
                "carrier_kind": (
                    "PLAN0012_SYNTHETIC_TELEMETRY_FIXTURE" if group
                    else "PINNED_CUTOFF_JSON_ARTIFACT"
                ),
                "source_digest": digest,
                "source_bytes": byte_count,
                "definition_occurrence_count": len(definitions),
                "malformed_definition_like_count": len(malformed),
                "identity_pairs": [
                    {"definition_hash": exact, "d4_canonical_hash": d4}
                    for exact, d4 in pairs
                ],
            }
            parent_carriers[group].append(parent)
            carrier = _carrier_record(parent)
            carriers.append(carrier)
            all_definitions.append(
                (source_id, carrier["carrier_identity"], definitions)
            )
    if tuple(sorted(malformed_locations)) != (
        legacy._EXPECTED_MALFORMED_DEFINITION_LOCATIONS_V1
    ):
        raise HistoryIdentityError("HISTORY_PROJECTION_INCOMPLETE: malformed source")
    exact_set = {
        row["definition_hash"]
        for carrier in parent_carriers[0] for row in carrier["identity_pairs"]
    }
    d4_set = {
        row["d4_canonical_hash"]
        for carrier in parent_carriers[0] for row in carrier["identity_pairs"]
    }
    if (
        set(exact_references) - exact_set or set(d4_references) - d4_set
        or len(exact_references) != legacy.ATLAS_HISTORY_DEFINITION_HASH_REFERENCE_COUNT_V1
        or len(set(exact_references))
        != legacy.ATLAS_HISTORY_UNIQUE_DEFINITION_HASH_REFERENCE_COUNT_V1
        or len(d4_references) != legacy.ATLAS_HISTORY_D4_HASH_REFERENCE_COUNT_V1
        or len(set(d4_references)) != legacy.ATLAS_HISTORY_UNIQUE_D4_HASH_REFERENCE_COUNT_V1
    ):
        raise HistoryIdentityError("HISTORY_PROJECTION_INCOMPLETE: unresolved reference")

    rows = _identity_rows(all_definitions)
    carriers.sort(key=lambda row: row["carrier_id"])
    schema_counts = Counter(row["schema_version"] for row in rows)
    projection = {
        "projection_version": HISTORY_IDENTITY_PROJECTION_VERSION_V1,
        "projection_id": HISTORY_IDENTITY_PROJECTION_ID_V1,
        "cutoff": cutoff,
        "parents": {
            "legacy_projection_root": _prior_projection_root(parent_carriers[0], False),
            "synthetic_projection_root": _prior_projection_root(parent_carriers[1], True),
            "synthetic_benchmark_root": legacy.PLAN0012_SYNTHETIC_BENCHMARK_ROOT_V1,
        },
        "source_count": len(carriers),
        "definition_occurrence_count": sum(
            row["definition_occurrence_count"] for row in carriers
        ),
        "malformed_definition_like_count": sum(
            row["malformed_definition_like_count"] for row in carriers
        ),
        "unique_definition_count": len(rows),
        "unique_d4_count": len({row["d4_canonical_hash"] for row in rows}),
        "unique_role_neutral_count": len({row["role_neutral_hash"] for row in rows}),
        "schema_unique_counts": [
            {"schema_version": version, "unique_definition_count": count}
            for version, count in sorted(schema_counts.items())
        ],
        "carriers": carriers,
        "carrier_root": _digest(_CARRIER_ROOT_DOMAIN_V1, carriers),
        "identities": rows,
        "identity_root": _digest(_IDENTITY_ROOT_DOMAIN_V1, rows),
    }
    projection["projection_root"] = _digest(_PROJECTION_ROOT_DOMAIN_V1, projection)
    return projection


def build_history_identity_projection_v1(
    cutoff_classification: Mapping[str, Any],
    legacy_raw_bytes_by_path: Mapping[str, bytes],
    synthetic_raw_bytes_by_id: Mapping[str, bytes],
) -> Dict[str, Any]:
    """Authenticate all 73 mandatory sources and return a sealed identity projection."""
    return validate_history_identity_projection_v1(_derive_history_identity_projection(
        cutoff_classification, legacy_raw_bytes_by_path, synthetic_raw_bytes_by_id
    ))


__all__ = (
    "HISTORY_CARRIER_ROOT_V1",
    "HISTORY_DEFINITION_OCCURRENCE_COUNT_V1",
    "HISTORY_IDENTITY_PROJECTION_ID_V1",
    "HISTORY_IDENTITY_PROJECTION_VERSION_V1",
    "HISTORY_IDENTITY_ROOT_V1",
    "HISTORY_MALFORMED_DEFINITION_LIKE_COUNT_V1",
    "HISTORY_PROJECTION_ROOT_V1",
    "HISTORY_SCHEMA_UNIQUE_COUNTS_V1",
    "HISTORY_SOURCE_COUNT_V1",
    "HISTORY_UNIQUE_D4_COUNT_V1",
    "HISTORY_UNIQUE_DEFINITION_COUNT_V1",
    "HISTORY_UNIQUE_ROLE_NEUTRAL_COUNT_V1",
    "HistoryIdentityError",
    "PLAN0012_SYNTHETIC_IDENTITIES_V1",
    "build_history_identity_projection_v1",
    "role_neutral_definition_hash_v1",
    "validate_history_identity_projection_v1",
)
