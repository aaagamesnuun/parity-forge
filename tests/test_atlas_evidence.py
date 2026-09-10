from __future__ import annotations

import ast
import contextlib
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from parity_forge import atlas_protocol
import parity_forge.atlas_evidence as atlas_evidence
from parity_forge.atlas_evidence import (
    BodyRef,
    ChainSnapshot,
    EvidenceConflictError,
    EvidenceIntegrityError,
    EvidenceLockError,
    ImmutableEvidenceStore,
    LedgerSpec,
    ProductionClosure,
    StageContract,
    begin_stage,
    block_stage,
    build_attempt,
    build_blocked,
    build_completed,
    build_failure,
    build_orphaned,
    build_production_closure,
    build_reservation,
    build_terminal_seal,
    canonical_body_ref,
    canonical_json_bytes,
    capture_clean_head,
    domain_identity,
    extract_stage_contract,
    extract_recovery_stage_contract,
    load_canonical_json_bytes,
    publish_manifest_freeze,
    publish_manifest_bootstrap,
    publish_stage_completion_evidence,
    read_authenticated_stage_inputs,
    read_manifest_freeze,
    reconcile_status_ledger,
    recover_stage,
    reseal_production_closure,
    seal_completed_stage,
    validate_chain_snapshot,
    verify_commit_relation,
)


MANIFEST_ID = "OUTCOME_FREE_DEVELOPMENT_MANIFEST"
EXACT_ID = "EXACT_ALL_288"
RANDOM_ID = "RANDOM_ALL_18432_GAMES"
DEPTH_ID = "TERMINAL_DEPTH1_ALL_18432_GAMES"
TELEMETRY_ID = "REPLAY_TELEMETRY_COMPLETE_TRACES_ONLY"
ASSESSMENT_ID = "ASSESSMENT_AND_INSPECTION"

STAGE_PROTOCOL_IDS = {
    MANIFEST_ID: "plan0013-atlas-development-manifest-v1",
    EXACT_ID: "plan0013-atlas-development-exact-v1",
    RANDOM_ID: "plan0013-atlas-development-random-v1",
    DEPTH_ID: "plan0013-atlas-development-terminal-depth1-v1",
    TELEMETRY_ID: "plan0013-atlas-development-telemetry-v1",
    ASSESSMENT_ID: "plan0013-atlas-development-assessment-v1",
}

PRODUCTION_KEYS = (
    "manifest_experiment_plan_sha256",
    "manifest_protocol_blob_identity",
    "ordered_entrypoint_paths",
    "ordered_file_records",
    "source_commit",
    "source_tree",
    "stage_id",
)
RESERVATION_KEYS = (
    "evidence_protocol_id",
    "manifest_evidence_ref_or_null",
    "manifest_experiment_plan_sha256",
    "ordered_parent_terminal_seals",
    "production_closure_root",
    "protocol_id",
    "protocol_root",
    "stage_id",
    "stage_protocol_id",
)
ATTEMPT_KEYS = (
    "attempt_index",
    "production_closure_root",
    "reservation_id",
    "source_commit",
    "source_tree",
)
BLOCKED_KEYS = (
    "evidence_protocol_id",
    "failed_prerequisite_stage_id",
    "manifest_evidence_ref",
    "prerequisite_terminal_seal",
    "production_closure_root",
    "protocol_id",
    "protocol_root",
    "stage_id",
    "stage_protocol_id",
)
ORPHANED_KEYS = (
    "attempt_id_or_null",
    "orphan_reason",
    "partial_evidence_root_or_null",
    "reservation_id",
    "stage_id",
    "stage_protocol_id",
)
TERMINAL_KEYS = (
    "attempt_id_or_null",
    "blocked_id_or_null",
    "completed_root_or_null",
    "failure_root_or_null",
    "lifecycle",
    "orphaned_id_or_null",
    "partial_evidence_root_or_null",
    "reservation_id_or_null",
    "stage_id",
    "stage_protocol_id",
)

SCHEMA_KEYS = {
    "production_closure_root": PRODUCTION_KEYS,
    "stage_reservation_id": RESERVATION_KEYS,
    "stage_attempt_id": ATTEMPT_KEYS,
    "stage_blocked_id": BLOCKED_KEYS,
    "stage_orphaned_id": ORPHANED_KEYS,
    "stage_terminal_seal": TERMINAL_KEYS,
}
SCHEMA_DOMAINS = {
    "production_closure_root": atlas_protocol._PRODUCTION_CLOSURE_ROOT_DOMAIN_V1,
    "stage_reservation_id": atlas_protocol._STAGE_RESERVATION_ID_DOMAIN_V1,
    "stage_attempt_id": atlas_protocol._STAGE_ATTEMPT_ID_DOMAIN_V1,
    "stage_blocked_id": atlas_protocol._STAGE_BLOCKED_ID_DOMAIN_V1,
    "stage_orphaned_id": atlas_protocol._STAGE_ORPHANED_ID_DOMAIN_V1,
    "stage_terminal_seal": atlas_protocol._STAGE_TERMINAL_SEAL_DOMAIN_V1,
}


def make_contract(
    stage_id=MANIFEST_ID,
    *,
    parents=(),
    predicates=(),
    required_paths=("src/parity_forge/atlas_protocol.py",),
    forbidden_paths=(),
    checkpoint_commit="1" * 40,
    checkpoint_paths=(),
    stage_index=0,
):
    return StageContract(
        stage_index=stage_index,
        stage_id=stage_id,
        stage_protocol_id=STAGE_PROTOCOL_IDS[stage_id],
        prerequisite_stage_id=None if not parents else parents[-1],
        prerequisite_gate=None if not parents else "FROZEN_GATE",
        required_parent_terminal_stage_ids=tuple(parents),
        required_parent_terminal_predicates=tuple(predicates),
        required_known_paths=tuple(required_paths),
        forbidden_known_paths=tuple(forbidden_paths),
        checkpoint_commit=checkpoint_commit,
        checkpoint_paths=tuple(checkpoint_paths),
        reservation_scope="FIXED_SCOPE",
        reservation_timing="BEFORE_CAPABILITY",
        attempt_timing="AFTER_RESERVATION_BEFORE_CAPABILITY",
        capability_boundary="SYNTHETIC_TEST_ONLY",
        completion_gate="FULL_FIXED_LEDGER",
        protocol_id=atlas_protocol.ATLAS_PROTOCOL_ID_V1,
        protocol_root="a" * 64,
        evidence_protocol_id="plan0013-atlas-development-evidence-v1",
        evidence_protocol_version=1,
        identity_domains=tuple(SCHEMA_DOMAINS.items()),
        identity_payload_keys=tuple(SCHEMA_KEYS.items()),
    )


def make_closure(contract, plan=b"plan", source_commit="2" * 40, source_tree="3" * 40):
    raw = b"protocol"
    record = {
        "byte_count": len(raw),
        "current_sha256": hashlib.sha256(raw).hexdigest(),
        "path": "src/parity_forge/atlas_protocol.py",
        "source_commit_blob_sha1": "4" * 40,
    }
    payload = {
        "manifest_experiment_plan_sha256": hashlib.sha256(plan).hexdigest(),
        "manifest_protocol_blob_identity": record["source_commit_blob_sha1"],
        "ordered_entrypoint_paths": ["src/parity_forge/atlas_protocol.py"],
        "ordered_file_records": [record],
        "source_commit": source_commit,
        "source_tree": source_tree,
        "stage_id": contract.stage_id,
    }
    return ProductionClosure(
        domain_identity(contract.identity_domain("production_closure_root"), payload),
        payload,
    )


def completed_manifest_chain(plan=b"plan"):
    contract = make_contract()
    closure = make_closure(contract, plan)
    reservation = build_reservation(contract, closure, ())
    attempt = build_attempt(contract, reservation)
    completed = build_completed(contract, reservation, attempt, {"ok": True})
    terminal = build_terminal_seal(
        contract,
        "COMPLETED",
        reservation=reservation,
        attempt=attempt,
        completed=completed,
    )
    return contract, closure, reservation, attempt, completed, terminal


def publish_synthetic_completed_manifest(store, protocol, plan=b"plan"):
    contracts = tuple(
        extract_stage_contract(protocol, stage_id)
        for stage_id in protocol["stage_sequence"]
    )
    closures = tuple(make_closure(contract, plan) for contract in contracts)
    manifest_contract = contracts[0]
    reservation = build_reservation(manifest_contract, closures[0], ())
    attempt = build_attempt(manifest_contract, reservation)
    with store.stage_lock(manifest_contract.stage_protocol_id):
        publish_manifest_bootstrap(
            store, manifest_contract, protocol, closures, plan
        )
        store.publish_json(
            manifest_contract.stage_protocol_id, "reservation", reservation
        )
        store.publish_json(
            manifest_contract.stage_protocol_id, "attempt", attempt
        )
        refs = publish_manifest_freeze(
            store,
            manifest_contract,
            protocol,
            {"development_definitions": []},
            closures,
            plan,
        )
        completed = build_completed(
            manifest_contract,
            reservation,
            attempt,
            {
                "artifact_refs_or_null": refs.as_dict(),
                "summary": {"fixture": "completed-manifest"},
            },
        )
        terminal = build_terminal_seal(
            manifest_contract,
            "COMPLETED",
            reservation=reservation,
            attempt=attempt,
            completed=completed,
        )
        store.publish_json(
            manifest_contract.stage_protocol_id, "completed", completed
        )
        store.publish_json(
            manifest_contract.stage_protocol_id, "terminal_seal", terminal
        )
    return {
        "attempt": attempt,
        "closures": closures,
        "completed": completed,
        "contracts": contracts,
        "refs": refs,
        "reservation": reservation,
        "terminal": terminal,
    }


def publish_completed_outcome_chain(
    store,
    contract,
    reservation,
    attempt,
    refs,
    *,
    summary=None,
):
    """Publish a synthetic COMPLETED chain after its referenced bodies exist."""

    completed = build_completed(
        contract,
        reservation,
        attempt,
        {
            "artifact_refs_or_null": refs.as_dict(),
            "summary": {} if summary is None else summary,
        },
    )
    terminal = build_terminal_seal(
        contract,
        "COMPLETED",
        reservation=reservation,
        attempt=attempt,
        completed=completed,
    )
    store.publish_json(contract.stage_protocol_id, "completed", completed)
    store.publish_json(contract.stage_protocol_id, "terminal_seal", terminal)
    return {
        "attempt": attempt,
        "completed": completed,
        "reservation": reservation,
        "terminal": terminal,
    }


