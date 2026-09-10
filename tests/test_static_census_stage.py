from __future__ import annotations

import ast
import contextlib
import copy
import hashlib
import inspect
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from parity_forge_universe import static_census as census
from parity_forge_universe import static_census_evidence as evidence
from parity_forge_universe import static_census_protocol as protocol
from parity_forge_universe import static_census_reconstruction as reconstruction
from parity_forge_universe import static_census_stage as stage


_EVIDENCE_CAPABILITY = inspect.signature(
    stage._recover_with_held_lock_v1
).parameters["_cap"].default


def _for_run(root):
    return evidence._StaticCensusEvidenceStore._for_run(
        _EVIDENCE_CAPABILITY, root
    )


def _stage_lock(store):
    return store._stage_lock(_EVIDENCE_CAPABILITY, blocking=False)


def _publish_bootstrap(store, bootstrap):
    return evidence._publish_bootstrap_v1(
        _EVIDENCE_CAPABILITY,
        store,
        evidence.fixed_static_census_evidence_contract_v1(),
        bootstrap,
        store.scan_fixed_catalog(),
    )


def _begin_stage(store, contract, bootstrap, expected_catalog=None):
    if expected_catalog is None:
        expected_catalog = store.scan_fixed_catalog()
    return evidence._begin_stage_v1(
        _EVIDENCE_CAPABILITY,
        store,
        contract,
        bootstrap,
        expected_catalog,
    )


def _publish_report(store, contract, bootstrap, report_bytes):
    expected_catalog = store.scan_fixed_catalog()
    return evidence._publish_report_v1(
        _EVIDENCE_CAPABILITY,
        store,
        contract,
        bootstrap,
        report_bytes,
        expected_catalog,
    )


def _seal_completed(
    store,
    contract,
    bootstrap,
    expected_report_bytes=None,
    expected_catalog=None,
):
    if expected_catalog is None:
        expected_catalog = store.scan_fixed_catalog()
    if expected_report_bytes is None:
        expected_report_bytes = (
            evidence._load_chain_snapshot_matching_catalog_v1(
                store, expected_catalog
            ).report_bytes
        )
    return evidence._seal_completed_v1(
        _EVIDENCE_CAPABILITY,
        store,
        contract,
        bootstrap,
        expected_report_bytes,
        expected_catalog,
    )


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
    if tuple(payload) != protocol.identity_payload_keys_v1(
        "production_closure_root"
    ):
        raise AssertionError("synthetic production closure schema changed")
    return {
        "artifact_type": protocol.PRODUCTION_CLOSURE_ARTIFACT_TYPE_V1,
        "identity": _identity("production_closure_root", payload),
        "payload": payload,
    }


_REPORT_BYTES = _canonical({"fixture": "complete-static-census-report"})
_ALTERNATE_REPORT_BYTES = _canonical(
    {"fixture": "alternate-complete-static-census-report"}
)
_REPORT_DIGEST = "4" * 64


