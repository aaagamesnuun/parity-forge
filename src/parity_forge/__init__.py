"""Parity Forge's deterministic game-research core."""

from .dsl import GameDefinition, canonical_json, definition_hash, parse_definition
from .engine import Action, GameState, apply_action, initial_state, legal_actions, replay

__all__ = [
    "Action",
    "GameDefinition",
    "GameState",
    "apply_action",
    "canonical_json",
    "definition_hash",
    "initial_state",
    "legal_actions",
    "parse_definition",
    "replay",
]

__version__ = "0.1.0"
