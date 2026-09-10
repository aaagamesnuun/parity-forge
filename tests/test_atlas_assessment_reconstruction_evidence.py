from __future__ import annotations

import ast
import hashlib
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from parity_forge import atlas_assessment_reconstruction_protocol as protocol
from parity_forge.atlas_assessment_reconstruction_evidence import (
    PLAN0014_RECONSTRUCTION_STAGE_PROTOCOL_ID_V1,
    ReconstructionChainSnapshot,
    ReconstructionEvidenceStore,
    begin_stage_v1,
    build_attempt_v1,
    build_bootstrap_v1,
    build_completed_v1,
    build_failure_v1,
    build_orphaned_v1,
    build_reservation_v1,
    build_terminal_seal_v1,
    failure_value_v1,
    fixed_reconstruction_evidence_contract_v1,
    load_chain_snapshot_v1,
    open_recovery_store_v1,
    publish_bootstrap_v1,
    recover_stage_locked_v1,
    recover_stage_v1,
    seal_completed_v1,
    seal_failed_v1,
    validate_bootstrap_v1,
    validate_chain_snapshot_v1,
)
from parity_forge.atlas_evidence import (
    EvidenceConflictError,
    EvidenceIntegrityError,
    EvidenceLockError,
    canonical_json_bytes,
    domain_identity,
)


def _body_ref(raw: bytes):
    return {"byte_count": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def _assert_special_path_fails_closed_without_blocking(
    testcase, root: Path, operation: str
):
    source_root = Path(__file__).resolve().parents[1] / "src"
    environment = dict(os.environ)
    prior_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = str(source_root) + (
        "" if not prior_pythonpath else os.pathsep + prior_pythonpath
    )
    script = r"""
import os
from pathlib import Path
import sys

from parity_forge import atlas_assessment_reconstruction_evidence as evidence
from parity_forge.atlas_evidence import EvidenceIntegrityError

root = Path(sys.argv[1])
operation = sys.argv[2]
try:
    if operation == "scan":
        with evidence.ReconstructionEvidenceStore.for_recovery(root) as store:
            store.scan_fixed_catalog()
    elif operation == "lock":
        with evidence.ReconstructionEvidenceStore.for_recovery(root) as store:
            with store.stage_lock():
                pass
    elif operation == "reconcile":
        with evidence.ReconstructionEvidenceStore.for_recovery(root) as store:
            with store.stage_lock():
                store.reconcile_pending_publications()
    elif operation == "device":
        directory_fd = os.open("/dev", os.O_RDONLY | os.O_DIRECTORY)
        try:
            evidence._read_regular_at(directory_fd, "null")
        finally:
            os.close(directory_fd)
    else:
        raise AssertionError("unknown probe operation")
except EvidenceIntegrityError:
    raise SystemExit(0)
except BaseException as error:
    print(type(error).__name__ + ": " + str(error), file=sys.stderr)
    raise SystemExit(4)
raise SystemExit(5)
"""
    result = subprocess.run(
        (sys.executable, "-c", script, str(root), operation),
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
        timeout=2,
    )
    testcase.assertEqual(
        result.returncode,
        0,
        result.stderr.decode("utf-8", "replace"),
    )


def _fixture():
    protocol_value = protocol.build_plan0014_assessment_reconstruction_protocol_v1()
    plan = b"# synthetic active plan\n"
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
        "source_binding_id": "synthetic-source-binding",
        "source_binding_version": 1,
    }
    binding = {
        "artifact_type": "PLAN0014_RECONSTRUCTION_SOURCE_BINDING_V1",
        "identity": domain_identity(
            protocol.identity_domain_v1("source_binding_root"), binding_payload
        ),
        "payload": binding_payload,
    }
    bootstrap = build_bootstrap_v1(protocol_value, plan, closure, binding)
    result = {
        "inner_report": {
            "report_root": "5" * 64,
            "status": "FORMAL_COMPLETE",
        },
        "outer_attestation": {
            "artifact_type": "PLAN0014_RECONSTRUCTION_ATTESTATION_V1",
            "identity": "6" * 64,
        },
    }
    return {
        "binding": binding,
        "bootstrap": bootstrap,
        "closure": closure,
        "contract": fixed_reconstruction_evidence_contract_v1(),
        "plan": plan,
        "protocol": protocol_value,
        "result": result,
    }


