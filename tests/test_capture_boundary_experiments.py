import json
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import parity_forge.capture_boundary_experiments as experiments


_COMMIT = "1" * 40


@contextmanager
def temporary_boundary_paths():
    with tempfile.TemporaryDirectory() as temporary:
        repository = Path(temporary)
        output = repository / "experiments/runs"
        corpus = repository / experiments.CAPTURE_BOUNDARY_CORPUS_RELATIVE
        output.mkdir(parents=True)
        corpus.parent.mkdir(parents=True, exist_ok=True)
        chain = repository / "synthetic-chain.json"
        chain.write_text("{}\n", encoding="utf-8")
        yield {
            "repository": repository,
            "output": output,
            "corpus": corpus,
            "manifest": corpus / "manifest.json",
            "lock": corpus / "manifest.lock.json",
            "chain": chain,
        }


def synthetic_manifest():
    return {
        "manifest_id": experiments.BOUNDARY_MANIFEST_ID,
        "provenance": {"freezer_git_commit": _COMMIT},
        "pairs": [],
    }


def patch_run_preflight(paths, manifest):
    manifest_bytes = experiments._encoded_json(manifest)
    manifest_chain_hashes = experiments._chain_hashes((paths["chain"],))
    return (
        patch.object(
            experiments,
            "_validate_frozen_capture_boundary_manifest",
            return_value=(manifest_bytes, manifest, manifest_chain_hashes),
        ),
        patch.object(experiments, "_require_clean_repository", return_value=_COMMIT),
        patch.object(experiments, "_require_frozen_lineage"),
        patch.object(experiments, "_scan_prior_protocol"),
        patch.object(
            experiments,
            "_manifest_chain_paths",
            return_value=(paths["chain"],),
        ),
        patch.object(
            experiments,
            "_authenticated_frozen_worktree_hashes",
            return_value={},
        ),
        patch.object(experiments, "_frozen_source_chain_hashes", return_value={}),
        patch.object(experiments, "_require_head_unchanged"),
    )


