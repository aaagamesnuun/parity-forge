"""Pure evaluators for the fixed Plan 0009 capture-boundary replication.

The module deliberately contains no filesystem, Git, reservation, or one-shot
runner logic.  A runner may either call the two ``evaluate_*`` entry points or
execute the frozen schedules itself and pass the resulting slots to the matching
``build_*_result`` function.  Public validators rebuild every derived field from
the manifest definitions and the stored action/PV evidence.
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

from .agents import AgentIdentity, MinimaxAgent, SearchBudgetExceeded
from .audit import sampled_direction
from .batch import PlayGates
from .capture import (
    CAPTURE_STATE_BOUND,
    build_capture_profile_evidence,
    build_censored_capture_profile_evidence,
    derive_capture_trace,
    normalize_capture_pv,
    validate_capture_monotonicity,
    validate_capture_profile_evidence,
    validate_capture_searched_states,
)
from .dsl import (
    ActionKind,
    GameDefinition,
    GoalKind,
    Player,
    definition_hash,
    parse_definition,
)
from .engine import action_from_dict, apply_action, initial_state, legal_actions
from .play import GameRecord
from .solver import SolveBudgetExceeded, solve_game
from .symmetry import d4_canonical_hash


CAPTURE_BOUNDARY_PAIR_COUNT = 64
CAPTURE_BOUNDARY_EXACT_MAX_STATES = 100_000
CAPTURE_BOUNDARY_DEPTH = 5
CAPTURE_BOUNDARY_MAX_NODES = 5_000_000
CAPTURE_BOUNDARY_SEEDS = tuple(range(30))
CAPTURE_BOUNDARY_EXACT_PROTOCOL_ID = "capture-boundary-v1-paired-exact"
CAPTURE_BOUNDARY_DEPTH5_PROTOCOL_ID = "capture-boundary-v1-fixed-depth5"

_PROFILE_PREFIX = "minimax-v1-depth"
_CHANGE_DOMAIN = b"capture-boundary-v1-inspection-change-v1\0"
_CONTROL_DOMAIN = b"capture-boundary-v1-inspection-control-v1\0"
_SOURCE_EXACT_DOMAIN = b"capture-boundary-v1-source-exact-slots-v1\0"
_TREATMENT_EXACT_DOMAIN = b"capture-boundary-v1-treatment-exact-slots-v1\0"
_SOURCE_DEPTH5_DOMAIN = b"capture-boundary-v1-source-depth5-slots-v1\0"
_TREATMENT_DEPTH5_DOMAIN = b"capture-boundary-v1-treatment-depth5-slots-v1\0"
_INSPECTION_REASONS = (
    "EXACT_CENSOR",
    "NODE_CENSOR",
    "EXACT_HORIZON",
    "DIRECTION_MISMATCH",
    "A_FRONTIER",
    "CANDIDATE_SHAPED",
    "OUTCOME_CHANGE_SAMPLE",
    "OUTCOME_UNCHANGED_CONTROL",
    "STRATUM_FLOOR",
)
_VALUE_BY_RESULT = {"A_WIN": 1, "DRAW": 0, "B_WIN": -1}
_SHAPE_FAILURES = frozenset(("EXCESSIVE_DRAWS", "TOO_SHORT", "TOO_LONG"))
_DOMINANCE_FAILURES = frozenset(("A_DOMINANT", "B_DOMINANT"))


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _copy(value: Any, label: str = "value") -> Any:
    try:
        return json.loads(_canonical_bytes(value))
    except (TypeError, ValueError) as error:
        raise ValueError("{} must be canonical-JSON compatible".format(label)) from error


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


def _timing_free_result(value: Mapping[str, Any]) -> Dict[str, Any]:
    projection = _copy(value, "result timing-free projection")
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
    label: str,
) -> Dict[str, float]:
    timing = _exact_keys(
        timing_value,
        ("source_seconds", "treatment_seconds", "total_seconds"),
        label,
    )
    normalized = {
        field: _elapsed_seconds(timing[field], "{} {}".format(label, field))
        for field in timing
    }
    source_seconds = sum(slot["elapsed_seconds"] for slot in slots[:pair_count])
    treatment_seconds = sum(slot["elapsed_seconds"] for slot in slots[pair_count:])
    if normalized != {
        "source_seconds": source_seconds,
        "treatment_seconds": treatment_seconds,
        "total_seconds": source_seconds + treatment_seconds,
    }:
        raise ValueError("{} does not match slot timings".format(label))
    return normalized


def _nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("{} must be a nonempty string".format(label))
    return value


def _sha256(value: Any, label: str) -> str:
    value = _nonempty_string(value, label)
    if len(value) != 64:
        raise ValueError("{} must be a SHA-256 hex digest".format(label))
    try:
        int(value, 16)
    except ValueError as error:
        raise ValueError("{} must be a SHA-256 hex digest".format(label)) from error
    if value != value.lower():
        raise ValueError("{} must use canonical lowercase hexadecimal".format(label))
    return value


def _side_field(pair: Mapping[str, Any], side: str, field: str) -> Any:
    flat = "{}_{}".format(side, field)
    if flat in pair:
        return pair[flat]
    nested = pair.get(side)
    if isinstance(nested, Mapping) and field in nested:
        return nested[field]
    aliases = {
        "definition_hash": ("hash", "game_hash"),
        "d4_canonical_hash": ("d4_hash", "orbit_hash"),
    }
    if isinstance(nested, Mapping):
        for alias in aliases.get(field, ()):
            if alias in nested:
                return nested[alias]
    return None


def _derived_stratum(definition: GameDefinition) -> Dict[str, Any]:
    role_a = definition.role(Player.A)
    role_b = definition.role(Player.B)
    if role_b.goal.edge is None or len(definition.initial_pieces) != 1:
        raise ValueError("capture-boundary definition is outside the frozen family")
    row, column = definition.initial_pieces[0].position
    if row not in (0, 2) and column not in (0, 2):
        raise ValueError("capture-boundary runner start must lie on the boundary")
    corner = row in (0, 2) and column in (0, 2)
    return {
        "first_player": definition.first_player.value,
        "goal_axis_relation": (
            "ALIGNED" if role_b.goal.edge in role_a.goal.edges else "ORTHOGONAL"
        ),
        "runner_start_class": "CORNER" if corner else "EDGE_MIDPOINT",
        "vector_count": len(role_b.action.vectors),
    }


def _stratum_id(stratum: Mapping[str, Any]) -> str:
    expected = {
        "first_player",
        "goal_axis_relation",
        "runner_start_class",
        "vector_count",
    }
    projection = {key: stratum.get(key) for key in expected}
    if (
        projection["first_player"] not in ("A", "B")
        or projection["goal_axis_relation"] not in ("ALIGNED", "ORTHOGONAL")
        or projection["runner_start_class"] not in ("CORNER", "EDGE_MIDPOINT")
        or projection["vector_count"] not in (3, 4)
    ):
        raise ValueError("capture-boundary stratum is malformed")
    return "f{}-{}-{}-p18-v{}".format(
        projection["first_player"],
        projection["goal_axis_relation"].lower(),
        projection["runner_start_class"].lower(),
        projection["vector_count"],
    )


def _structural_cell(stratum: Mapping[str, Any]) -> str:
    return "f{}-{}-{}".format(
        stratum["first_player"],
        stratum["goal_axis_relation"].lower(),
        stratum["runner_start_class"].lower(),
    )


def _validate_pair_semantics(source: GameDefinition, treatment: GameDefinition) -> None:
    source_a = source.role(Player.A)
    source_b = source.role(Player.B)
    if (
        source.schema_version != 1
        or treatment.schema_version != 3
        or source.board_size != 3
        or treatment.board_size != 3
        or source.max_plies != 18
        or treatment.max_plies != 18
        or source_a.action.kind is not ActionKind.PLACE
        or source_a.goal.kind is not GoalKind.CONNECT_EDGES
        or source_a.action.piece != source_a.goal.piece
        or source_b.action.kind is not ActionKind.MOVE
        or source_b.goal.kind is not GoalKind.REACH_EDGE
        or source_b.action.piece != source_b.goal.piece
        or source_b.action.piece != "runner"
        or treatment.role(Player.B).action.kind is not ActionKind.MOVE_CAPTURE
    ):
        raise ValueError("capture-boundary pair is outside the frozen schema family")
    vector_count = len(source.role(Player.B).action.vectors)
    if vector_count not in (3, 4):
        raise ValueError("capture-boundary pair must have exactly three or four vectors")
    if (
        len(source.initial_pieces) != 1
        or source.initial_pieces[0].owner is not Player.B
        or source.initial_pieces[0].piece != source_b.action.piece
    ):
        raise ValueError("capture-boundary source must contain exactly one B runner")
    reverted = treatment.to_dict()
    reverted["schema_version"] = 1
    reverted["roles"]["B"]["action"]["kind"] = "MOVE"
    if _canonical_bytes(reverted) != _canonical_bytes(source.to_dict()):
        raise ValueError("capture-boundary treatment changes more than schema/action kind")


def _normalize_pair(raw: Any, index: int) -> Dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError("capture-boundary pairs must be objects")
    pair_id = _nonempty_string(raw.get("pair_id"), "pair_id")
    source_case_id = raw.get("source_case_id", raw.get("case_id"))
    source_case_id = _nonempty_string(source_case_id, "source_case_id")
    source_raw = _side_field(raw, "source", "definition")
    treatment_raw = _side_field(raw, "treatment", "definition")
    if not isinstance(source_raw, Mapping) or not isinstance(treatment_raw, Mapping):
        raise ValueError("capture-boundary pair is missing source/treatment definitions")
    source = parse_definition(source_raw)
    treatment = parse_definition(treatment_raw)
    _validate_pair_semantics(source, treatment)

    source_hash = definition_hash(source)
    treatment_hash = definition_hash(treatment)
    source_d4 = d4_canonical_hash(source)
    treatment_d4 = d4_canonical_hash(treatment)
    supplied = (
        (_side_field(raw, "source", "definition_hash"), source_hash, "source hash"),
        (_side_field(raw, "treatment", "definition_hash"), treatment_hash, "treatment hash"),
        (_side_field(raw, "source", "d4_canonical_hash"), source_d4, "source D4 hash"),
        (_side_field(raw, "treatment", "d4_canonical_hash"), treatment_d4, "treatment D4 hash"),
    )
    for observed, expected, label in supplied:
        if observed is not None and _sha256(observed, label) != expected:
            raise ValueError("{} does not match definition".format(label))

    expected_stratum = _derived_stratum(source)
    raw_stratum = raw.get("stratum")
    if raw_stratum is None:
        stratum = expected_stratum
    elif not isinstance(raw_stratum, Mapping):
        raise ValueError("capture-boundary stratum must be an object")
    else:
        # Tolerate selection-manifest metadata beyond the four frozen dimensions.
        stratum = {key: raw_stratum.get(key) for key in expected_stratum}
        if stratum != expected_stratum:
            raise ValueError("capture-boundary stratum disagrees with definition")
    vector_count = raw.get("vector_count", expected_stratum["vector_count"])
    if type(vector_count) is not int or vector_count != expected_stratum["vector_count"]:
        raise ValueError("capture-boundary vector_count mismatch")
    rank = raw.get("selection_rank")
    _strict_int(rank, "selection_rank")
    score = raw.get("selection_score")
    if score is not None:
        _sha256(score, "selection_score")

    return {
        "pair_index": index,
        "pair_id": pair_id,
        "source_case_id": source_case_id,
        "stratum": _copy(stratum, "stratum"),
        "stratum_id": _stratum_id(stratum),
        "structural_cell": _structural_cell(stratum),
        "vector_count": vector_count,
        "selection_rank": rank,
        "selection_score": score,
        "source_definition": source.to_dict(),
        "source_definition_hash": source_hash,
        "source_d4_canonical_hash": source_d4,
        "treatment_definition": treatment.to_dict(),
        "treatment_definition_hash": treatment_hash,
        "treatment_d4_canonical_hash": treatment_d4,
    }


def _manifest_pairs(
    manifest_or_pairs: Any,
    *,
    manifest_validator: Optional[Callable[[Any], Any]],
    expected_pair_count: int,
) -> Tuple[Tuple[Dict[str, Any], ...], str, Optional[str]]:
    _strict_int(expected_pair_count, "expected_pair_count", minimum=1)
    original = manifest_or_pairs
    validated = manifest_validator(original) if manifest_validator is not None else original
    candidate = validated if validated is not None else original
    if isinstance(candidate, Mapping):
        raw_pairs = candidate.get("pairs")
    else:
        raw_pairs = candidate
    if not isinstance(raw_pairs, (list, tuple)):
        # Some validators return a wrapper while leaving normalized pairs on input.
        raw_pairs = original.get("pairs") if isinstance(original, Mapping) else None
    if not isinstance(raw_pairs, (list, tuple)):
        raise ValueError("capture-boundary manifest must expose a pairs array")
    if len(raw_pairs) != expected_pair_count:
        raise ValueError(
            "capture-boundary pair count must be {}".format(expected_pair_count)
        )
    pairs = tuple(_normalize_pair(pair, index) for index, pair in enumerate(raw_pairs))
    for field in ("pair_id", "source_d4_canonical_hash", "treatment_d4_canonical_hash"):
        values = [pair[field] for pair in pairs]
        if len(set(values)) != len(values):
            raise ValueError("capture-boundary {} values must be unique".format(field))
    manifest_id = original.get("manifest_id") if isinstance(original, Mapping) else None
    digest_source = original if isinstance(original, Mapping) else list(raw_pairs)
    digest = hashlib.sha256(_canonical_bytes(digest_source)).hexdigest()
    return pairs, digest, manifest_id if isinstance(manifest_id, str) else None


def capture_boundary_schedule(
    manifest_or_pairs: Any,
    *,
    manifest_validator: Optional[Callable[[Any], Any]] = None,
    expected_pair_count: int = CAPTURE_BOUNDARY_PAIR_COUNT,
) -> list[Dict[str, Any]]:
    """Return the frozen source-all-then-treatment-all schedule."""

    pairs, _, _ = _manifest_pairs(
        manifest_or_pairs,
        manifest_validator=manifest_validator,
        expected_pair_count=expected_pair_count,
    )
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


def _exact_payload_from_solve(solved: Any) -> Dict[str, Any]:
    result = solved.to_dict() if hasattr(solved, "to_dict") else solved
    if not isinstance(result, Mapping):
        raise ValueError("exact solver must return SolveResult-compatible evidence")
    return {
        "status": "COMPLETED",
        "result": _copy(result, "exact result"),
        "budget_observation": None,
    }


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
        "exact schedule slot",
    )
    for field in (
        "schedule_index",
        "pair_index",
        "side",
        "pair_id",
        "definition_hash",
    ):
        if slot[field] != expected[field]:
            raise ValueError("exact schedule identity/order mismatch")
    side = expected["side"]
    definition = parse_definition(pair["{}_definition".format(side.lower())])
    exact, capture = _normalize_exact(
        definition, slot["exact"], max_states=max_states, side=side
    )
    return (
        {
            **expected,
            "exact": exact,
            "elapsed_seconds": _elapsed_seconds(
                slot["elapsed_seconds"], "exact slot elapsed_seconds"
            ),
        },
        capture,
    )


def _exact_slots_digest(domain: bytes, slots: Sequence[Mapping[str, Any]]) -> str:
    return hashlib.sha256(
        domain
        + _canonical_bytes(
            [
                {key: value for key, value in slot.items() if key != "elapsed_seconds"}
                for slot in slots
            ]
        )
    ).hexdigest()


def _normalize_exact(
    definition: GameDefinition,
    value: Any,
    *,
    max_states: int,
    side: str,
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    exact = _exact_keys(
        value,
        ("status", "result", "budget_observation"),
        "exact slot evidence",
    )
    status = exact["status"]
    if status == "CENSORED_STATE_BUDGET":
        budget = _exact_keys(
            exact["budget_observation"],
            ("searched_states", "max_states"),
            "exact censor observation",
        )
        if (
            exact["result"] is not None
            or type(budget["searched_states"]) is not int
            or type(budget["max_states"]) is not int
            or budget["searched_states"] != max_states
            or budget["max_states"] != max_states
        ):
            raise ValueError("exact censor evidence is malformed")
        return _copy(exact, "exact censor"), None
    if status != "COMPLETED" or exact["budget_observation"] is not None:
        raise ValueError("exact slot has an unknown or inconsistent status")
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
        "exact result",
    )
    forced = result["forced_result"]
    if (
        forced not in _VALUE_BY_RESULT
        or type(result["value_for_a"]) is not int
        or result["value_for_a"] != _VALUE_BY_RESULT[forced]
    ):
        raise ValueError("exact forced-result/value encoding mismatch")
    validate_capture_searched_states(result["searched_states"])
    if result["searched_states"] > max_states:
        raise ValueError("completed exact result exceeds its execution cap")
    _strict_int(result["cache_hits"], "exact cache_hits")
    pv = result["principal_variation"]
    if (
        not isinstance(pv, list)
        or type(result["principal_variation_plies"]) is not int
        or result["principal_variation_plies"] != len(pv)
    ):
        raise ValueError("exact principal variation length mismatch")
    trace = derive_capture_trace(definition, pv)
    expected_winner = {"A_WIN": "A", "B_WIN": "B", "DRAW": None}[forced]
    if (
        trace["terminal_outcome"]["winner"] != expected_winner
        or trace["terminal_outcome"]["reason"] != result["terminal_reason"]
        or trace["terminal_ply"] != result["principal_variation_plies"]
    ):
        raise ValueError("exact principal variation terminal claim does not replay")
    if side == "SOURCE" and result["terminal_reason"] == "PLY_LIMIT":
        raise ValueError("schema-v1 source ended at PLY_LIMIT")
    capture = {
        key: trace[key]
        for key in (
            "capture_count",
            "first_capture_ply",
            "capture_plies",
            "capture_cells",
            "repeated_position",
            "replacement_recapture",
            "capture_replace_cycle",
        )
    }
    return _copy(exact, "exact evidence"), capture


def _response_assessment(
    records: Sequence[Mapping[str, Any]], field: str, *, exact_censored: bool
) -> Dict[str, Any]:
    selected = [record for record in records if record.get(field) is True]
    strata = {record["stratum_id"] for record in selected}
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


def assess_capture_boundary_response(
    pair_records: Sequence[Mapping[str, Any]], response_field: str
) -> Dict[str, Any]:
    """Public threshold helper: >=4 responses across >=2 full strata."""

    if response_field not in ("primary_response", "realized_response"):
        raise ValueError("unknown capture-boundary response field")
    return _response_assessment(
        pair_records, response_field, exact_censored=False
    )


def _cycling_assessment(
    records: Sequence[Mapping[str, Any]], *, exact_censored: bool
) -> Dict[str, Any]:
    eligible = []
    for record in records:
        source = record["source_exact"]
        treatment = record["treatment_exact"]
        if source["status"] != "COMPLETED" or treatment["status"] != "COMPLETED":
            continue
        source_result = source["result"]
        treatment_result = treatment["result"]
        if (
            source_result["forced_result"] == "A_WIN"
            and source_result["terminal_reason"] == "NO_LEGAL_ACTION"
            and source_result["value_for_a"] != treatment_result["value_for_a"]
        ):
            eligible.append(record)
    horizon = sum(record["exact_horizon"] for record in eligible)
    non_horizon_b = sum(
        not record["exact_horizon"]
        and record["treatment_exact"]["result"]["forced_result"] == "B_WIN"
        for record in eligible
    )
    if exact_censored:
        status = "INCONCLUSIVE_EXACT_CENSOR"
    else:
        status = "DOMINANT" if horizon > non_horizon_b else "NOT_DOMINANT"
    return {
        "status": status,
        "eligible_count": len(eligible),
        "exact_horizon_count": horizon,
        "non_horizon_b_win_count": non_horizon_b,
    }


def _integer_histogram(values: Iterable[int]) -> Dict[str, int]:
    histogram = Counter(values)
    return {str(value): histogram[value] for value in sorted(histogram)}


def _first_capture_ply_histogram(
    values: Iterable[Optional[int]],
) -> Dict[str, int]:
    """Use the literal JSON-object key ``null`` for a missing first capture."""

    histogram = Counter(values)
    result = {"null": histogram.get(None, 0)}
    result.update(
        {
            str(value): histogram[value]
            for value in sorted(key for key in histogram if key is not None)
        }
    )
    return result


def _exact_side_breakdown(
    records: Sequence[Mapping[str, Any]], side: str
) -> Dict[str, Any]:
    exact_key = "{}_exact".format(side)
    capture_key = "{}_pv_capture".format(side)
    completed = [record for record in records if record[exact_key]["status"] == "COMPLETED"]
    forced = Counter(
        record[exact_key]["result"]["forced_result"] for record in completed
    )
    terminal = Counter(
        record[exact_key]["result"]["terminal_reason"] for record in completed
    )
    captures = [record[capture_key] for record in completed]
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
        "pv_capture_count": sum(
            capture["capture_count"] for capture in captures
        ),
        "pv_with_capture_count": sum(
            capture["capture_count"] > 0 for capture in captures
        ),
        "pv_capture_count_histogram": _integer_histogram(
            capture["capture_count"] for capture in captures
        ),
        "first_capture_ply_histogram": _first_capture_ply_histogram(
            capture["first_capture_ply"] for capture in captures
        ),
        "repeated_position_count": sum(
            capture["repeated_position"] for capture in captures
        ),
        "replacement_recapture_count": sum(
            capture["replacement_recapture"] for capture in captures
        ),
        "capture_replace_cycle_count": sum(
            capture["capture_replace_cycle"] for capture in captures
        ),
    }


def _exact_group_summary(records: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    transitions = Counter()
    terminal_transitions = Counter()
    normalized_prefixes = Counter()
    pv_length_deltas = Counter()
    value_changed_count = 0
    capture_threat_without_pv_capture_count = 0
    for record in records:
        source = record["source_exact"]
        treatment = record["treatment_exact"]
        if source["status"] == "COMPLETED" and treatment["status"] == "COMPLETED":
            transitions[
                "{}->{}".format(
                    source["result"]["forced_result"],
                    treatment["result"]["forced_result"],
                )
            ] += 1
            terminal_transitions[
                "{}->{}".format(
                    source["result"]["terminal_reason"],
                    treatment["result"]["terminal_reason"],
                )
            ] += 1
            normalization = record["normalized_pv"]
            normalized_prefixes[normalization["common_prefix_plies"]] += 1
            pv_length_deltas[
                normalization["principal_variation_plies_delta"]
            ] += 1
            value_changed = record["monotonicity"]["value_changed"]
            value_changed_count += value_changed
            capture_threat_without_pv_capture_count += bool(
                value_changed
                and record["treatment_pv_capture"]["capture_count"] == 0
            )
    return {
        "pair_count": len(records),
        "paired_completed_count": sum(
            record["paired_status"] == "COMPLETED" for record in records
        ),
        "paired_censored_count": sum(
            record["paired_status"] != "COMPLETED" for record in records
        ),
        "source": _exact_side_breakdown(records, "source"),
        "treatment": _exact_side_breakdown(records, "treatment"),
        "forced_result_transitions": dict(sorted(transitions.items())),
        "terminal_reason_transitions": dict(sorted(terminal_transitions.items())),
        "normalized_pv_common_prefix_histogram": _integer_histogram(
            normalized_prefixes.elements()
        ),
        "principal_variation_plies_delta_histogram": _integer_histogram(
            pv_length_deltas.elements()
        ),
        "value_changed_count": value_changed_count,
        "capture_threat_without_pv_capture_count": (
            capture_threat_without_pv_capture_count
        ),
        "exact_horizon_count": sum(record["exact_horizon"] for record in records),
        "primary_response_count": sum(
            record["primary_response"] is True for record in records
        ),
        "realized_response_count": sum(
            record["realized_response"] is True for record in records
        ),
    }


def _exact_breakdowns(records: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    cells = sorted({record["structural_cell"] for record in records})
    return {
        "all": _exact_group_summary(records),
        "by_vector": {
            "v3": _exact_group_summary(
                [record for record in records if record["vector_count"] == 3]
            ),
            "v4": _exact_group_summary(
                [record for record in records if record["vector_count"] == 4]
            ),
        },
        "by_structural_cell": {
            cell: _exact_group_summary(
                [record for record in records if record["structural_cell"] == cell]
            )
            for cell in cells
        },
    }


def build_capture_boundary_exact_result(
    manifest_or_pairs: Any,
    exact_slots: Sequence[Mapping[str, Any]],
    *,
    manifest_validator: Optional[Callable[[Any], Any]] = None,
    expected_pair_count: int = CAPTURE_BOUNDARY_PAIR_COUNT,
    max_states: int = CAPTURE_BOUNDARY_EXACT_MAX_STATES,
) -> Dict[str, Any]:
    """Validate fixed exact slots and derive the complete raw result."""

    _strict_int(max_states, "max_states", minimum=1)
    pairs, manifest_digest, manifest_id = _manifest_pairs(
        manifest_or_pairs,
        manifest_validator=manifest_validator,
        expected_pair_count=expected_pair_count,
    )
    expected_schedule = capture_boundary_schedule(
        manifest_or_pairs,
        manifest_validator=manifest_validator,
        expected_pair_count=expected_pair_count,
    )
    if not isinstance(exact_slots, (list, tuple)) or len(exact_slots) != len(
        expected_schedule
    ):
        raise ValueError("exact slots must cover the full fixed schedule")
    normalized_slots = []
    by_pair: Dict[int, Dict[str, Any]] = {
        index: {} for index in range(expected_pair_count)
    }
    for expected, raw_slot in zip(expected_schedule, exact_slots):
        pair = pairs[expected["pair_index"]]
        normalized, capture = _normalize_exact_slot(
            pair, expected, raw_slot, max_states=max_states
        )
        normalized_slots.append(normalized)
        prefix = expected["side"].lower()
        exact = normalized["exact"]
        by_pair[pair["pair_index"]]["{}_exact".format(prefix)] = exact
        by_pair[pair["pair_index"]]["{}_pv_capture".format(prefix)] = capture

    records = []
    for pair in pairs:
        evidence = by_pair[pair["pair_index"]]
        source_exact = evidence["source_exact"]
        treatment_exact = evidence["treatment_exact"]
        complete = (
            source_exact["status"] == "COMPLETED"
            and treatment_exact["status"] == "COMPLETED"
        )
        exact_horizon = bool(
            treatment_exact["status"] == "COMPLETED"
            and treatment_exact["result"]["terminal_reason"] == "PLY_LIMIT"
        )
        if complete:
            monotonicity = validate_capture_monotonicity(source_exact, treatment_exact)
            normalized_pv = normalize_capture_pv(
                pair["source_definition"],
                source_exact["result"]["principal_variation"],
                pair["treatment_definition"],
                treatment_exact["result"]["principal_variation"],
            )
            primary = bool(
                source_exact["result"]["forced_result"] == "A_WIN"
                and source_exact["result"]["terminal_reason"] == "NO_LEGAL_ACTION"
                and not exact_horizon
                and treatment_exact["result"]["forced_result"] == "B_WIN"
                and treatment_exact["result"]["terminal_reason"] == "GOAL"
            )
            realized = bool(
                not exact_horizon
                and evidence["treatment_pv_capture"]["capture_count"] > 0
            )
        else:
            monotonicity = None
            normalized_pv = None
            primary = None
            realized = None
        records.append(
            {
                "pair_index": pair["pair_index"],
                "pair_id": pair["pair_id"],
                "source_case_id": pair["source_case_id"],
                "stratum": pair["stratum"],
                "stratum_id": pair["stratum_id"],
                "structural_cell": pair["structural_cell"],
                "vector_count": pair["vector_count"],
                "selection_rank": pair["selection_rank"],
                "source_definition_hash": pair["source_definition_hash"],
                "source_d4_canonical_hash": pair["source_d4_canonical_hash"],
                "treatment_definition_hash": pair["treatment_definition_hash"],
                "treatment_d4_canonical_hash": pair["treatment_d4_canonical_hash"],
                "source_exact": source_exact,
                "source_pv_capture": evidence["source_pv_capture"],
                "treatment_exact": treatment_exact,
                "treatment_pv_capture": evidence["treatment_pv_capture"],
                "paired_status": "COMPLETED" if complete else "INCOMPLETE_EXACT_CENSOR",
                "normalized_pv": normalized_pv,
                "monotonicity": monotonicity,
                "exact_horizon": exact_horizon,
                "primary_response": primary,
                "realized_response": realized,
            }
        )

    censored = [slot for slot in normalized_slots if slot["exact"]["status"] != "COMPLETED"]
    exact_censored = bool(censored)
    primary_assessment = _response_assessment(
        records, "primary_response", exact_censored=exact_censored
    )
    realized_assessment = _response_assessment(
        records, "realized_response", exact_censored=exact_censored
    )
    cycling = _cycling_assessment(records, exact_censored=exact_censored)
    raw_assessments = {
        "primary_response": primary_assessment,
        "realized_response": realized_assessment,
        "cycling_dominance": cycling,
        "boundary": {
            "status": "INCONCLUSIVE_EXACT_CENSOR" if exact_censored else "PENDING_DEPTH5"
        },
        "candidate_shape": {
            "status": "INCONCLUSIVE_EXACT_CENSOR" if exact_censored else "PENDING_DEPTH5"
        },
        "overall": {
            "status": "INCONCLUSIVE_EXACT_CENSOR" if exact_censored else "PENDING_DEPTH5"
        },
    }
    source_histogram: Counter[str] = Counter()
    treatment_histogram: Counter[str] = Counter()
    for record in records:
        if record["source_exact"]["status"] == "COMPLETED":
            source_histogram[record["source_exact"]["result"]["forced_result"]] += 1
        if record["treatment_exact"]["status"] == "COMPLETED":
            treatment_histogram[record["treatment_exact"]["result"]["forced_result"]] += 1
    inspection = build_capture_boundary_inspection(
        records, manifest_pairs=pairs, exact_censored=exact_censored
    )
    source_seconds = sum(
        slot["elapsed_seconds"] for slot in normalized_slots[:expected_pair_count]
    )
    treatment_seconds = sum(
        slot["elapsed_seconds"] for slot in normalized_slots[expected_pair_count:]
    )
    return {
        "protocol_id": CAPTURE_BOUNDARY_EXACT_PROTOCOL_ID,
        "manifest_id": manifest_id,
        "manifest_digest": manifest_digest,
        "configuration": {
            "pair_count": expected_pair_count,
            "max_states": max_states,
            "state_bound": CAPTURE_STATE_BOUND,
            "schedule": "SOURCE_THEN_TREATMENT",
        },
        "schedule": expected_schedule,
        "slots": normalized_slots,
        "pairs": records,
        "aggregate": {
            "exact_attempted": len(normalized_slots),
            "exact_completed": len(normalized_slots) - len(censored),
            "exact_censored_count": len(censored),
            "exact_censored_slots": [slot["schedule_index"] for slot in censored],
            "source_evidence_digest": _exact_slots_digest(
                _SOURCE_EXACT_DOMAIN, normalized_slots[:expected_pair_count]
            ),
            "treatment_evidence_digest": _exact_slots_digest(
                _TREATMENT_EXACT_DOMAIN, normalized_slots[expected_pair_count:]
            ),
            "source_forced_results": dict(sorted(source_histogram.items())),
            "treatment_forced_results": dict(sorted(treatment_histogram.items())),
            "exact_horizon_count": sum(record["exact_horizon"] for record in records),
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


def evaluate_capture_boundary_exact(
    manifest_or_pairs: Any,
    *,
    manifest_validator: Optional[Callable[[Any], Any]] = None,
    expected_pair_count: int = CAPTURE_BOUNDARY_PAIR_COUNT,
    max_states: int = CAPTURE_BOUNDARY_EXACT_MAX_STATES,
    solver: Callable[..., Any] = solve_game,
    clock: Callable[[], float] = time.perf_counter,
) -> Dict[str, Any]:
    """Execute all source slots, then all treatment slots, continuing after censors."""

    pairs, _, _ = _manifest_pairs(
        manifest_or_pairs,
        manifest_validator=manifest_validator,
        expected_pair_count=expected_pair_count,
    )
    schedule = capture_boundary_schedule(
        manifest_or_pairs,
        manifest_validator=manifest_validator,
        expected_pair_count=expected_pair_count,
    )
    slots = []
    source_slots = []
    for entry in schedule[:expected_pair_count]:
        pair = pairs[entry["pair_index"]]
        definition = parse_definition(
            pair["{}_definition".format(entry["side"].lower())]
        )
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

    # The source phase is an explicit integrity boundary.  Replaying and sealing
    # all source PVs here guarantees that no treatment is solved after malformed
    # source evidence, while state-budget censors remain ordinary occupied slots.
    sealed_source_slots = [
        _normalize_exact_slot(
            pairs[entry["pair_index"]], entry, slot, max_states=max_states
        )[0]
        for entry, slot in zip(schedule[:expected_pair_count], source_slots)
    ]
    source_seal = _exact_slots_digest(_SOURCE_EXACT_DOMAIN, sealed_source_slots)
    slots.extend(source_slots)

    for entry in schedule[expected_pair_count:]:
        pair = pairs[entry["pair_index"]]
        definition = parse_definition(
            pair["{}_definition".format(entry["side"].lower())]
        )
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

    result = build_capture_boundary_exact_result(
        manifest_or_pairs,
        slots,
        manifest_validator=manifest_validator,
        expected_pair_count=expected_pair_count,
        max_states=max_states,
    )
    if result["aggregate"]["source_evidence_digest"] != source_seal:
        raise ValueError("source exact evidence changed after its phase seal")
    return result


def validate_capture_boundary_exact_result(
    result: Mapping[str, Any],
    manifest_or_pairs: Any,
    *,
    manifest_validator: Optional[Callable[[Any], Any]] = None,
    expected_pair_count: int = CAPTURE_BOUNDARY_PAIR_COUNT,
    max_states: int = CAPTURE_BOUNDARY_EXACT_MAX_STATES,
) -> Dict[str, Any]:
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
        "capture-boundary exact result",
    )
    rebuilt = build_capture_boundary_exact_result(
        manifest_or_pairs,
        value["slots"],
        manifest_validator=manifest_validator,
        expected_pair_count=expected_pair_count,
        max_states=max_states,
    )
    _validate_timing_summary(
        value["timing"], value["slots"], expected_pair_count, "exact timing"
    )
    if _canonical_bytes(_timing_free_result(value)) != _canonical_bytes(
        _timing_free_result(rebuilt)
    ):
        raise ValueError("capture-boundary exact result does not reconstruct")
    return _copy(value, "capture-boundary exact result")


def _wilson_interval(successes: int, samples: int) -> Optional[list[float]]:
    if samples == 0:
        return None
    z = 1.959963984540054
    proportion = successes / samples
    denominator = 1.0 + z * z / samples
    center = (proportion + z * z / (2.0 * samples)) / denominator
    margin = z * math.sqrt(
        proportion * (1.0 - proportion) / samples
        + z * z / (4.0 * samples * samples)
    ) / denominator
    return [max(0.0, center - margin), min(1.0, center + margin)]


def _sampled_profile(
    evidence: Mapping[str, Any], *, capture_summary_field: str = "profile_summary"
) -> Dict[str, Any]:
    games = evidence["games"]
    a_wins = sum(game["terminal_outcome"]["winner"] == "A" for game in games)
    b_wins = sum(game["terminal_outcome"]["winner"] == "B" for game in games)
    draws = len(games) - a_wins - b_wins
    decisive = a_wins + b_wins
    reasons = Counter(game["terminal_outcome"]["reason"] for game in games)
    return {
        "profile": evidence["profile"],
        "samples": len(games),
        "a_wins": a_wins,
        "b_wins": b_wins,
        "draws": draws,
        "a_win_rate": a_wins / len(games) if games else None,
        "b_win_rate": b_wins / len(games) if games else None,
        "draw_rate": draws / len(games) if games else None,
        "average_plies": (
            sum(game["terminal_ply"] for game in games) / len(games) if games else None
        ),
        "decisive_a_share": a_wins / decisive if decisive else None,
        "decisive_a_wilson_95": _wilson_interval(a_wins, decisive),
        "terminal_reasons": dict(sorted(reasons.items())),
        "seeds": [game["seed"] for game in games],
        "capture_summary": _copy(
            evidence[capture_summary_field], "capture summary"
        ),
    }


def _strong_failures(
    definition: GameDefinition, profile: Mapping[str, Any], gates: PlayGates
) -> list[str]:
    failures = set()
    samples = profile["samples"]
    if type(samples) is not int or samples < 1:
        raise ValueError("complete strong profile requires at least one game")
    if profile["draws"] / samples > gates.max_draw_rate:
        failures.add("EXCESSIVE_DRAWS")
    if profile["average_plies"] < gates.min_average_plies:
        failures.add("TOO_SHORT")
    if profile["average_plies"] > definition.max_plies * gates.max_average_plies_fraction:
        failures.add("TOO_LONG")
    interval = profile["decisive_a_wilson_95"]
    if interval is not None:
        if interval[0] > 0.5 + gates.dominance_interval_margin:
            failures.add("A_DOMINANT")
        if interval[1] < 0.5 - gates.dominance_interval_margin:
            failures.add("B_DOMINANT")
    return sorted(failures)


def capture_boundary_direction(
    profile_summary: Optional[Mapping[str, Any]],
    exact_result: Mapping[str, Any],
    exact_terminal_reason: str,
    *,
    profile_status: str = "COMPLETED",
) -> Dict[str, Any]:
    """Apply the exact-horizon distinction to one strong profile."""

    if exact_terminal_reason == "PLY_LIMIT":
        return {
            "status": "NOT_APPLICABLE_HORIZON",
            "sampled_direction": None,
            "direction_match": None,
        }
    if profile_status != "COMPLETED":
        return {
            "status": "NOT_APPLICABLE_NODE_CENSOR",
            "sampled_direction": None,
            "direction_match": None,
        }
    forced = exact_result.get("forced_result")
    if forced not in _VALUE_BY_RESULT or not isinstance(profile_summary, Mapping):
        raise ValueError("non-horizon direction requires an exact result and complete profile")
    direction = sampled_direction(profile_summary)
    # Only directional A/B labels can match.  An exact draw remains a public
    # mismatch under the frozen strong contract rather than an integrity error.
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
    if agent_factory is None:
        agent = MinimaxAgent(depth=depth, max_total_nodes=max_nodes)
    else:
        agent = agent_factory(
            definition=definition,
            depth=depth,
            max_nodes=max_nodes,
            schedule_entry=_copy(entry, "schedule entry"),
        )
    reset = getattr(agent, "reset_budget", None)
    if not callable(reset):
        raise ValueError("strong agent must expose reset_budget")
    reset()
    if type(getattr(agent, "total_nodes", None)) is not int or agent.total_nodes != 0:
        raise ValueError("strong agent reset must set total_nodes to zero")
    return agent


def _complete_game_record(
    definition: GameDefinition,
    agent: Any,
    seed: int,
) -> Tuple[GameRecord, list[Dict[str, Any]]]:
    rng = random.Random(seed)
    state = initial_state(definition)
    actions = []
    while not state.terminal:
        choices = legal_actions(definition, state)
        action = agent.select_action(definition, state, choices, rng)
        if action not in choices:
            raise ValueError("strong agent selected an illegal action")
        actions.append(action)
        state = apply_action(definition, state, action)
    assert state.outcome is not None
    identity = _agent_identity(agent)
    return (
        GameRecord(
            seed=seed,
            agent_a=identity,
            agent_b=identity,
            actions=tuple(actions),
            winner=state.outcome.winner,
            terminal_reason=state.outcome.reason,
        ),
        [action.to_dict() for action in actions],
    )


def _execute_profile(
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
        raise ValueError(
            "strong agent identity must be {}".format(expected_identity)
        )
    records = []
    game_nodes = []
    incomplete = None
    for seed in seeds:
        before = agent.total_nodes
        partial_actions: list[Dict[str, Any]] = []
        rng = random.Random(seed)
        state = initial_state(definition)
        try:
            while not state.terminal:
                choices = legal_actions(definition, state)
                action = agent.select_action(definition, state, choices, rng)
                if action not in choices:
                    raise ValueError("strong agent selected an illegal action")
                partial_actions.append(action.to_dict())
                state = apply_action(definition, state, action)
        except SearchBudgetExceeded as error:
            if error.scope != "per-candidate":
                raise
            final = agent.total_nodes
            if (
                type(final) is not int
                or final != error.visited_nodes
                or error.max_nodes != max_nodes
                or final != max_nodes
                or final < before
            ):
                raise ValueError("strong censor node accounting mismatch")
            incomplete = {
                "seed": seed,
                "completed_action_prefix": partial_actions,
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
            actions=tuple(action_from_dict(action) for action in partial_actions),
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
        evidence = build_capture_profile_evidence(definition, profile, records, seeds)
        status = "COMPLETED"
    else:
        evidence = build_censored_capture_profile_evidence(
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
        "depth-5 schedule slot",
    )
    for field in ("schedule_index", "pair_index", "side", "pair_id", "definition_hash"):
        if slot[field] != expected[field]:
            raise ValueError("depth-5 schedule identity/order mismatch")
    if slot["agent_identity"] != _profile_name(depth):
        raise ValueError("depth-5 agent identity mismatch")
    definition = parse_definition(
        pair["{}_definition".format(expected["side"].lower())]
    )
    evidence = validate_capture_profile_evidence(
        definition, slot["profile_evidence"], expected_seeds=seeds
    )
    if evidence["profile"] != _profile_name(depth):
        raise ValueError("depth-5 profile evidence identity mismatch")
    expected_status = (
        "COMPLETED"
        if evidence["status"] == "COMPLETED"
        else "INCOMPLETE_NODE_CENSOR"
    )
    if slot["status"] != expected_status:
        raise ValueError("depth-5 slot/profile status mismatch")
    expanded = _strict_int(slot["expanded_nodes"], "expanded_nodes")
    if expanded > max_nodes:
        raise ValueError("depth-5 expanded_nodes exceeds frozen cap")
    game_nodes = slot["game_nodes"]
    if not isinstance(game_nodes, list) or len(game_nodes) != len(evidence["games"]):
        raise ValueError("depth-5 game node ledger length mismatch")
    previous = 0
    normalized_nodes = []
    for game, raw_nodes in zip(evidence["games"], game_nodes):
        nodes = _exact_keys(
            raw_nodes,
            ("seed", "nodes_before", "nodes_after", "nodes_used"),
            "game node evidence",
        )
        before = _strict_int(nodes["nodes_before"], "nodes_before")
        after = _strict_int(nodes["nodes_after"], "nodes_after")
        used = _strict_int(nodes["nodes_used"], "nodes_used", minimum=1)
        seed = _strict_int(nodes["seed"], "game node seed")
        if (
            seed != game["seed"]
            or before != previous
            or after <= before
            or used != after - before
            or after > max_nodes
        ):
            raise ValueError("game node evidence does not reconstruct")
        previous = after
        normalized_nodes.append(_copy(nodes, "game node evidence"))
    incomplete = slot["incomplete_attempt"]
    if expected_status == "COMPLETED":
        if incomplete is not None or previous != expanded:
            raise ValueError("completed depth-5 slot node evidence is inconsistent")
    else:
        item = _exact_keys(
            incomplete,
            (
                "seed",
                "completed_action_prefix",
                "nodes_before_seed",
                "nodes_consumed",
                "final_cumulative_nodes",
                "limit",
                "scope",
            ),
            "incomplete profile attempt",
        )
        before = _strict_int(item["nodes_before_seed"], "incomplete nodes_before_seed")
        consumed = _strict_int(item["nodes_consumed"], "incomplete nodes_consumed")
        final = _strict_int(
            item["final_cumulative_nodes"], "incomplete final_cumulative_nodes"
        )
        limit = _strict_int(item["limit"], "incomplete node limit", minimum=1)
        incomplete_seed = _strict_int(item["seed"], "incomplete seed")
        if (
            incomplete_seed != evidence["incomplete_seed"]
            or before != previous
            or final != before + consumed
            or final != expanded
            or final != limit
            or limit != max_nodes
            or item["scope"] != "per-candidate"
        ):
            raise ValueError("incomplete profile node evidence is inconsistent")
        trace = derive_capture_trace(
            definition, item["completed_action_prefix"], require_terminal=False
        )
        if trace["terminal"]:
            raise ValueError("incomplete attempt action prefix is already terminal")
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
        "incomplete_attempt": _copy(incomplete, "incomplete attempt") if incomplete else None,
        "expanded_nodes": expanded,
        "elapsed_seconds": _elapsed_seconds(
            slot["elapsed_seconds"], "depth-5 slot elapsed_seconds"
        ),
    }


def _profile_slots_digest(
    domain: bytes, slots: Sequence[Mapping[str, Any]]
) -> str:
    return hashlib.sha256(
        domain
        + _canonical_bytes(
            [
                {key: value for key, value in slot.items() if key != "elapsed_seconds"}
                for slot in slots
            ]
        )
    ).hexdigest()


def _profile_assessment(
    definition: GameDefinition,
    slot: Mapping[str, Any],
    exact: Mapping[str, Any],
    *,
    gates: PlayGates,
) -> Dict[str, Any]:
    if slot["status"] != "COMPLETED":
        direction = capture_boundary_direction(
            None,
            exact["result"],
            exact["result"]["terminal_reason"],
            profile_status=slot["status"],
        )
        return {
            "status": slot["status"],
            "profile": None,
            "partial_profile": _sampled_profile(
                slot["profile_evidence"], capture_summary_field="partial_summary"
            ),
            "direction": direction,
            "failure_codes": None,
            "games_with_capture": None,
        }
    profile = _sampled_profile(slot["profile_evidence"])
    direction = capture_boundary_direction(
        profile,
        exact["result"],
        exact["result"]["terminal_reason"],
    )
    failures = _strong_failures(definition, profile, gates)
    return {
        "status": "COMPLETED",
        "profile": profile,
        "partial_profile": None,
        "direction": direction,
        "failure_codes": failures,
        "games_with_capture": profile["capture_summary"]["games_with_capture"],
    }


def _profile_node_totals(slots: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    completed = sum(
        game_nodes["nodes_used"]
        for slot in slots
        for game_nodes in slot["game_nodes"]
    )
    incomplete = sum(
        slot["incomplete_attempt"]["nodes_consumed"]
        for slot in slots
        if slot["incomplete_attempt"] is not None
    )
    expanded = sum(slot["expanded_nodes"] for slot in slots)
    if expanded != completed + incomplete:
        raise ValueError("profile node totals do not reconstruct")
    return {
        "completed_game_nodes": completed,
        "incomplete_attempt_nodes": incomplete,
        "expanded_nodes_total": expanded,
    }


def _profile_slot_bucket(slots: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    games = [
        game
        for slot in slots
        for game in slot["profile_evidence"]["games"]
    ]
    winner_histogram = Counter(
        "DRAW" if game["terminal_outcome"]["winner"] is None
        else "{}_WIN".format(game["terminal_outcome"]["winner"])
        for game in games
    )
    terminal_histogram = Counter(
        game["terminal_outcome"]["reason"] for game in games
    )
    capture_histogram = Counter(
        game["capture"]["capture_count"] for game in games
    )
    total_plies = sum(game["terminal_ply"] for game in games)
    return {
        "definition_count": len(slots),
        "game_count": len(games),
        "sampled_results": dict(sorted(winner_histogram.items())),
        "terminal_reasons": dict(sorted(terminal_histogram.items())),
        "total_plies": total_plies,
        "average_plies": total_plies / len(games) if games else None,
        "capture_count": sum(game["capture"]["capture_count"] for game in games),
        "games_with_capture": sum(
            game["capture"]["capture_count"] > 0 for game in games
        ),
        "capture_count_histogram": {
            str(count): capture_histogram[count] for count in sorted(capture_histogram)
        },
        "first_capture_ply_histogram": _first_capture_ply_histogram(
            game["capture"]["first_capture_ply"] for game in games
        ),
        "repeated_position_games": sum(
            game["capture"]["repeated_position"] for game in games
        ),
        "replacement_recapture_games": sum(
            game["capture"]["replacement_recapture"] for game in games
        ),
        "capture_replace_cycle_games": sum(
            game["capture"]["capture_replace_cycle"] for game in games
        ),
        **_profile_node_totals(slots),
    }


def _descriptive_profile_aggregate(
    slots: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
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
    side_name = side.upper()
    side_slots = [
        slot
        for slot in slots
        if slot["side"] == side_name and slot["pair_id"] in pair_ids
    ]
    profiles = [record["{}_profile".format(side)] for record in records]
    direction_statuses = Counter(
        profile["direction"]["status"] for profile in profiles
    )
    failures = Counter(
        code
        for profile in profiles
        for code in (profile["failure_codes"] or [])
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
    records: Sequence[Mapping[str, Any]], slots: Sequence[Mapping[str, Any]]
) -> Dict[str, Any]:
    treatment_exact = Counter(
        record["treatment_exact_forced_result"] for record in records
    )
    frontier = [record for record in records if record["interaction_frontier"]]
    return {
        "pair_count": len(records),
        "source": _depth_side_breakdown(records, slots, "source"),
        "treatment": _depth_side_breakdown(records, slots, "treatment"),
        "treatment_exact_forced_results": dict(sorted(treatment_exact.items())),
        "exact_horizon_count": sum(record["exact_horizon"] for record in records),
        "node_censor_count": sum(record["node_censored"] for record in records),
        "direction_mismatch_count": sum(
            record["direction_mismatch"] for record in records
        ),
        "interaction_frontier_count": len(frontier),
        "a_frontier_count": sum(
            record["treatment_exact_forced_result"] == "A_WIN"
            for record in frontier
        ),
        "b_frontier_count": sum(
            record["treatment_exact_forced_result"] == "B_WIN"
            for record in frontier
        ),
        "candidate_shaped_count": sum(
            record["candidate_shaped"] for record in records
        ),
    }


def _depth_breakdowns(
    records: Sequence[Mapping[str, Any]], slots: Sequence[Mapping[str, Any]]
) -> Dict[str, Any]:
    cells = sorted({record["structural_cell"] for record in records})
    return {
        "all": _depth_group_summary(records, slots),
        "by_vector": {
            "v3": _depth_group_summary(
                [record for record in records if record["vector_count"] == 3],
                slots,
            ),
            "v4": _depth_group_summary(
                [record for record in records if record["vector_count"] == 4],
                slots,
            ),
        },
        "by_structural_cell": {
            cell: _depth_group_summary(
                [record for record in records if record["structural_cell"] == cell],
                slots,
            )
            for cell in cells
        },
    }


def assess_capture_boundary_pairs(
    pair_records: Sequence[Mapping[str, Any]],
    raw_assessments: Mapping[str, Any],
) -> Dict[str, Any]:
    """Apply Plan 0009's frozen boundary, shape, and composite priority rules."""

    if not isinstance(pair_records, (list, tuple)) or not pair_records:
        raise ValueError("capture-boundary assessment requires pair records")
    primary = raw_assessments.get("primary_response")
    realized = raw_assessments.get("realized_response")
    cycling = raw_assessments.get("cycling_dominance")
    if not all(isinstance(item, Mapping) for item in (primary, realized, cycling)):
        raise ValueError("capture-boundary raw assessments are incomplete")
    both_raw_supported = (
        primary.get("status") == "SUPPORTED" and realized.get("status") == "SUPPORTED"
    )

    exact_horizons = sum(bool(record.get("exact_horizon")) for record in pair_records)
    node_censors = sum(bool(record.get("node_censored")) for record in pair_records)
    direction_mismatches = sum(
        bool(record.get("direction_mismatch")) for record in pair_records
    )
    frontier = [record for record in pair_records if record.get("interaction_frontier") is True]
    candidate = [record for record in pair_records if record.get("candidate_shaped") is True]
    a_frontier = [
        record for record in frontier if record.get("treatment_exact_forced_result") == "A_WIN"
    ]
    b_frontier = [
        record for record in frontier if record.get("treatment_exact_forced_result") == "B_WIN"
    ]
    b3 = sum(
        record.get("vector_count") == 3
        and record.get("treatment_exact_forced_result") == "B_WIN"
        for record in pair_records
    )
    b4 = sum(
        record.get("vector_count") == 4
        and record.get("treatment_exact_forced_result") == "B_WIN"
        for record in pair_records
    )
    cell_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: {"B3": 0, "B4": 0})
    for record in pair_records:
        cell = record.get("structural_cell")
        if not isinstance(cell, str):
            stratum = record.get("stratum")
            if not isinstance(stratum, Mapping):
                raise ValueError("assessment pair lacks a structural cell")
            cell = _structural_cell(stratum)
        if record.get("treatment_exact_forced_result") == "B_WIN":
            cell_counts[cell]["B{}".format(record.get("vector_count"))] += 1
    improved_cells = sum(value["B4"] > value["B3"] for value in cell_counts.values())
    v3_a_frontier = [record for record in a_frontier if record.get("vector_count") == 3]
    v4_b_frontier = [record for record in b_frontier if record.get("vector_count") == 4]
    v3_b_frontier = [record for record in b_frontier if record.get("vector_count") == 3]
    boundary_supported = bool(
        both_raw_supported
        and b4 >= 24
        and b3 <= 24
        and b4 - b3 >= 8
        and improved_cells >= 5
        and len(v3_a_frontier) >= 4
        and len({record["structural_cell"] for record in v3_a_frontier}) >= 2
        and len(v4_b_frontier) >= 4
        and len({record["structural_cell"] for record in v4_b_frontier}) >= 2
    )
    overcorrection = bool(
        not boundary_supported
        and both_raw_supported
        and b3 + b4 >= 48
        and b3 >= 24
        and b4 >= 24
        and len(b_frontier) >= 8
        and len({record["structural_cell"] for record in b_frontier}) >= 4
        and len(a_frontier) <= 3
    )
    vector_not_supported = bool(
        not overcorrection
        and b4 <= b3
        and len(v4_b_frontier) <= len(v3_b_frontier)
    )
    candidate_cells = {record["structural_cell"] for record in candidate}
    candidate_roles = {record["treatment_exact_forced_result"] for record in candidate}
    if (
        len(candidate) >= 4
        and len(candidate_cells) >= 2
        and {"A_WIN", "B_WIN"}.issubset(candidate_roles)
    ):
        candidate_status = "SUPPORTED"
    elif not candidate:
        candidate_status = "NOT_SUPPORTED"
    else:
        candidate_status = "INCONCLUSIVE"

    capture_zero = bool(
        primary.get("count") == 0
        or realized.get("count") == 0
        or not b_frontier
        or not frontier
    )
    cycling_dominant = cycling.get("status") == "DOMINANT"
    incomplete = bool(exact_horizons or node_censors or direction_mismatches)
    if exact_horizons:
        incomplete_reason = "EXACT_HORIZON"
    elif node_censors:
        incomplete_reason = "NODE_CENSOR"
    elif direction_mismatches:
        incomplete_reason = "DIRECTION_MISMATCH"
    else:
        incomplete_reason = None

    if incomplete:
        boundary_status = "INCONCLUSIVE"
        candidate_assessment_status = "INCONCLUSIVE"
        if cycling_dominant:
            overall = "REJECT_CYCLING"
            next_branch = "FAMILY_REASSESSMENT"
        else:
            overall = "INCONCLUSIVE"
            next_branch = "NO_NEW_CASES_OR_RULE"
    else:
        boundary_status = (
            "SUPPORTED_VECTOR_BOUNDARY"
            if boundary_supported
            else (
                "NOT_SUPPORTED_VECTOR_BOUNDARY"
                if vector_not_supported
                else "INCONCLUSIVE"
            )
        )
        candidate_assessment_status = candidate_status
        if cycling_dominant:
            overall = "REJECT_CYCLING"
            next_branch = "FAMILY_REASSESSMENT"
        elif capture_zero:
            overall = "NOT_SUPPORTED_CAPTURE"
            next_branch = "FAMILY_REASSESSMENT"
        elif overcorrection:
            overall = "OVERCORRECTION"
            next_branch = "FAMILY_REASSESSMENT"
        elif boundary_supported and candidate_status == "SUPPORTED":
            overall = "SUPPORTED"
            next_branch = "PLAN_GENERATOR_V3"
        elif boundary_supported and candidate_status == "NOT_SUPPORTED":
            overall = "NOT_SUPPORTED"
            next_branch = "FAMILY_REASSESSMENT"
        elif vector_not_supported:
            overall = "NOT_SUPPORTED_VECTOR_BOUNDARY"
            next_branch = "FAMILY_REASSESSMENT"
        else:
            overall = "INCONCLUSIVE"
            next_branch = "NO_NEW_CASES_OR_RULE"

    return {
        "strong_evidence": {
            "status": "INCONCLUSIVE" if incomplete else "COMPLETE",
            "exact_horizon_count": exact_horizons,
            "node_censor_count": node_censors,
            "direction_mismatch_count": direction_mismatches,
            "incomplete_reason": incomplete_reason,
        },
        "mechanical_boundary": {
            "status": boundary_status,
            "B3": b3,
            "B4": b4,
            "b_win_increase": b4 - b3,
            "improved_cell_count": improved_cells,
            "cell_counts": {key: cell_counts[key] for key in sorted(cell_counts)},
            "v3_a_frontier_count": len(v3_a_frontier),
            "v3_a_frontier_cell_count": len(
                {record["structural_cell"] for record in v3_a_frontier}
            ),
            "v4_b_frontier_count": len(v4_b_frontier),
            "v4_b_frontier_cell_count": len(
                {record["structural_cell"] for record in v4_b_frontier}
            ),
        },
        "overcorrection": {
            "status": (
                "INCONCLUSIVE"
                if incomplete
                else ("OVERCORRECTION" if overcorrection else "NOT_MET")
            ),
            "total_b_wins": b3 + b4,
            "b_frontier_count": len(b_frontier),
            "b_frontier_cell_count": len(
                {record["structural_cell"] for record in b_frontier}
            ),
            "a_frontier_count": len(a_frontier),
        },
        "candidate_shape": {
            "status": candidate_assessment_status,
            "case_count": len(candidate),
            "structural_cell_count": len(candidate_cells),
            "exact_roles": sorted(candidate_roles),
        },
        "interaction_frontier": {
            "case_count": len(frontier),
            "a_win_count": len(a_frontier),
            "b_win_count": len(b_frontier),
        },
        "overall": {
            "status": overall,
            "next_branch": next_branch,
            "dominance_cliff": bool(
                overall == "NOT_SUPPORTED"
                and boundary_supported
                and candidate_status == "NOT_SUPPORTED"
            ),
        },
    }


