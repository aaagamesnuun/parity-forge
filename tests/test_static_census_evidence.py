import ast
import contextlib
import copy
import hashlib
import inspect
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from parity_forge_universe import static_census_evidence as _evidence
from parity_forge_universe import static_census_protocol as protocol
from parity_forge_universe import static_census_reconstruction as reconstruction
from parity_forge_universe import static_census_stage as stage


_CAPABILITY = inspect.signature(
    stage._recover_with_held_lock_v1
).parameters["_cap"].default
_AUTO_RECOVERY_CATALOG = object()


class _TestStoreAdapter:
    """Keep lifecycle tests readable while exercising only the private edge."""

    def __init__(self, store):
        self._store = store

    @classmethod
    def for_run(cls, root):
        return cls(
            _evidence._StaticCensusEvidenceStore._for_run(_CAPABILITY, root)
        )

    @classmethod
    def for_recovery(cls, root):
        return cls(
            _evidence._StaticCensusEvidenceStore._for_recovery(
                _CAPABILITY, root
            )
        )

    def __enter__(self):
        self._store.__enter__()
        return self

    def __exit__(self, kind, value, traceback):
        return self._store.__exit__(kind, value, traceback)

    def __getattr__(self, name):
        return getattr(self._store, name)

    def stage_lock(self, *, blocking=False):
        return self._store._stage_lock(_CAPABILITY, blocking=blocking)

    def reconcile_pending_publications(self):
        return self._store._reconcile_pending_publications(_CAPABILITY)

    def publish_bootstrap(self, value):
        return self._store._publish_bootstrap(_CAPABILITY, value)

    def publish_contradiction(self, value):
        return self._store._publish_contradiction(_CAPABILITY, value)

    def publish_stage_json(self, artifact, value):
        return self._store._publish_stage_json(
            _CAPABILITY, artifact, value
        )

    def publish_report_bytes(self, raw):
        return self._store._publish_report_bytes(_CAPABILITY, raw)


def _unwrap_store(store):
    return store._store if type(store) is _TestStoreAdapter else store


@contextlib.contextmanager
def _open_recovery_store_v1(root):
    with _evidence._open_recovery_store_v1(_CAPABILITY, root) as store:
        yield None if store is None else _TestStoreAdapter(store)


def _publish_bootstrap_v1(store, value):
    actual = _unwrap_store(store)
    return _evidence._publish_bootstrap_v1(
        _CAPABILITY,
        actual,
        _evidence.fixed_static_census_evidence_contract_v1(),
        value,
        actual.scan_fixed_catalog(),
    )


def _begin_stage_v1(
    store, contract, bootstrap, expected_catalog=_AUTO_RECOVERY_CATALOG
):
    actual = _unwrap_store(store)
    if expected_catalog is _AUTO_RECOVERY_CATALOG:
        expected_catalog = actual.scan_fixed_catalog()
    snapshot, _attempted_catalog = _evidence._begin_stage_v1(
        _CAPABILITY,
        actual,
        contract,
        bootstrap,
        expected_catalog,
    )
    return snapshot


def _publish_report_v1(
    store,
    contract,
    bootstrap,
    report_bytes,
    expected_catalog=_AUTO_RECOVERY_CATALOG,
):
    actual = _unwrap_store(store)
    if expected_catalog is _AUTO_RECOVERY_CATALOG:
        expected_catalog = actual.scan_fixed_catalog()
    return _evidence._publish_report_v1(
        _CAPABILITY,
        actual,
        contract,
        bootstrap,
        report_bytes,
        expected_catalog,
    )


def _seal_completed_v1(
    store,
    contract,
    bootstrap,
    expected_report_bytes=None,
    expected_catalog=_AUTO_RECOVERY_CATALOG,
):
    actual = _unwrap_store(store)
    if expected_catalog is _AUTO_RECOVERY_CATALOG:
        expected_catalog = actual.scan_fixed_catalog()
    if expected_report_bytes is None:
        expected_report_bytes = (
            _evidence._load_chain_snapshot_matching_catalog_v1(
                actual, expected_catalog
            ).report_bytes
        )
    return _evidence._seal_completed_v1(
        _CAPABILITY,
        actual,
        contract,
        bootstrap,
        expected_report_bytes,
        expected_catalog,
    )


def _seal_failed_v1(
    store,
    contract,
    bootstrap,
    failure,
    expected_catalog=_AUTO_RECOVERY_CATALOG,
):
    actual = _unwrap_store(store)
    if expected_catalog is _AUTO_RECOVERY_CATALOG:
        expected_catalog = actual.scan_fixed_catalog()
    return _evidence._seal_failed_v1(
        _CAPABILITY,
        actual,
        contract,
        bootstrap,
        failure,
        expected_catalog,
    )


def _load_chain_snapshot_v1(store):
    return _evidence.load_chain_snapshot_v1(_unwrap_store(store))


def _recover_stage_locked_v1(
    store, contract, bootstrap, expected_catalog=_AUTO_RECOVERY_CATALOG
):
    actual = _unwrap_store(store)
    if expected_catalog is _AUTO_RECOVERY_CATALOG:
        expected_catalog = actual.scan_fixed_catalog()
    return _evidence._recover_stage_locked_v1(
        _CAPABILITY,
        actual,
        contract,
        bootstrap,
        expected_catalog,
    )


def _recover_stage_v1(
    store, contract, bootstrap, expected_catalog=_AUTO_RECOVERY_CATALOG
):
    actual = _unwrap_store(store)
    with actual._stage_lock(_CAPABILITY, blocking=False):
        actual._reconcile_pending_publications(_CAPABILITY)
        if expected_catalog is _AUTO_RECOVERY_CATALOG:
            expected_catalog = actual.scan_fixed_catalog()
        return _evidence._recover_stage_locked_v1(
            _CAPABILITY,
            actual,
            contract,
            bootstrap,
            expected_catalog,
        )