def _fake_reconstruct(raw):
    if type(raw) is not bytes:
        raise TypeError("raw report must be exact bytes")
    if raw not in (_REPORT_BYTES, _ALTERNATE_REPORT_BYTES):
        raise reconstruction.StaticCensusReconstructionError(
            "synthetic report changed"
        )
    report_ref = {
        "byte_count": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    summary = {
        "report_digest": _REPORT_DIGEST,
        "setup_orbit_table_root": "5" * 64,
        "skeleton_authority_root": "6" * 64,
        "ordered_shard_commitment_root": "7" * 64,
        "population": {
            "skeleton_count": 1_518,
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
    ), mock.patch.object(
        evidence, "_RECONSTRUCT_REPORT_V1", _fake_reconstruct
    ):
        yield


@contextlib.contextmanager
def _calculation_boundary(events, *, builder_error=None, reseal_error_at=None):
    token = object()
    reseal_calls = 0

    def build():
        events.append("build")
        if builder_error is not None:
            raise builder_error
        return token

    def serialize(value):
        events.append("serialize")
        if value is not token:
            raise AssertionError("serializer received another report token")
        return _REPORT_BYTES.decode("utf-8")

    def report_hash(value):
        events.append("report-hash")
        if value is not token:
            raise AssertionError("hash received another report token")
        return _REPORT_DIGEST

    def reseal(_repository, _closure):
        nonlocal reseal_calls
        reseal_calls += 1
        events.append("reseal-{}".format(reseal_calls))
        if reseal_error_at == reseal_calls:
            raise RuntimeError("synthetic reseal failure")

    with _synthetic_report_boundary(), mock.patch.object(
        census, "build_static_census_v1", build
    ), mock.patch.object(
        census, "canonical_static_census_report_json_v1", serialize
    ), mock.patch.object(
        census, "static_census_report_hash_v1", report_hash
    ):
        yield {
            "build": build,
            "report_hash": report_hash,
            "reseal": reseal,
            "serialize": serialize,
        }


class StaticCensusStageFixture(unittest.TestCase):
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

    def alternate_bootstrap(self):
        closure = copy.deepcopy(self.closure)
        closure["payload"]["source_commit"] = "8" * 40
        closure["payload"]["source_tree"] = "9" * 40
        closure["identity"] = _identity(
            "production_closure_root", closure["payload"]
        )
        return evidence.build_bootstrap_v1(self.protocol_value, closure)

    def begin(self, root):
        store = _for_run(root)
        with _stage_lock(store):
            _publish_bootstrap(store, self.bootstrap)
            _begin_stage(
                store, self.contract, self.bootstrap
            )
        return store


class StaticCensusCalculationStageTests(StaticCensusStageFixture):
    def test_attempt_precedes_exactly_one_build_and_success_is_reread(self):
        events = []
        with tempfile.TemporaryDirectory() as directory:
            root = self.new_root(directory)
            with _for_run(root) as store:
                with _stage_lock(store):
                    _publish_bootstrap(store, self.bootstrap)
                    _attempted_snapshot, attempted_catalog = _begin_stage(
                        store, self.contract, self.bootstrap
                    )
                    self.assertEqual(
                        evidence.validate_chain_snapshot_v1(
                            self.contract,
                            self.bootstrap,
                            evidence.load_chain_snapshot_v1(store),
                        ),
                        "ATTEMPTED",
                    )
                    events.append("attempt-observed")
                    real_publish = evidence._publish_report_v1
                    real_complete = evidence._seal_completed_v1

                    def publish(*args):
                        events.append("publish-report")
                        return real_publish(*args)

                    def complete(*args):
                        events.append("seal-completed")
                        return real_complete(*args)

                    with _calculation_boundary(events) as calls, mock.patch.object(
                        evidence, "_publish_report_v1", publish
                    ), mock.patch.object(
                        evidence, "_seal_completed_v1", complete
                    ):
                        observed = stage._calculate_and_seal_v1(
                            store,
                            self.contract,
                            Path(directory).resolve(),
                            self.bootstrap,
                            self.closure,
                            attempted_catalog,
                            _build=calls["build"],
                            _serialize=calls["serialize"],
                            _report_hash=calls["report_hash"],
                            _reconstruct=_fake_reconstruct,
                            _reseal=calls["reseal"],
                            _publish_report=publish,
                            _seal_completed=complete,
                        )

                    self.assertEqual(observed["lifecycle"], "COMPLETED")
                    self.assertEqual(
                        observed["report_ref"]["sha256"],
                        hashlib.sha256(_REPORT_BYTES).hexdigest(),
                    )
                    self.assertEqual(events.count("build"), 1)
                    self.assertLess(events.index("attempt-observed"), events.index("build"))
                    self.assertLess(events.index("build"), events.index("reseal-1"))
                    self.assertLess(events.index("reseal-1"), events.index("publish-report"))
                    self.assertLess(events.index("publish-report"), events.index("seal-completed"))
                    self.assertLess(
                        events.index("seal-completed"),
                        events.index("reseal-2"),
                    )
                    with _synthetic_report_boundary():
                        self.assertEqual(
                            evidence.validate_chain_snapshot_v1(
                                self.contract,
                                self.bootstrap,
                                evidence.load_chain_snapshot_v1(store),
                            ),
                            "COMPLETED",
                        )

    def test_pre_report_exception_seals_failure_once(self):
        events = []
        failure = RuntimeError("synthetic calculation failure")
        with tempfile.TemporaryDirectory() as directory:
            root = self.new_root(directory)
            with _for_run(root) as store:
                with _stage_lock(store):
                    _publish_bootstrap(store, self.bootstrap)
                    _attempted_snapshot, attempted_catalog = _begin_stage(
                        store, self.contract, self.bootstrap
                    )
                    with _calculation_boundary(
                        events, builder_error=failure
                    ) as calls:
                        observed = stage._calculate_and_seal_v1(
                            store,
                            self.contract,
                            Path(directory).resolve(),
                            self.bootstrap,
                            self.closure,
                            attempted_catalog,
                            _build=calls["build"],
                            _serialize=calls["serialize"],
                            _report_hash=calls["report_hash"],
                            _reconstruct=_fake_reconstruct,
                            _reseal=calls["reseal"],
                        )
                    snapshot = evidence.load_chain_snapshot_v1(store)
                    self.assertEqual(observed["lifecycle"], "FAILED")
                    self.assertEqual(
                        events,
                        ["build", "reseal-1", "reseal-2", "reseal-3"],
                    )
                    self.assertIsNone(snapshot.report_bytes)
                    self.assertIsNotNone(snapshot.failure)
                    self.assertIsNotNone(snapshot.terminal_seal)

    def test_attempted_receipt_blocks_bootstrap_rollback_after_build(self):
        events = []
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory).resolve()
            root = self.new_root(directory)
            stage_path = root / "stages" / evidence.STAGE_PROTOCOL_ID_V1
            displaced_stage = parent / "displaced-built-attempt"
            with _for_run(root) as store:
                with _stage_lock(store):
                    _publish_bootstrap(store, self.bootstrap)
                    _attempted_snapshot, attempted_catalog = _begin_stage(
                        store, self.contract, self.bootstrap
                    )
                    with _calculation_boundary(events) as calls:
                        real_build = calls["build"]

                        def build_then_rollback():
                            report = real_build()
                            stage_path.rename(displaced_stage)
                            return report

                        with self.assertRaisesRegex(
                            evidence.StaticCensusEvidenceIntegrityError,
                            "catalog changed",
                        ):
                            stage._calculate_and_seal_v1(
                                store,
                                self.contract,
                                parent,
                                self.bootstrap,
                                self.closure,
                                attempted_catalog,
                                _build=build_then_rollback,
                                _serialize=calls["serialize"],
                                _report_hash=calls["report_hash"],
                                _reconstruct=_fake_reconstruct,
                                _reseal=calls["reseal"],
                            )
            self.assertEqual(events.count("build"), 1)
            self.assertTrue((root / "contradiction.json").is_file())
            self.assertFalse(stage_path.exists())
            self.assertTrue((displaced_stage / "attempt.json").is_file())

    def test_attempted_receipt_blocks_bootstrap_rollback_after_build_failure(self):
        events = []
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory).resolve()
            root = self.new_root(directory)
            stage_path = root / "stages" / evidence.STAGE_PROTOCOL_ID_V1
            displaced_stage = parent / "displaced-failed-attempt"
            with _for_run(root) as store:
                with _stage_lock(store):
                    _publish_bootstrap(store, self.bootstrap)
                    _attempted_snapshot, attempted_catalog = _begin_stage(
                        store, self.contract, self.bootstrap
                    )
                    with _calculation_boundary(events) as calls:
                        real_build = calls["build"]

                        def rollback_then_fail():
                            real_build()
                            stage_path.rename(displaced_stage)
                            raise RuntimeError("synthetic rolled-back failure")

                        with self.assertRaisesRegex(
                            evidence.StaticCensusEvidenceIntegrityError,
                            "catalog changed",
                        ):
                            stage._calculate_and_seal_v1(
                                store,
                                self.contract,
                                parent,
                                self.bootstrap,
                                self.closure,
                                attempted_catalog,
                                _build=rollback_then_fail,
                                _serialize=calls["serialize"],
                                _report_hash=calls["report_hash"],
                                _reconstruct=_fake_reconstruct,
                                _reseal=calls["reseal"],
                            )
            self.assertEqual(events.count("build"), 1)
            self.assertTrue((root / "contradiction.json").is_file())
            self.assertFalse(stage_path.exists())
            self.assertTrue((displaced_stage / "attempt.json").is_file())

    def test_build_failure_rejects_swapped_report_precedence_chains(self):
        for lifecycle in ("REPORTED", "COMPLETED"):
            with self.subTest(lifecycle=lifecycle), tempfile.TemporaryDirectory() as directory:
                events = []
                parent = Path(directory).resolve()
                root = self.new_root(directory)
                replacement_root = parent / "replacement-evidence"
                with _synthetic_report_boundary():
                    with _for_run(root) as store:
                        with _stage_lock(store):
                            _publish_bootstrap(store, self.bootstrap)
                            _attempted_snapshot, attempted_catalog = _begin_stage(
                                store, self.contract, self.bootstrap
                            )
                    with _for_run(replacement_root) as replacement_store:
                        with _stage_lock(replacement_store):
                            _publish_bootstrap(
                                replacement_store, self.bootstrap
                            )
                            _begin_stage(
                                replacement_store,
                                self.contract,
                                self.bootstrap,
                            )
                            report_receipt = _publish_report(
                                replacement_store,
                                self.contract,
                                self.bootstrap,
                                _ALTERNATE_REPORT_BYTES,
                            )
                            if lifecycle == "COMPLETED":
                                _seal_completed(
                                    replacement_store,
                                    self.contract,
                                    self.bootstrap,
                                    _ALTERNATE_REPORT_BYTES,
                                    report_receipt[1],
                                )

                stage_path = (
                    root / "stages" / evidence.STAGE_PROTOCOL_ID_V1
                )
                replacement_stage = (
                    replacement_root
                    / "stages"
                    / evidence.STAGE_PROTOCOL_ID_V1
                )
                displaced_stage = parent / "displaced-build-failure-attempt"
                with _for_run(root) as store:
                    with _stage_lock(store), _calculation_boundary(
                        events
                    ) as calls:
                        real_build = calls["build"]

                        def swap_then_fail():
                            real_build()
                            stage_path.rename(displaced_stage)
                            replacement_stage.rename(stage_path)
                            raise RuntimeError(
                                "synthetic failure after precedence swap"
                            )

                        with self.assertRaisesRegex(
                            evidence.StaticCensusEvidenceIntegrityError,
                            "catalog changed",
                        ):
                            stage._calculate_and_seal_v1(
                                store,
                                self.contract,
                                parent,
                                self.bootstrap,
                                self.closure,
                                attempted_catalog,
                                _build=swap_then_fail,
                                _serialize=calls["serialize"],
                                _report_hash=calls["report_hash"],
                                _reconstruct=_fake_reconstruct,
                                _reseal=calls["reseal"],
                            )
                self.assertTrue((root / "contradiction.json").is_file())
                self.assertFalse((stage_path / "failure.json").exists())
                self.assertTrue((displaced_stage / "attempt.json").is_file())

    def test_every_transition_conflict_after_precheck_is_contradictory(self):
        for transition in ("begin", "report", "completed", "failed"):
            with self.subTest(transition=transition), tempfile.TemporaryDirectory() as directory, _synthetic_report_boundary():
                parent = Path(directory).resolve()
                root = parent / "evidence"
                replacement_root = parent / "replacement-evidence"
                failure = evidence.failure_value_v1(
                    RuntimeError("fixed transition failure")
                )

                with _for_run(root) as store:
                    with _stage_lock(store):
                        _publish_bootstrap(store, self.bootstrap)
                        attempted_catalog = None
                        report_catalog = None
                        if transition != "begin":
                            _snapshot, attempted_catalog = _begin_stage(
                                store, self.contract, self.bootstrap
                            )
                        if transition == "completed":
                            _reconstructed, report_catalog = _publish_report(
                                store,
                                self.contract,
                                self.bootstrap,
                                _REPORT_BYTES,
                            )

                with _for_run(replacement_root) as replacement_store:
                    with _stage_lock(replacement_store):
                        _publish_bootstrap(
                            replacement_store, self.bootstrap
                        )
                        _replacement_snapshot, replacement_attempted = (
                            _begin_stage(
                                replacement_store,
                                self.contract,
                                self.bootstrap,
                            )
                        )
                        if transition in ("report", "completed"):
                            (
                                _replacement_reconstruction,
                                replacement_report_catalog,
                            ) = _publish_report(
                                replacement_store,
                                self.contract,
                                self.bootstrap,
                                _REPORT_BYTES,
                            )
                        if transition == "completed":
                            _seal_completed(
                                replacement_store,
                                self.contract,
                                self.bootstrap,
                                _REPORT_BYTES,
                                replacement_report_catalog,
                            )
                        elif transition == "failed":
                            evidence._seal_failed_v1(
                                _EVIDENCE_CAPABILITY,
                                replacement_store,
                                self.contract,
                                self.bootstrap,
                                failure,
                                replacement_attempted,
                            )

                stage_path = (
                    root / "stages" / evidence.STAGE_PROTOCOL_ID_V1
                )
                replacement_stage = (
                    replacement_root
                    / "stages"
                    / evidence.STAGE_PROTOCOL_ID_V1
                )
                displaced_stage = parent / "displaced-transition-stage"
                real_json_publish = (
                    evidence._StaticCensusEvidenceStore._publish_stage_json
                )
                real_report_publish = (
                    evidence._StaticCensusEvidenceStore._publish_report_bytes
                )
                swapped = []

                def swap_stage():
                    if stage_path.exists():
                        stage_path.rename(displaced_stage)
                    else:
                        stage_path.parent.mkdir(mode=0o700, exist_ok=True)
                    replacement_stage.rename(stage_path)
                    swapped.append(True)

                def swap_then_publish_json(
                    target_store, capability, artifact, value
                ):
                    target_artifact = {
                        "begin": "reservation",
                        "completed": "completed",
                        "failed": "failure",
                    }.get(transition)
                    if not swapped and artifact == target_artifact:
                        swap_stage()
                    return real_json_publish(
                        target_store, capability, artifact, value
                    )

                def swap_then_publish_report(
                    target_store, capability, raw
                ):
                    if not swapped:
                        swap_stage()
                    return real_report_publish(target_store, capability, raw)

                publication_patch = (
                    mock.patch.object(
                        evidence._StaticCensusEvidenceStore,
                        "_publish_report_bytes",
                        swap_then_publish_report,
                    )
                    if transition == "report"
                    else mock.patch.object(
                        evidence._StaticCensusEvidenceStore,
                        "_publish_stage_json",
                        swap_then_publish_json,
                    )
                )
                with _for_run(root) as store:
                    with _stage_lock(store), publication_patch:
                        with self.assertRaises(
                            (
                                evidence.StaticCensusEvidenceConflictError,
                                evidence.StaticCensusEvidenceIntegrityError,
                            )
                        ):
                            if transition == "begin":
                                _begin_stage(
                                    store, self.contract, self.bootstrap
                                )
                            elif transition == "report":
                                evidence._publish_report_v1(
                                    _EVIDENCE_CAPABILITY,
                                    store,
                                    self.contract,
                                    self.bootstrap,
                                    _REPORT_BYTES,
                                    attempted_catalog,
                                )
                            elif transition == "completed":
                                evidence._seal_completed_v1(
                                    _EVIDENCE_CAPABILITY,
                                    store,
                                    self.contract,
                                    self.bootstrap,
                                    _REPORT_BYTES,
                                    report_catalog,
                                )
                            else:
                                evidence._seal_failed_v1(
                                    _EVIDENCE_CAPABILITY,
                                    store,
                                    self.contract,
                                    self.bootstrap,
                                    failure,
                                    attempted_catalog,
                                )
                self.assertEqual(swapped, [True])
                self.assertTrue((root / "contradiction.json").is_file())

    def test_published_report_crash_is_never_replaced_by_failure(self):
        events = []
        with tempfile.TemporaryDirectory() as directory:
            root = self.new_root(directory)
            with _for_run(root) as store:
                with _stage_lock(store):
                    _publish_bootstrap(store, self.bootstrap)
                    _attempted_snapshot, attempted_catalog = _begin_stage(
                        store, self.contract, self.bootstrap
                    )
                    real_publish = evidence._publish_report_v1

                    def publish_then_crash(*args):
                        real_publish(*args)
                        raise RuntimeError("synthetic post-report crash")

                    with _calculation_boundary(events) as calls, mock.patch.object(
                        evidence, "_publish_report_v1", publish_then_crash
                    ):
                        with self.assertRaisesRegex(
                            RuntimeError, "post-report crash"
                        ):
                            stage._calculate_and_seal_v1(
                                store,
                                self.contract,
                                Path(directory).resolve(),
                                self.bootstrap,
                                self.closure,
                                attempted_catalog,
                                _build=calls["build"],
                                _serialize=calls["serialize"],
                                _report_hash=calls["report_hash"],
                                _reconstruct=_fake_reconstruct,
                                _reseal=calls["reseal"],
                                _publish_report=publish_then_crash,
                            )
                    with _synthetic_report_boundary():
                        snapshot = evidence.load_chain_snapshot_v1(store)
                        self.assertIsNotNone(snapshot.report_bytes)
                        self.assertIsNone(snapshot.completed)
                        self.assertIsNone(snapshot.failure)
                        self.assertEqual(
                            evidence.validate_chain_snapshot_v1(
                                self.contract, self.bootstrap, snapshot
                            ),
                            "REPORTED",
                        )

    def test_report_publication_start_permanently_precludes_failure_after_swap(self):
        events = []
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory).resolve()
            root = parent / "evidence"
            replacement_root = parent / "replacement-evidence"
            with _for_run(root) as store:
                with _stage_lock(store):
                    _publish_bootstrap(store, self.bootstrap)
                    _attempted_snapshot, attempted_catalog = _begin_stage(
                        store, self.contract, self.bootstrap
                    )
            with _for_run(replacement_root) as replacement_store:
                with _stage_lock(replacement_store):
                    _publish_bootstrap(replacement_store, self.bootstrap)
                    _begin_stage(
                        replacement_store,
                        self.contract,
                        self.bootstrap,
                    )

            stage_path = root / "stages" / evidence.STAGE_PROTOCOL_ID_V1
            replacement_stage = (
                replacement_root
                / "stages"
                / evidence.STAGE_PROTOCOL_ID_V1
            )
            displaced_stage = parent / "displaced-reported-stage"
            with _for_run(root) as store:
                with _stage_lock(store):
                    real_publish = evidence._publish_report_v1

                    def publish_swap_then_crash(*args):
                        real_publish(*args)
                        stage_path.rename(displaced_stage)
                        replacement_stage.rename(stage_path)
                        raise RuntimeError("synthetic post-report path swap")

                    with _calculation_boundary(events) as calls, mock.patch.object(
                        evidence,
                        "_publish_report_v1",
                        publish_swap_then_crash,
                    ):
                        with self.assertRaisesRegex(
                            RuntimeError, "post-report path swap"
                        ):
                            stage._calculate_and_seal_v1(
                                store,
                                self.contract,
                                parent,
                                self.bootstrap,
                                self.closure,
                                attempted_catalog,
                                _build=calls["build"],
                                _serialize=calls["serialize"],
                                _report_hash=calls["report_hash"],
                                _reconstruct=_fake_reconstruct,
                                _reseal=calls["reseal"],
                                _publish_report=publish_swap_then_crash,
                            )
                    with _synthetic_report_boundary():
                        snapshot = evidence.load_chain_snapshot_v1(store)
                        self.assertEqual(
                            evidence.validate_chain_snapshot_v1(
                                self.contract, self.bootstrap, snapshot
                            ),
                            "ATTEMPTED",
                        )
                    self.assertIsNone(snapshot.failure)
                    self.assertFalse(
                        (stage_path / "failure.json").exists()
                    )
                    self.assertFalse(
                        (stage_path / "orphaned.json").exists()
                    )
                    self.assertFalse(
                        (stage_path / "terminal-seal.json").exists()
                    )
                    self.assertTrue(
                        (
                            displaced_stage / "static-census-report.json"
                        ).is_file()
                    )

    def test_completed_seal_is_bound_to_the_exact_published_report(self):
        events = []
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory).resolve()
            root = parent / "evidence"
            replacement_root = parent / "replacement-evidence"
            with _synthetic_report_boundary():
                with _for_run(root) as store:
                    with _stage_lock(store):
                        _publish_bootstrap(store, self.bootstrap)
                        _begin_stage(store, self.contract, self.bootstrap)
                with _for_run(replacement_root) as replacement_store:
                    with _stage_lock(replacement_store):
                        _publish_bootstrap(
                            replacement_store, self.bootstrap
                        )
                        _begin_stage(
                            replacement_store,
                            self.contract,
                            self.bootstrap,
                        )
                        _publish_report(
                            replacement_store,
                            self.contract,
                            self.bootstrap,
                            _ALTERNATE_REPORT_BYTES,
                        )

            stage_path = root / "stages" / evidence.STAGE_PROTOCOL_ID_V1
            replacement_stage = (
                replacement_root
                / "stages"
                / evidence.STAGE_PROTOCOL_ID_V1
            )
            displaced_stage = parent / "displaced-original-reported-stage"
            with _for_run(root) as store:
                with _stage_lock(store):
                    attempted_catalog = store.scan_fixed_catalog()
                    real_publish = evidence._publish_report_v1

                    def publish_then_swap(*args):
                        receipt = real_publish(*args)
                        stage_path.rename(displaced_stage)
                        replacement_stage.rename(stage_path)
                        return receipt

                    with _calculation_boundary(events) as calls, mock.patch.object(
                        evidence,
                        "_publish_report_v1",
                        publish_then_swap,
                    ):
                        with self.assertRaisesRegex(
                            evidence.StaticCensusEvidenceIntegrityError,
                            "catalog changed",
                        ):
                            stage._calculate_and_seal_v1(
                                store,
                                self.contract,
                                parent,
                                self.bootstrap,
                                self.closure,
                                attempted_catalog,
                                _build=calls["build"],
                                _serialize=calls["serialize"],
                                _report_hash=calls["report_hash"],
                                _reconstruct=_fake_reconstruct,
                                _reseal=calls["reseal"],
                                _publish_report=publish_then_swap,
                            )
                    self.assertTrue((root / "contradiction.json").is_file())
                    self.assertEqual(
                        (stage_path / "static-census-report.json").read_bytes(),
                        _ALTERNATE_REPORT_BYTES,
                    )
                    for filename in (
                        "completed.json",
                        "failure.json",
                        "orphaned.json",
                        "terminal-seal.json",
                    ):
                        self.assertFalse((stage_path / filename).exists())
                    self.assertTrue(
                        (
                            displaced_stage / "static-census-report.json"
                        ).is_file()
                    )

    def test_final_reseal_failure_with_completion_cannot_publish_failure(self):
        events = []
        with tempfile.TemporaryDirectory() as directory:
            root = self.new_root(directory)
            with _for_run(root) as store:
                with _stage_lock(store):
                    _publish_bootstrap(store, self.bootstrap)
                    _attempted_snapshot, attempted_catalog = _begin_stage(
                        store, self.contract, self.bootstrap
                    )
                    with _calculation_boundary(
                        events, reseal_error_at=2
                    ) as calls:
                        with self.assertRaisesRegex(
                            RuntimeError, "reseal failure"
                        ):
                            stage._calculate_and_seal_v1(
                                store,
                                self.contract,
                                Path(directory).resolve(),
                                self.bootstrap,
                                self.closure,
                                attempted_catalog,
                                _build=calls["build"],
                                _serialize=calls["serialize"],
                                _report_hash=calls["report_hash"],
                                _reconstruct=_fake_reconstruct,
                                _reseal=calls["reseal"],
                            )
                    with _synthetic_report_boundary():
                        snapshot = evidence.load_chain_snapshot_v1(store)
                        self.assertIsNotNone(snapshot.completed)
                        self.assertIsNone(snapshot.failure)
                        self.assertEqual(
                            evidence.validate_chain_snapshot_v1(
                                self.contract, self.bootstrap, snapshot
                            ),
                            "COMPLETED",
                        )