def build_capture_boundary_depth5_result(
    manifest_or_pairs: Any,
    exact_result: Mapping[str, Any],
    profile_slots: Sequence[Mapping[str, Any]],
    *,
    manifest_validator: Optional[Callable[[Any], Any]] = None,
    expected_pair_count: int = CAPTURE_BOUNDARY_PAIR_COUNT,
    seeds: Sequence[int] = CAPTURE_BOUNDARY_SEEDS,
    depth: int = CAPTURE_BOUNDARY_DEPTH,
    max_nodes: int = CAPTURE_BOUNDARY_MAX_NODES,
    gates: PlayGates = PlayGates(),
) -> Dict[str, Any]:
    _strict_int(depth, "depth", minimum=1)
    _strict_int(max_nodes, "max_nodes", minimum=1)
    if not isinstance(gates, PlayGates):
        raise ValueError("gates must be PlayGates")
    seed_tuple = tuple(seeds)
    if (
        not seed_tuple
        or any(type(seed) is not int for seed in seed_tuple)
        or len(set(seed_tuple)) != len(seed_tuple)
    ):
        raise ValueError("depth-5 seeds must be unique integers")
    pairs, manifest_digest, manifest_id = _manifest_pairs(
        manifest_or_pairs,
        manifest_validator=manifest_validator,
        expected_pair_count=expected_pair_count,
    )
    exact = validate_capture_boundary_exact_result(
        exact_result,
        manifest_or_pairs,
        manifest_validator=manifest_validator,
        expected_pair_count=expected_pair_count,
        max_states=CAPTURE_BOUNDARY_EXACT_MAX_STATES,
    )
    if exact["aggregate"]["exact_censored_count"]:
        raise ValueError("depth-5 stage is blocked by exact censoring")
    expected_schedule = capture_boundary_schedule(
        manifest_or_pairs,
        manifest_validator=manifest_validator,
        expected_pair_count=expected_pair_count,
    )
    if not isinstance(profile_slots, (list, tuple)) or len(profile_slots) != len(
        expected_schedule
    ):
        raise ValueError("profile slots must cover the full fixed schedule")
    normalized_slots = []
    by_pair: Dict[int, Dict[str, Any]] = {
        index: {} for index in range(expected_pair_count)
    }
    exact_by_pair = {record["pair_id"]: record for record in exact["pairs"]}
    for expected, raw_slot in zip(expected_schedule, profile_slots):
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
        exact_side = exact_by_pair[pair["pair_id"]]["{}_exact".format(side)]
        by_pair[pair["pair_index"]][side] = _profile_assessment(
            definition, slot, exact_side, gates=gates
        )

    records = []
    for pair in pairs:
        raw_pair = exact_by_pair[pair["pair_id"]]
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
        exact_result_value = raw_pair["treatment_exact"]["result"]["forced_result"]
        interaction = bool(
            not node_censored
            and not raw_pair["exact_horizon"]
            and source_profile["direction"]["direction_match"] is True
            and treatment_profile["direction"]["direction_match"] is True
            and not set(treatment_profile["failure_codes"]).intersection(_SHAPE_FAILURES)
            and treatment_profile["games_with_capture"] > 0
        )
        candidate = bool(
            interaction
            and not set(treatment_profile["failure_codes"]).intersection(
                _DOMINANCE_FAILURES
            )
        )
        records.append(
            {
                "pair_index": pair["pair_index"],
                "pair_id": pair["pair_id"],
                "source_case_id": pair["source_case_id"],
                "stratum": pair["stratum"],
                "stratum_id": pair["stratum_id"],
                "structural_cell": pair["structural_cell"],
                "vector_count": pair["vector_count"],
                "selection_rank": pair["selection_rank"],
                "source_definition_hash": pair["source_definition_hash"],
                "source_d4_canonical_hash": pair["source_d4_canonical_hash"],
                "treatment_definition_hash": pair["treatment_definition_hash"],
                "treatment_d4_canonical_hash": pair["treatment_d4_canonical_hash"],
                "source_exact": raw_pair["source_exact"],
                "treatment_exact": raw_pair["treatment_exact"],
                "exact_horizon": raw_pair["exact_horizon"],
                "source_profile": source_profile,
                "treatment_profile": treatment_profile,
                "node_censored": node_censored,
                "direction_mismatch": direction_mismatch,
                "treatment_exact_forced_result": exact_result_value,
                "interaction_frontier": interaction,
                "candidate_shaped": candidate,
            }
        )
    raw_assessments = exact["aggregate"]["raw_assessments"]
    assessments = assess_capture_boundary_pairs(records, raw_assessments)
    inspection = build_capture_boundary_inspection(
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
        "protocol_id": CAPTURE_BOUNDARY_DEPTH5_PROTOCOL_ID,
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
        "schedule": expected_schedule,
        "slots": normalized_slots,
        "pairs": records,
        "aggregate": {
            "profile_attempted": len(normalized_slots),
            "profile_completed": sum(slot["status"] == "COMPLETED" for slot in normalized_slots),
            "node_censored": sum(
                slot["status"] == "INCOMPLETE_NODE_CENSOR" for slot in normalized_slots
            ),
            "expanded_nodes_total": node_totals["expanded_nodes_total"],
            "completed_game_nodes_total": node_totals["completed_game_nodes"],
            "incomplete_attempt_nodes_total": node_totals[
                "incomplete_attempt_nodes"
            ],
            "source_evidence_digest": _profile_slots_digest(
                _SOURCE_DEPTH5_DOMAIN, normalized_slots[:expected_pair_count]
            ),
            "treatment_evidence_digest": _profile_slots_digest(
                _TREATMENT_DEPTH5_DOMAIN,
                normalized_slots[expected_pair_count:],
            ),
            "interaction_frontier_count": sum(
                record["interaction_frontier"] for record in records
            ),
            "candidate_shaped_count": sum(record["candidate_shaped"] for record in records),
            "descriptive_profiles": _descriptive_profile_aggregate(normalized_slots),
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


def evaluate_capture_boundary_depth5(
    manifest_or_pairs: Any,
    exact_result: Mapping[str, Any],
    *,
    manifest_validator: Optional[Callable[[Any], Any]] = None,
    expected_pair_count: int = CAPTURE_BOUNDARY_PAIR_COUNT,
    seeds: Sequence[int] = CAPTURE_BOUNDARY_SEEDS,
    depth: int = CAPTURE_BOUNDARY_DEPTH,
    max_nodes: int = CAPTURE_BOUNDARY_MAX_NODES,
    gates: PlayGates = PlayGates(),
    agent_factory: Optional[Callable[..., Any]] = None,
    clock: Callable[[], float] = time.perf_counter,
) -> Dict[str, Any]:
    """Execute the complete fixed source-then-treatment depth-5 schedule."""

    seed_tuple = tuple(seeds)
    pairs, _, _ = _manifest_pairs(
        manifest_or_pairs,
        manifest_validator=manifest_validator,
        expected_pair_count=expected_pair_count,
    )
    exact = validate_capture_boundary_exact_result(
        exact_result,
        manifest_or_pairs,
        manifest_validator=manifest_validator,
        expected_pair_count=expected_pair_count,
        max_states=CAPTURE_BOUNDARY_EXACT_MAX_STATES,
    )
    if exact["aggregate"]["exact_censored_count"]:
        raise ValueError("depth-5 stage is blocked by exact censoring")
    schedule = capture_boundary_schedule(
        manifest_or_pairs,
        manifest_validator=manifest_validator,
        expected_pair_count=expected_pair_count,
    )
    slots = []
    source_slots = []
    for entry in schedule[:expected_pair_count]:
        pair = pairs[entry["pair_index"]]
        definition = parse_definition(
            pair["{}_definition".format(entry["side"].lower())]
        )
        started = clock()
        slot = _execute_profile(
            definition,
            entry,
            seeds=seed_tuple,
            depth=depth,
            max_nodes=max_nodes,
            agent_factory=agent_factory,
        )
        slot["elapsed_seconds"] = _elapsed_seconds(
            clock() - started, "depth-5 elapsed_seconds"
        )
        source_slots.append(slot)

    # As with exact solving, source profiles form a mandatory phase boundary.
    # Full trace/profile/node validation and a timing-free ordered seal happen
    # before any treatment agent is constructed.
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
    slots.extend(source_slots)

    for entry in schedule[expected_pair_count:]:
        pair = pairs[entry["pair_index"]]
        definition = parse_definition(
            pair["{}_definition".format(entry["side"].lower())]
        )
        started = clock()
        slot = _execute_profile(
            definition,
            entry,
            seeds=seed_tuple,
            depth=depth,
            max_nodes=max_nodes,
            agent_factory=agent_factory,
        )
        slot["elapsed_seconds"] = _elapsed_seconds(
            clock() - started, "depth-5 elapsed_seconds"
        )
        slots.append(slot)

    result = build_capture_boundary_depth5_result(
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


def validate_capture_boundary_depth5_result(
    result: Mapping[str, Any],
    manifest_or_pairs: Any,
    exact_result: Mapping[str, Any],
    *,
    manifest_validator: Optional[Callable[[Any], Any]] = None,
    expected_pair_count: int = CAPTURE_BOUNDARY_PAIR_COUNT,
    seeds: Sequence[int] = CAPTURE_BOUNDARY_SEEDS,
    depth: int = CAPTURE_BOUNDARY_DEPTH,
    max_nodes: int = CAPTURE_BOUNDARY_MAX_NODES,
    gates: PlayGates = PlayGates(),
) -> Dict[str, Any]:
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
        "capture-boundary depth-5 result",
    )
    rebuilt = build_capture_boundary_depth5_result(
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
    _validate_timing_summary(
        value["timing"], value["slots"], expected_pair_count, "depth-5 timing"
    )
    if _canonical_bytes(_timing_free_result(value)) != _canonical_bytes(
        _timing_free_result(rebuilt)
    ):
        raise ValueError("capture-boundary depth-5 result does not reconstruct")
    return _copy(value, "capture-boundary depth-5 result")


def _inspection_score(domain: bytes, treatment_d4_hash: str) -> str:
    return hashlib.sha256(domain + treatment_d4_hash.encode("ascii")).hexdigest()


def _record_exact(record: Mapping[str, Any], side: str) -> Optional[Mapping[str, Any]]:
    exact = record.get("{}_exact".format(side))
    return exact if isinstance(exact, Mapping) else None


def build_capture_boundary_inspection(
    pair_records: Sequence[Mapping[str, Any]],
    *,
    manifest_pairs: Sequence[Mapping[str, Any]],
    exact_censored: bool = False,
) -> Dict[str, Any]:
    """Build the deterministic inspection union in manifest order."""

    if not isinstance(pair_records, (list, tuple)) or not isinstance(
        manifest_pairs, (list, tuple)
    ):
        raise ValueError("inspection inputs must be pair arrays")
    if len(pair_records) != len(manifest_pairs):
        raise ValueError("inspection pair/manifest lengths differ")
    by_id = {record.get("pair_id"): record for record in pair_records}
    if len(by_id) != len(pair_records) or None in by_id:
        raise ValueError("inspection pair identities must be unique")
    reasons: Dict[str, set[str]] = defaultdict(set)
    completed_by_vector: Dict[int, Dict[str, list[Mapping[str, Any]]]] = {
        3: {"change": [], "control": []},
        4: {"change": [], "control": []},
    }
    for pair in manifest_pairs:
        pair_id = pair["pair_id"]
        if pair_id not in by_id:
            raise ValueError("inspection record missing manifest pair")
        record = by_id[pair_id]
        source = _record_exact(record, "source")
        treatment = _record_exact(record, "treatment")
        exact_incomplete = (
            not isinstance(source, Mapping)
            or not isinstance(treatment, Mapping)
            or source.get("status") != "COMPLETED"
            or treatment.get("status") != "COMPLETED"
        )
        if exact_incomplete:
            reasons[pair_id].add("EXACT_CENSOR")
        if (
            isinstance(treatment, Mapping)
            and treatment.get("status") == "COMPLETED"
            and treatment["result"]["terminal_reason"] == "PLY_LIMIT"
        ):
            reasons[pair_id].add("EXACT_HORIZON")
        if not exact_incomplete:
            pool = (
                "change"
                if source["result"]["forced_result"]
                != treatment["result"]["forced_result"]
                else "control"
            )
            completed_by_vector[pair["vector_count"]][pool].append(pair)
        if record.get("node_censored") is True:
            reasons[pair_id].add("NODE_CENSOR")
        if record.get("direction_mismatch") is True:
            reasons[pair_id].add("DIRECTION_MISMATCH")
        if (
            record.get("interaction_frontier") is True
            and record.get("treatment_exact_forced_result") == "A_WIN"
        ):
            reasons[pair_id].add("A_FRONTIER")
        if record.get("candidate_shaped") is True:
            reasons[pair_id].add("CANDIDATE_SHAPED")
        if pair["selection_rank"] == 0:
            reasons[pair_id].add("STRATUM_FLOOR")

    pools: Dict[str, Any] = {}
    for vector_count in (3, 4):
        for pool_name, domain, reason in (
            ("change", _CHANGE_DOMAIN, "OUTCOME_CHANGE_SAMPLE"),
            ("control", _CONTROL_DOMAIN, "OUTCOME_UNCHANGED_CONTROL"),
        ):
            pool = completed_by_vector[vector_count][pool_name]
            ordered = sorted(
                pool,
                key=lambda pair: (
                    _inspection_score(domain, pair["treatment_d4_canonical_hash"]),
                    pair["treatment_d4_canonical_hash"],
                    pair["pair_id"],
                ),
            )
            selected = ordered[:8]
            for pair in selected:
                reasons[pair["pair_id"]].add(reason)
            key = "v{}_{}".format(vector_count, pool_name)
            pools[key] = {
                "availability": "PARTIAL_EXACT_CENSOR" if exact_censored else "COMPLETE",
                "pool_size": len(pool),
                "selected_count": len(selected),
                "shortfall": max(0, 8 - len(pool)),
                "selected_pair_ids": [pair["pair_id"] for pair in selected],
            }

    reason_rank = {reason: index for index, reason in enumerate(_INSPECTION_REASONS)}
    selected_rows = []
    for pair in manifest_pairs:
        pair_reasons = reasons.get(pair["pair_id"], set())
        if not pair_reasons:
            continue
        selected_rows.append(
            {
                "pair_id": pair["pair_id"],
                "source_d4_canonical_hash": pair["source_d4_canonical_hash"],
                "treatment_d4_canonical_hash": pair["treatment_d4_canonical_hash"],
                "vector_count": pair["vector_count"],
                "stratum_id": pair["stratum_id"],
                "reasons": sorted(pair_reasons, key=reason_rank.__getitem__),
            }
        )
    return {
        "version": "capture-boundary-v1-inspection-v1",
        "disposition": "EXACT_ONLY_CENSORED" if exact_censored else "COMPLETE",
        "reason_order": list(_INSPECTION_REASONS),
        "pools": pools,
        "selected": selected_rows,
    }


def validate_capture_boundary_inspection(
    inspection: Mapping[str, Any],
    pair_records: Sequence[Mapping[str, Any]],
    *,
    manifest_pairs: Sequence[Mapping[str, Any]],
    exact_censored: bool = False,
) -> Dict[str, Any]:
    rebuilt = build_capture_boundary_inspection(
        pair_records,
        manifest_pairs=manifest_pairs,
        exact_censored=exact_censored,
    )
    if _canonical_bytes(inspection) != _canonical_bytes(rebuilt):
        raise ValueError("capture-boundary inspection does not reconstruct")
    return _copy(inspection, "capture-boundary inspection")


__all__ = [
    "CAPTURE_BOUNDARY_PAIR_COUNT",
    "CAPTURE_BOUNDARY_EXACT_MAX_STATES",
    "CAPTURE_BOUNDARY_DEPTH",
    "CAPTURE_BOUNDARY_MAX_NODES",
    "CAPTURE_BOUNDARY_SEEDS",
    "capture_boundary_schedule",
    "evaluate_capture_boundary_exact",
    "build_capture_boundary_exact_result",
    "validate_capture_boundary_exact_result",
    "evaluate_capture_boundary_depth5",
    "build_capture_boundary_depth5_result",
    "validate_capture_boundary_depth5_result",
    "capture_boundary_direction",
    "assess_capture_boundary_response",
    "assess_capture_boundary_pairs",
    "build_capture_boundary_inspection",
    "validate_capture_boundary_inspection",
]
