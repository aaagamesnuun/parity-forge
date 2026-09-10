"""Pure outcome-free feasibility inputs for the provisional Plan-0012 portfolio.

This module is deliberately narrower than a generator or experiment runner.  It
defines one provisional, finite 3x3 input domain; compiles an input into the
authoritative schema-v4 DSL; and reconstructs identities and conservative work
bounds.  It never applies an action, constructs gameplay, solves a position, or
uses an outcome.

The domain is not a final family registry or search envelope.  Its six labels
are the provisional cells named by Plan 0012, and its census evidence may later
justify revising or removing a cell before any gameplay plan is authorized.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from enum import Enum
from itertools import combinations
from typing import Any, Dict, Iterable, Iterator, Mapping, Optional, Tuple

from .dsl import (
    ActionKind,
    GameDefinition,
    GoalKind,
    Player,
    canonical_json,
    definition_hash,
    parse_definition,
)
from .family import (
    ActionPrimitive,
    FamilySignature,
    GoalPrimitive,
    RoleSignature,
    StateKernel,
    TerminalContract,
    TurnStructure,
    canonical_family_signature_json,
    family_signature_hash,
    validate_nonretired_family_signature,
)
from .symmetry import d4_canonical_hash


PROVISIONAL_DOMAIN_VERSION_V1 = 1
PROVISIONAL_CASE_INPUT_VERSION_V1 = 1
PROVISIONAL_DERIVATION_WITNESS_VERSION_V1 = 1
PROVISIONAL_STATE_WORK_PROOF_VERSION_V1 = 1

PROVISIONAL_DSL_SCHEMA_VERSION_V1 = 4
PROVISIONAL_BOARD_SIZE_V1 = 3
PROVISIONAL_MAX_PLIES_V1 = 18
PROVISIONAL_MAX_JSON_NODES_V1 = 100_000
PROVISIONAL_MAX_JSON_DEPTH_V1 = 32

FEASIBILITY_DOMAIN_ID = "plan0012-provisional-feasibility-domain-v1"
FEASIBILITY_ENUMERATOR_ID = "plan0012-provisional-feasibility-enumerator-v1"
FEASIBILITY_ENUMERATOR_VERSION = 1
FEASIBILITY_COMPILER_ID = "plan0012-occupancy-v4-compiler-v1"
FEASIBILITY_COMPILER_VERSION = 1
FEASIBILITY_D4_CANONICALIZATION_ID = "square-definition-d4-v1"
FEASIBILITY_D4_CANONICALIZATION_VERSION = 1

_BOARD_CELLS_V1 = tuple(
    (row, column)
    for row in range(PROVISIONAL_BOARD_SIZE_V1)
    for column in range(PROVISIONAL_BOARD_SIZE_V1)
)
_SETUP_COUNT_PAIRS_V1 = ((2, 2), (3, 3))
_FIRST_PLAYERS_V1 = (Player.A, Player.B)
if PROVISIONAL_MAX_PLIES_V1 != 2 * len(_BOARD_CELLS_V1):
    raise AssertionError("provisional max-plies rule drifted")

_CASE_INPUT_HASH_DOMAIN_V1 = b"parity-forge:plan0012:case-input:v1\0"
_DOMAIN_HASH_DOMAIN_V1 = b"parity-forge:plan0012:provisional-domain:v1\0"
_WITNESS_HASH_DOMAIN_V1 = b"parity-forge:plan0012:derivation-witness:v1\0"


class VectorProfileV1(str, Enum):
    """The two D4-invariant local direction profiles in the provisional domain."""

    ORTHOGONAL_4 = "ORTHOGONAL_4"
    KING_8 = "KING_8"


class GoalFrameV1(str, Enum):
    """One canonical representative of each family-specific D4 goal relation."""

    REACH_REACH_SAME = "REACH_REACH_SAME"
    REACH_REACH_OPPOSITE = "REACH_REACH_OPPOSITE"
    REACH_REACH_ADJACENT = "REACH_REACH_ADJACENT"
    CONNECT_REACH_ALIGNED = "CONNECT_REACH_ALIGNED"
    CONNECT_REACH_PERPENDICULAR = "CONNECT_REACH_PERPENDICULAR"
    ELIMINATE_REACH = "ELIMINATE_REACH"
    ELIMINATE_ELIMINATE = "ELIMINATE_ELIMINATE"
    CONNECT_CONNECT_SAME_AXIS = "CONNECT_CONNECT_SAME_AXIS"
    CONNECT_CONNECT_PERPENDICULAR = "CONNECT_CONNECT_PERPENDICULAR"


_VECTOR_PROFILES_V1: Mapping[VectorProfileV1, Tuple[Tuple[int, int], ...]] = {
    VectorProfileV1.ORTHOGONAL_4: (
        (-1, 0),
        (0, -1),
        (0, 1),
        (1, 0),
    ),
    VectorProfileV1.KING_8: (
        (-1, -1),
        (-1, 0),
        (-1, 1),
        (0, -1),
        (0, 1),
        (1, -1),
        (1, 0),
        (1, 1),
    ),
}


@dataclass(frozen=True)
class _FamilySpecV1:
    family_id: str
    action_a: ActionPrimitive
    goal_a: GoalPrimitive
    action_b: ActionPrimitive
    goal_b: GoalPrimitive
    goal_frames: Tuple[GoalFrameV1, ...]


_FAMILY_SPECS_V1 = (
    _FamilySpecV1(
        family_id="push-hop-race-v1",
        action_a=ActionPrimitive.PUSH,
        goal_a=GoalPrimitive.REACH_EDGE,
        action_b=ActionPrimitive.HOP,
        goal_b=GoalPrimitive.REACH_EDGE,
        goal_frames=(
            GoalFrameV1.REACH_REACH_SAME,
            GoalFrameV1.REACH_REACH_OPPOSITE,
            GoalFrameV1.REACH_REACH_ADJACENT,
        ),
    ),
    _FamilySpecV1(
        family_id="swap-hop-network-v1",
        action_a=ActionPrimitive.SWAP,
        goal_a=GoalPrimitive.CONNECT_EDGES,
        action_b=ActionPrimitive.HOP,
        goal_b=GoalPrimitive.REACH_EDGE,
        goal_frames=(
            GoalFrameV1.CONNECT_REACH_ALIGNED,
            GoalFrameV1.CONNECT_REACH_PERPENDICULAR,
        ),
    ),
    _FamilySpecV1(
        family_id="convert-push-front-v1",
        action_a=ActionPrimitive.CONVERT,
        goal_a=GoalPrimitive.CONNECT_EDGES,
        action_b=ActionPrimitive.PUSH,
        goal_b=GoalPrimitive.REACH_EDGE,
        goal_frames=(
            GoalFrameV1.CONNECT_REACH_ALIGNED,
            GoalFrameV1.CONNECT_REACH_PERPENDICULAR,
        ),
    ),
    _FamilySpecV1(
        family_id="capture-hop-hunt-v1",
        action_a=ActionPrimitive.MOVE_CAPTURE,
        goal_a=GoalPrimitive.ELIMINATE,
        action_b=ActionPrimitive.HOP,
        goal_b=GoalPrimitive.REACH_EDGE,
        goal_frames=(GoalFrameV1.ELIMINATE_REACH,),
    ),
    _FamilySpecV1(
        family_id="convert-capture-duel-v1",
        action_a=ActionPrimitive.CONVERT,
        goal_a=GoalPrimitive.ELIMINATE,
        action_b=ActionPrimitive.MOVE_CAPTURE,
        goal_b=GoalPrimitive.ELIMINATE,
        goal_frames=(GoalFrameV1.ELIMINATE_ELIMINATE,),
    ),
    _FamilySpecV1(
        family_id="push-swap-networks-v1",
        action_a=ActionPrimitive.PUSH,
        goal_a=GoalPrimitive.CONNECT_EDGES,
        action_b=ActionPrimitive.SWAP,
        goal_b=GoalPrimitive.CONNECT_EDGES,
        goal_frames=(
            GoalFrameV1.CONNECT_CONNECT_SAME_AXIS,
            GoalFrameV1.CONNECT_CONNECT_PERPENDICULAR,
        ),
    ),
)

_FAMILY_SPEC_BY_ID_V1 = {spec.family_id: spec for spec in _FAMILY_SPECS_V1}
if len(_FAMILY_SPEC_BY_ID_V1) != len(_FAMILY_SPECS_V1):
    raise AssertionError("provisional family IDs must be unique")


def _setup_arrangement_count(a_count: int, b_count: int) -> int:
    cells = PROVISIONAL_BOARD_SIZE_V1**2
    return math.comb(cells, a_count) * math.comb(cells - a_count, b_count)


_SETUP_ARRANGEMENT_COUNTS_V1 = tuple(
    _setup_arrangement_count(a_count, b_count)
    for a_count, b_count in _SETUP_COUNT_PAIRS_V1
)
PROVISIONAL_SETUP_ARRANGEMENT_COUNT_V1 = sum(
    _SETUP_ARRANGEMENT_COUNTS_V1
)
PROVISIONAL_GOAL_FRAME_COUNT_V1 = sum(
    len(spec.goal_frames) for spec in _FAMILY_SPECS_V1
)
PROVISIONAL_ORDERED_VECTOR_PROFILE_PAIR_COUNT_V1 = len(VectorProfileV1) ** 2
PROVISIONAL_RAW_CASE_INPUT_COUNT_V1 = (
    PROVISIONAL_SETUP_ARRANGEMENT_COUNT_V1
    * PROVISIONAL_GOAL_FRAME_COUNT_V1
    * PROVISIONAL_ORDERED_VECTOR_PROFILE_PAIR_COUNT_V1
    * len(_FIRST_PLAYERS_V1)
)
if _SETUP_ARRANGEMENT_COUNTS_V1 != (756, 1_680):
    raise AssertionError("provisional setup combinatorics drifted")
if PROVISIONAL_SETUP_ARRANGEMENT_COUNT_V1 != 2_436:
    raise AssertionError("provisional setup supply drifted")
if PROVISIONAL_GOAL_FRAME_COUNT_V1 != 11:
    raise AssertionError("provisional goal-frame quotient drifted")
if PROVISIONAL_RAW_CASE_INPUT_COUNT_V1 != 214_368:
    raise AssertionError("provisional raw input combinatorics drifted")

# Public names describe the capability rather than prematurely declaring this
# provisional domain to be a final registry or search envelope.
FEASIBILITY_DOMAIN_VERSION = PROVISIONAL_DOMAIN_VERSION_V1
FEASIBILITY_INPUT_VERSION = PROVISIONAL_CASE_INPUT_VERSION_V1
FEASIBILITY_INPUT_COUNT_V1 = PROVISIONAL_RAW_CASE_INPUT_COUNT_V1


def _family_spec(family_id: Any) -> _FamilySpecV1:
    if type(family_id) is not str:
        raise TypeError("family_id must be a string")
    try:
        return _FAMILY_SPEC_BY_ID_V1[family_id]
    except KeyError as error:
        raise ValueError(
            "family_id must be one of {}".format(
                [spec.family_id for spec in _FAMILY_SPECS_V1]
            )
        ) from error


def provisional_family_signature_v1(family_id: str) -> FamilySignature:
    """Return one normalized nonretired provisional family signature."""

    spec = _family_spec(family_id)
    signature = FamilySignature(
        signature_version=1,
        state_kernel=StateKernel.OCCUPANCY,
        role_a=RoleSignature(spec.action_a, spec.goal_a),
        role_b=RoleSignature(spec.action_b, spec.goal_b),
        terminal_contract=(
            TerminalContract.ANY_GOAL_ACTION_ACTOR_INITIAL_FIRST_PRIORITY_PLY_CAP_STUCK_LOSS_V1
        ),
        turn_structure=TurnStructure.ALTERNATING_SINGLE_ACTION,
    )
    return validate_nonretired_family_signature(signature)


def _require_exact_fields(value: Any, expected: Iterable[str], label: str) -> Dict[str, Any]:
    if type(value) is not dict:
        raise TypeError("{} must be an exact object".format(label))
    if any(type(key) is not str for key in value):
        raise TypeError("{} keys must be strings".format(label))
    expected_set = set(expected)
    if len(value) > len(expected_set) + 32:
        raise ValueError("{} has too many fields".format(label))
    actual = set(value)
    if actual != expected_set:
        missing = sorted(expected_set - actual)
        unknown = sorted(actual - expected_set)
        parts = []
        if missing:
            parts.append("missing {}".format(missing))
        if unknown:
            parts.append("unknown {}".format(unknown))
        raise ValueError("{} has {}".format(label, ", ".join(parts)))
    return value


def _exact_int(value: Any, expected: Optional[int], label: str) -> int:
    if type(value) is not int:
        raise TypeError("{} must be an integer".format(label))
    if expected is not None and value != expected:
        raise ValueError("{} must equal {}".format(label, expected))
    return value


def _exact_enum(enum_type: Any, value: Any, label: str) -> Any:
    if type(value) is not str:
        raise TypeError("{} must be a string".format(label))
    try:
        return enum_type(value)
    except ValueError as error:
        raise ValueError(
            "{} must be one of {}".format(
                label, [member.value for member in enum_type]
            )
        ) from error


def _parse_positions(value: Any, label: str) -> Tuple[Tuple[int, int], ...]:
    if type(value) is not list:
        raise TypeError("{} must be an array".format(label))
    if len(value) not in (2, 3):
        raise ValueError("{} must contain two or three positions".format(label))
    positions = []
    for index, raw in enumerate(value):
        path = "{}[{}]".format(label, index)
        if (
            type(raw) is not list
            or len(raw) != 2
            or any(type(coordinate) is not int for coordinate in raw)
        ):
            raise TypeError("{} must be a two-integer array".format(path))
        position = (raw[0], raw[1])
        if position not in _BOARD_CELLS_V1:
            raise ValueError("{} is outside the 3x3 board".format(path))
        positions.append(position)
    result = tuple(positions)
    if len(set(result)) != len(result):
        raise ValueError("{} cannot contain duplicate positions".format(label))
    if result != tuple(sorted(result)):
        raise ValueError("{} must be canonically sorted".format(label))
    return result


@dataclass(frozen=True)
class FeasibilityInputV1:
    """One immutable member of the exact provisional feasibility domain."""

    case_input_version: int
    dsl_schema_version: int
    family_id: str
    board_size: int
    first_player: Player
    max_plies: int
    a_vector_profile: VectorProfileV1
    b_vector_profile: VectorProfileV1
    goal_frame: GoalFrameV1
    a_positions: Tuple[Tuple[int, int], ...]
    b_positions: Tuple[Tuple[int, int], ...]

    def __post_init__(self) -> None:
        _validate_case_input_fields(self)

    def to_dict(self) -> Dict[str, Any]:
        _validate_case_input_fields(self)
        return {
            "case_input_version": self.case_input_version,
            "dsl_schema_version": self.dsl_schema_version,
            "family_id": self.family_id,
            "board_size": self.board_size,
            "first_player": self.first_player.value,
            "max_plies": self.max_plies,
            "vector_profiles": {
                "A": self.a_vector_profile.value,
                "B": self.b_vector_profile.value,
            },
            "goal_frame": self.goal_frame.value,
            "initial_positions": {
                "A": [list(position) for position in self.a_positions],
                "B": [list(position) for position in self.b_positions],
            },
        }


def _validate_case_input_fields(value: Any) -> None:
    if type(value) is not FeasibilityInputV1:
        raise TypeError("case input must be an exact FeasibilityInputV1")
    try:
        fields = vars(value)
    except TypeError as error:
        raise TypeError("case input fields are unavailable") from error
    expected = {
        "case_input_version",
        "dsl_schema_version",
        "family_id",
        "board_size",
        "first_player",
        "max_plies",
        "a_vector_profile",
        "b_vector_profile",
        "goal_frame",
        "a_positions",
        "b_positions",
    }
    if type(fields) is not dict or set(fields) != expected:
        raise ValueError("case input has noncanonical fields")
    _exact_int(value.case_input_version, PROVISIONAL_CASE_INPUT_VERSION_V1, "case input version")
    _exact_int(value.dsl_schema_version, PROVISIONAL_DSL_SCHEMA_VERSION_V1, "case DSL schema version")
    _exact_int(value.board_size, PROVISIONAL_BOARD_SIZE_V1, "case board_size")
    _exact_int(value.max_plies, PROVISIONAL_MAX_PLIES_V1, "case max_plies")
    spec = _family_spec(value.family_id)
    if type(value.first_player) is not Player:
        raise TypeError("case first_player must be a Player")
    if type(value.a_vector_profile) is not VectorProfileV1:
        raise TypeError("case A vector profile must be a VectorProfileV1")
    if type(value.b_vector_profile) is not VectorProfileV1:
        raise TypeError("case B vector profile must be a VectorProfileV1")
    if type(value.goal_frame) is not GoalFrameV1:
        raise TypeError("case goal frame must be a GoalFrameV1")
    if value.goal_frame not in spec.goal_frames:
        raise ValueError(
            "goal frame {} is not valid for {}".format(
                value.goal_frame.value, value.family_id
            )
        )
    for positions, label in (
        (value.a_positions, "case A positions"),
        (value.b_positions, "case B positions"),
    ):
        if (
            type(positions) is not tuple
            or any(
                type(position) is not tuple
                or len(position) != 2
                or any(type(coordinate) is not int for coordinate in position)
                for position in positions
            )
        ):
            raise TypeError("{} must be canonical position tuples".format(label))
        if positions != tuple(sorted(positions)):
            raise ValueError("{} must be canonically sorted".format(label))
        if len(set(positions)) != len(positions):
            raise ValueError("{} cannot contain duplicates".format(label))
        if any(position not in _BOARD_CELLS_V1 for position in positions):
            raise ValueError("{} contains an out-of-bounds position".format(label))
    counts = (len(value.a_positions), len(value.b_positions))
    if counts not in _SETUP_COUNT_PAIRS_V1:
        raise ValueError(
            "case setup counts must be one of {}".format(
                [list(pair) for pair in _SETUP_COUNT_PAIRS_V1]
            )
        )
    if set(value.a_positions) & set(value.b_positions):
        raise ValueError("case A and B positions must be disjoint")


_CASE_KEYS_V1 = (
    "case_input_version",
    "dsl_schema_version",
    "family_id",
    "board_size",
    "first_player",
    "max_plies",
    "vector_profiles",
    "goal_frame",
    "initial_positions",
)


def parse_provisional_case_input_v1(value: Any) -> FeasibilityInputV1:
    """Strictly parse one exact JSON-shaped provisional case input."""

    top = _require_exact_fields(value, _CASE_KEYS_V1, "case input")
    vectors = _require_exact_fields(
        top["vector_profiles"], ("A", "B"), "case vector_profiles"
    )
    positions = _require_exact_fields(
        top["initial_positions"], ("A", "B"), "case initial_positions"
    )
    return FeasibilityInputV1(
        case_input_version=_exact_int(
            top["case_input_version"],
            PROVISIONAL_CASE_INPUT_VERSION_V1,
            "case input version",
        ),
        dsl_schema_version=_exact_int(
            top["dsl_schema_version"],
            PROVISIONAL_DSL_SCHEMA_VERSION_V1,
            "case DSL schema version",
        ),
        family_id=top["family_id"],
        board_size=_exact_int(
            top["board_size"], PROVISIONAL_BOARD_SIZE_V1, "case board_size"
        ),
        first_player=_exact_enum(Player, top["first_player"], "case first_player"),
        max_plies=_exact_int(
            top["max_plies"], PROVISIONAL_MAX_PLIES_V1, "case max_plies"
        ),
        a_vector_profile=_exact_enum(
            VectorProfileV1, vectors["A"], "case A vector profile"
        ),
        b_vector_profile=_exact_enum(
            VectorProfileV1, vectors["B"], "case B vector profile"
        ),
        goal_frame=_exact_enum(
            GoalFrameV1, top["goal_frame"], "case goal frame"
        ),
        a_positions=_parse_positions(positions["A"], "case initial_positions.A"),
        b_positions=_parse_positions(positions["B"], "case initial_positions.B"),
    )


def _normalized_case_input(value: Any) -> FeasibilityInputV1:
    if type(value) is FeasibilityInputV1:
        try:
            return parse_provisional_case_input_v1(value.to_dict())
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("case input is not parser-normalized") from error
    if type(value) is dict:
        return parse_provisional_case_input_v1(value)
    raise TypeError("case input must be a FeasibilityInputV1 or exact object")


def canonical_provisional_case_input_json_v1(value: Any) -> str:
    case = _normalized_case_input(value)
    return json.dumps(
        case.to_dict(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def provisional_case_input_hash_v1(value: Any) -> str:
    canonical = canonical_provisional_case_input_json_v1(value).encode("utf-8")
    return hashlib.sha256(_CASE_INPUT_HASH_DOMAIN_V1 + canonical).hexdigest()


def enumerate_provisional_case_inputs_v1() -> Iterator[FeasibilityInputV1]:
    """Yield all 214,368 inputs once in the declared deterministic order."""

    emitted = 0
    for spec in _FAMILY_SPECS_V1:
        for goal_frame in spec.goal_frames:
            for a_count, b_count in _SETUP_COUNT_PAIRS_V1:
                for a_positions in combinations(_BOARD_CELLS_V1, a_count):
                    remaining = tuple(
                        position
                        for position in _BOARD_CELLS_V1
                        if position not in a_positions
                    )
                    for b_positions in combinations(remaining, b_count):
                        for a_profile in VectorProfileV1:
                            for b_profile in VectorProfileV1:
                                for first_player in _FIRST_PLAYERS_V1:
                                    emitted += 1
                                    yield FeasibilityInputV1(
                                        case_input_version=PROVISIONAL_CASE_INPUT_VERSION_V1,
                                        dsl_schema_version=PROVISIONAL_DSL_SCHEMA_VERSION_V1,
                                        family_id=spec.family_id,
                                        board_size=PROVISIONAL_BOARD_SIZE_V1,
                                        first_player=first_player,
                                        max_plies=PROVISIONAL_MAX_PLIES_V1,
                                        a_vector_profile=a_profile,
                                        b_vector_profile=b_profile,
                                        goal_frame=goal_frame,
                                        a_positions=tuple(a_positions),
                                        b_positions=tuple(b_positions),
                                    )
    if emitted != PROVISIONAL_RAW_CASE_INPUT_COUNT_V1:
        raise AssertionError(
            "provisional enumeration emitted {} inputs, expected {}".format(
                emitted, PROVISIONAL_RAW_CASE_INPUT_COUNT_V1
            )
        )


def _goal_dicts(frame: GoalFrameV1) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    if frame is GoalFrameV1.REACH_REACH_SAME:
        return (
            {"kind": "REACH_EDGE", "piece": "a", "edge": "TOP"},
            {"kind": "REACH_EDGE", "piece": "b", "edge": "TOP"},
        )
    if frame is GoalFrameV1.REACH_REACH_OPPOSITE:
        return (
            {"kind": "REACH_EDGE", "piece": "a", "edge": "TOP"},
            {"kind": "REACH_EDGE", "piece": "b", "edge": "BOTTOM"},
        )
    if frame is GoalFrameV1.REACH_REACH_ADJACENT:
        return (
            {"kind": "REACH_EDGE", "piece": "a", "edge": "TOP"},
            {"kind": "REACH_EDGE", "piece": "b", "edge": "RIGHT"},
        )
    if frame is GoalFrameV1.CONNECT_REACH_ALIGNED:
        return (
            {
                "kind": "CONNECT_EDGES",
                "piece": "a",
                "edges": ["BOTTOM", "TOP"],
            },
            {"kind": "REACH_EDGE", "piece": "b", "edge": "TOP"},
        )
    if frame is GoalFrameV1.CONNECT_REACH_PERPENDICULAR:
        return (
            {
                "kind": "CONNECT_EDGES",
                "piece": "a",
                "edges": ["BOTTOM", "TOP"],
            },
            {"kind": "REACH_EDGE", "piece": "b", "edge": "RIGHT"},
        )
    if frame is GoalFrameV1.ELIMINATE_REACH:
        return (
            {"kind": "ELIMINATE", "piece": "b"},
            {"kind": "REACH_EDGE", "piece": "b", "edge": "TOP"},
        )
    if frame is GoalFrameV1.ELIMINATE_ELIMINATE:
        return (
            {"kind": "ELIMINATE", "piece": "b"},
            {"kind": "ELIMINATE", "piece": "a"},
        )
    if frame is GoalFrameV1.CONNECT_CONNECT_SAME_AXIS:
        return (
            {
                "kind": "CONNECT_EDGES",
                "piece": "a",
                "edges": ["BOTTOM", "TOP"],
            },
            {
                "kind": "CONNECT_EDGES",
                "piece": "b",
                "edges": ["BOTTOM", "TOP"],
            },
        )
    if frame is GoalFrameV1.CONNECT_CONNECT_PERPENDICULAR:
        return (
            {
                "kind": "CONNECT_EDGES",
                "piece": "a",
                "edges": ["BOTTOM", "TOP"],
            },
            {
                "kind": "CONNECT_EDGES",
                "piece": "b",
                "edges": ["LEFT", "RIGHT"],
            },
        )
    raise AssertionError("closed goal-frame vocabulary was not handled")


_ACTION_TO_DSL_V1: Mapping[ActionPrimitive, ActionKind] = {
    ActionPrimitive.MOVE_CAPTURE: ActionKind.MOVE_CAPTURE,
    ActionPrimitive.PUSH: ActionKind.PUSH,
    ActionPrimitive.SWAP: ActionKind.SWAP,
    ActionPrimitive.HOP: ActionKind.HOP,
    ActionPrimitive.CONVERT: ActionKind.CONVERT,
}
_DSL_TO_ACTION_V1: Mapping[ActionKind, ActionPrimitive] = {
    ActionKind.PLACE: ActionPrimitive.PLACE,
    ActionKind.MOVE: ActionPrimitive.MOVE,
    ActionKind.MOVE_CAPTURE: ActionPrimitive.MOVE_CAPTURE,
    ActionKind.PUSH: ActionPrimitive.PUSH,
    ActionKind.SWAP: ActionPrimitive.SWAP,
    ActionKind.HOP: ActionPrimitive.HOP,
    ActionKind.CONVERT: ActionPrimitive.CONVERT,
}
_DSL_TO_GOAL_V1: Mapping[GoalKind, GoalPrimitive] = {
    GoalKind.CONNECT_EDGES: GoalPrimitive.CONNECT_EDGES,
    GoalKind.REACH_EDGE: GoalPrimitive.REACH_EDGE,
    GoalKind.ELIMINATE: GoalPrimitive.ELIMINATE,
}


def _action_dict(
    primitive: ActionPrimitive,
    piece: str,
    profile: VectorProfileV1,
) -> Dict[str, Any]:
    try:
        kind = _ACTION_TO_DSL_V1[primitive]
    except KeyError as error:
        raise ValueError(
            "provisional compiler cannot emit action primitive {}".format(
                primitive.value
            )
        ) from error
    return {
        "kind": kind.value,
        "piece": piece,
        "vectors": [list(vector) for vector in _VECTOR_PROFILES_V1[profile]],
    }


def _normalized_definition(value: Any) -> GameDefinition:
    if type(value) is GameDefinition:
        try:
            return parse_definition(json.loads(canonical_json(value)))
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("definition is not parser-normalized") from error
    if type(value) is dict:
        _validate_json_tree(value, "definition")
        return parse_definition(_json_copy(value, "definition"))
    raise TypeError("definition must be a GameDefinition or exact object")


def project_family_signature_v1(definition_value: Any) -> FamilySignature:
    """Project an authoritative schema-v4 definition back to family identity."""

    definition = _normalized_definition(definition_value)
    if definition.schema_version != PROVISIONAL_DSL_SCHEMA_VERSION_V1:
        raise ValueError("family projection requires a schema-v4 definition")
    if definition.terminal_policy is not None:
        raise ValueError("schema-v4 family projection cannot contain terminal_policy")
    role_a = definition.role(Player.A)
    role_b = definition.role(Player.B)
    try:
        action_a = _DSL_TO_ACTION_V1[role_a.action.kind]
        action_b = _DSL_TO_ACTION_V1[role_b.action.kind]
        goal_a = _DSL_TO_GOAL_V1[role_a.goal.kind]
        goal_b = _DSL_TO_GOAL_V1[role_b.goal.kind]
    except KeyError as error:
        raise ValueError("definition uses a ludeme outside family-signature v1") from error
    return validate_nonretired_family_signature(
        FamilySignature(
            signature_version=1,
            state_kernel=StateKernel.OCCUPANCY,
            role_a=RoleSignature(action_a, goal_a),
            role_b=RoleSignature(action_b, goal_b),
            terminal_contract=(
                TerminalContract.ANY_GOAL_ACTION_ACTOR_INITIAL_FIRST_PRIORITY_PLY_CAP_STUCK_LOSS_V1
            ),
            turn_structure=TurnStructure.ALTERNATING_SINGLE_ACTION,
        )
    )


def compile_provisional_case_v1(case_value: Any) -> GameDefinition:
    """Compile one domain member into a strict schema-v4 definition."""

    case = _normalized_case_input(case_value)
    spec = _family_spec(case.family_id)
    signature = provisional_family_signature_v1(case.family_id)
    signature = validate_nonretired_family_signature(signature)
    goal_a, goal_b = _goal_dicts(case.goal_frame)
    case_hash = provisional_case_input_hash_v1(case)
    definition = parse_definition(
        {
            "schema_version": PROVISIONAL_DSL_SCHEMA_VERSION_V1,
            "name": "pf12-{}-{}".format(case.family_id, case_hash[:20]),
            "board_size": PROVISIONAL_BOARD_SIZE_V1,
            "first_player": case.first_player.value,
            "max_plies": PROVISIONAL_MAX_PLIES_V1,
            "roles": {
                "A": {
                    "action": _action_dict(
                        spec.action_a, "a", case.a_vector_profile
                    ),
                    "goal": goal_a,
                },
                "B": {
                    "action": _action_dict(
                        spec.action_b, "b", case.b_vector_profile
                    ),
                    "goal": goal_b,
                },
            },
            "initial_pieces": [
                *(
                    {"owner": "A", "piece": "a", "position": list(position)}
                    for position in case.a_positions
                ),
                *(
                    {"owner": "B", "piece": "b", "position": list(position)}
                    for position in case.b_positions
                ),
            ],
        }
    )
    projected = project_family_signature_v1(definition)
    if canonical_family_signature_json(projected) != canonical_family_signature_json(
        signature
    ):
        raise AssertionError("compiled definition does not project to its family")
    return definition


_STATE_BOUND_CLASS_BY_FAMILY_V1 = {
    "push-hop-race-v1": "FIXED_COUNTS",
    "swap-hop-network-v1": "FIXED_COUNTS",
    "convert-push-front-v1": "A_CONVERTS_B_COUNTS",
    "capture-hop-hunt-v1": "A_CAPTURES_B_COUNTS",
    "convert-capture-duel-v1": "A_CONVERTS_B_B_CAPTURES_A_COUNTS",
    "push-swap-networks-v1": "FIXED_COUNTS",
}
_EXPECTED_STRUCTURAL_STATE_BOUNDS_V1 = {
    "FIXED_COUNTS": {2: 14_364, 3: 31_920},
    "A_CONVERTS_B_COUNTS": {2: 26_334, 3: 67_032},
    "A_CAPTURES_B_COUNTS": {2: 19_836, 3: 67_032},
    "A_CONVERTS_B_B_CAPTURES_A_COUNTS": {2: 40_603, 3: 181_051},
}


def _owner_count_classes(
    bound_class: str, per_role_initial_count: int
) -> Tuple[Tuple[int, int], ...]:
    count = per_role_initial_count
    if bound_class == "FIXED_COUNTS":
        return ((count, count),)
    if bound_class == "A_CONVERTS_B_COUNTS":
        return tuple((a_count, 2 * count - a_count) for a_count in range(count, 2 * count + 1))
    if bound_class == "A_CAPTURES_B_COUNTS":
        return tuple((count, b_count) for b_count in range(count + 1))
    if bound_class == "A_CONVERTS_B_B_CAPTURES_A_COUNTS":
        return tuple(
            (a_count, b_count)
            for b_count in range(count + 1)
            for a_count in range(2 * count - b_count + 1)
        )
    raise AssertionError("closed state-bound class was not handled")


def build_provisional_state_work_proof_v1(case_value: Any) -> Dict[str, Any]:
    """Return a conservative, transition-free structural bound for one case.

    All six provisional cells lack PLACE.  PUSH, SWAP, and HOP preserve labels;
    MOVE_CAPTURE may only remove a piece; and CONVERT can only produce the
    already-declared owner-aligned labels ``A/a`` or ``B/b``.  Consequently no
    reachable board has more occupied cells than the initial setup or a label
    outside that two-label universe.  The proof intentionally counts many
    unreachable boards.
    """

    case = _normalized_case_input(case_value)
    compile_provisional_case_v1(case)
    board_cells = PROVISIONAL_BOARD_SIZE_V1**2
    per_role_initial_count = len(case.a_positions)
    initial_count = per_role_initial_count * 2
    bound_class = _STATE_BOUND_CLASS_BY_FAMILY_V1[case.family_id]
    owner_count_classes = _owner_count_classes(
        bound_class, per_role_initial_count
    )
    occupancy_layers = []
    for a_count, b_count in owner_count_classes:
        position_assignments = math.comb(board_cells, a_count) * math.comb(
            board_cells - a_count, b_count
        )
        occupancy_layers.append(
            {
                "A_count": a_count,
                "B_count": b_count,
                "occupied_count": a_count + b_count,
                "board_configuration_upper_bound": position_assignments,
            }
        )
    board_bound = sum(
        layer["board_configuration_upper_bound"] for layer in occupancy_layers
    )
    ply_layer_count = case.max_plies + 1
    state_bound = board_bound * ply_layer_count
    role_vector_counts = {
        "A": len(_VECTOR_PROFILES_V1[case.a_vector_profile]),
        "B": len(_VECTOR_PROFILES_V1[case.b_vector_profile]),
    }
    maximum_role_actor_counts = {
        "A": (
            2 * per_role_initial_count
            if bound_class
            in (
                "A_CONVERTS_B_COUNTS",
                "A_CONVERTS_B_B_CAPTURES_A_COUNTS",
            )
            else per_role_initial_count
        ),
        "B": per_role_initial_count,
    }
    role_candidate_bounds = {
        player: maximum_role_actor_counts[player] * vector_count
        for player, vector_count in role_vector_counts.items()
    }
    max_candidates = max(role_candidate_bounds.values())
    expected_state_bound = _EXPECTED_STRUCTURAL_STATE_BOUNDS_V1[bound_class][
        per_role_initial_count
    ]
    if state_bound != expected_state_bound:
        raise AssertionError("provisional structural state bound drifted")
    return {
        "proof_version": PROVISIONAL_STATE_WORK_PROOF_VERSION_V1,
        "state_bound_class": bound_class,
        "board_cells": board_cells,
        "per_role_initial_piece_count": per_role_initial_count,
        "initial_occupied_count": initial_count,
        "maximum_occupied_count": initial_count,
        "reachable_owner_kind_labels": [
            {"owner": "A", "piece": "a"},
            {"owner": "B", "piece": "b"},
        ],
        "occupancy_layer_bounds": occupancy_layers,
        "board_configuration_upper_bound": board_bound,
        "ply_layer_count": ply_layer_count,
        "to_move_multiplier": 1,
        "structural_state_upper_bound": state_bound,
        "role_vector_counts": role_vector_counts,
        "maximum_role_actor_counts": maximum_role_actor_counts,
        "role_action_candidate_upper_bounds": role_candidate_bounds,
        "max_action_candidates_per_state": max_candidates,
        "state_action_candidate_evaluation_upper_bound": state_bound
        * max_candidates,
    }


def _domain_descriptor() -> Dict[str, Any]:
    setup_records = []
    for pair, count in zip(
        _SETUP_COUNT_PAIRS_V1, _SETUP_ARRANGEMENT_COUNTS_V1
    ):
        setup_records.append(
            {
                "A_count": pair[0],
                "B_count": pair[1],
                "disjoint_arrangement_count": count,
            }
        )
    families = []
    for spec in _FAMILY_SPECS_V1:
        signature = provisional_family_signature_v1(spec.family_id)
        families.append(
            {
                "family_id": spec.family_id,
                "signature": signature.to_dict(),
                "family_signature_hash": family_signature_hash(signature),
                "goal_frames": [frame.value for frame in spec.goal_frames],
            }
        )
    return {
        "domain_id": FEASIBILITY_DOMAIN_ID,
        "domain_version": PROVISIONAL_DOMAIN_VERSION_V1,
        "status": "PROVISIONAL_NOT_A_REGISTRY_OR_SEARCH_ENVELOPE",
        "input_version": FEASIBILITY_INPUT_VERSION,
        "derivation_witness_version": (
            PROVISIONAL_DERIVATION_WITNESS_VERSION_V1
        ),
        "state_work_proof_version": PROVISIONAL_STATE_WORK_PROOF_VERSION_V1,
        "enumerator": {
            "enumerator_id": FEASIBILITY_ENUMERATOR_ID,
            "enumerator_version": FEASIBILITY_ENUMERATOR_VERSION,
        },
        "compiler": {
            "compiler_id": FEASIBILITY_COMPILER_ID,
            "compiler_version": FEASIBILITY_COMPILER_VERSION,
        },
        "d4_canonicalization": {
            "canonicalization_id": FEASIBILITY_D4_CANONICALIZATION_ID,
            "canonicalization_version": FEASIBILITY_D4_CANONICALIZATION_VERSION,
        },
        "dsl_schema_version": PROVISIONAL_DSL_SCHEMA_VERSION_V1,
        "board_size": PROVISIONAL_BOARD_SIZE_V1,
        "max_plies": [PROVISIONAL_MAX_PLIES_V1],
        "max_plies_rule": "TWO_TIMES_BOARD_CELLS_V1",
        "first_players": [player.value for player in _FIRST_PLAYERS_V1],
        "piece_kinds": {"A": "a", "B": "b"},
        "setup_rule": "BALANCED_DISJOINT_UNORDERED_CANONICAL_POSITIONS",
        "position_order": "ROW_MAJOR",
        "setup_count_pairs": setup_records,
        "vector_profile_order": [profile.value for profile in VectorProfileV1],
        "vector_profiles": {
            profile.value: [list(vector) for vector in _VECTOR_PROFILES_V1[profile]]
            for profile in VectorProfileV1
        },
        "vector_profile_assignment": "ORDERED_INDEPENDENT_A_B",
        "goal_frame_definitions": {
            frame.value: {
                "A": _goal_dicts(frame)[0],
                "B": _goal_dicts(frame)[1],
            }
            for frame in GoalFrameV1
        },
        "families": families,
        "enumeration_order": [
            "family",
            "goal_frame",
            "setup_count_pair",
            "A_positions",
            "B_positions",
            "A_vector_profile",
            "B_vector_profile",
            "first_player",
        ],
        "combinatorics": {
            "board_cell_count": PROVISIONAL_BOARD_SIZE_V1**2,
            "setup_arrangement_count": PROVISIONAL_SETUP_ARRANGEMENT_COUNT_V1,
            "goal_frame_count": PROVISIONAL_GOAL_FRAME_COUNT_V1,
            "ordered_vector_profile_pair_count": (
                PROVISIONAL_ORDERED_VECTOR_PROFILE_PAIR_COUNT_V1
            ),
            "first_player_count": len(_FIRST_PLAYERS_V1),
            "raw_case_input_count": PROVISIONAL_RAW_CASE_INPUT_COUNT_V1,
        },
    }


def _validate_json_tree(value: Any, label: str) -> None:
    nodes = 0
    active = set()

    def visit(item: Any, depth: int) -> None:
        nonlocal nodes
        nodes += 1
        if nodes > PROVISIONAL_MAX_JSON_NODES_V1:
            raise ValueError("{} exceeds the JSON node cap".format(label))
        if depth > PROVISIONAL_MAX_JSON_DEPTH_V1:
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


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _json_copy(value: Any, label: str) -> Any:
    _validate_json_tree(value, label)
    return json.loads(_canonical_bytes(value))


def build_provisional_domain_descriptor_v1() -> Dict[str, Any]:
    """Return the detached descriptor of the exact provisional finite domain."""

    descriptor = _domain_descriptor()
    if (
        descriptor["combinatorics"]["raw_case_input_count"]
        != sum(
            math.comb(PROVISIONAL_BOARD_SIZE_V1**2, a_count)
            * math.comb(PROVISIONAL_BOARD_SIZE_V1**2 - a_count, b_count)
            for a_count, b_count in _SETUP_COUNT_PAIRS_V1
        )
        * sum(len(spec.goal_frames) for spec in _FAMILY_SPECS_V1)
        * (len(VectorProfileV1) ** 2)
        * len(_FIRST_PLAYERS_V1)
    ):
        raise AssertionError("domain descriptor raw count is not reconstructable")
    return _json_copy(descriptor, "provisional domain descriptor")


def validate_provisional_domain_descriptor_v1(value: Any) -> Dict[str, Any]:
    """Rebuild the fixed descriptor and reject any stored-field drift."""

    if type(value) is not dict:
        raise TypeError("provisional domain descriptor must be an exact object")
    _validate_json_tree(value, "provisional domain descriptor")
    entry = _canonical_bytes(value)
    expected = build_provisional_domain_descriptor_v1()
    if entry != _canonical_bytes(expected):
        raise ValueError("provisional domain descriptor does not reconstruct")
    if entry != _canonical_bytes(value):
        raise ValueError("provisional domain descriptor changed during validation")
    return _json_copy(expected, "validated provisional domain descriptor")


def canonical_provisional_domain_json_v1() -> str:
    return _canonical_bytes(build_provisional_domain_descriptor_v1()).decode("utf-8")


def provisional_domain_hash_v1() -> str:
    canonical = canonical_provisional_domain_json_v1().encode("utf-8")
    return hashlib.sha256(_DOMAIN_HASH_DOMAIN_V1 + canonical).hexdigest()


_WITNESS_KEYS_V1 = (
    "witness_version",
    "domain_hash",
    "compiler_id",
    "compiler_version",
    "case_input",
    "case_input_hash",
    "family_signature",
    "family_signature_hash",
    "definition",
    "definition_hash",
    "d4_canonical_hash",
    "state_work_proof",
    "witness_digest",
)


def build_provisional_derivation_witness_v1(case_value: Any) -> Dict[str, Any]:
    """Bind one input to its family, definition, D4 identity, and work proof."""

    case = _normalized_case_input(case_value)
    signature = provisional_family_signature_v1(case.family_id)
    definition = compile_provisional_case_v1(case)
    payload = {
        "witness_version": PROVISIONAL_DERIVATION_WITNESS_VERSION_V1,
        "domain_hash": provisional_domain_hash_v1(),
        "compiler_id": FEASIBILITY_COMPILER_ID,
        "compiler_version": FEASIBILITY_COMPILER_VERSION,
        "case_input": case.to_dict(),
        "case_input_hash": provisional_case_input_hash_v1(case),
        "family_signature": signature.to_dict(),
        "family_signature_hash": family_signature_hash(signature),
        "definition": definition.to_dict(),
        "definition_hash": definition_hash(definition),
        "d4_canonical_hash": d4_canonical_hash(definition),
        "state_work_proof": build_provisional_state_work_proof_v1(case),
    }
    digest = hashlib.sha256(
        _WITNESS_HASH_DOMAIN_V1 + _canonical_bytes(payload)
    ).hexdigest()
    witness = dict(payload)
    witness["witness_digest"] = digest
    return _json_copy(witness, "provisional derivation witness")


def validate_provisional_derivation_witness_v1(value: Any) -> Dict[str, Any]:
    """Rebuild a stored witness solely from its strict retained case input."""

    top = _require_exact_fields(
        value, _WITNESS_KEYS_V1, "provisional derivation witness"
    )
    _validate_json_tree(top, "provisional derivation witness")
    entry = _canonical_bytes(top)
    _exact_int(
        top["witness_version"],
        PROVISIONAL_DERIVATION_WITNESS_VERSION_V1,
        "derivation witness version",
    )
    case = parse_provisional_case_input_v1(top["case_input"])
    expected = build_provisional_derivation_witness_v1(case)
    if entry != _canonical_bytes(expected):
        raise ValueError("provisional derivation witness does not reconstruct")
    if entry != _canonical_bytes(top):
        raise ValueError("provisional derivation witness changed during validation")
    return _json_copy(expected, "validated provisional derivation witness")


# The Plan-0012 public API uses concise feasibility names.  The implementation
# names above retain "provisional" where it helps prevent scientific
# over-interpretation; these aliases and wrappers are behaviorally identical.
# Compatibility name retained only inside this new, not-yet-frozen slice.
ProvisionalCaseInputV1 = FeasibilityInputV1


def build_feasibility_domain_v1() -> Dict[str, Any]:
    return build_provisional_domain_descriptor_v1()


def feasibility_domain_hash_v1() -> str:
    return provisional_domain_hash_v1()


def parse_feasibility_input_v1(value: Any) -> FeasibilityInputV1:
    return parse_provisional_case_input_v1(value)


def enumerate_feasibility_inputs_v1() -> Iterator[FeasibilityInputV1]:
    yield from enumerate_provisional_case_inputs_v1()


def compile_feasibility_definition_v1(case_value: Any) -> GameDefinition:
    return compile_provisional_case_v1(case_value)


def project_definition_family_signature_v1(
    definition_value: Any,
) -> FamilySignature:
    return project_family_signature_v1(definition_value)


def build_derivation_witness_v1(case_value: Any) -> Dict[str, Any]:
    return build_provisional_derivation_witness_v1(case_value)


def validate_derivation_witness_v1(value: Any) -> Dict[str, Any]:
    return validate_provisional_derivation_witness_v1(value)


def build_state_work_proof_v1(case_value: Any) -> Dict[str, Any]:
    return build_provisional_state_work_proof_v1(case_value)


def validate_state_work_proof_v1(
    value: Any, case_value: Any
) -> Dict[str, Any]:
    """Rebuild a stored proof from its authoritative case input."""

    if type(value) is not dict:
        raise TypeError("state/work proof must be an exact object")
    _validate_json_tree(value, "state/work proof")
    entry = _canonical_bytes(value)
    expected = build_provisional_state_work_proof_v1(case_value)
    if entry != _canonical_bytes(expected):
        raise ValueError("state/work proof does not reconstruct")
    if entry != _canonical_bytes(value):
        raise ValueError("state/work proof changed during validation")
    return _json_copy(expected, "validated state/work proof")


__all__ = (
    "FEASIBILITY_COMPILER_ID",
    "FEASIBILITY_COMPILER_VERSION",
    "FEASIBILITY_D4_CANONICALIZATION_ID",
    "FEASIBILITY_D4_CANONICALIZATION_VERSION",
    "FEASIBILITY_DOMAIN_ID",
    "FEASIBILITY_DOMAIN_VERSION",
    "FEASIBILITY_ENUMERATOR_ID",
    "FEASIBILITY_ENUMERATOR_VERSION",
    "FEASIBILITY_INPUT_COUNT_V1",
    "FEASIBILITY_INPUT_VERSION",
    "FeasibilityInputV1",
    "PROVISIONAL_BOARD_SIZE_V1",
    "PROVISIONAL_CASE_INPUT_VERSION_V1",
    "PROVISIONAL_DERIVATION_WITNESS_VERSION_V1",
    "PROVISIONAL_DOMAIN_VERSION_V1",
    "PROVISIONAL_DSL_SCHEMA_VERSION_V1",
    "PROVISIONAL_GOAL_FRAME_COUNT_V1",
    "PROVISIONAL_MAX_PLIES_V1",
    "PROVISIONAL_ORDERED_VECTOR_PROFILE_PAIR_COUNT_V1",
    "PROVISIONAL_RAW_CASE_INPUT_COUNT_V1",
    "PROVISIONAL_SETUP_ARRANGEMENT_COUNT_V1",
    "PROVISIONAL_STATE_WORK_PROOF_VERSION_V1",
    "GoalFrameV1",
    "ProvisionalCaseInputV1",
    "VectorProfileV1",
    "build_provisional_derivation_witness_v1",
    "build_provisional_domain_descriptor_v1",
    "build_provisional_state_work_proof_v1",
    "canonical_provisional_case_input_json_v1",
    "canonical_provisional_domain_json_v1",
    "build_derivation_witness_v1",
    "build_feasibility_domain_v1",
    "build_state_work_proof_v1",
    "compile_feasibility_definition_v1",
    "compile_provisional_case_v1",
    "enumerate_provisional_case_inputs_v1",
    "enumerate_feasibility_inputs_v1",
    "feasibility_domain_hash_v1",
    "parse_feasibility_input_v1",
    "parse_provisional_case_input_v1",
    "project_family_signature_v1",
    "project_definition_family_signature_v1",
    "provisional_case_input_hash_v1",
    "provisional_domain_hash_v1",
    "provisional_family_signature_v1",
    "validate_provisional_derivation_witness_v1",
    "validate_provisional_domain_descriptor_v1",
    "validate_derivation_witness_v1",
    "validate_state_work_proof_v1",
)
