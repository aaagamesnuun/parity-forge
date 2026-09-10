import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import Mock, patch

import parity_forge.two_runner_experiments as experiments


_COMMIT = "1" * 40


def _strict_provenance(ledger_bytes=b"{}\n"):
    return {
        "freezer_git_commit": _COMMIT,
        "freezer_git_dirty": False,
        "created_at": "2026-08-31T00:00:00Z",
        "protocol_id": experiments.TWO_RUNNER_MANIFEST_PROTOCOL_ID,
        "protocol_plan": {
            "path": str(experiments._PROTOCOL_PLAN_RELATIVE),
            "sha256": "2" * 64,
            "git_blob_sha": "3" * 40,
        },
        "protocol_fingerprints": {
            str(experiments._PROTOCOL_PLAN_RELATIVE): "2" * 64,
        },
        "executable_fingerprints": {
            path: "4" * 64
            for path in experiments.TWO_RUNNER_EXECUTABLE_FINGERPRINT_PATHS
        },
        "closed_projection_bundle": {
            "path": str(experiments.TWO_RUNNER_EXCLUSION_LEDGER_RELATIVE),
            "bundle_root": experiments.TWO_RUNNER_CLOSED_PROJECTION_BUNDLE_ROOT,
            "sha256": experiments._sha256(ledger_bytes),
            "bytes": len(ledger_bytes),
        },
        "plan0009_manifest_chain": [
            dict(record)
            for record in experiments.TWO_RUNNER_PLAN0009_MANIFEST_CHAIN
        ],
        "selection_inputs": "authenticated-definition-projections-only",
        "independent_review": "PASSED",
    }


def _bundle():
    return {
        "bundle_version": 1,
        "bundle_root": experiments.TWO_RUNNER_CLOSED_PROJECTION_BUNDLE_ROOT,
        "evaluated_orbit_projection": {"projection_root": "5" * 64},
        "historical_definition_projection": {"projection_root": "6" * 64},
    }


def _manifest(provenance=None):
    return {
        "manifest_id": experiments.TWO_RUNNER_MANIFEST_ID,
        "protocol_id": experiments.TWO_RUNNER_MANIFEST_PROTOCOL_ID,
        "status": "FROZEN",
        "source": {
            "closed_projection_bundle_root": (
                experiments.TWO_RUNNER_CLOSED_PROJECTION_BUNDLE_ROOT
            ),
        },
        "provenance": provenance or _strict_provenance(),
        "pairs": [],
    }


