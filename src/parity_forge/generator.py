"""Mechanically interpretable structured generation for DSL v1."""

from __future__ import annotations

import random
from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations
from typing import Dict, Tuple

from .dsl import GameDefinition, definition_hash, parse_definition


GENERATOR_VERSION = 2
_VECTORS = (
    (-1, -1),
    (-1, 0),
    (-1, 1),
    (0, -1),
    (0, 1),
    (1, -1),
    (1, 0),
    (1, 1),
)
_EDGE_PAIRS = (("TOP", "BOTTOM"), ("LEFT", "RIGHT"))
_EDGES = ("TOP", "RIGHT", "BOTTOM", "LEFT")


@dataclass(frozen=True)
class GeneratorConfig:
    seed: int
    candidate_count: int
    version: int = GENERATOR_VERSION
    max_attempt_multiplier: int = 50


def _build_definition(
    size: int,
    first: str,
    connection_edges: Tuple[str, str],
    target_edge: str,
    start: Tuple[int, int],
    vectors: Tuple[Tuple[int, int], ...],
    max_plies: int,
) -> GameDefinition:
    """Build one definition without making any random choices."""

    vector_tag = "".join(
        "{}{}".format(row + 1, column + 1) for row, column in vectors
    )
    name = "Forge-n{}-f{}-c{}{}-r{}-s{}{}-v{}-p{}".format(
        size,
        first,
        connection_edges[0][0],
        connection_edges[1][0],
        target_edge[0],
        start[0],
        start[1],
        vector_tag,
        max_plies,
    )
    return parse_definition(
        {
            "schema_version": 1,
            "name": name,
            "board_size": size,
            "first_player": first,
            "max_plies": max_plies,
            "roles": {
                "A": {
                    "action": {"kind": "PLACE", "piece": "seed"},
                    "goal": {
                        "kind": "CONNECT_EDGES",
                        "piece": "seed",
                        "edges": list(connection_edges),
                    },
                },
                "B": {
                    "action": {
                        "kind": "MOVE",
                        "piece": "runner",
                        "vectors": [list(vector) for vector in vectors],
                    },
                    "goal": {
                        "kind": "REACH_EDGE",
                        "piece": "runner",
                        "edge": target_edge,
                    },
                },
            },
            "initial_pieces": [
                {"owner": "B", "piece": "runner", "position": list(start)}
            ],
        }
    )


def _candidate(rng: random.Random, version: int) -> GameDefinition:
    size = rng.choice((3, 4, 5))
    first = rng.choice(("A", "B"))
    connection_edges = rng.choice(_EDGE_PAIRS)
    target_edge = rng.choice(_EDGES)
    raw_start = (rng.randrange(size), rng.randrange(size))
    if version == 1:
        start = raw_start
    else:
        start = {
            "TOP": (size - 1, raw_start[1]),
            "BOTTOM": (0, raw_start[1]),
            "LEFT": (raw_start[0], size - 1),
            "RIGHT": (raw_start[0], 0),
        }[target_edge]
    vector_count = rng.randint(1, len(_VECTORS))
    vectors = tuple(sorted(rng.sample(_VECTORS, vector_count)))
    max_plies = rng.choice((2 * size, 3 * size, 2 * size * size))
    return _build_definition(
        size,
        first,
        connection_edges,
        target_edge,
        start,
        vectors,
        max_plies,
    )


@lru_cache(maxsize=1)
def enumerate_v2_three_by_three() -> Tuple[GameDefinition, ...]:
    """Return the complete generator-v2 3x3 vocabulary in stable order.

    The v2 start mapping discards one coordinate of its sampled raw position, so
    unique enumeration visits the three cells on the edge opposite B's target
    instead of replaying all nine raw-coordinate preimages.
    """

    definitions = []
    size = 3
    for first in ("A", "B"):
        for connection_edges in _EDGE_PAIRS:
            for target_edge in _EDGES:
                for edge_offset in range(size):
                    start = {
                        "TOP": (size - 1, edge_offset),
                        "BOTTOM": (0, edge_offset),
                        "LEFT": (edge_offset, size - 1),
                        "RIGHT": (edge_offset, 0),
                    }[target_edge]
                    for max_plies in (2 * size, 3 * size, 2 * size * size):
                        for vector_count in range(1, len(_VECTORS) + 1):
                            for vectors in combinations(_VECTORS, vector_count):
                                definitions.append(
                                    _build_definition(
                                        size,
                                        first,
                                        connection_edges,
                                        target_edge,
                                        start,
                                        vectors,
                                        max_plies,
                                    )
                                )
    return tuple(definitions)


@lru_cache(maxsize=1)
def enumerate_v2_four_by_four_max8() -> Tuple[GameDefinition, ...]:
    """Return the complete generator-v2 4x4/max-8 vocabulary in stable order.

    This is the native finite-horizon slice used by the Plan-0011 evaluator
    transfer calibration.  As in generator v2, the runner starts on one of the
    four cells of the edge opposite its target.  Every nonempty subset of the
    eight movement vectors is retained here; definition gates are a separate
    concern for the calibration census.
    """

    definitions = []
    size = 4
    max_plies = 8
    for first in ("A", "B"):
        for connection_edges in _EDGE_PAIRS:
            for target_edge in _EDGES:
                for edge_offset in range(size):
                    start = {
                        "TOP": (size - 1, edge_offset),
                        "BOTTOM": (0, edge_offset),
                        "LEFT": (edge_offset, size - 1),
                        "RIGHT": (edge_offset, 0),
                    }[target_edge]
                    for vector_count in range(1, len(_VECTORS) + 1):
                        for vectors in combinations(_VECTORS, vector_count):
                            definitions.append(
                                _build_definition(
                                    size,
                                    first,
                                    connection_edges,
                                    target_edge,
                                    start,
                                    vectors,
                                    max_plies,
                                )
                            )
    return tuple(definitions)


def generate_definitions(config: GeneratorConfig) -> Tuple[GameDefinition, ...]:
    if config.candidate_count < 1:
        raise ValueError("candidate_count must be at least one")
    if config.max_attempt_multiplier < 1:
        raise ValueError("max_attempt_multiplier must be at least one")
    if config.version not in (1, 2):
        raise ValueError("generator version must be 1 or 2")
    rng = random.Random(config.seed)
    unique: Dict[str, GameDefinition] = {}
    max_attempts = config.candidate_count * config.max_attempt_multiplier
    for _ in range(max_attempts):
        definition = _candidate(rng, config.version)
        unique.setdefault(definition_hash(definition), definition)
        if len(unique) == config.candidate_count:
            return tuple(unique.values())
    raise RuntimeError(
        "generated only {} unique definitions after {} attempts".format(len(unique), max_attempts)
    )
