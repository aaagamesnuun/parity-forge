"""Pure depth-5 evaluation for Plan 0011's fixed 4x4 calibration.

The public executor is deliberately non-injectable: it always uses depth 5,
seeds 0..29, one fresh ``MinimaxAgent`` per definition, and one cumulative
5,000,000-node allowance.  Test doubles live only behind the private executor
seam.  Raw evidence can prove replay, ordering, and node-ledger consistency;
the concrete agent implementation is bound later by the one-shot executable
fingerprint boundary.

This module owns no filesystem, Git, reservation, lock, or artifact-writing
capability.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import time
from collections import Counter
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from .agents import AgentIdentity, MinimaxAgent, SearchBudgetExceeded
from .audit import sampled_direction
from .dsl import GameDefinition, definition_hash, parse_definition
from .engine import Action, action_from_dict, apply_action, initial_state, legal_actions
from .four_by_four_calibration import (
    FOUR_BY_FOUR_CASE_COUNT,
    validate_four_by_four_calibration_definition,
)
from .four_by_four_evaluation import (
    FOUR_BY_FOUR_MIN_A_WINS,
    FOUR_BY_FOUR_MIN_B_WINS,
    FOUR_BY_FOUR_MIN_DECISIVE_LABELS,
    FOUR_BY_FOUR_MIN_HORIZON_DRAWS,
    FOUR_BY_FOUR_MIN_STRATA_PER_LABEL,
    validate_four_by_four_exact_result,
)


FOUR_BY_FOUR_DEPTH5_RESULT_VERSION = 1
FOUR_BY_FOUR_DEPTH5_PROTOCOL_ID = "four-by-four-calibration-v1-fixed-depth5"
FOUR_BY_FOUR_DEPTH = 5
FOUR_BY_FOUR_DEPTH5_SEEDS = tuple(range(30))
FOUR_BY_FOUR_DEPTH5_MAX_NODES = 5_000_000
FOUR_BY_FOUR_DEPTH5_PROFILE = "minimax-v1-depth5"
FOUR_BY_FOUR_TRANSFER_ACCURACY_NUMERATOR = 9
FOUR_BY_FOUR_TRANSFER_ACCURACY_DENOMINATOR = 10

_DIRECTIONS = ("A_WIN", "B_WIN", "DRAW_OR_BALANCED")
_EXACT_LABELS = ("A_WIN", "B_WIN", "HORIZON_DRAW")
_TERMINAL_REASONS = ("GOAL", "NO_LEGAL_ACTION", "PLY_LIMIT")
_VECTOR_BANDS = ("v1_3", "v4", "v5", "v6_7")
_ORDERED_STRATUM_IDS = tuple(
    "f{}-{}-{}-{}".format(first, relation, start, band)
    for first in ("A", "B")
    for relation in ("aligned", "orthogonal")
    for start in ("corner", "edge_inner")
    for band in _VECTOR_BANDS
)
_PROFILE_SLOTS_DOMAIN = b"four-by-four-calibration-v1-depth5-slots-v1"
_PROFILE_TRACE_DOMAIN = b"four-by-four-calibration-v1-depth5-trace-v1"
_EXACT_RESULT_DOMAIN = b"four-by-four-calibration-v1-upstream-exact-v1"
_INSPECTION_REASON_ORDER = (
    "EXACT_A",
    "EXACT_B",
    "EXACT_HORIZON_DRAW",
    "NODE_CENSOR",
    "DIRECTION_MISMATCH",
    "EXACT_DRAW_DECISIVE_ERROR",
)
_FROZEN_PLAY_GATES = {
    "max_draw_rate": 0.50,
    "min_average_plies": 4.0,
    "max_average_plies_fraction": 0.85,
    "dominance_interval_margin": 0.05,
}


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
        raise ValueError("4x4 depth evidence must be finite canonical JSON") from error


def _copy(value: Any, label: str) -> Any:
    try:
        return json.loads(_canonical_bytes(value))
    except (TypeError, ValueError) as error:
        raise ValueError("{} must be finite canonical JSON".format(label)) from error


def _exact_keys(value: Any, expected: Iterable[str], label: str) -> Mapping[str, Any]:
    expected_set = set(expected)
    if not isinstance(value, Mapping) or set(value) != expected_set:
        raise ValueError("{} keys must be exactly {}".format(label, sorted(expected_set)))
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


def _domain_digest(domain: bytes, value: Any) -> str:
    return hashlib.sha256(domain + b"\0" + _canonical_bytes(value)).hexdigest()


def _timing_free(value: Mapping[str, Any]) -> Dict[str, Any]:
    projection = _copy(value, "timing-free projection")
    projection.pop("timing", None)
    slots = projection.get("slots")
    if isinstance(slots, list):
        for slot in slots:
            if isinstance(slot, dict):
                slot.pop("elapsed_seconds", None)
    return projection


def _exact_result_digest(exact: Mapping[str, Any]) -> str:
    return _domain_digest(_EXACT_RESULT_DOMAIN, _timing_free(exact))


def _validated_context(
    manifest: Mapping[str, Any],
    historical_projection: Mapping[str, Any],
    exact_result: Mapping[str, Any],
) -> Tuple[Tuple[Dict[str, Any], ...], Dict[str, Any], str, str]:
    manifest_bytes = _canonical_bytes(manifest)
    history_bytes = _canonical_bytes(historical_projection)
    exact_bytes = _canonical_bytes(exact_result)
    exact = validate_four_by_four_exact_result(
        exact_result, manifest, historical_projection
    )
    if _canonical_bytes(manifest) != manifest_bytes:
        raise ValueError("depth input validation mutated the frozen manifest")
    if _canonical_bytes(historical_projection) != history_bytes:
        raise ValueError("depth input validation mutated the closed-history witness")
    if _canonical_bytes(exact_result) != exact_bytes:
        raise ValueError("depth input validation mutated the upstream exact result")
    aggregate = exact.get("aggregate")
    assessment = exact.get("assessment")
    if (
        not isinstance(aggregate, Mapping)
        or aggregate.get("exact_completed") != FOUR_BY_FOUR_CASE_COUNT
        or aggregate.get("exact_censored_count") != 0
        or not isinstance(assessment, Mapping)
        or assessment.get("status") != "SUFFICIENT_LABEL_COVERAGE"
        or assessment.get("integrity_status") != "PASSED"
        or assessment.get("coverage_trusted") is not True
        or assessment.get("depth5_disposition") != "ELIGIBLE"
    ):
        raise ValueError("4x4 depth-5 requires sufficient trusted complete exact labels")
    cases = exact.get("cases")
    if not isinstance(cases, list) or len(cases) != FOUR_BY_FOUR_CASE_COUNT:
        raise ValueError("4x4 depth-5 exact case array is incomplete")
    normalized_cases = tuple(_copy(case, "4x4 depth exact case") for case in cases)
    manifest_digest = _nonempty_string(exact.get("manifest_digest"), "manifest digest")
    upstream_evidence = aggregate.get("evidence_digest")
    if not isinstance(upstream_evidence, str) or len(upstream_evidence) != 64:
        raise ValueError("upstream exact evidence digest is malformed")
    return (
        normalized_cases,
        exact,
        manifest_digest,
        _exact_result_digest(exact),
    )


def _schedule_from_cases(cases: Sequence[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    schedule = []
    for index, case in enumerate(cases):
        entry = {
            "schedule_index": index,
            "case_index": case["case_index"],
            "case_id": case["case_id"],
            "stratum_id": case["stratum_id"],
            "definition_hash": case["definition_hash"],
            "d4_canonical_hash": case["d4_canonical_hash"],
            "case_fingerprint": case["case_fingerprint"],
        }
        schedule.append(entry)
    return schedule


def four_by_four_depth5_schedule(
    manifest: Mapping[str, Any],
    historical_projection: Mapping[str, Any],
    exact_result: Mapping[str, Any],
) -> list[Dict[str, Any]]:
    """Return the fixed manifest-order 32-profile schedule."""

    cases, _, _, _ = _validated_context(
        manifest, historical_projection, exact_result
    )
    return _copy(_schedule_from_cases(cases), "4x4 depth-5 schedule")


def derive_four_by_four_depth5_trace(
    definition_value: Any,
    actions: Sequence[Any],
    *,
    require_terminal: bool = True,
) -> Dict[str, Any]:
    """Replay one complete game or node-censored action prefix."""

    if type(require_terminal) is not bool:
        raise ValueError("require_terminal must be a boolean")
    definition = validate_four_by_four_calibration_definition(definition_value)
    if not isinstance(actions, (list, tuple)):
        raise ValueError("4x4 depth action trace must be an array")
    state = initial_state(definition)
    normalized_actions = []
    root_legal_action_count_sum = 0
    for raw_action in actions:
        if not isinstance(raw_action, Mapping):
            raise ValueError("4x4 depth actions must be objects")
        action = action_from_dict(raw_action)
        choices = legal_actions(definition, state)
        if action not in choices:
            raise ValueError("4x4 depth trace contains an illegal action")
        root_legal_action_count_sum += len(choices)
        state = apply_action(definition, state, action)
        normalized_actions.append(action.to_dict())
    if require_terminal and not state.terminal:
        raise ValueError("complete 4x4 depth trace must end at a terminal state")
    trace = {
        "trace_version": 1,
        "definition_hash": definition_hash(definition),
        "actions": normalized_actions,
        "root_legal_action_count_sum": root_legal_action_count_sum,
        "is_terminal": state.terminal,
        "ply": state.ply,
        "terminal_outcome": state.outcome.to_dict() if state.outcome else None,
        "final_state": state.to_dict(),
    }
    trace["trace_digest"] = _domain_digest(_PROFILE_TRACE_DOMAIN, trace)
    return _copy(trace, "4x4 depth trace")


def _normalize_game(definition: GameDefinition, value: Any) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("4x4 depth sampled game must be an object")
    fields = set(value)
    minimal = {"seed", "actions", "terminal_outcome", "terminal_ply"}
    canonical = minimal | {"trace"}
    if fields not in (minimal, canonical):
        raise ValueError("4x4 depth sampled game fields mismatch")
    seed = _strict_int(value["seed"], "sampled game seed")
    claim = _exact_keys(
        value["terminal_outcome"], ("winner", "reason"), "sampled terminal outcome"
    )
    if claim["winner"] not in ("A", "B", None):
        raise ValueError("sampled terminal winner is malformed")
    _nonempty_string(claim["reason"], "sampled terminal reason")
    terminal_ply = _strict_int(value["terminal_ply"], "sampled terminal ply")
    trace = derive_four_by_four_depth5_trace(definition, value["actions"])
    if (
        _canonical_bytes(claim) != _canonical_bytes(trace["terminal_outcome"])
        or terminal_ply != trace["ply"]
    ):
        raise ValueError("4x4 sampled terminal claim does not replay")
    if "trace" in value and _canonical_bytes(value["trace"]) != _canonical_bytes(trace):
        raise ValueError("stored 4x4 sampled trace does not reconstruct")
    return {
        "seed": seed,
        "actions": trace["actions"],
        "terminal_outcome": trace["terminal_outcome"],
        "terminal_ply": terminal_ply,
        "trace": trace,
    }


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


def _profile_summary(games: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    a_wins = sum(game["terminal_outcome"]["winner"] == "A" for game in games)
    b_wins = sum(game["terminal_outcome"]["winner"] == "B" for game in games)
    draws = len(games) - a_wins - b_wins
    decisive = a_wins + b_wins
    reasons = Counter(game["terminal_outcome"]["reason"] for game in games)
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
        "decisive_count": decisive,
        "decisive_a_share": a_wins / decisive if decisive else None,
        "decisive_a_wilson_95": _wilson_interval(a_wins, decisive),
        "terminal_reasons": {reason: reasons[reason] for reason in _TERMINAL_REASONS},
        "seeds": [game["seed"] for game in games],
    }


def _build_profile_evidence(
    definition_value: Any,
    games: Sequence[Any],
    *,
    incomplete_seed: Optional[int] = None,
    budget_observation: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    definition = validate_four_by_four_calibration_definition(definition_value)
    if not isinstance(games, (list, tuple)):
        raise ValueError("4x4 depth profile games must be an array")
    normalized = tuple(_normalize_game(definition, game) for game in games)
    game_seeds = tuple(game["seed"] for game in normalized)
    seeds = FOUR_BY_FOUR_DEPTH5_SEEDS
    if incomplete_seed is None:
        if game_seeds != seeds or budget_observation is not None:
            raise ValueError("complete 4x4 depth profile must contain seeds 0..29")
        result = {
            "status": "COMPLETED",
            "profile": FOUR_BY_FOUR_DEPTH5_PROFILE,
            "expected_seeds": list(seeds),
            "completed_seed_prefix": list(seeds),
            "incomplete_seed": None,
            "games": list(normalized),
            "profile_summary": _profile_summary(normalized),
            "partial_summary": None,
            "budget_observation": None,
        }
    else:
        incomplete_seed = _strict_int(incomplete_seed, "incomplete seed")
        if (
            len(game_seeds) >= len(seeds)
            or game_seeds != seeds[: len(game_seeds)]
            or incomplete_seed != seeds[len(game_seeds)]
        ):
            raise ValueError("censored profile must retain a strict seed prefix")
        budget = _exact_keys(
            budget_observation,
            ("visited_nodes", "max_nodes", "scope"),
            "4x4 depth budget observation",
        )
        _strict_int(
            budget["visited_nodes"],
            "visited_nodes",
            expected=FOUR_BY_FOUR_DEPTH5_MAX_NODES,
        )
        _strict_int(
            budget["max_nodes"],
            "max_nodes",
            expected=FOUR_BY_FOUR_DEPTH5_MAX_NODES,
        )
        if budget["scope"] != "per-candidate":
            raise ValueError("4x4 depth censor scope must be per-candidate")
        result = {
            "status": "CENSORED_NODE_BUDGET",
            "profile": FOUR_BY_FOUR_DEPTH5_PROFILE,
            "expected_seeds": list(seeds),
            "completed_seed_prefix": list(game_seeds),
            "incomplete_seed": incomplete_seed,
            "games": list(normalized),
            "profile_summary": None,
            "partial_summary": _profile_summary(normalized),
            "budget_observation": _copy(budget, "4x4 depth budget"),
        }
    validate_four_by_four_depth5_profile_evidence(definition, result)
    return result


def build_four_by_four_depth5_profile_evidence(
    definition_value: Any, games: Sequence[Any]
) -> Dict[str, Any]:
    """Build one complete fixed 30-seed profile."""

    return _build_profile_evidence(definition_value, games)


def build_censored_four_by_four_depth5_profile_evidence(
    definition_value: Any,
    completed_games: Sequence[Any],
    incomplete_seed: int,
    budget_observation: Mapping[str, Any],
) -> Dict[str, Any]:
    """Build one cumulative-node-censored strict seed prefix."""

    return _build_profile_evidence(
        definition_value,
        completed_games,
        incomplete_seed=incomplete_seed,
        budget_observation=budget_observation,
    )


def validate_four_by_four_depth5_profile_evidence(
    definition_value: Any, evidence: Any
) -> Dict[str, Any]:
    """Replay all stored games and rebuild complete or censored profile claims."""

    definition = validate_four_by_four_calibration_definition(definition_value)
    value = _exact_keys(
        _copy(evidence, "4x4 depth profile evidence"),
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
        "4x4 depth profile evidence",
    )
    if value["profile"] != FOUR_BY_FOUR_DEPTH5_PROFILE:
        raise ValueError("4x4 depth profile identity mismatch")
    if value["expected_seeds"] != list(FOUR_BY_FOUR_DEPTH5_SEEDS) or any(
        type(seed) is not int for seed in value["expected_seeds"]
    ):
        raise ValueError("4x4 depth profile seeds must be exactly 0..29")
    if not isinstance(value["games"], list):
        raise ValueError("4x4 depth profile games must be an array")
    games = tuple(_normalize_game(definition, game) for game in value["games"])
    if _canonical_bytes(value["games"]) != _canonical_bytes(games):
        raise ValueError("stored 4x4 depth games do not reconstruct")
    game_seeds = tuple(game["seed"] for game in games)
    prefix = value["completed_seed_prefix"]
    if not isinstance(prefix, list) or any(type(seed) is not int for seed in prefix):
        raise ValueError("completed seed prefix must be an integer array")
    summary = _profile_summary(games)
    if value["status"] == "COMPLETED":
        if (
            game_seeds != FOUR_BY_FOUR_DEPTH5_SEEDS
            or prefix != list(FOUR_BY_FOUR_DEPTH5_SEEDS)
            or value["incomplete_seed"] is not None
            or _canonical_bytes(value["profile_summary"]) != _canonical_bytes(summary)
            or value["partial_summary"] is not None
            or value["budget_observation"] is not None
        ):
            raise ValueError("complete 4x4 depth profile evidence is inconsistent")
    elif value["status"] == "CENSORED_NODE_BUDGET":
        incomplete_seed = _strict_int(value["incomplete_seed"], "incomplete seed")
        if (
            len(game_seeds) >= len(FOUR_BY_FOUR_DEPTH5_SEEDS)
            or game_seeds != FOUR_BY_FOUR_DEPTH5_SEEDS[: len(game_seeds)]
            or prefix != list(game_seeds)
            or incomplete_seed != FOUR_BY_FOUR_DEPTH5_SEEDS[len(game_seeds)]
            or value["profile_summary"] is not None
            or _canonical_bytes(value["partial_summary"]) != _canonical_bytes(summary)
        ):
            raise ValueError("censored 4x4 depth profile evidence is inconsistent")
        budget = _exact_keys(
            value["budget_observation"],
            ("visited_nodes", "max_nodes", "scope"),
            "4x4 depth budget observation",
        )
        if (
            type(budget["visited_nodes"]) is not int
            or type(budget["max_nodes"]) is not int
            or budget["visited_nodes"] != FOUR_BY_FOUR_DEPTH5_MAX_NODES
            or budget["max_nodes"] != FOUR_BY_FOUR_DEPTH5_MAX_NODES
            or budget["scope"] != "per-candidate"
        ):
            raise ValueError("censored 4x4 depth budget is malformed")
    else:
        raise ValueError("4x4 depth profile has an unknown status")
    return _copy(value, "validated 4x4 depth profile")


def _normalize_profile_slot(
    case: Mapping[str, Any], expected: Mapping[str, Any], raw_slot: Any
) -> Dict[str, Any]:
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
            "status",
            "agent_identity",
            "profile_evidence",
            "game_nodes",
            "incomplete_attempt",
            "expanded_nodes",
            "elapsed_seconds",
        ),
        "4x4 depth schedule slot",
    )
    for field in expected:
        if _canonical_bytes(slot[field]) != _canonical_bytes(expected[field]):
            raise ValueError("4x4 depth schedule identity/order mismatch")
    if slot["agent_identity"] != FOUR_BY_FOUR_DEPTH5_PROFILE:
        raise ValueError("4x4 depth agent identity mismatch")
    definition = validate_four_by_four_calibration_definition(case["definition"])
    evidence = validate_four_by_four_depth5_profile_evidence(
        definition, slot["profile_evidence"]
    )
    expected_status = (
        "COMPLETED"
        if evidence["status"] == "COMPLETED"
        else "INCOMPLETE_NODE_CENSOR"
    )
    if slot["status"] != expected_status:
        raise ValueError("4x4 depth slot/profile status mismatch")
    expanded = _strict_int(slot["expanded_nodes"], "expanded_nodes")
    if expanded > FOUR_BY_FOUR_DEPTH5_MAX_NODES:
        raise ValueError("4x4 depth expanded_nodes exceeds its fixed cap")
    raw_nodes = slot["game_nodes"]
    if not isinstance(raw_nodes, list) or len(raw_nodes) != len(evidence["games"]):
        raise ValueError("4x4 depth game node ledger length mismatch")
    previous = 0
    normalized_nodes = []
    for game, raw_node in zip(evidence["games"], raw_nodes):
        node = _exact_keys(
            raw_node,
            ("seed", "nodes_before", "nodes_after", "nodes_used"),
            "4x4 depth game node evidence",
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
            or after > FOUR_BY_FOUR_DEPTH5_MAX_NODES
            or used < game["trace"]["root_legal_action_count_sum"]
        ):
            raise ValueError("4x4 depth game node evidence does not reconstruct")
        previous = after
        normalized_nodes.append(_copy(node, "4x4 game node evidence"))

    incomplete = slot["incomplete_attempt"]
    if expected_status == "COMPLETED":
        if incomplete is not None or previous != expanded:
            raise ValueError("complete 4x4 depth node evidence is inconsistent")
        normalized_incomplete = None
    else:
        item = _exact_keys(
            incomplete,
            (
                "seed",
                "completed_action_prefix",
                "trace",
                "nodes_before_seed",
                "nodes_consumed",
                "final_cumulative_nodes",
                "limit",
                "scope",
            ),
            "incomplete 4x4 depth attempt",
        )
        seed = _strict_int(item["seed"], "incomplete seed")
        before = _strict_int(item["nodes_before_seed"], "incomplete nodes_before")
        consumed = _strict_int(item["nodes_consumed"], "incomplete nodes_consumed")
        final = _strict_int(
            item["final_cumulative_nodes"], "incomplete final cumulative nodes"
        )
        limit = _strict_int(
            item["limit"],
            "incomplete node limit",
            expected=FOUR_BY_FOUR_DEPTH5_MAX_NODES,
        )
        trace = derive_four_by_four_depth5_trace(
            definition, item["completed_action_prefix"], require_terminal=False
        )
        if (
            seed != evidence["incomplete_seed"]
            or _canonical_bytes(item["trace"]) != _canonical_bytes(trace)
            or trace["is_terminal"]
            or before != previous
            or final != before + consumed
            or final != expanded
            or final != limit
            or item["scope"] != "per-candidate"
            or consumed < trace["root_legal_action_count_sum"]
        ):
            raise ValueError("incomplete 4x4 depth attempt does not reconstruct")
        budget = evidence["budget_observation"]
        if (
            budget["visited_nodes"] != final
            or budget["max_nodes"] != limit
            or budget["scope"] != item["scope"]
        ):
            raise ValueError("profile and incomplete-attempt budgets disagree")
        normalized_incomplete = _copy(item, "incomplete 4x4 depth attempt")
    return {
        **expected,
        "status": expected_status,
        "agent_identity": FOUR_BY_FOUR_DEPTH5_PROFILE,
        "profile_evidence": evidence,
        "game_nodes": normalized_nodes,
        "incomplete_attempt": normalized_incomplete,
        "expanded_nodes": expanded,
        "elapsed_seconds": _elapsed_seconds(
            slot["elapsed_seconds"], "4x4 depth elapsed_seconds"
        ),
    }


def _profile_slots_digest(slots: Sequence[Mapping[str, Any]]) -> str:
    payload = [
        {key: value for key, value in slot.items() if key != "elapsed_seconds"}
        for slot in slots
    ]
    return _domain_digest(_PROFILE_SLOTS_DOMAIN, payload)


def _shape_failures(
    definition: GameDefinition, profile: Mapping[str, Any]
) -> list[str]:
    samples = profile["game_count"]
    failures = set()
    if profile["draws"] / samples > _FROZEN_PLAY_GATES["max_draw_rate"]:
        failures.add("EXCESSIVE_DRAWS")
    if profile["average_plies"] < _FROZEN_PLAY_GATES["min_average_plies"]:
        failures.add("TOO_SHORT")
    if (
        profile["average_plies"]
        > definition.max_plies * _FROZEN_PLAY_GATES["max_average_plies_fraction"]
    ):
        failures.add("TOO_LONG")
    interval = profile["decisive_a_wilson_95"]
    if interval is not None:
        if interval[0] > 0.5 + _FROZEN_PLAY_GATES["dominance_interval_margin"]:
            failures.add("A_DOMINANT")
        if interval[1] < 0.5 - _FROZEN_PLAY_GATES["dominance_interval_margin"]:
            failures.add("B_DOMINANT")
    return sorted(failures)


def _case_record(
    case: Mapping[str, Any], slot: Mapping[str, Any]
) -> Dict[str, Any]:
    exact = case["exact"]["result"]
    exact_label = case["calibration_label"]
    completed = slot["status"] == "COMPLETED"
    if completed:
        profile = _copy(
            slot["profile_evidence"]["profile_summary"], "4x4 sampled profile"
        )
        partial_profile = None
        direction = sampled_direction(profile)
        shape_failures = _shape_failures(
            parse_definition(case["definition"]), profile
        )
    else:
        profile = None
        partial_profile = _copy(
            slot["profile_evidence"]["partial_summary"],
            "4x4 partial sampled profile",
        )
        direction = None
        shape_failures = None
    if exact_label in ("A_WIN", "B_WIN") and completed:
        direction_match = direction == exact_label
        draw_error = None
    elif exact_label == "HORIZON_DRAW" and completed:
        direction_match = None
        draw_error = direction in ("A_WIN", "B_WIN")
    else:
        direction_match = None
        draw_error = None
    return {
        "case_index": case["case_index"],
        "case_id": case["case_id"],
        "stratum_id": case["stratum_id"],
        "stratum": _copy(case["stratum"], "4x4 depth stratum"),
        "definition_hash": case["definition_hash"],
        "d4_canonical_hash": case["d4_canonical_hash"],
        "case_fingerprint": case["case_fingerprint"],
        "definition": _copy(case["definition"], "4x4 depth definition"),
        "calibration_label": exact_label,
        "exact_forced_result": exact["forced_result"],
        "exact_terminal_reason": exact["terminal_reason"],
        "exact_pv_trace_digest": case["principal_variation_trace"]["trace_digest"],
        "profile_status": slot["status"],
        "profile": profile,
        "partial_profile": partial_profile,
        "sampled_direction": direction,
        "direction_match": direction_match,
        "exact_draw_decisive_error": draw_error,
        "shape_failure_codes": shape_failures,
        "node_censored": not completed,
        "expanded_nodes": slot["expanded_nodes"],
    }


def assess_four_by_four_depth5_transfer(
    case_records: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Apply the fixed node-censor, 90%-accuracy, and exact-draw priorities."""

    if not isinstance(case_records, (list, tuple)) or len(case_records) != FOUR_BY_FOUR_CASE_COUNT:
        raise ValueError("4x4 transfer assessment requires exactly 32 cases")
    seen_ids = set()
    seen_strata = set()
    normalized = []
    for index, raw in enumerate(case_records):
        record = _exact_keys(
            raw,
            (
                "case_index",
                "case_id",
                "stratum_id",
                "profile_status",
                "calibration_label",
                "sampled_direction",
            ),
            "4x4 transfer assessment record",
        )
        _strict_int(record["case_index"], "assessment case index", expected=index)
        case_id = _nonempty_string(record["case_id"], "assessment case id")
        stratum_id = _nonempty_string(record["stratum_id"], "assessment stratum id")
        if case_id != "four-by-four-calibration-v1-" + stratum_id:
            raise ValueError("4x4 transfer case/stratum identity mismatch")
        if case_id in seen_ids or stratum_id in seen_strata:
            raise ValueError("4x4 transfer assessment identities must be unique")
        seen_ids.add(case_id)
        seen_strata.add(stratum_id)
        label = record["calibration_label"]
        status = record["profile_status"]
        direction = record["sampled_direction"]
        if label not in _EXACT_LABELS:
            raise ValueError("4x4 transfer exact label is malformed")
        if status == "COMPLETED":
            if direction not in _DIRECTIONS:
                raise ValueError("completed 4x4 transfer direction is malformed")
        elif status == "INCOMPLETE_NODE_CENSOR":
            if direction is not None:
                raise ValueError("censored 4x4 transfer direction must be null")
        else:
            raise ValueError("4x4 transfer profile status is malformed")
        normalized.append(
            {
                "case_index": index,
                "case_id": case_id,
                "stratum_id": stratum_id,
                "profile_status": status,
                "calibration_label": label,
                "sampled_direction": direction,
            }
        )
    if tuple(record["stratum_id"] for record in normalized) != _ORDERED_STRATUM_IDS:
        raise ValueError("4x4 transfer cases must follow all frozen strata")
    label_counts = Counter(record["calibration_label"] for record in normalized)
    label_strata = {
        label: {
            record["stratum_id"]
            for record in normalized
            if record["calibration_label"] == label
        }
        for label in _EXACT_LABELS
    }
    if (
        label_counts["A_WIN"] + label_counts["B_WIN"]
        < FOUR_BY_FOUR_MIN_DECISIVE_LABELS
        or label_counts["A_WIN"] < FOUR_BY_FOUR_MIN_A_WINS
        or label_counts["B_WIN"] < FOUR_BY_FOUR_MIN_B_WINS
        or label_counts["HORIZON_DRAW"] < FOUR_BY_FOUR_MIN_HORIZON_DRAWS
        or any(
            len(label_strata[label]) < FOUR_BY_FOUR_MIN_STRATA_PER_LABEL
            for label in _EXACT_LABELS
        )
    ):
        raise ValueError("4x4 transfer assessment requires sufficient exact labels")
    node_censors = sum(
        record["profile_status"] != "COMPLETED" for record in normalized
    )
    decisive = [record for record in normalized if record["calibration_label"] != "HORIZON_DRAW"]
    completed_decisive = [record for record in decisive if record["profile_status"] == "COMPLETED"]
    matches = sum(
        record["sampled_direction"] == record["calibration_label"]
        for record in completed_decisive
    )
    draws = [record for record in normalized if record["calibration_label"] == "HORIZON_DRAW"]
    completed_draws = [record for record in draws if record["profile_status"] == "COMPLETED"]
    draw_errors = [
        record
        for record in completed_draws
        if record["sampled_direction"] in ("A_WIN", "B_WIN")
    ]
    accuracy_passes = bool(
        completed_decisive
        and FOUR_BY_FOUR_TRANSFER_ACCURACY_DENOMINATOR * matches
        >= FOUR_BY_FOUR_TRANSFER_ACCURACY_NUMERATOR * len(completed_decisive)
    )
    if node_censors:
        status = "INCONCLUSIVE_NODE_BUDGET"
        next_branch = "RETIRE_PLACE_VS_MOVE_FAMILY"
    elif accuracy_passes and not draw_errors:
        status = "SUPPORTED_4X4_DEPTH5_TRANSFER"
        next_branch = "PLAN_OUTCOME_BLIND_4X4_FAMILY_VIABILITY"
    else:
        status = "NOT_SUPPORTED_4X4_DEPTH5_TRANSFER"
        next_branch = "RETIRE_PLACE_VS_MOVE_FAMILY"
    decisive_confusion = {
        label: {direction: 0 for direction in (*_DIRECTIONS, "NODE_CENSOR")}
        for label in ("A_WIN", "B_WIN")
    }
    draw_directions = {direction: 0 for direction in (*_DIRECTIONS, "NODE_CENSOR")}
    for record in normalized:
        direction = (
            record["sampled_direction"]
            if record["profile_status"] == "COMPLETED"
            else "NODE_CENSOR"
        )
        if record["calibration_label"] == "HORIZON_DRAW":
            draw_directions[direction] += 1
        else:
            decisive_confusion[record["calibration_label"]][direction] += 1
    return {
        "status": status,
        "integrity_status": "PASSED",
        "requirements": {
            "minimum_decisive_direction_accuracy_numerator": (
                FOUR_BY_FOUR_TRANSFER_ACCURACY_NUMERATOR
            ),
            "minimum_decisive_direction_accuracy_denominator": (
                FOUR_BY_FOUR_TRANSFER_ACCURACY_DENOMINATOR
            ),
            "maximum_exact_draw_decisive_errors": 0,
            "maximum_node_censors_for_decision": 0,
        },
        "observed": {
            "case_count": len(normalized),
            "completed_profile_count": len(normalized) - node_censors,
            "node_censor_count": node_censors,
            "exact_decisive_count": len(decisive),
            "completed_exact_decisive_count": len(completed_decisive),
            "decisive_direction_match_count": matches,
            "decisive_direction_accuracy": (
                matches / len(completed_decisive) if completed_decisive else None
            ),
            "exact_horizon_draw_count": len(draws),
            "completed_exact_horizon_draw_count": len(completed_draws),
            "exact_draw_decisive_error_count": len(draw_errors),
        },
        "decisive_direction_confusion": decisive_confusion,
        "exact_draw_sampled_directions": draw_directions,
        "node_censored_case_ids": [
            record["case_id"]
            for record in normalized
            if record["profile_status"] != "COMPLETED"
        ],
        "direction_mismatch_case_ids": [
            record["case_id"]
            for record in completed_decisive
            if record["sampled_direction"] != record["calibration_label"]
        ],
        "exact_draw_decisive_error_case_ids": [
            record["case_id"] for record in draw_errors
        ],
        "next_branch": next_branch,
    }