def publish_synthetic_assessment_chain(
    store,
    fixture,
    summary,
    *,
    publish_completed=True,
    publish_terminal=True,
):
    """Publish an assessment chain with structurally valid embedded parents."""

    terminals = {MANIFEST_ID: fixture["terminal"]}
    for contract, closure in zip(
        fixture["contracts"][1:5], fixture["closures"][1:5]
    ):
        parents = tuple(
            terminals[parent]
            for parent in contract.required_parent_terminal_stage_ids
        )
        reservation = build_reservation(contract, closure, parents)
        attempt = build_attempt(contract, reservation)
        completed = build_completed(
            contract,
            reservation,
            attempt,
            {"artifact_refs_or_null": None, "summary": {}},
        )
        terminals[contract.stage_id] = build_terminal_seal(
            contract,
            "COMPLETED",
            reservation=reservation,
            attempt=attempt,
            completed=completed,
        )
    contract = fixture["contracts"][5]
    parents = tuple(
        terminals[parent]
        for parent in contract.required_parent_terminal_stage_ids
    )
    reservation = build_reservation(contract, fixture["closures"][5], parents)
    attempt = build_attempt(contract, reservation)
    completed = build_completed(
        contract,
        reservation,
        attempt,
        {"artifact_refs_or_null": None, "summary": summary},
    )
    terminal = build_terminal_seal(
        contract,
        "COMPLETED",
        reservation=reservation,
        attempt=attempt,
        completed=completed,
    )
    store.publish_json(contract.stage_protocol_id, "reservation", reservation)
    store.publish_json(contract.stage_protocol_id, "attempt", attempt)
    if publish_completed:
        store.publish_json(contract.stage_protocol_id, "completed", completed)
    if publish_completed and publish_terminal:
        store.publish_json(contract.stage_protocol_id, "terminal_seal", terminal)
    return {
        "attempt": attempt,
        "completed": completed,
        "contract": contract,
        "reservation": reservation,
        "terminal": terminal,
    }


def exact_contract(checkpoint_commit="1" * 40, required_paths=None):
    return make_contract(
        EXACT_ID,
        parents=(MANIFEST_ID,),
        predicates=((MANIFEST_ID, "COMPLETED_VALID"),),
        checkpoint_commit=checkpoint_commit,
        required_paths=(
            ("src/parity_forge/atlas_protocol.py",)
            if required_paths is None
            else required_paths
        ),
        stage_index=1,
    )


def run_git(repository, *arguments):
    return subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    ).stdout.decode("utf-8").strip()


def make_git_repository(root):
    repository = Path(root) / "repo"
    (repository / "src/parity_forge").mkdir(parents=True)
    files = {
        "src/parity_forge/__init__.py": "\n",
        "src/parity_forge/dsl.py": "VALUE = 1\n",
        "src/parity_forge/engine.py": "from .dsl import VALUE\n",
        "src/parity_forge/atlas_protocol.py": "from . import dsl\n",
        "src/parity_forge/entry.py": (
            "from parity_forge import atlas_protocol\nfrom .engine import VALUE\n"
        ),
        "docs/plans/active/0013-six-family-development-atlas.md": "synthetic plan\n",
    }
    for relative, text in files.items():
        path = repository / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    run_git(repository, "init", "-q")
    run_git(repository, "config", "user.email", "test@example.com")
    run_git(repository, "config", "user.name", "Atlas Evidence Test")
    run_git(repository, "add", ".")
    run_git(repository, "commit", "-qm", "checkpoint")
    return repository, run_git(repository, "rev-parse", "HEAD")


def synthetic_protocol():
    stage_ids = (
        MANIFEST_ID,
        EXACT_ID,
        RANDOM_ID,
        DEPTH_ID,
        TELEMETRY_ID,
        ASSESSMENT_ID,
    )
    parent_map = {
        MANIFEST_ID: (),
        EXACT_ID: (MANIFEST_ID,),
        RANDOM_ID: (MANIFEST_ID, EXACT_ID),
        DEPTH_ID: (MANIFEST_ID, EXACT_ID, RANDOM_ID),
        TELEMETRY_ID: (MANIFEST_ID, EXACT_ID, RANDOM_ID, DEPTH_ID),
        ASSESSMENT_ID: (MANIFEST_ID, EXACT_ID, RANDOM_ID, DEPTH_ID, TELEMETRY_ID),
    }
    stages = []
    for index, stage_id in enumerate(stage_ids):
        parents = parent_map[stage_id]
        predicate = "TERMINAL_SEAL_PRESENT" if stage_id in (TELEMETRY_ID, ASSESSMENT_ID) else "COMPLETED_VALID"
        stages.append(
            {
                "attempt_timing": "AFTER_RESERVATION",
                "capability_boundary": "SYNTHETIC",
                "completion_gate": "COMPLETE",
                "prerequisite_gate": None if not parents else "FROZEN",
                "prerequisite_stage_id": None if not parents else parents[-1],
                "required_parent_terminal_predicates": {
                    parent: ("COMPLETED_VALID" if parent == MANIFEST_ID else predicate)
                    for parent in parents
                },
                "required_parent_terminal_stage_ids": list(parents),
                "reservation_scope": "FIXED",
                "reservation_timing": "BEFORE_CAPABILITY",
                "source_closure_policy": {
                    "checkpoint_blob_equivalence": {
                        "paths": [],
                        "reference_commit": "1" * 40,
                    },
                    "forbidden_known_paths": [],
                    "required_known_paths": ["src/parity_forge/atlas_protocol.py"],
                    "stage_id": stage_id,
                },
                "stage_id": stage_id,
                "stage_index": index,
                "stage_protocol_id": STAGE_PROTOCOL_IDS[stage_id],
            }
        )
    schemas = {
        name: {"domain_hex": SCHEMA_DOMAINS[name].hex(), "payload_keys": list(keys)}
        for name, keys in SCHEMA_KEYS.items()
    }
    unsigned = {
        "manifest_and_run_provenance": {
            "artifact_identity_schemas": schemas,
            "evidence_protocol_id": "plan0013-atlas-development-evidence-v2",
            "evidence_protocol_version": 2,
            "outcome_free_manifest_bootstrap": {
                "identity_schema": {
                    "domain_hex": (
                        atlas_protocol._MANIFEST_BOOTSTRAP_ROOT_DOMAIN_V1.hex()
                    ),
                    "payload_keys": [
                        "artifact_type",
                        "evidence_protocol_id",
                        "experiment_plan_ref",
                        "production_closure_count",
                        "production_closures_ref",
                        "protocol_id",
                        "protocol_ref",
                        "protocol_root",
                        "source_commit",
                        "source_tree",
                    ],
                },
            },
            "stages": stages,
        },
        "protocol_id": atlas_protocol.ATLAS_PROTOCOL_ID_V1,
        "protocol_version": 1,
        "stage_sequence": list(stage_ids),
    }
    protocol = dict(unsigned)
    protocol["protocol_root"] = domain_identity(
        atlas_protocol._PROTOCOL_ROOT_DOMAIN_V1, unsigned
    )
    return protocol


_SYNTHETIC_LEDGER_SCHEDULE = None


def synthetic_ledger_schedule():
    global _SYNTHETIC_LEDGER_SCHEDULE
    if _SYNTHETIC_LEDGER_SCHEDULE is None:
        exact = [
            {"slot_id": hashlib.sha256("exact:{}".format(index).encode()).hexdigest()}
            for index in range(288)
        ]
        orientations = [
            {"slot_id": hashlib.sha256("pv:{}".format(index).encode()).hexdigest()}
            for index in range(2_304)
        ]
        games = []
        for strength in (
            "random-v1-weak",
            "terminal_only_minimax-v1-depth1",
        ):
            games.extend(
                {
                    "slot_id": hashlib.sha256(
                        "{}:{}".format(strength, index).encode()
                    ).hexdigest(),
                    "strength": {"identity": strength},
                }
                for index in range(18_432)
            )
        _SYNTHETIC_LEDGER_SCHEDULE = (exact, orientations, games)
    return _SYNTHETIC_LEDGER_SCHEDULE


@contextlib.contextmanager
def frozen_synthetic_protocol(protocol):
    exact, orientations, games = synthetic_ledger_schedule()
    with mock.patch.object(
        atlas_protocol, "ATLAS_PROTOCOL_ROOT_V1", protocol["protocol_root"]
    ), mock.patch.object(
        atlas_protocol,
        "ATLAS_PROTOCOL_CANONICAL_SHA256_V1",
        hashlib.sha256(canonical_json_bytes(protocol)).hexdigest(),
    ), mock.patch.object(
        atlas_protocol,
        "iter_frozen_atlas_exact_schedule_from_protocol_v1",
        side_effect=lambda _value: iter(exact),
    ), mock.patch.object(
        atlas_protocol,
        "iter_frozen_atlas_orientation_schedule_from_protocol_v1",
        side_effect=lambda _value: iter(orientations),
    ), mock.patch.object(
        atlas_protocol,
        "iter_frozen_atlas_game_schedule_from_protocol_v1",
        side_effect=lambda _value: iter(games),
    ):
        yield


class CanonicalCodecTests(unittest.TestCase):
    def test_strict_round_trip_and_domain_vectors(self):
        value = {"é": [None, True, -12], "a": "x"}
        raw = canonical_json_bytes(value)
        self.assertEqual(load_canonical_json_bytes(raw), value)
        self.assertEqual(raw, json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())
        ref = canonical_body_ref(value)
        self.assertEqual(ref.sha256, hashlib.sha256(raw).hexdigest())
        domain = b"test-domain\0"
        self.assertEqual(domain_identity(domain, value), hashlib.sha256(domain + raw).hexdigest())

    def test_rejects_duplicate_float_cycle_type_depth_and_size(self):
        with self.assertRaises(ValueError):
            load_canonical_json_bytes(b'{"a":1,"a":2}')
        with self.assertRaises(ValueError):
            load_canonical_json_bytes(b'{"a":1.0}')
        with self.assertRaises(TypeError):
            canonical_json_bytes({"a": 1.0})
        cyclic = []
        cyclic.append(cyclic)
        with self.assertRaises(ValueError):
            canonical_json_bytes(cyclic)
        class DictSubclass(dict):
            pass
        with self.assertRaises(TypeError):
            canonical_json_bytes(DictSubclass(a=1))
        with self.assertRaises(ValueError):
            canonical_json_bytes([[[0]]], max_depth=2)
        with self.assertRaises(ValueError):
            canonical_json_bytes("abcd", max_string_bytes=3)
        with self.assertRaises(ValueError):
            canonical_json_bytes({"a": 1}, max_bytes=3)
        with self.assertRaises(ValueError):
            load_canonical_json_bytes(b'{"a":1 }')