class _EvidenceTestFacade:
    _MUTATION_ADAPTERS = {
        "StaticCensusEvidenceStore": _TestStoreAdapter,
        "open_recovery_store_v1": _open_recovery_store_v1,
        "publish_bootstrap_v1": _publish_bootstrap_v1,
        "begin_stage_v1": _begin_stage_v1,
        "publish_report_v1": _publish_report_v1,
        "seal_completed_v1": _seal_completed_v1,
        "seal_failed_v1": _seal_failed_v1,
        "load_chain_snapshot_v1": _load_chain_snapshot_v1,
        "recover_stage_locked_v1": _recover_stage_locked_v1,
        "recover_stage_v1": _recover_stage_v1,
    }

    def __getattr__(self, name):
        if name in self._MUTATION_ADAPTERS:
            return self._MUTATION_ADAPTERS[name]
        return getattr(_evidence, name)

    def __setattr__(self, name, value):
        setattr(_evidence, name, value)

    def __delattr__(self, name):
        delattr(_evidence, name)


evidence = _EvidenceTestFacade()


def _canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _identity(kind, payload):
    return hashlib.sha256(
        protocol.identity_domain_v1(kind) + _canonical(payload)
    ).hexdigest()


def _synthetic_closure():
    plan = b"synthetic preregistered plan\n"
    payload = {
        "active_plan_ref": {
            "byte_count": len(plan),
            "sha256": hashlib.sha256(plan).hexdigest(),
        },
        "calculation_checkpoint_commit": (
            protocol.PLAN0015_STATIC_CENSUS_CALCULATION_COMMIT_V1
        ),
        "calculation_checkpoint_tree": (
            protocol.PLAN0015_STATIC_CENSUS_CALCULATION_TREE_V1
        ),
        "ordered_entrypoint_paths": list(protocol.PRODUCTION_ENTRYPOINT_PATHS_V1),
        "ordered_file_records": [],
        "preregistration_commit": (
            protocol.PLAN0015_STATIC_CENSUS_PREREGISTRATION_COMMIT_V1
        ),
        "preregistration_tree": (
            protocol.PLAN0015_STATIC_CENSUS_PREREGISTRATION_TREE_V1
        ),
        "protocol_module_blob_identity": "1" * 40,
        "source_commit": "2" * 40,
        "source_tree": "3" * 40,
        "stage_id": protocol.STAGE_ID_V1,
    }
    assert tuple(payload) == protocol.identity_payload_keys_v1(
        "production_closure_root"
    )
    return {
        "artifact_type": protocol.PRODUCTION_CLOSURE_ARTIFACT_TYPE_V1,
        "identity": _identity("production_closure_root", payload),
        "payload": payload,
    }


_REPORT_BYTES = _canonical({"fixture": "complete-static-census-report"})


