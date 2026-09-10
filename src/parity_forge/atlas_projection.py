"""Definition-only identity projections for the Plan-0013 atlas.

This module is the narrow data boundary shared by the historical source adapter
and the outcome-free selector.  It accepts no raw artifact bytes and retains no
DSL definition, result, trace, score, or outcome.  Every projection is a strict,
detached JSON value containing only authenticated source metadata and exact/D4
identity pairs.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterable, Mapping, Sequence, Tuple


ATLAS_IDENTITY_PROJECTION_VERSION_V1 = 1
ATLAS_PRIOR_GAMEPLAY_EXPOSURE_KIND_V1 = "PRIOR_GAMEPLAY_EXPOSURE"
ATLAS_SYNTHETIC_FIXTURE_EXPOSURE_KIND_V1 = (
    "SYNTHETIC_EVALUATOR_FIXTURE_EXPOSURE"
)

_ALLOWED_EXPOSURE_KINDS_V1 = frozenset(
    (
        ATLAS_PRIOR_GAMEPLAY_EXPOSURE_KIND_V1,
        ATLAS_SYNTHETIC_FIXTURE_EXPOSURE_KIND_V1,
    )
)
_ATTESTATION_DOMAIN_V1 = b"parity-forge:plan0013:source-attestation:v1\0"
_CARRIER_DOMAIN_V1 = b"parity-forge:plan0013:identity-carrier:v1\0"
_EXACT_ROOT_DOMAIN_V1 = b"parity-forge:plan0013:identity-exact:v1\0"
_D4_ROOT_DOMAIN_V1 = b"parity-forge:plan0013:identity-d4:v1\0"
_PROJECTION_DOMAIN_V1 = b"parity-forge:plan0013:identity-projection:v1\0"

_MAX_JSON_NODES_V1 = 500_000
_MAX_JSON_DEPTH_V1 = 32
_SHA256_LENGTH = 64


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
        raise ValueError("projection values must be finite canonical JSON") from error


def _validate_json_tree(value: Any, label: str) -> None:
    nodes = 0
    active = set()

    def visit(item: Any, depth: int) -> None:
        nonlocal nodes
        nodes += 1
        if nodes > _MAX_JSON_NODES_V1:
            raise ValueError("{} exceeds the JSON node cap".format(label))
        if depth > _MAX_JSON_DEPTH_V1:
            raise ValueError("{} exceeds the JSON depth cap".format(label))
        if item is None or type(item) in (bool, int, str):
            return
        if type(item) not in (dict, list):
            raise TypeError("{} must contain only exact JSON values".format(label))
        identity = id(item)
        if identity in active:
            raise ValueError("{} cannot contain a cycle".format(label))
        active.add(identity)
        try:
            if type(item) is dict:
                if any(type(key) is not str for key in item):
                    raise TypeError("{} object keys must be strings".format(label))
                for key in sorted(item):
                    visit(item[key], depth + 1)
            else:
                for child in item:
                    visit(child, depth + 1)
        finally:
            active.remove(identity)

    visit(value, 0)


def _json_copy(value: Any, label: str) -> Any:
    _validate_json_tree(value, label)
    return json.loads(_canonical_bytes(value))


def _domain_digest(domain: bytes, value: Any) -> str:
    return hashlib.sha256(domain + _canonical_bytes(value)).hexdigest()


def _exact_keys(
    value: Any, expected: Iterable[str], label: str
) -> Dict[str, Any]:
    if type(value) is not dict:
        raise TypeError("{} must be an exact object".format(label))
    if any(type(key) is not str for key in value):
        raise TypeError("{} keys must be strings".format(label))
    expected_set = set(expected)
    actual = set(value)
    if actual != expected_set:
        missing = sorted(expected_set - actual)
        unknown = sorted(actual - expected_set)
        raise ValueError(
            "{} fields mismatch; missing={}, unknown={}".format(
                label, missing, unknown
            )
        )
    return value


def _require_string(value: Any, label: str) -> str:
    if type(value) is not str or not value:
        raise TypeError("{} must be a nonempty string".format(label))
    return value


def _require_nonnegative_int(value: Any, label: str) -> int:
    if type(value) is not int or value < 0:
        raise TypeError("{} must be a nonnegative exact integer".format(label))
    return value


def _require_sha256(value: Any, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != _SHA256_LENGTH
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError("{} must be a lowercase SHA-256 digest".format(label))
    return value


def _identity_pairs(
    value: Any, label: str
) -> Tuple[Tuple[str, str], ...]:
    if type(value) not in (list, tuple):
        raise TypeError("{} must be an array".format(label))
    pairs = []
    for index, raw in enumerate(value):
        record = _exact_keys(
            raw,
            ("definition_hash", "d4_canonical_hash"),
            "{}[{}]".format(label, index),
        )
        pairs.append(
            (
                _require_sha256(
                    record["definition_hash"],
                    "{} definition hash".format(label),
                ),
                _require_sha256(
                    record["d4_canonical_hash"],
                    "{} D4 hash".format(label),
                ),
            )
        )
    ordered = tuple(sorted(set(pairs)))
    if tuple(pairs) != ordered:
        raise ValueError("{} must be unique and lexically ordered".format(label))
    return ordered


def _carrier_metadata(carrier: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "carrier_id": carrier["carrier_id"],
        "carrier_kind": carrier["carrier_kind"],
        "source_digest": carrier["source_digest"],
        "source_bytes": carrier["source_bytes"],
    }


def build_atlas_identity_projection_v1(
    *,
    projection_id: str,
    exposure_kind: str,
    cutoff_id: str,
    carriers: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Build one strict identity-only projection from adapter-produced carriers."""

    projection_id = _require_string(projection_id, "projection_id")
    cutoff_id = _require_string(cutoff_id, "cutoff_id")
    if exposure_kind not in _ALLOWED_EXPOSURE_KINDS_V1:
        raise ValueError("exposure_kind is not part of projection-v1")
    if type(carriers) not in (list, tuple):
        raise TypeError("carriers must be an array")

    normalized = []
    for index, raw in enumerate(carriers):
        carrier = _exact_keys(
            raw,
            (
                "carrier_id",
                "carrier_kind",
                "source_digest",
                "source_bytes",
                "definition_occurrence_count",
                "malformed_definition_like_count",
                "identity_pairs",
            ),
            "carrier[{}]".format(index),
        )
        pairs = _identity_pairs(
            carrier["identity_pairs"], "carrier identity_pairs"
        )
        occurrence_count = _require_nonnegative_int(
            carrier["definition_occurrence_count"],
            "carrier definition occurrence count",
        )
        malformed_count = _require_nonnegative_int(
            carrier["malformed_definition_like_count"],
            "carrier malformed definition-like count",
        )
        if occurrence_count < len(pairs):
            raise ValueError(
                "carrier occurrences cannot be fewer than unique identities"
            )
        value = {
            "carrier_id": _require_string(
                carrier["carrier_id"], "carrier_id"
            ),
            "carrier_kind": _require_string(
                carrier["carrier_kind"], "carrier_kind"
            ),
            "source_digest": _require_sha256(
                carrier["source_digest"], "carrier source digest"
            ),
            "source_bytes": _require_nonnegative_int(
                carrier["source_bytes"], "carrier source bytes"
            ),
            "definition_occurrence_count": occurrence_count,
            "malformed_definition_like_count": malformed_count,
            "identity_pairs": [
                {
                    "definition_hash": definition_digest,
                    "d4_canonical_hash": d4_digest,
                }
                for definition_digest, d4_digest in pairs
            ],
        }
        value["carrier_root"] = _domain_digest(_CARRIER_DOMAIN_V1, value)
        normalized.append(value)

    carrier_ids = [carrier["carrier_id"] for carrier in normalized]
    if carrier_ids != sorted(set(carrier_ids)):
        raise ValueError("carrier IDs must be unique and lexically ordered")

    exact_hashes = sorted(
        {
            pair["definition_hash"]
            for carrier in normalized
            for pair in carrier["identity_pairs"]
        }
    )
    d4_hashes = sorted(
        {
            pair["d4_canonical_hash"]
            for carrier in normalized
            for pair in carrier["identity_pairs"]
        }
    )
    metadata = [_carrier_metadata(carrier) for carrier in normalized]
    result = {
        "projection_version": ATLAS_IDENTITY_PROJECTION_VERSION_V1,
        "projection_id": projection_id,
        "exposure_kind": exposure_kind,
        "cutoff_id": cutoff_id,
        "source_attestation_root": _domain_digest(
            _ATTESTATION_DOMAIN_V1, metadata
        ),
        "source_count": len(normalized),
        "definition_occurrence_count": sum(
            carrier["definition_occurrence_count"] for carrier in normalized
        ),
        "malformed_definition_like_count": sum(
            carrier["malformed_definition_like_count"] for carrier in normalized
        ),
        "unique_definition_count": len(exact_hashes),
        "unique_definition_hashes": exact_hashes,
        "unique_definition_root": _domain_digest(
            _EXACT_ROOT_DOMAIN_V1, exact_hashes
        ),
        "unique_d4_count": len(d4_hashes),
        "unique_d4_hashes": d4_hashes,
        "unique_d4_root": _domain_digest(_D4_ROOT_DOMAIN_V1, d4_hashes),
        "carriers": normalized,
    }
    result["projection_root"] = _domain_digest(_PROJECTION_DOMAIN_V1, result)
    return validate_atlas_identity_projection_v1(result)