class StaticCensusRunRecoveryTests(StaticCensusStageFixture):
    def setUp(self):
        self._source_runtime_patch = mock.patch.object(
            stage, "_require_source_only_runtime_v1"
        )
        self._source_launcher_patch = mock.patch.object(
            stage, "_require_trusted_source_launcher_v1"
        )
        self._source_runtime_patch.start()
        self._source_launcher_patch.start()
        self.addCleanup(self._source_launcher_patch.stop)
        self.addCleanup(self._source_runtime_patch.stop)

    def test_fresh_public_run_reseals_and_attempts_before_calculation(self):
        events = []
        real_publish = stage._PUBLISH_BOOTSTRAP_V1
        real_begin = stage._BEGIN_STAGE_V1

        def publish(
            capability,
            store,
            contract,
            bootstrap,
            expected_catalog,
        ):
            events.append("publish-bootstrap")
            return real_publish(
                capability,
                store,
                contract,
                bootstrap,
                expected_catalog,
            )

        def begin(
            capability, store, contract, bootstrap, expected_catalog
        ):
            events.append("begin-stage")
            return real_begin(
                capability,
                store,
                contract,
                bootstrap,
                expected_catalog,
            )

        def calculate(
            store,
            contract,
            repository,
            bootstrap,
            closure,
            attempted_catalog,
            *,
            _cap,
        ):
            self.assertEqual(attempted_catalog, store.scan_fixed_catalog())
            self.assertEqual(
                evidence.validate_chain_snapshot_v1(
                    contract,
                    bootstrap,
                    evidence.load_chain_snapshot_v1(store),
                ),
                "ATTEMPTED",
            )
            self.assertEqual(closure, self.closure)
            events.append("calculate")
            return {
                "action": "SYNTHETIC_CALCULATION_BOUNDARY",
                "lifecycle": "ATTEMPTED",
            }

        def reseal(repository, closure):
            self.assertEqual(closure, self.closure)
            events.append("reseal")

        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory).resolve()
            root = repository / evidence.EVIDENCE_ROOT_RELATIVE_V1
            root.parent.mkdir(parents=True)
            with mock.patch.object(
                stage, "_require_runtime_bindings_v1"
            ), mock.patch.object(
                stage, "_repository_path_v1", return_value=repository
            ), mock.patch.object(
                stage, "_validate_runtime_origins_v1"
            ), mock.patch.object(
                stage, "_BUILD_PROTOCOL_V1", return_value=self.protocol_value
            ), mock.patch.object(
                stage,
                "_VALIDATE_PROTOCOL_V1",
                return_value=copy.deepcopy(self.protocol_value),
            ), mock.patch.object(
                stage,
                "_AUTHENTICATE_RECOVERY_CLOSURE_V1",
                return_value=copy.deepcopy(self.closure),
            ), mock.patch.object(
                stage, "_RESEAL_PRODUCTION_CLOSURE_V1", reseal
            ), mock.patch.object(
                stage, "_PUBLISH_BOOTSTRAP_V1", publish
            ), mock.patch.object(
                stage, "_BEGIN_STAGE_V1", begin
            ), mock.patch.object(
                stage, "_calculate_and_seal_v1", calculate
            ):
                observed = stage._run_static_census_stage_impl_v1(
                    str(repository)
                )

            self.assertEqual(observed["action"], "SYNTHETIC_CALCULATION_BOUNDARY")
            self.assertEqual(
                events,
                [
                    "reseal",
                    "reseal",
                    "publish-bootstrap",
                    "begin-stage",
                    "calculate",
                ],
            )

    def test_fresh_bootstrap_receipt_rejects_replacement_before_begin(self):
        alternate = self.alternate_bootstrap()
        calculate = mock.Mock(
            side_effect=AssertionError("replaced bootstrap reached calculation")
        )
        real_publish = stage._PUBLISH_BOOTSTRAP_V1

        def publish_then_replace(
            capability,
            store,
            contract,
            bootstrap,
            expected_catalog,
        ):
            receipt = real_publish(
                capability,
                store,
                contract,
                bootstrap,
                expected_catalog,
            )
            target = store.root / "bootstrap.json"
            target.unlink()
            target.write_bytes(_canonical(alternate))
            target.chmod(0o400)
            return receipt

        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory).resolve()
            root = repository / evidence.EVIDENCE_ROOT_RELATIVE_V1
            root.parent.mkdir(parents=True)
            with mock.patch.object(
                stage, "_require_runtime_bindings_v1"
            ), mock.patch.object(
                stage, "_repository_path_v1", return_value=repository
            ), mock.patch.object(
                stage, "_validate_runtime_origins_v1"
            ), mock.patch.object(
                stage, "_BUILD_PROTOCOL_V1", return_value=self.protocol_value
            ), mock.patch.object(
                stage,
                "_VALIDATE_PROTOCOL_V1",
                return_value=copy.deepcopy(self.protocol_value),
            ), mock.patch.object(
                stage,
                "_AUTHENTICATE_RECOVERY_CLOSURE_V1",
                return_value=copy.deepcopy(self.closure),
            ), mock.patch.object(
                stage, "_RESEAL_PRODUCTION_CLOSURE_V1"
            ), mock.patch.object(
                stage, "_PUBLISH_BOOTSTRAP_V1", publish_then_replace
            ), mock.patch.object(
                stage, "_calculate_and_seal_v1", calculate
            ):
                with self.assertRaisesRegex(
                    evidence.StaticCensusEvidenceIntegrityError,
                    "catalog changed",
                ):
                    stage._run_static_census_stage_impl_v1(str(repository))
            calculate.assert_not_called()
            self.assertTrue((root / "contradiction.json").is_file())
            self.assertFalse((root / "stages").exists())

    def test_missing_recovery_root_is_write_free(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory).resolve()
            root = repository / evidence.EVIDENCE_ROOT_RELATIVE_V1
            with mock.patch.object(
                stage, "_require_runtime_bindings_v1"
            ), mock.patch.object(
                stage, "_repository_path_v1", return_value=repository
            ), mock.patch.object(stage, "_validate_runtime_origins_v1"):
                observed = stage._recover_static_census_stage_impl_v1(
                    str(repository)
                )
            self.assertEqual(observed["action"], "NO_EVIDENCE")
            self.assertIsNone(observed["lifecycle"])
            self.assertFalse(root.exists())

    def test_malformed_catalog_is_routed_to_immutable_contradiction(self):
        reseal = mock.Mock()
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory).resolve()
            root = repository / evidence.EVIDENCE_ROOT_RELATIVE_V1
            root.parent.mkdir(parents=True)
            with _for_run(root):
                pass
            (root / "unknown.json").write_text("{}", encoding="utf-8")
            with mock.patch.object(
                stage, "_require_runtime_bindings_v1"
            ), mock.patch.object(
                stage, "_repository_path_v1", return_value=repository
            ), mock.patch.object(
                stage, "_validate_runtime_origins_v1"
            ), mock.patch.object(
                stage,
                "_authenticate_current_source_v1",
                return_value=copy.deepcopy(self.closure),
            ), mock.patch.object(
                stage, "_RESEAL_PRODUCTION_CLOSURE_V1", reseal
            ):
                with self.assertRaisesRegex(
                    evidence.StaticCensusEvidenceIntegrityError,
                    "recovery failed closed",
                ):
                    stage._recover_static_census_stage_impl_v1(str(repository))
            self.assertTrue((root / "contradiction.json").is_file())
            reseal.assert_called_once_with(str(repository), self.closure)

    def test_invalid_bootstrap_identity_is_an_immutable_contradiction(self):
        reseal = mock.Mock()
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory).resolve()
            root = repository / evidence.EVIDENCE_ROOT_RELATIVE_V1
            root.parent.mkdir(parents=True)
            with _for_run(root):
                pass
            invalid = copy.deepcopy(self.bootstrap)
            invalid["identity"] = "0" * 64
            (root / "bootstrap.json").write_bytes(_canonical(invalid))
            with mock.patch.object(
                stage, "_require_runtime_bindings_v1"
            ), mock.patch.object(
                stage, "_repository_path_v1", return_value=repository
            ), mock.patch.object(
                stage, "_validate_runtime_origins_v1"
            ), mock.patch.object(
                stage,
                "_authenticate_current_source_v1",
                return_value=copy.deepcopy(self.closure),
            ), mock.patch.object(
                stage, "_RESEAL_PRODUCTION_CLOSURE_V1", reseal
            ):
                with self.assertRaisesRegex(
                    evidence.StaticCensusEvidenceIntegrityError,
                    "recovery failed closed",
                ):
                    stage._recover_static_census_stage_impl_v1(str(repository))
            self.assertTrue((root / "contradiction.json").is_file())
            reseal.assert_called_once_with(str(repository), self.closure)

    def test_resigned_stored_closure_drift_is_an_immutable_contradiction(self):
        reseal = mock.Mock()
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory).resolve()
            root = repository / evidence.EVIDENCE_ROOT_RELATIVE_V1
            root.parent.mkdir(parents=True)
            with _for_run(root) as store:
                with _stage_lock(store):
                    _publish_bootstrap(store, self.bootstrap)
            alternate = self.alternate_bootstrap()

            def replace_then_reject(_repository, _store):
                target = root / "bootstrap.json"
                target.unlink()
                target.write_bytes(_canonical(alternate))
                target.chmod(0o400)
                raise protocol.StaticCensusStoredClosureIntegrityError(
                    "stored closure drift"
                )

            with mock.patch.object(
                stage, "_require_runtime_bindings_v1"
            ), mock.patch.object(
                stage, "_repository_path_v1", return_value=repository
            ), mock.patch.object(
                stage, "_validate_runtime_origins_v1"
            ), mock.patch.object(
                stage,
                "_authenticate_current_source_v1",
                return_value=copy.deepcopy(self.closure),
            ), mock.patch.object(
                stage,
                "_validate_recorded_bootstrap_v1",
                side_effect=replace_then_reject,
            ), mock.patch.object(
                stage, "_RESEAL_PRODUCTION_CLOSURE_V1", reseal
            ):
                with self.assertRaisesRegex(
                    evidence.StaticCensusEvidenceIntegrityError,
                    "stored production closure failed closed",
                ):
                    stage._recover_static_census_stage_impl_v1(str(repository))
            contradiction_path = root / "contradiction.json"
            self.assertTrue(contradiction_path.is_file())
            contradiction = json.loads(contradiction_path.read_bytes())
            alternate_raw = _canonical(alternate)
            self.assertEqual(
                contradiction["payload"]["bootstrap_root_or_null"],
                alternate["identity"],
            )
            self.assertEqual(
                contradiction["payload"]["observed_catalog_refs"][
                    "bootstrap"
                ],
                {
                    "byte_count": len(alternate_raw),
                    "sha256": hashlib.sha256(alternate_raw).hexdigest(),
                },
            )
            reseal.assert_called_once_with(str(repository), self.closure)

    def test_ambient_git_failure_during_stored_validation_is_write_free(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory).resolve()
            root = repository / evidence.EVIDENCE_ROOT_RELATIVE_V1
            root.parent.mkdir(parents=True)
            with _for_run(root) as store:
                with _stage_lock(store):
                    _publish_bootstrap(store, self.bootstrap)
            with mock.patch.object(
                stage, "_require_runtime_bindings_v1"
            ), mock.patch.object(
                stage, "_repository_path_v1", return_value=repository
            ), mock.patch.object(
                stage, "_validate_runtime_origins_v1"
            ), mock.patch.object(
                stage,
                "_authenticate_current_source_v1",
                return_value=copy.deepcopy(self.closure),
            ), mock.patch.object(
                stage,
                "_validate_recorded_bootstrap_v1",
                side_effect=protocol.StaticCensusProtocolError(
                    "ambient Git lookup failed"
                ),
            ):
                with self.assertRaisesRegex(
                    protocol.StaticCensusProtocolError,
                    "ambient Git lookup failed",
                ):
                    stage._recover_static_census_stage_impl_v1(str(repository))
            self.assertFalse((root / "contradiction.json").exists())

    def test_existing_run_routes_stored_closure_drift_to_contradiction(self):
        poison_builder = mock.Mock(
            side_effect=AssertionError("stored-drift run called the builder")
        )
        reseal = mock.Mock()
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory).resolve()
            root = repository / evidence.EVIDENCE_ROOT_RELATIVE_V1
            root.parent.mkdir(parents=True)
            with _for_run(root) as store:
                with _stage_lock(store):
                    _publish_bootstrap(store, self.bootstrap)
            with mock.patch.object(
                stage, "_require_runtime_bindings_v1"
            ), mock.patch.object(
                stage, "_repository_path_v1", return_value=repository
            ), mock.patch.object(
                stage, "_validate_runtime_origins_v1"
            ), mock.patch.object(
                stage,
                "_authenticate_current_source_v1",
                return_value=copy.deepcopy(self.closure),
            ), mock.patch.object(
                stage,
                "_validate_recorded_bootstrap_v1",
                side_effect=protocol.StaticCensusStoredClosureIntegrityError(
                    "stored closure drift"
                ),
            ), mock.patch.object(
                stage, "_RESEAL_PRODUCTION_CLOSURE_V1", reseal
            ), mock.patch.object(
                census, "build_static_census_v1", poison_builder
            ), mock.patch.object(
                stage, "_BUILD_CENSUS_V1", poison_builder
            ):
                with self.assertRaisesRegex(
                    evidence.StaticCensusEvidenceIntegrityError,
                    "stored production closure failed closed",
                ):
                    stage._run_static_census_stage_impl_v1(str(repository))
            poison_builder.assert_not_called()
            self.assertTrue((root / "contradiction.json").is_file())

    def test_existing_run_keeps_ambient_git_failure_write_free(self):
        poison_builder = mock.Mock(
            side_effect=AssertionError("ambient-failure run called the builder")
        )
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory).resolve()
            root = repository / evidence.EVIDENCE_ROOT_RELATIVE_V1
            root.parent.mkdir(parents=True)
            with _for_run(root) as store:
                with _stage_lock(store):
                    _publish_bootstrap(store, self.bootstrap)
            with mock.patch.object(
                stage, "_require_runtime_bindings_v1"
            ), mock.patch.object(
                stage, "_repository_path_v1", return_value=repository
            ), mock.patch.object(
                stage, "_validate_runtime_origins_v1"
            ), mock.patch.object(
                stage,
                "_authenticate_current_source_v1",
                return_value=copy.deepcopy(self.closure),
            ), mock.patch.object(
                stage,
                "_validate_recorded_bootstrap_v1",
                side_effect=protocol.StaticCensusProtocolError(
                    "ambient Git lookup failed"
                ),
            ), mock.patch.object(
                stage, "_RESEAL_PRODUCTION_CLOSURE_V1"
            ), mock.patch.object(
                census, "build_static_census_v1", poison_builder
            ), mock.patch.object(
                stage, "_BUILD_CENSUS_V1", poison_builder
            ):
                with self.assertRaisesRegex(
                    protocol.StaticCensusProtocolError,
                    "ambient Git lookup failed",
                ):
                    stage._run_static_census_stage_impl_v1(str(repository))
            poison_builder.assert_not_called()
            self.assertFalse((root / "contradiction.json").exists())

    def test_existing_run_never_recalculates_nonbootstrap_lifecycles(self):
        expected_actions = {
            "ATTEMPTED": "SEALED_NEW_ORPHANED",
            "REPORTED": "SEALED_REPORTED_COMPLETED",
            "COMPLETED": "VERIFIED_NO_OP",
        }
        for lifecycle, expected_action in expected_actions.items():
            with self.subTest(lifecycle=lifecycle), tempfile.TemporaryDirectory() as directory:
                repository = Path(directory).resolve()
                root = repository / evidence.EVIDENCE_ROOT_RELATIVE_V1
                root.parent.mkdir(parents=True)
                with _synthetic_report_boundary():
                    with _for_run(root) as store:
                        with _stage_lock(store):
                            _publish_bootstrap(store, self.bootstrap)
                            _begin_stage(store, self.contract, self.bootstrap)
                            if lifecycle in ("REPORTED", "COMPLETED"):
                                _publish_report(
                                    store,
                                    self.contract,
                                    self.bootstrap,
                                    _REPORT_BYTES,
                                )
                            if lifecycle == "COMPLETED":
                                _seal_completed(
                                    store, self.contract, self.bootstrap
                                )
                    poison_builder = mock.Mock(
                        side_effect=AssertionError(
                            "existing run called the census builder"
                        )
                    )
                    with mock.patch.object(
                        stage, "_require_runtime_bindings_v1"
                    ), mock.patch.object(
                        stage, "_repository_path_v1", return_value=repository
                    ), mock.patch.object(
                        stage, "_validate_runtime_origins_v1"
                    ), mock.patch.object(
                        stage,
                        "_authenticate_current_source_v1",
                        return_value=copy.deepcopy(self.closure),
                    ), mock.patch.object(
                        stage,
                        "_validate_recorded_bootstrap_v1",
                        return_value=copy.deepcopy(self.bootstrap),
                    ), mock.patch.object(
                        stage, "_RECONSTRUCT_REPORT_V1", _fake_reconstruct
                    ), mock.patch.object(
                        stage, "_RESEAL_PRODUCTION_CLOSURE_V1"
                    ), mock.patch.object(
                        census, "build_static_census_v1", poison_builder
                    ), mock.patch.object(
                        stage, "_BUILD_CENSUS_V1", poison_builder
                    ):
                        observed = stage._run_static_census_stage_impl_v1(
                            str(repository)
                        )
                self.assertEqual(observed["action"], expected_action)
                poison_builder.assert_not_called()

    def test_attempt_recovery_orphans_without_builder_or_checkpoint(self):
        poison_builder = mock.Mock(
            side_effect=AssertionError("recover called the census builder")
        )
        reseal = mock.Mock()
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory).resolve()
            root = repository / evidence.EVIDENCE_ROOT_RELATIVE_V1
            root.parent.mkdir(parents=True)
            with _for_run(root) as store:
                with _stage_lock(store):
                    _publish_bootstrap(store, self.bootstrap)
                    _begin_stage(
                        store, self.contract, self.bootstrap
                    )

            with mock.patch.object(
                stage, "_require_runtime_bindings_v1"
            ), mock.patch.object(
                stage, "_repository_path_v1", return_value=repository
            ), mock.patch.object(
                stage, "_validate_runtime_origins_v1"
            ), mock.patch.object(
                stage,
                "_validate_recorded_bootstrap_v1",
                return_value=copy.deepcopy(self.bootstrap),
            ), mock.patch.object(
                stage,
                "_authenticate_current_source_v1",
                return_value=copy.deepcopy(self.closure),
            ), mock.patch.object(
                census,
                "build_static_census_v1",
                poison_builder,
            ), mock.patch.object(
                stage, "_BUILD_CENSUS_V1", poison_builder
            ), mock.patch.object(
                stage, "_RESEAL_PRODUCTION_CLOSURE_V1", reseal
            ), mock.patch.object(
                census,
                "advance_static_census_checkpoint_v1",
                side_effect=AssertionError("recover advanced a checkpoint"),
            ):
                observed = stage._recover_static_census_stage_impl_v1(
                    str(repository)
                )
            self.assertEqual(observed["action"], "SEALED_NEW_ORPHANED")
            self.assertEqual(observed["lifecycle"], "ORPHANED")
            poison_builder.assert_not_called()
            self.assertEqual(reseal.call_count, 2)
            reseal.assert_has_calls(
                [mock.call(str(repository), self.closure)] * 2
            )

    def test_recovery_binds_git_authenticated_bootstrap_to_evidence_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory).resolve()
            root = repository / evidence.EVIDENCE_ROOT_RELATIVE_V1
            root.parent.mkdir(parents=True)
            with _for_run(root) as store:
                with _stage_lock(store):
                    _publish_bootstrap(store, self.bootstrap)
                    _begin_stage(store, self.contract, self.bootstrap)

            alternate = self.alternate_bootstrap()
            reservation = evidence.build_reservation_v1(
                self.contract, alternate
            )
            attempt = evidence.build_attempt_v1(
                self.contract, alternate, reservation
            )
            replacements = (
                (root / "bootstrap.json", alternate),
                (
                    root
                    / "stages"
                    / evidence.STAGE_PROTOCOL_ID_V1
                    / "reservation.json",
                    reservation,
                ),
                (
                    root
                    / "stages"
                    / evidence.STAGE_PROTOCOL_ID_V1
                    / "attempt.json",
                    attempt,
                ),
            )
            real_recover = stage._RECOVER_STAGE_LOCKED_V1
            swapped = []

            def swap_then_recover(
                capability,
                store,
                contract,
                authenticated,
                expected_catalog,
            ):
                self.assertEqual(authenticated, self.bootstrap)
                for path, value in replacements:
                    path.unlink()
                    path.write_bytes(_canonical(value))
                    path.chmod(0o400)
                swapped.append(True)
                return real_recover(
                    capability,
                    store,
                    contract,
                    authenticated,
                    expected_catalog,
                )

            with mock.patch.object(
                stage, "_require_runtime_bindings_v1"
            ), mock.patch.object(
                stage, "_repository_path_v1", return_value=repository
            ), mock.patch.object(
                stage, "_validate_runtime_origins_v1"
            ), mock.patch.object(
                stage,
                "_authenticate_current_source_v1",
                return_value=copy.deepcopy(self.closure),
            ), mock.patch.object(
                stage,
                "_validate_recorded_bootstrap_v1",
                return_value=copy.deepcopy(self.bootstrap),
            ), mock.patch.object(
                stage, "_RESEAL_PRODUCTION_CLOSURE_V1"
            ), mock.patch.object(
                stage,
                "_RECOVER_STAGE_LOCKED_V1",
                swap_then_recover,
            ):
                with self.assertRaisesRegex(
                    evidence.StaticCensusEvidenceIntegrityError,
                    "recovery failed closed",
                ):
                    stage._recover_static_census_stage_impl_v1(
                        str(repository)
                    )
            self.assertEqual(swapped, [True])
            self.assertTrue((root / "contradiction.json").is_file())
            stage_root = root / "stages" / evidence.STAGE_PROTOCOL_ID_V1
            self.assertFalse((stage_root / "orphaned.json").exists())
            self.assertFalse((stage_root / "terminal-seal.json").exists())

    def test_existing_completed_catalog_cannot_swap_to_attempted_and_recalculate(self):
        poison_builder = mock.Mock(
            side_effect=AssertionError("catalog rollback called the builder")
        )
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory).resolve()
            root = repository / evidence.EVIDENCE_ROOT_RELATIVE_V1
            replacement_root = repository / "replacement-evidence"
            root.parent.mkdir(parents=True)
            with _synthetic_report_boundary():
                with _for_run(root) as store:
                    with _stage_lock(store):
                        _publish_bootstrap(store, self.bootstrap)
                        _begin_stage(store, self.contract, self.bootstrap)
                        _publish_report(
                            store,
                            self.contract,
                            self.bootstrap,
                            _REPORT_BYTES,
                        )
                        _seal_completed(
                            store, self.contract, self.bootstrap
                        )
                with _for_run(replacement_root) as store:
                    with _stage_lock(store):
                        _publish_bootstrap(store, self.bootstrap)
                        _begin_stage(store, self.contract, self.bootstrap)

            stage_path = root / "stages" / evidence.STAGE_PROTOCOL_ID_V1
            replacement_stage = (
                replacement_root
                / "stages"
                / evidence.STAGE_PROTOCOL_ID_V1
            )
            displaced_stage = repository / "displaced-completed-stage"
            swapped = []

            def authenticate_then_swap(_repository, _store):
                stage_path.rename(displaced_stage)
                replacement_stage.rename(stage_path)
                swapped.append(True)
                return copy.deepcopy(self.bootstrap)

            with _synthetic_report_boundary(), mock.patch.object(
                stage, "_require_runtime_bindings_v1"
            ), mock.patch.object(
                stage, "_repository_path_v1", return_value=repository
            ), mock.patch.object(
                stage, "_validate_runtime_origins_v1"
            ), mock.patch.object(
                stage,
                "_authenticate_current_source_v1",
                return_value=copy.deepcopy(self.closure),
            ), mock.patch.object(
                stage,
                "_validate_recorded_bootstrap_v1",
                side_effect=authenticate_then_swap,
            ), mock.patch.object(
                stage, "_RESEAL_PRODUCTION_CLOSURE_V1"
            ), mock.patch.object(
                census, "build_static_census_v1", poison_builder
            ), mock.patch.object(
                stage, "_BUILD_CENSUS_V1", poison_builder
            ):
                with self.assertRaisesRegex(
                    evidence.StaticCensusEvidenceIntegrityError,
                    "recovery failed closed",
                ):
                    stage._run_static_census_stage_impl_v1(str(repository))
            self.assertEqual(swapped, [True])
            poison_builder.assert_not_called()
            self.assertTrue((root / "contradiction.json").is_file())
            self.assertFalse((stage_path / "orphaned.json").exists())
            self.assertFalse((stage_path / "terminal-seal.json").exists())
            self.assertTrue((displaced_stage / "terminal-seal.json").is_file())

    def test_prior_completed_catalog_cannot_rollback_before_existing_scan(self):
        calculate = mock.Mock(
            side_effect=AssertionError("catalog rollback reached calculation")
        )
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory).resolve()
            root = repository / evidence.EVIDENCE_ROOT_RELATIVE_V1
            root.parent.mkdir(parents=True)
            with _synthetic_report_boundary():
                with _for_run(root) as store:
                    with _stage_lock(store):
                        _publish_bootstrap(store, self.bootstrap)
                        _begin_stage(store, self.contract, self.bootstrap)
                        report_receipt = _publish_report(
                            store,
                            self.contract,
                            self.bootstrap,
                            _REPORT_BYTES,
                        )
                        _seal_completed(
                            store,
                            self.contract,
                            self.bootstrap,
                            _REPORT_BYTES,
                            report_receipt[1],
                        )

            stage_path = root / "stages" / evidence.STAGE_PROTOCOL_ID_V1
            displaced_stage = repository / "displaced-prior-completed-stage"
            with _synthetic_report_boundary(), _for_run(root) as store:
                with _stage_lock(store):
                    expected_catalog = store.scan_fixed_catalog()
                    stage_path.rename(displaced_stage)
                    with mock.patch.object(
                        stage,
                        "_authenticate_current_source_v1",
                        return_value=copy.deepcopy(self.closure),
                    ), mock.patch.object(
                        stage, "_RESEAL_PRODUCTION_CLOSURE_V1"
                    ), mock.patch.object(
                        stage, "_calculate_and_seal_v1", calculate
                    ):
                        with self.assertRaisesRegex(
                            evidence.StaticCensusEvidenceIntegrityError,
                            "recovery failed closed",
                        ):
                            stage._run_existing_with_held_lock_v1(
                                store,
                                self.contract,
                                repository,
                                _EVIDENCE_CAPABILITY,
                                expected_catalog,
                            )
            calculate.assert_not_called()
            self.assertTrue((root / "contradiction.json").is_file())
            self.assertFalse(stage_path.exists())
            self.assertTrue((displaced_stage / "terminal-seal.json").is_file())

    def test_existing_scan_failure_cannot_rebaseline_an_attempted_swap(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory).resolve()
            root = repository / evidence.EVIDENCE_ROOT_RELATIVE_V1
            replacement_root = repository / "replacement-evidence"
            root.parent.mkdir(parents=True)
            with _synthetic_report_boundary():
                with _for_run(root) as store:
                    with _stage_lock(store):
                        _publish_bootstrap(store, self.bootstrap)
                        _begin_stage(store, self.contract, self.bootstrap)
                        receipt = _publish_report(
                            store,
                            self.contract,
                            self.bootstrap,
                            _REPORT_BYTES,
                        )
                        _seal_completed(
                            store,
                            self.contract,
                            self.bootstrap,
                            _REPORT_BYTES,
                            receipt[1],
                        )
                with _for_run(replacement_root) as replacement_store:
                    with _stage_lock(replacement_store):
                        _publish_bootstrap(
                            replacement_store, self.bootstrap
                        )
                        _begin_stage(
                            replacement_store,
                            self.contract,
                            self.bootstrap,
                        )

            stage_path = root / "stages" / evidence.STAGE_PROTOCOL_ID_V1
            replacement_stage = (
                replacement_root
                / "stages"
                / evidence.STAGE_PROTOCOL_ID_V1
            )
            displaced_stage = repository / "displaced-scan-completed-stage"
            real_scan = evidence._StaticCensusEvidenceStore.scan_fixed_catalog
            first_scan = True

            def swap_then_fail_scan(store):
                nonlocal first_scan
                if first_scan:
                    first_scan = False
                    stage_path.rename(displaced_stage)
                    replacement_stage.rename(stage_path)
                    raise evidence.StaticCensusEvidenceIntegrityError(
                        "synthetic catalog binding drift"
                    )
                return real_scan(store)

            with _synthetic_report_boundary(), _for_run(root) as store:
                with _stage_lock(store), mock.patch.object(
                    stage,
                    "_authenticate_current_source_v1",
                    return_value=copy.deepcopy(self.closure),
                ), mock.patch.object(
                    stage, "_RESEAL_PRODUCTION_CLOSURE_V1"
                ), mock.patch.object(
                    evidence._StaticCensusEvidenceStore,
                    "scan_fixed_catalog",
                    swap_then_fail_scan,
                ):
                    with self.assertRaisesRegex(
                        evidence.StaticCensusEvidenceIntegrityError,
                        "recovery failed closed",
                    ):
                        stage._run_existing_with_held_lock_v1(
                            store,
                            self.contract,
                            repository,
                            _EVIDENCE_CAPABILITY,
                        )
            self.assertTrue((root / "contradiction.json").is_file())
            self.assertFalse((stage_path / "orphaned.json").exists())
            self.assertFalse((stage_path / "terminal-seal.json").exists())
            self.assertTrue((displaced_stage / "terminal-seal.json").is_file())

    def test_reported_recovery_completes_from_stored_bytes_without_builder(self):
        poison_builder = mock.Mock(
            side_effect=AssertionError("recover called the census builder")
        )
        reseal = mock.Mock()
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory).resolve()
            root = repository / evidence.EVIDENCE_ROOT_RELATIVE_V1
            root.parent.mkdir(parents=True)
            with _synthetic_report_boundary():
                with _for_run(root) as store:
                    with _stage_lock(store):
                        _publish_bootstrap(store, self.bootstrap)
                        _begin_stage(
                            store, self.contract, self.bootstrap
                        )
                        _publish_report(
                            store,
                            self.contract,
                            self.bootstrap,
                            _REPORT_BYTES,
                        )

                with mock.patch.object(
                    stage, "_require_runtime_bindings_v1"
                ), mock.patch.object(
                    stage, "_repository_path_v1", return_value=repository
                ), mock.patch.object(
                    stage, "_validate_runtime_origins_v1"
                ), mock.patch.object(
                    stage,
                    "_validate_recorded_bootstrap_v1",
                    return_value=copy.deepcopy(self.bootstrap),
                ), mock.patch.object(
                    stage,
                    "_authenticate_current_source_v1",
                    return_value=copy.deepcopy(self.closure),
                ), mock.patch.object(
                    stage, "_RECONSTRUCT_REPORT_V1", _fake_reconstruct
                ), mock.patch.object(
                    census,
                    "build_static_census_v1",
                    poison_builder,
                ), mock.patch.object(
                    stage, "_BUILD_CENSUS_V1", poison_builder
                ), mock.patch.object(
                    stage, "_RESEAL_PRODUCTION_CLOSURE_V1", reseal
                ), mock.patch.object(
                    census,
                    "advance_static_census_checkpoint_v1",
                    side_effect=AssertionError("recover advanced a checkpoint"),
                ):
                    observed = stage._recover_static_census_stage_impl_v1(
                        str(repository)
                    )
            self.assertEqual(observed["action"], "SEALED_REPORTED_COMPLETED")
            self.assertEqual(observed["lifecycle"], "COMPLETED")
            self.assertEqual(
                observed["report_summary"]["report_digest"], _REPORT_DIGEST
            )
            poison_builder.assert_not_called()
            self.assertEqual(reseal.call_count, 2)
            reseal.assert_has_calls(
                [mock.call(str(repository), self.closure)] * 2
            )

    def test_completed_recovery_reseals_before_verified_no_op(self):
        poison_builder = mock.Mock(
            side_effect=AssertionError("completed recovery called the builder")
        )
        reseal = mock.Mock()
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory).resolve()
            root = repository / evidence.EVIDENCE_ROOT_RELATIVE_V1
            root.parent.mkdir(parents=True)
            with _synthetic_report_boundary():
                with _for_run(root) as store:
                    with _stage_lock(store):
                        _publish_bootstrap(store, self.bootstrap)
                        _begin_stage(
                            store, self.contract, self.bootstrap
                        )
                        _publish_report(
                            store,
                            self.contract,
                            self.bootstrap,
                            _REPORT_BYTES,
                        )
                        _seal_completed(
                            store, self.contract, self.bootstrap
                        )

                with mock.patch.object(
                    stage, "_require_runtime_bindings_v1"
                ), mock.patch.object(
                    stage, "_repository_path_v1", return_value=repository
                ), mock.patch.object(
                    stage, "_validate_runtime_origins_v1"
                ), mock.patch.object(
                    stage,
                    "_validate_recorded_bootstrap_v1",
                    return_value=copy.deepcopy(self.bootstrap),
                ), mock.patch.object(
                    stage,
                    "_authenticate_current_source_v1",
                    return_value=copy.deepcopy(self.closure),
                ), mock.patch.object(
                    stage, "_RECONSTRUCT_REPORT_V1", _fake_reconstruct
                ), mock.patch.object(
                    evidence._StaticCensusEvidenceStore,
                    "read_report_bytes",
                    side_effect=AssertionError(
                        "stage reread report outside validated snapshot"
                    ),
                ), mock.patch.object(
                    census, "build_static_census_v1", poison_builder
                ), mock.patch.object(
                    stage, "_BUILD_CENSUS_V1", poison_builder
                ), mock.patch.object(
                    stage, "_RESEAL_PRODUCTION_CLOSURE_V1", reseal
                ):
                    observed = stage._recover_static_census_stage_impl_v1(
                        str(repository)
                    )
            self.assertEqual(observed["action"], "VERIFIED_NO_OP")
            self.assertEqual(observed["lifecycle"], "COMPLETED")
            poison_builder.assert_not_called()
            self.assertEqual(reseal.call_count, 2)
            reseal.assert_has_calls(
                [mock.call(str(repository), self.closure)] * 2
            )

    def test_invalid_terminal_reseals_before_contradiction_publication(self):
        events = []
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory).resolve()
            root = repository / evidence.EVIDENCE_ROOT_RELATIVE_V1
            root.parent.mkdir(parents=True)
            with _synthetic_report_boundary():
                with _for_run(root) as store:
                    with _stage_lock(store):
                        _publish_bootstrap(store, self.bootstrap)
                        _begin_stage(
                            store, self.contract, self.bootstrap
                        )
                        _publish_report(
                            store,
                            self.contract,
                            self.bootstrap,
                            _REPORT_BYTES,
                        )
                        _seal_completed(
                            store, self.contract, self.bootstrap
                        )

                terminal_path = (
                    root
                    / "stages"
                    / evidence.STAGE_PROTOCOL_ID_V1
                    / "terminal-seal.json"
                )
                terminal = json.loads(terminal_path.read_bytes())
                terminal["identity"] = "0" * 64
                terminal_path.chmod(0o600)
                terminal_path.write_bytes(_canonical(terminal))
                terminal_path.chmod(0o400)

                real_recover = stage._RECOVER_STAGE_LOCKED_V1

                def reseal(_repository, closure):
                    self.assertEqual(closure, self.closure)
                    events.append("reseal")

                def authenticate(_repository):
                    events.append("authenticate")
                    return copy.deepcopy(self.closure)

                def recover(*args):
                    events.append("recover")
                    return real_recover(*args)

                with mock.patch.object(
                    stage, "_require_runtime_bindings_v1"
                ), mock.patch.object(
                    stage, "_repository_path_v1", return_value=repository
                ), mock.patch.object(
                    stage, "_validate_runtime_origins_v1"
                ), mock.patch.object(
                    stage,
                    "_authenticate_current_source_v1",
                    side_effect=authenticate,
                ), mock.patch.object(
                    stage,
                    "_validate_recorded_bootstrap_v1",
                    return_value=copy.deepcopy(self.bootstrap),
                ), mock.patch.object(
                    stage, "_RESEAL_PRODUCTION_CLOSURE_V1", reseal
                ), mock.patch.object(
                    stage, "_RECOVER_STAGE_LOCKED_V1", recover
                ):
                    with self.assertRaisesRegex(
                        evidence.StaticCensusEvidenceIntegrityError,
                        "recovery failed closed",
                    ):
                        stage._recover_static_census_stage_impl_v1(
                            str(repository)
                        )
            self.assertEqual(events, ["authenticate", "reseal", "recover"])
            self.assertTrue((root / "contradiction.json").is_file())


