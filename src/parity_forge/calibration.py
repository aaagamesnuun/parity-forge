"""Evaluate a changed agent on a frozen exactly solved corpus."""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Mapping, Sequence

from .agents import MinimaxAgent
from .audit import sampled_direction
from .dsl import Player, parse_definition
from .play import evaluate_matchup


def calibrate_minimax(
    candidates: Sequence[Mapping[str, Any]],
    exact_candidates: Sequence[Mapping[str, Any]],
    seeds: Sequence[int],
    depth: int,
) -> Dict[str, Any]:
    by_hash = {candidate["definition_hash"]: candidate for candidate in candidates}
    agent = MinimaxAgent(depth=depth)
    confusion: Counter[str] = Counter()
    results = []
    for exact in exact_candidates:
        game_hash = exact["definition_hash"]
        candidate = by_hash[game_hash]
        definition = parse_definition(candidate["definition"])
        profile = evaluate_matchup(
            definition,
            "strong-minimax-depth{}".format(depth),
            {Player.A: agent, Player.B: agent},
            seeds,
        )
        direction = sampled_direction(profile.to_dict(include_records=False))
        forced = exact["solve"]["forced_result"]
        confusion["{}->{}".format(direction, forced)] += 1
        results.append(
            {
                "definition_hash": game_hash,
                "forced_result": forced,
                "sampled_direction": direction,
                "profile": profile.to_dict(include_records=False),
            }
        )
    matches = sum(
        result["sampled_direction"] == result["forced_result"]
        or (
            result["sampled_direction"] == "DRAW_OR_BALANCED"
            and result["forced_result"] == "DRAW"
        )
        for result in results
    )
    return {
        "agent": agent.identity.key,
        "depth": depth,
        "seeds": list(seeds),
        "audited_count": len(results),
        "matching_directions": matches,
        "direction_accuracy": matches / len(results) if results else None,
        "direction_confusion": dict(sorted(confusion.items())),
        "candidates": results,
    }