class BootstrapTests(unittest.TestCase):
    def test_bootstrap_binds_all_full_references(self):
        fixture = _fixture()
        observed = validate_bootstrap_v1(fixture["bootstrap"])
        self.assertEqual(observed, fixture["bootstrap"])
        self.assertEqual(
            observed["payload"]["production_closure_root"],
            fixture["closure"]["identity"],
        )
        self.assertEqual(
            observed["payload"]["source_binding_root"],
            fixture["binding"]["identity"],
        )

    def test_bootstrap_rejects_reference_and_artifact_type_forgery(self):
        fixture = _fixture()
        forged = dict(fixture["bootstrap"])
        forged["references"] = dict(forged["references"])
        forged["references"]["active_plan_base64"] = "eA=="
        with self.assertRaises(EvidenceIntegrityError):
            validate_bootstrap_v1(forged)

        binding = dict(fixture["binding"])
        binding["artifact_type"] = "WRONG"
        with self.assertRaises(EvidenceIntegrityError):
            build_bootstrap_v1(
                fixture["protocol"],
                fixture["plan"],
                fixture["closure"],
                binding,
            )


class PureLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.fixture = _fixture()
        self.contract = self.fixture["contract"]
        self.bootstrap = self.fixture["bootstrap"]
        self.reservation = build_reservation_v1(self.contract, self.bootstrap)
        self.attempt = build_attempt_v1(
            self.contract, self.bootstrap, self.reservation
        )

    def test_completed_chain_and_terminal_reconstruct(self):
        completed = build_completed_v1(
            self.contract,
            self.bootstrap,
            self.reservation,
            self.attempt,
            self.fixture["result"],
        )
        terminal = build_terminal_seal_v1(
            self.contract,
            self.bootstrap,
            "COMPLETED",
            reservation=self.reservation,
            attempt=self.attempt,
            completed=completed,
        )
        completed_raw = canonical_json_bytes(completed)
        self.assertEqual(
            terminal["payload"]["completed_root_or_null"],
            hashlib.sha256(completed_raw).hexdigest(),
        )
        self.assertIsNone(terminal["payload"]["failure_root_or_null"])
        snapshot = ReconstructionChainSnapshot(
            reservation=self.reservation,
            attempt=self.attempt,
            completed=completed,
            terminal_seal=terminal,
        )
        self.assertEqual(
            validate_chain_snapshot_v1(
                self.contract, self.bootstrap, snapshot
            ),
            "COMPLETED",
        )

    def test_failure_and_both_orphan_shapes(self):
        failure = build_failure_v1(
            self.contract,
            self.bootstrap,
            self.reservation,
            self.attempt,
            failure_value_v1(ValueError("synthetic")),
        )
        failed_terminal = build_terminal_seal_v1(
            self.contract,
            self.bootstrap,
            "FAILED",
            reservation=self.reservation,
            attempt=self.attempt,
            failure=failure,
        )
        self.assertEqual(
            validate_chain_snapshot_v1(
                self.contract,
                self.bootstrap,
                ReconstructionChainSnapshot(
                    reservation=self.reservation,
                    attempt=self.attempt,
                    failure=failure,
                    terminal_seal=failed_terminal,
                ),
            ),
            "FAILED",
        )
        for attempt, reason in (
            (None, "RESERVATION_WITHOUT_ATTEMPT"),
            (self.attempt, "ATTEMPT_WITHOUT_LIFECYCLE_BODY"),
        ):
            with self.subTest(reason=reason):
                orphaned = build_orphaned_v1(
                    self.contract,
                    self.bootstrap,
                    self.reservation,
                    attempt,
                )
                self.assertEqual(orphaned["payload"]["orphan_reason"], reason)

    def test_chain_rejects_conflicting_bodies_and_tampered_terminal(self):
        completed = build_completed_v1(
            self.contract,
            self.bootstrap,
            self.reservation,
            self.attempt,
            self.fixture["result"],
        )
        failure = build_failure_v1(
            self.contract,
            self.bootstrap,
            self.reservation,
            self.attempt,
            failure_value_v1(RuntimeError("x")),
        )
        with self.assertRaises(EvidenceIntegrityError):
            validate_chain_snapshot_v1(
                self.contract,
                self.bootstrap,
                ReconstructionChainSnapshot(
                    reservation=self.reservation,
                    attempt=self.attempt,
                    completed=completed,
                    failure=failure,
                ),
            )

        terminal = build_terminal_seal_v1(
            self.contract,
            self.bootstrap,
            "COMPLETED",
            reservation=self.reservation,
            attempt=self.attempt,
            completed=completed,
        )
        tampered = dict(terminal)
        tampered["payload"] = dict(tampered["payload"])
        tampered["payload"]["completed_root_or_null"] = "0" * 64
        with self.assertRaises(EvidenceIntegrityError):
            validate_chain_snapshot_v1(
                self.contract,
                self.bootstrap,
                ReconstructionChainSnapshot(
                    reservation=self.reservation,
                    attempt=self.attempt,
                    completed=completed,
                    terminal_seal=tampered,
                ),
            )

    def test_exact_types_and_result_shape_are_closed(self):
        with self.assertRaises(EvidenceIntegrityError):
            build_completed_v1(
                self.contract,
                self.bootstrap,
                self.reservation,
                self.attempt,
                {"inner_report": {}, "outer_attestation": {}, "extra": True},
            )
        bad_failure = failure_value_v1(ValueError("x"))
        bad_failure["message"] = 1
        with self.assertRaises(EvidenceIntegrityError):
            build_failure_v1(
                self.contract,
                self.bootstrap,
                self.reservation,
                self.attempt,
                bad_failure,
            )


