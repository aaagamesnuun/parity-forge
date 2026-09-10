import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import parity_forge.capture as capture
import parity_forge.capture_experiments as experiments
from tests.test_capture import _baseline_case, _tiny_manifest, _treatment_case


class CaptureExperimentRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        _, self.manifest = _tiny_manifest()
        self.pairs = tuple(self.manifest["pairs"])
        self.baseline_candidates = [
            {"case_id": pair["source_case_id"]} for pair in self.pairs
        ]
        self.source_raw = {
            "run_id": experiments.SOURCE_LANDSCAPE_RAW_RUN_ID,
            "results": {"candidates": copy.deepcopy(self.baseline_candidates)},
        }

    def test_stage_cases_pin_baseline_and_treatment_identity_and_order(self) -> None:
        baseline = [_baseline_case(pair) for pair in self.pairs]
        treatment = [_treatment_case(pair) for pair in self.pairs]
        with patch.object(experiments, "CAPTURE_PAIR_COUNT", len(self.pairs)):
            experiments._validate_stage_cases(
                baseline, self.pairs, treatment=False
            )
            experiments._validate_stage_cases(
                treatment, self.pairs, treatment=True
            )

            alterations = {
                "baseline-reversed": (list(reversed(baseline)), False),
                "baseline-identity": (
                    [
                        {**baseline[0], "definition_hash": "0" * 64},
                        baseline[1],
                    ],
                    False,
                ),
                "treatment-duplicated": ([treatment[0], treatment[0]], True),
                "treatment-extra-key": (
                    [{**treatment[0], "unexpected": True}, treatment[1]],
                    True,
                ),
            }
            for label, (cases, is_treatment) in alterations.items():
                with self.subTest(label=label):
                    with self.assertRaisesRegex(
                        ValueError, "identity or order|schema mismatch"
                    ):
                        experiments._validate_stage_cases(
                            cases, self.pairs, treatment=is_treatment
                        )

    def test_raw_configuration_is_exact_path_bound_and_pins_state_bound(self) -> None:
        recorded_root = Path("/recorded/parity-forge")
        configuration = raw_configuration(self.manifest, recorded_root)
        experiments._validate_capture_raw_configuration(
            configuration, self.manifest
        )

        mutations = {
            "extra-key": ("unexpected", True),
            "structural-bound": (
                "structural_state_bound",
                experiments.CAPTURE_STATE_BOUND + 1,
            ),
            "exact-cap": (
                "max_exact_states",
                experiments.CAPTURE_EXACT_MAX_STATES - 1,
            ),
            "phase-order": (
                "phase_order",
                list(reversed(experiments._RAW_PHASE_ORDER)),
            ),
            "boolean-seed": (
                "play_seeds",
                [False, *list(experiments.CAPTURE_PLAY_SEEDS)[1:]],
            ),
            "different-root": (
                "source_landscape_raw_path",
                str(
                    Path("/different/repository")
                    / experiments.SOURCE_LANDSCAPE_RAW_RELATIVE
                ),
            ),
        }
        for label, (key, value) in mutations.items():
            with self.subTest(label=label):
                altered = copy.deepcopy(configuration)
                altered[key] = value
                with self.assertRaisesRegex(ValueError, "configuration|roots"):
                    experiments._validate_capture_raw_configuration(
                        altered, self.manifest
                    )

    def test_stress_configuration_is_exact_path_and_raw_hash_bound(self) -> None:
        recorded_root = Path("/recorded/parity-forge")
        raw_record = {"run_id": "synthetic-capture-raw", "results": {}}
        configuration = stress_configuration(
            self.manifest, raw_record, recorded_root
        )
        experiments._validate_capture_stress_configuration(
            configuration, self.manifest, raw_record
        )

        mutations = {
            "extra-key": ("unexpected", True),
            "depth": ("depth", experiments.CAPTURE_STRESS_DEPTH + 1),
            "candidate-cap": (
                "max_candidates",
                experiments.CAPTURE_STRESS_MAX_CANDIDATES + 1,
            ),
            "raw-hash": ("source_raw_sha256", "0" * 64),
            "boolean-seed": (
                "seeds",
                [False, *list(experiments.CAPTURE_STRESS_SEEDS)[1:]],
            ),
            "different-root": (
                "source_raw_path",
                str(
                    Path("/different/repository/experiments/runs")
                    / raw_record["run_id"]
                    / "run.json"
                ),
            ),
        }
        for label, (key, value) in mutations.items():
            with self.subTest(label=label):
                altered = copy.deepcopy(configuration)
                altered[key] = value
                with self.assertRaisesRegex(ValueError, "configuration|roots"):
                    experiments._validate_capture_stress_configuration(
                        altered, self.manifest, raw_record
                    )

    def test_baseline_mismatch_prevents_treatment_evaluation(self) -> None:
        with temporary_capture_paths() as paths:
            calls = {"baseline": 0, "treatment": 0}

            def baseline_evaluator(cases, **kwargs):
                del cases, kwargs
                calls["baseline"] += 1
                return {"candidates": copy.deepcopy(self.baseline_candidates)}

            def treatment_evaluator(cases, **kwargs):
                del cases, kwargs
                calls["treatment"] += 1
                raise AssertionError("treatment must not be called")

            def paired_evaluator(
                manifest,
                pinned,
                *,
                baseline_evaluator,
                treatment_evaluator,
            ):
                del pinned
                baseline_evaluator(stage_cases(manifest, treatment=False))
                treatment_evaluator(stage_cases(manifest, treatment=True))
                raise AssertionError("unreachable")

            baseline_validator = Mock(
                side_effect=ValueError("synthetic baseline replay mismatch")
            )
            with patched_raw_preflight(
                paths, self.manifest, self.pairs, self.source_raw
            ), patch.object(
                experiments,
                "validate_capture_baseline_replay",
                baseline_validator,
            ):
                with self.assertRaisesRegex(ValueError, "baseline replay mismatch"):
                    experiments.run_capture_paired(
                        paths["manifest"],
                        paths["lock"],
                        paths["source_raw"],
                        paths["output"],
                        paths["repository"],
                        paired_evaluator=paired_evaluator,
                        baseline_evaluator=baseline_evaluator,
                        treatment_evaluator=treatment_evaluator,
                    )

            self.assertEqual(calls, {"baseline": 1, "treatment": 0})
            self.assertEqual(baseline_validator.call_count, 1)
            self.assertEqual(
                load_only_failure(paths["output"])["phase"],
                "BASELINE_REPLAY_ATTESTATION",
            )

    def test_evidence_mutation_at_phase_boundary_prevents_treatment(self) -> None:
        with temporary_capture_paths() as paths:
            calls = {"baseline": 0, "treatment": 0}

            def baseline_evaluator(cases, **kwargs):
                del cases, kwargs
                calls["baseline"] += 1
                paths["manifest"].write_bytes(b"mutated after baseline")
                return {"candidates": copy.deepcopy(self.baseline_candidates)}

            def treatment_evaluator(cases, **kwargs):
                del cases, kwargs
                calls["treatment"] += 1
                raise AssertionError("treatment must not be called")

            def paired_evaluator(
                manifest,
                pinned,
                *,
                baseline_evaluator,
                treatment_evaluator,
            ):
                del pinned
                baseline_evaluator(stage_cases(manifest, treatment=False))
                treatment_evaluator(stage_cases(manifest, treatment=True))
                raise AssertionError("unreachable")

            with patched_raw_preflight(
                paths, self.manifest, self.pairs, self.source_raw
            ), patch.object(
                experiments, "validate_capture_baseline_replay", return_value=()
            ):
                with self.assertRaisesRegex(ValueError, "bytes changed"):
                    experiments.run_capture_paired(
                        paths["manifest"],
                        paths["lock"],
                        paths["source_raw"],
                        paths["output"],
                        paths["repository"],
                        paired_evaluator=paired_evaluator,
                        baseline_evaluator=baseline_evaluator,
                        treatment_evaluator=treatment_evaluator,
                    )

            self.assertEqual(calls, {"baseline": 1, "treatment": 0})
            self.assertEqual(
                load_only_failure(paths["output"])["phase"],
                "TREATMENT_EVALUATION",
            )

    def test_runner_rejects_reversed_or_duplicated_callback_cases(self) -> None:
        scenarios = ("treatment-first", "baseline-reversed", "treatment-duplicated")
        for scenario in scenarios:
            with self.subTest(scenario=scenario), temporary_capture_paths() as paths:
                baseline = Mock(
                    return_value={
                        "candidates": copy.deepcopy(self.baseline_candidates)
                    }
                )
                treatment = Mock(
                    side_effect=AssertionError("underlying treatment must not run")
                )

                def paired_evaluator(
                    manifest,
                    pinned,
                    *,
                    baseline_evaluator,
                    treatment_evaluator,
                ):
                    del pinned
                    baseline_cases = stage_cases(manifest, treatment=False)
                    treatment_cases = stage_cases(manifest, treatment=True)
                    if scenario == "treatment-first":
                        treatment_evaluator(treatment_cases)
                    elif scenario == "baseline-reversed":
                        baseline_evaluator(list(reversed(baseline_cases)))
                    else:
                        baseline_evaluator(baseline_cases)
                        treatment_evaluator(
                            [treatment_cases[0], treatment_cases[0]]
                        )
                    raise AssertionError("unreachable")

                with patched_raw_preflight(
                    paths, self.manifest, self.pairs, self.source_raw
                ), patch.object(
                    experiments,
                    "validate_capture_baseline_replay",
                    return_value=(),
                ):
                    with self.assertRaisesRegex(
                        ValueError,
                        "attested baseline|identity or order",
                    ):
                        experiments.run_capture_paired(
                            paths["manifest"],
                            paths["lock"],
                            paths["source_raw"],
                            paths["output"],
                            paths["repository"],
                            paired_evaluator=paired_evaluator,
                            baseline_evaluator=baseline,
                            treatment_evaluator=treatment,
                        )

                treatment.assert_not_called()
                if scenario == "treatment-duplicated":
                    self.assertEqual(baseline.call_count, 1)
                else:
                    baseline.assert_not_called()

    def test_runner_calls_stages_once_in_order_with_frozen_arguments(self) -> None:
        with temporary_capture_paths() as paths:
            events = []

            def assert_arguments(kwargs):
                self.assertEqual(
                    set(kwargs),
                    {"play_seeds", "max_exact_states", "gates", "clock"},
                )
                self.assertEqual(kwargs["play_seeds"], experiments.CAPTURE_PLAY_SEEDS)
                self.assertEqual(
                    kwargs["max_exact_states"],
                    experiments.CAPTURE_EXACT_MAX_STATES,
                )
                self.assertEqual(kwargs["gates"], experiments.PlayGates())
                self.assertTrue(callable(kwargs["clock"]))

            def baseline_evaluator(cases, **kwargs):
                assert_arguments(kwargs)
                events.append(("baseline", [item["case_id"] for item in cases]))
                return {"candidates": copy.deepcopy(self.baseline_candidates)}

            def treatment_evaluator(cases, **kwargs):
                assert_arguments(kwargs)
                events.append(
                    (
                        "treatment",
                        [item["source_case_id"] for item in cases],
                    )
                )
                raise RuntimeError("synthetic treatment stop")

            def paired_evaluator(
                manifest,
                pinned,
                *,
                baseline_evaluator,
                treatment_evaluator,
            ):
                del pinned
                baseline_evaluator(stage_cases(manifest, treatment=False))
                treatment_evaluator(stage_cases(manifest, treatment=True))
                raise AssertionError("unreachable")

            with patched_raw_preflight(
                paths, self.manifest, self.pairs, self.source_raw
            ), patch.object(
                experiments, "validate_capture_baseline_replay", return_value=()
            ):
                with self.assertRaisesRegex(RuntimeError, "synthetic treatment stop"):
                    experiments.run_capture_paired(
                        paths["manifest"],
                        paths["lock"],
                        paths["source_raw"],
                        paths["output"],
                        paths["repository"],
                        paired_evaluator=paired_evaluator,
                        baseline_evaluator=baseline_evaluator,
                        treatment_evaluator=treatment_evaluator,
                    )

            expected_ids = [pair["source_case_id"] for pair in self.pairs]
            self.assertEqual(
                events,
                [("baseline", expected_ids), ("treatment", expected_ids)],
            )

    def test_reserved_raw_directory_collision_preserves_sentinel_and_writes_sidecar(self) -> None:
        with temporary_capture_paths() as paths:
            real_reserve = experiments._reserve_protocol
            collision = {}

            def reserve_with_collision(
                output_root, protocol_id, run_id, commit, started_at
            ):
                reservation = real_reserve(
                    output_root, protocol_id, run_id, commit, started_at
                )
                run_directory = output_root / run_id
                run_directory.mkdir()
                sentinel = run_directory / "sentinel.txt"
                sentinel.write_text("preserve", encoding="utf-8")
                collision["sentinel"] = sentinel
                return reservation

            with patched_raw_preflight(
                paths, self.manifest, self.pairs, self.source_raw
            ), patch.object(
                experiments, "_reserve_protocol", side_effect=reserve_with_collision
            ):
                with self.assertRaises(FileExistsError):
                    experiments.run_capture_paired(
                        paths["manifest"],
                        paths["lock"],
                        paths["source_raw"],
                        paths["output"],
                        paths["repository"],
                    )

            self.assertEqual(
                collision["sentinel"].read_text(encoding="utf-8"), "preserve"
            )
            sidecar = paths["output"] / ".{}.failure.json".format(
                experiments.CAPTURE_RAW_PROTOCOL_ID
            )
            failure = json.loads(sidecar.read_text(encoding="utf-8"))
            self.assertEqual(failure["phase"], "RAW_RUN_DIRECTORY_SETUP")
            self.assertEqual(failure["error"]["type"], "FileExistsError")

    def test_exact_censor_blocks_stress_before_reservation(self) -> None:
        with temporary_capture_paths() as paths:
            raw_record = {
                "run_id": "synthetic-capture-raw",
                "results": {
                    "aggregate": {
                        "exact_censored": 1,
                        "adaptive_stress_disposition": "BLOCKED_EXACT_CENSOR",
                    },
                    "pre_stress_inspection": {
                        "adaptive_stress_disposition": "BLOCKED_EXACT_CENSOR"
                    },
                },
            }
            stress = Mock(side_effect=AssertionError("stress must not run"))
            with patched_stress_preflight(paths, self.manifest, raw_record):
                with self.assertRaisesRegex(ValueError, "exact censoring blocks"):
                    experiments.run_capture_interaction_stress(
                        paths["raw_run"],
                        paths["manifest"],
                        paths["lock"],
                        paths["output"],
                        paths["repository"],
                        stress_evaluator=stress,
                    )
            stress.assert_not_called()
            self.assertFalse(stress_reservation(paths["output"]).exists())

    def test_ply_limit_alone_does_not_block_stress_reservation(self) -> None:
        with temporary_capture_paths() as paths:
            raw_record = {
                "run_id": "synthetic-capture-raw",
                "results": {
                    "aggregate": {
                        "exact_censored": 0,
                        "treatment_ply_limit_count": 1,
                        "adaptive_stress_disposition": "ELIGIBLE",
                    },
                    "pre_stress_inspection": {
                        "adaptive_stress_disposition": "ELIGIBLE"
                    },
                },
            }
            stress = Mock(side_effect=RuntimeError("synthetic stress stop"))
            with patched_stress_preflight(
                paths, self.manifest, raw_record
            ), patch.object(
                experiments, "_require_clean_repository", return_value="a" * 40
            ), patch.object(
                experiments, "_require_same_fingerprints", return_value=None
            ), patch.object(
                experiments, "_chain_hashes", return_value={}
            ):
                with self.assertRaisesRegex(RuntimeError, "synthetic stress stop"):
                    experiments.run_capture_interaction_stress(
                        paths["raw_run"],
                        paths["manifest"],
                        paths["lock"],
                        paths["output"],
                        paths["repository"],
                        stress_evaluator=stress,
                    )
            self.assertEqual(stress.call_count, 1)
            self.assertTrue(stress_reservation(paths["output"]).exists())
            self.assertEqual(
                load_only_failure(paths["output"])["phase"],
                "INTERACTION_STRESS_EVALUATION",
            )

    def test_narratives_are_derived_from_assessments_and_decisions(self) -> None:
        raw_result = {
            "aggregate": {
                "adaptive_stress_disposition": "BLOCKED_EXACT_CENSOR",
                "predeclared_assessment": {
                    "exact_completion": {"status": "INCONCLUSIVE"},
                    "primary_counterplay_response": {"status": "NOT_SUPPORTED"},
                    "realized_capture_response": {"status": "INCONCLUSIVE"},
                },
            },
            "timing": {"used_for_assessment": False},
        }
        raw_narrative = experiments._raw_narrative(raw_result)
        self.assertEqual(
            raw_narrative["decision"], "AUDIT_STATE_BOUND_OR_SOLVER"
        )
        self.assertIn("Exact completion is INCONCLUSIVE", raw_narrative["interpretation"])
        raw_record = completed_record(raw_result, raw_narrative)
        experiments._validate_completed_narrative(
            raw_record, raw_result, experiments._raw_narrative, "capture raw"
        )

        stress_result = {
            "aggregate": {
                "predeclared_assessment": {
                    "general_strong_response": {"status": "SUPPORTED"},
                    "interaction_frontier": {"status": "SUPPORTED"},
                    "overall_interaction_response": {
                        "status": "INCONCLUSIVE",
                        "next_branch": "FOCUSED_OUTCOME_BLIND_VALIDATION",
                    },
                }
            }
        }
        stress_narrative = experiments._stress_narrative(stress_result)
        self.assertEqual(
            stress_narrative["decision"], "FOCUSED_OUTCOME_BLIND_VALIDATION"
        )
        self.assertIn(
            "overall interaction response is INCONCLUSIVE",
            stress_narrative["interpretation"],
        )
        stress_record = completed_record(stress_result, stress_narrative)
        experiments._validate_completed_narrative(
            stress_record,
            stress_result,
            experiments._stress_narrative,
            "capture stress",
        )

        for label, record, result, builder in (
            ("raw", raw_record, raw_result, experiments._raw_narrative),
            (
                "stress",
                stress_record,
                stress_result,
                experiments._stress_narrative,
            ),
        ):
            with self.subTest(label=label):
                altered = copy.deepcopy(record)
                altered["decision"] = "UNREGISTERED_BRANCH"
                with self.assertRaisesRegex(ValueError, "narrative fields"):
                    experiments._validate_completed_narrative(
                        altered, result, builder, label
                    )

    def test_manifest_raw_and_stress_protocol_ids_are_distinct(self) -> None:
        self.assertEqual(
            len(
                {
                    capture.CAPTURE_PROTOCOL_ID,
                    experiments.CAPTURE_RAW_PROTOCOL_ID,
                    experiments.CAPTURE_STRESS_PROTOCOL_ID,
                }
            ),
            3,
        )
        self.assertEqual(experiments.CAPTURE_PROTOCOL_ID, capture.CAPTURE_PROTOCOL_ID)