class StaticCensusStageSurfaceTests(unittest.TestCase):
    def _copy_direct_launcher_repository(self, directory):
        repository = Path(directory).resolve() / "repository"
        package = repository / "src" / "parity_forge_universe"
        legacy = repository / "src" / "parity_forge"
        package.mkdir(parents=True)
        legacy.mkdir()
        source_package = Path(stage.__file__).resolve().parent
        for name in (
            "__init__.py",
            "initial_structure.py",
            "schema_v4_compiler.py",
            "static_census.py",
            "static_census_evidence.py",
            "static_census_protocol.py",
            "static_census_reconstruction.py",
            "static_census_stage.py",
            "typed_occupancy.py",
        ):
            shutil.copyfile(source_package / name, package / name)
        (repository / "experiments" / "runs").mkdir(parents=True)
        subprocess.run(
            ["/usr/bin/git", "init", "-q"],
            cwd=repository,
            check=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        subprocess.run(
            ["/usr/bin/git", "add", "--", "src"],
            cwd=repository,
            check=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        subprocess.run(
            [
                "/usr/bin/git",
                "-c",
                "user.name=Parity Forge Test",
                "-c",
                "user.email=parity-forge-test@example.invalid",
                "commit",
                "-q",
                "-m",
                "fixture",
            ],
            cwd=repository,
            check=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return repository

    def test_public_surface_cli_and_private_binding_are_fixed(self):
        self.assertFalse(
            hasattr(stage, "_EVIDENCE_MUTATION_CAPABILITY_V1")
        )
        self.assertFalse(
            hasattr(stage, "_CLAIM_EVIDENCE_MUTATION_CAPABILITY_V1")
        )
        for function in (
            stage.run_static_census_stage_v1,
            stage.recover_static_census_stage_v1,
        ):
            signature = inspect.signature(function)
            self.assertEqual(tuple(signature.parameters), ("repository",))
            self.assertIs(
                signature.parameters["repository"].default,
                inspect.Parameter.empty,
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
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                parser.parse_args(["resume", "--repository", "/fixed"])
        destinations = {
            action.dest for action in parser._actions if action.dest != "help"
        }
        self.assertEqual(destinations, {"command", "repository"})

        original = stage._run_static_census_stage_impl_v1
        with mock.patch.object(
            stage,
            "_run_static_census_stage_impl_v1",
            side_effect=AssertionError("rebound implementation ran"),
        ):
            with self.assertRaisesRegex(
                stage.StaticCensusStageError, "implementation binding"
            ):
                stage.run_static_census_stage_v1("/fixed")
        self.assertIsNotNone(original)

    def test_stage_has_no_resume_checkpoint_history_outcome_or_game_capability(self):
        source_path = Path(stage.__file__).resolve()
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.add(node.module)
        forbidden = (
            "agent",
            "candidate",
            "engine",
            "history",
            "play",
            "solver",
            "telemetry",
            "terminal",
        )
        self.assertFalse(
            {
                name
                for name in imported
                if any(fragment in name for fragment in forbidden)
            }
        )
        self.assertNotIn("advance_static_census_checkpoint_v1", source)
        self.assertNotIn("finalize_static_census_v1", source)
        attributes = [
            node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
        ]
        self.assertEqual(attributes.count("build_static_census_v1"), 2)
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        calculation_calls = [
            node
            for node in ast.walk(functions["_calculate_and_seal_v1"])
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_build"
        ]
        self.assertEqual(len(calculation_calls), 1)
        self.assertEqual(calculation_calls[0].args, [])
        self.assertEqual(calculation_calls[0].keywords, [])
        for name, function in functions.items():
            if "recover" not in name:
                continue
            forbidden_calls = [
                node
                for node in ast.walk(function)
                if isinstance(node, ast.Call)
                and (
                    isinstance(node.func, ast.Name)
                    and node.func.id == "_build"
                    or isinstance(node.func, ast.Attribute)
                    and node.func.attr == "build_static_census_v1"
                )
            ]
            self.assertEqual(forbidden_calls, [], name)

    def test_runtime_dependency_rebinding_fails_before_repository_or_stage_work(self):
        replacements = (
            (evidence, "_load_chain_snapshot_matching_catalog_v1"),
            (evidence, "_publish_report_v1"),
            (evidence, "_seal_completed_v1"),
            (evidence, "_recover_stage_locked_v1"),
            (protocol, "resolve_static_census_repository_v1"),
            (protocol, "authenticate_static_census_recovery_closure_v1"),
            (protocol, "StaticCensusStoredClosureIntegrityError"),
            (protocol, "reseal_static_census_production_closure_v1"),
            (reconstruction, "reconstruct_static_census_report_artifact_v1"),
            (census, "build_static_census_v1"),
        )
        for owner, name in replacements:
            with self.subTest(name=name), mock.patch.object(
                owner, name, mock.Mock()
            ):
                with self.assertRaisesRegex(
                    stage.StaticCensusStageError, "dependency binding"
                ):
                    stage.run_static_census_stage_v1("/fixed")

        for name in ("int", "len"):
            with self.subTest(name=name), mock.patch.object(
                stage, name, mock.Mock(), create=True
            ):
                with self.assertRaisesRegex(
                    stage.StaticCensusStageError, "builtin binding"
                ):
                    stage.run_static_census_stage_v1("/fixed")

    def test_public_wrapper_makes_closure_reseal_its_final_effect(self):
        events = []
        closure = {"fixture": "reviewed-production-closure"}

        def implementation(repository):
            events.append(("implementation", repository))
            return {
                stage._PUBLIC_RETURN_CLOSURE_KEY_V1: closure,
                "action": "FIXTURE",
            }

        def runtime_guard():
            events.append(("runtime",))

        def source_runtime_guard():
            events.append(("source-runtime",))

        def launcher_guard(repository, command):
            events.append(("launcher", repository, command))

        def reseal(repository, observed_closure):
            events.append(("reseal", repository, observed_closure))

        name = "_test_terminal_return_impl_v1"
        with mock.patch.object(
            stage, name, implementation, create=True
        ), mock.patch.object(
            stage, "_require_runtime_bindings_v1", runtime_guard
        ):
            invoke = stage._fixed_public_entrypoint(
                implementation,
                name,
                "recover",
                runtime_guard,
                source_runtime_guard,
                launcher_guard,
                reseal,
                stage._PUBLIC_RETURN_CLOSURE_KEY_V1,
            )
            observed = invoke("/fixed")
        self.assertEqual(observed, {"action": "FIXTURE"})
        self.assertEqual(events[-1], ("reseal", "/fixed", closure))
        self.assertEqual(
            events[:-1],
            [
                ("runtime",),
                ("source-runtime",),
                ("launcher", "/fixed", "recover"),
                ("implementation", "/fixed"),
                ("runtime",),
                ("source-runtime",),
                ("launcher", "/fixed", "recover"),
            ],
        )

    def test_guard_expectations_cannot_be_rebound_with_the_target(self):
        forged = mock.Mock()
        with mock.patch.object(
            stage, "_run_existing_root_v1", forged
        ), mock.patch.object(stage, "_STAGE_LOCAL_BINDINGS_V1", ()):
            with self.assertRaisesRegex(
                stage.StaticCensusStageError, "binding catalog"
            ):
                stage.run_static_census_stage_v1("/fixed")
        forged.assert_not_called()

        with mock.patch.object(
            evidence, "_open_recovery_store_v1", forged
        ), mock.patch.object(
            stage, "_OPEN_RECOVERY_STORE_V1", forged
        ), mock.patch.object(
            stage, "_STAGE_DEPENDENCY_IDENTITY_BINDINGS_V1", ()
        ):
            with self.assertRaisesRegex(
                stage.StaticCensusStageError, "binding catalog"
            ):
                stage.run_static_census_stage_v1("/fixed")
        forged.assert_not_called()

    def test_stage_source_and_loader_origin_are_bound(self):
        repository = Path(stage.__file__).resolve().parents[2]
        with self.assertRaisesRegex(
            stage.StaticCensusStageError, "stage origin"
        ):
            stage._validate_runtime_origins_v1(
                repository,
                _stage_file="/tmp/forged/static_census_stage.py",
            )
        with mock.patch.object(
            stage, "__file__", "/tmp/forged/static_census_stage.py"
        ):
            with self.assertRaisesRegex(
                stage.StaticCensusStageError, "stage constant"
            ):
                stage.run_static_census_stage_v1("/fixed")

        with mock.patch.object(
            stage._INITIAL_MODULE_V1,
            "__file__",
            "/tmp/forged/initial_structure.py",
        ):
            with self.assertRaisesRegex(
                stage.StaticCensusStageError, "module origin"
            ):
                stage._validate_runtime_origins_v1(repository)

    def test_public_stage_requires_an_empty_isolated_pycache_boundary(self):
        with self.assertRaisesRegex(
            stage.StaticCensusStageError, "source-only isolated interpreter"
        ):
            stage.recover_static_census_stage_v1("/fixed")

        repository = Path(stage.__file__).resolve().parents[2]
        source = repository / "src"
        script = """
import sys
sys.path.append({!r})
from parity_forge_universe import static_census_stage as stage
stage._require_source_only_runtime_v1()
stage._validate_runtime_origins_v1(stage.Path({!r}))
print("SOURCE_ONLY_OK")
""".format(str(source), str(repository))
        with tempfile.TemporaryDirectory() as cache:
            process = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-B",
                    "-S",
                    "-X",
                    "pycache_prefix=" + cache,
                    "-c",
                    script,
                ],
                cwd=repository,
                check=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(process.stdout.strip(), "SOURCE_ONLY_OK")
            self.assertEqual(list(Path(cache).iterdir()), [])

        with tempfile.TemporaryDirectory() as cache:
            (Path(cache) / "hostile.pyc").write_bytes(b"not bytecode")
            process = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-B",
                    "-S",
                    "-X",
                    "pycache_prefix=" + cache,
                    "-c",
                    script,
                ],
                cwd=repository,
                check=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertNotEqual(process.returncode, 0)
            self.assertIn("pycache prefix is not empty", process.stderr)

    def test_trusted_direct_launcher_recovers_missing_temp_root_without_writes(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as cache:
            repository = self._copy_direct_launcher_repository(directory)
            stage_file = (
                repository
                / "src"
                / "parity_forge_universe"
                / "static_census_stage.py"
            )
            process = subprocess.run(
                [
                    "/usr/bin/python3",
                    "-I",
                    "-B",
                    "-S",
                    "-X",
                    "pycache_prefix=" + cache,
                    str(stage_file),
                    "recover",
                    "--repository",
                    str(repository),
                ],
                cwd=repository,
                check=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(
                json.loads(process.stdout),
                {
                    "action": "NO_EVIDENCE",
                    "lifecycle": None,
                    "stage_id": evidence.STAGE_ID_V1,
                    "terminal_seal_or_null": None,
                },
            )
            self.assertFalse(
                (repository / evidence.EVIDENCE_ROOT_RELATIVE_V1).exists()
            )
            self.assertEqual(list(Path(cache).iterdir()), [])

    def test_direct_launcher_rejects_ignored_bytecode_before_import(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as cache:
            repository = self._copy_direct_launcher_repository(directory)
            (repository / "src" / "hashlib.pyc").write_bytes(b"ignored shadow")
            stage_file = (
                repository
                / "src"
                / "parity_forge_universe"
                / "static_census_stage.py"
            )
            process = subprocess.run(
                [
                    "/usr/bin/python3",
                    "-I",
                    "-B",
                    "-S",
                    "-X",
                    "pycache_prefix=" + cache,
                    str(stage_file),
                    "--help",
                ],
                cwd=repository,
                check=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertNotEqual(process.returncode, 0)
            self.assertIn("unreviewed import capability", process.stderr)

    def test_direct_launcher_rejects_capability_affecting_interpreter_options(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = self._copy_direct_launcher_repository(directory)
            stage_file = (
                repository
                / "src"
                / "parity_forge_universe"
                / "static_census_stage.py"
            )
            for extra in (("-X", "faulthandler"), ("-W", "ignore")):
                with self.subTest(extra=extra), tempfile.TemporaryDirectory() as cache:
                    process = subprocess.run(
                        [
                            "/usr/bin/python3",
                            "-I",
                            "-B",
                            "-S",
                            *extra,
                            "-X",
                            "pycache_prefix=" + cache,
                            str(stage_file),
                            "--help",
                        ],
                        cwd=repository,
                        check=False,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                    self.assertNotEqual(process.returncode, 0)
                    self.assertIn("fixed launcher", process.stderr)

    def test_direct_launcher_detects_source_change_during_import(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as cache:
            repository = self._copy_direct_launcher_repository(directory)
            package = repository / "src" / "parity_forge_universe"
            initializer = package / "__init__.py"
            with initializer.open("a", encoding="utf-8") as stream:
                stream.write(
                    "\nwith open(__file__.rsplit('/', 1)[0] + "
                    "'/typed_occupancy.py', 'ab') as _stream:\n"
                    "    _stream.write(b'\\n')\n"
                )
            stage_file = package / "static_census_stage.py"
            process = subprocess.run(
                [
                    "/usr/bin/python3",
                    "-I",
                    "-B",
                    "-S",
                    "-X",
                    "pycache_prefix=" + cache,
                    str(stage_file),
                    "--help",
                ],
                cwd=repository,
                check=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertNotEqual(process.returncode, 0)
            self.assertIn("source changed during import", process.stderr)

    def test_direct_launcher_detects_ancestor_rename_and_restore_during_import(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as cache:
            repository = self._copy_direct_launcher_repository(directory)
            package = repository / "src" / "parity_forge_universe"
            initializer = package / "__init__.py"
            moved = repository.with_name(repository.name + "-moved")
            with initializer.open("a", encoding="utf-8") as stream:
                stream.write(
                    "\nimport os as _stage_test_os\n"
                    "_stage_test_os.rename({!r}, {!r})\n"
                    "_stage_test_os.rename({!r}, {!r})\n".format(
                        str(repository),
                        str(moved),
                        str(moved),
                        str(repository),
                    )
                )
            stage_file = package / "static_census_stage.py"
            process = subprocess.run(
                [
                    "/usr/bin/python3",
                    "-I",
                    "-B",
                    "-S",
                    "-X",
                    "pycache_prefix=" + cache,
                    str(stage_file),
                    "--help",
                ],
                cwd=repository,
                check=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertNotEqual(process.returncode, 0)
            self.assertIn(
                "source ancestry changed during source loading",
                process.stderr,
            )

    def test_imported_isolated_prelude_cannot_enter_public_stage(self):
        repository = Path(stage.__file__).resolve().parents[2]
        source = repository / "src"
        script = """
import sys
sys.path.append({!r})
from parity_forge_universe import static_census_stage as stage
try:
    stage.recover_static_census_stage_v1("/fixed")
except stage.StaticCensusStageError as error:
    print(str(error))
else:
    raise AssertionError("arbitrary prelude entered the public stage")
""".format(str(source))
        with tempfile.TemporaryDirectory() as cache:
            process = subprocess.run(
                [
                    "/usr/bin/python3",
                    "-I",
                    "-B",
                    "-S",
                    "-X",
                    "pycache_prefix=" + cache,
                    "-c",
                    script,
                ],
                cwd=repository,
                check=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertIn("trusted direct source launcher", process.stdout)

    def test_fresh_host_process_is_the_explicit_launcher_trust_boundary(self):
        source = Path(stage.__file__).read_text(encoding="utf-8")
        self.assertIn(
            "root of trust is a host selecting the independently reviewed source",
            source,
        )
        tree = ast.parse(source)
        dynamic_calls = [
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"__import__", "eval", "exec"}
        ]
        self.assertEqual(dynamic_calls, [])

    def test_ordinary_exec_prelude_cannot_impersonate_the_direct_script_frame(self):
        repository = Path(stage.__file__).resolve().parents[2]
        stage_file = Path(stage.__file__).resolve()
        script = """
import sys
from importlib.machinery import SourceFileLoader
stage_file = {!r}
sys.argv = [stage_file, "recover", "--repository", {!r}]
namespace = globals()
namespace["__file__"] = stage_file
namespace["__loader__"] = SourceFileLoader("__main__", stage_file)
namespace["__package__"] = ""
with open(stage_file, "r", encoding="utf-8") as stream:
    source = stream.read()
exec(compile(source, stage_file, "exec"), namespace)
""".format(str(stage_file), str(repository))
        with tempfile.TemporaryDirectory() as cache:
            process = subprocess.run(
                [
                    "/usr/bin/python3",
                    "-I",
                    "-B",
                    "-S",
                    "-X",
                    "pycache_prefix=" + cache,
                    "-c",
                    script,
                ],
                cwd=repository,
                check=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertNotEqual(process.returncode, 0)
            self.assertIn("direct script has a Python caller", process.stderr)

    def test_prefixed_root_code_cannot_match_the_canonical_stage_source(self):
        repository = Path(stage.__file__).resolve().parents[2]
        stage_file = Path(stage.__file__).resolve()
        source = stage_file.read_text(encoding="utf-8")
        marker = "from __future__ import annotations\n"
        prefix = """
import sys
from importlib.machinery import SourceFileLoader
__file__ = {!r}
__loader__ = SourceFileLoader("__main__", __file__)
__package__ = ""
sys.argv = [__file__, "recover", "--repository", {!r}]
""".format(str(stage_file), str(repository))
        forged_source = source.replace(marker, marker + prefix, 1)
        with tempfile.TemporaryDirectory() as cache:
            process = subprocess.run(
                [
                    "/usr/bin/python3",
                    "-I",
                    "-B",
                    "-S",
                    "-X",
                    "pycache_prefix=" + cache,
                    "-c",
                    forged_source,
                ],
                cwd=repository,
                check=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertNotEqual(process.returncode, 0)
            self.assertIn(
                "direct entry code differs from canonical source",
                process.stderr,
            )

    def test_isolated_import_does_not_load_legacy_package(self):
        repository = Path(stage.__file__).resolve().parents[2]
        script = """
import json
import sys
import parity_forge_universe.static_census_stage
print(json.dumps(sorted(sys.modules)))
"""
        process = subprocess.run(
            [sys.executable, "-I", "-c", script],
            cwd=repository,
            env={"PYTHONPATH": str(repository / "src")},
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if process.returncode != 0:
            # Isolated mode ignores PYTHONPATH; use one explicit, fixed source
            # insertion while retaining a clean interpreter module table.
            isolated = """
import json
import sys
sys.path.insert(0, {!r})
import parity_forge_universe.static_census_stage
print(json.dumps(sorted(sys.modules)))
""".format(str(repository / "src"))
            process = subprocess.run(
                [sys.executable, "-I", "-c", isolated],
                cwd=repository,
                check=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        modules = json.loads(process.stdout)
        self.assertNotIn("parity_forge", modules)
        self.assertFalse(
            any(
                name.startswith("parity_forge.")
                or name.endswith(".engine")
                or name.endswith(".play")
                for name in modules
            )
        )


if __name__ == "__main__":
    unittest.main()