def validate_atlas_identity_projection_v1(value: Any) -> Dict[str, Any]:
    """Strictly validate and detach an identity-only projection."""

    _validate_json_tree(value, "atlas identity projection")
    # Seal caller-owned containers before interpreting any field.  Validation
    # below uses only this private JSON tree, so a concurrent mutation cannot
    # change the identities after their roots have been checked.
    entry = _canonical_bytes(value)
    detached = json.loads(entry)
    top = _exact_keys(
        detached,
        (
            "projection_version",
            "projection_id",
            "exposure_kind",
            "cutoff_id",
            "source_attestation_root",
            "source_count",
            "definition_occurrence_count",
            "malformed_definition_like_count",
            "unique_definition_count",
            "unique_definition_hashes",
            "unique_definition_root",
            "unique_d4_count",
            "unique_d4_hashes",
            "unique_d4_root",
            "carriers",
            "projection_root",
        ),
        "atlas identity projection",
    )
    if (
        type(top["projection_version"]) is not int
        or top["projection_version"]
        != ATLAS_IDENTITY_PROJECTION_VERSION_V1
    ):
        raise ValueError("atlas identity projection version mismatch")
    projection_id = _require_string(top["projection_id"], "projection_id")
    cutoff_id = _require_string(top["cutoff_id"], "cutoff_id")
    exposure_kind = top["exposure_kind"]
    if exposure_kind not in _ALLOWED_EXPOSURE_KINDS_V1:
        raise ValueError("atlas identity exposure kind mismatch")
    if type(top["carriers"]) is not list:
        raise TypeError("projection carriers must be an array")

    unsigned_carriers = []
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
                "identity_pairs",
                "carrier_root",
            ),
            "projection carrier[{}]".format(index),
        )
        unsigned = dict(carrier)
        carrier_root = unsigned.pop("carrier_root")
        if _require_sha256(carrier_root, "carrier root") != _domain_digest(
            _CARRIER_DOMAIN_V1, unsigned
        ):
            raise ValueError("identity carrier root mismatch")
        unsigned_carriers.append(unsigned)

    # Reconstruct without recursive public validation.
    carrier_ids = [carrier["carrier_id"] for carrier in unsigned_carriers]
    if carrier_ids != sorted(set(carrier_ids)):
        raise ValueError("projection carrier IDs must be unique and ordered")
    all_pairs = []
    for carrier in unsigned_carriers:
        _require_string(carrier["carrier_id"], "carrier_id")
        _require_string(carrier["carrier_kind"], "carrier_kind")
        _require_sha256(carrier["source_digest"], "carrier source digest")
        _require_nonnegative_int(carrier["source_bytes"], "carrier source bytes")
        pairs = _identity_pairs(
            carrier["identity_pairs"], "projection carrier identity_pairs"
        )
        if _require_nonnegative_int(
            carrier["definition_occurrence_count"],
            "carrier definition occurrence count",
        ) < len(pairs):
            raise ValueError(
                "carrier occurrences cannot be fewer than unique identities"
            )
        _require_nonnegative_int(
            carrier["malformed_definition_like_count"],
            "carrier malformed definition-like count",
        )
        all_pairs.extend(pairs)

    exact_hashes = sorted({pair[0] for pair in all_pairs})
    d4_hashes = sorted({pair[1] for pair in all_pairs})
    exact_to_d4: Dict[str, str] = {}
    for definition_digest, d4_digest in all_pairs:
        previous = exact_to_d4.setdefault(definition_digest, d4_digest)
        if previous != d4_digest:
            raise ValueError("one exact definition maps to multiple D4 identities")
    for key, observed in (
        ("source_count", len(unsigned_carriers)),
        (
            "definition_occurrence_count",
            sum(
                carrier["definition_occurrence_count"]
                for carrier in unsigned_carriers
            ),
        ),
        (
            "malformed_definition_like_count",
            sum(
                carrier["malformed_definition_like_count"]
                for carrier in unsigned_carriers
            ),
        ),
        ("unique_definition_count", len(exact_hashes)),
        ("unique_d4_count", len(d4_hashes)),
    ):
        if _require_nonnegative_int(top[key], key) != observed:
            raise ValueError("{} mismatch".format(key))
    if top["unique_definition_hashes"] != exact_hashes:
        raise ValueError("unique definition hash projection mismatch")
    if top["unique_d4_hashes"] != d4_hashes:
        raise ValueError("unique D4 hash projection mismatch")
    if _require_sha256(
        top["source_attestation_root"], "source attestation root"
    ) != _domain_digest(
        _ATTESTATION_DOMAIN_V1,
        [_carrier_metadata(carrier) for carrier in unsigned_carriers],
    ):
        raise ValueError("source attestation root mismatch")
    if _require_sha256(
        top["unique_definition_root"], "unique definition root"
    ) != _domain_digest(_EXACT_ROOT_DOMAIN_V1, exact_hashes):
        raise ValueError("unique definition root mismatch")
    if _require_sha256(top["unique_d4_root"], "unique D4 root") != _domain_digest(
        _D4_ROOT_DOMAIN_V1, d4_hashes
    ):
        raise ValueError("unique D4 root mismatch")
    unsigned_top = dict(top)
    projection_root = unsigned_top.pop("projection_root")
    if _require_sha256(projection_root, "projection root") != _domain_digest(
        _PROJECTION_DOMAIN_V1, unsigned_top
    ):
        raise ValueError("identity projection root mismatch")
    if entry != _canonical_bytes(value):
        raise ValueError("atlas identity projection changed during validation")
    return _json_copy(top, "atlas identity projection")


__all__ = (
    "ATLAS_IDENTITY_PROJECTION_VERSION_V1",
    "ATLAS_PRIOR_GAMEPLAY_EXPOSURE_KIND_V1",
    "ATLAS_SYNTHETIC_FIXTURE_EXPOSURE_KIND_V1",
    "build_atlas_identity_projection_v1",
    "validate_atlas_identity_projection_v1",
)