def raw_configuration(manifest, recorded_root: Path):
    return {
        "manifest_id": experiments.CAPTURE_MANIFEST_ID,
        "manifest_path": str(recorded_root / experiments.CAPTURE_MANIFEST_RELATIVE),
        "manifest_sha256": hashlib.sha256(
            experiments._encoded_json(manifest)
        ).hexdigest(),
        "source_landscape_raw_run_id": experiments.SOURCE_LANDSCAPE_RAW_RUN_ID,
        "source_landscape_raw_path": str(
            recorded_root / experiments.SOURCE_LANDSCAPE_RAW_RELATIVE
        ),
        "source_landscape_raw_sha256": experiments.SOURCE_LANDSCAPE_RAW_SHA256,
        "play_seeds": list(experiments.CAPTURE_PLAY_SEEDS),
        "play_gates": experiments.asdict(experiments.PlayGates()),
        "max_exact_states": experiments.CAPTURE_EXACT_MAX_STATES,
        "structural_state_bound": experiments.CAPTURE_STATE_BOUND,
        "replay_attestation_version": experiments.CAPTURE_REPLAY_ATTESTATION_VERSION,
        "phase_order": list(experiments._RAW_PHASE_ORDER),
    }


def stress_configuration(manifest, raw_record, recorded_root: Path):
    return {
        "manifest_id": experiments.CAPTURE_MANIFEST_ID,
        "manifest_path": str(recorded_root / experiments.CAPTURE_MANIFEST_RELATIVE),
        "manifest_sha256": hashlib.sha256(
            experiments._encoded_json(manifest)
        ).hexdigest(),
        "source_raw_run_id": raw_record["run_id"],
        "source_raw_path": str(
            recorded_root
            / "experiments/runs"
            / raw_record["run_id"]
            / "run.json"
        ),
        "source_raw_sha256": hashlib.sha256(
            experiments._encoded_json(raw_record)
        ).hexdigest(),
        "seeds": list(experiments.CAPTURE_STRESS_SEEDS),
        "depth": experiments.CAPTURE_STRESS_DEPTH,
        "max_nodes_per_candidate": experiments.CAPTURE_STRESS_MAX_NODES,
        "max_candidates": experiments.CAPTURE_STRESS_MAX_CANDIDATES,
        "play_gates": experiments.asdict(experiments.PlayGates()),
    }


