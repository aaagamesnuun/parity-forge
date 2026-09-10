"""Small, inspectable agents for early evaluator calibration."""

from __future__ import annotations

import random
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol, Sequence, Set, Tuple

from .dsl import Edge, GameDefinition, GoalKind, Player, Position
from .engine import Action, GameState, apply_action, legal_actions


@dataclass(frozen=True)
class AgentIdentity:
    family: str
    version: int
    strength: str

    @property
    def key(self) -> str:
        return "{}-v{}-{}".format(self.family, self.version, self.strength)


class Agent(Protocol):
    identity: AgentIdentity

    def select_action(
        self,
        definition: GameDefinition,
        state: GameState,
        actions: Sequence[Action],
        rng: random.Random,
    ) -> Action:
        ...


class SearchBudgetExceeded(RuntimeError):
    """Raised when a deterministic minimax node allowance is exhausted."""

    def __init__(self, scope: str, visited_nodes: int, max_nodes: int) -> None:
        self.scope = scope
        self.visited_nodes = visited_nodes
        self.max_nodes = max_nodes
        super().__init__(
            "minimax {} node budget exhausted at {} of {} nodes".format(
                scope, visited_nodes, max_nodes
            )
        )


class RandomAgent:
    identity = AgentIdentity(family="random", version=1, strength="weak")

    def select_action(
        self,
        definition: GameDefinition,
        state: GameState,
        actions: Sequence[Action],
        rng: random.Random,
    ) -> Action:
        if not actions:
            raise ValueError("agent cannot choose from an empty legal-action sequence")
        return actions[rng.randrange(len(actions))]


def _connected_components(positions: Set[Position]) -> Tuple[Set[Position], ...]:
    remaining = set(positions)
    components = []
    while remaining:
        frontier = [min(remaining)]
        component = {frontier[0]}
        remaining.remove(frontier[0])
        while frontier:
            row, column = frontier.pop()
            for neighbor in ((row - 1, column), (row, column - 1), (row, column + 1), (row + 1, column)):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    component.add(neighbor)
                    frontier.append(neighbor)
        components.append(component)
    return tuple(components)


def _edge_distance(position: Position, edge: Edge, size: int) -> int:
    row, column = position
    return {
        Edge.TOP: row,
        Edge.RIGHT: size - 1 - column,
        Edge.BOTTOM: size - 1 - row,
        Edge.LEFT: column,
    }[edge]


def goal_progress(definition: GameDefinition, state: GameState, player: Player) -> float:
    """Return a role-normalized, transparent progress heuristic in roughly [0, 1]."""

    goal = definition.role(player).goal
    if goal.kind is GoalKind.ELIMINATE:
        raise ValueError(
            "goal-progress-v1 does not support ELIMINATE goals"
        )
    positions = {
        piece.position
        for piece in state.pieces
        if piece.owner is player and piece.piece == goal.piece
    }
    if not positions:
        return 0.0
    denominator = max(1, definition.board_size - 1)
    if goal.kind is GoalKind.REACH_EDGE:
        assert goal.edge is not None
        distance = min(_edge_distance(position, goal.edge, definition.board_size) for position in positions)
        return 1.0 - distance / denominator

    if goal.kind is not GoalKind.CONNECT_EDGES:
        raise AssertionError("validated definition has an unknown goal kind")
    first, second = goal.edges
    best = 0.0
    for component in _connected_components(positions):
        distance_first = min(_edge_distance(position, first, definition.board_size) for position in component)
        distance_second = min(_edge_distance(position, second, definition.board_size) for position in component)
        gap_progress = 1.0 - (distance_first + distance_second) / (2 * denominator)
        coverage = min(1.0, len(component) / definition.board_size)
        best = max(best, 0.65 * gap_progress + 0.35 * coverage)
    return best


def _require_v1_goal_heuristic_support(definition: GameDefinition) -> None:
    if any(
        definition.role(player).goal.kind is GoalKind.ELIMINATE
        for player in (Player.A, Player.B)
    ):
        raise ValueError(
            "goal-progress-v1 agents do not support ELIMINATE goals"
        )


class GoalDirectedAgent:
    """One-ply goal progress with seeded tie-breaking; no opponent model."""

    identity = AgentIdentity(family="goal_directed", version=1, strength="medium")

    def select_action(
        self,
        definition: GameDefinition,
        state: GameState,
        actions: Sequence[Action],
        rng: random.Random,
    ) -> Action:
        _require_v1_goal_heuristic_support(definition)
        if not actions:
            raise ValueError("agent cannot choose from an empty legal-action sequence")
        scored = []
        for action in actions:
            result = apply_action(definition, state, action)
            won = result.outcome is not None and result.outcome.winner is state.to_move
            score = 2.0 if won else goal_progress(definition, result, state.to_move)
            scored.append((score, action))
        best_score = max(score for score, _ in scored)
        best_actions = [action for score, action in scored if score == best_score]
        return best_actions[rng.randrange(len(best_actions))]


class MinimaxAgent:
    """Depth-limited zero-sum search with a normalized goal-progress leaf value."""

    def __init__(
        self,
        depth: int = 3,
        max_nodes_per_move: int = 0,
        max_total_nodes: int = 0,
    ) -> None:
        if depth < 1:
            raise ValueError("minimax depth must be at least one")
        if max_nodes_per_move < 0:
            raise ValueError("max_nodes_per_move cannot be negative")
        if max_total_nodes < 0:
            raise ValueError("max_total_nodes cannot be negative")
        self.depth = depth
        self.max_nodes_per_move = max_nodes_per_move
        self.max_total_nodes = max_total_nodes
        self.total_nodes = 0
        self.identity = AgentIdentity(
            family="minimax",
            version=1,
            strength="depth{}".format(depth),
        )

    def reset_budget(self) -> None:
        self.total_nodes = 0

    def select_action(
        self,
        definition: GameDefinition,
        state: GameState,
        actions: Sequence[Action],
        rng: random.Random,
    ) -> Action:
        _require_v1_goal_heuristic_support(definition)
        if not actions:
            raise ValueError("agent cannot choose from an empty legal-action sequence")

        visited_nodes = 0

        @lru_cache(maxsize=None)
        def search(candidate: GameState, remaining: int) -> float:
            nonlocal visited_nodes
            if self.max_nodes_per_move and visited_nodes >= self.max_nodes_per_move:
                raise SearchBudgetExceeded(
                    "per-move", visited_nodes, self.max_nodes_per_move
                )
            if self.max_total_nodes and self.total_nodes >= self.max_total_nodes:
                raise SearchBudgetExceeded(
                    "per-candidate", self.total_nodes, self.max_total_nodes
                )
            visited_nodes += 1
            self.total_nodes += 1
            if candidate.outcome is not None:
                if candidate.outcome.winner is Player.A:
                    return 2.0
                if candidate.outcome.winner is Player.B:
                    return -2.0
                return 0.0
            if remaining == 0:
                return goal_progress(definition, candidate, Player.A) - goal_progress(
                    definition, candidate, Player.B
                )
            values = [
                search(apply_action(definition, candidate, action), remaining - 1)
                for action in legal_actions(definition, candidate)
            ]
            return max(values) if candidate.to_move is Player.A else min(values)

        scored = [
            (action, search(apply_action(definition, state, action), self.depth - 1))
            for action in actions
        ]
        target = (
            max(value for _, value in scored)
            if state.to_move is Player.A
            else min(value for _, value in scored)
        )
        best_actions = [action for action, value in scored if value == target]
        return best_actions[rng.randrange(len(best_actions))]
