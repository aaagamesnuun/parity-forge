"""Pure typed setup identities and a strict schema-v4 compiler bridge.

This module is the Plan-0015 slice-2 boundary between the sealed descriptive
typed universe and canonical schema-v4 JSON.  It deliberately does not import
the legacy :mod:`parity_forge` package: doing so would acquire engine and game
execution capability through that package's frozen eager initializer.

The compiler is data only.  It validates and detaches finite typed values,
applies square symmetries by fixed formula, emits canonical JSON, and projects
only exact compiler images back to their complete typed source.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Iterable, List, Tuple

from . import typed_occupancy as universe


TYPED_OCCUPANCY_COMPILER_VERSION = 1
TYPED_SETUP_VERSION_V1 = 1
TYPED_SETUP_CARRIER_VERSION_V1 = 1
TYPED_DEFINITION_MEMBER_VERSION_V1 = 1


class CompilerClosureError(ValueError):
    """The compiler's closed vocabulary or public version binding changed."""


def _typed_api(_original: Any = universe) -> Any:
    """Return the definition-time typed module or fail on alias replacement."""

    if universe is not _original:
        raise CompilerClosureError("typed occupancy module binding changed")
    return _original


def _official_compiler_version() -> int:
    _typed_api()
    _fixed_role_owners()
    if (
        type(TYPED_OCCUPANCY_COMPILER_VERSION) is not int
        or TYPED_OCCUPANCY_COMPILER_VERSION != 1
        or type(TYPED_SETUP_VERSION_V1) is not int
        or TYPED_SETUP_VERSION_V1 != 1
        or type(TYPED_SETUP_CARRIER_VERSION_V1) is not int
        or TYPED_SETUP_CARRIER_VERSION_V1 != 1
        or type(TYPED_DEFINITION_MEMBER_VERSION_V1) is not int
        or TYPED_DEFINITION_MEMBER_VERSION_V1 != 1
    ):
        raise CompilerClosureError("typed compiler version binding changed")
    return 1


class RoleOwner(str, Enum):
    """The two exact owner/first-player labels used by the typed compiler."""

    A = "A"
    B = "B"


def _fixed_owner_value(owner: RoleOwner) -> str:
    if owner is RoleOwner.A:
        return "A"
    if owner is RoleOwner.B:
        return "B"
    raise TypeError("role owner must be a RoleOwner")


def _fixed_role_owners(
    _members: Tuple[RoleOwner, RoleOwner] = (RoleOwner.A, RoleOwner.B),
) -> Tuple[RoleOwner, RoleOwner]:
    """Validate every mutable Enum carrier against original singleton anchors."""

    names = ("A", "B")
    if any(type(member) is not RoleOwner for member in _members):
        raise CompilerClosureError("role-owner member type changed")
    raw_names = tuple(member.__dict__.get("_name_") for member in _members)
    raw_values = tuple(member.__dict__.get("_value_") for member in _members)
    intrinsic_values = tuple(str.__str__(member) for member in _members)
    if (
        any(type(item) is not str for item in raw_names)
        or any(type(item) is not str for item in raw_values)
        or any(type(item) is not str for item in intrinsic_values)
        or raw_names != names
        or raw_values != names
        or intrinsic_values != names
    ):
        raise CompilerClosureError("role-owner member identity carrier changed")

    member_names = RoleOwner.__dict__.get("_member_names_")
    member_map = RoleOwner.__dict__.get("_member_map_")
    value_map = RoleOwner.__dict__.get("_value2member_map_")
    if (
        type(member_names) is not list
        or any(type(name) is not str for name in member_names)
        or tuple(member_names) != names
    ):
        raise CompilerClosureError("role-owner member-name carrier changed")
    if (
        type(member_map) is not dict
        or any(type(name) is not str for name in member_map)
        or tuple(member_map) != names
        or tuple(map(id, member_map.values())) != tuple(map(id, _members))
    ):
        raise CompilerClosureError("role-owner member map changed")
    if (
        tuple(RoleOwner.__members__) != names
        or tuple(map(id, RoleOwner.__members__.values())) != tuple(map(id, _members))
    ):
        raise CompilerClosureError("role-owner public member map changed")
    if (
        type(value_map) is not dict
        or any(type(name) is not str for name in value_map)
        or tuple(value_map) != names
        or tuple(map(id, value_map.values())) != tuple(map(id, _members))
    ):
        raise CompilerClosureError("role-owner value map changed")
    if tuple(id(RoleOwner.__dict__.get(name)) for name in names) != tuple(
        map(id, _members)
    ):
        raise CompilerClosureError("role-owner class member binding changed")
    if len({id(member) for member in _members}) != 2:
        raise CompilerClosureError("role-owner member identities alias")
    return _members


def _require_owner(value: Any, label: str) -> RoleOwner:
    owners = _fixed_role_owners()
    if type(value) is not RoleOwner or all(value is not owner for owner in owners):
        raise TypeError("{} must be a RoleOwner".format(label))
    if value.value != _fixed_owner_value(value) or value.name != _fixed_owner_value(
        value
    ):
        raise CompilerClosureError("role-owner vocabulary changed")
    return value


def _owner_from_string(value: Any, label: str) -> RoleOwner:
    _fixed_role_owners()
    if type(value) is not str:
        raise TypeError("{} must be an exact string".format(label))
    if value == "A":
        return _require_owner(RoleOwner.A, label)
    if value == "B":
        return _require_owner(RoleOwner.B, label)
    raise ValueError("{} must be A or B".format(label))


def _require_exact_fields(value: Any, expected: Iterable[str], label: str) -> None:
    try:
        fields = vars(value)
    except TypeError as error:
        raise TypeError("{} fields are unavailable".format(label)) from error
    if type(fields) is not dict or set(fields) != set(expected):
        raise TypeError("{} has noncanonical fields".format(label))


def _exact_dict(value: Any, label: str) -> Dict[str, Any]:
    if type(value) is not dict:
        raise TypeError("{} must be an exact object".format(label))
    if any(type(key) is not str for key in value):
        raise TypeError("{} keys must be exact strings".format(label))
    return value


def _exact_keys(value: Dict[str, Any], expected: Iterable[str], label: str) -> None:
    expected_set = set(expected)
    actual_set = set(value)
    if actual_set != expected_set:
        missing = sorted(expected_set - actual_set)
        extra = sorted(actual_set - expected_set)
        details = []
        if missing:
            details.append("missing {}".format(missing))
        if extra:
            details.append("unknown {}".format(extra))
        raise ValueError("{} has {}".format(label, ", ".join(details)))


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _domain_hash(domain: bytes, canonical: str) -> str:
    return hashlib.sha256(domain + canonical.encode("utf-8")).hexdigest()


Position = Tuple[int, int]


