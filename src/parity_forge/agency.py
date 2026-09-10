"""Pure replay-derived agency and interaction telemetry for schema v4.

Telemetry in this module is descriptive evidence.  It is reconstructed from an
authoritative definition and a *complete* retained action trace; it is not an
agent score, a selector, or a gameplay threshold.  Version 1 deliberately uses
only one-ply counterfactuals and freezes every vocabulary it interprets.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from typing import Any, Dict, Iterable, Iterator, Mapping, Optional, Tuple

from .dsl import (
    ActionKind,
    GameDefinition,
    Player,
    canonical_json,
    parse_definition,
)
from .engine import (
    Action,
    GameState,
    action_from_dict,
    apply_action,
    initial_state,
    legal_actions,
)


REPLAY_TELEMETRY_VERSION = 1

# These tuples, rather than the current Enum iteration order, are the closed
# interpretation domains for telemetry-v1.  A future DSL addition therefore
# fails closed until a new telemetry version explicitly admits it.
ACTION_VOCABULARY_V1 = (
    "PLACE",
    "MOVE",
    "MOVE_CAPTURE",
    "PUSH",
    "SWAP",
    "HOP",
    "CONVERT",
)
GOAL_VOCABULARY_V1 = (
    "CONNECT_EDGES",
    "REACH_EDGE",
    "ELIMINATE",
)
TERMINAL_REASON_VOCABULARY_V1 = (
    "GOAL",
    "NO_LEGAL_ACTION",
    "PLY_LIMIT",
)
EFFECT_MODE_VOCABULARY_V1 = (
    "PLACE",
    "ORDINARY_STEP",
    "CAPTURE",
    "PUSH",
    "SWAP",
    "HOP",
    "CONVERT",
)
OUTCOME_CLASS_VOCABULARY_V1 = (
    "NONTERMINAL",
    "ACTOR_WIN",
    "DRAW",
    "ACTOR_LOSS",
)
DIRECT_EFFECT_STATUS_VOCABULARY_V1 = (
    "NONE",
    "A_ONLY",
    "B_ONLY",
    "BOTH_ROLES",
)

# These are deliberately not a partition of EFFECT_MODE_VOCABULARY_V1.  PLACE
# and CONVERT are standalone actions.  Only the four conditional modes below
# are special alternatives to an ordinary step in the same action ludeme.
ORDINARY_STEP_EFFECT_MODES_V1 = frozenset(("ORDINARY_STEP",))
CONDITIONAL_SPECIAL_EFFECT_MODES_V1 = frozenset(
    ("CAPTURE", "PUSH", "SWAP", "HOP")
)

# A 5x5 occupancy state and eight one-step vectors permit no more than 200
# generated actions.  The horizon is at most 1,000 plies.  The second cap is the
# corresponding worst-case number of observed next actions.  Both are explicit
# work boundaries, not sampling instructions.
MAX_LEGAL_ACTIONS_PER_DECISION_V1 = 200
MAX_COUNTERFACTUAL_SUCCESSORS_V1 = 200_000
MAX_NEXT_ACTION_OBSERVATIONS_V1 = 40_000_000
MAX_REPLAY_ACTIONS_V1 = 1_000
MAX_STORED_JSON_NODES_V1 = 1_000_000
MAX_STORED_JSON_DEPTH_V1 = 32

_STATE_DIGEST_DOMAIN = b"parity-forge-replay-telemetry-v1-state"
_COUNTERFACTUAL_DIGEST_DOMAIN = b"parity-forge-replay-telemetry-v1-counterfactual"
_EVIDENCE_DIGEST_DOMAIN = b"parity-forge-replay-telemetry-v1-evidence"


def _canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ValueError("telemetry values must be finite canonical JSON") from error


def _domain_digest(domain: bytes, value: Any) -> str:
    return hashlib.sha256(domain + b"\0" + _canonical_bytes(value)).hexdigest()


def _histogram(labels: Tuple[str, ...], counts: Mapping[str, int]) -> Tuple[Tuple[str, int], ...]:
    return tuple((label, counts.get(label, 0)) for label in labels)


def _histogram_dict(values: Tuple[Tuple[str, int], ...]) -> Dict[str, int]:
    return {label: count for label, count in values}


@dataclass(frozen=True)
class ActionRecordV1:
    """An immutable exact action record detached from caller-owned JSON."""

    kind: str
    to_position: Tuple[int, int]
    from_position: Optional[Tuple[int, int]] = None

    @classmethod
    def from_action(cls, action: Action) -> "ActionRecordV1":
        return cls(
            kind=action.kind.value,
            from_position=action.from_position,
            to_position=action.to_position,
        )

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "kind": self.kind,
            "to": list(self.to_position),
        }
        if self.from_position is not None:
            result["from"] = list(self.from_position)
        return result


@dataclass(frozen=True)
class StateEffectV1:
    """The selected action's realized, actor-relative state effect."""

    own_placements: int
    own_movements: int
    opponent_movements: int
    conversions: int
    removals: int
    own_piece_count_delta: int
    opponent_piece_count_delta: int
    occupied_cell_delta: int
    opponent_dependency: bool
    realized_opponent_effect: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "own_placements": self.own_placements,
            "own_movements": self.own_movements,
            "opponent_movements": self.opponent_movements,
            "conversions": self.conversions,
            "removals": self.removals,
            "own_piece_count_delta": self.own_piece_count_delta,
            "opponent_piece_count_delta": self.opponent_piece_count_delta,
            "occupied_cell_delta": self.occupied_cell_delta,
            "opponent_dependency": self.opponent_dependency,
            "realized_opponent_effect": self.realized_opponent_effect,
        }


@dataclass(frozen=True)
class ExactFractionV1:
    numerator: int
    denominator: int

    def to_dict(self) -> Dict[str, int]:
        return {"numerator": self.numerator, "denominator": self.denominator}


