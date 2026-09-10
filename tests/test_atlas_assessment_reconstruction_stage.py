from __future__ import annotations

import ast
import contextlib
import copy
import hashlib
import inspect
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from parity_forge import atlas_assessment_reconstruction_evidence as evidence
from parity_forge import atlas_assessment_reconstruction_protocol as protocol
import parity_forge.atlas_assessment_reconstruction_stage as stage
from parity_forge.atlas_evidence import (
    EvidenceIntegrityError,
    canonical_json_bytes,
    capture_clean_head,
    domain_identity,
)


def _body_ref(raw):
    return {"byte_count": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def _fixture():
    protocol_value = protocol.build_plan0014_assessment_reconstruction_protocol_v1()
    plan = b"# synthetic Plan 0014\n"
    repair = protocol_value["source_chain"]["repair_checkpoint"]
    closure_payload = {
        "active_plan_ref": _body_ref(plan),
        "ordered_entrypoint_paths": [
            "src/parity_forge/atlas_assessment_reconstruction_stage.py"
        ],
        "ordered_file_records": [
            {
                "byte_count": 1,
                "git_blob_sha1": "1" * 40,
                "path": "src/parity_forge/atlas_assessment_reconstruction_stage.py",
                "sha256": hashlib.sha256(b"x").hexdigest(),
            }
        ],
        "protocol_module_blob_identity": "2" * 40,
        "repair_checkpoint_commit": repair["commit"],
        "repair_checkpoint_tree": repair["tree"],
        "source_commit": "3" * 40,
        "source_tree": "4" * 40,
        "stage_id": protocol.PLAN0014_RECONSTRUCTION_STAGE_ID_V1,
    }
    closure = {
        "artifact_type": "PLAN0014_RECONSTRUCTION_PRODUCTION_CLOSURE_V1",
        "identity": domain_identity(
            protocol.identity_domain_v1("production_closure_root"),
            closure_payload,
        ),
        "payload": closure_payload,
    }
    binding_payload = {
        "archive": {"fixture": True},
        "archive_live_inventory": {"fixture": True},
        "bootstrap": {"fixture": True},
        "evidence_store_relative_path": "synthetic-v2",
        "failed_assessment": {"fixture": True},
        "ordered_stage_terminals": [],
        "repair_checkpoint": {"fixture": True},
        "source_binding_id": "synthetic-source-binding-v1",
        "source_binding_version": 1,
    }
    binding = {
        "artifact_type": "PLAN0014_RECONSTRUCTION_SOURCE_BINDING_V1",
        "identity": domain_identity(
            protocol.identity_domain_v1("source_binding_root"), binding_payload
        ),
        "payload": binding_payload,
    }
    result = {
        "inner_report": {
            "claim_level": "FAMILY_FRONTIER_SIGNAL_NOT_FAIR_GAME",
            "report_root": "5" * 64,
            "status": "FORMAL_COMPLETE",
        },
        "outer_attestation": {
            "attestation_root": "6" * 64,
            "claim_level": (
                "POST_FAILURE_CALCULATION_ONLY_NO_FAIRNESS_STRATEGY_FUN_OR_"
                "CONFIRMATION_CLAIM"
            ),
        },
    }
    bootstrap = evidence.build_bootstrap_v1(
        protocol_value, plan, closure, binding
    )
    return {
        "binding": binding,
        "bootstrap": bootstrap,
        "closure": closure,
        "plan": plan,
        "protocol": protocol_value,
        "result": result,
    }


@contextlib.contextmanager
def _fixed_inputs(
    repository,
    fixture,
    *,
    events=None,
    reconstruction_error=None,
    forbid_current_source=False,
):
    events = [] if events is None else events

    def returning(name, value):
        def invoke(*_args, **_kwargs):
            events.append(name)
            return copy.deepcopy(value)

        return invoke

    def reconstruction(*_args, **_kwargs):
        events.append("reconstruct")
        if reconstruction_error is not None:
            raise reconstruction_error
        return {
            "source_binding": copy.deepcopy(fixture["binding"]),
            "result": copy.deepcopy(fixture["result"]),
        }

    current_error = AssertionError("current source must not be inspected")
    with contextlib.ExitStack() as stack:
        stack.enter_context(
            mock.patch.object(
                stage, "_repository_path_v1", return_value=repository
            )
        )
        build_protocol = stack.enter_context(
            mock.patch.object(
                stage,
                "build_plan0014_assessment_reconstruction_protocol_v1",
                side_effect=(
                    current_error
                    if forbid_current_source
                    else returning("build-protocol", fixture["protocol"])
                ),
            )
        )
        validate_protocol = stack.enter_context(
            mock.patch.object(
                stage,
                "validate_plan0014_assessment_reconstruction_protocol_v1",
                side_effect=returning("validate-protocol", fixture["protocol"]),
            )
        )
        build_closure = stack.enter_context(
            mock.patch.object(
                stage,
                "build_plan0014_production_closure_v1",
                side_effect=(
                    current_error
                    if forbid_current_source
                    else returning("build-closure", fixture["closure"])
                ),
            )
        )
        read_plan = stack.enter_context(
            mock.patch.object(
                stage,
                "_read_active_plan_v1",
                side_effect=(
                    current_error
                    if forbid_current_source
                    else returning("read-plan", fixture["plan"])
                ),
            )
        )
        build_binding = stack.enter_context(
            mock.patch.object(
                stage,
                "build_plan0014_source_binding_v1",
                side_effect=(
                    current_error
                    if forbid_current_source
                    else returning("build-binding", fixture["binding"])
                ),
            )
        )
        validate_closure = stack.enter_context(
            mock.patch.object(
                stage,
                "validate_plan0014_production_closure_v1",
                side_effect=returning(
                    "validate-recorded-closure", fixture["closure"]
                ),
            )
        )
        validate_binding = stack.enter_context(
            mock.patch.object(
                stage,
                "validate_plan0014_source_binding_v1",
                side_effect=returning(
                    "validate-recorded-binding", fixture["binding"]
                ),
            )
        )
        reconstruct = stack.enter_context(
            mock.patch.object(
                stage,
                "reconstruct_plan0014_assessment_artifacts_v1",
                side_effect=reconstruction,
            )
        )
        reseal = stack.enter_context(
            mock.patch.object(
                stage,
                "reseal_plan0014_production_closure_v1",
                side_effect=(
                    current_error
                    if forbid_current_source
                    else returning("reseal", None)
                ),
            )
        )
        yield {
            "build_binding": build_binding,
            "build_closure": build_closure,
            "build_protocol": build_protocol,
            "read_plan": read_plan,
            "reconstruct": reconstruct,
            "reseal": reseal,
            "validate_binding": validate_binding,
            "validate_closure": validate_closure,
            "validate_protocol": validate_protocol,
        }


class ReconstructionStageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = _fixture()

    def evidence_root(self, repository):
        return (
            repository
            / protocol.PLAN0014_RECONSTRUCTION_EVIDENCE_ROOT_RELATIVE_V1
        )

    def test_run_authenticates_then_reserves_before_exactly_one_reconstruction(self):
        events = []
        real_bootstrap = stage.build_bootstrap_v1
        real_publish = stage.publish_bootstrap_v1
        real_begin = stage.begin_stage_v1
        real_complete = stage.seal_completed_v1

        def logged(name, function):
            def invoke(*args, **kwargs):
                events.append(name)
                return function(*args, **kwargs)

            return invoke

        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory).resolve()
            self.evidence_root(repository).parent.mkdir(parents=True)
            with _fixed_inputs(repository, self.fixture, events=events) as calls:
                with mock.patch.object(
                    stage,
                    "build_bootstrap_v1",
                    side_effect=logged("build-bootstrap", real_bootstrap),
                ), mock.patch.object(
                    stage,
                    "publish_bootstrap_v1",
                    side_effect=logged("publish-bootstrap", real_publish),
                ), mock.patch.object(
                    stage,
                    "begin_stage_v1",
                    side_effect=logged("begin-stage", real_begin),
                ), mock.patch.object(
                    stage,
                    "seal_completed_v1",
                    side_effect=logged("seal-completed", real_complete),
                ):
                    observed = stage.run_atlas_assessment_reconstruction_stage_v1(
                        str(repository)
                    )

            self.assertEqual(observed["lifecycle"], "COMPLETED")
            self.assertEqual(observed["result"], self.fixture["result"])
            self.assertEqual(calls["reconstruct"].call_count, 1)
            self.assertEqual(
                events,
                [
                    "build-protocol",
                    "validate-protocol",
                    "build-closure",
                    "read-plan",
                    "build-binding",
                    "build-bootstrap",
                    "validate-recorded-binding",
                    "reseal",
                    "publish-bootstrap",
                    "begin-stage",
                    "reconstruct",
                    "reseal",
                    "seal-completed",
                ],
            )

            with evidence.ReconstructionEvidenceStore.for_recovery(
                self.evidence_root(repository)
            ) as store:
                state = evidence.validate_chain_snapshot_v1(
                    evidence.fixed_reconstruction_evidence_contract_v1(),
                    store.read_bootstrap(),
                    evidence.load_chain_snapshot_v1(store),
                )
                self.assertEqual(state, "COMPLETED")

    def test_precompleted_exception_seals_failed_and_recovery_does_not_calculate(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory).resolve()
            self.evidence_root(repository).parent.mkdir(parents=True)
            failure = RuntimeError("synthetic pre-completed failure")
            with _fixed_inputs(
                repository,
                self.fixture,
                reconstruction_error=failure,
            ) as calls:
                observed = stage.run_atlas_assessment_reconstruction_stage_v1(
                    str(repository)
                )
            self.assertEqual(observed["lifecycle"], "FAILED")
            self.assertEqual(calls["reconstruct"].call_count, 1)

            with _fixed_inputs(
                repository,
                self.fixture,
                reconstruction_error=AssertionError(
                    "failed recovery must not reconstruct a report"
                ),
                forbid_current_source=True,
            ) as recovery_calls:
                recovered = (
                    stage.recover_atlas_assessment_reconstruction_stage_v1(
                        str(repository)
                    )
                )
            self.assertEqual(recovered["action"], "VERIFIED_NO_OP")
            self.assertEqual(recovered["lifecycle"], "FAILED")
            self.assertEqual(recovery_calls["reconstruct"].call_count, 0)

    def test_completed_publication_crash_is_never_replaced_and_recovers(self):
        def publish_completed_then_crash(store, contract, bootstrap, result):
            snapshot = evidence.load_chain_snapshot_v1(store)
            completed = evidence.build_completed_v1(
                contract,
                bootstrap,
                snapshot.reservation,
                snapshot.attempt,
                result,
            )
            store.publish_stage_json("completed", completed)
            raise RuntimeError("synthetic crash after completed publication")

        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory).resolve()
            self.evidence_root(repository).parent.mkdir(parents=True)
            with _fixed_inputs(repository, self.fixture):
                with mock.patch.object(
                    stage,
                    "seal_completed_v1",
                    side_effect=publish_completed_then_crash,
                ):
                    with self.assertRaisesRegex(RuntimeError, "after completed"):
                        stage.run_atlas_assessment_reconstruction_stage_v1(
                            str(repository)
                        )

            with evidence.ReconstructionEvidenceStore.for_recovery(
                self.evidence_root(repository)
            ) as store:
                snapshot = evidence.load_chain_snapshot_v1(store)
                self.assertIsNotNone(snapshot.completed)
                self.assertIsNone(snapshot.failure)
                self.assertEqual(
                    evidence.validate_chain_snapshot_v1(
                        evidence.fixed_reconstruction_evidence_contract_v1(),
                        store.read_bootstrap(),
                        snapshot,
                    ),
                    "COMPLETED_UNSEALED",
                )

            with _fixed_inputs(
                repository, self.fixture, forbid_current_source=True
            ) as recovery_calls:
                recovered = (
                    stage.recover_atlas_assessment_reconstruction_stage_v1(
                        str(repository)
                    )
                )
            self.assertEqual(recovered["action"], "SEALED_EXISTING_COMPLETED")
            self.assertEqual(recovery_calls["reconstruct"].call_count, 1)

            with _fixed_inputs(
                repository, self.fixture, forbid_current_source=True
            ) as no_op_calls:
                no_op = stage.run_atlas_assessment_reconstruction_stage_v1(
                    str(repository)
                )
            self.assertEqual(no_op["action"], "VERIFIED_NO_OP")
            self.assertEqual(no_op["lifecycle"], "COMPLETED")
            self.assertEqual(no_op_calls["reconstruct"].call_count, 1)
            self.assertEqual(no_op_calls["build_closure"].call_count, 0)
            self.assertEqual(no_op_calls["read_plan"].call_count, 0)
            self.assertEqual(no_op_calls["build_binding"].call_count, 0)
            self.assertEqual(no_op_calls["reseal"].call_count, 0)

    def test_bootstrap_only_and_attempt_recovery_never_start_calculation(self):
        for initial in ("BOOTSTRAP_ONLY", "ATTEMPTED"):
            with self.subTest(initial=initial), tempfile.TemporaryDirectory() as directory:
                repository = Path(directory).resolve()
                root = self.evidence_root(repository)
                root.parent.mkdir(parents=True)
                contract = evidence.fixed_reconstruction_evidence_contract_v1()
                with evidence.ReconstructionEvidenceStore.for_run(root) as store:
                    with store.stage_lock():
                        evidence.publish_bootstrap_v1(
                            store, self.fixture["bootstrap"]
                        )
                        if initial == "ATTEMPTED":
                            evidence.begin_stage_v1(
                                store, contract, self.fixture["bootstrap"]
                            )

                with _fixed_inputs(
                    repository,
                    self.fixture,
                    reconstruction_error=AssertionError(
                        "interrupted recovery must not calculate"
                    ),
                    forbid_current_source=True,
                ) as calls:
                    recovered = (
                        stage.recover_atlas_assessment_reconstruction_stage_v1(
                            str(repository)
                        )
                    )
                self.assertEqual(calls["reconstruct"].call_count, 0)
                if initial == "BOOTSTRAP_ONLY":
                    self.assertEqual(
                        recovered["action"], "BOOTSTRAP_ONLY_NO_STAGE"
                    )
                    self.assertIsNone(recovered["lifecycle"])
                else:
                    self.assertEqual(recovered["action"], "SEALED_NEW_ORPHANED")
                    self.assertEqual(recovered["lifecycle"], "ORPHANED")
                    with _fixed_inputs(
                        repository,
                        self.fixture,
                        reconstruction_error=AssertionError(
                            "orphan no-op must not calculate"
                        ),
                        forbid_current_source=True,
                    ) as no_op_calls:
                        no_op = (
                            stage.recover_atlas_assessment_reconstruction_stage_v1(
                                str(repository)
                            )
                        )
                    self.assertEqual(no_op["action"], "VERIFIED_NO_OP")
                    self.assertEqual(no_op_calls["reconstruct"].call_count, 0)

    def test_run_continues_operational_only_and_bootstrap_only_pre_attempt_states(self):
        for initial in ("OPERATIONAL_ONLY", "BOOTSTRAP_ONLY"):
            with self.subTest(initial=initial), tempfile.TemporaryDirectory() as directory:
                repository = Path(directory).resolve()
                root = self.evidence_root(repository)
                root.parent.mkdir(parents=True)
                with evidence.ReconstructionEvidenceStore.for_run(root) as store:
                    if initial == "BOOTSTRAP_ONLY":
                        with store.stage_lock():
                            evidence.publish_bootstrap_v1(
                                store, self.fixture["bootstrap"]
                            )

                with _fixed_inputs(repository, self.fixture) as calls:
                    observed = stage.run_atlas_assessment_reconstruction_stage_v1(
                        str(repository)
                    )

                self.assertEqual(observed["lifecycle"], "COMPLETED")
                self.assertEqual(calls["reconstruct"].call_count, 1)
                if initial == "OPERATIONAL_ONLY":
                    self.assertEqual(calls["build_closure"].call_count, 1)
                    self.assertEqual(calls["build_binding"].call_count, 1)
                else:
                    self.assertEqual(calls["build_protocol"].call_count, 0)
                    self.assertEqual(calls["build_closure"].call_count, 0)
                    self.assertEqual(calls["read_plan"].call_count, 0)
                    self.assertEqual(calls["build_binding"].call_count, 0)
                    self.assertEqual(calls["reseal"].call_count, 2)

    def test_operational_only_lock_is_ignored_by_real_clean_head(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory).resolve()
            source_repository = Path(__file__).resolve().parents[1]
            (repository / ".gitignore").write_bytes(
                (source_repository / ".gitignore").read_bytes()
            )
            (repository / "tracked.txt").write_text("fixture\n", encoding="utf-8")
            subprocess.run(
                ("git", "init", "-q", str(repository)), check=True
            )
            subprocess.run(
                ("git", "-C", str(repository), "config", "user.email", "test@example.invalid"),
                check=True,
            )
            subprocess.run(
                ("git", "-C", str(repository), "config", "user.name", "Parity Forge Test"),
                check=True,
            )
            subprocess.run(
                ("git", "-C", str(repository), "add", ".gitignore", "tracked.txt"),
                check=True,
            )
            subprocess.run(
                ("git", "-C", str(repository), "commit", "-q", "-m", "fixture"),
                check=True,
            )

            root = self.evidence_root(repository)
            root.parent.mkdir(parents=True)
            with evidence.ReconstructionEvidenceStore.for_run(root) as store:
                with store.stage_lock():
                    pass

            expected_head = subprocess.run(
                ("git", "-C", str(repository), "rev-parse", "HEAD"),
                check=True,
                stdout=subprocess.PIPE,
            ).stdout.decode("ascii").strip()
            self.assertEqual(
                capture_clean_head(repository)["source_commit"], expected_head
            )

    def test_prepublication_reseal_or_source_drift_consumes_no_attempt(self):
        for boundary in ("source-binding", "production-closure"):
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory() as directory:
                repository = Path(directory).resolve()
                root = self.evidence_root(repository)
                root.parent.mkdir(parents=True)
                with _fixed_inputs(repository, self.fixture) as calls:
                    target = (
                        calls["validate_binding"]
                        if boundary == "source-binding"
                        else calls["reseal"]
                    )
                    target.side_effect = EvidenceIntegrityError(
                        "synthetic prepublication drift"
                    )
                    with self.assertRaisesRegex(
                        EvidenceIntegrityError, "prepublication drift"
                    ):
                        stage.run_atlas_assessment_reconstruction_stage_v1(
                            str(repository)
                        )
                self.assertEqual(calls["reconstruct"].call_count, 0)
                with evidence.ReconstructionEvidenceStore.for_recovery(
                    root
                ) as store:
                    catalog = store.scan_fixed_catalog()
                    self.assertIsNone(catalog["bootstrap"])
                    self.assertFalse(store.stage_entry_exists())

    def test_missing_recovery_root_is_a_write_free_no_evidence_result(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory).resolve()
            root = self.evidence_root(repository)
            with mock.patch.object(
                stage, "_repository_path_v1", return_value=repository
            ):
                observed = (
                    stage.recover_atlas_assessment_reconstruction_stage_v1(
                        str(repository)
                    )
                )
            self.assertEqual(observed["action"], "NO_EVIDENCE")
            self.assertFalse(root.exists())

    def test_public_surface_cli_and_imports_are_capability_closed(self):
        for function in (
            stage.run_atlas_assessment_reconstruction_stage_v1,
            stage.recover_atlas_assessment_reconstruction_stage_v1,
        ):
            signature = inspect.signature(function)
            self.assertEqual(tuple(signature.parameters), ("repository",))
            self.assertIs(
                signature.parameters["repository"].default, inspect.Parameter.empty
            )

        parser = stage._build_parser()
        self.assertEqual(
            parser.parse_args(["run", "--repository", "/fixed"]).command,
            "run",
        )
        self.assertEqual(
            parser.parse_args(["recover", "--repository", "/fixed"]).command,
            "recover",
        )
        with self.assertRaises(SystemExit):
            parser.parse_args(["resume", "--repository", "/fixed"])
        destinations = {
            action.dest for action in parser._actions if action.dest != "help"
        }
        self.assertEqual(destinations, {"command", "repository"})

        source_path = Path(stage.__file__).resolve()
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.add(node.module)
        forbidden_fragments = (
            "agency",
            "agents",
            "atlas_history",
            "atlas_projection",
            "atlas_depth1_stage",
            "atlas_exact_stage",
            "atlas_manifest_stage",
            "atlas_random_stage",
            "atlas_telemetry_stage",
            "feasibility",
            "play",
            "solver",
            "terminal_search",
        )
        self.assertFalse(
            {
                name
                for name in imported
                if any(fragment in name for fragment in forbidden_fragments)
            }
        )
        calls = [
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        ]
        self.assertEqual(
            calls.count("reconstruct_plan0014_assessment_artifacts_v1"), 1
        )


if __name__ == "__main__":
    unittest.main()
