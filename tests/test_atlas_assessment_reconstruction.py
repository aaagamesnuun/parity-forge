import ast
import hashlib
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import parity_forge.atlas_assessment_reconstruction as reconstruction
from parity_forge.atlas_evidence import canonical_json_bytes


def _completed_terminal(stage_index):
    return {
        "payload": {
            "lifecycle": "COMPLETED",
            "stage_id": "PARENT_{}".format(stage_index),
        }
    }


def _evidence_tree_inventory(root):
    """Capture content and mutation-relevant metadata for the whole V2 tree."""

    records = []
    pending = [root]
    while pending:
        path = pending.pop()
        info = path.lstat()
        relative = "." if path == root else path.relative_to(root).as_posix()
        digest = None
        target = None
        if stat.S_ISREG(info.st_mode):
            hasher = hashlib.sha256()
            with path.open("rb") as stream:
                while True:
                    chunk = stream.read(1024 * 1024)
                    if not chunk:
                        break
                    hasher.update(chunk)
            digest = hasher.hexdigest()
        elif stat.S_ISLNK(info.st_mode):
            target = os.readlink(path)
        elif stat.S_ISDIR(info.st_mode):
            pending.extend(
                sorted(path.iterdir(), reverse=True, key=lambda item: item.name)
            )
        records.append(
            (
                relative,
                stat.S_IFMT(info.st_mode),
                stat.S_IMODE(info.st_mode),
                info.st_ino,
                info.st_nlink,
                info.st_size,
                info.st_mtime_ns,
                info.st_ctime_ns,
                digest,
                target,
            )
        )
    return tuple(sorted(records))


class AtlasAssessmentReconstructionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repository = Path(temporary.name).resolve()
        self.evidence_root = (
            self.repository
            / reconstruction.PLAN0013_ATLAS_EVIDENCE_ROOT_RELATIVE_V1
        )
        for component in (
            "stages",
            "manifest-bootstrap",
        ):
            (self.evidence_root / component).mkdir(parents=True, exist_ok=True)

    def _inputs(self):
        return SimpleNamespace(
            contract=SimpleNamespace(
                stage_protocol_id=(
                    reconstruction.ATLAS_ASSESSMENT_STAGE_PROTOCOL_ID_V1
                )
            ),
            detached_manifest={"manifest": "authenticated"},
            protocol={"protocol": "authenticated"},
            ordered_parent_terminal_seals=tuple(
                _completed_terminal(index) for index in range(5)
            ),
        )

    def test_public_api_uses_only_authenticated_read_and_frozen_builder(self):
        store = mock.MagicMock()
        store.__enter__.return_value = store
        store.__exit__.return_value = None
        inputs = self._inputs()
        parent_values = tuple({"parent": index} for index in range(10))
        expected = {"report": "reconstructed"}
        events = []
        store_type = mock.Mock()
        store_type.from_read_only_directory_fd.return_value = store
        read_inputs = mock.Mock(
            side_effect=lambda *_args: events.append("authenticated") or inputs
        )
        prerequisites = mock.Mock(
            side_effect=lambda *_args: events.append("prerequisites")
        )
        read_parents = mock.Mock(
            side_effect=lambda *_args: events.append("parents") or parent_values
        )
        build_report = mock.Mock(
            side_effect=lambda *_args: events.append("report") or expected
        )

        with mock.patch.multiple(
            reconstruction,
            ImmutableEvidenceStore=store_type,
            read_authenticated_stage_inputs=read_inputs,
            _assessment_prerequisites_v1=prerequisites,
            _assessment_parent_inputs_v1=read_parents,
            _build_atlas_assessment_report_v1=build_report,
        ):
            result = reconstruction.reconstruct_plan0013_atlas_assessment_report_v1(
                str(self.repository)
            )

        self.assertIs(result, expected)
        self.assertEqual(
            events, ["authenticated", "prerequisites", "parents", "report"]
        )
        store_type.from_read_only_directory_fd.assert_called_once_with(
            Path(os.path.abspath(str(self.repository)))
            / reconstruction.PLAN0013_ATLAS_EVIDENCE_ROOT_RELATIVE_V1,
            mock.ANY,
        )
        self.assertIs(
            type(
                store_type.from_read_only_directory_fd.call_args.args[1]
            ),
            int,
        )
        read_inputs.assert_called_once_with(
            store, reconstruction.ATLAS_ASSESSMENT_STAGE_ID_V1
        )
        prerequisites.assert_called_once_with(
            inputs.contract, inputs.ordered_parent_terminal_seals
        )
        read_parents.assert_called_once_with(
            store, inputs.protocol, inputs.ordered_parent_terminal_seals
        )
        build_report.assert_called_once_with(
            inputs.detached_manifest, inputs.protocol, *parent_values
        )
        store.stage_lock.assert_not_called()

    def test_missing_store_fails_before_store_constructor_and_creates_nothing(self):
        missing_repository = self.repository / "missing"
        store_type = mock.Mock()
        store_type.from_read_only_directory_fd.side_effect = AssertionError(
            "store was opened"
        )
        with mock.patch.object(
            reconstruction, "ImmutableEvidenceStore", store_type
        ):
            with self.assertRaisesRegex(FileNotFoundError, "fixed Plan-0013"):
                reconstruction.reconstruct_plan0013_atlas_assessment_report_v1(
                    str(missing_repository)
                )
        store_type.from_read_only_directory_fd.assert_not_called()
        self.assertFalse(missing_repository.exists())

    def test_redirected_store_component_is_rejected_before_open(self):
        redirected = self.repository / "redirected-stages"
        redirected.mkdir()
        (self.evidence_root / "stages").rmdir()
        (self.evidence_root / "stages").symlink_to(redirected, target_is_directory=True)
        store_type = mock.Mock()
        store_type.from_read_only_directory_fd.side_effect = AssertionError(
            "store was opened"
        )
        with mock.patch.object(
            reconstruction, "ImmutableEvidenceStore", store_type
        ):
            with self.assertRaisesRegex(ValueError, "real directories"):
                reconstruction.reconstruct_plan0013_atlas_assessment_report_v1(
                    str(self.repository)
                )
        store_type.from_read_only_directory_fd.assert_not_called()

    def test_redirected_store_ancestor_is_rejected_before_open(self):
        experiments = self.repository / "experiments"
        real_experiments = self.repository / "real-experiments"
        experiments.rename(real_experiments)
        experiments.symlink_to(real_experiments, target_is_directory=True)
        store_type = mock.Mock()
        store_type.from_read_only_directory_fd.side_effect = AssertionError(
            "store was opened"
        )
        with mock.patch.object(
            reconstruction, "ImmutableEvidenceStore", store_type
        ):
            with self.assertRaisesRegex(ValueError, "real directories"):
                reconstruction.reconstruct_plan0013_atlas_assessment_report_v1(
                    str(self.repository)
                )
        store_type.from_read_only_directory_fd.assert_not_called()

    def test_repository_symlink_alias_is_rejected_before_open(self):
        alias = self.repository / "repository-alias"
        alias.symlink_to(self.repository, target_is_directory=True)
        store_type = mock.Mock()
        store_type.from_read_only_directory_fd.side_effect = AssertionError(
            "store was opened"
        )
        with mock.patch.object(
            reconstruction, "ImmutableEvidenceStore", store_type
        ):
            with self.assertRaisesRegex(ValueError, "real directories"):
                reconstruction.reconstruct_plan0013_atlas_assessment_report_v1(
                    str(alias)
                )
        store_type.from_read_only_directory_fd.assert_not_called()

    def test_repository_ancestor_symlink_alias_is_rejected_before_open(self):
        real_parent = self.repository / "real-parent"
        nested_repository = real_parent / "nested-repository"
        nested_root = (
            nested_repository
            / reconstruction.PLAN0013_ATLAS_EVIDENCE_ROOT_RELATIVE_V1
        )
        (nested_root / "stages").mkdir(parents=True)
        (nested_root / "manifest-bootstrap").mkdir()
        alias_parent = self.repository / "parent-alias"
        alias_parent.symlink_to(real_parent, target_is_directory=True)
        aliased_repository = alias_parent / "nested-repository"
        store_type = mock.Mock()
        store_type.from_read_only_directory_fd.side_effect = AssertionError(
            "store was opened"
        )
        with mock.patch.object(
            reconstruction, "ImmutableEvidenceStore", store_type
        ):
            with self.assertRaisesRegex(ValueError, "real directories"):
                reconstruction.reconstruct_plan0013_atlas_assessment_report_v1(
                    str(aliased_repository)
                )
        store_type.from_read_only_directory_fd.assert_not_called()

    def test_path_swap_at_reader_boundary_keeps_authenticated_store(self):
        stage_id = "plan0013-atlas-development-manifest-v1"
        original_stage = self.evidence_root / "stages" / stage_id
        original_stage.mkdir()
        (original_stage / "reservation.json").write_bytes(
            canonical_json_bytes({"source": "authenticated"})
        )
        original_factory = (
            reconstruction.ImmutableEvidenceStore.from_read_only_directory_fd
        )
        observed = []

        def swap_then_bind(root, directory_fd):
            experiments = self.repository / "experiments"
            experiments.rename(self.repository / "authenticated-experiments")
            replacement_stage = root / "stages" / stage_id
            replacement_stage.mkdir(parents=True)
            (root / "manifest-bootstrap").mkdir()
            (replacement_stage / "reservation.json").write_bytes(
                canonical_json_bytes({"source": "replacement"})
            )
            return original_factory(root, directory_fd)

        def read_inputs(store, _stage_id):
            observed.append(store.read_json(stage_id, "reservation"))
            return self._inputs()

        with mock.patch.object(
            reconstruction.ImmutableEvidenceStore,
            "from_read_only_directory_fd",
            side_effect=swap_then_bind,
        ), mock.patch.multiple(
            reconstruction,
            read_authenticated_stage_inputs=mock.Mock(side_effect=read_inputs),
            _assessment_prerequisites_v1=mock.Mock(),
            _assessment_parent_inputs_v1=mock.Mock(return_value=()),
            _build_atlas_assessment_report_v1=mock.Mock(
                return_value={"report": "authenticated"}
            ),
        ):
            result = reconstruction.reconstruct_plan0013_atlas_assessment_report_v1(
                str(self.repository)
            )

        self.assertEqual(result, {"report": "authenticated"})
        self.assertEqual(observed, [{"source": "authenticated"}])
        replacement = self.repository / "experiments" / "runs"
        replacement /= "plan0013-atlas-development-evidence-v2"
        self.assertEqual(
            (replacement / "stages" / stage_id / "reservation.json").read_bytes(),
            canonical_json_bytes({"source": "replacement"}),
        )

    def test_protocol_manifest_and_parent_lifecycle_fail_closed(self):
        cases = (
            ("protocol", "assessment stage protocol identity drifted"),
            ("manifest", "completed Plan-0013 manifest is unavailable"),
            ("parent", "assessment parent is not completed"),
            ("count", "exactly five parents"),
        )
        for case, message in cases:
            with self.subTest(case=case):
                inputs = self._inputs()
                if case == "protocol":
                    inputs.contract.stage_protocol_id = "wrong-protocol"
                elif case == "manifest":
                    inputs.detached_manifest = None
                elif case == "parent":
                    inputs.ordered_parent_terminal_seals[-1]["payload"][
                        "lifecycle"
                    ] = "FAILED"
                else:
                    inputs.ordered_parent_terminal_seals = (
                        inputs.ordered_parent_terminal_seals[:-1]
                    )
                store = mock.MagicMock()
                store.__enter__.return_value = store
                store_type = mock.Mock()
                store_type.from_read_only_directory_fd.return_value = store
                read_parents = mock.Mock()
                build_report = mock.Mock()
                with mock.patch.multiple(
                    reconstruction,
                    ImmutableEvidenceStore=store_type,
                    read_authenticated_stage_inputs=mock.Mock(return_value=inputs),
                    _assessment_prerequisites_v1=mock.Mock(),
                    _assessment_parent_inputs_v1=read_parents,
                    _build_atlas_assessment_report_v1=build_report,
                ):
                    with self.assertRaisesRegex(ValueError, message):
                        reconstruction.reconstruct_plan0013_atlas_assessment_report_v1(
                            str(self.repository)
                        )
                read_parents.assert_not_called()
                build_report.assert_not_called()

    def test_repository_is_a_nonempty_exact_string(self):
        for value in (None, Path("."), ""):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "nonempty exact string"):
                    reconstruction.reconstruct_plan0013_atlas_assessment_report_v1(
                        value
                    )

    def test_module_has_no_evidence_write_or_gameplay_capability(self):
        source_path = Path(reconstruction.__file__)
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        forbidden_import_roots = {
            "agent",
            "atlas_assessment_stage",
            "atlas_depth1_stage",
            "atlas_exact_stage",
            "atlas_manifest_stage",
            "atlas_random_stage",
            "atlas_selector",
            "atlas_telemetry_stage",
            "engine",
            "solver",
        }
        forbidden_calls = {
            "begin_stage",
            "getattr",
            "mkdir",
            "open",
            "rename",
            "recover_stage",
            "run_atlas_assessment_stage_v1",
            "recover_atlas_assessment_stage_v1",
            "seal_completed_stage",
            "seal_failed_stage",
            "setattr",
            "stage_lock",
            "touch",
            "unlink",
            "write_bytes",
            "write_text",
            "publish_bytes",
            "publish_json",
            "publish_journal_start",
            "publish_journal_result",
            "publish_contradiction",
        }
        imported_roots = set()
        imported_names = set()
        called_names = set()
        called_attributes = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(
                    alias.name.rsplit(".", 1)[-1] for alias in node.names
                )
                imported_names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.rsplit(".", 1)[-1])
                imported_names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    called_names.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    called_attributes.add(node.func.attr)
        self.assertFalse(forbidden_import_roots.intersection(imported_roots))
        self.assertIn("atlas_assessment_core", imported_roots)
        self.assertFalse(forbidden_calls.intersection(imported_names))
        self.assertFalse(forbidden_calls.intersection(called_names))
        self.assertFalse(
            (forbidden_calls - {"getattr", "open"}).intersection(
                called_attributes
            )
        )

        os_open_callers = set()
        for function in (
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ):
            for node in ast.walk(function):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "os"
                    and node.func.attr == "open"
                ):
                    os_open_callers.add(function.name)
        self.assertEqual(
            os_open_callers,
            {
                "_open_existing_directory_at_v1",
                "_open_existing_store_path_v1",
            },
        )
        source = source_path.read_text(encoding="utf-8")
        for write_flag in ("os.O_CREAT", "os.O_WRONLY", "os.O_RDWR"):
            self.assertNotIn(write_flag, source)


