import ast
import copy
import hashlib
import inspect
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from parity_forge import atlas_assessment_reconstruction_protocol as protocol
from parity_forge.atlas_evidence import (
    EvidenceIntegrityError,
    canonical_json_bytes,
    domain_identity,
)


class _DictSubclass(dict):
    pass


def _git(repository, *arguments, check=True):
    return subprocess.run(
        ("git", "-C", str(repository), *arguments),
        check=check,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ).stdout.strip()


def _run_current_regular_probe(repository, path, expected_size):
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
import sys
from pathlib import Path

from parity_forge import atlas_assessment_reconstruction_protocol as target
from parity_forge.atlas_evidence import EvidenceIntegrityError

try:
    target._read_current_regular(Path(sys.argv[1]), sys.argv[2], int(sys.argv[3]))
except EvidenceIntegrityError:
    pass
else:
    raise AssertionError("unsafe current source path was accepted")
""",
            str(repository),
            path,
            str(expected_size),
        ),
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=2,
        env=environment,
    )


class Plan0014AssessmentReconstructionProtocolTests(unittest.TestCase):
    def test_fixed_identities_paths_and_literal_goldens(self):
        self.assertEqual(
            protocol.PLAN0014_RECONSTRUCTION_PROTOCOL_ID_V1,
            "plan0014-plan0013-assessment-reconstruction-protocol-v1",
        )
        self.assertEqual(
            protocol.EVIDENCE_PROTOCOL_ID_V1,
            "plan0014-plan0013-assessment-reconstruction-evidence-v1",
        )
        self.assertEqual(
            protocol.STAGE_ID_V1,
            "PLAN0013_ASSESSMENT_RECONSTRUCTION",
        )
        self.assertEqual(
            protocol.STAGE_PROTOCOL_ID_V1,
            "plan0014-plan0013-assessment-reconstruction-stage-v1",
        )
        self.assertEqual(
            protocol.EVIDENCE_ROOT_RELATIVE_V1,
            "experiments/runs/plan0014-plan0013-assessment-reconstruction-evidence-v1",
        )
        self.assertEqual(
            protocol.ACTIVE_PLAN_PATH_V1,
            "docs/plans/active/0014-post-outcome-atlas-assessment-reconstruction.md",
        )
        self.assertEqual(
            protocol.REPAIR_PROTOCOL_ID_V1,
            "plan0014-two-defect-assessment-repair-v1",
        )
        self.assertEqual(
            protocol.REPAIR_PROTOCOL_ROOT_V1,
            "4dcc7ee7663c1b1975c13b6bded28d6ff66d4273cc529d97e111b645bfe6f9dc",
        )
        self.assertEqual(
            protocol.PLAN0014_RECONSTRUCTION_PROTOCOL_ROOT_V1,
            "b412e0af7f36850f06199a3d21897195b26d1eb4ef417616debca57a3185d38d",
        )
        self.assertEqual(
            protocol.PLAN0014_RECONSTRUCTION_PROTOCOL_CANONICAL_SHA256_V1,
            "0aeb2bf4a3e6d0caa048f4e4238981738ebfb0287c63f938e86b47d9984ecfd1",
        )
        self.assertEqual(
            protocol.PLAN0014_REJECTED_IMPLEMENTATION_PROTOCOL_ROOT_V1,
            "5424b2d066843f5e52d70e8395ed594dda1760c3447080e7b515dbccb78f8458",
        )
        self.assertEqual(
            protocol.PLAN0014_REJECTED_IMPLEMENTATION_PROTOCOL_CANONICAL_SHA256_V1,
            "adb409bac1bdc2eb80e8331b29238b89f41fe3705b9137947d90b0bbb4f6fa88",
        )

    def test_protocol_reconstructs_both_golden_roots_and_sha(self):
        value = protocol.build_plan0014_assessment_reconstruction_protocol_v1()
        unsigned = dict(value)
        del unsigned["protocol_root"]
        self.assertEqual(
            domain_identity(protocol.identity_domain_v1("protocol_root"), unsigned),
            protocol.PLAN0014_RECONSTRUCTION_PROTOCOL_ROOT_V1,
        )
        self.assertEqual(
            hashlib.sha256(canonical_json_bytes(value)).hexdigest(),
            protocol.PLAN0014_RECONSTRUCTION_PROTOCOL_CANONICAL_SHA256_V1,
        )
        repair = dict(value["repair_protocol"])
        del repair["repair_protocol_root"]
        self.assertEqual(
            tuple(sorted(repair)),
            tuple(sorted(protocol.identity_payload_keys_v1("repair_protocol_root"))),
        )
        self.assertEqual(
            domain_identity(
                protocol.identity_domain_v1("repair_protocol_root"), repair
            ),
            protocol.REPAIR_PROTOCOL_ROOT_V1,
        )
        self.assertEqual(len(canonical_json_bytes(value)), 16_880)

    def test_every_domain_uses_one_plan0014_prefix_and_exact_schema(self):
        value = protocol.build_plan0014_assessment_reconstruction_protocol_v1()
        expected_prefix = (
            b"parity-forge:plan0014:plan0013-assessment-reconstruction:"
        )
        self.assertEqual(set(value["identity_schemas"]), set(protocol._IDENTITY_DOMAINS_V1))
        for kind, schema in value["identity_schemas"].items():
            with self.subTest(kind=kind):
                domain = protocol.identity_domain_v1(kind)
                self.assertTrue(domain.startswith(expected_prefix))
                self.assertTrue(domain.endswith(b":v1\0"))
                self.assertEqual(domain.hex(), schema["domain_hex"])
                self.assertEqual(
                    tuple(schema["payload_keys"]),
                    protocol.identity_payload_keys_v1(kind),
                )
                self.assertEqual(
                    len(schema["payload_keys"]),
                    len(set(schema["payload_keys"])),
                )
        self.assertEqual(
            protocol.identity_payload_keys_v1("archive_live_inventory_root"),
            ("ordered_file_records",),
        )

    def test_unknown_and_nonexact_identity_kinds_fail_closed(self):
        for function in (protocol.identity_domain_v1, protocol.identity_payload_keys_v1):
            with self.subTest(function=function.__name__):
                with self.assertRaises(TypeError):
                    function(None)
                with self.assertRaises(ValueError):
                    function("unknown")

    def test_protocol_validator_rejects_mutation_shape_and_exact_type_drift(self):
        original = protocol.build_plan0014_assessment_reconstruction_protocol_v1()
        mutations = []
        removed = copy.deepcopy(original)
        del removed["stage"]
        mutations.append(removed)
        extra = copy.deepcopy(original)
        extra["extra"] = None
        mutations.append(extra)
        wrong_root = copy.deepcopy(original)
        wrong_root["protocol_root"] = "0" * 64
        mutations.append(wrong_root)
        wrong_defects = copy.deepcopy(original)
        wrong_defects["repair_protocol"]["closed_defect_ids"].reverse()
        mutations.append(wrong_defects)
        wrong_equation = copy.deepcopy(original)
        wrong_equation["repair_protocol"]["repairs"][1]["identities"][0] = "changed"
        mutations.append(wrong_equation)
        wrong_zero = copy.deepcopy(original)
        wrong_zero["repair_protocol"]["scientific_rule_change_count"] = False
        mutations.append(wrong_zero)
        wrong_container = copy.deepcopy(original)
        wrong_container["stage"]["commands"] = ("run", "recover")
        mutations.append(wrong_container)
        subclass = _DictSubclass(copy.deepcopy(original))
        mutations.append(subclass)
        for index, value in enumerate(mutations):
            with self.subTest(index=index):
                with self.assertRaises(EvidenceIntegrityError):
                    protocol.validate_plan0014_assessment_reconstruction_protocol_v1(
                        value
                    )
        validated = protocol.validate_plan0014_assessment_reconstruction_protocol_v1(
            original
        )
        self.assertEqual(validated, original)
        self.assertIsNot(validated, original)

    def test_two_repairs_and_epistemic_boundary_are_exact(self):
        value = protocol.build_plan0014_assessment_reconstruction_protocol_v1()
        repair = value["repair_protocol"]
        self.assertEqual(
            tuple(repair["closed_defect_ids"]), protocol.CLOSED_DEFECT_IDS_V1
        )
        self.assertEqual(repair["integration_correction_count"], 2)
        self.assertIs(type(repair["integration_correction_count"]), int)
        self.assertEqual(repair["scientific_rule_change_count"], 0)
        self.assertEqual(
            repair["repairs"][1]["identities"],
            [
                "sum(legal_count_bins)==legal_observation_count",
                "bin[1]+bin[2+]==decision_count",
                "legal_observation_count==decision_count+bin[0]",
            ],
        )
        attestation = value["attestation_contract"]
        self.assertEqual(attestation["original_stage_lifecycle"], "FAILED")
        self.assertEqual(
            attestation["epistemic_status"],
            "POST_FAILURE_MECHANICAL_RECONSTRUCTION_NOT_CONFIRMATION",
        )
        self.assertFalse(attestation["protocol_pins_outcome_digest"])
        self.assertNotIn("report_root", canonical_json_bytes(value).decode("utf-8"))

        chain = value["source_chain"]
        rejected = chain["rejected_initial_implementation"]
        self.assertEqual(rejected["status"], "REJECTED_PRE_RUN")
        self.assertEqual(rejected["production_invocation_count"], 0)
        self.assertEqual(
            rejected["protocol_root"],
            protocol.PLAN0014_REJECTED_IMPLEMENTATION_PROTOCOL_ROOT_V1,
        )
        hardening = chain["reader_hardening_checkpoint"]
        self.assertEqual(hardening["scientific_rule_change_count"], 0)
        self.assertEqual(hardening["assessment_integration_correction_count"], 0)
        self.assertEqual(
            hardening["hardening_id"],
            protocol.PLAN0014_READER_HARDENING_PROTOCOL_ID_V1,
        )
        self.assertEqual(
            chain["final_source_contract"]["exact_single_parent_commit"],
            protocol.PLAN0014_READER_HARDENING_CHECKPOINT_COMMIT_V1,
        )
        self.assertEqual(
            len(protocol.PLAN0014_REPAIR_PRODUCTION_EQUIVALENCE_BLOBS_V1),
            3,
        )
        self.assertEqual(
            len(
                protocol.PLAN0014_READER_HARDENING_PRODUCTION_EQUIVALENCE_BLOBS_V1
            ),
            4,
        )
        self.assertNotIn(
            "src/parity_forge/atlas_assessment_reconstruction_protocol.py",
            dict(
                protocol.PLAN0014_READER_HARDENING_PRODUCTION_EQUIVALENCE_BLOBS_V1
            ),
        )

    def test_capability_zero_names_do_not_deny_frozen_inspection_calculation(self):
        value = protocol.build_plan0014_assessment_reconstruction_protocol_v1()
        names = value["capability_contract"]["zero_count_names"]
        self.assertEqual(
            names,
            [
                "outcome_generation_count",
                "solver_invocation_count",
                "sampled_game_generation_count",
                "telemetry_generation_count",
                "candidate_block_access_count",
                "candidate_block_export_count",
                "candidate_block_evaluation_count",
                "candidate_block_allocation_count",
            ],
        )
        self.assertNotIn("selection_call_count", names)
        self.assertNotIn("inspection_selection_call_count", names)
        self.assertIn(
            "reconstruct-frozen-report-and-inspection",
            value["capability_contract"]["allowed"],
        )

    def test_archive_protocol_is_compact_but_fixes_calculation_denominators(self):
        archive = protocol.build_plan0014_assessment_reconstruction_protocol_v1()[
            "source_chain"
        ]["archive"]
        self.assertEqual(archive["tracked_evidence_file_count"], 152_680)
        self.assertEqual(archive["tracked_evidence_total_blob_bytes"], 601_787_372)
        self.assertEqual(
            archive["live_inventory_calculation_record_keys"],
            ["path", "mode", "git_blob_sha1", "byte_count"],
        )
        self.assertEqual(
            archive["live_inventory_persistence"],
            "COMPACT-ROOT-COUNT-TOTAL-BYTES-ONLY-NO-ORDERED-RECORDS",
        )

    def test_fixed_git_archive_source_repair_and_body_refs_exist(self):
        repository = Path(__file__).resolve().parents[1]
        self.assertEqual(
            _git(repository, "rev-parse", protocol.PLAN0013_SOURCE_COMMIT_V1 + "^{tree}"),
            protocol.PLAN0013_SOURCE_TREE_V1,
        )
        self.assertEqual(
            _git(repository, "rev-parse", protocol.PLAN0013_ARCHIVE_COMMIT_V1 + "^{tree}"),
            protocol.PLAN0013_ARCHIVE_TREE_V1,
        )
        self.assertEqual(
            _git(
                repository,
                "rev-parse",
                protocol.PLAN0013_ARCHIVE_COMMIT_V1
                + ":"
                + protocol.PLAN0013_EVIDENCE_ROOT_RELATIVE_V1,
            ),
            protocol.PLAN0013_ARCHIVED_EVIDENCE_TREE_V1,
        )
        self.assertEqual(
            _git(
                repository,
                "show",
                "-s",
                "--format=%P",
                protocol.PLAN0013_ARCHIVE_COMMIT_V1,
            ),
            protocol.PLAN0013_SOURCE_COMMIT_V1,
        )
        self.assertEqual(
            _git(
                repository,
                "rev-parse",
                protocol.PLAN0014_REPAIR_CHECKPOINT_COMMIT_V1 + "^{tree}",
            ),
            protocol.PLAN0014_REPAIR_CHECKPOINT_TREE_V1,
        )
        self.assertEqual(
            _git(
                repository,
                "show",
                "-s",
                "--format=%P",
                protocol.PLAN0014_REPAIR_CHECKPOINT_COMMIT_V1,
            ),
            protocol.PLAN0013_ARCHIVE_COMMIT_V1,
        )
        self.assertEqual(
            _git(
                repository,
                "rev-parse",
                protocol.PLAN0014_REJECTED_IMPLEMENTATION_CHECKPOINT_COMMIT_V1
                + "^{tree}",
            ),
            protocol.PLAN0014_REJECTED_IMPLEMENTATION_CHECKPOINT_TREE_V1,
        )
        self.assertEqual(
            _git(
                repository,
                "show",
                "-s",
                "--format=%P",
                protocol.PLAN0014_REJECTED_IMPLEMENTATION_CHECKPOINT_COMMIT_V1,
            ),
            protocol.PLAN0014_REPAIR_CHECKPOINT_COMMIT_V1,
        )
        self.assertEqual(
            _git(
                repository,
                "rev-parse",
                protocol.PLAN0014_READER_HARDENING_CHECKPOINT_COMMIT_V1
                + "^{tree}",
            ),
            protocol.PLAN0014_READER_HARDENING_CHECKPOINT_TREE_V1,
        )
        self.assertEqual(
            _git(
                repository,
                "show",
                "-s",
                "--format=%P",
                protocol.PLAN0014_READER_HARDENING_CHECKPOINT_COMMIT_V1,
            ),
            protocol.PLAN0014_REJECTED_IMPLEMENTATION_CHECKPOINT_COMMIT_V1,
        )
        self.assertEqual(
            tuple(
                _git(
                    repository,
                    "diff-tree",
                    "--no-commit-id",
                    "--name-only",
                    "--no-renames",
                    "-r",
                    protocol.PLAN0014_READER_HARDENING_CHECKPOINT_COMMIT_V1,
                ).splitlines()
            ),
            protocol.PLAN0014_READER_HARDENING_CHECKPOINT_CHANGED_PATHS_V1,
        )
        for path, blob in protocol.PLAN0014_REPAIR_CHECKPOINT_BLOBS_V1:
            with self.subTest(path=path):
                self.assertEqual(
                    _git(
                        repository,
                        "rev-parse",
                        protocol.PLAN0014_REPAIR_CHECKPOINT_COMMIT_V1 + ":" + path,
                    ),
                    blob,
                )
        for path, blob in protocol.PLAN0014_READER_HARDENING_CHECKPOINT_BLOBS_V1:
            with self.subTest(reader_hardening=path):
                self.assertEqual(
                    _git(
                        repository,
                        "rev-parse",
                        protocol.PLAN0014_READER_HARDENING_CHECKPOINT_COMMIT_V1
                        + ":"
                        + path,
                    ),
                    blob,
                )
        for (
            path,
            blob,
        ) in protocol.PLAN0014_UNCHANGED_PRODUCTION_DEPENDENCY_BLOBS_V1:
            with self.subTest(unchanged_dependency=path):
                self.assertEqual(
                    _git(
                        repository,
                        "rev-parse",
                        protocol.PLAN0014_REPAIR_CHECKPOINT_COMMIT_V1 + ":" + path,
                    ),
                    blob,
                )

        root = repository / protocol.PLAN0013_EVIDENCE_ROOT_RELATIVE_V1
        for terminal, reference in zip(
            protocol.PLAN0013_ORDERED_TERMINALS_V1,
            protocol.PLAN0013_ORDERED_TERMINAL_REFS_V1,
        ):
            stage_protocol_id = terminal[1]
            raw = (root / "stages" / stage_protocol_id / "terminal-seal.json").read_bytes()
            self.assertEqual((hashlib.sha256(raw).hexdigest(), len(raw)), reference)
        assessment = root / "stages" / protocol.PLAN0013_ORDERED_TERMINALS_V1[-1][1]
        for name, reference in (
            ("reservation.json", protocol.PLAN0013_ASSESSMENT_RESERVATION_REF_V1),
            ("attempt.json", protocol.PLAN0013_ASSESSMENT_ATTEMPT_REF_V1),
            ("failure.json", protocol.PLAN0013_ASSESSMENT_FAILURE_REF_V1),
        ):
            raw = (assessment / name).read_bytes()
            self.assertEqual(
                {"byte_count": len(raw), "sha256": hashlib.sha256(raw).hexdigest()},
                reference,
            )

    def test_public_closure_api_is_noninjectable(self):
        self.assertEqual(
            tuple(inspect.signature(protocol.build_plan0014_production_closure_v1).parameters),
            ("repository",),
        )
        self.assertEqual(
            tuple(inspect.signature(protocol.validate_plan0014_production_closure_v1).parameters),
            ("repository", "value"),
        )
        self.assertEqual(
            tuple(inspect.signature(protocol.reseal_plan0014_production_closure_v1).parameters),
            ("repository", "value"),
        )

    def test_recursive_closure_contract_is_exact_and_forbids_old_execution_paths(self):
        self.assertEqual(
            protocol.PRODUCTION_CLOSURE_PATHS_V1,
            tuple(sorted(protocol.PRODUCTION_CLOSURE_PATHS_V1)),
        )
        self.assertEqual(len(protocol.PRODUCTION_CLOSURE_PATHS_V1), 13)
        self.assertIn(
            "src/parity_forge/atlas_assessment_reconstruction_stage.py",
            protocol.PRODUCTION_CLOSURE_PATHS_V1,
        )
        self.assertIn(
            "src/parity_forge/engine.py", protocol.PRODUCTION_CLOSURE_PATHS_V1
        )
        self.assertNotIn(
            "src/parity_forge/atlas_assessment_stage.py",
            protocol.PRODUCTION_CLOSURE_PATHS_V1,
        )
        self.assertFalse(
            set(protocol.PRODUCTION_CLOSURE_PATHS_V1).intersection(
                protocol.PRODUCTION_FORBIDDEN_PATHS_V1
            )
        )

        source_path = Path(protocol.__file__)
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        imported = set()
        called = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.rsplit(".", 1)[-1])
            elif isinstance(node, ast.Import):
                imported.update(alias.name.rsplit(".", 1)[-1] for alias in node.names)
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    called.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    called.add(node.func.attr)
        self.assertFalse(
            {
                "agents",
                "atlas_assessment_stage",
                "atlas_depth1_stage",
                "atlas_exact_stage",
                "atlas_manifest_stage",
                "atlas_random_stage",
                "atlas_telemetry_stage",
                "play",
                "solver",
                "terminal_search",
            }.intersection(imported)
        )
        self.assertFalse(
            {
                "run_atlas_assessment_stage_v1",
                "recover_atlas_assessment_stage_v1",
                "solve",
                "play_game",
            }.intersection(called)
        )


class Plan0014ProductionClosureSyntheticGitTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repository = Path(temporary.name).resolve()
        _git(self.repository, "init")
        _git(self.repository, "config", "user.email", "test@example.invalid")
        _git(self.repository, "config", "user.name", "Plan 0014 Test")
        self._write_fixture()
        _git(self.repository, "add", ".")
        _git(self.repository, "commit", "-m", "production fixture")
        self.source_commit = _git(self.repository, "rev-parse", "HEAD^{commit}")
        self.source_tree = _git(self.repository, "rev-parse", "HEAD^{tree}")
        self.archive_subtree = _git(
            self.repository,
            "rev-parse",
            "HEAD:" + protocol.PLAN0013_EVIDENCE_ROOT_RELATIVE_V1,
        )
        self.repair_production_blobs = tuple(
            (
                path,
                _git(self.repository, "rev-parse", "HEAD:" + path),
            )
            for path, _blob in (
                protocol.PLAN0014_REPAIR_PRODUCTION_EQUIVALENCE_BLOBS_V1
            )
        )
        self.reader_hardening_production_blobs = tuple(
            (
                path,
                _git(self.repository, "rev-parse", "HEAD:" + path),
            )
            for path, _blob in (
                protocol.PLAN0014_READER_HARDENING_PRODUCTION_EQUIVALENCE_BLOBS_V1
            )
        )
        self.unchanged_dependency_blobs = tuple(
            (
                path,
                _git(self.repository, "rev-parse", "HEAD:" + path),
            )
            for path, _blob in (
                protocol.PLAN0014_UNCHANGED_PRODUCTION_DEPENDENCY_BLOBS_V1
            )
        )

    def _write(self, relative, text="X = 1\n"):
        path = self.repository / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def _write_fixture(self):
        imports = {
            "src/parity_forge/__init__.py": (
                "from .dsl import X\nfrom .engine import X\n"
            ),
            "src/parity_forge/atlas_assessment_reconstruction_stage.py": (
                "from .atlas_assessment_reconstruction_attestation import X\n"
                "from .atlas_assessment_reconstruction_evidence import X\n"
                "from .atlas_assessment_reconstruction_protocol import X\n"
                "from .atlas_assessment_reconstruction import X\n"
            ),
            "src/parity_forge/atlas_assessment_reconstruction_attestation.py": (
                "from .atlas_assessment_reconstruction_protocol import X\n"
            ),
            "src/parity_forge/atlas_assessment_reconstruction_evidence.py": (
                "from .atlas_evidence import X\n"
            ),
            "src/parity_forge/atlas_assessment_reconstruction_protocol.py": (
                "from .atlas_evidence import X\n"
            ),
            "src/parity_forge/atlas_assessment_reconstruction.py": (
                "from .atlas_assessment_core import X\n"
                "from .atlas_evidence import X\n"
            ),
            "src/parity_forge/atlas_assessment_core.py": (
                "from .atlas_protocol import X\nfrom .atlas_stage_data import X\n"
            ),
            "src/parity_forge/atlas_evidence.py": "from .atlas_protocol import X\n",
            "src/parity_forge/atlas_protocol.py": "X = 1\n",
            "src/parity_forge/atlas_stage_data.py": (
                "from .dsl import X\nfrom .engine import X\nfrom .symmetry import X\n"
            ),
            "src/parity_forge/dsl.py": "X = 1\n",
            "src/parity_forge/engine.py": "from .dsl import X\n",
            "src/parity_forge/symmetry.py": "from .dsl import X\n",
        }
        self.assertEqual(set(imports), set(protocol.PRODUCTION_CLOSURE_PATHS_V1))
        for relative, text in imports.items():
            self._write(relative, text)
        # The historical facade is bound at the repair checkpoint but remains
        # deliberately outside (and forbidden from) the production closure.
        self._write("src/parity_forge/atlas_assessment_stage.py", "X = 1\n")
        self._write(protocol.ACTIVE_PLAN_PATH_V1, "# synthetic plan\n")
        self._write(
            protocol.PLAN0013_EVIDENCE_ROOT_RELATIVE_V1 + "/sentinel.json",
            "{}\n",
        )

    def _patches(self):
        return (
            mock.patch.object(protocol, "_require_fixed_git_chain"),
            mock.patch.object(
                protocol,
                "PLAN0013_ARCHIVED_EVIDENCE_TREE_V1",
                self.archive_subtree,
            ),
            mock.patch.object(
                protocol,
                "PLAN0014_REPAIR_PRODUCTION_EQUIVALENCE_BLOBS_V1",
                self.repair_production_blobs,
            ),
            mock.patch.object(
                protocol,
                "PLAN0014_READER_HARDENING_PRODUCTION_EQUIVALENCE_BLOBS_V1",
                self.reader_hardening_production_blobs,
            ),
            mock.patch.object(
                protocol,
                "PLAN0014_UNCHANGED_PRODUCTION_DEPENDENCY_BLOBS_V1",
                self.unchanged_dependency_blobs,
            ),
        )

    def _build(self):
        first, second, third, fourth, fifth = self._patches()
        with first, second, third, fourth, fifth:
            return protocol.build_plan0014_production_closure_v1(
                str(self.repository)
            )

    def _validate(self, closure):
        first, second, third, fourth, fifth = self._patches()
        with first, second, third, fourth, fifth:
            return protocol.validate_plan0014_production_closure_v1(
                str(self.repository), closure
            )

    def _reseal(self, closure):
        first, second, third, fourth, fifth = self._patches()
        with first, second, third, fourth, fifth:
            return protocol.reseal_plan0014_production_closure_v1(
                str(self.repository), closure
            )

    def test_build_validate_and_reseal_exact_recursive_closure(self):
        closure = self._build()
        self.assertEqual(
            set(closure), {"artifact_type", "identity", "payload"}
        )
        self.assertEqual(
            closure["identity"],
            domain_identity(
                protocol.identity_domain_v1("production_closure_root"),
                closure["payload"],
            ),
        )
        self.assertEqual(
            tuple(
                record["path"]
                for record in closure["payload"]["ordered_file_records"]
            ),
            protocol.PRODUCTION_CLOSURE_PATHS_V1,
        )
        self.assertEqual(
            closure["payload"]["active_plan_ref"],
            {
                "byte_count": len(b"# synthetic plan\n"),
                "sha256": hashlib.sha256(b"# synthetic plan\n").hexdigest(),
            },
        )
        self.assertEqual(self._validate(closure), closure)
        self.assertIsNone(self._reseal(closure))

    def test_historical_validate_ignores_current_bytes_but_reseal_rejects_drift(self):
        closure = self._build()
        target = self.repository / "src/parity_forge/atlas_assessment_core.py"
        target.write_text("X = 2\n", encoding="utf-8")
        self.assertEqual(self._validate(closure), closure)
        with self.assertRaisesRegex(EvidenceIntegrityError, "current production"):
            self._reseal(closure)

    def test_current_reader_rejects_special_and_substituted_paths_without_blocking(self):
        leaf_parent = self.repository / "special"
        leaf_parent.mkdir()

        fifo = leaf_parent / "source.py"
        os.mkfifo(fifo)
        completed = _run_current_regular_probe(
            self.repository, "special/source.py", 0
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        fifo.unlink()

        socket_path = leaf_parent / "source.py"
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(str(socket_path))
            completed = _run_current_regular_probe(
                self.repository, "special/source.py", 0
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        socket_path.unlink()

        real_ancestor = self.repository / "real-ancestor"
        real_ancestor.mkdir()
        (real_ancestor / "source.py").write_bytes(b"")
        symlink_ancestor = self.repository / "symlink-ancestor"
        symlink_ancestor.symlink_to(real_ancestor, target_is_directory=True)
        completed = _run_current_regular_probe(
            self.repository, "symlink-ancestor/source.py", 0
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

        fifo_ancestor = self.repository / "fifo-ancestor"
        os.mkfifo(fifo_ancestor)
        completed = _run_current_regular_probe(
            self.repository, "fifo-ancestor/source.py", 0
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

        repository_alias = self.repository / "repository-alias"
        repository_alias.symlink_to(self.repository, target_is_directory=True)
        completed = _run_current_regular_probe(
            repository_alias, "real-ancestor/source.py", 0
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

        completed = _run_current_regular_probe(Path("/"), "dev/null", 0)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_current_reader_enforces_exact_size(self):
        source = self.repository / "exact-size.py"
        source.write_bytes(b"x")
        completed = _run_current_regular_probe(
            self.repository, "exact-size.py", 0
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_validator_rejects_identity_record_and_source_tree_drift(self):
        closure = self._build()
        cases = []
        wrong_identity = copy.deepcopy(closure)
        wrong_identity["identity"] = "0" * 64
        cases.append(wrong_identity)
        wrong_record = copy.deepcopy(closure)
        wrong_record["payload"]["ordered_file_records"][0]["byte_count"] += 1
        wrong_record["identity"] = domain_identity(
            protocol.identity_domain_v1("production_closure_root"),
            wrong_record["payload"],
        )
        cases.append(wrong_record)
        wrong_tree = copy.deepcopy(closure)
        wrong_tree["payload"]["source_tree"] = "0" * 40
        wrong_tree["identity"] = domain_identity(
            protocol.identity_domain_v1("production_closure_root"),
            wrong_tree["payload"],
        )
        cases.append(wrong_tree)
        extra = copy.deepcopy(closure)
        extra["payload"]["extra"] = None
        cases.append(extra)
        for index, value in enumerate(cases):
            with self.subTest(index=index):
                with self.assertRaises(EvidenceIntegrityError):
                    self._validate(value)

    def test_clean_head_and_exact_repository_top_are_required_for_build(self):
        (self.repository / "untracked.txt").write_text("dirty\n", encoding="utf-8")
        with self.assertRaisesRegex(EvidenceIntegrityError, "not clean"):
            self._build()
        with self.assertRaisesRegex(EvidenceIntegrityError, "exact Git top level"):
            protocol.build_plan0014_production_closure_v1(
                str(self.repository / "src")
            )

    def test_dynamic_or_forbidden_recursive_import_fails_closed(self):
        stage = self.repository / protocol.PRODUCTION_ENTRYPOINT_PATHS_V1[0]
        original = stage.read_text(encoding="utf-8")
        variants = (
            "__import__('parity_forge.solver')\n",
            (
                "from importlib import import_module as load\n"
                "load('parity_forge.solver')\n"
            ),
            (
                "import importlib as loader\n"
                "loader.import_module('parity_forge.solver')\n"
            ),
            (
                "from builtins import __import__ as load\n"
                "load('parity_forge.solver')\n"
            ),
            (
                "load = __import__\n"
                "load('parity_forge.solver')\n"
            ),
            "exec('import parity_forge.solver')\n",
            "eval(\"__import__('parity_forge.solver')\")\n",
        )
        for index, suffix in enumerate(variants):
            with self.subTest(index=index):
                stage.write_text(original + suffix, encoding="utf-8")
                _git(self.repository, "add", ".")
                _git(
                    self.repository,
                    "commit",
                    "-m",
                    "dynamic import {}".format(index),
                )
                self.source_commit = _git(
                    self.repository, "rev-parse", "HEAD^{commit}"
                )
                self.source_tree = _git(
                    self.repository, "rev-parse", "HEAD^{tree}"
                )
                self.archive_subtree = _git(
                    self.repository,
                    "rev-parse",
                    "HEAD:" + protocol.PLAN0013_EVIDENCE_ROOT_RELATIVE_V1,
                )
                self.repair_production_blobs = tuple(
                    (path, _git(self.repository, "rev-parse", "HEAD:" + path))
                    for path, _blob in (
                        protocol.PLAN0014_REPAIR_PRODUCTION_EQUIVALENCE_BLOBS_V1
                    )
                )
                self.reader_hardening_production_blobs = tuple(
                    (path, _git(self.repository, "rev-parse", "HEAD:" + path))
                    for path, _blob in (
                        protocol.PLAN0014_READER_HARDENING_PRODUCTION_EQUIVALENCE_BLOBS_V1
                    )
                )
                with self.assertRaisesRegex(
                    EvidenceIntegrityError, "dynamic imports"
                ):
                    self._build()

    def test_reader_hardening_production_drift_fails_closed(self):
        for index, (relative, _blob) in enumerate(
            protocol.PLAN0014_READER_HARDENING_PRODUCTION_EQUIVALENCE_BLOBS_V1
        ):
            with self.subTest(path=relative):
                target = self.repository / relative
                original = target.read_bytes()
                target.write_bytes(original + b"# hardening drift\n")
                _git(self.repository, "add", relative)
                _git(
                    self.repository,
                    "commit",
                    "-m",
                    "drift hardening {}".format(index),
                )
                with self.assertRaisesRegex(
                    EvidenceIntegrityError, "reader-hardening bytes"
                ):
                    self._build()

                target.write_bytes(original)
                _git(self.repository, "add", relative)
                _git(
                    self.repository,
                    "commit",
                    "-m",
                    "restore hardening {}".format(index),
                )

    def test_preexisting_scientific_dependency_drift_fails_closed(self):
        target = self.repository / "src/parity_forge/atlas_protocol.py"
        target.write_text("X = 2\n", encoding="utf-8")
        _git(self.repository, "add", ".")
        _git(self.repository, "commit", "-m", "drift scientific dependency")
        self.source_commit = _git(self.repository, "rev-parse", "HEAD^{commit}")
        self.source_tree = _git(self.repository, "rev-parse", "HEAD^{tree}")
        self.archive_subtree = _git(
            self.repository,
            "rev-parse",
            "HEAD:" + protocol.PLAN0013_EVIDENCE_ROOT_RELATIVE_V1,
        )
        with self.assertRaisesRegex(
            EvidenceIntegrityError, "frozen pre-existing dependency"
        ):
            self._build()


if __name__ == "__main__":
    unittest.main()