class TemporaryPaths:
    def __enter__(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.repository = Path(self.temporary.name)
        (self.repository / "experiments/corpora").mkdir(parents=True)
        (self.repository / "experiments/runs").mkdir(parents=True)
        self.corpus = self.repository / experiments.TWO_RUNNER_CORPUS_RELATIVE
        self.manifest = self.repository / experiments.TWO_RUNNER_MANIFEST_RELATIVE
        self.lock = self.repository / experiments.TWO_RUNNER_LOCK_RELATIVE
        self.output = self.repository / "experiments/runs"
        return self

    def __exit__(self, *args):
        return self.temporary.__exit__(*args)


def _freeze_patches(paths, bundle, manifest):
    inputs = {
        "source_records": (),
        "source_metadata": (),
        "supporting_dependency_records": (),
        "supporting_dependency_metadata": (),
        "coverage_records": (),
        "coverage_registry": (),
        "plan0009_manifest": {},
        "plan0009_manifest_chain": tuple(
            dict(record)
            for record in experiments.TWO_RUNNER_PLAN0009_MANIFEST_CHAIN
        ),
        "plan0009_chain_hashes": {},
    }
    return (
        patch.object(experiments, "_require_clean_repository", return_value=_COMMIT),
        patch.object(
            experiments, "_authenticated_frozen_worktree_hashes", return_value={}
        ),
        patch.object(experiments, "_closed_projection_inputs", return_value=inputs),
        patch.object(experiments, "_closed_source_chain_hashes", return_value={}),
        patch.object(
            experiments, "build_two_runner_closed_projection_bundle", return_value=bundle
        ),
        patch.object(
            experiments,
            "validate_two_runner_closed_projection_bundle",
            return_value={
                "evaluated_orbit_projection": bundle["evaluated_orbit_projection"],
                "historical_definition_projection": bundle[
                    "historical_definition_projection"
                ],
            },
        ),
        patch.object(
            experiments,
            "_manifest_provenance",
            return_value=manifest["provenance"],
        ),
        patch.object(experiments, "build_two_runner_manifest", return_value=manifest),
        patch.object(
            experiments,
            "validate_two_runner_manifest",
            return_value=tuple({"pair_index": index} for index in range(64)),
        ),
        patch.object(experiments, "_require_head_unchanged"),
    )


def _run_patches(manifest, bundle):
    return (
        patch.object(
            experiments,
            "_validate_frozen_two_runner_manifest",
            return_value=(experiments._encoded_json(manifest), manifest, bundle, {}),
        ),
        patch.object(experiments, "_require_clean_repository", return_value=_COMMIT),
        patch.object(experiments, "_require_frozen_lineage"),
        patch.object(
            experiments, "_authenticated_frozen_worktree_hashes", return_value={}
        ),
        patch.object(experiments, "_closed_source_chain_hashes", return_value={}),
        patch.object(experiments, "_require_head_unchanged"),
    )


class TwoRunnerManifestEdgeTests(unittest.TestCase):
    def test_authenticated_hash_merge_accepts_only_matching_duplicates(self):
        digest = "a" * 64
        self.assertEqual(
            experiments._merged_chain_hashes(
                {"/evidence/shared.json": digest},
                {"/evidence/shared.json": digest},
            ),
            {"/evidence/shared.json": digest},
        )
        with self.assertRaisesRegex(ValueError, "inconsistent duplicate bytes"):
            experiments._merged_chain_hashes(
                {"/evidence/shared.json": digest},
                {"/evidence/shared.json": "b" * 64},
            )

    def test_protocol_ids_paths_and_budgets_are_frozen(self):
        self.assertEqual(
            len(
                {
                    experiments.TWO_RUNNER_MANIFEST_PROTOCOL_ID,
                    experiments.TWO_RUNNER_EXACT_PROTOCOL_ID,
                    experiments.TWO_RUNNER_DEPTH5_PROTOCOL_ID,
                }
            ),
            3,
        )
        self.assertEqual(
            experiments.TWO_RUNNER_CORPUS_RELATIVE,
            Path("experiments/corpora/two-runner-v1"),
        )
        self.assertEqual(experiments.TWO_RUNNER_EXACT_MAX_STATES, 100_000)
        self.assertEqual(experiments.TWO_RUNNER_DEPTH5_SEEDS, tuple(range(30)))
        self.assertEqual(experiments.TWO_RUNNER_DEPTH5_DEPTH, 5)
        self.assertEqual(experiments.TWO_RUNNER_DEPTH5_MAX_NODES, 5_000_000)
        self.assertEqual(
            tuple(str(path) for path in experiments._FROZEN_EXECUTABLE_RELATIVES),
            experiments.TWO_RUNNER_EXECUTABLE_FINGERPRINT_PATHS,
        )
        for transitive_import in (
            "src/parity_forge/calibration.py",
            "src/parity_forge/cascade.py",
            "src/parity_forge/capture_experiments.py",
            "src/parity_forge/heldout_audit.py",
            "src/parity_forge/stalemate.py",
            "src/parity_forge/stalemate_experiments.py",
        ):
            self.assertIn(
                transitive_import,
                experiments.TWO_RUNNER_EXECUTABLE_FINGERPRINT_PATHS,
            )

    def test_production_edges_accept_no_callable_injection(self):
        with self.assertRaisesRegex(TypeError, "unexpected keyword"):
            experiments.freeze_two_runner_manifest(
                Path("unused"), Path("unused"), manifest_builder=Mock()
            )
        with self.assertRaisesRegex(TypeError, "unexpected keyword"):
            experiments.run_two_runner_paired_exact(
                Path("unused"),
                Path("unused"),
                Path("unused"),
                Path("unused"),
                exact_evaluator=Mock(),
            )
        with self.assertRaisesRegex(TypeError, "unexpected keyword"):
            experiments.run_two_runner_fixed_depth5(
                Path("unused"),
                Path("unused"),
                Path("unused"),
                Path("unused"),
                Path("unused"),
                agent_factory=Mock(),
            )

    def test_manifest_provenance_binds_plan_code_bundle_and_chain(self):
        ledger = _bundle()
        ledger_bytes = experiments._encoded_json(ledger)
        protocol = {str(experiments._PROTOCOL_PLAN_RELATIVE): "2" * 64}
        executables = {
            str(path): "4" * 64
            for path in experiments._FROZEN_EXECUTABLE_RELATIVES
        }
        with patch.object(
            experiments,
            "_frozen_source_fingerprints_at_commit",
            side_effect=(protocol, executables),
        ), patch.object(experiments, "_git_blob_sha", return_value="3" * 40):
            provenance = experiments._manifest_provenance(
                Path("/repository"),
                _COMMIT,
                "2026-08-31T00:00:00Z",
                ledger_bytes,
                ledger,
                experiments.TWO_RUNNER_PLAN0009_MANIFEST_CHAIN,
            )
        self.assertIs(provenance["freezer_git_dirty"], False)
        self.assertEqual(
            provenance["closed_projection_bundle"],
            {
                "path": str(experiments.TWO_RUNNER_EXCLUSION_LEDGER_RELATIVE),
                "bundle_root": experiments.TWO_RUNNER_CLOSED_PROJECTION_BUNDLE_ROOT,
                "sha256": experiments._sha256(ledger_bytes),
                "bytes": len(ledger_bytes),
            },
        )
        self.assertEqual(provenance["protocol_fingerprints"], protocol)
        self.assertEqual(provenance["executable_fingerprints"], executables)

    def test_manifest_freezer_writes_only_five_outcome_free_files(self):
        with TemporaryPaths() as paths:
            bundle = _bundle()
            provenance = _strict_provenance(experiments._encoded_json(bundle))
            manifest = _manifest(provenance)
            with ExitStack() as stack:
                for context in _freeze_patches(paths, bundle, manifest):
                    stack.enter_context(context)
                destination = experiments.freeze_two_runner_manifest(
                    paths.corpus, paths.repository
                )
            self.assertEqual(destination, paths.manifest)
            self.assertEqual(
                sorted(path.name for path in paths.corpus.iterdir()),
                [
                    "exclusion-ledger.json",
                    "manifest-attempt.json",
                    "manifest-reservation.json",
                    "manifest.json",
                    "manifest.lock.json",
                ],
            )
            all_bytes = b"".join(path.read_bytes() for path in paths.corpus.iterdir())
            self.assertNotIn(b'"forced_result"', all_bytes)
            self.assertNotIn(b'"principal_variation"', all_bytes)
            lock = json.loads(paths.lock.read_text(encoding="utf-8"))
            ledger_bytes = (
                paths.repository / experiments.TWO_RUNNER_EXCLUSION_LEDGER_RELATIVE
            ).read_bytes()
            manifest_bytes = paths.manifest.read_bytes()
            self.assertEqual(lock["projection_bundle_sha256"], experiments._sha256(ledger_bytes))
            self.assertEqual(lock["projection_bundle_bytes"], len(ledger_bytes))
            self.assertEqual(lock["manifest_sha256"], experiments._sha256(manifest_bytes))
            self.assertEqual(lock["manifest_bytes"], len(manifest_bytes))

    def test_manifest_source_mutation_becomes_permanent_failure(self):
        with TemporaryPaths() as paths:
            bundle = _bundle()
            manifest = _manifest(_strict_provenance(experiments._encoded_json(bundle)))
            contexts = _freeze_patches(paths, bundle, manifest)
            with ExitStack() as stack:
                for context in contexts:
                    stack.enter_context(context)
                with patch.object(
                    experiments,
                    "_closed_source_chain_hashes",
                    side_effect=({"source": "a"}, {"source": "b"}),
                ):
                    with self.assertRaisesRegex(ValueError, "source chain changed"):
                        experiments.freeze_two_runner_manifest(
                            paths.corpus, paths.repository
                        )
            failure = paths.corpus / "manifest-failure.json"
            self.assertTrue(failure.exists())
            self.assertEqual(
                json.loads(failure.read_text(encoding="utf-8"))["phase"],
                "MANIFEST_CONSTRUCTION",
            )
            self.assertFalse(paths.manifest.exists())

    def test_manifest_final_checks_cannot_mutate_completed_chain(self):
        with TemporaryPaths() as paths:
            bundle = _bundle()
            manifest = _manifest(
                _strict_provenance(experiments._encoded_json(bundle))
            )
            head_checks = 0

            def mutate_after_completed_hash(repository, commit):
                nonlocal head_checks
                head_checks += 1
                if head_checks == 2:
                    paths.manifest.write_bytes(b"{}\n")

            with ExitStack() as stack:
                for context in _freeze_patches(paths, bundle, manifest):
                    stack.enter_context(context)
                stack.enter_context(
                    patch.object(
                        experiments,
                        "_require_head_unchanged",
                        side_effect=mutate_after_completed_hash,
                    )
                )
                with self.assertRaisesRegex(ValueError, "evidence chain bytes changed"):
                    experiments.freeze_two_runner_manifest(
                        paths.corpus, paths.repository
                    )
            self.assertTrue((paths.corpus / "manifest-failure.json").exists())

    def test_manifest_final_linearization_rechecks_upstream_chain(self):
        with TemporaryPaths() as paths:
            bundle = _bundle()
            manifest = _manifest(
                _strict_provenance(experiments._encoded_json(bundle))
            )
            source = paths.repository / "authenticated-source.json"
            source.write_bytes(b"original\n")
            snapshot = {
                str(source.resolve()): experiments._sha256(source.read_bytes())
            }
            head_checks = 0

            def mutate_after_all_earlier_checks(repository, commit):
                nonlocal head_checks
                head_checks += 1
                if head_checks == 2:
                    source.write_bytes(b"changed\n")

            with ExitStack() as stack:
                for context in _freeze_patches(paths, bundle, manifest):
                    stack.enter_context(context)
                stack.enter_context(
                    patch.object(
                        experiments,
                        "_closed_source_chain_hashes",
                        return_value=snapshot,
                    )
                )
                stack.enter_context(
                    patch.object(
                        experiments,
                        "_require_head_unchanged",
                        side_effect=mutate_after_all_earlier_checks,
                    )
                )
                with self.assertRaisesRegex(ValueError, "evidence chain bytes changed"):
                    experiments.freeze_two_runner_manifest(
                        paths.corpus, paths.repository
                    )

    def test_lock_comparison_is_type_sensitive(self):
        with TemporaryPaths() as paths:
            paths.corpus.mkdir()
            started_at = "2026-08-31T00:00:00Z"
            attempt = {
                "run_id": experiments.TWO_RUNNER_MANIFEST_ID,
                "protocol_id": experiments.TWO_RUNNER_MANIFEST_PROTOCOL_ID,
                "experiment_type": "two-runner-v1-outcome-free-paired-manifest",
                "status": "STARTED",
                "started_at": started_at,
                "git_commit": _COMMIT,
                "git_dirty": False,
                "environment": {"python": "synthetic", "platform": "synthetic"},
                "component_versions": dict(experiments._MANIFEST_COMPONENT_VERSIONS),
                "configuration": experiments._manifest_configuration(paths.corpus),
            }
            reservation = {
                "run_id": experiments.TWO_RUNNER_MANIFEST_ID,
                "protocol_id": experiments.TWO_RUNNER_MANIFEST_PROTOCOL_ID,
                "status": "RESERVED",
                "reserved_at": started_at,
                "git_commit": _COMMIT,
            }
            ledger = _bundle()
            manifest = _manifest(_strict_provenance(experiments._encoded_json(ledger)))
            ledger_bytes = experiments._encoded_json(ledger)
            manifest_bytes = experiments._encoded_json(manifest)
            lock = {
                "manifest_id": experiments.TWO_RUNNER_MANIFEST_ID,
                "protocol_id": experiments.TWO_RUNNER_MANIFEST_PROTOCOL_ID,
                "projection_bundle_root": ledger["bundle_root"],
                "projection_bundle_sha256": experiments._sha256(ledger_bytes),
                "projection_bundle_bytes": True,
                "manifest_sha256": experiments._sha256(manifest_bytes),
                "manifest_bytes": len(manifest_bytes),
                "freezer_git_commit": _COMMIT,
            }
            values = (reservation, attempt, ledger, manifest, lock)
            read_results = [
                (experiments._encoded_json(value), value) for value in values
            ]
            with patch.object(experiments, "_require_tracked"), patch.object(
                experiments, "_read_json_bytes", side_effect=read_results
            ), patch.object(experiments, "_exact_byte_hashes", return_value={}):
                with self.assertRaisesRegex(ValueError, "lock does not match"):
                    experiments._validate_frozen_two_runner_manifest(
                        paths.manifest, paths.lock, paths.repository
                    )

    def test_manifest_chain_rejects_internal_symlink(self):
        with TemporaryPaths() as paths:
            relocated = paths.repository / "relocated"
            relocated.mkdir()
            paths.corpus.parent.mkdir(parents=True, exist_ok=True)
            paths.corpus.symlink_to(relocated, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "internal symlink|canonical"):
                experiments._validate_frozen_two_runner_manifest(
                    paths.manifest, paths.lock, paths.repository
                )

    def test_manifest_validator_rechecks_its_original_source_snapshot(self):
        with TemporaryPaths() as paths:
            started_at = "2026-08-31T00:00:00Z"
            ledger = _bundle()
            ledger_bytes = experiments._encoded_json(ledger)
            provenance = _strict_provenance(ledger_bytes)
            manifest = _manifest(provenance)
            manifest_bytes = experiments._encoded_json(manifest)
            attempt = {
                "run_id": experiments.TWO_RUNNER_MANIFEST_ID,
                "protocol_id": experiments.TWO_RUNNER_MANIFEST_PROTOCOL_ID,
                "experiment_type": "two-runner-v1-outcome-free-paired-manifest",
                "status": "STARTED",
                "started_at": started_at,
                "git_commit": _COMMIT,
                "git_dirty": False,
                "environment": {"python": "synthetic", "platform": "synthetic"},
                "component_versions": dict(experiments._MANIFEST_COMPONENT_VERSIONS),
                "configuration": experiments._manifest_configuration(paths.corpus),
            }
            reservation = {
                "run_id": experiments.TWO_RUNNER_MANIFEST_ID,
                "protocol_id": experiments.TWO_RUNNER_MANIFEST_PROTOCOL_ID,
                "status": "RESERVED",
                "reserved_at": started_at,
                "git_commit": _COMMIT,
            }
            lock = {
                "manifest_id": experiments.TWO_RUNNER_MANIFEST_ID,
                "protocol_id": experiments.TWO_RUNNER_MANIFEST_PROTOCOL_ID,
                "projection_bundle_root": ledger["bundle_root"],
                "projection_bundle_sha256": experiments._sha256(ledger_bytes),
                "projection_bundle_bytes": len(ledger_bytes),
                "manifest_sha256": experiments._sha256(manifest_bytes),
                "manifest_bytes": len(manifest_bytes),
                "freezer_git_commit": _COMMIT,
            }
            values = (reservation, attempt, ledger, manifest, lock)
            inputs = {
                "source_records": (),
                "source_metadata": (),
                "supporting_dependency_records": (),
                "supporting_dependency_metadata": (),
                "coverage_records": (),
                "coverage_registry": (),
                "plan0009_manifest": {},
                "plan0009_manifest_chain": tuple(
                    dict(record)
                    for record in experiments.TWO_RUNNER_PLAN0009_MANIFEST_CHAIN
                ),
                "plan0009_chain_hashes": {},
            }
            with patch.object(experiments, "_require_tracked"), patch.object(
                experiments,
                "_read_json_bytes",
                side_effect=[
                    (experiments._encoded_json(value), value) for value in values
                ],
            ), patch.object(
                experiments, "_exact_byte_hashes", return_value={}
            ), patch.object(
                experiments, "_require_commit_ancestor", return_value=_COMMIT
            ), patch.object(
                experiments, "_closed_projection_inputs", return_value=inputs
            ), patch.object(
                experiments,
                "_closed_source_chain_hashes",
                side_effect=({"source": "before"}, {"source": "after"}),
            ), patch.object(
                experiments,
                "build_two_runner_closed_projection_bundle",
                return_value=ledger,
            ), patch.object(
                experiments,
                "validate_two_runner_closed_projection_bundle",
                return_value={
                    "evaluated_orbit_projection": ledger[
                        "evaluated_orbit_projection"
                    ],
                    "historical_definition_projection": ledger[
                        "historical_definition_projection"
                    ],
                },
            ), patch.object(
                experiments, "_manifest_provenance", return_value=provenance
            ), patch.object(
                experiments,
                "validate_two_runner_manifest",
                return_value=tuple({"pair_index": index} for index in range(64)),
            ):
                with self.assertRaisesRegex(ValueError, "source chain changed"):
                    experiments._validate_frozen_two_runner_manifest(
                        paths.manifest, paths.lock, paths.repository
                    )


class TwoRunnerRunEdgeTests(unittest.TestCase):
    def test_exact_runner_uses_one_fixed_public_schedule(self):
        with TemporaryPaths() as paths:
            bundle = _bundle()
            manifest = _manifest()
            result = {
                "aggregate": {"exact_censored_count": 0, "exact_attempted": 128},
                "timing": {
                    "source_seconds": 1.0,
                    "treatment_seconds": 2.0,
                    "total_seconds": 3.0,
                },
            }
            evaluator = Mock(return_value=result)
            validator = Mock(return_value=result)
            with ExitStack() as stack:
                for context in _run_patches(manifest, bundle):
                    stack.enter_context(context)
                stack.enter_context(
                    patch.object(
                        experiments._evaluation,
                        "evaluate_two_runner_exact",
                        evaluator,
                    )
                )
                stack.enter_context(
                    patch.object(
                        experiments._evaluation,
                        "validate_two_runner_exact_result",
                        validator,
                    )
                )
                destination = experiments.run_two_runner_paired_exact(
                    paths.manifest,
                    paths.lock,
                    paths.output,
                    paths.repository,
                )
            self.assertTrue(destination.exists())
            record = json.loads(destination.read_text(encoding="utf-8"))
            self.assertEqual(record["status"], "COMPLETED")
            self.assertEqual(
                record["configuration"]["phase_order"],
                ["SOURCE_EXACT", "SOURCE_SEAL", "TREATMENT_EXACT", "PAIRED_RESULT"],
            )
            args, kwargs = evaluator.call_args
            self.assertEqual(args, (manifest,))
            self.assertTrue(callable(kwargs["manifest_validator"]))
            self.assertEqual(kwargs["expected_pair_count"], 64)
            self.assertEqual(kwargs["max_states"], 100_000)
            self.assertNotIn("solver", kwargs)
            self.assertNotIn("clock", kwargs)
            validator.assert_called_once()

    def test_exact_stage_seal_failure_is_permanent_and_precedes_evaluation(self):
        with TemporaryPaths() as paths:
            bundle = _bundle()
            manifest = _manifest()
            evaluator = Mock(side_effect=AssertionError("must not evaluate"))
            with ExitStack() as stack:
                for context in _run_patches(manifest, bundle):
                    stack.enter_context(context)
                stack.enter_context(
                    patch.object(
                        experiments,
                        "_exact_byte_hashes",
                        side_effect=ValueError("synthetic seal failure"),
                    )
                )
                stack.enter_context(
                    patch.object(
                        experiments._evaluation,
                        "evaluate_two_runner_exact",
                        evaluator,
                    )
                )
                with self.assertRaisesRegex(ValueError, "seal failure"):
                    experiments.run_two_runner_paired_exact(
                        paths.manifest,
                        paths.lock,
                        paths.output,
                        paths.repository,
                    )
            evaluator.assert_not_called()
            failures = list(paths.output.glob("*/failure.json"))
            self.assertEqual(len(failures), 1)
            self.assertEqual(
                json.loads(failures[0].read_text(encoding="utf-8"))["phase"],
                "EXACT_STAGE_EVIDENCE_SEAL",
            )

    def test_exact_run_directory_collision_writes_protocol_failure(self):
        with TemporaryPaths() as paths:
            bundle = _bundle()
            manifest = _manifest()
            real_reserve = experiments._reserve_protocol

            def reserve_with_collision(output, protocol, run_id, commit, started):
                reservation = real_reserve(
                    output, protocol, run_id, commit, started
                )
                (output / run_id).mkdir()
                return reservation

            with ExitStack() as stack:
                for context in _run_patches(manifest, bundle):
                    stack.enter_context(context)
                stack.enter_context(
                    patch.object(
                        experiments,
                        "_reserve_protocol",
                        side_effect=reserve_with_collision,
                    )
                )
                with self.assertRaises(FileExistsError):
                    experiments.run_two_runner_paired_exact(
                        paths.manifest,
                        paths.lock,
                        paths.output,
                        paths.repository,
                    )
            sidecar = paths.output / ".{}.failure.json".format(
                experiments.TWO_RUNNER_EXACT_PROTOCOL_ID
            )
            self.assertTrue(sidecar.exists())
            failure = json.loads(sidecar.read_text(encoding="utf-8"))
            self.assertEqual(failure["phase"], "EXACT_RUN_DIRECTORY_SETUP")

    def test_orphan_exact_failure_blocks_before_reservation(self):
        with TemporaryPaths() as paths:
            bundle = _bundle()
            manifest = _manifest()
            failure = paths.output / ".{}.failure.json".format(
                experiments.TWO_RUNNER_EXACT_PROTOCOL_ID
            )
            failure.write_text("{}\n", encoding="utf-8")
            with ExitStack() as stack:
                for context in _run_patches(manifest, bundle):
                    stack.enter_context(context)
                reserve = stack.enter_context(
                    patch.object(experiments, "_reserve_protocol")
                )
                with self.assertRaisesRegex(ValueError, "failure evidence"):
                    experiments.run_two_runner_paired_exact(
                        paths.manifest,
                        paths.lock,
                        paths.output,
                        paths.repository,
                    )
            reserve.assert_not_called()

    def test_exact_rejects_source_reread_conflict_before_reservation(self):
        with TemporaryPaths() as paths:
            manifest = _manifest()
            bundle = _bundle()
            source = paths.repository / "shared-authenticated-source.json"
            source.write_bytes(b"before\n")
            absolute = str(source.resolve())
            manifest_snapshot = {
                absolute: experiments._sha256(source.read_bytes())
            }

            def changed_source_snapshot(repository):
                source.write_bytes(b"after\n")
                return {absolute: experiments._sha256(source.read_bytes())}

            evaluator = Mock(side_effect=AssertionError("must not evaluate"))
            reserve = Mock(side_effect=AssertionError("must not reserve"))
            with ExitStack() as stack:
                for context in _run_patches(manifest, bundle):
                    stack.enter_context(context)
                stack.enter_context(
                    patch.object(
                        experiments,
                        "_validate_frozen_two_runner_manifest",
                        return_value=(
                            experiments._encoded_json(manifest),
                            manifest,
                            bundle,
                            manifest_snapshot,
                        ),
                    )
                )
                stack.enter_context(
                    patch.object(
                        experiments,
                        "_closed_source_chain_hashes",
                        side_effect=changed_source_snapshot,
                    )
                )
                stack.enter_context(
                    patch.object(experiments, "_reserve_protocol", reserve)
                )
                stack.enter_context(
                    patch.object(
                        experiments._evaluation,
                        "evaluate_two_runner_exact",
                        evaluator,
                    )
                )
                with self.assertRaisesRegex(
                    ValueError, "inconsistent duplicate bytes"
                ):
                    experiments.run_two_runner_paired_exact(
                        paths.manifest,
                        paths.lock,
                        paths.output,
                        paths.repository,
                    )
            reserve.assert_not_called()
            evaluator.assert_not_called()

    def test_broken_reservation_symlink_blocks_before_reservation(self):
        with TemporaryPaths() as paths:
            reservation = paths.output / ".{}.reservation.json".format(
                experiments.TWO_RUNNER_EXACT_PROTOCOL_ID
            )
            reservation.symlink_to(paths.output / "missing-reservation-target")
            with self.assertRaisesRegex(ValueError, "symlink"):
                experiments._scan_prior_protocol(
                    paths.output, experiments.TWO_RUNNER_EXACT_PROTOCOL_ID
                )

    def test_exact_source_rejects_internal_parent_symlink(self):
        with TemporaryPaths() as paths:
            real_run = paths.output / "real-run"
            real_run.mkdir()
            alias = paths.output / "aliased-run"
            alias.symlink_to(real_run, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "internal symlink"):
                experiments._validate_two_runner_exact_source(
                    alias / "run.json",
                    paths.output,
                    paths.repository,
                    _manifest(),
                    _bundle(),
                )

    def test_exact_final_checks_cannot_mutate_completed_chain(self):
        with TemporaryPaths() as paths:
            bundle = _bundle()
            manifest = _manifest()
            result = {
                "aggregate": {"exact_censored_count": 0, "exact_attempted": 128},
                "timing": {
                    "source_seconds": 1.0,
                    "treatment_seconds": 2.0,
                    "total_seconds": 3.0,
                },
            }
            head_checks = 0

            def mutate_after_completed_hash(repository, commit):
                nonlocal head_checks
                head_checks += 1
                if head_checks == 2:
                    run_path = next(paths.output.glob("*/run.json"))
                    run_path.write_bytes(b"{}\n")

            with ExitStack() as stack:
                for context in _run_patches(manifest, bundle):
                    stack.enter_context(context)
                stack.enter_context(
                    patch.object(
                        experiments._evaluation,
                        "evaluate_two_runner_exact",
                        return_value=result,
                    )
                )
                stack.enter_context(
                    patch.object(
                        experiments._evaluation, "validate_two_runner_exact_result"
                    )
                )
                stack.enter_context(
                    patch.object(
                        experiments,
                        "_require_head_unchanged",
                        side_effect=mutate_after_completed_hash,
                    )
                )
                with self.assertRaisesRegex(ValueError, "evidence chain bytes changed"):
                    experiments.run_two_runner_paired_exact(
                        paths.manifest,
                        paths.lock,
                        paths.output,
                        paths.repository,
                    )
            failures = list(paths.output.glob("*/failure.json"))
            self.assertEqual(len(failures), 1)

    def test_exact_final_linearization_rechecks_upstream_chain(self):
        with TemporaryPaths() as paths:
            bundle = _bundle()
            manifest = _manifest()
            source = paths.repository / "authenticated-manifest-chain.json"
            source.write_bytes(b"original\n")
            upstream = {
                str(source.resolve()): experiments._sha256(source.read_bytes())
            }
            result = {
                "aggregate": {"exact_censored_count": 0, "exact_attempted": 128},
                "timing": {
                    "source_seconds": 1.0,
                    "treatment_seconds": 2.0,
                    "total_seconds": 3.0,
                },
            }
            head_checks = 0

            def mutate_after_all_earlier_checks(repository, commit):
                nonlocal head_checks
                head_checks += 1
                if head_checks == 2:
                    source.write_bytes(b"changed\n")

            with ExitStack() as stack:
                for context in _run_patches(manifest, bundle):
                    stack.enter_context(context)
                stack.enter_context(
                    patch.object(
                        experiments,
                        "_validate_frozen_two_runner_manifest",
                        return_value=(
                            experiments._encoded_json(manifest),
                            manifest,
                            bundle,
                            upstream,
                        ),
                    )
                )
                stack.enter_context(
                    patch.object(
                        experiments._evaluation,
                        "evaluate_two_runner_exact",
                        return_value=result,
                    )
                )
                stack.enter_context(
                    patch.object(
                        experiments._evaluation, "validate_two_runner_exact_result"
                    )
                )
                stack.enter_context(
                    patch.object(
                        experiments,
                        "_require_head_unchanged",
                        side_effect=mutate_after_all_earlier_checks,
                    )
                )
                with self.assertRaisesRegex(ValueError, "evidence chain bytes changed"):
                    experiments.run_two_runner_paired_exact(
                        paths.manifest,
                        paths.lock,
                        paths.output,
                        paths.repository,
                    )

    def test_exact_censor_blocks_depth_before_clean_check_and_reservation(self):
        with TemporaryPaths() as paths:
            manifest = _manifest()
            bundle = _bundle()
            exact_record = {
                "run_id": "synthetic-exact",
                "git_commit": _COMMIT,
                "results": {"aggregate": {"exact_censored_count": 1}},
            }
            clean = Mock(side_effect=AssertionError("must stop before clean"))
            reserve = Mock(side_effect=AssertionError("must stop before reserve"))
            with patch.object(
                experiments,
                "_validate_frozen_two_runner_manifest",
                return_value=(
                    experiments._encoded_json(manifest),
                    manifest,
                    bundle,
                    {},
                ),
            ), patch.object(
                experiments,
                "_validate_two_runner_exact_source",
                return_value=(b"{}\n", exact_record, {}),
            ), patch.object(
                experiments, "_require_clean_repository", clean
            ), patch.object(experiments, "_reserve_protocol", reserve):
                with self.assertRaisesRegex(ValueError, "before reservation"):
                    experiments.run_two_runner_fixed_depth5(
                        paths.output / "synthetic-exact/run.json",
                        paths.manifest,
                        paths.lock,
                        paths.output,
                        paths.repository,
                    )
            clean.assert_not_called()
            reserve.assert_not_called()

    def test_depth_rejects_source_reread_conflict_before_reservation(self):
        with TemporaryPaths() as paths:
            manifest = _manifest()
            bundle = _bundle()
            exact_record = {
                "run_id": "synthetic-exact",
                "git_commit": "2" * 40,
                "results": {"aggregate": {"exact_censored_count": 0}},
            }
            source = paths.repository / "shared-authenticated-source.json"
            source.write_bytes(b"before\n")
            absolute = str(source.resolve())
            manifest_snapshot = {
                absolute: experiments._sha256(source.read_bytes())
            }

            def changed_source_snapshot(repository):
                source.write_bytes(b"after\n")
                return {absolute: experiments._sha256(source.read_bytes())}

            evaluator = Mock(side_effect=AssertionError("must not evaluate"))
            reserve = Mock(side_effect=AssertionError("must not reserve"))
            with ExitStack() as stack:
                for context in _run_patches(manifest, bundle):
                    stack.enter_context(context)
                stack.enter_context(
                    patch.object(
                        experiments,
                        "_validate_frozen_two_runner_manifest",
                        return_value=(
                            experiments._encoded_json(manifest),
                            manifest,
                            bundle,
                            manifest_snapshot,
                        ),
                    )
                )
                stack.enter_context(
                    patch.object(
                        experiments,
                        "_validate_two_runner_exact_source",
                        return_value=(
                            experiments._encoded_json(exact_record),
                            exact_record,
                            {},
                        ),
                    )
                )
                stack.enter_context(
                    patch.object(
                        experiments,
                        "_closed_source_chain_hashes",
                        side_effect=changed_source_snapshot,
                    )
                )
                stack.enter_context(patch.object(experiments, "_require_commit_ancestor"))
                stack.enter_context(patch.object(experiments, "_require_commit_precedes"))
                stack.enter_context(
                    patch.object(experiments, "_reserve_protocol", reserve)
                )
                stack.enter_context(
                    patch.object(
                        experiments._evaluation,
                        "evaluate_two_runner_depth5",
                        evaluator,
                    )
                )
                with self.assertRaisesRegex(
                    ValueError, "inconsistent duplicate bytes"
                ):
                    experiments.run_two_runner_fixed_depth5(
                        paths.output / "synthetic-exact/run.json",
                        paths.manifest,
                        paths.lock,
                        paths.output,
                        paths.repository,
                    )
            reserve.assert_not_called()
            evaluator.assert_not_called()

    def test_depth_runner_passes_only_the_frozen_schedule(self):
        with TemporaryPaths() as paths:
            manifest = _manifest()
            bundle = _bundle()
            exact_result = {"aggregate": {"exact_censored_count": 0}}
            exact_record = {
                "run_id": "synthetic-exact",
                "git_commit": "2" * 40,
                "results": exact_result,
            }
            exact_bytes = experiments._encoded_json(exact_record)
            result = {
                "aggregate": {
                    "profile_attempted": 128,
                    "assessments": {
                        "overall": {"next_branch": "FAMILY_REASSESSMENT"}
                    },
                },
                "timing": {
                    "source_seconds": 4.0,
                    "treatment_seconds": 5.0,
                    "total_seconds": 9.0,
                },
            }
            evaluator = Mock(return_value=result)
            validator = Mock(return_value=result)
            with ExitStack() as stack:
                for context in _run_patches(manifest, bundle):
                    stack.enter_context(context)
                stack.enter_context(
                    patch.object(
                        experiments,
                        "_validate_two_runner_exact_source",
                        return_value=(exact_bytes, exact_record, {}),
                    )
                )
                stack.enter_context(patch.object(experiments, "_require_commit_ancestor"))
                stack.enter_context(patch.object(experiments, "_require_commit_precedes"))
                stack.enter_context(
                    patch.object(
                        experiments._evaluation,
                        "evaluate_two_runner_depth5",
                        evaluator,
                    )
                )
                stack.enter_context(
                    patch.object(
                        experiments._evaluation,
                        "validate_two_runner_depth5_result",
                        validator,
                    )
                )
                destination = experiments.run_two_runner_fixed_depth5(
                    paths.output / "synthetic-exact/run.json",
                    paths.manifest,
                    paths.lock,
                    paths.output,
                    paths.repository,
                )
            self.assertTrue(destination.exists())
            args, kwargs = evaluator.call_args
            self.assertEqual(args, (manifest, exact_result))
            self.assertTrue(callable(kwargs["manifest_validator"]))
            self.assertEqual(kwargs["expected_pair_count"], 64)
            self.assertEqual(kwargs["seeds"], tuple(range(30)))
            self.assertEqual(kwargs["depth"], 5)
            self.assertEqual(kwargs["max_nodes"], 5_000_000)
            self.assertEqual(kwargs["gates"], experiments.PlayGates())
            self.assertNotIn("agent_factory", kwargs)
            self.assertNotIn("clock", kwargs)
            attempt = json.loads(
                (destination.parent / "attempt.json").read_text(encoding="utf-8")
            )
            self.assertIs(attempt["configuration"]["adaptive_eligibility"], False)
            self.assertIsNone(attempt["configuration"]["candidate_cap"])
            self.assertIs(attempt["configuration"]["replacement"], False)

    def test_depth_final_checks_cannot_mutate_completed_chain(self):
        with TemporaryPaths() as paths:
            manifest = _manifest()
            bundle = _bundle()
            exact_result = {"aggregate": {"exact_censored_count": 0}}
            exact_record = {
                "run_id": "synthetic-exact",
                "git_commit": "2" * 40,
                "results": exact_result,
            }
            result = {
                "aggregate": {
                    "profile_attempted": 128,
                    "assessments": {
                        "overall": {"next_branch": "FAMILY_REASSESSMENT"}
                    },
                },
                "timing": {
                    "source_seconds": 4.0,
                    "treatment_seconds": 5.0,
                    "total_seconds": 9.0,
                },
            }
            head_checks = 0

            def mutate_after_completed_hash(repository, commit):
                nonlocal head_checks
                head_checks += 1
                if head_checks == 2:
                    run_path = next(paths.output.glob("*/run.json"))
                    run_path.write_bytes(b"{}\n")

            with ExitStack() as stack:
                for context in _run_patches(manifest, bundle):
                    stack.enter_context(context)
                stack.enter_context(
                    patch.object(
                        experiments,
                        "_validate_two_runner_exact_source",
                        return_value=(
                            experiments._encoded_json(exact_record),
                            exact_record,
                            {},
                        ),
                    )
                )
                stack.enter_context(patch.object(experiments, "_require_commit_ancestor"))
                stack.enter_context(patch.object(experiments, "_require_commit_precedes"))
                stack.enter_context(
                    patch.object(
                        experiments._evaluation,
                        "evaluate_two_runner_depth5",
                        return_value=result,
                    )
                )
                stack.enter_context(
                    patch.object(
                        experiments._evaluation, "validate_two_runner_depth5_result"
                    )
                )
                stack.enter_context(
                    patch.object(
                        experiments,
                        "_require_head_unchanged",
                        side_effect=mutate_after_completed_hash,
                    )
                )
                with self.assertRaisesRegex(ValueError, "evidence chain bytes changed"):
                    experiments.run_two_runner_fixed_depth5(
                        paths.output / "synthetic-exact/run.json",
                        paths.manifest,
                        paths.lock,
                        paths.output,
                        paths.repository,
                    )
            failures = list(paths.output.glob("*/failure.json"))
            self.assertEqual(len(failures), 1)

    def test_depth_final_linearization_rechecks_upstream_chain(self):
        with TemporaryPaths() as paths:
            manifest = _manifest()
            bundle = _bundle()
            source = paths.repository / "authenticated-manifest-chain.json"
            source.write_bytes(b"original\n")
            upstream = {
                str(source.resolve()): experiments._sha256(source.read_bytes())
            }
            exact_result = {"aggregate": {"exact_censored_count": 0}}
            exact_record = {
                "run_id": "synthetic-exact",
                "git_commit": "2" * 40,
                "results": exact_result,
            }
            result = {
                "aggregate": {
                    "profile_attempted": 128,
                    "assessments": {
                        "overall": {"next_branch": "FAMILY_REASSESSMENT"}
                    },
                },
                "timing": {
                    "source_seconds": 4.0,
                    "treatment_seconds": 5.0,
                    "total_seconds": 9.0,
                },
            }
            head_checks = 0

            def mutate_after_all_earlier_checks(repository, commit):
                nonlocal head_checks
                head_checks += 1
                if head_checks == 2:
                    source.write_bytes(b"changed\n")

            with ExitStack() as stack:
                for context in _run_patches(manifest, bundle):
                    stack.enter_context(context)
                stack.enter_context(
                    patch.object(
                        experiments,
                        "_validate_frozen_two_runner_manifest",
                        return_value=(
                            experiments._encoded_json(manifest),
                            manifest,
                            bundle,
                            upstream,
                        ),
                    )
                )
                stack.enter_context(
                    patch.object(
                        experiments,
                        "_validate_two_runner_exact_source",
                        return_value=(
                            experiments._encoded_json(exact_record),
                            exact_record,
                            {},
                        ),
                    )
                )
                stack.enter_context(patch.object(experiments, "_require_commit_ancestor"))
                stack.enter_context(patch.object(experiments, "_require_commit_precedes"))
                stack.enter_context(
                    patch.object(
                        experiments._evaluation,
                        "evaluate_two_runner_depth5",
                        return_value=result,
                    )
                )
                stack.enter_context(
                    patch.object(
                        experiments._evaluation, "validate_two_runner_depth5_result"
                    )
                )
                stack.enter_context(
                    patch.object(
                        experiments,
                        "_require_head_unchanged",
                        side_effect=mutate_after_all_earlier_checks,
                    )
                )
                with self.assertRaisesRegex(ValueError, "evidence chain bytes changed"):
                    experiments.run_two_runner_fixed_depth5(
                        paths.output / "synthetic-exact/run.json",
                        paths.manifest,
                        paths.lock,
                        paths.output,
                        paths.repository,
                    )

    def test_configuration_and_attempt_comparison_are_type_sensitive(self):
        manifest = _manifest()
        configuration = experiments._exact_configuration(
            Path("/tmp/repository") / experiments.TWO_RUNNER_MANIFEST_RELATIVE,
            experiments._encoded_json(manifest),
        )
        experiments._validate_exact_configuration(configuration, manifest)
        altered = dict(configuration)
        altered["pair_count"] = True
        with self.assertRaisesRegex(ValueError, "configuration mismatch"):
            experiments._validate_exact_configuration(altered, manifest)

        record = {key: None for key in experiments._ATTEMPT_KEYS}
        record.update({"status": "COMPLETED", "configuration": {"pair_count": 64}})
        attempt = {
            key: ("STARTED" if key == "status" else value)
            for key, value in record.items()
        }
        attempt["configuration"] = {"pair_count": True}
        with self.assertRaisesRegex(ValueError, "attempt differs"):
            experiments._require_type_sensitive_attempt_match(
                attempt, record, "synthetic"
            )


if __name__ == "__main__":
    unittest.main()
