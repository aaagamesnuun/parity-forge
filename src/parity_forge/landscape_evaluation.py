"""Frozen evaluation lanes for the 3x3 outcome landscape.

Selection lives in :mod:`parity_forge.landscape`.  This module deliberately takes
an already selected sequence and never substitutes a case after a budget is spent.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from typing import Any, Callable, Dict, Mapping, Sequence, Set, Tuple

from .agents import GoalDirectedAgent, MinimaxAgent, RandomAgent, SearchBudgetExceeded
from .analysis import FailureCode, analyze_definition
from .asymmetry import evaluate_asymmetry
from .audit import sampled_direction
from .batch import PlayGates, classify_play_failures
from .dsl import Player, definition_hash, parse_definition
from .play import evaluate_matchup
from .simplicity import evaluate_simplicity, exceeds_limits
from .solver import SolveBudgetExceeded, solve_game


LANDSCAPE_PLAY_SEEDS = tuple(range(30))
LANDSCAPE_EXACT_MAX_STATES = 100000
DRAW_STRESS_DEPTH = 5
DRAW_STRESS_MAX_CANDIDATES = 32
DRAW_STRESS_MAX_NODES = 5000000
DRAW_STRESS_SEEDS = tuple(range(30))
LANDSCAPE_INSPECTION_ORDINARY_COUNT = 16

_DRAW_STRESS_CLEAN_PREFIX = "draw-stress-clean-v1:"
_DRAW_STRESS_OTHER_PREFIX = "draw-stress-other-v1:"
_INSPECTION_PREFIX = "landscape-inspection-v1:"
_FORCED_RESULTS = ("A_WIN", "B_WIN", "DRAW")
_SHAPE_FAILURES = {
    FailureCode.EXCESSIVE_DRAWS.value,
    FailureCode.TOO_SHORT.value,
    FailureCode.TOO_LONG.value,
}


def _validate_seeds(seeds: Sequence[int], label: str) -> Tuple[int, ...]:
    seed_tuple = tuple(seeds)
    if not seed_tuple:
        raise ValueError("{} requires at least one seed".format(label))
    if len(set(seed_tuple)) != len(seed_tuple):
        raise ValueError("{} seeds must be unique".format(label))
    return seed_tuple


def _dimension_aggregates(
    candidates: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    dimensions = (
        "first_player",
        "goal_axis_relation",
        "runner_start_class",
        "max_plies",
        "vector_count_band",
        "vector_count",
    )
    grouped: Dict[str, Dict[Any, Counter[str]]] = {
        dimension: defaultdict(Counter) for dimension in dimensions
    }
    for candidate in candidates:
        stratum = candidate["stratum"]
        values = {
            **stratum,
            "vector_count": candidate["vector_count"],
        }
        exact = candidate["exact"]
        outcome = (
            exact["result"]["forced_result"]
            if exact["status"] == "COMPLETED"
            else "CENSORED"
        )
        for dimension in dimensions:
            grouped[dimension][values[dimension]][outcome] += 1

    result: Dict[str, Any] = {}
    for dimension in dimensions:
        records = []
        for value, counter in sorted(grouped[dimension].items()):
            histogram = {
                key: counter.get(key, 0)
                for key in (*_FORCED_RESULTS, "CENSORED")
            }
            records.append(
                {
                    "value": value,
                    "case_count": sum(histogram.values()),
                    "exact_result_histogram": histogram,
                }
            )
        result[dimension] = records
    return result


def evaluate_landscape_cases(
    cases: Sequence[Mapping[str, Any]],
    play_seeds: Sequence[int] = LANDSCAPE_PLAY_SEEDS,
    max_exact_states: int = LANDSCAPE_EXACT_MAX_STATES,
    gates: PlayGates = PlayGates(),
    clock: Callable[[], float] = time.perf_counter,
) -> Dict[str, Any]:
    """Evaluate an already frozen case list without outcome-dependent routing."""

    seed_tuple = _validate_seeds(play_seeds, "landscape play")
    if max_exact_states < 1:
        raise ValueError("max_exact_states must be at least one")
    if not cases:
        raise ValueError("landscape evaluation requires at least one case")

    random_agent = RandomAgent()
    directed_agent = GoalDirectedAgent()
    seen_case_ids: Set[str] = set()
    seen_hashes: Set[str] = set()
    seen_orbits: Set[str] = set()
    candidates = []
    static_failure_histogram: Counter[str] = Counter()
    cheap_failure_histogram: Counter[str] = Counter()
    exact_histogram: Counter[str] = Counter()
    exact_draw_terminal_reason_histogram: Counter[str] = Counter()
    direction_confusion: Dict[str, Counter[str]] = defaultdict(Counter)
    static_seconds = 0.0
    cheap_seconds = 0.0
    exact_seconds = 0.0
    exact_work = []
    total_started = clock()

    for manifest_index, case in enumerate(cases):
        case_id = case.get("case_id")
        game_hash = case.get("definition_hash")
        orbit_hash = case.get("d4_canonical_hash")
        if not all(isinstance(value, str) for value in (case_id, game_hash, orbit_hash)):
            raise ValueError("every landscape case needs string identifiers")
        if case_id in seen_case_ids or game_hash in seen_hashes or orbit_hash in seen_orbits:
            raise ValueError("landscape case, definition, and D4 identifiers must be unique")
        seen_case_ids.add(case_id)
        seen_hashes.add(game_hash)
        seen_orbits.add(orbit_hash)
        definition_mapping = case.get("definition")
        if not isinstance(definition_mapping, Mapping):
            raise ValueError("every landscape case needs a definition")
        definition = parse_definition(definition_mapping)
        if definition_hash(definition) != game_hash:
            raise ValueError("landscape definition hash mismatch for {}".format(case_id))

        static_started = clock()
        static = analyze_definition(definition)
        asymmetry = evaluate_asymmetry(definition)
        simplicity = evaluate_simplicity(definition)
        simplicity_passes = not exceeds_limits(simplicity)
        gate_passes = (
            static.passes
            and asymmetry.qualifies
            and simplicity_passes
        )
        static_elapsed = clock() - static_started
        static_seconds += static_elapsed
        static_failure_histogram.update(code.value for code in static.failure_codes)

        cheap_profiles = ()
        cheap_failures: Set[FailureCode] = set()
        cheap_elapsed = 0.0
        if gate_passes:
            cheap_started = clock()
            cheap_profiles = (
                evaluate_matchup(
                    definition,
                    "weak-random",
                    {Player.A: random_agent, Player.B: random_agent},
                    seed_tuple,
                ),
                evaluate_matchup(
                    definition,
                    "medium-goal-directed",
                    {Player.A: directed_agent, Player.B: directed_agent},
                    seed_tuple,
                ),
            )
            cheap_failures = classify_play_failures(
                definition, cheap_profiles, gates
            )
            cheap_elapsed = clock() - cheap_started
            cheap_seconds += cheap_elapsed
            cheap_failure_histogram.update(code.value for code in cheap_failures)

        exact_started = clock()
        exact_result = None
        budget_observation = None
        exact_status = "COMPLETED"
        try:
            solved = solve_game(definition, max_states=max_exact_states)
        except SolveBudgetExceeded as error:
            exact_status = "CENSORED_STATE_BUDGET"
            budget_observation = {
                "searched_states": error.searched_states,
                "max_states": error.max_states,
            }
            exact_work.append(error.searched_states)
        else:
            exact_result = solved.to_dict()
            exact_histogram[solved.forced_result] += 1
            if solved.forced_result == "DRAW":
                exact_draw_terminal_reason_histogram[solved.terminal_reason] += 1
            exact_work.append(solved.searched_states)
        exact_elapsed = clock() - exact_started
        exact_seconds += exact_elapsed

        profile_mappings = tuple(
            profile.to_dict(include_records=False) for profile in cheap_profiles
        )
        if exact_result is not None:
            for profile in profile_mappings:
                direction = sampled_direction(profile)
                direction_confusion[profile["profile"]][
                    "{}->{}".format(direction, exact_result["forced_result"])
                ] += 1

        candidate = {
            "manifest_index": manifest_index,
            "case_id": case_id,
            "definition_hash": game_hash,
            "d4_canonical_hash": orbit_hash,
            "stratum": dict(case["stratum"]),
            "vector_count": case["vector_count"],
            "definition": definition.to_dict(),
            "static": static.to_dict(),
            "asymmetry": asymmetry.to_dict(),
            "simplicity": simplicity.to_dict(),
            "simplicity_passes": simplicity_passes,
            "analysis_gate_passes": gate_passes,
            "cheap_profiles": list(profile_mappings),
            "cheap_failure_codes": sorted(code.value for code in cheap_failures),
            "exact": {
                "status": exact_status,
                "result": exact_result,
                "budget_observation": budget_observation,
                "elapsed_seconds": exact_elapsed,
            },
            "timing": {
                "static_asymmetry_simplicity_seconds": static_elapsed,
                "cheap_play_seconds": cheap_elapsed,
            },
        }
        candidates.append(candidate)

    exact_completed = sum(
        candidate["exact"]["status"] == "COMPLETED"
        for candidate in candidates
    )
    exact_censored = len(candidates) - exact_completed
    shape_clean_draws = sum(
        candidate["analysis_gate_passes"]
        and candidate["exact"]["status"] == "COMPLETED"
        and candidate["exact"]["result"]["forced_result"] == "DRAW"
        and not set(candidate["cheap_failure_codes"]).intersection(_SHAPE_FAILURES)
        for candidate in candidates
    )
    total_seconds = clock() - total_started
    assessment = {
        "status": "SUPPORTED" if exact_censored == 0 else "INCONCLUSIVE",
        "reasons": [] if exact_censored == 0 else ["EXACT_STATE_BUDGET_CENSORING"],
    }
    aggregate = {
        "manifest_case_count": len(candidates),
        "static_pass_count": sum(candidate["static"]["passes"] for candidate in candidates),
        "asymmetry_qualifies_count": sum(
            candidate["asymmetry"]["qualifies"] for candidate in candidates
        ),
        "simplicity_pass_count": sum(
            candidate["simplicity_passes"] for candidate in candidates
        ),
        "analysis_gate_pass_count": sum(
            candidate["analysis_gate_passes"] for candidate in candidates
        ),
        "cheap_attempted": sum(bool(candidate["cheap_profiles"]) for candidate in candidates),
        "cheap_evaluated": sum(bool(candidate["cheap_profiles"]) for candidate in candidates),
        "exact_attempted": len(candidates),
        "exact_completed": exact_completed,
        "exact_censored": exact_censored,
        "exact_censored_hashes": sorted(
            candidate["definition_hash"]
            for candidate in candidates
            if candidate["exact"]["status"] != "COMPLETED"
        ),
        "exact_completion_rate": exact_completed / len(candidates),
        "exact_result_histogram": {
            result: exact_histogram.get(result, 0) for result in _FORCED_RESULTS
        },
        "exact_draw_terminal_reason_histogram": dict(
            sorted(exact_draw_terminal_reason_histogram.items())
        ),
        "static_failure_histogram": dict(sorted(static_failure_histogram.items())),
        "cheap_failure_histogram": dict(sorted(cheap_failure_histogram.items())),
        "cheap_exact_direction_confusion": {
            profile: dict(sorted(counter.items()))
            for profile, counter in sorted(direction_confusion.items())
        },
        "exact_work_states_total": sum(exact_work),
        "exact_work_states_max": max(exact_work, default=0),
        "analysis_eligible_exact_draw_count": sum(
            candidate["analysis_gate_passes"]
            and candidate["exact"]["status"] == "COMPLETED"
            and candidate["exact"]["result"]["forced_result"] == "DRAW"
            for candidate in candidates
        ),
        "shape_clean_exact_draw_count": shape_clean_draws,
        "exact_by_dimension": _dimension_aggregates(candidates),
        "predeclared_assessment": {"exact_completion": assessment},
    }
    return {
        "configuration": {
            "play_seeds": list(seed_tuple),
            "play_gates": asdict(gates),
            "max_exact_states": max_exact_states,
            "exact_routing": "all manifest cases independent of other gates",
            "cheap_routing": "static, asymmetry, and simplicity pass only",
        },
        "aggregate": aggregate,
        "timing": {
            "static_asymmetry_simplicity_seconds": static_seconds,
            "cheap_play_seconds": cheap_seconds,
            "exact_seconds": exact_seconds,
            "total_seconds": total_seconds,
        },
        "candidates": candidates,
    }


def _draw_selection_score(game_hash: str, shape_clean: bool) -> str:
    prefix = _DRAW_STRESS_CLEAN_PREFIX if shape_clean else _DRAW_STRESS_OTHER_PREFIX
    return hashlib.sha256((prefix + game_hash).encode("ascii")).hexdigest()


def _validate_raw_exact_evidence(candidate: Mapping[str, Any]) -> str:
    """Return a known exact status or reject malformed source evidence."""

    exact = candidate.get("exact")
    if not isinstance(exact, Mapping):
        raise ValueError("raw landscape candidate is missing exact evidence")
    status = exact.get("status")
    result = exact.get("result")
    budget_observation = exact.get("budget_observation")
    if status == "COMPLETED":
        if (
            not isinstance(result, Mapping)
            or result.get("forced_result") not in _FORCED_RESULTS
            or budget_observation is not None
        ):
            raise ValueError("raw completed exact evidence is malformed")
    elif status == "CENSORED_STATE_BUDGET":
        if result is not None or not isinstance(budget_observation, Mapping):
            raise ValueError("raw censored exact evidence is malformed")
    else:
        raise ValueError("raw landscape exact status is unknown")
    return status


def select_draw_stress_candidates(
    raw_candidates: Sequence[Mapping[str, Any]],
    max_candidates: int = DRAW_STRESS_MAX_CANDIDATES,
) -> Dict[str, Any]:
    """Select exact draws with shape-clean cases first and no replacement."""

    if max_candidates < 1:
        raise ValueError("draw stress max_candidates must be at least one")
    eligible = []
    seen_hashes: Set[str] = set()
    for candidate in raw_candidates:
        if not isinstance(candidate, Mapping):
            raise ValueError("raw landscape candidates must be objects")
        game_hash = candidate.get("definition_hash")
        if not isinstance(game_hash, str) or game_hash in seen_hashes:
            raise ValueError("raw landscape candidates need unique definition hashes")
        seen_hashes.add(game_hash)
        status = _validate_raw_exact_evidence(candidate)
        if status != "COMPLETED":
            continue
        exact = candidate["exact"]
        result = exact.get("result")
        assert isinstance(result, Mapping)
        if result["forced_result"] != "DRAW":
            continue
        gate_passes = candidate.get("analysis_gate_passes")
        cheap_failure_codes = candidate.get("cheap_failure_codes")
        if not isinstance(gate_passes, bool) or not isinstance(
            cheap_failure_codes, list
        ) or not all(isinstance(code, str) for code in cheap_failure_codes):
            raise ValueError("raw draw candidate has malformed gate or failure evidence")
        shape_clean = gate_passes and not set(cheap_failure_codes).intersection(
            _SHAPE_FAILURES
        )
        eligible.append(
            {
                "candidate": candidate,
                "shape_clean": shape_clean,
                "selection_group": "SHAPE_CLEAN" if shape_clean else "OTHER_DRAW",
                "selection_score": _draw_selection_score(game_hash, shape_clean),
            }
        )
    eligible.sort(
        key=lambda item: (
            not item["shape_clean"],
            item["selection_score"],
            item["candidate"]["definition_hash"],
        )
    )
    selected = eligible[:max_candidates]
    for rank, item in enumerate(selected, start=1):
        item["selection_rank"] = rank
    return {
        "eligible": eligible,
        "selected": selected,
        "unselected": eligible[max_candidates:],
    }


def select_landscape_inspection_cases(
    raw_candidates: Sequence[Mapping[str, Any]],
    stress_candidates: Sequence[Mapping[str, Any]],
    ordinary_count: int = LANDSCAPE_INSPECTION_ORDINARY_COUNT,
) -> Dict[str, Any]:
    """Freeze the predeclared post-result inspection set without changing labels."""

    if ordinary_count < 0:
        raise ValueError("inspection ordinary_count cannot be negative")
    raw_by_hash = {}
    raw_order = []
    reasons: Dict[str, Set[str]] = defaultdict(set)
    for candidate in raw_candidates:
        if not isinstance(candidate, Mapping):
            raise ValueError("raw inspection candidates must be objects")
        game_hash = candidate.get("definition_hash")
        case_id = candidate.get("case_id")
        if (
            not isinstance(game_hash, str)
            or not isinstance(case_id, str)
            or game_hash in raw_by_hash
        ):
            raise ValueError("raw inspection candidates need unique identifiers")
        status = _validate_raw_exact_evidence(candidate)
        raw_by_hash[game_hash] = candidate
        raw_order.append(game_hash)
        if status == "CENSORED_STATE_BUDGET":
            reasons[game_hash].add("EXACT_CENSORED")
        elif candidate["exact"]["result"]["forced_result"] == "DRAW":
            reasons[game_hash].add("EXACT_DRAW")

    seen_stress = set()
    for candidate in stress_candidates:
        if not isinstance(candidate, Mapping):
            raise ValueError("stress inspection candidates must be objects")
        game_hash = candidate.get("definition_hash")
        if game_hash not in raw_by_hash or game_hash in seen_stress:
            raise ValueError("stress inspection candidate does not match raw evidence")
        seen_stress.add(game_hash)
        if candidate.get("case_id") != raw_by_hash[game_hash]["case_id"]:
            raise ValueError("stress inspection case identity mismatch")
        status = candidate.get("status")
        if status == "CENSORED_NODE_BUDGET":
            reasons[game_hash].add("DEPTH5_CENSORED")
        elif status != "EVALUATED":
            raise ValueError("stress inspection candidate status is unknown")
        diagnostic_frontier = candidate.get("diagnostic_frontier")
        if not isinstance(diagnostic_frontier, bool):
            raise ValueError("stress inspection frontier flag is malformed")
        if diagnostic_frontier:
            if status != "EVALUATED":
                raise ValueError("censored stress candidate cannot be a frontier")
            reasons[game_hash].add("DIAGNOSTIC_FRONTIER")

    ordinary = []
    for game_hash in raw_order:
        if reasons[game_hash]:
            continue
        score = hashlib.sha256(
            (_INSPECTION_PREFIX + game_hash).encode("ascii")
        ).hexdigest()
        ordinary.append((score, game_hash))
    ordinary.sort()
    for score, game_hash in ordinary[:ordinary_count]:
        reasons[game_hash].add("HASH_SELECTED_ORDINARY")

    records = []
    for game_hash in raw_order:
        if not reasons[game_hash]:
            continue
        candidate = raw_by_hash[game_hash]
        score = hashlib.sha256(
            (_INSPECTION_PREFIX + game_hash).encode("ascii")
        ).hexdigest()
        records.append(
            {
                "case_id": candidate["case_id"],
                "definition_hash": game_hash,
                "reasons": sorted(reasons[game_hash]),
                "ordinary_selection_score": score,
            }
        )
    mandatory_count = sum(
        "HASH_SELECTED_ORDINARY" not in record["reasons"] for record in records
    )
    ordinary_selected_count = sum(
        "HASH_SELECTED_ORDINARY" in record["reasons"] for record in records
    )
    return {
        "configuration": {
            "ordinary_count": ordinary_count,
            "ordinary_order": "sha256(landscape-inspection-v1:<definition_hash>)",
        },
        "aggregate": {
            "mandatory_case_count": mandatory_count,
            "ordinary_selected_count": ordinary_selected_count,
            "selected_case_count": len(records),
        },
        "cases": records,
    }


def stress_landscape_draws(
    raw_candidates: Sequence[Mapping[str, Any]],
    seeds: Sequence[int] = DRAW_STRESS_SEEDS,
    depth: int = DRAW_STRESS_DEPTH,
    max_nodes_per_candidate: int = DRAW_STRESS_MAX_NODES,
    max_candidates: int = DRAW_STRESS_MAX_CANDIDATES,
    gates: PlayGates = PlayGates(),
    clock: Callable[[], float] = time.perf_counter,
) -> Dict[str, Any]:
    """Adversarially stress completed exact draws with frozen depth-5 play."""

    seed_tuple = _validate_seeds(seeds, "landscape draw stress")
    if depth != DRAW_STRESS_DEPTH:
        raise ValueError("landscape draw stress freezes depth at 5")
    if max_nodes_per_candidate < 1:
        raise ValueError("max_nodes_per_candidate must be at least one")
    selection = select_draw_stress_candidates(raw_candidates, max_candidates)
    exact_statuses = tuple(
        _validate_raw_exact_evidence(candidate) for candidate in raw_candidates
    )
    exact_censored = sum(status != "COMPLETED" for status in exact_statuses)
    records = []
    failure_histogram: Counter[str] = Counter()
    direction_histogram: Counter[str] = Counter()
    expanded_nodes = []
    total_started = clock()
    stress_seconds = 0.0

    for selected in selection["selected"]:
        source = selected["candidate"]
        definition = parse_definition(source["definition"])
        if definition_hash(definition) != source["definition_hash"]:
            raise ValueError("draw-stress definition hash mismatch")
        agent = MinimaxAgent(
            depth=depth,
            max_total_nodes=max_nodes_per_candidate,
        )
        candidate_started = clock()
        try:
            profile = evaluate_matchup(
                definition,
                "stress-minimax-depth5",
                {Player.A: agent, Player.B: agent},
                seed_tuple,
            )
        except SearchBudgetExceeded as error:
            elapsed = clock() - candidate_started
            stress_seconds += elapsed
            expanded_nodes.append(agent.total_nodes)
            records.append(
                {
                    "case_id": source["case_id"],
                    "definition_hash": source["definition_hash"],
                    "d4_canonical_hash": source["d4_canonical_hash"],
                    "stratum": dict(source["stratum"]),
                    "shape_clean": selected["shape_clean"],
                    "selection_group": selected["selection_group"],
                    "selection_score": selected["selection_score"],
                    "selection_rank": selected["selection_rank"],
                    "status": "CENSORED_NODE_BUDGET",
                    "sampled_direction": None,
                    "decisive_misclassification": None,
                    "strong_failure_codes": [],
                    "diagnostic_frontier": False,
                    "expanded_nodes": agent.total_nodes,
                    "elapsed_seconds": elapsed,
                    "budget_observation": {
                        "scope": error.scope,
                        "visited_nodes": error.visited_nodes,
                        "max_nodes": error.max_nodes,
                    },
                    "profile": None,
                    "definition": definition.to_dict(),
                }
            )
            continue

        elapsed = clock() - candidate_started
        stress_seconds += elapsed
        expanded_nodes.append(agent.total_nodes)
        profile_mapping = profile.to_dict(include_records=False)
        direction = sampled_direction(profile_mapping)
        decisive = direction in {"A_WIN", "B_WIN"}
        failures = sorted(
            code.value
            for code in classify_play_failures(definition, (profile,), gates)
        )
        frontier = selected["shape_clean"] and not decisive and not failures
        failure_histogram.update(failures)
        direction_histogram[direction] += 1
        records.append(
            {
                "case_id": source["case_id"],
                "definition_hash": source["definition_hash"],
                "d4_canonical_hash": source["d4_canonical_hash"],
                "stratum": dict(source["stratum"]),
                "shape_clean": selected["shape_clean"],
                "selection_group": selected["selection_group"],
                "selection_score": selected["selection_score"],
                "selection_rank": selected["selection_rank"],
                "status": "EVALUATED",
                "sampled_direction": direction,
                "decisive_misclassification": decisive,
                "strong_failure_codes": failures,
                "diagnostic_frontier": frontier,
                "expanded_nodes": agent.total_nodes,
                "elapsed_seconds": elapsed,
                "budget_observation": None,
                "profile": profile_mapping,
                "definition": definition.to_dict(),
            }
        )

    evaluated = sum(record["status"] == "EVALUATED" for record in records)
    node_censored = len(records) - evaluated
    decisive_hashes = sorted(
        record["definition_hash"]
        for record in records
        if record["decisive_misclassification"] is True
    )
    frontier_records = [record for record in records if record["diagnostic_frontier"]]
    eligible = selection["eligible"]
    unselected = selection["unselected"]
    eligible_clean = sum(item["shape_clean"] for item in eligible)
    unselected_clean = sum(item["shape_clean"] for item in unselected)
    deferred_clean = sum(
        record["shape_clean"] and record["status"] != "EVALUATED"
        for record in records
    )
    candidate_cap_censored = len(unselected)
    if decisive_hashes:
        stress_status = "NOT_SUPPORTED"
        stress_reasons = ["EXACT_DRAW_CALLED_DECISIVE"]
    elif candidate_cap_censored or node_censored or evaluated < 15:
        stress_status = "INCONCLUSIVE"
        stress_reasons = []
        if candidate_cap_censored:
            stress_reasons.append("DRAW_CANDIDATE_CAP_CENSORING")
        if node_censored:
            stress_reasons.append("DEPTH5_NODE_BUDGET_CENSORING")
        if evaluated < 15:
            stress_reasons.append("FEWER_THAN_15_COMPLETIONS")
    else:
        stress_status = "SUPPORTED"
        stress_reasons = []

    frontier_complete = (
        exact_censored == 0
        and unselected_clean == 0
        and deferred_clean == 0
        and not decisive_hashes
    )
    frontier_strata = {
        json.dumps(record["stratum"], sort_keys=True, separators=(",", ":"))
        for record in frontier_records
    }
    frontier_by_stratum: Dict[str, int] = dict(
        sorted(
            Counter(
                json.dumps(
                    record["stratum"], sort_keys=True, separators=(",", ":")
                )
                for record in frontier_records
            ).items()
        )
    )
    if decisive_hashes:
        next_branch = "PRIORITIZE_INDEPENDENT_SOLVER_OR_LEAF_FAMILY"
    elif not frontier_complete:
        next_branch = "FRONTIER_INCONCLUSIVE"
    elif len(frontier_records) >= 4 and len(frontier_strata) >= 2:
        next_branch = "FORM_GENERATOR_V3_HYPOTHESIS"
    elif len(frontier_records) >= 4:
        next_branch = "FREEZE_SINGLE_STRATUM_VALIDATION_SAMPLE"
    elif frontier_records:
        next_branch = "FREEZE_FOCUSED_VALIDATION_SAMPLE"
    else:
        next_branch = "DESIGN_MINIMAL_MECHANIC_TEST"

    total_seconds = clock() - total_started
    aggregate = {
        "raw_exact_censored_count": exact_censored,
        "exact_draw_eligible_count": len(eligible),
        "exact_draw_selected_count": len(records),
        "exact_draw_unselected_count": len(unselected),
        "exact_draw_unselected_hashes": sorted(
            item["candidate"]["definition_hash"] for item in unselected
        ),
        "shape_clean_draw_eligible_count": eligible_clean,
        "shape_clean_draw_selected_count": sum(
            record["shape_clean"] for record in records
        ),
        "shape_clean_draw_unselected_count": unselected_clean,
        "shape_clean_draw_unselected_hashes": sorted(
            item["candidate"]["definition_hash"]
            for item in unselected
            if item["shape_clean"]
        ),
        "evaluated_count": evaluated,
        "node_budget_censored_count": node_censored,
        "node_budget_censored_hashes": sorted(
            record["definition_hash"]
            for record in records
            if record["status"] == "CENSORED_NODE_BUDGET"
        ),
        "candidate_cap_censored_count": candidate_cap_censored,
        "sampled_direction_histogram": dict(sorted(direction_histogram.items())),
        "exact_draw_decisive_misclassification_count": len(decisive_hashes),
        "exact_draw_decisive_misclassification_hashes": decisive_hashes,
        "strong_failure_histogram": dict(sorted(failure_histogram.items())),
        "diagnostic_frontier_count": len(frontier_records),
        "diagnostic_frontier_hashes": sorted(
            record["definition_hash"] for record in frontier_records
        ),
        "diagnostic_frontier_stratum_count": len(frontier_strata),
        "diagnostic_frontier_by_stratum": frontier_by_stratum,
        "expanded_nodes_total": sum(expanded_nodes),
        "expanded_nodes_max": max(expanded_nodes, default=0),
        "frontier_assessment": {
            "status": "COMPLETE" if frontier_complete else "INCONCLUSIVE",
            "reasons": [
                reason
                for condition, reason in (
                    (exact_censored > 0, "RAW_EXACT_CENSORING"),
                    (unselected_clean > 0, "SHAPE_CLEAN_DRAW_CANDIDATE_CAP"),
                    (deferred_clean > 0, "SHAPE_CLEAN_DRAW_NODE_BUDGET"),
                    (bool(decisive_hashes), "EXACT_DRAW_CALLED_DECISIVE"),
                )
                if condition
            ],
        },
        "predeclared_assessment": {
            "draw_stress": {
                "status": stress_status,
                "reasons": stress_reasons,
            }
        },
        "next_branch": next_branch,
    }
    return {
        "configuration": {
            "depth": depth,
            "seeds": list(seed_tuple),
            "max_nodes_per_candidate": max_nodes_per_candidate,
            "max_candidates": max_candidates,
            "play_gates": asdict(gates),
            "selection": (
                "shape-clean exact draws by sha256(draw-stress-clean-v1:<hash>), "
                "then other exact draws by sha256(draw-stress-other-v1:<hash>)"
            ),
        },
        "aggregate": aggregate,
        "timing": {
            "depth5_seconds": stress_seconds,
            "total_seconds": total_seconds,
        },
        "candidates": records,
        "inspection_selection": select_landscape_inspection_cases(
            raw_candidates, records
        ),
    }
