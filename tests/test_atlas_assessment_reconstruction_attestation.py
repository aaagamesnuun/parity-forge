import copy
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import parity_forge.atlas_assessment_reconstruction_attestation as attestation
from parity_forge.atlas_assessment_reconstruction_protocol import identity_domain_v1
from parity_forge.atlas_evidence import (
    EvidenceIntegrityError,
    canonical_body_ref,
    canonical_json_bytes,
    domain_identity,
)


def _source_binding(inventory_root="a" * 64):
    terminal_values = []
    for (
        stage_id,
        stage_protocol_id,
        lifecycle,
        identity,
        terminal_ref,
        result_ref,
    ) in attestation._STAGE_PINS_V1:
        terminal_values.append(
            {
                "stage_id": stage_id,
                "stage_protocol_id": stage_protocol_id,
                "lifecycle": lifecycle,
                "terminal_seal_identity": identity,
                "terminal_body_ref": terminal_ref.as_dict(),
                "result_body_ref": result_ref.as_dict(),
            }
        )
    payload = {
        "source_binding_version": attestation.PLAN0014_SOURCE_BINDING_VERSION_V1,
        "source_binding_id": attestation.PLAN0014_SOURCE_BINDING_ID_V1,
        "evidence_store_relative_path": (
            attestation.PLAN0013_ATLAS_EVIDENCE_ROOT_RELATIVE_V1
        ),
        "archive": {
            "commit": attestation.PLAN0013_ARCHIVE_COMMIT_V1,
            "tree": attestation.PLAN0013_ARCHIVE_TREE_V1,
            "evidence_subtree": (
                attestation.PLAN0013_ARCHIVE_EVIDENCE_SUBTREE_V1
            ),
        },
        "repair_checkpoint": {
            "commit": attestation.PLAN0014_REPAIR_CHECKPOINT_COMMIT_V1,
            "tree": attestation.PLAN0014_REPAIR_CHECKPOINT_TREE_V1,
        },
        "archive_live_inventory": {
            "archive_file_count": attestation.PLAN0013_ARCHIVE_FILE_COUNT_V1,
            "archive_total_bytes": attestation.PLAN0013_ARCHIVE_TOTAL_BYTES_V1,
            "archive_inventory_root": inventory_root,
            "archive_git_subtree": (
                attestation.PLAN0013_ARCHIVE_EVIDENCE_SUBTREE_V1
            ),
            "live_file_count": attestation.PLAN0013_ARCHIVE_FILE_COUNT_V1,
            "live_total_bytes": attestation.PLAN0013_ARCHIVE_TOTAL_BYTES_V1,
            "live_inventory_root": inventory_root,
            "live_git_subtree": (
                attestation.PLAN0013_ARCHIVE_EVIDENCE_SUBTREE_V1
            ),
            "excluded_operational_paths": [".locks", "contradictions"],
        },
        "bootstrap": {
            "bootstrap_root": attestation.PLAN0013_BOOTSTRAP_ROOT_V1,
            "protocol_root": attestation.PLAN0013_PROTOCOL_ROOT_V1,
            "protocol_body_ref": (
                attestation.PLAN0013_PROTOCOL_BODY_REF_V1.as_dict()
            ),
            "manifest_root": attestation.PLAN0013_MANIFEST_ROOT_V1,
            "source_commit": attestation.PLAN0013_SOURCE_COMMIT_V1,
            "source_tree": attestation.PLAN0013_SOURCE_TREE_V1,
        },
        "ordered_stage_terminals": terminal_values,
        "failed_assessment": {
            "reservation_id": attestation._ASSESSMENT_RESERVATION_ID_V1,
            "reservation_body_ref": (
                attestation._ASSESSMENT_RESERVATION_REF_V1.as_dict()
            ),
            "attempt_id": attestation._ASSESSMENT_ATTEMPT_ID_V1,
            "attempt_body_ref": attestation._ASSESSMENT_ATTEMPT_REF_V1.as_dict(),
            "failure_body_ref": attestation._ASSESSMENT_FAILURE_REF_V1.as_dict(),
            "production_closure_root": attestation._ASSESSMENT_CLOSURE_ROOT_V1,
            "embedded_parent_terminal_match_count": 5,
            "partial_evidence_root_or_null": None,
            "exception": {
                "exception_module": "builtins",
                "exception_type": "TypeError",
                "kind": "ASSESSMENT_STAGE_EXCEPTION",
                "message": "admissible slots must be an exact array",
            },
        },
    }
    return {
        "artifact_type": attestation.PLAN0014_SOURCE_BINDING_ARTIFACT_TYPE_V1,
        "identity": domain_identity(
            identity_domain_v1("source_binding_root"), payload
        ),
        "payload": payload,
    }