@dataclass(frozen=True)
class DecisionTelemetryV1:
    ply: int
    actor: str
    pre_state_digest: str
    legal_count: int
    legal_action_kind_counts: Tuple[Tuple[str, int], ...]
    legal_effect_mode_counts: Tuple[Tuple[str, int], ...]
    chosen_action: ActionRecordV1
    chosen_effect_mode: str
    chosen_effect: StateEffectV1
    ordinary_step_available: bool
    conditional_special_available: bool
    chosen_conditional_special: bool
    successor_position_variant_count: int
    effect_signature_variant_count: int
    immediate_reconvergence: bool
    redundant_successor_count: int
    immediate_outcome_class_counts: Tuple[Tuple[str, int], ...]
    immediate_outcome_sensitive: bool
    nonterminal_successor_count: int
    next_legal_set_comparable: bool
    next_legal_set_variant_count: Optional[int]
    next_legal_set_sensitive: Optional[bool]
    counterfactual_digest: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ply": self.ply,
            "actor": self.actor,
            "pre_state_digest": self.pre_state_digest,
            "legal_count": self.legal_count,
            "legal_action_kind_counts": _histogram_dict(
                self.legal_action_kind_counts
            ),
            "legal_effect_mode_counts": _histogram_dict(
                self.legal_effect_mode_counts
            ),
            "chosen_action": self.chosen_action.to_dict(),
            "chosen_effect_mode": self.chosen_effect_mode,
            "chosen_effect": self.chosen_effect.to_dict(),
            "ordinary_step_available": self.ordinary_step_available,
            "conditional_special_available": self.conditional_special_available,
            "chosen_conditional_special": self.chosen_conditional_special,
            "successor_position_variant_count": (
                self.successor_position_variant_count
            ),
            "effect_signature_variant_count": self.effect_signature_variant_count,
            "immediate_reconvergence": self.immediate_reconvergence,
            "redundant_successor_count": self.redundant_successor_count,
            "immediate_outcome_class_counts": _histogram_dict(
                self.immediate_outcome_class_counts
            ),
            "immediate_outcome_sensitive": self.immediate_outcome_sensitive,
            "nonterminal_successor_count": self.nonterminal_successor_count,
            "next_legal_set_comparable": self.next_legal_set_comparable,
            "next_legal_set_variant_count": self.next_legal_set_variant_count,
            "next_legal_set_sensitive": self.next_legal_set_sensitive,
            "counterfactual_digest": self.counterfactual_digest,
        }


@dataclass(frozen=True)
class RoleTelemetryV1:
    player: str
    action_count: int
    decision_count: int
    legal_observation_count: int
    legal_action_count_total: int
    legal_action_count_min: Optional[int]
    legal_action_count_max: Optional[int]
    legal_count_0_observations: int
    legal_count_1_observations: int
    legal_count_2_plus_observations: int
    forced_fraction: Optional[ExactFractionV1]
    legal_action_kind_counts: Tuple[Tuple[str, int], ...]
    legal_effect_mode_counts: Tuple[Tuple[str, int], ...]
    chosen_action_kind_counts: Tuple[Tuple[str, int], ...]
    chosen_effect_mode_counts: Tuple[Tuple[str, int], ...]
    immediate_outcome_class_counts: Tuple[Tuple[str, int], ...]
    ordinary_step_available_decisions: int
    conditional_special_available_decisions: int
    ordinary_step_chosen_actions: int
    conditional_special_chosen_actions: int
    own_placements: int
    own_movements: int
    opponent_movements: int
    conversions: int
    removals: int
    own_piece_count_delta: int
    opponent_piece_count_delta: int
    occupied_cell_delta: int
    opponent_dependency_actions: int
    realized_opponent_effect_actions: int
    immediate_outcome_sensitive_decisions: int
    next_legal_set_comparable_decisions: int
    next_legal_set_sensitive_decisions: int
    immediate_reconvergence_decisions: int
    successor_position_variant_total: int
    effect_signature_variant_total: int
    nonterminal_successor_total: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "player": self.player,
            "action_count": self.action_count,
            "decision_count": self.decision_count,
            "legal_observation_count": self.legal_observation_count,
            "legal_action_count_total": self.legal_action_count_total,
            "legal_action_count_min": self.legal_action_count_min,
            "legal_action_count_max": self.legal_action_count_max,
            "legal_count_bins": {
                "0": self.legal_count_0_observations,
                "1": self.legal_count_1_observations,
                "2+": self.legal_count_2_plus_observations,
            },
            "forced_fraction": (
                self.forced_fraction.to_dict()
                if self.forced_fraction is not None
                else None
            ),
            "legal_action_kind_counts": _histogram_dict(
                self.legal_action_kind_counts
            ),
            "legal_effect_mode_counts": _histogram_dict(
                self.legal_effect_mode_counts
            ),
            "chosen_action_kind_counts": _histogram_dict(
                self.chosen_action_kind_counts
            ),
            "chosen_effect_mode_counts": _histogram_dict(
                self.chosen_effect_mode_counts
            ),
            "immediate_outcome_class_counts": _histogram_dict(
                self.immediate_outcome_class_counts
            ),
            "ordinary_step_available_decisions": (
                self.ordinary_step_available_decisions
            ),
            "conditional_special_available_decisions": (
                self.conditional_special_available_decisions
            ),
            "ordinary_step_chosen_actions": self.ordinary_step_chosen_actions,
            "conditional_special_chosen_actions": (
                self.conditional_special_chosen_actions
            ),
            "own_placements": self.own_placements,
            "own_movements": self.own_movements,
            "opponent_movements": self.opponent_movements,
            "conversions": self.conversions,
            "removals": self.removals,
            "own_piece_count_delta": self.own_piece_count_delta,
            "opponent_piece_count_delta": self.opponent_piece_count_delta,
            "occupied_cell_delta": self.occupied_cell_delta,
            "opponent_dependency_actions": self.opponent_dependency_actions,
            "realized_opponent_effect_actions": (
                self.realized_opponent_effect_actions
            ),
            "immediate_outcome_sensitive_decisions": (
                self.immediate_outcome_sensitive_decisions
            ),
            "next_legal_set_comparable_decisions": (
                self.next_legal_set_comparable_decisions
            ),
            "next_legal_set_sensitive_decisions": (
                self.next_legal_set_sensitive_decisions
            ),
            "immediate_reconvergence_decisions": (
                self.immediate_reconvergence_decisions
            ),
            "successor_position_variant_total": (
                self.successor_position_variant_total
            ),
            "effect_signature_variant_total": self.effect_signature_variant_total,
            "nonterminal_successor_total": self.nonterminal_successor_total,
        }


