"""Blind held-out checks for the exact-completed 3x3 strong-run subset."""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Mapping, Sequence, Tuple

from .agents import MinimaxAgent, SearchBudgetExceeded
from .audit import sampled_direction
from .dsl import Player, definition_hash, parse_definition
from .play import evaluate_matchup


_FORCED_RESULTS = {"A_WIN", "B_WIN", "DRAW"}


def _matches_exact(direction: str, forced_result: str) -> bool:
    return direction == forced_result or (
        direction == "DRAW_OR_BALANCED" and forced_result == "DRAW"
    )


def _eligible_exact_3x3(
    candidates: Sequence[Mapping[str, Any]],
) -> Tuple[Tuple[Mapping[str, Any], Any, str], ...]:
    """Select by exact completion and board size, never by admission outcome."""

    eligible = []
    seen_hashes = set()
    for candidate in candidates:
        game_hash = candidate.get("definition_hash")
        if not isinstance(game_hash, str):
            raise ValueError("every strong-run candidate needs a definition_hash")
        if game_hash in seen_hashes:
            raise ValueError("strong-run candidates must have unique definition hashes")
        seen_hashes.add(game_hash)

        late_stage = candidate.get("late_stage")
        if not isinstance(late_stage, Mapping):
            continue
        exact = late_stage.get("exact_result")
        if exact is None:
            continue
        if not isinstance(exact, Mapping):
            raise ValueError("exact_result must be an object or null")

        definition_mapping = candidate.get("definition")
        if not isinstance(definition_mapping, Mapping):
            raise ValueError("an exact-completed candidate needs a definition")
        definition = parse_definition(definition_mapping)
        if definition_hash(definition) != game_hash:
            raise ValueError("candidate definition hash does not match its definition")
        if definition.board_size != 3:
            continue

        forced_result = exact.get("forced_result")
        if forced_result not in _FORCED_RESULTS:
            raise ValueError("exact_result has an unknown forced_result")
        eligible.append((candidate, definition, forced_result))

    return tuple(sorted(eligible, key=lambda item: item[0]["definition_hash"]))


def blind_depth5_audit(
    candidates: Sequence[Mapping[str, Any]],
    seeds: Sequence[int],
    max_nodes_per_candidate: int,
    depth: int = 5,
) -> Dict[str, Any]:
    """Re-evaluate every exact-completed 3x3 case independently of admission.

    The node allowance accumulates across every move and seed for one definition.
    Exhaustion defers that definition and contributes no direction classification.
    Input candidates are never mutated.
    """

    seed_tuple = tuple(seeds)
    if not seed_tuple:
        raise ValueError("blind audit requires at least one seed")
    if len(set(seed_tuple)) != len(seed_tuple):
        raise ValueError("blind-audit seeds must be unique")
    if depth != 5:
        raise ValueError("the held-out blind audit freezes minimax depth at 5")
    if max_nodes_per_candidate < 1:
        raise ValueError("max_nodes_per_candidate must be at least one")

    eligible = _eligible_exact_3x3(candidates)
    records = []
    confusion: Counter[str] = Counter()
    matching_directions = 0
    exact_draw_count = 0
    evaluated_exact_draw_count = 0
    draw_decisive_hashes = []
    expanded_node_counts = []

    for candidate, definition, forced_result in eligible:
        game_hash = candidate["definition_hash"]
        admitted = bool(candidate["late_stage"].get("admitted", False))
        if forced_result == "DRAW":
            exact_draw_count += 1

        agent = MinimaxAgent(
            depth=depth,
            max_total_nodes=max_nodes_per_candidate,
        )
        try:
            profile = evaluate_matchup(
                definition,
                "blind-minimax-depth5",
                {Player.A: agent, Player.B: agent},
                seed_tuple,
            )
        except SearchBudgetExceeded as error:
            expanded_node_counts.append(agent.total_nodes)
            records.append(
                {
                    "definition_hash": game_hash,
                    "admitted": admitted,
                    "exact_forced_result": forced_result,
                    "status": "DEFERRED_NODE_BUDGET",
                    "sampled_direction": None,
                    "direction_matches_exact": None,
                    "exact_draw_decisive_misclassification": None,
                    "expanded_nodes": agent.total_nodes,
                    "budget_observation": {
                        "scope": error.scope,
                        "visited_nodes": error.visited_nodes,
                        "max_nodes": error.max_nodes,
                    },
                    "profile": None,
                }
            )
            continue

        profile_mapping = profile.to_dict(include_records=False)
        direction = sampled_direction(profile_mapping)
        matches = _matches_exact(direction, forced_result)
        draw_decisive = forced_result == "DRAW" and direction in {
            "A_WIN",
            "B_WIN",
        }
        if matches:
            matching_directions += 1
        if forced_result == "DRAW":
            evaluated_exact_draw_count += 1
        if draw_decisive:
            draw_decisive_hashes.append(game_hash)
        confusion["{}->{}".format(direction, forced_result)] += 1
        expanded_node_counts.append(agent.total_nodes)
        records.append(
            {
                "definition_hash": game_hash,
                "admitted": admitted,
                "exact_forced_result": forced_result,
                "status": "EVALUATED",
                "sampled_direction": direction,
                "direction_matches_exact": matches,
                "exact_draw_decisive_misclassification": draw_decisive,
                "expanded_nodes": agent.total_nodes,
                "budget_observation": None,
                "profile": profile_mapping,
            }
        )

    evaluated_count = sum(record["status"] == "EVALUATED" for record in records)
    deferred_count = len(records) - evaluated_count
    admitted_count = sum(record["admitted"] for record in records)
    return {
        "configuration": {
            "depth": depth,
            "seeds": list(seed_tuple),
            "max_nodes_per_candidate": max_nodes_per_candidate,
            "eligibility": "exact-completed 3x3 candidates; admission ignored",
        },
        "aggregate": {
            "eligible_count": len(records),
            "attempted_count": len(records),
            "evaluated_count": evaluated_count,
            "deferred_count": deferred_count,
            "admitted_count": admitted_count,
            "not_admitted_count": len(records) - admitted_count,
            "matching_directions": matching_directions,
            "direction_accuracy": (
                matching_directions / evaluated_count if evaluated_count else None
            ),
            "direction_confusion": dict(sorted(confusion.items())),
            "exact_draw_count": exact_draw_count,
            "evaluated_exact_draw_count": evaluated_exact_draw_count,
            "exact_draw_decisive_misclassifications": len(
                draw_decisive_hashes
            ),
            "exact_draw_decisive_hashes": sorted(draw_decisive_hashes),
            "expanded_nodes_total": sum(expanded_node_counts),
            "expanded_nodes_max": max(expanded_node_counts, default=0),
        },
        "candidates": records,
    }