def _inner_report():
    return {
        "claim_level": "FAMILY_FRONTIER_SIGNAL_NOT_FAIR_GAME",
        "inspection_selection": {
            "selected_pair_count": 0,
            "selected_pairs": [],
        },
        "report_root": "2" * 64,
        "status": "FORMAL_COMPLETE",
    }


def _reseal_source(binding):
    binding["identity"] = domain_identity(
        identity_domain_v1("source_binding_root"), binding["payload"]
    )


def _reseal_outer(value):
    unsigned = dict(value)
    del unsigned["attestation_root"]
    value["attestation_root"] = domain_identity(
        identity_domain_v1("attestation_root"), unsigned
    )


def _run_regular_file_probe(parent, name, expected_size):
    source_root = Path(__file__).resolve().parents[1] / "src"
    environment = dict(os.environ)
    inherited = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = str(source_root) + (
        os.pathsep + inherited if inherited else ""
    )
    return subprocess.run(
        (
            sys.executable,
            "-c",
            """
import os
import sys

from parity_forge import atlas_assessment_reconstruction_attestation as target
from parity_forge.atlas_evidence import EvidenceIntegrityError

parent_fd = os.open(
    sys.argv[1],
    os.O_RDONLY
    | getattr(os, "O_DIRECTORY", 0)
    | getattr(os, "O_NOFOLLOW", 0)
    | getattr(os, "O_NONBLOCK", 0),
)
try:
    expected_size = None if sys.argv[3] == "none" else int(sys.argv[3])
    try:
        target._read_all_regular_at(
            parent_fd,
            sys.argv[2],
            expected_size=expected_size,
        )
    except EvidenceIntegrityError:
        pass
    else:
        raise AssertionError("unsafe source path was accepted")
finally:
    os.close(parent_fd)
""",
            str(parent),
            name,
            "none" if expected_size is None else str(expected_size),
        ),
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=2,
        env=environment,
    )


