import json
import unittest
from pathlib import Path

from parity_forge.batch import BatchConfig
from parity_forge.cascade import (
    AdmissionPolicy,
    StrongCascadeConfig,
    admission_reasons,
    assess_primary_hypotheses,
    evaluate_admission_policy,
    screen_strong_batch,
)


ROOT = Path(__file__).resolve().parents[1]
BATCH_RUN = ROOT / "experiments" / "runs" / "20260830T154309225370Z-batch-g20260831" / "run.json"
AUDIT_RUN = ROOT / "experiments" / "runs" / "20260830T154446539528Z-audit-374bfc58" / "run.json"


class StepClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        self.value += 1.0
        return self.value


class CascadeTests(unittest.TestCase):
    def test_predeclared_assessment_has_explicit_denominators(self) -> None:
        aggregate = {
            "admission_rate": 0.40,
            "depth5_attempted": 10,
            "depth5_completion_rate": 0.90,
            "depth5_candidate_budget_deferred": 0,
            "exact_routed": 20,
            "exact_evaluated": 20,
            "exact_draw_count": 2,
            "exact_draw_recall": 1.0,
        }
        supported = assess_primary_hypotheses(aggregate)
        self.assertEqual(supported["overall"], "SUPPORTED")

        no_depth5 = dict(aggregate, depth5_attempted=0, depth5_completion_rate=None)
        self.assertEqual(
            assess_primary_hypotheses(no_depth5)["compute"]["status"],
            "INCONCLUSIVE",
        )

        missed_draw = dict(aggregate, exact_draw_recall=0.5)
        self.assertEqual(
            assess_primary_hypotheses(missed_draw)["admission_draw_recall"][
                "status"
            ],
            "NOT_SUPPORTED",
        )

    def test_admission_requires_nonshort_nondominance_or_weak_draws(self) -> None:
        nondominant = {
            "failure_codes": [],
            "play_profiles": [
                {"profile": "weak-random", "draw_rate": 0.0},
                {"profile": "medium-goal-directed", "draw_rate": 0.0},
            ]
        }
        self.assertEqual(
            admission_reasons(nondominant),
            ("NO_CHEAP_DOMINANCE_CLASSIFICATION",),
        )
        high_draw = {
            "failure_codes": ["B_DOMINANT"],
            "play_profiles": [
                {"profile": "weak-random", "draw_rate": 0.5},
                {"profile": "medium-goal-directed", "draw_rate": 0.0},
            ]
        }
        self.assertEqual(
            admission_reasons(high_draw),
            ("WEAK_RANDOM_HIGH_DRAW",),
        )

    def test_policy_retains_both_frozen_exact_draws(self) -> None:
        batch = json.loads(BATCH_RUN.read_text(encoding="utf-8"))
        audit = json.loads(AUDIT_RUN.read_text(encoding="utf-8"))
        report = evaluate_admission_policy(
            batch["results"]["candidates"],
            audit["results"]["candidates"],
            AdmissionPolicy(),
        )
        self.assertEqual(report["play_candidate_count"], 57)
        self.assertEqual(report["admitted_count"], 25)
        self.assertEqual(report["exact_audited_admitted_count"], 3)
        self.assertEqual(report["admitted_exact_draw_count"], 2)
        self.assertEqual(report["exact_draw_recall"], 1.0)

    def test_policy_rejects_mismatched_exact_corpus(self) -> None:
        candidate = {
            "definition_hash": "candidate",
            "failure_codes": [],
            "play_profiles": [
                {"profile": "weak-random", "draw_rate": 0.0},
                {"profile": "medium-goal-directed", "draw_rate": 0.0},
            ],
        }
        exact = {"definition_hash": "other", "solve": {"forced_result": "DRAW"}}
        with self.assertRaisesRegex(ValueError, "absent"):
            evaluate_admission_policy([candidate], [exact])

    def test_small_strong_batch_is_deterministic_and_budgeted(self) -> None:
        config = StrongCascadeConfig(
            base=BatchConfig(
                generator_seed=11,
                candidate_count=8,
                play_seeds=tuple(range(3)),
                generator_version=2,
            ),
            strong_seeds=(1000,),
            minimax_depth=5,
            max_depth5_board_size=3,
            max_depth5_candidates=1,
            max_nodes_per_candidate=1000,
            exact_max_board_size=3,
            max_exact_candidates=8,
            max_exact_states=5000,
        )
        first = screen_strong_batch(config, clock=StepClock())
        second = screen_strong_batch(config, clock=StepClock())
        self.assertEqual(first, second)
        self.assertLessEqual(first["aggregate"]["depth5_evaluated"], 1)
        self.assertLessEqual(first["aggregate"]["exact_evaluated"], 8)
        self.assertTrue(
            all(
                candidate["late_stage"]["final_status"] is not None
                for candidate in first["candidates"]
            )
        )
        self.assertTrue(
            all("status" not in candidate for candidate in first["candidates"])
        )

    def test_four_by_four_candidate_runs_depth5_lane(self) -> None:
        config = StrongCascadeConfig(
            base=BatchConfig(
                generator_seed=666,
                candidate_count=1,
                play_seeds=(0,),
                generator_version=2,
            ),
            strong_seeds=(1000,),
            minimax_depth=5,
            max_depth5_board_size=4,
            max_depth5_candidates=1,
            max_nodes_per_candidate=100000,
            exact_max_board_size=3,
            max_exact_candidates=1,
            max_exact_states=5000,
        )
        result = screen_strong_batch(config, clock=StepClock())
        candidate = result["candidates"][0]
        late = candidate["late_stage"]

        self.assertEqual(candidate["definition"]["board_size"], 4)
        self.assertEqual(result["aggregate"]["depth5_attempted"], 1)
        self.assertEqual(result["aggregate"]["depth5_evaluated"], 1)
        self.assertEqual(result["aggregate"]["depth5_completion_rate"], 1.0)
        self.assertEqual(result["aggregate"]["exact_attempted"], 0)
        self.assertEqual(
            late["strong_profile_result"]["profile"], "strong-minimax-depth5"
        )
        self.assertGreater(late["strong_expanded_nodes"], 0)
        self.assertIsNone(late["deferred_reason"])

    def test_depth5_budget_exhaustion_is_deferred(self) -> None:
        config = StrongCascadeConfig(
            base=BatchConfig(
                generator_seed=666,
                candidate_count=1,
                play_seeds=(0,),
                generator_version=2,
            ),
            strong_seeds=(1000,),
            minimax_depth=5,
            max_depth5_board_size=4,
            max_depth5_candidates=1,
            max_nodes_per_candidate=1,
            exact_max_board_size=3,
            max_exact_candidates=1,
            max_exact_states=5000,
        )
        result = screen_strong_batch(config, clock=StepClock())
        late = result["candidates"][0]["late_stage"]

        self.assertEqual(result["aggregate"]["depth5_attempted"], 1)
        self.assertEqual(result["aggregate"]["depth5_evaluated"], 0)
        self.assertEqual(late["deferred_reason"], "DEPTH5_NODE_BUDGET_EXHAUSTED")
        self.assertEqual(late["final_status"], "DEFERRED_BUDGET")
        self.assertIsNone(late["strong_profile_result"])
        self.assertEqual(
            late["budget_observation"],
            {"scope": "per-candidate", "visited_nodes": 1, "max_nodes": 1},
        )

    def test_exact_budget_exhaustion_is_deferred(self) -> None:
        config = StrongCascadeConfig(
            base=BatchConfig(
                generator_seed=51,
                candidate_count=1,
                play_seeds=(0,),
                generator_version=2,
            ),
            strong_seeds=(1000,),
            minimax_depth=5,
            max_depth5_board_size=3,
            max_depth5_candidates=1,
            max_nodes_per_candidate=1000,
            exact_max_board_size=3,
            max_exact_candidates=1,
            max_exact_states=1,
        )
        result = screen_strong_batch(config, clock=StepClock())
        candidate = result["candidates"][0]
        late = candidate["late_stage"]

        self.assertEqual(candidate["definition"]["board_size"], 3)
        self.assertEqual(result["aggregate"]["exact_attempted"], 1)
        self.assertEqual(result["aggregate"]["exact_evaluated"], 0)
        self.assertEqual(result["aggregate"]["exact_completion_rate"], 0.0)
        self.assertEqual(late["deferred_reason"], "EXACT_STATE_BUDGET_EXHAUSTED")
        self.assertEqual(late["final_status"], "DEFERRED_BUDGET")
        self.assertIsNone(late["exact_result"])
        self.assertEqual(
            late["budget_observation"],
            {"searched_states": 1, "max_states": 1},
        )

    def test_nonadmitted_exact_draw_stays_not_admitted_after_strong_audit(self) -> None:
        config = StrongCascadeConfig(
            base=BatchConfig(
                generator_seed=292,
                candidate_count=1,
                play_seeds=(0,),
                generator_version=2,
            ),
            strong_seeds=(1000,),
            minimax_depth=5,
            max_depth5_board_size=3,
            max_depth5_candidates=1,
            max_nodes_per_candidate=100000,
            exact_max_board_size=3,
            max_exact_candidates=1,
            max_exact_states=5000,
        )
        result = screen_strong_batch(config, clock=StepClock())
        late = result["candidates"][0]["late_stage"]

        self.assertFalse(late["admitted"])
        self.assertEqual(late["exact_result"]["forced_result"], "DRAW")
        self.assertIsNotNone(late["strong_profile_result"])
        self.assertEqual(result["aggregate"]["exact_evaluated"], 1)
        self.assertEqual(result["aggregate"]["depth5_evaluated"], 1)
        self.assertEqual(result["aggregate"]["exact_draw_count"], 1)
        self.assertEqual(result["aggregate"]["admitted_exact_draw_count"], 0)
        self.assertEqual(result["aggregate"]["exact_draw_recall"], 0.0)
        self.assertEqual(result["aggregate"]["strong_survivors"], 0)
        self.assertEqual(late["final_status"], "NOT_ADMITTED")


if __name__ == "__main__":
    unittest.main()
