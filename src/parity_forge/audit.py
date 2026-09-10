"""Cross-check sampled evaluator claims against exact results where tractable."""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Mapping, Sequence

from .dsl import parse_definition
from .solver import solve_game


def sampled_direction(profile: Mapping[str, Any]) -> str:
    share = profile.get("decisive_a_share")
    if share is None or share == 0.5:
        return "DRAW_OR_BALANCED"
    return "A_WIN" if share > 0.5 else "B_WIN"


def exact_audit(
    candidates: Sequence[Mapping[str, Any]], max_board_size: int = 3
) -> Dict[str, Any]:
    audited = []
    forced_results: Counter[str] = Counter()
    profile_confusion: Dict[str, Counter[str]] = {}
    for candidate in candidates:
        definition = parse_definition(candidate["definition"])
        if definition.board_size > max_board_size or not candidate.get("play_profiles"):
            continue
        solved = solve_game(definition)
        forced_results[solved.forced_result] += 1
        profile_directions = {}
        for profile in candidate["play_profiles"]:
            label = profile["profile"]
            direction = sampled_direction(profile)
            profile_directions[label] = direction
            profile_confusion.setdefault(label, Counter())[
                "{}->{}".format(direction, solved.forced_result)
            ] += 1
        audited.append(
            {
                "definition_hash": candidate["definition_hash"],
                "prior_failure_codes": candidate["failure_codes"],
                "sampled_directions": profile_directions,
                "solve": solved.to_dict(),
            }
        )
    return {
        "max_board_size": max_board_size,
        "audited_count": len(audited),
        "forced_result_histogram": dict(sorted(forced_results.items())),
        "profile_direction_confusion": {
            label: dict(sorted(counter.items()))
            for label, counter in sorted(profile_confusion.items())
        },
        "candidates": audited,
    }
