import contextlib
import hashlib
import inspect
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from parity_forge import atlas_manifest_stage as manifest_stage
from parity_forge import atlas_evidence
from parity_forge import atlas_protocol
from parity_forge.atlas_evidence import (
    BodyRef,
    EvidenceIntegrityError,
    ImmutableEvidenceStore,
    ProductionClosure,
    build_attempt,
    build_reservation,
    canonical_json_bytes,
    domain_identity,
    extract_recovery_stage_contract,
    extract_stage_contract,
    publish_manifest_bootstrap,
)


class _Context:
    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self.value

    def __exit__(self, *_args):
        return None


class _FakeStore:
    def __init__(self, _root, *, completed=False, stored_protocol=None):
        self.completed = completed
        self.stored_protocol = stored_protocol

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def stage_lock(self, _stage_protocol_id):
        return _Context(None)

    def artifact_exists(self, _stage_protocol_id, artifact):
        return artifact == "completed" and self.completed

    def read_json(self, _stage_protocol_id, artifact):
        if artifact != "protocol" or self.stored_protocol is None:
            raise FileNotFoundError
        return self.stored_protocol


def _preflight():
    contract = SimpleNamespace(
        stage_id=manifest_stage.ATLAS_MANIFEST_STAGE_ID_V1,
        stage_protocol_id=manifest_stage.ATLAS_MANIFEST_STAGE_PROTOCOL_ID_V1,
    )
    closure = ProductionClosure(
        "a" * 64,
        {
            "source_commit": "b" * 40,
            "source_tree": "c" * 40,
        },
    )
    return manifest_stage._ManifestPreflight(
        repository=Path("/tmp/repository"),
        selection={"selection": "private"},
        protocol={"stage_sequence": []},
        contract=contract,
        contracts=(contract,),
        closures=(closure,),
        experiment_plan_bytes=b"plan",
    )


def _manifest():
    return {
        "manifest_id": manifest_stage.ATLAS_DETACHED_MANIFEST_ID_V1,
        "manifest_root": "d" * 64,
        "development_pair_count": manifest_stage.ATLAS_DEVELOPMENT_PAIR_COUNT_V1,
        "development_definition_count": (
            manifest_stage.ATLAS_DEVELOPMENT_DEFINITION_COUNT_V1
        ),
        "orientation_definition_count": (
            manifest_stage.ATLAS_DEFINITION_ORIENTATION_COUNT_V1
        ),
    }


def _complete_manifest_closure(contract, plan=b"plan"):
    records = []
    protocol_blob = None
    for path in sorted(contract.required_known_paths):
        raw = path.encode("ascii")
        blob = hashlib.sha1(raw).hexdigest()
        if path == "src/parity_forge/atlas_protocol.py":
            protocol_blob = blob
        records.append(
            {
                "byte_count": len(raw),
                "current_sha256": hashlib.sha256(raw).hexdigest(),
                "path": path,
                "source_commit_blob_sha1": blob,
            }
        )
    payload = {
        "manifest_experiment_plan_sha256": hashlib.sha256(plan).hexdigest(),
        "manifest_protocol_blob_identity": protocol_blob,
        "ordered_entrypoint_paths": [records[0]["path"]],
        "ordered_file_records": records,
        "source_commit": "b" * 40,
        "source_tree": "c" * 40,
        "stage_id": contract.stage_id,
    }
    return ProductionClosure(
        domain_identity(contract.identity_domain("production_closure_root"), payload),
        payload,
    )


@contextlib.contextmanager
def _synthetic_bootstrap_fixture(plan=b"plan"):
    provenance = atlas_protocol._execution_evidence_protocol()
    stage_ids = tuple(stage["stage_id"] for stage in provenance["stages"])
    unsigned = {
        "manifest_and_run_provenance": provenance,
        "protocol_id": atlas_protocol.ATLAS_PROTOCOL_ID_V1,
        "protocol_version": 1,
        "stage_sequence": list(stage_ids),
    }
    protocol = dict(unsigned)
    protocol["protocol_root"] = domain_identity(
        atlas_protocol._PROTOCOL_ROOT_DOMAIN_V1, unsigned
    )
    protocol_sha = hashlib.sha256(canonical_json_bytes(protocol)).hexdigest()
    with mock.patch.object(
        atlas_protocol, "ATLAS_PROTOCOL_ROOT_V1", protocol["protocol_root"]
    ), mock.patch.object(
        atlas_protocol, "ATLAS_PROTOCOL_CANONICAL_SHA256_V1", protocol_sha
    ):
        contracts = tuple(
            extract_stage_contract(protocol, stage_id) for stage_id in stage_ids
        )
        closures = tuple(
            _complete_manifest_closure(contract, plan) for contract in contracts
        )
        yield protocol, contracts, closures, plan


