"""Pure exact and depth-5 evaluation for the fixed Plan 0010 experiment.

This module owns no filesystem, Git, reservation, or one-shot behavior.  It
accepts an already frozen manifest (or its detached pair array), executes or
validates fixed source-all-then-treatment-all schedules, and rebuilds every
derived result from principal variations or complete sampled action traces.

Runner labels are deliberately trace-local.  ``ORIGINAL`` is witnessed by the
one-runner source definition and ``ADDED`` by the frozen same-frame transform;
neither label enters a game state, solver key, definition identity, or legal
action calculation.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from .agents import MinimaxAgent, SearchBudgetExceeded
from .audit import sampled_direction
from .batch import PlayGates
from .dsl import ActionKind, GameDefinition, Player, definition_hash, parse_definition
from .engine import action_from_dict, apply_action, initial_state, legal_actions
from .play import GameRecord
from .solver import SolveBudgetExceeded, solve_game
from .symmetry import d4_canonical_hash
from .two_runner import (
    TWO_RUNNER_EXACT_MAX_STATES,
    TWO_RUNNER_PAIR_COUNT,
    TWO_RUNNER_SOURCE_STATE_BOUND,
    TWO_RUNNER_TREATMENT_STATE_BOUND,
    derive_two_runner_treatment,
    two_runner_added_position,
    two_runner_natural_terminal_ply_bound,
    two_runner_stratum,
    validate_two_runner_pair,
    validate_two_runner_searched_states,
)


TWO_RUNNER_EXACT_PROTOCOL_ID = "two-runner-v1-paired-exact"
TWO_RUNNER_DEPTH5_PROTOCOL_ID = "two-runner-v1-fixed-depth5"
TWO_RUNNER_DEPTH = 5
TWO_RUNNER_MAX_NODES = 5_000_000
TWO_RUNNER_SEEDS = tuple(range(30))

_SOURCE_EXACT_DOMAIN = b"two-runner-v1-source-exact-slots-v1\0"
_TREATMENT_EXACT_DOMAIN = b"two-runner-v1-treatment-exact-slots-v1\0"
_SOURCE_DEPTH5_DOMAIN = b"two-runner-v1-source-depth5-slots-v1\0"
_TREATMENT_DEPTH5_DOMAIN = b"two-runner-v1-treatment-depth5-slots-v1\0"
_CHANGE_INSPECTION_DOMAIN = b"two-runner-v1-inspection-change-v1\0"
_CONTROL_INSPECTION_DOMAIN = b"two-runner-v1-inspection-control-v1\0"
_PAIR_FINGERPRINT_DOMAIN = b"two-runner-v1-pair-v1"
_LINEAGE_ORDER = ("ORIGINAL", "ADDED")
_VECTOR_BANDS = ("v1_3", "v4", "v5", "v6_7")
_STRUCTURAL_CELLS = (
    "fA-aligned",
    "fA-orthogonal",
    "fB-aligned",
    "fB-orthogonal",
)
_STRATUM_IDS = tuple(
    "{}-{}".format(cell, band)
    for cell in _STRUCTURAL_CELLS
    for band in _VECTOR_BANDS
)
_VALUE_BY_RESULT = {"A_WIN": 1, "DRAW": 0, "B_WIN": -1}
_PROFILE_PREFIX = "minimax-v1-depth"
_SHAPE_FAILURES = frozenset(("EXCESSIVE_DRAWS", "TOO_SHORT", "TOO_LONG"))
_DOMINANCE_FAILURES = frozenset(("A_DOMINANT", "B_DOMINANT"))
_EXACT_INSPECTION_REASON_ORDER = (
    "EXACT_CENSOR",
    "CONTAINMENT_RESPONSE",
    "EXACT_ENGAGEMENT_RESPONSE",
    "OUTCOME_CHANGE_SAMPLE",
    "OUTCOME_UNCHANGED_CONTROL",
    "STRATUM_FLOOR",
)
_FINAL_INSPECTION_REASON_ORDER = (
    "EXACT_CENSOR",
    "NODE_CENSOR",
    "DIRECTION_MISMATCH",
    "CONTAINMENT_RESPONSE",
    "EXACT_ENGAGEMENT_RESPONSE",
    "STRONG_FRONTIER",
    "CANDIDATE_SHAPED",
    "OUTCOME_CHANGE_SAMPLE",
    "OUTCOME_UNCHANGED_CONTROL",
    "STRATUM_FLOOR",
)


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
        raise ValueError("evidence must be finite canonical JSON") from error


def _copy(value: Any, label: str) -> Any:
    try:
        return json.loads(_canonical_bytes(value))
    except (TypeError, ValueError) as error:
        raise ValueError("{} must be finite canonical JSON".format(label)) from error


def _exact_keys(value: Any, expected: Iterable[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != set(expected):
        raise ValueError("{} fields mismatch".format(label))
    return value


def _strict_int(value: Any, label: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError("{} must be an integer >= {}".format(label, minimum))
    return value


def _elapsed_seconds(value: Any, label: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError("{} must be a finite nonnegative number".format(label))
    return float(value)


def _nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("{} must be a nonempty string".format(label))
    return value


def _sha256(value: Any, label: str) -> str:
    value = _nonempty_string(value, label)
    if (
        len(value) != 64
        or value != value.lower()
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError("{} must be a lowercase SHA-256 digest".format(label))
    return value


def _coerce_definition(value: Any, label: str) -> GameDefinition:
    if isinstance(value, GameDefinition):
        return value
    if isinstance(value, Mapping):
        return parse_definition(value)
    raise ValueError("{} must be a definition or definition object".format(label))


def _stratum_id(stratum: Mapping[str, Any]) -> str:
    value = _exact_keys(
        stratum,
        ("first_player", "goal_axis_relation", "vector_band"),
        "two-runner stratum",
    )
    if value["first_player"] not in ("A", "B"):
        raise ValueError("two-runner first-player stratum mismatch")
    if value["goal_axis_relation"] not in ("ALIGNED", "ORTHOGONAL"):
        raise ValueError("two-runner goal-axis stratum mismatch")
    if value["vector_band"] not in _VECTOR_BANDS:
        raise ValueError("two-runner vector-band stratum mismatch")
    return "f{}-{}-{}".format(
        value["first_player"],
        value["goal_axis_relation"].lower(),
        value["vector_band"],
    )


def _structural_cell(stratum: Mapping[str, Any]) -> str:
    _stratum_id(stratum)
    return "f{}-{}".format(
        stratum["first_player"], stratum["goal_axis_relation"].lower()
    )


def _normalize_pair(raw: Any, index: int) -> Dict[str, Any]:
    pair = _exact_keys(
        raw,
        (
            "pair_id",
            "source_case_id",
            "stratum_id",
            "stratum",
            "selection_rank",
            "selection_score",
            "source_definition_hash",
            "source_d4_canonical_hash",
            "source_definition",
            "treatment_definition_hash",
            "treatment_d4_canonical_hash",
            "treatment_definition",
            "added_runner_position",
            "piece_multiplicity_delta",
            "pair_fingerprint",
        ),
        "two-runner manifest pair",
    )
    source = parse_definition(pair["source_definition"])
    treatment = parse_definition(pair["treatment_definition"])
    validate_two_runner_pair(source, treatment)
    source_hash = definition_hash(source)
    treatment_hash = definition_hash(treatment)
    source_d4 = d4_canonical_hash(source)
    treatment_d4 = d4_canonical_hash(treatment)
    supplied_hashes = (
        (pair["source_definition_hash"], source_hash, "source definition hash"),
        (
            pair["treatment_definition_hash"],
            treatment_hash,
            "treatment definition hash",
        ),
        (pair["source_d4_canonical_hash"], source_d4, "source D4 hash"),
        (
            pair["treatment_d4_canonical_hash"],
            treatment_d4,
            "treatment D4 hash",
        ),
    )
    for supplied, expected, label in supplied_hashes:
        if _sha256(supplied, label) != expected:
            raise ValueError("{} does not match its definition".format(label))

    expected_stratum = two_runner_stratum(source)
    if _canonical_bytes(pair["stratum"]) != _canonical_bytes(expected_stratum):
        raise ValueError("two-runner pair stratum does not match its source")
    expected_stratum_id = _stratum_id(expected_stratum)
    if pair["stratum_id"] != expected_stratum_id:
        raise ValueError("two-runner pair stratum_id mismatch")
    rank = _strict_int(pair["selection_rank"], "selection_rank")
    score = _sha256(pair["selection_score"], "selection_score")
    added_position = pair["added_runner_position"]
    if (
        not isinstance(added_position, (list, tuple))
        or len(added_position) != 2
        or any(type(coordinate) is not int for coordinate in added_position)
        or tuple(added_position) != two_runner_added_position(source)
    ):
        raise ValueError("two-runner added-runner position mismatch")
    if type(pair["piece_multiplicity_delta"]) is not int or pair[
        "piece_multiplicity_delta"
    ] != 1:
        raise ValueError("two-runner piece multiplicity delta must be integer one")
    fingerprint = _sha256(pair["pair_fingerprint"], "pair_fingerprint")
    fingerprint_payload = dict(pair)
    fingerprint_payload.pop("pair_fingerprint")
    expected_fingerprint = hashlib.sha256(
        _PAIR_FINGERPRINT_DOMAIN + b"\0" + _canonical_bytes(fingerprint_payload)
    ).hexdigest()
    if fingerprint != expected_fingerprint:
        raise ValueError("two-runner pair fingerprint does not reconstruct")

    return {
        "pair_index": index,
        "pair_id": _nonempty_string(pair["pair_id"], "pair_id"),
        "source_case_id": _nonempty_string(
            pair["source_case_id"], "source_case_id"
        ),
        "stratum_id": expected_stratum_id,
        "stratum": _copy(expected_stratum, "two-runner stratum"),
        "structural_cell": _structural_cell(expected_stratum),
        "vector_band": expected_stratum["vector_band"],
        "selection_rank": rank,
        "selection_score": score,
        "source_definition_hash": source_hash,
        "source_d4_canonical_hash": source_d4,
        "source_definition": source.to_dict(),
        "treatment_definition_hash": treatment_hash,
        "treatment_d4_canonical_hash": treatment_d4,
        "treatment_definition": treatment.to_dict(),
        "added_runner_position": list(two_runner_added_position(source)),
        "piece_multiplicity_delta": 1,
        "pair_fingerprint": fingerprint,
    }


def _manifest_pairs(
    manifest_or_pairs: Any,
    *,
    manifest_validator: Optional[Callable[[Any], Any]],
    expected_pair_count: int,
) -> Tuple[Tuple[Dict[str, Any], ...], str, Optional[str]]:
    _strict_int(expected_pair_count, "expected_pair_count", minimum=1)
    original = manifest_or_pairs
    original_snapshot = _copy(original, "two-runner manifest")
    original_bytes = _canonical_bytes(original_snapshot)
    validated = manifest_validator(original) if manifest_validator is not None else None
    if _canonical_bytes(original) != original_bytes:
        raise ValueError("manifest validator mutated the frozen manifest input")
    original_pairs = (
        original_snapshot.get("pairs")
        if isinstance(original_snapshot, Mapping)
        else original_snapshot
    )
    validated_pairs = (
        validated.get("pairs") if isinstance(validated, Mapping) else validated
    )
    if (
        manifest_validator is not None
        and validated is not None
        and isinstance(original_pairs, (list, tuple))
        and isinstance(validated_pairs, (list, tuple))
        and _canonical_bytes(original_pairs) != _canonical_bytes(validated_pairs)
    ):
        raise ValueError("manifest validator replaced the frozen pairs array")
    candidate = original_snapshot if validated is None else validated
    raw_pairs = candidate.get("pairs") if isinstance(candidate, Mapping) else candidate
    if not isinstance(raw_pairs, (list, tuple)):
        raw_pairs = (
            original_pairs if isinstance(original_snapshot, Mapping) else None
        )
    if not isinstance(raw_pairs, (list, tuple)):
        raise ValueError("two-runner manifest must expose a pairs array")
    if len(raw_pairs) != expected_pair_count:
        raise ValueError("two-runner pair count must be {}".format(expected_pair_count))
    pairs = tuple(_normalize_pair(pair, index) for index, pair in enumerate(raw_pairs))

    unique_fields = (
        "pair_id",
        "source_case_id",
        "source_definition_hash",
        "source_d4_canonical_hash",
        "treatment_definition_hash",
        "treatment_d4_canonical_hash",
    )
    for field in unique_fields:
        values = [pair[field] for pair in pairs]
        if len(values) != len(set(values)):
            raise ValueError("two-runner {} values must be unique".format(field))
    if set(pair["source_definition_hash"] for pair in pairs).intersection(
        pair["treatment_definition_hash"] for pair in pairs
    ):
        raise ValueError("two-runner source and treatment definitions must be disjoint")
    if set(pair["source_d4_canonical_hash"] for pair in pairs).intersection(
        pair["treatment_d4_canonical_hash"] for pair in pairs
    ):
        raise ValueError("two-runner source and treatment D4 identities must be disjoint")

    manifest_id = (
        original_snapshot.get("manifest_id")
        if isinstance(original_snapshot, Mapping)
        else None
    )
    if manifest_id is not None:
        manifest_id = _nonempty_string(manifest_id, "manifest_id")
    digest_source = original_snapshot
    digest = hashlib.sha256(_canonical_bytes(digest_source)).hexdigest()
    return pairs, digest, manifest_id


def _schedule_from_pairs(pairs: Sequence[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    schedule = []
    for side in ("SOURCE", "TREATMENT"):
        prefix = side.lower()
        for pair in pairs:
            schedule.append(
                {
                    "schedule_index": len(schedule),
                    "pair_index": pair["pair_index"],
                    "side": side,
                    "pair_id": pair["pair_id"],
                    "definition_hash": pair["{}_definition_hash".format(prefix)],
                }
            )
    return schedule


def two_runner_schedule(
    manifest_or_pairs: Any,
    *,
    manifest_validator: Optional[Callable[[Any], Any]] = None,
    expected_pair_count: int = TWO_RUNNER_PAIR_COUNT,
) -> list[Dict[str, Any]]:
    """Return the immutable all-source-then-all-treatment exact schedule."""

    pairs, _, _ = _manifest_pairs(
        manifest_or_pairs,
        manifest_validator=manifest_validator,
        expected_pair_count=expected_pair_count,
    )
    return _schedule_from_pairs(pairs)


def derive_two_runner_lineage_trace(
    source_definition_value: Any,
    played_definition_value: Any,
    actions: Sequence[Any],
    *,
    require_terminal: bool = True,
) -> Dict[str, Any]:
    """Replay one trace and derive source-witnessed runner lineage facts.

    ``ORIGINAL`` is the source's sole starting runner.  For a treatment,
    ``ADDED`` is the other frozen opposite-edge corner.  The engine continues to
    see two identical ordinary pieces; this mapping is updated only after a legal
    B move has been identified from its pre-action origin.
    """

    if type(require_terminal) is not bool:
        raise ValueError("require_terminal must be a boolean")
    source = _coerce_definition(source_definition_value, "source definition")
    played = _coerce_definition(played_definition_value, "played definition")
    expected_treatment = derive_two_runner_treatment(source)
    if _canonical_bytes(played.to_dict()) == _canonical_bytes(source.to_dict()):
        side = "SOURCE"
        added_start = None
    else:
        validate_two_runner_pair(source, played)
        if _canonical_bytes(played.to_dict()) != _canonical_bytes(
            expected_treatment.to_dict()
        ):
            raise ValueError("played treatment differs from the source-witnessed edit")
        side = "TREATMENT"
        added_start = two_runner_added_position(source)
    if not isinstance(actions, (list, tuple)):
        raise ValueError("two-runner trace actions must be an array")

    original_start = source.initial_pieces[0].position
    lineage_at = {original_start: "ORIGINAL"}
    if added_start is not None:
        lineage_at[added_start] = "ADDED"
    state = initial_state(played)
    runner_piece = played.role(Player.B).action.piece

    def validate_lineage_overlay(current_state: Any) -> None:
        engine_positions = [
            piece.position
            for piece in current_state.pieces
            if piece.owner is Player.B and piece.piece == runner_piece
        ]
        if (
            len(engine_positions) != len(lineage_at)
            or set(engine_positions) != set(lineage_at)
        ):
            raise ValueError(
                "source-witnessed lineage positions differ from engine B runners"
            )

    validate_lineage_overlay(state)
    normalized_actions = []
    decision_events = []
    move_counts = Counter({"ORIGINAL": 0, "ADDED": 0})

    for offset, raw_action in enumerate(actions):
        if not isinstance(raw_action, Mapping):
            raise ValueError("two-runner trace actions must be objects")
        action = action_from_dict(raw_action)
        choices = legal_actions(played, state)
        if action not in choices:
            raise ValueError("two-runner trace contains an illegal action")
        actor = state.to_move
        moved_lineage = None
        if actor is Player.B:
            if action.kind is not ActionKind.MOVE or action.from_position is None:
                raise ValueError("two-runner B trace action must be an ordinary move")
            origin_action_counts = Counter({lineage: 0 for lineage in _LINEAGE_ORDER})
            for choice in choices:
                if choice.kind is not ActionKind.MOVE or choice.from_position is None:
                    raise ValueError("two-runner B legal action is not an ordinary move")
                lineage = lineage_at.get(choice.from_position)
                if lineage is None:
                    raise ValueError("B legal action lacks a source-witnessed lineage")
                origin_action_counts[lineage] += 1
            ordered_origins = [
                lineage
                for lineage in _LINEAGE_ORDER
                if origin_action_counts[lineage] > 0
            ]
            both_available = all(
                origin_action_counts[lineage] > 0 for lineage in _LINEAGE_ORDER
            )
            moved_lineage = lineage_at.get(action.from_position)
            if moved_lineage is None:
                raise ValueError("B move origin lacks a source-witnessed lineage")
            decision_events.append(
                {
                    "ply": offset + 1,
                    "legal_action_count": len(choices),
                    "legal_origin_lineages": ordered_origins,
                    "legal_action_counts": {
                        lineage: origin_action_counts[lineage]
                        for lineage in _LINEAGE_ORDER
                    },
                    "both_lineages_available": both_available,
                    "selected_lineage": moved_lineage,
                    "selected_action": action.to_dict(),
                }
            )

        next_state = apply_action(played, state, action)
        if moved_lineage is not None:
            if action.from_position is None:
                raise ValueError("B lineage move unexpectedly lacks an origin")
            if lineage_at.pop(action.from_position) != moved_lineage:
                raise ValueError("runner lineage changed before its legal move")
            if action.to_position in lineage_at:
                raise ValueError("ordinary MOVE entered another runner's cell")
            lineage_at[action.to_position] = moved_lineage
            move_counts[moved_lineage] += 1
        validate_lineage_overlay(next_state)
        state = next_state
        normalized_actions.append(action.to_dict())

    if state.outcome is not None and state.outcome.reason == "PLY_LIMIT":
        raise ValueError("two-runner PLY_LIMIT contradicts natural termination")
    natural_bound = two_runner_natural_terminal_ply_bound(played)
    if state.ply > natural_bound:
        raise ValueError("two-runner trace exceeds its natural terminal ply bound")
    if require_terminal and not state.terminal:
        raise ValueError("two-runner trace must end at a terminal state")

    both_decisions = [
        event["ply"] for event in decision_events if event["both_lineages_available"]
    ]
    original_moved = move_counts["ORIGINAL"] > 0
    added_moved = move_counts["ADDED"] > 0
    terminal_outcome = state.outcome.to_dict() if state.outcome is not None else None
    final_by_lineage = {
        lineage: next(
            (
                list(position)
                for position, observed in lineage_at.items()
                if observed == lineage
            ),
            None,
        )
        for lineage in _LINEAGE_ORDER
    }
    return {
        "version": "two-runner-lineage-v1",
        "side": side,
        "actions": normalized_actions,
        "terminal": {
            "is_terminal": state.terminal,
            "outcome": terminal_outcome,
            "terminal_ply": state.ply if state.terminal else None,
            "replayed_ply": state.ply,
            "natural_terminal_ply_bound": natural_bound,
        },
        "start_positions": {
            "ORIGINAL": list(original_start),
            "ADDED": list(added_start) if added_start is not None else None,
        },
        "final_positions": final_by_lineage,
        "b_decisions": decision_events,
        "summary": {
            "original_move_count": move_counts["ORIGINAL"],
            "added_move_count": move_counts["ADDED"],
            "original_moved": original_moved,
            "added_moved": added_moved,
            "both_lineages_moved": bool(
                added_start is not None and original_moved and added_moved
            ),
            "both_lineage_decision_count": len(both_decisions),
            "both_lineage_decision_plies": both_decisions,
            "two_runner_engaged": bool(
                added_start is not None and added_moved and both_decisions
            ),
        },
    }


def validate_two_runner_lineage_trace(
    source_definition_value: Any,
    played_definition_value: Any,
    trace: Any,
    *,
    require_terminal: bool = True,
) -> Dict[str, Any]:
    """Rebuild a stored lineage trace from only definitions and its actions."""

    if type(require_terminal) is not bool:
        raise ValueError("require_terminal must be a boolean")
    value = _exact_keys(
        trace,
        (
            "version",
            "side",
            "actions",
            "terminal",
            "start_positions",
            "final_positions",
            "b_decisions",
            "summary",
        ),
        "two-runner lineage trace",
    )
    rebuilt = derive_two_runner_lineage_trace(
        source_definition_value,
        played_definition_value,
        value["actions"],
        require_terminal=require_terminal,
    )
    if _canonical_bytes(value) != _canonical_bytes(rebuilt):
        raise ValueError("two-runner lineage trace does not reconstruct")
    return _copy(value, "two-runner lineage trace")


def derive_two_runner_trace(
    source_definition_value: Any,
    played_definition_value: Any,
    actions: Sequence[Any],
    *,
    require_terminal: bool = True,
) -> Dict[str, Any]:
    """Compatibility spelling for :func:`derive_two_runner_lineage_trace`."""

    return derive_two_runner_lineage_trace(
        source_definition_value,
        played_definition_value,
        actions,
        require_terminal=require_terminal,
    )


def _lineage_evidence(trace: Mapping[str, Any]) -> Dict[str, Any]:
    _exact_keys(
        trace,
        (
            "version",
            "side",
            "actions",
            "terminal",
            "start_positions",
            "final_positions",
            "b_decisions",
            "summary",
        ),
        "two-runner lineage evidence",
    )
    return _copy(trace, "two-runner lineage evidence")


def _exact_payload_from_solve(solved: Any) -> Dict[str, Any]:
    result = solved.to_dict() if hasattr(solved, "to_dict") else solved
    if not isinstance(result, Mapping):
        raise ValueError("exact solver must return SolveResult-compatible evidence")
    return {
        "status": "COMPLETED",
        "result": _copy(result, "exact result"),
        "budget_observation": None,
    }


def _normalize_exact(
    source: GameDefinition,
    definition: GameDefinition,
    value: Any,
    *,
    max_states: int,
    side: str,
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    exact = _exact_keys(
        value,
        ("status", "result", "budget_observation"),
        "two-runner exact evidence",
    )
    status = exact["status"]
    if status == "CENSORED_STATE_BUDGET":
        budget = _exact_keys(
            exact["budget_observation"],
            ("searched_states", "max_states"),
            "two-runner exact censor observation",
        )
        searched = _strict_int(
            budget["searched_states"], "censored searched_states", minimum=1
        )
        maximum = _strict_int(budget["max_states"], "censored max_states", minimum=1)
        if exact["result"] is not None or searched != max_states or maximum != max_states:
            raise ValueError("two-runner exact censor evidence is malformed")
        try:
            validate_two_runner_searched_states(searched, definition)
        except ValueError as error:
            raise ValueError(
                "censored searched_states must remain within the side-specific proved bound"
            ) from error
        structural_bound = {
            "SOURCE": TWO_RUNNER_SOURCE_STATE_BOUND,
            "TREATMENT": TWO_RUNNER_TREATMENT_STATE_BOUND,
        }.get(side)
        if structural_bound is None or searched >= structural_bound:
            raise ValueError(
                "exact censor would require a state beyond the side-specific proved bound"
            )
        return _copy(exact, "two-runner exact censor"), None
    if status != "COMPLETED" or exact["budget_observation"] is not None:
        raise ValueError("two-runner exact evidence has an inconsistent status")

    result = _exact_keys(
        exact["result"],
        (
            "value_for_a",
            "forced_result",
            "principal_variation",
            "principal_variation_plies",
            "terminal_reason",
            "searched_states",
            "cache_hits",
        ),
        "two-runner exact result",
    )
    forced = result["forced_result"]
    if (
        forced not in _VALUE_BY_RESULT
        or type(result["value_for_a"]) is not int
        or result["value_for_a"] != _VALUE_BY_RESULT[forced]
    ):
        raise ValueError("two-runner exact forced-result/value encoding mismatch")
    terminal_reason = _nonempty_string(result["terminal_reason"], "terminal_reason")
    # This check intentionally precedes PV replay: PLY_LIMIT is a structural
    # contradiction for both source and treatment, never horizon evidence.
    if terminal_reason == "PLY_LIMIT":
        raise ValueError("two-runner PLY_LIMIT contradicts natural termination")
    try:
        validate_two_runner_searched_states(result["searched_states"], definition)
    except ValueError as error:
        raise ValueError(
            "searched_states must remain within the side-specific proved bound"
        ) from error
    if result["searched_states"] > max_states:
        raise ValueError("completed exact result exceeds its execution cap")
    _strict_int(result["cache_hits"], "exact cache_hits")
    pv = result["principal_variation"]
    pv_plies = _strict_int(
        result["principal_variation_plies"], "principal_variation_plies"
    )
    if not isinstance(pv, list) or pv_plies != len(pv):
        raise ValueError("two-runner exact principal variation length mismatch")
    if pv_plies > two_runner_natural_terminal_ply_bound(definition):
        raise ValueError("two-runner exact PV exceeds its natural terminal ply bound")
    trace = derive_two_runner_lineage_trace(source, definition, pv)
    expected_winner = {"A_WIN": "A", "B_WIN": "B", "DRAW": None}[forced]
    terminal = trace["terminal"]
    if (
        terminal["outcome"]["winner"] != expected_winner
        or terminal["outcome"]["reason"] != terminal_reason
        or terminal["terminal_ply"] != pv_plies
        or trace["side"] != side
    ):
        raise ValueError("two-runner exact principal variation claim does not replay")
    normalized_result = dict(_copy(result, "two-runner exact result"))
    normalized_result["principal_variation"] = trace["actions"]
    normalized_exact = {
        "status": "COMPLETED",
        "result": normalized_result,
        "budget_observation": None,
    }
    return normalized_exact, _lineage_evidence(trace)


def _normalize_exact_slot(
    pair: Mapping[str, Any],
    expected: Mapping[str, Any],
    raw_slot: Any,
    *,
    max_states: int,
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    slot = _exact_keys(
        raw_slot,
        (
            "schedule_index",
            "pair_index",
            "side",
            "pair_id",
            "definition_hash",
            "exact",
            "elapsed_seconds",
        ),
        "two-runner exact schedule slot",
    )
    for field in (
        "schedule_index",
        "pair_index",
        "side",
        "pair_id",
        "definition_hash",
    ):
        if _canonical_bytes(slot[field]) != _canonical_bytes(expected[field]):
            raise ValueError("two-runner exact schedule identity/order mismatch")
    side = expected["side"]
    source = parse_definition(pair["source_definition"])
    definition = parse_definition(pair["{}_definition".format(side.lower())])
    exact, lineage = _normalize_exact(
        source,
        definition,
        slot["exact"],
        max_states=max_states,
        side=side,
    )
    return (
        {
            **expected,
            "exact": exact,
            "elapsed_seconds": _elapsed_seconds(
                slot["elapsed_seconds"], "exact slot elapsed_seconds"
            ),
        },
        lineage,
    )


def _exact_slots_digest(domain: bytes, slots: Sequence[Mapping[str, Any]]) -> str:
    payload = [
        {key: value for key, value in slot.items() if key != "elapsed_seconds"}
        for slot in slots
    ]
    return hashlib.sha256(domain + _canonical_bytes(payload)).hexdigest()


def _normalize_pv_pair(
    source_actions: Sequence[Mapping[str, Any]],
    treatment_actions: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    common = 0
    for source_action, treatment_action in zip(source_actions, treatment_actions):
        if _canonical_bytes(source_action) != _canonical_bytes(treatment_action):
            break
        common += 1
    source_length = len(source_actions)
    treatment_length = len(treatment_actions)
    return {
        "common_prefix_plies": common,
        "first_divergence_ply": (
            None if common == source_length == treatment_length else common + 1
        ),
        "source_principal_variation_plies": source_length,
        "treatment_principal_variation_plies": treatment_length,
        "principal_variation_plies_delta": treatment_length - source_length,
    }


def _outcome_comparison(
    source_exact: Mapping[str, Any], treatment_exact: Mapping[str, Any]
) -> Dict[str, Any]:
    source = source_exact["result"]
    treatment = treatment_exact["result"]
    source_value = source["value_for_a"]
    treatment_value = treatment["value_for_a"]
    return {
        "source_value_for_a": source_value,
        "treatment_value_for_a": treatment_value,
        "value_delta_for_a": treatment_value - source_value,
        "value_changed": source_value != treatment_value,
        "forced_result_transition": "{}->{}".format(
            source["forced_result"], treatment["forced_result"]
        ),
        "terminal_reason_transition": "{}->{}".format(
            source["terminal_reason"], treatment["terminal_reason"]
        ),
    }


def _response_assessment(
    records: Sequence[Mapping[str, Any]],
    response_field: str,
    *,
    exact_censored: bool,
) -> Dict[str, Any]:
    selected = [record for record in records if record.get(response_field) is True]
    strata = {record.get("stratum_id") for record in selected}
    if None in strata:
        raise ValueError("two-runner response record is missing stratum_id")
    if exact_censored:
        status = "INCONCLUSIVE_EXACT_CENSOR"
    elif len(selected) >= 4 and len(strata) >= 2:
        status = "SUPPORTED"
    elif not selected:
        status = "NOT_SUPPORTED"
    else:
        status = "INCONCLUSIVE"
    return {
        "status": status,
        "count": len(selected),
        "stratum_count": len(strata),
        "pair_ids": [record["pair_id"] for record in selected],
    }


def assess_two_runner_response(
    pair_records: Sequence[Mapping[str, Any]],
    response_field: str,
    *,
    exact_censored: bool = False,
) -> Dict[str, Any]:
    """Apply the frozen >=4 cases across >=2 full-strata response threshold."""

    if response_field not in (
        "containment_response",
        "exact_engagement_response",
    ):
        raise ValueError("unknown two-runner response field")
    if type(exact_censored) is not bool:
        raise ValueError("exact_censored must be a boolean")
    if not isinstance(pair_records, (list, tuple)):
        raise ValueError("two-runner response records must be an array")
    pair_ids = []
    for index, record in enumerate(pair_records):
        if not isinstance(record, Mapping):
            raise ValueError(
                "two-runner response record {} must be an object".format(index)
            )
        pair_id = record.get("pair_id")
        if not isinstance(pair_id, str) or not pair_id:
            raise ValueError(
                "two-runner response record {} pair_id must be a non-empty string".format(
                    index
                )
            )
        stratum_id = record.get("stratum_id")
        if stratum_id not in _STRATUM_IDS:
            raise ValueError(
                "two-runner response record {} has an unknown stratum_id".format(
                    index
                )
            )
        if response_field not in record:
            raise ValueError(
                "two-runner response record {} has a malformed response value".format(
                    index
                )
            )
        response = record[response_field]
        if response is not True and response is not False and response is not None:
            raise ValueError(
                "two-runner response record {} has a malformed response value".format(
                    index
                )
            )
        pair_ids.append(pair_id)
    if len(set(pair_ids)) != len(pair_ids):
        raise ValueError("two-runner response pair_ids must be unique")
    return _response_assessment(
        pair_records, response_field, exact_censored=exact_censored
    )


def _integer_histogram(values: Iterable[int]) -> Dict[str, int]:
    histogram = Counter(values)
    return {str(value): histogram[value] for value in sorted(histogram)}


def _exact_side_summary(
    records: Sequence[Mapping[str, Any]], side: str
) -> Dict[str, Any]:
    exact_key = "{}_exact".format(side)
    lineage_key = "{}_pv_lineage".format(side)
    completed = [record for record in records if record[exact_key]["status"] == "COMPLETED"]
    forced = Counter(record[exact_key]["result"]["forced_result"] for record in completed)
    terminal = Counter(
        record[exact_key]["result"]["terminal_reason"] for record in completed
    )
    lineages = [record[lineage_key] for record in completed]
    return {
        "completed_count": len(completed),
        "censored_count": len(records) - len(completed),
        "forced_results": dict(sorted(forced.items())),
        "terminal_reasons": dict(sorted(terminal.items())),
        "searched_states_total": sum(
            record[exact_key]["result"]["searched_states"] for record in completed
        ),
        "cache_hits_total": sum(
            record[exact_key]["result"]["cache_hits"] for record in completed
        ),
        "principal_variation_plies_histogram": _integer_histogram(
            record[exact_key]["result"]["principal_variation_plies"]
            for record in completed
        ),
        "pv_original_moved_count": sum(
            lineage["summary"]["original_moved"] for lineage in lineages
        ),
        "pv_added_moved_count": sum(
            lineage["summary"]["added_moved"] for lineage in lineages
        ),
        "pv_both_lineages_moved_count": sum(
            lineage["summary"]["both_lineages_moved"] for lineage in lineages
        ),
        "pv_with_both_lineage_decision_count": sum(
            lineage["summary"]["both_lineage_decision_count"] > 0
            for lineage in lineages
        ),
        "pv_engaged_count": sum(
            lineage["summary"]["two_runner_engaged"] for lineage in lineages
        ),
    }


def _exact_group_summary(records: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    paired = [record for record in records if record["paired_status"] == "COMPLETED"]
    transitions = Counter(
        record["outcome_comparison"]["forced_result_transition"] for record in paired
    )
    terminal_transitions = Counter(
        record["outcome_comparison"]["terminal_reason_transition"] for record in paired
    )
    return {
        "pair_count": len(records),
        "paired_completed_count": len(paired),
        "paired_censored_count": len(records) - len(paired),
        "source": _exact_side_summary(records, "source"),
        "treatment": _exact_side_summary(records, "treatment"),
        "forced_result_transitions": dict(sorted(transitions.items())),
        "terminal_reason_transitions": dict(sorted(terminal_transitions.items())),
        "principal_variation_plies_delta_histogram": _integer_histogram(
            record["normalized_pv"]["principal_variation_plies_delta"]
            for record in paired
        ),
        "value_changed_count": sum(
            record["outcome_comparison"]["value_changed"] for record in paired
        ),
        "containment_response_count": sum(
            record["containment_response"] is True for record in records
        ),
        "exact_engagement_response_count": sum(
            record["exact_engagement_response"] is True for record in records
        ),
    }


def _exact_breakdowns(records: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    return {
        "all": _exact_group_summary(records),
        "by_vector_band": {
            band: _exact_group_summary(
                [record for record in records if record["vector_band"] == band]
            )
            for band in _VECTOR_BANDS
        },
        "by_first_player": {
            first: _exact_group_summary(
                [
                    record
                    for record in records
                    if record["stratum"]["first_player"] == first
                ]
            )
            for first in ("A", "B")
        },
        "by_goal_axis_relation": {
            relation: _exact_group_summary(
                [
                    record
                    for record in records
                    if record["stratum"]["goal_axis_relation"] == relation
                ]
            )
            for relation in ("ALIGNED", "ORTHOGONAL")
        },
        "by_structural_cell": {
            cell: _exact_group_summary(
                [record for record in records if record["structural_cell"] == cell]
            )
            for cell in _STRUCTURAL_CELLS
        },
        "by_stratum": {
            stratum: _exact_group_summary(
                [record for record in records if record["stratum_id"] == stratum]
            )
            for stratum in _STRATUM_IDS
        },
    }


def _inspection_score(domain: bytes, pair: Mapping[str, Any]) -> str:
    identity = {
        "source_d4_canonical_hash": pair["source_d4_canonical_hash"],
        "treatment_d4_canonical_hash": pair["treatment_d4_canonical_hash"],
    }
    return hashlib.sha256(domain + _canonical_bytes(identity)).hexdigest()


def build_two_runner_exact_inspection(
    pair_records: Sequence[Mapping[str, Any]],
    *,
    manifest_pairs: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Build the exact-only deterministic inspection union in manifest order."""

    if not isinstance(pair_records, (list, tuple)) or not isinstance(
        manifest_pairs, (list, tuple)
    ):
        raise ValueError("two-runner inspection inputs must be pair arrays")
    if len(pair_records) != len(manifest_pairs):
        raise ValueError("two-runner inspection pair/manifest lengths differ")
    by_id = {record.get("pair_id"): record for record in pair_records}
    if len(by_id) != len(pair_records) or None in by_id:
        raise ValueError("two-runner inspection pair identities must be unique")

    reasons: Dict[str, set[str]] = {}
    pools: Dict[str, Dict[str, list[Mapping[str, Any]]]] = {
        band: {"change": [], "control": []} for band in _VECTOR_BANDS
    }
    exact_censored = False
    for pair in manifest_pairs:
        pair_id = pair["pair_id"]
        if pair_id not in by_id:
            raise ValueError("two-runner inspection record is missing a manifest pair")
        record = by_id[pair_id]
        pair_reasons = reasons.setdefault(pair_id, set())
        source = record.get("source_exact")
        treatment = record.get("treatment_exact")
        incomplete = bool(
            not isinstance(source, Mapping)
            or not isinstance(treatment, Mapping)
            or source.get("status") != "COMPLETED"
            or treatment.get("status") != "COMPLETED"
        )
        if incomplete:
            exact_censored = True
            pair_reasons.add("EXACT_CENSOR")
        else:
            pool_name = (
                "change" if record["outcome_comparison"]["value_changed"] else "control"
            )
            pools[pair["vector_band"]][pool_name].append(pair)
        if record.get("containment_response") is True:
            pair_reasons.add("CONTAINMENT_RESPONSE")
        if record.get("exact_engagement_response") is True:
            pair_reasons.add("EXACT_ENGAGEMENT_RESPONSE")
        if pair["selection_rank"] == 0:
            pair_reasons.add("STRATUM_FLOOR")

    pool_evidence: Dict[str, Any] = {}
    for band in _VECTOR_BANDS:
        for pool_name, domain, reason in (
            ("change", _CHANGE_INSPECTION_DOMAIN, "OUTCOME_CHANGE_SAMPLE"),
            ("control", _CONTROL_INSPECTION_DOMAIN, "OUTCOME_UNCHANGED_CONTROL"),
        ):
            pool = pools[band][pool_name]
            ordered = sorted(
                pool,
                key=lambda pair: (
                    _inspection_score(domain, pair),
                    pair["source_d4_canonical_hash"],
                    pair["treatment_d4_canonical_hash"],
                    pair["pair_id"],
                ),
            )
            selected = ordered[:4]
            for pair in selected:
                reasons[pair["pair_id"]].add(reason)
            pool_evidence["{}_{}".format(band, pool_name)] = {
                "availability": "PARTIAL_EXACT_CENSOR" if exact_censored else "COMPLETE",
                "pool_size": len(pool),
                "selected_count": len(selected),
                "shortfall": max(0, 4 - len(pool)),
                "selected_pair_ids": [pair["pair_id"] for pair in selected],
            }

    reason_rank = {
        reason: index for index, reason in enumerate(_EXACT_INSPECTION_REASON_ORDER)
    }
    selected_rows = []
    for pair in manifest_pairs:
        pair_reasons = reasons[pair["pair_id"]]
        if not pair_reasons:
            continue
        selected_rows.append(
            {
                "pair_id": pair["pair_id"],
                "source_d4_canonical_hash": pair["source_d4_canonical_hash"],
                "treatment_d4_canonical_hash": pair[
                    "treatment_d4_canonical_hash"
                ],
                "vector_band": pair["vector_band"],
                "stratum_id": pair["stratum_id"],
                "reasons": sorted(pair_reasons, key=reason_rank.__getitem__),
            }
        )
    return {
        "version": "two-runner-v1-exact-inspection-v1",
        "disposition": (
            "EXACT_ONLY_CENSORED" if exact_censored else "EXACT_COMPLETE_PENDING_DEPTH5"
        ),
        "reason_order": list(_EXACT_INSPECTION_REASON_ORDER),
        "pools": pool_evidence,
        "selected": selected_rows,
    }