@dataclass(frozen=True)
class RepetitionEventV1:
    ply: int
    first_seen_ply: int
    previous_seen_ply: int
    period: int
    terminal: bool
    cycle_prefix: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ply": self.ply,
            "first_seen_ply": self.first_seen_ply,
            "previous_seen_ply": self.previous_seen_ply,
            "period": self.period,
            "terminal": self.terminal,
            "cycle_prefix": self.cycle_prefix,
        }


@dataclass(frozen=True)
class RepetitionTelemetryV1:
    state_observation_count: int
    repeat_event_count: int
    repeated_state_count: int
    has_repetition: bool
    first_repeat_ply: Optional[int]
    shortest_period: Optional[int]
    cycle_prefix_count: int
    has_cycle_prefix: bool
    events: Tuple[RepetitionEventV1, ...]

    def to_dict(self) -> Dict[str, Any]:
        first_event = self.events[0] if self.events else None
        terminal_repeated = any(event.terminal for event in self.events)
        cycle_prefix_plies = max(
            (event.ply for event in self.events if event.cycle_prefix),
            default=0,
        )
        return {
            "state_observation_count": self.state_observation_count,
            "repeat_event_count": self.repeat_event_count,
            "repeated_configuration_count": self.repeated_state_count,
            "has_repeated_configuration": self.has_repetition,
            "first_repeat_ply": self.first_repeat_ply,
            "first_repeat_period": (
                first_event.period if first_event is not None else None
            ),
            "shortest_period": self.shortest_period,
            "terminal_configuration_repeated": terminal_repeated,
            "cycle_prefix_event_count": self.cycle_prefix_count,
            "cycle_prefix_plies": cycle_prefix_plies,
            "events": [event.to_dict() for event in self.events],
        }


@dataclass(frozen=True)
class TerminalTelemetryV1:
    ply: int
    winner: Optional[str]
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ply": self.ply,
            "winner": self.winner,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class WorkTelemetryV1:
    replayed_actions: int
    decision_count: int
    state_observation_count: int
    successor_evaluations: int
    next_action_observations: int

    def to_dict(self) -> Dict[str, int]:
        return {
            "replayed_actions": self.replayed_actions,
            "decision_count": self.decision_count,
            "state_observation_count": self.state_observation_count,
            "successor_evaluations": self.successor_evaluations,
            "next_action_observations": self.next_action_observations,
        }


@dataclass(frozen=True)
class ReplayTelemetryV1:
    telemetry_version: int
    dsl_schema_version: int
    definition_hash: str
    action_vocabulary: Tuple[str, ...]
    goal_vocabulary: Tuple[str, ...]
    terminal_reason_vocabulary: Tuple[str, ...]
    effect_mode_vocabulary: Tuple[str, ...]
    outcome_class_vocabulary: Tuple[str, ...]
    direct_effect_status_vocabulary: Tuple[str, ...]
    actions: Tuple[ActionRecordV1, ...]
    decisions: Tuple[DecisionTelemetryV1, ...]
    role_a: RoleTelemetryV1
    role_b: RoleTelemetryV1
    longest_forced_run: int
    direct_effect_status: str
    repetition: RepetitionTelemetryV1
    terminal: TerminalTelemetryV1
    work: WorkTelemetryV1
    evidence_digest: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "telemetry_version": self.telemetry_version,
            "dsl_schema_version": self.dsl_schema_version,
            "definition_hash": self.definition_hash,
            "action_vocabulary": list(self.action_vocabulary),
            "goal_vocabulary": list(self.goal_vocabulary),
            "terminal_reason_vocabulary": list(
                self.terminal_reason_vocabulary
            ),
            "effect_mode_vocabulary": list(self.effect_mode_vocabulary),
            "outcome_class_vocabulary": list(self.outcome_class_vocabulary),
            "direct_effect_status_vocabulary": list(
                self.direct_effect_status_vocabulary
            ),
            "actions": [action.to_dict() for action in self.actions],
            "decisions": [decision.to_dict() for decision in self.decisions],
            "roles": {
                "A": self.role_a.to_dict(),
                "B": self.role_b.to_dict(),
            },
            "longest_forced_run": self.longest_forced_run,
            "direct_effect_status": self.direct_effect_status,
            "repetition": self.repetition.to_dict(),
            "terminal": self.terminal.to_dict(),
            "work": self.work.to_dict(),
            "evidence_digest": self.evidence_digest,
        }


def _canonical_definition_value(value: Any) -> str:
    try:
        if type(value) is GameDefinition:
            return canonical_json(value)
        if isinstance(value, Mapping):
            return canonical_json(parse_definition(value))
    except (AssertionError, AttributeError, TypeError, ValueError) as error:
        raise ValueError("telemetry definition is not canonicalizable") from error
    raise ValueError("telemetry definition must be a GameDefinition or mapping")


def _definition_snapshot(value: Any) -> Tuple[str, GameDefinition]:
    source_seal = _canonical_definition_value(value)
    try:
        detached = parse_definition(json.loads(source_seal))
    except (TypeError, ValueError) as error:
        raise ValueError("telemetry definition snapshot cannot be parsed") from error
    if detached.schema_version != 4:
        raise ValueError("replay telemetry v1 accepts only schema-v4 definitions")
    action_values = tuple(
        detached.role(player).action.kind.value for player in (Player.A, Player.B)
    )
    goal_values = tuple(
        detached.role(player).goal.kind.value for player in (Player.A, Player.B)
    )
    if any(value not in ACTION_VOCABULARY_V1 for value in action_values):
        raise ValueError("definition uses an action outside telemetry-v1 vocabulary")
    if any(value not in GOAL_VOCABULARY_V1 for value in goal_values):
        raise ValueError("definition uses a goal outside telemetry-v1 vocabulary")
    return source_seal, detached


