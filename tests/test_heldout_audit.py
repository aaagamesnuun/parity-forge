import copy
import unittest

from parity_forge.dsl import definition_hash, parse_definition
from parity_forge.heldout_audit import blind_depth5_audit

from tests.support import crossing_definition


def strong_candidate(raw, forced_result, admitted):
    definition = parse_definition(raw)
    return {
        "definition_hash": definition_hash(definition),
        "definition": definition.to_dict(),
        "late_stage": {
            "admitted": admitted,
            "exact_result": {"forced_result": forced_result},
        },
    }


class HeldoutAuditTests(unittest.TestCase):
    def test_exact_3x3_selection_ignores_admission_and_input_order(self) -> None:
        draw = crossing_definition()
        draw["max_plies"] = 1
        not_admitted = strong_candidate(draw, "DRAW", admitted=False)

        larger = crossing_definition()
        larger["board_size"] = 4
        larger["initial_pieces"][0]["position"] = [3, 1]
        ignored_board = strong_candidate(larger, "DRAW", admitted=True)

        no_exact = copy.deepcopy(not_admitted)
        no_exact["definition"]["name"] = "No exact result"
        no_exact["definition_hash"] = definition_hash(
            parse_definition(no_exact["definition"])
        )
        no_exact["late_stage"]["exact_result"] = None

        candidates = [ignored_board, no_exact, not_admitted]
        preserved = copy.deepcopy(candidates)
        first = blind_depth5_audit(candidates, (0, 1), 1000)
        second = blind_depth5_audit(tuple(reversed(candidates)), (0, 1), 1000)

        self.assertEqual(first, second)
        self.assertEqual(candidates, preserved)
        self.assertEqual(first["aggregate"]["eligible_count"], 1)
        self.assertEqual(first["aggregate"]["not_admitted_count"], 1)
        self.assertEqual(first["aggregate"]["matching_directions"], 1)
        self.assertEqual(first["aggregate"]["direction_accuracy"], 1.0)
        self.assertEqual(first["candidates"][0]["sampled_direction"], "DRAW_OR_BALANCED")

    def test_cumulative_node_budget_defers_without_a_direction(self) -> None:
        draw = crossing_definition()
        draw["max_plies"] = 1
        candidate = strong_candidate(draw, "DRAW", admitted=False)

        report = blind_depth5_audit([candidate], (0, 1), 1)

        self.assertEqual(report["aggregate"]["evaluated_count"], 0)
        self.assertEqual(report["aggregate"]["deferred_count"], 1)
        self.assertIsNone(report["aggregate"]["direction_accuracy"])
        self.assertEqual(report["aggregate"]["expanded_nodes_total"], 1)
        record = report["candidates"][0]
        self.assertEqual(record["status"], "DEFERRED_NODE_BUDGET")
        self.assertIsNone(record["sampled_direction"])
        self.assertEqual(record["budget_observation"]["scope"], "per-candidate")

    def test_exact_draw_decisive_misclassification_is_counted(self) -> None:
        immediate_a = crossing_definition()
        immediate_a["initial_pieces"].extend(
            [
                {"owner": "A", "piece": "seed", "position": [0, 0]},
                {"owner": "A", "piece": "seed", "position": [1, 0]},
            ]
        )
        # The deliberately contradictory exact label exercises the blind
        # comparison path without mocking the evaluator.
        candidate = strong_candidate(immediate_a, "DRAW", admitted=True)

        report = blind_depth5_audit([candidate], (7,), 100000)

        self.assertEqual(report["aggregate"]["evaluated_count"], 1)
        self.assertEqual(report["aggregate"]["matching_directions"], 0)
        self.assertEqual(report["aggregate"]["direction_accuracy"], 0.0)
        self.assertEqual(
            report["aggregate"]["exact_draw_decisive_misclassifications"], 1
        )
        self.assertEqual(report["candidates"][0]["sampled_direction"], "A_WIN")
        self.assertTrue(
            report["candidates"][0]["exact_draw_decisive_misclassification"]
        )

    def test_configuration_validation_is_explicit(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one seed"):
            blind_depth5_audit([], (), 100)
        with self.assertRaisesRegex(ValueError, "unique"):
            blind_depth5_audit([], (1, 1), 100)
        with self.assertRaisesRegex(ValueError, "depth at 5"):
            blind_depth5_audit([], (1,), 100, depth=3)
        with self.assertRaisesRegex(ValueError, "at least one"):
            blind_depth5_audit([], (1,), 0)


if __name__ == "__main__":
    unittest.main()