class CaptureBoundaryExperimentRunnerTests(unittest.TestCase):
    def test_protocol_ids_and_frozen_budgets_are_distinct(self) -> None:
        self.assertEqual(
            {
                experiments.CAPTURE_BOUNDARY_MANIFEST_PROTOCOL_ID,
                experiments.CAPTURE_BOUNDARY_EXACT_PROTOCOL_ID,
                experiments.CAPTURE_BOUNDARY_DEPTH5_PROTOCOL_ID,
            },
            {
                "capture-boundary-v1-manifest-freeze",
                "capture-boundary-v1-paired-exact",
                "capture-boundary-v1-fixed-depth5",
            },
        )
        self.assertEqual(experiments.CAPTURE_BOUNDARY_PAIR_COUNT, 64)
        self.assertEqual(experiments.CAPTURE_BOUNDARY_STRUCTURAL_STATE_BOUND, 43_776)
        self.assertEqual(experiments.CAPTURE_BOUNDARY_DEPTH5_SEEDS, tuple(range(30)))
        self.assertEqual(experiments.CAPTURE_BOUNDARY_DEPTH5_DEPTH, 5)
        self.assertEqual(experiments.CAPTURE_BOUNDARY_DEPTH5_MAX_NODES, 5_000_000)

    def test_registry_is_reconstructed_from_the_historical_cutoff(self) -> None:
        repository = Path.cwd()
        records, registry = experiments._load_evaluated_registry(repository)
        self.assertEqual(len(records), 16)
        self.assertEqual(len(registry), 16)
        payload = experiments._canonical_json(list(registry))
        self.assertEqual(
            experiments._sha256(experiments._REGISTRY_DOMAIN + payload),
            experiments.CAPTURE_BOUNDARY_EVALUATED_REGISTRY_ROOT,
        )
        self.assertEqual(
            [entry["path"] for entry in registry],
            sorted(entry["path"] for entry in registry),
        )

    def test_pinned_exclusion_sources_have_exact_bytes_and_identities(self) -> None:
        records, metadata = experiments._load_pinned_exclusion_sources(Path.cwd())
        self.assertEqual(len(records), 4)
        self.assertEqual(len(metadata), 4)
        self.assertEqual(
            [item["path"] for item in metadata],
            [str(spec["path"]) for spec in experiments._PINNED_EXCLUSION_SPECS],
        )

    def test_supporting_dependencies_are_path_byte_and_identity_pinned(self) -> None:
        records, metadata = experiments._load_supporting_dependencies(Path.cwd())
        self.assertEqual(len(records), 3)
        self.assertEqual(
            metadata,
            tuple(
                {
                    "path": str(spec["path"]),
                    "sha256": spec["sha256"],
                    "identity_kind": spec["identity_kind"],
                    "identity": spec["identity"],
                }
                for spec in experiments._SUPPORTING_DEPENDENCY_SPECS
            ),
        )
        self.assertIs(records[0]["frozen"], True)
        self.assertEqual(
            records[1]["protocol_id"], "stalemate-v1-paired-manifest-freeze"
        )
        self.assertEqual(records[2]["status"], "FROZEN")

    def test_frozen_source_chain_includes_all_supporting_dependencies(self) -> None:
        hashes = experiments._frozen_source_chain_hashes(Path.cwd())
        for path in experiments._supporting_dependency_paths(Path.cwd()):
            self.assertIn(str(path.resolve()), hashes)

    def test_manifest_freezer_does_not_accept_an_injectable_raw_projector(self) -> None:
        with self.assertRaisesRegex(TypeError, "unexpected keyword"):
            experiments.freeze_capture_boundary_manifest(
                Path("unused"), Path("unused"), projector=Mock()
            )
        with self.assertRaisesRegex(TypeError, "unexpected keyword"):
            experiments.freeze_capture_boundary_manifest(
                Path("unused"), Path("unused"), manifest_builder=Mock()
            )
        with self.assertRaisesRegex(TypeError, "unexpected keyword"):
            experiments.run_capture_boundary_paired_exact(
                Path("unused"),
                Path("unused"),
                Path("unused"),
                Path("unused"),
                exact_evaluator=Mock(),
            )
        with self.assertRaisesRegex(TypeError, "unexpected keyword"):
            experiments.run_capture_boundary_fixed_depth5(
                Path("unused"),
                Path("unused"),
                Path("unused"),
                Path("unused"),
                Path("unused"),
                depth5_evaluator=Mock(),
            )

    def test_stage_lineage_requires_a_strict_descendant(self) -> None:
        with self.assertRaisesRegex(ValueError, "later descendant"):
            experiments._require_commit_precedes(
                _COMMIT, _COMMIT, Path.cwd(), "synthetic lineage"
            )

    def test_stage_rejects_a_head_move_after_reservation(self) -> None:
        completed = Mock(stdout="2" * 40 + "\n")
        with patch.object(experiments.subprocess, "run", return_value=completed):
            with self.assertRaisesRegex(ValueError, "HEAD changed"):
                experiments._require_head_unchanged(Path.cwd(), _COMMIT)

    def test_broken_failure_symlink_is_not_treated_as_absent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            failure = Path(temporary) / "failure.json"
            failure.symlink_to(Path(temporary) / "missing.json")
            with self.assertRaisesRegex(ValueError, "failure evidence"):
                experiments._require_failure_evidence_absent((failure,))

    def test_chain_hashing_rejects_leaf_symlinks_and_later_redirects(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            chain = root / "chain.json"
            backing = root / "backing.json"
            chain.write_text("{}\n", encoding="utf-8")
            backing.write_text("{}\n", encoding="utf-8")
            hashes = experiments._chain_hashes((chain,))
            chain.unlink()
            chain.symlink_to(backing)
            with self.assertRaisesRegex(ValueError, "path changed"):
                experiments._require_chain_unchanged(hashes)
            with self.assertRaisesRegex(ValueError, "cannot contain a symlink"):
                experiments._chain_hashes((chain,))

    def test_chain_guards_reject_an_internal_parent_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            relocated = repository / "relocated"
            (relocated / "nested").mkdir(parents=True)
            source = relocated / "nested/evidence.json"
            source.write_text("{}\n", encoding="utf-8")
            (repository / "logical").symlink_to(
                relocated, target_is_directory=True
            )
            logical = repository / "logical/nested/evidence.json"

            with self.assertRaisesRegex(ValueError, "internal symlink"):
                experiments._require_canonical_path(
                    logical,
                    repository,
                    Path("logical/nested/evidence.json"),
                    "synthetic evidence",
                )
            with self.assertRaisesRegex(ValueError, "internal symlink"):
                experiments._chain_hashes((logical,), anchor=repository)
            with self.assertRaisesRegex(ValueError, "internal symlink"):
                experiments._exact_byte_hashes(
                    ((logical, b"{}\n"),),
                    "synthetic evidence",
                    anchor=repository,
                )

    def test_frozen_lineage_checks_historical_plan_and_executables_at_both_commits(self) -> None:
        protocol = {str(experiments._PROTOCOL_PLAN_RELATIVE): "2" * 64}
        executables = {"src/parity_forge/capture_boundary.py": "3" * 64}
        manifest = {
            "provenance": {
                "freezer_git_commit": "1" * 40,
                "protocol_fingerprints": protocol,
                "executable_fingerprints": executables,
                "protocol_plan": {
                    "path": str(experiments._PROTOCOL_PLAN_RELATIVE),
                    "sha256": "2" * 64,
                    "git_blob_sha": "4" * 40,
                },
            }
        }
        with patch.object(
            experiments,
            "_require_commit_ancestor",
            side_effect=lambda commit, repository, label: commit,
        ) as ancestor, patch.object(
            experiments,
            "_frozen_source_fingerprints_at_commit",
            side_effect=(protocol, executables, protocol, executables),
        ) as fingerprints, patch.object(
            experiments, "_git_blob_sha", return_value="4" * 40
        ), patch.object(
            experiments, "_require_commit_precedes"
        ):
            experiments._require_frozen_lineage(
                Path("/synthetic/repository"), manifest, "5" * 40
            )
        self.assertEqual(ancestor.call_count, 2)
        self.assertEqual(fingerprints.call_count, 4)

    def test_manifest_freezer_writes_only_outcome_free_chain(self) -> None:
        with temporary_boundary_paths() as paths:
            exclusion_ledger = {"ledger_version": "synthetic", "d4_hashes": []}
            coverage_projection = {
                "coverage_version": "synthetic",
                "projected_d4_hashes": [],
            }
            projection = {
                "exclusion_ledger": exclusion_ledger,
                "coverage_projection": coverage_projection,
            }
            provenance = {
                "freezer_git_commit": _COMMIT,
                "case_membership_outcome_fields_consulted": False,
                "capture_treatment_outcomes_computed": False,
            }
            manifest = {
                "manifest_id": experiments.BOUNDARY_MANIFEST_ID,
                "provenance": provenance,
                "pairs": [],
            }
            projector = Mock(return_value=projection)
            builder = Mock(return_value=manifest)
            validator = Mock(return_value=())
            with patch.object(
                experiments, "_require_clean_repository", return_value=_COMMIT
            ), patch.object(
                experiments, "_authenticated_frozen_worktree_hashes", return_value={}
            ), patch.object(
                experiments,
                "_load_pinned_exclusion_sources",
                return_value=(({"source": "record"},), ({"label": "source"},)),
            ), patch.object(
                experiments,
                "_load_supporting_dependencies",
                return_value=(
                    ({"support": "record"},),
                    ({"path": "support"},),
                ),
            ), patch.object(
                experiments,
                "_load_evaluated_registry",
                return_value=(
                    ({"coverage": "record"},),
                    ({"path": "experiments/runs/x/run.json", "sha256": "2" * 64},),
                ),
            ), patch.object(
                experiments,
                "_load_plan0008_manifest_chain",
                return_value=({"manifest_id": "plan0008"}, ({"label": "plan0008"},)),
            ), patch.object(
                experiments, "_manifest_provenance", return_value=provenance
            ), patch.object(
                experiments, "_frozen_source_chain_hashes", return_value={}
            ), patch.object(
                experiments,
                "project_boundary_exclusion_sources",
                projector,
            ), patch.object(
                experiments, "build_capture_boundary_manifest", builder
            ), patch.object(
                experiments, "validate_capture_boundary_manifest", validator
            ), patch.object(
                experiments, "_require_head_unchanged"
            ):
                destination = experiments.freeze_capture_boundary_manifest(
                    paths["corpus"],
                    paths["repository"],
                )

            self.assertEqual(destination, paths["manifest"])
            self.assertEqual(
                sorted(path.name for path in paths["corpus"].iterdir()),
                [
                    "exclusion-ledger.json",
                    "manifest-attempt.json",
                    "manifest-reservation.json",
                    "manifest.json",
                    "manifest.lock.json",
                ],
            )
            freezer_bytes = b"".join(
                path.read_bytes() for path in paths["corpus"].iterdir()
            )
            self.assertNotIn(b'"results"', freezer_bytes)
            self.assertNotIn(b'"forced_result"', freezer_bytes)
            projector.assert_called_once()
            self.assertEqual(len(projector.call_args.args), 6)
            self.assertEqual(projector.call_args.args[2], ({"support": "record"},))
            self.assertEqual(projector.call_args.args[3], ({"path": "support"},))
            builder.assert_called_once()
            validator.assert_called_once_with(
                manifest,
                exclusion_ledger,
                coverage_projection,
                {"manifest_id": "plan0008"},
            )

    def test_manifest_lock_rejects_boolean_substitution_for_byte_count(self) -> None:
        with temporary_boundary_paths() as paths:
            started_at = "2026-08-31T00:00:00Z"
            attempt = {
                "run_id": experiments.BOUNDARY_MANIFEST_ID,
                "protocol_id": experiments.CAPTURE_BOUNDARY_MANIFEST_PROTOCOL_ID,
                "experiment_type": "capture-boundary-v1-outcome-free-paired-manifest",
                "status": "STARTED",
                "started_at": started_at,
                "git_commit": _COMMIT,
                "git_dirty": False,
                "environment": {"python": "synthetic", "platform": "synthetic"},
                "component_versions": dict(experiments._MANIFEST_COMPONENT_VERSIONS),
                "configuration": experiments._manifest_configuration(paths["corpus"]),
            }
            reservation = {
                "run_id": experiments.BOUNDARY_MANIFEST_ID,
                "protocol_id": experiments.CAPTURE_BOUNDARY_MANIFEST_PROTOCOL_ID,
                "status": "RESERVED",
                "reserved_at": started_at,
                "git_commit": _COMMIT,
            }
            ledger = {"exclusion_ledger": {}, "coverage_projection": {}}
            manifest = synthetic_manifest()
            ledger_bytes = experiments._encoded_json(ledger)
            manifest_bytes = experiments._encoded_json(manifest)
            lock = {
                "manifest_id": experiments.BOUNDARY_MANIFEST_ID,
                "protocol_id": experiments.CAPTURE_BOUNDARY_MANIFEST_PROTOCOL_ID,
                "exclusion_ledger_sha256": experiments._sha256(ledger_bytes),
                "exclusion_ledger_bytes": len(ledger_bytes),
                "manifest_sha256": experiments._sha256(manifest_bytes),
                "manifest_bytes": True,
                "freezer_git_commit": _COMMIT,
            }
            values = (reservation, attempt, ledger, manifest, lock)
            read_results = [
                (experiments._encoded_json(value), value) for value in values
            ]
            with patch.object(experiments, "_require_tracked"), patch.object(
                experiments, "_read_json_bytes", side_effect=read_results
            ), patch.object(
                experiments, "_exact_byte_hashes", return_value={}
            ):
                with self.assertRaisesRegex(ValueError, "lock does not match"):
                    experiments._validate_frozen_capture_boundary_manifest(
                        paths["manifest"], paths["lock"], paths["repository"]
                    )

    def test_manifest_chain_rejects_a_symlinked_reservation_leaf(self) -> None:
        with temporary_boundary_paths() as paths:
            target = paths["repository"] / "synthetic-reservation.json"
            target.write_text("{}\n", encoding="utf-8")
            reservation = (
                paths["repository"]
                / experiments.CAPTURE_BOUNDARY_MANIFEST_RESERVATION_RELATIVE
            )
            reservation.parent.mkdir(parents=True, exist_ok=True)
            reservation.symlink_to(target)
            with self.assertRaisesRegex(ValueError, "canonical repository path"):
                experiments._validate_frozen_capture_boundary_manifest(
                    paths["manifest"], paths["lock"], paths["repository"]
                )

    def test_manifest_builder_upstream_mutation_becomes_permanent_failure(self) -> None:
        with temporary_boundary_paths() as paths:
            projection = {
                "exclusion_ledger": {"ledger_version": "synthetic"},
                "coverage_projection": {"coverage_version": "synthetic"},
            }
            provenance = {"freezer_git_commit": _COMMIT}
            manifest = {
                "manifest_id": experiments.BOUNDARY_MANIFEST_ID,
                "provenance": provenance,
                "pairs": [],
            }

            def mutating_builder(*args):
                del args
                paths["chain"].write_text('{"mutated":true}\n', encoding="utf-8")
                return manifest

            with patch.object(
                experiments, "_require_clean_repository", return_value=_COMMIT
            ), patch.object(
                experiments, "_authenticated_frozen_worktree_hashes", return_value={}
            ), patch.object(
                experiments,
                "_load_pinned_exclusion_sources",
                return_value=(({"source": "record"},), ({"label": "source"},)),
            ), patch.object(
                experiments,
                "_load_supporting_dependencies",
                return_value=(({"support": "record"},), ({"path": "support"},)),
            ), patch.object(
                experiments,
                "_load_evaluated_registry",
                return_value=(
                    ({"coverage": "record"},),
                    ({"path": "experiments/runs/x/run.json", "sha256": "2" * 64},),
                ),
            ), patch.object(
                experiments,
                "_load_plan0008_manifest_chain",
                return_value=({"manifest_id": "plan0008"}, ({"label": "plan0008"},)),
            ), patch.object(
                experiments,
                "_frozen_source_chain_hashes",
                side_effect=lambda repository: experiments._chain_hashes(
                    (paths["chain"],)
                ),
            ), patch.object(
                experiments, "_manifest_provenance", return_value=provenance
            ), patch.object(
                experiments,
                "project_boundary_exclusion_sources",
                return_value=projection,
            ), patch.object(
                experiments, "build_capture_boundary_manifest", mutating_builder
            ), patch.object(
                experiments,
                "validate_capture_boundary_manifest",
                return_value=(),
            ):
                with self.assertRaisesRegex(ValueError, "frozen source chain changed"):
                    experiments.freeze_capture_boundary_manifest(
                        paths["corpus"],
                        paths["repository"],
                    )

            failure = paths["corpus"] / "manifest-failure.json"
            self.assertTrue(failure.exists())
            self.assertEqual(
                json.loads(failure.read_text(encoding="utf-8"))["phase"],
                "MANIFEST_CONSTRUCTION",
            )
            self.assertFalse(paths["manifest"].exists())
            self.assertFalse(paths["lock"].exists())

    def test_exact_runner_calls_one_pure_fixed_schedule_and_writes_run(self) -> None:
        with temporary_boundary_paths() as paths:
            manifest = synthetic_manifest()
            result = {
                "aggregate": {
                    "exact_censored_count": 0,
                    "exact_attempted": 128,
                },
                "timing": {
                    "source_seconds": 1.0,
                    "treatment_seconds": 2.0,
                    "total_seconds": 3.0,
                },
            }
            evaluator = Mock(return_value=result)
            validator = Mock(return_value=result)
            contexts = patch_run_preflight(paths, manifest)
            with contexts[0], contexts[1], contexts[2], contexts[3], contexts[4], contexts[5], contexts[6], contexts[7], patch.object(
                experiments, "evaluate_capture_boundary_exact", evaluator
            ), patch.object(
                experiments, "validate_capture_boundary_exact_result", validator
            ):
                destination = experiments.run_capture_boundary_paired_exact(
                    paths["manifest"],
                    paths["lock"],
                    paths["output"],
                    paths["repository"],
                )

            self.assertTrue(destination.exists())
            record = json.loads(destination.read_text(encoding="utf-8"))
            self.assertEqual(record["status"], "COMPLETED")
            self.assertEqual(
                record["configuration"]["phase_order"],
                ["SOURCE_EXACT", "SOURCE_SEAL", "TREATMENT_EXACT", "PAIRED_RESULT"],
            )
            evaluator.assert_called_once_with(
                manifest,
                expected_pair_count=64,
                max_states=100_000,
            )
            validator.assert_called_once_with(
                result,
                manifest,
                expected_pair_count=64,
                max_states=100_000,
            )

    def test_exact_initial_stage_seal_failure_is_permanent(self) -> None:
        with temporary_boundary_paths() as paths:
            manifest = synthetic_manifest()
            evaluator = Mock(side_effect=AssertionError("evaluation must not start"))
            contexts = patch_run_preflight(paths, manifest)
            with contexts[0], contexts[1], contexts[2], contexts[3], contexts[4], contexts[5], contexts[6], contexts[7], patch.object(
                experiments,
                "_exact_byte_hashes",
                side_effect=ValueError("synthetic seal failure"),
            ), patch.object(
                experiments, "evaluate_capture_boundary_exact", evaluator
            ):
                with self.assertRaisesRegex(ValueError, "seal failure"):
                    experiments.run_capture_boundary_paired_exact(
                        paths["manifest"],
                        paths["lock"],
                        paths["output"],
                        paths["repository"],
                    )
            evaluator.assert_not_called()
            failures = list(paths["output"].glob("*/failure.json"))
            self.assertEqual(len(failures), 1)
            self.assertEqual(
                json.loads(failures[0].read_text(encoding="utf-8"))["phase"],
                "EXACT_STAGE_EVIDENCE_SEAL",
            )

    def test_exact_rechecks_the_manifest_validators_original_snapshot(self) -> None:
        with temporary_boundary_paths() as paths:
            manifest = synthetic_manifest()
            manifest_bytes = experiments._encoded_json(manifest)
            authenticated = experiments._chain_hashes((paths["chain"],))

            def moving_clean(repository):
                del repository
                paths["chain"].write_text('{"changed":true}\n', encoding="utf-8")
                return _COMMIT

            with patch.object(
                experiments,
                "_validate_frozen_capture_boundary_manifest",
                return_value=(manifest_bytes, manifest, authenticated),
            ), patch.object(
                experiments, "_require_clean_repository", side_effect=moving_clean
            ), patch.object(
                experiments, "_require_frozen_lineage"
            ), patch.object(
                experiments, "_reserve_protocol"
            ) as reserve:
                with self.assertRaisesRegex(ValueError, "bytes changed"):
                    experiments.run_capture_boundary_paired_exact(
                        paths["manifest"],
                        paths["lock"],
                        paths["output"],
                        paths["repository"],
                    )
            reserve.assert_not_called()

    def test_exact_head_move_during_evaluation_is_a_permanent_failure(self) -> None:
        with temporary_boundary_paths() as paths:
            manifest = synthetic_manifest()
            result = {
                "aggregate": {"exact_censored_count": 0},
                "timing": {
                    "source_seconds": 1.0,
                    "treatment_seconds": 1.0,
                    "total_seconds": 2.0,
                },
            }
            contexts = patch_run_preflight(paths, manifest)
            with contexts[0], contexts[1], contexts[2], contexts[3], contexts[4], contexts[5], contexts[6], contexts[7], patch.object(
                experiments,
                "evaluate_capture_boundary_exact",
                return_value=result,
            ), patch.object(
                experiments,
                "validate_capture_boundary_exact_result",
                return_value=result,
            ), patch.object(
                experiments,
                "_require_head_unchanged",
                side_effect=ValueError("Git HEAD changed after reservation"),
            ):
                with self.assertRaisesRegex(ValueError, "HEAD changed"):
                    experiments.run_capture_boundary_paired_exact(
                        paths["manifest"],
                        paths["lock"],
                        paths["output"],
                        paths["repository"],
                    )
            failures = list(paths["output"].glob("*/failure.json"))
            self.assertEqual(len(failures), 1)
            self.assertEqual(
                json.loads(failures[0].read_text(encoding="utf-8"))["phase"],
                "PAIRED_EXACT_EVALUATION",
            )

    def test_exact_cannot_complete_if_manifest_failure_appears_midstage(self) -> None:
        with temporary_boundary_paths() as paths:
            manifest = synthetic_manifest()
            result = {
                "aggregate": {"exact_censored_count": 0},
                "timing": {
                    "source_seconds": 1.0,
                    "treatment_seconds": 1.0,
                    "total_seconds": 2.0,
                },
            }

            def evaluator(value, **kwargs):
                del value, kwargs
                failure = paths["corpus"] / "manifest-failure.json"
                failure.parent.mkdir(parents=True, exist_ok=True)
                failure.write_text("{}\n", encoding="utf-8")
                return result

            contexts = patch_run_preflight(paths, manifest)
            with contexts[0], contexts[1], contexts[2], contexts[3], contexts[4], contexts[5], contexts[6], contexts[7], patch.object(
                experiments, "evaluate_capture_boundary_exact", evaluator
            ), patch.object(
                experiments,
                "validate_capture_boundary_exact_result",
                return_value=result,
            ):
                with self.assertRaisesRegex(ValueError, "failure evidence"):
                    experiments.run_capture_boundary_paired_exact(
                        paths["manifest"],
                        paths["lock"],
                        paths["output"],
                        paths["repository"],
                    )
            failures = list(paths["output"].glob("*/failure.json"))
            self.assertEqual(len(failures), 1)
            self.assertEqual(
                json.loads(failures[0].read_text(encoding="utf-8"))["phase"],
                "PAIRED_EXACT_EVALUATION",
            )

    def test_exact_run_directory_collision_preserves_directory_and_writes_sidecar(self) -> None:
        with temporary_boundary_paths() as paths:
            manifest = synthetic_manifest()
            frozen_now = datetime(2026, 8, 31, tzinfo=timezone.utc)
            manifest_bytes = experiments._encoded_json(manifest)
            run_id = "{}-capture-boundary-exact-{}".format(
                frozen_now.strftime("%Y%m%dT%H%M%S%fZ"),
                experiments._sha256(manifest_bytes)[:8],
            )
            collision = paths["output"] / run_id
            collision.mkdir()
            sentinel = collision / "sentinel.txt"
            sentinel.write_text("preserve", encoding="utf-8")
            contexts = patch_run_preflight(paths, manifest)
            with contexts[0], contexts[1], contexts[2], contexts[3], contexts[4], contexts[5], contexts[6], contexts[7], patch.object(
                experiments, "_utc_now", return_value=frozen_now
            ):
                with self.assertRaises(FileExistsError):
                    experiments.run_capture_boundary_paired_exact(
                        paths["manifest"],
                        paths["lock"],
                        paths["output"],
                        paths["repository"],
                    )
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve")
            failure = paths["output"] / ".{}.failure.json".format(
                experiments.CAPTURE_BOUNDARY_EXACT_PROTOCOL_ID
            )
            self.assertTrue(failure.exists())
            self.assertEqual(
                json.loads(failure.read_text(encoding="utf-8"))["phase"],
                "EXACT_RUN_DIRECTORY_SETUP",
            )

    def test_exact_reservation_and_attempt_mutation_cannot_be_snapshotted(self) -> None:
        for target in ("reservation", "attempt"):
            with self.subTest(target=target), temporary_boundary_paths() as paths:
                manifest = synthetic_manifest()
                result = {
                    "aggregate": {"exact_censored_count": 0},
                    "timing": {
                        "source_seconds": 1.0,
                        "treatment_seconds": 1.0,
                        "total_seconds": 2.0,
                    },
                }

                def evaluator(value, **kwargs):
                    del value, kwargs
                    if target == "reservation":
                        path = paths["output"] / ".{}.reservation.json".format(
                            experiments.CAPTURE_BOUNDARY_EXACT_PROTOCOL_ID
                        )
                    else:
                        run_directories = [
                            path for path in paths["output"].iterdir() if path.is_dir()
                        ]
                        self.assertEqual(len(run_directories), 1)
                        path = run_directories[0] / "attempt.json"
                    path.write_text("{}\n", encoding="utf-8")
                    return result

                contexts = patch_run_preflight(paths, manifest)
                with contexts[0], contexts[1], contexts[2], contexts[3], contexts[4], contexts[5], contexts[6], contexts[7], patch.object(
                    experiments, "evaluate_capture_boundary_exact", evaluator
                ), patch.object(
                    experiments,
                    "validate_capture_boundary_exact_result",
                    return_value=result,
                ):
                    with self.assertRaisesRegex(ValueError, "constructed evidence"):
                        experiments.run_capture_boundary_paired_exact(
                            paths["manifest"],
                            paths["lock"],
                            paths["output"],
                            paths["repository"],
                        )
                failures = list(paths["output"].glob("*/failure.json"))
                self.assertEqual(len(failures), 1)
                self.assertEqual(
                    json.loads(failures[0].read_text(encoding="utf-8"))["phase"],
                    "PAIRED_EXACT_EVALUATION",
                )

    def test_depth_source_rejects_noncanonical_exact_reservation_or_attempt(self) -> None:
        for target in ("reservation", "attempt"):
            with self.subTest(target=target), temporary_boundary_paths() as paths:
                exact_directory = paths["output"] / "synthetic-exact"
                exact_directory.mkdir()
                attempt = {
                    "run_id": "synthetic-exact",
                    "status": "STARTED",
                    "started_at": "2026-08-31T00:00:00Z",
                    "git_commit": _COMMIT,
                }
                record = {**attempt, "status": "COMPLETED"}
                reservation = {
                    "protocol_id": experiments.CAPTURE_BOUNDARY_EXACT_PROTOCOL_ID,
                    "run_id": "synthetic-exact",
                    "status": "RESERVED",
                    "reserved_at": attempt["started_at"],
                    "git_commit": _COMMIT,
                }
                reservation_path = paths["output"] / ".{}.reservation.json".format(
                    experiments.CAPTURE_BOUNDARY_EXACT_PROTOCOL_ID
                )
                attempt_path = exact_directory / "attempt.json"
                run_path = exact_directory / "run.json"
                reservation_path.write_bytes(experiments._encoded_json(reservation))
                attempt_path.write_bytes(experiments._encoded_json(attempt))
                run_path.write_bytes(experiments._encoded_json(record))
                tampered = reservation_path if target == "reservation" else attempt_path
                tampered.write_bytes(b" " + tampered.read_bytes())
                with self.assertRaisesRegex(ValueError, "constructed evidence"):
                    experiments._require_exact_source_chain_canonical(
                        run_path, paths["output"], record, attempt
                    )

    def test_exact_censor_blocks_depth5_before_clean_check_or_reservation(self) -> None:
        with temporary_boundary_paths() as paths:
            manifest = synthetic_manifest()
            exact_record = {
                "run_id": "synthetic-exact",
                "git_commit": _COMMIT,
                "results": {"aggregate": {"exact_censored_count": 1}},
            }
            clean = Mock(side_effect=AssertionError("must stop before clean check"))
            reserve = Mock(side_effect=AssertionError("must stop before reservation"))
            with patch.object(
                experiments,
                "_validate_frozen_capture_boundary_manifest",
                return_value=(experiments._encoded_json(manifest), manifest, {}),
            ), patch.object(
                experiments,
                "_validate_capture_boundary_exact_source",
                return_value=(b"{}\n", exact_record, {}),
            ), patch.object(
                experiments, "_require_clean_repository", clean
            ), patch.object(experiments, "_reserve_protocol", reserve):
                with self.assertRaisesRegex(ValueError, "before reservation"):
                    experiments.run_capture_boundary_fixed_depth5(
                        paths["output"] / "synthetic-exact/run.json",
                        paths["manifest"],
                        paths["lock"],
                        paths["output"],
                        paths["repository"],
                    )
            clean.assert_not_called()
            reserve.assert_not_called()

    def test_orphan_protocol_failure_blocks_exact_before_new_reservation(self) -> None:
        with temporary_boundary_paths() as paths:
            manifest = synthetic_manifest()
            failure = paths["output"] / ".{}.failure.json".format(
                experiments.CAPTURE_BOUNDARY_EXACT_PROTOCOL_ID
            )
            failure.write_text("{}\n", encoding="utf-8")
            reservation = paths["output"] / ".{}.reservation.json".format(
                experiments.CAPTURE_BOUNDARY_EXACT_PROTOCOL_ID
            )
            self.assertFalse(reservation.exists())
            contexts = patch_run_preflight(paths, manifest)
            with contexts[0], contexts[1], contexts[2], contexts[3], contexts[4], contexts[5], contexts[6], contexts[7], patch.object(
                experiments, "_reserve_protocol"
            ) as reserve:
                with self.assertRaisesRegex(ValueError, "failure evidence"):
                    experiments.run_capture_boundary_paired_exact(
                        paths["manifest"],
                        paths["lock"],
                        paths["output"],
                        paths["repository"],
                    )
            reserve.assert_not_called()

    def test_orphan_protocol_failure_blocks_depth5_before_new_reservation(self) -> None:
        with temporary_boundary_paths() as paths:
            manifest = synthetic_manifest()
            exact_record = {
                "run_id": "synthetic-exact",
                "git_commit": "2" * 40,
                "results": {"aggregate": {"exact_censored_count": 0}},
            }
            failure = paths["output"] / ".{}.failure.json".format(
                experiments.CAPTURE_BOUNDARY_DEPTH5_PROTOCOL_ID
            )
            failure.write_text("{}\n", encoding="utf-8")
            reservation = paths["output"] / ".{}.reservation.json".format(
                experiments.CAPTURE_BOUNDARY_DEPTH5_PROTOCOL_ID
            )
            self.assertFalse(reservation.exists())
            with patch.object(
                experiments,
                "_validate_frozen_capture_boundary_manifest",
                return_value=(experiments._encoded_json(manifest), manifest, {}),
            ), patch.object(
                experiments,
                "_validate_capture_boundary_exact_source",
                return_value=(b"{}\n", exact_record, {}),
            ), patch.object(
                experiments, "_require_clean_repository", return_value=_COMMIT
            ), patch.object(
                experiments, "_require_frozen_lineage"
            ), patch.object(
                experiments, "_require_commit_ancestor"
            ), patch.object(
                experiments, "_require_commit_precedes"
            ), patch.object(
                experiments, "_reserve_protocol"
            ) as reserve:
                with self.assertRaisesRegex(ValueError, "failure evidence"):
                    experiments.run_capture_boundary_fixed_depth5(
                        paths["output"] / "synthetic-exact/run.json",
                        paths["manifest"],
                        paths["lock"],
                        paths["output"],
                        paths["repository"],
                    )
            reserve.assert_not_called()

    def test_depth_rechecks_the_exact_validators_original_snapshot(self) -> None:
        with temporary_boundary_paths() as paths:
            manifest = synthetic_manifest()
            exact_record = {
                "run_id": "synthetic-exact",
                "git_commit": "2" * 40,
                "results": {"aggregate": {"exact_censored_count": 0}},
            }
            authenticated = experiments._chain_hashes((paths["chain"],))

            def moving_clean(repository):
                del repository
                paths["chain"].write_text('{"changed":true}\n', encoding="utf-8")
                return _COMMIT

            with patch.object(
                experiments,
                "_validate_frozen_capture_boundary_manifest",
                return_value=(experiments._encoded_json(manifest), manifest, {}),
            ), patch.object(
                experiments,
                "_validate_capture_boundary_exact_source",
                return_value=(b"{}\n", exact_record, authenticated),
            ), patch.object(
                experiments, "_require_clean_repository", side_effect=moving_clean
            ), patch.object(
                experiments, "_require_frozen_lineage"
            ), patch.object(
                experiments, "_require_commit_ancestor"
            ), patch.object(
                experiments, "_require_commit_precedes"
            ), patch.object(
                experiments, "_reserve_protocol"
            ) as reserve:
                with self.assertRaisesRegex(ValueError, "bytes changed"):
                    experiments.run_capture_boundary_fixed_depth5(
                        paths["output"] / "synthetic-exact/run.json",
                        paths["manifest"],
                        paths["lock"],
                        paths["output"],
                        paths["repository"],
                    )
            reserve.assert_not_called()

    def test_depth_initial_stage_seal_failure_is_permanent(self) -> None:
        with temporary_boundary_paths() as paths:
            manifest = synthetic_manifest()
            exact_result = {"aggregate": {"exact_censored_count": 0}}
            exact_record = {
                "run_id": "synthetic-exact",
                "git_commit": _COMMIT,
                "results": exact_result,
            }
            evaluator = Mock(side_effect=AssertionError("evaluation must not start"))
            contexts = patch_run_preflight(paths, manifest)
            with contexts[0], contexts[1], contexts[2], contexts[3], contexts[4], contexts[5], contexts[6], contexts[7], patch.object(
                experiments,
                "_validate_capture_boundary_exact_source",
                return_value=(experiments._encoded_json(exact_record), exact_record, {}),
            ), patch.object(
                experiments, "_require_commit_ancestor"
            ), patch.object(
                experiments, "_require_commit_precedes"
            ), patch.object(
                experiments,
                "_exact_byte_hashes",
                side_effect=ValueError("synthetic depth seal failure"),
            ), patch.object(
                experiments, "evaluate_capture_boundary_depth5", evaluator
            ):
                with self.assertRaisesRegex(ValueError, "depth seal failure"):
                    experiments.run_capture_boundary_fixed_depth5(
                        paths["output"] / "synthetic-exact/run.json",
                        paths["manifest"],
                        paths["lock"],
                        paths["output"],
                        paths["repository"],
                    )
            evaluator.assert_not_called()
            failures = list(paths["output"].glob("*/failure.json"))
            self.assertEqual(len(failures), 1)
            self.assertEqual(
                json.loads(failures[0].read_text(encoding="utf-8"))["phase"],
                "DEPTH5_STAGE_EVIDENCE_SEAL",
            )

    def test_depth_cannot_complete_if_exact_failure_appears_midstage(self) -> None:
        with temporary_boundary_paths() as paths:
            manifest = synthetic_manifest()
            exact_result = {"aggregate": {"exact_censored_count": 0}}
            exact_record = {
                "run_id": "synthetic-exact",
                "git_commit": _COMMIT,
                "results": exact_result,
            }
            exact_run_path = paths["output"] / "synthetic-exact/run.json"
            result = {
                "aggregate": {
                    "assessments": {"overall": {"next_branch": "STOP"}}
                },
                "timing": {
                    "source_seconds": 1.0,
                    "treatment_seconds": 1.0,
                    "total_seconds": 2.0,
                },
            }

            def evaluator(manifest_value, exact_value, **kwargs):
                del manifest_value, exact_value, kwargs
                exact_run_path.parent.mkdir(exist_ok=True)
                (exact_run_path.parent / "failure.json").write_text(
                    "{}\n", encoding="utf-8"
                )
                return result

            contexts = patch_run_preflight(paths, manifest)
            with contexts[0], contexts[1], contexts[2], contexts[3], contexts[4], contexts[5], contexts[6], contexts[7], patch.object(
                experiments,
                "_validate_capture_boundary_exact_source",
                return_value=(experiments._encoded_json(exact_record), exact_record, {}),
            ), patch.object(
                experiments, "_require_commit_ancestor"
            ), patch.object(
                experiments, "_require_commit_precedes"
            ), patch.object(
                experiments, "evaluate_capture_boundary_depth5", evaluator
            ), patch.object(
                experiments,
                "validate_capture_boundary_depth5_result",
                return_value=result,
            ):
                with self.assertRaisesRegex(ValueError, "failure evidence"):
                    experiments.run_capture_boundary_fixed_depth5(
                        exact_run_path,
                        paths["manifest"],
                        paths["lock"],
                        paths["output"],
                        paths["repository"],
                    )
            stage_failures = [
                json.loads(path.read_text(encoding="utf-8"))
                for path in paths["output"].glob("*/failure.json")
                if path.parent.name != "synthetic-exact"
            ]
            self.assertEqual(len(stage_failures), 1)
            self.assertEqual(stage_failures[0]["phase"], "FIXED_DEPTH5_EVALUATION")

    def test_fixed_depth5_runner_passes_the_full_frozen_schedule(self) -> None:
        with temporary_boundary_paths() as paths:
            manifest = synthetic_manifest()
            exact_result = {
                "aggregate": {"exact_censored_count": 0},
                "configuration": {"max_states": 100_000},
            }
            exact_record = {
                "run_id": "synthetic-exact",
                "git_commit": _COMMIT,
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
            contexts = patch_run_preflight(paths, manifest)
            with contexts[0], contexts[1], contexts[2], contexts[3], contexts[4], contexts[5], contexts[6], contexts[7], patch.object(
                experiments,
                "_validate_capture_boundary_exact_source",
                return_value=(exact_bytes, exact_record, {}),
            ), patch.object(experiments, "_require_commit_ancestor"), patch.object(
                experiments, "_require_commit_precedes"
            ), patch.object(
                experiments, "_chain_hashes", return_value={}
            ), patch.object(
                experiments, "evaluate_capture_boundary_depth5", evaluator
            ), patch.object(
                experiments, "validate_capture_boundary_depth5_result", validator
            ):
                destination = experiments.run_capture_boundary_fixed_depth5(
                    paths["output"] / "synthetic-exact/run.json",
                    paths["manifest"],
                    paths["lock"],
                    paths["output"],
                    paths["repository"],
                )

            self.assertTrue(destination.exists())
            evaluator.assert_called_once_with(
                manifest,
                exact_result,
                expected_pair_count=64,
                seeds=tuple(range(30)),
                depth=5,
                max_nodes=5_000_000,
                gates=experiments.PlayGates(),
            )
            reservation = paths["output"] / ".{}.reservation.json".format(
                experiments.CAPTURE_BOUNDARY_DEPTH5_PROTOCOL_ID
            )
            self.assertTrue(reservation.exists())
            attempt = json.loads(
                (destination.parent / "attempt.json").read_text(encoding="utf-8")
            )
            self.assertIs(attempt["configuration"]["adaptive_eligibility"], False)
            self.assertIsNone(attempt["configuration"]["candidate_cap"])
            self.assertIs(attempt["configuration"]["replacement"], False)
            validator.assert_called_once_with(
                result,
                manifest,
                exact_result,
                expected_pair_count=64,
                seeds=tuple(range(30)),
                depth=5,
                max_nodes=5_000_000,
                gates=experiments.PlayGates(),
            )

    def test_configuration_comparison_is_type_sensitive(self) -> None:
        manifest = synthetic_manifest()
        configuration = experiments._exact_configuration(
            Path("/tmp/repository") / experiments.CAPTURE_BOUNDARY_MANIFEST_RELATIVE,
            experiments._encoded_json(manifest),
        )
        experiments._validate_exact_configuration(configuration, manifest)
        altered = dict(configuration)
        altered["pair_count"] = True
        with self.assertRaisesRegex(ValueError, "configuration mismatch"):
            experiments._validate_exact_configuration(altered, manifest)

    def test_attempt_chain_rejects_boolean_integer_substitution(self) -> None:
        record = {
            "run_id": "run",
            "protocol_id": experiments.CAPTURE_BOUNDARY_EXACT_PROTOCOL_ID,
            "experiment_type": "capture-boundary-v1-paired-exact",
            "status": "COMPLETED",
            "started_at": "2026-08-31T00:00:00Z",
            "git_commit": _COMMIT,
            "git_dirty": False,
            "environment": {"python": "synthetic", "platform": "synthetic"},
            "component_versions": {"version": 1},
            "configuration": {"pair_count": 64},
        }
        attempt = {
            **record,
            "status": "STARTED",
            "configuration": {"pair_count": True},
        }
        with self.assertRaisesRegex(ValueError, "attempt differs"):
            experiments._require_type_sensitive_attempt_match(
                attempt, record, "synthetic"
            )

    def test_noncanonical_output_fails_before_reservation(self) -> None:
        with temporary_boundary_paths() as paths:
            alternate = paths["repository"] / "alternate-runs"
            alternate.mkdir()
            with patch.object(experiments, "_reserve_protocol") as reserve:
                with self.assertRaisesRegex(ValueError, "canonical repository path"):
                    experiments.run_capture_boundary_paired_exact(
                        paths["manifest"],
                        paths["lock"],
                        alternate,
                        paths["repository"],
                    )
            reserve.assert_not_called()


if __name__ == "__main__":
    unittest.main()
