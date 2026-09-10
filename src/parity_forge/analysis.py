"""Cheap, deterministic diagnostics that run before simulated play."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Iterable, Mapping, Optional, Set, Tuple

from .dsl import (
    ActionKind,
    DefinitionError,
    Edge,
    GameDefinition,
    GoalKind,
    MOVEMENT_ACTION_KINDS,
    Player,
    parse_definition,
)
from .engine import GameState, goal_satisfied, initial_state
from .simplicity import ComplexityLimits, DEFAULT_LIMITS, evaluate_simplicity, exceeds_limits


class FailureCode(str, Enum):
    INVALID_DEFINITION = "INVALID_DEFINITION"
    NO_LEGAL_MOVE_AT_START = "NO_LEGAL_MOVE_AT_START"
    UNREACHABLE_WIN_CONDITION = "UNREACHABLE_WIN_CONDITION"
    NON_TERMINATING = "NON_TERMINATING"
    TRIVIAL_FORCED_RESULT = "TRIVIAL_FORCED_RESULT"
    A_DOMINANT = "A_DOMINANT"
    B_DOMINANT = "B_DOMINANT"
    EXCESSIVE_DRAWS = "EXCESSIVE_DRAWS"
    TOO_SYMMETRIC = "TOO_SYMMETRIC"
    TOO_COMPLEX = "TOO_COMPLEX"
    TOO_SHORT = "TOO_SHORT"
    TOO_LONG = "TOO_LONG"
    NO_MEANINGFUL_CHOICE = "NO_MEANINGFUL_CHOICE"
    SINGLE_STRATEGY = "SINGLE_STRATEGY"
    SOLVED_OPENING = "SOLVED_OPENING"
    AGENT_DISAGREEMENT = "AGENT_DISAGREEMENT"
    EVALUATOR_SUSPECTED_FALSE_POSITIVE = "EVALUATOR_SUSPECTED_FALSE_POSITIVE"


@dataclass(frozen=True)
class Diagnostic:
    code: FailureCode
    detail: str

    def to_dict(self) -> Dict[str, str]:
        return {"code": self.code.value, "detail": self.detail}


@dataclass(frozen=True)
class StaticReport:
    definition_hash: Optional[str]
    diagnostics: Tuple[Diagnostic, ...]

    @property
    def failure_codes(self) -> Tuple[FailureCode, ...]:
        return tuple(diagnostic.code for diagnostic in self.diagnostics)

    @property
    def passes(self) -> bool:
        return not self.diagnostics

    def to_dict(self) -> Dict[str, Any]:
        return {
            "definition_hash": self.definition_hash,
            "passes": self.passes,
            "diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
        }


def _positions_on_edge(size: int, edge: Edge) -> Set[Tuple[int, int]]:
    if edge is Edge.TOP:
        return {(0, column) for column in range(size)}
    if edge is Edge.BOTTOM:
        return {(size - 1, column) for column in range(size)}
    if edge is Edge.LEFT:
        return {(row, 0) for row in range(size)}
    return {(row, size - 1) for row in range(size)}


def _reach_goal_possible_ignoring_blockers(
    definition: GameDefinition, player: Player
) -> bool:
    role = definition.role(player)
    assert role.goal.kind is GoalKind.REACH_EDGE and role.goal.edge is not None
    starts = {
        piece.position
        for piece in definition.initial_pieces
        if piece.owner is player and piece.piece == role.goal.piece
    }
    if role.action.kind is ActionKind.PLACE and role.action.piece == role.goal.piece:
        return True
    if (
        role.action.kind not in MOVEMENT_ACTION_KINDS
        or role.action.piece != role.goal.piece
    ):
        return any(position in _positions_on_edge(definition.board_size, role.goal.edge) for position in starts)

    targets = _positions_on_edge(definition.board_size, role.goal.edge)
    frontier = list(starts)
    visited = set(starts)
    while frontier:
        position = frontier.pop()
        if position in targets:
            return True
        for row_delta, column_delta in role.action.vectors:
            destination = (position[0] + row_delta, position[1] + column_delta)
            if (
                0 <= destination[0] < definition.board_size
                and 0 <= destination[1] < definition.board_size
                and destination not in visited
            ):
                visited.add(destination)
                frontier.append(destination)
    return False


def _goal_reachable_under_relaxation(
    definition: GameDefinition, player: Player
) -> bool:
    role = definition.role(player)
    if goal_satisfied(definition, definition.initial_pieces, player):
        return True
    if role.goal.kind is GoalKind.ELIMINATE:
        return (
            role.action.kind in (ActionKind.MOVE_CAPTURE, ActionKind.CONVERT)
            and any(
                piece.owner is player and piece.piece == role.action.piece
                for piece in definition.initial_pieces
            )
        )
    if role.goal.kind not in (GoalKind.REACH_EDGE, GoalKind.CONNECT_EDGES):
        raise AssertionError("validated definition has an unknown goal kind")
    if (
        role.action.kind is ActionKind.CONVERT
        and role.action.piece == role.goal.piece
        and any(
            piece.owner is player and piece.piece == role.action.piece
            for piece in definition.initial_pieces
        )
    ):
        # CONVERT preserves its actor and can create another owned action/goal
        # piece at a declared adjacent target.  As with PLACE, this cheap static
        # upper bound deliberately relaxes target supply and blockers rather
        # than rejecting a definition from its initial target arrangement.
        return True
    if role.goal.kind is GoalKind.REACH_EDGE:
        return _reach_goal_possible_ignoring_blockers(definition, player)

    assert role.goal.kind is GoalKind.CONNECT_EDGES

    relevant_count = sum(
        piece.owner is player and piece.piece == role.goal.piece
        for piece in definition.initial_pieces
    )
    if role.action.kind is ActionKind.PLACE and role.action.piece == role.goal.piece:
        return True
    if (
        role.action.kind in MOVEMENT_ACTION_KINDS
        and role.action.piece == role.goal.piece
    ):
        return relevant_count >= definition.board_size
    return False


def analyze_definition(
    definition: GameDefinition,
    complexity_limits: ComplexityLimits = DEFAULT_LIMITS,
) -> StaticReport:
    from .dsl import definition_hash

    diagnostics = []
    seen = set()

    def add(code: FailureCode, detail: str) -> None:
        if code not in seen:
            seen.add(code)
            diagnostics.append(Diagnostic(code=code, detail=detail))

    state = initial_state(definition)
    if state.outcome is not None and state.outcome.reason == "NO_LEGAL_ACTION":
        add(FailureCode.NO_LEGAL_MOVE_AT_START, "{} has no legal initial action".format(definition.first_player.value))
    if any(goal_satisfied(definition, definition.initial_pieces, player) for player in Player):
        add(FailureCode.TRIVIAL_FORCED_RESULT, "at least one role's goal is satisfied in the initial position")
    unreachable = [
        player.value
        for player in Player
        if not _goal_reachable_under_relaxation(definition, player)
    ]
    if unreachable:
        add(
            FailureCode.UNREACHABLE_WIN_CONDITION,
            "goal is unreachable even after relaxing blockers for role(s) {}".format(", ".join(unreachable)),
        )
    if definition.role(Player.A).action.kind is definition.role(Player.B).action.kind:
        add(FailureCode.TOO_SYMMETRIC, "both roles use the same action primitive")
    if exceeds_limits(evaluate_simplicity(definition), complexity_limits):
        add(FailureCode.TOO_COMPLEX, "candidate exceeds at least one frozen provisional complexity gate")
    return StaticReport(
        definition_hash=definition_hash(definition),
        diagnostics=tuple(diagnostics),
    )


def analyze_mapping(
    value: Mapping[str, Any],
    complexity_limits: ComplexityLimits = DEFAULT_LIMITS,
) -> StaticReport:
    try:
        definition = parse_definition(value)
    except (DefinitionError, TypeError) as error:
        return StaticReport(
            definition_hash=None,
            diagnostics=(Diagnostic(FailureCode.INVALID_DEFINITION, str(error)),),
        )
    return analyze_definition(definition, complexity_limits)
