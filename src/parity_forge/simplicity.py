"""Transparent, separate complexity dimensions for supported DSL schemas."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict

from .dsl import (
    ActionKind,
    GameDefinition,
    Player,
    VECTOR_ACTION_KINDS,
    describe_rules,
)
from .engine import initial_state, legal_actions


@dataclass(frozen=True)
class StructuralComplexity:
    action_types: int
    piece_types: int
    state_variables: int
    numeric_parameters: int
    victory_clauses: int
    exception_clauses: int
    phases: int
    action_substeps: int
    primitive_concepts: int


@dataclass(frozen=True)
class DescriptionComplexity:
    independent_statements: int
    conditional_clauses: int
    exception_clauses: int
    learned_concepts: int


@dataclass(frozen=True)
class OperationalComplexity:
    max_action_parameters: int
    tracked_fields: int
    initial_legal_actions: int


@dataclass(frozen=True)
class SimplicityReport:
    structural: StructuralComplexity
    description: DescriptionComplexity
    operational: OperationalComplexity

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ComplexityLimits:
    """Provisional gates, kept explicit so experiments can freeze them."""

    max_piece_types: int = 4
    max_numeric_parameters: int = 16
    max_independent_statements: int = 10
    max_initial_legal_actions: int = 25


DEFAULT_LIMITS = ComplexityLimits()


def evaluate_simplicity(definition: GameDefinition) -> SimplicityReport:
    roles = [definition.role(player) for player in (Player.A, Player.B)]
    action_types = {role.action.kind for role in roles}
    piece_types = {
        item
        for role in roles
        for item in (role.action.piece, role.goal.piece)
    }
    piece_types.update(piece.piece for piece in definition.initial_pieces)
    numeric_parameters = 2 + sum(
        len(role.action.vectors) * 2
        for role in roles
        if role.action.kind in VECTOR_ACTION_KINDS
    )
    action_concepts = set()
    for role in roles:
        if role.action.kind is ActionKind.PLACE:
            action_concepts.add(ActionKind.PLACE.value)
        elif role.action.kind is ActionKind.CONVERT:
            # CONVERT is a vector-bearing ownership/kind transformation, not a
            # relocation with an optional special form.
            action_concepts.add(ActionKind.CONVERT.value)
        else:
            action_concepts.add(ActionKind.MOVE.value)
            if role.action.kind in (
                ActionKind.MOVE_CAPTURE,
                ActionKind.PUSH,
                ActionKind.SWAP,
                ActionKind.HOP,
            ):
                action_concepts.add(role.action.kind.value)
    primitive_concepts = len(
        action_concepts | {role.goal.kind.value for role in roles}
    )
    has_capture = any(
        role.action.kind is ActionKind.MOVE_CAPTURE for role in roles
    )
    push_role_count = sum(
        role.action.kind is ActionKind.PUSH for role in roles
    )
    swap_role_count = sum(
        role.action.kind is ActionKind.SWAP for role in roles
    )
    hop_role_count = sum(
        role.action.kind is ActionKind.HOP for role in roles
    )
    terminal_conditional_clauses = 5 if definition.schema_version == 4 else 3
    terminal_contract_concepts = 2 if definition.schema_version == 4 else 0
    # CONVERT has one actor/target relation and one atomic target rewrite, so it
    # retains the two-substep base used by ordinary from/to actions.  Only the
    # optional special forms below add a third substep.
    action_substeps = sum(
        (
            1
            if role.action.kind is ActionKind.PLACE
            else 3
            if role.action.kind in (
                ActionKind.PUSH,
                ActionKind.SWAP,
                ActionKind.HOP,
            )
            else 2
        )
        for role in roles
    )
    statements = describe_rules(definition)
    state = initial_state(definition)
    initial_branching = 0 if state.terminal else len(legal_actions(definition, state))
    return SimplicityReport(
        structural=StructuralComplexity(
            action_types=len(action_types),
            piece_types=len(piece_types),
            state_variables=4,  # board contents, side to move, ply, terminal outcome
            numeric_parameters=numeric_parameters,
            victory_clauses=2,
            exception_clauses=0,
            phases=1,
            action_substeps=action_substeps,
            primitive_concepts=primitive_concepts,
        ),
        description=DescriptionComplexity(
            independent_statements=len(statements),
            conditional_clauses=(
                terminal_conditional_clauses
                + int(has_capture)
                + push_role_count
                + swap_role_count
                + hop_role_count
            ),
            exception_clauses=0,
            learned_concepts=(
                primitive_concepts
                + 4  # board, ownership, empty cell, alternating turn
                + terminal_contract_concepts
            ),
        ),
        operational=OperationalComplexity(
            max_action_parameters=max(
                2 if role.action.kind is ActionKind.PLACE else 4 for role in roles
            ),
            tracked_fields=5,  # position, owner, kind, side to move, ply
            initial_legal_actions=initial_branching,
        ),
    )


def exceeds_limits(
    report: SimplicityReport, limits: ComplexityLimits = DEFAULT_LIMITS
) -> bool:
    return any(
        (
            report.structural.piece_types > limits.max_piece_types,
            report.structural.numeric_parameters > limits.max_numeric_parameters,
            report.description.independent_statements > limits.max_independent_statements,
            report.operational.initial_legal_actions > limits.max_initial_legal_actions,
        )
    )
