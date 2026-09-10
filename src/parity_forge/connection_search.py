"""Frozen connection-distance baseline and bounded, deterministic move selection."""

from collections import deque
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from .connection import Action, apply_action, legal_actions, neighbors, validate_state
from .dsl import Player


POLICIES = ("random-v1", "connection-greedy-v1", "connection-search-v1")


@dataclass(frozen=True)
class Selection:
    action: Optional[Action]
    completed_depth: int
    search_transitions: int
    budget_exhausted: bool
    fallback: bool
    cpu_expired: bool


@lru_cache(maxsize=32)
def _topology(definition):
    """Cache only immutable board adjacency, never states, scores or search values."""
    return tuple(neighbors(definition, cell) for cell in range(definition.size ** 2))


def _distance(definition, state, player):
    size = definition.size
    topology = _topology(definition)
    no_path = size * size + 1
    own, opponent = (state.a, state.b) if player is Player.A else (state.b, state.a)
    starts = range(0, size * size, size) if player is Player.A else range(size)
    distances = [no_path] * (size * size)
    frontier = deque()
    for cell in starts:
        if opponent & (1 << cell):
            continue
        cost = 0 if own & (1 << cell) else 1
        distances[cell] = cost
        if cost == 0:
            frontier.appendleft((cost, cell))
        else:
            frontier.append((cost, cell))
    while frontier:
        distance, cell = frontier.popleft()
        if distance != distances[cell]:
            continue
        if (cell % size == size - 1 if player is Player.A else cell // size == size - 1):
            return distance
        for neighbor in topology[cell]:
            if opponent & (1 << neighbor):
                continue
            cost = 0 if own & (1 << neighbor) else 1
            candidate = distance + cost
            if candidate < distances[neighbor]:
                distances[neighbor] = candidate
                if cost == 0:
                    frontier.appendleft((candidate, neighbor))
                else:
                    frontier.append((candidate, neighbor))
    return no_path


def connection_distance(definition, state, player):
    """Registered 0/1 vertex-path distance; opponent stones are impassable."""
    validate_state(definition, state)
    if not isinstance(player, Player):
        raise ValueError("distance player must be A or B")
    return _distance(definition, state, player)


def evaluate_state(definition, state):
    """A perspective only: terminal +/-1000, otherwise dB-dA; no bonuses."""
    validate_state(definition, state)
    if state.winner is not None:
        return 1000 if state.winner is Player.A else -1000
    return _distance(definition, state, Player.B) - _distance(definition, state, Player.A)


class _TransitionLimit(Exception):
    pass


class _CpuExpired(Exception):
    pass


def select_action(definition, state, policy, rng, max_transitions, max_depth, cpu_expired):
    """One RNG choice after full root iterations; no partial result is promoted.

    Every speculative apply is charged, including repeated iterative-deepening
    work. CPU interruption returns no action, even if a previous depth finished.
    """
    if policy not in POLICIES:
        raise ValueError("unknown connection policy")
    if type(max_transitions) is not int or not 0 <= max_transitions <= 32768:
        raise ValueError("transition limit must be an integer in 0..32768")
    if type(max_depth) is not int or not 1 <= max_depth <= 3:
        raise ValueError("depth must be an integer in 1..3")
    if not callable(cpu_expired) or not callable(getattr(rng, "choice", None)):
        raise ValueError("CPU callback and RNG choice are required")
    transitions, completed_depth = 0, 0
    budget_exhausted = False
    best_actions = None

    def check_cpu():
        if cpu_expired():
            raise _CpuExpired()

    def successor(position, action):
        nonlocal transitions
        check_cpu()
        if transitions >= max_transitions:
            raise _TransitionLimit()
        transitions += 1
        child = apply_action(definition, position, action)
        check_cpu()
        return child

    def value(position, depth, alpha, beta):
        check_cpu()
        if position.winner is not None or depth == 0:
            score = evaluate_state(definition, position)
            check_cpu()
            return score
        actions = legal_actions(definition, position)
        check_cpu()
        if not actions:
            raise ValueError("nonterminal connection state has no legal action")
        maximize = position.to_move is Player.A
        best = float("-inf") if maximize else float("inf")
        for action in actions:
            score = value(successor(position, action), depth - 1, alpha, beta)
            if maximize:
                best = max(best, score)
                alpha = max(alpha, best)
            else:
                best = min(best, score)
                beta = min(beta, best)
            if alpha >= beta:
                break
        return best

    try:
        check_cpu()
        validate_state(definition, state)
        actions = legal_actions(definition, state)
        check_cpu()
        if state.winner is not None:
            return Selection(None, 0, 0, False, False, False)
        if not actions:
            raise ValueError("nonterminal connection state has no legal action")
        if policy == "random-v1":
            selected = rng.choice(actions)
            check_cpu()
            return Selection(selected, 0, 0, False, False, False)
        final_depth = 1 if policy == "connection-greedy-v1" else max_depth
        maximize = state.to_move is Player.A
        for depth in range(1, final_depth + 1):
            iteration_best = float("-inf") if maximize else float("inf")
            iteration_actions = []
            try:
                for action in actions:
                    # Each root child needs an exact score, not an alpha/beta bound.
                    score = value(successor(state, action), depth - 1,
                                  float("-inf"), float("inf"))
                    better = score > iteration_best if maximize else score < iteration_best
                    if better:
                        iteration_best, iteration_actions = score, [action]
                    elif score == iteration_best:
                        iteration_actions.append(action)
                check_cpu()
            except _TransitionLimit:
                budget_exhausted = True
                break
            best_actions = iteration_actions
            completed_depth = depth
        check_cpu()
        fallback = best_actions is None
        selected = actions[0] if fallback else rng.choice(best_actions)
        check_cpu()
        return Selection(selected, completed_depth, transitions, budget_exhausted, fallback, False)
    except _CpuExpired:
        return Selection(None, completed_depth, transitions, budget_exhausted, False, True)
