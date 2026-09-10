import json
import tempfile
import unittest
from pathlib import Path

from parity_forge.batch import BatchConfig
from parity_forge.cascade import StrongCascadeConfig
from parity_forge.dsl import definition_hash, parse_definition
from parity_forge.experiments import (
    check_static_corpus,
    run_blind_heldout_audit,
    run_static_corpus,
    run_strong_generation_batch,
)

from tests.support import crossing_definition


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "experiments" / "corpora" / "static-v1" / "corpus.json"


class ExperimentTests(unittest.TestCase):
    def test_heldout_runner_fails_closed_on_configuration_drift(self) -> None:
        config = StrongCascadeConfig(
            base=BatchConfig(
                generator_seed=1,
                candidate_count=1,
                play_seeds=(0,),
                generator_version=2,
            ),
            strong_seeds=(0,),
        )
        with self.assertRaisesRegex(ValueError, "differs from preregistration"):
            run_strong_generation_batch(
                config,
                Path("unused"),
                ROOT,
                development_source={},
            )

    def test_corpus_check_is_reproducible(self) -> None:
        corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
        self.assertEqual(check_static_corpus(corpus), check_static_corpus(corpus))
        self.assertEqual(check_static_corpus(corpus)["aggregate"]["mismatching_cases"], 0)

    def test_run_is_created_once_with_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            destination = run_static_corpus(CORPUS, Path(temporary), ROOT)
            record = json.loads(destination.read_text(encoding="utf-8"))
            self.assertEqual(record["status"], "COMPLETED")
            self.assertEqual(record["actual_result"]["mismatching_cases"], 0)
            self.assertEqual(len(record["configuration"]["corpus_sha256"]), 64)
            self.assertEqual(record["configuration"]["seeds"], [])

    def test_blind_heldout_audit_preserves_source_provenance(self) -> None:
        raw = crossing_definition()
        raw["max_plies"] = 1
        definition = parse_definition(raw)
        source = {
            "run_id": "heldout-source",
            "experiment_type": "strong-cascade-held-out-generation",
            "status": "COMPLETED",
            "results": {
                "candidates": [
                    {
                        "definition_hash": definition_hash(definition),
                        "definition": definition.to_dict(),
                        "late_stage": {
                            "admitted": False,
                            "exact_result": {"forced_result": "DRAW"},
                        },
                    }
                ]
            },
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_path = root / "source.json"
            source_path.write_text(json.dumps(source), encoding="utf-8")
            destination = run_blind_heldout_audit(
                source_path,
                (0,),
                5,
                1000,
                root / "runs",
                ROOT,
            )
            record = json.loads(destination.read_text(encoding="utf-8"))

        self.assertEqual(record["status"], "COMPLETED")
        self.assertEqual(
            record["configuration"]["source_strong_run_id"], "heldout-source"
        )
        self.assertEqual(record["actual_result"]["eligible_count"], 1)
        self.assertEqual(record["actual_result"]["predeclared_outcome"], "INCONCLUSIVE")

    def test_observed_exact_draw_error_overrides_small_blind_sample(self) -> None:
        raw = crossing_definition()
        raw["initial_pieces"].extend(
            [
                {"owner": "A", "piece": "seed", "position": [0, 0]},
                {"owner": "A", "piece": "seed", "position": [1, 0]},
            ]
        )
        definition = parse_definition(raw)
        source = {
            "run_id": "heldout-source",
            "experiment_type": "strong-cascade-held-out-generation",
            "status": "COMPLETED",
            "results": {
                "candidates": [
                    {
                        "definition_hash": definition_hash(definition),
                        "definition": definition.to_dict(),
                        "late_stage": {
                            "admitted": True,
                            "exact_result": {"forced_result": "DRAW"},
                        },
                    }
                ]
            },
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_path = root / "source.json"
            source_path.write_text(json.dumps(source), encoding="utf-8")
            destination = run_blind_heldout_audit(
                source_path,
                (0,),
                5,
                100000,
                root / "runs",
                ROOT,
            )
            record = json.loads(destination.read_text(encoding="utf-8"))

        self.assertEqual(
            record["actual_result"]["exact_draw_decisive_misclassifications"],
            1,
        )
        self.assertEqual(
            record["actual_result"]["predeclared_outcome"], "NOT_SUPPORTED"
        )


if __name__ == "__main__":
    unittest.main()