class AtlasAssessmentReconstructionAttestationTests(unittest.TestCase):
    def test_outer_attestation_golden_and_nested_refs(self):
        binding = _source_binding()
        inner = _inner_report()
        before = canonical_json_bytes(inner)

        value = attestation.build_plan0014_outer_attestation_v1(binding, inner)

        self.assertEqual(canonical_json_bytes(inner), before)
        self.assertEqual(
            value["inner_report"]["body_ref"],
            canonical_body_ref(inner).as_dict(),
        )
        self.assertEqual(
            value["inspection_selection"]["body_ref"],
            canonical_body_ref(inner["inspection_selection"]).as_dict(),
        )
        inspection_payload = {
            "inner_report_body_ref": canonical_body_ref(inner).as_dict(),
            "inspection_selection_body_ref": canonical_body_ref(
                inner["inspection_selection"]
            ).as_dict(),
            "inspection_selection": inner["inspection_selection"],
        }
        self.assertEqual(
            value["inspection_selection"]["root"],
            domain_identity(
                identity_domain_v1("inspection_selection_root"),
                inspection_payload,
            ),
        )
        self.assertEqual(
            value["execution_counts"],
            {
                "candidate_block_access_count": 0,
                "candidate_block_allocation_count": 0,
                "candidate_block_evaluation_count": 0,
                "candidate_block_export_count": 0,
                "outcome_generation_count": 0,
                "sampled_game_generation_count": 0,
                "solver_invocation_count": 0,
                "telemetry_generation_count": 0,
            },
        )
        self.assertEqual(value["original_stage_lifecycle"], "FAILED")
        self.assertEqual(
            value["original_stage_terminal_identity"],
            attestation._STAGE_PINS_V1[-1][3],
        )
        self.assertEqual(value["original_stage_completed_body_count"], 0)
        self.assertEqual(
            binding["identity"],
            "953ae6042fdeef6437344c4d7c5939ce344ac9e76e39d79b84b0f6a522eafd04",
        )
        self.assertEqual(
            value["inspection_selection"]["root"],
            "836c620efdeb0ec87731cdb71f996bbf8ff815575a48ab2cb1e4803928f70c2b",
        )
        self.assertEqual(
            value["attestation_root"],
            "203ee75e12a5c14e2d9fa53838097f1353d4ff8fccbbe5d4f5998acb8a7aef2c",
        )
        self.assertEqual(len(canonical_json_bytes(value)), 2003)
        self.assertEqual(
            value["epistemic_status"],
            "POST_FAILURE_MECHANICAL_RECONSTRUCTION_NOT_CONFIRMATION",
        )

    def test_outer_validation_rejects_self_consistent_promotions_and_substitution(self):
        binding = _source_binding()
        inner = _inner_report()
        expected = attestation.build_plan0014_outer_attestation_v1(binding, inner)
        attacks = []
        for path, replacement in (
            (("original_stage_lifecycle",), "COMPLETED"),
            (("epistemic_status",), "CONFIRMATION"),
            (("claim_level",), "FAIR_GAME"),
            (("repair_boundary", "scientific_rule_change_count"), 1),
            (("execution_counts", "sampled_game_generation_count"), 1),
            (("inner_report", "status"), "EVIDENCE_INVALID"),
            (("inspection_selection", "root"), "f" * 64),
        ):
            value = copy.deepcopy(expected)
            target = value
            for component in path[:-1]:
                target = target[component]
            target[path[-1]] = replacement
            _reseal_outer(value)
            attacks.append((path, value))
        for path, value in attacks:
            with self.subTest(path=path):
                with self.assertRaisesRegex(ValueError, "does not reconstruct"):
                    attestation.validate_plan0014_outer_attestation_v1(
                        value, binding, inner
                    )

    def test_inner_report_substitution_fails_even_with_resealed_outer(self):
        binding = _source_binding()
        inner = _inner_report()
        stored = attestation.build_plan0014_outer_attestation_v1(binding, inner)
        substituted = copy.deepcopy(inner)
        substituted["inspection_selection"]["selected_pair_count"] = 1
        substituted["inspection_selection"]["selected_pairs"] = [{"pair_index": 0}]
        with self.assertRaisesRegex(ValueError, "does not reconstruct"):
            attestation.validate_plan0014_outer_attestation_v1(
                stored, binding, substituted
            )

    def test_source_binding_rejects_resealed_fixed_chain_attacks(self):
        attacks = []
        cases = (
            (("archive", "commit"), "0" * 40),
            (("archive_live_inventory", "live_file_count"), 0),
            (
                ("archive_live_inventory", "excluded_operational_paths"),
                [".locks"],
            ),
            (("source_binding_version",), True),
            (("bootstrap", "manifest_root"), "0" * 64),
            (("ordered_stage_terminals", 5, "lifecycle"), "COMPLETED"),
            (("failed_assessment", "embedded_parent_terminal_match_count"), 4),
            (("failed_assessment", "partial_evidence_root_or_null"), "0" * 64),
            (("failed_assessment", "exception", "message"), "different"),
        )
        for path, replacement in cases:
            value = _source_binding()
            target = value["payload"]
            for component in path[:-1]:
                target = target[component]
            target[path[-1]] = replacement
            _reseal_source(value)
            attacks.append((path, value))
        for path, value in attacks:
            with self.subTest(path=path):
                with self.assertRaises((TypeError, ValueError)):
                    attestation._validate_source_binding_shape_v1(value)

    def test_reconstruction_uses_one_source_session_and_embeds_inner_unchanged(self):
        binding = _source_binding()
        inner = _inner_report()
        session = SimpleNamespace()
        inputs = object()
        manager = mock.MagicMock()
        manager.__enter__.return_value = session
        manager.__exit__.return_value = None
        open_mock = mock.Mock(return_value=manager)
        source_mock = mock.Mock(return_value=(binding, inputs))
        inner_mock = mock.Mock(return_value=inner)
        with mock.patch.multiple(
            attestation,
            open_plan0013_assessment_source_session_v1=open_mock,
            _source_binding_from_session_v1=source_mock,
            _inner_report_from_inputs_v1=inner_mock,
        ):
            result = attestation.reconstruct_plan0014_assessment_artifacts_v1(
                "/fixed/repository"
            )
        self.assertIs(result["result"]["inner_report"], inner)
        self.assertEqual(source_mock.call_args_list, [mock.call(session), mock.call(session)])
        inner_mock.assert_called_once_with(session, inputs)
        self.assertEqual(
            result["result"]["outer_attestation"]["inner_report"]["body_ref"],
            canonical_body_ref(inner).as_dict(),
        )

    def test_source_session_binds_store_and_inventory_to_same_descriptor(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        repository = Path(temporary.name).resolve()
        subprocess.run(("git", "init", "-q", str(repository)), check=True)
        evidence_root = (
            repository / attestation.PLAN0013_ATLAS_EVIDENCE_ROOT_RELATIVE_V1
        )
        (evidence_root / "stages").mkdir(parents=True)
        (evidence_root / "manifest-bootstrap").mkdir()
        store = mock.MagicMock()
        store.__enter__.return_value = store
        store.__exit__.return_value = None
        factory = mock.Mock(return_value=store)
        with mock.patch.object(
            attestation.ImmutableEvidenceStore,
            "from_read_only_directory_fd",
            factory,
        ):
            with attestation.open_plan0013_assessment_source_session_v1(
                str(repository)
            ) as session:
                passed_fd = factory.call_args.args[1]
                self.assertEqual(session.evidence_root_fd, passed_fd)
                self.assertIs(session.store, store)
                os.fstat(session.evidence_root_fd)
        with self.assertRaises(OSError):
            os.fstat(passed_fd)

    def test_live_inventory_rejects_path_link_and_mode_attacks(self):
        for attack in (
            "symlink",
            "hardlink",
            "unknown",
            "artifact-mode",
            "lock-mode",
            "directory-mode",
            "root-mode",
        ):
            with self.subTest(attack=attack):
                temporary = tempfile.TemporaryDirectory()
                self.addCleanup(temporary.cleanup)
                root = Path(temporary.name)
                for name in (".locks", "contradictions", "manifest-bootstrap", "stages"):
                    (root / name).mkdir()
                for lock in attestation._EXPECTED_LOCK_FILES_V1:
                    path = root / ".locks" / lock
                    path.touch(mode=0o600)
                body = root / "manifest-bootstrap" / "body.json"
                body.write_bytes(b"{}")
                body.chmod(0o400)
                if attack == "symlink":
                    (root / "stages" / "bad").symlink_to(body)
                elif attack == "hardlink":
                    os.link(body, root / "stages" / "bad")
                elif attack == "unknown":
                    (root / "unknown").mkdir()
                elif attack == "artifact-mode":
                    body.chmod(0o600)
                elif attack == "lock-mode":
                    next(iter((root / ".locks").iterdir())).chmod(0o644)
                elif attack == "directory-mode":
                    (root / "stages").chmod(0o777)
                else:
                    root.chmod(0o777)
                fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    with self.assertRaises((OSError, EvidenceIntegrityError)):
                        attestation._live_inventory_records_v1(fd)
                finally:
                    os.close(fd)

    def test_regular_reader_rejects_special_paths_without_blocking(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)

        fifo = root / "source-fifo"
        os.mkfifo(fifo, mode=0o400)
        completed = _run_regular_file_probe(root, fifo.name, 0)
        self.assertEqual(completed.returncode, 0, completed.stderr)

        socket_path = root / "source-socket"
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(str(socket_path))
            completed = _run_regular_file_probe(root, socket_path.name, 0)
        self.assertEqual(completed.returncode, 0, completed.stderr)

        completed = _run_regular_file_probe(Path("/dev"), "null", 0)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_regular_reader_enforces_exact_and_unpinned_size_bounds(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)

        wrong_size = root / "wrong-size.json"
        wrong_size.write_bytes(b"x")
        completed = _run_regular_file_probe(root, wrong_size.name, 0)
        self.assertEqual(completed.returncode, 0, completed.stderr)

        oversized = root / "oversized.json"
        with oversized.open("wb") as stream:
            stream.truncate(attestation._MAX_UNPINNED_SOURCE_FILE_BYTES_V1 + 1)
        completed = _run_regular_file_probe(root, oversized.name, None)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_archive_and_live_inventory_match_on_small_real_git_fixture(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        repository = Path(temporary.name).resolve()
        subprocess.run(("git", "init", "-q", str(repository)), check=True)
        subprocess.run(
            ("git", "-C", str(repository), "config", "user.email", "test@example.invalid"),
            check=True,
        )
        subprocess.run(
            ("git", "-C", str(repository), "config", "user.name", "Test"),
            check=True,
        )
        subprocess.run(
            (
                "git",
                "-C",
                str(repository),
                "commit",
                "--allow-empty",
                "-qm",
                "source",
            ),
            check=True,
        )
        source_commit = subprocess.run(
            ("git", "-C", str(repository), "rev-parse", "HEAD"),
            check=True,
            stdout=subprocess.PIPE,
        ).stdout.decode().strip()
        source_tree = subprocess.run(
            ("git", "-C", str(repository), "rev-parse", "HEAD^{tree}"),
            check=True,
            stdout=subprocess.PIPE,
        ).stdout.decode().strip()
        root = repository / attestation.PLAN0013_ATLAS_EVIDENCE_ROOT_RELATIVE_V1
        for name in (".locks", "contradictions", "manifest-bootstrap", "stages"):
            (root / name).mkdir(parents=True, exist_ok=True)
        contents = {
            root / "manifest-bootstrap" / "catalog.json": b"{}",
            root / "stages" / "body.json": b'{"value":1}',
        }
        for path, raw in contents.items():
            path.write_bytes(raw)
        subprocess.run(("git", "-C", str(repository), "add", "."), check=True)
        subprocess.run(
            ("git", "-C", str(repository), "commit", "-qm", "fixture"), check=True
        )
        for path in contents:
            path.chmod(0o400)
        for lock in attestation._EXPECTED_LOCK_FILES_V1:
            path = root / ".locks" / lock
            path.touch(mode=0o600)
        archive_commit = subprocess.run(
            ("git", "-C", str(repository), "rev-parse", "HEAD"),
            check=True,
            stdout=subprocess.PIPE,
        ).stdout.decode().strip()
        archive_tree = subprocess.run(
            ("git", "-C", str(repository), "rev-parse", "HEAD^{tree}"),
            check=True,
            stdout=subprocess.PIPE,
        ).stdout.decode().strip()
        subprocess.run(
            (
                "git",
                "-C",
                str(repository),
                "commit",
                "--allow-empty",
                "-qm",
                "repair checkpoint",
            ),
            check=True,
        )
        repair_commit = subprocess.run(
            ("git", "-C", str(repository), "rev-parse", "HEAD"),
            check=True,
            stdout=subprocess.PIPE,
        ).stdout.decode().strip()
        repair_tree = subprocess.run(
            ("git", "-C", str(repository), "rev-parse", "HEAD^{tree}"),
            check=True,
            stdout=subprocess.PIPE,
        ).stdout.decode().strip()
        subtree = subprocess.run(
            (
                "git",
                "-C",
                str(repository),
                "rev-parse",
                "HEAD:" + attestation.PLAN0013_ATLAS_EVIDENCE_ROOT_RELATIVE_V1,
            ),
            check=True,
            stdout=subprocess.PIPE,
        ).stdout.decode().strip()
        root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        session = SimpleNamespace(repository=repository, evidence_root_fd=root_fd)
        try:
            with mock.patch.multiple(
                attestation,
                PLAN0013_ARCHIVE_COMMIT_V1=archive_commit,
                PLAN0013_ARCHIVE_TREE_V1=archive_tree,
                PLAN0013_ARCHIVE_EVIDENCE_SUBTREE_V1=subtree,
                PLAN0013_SOURCE_COMMIT_V1=source_commit,
                PLAN0013_SOURCE_TREE_V1=source_tree,
                PLAN0014_REPAIR_CHECKPOINT_COMMIT_V1=repair_commit,
                PLAN0014_REPAIR_CHECKPOINT_TREE_V1=repair_tree,
                PLAN0013_ARCHIVE_FILE_COUNT_V1=len(contents),
                PLAN0013_ARCHIVE_TOTAL_BYTES_V1=sum(map(len, contents.values())),
            ):
                observed = attestation._archive_live_inventory_v1(session)
                for lock_path in (root / ".locks").iterdir():
                    lock_path.unlink()
                (root / ".locks").rmdir()
                (root / "contradictions").rmdir()
                root.chmod(0o755)
                (root / "manifest-bootstrap").chmod(0o755)
                (root / "stages").chmod(0o755)
                for path in contents:
                    path.chmod(0o644)
                without_operational_dirs = (
                    attestation._archive_live_inventory_v1(session)
                )
        finally:
            os.close(root_fd)
        self.assertEqual(observed["archive_file_count"], 2)
        self.assertEqual(observed["live_file_count"], 2)
        self.assertEqual(
            observed["archive_inventory_root"], observed["live_inventory_root"]
        )
        self.assertEqual(without_operational_dirs, observed)

    def test_module_has_no_write_or_gameplay_import(self):
        source = Path(attestation.__file__).read_text(encoding="utf-8")
        for forbidden in (
            "atlas_assessment_stage",
            "atlas_exact_stage",
            "atlas_random_stage",
            "atlas_depth1_stage",
            "atlas_telemetry_stage",
            "atlas_selector",
            "from .agents",
            "from .solver",
            "from .play",
            "seal_completed_stage",
            "seal_failed_stage",
            "recover_stage",
            "publish_json",
            "publish_bytes",
        ):
            self.assertNotIn(forbidden, source)
        for write_flag in ("os.O_CREAT", "os.O_WRONLY", "os.O_RDWR"):
            self.assertNotIn(write_flag, source)


@unittest.skipUnless(
    os.environ.get("PARITY_FORGE_RUN_PLAN0014_REAL_ATTESTATION") == "1",
    "real archived V2 reconstruction is opt-in",
)
class AtlasAssessmentReconstructionAttestationRealTests(unittest.TestCase):
    def test_real_source_and_inner_golden(self):
        repository = Path(__file__).resolve().parents[1]
        artifacts = attestation.reconstruct_plan0014_assessment_artifacts_v1(
            str(repository)
        )
        source_binding = artifacts["source_binding"]
        inner = artifacts["result"]["inner_report"]
        outer = artifacts["result"]["outer_attestation"]
        self.assertEqual(
            source_binding["identity"],
            "f763bad5ca0c0d1a82aa879aa0cc08fb47b0920effe27899ef85b0dac21e5157",
        )
        self.assertEqual(
            source_binding["payload"]["archive_live_inventory"],
            {
                "archive_file_count": 152680,
                "archive_git_subtree": "40f4b65f913a842a43e1b3a092a40cbb9933e489",
                "archive_inventory_root": "773941af8b9982f3ca365e6d26c5e7967eb2b3f5fc0fecc212c255e6e15cd612",
                "archive_total_bytes": 601787372,
                "excluded_operational_paths": [".locks", "contradictions"],
                "live_file_count": 152680,
                "live_git_subtree": "40f4b65f913a842a43e1b3a092a40cbb9933e489",
                "live_inventory_root": "773941af8b9982f3ca365e6d26c5e7967eb2b3f5fc0fecc212c255e6e15cd612",
                "live_total_bytes": 601787372,
            },
        )
        self.assertEqual(
            canonical_body_ref(inner).as_dict(),
            {
                "byte_count": 278393,
                "sha256": "4acd5dda387b3d5876b03a8ba6fe2dcc2cb40c18c0fa44f0c17e18163b6027c0",
            },
        )
        self.assertEqual(
            inner["report_root"],
            "2a873b0b1d11e9ffb617792d41c870e1fb0fe32f4f2c7b6aa5fdfeb5d215484d",
        )
        self.assertEqual(
            outer["inspection_selection"]["body_ref"],
            {
                "byte_count": 104458,
                "sha256": "0fc525939d67cbf426704e28b7383fa1b92aa14d6f497cbaaf7d136be3803c7e",
            },
        )


if __name__ == "__main__":
    unittest.main()
