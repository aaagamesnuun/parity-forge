import copy
import unittest
from unittest.mock import patch

from parity_forge.analysis import FailureCode
from parity_forge.dsl import Player, definition_hash, parse_definition
from parity_forge.landscape_evaluation import (
    evaluate_landscape_cases,
    select_draw_stress_candidates,
    select_landscape_inspection_cases,
    stress_landscape_draws,
)
from parity_forge.symmetry import d4_canonical_hash

from tests.support import crossing_definition


class StepClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        self.value += 1.0
        return self.value


def _case(raw, case_id="case"):
    definition = parse_definition(raw)
    return {
        "case_id": case_id,
        "stratum": {
            "first_player": definition.first_player.value,
            "goal_axis_relation": "ALIGNED",
            "runner_start_class": "EDGE_MIDPOINT",
            "max_plies": definition.max_plies,
            "vector_count_band": "1_TO_3",
        },
        "vector_count": len(definition.role(Player.B).action.vectors),
        "definition_hash": definition_hash(definition),
        "d4_canonical_hash": d4_canonical_hash(definition),
        "definition": definition.to_dict(),
    }


def _one_ply_draw_raw(name="One-ply draw"):
    raw = crossing_definition()
    raw["name"] = name
    raw["max_plies"] = 1
    return raw


def _raw_draw_candidate(index, shape_clean=False):
    raw = _one_ply_draw_raw("One-ply draw {}".format(index))
    definition = parse_definition(raw)
    return {
        "case_id": "draw-{}".format(index),
        "definition_hash": definition_hash(definition),
        "d4_canonical_hash": "orbit-{}".format(index),
        "stratum": {
            "first_player": "A",
            "goal_axis_relation": "ALIGNED",
            "runner_start_class": "EDGE_MIDPOINT",
            "max_plies": 1,
            "vector_count_band": "1_TO_3",
        },
        "vector_count": 4,
        "definition": definition.to_dict(),
        "analysis_gate_passes": shape_clean,
        "cheap_failure_codes": [],
        "exact": {
            "status": "COMPLETED",
            "result": {"forced_result": "DRAW"},
        },
    }


