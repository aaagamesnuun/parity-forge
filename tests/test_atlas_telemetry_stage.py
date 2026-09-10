import ast
import copy
import hashlib
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import parity_forge.atlas_telemetry_stage as telemetry_stage
from parity_forge.atlas_evidence import canonical_body_ref, domain_identity
from parity_forge.atlas_stage_data import (
    ATLAS_COMPLETE_TRACE_VERSION_V1,
    ATLAS_RANDOM_STRENGTH_ID_V1,
)
from parity_forge.dsl import definition_hash, parse_definition


def _sha(label):
    return hashlib.sha256(label.encode("ascii")).hexdigest()


def _definition(max_plies=1):
    return parse_definition(
        {
            "schema_version": 4,
            "name": "Synthetic one-ply telemetry",
            "board_size": 3,
            "first_player": "A",
            "max_plies": max_plies,
            "roles": {
                "A": {
                    "action": {
                        "kind": "PUSH",
                        "piece": "actor",
                        "vectors": [[0, 1]],
                    },
                    "goal": {
                        "kind": "REACH_EDGE",
                        "piece": "actor",
                        "edge": "TOP",
                    },
                },
                "B": {
                    "action": {
                        "kind": "MOVE",
                        "piece": "b_actor",
                        "vectors": [[-1, 0]],
                    },
                    "goal": {
                        "kind": "REACH_EDGE",
                        "piece": "b_actor",
                        "edge": "TOP",
                    },
                },
            },
            "initial_pieces": [
                {"owner": "A", "piece": "actor", "position": [1, 0]},
                {"owner": "B", "piece": "b_actor", "position": [2, 0]},
            ],
        }
    )


def _game_slot(definition):
    return {
        "slot_id": _sha("game"),
        "profile_slot_id": _sha("profile"),
        "ordered_role_slot_ids": [_sha("role-a"), _sha("role-b")],
        "matched_start_block_id": _sha("block"),
        "transformed_definition_hash": definition_hash(definition),
        "strength": {"identity": ATLAS_RANDOM_STRENGTH_ID_V1},
        "seed_index": 0,
        "seed": 0,
        "rng_scope": "fresh-random.Random(seed)-per-game",
        "rng_stream": "one-stream-shared-by-both-roles-in-ply-order",
    }


def _sampled_record(definition, game, status="COMPLETE", trace=None):
    if trace is None and status == "COMPLETE":
        trace = {
            "trace_version": ATLAS_COMPLETE_TRACE_VERSION_V1,
            "definition_hash": definition_hash(definition),
            "actions": [
                {"kind": "PUSH", "from": [1, 0], "to": [1, 1]}
            ],
            "plies": 1,
            "winner": None,
            "terminal_reason": "PLY_LIMIT",
        }
    unsigned = {
        "record_version": 1,
        "record_kind": "SAMPLED_GAME",
        "strength_identity": ATLAS_RANDOM_STRENGTH_ID_V1,
        "status": status,
        "game_slot_id": game["slot_id"],
        "profile_slot_id": game["profile_slot_id"],
        "ordered_role_slot_ids": game["ordered_role_slot_ids"],
        "matched_start_block_id": game["matched_start_block_id"],
        "seed_index": game["seed_index"],
        "seed": game["seed"],
        "definition_hash": game["transformed_definition_hash"],
        "definition_byte_count": 1 if status == "COMPLETE" else None,
        "agent_a": ATLAS_RANDOM_STRENGTH_ID_V1,
        "agent_b": ATLAS_RANDOM_STRENGTH_ID_V1,
        "rng_scope": game["rng_scope"],
        "rng_stream": game["rng_stream"],
        "decisions": [],
        "node_ledger_or_null": None,
        "complete_trace_or_null": trace,
        "censored_prefix_or_null": None if status == "COMPLETE" else {"kind": "x"},
    }
    return {
        **unsigned,
        "record_root": domain_identity(
            b"parity-forge:plan0013:random-game-record:v1\0", unsigned
        ),
    }


