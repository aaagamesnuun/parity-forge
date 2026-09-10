import ast
import hashlib
import inspect
import unittest
from pathlib import Path
from unittest import mock

import parity_forge.atlas_exact_stage as exact_stage
from parity_forge.dsl import definition_hash, parse_definition
from parity_forge.symmetry import D4_TRANSFORMS, transform_definition


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "parity_forge"
    / "atlas_exact_stage.py"
)


def _digest(label):
    return hashlib.sha256(label.encode("ascii")).hexdigest()


def _definition():
    return parse_definition(
        {
            "schema_version": 4,
            "name": "Synthetic exact stage fixture",
            "board_size": 3,
            "first_player": "A",
            "max_plies": 2,
            "roles": {
                "A": {
                    "action": {
                        "kind": "PUSH",
                        "piece": "a",
                        "vectors": [[0, 1], [1, 0]],
                    },
                    "goal": {
                        "kind": "REACH_EDGE",
                        "piece": "never_a",
                        "edge": "BOTTOM",
                    },
                },
                "B": {
                    "action": {
                        "kind": "HOP",
                        "piece": "b",
                        "vectors": [[-1, 0], [0, -1]],
                    },
                    "goal": {
                        "kind": "REACH_EDGE",
                        "piece": "never_b",
                        "edge": "TOP",
                    },
                },
            },
            "initial_pieces": [
                {"owner": "A", "piece": "a", "position": [0, 0]},
                {"owner": "A", "piece": "a", "position": [1, 0]},
                {"owner": "B", "piece": "b", "position": [2, 2]},
            ],
        }
    )


def _exact_slot(definition, max_states=100):
    return {
        "slot_id": _digest("synthetic-exact-slot"),
        "representative_definition_hash": definition_hash(definition),
        "max_states": max_states,
        "max_action_candidates_per_state": 48,
        "max_state_action_candidate_evaluations": max_states * 48,
    }


def _orientation_slot(exact_slot, definition, transform_index):
    transform = D4_TRANSFORMS[transform_index]
    transformed = transform_definition(definition, transform)
    return {
        "slot_id": _digest("synthetic-orientation-{}".format(transform_index)),
        "exact_slot_id": exact_slot["slot_id"],
        "transform_index": transform_index,
        "transform": transform,
        "transformed_definition_hash": definition_hash(transformed),
    }, transformed


class AtlasExactStageTests(unittest.TestCase):
    def test_ledger_specs_cover_both_exact_and_pv_phases(self):
        with mock.patch.object(
            exact_stage,
            "iter_frozen_atlas_exact_schedule_from_protocol_v1",
            return_value=iter(({"slot_id": "exact-0"}, {"slot_id": "exact-1"})),
        ), mock.patch.object(
            exact_stage,
            "iter_frozen_atlas_orientation_schedule_from_protocol_v1",
            return_value=iter(({"slot_id": "pv-0"}, {"slot_id": "pv-1"})),
        ):
            specs = exact_stage._exact_ledger_specs_v1({})
        self.assertEqual(len(specs), 2)
        self.assertEqual(specs[0].phase_id, "exact")
        self.assertEqual(specs[0].ordered_slot_ids, ("exact-0", "exact-1"))
        self.assertEqual(specs[1].phase_id, "exact-pv")
        self.assertEqual(specs[1].ordered_slot_ids, ("pv-0", "pv-1"))

    def test_synthetic_solve_and_all_eight_transformed_pv_replays(self):
        definition = _definition()
        slot = _exact_slot(definition)
        record, result = exact_stage._solve_exact_slot_v1(
            slot, definition.to_dict()
        )
        self.assertEqual(record["status"], "COMPLETE")
        self.assertEqual(record["slot_id"], slot["slot_id"])
        self.assertEqual(record["result_or_null"]["searched_states"], result.searched_states)
        self.assertLessEqual(result.searched_states, slot["max_states"])

        pv_records = []
        for index in range(8):
            orientation, transformed = _orientation_slot(slot, definition, index)
            pv_records.append(
                exact_stage._replay_orientation_pv_v1(
                    slot,
                    orientation,
                    definition.to_dict(),
                    transformed.to_dict(),
                    result,
                )
            )
        self.assertEqual(len(pv_records), 8)
        self.assertEqual({record["status"] for record in pv_records}, {"VALID"})
        self.assertEqual(
            {record["forced_result_or_null"] for record in pv_records},
            {result.forced_result},
        )
        self.assertEqual(len({record["record_root"] for record in pv_records}), 8)

    def test_state_cap_exhaustion_is_proof_contradiction(self):
        definition = _definition()
        record, result = exact_stage._solve_exact_slot_v1(
            _exact_slot(definition, max_states=1), definition.to_dict()
        )
        self.assertIsNone(result)
        self.assertEqual(record["status"], "PROOF_CONTRADICTION")
        self.assertEqual(
            record["contradiction_or_null"]["kind"],
            "EXACT_STATE_CAP_EXHAUSTED",
        )

    def test_replay_rejects_a_definition_outside_its_declared_transform(self):
        definition = _definition()
        slot = _exact_slot(definition)
        _record, result = exact_stage._solve_exact_slot_v1(slot, definition.to_dict())
        orientation, transformed = _orientation_slot(slot, definition, 1)
        forged = transformed.to_dict()
        forged["name"] = "forged transformed body"
        with self.assertRaisesRegex(ValueError, "definition hash"):
            exact_stage._replay_orientation_pv_v1(
                slot, orientation, definition.to_dict(), forged, result
            )

    def test_cli_has_only_run_recover_and_repository(self):
        self.assertEqual(
            list(inspect.signature(exact_stage.run_atlas_exact_stage_v1).parameters),
            ["repository"],
        )
        self.assertEqual(
            list(
                inspect.signature(
                    exact_stage.recover_atlas_exact_stage_v1
                ).parameters
            ),
            ["repository"],
        )
        parser = exact_stage._build_parser()
        parsed = parser.parse_args(["run", "--repository", "/tmp/repo"])
        self.assertEqual((parsed.command, parsed.repository), ("run", "/tmp/repo"))
        with self.assertRaises(SystemExit):
            parser.parse_args(
                ["run", "--repository", "/tmp/repo", "--max-states", "1"]
            )

    def test_import_closure_excludes_agents_selection_and_play(self):
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        local_imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level:
                local_imports.add(node.module)
        self.assertTrue(
            local_imports.issubset(
                {
                    "atlas_protocol",
                    "atlas_stage_data",
                    "atlas_evidence",
                    "dsl",
                    "engine",
                    "solver",
                    "symmetry",
                }
            )
        )
        self.assertFalse(
            local_imports.intersection(
                {"agents", "atlas", "atlas_history", "play", "terminal_search"}
            )
        )


if __name__ == "__main__":
    unittest.main()
