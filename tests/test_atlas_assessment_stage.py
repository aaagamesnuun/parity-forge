import ast
import copy
import hashlib
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import parity_forge.atlas_assessment_stage as assessment_stage
import parity_forge.atlas_assessment_core as assessment_core
from parity_forge.atlas_protocol import (
    ATLAS_D4_TRANSFORMS_V1,
    ATLAS_FAMILY_ORDER_V1,
)
from parity_forge.atlas_stage_data import (
    ATLAS_DEPTH1_STRENGTH_ID_V1,
    ATLAS_RANDOM_STRENGTH_ID_V1,
)


def _sha(label):
    return hashlib.sha256(label.encode("ascii")).hexdigest()


def _outcome_summary(scheduled, a_wins, b_wins, draws=0):
    return {
        "status": "COMPLETE",
        "scheduled_games": scheduled,
        "completed_games": scheduled,
        "a_wins": a_wins,
        "b_wins": b_wins,
        "draw_ply_limit": draws,
    }


def _pair_inputs():
    result = []
    for pair_index in range(144):
        family_id = ATLAS_FAMILY_ORDER_V1[pair_index // 24]
        sampled = {
            identity: {
                "status": "COMPLETE",
                "scheduled_games": 128,
                "completed_games": 128,
                "a_wins": 64,
                "b_wins": 64,
                "draws": 0,
            }
            for identity in (
                ATLAS_RANDOM_STRENGTH_ID_V1,
                ATLAS_DEPTH1_STRENGTH_ID_V1,
            )
        }
        d4 = {
            identity: {
                transform: _outcome_summary(16, 8, 8)
                for transform in ATLAS_D4_TRANSFORMS_V1
            }
            for identity in (
                ATLAS_RANDOM_STRENGTH_ID_V1,
                ATLAS_DEPTH1_STRENGTH_ID_V1,
            )
        }
        result.append(
            {
                "pair_index": pair_index,
                "paired_mechanical_d4_identity": _sha(
                    "pair-{:03d}".format(pair_index)
                ),
                "family_id": family_id,
                "paired_stratum_id": "synthetic-stratum-{:02d}".format(
                    pair_index % 44
                ),
                "channel_statuses": {
                    "exact": "COMPLETE",
                    "random": "COMPLETE",
                    "terminal_depth1": "COMPLETE",
                    "telemetry": "COMPLETE",
                },
                "exact_members": {
                    "A_FIRST": {
                        "status": "COMPLETE",
                        "forced_result": "A_WIN",
                        "terminal_reason": "GOAL",
                    },
                    "B_FIRST": {
                        "status": "COMPLETE",
                        "forced_result": "B_WIN",
                        "terminal_reason": "GOAL",
                    },
                },
                "exact_utilization": {
                    "A_FIRST": {
                        "status": "COMPLETE",
                        "searched_states": 5,
                        "max_states": 10,
                    },
                    "B_FIRST": {
                        "status": "COMPLETE",
                        "searched_states": 4,
                        "max_states": 10,
                    },
                },
                "sampled_summaries": sampled,
                "d4_summaries": d4,
                "depth1_ply_summary": _outcome_summary(128, 64, 64),
                "forced_input": {
                    "A": {
                        "status": "COMPLETE",
                        "decision_count": 100,
                        "forced_decision_count": 25,
                    },
                    "B": {
                        "status": "COMPLETE",
                        "decision_count": 80,
                        "forced_decision_count": 20,
                    },
                },
                "reciprocal_input": {
                    "status": "COMPLETE",
                    "scheduled_games": 128,
                    "completed_games": 128,
                    "reciprocal_games": 64,
                },
            }
        )
    return result


def _bindings():
    return {
        "protocol_id": "synthetic-protocol-v1",
        "protocol_root": _sha("protocol"),
        "manifest_root": _sha("manifest"),
        "input_roots": {
            "exact_ledger_root": _sha("exact-ledger"),
            "pv_ledger_root": _sha("pv-ledger"),
            "random_ledger_root": _sha("random-ledger"),
            "depth1_ledger_root": _sha("depth-ledger"),
            "telemetry_ledger_root": _sha("telemetry-ledger"),
        },
        "channel_counts": {
            "exact": {"COMPLETE": 288},
            "exact_pv_replay": {"VALID": 2304},
            "random": {"COMPLETE": 18432},
            "terminal_depth1": {"COMPLETE": 18432},
            "telemetry": {"VALIDATED": 36864},
        },
    }


def _meta_parent_terminals(manifest_lifecycle="FAILED"):
    manifest_stage = assessment_stage._MANIFEST_PARENT
    manifest_identity = _sha("manifest-terminal-{}".format(manifest_lifecycle))
    manifest_payload = {
        "attempt_id_or_null": (
            _sha("manifest-attempt") if manifest_lifecycle == "FAILED" else None
        ),
        "blocked_id_or_null": None,
        "completed_root_or_null": None,
        "failure_root_or_null": (
            _sha("manifest-failure") if manifest_lifecycle == "FAILED" else None
        ),
        "lifecycle": manifest_lifecycle,
        "orphaned_id_or_null": (
            _sha("manifest-orphaned")
            if manifest_lifecycle == "ORPHANED"
            else None
        ),
        "partial_evidence_root_or_null": None,
        "reservation_id_or_null": _sha("manifest-reservation"),
        "stage_id": manifest_stage[0],
        "stage_protocol_id": manifest_stage[1],
    }
    terminals = [
        {
            "artifact_type": "ATLAS_STAGE_TERMINAL_SEAL_V1",
            "identity": manifest_identity,
            "payload": manifest_payload,
            "references": {"candidate_poison": _sha("must-not-leak")},
        }
    ]
    for index, stage in enumerate(assessment_stage._META_PARENT_ORDER_V1[1:], 1):
        blocked_identity = _sha("blocked-artifact-{}".format(index))
        blocked = {
            "artifact_type": "ATLAS_STAGE_BLOCKED_V1",
            "identity": blocked_identity,
            "payload": {
                "failed_prerequisite_stage_id": manifest_stage[0],
                "prerequisite_terminal_seal": manifest_identity,
                "stage_id": stage[0],
                "stage_protocol_id": stage[1],
            },
            "references": {
                "ordered_parent_terminal_seals": copy.deepcopy(terminals),
                "prerequisite_terminal_seal": copy.deepcopy(terminals[0]),
                "production_closure": {
                    "candidate_poison": _sha("must-not-leak")
                },
            },
        }
        terminals.append(
            {
                "artifact_type": "ATLAS_STAGE_TERMINAL_SEAL_V1",
                "identity": _sha("blocked-terminal-{}".format(index)),
                "payload": {
                    "attempt_id_or_null": None,
                    "blocked_id_or_null": blocked_identity,
                    "completed_root_or_null": None,
                    "failure_root_or_null": None,
                    "lifecycle": "BLOCKED",
                    "orphaned_id_or_null": None,
                    "partial_evidence_root_or_null": None,
                    "reservation_id_or_null": None,
                    "stage_id": stage[0],
                    "stage_protocol_id": stage[1],
                },
                "references": {
                    "blocked": blocked,
                    "completed": None,
                    "failure": None,
                    "orphaned": None,
                    "partial_evidence": None,
                    "stage_attempt": None,
                    "stage_reservation": None,
                },
            }
        )
    return terminals


class AtlasAssessmentStageTests(unittest.TestCase):
    def test_manifest_unavailable_meta_report_is_rooted_and_candidate_neutral(self):
        protocol = {
            "protocol_id": assessment_stage.ATLAS_PROTOCOL_ID_V1,
            "protocol_root": assessment_stage.ATLAS_PROTOCOL_ROOT_V1,
        }
        for lifecycle in ("FAILED", "ORPHANED"):
            with self.subTest(lifecycle=lifecycle):
                terminals = _meta_parent_terminals(lifecycle)
                report = assessment_stage._build_manifest_unavailable_meta_report_v1(
                    protocol, terminals
                )
                self.assertEqual(
                    report["status"],
                    "EXPERIMENT_INVALID_BEFORE_DEVELOPMENT_OUTCOMES",
                )
                self.assertEqual(report["gameplay_outcome_record_count"], 0)
                self.assertEqual(
                    report["candidate_definition_read_or_export_count"], 0
                )
                self.assertEqual(report["raw_parent_result_read_count"], 0)
                self.assertEqual(
                    report["fixed_denominators_source"],
                    "bootstrap-protocol-constants-only",
                )
                self.assertEqual(
                    report["formal_family_or_pair_labels"], "FORBIDDEN"
                )
                self.assertNotIn("raw_parent_outcomes_read", report)
                self.assertEqual(report["manifest_terminal"]["lifecycle"], lifecycle)
                self.assertEqual(len(report["blocked_downstream_terminals"]), 4)
                self.assertNotIn(_sha("must-not-leak"), str(report))
                self.assertEqual(
                    assessment_stage._validate_manifest_unavailable_meta_report_v1(
                        report, protocol, terminals
                    ),
                    report,
                )

                for field, forged_value in (
                    ("gameplay_outcome_record_count", 1),
                    ("candidate_definition_read_or_export_count", 1),
                    ("raw_parent_result_read_count", 1),
                    ("fixed_denominators_source", "caller-supplied"),
                    ("formal_family_or_pair_labels", "ALLOWED"),
                ):
                    with self.subTest(lifecycle=lifecycle, forged_field=field):
                        forged = copy.deepcopy(report)
                        forged[field] = forged_value
                        with self.assertRaisesRegex(
                            ValueError, "does not reconstruct"
                        ):
                            assessment_stage._validate_manifest_unavailable_meta_report_v1(
                                forged, protocol, terminals
                            )

                forged = copy.deepcopy(report)
                forged["raw_parent_outcomes_read"] = False
                with self.assertRaisesRegex(ValueError, "does not reconstruct"):
                    assessment_stage._validate_manifest_unavailable_meta_report_v1(
                        forged, protocol, terminals
                    )

    def test_manifest_unavailable_meta_report_rejects_nonblocked_descendants(self):
        protocol = {
            "protocol_id": assessment_stage.ATLAS_PROTOCOL_ID_V1,
            "protocol_root": assessment_stage.ATLAS_PROTOCOL_ROOT_V1,
        }
        terminals = _meta_parent_terminals()
        terminals[0]["payload"]["lifecycle"] = "COMPLETED"
        with self.assertRaisesRegex(ValueError, "lifecycle drifted"):
            assessment_stage._build_manifest_unavailable_meta_report_v1(
                protocol, terminals
            )

        terminals = _meta_parent_terminals()
        terminals[2]["payload"]["lifecycle"] = "FAILED"
        with self.assertRaisesRegex(ValueError, "lifecycle drifted"):
            assessment_stage._build_manifest_unavailable_meta_report_v1(
                protocol, terminals
            )

        terminals = _meta_parent_terminals()
        terminals[3]["references"]["blocked"]["references"][
            "ordered_parent_terminal_seals"
        ][1]["identity"] = _sha("different-exact-terminal")
        with self.assertRaisesRegex(ValueError, "chain differs"):
            assessment_stage._build_manifest_unavailable_meta_report_v1(
                protocol, terminals
            )

    def test_manifest_unavailable_runner_reserves_before_meta_without_raw_reads(self):
        store = mock.MagicMock()
        store.__enter__.return_value = store
        store.stage_lock.return_value.__enter__.return_value = None
        inputs = SimpleNamespace(
            contract=SimpleNamespace(
                stage_protocol_id=(
                    assessment_stage.ATLAS_ASSESSMENT_STAGE_PROTOCOL_ID_V1
                )
            ),
            protocol={"protocol": "authenticated"},
            detached_manifest=None,
            production_closure=object(),
            ordered_parent_terminal_seals=tuple(_meta_parent_terminals()),
            experiment_plan_bytes=b"plan",
        )
        events = []
        begin = mock.Mock(side_effect=lambda *_args: events.append("begin"))
        build_meta = mock.Mock(
            side_effect=lambda *_args: events.append("meta") or {"meta": 1}
        )
        read_raw = mock.Mock(side_effect=AssertionError("raw outcomes were read"))
        build_normal = mock.Mock(side_effect=AssertionError("normal report was built"))
        with mock.patch.multiple(
            assessment_stage,
            ImmutableEvidenceStore=mock.Mock(return_value=store),
            read_authenticated_stage_inputs=mock.Mock(return_value=inputs),
            _assessment_prerequisites_v1=mock.Mock(),
            begin_stage=begin,
            _build_manifest_unavailable_meta_report_v1=build_meta,
            _assessment_parent_inputs_v1=read_raw,
            _build_atlas_assessment_report_v1=build_normal,
            seal_completed_stage=mock.Mock(
                return_value={"identity": _sha("completed")}
            ),
        ):
            result = assessment_stage.run_atlas_assessment_stage_v1(
                "/tmp/repository"
            )
        self.assertEqual(events, ["begin", "meta"])
        self.assertEqual(result["lifecycle"], "COMPLETED")
        read_raw.assert_not_called()
        build_normal.assert_not_called()

    def test_recovery_without_completed_body_does_not_reconstruct_outcomes(self):
        store = mock.MagicMock()
        store.__enter__.return_value = store
        store.artifact_exists.return_value = False
        inputs = SimpleNamespace(
            contract=object(),
            protocol={"protocol": "authenticated"},
            detached_manifest={"development": "manifest"},
            ordered_parent_terminal_seals=tuple(_meta_parent_terminals()),
        )
        recovery = SimpleNamespace(
            action="SEALED_EXISTING_FAILED",
            lifecycle="FAILED",
            terminal_identity=_sha("failed-terminal"),
        )
        read_raw = mock.Mock(side_effect=AssertionError("raw outcomes were read"))
        build_normal = mock.Mock(side_effect=AssertionError("report was rebuilt"))
        build_meta = mock.Mock(side_effect=AssertionError("meta report was rebuilt"))
        recover = mock.Mock(return_value=recovery)
        with mock.patch.multiple(
            assessment_stage,
            ImmutableEvidenceStore=mock.Mock(return_value=store),
            read_authenticated_stage_inputs=mock.Mock(return_value=inputs),
            _assessment_parent_inputs_v1=read_raw,
            _build_atlas_assessment_report_v1=build_normal,
            _build_manifest_unavailable_meta_report_v1=build_meta,
            recover_stage=recover,
        ):
            result = assessment_stage.recover_atlas_assessment_stage_v1(
                "/tmp/repository"
            )
        self.assertEqual(result["lifecycle"], "FAILED")
        recover.assert_called_once()
        self.assertIsNone(
            recover.call_args.kwargs["expected_completed_summary"]
        )
        read_raw.assert_not_called()
        build_normal.assert_not_called()
        build_meta.assert_not_called()

    def test_recovery_rebuilds_expected_meta_summary_without_raw_reads(self):
        store = mock.MagicMock()
        store.__enter__.return_value = store
        store.artifact_exists.return_value = True
        terminals = tuple(_meta_parent_terminals())
        inputs = SimpleNamespace(
            contract=object(),
            protocol={"protocol": "authenticated"},
            detached_manifest=None,
            ordered_parent_terminal_seals=terminals,
        )
        expected = {"report": "canonical-meta"}
        build_meta = mock.Mock(return_value=expected)
        read_raw = mock.Mock(side_effect=AssertionError("raw outcomes were read"))
        recover = mock.Mock(
            return_value=SimpleNamespace(
                action="SEALED_EXISTING_COMPLETED",
                lifecycle="COMPLETED",
                terminal_identity=_sha("completed-terminal"),
            )
        )
        with mock.patch.multiple(
            assessment_stage,
            ImmutableEvidenceStore=mock.Mock(return_value=store),
            read_authenticated_stage_inputs=mock.Mock(return_value=inputs),
            _build_manifest_unavailable_meta_report_v1=build_meta,
            _assessment_parent_inputs_v1=read_raw,
            _build_atlas_assessment_report_v1=mock.Mock(
                side_effect=AssertionError("normal report was rebuilt")
            ),
            recover_stage=recover,
        ):
            result = assessment_stage.recover_atlas_assessment_stage_v1(
                "/tmp/repository"
            )
        self.assertEqual(result["lifecycle"], "COMPLETED")
        build_meta.assert_called_once_with(inputs.protocol, terminals)
        read_raw.assert_not_called()
        self.assertEqual(
            recover.call_args.kwargs["expected_completed_summary"], expected
        )

    def test_recovery_rebuilds_expected_normal_summary_from_parent_evidence(self):
        store = mock.MagicMock()
        store.__enter__.return_value = store
        store.artifact_exists.return_value = True
        terminals = (object(),)
        manifest = {"development": "manifest"}
        inputs = SimpleNamespace(
            contract=object(),
            protocol={"protocol": "authenticated"},
            detached_manifest=manifest,
            ordered_parent_terminal_seals=terminals,
        )
        parent_values = ({"parent": "evidence"},)
        expected = {"report": "canonical-normal"}
        read_raw = mock.Mock(return_value=parent_values)
        build_normal = mock.Mock(return_value=expected)
        recover = mock.Mock(
            return_value=SimpleNamespace(
                action="VERIFIED_NO_OP",
                lifecycle="COMPLETED",
                terminal_identity=_sha("completed-terminal"),
            )
        )
        with mock.patch.multiple(
            assessment_stage,
            ImmutableEvidenceStore=mock.Mock(return_value=store),
            read_authenticated_stage_inputs=mock.Mock(return_value=inputs),
            _assessment_parent_inputs_v1=read_raw,
            _build_atlas_assessment_report_v1=build_normal,
            _build_manifest_unavailable_meta_report_v1=mock.Mock(
                side_effect=AssertionError("meta report was rebuilt")
            ),
            recover_stage=recover,
        ):
            result = assessment_stage.recover_atlas_assessment_stage_v1(
                "/tmp/repository"
            )
        self.assertEqual(result["lifecycle"], "COMPLETED")
        read_raw.assert_called_once_with(store, inputs.protocol, terminals)
        build_normal.assert_called_once_with(
            manifest, inputs.protocol, *parent_values
        )
        self.assertEqual(
            recover.call_args.kwargs["expected_completed_summary"], expected
        )

    def test_recovery_reconstruction_failure_prevents_generic_recovery(self):
        store = mock.MagicMock()
        store.__enter__.return_value = store
        store.artifact_exists.return_value = True
        inputs = SimpleNamespace(
            contract=object(),
            protocol={"protocol": "authenticated"},
            detached_manifest=None,
            ordered_parent_terminal_seals=tuple(_meta_parent_terminals()),
        )
        recover = mock.Mock()
        with mock.patch.multiple(
            assessment_stage,
            ImmutableEvidenceStore=mock.Mock(return_value=store),
            read_authenticated_stage_inputs=mock.Mock(return_value=inputs),
            _build_manifest_unavailable_meta_report_v1=mock.Mock(
                side_effect=ValueError("parent evidence invalid")
            ),
            recover_stage=recover,
        ):
            with self.assertRaisesRegex(ValueError, "parent evidence invalid"):
                assessment_stage.recover_atlas_assessment_stage_v1(
                    "/tmp/repository"
                )
        recover.assert_not_called()

    def test_completion_failure_before_completed_body_seals_failed(self):
        store = mock.MagicMock()
        store.__enter__.return_value = store
        store.stage_lock.return_value.__enter__.return_value = None
        store.artifact_exists.return_value = False
        inputs = SimpleNamespace(
            contract=SimpleNamespace(
                stage_protocol_id=(
                    assessment_stage.ATLAS_ASSESSMENT_STAGE_PROTOCOL_ID_V1
                )
            ),
            protocol={},
            detached_manifest={},
            production_closure=object(),
            ordered_parent_terminal_seals=(),
            experiment_plan_bytes=b"plan",
        )
        seal_failed = mock.Mock(return_value={"identity": _sha("failed")})
        with mock.patch.multiple(
            assessment_stage,
            ImmutableEvidenceStore=mock.Mock(return_value=store),
            read_authenticated_stage_inputs=mock.Mock(return_value=inputs),
            _assessment_prerequisites_v1=mock.Mock(),
            begin_stage=mock.Mock(),
            _assessment_parent_inputs_v1=mock.Mock(return_value=()),
            _build_atlas_assessment_report_v1=mock.Mock(return_value={"report": 1}),
            seal_completed_stage=mock.Mock(side_effect=OSError("before publish")),
            seal_failed_stage=seal_failed,
        ):
            result = assessment_stage.run_atlas_assessment_stage_v1(
                "/tmp/repository"
            )
        self.assertEqual(result["lifecycle"], "FAILED")
        seal_failed.assert_called_once()

    def test_valid_pv_allows_the_exact_draw_winner_to_be_null(self):
        orientation = {
            "slot_id": _sha("orientation"),
            "exact_slot_id": _sha("exact"),
            "transform_index": 0,
            "transform": "IDENTITY",
            "transformed_definition_hash": _sha("transformed"),
        }
        record = {
            "record_version": 1,
            "record_kind": "EXACT_PV",
            "status": "VALID",
            "orientation_slot_id": orientation["slot_id"],
            "exact_slot_id": orientation["exact_slot_id"],
            "transform_index": 0,
            "transform": "IDENTITY",
            "representative_definition_hash": _sha("representative"),
            "representative_definition_byte_count": 1,
            "transformed_definition_hash": orientation[
                "transformed_definition_hash"
            ],
            "transformed_definition_byte_count": 1,
            "principal_variation_or_null": [],
            "principal_variation_plies_or_null": 0,
            "value_for_a_or_null": 0,
            "forced_result_or_null": "DRAW",
            "winner_or_null": None,
            "terminal_reason_or_null": "PLY_LIMIT",
            "error_or_null": None,
        }
        assessment_stage._validate_pv_record(record, orientation)

    def test_formal_report_rebuilds_labels_metrics_families_and_inspection(self):
        pair_inputs = _pair_inputs()
        pair_inputs[0]["exact_label"] = "CALLER_FORGERY_IS_IGNORED"
        report = assessment_stage._validate_reconstructed_assessment_v1(
            None, pair_inputs=pair_inputs, **_bindings()
        )
        self.assertEqual(report["status"], "FORMAL_COMPLETE")
        self.assertTrue(report["formal_evidence"])
        self.assertEqual(report["pair_count"], 144)
        self.assertEqual(report["family_count"], 6)
        self.assertEqual(
            {pair["exact_label"] for pair in report["pairs"]},
            {"FIRST_PLAYER_DOMINANT"},
        )
        self.assertEqual(
            {pair["random_label"] for pair in report["pairs"]},
            {"WEAK_BALANCE_SIGNAL_V1"},
        )
        self.assertEqual(
            {pair["pair_assessment"] for pair in report["pairs"]},
            {"PAIR_FRONTIER_SIGNAL_V1"},
        )
        self.assertEqual(
            report["pairs"][0]["metrics"]["exact_state_utilization"],
            {"status": "DEFINED", "numerator": 1, "denominator": 2},
        )
        self.assertEqual(
            report["pairs"][0]["metrics"][
                "depth1_reciprocal_dependency_fraction"
            ],
            {"status": "DEFINED", "numerator": 1, "denominator": 2},
        )
        self.assertEqual(
            {family["status"] for family in report["families"]},
            {"SUPPORTED_FAMILY_FRONTIER"},
        )
        self.assertEqual(
            report["inspection_selection"]["selected_pair_count"], 144
        )

    def test_telemetry_exception_does_not_change_formal_family_signal(self):
        pair_inputs = _pair_inputs()
        for pair in pair_inputs:
            pair["channel_statuses"]["telemetry"] = "INCOMPLETE"
            for role in ("A", "B"):
                pair["forced_input"][role]["status"] = "INCOMPLETE"
            pair["reciprocal_input"]["status"] = "INCOMPLETE"
            pair["reciprocal_input"]["completed_games"] = 0
            pair["reciprocal_input"]["reciprocal_games"] = 0
        report = assessment_stage._validate_reconstructed_assessment_v1(
            None, pair_inputs=pair_inputs, **_bindings()
        )
        self.assertEqual(
            report["status"], "FORMAL_COMPLETE_WITH_TELEMETRY_EXCEPTION"
        )
        self.assertEqual(
            {family["status"] for family in report["families"]},
            {"SUPPORTED_FAMILY_FRONTIER"},
        )
        metric = report["pairs"][0]["metrics"]["forced_decision_fraction"]["A"]
        self.assertEqual(metric, {"status": "MISSING", "reason": "INCOMPLETE_TELEMETRY"})

    def test_noncomplete_formal_channel_and_tampered_report_fail_closed(self):
        pair_inputs = _pair_inputs()
        pair_inputs[0]["channel_statuses"]["exact"] = "PROOF_CONTRADICTION"
        report = assessment_stage._validate_reconstructed_assessment_v1(
            None, pair_inputs=pair_inputs, **_bindings()
        )
        self.assertEqual(report["status"], "EVIDENCE_INVALID")
        self.assertEqual(report["pairs"][0]["exact_label"], "EVIDENCE_INVALID")
        self.assertEqual(report["families"][0]["status"], "EVIDENCE_INVALID")

        forged = copy.deepcopy(report)
        forged["pairs"][0]["exact_label"] = "FIRST_PLAYER_DOMINANT"
        with self.assertRaisesRegex(ValueError, "does not reconstruct"):
            assessment_stage._validate_reconstructed_assessment_v1(
                forged, pair_inputs=pair_inputs, **_bindings()
            )

    def test_cli_imports_and_private_helper_call_boundary(self):
        parser = assessment_stage._build_parser()
        self.assertEqual(
            parser.parse_args(["recover", "--repository", "/tmp/repo"]).command,
            "recover",
        )
        with self.assertRaises(SystemExit):
            parser.parse_args(["run", "--repository", "/tmp/repo", "--pair", "1"])

        stage_path = Path(assessment_stage.__file__)
        stage_tree = ast.parse(stage_path.read_text(encoding="utf-8"))
        stage_local_imports = {
            node.module
            for node in ast.walk(stage_tree)
            if isinstance(node, ast.ImportFrom) and node.level
        }
        self.assertEqual(
            stage_local_imports,
            {"atlas_assessment_core", "atlas_evidence"},
        )

        core_path = Path(assessment_core.__file__)
        tree = ast.parse(core_path.read_text(encoding="utf-8"))
        local_imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.level
        }
        self.assertTrue(
            local_imports.issubset(
                {None, "atlas_protocol", "atlas_stage_data", "atlas_evidence"}
            )
        )
        self.assertFalse(
            local_imports.intersection(
                {
                    "agency",
                    "agents",
                    "atlas",
                    "atlas_history",
                    "atlas_projection",
                    "feasibility",
                    "play",
                    "solver",
                    "terminal_search",
                }
            )
        )
        formal_callers = set()
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for child in ast.walk(node):
                if (
                    isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Attribute)
                    and isinstance(child.func.value, ast.Name)
                    and child.func.value.id == "_protocol"
                    and child.func.attr.startswith(
                        ("_classify_", "_assess_", "_calculate_")
                    )
                ):
                    formal_callers.add(node.name)
        self.assertEqual(formal_callers, {"_validate_reconstructed_assessment_v1"})

    def test_stage_facade_aliases_the_single_core_implementation(self):
        for name in (
            "_assessment_parent_inputs_v1",
            "_assessment_prerequisites_v1",
            "_build_atlas_assessment_report_v1",
            "_build_manifest_unavailable_meta_report_v1",
            "_telemetry_metric_values",
            "_validate_manifest_unavailable_meta_report_v1",
            "_validate_pv_record",
            "_validate_reconstructed_assessment_v1",
        ):
            with self.subTest(name=name):
                self.assertIs(
                    getattr(assessment_stage, name),
                    getattr(assessment_core, name),
                )

    def test_assessment_core_has_no_write_lifecycle_import_or_call(self):
        path = Path(assessment_core.__file__)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        forbidden = {
            "begin_stage",
            "publish_bytes",
            "publish_contradiction",
            "publish_journal_result",
            "publish_journal_start",
            "publish_json",
            "recover_stage",
            "seal_completed_stage",
            "seal_failed_stage",
            "stage_lock",
        }
        imported = set()
        called = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.asname or alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.update(alias.asname or alias.name for alias in node.names)
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    called.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    called.add(node.func.attr)
        self.assertFalse(forbidden.intersection(imported))
        self.assertFalse(forbidden.intersection(called))


if __name__ == "__main__":
    unittest.main()