def validate_two_runner_exact_inspection(
    inspection: Mapping[str, Any],
    pair_records: Sequence[Mapping[str, Any]],
    *,
    manifest_pairs: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    rebuilt = build_two_runner_exact_inspection(
        pair_records, manifest_pairs=manifest_pairs
    )
    if _canonical_bytes(inspection) != _canonical_bytes(rebuilt):
        raise ValueError("two-runner exact inspection does not reconstruct")
    return _copy(inspection, "two-runner exact inspection")


def build_two_runner_exact_result(
    manifest_or_pairs: Any,
    exact_slots: Sequence[Mapping[str, Any]],
    *,
    manifest_validator: Optional[Callable[[Any], Any]] = None,
    expected_pair_count: int = TWO_RUNNER_PAIR_COUNT,
    max_states: int = TWO_RUNNER_EXACT_MAX_STATES,
) -> Dict[str, Any]:
    """Validate all fixed exact slots and derive the complete exact artifact."""

    _strict_int(max_states, "max_states", minimum=1)
    pairs, manifest_digest, manifest_id = _manifest_pairs(
        manifest_or_pairs,
        manifest_validator=manifest_validator,
        expected_pair_count=expected_pair_count,
    )
    schedule = _schedule_from_pairs(pairs)
    if not isinstance(exact_slots, (list, tuple)) or len(exact_slots) != len(schedule):
        raise ValueError("two-runner exact slots must cover the full fixed schedule")

    normalized_slots = []
    by_pair: Dict[int, Dict[str, Any]] = {
        index: {} for index in range(expected_pair_count)
    }
    for expected, raw_slot in zip(schedule, exact_slots):
        pair = pairs[expected["pair_index"]]
        normalized, lineage = _normalize_exact_slot(
            pair, expected, raw_slot, max_states=max_states
        )
        normalized_slots.append(normalized)
        side = expected["side"].lower()
        by_pair[pair["pair_index"]]["{}_exact".format(side)] = normalized["exact"]
        by_pair[pair["pair_index"]]["{}_pv_lineage".format(side)] = lineage

    records = []
    for pair in pairs:
        evidence = by_pair[pair["pair_index"]]
        source_exact = evidence["source_exact"]
        treatment_exact = evidence["treatment_exact"]
        source_complete = source_exact["status"] == "COMPLETED"
        treatment_complete = treatment_exact["status"] == "COMPLETED"
        paired_complete = source_complete and treatment_complete
        if paired_complete:
            source_result = source_exact["result"]
            treatment_result = treatment_exact["result"]
            comparison = _outcome_comparison(source_exact, treatment_exact)
            normalized_pv = _normalize_pv_pair(
                source_result["principal_variation"],
                treatment_result["principal_variation"],
            )
            containment = bool(
                source_result["forced_result"] == "A_WIN"
                and source_result["terminal_reason"] == "NO_LEGAL_ACTION"
                and treatment_result["forced_result"] == "B_WIN"
                and treatment_result["terminal_reason"] == "GOAL"
            )
        else:
            comparison = None
            normalized_pv = None
            containment = None
        treatment_lineage = evidence["treatment_pv_lineage"]
        engagement = (
            bool(treatment_lineage["summary"]["two_runner_engaged"])
            if treatment_complete and treatment_lineage is not None
            else None
        )
        records.append(
            {
                "pair_index": pair["pair_index"],
                "pair_id": pair["pair_id"],
                "source_case_id": pair["source_case_id"],
                "stratum": pair["stratum"],
                "stratum_id": pair["stratum_id"],
                "structural_cell": pair["structural_cell"],
                "vector_band": pair["vector_band"],
                "selection_rank": pair["selection_rank"],
                "piece_multiplicity_delta": pair["piece_multiplicity_delta"],
                "source_definition_hash": pair["source_definition_hash"],
                "source_d4_canonical_hash": pair["source_d4_canonical_hash"],
                "treatment_definition_hash": pair["treatment_definition_hash"],
                "treatment_d4_canonical_hash": pair[
                    "treatment_d4_canonical_hash"
                ],
                "source_exact": source_exact,
                "source_pv_lineage": evidence["source_pv_lineage"],
                "treatment_exact": treatment_exact,
                "treatment_pv_lineage": treatment_lineage,
                "paired_status": (
                    "COMPLETED" if paired_complete else "INCOMPLETE_EXACT_CENSOR"
                ),
                "outcome_comparison": comparison,
                "normalized_pv": normalized_pv,
                "containment_response": containment,
                "exact_engagement_response": engagement,
            }
        )

    censored_slots = [
        slot for slot in normalized_slots if slot["exact"]["status"] != "COMPLETED"
    ]
    exact_censored = bool(censored_slots)
    containment_assessment = assess_two_runner_response(
        records, "containment_response", exact_censored=exact_censored
    )
    engagement_assessment = assess_two_runner_response(
        records, "exact_engagement_response", exact_censored=exact_censored
    )
    pending_status = "INCONCLUSIVE_EXACT_CENSOR" if exact_censored else "PENDING_DEPTH5"
    raw_assessments = {
        "containment_response": containment_assessment,
        "exact_engagement_response": engagement_assessment,
        "strong_frontier": {"status": pending_status},
        "candidate_shape": {"status": pending_status},
        "overall": {"status": pending_status},
    }
    source_forced = Counter()
    treatment_forced = Counter()
    for record in records:
        if record["source_exact"]["status"] == "COMPLETED":
            source_forced[record["source_exact"]["result"]["forced_result"]] += 1
        if record["treatment_exact"]["status"] == "COMPLETED":
            treatment_forced[
                record["treatment_exact"]["result"]["forced_result"]
            ] += 1
    inspection = build_two_runner_exact_inspection(records, manifest_pairs=pairs)
    source_seconds = sum(
        slot["elapsed_seconds"] for slot in normalized_slots[:expected_pair_count]
    )
    treatment_seconds = sum(
        slot["elapsed_seconds"] for slot in normalized_slots[expected_pair_count:]
    )
    return {
        "protocol_id": TWO_RUNNER_EXACT_PROTOCOL_ID,
        "manifest_id": manifest_id,
        "manifest_digest": manifest_digest,
        "configuration": {
            "pair_count": expected_pair_count,
            "max_states": max_states,
            "source_state_bound": TWO_RUNNER_SOURCE_STATE_BOUND,
            "treatment_state_bound": TWO_RUNNER_TREATMENT_STATE_BOUND,
            "source_natural_terminal_ply": {"A": 15, "B": 16},
            "treatment_natural_terminal_ply": {"A": 13, "B": 14},
            "schedule": "SOURCE_THEN_TREATMENT",
        },
        "schedule": schedule,
        "slots": normalized_slots,
        "pairs": records,
        "aggregate": {
            "exact_attempted": len(normalized_slots),
            "exact_completed": len(normalized_slots) - len(censored_slots),
            "exact_censored_count": len(censored_slots),
            "exact_censored_slots": [
                slot["schedule_index"] for slot in censored_slots
            ],
            "source_evidence_digest": _exact_slots_digest(
                _SOURCE_EXACT_DOMAIN, normalized_slots[:expected_pair_count]
            ),
            "treatment_evidence_digest": _exact_slots_digest(
                _TREATMENT_EXACT_DOMAIN,
                normalized_slots[expected_pair_count:],
            ),
            "source_forced_results": dict(sorted(source_forced.items())),
            "treatment_forced_results": dict(sorted(treatment_forced.items())),
            "containment_response_count": sum(
                record["containment_response"] is True for record in records
            ),
            "exact_engagement_response_count": sum(
                record["exact_engagement_response"] is True for record in records
            ),
            "piece_multiplicity_delta": 1,
            "breakdowns": _exact_breakdowns(records),
            "raw_assessments": raw_assessments,
        },
        "inspection": inspection,
        "timing": {
            "source_seconds": source_seconds,
            "treatment_seconds": treatment_seconds,
            "total_seconds": source_seconds + treatment_seconds,
        },
    }


def evaluate_two_runner_exact(
    manifest_or_pairs: Any,
    *,
    manifest_validator: Optional[Callable[[Any], Any]] = None,
    expected_pair_count: int = TWO_RUNNER_PAIR_COUNT,
    max_states: int = TWO_RUNNER_EXACT_MAX_STATES,
    solver: Callable[..., Any] = solve_game,
    clock: Callable[[], float] = time.perf_counter,
) -> Dict[str, Any]:
    """Execute every source, seal it, then execute every treatment.

    State-budget censors occupy their scheduled slot and do not suppress later
    definitions.  Any malformed source evidence, including a PLY_LIMIT claim,
    fails during the source phase seal before the first treatment solver call.
    """

    _strict_int(max_states, "max_states", minimum=1)
    pairs, _, _ = _manifest_pairs(
        manifest_or_pairs,
        manifest_validator=manifest_validator,
        expected_pair_count=expected_pair_count,
    )
    schedule = _schedule_from_pairs(pairs)
    source_slots = []
    for entry in schedule[:expected_pair_count]:
        pair = pairs[entry["pair_index"]]
        definition = parse_definition(pair["source_definition"])
        started = clock()
        try:
            exact = _exact_payload_from_solve(solver(definition, max_states=max_states))
        except SolveBudgetExceeded as error:
            exact = {
                "status": "CENSORED_STATE_BUDGET",
                "result": None,
                "budget_observation": {
                    "searched_states": error.searched_states,
                    "max_states": error.max_states,
                },
            }
        elapsed = _elapsed_seconds(clock() - started, "exact elapsed_seconds")
        source_slots.append({**entry, "exact": exact, "elapsed_seconds": elapsed})

    sealed_source_slots = [
        _normalize_exact_slot(
            pairs[entry["pair_index"]], entry, slot, max_states=max_states
        )[0]
        for entry, slot in zip(schedule[:expected_pair_count], source_slots)
    ]
    source_seal = _exact_slots_digest(_SOURCE_EXACT_DOMAIN, sealed_source_slots)
    slots = list(source_slots)

    for entry in schedule[expected_pair_count:]:
        pair = pairs[entry["pair_index"]]
        definition = parse_definition(pair["treatment_definition"])
        started = clock()
        try:
            exact = _exact_payload_from_solve(solver(definition, max_states=max_states))
        except SolveBudgetExceeded as error:
            exact = {
                "status": "CENSORED_STATE_BUDGET",
                "result": None,
                "budget_observation": {
                    "searched_states": error.searched_states,
                    "max_states": error.max_states,
                },
            }
        elapsed = _elapsed_seconds(clock() - started, "exact elapsed_seconds")
        slots.append({**entry, "exact": exact, "elapsed_seconds": elapsed})

    result = build_two_runner_exact_result(
        manifest_or_pairs,
        slots,
        manifest_validator=manifest_validator,
        expected_pair_count=expected_pair_count,
        max_states=max_states,
    )
    if result["aggregate"]["source_evidence_digest"] != source_seal:
        raise ValueError("source exact evidence changed after its phase seal")
    return result


def _timing_free_result(value: Mapping[str, Any]) -> Dict[str, Any]:
    projection = _copy(value, "two-runner timing-free result")
    projection.pop("timing", None)
    slots = projection.get("slots")
    if isinstance(slots, list):
        for slot in slots:
            if isinstance(slot, dict):
                slot.pop("elapsed_seconds", None)
    return projection


def _validate_timing_summary(
    timing_value: Any,
    slots: Sequence[Mapping[str, Any]],
    pair_count: int,
) -> Dict[str, float]:
    timing = _exact_keys(
        timing_value,
        ("source_seconds", "treatment_seconds", "total_seconds"),
        "two-runner exact timing",
    )
    normalized = {
        field: _elapsed_seconds(timing[field], "exact timing {}".format(field))
        for field in timing
    }
    source_seconds = sum(
        _elapsed_seconds(slot["elapsed_seconds"], "source slot timing")
        for slot in slots[:pair_count]
    )
    treatment_seconds = sum(
        _elapsed_seconds(slot["elapsed_seconds"], "treatment slot timing")
        for slot in slots[pair_count:]
    )
    expected = {
        "source_seconds": source_seconds,
        "treatment_seconds": treatment_seconds,
        "total_seconds": source_seconds + treatment_seconds,
    }
    if normalized != expected:
        raise ValueError("two-runner exact timing does not match slot timings")
    return normalized


def validate_two_runner_exact_result(
    result: Mapping[str, Any],
    manifest_or_pairs: Any,
    *,
    manifest_validator: Optional[Callable[[Any], Any]] = None,
    expected_pair_count: int = TWO_RUNNER_PAIR_COUNT,
    max_states: int = TWO_RUNNER_EXACT_MAX_STATES,
) -> Dict[str, Any]:
    """Strictly reconstruct an exact artifact from its manifest and raw slots."""

    value = _exact_keys(
        result,
        (
            "protocol_id",
            "manifest_id",
            "manifest_digest",
            "configuration",
            "schedule",
            "slots",
            "pairs",
            "aggregate",
            "inspection",
            "timing",
        ),
        "two-runner exact result",
    )
    rebuilt = build_two_runner_exact_result(
        manifest_or_pairs,
        value["slots"],
        manifest_validator=manifest_validator,
        expected_pair_count=expected_pair_count,
        max_states=max_states,
    )
    _validate_timing_summary(value["timing"], value["slots"], expected_pair_count)
    if _canonical_bytes(_timing_free_result(value)) != _canonical_bytes(
        _timing_free_result(rebuilt)
    ):
        raise ValueError("two-runner exact result does not reconstruct")
    return _copy(value, "two-runner exact result")


def _validate_seed_sequence(value: Any, label: str) -> Tuple[int, ...]:
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError("{} seeds must be a nonempty array".format(label))
    seeds = tuple(value)
    if any(type(seed) is not int for seed in seeds):
        raise ValueError("{} seeds must be integers (not booleans)".format(label))
    if len(set(seeds)) != len(seeds):
        raise ValueError("{} seeds must be unique".format(label))
    return seeds


def _normalize_profile_game(
    source: GameDefinition,
    definition: GameDefinition,
    value: Any,
) -> Dict[str, Any]:
    stored_lineage = None
    if isinstance(value, GameRecord):
        raw = value.to_dict()
        seed = raw["seed"]
        actions = raw["actions"]
        terminal_outcome = {
            "winner": raw["winner"],
            "reason": raw["terminal_reason"],
        }
        terminal_ply = raw["plies"]
    else:
        if not isinstance(value, Mapping):
            raise ValueError("two-runner sampled game must be an object")
        fields = set(value)
        normalized_fields = {
            "seed",
            "actions",
            "terminal_outcome",
            "terminal_ply",
            "lineage",
        }
        compact_fields = normalized_fields - {"lineage"}
        game_record_fields = {
            "seed",
            "agent_a",
            "agent_b",
            "actions",
            "winner",
            "terminal_reason",
            "plies",
        }
        if fields == normalized_fields:
            seed = value["seed"]
            actions = value["actions"]
            terminal_outcome = value["terminal_outcome"]
            terminal_ply = value["terminal_ply"]
            stored_lineage = value["lineage"]
        elif fields == compact_fields:
            seed = value["seed"]
            actions = value["actions"]
            terminal_outcome = value["terminal_outcome"]
            terminal_ply = value["terminal_ply"]
        elif fields == game_record_fields:
            seed = value["seed"]
            actions = value["actions"]
            terminal_outcome = {
                "winner": value["winner"],
                "reason": value["terminal_reason"],
            }
            terminal_ply = value["plies"]
        else:
            raise ValueError("two-runner sampled game fields mismatch")

    seed = _strict_int(seed, "sampled game seed")
    claim = _exact_keys(
        terminal_outcome,
        ("winner", "reason"),
        "sampled terminal outcome",
    )
    if claim["winner"] not in ("A", "B", None):
        raise ValueError("sampled terminal winner is malformed")
    terminal_reason = _nonempty_string(
        claim["reason"], "sampled terminal reason"
    )
    if terminal_reason == "PLY_LIMIT":
        raise ValueError("sampled two-runner PLY_LIMIT is an integrity failure")
    terminal_ply = _strict_int(terminal_ply, "sampled terminal ply")
    trace = derive_two_runner_lineage_trace(source, definition, actions)
    terminal = trace["terminal"]
    if (
        _canonical_bytes(claim) != _canonical_bytes(terminal["outcome"])
        or terminal_ply != terminal["terminal_ply"]
    ):
        raise ValueError("two-runner sampled terminal claim does not replay")
    if stored_lineage is not None:
        validated_lineage = validate_two_runner_lineage_trace(
            source, definition, stored_lineage
        )
        if _canonical_bytes(validated_lineage) != _canonical_bytes(trace):
            raise ValueError("stored sampled lineage does not match its actions")
    return {
        "seed": seed,
        "actions": trace["actions"],
        "terminal_outcome": _copy(terminal["outcome"], "terminal outcome"),
        "terminal_ply": terminal_ply,
        "lineage": _lineage_evidence(trace),
    }


def _wilson_interval(
    successes: int, samples: int, z: float = 1.959963984540054
) -> Optional[list[float]]:
    if samples == 0:
        return None
    proportion = successes / samples
    denominator = 1.0 + z * z / samples
    center = (proportion + z * z / (2.0 * samples)) / denominator
    margin = z * math.sqrt(
        proportion * (1.0 - proportion) / samples
        + z * z / (4.0 * samples * samples)
    ) / denominator
    return [max(0.0, center - margin), min(1.0, center + margin)]


def _profile_summary(games: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    a_wins = sum(game["terminal_outcome"]["winner"] == "A" for game in games)
    b_wins = sum(game["terminal_outcome"]["winner"] == "B" for game in games)
    draws = len(games) - a_wins - b_wins
    decisive = a_wins + b_wins
    reasons = Counter(game["terminal_outcome"]["reason"] for game in games)
    engaged = [
        game
        for game in games
        if game["lineage"]["summary"]["two_runner_engaged"]
    ]
    return {
        "game_count": len(games),
        "a_wins": a_wins,
        "b_wins": b_wins,
        "draws": draws,
        "a_win_rate": a_wins / len(games) if games else None,
        "b_win_rate": b_wins / len(games) if games else None,
        "draw_rate": draws / len(games) if games else None,
        "average_plies": (
            sum(game["terminal_ply"] for game in games) / len(games)
            if games
            else None
        ),
        "decisive_a_share": a_wins / decisive if decisive else None,
        "decisive_a_wilson_95": _wilson_interval(a_wins, decisive),
        "terminal_reasons": dict(sorted(reasons.items())),
        "seeds": [game["seed"] for game in games],
        "games_with_original_move": sum(
            game["lineage"]["summary"]["original_moved"] for game in games
        ),
        "games_with_added_move": sum(
            game["lineage"]["summary"]["added_moved"] for game in games
        ),
        "games_with_both_lineages_moved": sum(
            game["lineage"]["summary"]["both_lineages_moved"]
            for game in games
        ),
        "games_with_both_lineage_decision": sum(
            game["lineage"]["summary"]["both_lineage_decision_count"] > 0
            for game in games
        ),
        "engaged_game_count": len(engaged),
        "engaged_seeds": [game["seed"] for game in engaged],
    }


def build_two_runner_profile_evidence(
    source_definition_value: Any,
    played_definition_value: Any,
    profile: str,
    games: Sequence[Any],
    expected_seeds: Sequence[int] = TWO_RUNNER_SEEDS,
) -> Dict[str, Any]:
    """Seal one complete sampled profile with full replayable lineage traces."""

    source = _coerce_definition(source_definition_value, "source definition")
    definition = _coerce_definition(played_definition_value, "played definition")
    profile = _nonempty_string(profile, "profile")
    seeds = _validate_seed_sequence(expected_seeds, "two-runner profile")
    if not isinstance(games, (list, tuple)):
        raise ValueError("two-runner profile games must be an array")
    normalized = tuple(
        _normalize_profile_game(source, definition, game) for game in games
    )
    if tuple(game["seed"] for game in normalized) != seeds:
        raise ValueError("complete two-runner profile must preserve full seed order")
    result = {
        "status": "COMPLETED",
        "profile": profile,
        "expected_seeds": list(seeds),
        "completed_seed_prefix": list(seeds),
        "incomplete_seed": None,
        "games": list(normalized),
        "profile_summary": _profile_summary(normalized),
        "partial_summary": None,
        "budget_observation": None,
    }
    validate_two_runner_profile_evidence(
        source, definition, result, expected_seeds=seeds
    )
    return result


def build_censored_two_runner_profile_evidence(
    source_definition_value: Any,
    played_definition_value: Any,
    profile: str,
    completed_games: Sequence[Any],
    expected_seeds: Sequence[int],
    incomplete_seed: int,
    budget_observation: Mapping[str, Any],
) -> Dict[str, Any]:
    """Seal a completed seed prefix and the next node-censored seed."""

    source = _coerce_definition(source_definition_value, "source definition")
    definition = _coerce_definition(played_definition_value, "played definition")
    profile = _nonempty_string(profile, "profile")
    seeds = _validate_seed_sequence(expected_seeds, "two-runner profile")
    incomplete_seed = _strict_int(incomplete_seed, "incomplete seed")
    if not isinstance(completed_games, (list, tuple)):
        raise ValueError("two-runner completed games must be an array")
    normalized = tuple(
        _normalize_profile_game(source, definition, game)
        for game in completed_games
    )
    prefix = tuple(game["seed"] for game in normalized)
    if len(prefix) >= len(seeds) or prefix != seeds[: len(prefix)]:
        raise ValueError("censored games must be a strict completed seed prefix")
    if incomplete_seed != seeds[len(prefix)]:
        raise ValueError("censored profile must identify the next seed")
    budget = _exact_keys(
        budget_observation,
        ("visited_nodes", "max_nodes", "scope"),
        "two-runner profile budget observation",
    )
    visited = _strict_int(budget["visited_nodes"], "visited_nodes")
    maximum = _strict_int(budget["max_nodes"], "max_nodes", minimum=1)
    if visited != maximum or budget["scope"] != "per-candidate":
        raise ValueError("two-runner censor must exhaust its per-definition budget")
    result = {
        "status": "CENSORED_NODE_BUDGET",
        "profile": profile,
        "expected_seeds": list(seeds),
        "completed_seed_prefix": list(prefix),
        "incomplete_seed": incomplete_seed,
        "games": list(normalized),
        "profile_summary": None,
        "partial_summary": _profile_summary(normalized),
        "budget_observation": _copy(budget, "profile budget observation"),
    }
    validate_two_runner_profile_evidence(
        source, definition, result, expected_seeds=seeds
    )
    return result


def build_two_runner_censored_profile_evidence(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    """Compatibility spelling for the censored profile builder."""

    return build_censored_two_runner_profile_evidence(*args, **kwargs)


def validate_two_runner_profile_evidence(
    source_definition_value: Any,
    played_definition_value: Any,
    evidence: Any,
    *,
    expected_seeds: Optional[Sequence[int]] = None,
) -> Dict[str, Any]:
    """Rebuild every stored game, summary, and completed-prefix claim."""

    source = _coerce_definition(source_definition_value, "source definition")
    definition = _coerce_definition(played_definition_value, "played definition")
    value = _exact_keys(
        evidence,
        (
            "status",
            "profile",
            "expected_seeds",
            "completed_seed_prefix",
            "incomplete_seed",
            "games",
            "profile_summary",
            "partial_summary",
            "budget_observation",
        ),
        "two-runner profile evidence",
    )
    _nonempty_string(value["profile"], "profile")
    seeds = _validate_seed_sequence(value["expected_seeds"], "two-runner profile")
    if expected_seeds is not None:
        expected = _validate_seed_sequence(expected_seeds, "expected profile")
        if seeds != expected:
            raise ValueError("two-runner profile expected seed sequence mismatch")
    games = value["games"]
    if not isinstance(games, list):
        raise ValueError("two-runner profile games must be an array")
    completed_prefix = value["completed_seed_prefix"]
    if not isinstance(completed_prefix, list) or any(
        type(seed) is not int for seed in completed_prefix
    ):
        raise ValueError("completed seed prefix must be an integer array")
    normalized = tuple(
        _normalize_profile_game(source, definition, game) for game in games
    )
    if _canonical_bytes(games) != _canonical_bytes(normalized):
        raise ValueError("stored two-runner game evidence does not reconstruct")
    game_seeds = tuple(game["seed"] for game in normalized)
    summary = _profile_summary(normalized)
    if value["status"] == "COMPLETED":
        if (
            game_seeds != seeds
            or completed_prefix != list(seeds)
            or value["incomplete_seed"] is not None
            or _canonical_bytes(value["profile_summary"])
            != _canonical_bytes(summary)
            or value["partial_summary"] is not None
            or value["budget_observation"] is not None
        ):
            raise ValueError("complete two-runner profile evidence is inconsistent")
    elif value["status"] == "CENSORED_NODE_BUDGET":
        incomplete_seed = _strict_int(value["incomplete_seed"], "incomplete seed")
        if (
            len(game_seeds) >= len(seeds)
            or game_seeds != seeds[: len(game_seeds)]
            or completed_prefix != list(game_seeds)
            or incomplete_seed != seeds[len(game_seeds)]
            or value["profile_summary"] is not None
            or _canonical_bytes(value["partial_summary"])
            != _canonical_bytes(summary)
        ):
            raise ValueError("censored two-runner profile evidence is inconsistent")
        budget = _exact_keys(
            value["budget_observation"],
            ("visited_nodes", "max_nodes", "scope"),
            "two-runner profile budget observation",
        )
        if (
            type(budget["visited_nodes"]) is not int
            or type(budget["max_nodes"]) is not int
            or budget["visited_nodes"] != budget["max_nodes"]
            or budget["max_nodes"] < 1
            or budget["scope"] != "per-candidate"
        ):
            raise ValueError("censored two-runner profile budget is malformed")
    else:
        raise ValueError("two-runner profile has an unknown status")
    return _copy(value, "two-runner profile evidence")


def two_runner_direction(
    profile_summary: Optional[Mapping[str, Any]],
    exact_result: Mapping[str, Any],
    exact_terminal_reason: str,
    *,
    profile_status: str = "COMPLETED",
) -> Dict[str, Any]:
    """Compare one sampled direction with its exact non-horizon result."""

    _nonempty_string(exact_terminal_reason, "exact terminal reason")
    if exact_terminal_reason == "PLY_LIMIT":
        raise ValueError("two-runner exact PLY_LIMIT is an integrity failure")
    if profile_status not in ("COMPLETED", "INCOMPLETE_NODE_CENSOR"):
        raise ValueError("two-runner direction profile status is malformed")
    if profile_status != "COMPLETED":
        return {
            "status": "NOT_APPLICABLE_NODE_CENSOR",
            "sampled_direction": None,
            "direction_match": None,
        }
    forced = exact_result.get("forced_result")
    if forced not in _VALUE_BY_RESULT or not isinstance(profile_summary, Mapping):
        raise ValueError("two-runner direction needs exact and complete profile evidence")
    direction = sampled_direction(profile_summary)
    matches = forced in ("A_WIN", "B_WIN") and direction == forced
    return {
        "status": "MATCH" if matches else "MISMATCH",
        "sampled_direction": direction,
        "direction_match": matches,
    }


def _profile_name(depth: int) -> str:
    return "{}{}".format(_PROFILE_PREFIX, depth)


def _agent_identity(agent: Any) -> str:
    identity = getattr(agent, "identity", None)
    key = getattr(identity, "key", None)
    if not isinstance(key, str) or not key:
        raise ValueError("strong agent must expose a stable identity key")
    return key


def _new_agent(
    definition: GameDefinition,
    entry: Mapping[str, Any],
    *,
    depth: int,
    max_nodes: int,
    agent_factory: Optional[Callable[..., Any]],
) -> Any:
    agent = (
        MinimaxAgent(depth=depth, max_total_nodes=max_nodes)
        if agent_factory is None
        else agent_factory(
            definition=definition,
            depth=depth,
            max_nodes=max_nodes,
            schedule_entry=_copy(entry, "schedule entry"),
        )
    )
    reset = getattr(agent, "reset_budget", None)
    if not callable(reset):
        raise ValueError("strong agent must expose reset_budget")
    reset()
    if type(getattr(agent, "total_nodes", None)) is not int or agent.total_nodes != 0:
        raise ValueError("strong agent reset must set total_nodes to zero")
    return agent


def _execute_profile(
    source: GameDefinition,
    definition: GameDefinition,
    entry: Mapping[str, Any],
    *,
    seeds: Tuple[int, ...],
    depth: int,
    max_nodes: int,
    agent_factory: Optional[Callable[..., Any]],
) -> Dict[str, Any]:
    agent = _new_agent(
        definition,
        entry,
        depth=depth,
        max_nodes=max_nodes,
        agent_factory=agent_factory,
    )
    identity = _agent_identity(agent)
    expected_identity = _profile_name(depth)
    if identity != expected_identity:
        raise ValueError("strong agent identity must be {}".format(expected_identity))
    records = []
    game_nodes = []
    incomplete = None
    for seed in seeds:
        before = agent.total_nodes
        actions = []
        state = initial_state(definition)
        rng = random.Random(seed)
        try:
            while not state.terminal:
                choices = legal_actions(definition, state)
                action = agent.select_action(definition, state, choices, rng)
                if action not in choices:
                    raise ValueError("strong agent selected an illegal action")
                actions.append(action.to_dict())
                state = apply_action(definition, state, action)
        except SearchBudgetExceeded as error:
            if error.scope != "per-candidate":
                raise
            final = agent.total_nodes
            if (
                type(final) is not int
                or type(error.visited_nodes) is not int
                or type(error.max_nodes) is not int
                or final != error.visited_nodes
                or error.max_nodes != max_nodes
                or final != max_nodes
                or final < before
            ):
                raise ValueError("strong censor node accounting mismatch")
            lineage_prefix = derive_two_runner_lineage_trace(
                source, definition, actions, require_terminal=False
            )
            if lineage_prefix["terminal"]["is_terminal"]:
                raise ValueError("incomplete action prefix is already terminal")
            incomplete = {
                "seed": seed,
                "completed_action_prefix": lineage_prefix["actions"],
                "lineage_prefix": lineage_prefix,
                "nodes_before_seed": before,
                "nodes_consumed": final - before,
                "final_cumulative_nodes": final,
                "limit": error.max_nodes,
                "scope": error.scope,
            }
            break
        assert state.outcome is not None
        after = agent.total_nodes
        if type(after) is not int or after <= before or after > max_nodes:
            raise ValueError("strong game node accounting mismatch")
        record = GameRecord(
            seed=seed,
            agent_a=identity,
            agent_b=identity,
            actions=tuple(action_from_dict(action) for action in actions),
            winner=state.outcome.winner,
            terminal_reason=state.outcome.reason,
        )
        records.append(record)
        game_nodes.append(
            {
                "seed": seed,
                "nodes_before": before,
                "nodes_after": after,
                "nodes_used": after - before,
            }
        )

    profile = _profile_name(depth)
    if incomplete is None:
        evidence = build_two_runner_profile_evidence(
            source, definition, profile, records, seeds
        )
        status = "COMPLETED"
    else:
        evidence = build_censored_two_runner_profile_evidence(
            source,
            definition,
            profile,
            records,
            seeds,
            incomplete["seed"],
            {
                "visited_nodes": incomplete["final_cumulative_nodes"],
                "max_nodes": incomplete["limit"],
                "scope": incomplete["scope"],
            },
        )
        status = "INCOMPLETE_NODE_CENSOR"
    return {
        **entry,
        "status": status,
        "agent_identity": identity,
        "profile_evidence": evidence,
        "game_nodes": game_nodes,
        "incomplete_attempt": incomplete,
        "expanded_nodes": agent.total_nodes,
    }


def _normalize_profile_slot(
    pair: Mapping[str, Any],
    expected: Mapping[str, Any],
    raw_slot: Any,
    *,
    seeds: Tuple[int, ...],
    depth: int,
    max_nodes: int,
) -> Dict[str, Any]:
    slot = _exact_keys(
        raw_slot,
        (
            "schedule_index",
            "pair_index",
            "side",
            "pair_id",
            "definition_hash",
            "status",
            "agent_identity",
            "profile_evidence",
            "game_nodes",
            "incomplete_attempt",
            "expanded_nodes",
            "elapsed_seconds",
        ),
        "two-runner depth-5 schedule slot",
    )
    for field in ("schedule_index", "pair_index", "side", "pair_id", "definition_hash"):
        if _canonical_bytes(slot[field]) != _canonical_bytes(expected[field]):
            raise ValueError("two-runner depth-5 schedule identity/order mismatch")
    if slot["agent_identity"] != _profile_name(depth):
        raise ValueError("two-runner depth-5 agent identity mismatch")
    source = parse_definition(pair["source_definition"])
    definition = parse_definition(
        pair["{}_definition".format(expected["side"].lower())]
    )
    evidence = validate_two_runner_profile_evidence(
        source, definition, slot["profile_evidence"], expected_seeds=seeds
    )
    if evidence["profile"] != _profile_name(depth):
        raise ValueError("two-runner depth-5 profile identity mismatch")
    expected_status = (
        "COMPLETED"
        if evidence["status"] == "COMPLETED"
        else "INCOMPLETE_NODE_CENSOR"
    )
    if slot["status"] != expected_status:
        raise ValueError("two-runner depth-5 slot/profile status mismatch")
    expanded = _strict_int(slot["expanded_nodes"], "expanded_nodes")
    if expanded > max_nodes:
        raise ValueError("two-runner expanded_nodes exceeds its fixed cap")
    raw_nodes = slot["game_nodes"]
    if not isinstance(raw_nodes, list) or len(raw_nodes) != len(evidence["games"]):
        raise ValueError("two-runner game node ledger length mismatch")
    previous = 0
    normalized_nodes = []
    for game, raw_node in zip(evidence["games"], raw_nodes):
        node = _exact_keys(
            raw_node,
            ("seed", "nodes_before", "nodes_after", "nodes_used"),
            "two-runner game node evidence",
        )
        seed = _strict_int(node["seed"], "game node seed")
        before = _strict_int(node["nodes_before"], "nodes_before")
        after = _strict_int(node["nodes_after"], "nodes_after")
        used = _strict_int(node["nodes_used"], "nodes_used", minimum=1)
        if (
            seed != game["seed"]
            or before != previous
            or after <= before
            or used != after - before
            or after > max_nodes
        ):
            raise ValueError("two-runner game node evidence does not reconstruct")
        previous = after
        normalized_nodes.append(_copy(node, "game node evidence"))

    incomplete = slot["incomplete_attempt"]
    if expected_status == "COMPLETED":
        if incomplete is not None or previous != expanded:
            raise ValueError("completed two-runner profile node evidence is inconsistent")
    else:
        item = _exact_keys(
            incomplete,
            (
                "seed",
                "completed_action_prefix",
                "lineage_prefix",
                "nodes_before_seed",
                "nodes_consumed",
                "final_cumulative_nodes",
                "limit",
                "scope",
            ),
            "incomplete two-runner profile attempt",
        )
        incomplete_seed = _strict_int(item["seed"], "incomplete seed")
        before = _strict_int(item["nodes_before_seed"], "incomplete nodes_before")
        consumed = _strict_int(item["nodes_consumed"], "incomplete nodes_consumed")
        final = _strict_int(
            item["final_cumulative_nodes"], "incomplete final cumulative nodes"
        )
        limit = _strict_int(item["limit"], "incomplete node limit", minimum=1)
        lineage = validate_two_runner_lineage_trace(
            source,
            definition,
            item["lineage_prefix"],
            require_terminal=False,
        )
        if (
            incomplete_seed != evidence["incomplete_seed"]
            or _canonical_bytes(item["completed_action_prefix"])
            != _canonical_bytes(lineage["actions"])
            or lineage["terminal"]["is_terminal"]
            or before != previous
            or final != before + consumed
            or final != expanded
            or final != limit
            or limit != max_nodes
            or item["scope"] != "per-candidate"
        ):
            raise ValueError("incomplete two-runner profile evidence is inconsistent")
        budget = evidence["budget_observation"]
        if (
            budget["visited_nodes"] != final
            or budget["max_nodes"] != limit
            or budget["scope"] != item["scope"]
        ):
            raise ValueError("profile and incomplete-attempt budgets disagree")
    return {
        **expected,
        "status": expected_status,
        "agent_identity": slot["agent_identity"],
        "profile_evidence": evidence,
        "game_nodes": normalized_nodes,
        "incomplete_attempt": (
            _copy(incomplete, "incomplete attempt") if incomplete is not None else None
        ),
        "expanded_nodes": expanded,
        "elapsed_seconds": _elapsed_seconds(
            slot["elapsed_seconds"], "depth-5 slot elapsed_seconds"
        ),
    }


def _profile_slots_digest(
    domain: bytes, slots: Sequence[Mapping[str, Any]]
) -> str:
    payload = [
        {key: value for key, value in slot.items() if key != "elapsed_seconds"}
        for slot in slots
    ]
    return hashlib.sha256(domain + _canonical_bytes(payload)).hexdigest()


def _strong_failures(
    definition: GameDefinition,
    profile: Mapping[str, Any],
    gates: PlayGates,
) -> list[str]:
    samples = profile.get("game_count")
    if type(samples) is not int or samples < 1:
        raise ValueError("complete strong profile requires at least one game")
    failures = set()
    if profile["draws"] / samples > gates.max_draw_rate:
        failures.add("EXCESSIVE_DRAWS")
    if profile["average_plies"] < gates.min_average_plies:
        failures.add("TOO_SHORT")
    if (
        profile["average_plies"]
        > definition.max_plies * gates.max_average_plies_fraction
    ):
        failures.add("TOO_LONG")
    interval = profile["decisive_a_wilson_95"]
    if interval is not None:
        if interval[0] > 0.5 + gates.dominance_interval_margin:
            failures.add("A_DOMINANT")
        if interval[1] < 0.5 - gates.dominance_interval_margin:
            failures.add("B_DOMINANT")
    return sorted(failures)


def _profile_assessment(
    definition: GameDefinition,
    slot: Mapping[str, Any],
    exact: Mapping[str, Any],
    *,
    gates: PlayGates,
) -> Dict[str, Any]:
    exact_result = exact["result"]
    if slot["status"] != "COMPLETED":
        direction = two_runner_direction(
            None,
            exact_result,
            exact_result["terminal_reason"],
            profile_status=slot["status"],
        )
        return {
            "status": slot["status"],
            "profile": None,
            "partial_profile": _copy(
                slot["profile_evidence"]["partial_summary"],
                "partial sampled profile",
            ),
            "direction": direction,
            "failure_codes": None,
            "same_game_engagement": None,
        }
    profile = _copy(
        slot["profile_evidence"]["profile_summary"], "sampled profile"
    )
    direction = two_runner_direction(
        profile, exact_result, exact_result["terminal_reason"]
    )
    return {
        "status": "COMPLETED",
        "profile": profile,
        "partial_profile": None,
        "direction": direction,
        "failure_codes": _strong_failures(definition, profile, gates),
        "same_game_engagement": bool(profile["engaged_game_count"] > 0),
    }


def _profile_node_totals(slots: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    completed = sum(
        item["nodes_used"] for slot in slots for item in slot["game_nodes"]
    )
    incomplete = sum(
        slot["incomplete_attempt"]["nodes_consumed"]
        for slot in slots
        if slot["incomplete_attempt"] is not None
    )
    expanded = sum(slot["expanded_nodes"] for slot in slots)
    if expanded != completed + incomplete:
        raise ValueError("two-runner profile node totals do not reconstruct")
    return {
        "completed_game_nodes": completed,
        "incomplete_attempt_nodes": incomplete,
        "expanded_nodes_total": expanded,
    }


def _profile_slot_bucket(slots: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    games = [
        game for slot in slots for game in slot["profile_evidence"]["games"]
    ]
    results = Counter(
        "DRAW"
        if game["terminal_outcome"]["winner"] is None
        else "{}_WIN".format(game["terminal_outcome"]["winner"])
        for game in games
    )
    terminal = Counter(game["terminal_outcome"]["reason"] for game in games)
    total_plies = sum(game["terminal_ply"] for game in games)
    return {
        "definition_count": len(slots),
        "game_count": len(games),
        "sampled_results": dict(sorted(results.items())),
        "terminal_reasons": dict(sorted(terminal.items())),
        "total_plies": total_plies,
        "average_plies": total_plies / len(games) if games else None,
        "games_with_original_move": sum(
            game["lineage"]["summary"]["original_moved"] for game in games
        ),
        "games_with_added_move": sum(
            game["lineage"]["summary"]["added_moved"] for game in games
        ),
        "games_with_both_lineages_moved": sum(
            game["lineage"]["summary"]["both_lineages_moved"] for game in games
        ),
        "games_with_both_lineage_decision": sum(
            game["lineage"]["summary"]["both_lineage_decision_count"] > 0
            for game in games
        ),
        "engaged_game_count": sum(
            game["lineage"]["summary"]["two_runner_engaged"] for game in games
        ),
        **_profile_node_totals(slots),
    }


def _descriptive_profile_aggregate(
    slots: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    result = {}
    for side in ("SOURCE", "TREATMENT"):
        side_slots = [slot for slot in slots if slot["side"] == side]
        result[side.lower()] = {
            "completed_profiles": _profile_slot_bucket(
                [slot for slot in side_slots if slot["status"] == "COMPLETED"]
            ),
            "censored_prefixes": _profile_slot_bucket(
                [
                    slot
                    for slot in side_slots
                    if slot["status"] == "INCOMPLETE_NODE_CENSOR"
                ]
            ),
        }
    return result


def _depth_side_breakdown(
    records: Sequence[Mapping[str, Any]],
    slots: Sequence[Mapping[str, Any]],
    side: str,
) -> Dict[str, Any]:
    pair_ids = {record["pair_id"] for record in records}
    side_slots = [
        slot
        for slot in slots
        if slot["side"] == side.upper() and slot["pair_id"] in pair_ids
    ]
    profiles = [record["{}_profile".format(side)] for record in records]
    direction_statuses = Counter(
        profile["direction"]["status"] for profile in profiles
    )
    failures = Counter(
        code for profile in profiles for code in (profile["failure_codes"] or [])
    )
    return {
        "profile_count": len(side_slots),
        "completed_profile_count": sum(
            slot["status"] == "COMPLETED" for slot in side_slots
        ),
        "censored_profile_count": sum(
            slot["status"] == "INCOMPLETE_NODE_CENSOR" for slot in side_slots
        ),
        "completed": _profile_slot_bucket(
            [slot for slot in side_slots if slot["status"] == "COMPLETED"]
        ),
        "censored_prefix": _profile_slot_bucket(
            [
                slot
                for slot in side_slots
                if slot["status"] == "INCOMPLETE_NODE_CENSOR"
            ]
        ),
        "direction_statuses": dict(sorted(direction_statuses.items())),
        "direction_mismatch_count": sum(
            profile["direction"]["direction_match"] is False
            for profile in profiles
        ),
        "failure_codes": dict(sorted(failures.items())),
    }


def _depth_group_summary(
    records: Sequence[Mapping[str, Any]],
    slots: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    frontier = [record for record in records if record["strong_frontier"]]
    candidates = [record for record in records if record["candidate_shaped"]]
    forced = Counter(
        record["treatment_exact_forced_result"] for record in records
    )
    return {
        "pair_count": len(records),
        "source": _depth_side_breakdown(records, slots, "source"),
        "treatment": _depth_side_breakdown(records, slots, "treatment"),
        "treatment_exact_forced_results": dict(sorted(forced.items())),
        "node_censor_count": sum(record["node_censored"] for record in records),
        "direction_mismatch_count": sum(
            record["direction_mismatch"] for record in records
        ),
        "treatment_same_game_engagement_count": sum(
            record["treatment_same_game_engagement"] is True
            for record in records
        ),
        "strong_frontier_count": len(frontier),
        "frontier_a_win_count": sum(
            record["treatment_exact_forced_result"] == "A_WIN"
            for record in frontier
        ),
        "frontier_b_win_count": sum(
            record["treatment_exact_forced_result"] == "B_WIN"
            for record in frontier
        ),
        "candidate_shaped_count": len(candidates),
    }


def _depth_breakdowns(
    records: Sequence[Mapping[str, Any]],
    slots: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    return {
        "all": _depth_group_summary(records, slots),
        "by_vector_band": {
            band: _depth_group_summary(
                [record for record in records if record["vector_band"] == band],
                slots,
            )
            for band in _VECTOR_BANDS
        },
        "by_first_player": {
            first: _depth_group_summary(
                [
                    record
                    for record in records
                    if record["stratum"]["first_player"] == first
                ],
                slots,
            )
            for first in ("A", "B")
        },
        "by_goal_axis_relation": {
            relation: _depth_group_summary(
                [
                    record
                    for record in records
                    if record["stratum"]["goal_axis_relation"] == relation
                ],
                slots,
            )
            for relation in ("ALIGNED", "ORTHOGONAL")
        },
        "by_structural_cell": {
            cell: _depth_group_summary(
                [record for record in records if record["structural_cell"] == cell],
                slots,
            )
            for cell in _STRUCTURAL_CELLS
        },
        "by_stratum": {
            stratum: _depth_group_summary(
                [record for record in records if record["stratum_id"] == stratum],
                slots,
            )
            for stratum in _STRATUM_IDS
        },
    }


def assess_two_runner_pairs(
    pair_records: Sequence[Mapping[str, Any]],
    raw_assessments: Mapping[str, Any],
) -> Dict[str, Any]:
    """Apply the frozen strong-frontier and candidate-shape priorities."""

    if not isinstance(pair_records, (list, tuple)) or not pair_records:
        raise ValueError("two-runner assessment requires pair records")
    if not isinstance(raw_assessments, Mapping):
        raise ValueError("two-runner raw assessments must be an object")
    containment = raw_assessments.get("containment_response")
    engagement = raw_assessments.get("exact_engagement_response")
    if not isinstance(containment, Mapping) or not isinstance(engagement, Mapping):
        raise ValueError("two-runner raw response assessments are incomplete")

    seen = set()
    for record in pair_records:
        if not isinstance(record, Mapping):
            raise ValueError("two-runner assessment records must be objects")
        pair_id = record.get("pair_id")
        if not isinstance(pair_id, str) or not pair_id or pair_id in seen:
            raise ValueError("two-runner assessment pair identities must be unique")
        seen.add(pair_id)
        for field in (
            "node_censored",
            "direction_mismatch",
            "strong_frontier",
            "candidate_shaped",
        ):
            if type(record.get(field)) is not bool:
                raise ValueError("two-runner assessment {} must be boolean".format(field))
        if record.get("structural_cell") not in _STRUCTURAL_CELLS:
            raise ValueError("two-runner assessment structural cell is malformed")
        if record.get("treatment_exact_forced_result") not in _VALUE_BY_RESULT:
            raise ValueError("two-runner assessment exact result is malformed")
        if record["candidate_shaped"] and not record["strong_frontier"]:
            raise ValueError("candidate-shaped case must belong to the strong frontier")

    node_censors = sum(record["node_censored"] for record in pair_records)
    direction_mismatches = sum(
        record["direction_mismatch"] for record in pair_records
    )
    frontier = [record for record in pair_records if record["strong_frontier"]]
    candidate = [record for record in pair_records if record["candidate_shaped"]]
    candidate_cells = {record["structural_cell"] for record in candidate}
    candidate_roles = {
        record["treatment_exact_forced_result"] for record in candidate
    }
    incomplete = bool(node_censors or direction_mismatches)
    if node_censors:
        incomplete_reason = "NODE_CENSOR"
    elif direction_mismatches:
        incomplete_reason = "DIRECTION_MISMATCH"
    else:
        incomplete_reason = None

    if incomplete:
        candidate_status = "INCONCLUSIVE"
        frontier_status = "INCONCLUSIVE"
        overall_status = "INCONCLUSIVE"
        next_branch = "NO_NEW_CASES_OR_RULE"
    else:
        frontier_status = "PRESENT" if frontier else "EMPTY"
        if (
            len(candidate) >= 4
            and len(candidate_cells) >= 2
            and {"A_WIN", "B_WIN"}.issubset(candidate_roles)
        ):
            candidate_status = "SUPPORTED"
            overall_status = "SUPPORTED_TWO_RUNNER_SETUP"
            next_branch = "PLAN_TWO_RUNNER_GENERATOR_HYPOTHESIS"
        elif not candidate:
            candidate_status = "NOT_SUPPORTED"
            overall_status = "NOT_SUPPORTED_TWO_RUNNER_SETUP"
            next_branch = "FAMILY_REASSESSMENT"
        else:
            candidate_status = "INCONCLUSIVE"
            overall_status = "INCONCLUSIVE"
            next_branch = "NO_NEW_CASES_OR_RULE"
    return {
        "strong_evidence": {
            "status": "INCONCLUSIVE" if incomplete else "COMPLETE",
            "node_censor_count": node_censors,
            "direction_mismatch_count": direction_mismatches,
            "incomplete_reason": incomplete_reason,
        },
        "containment_response": _copy(containment, "containment assessment"),
        "exact_engagement_response": _copy(
            engagement, "exact engagement assessment"
        ),
        "strong_frontier": {
            "status": frontier_status,
            "case_count": len(frontier),
            "a_win_count": sum(
                record["treatment_exact_forced_result"] == "A_WIN"
                for record in frontier
            ),
            "b_win_count": sum(
                record["treatment_exact_forced_result"] == "B_WIN"
                for record in frontier
            ),
            "structural_cell_count": len(
                {record["structural_cell"] for record in frontier}
            ),
        },
        "candidate_shape": {
            "status": candidate_status,
            "case_count": len(candidate),
            "structural_cell_count": len(candidate_cells),
            "exact_roles": sorted(candidate_roles),
        },
        "overall": {
            "status": overall_status,
            "next_branch": next_branch,
        },
    }


def build_two_runner_inspection(
    pair_records: Sequence[Mapping[str, Any]],
    *,
    manifest_pairs: Sequence[Mapping[str, Any]],
    exact_censored: bool = False,
) -> Dict[str, Any]:
    """Build the final manifest-ordered inspection union and pool evidence."""

    if type(exact_censored) is not bool:
        raise ValueError("exact_censored must be a boolean")
    if not isinstance(pair_records, (list, tuple)) or not isinstance(
        manifest_pairs, (list, tuple)
    ):
        raise ValueError("two-runner inspection inputs must be pair arrays")
    if len(pair_records) != len(manifest_pairs):
        raise ValueError("two-runner inspection pair/manifest lengths differ")
    by_id = {record.get("pair_id"): record for record in pair_records}
    if len(by_id) != len(pair_records) or None in by_id:
        raise ValueError("two-runner inspection pair identities must be unique")
    reasons: Dict[str, set[str]] = defaultdict(set)
    pools: Dict[str, Dict[str, list[Mapping[str, Any]]]] = {
        band: {"change": [], "control": []} for band in _VECTOR_BANDS
    }
    any_node_censor = False
    any_direction_mismatch = False
    for pair in manifest_pairs:
        pair_id = pair["pair_id"]
        if pair_id not in by_id:
            raise ValueError("two-runner inspection record is missing a manifest pair")
        record = by_id[pair_id]
        source_exact = record.get("source_exact")
        treatment_exact = record.get("treatment_exact")
        exact_incomplete = bool(
            not isinstance(source_exact, Mapping)
            or not isinstance(treatment_exact, Mapping)
            or source_exact.get("status") != "COMPLETED"
            or treatment_exact.get("status") != "COMPLETED"
        )
        if exact_incomplete:
            reasons[pair_id].add("EXACT_CENSOR")
        else:
            comparison = record.get("outcome_comparison")
            if not isinstance(comparison, Mapping):
                raise ValueError("complete inspection pair lacks outcome comparison")
            pool_name = "change" if comparison.get("value_changed") else "control"
            pools[pair["vector_band"]][pool_name].append(pair)
        if record.get("node_censored") is True:
            any_node_censor = True
            reasons[pair_id].add("NODE_CENSOR")
        if record.get("direction_mismatch") is True:
            any_direction_mismatch = True
            reasons[pair_id].add("DIRECTION_MISMATCH")
        if record.get("containment_response") is True:
            reasons[pair_id].add("CONTAINMENT_RESPONSE")
        if record.get("exact_engagement_response") is True:
            reasons[pair_id].add("EXACT_ENGAGEMENT_RESPONSE")
        if record.get("strong_frontier") is True:
            reasons[pair_id].add("STRONG_FRONTIER")
        if record.get("candidate_shaped") is True:
            reasons[pair_id].add("CANDIDATE_SHAPED")
        if pair["selection_rank"] == 0:
            reasons[pair_id].add("STRATUM_FLOOR")

    pool_evidence = {}
    for band in _VECTOR_BANDS:
        for pool_name, domain, reason in (
            (
                "change",
                _CHANGE_INSPECTION_DOMAIN,
                "OUTCOME_CHANGE_SAMPLE",
            ),
            (
                "control",
                _CONTROL_INSPECTION_DOMAIN,
                "OUTCOME_UNCHANGED_CONTROL",
            ),
        ):
            ordered = sorted(
                pools[band][pool_name],
                key=lambda pair: (
                    _inspection_score(domain, pair),
                    pair["source_d4_canonical_hash"],
                    pair["treatment_d4_canonical_hash"],
                    pair["pair_id"],
                ),
            )
            selected = ordered[:4]
            for pair in selected:
                reasons[pair["pair_id"]].add(reason)
            pool_evidence["{}_{}".format(band, pool_name)] = {
                "availability": (
                    "PARTIAL_EXACT_CENSOR" if exact_censored else "COMPLETE"
                ),
                "pool_size": len(ordered),
                "selected_count": len(selected),
                "shortfall": max(0, 4 - len(ordered)),
                "selected_pair_ids": [pair["pair_id"] for pair in selected],
            }

    reason_rank = {
        reason: index
        for index, reason in enumerate(_FINAL_INSPECTION_REASON_ORDER)
    }
    selected_rows = []
    for pair in manifest_pairs:
        pair_reasons = reasons[pair["pair_id"]]
        if not pair_reasons:
            continue
        selected_rows.append(
            {
                "pair_id": pair["pair_id"],
                "source_d4_canonical_hash": pair["source_d4_canonical_hash"],
                "treatment_d4_canonical_hash": pair[
                    "treatment_d4_canonical_hash"
                ],
                "vector_band": pair["vector_band"],
                "stratum_id": pair["stratum_id"],
                "reasons": sorted(pair_reasons, key=reason_rank.__getitem__),
            }
        )
    if exact_censored:
        disposition = "EXACT_ONLY_CENSORED"
    elif any_node_censor or any_direction_mismatch:
        disposition = "INCONCLUSIVE_STRONG_EVIDENCE"
    else:
        disposition = "COMPLETE"
    return {
        "version": "two-runner-v1-final-inspection-v1",
        "disposition": disposition,
        "reason_order": list(_FINAL_INSPECTION_REASON_ORDER),
        "pools": pool_evidence,
        "selected": selected_rows,
    }


def validate_two_runner_inspection(
    inspection: Mapping[str, Any],
    pair_records: Sequence[Mapping[str, Any]],
    *,
    manifest_pairs: Sequence[Mapping[str, Any]],
    exact_censored: bool = False,
) -> Dict[str, Any]:
    rebuilt = build_two_runner_inspection(
        pair_records,
        manifest_pairs=manifest_pairs,
        exact_censored=exact_censored,
    )
    if _canonical_bytes(inspection) != _canonical_bytes(rebuilt):
        raise ValueError("two-runner final inspection does not reconstruct")
    return _copy(inspection, "two-runner final inspection")


def build_two_runner_depth5_result(
    manifest_or_pairs: Any,
    exact_result: Mapping[str, Any],
    profile_slots: Sequence[Mapping[str, Any]],
    *,
    manifest_validator: Optional[Callable[[Any], Any]] = None,
    expected_pair_count: int = TWO_RUNNER_PAIR_COUNT,
    seeds: Sequence[int] = TWO_RUNNER_SEEDS,
    depth: int = TWO_RUNNER_DEPTH,
    max_nodes: int = TWO_RUNNER_MAX_NODES,
    gates: PlayGates = PlayGates(),
) -> Dict[str, Any]:
    """Validate fixed strong slots and rebuild all depth-5 conclusions."""

    depth = _strict_int(depth, "depth", minimum=1)
    max_nodes = _strict_int(max_nodes, "max_nodes", minimum=1)
    seed_tuple = _validate_seed_sequence(seeds, "two-runner depth-5")
    if not isinstance(gates, PlayGates):
        raise ValueError("gates must be PlayGates")
    pairs, manifest_digest, manifest_id = _manifest_pairs(
        manifest_or_pairs,
        manifest_validator=manifest_validator,
        expected_pair_count=expected_pair_count,
    )
    exact = validate_two_runner_exact_result(
        exact_result,
        manifest_or_pairs,
        manifest_validator=manifest_validator,
        expected_pair_count=expected_pair_count,
        max_states=TWO_RUNNER_EXACT_MAX_STATES,
    )
    if exact["aggregate"]["exact_censored_count"]:
        raise ValueError("two-runner depth-5 stage is blocked by exact censoring")
    schedule = _schedule_from_pairs(pairs)
    if not isinstance(profile_slots, (list, tuple)) or len(profile_slots) != len(
        schedule
    ):
        raise ValueError("two-runner profile slots must cover the full fixed schedule")

    normalized_slots = []
    by_pair: Dict[int, Dict[str, Any]] = {
        index: {} for index in range(expected_pair_count)
    }
    exact_by_id = {record["pair_id"]: record for record in exact["pairs"]}
    for expected, raw_slot in zip(schedule, profile_slots):
        pair = pairs[expected["pair_index"]]
        slot = _normalize_profile_slot(
            pair,
            expected,
            raw_slot,
            seeds=seed_tuple,
            depth=depth,
            max_nodes=max_nodes,
        )
        normalized_slots.append(slot)
        side = expected["side"].lower()
        definition = parse_definition(pair["{}_definition".format(side)])
        exact_side = exact_by_id[pair["pair_id"]]["{}_exact".format(side)]
        by_pair[pair["pair_index"]][side] = _profile_assessment(
            definition, slot, exact_side, gates=gates
        )

    records = []
    for pair in pairs:
        exact_pair = exact_by_id[pair["pair_id"]]
        source_profile = by_pair[pair["pair_index"]]["source"]
        treatment_profile = by_pair[pair["pair_index"]]["treatment"]
        node_censored = bool(
            source_profile["status"] != "COMPLETED"
            or treatment_profile["status"] != "COMPLETED"
        )
        direction_mismatch = bool(
            source_profile["direction"]["direction_match"] is False
            or treatment_profile["direction"]["direction_match"] is False
        )
        same_game_engagement = treatment_profile["same_game_engagement"]
        treatment_failures = set(treatment_profile["failure_codes"] or [])
        strong_frontier = bool(
            not node_censored
            and source_profile["direction"]["direction_match"] is True
            and treatment_profile["direction"]["direction_match"] is True
            and not treatment_failures.intersection(_SHAPE_FAILURES)
            and same_game_engagement is True
        )
        candidate = bool(
            strong_frontier
            and not treatment_failures.intersection(_DOMINANCE_FAILURES)
        )
        records.append(
            {
                "pair_index": pair["pair_index"],
                "pair_id": pair["pair_id"],
                "source_case_id": pair["source_case_id"],
                "stratum": pair["stratum"],
                "stratum_id": pair["stratum_id"],
                "structural_cell": pair["structural_cell"],
                "vector_band": pair["vector_band"],
                "selection_rank": pair["selection_rank"],
                "piece_multiplicity_delta": pair["piece_multiplicity_delta"],
                "source_definition_hash": pair["source_definition_hash"],
                "source_d4_canonical_hash": pair["source_d4_canonical_hash"],
                "treatment_definition_hash": pair["treatment_definition_hash"],
                "treatment_d4_canonical_hash": pair[
                    "treatment_d4_canonical_hash"
                ],
                "source_exact": exact_pair["source_exact"],
                "treatment_exact": exact_pair["treatment_exact"],
                "outcome_comparison": exact_pair["outcome_comparison"],
                "containment_response": exact_pair["containment_response"],
                "exact_engagement_response": exact_pair[
                    "exact_engagement_response"
                ],
                "source_profile": source_profile,
                "treatment_profile": treatment_profile,
                "node_censored": node_censored,
                "direction_mismatch": direction_mismatch,
                "treatment_same_game_engagement": same_game_engagement,
                "treatment_exact_forced_result": exact_pair["treatment_exact"][
                    "result"
                ]["forced_result"],
                "strong_frontier": strong_frontier,
                "candidate_shaped": candidate,
            }
        )

    raw_assessments = exact["aggregate"]["raw_assessments"]
    assessments = assess_two_runner_pairs(records, raw_assessments)
    inspection = build_two_runner_inspection(
        records, manifest_pairs=pairs, exact_censored=False
    )
    source_seconds = sum(
        slot["elapsed_seconds"] for slot in normalized_slots[:expected_pair_count]
    )
    treatment_seconds = sum(
        slot["elapsed_seconds"] for slot in normalized_slots[expected_pair_count:]
    )
    node_totals = _profile_node_totals(normalized_slots)
    return {
        "protocol_id": TWO_RUNNER_DEPTH5_PROTOCOL_ID,
        "manifest_id": manifest_id,
        "manifest_digest": manifest_digest,
        "exact_result_digest": hashlib.sha256(
            _canonical_bytes(_timing_free_result(exact))
        ).hexdigest(),
        "configuration": {
            "pair_count": expected_pair_count,
            "depth": depth,
            "seeds": list(seed_tuple),
            "max_nodes_per_definition": max_nodes,
            "schedule": "SOURCE_THEN_TREATMENT",
            "play_gates": asdict(gates),
        },
        "schedule": schedule,
        "slots": normalized_slots,
        "pairs": records,
        "aggregate": {
            "profile_attempted": len(normalized_slots),
            "profile_completed": sum(
                slot["status"] == "COMPLETED" for slot in normalized_slots
            ),
            "node_censored": sum(
                slot["status"] == "INCOMPLETE_NODE_CENSOR"
                for slot in normalized_slots
            ),
            "expanded_nodes_total": node_totals["expanded_nodes_total"],
            "completed_game_nodes_total": node_totals["completed_game_nodes"],
            "incomplete_attempt_nodes_total": node_totals[
                "incomplete_attempt_nodes"
            ],
            "source_evidence_digest": _profile_slots_digest(
                _SOURCE_DEPTH5_DOMAIN,
                normalized_slots[:expected_pair_count],
            ),
            "treatment_evidence_digest": _profile_slots_digest(
                _TREATMENT_DEPTH5_DOMAIN,
                normalized_slots[expected_pair_count:],
            ),
            "treatment_same_game_engagement_count": sum(
                record["treatment_same_game_engagement"] is True
                for record in records
            ),
            "strong_frontier_count": sum(
                record["strong_frontier"] for record in records
            ),
            "candidate_shaped_count": sum(
                record["candidate_shaped"] for record in records
            ),
            "descriptive_profiles": _descriptive_profile_aggregate(
                normalized_slots
            ),
            "breakdowns": _depth_breakdowns(records, normalized_slots),
            "raw_assessments": _copy(raw_assessments, "raw assessments"),
            "assessments": assessments,
        },
        "inspection": inspection,
        "timing": {
            "source_seconds": source_seconds,
            "treatment_seconds": treatment_seconds,
            "total_seconds": source_seconds + treatment_seconds,
        },
    }


def evaluate_two_runner_depth5(
    manifest_or_pairs: Any,
    exact_result: Mapping[str, Any],
    *,
    manifest_validator: Optional[Callable[[Any], Any]] = None,
    expected_pair_count: int = TWO_RUNNER_PAIR_COUNT,
    seeds: Sequence[int] = TWO_RUNNER_SEEDS,
    depth: int = TWO_RUNNER_DEPTH,
    max_nodes: int = TWO_RUNNER_MAX_NODES,
    gates: PlayGates = PlayGates(),
    agent_factory: Optional[Callable[..., Any]] = None,
    clock: Callable[[], float] = time.perf_counter,
) -> Dict[str, Any]:
    """Execute, seal, and validate the fixed all-case strong schedule."""

    depth = _strict_int(depth, "depth", minimum=1)
    max_nodes = _strict_int(max_nodes, "max_nodes", minimum=1)
    seed_tuple = _validate_seed_sequence(seeds, "two-runner depth-5")
    if not isinstance(gates, PlayGates):
        raise ValueError("gates must be PlayGates")
    exact = validate_two_runner_exact_result(
        exact_result,
        manifest_or_pairs,
        manifest_validator=manifest_validator,
        expected_pair_count=expected_pair_count,
        max_states=TWO_RUNNER_EXACT_MAX_STATES,
    )
    if exact["aggregate"]["exact_censored_count"]:
        raise ValueError("two-runner depth-5 stage is blocked by exact censoring")
    pairs, _, _ = _manifest_pairs(
        manifest_or_pairs,
        manifest_validator=manifest_validator,
        expected_pair_count=expected_pair_count,
    )
    schedule = _schedule_from_pairs(pairs)
    source_slots = []
    for entry in schedule[:expected_pair_count]:
        pair = pairs[entry["pair_index"]]
        source = parse_definition(pair["source_definition"])
        started = clock()
        slot = _execute_profile(
            source,
            source,
            entry,
            seeds=seed_tuple,
            depth=depth,
            max_nodes=max_nodes,
            agent_factory=agent_factory,
        )
        source_slots.append(
            {
                **slot,
                "elapsed_seconds": _elapsed_seconds(
                    clock() - started, "depth-5 elapsed_seconds"
                ),
            }
        )
    sealed_source_slots = [
        _normalize_profile_slot(
            pairs[entry["pair_index"]],
            entry,
            slot,
            seeds=seed_tuple,
            depth=depth,
            max_nodes=max_nodes,
        )
        for entry, slot in zip(schedule[:expected_pair_count], source_slots)
    ]
    source_seal = _profile_slots_digest(_SOURCE_DEPTH5_DOMAIN, sealed_source_slots)
    slots = list(source_slots)

    for entry in schedule[expected_pair_count:]:
        pair = pairs[entry["pair_index"]]
        source = parse_definition(pair["source_definition"])
        treatment = parse_definition(pair["treatment_definition"])
        started = clock()
        slot = _execute_profile(
            source,
            treatment,
            entry,
            seeds=seed_tuple,
            depth=depth,
            max_nodes=max_nodes,
            agent_factory=agent_factory,
        )
        slots.append(
            {
                **slot,
                "elapsed_seconds": _elapsed_seconds(
                    clock() - started, "depth-5 elapsed_seconds"
                ),
            }
        )

    result = build_two_runner_depth5_result(
        manifest_or_pairs,
        exact,
        slots,
        manifest_validator=manifest_validator,
        expected_pair_count=expected_pair_count,
        seeds=seed_tuple,
        depth=depth,
        max_nodes=max_nodes,
        gates=gates,
    )
    if result["aggregate"]["source_evidence_digest"] != source_seal:
        raise ValueError("source depth-5 evidence changed after its phase seal")
    return result


def _validate_depth_timing_summary(
    timing_value: Any,
    slots: Sequence[Mapping[str, Any]],
    pair_count: int,
) -> Dict[str, float]:
    timing = _exact_keys(
        timing_value,
        ("source_seconds", "treatment_seconds", "total_seconds"),
        "two-runner depth-5 timing",
    )
    normalized = {
        field: _elapsed_seconds(timing[field], "depth-5 timing {}".format(field))
        for field in timing
    }
    source_seconds = sum(
        _elapsed_seconds(slot["elapsed_seconds"], "source slot timing")
        for slot in slots[:pair_count]
    )
    treatment_seconds = sum(
        _elapsed_seconds(slot["elapsed_seconds"], "treatment slot timing")
        for slot in slots[pair_count:]
    )
    expected = {
        "source_seconds": source_seconds,
        "treatment_seconds": treatment_seconds,
        "total_seconds": source_seconds + treatment_seconds,
    }
    if normalized != expected:
        raise ValueError("two-runner depth-5 timing does not match slot timings")
    return normalized


def validate_two_runner_depth5_result(
    result: Mapping[str, Any],
    manifest_or_pairs: Any,
    exact_result: Mapping[str, Any],
    *,
    manifest_validator: Optional[Callable[[Any], Any]] = None,
    expected_pair_count: int = TWO_RUNNER_PAIR_COUNT,
    seeds: Sequence[int] = TWO_RUNNER_SEEDS,
    depth: int = TWO_RUNNER_DEPTH,
    max_nodes: int = TWO_RUNNER_MAX_NODES,
    gates: PlayGates = PlayGates(),
) -> Dict[str, Any]:
    """Reconstruct a depth-5 artifact from its exact input and raw slots."""

    value = _exact_keys(
        result,
        (
            "protocol_id",
            "manifest_id",
            "manifest_digest",
            "exact_result_digest",
            "configuration",
            "schedule",
            "slots",
            "pairs",
            "aggregate",
            "inspection",
            "timing",
        ),
        "two-runner depth-5 result",
    )
    rebuilt = build_two_runner_depth5_result(
        manifest_or_pairs,
        exact_result,
        value["slots"],
        manifest_validator=manifest_validator,
        expected_pair_count=expected_pair_count,
        seeds=seeds,
        depth=depth,
        max_nodes=max_nodes,
        gates=gates,
    )
    _validate_depth_timing_summary(
        value["timing"], value["slots"], expected_pair_count
    )
    if _canonical_bytes(_timing_free_result(value)) != _canonical_bytes(
        _timing_free_result(rebuilt)
    ):
        raise ValueError("two-runner depth-5 result does not reconstruct")
    return _copy(value, "two-runner depth-5 result")


__all__ = (
    "TWO_RUNNER_EXACT_PROTOCOL_ID",
    "TWO_RUNNER_DEPTH5_PROTOCOL_ID",
    "TWO_RUNNER_DEPTH",
    "TWO_RUNNER_MAX_NODES",
    "TWO_RUNNER_SEEDS",
    "TWO_RUNNER_EXACT_MAX_STATES",
    "TWO_RUNNER_PAIR_COUNT",
    "TWO_RUNNER_SOURCE_STATE_BOUND",
    "TWO_RUNNER_TREATMENT_STATE_BOUND",
    "two_runner_schedule",
    "derive_two_runner_lineage_trace",
    "validate_two_runner_lineage_trace",
    "derive_two_runner_trace",
    "assess_two_runner_response",
    "build_two_runner_exact_inspection",
    "validate_two_runner_exact_inspection",
    "build_two_runner_exact_result",
    "evaluate_two_runner_exact",
    "validate_two_runner_exact_result",
    "build_two_runner_profile_evidence",
    "build_censored_two_runner_profile_evidence",
    "build_two_runner_censored_profile_evidence",
    "validate_two_runner_profile_evidence",
    "two_runner_direction",
    "assess_two_runner_pairs",
    "build_two_runner_inspection",
    "validate_two_runner_inspection",
    "build_two_runner_depth5_result",
    "evaluate_two_runner_depth5",
    "validate_two_runner_depth5_result",
)
