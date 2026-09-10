"""Pure typed grammar and spatial identities for the Plan-0015 universe.

This module closes the *descriptive* isotropic occupancy-v4 envelope.  It can
name role programs, spatial goal frames, invariant vector profiles, and their
D4-plus-role-swap identities.  It deliberately contains no setup compiler or
state-transition capability.

The finite vocabulary is mirrored here as a sealed descriptive boundary and
is differentially checked against the frozen family vocabulary in tests.  The
later compiler slice is the only place that may bridge these values into the
authoritative DSL.  This package therefore cannot acquire the legacy
``parity_forge`` package initializer, apply an action, inspect a terminal, or
observe a game result.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from itertools import product
from typing import Any, Dict, Iterable, List, Sequence, Tuple

TYPED_OCCUPANCY_UNIVERSE_VERSION = 1


class UniverseClosureError(ValueError):
    """The finite grammar failed to reproduce its registered closure."""


def _official_universe_version() -> int:
    """Return the code-literal version after checking the public binding."""

    if (
        type(TYPED_OCCUPANCY_UNIVERSE_VERSION) is not int
        or TYPED_OCCUPANCY_UNIVERSE_VERSION != 1
    ):
        raise UniverseClosureError("typed occupancy universe version binding changed")
    return 1


class ActionPrimitive(str, Enum):
    """The seven nonretired action names admitted by this closed universe."""

    PLACE = "PLACE"
    MOVE = "MOVE"
    MOVE_CAPTURE = "MOVE_CAPTURE"
    PUSH = "PUSH"
    SWAP = "SWAP"
    HOP = "HOP"
    CONVERT = "CONVERT"


class GoalPrimitive(str, Enum):
    """The three schema-v4 goal names admitted by this closed universe."""

    CONNECT_EDGES = "CONNECT_EDGES"
    REACH_EDGE = "REACH_EDGE"
    ELIMINATE = "ELIMINATE"


def _fixed_action_value(value: ActionPrimitive) -> str:
    if value is ActionPrimitive.PLACE:
        return "PLACE"
    if value is ActionPrimitive.MOVE:
        return "MOVE"
    if value is ActionPrimitive.MOVE_CAPTURE:
        return "MOVE_CAPTURE"
    if value is ActionPrimitive.PUSH:
        return "PUSH"
    if value is ActionPrimitive.SWAP:
        return "SWAP"
    if value is ActionPrimitive.HOP:
        return "HOP"
    if value is ActionPrimitive.CONVERT:
        return "CONVERT"
    raise TypeError("role action primitive must be an ActionPrimitive")


def _fixed_goal_value(value: GoalPrimitive) -> str:
    if value is GoalPrimitive.CONNECT_EDGES:
        return "CONNECT_EDGES"
    if value is GoalPrimitive.REACH_EDGE:
        return "REACH_EDGE"
    if value is GoalPrimitive.ELIMINATE:
        return "ELIMINATE"
    raise TypeError("role goal primitive must be a GoalPrimitive")


@dataclass(frozen=True, init=False)
class RoleSignature:
    """One descriptive action/goal atom, prior to DSL compilation."""

    action_primitive: ActionPrimitive
    goal_primitive: GoalPrimitive
    _construction_snapshot: Tuple[str, str]

    def __init__(
        self,
        action_primitive: ActionPrimitive,
        goal_primitive: GoalPrimitive,
    ) -> None:
        _require_exact_enum(
            action_primitive, ActionPrimitive, "role action primitive"
        )
        _require_exact_enum(
            goal_primitive, GoalPrimitive, "role goal primitive"
        )
        action_value = _fixed_action_value(action_primitive)
        goal_value = _fixed_goal_value(goal_primitive)
        if (
            goal_primitive is GoalPrimitive.ELIMINATE
            and action_primitive
            not in (ActionPrimitive.MOVE_CAPTURE, ActionPrimitive.CONVERT)
        ):
            raise ValueError("ELIMINATE requires MOVE_CAPTURE or CONVERT")
        object.__setattr__(self, "action_primitive", action_primitive)
        object.__setattr__(self, "goal_primitive", goal_primitive)
        object.__setattr__(
            self,
            "_construction_snapshot",
            (action_value, goal_value),
        )

    def _assert_unchanged(self) -> None:
        _require_exact_fields(
            self,
            ("action_primitive", "goal_primitive", "_construction_snapshot"),
            "role signature",
        )
        _require_exact_enum(
            self.action_primitive, ActionPrimitive, "role action primitive"
        )
        _require_exact_enum(
            self.goal_primitive, GoalPrimitive, "role goal primitive"
        )
        action_value = _fixed_action_value(self.action_primitive)
        goal_value = _fixed_goal_value(self.goal_primitive)
        if (
            self.goal_primitive is GoalPrimitive.ELIMINATE
            and self.action_primitive
            not in (ActionPrimitive.MOVE_CAPTURE, ActionPrimitive.CONVERT)
        ):
            raise ValueError("role signature became incoherent")
        if (
            type(self._construction_snapshot) is not tuple
            or len(self._construction_snapshot) != 2
            or type(self._construction_snapshot[0]) is not str
            or type(self._construction_snapshot[1]) is not str
        ):
            raise TypeError("role signature construction snapshot changed type")
        if self._construction_snapshot != (
            action_value,
            goal_value,
        ):
            raise ValueError("role signature changed after construction")

    def to_dict(self) -> Dict[str, str]:
        self._assert_unchanged()
        return {
            "action_primitive": self.action_primitive.value,
            "goal_primitive": self.goal_primitive.value,
        }


class BoardEdge(str, Enum):
    """The four directed boundary names used by spatial goal targets."""

    TOP = "TOP"
    RIGHT = "RIGHT"
    BOTTOM = "BOTTOM"
    LEFT = "LEFT"


class D4Transform(str, Enum):
    """Authoritative ordering of the eight square symmetries."""

    I = "I"
    R90 = "R90"
    R180 = "R180"
    R270 = "R270"
    FLR = "FLR"
    FTB = "FTB"
    FD = "FD"
    FA = "FA"


class VectorProfile(str, Enum):
    """D4-invariant Moore profiles plus the PLACE-only sentinel."""

    NONE = "NONE"
    ORTHOGONAL_4 = "ORTHOGONAL_4"
    DIAGONAL_4 = "DIAGONAL_4"
    KING_8 = "KING_8"


class GoalFrameKind(str, Enum):
    """The complete ordered D4 quotient of two goal targets."""

    CONNECT_CONNECT_SAME_AXIS = "CONNECT_CONNECT_SAME_AXIS"
    CONNECT_CONNECT_PERPENDICULAR = "CONNECT_CONNECT_PERPENDICULAR"
    CONNECT_REACH_ALIGNED = "CONNECT_REACH_ALIGNED"
    CONNECT_REACH_PERPENDICULAR = "CONNECT_REACH_PERPENDICULAR"
    CONNECT_ELIMINATE = "CONNECT_ELIMINATE"
    REACH_CONNECT_ALIGNED = "REACH_CONNECT_ALIGNED"
    REACH_CONNECT_PERPENDICULAR = "REACH_CONNECT_PERPENDICULAR"
    REACH_REACH_SAME = "REACH_REACH_SAME"
    REACH_REACH_OPPOSITE = "REACH_REACH_OPPOSITE"
    REACH_REACH_ADJACENT = "REACH_REACH_ADJACENT"
    REACH_ELIMINATE = "REACH_ELIMINATE"
    ELIMINATE_CONNECT = "ELIMINATE_CONNECT"
    ELIMINATE_REACH = "ELIMINATE_REACH"
    ELIMINATE_ELIMINATE = "ELIMINATE_ELIMINATE"


def _fixed_board_edge_value(value: BoardEdge) -> str:
    if value is BoardEdge.TOP:
        return "TOP"
    if value is BoardEdge.RIGHT:
        return "RIGHT"
    if value is BoardEdge.BOTTOM:
        return "BOTTOM"
    if value is BoardEdge.LEFT:
        return "LEFT"
    raise TypeError("value must be a BoardEdge")


def _fixed_d4_transform_value(value: D4Transform) -> str:
    if value is D4Transform.I:
        return "I"
    if value is D4Transform.R90:
        return "R90"
    if value is D4Transform.R180:
        return "R180"
    if value is D4Transform.R270:
        return "R270"
    if value is D4Transform.FLR:
        return "FLR"
    if value is D4Transform.FTB:
        return "FTB"
    if value is D4Transform.FD:
        return "FD"
    if value is D4Transform.FA:
        return "FA"
    raise TypeError("value must be a D4Transform")


def _fixed_vector_profile_value(value: VectorProfile) -> str:
    if value is VectorProfile.NONE:
        return "NONE"
    if value is VectorProfile.ORTHOGONAL_4:
        return "ORTHOGONAL_4"
    if value is VectorProfile.DIAGONAL_4:
        return "DIAGONAL_4"
    if value is VectorProfile.KING_8:
        return "KING_8"
    raise TypeError("value must be a VectorProfile")


def _fixed_goal_frame_kind_value(value: GoalFrameKind) -> str:
    if value is GoalFrameKind.CONNECT_CONNECT_SAME_AXIS:
        return "CONNECT_CONNECT_SAME_AXIS"
    if value is GoalFrameKind.CONNECT_CONNECT_PERPENDICULAR:
        return "CONNECT_CONNECT_PERPENDICULAR"
    if value is GoalFrameKind.CONNECT_REACH_ALIGNED:
        return "CONNECT_REACH_ALIGNED"
    if value is GoalFrameKind.CONNECT_REACH_PERPENDICULAR:
        return "CONNECT_REACH_PERPENDICULAR"
    if value is GoalFrameKind.CONNECT_ELIMINATE:
        return "CONNECT_ELIMINATE"
    if value is GoalFrameKind.REACH_CONNECT_ALIGNED:
        return "REACH_CONNECT_ALIGNED"
    if value is GoalFrameKind.REACH_CONNECT_PERPENDICULAR:
        return "REACH_CONNECT_PERPENDICULAR"
    if value is GoalFrameKind.REACH_REACH_SAME:
        return "REACH_REACH_SAME"
    if value is GoalFrameKind.REACH_REACH_OPPOSITE:
        return "REACH_REACH_OPPOSITE"
    if value is GoalFrameKind.REACH_REACH_ADJACENT:
        return "REACH_REACH_ADJACENT"
    if value is GoalFrameKind.REACH_ELIMINATE:
        return "REACH_ELIMINATE"
    if value is GoalFrameKind.ELIMINATE_CONNECT:
        return "ELIMINATE_CONNECT"
    if value is GoalFrameKind.ELIMINATE_REACH:
        return "ELIMINATE_REACH"
    if value is GoalFrameKind.ELIMINATE_ELIMINATE:
        return "ELIMINATE_ELIMINATE"
    raise TypeError("value must be a GoalFrameKind")


Vector = Tuple[int, int]


def _require_exact_enum_member(value: Any, enum_type: Any, label: str) -> None:
    if type(value) is not enum_type:
        raise TypeError("{} must be a {}".format(label, enum_type.__name__))
    if enum_type is ActionPrimitive:
        expected = _fixed_action_value(value)
    elif enum_type is GoalPrimitive:
        expected = _fixed_goal_value(value)
    elif enum_type is BoardEdge:
        expected = _fixed_board_edge_value(value)
    elif enum_type is D4Transform:
        expected = _fixed_d4_transform_value(value)
    elif enum_type is VectorProfile:
        expected = _fixed_vector_profile_value(value)
    elif enum_type is GoalFrameKind:
        expected = _fixed_goal_frame_kind_value(value)
    else:  # pragma: no cover - every production enum is explicitly closed above
        raise TypeError("{} uses an unsupported enum type".format(label))
    if type(value.value) is not str or type(value.name) is not str:
        raise TypeError("{} vocabulary must use exact strings".format(label))
    if value.value != expected or value.name != expected:
        raise ValueError("{} vocabulary changed".format(label))


def _require_exact_enum(value: Any, enum_type: Any, label: str) -> None:
    _require_exact_enum_member(value, enum_type, label)
    _fixed_enum_members(enum_type, label + " vocabulary")


def _expected_enum_members(
    enum_type: Any,
    _action_members: Tuple[ActionPrimitive, ...] = (
        ActionPrimitive.PLACE,
        ActionPrimitive.MOVE,
        ActionPrimitive.MOVE_CAPTURE,
        ActionPrimitive.PUSH,
        ActionPrimitive.SWAP,
        ActionPrimitive.HOP,
        ActionPrimitive.CONVERT,
    ),
    _goal_members: Tuple[GoalPrimitive, ...] = (
        GoalPrimitive.CONNECT_EDGES,
        GoalPrimitive.REACH_EDGE,
        GoalPrimitive.ELIMINATE,
    ),
    _edge_members: Tuple[BoardEdge, ...] = (
        BoardEdge.TOP,
        BoardEdge.RIGHT,
        BoardEdge.BOTTOM,
        BoardEdge.LEFT,
    ),
    _d4_members: Tuple[D4Transform, ...] = (
        D4Transform.I,
        D4Transform.R90,
        D4Transform.R180,
        D4Transform.R270,
        D4Transform.FLR,
        D4Transform.FTB,
        D4Transform.FD,
        D4Transform.FA,
    ),
    _profile_members: Tuple[VectorProfile, ...] = (
        VectorProfile.NONE,
        VectorProfile.ORTHOGONAL_4,
        VectorProfile.DIAGONAL_4,
        VectorProfile.KING_8,
    ),
    _frame_kind_members: Tuple[GoalFrameKind, ...] = (
        GoalFrameKind.CONNECT_CONNECT_SAME_AXIS,
        GoalFrameKind.CONNECT_CONNECT_PERPENDICULAR,
        GoalFrameKind.CONNECT_REACH_ALIGNED,
        GoalFrameKind.CONNECT_REACH_PERPENDICULAR,
        GoalFrameKind.CONNECT_ELIMINATE,
        GoalFrameKind.REACH_CONNECT_ALIGNED,
        GoalFrameKind.REACH_CONNECT_PERPENDICULAR,
        GoalFrameKind.REACH_REACH_SAME,
        GoalFrameKind.REACH_REACH_OPPOSITE,
        GoalFrameKind.REACH_REACH_ADJACENT,
        GoalFrameKind.REACH_ELIMINATE,
        GoalFrameKind.ELIMINATE_CONNECT,
        GoalFrameKind.ELIMINATE_REACH,
        GoalFrameKind.ELIMINATE_ELIMINATE,
    ),
) -> Tuple[Any, ...]:
    """Return one code-literal member order without consulting Enum carriers."""

    if enum_type is ActionPrimitive:
        return _action_members
    if enum_type is GoalPrimitive:
        return _goal_members
    if enum_type is BoardEdge:
        return _edge_members
    if enum_type is D4Transform:
        return _d4_members
    if enum_type is VectorProfile:
        return _profile_members
    if enum_type is GoalFrameKind:
        return _frame_kind_members
    raise TypeError("unsupported closed enum type")


def _expected_enum_names(enum_type: Any) -> Tuple[str, ...]:
    if enum_type is ActionPrimitive:
        return (
            "PLACE",
            "MOVE",
            "MOVE_CAPTURE",
            "PUSH",
            "SWAP",
            "HOP",
            "CONVERT",
        )
    if enum_type is GoalPrimitive:
        return ("CONNECT_EDGES", "REACH_EDGE", "ELIMINATE")
    if enum_type is BoardEdge:
        return ("TOP", "RIGHT", "BOTTOM", "LEFT")
    if enum_type is D4Transform:
        return ("I", "R90", "R180", "R270", "FLR", "FTB", "FD", "FA")
    if enum_type is VectorProfile:
        return ("NONE", "ORTHOGONAL_4", "DIAGONAL_4", "KING_8")
    if enum_type is GoalFrameKind:
        return (
            "CONNECT_CONNECT_SAME_AXIS",
            "CONNECT_CONNECT_PERPENDICULAR",
            "CONNECT_REACH_ALIGNED",
            "CONNECT_REACH_PERPENDICULAR",
            "CONNECT_ELIMINATE",
            "REACH_CONNECT_ALIGNED",
            "REACH_CONNECT_PERPENDICULAR",
            "REACH_REACH_SAME",
            "REACH_REACH_OPPOSITE",
            "REACH_REACH_ADJACENT",
            "REACH_ELIMINATE",
            "ELIMINATE_CONNECT",
            "ELIMINATE_REACH",
            "ELIMINATE_ELIMINATE",
        )
    raise TypeError("unsupported closed enum type")


def _fixed_enum_members(enum_type: Any, label: str) -> Tuple[Any, ...]:
    """Validate every mutable Enum carrier and return the fixed identity order."""

    members = _expected_enum_members(enum_type)
    names = _expected_enum_names(enum_type)
    if any(type(member) is not enum_type for member in members):
        raise UniverseClosureError("{} member type changed".format(label))
    raw_names = tuple(member.__dict__.get("_name_") for member in members)
    raw_values = tuple(member.__dict__.get("_value_") for member in members)
    intrinsic_values = tuple(str.__str__(member) for member in members)
    if (
        any(type(name) is not str for name in raw_names)
        or any(type(value) is not str for value in raw_values)
        or any(type(value) is not str for value in intrinsic_values)
        or raw_names != names
        or raw_values != names
        or intrinsic_values != names
    ):
        raise UniverseClosureError("{} member identity carrier changed".format(label))

    member_names = enum_type.__dict__.get("_member_names_")
    if (
        type(member_names) is not list
        or any(type(name) is not str for name in member_names)
        or tuple(member_names) != names
    ):
        raise UniverseClosureError("{} member-name carrier changed".format(label))

    member_map = enum_type.__dict__.get("_member_map_")
    if (
        type(member_map) is not dict
        or any(type(name) is not str for name in member_map)
        or tuple(member_map) != names
        or tuple(map(id, member_map.values())) != tuple(map(id, members))
    ):
        raise UniverseClosureError("{} member map changed".format(label))

    public_members = enum_type.__members__
    if (
        tuple(public_members) != names
        or tuple(map(id, public_members.values())) != tuple(map(id, members))
    ):
        raise UniverseClosureError("{} public member map changed".format(label))

    value_map = enum_type.__dict__.get("_value2member_map_")
    if (
        type(value_map) is not dict
        or any(type(value) is not str for value in value_map)
        or tuple(value_map) != names
        or tuple(map(id, value_map.values())) != tuple(map(id, members))
    ):
        raise UniverseClosureError("{} value map changed".format(label))
    if len({id(member) for member in members}) != len(members):
        raise UniverseClosureError("{} member identities alias".format(label))
    if tuple(
        id(enum_type.__dict__.get(name)) for name in names
    ) != tuple(map(id, members)):
        raise UniverseClosureError("{} class member binding changed".format(label))
    return members


def _active_actions() -> Tuple[ActionPrimitive, ...]:
    return _fixed_enum_members(ActionPrimitive, "action vocabulary")


def _is_active_action(action: ActionPrimitive) -> bool:
    return (
        action is ActionPrimitive.PLACE
        or action is ActionPrimitive.MOVE
        or action is ActionPrimitive.MOVE_CAPTURE
        or action is ActionPrimitive.PUSH
        or action is ActionPrimitive.SWAP
        or action is ActionPrimitive.HOP
        or action is ActionPrimitive.CONVERT
    )


def _is_schema_v4_action(action: ActionPrimitive) -> bool:
    return (
        action is ActionPrimitive.PUSH
        or action is ActionPrimitive.SWAP
        or action is ActionPrimitive.HOP
        or action is ActionPrimitive.CONVERT
    )


def _is_material_reducing_action(action: ActionPrimitive) -> bool:
    return (
        action is ActionPrimitive.MOVE_CAPTURE
        or action is ActionPrimitive.CONVERT
    )


def _spatial_goals() -> Tuple[GoalPrimitive, GoalPrimitive]:
    return (GoalPrimitive.CONNECT_EDGES, GoalPrimitive.REACH_EDGE)


def _connect_axes() -> Tuple[Tuple[BoardEdge, BoardEdge], ...]:
    return (
        (BoardEdge.TOP, BoardEdge.BOTTOM),
        (BoardEdge.RIGHT, BoardEdge.LEFT),
    )


def _fixed_edge_index(edge: BoardEdge) -> int:
    if edge is BoardEdge.TOP:
        return 0
    if edge is BoardEdge.RIGHT:
        return 1
    if edge is BoardEdge.BOTTOM:
        return 2
    if edge is BoardEdge.LEFT:
        return 3
    raise TypeError("edge must be a BoardEdge")


def _board_edge_by_index(index: int) -> BoardEdge:
    if index == 0:
        return BoardEdge.TOP
    if index == 1:
        return BoardEdge.RIGHT
    if index == 2:
        return BoardEdge.BOTTOM
    if index == 3:
        return BoardEdge.LEFT
    raise ValueError("edge index is outside the closed square boundary")


def _opposite_edge(edge: BoardEdge) -> BoardEdge:
    return _board_edge_by_index((_fixed_edge_index(edge) + 2) % 4)


def _transform_edge(edge: BoardEdge, transform: D4Transform) -> BoardEdge:
    index = _fixed_edge_index(edge)
    if transform is D4Transform.I:
        target = index
    elif transform is D4Transform.R90:
        target = (index + 1) % 4
    elif transform is D4Transform.R180:
        target = (index + 2) % 4
    elif transform is D4Transform.R270:
        target = (index + 3) % 4
    elif transform is D4Transform.FLR:
        target = (-index) % 4
    elif transform is D4Transform.FTB:
        target = (2 - index) % 4
    elif transform is D4Transform.FD:
        target = (3 - index) % 4
    elif transform is D4Transform.FA:
        target = (1 - index) % 4
    else:
        raise TypeError("transform must be a D4Transform")
    return _board_edge_by_index(target)


def _inverse_transform(transform: D4Transform) -> D4Transform:
    if transform is D4Transform.I:
        return D4Transform.I
    if transform is D4Transform.R90:
        return D4Transform.R270
    if transform is D4Transform.R180:
        return D4Transform.R180
    if transform is D4Transform.R270:
        return D4Transform.R90
    if transform is D4Transform.FLR:
        return D4Transform.FLR
    if transform is D4Transform.FTB:
        return D4Transform.FTB
    if transform is D4Transform.FD:
        return D4Transform.FD
    if transform is D4Transform.FA:
        return D4Transform.FA
    raise TypeError("transform must be a D4Transform")


def _moore_vectors() -> Tuple[Vector, ...]:
    return (
        (-1, -1),
        (-1, 0),
        (-1, 1),
        (0, -1),
        (0, 1),
        (1, -1),
        (1, 0),
        (1, 1),
    )


def _fixed_profile_vector_set(profile: VectorProfile) -> frozenset:
    if profile is VectorProfile.ORTHOGONAL_4:
        return frozenset(((-1, 0), (0, -1), (0, 1), (1, 0)))
    if profile is VectorProfile.DIAGONAL_4:
        return frozenset(((-1, -1), (-1, 1), (1, -1), (1, 1)))
    if profile is VectorProfile.KING_8:
        return frozenset(_moore_vectors())
    raise ValueError("NONE has no movement vector set")


def _is_movement_vector_profile(profile: VectorProfile) -> bool:
    return (
        profile is VectorProfile.ORTHOGONAL_4
        or profile is VectorProfile.DIAGONAL_4
        or profile is VectorProfile.KING_8
    )


def _hash_domain(name: str) -> bytes:
    """Return every identity domain from code literals, never a mutable table."""

    if type(name) is not str:
        raise TypeError("hash-domain name must be an exact string")
    if name == "semantic_hash":
        return b"parity-forge:typed-occupancy:semantic:v1\0"
    if name == "role_neutral_semantic_hash":
        return b"parity-forge:typed-occupancy:role-neutral-semantic:v1\0"
    if name == "skeleton_hash":
        return b"parity-forge:typed-occupancy:skeleton:v1\0"
    if name == "role_neutral_skeleton_hash":
        return b"parity-forge:typed-occupancy:role-neutral-skeleton:v1\0"
    if name == "role_atom_root":
        return b"parity-forge:typed-occupancy:role-atoms:v1\0"
    if name == "ordered_semantic_signature_root":
        return b"parity-forge:typed-occupancy:ordered-semantics:v1\0"
    if name == "goal_frame_root":
        return b"parity-forge:typed-occupancy:goal-frames:v1\0"
    if name == "raw_goal_frame_root":
        return b"parity-forge:typed-occupancy:raw-goal-frames:v1\0"
    if name == "role_neutral_goal_frame_root":
        return b"parity-forge:typed-occupancy:role-neutral-goal-frames:v1\0"
    if name == "admitted_signature_root":
        return b"parity-forge:typed-occupancy:admitted-signatures:v1\0"
    if name == "role_neutral_semantic_root":
        return b"parity-forge:typed-occupancy:role-neutral-semantics:v1\0"
    if name == "fresh_semantic_root":
        return b"parity-forge:typed-occupancy:fresh-semantics:v1\0"
    if name == "old_semantic_root":
        return b"parity-forge:typed-occupancy:old-semantics:v1\0"
    if name == "semantic_mapping_root":
        return b"parity-forge:typed-occupancy:semantic-mapping:v1\0"
    if name == "vector_profile_definition_root":
        return b"parity-forge:typed-occupancy:vector-profile-definitions:v1\0"
    if name == "d4_definition_root":
        return b"parity-forge:typed-occupancy:d4-definitions:v1\0"
    if name == "ordered_profiled_skeleton_root":
        return b"parity-forge:typed-occupancy:ordered-skeletons:v1\0"
    if name == "self_isomorphic_ordered_skeleton_root":
        return b"parity-forge:typed-occupancy:self-isomorphic:v1\0"
    if name == "old_region_ordered_skeleton_root":
        return b"parity-forge:typed-occupancy:old-region:v1\0"
    if name == "old_region_role_neutral_skeleton_root":
        return b"parity-forge:typed-occupancy:old-region-neutral:v1\0"
    if name == "fresh_canonical_skeleton_root":
        return b"parity-forge:typed-occupancy:fresh-canonical:v1\0"
    if name == "full_witness_mapping_root":
        return b"parity-forge:typed-occupancy:full-witness-mapping:v1\0"
    if name == "descriptor_root":
        return b"parity-forge:typed-occupancy:descriptor:v1\0"
    raise UniverseClosureError("unknown hash-domain name: {}".format(name))


def _require_exact_fields(value: Any, expected: Sequence[str], label: str) -> None:
    try:
        actual = set(vars(value))
    except TypeError as error:
        raise TypeError("{} must expose exact instance fields".format(label)) from error
    expected_set = set(expected)
    if actual != expected_set:
        raise ValueError(
            "{} has noncanonical fields: expected {}, got {}".format(
                label, sorted(expected_set), sorted(actual)
            )
        )


def _exact_dict(value: Any, label: str) -> Dict[str, Any]:
    if type(value) is not dict:
        raise TypeError("{} must be an exact object".format(label))
    if any(type(key) is not str for key in value):
        raise TypeError("{} keys must be exact strings".format(label))
    return value


def _exact_keys(value: Dict[str, Any], expected: Sequence[str], label: str) -> None:
    expected_set = set(expected)
    actual = set(value)
    if actual != expected_set:
        missing = sorted(expected_set - actual)
        unknown = sorted(actual - expected_set)
        details: List[str] = []
        if missing:
            details.append("missing {}".format(missing))
        if unknown:
            details.append("unknown {}".format(unknown))
        raise ValueError("{} has {}".format(label, ", ".join(details)))


def _enum_from_exact_string(enum_type: Any, value: Any, label: str) -> Any:
    if type(value) is not str:
        raise TypeError("{} must be an exact string".format(label))
    members = _fixed_enum_members(enum_type, label + " vocabulary")
    try:
        result = enum_type(value)
    except ValueError as error:
        raise ValueError(
            "{} must be one of {}".format(
                label, [member.value for member in members]
            )
        ) from error
    _require_exact_enum(result, enum_type, label)
    if result.value != value:
        raise ValueError("{} enum lookup changed identity".format(label))
    return result


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _hash(domain: bytes, canonical: str) -> str:
    return hashlib.sha256(domain + canonical.encode("utf-8")).hexdigest()


def _sequence_root(domain: bytes, canonical_values: Iterable[str]) -> str:
    values = tuple(canonical_values)
    if any(type(value) is not str for value in values):
        raise TypeError("ordered root values must be exact canonical strings")
    digest = hashlib.sha256(domain)
    digest.update(len(values).to_bytes(8, "big"))
    for ordinal, canonical in enumerate(values):
        encoded = canonical.encode("utf-8")
        digest.update(ordinal.to_bytes(8, "big"))
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def _assert_role_signature(value: Any, label: str) -> None:
    if type(value) is not RoleSignature:
        raise TypeError("{} must be a RoleSignature".format(label))
    value._assert_unchanged()
    _require_exact_enum(
        value.action_primitive, ActionPrimitive, label + " action primitive"
    )
    _require_exact_enum(
        value.goal_primitive, GoalPrimitive, label + " goal primitive"
    )
    if not _is_active_action(value.action_primitive):
        raise ValueError("{} action primitive is retired or unknown".format(label))
    if (
        value.goal_primitive is GoalPrimitive.ELIMINATE
        and not _is_material_reducing_action(value.action_primitive)
    ):
        raise ValueError(
            "{} ELIMINATE requires MOVE_CAPTURE or CONVERT".format(label)
        )


def _detached_role_signature(value: Any, label: str) -> RoleSignature:
    _assert_role_signature(value, label)
    return RoleSignature(value.action_primitive, value.goal_primitive)


def _role_to_dict(role: RoleSignature) -> Dict[str, str]:
    _assert_role_signature(role, "role signature")
    return {
        "action_primitive": role.action_primitive.value,
        "goal_primitive": role.goal_primitive.value,
    }


def _parse_role(value: Any, label: str) -> RoleSignature:
    role = _exact_dict(value, label)
    _exact_keys(role, ("action_primitive", "goal_primitive"), label)
    result = RoleSignature(
        action_primitive=_enum_from_exact_string(
            ActionPrimitive, role["action_primitive"], label + ".action_primitive"
        ),
        goal_primitive=_enum_from_exact_string(
            GoalPrimitive, role["goal_primitive"], label + ".goal_primitive"
        ),
    )
    _assert_role_signature(result, label)
    return result


def _validate_goal_target_components(
    goal_primitive: Any, edges: Any, label: str
) -> None:
    _require_exact_enum(goal_primitive, GoalPrimitive, label + " primitive")
    if type(edges) is not tuple:
        raise TypeError("{} edges must be a canonical tuple".format(label))
    for edge in edges:
        _require_exact_enum(edge, BoardEdge, label + " edge")
    if goal_primitive is GoalPrimitive.CONNECT_EDGES:
        if edges not in _connect_axes():
            raise ValueError(
                "CONNECT_EDGES target must be one canonical opposite-edge axis"
            )
    elif goal_primitive is GoalPrimitive.REACH_EDGE:
        if len(edges) != 1:
            raise ValueError("REACH_EDGE target must contain exactly one edge")
    elif goal_primitive is GoalPrimitive.ELIMINATE:
        if edges:
            raise ValueError("ELIMINATE target cannot contain a spatial edge")
    else:  # pragma: no cover - exact closed enum above
        raise AssertionError("closed goal primitive was not handled")


@dataclass(frozen=True, init=False)
class GoalTarget:
    """One goal primitive together with its complete spatial target."""

    goal_primitive: GoalPrimitive
    edges: Tuple[BoardEdge, ...]
    _construction_snapshot: str

    def __init__(
        self, goal_primitive: GoalPrimitive, edges: Tuple[BoardEdge, ...]
    ) -> None:
        _validate_goal_target_components(goal_primitive, edges, "goal target")
        object.__setattr__(self, "goal_primitive", goal_primitive)
        object.__setattr__(self, "edges", tuple(edges))
        object.__setattr__(
            self, "_construction_snapshot", _canonical_json(self._payload_unchecked())
        )

    def _payload_unchecked(self) -> Dict[str, Any]:
        return {
            "goal_primitive": self.goal_primitive.value,
            "edges": [edge.value for edge in self.edges],
        }

    def _assert_unchanged(self) -> None:
        _require_exact_fields(
            self,
            ("goal_primitive", "edges", "_construction_snapshot"),
            "goal target",
        )
        _validate_goal_target_components(
            self.goal_primitive, self.edges, "goal target"
        )
        if (
            type(self._construction_snapshot) is not str
            or self._construction_snapshot
            != _canonical_json(self._payload_unchecked())
        ):
            raise ValueError("goal target changed after construction")

    def to_dict(self) -> Dict[str, Any]:
        self._assert_unchanged()
        return self._payload_unchecked()


@dataclass(frozen=True, init=False)
class GoalFrame:
    """Two ordered goal targets before setup or first-player expansion."""

    role_a: GoalTarget
    role_b: GoalTarget
    _construction_snapshot: str

    def __init__(self, role_a: GoalTarget, role_b: GoalTarget) -> None:
        if type(role_a) is not GoalTarget:
            raise TypeError("goal frame role A must be a GoalTarget")
        if type(role_b) is not GoalTarget:
            raise TypeError("goal frame role B must be a GoalTarget")
        role_a._assert_unchanged()
        role_b._assert_unchanged()
        detached_a = GoalTarget(role_a.goal_primitive, tuple(role_a.edges))
        detached_b = GoalTarget(role_b.goal_primitive, tuple(role_b.edges))
        object.__setattr__(self, "role_a", detached_a)
        object.__setattr__(self, "role_b", detached_b)
        object.__setattr__(
            self, "_construction_snapshot", _canonical_json(self._payload_unchecked())
        )

    def _payload_unchecked(self) -> Dict[str, Any]:
        return {
            "A": self.role_a._payload_unchecked(),
            "B": self.role_b._payload_unchecked(),
        }

    def _assert_unchanged(self) -> None:
        _require_exact_fields(
            self,
            ("role_a", "role_b", "_construction_snapshot"),
            "goal frame",
        )
        if type(self.role_a) is not GoalTarget or type(self.role_b) is not GoalTarget:
            raise TypeError("goal frame roles must remain GoalTarget values")
        self.role_a._assert_unchanged()
        self.role_b._assert_unchanged()
        if (
            type(self._construction_snapshot) is not str
            or self._construction_snapshot
            != _canonical_json(self._payload_unchecked())
        ):
            raise ValueError("goal frame changed after construction")

    @property
    def kind(self) -> GoalFrameKind:
        self._assert_unchanged()
        result = _classify_goal_frame(self)
        _require_exact_enum(result, GoalFrameKind, "goal frame kind")
        return result

    def to_dict(self) -> Dict[str, Any]:
        self._assert_unchanged()
        return self._payload_unchecked()


@dataclass(frozen=True, init=False)
class SemanticSignature:
    """An ordered pair of coherent role atoms, before profiles or targets."""

    universe_version: int
    role_a: RoleSignature
    role_b: RoleSignature
    _construction_snapshot: str

    def __init__(
        self,
        universe_version: int,
        role_a: RoleSignature,
        role_b: RoleSignature,
    ) -> None:
        if type(universe_version) is not int:
            raise TypeError("semantic signature version must be an exact integer")
        if universe_version != _official_universe_version():
            raise ValueError(
                "semantic signature version must equal {}".format(
                    _official_universe_version()
                )
            )
        detached_a = _detached_role_signature(role_a, "semantic role A")
        detached_b = _detached_role_signature(role_b, "semantic role B")
        object.__setattr__(self, "universe_version", universe_version)
        object.__setattr__(self, "role_a", detached_a)
        object.__setattr__(self, "role_b", detached_b)
        object.__setattr__(
            self, "_construction_snapshot", _canonical_json(self._payload_unchecked())
        )

    def _payload_unchecked(self) -> Dict[str, Any]:
        return {
            "universe_version": self.universe_version,
            "roles": {
                "A": _role_to_dict(self.role_a),
                "B": _role_to_dict(self.role_b),
            },
        }

    def _assert_unchanged(self) -> None:
        _require_exact_fields(
            self,
            ("universe_version", "role_a", "role_b", "_construction_snapshot"),
            "semantic signature",
        )
        if (
            type(self.universe_version) is not int
            or self.universe_version != _official_universe_version()
        ):
            raise ValueError("semantic signature version changed after construction")
        _assert_role_signature(self.role_a, "semantic role A")
        _assert_role_signature(self.role_b, "semantic role B")
        if (
            type(self._construction_snapshot) is not str
            or self._construction_snapshot
            != _canonical_json(self._payload_unchecked())
        ):
            raise ValueError("semantic signature changed after construction")

    @property
    def roles(self) -> Tuple[RoleSignature, RoleSignature]:
        self._assert_unchanged()
        return (self.role_a, self.role_b)

    def to_dict(self) -> Dict[str, Any]:
        self._assert_unchanged()
        return self._payload_unchecked()


@dataclass(frozen=True, init=False)
class ProfiledRole:
    """A coherent role atom with a profile and exact goal target."""

    signature: RoleSignature
    vector_profile: VectorProfile
    goal_target: GoalTarget
    _construction_snapshot: str

    def __init__(
        self,
        signature: RoleSignature,
        vector_profile: VectorProfile,
        goal_target: GoalTarget,
    ) -> None:
        detached_signature = _detached_role_signature(
            signature, "profiled role signature"
        )
        _require_exact_enum(
            vector_profile, VectorProfile, "profiled role vector profile"
        )
        if type(goal_target) is not GoalTarget:
            raise TypeError("profiled role goal target must be a GoalTarget")
        goal_target._assert_unchanged()
        detached_target = GoalTarget(
            goal_target.goal_primitive, tuple(goal_target.edges)
        )
        if detached_target.goal_primitive is not detached_signature.goal_primitive:
            raise ValueError("profiled role target must match its goal primitive")
        if detached_signature.action_primitive is ActionPrimitive.PLACE:
            if vector_profile is not VectorProfile.NONE:
                raise ValueError("PLACE must use vector profile NONE")
        elif not _is_movement_vector_profile(vector_profile):
            raise ValueError("non-PLACE action must use one invariant vector profile")
        object.__setattr__(self, "signature", detached_signature)
        object.__setattr__(self, "vector_profile", vector_profile)
        object.__setattr__(self, "goal_target", detached_target)
        object.__setattr__(
            self, "_construction_snapshot", _canonical_json(self._payload_unchecked())
        )

    def _payload_unchecked(self) -> Dict[str, Any]:
        return {
            "action_primitive": self.signature.action_primitive.value,
            "goal_primitive": self.signature.goal_primitive.value,
            "vector_profile": self.vector_profile.value,
            "target_edges": [edge.value for edge in self.goal_target.edges],
        }

    def _assert_unchanged(self) -> None:
        _require_exact_fields(
            self,
            (
                "signature",
                "vector_profile",
                "goal_target",
                "_construction_snapshot",
            ),
            "profiled role",
        )
        _assert_role_signature(self.signature, "profiled role signature")
        _require_exact_enum(
            self.vector_profile, VectorProfile, "profiled role vector profile"
        )
        if type(self.goal_target) is not GoalTarget:
            raise TypeError("profiled role goal target must remain a GoalTarget")
        self.goal_target._assert_unchanged()
        if self.goal_target.goal_primitive is not self.signature.goal_primitive:
            raise ValueError("profiled role target changed away from its goal")
        if self.signature.action_primitive is ActionPrimitive.PLACE:
            if self.vector_profile is not VectorProfile.NONE:
                raise ValueError("PLACE must use vector profile NONE")
        elif not _is_movement_vector_profile(self.vector_profile):
            raise ValueError("non-PLACE action must use one invariant vector profile")
        if (
            type(self._construction_snapshot) is not str
            or self._construction_snapshot
            != _canonical_json(self._payload_unchecked())
        ):
            raise ValueError("profiled role changed after construction")

    def to_dict(self) -> Dict[str, Any]:
        self._assert_unchanged()
        return self._payload_unchecked()


@dataclass(frozen=True, init=False)
class ProfiledSkeleton:
    """One ordered, oriented profiled skeleton and no executable setup."""

    universe_version: int
    role_a: ProfiledRole
    role_b: ProfiledRole
    _construction_snapshot: str

    def __init__(
        self,
        universe_version: int,
        role_a: ProfiledRole,
        role_b: ProfiledRole,
    ) -> None:
        if type(universe_version) is not int:
            raise TypeError("profiled skeleton version must be an exact integer")
        if universe_version != _official_universe_version():
            raise ValueError(
                "profiled skeleton version must equal {}".format(
                    _official_universe_version()
                )
            )
        if type(role_a) is not ProfiledRole:
            raise TypeError("profiled skeleton role A must be a ProfiledRole")
        if type(role_b) is not ProfiledRole:
            raise TypeError("profiled skeleton role B must be a ProfiledRole")
        role_a._assert_unchanged()
        role_b._assert_unchanged()
        detached_a = ProfiledRole(
            role_a.signature, role_a.vector_profile, role_a.goal_target
        )
        detached_b = ProfiledRole(
            role_b.signature, role_b.vector_profile, role_b.goal_target
        )
        signature = SemanticSignature(
            universe_version=universe_version,
            role_a=detached_a.signature,
            role_b=detached_b.signature,
        )
        if not _schema_v4_admitted_unchecked(signature):
            raise ValueError(
                "profiled skeleton requires a schema-v4 action or ELIMINATE goal"
            )
        object.__setattr__(self, "universe_version", universe_version)
        object.__setattr__(self, "role_a", detached_a)
        object.__setattr__(self, "role_b", detached_b)
        object.__setattr__(
            self, "_construction_snapshot", _canonical_json(self._payload_unchecked())
        )

    def _payload_unchecked(self) -> Dict[str, Any]:
        return {
            "universe_version": self.universe_version,
            "roles": {
                "A": self.role_a._payload_unchecked(),
                "B": self.role_b._payload_unchecked(),
            },
        }

    def _assert_unchanged(self) -> None:
        _require_exact_fields(
            self,
            ("universe_version", "role_a", "role_b", "_construction_snapshot"),
            "profiled skeleton",
        )
        if (
            type(self.universe_version) is not int
            or self.universe_version != _official_universe_version()
        ):
            raise ValueError("profiled skeleton version changed after construction")
        if type(self.role_a) is not ProfiledRole or type(self.role_b) is not ProfiledRole:
            raise TypeError("profiled skeleton roles must remain ProfiledRole values")
        self.role_a._assert_unchanged()
        self.role_b._assert_unchanged()
        signature = SemanticSignature(
            self.universe_version, self.role_a.signature, self.role_b.signature
        )
        if not _schema_v4_admitted_unchecked(signature):
            raise ValueError("profiled skeleton no longer satisfies schema-v4 admission")
        if (
            type(self._construction_snapshot) is not str
            or self._construction_snapshot
            != _canonical_json(self._payload_unchecked())
        ):
            raise ValueError("profiled skeleton changed after construction")

    @property
    def semantic_signature(self) -> SemanticSignature:
        self._assert_unchanged()
        return SemanticSignature(
            universe_version=self.universe_version,
            role_a=self.role_a.signature,
            role_b=self.role_b.signature,
        )

    @property
    def goal_frame(self) -> GoalFrame:
        self._assert_unchanged()
        return GoalFrame(self.role_a.goal_target, self.role_b.goal_target)

    @property
    def vector_profiles(self) -> Tuple[VectorProfile, VectorProfile]:
        self._assert_unchanged()
        return (self.role_a.vector_profile, self.role_b.vector_profile)

    def to_dict(self) -> Dict[str, Any]:
        self._assert_unchanged()
        return self._payload_unchecked()


@dataclass(frozen=True, init=False)
class SkeletonOrbitWitness:
    """Forward and inverse proof for one canonical D4-plus-swap identity."""

    source: ProfiledSkeleton
    canonical: ProfiledSkeleton
    transform: D4Transform
    inverse_transform: D4Transform
    role_swapped: bool
    source_goal_frame: GoalFrame
    source_vector_profiles: Tuple[VectorProfile, VectorProfile]
    _construction_snapshot: str

    def __init__(
        self,
        source: ProfiledSkeleton,
        canonical: ProfiledSkeleton,
        transform: D4Transform,
        inverse_transform: D4Transform,
        role_swapped: bool,
        source_goal_frame: GoalFrame,
        source_vector_profiles: Tuple[VectorProfile, VectorProfile],
    ) -> None:
        if type(source) is not ProfiledSkeleton:
            raise TypeError("orbit witness source must be a ProfiledSkeleton")
        if type(canonical) is not ProfiledSkeleton:
            raise TypeError("orbit witness canonical must be a ProfiledSkeleton")
        source._assert_unchanged()
        canonical._assert_unchanged()
        detached_source = ProfiledSkeleton(
            source.universe_version, source.role_a, source.role_b
        )
        detached_canonical = ProfiledSkeleton(
            canonical.universe_version, canonical.role_a, canonical.role_b
        )
        _require_exact_enum(transform, D4Transform, "orbit witness transform")
        _require_exact_enum(
            inverse_transform, D4Transform, "orbit witness inverse transform"
        )
        if type(role_swapped) is not bool:
            raise TypeError("orbit witness role_swapped must be an exact boolean")
        if type(source_goal_frame) is not GoalFrame:
            raise TypeError("orbit witness source_goal_frame must be a GoalFrame")
        source_goal_frame._assert_unchanged()
        detached_frame = GoalFrame(
            source_goal_frame.role_a, source_goal_frame.role_b
        )
        if (
            type(source_vector_profiles) is not tuple
            or len(source_vector_profiles) != 2
            or any(
                type(profile) is not VectorProfile
                for profile in source_vector_profiles
            )
        ):
            raise TypeError(
                "orbit witness source_vector_profiles must be a canonical pair"
            )
        if inverse_transform is not _inverse_transform(transform):
            raise ValueError("orbit witness inverse transform is incorrect")
        if detached_source.goal_frame != detached_frame:
            raise ValueError("orbit witness goal frame does not describe its source")
        detached_profiles = tuple(source_vector_profiles)
        if detached_source.vector_profiles != detached_profiles:
            raise ValueError(
                "orbit witness vector profiles do not describe its source"
            )
        base = (
            _role_swap_skeleton_unchecked(detached_source)
            if role_swapped
            else detached_source
        )
        forward = _transform_skeleton_unchecked(base, transform)
        if forward != detached_canonical:
            raise ValueError("orbit witness forward map does not reach canonical")
        restored = _transform_skeleton_unchecked(
            detached_canonical, inverse_transform
        )
        if role_swapped:
            restored = _role_swap_skeleton_unchecked(restored)
        if restored != detached_source:
            raise ValueError("orbit witness inverse does not restore source")
        expected, expected_transform, expected_swapped, _expected_json = (
            _canonical_skeleton_choice(detached_source)
        )
        if (
            expected != detached_canonical
            or expected_transform is not transform
            or expected_swapped is not role_swapped
        ):
            raise ValueError("orbit witness does not identify the byte minimum")
        object.__setattr__(self, "source", detached_source)
        object.__setattr__(self, "canonical", detached_canonical)
        object.__setattr__(self, "transform", transform)
        object.__setattr__(self, "inverse_transform", inverse_transform)
        object.__setattr__(self, "role_swapped", role_swapped)
        object.__setattr__(self, "source_goal_frame", detached_frame)
        object.__setattr__(self, "source_vector_profiles", detached_profiles)
        object.__setattr__(
            self, "_construction_snapshot", _canonical_json(self._payload_unchecked())
        )

    def _payload_unchecked(self) -> Dict[str, Any]:
        return {
            "source": self.source._payload_unchecked(),
            "canonical": self.canonical._payload_unchecked(),
            "transform": self.transform.value,
            "inverse_transform": self.inverse_transform.value,
            "role_swapped": self.role_swapped,
            "source_goal_frame": self.source_goal_frame._payload_unchecked(),
            "source_vector_profiles": [
                profile.value for profile in self.source_vector_profiles
            ],
        }

    def _assert_unchanged(self) -> None:
        _require_exact_fields(
            self,
            (
                "source",
                "canonical",
                "transform",
                "inverse_transform",
                "role_swapped",
                "source_goal_frame",
                "source_vector_profiles",
                "_construction_snapshot",
            ),
            "orbit witness",
        )
        if type(self.source) is not ProfiledSkeleton:
            raise TypeError("orbit witness source must remain a ProfiledSkeleton")
        if type(self.canonical) is not ProfiledSkeleton:
            raise TypeError("orbit witness canonical must remain a ProfiledSkeleton")
        self.source._assert_unchanged()
        self.canonical._assert_unchanged()
        _require_exact_enum(self.transform, D4Transform, "orbit witness transform")
        _require_exact_enum(
            self.inverse_transform, D4Transform, "orbit witness inverse transform"
        )
        if type(self.role_swapped) is not bool:
            raise TypeError("orbit witness role_swapped must remain an exact boolean")
        if type(self.source_goal_frame) is not GoalFrame:
            raise TypeError("orbit witness source frame must remain a GoalFrame")
        self.source_goal_frame._assert_unchanged()
        if (
            type(self.source_vector_profiles) is not tuple
            or len(self.source_vector_profiles) != 2
            or any(
                type(profile) is not VectorProfile
                for profile in self.source_vector_profiles
            )
        ):
            raise TypeError("orbit witness profiles changed type")
        if (
            type(self._construction_snapshot) is not str
            or self._construction_snapshot
            != _canonical_json(self._payload_unchecked())
        ):
            raise ValueError("orbit witness changed after construction")
        if self.inverse_transform is not _inverse_transform(self.transform):
            raise ValueError("orbit witness inverse transform changed")
        if self.source.goal_frame != self.source_goal_frame:
            raise ValueError("orbit witness source frame changed")
        if self.source.vector_profiles != self.source_vector_profiles:
            raise ValueError("orbit witness source profiles changed")
        base = (
            _role_swap_skeleton_unchecked(self.source)
            if self.role_swapped
            else self.source
        )
        if _transform_skeleton_unchecked(base, self.transform) != self.canonical:
            raise ValueError("orbit witness forward map changed")
        expected, transform, role_swapped, _expected_json = (
            _canonical_skeleton_choice(self.source)
        )
        if (
            expected != self.canonical
            or transform is not self.transform
            or role_swapped is not self.role_swapped
        ):
            raise ValueError("orbit witness no longer identifies the byte minimum")

    def to_dict(self) -> Dict[str, Any]:
        self._assert_unchanged()
        return self._payload_unchecked()


def _is_lower_sha256(value: Any) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


@dataclass(frozen=True, init=False)
class SkeletonCanonicalization:
    """Canonical bytes, domain-separated identity, and reversible witness."""

    canonical_hash: str
    canonical_json: str
    witness: SkeletonOrbitWitness
    _construction_snapshot: str

    def __init__(
        self,
        canonical_hash: str,
        canonical_json: str,
        witness: SkeletonOrbitWitness,
    ) -> None:
        if not _is_lower_sha256(canonical_hash):
            raise ValueError("canonical skeleton hash must be a SHA-256 hex digest")
        if type(canonical_json) is not str:
            raise TypeError("canonical skeleton JSON must be an exact string")
        if type(witness) is not SkeletonOrbitWitness:
            raise TypeError("canonical skeleton witness has the wrong type")
        witness._assert_unchanged()
        detached_witness = SkeletonOrbitWitness(
            witness.source,
            witness.canonical,
            witness.transform,
            witness.inverse_transform,
            witness.role_swapped,
            witness.source_goal_frame,
            witness.source_vector_profiles,
        )
        expected_json = _skeleton_json_unchecked(detached_witness.canonical)
        if canonical_json != expected_json:
            raise ValueError("canonical skeleton JSON is not the byte minimum")
        expected_hash = _hash(
            _hash_domain("role_neutral_skeleton_hash"), expected_json
        )
        if canonical_hash != expected_hash:
            raise ValueError("canonical skeleton hash does not seal canonical JSON")
        object.__setattr__(self, "canonical_hash", canonical_hash)
        object.__setattr__(self, "canonical_json", canonical_json)
        object.__setattr__(self, "witness", detached_witness)
        object.__setattr__(
            self, "_construction_snapshot", _canonical_json(self._payload_unchecked())
        )

    def _payload_unchecked(self) -> Dict[str, Any]:
        return {
            "canonical_hash": self.canonical_hash,
            "canonical_json": self.canonical_json,
            "witness": self.witness._payload_unchecked(),
        }

    def _assert_unchanged(self) -> None:
        _require_exact_fields(
            self,
            (
                "canonical_hash",
                "canonical_json",
                "witness",
                "_construction_snapshot",
            ),
            "skeleton canonicalization",
        )
        if not _is_lower_sha256(self.canonical_hash):
            raise ValueError("canonical skeleton hash changed type or format")
        if type(self.canonical_json) is not str:
            raise TypeError("canonical skeleton JSON changed type")
        if type(self.witness) is not SkeletonOrbitWitness:
            raise TypeError("canonical skeleton witness changed type")
        self.witness._assert_unchanged()
        expected_json = _skeleton_json_unchecked(self.witness.canonical)
        if self.canonical_json != expected_json:
            raise ValueError("canonical skeleton JSON changed")
        if self.canonical_hash != _hash(
            _hash_domain("role_neutral_skeleton_hash"), expected_json
        ):
            raise ValueError("canonical skeleton hash changed")
        if (
            type(self._construction_snapshot) is not str
            or self._construction_snapshot
            != _canonical_json(self._payload_unchecked())
        ):
            raise ValueError("skeleton canonicalization changed after construction")

    def to_dict(self) -> Dict[str, Any]:
        self._assert_unchanged()
        return self._payload_unchecked()


@dataclass(frozen=True, init=False)
class UniverseDescriptor:
    """Finite slice-1 counts, histograms, roots, and its descriptor seal."""

    universe_version: int
    counts: Tuple[Tuple[str, int], ...]
    histograms: Tuple[Tuple[str, Tuple[Tuple[str, int], ...]], ...]
    roots: Tuple[Tuple[str, str], ...]
    endpoints: Tuple[Tuple[str, str, str], ...]
    descriptor_root: str
    _construction_snapshot: str

    def __init__(
        self,
        universe_version: int,
        counts: Tuple[Tuple[str, int], ...],
        histograms: Tuple[Tuple[str, Tuple[Tuple[str, int], ...]], ...],
        roots: Tuple[Tuple[str, str], ...],
        endpoints: Tuple[Tuple[str, str, str], ...],
        descriptor_root: str,
    ) -> None:
        if type(universe_version) is not int:
            raise TypeError("descriptor version must be an exact integer")
        if universe_version != _official_universe_version():
            raise ValueError("descriptor version is not supported")
        _validate_named_counts(counts, "descriptor counts")
        if type(histograms) is not tuple:
            raise TypeError("descriptor histograms must be a canonical tuple")
        histogram_names = []
        detached_histograms = []
        for entry in histograms:
            if type(entry) is not tuple or len(entry) != 2:
                raise TypeError("descriptor histogram entries must be canonical pairs")
            name, entries = entry
            if type(name) is not str:
                raise TypeError("descriptor histogram names must be exact strings")
            histogram_names.append(name)
            _validate_named_counts(entries, "descriptor histogram {}".format(name))
            detached_histograms.append((name, tuple(entries)))
        if histogram_names != sorted(histogram_names) or len(set(histogram_names)) != len(
            histogram_names
        ):
            raise ValueError("descriptor histograms must have unique sorted names")
        if type(roots) is not tuple:
            raise TypeError("descriptor roots must be a canonical tuple")
        root_names = []
        detached_roots = []
        for entry in roots:
            if type(entry) is not tuple or len(entry) != 2:
                raise TypeError("descriptor root entries must be canonical pairs")
            name, digest = entry
            if type(name) is not str or not _is_lower_sha256(digest):
                raise ValueError("descriptor roots must be named SHA-256 digests")
            root_names.append(name)
            detached_roots.append((name, digest))
        if root_names != sorted(root_names) or len(set(root_names)) != len(root_names):
            raise ValueError("descriptor roots must have unique sorted names")
        if type(endpoints) is not tuple:
            raise TypeError("descriptor endpoints must be a canonical tuple")
        endpoint_names = []
        detached_endpoints = []
        for entry in endpoints:
            if type(entry) is not tuple or len(entry) != 3:
                raise TypeError("descriptor endpoint entries must be canonical triples")
            name, first, last = entry
            if any(type(value) is not str for value in entry):
                raise TypeError("descriptor endpoints must contain exact strings")
            if not first or not last:
                raise ValueError("descriptor endpoints cannot be empty")
            endpoint_names.append(name)
            detached_endpoints.append((name, first, last))
        if endpoint_names != sorted(endpoint_names) or len(set(endpoint_names)) != len(
            endpoint_names
        ):
            raise ValueError("descriptor endpoints must have unique sorted names")
        if endpoint_names != root_names:
            raise ValueError("descriptor endpoints must cover every ordered root")
        if not _is_lower_sha256(descriptor_root):
            raise ValueError("descriptor root must be a SHA-256 hex digest")
        detached_counts = tuple((name, count) for name, count in counts)
        detached_histogram_tuple = tuple(detached_histograms)
        detached_root_tuple = tuple(detached_roots)
        detached_endpoint_tuple = tuple(detached_endpoints)
        object.__setattr__(self, "universe_version", universe_version)
        object.__setattr__(self, "counts", detached_counts)
        object.__setattr__(self, "histograms", detached_histogram_tuple)
        object.__setattr__(self, "roots", detached_root_tuple)
        object.__setattr__(self, "endpoints", detached_endpoint_tuple)
        object.__setattr__(self, "descriptor_root", descriptor_root)
        if descriptor_root != _hash(
            _hash_domain("descriptor_root"),
            _canonical_json(self._payload_unchecked()),
        ):
            raise ValueError("descriptor root does not seal its payload")
        _require_official_descriptor(self)
        object.__setattr__(
            self, "_construction_snapshot", _canonical_json(self._dict_unchecked())
        )

    def _payload_unchecked(self) -> Dict[str, Any]:
        return {
            "universe_version": self.universe_version,
            "counts": {name: count for name, count in self.counts},
            "histograms": {
                name: {key: count for key, count in entries}
                for name, entries in self.histograms
            },
            "roots": {name: digest for name, digest in self.roots},
            "endpoints": {
                name: {"first": first, "last": last}
                for name, first, last in self.endpoints
            },
        }

    def _dict_unchecked(self) -> Dict[str, Any]:
        value = self._payload_unchecked()
        value["descriptor_root"] = self.descriptor_root
        return value

    def _assert_unchanged(self) -> None:
        _require_exact_fields(
            self,
            (
                "universe_version",
                "counts",
                "histograms",
                "roots",
                "endpoints",
                "descriptor_root",
                "_construction_snapshot",
            ),
            "universe descriptor",
        )
        if (
            type(self.universe_version) is not int
            or self.universe_version != _official_universe_version()
        ):
            raise ValueError("descriptor version changed after construction")
        _validate_named_counts(self.counts, "descriptor counts")
        if type(self.histograms) is not tuple:
            raise TypeError("descriptor histograms changed type")
        histogram_names = []
        for entry in self.histograms:
            if type(entry) is not tuple or len(entry) != 2:
                raise TypeError("descriptor histogram entries changed type")
            name, entries = entry
            if type(name) is not str:
                raise TypeError("descriptor histogram names changed type")
            histogram_names.append(name)
            _validate_named_counts(entries, "descriptor histogram {}".format(name))
        if histogram_names != sorted(histogram_names) or len(
            set(histogram_names)
        ) != len(histogram_names):
            raise ValueError("descriptor histogram names changed order or uniqueness")
        if type(self.roots) is not tuple:
            raise TypeError("descriptor roots changed type")
        root_names = []
        for entry in self.roots:
            if type(entry) is not tuple or len(entry) != 2:
                raise TypeError("descriptor root entries changed type")
            name, digest = entry
            if type(name) is not str or not _is_lower_sha256(digest):
                raise TypeError("descriptor roots changed type or format")
            root_names.append(name)
        if root_names != sorted(root_names) or len(set(root_names)) != len(root_names):
            raise ValueError("descriptor root names changed order or uniqueness")
        if type(self.endpoints) is not tuple:
            raise TypeError("descriptor endpoints changed type")
        endpoint_names = []
        for entry in self.endpoints:
            if (
                type(entry) is not tuple
                or len(entry) != 3
                or any(type(value) is not str or not value for value in entry)
            ):
                raise TypeError("descriptor endpoints changed type or format")
            endpoint_names.append(entry[0])
        if endpoint_names != sorted(endpoint_names) or len(
            set(endpoint_names)
        ) != len(endpoint_names):
            raise ValueError("descriptor endpoint names changed order or uniqueness")
        if endpoint_names != root_names:
            raise ValueError("descriptor endpoint/root coverage changed")
        if not _is_lower_sha256(self.descriptor_root):
            raise ValueError("descriptor root changed type or format")
        if self.descriptor_root != _hash(
            _hash_domain("descriptor_root"),
            _canonical_json(self._payload_unchecked()),
        ):
            raise ValueError("descriptor root no longer seals its payload")
        _require_official_descriptor(self)
        if (
            type(self._construction_snapshot) is not str
            or self._construction_snapshot != _canonical_json(self._dict_unchecked())
        ):
            raise ValueError("universe descriptor changed after construction")

    def payload_dict(self) -> Dict[str, Any]:
        self._assert_unchanged()
        return self._payload_unchecked()

    def to_dict(self) -> Dict[str, Any]:
        self._assert_unchanged()
        return self._dict_unchecked()


def _validate_named_counts(value: Any, label: str) -> None:
    if type(value) is not tuple:
        raise TypeError("{} must be a canonical tuple".format(label))
    names = []
    for entry in value:
        if type(entry) is not tuple or len(entry) != 2:
            raise TypeError("{} entries must be canonical pairs".format(label))
        name, count = entry
        if type(name) is not str or type(count) is not int or count < 0:
            raise TypeError("{} entries require an exact string and integer".format(label))
        names.append(name)
    if names != sorted(names) or len(set(names)) != len(names):
        raise ValueError("{} names must be unique and sorted".format(label))


def _clone_role_signature_unchecked(signature: RoleSignature) -> RoleSignature:
    clone = object.__new__(RoleSignature)
    object.__setattr__(clone, "action_primitive", signature.action_primitive)
    object.__setattr__(clone, "goal_primitive", signature.goal_primitive)
    object.__setattr__(
        clone,
        "_construction_snapshot",
        (
            _fixed_action_value(signature.action_primitive),
            _fixed_goal_value(signature.goal_primitive),
        ),
    )
    return clone


def _make_goal_target_unchecked(
    goal_primitive: GoalPrimitive, edges: Iterable[BoardEdge]
) -> GoalTarget:
    target = object.__new__(GoalTarget)
    object.__setattr__(target, "goal_primitive", goal_primitive)
    object.__setattr__(target, "edges", tuple(edges))
    object.__setattr__(
        target,
        "_construction_snapshot",
        _canonical_json(target._payload_unchecked()),
    )
    return target


def _clone_goal_target_unchecked(target: GoalTarget) -> GoalTarget:
    return _make_goal_target_unchecked(target.goal_primitive, target.edges)


def _make_goal_frame_unchecked(
    role_a: GoalTarget, role_b: GoalTarget
) -> GoalFrame:
    frame = object.__new__(GoalFrame)
    object.__setattr__(frame, "role_a", _clone_goal_target_unchecked(role_a))
    object.__setattr__(frame, "role_b", _clone_goal_target_unchecked(role_b))
    object.__setattr__(
        frame,
        "_construction_snapshot",
        _canonical_json(frame._payload_unchecked()),
    )
    return frame


def _make_profiled_role_unchecked(
    signature: RoleSignature,
    vector_profile: VectorProfile,
    goal_target: GoalTarget,
) -> ProfiledRole:
    role = object.__new__(ProfiledRole)
    object.__setattr__(
        role, "signature", _clone_role_signature_unchecked(signature)
    )
    object.__setattr__(role, "vector_profile", vector_profile)
    object.__setattr__(
        role, "goal_target", _clone_goal_target_unchecked(goal_target)
    )
    object.__setattr__(
        role,
        "_construction_snapshot",
        _canonical_json(role._payload_unchecked()),
    )
    return role


def _make_profiled_skeleton_unchecked(
    universe_version: int, role_a: ProfiledRole, role_b: ProfiledRole
) -> ProfiledSkeleton:
    skeleton = object.__new__(ProfiledSkeleton)
    object.__setattr__(skeleton, "universe_version", universe_version)
    object.__setattr__(
        skeleton,
        "role_a",
        _make_profiled_role_unchecked(
            role_a.signature, role_a.vector_profile, role_a.goal_target
        ),
    )
    object.__setattr__(
        skeleton,
        "role_b",
        _make_profiled_role_unchecked(
            role_b.signature, role_b.vector_profile, role_b.goal_target
        ),
    )
    object.__setattr__(
        skeleton,
        "_construction_snapshot",
        _canonical_json(skeleton._payload_unchecked()),
    )
    return skeleton


def _normalize_axis(edges: Iterable[BoardEdge]) -> Tuple[BoardEdge, ...]:
    edge_set = frozenset(edges)
    for axis in _connect_axes():
        if edge_set == frozenset(axis):
            return axis
    raise ValueError("transformed CONNECT_EDGES target is not an axis")


def _transform_vector(vector: Vector, transform: D4Transform) -> Vector:
    row_delta, column_delta = vector
    return {
        D4Transform.I: (row_delta, column_delta),
        D4Transform.R90: (column_delta, -row_delta),
        D4Transform.R180: (-row_delta, -column_delta),
        D4Transform.R270: (-column_delta, row_delta),
        D4Transform.FLR: (row_delta, -column_delta),
        D4Transform.FTB: (-row_delta, column_delta),
        D4Transform.FD: (column_delta, row_delta),
        D4Transform.FA: (-column_delta, -row_delta),
    }[transform]


def _transform_goal_target_unchecked(
    target: GoalTarget, transform: D4Transform
) -> GoalTarget:
    mapped = tuple(_transform_edge(edge, transform) for edge in target.edges)
    if target.goal_primitive is GoalPrimitive.CONNECT_EDGES:
        mapped = _normalize_axis(mapped)
    elif target.goal_primitive is GoalPrimitive.REACH_EDGE:
        mapped = (mapped[0],)
    else:
        mapped = ()
    return _make_goal_target_unchecked(target.goal_primitive, mapped)


def _transform_goal_frame_unchecked(
    frame: GoalFrame, transform: D4Transform
) -> GoalFrame:
    return _make_goal_frame_unchecked(
        _transform_goal_target_unchecked(frame.role_a, transform),
        _transform_goal_target_unchecked(frame.role_b, transform),
    )


def _swap_goal_frame_unchecked(frame: GoalFrame) -> GoalFrame:
    return _make_goal_frame_unchecked(frame.role_b, frame.role_a)


def _goal_frame_json_unchecked(frame: GoalFrame) -> str:
    return _canonical_json(frame._payload_unchecked())


def _normalize_goal_target(target: Any, label: str) -> GoalTarget:
    if type(target) is not GoalTarget:
        raise TypeError("{} must be a GoalTarget".format(label))
    target._assert_unchanged()
    return GoalTarget(target.goal_primitive, tuple(target.edges))


def _normalize_goal_frame(frame: Any) -> GoalFrame:
    if type(frame) is not GoalFrame:
        raise TypeError("goal frame must be a GoalFrame")
    frame._assert_unchanged()
    return GoalFrame(
        _normalize_goal_target(frame.role_a, "goal frame role A"),
        _normalize_goal_target(frame.role_b, "goal frame role B"),
    )


def transform_goal_frame(frame: GoalFrame, transform: D4Transform) -> GoalFrame:
    """Transform both ordered targets without swapping their role ownership."""

    normalized = _normalize_goal_frame(frame)
    _require_exact_enum(transform, D4Transform, "goal-frame transform")
    return _transform_goal_frame_unchecked(normalized, transform)


def role_swap_goal_frame(frame: GoalFrame) -> GoalFrame:
    """Exchange both complete goal targets."""

    return _swap_goal_frame_unchecked(_normalize_goal_frame(frame))


def _canonical_goal_frame_d4(frame: GoalFrame) -> GoalFrame:
    options = (
        _transform_goal_frame_unchecked(frame, transform)
        for transform in _fixed_enum_members(D4Transform, "D4 vocabulary")
    )
    return min(options, key=_goal_frame_json_unchecked)


def _canonical_goal_frame_role_neutral(frame: GoalFrame) -> GoalFrame:
    options = []
    for role_swapped in (False, True):
        base = _swap_goal_frame_unchecked(frame) if role_swapped else frame
        options.extend(
            _transform_goal_frame_unchecked(base, transform)
            for transform in _fixed_enum_members(D4Transform, "D4 vocabulary")
        )
    return min(options, key=_goal_frame_json_unchecked)


def _classify_goal_frame(frame: GoalFrame) -> GoalFrameKind:
    goal_a = frame.role_a.goal_primitive
    goal_b = frame.role_b.goal_primitive
    if goal_a is GoalPrimitive.CONNECT_EDGES:
        if goal_b is GoalPrimitive.CONNECT_EDGES:
            if frame.role_a.edges == frame.role_b.edges:
                return GoalFrameKind.CONNECT_CONNECT_SAME_AXIS
            return GoalFrameKind.CONNECT_CONNECT_PERPENDICULAR
        if goal_b is GoalPrimitive.REACH_EDGE:
            if frame.role_b.edges[0] in frame.role_a.edges:
                return GoalFrameKind.CONNECT_REACH_ALIGNED
            return GoalFrameKind.CONNECT_REACH_PERPENDICULAR
        return GoalFrameKind.CONNECT_ELIMINATE
    if goal_a is GoalPrimitive.REACH_EDGE:
        if goal_b is GoalPrimitive.CONNECT_EDGES:
            if frame.role_a.edges[0] in frame.role_b.edges:
                return GoalFrameKind.REACH_CONNECT_ALIGNED
            return GoalFrameKind.REACH_CONNECT_PERPENDICULAR
        if goal_b is GoalPrimitive.REACH_EDGE:
            edge_a = frame.role_a.edges[0]
            edge_b = frame.role_b.edges[0]
            if edge_a is edge_b:
                return GoalFrameKind.REACH_REACH_SAME
            if _opposite_edge(edge_a) is edge_b:
                return GoalFrameKind.REACH_REACH_OPPOSITE
            return GoalFrameKind.REACH_REACH_ADJACENT
        return GoalFrameKind.REACH_ELIMINATE
    if goal_b is GoalPrimitive.CONNECT_EDGES:
        return GoalFrameKind.ELIMINATE_CONNECT
    if goal_b is GoalPrimitive.REACH_EDGE:
        return GoalFrameKind.ELIMINATE_REACH
    return GoalFrameKind.ELIMINATE_ELIMINATE


def _goal_targets(goal: GoalPrimitive) -> Tuple[GoalTarget, ...]:
    if goal is GoalPrimitive.CONNECT_EDGES:
        return tuple(GoalTarget(goal, axis) for axis in _connect_axes())
    if goal is GoalPrimitive.REACH_EDGE:
        return tuple(
            GoalTarget(goal, (edge,))
            for edge in _fixed_enum_members(BoardEdge, "board-edge vocabulary")
        )
    if goal is GoalPrimitive.ELIMINATE:
        return (GoalTarget(goal, ()),)
    raise AssertionError("closed goal primitive was not handled")


def enumerate_raw_goal_frames() -> Tuple[GoalFrame, ...]:
    """Return all 49 ordered target pairs before the D4 quotient."""

    return tuple(
        GoalFrame(target_a, target_b)
        for goal_a, goal_b in product(
            _fixed_enum_members(GoalPrimitive, "goal vocabulary"), repeat=2
        )
        for target_a, target_b in product(
            _goal_targets(goal_a), _goal_targets(goal_b)
        )
    )


def enumerate_goal_frames() -> Tuple[GoalFrame, ...]:
    """Reconstruct all 14 ordered D4 goal-frame orbits from 49 raw pairs."""

    by_kind: Dict[GoalFrameKind, Dict[str, GoalFrame]] = {}
    for raw_frame in enumerate_raw_goal_frames():
        canonical = _canonical_goal_frame_d4(raw_frame)
        by_kind.setdefault(canonical.kind, {})[
            _goal_frame_json_unchecked(canonical)
        ] = canonical
    kinds = _fixed_enum_members(GoalFrameKind, "goal-frame-kind vocabulary")
    if set(by_kind) != set(kinds):
        raise UniverseClosureError("ordered goal-frame vocabulary is incomplete")
    if any(len(options) != 1 for options in by_kind.values()):
        raise UniverseClosureError("goal-frame relation labels alias D4 orbits")
    return tuple(next(iter(by_kind[kind].values())) for kind in kinds)


def enumerate_role_neutral_goal_frames() -> Tuple[GoalFrame, ...]:
    """Return the 10 goal-frame classes after complete role swap."""

    representatives: Dict[str, GoalFrame] = {}
    for frame in enumerate_goal_frames():
        canonical = _canonical_goal_frame_role_neutral(frame)
        representatives[_goal_frame_json_unchecked(canonical)] = canonical
    return tuple(representatives[key] for key in sorted(representatives))


def goal_frame_d4_stabilizer_size(frame: GoalFrame) -> int:
    """Count D4 elements that fix one exact ordered goal frame."""

    normalized = _normalize_goal_frame(frame)
    return sum(
        _transform_goal_frame_unchecked(normalized, transform) == normalized
        for transform in _fixed_enum_members(D4Transform, "D4 vocabulary")
    )


def enumerate_d4_invariant_vector_sets() -> Tuple[Tuple[Vector, ...], ...]:
    """Exhaust the 255 nonempty Moore subsets and retain the D4 invariants."""

    vectors = _moore_vectors()
    transforms = _fixed_enum_members(D4Transform, "D4 vocabulary")
    invariant = []
    for mask in range(1, 1 << len(vectors)):
        vector_set = frozenset(
            vector
            for index, vector in enumerate(vectors)
            if mask & (1 << index)
        )
        if all(
            frozenset(_transform_vector(vector, transform) for vector in vector_set)
            == vector_set
            for transform in transforms
        ):
            invariant.append(
                tuple(vector for vector in vectors if vector in vector_set)
            )
    return tuple(sorted(invariant, key=lambda vectors: (len(vectors), vectors)))


def enumerate_movement_vector_profiles() -> Tuple[VectorProfile, ...]:
    """Name the complete nonempty D4-invariant Moore subset vocabulary."""

    all_profiles = _fixed_enum_members(VectorProfile, "vector-profile vocabulary")
    profiles = (
        VectorProfile.ORTHOGONAL_4,
        VectorProfile.DIAGONAL_4,
        VectorProfile.KING_8,
    )
    if all_profiles != (VectorProfile.NONE,) + profiles:
        raise UniverseClosureError("vector-profile vocabulary changed")
    derived_sets = {frozenset(vectors) for vectors in enumerate_d4_invariant_vector_sets()}
    named_sets = {_fixed_profile_vector_set(profile) for profile in profiles}
    if derived_sets != named_sets:
        raise UniverseClosureError("named vector profiles do not close the Moore quotient")
    return profiles


def vector_profile_vectors(profile: VectorProfile) -> Tuple[Vector, ...]:
    """Return the canonical vectors represented by one movement profile."""

    _require_exact_enum(profile, VectorProfile, "vector profile")
    if profile is VectorProfile.NONE:
        return ()
    vector_set = _fixed_profile_vector_set(profile)
    return tuple(vector for vector in _moore_vectors() if vector in vector_set)


def _coherent_goals(action: ActionPrimitive) -> Tuple[GoalPrimitive, ...]:
    goals = list(_spatial_goals())
    if _is_material_reducing_action(action):
        goals.append(GoalPrimitive.ELIMINATE)
    return tuple(goals)


def enumerate_role_atoms() -> Tuple[RoleSignature, ...]:
    """Enumerate the 16 coherent role atoms from the sealed pure vocabulary."""

    actions = _active_actions()
    _fixed_enum_members(GoalPrimitive, "goal vocabulary")
    if tuple(action.value for action in actions) != (
        "PLACE",
        "MOVE",
        "MOVE_CAPTURE",
        "PUSH",
        "SWAP",
        "HOP",
        "CONVERT",
    ):
        raise UniverseClosureError("active action vocabulary changed")
    return tuple(
        RoleSignature(action, goal)
        for action in actions
        for goal in _coherent_goals(action)
    )


def _normalize_semantic_signature(signature: Any) -> SemanticSignature:
    if type(signature) is not SemanticSignature:
        raise TypeError("semantic signature must be a SemanticSignature")
    signature._assert_unchanged()
    parsed = parse_semantic_signature(signature.to_dict())
    if parsed != signature:
        raise ValueError("semantic signature is not parser-normalized")
    return parsed


def parse_semantic_signature(value: Any) -> SemanticSignature:
    """Strictly parse one JSON-compatible ordered semantic signature."""

    signature = _exact_dict(value, "semantic signature")
    _exact_keys(signature, ("universe_version", "roles"), "semantic signature")
    version = signature["universe_version"]
    if type(version) is not int:
        raise TypeError("semantic signature version must be an exact integer")
    roles = _exact_dict(signature["roles"], "semantic signature roles")
    _exact_keys(roles, ("A", "B"), "semantic signature roles")
    return SemanticSignature(
        universe_version=version,
        role_a=_parse_role(roles["A"], "semantic role A"),
        role_b=_parse_role(roles["B"], "semantic role B"),
    )


def canonical_semantic_signature_json(signature: SemanticSignature) -> str:
    """Serialize one exact ordered signature after strict revalidation."""

    return _canonical_json(_normalize_semantic_signature(signature).to_dict())


def semantic_signature_hash(signature: SemanticSignature) -> str:
    """Hash one orientation-sensitive A/B semantic signature."""

    return _hash(
        _hash_domain("semantic_hash"),
        canonical_semantic_signature_json(signature),
    )


def role_swap_semantic_signature(signature: SemanticSignature) -> SemanticSignature:
    """Exchange the complete role atoms of an ordered signature."""

    normalized = _normalize_semantic_signature(signature)
    return SemanticSignature(
        normalized.universe_version, normalized.role_b, normalized.role_a
    )


def _role_neutral_semantic_choice(signature: SemanticSignature) -> SemanticSignature:
    swapped = SemanticSignature(
        signature.universe_version, signature.role_b, signature.role_a
    )
    return min(
        (signature, swapped), key=lambda item: _canonical_json(item.to_dict())
    )


def canonical_role_neutral_semantic_json(signature: SemanticSignature) -> str:
    """Serialize the bytewise minimum of an ordered signature and its swap."""

    normalized = _normalize_semantic_signature(signature)
    return _canonical_json(_role_neutral_semantic_choice(normalized).to_dict())


def role_neutral_semantic_hash(signature: SemanticSignature) -> str:
    """Hash a complete role-swap semantic class under a separate domain."""

    return _hash(
        _hash_domain("role_neutral_semantic_hash"),
        canonical_role_neutral_semantic_json(signature),
    )


def _schema_v4_admitted_unchecked(signature: SemanticSignature) -> bool:
    return any(
        _is_schema_v4_action(role.action_primitive)
        for role in signature.roles
    ) or any(
        role.goal_primitive is GoalPrimitive.ELIMINATE
        for role in signature.roles
    )


def schema_v4_admitted_signature(signature: SemanticSignature) -> bool:
    """Apply the frozen v4 feature-admission rule without compiling a game."""

    return _schema_v4_admitted_unchecked(_normalize_semantic_signature(signature))


def enumerate_ordered_semantic_signatures() -> Tuple[SemanticSignature, ...]:
    """Return all 256 coherent ordered role-atom pairs."""

    atoms = enumerate_role_atoms()
    return tuple(
        SemanticSignature(_official_universe_version(), role_a, role_b)
        for role_a, role_b in product(atoms, repeat=2)
    )


def enumerate_admitted_semantic_signatures() -> Tuple[SemanticSignature, ...]:
    """Return the 220 pairs admitted as schema-v4 programs."""

    admitted = tuple(
        signature
        for signature in enumerate_ordered_semantic_signatures()
        if _schema_v4_admitted_unchecked(signature)
    )
    return tuple(sorted(admitted, key=lambda item: _canonical_json(item.to_dict())))


def enumerate_role_neutral_semantic_classes() -> Tuple[SemanticSignature, ...]:
    """Return the 115 admitted role-neutral semantic representatives."""

    representatives: Dict[str, SemanticSignature] = {}
    for signature in enumerate_admitted_semantic_signatures():
        canonical = _role_neutral_semantic_choice(signature)
        representatives[_canonical_json(canonical.to_dict())] = canonical
    return tuple(representatives[key] for key in sorted(representatives))


def _plan0013_semantic_specs() -> Tuple[Tuple[str, str, str, str], ...]:
    return (
        ("PUSH", "REACH_EDGE", "HOP", "REACH_EDGE"),
        ("SWAP", "CONNECT_EDGES", "HOP", "REACH_EDGE"),
        ("CONVERT", "CONNECT_EDGES", "PUSH", "REACH_EDGE"),
        ("MOVE_CAPTURE", "ELIMINATE", "HOP", "REACH_EDGE"),
        ("CONVERT", "ELIMINATE", "MOVE_CAPTURE", "ELIMINATE"),
        ("PUSH", "CONNECT_EDGES", "SWAP", "CONNECT_EDGES"),
    )


def enumerate_plan0013_semantic_classes() -> Tuple[SemanticSignature, ...]:
    """Rebuild the six public old-region classes without candidate access."""

    classes = []
    specs = _plan0013_semantic_specs()
    for action_a, goal_a, action_b, goal_b in specs:
        source = SemanticSignature(
            _official_universe_version(),
            RoleSignature(
                _enum_from_exact_string(
                    ActionPrimitive, action_a, "old role A action"
                ),
                _enum_from_exact_string(GoalPrimitive, goal_a, "old role A goal"),
            ),
            RoleSignature(
                _enum_from_exact_string(
                    ActionPrimitive, action_b, "old role B action"
                ),
                _enum_from_exact_string(GoalPrimitive, goal_b, "old role B goal"),
            ),
        )
        classes.append(_role_neutral_semantic_choice(source))
    unique = {
        _canonical_json(signature.to_dict()): signature for signature in classes
    }
    if len(unique) != len(specs):
        raise UniverseClosureError("old semantic regions alias one another")
    return tuple(unique[key] for key in sorted(unique))


def _old_semantic_keys() -> frozenset:
    return frozenset(
        _canonical_json(signature.to_dict())
        for signature in enumerate_plan0013_semantic_classes()
    )


def is_plan0013_semantic_region(signature: SemanticSignature) -> bool:
    """Test membership in the six old classes including reverse-role images."""

    normalized = _normalize_semantic_signature(signature)
    canonical = _role_neutral_semantic_choice(normalized)
    return _canonical_json(canonical.to_dict()) in _old_semantic_keys()


def enumerate_fresh_semantic_classes() -> Tuple[SemanticSignature, ...]:
    """Return all 109 admitted semantic classes outside the old-six firewall."""

    old = _old_semantic_keys()
    return tuple(
        signature
        for signature in enumerate_role_neutral_semantic_classes()
        if _canonical_json(signature.to_dict()) not in old
    )


def _parse_profiled_role(value: Any, label: str) -> ProfiledRole:
    role = _exact_dict(value, label)
    _exact_keys(
        role,
        (
            "action_primitive",
            "goal_primitive",
            "vector_profile",
            "target_edges",
        ),
        label,
    )
    signature = _parse_role(
        {
            "action_primitive": role["action_primitive"],
            "goal_primitive": role["goal_primitive"],
        },
        label,
    )
    profile = _enum_from_exact_string(
        VectorProfile, role["vector_profile"], label + ".vector_profile"
    )
    edges_value = role["target_edges"]
    if type(edges_value) is not list:
        raise TypeError("{}.target_edges must be an exact array".format(label))
    edges = tuple(
        _enum_from_exact_string(BoardEdge, edge, label + ".target_edges[]")
        for edge in edges_value
    )
    target = GoalTarget(signature.goal_primitive, edges)
    return ProfiledRole(signature, profile, target)


def parse_profiled_skeleton(value: Any) -> ProfiledSkeleton:
    """Strictly parse one JSON-compatible profiled skeleton."""

    skeleton = _exact_dict(value, "profiled skeleton")
    _exact_keys(skeleton, ("universe_version", "roles"), "profiled skeleton")
    version = skeleton["universe_version"]
    if type(version) is not int:
        raise TypeError("profiled skeleton version must be an exact integer")
    roles = _exact_dict(skeleton["roles"], "profiled skeleton roles")
    _exact_keys(roles, ("A", "B"), "profiled skeleton roles")
    return ProfiledSkeleton(
        universe_version=version,
        role_a=_parse_profiled_role(roles["A"], "profiled role A"),
        role_b=_parse_profiled_role(roles["B"], "profiled role B"),
    )


def _normalize_profiled_role(role: Any, label: str) -> ProfiledRole:
    if type(role) is not ProfiledRole:
        raise TypeError("{} must be a ProfiledRole".format(label))
    role._assert_unchanged()
    return _parse_profiled_role(role.to_dict(), label)


def _normalize_skeleton(skeleton: Any) -> ProfiledSkeleton:
    if type(skeleton) is not ProfiledSkeleton:
        raise TypeError("profiled skeleton must be a ProfiledSkeleton")
    skeleton._assert_unchanged()
    normalized_role_a = _normalize_profiled_role(skeleton.role_a, "profiled role A")
    normalized_role_b = _normalize_profiled_role(skeleton.role_b, "profiled role B")
    parsed = ProfiledSkeleton(
        skeleton.universe_version, normalized_role_a, normalized_role_b
    )
    if parsed != skeleton:
        raise ValueError("profiled skeleton is not parser-normalized")
    return parsed


def _skeleton_json_unchecked(skeleton: ProfiledSkeleton) -> str:
    return _canonical_json(skeleton._payload_unchecked())


def canonical_profiled_skeleton_json(skeleton: ProfiledSkeleton) -> str:
    """Serialize one exact ordered/oriented skeleton after strict revalidation."""

    return _skeleton_json_unchecked(_normalize_skeleton(skeleton))


def profiled_skeleton_hash(skeleton: ProfiledSkeleton) -> str:
    """Hash one exact ordered/oriented skeleton."""

    return _hash(
        _hash_domain("skeleton_hash"),
        canonical_profiled_skeleton_json(skeleton),
    )


def _transform_profiled_role_unchecked(
    role: ProfiledRole, transform: D4Transform
) -> ProfiledRole:
    return _make_profiled_role_unchecked(
        role.signature,
        role.vector_profile,
        _transform_goal_target_unchecked(role.goal_target, transform),
    )


def _transform_skeleton_unchecked(
    skeleton: ProfiledSkeleton, transform: D4Transform
) -> ProfiledSkeleton:
    return _make_profiled_skeleton_unchecked(
        skeleton.universe_version,
        _transform_profiled_role_unchecked(skeleton.role_a, transform),
        _transform_profiled_role_unchecked(skeleton.role_b, transform),
    )


def _role_swap_skeleton_unchecked(skeleton: ProfiledSkeleton) -> ProfiledSkeleton:
    return _make_profiled_skeleton_unchecked(
        skeleton.universe_version, skeleton.role_b, skeleton.role_a
    )


def transform_profiled_skeleton(
    skeleton: ProfiledSkeleton, transform: D4Transform
) -> ProfiledSkeleton:
    """Apply one D4 transform while retaining ordered role ownership."""

    normalized = _normalize_skeleton(skeleton)
    _require_exact_enum(transform, D4Transform, "skeleton transform")
    return _transform_skeleton_unchecked(normalized, transform)


def role_swap_profiled_skeleton(skeleton: ProfiledSkeleton) -> ProfiledSkeleton:
    """Exchange actions, goals, targets, and vector profiles together."""

    return _role_swap_skeleton_unchecked(_normalize_skeleton(skeleton))


def _canonical_skeleton_choice(
    source: ProfiledSkeleton,
) -> Tuple[ProfiledSkeleton, D4Transform, bool, str]:
    selected: Any = None
    for role_swapped in (False, True):
        base = _role_swap_skeleton_unchecked(source) if role_swapped else source
        for transform in _fixed_enum_members(D4Transform, "D4 vocabulary"):
            option = _transform_skeleton_unchecked(base, transform)
            option_json = _skeleton_json_unchecked(option)
            # Strict comparison preserves the declared non-swap/swap and D4
            # iteration order as the deterministic witness tie break.
            record = (option_json, option, transform, role_swapped)
            if selected is None or option_json < selected[0]:
                selected = record
    assert selected is not None
    option_json, option, transform, role_swapped = selected
    return option, transform, role_swapped, option_json


def canonicalize_profiled_skeleton(
    skeleton: ProfiledSkeleton,
) -> SkeletonCanonicalization:
    """Canonicalize over all 16 D4-plus-complete-role-swap images."""

    source = _normalize_skeleton(skeleton)
    canonical, transform, role_swapped, canonical_json = _canonical_skeleton_choice(
        source
    )
    witness = SkeletonOrbitWitness(
        source=source,
        canonical=canonical,
        transform=transform,
        inverse_transform=_inverse_transform(transform),
        role_swapped=role_swapped,
        source_goal_frame=source.goal_frame,
        source_vector_profiles=source.vector_profiles,
    )
    return SkeletonCanonicalization(
        canonical_hash=_hash(
            _hash_domain("role_neutral_skeleton_hash"), canonical_json
        ),
        canonical_json=canonical_json,
        witness=witness,
    )


def role_neutral_profiled_skeleton_hash(skeleton: ProfiledSkeleton) -> str:
    """Return the role-swap-plus-D4 identity under its own hash domain."""

    return canonicalize_profiled_skeleton(skeleton).canonical_hash


def _normalize_witness(witness: Any) -> SkeletonOrbitWitness:
    if type(witness) is not SkeletonOrbitWitness:
        raise TypeError("orbit witness must be a SkeletonOrbitWitness")
    witness._assert_unchanged()
    source = _normalize_skeleton(witness.source)
    canonical = _normalize_skeleton(witness.canonical)
    _require_exact_enum(witness.transform, D4Transform, "orbit witness transform")
    _require_exact_enum(
        witness.inverse_transform, D4Transform, "orbit witness inverse transform"
    )
    if type(witness.role_swapped) is not bool:
        raise TypeError("orbit witness role_swapped must be an exact boolean")
    source_frame = _normalize_goal_frame(witness.source_goal_frame)
    profiles = witness.source_vector_profiles
    if (
        type(profiles) is not tuple
        or len(profiles) != 2
        or any(type(profile) is not VectorProfile for profile in profiles)
    ):
        raise TypeError("orbit witness source vector profiles are not canonical")
    normalized = SkeletonOrbitWitness(
        source,
        canonical,
        witness.transform,
        witness.inverse_transform,
        witness.role_swapped,
        source_frame,
        tuple(profiles),
    )
    expected, transform, role_swapped, _canonical_json_value = (
        _canonical_skeleton_choice(source)
    )
    if (
        canonical != expected
        or witness.transform is not transform
        or witness.role_swapped is not role_swapped
    ):
        raise ValueError("orbit witness does not identify the canonical minimum")
    return normalized


def reconstruct_profiled_skeleton_source(
    witness: SkeletonOrbitWitness,
) -> ProfiledSkeleton:
    """Apply the registered inverse and recover the exact ordered source."""

    normalized = _normalize_witness(witness)
    restored = _transform_skeleton_unchecked(
        normalized.canonical, normalized.inverse_transform
    )
    if normalized.role_swapped:
        restored = _role_swap_skeleton_unchecked(restored)
    if restored != normalized.source:
        raise ValueError("orbit witness inverse does not reconstruct its source")
    return restored


def is_role_swap_d4_self_isomorphic(skeleton: ProfiledSkeleton) -> bool:
    """Whether swap(source) lies in source's *ordered* D4 orbit.

    Comparing role-neutral canonical hashes here would be tautological and mark
    every skeleton self-isomorphic.  The explicit ordered-orbit test preserves
    profile, role-program, and target differences.
    """

    source = _normalize_skeleton(skeleton)
    swapped = _role_swap_skeleton_unchecked(source)
    return any(
        _transform_skeleton_unchecked(swapped, transform) == source
        for transform in _fixed_enum_members(D4Transform, "D4 vocabulary")
    )


def profiled_skeleton_d4_stabilizer_size(skeleton: ProfiledSkeleton) -> int:
    """Count D4 elements that fix one exact ordered skeleton."""

    source = _normalize_skeleton(skeleton)
    return sum(
        _transform_skeleton_unchecked(source, transform) == source
        for transform in _fixed_enum_members(D4Transform, "D4 vocabulary")
    )


def _profiles_for_action(action: ActionPrimitive) -> Tuple[VectorProfile, ...]:
    if action is ActionPrimitive.PLACE:
        return (VectorProfile.NONE,)
    return enumerate_movement_vector_profiles()


def enumerate_admitted_profiled_skeletons() -> Tuple[ProfiledSkeleton, ...]:
    """Enumerate all 3,300 admitted ordered D4-quotient skeletons."""

    frames_by_goals: Dict[Tuple[GoalPrimitive, GoalPrimitive], List[GoalFrame]] = {}
    for frame in enumerate_goal_frames():
        key = (frame.role_a.goal_primitive, frame.role_b.goal_primitive)
        frames_by_goals.setdefault(key, []).append(frame)
    skeletons = []
    for signature in enumerate_admitted_semantic_signatures():
        key = (
            signature.role_a.goal_primitive,
            signature.role_b.goal_primitive,
        )
        for frame in frames_by_goals[key]:
            for profile_a, profile_b in product(
                _profiles_for_action(signature.role_a.action_primitive),
                _profiles_for_action(signature.role_b.action_primitive),
            ):
                skeletons.append(
                    ProfiledSkeleton(
                        _official_universe_version(),
                        ProfiledRole(signature.role_a, profile_a, frame.role_a),
                        ProfiledRole(signature.role_b, profile_b, frame.role_b),
                    )
                )
    return tuple(sorted(skeletons, key=_skeleton_json_unchecked))


def is_plan0013_profiled_region(skeleton: ProfiledSkeleton) -> bool:
    """Apply the old-six semantic firewall before any setup exists."""

    source = _normalize_skeleton(skeleton)
    return is_plan0013_semantic_region(source.semantic_signature)


def enumerate_self_isomorphic_profiled_skeletons() -> Tuple[ProfiledSkeleton, ...]:
    """Return the 66 setup-only-asymmetric skeletons."""

    return tuple(
        skeleton
        for skeleton in enumerate_admitted_profiled_skeletons()
        if is_role_swap_d4_self_isomorphic(skeleton)
    )


def enumerate_plan0013_profiled_region_closure() -> Tuple[ProfiledSkeleton, ...]:
    """Return all 198 ordered skeletons in the old-six swap closure."""

    return tuple(
        skeleton
        for skeleton in enumerate_admitted_profiled_skeletons()
        if is_plan0013_profiled_region(skeleton)
    )


def enumerate_fresh_canonical_profiled_skeletons() -> Tuple[ProfiledSkeleton, ...]:
    """Return the 1,518 fresh asymmetric role-neutral representatives."""

    representatives: Dict[str, ProfiledSkeleton] = {}
    for skeleton in enumerate_admitted_profiled_skeletons():
        if is_role_swap_d4_self_isomorphic(skeleton):
            continue
        if is_plan0013_profiled_region(skeleton):
            continue
        canonical, _transform, _swapped, canonical_json = (
            _canonical_skeleton_choice(skeleton)
        )
        representatives[canonical_json] = canonical
    return tuple(representatives[key] for key in sorted(representatives))


def _histogram(values: Iterable[Any]) -> Tuple[Tuple[str, int], ...]:
    counts: Dict[str, int] = {}
    for value in values:
        key = str(value)
        counts[key] = counts.get(key, 0) + 1
    return tuple(sorted(counts.items()))


def _named_counts(values: Dict[str, int]) -> Tuple[Tuple[str, int], ...]:
    return tuple(sorted(values.items()))


def _expected_counts() -> Dict[str, int]:
    return {
        "admitted_ordered_profiled_skeleton_count": 3300,
        "admitted_ordered_signature_count": 220,
        "fresh_canonical_skeleton_count": 1518,
        "fresh_semantic_class_count": 109,
        "legacy_rejected_ordered_signature_count": 36,
        "movement_vector_profile_count": 3,
        "old_region_ordered_skeleton_count": 198,
        "old_region_role_neutral_skeleton_count": 99,
        "old_semantic_class_count": 6,
        "ordered_goal_frame_count": 14,
        "ordered_semantic_product_count": 256,
        "role_atom_count": 16,
        "role_neutral_goal_frame_count": 10,
        "role_neutral_semantic_class_count": 115,
        "role_swap_fixed_signature_count": 10,
        "self_isomorphic_ordered_skeleton_count": 66,
    }


def _expected_histograms() -> Dict[str, Dict[str, int]]:
    return {
        "all_skeleton_d4_stabilizer": {
            "1": 312,
            "2": 2100,
            "4": 852,
            "8": 36,
        },
        "fresh_canonical_d4_stabilizer": {
            "1": 141,
            "2": 975,
            "4": 396,
            "8": 6,
        },
        "goal_frame_d4_stabilizer": {"1": 1, "2": 8, "4": 4, "8": 1},
        "old_region_d4_stabilizer": {
            "1": 18,
            "2": 126,
            "4": 36,
            "8": 18,
        },
        "role_atom_by_action": {
            "CONVERT": 3,
            "HOP": 2,
            "MOVE": 2,
            "MOVE_CAPTURE": 3,
            "PLACE": 2,
            "PUSH": 2,
            "SWAP": 2,
        },
        "role_atom_by_goal": {
            "CONNECT_EDGES": 7,
            "ELIMINATE": 2,
            "REACH_EDGE": 7,
        },
        "self_isomorphic_d4_stabilizer": {
            "1": 12,
            "2": 24,
            "4": 24,
            "8": 6,
        },
    }


def _expected_roots() -> Dict[str, str]:
    return {
        "admitted_signature_root": "1ac9fe901ca02b209915d717fa936cee11d6b9a3d8b081317fc134d0a9a141c4",
        "d4_definition_root": "b89efcb15a66b71a584ffae101716104c616aa3235e36eb3086bee02be4d464e",
        "fresh_canonical_skeleton_root": "ca02a2bbd844962fd83c7190eec69dea51877940ea6f0836c5a00338a3e9e190",
        "fresh_semantic_root": "d24dd0d6c2e5f923e5b6b758125f311e590d319c6e03069cc76d1a9ac001df91",
        "full_witness_mapping_root": "6095576351eb9c937efa3a14a03bd376b0ca11a102aac99922bb00895eb68389",
        "goal_frame_root": "5e5185604ea940301150e6144d3834619786318b76e49433eafef142327a4164",
        "old_region_ordered_skeleton_root": "6c678dffab9dbcdec4a21b2c8c8cef4a61e57a4ee21ae2a1906d5b574060fdc2",
        "old_region_role_neutral_skeleton_root": "a75aa32b576d1a8988bb8def141211877f53e5f2fda55e71e884eb70f9d45ff8",
        "old_semantic_root": "f2747aa13ed6419df0bbfda4110cadafb2c779cb3709420dfc2cb963fe6c4464",
        "ordered_profiled_skeleton_root": "3170c498af35c6f2b13bbdfc7297e3527160ae0cbc1fe602cbe3a89b2bae1d78",
        "ordered_semantic_signature_root": "e03dc3a28577649444b45c3f540ddbd8ea622a1df686b9069218db17083cc9e0",
        "raw_goal_frame_root": "47128e2a247272fc4bce152ebfb06a81b8df7d50544bd621d5ae79ca5a78a338",
        "role_atom_root": "f2286dfc7c0e1d4053612bf37e4e1bfc87c4d9b4ace616cc6007cf9df820e2b0",
        "role_neutral_goal_frame_root": "c6e806e6b9f1d50ac891931d5f1772bf4ad733bf370eaa009e8bb13e9b8146db",
        "role_neutral_semantic_root": "64704a4f9434167e26df82ed1222b42165e59ae5f1ec73c445eb9aa337ef0cf4",
        "self_isomorphic_ordered_skeleton_root": "7825bb7a70ee9d373d2a6971bd991bba5d60e8ce3f251a0a00f416d56cb8c539",
        "semantic_mapping_root": "7079e33bb347bfe0316c3b5c356fda9827ed9a557363016f3c01e6c04f1fe20b",
        "vector_profile_definition_root": "dc2c19b42ba6514fd16dd4e76b7c4c995f5b94c824defc19e6bf96c3cd17bb3f",
    }


def _official_descriptor_root() -> str:
    return "05826dc2da02890f3f562ee2d6febda523c58837affb757b5dff6d62c074e6ab"


def _vector_profile_definition_values() -> Tuple[str, ...]:
    return tuple(
        _canonical_json(
            {
                "profile": profile.value,
                "vectors": [
                    [row_delta, column_delta]
                    for row_delta, column_delta in vector_profile_vectors(profile)
                ],
            }
        )
        for profile in _fixed_enum_members(
            VectorProfile, "vector-profile vocabulary"
        )
    )


def _d4_definition_values() -> Tuple[str, ...]:
    return tuple(
        _canonical_json(
            {
                "transform": transform.value,
                "inverse_transform": _inverse_transform(transform).value,
                "edge_map": [
                    {
                        "source": edge.value,
                        "target": _transform_edge(edge, transform).value,
                    }
                    for edge in _fixed_enum_members(
                        BoardEdge, "board-edge vocabulary"
                    )
                ],
                "vector_map": [
                    {
                        "source": [vector[0], vector[1]],
                        "target": list(_transform_vector(vector, transform)),
                    }
                    for vector in _moore_vectors()
                ],
            }
        )
        for transform in _fixed_enum_members(D4Transform, "D4 vocabulary")
    )


def _semantic_mapping_values(
    signatures: Sequence[SemanticSignature],
) -> Tuple[str, ...]:
    return tuple(
        _canonical_json(
            {
                "ordered": signature._payload_unchecked(),
                "role_neutral": _role_neutral_semantic_choice(
                    signature
                )._payload_unchecked(),
            }
        )
        for signature in signatures
    )


def _full_witness_mapping_values(
    skeletons: Sequence[ProfiledSkeleton],
) -> Tuple[str, ...]:
    values = []
    for source in skeletons:
        canonical, transform, role_swapped, canonical_json = (
            _canonical_skeleton_choice(source)
        )
        inverse = _inverse_transform(transform)
        restored = _transform_skeleton_unchecked(canonical, inverse)
        if role_swapped:
            restored = _role_swap_skeleton_unchecked(restored)
        if restored != source:
            raise UniverseClosureError("full witness mapping failed its inverse")
        values.append(
            _canonical_json(
                {
                    "source": source._payload_unchecked(),
                    "source_hash": _hash(
                        _hash_domain("skeleton_hash"),
                        _skeleton_json_unchecked(source),
                    ),
                    "canonical": canonical._payload_unchecked(),
                    "canonical_hash": _hash(
                        _hash_domain("role_neutral_skeleton_hash"),
                        canonical_json,
                    ),
                    "transform": transform.value,
                    "inverse_transform": inverse.value,
                    "role_swapped": role_swapped,
                    "source_goal_frame": source.goal_frame._payload_unchecked(),
                    "source_goal_frame_kind": source.goal_frame.kind.value,
                    "source_vector_profiles": [
                        profile.value for profile in source.vector_profiles
                    ],
                }
            )
        )
    return tuple(values)


def _register_root(
    name: str,
    domain: bytes,
    values: Sequence[str],
    roots: Dict[str, str],
    endpoints: Dict[str, Tuple[str, str]],
) -> None:
    if type(values) is not tuple or not values:
        raise UniverseClosureError("ordered root {} must be a nonempty tuple".format(name))
    roots[name] = _sequence_root(domain, values)
    endpoints[name] = (values[0], values[-1])


def _descriptor_components() -> Tuple[
    Tuple[Tuple[str, int], ...],
    Tuple[Tuple[str, Tuple[Tuple[str, int], ...]], ...],
    Tuple[Tuple[str, str], ...],
    Tuple[Tuple[str, str, str], ...],
]:
    """Derive every descriptor component without constructing a self-seal."""

    atoms = enumerate_role_atoms()
    all_signatures = enumerate_ordered_semantic_signatures()
    admitted_signatures = enumerate_admitted_semantic_signatures()
    neutral_semantics = enumerate_role_neutral_semantic_classes()
    fresh_semantics = enumerate_fresh_semantic_classes()
    old_semantics = enumerate_plan0013_semantic_classes()
    raw_goal_frames = enumerate_raw_goal_frames()
    goal_frames = enumerate_goal_frames()
    neutral_goal_frames = enumerate_role_neutral_goal_frames()
    profiles = enumerate_movement_vector_profiles()
    ordered = enumerate_admitted_profiled_skeletons()
    self_isomorphic = tuple(
        skeleton
        for skeleton in ordered
        if is_role_swap_d4_self_isomorphic(skeleton)
    )
    old_region = tuple(
        skeleton for skeleton in ordered if is_plan0013_profiled_region(skeleton)
    )
    old_neutral_keys = {
        _canonical_skeleton_choice(skeleton)[3] for skeleton in old_region
    }
    old_neutral = tuple(
        parse_profiled_skeleton(json.loads(value))
        for value in sorted(old_neutral_keys)
    )
    fresh = enumerate_fresh_canonical_profiled_skeletons()

    counts = _named_counts(
        {
            "role_atom_count": len(atoms),
            "ordered_semantic_product_count": len(all_signatures),
            "legacy_rejected_ordered_signature_count": len(all_signatures)
            - len(admitted_signatures),
            "admitted_ordered_signature_count": len(admitted_signatures),
            "role_swap_fixed_signature_count": sum(
                signature.role_a == signature.role_b
                for signature in admitted_signatures
            ),
            "role_neutral_semantic_class_count": len(neutral_semantics),
            "old_semantic_class_count": len(old_semantics),
            "fresh_semantic_class_count": len(fresh_semantics),
            "ordered_goal_frame_count": len(goal_frames),
            "role_neutral_goal_frame_count": len(neutral_goal_frames),
            "movement_vector_profile_count": len(profiles),
            "admitted_ordered_profiled_skeleton_count": len(ordered),
            "self_isomorphic_ordered_skeleton_count": len(self_isomorphic),
            "old_region_ordered_skeleton_count": len(old_region),
            "old_region_role_neutral_skeleton_count": len(old_neutral_keys),
            "fresh_canonical_skeleton_count": len(fresh),
        }
    )
    if dict(counts) != _expected_counts():
        raise UniverseClosureError(
            "typed universe arithmetic does not match the registered closure"
        )

    histograms = tuple(
        sorted(
            {
                "all_skeleton_d4_stabilizer": _histogram(
                    profiled_skeleton_d4_stabilizer_size(skeleton)
                    for skeleton in ordered
                ),
                "fresh_canonical_d4_stabilizer": _histogram(
                    profiled_skeleton_d4_stabilizer_size(skeleton)
                    for skeleton in fresh
                ),
                "goal_frame_d4_stabilizer": _histogram(
                    goal_frame_d4_stabilizer_size(frame) for frame in goal_frames
                ),
                "old_region_d4_stabilizer": _histogram(
                    profiled_skeleton_d4_stabilizer_size(skeleton)
                    for skeleton in old_region
                ),
                "role_atom_by_action": _histogram(
                    atom.action_primitive.value for atom in atoms
                ),
                "role_atom_by_goal": _histogram(
                    atom.goal_primitive.value for atom in atoms
                ),
                "self_isomorphic_d4_stabilizer": _histogram(
                    profiled_skeleton_d4_stabilizer_size(skeleton)
                    for skeleton in self_isomorphic
                ),
            }.items()
        )
    )
    if {
        name: dict(entries) for name, entries in histograms
    } != _expected_histograms():
        raise UniverseClosureError("typed universe stabilizer histograms changed")

    root_values = {
        "role_atom_root": tuple(
            _canonical_json(_role_to_dict(atom)) for atom in atoms
        ),
        "ordered_semantic_signature_root": tuple(
            _canonical_json(signature._payload_unchecked())
            for signature in all_signatures
        ),
        "admitted_signature_root": tuple(
            _canonical_json(signature._payload_unchecked())
            for signature in admitted_signatures
        ),
        "role_neutral_semantic_root": tuple(
            _canonical_json(signature._payload_unchecked())
            for signature in neutral_semantics
        ),
        "fresh_semantic_root": tuple(
            _canonical_json(signature._payload_unchecked())
            for signature in fresh_semantics
        ),
        "old_semantic_root": tuple(
            _canonical_json(signature._payload_unchecked())
            for signature in old_semantics
        ),
        "semantic_mapping_root": _semantic_mapping_values(all_signatures),
        "vector_profile_definition_root": _vector_profile_definition_values(),
        "d4_definition_root": _d4_definition_values(),
        "raw_goal_frame_root": tuple(
            _goal_frame_json_unchecked(frame) for frame in raw_goal_frames
        ),
        "goal_frame_root": tuple(
            _goal_frame_json_unchecked(frame) for frame in goal_frames
        ),
        "role_neutral_goal_frame_root": tuple(
            _goal_frame_json_unchecked(frame) for frame in neutral_goal_frames
        ),
        "ordered_profiled_skeleton_root": tuple(
            _skeleton_json_unchecked(skeleton) for skeleton in ordered
        ),
        "self_isomorphic_ordered_skeleton_root": tuple(
            _skeleton_json_unchecked(skeleton) for skeleton in self_isomorphic
        ),
        "old_region_ordered_skeleton_root": tuple(
            _skeleton_json_unchecked(skeleton) for skeleton in old_region
        ),
        "old_region_role_neutral_skeleton_root": tuple(
            _skeleton_json_unchecked(skeleton) for skeleton in old_neutral
        ),
        "fresh_canonical_skeleton_root": tuple(
            _skeleton_json_unchecked(skeleton) for skeleton in fresh
        ),
        "full_witness_mapping_root": _full_witness_mapping_values(ordered),
    }
    roots_by_name: Dict[str, str] = {}
    endpoints_by_name: Dict[str, Tuple[str, str]] = {}
    for name in sorted(root_values):
        _register_root(
            name,
            _hash_domain(name),
            root_values[name],
            roots_by_name,
            endpoints_by_name,
        )
    roots = tuple(sorted(roots_by_name.items()))
    endpoints = tuple(
        (name, endpoints_by_name[name][0], endpoints_by_name[name][1])
        for name in sorted(endpoints_by_name)
    )
    return counts, histograms, roots, endpoints


def _require_official_descriptor(descriptor: UniverseDescriptor) -> None:
    if dict(descriptor.counts) != _expected_counts():
        raise UniverseClosureError("descriptor is not the official universe counts")
    if {
        name: dict(entries) for name, entries in descriptor.histograms
    } != _expected_histograms():
        raise UniverseClosureError("descriptor is not the official universe histograms")
    if dict(descriptor.roots) != _expected_roots():
        raise UniverseClosureError("descriptor is not the official universe roots")
    if descriptor.descriptor_root != _official_descriptor_root():
        raise UniverseClosureError("descriptor is not the official universe seal")


def build_universe_descriptor() -> UniverseDescriptor:
    """Reconstruct and seal the complete slice-1 arithmetic from enumeration."""

    counts, histograms, roots, endpoints = _descriptor_components()
    payload = {
        "universe_version": _official_universe_version(),
        "counts": dict(counts),
        "histograms": {
            name: dict(entries) for name, entries in histograms
        },
        "roots": dict(roots),
        "endpoints": {
            name: {"first": first, "last": last}
            for name, first, last in endpoints
        },
    }
    descriptor_root = _hash(
        _hash_domain("descriptor_root"), _canonical_json(payload)
    )
    return UniverseDescriptor(
        universe_version=_official_universe_version(),
        counts=counts,
        histograms=histograms,
        roots=roots,
        endpoints=endpoints,
        descriptor_root=descriptor_root,
    )


def canonical_universe_descriptor_json(descriptor: UniverseDescriptor) -> str:
    """Serialize one exact descriptor after verifying its complete seal."""

    if type(descriptor) is not UniverseDescriptor:
        raise TypeError("universe descriptor must be a UniverseDescriptor")
    descriptor._assert_unchanged()
    # Reconstructing the exact dataclass re-runs all shape and seal checks.
    normalized = UniverseDescriptor(
        descriptor.universe_version,
        tuple(descriptor.counts),
        tuple((name, tuple(entries)) for name, entries in descriptor.histograms),
        tuple(descriptor.roots),
        tuple(descriptor.endpoints),
        descriptor.descriptor_root,
    )
    return _canonical_json(normalized.to_dict())


__all__ = (
    "TYPED_OCCUPANCY_UNIVERSE_VERSION",
    "ActionPrimitive",
    "BoardEdge",
    "D4Transform",
    "GoalFrame",
    "GoalFrameKind",
    "GoalPrimitive",
    "GoalTarget",
    "ProfiledRole",
    "ProfiledSkeleton",
    "RoleSignature",
    "SemanticSignature",
    "SkeletonCanonicalization",
    "SkeletonOrbitWitness",
    "UniverseClosureError",
    "UniverseDescriptor",
    "VectorProfile",
    "build_universe_descriptor",
    "canonical_profiled_skeleton_json",
    "canonical_role_neutral_semantic_json",
    "canonical_semantic_signature_json",
    "canonical_universe_descriptor_json",
    "canonicalize_profiled_skeleton",
    "enumerate_admitted_profiled_skeletons",
    "enumerate_admitted_semantic_signatures",
    "enumerate_d4_invariant_vector_sets",
    "enumerate_fresh_canonical_profiled_skeletons",
    "enumerate_fresh_semantic_classes",
    "enumerate_goal_frames",
    "enumerate_movement_vector_profiles",
    "enumerate_ordered_semantic_signatures",
    "enumerate_plan0013_profiled_region_closure",
    "enumerate_plan0013_semantic_classes",
    "enumerate_raw_goal_frames",
    "enumerate_role_atoms",
    "enumerate_role_neutral_goal_frames",
    "enumerate_role_neutral_semantic_classes",
    "enumerate_self_isomorphic_profiled_skeletons",
    "goal_frame_d4_stabilizer_size",
    "is_plan0013_profiled_region",
    "is_plan0013_semantic_region",
    "is_role_swap_d4_self_isomorphic",
    "parse_profiled_skeleton",
    "parse_semantic_signature",
    "profiled_skeleton_d4_stabilizer_size",
    "profiled_skeleton_hash",
    "reconstruct_profiled_skeleton_source",
    "role_neutral_profiled_skeleton_hash",
    "role_neutral_semantic_hash",
    "role_swap_goal_frame",
    "role_swap_profiled_skeleton",
    "role_swap_semantic_signature",
    "schema_v4_admitted_signature",
    "semantic_signature_hash",
    "transform_goal_frame",
    "transform_profiled_skeleton",
    "vector_profile_vectors",
)
