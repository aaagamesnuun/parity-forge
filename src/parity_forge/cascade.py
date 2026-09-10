"""Versioned late-stage admission and strong screening cascade."""

from __future__ import annotations

import copy
import hashlib
import time
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, Mapping, Sequence, Set, Tuple

from .agents import MinimaxAgent, SearchBudgetExceeded
from .analysis import FailureCode
from .batch import BatchConfig, classify_play_failures, screen_batch
from .dsl import Player, parse_definition
from .play import evaluate_matchup
from .solver import SolveBudgetExceeded, solve_game


CASCADE_VERSION = 2


@dataclass(frozen=True)
class AdmissionPolicy:
    """Discovery gate declared from the frozen exact-v1 evidence."""

    minimum_weak_draw_rate: float = 0.50
    exclude_too_short: bool = True


@dataclass(frozen=True)
class StrongCascadeConfig:
    base: BatchConfig
    strong_seeds: Tuple[int, ...]
    minimax_depth: int = 5
    max_depth5_board_size: int = 4
    max_depth5_candidates: int = 100
    max_nodes_per_candidate: int = 5000000
    exact_max_board_size: int = 3
    max_exact_candidates: int = 100
    max_exact_states: int = 100000
    admission: AdmissionPolicy = AdmissionPolicy()
    development_definition_hashes: Tuple[str, ...] = ()


_SHAPE_FAILURES = {
    FailureCode.EXCESSIVE_DRAWS,
    FailureCode.TOO_SHORT,
    FailureCode.TOO_LONG,
}


def admission_reasons(
    candidate: Mapping[str, Any], policy: AdmissionPolicy = AdmissionPolicy()
) -> Tuple[str, ...]:
    """Return explicit reasons a cheap-play candidate reaches strong analysis.

    A non-short candidate is admitted when weak random play has at least 50% draws
    or when neither cheap profile produces a frozen dominance classification. This
    retained both exact draws while admitting only one forced win in exact-v1.
    """

    profiles = candidate.get("play_profiles", ())
    if not profiles:
        return ()
    failures = set(
        candidate.get("cheap_stage", {}).get(
            "failure_codes", candidate.get("failure_codes", ())
        )
    )
    if policy.exclude_too_short and FailureCode.TOO_SHORT.value in failures:
        return ()
    weak_profiles = [profile for profile in profiles if profile["profile"] == "weak-random"]
    if len(weak_profiles) != 1:
        raise ValueError("admission requires exactly one weak-random profile")
    weak_high_draw = (
        weak_profiles[0]["draw_rate"] >= policy.minimum_weak_draw_rate
    )
    no_dominance = not failures.intersection(
        (FailureCode.A_DOMINANT.value, FailureCode.B_DOMINANT.value)
    )
    reasons = []
    if weak_high_draw:
        reasons.append("WEAK_RANDOM_HIGH_DRAW")
    if no_dominance:
        reasons.append("NO_CHEAP_DOMINANCE_CLASSIFICATION")
    return tuple(reasons)


def evaluate_admission_policy(
    candidates: Sequence[Mapping[str, Any]],
    exact_candidates: Sequence[Mapping[str, Any]],
    policy: AdmissionPolicy = AdmissionPolicy(),
) -> Dict[str, Any]:
    """Measure admission coverage against an already frozen exact corpus."""

    exact_by_hash = {
        candidate["definition_hash"]: candidate["solve"]["forced_result"]
        for candidate in exact_candidates
    }
    candidate_hashes = {candidate["definition_hash"] for candidate in candidates}
    missing_exact_hashes = sorted(set(exact_by_hash) - candidate_hashes)
    if missing_exact_hashes:
        raise ValueError(
            "exact corpus contains {} definitions absent from candidate corpus".format(
                len(missing_exact_hashes)
            )
        )
    play_candidates = [
        candidate for candidate in candidates if candidate.get("play_profiles")
    ]
    admitted = [
        candidate
        for candidate in play_candidates
        if admission_reasons(candidate, policy)
    ]
    audited_admitted = [
        candidate
        for candidate in admitted
        if candidate["definition_hash"] in exact_by_hash
    ]
    exact_histogram = Counter(
        exact_by_hash[candidate["definition_hash"]] for candidate in audited_admitted
    )
    total_draws = sum(result == "DRAW" for result in exact_by_hash.values())
    admitted_draws = exact_histogram["DRAW"]
    return {
        "policy": asdict(policy),
        "play_candidate_count": len(play_candidates),
        "admitted_count": len(admitted),
        "admission_rate": (
            len(admitted) / len(play_candidates) if play_candidates else None
        ),
        "exact_audited_count": len(exact_by_hash),
        "exact_audited_admitted_count": len(audited_admitted),
        "admitted_exact_result_histogram": dict(sorted(exact_histogram.items())),
        "exact_draw_count": total_draws,
        "admitted_exact_draw_count": admitted_draws,
        "exact_draw_recall": admitted_draws / total_draws if total_draws else None,
        "admitted_hashes": sorted(
            candidate["definition_hash"] for candidate in admitted
        ),
    }


