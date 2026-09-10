"""Outcome-free initial-position census for the provisional Plan-0012 domain.

The census is intentionally limited to facts available at the compiled initial
position: exact and D4 identities, goal predicates, legal-action counts,
connection-material capacity, density, and the compiler's structural work
proof.  It does not apply an action or invoke a player, search, or evaluator.

The public one-case path uses :func:`d4_canonical_hash` directly.  The complete
214,368-case builder caches the non-varying compiled fields and reconstructs the
same canonical mechanical bytes after each D4 transform.  A fixed coverage set
is rebuilt through the public path and must match byte for byte before a census
can be returned.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set, Tuple

from .dsl import ActionKind, GoalKind, InitialPiece, Player, definition_hash
from .engine import GameState, goal_satisfied, legal_actions
from .feasibility import (
    FEASIBILITY_COMPILER_ID,
    FEASIBILITY_COMPILER_VERSION,
    FEASIBILITY_D4_CANONICALIZATION_ID,
    FEASIBILITY_D4_CANONICALIZATION_VERSION,
    FEASIBILITY_INPUT_COUNT_V1,
    PROVISIONAL_STATE_WORK_PROOF_VERSION_V1,
    FeasibilityInputV1,
    build_state_work_proof_v1,
    compile_feasibility_definition_v1,
    enumerate_feasibility_inputs_v1,
    feasibility_domain_hash_v1,
    parse_feasibility_input_v1,
    provisional_case_input_hash_v1,
)
from .symmetry import (
    D4_TRANSFORMS,
    d4_canonical_hash,
    transform_definition,
    transform_position,
)


FEASIBILITY_CENSUS_VERSION_V1 = 1
FEASIBILITY_CASE_DESCRIPTOR_VERSION_V1 = 1
FEASIBILITY_CENSUS_ID_V1 = "plan0012-outcome-free-feasibility-census-v1"
FEASIBILITY_CENSUS_GATE_ID_V1 = (
    "initial-goals-structural-connection-material-both-mobility-v1"
)
FEASIBILITY_CONNECTION_MATERIAL_RULE_V1 = (
    "ACTION_SPECIFIC_STRUCTURAL_UPPER_BOUND_GEOMETRIC_MINIMUM_V1"
)
FEASIBILITY_CENSUS_EVIDENCE_DIGEST_V1 = (
    "ade64ebaaf9892848e03c2312786a6ef3825f3c82f4311e16a9c810711d035d2"
)
FEASIBILITY_ORDERED_CASE_TO_D4_ROOT_V1 = (
    "e016d4644645595030914f496372c7d07cf2658def25b6c18394a339589100a6"
)
FEASIBILITY_SORTED_ELIGIBLE_D4_ROOT_V1 = (
    "6b96cf4ee19d708c61c941c5759c46db0fb0420f2f820959584dd5f1e34d0108"
)

_STRATUM_ID_DOMAIN_V1 = b"parity-forge:plan0012:feasibility-stratum:v1\0"
_CASE_DESCRIPTOR_DOMAIN_V1 = (
    b"parity-forge:plan0012:feasibility-case-descriptor:v1\0"
)
_CENSUS_EVIDENCE_DOMAIN_V1 = (
    b"parity-forge:plan0012:feasibility-census-evidence:v1\0"
)
_D4_HASH_DOMAIN_V1 = b"parity-forge:d4:v1\0"
_ORDERED_INPUT_ROOT_DOMAIN_V1 = (
    b"parity-forge:plan0012:ordered-case-inputs:v1\0"
)
_D4_CROSS_CHECK_ROOT_DOMAIN_V1 = (
    b"parity-forge:plan0012:feasibility-d4-cross-check:v1\0"
)
_D4_MEASUREMENT_ROOT_DOMAIN_V1 = (
    b"parity-forge:plan0012:feasibility-d4-measurements:v1\0"
)
_D4_CASE_MEASUREMENT_DOMAIN_V1 = (
    b"parity-forge:plan0012:feasibility-d4-case-measurement:v1\0"
)
_CASE_TO_D4_ROOT_DOMAIN_V1 = (
    b"parity-forge:plan0012:feasibility-case-to-d4:v1\0"
)
_D4_ORBIT_WITNESS_ROOT_DOMAIN_V1 = (
    b"parity-forge:plan0012:feasibility-d4-orbit-witness:v1\0"
)
_D4_INVARIANT_DOMAIN_V1 = (
    b"parity-forge:plan0012:feasibility-d4-invariant:v1\0"
)

_MAX_JSON_NODES_V1 = 250_000
_MAX_JSON_DEPTH_V1 = 40
_D4_CADENCE_V1 = 997

_GOAL_MASKS_V1 = ("NEITHER", "A_ONLY", "B_ONLY", "BOTH")
_MOBILITY_MASKS_V1 = ("BOTH", "A_ONLY", "B_ONLY", "NEITHER")
_REJECTION_REASONS_V1 = (
    "INITIAL_GOAL_A",
    "INITIAL_GOAL_B",
    "INSUFFICIENT_CONNECTION_MATERIAL_A",
    "INSUFFICIENT_CONNECTION_MATERIAL_B",
    "INITIAL_IMMOBILITY_A",
    "INITIAL_IMMOBILITY_B",
)
_GATE_STAGES_V1 = (
    "raw",
    "no_initial_goal",
    "connection_material_supported",
    "both_initially_mobile",
    "no_initial_goal_and_connection_material",
    "eligible",
)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _validate_json_tree(value: Any, label: str) -> None:
    nodes = 0
    active: Set[int] = set()

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


def _normalized_case(value: Any) -> FeasibilityInputV1:
    if type(value) is FeasibilityInputV1:
        return parse_feasibility_input_v1(value.to_dict())
    if type(value) is dict:
        return parse_feasibility_input_v1(value)
    raise TypeError("feasibility case must be a FeasibilityInputV1 or exact object")


def _stratum_value(case: FeasibilityInputV1) -> Dict[str, Any]:
    count = len(case.a_positions)
    return {
        "goal_frame": case.goal_frame.value,
        "setup": {"A_count": count, "B_count": len(case.b_positions)},
        "vector_profiles": {
            "A": case.a_vector_profile.value,
            "B": case.b_vector_profile.value,
        },
        "first_player": case.first_player.value,
    }


def _stratum_id(family_id: str, stratum: Mapping[str, Any]) -> str:
    payload = {"family_id": family_id, "stratum": dict(stratum)}
    return hashlib.sha256(
        _STRATUM_ID_DOMAIN_V1 + _canonical_bytes(payload)
    ).hexdigest()


def _initial_pieces(
    case: FeasibilityInputV1,
) -> Tuple[InitialPiece, ...]:
    pieces = [
        InitialPiece(owner=Player.A, piece="a", position=position)
        for position in case.a_positions
    ] + [
        InitialPiece(owner=Player.B, piece="b", position=position)
        for position in case.b_positions
    ]
    return tuple(
        sorted(
            pieces,
            key=lambda piece: (
                piece.position,
                piece.owner.value,
                piece.piece,
            ),
        )
    )


def _initial_measurements(
    definition: Any,
    pieces: Tuple[InitialPiece, ...],
) -> Tuple[
    Dict[str, bool],
    Dict[str, int],
    Dict[str, bool],
    Dict[str, Dict[str, int]],
]:
    goals = {
        "A": goal_satisfied(definition, pieces, Player.A),
        "B": goal_satisfied(definition, pieces, Player.B),
    }
    occupied = {piece.position: piece for piece in pieces}
    legal_by_role = {}
    for player in (Player.A, Player.B):
        legal_by_role[player.value] = legal_actions(
            definition,
            GameState(ply=0, to_move=player, pieces=pieces),
        )
    legal_counts = {
        label: len(actions) for label, actions in legal_by_role.items()
    }
    observations: Dict[str, Dict[str, int]] = {}
    for player in (Player.A, Player.B):
        label = player.value
        action_spec = definition.role(player).action
        dependency_count = 0
        direct_effect_count = 0
        for action in legal_by_role[label]:
            dependency = False
            direct_effect = False
            if action.kind is ActionKind.CONVERT:
                dependency = True
                direct_effect = True
            elif action.kind in (
                ActionKind.MOVE_CAPTURE,
                ActionKind.PUSH,
                ActionKind.SWAP,
            ):
                dependency = action.to_position in occupied
                direct_effect = dependency
            elif action.kind is ActionKind.HOP:
                if action.from_position is None:
                    raise AssertionError("HOP action is missing its origin")
                delta = (
                    action.to_position[0] - action.from_position[0],
                    action.to_position[1] - action.from_position[1],
                )
                dependency = delta in tuple(
                    (2 * row, 2 * column)
                    for row, column in action_spec.vectors
                )
            if dependency:
                dependency_count += 1
            if direct_effect:
                direct_effect_count += 1
        observations[label] = {
            "legal_action_count": legal_counts[label],
            "occupied_dependency_action_count": dependency_count,
            "direct_effect_action_count": direct_effect_count,
        }
    mobile = {
        "A": legal_counts["A"] > 0,
        "B": legal_counts["B"] > 0,
    }
    return goals, legal_counts, mobile, observations


def _connection_material(
    definition: Any,
    proof: Mapping[str, Any],
    case: FeasibilityInputV1,
) -> Dict[str, Any]:
    counts = {"A": len(case.a_positions), "B": len(case.b_positions)}
    roles: Dict[str, Dict[str, Any]] = {}
    for player in (Player.A, Player.B):
        label = player.value
        required = definition.role(player).goal.kind is GoalKind.CONNECT_EDGES
        minimum = definition.board_size if required else 0
        upper = proof["maximum_role_actor_counts"][label]
        roles[label] = {
            "required": required,
            "minimum_piece_count": minimum,
            "initial_piece_count": counts[label],
            "structural_piece_upper_bound": upper,
            "supported": (not required) or upper >= minimum,
        }
    return {
        "rule": FEASIBILITY_CONNECTION_MATERIAL_RULE_V1,
        "A": roles["A"],
        "B": roles["B"],
        "both_supported": roles["A"]["supported"] and roles["B"]["supported"],
    }


def _gate_value(
    goals: Mapping[str, bool],
    legal_counts: Mapping[str, int],
    mobile: Mapping[str, bool],
    connection: Mapping[str, Any],
) -> Dict[str, Any]:
    reasons = []
    for label in ("A", "B"):
        if goals[label]:
            reasons.append("INITIAL_GOAL_{}".format(label))
    for label in ("A", "B"):
        if not connection[label]["supported"]:
            reasons.append("INSUFFICIENT_CONNECTION_MATERIAL_{}".format(label))
    for label in ("A", "B"):
        if not mobile[label]:
            reasons.append("INITIAL_IMMOBILITY_{}".format(label))
    if any(reason not in _REJECTION_REASONS_V1 for reason in reasons):
        raise AssertionError("closed rejection vocabulary was not handled")
    return {
        "initial_goals": {
            "A": goals["A"],
            "B": goals["B"],
            "any": goals["A"] or goals["B"],
        },
        "connection_material": _json_copy(connection, "connection material"),
        "initial_legal_action_counts": {
            "A": legal_counts["A"],
            "B": legal_counts["B"],
        },
        "initial_mobile": {
            "A": mobile["A"],
            "B": mobile["B"],
            "both": mobile["A"] and mobile["B"],
        },
        "rejection_reasons": reasons,
        "eligible": not reasons,
    }


def _descriptor_value(
    case: FeasibilityInputV1,
    proof: Mapping[str, Any],
    action_observations: Mapping[str, Any],
) -> Dict[str, Any]:
    occupied = len(case.a_positions) + len(case.b_positions)
    board_cells = case.board_size**2
    return {
        "board_size": case.board_size,
        "initial_piece_counts": {
            "A": len(case.a_positions),
            "B": len(case.b_positions),
        },
        "initial_occupied_count": occupied,
        "initial_empty_cell_count": board_cells - occupied,
        "initial_occupancy_fraction": {
            "numerator": occupied,
            "denominator": board_cells,
        },
        "role_vector_counts": _json_copy(
            proof["role_vector_counts"], "role vector counts"
        ),
        "initial_action_observations": _json_copy(
            action_observations, "initial action observations"
        ),
        "state_bound_class": proof["state_bound_class"],
        "structural_state_upper_bound": proof[
            "structural_state_upper_bound"
        ],
        "max_action_candidates_per_state": proof[
            "max_action_candidates_per_state"
        ],
        "state_action_candidate_evaluation_upper_bound": proof[
            "state_action_candidate_evaluation_upper_bound"
        ],
    }


def _assemble_case_descriptor(
    case: FeasibilityInputV1,
    definition: Any,
    case_hash: str,
    exact_definition_hash: str,
    orbit_hash: str,
    proof: Mapping[str, Any],
    pieces: Tuple[InitialPiece, ...],
) -> Dict[str, Any]:
    stratum = _stratum_value(case)
    goals, legal_counts, mobile, action_observations = _initial_measurements(
        definition, pieces
    )
    connection = _connection_material(definition, proof, case)
    value = {
        "descriptor_version": FEASIBILITY_CASE_DESCRIPTOR_VERSION_V1,
        "case_input_hash": case_hash,
        "family_id": case.family_id,
        "stratum_id": _stratum_id(case.family_id, stratum),
        "stratum": stratum,
        "definition_hash": exact_definition_hash,
        "d4_canonical_hash": orbit_hash,
        "gate": _gate_value(goals, legal_counts, mobile, connection),
        "descriptors": _descriptor_value(case, proof, action_observations),
    }
    value["descriptor_digest"] = hashlib.sha256(
        _CASE_DESCRIPTOR_DOMAIN_V1 + _canonical_bytes(value)
    ).hexdigest()
    return _json_copy(value, "feasibility case descriptor")


def derive_feasibility_case_descriptor_v1(case_value: Any) -> Dict[str, Any]:
    """Derive one initial-position descriptor using authoritative identities."""

    case = _normalized_case(case_value)
    definition = compile_feasibility_definition_v1(case)
    proof = build_state_work_proof_v1(case)
    return _assemble_case_descriptor(
        case=case,
        definition=definition,
        case_hash=provisional_case_input_hash_v1(case),
        exact_definition_hash=definition_hash(definition),
        orbit_hash=d4_canonical_hash(definition),
        proof=proof,
        pieces=definition.initial_pieces,
    )


def feasibility_case_descriptor_digest_v1(case_value: Any) -> str:
    descriptor = derive_feasibility_case_descriptor_v1(case_value)
    return descriptor["descriptor_digest"]


def enumerate_feasibility_case_descriptors_v1(
    setup_piece_count: Optional[int] = None,
) -> Iterable[Tuple[FeasibilityInputV1, Dict[str, Any]]]:
    """Yield optimized authoritative-equivalent descriptors in domain order.

    The public one-case function remains the simple authority.  This batch path
    shares only compiler templates and structural proofs; its identity bytes are
    cross-checked by the full census and callers can independently compare any
    yielded case with :func:`derive_feasibility_case_descriptor_v1`.
    """

    if setup_piece_count is not None and (
        type(setup_piece_count) is not int or setup_piece_count not in (2, 3)
    ):
        raise ValueError("setup_piece_count must be exactly 2, 3, or None")
    templates: Dict[Tuple[str, ...], Dict[str, Any]] = {}
    proofs: Dict[Tuple[str, int, str, str], Dict[str, Any]] = {}
    for case in enumerate_feasibility_inputs_v1():
        count = len(case.a_positions)
        if setup_piece_count is not None and count != setup_piece_count:
            continue
        template_key = _template_key(case)
        template = templates.get(template_key)
        if template is None:
            template = _build_template(case)
            templates[template_key] = template
        proof_key = (
            case.family_id,
            count,
            case.a_vector_profile.value,
            case.b_vector_profile.value,
        )
        proof = proofs.get(proof_key)
        if proof is None:
            proof = build_state_work_proof_v1(case)
            proofs[proof_key] = proof
        yield case, _fast_case_descriptor(case, template, proof)


def _transformed_pieces(
    case: FeasibilityInputV1, transform: str
) -> Tuple[InitialPiece, ...]:
    pieces = [
        InitialPiece(
            owner=Player.A,
            piece="a",
            position=transform_position(
                position, case.board_size, transform
            ),
        )
        for position in case.a_positions
    ] + [
        InitialPiece(
            owner=Player.B,
            piece="b",
            position=transform_position(
                position, case.board_size, transform
            ),
        )
        for position in case.b_positions
    ]
    return tuple(
        sorted(
            pieces,
            key=lambda piece: (
                piece.position,
                piece.owner.value,
                piece.piece,
            ),
        )
    )


def _piece_dicts(
    case: FeasibilityInputV1, transform: str
) -> List[Dict[str, Any]]:
    return [piece.to_dict() for piece in _transformed_pieces(case, transform)]


def _template_key(case: FeasibilityInputV1) -> Tuple[str, ...]:
    return (
        case.family_id,
        case.goal_frame.value,
        case.a_vector_profile.value,
        case.b_vector_profile.value,
        case.first_player.value,
    )


def _build_template(case: FeasibilityInputV1) -> Dict[str, Any]:
    definition = compile_feasibility_definition_v1(case)
    transformed = []
    for transform in D4_TRANSFORMS:
        transformed_definition = transform_definition(definition, transform)
        base = transformed_definition.to_dict()
        del base["name"]
        del base["initial_pieces"]
        transformed.append(
            {
                "transform": transform,
                "definition": transformed_definition,
                "mechanical_base": base,
            }
        )
    return {
        "definition": definition,
        "transformed": tuple(transformed),
    }


def _fast_definition_and_d4_hashes(
    case: FeasibilityInputV1,
    case_hash: str,
    template: Mapping[str, Any],
) -> Tuple[str, str]:
    candidates = []
    exact_bytes: Optional[bytes] = None
    for item in template["transformed"]:
        transform = item["transform"]
        mechanical = dict(item["mechanical_base"])
        mechanical["initial_pieces"] = _piece_dicts(case, transform)
        mechanical_bytes = _canonical_bytes(mechanical)
        candidates.append(mechanical_bytes)
        if transform == "I":
            exact = dict(mechanical)
            exact["name"] = "pf12-{}-{}".format(
                case.family_id, case_hash[:20]
            )
            exact_bytes = _canonical_bytes(exact)
    if exact_bytes is None or len(candidates) != len(D4_TRANSFORMS):
        raise AssertionError("cached D4 template is incomplete")
    return (
        hashlib.sha256(exact_bytes).hexdigest(),
        hashlib.sha256(_D4_HASH_DOMAIN_V1 + min(candidates)).hexdigest(),
    )


def _fast_case_descriptor(
    case: FeasibilityInputV1,
    template: Mapping[str, Any],
    proof: Mapping[str, Any],
) -> Dict[str, Any]:
    case_hash = provisional_case_input_hash_v1(case)
    exact_hash, orbit_hash = _fast_definition_and_d4_hashes(
        case, case_hash, template
    )
    return _assemble_case_descriptor(
        case=case,
        definition=template["definition"],
        case_hash=case_hash,
        exact_definition_hash=exact_hash,
        orbit_hash=orbit_hash,
        proof=proof,
        pieces=_initial_pieces(case),
    )


def _goal_mask(gate: Mapping[str, Any]) -> str:
    a_goal = gate["initial_goals"]["A"]
    b_goal = gate["initial_goals"]["B"]
    if a_goal and b_goal:
        return "BOTH"
    if a_goal:
        return "A_ONLY"
    if b_goal:
        return "B_ONLY"
    return "NEITHER"


def _mobility_mask(gate: Mapping[str, Any]) -> str:
    a_mobile = gate["initial_mobile"]["A"]
    b_mobile = gate["initial_mobile"]["B"]
    if a_mobile and b_mobile:
        return "BOTH"
    if a_mobile:
        return "A_ONLY"
    if b_mobile:
        return "B_ONLY"
    return "NEITHER"


def _stage_flags(gate: Mapping[str, Any]) -> Dict[str, bool]:
    no_goal = not gate["initial_goals"]["any"]
    material = gate["connection_material"]["both_supported"]
    mobile = gate["initial_mobile"]["both"]
    return {
        "raw": True,
        "no_initial_goal": no_goal,
        "connection_material_supported": material,
        "both_initially_mobile": mobile,
        "no_initial_goal_and_connection_material": no_goal and material,
        "eligible": gate["eligible"],
    }


def _stream_hasher(scope_id: str, label: str) -> Any:
    domain = "parity-forge:plan0012:feasibility-census:{}:{}:v1\0".format(
        scope_id, label
    ).encode("utf-8")
    return hashlib.sha256(domain)


def _update_stream(hasher: Any, digest: str) -> None:
    hasher.update(digest.encode("ascii"))
    hasher.update(b"\n")


def _new_accumulator(scope_id: str) -> Dict[str, Any]:
    return {
        "scope_id": scope_id,
        "gate_exact": Counter(),
        "gate_orbits": Counter(),
        "goal_exact": Counter(),
        "goal_orbits": Counter(),
        "mobility_exact": Counter(),
        "mobility_orbits": Counter(),
        "reasons_exact": Counter(),
        "reasons_orbits": Counter(),
        "reason_combinations_exact": Counter(),
        "reason_combinations_orbits": Counter(),
        "observations_exact": Counter(),
        "observations_orbits": Counter(),
        "occupancy_exact": Counter(),
        "occupancy_orbits": Counter(),
        "state_exact": Counter(),
        "state_orbits": Counter(),
        "work_exact": Counter(),
        "work_orbits": Counter(),
        "multiplicity": Counter(),
        "raw_d4": set(),
        "eligible_d4": set(),
        "raw_case_root": _stream_hasher(scope_id, "raw-case-inputs"),
        "eligible_case_root": _stream_hasher(
            scope_id, "eligible-case-inputs"
        ),
        "raw_definition_root": _stream_hasher(
            scope_id, "raw-definitions"
        ),
        "eligible_definition_root": _stream_hasher(
            scope_id, "eligible-definitions"
        ),
        "raw_descriptor_root": _stream_hasher(
            scope_id, "raw-case-descriptors"
        ),
        "eligible_descriptor_root": _stream_hasher(
            scope_id, "eligible-case-descriptors"
        ),
    }


def _observe_exact(accumulator: Dict[str, Any], descriptor: Mapping[str, Any]) -> None:
    gate = descriptor["gate"]
    stages = _stage_flags(gate)
    for stage, passed in stages.items():
        if passed:
            accumulator["gate_exact"][stage] += 1
    accumulator["goal_exact"][_goal_mask(gate)] += 1
    accumulator["mobility_exact"][_mobility_mask(gate)] += 1
    for reason in gate["rejection_reasons"]:
        accumulator["reasons_exact"][reason] += 1
    accumulator["reason_combinations_exact"][
        tuple(gate["rejection_reasons"])
    ] += 1

    _update_stream(accumulator["raw_case_root"], descriptor["case_input_hash"])
    _update_stream(
        accumulator["raw_definition_root"], descriptor["definition_hash"]
    )
    _update_stream(
        accumulator["raw_descriptor_root"], descriptor["descriptor_digest"]
    )
    if gate["eligible"]:
        _update_stream(
            accumulator["eligible_case_root"], descriptor["case_input_hash"]
        )
        _update_stream(
            accumulator["eligible_definition_root"],
            descriptor["definition_hash"],
        )
        _update_stream(
            accumulator["eligible_descriptor_root"],
            descriptor["descriptor_digest"],
        )

    _observe_distributions(
        accumulator, descriptor, population="raw", orbit=False
    )
    if gate["eligible"]:
        _observe_distributions(
            accumulator, descriptor, population="eligible", orbit=False
        )


def _observe_orbit(
    accumulator: Dict[str, Any],
    descriptor: Mapping[str, Any],
    orbit_hash: str,
    multiplicity: int,
) -> None:
    gate = descriptor["gate"]
    stages = _stage_flags(gate)
    for stage, passed in stages.items():
        if passed:
            accumulator["gate_orbits"][stage] += 1
    accumulator["goal_orbits"][_goal_mask(gate)] += 1
    accumulator["mobility_orbits"][_mobility_mask(gate)] += 1
    for reason in gate["rejection_reasons"]:
        accumulator["reasons_orbits"][reason] += 1
    accumulator["reason_combinations_orbits"][
        tuple(gate["rejection_reasons"])
    ] += 1
    accumulator["multiplicity"][multiplicity] += 1
    accumulator["raw_d4"].add(orbit_hash)
    if gate["eligible"]:
        accumulator["eligible_d4"].add(orbit_hash)

    _observe_distributions(
        accumulator, descriptor, population="raw", orbit=True
    )
    if gate["eligible"]:
        _observe_distributions(
            accumulator, descriptor, population="eligible", orbit=True
        )


def _observe_distributions(
    accumulator: Dict[str, Any],
    descriptor: Mapping[str, Any],
    population: str,
    orbit: bool,
) -> None:
    suffix = "orbits" if orbit else "exact"
    observations = descriptor["descriptors"]["initial_action_observations"]
    for role in ("A", "B"):
        for metric in (
            "legal_action_count",
            "occupied_dependency_action_count",
            "direct_effect_action_count",
        ):
            accumulator["observations_{}".format(suffix)][
                (population, role, metric, observations[role][metric])
            ] += 1
    occupied = descriptor["descriptors"]["initial_occupied_count"]
    accumulator["occupancy_{}".format(suffix)][
        (population, occupied)
    ] += 1
    state_bound = descriptor["descriptors"]["structural_state_upper_bound"]
    accumulator["state_{}".format(suffix)][
        (population, state_bound)
    ] += 1
    maximum_candidates = descriptor["descriptors"][
        "max_action_candidates_per_state"
    ]
    work_bound = descriptor["descriptors"][
        "state_action_candidate_evaluation_upper_bound"
    ]
    accumulator["work_{}".format(suffix)][
        (population, state_bound, maximum_candidates, work_bound)
    ] += 1


def _sorted_d4_root(scope_id: str, label: str, hashes: Iterable[str]) -> str:
    hasher = _stream_hasher(scope_id, label)
    for orbit_hash in sorted(hashes):
        _update_stream(hasher, orbit_hash)
    return hasher.hexdigest()


def _histogram(counter: Counter, prefix: Tuple[Any, ...]) -> Dict[str, int]:
    values = {
        key[len(prefix)]: count
        for key, count in counter.items()
        if type(key) is tuple and key[: len(prefix)] == prefix
    }
    return {str(value): values[value] for value in sorted(values)}


def _observation_summary(
    counter: Counter,
    population: str,
    role: str,
    metric: str,
) -> Dict[str, Any]:
    histogram = _histogram(counter, (population, role, metric))
    numeric = {int(value): count for value, count in histogram.items()}
    return {
        "observation_count": sum(numeric.values()),
        "minimum": min(numeric) if numeric else None,
        "maximum": max(numeric) if numeric else None,
        "sum": sum(value * count for value, count in numeric.items()),
        "histogram": histogram,
    }


def _population_distribution(
    counter: Counter, population: str
) -> Dict[str, int]:
    values = {
        key[1]: count
        for key, count in counter.items()
        if type(key) is tuple and len(key) == 2 and key[0] == population
    }
    return {str(value): values[value] for value in sorted(values)}


def _work_distribution(counter: Counter, population: str) -> Dict[str, int]:
    values = {}
    for key, count in counter.items():
        if type(key) is not tuple or len(key) != 4 or key[0] != population:
            continue
        _, state_bound, maximum_candidates, work_bound = key
        label = "state={};max_candidates={};work={}".format(
            state_bound, maximum_candidates, work_bound
        )
        values[label] = count
    return {label: values[label] for label in sorted(values)}


def _finalize_accumulator(
    accumulator: Dict[str, Any], include_roots: bool = True
) -> Dict[str, Any]:
    action_observations = {}
    for population in ("raw", "eligible"):
        action_observations[population] = {}
        for evidence_kind, counter_key in (
            ("exact", "observations_exact"),
            ("d4_orbits", "observations_orbits"),
        ):
            action_observations[population][evidence_kind] = {
                role: {
                    metric: _observation_summary(
                        accumulator[counter_key], population, role, metric
                    )
                    for metric in (
                        "legal_action_count",
                        "occupied_dependency_action_count",
                        "direct_effect_action_count",
                    )
                }
                for role in ("A", "B")
            }

    occupancy = {}
    state_bounds = {}
    work_bounds = {}
    for population in ("raw", "eligible"):
        occupancy[population] = {
            "exact": _population_distribution(
                accumulator["occupancy_exact"], population
            ),
            "d4_orbits": _population_distribution(
                accumulator["occupancy_orbits"], population
            ),
        }
        state_bounds[population] = {
            "exact": _population_distribution(
                accumulator["state_exact"], population
            ),
            "d4_orbits": _population_distribution(
                accumulator["state_orbits"], population
            ),
        }
        work_bounds[population] = {
            "exact": _work_distribution(
                accumulator["work_exact"], population
            ),
            "d4_orbits": _work_distribution(
                accumulator["work_orbits"], population
            ),
        }

    scope_id = accumulator["scope_id"]
    reason_combinations = sorted(
        set(accumulator["reason_combinations_exact"])
        | set(accumulator["reason_combinations_orbits"])
    )
    result = {
        "case_counts": {
            "raw": accumulator["gate_exact"]["raw"],
            "eligible": accumulator["gate_exact"]["eligible"],
        },
        "d4_orbit_counts": {
            "raw": accumulator["gate_orbits"]["raw"],
            "eligible": accumulator["gate_orbits"]["eligible"],
        },
        "gate_counts": {
            stage: {
                "exact": accumulator["gate_exact"][stage],
                "d4_orbits": accumulator["gate_orbits"][stage],
            }
            for stage in _GATE_STAGES_V1
        },
        "initial_goal_masks": {
            mask: {
                "exact": accumulator["goal_exact"][mask],
                "d4_orbits": accumulator["goal_orbits"][mask],
            }
            for mask in _GOAL_MASKS_V1
        },
        "initial_mobility_masks": {
            mask: {
                "exact": accumulator["mobility_exact"][mask],
                "d4_orbits": accumulator["mobility_orbits"][mask],
            }
            for mask in _MOBILITY_MASKS_V1
        },
        "rejection_reason_counts": {
            reason: {
                "exact": accumulator["reasons_exact"][reason],
                "d4_orbits": accumulator["reasons_orbits"][reason],
            }
            for reason in _REJECTION_REASONS_V1
        },
        "rejection_reason_combinations": [
            {
                "reasons": list(reasons),
                "exact": accumulator["reason_combinations_exact"][reasons],
                "d4_orbits": accumulator[
                    "reason_combinations_orbits"
                ][reasons],
            }
            for reasons in reason_combinations
        ],
        "initial_action_observations": action_observations,
        "initial_occupancy_counts": occupancy,
        "structural_state_upper_bounds": state_bounds,
        "state_action_candidate_work_bounds": work_bounds,
        "d4_orbit_multiplicity_histogram": {
            str(multiplicity): accumulator["multiplicity"][multiplicity]
            for multiplicity in sorted(accumulator["multiplicity"])
        },
        "roots": {
            "ordered_raw_case_input_root": accumulator[
                "raw_case_root"
            ].hexdigest(),
            "ordered_eligible_case_input_root": accumulator[
                "eligible_case_root"
            ].hexdigest(),
            "ordered_raw_definition_root": accumulator[
                "raw_definition_root"
            ].hexdigest(),
            "ordered_eligible_definition_root": accumulator[
                "eligible_definition_root"
            ].hexdigest(),
            "ordered_raw_case_descriptor_root": accumulator[
                "raw_descriptor_root"
            ].hexdigest(),
            "ordered_eligible_case_descriptor_root": accumulator[
                "eligible_descriptor_root"
            ].hexdigest(),
            "sorted_raw_d4_root": _sorted_d4_root(
                scope_id, "raw-d4-orbits", accumulator["raw_d4"]
            ),
            "sorted_eligible_d4_root": _sorted_d4_root(
                scope_id,
                "eligible-d4-orbits",
                accumulator["eligible_d4"],
            ),
        },
    }
    if not include_roots:
        del result["roots"]
    return result


def _descriptor_invariant(descriptor: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "descriptor_version": descriptor["descriptor_version"],
        "family_id": descriptor["family_id"],
        "stratum_id": descriptor["stratum_id"],
        "stratum": descriptor["stratum"],
        "gate": descriptor["gate"],
        "descriptors": descriptor["descriptors"],
    }


def _verify_d4_measurements(
    case: FeasibilityInputV1,
    template: Mapping[str, Any],
    descriptor: Mapping[str, Any],
) -> Tuple[int, str]:
    expected = {
        "initial_goals": descriptor["gate"]["initial_goals"],
        "initial_legal_action_counts": descriptor["gate"][
            "initial_legal_action_counts"
        ],
        "initial_mobile": descriptor["gate"]["initial_mobile"],
        "initial_action_observations": descriptor["descriptors"][
            "initial_action_observations"
        ],
    }
    expected_bytes = _canonical_bytes(expected)
    evidence = hashlib.sha256(_D4_CASE_MEASUREMENT_DOMAIN_V1)
    checked = 0
    for item in template["transformed"]:
        transform = item["transform"]
        goals, legal_counts, mobile, observations = _initial_measurements(
            item["definition"], _transformed_pieces(case, transform)
        )
        observed = {
            "initial_goals": {
                "A": goals["A"],
                "B": goals["B"],
                "any": goals["A"] or goals["B"],
            },
            "initial_legal_action_counts": legal_counts,
            "initial_mobile": {
                "A": mobile["A"],
                "B": mobile["B"],
                "both": mobile["A"] and mobile["B"],
            },
            "initial_action_observations": observations,
        }
        observed_bytes = _canonical_bytes(observed)
        if observed_bytes != expected_bytes:
            raise AssertionError(
                "initial descriptor is not D4-invariant for {}".format(
                    transform
                )
            )
        evidence.update(
            _canonical_bytes(
                {
                    "transform": transform,
                    "observed_digest": hashlib.sha256(
                        observed_bytes
                    ).hexdigest(),
                }
            )
        )
        evidence.update(b"\n")
        checked += 1
    return checked, evidence.hexdigest()


def _build_feasibility_census_uncached_v1() -> Dict[str, Any]:
    templates: Dict[Tuple[str, ...], Dict[str, Any]] = {}
    proofs: Dict[Tuple[str, int, str, str], Dict[str, Any]] = {}
    global_accumulator = _new_accumulator("global")
    family_accumulators: Dict[str, Dict[str, Any]] = {}
    stratum_accumulators: Dict[str, Dict[str, Any]] = {}
    stratum_records: Dict[str, Dict[str, Any]] = {}
    family_order: List[str] = []
    stratum_order: List[str] = []
    orbit_records: Dict[str, Dict[str, Any]] = {}

    ordered_input_root = hashlib.sha256(_ORDERED_INPUT_ROOT_DOMAIN_V1)
    case_to_d4_root = hashlib.sha256(_CASE_TO_D4_ROOT_DOMAIN_V1)
    cross_check_root = hashlib.sha256(_D4_CROSS_CHECK_ROOT_DOMAIN_V1)
    measurement_root = hashlib.sha256(_D4_MEASUREMENT_ROOT_DOMAIN_V1)
    checked_strata: Set[str] = set()
    cross_check_case_count = 0
    cross_check_transform_count = 0

    case_count = 0
    for index, case in enumerate(enumerate_feasibility_inputs_v1()):
        case_count += 1
        template_key = _template_key(case)
        template = templates.get(template_key)
        if template is None:
            template = _build_template(case)
            templates[template_key] = template

        proof_key = (
            case.family_id,
            len(case.a_positions),
            case.a_vector_profile.value,
            case.b_vector_profile.value,
        )
        proof = proofs.get(proof_key)
        if proof is None:
            proof = build_state_work_proof_v1(case)
            proofs[proof_key] = proof

        descriptor = _fast_case_descriptor(case, template, proof)
        case_hash = descriptor["case_input_hash"]
        _update_stream(ordered_input_root, case_hash)
        transform_check_count, transform_measurement_digest = (
            _verify_d4_measurements(
                case, template, descriptor
            )
        )
        cross_check_transform_count += transform_check_count
        measurement_root.update(
            _canonical_bytes(
                {
                    "case_index": index,
                    "case_input_hash": case_hash,
                    "descriptor_digest": descriptor["descriptor_digest"],
                    "transform_check_count": transform_check_count,
                    "transform_measurement_digest": (
                        transform_measurement_digest
                    ),
                }
            )
        )
        measurement_root.update(b"\n")

        family_id = descriptor["family_id"]
        if family_id not in family_accumulators:
            family_order.append(family_id)
            family_accumulators[family_id] = _new_accumulator(
                "family-{}".format(family_id)
            )
        stratum_id = descriptor["stratum_id"]
        if stratum_id not in stratum_accumulators:
            stratum_order.append(stratum_id)
            stratum_accumulators[stratum_id] = _new_accumulator(
                "stratum-{}".format(stratum_id)
            )
            stratum_records[stratum_id] = {
                "stratum_id": stratum_id,
                "family_id": family_id,
                "stratum": descriptor["stratum"],
            }

        for accumulator in (
            global_accumulator,
            family_accumulators[family_id],
            stratum_accumulators[stratum_id],
        ):
            _observe_exact(accumulator, descriptor)

        orbit_hash = descriptor["d4_canonical_hash"]
        case_to_d4_root.update(
            _canonical_bytes(
                {
                    "case_index": index,
                    "case_input_hash": case_hash,
                    "family_id": family_id,
                    "stratum_id": stratum_id,
                    "d4_canonical_hash": orbit_hash,
                }
            )
        )
        case_to_d4_root.update(b"\n")
        invariant = _descriptor_invariant(descriptor)
        orbit_record = orbit_records.get(orbit_hash)
        if orbit_record is None:
            orbit_records[orbit_hash] = {
                "descriptor": descriptor,
                "invariant": invariant,
                "multiplicity": 1,
                "representative_case_input_hash": case_hash,
            }
        else:
            if _canonical_bytes(orbit_record["invariant"]) != _canonical_bytes(
                invariant
            ):
                raise AssertionError(
                    "one D4 orbit has non-invariant feasibility descriptors"
                )
            orbit_record["multiplicity"] += 1
            if case_hash < orbit_record["representative_case_input_hash"]:
                orbit_record["representative_case_input_hash"] = case_hash

        first_in_stratum = stratum_id not in checked_strata
        cadence_member = index % _D4_CADENCE_V1 == 0
        if first_in_stratum or cadence_member:
            checked_strata.add(stratum_id)
            authoritative = derive_feasibility_case_descriptor_v1(case)
            if _canonical_bytes(authoritative) != _canonical_bytes(descriptor):
                raise AssertionError(
                    "optimized case descriptor differs from authoritative path"
                )
            record = {
                "case_index": index,
                "case_input_hash": case_hash,
                "stratum_id": stratum_id,
                "first_in_stratum": first_in_stratum,
                "cadence_member": cadence_member,
                "descriptor_digest": descriptor["descriptor_digest"],
                "definition_hash": descriptor["definition_hash"],
                "d4_canonical_hash": orbit_hash,
                "transform_check_count": len(D4_TRANSFORMS),
            }
            cross_check_root.update(_canonical_bytes(record))
            cross_check_root.update(b"\n")
            cross_check_case_count += 1

    if case_count != FEASIBILITY_INPUT_COUNT_V1:
        raise AssertionError(
            "feasibility census enumerated {} cases, expected {}".format(
                case_count, FEASIBILITY_INPUT_COUNT_V1
            )
        )
    if len(family_order) != 6 or len(stratum_order) != 176:
        raise AssertionError("feasibility family or stratum census drifted")

    orbit_witness_root = hashlib.sha256(_D4_ORBIT_WITNESS_ROOT_DOMAIN_V1)
    for orbit_hash in sorted(orbit_records):
        orbit_record = orbit_records[orbit_hash]
        descriptor = orbit_record["descriptor"]
        family_id = descriptor["family_id"]
        stratum_id = descriptor["stratum_id"]
        multiplicity = orbit_record["multiplicity"]
        orbit_witness_root.update(
            _canonical_bytes(
                {
                    "d4_canonical_hash": orbit_hash,
                    "family_id": family_id,
                    "stratum_id": stratum_id,
                    "representative_case_input_hash": orbit_record[
                        "representative_case_input_hash"
                    ],
                    "multiplicity": multiplicity,
                    "eligible": descriptor["gate"]["eligible"],
                    "rejection_reasons": descriptor["gate"][
                        "rejection_reasons"
                    ],
                    "invariant_digest": hashlib.sha256(
                        _D4_INVARIANT_DOMAIN_V1
                        + _canonical_bytes(orbit_record["invariant"])
                    ).hexdigest(),
                }
            )
        )
        orbit_witness_root.update(b"\n")
        for accumulator in (
            global_accumulator,
            family_accumulators[family_id],
            stratum_accumulators[stratum_id],
        ):
            _observe_orbit(
                accumulator, descriptor, orbit_hash, multiplicity
            )

    families = []
    for family_id in family_order:
        family = {"family_id": family_id}
        family.update(_finalize_accumulator(family_accumulators[family_id]))
        families.append(family)
    strata = []
    for stratum_id in stratum_order:
        stratum = dict(stratum_records[stratum_id])
        stratum.update(
            _finalize_accumulator(
                stratum_accumulators[stratum_id], include_roots=False
            )
        )
        strata.append(stratum)

    stratum_root = _stream_hasher("global", "ordered-strata")
    for stratum_id in stratum_order:
        _update_stream(stratum_root, stratum_id)

    report = {
        "census_version": FEASIBILITY_CENSUS_VERSION_V1,
        "census_id": FEASIBILITY_CENSUS_ID_V1,
        "status": "PROVISIONAL_OUTCOME_FREE_FEASIBILITY_EVIDENCE",
        "domain": {
            "domain_hash": feasibility_domain_hash_v1(),
            "ordered_input_root": ordered_input_root.hexdigest(),
            "case_input_count": case_count,
        },
        "protocol": {
            "domain_hash": feasibility_domain_hash_v1(),
            "input_count": FEASIBILITY_INPUT_COUNT_V1,
            "case_descriptor_version": FEASIBILITY_CASE_DESCRIPTOR_VERSION_V1,
            "compiler": {
                "compiler_id": FEASIBILITY_COMPILER_ID,
                "compiler_version": FEASIBILITY_COMPILER_VERSION,
                "state_work_proof_version": (
                    PROVISIONAL_STATE_WORK_PROOF_VERSION_V1
                ),
            },
            "d4_canonicalization": {
                "canonicalization_id": FEASIBILITY_D4_CANONICALIZATION_ID,
                "canonicalization_version": (
                    FEASIBILITY_D4_CANONICALIZATION_VERSION
                ),
                "transforms": list(D4_TRANSFORMS),
            },
            "gate": {
                "gate_id": FEASIBILITY_CENSUS_GATE_ID_V1,
                "connection_material_rule": (
                    FEASIBILITY_CONNECTION_MATERIAL_RULE_V1
                ),
                "connection_geometric_minimum_rule": (
                    "BOARD_SIZE_FOR_OPPOSITE_ORTHOGONAL_EDGES"
                ),
                "requirements": [
                    "NO_INITIAL_GOAL_FOR_EITHER_ROLE",
                    "BOTH_CONNECTION_MATERIAL_UPPER_BOUNDS_SUPPORTED",
                    "BOTH_ROLES_HAVE_AN_INITIAL_LEGAL_ACTION",
                ],
                "rejection_reason_vocabulary": list(_REJECTION_REASONS_V1),
                "rejection_reason_partition": (
                    "ORDERED_COMPLETE_REASON_COMBINATION_V1"
                ),
            },
            "stratum_dimensions": [
                "family_id",
                "goal_frame",
                "setup",
                "vector_profiles",
                "first_player",
            ],
            "initial_action_observation_contract": {
                "occupied_dependency": (
                    "CONVERT_OR_CONDITIONAL_CAPTURE_PUSH_SWAP_OR_HOP"
                ),
                "direct_effect": (
                    "CONVERT_OR_CONDITIONAL_CAPTURE_PUSH_SWAP"
                ),
                "hop_direct_effect": False,
            },
            "optimized_identity_path": {
                "method": (
                    "CACHED_TRANSFORMED_MECHANICAL_FIELDS_WITH_"
                    "CANONICAL_PIECE_REINSERTION_V1"
                ),
                "position_transform_authority": (
                    "parity_forge.symmetry.transform_position"
                ),
                "canonical_bytes_match_public_d4_contract": True,
                "cross_check_schedule": (
                    "FIRST_CASE_PER_176_STRATA_PLUS_EVERY_997TH_INPUT_V1"
                ),
            },
        },
        "global": _finalize_accumulator(global_accumulator),
        "families": families,
        "strata": strata,
        "roots": {
            "ordered_input_root": ordered_input_root.hexdigest(),
            "ordered_stratum_root": stratum_root.hexdigest(),
            "ordered_case_to_d4_root": case_to_d4_root.hexdigest(),
            "sorted_d4_orbit_witness_root": orbit_witness_root.hexdigest(),
        },
        "d4_cross_check": {
            "all_invariant": True,
            "invariant_case_count": case_count,
            "checked_transform_count": cross_check_transform_count,
            "violation_count": 0,
            "measurement_evidence_root": measurement_root.hexdigest(),
            "authoritative_identity_case_count": cross_check_case_count,
            "authoritative_identity_stratum_count": len(checked_strata),
            "authoritative_identity_transform_count": (
                cross_check_case_count * len(D4_TRANSFORMS)
            ),
            "authoritative_identity_mismatch_count": 0,
            "authoritative_identity_evidence_root": cross_check_root.hexdigest(),
        },
    }
    report["evidence_digest"] = hashlib.sha256(
        _CENSUS_EVIDENCE_DOMAIN_V1 + _canonical_bytes(report)
    ).hexdigest()
    expected_parent_roots = {
        "evidence_digest": FEASIBILITY_CENSUS_EVIDENCE_DIGEST_V1,
        "ordered_case_to_d4_root": FEASIBILITY_ORDERED_CASE_TO_D4_ROOT_V1,
        "sorted_eligible_d4_root": FEASIBILITY_SORTED_ELIGIBLE_D4_ROOT_V1,
    }
    observed_parent_roots = {
        "evidence_digest": report["evidence_digest"],
        "ordered_case_to_d4_root": report["roots"][
            "ordered_case_to_d4_root"
        ],
        "sorted_eligible_d4_root": report["global"]["roots"][
            "sorted_eligible_d4_root"
        ],
    }
    if observed_parent_roots != expected_parent_roots:
        raise AssertionError("frozen feasibility census parent roots drifted")
    return _json_copy(report, "feasibility census")


@lru_cache(maxsize=1)
def _cached_feasibility_census_json_v1() -> str:
    return _canonical_bytes(_build_feasibility_census_uncached_v1()).decode(
        "utf-8"
    )


def build_feasibility_census_v1() -> Dict[str, Any]:
    """Build or retrieve the detached compact full-domain census."""

    return json.loads(_cached_feasibility_census_json_v1())


def validate_feasibility_census_v1(value: Any) -> Dict[str, Any]:
    """Rebuild every retained census claim and reject any field drift."""

    if type(value) is not dict:
        raise TypeError("feasibility census must be an exact object")
    _validate_json_tree(value, "feasibility census")
    entry = _canonical_bytes(value)
    expected_json = _cached_feasibility_census_json_v1()
    expected = expected_json.encode("utf-8")
    if entry != expected:
        raise ValueError("feasibility census does not reconstruct")
    if entry != _canonical_bytes(value):
        raise ValueError("feasibility census changed during validation")
    return json.loads(expected_json)


def canonical_feasibility_census_json_v1(value: Optional[Any] = None) -> str:
    if value is None:
        return _cached_feasibility_census_json_v1()
    validated = validate_feasibility_census_v1(value)
    return _canonical_bytes(validated).decode("utf-8")


def feasibility_census_hash_v1(value: Optional[Any] = None) -> str:
    if value is None:
        report = build_feasibility_census_v1()
    else:
        report = validate_feasibility_census_v1(value)
    return report["evidence_digest"]


__all__ = (
    "FEASIBILITY_CASE_DESCRIPTOR_VERSION_V1",
    "FEASIBILITY_CENSUS_GATE_ID_V1",
    "FEASIBILITY_CENSUS_ID_V1",
    "FEASIBILITY_CENSUS_EVIDENCE_DIGEST_V1",
    "FEASIBILITY_CENSUS_VERSION_V1",
    "FEASIBILITY_CONNECTION_MATERIAL_RULE_V1",
    "FEASIBILITY_ORDERED_CASE_TO_D4_ROOT_V1",
    "FEASIBILITY_SORTED_ELIGIBLE_D4_ROOT_V1",
    "build_feasibility_census_v1",
    "canonical_feasibility_census_json_v1",
    "derive_feasibility_case_descriptor_v1",
    "enumerate_feasibility_case_descriptors_v1",
    "feasibility_case_descriptor_digest_v1",
    "feasibility_census_hash_v1",
    "validate_feasibility_census_v1",
)
