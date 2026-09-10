"""Bounded, callback-free semantic identities for game families.

This module classifies ludeme-level families. It deliberately does *not*
describe a generator search envelope or an executable game. Those identities
remain separate:

* :class:`FamilySignature` identifies a name-free mechanical family cell;
* :class:`FamilyRecord` gives that cell a stable registry label;
* a future search envelope will bind setup and parameter domains; and
* :class:`~parity_forge.dsl.GameDefinition` remains the authoritative rule object.

All accepted data is finite, declarative, canonical, and free of callbacks,
predicates, generated code, outcomes, or presentation prose.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Iterable, Iterator, Mapping, Tuple


FAMILY_SIGNATURE_VERSION = 1
FAMILY_REGISTRY_VERSION = 1


class StateKernel(str, Enum):
    """State shapes with semantics defined for signature version 1."""

    OCCUPANCY = "OCCUPANCY"


class ActionPrimitive(str, Enum):
    """Closed action concepts; their executable semantics live in the DSL.

    ``CAPTURE_STEP`` is a provisional signature-v1 token retained for identity
    compatibility.  It has no executable DSL primitive because its proposed
    semantics alias the existing ``MOVE_CAPTURE`` primitive.
    """

    PLACE = "PLACE"
    MOVE = "MOVE"
    MOVE_CAPTURE = "MOVE_CAPTURE"
    PUSH = "PUSH"
    SWAP = "SWAP"
    HOP = "HOP"
    CONVERT = "CONVERT"
    CAPTURE_STEP = "CAPTURE_STEP"


NONRETIRED_ACTION_PRIMITIVES_V1 = frozenset(
    {
        ActionPrimitive.PLACE,
        ActionPrimitive.MOVE,
        ActionPrimitive.MOVE_CAPTURE,
        ActionPrimitive.PUSH,
        ActionPrimitive.SWAP,
        ActionPrimitive.HOP,
        ActionPrimitive.CONVERT,
    }
)


class GoalPrimitive(str, Enum):
    """Closed goal concepts; their executable semantics live in the DSL."""

    CONNECT_EDGES = "CONNECT_EDGES"
    REACH_EDGE = "REACH_EDGE"
    ELIMINATE = "ELIMINATE"


class TerminalContract(str, Enum):
    """Versioned ordering of goal, horizon, and stuck-player checks."""

    ACTOR_GOAL_PLY_CAP_STUCK_LOSS_V1 = "ACTOR_GOAL_PLY_CAP_STUCK_LOSS_V1"
    ACTOR_GOAL_PLY_CAP_STUCK_DRAW_V1 = "ACTOR_GOAL_PLY_CAP_STUCK_DRAW_V1"
    ANY_GOAL_ACTION_ACTOR_INITIAL_FIRST_PRIORITY_PLY_CAP_STUCK_LOSS_V1 = (
        "ANY_GOAL_ACTION_ACTOR_INITIAL_FIRST_PRIORITY_PLY_CAP_STUCK_LOSS_V1"
    )


class TurnStructure(str, Enum):
    """Allowed turn structures for the bounded-family grammar."""

    ALTERNATING_SINGLE_ACTION = "ALTERNATING_SINGLE_ACTION"


@dataclass(frozen=True)
class RoleSignature:
    """The two primitive concepts that make one role mechanically distinct."""

    action_primitive: ActionPrimitive
    goal_primitive: GoalPrimitive

    def __post_init__(self) -> None:
        _require_exact_enum(
            self.action_primitive, ActionPrimitive, "role action primitive"
        )
        _require_exact_enum(
            self.goal_primitive, GoalPrimitive, "role goal primitive"
        )

    def to_dict(self) -> Dict[str, str]:
        return {
            "action_primitive": self.action_primitive.value,
            "goal_primitive": self.goal_primitive.value,
        }


@dataclass(frozen=True)
class FamilySignature:
    """Name-free ludeme identity, distinct from any search envelope."""

    signature_version: int
    state_kernel: StateKernel
    role_a: RoleSignature
    role_b: RoleSignature
    terminal_contract: TerminalContract
    turn_structure: TurnStructure

    def __post_init__(self) -> None:
        if type(self.signature_version) is not int:
            raise TypeError("family signature version must be an integer")
        if self.signature_version != FAMILY_SIGNATURE_VERSION:
            raise ValueError(
                "family signature version must equal {}".format(
                    FAMILY_SIGNATURE_VERSION
                )
            )
        _require_exact_enum(self.state_kernel, StateKernel, "family state kernel")
        if type(self.role_a) is not RoleSignature:
            raise TypeError("family role A must be a RoleSignature")
        if type(self.role_b) is not RoleSignature:
            raise TypeError("family role B must be a RoleSignature")
        _require_exact_enum(
            self.terminal_contract, TerminalContract, "family terminal contract"
        )
        _require_exact_enum(
            self.turn_structure, TurnStructure, "family turn structure"
        )

    @property
    def roles(self) -> Tuple[Tuple[str, RoleSignature], ...]:
        """Return roles in the only canonical order: A followed by B."""

        return (("A", self.role_a), ("B", self.role_b))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signature_version": self.signature_version,
            "state_kernel": self.state_kernel.value,
            "roles": {
                "A": self.role_a.to_dict(),
                "B": self.role_b.to_dict(),
            },
            "terminal_contract": self.terminal_contract.value,
            "turn_structure": self.turn_structure.value,
        }


_FAMILY_ID = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")


@dataclass(frozen=True)
class FamilyRecord:
    """A stable registry label paired with a name-independent signature."""

    family_id: str
    signature: FamilySignature

    def __post_init__(self) -> None:
        if (
            type(self.family_id) is not str
            or len(self.family_id) > 80
            or _FAMILY_ID.fullmatch(self.family_id) is None
        ):
            raise ValueError(
                "family_id must be a lowercase hyphen-separated stable identifier"
            )
        if type(self.signature) is not FamilySignature:
            raise TypeError("family record signature must be a FamilySignature")

    @property
    def semantic_hash(self) -> str:
        return family_signature_hash(self.signature)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "family_id": self.family_id,
            "signature": self.signature.to_dict(),
        }


@dataclass(frozen=True, init=False)
class FamilyRegistry:
    """Immutable ordered records with unique labels and semantic identities."""

    records: Tuple[FamilyRecord, ...]
    _canonical_snapshot: str

    def __init__(self, records: Iterable[FamilyRecord] = ()) -> None:
        try:
            supplied = tuple(records)
        except TypeError as error:
            raise TypeError("family registry records must be iterable") from error
        if any(type(record) is not FamilyRecord for record in supplied):
            raise TypeError("family registry accepts only FamilyRecord values")

        # Reparse at the boundary. This detaches caller references and rejects
        # exact-type objects forged with object.__setattr__.
        canonical_records = tuple(
            parse_family_record(record.to_dict()) for record in supplied
        )
        seen_ids: Dict[str, str] = {}
        seen_hashes: Dict[str, str] = {}
        for record in canonical_records:
            digest = record.semantic_hash
            if record.family_id in seen_ids:
                raise ValueError(
                    "family registry contains duplicate family_id {}".format(
                        record.family_id
                    )
                )
            if digest in seen_hashes:
                raise ValueError(
                    "family registry aliases the same semantic signature as {}".format(
                        seen_hashes[digest]
                    )
                )
            seen_ids[record.family_id] = digest
            seen_hashes[digest] = record.family_id
        object.__setattr__(self, "records", canonical_records)
        snapshot = json.dumps(
            {
                "registry_version": FAMILY_REGISTRY_VERSION,
                "records": [record.to_dict() for record in canonical_records],
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        object.__setattr__(self, "_canonical_snapshot", snapshot)

    def __iter__(self) -> Iterator[FamilyRecord]:
        self._assert_unchanged()
        return iter(self.records)

    def __len__(self) -> int:
        self._assert_unchanged()
        return len(self.records)

    @property
    def family_ids(self) -> Tuple[str, ...]:
        self._assert_unchanged()
        return tuple(record.family_id for record in self.records)

    @property
    def semantic_hashes(self) -> Tuple[str, ...]:
        self._assert_unchanged()
        return tuple(record.semantic_hash for record in self.records)

    def get(self, family_id: str) -> FamilyRecord:
        self._assert_unchanged()
        if type(family_id) is not str:
            raise TypeError("family registry lookup ID must be a string")
        for record in self.records:
            if record.family_id == family_id:
                return record
        raise KeyError(family_id)

    def to_dict(self) -> Dict[str, Any]:
        self._assert_unchanged()
        return {
            "registry_version": FAMILY_REGISTRY_VERSION,
            "records": [record.to_dict() for record in self.records],
        }

    def _assert_unchanged(self) -> None:
        try:
            current = json.dumps(
                {
                    "registry_version": FAMILY_REGISTRY_VERSION,
                    "records": [record.to_dict() for record in self.records],
                },
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("family registry changed after construction") from error
        if (
            type(self._canonical_snapshot) is not str
            or current != self._canonical_snapshot
        ):
            raise ValueError("family registry changed after construction")


_ROLE_KEYS = ("action_primitive", "goal_primitive")
_SIGNATURE_KEYS = (
    "signature_version",
    "state_kernel",
    "roles",
    "terminal_contract",
    "turn_structure",
)
_FAMILY_SIGNATURE_HASH_DOMAIN = b"parity-forge:family-signature:v1\0"
_FAMILY_REGISTRY_HASH_DOMAIN = b"parity-forge:family-registry:v1\0"


def _require_exact_enum(value: Any, enum_type: Any, label: str) -> None:
    if type(value) is not enum_type:
        raise TypeError("{} must be a {}".format(label, enum_type.__name__))


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("{} must be an object".format(label))
    if not all(type(key) is str for key in value):
        raise TypeError("{} keys must be strings".format(label))
    return value


def _exact_keys(value: Mapping[str, Any], expected: Iterable[str], label: str) -> None:
    expected_set = set(expected)
    actual = set(value)
    if actual != expected_set:
        missing = sorted(expected_set - actual)
        unknown = sorted(actual - expected_set)
        details = []
        if missing:
            details.append("missing {}".format(missing))
        if unknown:
            details.append("unknown {}".format(unknown))
        raise ValueError("{} has {}".format(label, ", ".join(details)))


def _enum_from_string(enum_type: Any, value: Any, label: str) -> Any:
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


def _parse_role_signature(value: Any, label: str) -> RoleSignature:
    role = _mapping(value, label)
    _exact_keys(role, _ROLE_KEYS, label)
    return RoleSignature(
        action_primitive=_enum_from_string(
            ActionPrimitive,
            role["action_primitive"],
            label + ".action_primitive",
        ),
        goal_primitive=_enum_from_string(
            GoalPrimitive,
            role["goal_primitive"],
            label + ".goal_primitive",
        ),
    )


def parse_family_signature(value: Any) -> FamilySignature:
    """Strictly parse one JSON-compatible semantic family signature."""

    signature = _mapping(value, "family signature")
    _exact_keys(signature, _SIGNATURE_KEYS, "family signature")
    version = signature["signature_version"]
    if type(version) is not int:
        raise TypeError("family signature version must be an integer")
    roles = _mapping(signature["roles"], "family signature roles")
    _exact_keys(roles, ("A", "B"), "family signature roles")
    return FamilySignature(
        signature_version=version,
        state_kernel=_enum_from_string(
            StateKernel, signature["state_kernel"], "family state kernel"
        ),
        role_a=_parse_role_signature(roles["A"], "family role A"),
        role_b=_parse_role_signature(roles["B"], "family role B"),
        terminal_contract=_enum_from_string(
            TerminalContract,
            signature["terminal_contract"],
            "family terminal contract",
        ),
        turn_structure=_enum_from_string(
            TurnStructure,
            signature["turn_structure"],
            "family turn structure",
        ),
    )


def parse_family_record(value: Any) -> FamilyRecord:
    """Strictly parse registry metadata without changing semantic identity."""

    record = _mapping(value, "family record")
    _exact_keys(record, ("family_id", "signature"), "family record")
    return FamilyRecord(
        family_id=record["family_id"],
        signature=parse_family_signature(record["signature"]),
    )


def parse_family_registry(value: Any) -> FamilyRegistry:
    """Strictly parse a versioned registry whose record order is significant."""

    registry = _mapping(value, "family registry")
    _exact_keys(registry, ("registry_version", "records"), "family registry")
    version = registry["registry_version"]
    if type(version) is not int:
        raise TypeError("family registry version must be an integer")
    if version != FAMILY_REGISTRY_VERSION:
        raise ValueError(
            "family registry version must equal {}".format(
                FAMILY_REGISTRY_VERSION
            )
        )
    records = registry["records"]
    if type(records) is not list:
        raise TypeError("family registry records must be an array")
    return FamilyRegistry(parse_family_record(record) for record in records)


def _normalized_signature(signature: FamilySignature) -> FamilySignature:
    if type(signature) is not FamilySignature:
        raise TypeError("canonical family JSON requires a FamilySignature")
    try:
        return parse_family_signature(signature.to_dict())
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("family signature is not parser-normalized") from error


def _normalized_registry(registry: FamilyRegistry) -> FamilyRegistry:
    if type(registry) is not FamilyRegistry:
        raise TypeError("canonical family registry JSON requires a FamilyRegistry")
    try:
        registry._assert_unchanged()
        normalized = parse_family_registry(registry.to_dict())
        if normalized._canonical_snapshot != registry._canonical_snapshot:
            raise ValueError("family registry snapshot does not reconstruct")
        return normalized
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("family registry is not parser-normalized") from error


def canonical_family_signature_json(signature: FamilySignature) -> str:
    """Return canonical JSON after strict exact-type revalidation."""

    normalized = _normalized_signature(signature)
    return json.dumps(
        normalized.to_dict(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def family_signature_hash(signature: FamilySignature) -> str:
    """Return the domain-separated, registry-name-independent semantic hash."""

    canonical = canonical_family_signature_json(signature).encode("utf-8")
    return hashlib.sha256(_FAMILY_SIGNATURE_HASH_DOMAIN + canonical).hexdigest()


def canonical_family_registry_json(registry: FamilyRegistry) -> str:
    """Serialize a registry canonically while preserving declared record order."""

    normalized = _normalized_registry(registry)
    return json.dumps(
        normalized.to_dict(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def family_registry_hash(registry: FamilyRegistry) -> str:
    """Hash registry labels, ordered membership, and semantic signatures."""

    canonical = canonical_family_registry_json(registry).encode("utf-8")
    return hashlib.sha256(_FAMILY_REGISTRY_HASH_DOMAIN + canonical).hexdigest()


def validate_nonretired_family_signature(
    signature: FamilySignature,
) -> FamilySignature:
    """Return a normalized signature only if it uses no retired alias token.

    Signature version 1 keeps retired proposal tokens readable so previously
    recorded semantic identities remain reconstructable. Active builders must
    cross this boundary before emission, then separately prove DSL compilability
    and schema admission; this check alone does not establish either property.
    """

    normalized = _normalized_signature(signature)
    for role_name, role in normalized.roles:
        if role.action_primitive not in NONRETIRED_ACTION_PRIMITIVES_V1:
            raise ValueError(
                "family role {} action primitive {} is retired; use "
                "MOVE_CAPTURE for CAPTURE_STEP mechanics".format(
                    role_name,
                    role.action_primitive.value,
                )
            )
    return normalized


def validate_nonretired_family_registry(
    registry: FamilyRegistry,
) -> FamilyRegistry:
    """Return a normalized registry only if no signature uses a retired alias."""

    normalized = _normalized_registry(registry)
    for record in normalized.records:
        try:
            validate_nonretired_family_signature(record.signature)
        except ValueError as error:
            raise ValueError(
                "family record {} uses a retired primitive: {}".format(
                    record.family_id,
                    error,
                )
            ) from error
    return normalized


__all__ = (
    "FAMILY_REGISTRY_VERSION",
    "FAMILY_SIGNATURE_VERSION",
    "NONRETIRED_ACTION_PRIMITIVES_V1",
    "ActionPrimitive",
    "FamilyRecord",
    "FamilyRegistry",
    "FamilySignature",
    "GoalPrimitive",
    "RoleSignature",
    "StateKernel",
    "TerminalContract",
    "TurnStructure",
    "canonical_family_registry_json",
    "canonical_family_signature_json",
    "family_registry_hash",
    "family_signature_hash",
    "parse_family_record",
    "parse_family_registry",
    "parse_family_signature",
    "validate_nonretired_family_registry",
    "validate_nonretired_family_signature",
)
