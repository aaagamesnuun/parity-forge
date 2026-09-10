"""Strict, declarative, versioned game definitions.

This module is intentionally boring: it accepts data, rejects unknown structure,
and produces immutable values. It cannot execute definition-supplied behavior.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple


class Player(str, Enum):
    A = "A"
    B = "B"

    @property
    def other(self) -> "Player":
        return Player.B if self is Player.A else Player.A


class ActionKind(str, Enum):
    PLACE = "PLACE"
    MOVE = "MOVE"
    MOVE_CAPTURE = "MOVE_CAPTURE"
    PUSH = "PUSH"
    SWAP = "SWAP"
    HOP = "HOP"
    CONVERT = "CONVERT"


MOVEMENT_ACTION_KINDS = frozenset(
    (
        ActionKind.MOVE,
        ActionKind.MOVE_CAPTURE,
        ActionKind.PUSH,
        ActionKind.SWAP,
        ActionKind.HOP,
    )
)

VECTOR_ACTION_KINDS = MOVEMENT_ACTION_KINDS | frozenset((ActionKind.CONVERT,))

_SCHEMA_ACTION_KINDS = {
    1: (ActionKind.PLACE, ActionKind.MOVE),
    2: (ActionKind.PLACE, ActionKind.MOVE),
    3: (ActionKind.PLACE, ActionKind.MOVE, ActionKind.MOVE_CAPTURE),
    4: (
        ActionKind.PLACE,
        ActionKind.MOVE,
        ActionKind.MOVE_CAPTURE,
        ActionKind.PUSH,
        ActionKind.SWAP,
        ActionKind.HOP,
        ActionKind.CONVERT,
    ),
}


class GoalKind(str, Enum):
    CONNECT_EDGES = "CONNECT_EDGES"
    REACH_EDGE = "REACH_EDGE"
    ELIMINATE = "ELIMINATE"


_SCHEMA_GOAL_KINDS = {
    1: (GoalKind.CONNECT_EDGES, GoalKind.REACH_EDGE),
    2: (GoalKind.CONNECT_EDGES, GoalKind.REACH_EDGE),
    3: (GoalKind.CONNECT_EDGES, GoalKind.REACH_EDGE),
    4: (GoalKind.CONNECT_EDGES, GoalKind.REACH_EDGE, GoalKind.ELIMINATE),
}


class Edge(str, Enum):
    TOP = "TOP"
    RIGHT = "RIGHT"
    BOTTOM = "BOTTOM"
    LEFT = "LEFT"


class NoLegalActionOutcome(str, Enum):
    DRAW = "DRAW"


Position = Tuple[int, int]
Vector = Tuple[int, int]


class DefinitionError(ValueError):
    """Raised when input is outside the schema or violates a DSL invariant."""


_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,31}$")


@dataclass(frozen=True)
class ActionSpec:
    kind: ActionKind
    piece: str
    vectors: Tuple[Vector, ...] = ()

    def __post_init__(self) -> None:
        if type(self.kind) is not ActionKind:
            raise DefinitionError("action kind must be an ActionKind")
        # Preserve the historical direct-construction behavior for schemas 1--3,
        # while making new v4 vector-action representations closed and immutable
        # from their first public versions.
        if self.kind not in (
            ActionKind.PUSH,
            ActionKind.SWAP,
            ActionKind.HOP,
            ActionKind.CONVERT,
        ):
            return
        label = self.kind.value
        if type(self.piece) is not str or not _IDENTIFIER.fullmatch(self.piece):
            raise DefinitionError(
                "{} action piece must match {}".format(label, _IDENTIFIER.pattern)
            )
        if type(self.vectors) is not tuple or not self.vectors:
            raise DefinitionError(
                "{} action vectors must be a non-empty tuple".format(label)
            )
        if any(
            type(vector) is not tuple
            or len(vector) != 2
            or any(type(coordinate) is not int for coordinate in vector)
            for vector in self.vectors
        ):
            raise DefinitionError(
                "{} action vectors must be two-integer tuples".format(label)
            )
        if any(vector == (0, 0) for vector in self.vectors):
            raise DefinitionError(
                "{} action vectors cannot contain (0, 0)".format(label)
            )
        if any(
            abs(row) > 1 or abs(column) > 1
            for row, column in self.vectors
        ):
            raise DefinitionError(
                "{} action vectors must be one-step offsets".format(label)
            )
        if len(set(self.vectors)) != len(self.vectors):
            raise DefinitionError(
                "{} action vectors cannot contain duplicates".format(label)
            )
        if self.vectors != tuple(sorted(self.vectors)):
            raise DefinitionError(
                "{} action vectors must be canonically sorted".format(label)
            )

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"kind": self.kind.value, "piece": self.piece}
        if self.kind in VECTOR_ACTION_KINDS:
            result["vectors"] = [list(vector) for vector in self.vectors]
        return result


@dataclass(frozen=True)
class GoalSpec:
    kind: GoalKind
    piece: str
    edges: Tuple[Edge, Edge] = ()
    edge: Optional[Edge] = None

    def to_dict(self) -> Dict[str, Any]:
        if type(self.kind) is not GoalKind:
            raise DefinitionError("goal kind must be a GoalKind")
        result: Dict[str, Any] = {"kind": self.kind.value, "piece": self.piece}
        if self.kind is GoalKind.CONNECT_EDGES:
            result["edges"] = [edge.value for edge in self.edges]
        elif self.kind is GoalKind.REACH_EDGE:
            assert self.edge is not None
            result["edge"] = self.edge.value
        elif self.kind is GoalKind.ELIMINATE:
            pass
        else:
            raise DefinitionError("goal has an unsupported kind")
        return result


@dataclass(frozen=True)
class RoleSpec:
    action: ActionSpec
    goal: GoalSpec

    def to_dict(self) -> Dict[str, Any]:
        return {"action": self.action.to_dict(), "goal": self.goal.to_dict()}


@dataclass(frozen=True)
class InitialPiece:
    owner: Player
    piece: str
    position: Position

    def to_dict(self) -> Dict[str, Any]:
        return {
            "owner": self.owner.value,
            "piece": self.piece,
            "position": list(self.position),
        }


@dataclass(frozen=True)
class TerminalPolicy:
    no_legal_action: NoLegalActionOutcome

    def to_dict(self) -> Dict[str, str]:
        return {"no_legal_action": self.no_legal_action.value}


@dataclass(frozen=True)
class GameDefinition:
    schema_version: int
    name: str
    board_size: int
    first_player: Player
    max_plies: int
    roles: Tuple[Tuple[Player, RoleSpec], ...]
    initial_pieces: Tuple[InitialPiece, ...]
    terminal_policy: Optional[TerminalPolicy] = None

    def __post_init__(self) -> None:
        if (
            type(self.schema_version) is not int
            or self.schema_version not in _SCHEMA_ACTION_KINDS
        ):
            raise DefinitionError("game definition has an unsupported schema_version")
        if self.schema_version == 4:
            _validate_schema_v4_definition(self)
            return
        allowed_action_kinds = _SCHEMA_ACTION_KINDS[self.schema_version]
        if any(
            role.action.kind not in allowed_action_kinds for _, role in self.roles
        ):
            raise DefinitionError(
                "schema-v{} definitions contain an unsupported action kind".format(
                    self.schema_version
                )
            )
        allowed_goal_kinds = _SCHEMA_GOAL_KINDS[self.schema_version]
        if any(role.goal.kind not in allowed_goal_kinds for _, role in self.roles):
            raise DefinitionError(
                "schema-v{} definitions contain an unsupported goal kind".format(
                    self.schema_version
                )
            )
        if self.schema_version == 3 and not any(
            role.action.kind is ActionKind.MOVE_CAPTURE for _, role in self.roles
        ):
            raise DefinitionError(
                "schema-v3 definitions require at least one MOVE_CAPTURE action"
            )
        if self.schema_version in (1, 3):
            if self.terminal_policy is not None:
                raise DefinitionError(
                    "schema-v{} definitions cannot define terminal_policy".format(
                        self.schema_version
                    )
                )
            return
        if (
            not isinstance(self.terminal_policy, TerminalPolicy)
            or self.terminal_policy.no_legal_action
            is not NoLegalActionOutcome.DRAW
        ):
            raise DefinitionError(
                "schema-v2 definitions require terminal_policy.no_legal_action = DRAW"
            )

    def role(self, player: Player) -> RoleSpec:
        for candidate, role in self.roles:
            if candidate is player:
                return role
        raise AssertionError("validated definition is missing a role")

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "schema_version": self.schema_version,
            "name": self.name,
            "board_size": self.board_size,
            "first_player": self.first_player.value,
            "max_plies": self.max_plies,
            "roles": {
                player.value: self.role(player).to_dict()
                for player in (Player.A, Player.B)
            },
            "initial_pieces": [piece.to_dict() for piece in self.initial_pieces],
        }
        if self.terminal_policy is not None:
            result["terminal_policy"] = self.terminal_policy.to_dict()
        return result


_OPPOSITE_EDGE_SETS = {
    frozenset((Edge.TOP, Edge.BOTTOM)),
    frozenset((Edge.LEFT, Edge.RIGHT)),
}


def _require_exact_instance_fields(
    value: Any, expected: Iterable[str], path: str
) -> None:
    try:
        fields = vars(value)
    except TypeError as error:
        raise DefinitionError("{} fields are unavailable".format(path)) from error
    if type(fields) is not dict or set(fields) != set(expected):
        raise DefinitionError("{} has noncanonical fields".format(path))


def _validate_schema_v4_action(action: Any, path: str) -> None:
    if type(action) is not ActionSpec:
        raise DefinitionError("{} must be an ActionSpec".format(path))
    _require_exact_instance_fields(action, ("kind", "piece", "vectors"), path)
    if type(action.kind) is not ActionKind:
        raise DefinitionError("{}.kind must be an ActionKind".format(path))
    if action.kind not in _SCHEMA_ACTION_KINDS[4]:
        raise DefinitionError("{} has an unsupported action kind".format(path))
    if type(action.piece) is not str or _IDENTIFIER.fullmatch(action.piece) is None:
        raise DefinitionError("{}.piece must match {}".format(path, _IDENTIFIER.pattern))
    if type(action.vectors) is not tuple:
        raise DefinitionError("{}.vectors must be a tuple".format(path))
    if action.kind is ActionKind.PLACE:
        if action.vectors:
            raise DefinitionError("PLACE action cannot define vectors")
        return
    if not action.vectors:
        raise DefinitionError("{}.vectors must be non-empty".format(path))
    if any(
        type(vector) is not tuple
        or len(vector) != 2
        or any(type(coordinate) is not int for coordinate in vector)
        for vector in action.vectors
    ):
        raise DefinitionError("{}.vectors must contain two-integer tuples".format(path))
    if any(vector == (0, 0) for vector in action.vectors):
        raise DefinitionError("{}.vectors cannot contain (0, 0)".format(path))
    if any(
        abs(row) > 1 or abs(column) > 1
        for row, column in action.vectors
    ):
        raise DefinitionError("{}.vectors must be one-step offsets".format(path))
    if len(set(action.vectors)) != len(action.vectors):
        raise DefinitionError("{}.vectors cannot contain duplicates".format(path))
    if action.vectors != tuple(sorted(action.vectors)):
        raise DefinitionError("{}.vectors must be canonically sorted".format(path))


def _validate_schema_v4_goal(goal: Any, path: str) -> None:
    if type(goal) is not GoalSpec:
        raise DefinitionError("{} must be a GoalSpec".format(path))
    _require_exact_instance_fields(
        goal, ("kind", "piece", "edges", "edge"), path
    )
    if type(goal.kind) is not GoalKind:
        raise DefinitionError("{}.kind must be a GoalKind".format(path))
    if type(goal.piece) is not str or _IDENTIFIER.fullmatch(goal.piece) is None:
        raise DefinitionError("{}.piece must match {}".format(path, _IDENTIFIER.pattern))
    if type(goal.edges) is not tuple:
        raise DefinitionError("{}.edges must be a tuple".format(path))
    if goal.kind is GoalKind.CONNECT_EDGES:
        if goal.edge is not None:
            raise DefinitionError("CONNECT_EDGES goal cannot define edge")
        if (
            len(goal.edges) != 2
            or any(type(edge) is not Edge for edge in goal.edges)
            or frozenset(goal.edges) not in _OPPOSITE_EDGE_SETS
        ):
            raise DefinitionError("{}.edges must be an opposite Edge pair".format(path))
        if goal.edges != tuple(sorted(goal.edges, key=lambda edge: edge.value)):
            raise DefinitionError("{}.edges must be canonically sorted".format(path))
        return
    if goal.kind is GoalKind.REACH_EDGE:
        if goal.edges:
            raise DefinitionError("REACH_EDGE goal cannot define edges")
        if type(goal.edge) is not Edge:
            raise DefinitionError("{}.edge must be an Edge".format(path))
        return
    if goal.kind is GoalKind.ELIMINATE:
        if goal.edges:
            raise DefinitionError("ELIMINATE goal cannot define edges")
        if goal.edge is not None:
            raise DefinitionError("ELIMINATE goal cannot define edge")
        return
    raise DefinitionError("{} has an unsupported goal kind".format(path))


def _validate_schema_v4_definition(definition: GameDefinition) -> None:
    """Require direct v4 construction to match parser-normalized values exactly."""

    _require_exact_instance_fields(
        definition,
        (
            "schema_version",
            "name",
            "board_size",
            "first_player",
            "max_plies",
            "roles",
            "initial_pieces",
            "terminal_policy",
        ),
        "schema-v4 definition",
    )
    if (
        type(definition.name) is not str
        or not definition.name.strip()
        or len(definition.name) > 120
        or definition.name != definition.name.strip()
    ):
        raise DefinitionError(
            "schema-v4 name must be a canonical 1-120 character string"
        )
    if (
        type(definition.board_size) is not int
        or not 3 <= definition.board_size <= 5
    ):
        raise DefinitionError("schema-v4 board_size must be an integer from 3 to 5")
    if type(definition.first_player) is not Player:
        raise DefinitionError("schema-v4 first_player must be a Player")
    if (
        type(definition.max_plies) is not int
        or not 1 <= definition.max_plies <= 1000
    ):
        raise DefinitionError("schema-v4 max_plies must be an integer from 1 to 1000")
    if type(definition.roles) is not tuple or len(definition.roles) != 2:
        raise DefinitionError("schema-v4 roles must be a canonical two-role tuple")
    if any(
        type(entry) is not tuple or len(entry) != 2
        for entry in definition.roles
    ):
        raise DefinitionError("schema-v4 role entries must be two-item tuples")
    if any(type(entry[0]) is not Player for entry in definition.roles):
        raise DefinitionError("schema-v4 role owners must be Player values")
    if tuple(entry[0] for entry in definition.roles) != (Player.A, Player.B):
        raise DefinitionError("schema-v4 roles must be ordered uniquely as A then B")
    for player, role in definition.roles:
        if type(role) is not RoleSpec:
            raise DefinitionError(
                "schema-v4 role {} must be a RoleSpec".format(player.value)
            )
        _require_exact_instance_fields(
            role,
            ("action", "goal"),
            "schema-v4 role {}".format(player.value),
        )
        _validate_schema_v4_action(
            role.action, "schema-v4 role {} action".format(player.value)
        )
        _validate_schema_v4_goal(
            role.goal, "schema-v4 role {} goal".format(player.value)
        )
    has_schema_v4_action = any(
        role.action.kind
        in (
            ActionKind.PUSH,
            ActionKind.SWAP,
            ActionKind.HOP,
            ActionKind.CONVERT,
        )
        for _, role in definition.roles
    )
    has_schema_v4_goal = any(
        role.goal.kind is GoalKind.ELIMINATE for _, role in definition.roles
    )
    if not (has_schema_v4_action or has_schema_v4_goal):
        raise DefinitionError(
            "schema-v4 definitions require at least one PUSH, SWAP, HOP, or "
            "CONVERT action, or ELIMINATE goal"
        )
    if definition.terminal_policy is not None:
        raise DefinitionError("schema-v4 definitions cannot define terminal_policy")

    if type(definition.initial_pieces) is not tuple:
        raise DefinitionError("schema-v4 initial_pieces must be a canonical tuple")
    occupied = set()
    for index, piece in enumerate(definition.initial_pieces):
        path = "schema-v4 initial_pieces[{}]".format(index)
        if type(piece) is not InitialPiece:
            raise DefinitionError("{} must be an InitialPiece".format(path))
        _require_exact_instance_fields(
            piece, ("owner", "piece", "position"), path
        )
        if type(piece.owner) is not Player:
            raise DefinitionError("{}.owner must be a Player".format(path))
        if type(piece.piece) is not str or _IDENTIFIER.fullmatch(piece.piece) is None:
            raise DefinitionError("{}.piece must match {}".format(path, _IDENTIFIER.pattern))
        if (
            type(piece.position) is not tuple
            or len(piece.position) != 2
            or any(type(coordinate) is not int for coordinate in piece.position)
        ):
            raise DefinitionError("{}.position must be a two-integer tuple".format(path))
        if not all(0 <= coordinate < definition.board_size for coordinate in piece.position):
            raise DefinitionError("{}.position is outside the board".format(path))
        if piece.position in occupied:
            raise DefinitionError(
                "schema-v4 initial pieces cannot share position {}".format(
                    piece.position
                )
            )
        occupied.add(piece.position)
    if definition.initial_pieces != tuple(
        sorted(
            definition.initial_pieces,
            key=lambda piece: (piece.position, piece.owner.value, piece.piece),
        )
    ):
        raise DefinitionError("schema-v4 initial_pieces must be canonically sorted")


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise DefinitionError("{} must be an object".format(path))
    if not all(isinstance(key, str) for key in value):
        raise DefinitionError("{} keys must be strings".format(path))
    return value


def _exact_keys(value: Mapping[str, Any], expected: Iterable[str], path: str) -> None:
    expected_set = set(expected)
    actual = set(value)
    if actual != expected_set:
        missing = sorted(expected_set - actual)
        unknown = sorted(actual - expected_set)
        parts = []
        if missing:
            parts.append("missing {}".format(missing))
        if unknown:
            parts.append("unknown {}".format(unknown))
        raise DefinitionError("{} has {}".format(path, ", ".join(parts)))


def _integer(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise DefinitionError("{} must be an integer".format(path))
    return value


def _enum(enum_type: Any, value: Any, path: str) -> Any:
    if not isinstance(value, str):
        raise DefinitionError("{} must be a string".format(path))
    try:
        return enum_type(value)
    except ValueError:
        allowed = [member.value for member in enum_type]
        raise DefinitionError("{} must be one of {}".format(path, allowed))


def _piece_name(value: Any, path: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise DefinitionError(
            "{} must match {}".format(path, _IDENTIFIER.pattern)
        )
    return value


def _position(value: Any, path: str) -> Position:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise DefinitionError("{} must be a two-integer array".format(path))
    return (_integer(value[0], path + "[0]"), _integer(value[1], path + "[1]"))


def _parse_action(value: Any, path: str, schema_version: int) -> ActionSpec:
    data = _mapping(value, path)
    if "kind" not in data:
        raise DefinitionError("{} is missing kind".format(path))
    raw_kind = data["kind"]
    allowed_kinds = _SCHEMA_ACTION_KINDS[schema_version]
    allowed_values = [kind.value for kind in allowed_kinds]
    if not isinstance(raw_kind, str):
        raise DefinitionError("{}.kind must be a string".format(path))
    if raw_kind not in allowed_values:
        raise DefinitionError(
            "{}.kind must be one of {}".format(path, allowed_values)
        )
    kind = ActionKind(raw_kind)
    expected = ("kind", "piece") if kind is ActionKind.PLACE else ("kind", "piece", "vectors")
    _exact_keys(data, expected, path)
    piece = _piece_name(data["piece"], path + ".piece")
    if kind is ActionKind.PLACE:
        return ActionSpec(kind=kind, piece=piece)

    raw_vectors = data["vectors"]
    if not isinstance(raw_vectors, (list, tuple)) or not raw_vectors:
        raise DefinitionError("{}.vectors must be a non-empty array".format(path))
    vectors = tuple(_position(item, "{}.vectors[{}]".format(path, index)) for index, item in enumerate(raw_vectors))
    if any(vector == (0, 0) for vector in vectors):
        raise DefinitionError("{}.vectors cannot contain [0, 0]".format(path))
    if any(abs(row) > 1 or abs(column) > 1 for row, column in vectors):
        raise DefinitionError("{}.vectors must be one-step offsets".format(path))
    if len(set(vectors)) != len(vectors):
        raise DefinitionError("{}.vectors cannot contain duplicates".format(path))
    return ActionSpec(kind=kind, piece=piece, vectors=tuple(sorted(vectors)))


def _parse_goal(value: Any, path: str, schema_version: int) -> GoalSpec:
    data = _mapping(value, path)
    if "kind" not in data:
        raise DefinitionError("{} is missing kind".format(path))
    raw_kind = data["kind"]
    allowed_kinds = _SCHEMA_GOAL_KINDS[schema_version]
    allowed_values = [kind.value for kind in allowed_kinds]
    if not isinstance(raw_kind, str):
        raise DefinitionError("{}.kind must be a string".format(path))
    if raw_kind not in allowed_values:
        raise DefinitionError(
            "{}.kind must be one of {}".format(path, allowed_values)
        )
    kind = GoalKind(raw_kind)
    if kind is GoalKind.CONNECT_EDGES:
        _exact_keys(data, ("kind", "piece", "edges"), path)
        raw_edges = data["edges"]
        if not isinstance(raw_edges, (list, tuple)) or len(raw_edges) != 2:
            raise DefinitionError("{}.edges must contain exactly two edges".format(path))
        edges = tuple(_enum(Edge, edge, "{}.edges".format(path)) for edge in raw_edges)
        if frozenset(edges) not in _OPPOSITE_EDGE_SETS:
            raise DefinitionError("{}.edges must be an opposite pair".format(path))
        canonical_edges = tuple(sorted(edges, key=lambda edge: edge.value))
        return GoalSpec(kind=kind, piece=_piece_name(data["piece"], path + ".piece"), edges=canonical_edges)  # type: ignore[arg-type]

    if kind is GoalKind.REACH_EDGE:
        _exact_keys(data, ("kind", "piece", "edge"), path)
        return GoalSpec(
            kind=kind,
            piece=_piece_name(data["piece"], path + ".piece"),
            edge=_enum(Edge, data["edge"], path + ".edge"),
        )

    if kind is GoalKind.ELIMINATE:
        _exact_keys(data, ("kind", "piece"), path)
        return GoalSpec(
            kind=kind,
            piece=_piece_name(data["piece"], path + ".piece"),
        )

    raise AssertionError("allowed goal kind has no parser")


def _parse_role(value: Any, path: str, schema_version: int) -> RoleSpec:
    data = _mapping(value, path)
    _exact_keys(data, ("action", "goal"), path)
    return RoleSpec(
        action=_parse_action(data["action"], path + ".action", schema_version),
        goal=_parse_goal(data["goal"], path + ".goal", schema_version),
    )


def _parse_terminal_policy(value: Any, path: str) -> TerminalPolicy:
    data = _mapping(value, path)
    _exact_keys(data, ("no_legal_action",), path)
    return TerminalPolicy(
        no_legal_action=_enum(
            NoLegalActionOutcome,
            data["no_legal_action"],
            path + ".no_legal_action",
        )
    )


def parse_definition(value: Mapping[str, Any]) -> GameDefinition:
    """Parse and validate one JSON-compatible mapping as a supported definition."""

    data = _mapping(value, "definition")
    base_keys = (
        "schema_version",
        "name",
        "board_size",
        "first_player",
        "max_plies",
        "roles",
        "initial_pieces",
    )
    if "schema_version" not in data:
        _exact_keys(data, base_keys, "definition")
        raise AssertionError("missing schema version passed exact-key validation")
    schema_version = _integer(data["schema_version"], "definition.schema_version")
    if schema_version not in _SCHEMA_ACTION_KINDS:
        raise DefinitionError("definition.schema_version must be one of [1, 2, 3, 4]")
    _exact_keys(
        data,
        (*base_keys, "terminal_policy") if schema_version == 2 else base_keys,
        "definition",
    )
    terminal_policy = (
        _parse_terminal_policy(data["terminal_policy"], "definition.terminal_policy")
        if schema_version == 2
        else None
    )
    name = data["name"]
    if not isinstance(name, str) or not name.strip() or len(name) > 120:
        raise DefinitionError("definition.name must be 1-120 non-whitespace characters")
    board_size = _integer(data["board_size"], "definition.board_size")
    if not 3 <= board_size <= 5:
        raise DefinitionError("definition.board_size must be between 3 and 5")
    max_plies = _integer(data["max_plies"], "definition.max_plies")
    if not 1 <= max_plies <= 1000:
        raise DefinitionError("definition.max_plies must be between 1 and 1000")

    raw_roles = _mapping(data["roles"], "definition.roles")
    _exact_keys(raw_roles, (Player.A.value, Player.B.value), "definition.roles")
    roles = tuple(
        (
            player,
            _parse_role(
                raw_roles[player.value],
                "definition.roles." + player.value,
                schema_version,
            ),
        )
        for player in (Player.A, Player.B)
    )

    raw_pieces = data["initial_pieces"]
    if not isinstance(raw_pieces, (list, tuple)):
        raise DefinitionError("definition.initial_pieces must be an array")
    pieces = []
    occupied = set()
    for index, item in enumerate(raw_pieces):
        path = "definition.initial_pieces[{}]".format(index)
        piece_data = _mapping(item, path)
        _exact_keys(piece_data, ("owner", "piece", "position"), path)
        position = _position(piece_data["position"], path + ".position")
        if not all(0 <= coordinate < board_size for coordinate in position):
            raise DefinitionError("{}.position is outside the board".format(path))
        if position in occupied:
            raise DefinitionError("initial pieces cannot share position {}".format(position))
        occupied.add(position)
        pieces.append(
            InitialPiece(
                owner=_enum(Player, piece_data["owner"], path + ".owner"),
                piece=_piece_name(piece_data["piece"], path + ".piece"),
                position=position,
            )
        )

    canonical_pieces = tuple(
        sorted(pieces, key=lambda piece: (piece.position, piece.owner.value, piece.piece))
    )
    return GameDefinition(
        schema_version=schema_version,
        name=name.strip(),
        board_size=board_size,
        first_player=_enum(Player, data["first_player"], "definition.first_player"),
        max_plies=max_plies,
        roles=roles,
        initial_pieces=canonical_pieces,
        terminal_policy=terminal_policy,
    )


def load_definition(path: Path) -> GameDefinition:
    try:
        with path.open("r", encoding="utf-8") as source:
            value = json.load(source)
    except (OSError, json.JSONDecodeError) as error:
        raise DefinitionError("cannot load {}: {}".format(path, error))
    return parse_definition(value)


def _normalized_definition(definition: GameDefinition) -> GameDefinition:
    if type(definition) is not GameDefinition:
        raise TypeError("canonical DSL operations require a GameDefinition")
    try:
        if definition.schema_version == 4:
            _validate_schema_v4_definition(definition)
        raw = definition.to_dict()
        normalized = parse_definition(raw)
    except (
        AssertionError,
        AttributeError,
        DefinitionError,
        TypeError,
        ValueError,
    ) as error:
        raise DefinitionError("game definition is not parser-normalized") from error
    if normalized != definition or normalized.to_dict() != raw:
        raise DefinitionError("game definition is not parser-normalized")
    return normalized


def canonical_json(definition: GameDefinition) -> str:
    normalized = _normalized_definition(definition)
    return json.dumps(
        normalized.to_dict(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def definition_hash(definition: GameDefinition) -> str:
    return hashlib.sha256(canonical_json(definition).encode("utf-8")).hexdigest()


def describe_rules(definition: GameDefinition) -> Tuple[str, ...]:
    """Derive compact complete prose from the authoritative definition."""

    definition = _normalized_definition(definition)

    statements = [
        "Use a {0} by {0} board.".format(definition.board_size),
    ]
    if definition.initial_pieces:
        setup = ", ".join(
            "{} {} at ({}, {})".format(
                piece.owner.value, piece.piece, piece.position[0], piece.position[1]
            )
            for piece in definition.initial_pieces
        )
        statements.append("Start with " + setup + ".")
    else:
        statements.append("Start with an empty board.")
    statements.append("{} moves first; turns alternate.".format(definition.first_player.value))
    for player in (Player.A, Player.B):
        role = definition.role(player)
        if role.action.kind is ActionKind.PLACE:
            statements.append("{} places one {} in any empty cell.".format(player.value, role.action.piece))
        elif role.action.kind is ActionKind.CONVERT:
            vectors = ", ".join(
                "({}, {})".format(*vector) for vector in role.action.vectors
            )
            statements.append(
                "{} uses one owned {}, which stays in its cell, to convert "
                "exactly one adjacent opponent piece, regardless of kind, by "
                "one of [{}] into an {}-owned {} in that same target cell; "
                "both positions are unchanged, and empty cells, friendly "
                "pieces, ranged conversions, and multi-target conversions are "
                "not allowed.".format(
                    player.value,
                    role.action.piece,
                    vectors,
                    player.value,
                    role.action.piece,
                )
            )
        else:
            vectors = ", ".join("({}, {})".format(*vector) for vector in role.action.vectors)
            statements.append(
                "{} moves one owned {} by one of [{}] to an empty in-bounds cell.".format(
                    player.value, role.action.piece, vectors
                )
            )
            if role.action.kind is ActionKind.MOVE_CAPTURE:
                statements.append(
                    "{} may also move that {} by one of those vectors into an "
                    "in-bounds cell occupied by one opponent piece, remove that "
                    "piece, and finish the move there.".format(
                        player.value, role.action.piece
                    )
                )
            elif role.action.kind is ActionKind.PUSH:
                statements.append(
                    "{} may instead use one of those vectors to push one "
                    "adjacent opponent piece: the {} enters the opponent "
                    "piece's cell, and that piece moves one more cell along "
                    "the same vector; the landing cell must be in bounds and "
                    "empty.".format(player.value, role.action.piece)
                )
            elif role.action.kind is ActionKind.SWAP:
                statements.append(
                    "{} may instead use one of those vectors to swap that {} "
                    "with one adjacent opponent piece; the two pieces exchange "
                    "positions.".format(player.value, role.action.piece)
                )
            elif role.action.kind is ActionKind.HOP:
                statements.append(
                    "{} may instead use one of those vectors to hop that {} "
                    "over exactly one adjacent occupied piece, regardless of "
                    "owner or kind, to the empty in-bounds cell one more step "
                    "along the same vector; the jumped piece is unchanged, and "
                    "chained hops are not allowed.".format(
                        player.value, role.action.piece
                    )
                )
        if role.goal.kind is GoalKind.CONNECT_EDGES:
            if definition.schema_version == 4:
                statements.append(
                    "{}'s goal is to orthogonally connect {} with owned {} "
                    "pieces.".format(
                        player.value,
                        " and ".join(
                            edge.value.lower() for edge in role.goal.edges
                        ),
                        role.goal.piece,
                    )
                )
            else:
                statements.append(
                    "{} wins after its action by orthogonally connecting {} with {} pieces.".format(
                        player.value,
                        " and ".join(edge.value.lower() for edge in role.goal.edges),
                        role.goal.piece,
                    )
                )
        elif role.goal.kind is GoalKind.REACH_EDGE:
            assert role.goal.edge is not None
            if definition.schema_version == 4:
                statements.append(
                    "{}'s goal is for an owned {} to reach the {} edge.".format(
                        player.value,
                        role.goal.piece,
                        role.goal.edge.value.lower(),
                    )
                )
            else:
                statements.append(
                    "{} wins after its action when an owned {} reaches the {} edge.".format(
                        player.value, role.goal.piece, role.goal.edge.value.lower()
                    )
                )
        elif role.goal.kind is GoalKind.ELIMINATE:
            statements.append(
                "{}'s goal is to have no opponent-owned {} pieces remaining.".format(
                    player.value, role.goal.piece
                )
            )
        else:
            raise AssertionError("validated definition has an unsupported goal kind")
    if definition.schema_version == 4:
        first = definition.first_player
        second = first.other
        statements.append(
            "Initially, check {}'s goal first and {}'s goal second; the owner "
            "of the first satisfied goal wins.".format(first.value, second.value)
        )
        statements.append(
            "If neither initial goal is satisfied and {} has no legal action, "
            "{} wins.".format(first.value, second.value)
        )
        statements.append(
            "After each action, check the actor's goal first and the opponent's "
            "goal second; the owner of the first satisfied goal wins."
        )
        statements.append(
            "If neither goal is satisfied, reaching {} plies is a draw before "
            "checking the next player's legal actions.".format(
                definition.max_plies
            )
        )
        statements.append("Otherwise, a next player with no legal action loses.")
    elif definition.terminal_policy is None:
        statements.append("A player with no legal action loses.")
        statements.append(
            "If no one wins within {} plies, the game is a draw.".format(
                definition.max_plies
            )
        )
    else:
        assert (
            definition.terminal_policy.no_legal_action
            is NoLegalActionOutcome.DRAW
        )
        statements.append(
            "If no one wins within {} plies, the game is a draw.".format(
                definition.max_plies
            )
        )
        statements.append(
            "If a player has no legal action, the game is a draw; after an "
            "action, goal and ply-limit endings take precedence."
        )
    return tuple(statements)
