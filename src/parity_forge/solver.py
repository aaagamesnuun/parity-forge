"""Exact finite-horizon minimax for small diagnostic candidates."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, Tuple

from .dsl import GameDefinition, Player
from .engine import Action, GameState, apply_action, initial_state, legal_actions


@dataclass(frozen=True)
class SolveResult:
    value_for_a: int
    forced_result: str
    principal_variation: Tuple[Action, ...]
    terminal_reason: str
    searched_states: int
    cache_hits: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "value_for_a": self.value_for_a,
            "forced_result": self.forced_result,
            "principal_variation": [action.to_dict() for action in self.principal_variation],
            "principal_variation_plies": len(self.principal_variation),
            "terminal_reason": self.terminal_reason,
            "searched_states": self.searched_states,
            "cache_hits": self.cache_hits,
        }


class SolveBudgetExceeded(RuntimeError):
    """Raised when an exact solve exceeds a deterministic state allowance."""

    def __init__(self, searched_states: int, max_states: int) -> None:
        self.searched_states = searched_states
        self.max_states = max_states
        super().__init__(
            "exact state budget exhausted at {} of {} states".format(
                searched_states, max_states
            )
        )


def _terminal_value(state: GameState) -> int:
    assert state.outcome is not None
    if state.outcome.winner is Player.A:
        return 1
    if state.outcome.winner is Player.B:
        return -1
    return 0


def solve_game(definition: GameDefinition, max_states: int = 0) -> SolveResult:
    """Solve optimal play exactly; DSL's ply cap makes the graph acyclic."""

    if max_states < 0:
        raise ValueError("max_states cannot be negative")

    searched_states = 0

    @lru_cache(maxsize=None)
    def visit(state: GameState) -> Tuple[int, Tuple[Action, ...]]:
        nonlocal searched_states
        if max_states and searched_states >= max_states:
            raise SolveBudgetExceeded(searched_states, max_states)
        searched_states += 1
        if state.terminal:
            return _terminal_value(state), ()
        scored = tuple(
            (action, visit(apply_action(definition, state, action))[0])
            for action in legal_actions(definition, state)
        )
        target = (
            max(value for _, value in scored)
            if state.to_move is Player.A
            else min(value for _, value in scored)
        )
        best = tuple(action for action, value in scored if value == target)
        return target, best

    state = initial_state(definition)
    value, _ = visit(state)
    principal_variation = []
    while not state.terminal:
        _, best_actions = visit(state)
        action = best_actions[0]
        principal_variation.append(action)
        state = apply_action(definition, state, action)
    assert state.outcome is not None
    cache = visit.cache_info()
    return SolveResult(
        value_for_a=value,
        forced_result={1: "A_WIN", 0: "DRAW", -1: "B_WIN"}[value],
        principal_variation=tuple(principal_variation),
        terminal_reason=state.outcome.reason,
        searched_states=searched_states,
        cache_hits=cache.hits,
    )