def _node_totals(slots: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    completed = sum(
        node["nodes_used"] for slot in slots for node in slot["game_nodes"]
    )
    incomplete = sum(
        slot["incomplete_attempt"]["nodes_consumed"]
        for slot in slots
        if slot["incomplete_attempt"] is not None
    )
    expanded = sum(slot["expanded_nodes"] for slot in slots)
    if expanded != completed + incomplete:
        raise ValueError("4x4 depth node totals do not reconstruct")
    return {
        "completed_game_nodes": completed,
        "incomplete_attempt_nodes": incomplete,
        "expanded_nodes_total": expanded,
    }


def _fixed_histogram(values: Iterable[str], keys: Sequence[str]) -> Dict[str, int]:
    counter = Counter(values)
    return {key: counter[key] for key in keys}


def _group_summary(
    records: Sequence[Mapping[str, Any]], slots: Sequence[Mapping[str, Any]]
) -> Dict[str, Any]:
    case_ids = {record["case_id"] for record in records}
    group_slots = [slot for slot in slots if slot["case_id"] in case_ids]
    games = [
        game
        for slot in group_slots
        for game in slot["profile_evidence"]["games"]
    ]
    sampled_results = Counter(
        "DRAW"
        if game["terminal_outcome"]["winner"] is None
        else "{}_WIN".format(game["terminal_outcome"]["winner"])
        for game in games
    )
    terminal = Counter(game["terminal_outcome"]["reason"] for game in games)
    directions = Counter(
        record["sampled_direction"]
        if record["sampled_direction"] is not None
        else "NODE_CENSOR"
        for record in records
    )
    failures = Counter(
        code
        for record in records
        for code in (record["shape_failure_codes"] or [])
    )
    nodes = _node_totals(group_slots)
    total_plies = sum(game["terminal_ply"] for game in games)
    return {
        "case_count": len(records),
        "completed_profile_count": sum(
            record["profile_status"] == "COMPLETED" for record in records
        ),
        "node_censored_profile_count": sum(record["node_censored"] for record in records),
        "completed_game_count": len(games),
        "exact_labels": _fixed_histogram(
            (record["calibration_label"] for record in records), _EXACT_LABELS
        ),
        "sampled_directions": {
            direction: directions[direction]
            for direction in (*_DIRECTIONS, "NODE_CENSOR")
        },
        "sampled_results": {
            result: sampled_results[result] for result in ("A_WIN", "B_WIN", "DRAW")
        },
        "terminal_reasons": {
            reason: terminal[reason] for reason in _TERMINAL_REASONS
        },
        "total_plies": total_plies,
        "average_plies": total_plies / len(games) if games else None,
        "direction_mismatch_count": sum(
            record["direction_match"] is False for record in records
        ),
        "exact_draw_decisive_error_count": sum(
            record["exact_draw_decisive_error"] is True for record in records
        ),
        "shape_failure_codes": dict(sorted(failures.items())),
        **nodes,
    }


def _breakdowns(
    records: Sequence[Mapping[str, Any]], slots: Sequence[Mapping[str, Any]]
) -> Dict[str, Any]:
    return {
        "all": _group_summary(records, slots),
        "by_first_player": {
            first: _group_summary(
                [record for record in records if record["stratum"]["first_player"] == first],
                slots,
            )
            for first in ("A", "B")
        },
        "by_goal_axis_relation": {
            relation: _group_summary(
                [
                    record
                    for record in records
                    if record["stratum"]["goal_axis_relation"] == relation
                ],
                slots,
            )
            for relation in ("ALIGNED", "ORTHOGONAL")
        },
        "by_runner_start_class": {
            start: _group_summary(
                [
                    record
                    for record in records
                    if record["stratum"]["runner_start_class"] == start
                ],
                slots,
            )
            for start in ("CORNER", "EDGE_INTERIOR")
        },
        "by_vector_band": {
            band: _group_summary(
                [record for record in records if record["stratum"]["vector_band"] == band],
                slots,
            )
            for band in _VECTOR_BANDS
        },
        "by_stratum": {
            record["stratum_id"]: _group_summary([record], slots)
            for record in records
        },
    }


def _build_inspection(
    records: Sequence[Mapping[str, Any]], assessment: Mapping[str, Any]
) -> Dict[str, Any]:
    exact_reason = {
        "A_WIN": "EXACT_A",
        "B_WIN": "EXACT_B",
        "HORIZON_DRAW": "EXACT_HORIZON_DRAW",
    }
    rows = []
    for record in records:
        reasons = [exact_reason[record["calibration_label"]]]
        if record["node_censored"]:
            reasons.append("NODE_CENSOR")
        if record["direction_match"] is False:
            reasons.append("DIRECTION_MISMATCH")
        if record["exact_draw_decisive_error"] is True:
            reasons.append("EXACT_DRAW_DECISIVE_ERROR")
        rows.append(
            {
                "case_index": record["case_index"],
                "case_id": record["case_id"],
                "stratum_id": record["stratum_id"],
                "stratum": _copy(record["stratum"], "inspection stratum"),
                "definition_hash": record["definition_hash"],
                "d4_canonical_hash": record["d4_canonical_hash"],
                "case_fingerprint": record["case_fingerprint"],
                "definition": _copy(record["definition"], "inspection definition"),
                "calibration_label": record["calibration_label"],
                "exact_forced_result": record["exact_forced_result"],
                "exact_terminal_reason": record["exact_terminal_reason"],
                "exact_pv_trace_digest": record["exact_pv_trace_digest"],
                "profile_status": record["profile_status"],
                "sampled_direction": record["sampled_direction"],
                "direction_match": record["direction_match"],
                "exact_draw_decisive_error": record["exact_draw_decisive_error"],
                "shape_failure_codes": record["shape_failure_codes"],
                "expanded_nodes": record["expanded_nodes"],
                "reasons": reasons,
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
        _elapsed_seconds(slot["elapsed_seconds"], "4x4 depth slot timing")
        for slot in slots
    ]
    total = _elapsed_seconds(sum(values), "4x4 depth total timing")
    mean = _elapsed_seconds(total / len(values), "4x4 depth mean timing")
    return {
        "total_seconds": total,
        "minimum_slot_seconds": min(values),
        "maximum_slot_seconds": max(values),
        "mean_slot_seconds": mean,
    }


def build_four_by_four_depth5_result(
    manifest: Mapping[str, Any],
    historical_projection: Mapping[str, Any],
    exact_result: Mapping[str, Any],
    profile_slots: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Validate all raw profile slots and rebuild the complete transfer artifact."""

    manifest_bytes = _canonical_bytes(manifest)
    history_bytes = _canonical_bytes(historical_projection)
    exact_bytes = _canonical_bytes(exact_result)

    def require_stable_inputs() -> None:
        if _canonical_bytes(manifest) != manifest_bytes:
            raise ValueError("4x4 depth builder input mutated the frozen manifest")
        if _canonical_bytes(historical_projection) != history_bytes:
            raise ValueError(
                "4x4 depth builder input mutated the closed-history witness"
            )
        if _canonical_bytes(exact_result) != exact_bytes:
            raise ValueError(
                "4x4 depth builder input mutated the upstream exact result"
            )

    def guarded(callback: Callable[[], Any]) -> Any:
        try:
            value = callback()
        except Exception as error:
            try:
                require_stable_inputs()
            except ValueError as mutation_error:
                raise mutation_error from error
            raise
        require_stable_inputs()
        return value

    cases, exact, manifest_digest, exact_digest = guarded(
        lambda: _validated_context(manifest, historical_projection, exact_result)
    )
    schedule = _schedule_from_cases(cases)
    raw_slots = guarded(lambda: _copy(profile_slots, "4x4 depth raw slots"))
    if not isinstance(raw_slots, list) or len(raw_slots) != FOUR_BY_FOUR_CASE_COUNT:
        raise ValueError("4x4 depth slots must cover the full fixed schedule")
    slots = [
        _normalize_profile_slot(case, expected, raw)
        for case, expected, raw in zip(cases, schedule, raw_slots)
    ]
    records = [_case_record(case, slot) for case, slot in zip(cases, slots)]
    assessment_inputs = [
        {
            "case_index": record["case_index"],
            "case_id": record["case_id"],
            "stratum_id": record["stratum_id"],
            "profile_status": record["profile_status"],
            "calibration_label": record["calibration_label"],
            "sampled_direction": record["sampled_direction"],
        }
        for record in records
    ]
    assessment = assess_four_by_four_depth5_transfer(assessment_inputs)
    breakdowns = _breakdowns(records, slots)
    node_totals = _node_totals(slots)
    result = {
        "result_version": FOUR_BY_FOUR_DEPTH5_RESULT_VERSION,
        "protocol_id": FOUR_BY_FOUR_DEPTH5_PROTOCOL_ID,
        "manifest_id": exact["manifest_id"],
        "manifest_digest": manifest_digest,
        "upstream_exact_evidence_digest": exact["aggregate"]["evidence_digest"],
        "upstream_exact_result_digest": exact_digest,
        "configuration": {
            "case_count": FOUR_BY_FOUR_CASE_COUNT,
            "depth": FOUR_BY_FOUR_DEPTH,
            "seeds": list(FOUR_BY_FOUR_DEPTH5_SEEDS),
            "max_nodes_per_definition": FOUR_BY_FOUR_DEPTH5_MAX_NODES,
            "max_nodes_per_move": 0,
            "profile": FOUR_BY_FOUR_DEPTH5_PROFILE,
            "schedule": "MANIFEST_ORDER_ALL_CASES",
            "agent_lifecycle": "ONE_FRESH_RESET_AGENT_PER_DEFINITION_SHARED_BY_BOTH_ROLES",
            "node_budget_scope": "CUMULATIVE_PER_DEFINITION",
            "sampled_direction_rule": "DECISIVE_A_SHARE_GT_HALF_A_LT_HALF_B_ELSE_BALANCED",
            "play_gates": dict(_FROZEN_PLAY_GATES),
            "play_gate_disposition": "DESCRIPTIVE_ONLY",
        },
        "schedule": schedule,
        "slots": slots,
        "cases": records,
        "aggregate": {
            "profile_attempted": len(slots),
            "profile_completed": sum(slot["status"] == "COMPLETED" for slot in slots),
            "node_censored": sum(slot["status"] == "INCOMPLETE_NODE_CENSOR" for slot in slots),
            "completed_game_count": sum(len(slot["profile_evidence"]["games"]) for slot in slots),
            "expanded_nodes_total": node_totals["expanded_nodes_total"],
            "completed_game_nodes_total": node_totals["completed_game_nodes"],
            "incomplete_attempt_nodes_total": node_totals["incomplete_attempt_nodes"],
            "evidence_digest": _profile_slots_digest(slots),
            "confusion": {
                "by_exact_label": {
                    "A_WIN": _copy(
                        assessment["decisive_direction_confusion"]["A_WIN"],
                        "4x4 depth A confusion",
                    ),
                    "B_WIN": _copy(
                        assessment["decisive_direction_confusion"]["B_WIN"],
                        "4x4 depth B confusion",
                    ),
                    "HORIZON_DRAW": _copy(
                        assessment["exact_draw_sampled_directions"],
                        "4x4 depth horizon-draw confusion",
                    ),
                }
            },
            "breakdowns": breakdowns,
        },
        "assessment": assessment,
        "inspection": _build_inspection(records, assessment),
        "timing": _timing_summary(slots),
    }
    require_stable_inputs()
    return result


def validate_four_by_four_depth5_result(
    result: Mapping[str, Any],
    manifest: Mapping[str, Any],
    historical_projection: Mapping[str, Any],
    exact_result: Mapping[str, Any],
) -> Dict[str, Any]:
    """Strictly reconstruct every derived depth-5 field from raw slots."""

    manifest_bytes = _canonical_bytes(manifest)
    history_bytes = _canonical_bytes(historical_projection)
    exact_bytes = _canonical_bytes(exact_result)

    def require_stable_inputs() -> None:
        if _canonical_bytes(manifest) != manifest_bytes:
            raise ValueError("4x4 depth validator input mutated the frozen manifest")
        if _canonical_bytes(historical_projection) != history_bytes:
            raise ValueError(
                "4x4 depth validator input mutated the closed-history witness"
            )
        if _canonical_bytes(exact_result) != exact_bytes:
            raise ValueError(
                "4x4 depth validator input mutated the upstream exact result"
            )

    def guarded(callback: Callable[[], Any]) -> Any:
        try:
            copied = callback()
        except Exception as error:
            try:
                require_stable_inputs()
            except ValueError as mutation_error:
                raise mutation_error from error
            raise
        require_stable_inputs()
        return copied

    value = _exact_keys(
        guarded(lambda: _copy(result, "4x4 depth result")),
        (
            "result_version",
            "protocol_id",
            "manifest_id",
            "manifest_digest",
            "upstream_exact_evidence_digest",
            "upstream_exact_result_digest",
            "configuration",
            "schedule",
            "slots",
            "cases",
            "aggregate",
            "assessment",
            "inspection",
            "timing",
        ),
        "4x4 depth result",
    )
    rebuilt = guarded(
        lambda: build_four_by_four_depth5_result(
            manifest, historical_projection, exact_result, value["slots"]
        )
    )
    if _canonical_bytes(value) != _canonical_bytes(rebuilt):
        raise ValueError("4x4 depth result does not reconstruct")
    validated = _copy(value, "validated 4x4 depth result")
    require_stable_inputs()
    return validated


def _raw_agent_contract(agent: Any) -> Tuple[Any, ...]:
    identity = getattr(agent, "identity", None)
    return (
        identity,
        getattr(identity, "family", None),
        getattr(identity, "version", None),
        getattr(identity, "strength", None),
        getattr(identity, "key", None),
        getattr(agent, "depth", None),
        getattr(agent, "max_total_nodes", None),
        getattr(agent, "max_nodes_per_move", None),
        getattr(agent, "total_nodes", None),
    )


def _validate_agent_contract_snapshot(
    snapshot: Tuple[Any, ...], node_label: str
) -> Tuple[str, int]:
    (
        identity,
        family,
        version,
        strength,
        key,
        depth,
        max_total,
        max_move,
        total_nodes,
    ) = snapshot
    if type(identity) is not AgentIdentity:
        raise ValueError("4x4 depth agent identity must be an AgentIdentity")
    if (
        type(family) is not str
        or family != "minimax"
        or type(version) is not int
        or version != 1
        or type(strength) is not str
        or strength != "depth5"
        or type(key) is not str
        or key != FOUR_BY_FOUR_DEPTH5_PROFILE
    ):
        raise ValueError("4x4 depth agent identity must be minimax-v1-depth5")
    if (
        type(depth) is not int
        or depth != FOUR_BY_FOUR_DEPTH
        or type(max_total) is not int
        or max_total != FOUR_BY_FOUR_DEPTH5_MAX_NODES
        or type(max_move) is not int
        or max_move != 0
    ):
        raise ValueError("4x4 depth agent configuration is not frozen")
    return key, _strict_int(total_nodes, node_label)


def _agent_contract(
    agent: Any, guarded: Callable[..., Any], node_label: str
) -> Tuple[str, int]:
    return _validate_agent_contract_snapshot(
        guarded(lambda: _raw_agent_contract(agent)), node_label
    )


def _new_agent(
    definition: GameDefinition,
    entry: Mapping[str, Any],
    *,
    agent_factory: Optional[Callable[..., Any]],
    prior_agents: list[Any],
    guarded: Callable[..., Any],
) -> Any:
    if agent_factory is None:
        agent = guarded(
            lambda: MinimaxAgent(
                depth=FOUR_BY_FOUR_DEPTH,
                max_nodes_per_move=0,
                max_total_nodes=FOUR_BY_FOUR_DEPTH5_MAX_NODES,
            )
        )
    else:
        agent = guarded(
            lambda: agent_factory(
                definition=definition,
                depth=FOUR_BY_FOUR_DEPTH,
                max_nodes=FOUR_BY_FOUR_DEPTH5_MAX_NODES,
                schedule_entry=_copy(entry, "4x4 depth schedule entry"),
            )
        )
    if any(agent is prior for prior in prior_agents):
        raise ValueError("4x4 depth requires a fresh agent object per definition")
    prior_agents.append(agent)
    _agent_contract(agent, guarded, "pre-reset total_nodes")
    reset = guarded(lambda: getattr(agent, "reset_budget", None))
    if not callable(reset):
        raise ValueError("4x4 depth agent must expose reset_budget")
    guarded(reset)
    _, post_reset_nodes = _agent_contract(
        agent, guarded, "post-reset total_nodes"
    )
    if post_reset_nodes != 0:
        raise ValueError("4x4 depth reset must set total_nodes to zero")
    return agent


def _select_action(
    agent: Any,
    definition: GameDefinition,
    state: Any,
    choices: Tuple[Action, ...],
    rng: random.Random,
    guarded: Callable[..., Any],
) -> Tuple[Action, int]:
    definition_bytes = _canonical_bytes(definition.to_dict())
    state_bytes = _canonical_bytes(state.to_dict())
    choices_bytes = _canonical_bytes([action.to_dict() for action in choices])

    def require_local_stability() -> None:
        if _canonical_bytes(definition.to_dict()) != definition_bytes:
            raise ValueError("4x4 depth agent mutated its definition input")
        if _canonical_bytes(state.to_dict()) != state_bytes:
            raise ValueError("4x4 depth agent mutated its state input")
        if _canonical_bytes([action.to_dict() for action in choices]) != choices_bytes:
            raise ValueError("4x4 depth agent mutated its legal-action input")

    try:
        action, contract = guarded(
            lambda: (
                agent.select_action(definition, state, choices, rng),
                _raw_agent_contract(agent),
            )
        )
    except Exception as error:
        try:
            require_local_stability()
        except ValueError as mutation_error:
            raise mutation_error from error
        raise
    require_local_stability()
    _, nodes_after = _validate_agent_contract_snapshot(
        contract, "nodes after action"
    )
    if type(action) is not Action or action not in choices:
        raise ValueError("4x4 depth agent selected an illegal or forged action")
    raw_action = Action.to_dict(action)
    normalized = action_from_dict(raw_action)
    if normalized != action:
        raise ValueError("4x4 depth selected action does not round-trip")
    return normalized, nodes_after


def _execute_profile(
    definition: GameDefinition,
    entry: Mapping[str, Any],
    *,
    agent_factory: Optional[Callable[..., Any]],
    prior_agents: list[Any],
    guarded: Callable[..., Any],
) -> Dict[str, Any]:
    definition_bytes = _canonical_bytes(definition.to_dict())

    def require_definition_stable() -> None:
        if _canonical_bytes(definition.to_dict()) != definition_bytes:
            raise ValueError("4x4 depth callback mutated its active definition")

    def locally_guarded(callback: Callable[[], Any]) -> Any:
        try:
            result = guarded(callback)
        except Exception as error:
            try:
                require_definition_stable()
            except ValueError as mutation_error:
                raise mutation_error from error
            raise
        require_definition_stable()
        return result

    agent = _new_agent(
        definition,
        entry,
        agent_factory=agent_factory,
        prior_agents=prior_agents,
        guarded=locally_guarded,
    )
    identity, current_nodes = _agent_contract(
        agent, locally_guarded, "initial total_nodes"
    )
    games = []
    game_nodes = []
    incomplete = None
    previous = 0
    for seed in FOUR_BY_FOUR_DEPTH5_SEEDS:
        _, before = _agent_contract(agent, locally_guarded, "nodes before seed")
        if before != previous:
            raise ValueError("4x4 depth cumulative node ledger reset or drifted")
        current_nodes = before
        state = initial_state(definition)
        actions = []
        rng = random.Random(seed)
        selecting = False
        try:
            while not state.terminal:
                choices = legal_actions(definition, state)
                action_nodes_before = current_nodes
                selecting = True
                action, current_nodes = _select_action(
                    agent, definition, state, choices, rng, locally_guarded
                )
                selecting = False
                if (
                    current_nodes - action_nodes_before < len(choices)
                    or current_nodes > FOUR_BY_FOUR_DEPTH5_MAX_NODES
                ):
                    raise ValueError(
                        "4x4 depth action node accounting mismatch"
                    )
                actions.append(action.to_dict())
                state = apply_action(definition, state, action)
        except SearchBudgetExceeded as error:
            if not selecting:
                raise ValueError(
                    "4x4 depth censor may arise only from select_action"
                ) from error
            if type(error) is not SearchBudgetExceeded:
                raise ValueError(
                    "4x4 depth censor must use exact SearchBudgetExceeded"
                ) from error
            try:
                _, final = _agent_contract(
                    agent, locally_guarded, "censored total_nodes"
                )
            except Exception as contract_error:
                raise contract_error from error
            scope, visited, maximum = locally_guarded(
                lambda: (error.scope, error.visited_nodes, error.max_nodes)
            )
            if (
                type(scope) is not str
                or scope != "per-candidate"
                or type(visited) is not int
                or type(maximum) is not int
                or visited != FOUR_BY_FOUR_DEPTH5_MAX_NODES
                or maximum != FOUR_BY_FOUR_DEPTH5_MAX_NODES
                or final != visited
                or final < action_nodes_before
            ):
                raise ValueError("4x4 depth censor node accounting mismatch")
            trace = derive_four_by_four_depth5_trace(
                definition, actions, require_terminal=False
            )
            if trace["is_terminal"]:
                raise ValueError("4x4 depth incomplete prefix is already terminal")
            incomplete = {
                "seed": seed,
                "completed_action_prefix": trace["actions"],
                "trace": trace,
                "nodes_before_seed": before,
                "nodes_consumed": final - before,
                "final_cumulative_nodes": final,
                "limit": maximum,
                "scope": scope,
            }
            previous = final
            break
        trace = derive_four_by_four_depth5_trace(definition, actions)
        after = current_nodes
        if (
            after <= before
            or after > FOUR_BY_FOUR_DEPTH5_MAX_NODES
            or after - before < trace["root_legal_action_count_sum"]
        ):
            raise ValueError("4x4 depth completed game node accounting mismatch")
        games.append(
            {
                "seed": seed,
                "actions": trace["actions"],
                "terminal_outcome": trace["terminal_outcome"],
                "terminal_ply": trace["ply"],
                "trace": trace,
            }
        )
        game_nodes.append(
            {
                "seed": seed,
                "nodes_before": before,
                "nodes_after": after,
                "nodes_used": after - before,
            }
        )
        previous = after
    final_identity, expanded = _agent_contract(
        agent, locally_guarded, "final expanded_nodes"
    )
    if final_identity != identity:
        raise ValueError("4x4 depth agent identity drifted")
    if expanded != previous:
        raise ValueError("4x4 depth final cumulative nodes drifted")
    if incomplete is None:
        evidence = build_four_by_four_depth5_profile_evidence(definition, games)
        status = "COMPLETED"
    else:
        evidence = build_censored_four_by_four_depth5_profile_evidence(
            definition,
            games,
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
        "expanded_nodes": expanded,
    }


def _evaluate_four_by_four_depth5(
    manifest: Mapping[str, Any],
    historical_projection: Mapping[str, Any],
    exact_result: Mapping[str, Any],
    *,
    agent_factory: Optional[Callable[..., Any]],
    clock: Callable[[], float],
) -> Dict[str, Any]:
    """Private injectable seam; public execution fixes the real agent and clock."""

    if agent_factory is not None and not callable(agent_factory):
        raise ValueError("4x4 depth agent_factory must be callable or null")
    if not callable(clock):
        raise ValueError("4x4 depth clock must be callable")
    cases, _, _, _ = _validated_context(
        manifest, historical_projection, exact_result
    )
    schedule = _schedule_from_cases(cases)
    manifest_bytes = _canonical_bytes(manifest)
    history_bytes = _canonical_bytes(historical_projection)
    exact_bytes = _canonical_bytes(exact_result)

    def require_stable_inputs() -> None:
        if _canonical_bytes(manifest) != manifest_bytes:
            raise ValueError("4x4 depth callback mutated the frozen manifest")
        if _canonical_bytes(historical_projection) != history_bytes:
            raise ValueError("4x4 depth callback mutated the closed-history witness")
        if _canonical_bytes(exact_result) != exact_bytes:
            raise ValueError("4x4 depth callback mutated the upstream exact result")

    def guarded(callback: Callable[[], Any]) -> Any:
        try:
            result = callback()
        except Exception as error:
            try:
                require_stable_inputs()
            except ValueError as mutation_error:
                raise mutation_error from error
            raise
        require_stable_inputs()
        return result

    def clock_value() -> float:
        return _elapsed_seconds(guarded(clock), "4x4 depth clock observation")

    slots = []
    agents: list[Any] = []
    for case, entry in zip(cases, schedule):
        definition = validate_four_by_four_calibration_definition(case["definition"])
        started = clock_value()
        raw = _execute_profile(
            definition,
            entry,
            agent_factory=agent_factory,
            prior_agents=agents,
            guarded=guarded,
        )
        finished = clock_value()
        slot = {**raw, "elapsed_seconds": _elapsed_seconds(
            finished - started, "4x4 depth elapsed_seconds"
        )}
        normalized = _normalize_profile_slot(case, entry, slot)
        require_stable_inputs()
        slots.append(normalized)
    result = build_four_by_four_depth5_result(
        manifest, historical_projection, exact_result, slots
    )
    require_stable_inputs()
    return result


def evaluate_four_by_four_depth5(
    manifest: Mapping[str, Any],
    historical_projection: Mapping[str, Any],
    exact_result: Mapping[str, Any],
) -> Dict[str, Any]:
    """Execute the fixed production-shaped all-case depth-5 schedule."""

    return _evaluate_four_by_four_depth5(
        manifest,
        historical_projection,
        exact_result,
        agent_factory=None,
        clock=time.perf_counter,
    )


__all__ = (
    "FOUR_BY_FOUR_DEPTH5_MAX_NODES",
    "FOUR_BY_FOUR_DEPTH5_PROFILE",
    "FOUR_BY_FOUR_DEPTH5_PROTOCOL_ID",
    "FOUR_BY_FOUR_DEPTH5_RESULT_VERSION",
    "FOUR_BY_FOUR_DEPTH5_SEEDS",
    "FOUR_BY_FOUR_DEPTH",
    "FOUR_BY_FOUR_TRANSFER_ACCURACY_DENOMINATOR",
    "FOUR_BY_FOUR_TRANSFER_ACCURACY_NUMERATOR",
    "assess_four_by_four_depth5_transfer",
    "build_censored_four_by_four_depth5_profile_evidence",
    "build_four_by_four_depth5_profile_evidence",
    "build_four_by_four_depth5_result",
    "derive_four_by_four_depth5_trace",
    "evaluate_four_by_four_depth5",
    "four_by_four_depth5_schedule",
    "validate_four_by_four_depth5_profile_evidence",
    "validate_four_by_four_depth5_result",
)