def _validate_positions(value: Any, label: str) -> Tuple[Position, ...]:
    if type(value) is not tuple:
        raise TypeError("{} must be an exact tuple".format(label))
    if len(value) > 3:
        raise ValueError("{} may contain at most three positions".format(label))
    detached: List[Position] = []
    for index, position in enumerate(value):
        path = "{}[{}]".format(label, index)
        if type(position) is not tuple or len(position) != 2:
            raise TypeError("{} must be an exact two-item tuple".format(path))
        row, column = position
        if type(row) is not int or type(column) is not int:
            raise TypeError("{} coordinates must be exact integers".format(path))
        if not (0 <= row < 3 and 0 <= column < 3):
            raise ValueError("{} is outside the 3x3 board".format(path))
        detached.append((row, column))
    result = tuple(detached)
    if result != tuple(sorted(result)):
        raise ValueError("{} must be canonically sorted".format(label))
    if len(set(result)) != len(result):
        raise ValueError("{} cannot contain duplicates".format(label))
    return result


def _positions_from_json(value: Any, label: str) -> Tuple[Position, ...]:
    if type(value) is not list:
        raise TypeError("{} must be an exact array".format(label))
    converted = []
    for index, position in enumerate(value):
        path = "{}[{}]".format(label, index)
        if type(position) is not list or len(position) != 2:
            raise TypeError("{} must be an exact two-item array".format(path))
        if type(position[0]) is not int or type(position[1]) is not int:
            raise TypeError("{} coordinates must be exact integers".format(path))
        converted.append((position[0], position[1]))
    return tuple(converted)


@dataclass(frozen=True, init=False)
class TypedSetupV1:
    """One canonical disjoint 3x3 setup with zero to three pieces per owner."""

    setup_version: int
    role_a_positions: Tuple[Position, ...]
    role_b_positions: Tuple[Position, ...]
    _construction_snapshot: str

    def __init__(
        self,
        setup_version: int,
        role_a_positions: Tuple[Position, ...],
        role_b_positions: Tuple[Position, ...],
    ) -> None:
        if type(setup_version) is not int:
            raise TypeError("typed setup version must be an exact integer")
        if setup_version != _official_compiler_version():
            raise ValueError(
                "typed setup version must equal {}".format(
                    _official_compiler_version()
                )
            )
        positions_a = _validate_positions(role_a_positions, "role A positions")
        positions_b = _validate_positions(role_b_positions, "role B positions")
        if not positions_a and not positions_b:
            raise ValueError("typed setup cannot be empty for both roles")
        if set(positions_a).intersection(positions_b):
            raise ValueError("typed setup positions must be disjoint")
        object.__setattr__(self, "setup_version", setup_version)
        object.__setattr__(self, "role_a_positions", tuple(positions_a))
        object.__setattr__(self, "role_b_positions", tuple(positions_b))
        object.__setattr__(
            self,
            "_construction_snapshot",
            _canonical_json(self._payload_unchecked()),
        )

    def _payload_unchecked(self) -> Dict[str, Any]:
        return {
            "setup_version": self.setup_version,
            "positions": {
                "A": [list(position) for position in self.role_a_positions],
                "B": [list(position) for position in self.role_b_positions],
            },
        }

    def _assert_unchanged(self) -> None:
        _require_exact_fields(
            self,
            (
                "setup_version",
                "role_a_positions",
                "role_b_positions",
                "_construction_snapshot",
            ),
            "typed setup",
        )
        if (
            type(self.setup_version) is not int
            or self.setup_version != _official_compiler_version()
        ):
            raise ValueError("typed setup version changed after construction")
        positions_a = _validate_positions(
            self.role_a_positions, "role A positions"
        )
        positions_b = _validate_positions(
            self.role_b_positions, "role B positions"
        )
        if not positions_a and not positions_b:
            raise ValueError("typed setup became empty")
        if set(positions_a).intersection(positions_b):
            raise ValueError("typed setup positions became non-disjoint")
        if (
            type(self._construction_snapshot) is not str
            or self._construction_snapshot
            != _canonical_json(self._payload_unchecked())
        ):
            raise ValueError("typed setup changed after construction")

    def to_dict(self) -> Dict[str, Any]:
        source = _normalize_setup(self)
        return source._payload_unchecked()


def parse_typed_setup_v1(value: Any) -> TypedSetupV1:
    """Strictly parse one JSON-compatible typed setup payload."""

    setup = _exact_dict(value, "typed setup")
    _exact_keys(setup, ("setup_version", "positions"), "typed setup")
    version = setup["setup_version"]
    if type(version) is not int:
        raise TypeError("typed setup version must be an exact integer")
    positions = _exact_dict(setup["positions"], "typed setup positions")
    _exact_keys(positions, ("A", "B"), "typed setup positions")
    return TypedSetupV1(
        setup_version=version,
        role_a_positions=_positions_from_json(
            positions["A"], "typed setup positions.A"
        ),
        role_b_positions=_positions_from_json(
            positions["B"], "typed setup positions.B"
        ),
    )


def _normalize_setup(
    value: Any,
    _setup_type: Any = TypedSetupV1,
    _assert_unchanged: Any = TypedSetupV1._assert_unchanged,
    _payload_unchecked: Any = TypedSetupV1._payload_unchecked,
) -> TypedSetupV1:
    if (
        TypedSetupV1 is not _setup_type
        or _setup_type._assert_unchanged is not _assert_unchanged
        or _setup_type._payload_unchecked is not _payload_unchecked
    ):
        raise CompilerClosureError("typed setup class binding changed")
    if type(value) is not _setup_type:
        raise TypeError("typed setup must be a TypedSetupV1")
    _assert_unchanged(value)
    return value


def _detach_setup(value: Any) -> TypedSetupV1:
    source = _normalize_setup(value)
    return TypedSetupV1(
        source.setup_version,
        tuple(source.role_a_positions),
        tuple(source.role_b_positions),
    )


def canonical_typed_setup_json_v1(setup: TypedSetupV1) -> str:
    """Serialize one strict setup in its orientation-sensitive identity."""

    source = _normalize_setup(setup)
    return _canonical_json(source._payload_unchecked())


def typed_setup_hash_v1(setup: TypedSetupV1) -> str:
    """Hash one exact typed setup under its own identity domain."""

    return _domain_hash(
        b"parity-forge:plan0015:typed-setup:v1\0",
        canonical_typed_setup_json_v1(setup),
    )