def _require_exact_position(value: Any, label: str) -> Tuple[int, int]:
    if (
        type(value) is not list
        or len(value) != 2
        or any(type(coordinate) is not int for coordinate in value)
    ):
        raise ValueError("{} must be an exact two-integer JSON array".format(label))
    return (value[0], value[1])


def _parse_exact_action(value: Any, label: str) -> Tuple[Action, ActionRecordV1]:
    if type(value) is not dict or any(type(key) is not str for key in value):
        raise ValueError("{} must be an exact JSON object".format(label))
    raw_kind = value.get("kind")
    if type(raw_kind) is not str or raw_kind not in ACTION_VOCABULARY_V1:
        raise ValueError("{}.kind is outside telemetry-v1 vocabulary".format(label))
    expected = {"kind", "to"} if raw_kind == "PLACE" else {"kind", "from", "to"}
    if set(value) != expected:
        raise ValueError("{} fields do not match {}".format(label, raw_kind))
    destination = _require_exact_position(value["to"], label + ".to")
    canonical: Dict[str, Any] = {"kind": raw_kind, "to": list(destination)}
    if raw_kind != "PLACE":
        origin = _require_exact_position(value["from"], label + ".from")
        canonical["from"] = list(origin)
    try:
        action = action_from_dict(canonical)
    except (AssertionError, AttributeError, TypeError, ValueError) as error:
        raise ValueError("{} is not a valid action record".format(label)) from error
    return action, ActionRecordV1.from_action(action)


def _trace_iterator(actions: Any, max_plies: int) -> Iterator[Any]:
    if isinstance(actions, Mapping) or isinstance(actions, (str, bytes, bytearray)):
        raise ValueError("complete action trace must be an iterable of action objects")
    if type(actions) in (list, tuple) and len(actions) > max_plies:
        raise ValueError("complete action trace exceeds the definition horizon")
    try:
        return iter(actions)
    except TypeError as error:
        raise ValueError("complete action trace must be iterable") from error


def _piece_counts(state: GameState, actor: Player) -> Tuple[int, int, int]:
    own = sum(piece.owner is actor for piece in state.pieces)
    opponent = sum(piece.owner is actor.other for piece in state.pieces)
    return own, opponent, len(state.pieces)


def _piece_at(state: GameState, position: Tuple[int, int]) -> Any:
    return next((piece for piece in state.pieces if piece.position == position), None)


def _effect_mode(
    definition: GameDefinition, state: GameState, action: Action
) -> str:
    kind = action.kind
    if kind is ActionKind.PLACE:
        return "PLACE"
    if kind is ActionKind.CONVERT:
        return "CONVERT"
    target = _piece_at(state, action.to_position)
    if kind is ActionKind.MOVE:
        return "ORDINARY_STEP"
    if kind is ActionKind.MOVE_CAPTURE:
        return "CAPTURE" if target is not None else "ORDINARY_STEP"
    if kind is ActionKind.PUSH:
        return "PUSH" if target is not None else "ORDINARY_STEP"
    if kind is ActionKind.SWAP:
        return "SWAP" if target is not None else "ORDINARY_STEP"
    if kind is ActionKind.HOP:
        assert action.from_position is not None
        delta = (
            action.to_position[0] - action.from_position[0],
            action.to_position[1] - action.from_position[1],
        )
        vectors = definition.role(state.to_move).action.vectors
        if delta in vectors:
            return "ORDINARY_STEP"
        if delta in tuple((2 * row, 2 * column) for row, column in vectors):
            return "HOP"
    raise ValueError("legal action has no telemetry-v1 effect mode")


def _state_effect(
    definition: GameDefinition,
    before: GameState,
    action: Action,
    after: GameState,
    mode: str,
) -> StateEffectV1:
    actor = before.to_move
    own_before, opponent_before, occupied_before = _piece_counts(before, actor)
    own_after, opponent_after, occupied_after = _piece_counts(after, actor)
    own_placements = int(action.kind is ActionKind.PLACE)
    own_movements = int(action.kind not in (ActionKind.PLACE, ActionKind.CONVERT))
    opponent_movements = int(mode in ("PUSH", "SWAP"))
    conversions = int(mode == "CONVERT")
    removals = int(mode == "CAPTURE")
    opponent_dependency = mode in ("CAPTURE", "PUSH", "SWAP", "CONVERT")
    if mode == "HOP":
        assert action.from_position is not None
        midpoint = (
            (action.from_position[0] + action.to_position[0]) // 2,
            (action.from_position[1] + action.to_position[1]) // 2,
        )
        jumped = _piece_at(before, midpoint)
        opponent_dependency = jumped is not None and jumped.owner is actor.other
    realized_opponent_effect = bool(
        opponent_movements
        or conversions
        or removals
        or opponent_after != opponent_before
    )
    effect = StateEffectV1(
        own_placements=own_placements,
        own_movements=own_movements,
        opponent_movements=opponent_movements,
        conversions=conversions,
        removals=removals,
        own_piece_count_delta=own_after - own_before,
        opponent_piece_count_delta=opponent_after - opponent_before,
        occupied_cell_delta=occupied_after - occupied_before,
        opponent_dependency=opponent_dependency,
        realized_opponent_effect=realized_opponent_effect,
    )
    # These relations are part of the telemetry contract, not assumptions made
    # by downstream analysis.
    if conversions != int(
        effect.own_piece_count_delta == 1
        and effect.opponent_piece_count_delta == -1
        and effect.occupied_cell_delta == 0
    ) and conversions:
        raise ValueError("CONVERT transition violates telemetry-v1 state deltas")
    if removals and not (
        effect.own_piece_count_delta == 0
        and effect.opponent_piece_count_delta == -1
        and effect.occupied_cell_delta == -1
    ):
        raise ValueError("capture transition violates telemetry-v1 state deltas")
    return effect