def assess_primary_hypotheses(aggregate: Mapping[str, Any]) -> Dict[str, Any]:
    """Apply the held-out cascade-v2 decision rules without post-hoc judgment."""

    admission_rate = aggregate["admission_rate"]
    depth5_attempted = aggregate["depth5_attempted"]
    depth5_completion_rate = aggregate["depth5_completion_rate"]
    depth5_candidate_deferrals = aggregate[
        "depth5_candidate_budget_deferred"
    ]
    compute_failures = []
    compute_inconclusive = []
    if admission_rate is None:
        compute_inconclusive.append("NO_NOVEL_CHEAP_PLAY_CASES")
    elif admission_rate > 0.50:
        compute_failures.append("ADMISSION_RATE_ABOVE_0_50")
    if depth5_candidate_deferrals:
        compute_failures.append("DEPTH5_CANDIDATE_CAP_EXHAUSTED")
    if depth5_attempted == 0:
        compute_inconclusive.append("NO_DEPTH5_ATTEMPTS")
    elif depth5_completion_rate is None or depth5_completion_rate < 0.90:
        compute_failures.append("DEPTH5_COMPLETION_BELOW_0_90")
    compute_status = (
        "NOT_SUPPORTED"
        if compute_failures
        else "INCONCLUSIVE" if compute_inconclusive else "SUPPORTED"
    )

    exact_routed = aggregate["exact_routed"]
    exact_evaluated = aggregate["exact_evaluated"]
    exact_reasons = []
    if exact_routed == 0:
        exact_reasons.append("NO_EXACT_ELIGIBLE_CASES")
    elif exact_evaluated != exact_routed:
        exact_reasons.append("EXACT_CASE_CENSORED")
    exact_status = "INCONCLUSIVE" if exact_reasons else "SUPPORTED"

    admission_reasons = []
    if exact_status != "SUPPORTED":
        admission_reasons.append("EXACT_AUDIT_INCOMPLETE")
        admission_status = "INCONCLUSIVE"
    elif aggregate["exact_draw_count"] < 2:
        admission_reasons.append("FEWER_THAN_TWO_EXACT_DRAWS")
        admission_status = "INCONCLUSIVE"
    elif aggregate["exact_draw_recall"] != 1.0:
        admission_reasons.append("EXACT_DRAW_FALSE_NEGATIVE")
        admission_status = "NOT_SUPPORTED"
    else:
        admission_status = "SUPPORTED"

    statuses = (compute_status, exact_status, admission_status)
    overall_status = (
        "NOT_SUPPORTED"
        if "NOT_SUPPORTED" in statuses
        else "INCONCLUSIVE" if "INCONCLUSIVE" in statuses else "SUPPORTED"
    )
    return {
        "overall": overall_status,
        "compute": {
            "status": compute_status,
            "failure_reasons": compute_failures,
            "inconclusive_reasons": compute_inconclusive,
        },
        "exact_completion": {
            "status": exact_status,
            "reasons": exact_reasons,
        },
        "admission_draw_recall": {
            "status": admission_status,
            "reasons": admission_reasons,
        },
    }