def _preflight_profiled_skeleton_instance(
    value: Any,
    _skeleton_type: Any = universe.ProfiledSkeleton,
    _profiled_role_type: Any = universe.ProfiledRole,
    _role_signature_type: Any = universe.RoleSignature,
    _goal_target_type: Any = universe.GoalTarget,
    _skeleton_assert: Any = universe.ProfiledSkeleton._assert_unchanged,
    _skeleton_payload: Any = universe.ProfiledSkeleton._payload_unchecked,
    _skeleton_to_dict: Any = universe.ProfiledSkeleton.to_dict,
    _role_assert: Any = universe.ProfiledRole._assert_unchanged,
    _role_payload: Any = universe.ProfiledRole._payload_unchecked,
    _signature_assert: Any = universe.RoleSignature._assert_unchanged,
    _target_assert: Any = universe.GoalTarget._assert_unchanged,
    _target_payload: Any = universe.GoalTarget._payload_unchecked,
) -> universe.ProfiledSkeleton:
    """Reject per-instance method shadows before crossing the sealed API."""

    typed = _typed_api()
    if (
        typed.ProfiledSkeleton is not _skeleton_type
        or typed.ProfiledRole is not _profiled_role_type
        or typed.RoleSignature is not _role_signature_type
        or typed.GoalTarget is not _goal_target_type
        or _skeleton_type._assert_unchanged is not _skeleton_assert
        or _skeleton_type._payload_unchecked is not _skeleton_payload
        or _skeleton_type.to_dict is not _skeleton_to_dict
        or _profiled_role_type._assert_unchanged is not _role_assert
        or _profiled_role_type._payload_unchecked is not _role_payload
        or _role_signature_type._assert_unchanged is not _signature_assert
        or _goal_target_type._assert_unchanged is not _target_assert
        or _goal_target_type._payload_unchecked is not _target_payload
    ):
        raise CompilerClosureError("typed skeleton class binding changed")
    if type(value) is not _skeleton_type:
        raise TypeError("profiled skeleton must be a ProfiledSkeleton")
    _require_exact_fields(
        value,
        ("universe_version", "role_a", "role_b", "_construction_snapshot"),
        "profiled skeleton",
    )
    for label, role in (("A", value.role_a), ("B", value.role_b)):
        if type(role) is not _profiled_role_type:
            raise TypeError("profiled skeleton role {} changed type".format(label))
        _require_exact_fields(
            role,
            ("signature", "vector_profile", "goal_target", "_construction_snapshot"),
            "profiled role {}".format(label),
        )
        if type(role.signature) is not _role_signature_type:
            raise TypeError("profiled role {} signature changed type".format(label))
        _require_exact_fields(
            role.signature,
            ("action_primitive", "goal_primitive", "_construction_snapshot"),
            "profiled role {} signature".format(label),
        )
        if type(role.goal_target) is not _goal_target_type:
            raise TypeError("profiled role {} target changed type".format(label))
        _require_exact_fields(
            role.goal_target,
            ("goal_primitive", "edges", "_construction_snapshot"),
            "profiled role {} target".format(label),
        )
    return value


def _detach_skeleton(
    value: Any,
    _parse: Any = universe.parse_profiled_skeleton,
    _to_dict: Any = universe.ProfiledSkeleton.to_dict,
) -> universe.ProfiledSkeleton:
    if (
        _typed_api().parse_profiled_skeleton is not _parse
        or _typed_api().ProfiledSkeleton.to_dict is not _to_dict
    ):
        raise CompilerClosureError("typed skeleton parser binding changed")
    source = _preflight_profiled_skeleton_instance(value)
    detached = _parse(_to_dict(source))
    if detached != source:
        raise CompilerClosureError("typed skeleton detachment changed its identity")
    return detached


def _require_fresh_transport_skeleton(
    skeleton: universe.ProfiledSkeleton,
) -> universe.ProfiledSkeleton:
    detached = _detach_skeleton(skeleton)
    return _validate_fresh_detached_skeleton(detached)


def _validate_fresh_detached_skeleton(
    detached: universe.ProfiledSkeleton,
) -> universe.ProfiledSkeleton:
    public_self_isomorphic = universe.is_role_swap_d4_self_isomorphic(detached)
    literal_self_isomorphic = _is_role_swap_d4_self_isomorphic_literal(detached)
    if public_self_isomorphic is not literal_self_isomorphic:
        raise CompilerClosureError("typed self-isomorphism predicates disagree")
    if literal_self_isomorphic:
        raise ValueError("typed setup carrier rejects self-isomorphic skeletons")
    if _is_plan0013_profiled_region_literal(detached):
        raise ValueError("typed setup carrier rejects the Plan-0013 region")
    return detached


def _is_plan0013_profiled_region_literal(
    skeleton: universe.ProfiledSkeleton,
) -> bool:
    """Reproduce the public old-six semantic firewall from code literals."""

    key = (
        _action_string(skeleton.role_a.signature.action_primitive),
        _goal_string(skeleton.role_a.signature.goal_primitive),
        _action_string(skeleton.role_b.signature.action_primitive),
        _goal_string(skeleton.role_b.signature.goal_primitive),
    )
    swapped = (key[2], key[3], key[0], key[1])
    for semantic_key in (key, swapped):
        if semantic_key == ("PUSH", "REACH_EDGE", "HOP", "REACH_EDGE"):
            return True
        if semantic_key == ("SWAP", "CONNECT_EDGES", "HOP", "REACH_EDGE"):
            return True
        if semantic_key == ("CONVERT", "CONNECT_EDGES", "PUSH", "REACH_EDGE"):
            return True
        if semantic_key == (
            "MOVE_CAPTURE",
            "ELIMINATE",
            "HOP",
            "REACH_EDGE",
        ):
            return True
        if semantic_key == (
            "CONVERT",
            "ELIMINATE",
            "MOVE_CAPTURE",
            "ELIMINATE",
        ):
            return True
        if semantic_key == (
            "PUSH",
            "CONNECT_EDGES",
            "SWAP",
            "CONNECT_EDGES",
        ):
            return True
    return False


def _assert_fresh_transport_skeleton(
    skeleton: Any,
    _to_dict: Any = universe.ProfiledSkeleton.to_dict,
) -> universe.ProfiledSkeleton:
    if _typed_api().ProfiledSkeleton.to_dict is not _to_dict:
        raise CompilerClosureError("typed skeleton serializer binding changed")
    source = _preflight_profiled_skeleton_instance(skeleton)
    _to_dict(source)
    if _is_role_swap_d4_self_isomorphic_literal(source):
        raise ValueError("typed setup carrier became self-isomorphic")
    if _is_plan0013_profiled_region_literal(source):
        raise ValueError("typed setup carrier entered the Plan-0013 region")
    return source


def _transform_edge_string_literal(edge: str, transform: str) -> str:
    if transform == "I":
        return edge
    if transform == "R90":
        if edge == "TOP":
            return "RIGHT"
        if edge == "RIGHT":
            return "BOTTOM"
        if edge == "BOTTOM":
            return "LEFT"
        if edge == "LEFT":
            return "TOP"
    elif transform == "R180":
        if edge == "TOP":
            return "BOTTOM"
        if edge == "RIGHT":
            return "LEFT"
        if edge == "BOTTOM":
            return "TOP"
        if edge == "LEFT":
            return "RIGHT"
    elif transform == "R270":
        if edge == "TOP":
            return "LEFT"
        if edge == "RIGHT":
            return "TOP"
        if edge == "BOTTOM":
            return "RIGHT"
        if edge == "LEFT":
            return "BOTTOM"
    elif transform == "FLR":
        if edge == "TOP":
            return "TOP"
        if edge == "RIGHT":
            return "LEFT"
        if edge == "BOTTOM":
            return "BOTTOM"
        if edge == "LEFT":
            return "RIGHT"
    elif transform == "FTB":
        if edge == "TOP":
            return "BOTTOM"
        if edge == "RIGHT":
            return "RIGHT"
        if edge == "BOTTOM":
            return "TOP"
        if edge == "LEFT":
            return "LEFT"
    elif transform == "FD":
        if edge == "TOP":
            return "LEFT"
        if edge == "RIGHT":
            return "BOTTOM"
        if edge == "BOTTOM":
            return "RIGHT"
        if edge == "LEFT":
            return "TOP"
    elif transform == "FA":
        if edge == "TOP":
            return "RIGHT"
        if edge == "RIGHT":
            return "TOP"
        if edge == "BOTTOM":
            return "LEFT"
        if edge == "LEFT":
            return "BOTTOM"
    raise CompilerClosureError("typed edge/D4 vocabulary changed")


