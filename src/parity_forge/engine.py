"""Pure deterministic state transitions for supported Game DSL schemas."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

from .dsl import (
    ActionKind,
    Edge,
    GameDefinition,
    GoalKind,
    InitialPiece,
    NoLegalActionOutcome,
    Player,
    Position,
)


class IllegalAction(ValueError):
    """Raised when an action is malformed or not legal in the supplied state."""


@dataclass(frozen=True)
class Outcome:
    winner: Optional[Player]
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "winner": self.winner.value if self.winner is not None else None,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class Action:
    kind: ActionKind
    to_position: Position
    from_position: Optional[Position] = None

    def __post_init__(self) -> None:
        _validate_action(self)

    @classmethod
    def place(cls, row: int, column: int) -> "Action":
        return cls(kind=ActionKind.PLACE, to_position=(row, column))

    @classmethod
    def move(cls, from_position: Position, to_position: Position) -> "Action":
        return cls(kind=ActionKind.MOVE, from_position=from_position, to_position=to_position)

    @classmethod
    def move_capture(
        cls, from_position: Position, to_position: Position
    ) -> "Action":
        return cls(
            kind=ActionKind.MOVE_CAPTURE,
            from_position=from_position,
            to_position=to_position,
        )

    @classmethod
    def push(cls, from_position: Position, to_position: Position) -> "Action":
        return cls(
            kind=ActionKind.PUSH,
            from_position=from_position,
            to_position=to_position,
        )

    @classmethod
    def swap(cls, from_position: Position, to_position: Position) -> "Action":
        return cls(
            kind=ActionKind.SWAP,
            from_position=from_position,
            to_position=to_position,
        )

    @classmethod
    def hop(cls, from_position: Position, to_position: Position) -> "Action":
        return cls(
            kind=ActionKind.HOP,
            from_position=from_position,
            to_position=to_position,
        )

    @classmethod
    def convert(cls, from_position: Position, to_position: Position) -> "Action":
        return cls(
            kind=ActionKind.CONVERT,
            from_position=from_position,
            to_position=to_position,
        )

    def sort_key(self) -> Tuple[Any, ...]:
        _validate_action(self)
        origin = self.from_position if self.from_position is not None else (-1, -1)
        return (self.kind.value, origin[0], origin[1], self.to_position[0], self.to_position[1])

    def to_dict(self) -> Dict[str, Any]:
        _validate_action(self)
        result: Dict[str, Any] = {
            "kind": self.kind.value,
            "to": list(self.to_position),
        }
        if self.from_position is not None:
            result["from"] = list(self.from_position)
        return result


def _validate_action(action: Any) -> None:
    """Revalidate actions at every public serialization/transition boundary."""

    if type(action) is not Action:
        raise IllegalAction("action must be an exact Action value")
    try:
        fields = vars(action)
    except TypeError as error:
        raise IllegalAction("action fields are unavailable") from error
    expected_fields = {"kind", "to_position", "from_position"}
    if type(fields) is not dict or set(fields) != expected_fields:
        raise IllegalAction("action fields must be exactly kind/from/to")

    kind = fields["kind"]
    to_position = fields["to_position"]
    from_position = fields["from_position"]
    if type(kind) is not ActionKind:
        raise IllegalAction("action kind must be an ActionKind")

    def require_position(value: Any, field: str) -> None:
        if (
            type(value) is not tuple
            or len(value) != 2
            or any(type(coordinate) is not int for coordinate in value)
        ):
            raise IllegalAction(
                "action {} must be a two-integer tuple".format(field)
            )

    require_position(to_position, "to_position")
    if kind is ActionKind.PLACE:
        if from_position is not None:
            raise IllegalAction("PLACE action cannot define from_position")
    elif from_position is None:
        raise IllegalAction(
            "{} action requires from_position".format(kind.value)
        )
    else:
        require_position(from_position, "from_position")


@dataclass(frozen=True)
class GameState:
    ply: int
    to_move: Player
    pieces: Tuple[InitialPiece, ...]
    outcome: Optional[Outcome] = None

    @property
    def terminal(self) -> bool:
        return self.outcome is not None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ply": self.ply,
            "to_move": self.to_move.value,
            "pieces": [piece.to_dict() for piece in self.pieces],
            "outcome": self.outcome.to_dict() if self.outcome is not None else None,
        }


def _canonical_pieces(pieces: Iterable[InitialPiece]) -> Tuple[InitialPiece, ...]:
    return tuple(sorted(pieces, key=lambda piece: (piece.position, piece.owner.value, piece.piece)))


def _no_legal_action_outcome(
    definition: GameDefinition, v1_winner: Player
) -> Outcome:
    policy = definition.terminal_policy
    if policy is None:
        return Outcome(winner=v1_winner, reason="NO_LEGAL_ACTION")
    assert policy.no_legal_action is NoLegalActionOutcome.DRAW
    return Outcome(winner=None, reason="NO_LEGAL_ACTION")


def initial_state(definition: GameDefinition) -> GameState:
    state = GameState(
        ply=0,
        to_move=definition.first_player,
        pieces=definition.initial_pieces,
    )
    if definition.schema_version == 4:
        for player in (
            definition.first_player,
            definition.first_player.other,
        ):
            if goal_satisfied(definition, state.pieces, player):
                return GameState(
                    ply=0,
                    to_move=definition.first_player,
                    pieces=definition.initial_pieces,
                    outcome=Outcome(winner=player, reason="GOAL"),
                )
    if not legal_actions(definition, state):
        return GameState(
            ply=0,
            to_move=definition.first_player,
            pieces=definition.initial_pieces,
            outcome=_no_legal_action_outcome(
                definition, definition.first_player.other
            ),
        )
    return state


def legal_actions(definition: GameDefinition, state: GameState) -> Tuple[Action, ...]:
    if state.terminal:
        return ()
    occupied = {piece.position: piece for piece in state.pieces}
    action_spec = definition.role(state.to_move).action
    actions = []
    if action_spec.kind is ActionKind.PLACE:
        for row in range(definition.board_size):
            for column in range(definition.board_size):
                position = (row, column)
                if position not in occupied:
                    actions.append(Action.place(row, column))
    elif action_spec.kind is ActionKind.CONVERT:
        convertible = (
            piece
            for piece in state.pieces
            if piece.owner is state.to_move and piece.piece == action_spec.piece
        )
        for piece in convertible:
            for row_delta, column_delta in action_spec.vectors:
                target_position = (
                    piece.position[0] + row_delta,
                    piece.position[1] + column_delta,
                )
                if not (
                    0 <= target_position[0] < definition.board_size
                    and 0 <= target_position[1] < definition.board_size
                ):
                    continue
                target = occupied.get(target_position)
                if target is not None and target.owner is state.to_move.other:
                    actions.append(Action.convert(piece.position, target_position))
    else:
        if action_spec.kind is ActionKind.MOVE:
            moving_action = Action.move
        elif action_spec.kind is ActionKind.MOVE_CAPTURE:
            moving_action = Action.move_capture
        elif action_spec.kind is ActionKind.PUSH:
            moving_action = Action.push
        elif action_spec.kind is ActionKind.SWAP:
            moving_action = Action.swap
        elif action_spec.kind is ActionKind.HOP:
            moving_action = Action.hop
        else:
            raise AssertionError("validated definition has an unknown action kind")
        movable = (
            piece
            for piece in state.pieces
            if piece.owner is state.to_move and piece.piece == action_spec.piece
        )
        for piece in movable:
            for row_delta, column_delta in action_spec.vectors:
                destination = (
                    piece.position[0] + row_delta,
                    piece.position[1] + column_delta,
                )
                if not (
                    0 <= destination[0] < definition.board_size
                    and 0 <= destination[1] < definition.board_size
                ):
                    continue
                destination_piece = occupied.get(destination)
                if action_spec.kind is ActionKind.HOP:
                    if destination_piece is None:
                        actions.append(moving_action(piece.position, destination))
                    else:
                        landing = (
                            destination[0] + row_delta,
                            destination[1] + column_delta,
                        )
                        if (
                            0 <= landing[0] < definition.board_size
                            and 0 <= landing[1] < definition.board_size
                            and landing not in occupied
                        ):
                            actions.append(moving_action(piece.position, landing))
                    continue
                legal_destination = destination_piece is None
                if (
                    destination_piece is not None
                    and destination_piece.owner is state.to_move.other
                ):
                    if action_spec.kind is ActionKind.MOVE_CAPTURE:
                        legal_destination = True
                    elif action_spec.kind is ActionKind.PUSH:
                        landing = (
                            destination[0] + row_delta,
                            destination[1] + column_delta,
                        )
                        legal_destination = (
                            0 <= landing[0] < definition.board_size
                            and 0 <= landing[1] < definition.board_size
                            and landing not in occupied
                        )
                    elif action_spec.kind is ActionKind.SWAP:
                        legal_destination = True
                if legal_destination:
                    actions.append(moving_action(piece.position, destination))
    return tuple(sorted(actions, key=Action.sort_key))


def _touches_edge(position: Position, edge: Edge, size: int) -> bool:
    row, column = position
    return {
        Edge.TOP: row == 0,
        Edge.RIGHT: column == size - 1,
        Edge.BOTTOM: row == size - 1,
        Edge.LEFT: column == 0,
    }[edge]


def goal_satisfied(
    definition: GameDefinition, pieces: Tuple[InitialPiece, ...], player: Player
) -> bool:
    goal = definition.role(player).goal
    if goal.kind is GoalKind.ELIMINATE:
        return not any(
            piece.owner is player.other and piece.piece == goal.piece
            for piece in pieces
        )

    positions = {
        piece.position
        for piece in pieces
        if piece.owner is player and piece.piece == goal.piece
    }
    if goal.kind is GoalKind.REACH_EDGE:
        assert goal.edge is not None
        return any(_touches_edge(position, goal.edge, definition.board_size) for position in positions)

    if goal.kind is not GoalKind.CONNECT_EDGES:
        raise AssertionError("validated definition has an unknown goal kind")
    first_edge, second_edge = goal.edges
    frontier = [
        position
        for position in sorted(positions)
        if _touches_edge(position, first_edge, definition.board_size)
    ]
    visited = set(frontier)
    while frontier:
        row, column = frontier.pop()
        if _touches_edge((row, column), second_edge, definition.board_size):
            return True
        for neighbor in ((row - 1, column), (row, column - 1), (row, column + 1), (row + 1, column)):
            if neighbor in positions and neighbor not in visited:
                visited.add(neighbor)
                frontier.append(neighbor)
    return False


def apply_action(definition: GameDefinition, state: GameState, action: Action) -> GameState:
    if state.terminal:
        raise IllegalAction("cannot act after the game is terminal")
    _validate_action(action)
    if action not in legal_actions(definition, state):
        raise IllegalAction("action is not legal in this state: {}".format(action.to_dict()))

    actor = state.to_move
    spec = definition.role(actor).action
    pieces = list(state.pieces)
    if action.kind is ActionKind.PLACE:
        pieces.append(InitialPiece(owner=actor, piece=spec.piece, position=action.to_position))
    elif action.kind is ActionKind.CONVERT:
        target_index = next(
            index
            for index, piece in enumerate(pieces)
            if piece.owner is actor.other
            and piece.position == action.to_position
        )
        pieces[target_index] = InitialPiece(
            owner=actor,
            piece=spec.piece,
            position=action.to_position,
        )
    else:
        assert action.from_position is not None
        if action.kind is ActionKind.MOVE_CAPTURE:
            pieces = [
                piece
                for piece in pieces
                if not (
                    piece.owner is actor.other
                    and piece.position == action.to_position
                )
            ]
        elif action.kind is ActionKind.PUSH:
            target_index = next(
                (
                    index
                    for index, piece in enumerate(pieces)
                    if piece.owner is actor.other
                    and piece.position == action.to_position
                ),
                None,
            )
            if target_index is not None:
                row_delta = action.to_position[0] - action.from_position[0]
                column_delta = action.to_position[1] - action.from_position[1]
                target = pieces[target_index]
                pieces[target_index] = InitialPiece(
                    owner=target.owner,
                    piece=target.piece,
                    position=(
                        action.to_position[0] + row_delta,
                        action.to_position[1] + column_delta,
                    ),
                )
        elif action.kind is ActionKind.SWAP:
            target_index = next(
                (
                    index
                    for index, piece in enumerate(pieces)
                    if piece.owner is actor.other
                    and piece.position == action.to_position
                ),
                None,
            )
            if target_index is not None:
                target = pieces[target_index]
                pieces[target_index] = InitialPiece(
                    owner=target.owner,
                    piece=target.piece,
                    position=action.from_position,
                )
        source_index = next(
            index
            for index, piece in enumerate(pieces)
            if piece.owner is actor
            and piece.piece == spec.piece
            and piece.position == action.from_position
        )
        pieces[source_index] = InitialPiece(
            owner=actor,
            piece=spec.piece,
            position=action.to_position,
        )

    canonical_pieces = _canonical_pieces(pieces)
    next_ply = state.ply + 1
    if goal_satisfied(definition, canonical_pieces, actor):
        return GameState(
            ply=next_ply,
            to_move=actor.other,
            pieces=canonical_pieces,
            outcome=Outcome(winner=actor, reason="GOAL"),
        )
    if (
        definition.schema_version == 4
        and goal_satisfied(definition, canonical_pieces, actor.other)
    ):
        return GameState(
            ply=next_ply,
            to_move=actor.other,
            pieces=canonical_pieces,
            outcome=Outcome(winner=actor.other, reason="GOAL"),
        )
    if next_ply >= definition.max_plies:
        return GameState(
            ply=next_ply,
            to_move=actor.other,
            pieces=canonical_pieces,
            outcome=Outcome(winner=None, reason="PLY_LIMIT"),
        )

    candidate = GameState(ply=next_ply, to_move=actor.other, pieces=canonical_pieces)
    if not legal_actions(definition, candidate):
        return GameState(
            ply=next_ply,
            to_move=actor.other,
            pieces=canonical_pieces,
            outcome=_no_legal_action_outcome(definition, actor),
        )
    return candidate


def action_from_dict(value: Mapping[str, Any]) -> Action:
    if not isinstance(value, Mapping):
        raise IllegalAction("recorded action must be an object")
    kind_value = value.get("kind")
    try:
        kind = ActionKind(kind_value)
    except (TypeError, ValueError):
        raise IllegalAction("recorded action has an invalid kind")
    expected = {"kind", "to"} if kind is ActionKind.PLACE else {"kind", "from", "to"}
    if set(value) != expected:
        raise IllegalAction("recorded action fields do not match {}".format(kind.value))

    def parse_position(raw: Any, field: str) -> Position:
        if (
            not isinstance(raw, (list, tuple))
            or len(raw) != 2
            or any(isinstance(item, bool) or not isinstance(item, int) for item in raw)
        ):
            raise IllegalAction("{} must be a two-integer array".format(field))
        return (raw[0], raw[1])

    destination = parse_position(value["to"], "to")
    if kind is ActionKind.PLACE:
        return Action.place(*destination)
    origin = parse_position(value["from"], "from")
    if kind is ActionKind.MOVE_CAPTURE:
        return Action.move_capture(origin, destination)
    if kind is ActionKind.PUSH:
        return Action.push(origin, destination)
    if kind is ActionKind.SWAP:
        return Action.swap(origin, destination)
    if kind is ActionKind.HOP:
        return Action.hop(origin, destination)
    if kind is ActionKind.CONVERT:
        return Action.convert(origin, destination)
    if kind is ActionKind.MOVE:
        return Action.move(origin, destination)
    raise IllegalAction("recorded action has an unsupported kind")


def replay(
    definition: GameDefinition, actions: Iterable[Action]
) -> GameState:
    state = initial_state(definition)
    for action in actions:
        state = apply_action(definition, state, action)
    return state


def replay_dicts(
    definition: GameDefinition, actions: Iterable[Mapping[str, Any]]
) -> GameState:
    return replay(definition, (action_from_dict(action) for action in actions))