def _finalize_candidate(candidate: Dict[str, Any]) -> None:
    late = candidate["late_stage"]
    if late["development_overlap"]:
        late["final_failure_codes"] = list(candidate["cheap_stage"]["failure_codes"])
        late["final_status"] = "EXCLUDED_DEVELOPMENT_OVERLAP"
        return
    if not late["admitted"]:
        # The exact lane is an independent audit. Its labels and diagnostics must
        # never rescue a definition that failed the already-sealed admission gate.
        late["final_failure_codes"] = list(candidate["cheap_stage"]["failure_codes"])
        late["final_status"] = (
            "REJECTED_STATIC" if not candidate.get("play_profiles") else "NOT_ADMITTED"
        )
        return
    if late["deferred_reason"] is not None:
        late["final_failure_codes"] = list(candidate["cheap_stage"]["failure_codes"])
        late["final_status"] = "DEFERRED_BUDGET"
        return

    failures: Set[str] = {
        code
        for code in candidate["cheap_stage"]["failure_codes"]
        if code in {failure.value for failure in _SHAPE_FAILURES}
    }
    failures.update(late["strong_failure_codes"])
    exact = late["exact_result"]
    if exact is not None:
        # Exact game-theoretic result supersedes sampled dominance, never observed
        # duration/draw pathologies.
        failures.discard(FailureCode.A_DOMINANT.value)
        failures.discard(FailureCode.B_DOMINANT.value)
        if exact["forced_result"] == "A_WIN":
            failures.add(FailureCode.A_DOMINANT.value)
        elif exact["forced_result"] == "B_WIN":
            failures.add(FailureCode.B_DOMINANT.value)
        elif late["strong_profile_result"] is None:
            raise AssertionError("an exact draw must receive the strong draw diagnostic")
    elif late["strong_profile_result"] is None:
        raise AssertionError("a non-exact late-stage candidate must receive strong play")
    late["final_failure_codes"] = sorted(failures)
    if exact is not None and exact["forced_result"] != "DRAW":
        late["final_status"] = "REJECTED_EXACT"
    elif failures:
        late["final_status"] = "REJECTED_STRONG"
    else:
        late["final_status"] = "SURVIVES_STRONG"