def _is_role_swap_d4_self_isomorphic_literal(
    skeleton: universe.ProfiledSkeleton,
) -> bool:
    role_a = skeleton.role_a
    role_b = skeleton.role_b
    if (
        role_a.signature != role_b.signature
        or role_a.vector_profile is not role_b.vector_profile
    ):
        return False
    edges_a = frozenset(_edge_string(edge) for edge in role_a.goal_target.edges)
    edges_b = frozenset(_edge_string(edge) for edge in role_b.goal_target.edges)
    for transform in ("I", "R90", "R180", "R270", "FLR", "FTB", "FD", "FA"):
        mapped_a = frozenset(
            _transform_edge_string_literal(edge, transform) for edge in edges_a
        )
        mapped_b = frozenset(
            _transform_edge_string_literal(edge, transform) for edge in edges_b
        )
        if mapped_a == edges_b and mapped_b == edges_a:
            return True
    return False


@dataclass(frozen=True, init=False)
class TypedSetupCarrierV1:
    """One exact ordered/oriented fresh skeleton paired with one setup."""

    carrier_version: int
    skeleton: universe.ProfiledSkeleton
    setup: TypedSetupV1
    _construction_snapshot: str

    def __init__(
        self,
        carrier_version: int,
        skeleton: universe.ProfiledSkeleton,
        setup: TypedSetupV1,
    ) -> None:
        if type(carrier_version) is not int:
            raise TypeError("typed setup carrier version must be an exact integer")
        if carrier_version != _official_compiler_version():
            raise ValueError(
                "typed setup carrier version must equal {}".format(
                    _official_compiler_version()
                )
            )
        detached_skeleton = _require_fresh_transport_skeleton(skeleton)
        detached_setup = _detach_setup(setup)
        object.__setattr__(self, "carrier_version", carrier_version)
        object.__setattr__(self, "skeleton", detached_skeleton)
        object.__setattr__(self, "setup", detached_setup)
        object.__setattr__(
            self,
            "_construction_snapshot",
            _canonical_json(self._payload_unchecked()),
        )

    def _payload_unchecked(self) -> Dict[str, Any]:
        return {
            "carrier_version": self.carrier_version,
            "profiled_skeleton": self.skeleton._payload_unchecked(),
            "setup": self.setup._payload_unchecked(),
        }

    def _assert_unchanged(self) -> None:
        _require_exact_fields(
            self,
            ("carrier_version", "skeleton", "setup", "_construction_snapshot"),
            "typed setup carrier",
        )
        if (
            type(self.carrier_version) is not int
            or self.carrier_version != _official_compiler_version()
        ):
            raise ValueError("typed setup carrier version changed after construction")
        _assert_fresh_transport_skeleton(self.skeleton)
        if type(self.setup) is not TypedSetupV1:
            raise TypeError("typed setup carrier setup must remain a TypedSetupV1")
        _normalize_setup(self.setup)
        if (
            type(self._construction_snapshot) is not str
            or self._construction_snapshot
            != _canonical_json(self._payload_unchecked())
        ):
            raise ValueError("typed setup carrier changed after construction")

    def to_dict(self) -> Dict[str, Any]:
        source = _normalize_carrier(self)
        return source._payload_unchecked()


def parse_typed_setup_carrier_v1(value: Any) -> TypedSetupCarrierV1:
    """Strictly parse one JSON-compatible skeleton/setup carrier."""

    carrier = _exact_dict(value, "typed setup carrier")
    _exact_keys(
        carrier,
        ("carrier_version", "profiled_skeleton", "setup"),
        "typed setup carrier",
    )
    version = carrier["carrier_version"]
    if type(version) is not int:
        raise TypeError("typed setup carrier version must be an exact integer")
    return TypedSetupCarrierV1(
        carrier_version=version,
        skeleton=universe.parse_profiled_skeleton(carrier["profiled_skeleton"]),
        setup=parse_typed_setup_v1(carrier["setup"]),
    )


def _normalize_carrier(
    value: Any,
    _carrier_type: Any = TypedSetupCarrierV1,
    _assert_unchanged: Any = TypedSetupCarrierV1._assert_unchanged,
    _payload_unchecked: Any = TypedSetupCarrierV1._payload_unchecked,
) -> TypedSetupCarrierV1:
    if (
        TypedSetupCarrierV1 is not _carrier_type
        or _carrier_type._assert_unchanged is not _assert_unchanged
        or _carrier_type._payload_unchecked is not _payload_unchecked
    ):
        raise CompilerClosureError("typed setup carrier class binding changed")
    if type(value) is not _carrier_type:
        raise TypeError("typed setup carrier must be a TypedSetupCarrierV1")
    _assert_unchanged(value)
    return value


def _detach_carrier(value: Any) -> TypedSetupCarrierV1:
    source = _normalize_carrier(value)
    detached = object.__new__(TypedSetupCarrierV1)
    object.__setattr__(detached, "carrier_version", source.carrier_version)
    object.__setattr__(detached, "skeleton", _detach_skeleton(source.skeleton))
    object.__setattr__(detached, "setup", _detach_setup(source.setup))
    object.__setattr__(
        detached,
        "_construction_snapshot",
        _canonical_json(detached._payload_unchecked()),
    )
    return detached


def canonical_typed_setup_carrier_json_v1(
    carrier: TypedSetupCarrierV1,
) -> str:
    """Serialize one exact ordered/oriented skeleton/setup carrier."""

    source = _normalize_carrier(carrier)
    return _canonical_json(source._payload_unchecked())


def typed_setup_carrier_hash_v1(carrier: TypedSetupCarrierV1) -> str:
    """Hash one exact ordered/oriented carrier under its own domain."""

    return _domain_hash(
        b"parity-forge:plan0015:typed-setup-carrier:v1\0",
        canonical_typed_setup_carrier_json_v1(carrier),
    )