def _outcome_class(state: GameState, actor: Player) -> str:
    if state.outcome is None:
        return "NONTERMINAL"
    if state.outcome.reason not in TERMINAL_REASON_VOCABULARY_V1:
        raise ValueError("engine produced a terminal reason outside telemetry-v1")
    if state.outcome.winner is actor:
        return "ACTOR_WIN"
    if state.outcome.winner is None:
        return "DRAW"
    if state.outcome.winner is actor.other:
        return "ACTOR_LOSS"
    raise ValueError("engine produced a terminal winner outside telemetry-v1")


def _position_key(state: GameState) -> Tuple[Any, ...]:
    return (
        state.to_move.value,
        tuple(
            (
                piece.owner.value,
                piece.piece,
                piece.position[0],
                piece.position[1],
            )
            for piece in state.pieces
        ),
    )


def _position_dict(state: GameState) -> Dict[str, Any]:
    return {
        "to_move": state.to_move.value,
        "pieces": [piece.to_dict() for piece in state.pieces],
    }


def _action_identity(action: Action) -> Tuple[Any, ...]:
    origin = action.from_position if action.from_position is not None else (-1, -1)
    return (
        action.kind.value,
        origin[0],
        origin[1],
        action.to_position[0],
        action.to_position[1],
    )


def _counterfactual_decision(
    definition: GameDefinition,
    state: GameState,
    chosen: Action,
    successors_used: int,
    next_actions_used: int,
) -> Tuple[DecisionTelemetryV1, GameState, int, int]:
    choices = legal_actions(definition, state)
    legal_count = len(choices)
    if legal_count < 1:
        raise ValueError("nonterminal replay state has no legal action")
    if legal_count > MAX_LEGAL_ACTIONS_PER_DECISION_V1:
        raise ValueError("legal action count exceeds telemetry-v1 structural bound")
    if chosen not in choices:
        raise ValueError("complete action trace contains an illegal action")
    if successors_used + legal_count > MAX_COUNTERFACTUAL_SUCCESSORS_V1:
        raise ValueError("telemetry-v1 counterfactual successor cap exceeded")

    kind_counts: Dict[str, int] = {}
    mode_counts: Dict[str, int] = {}
    outcome_counts: Dict[str, int] = {}
    successor_positions = set()
    effect_signatures = set()
    nonterminal_next_sets = []
    alternatives = []
    chosen_state: Optional[GameState] = None
    chosen_effect: Optional[StateEffectV1] = None
    chosen_mode: Optional[str] = None

    for candidate in choices:
        if candidate.kind.value not in ACTION_VOCABULARY_V1:
            raise ValueError("engine produced an action outside telemetry-v1")
        mode = _effect_mode(definition, state, candidate)
        if mode not in EFFECT_MODE_VOCABULARY_V1:
            raise ValueError("engine produced an effect mode outside telemetry-v1")
        successor = apply_action(definition, state, candidate)
        effect = _state_effect(definition, state, candidate, successor, mode)
        outcome_class = _outcome_class(successor, state.to_move)
        position_key = _position_key(successor)
        successor_positions.add(position_key)
        effect_signatures.add((mode, effect))
        kind_counts[candidate.kind.value] = kind_counts.get(candidate.kind.value, 0) + 1
        mode_counts[mode] = mode_counts.get(mode, 0) + 1
        outcome_counts[outcome_class] = outcome_counts.get(outcome_class, 0) + 1

        next_records: Optional[Tuple[ActionRecordV1, ...]] = None
        if not successor.terminal:
            next_actions = legal_actions(definition, successor)
            if len(next_actions) > MAX_LEGAL_ACTIONS_PER_DECISION_V1:
                raise ValueError(
                    "next legal action count exceeds telemetry-v1 structural bound"
                )
            if next_actions_used + len(next_actions) > MAX_NEXT_ACTION_OBSERVATIONS_V1:
                raise ValueError("telemetry-v1 next-action observation cap exceeded")
            next_actions_used += len(next_actions)
            next_records = tuple(ActionRecordV1.from_action(item) for item in next_actions)
            next_identity = frozenset(_action_identity(item) for item in next_actions)
            nonterminal_next_sets.append(next_identity)

        alternatives.append(
            {
                "action": ActionRecordV1.from_action(candidate).to_dict(),
                "effect_mode": mode,
                "effect": effect.to_dict(),
                "outcome_class": outcome_class,
                "outcome": (
                    successor.outcome.to_dict()
                    if successor.outcome is not None
                    else None
                ),
                "successor_position": _position_dict(successor),
                "next_legal_actions": (
                    [record.to_dict() for record in next_records]
                    if next_records is not None
                    else None
                ),
            }
        )
        if candidate == chosen:
            chosen_state = successor
            chosen_effect = effect
            chosen_mode = mode

    assert chosen_state is not None and chosen_effect is not None and chosen_mode is not None
    nonterminal_count = len(nonterminal_next_sets)
    comparable = nonterminal_count >= 2
    next_variant_count = (
        len(set(nonterminal_next_sets)) if comparable else None
    )
    next_sensitive = (
        next_variant_count is not None and next_variant_count > 1
        if comparable
        else None
    )
    outcome_variant_count = sum(count > 0 for count in outcome_counts.values())
    successor_variant_count = len(successor_positions)
    effect_variant_count = len(effect_signatures)
    counterfactual_payload = {
        "pre_state": state.to_dict(),
        "alternatives": alternatives,
    }
    decision = DecisionTelemetryV1(
        ply=state.ply,
        actor=state.to_move.value,
        pre_state_digest=_domain_digest(_STATE_DIGEST_DOMAIN, state.to_dict()),
        legal_count=legal_count,
        legal_action_kind_counts=_histogram(ACTION_VOCABULARY_V1, kind_counts),
        legal_effect_mode_counts=_histogram(EFFECT_MODE_VOCABULARY_V1, mode_counts),
        chosen_action=ActionRecordV1.from_action(chosen),
        chosen_effect_mode=chosen_mode,
        chosen_effect=chosen_effect,
        ordinary_step_available=any(
            mode_counts.get(mode, 0) for mode in ORDINARY_STEP_EFFECT_MODES_V1
        ),
        conditional_special_available=any(
            mode_counts.get(mode, 0)
            for mode in CONDITIONAL_SPECIAL_EFFECT_MODES_V1
        ),
        chosen_conditional_special=(
            chosen_mode in CONDITIONAL_SPECIAL_EFFECT_MODES_V1
        ),
        successor_position_variant_count=successor_variant_count,
        effect_signature_variant_count=effect_variant_count,
        immediate_reconvergence=successor_variant_count < legal_count,
        redundant_successor_count=legal_count - successor_variant_count,
        immediate_outcome_class_counts=_histogram(
            OUTCOME_CLASS_VOCABULARY_V1, outcome_counts
        ),
        immediate_outcome_sensitive=outcome_variant_count > 1,
        nonterminal_successor_count=nonterminal_count,
        next_legal_set_comparable=comparable,
        next_legal_set_variant_count=next_variant_count,
        next_legal_set_sensitive=next_sensitive,
        counterfactual_digest=_domain_digest(
            _COUNTERFACTUAL_DIGEST_DOMAIN, counterfactual_payload
        ),
    )
    return decision, chosen_state, successors_used + legal_count, next_actions_used