def screen_strong_batch(
    config: StrongCascadeConfig,
    clock: Callable[[], float] = time.perf_counter,
) -> Dict[str, Any]:
    """Run cheap screening, sealed admission, exact 3x3, then depth-5."""

    if not config.strong_seeds:
        raise ValueError("strong cascade requires at least one strong-play seed")
    if len(set(config.strong_seeds)) != len(config.strong_seeds):
        raise ValueError("strong-play seeds must be unique")
    if config.minimax_depth < 1:
        raise ValueError("minimax depth must be at least one")
    if config.minimax_depth != 5:
        raise ValueError("cascade-v2 freezes minimax depth at 5")
    if config.max_depth5_candidates < 1 or config.max_exact_candidates < 1:
        raise ValueError("candidate budgets must be at least one")
    if not config.exact_max_board_size <= config.max_depth5_board_size:
        raise ValueError("exact board-size limit cannot exceed depth-5 board-size limit")
    if config.exact_max_board_size != 3:
        raise ValueError("cascade-v2 freezes exact solving at board size 3")
    if config.max_nodes_per_candidate < 1 or config.max_exact_states < 1:
        raise ValueError("deterministic search budgets must be at least one")

    total_started = clock()
    cheap_started = clock()
    cheap = screen_batch(config.base)
    cheap_seconds = clock() - cheap_started
    records = copy.deepcopy(cheap["candidates"])
    development_hashes = set(config.development_definition_hashes)

    admitted = []
    for candidate in records:
        development_overlap = candidate["definition_hash"] in development_hashes
        reasons = () if development_overlap else admission_reasons(candidate, config.admission)
        candidate["cheap_stage"] = {
            "status": candidate.pop("status"),
            "failure_codes": candidate.pop("failure_codes"),
            "evaluated_stages": candidate.pop("evaluated_stages"),
        }
        candidate["late_stage"] = {
            "admitted": bool(reasons),
            "admission_reasons": list(reasons),
            "development_overlap": development_overlap,
            "exact_routed": False,
            "deferred_reason": None,
            "strong_profile_result": None,
            "strong_failure_codes": [],
            "strong_elapsed_seconds": None,
            "strong_expanded_nodes": None,
            "exact_result": None,
            "exact_elapsed_seconds": None,
            "budget_observation": None,
            "final_failure_codes": [],
            "final_status": None,
        }
        if reasons:
            admitted.append(candidate)

    exact_eligible = sorted(
        (
            candidate
            for candidate in records
            if candidate.get("play_profiles")
            and not candidate["late_stage"]["development_overlap"]
            and candidate["definition"]["board_size"] <= config.exact_max_board_size
        ),
        # Keep the audit sample independent of admission if a diagnostic cap is
        # ever lower than the eligible population.
        key=lambda candidate: candidate["definition_hash"],
    )
    for candidate in exact_eligible:
        candidate["late_stage"]["exact_routed"] = True
    selected_exact = exact_eligible[: config.max_exact_candidates]
    for candidate in exact_eligible[config.max_exact_candidates :]:
        candidate["late_stage"]["deferred_reason"] = (
            "EXACT_CANDIDATE_BUDGET_EXHAUSTED"
        )

    exact_stage_started = clock()
    for candidate in selected_exact:
        definition = parse_definition(candidate["definition"])
        candidate_started = clock()
        try:
            result = solve_game(definition, max_states=config.max_exact_states)
        except SolveBudgetExceeded as error:
            candidate["late_stage"]["deferred_reason"] = (
                "EXACT_STATE_BUDGET_EXHAUSTED"
            )
            candidate["late_stage"]["budget_observation"] = {
                "searched_states": error.searched_states,
                "max_states": error.max_states,
            }
            candidate["late_stage"]["exact_elapsed_seconds"] = (
                clock() - candidate_started
            )
            continue
        elapsed = clock() - candidate_started
        candidate["late_stage"]["exact_result"] = result.to_dict()
        candidate["late_stage"]["exact_elapsed_seconds"] = elapsed
    exact_seconds = clock() - exact_stage_started

    within_board_budget = []
    for candidate in admitted:
        board_size = candidate["definition"]["board_size"]
        if board_size <= config.exact_max_board_size:
            continue
        if board_size > config.max_depth5_board_size:
            candidate["late_stage"]["deferred_reason"] = "BOARD_SIZE_EXCEEDS_DEPTH5_BUDGET"
        else:
            within_board_budget.append(candidate)

    # Exact draws need sampled strong-play draw diagnostics; forced wins do not.
    within_board_budget.extend(
        candidate
        for candidate in selected_exact
        if candidate["late_stage"]["deferred_reason"] is None
        and candidate["late_stage"]["exact_result"] is not None
        and candidate["late_stage"]["exact_result"]["forced_result"] == "DRAW"
    )
    ordered_depth5 = sorted(
        within_board_budget,
        key=lambda candidate: (
            not (
                candidate["late_stage"]["exact_result"] is not None
                and candidate["late_stage"]["exact_result"]["forced_result"] == "DRAW"
            ),
            candidate["definition_hash"],
        ),
    )
    selected_depth5 = ordered_depth5[: config.max_depth5_candidates]
    for candidate in ordered_depth5[config.max_depth5_candidates :]:
        candidate["late_stage"]["deferred_reason"] = "DEPTH5_CANDIDATE_BUDGET_EXHAUSTED"

    strong_agent = MinimaxAgent(
        depth=config.minimax_depth,
        max_total_nodes=config.max_nodes_per_candidate,
    )
    strong_stage_started = clock()
    for candidate in selected_depth5:
        definition = parse_definition(candidate["definition"])
        candidate_started = clock()
        strong_agent.reset_budget()
        try:
            result = evaluate_matchup(
                definition,
                "strong-minimax-depth{}".format(config.minimax_depth),
                {Player.A: strong_agent, Player.B: strong_agent},
                config.strong_seeds,
            )
        except SearchBudgetExceeded as error:
            candidate["late_stage"]["deferred_reason"] = (
                "DEPTH5_NODE_BUDGET_EXHAUSTED"
            )
            candidate["late_stage"]["budget_observation"] = {
                "scope": error.scope,
                "visited_nodes": error.visited_nodes,
                "max_nodes": error.max_nodes,
            }
            candidate["late_stage"]["strong_elapsed_seconds"] = (
                clock() - candidate_started
            )
            continue
        elapsed = clock() - candidate_started
        candidate["late_stage"]["strong_profile_result"] = result.to_dict(
            include_records=False
        )
        candidate["late_stage"]["strong_expanded_nodes"] = strong_agent.total_nodes
        candidate["late_stage"]["strong_failure_codes"] = sorted(
            code.value
            for code in classify_play_failures(definition, (result,), config.base.gates)
        )
        candidate["late_stage"]["strong_elapsed_seconds"] = elapsed
    strong_seconds = clock() - strong_stage_started

    for candidate in records:
        _finalize_candidate(candidate)

    all_final_failure_histogram: Counter[str] = Counter()
    primary_failure_histogram: Counter[str] = Counter()
    status_histogram: Counter[str] = Counter()
    for candidate in records:
        late = candidate["late_stage"]
        all_final_failure_histogram.update(late["final_failure_codes"])
        if not late["development_overlap"]:
            primary_failure_histogram.update(late["final_failure_codes"])
        status_histogram[late["final_status"]] += 1
    survivors = [
        candidate
        for candidate in records
        if candidate["late_stage"]["final_status"] == "SURVIVES_STRONG"
    ]
    novel_records = [
        candidate
        for candidate in records
        if not candidate["late_stage"]["development_overlap"]
    ]
    novel_play_evaluated = sum(
        bool(candidate.get("play_profiles")) for candidate in novel_records
    )

    def frontier_key(candidate: Mapping[str, Any]) -> Tuple[Any, ...]:
        profile = candidate["late_stage"]["strong_profile_result"]
        share = profile["decisive_a_share"]
        fairness_deviation = abs(share - 0.5) if share is not None else 1.0
        return (
            fairness_deviation,
            candidate["simplicity"]["structural"]["numeric_parameters"],
            candidate["definition_hash"],
        )

    total_seconds = clock() - total_started
    depth5_completed = sum(
        candidate["late_stage"]["strong_profile_result"] is not None
        for candidate in selected_depth5
    )
    exact_completed = sum(
        candidate["late_stage"]["exact_result"] is not None
        for candidate in selected_exact
    )
    exact_forced_histogram = Counter(
        candidate["late_stage"]["exact_result"]["forced_result"]
        for candidate in selected_exact
        if candidate["late_stage"]["exact_result"] is not None
    )
    exact_draw_count = exact_forced_histogram["DRAW"]
    admitted_exact_draw_count = sum(
        candidate["late_stage"]["admitted"]
        and candidate["late_stage"]["exact_result"] is not None
        and candidate["late_stage"]["exact_result"]["forced_result"] == "DRAW"
        for candidate in selected_exact
    )
    late_stage_routed = sum(
        candidate["late_stage"]["admitted"]
        or candidate["late_stage"]["exact_routed"]
        for candidate in records
    )
    development_fingerprint = hashlib.sha256(
        "\n".join(sorted(development_hashes)).encode("ascii")
    ).hexdigest()
    strong_node_counts = [
        candidate["late_stage"]["strong_expanded_nodes"]
        if candidate["late_stage"]["strong_expanded_nodes"] is not None
        else candidate["late_stage"]["budget_observation"]["visited_nodes"]
        for candidate in selected_depth5
        if candidate["late_stage"]["strong_expanded_nodes"] is not None
        or (
            candidate["late_stage"]["budget_observation"] is not None
            and "visited_nodes" in candidate["late_stage"]["budget_observation"]
        )
    ]
    exact_state_counts = [
        candidate["late_stage"]["exact_result"]["searched_states"]
        if candidate["late_stage"]["exact_result"] is not None
        else candidate["late_stage"]["budget_observation"]["searched_states"]
        for candidate in selected_exact
        if candidate["late_stage"]["exact_result"] is not None
        or (
            candidate["late_stage"]["budget_observation"] is not None
            and "searched_states" in candidate["late_stage"]["budget_observation"]
        )
    ]

    def strata(field: str) -> Dict[str, Dict[str, int]]:
        keys = sorted(
            {str(candidate["definition"][field]) for candidate in novel_records}
        )
        result: Dict[str, Dict[str, int]] = {}
        for key in keys:
            subset = [
                candidate
                for candidate in novel_records
                if str(candidate["definition"][field]) == key
            ]
            result[key] = {
                "generated": len(subset),
                "cheap_play_evaluated": sum(
                    bool(candidate.get("play_profiles")) for candidate in subset
                ),
                "admitted": sum(
                    candidate["late_stage"]["admitted"] for candidate in subset
                ),
                "exact_evaluated": sum(
                    candidate["late_stage"]["exact_result"] is not None
                    for candidate in subset
                ),
                "depth5_evaluated": sum(
                    candidate["late_stage"]["strong_profile_result"] is not None
                    for candidate in subset
                ),
                "deferred": sum(
                    candidate["late_stage"]["deferred_reason"] is not None
                    for candidate in subset
                ),
                "survives_strong": sum(
                    candidate["late_stage"]["final_status"] == "SURVIVES_STRONG"
                    for candidate in subset
                ),
            }
        return result

    deferred_reason_histogram = Counter(
        candidate["late_stage"]["deferred_reason"]
        for candidate in novel_records
        if candidate["late_stage"]["deferred_reason"] is not None
    )
    aggregate = {
        "generated_unique": len(records),
        "novel_generated": len(novel_records),
        "cheap_play_evaluated": cheap["aggregate"]["play_evaluated"],
        "novel_cheap_play_evaluated": novel_play_evaluated,
        "late_stage_admitted": len(admitted),
        "admission_rate": (
            len(admitted) / novel_play_evaluated if novel_play_evaluated else None
        ),
        "exact_routed": len(exact_eligible),
        "late_stage_routed": late_stage_routed,
        "depth5_attempted": len(selected_depth5),
        "depth5_evaluated": depth5_completed,
        "depth5_completion_rate": (
            depth5_completed / len(selected_depth5) if selected_depth5 else None
        ),
        "depth5_expanded_nodes_total": sum(strong_node_counts),
        "depth5_expanded_nodes_max": max(strong_node_counts, default=0),
        "exact_attempted": len(selected_exact),
        "exact_evaluated": exact_completed,
        "exact_completion_rate": (
            exact_completed / len(exact_eligible) if exact_eligible else None
        ),
        "exact_forced_result_histogram": dict(
            sorted(exact_forced_histogram.items())
        ),
        "exact_draw_count": exact_draw_count,
        "admitted_exact_draw_count": admitted_exact_draw_count,
        "exact_draw_recall": (
            admitted_exact_draw_count / exact_draw_count
            if exact_draw_count
            else None
        ),
        "exact_searched_states_total": sum(exact_state_counts),
        "exact_searched_states_max": max(exact_state_counts, default=0),
        "strong_survivors": len(survivors),
        "primary_status_deferred": status_histogram["DEFERRED_BUDGET"],
        "any_lane_deferred": sum(deferred_reason_histogram.values()),
        "depth5_node_budget_deferred": deferred_reason_histogram[
            "DEPTH5_NODE_BUDGET_EXHAUSTED"
        ],
        "depth5_candidate_budget_deferred": deferred_reason_histogram[
            "DEPTH5_CANDIDATE_BUDGET_EXHAUSTED"
        ],
        "exact_state_budget_deferred": deferred_reason_histogram[
            "EXACT_STATE_BUDGET_EXHAUSTED"
        ],
        "exact_candidate_budget_deferred": deferred_reason_histogram[
            "EXACT_CANDIDATE_BUDGET_EXHAUSTED"
        ],
        "board_size_deferred": deferred_reason_histogram[
            "BOARD_SIZE_EXCEEDS_DEPTH5_BUDGET"
        ],
        "development_overlaps": status_histogram[
            "EXCLUDED_DEVELOPMENT_OVERLAP"
        ],
        "deferred_reason_histogram": dict(sorted(deferred_reason_histogram.items())),
        "by_board_size": strata("board_size"),
        "by_first_player": strata("first_player"),
        "status_histogram": dict(sorted(status_histogram.items())),
        "final_failure_histogram": dict(sorted(primary_failure_histogram.items())),
        "all_final_failure_histogram": dict(
            sorted(all_final_failure_histogram.items())
        ),
        "frontier": [
            candidate["definition_hash"]
            for candidate in sorted(survivors, key=frontier_key)[:10]
        ],
    }
    aggregate["predeclared_assessment"] = assess_primary_hypotheses(aggregate)
    return {
        "configuration": {
            "cascade_version": CASCADE_VERSION,
            "base": cheap["configuration"],
            "strong_seeds": list(config.strong_seeds),
            "minimax_depth": config.minimax_depth,
            "max_depth5_board_size": config.max_depth5_board_size,
            "max_depth5_candidates": config.max_depth5_candidates,
            "max_nodes_per_candidate": config.max_nodes_per_candidate,
            "exact_max_board_size": config.exact_max_board_size,
            "max_exact_candidates": config.max_exact_candidates,
            "max_exact_states": config.max_exact_states,
            "admission_policy": asdict(config.admission),
            "development_definition_count": len(development_hashes),
            "development_definitions_sha256": development_fingerprint,
        },
        "aggregate": aggregate,
        "timing": {
            "cheap_cascade_seconds": cheap_seconds,
            "depth5_play_seconds": strong_seconds,
            "exact_solve_seconds": exact_seconds,
            "total_seconds": total_seconds,
        },
        "candidates": records,
    }