@dataclass(frozen=True, init=False)
class TypedDefinitionMemberV1:
    """One carrier expanded to an exact first-player-labeled DSL member."""

    member_version: int
    carrier: TypedSetupCarrierV1
    first_player: RoleOwner
    _construction_snapshot: str

    def __init__(
        self,
        member_version: int,
        carrier: TypedSetupCarrierV1,
        first_player: RoleOwner,
    ) -> None:
        if type(member_version) is not int:
            raise TypeError("typed definition member version must be an exact integer")
        if member_version != _official_compiler_version():
            raise ValueError(
                "typed definition member version must equal {}".format(
                    _official_compiler_version()
                )
            )
        detached_carrier = _detach_carrier(carrier)
        checked_player = _require_owner(first_player, "first player")
        object.__setattr__(self, "member_version", member_version)
        object.__setattr__(self, "carrier", detached_carrier)
        object.__setattr__(self, "first_player", checked_player)
        object.__setattr__(
            self,
            "_construction_snapshot",
            _canonical_json(self._payload_unchecked()),
        )

    def _payload_unchecked(self) -> Dict[str, Any]:
        return {
            "member_version": self.member_version,
            "carrier": self.carrier._payload_unchecked(),
            "first_player": _fixed_owner_value(self.first_player),
        }

    def _assert_unchanged(self) -> None:
        _require_exact_fields(
            self,
            ("member_version", "carrier", "first_player", "_construction_snapshot"),
            "typed definition member",
        )
        if (
            type(self.member_version) is not int
            or self.member_version != _official_compiler_version()
        ):
            raise ValueError("typed definition member version changed after construction")
        if type(self.carrier) is not TypedSetupCarrierV1:
            raise TypeError(
                "typed definition member carrier must remain a TypedSetupCarrierV1"
            )
        _normalize_carrier(self.carrier)
        _require_owner(self.first_player, "first player")
        if (
            type(self._construction_snapshot) is not str
            or self._construction_snapshot
            != _canonical_json(self._payload_unchecked())
        ):
            raise ValueError("typed definition member changed after construction")

    def to_dict(self) -> Dict[str, Any]:
        source = _normalize_member(self)
        return source._payload_unchecked()


def parse_typed_definition_member_v1(value: Any) -> TypedDefinitionMemberV1:
    """Strictly parse one JSON-compatible first-player-labeled member."""

    member = _exact_dict(value, "typed definition member")
    _exact_keys(
        member,
        ("member_version", "carrier", "first_player"),
        "typed definition member",
    )
    version = member["member_version"]
    if type(version) is not int:
        raise TypeError("typed definition member version must be an exact integer")
    return TypedDefinitionMemberV1(
        member_version=version,
        carrier=parse_typed_setup_carrier_v1(member["carrier"]),
        first_player=_owner_from_string(member["first_player"], "first player"),
    )


def _normalize_member(
    value: Any,
    _member_type: Any = TypedDefinitionMemberV1,
    _assert_unchanged: Any = TypedDefinitionMemberV1._assert_unchanged,
    _payload_unchecked: Any = TypedDefinitionMemberV1._payload_unchecked,
) -> TypedDefinitionMemberV1:
    if (
        TypedDefinitionMemberV1 is not _member_type
        or _member_type._assert_unchanged is not _assert_unchanged
        or _member_type._payload_unchecked is not _payload_unchecked
    ):
        raise CompilerClosureError("typed definition member class binding changed")
    if type(value) is not _member_type:
        raise TypeError("typed definition member must be a TypedDefinitionMemberV1")
    _assert_unchanged(value)
    return value


def canonical_typed_definition_member_json_v1(
    member: TypedDefinitionMemberV1,
) -> str:
    """Serialize one exact carrier/first-player member."""

    source = _normalize_member(member)
    return _canonical_json(source._payload_unchecked())


def _typed_definition_member_hash_unchecked(
    member: TypedDefinitionMemberV1,
) -> str:
    return _domain_hash(
        b"parity-forge:plan0015:typed-definition-member:v1\0",
        _canonical_json(member._payload_unchecked()),
    )


def typed_definition_member_hash_v1(member: TypedDefinitionMemberV1) -> str:
    """Hash one complete typed member under its own identity domain."""

    return _typed_definition_member_hash_unchecked(_normalize_member(member))


def _validate_d4_transform(
    transform: Any,
    _enum_type: Any = universe.D4Transform,
    _members: Tuple[universe.D4Transform, ...] = (
        universe.D4Transform.I,
        universe.D4Transform.R90,
        universe.D4Transform.R180,
        universe.D4Transform.R270,
        universe.D4Transform.FLR,
        universe.D4Transform.FTB,
        universe.D4Transform.FD,
        universe.D4Transform.FA,
    ),
) -> universe.D4Transform:
    """Cross the sealed typed public boundary before using a fixed formula."""

    typed = _typed_api()
    if typed.D4Transform is not _enum_type:
        raise CompilerClosureError("typed D4 class binding changed")
    if type(transform) is not _enum_type:
        raise TypeError("transform must be a D4Transform")
    probe_target = typed.GoalTarget(
        typed.GoalPrimitive.REACH_EDGE, (typed.BoardEdge.TOP,)
    )
    probe = typed.GoalFrame(probe_target, probe_target)
    typed.transform_goal_frame(probe, transform)
    if all(transform is not member for member in _members):
        raise CompilerClosureError("typed D4 singleton identity changed")
    if transform is _members[0]:
        return transform
    if transform is _members[1]:
        return transform
    if transform is _members[2]:
        return transform
    if transform is _members[3]:
        return transform
    if transform is _members[4]:
        return transform
    if transform is _members[5]:
        return transform
    if transform is _members[6]:
        return transform
    if transform is _members[7]:
        return transform
    raise CompilerClosureError("typed D4 vocabulary changed")


def _transform_position_v1(
    position: Position, transform: universe.D4Transform
) -> Position:
    row, column = position
    if transform is universe.D4Transform.I:
        return (row, column)
    if transform is universe.D4Transform.R90:
        return (column, 2 - row)
    if transform is universe.D4Transform.R180:
        return (2 - row, 2 - column)
    if transform is universe.D4Transform.R270:
        return (2 - column, row)
    if transform is universe.D4Transform.FLR:
        return (row, 2 - column)
    if transform is universe.D4Transform.FTB:
        return (2 - row, column)
    if transform is universe.D4Transform.FD:
        return (column, row)
    if transform is universe.D4Transform.FA:
        return (2 - column, 2 - row)
    raise CompilerClosureError("typed D4 vocabulary changed")


def transform_typed_setup_v1(
    setup: TypedSetupV1, transform: universe.D4Transform
) -> TypedSetupV1:
    """Apply one exact D4 element to both owner-labeled position sets."""

    source = _normalize_setup(setup)
    checked_transform = _validate_d4_transform(transform)
    return TypedSetupV1(
        setup_version=_official_compiler_version(),
        role_a_positions=tuple(
            sorted(
                _transform_position_v1(position, checked_transform)
                for position in source.role_a_positions
            )
        ),
        role_b_positions=tuple(
            sorted(
                _transform_position_v1(position, checked_transform)
                for position in source.role_b_positions
            )
        ),
    )


def transform_typed_setup_carrier_v1(
    carrier: TypedSetupCarrierV1, transform: universe.D4Transform
) -> TypedSetupCarrierV1:
    """Transform the exact skeleton frame and setup in the same orientation."""

    source = _normalize_carrier(carrier)
    checked_transform = _validate_d4_transform(transform)
    return TypedSetupCarrierV1(
        carrier_version=_official_compiler_version(),
        skeleton=universe.transform_profiled_skeleton(
            source.skeleton, checked_transform
        ),
        setup=transform_typed_setup_v1(source.setup, checked_transform),
    )


def transform_typed_definition_member_v1(
    member: TypedDefinitionMemberV1, transform: universe.D4Transform
) -> TypedDefinitionMemberV1:
    """Apply D4 while preserving exact role labels and the first player."""

    source = _normalize_member(member)
    return TypedDefinitionMemberV1(
        member_version=_official_compiler_version(),
        carrier=transform_typed_setup_carrier_v1(source.carrier, transform),
        first_player=source.first_player,
    )


