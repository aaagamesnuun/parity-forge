import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import parity_forge.stalemate as stalemate
import parity_forge.stalemate_experiments as experiments


ROOT = Path(__file__).resolve().parents[1]


class StalemateExperimentRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _, cls.source_manifest = experiments._validate_source_landscape_manifest(
            experiments.default_source_landscape_manifest_path(ROOT), ROOT
        )
        cls.manifest = stalemate.build_stalemate_paired_manifest(
            cls.source_manifest,
            stalemate.STALEMATE_SOURCE_MANIFEST_SHA256,
            {"fixture": True, "executable_fingerprints": {"fixture": "value"}},
        )
        _, cls.source_raw = experiments._validate_source_landscape_raw(
            experiments.default_source_landscape_raw_path(ROOT),
            ROOT,
            cls.manifest["pairs"],
        )

    def test_runner_uses_canonical_stalemate_contract(self) -> None:
        self.assertIs(
            experiments.build_stalemate_paired_manifest,
            stalemate.build_stalemate_paired_manifest,
        )
        self.assertIs(
            experiments.validate_stalemate_paired_manifest,
            stalemate.validate_stalemate_paired_manifest,
        )
        self.assertIs(
            experiments.evaluate_stalemate_pairs,
            stalemate.evaluate_stalemate_pairs,
        )
        self.assertIs(
            experiments.stress_stalemate_draws,
            stalemate.stress_stalemate_draws,
        )
        self.assertIs(
            experiments.validate_stalemate_paired_result,
            stalemate.validate_stalemate_paired_result,
        )
        self.assertIs(
            experiments.validate_stalemate_baseline_replay,
            stalemate.validate_stalemate_baseline_replay,
        )
        self.assertIs(
            experiments.validate_stalemate_stress_result,
            stalemate.validate_stalemate_stress_result,
        )
        self.assertEqual(
            experiments.STALEMATE_MANIFEST_ID, stalemate.STALEMATE_MANIFEST_ID
        )
        self.assertEqual(stalemate.STALEMATE_PROTOCOL_ID, self.manifest["protocol_id"])
        self.assertFalse(hasattr(experiments, "build_stalemate_manifest_payload"))
        self.assertFalse(hasattr(experiments, "summarize_stalemate_pairs"))
        self.assertFalse(hasattr(experiments, "select_stalemate_stress_candidates"))

    def test_historical_manifest_and_raw_are_exactly_pinned(self) -> None:
        manifest_path = experiments.default_source_landscape_manifest_path(ROOT)
        raw_path = experiments.default_source_landscape_raw_path(ROOT)
        self.assertEqual(
            hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            stalemate.STALEMATE_SOURCE_MANIFEST_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(raw_path.read_bytes()).hexdigest(),
            experiments.SOURCE_LANDSCAPE_RAW_SHA256,
        )
        self.assertEqual(
            self.source_raw["run_id"], experiments.SOURCE_LANDSCAPE_RAW_RUN_ID
        )
        self.assertEqual(len(self.manifest["pairs"]), stalemate.STALEMATE_PAIR_COUNT)

    def test_manifest_provenance_is_repository_relative(self) -> None:
        with patch.object(
            experiments,
            "_frozen_source_fingerprints_at_commit",
            return_value={"plan": "hash"},
        ), patch.object(
            experiments,
            "_current_fingerprints",
            return_value={"code": "hash"},
        ):
            provenance = experiments._manifest_provenance(
                ROOT, "a" * 40, "2026-08-31T00:00:00.000000Z"
            )
        source_path = provenance["source_manifest_path"]
        self.assertEqual(
            source_path, str(experiments.SOURCE_LANDSCAPE_MANIFEST_RELATIVE)
        )
        self.assertFalse(Path(source_path).is_absolute())
        self.assertTrue(provenance["baseline_outcomes_informed_protocol_design"])
        self.assertFalse(provenance["case_membership_outcome_fields_consulted"])
        self.assertFalse(provenance["treatment_outcomes_computed"])

    def test_frozen_manifest_rejects_extra_attempt_and_provenance_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            corpus = repository / experiments.STALEMATE_CORPUS_RELATIVE
            corpus.mkdir(parents=True)
            manifest_path = corpus / "manifest.json"
            lock_path = corpus / "manifest.lock.json"
            attempt_path = corpus / "manifest-attempt.json"
            reservation_path = corpus / "manifest-reservation.json"
            started_at = "2026-08-31T00:00:00.000000Z"
            commit = "a" * 40
            protocol_fingerprints = {
                str(experiments._FROZEN_PROTOCOL_RELATIVES[0]): "plan-hash"
            }
            executable_fingerprints = {
                str(experiments._FROZEN_EXECUTABLE_RELATIVES[0]): "code-hash"
            }
            provenance = {
                "freezer_git_commit": commit,
                "freezer_git_dirty": False,
                "created_at": started_at,
                "protocol_id": stalemate.STALEMATE_PROTOCOL_ID,
                "source_manifest_path": str(
                    experiments.SOURCE_LANDSCAPE_MANIFEST_RELATIVE
                ),
                "source_manifest_sha256": (
                    stalemate.STALEMATE_SOURCE_MANIFEST_SHA256
                ),
                "baseline_outcomes_informed_protocol_design": True,
                "case_membership_outcome_fields_consulted": False,
                "source_manifest_contains_outcomes": False,
                "treatment_outcomes_computed": False,
                "protocol_fingerprints": protocol_fingerprints,
                "executable_fingerprints": executable_fingerprints,
            }
            manifest = json.loads(json.dumps(self.manifest))
            manifest["provenance"] = provenance
            manifest_bytes = experiments._encoded_json(manifest)
            manifest_path.write_bytes(manifest_bytes)
            lock = {
                "manifest_id": stalemate.STALEMATE_MANIFEST_ID,
                "protocol_id": stalemate.STALEMATE_PROTOCOL_ID,
                "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                "manifest_bytes": len(manifest_bytes),
                "freezer_git_commit": commit,
            }
            attempt = {
                "run_id": stalemate.STALEMATE_MANIFEST_ID,
                "protocol_id": stalemate.STALEMATE_PROTOCOL_ID,
                "experiment_type": (
                    "baseline-informed-treatment-outcome-free-paired-manifest"
                ),
                "status": "STARTED",
                "started_at": started_at,
                "git_commit": commit,
                "git_dirty": False,
                "environment": {"python": "fixture", "platform": "fixture"},
                "component_versions": dict(
                    experiments._MANIFEST_COMPONENT_VERSIONS
                ),
                "configuration": {
                    "source_manifest_id": stalemate.STALEMATE_SOURCE_MANIFEST_ID,
                    "source_manifest_path": str(
                        repository / experiments.SOURCE_LANDSCAPE_MANIFEST_RELATIVE
                    ),
                    "source_manifest_sha256": (
                        stalemate.STALEMATE_SOURCE_MANIFEST_SHA256
                    ),
                    "destination": str(corpus),
                    "baseline_outcomes_informed_protocol_design": True,
                    "case_membership_outcome_fields_consulted": False,
                    "treatment_outcomes_computed": False,
                },
            }
            reservation = {
                "run_id": stalemate.STALEMATE_MANIFEST_ID,
                "protocol_id": stalemate.STALEMATE_PROTOCOL_ID,
                "status": "RESERVED",
                "reserved_at": started_at,
                "git_commit": commit,
            }

            def write_json(path, value):
                path.write_text(
                    json.dumps(value, sort_keys=True) + "\n", encoding="utf-8"
                )

            write_json(lock_path, lock)
            write_json(attempt_path, attempt)
            write_json(reservation_path, reservation)
            with patch.object(
                experiments, "_require_tracked"
            ), patch.object(
                experiments, "_require_commit_ancestor", return_value=commit
            ), patch.object(
                experiments,
                "_validate_source_landscape_manifest",
                return_value=(b"source", self.source_manifest),
            ), patch.object(
                experiments,
                "_frozen_source_fingerprints_at_commit",
                return_value=protocol_fingerprints,
            ), patch.object(
                experiments,
                "_current_fingerprints",
                return_value=executable_fingerprints,
            ):
                loaded_bytes, loaded = experiments._validate_frozen_stalemate_manifest(
                    manifest_path, lock_path, repository
                )
                self.assertEqual(loaded_bytes, manifest_bytes)
                self.assertEqual(loaded, manifest)

                failure_path = corpus / "manifest-failure.json"
                failure_path.write_text("{}\n", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "failure evidence"):
                    experiments._validate_frozen_stalemate_manifest(
                        manifest_path, lock_path, repository
                    )
                failure_path.unlink()

                attempt["unexpected"] = True
                write_json(attempt_path, attempt)
                with self.assertRaisesRegex(ValueError, "attempt mismatch"):
                    experiments._validate_frozen_stalemate_manifest(
                        manifest_path, lock_path, repository
                    )
                del attempt["unexpected"]
                write_json(attempt_path, attempt)

                manifest["provenance"]["unexpected"] = True
                manifest_bytes = experiments._encoded_json(manifest)
                manifest_path.write_bytes(manifest_bytes)
                lock["manifest_sha256"] = hashlib.sha256(manifest_bytes).hexdigest()
                lock["manifest_bytes"] = len(manifest_bytes)
                write_json(lock_path, lock)
                with self.assertRaisesRegex(ValueError, "provenance schema mismatch"):
                    experiments._validate_frozen_stalemate_manifest(
                        manifest_path, lock_path, repository
                    )

    def test_manifest_lock_hashes_exact_canonical_builder_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            corpus = repository / experiments.STALEMATE_CORPUS_RELATIVE
            corpus.parent.mkdir(parents=True)
            source_path = repository / experiments.SOURCE_LANDSCAPE_MANIFEST_RELATIVE
            provenance = {
                "created_at": "2026-08-31T00:00:00.000000Z",
                "source_manifest_path": str(
                    experiments.SOURCE_LANDSCAPE_MANIFEST_RELATIVE
                ),
                "source_manifest_sha256": stalemate.STALEMATE_SOURCE_MANIFEST_SHA256,
                "baseline_outcomes_informed_protocol_design": True,
                "case_membership_outcome_fields_consulted": False,
                "treatment_outcomes_computed": False,
                "executable_fingerprints": {"fixture": "value"},
            }
            with patch.object(
                experiments,
                "_validate_source_landscape_manifest",
                return_value=(b"source", self.source_manifest),
            ), patch.object(
                experiments, "_require_clean_repository", return_value="a" * 40
            ), patch.object(
                experiments, "_manifest_provenance", return_value=provenance
            ):
                manifest_path = experiments.freeze_stalemate_manifest(
                    source_path, corpus, repository
                )
            manifest_bytes = manifest_path.read_bytes()
            lock = json.loads(
                (corpus / "manifest.lock.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                lock["manifest_sha256"], hashlib.sha256(manifest_bytes).hexdigest()
            )
            self.assertEqual(lock["manifest_bytes"], len(manifest_bytes))
            loaded = json.loads(manifest_bytes)
            stalemate.validate_stalemate_paired_manifest(loaded)

    def test_manifest_builder_failure_leaves_permanent_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            corpus = repository / experiments.STALEMATE_CORPUS_RELATIVE
            corpus.parent.mkdir(parents=True)
            source_path = repository / experiments.SOURCE_LANDSCAPE_MANIFEST_RELATIVE
            failing_builder = Mock(side_effect=RuntimeError("builder failed"))
            with patch.object(
                experiments,
                "_validate_source_landscape_manifest",
                return_value=(b"source", self.source_manifest),
            ), patch.object(
                experiments, "_require_clean_repository", return_value="a" * 40
            ), patch.object(
                experiments,
                "_manifest_provenance",
                return_value={"created_at": "2026-08-31T00:00:00.000000Z"},
            ):
                with self.assertRaisesRegex(RuntimeError, "builder failed"):
                    experiments.freeze_stalemate_manifest(
                        source_path,
                        corpus,
                        repository,
                        manifest_builder=failing_builder,
                    )
                self.assertTrue((corpus / "manifest-reservation.json").exists())
                self.assertTrue((corpus / "manifest-attempt.json").exists())
                failure_path = corpus / "manifest-failure.json"
                self.assertTrue(failure_path.exists())
                failure = json.loads(failure_path.read_text(encoding="utf-8"))
                self.assertEqual(failure["phase"], "MANIFEST_CONSTRUCTION")
                with self.assertRaisesRegex(ValueError, "reserved evidence"):
                    experiments.freeze_stalemate_manifest(
                        source_path,
                        corpus,
                        repository,
                        manifest_builder=failing_builder,
                    )
            self.assertEqual(failing_builder.call_count, 1)

    def test_manifest_builder_cannot_smuggle_outcome_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            corpus = repository / experiments.STALEMATE_CORPUS_RELATIVE
            corpus.parent.mkdir(parents=True)
            source_path = repository / experiments.SOURCE_LANDSCAPE_MANIFEST_RELATIVE
            provenance = {"fixture": True}

            def leaking_builder(source, source_hash, supplied_provenance):
                manifest = stalemate.build_stalemate_paired_manifest(
                    source, source_hash, supplied_provenance
                )
                manifest["provenance"]["terminal_reason"] = "NO_LEGAL_ACTION"
                return manifest

            with patch.object(
                experiments,
                "_validate_source_landscape_manifest",
                return_value=(b"source", self.source_manifest),
            ), patch.object(
                experiments, "_require_clean_repository", return_value="a" * 40
            ), patch.object(
                experiments, "_manifest_provenance", return_value=provenance
            ):
                with self.assertRaisesRegex(ValueError, "canonical construction"):
                    experiments.freeze_stalemate_manifest(
                        source_path,
                        corpus,
                        repository,
                        manifest_builder=leaking_builder,
                    )

            self.assertFalse((corpus / "manifest.json").exists())
            self.assertTrue((corpus / "manifest-failure.json").exists())

    def test_baseline_mismatch_phase_has_zero_treatment_calls(self) -> None:
        with temporary_protocol_paths() as paths:
            call_counts = {"baseline": 0, "treatment": 0}

            def case_evaluator(cases, **kwargs):
                del kwargs
                stage = (
                    "baseline"
                    if cases[0]["definition"]["schema_version"] == 1
                    else "treatment"
                )
                call_counts[stage] += 1
                return {"stage": stage}

            def paired_evaluator(manifest, baseline, case_evaluator, **kwargs):
                del baseline, kwargs
                call_stage(case_evaluator, manifest, treatment=False)
                raise ValueError("v1 baseline replay mismatch")

            with patched_raw_preflight(paths, self.manifest, self.source_raw):
                with self.assertRaisesRegex(ValueError, "v1 baseline replay mismatch"):
                    experiments.run_stalemate_paired(
                        paths["manifest"],
                        paths["lock"],
                        paths["source_raw"],
                        paths["output"],
                        paths["repository"],
                        paired_evaluator=paired_evaluator,
                        case_evaluator=case_evaluator,
                    )
            self.assertEqual(call_counts, {"baseline": 1, "treatment": 0})
            failure = load_only_failure(paths["output"])
            self.assertEqual(failure["phase"], "BASELINE_REPLAY_VALIDATION")
            self.assertTrue(
                (
                    paths["output"]
                    / ".{}.reservation.json".format(
                        experiments.STALEMATE_RAW_PROTOCOL_ID
                    )
                ).exists()
            )
            completed = [
                path
                for path in paths["output"].glob("*/run.json")
                if path.parent.name != experiments.SOURCE_LANDSCAPE_RAW_RUN_ID
            ]
            self.assertFalse(completed)

    def test_runner_validates_baseline_result_before_treatment(self) -> None:
        with temporary_protocol_paths() as paths:
            calls = {"baseline": 0, "treatment": 0}

            def case_evaluator(cases, **kwargs):
                del kwargs
                stage = (
                    "baseline"
                    if cases[0]["definition"]["schema_version"] == 1
                    else "treatment"
                )
                calls[stage] += 1
                return {"stage": stage}

            def paired_evaluator(manifest, baseline, case_evaluator, **kwargs):
                del baseline, kwargs
                call_stage(case_evaluator, manifest, treatment=False)
                call_stage(case_evaluator, manifest, treatment=True)
                raise AssertionError("unreachable")

            baseline_validator = Mock(
                side_effect=ValueError("v1 baseline replay mismatch")
            )
            with patched_raw_preflight(
                paths, self.manifest, self.source_raw
            ), patch.object(
                experiments,
                "validate_stalemate_baseline_replay",
                baseline_validator,
            ):
                with self.assertRaisesRegex(ValueError, "baseline replay mismatch"):
                    experiments.run_stalemate_paired(
                        paths["manifest"],
                        paths["lock"],
                        paths["source_raw"],
                        paths["output"],
                        paths["repository"],
                        paired_evaluator=paired_evaluator,
                        case_evaluator=case_evaluator,
                    )
            self.assertEqual(calls, {"baseline": 1, "treatment": 0})
            self.assertEqual(baseline_validator.call_count, 1)
            self.assertEqual(
                baseline_validator.call_args.args[2], self.source_raw["results"]
            )
            self.assertIsNot(
                baseline_validator.call_args.args[2], self.source_raw["results"]
            )
            self.assertEqual(
                load_only_failure(paths["output"])["phase"],
                "BASELINE_REPLAY_VALIDATION",
            )

    def test_altered_treatment_arguments_are_rejected_before_evaluation(self) -> None:
        with temporary_protocol_paths() as paths:
            calls = {"baseline": 0, "treatment": 0}

            def case_evaluator(cases, **kwargs):
                del kwargs
                stage = (
                    "baseline"
                    if cases[0]["definition"]["schema_version"] == 1
                    else "treatment"
                )
                calls[stage] += 1
                return {"stage": stage}

            def paired_evaluator(manifest, baseline, case_evaluator, **kwargs):
                del baseline, kwargs
                call_stage(case_evaluator, manifest, treatment=False)
                case_evaluator(
                    stage_cases(manifest, treatment=True),
                    play_seeds=experiments.LANDSCAPE_PLAY_SEEDS,
                    max_exact_states=experiments.LANDSCAPE_EXACT_MAX_STATES - 1,
                    gates=experiments.PlayGates(),
                    clock=lambda: 0.0,
                )
                raise AssertionError("unreachable")

            with patched_raw_preflight(paths, self.manifest, self.source_raw):
                with self.assertRaisesRegex(ValueError, "arguments differ"):
                    experiments.run_stalemate_paired(
                        paths["manifest"],
                        paths["lock"],
                        paths["source_raw"],
                        paths["output"],
                        paths["repository"],
                        paired_evaluator=paired_evaluator,
                        case_evaluator=case_evaluator,
                    )
            self.assertEqual(calls, {"baseline": 1, "treatment": 0})
            self.assertEqual(
                load_only_failure(paths["output"])["phase"],
                "TREATMENT_EVALUATION",
            )

    def test_changed_source_at_boundary_prevents_treatment_call(self) -> None:
        with temporary_protocol_paths() as paths:
            calls = {"baseline": 0, "treatment": 0}

            def case_evaluator(cases, **kwargs):
                del kwargs
                stage = (
                    "baseline"
                    if cases[0]["definition"]["schema_version"] == 1
                    else "treatment"
                )
                calls[stage] += 1
                if stage == "baseline":
                    paths["manifest"].write_bytes(b"changed")
                return {"stage": stage}

            def paired_evaluator(manifest, baseline, case_evaluator, **kwargs):
                del baseline, kwargs
                call_stage(case_evaluator, manifest, treatment=False)
                call_stage(case_evaluator, manifest, treatment=True)
                raise AssertionError("unreachable")

            with patched_raw_preflight(paths, self.manifest, self.source_raw):
                with self.assertRaisesRegex(ValueError, "manifest bytes changed"):
                    experiments.run_stalemate_paired(
                        paths["manifest"],
                        paths["lock"],
                        paths["source_raw"],
                        paths["output"],
                        paths["repository"],
                        paired_evaluator=paired_evaluator,
                        case_evaluator=case_evaluator,
                    )
            self.assertEqual(calls, {"baseline": 1, "treatment": 0})
            failure = load_only_failure(paths["output"])
            self.assertEqual(failure["phase"], "TREATMENT_EVALUATION")

    def test_case_evaluator_failure_is_recorded_in_exact_phase(self) -> None:
        with temporary_protocol_paths() as paths:
            calls = []

            def case_evaluator(cases, **kwargs):
                del kwargs
                stage = (
                    "baseline"
                    if cases[0]["definition"]["schema_version"] == 1
                    else "treatment"
                )
                calls.append(stage)
                if stage == "treatment":
                    raise RuntimeError("treatment evaluator failed")
                return {"stage": stage}

            def paired_evaluator(manifest, baseline, case_evaluator, **kwargs):
                del baseline, kwargs
                call_stage(case_evaluator, manifest, treatment=False)
                call_stage(case_evaluator, manifest, treatment=True)
                raise AssertionError("unreachable")

            with patched_raw_preflight(paths, self.manifest, self.source_raw):
                with self.assertRaisesRegex(RuntimeError, "treatment evaluator failed"):
                    experiments.run_stalemate_paired(
                        paths["manifest"],
                        paths["lock"],
                        paths["source_raw"],
                        paths["output"],
                        paths["repository"],
                        paired_evaluator=paired_evaluator,
                        case_evaluator=case_evaluator,
                    )
            self.assertEqual(calls, ["baseline", "treatment"])
            failure = load_only_failure(paths["output"])
            self.assertEqual(failure["phase"], "TREATMENT_EVALUATION")

    def test_raw_completion_uses_public_full_result_validator(self) -> None:
        with temporary_protocol_paths() as paths:
            result = {
                "aggregate": {
                    "predeclared_assessment": {
                        "exact_completion": {"status": "SUPPORTED"},
                        "clean_non_horizon": {"status": "SUPPORTED"},
                        "semantic_response": {"status": "SUPPORTED"},
                        "overall_treatment_discovery": {
                            "status": "INCONCLUSIVE"
                        },
                    }
                },
                "timing": {"v1_replay": {}, "treatment": {}},
            }

            def case_evaluator(cases, **kwargs):
                del kwargs
                return {
                    "stage": cases[0]["definition"]["schema_version"],
                }

            def paired_evaluator(manifest, baseline, case_evaluator, **kwargs):
                del baseline, kwargs
                call_stage(case_evaluator, manifest, treatment=False)
                call_stage(case_evaluator, manifest, treatment=True)
                return result

            validator = Mock(return_value=())
            with patched_raw_preflight(
                paths, self.manifest, self.source_raw
            ), patch.object(
                experiments, "validate_stalemate_paired_result", validator
            ):
                destination = experiments.run_stalemate_paired(
                    paths["manifest"],
                    paths["lock"],
                    paths["source_raw"],
                    paths["output"],
                    paths["repository"],
                    paired_evaluator=paired_evaluator,
                    case_evaluator=case_evaluator,
                )
            completed = json.loads(destination.read_text(encoding="utf-8"))
            self.assertEqual(completed["results"], result)
            self.assertEqual(validator.call_count, 1)
            args = validator.call_args.args
            self.assertIs(args[0], result)
            self.assertIs(args[1], self.manifest)
            self.assertEqual(args[2], self.source_raw["results"])
            self.assertIsNot(args[2], self.source_raw["results"])
            self.assertTrue(experiments._NARRATIVE_KEYS <= set(completed))
            self.assertEqual(
                completed["actual_result"],
                {**result["aggregate"], "timing": result["timing"]},
            )
            self.assertEqual(
                completed["decision"],
                "COMMIT_RAW_THEN_RUN_PREDECLARED_STRESS",
            )

    def test_stress_source_validation_rereads_pinned_baseline(self) -> None:
        raw_result = {"sealed": "raw"}
        pinned = {"results": {"sealed": "historical-baseline"}}
        source_loader = Mock(return_value=(b"pinned", pinned))
        validator = Mock(return_value=("validated",))
        with patch.object(
            experiments, "_validate_source_landscape_raw", source_loader
        ), patch.object(
            experiments, "validate_stalemate_paired_result", validator
        ):
            validated = experiments._validate_paired_result_against_pinned_source(
                raw_result, self.manifest, ROOT
            )
        self.assertEqual(validated, ("validated",))
        self.assertEqual(source_loader.call_count, 1)
        self.assertEqual(
            source_loader.call_args.args[0],
            ROOT / experiments.SOURCE_LANDSCAPE_RAW_RELATIVE,
        )
        self.assertIs(validator.call_args.args[0], raw_result)
        self.assertIs(validator.call_args.args[2], pinned["results"])

    def test_paired_raw_configuration_is_exact_and_path_bound(self) -> None:
        recorded_root = Path("/recorded/parity-forge")
        configuration = {
            "manifest_id": experiments.STALEMATE_MANIFEST_ID,
            "manifest_path": str(
                recorded_root / experiments.STALEMATE_MANIFEST_RELATIVE
            ),
            "manifest_sha256": hashlib.sha256(
                experiments._encoded_json(self.manifest)
            ).hexdigest(),
            "source_landscape_raw_run_id": experiments.SOURCE_LANDSCAPE_RAW_RUN_ID,
            "source_landscape_raw_path": str(
                recorded_root / experiments.SOURCE_LANDSCAPE_RAW_RELATIVE
            ),
            "source_landscape_raw_sha256": experiments.SOURCE_LANDSCAPE_RAW_SHA256,
            "play_seeds": list(experiments.LANDSCAPE_PLAY_SEEDS),
            "play_gates": experiments.asdict(experiments.PlayGates()),
            "max_exact_states": experiments.LANDSCAPE_EXACT_MAX_STATES,
            "phase_order": list(experiments._RAW_PHASE_ORDER),
        }
        experiments._validate_paired_raw_configuration(
            configuration, self.manifest
        )

        mutations = (
            ("extra", True),
            ("manifest_sha256", "0" * 64),
            ("manifest_path", "/recorded/parity-forge/wrong/manifest.json"),
            (
                "source_landscape_raw_path",
                str(Path("/other/repository") / experiments.SOURCE_LANDSCAPE_RAW_RELATIVE),
            ),
            ("phase_order", list(reversed(experiments._RAW_PHASE_ORDER))),
        )
        for key, value in mutations:
            with self.subTest(key=key):
                altered = copy.deepcopy(configuration)
                altered[key] = value
                with self.assertRaisesRegex(ValueError, "configuration|path"):
                    experiments._validate_paired_raw_configuration(
                        altered, self.manifest
                    )

    def test_paired_evaluator_cannot_reverse_baseline_and_treatment(self) -> None:
        with temporary_protocol_paths() as paths:
            underlying = Mock(side_effect=AssertionError("must not be called"))

            def reversed_evaluator(manifest, baseline, case_evaluator, **kwargs):
                del baseline, kwargs
                call_stage(case_evaluator, manifest, treatment=True)
                raise AssertionError("unreachable")

            with patched_raw_preflight(paths, self.manifest, self.source_raw):
                with self.assertRaisesRegex(ValueError, "source evaluator case"):
                    experiments.run_stalemate_paired(
                        paths["manifest"],
                        paths["lock"],
                        paths["source_raw"],
                        paths["output"],
                        paths["repository"],
                        paired_evaluator=reversed_evaluator,
                        case_evaluator=underlying,
                    )
            underlying.assert_not_called()
            failure = load_only_failure(paths["output"])
            self.assertEqual(failure["phase"], "BASELINE_REPLAY")

    def test_ply_limit_blocks_stress_before_reservation(self) -> None:
        with temporary_protocol_paths() as paths:
            raw_record = {
                "run_id": "paired-raw",
                "results": {"aggregate": {"ply_limit_result_count": 1}},
            }
            stress = Mock(side_effect=AssertionError("must not be called"))
            with patch.object(
                experiments,
                "_validate_frozen_stalemate_manifest",
                return_value=(b"manifest", self.manifest),
            ), patch.object(
                experiments,
                "_validate_paired_raw_source",
                return_value=(b"raw", raw_record),
            ):
                with self.assertRaisesRegex(ValueError, "PLY_LIMIT blocks"):
                    experiments.run_stalemate_draw_stress(
                        paths["source_raw"],
                        paths["manifest"],
                        paths["lock"],
                        paths["output"],
                        paths["repository"],
                        stress_evaluator=stress,
                    )
            stress.assert_not_called()
            self.assertFalse(
                (
                    paths["output"]
                    / ".{}.reservation.json".format(
                        experiments.STALEMATE_DRAW_STRESS_PROTOCOL_ID
                    )
                ).exists()
            )

    def test_exact_censor_blocks_stress_before_reservation(self) -> None:
        with temporary_protocol_paths() as paths:
            raw_record = {
                "run_id": "paired-raw",
                "results": {
                    "aggregate": {
                        "ply_limit_result_count": 0,
                        "exact_censored_count": 1,
                    }
                },
            }
            stress = Mock(side_effect=AssertionError("must not be called"))
            with patch.object(
                experiments,
                "_validate_frozen_stalemate_manifest",
                return_value=(b"manifest", self.manifest),
            ), patch.object(
                experiments,
                "_validate_paired_raw_source",
                return_value=(b"raw", raw_record),
            ):
                with self.assertRaisesRegex(ValueError, "state censoring blocks"):
                    experiments.run_stalemate_draw_stress(
                        paths["source_raw"],
                        paths["manifest"],
                        paths["lock"],
                        paths["output"],
                        paths["repository"],
                        stress_evaluator=stress,
                    )
            stress.assert_not_called()
            self.assertFalse(
                (
                    paths["output"]
                    / ".{}.reservation.json".format(
                        experiments.STALEMATE_DRAW_STRESS_PROTOCOL_ID
                    )
                ).exists()
            )

    def test_stress_completion_uses_public_validator_and_narrative(self) -> None:
        with temporary_protocol_paths() as paths:
            raw_result = {
                "aggregate": {
                    "ply_limit_result_count": 0,
                    "exact_censored_count": 0,
                },
                "candidates": [],
            }
            raw_record = {"run_id": "paired-raw", "results": raw_result}
            result = {
                "aggregate": {
                    "predeclared_assessment": {
                        "general_draw_stress": {"status": "SUPPORTED"},
                        "frontier_response": {"status": "NOT_SUPPORTED"},
                        "overall_treatment_discovery": {
                            "status": "NOT_SUPPORTED"
                        },
                    },
                    "next_branch": "DESIGN_DIRECT_INTERACTION_TEST",
                },
                "timing": {"total_seconds": 1.0},
            }
            validator = Mock(return_value=())
            stress = Mock(return_value=result)
            with patch.object(
                experiments,
                "_validate_frozen_stalemate_manifest",
                return_value=(b"manifest", self.manifest),
            ), patch.object(
                experiments,
                "_validate_paired_raw_source",
                return_value=(b"raw", raw_record),
            ), patch.object(
                experiments, "_require_clean_repository", return_value="a" * 40
            ), patch.object(
                experiments, "_require_same_fingerprints"
            ), patch.object(
                experiments, "_require_unchanged_bytes"
            ), patch.object(
                experiments, "validate_stalemate_stress_result", validator
            ):
                destination = experiments.run_stalemate_draw_stress(
                    paths["source_raw"],
                    paths["manifest"],
                    paths["lock"],
                    paths["output"],
                    paths["repository"],
                    stress_evaluator=stress,
                )
            completed = json.loads(destination.read_text(encoding="utf-8"))
            self.assertIs(validator.call_args.args[0], result)
            self.assertIs(validator.call_args.args[1], raw_result)
            self.assertTrue(experiments._NARRATIVE_KEYS <= set(completed))
            self.assertEqual(completed["decision"], result["aggregate"]["next_branch"])
            self.assertEqual(
                completed["actual_result"],
                {**result["aggregate"], "timing": result["timing"]},
            )

    def test_stress_failure_after_reservation_is_permanent(self) -> None:
        with temporary_protocol_paths() as paths:
            raw_record = {
                "run_id": "paired-raw",
                "results": {
                    "aggregate": {"ply_limit_result_count": 0},
                    "candidates": [],
                },
            }
            stress = Mock(side_effect=RuntimeError("stress failed"))
            with patch.object(
                experiments,
                "_validate_frozen_stalemate_manifest",
                return_value=(b"manifest", self.manifest),
            ), patch.object(
                experiments,
                "_validate_paired_raw_source",
                return_value=(b"raw", raw_record),
            ), patch.object(
                experiments, "_require_clean_repository", return_value="a" * 40
            ), patch.object(experiments, "_require_same_fingerprints"):
                with self.assertRaisesRegex(RuntimeError, "stress failed"):
                    experiments.run_stalemate_draw_stress(
                        paths["source_raw"],
                        paths["manifest"],
                        paths["lock"],
                        paths["output"],
                        paths["repository"],
                        stress_evaluator=stress,
                    )
            self.assertEqual(stress.call_count, 1)
            failure = load_only_failure(paths["output"])
            self.assertEqual(failure["phase"], "DRAW_STRESS_EVALUATION")
            self.assertTrue(
                (
                    paths["output"]
                    / ".{}.reservation.json".format(
                        experiments.STALEMATE_DRAW_STRESS_PROTOCOL_ID
                    )
                ).exists()
            )

    def test_stage_reservations_and_fingerprint_domains_are_separate(self) -> None:
        self.assertEqual(
            len(
                {
                    stalemate.STALEMATE_PROTOCOL_ID,
                    experiments.STALEMATE_RAW_PROTOCOL_ID,
                    experiments.STALEMATE_DRAW_STRESS_PROTOCOL_ID,
                }
            ),
            3,
        )
        self.assertNotIn(
            experiments._FROZEN_PROTOCOL_RELATIVES[0],
            experiments._FROZEN_EXECUTABLE_RELATIVES,
        )
        self.assertIn(
            Path("src/parity_forge/stalemate.py"),
            experiments._FROZEN_EXECUTABLE_RELATIVES,
        )
        self.assertIn(
            Path("src/parity_forge/stalemate_experiments.py"),
            experiments._FROZEN_EXECUTABLE_RELATIVES,
        )


class temporary_protocol_paths:
    def __enter__(self):
        self.temporary = tempfile.TemporaryDirectory()
        repository = Path(self.temporary.name)
        output = repository / "experiments/runs"
        output.mkdir(parents=True)
        manifest = repository / experiments.STALEMATE_MANIFEST_RELATIVE
        manifest.parent.mkdir(parents=True)
        manifest.write_bytes(b"manifest")
        lock = repository / experiments.STALEMATE_LOCK_RELATIVE
        lock.write_bytes(b"lock")
        source_raw = repository / experiments.SOURCE_LANDSCAPE_RAW_RELATIVE
        source_raw.parent.mkdir(parents=True)
        source_raw.write_text(
            json.dumps({"protocol_id": "historical-source"}) + "\n",
            encoding="utf-8",
        )
        self.paths = {
            "repository": repository,
            "output": output,
            "manifest": manifest,
            "lock": lock,
            "source_raw": source_raw,
        }
        return self.paths

    def __exit__(self, exc_type, exc_value, traceback):
        return self.temporary.__exit__(exc_type, exc_value, traceback)


def patched_raw_preflight(paths, manifest, source_raw):
    return patch.multiple(
        experiments,
        _validate_frozen_stalemate_manifest=Mock(
            return_value=(b"manifest", manifest)
        ),
        _validate_source_landscape_raw=Mock(
            return_value=(paths["source_raw"].read_bytes(), source_raw)
        ),
        _require_clean_repository=Mock(return_value="a" * 40),
        _require_same_fingerprints=Mock(return_value=None),
        validate_stalemate_baseline_replay=Mock(return_value=()),
    )


def load_only_failure(output_root: Path):
    failures = list(output_root.glob("*/failure.json"))
    if len(failures) != 1:
        raise AssertionError("expected one failure record, got {}".format(failures))
    return json.loads(failures[0].read_text(encoding="utf-8"))


def stage_cases(manifest, treatment: bool):
    prefix = "treatment" if treatment else "source"
    return [
        {
            "case_id": pair["pair_id"] if treatment else pair["source_case_id"],
            "stratum": pair["stratum"],
            "vector_count": pair["vector_count"],
            "definition_hash": pair[prefix + "_definition_hash"],
            "d4_canonical_hash": pair[prefix + "_d4_canonical_hash"],
            "definition": pair[prefix + "_definition"],
        }
        for pair in manifest["pairs"]
    ]


def call_stage(case_evaluator, manifest, treatment: bool):
    return case_evaluator(
        stage_cases(manifest, treatment),
        play_seeds=experiments.LANDSCAPE_PLAY_SEEDS,
        max_exact_states=experiments.LANDSCAPE_EXACT_MAX_STATES,
        gates=experiments.PlayGates(),
        clock=lambda: 0.0,
    )


if __name__ == "__main__":
    unittest.main()