def stage_cases(manifest, treatment: bool):
    builder = _treatment_case if treatment else _baseline_case
    return [builder(pair) for pair in manifest["pairs"]]


class temporary_capture_paths:
    def __enter__(self):
        self.temporary = tempfile.TemporaryDirectory()
        repository = Path(self.temporary.name)
        output = repository / "experiments/runs"
        output.mkdir(parents=True)

        paths = {
            "repository": repository,
            "output": output,
            "manifest": repository / experiments.CAPTURE_MANIFEST_RELATIVE,
            "lock": repository / experiments.CAPTURE_LOCK_RELATIVE,
            "source_raw": repository / experiments.SOURCE_LANDSCAPE_RAW_RELATIVE,
            "raw_run": output / "synthetic-capture-raw" / "run.json",
        }
        evidence_paths = (
            repository / experiments.CAPTURE_MANIFEST_RESERVATION_RELATIVE,
            repository / experiments.CAPTURE_MANIFEST_ATTEMPT_RELATIVE,
            paths["manifest"],
            paths["lock"],
            repository / experiments.SOURCE_LANDSCAPE_MANIFEST_RELATIVE,
            repository / experiments.SOURCE_LANDSCAPE_LOCK_RELATIVE,
            repository / experiments.SOURCE_LANDSCAPE_ATTEMPT_RELATIVE,
            repository
            / "experiments/runs/.{}.reservation.json".format(
                experiments.LANDSCAPE_RAW_PROTOCOL_ID
            ),
            paths["source_raw"].parent / "attempt.json",
            paths["source_raw"],
            paths["raw_run"],
        )
        for index, path in enumerate(evidence_paths):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {
                        "fixture": index,
                        "protocol_id": "synthetic-upstream",
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
        self.paths = paths
        return paths

    def __exit__(self, exc_type, exc_value, traceback):
        return self.temporary.__exit__(exc_type, exc_value, traceback)


def patched_raw_preflight(paths, manifest, pairs, source_raw):
    manifest_bytes = experiments._encoded_json(manifest)
    paths["manifest"].write_bytes(manifest_bytes)
    return patch.multiple(
        experiments,
        CAPTURE_PAIR_COUNT=len(pairs),
        _validate_frozen_capture_manifest=Mock(
            return_value=(manifest_bytes, manifest)
        ),
        validate_capture_paired_manifest=Mock(return_value=pairs),
        _validate_source_landscape_raw=Mock(
            return_value=(paths["source_raw"].read_bytes(), source_raw)
        ),
        _require_clean_repository=Mock(return_value="a" * 40),
        _require_same_fingerprints=Mock(return_value=None),
    )


def patched_stress_preflight(paths, manifest, raw_record):
    manifest_bytes = experiments._encoded_json(manifest)
    raw_bytes = experiments._encoded_json(raw_record)
    paths["manifest"].write_bytes(manifest_bytes)
    paths["raw_run"].write_bytes(raw_bytes)
    return patch.multiple(
        experiments,
        _validate_frozen_capture_manifest=Mock(
            return_value=(manifest_bytes, manifest)
        ),
        _validate_capture_paired_raw_source=Mock(
            return_value=(raw_bytes, raw_record)
        ),
    )


def stress_reservation(output_root: Path):
    return output_root / ".{}.reservation.json".format(
        experiments.CAPTURE_STRESS_PROTOCOL_ID
    )


def load_only_failure(output_root: Path):
    failures = list(output_root.glob("*/failure.json"))
    if len(failures) != 1:
        raise AssertionError("expected one failure record, got {}".format(failures))
    return json.loads(failures[0].read_text(encoding="utf-8"))


def completed_record(result, narrative):
    record = {key: None for key in experiments._COMPLETED_RUN_KEYS}
    record.update(copy.deepcopy(narrative))
    record["results"] = result
    return record


if __name__ == "__main__":
    unittest.main()
