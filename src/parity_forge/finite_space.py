"""Finite, draw-free TILE/TRAIL game core for Plan 0032.

This namespace is deliberately independent from the historical game DSL.  Its
closed grammar makes termination structural: every action consumes at least one
cell of finite empty/open capacity, and an immobile player loses.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
import re
from typing import Any, Iterable, Mapping, Optional, Tuple

from .dsl import DefinitionError, Player


FORMAT = "parity-forge:finite-space:v1"
TERMINAL_RULE = "NO_LEGAL_ACTION_LOSES"
HASH_DOMAIN = b"parity-forge:finite-space-definition:v1\n"
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_-]{0,79}$")
Position = Tuple[int, int]
Shape = Tuple[Position, ...]


@dataclass(frozen=True)
class Role:
    kind: str
    shapes: Tuple[Shape, ...] = ()
    vectors: Tuple[Position, ...] = ()
    max_distance: int = 0
    starts: Tuple[Position, ...] = ()


@dataclass(frozen=True)
class Definition:
    id: str
    rows: int
    cols: int
    blocked: Tuple[Position, ...]
    first_player: Player
    roles: Tuple[Role, Role]

    def role(self, player: Player) -> Role:
        if type(player) is not Player:
            raise DefinitionError("role player must be Player")
        return self.roles[0 if player is Player.A else 1]


@dataclass(frozen=True)
class State:
    closed: int
    a: Tuple[int, ...]
    b: Tuple[int, ...]
    to_move: Player
    plies: int
    winner: Optional[Player] = None


@dataclass(frozen=True, order=True)
class Action:
    kind: str
    cells: Tuple[int, ...] = ()
    source: int = -1
    destination: int = -1

    def __post_init__(self) -> None:
        if type(self.kind) is not str:
            raise ValueError("action kind must be an exact string")
        if self.kind == "TILE":
            if (
                not self.cells
                or self.cells != tuple(sorted(set(self.cells)))
                or any(type(cell) is not int or cell < 0 for cell in self.cells)
                or self.source != -1
                or self.destination != -1
            ):
                raise ValueError("invalid TILE action fields")
        elif self.kind == "TRAIL":
            if (
                self.cells
                or type(self.source) is not int
                or type(self.destination) is not int
                or self.source < 0
                or self.destination < 0
                or self.source == self.destination
            ):
                raise ValueError("invalid TRAIL action fields")
        else:
            raise ValueError("action kind must be TILE or TRAIL")


def _validate_action(action: Action) -> None:
    """Revalidate even frozen actions at every public trust boundary."""

    if type(action) is not Action:
        raise ValueError("action must be Action")
    try: fields = vars(action)
    except TypeError as error: raise ValueError("action fields are unavailable") from error
    if type(fields) is not dict or set(fields) != {"kind", "cells", "source", "destination"}:
        raise ValueError("action fields differ")
    if type(action.kind) is not str:
        raise ValueError("action kind must be an exact string")
    if type(action.cells) is not tuple:
        raise ValueError("action cells must be a tuple")
    if action.kind == "TILE":
        if (
            not action.cells
            or action.cells != tuple(sorted(set(action.cells)))
            or any(type(cell) is not int or cell < 0 for cell in action.cells)
            or type(action.source) is not int or type(action.destination) is not int
            or action.source != -1 or action.destination != -1
        ):
            raise ValueError("invalid TILE action fields")
    elif action.kind == "TRAIL":
        if (
            action.cells
            or type(action.source) is not int or type(action.destination) is not int
            or action.source < 0 or action.destination < 0
            or action.source == action.destination
        ):
            raise ValueError("invalid TRAIL action fields")
    else:
        raise ValueError("action kind must be TILE or TRAIL")


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or not all(type(key) is str for key in value):
        raise DefinitionError("{} must be an object with string keys".format(path))
    return value


def _keys(value: Mapping[str, Any], expected: Iterable[str], path: str) -> None:
    expected = set(expected)
    actual = set(value)
    if actual != expected:
        raise DefinitionError(
            "{} keys differ: missing={} unknown={}".format(
                path, sorted(expected - actual), sorted(actual - expected)
            )
        )


def _integer(value: Any, path: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise DefinitionError(
            "{} must be an integer in [{}, {}]".format(path, minimum, maximum)
        )
    return value


def _position(value: Any, path: str) -> Position:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise DefinitionError("{} must be a two-integer coordinate".format(path))
    return (
        _integer(value[0], path + "[0]", -32, 32),
        _integer(value[1], path + "[1]", -32, 32),
    )


def _board_position(value: Any, path: str, rows: int, cols: int) -> Position:
    position = _position(value, path)
    if not (0 <= position[0] < rows and 0 <= position[1] < cols):
        raise DefinitionError("{} is outside the board".format(path))
    return position


def _unique_positions(
    value: Any, path: str, rows: int, cols: int, *, nonempty: bool, maximum: int
) -> Tuple[Position, ...]:
    if not isinstance(value, (list, tuple)) or (nonempty and not value) or len(value) > maximum:
        raise DefinitionError("{} has an invalid item count".format(path))
    positions = tuple(
        _board_position(item, "{}[{}]".format(path, index), rows, cols)
        for index, item in enumerate(value)
    )
    if len(set(positions)) != len(positions):
        raise DefinitionError("{} cannot contain duplicates".format(path))
    return tuple(sorted(positions))


def _connected(shape: Shape) -> bool:
    remaining = set(shape)
    frontier = [next(iter(remaining))]
    visited = set(frontier)
    while frontier:
        row, col = frontier.pop()
        for neighbor in ((row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1)):
            if neighbor in remaining and neighbor not in visited:
                visited.add(neighbor)
                frontier.append(neighbor)
    return len(visited) == len(shape)


def _parse_role(value: Any, path: str, rows: int, cols: int) -> Role:
    data = _mapping(value, path)
    kind = data.get("kind")
    if type(kind) is not str:
        raise DefinitionError("{}.kind must be an exact string".format(path))
    if kind == "TILE":
        _keys(data, ("kind", "shapes"), path)
        raw_shapes = data["shapes"]
        if not isinstance(raw_shapes, (list, tuple)) or not 1 <= len(raw_shapes) <= 16:
            raise DefinitionError("{}.shapes must contain 1..16 shapes".format(path))
        shapes = []
        for index, raw_shape in enumerate(raw_shapes):
            shape_path = "{}.shapes[{}]".format(path, index)
            shape = _unique_positions(
                raw_shape, shape_path, rows, cols, nonempty=True, maximum=8
            )
            if min(row for row, _ in shape) != 0 or min(col for _, col in shape) != 0:
                raise DefinitionError("{} must have minimum row and column zero".format(shape_path))
            if not _connected(shape):
                raise DefinitionError("{} must be orthogonally connected".format(shape_path))
            shapes.append(shape)
        if len(set(shapes)) != len(shapes):
            raise DefinitionError("{}.shapes contains equivalent translations".format(path))
        return Role(kind="TILE", shapes=tuple(sorted(shapes)))
    if kind == "TRAIL":
        _keys(data, ("kind", "vectors", "max_distance", "starts"), path)
        raw_vectors = data["vectors"]
        if not isinstance(raw_vectors, (list, tuple)) or not 1 <= len(raw_vectors) <= 8:
            raise DefinitionError("{}.vectors must contain 1..8 vectors".format(path))
        vectors = tuple(
            _position(item, "{}.vectors[{}]".format(path, index))
            for index, item in enumerate(raw_vectors)
        )
        if (
            any(vector == (0, 0) or max(abs(vector[0]), abs(vector[1])) != 1 for vector in vectors)
            or len(set(vectors)) != len(vectors)
        ):
            raise DefinitionError("{}.vectors must be distinct nonzero unit-neighborhood vectors".format(path))
        starts = _unique_positions(
            data["starts"], path + ".starts", rows, cols, nonempty=True, maximum=16
        )
        return Role(
            kind="TRAIL",
            vectors=tuple(sorted(vectors)),
            max_distance=_integer(data["max_distance"], path + ".max_distance", 1, 32),
            starts=starts,
        )
    raise DefinitionError("{}.kind must be TILE or TRAIL".format(path))


def parse_definition(value: Mapping[str, Any]) -> Definition:
    data = _mapping(value, "definition")
    _keys(data, ("format", "id", "board", "first_player", "terminal_rule", "roles"), "definition")
    if type(data["format"]) is not str or data["format"] != FORMAT:
        raise DefinitionError("definition.format differs")
    identifier = data["id"]
    if type(identifier) is not str or _IDENTIFIER.fullmatch(identifier) is None:
        raise DefinitionError("definition.id is not a bounded safe identifier")
    board = _mapping(data["board"], "definition.board")
    _keys(board, ("rows", "cols", "blocked"), "definition.board")
    rows = _integer(board["rows"], "definition.board.rows", 1, 32)
    cols = _integer(board["cols"], "definition.board.cols", 1, 32)
    blocked = _unique_positions(
        board["blocked"], "definition.board.blocked", rows, cols, nonempty=False, maximum=rows * cols
    )
    if type(data["first_player"]) is not str or data["first_player"] not in ("A", "B"):
        raise DefinitionError("definition.first_player must be A or B")
    if type(data["terminal_rule"]) is not str or data["terminal_rule"] != TERMINAL_RULE:
        raise DefinitionError("definition.terminal_rule differs")
    roles = _mapping(data["roles"], "definition.roles")
    _keys(roles, ("A", "B"), "definition.roles")
    parsed_roles = (
        _parse_role(roles["A"], "definition.roles.A", rows, cols),
        _parse_role(roles["B"], "definition.roles.B", rows, cols),
    )
    starts = parsed_roles[0].starts + parsed_roles[1].starts
    if len(set(starts)) != len(starts) or set(starts) & set(blocked):
        raise DefinitionError("starting pieces overlap each other or blocked cells")
    definition = Definition(identifier, rows, cols, blocked, Player(data["first_player"]), parsed_roles)
    _validate_definition(definition)
    return definition


def _fields(value: Any, expected: Iterable[str], path: str) -> None:
    try:
        actual = vars(value)
    except TypeError as error:
        raise DefinitionError("{} fields are unavailable".format(path)) from error
    if type(actual) is not dict or set(actual) != set(expected):
        raise DefinitionError("{} fields differ".format(path))


def _validate_role(role: Role, path: str, rows: int, cols: int) -> None:
    if type(role) is not Role:
        raise DefinitionError("{} must be Role".format(path))
    _fields(role, ("kind", "shapes", "vectors", "max_distance", "starts"), path)
    if (
        type(role.kind) is not str
        or type(role.shapes) is not tuple
        or type(role.vectors) is not tuple
        or type(role.max_distance) is not int
        or type(role.starts) is not tuple
        or any(type(shape) is not tuple for shape in role.shapes)
        or any(type(position) is not tuple for shape in role.shapes for position in shape)
        or any(type(vector) is not tuple for vector in role.vectors)
        or any(type(start) is not tuple for start in role.starts)
    ):
        raise DefinitionError("{} fields must use exact canonical scalar/tuple types".format(path))
    # The serializer/parser round trip is the single canonical-role validator.
    if role.kind == "TILE":
        raw = {"kind": "TILE", "shapes": [[list(cell) for cell in shape] for shape in role.shapes]}
    elif role.kind == "TRAIL":
        raw = {
            "kind": "TRAIL",
            "vectors": [list(vector) for vector in role.vectors],
            "max_distance": role.max_distance,
            "starts": [list(start) for start in role.starts],
        }
    else:
        raise DefinitionError("{}.kind differs".format(path))
    if _parse_role(raw, path, rows, cols) != role:
        raise DefinitionError("{} is not canonical".format(path))


def _validate_definition(definition: Definition) -> None:
    if type(definition) is not Definition:
        raise DefinitionError("definition must be Definition")
    _fields(definition, ("id", "rows", "cols", "blocked", "first_player", "roles"), "definition")
    if type(definition.id) is not str or _IDENTIFIER.fullmatch(definition.id) is None:
        raise DefinitionError("definition.id differs")
    if type(definition.rows) is not int or type(definition.cols) is not int or not (
        1 <= definition.rows <= 32 and 1 <= definition.cols <= 32
    ):
        raise DefinitionError("definition dimensions differ")
    if type(definition.blocked) is not tuple or definition.blocked != tuple(sorted(set(definition.blocked))):
        raise DefinitionError("definition.blocked is not canonical")
    for position in definition.blocked:
        if type(position) is not tuple:
            raise DefinitionError("definition.blocked positions must be exact tuples")
        _board_position(position, "definition.blocked", definition.rows, definition.cols)
    if type(definition.first_player) is not Player:
        raise DefinitionError("definition.first_player differs")
    if type(definition.roles) is not tuple or len(definition.roles) != 2:
        raise DefinitionError("definition.roles differs")
    for index, role in enumerate(definition.roles):
        _validate_role(role, "definition.roles.{}".format("AB"[index]), definition.rows, definition.cols)
    starts = definition.roles[0].starts + definition.roles[1].starts
    if len(set(starts)) != len(starts) or set(starts) & set(definition.blocked):
        raise DefinitionError("definition starting occupancy differs")


def definition_to_dict(definition: Definition) -> dict:
    _validate_definition(definition)
    role_wires = {}
    for player in (Player.A, Player.B):
        role = definition.role(player)
        role_wires[player.value] = (
            {"kind": "TILE", "shapes": [[list(cell) for cell in shape] for shape in role.shapes]}
            if role.kind == "TILE"
            else {
                "kind": "TRAIL",
                "vectors": [list(vector) for vector in role.vectors],
                "max_distance": role.max_distance,
                "starts": [list(start) for start in role.starts],
            }
        )
    return {
        "format": FORMAT,
        "id": definition.id,
        "board": {
            "rows": definition.rows,
            "cols": definition.cols,
            "blocked": [list(position) for position in definition.blocked],
        },
        "first_player": definition.first_player.value,
        "terminal_rule": TERMINAL_RULE,
        "roles": role_wires,
    }


def canonical_json(definition: Definition) -> str:
    return json.dumps(
        definition_to_dict(definition), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    )


def definition_hash(definition: Definition) -> str:
    wire = definition_to_dict(definition)
    del wire["id"]
    payload = json.dumps(
        wire, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(HASH_DOMAIN + payload).hexdigest()


def _index(definition: Definition, position: Position) -> int:
    return position[0] * definition.cols + position[1]


def _coordinate(definition: Definition, index: int) -> Position:
    return divmod(index, definition.cols)


def _blocked_mask(definition: Definition) -> int:
    return sum(1 << _index(definition, position) for position in definition.blocked)


def _validate_state(definition: Definition, state: State) -> Tuple[Action, ...]:
    _validate_definition(definition)
    if type(state) is not State:
        raise ValueError("state must be State")
    _fields(state, ("closed", "a", "b", "to_move", "plies", "winner"), "state")
    cells = definition.rows * definition.cols
    if type(state.closed) is not int or state.closed < 0 or state.closed >> cells:
        raise ValueError("state.closed is outside the board")
    if state.closed & _blocked_mask(definition) != _blocked_mask(definition):
        raise ValueError("state.closed omitted a blocked cell")
    for label, positions in (("a", state.a), ("b", state.b)):
        if (
            type(positions) is not tuple
            or positions != tuple(sorted(set(positions)))
            or any(type(cell) is not int or not 0 <= cell < cells for cell in positions)
        ):
            raise ValueError("state.{} is not canonical".format(label))
    occupied = set(state.a) | set(state.b)
    if len(occupied) != len(state.a) + len(state.b) or any(state.closed & (1 << cell) for cell in occupied):
        raise ValueError("state occupancy overlaps")
    for player, positions in ((Player.A, state.a), (Player.B, state.b)):
        role = definition.role(player)
        if role.kind == "TRAIL" and len(positions) != len(role.starts):
            raise ValueError("TRAIL piece count changed")
    if type(state.to_move) is not Player or type(state.plies) is not int or state.plies < 0:
        raise ValueError("state turn fields differ")
    expected = definition.first_player if state.plies % 2 == 0 else definition.first_player.other
    if state.to_move is not expected:
        raise ValueError("state turn does not match ply parity")
    if state.winner is not None and type(state.winner) is not Player:
        raise ValueError("state winner must be Player or None")
    if state.winner is not None and state.winner is not state.to_move.other:
        raise ValueError("terminal winner must be the immobile player's opponent")
    current_actions = _actions_unchecked(definition, state, state.to_move)
    if (state.winner is None) != bool(current_actions):
        raise ValueError("state winner must exactly represent current immobility")
    return current_actions


def _actions_unchecked(definition: Definition, state: State, player: Player) -> Tuple[Action, ...]:
    role = definition.role(player)
    occupied = set(state.a) | set(state.b)
    unavailable = occupied | {cell for cell in range(definition.rows * definition.cols) if state.closed & (1 << cell)}
    actions = set()
    if role.kind == "TILE":
        for cells in _tile_placements(definition.rows, definition.cols, role.shapes):
            if not set(cells) & unavailable:
                actions.add(Action("TILE", cells=cells))
    else:
        pieces = state.a if player is Player.A else state.b
        for source in pieces:
            row, col = _coordinate(definition, source)
            for delta_row, delta_col in role.vectors:
                for distance in range(1, role.max_distance + 1):
                    target = (row + delta_row * distance, col + delta_col * distance)
                    if not (0 <= target[0] < definition.rows and 0 <= target[1] < definition.cols):
                        break
                    destination = _index(definition, target)
                    if destination in unavailable:
                        break
                    actions.add(Action("TRAIL", source=source, destination=destination))
    return tuple(sorted(actions))


@lru_cache(maxsize=16)
def _tile_placements(rows: int, cols: int, shapes: Tuple[Shape, ...]) -> Tuple[Tuple[int, ...], ...]:
    """Cache inert integer geometry, never caller-visible Action objects."""

    actions = set()
    for shape in shapes:
        height = max(row for row, _ in shape) + 1
        width = max(col for _, col in shape) + 1
        for base_row in range(rows - height + 1):
            for base_col in range(cols - width + 1):
                actions.add(
                    tuple(
                        sorted(
                            (base_row + row) * cols + base_col + col
                            for row, col in shape
                        )
                    )
                )
    return tuple(sorted(actions))


def initial_state(definition: Definition) -> State:
    _validate_definition(definition)
    positions = []
    for role in definition.roles:
        positions.append(tuple(sorted(_index(definition, start) for start in role.starts)))
    state = State(_blocked_mask(definition), positions[0], positions[1], definition.first_player, 0)
    if not _actions_unchecked(definition, state, state.to_move):
        state = State(state.closed, state.a, state.b, state.to_move, 0, state.to_move.other)
    return state


def legal_actions(
    definition: Definition, state: State, player: Optional[Player] = None
) -> Tuple[Action, ...]:
    current_actions = _validate_state(definition, state)
    if player is not None and type(player) is not Player:
        raise ValueError("optional player must be Player")
    if state.winner is not None:
        return ()
    actor = state.to_move if player is None else player
    return current_actions if actor is state.to_move else _actions_unchecked(definition, state, actor)


def free_cells(definition: Definition, state: State) -> int:
    _validate_state(definition, state)
    return _free_cells_unchecked(definition, state)


def _free_cells_unchecked(definition: Definition, state: State) -> int:
    return definition.rows * definition.cols - bin(state.closed).count("1") - len(state.a) - len(state.b)


def apply_action(definition: Definition, state: State, action: Action) -> State:
    current_actions = _validate_state(definition, state)
    if state.winner is not None:
        raise ValueError("cannot move after terminality")
    _validate_action(action)
    if action not in current_actions:
        raise ValueError("action is not a current canonical legal action")
    before = _free_cells_unchecked(definition, state)
    a, b, closed = list(state.a), list(state.b), state.closed
    actor_cells = a if state.to_move is Player.A else b
    if action.kind == "TILE":
        actor_cells.extend(action.cells)
        actor_cells.sort()
        expected_decrease = len(action.cells)
    else:
        actor_cells.remove(action.source)
        actor_cells.append(action.destination)
        actor_cells.sort()
        closed |= 1 << action.source
        expected_decrease = 1
    candidate = State(closed, tuple(a), tuple(b), state.to_move.other, state.plies + 1)
    after = _free_cells_unchecked(definition, candidate)
    if before - after != expected_decrease or expected_decrease < 1:
        raise AssertionError("finite-space capacity failed to strictly decrease")
    if not _actions_unchecked(definition, candidate, candidate.to_move):
        candidate = State(candidate.closed, candidate.a, candidate.b, candidate.to_move, candidate.plies, state.to_move)
    return candidate


def action_to_dict(definition: Definition, action: Action) -> dict:
    _validate_definition(definition)
    _validate_action(action)
    if action.kind == "TILE":
        if any(not 0 <= cell < definition.rows * definition.cols for cell in action.cells):
            raise ValueError("TILE action cell is outside the board")
        return {"kind": "TILE", "cells": [list(_coordinate(definition, cell)) for cell in action.cells]}
    if action.kind == "TRAIL":
        if any(not 0 <= cell < definition.rows * definition.cols for cell in (action.source, action.destination)):
            raise ValueError("TRAIL action cell is outside the board")
        return {
            "kind": "TRAIL",
            "from": list(_coordinate(definition, action.source)),
            "to": list(_coordinate(definition, action.destination)),
        }
    raise ValueError("unknown action kind")


def action_from_dict(definition: Definition, value: Mapping[str, Any]) -> Action:
    _validate_definition(definition)
    data = _mapping(value, "action")
    if type(data.get("kind")) is not str:
        raise ValueError("action.kind must be an exact string")
    if data.get("kind") == "TILE":
        _keys(data, ("kind", "cells"), "action")
        if not isinstance(data["cells"], (list, tuple)) or not data["cells"]:
            raise ValueError("TILE action cells must be nonempty")
        coordinates = tuple(
            _board_position(cell, "action.cells[{}]".format(index), definition.rows, definition.cols)
            for index, cell in enumerate(data["cells"])
        )
        cells = tuple(_index(definition, cell) for cell in coordinates)
        if cells != tuple(sorted(set(cells))):
            raise ValueError("TILE action cells must be canonical and unique")
        return Action("TILE", cells=cells)
    if data.get("kind") == "TRAIL":
        _keys(data, ("kind", "from", "to"), "action")
        source = _index(definition, _board_position(data["from"], "action.from", definition.rows, definition.cols))
        destination = _index(definition, _board_position(data["to"], "action.to", definition.rows, definition.cols))
        return Action("TRAIL", source=source, destination=destination)
    raise ValueError("action.kind must be TILE or TRAIL")


def state_to_dict(definition: Definition, state: State) -> dict:
    _validate_state(definition, state)
    positions = lambda values: [list(_coordinate(definition, cell)) for cell in values]
    closed = positions(tuple(cell for cell in range(definition.rows * definition.cols) if state.closed & (1 << cell)))
    return {
        "closed": closed,
        "A": positions(state.a),
        "B": positions(state.b),
        "to_move": state.to_move.value,
        "plies": state.plies,
        "winner": None if state.winner is None else state.winner.value,
    }


def replay(definition: Definition, action_dicts: Iterable[Mapping[str, Any]]) -> State:
    state = initial_state(definition)
    for raw in action_dicts:
        state = apply_action(definition, state, action_from_dict(definition, raw))
    return state


def termination_certificate(definition: Definition) -> dict:
    state = initial_state(definition)
    capacity = free_cells(definition, state)
    return {
        "proof_type": "STRICT_EMPTY_CAPACITY",
        "initial_capacity": capacity,
        "maximum_legal_plies": capacity,
        "terminal_rule": TERMINAL_RULE,
        "decrease_laws": {
            "TILE": "PLACED_SHAPE_AREA_AT_LEAST_1",
            "TRAIL": "EXACTLY_1_ORIGIN_BECOMES_CLOSED",
        },
    }


def _transforms(position: Position) -> Tuple[Position, ...]:
    row, col = position
    return (
        (row, col), (row, -col), (-row, col), (-row, -col),
        (col, row), (col, -row), (-col, row), (-col, -row),
    )


def _shape_images(shapes: Tuple[Shape, ...]) -> set:
    images = set()
    for transform in range(8):
        transformed = []
        for shape in shapes:
            points = [_transforms(point)[transform] for point in shape]
            min_row = min(row for row, _ in points)
            min_col = min(col for _, col in points)
            transformed.append(tuple(sorted((row - min_row, col - min_col) for row, col in points)))
        images.add(tuple(sorted(transformed)))
    return images


def _effective_vectors(role: Role, rows: int, cols: int) -> Tuple[Tuple[Position, int], ...]:
    result = []
    for vector in role.vectors:
        row, col = vector
        reachable = min(role.max_distance, rows - 1 if row else 32, cols - 1 if col else 32)
        if reachable:
            result.append((vector, reachable))
    return tuple(sorted(result))


def _common_cap_vectors(role: Role, rows: int, cols: int) -> Tuple[Tuple[Position, int], ...]:
    cap = min(role.max_distance, max(rows, cols) - 1)
    return () if cap == 0 else tuple((vector, cap) for vector in role.vectors)


def _vector_images(vectors: Tuple[Tuple[Position, int], ...]) -> set:
    return {tuple(sorted((_transforms(vector)[transform], reach) for vector, reach in vectors))
            for transform in range(8)}


def asymmetry_witness(definition: Definition) -> dict:
    _validate_definition(definition)
    first, second = definition.roles
    if first.kind != second.kind:
        return {"mechanically_asymmetric": True, "reason": "DIFFERENT_ACTION_KINDS"}
    if first.kind == "TILE":
        if second.shapes not in _shape_images(first.shapes):
            return {"mechanically_asymmetric": True, "reason": "INEQUIVALENT_TILE_SHAPE_SETS"}
    else:
        if len(first.starts) != len(second.starts):
            return {"mechanically_asymmetric": True, "reason": "DIFFERENT_TRAIL_PIECE_COUNTS"}
        first_common = _common_cap_vectors(first, definition.rows, definition.cols)
        second_common = _common_cap_vectors(second, definition.rows, definition.cols)
        if second_common in _vector_images(first_common):
            return {"mechanically_asymmetric": False, "reason": "NOT_ESTABLISHED"}
        first_effective = _effective_vectors(first, definition.rows, definition.cols)
        second_effective = _effective_vectors(second, definition.rows, definition.cols)
        if second_effective not in _vector_images(first_effective):
            first_ranges = sorted(reach for _vector, reach in first_effective)
            second_ranges = sorted(reach for _vector, reach in second_effective)
            reason = (
                "INEQUIVALENT_TRAIL_EFFECTIVE_RANGES"
                if len(first_ranges) == len(second_ranges) and first_ranges != second_ranges
                else "INEQUIVALENT_TRAIL_DIRECTION_SETS"
            )
            return {"mechanically_asymmetric": True, "reason": reason}
    return {"mechanically_asymmetric": False, "reason": "NOT_ESTABLISHED"}


def describe_rules(definition: Definition) -> Tuple[str, ...]:
    _validate_definition(definition)
    lines = [
        "盤面は{}行×{}列です。".format(definition.rows, definition.cols),
        "先手は{}です。手番で合法手がないプレイヤーが負け、相手だけが勝者です。".format(definition.first_player.value),
        "使用不能マスは{}個です。引き分け、パス、手数上限はありません。".format(len(definition.blocked)),
    ]
    for player in (Player.A, Player.B):
        role = definition.role(player)
        if role.kind == "TILE":
            rendered = ["{" + ",".join("({}, {})".format(*cell) for cell in shape) + "}" for shape in role.shapes]
            lines.append(
                "{}はタイル役です。向きとして明示された形{}を、空いていて閉鎖されていない任意の位置に置きます。".format(player.value, "・".join(rendered))
            )
        else:
            vectors = "・".join("({}, {})".format(*vector) for vector in role.vectors)
            lines.append(
                "{}は軌跡役です。{}個の駒を方向{}へ1〜{}マス動かし、通過先はすべて空所に限り、元のマスを永久閉鎖します。".format(
                    player.value, len(role.starts), vectors, role.max_distance
                )
            )
    return tuple(lines)
