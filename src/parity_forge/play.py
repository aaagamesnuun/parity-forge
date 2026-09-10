"""Complete-game simulation and role-separated outcome reporting."""

from __future__ import annotations

import math
import random
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from .agents import Agent
from .dsl import GameDefinition, Player
from .engine import Action, apply_action, initial_state, legal_actions


@dataclass(frozen=True)
class GameRecord:
    seed: int
    agent_a: str
    agent_b: str
    actions: Tuple[Action, ...]
    winner: Optional[Player]
    terminal_reason: str

    @property
    def plies(self) -> int:
        return len(self.actions)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "seed": self.seed,
            "agent_a": self.agent_a,
            "agent_b": self.agent_b,
            "actions": [action.to_dict() for action in self.actions],
            "winner": self.winner.value if self.winner is not None else None,
            "terminal_reason": self.terminal_reason,
            "plies": self.plies,
        }


@dataclass(frozen=True)
class MatchupResult:
    profile: str
    agent_a: str
    agent_b: str
    records: Tuple[GameRecord, ...]
    a_wins: int
    b_wins: int
    draws: int
    average_plies: float
    decisive_a_share: Optional[float]
    decisive_a_wilson_95: Optional[Tuple[float, float]]
    terminal_reasons: Tuple[Tuple[str, int], ...]

    @property
    def samples(self) -> int:
        return len(self.records)

    def to_dict(self, include_records: bool = True) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "profile": self.profile,
            "agent_a": self.agent_a,
            "agent_b": self.agent_b,
            "samples": self.samples,
            "a_wins": self.a_wins,
            "b_wins": self.b_wins,
            "draws": self.draws,
            "a_win_rate": self.a_wins / self.samples if self.samples else None,
            "b_win_rate": self.b_wins / self.samples if self.samples else None,
            "draw_rate": self.draws / self.samples if self.samples else None,
            "average_plies": self.average_plies,
            "decisive_a_share": self.decisive_a_share,
            "decisive_a_wilson_95": list(self.decisive_a_wilson_95) if self.decisive_a_wilson_95 else None,
            "terminal_reasons": dict(self.terminal_reasons),
            "seeds": [record.seed for record in self.records],
        }
        if include_records:
            result["games"] = [record.to_dict() for record in self.records]
        return result


def _wilson_interval(successes: int, samples: int, z: float = 1.959963984540054) -> Optional[Tuple[float, float]]:
    if samples == 0:
        return None
    proportion = successes / samples
    denominator = 1.0 + z * z / samples
    center = (proportion + z * z / (2.0 * samples)) / denominator
    margin = z * math.sqrt(
        proportion * (1.0 - proportion) / samples + z * z / (4.0 * samples * samples)
    ) / denominator
    return (max(0.0, center - margin), min(1.0, center + margin))


def play_game(
    definition: GameDefinition,
    agents: Mapping[Player, Agent],
    seed: int,
) -> GameRecord:
    if set(agents) != {Player.A, Player.B}:
        raise ValueError("agents must provide exactly roles A and B")
    rng = random.Random(seed)
    state = initial_state(definition)
    actions = []
    while not state.terminal:
        choices = legal_actions(definition, state)
        action = agents[state.to_move].select_action(definition, state, choices, rng)
        if action not in choices:
            raise ValueError("agent selected an action outside the engine's legal set")
        actions.append(action)
        state = apply_action(definition, state, action)
    assert state.outcome is not None
    return GameRecord(
        seed=seed,
        agent_a=agents[Player.A].identity.key,
        agent_b=agents[Player.B].identity.key,
        actions=tuple(actions),
        winner=state.outcome.winner,
        terminal_reason=state.outcome.reason,
    )


def evaluate_matchup(
    definition: GameDefinition,
    profile: str,
    agents: Mapping[Player, Agent],
    seeds: Iterable[int],
) -> MatchupResult:
    seed_tuple = tuple(seeds)
    if not seed_tuple:
        raise ValueError("at least one seed is required")
    if len(set(seed_tuple)) != len(seed_tuple):
        raise ValueError("seeds must be unique within a matchup")
    records = tuple(play_game(definition, agents, seed) for seed in seed_tuple)
    a_wins = sum(record.winner is Player.A for record in records)
    b_wins = sum(record.winner is Player.B for record in records)
    draws = sum(record.winner is None for record in records)
    decisive = a_wins + b_wins
    reasons = Counter(record.terminal_reason for record in records)
    return MatchupResult(
        profile=profile,
        agent_a=agents[Player.A].identity.key,
        agent_b=agents[Player.B].identity.key,
        records=records,
        a_wins=a_wins,
        b_wins=b_wins,
        draws=draws,
        average_plies=sum(record.plies for record in records) / len(records),
        decisive_a_share=a_wins / decisive if decisive else None,
        decisive_a_wilson_95=_wilson_interval(a_wins, decisive),
        terminal_reasons=tuple(sorted(reasons.items())),
    )


def profile_disagreement(results: Sequence[MatchupResult], threshold: float = 0.15) -> bool:
    shares = [result.decisive_a_share for result in results if result.decisive_a_share is not None]
    return bool(shares) and max(shares) - min(shares) >= threshold