class StoreTests(unittest.TestCase):
    def test_new_directory_entries_are_synced_before_artifact_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory).resolve()
            root = parent / "evidence"
            real_fsync = os.fsync
            events = []

            def fsync_spy(fd):
                info = os.fstat(fd)
                events.append((info.st_dev, info.st_ino))
                return real_fsync(fd)

            with mock.patch(
                "parity_forge.atlas_assessment_reconstruction_evidence.os.fsync",
                side_effect=fsync_spy,
            ):
                store = ReconstructionEvidenceStore.for_run(root)
            root_identity = (root.stat().st_dev, root.stat().st_ino)
            parent_identity = (parent.stat().st_dev, parent.stat().st_ino)
            locks_identity = (
                (root / ".locks").stat().st_dev,
                (root / ".locks").stat().st_ino,
            )
            pending_identity = (
                (root / ".pending").stat().st_dev,
                (root / ".pending").stat().st_ino,
            )
            self.assertEqual(
                events[:6],
                [
                    root_identity,
                    parent_identity,
                    locks_identity,
                    root_identity,
                    pending_identity,
                    root_identity,
                ],
            )

            events.clear()
            with store.stage_lock(), mock.patch(
                "parity_forge.atlas_assessment_reconstruction_evidence.os.fsync",
                side_effect=fsync_spy,
            ):
                store.publish_stage_json("reservation", {"synthetic": True})
            stages = root / "stages"
            stage = stages / PLAN0014_RECONSTRUCTION_STAGE_PROTOCOL_ID_V1
            stages_identity = (stages.stat().st_dev, stages.stat().st_ino)
            stage_identity = (stage.stat().st_dev, stage.stat().st_ino)
            self.assertEqual(
                events[:6],
                [
                    pending_identity,
                    root_identity,
                    stages_identity,
                    root_identity,
                    stage_identity,
                    stages_identity,
                ],
            )
            store.close()

    def test_existing_create_intent_adopts_directory_durability(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory).resolve()
            root = parent / "evidence"
            with ReconstructionEvidenceStore.for_run(root):
                pass

            root_identity = (root.stat().st_dev, root.stat().st_ino)
            parent_identity = (parent.stat().st_dev, parent.stat().st_ino)
            locks_identity = (
                (root / ".locks").stat().st_dev,
                (root / ".locks").stat().st_ino,
            )
            pending_identity = (
                (root / ".pending").stat().st_dev,
                (root / ".pending").stat().st_ino,
            )
            real_fsync = os.fsync
            events = []

            def fsync_spy(fd):
                info = os.fstat(fd)
                events.append((info.st_dev, info.st_ino))
                return real_fsync(fd)

            with mock.patch(
                "parity_forge.atlas_assessment_reconstruction_evidence.os.fsync",
                side_effect=fsync_spy,
            ):
                with ReconstructionEvidenceStore.for_run(root):
                    pass

            self.assertEqual(
                events[:6],
                [
                    root_identity,
                    parent_identity,
                    locks_identity,
                    root_identity,
                    pending_identity,
                    root_identity,
                ],
            )

    def test_missing_recovery_root_is_not_created(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve() / "missing"
            with open_recovery_store_v1(root) as store:
                self.assertIsNone(store)
            self.assertFalse(root.exists())

    def test_lock_and_bootstrap_are_exclusive_and_idempotent(self):
        fixture = _fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve() / "evidence"
            with ReconstructionEvidenceStore.for_run(root) as store:
                with self.assertRaises(EvidenceLockError):
                    store.publish_bootstrap(fixture["bootstrap"])
                with store.stage_lock():
                    first = publish_bootstrap_v1(store, fixture["bootstrap"])
                    second = publish_bootstrap_v1(store, fixture["bootstrap"])
                    self.assertEqual(first, second)
                self.assertEqual(store.read_bootstrap(), fixture["bootstrap"])

    def test_descriptor_binding_survives_path_swap(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory).resolve()
            root = parent / "evidence"
            with ReconstructionEvidenceStore.for_run(root) as store:
                original = parent / "original"
                root.rename(original)
                root.mkdir()
                with store.stage_lock():
                    store.publish_bootstrap({"bound": "original"})
            self.assertTrue((original / "bootstrap.json").is_file())
            self.assertFalse((root / "bootstrap.json").exists())

    def test_symlink_ancestor_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory).resolve()
            real = parent / "real"
            real.mkdir()
            alias = parent / "alias"
            alias.symlink_to(real, target_is_directory=True)
            with self.assertRaises(EvidenceIntegrityError):
                ReconstructionEvidenceStore.for_run(alias / "evidence")

    def test_fixed_catalog_rejects_unknown_symlink_and_hardlink(self):
        for kind in ("unknown", "symlink", "hardlink"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve() / "evidence"
                with ReconstructionEvidenceStore.for_run(root) as store:
                    if kind == "unknown":
                        (root / "foreign").write_text("x", encoding="utf-8")
                    elif kind == "symlink":
                        (root / "bootstrap.json").symlink_to(root / ".locks")
                    else:
                        outside = Path(directory).resolve() / "outside.json"
                        outside.write_bytes(canonical_json_bytes({"x": 1}))
                        os.link(outside, root / "bootstrap.json")
                    with self.assertRaises(EvidenceIntegrityError):
                        store.scan_fixed_catalog()

    def test_fifo_socket_and_device_paths_fail_closed_without_blocking(self):
        for kind in (
            "bootstrap-fifo",
            "stage-fifo",
            "lock-fifo",
            "pending-fifo",
            "bootstrap-socket",
            "device",
        ):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve() / "evidence"
                bound_socket = None
                operation = "scan"
                if kind != "device":
                    with ReconstructionEvidenceStore.for_run(root):
                        pass
                if kind == "bootstrap-fifo":
                    os.mkfifo(root / "bootstrap.json", mode=0o400)
                elif kind == "stage-fifo":
                    stage_directory = (
                        root
                        / "stages"
                        / PLAN0014_RECONSTRUCTION_STAGE_PROTOCOL_ID_V1
                    )
                    stage_directory.mkdir(parents=True)
                    os.mkfifo(stage_directory / "reservation.json", mode=0o400)
                elif kind == "lock-fifo":
                    os.mkfifo(
                        root
                        / ".locks"
                        / (
                            PLAN0014_RECONSTRUCTION_STAGE_PROTOCOL_ID_V1
                            + ".lock"
                        ),
                        mode=0o600,
                    )
                    operation = "lock"
                elif kind == "pending-fifo":
                    (root / "bootstrap.json").write_bytes(
                        canonical_json_bytes({"synthetic": True})
                    )
                    (root / "bootstrap.json").chmod(0o400)
                    os.mkfifo(
                        root / ".pending" / "root--bootstrap.json.pending",
                        mode=0o400,
                    )
                    operation = "reconcile"
                elif kind == "bootstrap-socket":
                    bound_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    bound_socket.bind(str(root / "bootstrap.json"))
                else:
                    operation = "device"
                try:
                    _assert_special_path_fails_closed_without_blocking(
                        self, root, operation
                    )
                finally:
                    if bound_socket is not None:
                        bound_socket.close()

    def test_pending_only_is_discarded_and_linked_publish_is_finished(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve() / "evidence"
            with ReconstructionEvidenceStore.for_run(root) as store:
                pending = root / ".pending" / "root--bootstrap.json.pending"
                pending.write_bytes(canonical_json_bytes({"phase": "unpublished"}))
                pending.chmod(0o400)
                with store.stage_lock():
                    store.reconcile_pending_publications()
                self.assertFalse(pending.exists())

                raw = canonical_json_bytes({"phase": "linked"})
                pending.write_bytes(raw)
                pending.chmod(0o400)
                os.link(pending, root / "bootstrap.json")
                self.assertEqual((root / "bootstrap.json").stat().st_nlink, 2)
                with store.stage_lock():
                    store.reconcile_pending_publications()
                self.assertFalse(pending.exists())
                self.assertEqual((root / "bootstrap.json").stat().st_nlink, 1)
                self.assertEqual((root / "bootstrap.json").read_bytes(), raw)

    def test_unknown_or_inconsistent_pending_fails_closed(self):
        for kind in ("unknown", "different-inode"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve() / "evidence"
                with ReconstructionEvidenceStore.for_run(root) as store:
                    if kind == "unknown":
                        (root / ".pending" / "foreign.pending").write_text(
                            "x", encoding="utf-8"
                        )
                    else:
                        pending = (
                            root
                            / ".pending"
                            / "root--bootstrap.json.pending"
                        )
                        pending.write_bytes(canonical_json_bytes({"x": 1}))
                        (root / "bootstrap.json").write_bytes(
                            canonical_json_bytes({"x": 1})
                        )
                    with store.stage_lock():
                        with self.assertRaises(EvidenceIntegrityError):
                            store.reconcile_pending_publications()

    def test_link_collision_removes_unpublished_pending(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve() / "evidence"
            with ReconstructionEvidenceStore.for_run(root) as store:
                with store.stage_lock(), mock.patch(
                    "parity_forge.atlas_assessment_reconstruction_evidence.os.link",
                    side_effect=FileExistsError("synthetic collision"),
                ):
                    with self.assertRaises(EvidenceConflictError):
                        store.publish_stage_json("reservation", {"synthetic": True})
                self.assertFalse(
                    (
                        root
                        / ".pending"
                        / "stage--reservation.json.pending"
                    ).exists()
                )
                self.assertFalse(
                    (
                        root
                        / "stages"
                        / PLAN0014_RECONSTRUCTION_STAGE_PROTOCOL_ID_V1
                        / "reservation.json"
                    ).exists()
                )

    def test_stage_pending_without_stage_directory_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve() / "evidence"
            with ReconstructionEvidenceStore.for_run(root) as store:
                pending = (
                    root / ".pending" / "stage--reservation.json.pending"
                )
                pending.write_bytes(canonical_json_bytes({"synthetic": True}))
                pending.chmod(0o400)
                with store.stage_lock():
                    with self.assertRaises(EvidenceIntegrityError):
                        store.reconcile_pending_publications()
                self.assertTrue(pending.is_file())
                self.assertFalse((root / "stages").exists())

    def test_modes_and_empty_lock_are_strict(self):
        for kind in ("artifact-mode", "directory-mode", "lock-mode", "lock-body"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve() / "evidence"
                with ReconstructionEvidenceStore.for_run(root) as store:
                    if kind == "artifact-mode":
                        with store.stage_lock():
                            store.publish_bootstrap({"synthetic": True})
                        (root / "bootstrap.json").chmod(0o600)
                        with self.assertRaises(EvidenceIntegrityError):
                            store.scan_fixed_catalog()
                    elif kind == "directory-mode":
                        (root / ".pending").chmod(0o755)
                        with self.assertRaises(EvidenceIntegrityError):
                            store.scan_fixed_catalog()
                    else:
                        with store.stage_lock():
                            pass
                        lock = (
                            root
                            / ".locks"
                            / (
                                PLAN0014_RECONSTRUCTION_STAGE_PROTOCOL_ID_V1
                                + ".lock"
                            )
                        )
                        if kind == "lock-mode":
                            lock.chmod(0o400)
                        else:
                            lock.write_bytes(b"not-empty")
                            lock.chmod(0o600)
                        with self.assertRaises(EvidenceIntegrityError):
                            with store.stage_lock():
                                pass

    def test_publication_modes_are_private_and_checkout_modes_are_readable(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = _fixture()
            root = Path(directory).resolve() / "evidence"
            with ReconstructionEvidenceStore.for_run(root) as store:
                with store.stage_lock():
                    publish_bootstrap_v1(store, fixture["bootstrap"])
                    begin_stage_v1(
                        store, fixture["contract"], fixture["bootstrap"]
                    )
                    seal_completed_v1(
                        store,
                        fixture["contract"],
                        fixture["bootstrap"],
                        fixture["result"],
                    )
                stage = (
                    root
                    / "stages"
                    / PLAN0014_RECONSTRUCTION_STAGE_PROTOCOL_ID_V1
                )
                self.assertEqual(root.stat().st_mode & 0o777, 0o700)
                self.assertEqual(stage.stat().st_mode & 0o777, 0o700)
                self.assertEqual(
                    (root / "bootstrap.json").stat().st_mode & 0o777,
                    0o400,
                )
                lock = (
                    root
                    / ".locks"
                    / (PLAN0014_RECONSTRUCTION_STAGE_PROTOCOL_ID_V1 + ".lock")
                )
                self.assertEqual(lock.stat().st_mode & 0o777, 0o600)
                self.assertEqual(lock.stat().st_size, 0)

            # Git preserves file content and the executable bit, not these
            # private publication permissions.  Simulate a normal checkout.
            root.chmod(0o755)
            (root / "stages").chmod(0o755)
            stage.chmod(0o755)
            (root / "bootstrap.json").chmod(0o644)
            for artifact in stage.iterdir():
                artifact.chmod(0o644)
            with ReconstructionEvidenceStore.for_recovery(root) as recovery:
                result = recover_stage_v1(
                    recovery,
                    fixture["contract"],
                    expected_completed_result=fixture["result"],
                )
            self.assertEqual(result.action, "VERIFIED_NO_OP")

    def test_executable_artifact_mode_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve() / "evidence"
            with ReconstructionEvidenceStore.for_run(root) as store:
                with store.stage_lock():
                    store.publish_bootstrap({"synthetic": True})
                (root / "bootstrap.json").chmod(0o744)
                with self.assertRaises(EvidenceIntegrityError):
                    store.scan_fixed_catalog()

    def test_second_process_style_lock_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve() / "evidence"
            with ReconstructionEvidenceStore.for_run(root) as first, ReconstructionEvidenceStore.for_recovery(
                root
            ) as second:
                with first.stage_lock():
                    with self.assertRaises(EvidenceLockError):
                        with second.stage_lock():
                            pass


class RecoveryTests(unittest.TestCase):
    def _store_with_bootstrap(self, directory):
        fixture = _fixture()
        root = Path(directory).resolve() / "evidence"
        store = ReconstructionEvidenceStore.for_run(root)
        with store.stage_lock():
            publish_bootstrap_v1(store, fixture["bootstrap"])
        return fixture, root, store

    def test_bootstrap_only_recovery_does_not_create_stage(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture, root, store = self._store_with_bootstrap(directory)
            store.close()
            with ReconstructionEvidenceStore.for_recovery(root) as recovery:
                result = recover_stage_v1(recovery, fixture["contract"])
            self.assertEqual(result.action, "BOOTSTRAP_ONLY_NO_STAGE")
            self.assertFalse((root / "stages").exists())

    def test_existing_empty_root_recovers_as_no_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve() / "evidence"
            root.mkdir()
            root.chmod(0o700)
            with ReconstructionEvidenceStore.for_recovery(root) as recovery:
                result = recover_stage_v1(
                    recovery, fixed_reconstruction_evidence_contract_v1()
                )
            self.assertEqual(result.action, "NO_EVIDENCE")
            self.assertFalse((root / "bootstrap.json").exists())
            self.assertFalse((root / "stages").exists())

    def test_locked_recovery_requires_lock_and_matches_wrapper(self):
        with tempfile.TemporaryDirectory() as first_directory, tempfile.TemporaryDirectory() as second_directory:
            first_fixture, _first_root, first = self._store_with_bootstrap(
                first_directory
            )
            second_fixture, _second_root, second = self._store_with_bootstrap(
                second_directory
            )
            with self.assertRaises(EvidenceLockError):
                recover_stage_locked_v1(first, first_fixture["contract"])
            wrapped = recover_stage_v1(first, first_fixture["contract"])
            with second.stage_lock():
                locked = recover_stage_locked_v1(
                    second, second_fixture["contract"]
                )
            self.assertEqual(locked, wrapped)
            first.close()
            second.close()

    def test_locked_completed_recovery_prevents_observation_race(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture, root, store = self._store_with_bootstrap(directory)
            with store.stage_lock():
                snapshot = begin_stage_v1(
                    store, fixture["contract"], fixture["bootstrap"]
                )
                completed = build_completed_v1(
                    fixture["contract"],
                    fixture["bootstrap"],
                    snapshot.reservation,
                    snapshot.attempt,
                    fixture["result"],
                )
                store.publish_stage_json("completed", completed)
            store.close()

            with ReconstructionEvidenceStore.for_recovery(root) as recovery, ReconstructionEvidenceStore.for_recovery(
                root
            ) as competitor:
                with recovery.stage_lock():
                    observed = load_chain_snapshot_v1(recovery)
                    self.assertIsNotNone(observed.completed)
                    with self.assertRaises(EvidenceLockError):
                        recover_stage_v1(
                            competitor,
                            fixture["contract"],
                            expected_completed_result=fixture["result"],
                        )
                    result = recover_stage_locked_v1(
                        recovery,
                        fixture["contract"],
                        expected_completed_result=fixture["result"],
                    )
            self.assertEqual(result.action, "SEALED_EXISTING_COMPLETED")

    def test_reserved_and_attempted_recover_to_orphan_without_result(self):
        for attempted in (False, True):
            with self.subTest(attempted=attempted), tempfile.TemporaryDirectory() as directory:
                fixture, root, store = self._store_with_bootstrap(directory)
                reservation = build_reservation_v1(
                    fixture["contract"], fixture["bootstrap"]
                )
                with store.stage_lock():
                    store.publish_stage_json("reservation", reservation)
                    if attempted:
                        store.publish_stage_json(
                            "attempt",
                            build_attempt_v1(
                                fixture["contract"],
                                fixture["bootstrap"],
                                reservation,
                            ),
                        )
                store.close()
                with ReconstructionEvidenceStore.for_recovery(root) as recovery:
                    result = recover_stage_v1(recovery, fixture["contract"])
                    again = recover_stage_v1(recovery, fixture["contract"])
                self.assertEqual(result.action, "SEALED_NEW_ORPHANED")
                self.assertEqual(result.lifecycle, "ORPHANED")
                self.assertEqual(again.action, "VERIFIED_NO_OP")

    def test_failure_unsealed_is_sealed_without_completed_expectation(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture, root, store = self._store_with_bootstrap(directory)
            with store.stage_lock():
                snapshot = begin_stage_v1(
                    store, fixture["contract"], fixture["bootstrap"]
                )
                failure = build_failure_v1(
                    fixture["contract"],
                    fixture["bootstrap"],
                    snapshot.reservation,
                    snapshot.attempt,
                    failure_value_v1(RuntimeError("synthetic")),
                )
                store.publish_stage_json("failure", failure)
            store.close()
            with ReconstructionEvidenceStore.for_recovery(root) as recovery:
                result = recover_stage_v1(recovery, fixture["contract"])
            self.assertEqual(result.action, "SEALED_EXISTING_FAILED")

    def test_completed_unsealed_requires_exact_independent_result(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture, root, store = self._store_with_bootstrap(directory)
            with store.stage_lock():
                snapshot = begin_stage_v1(
                    store, fixture["contract"], fixture["bootstrap"]
                )
                completed = build_completed_v1(
                    fixture["contract"],
                    fixture["bootstrap"],
                    snapshot.reservation,
                    snapshot.attempt,
                    fixture["result"],
                )
                store.publish_stage_json("completed", completed)
            store.close()
            with ReconstructionEvidenceStore.for_recovery(root) as recovery:
                result = recover_stage_v1(
                    recovery,
                    fixture["contract"],
                    expected_completed_result=fixture["result"],
                )
            self.assertEqual(result.action, "SEALED_EXISTING_COMPLETED")

    def test_completed_body_cannot_be_replaced_by_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture, _root, store = self._store_with_bootstrap(directory)
            with store.stage_lock():
                snapshot = begin_stage_v1(
                    store, fixture["contract"], fixture["bootstrap"]
                )
                completed = build_completed_v1(
                    fixture["contract"],
                    fixture["bootstrap"],
                    snapshot.reservation,
                    snapshot.attempt,
                    fixture["result"],
                )
                store.publish_stage_json("completed", completed)
                with self.assertRaises(EvidenceConflictError):
                    seal_failed_v1(
                        store,
                        fixture["contract"],
                        fixture["bootstrap"],
                        failure_value_v1(RuntimeError("must-not-replace")),
                    )
                self.assertFalse(store.stage_artifact_exists("failure"))
            store.close()

    def test_completed_mismatch_fails_closed_with_contradiction(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture, root, store = self._store_with_bootstrap(directory)
            with store.stage_lock():
                begin_stage_v1(store, fixture["contract"], fixture["bootstrap"])
                seal_completed_v1(
                    store,
                    fixture["contract"],
                    fixture["bootstrap"],
                    fixture["result"],
                )
            store.close()
            wrong = {
                "inner_report": {"wrong": True},
                "outer_attestation": fixture["result"]["outer_attestation"],
            }
            with ReconstructionEvidenceStore.for_recovery(root) as recovery:
                with self.assertRaises(EvidenceIntegrityError):
                    recover_stage_v1(
                        recovery,
                        fixture["contract"],
                        expected_completed_result=wrong,
                    )
            self.assertTrue((root / "contradiction.json").is_file())

    def test_boundary_helpers_complete_and_fail(self):
        for lifecycle in ("COMPLETED", "FAILED"):
            with self.subTest(lifecycle=lifecycle), tempfile.TemporaryDirectory() as directory:
                fixture, _root, store = self._store_with_bootstrap(directory)
                with store.stage_lock():
                    begin_stage_v1(store, fixture["contract"], fixture["bootstrap"])
                    if lifecycle == "COMPLETED":
                        terminal = seal_completed_v1(
                            store,
                            fixture["contract"],
                            fixture["bootstrap"],
                            fixture["result"],
                        )
                    else:
                        terminal = seal_failed_v1(
                            store,
                            fixture["contract"],
                            fixture["bootstrap"],
                            failure_value_v1(ValueError("synthetic")),
                        )
                    snapshot = load_chain_snapshot_v1(store)
                self.assertEqual(terminal["payload"]["lifecycle"], lifecycle)
                self.assertEqual(
                    validate_chain_snapshot_v1(
                        fixture["contract"], fixture["bootstrap"], snapshot
                    ),
                    lifecycle,
                )
                store.close()


class ModuleBoundaryTests(unittest.TestCase):
    def test_module_has_no_report_source_or_game_capability_import(self):
        path = (
            Path(__file__).resolve().parents[1]
            / "src/parity_forge/atlas_assessment_reconstruction_evidence.py"
        )
        tree = ast.parse(path.read_text(encoding="utf-8"))
        local_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level:
                if node.module:
                    local_modules.add(node.module.split(".")[0])
                else:
                    local_modules.update(alias.name for alias in node.names)
        self.assertEqual(
            local_modules,
            {"atlas_assessment_reconstruction_protocol", "atlas_evidence"},
        )
        forbidden = {
            "agents",
            "atlas_assessment_core",
            "atlas_assessment_reconstruction",
            "atlas_assessment_reconstruction_attestation",
            "atlas_assessment_stage",
            "atlas_selector",
            "play",
            "solver",
            "telemetry",
        }
        self.assertFalse(forbidden & local_modules)


if __name__ == "__main__":
    unittest.main()