class AtlasManifestStageTests(unittest.TestCase):
    def test_public_entrypoints_accept_only_repository(self):
        self.assertEqual(
            tuple(inspect.signature(manifest_stage.run_atlas_manifest_stage_v1).parameters),
            ("repository",),
        )
        self.assertEqual(
            tuple(
                inspect.signature(
                    manifest_stage.recover_atlas_manifest_stage_v1
                ).parameters
            ),
            ("repository",),
        )

    def test_all_six_entrypoints_are_exact_and_independent(self):
        expected = {
            "OUTCOME_FREE_DEVELOPMENT_MANIFEST": (
                "src/parity_forge/atlas_manifest_stage.py",
            ),
            "EXACT_ALL_288": ("src/parity_forge/atlas_exact_stage.py",),
            "RANDOM_ALL_18432_GAMES": (
                "src/parity_forge/atlas_random_stage.py",
            ),
            "TERMINAL_DEPTH1_ALL_18432_GAMES": (
                "src/parity_forge/atlas_depth1_stage.py",
            ),
            "REPLAY_TELEMETRY_COMPLETE_TRACES_ONLY": (
                "src/parity_forge/atlas_telemetry_stage.py",
            ),
            "ASSESSMENT_AND_INSPECTION": (
                "src/parity_forge/atlas_assessment_stage.py",
            ),
        }
        self.assertEqual(manifest_stage.ATLAS_PRODUCTION_ENTRYPOINTS_V1, expected)
        self.assertEqual(len({path[0] for path in expected.values()}), 6)

    def test_manifest_recursive_closure_has_no_outcome_capability(self):
        repository = Path(__file__).resolve().parents[1]
        paths, _contents = atlas_evidence._closure_paths(
            repository, ("src/parity_forge/atlas_manifest_stage.py",)
        )
        forbidden = {
            "src/parity_forge/agency.py",
            "src/parity_forge/agents.py",
            "src/parity_forge/play.py",
            "src/parity_forge/solver.py",
            "src/parity_forge/terminal_search.py",
        }
        self.assertFalse(forbidden.intersection(paths))
        self.assertIn("src/parity_forge/atlas.py", paths)
        self.assertIn("src/parity_forge/atlas_history.py", paths)
        self.assertIn("src/parity_forge/atlas_stage_data.py", paths)

    def test_every_recursive_closure_satisfies_frozen_capability_policy(self):
        repository = Path(__file__).resolve().parents[1]
        for stage_id, entrypoints in (
            manifest_stage.ATLAS_PRODUCTION_ENTRYPOINTS_V1.items()
        ):
            with self.subTest(stage_id=stage_id):
                contract = extract_recovery_stage_contract(stage_id)
                paths, _contents = atlas_evidence._closure_paths(
                    repository, entrypoints
                )
                self.assertFalse(set(contract.required_known_paths) - set(paths))
                self.assertFalse(set(contract.forbidden_known_paths) & set(paths))

    def test_history_reader_uses_only_pinned_git_inventory(self):
        calls = []

        def fake_git(_repository, arguments):
            calls.append(tuple(arguments))
            if arguments[0] == "rev-parse":
                return (manifest_stage.ATLAS_HISTORY_CUTOFF_TREE_V1 + "\n").encode()
            return arguments[1].encode()

        with mock.patch.object(manifest_stage, "_run_git", side_effect=fake_git):
            result = manifest_stage._read_history_sources(Path("/repository"))
        expected_paths = tuple(
            row[0] for row in manifest_stage.ATLAS_HISTORY_INVENTORY_V1
        )
        self.assertEqual(tuple(result), expected_paths)
        self.assertEqual(len(calls), len(expected_paths) + 1)
        self.assertTrue(
            all(
                call
                == (
                    "show",
                    manifest_stage.ATLAS_HISTORY_CUTOFF_COMMIT_V1 + ":" + path,
                )
                for call, path in zip(calls[1:], expected_paths)
            )
        )

    def test_rebuild_reauthenticates_selection_and_protocol(self):
        selection = {"selection_partition_root": "partition"}
        protocol = {"protocol_id": "protocol", "protocol_root": "root"}
        selection_sha = hashlib.sha256(
            manifest_stage.canonical_json_bytes(selection)
        ).hexdigest()
        protocol_sha = hashlib.sha256(
            manifest_stage.canonical_json_bytes(protocol)
        ).hexdigest()
        with mock.patch.multiple(
            manifest_stage,
            _read_history_sources=mock.DEFAULT,
            build_prior_gameplay_exposure_projection_v1=mock.DEFAULT,
            build_synthetic_fixture_exposure_projection_v1=mock.DEFAULT,
            build_frozen_atlas_selection_snapshot_v1=mock.DEFAULT,
            validate_frozen_atlas_selection_snapshot_v1=mock.DEFAULT,
            build_frozen_atlas_protocol_v1=mock.DEFAULT,
            validate_frozen_atlas_protocol_v1=mock.DEFAULT,
            ATLAS_CANONICAL_SELECTION_SHA256_V1=selection_sha,
            ATLAS_SELECTION_PARTITION_ROOT_V1="partition",
            ATLAS_PROTOCOL_CANONICAL_SHA256_V1=protocol_sha,
            ATLAS_PROTOCOL_ID_V1="protocol",
            ATLAS_PROTOCOL_ROOT_V1="root",
        ) as patched:
            patched["_read_history_sources"].return_value = {"source": b"bytes"}
            patched[
                "build_prior_gameplay_exposure_projection_v1"
            ].return_value = {"prior": 1}
            patched[
                "build_synthetic_fixture_exposure_projection_v1"
            ].return_value = {"synthetic": 1}
            patched[
                "build_frozen_atlas_selection_snapshot_v1"
            ].return_value = selection
            patched["build_frozen_atlas_protocol_v1"].return_value = protocol
            observed = manifest_stage._rebuild_selection_and_protocol(
                Path("/repository")
            )
        self.assertEqual(observed, (selection, protocol))
        patched["validate_frozen_atlas_selection_snapshot_v1"].assert_called_once()
        patched["validate_frozen_atlas_protocol_v1"].assert_called_once()

    def test_summary_is_explicitly_outcome_and_candidate_free(self):
        value = manifest_stage._manifest_summary(_preflight(), _manifest())
        self.assertEqual(value["gameplay_outcome_count"], 0)
        self.assertEqual(value["candidate_definition_export_count"], 0)
        self.assertEqual(value["production_closure_count"], 1)
        self.assertNotIn("candidate", " ".join(value.keys()).replace(
            "candidate_definition_export_count", ""
        ))

    def test_failure_record_never_persists_exception_message(self):
        failure = manifest_stage._manifest_failure(
            ValueError("private-candidate-identity")
        )
        self.assertNotIn("private-candidate-identity", str(failure))
        self.assertEqual(failure["exception_type"], "ValueError")

    def test_run_reserves_before_detached_export_and_completes(self):
        events = []
        preflight = _preflight()
        refs = SimpleNamespace(
            as_dict=lambda: {
                "protocol": BodyRef("e" * 64, 1).as_dict(),
            }
        )

        def begin(*_args, **_kwargs):
            events.append("begin")

        def bootstrap(*_args, **_kwargs):
            events.append("publish-bootstrap")

        def build(*_args, **_kwargs):
            events.append("build-manifest")
            return _manifest()

        def publish(*_args, **_kwargs):
            events.append("publish-freeze")
            return refs

        def seal(*_args, **_kwargs):
            events.append("seal-completed")
            return {"identity": "f" * 64}

        def reseal(_preflight):
            events.append("reseal-all")

        with mock.patch.multiple(
            manifest_stage,
            _manifest_preflight=mock.Mock(return_value=preflight),
            ImmutableEvidenceStore=mock.Mock(side_effect=_FakeStore),
            publish_manifest_bootstrap=mock.Mock(side_effect=bootstrap),
            begin_stage=mock.Mock(side_effect=begin),
            build_detached_atlas_development_manifest_v1=mock.Mock(
                side_effect=build
            ),
            validate_detached_atlas_development_manifest_v1=mock.Mock(
                side_effect=lambda value, _protocol: value
            ),
            publish_manifest_freeze=mock.Mock(side_effect=publish),
            _reseal_all_production_closures=mock.Mock(side_effect=reseal),
            seal_completed_stage=mock.Mock(side_effect=seal),
        ):
            result = manifest_stage.run_atlas_manifest_stage_v1("/repository")
        self.assertEqual(
            events,
            [
                "publish-bootstrap",
                "begin",
                "build-manifest",
                "publish-freeze",
                "reseal-all",
                "seal-completed",
            ],
        )
        self.assertEqual(result["lifecycle"], "COMPLETED")

    def test_post_attempt_failure_is_permanently_sealed(self):
        preflight = _preflight()
        failed = mock.Mock(return_value={"identity": "f" * 64})
        with mock.patch.multiple(
            manifest_stage,
            _manifest_preflight=mock.Mock(return_value=preflight),
            ImmutableEvidenceStore=mock.Mock(side_effect=_FakeStore),
            publish_manifest_bootstrap=mock.Mock(),
            begin_stage=mock.Mock(),
            build_detached_atlas_development_manifest_v1=mock.Mock(
                side_effect=ValueError("private")
            ),
            seal_failed_stage=failed,
        ):
            result = manifest_stage.run_atlas_manifest_stage_v1("/repository")
        self.assertEqual(result["lifecycle"], "FAILED")
        failure = failed.call_args.args[2]
        self.assertNotIn("private", str(failure))

    def test_completed_publication_window_is_left_for_recovery(self):
        preflight = _preflight()
        failed = mock.Mock()

        class CompletedStore(_FakeStore):
            def __init__(self, root):
                super().__init__(root, completed=True)

        with mock.patch.multiple(
            manifest_stage,
            _manifest_preflight=mock.Mock(return_value=preflight),
            ImmutableEvidenceStore=mock.Mock(side_effect=CompletedStore),
            publish_manifest_bootstrap=mock.Mock(),
            begin_stage=mock.Mock(),
            build_detached_atlas_development_manifest_v1=mock.Mock(
                return_value=_manifest()
            ),
            validate_detached_atlas_development_manifest_v1=mock.Mock(
                side_effect=lambda value, _protocol: value
            ),
            publish_manifest_freeze=mock.Mock(return_value=SimpleNamespace()),
            _reseal_all_production_closures=mock.Mock(),
            seal_completed_stage=mock.Mock(side_effect=OSError("crash")),
            seal_failed_stage=failed,
        ):
            with self.assertRaises(OSError):
                manifest_stage.run_atlas_manifest_stage_v1("/repository")
        failed.assert_not_called()

    def test_recovery_uses_candidate_neutral_contract_without_selector_rebuild(self):
        contract = SimpleNamespace(
            stage_protocol_id=manifest_stage.ATLAS_MANIFEST_STAGE_PROTOCOL_ID_V1
        )
        recovery = SimpleNamespace(
            action="ALREADY_TERMINAL",
            lifecycle="COMPLETED",
            terminal_identity="a" * 64,
        )

        rebuild = mock.Mock()
        with mock.patch.multiple(
            manifest_stage,
            _exact_repository=mock.Mock(return_value=Path("/repository")),
            ImmutableEvidenceStore=mock.Mock(side_effect=_FakeStore),
            extract_recovery_stage_contract=mock.Mock(return_value=contract),
            recover_stage=mock.Mock(return_value=recovery),
            _rebuild_selection_and_protocol=rebuild,
        ):
            result = manifest_stage.recover_atlas_manifest_stage_v1("/repository")
        self.assertEqual(result["lifecycle"], "COMPLETED")
        rebuild.assert_not_called()

    def test_real_store_attempt_without_bootstrap_fails_closed(self):
        contract = extract_recovery_stage_contract(
            manifest_stage.ATLAS_MANIFEST_STAGE_ID_V1
        )
        plan = b"plan"
        closure = _complete_manifest_closure(contract, plan)
        reservation = build_reservation(contract, closure, ())
        attempt = build_attempt(contract, reservation)
        with tempfile.TemporaryDirectory() as directory:
            evidence_root = Path(directory) / "evidence"
            with ImmutableEvidenceStore(evidence_root) as store:
                with store.stage_lock(contract.stage_protocol_id):
                    store.publish_json(
                        contract.stage_protocol_id, "reservation", reservation
                    )
                    store.publish_bytes(
                        contract.stage_protocol_id, "experiment_plan", plan
                    )
                    store.publish_json(
                        contract.stage_protocol_id, "attempt", attempt
                    )
            rebuild = mock.Mock(side_effect=AssertionError("selector called"))
            with mock.patch.multiple(
                manifest_stage,
                _exact_repository=mock.Mock(return_value=Path("/repository")),
                _EVIDENCE_ROOT_RELATIVE_V1=str(evidence_root),
                _rebuild_selection_and_protocol=rebuild,
            ):
                with self.assertRaises(EvidenceIntegrityError):
                    manifest_stage.recover_atlas_manifest_stage_v1(
                        "/repository"
                    )
            rebuild.assert_not_called()
            contradiction = (
                evidence_root
                / "contradictions"
                / (contract.stage_protocol_id + ".json")
            )
            self.assertTrue(contradiction.is_file())

    def test_real_store_bootstrap_recovers_without_selector_or_git_plan_read(self):
        with _synthetic_bootstrap_fixture() as (
            protocol,
            contracts,
            closures,
            plan,
        ), tempfile.TemporaryDirectory() as directory:
            contract = contracts[0]
            reservation = build_reservation(contract, closures[0], ())
            attempt = build_attempt(contract, reservation)
            evidence_root = Path(directory) / "evidence"
            with ImmutableEvidenceStore(evidence_root) as store:
                with store.stage_lock(contract.stage_protocol_id):
                    publish_manifest_bootstrap(
                        store, contract, protocol, closures, plan
                    )
                    store.publish_json(
                        contract.stage_protocol_id, "reservation", reservation
                    )
                    store.publish_json(
                        contract.stage_protocol_id, "attempt", attempt
                    )
            rebuild = mock.Mock(side_effect=AssertionError("selector called"))
            git = mock.Mock(side_effect=AssertionError("Git plan read"))
            with mock.patch.multiple(
                manifest_stage,
                _exact_repository=mock.Mock(return_value=Path("/repository")),
                _EVIDENCE_ROOT_RELATIVE_V1=str(evidence_root),
                extract_recovery_stage_contract=mock.Mock(return_value=contract),
                _rebuild_selection_and_protocol=rebuild,
            ), mock.patch.object(atlas_evidence, "_run_git", git):
                result = manifest_stage.recover_atlas_manifest_stage_v1(
                    "/repository"
                )
            self.assertEqual(result["action"], "SEALED_NEW_ORPHANED")
            self.assertEqual(result["lifecycle"], "ORPHANED")
            rebuild.assert_not_called()
            git.assert_not_called()
            with ImmutableEvidenceStore(evidence_root) as store:
                self.assertEqual(
                    store.read_bytes(contract.stage_protocol_id, "experiment_plan"),
                    plan,
                )
                self.assertTrue(
                    store.artifact_exists(contract.stage_protocol_id, "terminal_seal")
                )

    def test_real_store_corrupt_bootstrap_fails_closed(self):
        with _synthetic_bootstrap_fixture() as (
            protocol,
            contracts,
            closures,
            plan,
        ), tempfile.TemporaryDirectory() as directory:
            contract = contracts[0]
            reservation = build_reservation(contract, closures[0], ())
            attempt = build_attempt(contract, reservation)
            evidence_root = Path(directory) / "evidence"
            with ImmutableEvidenceStore(evidence_root) as store:
                with store.stage_lock(contract.stage_protocol_id):
                    publish_manifest_bootstrap(
                        store, contract, protocol, closures, plan
                    )
                    store.publish_json(
                        contract.stage_protocol_id, "reservation", reservation
                    )
                    store.publish_json(
                        contract.stage_protocol_id, "attempt", attempt
                    )
            (
                evidence_root / "manifest-bootstrap" / "protocol.json"
            ).chmod(0o600)
            (
                evidence_root / "manifest-bootstrap" / "protocol.json"
            ).write_bytes(canonical_json_bytes({"corrupt": True}))
            rebuild = mock.Mock(side_effect=AssertionError("selector called"))
            with mock.patch.multiple(
                manifest_stage,
                _exact_repository=mock.Mock(return_value=Path("/repository")),
                _EVIDENCE_ROOT_RELATIVE_V1=str(evidence_root),
                extract_recovery_stage_contract=mock.Mock(return_value=contract),
                _rebuild_selection_and_protocol=rebuild,
            ):
                with self.assertRaises(EvidenceIntegrityError):
                    manifest_stage.recover_atlas_manifest_stage_v1("/repository")
            rebuild.assert_not_called()
            contradiction = (
                evidence_root
                / "contradictions"
                / (contract.stage_protocol_id + ".json")
            )
            self.assertTrue(contradiction.is_file())

    def test_real_store_corrupt_published_protocol_fails_closed(self):
        with _synthetic_bootstrap_fixture() as (
            protocol,
            contracts,
            closures,
            plan,
        ), tempfile.TemporaryDirectory() as directory:
            contract = contracts[0]
            reservation = build_reservation(contract, closures[0], ())
            attempt = build_attempt(contract, reservation)
            evidence_root = Path(directory) / "evidence"
            with ImmutableEvidenceStore(evidence_root) as store:
                with store.stage_lock(contract.stage_protocol_id):
                    publish_manifest_bootstrap(
                        store, contract, protocol, closures, plan
                    )
                    store.publish_json(
                        contract.stage_protocol_id, "reservation", reservation
                    )
                    store.publish_bytes(
                        contract.stage_protocol_id, "experiment_plan", plan
                    )
                    store.publish_json(
                        contract.stage_protocol_id, "attempt", attempt
                    )
                    store.publish_json(
                        contract.stage_protocol_id,
                        "protocol",
                        {"canonical_but": "not-the-frozen-protocol"},
                    )
            with mock.patch.multiple(
                manifest_stage,
                _exact_repository=mock.Mock(return_value=Path("/repository")),
                _EVIDENCE_ROOT_RELATIVE_V1=str(evidence_root),
                extract_recovery_stage_contract=mock.Mock(return_value=contract),
            ):
                with self.assertRaises(EvidenceIntegrityError):
                    manifest_stage.recover_atlas_manifest_stage_v1("/repository")
            contradiction = (
                evidence_root
                / "contradictions"
                / (contract.stage_protocol_id + ".json")
            )
            self.assertTrue(contradiction.is_file())

    def test_completion_reseals_every_stage_closure(self):
        stage_ids = tuple(manifest_stage.ATLAS_PRODUCTION_ENTRYPOINTS_V1)
        contracts = tuple(
            SimpleNamespace(stage_id=stage_id) for stage_id in stage_ids
        )
        closures = tuple(
            ProductionClosure(
                str(index) * 64,
                {
                    "stage_id": stage_id,
                    "source_commit": "b" * 40,
                    "source_tree": "c" * 40,
                },
            )
            for index, stage_id in enumerate(stage_ids, start=1)
        )
        preflight = manifest_stage._ManifestPreflight(
            repository=Path("/repository"),
            selection={},
            protocol={},
            contract=contracts[0],
            contracts=contracts,
            closures=closures,
            experiment_plan_bytes=b"plan",
        )
        reseal = mock.Mock()
        with mock.patch.object(
            manifest_stage, "reseal_production_closure", reseal
        ):
            manifest_stage._reseal_all_production_closures(preflight)
        self.assertEqual(reseal.call_count, 6)
        self.assertEqual(
            tuple(call.args[1].stage_id for call in reseal.call_args_list), stage_ids
        )

    def test_cli_exposes_no_scientific_parameter(self):
        parsed = manifest_stage._build_parser().parse_args(
            ("run", "--repository", "/repository")
        )
        self.assertEqual(vars(parsed), {"command": "run", "repository": "/repository"})


if __name__ == "__main__":
    unittest.main()
