"""Deterministic connection-game rules registered for Plan 0040.

This module contains rules and serialization only.  It deliberately has no
policy, search, filesystem, experiment, or historical-game dependency beyond
the shared :class:`Player` value type.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
import re
from typing import Any, Optional, Tuple

from .dsl import DefinitionError, Player


FORMAT = "parity-forge:connection:v1"
TOPOLOGY = "RHOMBUS_HEX_CELLS"
TERMINAL_RULE = "OPPOSITE_EDGE_CONNECTION"

PLACE_ONE = "PLACE_ONE"
BRIDGE_PAIR = "BRIDGE_PAIR"
PLACE_AND_CONVERT = "PLACE_AND_CONVERT"
ACTION_KINDS = (PLACE_ONE, BRIDGE_PAIR, PLACE_AND_CONVERT)

NEIGHBOR_DELTAS = (
    (-1, 0),
    (-1, 1),
    (0, -1),
    (0, 1),
    (1, -1),
    (1, 0),
)

_DEFINITION_KEYS = {
    "format",
    "id",
    "board",
    "first_player",
    "bridge_credits_A",
    "conversion_credits_B",
    "terminal_rule",
}
_BOARD_KEYS = {"size", "topology"}
_STATE_KEYS = {
    "a",
    "b",
    "bridge_left",
    "conversion_left",
    "to_move",
    "plies",
    "winner",
}
_ACTION_KEYS = {"kind", "cells"}
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_-]{0,79}$")


def _integer(value: Any, label: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(
            "{} must be an integer in [{}, {}]".format(label, minimum, maximum)
        )
    return value


def _definition_integer(
    value: Any, label: str, minimum: int, maximum: int
) -> int:
    try:
        return _integer(value, label, minimum, maximum)
    except ValueError as error:
        raise DefinitionError(str(error)) from error


def _mapping(value: Any, label: str) -> Mapping:
    if not isinstance(value, Mapping) or not all(type(key) is str for key in value):
        raise ValueError("{} must be an object with string keys".format(label))
    return value


def _definition_mapping(value: Any, label: str) -> Mapping:
    try:
        return _mapping(value, label)
    except ValueError as error:
        raise DefinitionError(str(error)) from error


def _keys(value: Mapping, expected: Iterable[str], label: str) -> None:
    expected_set = set(expected)
    actual = set(value)
    if actual != expected_set:
        raise ValueError(
            "{} keys differ: missing={} unknown={}".format(
                label,
                sorted(expected_set - actual),
                sorted(actual - expected_set),
            )
        )


def _definition_keys(value: Mapping, expected: Iterable[str], label: str) -> None:
    try:
        _keys(value, expected, label)
    except ValueError as error:
        raise DefinitionError(str(error)) from error


def _exact_fields(value: Any, expected: Iterable[str], label: str) -> None:
    try:
        fields = vars(value)
    except TypeError as error:
        raise ValueError("{} fields are unavailable".format(label)) from error
    if type(fields) is not dict or set(fields) != set(expected):
        raise ValueError("{} fields differ".format(label))


@dataclass(frozen=True)
class Definition:
    id: str
    size: int
    first_player: Player
    bridge_credits_A: int
    conversion_credits_B: int

    def __post_init__(self) -> None:
        _validate_definition(self)


@dataclass(frozen=True)
class State:
    a: int
    b: int
    bridge_left: int
    conversion_left: int
    to_move: Player
    plies: int
    winner: Optional[Player]


@dataclass(frozen=True)
class Action:
    kind: str
    cells: Tuple[int, ...]

    def __post_init__(self) -> None:
        _validate_action_shape(self)


def _validate_definition(definition: Definition) -> None:
    if type(definition) is not Definition:
        raise DefinitionError("definition must be an exact Definition")
    try:
        _exact_fields(
            definition,
            (
                "id",
                "size",
                "first_player",
                "bridge_credits_A",
                "conversion_credits_B",
            ),
            "definition",
        )
    except ValueError as error:
        raise DefinitionError(str(error)) from error
    if type(definition.id) is not str or _IDENTIFIER.fullmatch(definition.id) is None:
        raise DefinitionError("definition.id is not a bounded safe identifier")
    _definition_integer(definition.size, "definition.size", 2, 19)
    if type(definition.first_player) is not Player:
        raise DefinitionError("definition.first_player must be Player.A or Player.B")
    _definition_integer(
        definition.bridge_credits_A, "definition.bridge_credits_A", 0, 9
    )
    _definition_integer(
        definition.conversion_credits_B, "definition.conversion_credits_B", 0, 9
    )


def _require_definition(definition: Definition) -> None:
    _validate_definition(definition)


def _definition_to_dict(definition: Definition) -> dict:
    _require_definition(definition)
    return {
        "format": FORMAT,
        "id": definition.id,
        "board": {"size": definition.size, "topology": TOPOLOGY},
        "first_player": definition.first_player.value,
        "bridge_credits_A": definition.bridge_credits_A,
        "conversion_credits_B": definition.conversion_credits_B,
        "terminal_rule": TERMINAL_RULE,
    }


def parse_definition(value: Mapping[str, Any]) -> Definition:
    """Parse the exact registered connection-definition wire schema."""

    data = _definition_mapping(value, "definition")
    _definition_keys(data, _DEFINITION_KEYS, "definition")
    if type(data["format"]) is not str or data["format"] != FORMAT:
        raise DefinitionError("definition.format differs")
    identifier = data["id"]
    if type(identifier) is not str or _IDENTIFIER.fullmatch(identifier) is None:
        raise DefinitionError("definition.id is not a bounded safe identifier")
    board = _definition_mapping(data["board"], "definition.board")
    _definition_keys(board, _BOARD_KEYS, "definition.board")
    size = _definition_integer(board["size"], "definition.board.size", 2, 19)
    if type(board["topology"]) is not str or board["topology"] != TOPOLOGY:
        raise DefinitionError("definition.board.topology differs")
    if type(data["first_player"]) is not str or data["first_player"] not in (
        "A",
        "B",
    ):
        raise DefinitionError("definition.first_player must be A or B")
    bridge = _definition_integer(
        data["bridge_credits_A"], "definition.bridge_credits_A", 0, 9
    )
    conversion = _definition_integer(
        data["conversion_credits_B"], "definition.conversion_credits_B", 0, 9
    )
    if (
        type(data["terminal_rule"]) is not str
        or data["terminal_rule"] != TERMINAL_RULE
    ):
        raise DefinitionError("definition.terminal_rule differs")
    return Definition(identifier, size, Player(data["first_player"]), bridge, conversion)


def definition_hash(definition: Definition) -> str:
    """Hash canonical ASCII JSON after removing only the nonsemantic id."""

    wire = _definition_to_dict(definition)
    del wire["id"]
    canonical = json.dumps(
        wire,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(canonical).hexdigest()


def _cell_count(definition: Definition) -> int:
    return definition.size * definition.size


def _full_mask(definition: Definition) -> int:
    return (1 << _cell_count(definition)) - 1


def _validate_board_masks(definition: Definition, a: int, b: int) -> None:
    _require_definition(definition)
    maximum = _full_mask(definition)
    _integer(a, "a mask", 0, maximum)
    _integer(b, "b mask", 0, maximum)
    if a & b:
        raise ValueError("A and B masks must be disjoint")


@lru_cache(maxsize=None)
def _neighbors_for_size(size: int, index: int) -> Tuple[int, ...]:
    row, column = divmod(index, size)
    result = []
    for delta_row, delta_column in NEIGHBOR_DELTAS:
        neighbor_row = row + delta_row
        neighbor_column = column + delta_column
        if 0 <= neighbor_row < size and 0 <= neighbor_column < size:
            result.append(neighbor_row * size + neighbor_column)
    return tuple(sorted(result))


def neighbors(definition: Definition, index: int) -> Tuple[int, ...]:
    """Return canonical row-major Hex neighbors for one cell."""

    _require_definition(definition)
    _integer(index, "cell index", 0, _cell_count(definition) - 1)
    return _neighbors_for_size(definition.size, index)


def _has_connection(definition: Definition, mask: int, player: Player) -> bool:
    size = definition.size
    if player is Player.A:
        frontier = [row * size for row in range(size) if mask & (1 << (row * size))]
        is_target = lambda cell: cell % size == size - 1
    else:
        frontier = [column for column in range(size) if mask & (1 << column)]
        is_target = lambda cell: cell // size == size - 1
    seen = set(frontier)
    while frontier:
        cell = frontier.pop()
        if is_target(cell):
            return True
        for neighbor in _neighbors_for_size(size, cell):
            if mask & (1 << neighbor) and neighbor not in seen:
                seen.add(neighbor)
                frontier.append(neighbor)
    return False


def winner_from_board(definition: Definition, a: int, b: int) -> Optional[Player]:
    """Recompute the unique connection winner, rejecting impossible terminals."""

    _validate_board_masks(definition, a, b)
    a_wins = _has_connection(definition, a, Player.A)
    b_wins = _has_connection(definition, b, Player.B)
    if a_wins and b_wins:
        raise ValueError("invalid terminal board: both players connect")
    if a_wins:
        return Player.A
    if b_wins:
        return Player.B
    if (a | b) == _full_mask(definition):
        raise ValueError("invalid terminal board: full board has no connection")
    return None


def _turn_counts(definition: Definition, plies: int) -> Tuple[int, int]:
    first_turns = (plies + 1) // 2
    second_turns = plies // 2
    if definition.first_player is Player.A:
        return first_turns, second_turns
    return second_turns, first_turns


def _player_at_ply(definition: Definition, ply: int) -> Player:
    return definition.first_player if ply % 2 == 0 else definition.first_player.other


def validate_state(definition: Definition, state: State) -> None:
    """Validate canonical types and all registered necessary state invariants."""

    _require_definition(definition)
    if type(state) is not State:
        raise ValueError("state must be an exact State")
    _exact_fields(
        state,
        (
            "a",
            "b",
            "bridge_left",
            "conversion_left",
            "to_move",
            "plies",
            "winner",
        ),
        "state",
    )
    _validate_board_masks(definition, state.a, state.b)
    _integer(
        state.bridge_left,
        "state.bridge_left",
        0,
        definition.bridge_credits_A,
    )
    _integer(
        state.conversion_left,
        "state.conversion_left",
        0,
        definition.conversion_credits_B,
    )
    _integer(state.plies, "state.plies", 0, _cell_count(definition))
    if type(state.to_move) is not Player:
        raise ValueError("state.to_move must be Player.A or Player.B")
    if state.winner is not None and type(state.winner) is not Player:
        raise ValueError("state.winner must be Player.A, Player.B, or None")

    turns_a, turns_b = _turn_counts(definition, state.plies)
    used_a = definition.bridge_credits_A - state.bridge_left
    used_b = definition.conversion_credits_B - state.conversion_left
    if used_a > turns_a or used_b > turns_b:
        raise ValueError("credit use exceeds completed turns for its role")
    expected_a = turns_a + used_a - used_b
    expected_b = turns_b + used_b
    if expected_a < 0 or bin(state.a).count("1") != expected_a:
        raise ValueError("A stone count disagrees with turns and credits")
    if bin(state.b).count("1") != expected_b:
        raise ValueError("B stone count disagrees with turns and credits")

    board_winner = winner_from_board(definition, state.a, state.b)
    if state.winner is not board_winner:
        raise ValueError("state.winner disagrees with board connectivity")
    if state.winner is None:
        expected_to_move = _player_at_ply(definition, state.plies)
        if state.to_move is not expected_to_move:
            raise ValueError("state.to_move disagrees with ply parity")
    else:
        if state.plies == 0:
            raise ValueError("initial state cannot have a winner")
        mover = _player_at_ply(definition, state.plies - 1)
        if state.winner is not mover or state.to_move is not mover:
            raise ValueError("terminal winner and to_move must be the last mover")


def initial_state(definition: Definition) -> State:
    _require_definition(definition)
    state = State(
        a=0,
        b=0,
        bridge_left=definition.bridge_credits_A,
        conversion_left=definition.conversion_credits_B,
        to_move=definition.first_player,
        plies=0,
        winner=None,
    )
    validate_state(definition, state)
    return state


def _validate_action_shape(action: Action) -> None:
    if type(action) is not Action:
        raise ValueError("action must be an exact Action")
    _exact_fields(action, ("kind", "cells"), "action")
    if type(action.kind) is not str or action.kind not in ACTION_KINDS:
        raise ValueError("unknown action kind")
    if type(action.cells) is not tuple or any(
        type(cell) is not int or cell < 0 for cell in action.cells
    ):
        raise ValueError("action.cells must be a tuple of nonnegative integers")
    if action.kind == PLACE_ONE:
        if len(action.cells) != 1:
            raise ValueError("PLACE_ONE requires one cell")
    elif action.kind == BRIDGE_PAIR:
        if len(action.cells) != 2 or action.cells[0] >= action.cells[1]:
            raise ValueError("BRIDGE_PAIR requires a canonical increasing pair")
    elif action.kind == PLACE_AND_CONVERT:
        if len(action.cells) != 2 or action.cells[0] == action.cells[1]:
            raise ValueError("PLACE_AND_CONVERT requires distinct ordered cells")


def _validate_action_for_definition(definition: Definition, action: Action) -> None:
    _require_definition(definition)
    _validate_action_shape(action)
    maximum = _cell_count(definition) - 1
    for cell in action.cells:
        _integer(cell, "action cell", 0, maximum)
    if action.kind in (BRIDGE_PAIR, PLACE_AND_CONVERT):
        if action.cells[1] not in _neighbors_for_size(definition.size, action.cells[0]):
            raise ValueError("action cells must be Hex neighbors")


def legal_actions(definition: Definition, state: State) -> Tuple[Action, ...]:
    """Return all actions in the registered canonical kind/coordinate order."""

    validate_state(definition, state)
    if state.winner is not None:
        return ()
    occupied = state.a | state.b
    empty = [
        cell
        for cell in range(_cell_count(definition))
        if not occupied & (1 << cell)
    ]
    actions = [Action(PLACE_ONE, (cell,)) for cell in empty]
    if state.to_move is Player.A and state.bridge_left > 0:
        empty_set = set(empty)
        for first in empty:
            for second in _neighbors_for_size(definition.size, first):
                if first < second and second in empty_set:
                    actions.append(Action(BRIDGE_PAIR, (first, second)))
    if state.to_move is Player.B and state.conversion_left > 0:
        for place in empty:
            for convert in _neighbors_for_size(definition.size, place):
                if state.a & (1 << convert):
                    actions.append(Action(PLACE_AND_CONVERT, (place, convert)))
    return tuple(actions)


def apply_action(definition: Definition, state: State, action: Action) -> State:
    """Apply one atomic legal action and recompute both connections from scratch."""

    validate_state(definition, state)
    if state.winner is not None:
        raise ValueError("cannot act after a terminal connection")
    _validate_action_for_definition(definition, action)
    occupied = state.a | state.b
    player = state.to_move
    a = state.a
    b = state.b
    bridge_left = state.bridge_left
    conversion_left = state.conversion_left

    if action.kind == PLACE_ONE:
        cell = action.cells[0]
        bit = 1 << cell
        if occupied & bit:
            raise ValueError("PLACE_ONE target must be empty")
        if player is Player.A:
            a |= bit
        else:
            b |= bit
    elif action.kind == BRIDGE_PAIR:
        if player is not Player.A or bridge_left == 0:
            raise ValueError("only A with bridge credit may use BRIDGE_PAIR")
        first, second = action.cells
        bits = (1 << first) | (1 << second)
        if occupied & bits:
            raise ValueError("BRIDGE_PAIR targets must both be empty")
        a |= bits
        bridge_left -= 1
    else:
        if player is not Player.B or conversion_left == 0:
            raise ValueError(
                "only B with conversion credit may use PLACE_AND_CONVERT"
            )
        place, convert = action.cells
        place_bit = 1 << place
        convert_bit = 1 << convert
        if occupied & place_bit:
            raise ValueError("conversion place target must be empty")
        if not a & convert_bit:
            raise ValueError("conversion target must be a preexisting A stone")
        a &= ~convert_bit
        b |= place_bit | convert_bit
        conversion_left -= 1

    plies = state.plies + 1
    winner = winner_from_board(definition, a, b)
    if winner is not None and winner is not player:
        raise ValueError("an action cannot create a connection for the nonmover")
    result = State(
        a=a,
        b=b,
        bridge_left=bridge_left,
        conversion_left=conversion_left,
        to_move=player if winner is not None else player.other,
        plies=plies,
        winner=winner,
    )
    validate_state(definition, result)
    return result


def _coordinate(definition: Definition, cell: int) -> list:
    row, column = divmod(cell, definition.size)
    return [row, column]


def _parse_coordinate(definition: Definition, value: Any, label: str) -> int:
    if type(value) is not list or len(value) != 2:
        raise ValueError("{} must be a two-integer coordinate array".format(label))
    row = _integer(value[0], label + "[0]", 0, definition.size - 1)
    column = _integer(value[1], label + "[1]", 0, definition.size - 1)
    return row * definition.size + column


def action_to_dict(definition: Definition, action: Action) -> dict:
    _validate_action_for_definition(definition, action)
    return {
        "kind": action.kind,
        "cells": [_coordinate(definition, cell) for cell in action.cells],
    }


def action_from_dict(definition: Definition, value: Mapping[str, Any]) -> Action:
    _require_definition(definition)
    data = _mapping(value, "action")
    _keys(data, _ACTION_KEYS, "action")
    if type(data["kind"]) is not str:
        raise ValueError("action.kind must be an exact string")
    if type(data["cells"]) is not list:
        raise ValueError("action.cells must be an array")
    cells = tuple(
        _parse_coordinate(definition, item, "action.cells[{}]".format(index))
        for index, item in enumerate(data["cells"])
    )
    action = Action(data["kind"], cells)
    _validate_action_for_definition(definition, action)
    return action


def _mask_to_coordinates(definition: Definition, mask: int) -> list:
    return [
        _coordinate(definition, cell)
        for cell in range(_cell_count(definition))
        if mask & (1 << cell)
    ]


def _coordinates_to_mask(definition: Definition, value: Any, label: str) -> int:
    if type(value) is not list:
        raise ValueError("{} must be an array".format(label))
    cells = tuple(
        _parse_coordinate(definition, item, "{}[{}]".format(label, index))
        for index, item in enumerate(value)
    )
    if cells != tuple(sorted(set(cells))):
        raise ValueError("{} must be distinct and canonically sorted".format(label))
    mask = 0
    for cell in cells:
        mask |= 1 << cell
    return mask


def state_to_dict(definition: Definition, state: State) -> dict:
    validate_state(definition, state)
    return {
        "a": _mask_to_coordinates(definition, state.a),
        "b": _mask_to_coordinates(definition, state.b),
        "bridge_left": state.bridge_left,
        "conversion_left": state.conversion_left,
        "to_move": state.to_move.value,
        "plies": state.plies,
        "winner": None if state.winner is None else state.winner.value,
    }


def state_from_dict(definition: Definition, value: Mapping[str, Any]) -> State:
    _require_definition(definition)
    data = _mapping(value, "state")
    _keys(data, _STATE_KEYS, "state")
    a = _coordinates_to_mask(definition, data["a"], "state.a")
    b = _coordinates_to_mask(definition, data["b"], "state.b")
    bridge_left = _integer(
        data["bridge_left"],
        "state.bridge_left",
        0,
        definition.bridge_credits_A,
    )
    conversion_left = _integer(
        data["conversion_left"],
        "state.conversion_left",
        0,
        definition.conversion_credits_B,
    )
    if type(data["to_move"]) is not str or data["to_move"] not in ("A", "B"):
        raise ValueError("state.to_move must be A or B")
    plies = _integer(data["plies"], "state.plies", 0, _cell_count(definition))
    raw_winner = data["winner"]
    if raw_winner is None:
        winner = None
    elif type(raw_winner) is str and raw_winner in ("A", "B"):
        winner = Player(raw_winner)
    else:
        raise ValueError("state.winner must be A, B, or null")
    state = State(
        a=a,
        b=b,
        bridge_left=bridge_left,
        conversion_left=conversion_left,
        to_move=Player(data["to_move"]),
        plies=plies,
        winner=winner,
    )
    validate_state(definition, state)
    return state


def termination_certificate(definition: Definition) -> dict:
    """Return the finite-descent and unique-winner proof obligations."""

    _require_definition(definition)
    cells = _cell_count(definition)
    return {
        "measure": "EMPTY_CELL_COUNT",
        "initial_measure": cells,
        "minimum_decrease_per_action": 1,
        "maximum_actions": cells,
        "full_board_theorem": "EXACTLY_ONE_OPPOSITE_EDGE_CONNECTION",
        "terminal_winners": ["A", "B"],
        "draw_outcome": False,
        "no_legal_action_winner": False,
    }


def describe_rules(definition: Definition) -> Tuple[str, ...]:
    """Derive concise human-readable rules from an authoritative definition."""

    _require_definition(definition)
    return (
        "{}x{} rhombus Hex-cell board; {} moves first.".format(
            definition.size, definition.size, definition.first_player.value
        ),
        "A connects left to right and may spend {} bridge credits to place on two adjacent empty cells.".format(
            definition.bridge_credits_A
        ),
        "B connects top to bottom and may spend {} conversion credits to place on one empty cell and convert one adjacent preexisting A stone.".format(
            definition.conversion_credits_B
        ),
        "Either role may instead place one stone on one empty cell.",
        "Each action is atomic; after all effects, the mover wins exactly when their opposite edges connect.",
        "Every action fills at least one empty cell, and a full Hex board has exactly one connection winner; there is no pass, draw, or no-action loss.",
    )
