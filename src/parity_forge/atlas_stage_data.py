"""Candidate-blind data contracts for the Plan-0013 execution stages.

This module is deliberately capability-neutral.  It binds development DSL
bodies to the already-frozen protocol coordinates, reconciles closed status
ledgers, and replays retained complete traces with the pure engine.  It does
not select, solve, play, assess, or inspect a game.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .atlas_protocol import (
    ATLAS_ACTION_CANDIDATE_CAP_V1,
    ATLAS_DEFINITION_ORIENTATION_COUNT_V1,
    ATLAS_DEVELOPMENT_DEFINITION_COUNT_V1,
    ATLAS_DEVELOPMENT_PAIR_COUNT_V1,
    ATLAS_D4_TRANSFORMS_V1,
    ATLAS_EXACT_SCHEDULE_ROOT_V1,
    ATLAS_GAME_PLY_CAP_V1,
    ATLAS_GAME_SCHEDULE_ROOT_V1,
    ATLAS_ORIENTATION_SCHEDULE_ROOT_V1,
    ATLAS_PROTOCOL_ID_V1,
    ATLAS_PROTOCOL_ROOT_V1,
    ATLAS_SAMPLED_GAME_COUNT_V1,
    ATLAS_TELEMETRY_SCHEDULE_ROOT_V1,
    iter_frozen_atlas_exact_schedule_from_protocol_v1,
    iter_frozen_atlas_game_schedule_from_protocol_v1,
    iter_frozen_atlas_orientation_schedule_from_protocol_v1,
    iter_frozen_atlas_profile_schedule_from_protocol_v1,
)
from .dsl import Player, definition_hash, parse_definition
from .engine import action_from_dict, apply_action, initial_state, legal_actions
from .symmetry import D4_TRANSFORMS, d4_canonical_hash, transform_definition


ATLAS_STAGE_DATA_VERSION_V1 = 1
ATLAS_DETACHED_MANIFEST_ID_V1 = "plan0013-detached-development-manifest-v1"
ATLAS_STATUS_LEDGER_VERSION_V1 = 1
ATLAS_COMPLETE_TRACE_VERSION_V1 = 1

ATLAS_RANDOM_STRENGTH_ID_V1 = "random-v1-weak"
ATLAS_DEPTH1_STRENGTH_ID_V1 = "terminal_only_minimax-v1-depth1"

_MANIFEST_ROOT_DOMAIN_V1 = (
    b"parity-forge:plan0013:stage-data:detached-manifest:v1\0"
)
_LEDGER_ROOT_DOMAIN_V1 = b"parity-forge:plan0013:stage-data:status-ledger:v1\0"
_SUBSCHEDULE_ROOT_DOMAIN_V1 = (
    b"parity-forge:plan0013:stage-data:strength-subschedule:v1\0"
)

_MAX_JSON_NODES = 8_000_000
_MAX_JSON_DEPTH = 64
_MAX_CANONICAL_BYTES = 128_000_000
_MAX_STRING_CHARACTERS = 1_000_000
_MAX_INTEGER_BITS = 128

_MANIFEST_FIELDS = frozenset(
    (
        "manifest_version",
        "manifest_id",
        "status",
        "protocol_id",
        "protocol_root",
        "selection_canonical_sha256",
        "selection_partition_root",
        "development_pair_count",
        "development_definition_count",
        "orientation_definition_count",
        "definitions",
        "manifest_root",
    )
)
_DEFINITION_ENTRY_FIELDS = frozenset(
    (
        "definition_index",
        "exact_slot_id",
        "pair_index",
        "member_index",
        "member",
        "paired_mechanical_d4_identity",
        "representative_definition_hash",
        "d4_canonical_hash",
        "representative_definition",
        "orientations",
    )
)
_ORIENTATION_ENTRY_FIELDS = frozenset(
    (
        "orientation_slot_index",
        "orientation_slot_id",
        "transform_index",
        "transform",
        "transformed_definition_hash",
        "first_duplicate_transform_index",
        "definition",
    )
)

_LEDGER_FIELDS = frozenset(
    (
        "ledger_version",
        "ledger_kind",
        "protocol_id",
        "protocol_root",
        "parent_schedule_root",
        "subschedule_root",
        "strength_identity_or_null",
        "expected_slot_count",
        "rows",
        "status_counts",
        "ledger_root",
    )
)
_LEDGER_ROW_FIELDS = frozenset(
    ("slot_id", "status", "origin", "record_root_or_null")
)

_STATUS_VOCABULARIES = {
    "EXACT": (
        "COMPLETE",
        "INCOMPLETE",
        "INVALID",
        "PROOF_CONTRADICTION",
        "NOT_RUN",
        "BLOCKED",
    ),
    "EXACT_PV": (
        "VALID",
        "INCOMPLETE",
        "INVALID",
        "PROOF_CONTRADICTION",
        "NOT_RUN",
        "BLOCKED",
    ),
    "SAMPLED": (
        "COMPLETE",
        "INCOMPLETE",
        "INVALID",
        "PROOF_CONTRADICTION",
        "NOT_RUN",
        "BLOCKED",
    ),
    "TELEMETRY": (
        "VALIDATED",
        "NOT_ADMISSIBLE",
        "MISSING",
        "INVALID",
        "PROOF_CONTRADICTION",
        "BLOCKED",
    ),
}
_RAW_STATUSES = {
    "EXACT": frozenset(("COMPLETE", "INCOMPLETE", "INVALID", "PROOF_CONTRADICTION")),
    "EXACT_PV": frozenset(("VALID", "INCOMPLETE", "INVALID", "PROOF_CONTRADICTION")),
    "SAMPLED": frozenset(("COMPLETE", "INCOMPLETE", "INVALID", "PROOF_CONTRADICTION")),
    "TELEMETRY": frozenset(("VALIDATED", "INVALID", "PROOF_CONTRADICTION")),
}
_INTERRUPTED_STATUS = {
    "EXACT": "INCOMPLETE",
    "EXACT_PV": "INCOMPLETE",
    "SAMPLED": "INCOMPLETE",
    "TELEMETRY": "MISSING",
}


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _strict_json_bytes(value: Any, label: str) -> bytes:
    """Seal a finite exact-JSON tree without invoking caller hooks."""

    active = set()
    nodes = 0
    stack: List[Tuple[Any, int, bool]] = [(value, 0, False)]
    while stack:
        current, depth, leaving = stack.pop()
        if leaving:
            active.remove(id(current))
            continue
        nodes += 1
        if nodes > _MAX_JSON_NODES:
            raise ValueError("{} exceeds the JSON node limit".format(label))
        if depth > _MAX_JSON_DEPTH:
            raise ValueError("{} exceeds the JSON depth limit".format(label))
        if current is None or type(current) is bool:
            continue
        if type(current) is int:
            if current.bit_length() > _MAX_INTEGER_BITS:
                raise ValueError("{} contains an oversized integer".format(label))
            continue
        if type(current) is str:
            if len(current) > _MAX_STRING_CHARACTERS:
                raise ValueError("{} contains an oversized string".format(label))
            continue
        if type(current) not in (dict, list):
            raise TypeError("{} must contain exact JSON values".format(label))
        identity = id(current)
        if identity in active:
            raise ValueError("{} contains a cycle".format(label))
        active.add(identity)
        stack.append((current, depth, True))
        if type(current) is dict:
            if any(type(key) is not str for key in current):
                raise TypeError("{} object keys must be exact strings".format(label))
            for key in reversed(list(current)):
                stack.append((current[key], depth + 1, False))
        else:
            for item in reversed(current):
                stack.append((item, depth + 1, False))
    encoded = _canonical_bytes(value)
    if len(encoded) > _MAX_CANONICAL_BYTES:
        raise ValueError("{} exceeds the canonical byte limit".format(label))
    return encoded


def _json_copy(value: Any, label: str) -> Any:
    return json.loads(_strict_json_bytes(value, label).decode("utf-8"))


def _exact_object(value: Any, fields: Iterable[str], label: str) -> Dict[str, Any]:
    if type(value) is not dict or set(value) != set(fields):
        raise ValueError("{} fields drifted".format(label))
    return value


def _exact_list(value: Any, label: str) -> List[Any]:
    if type(value) is not list:
        raise TypeError("{} must be an exact array".format(label))
    return value


def _exact_int(value: Any, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError("{} must be an exact integer >= {}".format(label, minimum))
    return value


def _sha256(value: Any, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError("{} must be a lowercase SHA-256".format(label))
    return value


def _digest(domain: bytes, value: Any) -> str:
    return hashlib.sha256(domain + _canonical_bytes(value)).hexdigest()


def _protocol_binding(protocol_value: Any) -> Tuple[Dict[str, Any], bytes]:
    entry = _strict_json_bytes(protocol_value, "frozen atlas protocol")
    protocol = json.loads(entry.decode("utf-8"))
    if type(protocol) is not dict:
        raise TypeError("frozen atlas protocol must be an exact object")
    if protocol.get("protocol_id") != ATLAS_PROTOCOL_ID_V1:
        raise ValueError("frozen atlas protocol identity drifted")
    if protocol.get("protocol_root") != ATLAS_PROTOCOL_ROOT_V1:
        raise ValueError("frozen atlas protocol root drifted")
    # The protocol-only iterator performs the canonical-SHA and complete root
    # reconstruction checks.  Consume one fixed column here before trusting any
    # nested binding fields.
    exact = list(iter_frozen_atlas_exact_schedule_from_protocol_v1(protocol))
    if len(exact) != ATLAS_DEVELOPMENT_DEFINITION_COUNT_V1:
        raise ValueError("frozen exact schedule count drifted")
    if _strict_json_bytes(protocol_value, "frozen atlas protocol") != entry:
        raise ValueError("frozen atlas protocol changed during validation")
    return protocol, entry


def _selection_commitments(protocol: Mapping[str, Any]) -> Tuple[str, str]:
    try:
        roots = protocol["upstream"]["selector_roots"]
        selection_sha = roots["selection_canonical_sha256"]
        partition_root = roots["selection_partition_root"]
    except (KeyError, TypeError) as error:
        raise ValueError("protocol selector commitments are missing") from error
    return (
        _sha256(selection_sha, "selection canonical SHA-256"),
        _sha256(partition_root, "selection partition root"),
    )


def _validate_definition_body(value: Any, expected_hash: str, label: str):
    body_entry = _strict_json_bytes(value, label)
    definition = parse_definition(json.loads(body_entry.decode("utf-8")))
    canonical_body = definition.to_dict()
    if _canonical_bytes(canonical_body) != body_entry:
        raise ValueError("{} is not the canonical DSL body".format(label))
    if definition_hash(definition) != expected_hash:
        raise ValueError("{} hash differs from its schedule coordinate".format(label))
    return definition


def _build_manifest_from_schedules(
    development_pairs: Any,
    exact_rows: Sequence[Mapping[str, Any]],
    orientation_rows: Sequence[Mapping[str, Any]],
    *,
    protocol_id: str,
    protocol_root: str,
    selection_canonical_sha256: str,
    selection_partition_root: str,
) -> Dict[str, Any]:
    """Internal schedule-parametric builder used by synthetic contract tests."""

    pairs = _exact_list(development_pairs, "development pair block")
    exact = _json_copy(list(exact_rows), "exact schedule rows")
    orientations = _json_copy(list(orientation_rows), "orientation schedule rows")
    if len(exact) != 2 * len(pairs):
        raise ValueError("development definitions do not cover the exact schedule")
    if len(orientations) != len(exact) * len(ATLAS_D4_TRANSFORMS_V1):
        raise ValueError("D4 definitions do not cover the orientation schedule")
    if tuple(D4_TRANSFORMS) != tuple(ATLAS_D4_TRANSFORMS_V1):
        raise ValueError("DSL D4 order differs from the frozen protocol")

    orientation_by_exact: Dict[str, List[Dict[str, Any]]] = {}
    for row in orientations:
        if type(row) is not dict:
            raise TypeError("orientation schedule row must be an exact object")
        orientation_by_exact.setdefault(row.get("exact_slot_id"), []).append(row)

    entries = []
    seen_exact_ids = set()
    seen_orientation_ids = set()
    for expected_definition_index, row in enumerate(exact):
        if type(row) is not dict:
            raise TypeError("exact schedule row must be an exact object")
        exact_slot_id = _sha256(row.get("slot_id"), "exact slot identity")
        if exact_slot_id in seen_exact_ids:
            raise ValueError("exact schedule contains duplicate slot identities")
        seen_exact_ids.add(exact_slot_id)
        if row.get("definition_index") != expected_definition_index:
            raise ValueError("exact schedule definition order drifted")
        pair_index = _exact_int(row.get("pair_index"), "pair index")
        member_index = _exact_int(row.get("member_index"), "member index")
        if pair_index >= len(pairs) or member_index not in (0, 1):
            raise ValueError("exact schedule pair/member coordinate is out of range")
        member_label = row.get("member")
        if member_label != ("A_FIRST", "B_FIRST")[member_index]:
            raise ValueError("exact schedule member order drifted")
        pair = pairs[pair_index]
        if type(pair) is not dict:
            raise TypeError("development pair must be an exact object")
        if pair.get("paired_mechanical_d4_identity") != row.get(
            "paired_mechanical_d4_identity"
        ):
            raise ValueError("development pair identity differs from exact schedule")
        members = pair.get("members")
        if type(members) is not dict or set(members) != {"A_FIRST", "B_FIRST"}:
            raise ValueError("development pair member map drifted")
        member = members[member_label]
        if type(member) is not dict:
            raise TypeError("development member must be an exact object")
        representative_hash = _sha256(
            row.get("representative_definition_hash"),
            "representative definition hash",
        )
        if member.get("representative_definition_hash") != representative_hash:
            raise ValueError("selection representative hash differs from schedule")
        representative_body = _json_copy(
            member.get("representative_definition"),
            "development representative definition",
        )
        definition = _validate_definition_body(
            representative_body,
            representative_hash,
            "development representative definition",
        )
        if definition.first_player.value != row.get("first_player"):
            raise ValueError("representative first player differs from schedule")
        expected_d4_hash = _sha256(row.get("d4_canonical_hash"), "D4 hash")
        if d4_canonical_hash(definition) != expected_d4_hash:
            raise ValueError("representative D4 hash differs from schedule")

        scheduled_orientations = orientation_by_exact.get(exact_slot_id, [])
        if len(scheduled_orientations) != len(ATLAS_D4_TRANSFORMS_V1):
            raise ValueError("exact slot does not have eight orientation rows")
        orientation_entries = []
        transformed_hashes = []
        for transform_index, (transform, orientation) in enumerate(
            zip(ATLAS_D4_TRANSFORMS_V1, scheduled_orientations)
        ):
            if (
                orientation.get("definition_index") != expected_definition_index
                or orientation.get("pair_index") != pair_index
                or orientation.get("member") != member_label
                or orientation.get("transform_index") != transform_index
                or orientation.get("transform") != transform
            ):
                raise ValueError("orientation schedule coordinate drifted")
            orientation_slot_id = _sha256(
                orientation.get("slot_id"), "orientation slot identity"
            )
            if orientation_slot_id in seen_orientation_ids:
                raise ValueError("orientation schedule contains duplicate slot identities")
            seen_orientation_ids.add(orientation_slot_id)
            transformed = transform_definition(definition, transform)
            transformed_body = transformed.to_dict()
            transformed_hash = definition_hash(transformed)
            if transformed_hash != orientation.get("transformed_definition_hash"):
                raise ValueError("transformed definition hash differs from schedule")
            if orientation.get("d4_canonical_hash") != expected_d4_hash:
                raise ValueError("orientation D4 hash differs from representative")
            transformed_hashes.append(transformed_hash)
            if orientation.get("first_duplicate_transform_index") != transformed_hashes.index(
                transformed_hash
            ):
                raise ValueError("orientation duplicate witness drifted")
            orientation_entries.append(
                {
                    "orientation_slot_index": _exact_int(
                        orientation.get("orientation_slot_index"),
                        "orientation slot index",
                    ),
                    "orientation_slot_id": orientation_slot_id,
                    "transform_index": transform_index,
                    "transform": transform,
                    "transformed_definition_hash": transformed_hash,
                    "first_duplicate_transform_index": transformed_hashes.index(
                        transformed_hash
                    ),
                    "definition": transformed_body,
                }
            )
        entries.append(
            {
                "definition_index": expected_definition_index,
                "exact_slot_id": exact_slot_id,
                "pair_index": pair_index,
                "member_index": member_index,
                "member": member_label,
                "paired_mechanical_d4_identity": _sha256(
                    row.get("paired_mechanical_d4_identity"),
                    "development pair identity",
                ),
                "representative_definition_hash": representative_hash,
                "d4_canonical_hash": expected_d4_hash,
                "representative_definition": representative_body,
                "orientations": orientation_entries,
            }
        )

    unsigned = {
        "manifest_version": ATLAS_STAGE_DATA_VERSION_V1,
        "manifest_id": ATLAS_DETACHED_MANIFEST_ID_V1,
        "status": "OUTCOME_FREE_DETACHED_DEVELOPMENT_MANIFEST",
        "protocol_id": protocol_id,
        "protocol_root": protocol_root,
        "selection_canonical_sha256": _sha256(
            selection_canonical_sha256, "selection canonical SHA-256"
        ),
        "selection_partition_root": _sha256(
            selection_partition_root, "selection partition root"
        ),
        "development_pair_count": len(pairs),
        "development_definition_count": len(entries),
        "orientation_definition_count": sum(
            len(entry["orientations"]) for entry in entries
        ),
        "definitions": entries,
    }
    return {
        **unsigned,
        "manifest_root": _digest(_MANIFEST_ROOT_DOMAIN_V1, unsigned),
    }


def build_detached_atlas_development_manifest_v1(
    selection_value: Any, protocol_value: Any
) -> Dict[str, Any]:
    """Attach only the frozen development bodies to protocol coordinates."""

    selection_entry = _strict_json_bytes(selection_value, "frozen atlas selection")
    selection = json.loads(selection_entry.decode("utf-8"))
    if type(selection) is not dict:
        raise TypeError("frozen atlas selection must be an exact object")
    protocol, protocol_entry = _protocol_binding(protocol_value)
    selection_sha, partition_root = _selection_commitments(protocol)
    if hashlib.sha256(selection_entry).hexdigest() != selection_sha:
        raise ValueError("atlas selection differs from the frozen protocol commitment")
    if selection.get("selection_partition_root") != partition_root:
        raise ValueError("atlas selection partition root differs from protocol")
    development = selection.get("development_pairs")
    if type(development) is not list or len(development) != ATLAS_DEVELOPMENT_PAIR_COUNT_V1:
        raise ValueError("atlas development pair block count drifted")
    exact = list(iter_frozen_atlas_exact_schedule_from_protocol_v1(protocol))
    orientations = list(
        iter_frozen_atlas_orientation_schedule_from_protocol_v1(protocol)
    )
    manifest = _build_manifest_from_schedules(
        development,
        exact,
        orientations,
        protocol_id=ATLAS_PROTOCOL_ID_V1,
        protocol_root=ATLAS_PROTOCOL_ROOT_V1,
        selection_canonical_sha256=selection_sha,
        selection_partition_root=partition_root,
    )
    validate_detached_atlas_development_manifest_v1(manifest, protocol)
    if _strict_json_bytes(selection_value, "frozen atlas selection") != selection_entry:
        raise ValueError("atlas selection changed during manifest construction")
    if _strict_json_bytes(protocol_value, "frozen atlas protocol") != protocol_entry:
        raise ValueError("atlas protocol changed during manifest construction")
    return _json_copy(manifest, "detached development manifest")


def _validate_manifest_from_schedules(
    value: Any,
    exact_rows: Sequence[Mapping[str, Any]],
    orientation_rows: Sequence[Mapping[str, Any]],
    *,
    protocol_id: str,
    protocol_root: str,
    selection_canonical_sha256: str,
    selection_partition_root: str,
    fixed_counts: bool,
) -> Dict[str, Any]:
    entry = _strict_json_bytes(value, "detached development manifest")
    manifest = json.loads(entry.decode("utf-8"))
    _exact_object(manifest, _MANIFEST_FIELDS, "detached development manifest")
    if (
        manifest["manifest_version"] != ATLAS_STAGE_DATA_VERSION_V1
        or manifest["manifest_id"] != ATLAS_DETACHED_MANIFEST_ID_V1
        or manifest["status"] != "OUTCOME_FREE_DETACHED_DEVELOPMENT_MANIFEST"
        or manifest["protocol_id"] != protocol_id
        or manifest["protocol_root"] != protocol_root
        or manifest["selection_canonical_sha256"] != selection_canonical_sha256
        or manifest["selection_partition_root"] != selection_partition_root
    ):
        raise ValueError("detached development manifest binding drifted")
    definitions = _exact_list(manifest["definitions"], "manifest definitions")
    exact = _json_copy(list(exact_rows), "exact schedule rows")
    orientations = _json_copy(list(orientation_rows), "orientation schedule rows")
    if len(definitions) != len(exact):
        raise ValueError("manifest does not cover every exact slot")
    if manifest["development_definition_count"] != len(exact):
        raise ValueError("manifest definition count drifted")
    pair_count = len({row.get("pair_index") for row in exact})
    if manifest["development_pair_count"] != pair_count:
        raise ValueError("manifest pair count drifted")
    if manifest["orientation_definition_count"] != len(orientations):
        raise ValueError("manifest orientation count drifted")
    if fixed_counts and (
        pair_count != ATLAS_DEVELOPMENT_PAIR_COUNT_V1
        or len(exact) != ATLAS_DEVELOPMENT_DEFINITION_COUNT_V1
        or len(orientations) != ATLAS_DEFINITION_ORIENTATION_COUNT_V1
    ):
        raise ValueError("manifest fixed denominator drifted")

    orientation_by_exact: Dict[str, List[Dict[str, Any]]] = {}
    for row in orientations:
        orientation_by_exact.setdefault(row.get("exact_slot_id"), []).append(row)
    seen_orientation_ids = set()
    for index, (stored, scheduled) in enumerate(zip(definitions, exact)):
        _exact_object(stored, _DEFINITION_ENTRY_FIELDS, "manifest definition entry")
        expected_scalar = {
            "definition_index": scheduled.get("definition_index"),
            "exact_slot_id": scheduled.get("slot_id"),
            "pair_index": scheduled.get("pair_index"),
            "member_index": scheduled.get("member_index"),
            "member": scheduled.get("member"),
            "paired_mechanical_d4_identity": scheduled.get(
                "paired_mechanical_d4_identity"
            ),
            "representative_definition_hash": scheduled.get(
                "representative_definition_hash"
            ),
            "d4_canonical_hash": scheduled.get("d4_canonical_hash"),
        }
        if any(stored[key] != expected for key, expected in expected_scalar.items()):
            raise ValueError("manifest exact schedule join drifted at {}".format(index))
        definition = _validate_definition_body(
            stored["representative_definition"],
            _sha256(stored["representative_definition_hash"], "definition hash"),
            "manifest representative definition",
        )
        if definition.first_player.value != scheduled.get("first_player"):
            raise ValueError("manifest representative first player drifted")
        if d4_canonical_hash(definition) != stored["d4_canonical_hash"]:
            raise ValueError("manifest representative D4 hash drifted")
        stored_orientations = _exact_list(
            stored["orientations"], "manifest orientations"
        )
        scheduled_orientations = orientation_by_exact.get(stored["exact_slot_id"], [])
        if len(stored_orientations) != len(ATLAS_D4_TRANSFORMS_V1) or len(
            scheduled_orientations
        ) != len(ATLAS_D4_TRANSFORMS_V1):
            raise ValueError("manifest D4 coverage drifted")
        hashes = []
        for transform_index, (orientation, row, transform) in enumerate(
            zip(
                stored_orientations,
                scheduled_orientations,
                ATLAS_D4_TRANSFORMS_V1,
            )
        ):
            _exact_object(
                orientation, _ORIENTATION_ENTRY_FIELDS, "manifest orientation entry"
            )
            expected_orientation = {
                "orientation_slot_index": row.get("orientation_slot_index"),
                "orientation_slot_id": row.get("slot_id"),
                "transform_index": transform_index,
                "transform": transform,
                "transformed_definition_hash": row.get(
                    "transformed_definition_hash"
                ),
                "first_duplicate_transform_index": row.get(
                    "first_duplicate_transform_index"
                ),
            }
            if any(
                orientation[key] != expected
                for key, expected in expected_orientation.items()
            ):
                raise ValueError("manifest orientation schedule join drifted")
            orientation_id = _sha256(
                orientation["orientation_slot_id"], "orientation slot identity"
            )
            if orientation_id in seen_orientation_ids:
                raise ValueError("manifest repeats an orientation slot identity")
            seen_orientation_ids.add(orientation_id)
            transformed = transform_definition(definition, transform)
            expected_body = transformed.to_dict()
            if _canonical_bytes(orientation["definition"]) != _canonical_bytes(
                expected_body
            ):
                raise ValueError("manifest orientation body does not reconstruct")
            transformed_hash = definition_hash(transformed)
            _validate_definition_body(
                orientation["definition"],
                _sha256(
                    orientation["transformed_definition_hash"],
                    "transformed definition hash",
                ),
                "manifest orientation definition",
            )
            hashes.append(transformed_hash)
            if orientation["first_duplicate_transform_index"] != hashes.index(
                transformed_hash
            ):
                raise ValueError("manifest D4 duplicate witness drifted")

    unsigned = {key: manifest[key] for key in _MANIFEST_FIELDS if key != "manifest_root"}
    if manifest["manifest_root"] != _digest(_MANIFEST_ROOT_DOMAIN_V1, unsigned):
        raise ValueError("detached development manifest root drifted")
    if _strict_json_bytes(value, "detached development manifest") != entry:
        raise ValueError("detached development manifest changed during validation")
    return _json_copy(manifest, "validated detached development manifest")


def validate_detached_atlas_development_manifest_v1(
    value: Any, protocol_value: Any
) -> Dict[str, Any]:
    protocol, protocol_entry = _protocol_binding(protocol_value)
    selection_sha, partition_root = _selection_commitments(protocol)
    exact = list(iter_frozen_atlas_exact_schedule_from_protocol_v1(protocol))
    orientations = list(
        iter_frozen_atlas_orientation_schedule_from_protocol_v1(protocol)
    )
    result = _validate_manifest_from_schedules(
        value,
        exact,
        orientations,
        protocol_id=ATLAS_PROTOCOL_ID_V1,
        protocol_root=ATLAS_PROTOCOL_ROOT_V1,
        selection_canonical_sha256=selection_sha,
        selection_partition_root=partition_root,
        fixed_counts=True,
    )
    if _strict_json_bytes(protocol_value, "frozen atlas protocol") != protocol_entry:
        raise ValueError("atlas protocol changed during manifest validation")
    return result


def _manifest_indexes(
    manifest_value: Any, protocol_value: Any
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    manifest = validate_detached_atlas_development_manifest_v1(
        manifest_value, protocol_value
    )
    exact_index = {
        entry["exact_slot_id"]: entry for entry in manifest["definitions"]
    }
    orientation_index = {
        orientation["orientation_slot_id"]: orientation
        for entry in manifest["definitions"]
        for orientation in entry["orientations"]
    }
    return exact_index, orientation_index


def join_exact_slot_to_manifest_definition_v1(
    manifest_value: Any, protocol_value: Any, exact_slot_id: Any
) -> Dict[str, Any]:
    slot_id = _sha256(exact_slot_id, "exact slot identity")
    exact_index, _orientation_index = _manifest_indexes(manifest_value, protocol_value)
    try:
        body = exact_index[slot_id]["representative_definition"]
    except KeyError as error:
        raise ValueError("exact slot is outside the frozen manifest") from error
    return _json_copy(body, "joined exact definition")


def join_orientation_slot_to_manifest_definition_v1(
    manifest_value: Any, protocol_value: Any, orientation_slot_id: Any
) -> Dict[str, Any]:
    slot_id = _sha256(orientation_slot_id, "orientation slot identity")
    _exact_index, orientation_index = _manifest_indexes(manifest_value, protocol_value)
    try:
        body = orientation_index[slot_id]["definition"]
    except KeyError as error:
        raise ValueError("orientation slot is outside the frozen manifest") from error
    return _json_copy(body, "joined orientation definition")


def join_game_slot_to_manifest_definition_v1(
    manifest_value: Any, protocol_value: Any, game_slot_id: Any
) -> Dict[str, Any]:
    slot_id = _sha256(game_slot_id, "game slot identity")
    _exact_index, orientation_index = _manifest_indexes(manifest_value, protocol_value)
    profiles = {
        profile["slot_id"]: profile
        for profile in iter_frozen_atlas_profile_schedule_from_protocol_v1(
            protocol_value
        )
    }
    game = next(
        (
            row
            for row in iter_frozen_atlas_game_schedule_from_protocol_v1(protocol_value)
            if row["slot_id"] == slot_id
        ),
        None,
    )
    if game is None:
        raise ValueError("game slot is outside the frozen protocol")
    try:
        profile = profiles[game["profile_slot_id"]]
        orientation = orientation_index[profile["orientation_slot_id"]]
    except KeyError as error:
        raise ValueError("game slot cannot be joined to the manifest") from error
    if (
        orientation["transformed_definition_hash"]
        != game["transformed_definition_hash"]
    ):
        raise ValueError("game and manifest definition hashes differ")
    return _json_copy(orientation["definition"], "joined game definition")


def iter_joined_atlas_exact_definitions_v1(
    manifest_value: Any, protocol_value: Any
):
    """Iterate the exact schedule with one detached representative body each."""

    protocol_entry = _strict_json_bytes(protocol_value, "frozen atlas protocol")
    manifest = validate_detached_atlas_development_manifest_v1(
        manifest_value, protocol_value
    )
    by_slot = {entry["exact_slot_id"]: entry for entry in manifest["definitions"]}
    rows = list(iter_frozen_atlas_exact_schedule_from_protocol_v1(protocol_value))
    for row in rows:
        try:
            entry = by_slot[row["slot_id"]]
        except KeyError as error:
            raise ValueError("exact schedule cannot be joined to the manifest") from error
        if entry["representative_definition_hash"] != row["representative_definition_hash"]:
            raise ValueError("joined exact definition hash drifted")
    if _strict_json_bytes(protocol_value, "frozen atlas protocol") != protocol_entry:
        raise ValueError("atlas protocol changed during exact join")

    def generate():
        for row in rows:
            yield _json_copy(
                {
                    "slot": row,
                    "definition": by_slot[row["slot_id"]][
                        "representative_definition"
                    ],
                },
                "joined exact definition row",
            )

    return generate()


def iter_joined_atlas_orientation_definitions_v1(
    manifest_value: Any, protocol_value: Any
):
    """Iterate the orientation schedule with one detached transformed body each."""

    protocol_entry = _strict_json_bytes(protocol_value, "frozen atlas protocol")
    manifest = validate_detached_atlas_development_manifest_v1(
        manifest_value, protocol_value
    )
    by_slot = {
        orientation["orientation_slot_id"]: orientation
        for entry in manifest["definitions"]
        for orientation in entry["orientations"]
    }
    rows = list(
        iter_frozen_atlas_orientation_schedule_from_protocol_v1(protocol_value)
    )
    for row in rows:
        try:
            orientation = by_slot[row["slot_id"]]
        except KeyError as error:
            raise ValueError(
                "orientation schedule cannot be joined to the manifest"
            ) from error
        if orientation["transformed_definition_hash"] != row["transformed_definition_hash"]:
            raise ValueError("joined orientation definition hash drifted")
    if _strict_json_bytes(protocol_value, "frozen atlas protocol") != protocol_entry:
        raise ValueError("atlas protocol changed during orientation join")

    def generate():
        for row in rows:
            yield _json_copy(
                {
                    "slot": row,
                    "definition": by_slot[row["slot_id"]]["definition"],
                },
                "joined orientation definition row",
            )

    return generate()


def iter_joined_atlas_game_definitions_v1(
    manifest_value: Any, protocol_value: Any
):
    """Iterate all game slots with bodies via one O(N) protocol join.

    The returned iterator owns a detached snapshot.  No selection object or
    confirmation-candidate coordinate crosses this boundary.
    """

    protocol_entry = _strict_json_bytes(protocol_value, "frozen atlas protocol")
    manifest = validate_detached_atlas_development_manifest_v1(
        manifest_value, protocol_value
    )
    orientations = {
        orientation["orientation_slot_id"]: orientation
        for entry in manifest["definitions"]
        for orientation in entry["orientations"]
    }
    profiles = {
        profile["slot_id"]: profile
        for profile in iter_frozen_atlas_profile_schedule_from_protocol_v1(
            protocol_value
        )
    }
    games = list(iter_frozen_atlas_game_schedule_from_protocol_v1(protocol_value))
    orientation_ids = {}
    for game in games:
        try:
            orientation_slot_id = profiles[game["profile_slot_id"]][
                "orientation_slot_id"
            ]
            orientation = orientations[orientation_slot_id]
        except KeyError as error:
            raise ValueError("game schedule cannot be joined to the manifest") from error
        if orientation["transformed_definition_hash"] != game["transformed_definition_hash"]:
            raise ValueError("joined game definition hash drifted")
        orientation_ids[game["slot_id"]] = orientation_slot_id
    if _strict_json_bytes(protocol_value, "frozen atlas protocol") != protocol_entry:
        raise ValueError("atlas protocol changed during game join")

    def generate():
        for game in games:
            orientation_slot_id = orientation_ids[game["slot_id"]]
            yield _json_copy(
                {
                    "slot": game,
                    "orientation_slot_id": orientation_slot_id,
                    "definition": orientations[orientation_slot_id]["definition"],
                },
                "joined game definition row",
            )

    return generate()


def _ordered_slot_root(kind: str, slot_ids: Sequence[str]) -> str:
    return _digest(
        _SUBSCHEDULE_ROOT_DOMAIN_V1,
        {"ledger_kind": kind, "ordered_slot_ids": list(slot_ids)},
    )


def _ledger_schedule(
    protocol_value: Any, kind: str, strength_identity: Optional[str]
) -> Tuple[List[str], str, str]:
    _protocol, _entry = _protocol_binding(protocol_value)
    if kind == "EXACT":
        rows = list(iter_frozen_atlas_exact_schedule_from_protocol_v1(protocol_value))
        parent_root = ATLAS_EXACT_SCHEDULE_ROOT_V1
    elif kind == "EXACT_PV":
        rows = list(
            iter_frozen_atlas_orientation_schedule_from_protocol_v1(protocol_value)
        )
        parent_root = ATLAS_ORIENTATION_SCHEDULE_ROOT_V1
    elif kind in ("SAMPLED", "TELEMETRY"):
        rows = list(iter_frozen_atlas_game_schedule_from_protocol_v1(protocol_value))
        parent_root = (
            ATLAS_TELEMETRY_SCHEDULE_ROOT_V1
            if kind == "TELEMETRY"
            else ATLAS_GAME_SCHEDULE_ROOT_V1
        )
        if kind == "SAMPLED":
            if strength_identity not in (
                ATLAS_RANDOM_STRENGTH_ID_V1,
                ATLAS_DEPTH1_STRENGTH_ID_V1,
            ):
                raise ValueError("sampled ledger strength identity is not frozen")
            rows = [
                row
                for row in rows
                if row["strength"]["identity"] == strength_identity
            ]
        elif strength_identity is not None:
            raise ValueError("telemetry ledger cannot bind one sampled strength")
    else:
        raise ValueError("unknown atlas ledger kind")
    slot_ids = [row["slot_id"] for row in rows]
    if len(slot_ids) != len(set(slot_ids)):
        raise ValueError("ledger schedule contains duplicate slot identities")
    return slot_ids, parent_root, _ordered_slot_root(kind, slot_ids)


def _strict_id_list(value: Any, expected_ids: Sequence[str], label: str) -> List[str]:
    items = _exact_list(value, label)
    result = [_sha256(item, "{} slot identity".format(label)) for item in items]
    if len(result) != len(set(result)):
        raise ValueError("{} contains duplicate slot identities".format(label))
    if not set(result).issubset(expected_ids):
        raise ValueError("{} contains an unscheduled slot".format(label))
    return result


def _observed_records(
    value: Any, expected_ids: Sequence[str], kind: str
) -> Dict[str, Dict[str, Any]]:
    records = _exact_list(value, "observed status records")
    result = {}
    for record in records:
        _exact_object(
            record,
            ("slot_id", "status", "record_root_or_null"),
            "observed status record",
        )
        slot_id = _sha256(record["slot_id"], "observed slot identity")
        if slot_id in result:
            raise ValueError("observed status records repeat a slot")
        if slot_id not in expected_ids:
            raise ValueError("observed status record is outside the fixed schedule")
        if record["status"] not in _RAW_STATUSES[kind]:
            raise ValueError("observed raw status is not valid for {}".format(kind))
        _sha256(record["record_root_or_null"], "raw record root")
        result[slot_id] = _json_copy(record, "observed status record")
    return result


def _ledger_unsigned(
    kind: str,
    parent_root: str,
    subschedule_root: str,
    strength_identity: Optional[str],
    rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    counts = Counter(row["status"] for row in rows)
    return {
        "ledger_version": ATLAS_STATUS_LEDGER_VERSION_V1,
        "ledger_kind": kind,
        "protocol_id": ATLAS_PROTOCOL_ID_V1,
        "protocol_root": ATLAS_PROTOCOL_ROOT_V1,
        "parent_schedule_root": parent_root,
        "subschedule_root": subschedule_root,
        "strength_identity_or_null": strength_identity,
        "expected_slot_count": len(rows),
        "rows": rows,
        "status_counts": {
            status: counts.get(status, 0) for status in _STATUS_VOCABULARIES[kind]
        },
    }


def _reconcile_ledger(
    kind: str,
    expected_ids: Sequence[str],
    parent_root: str,
    subschedule_root: str,
    strength_identity: Optional[str],
    observed_value: Any,
    started_value: Any,
    *,
    blocked: Any,
    admissible_value: Any = None,
) -> Dict[str, Any]:
    if type(blocked) is not bool:
        raise TypeError("blocked must be an exact boolean")
    observed = _observed_records(observed_value, expected_ids, kind)
    started = set(_strict_id_list(started_value, expected_ids, "started slots"))
    if not set(observed).issubset(started):
        raise ValueError("every observed raw record must have a start marker")
    admissible: Optional[set] = None
    if kind == "TELEMETRY":
        admissible = set(
            _strict_id_list(admissible_value, expected_ids, "admissible slots")
        )
        if not started.issubset(admissible) or not set(observed).issubset(admissible):
            raise ValueError("telemetry attempts must be sampled-trace admissible")
    elif admissible_value is not None:
        raise ValueError("only telemetry reconciliation accepts admissible slots")
    if blocked and (observed or started):
        raise ValueError("a blocked stage cannot contain attempted raw records")

    rows = []
    for slot_id in expected_ids:
        if blocked:
            status = "BLOCKED"
            origin = "RECONCILED_BLOCKED"
            record_root = None
        elif slot_id in observed:
            status = observed[slot_id]["status"]
            origin = "RAW_RECORD"
            record_root = observed[slot_id]["record_root_or_null"]
        elif slot_id in started:
            status = _INTERRUPTED_STATUS[kind]
            origin = "RECONCILED_STARTED"
            record_root = None
        elif kind == "TELEMETRY" and slot_id not in admissible:
            status = "NOT_ADMISSIBLE"
            origin = "RECONCILED_NONADMISSIBLE"
            record_root = None
        elif kind == "TELEMETRY":
            status = "MISSING"
            origin = "RECONCILED_UNOBSERVED"
            record_root = None
        else:
            status = "NOT_RUN"
            origin = "RECONCILED_UNOBSERVED"
            record_root = None
        rows.append(
            {
                "slot_id": slot_id,
                "status": status,
                "origin": origin,
                "record_root_or_null": record_root,
            }
        )
    unsigned = _ledger_unsigned(
        kind, parent_root, subschedule_root, strength_identity, rows
    )
    return {**unsigned, "ledger_root": _digest(_LEDGER_ROOT_DOMAIN_V1, unsigned)}


def _validate_ledger(
    value: Any,
    kind: str,
    expected_ids: Sequence[str],
    parent_root: str,
    subschedule_root: str,
    strength_identity: Optional[str],
) -> Dict[str, Any]:
    entry = _strict_json_bytes(value, "atlas status ledger")
    ledger = json.loads(entry.decode("utf-8"))
    _exact_object(ledger, _LEDGER_FIELDS, "atlas status ledger")
    expected_header = {
        "ledger_version": ATLAS_STATUS_LEDGER_VERSION_V1,
        "ledger_kind": kind,
        "protocol_id": ATLAS_PROTOCOL_ID_V1,
        "protocol_root": ATLAS_PROTOCOL_ROOT_V1,
        "parent_schedule_root": parent_root,
        "subschedule_root": subschedule_root,
        "strength_identity_or_null": strength_identity,
        "expected_slot_count": len(expected_ids),
    }
    if any(ledger[key] != expected for key, expected in expected_header.items()):
        raise ValueError("atlas status ledger binding drifted")
    rows = _exact_list(ledger["rows"], "atlas status ledger rows")
    if len(rows) != len(expected_ids):
        raise ValueError("atlas status ledger denominator drifted")
    for expected_id, row in zip(expected_ids, rows):
        _exact_object(row, _LEDGER_ROW_FIELDS, "atlas status ledger row")
        if row["slot_id"] != expected_id:
            raise ValueError("atlas status ledger row order or identity drifted")
        if row["status"] not in _STATUS_VOCABULARIES[kind]:
            raise ValueError("atlas status ledger contains an unknown status")
        origin = row["origin"]
        record_root = row["record_root_or_null"]
        if origin == "RAW_RECORD":
            if row["status"] not in _RAW_STATUSES[kind]:
                raise ValueError("raw ledger row has a reconciled-only status")
            _sha256(record_root, "raw record root")
        elif origin == "RECONCILED_STARTED":
            if row["status"] != _INTERRUPTED_STATUS[kind] or record_root is not None:
                raise ValueError("started reconciliation row is inconsistent")
        elif origin == "RECONCILED_UNOBSERVED":
            expected_statuses = {"MISSING"} if kind == "TELEMETRY" else {"NOT_RUN"}
            if row["status"] not in expected_statuses or record_root is not None:
                raise ValueError("unobserved reconciliation row is inconsistent")
        elif origin == "RECONCILED_NONADMISSIBLE":
            if (
                kind != "TELEMETRY"
                or row["status"] != "NOT_ADMISSIBLE"
                or record_root is not None
            ):
                raise ValueError("nonadmissible reconciliation row is inconsistent")
        elif origin == "RECONCILED_BLOCKED":
            if row["status"] != "BLOCKED" or record_root is not None:
                raise ValueError("blocked reconciliation row is inconsistent")
        else:
            raise ValueError("atlas status ledger contains an unknown origin")
    counts = Counter(row["status"] for row in rows)
    expected_counts = {
        status: counts.get(status, 0) for status in _STATUS_VOCABULARIES[kind]
    }
    if type(ledger["status_counts"]) is not dict or ledger["status_counts"] != expected_counts:
        raise ValueError("atlas status ledger counts do not reconstruct")
    unsigned = {key: ledger[key] for key in _LEDGER_FIELDS if key != "ledger_root"}
    if ledger["ledger_root"] != _digest(_LEDGER_ROOT_DOMAIN_V1, unsigned):
        raise ValueError("atlas status ledger root drifted")
    if _strict_json_bytes(value, "atlas status ledger") != entry:
        raise ValueError("atlas status ledger changed during validation")
    return _json_copy(ledger, "validated atlas status ledger")


def reconcile_atlas_exact_status_ledger_v1(
    protocol_value: Any,
    observed_records: Any,
    started_slot_ids: Any,
    *,
    blocked: bool = False,
) -> Dict[str, Any]:
    ids, parent, subset = _ledger_schedule(protocol_value, "EXACT", None)
    result = _reconcile_ledger(
        "EXACT", ids, parent, subset, None, observed_records, started_slot_ids, blocked=blocked
    )
    return _validate_ledger(result, "EXACT", ids, parent, subset, None)


def validate_atlas_exact_status_ledger_v1(
    value: Any, protocol_value: Any
) -> Dict[str, Any]:
    ids, parent, subset = _ledger_schedule(protocol_value, "EXACT", None)
    return _validate_ledger(value, "EXACT", ids, parent, subset, None)


def reconcile_atlas_pv_status_ledger_v1(
    protocol_value: Any,
    observed_records: Any,
    started_slot_ids: Any,
    *,
    blocked: bool = False,
) -> Dict[str, Any]:
    ids, parent, subset = _ledger_schedule(protocol_value, "EXACT_PV", None)
    result = _reconcile_ledger(
        "EXACT_PV", ids, parent, subset, None, observed_records, started_slot_ids, blocked=blocked
    )
    return _validate_ledger(result, "EXACT_PV", ids, parent, subset, None)


def validate_atlas_pv_status_ledger_v1(
    value: Any, protocol_value: Any
) -> Dict[str, Any]:
    ids, parent, subset = _ledger_schedule(protocol_value, "EXACT_PV", None)
    return _validate_ledger(value, "EXACT_PV", ids, parent, subset, None)


def reconcile_atlas_sampled_status_ledger_v1(
    protocol_value: Any,
    strength_identity: Any,
    observed_records: Any,
    started_slot_ids: Any,
    *,
    blocked: bool = False,
) -> Dict[str, Any]:
    if type(strength_identity) is not str:
        raise TypeError("sampled strength identity must be an exact string")
    ids, parent, subset = _ledger_schedule(
        protocol_value, "SAMPLED", strength_identity
    )
    result = _reconcile_ledger(
        "SAMPLED",
        ids,
        parent,
        subset,
        strength_identity,
        observed_records,
        started_slot_ids,
        blocked=blocked,
    )
    return _validate_ledger(
        result, "SAMPLED", ids, parent, subset, strength_identity
    )


def validate_atlas_sampled_status_ledger_v1(
    value: Any, protocol_value: Any, strength_identity: Any = None
) -> Dict[str, Any]:
    if strength_identity is None:
        candidate = _json_copy(value, "sampled status ledger")
        if type(candidate) is not dict:
            raise TypeError("sampled status ledger must be an exact object")
        strength_identity = candidate.get("strength_identity_or_null")
    if type(strength_identity) is not str:
        raise TypeError("sampled strength identity must be an exact string")
    ids, parent, subset = _ledger_schedule(
        protocol_value, "SAMPLED", strength_identity
    )
    return _validate_ledger(
        value, "SAMPLED", ids, parent, subset, strength_identity
    )


def reconcile_atlas_telemetry_status_ledger_v1(
    protocol_value: Any,
    observed_records: Any,
    started_slot_ids: Any,
    admissible_slot_ids: Any,
    *,
    blocked: bool = False,
) -> Dict[str, Any]:
    ids, parent, subset = _ledger_schedule(protocol_value, "TELEMETRY", None)
    result = _reconcile_ledger(
        "TELEMETRY",
        ids,
        parent,
        subset,
        None,
        observed_records,
        started_slot_ids,
        blocked=blocked,
        admissible_value=admissible_slot_ids,
    )
    return _validate_ledger(result, "TELEMETRY", ids, parent, subset, None)


def validate_atlas_telemetry_status_ledger_v1(
    value: Any, protocol_value: Any
) -> Dict[str, Any]:
    ids, parent, subset = _ledger_schedule(protocol_value, "TELEMETRY", None)
    return _validate_ledger(value, "TELEMETRY", ids, parent, subset, None)


def validate_complete_atlas_trace_v1(
    definition_value: Any, trace_value: Any
) -> Dict[str, Any]:
    """Replay one claimed-complete trace directly through the pure engine."""

    definition_entry = _strict_json_bytes(definition_value, "trace definition")
    trace_entry = _strict_json_bytes(trace_value, "complete trace")
    definition_body = json.loads(definition_entry.decode("utf-8"))
    definition = parse_definition(definition_body)
    if _canonical_bytes(definition.to_dict()) != definition_entry:
        raise ValueError("trace definition is not a canonical DSL body")
    if definition.max_plies > ATLAS_GAME_PLY_CAP_V1:
        raise ValueError("trace definition exceeds the frozen game ply cap")
    trace = json.loads(trace_entry.decode("utf-8"))
    _exact_object(
        trace,
        (
            "trace_version",
            "definition_hash",
            "actions",
            "plies",
            "winner",
            "terminal_reason",
        ),
        "complete trace",
    )
    if trace["trace_version"] != ATLAS_COMPLETE_TRACE_VERSION_V1:
        raise ValueError("complete trace version drifted")
    expected_definition_hash = _sha256(
        trace["definition_hash"], "trace definition hash"
    )
    if definition_hash(definition) != expected_definition_hash:
        raise ValueError("trace definition hash differs from the supplied definition")
    actions = _exact_list(trace["actions"], "complete trace actions")
    plies = _exact_int(trace["plies"], "trace plies")
    if len(actions) != plies or plies > ATLAS_GAME_PLY_CAP_V1:
        raise ValueError("complete trace ply count exceeds or differs from its actions")
    if trace["winner"] not in (None, Player.A.value, Player.B.value):
        raise ValueError("complete trace winner is invalid")
    if type(trace["terminal_reason"]) is not str:
        raise TypeError("complete trace terminal reason must be an exact string")

    state = initial_state(definition)
    for raw_action in actions:
        if state.terminal:
            raise ValueError("complete trace acts after a terminal state")
        available = legal_actions(definition, state)
        if len(available) > ATLAS_ACTION_CANDIDATE_CAP_V1:
            raise ValueError("trace state exceeds the frozen legal-action cap")
        action = action_from_dict(raw_action)
        if action not in available:
            raise ValueError("complete trace contains an illegal action")
        if _canonical_bytes(action.to_dict()) != _canonical_bytes(raw_action):
            raise ValueError("complete trace action is not canonical")
        state = apply_action(definition, state, action)
    if not state.terminal or state.outcome is None:
        raise ValueError("complete trace does not reach a terminal state")
    observed_winner = (
        state.outcome.winner.value if state.outcome.winner is not None else None
    )
    if (
        state.ply != plies
        or observed_winner != trace["winner"]
        or state.outcome.reason != trace["terminal_reason"]
    ):
        raise ValueError("complete trace terminal claim does not replay")
    if _strict_json_bytes(definition_value, "trace definition") != definition_entry:
        raise ValueError("trace definition changed during replay")
    if _strict_json_bytes(trace_value, "complete trace") != trace_entry:
        raise ValueError("complete trace changed during replay")
    return _json_copy(trace, "validated complete trace")


__all__ = (
    "ATLAS_COMPLETE_TRACE_VERSION_V1",
    "ATLAS_DEPTH1_STRENGTH_ID_V1",
    "ATLAS_DETACHED_MANIFEST_ID_V1",
    "ATLAS_RANDOM_STRENGTH_ID_V1",
    "ATLAS_STAGE_DATA_VERSION_V1",
    "ATLAS_STATUS_LEDGER_VERSION_V1",
    "build_detached_atlas_development_manifest_v1",
    "join_exact_slot_to_manifest_definition_v1",
    "join_game_slot_to_manifest_definition_v1",
    "join_orientation_slot_to_manifest_definition_v1",
    "iter_joined_atlas_exact_definitions_v1",
    "iter_joined_atlas_game_definitions_v1",
    "iter_joined_atlas_orientation_definitions_v1",
    "reconcile_atlas_exact_status_ledger_v1",
    "reconcile_atlas_pv_status_ledger_v1",
    "reconcile_atlas_sampled_status_ledger_v1",
    "reconcile_atlas_telemetry_status_ledger_v1",
    "validate_atlas_exact_status_ledger_v1",
    "validate_atlas_pv_status_ledger_v1",
    "validate_atlas_sampled_status_ledger_v1",
    "validate_atlas_telemetry_status_ledger_v1",
    "validate_complete_atlas_trace_v1",
    "validate_detached_atlas_development_manifest_v1",
)
