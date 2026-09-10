"""Bounded policies and short-win questions for finite-space v1.

Budgets count applied successor transitions, not wall time or nominal depth.
Policy exhaustion returns the last *completed* iteration (or seeded random
fallback), with the limitation recorded. Proof exhaustion returns UNKNOWN.
Neither case changes the game's terminal rules.
"""

from dataclasses import dataclass
import random

from .dsl import Player
from .finite_space import apply_action, initial_state, legal_actions


WIN = 1_000_000
POLICIES = ("random-v1", "deny-v1", "mobility-search-v1")


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class Budget:
    limit: int
    used: int = 0
    expired: object = None

    def __post_init__(self):
        if type(self.limit) is not int or self.limit < 0:
            raise ValueError("budget must be a nonnegative integer")
        if type(self.used) is not int or self.used != 0:
            raise ValueError("a new budget starts at zero")
        if self.expired is not None and not callable(self.expired):
            raise TypeError("expired must be callable or None")

    def apply(self, definition, state, action):
        if self.used >= self.limit or (self.expired is not None and self.expired()):
            raise BudgetExceeded("successor transition budget exhausted")
        self.used += 1
        return apply_action(definition, state, action)


def _positive_integer(value, name):
    if type(value) is not int or value < 1:
        raise ValueError(name + " must be a positive integer")


def mobility_value(definition, state):
    """A-relative mobility, not a calibrated fairness or fun score."""
    current = legal_actions(definition, state)
    if state.winner is not None:
        return WIN if state.winner is Player.A else -WIN
    other = legal_actions(definition, state, state.to_move.other)
    value = len(current) - len(other)
    return value if state.to_move is Player.A else -value


def select_action(definition, state, policy, rng, max_nodes, max_depth=2, cpu_expired=None):
    """Return (legal action, honest resource/iteration telemetry)."""
    if policy not in POLICIES:
        raise ValueError("unknown policy")
    if type(rng) is not random.Random:
        raise TypeError("rng must be random.Random")
    _positive_integer(max_depth, "max_depth")
    if max_depth > 8:
        raise ValueError("policy depth exceeds v1 resource guard")
    budget = Budget(max_nodes, expired=cpu_expired)
    actions = legal_actions(definition, state)
    if not actions:
        raise ValueError("no action may be selected in a terminal state")
    selected = rng.choice(actions)
    completed_depth, exhausted = 0, False
    actor = state.to_move

    def search(position, depth, alpha, beta):
        if position.winner is not None or depth == 0:
            return mobility_value(definition, position)
        maximizing = position.to_move is Player.A
        value = -WIN * 2 if maximizing else WIN * 2
        for move in legal_actions(definition, position):
            child = budget.apply(definition, position, move)
            score = search(child, depth - 1, alpha, beta)
            value = max(value, score) if maximizing else min(value, score)
            if maximizing:
                alpha = max(alpha, value)
            else:
                beta = min(beta, value)
            if alpha >= beta:
                break
        return value

    depths = () if policy == "random-v1" else range(1, max_depth + 1)
    if policy == "deny-v1":
        depths = (1,)
    for depth in depths:
        values = []
        try:
            for action in actions:
                child = budget.apply(definition, state, action)
                if policy == "deny-v1":
                    score = (WIN if child.winner is actor else
                             -WIN if child.winner is not None else
                             -len(legal_actions(definition, child, actor.other)))
                else:
                    score = search(child, depth - 1, -WIN * 2, WIN * 2)
                    if actor is Player.B:
                        score = -score
                values.append((action, score))
        except BudgetExceeded:
            exhausted = True
            break
        best = max(score for _, score in values)
        selected = rng.choice(tuple(action for action, score in values if score == best))
        completed_depth = depth
    return selected, {
        "policy": policy, "nodes": budget.used,
        "completed_depth": completed_depth, "budget_exhausted": exhausted,
        "fallback": policy != "random-v1" and completed_depth == 0,
    }


def short_win(definition, player, max_plies, max_nodes, state=None, cpu_expired=None):
    """Can player force a win within max_plies against every opponent reply?

COMPLETE/false negates only this horizon-bounded proposition. It does not say
that the player loses eventually. UNKNOWN has no forced_win truth value.
"""
    if type(player) is not Player:
        raise TypeError("player must be Player")
    if type(max_plies) is not int or not 0 <= max_plies <= 32:
        raise ValueError("max_plies must be an integer in 0..32")
    budget = Budget(max_nodes, expired=cpu_expired)
    start = initial_state(definition) if state is None else state
    legal_actions(definition, start)  # Validate even a claimed terminal input.
    memo = {}

    def visit(position, remaining):
        if position.winner is not None:
            return position.winner is player
        if remaining == 0:
            return False
        key = (position, remaining)
        if key in memo:
            return memo[key]
        existential = position.to_move is player
        result = not existential
        for action in legal_actions(definition, position):
            child = budget.apply(definition, position, action)
            child_value = visit(child, remaining - 1)
            if child_value == existential:
                result = existential
                break
        memo[key] = result
        return result

    try:
        result = visit(start, max_plies)
        status = "COMPLETE"
    except BudgetExceeded:
        result, status = None, "UNKNOWN"
    return {
        "status": status, "forced_win": result, "player": player.value,
        "max_plies": max_plies, "max_nodes": max_nodes, "nodes": budget.used,
        "proposition": "FORCE_WIN_WITHIN_PLIES",
    }