def owner_swap_typed_setup_v1(setup: TypedSetupV1) -> TypedSetupV1:
    """Exchange only setup ownership labels A and B."""

    source = _normalize_setup(setup)
    return TypedSetupV1(
        setup_version=_official_compiler_version(),
        role_a_positions=source.role_b_positions,
        role_b_positions=source.role_a_positions,
    )


def owner_swap_typed_setup_carrier_v1(
    carrier: TypedSetupCarrierV1,
) -> TypedSetupCarrierV1:
    """Exchange setup owners while preserving the skeleton exactly."""

    source = _normalize_carrier(carrier)
    return TypedSetupCarrierV1(
        carrier_version=_official_compiler_version(),
        skeleton=source.skeleton,
        setup=owner_swap_typed_setup_v1(source.setup),
    )


def owner_swap_typed_definition_member_v1(
    member: TypedDefinitionMemberV1,
) -> TypedDefinitionMemberV1:
    """Exchange setup owners while preserving skeleton and first player."""

    source = _normalize_member(member)
    return TypedDefinitionMemberV1(
        member_version=_official_compiler_version(),
        carrier=owner_swap_typed_setup_carrier_v1(source.carrier),
        first_player=source.first_player,
    )


def toggle_first_player_member_v1(
    member: TypedDefinitionMemberV1,
) -> TypedDefinitionMemberV1:
    """Return the other first-player expansion of the same exact carrier."""

    source = _normalize_member(member)
    other = RoleOwner.B if source.first_player is RoleOwner.A else RoleOwner.A
    _require_owner(other, "toggled first player")
    return TypedDefinitionMemberV1(
        member_version=_official_compiler_version(),
        carrier=source.carrier,
        first_player=other,
    )


def complete_role_swap_typed_setup_carrier_v1(
    carrier: TypedSetupCarrierV1,
) -> TypedSetupCarrierV1:
    """Swap complete role programs together with their setup ownership."""

    source = _normalize_carrier(carrier)
    return TypedSetupCarrierV1(
        carrier_version=_official_compiler_version(),
        skeleton=universe.role_swap_profiled_skeleton(source.skeleton),
        setup=owner_swap_typed_setup_v1(source.setup),
    )


def complete_role_swap_typed_definition_member_v1(
    member: TypedDefinitionMemberV1,
) -> TypedDefinitionMemberV1:
    """Swap complete roles and toggle the first-player role label."""

    source = _normalize_member(member)
    toggled = RoleOwner.B if source.first_player is RoleOwner.A else RoleOwner.A
    return TypedDefinitionMemberV1(
        member_version=_official_compiler_version(),
        carrier=complete_role_swap_typed_setup_carrier_v1(source.carrier),
        first_player=_require_owner(toggled, "role-swapped first player"),
    )


def expand_first_player_pair_v1(
    carrier: TypedSetupCarrierV1,
) -> Tuple[TypedDefinitionMemberV1, TypedDefinitionMemberV1]:
    """Expand one carrier in the fixed A-first then B-first order."""

    source = _normalize_carrier(carrier)
    return (
        TypedDefinitionMemberV1(1, source, RoleOwner.A),
        TypedDefinitionMemberV1(1, source, RoleOwner.B),
    )


def _edge_string(edge: universe.BoardEdge) -> str:
    if edge is universe.BoardEdge.TOP:
        return "TOP"
    if edge is universe.BoardEdge.RIGHT:
        return "RIGHT"
    if edge is universe.BoardEdge.BOTTOM:
        return "BOTTOM"
    if edge is universe.BoardEdge.LEFT:
        return "LEFT"
    raise CompilerClosureError("typed board-edge vocabulary changed")


def _action_string(action: universe.ActionPrimitive) -> str:
    if action is universe.ActionPrimitive.PLACE:
        return "PLACE"
    if action is universe.ActionPrimitive.MOVE:
        return "MOVE"
    if action is universe.ActionPrimitive.MOVE_CAPTURE:
        return "MOVE_CAPTURE"
    if action is universe.ActionPrimitive.PUSH:
        return "PUSH"
    if action is universe.ActionPrimitive.SWAP:
        return "SWAP"
    if action is universe.ActionPrimitive.HOP:
        return "HOP"
    if action is universe.ActionPrimitive.CONVERT:
        return "CONVERT"
    raise CompilerClosureError("typed action vocabulary changed")


def _goal_string(goal: universe.GoalPrimitive) -> str:
    if goal is universe.GoalPrimitive.CONNECT_EDGES:
        return "CONNECT_EDGES"
    if goal is universe.GoalPrimitive.REACH_EDGE:
        return "REACH_EDGE"
    if goal is universe.GoalPrimitive.ELIMINATE:
        return "ELIMINATE"
    raise CompilerClosureError("typed goal vocabulary changed")


def _compile_action(role: universe.ProfiledRole, piece: str) -> Dict[str, Any]:
    action_kind = _action_string(role.signature.action_primitive)
    payload: Dict[str, Any] = {"kind": action_kind, "piece": piece}
    vectors = universe.vector_profile_vectors(role.vector_profile)
    if action_kind == "PLACE":
        if vectors:
            raise CompilerClosureError("PLACE acquired compiler vectors")
    else:
        if not vectors:
            raise CompilerClosureError("non-PLACE action lost compiler vectors")
        payload["vectors"] = [list(vector) for vector in vectors]
    return payload


def _compile_goal(
    role: universe.ProfiledRole, own_piece: str, opponent_piece: str
) -> Dict[str, Any]:
    goal_kind = _goal_string(role.signature.goal_primitive)
    target = role.goal_target
    if goal_kind == "CONNECT_EDGES":
        edges = sorted(_edge_string(edge) for edge in target.edges)
        if edges not in (["BOTTOM", "TOP"], ["LEFT", "RIGHT"]):
            raise CompilerClosureError("CONNECT_EDGES target left the square axes")
        return {"kind": goal_kind, "piece": own_piece, "edges": edges}
    if goal_kind == "REACH_EDGE":
        if len(target.edges) != 1:
            raise CompilerClosureError("REACH_EDGE target lost its single edge")
        return {
            "kind": goal_kind,
            "piece": own_piece,
            "edge": _edge_string(target.edges[0]),
        }
    if goal_kind == "ELIMINATE":
        if target.edges:
            raise CompilerClosureError("ELIMINATE acquired a spatial target")
        return {"kind": goal_kind, "piece": opponent_piece}
    raise CompilerClosureError("typed goal vocabulary changed")


def _compiled_definition_payload(member: TypedDefinitionMemberV1) -> Dict[str, Any]:
    return _compiled_definition_payload_unchecked(_normalize_member(member))