def _empty_role_accumulator() -> Dict[str, Any]:
    return {
        "decisions": [],
        "legal_action_kinds": {},
        "legal_effect_modes": {},
        "chosen_action_kinds": {},
        "chosen_effect_modes": {},
        "outcome_classes": {},
        "zero_observations": 0,
    }


def _add_histogram(target: Dict[str, int], source: Tuple[Tuple[str, int], ...]) -> None:
    for label, count in source:
        target[label] = target.get(label, 0) + count


def _build_role(
    player: Player, accumulator: Mapping[str, Any]
) -> RoleTelemetryV1:
    decisions = tuple(accumulator["decisions"])
    legal_counts = tuple(decision.legal_count for decision in decisions)
    zero = accumulator["zero_observations"]
    observed_legal_counts = legal_counts + ((0,) * zero)
    one = sum(count == 1 for count in legal_counts)
    two_plus = sum(count >= 2 for count in legal_counts)
    decision_count = len(decisions)
    forced_fraction = (
        ExactFractionV1(numerator=one, denominator=decision_count)
        if decision_count
        else None
    )
    effects = tuple(decision.chosen_effect for decision in decisions)
    return RoleTelemetryV1(
        player=player.value,
        action_count=decision_count,
        decision_count=decision_count,
        legal_observation_count=decision_count + zero,
        legal_action_count_total=sum(observed_legal_counts),
        legal_action_count_min=(
            min(observed_legal_counts) if observed_legal_counts else None
        ),
        legal_action_count_max=(
            max(observed_legal_counts) if observed_legal_counts else None
        ),
        legal_count_0_observations=zero,
        legal_count_1_observations=one,
        legal_count_2_plus_observations=two_plus,
        forced_fraction=forced_fraction,
        legal_action_kind_counts=_histogram(
            ACTION_VOCABULARY_V1, accumulator["legal_action_kinds"]
        ),
        legal_effect_mode_counts=_histogram(
            EFFECT_MODE_VOCABULARY_V1, accumulator["legal_effect_modes"]
        ),
        chosen_action_kind_counts=_histogram(
            ACTION_VOCABULARY_V1, accumulator["chosen_action_kinds"]
        ),
        chosen_effect_mode_counts=_histogram(
            EFFECT_MODE_VOCABULARY_V1, accumulator["chosen_effect_modes"]
        ),
        immediate_outcome_class_counts=_histogram(
            OUTCOME_CLASS_VOCABULARY_V1, accumulator["outcome_classes"]
        ),
        ordinary_step_available_decisions=sum(
            decision.ordinary_step_available for decision in decisions
        ),
        conditional_special_available_decisions=sum(
            decision.conditional_special_available for decision in decisions
        ),
        ordinary_step_chosen_actions=sum(
            decision.chosen_effect_mode in ORDINARY_STEP_EFFECT_MODES_V1
            for decision in decisions
        ),
        conditional_special_chosen_actions=sum(
            decision.chosen_conditional_special for decision in decisions
        ),
        own_placements=sum(effect.own_placements for effect in effects),
        own_movements=sum(effect.own_movements for effect in effects),
        opponent_movements=sum(effect.opponent_movements for effect in effects),
        conversions=sum(effect.conversions for effect in effects),
        removals=sum(effect.removals for effect in effects),
        own_piece_count_delta=sum(effect.own_piece_count_delta for effect in effects),
        opponent_piece_count_delta=sum(
            effect.opponent_piece_count_delta for effect in effects
        ),
        occupied_cell_delta=sum(effect.occupied_cell_delta for effect in effects),
        opponent_dependency_actions=sum(
            effect.opponent_dependency for effect in effects
        ),
        realized_opponent_effect_actions=sum(
            effect.realized_opponent_effect for effect in effects
        ),
        immediate_outcome_sensitive_decisions=sum(
            decision.immediate_outcome_sensitive for decision in decisions
        ),
        next_legal_set_comparable_decisions=sum(
            decision.next_legal_set_comparable for decision in decisions
        ),
        next_legal_set_sensitive_decisions=sum(
            decision.next_legal_set_sensitive is True for decision in decisions
        ),
        immediate_reconvergence_decisions=sum(
            decision.immediate_reconvergence for decision in decisions
        ),
        successor_position_variant_total=sum(
            decision.successor_position_variant_count for decision in decisions
        ),
        effect_signature_variant_total=sum(
            decision.effect_signature_variant_count for decision in decisions
        ),
        nonterminal_successor_total=sum(
            decision.nonterminal_successor_count for decision in decisions
        ),
    )


