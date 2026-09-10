import json
import unittest
from pathlib import Path

from parity_forge.analysis import analyze_mapping
from parity_forge.dsl import parse_definition
from parity_forge.simplicity import evaluate_simplicity, exceeds_limits

from tests.support import crossing_definition


ROOT = Path(__file__).resolve().parents[1]


class StaticAnalysisTests(unittest.TestCase):
    def test_frozen_corpus_classifications(self) -> None:
        path = ROOT / "experiments" / "corpora" / "static-v1" / "corpus.json"
        with path.open("r", encoding="utf-8") as source:
            corpus = json.load(source)
        self.assertTrue(corpus["frozen"])
        self.assertGreaterEqual(len(corpus["cases"]), 7)
        for case in corpus["cases"]:
            with self.subTest(case=case["id"]):
                report = analyze_mapping(case["definition"])
                actual = {code.value for code in report.failure_codes}
                self.assertEqual(actual, set(case["expected_failures"]))

    def test_simplicity_dimensions_are_separate_and_stable(self) -> None:
        report = evaluate_simplicity(parse_definition(crossing_definition()))
        self.assertEqual(report.structural.action_types, 2)
        self.assertEqual(report.structural.piece_types, 2)
        self.assertEqual(report.structural.numeric_parameters, 10)
        self.assertEqual(report.description.independent_statements, 9)
        self.assertEqual(report.operational.max_action_parameters, 4)
        self.assertEqual(report.operational.initial_legal_actions, 8)
        self.assertFalse(exceeds_limits(report))


if __name__ == "__main__":
    unittest.main()
