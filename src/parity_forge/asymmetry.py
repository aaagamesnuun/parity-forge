"""Mechanical asymmetry diagnostics that ignore labels and colors."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict

from .dsl import ActionKind, GameDefinition, MOVEMENT_ACTION_KINDS, Player
from .engine import GameState, legal_actions


@dataclass(frozen=True)
class AsymmetryReport:
    action_primitives_differ: bool
    placement_rights_differ: bool
    mobility_rights_differ: bool
    goal_primitives_differ: bool
    action_arity_differs: bool
    initial_mobility_counts_differ: bool
    distinct_dimensions: int
    qualifies: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def evaluate_asymmetry(definition: GameDefinition) -> AsymmetryReport:
    role_a = definition.role(Player.A)
    role_b = definition.role(Player.B)
    action_primitives_differ = role_a.action.kind is not role_b.action.kind
    placement_rights_differ = (
        role_a.action.kind is ActionKind.PLACE
    ) != (role_b.action.kind is ActionKind.PLACE)
    mobility_rights_differ = (
        role_a.action.kind in MOVEMENT_ACTION_KINDS
    ) != (role_b.action.kind in MOVEMENT_ACTION_KINDS)
    goal_primitives_differ = role_a.goal.kind is not role_b.goal.kind
    action_arity_differs = (
        2 if role_a.action.kind is ActionKind.PLACE else 4
    ) != (
        2 if role_b.action.kind is ActionKind.PLACE else 4
    )
    base = GameState(
        ply=0,
        to_move=Player.A,
        pieces=definition.initial_pieces,
    )
    a_count = len(legal_actions(definition, base))
    b_count = len(
        legal_actions(
            definition,
            GameState(ply=0, to_move=Player.B, pieces=definition.initial_pieces),
        )
    )
    initial_mobility_counts_differ = a_count != b_count
    dimensions = (
        action_primitives_differ,
        placement_rights_differ,
        mobility_rights_differ,
        goal_primitives_differ,
        action_arity_differs,
        initial_mobility_counts_differ,
    )
    # Action-space difference is mandatory; at least one further experiential
    # dimension prevents renamed primitives from qualifying alone.
    qualifies = action_primitives_differ and sum(dimensions) >= 2
    return AsymmetryReport(
        action_primitives_differ=action_primitives_differ,
        placement_rights_differ=placement_rights_differ,
        mobility_rights_differ=mobility_rights_differ,
        goal_primitives_differ=goal_primitives_differ,
        action_arity_differs=action_arity_differs,
        initial_mobility_counts_differ=initial_mobility_counts_differ,
        distinct_dimensions=sum(dimensions),
        qualifies=qualifies,
    )