class LandscapeEvaluationTests(unittest.TestCase):
    def test_exact_routing_ignores_static_rejection(self) -> None:
        raw = _one_ply_draw_raw("Unreachable runner")
        raw["roles"]["B"]["action"]["vectors"] = [[1, 0]]
        result = evaluate_landscape_cases(
            (_case(raw),),
            play_seeds=(0,),
            max_exact_states=1000,
            clock=StepClock(),
        )
        candidate = result["candidates"][0]

        self.assertFalse(candidate["analysis_gate_passes"])
        self.assertIn(
            FailureCode.UNREACHABLE_WIN_CONDITION.value,
            [item["code"] for item in candidate["static"]["diagnostics"]],
        )
        self.assertEqual(candidate["cheap_profiles"], [])
        self.assertEqual(candidate["exact"]["status"], "COMPLETED")
        self.assertEqual(result["aggregate"]["cheap_attempted"], 0)
        self.assertEqual(result["aggregate"]["exact_attempted"], 1)
        self.assertEqual(
            result["aggregate"]["exact_draw_terminal_reason_histogram"],
            {"PLY_LIMIT": 1},
        )

    def test_exact_budget_censor_keeps_the_manifest_denominator(self) -> None:
        result = evaluate_landscape_cases(
            (_case(_one_ply_draw_raw()),),
            play_seeds=(0,),
            max_exact_states=1,
            clock=StepClock(),
        )
        aggregate = result["aggregate"]
        candidate = result["candidates"][0]

        self.assertEqual(aggregate["manifest_case_count"], 1)
        self.assertEqual(aggregate["exact_attempted"], 1)
        self.assertEqual(aggregate["exact_completed"], 0)
        self.assertEqual(aggregate["exact_censored"], 1)
        self.assertEqual(
            aggregate["predeclared_assessment"]["exact_completion"]["status"],
            "INCONCLUSIVE",
        )
        self.assertEqual(candidate["exact"]["status"], "CENSORED_STATE_BUDGET")
        self.assertEqual(
            candidate["exact"]["budget_observation"]["searched_states"], 1
        )

    def test_draw_selection_is_hash_stable_and_shape_clean_first(self) -> None:
        candidates = [_raw_draw_candidate(index, index in (1, 3)) for index in range(5)]
        forced = copy.deepcopy(candidates[4])
        forced["definition_hash"] = "f" * 64
        forced["exact"]["result"]["forced_result"] = "A_WIN"
        selection = select_draw_stress_candidates(
            tuple(reversed(candidates + [forced])), max_candidates=2
        )

        self.assertEqual(len(selection["eligible"]), 5)
        self.assertEqual(len(selection["selected"]), 2)
        self.assertTrue(all(item["shape_clean"] for item in selection["selected"]))
        self.assertEqual(
            [item["selection_score"] for item in selection["selected"]],
            sorted(item["selection_score"] for item in selection["selected"]),
        )

    def test_draw_stress_requires_fifteen_uncensored_completions(self) -> None:
        fourteen = stress_landscape_draws(
            tuple(_raw_draw_candidate(index) for index in range(14)),
            clock=StepClock(),
        )
        fifteen = stress_landscape_draws(
            tuple(_raw_draw_candidate(index) for index in range(15)),
            clock=StepClock(),
        )

        self.assertEqual(
            fourteen["aggregate"]["predeclared_assessment"]["draw_stress"]["status"],
            "INCONCLUSIVE",
        )
        self.assertEqual(
            fifteen["aggregate"]["predeclared_assessment"]["draw_stress"]["status"],
            "SUPPORTED",
        )
        self.assertEqual(fifteen["aggregate"]["evaluated_count"], 15)
        self.assertEqual(
            fifteen["aggregate"]["exact_draw_decisive_misclassification_count"],
            0,
        )

    def test_decisive_draw_error_precedes_small_sample_inconclusive(self) -> None:
        raw = _one_ply_draw_raw("Fabricated draw-label error")
        raw["initial_pieces"].extend(
            [
                {"owner": "A", "piece": "seed", "position": [0, 0]},
                {"owner": "A", "piece": "seed", "position": [1, 0]},
            ]
        )
        candidate = _raw_draw_candidate(0)
        definition = parse_definition(raw)
        candidate["definition_hash"] = definition_hash(definition)
        candidate["definition"] = definition.to_dict()
        result = stress_landscape_draws((candidate,), clock=StepClock())

        self.assertEqual(
            result["aggregate"]["exact_draw_decisive_misclassification_count"], 1
        )
        self.assertEqual(
            result["aggregate"]["predeclared_assessment"]["draw_stress"]["status"],
            "NOT_SUPPORTED",
        )
        self.assertEqual(
            result["aggregate"]["next_branch"],
            "PRIORITIZE_INDEPENDENT_SOLVER_OR_LEAF_FAMILY",
        )

    def test_node_censor_never_creates_a_frontier(self) -> None:
        candidate = _raw_draw_candidate(0, shape_clean=True)
        result = stress_landscape_draws(
            (candidate,),
            max_nodes_per_candidate=1,
            clock=StepClock(),
        )
        aggregate = result["aggregate"]

        self.assertEqual(aggregate["node_budget_censored_count"], 1)
        self.assertEqual(aggregate["diagnostic_frontier_count"], 0)
        self.assertEqual(aggregate["frontier_assessment"]["status"], "INCONCLUSIVE")
        self.assertEqual(
            aggregate["predeclared_assessment"]["draw_stress"]["status"],
            "INCONCLUSIVE",
        )

    def test_malformed_completed_exact_fails_closed(self) -> None:
        candidate = _raw_draw_candidate(0)
        candidate["exact"]["result"]["forced_result"] = "UNKNOWN"

        with self.assertRaisesRegex(ValueError, "completed exact"):
            select_draw_stress_candidates((candidate,))
        with self.assertRaisesRegex(ValueError, "completed exact"):
            stress_landscape_draws((candidate,), clock=StepClock())

    def test_decisive_draw_error_is_never_a_frontier_case(self) -> None:
        raw = _one_ply_draw_raw("Fabricated decisive draw")
        raw["initial_pieces"].extend(
            [
                {"owner": "A", "piece": "seed", "position": [0, 0]},
                {"owner": "A", "piece": "seed", "position": [1, 0]},
            ]
        )
        candidate = _raw_draw_candidate(0, shape_clean=True)
        definition = parse_definition(raw)
        candidate["definition_hash"] = definition_hash(definition)
        candidate["definition"] = definition.to_dict()

        with patch(
            "parity_forge.landscape_evaluation.classify_play_failures",
            return_value=set(),
        ):
            result = stress_landscape_draws((candidate,), clock=StepClock())

        self.assertEqual(
            result["aggregate"]["exact_draw_decisive_misclassification_count"], 1
        )
        self.assertEqual(result["aggregate"]["diagnostic_frontier_count"], 0)
        self.assertEqual(
            result["aggregate"]["frontier_assessment"],
            {
                "status": "INCONCLUSIVE",
                "reasons": ["EXACT_DRAW_CALLED_DECISIVE"],
            },
        )

    def test_frontier_branch_distinguishes_single_and_multiple_strata(self) -> None:
        same_stratum = tuple(
            _raw_draw_candidate(index, shape_clean=True) for index in range(4)
        )
        multiple_strata = copy.deepcopy(same_stratum)
        multiple_strata[3]["stratum"]["goal_axis_relation"] = "ORTHOGONAL"

        with patch(
            "parity_forge.landscape_evaluation.classify_play_failures",
            return_value=set(),
        ):
            same = stress_landscape_draws(same_stratum, clock=StepClock())
            multiple = stress_landscape_draws(multiple_strata, clock=StepClock())

        self.assertEqual(
            same["aggregate"]["next_branch"],
            "FREEZE_SINGLE_STRATUM_VALIDATION_SAMPLE",
        )
        self.assertEqual(same["aggregate"]["diagnostic_frontier_stratum_count"], 1)
        self.assertEqual(
            multiple["aggregate"]["next_branch"],
            "FORM_GENERATOR_V3_HYPOTHESIS",
        )
        self.assertEqual(
            multiple["aggregate"]["diagnostic_frontier_stratum_count"], 2
        )

    def test_empty_draw_set_has_complete_frontier_but_inconclusive_stress(self) -> None:
        candidate = _raw_draw_candidate(0)
        candidate["exact"]["result"]["forced_result"] = "A_WIN"
        result = stress_landscape_draws((candidate,), clock=StepClock())
        aggregate = result["aggregate"]

        self.assertEqual(aggregate["exact_draw_eligible_count"], 0)
        self.assertEqual(aggregate["frontier_assessment"]["status"], "COMPLETE")
        self.assertEqual(
            aggregate["predeclared_assessment"]["draw_stress"]["status"],
            "INCONCLUSIVE",
        )
        self.assertEqual(aggregate["next_branch"], "DESIGN_MINIMAL_MECHANIC_TEST")

    def test_candidate_cap_only_censors_frontier_for_unselected_clean_draws(self) -> None:
        clean = tuple(
            _raw_draw_candidate(index, shape_clean=True) for index in range(33)
        )
        dirty = tuple(_raw_draw_candidate(index) for index in range(33))
        with patch(
            "parity_forge.landscape_evaluation.classify_play_failures",
            return_value=set(),
        ):
            clean_result = stress_landscape_draws(clean, clock=StepClock())
            dirty_result = stress_landscape_draws(dirty, clock=StepClock())

        self.assertEqual(
            clean_result["aggregate"]["frontier_assessment"]["status"],
            "INCONCLUSIVE",
        )
        self.assertEqual(
            clean_result["aggregate"]["next_branch"], "FRONTIER_INCONCLUSIVE"
        )
        self.assertEqual(
            dirty_result["aggregate"]["frontier_assessment"]["status"],
            "COMPLETE",
        )
        self.assertEqual(
            dirty_result["aggregate"]["next_branch"], "DESIGN_MINIMAL_MECHANIC_TEST"
        )
        self.assertEqual(
            dirty_result["aggregate"]["predeclared_assessment"]["draw_stress"][
                "status"
            ],
            "INCONCLUSIVE",
        )
        self.assertEqual(
            dirty_result["configuration"]["play_gates"],
            {
                "max_draw_rate": 0.5,
                "min_average_plies": 4.0,
                "max_average_plies_fraction": 0.85,
                "dominance_interval_margin": 0.05,
                "disagreement_threshold": 0.15,
            },
        )

    def test_inspection_selection_includes_all_mandatory_and_sixteen_ordinary(self) -> None:
        candidates = [_raw_draw_candidate(index) for index in range(20)]
        for candidate in candidates[1:]:
            candidate["exact"]["result"]["forced_result"] = "A_WIN"
        candidates[1]["exact"] = {
            "status": "CENSORED_STATE_BUDGET",
            "result": None,
            "budget_observation": {"searched_states": 100, "max_states": 100},
        }
        stress = (
            {
                "case_id": candidates[0]["case_id"],
                "definition_hash": candidates[0]["definition_hash"],
                "status": "EVALUATED",
                "diagnostic_frontier": True,
            },
        )

        selection = select_landscape_inspection_cases(candidates, stress)
        by_hash = {
            case["definition_hash"]: case for case in selection["cases"]
        }
        self.assertEqual(selection["aggregate"]["mandatory_case_count"], 2)
        self.assertEqual(selection["aggregate"]["ordinary_selected_count"], 16)
        self.assertEqual(selection["aggregate"]["selected_case_count"], 18)
        self.assertEqual(
            by_hash[candidates[0]["definition_hash"]]["reasons"],
            ["DIAGNOSTIC_FRONTIER", "EXACT_DRAW"],
        )
        self.assertEqual(
            by_hash[candidates[1]["definition_hash"]]["reasons"],
            ["EXACT_CENSORED"],
        )


if __name__ == "__main__":
    unittest.main()
