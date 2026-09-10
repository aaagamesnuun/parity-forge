"""Pure exact evaluation for the fixed Plan-0011 4x4 calibration corpus.

This module owns no filesystem, Git, reservation, lock, or one-shot behavior.
It accepts an already frozen manifest plus its closed-history witness, executes
the fixed manifest-order schedule, and reconstructs every derived field from raw
principal variations.

Unlike the natural-horizon experiments, ``DRAW``/``PLY_LIMIT`` is an expected
calibration label here.  A state-budget censor is an immediate integrity failure
because the public structural proof places every case strictly below the
unchanged execution cap; failure-sidecar persistence belongs to the later
one-shot runner boundary.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections import Counter
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from .dsl import GameDefinition, Player, definition_hash, parse_definition
from .engine import action_from_dict, apply_action, initial_state, legal_actions
from .four_by_four_calibration import (
    FOUR_BY_FOUR_A_FIRST_STATE_BOUND,
    FOUR_BY_FOUR_B_FIRST_STATE_BOUND,
    FOUR_BY_FOUR_CASE_COUNT,
    FOUR_BY_FOUR_EXACT_MAX_STATES,
    FOUR_BY_FOUR_FIXED_CORPUS_STATE_BOUND,
    build_four_by_four_state_bound_proof,
    four_by_four_calibration_stratum,
    four_by_four_state_upper_bound,
    validate_four_by_four_calibration_definition,
    validate_four_by_four_calibration_manifest,
    validate_four_by_four_searched_states,
)
from .solver import solve_game
from .symmetry import canonicalize_d4, d4_canonical_hash, mechanical_json


FOUR_BY_FOUR_EXACT_RESULT_VERSION = 1
FOUR_BY_FOUR_EXACT_PROTOCOL_ID = "four-by-four-calibration-v1-fixed-exact"
FOUR_BY_FOUR_MIN_DECISIVE_LABELS = 15
FOUR_BY_FOUR_MIN_A_WINS = 4
FOUR_BY_FOUR_MIN_B_WINS = 4
FOUR_BY_FOUR_MIN_HORIZON_DRAWS = 4
FOUR_BY_FOUR_MIN_STRATA_PER_LABEL = 2

_VALUE_BY_RESULT = {"A_WIN": 1, "DRAW": 0, "B_WIN": -1}
_CALIBRATION_LABELS = (
    "A_WIN",
    "B_WIN",
    "HORIZON_DRAW",
)
_TERMINAL_REASONS = ("GOAL", "NO_LEGAL_ACTION", "PLY_LIMIT")
_VECTOR_BANDS = ("v1_3", "v4", "v5", "v6_7")
_EXACT_SLOTS_DOMAIN = b"four-by-four-calibration-v1-exact-slots-v1"
_EXACT_TRACE_DOMAIN = b"four-by-four-calibration-v1-exact-trace-v1"
_CASE_FINGERPRINT_DOMAIN = b"four-by-four-calibration-v1-case-v1"
_INSPECTION_REASON_ORDER = (
    "EXACT_A",
    "EXACT_B",
    "EXACT_HORIZON_DRAW",
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
        raise ValueError("exact evidence must be finite canonical JSON") from error


def _copy(value: Any, label: str) -> Any:
    try:
        return json.loads(_canonical_bytes(value))
    except (TypeError, ValueError) as error:
        raise ValueError("{} must be finite canonical JSON".format(label)) from error


def _exact_keys(
    value: Any, expected: Iterable[str], label: str
) -> Mapping[str, Any]:
    expected_set = set(expected)
    if not isinstance(value, Mapping) or set(value) != expected_set:
        raise ValueError(
            "{} keys must be exactly {}".format(label, sorted(expected_set))
        )
    return value


def _strict_int(
    value: Any,
    label: str,
    *,
    minimum: int = 0,
    expected: Optional[int] = None,
) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError("{} must be an integer >= {}".format(label, minimum))
    if expected is not None and value != expected:
        raise ValueError("{} must equal {}".format(label, expected))
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
        raise ValueError("{} must be a canonical lowercase SHA-256".format(label))
    return value


def _domain_digest(domain: bytes, value: Any) -> str:
    return hashlib.sha256(domain + b"\0" + _canonical_bytes(value)).hexdigest()


def _ordered_stratum_ids() -> Tuple[str, ...]:
    return tuple(
        "f{}-{}-{}-{}".format(first, relation, start, band)
        for first in ("A", "B")
        for relation in ("aligned", "orthogonal")
        for start in ("corner", "edge_inner")
        for band in _VECTOR_BANDS
    )


_ORDERED_STRATUM_IDS = _ordered_stratum_ids()


def _stratum_id(value: Any) -> str:
    stratum = _exact_keys(
        value,
        (
            "first_player",
            "goal_axis_relation",
            "runner_start_class",
            "vector_band",
        ),
        "4x4 exact stratum",
    )
    first = stratum["first_player"]
    relation = {
        "ALIGNED": "aligned",
        "ORTHOGONAL": "orthogonal",
    }.get(stratum["goal_axis_relation"])
    start = {
        "CORNER": "corner",
        "EDGE_INTERIOR": "edge_inner",
    }.get(stratum["runner_start_class"])
    band = stratum["vector_band"]
    if first not in ("A", "B") or relation is None or start is None:
        raise ValueError("4x4 exact stratum dimensions are invalid")
    if band not in _VECTOR_BANDS:
        raise ValueError("4x4 exact vector band is invalid")
    return "f{}-{}-{}-{}".format(first, relation, start, band)


def _case_fingerprint(value: Mapping[str, Any]) -> str:
    payload = dict(value)
    payload.pop("case_fingerprint", None)
    return _domain_digest(_CASE_FINGERPRINT_DOMAIN, payload)


def _normalize_case(raw: Any, index: int) -> Dict[str, Any]:
    case = _exact_keys(
        raw,
        (
            "case_id",
            "stratum_id",
            "stratum",
            "selection_rank",
            "selection_score",
            "definition_hash",
            "d4_canonical_hash",
            "vector_count",
            "definition",
            "state_bound",
            "case_fingerprint",
        ),
        "4x4 exact manifest case",
    )
    definition = validate_four_by_four_calibration_definition(case["definition"])
    exact_hash = definition_hash(definition)
    orbit_hash = d4_canonical_hash(definition)
    if _sha256(case["definition_hash"], "4x4 definition hash") != exact_hash:
        raise ValueError("4x4 exact case definition hash mismatch")
    if _sha256(case["d4_canonical_hash"], "4x4 D4 hash") != orbit_hash:
        raise ValueError("4x4 exact case D4 hash mismatch")
    if mechanical_json(definition) != canonicalize_d4(definition).mechanical_json:
        raise ValueError("4x4 exact case must retain the canonical D4 orientation")

    expected_stratum = four_by_four_calibration_stratum(definition)
    if _canonical_bytes(case["stratum"]) != _canonical_bytes(expected_stratum):
        raise ValueError("4x4 exact case stratum mismatch")
    expected_stratum_id = _stratum_id(expected_stratum)
    if case["stratum_id"] != expected_stratum_id:
        raise ValueError("4x4 exact case stratum identifier mismatch")
    case_id = _nonempty_string(case["case_id"], "4x4 case_id")
    if case_id != "four-by-four-calibration-v1-" + expected_stratum_id:
        raise ValueError("4x4 exact case identifier mismatch")
    _strict_int(case["selection_rank"], "selection_rank", expected=1)
    selection_score = _sha256(case["selection_score"], "selection_score")
    vector_count = _strict_int(case["vector_count"], "vector_count", minimum=1)
    if vector_count != len(definition.role(Player.B).action.vectors):
        raise ValueError("4x4 exact case vector count mismatch")
    state_bound = _strict_int(case["state_bound"], "state_bound", minimum=1)
    if state_bound != four_by_four_state_upper_bound(definition):
        raise ValueError("4x4 exact case state bound mismatch")
    case_fingerprint = _sha256(case["case_fingerprint"], "case_fingerprint")
    if case_fingerprint != _case_fingerprint(case):
        raise ValueError("4x4 exact case fingerprint does not reconstruct")

    return {
        "case_index": index,
        "case_id": case_id,
        "stratum_id": expected_stratum_id,
        "stratum": _copy(expected_stratum, "4x4 stratum"),
        "selection_rank": 1,
        "selection_score": selection_score,
        "definition_hash": exact_hash,
        "d4_canonical_hash": orbit_hash,
        "vector_count": vector_count,
        "definition": definition.to_dict(),
        "state_bound": state_bound,
        "case_fingerprint": case_fingerprint,
    }


def _manifest_cases(
    manifest: Any,
    historical_projection: Mapping[str, Any],
) -> Tuple[Tuple[Dict[str, Any], ...], str, str]:
    original = manifest
    snapshot = _copy(original, "4x4 exact manifest")
    history_snapshot = _copy(
        historical_projection, "4x4 exact historical projection"
    )
    original_bytes = _canonical_bytes(snapshot)
    history_bytes = _canonical_bytes(history_snapshot)
    if not isinstance(snapshot, Mapping):
        raise ValueError("4x4 exact evaluation requires the frozen manifest object")
    original_cases = snapshot.get("cases")
    if not isinstance(original_cases, list):
        raise ValueError("4x4 exact manifest must expose a cases array")

    validated_cases = validate_four_by_four_calibration_manifest(
        original, historical_projection
    )
    if _canonical_bytes(original) != original_bytes:
        raise ValueError("manifest validation mutated the frozen manifest input")
    if _canonical_bytes(historical_projection) != history_bytes:
        raise ValueError("manifest validation mutated the closed-history input")
    if _canonical_bytes(validated_cases) != _canonical_bytes(original_cases):
        raise ValueError("manifest validation replaced the frozen cases array")

    if len(original_cases) != FOUR_BY_FOUR_CASE_COUNT:
        raise ValueError(
            "4x4 exact case count must be {}".format(FOUR_BY_FOUR_CASE_COUNT)
        )
    cases = tuple(_normalize_case(case, index) for index, case in enumerate(original_cases))
    unique_fields = (
        "case_id",
        "stratum_id",
        "definition_hash",
        "d4_canonical_hash",
        "case_fingerprint",
    )
    for field in unique_fields:
        values = [case[field] for case in cases]
        if len(values) != len(set(values)):
            raise ValueError("4x4 exact {} values must be unique".format(field))
    if tuple(case["stratum_id"] for case in cases) != _ORDERED_STRATUM_IDS:
        raise ValueError("4x4 exact cases must follow the frozen stratum order")
    if Counter(case["stratum"]["first_player"] for case in cases) != {
        "A": 16,
        "B": 16,
    }:
        raise ValueError("4x4 exact corpus first-player balance mismatch")
    if sum(case["state_bound"] for case in cases) != FOUR_BY_FOUR_FIXED_CORPUS_STATE_BOUND:
        raise ValueError("4x4 exact corpus state-bound sum mismatch")

    manifest_id = _nonempty_string(snapshot.get("manifest_id"), "manifest_id")
    return cases, hashlib.sha256(original_bytes).hexdigest(), manifest_id


def _schedule_from_cases(cases: Sequence[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    return [
        {
            "schedule_index": index,
            "case_index": case["case_index"],
            "case_id": case["case_id"],
            "stratum_id": case["stratum_id"],
            "definition_hash": case["definition_hash"],
            "d4_canonical_hash": case["d4_canonical_hash"],
            "case_fingerprint": case["case_fingerprint"],
            "state_bound": case["state_bound"],
        }
        for index, case in enumerate(cases)
    ]


def four_by_four_exact_schedule(
    manifest: Mapping[str, Any],
    historical_projection: Mapping[str, Any],
) -> list[Dict[str, Any]]:
    """Return the fixed 32-case exact schedule in manifest order."""

    cases, _, _ = _manifest_cases(manifest, historical_projection)
    return _copy(_schedule_from_cases(cases), "4x4 exact schedule")


def derive_four_by_four_exact_trace(
    definition_value: Any, actions: Sequence[Any]
) -> Dict[str, Any]:
    """Replay one stored principal variation to a terminal 4x4 state."""

    definition = validate_four_by_four_calibration_definition(definition_value)
    if not isinstance(actions, (list, tuple)):
        raise ValueError("4x4 exact principal variation must be an array")
    state = initial_state(definition)
    normalized_actions = []
    for raw_action in actions:
        if not isinstance(raw_action, Mapping):
            raise ValueError("4x4 exact principal-variation actions must be objects")
        action = action_from_dict(raw_action)
        if action not in legal_actions(definition, state):
            raise ValueError("4x4 exact principal variation contains an illegal action")
        state = apply_action(definition, state, action)
        normalized_actions.append(action.to_dict())
    if not state.terminal or state.outcome is None:
        raise ValueError("4x4 exact principal variation must end at a terminal state")
    trace = {
        "trace_version": 1,
        "definition_hash": definition_hash(definition),
        "actions": normalized_actions,
        "terminal_ply": state.ply,
        "terminal_outcome": state.outcome.to_dict(),
        "final_state": state.to_dict(),
    }
    trace["trace_digest"] = _domain_digest(_EXACT_TRACE_DOMAIN, trace)
    return _copy(trace, "4x4 exact trace")


def _normalize_exact_evidence(
    definition: GameDefinition,
    value: Any,
    *,
    max_states: int,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    exact = _exact_keys(
        value,
        ("status", "result", "budget_observation"),
        "4x4 exact slot evidence",
    )
    status = exact["status"]
    if status == "CENSORED_STATE_BUDGET":
        budget = _exact_keys(
            exact["budget_observation"],
            ("searched_states", "max_states"),
            "4x4 exact censor observation",
        )
        searched = _strict_int(
            budget["searched_states"],
            "censored searched_states",
            minimum=1,
            expected=max_states,
        )
        _strict_int(
            budget["max_states"],
            "censored max_states",
            minimum=1,
            expected=max_states,
        )
        state_bound = four_by_four_state_upper_bound(definition)
        if exact["result"] is not None or searched <= state_bound:
            raise ValueError(
                "4x4 exact censor must witness the declared cap beyond the proved bound"
            )
        raise ValueError(
            "4x4 exact state-budget censor contradicts the public structural proof"
        )
    if status != "COMPLETED" or exact["budget_observation"] is not None:
        raise ValueError("4x4 exact evidence has an unknown or inconsistent status")

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
        "4x4 exact result",
    )
    forced = result["forced_result"]
    if (
        forced not in _VALUE_BY_RESULT
        or type(result["value_for_a"]) is not int
        or result["value_for_a"] != _VALUE_BY_RESULT[forced]
    ):
        raise ValueError("4x4 exact forced-result/value encoding mismatch")
    searched = validate_four_by_four_searched_states(
        result["searched_states"], definition
    )
    if searched > max_states:
        raise ValueError("completed 4x4 exact result exceeds its execution cap")
    cache_hits = _strict_int(result["cache_hits"], "4x4 exact cache_hits")
    pv = result["principal_variation"]
    pv_plies = _strict_int(
        result["principal_variation_plies"],
        "4x4 exact principal_variation_plies",
    )
    if not isinstance(pv, list) or pv_plies != len(pv) or pv_plies > 8:
        raise ValueError("4x4 exact principal variation length mismatch")
    terminal_reason = _nonempty_string(
        result["terminal_reason"], "4x4 exact terminal_reason"
    )
    trace = derive_four_by_four_exact_trace(definition, pv)
    expected_winner = {"A_WIN": "A", "B_WIN": "B", "DRAW": None}[forced]
    if (
        trace["terminal_outcome"]["winner"] != expected_winner
        or trace["terminal_outcome"]["reason"] != terminal_reason
        or trace["terminal_ply"] != pv_plies
    ):
        raise ValueError("4x4 exact principal-variation claim does not replay")
    if searched < pv_plies + 1:
        raise ValueError("4x4 exact searched_states cannot cover its replayed PV")
    if cache_hits < pv_plies:
        raise ValueError("4x4 exact cache_hits cannot cover PV reconstruction")
    if (forced == "DRAW") != (terminal_reason == "PLY_LIMIT"):
        raise ValueError("4x4 exact draw must be exactly a PLY_LIMIT horizon label")
    normalized_result = {
        "value_for_a": result["value_for_a"],
        "forced_result": forced,
        "principal_variation": trace["actions"],
        "principal_variation_plies": pv_plies,
        "terminal_reason": terminal_reason,
        "searched_states": searched,
        "cache_hits": cache_hits,
    }
    return (
        {
            "status": "COMPLETED",
            "result": normalized_result,
            "budget_observation": None,
        },
        trace,
    )


def validate_four_by_four_exact_evidence(
    definition_value: Any,
    value: Any,
) -> Dict[str, Any]:
    """Validate one raw solver payload and publicly replay its PV."""

    definition = validate_four_by_four_calibration_definition(definition_value)
    exact, trace = _normalize_exact_evidence(
        definition, value, max_states=FOUR_BY_FOUR_EXACT_MAX_STATES
    )
    return {
        "exact": exact,
        "principal_variation_trace": trace,
    }


def _normalize_exact_slot(
    case: Mapping[str, Any],
    expected: Mapping[str, Any],
    raw_slot: Any,
    *,
    max_states: int,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    slot = _exact_keys(
        raw_slot,
        (
            "schedule_index",
            "case_index",
            "case_id",
            "stratum_id",
            "definition_hash",
            "d4_canonical_hash",
            "case_fingerprint",
            "state_bound",
            "exact",
            "elapsed_seconds",
        ),
        "4x4 exact schedule slot",
    )
    identity_fields = (
        "schedule_index",
        "case_index",
        "case_id",
        "stratum_id",
        "definition_hash",
        "d4_canonical_hash",
        "case_fingerprint",
        "state_bound",
    )
    for field in identity_fields:
        if _canonical_bytes(slot[field]) != _canonical_bytes(expected[field]):
            raise ValueError("4x4 exact schedule identity/order mismatch")
    definition = parse_definition(case["definition"])
    exact, trace = _normalize_exact_evidence(
        definition, slot["exact"], max_states=max_states
    )
    normalized = {
        **expected,
        "exact": exact,
        "elapsed_seconds": _elapsed_seconds(
            slot["elapsed_seconds"], "4x4 exact slot elapsed_seconds"
        ),
    }
    return normalized, trace


def _exact_slots_digest(slots: Sequence[Mapping[str, Any]]) -> str:
    timing_free = [
        {key: value for key, value in slot.items() if key != "elapsed_seconds"}
        for slot in slots
    ]
    return _domain_digest(_EXACT_SLOTS_DOMAIN, timing_free)


def _calibration_label(exact: Mapping[str, Any]) -> str:
    if exact["status"] != "COMPLETED":
        raise ValueError("4x4 calibration labels require completed exact evidence")
    result = exact["result"]
    if result["forced_result"] == "DRAW":
        return "HORIZON_DRAW"
    return result["forced_result"]


def assess_four_by_four_exact_coverage(
    label_records: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Apply the frozen exact-label coverage thresholds to 32 fixed records."""

    if not isinstance(label_records, (list, tuple)) or len(
        label_records
    ) != FOUR_BY_FOUR_CASE_COUNT:
        raise ValueError("4x4 exact coverage requires exactly 32 label records")
    normalized = []
    for raw in label_records:
        record = _exact_keys(
            raw,
            (
                "case_id",
                "stratum_id",
                "status",
                "forced_result",
                "terminal_reason",
            ),
            "4x4 exact coverage record",
        )
        case_id = _nonempty_string(record["case_id"], "coverage case_id")
        stratum_id = _nonempty_string(record["stratum_id"], "coverage stratum_id")
        if case_id != "four-by-four-calibration-v1-" + stratum_id:
            raise ValueError("4x4 exact coverage case/stratum identity mismatch")
        if record["status"] == "COMPLETED":
            forced = record["forced_result"]
            reason = record["terminal_reason"]
            if forced not in _VALUE_BY_RESULT or not isinstance(reason, str) or not reason:
                raise ValueError("completed 4x4 coverage record has an invalid label")
            if (forced == "DRAW") != (reason == "PLY_LIMIT"):
                raise ValueError("4x4 coverage draw must be a PLY_LIMIT horizon label")
            if forced in ("A_WIN", "B_WIN") and reason not in (
                "GOAL",
                "NO_LEGAL_ACTION",
            ):
                raise ValueError("4x4 decisive coverage terminal reason is invalid")
            label = "HORIZON_DRAW" if forced == "DRAW" else forced
        else:
            raise ValueError("4x4 exact coverage record has an unknown status")
        normalized.append(
            {
                "case_id": case_id,
                "stratum_id": stratum_id,
                "label": label,
            }
        )
    for field in ("case_id", "stratum_id"):
        values = [record[field] for record in normalized]
        if len(values) != len(set(values)):
            raise ValueError("4x4 exact coverage {} values must be unique".format(field))
    if tuple(record["stratum_id"] for record in normalized) != _ORDERED_STRATUM_IDS:
        raise ValueError("4x4 exact coverage records must follow all 32 frozen strata")

    counts = Counter(record["label"] for record in normalized)
    strata_by_label = {
        label: [
            record["stratum_id"] for record in normalized if record["label"] == label
        ]
        for label in _CALIBRATION_LABELS
    }
    decisive_count = counts["A_WIN"] + counts["B_WIN"]
    requirements = {
        "case_count": FOUR_BY_FOUR_CASE_COUNT,
        "minimum_decisive_count": FOUR_BY_FOUR_MIN_DECISIVE_LABELS,
        "minimum_A_win_count": FOUR_BY_FOUR_MIN_A_WINS,
        "minimum_B_win_count": FOUR_BY_FOUR_MIN_B_WINS,
        "minimum_horizon_draw_count": FOUR_BY_FOUR_MIN_HORIZON_DRAWS,
        "minimum_strata_per_label": FOUR_BY_FOUR_MIN_STRATA_PER_LABEL,
    }
    shortfalls = []
    checks = (
        (
            decisive_count >= FOUR_BY_FOUR_MIN_DECISIVE_LABELS,
            "DECISIVE_COUNT_BELOW_15",
        ),
        (counts["A_WIN"] >= FOUR_BY_FOUR_MIN_A_WINS, "A_WIN_COUNT_BELOW_4"),
        (counts["B_WIN"] >= FOUR_BY_FOUR_MIN_B_WINS, "B_WIN_COUNT_BELOW_4"),
        (
            counts["HORIZON_DRAW"] >= FOUR_BY_FOUR_MIN_HORIZON_DRAWS,
            "HORIZON_DRAW_COUNT_BELOW_4",
        ),
        (
            len(strata_by_label["A_WIN"]) >= FOUR_BY_FOUR_MIN_STRATA_PER_LABEL,
            "A_WIN_STRATA_BELOW_2",
        ),
        (
            len(strata_by_label["B_WIN"]) >= FOUR_BY_FOUR_MIN_STRATA_PER_LABEL,
            "B_WIN_STRATA_BELOW_2",
        ),
        (
            len(strata_by_label["HORIZON_DRAW"])
            >= FOUR_BY_FOUR_MIN_STRATA_PER_LABEL,
            "HORIZON_DRAW_STRATA_BELOW_2",
        ),
    )
    shortfalls.extend(code for passes, code in checks if not passes)
    if shortfalls:
        status = "INCONCLUSIVE_LABEL_COVERAGE"
        integrity_status = "PASSED"
        coverage_trusted = True
        depth5_disposition = "BLOCKED_LABEL_COVERAGE"
        next_branch = "RETIRE_PLACE_VS_MOVE_FAMILY"
    else:
        status = "SUFFICIENT_LABEL_COVERAGE"
        integrity_status = "PASSED"
        coverage_trusted = True
        depth5_disposition = "ELIGIBLE"
        next_branch = "RUN_FIXED_DEPTH5_AFTER_COMMITTED_RESERVATION"
    return {
        "status": status,
        "integrity_status": integrity_status,
        "coverage_trusted": coverage_trusted,
        "requirements": requirements,
        "observed": {
            "case_count": len(normalized),
            "completed_count": len(normalized),
            "censored_count": 0,
            "decisive_count": decisive_count,
            "label_counts": {
                label: counts[label] for label in _CALIBRATION_LABELS
            },
            "label_stratum_counts": {
                label: len(strata_by_label[label]) for label in _CALIBRATION_LABELS
            },
        },
        "label_strata": strata_by_label,
        "shortfalls": shortfalls,
        "depth5_disposition": depth5_disposition,
        "next_branch": next_branch,
    }