def _observe_repetition(
    state: GameState,
    first_seen: Dict[Tuple[Any, ...], int],
    last_seen: Dict[Tuple[Any, ...], int],
    repeated_keys: set,
    events: list,
) -> None:
    key = _position_key(state)
    if key not in first_seen:
        first_seen[key] = state.ply
        last_seen[key] = state.ply
        return
    first_ply = first_seen[key]
    previous_ply = last_seen[key]
    last_seen[key] = state.ply
    repeated_keys.add(key)
    events.append(
        RepetitionEventV1(
            ply=state.ply,
            first_seen_ply=first_ply,
            previous_seen_ply=previous_ply,
            period=state.ply - previous_ply,
            terminal=state.terminal,
            cycle_prefix=not state.terminal,
        )
    )


def _repetition_telemetry(
    state_count: int, repeated_keys: set, events: list
) -> RepetitionTelemetryV1:
    immutable_events = tuple(events)
    periods = tuple(event.period for event in immutable_events)
    cycle_prefix_count = sum(event.cycle_prefix for event in immutable_events)
    return RepetitionTelemetryV1(
        state_observation_count=state_count,
        repeat_event_count=len(immutable_events),
        repeated_state_count=len(repeated_keys),
        has_repetition=bool(immutable_events),
        first_repeat_ply=(immutable_events[0].ply if immutable_events else None),
        shortest_period=min(periods) if periods else None,
        cycle_prefix_count=cycle_prefix_count,
        has_cycle_prefix=cycle_prefix_count > 0,
        events=immutable_events,
    )


def _direct_effect_status(role_a: RoleTelemetryV1, role_b: RoleTelemetryV1) -> str:
    a = role_a.realized_opponent_effect_actions > 0
    b = role_b.realized_opponent_effect_actions > 0
    if a and b:
        return "BOTH_ROLES"
    if a:
        return "A_ONLY"
    if b:
        return "B_ONLY"
    return "NONE"


def _terminal_telemetry(state: GameState) -> TerminalTelemetryV1:
    if state.outcome is None:
        raise ValueError("complete action trace must end at a terminal state")
    if state.outcome.reason not in TERMINAL_REASON_VOCABULARY_V1:
        raise ValueError("terminal reason is outside telemetry-v1 vocabulary")
    winner = state.outcome.winner
    if winner is not None and type(winner) is not Player:
        raise ValueError("terminal winner is outside telemetry-v1 vocabulary")
    return TerminalTelemetryV1(
        ply=state.ply,
        winner=winner.value if winner is not None else None,
        reason=state.outcome.reason,
    )


def _root_digest(telemetry: ReplayTelemetryV1) -> str:
    payload = telemetry.to_dict()
    payload.pop("evidence_digest")
    return _domain_digest(_EVIDENCE_DIGEST_DOMAIN, payload)


def derive_replay_telemetry_v1(
    definition_value: Any, actions: Iterable[Mapping[str, Any]]
) -> ReplayTelemetryV1:
    """Derive telemetry-v1 from one authoritative complete schema-v4 replay.

    General iterables are consumed only through the terminal action plus one
    bounded pull used to reject trailing data.  A nonterminal EOF is always an
    incomplete-trace error; telemetry-v1 has no prefix mode.
    """

    source_seal, definition = _definition_snapshot(definition_value)
    iterator = _trace_iterator(actions, definition.max_plies)
    state = initial_state(definition)
    if state.outcome is not None:
        _outcome_class(state, state.to_move)

    normalized_actions = []
    decisions = []
    accumulators = {
        Player.A: _empty_role_accumulator(),
        Player.B: _empty_role_accumulator(),
    }
    successors_used = 0
    next_actions_used = 0
    first_seen: Dict[Tuple[Any, ...], int] = {}
    last_seen: Dict[Tuple[Any, ...], int] = {}
    repeated_keys: set = set()
    repetition_events: list = []
    _observe_repetition(
        state, first_seen, last_seen, repeated_keys, repetition_events
    )

    while True:
        if state.terminal:
            try:
                next(iterator)
            except StopIteration:
                break
            raise ValueError("complete action trace contains an action after terminal")

        try:
            raw_action = next(iterator)
        except StopIteration as error:
            raise ValueError("complete action trace ended before terminal") from error
        action_index = len(normalized_actions)
        action, record = _parse_exact_action(
            raw_action, "actions[{}]".format(action_index)
        )
        decision, successor, successors_used, next_actions_used = (
            _counterfactual_decision(
                definition,
                state,
                action,
                successors_used,
                next_actions_used,
            )
        )
        accumulator = accumulators[state.to_move]
        accumulator["decisions"].append(decision)
        _add_histogram(
            accumulator["legal_action_kinds"], decision.legal_action_kind_counts
        )
        _add_histogram(
            accumulator["legal_effect_modes"], decision.legal_effect_mode_counts
        )
        chosen_kind = decision.chosen_action.kind
        accumulator["chosen_action_kinds"][chosen_kind] = (
            accumulator["chosen_action_kinds"].get(chosen_kind, 0) + 1
        )
        chosen_mode = decision.chosen_effect_mode
        accumulator["chosen_effect_modes"][chosen_mode] = (
            accumulator["chosen_effect_modes"].get(chosen_mode, 0) + 1
        )
        _add_histogram(
            accumulator["outcome_classes"],
            decision.immediate_outcome_class_counts,
        )
        normalized_actions.append(record)
        decisions.append(decision)
        state = successor
        _observe_repetition(
            state, first_seen, last_seen, repeated_keys, repetition_events
        )

    terminal = _terminal_telemetry(state)
    if terminal.reason == "NO_LEGAL_ACTION":
        accumulators[state.to_move]["zero_observations"] += 1

    role_a = _build_role(Player.A, accumulators[Player.A])
    role_b = _build_role(Player.B, accumulators[Player.B])
    current_forced_run = 0
    longest_forced_run = 0
    for decision in decisions:
        if decision.legal_count == 1:
            current_forced_run += 1
            longest_forced_run = max(longest_forced_run, current_forced_run)
        else:
            current_forced_run = 0

    telemetry = ReplayTelemetryV1(
        telemetry_version=REPLAY_TELEMETRY_VERSION,
        dsl_schema_version=definition.schema_version,
        definition_hash=hashlib.sha256(source_seal.encode("utf-8")).hexdigest(),
        action_vocabulary=ACTION_VOCABULARY_V1,
        goal_vocabulary=GOAL_VOCABULARY_V1,
        terminal_reason_vocabulary=TERMINAL_REASON_VOCABULARY_V1,
        effect_mode_vocabulary=EFFECT_MODE_VOCABULARY_V1,
        outcome_class_vocabulary=OUTCOME_CLASS_VOCABULARY_V1,
        direct_effect_status_vocabulary=DIRECT_EFFECT_STATUS_VOCABULARY_V1,
        actions=tuple(normalized_actions),
        decisions=tuple(decisions),
        role_a=role_a,
        role_b=role_b,
        longest_forced_run=longest_forced_run,
        direct_effect_status=_direct_effect_status(role_a, role_b),
        repetition=_repetition_telemetry(
            len(normalized_actions) + 1, repeated_keys, repetition_events
        ),
        terminal=terminal,
        work=WorkTelemetryV1(
            replayed_actions=len(normalized_actions),
            decision_count=len(decisions),
            state_observation_count=len(normalized_actions) + 1,
            successor_evaluations=successors_used,
            next_action_observations=next_actions_used,
        ),
        evidence_digest="",
    )
    telemetry = replace(telemetry, evidence_digest=_root_digest(telemetry))

    # The detached snapshot is the only definition used above.  Resealing the
    # caller-owned source here detects semantically visible mid-derivation
    # mutation without ever letting it influence a partial result.
    if _canonical_definition_value(definition_value) != source_seal:
        raise ValueError("telemetry definition mutated during derivation")
    return telemetry


