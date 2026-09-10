"""Lexicographic screening cascade for generated definitions."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Sequence, Set, Tuple

from .agents import GoalDirectedAgent, RandomAgent
from .analysis import FailureCode, analyze_definition
from .asymmetry import evaluate_asymmetry
from .dsl import GameDefinition, Player, definition_hash
from .generator import GeneratorConfig, generate_definitions
from .play import MatchupResult, evaluate_matchup, profile_disagreement
from .simplicity import evaluate_simplicity


@dataclass(frozen=True)
class PlayGates:
    max_draw_rate: float = 0.50
    min_average_plies: float = 4.0
    max_average_plies_fraction: float = 0.85
    dominance_interval_margin: float = 0.05
    disagreement_threshold: float = 0.15


@dataclass(frozen=True)
class BatchConfig:
    generator_seed: int
    candidate_count: int
    play_seeds: Tuple[int, ...]
    generator_version: int = 2
    gates: PlayGates = PlayGates()


def _play_failures(
    definition: GameDefinition,
    results: Sequence[MatchupResult],
    gates: PlayGates,
) -> Set[FailureCode]:
    failures: Set[FailureCode] = set()
    for result in results:
        if result.draws / result.samples > gates.max_draw_rate:
            failures.add(FailureCode.EXCESSIVE_DRAWS)
        if result.average_plies < gates.min_average_plies:
            failures.add(FailureCode.TOO_SHORT)
        if result.average_plies > definition.max_plies * gates.max_average_plies_fraction:
            failures.add(FailureCode.TOO_LONG)
        interval = result.decisive_a_wilson_95
        if interval is not None:
            if interval[0] > 0.5 + gates.dominance_interval_margin:
                failures.add(FailureCode.A_DOMINANT)
            if interval[1] < 0.5 - gates.dominance_interval_margin:
                failures.add(FailureCode.B_DOMINANT)
    if profile_disagreement(results, gates.disagreement_threshold):
        failures.add(FailureCode.AGENT_DISAGREEMENT)
    return failures


def classify_play_failures(
    definition: GameDefinition,
    results: Sequence[MatchupResult],
    gates: PlayGates,
) -> Set[FailureCode]:
    """Public stable entry point for applying the frozen play gates."""

    return _play_failures(definition, results, gates)


def screen_batch(config: BatchConfig) -> Dict[str, Any]:
    if not config.play_seeds:
        raise ValueError("batch requires at least one play seed")
    definitions = generate_definitions(
        GeneratorConfig(
            seed=config.generator_seed,
            candidate_count=config.candidate_count,
            version=config.generator_version,
        )
    )
    random_agent = RandomAgent()
    directed_agent = GoalDirectedAgent()
    records: List[Dict[str, Any]] = []
    failure_histogram: Counter[str] = Counter()
    play_evaluated = 0

    for definition in definitions:
        game_hash = definition_hash(definition)
        static = analyze_definition(definition)
        asymmetry = evaluate_asymmetry(definition)
        simplicity = evaluate_simplicity(definition)
        failures = set(static.failure_codes)
        stages = ["static", "asymmetry", "simplicity"]
        if not asymmetry.qualifies:
            failures.add(FailureCode.TOO_SYMMETRIC)
        play_results: Tuple[MatchupResult, ...] = ()
        if not failures:
            play_evaluated += 1
            stages.append("sampled_play")
            play_results = (
                evaluate_matchup(
                    definition,
                    "weak-random",
                    {Player.A: random_agent, Player.B: random_agent},
                    config.play_seeds,
                ),
                evaluate_matchup(
                    definition,
                    "medium-goal-directed",
                    {Player.A: directed_agent, Player.B: directed_agent},
                    config.play_seeds,
                ),
            )
            failures.update(_play_failures(definition, play_results, config.gates))
        codes = sorted(code.value for code in failures)
        failure_histogram.update(codes)
        records.append(
            {
                "definition_hash": game_hash,
                "definition": definition.to_dict(),
                "status": "SURVIVES_PROVISIONAL" if not codes else "REJECTED",
                "failure_codes": codes,
                "evaluated_stages": stages,
                "static": static.to_dict(),
                "asymmetry": asymmetry.to_dict(),
                "simplicity": simplicity.to_dict(),
                "play_profiles": [result.to_dict(include_records=False) for result in play_results],
            }
        )

    survivors = [record for record in records if record["status"] == "SURVIVES_PROVISIONAL"]

    def frontier_key(record: Dict[str, Any]) -> Tuple[Any, ...]:
        profiles = record["play_profiles"]
        fairness_deviation = max(
            abs(profile["decisive_a_share"] - 0.5)
            if profile["decisive_a_share"] is not None
            else 1.0
            for profile in profiles
        )
        return (
            fairness_deviation,
            record["simplicity"]["structural"]["numeric_parameters"],
            record["simplicity"]["description"]["independent_statements"],
            record["definition_hash"],
        )

    frontier = [record["definition_hash"] for record in sorted(survivors, key=frontier_key)[:10]]
    return {
        "configuration": {
            "generator_version": config.generator_version,
            "generator_seed": config.generator_seed,
            "candidate_count": config.candidate_count,
            "play_seeds": list(config.play_seeds),
            "play_gates": asdict(config.gates),
        },
        "aggregate": {
            "generated_unique": len(records),
            "static_evaluated": len(records),
            "play_evaluated": play_evaluated,
            "provisional_survivors": len(survivors),
            "failure_histogram": dict(sorted(failure_histogram.items())),
            "frontier": frontier,
        },
        "candidates": records,
    }