def _compiled_definition_payload_unchecked(
    source: TypedDefinitionMemberV1,
) -> Dict[str, Any]:
    skeleton = source.carrier.skeleton
    setup = source.carrier.setup
    member_hash = _typed_definition_member_hash_unchecked(source)
    pieces = []
    for owner, piece, positions in (
        ("A", "a", setup.role_a_positions),
        ("B", "b", setup.role_b_positions),
    ):
        pieces.extend(
            {"owner": owner, "piece": piece, "position": list(position)}
            for position in positions
        )
    pieces.sort(
        key=lambda item: (
            tuple(item["position"]),
            item["owner"],
            item["piece"],
        )
    )
    return {
        "schema_version": 4,
        "name": "pf15-" + member_hash,
        "board_size": 3,
        "first_player": _fixed_owner_value(source.first_player),
        "max_plies": 18,
        "roles": {
            "A": {
                "action": _compile_action(skeleton.role_a, "a"),
                "goal": _compile_goal(skeleton.role_a, "a", "b"),
            },
            "B": {
                "action": _compile_action(skeleton.role_b, "b"),
                "goal": _compile_goal(skeleton.role_b, "b", "a"),
            },
        },
        "initial_pieces": pieces,
    }


def compile_schema_v4_json_v1(member: TypedDefinitionMemberV1) -> str:
    """Compile one typed member into canonical authoritative schema-v4 JSON."""

    return _canonical_json(_compiled_definition_payload(member))


def compiled_schema_v4_hash_v1(member: TypedDefinitionMemberV1) -> str:
    """Match the authoritative DSL definition hash over canonical JSON bytes."""

    return hashlib.sha256(compile_schema_v4_json_v1(member).encode("utf-8")).hexdigest()


def _make_carrier_unchecked(
    skeleton: universe.ProfiledSkeleton, setup: TypedSetupV1
) -> TypedSetupCarrierV1:
    carrier = object.__new__(TypedSetupCarrierV1)
    object.__setattr__(carrier, "carrier_version", 1)
    object.__setattr__(carrier, "skeleton", skeleton)
    object.__setattr__(carrier, "setup", setup)
    object.__setattr__(
        carrier,
        "_construction_snapshot",
        _canonical_json(carrier._payload_unchecked()),
    )
    return carrier


def _make_member_unchecked(
    carrier: TypedSetupCarrierV1, first_player: RoleOwner
) -> TypedDefinitionMemberV1:
    member = object.__new__(TypedDefinitionMemberV1)
    object.__setattr__(member, "member_version", 1)
    object.__setattr__(member, "carrier", carrier)
    object.__setattr__(member, "first_player", first_player)
    object.__setattr__(
        member,
        "_construction_snapshot",
        _canonical_json(member._payload_unchecked()),
    )
    return member


