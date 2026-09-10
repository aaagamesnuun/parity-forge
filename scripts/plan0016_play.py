"""Small trace-preserving adapter for the registered Plan-0016 pilot.

Selection, schedule identity, persistence, and triage belong to the runner.
This module only plays one supplied definition and summarizes one condition.
"""

from __future__ import annotations

import json
import random
from collections import Counter
from typing import Any, Dict, Iterable, Mapping

from parity_forge.agents import RandomAgent, SearchBudgetExceeded
from parity_forge.dsl import Player, canonical_json, definition_hash, parse_definition
from parity_forge.engine import apply_action, initial_state, legal_actions, replay_dicts
from parity_forge.terminal_search import TerminalOnlyMinimaxAgent


class PilotPlayError(RuntimeError):
    """An unexpected failure with the observed prefix retained for the runner."""

    def __init__(self, message: str, partial_record: Dict[str, Any]) -> None:
        super().__init__(message)
        self.partial_record = partial_record


def _json(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    )


def _integer(value: Any, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError("{} must be an integer >= {}".format(label, minimum))
    return value


def _position_key(state: Any) -> tuple:
    # Engine pieces are canonical. Deliberately exclude ply and outcome.
    return (state.to_move, state.pieces)


def play_one(
    definition_mapping: Mapping[str, Any],
    policy_a: int,
    policy_b: int,
    seed: int,
    max_nodes: int = 5000,
) -> Dict[str, Any]:
    """Play with fresh role agents; 0=random and 1/2=terminal-only depth.

    COMPLETE and SEARCH_CENSORED are ordinary results. Other execution failures
    raise PilotPlayError, whose partial_record must be retained before stopping.
    Short-horizon schema-v4 definitions are accepted for fixture calibration.
    """
    for policy in (policy_a, policy_b):
        if type(policy) is not int or policy not in (0, 1, 2):
            raise ValueError("policy must be exactly 0, 1, or 2")
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    _integer(max_nodes, "max_nodes", 1)
    input_snapshot = _json(definition_mapping)
    definition = parse_definition(definition_mapping)
    if definition.schema_version != 4:
        raise ValueError("Plan-0016 play requires schema v4")
    definition_snapshot = canonical_json(definition)
    definition_id = definition_hash(definition)
    agents = {
        role: RandomAgent() if policy == 0 else TerminalOnlyMinimaxAgent(policy, max_nodes)
        for role, policy in ((Player.A, policy_a), (Player.B, policy_b))
    }
    rng = random.Random(seed)
    actions = []
    decisions = []
    state = None

    def nodes() -> Dict[str, int]:
        return {role.value: getattr(agent, "total_nodes", 0) for role, agent in agents.items()}

    def record(status: str, censor: Any = None, failure: Any = None) -> Dict[str, Any]:
        outcome = state.outcome if state is not None else None
        return {
            "definition_hash": definition_id,
            "first_player": definition.first_player.value,
            "policy_a": policy_a,
            "policy_b": policy_b,
            "agent_a": agents[Player.A].identity.key,
            "agent_b": agents[Player.B].identity.key,
            "seed": seed,
            "max_nodes_per_role": max_nodes,
            "status": status,
            "actions": list(actions),
            "winner": outcome.winner.value if outcome is not None and outcome.winner else None,
            "terminal_reason": outcome.reason if outcome is not None else None,
            "plies": len(actions),
            "nodes_by_role": nodes(),
            "decisions": list(decisions),
            "state_after_prefix": state.to_dict() if state is not None else None,
            "censor": censor,
            "failure": failure,
        }

    try:
        state = initial_state(definition)
        censor = None
        while not state.terminal:
            choices = legal_actions(definition, state)
            if not choices:
                raise ValueError("nonterminal state has no legal actions")
            actor = state.to_move
            agent = agents[actor]
            before = getattr(agent, "total_nodes", 0)
            decision = {
                "ply": state.ply,
                "actor": actor.value,
                "legal_action_count": len(choices),
                "distinct_successor_position_count": len({
                    _position_key(apply_action(definition, state, action))
                    for action in choices
                }),
                "selected_action": None,
                "nodes_before": before,
                "nodes_after": before,
                "expanded_nodes": None,
                "cache_hits": None,
                "selection_status": "STARTED",
            }
            decisions.append(decision)
            try:
                selected = agent.select_action(definition, state, choices, rng)
                if selected not in choices:
                    raise ValueError("agent selected an action outside the engine legal set")
                decision.update(
                    selected_action=selected.to_dict(),
                    nodes_after=getattr(agent, "total_nodes", 0),
                    expanded_nodes=getattr(agent, "last_expanded_nodes", None),
                    cache_hits=getattr(agent, "last_cache_hits", None),
                    selection_status="SELECTED",
                )
                successor = apply_action(definition, state, selected)
            except SearchBudgetExceeded as error:
                after = getattr(agent, "total_nodes", 0)
                decision.update(
                    nodes_after=after, expanded_nodes=after - before,
                    selection_status="SEARCH_CENSORED",
                )
                censor = {
                    "role": actor.value,
                    "reason": "SEARCH_BUDGET",
                    "scope": error.scope,
                    "visited_nodes": error.visited_nodes,
                    "max_nodes": error.max_nodes,
                }
                break
            except Exception:
                after = getattr(agent, "total_nodes", 0)
                decision.update(
                    nodes_after=after, expanded_nodes=after - before,
                    selection_status="FAILED",
                )
                raise
            actions.append(selected.to_dict())
            state = successor

        if replay_dicts(definition, actions) != state:
            raise ValueError("replayed prefix differs from observed state")
        if _json(definition_mapping) != input_snapshot or canonical_json(definition) != definition_snapshot:
            raise ValueError("definition input drifted during play")
        if censor is not None:
            if state.terminal:
                raise ValueError("censored prefix unexpectedly has a terminal outcome")
            return record("SEARCH_CENSORED", censor=censor)
        return record("COMPLETE")
    except Exception as error:
        partial = record("FAILED", failure={"type": type(error).__name__, "message": str(error)})
        raise PilotPlayError(str(error), partial) from error


def _lengths(values: list) -> Dict[str, Any]:
    return {
        "count": len(values), "total": sum(values),
        "minimum": min(values) if values else None,
        "maximum": max(values) if values else None,
        "mean": sum(values) / len(values) if values else None,
    }


def summarize_games(records: Iterable[Mapping[str, Any]], planned_count: int) -> Dict[str, Any]:
    """Describe one first-player/ordered-policy cell; orientations may vary.

    This function produces no triage flag, confidence interval, or fairness
    claim. The runner retains the orientation axes and planned schedule.
    """
    _integer(planned_count, "planned_count")
    rows = tuple(records)
    if len(rows) > planned_count:
        raise ValueError("observed records exceed the planned count")
    conditions = set()
    for row in rows:
        first, policy_a, policy_b = row["first_player"], row["policy_a"], row["policy_b"]
        if first not in ("A", "B") or any(type(p) is not int or p not in (0, 1, 2) for p in (policy_a, policy_b)):
            raise ValueError("invalid summary condition")
        conditions.add((first, policy_a, policy_b))
    if len(conditions) > 1:
        raise ValueError("cannot pool first players or ordered policy pairs")
    complete, censored, failed = [], [], []
    decisions = []
    node_totals = {"A": 0, "B": 0}
    for row in rows:
        _integer(row["plies"], "record plies")
        if len(row["actions"]) != row["plies"]:
            raise ValueError("record action prefix length differs from plies")
        if row["status"] == "COMPLETE":
            if row["terminal_reason"] not in ("GOAL", "NO_LEGAL_ACTION", "PLY_LIMIT") or row["winner"] not in ("A", "B", None):
                raise ValueError("completed record has an invalid terminal result")
            if (row["terminal_reason"] == "GOAL" and row["winner"] is None) or (row["terminal_reason"] == "PLY_LIMIT" and row["winner"] is not None):
                raise ValueError("terminal reason and winner disagree")
            complete.append(row)
        elif row["status"] == "SEARCH_CENSORED":
            if row["winner"] is not None or row["terminal_reason"] is not None or row["censor"] is None:
                raise ValueError("censored record must not carry a game result")
            censored.append(row)
        elif row["status"] == "FAILED":
            failed.append(row)
        else:
            raise ValueError("unknown game record status")
        for role in ("A", "B"):
            node_totals[role] += _integer(row["nodes_by_role"][role], "role nodes")
        for decision in row["decisions"]:
            legal = _integer(decision["legal_action_count"], "legal count", 1)
            distinct = _integer(decision["distinct_successor_position_count"], "distinct successor count", 1)
            if distinct > legal:
                raise ValueError("distinct successors exceed legal actions")
            decisions.append(decision)
    a_wins = sum(row["winner"] == "A" for row in complete)
    b_wins = sum(row["winner"] == "B" for row in complete)
    draws = sum(row["winner"] is None for row in complete)
    ply_draws = sum(row["winner"] is None and row["terminal_reason"] == "PLY_LIMIT" for row in complete)
    condition = None
    if conditions:
        first, policy_a, policy_b = next(iter(conditions))
        condition = {"first_player": first, "policy_a": policy_a, "policy_b": policy_b}
    return {
        "condition": condition,
        "planned": planned_count, "attempted": len(rows),
        "completed": len(complete), "search_censored": len(censored),
        "failed": len(failed), "not_started": planned_count - len(rows),
        "a_wins": a_wins, "b_wins": b_wins, "draws": draws,
        "natural_draws": draws - ply_draws, "ply_limit_draws": ply_draws,
        "decisive_games": a_wins + b_wins,
        "decisive_a_share": a_wins / (a_wins + b_wins) if a_wins + b_wins else None,
        "terminal_reasons": dict(sorted(Counter(row["terminal_reason"] for row in complete).items())),
        "censor_roles": dict(sorted(Counter(row["censor"]["role"] for row in censored).items())),
        "lengths": {
            "completed": _lengths([row["plies"] for row in complete]),
            "censored_prefixes": _lengths([row["plies"] for row in censored]),
            "failed_prefixes": _lengths([row["plies"] for row in failed]),
        },
        "nodes_by_role": node_totals,
        "choices": {
            "decision_starts": len(decisions),
            "legal_action_total": sum(d["legal_action_count"] for d in decisions),
            "distinct_successor_position_total": sum(d["distinct_successor_position_count"] for d in decisions),
            "multiple_legal_action_decisions": sum(d["legal_action_count"] > 1 for d in decisions),
            "multiple_successor_position_decisions": sum(d["distinct_successor_position_count"] > 1 for d in decisions),
            "reconvergent_decisions": sum(d["distinct_successor_position_count"] < d["legal_action_count"] for d in decisions),
            "collapsed_action_total": sum(d["legal_action_count"] - d["distinct_successor_position_count"] for d in decisions),
        },
    }


__all__ = ["PilotPlayError", "play_one", "summarize_games"]