def _case_record(
    case: Mapping[str, Any],
    slot: Mapping[str, Any],
    trace: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    exact = slot["exact"]
    label = _calibration_label(exact)
    if exact["status"] != "COMPLETED" or trace is None:
        raise ValueError("4x4 exact case records require completed replayed evidence")
    result = exact["result"]
    searched_states = result["searched_states"]
    return {
        "case_index": case["case_index"],
        "case_id": case["case_id"],
        "stratum_id": case["stratum_id"],
        "stratum": _copy(case["stratum"], "4x4 exact record stratum"),
        "definition_hash": case["definition_hash"],
        "d4_canonical_hash": case["d4_canonical_hash"],
        "case_fingerprint": case["case_fingerprint"],
        "selection_rank": case["selection_rank"],
        "selection_score": case["selection_score"],
        "vector_count": case["vector_count"],
        "definition": _copy(case["definition"], "4x4 exact record definition"),
        "state_bound": case["state_bound"],
        "exact": _copy(exact, "4x4 exact record evidence"),
        "principal_variation_trace": _copy(trace, "4x4 exact record trace"),
        "calibration_label": label,
        "forced_result": result["forced_result"],
        "terminal_reason": result["terminal_reason"],
        "principal_variation_plies": result["principal_variation_plies"],
        "searched_states": searched_states,
        "cache_hits": result["cache_hits"],
        "state_bound_margin": case["state_bound"] - searched_states,
        "execution_cap_margin": FOUR_BY_FOUR_EXACT_MAX_STATES - searched_states,
    }


def _fixed_histogram(values: Iterable[str], keys: Sequence[str]) -> Dict[str, int]:
    counter = Counter(values)
    return {key: counter[key] for key in keys}


def _integer_histogram(values: Iterable[int]) -> Dict[str, int]:
    counter = Counter(values)
    return {str(value): counter[value] for value in sorted(counter)}


def _group_summary(records: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    completed = [record for record in records if record["exact"]["status"] == "COMPLETED"]
    censored = [record for record in records if record["exact"]["status"] != "COMPLETED"]
    completed_search = [record["searched_states"] for record in completed]
    return {
        "case_count": len(records),
        "completed_count": len(completed),
        "censored_count": len(censored),
        "calibration_labels": _fixed_histogram(
            (record["calibration_label"] for record in records),
            _CALIBRATION_LABELS,
        ),
        "forced_results": _fixed_histogram(
            (record["forced_result"] for record in completed),
            ("A_WIN", "B_WIN", "DRAW"),
        ),
        "terminal_reasons": _fixed_histogram(
            (record["terminal_reason"] for record in completed),
            _TERMINAL_REASONS,
        ),
        "searched_states_total": sum(record["searched_states"] for record in records),
        "completed_searched_states_total": sum(completed_search),
        "completed_searched_states_max": max(completed_search) if completed_search else None,
        "cache_hits_total": sum(record["cache_hits"] for record in completed),
        "principal_variation_plies_histogram": _integer_histogram(
            record["principal_variation_plies"] for record in completed
        ),
        "state_bound_total": sum(record["state_bound"] for record in records),
        "state_bound_margin_total": sum(record["state_bound_margin"] for record in records),
        "execution_cap_margin_total": sum(
            record["execution_cap_margin"] for record in records
        ),
    }


def _exact_breakdowns(records: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    return {
        "all": _group_summary(records),
        "by_first_player": {
            first: _group_summary(
                [record for record in records if record["stratum"]["first_player"] == first]
            )
            for first in ("A", "B")
        },
        "by_goal_axis_relation": {
            relation: _group_summary(
                [
                    record
                    for record in records
                    if record["stratum"]["goal_axis_relation"] == relation
                ]
            )
            for relation in ("ALIGNED", "ORTHOGONAL")
        },
        "by_runner_start_class": {
            start: _group_summary(
                [
                    record
                    for record in records
                    if record["stratum"]["runner_start_class"] == start
                ]
            )
            for start in ("CORNER", "EDGE_INTERIOR")
        },
        "by_vector_band": {
            band: _group_summary(
                [record for record in records if record["stratum"]["vector_band"] == band]
            )
            for band in _VECTOR_BANDS
        },
        "by_stratum": {
            stratum_id: _group_summary(
                [record for record in records if record["stratum_id"] == stratum_id]
            )
            for stratum_id in _ORDERED_STRATUM_IDS
        },
    }


def _coverage_records(records: Sequence[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    return [
        {
            "case_id": record["case_id"],
            "stratum_id": record["stratum_id"],
            "status": record["exact"]["status"],
            "forced_result": record["forced_result"],
            "terminal_reason": record["terminal_reason"],
        }
        for record in records
    ]


def _build_inspection(
    records: Sequence[Mapping[str, Any]], assessment: Mapping[str, Any]
) -> Dict[str, Any]:
    reason_by_label = {
        "A_WIN": "EXACT_A",
        "B_WIN": "EXACT_B",
        "HORIZON_DRAW": "EXACT_HORIZON_DRAW",
    }
    rows = []
    for record in records:
        trace = record["principal_variation_trace"]
        rows.append(
            {
                "case_index": record["case_index"],
                "case_id": record["case_id"],
                "stratum_id": record["stratum_id"],
                "stratum": _copy(record["stratum"], "4x4 inspection stratum"),
                "definition_hash": record["definition_hash"],
                "d4_canonical_hash": record["d4_canonical_hash"],
                "case_fingerprint": record["case_fingerprint"],
                "definition": _copy(
                    record["definition"], "4x4 inspection definition"
                ),
                "exact_status": record["exact"]["status"],
                "calibration_label": record["calibration_label"],
                "forced_result": record["forced_result"],
                "terminal_reason": record["terminal_reason"],
                "principal_variation_plies": record["principal_variation_plies"],
                "principal_variation_trace_digest": (
                    trace["trace_digest"] if trace is not None else None
                ),
                "searched_states": record["searched_states"],
                "cache_hits": record["cache_hits"],
                "state_bound": record["state_bound"],
                "state_bound_margin": record["state_bound_margin"],
                "execution_cap_margin": record["execution_cap_margin"],
                "reasons": [reason_by_label[record["calibration_label"]]],
            }
        )
    return {
        "inspection_version": 1,
        "disposition": assessment["status"],
        "reason_order": list(_INSPECTION_REASON_ORDER),
        "case_count": len(rows),
        "rows": rows,
    }


def _timing_summary(slots: Sequence[Mapping[str, Any]]) -> Dict[str, float]:
    values = [
        _elapsed_seconds(slot["elapsed_seconds"], "4x4 exact slot timing")
        for slot in slots
    ]
    total = _elapsed_seconds(sum(values), "4x4 exact total timing")
    mean = _elapsed_seconds(
        total / len(values), "4x4 exact mean slot timing"
    )
    return {
        "total_seconds": total,
        "minimum_slot_seconds": min(values),
        "maximum_slot_seconds": max(values),
        "mean_slot_seconds": mean,
    }


def build_four_by_four_exact_result(
    manifest: Mapping[str, Any],
    historical_projection: Mapping[str, Any],
    exact_slots: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Validate all 32 raw slots and derive the complete exact-stage artifact."""

    max_states = FOUR_BY_FOUR_EXACT_MAX_STATES
    cases, manifest_digest, manifest_id = _manifest_cases(
        manifest, historical_projection
    )
    schedule = _schedule_from_cases(cases)
    if not isinstance(exact_slots, (list, tuple)) or len(exact_slots) != len(schedule):
        raise ValueError("4x4 exact slots must cover the full fixed schedule")

    normalized_slots = []
    records = []
    for case, expected, raw_slot in zip(cases, schedule, exact_slots):
        slot, trace = _normalize_exact_slot(
            case, expected, raw_slot, max_states=max_states
        )
        normalized_slots.append(slot)
        records.append(_case_record(case, slot, trace))

    assessment = assess_four_by_four_exact_coverage(_coverage_records(records))
    breakdowns = _exact_breakdowns(records)
    all_summary = breakdowns["all"]
    inspection = _build_inspection(records, assessment)
    return {
        "result_version": FOUR_BY_FOUR_EXACT_RESULT_VERSION,
        "protocol_id": FOUR_BY_FOUR_EXACT_PROTOCOL_ID,
        "manifest_id": manifest_id,
        "manifest_digest": manifest_digest,
        "configuration": {
            "case_count": FOUR_BY_FOUR_CASE_COUNT,
            "max_states": max_states,
            "A_first_state_bound": FOUR_BY_FOUR_A_FIRST_STATE_BOUND,
            "B_first_state_bound": FOUR_BY_FOUR_B_FIRST_STATE_BOUND,
            "fixed_corpus_state_bound": FOUR_BY_FOUR_FIXED_CORPUS_STATE_BOUND,
            "state_bound_proof": build_four_by_four_state_bound_proof(),
            "schedule": "MANIFEST_ORDER_ALL_CASES",
            "horizon_semantics": "DRAW_PLY_LIMIT_IS_CALIBRATION_LABEL",
            "coverage_requirements": _copy(
                assessment["requirements"], "4x4 exact coverage requirements"
            ),
        },
        "schedule": schedule,
        "slots": normalized_slots,
        "cases": records,
        "aggregate": {
            "exact_attempted": len(normalized_slots),
            "exact_completed": len(normalized_slots),
            "exact_censored_count": 0,
            "exact_censored_slots": [],
            "evidence_digest": _exact_slots_digest(normalized_slots),
            "calibration_labels": all_summary["calibration_labels"],
            "forced_results": all_summary["forced_results"],
            "terminal_reasons": all_summary["terminal_reasons"],
            "searched_states_total": all_summary["searched_states_total"],
            "completed_searched_states_total": all_summary[
                "completed_searched_states_total"
            ],
            "cache_hits_total": all_summary["cache_hits_total"],
            "breakdowns": breakdowns,
        },
        "assessment": assessment,
        "inspection": inspection,
        "timing": _timing_summary(normalized_slots),
    }


def _exact_payload_from_solve(solved: Any) -> Dict[str, Any]:
    result = solved.to_dict() if hasattr(solved, "to_dict") else solved
    if not isinstance(result, Mapping):
        raise ValueError("4x4 exact solver must return SolveResult-compatible evidence")
    return {
        "status": "COMPLETED",
        "result": _copy(result, "4x4 solver result"),
        "budget_observation": None,
    }


def _evaluate_four_by_four_exact(
    manifest: Mapping[str, Any],
    historical_projection: Mapping[str, Any],
    *,
    solver: Callable[..., Any],
    clock: Callable[[], float],
) -> Dict[str, Any]:
    """Internal injectable executor used by the fixed public entry point."""

    max_states = FOUR_BY_FOUR_EXACT_MAX_STATES
    if not callable(solver) or not callable(clock):
        raise ValueError("4x4 exact solver and clock must be callable")
    cases, _, _ = _manifest_cases(manifest, historical_projection)
    schedule = _schedule_from_cases(cases)
    manifest_bytes = _canonical_bytes(manifest)
    history_bytes = _canonical_bytes(historical_projection)

    def require_stable_inputs() -> None:
        if _canonical_bytes(manifest) != manifest_bytes:
            raise ValueError("4x4 exact solver mutated the frozen manifest")
        if _canonical_bytes(historical_projection) != history_bytes:
            raise ValueError("4x4 exact solver mutated the closed-history witness")

    def stable_clock() -> float:
        try:
            observed = clock()
        except Exception as error:
            try:
                require_stable_inputs()
            except ValueError as mutation_error:
                raise mutation_error from error
            raise
        require_stable_inputs()
        return observed

    slots = []
    for case, entry in zip(cases, schedule):
        definition = parse_definition(case["definition"])
        started = stable_clock()
        try:
            solved = solver(definition, max_states=max_states)
            require_stable_inputs()
            exact = _exact_payload_from_solve(solved)
        except Exception as error:
            try:
                require_stable_inputs()
            except ValueError as mutation_error:
                raise mutation_error from error
            raise
        require_stable_inputs()
        elapsed = _elapsed_seconds(
            stable_clock() - started, "4x4 exact elapsed_seconds"
        )
        raw_slot = {**entry, "exact": exact, "elapsed_seconds": elapsed}
        normalized, _ = _normalize_exact_slot(
            case, entry, raw_slot, max_states=max_states
        )
        slots.append(normalized)
    return build_four_by_four_exact_result(
        manifest,
        historical_projection,
        slots,
    )


def evaluate_four_by_four_exact(
    manifest: Mapping[str, Any],
    historical_projection: Mapping[str, Any],
) -> Dict[str, Any]:
    """Execute the fixed production-shaped exact schedule with ``solve_game``."""

    return _evaluate_four_by_four_exact(
        manifest,
        historical_projection,
        solver=solve_game,
        clock=time.perf_counter,
    )


def validate_four_by_four_exact_result(
    result: Mapping[str, Any],
    manifest: Mapping[str, Any],
    historical_projection: Mapping[str, Any],
) -> Dict[str, Any]:
    """Strictly reconstruct a complete exact artifact from its manifest and slots."""

    value = _exact_keys(
        _copy(result, "4x4 exact result"),
        (
            "result_version",
            "protocol_id",
            "manifest_id",
            "manifest_digest",
            "configuration",
            "schedule",
            "slots",
            "cases",
            "aggregate",
            "assessment",
            "inspection",
            "timing",
        ),
        "4x4 exact result",
    )
    rebuilt = build_four_by_four_exact_result(
        manifest,
        historical_projection,
        value["slots"],
    )
    if _canonical_bytes(value) != _canonical_bytes(rebuilt):
        raise ValueError("4x4 exact result does not reconstruct")
    return _copy(value, "validated 4x4 exact result")


__all__ = (
    "FOUR_BY_FOUR_EXACT_PROTOCOL_ID",
    "FOUR_BY_FOUR_EXACT_RESULT_VERSION",
    "FOUR_BY_FOUR_MIN_DECISIVE_LABELS",
    "FOUR_BY_FOUR_MIN_A_WINS",
    "FOUR_BY_FOUR_MIN_B_WINS",
    "FOUR_BY_FOUR_MIN_HORIZON_DRAWS",
    "FOUR_BY_FOUR_MIN_STRATA_PER_LABEL",
    "assess_four_by_four_exact_coverage",
    "build_four_by_four_exact_result",
    "derive_four_by_four_exact_trace",
    "evaluate_four_by_four_exact",
    "four_by_four_exact_schedule",
    "validate_four_by_four_exact_evidence",
    "validate_four_by_four_exact_result",
)