def _require_exact_json_tree(value: Any, label: str) -> None:
    remaining = [MAX_STORED_JSON_NODES_V1]
    active_containers = set()

    def visit(item: Any, path: str, depth: int) -> None:
        remaining[0] -= 1
        if remaining[0] < 0:
            raise ValueError("stored telemetry exceeds the telemetry-v1 JSON bound")
        if depth > MAX_STORED_JSON_DEPTH_V1:
            raise ValueError("stored telemetry exceeds the telemetry-v1 depth bound")
        if item is None or type(item) in (str, int, bool):
            return
        if type(item) not in (list, dict):
            raise ValueError(
                "{} must contain only exact finite JSON values".format(path)
            )
        identity = id(item)
        if identity in active_containers:
            raise ValueError("stored telemetry cannot contain a cycle")
        active_containers.add(identity)
        try:
            if type(item) is list:
                for index, child in enumerate(item):
                    visit(child, "{}[{}]".format(path, index), depth + 1)
                return
            if not all(type(key) is str for key in item):
                raise ValueError("{} keys must be exact strings".format(path))
            for key, child in item.items():
                visit(child, "{}.{}".format(path, key), depth + 1)
        finally:
            active_containers.remove(identity)

    visit(value, label, 0)


_ROOT_KEYS_V1 = frozenset(
    (
        "telemetry_version",
        "dsl_schema_version",
        "definition_hash",
        "action_vocabulary",
        "goal_vocabulary",
        "terminal_reason_vocabulary",
        "effect_mode_vocabulary",
        "outcome_class_vocabulary",
        "direct_effect_status_vocabulary",
        "actions",
        "decisions",
        "roles",
        "longest_forced_run",
        "direct_effect_status",
        "repetition",
        "terminal",
        "work",
        "evidence_digest",
    )
)


def validate_replay_telemetry_v1(
    definition_value: Any, stored: Any
) -> ReplayTelemetryV1:
    """Rebuild and exactly validate a stored telemetry-v1 JSON record."""

    if type(stored) is not dict:
        raise ValueError("stored replay telemetry must be an exact object")
    supplied = stored
    if set(supplied) != _ROOT_KEYS_V1:
        raise ValueError("stored replay telemetry has noncanonical root fields")
    if type(supplied.get("telemetry_version")) is not int or supplied[
        "telemetry_version"
    ] != REPLAY_TELEMETRY_VERSION:
        raise ValueError("stored replay telemetry has the wrong version")
    raw_actions = supplied.get("actions")
    if type(raw_actions) is not list:
        raise ValueError("stored replay telemetry actions must be an exact array")
    if len(raw_actions) > MAX_REPLAY_ACTIONS_V1:
        raise ValueError("stored replay telemetry exceeds the telemetry-v1 horizon")
    _require_exact_json_tree(supplied, "stored telemetry")
    entry_seal = _canonical_bytes(supplied)

    # Seal untrusted stored evidence before invoking any caller-owned definition
    # Mapping methods.  A hostile Mapping must not be able to repair or retime a
    # tampered record before its entry bytes are fixed.
    source_seal, definition = _definition_snapshot(definition_value)
    if _canonical_bytes(stored) != entry_seal:
        raise ValueError("stored replay telemetry mutated during validation")
    if len(raw_actions) > definition.max_plies:
        raise ValueError("stored replay telemetry exceeds the definition horizon")
    for index, raw_action in enumerate(raw_actions):
        _parse_exact_action(raw_action, "stored.actions[{}]".format(index))

    rebuilt = derive_replay_telemetry_v1(definition, raw_actions)
    expected = rebuilt.to_dict()
    if _canonical_bytes(expected) != entry_seal:
        raise ValueError("stored replay telemetry does not exactly reconstruct")
    if _canonical_definition_value(definition_value) != source_seal:
        raise ValueError("telemetry definition mutated during validation")
    if _canonical_bytes(stored) != entry_seal:
        raise ValueError("stored replay telemetry mutated during validation")
    return rebuilt
