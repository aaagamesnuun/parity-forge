"""Pure outcome-free construction for the Plan-0013 development atlas.

The module fixes the final six-family registry and 3+3 search envelope, pairs
the A-first and B-first members of every eligible setup, and applies only a
definition-identity history projection when selecting the development and
future-candidate blocks.  It performs no filesystem access, play, solving,
agent evaluation, replay analysis, or experiment execution.

Human-readable registry IDs are retained for lookup and reports.  Mechanical
pair identity, representative orientation, and rank use only the name-free
family signature, first-player-free stratum, and first-player-free mechanical
definition bytes.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .atlas_projection import (
    ATLAS_PRIOR_GAMEPLAY_EXPOSURE_KIND_V1,
    ATLAS_SYNTHETIC_FIXTURE_EXPOSURE_KIND_V1,
    validate_atlas_identity_projection_v1,
)
from .dsl import GameDefinition, Player, definition_hash, parse_definition
from .family import (
    FamilyRecord,
    FamilyRegistry,
    family_registry_hash,
    validate_nonretired_family_registry,
)
from .feasibility import (
    FEASIBILITY_COMPILER_ID,
    FEASIBILITY_COMPILER_VERSION,
    FEASIBILITY_D4_CANONICALIZATION_ID,
    FEASIBILITY_D4_CANONICALIZATION_VERSION,
    FEASIBILITY_INPUT_COUNT_V1,
    VectorProfileV1,
    build_feasibility_domain_v1,
    build_state_work_proof_v1,
    compile_feasibility_definition_v1,
    feasibility_domain_hash_v1,
    provisional_family_signature_v1,
)
from .feasibility_census import (
    FEASIBILITY_CENSUS_EVIDENCE_DIGEST_V1,
    FEASIBILITY_ORDERED_CASE_TO_D4_ROOT_V1,
    FEASIBILITY_SORTED_ELIGIBLE_D4_ROOT_V1,
    enumerate_feasibility_case_descriptors_v1,
)
from .symmetry import (
    D4_TRANSFORMS,
    canonicalize_d4,
    transform_definition,
)


ATLAS_REGISTRY_VERSION_V1 = 1
ATLAS_ENVELOPE_VERSION_V1 = 1
ATLAS_PAIRED_UNIVERSE_VERSION_V1 = 1
ATLAS_SELECTION_VERSION_V1 = 1

ATLAS_REGISTRY_ID_V1 = "plan0013-final-six-family-registry-v1"
ATLAS_ENVELOPE_ID_V1 = "plan0013-six-family-3x3-envelope-v1"
ATLAS_PAIRED_UNIVERSE_ID_V1 = "plan0013-matched-pair-universe-v1"
ATLAS_SELECTION_ID_V1 = "plan0013-development-candidate-selection-v1"

ATLAS_FAMILY_COUNT_V1 = 6
ATLAS_PAIRED_STRATUM_COUNT_V1 = 44
ATLAS_RAW_EXACT_SETUP_PAIR_COUNT_V1 = 73_920
ATLAS_ELIGIBLE_EXACT_SETUP_PAIR_COUNT_V1 = 27_952
ATLAS_ELIGIBLE_PAIRED_D4_COUNT_V1 = 8_854
ATLAS_DEVELOPMENT_PAIR_COUNT_V1 = 144
ATLAS_CANDIDATE_PAIR_COUNT_V1 = 144
ATLAS_DEVELOPMENT_DEFINITION_COUNT_V1 = 288
ATLAS_CANDIDATE_DEFINITION_COUNT_V1 = 288
ATLAS_D4_COMMUTATION_CHECK_COUNT_V1 = (
    ATLAS_ELIGIBLE_PAIRED_D4_COUNT_V1 * len(D4_TRANSFORMS)
)
ATLAS_DEFERRED_2X2_RAW_EXACT_SETUP_PAIR_COUNT_V1 = 33_264
ATLAS_DEFERRED_2X2_RAW_DEFINITION_COUNT_V1 = 66_528
ATLAS_DEFERRED_2X2_ELIGIBLE_EXACT_SETUP_PAIR_COUNT_V1 = 7_740
ATLAS_DEFERRED_2X2_ELIGIBLE_EXACT_DEFINITION_COUNT_V1 = 15_480
ATLAS_DEFERRED_2X2_ELIGIBLE_PAIRED_D4_COUNT_V1 = 3_250
ATLAS_DEFERRED_2X2_ELIGIBLE_PAIRED_D4_DEFINITION_COUNT_V1 = 6_500
ATLAS_DEFERRED_2X2_SUPPORTED_PAIRED_STRATUM_COUNT_V1 = 28
ATLAS_DEFERRED_2X2_SUPPORTED_MEMBER_STRATUM_COUNT_V1 = 56
ATLAS_DEFERRED_2X2_UNSUPPORTED_PAIRED_STRATUM_COUNT_V1 = 16
ATLAS_DEFERRED_2X2_UNSUPPORTED_MEMBER_STRATUM_COUNT_V1 = 32

_ATLAS_PARENT_ELIGIBLE_EXACT_DEFINITION_COUNT_V1 = 71_384
_ATLAS_PARENT_ELIGIBLE_D4_DEFINITION_COUNT_V1 = 24_208

ATLAS_PARENT_DOMAIN_HASH_V1 = (
    "3456b5873dadfd177639b4c0d062bad6717d328a7ebee88a71f4294f9a5b0bc5"
)
ATLAS_PARENT_CENSUS_DIGEST_V1 = FEASIBILITY_CENSUS_EVIDENCE_DIGEST_V1
ATLAS_PARENT_CASE_TO_D4_ROOT_V1 = FEASIBILITY_ORDERED_CASE_TO_D4_ROOT_V1
ATLAS_PARENT_ELIGIBLE_D4_ROOT_V1 = FEASIBILITY_SORTED_ELIGIBLE_D4_ROOT_V1
ATLAS_FINAL_REGISTRY_ROOT_V1 = (
    "535e9936b7f260ad5dedb7409a6f0ef7a3af6b2ea4b31c9618529dd009298dc5"
)
ATLAS_SEARCH_ENVELOPE_ROOT_V1 = (
    "eb875a7d0da3319e50b6f662f48366f472348afda42c7a425bf42f5c05f6ead5"
)
ATLAS_PAIRED_UNIVERSE_WITNESS_ROOT_V1 = (
    "1167ac8d919f7d07ac8ed7680661bea22b3501349ced3be187f5c2518cecab15"
)
ATLAS_PRIOR_GAMEPLAY_PROJECTION_ROOT_V1 = (
    "b7461dbe226d436e1fd50a33cb0987efdff225626aea8105e99daa9eb4f59e9a"
)
ATLAS_SYNTHETIC_FIXTURE_PROJECTION_ROOT_V1 = (
    "67658d8b0683ad415f229d4d01a4315aa4ca33f56187c5d0eeecfc8974a70f1f"
)
ATLAS_HISTORY_BINDING_ROOT_V1 = (
    "6e99ceca9008897f0c9f2b006e9541a23c7ed8cf2d5069e54a55bc278f8ab08d"
)
ATLAS_COLLISION_ROOT_V1 = (
    "b6b7f14e82ccc18bcb73dbbbadb2cc302c6d385fc94d8f0d3418da2b84fab354"
)
ATLAS_SELECTION_PARTITION_ROOT_V1 = (
    "de65bf682bc5f0e02dc36eaee9fa932d5cfa77355277c3ce0fa41a6379967830"
)
ATLAS_CANONICAL_SELECTION_SHA256_V1 = (
    "b681c32bb06f6a3ab03cd53735a52d8838560a5fbad3e17b0c0e9f3158cb68b5"
)

_FAMILY_IDS_V1 = (
    "push-hop-race-v1",
    "swap-hop-network-v1",
    "convert-push-front-v1",
    "capture-hop-hunt-v1",
    "convert-capture-duel-v1",
    "push-swap-networks-v1",
)

_EXPECTED_FAMILY_PAIRED_D4_COUNTS_V1 = {
    "push-hop-race-v1": 728,
    "swap-hop-network-v1": 1_584,
    "convert-push-front-v1": 1_576,
    "capture-hop-hunt-v1": 832,
    "convert-capture-duel-v1": 906,
    "push-swap-networks-v1": 3_228,
}
_EXPECTED_MULTIPLICITY_HISTOGRAM_V1 = {
    "1": 688,
    "2": 4_236,
    "4": 3_162,
    "8": 768,
}

_REGISTRY_RECORD_ROOT_DOMAIN_V1 = b"parity-forge:plan0013:registry-records:v1\0"
_ENVELOPE_ROOT_DOMAIN_V1 = b"parity-forge:plan0013:search-envelope:v1\0"
_PAIRED_STRATUM_ID_DOMAIN_V1 = b"parity-forge:plan0013:paired-stratum:v1\0"
_PAIR_D4_ID_DOMAIN_V1 = b"parity-forge:plan0013:paired-mechanical-d4:v1\0"
_PAIR_RANK_DOMAIN_V1 = b"parity-forge:plan0013:pair-rank:v1\0"
_PAIR_EXACT_ROOT_DOMAIN_V1 = b"parity-forge:plan0013:pair-exact-members:v1\0"
_PAIRED_INPUT_ID_DOMAIN_V1 = b"parity-forge:plan0013:paired-input:v1\0"
_PAIR_EXACT_WITNESS_ROOT_DOMAIN_V1 = (
    b"parity-forge:plan0013:pair-exact-correspondence:v1\0"
)
_PAIR_INVARIANT_DOMAIN_V1 = b"parity-forge:plan0013:pair-invariant:v1\0"
_PAIR_WORK_PROOF_DOMAIN_V1 = b"parity-forge:plan0013:pair-work-proof:v1\0"
_PAIR_COMMUTATION_DOMAIN_V1 = b"parity-forge:plan0013:pair-commutation:v1\0"
_MEMBER_D4_SLOT_ROOT_DOMAIN_V1 = (
    b"parity-forge:plan0013:member-d4-exact-slots:v1\0"
)
_DEFERRED_MEMBER_STRATA_ROOT_DOMAIN_V1 = (
    b"parity-forge:plan0013:deferred-2x2-member-strata-root:v1\0"
)
_DEFERRED_PAIRED_STRATA_ROOT_DOMAIN_V1 = (
    b"parity-forge:plan0013:deferred-2x2-paired-strata-root:v1\0"
)
_DEFERRED_TWO_PLUS_TWO_ROOT_DOMAIN_V1 = (
    b"parity-forge:plan0013:deferred-2x2-contract:v1\0"
)
_DEFERRED_EXACT_PAIR_ID_DOMAIN_V1 = (
    b"parity-forge:plan0013:deferred-2x2-exact-pair-id:v1\0"
)
_DEFERRED_EXACT_PAIR_ROOT_DOMAIN_V1 = (
    b"parity-forge:plan0013:deferred-2x2-exact-pair-root:v1\0"
)
_DEFERRED_PAIRED_D4_ID_DOMAIN_V1 = (
    b"parity-forge:plan0013:deferred-2x2-paired-d4-id:v1\0"
)
_DEFERRED_PAIRED_D4_ROOT_DOMAIN_V1 = (
    b"parity-forge:plan0013:deferred-2x2-paired-d4-root:v1\0"
)
_PAIR_WITNESS_DOMAIN_V1 = b"parity-forge:plan0013:pair-witness:v1\0"
_STRATUM_UNIVERSE_DOMAIN_V1 = b"parity-forge:plan0013:stratum-universe:v1\0"
_UNIVERSE_ROOT_DOMAIN_V1 = b"parity-forge:plan0013:paired-universe:v1\0"
_HISTORY_BINDING_DOMAIN_V1 = b"parity-forge:plan0013:history-binding:v1\0"
_COLLISION_ROOT_DOMAIN_V1 = b"parity-forge:plan0013:history-collisions:v1\0"
_PARTITION_MEMBER_DOMAIN_V1 = b"parity-forge:plan0013:partition-member:v1\0"
_STRATUM_PARTITION_DOMAIN_V1 = b"parity-forge:plan0013:stratum-partition:v1\0"
_SELECTION_ROOT_DOMAIN_V1 = b"parity-forge:plan0013:selection-partition:v1\0"

_MAX_JSON_NODES_V1 = 10_000_000
_MAX_JSON_DEPTH_V1 = 40


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
        raise ValueError("atlas values must be finite canonical JSON") from error


def _domain_digest(domain: bytes, value: Any) -> str:
    return hashlib.sha256(domain + _canonical_bytes(value)).hexdigest()


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


def _without_first_player_stratum(stratum: Mapping[str, Any]) -> Dict[str, Any]:
    value = _json_copy(dict(stratum), "feasibility stratum")
    first_player = value.pop("first_player", None)
    if first_player not in ("A", "B"):
        raise ValueError("feasibility stratum must retain one first player")
    if value.get("setup") != {"A_count": 3, "B_count": 3}:
        raise ValueError("atlas accepts only the balanced 3+3 setup")
    return value


def _descriptor_pair_invariant(
    family_signature_digest: str,
    neutral_stratum: Mapping[str, Any],
    descriptor: Mapping[str, Any],
) -> Dict[str, Any]:
    return {
        "family_signature_hash": family_signature_digest,
        "stratum": _json_copy(neutral_stratum, "neutral stratum"),
        "gate": _json_copy(descriptor["gate"], "feasibility gate"),
        "descriptors": _json_copy(
            descriptor["descriptors"], "feasibility descriptors"
        ),
    }


def _neutral_d4_value(canonicalization: Any) -> Dict[str, Any]:
    value = json.loads(canonicalization.mechanical_json)
    first_player = value.pop("first_player", None)
    if first_player not in ("A", "B"):
        raise ValueError("canonical definition lacks a valid first player")
    if "name" in value:
        raise AssertionError("mechanical D4 JSON unexpectedly retained a name")
    return value


def _neutral_definition_value(definition: GameDefinition) -> Dict[str, Any]:
    canonicalization = canonicalize_d4(definition)
    return _neutral_d4_value(canonicalization)


def _representative_definition(
    neutral_value: Mapping[str, Any], pair_d4_identity: str, player: str
) -> GameDefinition:
    if player not in ("A", "B"):
        raise ValueError("representative first player must be A or B")
    value = _json_copy(dict(neutral_value), "neutral representative definition")
    value["first_player"] = player
    value["name"] = "pf13-{}-{}-first".format(
        pair_d4_identity[:24], player.lower()
    )
    return parse_definition(value)


def _paired_stratum_id(
    family_signature_digest: str, neutral_stratum: Mapping[str, Any]
) -> str:
    return _domain_digest(
        _PAIRED_STRATUM_ID_DOMAIN_V1,
        {
            "family_signature_hash": family_signature_digest,
            "stratum": dict(neutral_stratum),
        },
    )


def _pair_rank_digest(
    family_signature_digest: str,
    neutral_stratum: Mapping[str, Any],
    pair_d4_identity: str,
) -> str:
    """Return the rank digest from mechanical inputs alone."""

    return _domain_digest(
        _PAIR_RANK_DOMAIN_V1,
        {
            "family_signature_hash": family_signature_digest,
            "stratum": dict(neutral_stratum),
            "paired_mechanical_d4_identity": pair_d4_identity,
        },
    )


def _strip_first_player(definition: GameDefinition) -> Dict[str, Any]:
    value = definition.to_dict()
    value.pop("name")
    value.pop("first_player")
    return value


def _commutation_evidence(
    a_definition: GameDefinition, b_definition: GameDefinition
) -> Tuple[int, str, List[str], str, List[str], str]:
    records = []
    a_slot_hashes = []
    b_slot_hashes = []
    for transform in D4_TRANSFORMS:
        a_transformed = transform_definition(
            a_definition, transform, name=a_definition.name
        )
        b_transformed = transform_definition(
            b_definition, transform, name=b_definition.name
        )
        a_neutral = _strip_first_player(a_transformed)
        b_neutral = _strip_first_player(b_transformed)
        if _canonical_bytes(a_neutral) != _canonical_bytes(b_neutral):
            raise ValueError("first-player toggle does not commute with D4")
        a_hash = definition_hash(a_transformed)
        b_hash = definition_hash(b_transformed)
        a_slot_hashes.append(a_hash)
        b_slot_hashes.append(b_hash)
        records.append(
            {
                "transform": transform,
                "neutral_mechanical_digest": hashlib.sha256(
                    _canonical_bytes(a_neutral)
                ).hexdigest(),
                "member_exact_definition_hashes": {
                    "A_FIRST": a_hash,
                    "B_FIRST": b_hash,
                },
            }
        )
    a_root = _domain_digest(
        _MEMBER_D4_SLOT_ROOT_DOMAIN_V1,
        {
            "first_player": "A",
            "ordered_transforms": list(D4_TRANSFORMS),
            "exact_definition_hashes": a_slot_hashes,
        },
    )
    b_root = _domain_digest(
        _MEMBER_D4_SLOT_ROOT_DOMAIN_V1,
        {
            "first_player": "B",
            "ordered_transforms": list(D4_TRANSFORMS),
            "exact_definition_hashes": b_slot_hashes,
        },
    )
    return (
        len(records),
        _domain_digest(_PAIR_COMMUTATION_DOMAIN_V1, records),
        a_slot_hashes,
        a_root,
        b_slot_hashes,
        b_root,
    )


def build_atlas_family_registry_v1() -> FamilyRegistry:
    """Return the final ordered, nonretired six-family registry."""

    registry = FamilyRegistry(
        FamilyRecord(family_id, provisional_family_signature_v1(family_id))
        for family_id in _FAMILY_IDS_V1
    )
    registry = validate_nonretired_family_registry(registry)
    if family_registry_hash(registry) != ATLAS_FINAL_REGISTRY_ROOT_V1:
        raise AssertionError("final atlas registry root drifted")
    return registry


def _goal_frames_by_family() -> Dict[str, Tuple[str, ...]]:
    domain = build_feasibility_domain_v1()
    records = domain["families"]
    observed_ids = tuple(record["family_id"] for record in records)
    if observed_ids != _FAMILY_IDS_V1:
        raise AssertionError("feasibility family order differs from final registry")
    return {
        record["family_id"]: tuple(record["goal_frames"])
        for record in records
    }


def _quota_for_goal_frame_count(count: int) -> int:
    try:
        return {3: 2, 2: 3, 1: 6}[count]
    except KeyError as error:
        raise AssertionError("atlas goal-frame count has no declared quota") from error


def _ordered_paired_strata() -> Tuple[Dict[str, Any], ...]:
    registry = build_atlas_family_registry_v1()
    goal_frames = _goal_frames_by_family()
    records = []
    for family in registry:
        signature_digest = family.semantic_hash
        family_frames = goal_frames[family.family_id]
        quota = _quota_for_goal_frame_count(len(family_frames))
        for frame in family_frames:
            for a_profile in VectorProfileV1:
                for b_profile in VectorProfileV1:
                    stratum = {
                        "goal_frame": frame,
                        "setup": {"A_count": 3, "B_count": 3},
                        "vector_profiles": {
                            "A": a_profile.value,
                            "B": b_profile.value,
                        },
                    }
                    records.append(
                        {
                            "family_id": family.family_id,
                            "family_signature_hash": signature_digest,
                            "paired_stratum_id": _paired_stratum_id(
                                signature_digest, stratum
                            ),
                            "stratum": stratum,
                            "pair_quota": quota,
                            "definition_quota": 2 * quota,
                            "development_pair_count": quota,
                            "development_definition_count": 2 * quota,
                            "candidate_pair_count": quota,
                            "candidate_definition_count": 2 * quota,
                        }
                    )
    if len(records) != ATLAS_PAIRED_STRATUM_COUNT_V1:
        raise AssertionError("paired stratum product drifted")
    return tuple(records)


def _build_deferred_two_plus_two_contract() -> Dict[str, Any]:
    """Re-enumerate the complete 2+2 census slice and bind its deferral."""

    registry = build_atlas_family_registry_v1()
    signature_by_family = {
        record.family_id: record.semantic_hash for record in registry
    }
    member_order = []
    member_accumulators: Dict[str, Dict[str, Any]] = {}
    paired_orbits: Dict[Tuple[str, str, str, str], set] = defaultdict(set)
    eligible_exact_pair_witnesses = []
    pending: Optional[Tuple[Any, Dict[str, Any]]] = None
    raw_pair_count = 0
    eligible_pair_count = 0

    for case, descriptor in enumerate_feasibility_case_descriptors_v1(2):
        stratum_id = descriptor["stratum_id"]
        accumulator = member_accumulators.get(stratum_id)
        reasons = set(descriptor["gate"]["rejection_reasons"])
        if accumulator is None:
            accumulator = {
                "family_id": case.family_id,
                "family_signature_hash": signature_by_family[case.family_id],
                "parent_feasibility_stratum_id": stratum_id,
                "stratum": _json_copy(descriptor["stratum"], "2+2 stratum"),
                "raw_exact_definition_count": 0,
                "eligible_exact_definition_count": 0,
                "eligible_d4_hashes": set(),
                "universal_rejection_reasons": reasons,
            }
            member_accumulators[stratum_id] = accumulator
            member_order.append(stratum_id)
        else:
            if (
                accumulator["family_id"] != case.family_id
                or _canonical_bytes(accumulator["stratum"])
                != _canonical_bytes(descriptor["stratum"])
            ):
                raise ValueError("one parent feasibility stratum changed identity")
            accumulator["universal_rejection_reasons"].intersection_update(
                reasons
            )
        accumulator["raw_exact_definition_count"] += 1
        if descriptor["gate"]["eligible"]:
            accumulator["eligible_exact_definition_count"] += 1
            accumulator["eligible_d4_hashes"].add(
                descriptor["d4_canonical_hash"]
            )

        if pending is None:
            if case.first_player is not Player.A:
                raise AssertionError("2+2 descriptor order no longer begins A-first")
            pending = (case, descriptor)
            continue
        a_case, a_descriptor = pending
        pending = None
        if case.first_player is not Player.B:
            raise AssertionError("2+2 descriptor order no longer pairs B-first")
        if _case_pair_key(a_case) != _case_pair_key(case):
            raise ValueError("adjacent 2+2 first-player cases do not share setup")
        if a_descriptor["gate"]["eligible"] != descriptor["gate"]["eligible"]:
            raise ValueError("paired 2+2 members disagree on feasibility")
        raw_pair_count += 1
        if descriptor["gate"]["eligible"]:
            eligible_pair_count += 1
            neutral_key = (
                case.family_id,
                case.goal_frame.value,
                case.a_vector_profile.value,
                case.b_vector_profile.value,
            )
            paired_orbits[neutral_key].add(
                (
                    a_descriptor["d4_canonical_hash"],
                    descriptor["d4_canonical_hash"],
                )
            )
            neutral_stratum = {
                "goal_frame": case.goal_frame.value,
                "setup": {"A_count": 2, "B_count": 2},
                "vector_profiles": {
                    "A": case.a_vector_profile.value,
                    "B": case.b_vector_profile.value,
                },
            }
            exact_witness = {
                "family_signature_hash": signature_by_family[case.family_id],
                "paired_stratum_id": _paired_stratum_id(
                    signature_by_family[case.family_id], neutral_stratum
                ),
                "ordered_case_input_hashes": {
                    "A_FIRST": a_descriptor["case_input_hash"],
                    "B_FIRST": descriptor["case_input_hash"],
                },
                "ordered_exact_definition_hashes": {
                    "A_FIRST": a_descriptor["definition_hash"],
                    "B_FIRST": descriptor["definition_hash"],
                },
            }
            exact_witness["exact_pair_id"] = _domain_digest(
                _DEFERRED_EXACT_PAIR_ID_DOMAIN_V1, exact_witness
            )
            eligible_exact_pair_witnesses.append(exact_witness)

    if pending is not None:
        raise AssertionError("2+2 descriptor enumeration ended mid-pair")
    if len(member_order) != 88:
        raise AssertionError("2+2 member-stratum census drifted")

    ordered_reasons = (
        "INITIAL_GOAL_A",
        "INITIAL_GOAL_B",
        "INSUFFICIENT_CONNECTION_MATERIAL_A",
        "INSUFFICIENT_CONNECTION_MATERIAL_B",
        "INITIAL_IMMOBILITY_A",
        "INITIAL_IMMOBILITY_B",
    )
    members = []
    member_by_key = {}
    for stratum_id in member_order:
        accumulator = member_accumulators[stratum_id]
        universal = accumulator.pop("universal_rejection_reasons")
        eligible_d4_hashes = accumulator.pop("eligible_d4_hashes")
        if not universal.issubset(set(ordered_reasons)):
            raise ValueError("2+2 stratum has an unknown universal reason")
        accumulator["eligible_d4_definition_count"] = len(
            eligible_d4_hashes
        )
        accumulator["universal_rejection_reasons"] = [
            reason for reason in ordered_reasons if reason in universal
        ]
        members.append(accumulator)
        stratum = accumulator["stratum"]
        key = (
            accumulator["family_id"],
            stratum["goal_frame"],
            stratum["vector_profiles"]["A"],
            stratum["vector_profiles"]["B"],
            stratum["first_player"],
        )
        if key in member_by_key:
            raise ValueError("2+2 member-stratum key is duplicated")
        member_by_key[key] = accumulator

    member_raw_count = sum(
        member["raw_exact_definition_count"] for member in members
    )
    member_eligible_count = sum(
        member["eligible_exact_definition_count"] for member in members
    )
    member_eligible_d4_count = sum(
        member["eligible_d4_definition_count"] for member in members
    )
    supported_members = [
        member
        for member in members
        if member["eligible_d4_definition_count"] > 0
    ]
    unsupported_members = [
        member
        for member in members
        if member["eligible_d4_definition_count"] == 0
    ]

    paired_strata = []
    eligible_paired_d4_witnesses = []
    unsupported_pairs = []
    for family in registry:
        for frame in _goal_frames_by_family()[family.family_id]:
            for a_profile in VectorProfileV1:
                for b_profile in VectorProfileV1:
                    neutral_key = (
                        family.family_id,
                        frame,
                        a_profile.value,
                        b_profile.value,
                    )
                    a_member = member_by_key[neutral_key + ("A",)]
                    b_member = member_by_key[neutral_key + ("B",)]
                    if (
                        a_member["raw_exact_definition_count"]
                        != b_member["raw_exact_definition_count"]
                        or a_member["eligible_exact_definition_count"]
                        != b_member["eligible_exact_definition_count"]
                        or a_member["eligible_d4_definition_count"]
                        != b_member["eligible_d4_definition_count"]
                    ):
                        raise ValueError("paired 2+2 member-stratum counts differ")
                    neutral_stratum = {
                        "goal_frame": frame,
                        "setup": {"A_count": 2, "B_count": 2},
                        "vector_profiles": {
                            "A": a_profile.value,
                            "B": b_profile.value,
                        },
                    }
                    pair_record = {
                        "family_id": family.family_id,
                        "family_signature_hash": family.semantic_hash,
                        "paired_stratum_id": _paired_stratum_id(
                            family.semantic_hash, neutral_stratum
                        ),
                        "stratum": neutral_stratum,
                        "raw_exact_setup_pair_count": a_member[
                            "raw_exact_definition_count"
                        ],
                        "raw_exact_setup_definition_count": (
                            a_member["raw_exact_definition_count"]
                            + b_member["raw_exact_definition_count"]
                        ),
                        "eligible_exact_setup_pair_count": a_member[
                            "eligible_exact_definition_count"
                        ],
                        "eligible_exact_setup_definition_count": (
                            a_member["eligible_exact_definition_count"]
                            + b_member["eligible_exact_definition_count"]
                        ),
                        "eligible_paired_d4_count": len(
                            paired_orbits[neutral_key]
                        ),
                        "eligible_paired_d4_definition_count": 2
                        * len(paired_orbits[neutral_key]),
                        "ordered_parent_member_stratum_ids": [
                            a_member["parent_feasibility_stratum_id"],
                            b_member["parent_feasibility_stratum_id"],
                        ],
                    }
                    paired_strata.append(pair_record)
                    for a_d4, b_d4 in sorted(paired_orbits[neutral_key]):
                        d4_witness = {
                            "family_signature_hash": family.semantic_hash,
                            "paired_stratum_id": pair_record[
                                "paired_stratum_id"
                            ],
                            "ordered_member_d4_identities": {
                                "A_FIRST": a_d4,
                                "B_FIRST": b_d4,
                            },
                        }
                        d4_witness["deferred_paired_d4_id"] = _domain_digest(
                            _DEFERRED_PAIRED_D4_ID_DOMAIN_V1, d4_witness
                        )
                        eligible_paired_d4_witnesses.append(d4_witness)
                    if pair_record["eligible_paired_d4_count"] == 0:
                        if (
                            a_member["universal_rejection_reasons"]
                            != b_member["universal_rejection_reasons"]
                            or not a_member["universal_rejection_reasons"]
                            or any(
                                not reason.startswith(
                                    "INSUFFICIENT_CONNECTION_MATERIAL_"
                                )
                                for reason in a_member[
                                    "universal_rejection_reasons"
                                ]
                            )
                        ):
                            raise ValueError(
                                "unsupported 2+2 pair lacks universal material reason"
                            )
                        unsupported = dict(pair_record)
                        unsupported["status"] = (
                            "UNSUPPORTED_CONNECTION_MATERIAL"
                        )
                        unsupported["universal_rejection_reasons"] = list(
                            a_member["universal_rejection_reasons"]
                        )
                        unsupported_pairs.append(unsupported)

    supported_pairs = [
        record
        for record in paired_strata
        if record["eligible_paired_d4_count"] > 0
    ]
    eligible_paired_d4_witnesses.sort(
        key=lambda witness: (
            witness["paired_stratum_id"],
            witness["ordered_member_d4_identities"]["A_FIRST"],
            witness["ordered_member_d4_identities"]["B_FIRST"],
        )
    )
    observed_counts = {
        "raw_exact_setup_pair_count": raw_pair_count,
        "raw_exact_setup_definition_count": member_raw_count,
        "eligible_exact_setup_pair_count": eligible_pair_count,
        "eligible_exact_setup_definition_count": member_eligible_count,
        "eligible_paired_d4_count": sum(
            record["eligible_paired_d4_count"] for record in paired_strata
        ),
        "eligible_paired_d4_definition_count": member_eligible_d4_count,
        "supported_paired_stratum_count": len(supported_pairs),
        "supported_member_stratum_count": len(supported_members),
        "unsupported_paired_stratum_count": len(unsupported_pairs),
        "unsupported_member_stratum_count": len(unsupported_members),
    }
    expected_counts = {
        "raw_exact_setup_pair_count": (
            ATLAS_DEFERRED_2X2_RAW_EXACT_SETUP_PAIR_COUNT_V1
        ),
        "raw_exact_setup_definition_count": (
            ATLAS_DEFERRED_2X2_RAW_DEFINITION_COUNT_V1
        ),
        "eligible_exact_setup_pair_count": (
            ATLAS_DEFERRED_2X2_ELIGIBLE_EXACT_SETUP_PAIR_COUNT_V1
        ),
        "eligible_exact_setup_definition_count": (
            ATLAS_DEFERRED_2X2_ELIGIBLE_EXACT_DEFINITION_COUNT_V1
        ),
        "eligible_paired_d4_count": (
            ATLAS_DEFERRED_2X2_ELIGIBLE_PAIRED_D4_COUNT_V1
        ),
        "eligible_paired_d4_definition_count": (
            ATLAS_DEFERRED_2X2_ELIGIBLE_PAIRED_D4_DEFINITION_COUNT_V1
        ),
        "supported_paired_stratum_count": (
            ATLAS_DEFERRED_2X2_SUPPORTED_PAIRED_STRATUM_COUNT_V1
        ),
        "supported_member_stratum_count": (
            ATLAS_DEFERRED_2X2_SUPPORTED_MEMBER_STRATUM_COUNT_V1
        ),
        "unsupported_paired_stratum_count": (
            ATLAS_DEFERRED_2X2_UNSUPPORTED_PAIRED_STRATUM_COUNT_V1
        ),
        "unsupported_member_stratum_count": (
            ATLAS_DEFERRED_2X2_UNSUPPORTED_MEMBER_STRATUM_COUNT_V1
        ),
    }
    if observed_counts != expected_counts:
        raise AssertionError("reconstructed 2+2 census counts drifted")
    if member_eligible_d4_count != 2 * observed_counts[
        "eligible_paired_d4_count"
    ]:
        raise AssertionError("2+2 paired/member D4 counts differ")
    if (
        len(eligible_exact_pair_witnesses)
        != observed_counts["eligible_exact_setup_pair_count"]
        or len(eligible_paired_d4_witnesses)
        != observed_counts["eligible_paired_d4_count"]
    ):
        raise AssertionError("2+2 eligible witness counts drifted")

    full_parent_reconstruction = {
        "raw_exact_setup_pair_count": (
            ATLAS_RAW_EXACT_SETUP_PAIR_COUNT_V1
            + observed_counts["raw_exact_setup_pair_count"]
        ),
        "raw_exact_setup_definition_count": (
            2 * ATLAS_RAW_EXACT_SETUP_PAIR_COUNT_V1
            + observed_counts["raw_exact_setup_definition_count"]
        ),
        "eligible_exact_setup_pair_count": (
            ATLAS_ELIGIBLE_EXACT_SETUP_PAIR_COUNT_V1
            + observed_counts["eligible_exact_setup_pair_count"]
        ),
        "eligible_exact_setup_definition_count": (
            2 * ATLAS_ELIGIBLE_EXACT_SETUP_PAIR_COUNT_V1
            + observed_counts["eligible_exact_setup_definition_count"]
        ),
        "eligible_paired_d4_count": (
            ATLAS_ELIGIBLE_PAIRED_D4_COUNT_V1
            + observed_counts["eligible_paired_d4_count"]
        ),
        "eligible_paired_d4_definition_count": (
            2 * ATLAS_ELIGIBLE_PAIRED_D4_COUNT_V1
            + observed_counts["eligible_paired_d4_definition_count"]
        ),
    }
    if (
        full_parent_reconstruction["raw_exact_setup_definition_count"]
        != FEASIBILITY_INPUT_COUNT_V1
        or full_parent_reconstruction[
            "eligible_exact_setup_definition_count"
        ]
        != _ATLAS_PARENT_ELIGIBLE_EXACT_DEFINITION_COUNT_V1
        or full_parent_reconstruction[
            "eligible_paired_d4_definition_count"
        ]
        != _ATLAS_PARENT_ELIGIBLE_D4_DEFINITION_COUNT_V1
    ):
        raise AssertionError("2+2 plus 3+3 does not reconstruct parent census")

    unsupported_member_witnesses = []
    unsupported_ids = {
        member["parent_feasibility_stratum_id"] for member in unsupported_members
    }
    for member in members:
        if member["parent_feasibility_stratum_id"] not in unsupported_ids:
            continue
        witness = _json_copy(member, "unsupported 2+2 member stratum")
        witness["status"] = "UNSUPPORTED_CONNECTION_MATERIAL"
        unsupported_member_witnesses.append(witness)
    parent_census_roots = {
        "feasibility_census_digest": ATLAS_PARENT_CENSUS_DIGEST_V1,
        "ordered_case_to_d4_root": ATLAS_PARENT_CASE_TO_D4_ROOT_V1,
        "sorted_eligible_d4_root": ATLAS_PARENT_ELIGIBLE_D4_ROOT_V1,
    }
    eligible_exact_pair_root = _domain_digest(
        _DEFERRED_EXACT_PAIR_ROOT_DOMAIN_V1,
        {
            "parent_census_roots": parent_census_roots,
            "ordered_eligible_exact_pair_witnesses": (
                eligible_exact_pair_witnesses
            ),
        },
    )
    eligible_paired_d4_root = _domain_digest(
        _DEFERRED_PAIRED_D4_ROOT_DOMAIN_V1,
        {
            "parent_census_roots": parent_census_roots,
            "sorted_eligible_paired_d4_witnesses": (
                eligible_paired_d4_witnesses
            ),
        },
    )
    value = {
        "status": "ALL_ELIGIBLE_TWO_PLUS_TWO_DEFERRED",
        "inference_contract": (
            "DEFERRED_CASES_AND_UNSUPPORTED_STRATA_ARE_NOT_NEGATIVE_"
            "EVIDENCE_AGAINST_ANY_FAMILY"
        ),
        "setup": {"A_count": 2, "B_count": 2},
        "parent_census_roots": parent_census_roots,
        "full_parent_reconstruction": full_parent_reconstruction,
        "census": {
            **observed_counts,
            "deferred_eligible_pair_count": observed_counts[
                "eligible_paired_d4_count"
            ],
            "deferred_eligible_definition_count": observed_counts[
                "eligible_paired_d4_definition_count"
            ],
        },
        "ordered_unsupported_paired_strata": unsupported_pairs,
        "ordered_unsupported_member_strata": unsupported_member_witnesses,
        "ordered_eligible_exact_pair_root": eligible_exact_pair_root,
        "sorted_eligible_paired_d4_witness_root": eligible_paired_d4_root,
    }
    value["unsupported_paired_strata_root"] = _domain_digest(
        _DEFERRED_PAIRED_STRATA_ROOT_DOMAIN_V1,
        {
            "parent_census_roots": parent_census_roots,
            "ordered_unsupported_paired_strata": unsupported_pairs,
        },
    )
    value["unsupported_member_strata_root"] = _domain_digest(
        _DEFERRED_MEMBER_STRATA_ROOT_DOMAIN_V1,
        {
            "parent_census_roots": parent_census_roots,
            "ordered_unsupported_member_strata": unsupported_member_witnesses,
        },
    )
    value["deferred_two_plus_two_root"] = _domain_digest(
        _DEFERRED_TWO_PLUS_TWO_ROOT_DOMAIN_V1, value
    )
    return value


@lru_cache(maxsize=1)
def _cached_deferred_two_plus_two_json_v1() -> str:
    return _canonical_bytes(_build_deferred_two_plus_two_contract()).decode(
        "utf-8"
    )


def _deferred_two_plus_two_contract(
    registry: FamilyRegistry,
) -> Dict[str, Any]:
    value = json.loads(_cached_deferred_two_plus_two_json_v1())
    if value["parent_census_roots"] != {
        "feasibility_census_digest": ATLAS_PARENT_CENSUS_DIGEST_V1,
        "ordered_case_to_d4_root": ATLAS_PARENT_CASE_TO_D4_ROOT_V1,
        "sorted_eligible_d4_root": ATLAS_PARENT_ELIGIBLE_D4_ROOT_V1,
    }:
        raise AssertionError("deferred 2+2 parent roots drifted")
    if tuple(registry.semantic_hashes) != tuple(
        build_atlas_family_registry_v1().semantic_hashes
    ):
        raise AssertionError("deferred 2+2 registry differs from envelope")
    return value


@lru_cache(maxsize=1)
def _cached_envelope_json_v1() -> str:
    if feasibility_domain_hash_v1() != ATLAS_PARENT_DOMAIN_HASH_V1:
        raise AssertionError("Plan-0012 feasibility domain hash drifted")
    registry = build_atlas_family_registry_v1()
    strata = _ordered_paired_strata()
    family_records = []
    for family in registry:
        family_strata = [
            record for record in strata if record["family_id"] == family.family_id
        ]
        quotas = {record["pair_quota"] for record in family_strata}
        if len(quotas) != 1:
            raise AssertionError("one family has inconsistent pair quotas")
        quota = next(iter(quotas))
        family_records.append(
            {
                "family_id": family.family_id,
                "family_signature_hash": family.semantic_hash,
                "goal_frames": list(_goal_frames_by_family()[family.family_id]),
                "paired_stratum_count": len(family_strata),
                "development_pairs_per_stratum": quota,
                "development_definitions_per_stratum": 2 * quota,
                "candidate_pairs_per_stratum": quota,
                "candidate_definitions_per_stratum": 2 * quota,
                "development_pair_count": len(family_strata) * quota,
                "development_definition_count": 2 * len(family_strata) * quota,
                "candidate_pair_count": len(family_strata) * quota,
                "candidate_definition_count": 2 * len(family_strata) * quota,
            }
        )
    unsigned = {
        "envelope_version": ATLAS_ENVELOPE_VERSION_V1,
        "envelope_id": ATLAS_ENVELOPE_ID_V1,
        "status": "OUTCOME_FREE_FIXED_COMMON_SUPPORT",
        "parents": {
            "feasibility_domain_hash": ATLAS_PARENT_DOMAIN_HASH_V1,
            "feasibility_census_digest": ATLAS_PARENT_CENSUS_DIGEST_V1,
            "ordered_case_to_d4_root": ATLAS_PARENT_CASE_TO_D4_ROOT_V1,
            "sorted_eligible_d4_root": ATLAS_PARENT_ELIGIBLE_D4_ROOT_V1,
        },
        "registry": {
            "registry_version": ATLAS_REGISTRY_VERSION_V1,
            "registry_id": ATLAS_REGISTRY_ID_V1,
            "ordered_registry_root": family_registry_hash(registry),
            "ordered_registry_record_root": _domain_digest(
                _REGISTRY_RECORD_ROOT_DOMAIN_V1,
                [record.to_dict() for record in registry],
            ),
            "family_count": len(registry),
            "ordered_family_ids": list(registry.family_ids),
            "ordered_family_signature_hashes": list(registry.semantic_hashes),
        },
        "compiler": {
            "compiler_id": FEASIBILITY_COMPILER_ID,
            "compiler_version": FEASIBILITY_COMPILER_VERSION,
            "d4_canonicalization_id": FEASIBILITY_D4_CANONICALIZATION_ID,
            "d4_canonicalization_version": (
                FEASIBILITY_D4_CANONICALIZATION_VERSION
            ),
            "d4_transform_order": list(D4_TRANSFORMS),
        },
        "fixed_domain": {
            "dsl_schema_version": 4,
            "board_size": 3,
            "max_plies": 18,
            "piece_counts": {"A": 3, "B": 3},
            "first_players": ["A", "B"],
            "vector_profile_order": [profile.value for profile in VectorProfileV1],
            "pairing_rule": "SAME_SETUP_A_FIRST_AND_B_FIRST",
            "representative_rule": (
                "MINIMUM_FIRST_PLAYER_FREE_MECHANICAL_D4_BYTES_"
                "WITH_DECLARED_D4_TIE_ORDER"
            ),
            "rank_fields": [
                "family_signature_hash",
                "first_player_free_stratum",
                "paired_mechanical_d4_identity",
            ],
            "rank_excludes": [
                "family_id",
                "definition_name",
                "case_input_hash",
                "history_projection_root",
            ],
        },
        "families": family_records,
        "paired_strata": list(strata),
        "deferred_two_plus_two": _deferred_two_plus_two_contract(registry),
        "expected_census": {
            "raw_exact_setup_pair_count": ATLAS_RAW_EXACT_SETUP_PAIR_COUNT_V1,
            "raw_exact_setup_definition_count": (
                2 * ATLAS_RAW_EXACT_SETUP_PAIR_COUNT_V1
            ),
            "eligible_exact_setup_pair_count": (
                ATLAS_ELIGIBLE_EXACT_SETUP_PAIR_COUNT_V1
            ),
            "eligible_exact_setup_definition_count": (
                2 * ATLAS_ELIGIBLE_EXACT_SETUP_PAIR_COUNT_V1
            ),
            "eligible_paired_d4_count": ATLAS_ELIGIBLE_PAIRED_D4_COUNT_V1,
            "eligible_paired_d4_definition_count": (
                2 * ATLAS_ELIGIBLE_PAIRED_D4_COUNT_V1
            ),
            "paired_stratum_count": ATLAS_PAIRED_STRATUM_COUNT_V1,
            "development_pair_count": ATLAS_DEVELOPMENT_PAIR_COUNT_V1,
            "development_definition_count": (
                ATLAS_DEVELOPMENT_DEFINITION_COUNT_V1
            ),
            "candidate_pair_count": ATLAS_CANDIDATE_PAIR_COUNT_V1,
            "candidate_definition_count": ATLAS_CANDIDATE_DEFINITION_COUNT_V1,
        },
    }
    value = dict(unsigned)
    value["search_envelope_root"] = _domain_digest(
        _ENVELOPE_ROOT_DOMAIN_V1, unsigned
    )
    if value["search_envelope_root"] != ATLAS_SEARCH_ENVELOPE_ROOT_V1:
        raise AssertionError("atlas search-envelope root drifted")
    return _canonical_bytes(value).decode("utf-8")


def build_atlas_search_envelope_v1() -> Dict[str, Any]:
    """Return a detached copy of the fixed 3+3 common-support envelope."""

    return json.loads(_cached_envelope_json_v1())


def validate_atlas_search_envelope_v1(value: Any) -> Dict[str, Any]:
    """Rebuild the fixed envelope and reject any retained-field drift."""

    if type(value) is not dict:
        raise TypeError("atlas search envelope must be an exact object")
    _validate_json_tree(value, "atlas search envelope")
    entry = _canonical_bytes(value)
    expected_json = _cached_envelope_json_v1()
    if entry != expected_json.encode("utf-8"):
        raise ValueError("atlas search envelope does not reconstruct")
    if entry != _canonical_bytes(value):
        raise ValueError("atlas search envelope changed during validation")
    return json.loads(expected_json)


def _case_pair_key(case: Any) -> Tuple[Any, ...]:
    return (
        case.family_id,
        case.goal_frame.value,
        case.a_vector_profile.value,
        case.b_vector_profile.value,
        case.a_positions,
        case.b_positions,
    )


def _exact_pair_witness(
    a_case: Any,
    b_case: Any,
    a_descriptor: Mapping[str, Any],
    b_descriptor: Mapping[str, Any],
    family_signature_digest: str,
) -> Dict[str, Any]:
    a_neutral_input = a_case.to_dict()
    b_neutral_input = b_case.to_dict()
    for value in (a_neutral_input, b_neutral_input):
        value.pop("first_player")
        value.pop("family_id")
    if _canonical_bytes(a_neutral_input) != _canonical_bytes(b_neutral_input):
        raise ValueError("paired cases do not share a neutral feasibility input")
    paired_input_identity = _domain_digest(
        _PAIRED_INPUT_ID_DOMAIN_V1,
        {
            "family_signature_hash": family_signature_digest,
            "neutral_feasibility_input": a_neutral_input,
        },
    )
    return {
        "paired_input_identity": paired_input_identity,
        "ordered_case_input_hashes": {
            "A_FIRST": a_descriptor["case_input_hash"],
            "B_FIRST": b_descriptor["case_input_hash"],
        },
        "ordered_exact_definition_hashes": {
            "A_FIRST": a_descriptor["definition_hash"],
            "B_FIRST": b_descriptor["definition_hash"],
        },
    }


def _new_pair_record(
    a_case: Any,
    b_case: Any,
    a_descriptor: Mapping[str, Any],
    b_descriptor: Mapping[str, Any],
    family_signature_digest: str,
    neutral_stratum: Mapping[str, Any],
    paired_stratum_id: str,
    proof: Mapping[str, Any],
) -> Dict[str, Any]:
    a_definition = compile_feasibility_definition_v1(a_case)
    b_definition = compile_feasibility_definition_v1(b_case)
    a_canonical = canonicalize_d4(a_definition)
    b_canonical = canonicalize_d4(b_definition)
    a_neutral = _neutral_d4_value(a_canonical)
    b_neutral = _neutral_d4_value(b_canonical)
    if (
        a_canonical.transform != b_canonical.transform
        or _canonical_bytes(a_neutral) != _canonical_bytes(b_neutral)
    ):
        raise ValueError("paired members do not share a canonical D4 geometry")
    neutral_mechanical_digest = hashlib.sha256(
        _canonical_bytes(a_neutral)
    ).hexdigest()
    pair_d4_identity = _domain_digest(
        _PAIR_D4_ID_DOMAIN_V1,
        {
            "family_signature_hash": family_signature_digest,
            "neutral_mechanical_digest": neutral_mechanical_digest,
            "neutral_mechanical_definition": a_neutral,
            "member_d4_identities": {
                "A_FIRST": a_descriptor["d4_canonical_hash"],
                "B_FIRST": b_descriptor["d4_canonical_hash"],
            },
        },
    )
    representative_a = _representative_definition(
        a_neutral, pair_d4_identity, "A"
    )
    representative_b = _representative_definition(
        a_neutral, pair_d4_identity, "B"
    )
    representative_a_canonical = canonicalize_d4(representative_a)
    representative_b_canonical = canonicalize_d4(representative_b)
    if (
        representative_a_canonical.transform != "I"
        or representative_b_canonical.transform != "I"
    ):
        raise ValueError("paired representative is not in the declared D4 orientation")
    if (
        representative_a_canonical.canonical_hash
        != a_descriptor["d4_canonical_hash"]
        or representative_b_canonical.canonical_hash
        != b_descriptor["d4_canonical_hash"]
    ):
        raise ValueError("representative member D4 identity drifted")
    (
        commutation_count,
        commutation_root,
        a_slot_hashes,
        a_slot_root,
        b_slot_hashes,
        b_slot_root,
    ) = _commutation_evidence(representative_a, representative_b)
    invariant = _descriptor_pair_invariant(
        family_signature_digest, neutral_stratum, a_descriptor
    )
    rank_digest = _pair_rank_digest(
        family_signature_digest, neutral_stratum, pair_d4_identity
    )
    return {
        "paired_mechanical_d4_identity": pair_d4_identity,
        "family_id": a_case.family_id,
        "family_signature_hash": family_signature_digest,
        "paired_stratum_id": paired_stratum_id,
        "stratum": _json_copy(neutral_stratum, "pair stratum"),
        "neutral_mechanical_digest": neutral_mechanical_digest,
        "rank_digest": rank_digest,
        "member_definition_count": 2,
        "orbit_multiplicity": 0,
        "domain_exact_pair_witnesses": [],
        "feasibility_invariant_digest": _domain_digest(
            _PAIR_INVARIANT_DOMAIN_V1, invariant
        ),
        "state_work_proof": _json_copy(proof, "pair state/work proof"),
        "state_work_proof_digest": _domain_digest(
            _PAIR_WORK_PROOF_DOMAIN_V1, proof
        ),
        "d4_commutation_check_count": commutation_count,
        "d4_commutation_evidence_root": commutation_root,
        "members": {
            "A_FIRST": {
                "first_player": "A",
                "d4_canonical_hash": a_descriptor["d4_canonical_hash"],
                "domain_exact_definition_hashes": [],
                "representative_definition_hash": definition_hash(
                    representative_a
                ),
                "representative_d4_slot_definition_hashes": a_slot_hashes,
                "representative_d4_slot_definition_root": a_slot_root,
                "representative_definition": representative_a.to_dict(),
            },
            "B_FIRST": {
                "first_player": "B",
                "d4_canonical_hash": b_descriptor["d4_canonical_hash"],
                "domain_exact_definition_hashes": [],
                "representative_definition_hash": definition_hash(
                    representative_b
                ),
                "representative_d4_slot_definition_hashes": b_slot_hashes,
                "representative_d4_slot_definition_root": b_slot_root,
                "representative_definition": representative_b.to_dict(),
            },
        },
    }


def _pair_witness_payload(record: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "paired_mechanical_d4_identity": record[
            "paired_mechanical_d4_identity"
        ],
        "family_signature_hash": record["family_signature_hash"],
        "paired_stratum_id": record["paired_stratum_id"],
        "stratum": record["stratum"],
        "neutral_mechanical_digest": record["neutral_mechanical_digest"],
        "member_definition_count": record["member_definition_count"],
        "orbit_multiplicity": record["orbit_multiplicity"],
        "domain_exact_pair_witness_count": record[
            "domain_exact_pair_witness_count"
        ],
        "domain_exact_setup_pair_count": record[
            "domain_exact_setup_pair_count"
        ],
        "domain_exact_setup_definition_count": record[
            "domain_exact_setup_definition_count"
        ],
        "domain_exact_pair_witness_root": record[
            "domain_exact_pair_witness_root"
        ],
        "domain_exact_pair_witnesses": record[
            "domain_exact_pair_witnesses"
        ],
        "feasibility_invariant_digest": record[
            "feasibility_invariant_digest"
        ],
        "state_work_proof_digest": record["state_work_proof_digest"],
        "d4_commutation_check_count": record[
            "d4_commutation_check_count"
        ],
        "d4_commutation_evidence_root": record[
            "d4_commutation_evidence_root"
        ],
        "members": record["members"],
    }


def _finish_pair_record(record: Dict[str, Any]) -> None:
    members = record["members"]
    for member in members.values():
        hashes = sorted(member["domain_exact_definition_hashes"])
        if len(hashes) != len(set(hashes)):
            raise ValueError("one pair member repeats an exact definition hash")
        member["domain_exact_definition_hashes"] = hashes
        member["domain_exact_definition_count"] = len(hashes)
        member["domain_exact_definition_root"] = _domain_digest(
            _PAIR_EXACT_ROOT_DOMAIN_V1,
            {
                "first_player": member["first_player"],
                "definition_hashes": hashes,
            },
        )
    a_count = members["A_FIRST"]["domain_exact_definition_count"]
    b_count = members["B_FIRST"]["domain_exact_definition_count"]
    if a_count != b_count or a_count != record["orbit_multiplicity"]:
        raise ValueError("pair member multiplicities differ")
    exact_pair_witnesses = sorted(
        record["domain_exact_pair_witnesses"],
        key=lambda witness: (
            witness["paired_input_identity"],
            witness["ordered_case_input_hashes"]["A_FIRST"],
            witness["ordered_case_input_hashes"]["B_FIRST"],
        ),
    )
    paired_input_identities = [
        witness["paired_input_identity"] for witness in exact_pair_witnesses
    ]
    if (
        len(exact_pair_witnesses) != record["orbit_multiplicity"]
        or len(paired_input_identities) != len(set(paired_input_identities))
    ):
        raise ValueError("exact paired-input correspondence is not bijective")
    record["domain_exact_pair_witnesses"] = exact_pair_witnesses
    record["domain_exact_pair_witness_count"] = len(exact_pair_witnesses)
    record["domain_exact_setup_pair_count"] = len(exact_pair_witnesses)
    record["domain_exact_setup_definition_count"] = 2 * len(
        exact_pair_witnesses
    )
    record["domain_exact_pair_witness_root"] = _domain_digest(
        _PAIR_EXACT_WITNESS_ROOT_DOMAIN_V1, exact_pair_witnesses
    )
    record["pair_witness_digest"] = _domain_digest(
        _PAIR_WITNESS_DOMAIN_V1, _pair_witness_payload(record)
    )


@lru_cache(maxsize=1)
def _cached_paired_universe_json_v1() -> str:
    envelope = build_atlas_search_envelope_v1()
    registry = build_atlas_family_registry_v1()
    signature_by_family = {
        record.family_id: record.semantic_hash for record in registry
    }
    strata = _ordered_paired_strata()
    stratum_by_key = {
        (
            record["family_id"],
            record["stratum"]["goal_frame"],
            record["stratum"]["vector_profiles"]["A"],
            record["stratum"]["vector_profiles"]["B"],
        ): record
        for record in strata
    }
    work_proofs: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    pair_records: Dict[Tuple[str, str], Dict[str, Any]] = {}
    pending: Optional[Tuple[Any, Dict[str, Any]]] = None
    raw_exact_pairs = 0
    eligible_exact_pairs = 0

    for case, descriptor in enumerate_feasibility_case_descriptors_v1(3):
        if pending is None:
            if case.first_player is not Player.A:
                raise AssertionError("3+3 descriptor order no longer begins A-first")
            pending = (case, descriptor)
            continue
        a_case, a_descriptor = pending
        pending = None
        if case.first_player is not Player.B:
            raise AssertionError("3+3 descriptor order no longer pairs B-first")
        if _case_pair_key(a_case) != _case_pair_key(case):
            raise ValueError("adjacent first-player cases do not share one setup")
        raw_exact_pairs += 1
        a_neutral_stratum = _without_first_player_stratum(
            a_descriptor["stratum"]
        )
        b_neutral_stratum = _without_first_player_stratum(descriptor["stratum"])
        if _canonical_bytes(a_neutral_stratum) != _canonical_bytes(
            b_neutral_stratum
        ):
            raise ValueError("paired members disagree on their neutral stratum")
        signature_digest = signature_by_family[a_case.family_id]
        a_invariant = _descriptor_pair_invariant(
            signature_digest, a_neutral_stratum, a_descriptor
        )
        b_invariant = _descriptor_pair_invariant(
            signature_digest, b_neutral_stratum, descriptor
        )
        if _canonical_bytes(a_invariant) != _canonical_bytes(b_invariant):
            raise ValueError("paired first-player descriptors differ")
        if a_descriptor["gate"]["eligible"] != descriptor["gate"]["eligible"]:
            raise ValueError("paired members disagree on feasibility")
        if not a_descriptor["gate"]["eligible"]:
            continue
        eligible_exact_pairs += 1
        stratum_key = (
            a_case.family_id,
            a_case.goal_frame.value,
            a_case.a_vector_profile.value,
            a_case.b_vector_profile.value,
        )
        try:
            stratum_record = stratum_by_key[stratum_key]
        except KeyError as error:
            raise ValueError("eligible case is outside the fixed atlas envelope") from error
        orbit_key = (
            a_descriptor["d4_canonical_hash"],
            descriptor["d4_canonical_hash"],
        )
        record = pair_records.get(orbit_key)
        if record is None:
            proof_key = (
                a_case.family_id,
                a_case.a_vector_profile.value,
                a_case.b_vector_profile.value,
            )
            proof = work_proofs.get(proof_key)
            if proof is None:
                a_proof = build_state_work_proof_v1(a_case)
                b_proof = build_state_work_proof_v1(case)
                if _canonical_bytes(a_proof) != _canonical_bytes(b_proof):
                    raise ValueError(
                        "paired first-player cases disagree on state/work proof"
                    )
                proof = a_proof
                work_proofs[proof_key] = proof
            record = _new_pair_record(
                a_case,
                case,
                a_descriptor,
                descriptor,
                signature_digest,
                a_neutral_stratum,
                stratum_record["paired_stratum_id"],
                proof,
            )
            pair_records[orbit_key] = record
        else:
            if (
                record["paired_stratum_id"]
                != stratum_record["paired_stratum_id"]
                or record["feasibility_invariant_digest"]
                != _domain_digest(_PAIR_INVARIANT_DOMAIN_V1, a_invariant)
            ):
                raise ValueError("one paired D4 orbit crosses an invariant stratum")
        record["domain_exact_pair_witnesses"].append(
            _exact_pair_witness(
                a_case,
                case,
                a_descriptor,
                descriptor,
                signature_digest,
            )
        )
        record["orbit_multiplicity"] += 1
        record["members"]["A_FIRST"][
            "domain_exact_definition_hashes"
        ].append(a_descriptor["definition_hash"])
        record["members"]["B_FIRST"][
            "domain_exact_definition_hashes"
        ].append(descriptor["definition_hash"])

    if pending is not None:
        raise AssertionError("3+3 descriptor enumeration ended mid-pair")
    if raw_exact_pairs != ATLAS_RAW_EXACT_SETUP_PAIR_COUNT_V1:
        raise ValueError("raw exact setup-pair census mismatch")
    if eligible_exact_pairs != ATLAS_ELIGIBLE_EXACT_SETUP_PAIR_COUNT_V1:
        raise ValueError("eligible exact setup-pair census mismatch")
    if len(pair_records) != ATLAS_ELIGIBLE_PAIRED_D4_COUNT_V1:
        raise ValueError("eligible paired-D4 census mismatch")

    pair_ids = set()
    member_a_d4 = set()
    member_b_d4 = set()
    multiplicity_histogram: Dict[str, int] = defaultdict(int)
    by_stratum: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for record in pair_records.values():
        _finish_pair_record(record)
        pair_identity = record["paired_mechanical_d4_identity"]
        if pair_identity in pair_ids:
            raise ValueError("paired mechanical D4 identity is not unique")
        pair_ids.add(pair_identity)
        a_d4 = record["members"]["A_FIRST"]["d4_canonical_hash"]
        b_d4 = record["members"]["B_FIRST"]["d4_canonical_hash"]
        if a_d4 in member_a_d4 or b_d4 in member_b_d4:
            raise ValueError("first-player toggle is not a D4-orbit bijection")
        member_a_d4.add(a_d4)
        member_b_d4.add(b_d4)
        multiplicity_histogram[str(record["orbit_multiplicity"])] += 1
        by_stratum[record["paired_stratum_id"]].append(record)

    if dict(sorted(multiplicity_histogram.items())) != (
        _EXPECTED_MULTIPLICITY_HISTOGRAM_V1
    ):
        raise ValueError("paired-orbit multiplicity histogram mismatch")
    if sum(
        record["orbit_multiplicity"] for record in pair_records.values()
    ) != ATLAS_ELIGIBLE_EXACT_SETUP_PAIR_COUNT_V1:
        raise ValueError("paired multiplicities do not reconstruct exact supply")

    ordered_pairs = []
    stratum_summaries = []
    family_counts: Dict[str, int] = defaultdict(int)
    commutation_checks = 0
    for stratum in strata:
        candidates = by_stratum.get(stratum["paired_stratum_id"], [])
        candidates.sort(
            key=lambda record: (
                record["rank_digest"],
                record["paired_mechanical_d4_identity"],
                record["members"]["A_FIRST"]["d4_canonical_hash"],
                record["members"]["B_FIRST"]["d4_canonical_hash"],
            )
        )
        if len(candidates) < 2 * stratum["pair_quota"]:
            raise ValueError("one paired stratum lacks both declared blocks")
        for rank, record in enumerate(candidates, 1):
            record["pre_history_rank"] = rank
            ordered_pairs.append(record)
            family_counts[stratum["family_id"]] += 1
            commutation_checks += record["d4_commutation_check_count"]
        stratum_summaries.append(
            {
                **_json_copy(stratum, "paired stratum summary"),
                "eligible_pair_count": len(candidates),
                "eligible_definition_count": 2 * len(candidates),
                "eligible_exact_setup_pair_count": sum(
                    record["orbit_multiplicity"] for record in candidates
                ),
                "eligible_exact_setup_definition_count": 2
                * sum(record["orbit_multiplicity"] for record in candidates),
                "ordered_pair_root": _domain_digest(
                    _STRATUM_UNIVERSE_DOMAIN_V1,
                    [
                        {
                            "rank_digest": record["rank_digest"],
                            "paired_mechanical_d4_identity": record[
                                "paired_mechanical_d4_identity"
                            ],
                            "pair_witness_digest": record[
                                "pair_witness_digest"
                            ],
                        }
                        for record in candidates
                    ],
                ),
            }
        )
    if len(stratum_summaries) != ATLAS_PAIRED_STRATUM_COUNT_V1:
        raise ValueError("eligible paired-stratum census mismatch")
    if dict(family_counts) != _EXPECTED_FAMILY_PAIRED_D4_COUNTS_V1:
        raise ValueError("eligible paired-D4 family census mismatch")
    if commutation_checks != ATLAS_D4_COMMUTATION_CHECK_COUNT_V1:
        raise ValueError("D4 commutation proof count mismatch")

    witness_projection = [
        {
            "paired_stratum_id": record["paired_stratum_id"],
            "rank_digest": record["rank_digest"],
            "paired_mechanical_d4_identity": record[
                "paired_mechanical_d4_identity"
            ],
            "pair_witness_digest": record["pair_witness_digest"],
        }
        for record in ordered_pairs
    ]
    value = {
        "universe_version": ATLAS_PAIRED_UNIVERSE_VERSION_V1,
        "universe_id": ATLAS_PAIRED_UNIVERSE_ID_V1,
        "status": "OUTCOME_FREE_ELIGIBLE_PAIRED_UNIVERSE",
        "ordered_registry_root": envelope["registry"][
            "ordered_registry_root"
        ],
        "search_envelope_root": envelope["search_envelope_root"],
        "census": {
            "raw_exact_setup_pair_count": raw_exact_pairs,
            "raw_exact_setup_definition_count": 2 * raw_exact_pairs,
            "eligible_exact_setup_pair_count": eligible_exact_pairs,
            "eligible_exact_setup_definition_count": 2 * eligible_exact_pairs,
            "eligible_paired_d4_count": len(ordered_pairs),
            "eligible_paired_d4_definition_count": 2 * len(ordered_pairs),
            "paired_stratum_count": len(stratum_summaries),
            "minimum_eligible_pairs_per_stratum": min(
                summary["eligible_pair_count"] for summary in stratum_summaries
            ),
            "minimum_eligible_definitions_per_stratum": 2
            * min(
                summary["eligible_pair_count"] for summary in stratum_summaries
            ),
            "maximum_eligible_pairs_per_stratum": max(
                summary["eligible_pair_count"] for summary in stratum_summaries
            ),
            "maximum_eligible_definitions_per_stratum": 2
            * max(
                summary["eligible_pair_count"] for summary in stratum_summaries
            ),
            "family_paired_d4_counts": dict(family_counts),
            "family_paired_d4_definition_counts": {
                family_id: 2 * count
                for family_id, count in family_counts.items()
            },
            "orbit_multiplicity_histogram": dict(
                sorted(multiplicity_histogram.items())
            ),
            "d4_commutation_check_count": commutation_checks,
        },
        "paired_strata": stratum_summaries,
        "pairs": ordered_pairs,
    }
    value["paired_universe_witness_root"] = _domain_digest(
        _UNIVERSE_ROOT_DOMAIN_V1,
        {
            "search_envelope_root": envelope["search_envelope_root"],
            "ordered_pair_witnesses": witness_projection,
        },
    )
    if (
        value["paired_universe_witness_root"]
        != ATLAS_PAIRED_UNIVERSE_WITNESS_ROOT_V1
    ):
        raise AssertionError("atlas paired-universe witness root drifted")
    return _canonical_bytes(value).decode("utf-8")


def build_atlas_paired_universe_v1() -> Dict[str, Any]:
    """Return the detached complete 3+3 eligible matched-pair universe."""

    return json.loads(_cached_paired_universe_json_v1())


def validate_atlas_paired_universe_v1(value: Any) -> Dict[str, Any]:
    """Rebuild every pair, representative, proof, and root in the universe."""

    if type(value) is not dict:
        raise TypeError("atlas paired universe must be an exact object")
    _validate_json_tree(value, "atlas paired universe")
    entry = _canonical_bytes(value)
    expected_json = _cached_paired_universe_json_v1()
    if entry != expected_json.encode("utf-8"):
        raise ValueError("atlas paired universe does not reconstruct")
    if entry != _canonical_bytes(value):
        raise ValueError("atlas paired universe changed during validation")
    return json.loads(expected_json)


def _carrier_maps(
    projection: Mapping[str, Any],
) -> Tuple[Dict[str, Tuple[str, ...]], Dict[str, Tuple[str, ...]]]:
    exact: Dict[str, List[str]] = defaultdict(list)
    d4: Dict[str, List[str]] = defaultdict(list)
    for carrier in projection["carriers"]:
        carrier_id = carrier["carrier_id"]
        for identity in carrier["identity_pairs"]:
            exact[identity["definition_hash"]].append(carrier_id)
            d4[identity["d4_canonical_hash"]].append(carrier_id)
    return (
        {digest: tuple(sorted(set(ids))) for digest, ids in exact.items()},
        {digest: tuple(sorted(set(ids))) for digest, ids in d4.items()},
    )


def _member_collision(
    member: Mapping[str, Any],
    projections: Sequence[
        Tuple[str, Mapping[str, Any], Mapping[str, Tuple[str, ...]], Mapping[str, Tuple[str, ...]]]
    ],
) -> Dict[str, Any]:
    exact_identities = set(member["domain_exact_definition_hashes"])
    exact_identities.add(member["representative_definition_hash"])
    exact_identities.update(member["representative_d4_slot_definition_hashes"])
    categories = []
    any_exact = False
    any_d4 = False
    all_carriers = set()
    for label, projection, exact_map, d4_map in projections:
        exact_matches = sorted(exact_identities.intersection(exact_map.keys()))
        d4_match = member["d4_canonical_hash"] in d4_map
        carriers = set()
        for digest in exact_matches:
            carriers.update(exact_map[digest])
        if d4_match:
            carriers.update(d4_map[member["d4_canonical_hash"]])
        categories.append(
            {
                "exposure_kind": label,
                "projection_root": projection["projection_root"],
                "exact_collision_hashes": exact_matches,
                "d4_collision": d4_match,
                "carrier_ids": sorted(carriers),
            }
        )
        any_exact = any_exact or bool(exact_matches)
        any_d4 = any_d4 or d4_match
        all_carriers.update(carriers)
    return {
        "collides": any_exact or any_d4,
        "exact_collision": any_exact,
        "d4_collision": any_d4,
        "carrier_ids": sorted(all_carriers),
        "categories": categories,
    }


def _partition_root(label: str, identities: Iterable[str]) -> str:
    return _domain_digest(
        _PARTITION_MEMBER_DOMAIN_V1,
        {"partition": label, "paired_mechanical_d4_identities": list(identities)},
    )


def _selected_pair_record(
    pair: Mapping[str, Any],
    block: str,
    fresh_rank: int,
    block_rank: int,
) -> Dict[str, Any]:
    value = _json_copy(pair, "selected pair")
    value["selection"] = {
        "block": block,
        "pre_history_rank": pair["pre_history_rank"],
        "fresh_rank": fresh_rank,
        "block_rank": block_rank,
    }
    value["pair_id"] = "pf13-pair-{}".format(
        pair["paired_mechanical_d4_identity"][:24]
    )
    return value


def _build_selection_value(
    prior: Mapping[str, Any], synthetic: Mapping[str, Any]
) -> Dict[str, Any]:
    universe = build_atlas_paired_universe_v1()
    envelope = build_atlas_search_envelope_v1()
    prior_exact, prior_d4 = _carrier_maps(prior)
    synthetic_exact, synthetic_d4 = _carrier_maps(synthetic)
    projections = (
        (
            ATLAS_PRIOR_GAMEPLAY_EXPOSURE_KIND_V1,
            prior,
            prior_exact,
            prior_d4,
        ),
        (
            ATLAS_SYNTHETIC_FIXTURE_EXPOSURE_KIND_V1,
            synthetic,
            synthetic_exact,
            synthetic_d4,
        ),
    )
    history_binding = {
        "prior_gameplay_cutoff_id": prior["cutoff_id"],
        "prior_gameplay_projection_root": prior["projection_root"],
        "prior_gameplay_malformed_definition_like_count": prior[
            "malformed_definition_like_count"
        ],
        "prior_gameplay_source_attestation_root": prior[
            "source_attestation_root"
        ],
        "synthetic_fixture_cutoff_id": synthetic["cutoff_id"],
        "synthetic_fixture_projection_root": synthetic["projection_root"],
        "synthetic_fixture_malformed_definition_like_count": synthetic[
            "malformed_definition_like_count"
        ],
        "synthetic_fixture_source_attestation_root": synthetic[
            "source_attestation_root"
        ],
    }
    history_binding_root = _domain_digest(
        _HISTORY_BINDING_DOMAIN_V1, history_binding
    )

    pairs_by_stratum: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for pair in universe["pairs"]:
        pairs_by_stratum[pair["paired_stratum_id"]].append(pair)

    development = []
    candidate = []
    exclusions = []
    partitions = []
    collision_counts = {
        "A_FIRST_ONLY": 0,
        "B_FIRST_ONLY": 0,
        "BOTH": 0,
    }
    for stratum in universe["paired_strata"]:
        stratum_id = stratum["paired_stratum_id"]
        pairs = pairs_by_stratum[stratum_id]
        fresh = []
        excluded = []
        for pair in pairs:
            a_collision = _member_collision(pair["members"]["A_FIRST"], projections)
            b_collision = _member_collision(pair["members"]["B_FIRST"], projections)
            if a_collision["collides"] or b_collision["collides"]:
                collision_class = (
                    "BOTH"
                    if a_collision["collides"] and b_collision["collides"]
                    else "A_FIRST_ONLY"
                    if a_collision["collides"]
                    else "B_FIRST_ONLY"
                )
                collision_counts[collision_class] += 1
                exclusion = {
                    "paired_mechanical_d4_identity": pair[
                        "paired_mechanical_d4_identity"
                    ],
                    "excluded_definition_count": 2,
                    "paired_stratum_id": stratum_id,
                    "pre_history_rank": pair["pre_history_rank"],
                    "collision_class": collision_class,
                    "members": {
                        "A_FIRST": a_collision,
                        "B_FIRST": b_collision,
                    },
                }
                excluded.append(exclusion)
                exclusions.append(exclusion)
            else:
                fresh.append(pair)
        quota = stratum["pair_quota"]
        if len(fresh) < 2 * quota:
            raise ValueError(
                "historical exclusion leaves paired stratum {} below both-block quota".format(
                    stratum_id
                )
            )
        dev_pairs = fresh[:quota]
        candidate_pairs = fresh[quota : 2 * quota]
        residual_pairs = fresh[2 * quota :]
        dev_ids = [
            pair["paired_mechanical_d4_identity"] for pair in dev_pairs
        ]
        candidate_ids = [
            pair["paired_mechanical_d4_identity"] for pair in candidate_pairs
        ]
        residual_ids = [
            pair["paired_mechanical_d4_identity"] for pair in residual_pairs
        ]
        for index, pair in enumerate(dev_pairs, 1):
            development.append(
                _selected_pair_record(
                    pair,
                    "DEVELOPMENT",
                    fresh.index(pair) + 1,
                    index,
                )
            )
        for index, pair in enumerate(candidate_pairs, 1):
            candidate.append(
                _selected_pair_record(
                    pair,
                    "CONFIRMATION_CANDIDATE_BLOCK",
                    fresh.index(pair) + 1,
                    index,
                )
            )
        partition = {
            "paired_stratum_id": stratum_id,
            "pair_quota": quota,
            "definition_quota": 2 * quota,
            "pre_history_pair_count": len(pairs),
            "pre_history_definition_count": 2 * len(pairs),
            "pre_history_root": stratum["ordered_pair_root"],
            "excluded_pair_count": len(excluded),
            "excluded_definition_count": 2 * len(excluded),
            "excluded_root": _domain_digest(
                _COLLISION_ROOT_DOMAIN_V1, excluded
            ),
            "development_pair_count": len(dev_ids),
            "development_definition_count": 2 * len(dev_ids),
            "development_root": _partition_root("DEVELOPMENT", dev_ids),
            "candidate_pair_count": len(candidate_ids),
            "candidate_definition_count": 2 * len(candidate_ids),
            "candidate_root": _partition_root(
                "CONFIRMATION_CANDIDATE_BLOCK", candidate_ids
            ),
            "residual_pair_count": len(residual_ids),
            "residual_definition_count": 2 * len(residual_ids),
            "residual_root": _partition_root("UNTOUCHED_RESIDUAL", residual_ids),
        }
        partition["partition_root"] = _domain_digest(
            _STRATUM_PARTITION_DOMAIN_V1, partition
        )
        partitions.append(partition)

    if (
        len(development) != ATLAS_DEVELOPMENT_PAIR_COUNT_V1
        or len(candidate) != ATLAS_CANDIDATE_PAIR_COUNT_V1
    ):
        raise ValueError("fixed atlas block size mismatch")
    development_ids = {
        pair["paired_mechanical_d4_identity"] for pair in development
    }
    candidate_ids = {
        pair["paired_mechanical_d4_identity"] for pair in candidate
    }
    if development_ids & candidate_ids:
        raise ValueError("development and candidate blocks overlap")

    collision_root = _domain_digest(
        _COLLISION_ROOT_DOMAIN_V1,
        {
            "paired_universe_witness_root": universe[
                "paired_universe_witness_root"
            ],
            "history_binding_root": history_binding_root,
            "exclusions": exclusions,
        },
    )
    unsigned = {
        "selection_version": ATLAS_SELECTION_VERSION_V1,
        "selection_id": ATLAS_SELECTION_ID_V1,
        "status": "OUTCOME_FREE_DEVELOPMENT_AND_CANDIDATE_BLOCKS",
        "ordered_registry_root": envelope["registry"][
            "ordered_registry_root"
        ],
        "search_envelope_root": envelope["search_envelope_root"],
        "paired_universe_witness_root": universe[
            "paired_universe_witness_root"
        ],
        "history": {
            **history_binding,
            "history_binding_root": history_binding_root,
            "collision_root": collision_root,
            "excluded_pair_count": len(exclusions),
            "excluded_definition_count": 2 * len(exclusions),
            "collision_class_counts": collision_counts,
            "collision_class_definition_counts": {
                label: 2 * count for label, count in collision_counts.items()
            },
            "excluded_pairs": exclusions,
        },
        "census": {
            "pre_history_pair_count": len(universe["pairs"]),
            "pre_history_definition_count": 2 * len(universe["pairs"]),
            "fresh_pair_count": len(universe["pairs"]) - len(exclusions),
            "fresh_definition_count": 2
            * (len(universe["pairs"]) - len(exclusions)),
            "excluded_pair_count": len(exclusions),
            "excluded_definition_count": 2 * len(exclusions),
            "development_pair_count": len(development),
            "development_definition_count": 2 * len(development),
            "candidate_pair_count": len(candidate),
            "candidate_definition_count": 2 * len(candidate),
            "untouched_residual_pair_count": sum(
                partition["residual_pair_count"] for partition in partitions
            ),
            "untouched_residual_definition_count": 2
            * sum(
                partition["residual_pair_count"] for partition in partitions
            ),
            "paired_stratum_count": len(partitions),
        },
        "stratum_partitions": partitions,
        "development_pairs": development,
        "confirmation_candidate_pairs": candidate,
    }
    unsigned["selection_partition_root"] = _domain_digest(
        _SELECTION_ROOT_DOMAIN_V1,
        {
            "ordered_registry_root": unsigned["ordered_registry_root"],
            "search_envelope_root": unsigned["search_envelope_root"],
            "paired_universe_witness_root": unsigned[
                "paired_universe_witness_root"
            ],
            "history_binding_root": history_binding_root,
            "collision_root": collision_root,
            "ordered_stratum_partition_roots": [
                partition["partition_root"] for partition in partitions
            ],
        },
    )
    return unsigned


@lru_cache(maxsize=8)
def _cached_selection_json_v1(prior_json: str, synthetic_json: str) -> str:
    prior = json.loads(prior_json)
    synthetic = json.loads(synthetic_json)
    return _canonical_bytes(_build_selection_value(prior, synthetic)).decode(
        "utf-8"
    )


def _normalized_projections(
    prior_projection: Any, synthetic_projection: Any
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    prior = validate_atlas_identity_projection_v1(prior_projection)
    synthetic = validate_atlas_identity_projection_v1(synthetic_projection)
    if prior["exposure_kind"] != ATLAS_PRIOR_GAMEPLAY_EXPOSURE_KIND_V1:
        raise ValueError("prior projection has the wrong exposure kind")
    if (
        synthetic["exposure_kind"]
        != ATLAS_SYNTHETIC_FIXTURE_EXPOSURE_KIND_V1
    ):
        raise ValueError("synthetic projection has the wrong exposure kind")
    return prior, synthetic


def build_atlas_selection_snapshot_v1(
    prior_projection: Any, synthetic_projection: Any
) -> Dict[str, Any]:
    """Review-only selector; this is not the frozen production boundary."""

    prior, synthetic = _normalized_projections(
        prior_projection, synthetic_projection
    )
    prior_json = _canonical_bytes(prior).decode("utf-8")
    synthetic_json = _canonical_bytes(synthetic).decode("utf-8")
    return json.loads(_cached_selection_json_v1(prior_json, synthetic_json))


def build_frozen_atlas_selection_snapshot_v1(
    prior_projection: Any, synthetic_projection: Any
) -> Dict[str, Any]:
    """Build only the reviewed zero-collision Plan-0013 selection.

    The generic builder remains available for adversarial collision tests. This
    production boundary accepts the two exact adapter projections fixed for the
    atlas and verifies every downstream root and count before returning a
    detached snapshot.
    """

    prior, synthetic = _normalized_projections(
        prior_projection, synthetic_projection
    )
    if prior["projection_root"] != ATLAS_PRIOR_GAMEPLAY_PROJECTION_ROOT_V1:
        raise ValueError("prior gameplay projection differs from the frozen root")
    if (
        synthetic["projection_root"]
        != ATLAS_SYNTHETIC_FIXTURE_PROJECTION_ROOT_V1
    ):
        raise ValueError("synthetic fixture projection differs from the frozen root")
    snapshot = build_atlas_selection_snapshot_v1(prior, synthetic)
    root_checks = (
        (
            "history binding",
            snapshot["history"]["history_binding_root"],
            ATLAS_HISTORY_BINDING_ROOT_V1,
        ),
        (
            "history collision",
            snapshot["history"]["collision_root"],
            ATLAS_COLLISION_ROOT_V1,
        ),
        (
            "selection partition",
            snapshot["selection_partition_root"],
            ATLAS_SELECTION_PARTITION_ROOT_V1,
        ),
    )
    for label, observed, expected in root_checks:
        if observed != expected:
            raise ValueError("frozen atlas {} root drifted".format(label))
    expected_counts = {
        "pre_history_pair_count": ATLAS_ELIGIBLE_PAIRED_D4_COUNT_V1,
        "pre_history_definition_count": (
            2 * ATLAS_ELIGIBLE_PAIRED_D4_COUNT_V1
        ),
        "fresh_pair_count": ATLAS_ELIGIBLE_PAIRED_D4_COUNT_V1,
        "fresh_definition_count": 2 * ATLAS_ELIGIBLE_PAIRED_D4_COUNT_V1,
        "excluded_pair_count": 0,
        "excluded_definition_count": 0,
        "development_pair_count": ATLAS_DEVELOPMENT_PAIR_COUNT_V1,
        "development_definition_count": ATLAS_DEVELOPMENT_DEFINITION_COUNT_V1,
        "candidate_pair_count": ATLAS_CANDIDATE_PAIR_COUNT_V1,
        "candidate_definition_count": ATLAS_CANDIDATE_DEFINITION_COUNT_V1,
        "untouched_residual_pair_count": 8_566,
        "untouched_residual_definition_count": 17_132,
        "paired_stratum_count": ATLAS_PAIRED_STRATUM_COUNT_V1,
    }
    if snapshot["census"] != expected_counts:
        raise ValueError("frozen atlas selection census drifted")
    if (
        snapshot["history"]["excluded_pair_count"] != 0
        or snapshot["history"]["excluded_definition_count"] != 0
        or any(snapshot["history"]["collision_class_counts"].values())
        or any(
            snapshot["history"][
                "collision_class_definition_counts"
            ].values()
        )
    ):
        raise ValueError("frozen atlas projections unexpectedly collide")
    if hashlib.sha256(_canonical_bytes(snapshot)).hexdigest() != (
        ATLAS_CANONICAL_SELECTION_SHA256_V1
    ):
        raise ValueError("frozen atlas canonical selection bytes drifted")
    return _json_copy(snapshot, "frozen atlas selection snapshot")


def validate_frozen_atlas_selection_snapshot_v1(
    value: Any, prior_projection: Any, synthetic_projection: Any
) -> Dict[str, Any]:
    """Rebuild and validate the reviewed, fixed-root production selection."""

    _validate_json_tree(value, "frozen atlas selection snapshot")
    entry = _canonical_bytes(value)
    expected = build_frozen_atlas_selection_snapshot_v1(
        prior_projection, synthetic_projection
    )
    if entry != _canonical_bytes(expected):
        raise ValueError("frozen atlas selection snapshot does not reconstruct")
    if entry != _canonical_bytes(value):
        raise ValueError(
            "frozen atlas selection snapshot changed during validation"
        )
    return _json_copy(expected, "validated frozen atlas selection snapshot")


def validate_atlas_selection_snapshot_v1(
    value: Any, prior_projection: Any, synthetic_projection: Any
) -> Dict[str, Any]:
    """Review-only validator; this is not the frozen production boundary."""

    _validate_json_tree(value, "atlas selection snapshot")
    entry = _canonical_bytes(value)
    expected = build_atlas_selection_snapshot_v1(
        prior_projection, synthetic_projection
    )
    if entry != _canonical_bytes(expected):
        raise ValueError("atlas selection snapshot does not reconstruct")
    if entry != _canonical_bytes(value):
        raise ValueError("atlas selection snapshot changed during validation")
    return _json_copy(expected, "validated atlas selection snapshot")


def canonical_atlas_selection_json_v1(
    prior_projection: Any,
    synthetic_projection: Any,
    value: Optional[Any] = None,
) -> str:
    """Review-only canonicalizer; not the frozen production boundary."""

    if value is None:
        snapshot = build_atlas_selection_snapshot_v1(
            prior_projection, synthetic_projection
        )
    else:
        snapshot = validate_atlas_selection_snapshot_v1(
            value, prior_projection, synthetic_projection
        )
    return _canonical_bytes(snapshot).decode("utf-8")


def canonical_frozen_atlas_selection_json_v1(
    prior_projection: Any,
    synthetic_projection: Any,
    value: Optional[Any] = None,
) -> str:
    """Return canonical bytes only for the fixed reviewed production selection."""

    if value is None:
        snapshot = build_frozen_atlas_selection_snapshot_v1(
            prior_projection, synthetic_projection
        )
    else:
        snapshot = validate_frozen_atlas_selection_snapshot_v1(
            value, prior_projection, synthetic_projection
        )
    return _canonical_bytes(snapshot).decode("utf-8")


__all__ = (
    "ATLAS_CANDIDATE_DEFINITION_COUNT_V1",
    "ATLAS_CANDIDATE_PAIR_COUNT_V1",
    "ATLAS_DEVELOPMENT_DEFINITION_COUNT_V1",
    "ATLAS_DEVELOPMENT_PAIR_COUNT_V1",
    "ATLAS_DEFERRED_2X2_ELIGIBLE_EXACT_DEFINITION_COUNT_V1",
    "ATLAS_DEFERRED_2X2_ELIGIBLE_EXACT_SETUP_PAIR_COUNT_V1",
    "ATLAS_DEFERRED_2X2_ELIGIBLE_PAIRED_D4_COUNT_V1",
    "ATLAS_DEFERRED_2X2_ELIGIBLE_PAIRED_D4_DEFINITION_COUNT_V1",
    "ATLAS_DEFERRED_2X2_RAW_DEFINITION_COUNT_V1",
    "ATLAS_DEFERRED_2X2_RAW_EXACT_SETUP_PAIR_COUNT_V1",
    "ATLAS_DEFERRED_2X2_SUPPORTED_MEMBER_STRATUM_COUNT_V1",
    "ATLAS_DEFERRED_2X2_SUPPORTED_PAIRED_STRATUM_COUNT_V1",
    "ATLAS_DEFERRED_2X2_UNSUPPORTED_MEMBER_STRATUM_COUNT_V1",
    "ATLAS_DEFERRED_2X2_UNSUPPORTED_PAIRED_STRATUM_COUNT_V1",
    "ATLAS_ELIGIBLE_EXACT_SETUP_PAIR_COUNT_V1",
    "ATLAS_ELIGIBLE_PAIRED_D4_COUNT_V1",
    "ATLAS_ENVELOPE_ID_V1",
    "ATLAS_FINAL_REGISTRY_ROOT_V1",
    "ATLAS_HISTORY_BINDING_ROOT_V1",
    "ATLAS_PAIRED_STRATUM_COUNT_V1",
    "ATLAS_PAIRED_UNIVERSE_ID_V1",
    "ATLAS_PAIRED_UNIVERSE_WITNESS_ROOT_V1",
    "ATLAS_CANONICAL_SELECTION_SHA256_V1",
    "ATLAS_COLLISION_ROOT_V1",
    "ATLAS_PARENT_CENSUS_DIGEST_V1",
    "ATLAS_PRIOR_GAMEPLAY_PROJECTION_ROOT_V1",
    "ATLAS_RAW_EXACT_SETUP_PAIR_COUNT_V1",
    "ATLAS_SEARCH_ENVELOPE_ROOT_V1",
    "ATLAS_SELECTION_ID_V1",
    "ATLAS_SELECTION_PARTITION_ROOT_V1",
    "ATLAS_SYNTHETIC_FIXTURE_PROJECTION_ROOT_V1",
    "build_atlas_family_registry_v1",
    "build_atlas_paired_universe_v1",
    "build_atlas_search_envelope_v1",
    "build_frozen_atlas_selection_snapshot_v1",
    "canonical_frozen_atlas_selection_json_v1",
    "validate_atlas_paired_universe_v1",
    "validate_frozen_atlas_selection_snapshot_v1",
    "validate_atlas_search_envelope_v1",
)