class AtlasTelemetryStageTests(unittest.TestCase):
    def test_completion_failure_before_completed_body_seals_failed(self):
        store = mock.MagicMock()
        store.__enter__.return_value = store
        store.stage_lock.return_value.__enter__.return_value = None
        store.artifact_exists.return_value = False
        inputs = SimpleNamespace(
            contract=SimpleNamespace(stage_protocol_id=telemetry_stage.ATLAS_TELEMETRY_STAGE_PROTOCOL_ID_V1),
            protocol={},
            detached_manifest={},
            production_closure=object(),
            ordered_parent_terminal_seals=(),
            experiment_plan_bytes=b"plan",
        )
        summary = {
            "slot_count": 36_864,
            "result_count": 0,
            "status_counts": {
                "VALIDATED": 0,
                "NOT_ADMISSIBLE": 36_864,
                "MISSING": 0,
                "INVALID": 0,
                "PROOF_CONTRADICTION": 0,
            },
        }
        seal_failed = mock.Mock(return_value={"identity": _sha("failed")})
        with mock.patch.multiple(
            telemetry_stage,
            ImmutableEvidenceStore=mock.Mock(return_value=store),
            read_authenticated_stage_inputs=mock.Mock(return_value=inputs),
            _sampled_inputs_from_parents_v1=mock.Mock(return_value=({}, {}, {})),
            _telemetry_ledger_spec_v1=mock.Mock(return_value=object()),
            _prerequisites_pass_v1=mock.Mock(return_value=True),
            begin_stage=mock.Mock(),
            _execute_telemetry_journal_v1=mock.Mock(return_value=summary),
            publish_stage_completion_evidence=mock.Mock(return_value=object()),
            seal_completed_stage=mock.Mock(side_effect=OSError("before publish")),
            seal_failed_stage=seal_failed,
        ):
            result = telemetry_stage.run_atlas_telemetry_stage_v1("/tmp/repository")
        self.assertEqual(result["lifecycle"], "FAILED")
        seal_failed.assert_called_once()

    def test_invalid_or_contradictory_result_cannot_pass_completion_gate(self):
        for forbidden_status in ("INVALID", "PROOF_CONTRADICTION"):
            with self.subTest(status=forbidden_status):
                store = mock.MagicMock()
                store.__enter__.return_value = store
                store.stage_lock.return_value.__enter__.return_value = None
                store.artifact_exists.return_value = False
                inputs = SimpleNamespace(
                    contract=SimpleNamespace(
                        stage_protocol_id=(
                            telemetry_stage.ATLAS_TELEMETRY_STAGE_PROTOCOL_ID_V1
                        )
                    ),
                    protocol={},
                    detached_manifest={},
                    production_closure=object(),
                    ordered_parent_terminal_seals=(),
                    experiment_plan_bytes=b"plan",
                )
                counts = {
                    "VALIDATED": 36_863,
                    "NOT_ADMISSIBLE": 0,
                    "MISSING": 0,
                    "INVALID": 0,
                    "PROOF_CONTRADICTION": 0,
                }
                counts[forbidden_status] = 1
                summary = {
                    "slot_count": 36_864,
                    "result_count": 36_864,
                    "status_counts": counts,
                }
                publish_completion = mock.Mock()
                seal_completed = mock.Mock()
                seal_failed = mock.Mock(
                    return_value={"identity": _sha("failed-" + forbidden_status)}
                )
                with mock.patch.multiple(
                    telemetry_stage,
                    ImmutableEvidenceStore=mock.Mock(return_value=store),
                    read_authenticated_stage_inputs=mock.Mock(return_value=inputs),
                    _sampled_inputs_from_parents_v1=mock.Mock(
                        return_value=({}, {}, {})
                    ),
                    _telemetry_ledger_spec_v1=mock.Mock(return_value=object()),
                    _prerequisites_pass_v1=mock.Mock(return_value=True),
                    begin_stage=mock.Mock(),
                    _execute_telemetry_journal_v1=mock.Mock(
                        return_value=summary
                    ),
                    publish_stage_completion_evidence=publish_completion,
                    seal_completed_stage=seal_completed,
                    seal_failed_stage=seal_failed,
                ):
                    result = telemetry_stage.run_atlas_telemetry_stage_v1(
                        "/tmp/repository"
                    )
                self.assertEqual(result["lifecycle"], "FAILED")
                publish_completion.assert_not_called()
                seal_completed.assert_not_called()
                seal_failed.assert_called_once()

    def test_evidence_phase_projection_authenticates_envelopes_and_order(self):
        slot_id = _sha("evidence-slot")
        contract = type(
            "Contract",
            (),
            {"stage_id": "PARENT", "stage_protocol_id": "parent-v1"},
        )()
        start = {
            "artifact_type": "ATLAS_SLOT_START_V1",
            "phase_id": "sampled",
            "slot_id": slot_id,
            "slot_index": 0,
            "stage_protocol_id": "parent-v1",
        }
        raw = {
            "game_slot_id": slot_id,
            "status": "COMPLETE",
            "record_root": _sha("raw"),
        }
        envelope = {
            "artifact_type": "ATLAS_SLOT_RESULT_V1",
            "phase_id": "sampled",
            "result": raw,
            "slot_id": slot_id,
            "slot_index": 0,
            "stage_protocol_id": "parent-v1",
            "start_ref": canonical_body_ref(start).as_dict(),
            "status": "COMPLETE",
        }
        ledger_set = {
            "artifact_type": "ATLAS_FULL_STATUS_LEDGER_SET_V1",
            "ledgers": [
                {
                    "artifact_type": "ATLAS_FULL_STATUS_LEDGER_V1",
                    "phase_id": "sampled",
                    "slot_count": 1,
                    "slots": [
                        {
                            "result_ref_or_null": canonical_body_ref(envelope).as_dict(),
                            "slot_id": slot_id,
                            "slot_index": 0,
                            "start_ref_or_null": canonical_body_ref(start).as_dict(),
                            "status": "COMPLETE",
                        }
                    ],
                    "stage_id": "PARENT",
                    "stage_protocol_id": "parent-v1",
                    "status_counts": {"COMPLETE": 1},
                }
            ],
            "phase_ids": ["sampled"],
            "stage_id": "PARENT",
            "stage_protocol_id": "parent-v1",
        }

        class Store:
            def read_journal_start(self, *_args):
                return copy.deepcopy(start)

            def read_journal_result(self, *_args):
                return copy.deepcopy(envelope)

        observed, started, records = telemetry_stage._validated_phase_rows_v1(
            Store(),
            contract,
            ledger_set,
            "sampled",
            (slot_id,),
            ("COMPLETE",),
            "INCOMPLETE",
            "NOT_RUN",
        )
        self.assertEqual(started, [slot_id])
        self.assertEqual(records, [raw])
        self.assertEqual(observed[0]["record_root_or_null"], raw["record_root"])

        forged = copy.deepcopy(ledger_set)
        forged["ledgers"][0]["slots"][0]["slot_index"] = 1
        with self.assertRaisesRegex(ValueError, "order or identity"):
            telemetry_stage._validated_phase_rows_v1(
                Store(),
                contract,
                forged,
                "sampled",
                (slot_id,),
                ("COMPLETE",),
                "INCOMPLETE",
                "NOT_RUN",
            )

        swapped_envelope = copy.deepcopy(envelope)
        swapped_envelope["result"]["game_slot_id"] = _sha("another-slot")
        swapped_ledger = copy.deepcopy(ledger_set)
        swapped_ledger["ledgers"][0]["slots"][0][
            "result_ref_or_null"
        ] = canonical_body_ref(swapped_envelope).as_dict()

        class SwappedStore(Store):
            def read_journal_result(self, *_args):
                return copy.deepcopy(swapped_envelope)

        with self.assertRaisesRegex(ValueError, "journal slot"):
            telemetry_stage._validated_phase_rows_v1(
                SwappedStore(),
                contract,
                swapped_ledger,
                "sampled",
                (slot_id,),
                ("COMPLETE",),
                "INCOMPLETE",
                "NOT_RUN",
            )

    def test_complete_trace_derives_and_exactly_revalidates_telemetry(self):
        definition = _definition()
        game = _game_slot(definition)
        sampled = _sampled_record(definition, game)
        before = copy.deepcopy(sampled)
        record = telemetry_stage.derive_atlas_telemetry_record_v1(
            game, definition.to_dict(), sampled
        )
        self.assertEqual(record["status"], "VALIDATED")
        self.assertEqual(record["trace_plies_or_null"], 1)
        self.assertEqual(record["telemetry_or_null"]["work"]["replayed_actions"], 1)
        self.assertEqual(record["telemetry_or_null"]["terminal"]["reason"], "PLY_LIMIT")
        self.assertEqual(sampled, before)
        self.assertEqual(
            telemetry_stage.validate_atlas_telemetry_record_v1(
                game, definition.to_dict(), sampled, record
            ),
            record,
        )

    def test_sampled_parent_rejects_extra_evidence_phase(self):
        slot_id = _sha("game")
        ledger_set = {"phase_ids": ["random", "unexpected"]}
        contract = SimpleNamespace(stage_protocol_id="parent-v1")
        with mock.patch.multiple(
            telemetry_stage,
            iter_frozen_atlas_game_schedule_from_protocol_v1=mock.Mock(
                return_value=iter(
                    (
                        {
                            "slot_id": slot_id,
                            "strength": {
                                "identity": ATLAS_RANDOM_STRENGTH_ID_V1
                            },
                        },
                    )
                )
            ),
            _parent_ledger_set_v1=mock.Mock(
                return_value=(ledger_set, "COMPLETED", contract)
            ),
        ):
            with self.assertRaisesRegex(ValueError, "unexpected phase"):
                telemetry_stage._sampled_parent_data_v1(
                    mock.Mock(),
                    {},
                    {"payload": {}},
                    stage_id="PARENT",
                    stage_protocol_id="parent-v1",
                    phase_id="random",
                    strength_identity=ATLAS_RANDOM_STRENGTH_ID_V1,
                )

    def test_noncomplete_sample_is_never_replayed(self):
        definition = _definition()
        game = _game_slot(definition)
        sampled = _sampled_record(definition, game, status="INVALID", trace=None)
        with self.assertRaisesRegex(ValueError, "only from sampled COMPLETE"):
            telemetry_stage.derive_atlas_telemetry_record_v1(
                game, definition.to_dict(), sampled
            )

    def test_invalid_complete_trace_is_retained_as_invalid(self):
        definition = _definition()
        game = _game_slot(definition)
        trace = {
            "trace_version": 1,
            "definition_hash": definition_hash(definition),
            "actions": [{"kind": "PUSH", "from": [1, 0], "to": [9, 9]}],
            "plies": 1,
            "winner": None,
            "terminal_reason": "PLY_LIMIT",
        }
        sampled = _sampled_record(definition, game, trace=trace)
        record = telemetry_stage.derive_atlas_telemetry_record_v1(
            game, definition.to_dict(), sampled
        )
        self.assertEqual(record["status"], "INVALID")
        self.assertIsNone(record["telemetry_or_null"])
        self.assertEqual(record["error_or_null"]["kind"], "INVALID_COMPLETE_TRACE")

    def test_frozen_ply_cap_breach_is_a_proof_contradiction(self):
        definition = _definition(max_plies=19)
        game = _game_slot(definition)
        sampled = _sampled_record(definition, game)
        record = telemetry_stage.derive_atlas_telemetry_record_v1(
            game, definition.to_dict(), sampled
        )
        self.assertEqual(record["status"], "PROOF_CONTRADICTION")
        self.assertEqual(
            record["contradiction_or_null"]["kind"],
            "TRACE_STRUCTURAL_CAP_EXCEEDED",
        )

    def test_record_and_sample_roots_fail_closed(self):
        definition = _definition()
        game = _game_slot(definition)
        sampled = _sampled_record(definition, game)
        sampled["record_root"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "root"):
            telemetry_stage.derive_atlas_telemetry_record_v1(
                game, definition.to_dict(), sampled
            )

        sampled = _sampled_record(definition, game)
        record = telemetry_stage.derive_atlas_telemetry_record_v1(
            game, definition.to_dict(), sampled
        )
        record["telemetry_or_null"]["work"]["replayed_actions"] = 0
        with self.assertRaises(ValueError):
            telemetry_stage.validate_atlas_telemetry_record_v1(
                game, definition.to_dict(), sampled, record
            )

    def test_cli_and_import_boundary_are_minimal(self):
        parsed = telemetry_stage._build_parser().parse_args(
            ["recover", "--repository", "/tmp/repo"]
        )
        self.assertEqual(parsed.command, "recover")
        with self.assertRaises(SystemExit):
            telemetry_stage._build_parser().parse_args(
                ["run", "--repository", "/tmp/repo", "--game", "1"]
            )

        path = Path(telemetry_stage.__file__)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        local_imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.level
        }
        self.assertTrue(
            local_imports.issubset(
                {
                    "agency",
                    "atlas_evidence",
                    "atlas_protocol",
                    "atlas_stage_data",
                }
            )
        )
        self.assertFalse(
            local_imports.intersection(
                {
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


if __name__ == "__main__":
    unittest.main()