@unittest.skipUnless(
    os.environ.get("PARITY_FORGE_RUN_PLAN0014_REAL_RECONSTRUCTION") == "1",
    "real 36,864-record reconstruction is opt-in",
)
class AtlasAssessmentRealEvidenceIntegrationTests(unittest.TestCase):
    def test_committed_v2_evidence_reconstructs_without_worktree_change(self):
        repository = Path(__file__).resolve().parents[1]
        evidence_root = (
            repository
            / reconstruction.PLAN0013_ATLAS_EVIDENCE_ROOT_RELATIVE_V1
        )
        status_command = (
            "git",
            "-C",
            str(repository),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        )
        before = subprocess.run(
            status_command,
            check=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout
        evidence_before = _evidence_tree_inventory(evidence_root)
        with mock.patch.object(
            reconstruction.ImmutableEvidenceStore,
            "_require_writable",
            side_effect=AssertionError("reconstruction attempted a mutation"),
        ) as writable:
            report = (
                reconstruction.reconstruct_plan0013_atlas_assessment_report_v1(
                    str(repository)
                )
            )
        writable.assert_not_called()
        evidence_after = _evidence_tree_inventory(evidence_root)
        after = subprocess.run(
            status_command,
            check=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout

        self.assertEqual(after, before)
        self.assertEqual(evidence_after, evidence_before)
        self.assertEqual(report["report_version"], 1)
        self.assertEqual(report["status"], "FORMAL_COMPLETE")
        self.assertEqual(
            report["claim_level"],
            "FAMILY_FRONTIER_SIGNAL_NOT_FAIR_GAME",
        )
        self.assertEqual(
            report["report_root"],
            "2a873b0b1d11e9ffb617792d41c870e1fb0fe32f4f2c7b6aa5fdfeb5d215484d",
        )
        self.assertEqual(
            report["input_roots"],
            {
                "depth1_ledger_root": "e792dccc092b0a90e5ddc36f98b77468c3eb40d32e63fa59e6d869e04c9b4c25",
                "depth1_records_root": "89ea1521d97bc0e8e6858acedaabd82f2e766f49f7f38d311973125fd62ea8b0",
                "exact_ledger_root": "cb873a077491314940eaf3d14470c2d952422d7082853a1211c94604cf9ba5f0",
                "exact_records_root": "42722248c7e6bd682d4cfc629bc0464cb4a070d338c394660374661e72f7befa",
                "pv_ledger_root": "18323e00a6c4f900f678647787ddff9bdeeb42469e56c5e612752644e195ff44",
                "pv_records_root": "4ba16622745869987efc5beebc1b32ebe539f05e70cccb0fab26dca714b56762",
                "random_ledger_root": "1a74ef835cc6620f0d0c29db6d518fb08c236dca5b47f799e0a05ee5123ac310",
                "random_records_root": "377fc9c2158eb601f282ea5b40999b0377162bcf11a61384465448d540e61243",
                "telemetry_ledger_root": "d8ff96be1a6c2fbf5c0969f5849321638c2b5219714bd99e5091699c2457a4b7",
                "telemetry_records_root": "4bf60f29811b525a96894fe7605e4a7c4b5bcf0031f16f087a3c8836703bee99",
            },
        )
        self.assertEqual(report["pair_count"], 144)
        self.assertEqual(report["family_count"], 6)
        self.assertEqual(
            report["channel_counts"]["telemetry"]["VALIDATED"], 36864
        )
        self.assertEqual(
            sum(
                count
                for status, count in report["channel_counts"]["telemetry"].items()
                if status != "VALIDATED"
            ),
            0,
        )
        frontier_pairs = [
            pair
            for pair in report["pairs"]
            if pair["pair_assessment"] == "PAIR_FRONTIER_SIGNAL_V1"
        ]
        self.assertEqual(len(frontier_pairs), 14)
        self.assertEqual(
            {pair["exact_label"] for pair in frontier_pairs},
            {"FIRST_PLAYER_DOMINANT"},
        )
        self.assertEqual(
            [
                (
                    pair["pair_index"],
                    pair["paired_mechanical_d4_identity"],
                )
                for pair in frontier_pairs
            ],
            [
                (2, "ad4f319f6d31d3b76c0c08a87048a07a73b2cb37c101cff5cbe43ab740e4ab8d"),
                (4, "9361aff45a97f437739c0a2b76dfb4e83e25b346ed46ebce2e4f01d64c8829c3"),
                (5, "7fd94f17a6cd8781fb5f3c989062c2dae607351d63870dfae83c34be32a4bb5a"),
                (6, "1cd0c472dcbe493db88dadcfc9bf343d6a0a97e655d7d4447bb6fd87b927df09"),
                (7, "967807d915c654b6aa289d964f423660fa2ac448913f345b6f7c88bcb6443c9e"),
                (19, "b901d53a7908e39c40342dbd07e7f3367c519d421c3a199b3346e7fa9d3ac002"),
                (20, "83cf98ea357d389a787a820222a5ac497e41eddac55a198f9b9cda084f8e8cd0"),
                (22, "e4178876750fa1e5758cf542ac36024018f8daaf83a9b12514484e35f2b07f0b"),
                (23, "e5313d9b8bc8bab4cef2063c5eb2840688b03e2b735fe2029a771ca68d1f57a9"),
                (48, "1a605b4402c89d227df4478567003ef812e44ef6fa465baea124599f892a2eec"),
                (52, "b27f44bc005f06cc4b887283ea2f1a579854d5b7c9ed502e360c17b7cb988cd6"),
                (60, "639fd882e3b9b87aa5d2462c5b7e1f433a0dd95476823c9953d9fa1d4308c9bb"),
                (129, "3caa0bf9a430f0f9e7402f539a0ac5cb1e8165cf7bd91a2c866d2ee56a3041e1"),
                (130, "be982e50507762ce9e46cd34aca85f37a5a2c516bc942b8b6ccbef54a75a2064"),
            ],
        )
        self.assertEqual(
            {
                family["family_id"]: (
                    family["status"],
                    family["frontier_pair_count"],
                    family["frontier_distinct_stratum_count"],
                )
                for family in report["families"]
            },
            {
                "push-hop-race-v1": ("SUPPORTED_FAMILY_FRONTIER", 9, 6),
                "swap-hop-network-v1": ("NOT_SUPPORTED_COMPLETE", 0, 0),
                "convert-push-front-v1": ("SUPPORTED_FAMILY_FRONTIER", 3, 3),
                "capture-hop-hunt-v1": ("NOT_SUPPORTED_COMPLETE", 0, 0),
                "convert-capture-duel-v1": ("NOT_SUPPORTED_COMPLETE", 0, 0),
                "push-swap-networks-v1": ("NOT_SUPPORTED_COMPLETE", 2, 1),
            },
        )
        inspection_bytes = canonical_json_bytes(report["inspection_selection"])
        self.assertEqual(len(inspection_bytes), 104458)
        self.assertEqual(
            hashlib.sha256(inspection_bytes).hexdigest(),
            "0fc525939d67cbf426704e28b7383fa1b92aa14d6f497cbaaf7d136be3803c7e",
        )
        self.assertEqual(
            report["inspection_selection"]["class_group_summary_count"], 118
        )
        self.assertEqual(
            report["inspection_selection"]["selected_pair_count"], 98
        )


if __name__ == "__main__":
    unittest.main()