def _fake_reconstruct(raw):
    if type(raw) is not bytes:
        raise TypeError("raw report must be exact bytes")
    if raw != _REPORT_BYTES:
        raise reconstruction.StaticCensusReconstructionError(
            "synthetic report changed"
        )
    report_ref = {
        "byte_count": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    summary = {
        "report_digest": "4" * 64,
        "setup_orbit_table_root": "5" * 64,
        "skeleton_authority_root": "6" * 64,
        "ordered_shard_commitment_root": "7" * 64,
        "population": {
            "skeleton_count": 1518,
            "factorized_carrier_count": 5_111_055,
            "labeled_setup_count": 10_319_364,
            "paired_first_player_member_count": 20_638_728,
            "weight_histogram": {
                "1": 1_184_850,
                "2": 3_294_033,
                "4": 627_732,
                "8": 4_440,
            },
        },
        "eligibility": {
            "representative_eligible_count": 11,
            "weighted_eligible_count": 17,
            "paired_first_player_eligible_member_count": 34,
        },
    }
    return {
        "report": {
            "authorities": {
                "setup_orbit_table": {
                    "descriptor_root": summary["setup_orbit_table_root"]
                },
                "skeleton_authority": {
                    "descriptor_root": summary["skeleton_authority_root"]
                },
            },
            "eligibility": copy.deepcopy(summary["eligibility"]),
            "population": copy.deepcopy(summary["population"]),
            "report_digest": summary["report_digest"],
            "roots": {
                "ordered_shard_commitment_root": summary[
                    "ordered_shard_commitment_root"
                ]
            },
        },
        "report_ref": report_ref,
        "report_summary": summary,
    }


@contextlib.contextmanager
def _synthetic_report_boundary():
    with mock.patch.object(
        reconstruction,
        "reconstruct_static_census_report_artifact_v1",
        _fake_reconstruct,
    ), mock.patch.object(evidence, "_RECONSTRUCT_REPORT_V1", _fake_reconstruct):
        yield


class StaticCensusEvidenceFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol_value = protocol.build_static_census_protocol_v1()
        cls.closure = _synthetic_closure()
        cls.bootstrap = evidence.build_bootstrap_v1(
            cls.protocol_value, cls.closure
        )
        cls.contract = evidence.fixed_static_census_evidence_contract_v1()

    def new_root(self, directory):
        return Path(directory).resolve() / "evidence"


class LifecycleTests(StaticCensusEvidenceFixture):
    def _alternate_bootstrap(self):
        closure = copy.deepcopy(self.closure)
        closure["payload"]["source_commit"] = "8" * 40
        closure["payload"]["source_tree"] = "9" * 40
        closure["identity"] = _identity(
            "production_closure_root", closure["payload"]
        )
        return evidence.build_bootstrap_v1(self.protocol_value, closure)

    def test_bootstrap_with_empty_stage_parent_remains_continuable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.new_root(directory)
            with evidence.StaticCensusEvidenceStore.for_run(root) as store:
                with store.stage_lock():
                    evidence.publish_bootstrap_v1(store, self.bootstrap)
            (root / "stages").mkdir(mode=0o700)
            with evidence.StaticCensusEvidenceStore.for_recovery(root) as store:
                recovered = evidence.recover_stage_v1(
                    store, self.contract, self.bootstrap
                )
                self.assertEqual(recovered.action, "BOOTSTRAP_ONLY_NO_STAGE")
                with store.stage_lock():
                    snapshot = evidence.begin_stage_v1(
                        store, self.contract, self.bootstrap
                    )
                    self.assertEqual(
                        evidence.validate_chain_snapshot_v1(
                            self.contract, self.bootstrap, snapshot
                        ),
                        "ATTEMPTED",
                    )

    def test_honest_completed_chain_keeps_report_separate(self):
        with _synthetic_report_boundary(), tempfile.TemporaryDirectory() as directory:
            root = self.new_root(directory)
            with evidence.StaticCensusEvidenceStore.for_run(root) as store:
                with store.stage_lock():
                    evidence.publish_bootstrap_v1(store, self.bootstrap)
                    evidence.begin_stage_v1(store, self.contract, self.bootstrap)
                    reconstructed, report_catalog = evidence.publish_report_v1(
                        store,
                        self.contract,
                        self.bootstrap,
                        _REPORT_BYTES,
                    )
                    terminal = evidence.seal_completed_v1(
                        store,
                        self.contract,
                        self.bootstrap,
                        _REPORT_BYTES,
                        report_catalog,
                    )
                    snapshot = evidence.load_chain_snapshot_v1(store)
                    self.assertEqual(
                        evidence.validate_chain_snapshot_v1(
                            self.contract, self.bootstrap, snapshot
                        ),
                        "COMPLETED",
                    )
                    completed = snapshot.completed
                    self.assertEqual(
                        completed["payload"]["report_ref"],
                        reconstructed["report_ref"],
                    )
                    self.assertEqual(
                        completed["payload"]["report_summary"],
                        reconstructed["report_summary"],
                    )
                    self.assertNotIn("report", completed["payload"])
                    self.assertEqual(
                        terminal["payload"]["report_ref_or_null"],
                        reconstructed["report_ref"],
                    )
            with evidence.StaticCensusEvidenceStore.for_recovery(root) as store:
                result = evidence.recover_stage_v1(
                    store, self.contract, self.bootstrap
                )
            self.assertEqual(result.action, "VERIFIED_NO_OP")
            self.assertEqual(result.lifecycle, "COMPLETED")

    def test_honest_failure_is_bounded_and_has_no_report(self):
        huge = RuntimeError("x" * (20 * 1024))
        failure_value = evidence.failure_value_v1(huge)
        self.assertIn("exceeds", failure_value["message"])
        with tempfile.TemporaryDirectory() as directory:
            root = self.new_root(directory)
            with evidence.StaticCensusEvidenceStore.for_run(root) as store:
                with store.stage_lock():
                    evidence.publish_bootstrap_v1(store, self.bootstrap)
                    evidence.begin_stage_v1(store, self.contract, self.bootstrap)
                    evidence.seal_failed_v1(
                        store,
                        self.contract,
                        self.bootstrap,
                        failure_value,
                    )
                    snapshot = evidence.load_chain_snapshot_v1(store)
                    self.assertEqual(
                        evidence.validate_chain_snapshot_v1(
                            self.contract, self.bootstrap, snapshot
                        ),
                        "FAILED",
                    )
                    self.assertIsNone(snapshot.report_bytes)
            with evidence.StaticCensusEvidenceStore.for_recovery(root) as store:
                result = evidence.recover_stage_v1(
                    store, self.contract, self.bootstrap
                )
            self.assertEqual(result.action, "VERIFIED_NO_OP")
            self.assertEqual(result.lifecycle, "FAILED")

    def test_reserved_and_attempted_recover_to_distinct_orphans(self):
        for attempted, expected_reason in (
            (False, "RESERVATION_WITHOUT_ATTEMPT"),
            (True, "ATTEMPT_WITHOUT_LIFECYCLE_BODY"),
        ):
            with self.subTest(attempted=attempted), tempfile.TemporaryDirectory() as directory:
                root = self.new_root(directory)
                with evidence.StaticCensusEvidenceStore.for_run(root) as store:
                    with store.stage_lock():
                        evidence.publish_bootstrap_v1(store, self.bootstrap)
                        if attempted:
                            evidence.begin_stage_v1(
                                store, self.contract, self.bootstrap
                            )
                        else:
                            reservation = evidence.build_reservation_v1(
                                self.contract, self.bootstrap
                            )
                            store.publish_stage_json("reservation", reservation)
                with evidence.StaticCensusEvidenceStore.for_recovery(root) as store:
                    first = evidence.recover_stage_v1(
                        store, self.contract, self.bootstrap
                    )
                    orphaned = store.read_stage_json("orphaned")
                    second = evidence.recover_stage_v1(
                        store, self.contract, self.bootstrap
                    )
                self.assertEqual(first.action, "SEALED_NEW_ORPHANED")
                self.assertEqual(first.lifecycle, "ORPHANED")
                self.assertEqual(
                    orphaned["payload"]["orphan_reason"], expected_reason
                )
                self.assertEqual(second.action, "VERIFIED_NO_OP")

    def test_reported_crash_recovers_completion_without_recalculation(self):
        with _synthetic_report_boundary(), tempfile.TemporaryDirectory() as directory:
            root = self.new_root(directory)
            with evidence.StaticCensusEvidenceStore.for_run(root) as store:
                with store.stage_lock():
                    evidence.publish_bootstrap_v1(store, self.bootstrap)
                    evidence.begin_stage_v1(store, self.contract, self.bootstrap)
                    evidence.publish_report_v1(
                        store,
                        self.contract,
                        self.bootstrap,
                        _REPORT_BYTES,
                    )
                    self.assertEqual(
                        evidence.validate_chain_snapshot_v1(
                            self.contract,
                            self.bootstrap,
                            evidence.load_chain_snapshot_v1(store),
                        ),
                        "REPORTED",
                    )
            with evidence.StaticCensusEvidenceStore.for_recovery(root) as store:
                result = evidence.recover_stage_v1(
                    store, self.contract, self.bootstrap
                )
                state = evidence.validate_chain_snapshot_v1(
                    self.contract,
                    self.bootstrap,
                    evidence.load_chain_snapshot_v1(store),
                )
            self.assertEqual(result.action, "SEALED_REPORTED_COMPLETED")
            self.assertEqual(result.lifecycle, "COMPLETED")
            self.assertEqual(state, "COMPLETED")

    def test_recovery_rejects_bootstrap_replacement_after_held_read(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.new_root(directory)
            with evidence.StaticCensusEvidenceStore.for_run(root) as store:
                with store.stage_lock():
                    evidence.publish_bootstrap_v1(store, self.bootstrap)
                    evidence.begin_stage_v1(
                        store, self.contract, self.bootstrap
                    )

            target = root / "bootstrap.json"
            bootstrap_inode = target.stat().st_ino
            replacement = _canonical(self._alternate_bootstrap())
            real_read = _evidence._read_regular_descriptor
            replaced = []

            def replace_bootstrap_after_read(fd, **kwargs):
                raw = real_read(fd, **kwargs)
                if os.fstat(fd).st_ino == bootstrap_inode and not replaced:
                    target.unlink()
                    target.write_bytes(replacement)
                    target.chmod(0o400)
                    replaced.append(True)
                return raw

            with evidence.StaticCensusEvidenceStore.for_recovery(root) as store:
                expected_catalog = _unwrap_store(store).scan_fixed_catalog()
                with mock.patch.object(
                    _evidence,
                    "_read_regular_descriptor",
                    replace_bootstrap_after_read,
                ):
                    with self.assertRaisesRegex(
                        evidence.StaticCensusEvidenceIntegrityError,
                        "recovery failed closed",
                    ):
                        evidence.recover_stage_v1(
                            store,
                            self.contract,
                            self.bootstrap,
                            expected_catalog,
                        )
                self.assertTrue(store.contradiction_exists())
                self.assertFalse(store.stage_artifact_exists("orphaned"))
                self.assertFalse(store.stage_artifact_exists("terminal_seal"))
            self.assertEqual(replaced, [True])

    def test_recovery_without_authenticated_bootstrap_is_contradiction_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.new_root(directory)
            with evidence.StaticCensusEvidenceStore.for_run(root) as store:
                with store.stage_lock():
                    evidence.publish_bootstrap_v1(store, self.bootstrap)
                    evidence.begin_stage_v1(
                        store, self.contract, self.bootstrap
                    )
            with evidence.StaticCensusEvidenceStore.for_recovery(root) as store:
                with self.assertRaisesRegex(
                    evidence.StaticCensusEvidenceIntegrityError,
                    "recovery failed closed",
                ):
                    evidence.recover_stage_v1(store, self.contract, None)
                self.assertTrue(store.contradiction_exists())
                self.assertFalse(store.stage_artifact_exists("orphaned"))
                self.assertFalse(store.stage_artifact_exists("terminal_seal"))

    def test_begin_reloads_one_bootstrap_bound_attempted_chain(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.new_root(directory)
            with evidence.StaticCensusEvidenceStore.for_run(root) as store:
                with store.stage_lock():
                    evidence.publish_bootstrap_v1(store, self.bootstrap)
                    actual = _unwrap_store(store)
                    real_publish = actual._publish_stage_json
                    replacement = _canonical(self._alternate_bootstrap())
                    replaced = []

                    def replace_after_reservation(capability, artifact, value):
                        result = real_publish(capability, artifact, value)
                        if artifact == "reservation" and not replaced:
                            target = root / "bootstrap.json"
                            target.unlink()
                            target.write_bytes(replacement)
                            target.chmod(0o400)
                            replaced.append(True)
                        return result

                    with mock.patch.object(
                        actual,
                        "_publish_stage_json",
                        replace_after_reservation,
                    ):
                        with self.assertRaisesRegex(
                            evidence.StaticCensusEvidenceIntegrityError,
                            "catalog changed",
                        ):
                            evidence.begin_stage_v1(
                                store, self.contract, self.bootstrap
                            )
                    self.assertEqual(replaced, [True])
                    self.assertTrue(store.contradiction_exists())
                    self.assertFalse(store.stage_artifact_exists("orphaned"))
                    self.assertFalse(
                        store.stage_artifact_exists("terminal_seal")
                    )

    def test_each_unsealed_lifecycle_body_recovers_only_its_terminal(self):
        for lifecycle in ("COMPLETED", "FAILED", "ORPHANED"):
            with self.subTest(lifecycle=lifecycle), _synthetic_report_boundary(), tempfile.TemporaryDirectory() as directory:
                root = self.new_root(directory)
                with evidence.StaticCensusEvidenceStore.for_run(root) as store:
                    with store.stage_lock():
                        evidence.publish_bootstrap_v1(store, self.bootstrap)
                        snapshot = evidence.begin_stage_v1(
                            store, self.contract, self.bootstrap
                        )
                        if lifecycle == "COMPLETED":
                            (
                                reconstructed,
                                _report_catalog,
                            ) = evidence.publish_report_v1(
                                store,
                                self.contract,
                                self.bootstrap,
                                _REPORT_BYTES,
                            )
                            body = evidence.build_completed_v1(
                                self.contract,
                                self.bootstrap,
                                snapshot.reservation,
                                snapshot.attempt,
                                reconstructed,
                            )
                            store.publish_stage_json("completed", body)
                        elif lifecycle == "FAILED":
                            body = evidence.build_failure_v1(
                                self.contract,
                                self.bootstrap,
                                snapshot.reservation,
                                snapshot.attempt,
                                evidence.failure_value_v1(RuntimeError("boom")),
                            )
                            store.publish_stage_json("failure", body)
                        else:
                            body = evidence.build_orphaned_v1(
                                self.contract,
                                self.bootstrap,
                                snapshot.reservation,
                                snapshot.attempt,
                            )
                            store.publish_stage_json("orphaned", body)
                with evidence.StaticCensusEvidenceStore.for_recovery(root) as store:
                    result = evidence.recover_stage_v1(
                        store, self.contract, self.bootstrap
                    )
                    state = evidence.validate_chain_snapshot_v1(
                        self.contract,
                        self.bootstrap,
                        evidence.load_chain_snapshot_v1(store),
                    )
                self.assertEqual(result.action, "SEALED_EXISTING_" + lifecycle)
                self.assertEqual(result.lifecycle, lifecycle)
                self.assertEqual(state, lifecycle)

    def test_report_summary_boolean_alias_is_rejected_before_publication(self):
        def hostile_reconstruct(raw):
            value = _fake_reconstruct(raw)
            value["report_summary"]["eligibility"][
                "weighted_eligible_count"
            ] = True
            value["report"]["eligibility"]["weighted_eligible_count"] = True
            return value

        with mock.patch.object(
            reconstruction,
            "reconstruct_static_census_report_artifact_v1",
            hostile_reconstruct,
        ), mock.patch.object(
            evidence, "_RECONSTRUCT_REPORT_V1", hostile_reconstruct
        ), tempfile.TemporaryDirectory() as directory:
            root = self.new_root(directory)
            with evidence.StaticCensusEvidenceStore.for_run(root) as store:
                with store.stage_lock():
                    evidence.publish_bootstrap_v1(store, self.bootstrap)
                    evidence.begin_stage_v1(store, self.contract, self.bootstrap)
                    with self.assertRaises(
                        evidence.StaticCensusEvidenceIntegrityError
                    ):
                        evidence.publish_report_v1(
                            store,
                            self.contract,
                            self.bootstrap,
                            _REPORT_BYTES,
                        )
                    self.assertFalse(store.stage_artifact_exists("report"))

    def test_report_precludes_failure_and_conflict_becomes_contradiction(self):
        with _synthetic_report_boundary(), tempfile.TemporaryDirectory() as directory:
            root = self.new_root(directory)
            with evidence.StaticCensusEvidenceStore.for_run(root) as store:
                with store.stage_lock():
                    evidence.publish_bootstrap_v1(store, self.bootstrap)
                    evidence.begin_stage_v1(
                        store, self.contract, self.bootstrap
                    )
                    evidence.publish_report_v1(
                        store,
                        self.contract,
                        self.bootstrap,
                        _REPORT_BYTES,
                    )
                    with self.assertRaises(
                        evidence.StaticCensusEvidenceConflictError
                    ):
                        evidence.seal_failed_v1(
                            store,
                            self.contract,
                            self.bootstrap,
                            evidence.failure_value_v1(RuntimeError("late")),
                        )
                    self.assertTrue(store.contradiction_exists())
            with evidence.StaticCensusEvidenceStore.for_recovery(root) as store:
                with self.assertRaises(
                    evidence.StaticCensusEvidenceIntegrityError
                ):
                    evidence.recover_stage_v1(
                        store, self.contract, self.bootstrap
                    )
                self.assertTrue(store.contradiction_exists())

    def test_boolean_attempt_alias_is_rejected_even_when_rehashed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.new_root(directory)
            with evidence.StaticCensusEvidenceStore.for_run(root) as store:
                with store.stage_lock():
                    evidence.publish_bootstrap_v1(store, self.bootstrap)
                    evidence.begin_stage_v1(store, self.contract, self.bootstrap)
            attempt_path = (
                root
                / "stages"
                / evidence.STAGE_PROTOCOL_ID_V1
                / "attempt.json"
            )
            hostile = json.loads(attempt_path.read_text(encoding="utf-8"))
            hostile["payload"]["attempt_index"] = False
            hostile["identity"] = _identity("attempt_id", hostile["payload"])
            attempt_path.chmod(0o600)
            attempt_path.write_bytes(_canonical(hostile))
            attempt_path.chmod(0o400)
            with evidence.StaticCensusEvidenceStore.for_recovery(root) as store:
                with self.assertRaises(
                    evidence.StaticCensusEvidenceIntegrityError
                ):
                    evidence.recover_stage_v1(
                        store, self.contract, self.bootstrap
                    )
                self.assertTrue(store.contradiction_exists())


class StoreBoundaryTests(StaticCensusEvidenceFixture):
    def test_missing_recovery_root_is_write_free(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory).resolve()
            root = parent / "missing"
            before = tuple(parent.iterdir())
            with evidence.open_recovery_store_v1(root) as store:
                self.assertIsNone(store)
            self.assertEqual(tuple(parent.iterdir()), before)
            self.assertFalse(root.exists())

    def test_lock_is_nonblocking_nonreentrant_and_path_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.new_root(directory)
            with evidence.StaticCensusEvidenceStore.for_run(root) as first, evidence.StaticCensusEvidenceStore.for_recovery(
                root
            ) as second:
                with self.assertRaises(ValueError):
                    with first.stage_lock(blocking=True):
                        pass
                with first.stage_lock():
                    with self.assertRaises(evidence.StaticCensusEvidenceLockError):
                        with first.stage_lock():
                            pass
                    with self.assertRaises(evidence.StaticCensusEvidenceLockError):
                        with second.stage_lock():
                            pass

            with evidence.StaticCensusEvidenceStore.for_recovery(root) as store:
                moved = root.parent / "moved"
                root.rename(moved)
                root.mkdir(mode=0o700)
                with self.assertRaises(
                    evidence.StaticCensusEvidenceIntegrityError
                ):
                    store.scan_fixed_catalog()

    def test_internal_directory_descriptors_remain_name_bound(self):
        for attack in ("locks", "pending", "stage"):
            with self.subTest(attack=attack), tempfile.TemporaryDirectory() as directory:
                root = self.new_root(directory)
                with evidence.StaticCensusEvidenceStore.for_run(root) as store:
                    if attack == "locks":
                        context = store.stage_lock()
                        target = root / ".locks"
                        replacement_mode = 0o700
                    elif attack == "pending":
                        context = store._pending_fd(create=False)
                        target = root / ".pending"
                        replacement_mode = 0o700
                    else:
                        with store.stage_lock():
                            evidence.publish_bootstrap_v1(store, self.bootstrap)
                            evidence.begin_stage_v1(
                                store, self.contract, self.bootstrap
                            )
                        context = store._stage_fd(create=False)
                        target = (
                            root
                            / "stages"
                            / evidence.STAGE_PROTOCOL_ID_V1
                        )
                        replacement_mode = 0o700
                    moved = target.with_name(target.name + "-moved")
                    with self.assertRaises(evidence.StaticCensusEvidenceError):
                        with context:
                            target.rename(moved)
                            target.mkdir(mode=replacement_mode)

    def test_pending_only_is_discarded_and_linked_publish_is_finished(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.new_root(directory)
            with evidence.StaticCensusEvidenceStore.for_run(root) as store:
                pending = root / ".pending" / "root--bootstrap.json.pending"
                pending.write_bytes(_canonical({"partial": True}))
                pending.chmod(0o400)
                with store.stage_lock():
                    store.reconcile_pending_publications()
                self.assertFalse(pending.exists())

                raw = _canonical({"linked": True})
                pending.write_bytes(raw)
                pending.chmod(0o400)
                final = root / "bootstrap.json"
                os.link(pending, final)
                self.assertEqual(final.stat().st_nlink, 2)
                with store.stage_lock():
                    store.reconcile_pending_publications()
                self.assertFalse(pending.exists())
                self.assertEqual(final.stat().st_nlink, 1)
                self.assertEqual(final.read_bytes(), raw)

    def test_pending_only_cleanup_rejects_inode_swap_at_unlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.new_root(directory)
            with evidence.StaticCensusEvidenceStore.for_run(root) as store:
                pending = root / ".pending" / "root--bootstrap.json.pending"
                original = _canonical({"partial": True})
                replacement = _canonical({"replacement": True})
                pending.write_bytes(original)
                pending.chmod(0o400)
                real_unlink = os.unlink
                swapped = []

                def swap_then_unlink(name, *, dir_fd):
                    if not swapped:
                        os.rename(
                            name,
                            "held-original.pending",
                            src_dir_fd=dir_fd,
                            dst_dir_fd=dir_fd,
                        )
                        replacement_fd = os.open(
                            name,
                            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                            0o400,
                            dir_fd=dir_fd,
                        )
                        try:
                            os.write(replacement_fd, replacement)
                            os.fchmod(replacement_fd, 0o400)
                            os.fsync(replacement_fd)
                        finally:
                            os.close(replacement_fd)
                        swapped.append(True)
                    return real_unlink(name, dir_fd=dir_fd)

                with store.stage_lock(), mock.patch.object(
                    evidence.os, "unlink", swap_then_unlink
                ):
                    with self.assertRaisesRegex(
                        evidence.StaticCensusEvidenceIntegrityError,
                        "retained a link",
                    ):
                        store.reconcile_pending_publications()
                self.assertEqual(swapped, [True])
                self.assertFalse(pending.exists())
                self.assertEqual(
                    (root / ".pending" / "held-original.pending").read_bytes(),
                    original,
                )

    def test_publication_rejects_pending_inode_swap_before_link(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.new_root(directory)
            raw = _canonical(self.bootstrap)
            real_link = os.link
            swapped = []

            def swap_then_link(source, destination, **kwargs):
                pending_fd = kwargs["src_dir_fd"]
                os.unlink(source, dir_fd=pending_fd)
                replacement_fd = os.open(
                    source,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o400,
                    dir_fd=pending_fd,
                )
                try:
                    os.write(replacement_fd, raw)
                    os.fchmod(replacement_fd, 0o400)
                    os.fsync(replacement_fd)
                finally:
                    os.close(replacement_fd)
                swapped.append(True)
                return real_link(source, destination, **kwargs)

            with evidence.StaticCensusEvidenceStore.for_run(root) as store:
                with store.stage_lock(), mock.patch.object(
                    evidence.os, "link", swap_then_link
                ):
                    with self.assertRaisesRegex(
                        evidence.StaticCensusEvidenceIntegrityError,
                        "created pending artifact",
                    ):
                        store.publish_bootstrap(self.bootstrap)
            self.assertEqual(swapped, [True])

    def test_reconciliation_rejects_linked_pair_swap_after_descriptor_check(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.new_root(directory)
            with evidence.StaticCensusEvidenceStore.for_run(root) as store:
                pending = root / ".pending" / "root--bootstrap.json.pending"
                final = root / "bootstrap.json"
                pending.write_bytes(_canonical({"before": True}))
                pending.chmod(0o400)
                os.link(pending, final)
                replacement = _canonical({"after": True})
                real_read = evidence._read_regular_descriptor
                swapped = []

                def swap_pair_then_read(fd, **kwargs):
                    if not swapped:
                        pending.unlink()
                        final.unlink()
                        pending.write_bytes(replacement)
                        pending.chmod(0o400)
                        os.link(pending, final)
                        swapped.append(True)
                    return real_read(fd, **kwargs)

                with store.stage_lock(), mock.patch.object(
                    evidence,
                    "_read_regular_descriptor",
                    swap_pair_then_read,
                ):
                    with self.assertRaisesRegex(
                        evidence.StaticCensusEvidenceIntegrityError,
                        "invalid type or link count",
                    ):
                        store.reconcile_pending_publications()
                self.assertEqual(swapped, [True])
                self.assertEqual(final.read_bytes(), replacement)

    def test_chain_snapshot_rejects_stage_directory_replace_during_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.new_root(directory)
            with evidence.StaticCensusEvidenceStore.for_run(root) as store:
                with store.stage_lock():
                    evidence.publish_bootstrap_v1(store, self.bootstrap)
                    evidence.begin_stage_v1(store, self.contract, self.bootstrap)

                stage_path = (
                    root / "stages" / evidence.STAGE_PROTOCOL_ID_V1
                )
                moved_path = stage_path.with_name(stage_path.name + "-held")
                stage_inodes = {
                    (stage_path / "reservation.json").stat().st_ino,
                    (stage_path / "attempt.json").stat().st_ino,
                }
                real_read = _evidence._read_regular_descriptor
                replaced = []

                def replace_stage_after_body_read(fd, **kwargs):
                    raw = real_read(fd, **kwargs)
                    if os.fstat(fd).st_ino in stage_inodes and not replaced:
                        stage_path.rename(moved_path)
                        stage_path.mkdir(mode=0o700)
                        replaced.append(True)
                    return raw

                with mock.patch.object(
                    _evidence,
                    "_read_regular_descriptor",
                    replace_stage_after_body_read,
                ):
                    with self.assertRaisesRegex(
                        evidence.StaticCensusEvidenceIntegrityError,
                        "stage directory.*path changed",
                    ):
                        evidence.load_chain_snapshot_v1(store)
                self.assertEqual(replaced, [True])
                self.assertEqual(tuple(stage_path.iterdir()), ())
                self.assertTrue((moved_path / "reservation.json").is_file())
                self.assertTrue((moved_path / "attempt.json").is_file())

    def test_chain_snapshot_rejects_stage_entry_aba_between_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.new_root(directory)
            with evidence.StaticCensusEvidenceStore.for_run(root) as store:
                with store.stage_lock():
                    evidence.publish_bootstrap_v1(store, self.bootstrap)
                    evidence.begin_stage_v1(store, self.contract, self.bootstrap)

                stage_path = (
                    root / "stages" / evidence.STAGE_PROTOCOL_ID_V1
                )
                target = stage_path / "attempt.json"
                held = stage_path / "attempt-held.json"
                target_inode = target.stat().st_ino
                real_read = _evidence._read_regular_descriptor
                swapped = []

                def replace_and_restore_after_read(fd, **kwargs):
                    raw = real_read(fd, **kwargs)
                    if os.fstat(fd).st_ino == target_inode and not swapped:
                        target.rename(held)
                        target.write_bytes(raw)
                        target.chmod(0o400)
                        target.unlink()
                        held.rename(target)
                        swapped.append(True)
                    return raw

                with mock.patch.object(
                    _evidence,
                    "_read_regular_descriptor",
                    replace_and_restore_after_read,
                ):
                    with self.assertRaisesRegex(
                        evidence.StaticCensusEvidenceIntegrityError,
                        "changed across the evidence snapshot",
                    ):
                        evidence.load_chain_snapshot_v1(store)
                self.assertEqual(swapped, [True])
                self.assertTrue(target.is_file())

    def test_chain_snapshot_rechecks_earlier_body_after_later_read(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.new_root(directory)
            with evidence.StaticCensusEvidenceStore.for_run(root) as store:
                with store.stage_lock():
                    evidence.publish_bootstrap_v1(store, self.bootstrap)
                    evidence.begin_stage_v1(store, self.contract, self.bootstrap)

                stage_path = (
                    root / "stages" / evidence.STAGE_PROTOCOL_ID_V1
                )
                attempt = stage_path / "attempt.json"
                reservation = stage_path / "reservation.json"
                reservation_inode = reservation.stat().st_ino
                real_read = _evidence._read_regular_descriptor
                mutated = []

                def mutate_earlier_body_after_later_read(fd, **kwargs):
                    raw = real_read(fd, **kwargs)
                    if os.fstat(fd).st_ino == reservation_inode and not mutated:
                        attempt.chmod(0o600)
                        write_fd = os.open(attempt, os.O_WRONLY)
                        try:
                            os.pwrite(write_fd, b"[", 0)
                            os.fsync(write_fd)
                        finally:
                            os.close(write_fd)
                        attempt.chmod(0o400)
                        mutated.append(True)
                    return raw

                with mock.patch.object(
                    _evidence,
                    "_read_regular_descriptor",
                    mutate_earlier_body_after_later_read,
                ):
                    with self.assertRaisesRegex(
                        evidence.StaticCensusEvidenceIntegrityError,
                        "stage artifact changed across the evidence snapshot",
                    ):
                        evidence.load_chain_snapshot_v1(store)
                self.assertEqual(mutated, [True])
                self.assertEqual(attempt.read_bytes()[:1], b"[")

    def test_unknown_catalog_and_wrong_mode_fail_closed(self):
        for attack in ("unknown", "mode", "many"):
            with self.subTest(attack=attack), tempfile.TemporaryDirectory() as directory:
                root = self.new_root(directory)
                with evidence.StaticCensusEvidenceStore.for_run(root) as store:
                    if attack == "unknown":
                        (root / "unknown.json").write_bytes(b"{}")
                    elif attack == "mode":
                        target = root / "bootstrap.json"
                        target.write_bytes(b"{}")
                        target.chmod(0o600)
                    else:
                        for index in range(40):
                            (root / "unknown-{:02d}".format(index)).write_bytes(
                                b"{}"
                            )
                    with self.assertRaises(
                        evidence.StaticCensusEvidenceIntegrityError
                    ) as raised:
                        store.scan_fixed_catalog()
                    if attack == "many":
                        self.assertIn("entry bound", str(raised.exception))

    def test_symlink_fifo_socket_and_hardlink_are_rejected(self):
        attacks = ("symlink-ancestor", "fifo", "socket", "hardlink")
        for attack in attacks:
            with self.subTest(attack=attack), tempfile.TemporaryDirectory() as directory:
                parent = Path(directory).resolve()
                if attack == "symlink-ancestor":
                    real = parent / "real"
                    real.mkdir()
                    alias = parent / "alias"
                    alias.symlink_to(real, target_is_directory=True)
                    with self.assertRaises(
                        evidence.StaticCensusEvidenceIntegrityError
                    ):
                        evidence.StaticCensusEvidenceStore.for_run(
                            alias / "evidence"
                        )
                    continue

                root = parent / "evidence"
                with evidence.StaticCensusEvidenceStore.for_run(root):
                    pass
                target = root / "bootstrap.json"
                listener = None
                if attack == "fifo":
                    os.mkfifo(target)
                elif attack == "socket":
                    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    listener.bind(str(target))
                else:
                    outside = parent / "outside.json"
                    outside.write_bytes(b"{}")
                    outside.chmod(0o400)
                    os.link(outside, target)
                try:
                    with evidence.StaticCensusEvidenceStore.for_recovery(
                        root
                    ) as store:
                        with self.assertRaises(
                            evidence.StaticCensusEvidenceIntegrityError
                        ):
                            store.scan_fixed_catalog()
                finally:
                    if listener is not None:
                        listener.close()

    def test_inconsistent_pending_and_final_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.new_root(directory)
            with evidence.StaticCensusEvidenceStore.for_run(root) as store:
                pending = root / ".pending" / "root--bootstrap.json.pending"
                pending.write_bytes(_canonical({"pending": True}))
                pending.chmod(0o400)
                final = root / "bootstrap.json"
                final.write_bytes(_canonical({"final": True}))
                final.chmod(0o400)
                with store.stage_lock():
                    with self.assertRaises(
                        evidence.StaticCensusEvidenceIntegrityError
                    ):
                        store.reconcile_pending_publications()


class ModuleBoundaryTests(StaticCensusEvidenceFixture):
    def test_contract_and_protocol_bindings_are_fixed(self):
        contract = evidence.fixed_static_census_evidence_contract_v1()
        with self.assertRaises(evidence.StaticCensusEvidenceIntegrityError):
            evidence.StaticCensusEvidenceContract(
                protocol_id=contract.protocol_id,
                protocol_root=contract.protocol_root,
                evidence_protocol_id=contract.evidence_protocol_id,
                stage_id=contract.stage_id,
                stage_protocol_id=contract.stage_protocol_id,
                identity_domains=contract.identity_domains[:-1],
                identity_payload_keys=contract.identity_payload_keys,
            )
        mutated = copy.copy(contract)
        object.__setattr__(
            mutated, "identity_domains", mutated.identity_domains[:-1]
        )
        with self.assertRaises(evidence.StaticCensusEvidenceIntegrityError):
            evidence.build_reservation_v1(mutated, self.bootstrap)
        with mock.patch.object(protocol, "identity_domain_v1", lambda _kind: b"x\0"):
            with self.assertRaises(evidence.StaticCensusEvidenceIntegrityError):
                evidence.fixed_static_census_evidence_contract_v1()

    def test_module_imports_only_protocol_and_reconstruction_locally(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "parity_forge_universe"
            / "static_census_evidence.py"
        )
        tree = ast.parse(source.read_text(encoding="utf-8"))
        local_modules = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.level:
                continue
            if node.module is None:
                local_modules.update(alias.name for alias in node.names)
            else:
                local_modules.add(node.module.split(".")[0])
        self.assertEqual(
            local_modules,
            {"static_census_protocol", "static_census_reconstruction"},
        )
        text = source.read_text(encoding="utf-8")
        self.assertNotIn("from . import static_census\n", text)
        self.assertNotIn("parity_forge.", text)

    def test_mutation_surface_is_private_and_token_is_not_exported(self):
        public_mutation_names = (
            "StaticCensusEvidenceStore",
            "open_recovery_store_v1",
            "publish_bootstrap_v1",
            "begin_stage_v1",
            "publish_report_v1",
            "seal_completed_v1",
            "seal_failed_v1",
            "recover_stage_locked_v1",
            "recover_stage_v1",
        )
        for name in public_mutation_names:
            with self.subTest(name=name):
                self.assertFalse(hasattr(_evidence, name))
                self.assertNotIn(name, _evidence.__all__)
        self.assertFalse(
            any(value is _CAPABILITY for value in vars(_evidence).values())
        )

    def test_wrong_token_and_second_claim_fail_before_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.new_root(directory)
            wrong = _evidence._StaticCensusMutationCapability()
            with self.assertRaisesRegex(
                evidence.StaticCensusEvidenceIntegrityError,
                "capability is unavailable",
            ):
                _evidence._StaticCensusEvidenceStore._for_run(wrong, root)
            self.assertFalse(root.exists())

        with self.assertRaisesRegex(
            evidence.StaticCensusEvidenceIntegrityError,
            "already claimed",
        ):
            _evidence._claim_stage_mutation_capability_v1(stage)

    def test_external_caller_cannot_claim_for_a_forged_stage_binding(self):
        repository = Path(__file__).resolve().parents[1]
        source = (
            repository
            / "src"
            / "parity_forge_universe"
            / "static_census_stage.py"
        )
        script = "\n".join(
            (
                "import importlib.util, sys",
                "from parity_forge_universe import static_census_evidence as e",
                "name = 'parity_forge_universe.static_census_stage'",
                "spec = importlib.util.spec_from_file_location(name, {!r})".format(
                    str(source)
                ),
                "owner = importlib.util.module_from_spec(spec)",
                "sys.modules[name] = owner",
                "try:",
                "    e._claim_stage_mutation_capability_v1(owner)",
                "except e.StaticCensusEvidenceIntegrityError as error:",
                "    print(str(error))",
                "else:",
                "    raise SystemExit('external claim unexpectedly succeeded')",
            )
        )
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(repository / "src")
        completed = subprocess.run(
            [sys.executable, "-B", "-c", script],
            cwd=repository,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("only by the stage source", completed.stdout)


if __name__ == "__main__":
    unittest.main()