def _reject_duplicate_object(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("compiled schema-v4 JSON contains a duplicate key")
        result[key] = value
    return result


def _reject_noninteger_number(_value: str) -> Any:
    raise ValueError("compiled schema-v4 JSON cannot contain non-integer numbers")


def _load_bounded_compiled_json(value: Any) -> Dict[str, Any]:
    if type(value) is not str:
        raise TypeError("compiled schema-v4 JSON must be an exact string")
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError("compiled schema-v4 JSON must be valid UTF-8") from error
    if not value or len(encoded) > 8192:
        raise ValueError("compiled schema-v4 JSON is empty or exceeds its byte cap")
    try:
        parsed = json.loads(
            value,
            object_pairs_hook=_reject_duplicate_object,
            parse_float=_reject_noninteger_number,
            parse_constant=_reject_noninteger_number,
        )
    except (TypeError, ValueError, RecursionError) as error:
        raise ValueError("compiled schema-v4 JSON is invalid") from error
    root = _exact_dict(parsed, "compiled schema-v4 definition")

    node_count = 0

    def visit(item: Any, depth: int) -> None:
        nonlocal node_count
        node_count += 1
        if node_count > 256:
            raise ValueError("compiled schema-v4 JSON exceeds its node cap")
        if depth > 12:
            raise ValueError("compiled schema-v4 JSON exceeds its depth cap")
        if item is None or type(item) in (bool, int, str):
            return
        if type(item) is list:
            for child in item:
                visit(child, depth + 1)
            return
        if type(item) is dict:
            if any(type(key) is not str for key in item):
                raise TypeError("compiled schema-v4 JSON keys must be exact strings")
            for child in item.values():
                visit(child, depth + 1)
            return
        raise TypeError("compiled schema-v4 JSON contains a nonexact JSON value")

    visit(root, 0)
    if _canonical_json(root) != value:
        raise ValueError("compiled schema-v4 JSON must use exact canonical bytes")
    return root


def _parse_compiled_action(
    value: Any, piece: str, label: str
) -> Tuple[str, str]:
    action = _exact_dict(value, label)
    if "kind" not in action:
        raise ValueError("{} is missing kind".format(label))
    kind = action["kind"]
    if type(kind) is not str:
        raise TypeError("{}.kind must be an exact string".format(label))
    if kind == "PLACE":
        _exact_keys(action, ("kind", "piece"), label)
        profile = "NONE"
    elif kind in (
        "MOVE",
        "MOVE_CAPTURE",
        "PUSH",
        "SWAP",
        "HOP",
        "CONVERT",
    ):
        _exact_keys(action, ("kind", "piece", "vectors"), label)
        raw_vectors = action["vectors"]
        if type(raw_vectors) is not list or not raw_vectors:
            raise TypeError("{}.vectors must be a nonempty exact array".format(label))
        vectors = []
        for index, vector in enumerate(raw_vectors):
            path = "{}.vectors[{}]".format(label, index)
            if type(vector) is not list or len(vector) != 2:
                raise TypeError("{} must be an exact two-item array".format(path))
            if type(vector[0]) is not int or type(vector[1]) is not int:
                raise TypeError("{} coordinates must be exact integers".format(path))
            vectors.append((vector[0], vector[1]))
        vector_tuple = tuple(vectors)
        if vector_tuple == ((-1, 0), (0, -1), (0, 1), (1, 0)):
            profile = "ORTHOGONAL_4"
        elif vector_tuple == ((-1, -1), (-1, 1), (1, -1), (1, 1)):
            profile = "DIAGONAL_4"
        elif vector_tuple == (
            (-1, -1),
            (-1, 0),
            (-1, 1),
            (0, -1),
            (0, 1),
            (1, -1),
            (1, 0),
            (1, 1),
        ):
            profile = "KING_8"
        else:
            raise ValueError("{}.vectors are outside the typed profile closure".format(label))
    else:
        raise ValueError("{}.kind is outside the typed action closure".format(label))
    if type(action.get("piece")) is not str or action["piece"] != piece:
        raise ValueError("{}.piece must be {}".format(label, piece))
    return kind, profile


def _parse_compiled_goal(
    value: Any, own_piece: str, opponent_piece: str, label: str
) -> Tuple[str, List[str]]:
    goal = _exact_dict(value, label)
    if "kind" not in goal:
        raise ValueError("{} is missing kind".format(label))
    kind = goal["kind"]
    if type(kind) is not str:
        raise TypeError("{}.kind must be an exact string".format(label))
    if kind == "CONNECT_EDGES":
        _exact_keys(goal, ("kind", "piece", "edges"), label)
        if type(goal["edges"]) is not list:
            raise TypeError("{}.edges must be an exact array".format(label))
        if goal["edges"] == ["BOTTOM", "TOP"]:
            target_edges = ["TOP", "BOTTOM"]
        elif goal["edges"] == ["LEFT", "RIGHT"]:
            target_edges = ["RIGHT", "LEFT"]
        else:
            raise ValueError("{}.edges must be one DSL-canonical axis".format(label))
        expected_piece = own_piece
    elif kind == "REACH_EDGE":
        _exact_keys(goal, ("kind", "piece", "edge"), label)
        edge = goal["edge"]
        if type(edge) is not str or edge not in ("TOP", "RIGHT", "BOTTOM", "LEFT"):
            raise ValueError("{}.edge is outside the square boundary".format(label))
        target_edges = [edge]
        expected_piece = own_piece
    elif kind == "ELIMINATE":
        _exact_keys(goal, ("kind", "piece"), label)
        target_edges = []
        expected_piece = opponent_piece
    else:
        raise ValueError("{}.kind is outside the typed goal closure".format(label))
    if type(goal.get("piece")) is not str or goal["piece"] != expected_piece:
        raise ValueError("{}.piece must be {}".format(label, expected_piece))
    return kind, target_edges


def _parse_compiled_role(
    value: Any, own_piece: str, opponent_piece: str, label: str
) -> Dict[str, Any]:
    role = _exact_dict(value, label)
    _exact_keys(role, ("action", "goal"), label)
    action, profile = _parse_compiled_action(
        role["action"], own_piece, label + ".action"
    )
    goal, target_edges = _parse_compiled_goal(
        role["goal"], own_piece, opponent_piece, label + ".goal"
    )
    return {
        "action_primitive": action,
        "goal_primitive": goal,
        "vector_profile": profile,
        "target_edges": target_edges,
    }


def _parse_compiled_pieces(value: Any) -> Tuple[Tuple[Position, ...], Tuple[Position, ...]]:
    if type(value) is not list:
        raise TypeError("compiled initial_pieces must be an exact array")
    if not 1 <= len(value) <= 6:
        raise ValueError("compiled initial_pieces must contain one through six pieces")
    positions_a = []
    positions_b = []
    ordering = []
    for index, raw_piece in enumerate(value):
        label = "compiled initial_pieces[{}]".format(index)
        piece = _exact_dict(raw_piece, label)
        _exact_keys(piece, ("owner", "piece", "position"), label)
        owner = piece["owner"]
        if type(owner) is not str or owner not in ("A", "B"):
            raise ValueError("{}.owner must be A or B".format(label))
        expected_piece = "a" if owner == "A" else "b"
        if type(piece["piece"]) is not str or piece["piece"] != expected_piece:
            raise ValueError("{}.piece does not match its owner".format(label))
        position_value = piece["position"]
        if type(position_value) is not list or len(position_value) != 2:
            raise TypeError("{}.position must be an exact two-item array".format(label))
        if type(position_value[0]) is not int or type(position_value[1]) is not int:
            raise TypeError("{}.position coordinates must be exact integers".format(label))
        position = (position_value[0], position_value[1])
        ordering.append((position, owner, expected_piece))
        if owner == "A":
            positions_a.append(position)
        else:
            positions_b.append(position)
    if ordering != sorted(ordering):
        raise ValueError("compiled initial_pieces are not globally canonical")
    return tuple(sorted(positions_a)), tuple(sorted(positions_b))


def project_compiled_schema_v4_json_v1(value: str) -> TypedDefinitionMemberV1:
    """Reconstruct the complete typed source of one exact compiler image.

    Projection never treats the name hash as an inverse.  Every skeleton,
    setup, and first-player field is reconstructed from the DSL body, and the
    resulting member must recompile to the exact input bytes (including name).
    """

    definition = _load_bounded_compiled_json(value)
    _exact_keys(
        definition,
        (
            "schema_version",
            "name",
            "board_size",
            "first_player",
            "max_plies",
            "roles",
            "initial_pieces",
        ),
        "compiled schema-v4 definition",
    )
    if type(definition["schema_version"]) is not int or definition["schema_version"] != 4:
        raise ValueError("compiled definition must use schema_version 4")
    if type(definition["board_size"]) is not int or definition["board_size"] != 3:
        raise ValueError("compiled definition must use a 3x3 board")
    if type(definition["max_plies"]) is not int or definition["max_plies"] != 18:
        raise ValueError("compiled definition must use max_plies 18")
    name = definition["name"]
    if (
        type(name) is not str
        or len(name) != 69
        or not name.startswith("pf15-")
        or any(character not in "0123456789abcdef" for character in name[5:])
    ):
        raise ValueError("compiled definition name is not a pf15 member hash")
    first_player = _owner_from_string(
        definition["first_player"], "compiled first_player"
    )
    roles = _exact_dict(definition["roles"], "compiled roles")
    _exact_keys(roles, ("A", "B"), "compiled roles")
    raw_skeleton = {
        "universe_version": 1,
        "roles": {
            "A": _parse_compiled_role(roles["A"], "a", "b", "compiled role A"),
            "B": _parse_compiled_role(roles["B"], "b", "a", "compiled role B"),
        },
    }
    skeleton = universe.parse_profiled_skeleton(raw_skeleton)
    positions_a, positions_b = _parse_compiled_pieces(definition["initial_pieces"])
    setup = TypedSetupV1(1, positions_a, positions_b)
    checked_skeleton = _validate_fresh_detached_skeleton(skeleton)
    carrier = _make_carrier_unchecked(checked_skeleton, setup)
    member = _make_member_unchecked(carrier, first_player)
    if _canonical_json(_compiled_definition_payload_unchecked(member)) != value:
        raise ValueError("compiled schema-v4 JSON is not an exact compiler image")
    _normalize_member(member)
    return member


__all__ = (
    "TYPED_OCCUPANCY_COMPILER_VERSION",
    "TYPED_DEFINITION_MEMBER_VERSION_V1",
    "TYPED_SETUP_CARRIER_VERSION_V1",
    "TYPED_SETUP_VERSION_V1",
    "CompilerClosureError",
    "RoleOwner",
    "TypedDefinitionMemberV1",
    "TypedSetupCarrierV1",
    "TypedSetupV1",
    "canonical_typed_definition_member_json_v1",
    "canonical_typed_setup_carrier_json_v1",
    "canonical_typed_setup_json_v1",
    "compile_schema_v4_json_v1",
    "compiled_schema_v4_hash_v1",
    "complete_role_swap_typed_definition_member_v1",
    "complete_role_swap_typed_setup_carrier_v1",
    "expand_first_player_pair_v1",
    "owner_swap_typed_definition_member_v1",
    "owner_swap_typed_setup_carrier_v1",
    "owner_swap_typed_setup_v1",
    "parse_typed_definition_member_v1",
    "parse_typed_setup_carrier_v1",
    "parse_typed_setup_v1",
    "project_compiled_schema_v4_json_v1",
    "toggle_first_player_member_v1",
    "transform_typed_definition_member_v1",
    "transform_typed_setup_carrier_v1",
    "transform_typed_setup_v1",
    "typed_definition_member_hash_v1",
    "typed_setup_carrier_hash_v1",
    "typed_setup_hash_v1",
)