class ImmutableStoreTests(unittest.TestCase):
    def test_publish_is_locked_exclusive_durable_and_fixed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "evidence"
            with ImmutableEvidenceStore(root) as store:
                with self.assertRaises(EvidenceLockError):
                    store.publish_json(STAGE_PROTOCOL_IDS[MANIFEST_ID], "reservation", {"x": 1})
                with store.stage_lock(STAGE_PROTOCOL_IDS[MANIFEST_ID]):
                    ref = store.publish_json(
                        STAGE_PROTOCOL_IDS[MANIFEST_ID], "reservation", {"x": 1}
                    )
                    self.assertEqual(ref, canonical_body_ref({"x": 1}))
                    with self.assertRaises(EvidenceConflictError):
                        store.publish_json(
                            STAGE_PROTOCOL_IDS[MANIFEST_ID], "reservation", {"x": 1}
                        )
                artifact = root / "stages" / STAGE_PROTOCOL_IDS[MANIFEST_ID] / "reservation.json"
                self.assertEqual(artifact.stat().st_nlink, 1)
                self.assertEqual(artifact.stat().st_mode & 0o777, 0o400)
                self.assertFalse(list(artifact.parent.glob(".tmp-*")))
                with self.assertRaises(ValueError):
                    store.read_json("../escape", "reservation")
                with self.assertRaises(ValueError):
                    store.read_json(STAGE_PROTOCOL_IDS[EXACT_ID], "protocol")

    def test_symlink_hardlink_and_noncatalog_paths_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "evidence"
            with ImmutableEvidenceStore(root) as store:
                pid = STAGE_PROTOCOL_IDS[EXACT_ID]
                outside = Path(directory) / "outside"
                outside.mkdir()
                (root / "stages" / pid).symlink_to(outside, target_is_directory=True)
                with store.stage_lock(pid):
                    with self.assertRaises(EvidenceIntegrityError):
                        store.publish_json(pid, "reservation", {"x": 1})
            root2 = Path(directory) / "evidence2"
            with ImmutableEvidenceStore(root2) as store:
                pid = STAGE_PROTOCOL_IDS[MANIFEST_ID]
                with store.stage_lock(pid):
                    store.publish_json(pid, "reservation", {"x": 1})
                artifact = root2 / "stages" / pid / "reservation.json"
                os.link(artifact, Path(directory) / "second-link")
                with self.assertRaises(EvidenceIntegrityError):
                    store.read_json(pid, "reservation")
            root3 = Path(directory) / "evidence3"
            with ImmutableEvidenceStore(root3) as store:
                pid = STAGE_PROTOCOL_IDS[MANIFEST_ID]
                with store.stage_lock(pid):
                    store.publish_json(pid, "reservation", {"x": 1})
                (root3 / "stages" / pid / "rogue.json").write_text("{}", encoding="utf-8")
                with self.assertRaises(EvidenceIntegrityError):
                    store.scan_fixed_catalog(pid)

    def test_fcntl_lock_excludes_another_process(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "evidence"
            with ImmutableEvidenceStore(root) as store:
                pid = STAGE_PROTOCOL_IDS[MANIFEST_ID]
                code = (
                    "from parity_forge.atlas_evidence import ImmutableEvidenceStore, EvidenceLockError\n"
                    "from pathlib import Path\n"
                    "import sys\n"
                    "s=ImmutableEvidenceStore(Path(sys.argv[1]))\n"
                    "try:\n"
                    "  with s.stage_lock(sys.argv[2]): pass\n"
                    "except EvidenceLockError:\n"
                    "  raise SystemExit(0)\n"
                    "raise SystemExit(9)\n"
                )
                environment = dict(os.environ)
                environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
                with store.stage_lock(pid):
                    process = subprocess.run(
                        [sys.executable, "-c", code, str(root), pid],
                        check=False,
                        env=environment,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        shell=False,
                    )
                self.assertEqual(process.returncode, 0, process.stderr.decode())


class GitClosureTests(unittest.TestCase):
    def test_clean_head_recursive_imports_init_checkpoint_and_reseal(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, checkpoint = make_git_repository(directory)
            required = (
                "src/parity_forge/__init__.py",
                "src/parity_forge/atlas_protocol.py",
                "src/parity_forge/dsl.py",
                "src/parity_forge/engine.py",
                "src/parity_forge/entry.py",
            )
            contract = make_contract(
                checkpoint_commit=checkpoint,
                checkpoint_paths=required,
                required_paths=required,
            )
            head = capture_clean_head(repository)
            self.assertEqual(head["source_commit"], checkpoint)
            closure = build_production_closure(
                repository,
                contract,
                ["src/parity_forge/entry.py"],
                b"synthetic plan\n",
            )
            paths = [item["path"] for item in closure.payload["ordered_file_records"]]
            self.assertEqual(paths, sorted(required))
            reseal_production_closure(repository, contract, closure, b"synthetic plan\n")
            (repository / "src/parity_forge/dsl.py").write_text("VALUE = 2\n", encoding="utf-8")
            with self.assertRaises(EvidenceIntegrityError):
                reseal_production_closure(repository, contract, closure, b"synthetic plan\n")
            with self.assertRaises(EvidenceIntegrityError):
                capture_clean_head(repository)

    def test_checkpoint_drift_forbidden_import_and_strict_ancestry(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, first = make_git_repository(directory)
            (repository / "src/parity_forge/dsl.py").write_text("VALUE = 9\n", encoding="utf-8")
            run_git(repository, "add", ".")
            run_git(repository, "commit", "-qm", "second")
            second = run_git(repository, "rev-parse", "HEAD")
            verify_commit_relation(repository, first, second)
            with self.assertRaises(EvidenceIntegrityError):
                verify_commit_relation(repository, second, first)
            required = (
                "src/parity_forge/__init__.py",
                "src/parity_forge/atlas_protocol.py",
                "src/parity_forge/dsl.py",
                "src/parity_forge/engine.py",
                "src/parity_forge/entry.py",
            )
            drift_contract = make_contract(
                checkpoint_commit=first,
                checkpoint_paths=("src/parity_forge/dsl.py",),
                required_paths=required,
            )
            with self.assertRaises(EvidenceIntegrityError):
                build_production_closure(
                    repository,
                    drift_contract,
                    ["src/parity_forge/entry.py"],
                    b"synthetic plan\n",
                )
            (repository / "src/parity_forge/agents.py").write_text("VALUE = 1\n", encoding="utf-8")
            (repository / "src/parity_forge/entry.py").write_text(
                "from . import agents\nfrom . import atlas_protocol\nfrom .engine import VALUE\n",
                encoding="utf-8",
            )
            run_git(repository, "add", ".")
            run_git(repository, "commit", "-qm", "forbidden")
            third = run_git(repository, "rev-parse", "HEAD")
            forbidden_contract = make_contract(
                checkpoint_commit=third,
                checkpoint_paths=(),
                required_paths=required,
                forbidden_paths=("src/parity_forge/agents.py",),
            )
            with self.assertRaises(EvidenceIntegrityError):
                build_production_closure(
                    repository,
                    forbidden_contract,
                    ["src/parity_forge/entry.py"],
                    b"synthetic plan\n",
                )


class TypedChainTests(unittest.TestCase):
    def test_completed_failure_blocked_orphaned_and_cross_refs(self):
        _, _, _, _, _, manifest_terminal = completed_manifest_chain()
        contract = exact_contract()
        closure = make_closure(contract)
        reservation = build_reservation(contract, closure, (manifest_terminal,))
        attempt = build_attempt(contract, reservation)
        completed = build_completed(contract, reservation, attempt, {"count": 1})
        terminal = build_terminal_seal(
            contract,
            "COMPLETED",
            reservation=reservation,
            attempt=attempt,
            completed=completed,
        )
        snapshot = ChainSnapshot(
            production_closure=closure,
            reservation=reservation,
            attempt=attempt,
            completed=completed,
            terminal_seal=terminal,
        )
        self.assertEqual(validate_chain_snapshot(contract, snapshot), "COMPLETED")
        tampered = json.loads(canonical_json_bytes(terminal))
        tampered["payload"]["completed_root_or_null"] = "0" * 64
        with self.assertRaises(EvidenceIntegrityError):
            validate_chain_snapshot(contract, replace(snapshot, terminal_seal=tampered))
        ledger = {"artifact_type": "ledger", "slots": []}
        failure = build_failure(contract, reservation, attempt, {"code": "x"}, ledger)
        failed_terminal = build_terminal_seal(
            contract,
            "FAILED",
            reservation=reservation,
            attempt=attempt,
            failure=failure,
            partial_evidence=ledger,
        )
        self.assertEqual(
            validate_chain_snapshot(
                contract,
                ChainSnapshot(
                    production_closure=closure,
                    reservation=reservation,
                    attempt=attempt,
                    partial_evidence=ledger,
                    failure=failure,
                    terminal_seal=failed_terminal,
                ),
            ),
            "FAILED",
        )
        orphaned = build_orphaned(contract, reservation, attempt, ledger)
        self.assertEqual(orphaned["payload"]["orphan_reason"], "ATTEMPT_WITHOUT_TERMINAL_SEAL")

        manifest_contract, manifest_closure, mres, matt, _, _ = completed_manifest_chain()
        manifest_failure = build_failure(manifest_contract, mres, matt, {"code": "x"}, None)
        failed_manifest_terminal = build_terminal_seal(
            manifest_contract,
            "FAILED",
            reservation=mres,
            attempt=matt,
            failure=manifest_failure,
        )
        blocked = build_blocked(contract, closure, (failed_manifest_terminal,))
        blocked_terminal = build_terminal_seal(contract, "BLOCKED", blocked=blocked)
        self.assertEqual(
            validate_chain_snapshot(
                contract,
                ChainSnapshot(
                    production_closure=closure,
                    blocked=blocked,
                    terminal_seal=blocked_terminal,
                ),
            ),
            "BLOCKED",
        )


class JournalRecoveryTests(unittest.TestCase):
    def setUp(self):
        _, _, _, _, _, self.manifest_terminal = completed_manifest_chain()
        self.contract = exact_contract()
        self.closure = make_closure(self.contract)
        self.reservation = build_reservation(
            self.contract, self.closure, (self.manifest_terminal,)
        )
        self.attempt = build_attempt(self.contract, self.reservation)
        self.spec = LedgerSpec(
            "exact",
            ("slot-0", "slot-1", "slot-2"),
            ("COMPLETE", "CENSORED"),
            "INCOMPLETE",
            "NOT_RUN",
            preclassified_statuses=((2, "NOT_ADMISSIBLE"),),
        )

    @staticmethod
    def _publish_blocked_exact_fixture(store, protocol):
        contracts = tuple(
            extract_stage_contract(protocol, stage_id)
            for stage_id in protocol["stage_sequence"]
        )
        closures = tuple(make_closure(contract, b"plan") for contract in contracts)
        manifest_contract = contracts[0]
        manifest_reservation = build_reservation(
            manifest_contract, closures[0], ()
        )
        manifest_attempt = build_attempt(manifest_contract, manifest_reservation)
        manifest_failure = build_failure(
            manifest_contract,
            manifest_reservation,
            manifest_attempt,
            {"kind": "synthetic"},
            None,
        )
        manifest_terminal = build_terminal_seal(
            manifest_contract,
            "FAILED",
            reservation=manifest_reservation,
            attempt=manifest_attempt,
            failure=manifest_failure,
        )
        with store.stage_lock(manifest_contract.stage_protocol_id):
            publish_manifest_bootstrap(
                store, manifest_contract, protocol, closures, b"plan"
            )
            store.publish_json(
                manifest_contract.stage_protocol_id,
                "reservation",
                manifest_reservation,
            )
            store.publish_json(
                manifest_contract.stage_protocol_id, "attempt", manifest_attempt
            )
            store.publish_json(
                manifest_contract.stage_protocol_id, "failure", manifest_failure
            )
            store.publish_json(
                manifest_contract.stage_protocol_id,
                "terminal_seal",
                manifest_terminal,
            )
        contract = contracts[1]
        blocked = build_blocked(contract, closures[1], (manifest_terminal,))
        terminal = build_terminal_seal(contract, "BLOCKED", blocked=blocked)
        schedule = atlas_evidence._frozen_ledger_schedule(protocol)
        specs = atlas_evidence._base_frozen_ledger_specs(contract, schedule)
        with store.stage_lock(contract.stage_protocol_id):
            store.publish_json(contract.stage_protocol_id, "blocked", blocked)
            store.publish_json(
                contract.stage_protocol_id, "terminal_seal", terminal
            )
        return contract, specs

    def test_ledger_reconciles_result_interrupted_and_preclassified(self):
        with tempfile.TemporaryDirectory() as directory:
            with ImmutableEvidenceStore(Path(directory) / "evidence") as store:
                pid = self.contract.stage_protocol_id
                with store.stage_lock(pid):
                    store.publish_journal_start(pid, "exact", 0, "slot-0")
                    store.publish_journal_result(
                        pid, "exact", 0, "slot-0", "COMPLETE", {"value": 1}
                    )
                    store.publish_journal_start(pid, "exact", 1, "slot-1")
                    ledger = reconcile_status_ledger(store, self.contract, self.spec)
                self.assertEqual(
                    [slot["status"] for slot in ledger["slots"]],
                    ["COMPLETE", "INCOMPLETE", "NOT_ADMISSIBLE"],
                )
                self.assertEqual(ledger["status_counts"]["COMPLETE"], 1)

    def test_recovery_seals_orphan_and_is_idempotent(self):
        protocol = synthetic_protocol()
        with frozen_synthetic_protocol(protocol), tempfile.TemporaryDirectory() as directory:
            with ImmutableEvidenceStore(Path(directory) / "evidence") as store:
                fixture = publish_synthetic_completed_manifest(store, protocol)
                contract = fixture["contracts"][1]
                closure = fixture["closures"][1]
                schedule = atlas_evidence._frozen_ledger_schedule(protocol)
                specs = atlas_evidence._base_frozen_ledger_specs(
                    contract, schedule
                )
                reservation = build_reservation(
                    contract, closure, (fixture["terminal"],)
                )
                attempt = build_attempt(contract, reservation)
                pid = contract.stage_protocol_id
                with store.stage_lock(pid):
                    store.publish_json(pid, "reservation", reservation)
                    store.publish_json(pid, "attempt", attempt)
                    store.publish_journal_start(
                        pid, "exact", 0, specs[0].ordered_slot_ids[0]
                    )
                result = recover_stage(store, contract, specs)
                self.assertEqual(result.lifecycle, "ORPHANED")
                self.assertEqual(result.action, "SEALED_NEW_ORPHANED")
                partial = store.read_json(pid, "partial_ledger")
                self.assertEqual(partial["ledgers"][0]["slots"][0]["status"], "INCOMPLETE")
                self.assertEqual(partial["phase_ids"], ["exact", "exact-pv"])
                self.assertEqual(
                    [ledger["slot_count"] for ledger in partial["ledgers"]],
                    [288, 2_304],
                )
                again = recover_stage(store, contract, specs)
                self.assertEqual(again.action, "VERIFIED_NO_OP")
                snapshot = ChainSnapshot(
                    production_closure=closure,
                    reservation=reservation,
                    attempt=attempt,
                    partial_evidence=partial,
                    orphaned=store.read_json(pid, "orphaned"),
                    terminal_seal=store.read_json(pid, "terminal_seal"),
                )
                self.assertEqual(validate_chain_snapshot(contract, snapshot), "ORPHANED")

    def test_recovery_rejects_nonfixed_one_slot_exact_spec(self):
        protocol = synthetic_protocol()
        with frozen_synthetic_protocol(protocol), tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "evidence"
            with ImmutableEvidenceStore(root) as store:
                fixture = publish_synthetic_completed_manifest(store, protocol)
                contract = fixture["contracts"][1]
                reservation = build_reservation(
                    contract, fixture["closures"][1], (fixture["terminal"],)
                )
                attempt = build_attempt(contract, reservation)
                weak_spec = LedgerSpec(
                    "exact",
                    (synthetic_ledger_schedule()[0][0]["slot_id"],),
                    ("COMPLETE",),
                    "INCOMPLETE",
                    "NOT_RUN",
                )
                with store.stage_lock(contract.stage_protocol_id):
                    store.publish_json(
                        contract.stage_protocol_id, "reservation", reservation
                    )
                    store.publish_json(
                        contract.stage_protocol_id, "attempt", attempt
                    )
                with self.assertRaises(EvidenceIntegrityError):
                    recover_stage(store, contract, (weak_spec,))
                self.assertFalse(
                    store.artifact_exists(
                        contract.stage_protocol_id, "partial_ledger"
                    )
                )
            self.assertTrue(
                (
                    root
                    / "contradictions"
                    / (contract.stage_protocol_id + ".json")
                ).is_file()
            )

    def test_recovery_validates_fixed_specs_before_no_evidence(self):
        protocol = synthetic_protocol()
        with frozen_synthetic_protocol(protocol), tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "evidence"
            with ImmutableEvidenceStore(root) as store:
                fixture = publish_synthetic_completed_manifest(store, protocol)
                contract = fixture["contracts"][1]
                weak_spec = LedgerSpec(
                    "exact",
                    (synthetic_ledger_schedule()[0][0]["slot_id"],),
                    ("COMPLETE",),
                    "INCOMPLETE",
                    "NOT_RUN",
                )
                self.assertFalse(
                    (root / "stages" / contract.stage_protocol_id).exists()
                )
                with self.assertRaises(EvidenceIntegrityError):
                    recover_stage(store, contract, (weak_spec,))
                schedule = atlas_evidence._frozen_ledger_schedule(protocol)
                fixed_specs = atlas_evidence._base_frozen_ledger_specs(
                    contract, schedule
                )
                result = recover_stage(store, contract, fixed_specs)
                self.assertEqual(result.action, "NO_EVIDENCE")
            self.assertFalse(
                (
                    root
                    / "contradictions"
                    / (contract.stage_protocol_id + ".json")
                ).exists()
            )

    def test_recovery_rejects_journal_without_lifecycle_root(self):
        protocol = synthetic_protocol()
        with frozen_synthetic_protocol(protocol), tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "evidence"
            with ImmutableEvidenceStore(root) as store:
                fixture = publish_synthetic_completed_manifest(store, protocol)
                contract = fixture["contracts"][1]
                schedule = atlas_evidence._frozen_ledger_schedule(protocol)
                specs = atlas_evidence._base_frozen_ledger_specs(
                    contract, schedule
                )
                with store.stage_lock(contract.stage_protocol_id):
                    store.publish_journal_start(
                        contract.stage_protocol_id,
                        "exact",
                        0,
                        specs[0].ordered_slot_ids[0],
                    )
                with self.assertRaises(EvidenceIntegrityError):
                    recover_stage(store, contract, specs)
                self.assertFalse(
                    store.artifact_exists(
                        contract.stage_protocol_id, "partial_ledger"
                    )
                )
            self.assertTrue(
                (
                    root
                    / "contradictions"
                    / (contract.stage_protocol_id + ".json")
                ).is_file()
            )

    def test_blocked_recovery_rejects_residual_journal_evidence(self):
        protocol = synthetic_protocol()
        with frozen_synthetic_protocol(protocol), tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "evidence"
            with ImmutableEvidenceStore(root) as store:
                contract, specs = self._publish_blocked_exact_fixture(
                    store, protocol
                )
                with store.stage_lock(contract.stage_protocol_id):
                    store.publish_journal_start(
                        contract.stage_protocol_id,
                        "exact",
                        0,
                        specs[0].ordered_slot_ids[0],
                    )
                with self.assertRaises(EvidenceIntegrityError):
                    recover_stage(store, contract, specs)
            self.assertTrue(
                (
                    root
                    / "contradictions"
                    / (contract.stage_protocol_id + ".json")
                ).is_file()
            )

    def test_blocked_recovery_rejects_completion_artifact_residue(self):
        protocol = synthetic_protocol()
        for artifact in ("status_ledger", "record_catalog"):
            with self.subTest(artifact=artifact), frozen_synthetic_protocol(
                protocol
            ), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "evidence"
                with ImmutableEvidenceStore(root) as store:
                    contract, specs = self._publish_blocked_exact_fixture(
                        store, protocol
                    )
                    with store.stage_lock(contract.stage_protocol_id):
                        store.publish_json(
                            contract.stage_protocol_id,
                            artifact,
                            {"synthetic": "incompatible-with-BLOCKED"},
                        )
                    with self.assertRaisesRegex(
                        EvidenceIntegrityError,
                        "incompatible fixed-catalog artifact",
                    ):
                        read_authenticated_stage_inputs(store, RANDOM_ID)
                    with self.assertRaisesRegex(
                        EvidenceIntegrityError,
                        "stage recovery failed closed",
                    ):
                        recover_stage(store, contract, specs)
                self.assertTrue(
                    (
                        root
                        / "contradictions"
                        / (contract.stage_protocol_id + ".json")
                    ).is_file()
                )

    def test_reservation_without_attempt_rejects_slot_journal(self):
        protocol = synthetic_protocol()
        with frozen_synthetic_protocol(protocol), tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "evidence"
            with ImmutableEvidenceStore(root) as store:
                fixture = publish_synthetic_completed_manifest(store, protocol)
                contract = fixture["contracts"][1]
                reservation = build_reservation(
                    contract, fixture["closures"][1], (fixture["terminal"],)
                )
                schedule = atlas_evidence._frozen_ledger_schedule(protocol)
                specs = atlas_evidence._base_frozen_ledger_specs(
                    contract, schedule
                )
                with store.stage_lock(contract.stage_protocol_id):
                    store.publish_json(
                        contract.stage_protocol_id, "reservation", reservation
                    )
                    store.publish_journal_start(
                        contract.stage_protocol_id,
                        "exact",
                        0,
                        specs[0].ordered_slot_ids[0],
                    )
                with self.assertRaises(EvidenceIntegrityError):
                    recover_stage(store, contract, specs)
                self.assertFalse(
                    store.artifact_exists(
                        contract.stage_protocol_id, "partial_ledger"
                    )
                )
            self.assertTrue(
                (
                    root
                    / "contradictions"
                    / (contract.stage_protocol_id + ".json")
                ).is_file()
            )

    def test_conflicting_lifecycle_bodies_create_external_contradiction(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "evidence"
            with ImmutableEvidenceStore(root) as store:
                pid = self.contract.stage_protocol_id
                with store.stage_lock(pid):
                    store.publish_json(pid, "reservation", self.reservation)
                    store.publish_json(pid, "attempt", self.attempt)
                    for index, slot_id in enumerate(self.spec.ordered_slot_ids[:2]):
                        store.publish_journal_start(pid, "exact", index, slot_id)
                    partial = {
                        "artifact_type": "ATLAS_FULL_STATUS_LEDGER_SET_V1",
                        "ledgers": [reconcile_status_ledger(store, self.contract, self.spec)],
                        "phase_ids": ["exact"],
                        "stage_id": self.contract.stage_id,
                        "stage_protocol_id": pid,
                    }
                    failure = build_failure(
                        self.contract, self.reservation, self.attempt, {"code": "x"}, partial
                    )
                    completed = build_completed(
                        self.contract, self.reservation, self.attempt, {"ok": True}
                    )
                    store.publish_json(pid, "partial_ledger", partial)
                    store.publish_json(pid, "failure", failure)
                    store.publish_json(pid, "completed", completed)
                with self.assertRaises(EvidenceIntegrityError):
                    recover_stage(store, self.contract, (self.spec,))
                contradiction = root / "contradictions" / (pid + ".json")
                self.assertTrue(contradiction.is_file())
                self.assertEqual(
                    load_canonical_json_bytes(contradiction.read_bytes())["reason"],
                    "INVALID_OR_CONFLICTING_STAGE_EVIDENCE",
                )

    def test_completed_outcome_without_referenced_evidence_fails_closed(self):
        refs = {
            "record_catalog": {"byte_count": 1, "sha256": "4" * 64},
            "status_ledger": {"byte_count": 1, "sha256": "5" * 64},
        }
        completed = build_completed(
            self.contract,
            self.reservation,
            self.attempt,
            {"artifact_refs_or_null": refs, "summary": {}},
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "evidence"
            with ImmutableEvidenceStore(root) as store:
                pid = self.contract.stage_protocol_id
                with store.stage_lock(pid):
                    store.publish_json(pid, "reservation", self.reservation)
                    store.publish_json(pid, "attempt", self.attempt)
                    store.publish_json(pid, "completed", completed)
                with self.assertRaises(EvidenceIntegrityError):
                    recover_stage(store, self.contract, (self.spec,))
            self.assertTrue(
                (root / "contradictions" / (pid + ".json")).is_file()
            )

    def test_completed_ledger_must_reconcile_from_immutable_journals(self):
        ledger = {
            "artifact_type": "ATLAS_FULL_STATUS_LEDGER_SET_V1",
            "ledgers": [
                {
                    "artifact_type": "ATLAS_FULL_STATUS_LEDGER_V1",
                    "phase_id": self.spec.phase_id,
                    "slot_count": len(self.spec.ordered_slot_ids),
                    "slots": [
                        {
                            "result_ref_or_null": None,
                            "slot_id": slot_id,
                            "slot_index": index,
                            "start_ref_or_null": None,
                            "status": "COMPLETE",
                        }
                        for index, slot_id in enumerate(
                            self.spec.ordered_slot_ids
                        )
                    ],
                    "stage_id": self.contract.stage_id,
                    "stage_protocol_id": self.contract.stage_protocol_id,
                    "status_counts": {
                        "COMPLETE": len(self.spec.ordered_slot_ids)
                    },
                }
            ],
            "phase_ids": [self.spec.phase_id],
            "stage_id": self.contract.stage_id,
            "stage_protocol_id": self.contract.stage_protocol_id,
        }
        empty_records = []
        catalog = {
            "artifact_type": "ATLAS_RESULT_RECORD_CATALOG_V1",
            "ordered_record_count": 0,
            "ordered_record_root": hashlib.sha256(
                canonical_json_bytes(empty_records)
            ).hexdigest(),
            "ordered_records": empty_records,
            "stage_id": self.contract.stage_id,
            "stage_protocol_id": self.contract.stage_protocol_id,
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "evidence"
            with ImmutableEvidenceStore(root) as store:
                pid = self.contract.stage_protocol_id
                with store.stage_lock(pid):
                    store.publish_json(pid, "reservation", self.reservation)
                    store.publish_json(pid, "attempt", self.attempt)
                    ledger_ref = store.publish_json(
                        pid, "status_ledger", ledger
                    )
                    catalog_ref = store.publish_json(
                        pid, "record_catalog", catalog
                    )
                    completed = build_completed(
                        self.contract,
                        self.reservation,
                        self.attempt,
                        {
                            "artifact_refs_or_null": {
                                "record_catalog": catalog_ref.as_dict(),
                                "status_ledger": ledger_ref.as_dict(),
                            },
                            "summary": {},
                        },
                    )
                    store.publish_json(pid, "completed", completed)
                with self.assertRaises(EvidenceIntegrityError):
                    recover_stage(store, self.contract, (self.spec,))
            self.assertTrue(
                (root / "contradictions" / (pid + ".json")).is_file()
            )


class RecoveryCompletedSummaryTests(unittest.TestCase):
    def test_assessment_matching_summary_verifies_or_seals_completed(self):
        protocol = synthetic_protocol()
        for sealed in (True, False):
            with self.subTest(sealed=sealed), frozen_synthetic_protocol(
                protocol
            ), tempfile.TemporaryDirectory() as directory:
                with ImmutableEvidenceStore(Path(directory) / "evidence") as store:
                    fixture = publish_synthetic_completed_manifest(store, protocol)
                    summary = {"fixture": "independently-reconstructed"}
                    contract = fixture["contracts"][5]
                    with store.stage_lock(contract.stage_protocol_id):
                        chain = publish_synthetic_assessment_chain(
                            store,
                            fixture,
                            summary,
                            publish_terminal=sealed,
                        )
                    with mock.patch.object(
                        atlas_evidence,
                        "_validate_fixed_parent_references",
                    ):
                        result = recover_stage(
                            store,
                            chain["contract"],
                            expected_completed_summary=summary,
                        )
                    self.assertEqual(result.lifecycle, "COMPLETED")
                    self.assertEqual(
                        result.action,
                        "VERIFIED_NO_OP"
                        if sealed
                        else "SEALED_EXISTING_COMPLETED",
                    )
                    self.assertTrue(
                        store.artifact_exists(
                            contract.stage_protocol_id, "terminal_seal"
                        )
                    )

    def test_assessment_mismatch_or_missing_summary_fails_with_sidecar(self):
        protocol = synthetic_protocol()
        for expected in ({"fixture": "different"}, None):
            with self.subTest(expected=expected), frozen_synthetic_protocol(
                protocol
            ), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "evidence"
                with ImmutableEvidenceStore(root) as store:
                    fixture = publish_synthetic_completed_manifest(store, protocol)
                    contract = fixture["contracts"][5]
                    with store.stage_lock(contract.stage_protocol_id):
                        publish_synthetic_assessment_chain(
                            store,
                            fixture,
                            {"fixture": "stored"},
                        )
                    with mock.patch.object(
                        atlas_evidence,
                        "_validate_fixed_parent_references",
                    ):
                        with self.assertRaises(EvidenceIntegrityError):
                            recover_stage(
                                store,
                                contract,
                                expected_completed_summary=expected,
                            )
                self.assertTrue(
                    (
                        root
                        / "contradictions"
                        / (contract.stage_protocol_id + ".json")
                    ).is_file()
                )

    def test_noncompleted_assessment_rejects_unexpected_summary(self):
        protocol = synthetic_protocol()
        with frozen_synthetic_protocol(protocol), tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "evidence"
            with ImmutableEvidenceStore(root) as store:
                fixture = publish_synthetic_completed_manifest(store, protocol)
                contract = fixture["contracts"][5]
                with store.stage_lock(contract.stage_protocol_id):
                    publish_synthetic_assessment_chain(
                        store,
                        fixture,
                        {"unused": True},
                        publish_completed=False,
                        publish_terminal=False,
                    )
                with mock.patch.object(
                    atlas_evidence,
                    "_validate_fixed_parent_references",
                ):
                    with self.assertRaises(EvidenceIntegrityError):
                        recover_stage(
                            store,
                            contract,
                            expected_completed_summary={"unexpected": True},
                        )
            self.assertTrue(
                (
                    root
                    / "contradictions"
                    / (contract.stage_protocol_id + ".json")
                ).is_file()
            )

    def test_no_evidence_assessment_rejects_unexpected_summary(self):
        protocol = synthetic_protocol()
        with frozen_synthetic_protocol(protocol), tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "evidence"
            with ImmutableEvidenceStore(root) as store:
                fixture = publish_synthetic_completed_manifest(store, protocol)
                contract = fixture["contracts"][5]
                self.assertFalse(
                    (root / "stages" / contract.stage_protocol_id).exists()
                )
                with self.assertRaises(EvidenceIntegrityError):
                    recover_stage(
                        store,
                        contract,
                        expected_completed_summary={"unexpected": True},
                    )
            self.assertFalse(
                (
                    root
                    / "contradictions"
                    / (contract.stage_protocol_id + ".json")
                ).exists()
            )

    def test_nonassessment_rejects_completed_summary_expectation(self):
        protocol = synthetic_protocol()
        with frozen_synthetic_protocol(protocol), tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "evidence"
            with ImmutableEvidenceStore(root) as store:
                fixture = publish_synthetic_completed_manifest(store, protocol)
                contract = fixture["contracts"][0]
                with self.assertRaises(EvidenceIntegrityError):
                    recover_stage(
                        store,
                        contract,
                        expected_completed_summary={"unexpected": True},
                    )
            self.assertTrue(
                (
                    root
                    / "contradictions"
                    / (contract.stage_protocol_id + ".json")
                ).is_file()
            )


class ManifestRecoveryReferenceTests(unittest.TestCase):
    def test_recovery_contract_is_selection_free_and_matches_frozen_coordinates(self):
        contract = extract_recovery_stage_contract(MANIFEST_ID)
        self.assertEqual(contract.stage_id, MANIFEST_ID)
        self.assertEqual(contract.stage_protocol_id, STAGE_PROTOCOL_IDS[MANIFEST_ID])
        self.assertEqual(contract.protocol_id, atlas_protocol.ATLAS_PROTOCOL_ID_V1)
        self.assertEqual(contract.protocol_root, atlas_protocol.ATLAS_PROTOCOL_ROOT_V1)
        self.assertFalse(
            hasattr(atlas_protocol, "confirmation_candidate_pairs")
        )

    def test_recovery_contract_rejects_non_v2_evidence_version(self):
        provenance = atlas_protocol._execution_evidence_protocol()
        provenance["evidence_protocol_version"] = 1
        with mock.patch.object(
            atlas_protocol,
            "_execution_evidence_protocol",
            return_value=provenance,
        ):
            with self.assertRaises(EvidenceIntegrityError):
                extract_recovery_stage_contract(MANIFEST_ID)


class FixedParentChainTests(unittest.TestCase):
    @staticmethod
    def _alternate_manifest_terminal(fixture):
        manifest_contract = fixture["contracts"][0]
        completed = build_completed(
            manifest_contract,
            fixture["reservation"],
            fixture["attempt"],
            {
                "artifact_refs_or_null": fixture["refs"].as_dict(),
                "summary": {"fixture": "alternate-unpublished-manifest"},
            },
        )
        return build_terminal_seal(
            manifest_contract,
            "COMPLETED",
            reservation=fixture["reservation"],
            attempt=fixture["attempt"],
            completed=completed,
        )

    def test_authenticated_inputs_reject_parent_with_alternate_embedded_ancestor(self):
        protocol = synthetic_protocol()
        with frozen_synthetic_protocol(protocol), tempfile.TemporaryDirectory() as directory:
            with ImmutableEvidenceStore(Path(directory) / "evidence") as store:
                fixture = publish_synthetic_completed_manifest(store, protocol)
                exact_contract = fixture["contracts"][1]
                alternate_manifest = self._alternate_manifest_terminal(fixture)
                reservation = build_reservation(
                    exact_contract,
                    fixture["closures"][1],
                    (alternate_manifest,),
                )
                attempt = build_attempt(exact_contract, reservation)
                partial = {
                    "artifact_type": "ATLAS_FULL_STATUS_LEDGER_SET_V1",
                    "ledgers": [],
                    "phase_ids": [],
                    "stage_id": exact_contract.stage_id,
                    "stage_protocol_id": exact_contract.stage_protocol_id,
                }
                failure = build_failure(
                    exact_contract,
                    reservation,
                    attempt,
                    {"code": "synthetic"},
                    partial,
                )
                terminal = build_terminal_seal(
                    exact_contract,
                    "FAILED",
                    reservation=reservation,
                    attempt=attempt,
                    failure=failure,
                    partial_evidence=partial,
                )
                with store.stage_lock(exact_contract.stage_protocol_id):
                    store.publish_json(
                        exact_contract.stage_protocol_id,
                        "reservation",
                        reservation,
                    )
                    store.publish_json(
                        exact_contract.stage_protocol_id, "attempt", attempt
                    )
                    store.publish_json(
                        exact_contract.stage_protocol_id,
                        "partial_ledger",
                        partial,
                    )
                    store.publish_json(
                        exact_contract.stage_protocol_id, "failure", failure
                    )
                    store.publish_json(
                        exact_contract.stage_protocol_id,
                        "terminal_seal",
                        terminal,
                    )
                self.assertNotEqual(
                    alternate_manifest["identity"], fixture["terminal"]["identity"]
                )
                with self.assertRaises(EvidenceIntegrityError):
                    read_authenticated_stage_inputs(store, RANDOM_ID)

    def test_authenticated_inputs_reject_fixed_manifest_with_nonbootstrap_closure(self):
        protocol = synthetic_protocol()
        with frozen_synthetic_protocol(protocol), tempfile.TemporaryDirectory() as directory:
            contracts = tuple(
                extract_stage_contract(protocol, stage_id)
                for stage_id in protocol["stage_sequence"]
            )
            plan = b"plan"
            closures = tuple(make_closure(contract, plan) for contract in contracts)
            manifest_contract = contracts[0]
            alternate_closure = make_closure(
                manifest_contract,
                plan,
                source_commit="5" * 40,
                source_tree="6" * 40,
            )
            reservation = build_reservation(manifest_contract, alternate_closure, ())
            attempt = build_attempt(manifest_contract, reservation)
            failure = build_failure(
                manifest_contract,
                reservation,
                attempt,
                {"kind": "synthetic"},
                None,
            )
            terminal = build_terminal_seal(
                manifest_contract,
                "FAILED",
                reservation=reservation,
                attempt=attempt,
                failure=failure,
            )
            with ImmutableEvidenceStore(Path(directory) / "evidence") as store:
                with store.stage_lock(manifest_contract.stage_protocol_id):
                    publish_manifest_bootstrap(
                        store, manifest_contract, protocol, closures, plan
                    )
                    store.publish_json(
                        manifest_contract.stage_protocol_id,
                        "reservation",
                        reservation,
                    )
                    store.publish_json(
                        manifest_contract.stage_protocol_id, "attempt", attempt
                    )
                    store.publish_json(
                        manifest_contract.stage_protocol_id, "failure", failure
                    )
                    store.publish_json(
                        manifest_contract.stage_protocol_id,
                        "terminal_seal",
                        terminal,
                    )
                with self.assertRaises(EvidenceIntegrityError):
                    read_authenticated_stage_inputs(store, EXACT_ID)

    def test_authenticated_inputs_reject_parent_contradiction_sidecar(self):
        protocol = synthetic_protocol()
        with frozen_synthetic_protocol(protocol), tempfile.TemporaryDirectory() as directory:
            with ImmutableEvidenceStore(Path(directory) / "evidence") as store:
                fixture = publish_synthetic_completed_manifest(store, protocol)
                manifest_contract = fixture["contracts"][0]
                with store.stage_lock(manifest_contract.stage_protocol_id):
                    store.publish_contradiction(
                        manifest_contract.stage_protocol_id,
                        {
                            "artifact_type": "ATLAS_STAGE_CONTRADICTION_V1",
                            "observed_catalog": {},
                            "reason": "SYNTHETIC_PARENT_CONTRADICTION",
                            "stage_id": manifest_contract.stage_id,
                            "stage_protocol_id": (
                                manifest_contract.stage_protocol_id
                            ),
                        },
                    )
                with self.assertRaisesRegex(
                    EvidenceIntegrityError, "contradiction sidecar"
                ):
                    read_authenticated_stage_inputs(store, EXACT_ID)

    def test_recursive_parent_cache_never_suppresses_sidecar_check(self):
        protocol = synthetic_protocol()
        with frozen_synthetic_protocol(protocol), tempfile.TemporaryDirectory() as directory:
            with ImmutableEvidenceStore(Path(directory) / "evidence") as store:
                fixture = publish_synthetic_completed_manifest(store, protocol)
                contracts_by_stage = {
                    contract.stage_id: contract
                    for contract in fixture["contracts"]
                }
                closures_by_stage = {
                    contract.stage_id: fixture["closures"][contract.stage_index]
                    for contract in fixture["contracts"]
                }
                exact_contract = fixture["contracts"][1]
                exact_reservation = build_reservation(
                    exact_contract,
                    fixture["closures"][1],
                    (fixture["terminal"],),
                )
                manifest_contract = fixture["contracts"][0]
                with store.stage_lock(manifest_contract.stage_protocol_id):
                    store.publish_contradiction(
                        manifest_contract.stage_protocol_id,
                        {
                            "artifact_type": "ATLAS_STAGE_CONTRADICTION_V1",
                            "observed_catalog": {},
                            "reason": "SYNTHETIC_CACHED_PARENT_CONTRADICTION",
                            "stage_id": manifest_contract.stage_id,
                            "stage_protocol_id": (
                                manifest_contract.stage_protocol_id
                            ),
                        },
                    )
                with self.assertRaisesRegex(
                    EvidenceIntegrityError, "contradiction sidecar"
                ):
                    atlas_evidence._validate_fixed_parent_references(
                        store,
                        protocol,
                        exact_contract,
                        ChainSnapshot(
                            production_closure=fixture["closures"][1],
                            reservation=exact_reservation,
                        ),
                        contracts_by_stage,
                        closures_by_stage,
                        None,
                        validated_stage_ids={MANIFEST_ID},
                    )

    def test_authenticated_inputs_reject_exact_target_or_parent_contradiction(self):
        protocol = synthetic_protocol()
        with frozen_synthetic_protocol(protocol), tempfile.TemporaryDirectory() as directory:
            with ImmutableEvidenceStore(Path(directory) / "evidence") as store:
                fixture = publish_synthetic_completed_manifest(store, protocol)
                contract = fixture["contracts"][1]
                schedule = atlas_evidence._frozen_ledger_schedule(protocol)
                specs = atlas_evidence._base_frozen_ledger_specs(
                    contract, schedule
                )
                reservation = build_reservation(
                    contract, fixture["closures"][1], (fixture["terminal"],)
                )
                attempt = build_attempt(contract, reservation)
                with store.stage_lock(contract.stage_protocol_id):
                    store.publish_json(
                        contract.stage_protocol_id, "reservation", reservation
                    )
                    store.publish_json(
                        contract.stage_protocol_id, "attempt", attempt
                    )
                    atlas_evidence.seal_failed_stage(
                        store,
                        contract,
                        {"kind": "synthetic-exact-failure"},
                        specs,
                    )
                    store.publish_contradiction(
                        contract.stage_protocol_id,
                        {
                            "artifact_type": "ATLAS_STAGE_CONTRADICTION_V1",
                            "observed_catalog": {},
                            "reason": "SYNTHETIC_EXACT_CONTRADICTION",
                            "stage_id": contract.stage_id,
                            "stage_protocol_id": contract.stage_protocol_id,
                        },
                    )
                for target_stage_id in (EXACT_ID, RANDOM_ID):
                    with self.subTest(target_stage_id=target_stage_id):
                        with self.assertRaisesRegex(
                            EvidenceIntegrityError, "contradiction sidecar"
                        ):
                            read_authenticated_stage_inputs(
                                store, target_stage_id
                            )

    def test_authenticated_inputs_reject_parent_with_nonbootstrap_closure(self):
        protocol = synthetic_protocol()
        with frozen_synthetic_protocol(protocol), tempfile.TemporaryDirectory() as directory:
            with ImmutableEvidenceStore(Path(directory) / "evidence") as store:
                fixture = publish_synthetic_completed_manifest(store, protocol)
                exact_contract = fixture["contracts"][1]
                alternate_closure = make_closure(
                    exact_contract,
                    b"plan",
                    source_commit="5" * 40,
                    source_tree="6" * 40,
                )
                reservation = build_reservation(
                    exact_contract,
                    alternate_closure,
                    (fixture["terminal"],),
                )
                attempt = build_attempt(exact_contract, reservation)
                partial = {
                    "artifact_type": "ATLAS_FULL_STATUS_LEDGER_SET_V1",
                    "ledgers": [],
                    "phase_ids": [],
                    "stage_id": exact_contract.stage_id,
                    "stage_protocol_id": exact_contract.stage_protocol_id,
                }
                failure = build_failure(
                    exact_contract,
                    reservation,
                    attempt,
                    {"kind": "synthetic"},
                    partial,
                )
                terminal = build_terminal_seal(
                    exact_contract,
                    "FAILED",
                    reservation=reservation,
                    attempt=attempt,
                    failure=failure,
                    partial_evidence=partial,
                )
                with store.stage_lock(exact_contract.stage_protocol_id):
                    store.publish_json(
                        exact_contract.stage_protocol_id,
                        "reservation",
                        reservation,
                    )
                    store.publish_json(
                        exact_contract.stage_protocol_id, "attempt", attempt
                    )
                    store.publish_json(
                        exact_contract.stage_protocol_id,
                        "partial_ledger",
                        partial,
                    )
                    store.publish_json(
                        exact_contract.stage_protocol_id, "failure", failure
                    )
                    store.publish_json(
                        exact_contract.stage_protocol_id,
                        "terminal_seal",
                        terminal,
                    )
                with self.assertRaises(EvidenceIntegrityError):
                    read_authenticated_stage_inputs(store, RANDOM_ID)

    def test_recovery_rejects_alternate_fixed_parent_before_reconciliation(self):
        protocol = synthetic_protocol()
        with frozen_synthetic_protocol(protocol), tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "evidence"
            with ImmutableEvidenceStore(root) as store:
                fixture = publish_synthetic_completed_manifest(store, protocol)
                exact_contract = fixture["contracts"][1]
                alternate_manifest = self._alternate_manifest_terminal(fixture)
                reservation = build_reservation(
                    exact_contract,
                    fixture["closures"][1],
                    (alternate_manifest,),
                )
                attempt = build_attempt(exact_contract, reservation)
                spec = LedgerSpec(
                    "exact",
                    ("slot-0",),
                    ("COMPLETE",),
                    "INCOMPLETE",
                    "NOT_RUN",
                )
                with store.stage_lock(exact_contract.stage_protocol_id):
                    store.publish_json(
                        exact_contract.stage_protocol_id,
                        "reservation",
                        reservation,
                    )
                    store.publish_json(
                        exact_contract.stage_protocol_id, "attempt", attempt
                    )
                with self.assertRaises(EvidenceIntegrityError):
                    recover_stage(store, exact_contract, (spec,))
                self.assertFalse(
                    store.artifact_exists(
                        exact_contract.stage_protocol_id, "partial_ledger"
                    )
                )
            self.assertTrue(
                (
                    root
                    / "contradictions"
                    / (exact_contract.stage_protocol_id + ".json")
                ).is_file()
            )

    def test_recovery_rejects_target_nonbootstrap_closure_before_reconciliation(self):
        protocol = synthetic_protocol()
        with frozen_synthetic_protocol(protocol), tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "evidence"
            with ImmutableEvidenceStore(root) as store:
                fixture = publish_synthetic_completed_manifest(store, protocol)
                exact_contract = fixture["contracts"][1]
                alternate_closure = make_closure(
                    exact_contract,
                    b"plan",
                    source_commit="5" * 40,
                    source_tree="6" * 40,
                )
                reservation = build_reservation(
                    exact_contract,
                    alternate_closure,
                    (fixture["terminal"],),
                )
                attempt = build_attempt(exact_contract, reservation)
                spec = LedgerSpec(
                    "exact",
                    ("slot-0",),
                    ("COMPLETE",),
                    "INCOMPLETE",
                    "NOT_RUN",
                )
                with store.stage_lock(exact_contract.stage_protocol_id):
                    store.publish_json(
                        exact_contract.stage_protocol_id,
                        "reservation",
                        reservation,
                    )
                    store.publish_json(
                        exact_contract.stage_protocol_id, "attempt", attempt
                    )
                with self.assertRaises(EvidenceIntegrityError):
                    recover_stage(store, exact_contract, (spec,))
                self.assertFalse(
                    store.artifact_exists(
                        exact_contract.stage_protocol_id, "partial_ledger"
                    )
                )
            self.assertTrue(
                (
                    root
                    / "contradictions"
                    / (exact_contract.stage_protocol_id + ".json")
                ).is_file()
            )

    def test_self_consistent_empty_completed_ledger_is_not_completed_valid(self):
        protocol = synthetic_protocol()
        with frozen_synthetic_protocol(protocol), tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "evidence"
            with ImmutableEvidenceStore(root) as store:
                fixture = publish_synthetic_completed_manifest(store, protocol)
                contract = fixture["contracts"][1]
                reservation = build_reservation(
                    contract, fixture["closures"][1], (fixture["terminal"],)
                )
                attempt = build_attempt(contract, reservation)
                empty_ledger = {
                    "artifact_type": "ATLAS_FULL_STATUS_LEDGER_SET_V1",
                    "ledgers": [],
                    "phase_ids": [],
                    "stage_id": contract.stage_id,
                    "stage_protocol_id": contract.stage_protocol_id,
                }
                empty_records = []
                empty_catalog = {
                    "artifact_type": "ATLAS_RESULT_RECORD_CATALOG_V1",
                    "ordered_record_count": 0,
                    "ordered_record_root": hashlib.sha256(
                        canonical_json_bytes(empty_records)
                    ).hexdigest(),
                    "ordered_records": empty_records,
                    "stage_id": contract.stage_id,
                    "stage_protocol_id": contract.stage_protocol_id,
                }
                with store.stage_lock(contract.stage_protocol_id):
                    store.publish_json(
                        contract.stage_protocol_id, "reservation", reservation
                    )
                    store.publish_json(
                        contract.stage_protocol_id, "attempt", attempt
                    )
                    refs = atlas_evidence.StageResultRefs(
                        status_ledger=store.publish_json(
                            contract.stage_protocol_id,
                            "status_ledger",
                            empty_ledger,
                        ),
                        record_catalog=store.publish_json(
                            contract.stage_protocol_id,
                            "record_catalog",
                            empty_catalog,
                        ),
                    )
                    publish_completed_outcome_chain(
                        store, contract, reservation, attempt, refs
                    )
                with self.assertRaisesRegex(
                    EvidenceIntegrityError,
                    "completed status ledger from immutable journals",
                ):
                    read_authenticated_stage_inputs(store, RANDOM_ID)
                caller_spec = LedgerSpec(
                    "exact",
                    (synthetic_ledger_schedule()[0][0]["slot_id"],),
                    ("COMPLETE",),
                    "INCOMPLETE",
                    "NOT_RUN",
                )
                with self.assertRaises(EvidenceIntegrityError):
                    recover_stage(store, contract, (caller_spec,))
            self.assertTrue(
                (
                    root
                    / "contradictions"
                    / (contract.stage_protocol_id + ".json")
                ).is_file()
            )


class FrozenCompletionGateTests(unittest.TestCase):
    def test_frozen_schedule_revalidates_public_iterators_on_every_call(self):
        protocol = synthetic_protocol()
        with frozen_synthetic_protocol(protocol):
            first = atlas_evidence._frozen_ledger_schedule(protocol)
            self.assertEqual(len(first.telemetry_ids), 36_864)
            with mock.patch.object(
                atlas_protocol,
                "iter_frozen_atlas_exact_schedule_from_protocol_v1",
                side_effect=ValueError("poisoned sealed iterator context"),
            ):
                with self.assertRaisesRegex(ValueError, "poisoned"):
                    atlas_evidence._frozen_ledger_schedule(protocol)

    def test_telemetry_preclassification_is_exactly_parent_derived(self):
        protocol = synthetic_protocol()
        with frozen_synthetic_protocol(protocol):
            contracts = {
                stage_id: extract_stage_contract(protocol, stage_id)
                for stage_id in protocol["stage_sequence"]
            }
            schedule = atlas_evidence._frozen_ledger_schedule(protocol)

            def sampled_parent(_store, _protocol, contract, _contracts, _schedule):
                if contract.stage_id == RANDOM_ID:
                    phase_id = "random"
                    slot_ids = schedule.random_ids
                    statuses = ("COMPLETE",) + ("NOT_RUN",) * (
                        len(slot_ids) - 1
                    )
                elif contract.stage_id == DEPTH_ID:
                    phase_id = "depth1"
                    slot_ids = schedule.depth1_ids
                    statuses = ("BLOCKED",) * len(slot_ids)
                else:
                    raise AssertionError("unexpected sampled parent")
                return {
                    "phase_ids": [phase_id],
                    "ledgers": [
                        {
                            "phase_id": phase_id,
                            "slots": [
                                {"slot_id": slot_id, "status": status}
                                for slot_id, status in zip(slot_ids, statuses)
                            ],
                        }
                    ],
                }

            telemetry_contract = contracts[TELEMETRY_ID]
            with mock.patch.object(
                atlas_evidence,
                "_sampled_parent_ledger_for_telemetry",
                side_effect=sampled_parent,
            ):
                specs = atlas_evidence._frozen_completion_ledger_specs(
                    mock.Mock(),
                    protocol,
                    telemetry_contract,
                    contracts,
                    schedule,
                )
            self.assertEqual(len(specs), 1)
            self.assertEqual(len(specs[0].preclassified_statuses), 36_863)
            self.assertNotIn(0, dict(specs[0].preclassified_statuses))

            statuses = ["NOT_ADMISSIBLE"] * 36_864
            forged = {
                "phase_ids": ["telemetry"],
                "ledgers": [
                    {
                        "phase_id": "telemetry",
                        "slots": [{"status": status} for status in statuses],
                    }
                ],
            }
            with self.assertRaisesRegex(
                EvidenceIntegrityError, "nonvalidated admissible slot"
            ):
                atlas_evidence._require_frozen_completion_gate(
                    telemetry_contract, forged, specs
                )

            statuses[0] = "INVALID"
            invalid = {
                "phase_ids": ["telemetry"],
                "ledgers": [
                    {
                        "phase_id": "telemetry",
                        "slots": [{"status": status} for status in statuses],
                    }
                ],
            }
            with self.assertRaisesRegex(
                EvidenceIntegrityError, "nonvalidated admissible slot"
            ):
                atlas_evidence._require_frozen_completion_gate(
                    telemetry_contract, invalid, specs
                )

            statuses[0] = "VALIDATED"
            valid = {
                "phase_ids": ["telemetry"],
                "ledgers": [
                    {
                        "phase_id": "telemetry",
                        "slots": [{"status": status} for status in statuses],
                    }
                ],
            }
            atlas_evidence._require_frozen_completion_gate(
                telemetry_contract, valid, specs
            )

    def test_self_consistent_false_status_cannot_satisfy_exact_completion(self):
        protocol = synthetic_protocol()
        with frozen_synthetic_protocol(protocol), tempfile.TemporaryDirectory() as directory:
            with ImmutableEvidenceStore(Path(directory) / "evidence") as store:
                fixture = publish_synthetic_completed_manifest(store, protocol)
                contract = fixture["contracts"][1]
                schedule = atlas_evidence._frozen_ledger_schedule(protocol)
                specs = atlas_evidence._base_frozen_ledger_specs(
                    contract, schedule
                )
                reservation = build_reservation(
                    contract, fixture["closures"][1], (fixture["terminal"],)
                )
                attempt = build_attempt(contract, reservation)
                with store.stage_lock(contract.stage_protocol_id):
                    store.publish_json(
                        contract.stage_protocol_id, "reservation", reservation
                    )
                    store.publish_json(
                        contract.stage_protocol_id, "attempt", attempt
                    )
                    slot_id = specs[0].ordered_slot_ids[0]
                    store.publish_journal_start(
                        contract.stage_protocol_id, "exact", 0, slot_id
                    )
                    store.publish_journal_result(
                        contract.stage_protocol_id,
                        "exact",
                        0,
                        slot_id,
                        "INVALID",
                        {"fixture": "self-consistent-invalid"},
                    )
                    refs = publish_stage_completion_evidence(
                        store, contract, specs
                    )
                    publish_completed_outcome_chain(
                        store, contract, reservation, attempt, refs
                    )
                with self.assertRaisesRegex(
                    EvidenceIntegrityError, "all-slot frozen gate"
                ):
                    read_authenticated_stage_inputs(store, RANDOM_ID)

    def test_completed_ledger_must_match_late_immutable_journal(self):
        protocol = synthetic_protocol()
        with frozen_synthetic_protocol(protocol), tempfile.TemporaryDirectory() as directory:
            with ImmutableEvidenceStore(Path(directory) / "evidence") as store:
                fixture = publish_synthetic_completed_manifest(store, protocol)
                contract = fixture["contracts"][1]
                schedule = atlas_evidence._frozen_ledger_schedule(protocol)
                specs = atlas_evidence._base_frozen_ledger_specs(
                    contract, schedule
                )
                reservation = build_reservation(
                    contract, fixture["closures"][1], (fixture["terminal"],)
                )
                attempt = build_attempt(contract, reservation)
                with store.stage_lock(contract.stage_protocol_id):
                    store.publish_json(
                        contract.stage_protocol_id, "reservation", reservation
                    )
                    store.publish_json(
                        contract.stage_protocol_id, "attempt", attempt
                    )
                    stale_refs = publish_stage_completion_evidence(
                        store, contract, specs
                    )
                    slot_id = specs[0].ordered_slot_ids[0]
                    store.publish_journal_start(
                        contract.stage_protocol_id, "exact", 0, slot_id
                    )
                    store.publish_journal_result(
                        contract.stage_protocol_id,
                        "exact",
                        0,
                        slot_id,
                        "COMPLETE",
                        {"fixture": "published-after-ledger"},
                    )
                    publish_completed_outcome_chain(
                        store,
                        contract,
                        reservation,
                        attempt,
                        stale_refs,
                    )
                with self.assertRaisesRegex(
                    EvidenceIntegrityError,
                    "completed status ledger from immutable journals",
                ):
                    read_authenticated_stage_inputs(store, RANDOM_ID)


class BoundaryOperationTests(unittest.TestCase):
    def test_begin_journal_completion_publish_and_terminal(self):
        with tempfile.TemporaryDirectory() as repository_parent, tempfile.TemporaryDirectory() as evidence_parent:
            repository, checkpoint = make_git_repository(repository_parent)
            required = (
                "src/parity_forge/__init__.py",
                "src/parity_forge/atlas_protocol.py",
                "src/parity_forge/dsl.py",
                "src/parity_forge/engine.py",
                "src/parity_forge/entry.py",
            )
            contract = exact_contract(checkpoint, required)
            contract = replace(contract, checkpoint_paths=required)
            closure = build_production_closure(
                repository,
                contract,
                ["src/parity_forge/entry.py"],
                b"synthetic plan\n",
            )
            _, _, _, _, _, manifest_terminal = completed_manifest_chain(b"synthetic plan\n")
            spec = LedgerSpec(
                "exact", ("slot-0", "slot-1"), ("COMPLETE",), "INCOMPLETE", "NOT_RUN"
            )
            with ImmutableEvidenceStore(Path(evidence_parent) / "evidence") as store:
                with store.stage_lock(contract.stage_protocol_id):
                    begin_stage(
                        store,
                        repository,
                        contract,
                        closure,
                        (manifest_terminal,),
                        b"synthetic plan\n",
                        (spec,),
                    )
                    for index, slot_id in enumerate(spec.ordered_slot_ids):
                        store.publish_journal_start(
                            contract.stage_protocol_id, "exact", index, slot_id
                        )
                        store.publish_journal_result(
                            contract.stage_protocol_id,
                            "exact",
                            index,
                            slot_id,
                            "COMPLETE",
                            {"score": index},
                        )
                    refs = publish_stage_completion_evidence(store, contract, (spec,))
                    terminal = seal_completed_stage(
                        store,
                        repository,
                        contract,
                        closure,
                        b"synthetic plan\n",
                        {"complete_count": 2},
                        refs,
                    )
                self.assertEqual(terminal["payload"]["lifecycle"], "COMPLETED")
                completed = store.read_json(contract.stage_protocol_id, "completed")
                self.assertEqual(completed["result"]["artifact_refs_or_null"], refs.as_dict())

    def test_manifest_freeze_and_authenticated_candidate_neutral_inputs(self):
        protocol = synthetic_protocol()
        with frozen_synthetic_protocol(protocol), tempfile.TemporaryDirectory() as directory:
            contracts = tuple(
                extract_stage_contract(protocol, stage_id)
                for stage_id in protocol["stage_sequence"]
            )
            plan = b"synthetic frozen plan"
            closures = tuple(make_closure(contract, plan) for contract in contracts)
            manifest_contract = contracts[0]
            reservation = build_reservation(manifest_contract, closures[0], ())
            attempt = build_attempt(manifest_contract, reservation)
            with ImmutableEvidenceStore(Path(directory) / "evidence") as store:
                with store.stage_lock(manifest_contract.stage_protocol_id):
                    bootstrap_refs = publish_manifest_bootstrap(
                        store,
                        manifest_contract,
                        protocol,
                        closures,
                        plan,
                    )
                    store.publish_json(
                        manifest_contract.stage_protocol_id, "reservation", reservation
                    )
                    store.publish_json(
                        manifest_contract.stage_protocol_id, "attempt", attempt
                    )
                    refs = publish_manifest_freeze(
                        store,
                        manifest_contract,
                        protocol,
                        {"development_definitions": [{"id": "dev-0"}]},
                        closures,
                        plan,
                    )
                    completed = build_completed(
                        manifest_contract,
                        reservation,
                        attempt,
                        {"artifact_refs_or_null": refs.as_dict(), "summary": {"count": 1}},
                    )
                    terminal = build_terminal_seal(
                        manifest_contract,
                        "COMPLETED",
                        reservation=reservation,
                        attempt=attempt,
                        completed=completed,
                    )
                    store.publish_json(
                        manifest_contract.stage_protocol_id, "completed", completed
                    )
                    store.publish_json(
                        manifest_contract.stage_protocol_id, "terminal_seal", terminal
                    )
                frozen = read_manifest_freeze(store, manifest_contract)
                self.assertEqual(frozen["refs"], refs)
                inputs = read_authenticated_stage_inputs(store, EXACT_ID)
                self.assertEqual(inputs.contract.stage_id, EXACT_ID)
                self.assertEqual(inputs.production_closure.root, closures[1].root)
                self.assertEqual(inputs.experiment_plan_bytes, plan)
                self.assertEqual(inputs.manifest_bootstrap_refs, bootstrap_refs)
                self.assertEqual(inputs.manifest_lifecycle, "COMPLETED")
                self.assertEqual(
                    inputs.detached_manifest,
                    {"development_definitions": [{"id": "dev-0"}]},
                )
                self.assertNotIn("selection", inputs.__dict__)

    def test_bootstrap_allows_fail_closed_inputs_without_detached_manifest(self):
        protocol = synthetic_protocol()
        with frozen_synthetic_protocol(protocol), tempfile.TemporaryDirectory() as directory:
            contracts = tuple(
                extract_stage_contract(protocol, stage_id)
                for stage_id in protocol["stage_sequence"]
            )
            plan = b"synthetic bootstrap plan"
            closures = tuple(make_closure(contract, plan) for contract in contracts)
            manifest_contract = contracts[0]
            reservation = build_reservation(manifest_contract, closures[0], ())
            attempt = build_attempt(manifest_contract, reservation)
            failure = build_failure(
                manifest_contract,
                reservation,
                attempt,
                {"kind": "SYNTHETIC_MANIFEST_FAILURE"},
                None,
            )
            terminal = build_terminal_seal(
                manifest_contract,
                "FAILED",
                reservation=reservation,
                attempt=attempt,
                failure=failure,
            )
            with ImmutableEvidenceStore(Path(directory) / "evidence") as store:
                with store.stage_lock(manifest_contract.stage_protocol_id):
                    bootstrap_refs = publish_manifest_bootstrap(
                        store, manifest_contract, protocol, closures, plan
                    )
                    store.publish_json(
                        manifest_contract.stage_protocol_id,
                        "reservation",
                        reservation,
                    )
                    store.publish_json(
                        manifest_contract.stage_protocol_id, "attempt", attempt
                    )
                    store.publish_json(
                        manifest_contract.stage_protocol_id, "failure", failure
                    )
                    store.publish_json(
                        manifest_contract.stage_protocol_id,
                        "terminal_seal",
                        terminal,
                    )
                inputs = read_authenticated_stage_inputs(store, EXACT_ID)
                self.assertEqual(inputs.manifest_lifecycle, "FAILED")
                self.assertIsNone(inputs.detached_manifest)
                self.assertIsNone(inputs.manifest_freeze_refs)
                self.assertEqual(inputs.manifest_bootstrap_refs, bootstrap_refs)
                self.assertEqual(inputs.production_closure.root, closures[1].root)


class ModuleBoundaryTests(unittest.TestCase):
    def test_module_imports_only_stdlib_and_atlas_protocol(self):
        path = Path(__file__).resolve().parents[1] / "src/parity_forge/atlas_evidence.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        local_imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                local_imports.extend(
                    alias.name for alias in node.names if alias.name.startswith("parity_forge")
                )
            elif isinstance(node, ast.ImportFrom):
                if node.level or (node.module or "").startswith("parity_forge"):
                    local_imports.append((node.level, node.module, tuple(a.name for a in node.names)))
        self.assertEqual(local_imports, [(1, None, ("atlas_protocol",))])
        forbidden = {"solver", "agents", "agency", "play", "experiments"}
        imported_names = {
            alias.name.split(".")[-1]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported_names.update(
            (node.module or "").split(".")[-1]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        )
        self.assertFalse(forbidden & imported_names)


if __name__ == "__main__":
    unittest.main()
