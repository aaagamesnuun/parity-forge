import ast
import hashlib
import inspect
import unittest
from pathlib import Path
from unittest.mock import patch

import parity_forge.atlas_depth1_stage as depth1_stage
from parity_forge.atlas_protocol import ATLAS_TERMINAL_DEPTH1_ROLE_SLOT_CAP_V1
from parity_forge.dsl import Player, definition_hash, parse_definition
from parity_forge.terminal_search import TerminalOnlyMinimaxAgent


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "parity_forge"
    / "atlas_depth1_stage.py"
)


def _digest(label):
    return hashlib.sha256(label.encode("ascii")).hexdigest()


def _definition():
    return parse_definition(
        {
            "schema_version": 4,
            "name": "Synthetic depth-1 stage fixture",
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


def _game_slot(definition, seed):
    return {
        "slot_id": _digest("synthetic-depth1-game-{}".format(seed)),
        "profile_slot_id": _digest("synthetic-depth1-profile"),
        "ordered_role_slot_ids": [
            _digest("synthetic-depth1-role-a"),
            _digest("synthetic-depth1-role-b"),
        ],
        "matched_start_block_id": _digest("synthetic-depth1-block-{}".format(seed)),
        "transformed_definition_hash": definition_hash(definition),
        "strength": {
            "identity": "terminal_only_minimax-v1-depth1",
            "depth": 1,
            "max_total_nodes_per_role_slot": 3456,
        },
        "seed_index": seed,
        "seed": seed,
        "rng_scope": "fresh-random.Random(seed)-per-game",
        "rng_stream": "one-stream-shared-by-both-roles-in-ply-order",
    }


class AtlasDepth1StageTests(unittest.TestCase):
    def test_role_slots_are_fresh_reset_once_and_cumulative_over_eight_seeds(self):
        original_reset = TerminalOnlyMinimaxAgent.reset_budget
        reset_instances = []

        def recording_reset(agent):
            reset_instances.append(id(agent))
            return original_reset(agent)

        with patch.object(
            TerminalOnlyMinimaxAgent, "reset_budget", new=recording_reset
        ):
            agents = depth1_stage._fresh_depth1_role_agents_v1()
        self.assertIsNot(agents[Player.A], agents[Player.B])
        self.assertCountEqual(
            reset_instances, [id(agents[Player.A]), id(agents[Player.B])]
        )

        definition = _definition()
        records = []
        prior = {"A": 0, "B": 0}
        for seed in range(8):
            record = depth1_stage._run_depth1_game_v1(
                _game_slot(definition, seed), definition.to_dict(), agents
            )
            before = record["node_ledger_or_null"]["role_slot_nodes_before_game"]
            after = record["node_ledger_or_null"]["role_slot_nodes_after_game"]
            self.assertEqual(before, prior)
            self.assertGreaterEqual(after["A"], before["A"])
            self.assertGreaterEqual(after["B"], before["B"])
            self.assertLessEqual(after["A"], ATLAS_TERMINAL_DEPTH1_ROLE_SLOT_CAP_V1)
            self.assertLessEqual(after["B"], ATLAS_TERMINAL_DEPTH1_ROLE_SLOT_CAP_V1)
            prior = after
            records.append(record)
        depth1_stage._validate_depth1_profile_games_v1(records)
        self.assertEqual({record["status"] for record in records}, {"COMPLETE"})

    def test_node_exhaustion_retains_current_replayable_prefix(self):
        definition = _definition()
        agents = depth1_stage._fresh_depth1_role_agents_v1()
        agents[Player.A]._total_nodes = ATLAS_TERMINAL_DEPTH1_ROLE_SLOT_CAP_V1
        record = depth1_stage._run_depth1_game_v1(
            _game_slot(definition, 0), definition.to_dict(), agents
        )
        self.assertEqual(record["status"], "INCOMPLETE")
        self.assertIsNone(record["complete_trace_or_null"])
        prefix = record["censored_prefix_or_null"]
        self.assertEqual(prefix["actions"], [])
        self.assertEqual(prefix["plies"], 0)
        self.assertEqual(
            prefix["censor"]["kind"], "ROLE_SLOT_NODE_CAP_EXHAUSTED"
        )
        self.assertEqual(
            prefix["censor"]["max_nodes"],
            ATLAS_TERMINAL_DEPTH1_ROLE_SLOT_CAP_V1,
        )
        depth1_stage._validate_depth1_profile_games_v1([record])

    def test_profile_validator_forbids_games_after_censor(self):
        definition = _definition()
        complete_agents = depth1_stage._fresh_depth1_role_agents_v1()
        complete = depth1_stage._run_depth1_game_v1(
            _game_slot(definition, 0), definition.to_dict(), complete_agents
        )
        censored_agents = depth1_stage._fresh_depth1_role_agents_v1()
        censored_agents[Player.A]._total_nodes = ATLAS_TERMINAL_DEPTH1_ROLE_SLOT_CAP_V1
        censored = depth1_stage._run_depth1_game_v1(
            _game_slot(definition, 1), definition.to_dict(), censored_agents
        )
        after = dict(complete)
        after["seed"] = 2
        with self.assertRaisesRegex(ValueError, "terminate"):
            depth1_stage._validate_depth1_profile_games_v1(
                [complete, censored, after]
            )

    def test_cli_and_import_boundary_expose_no_scientific_controls(self):
        self.assertEqual(
            list(inspect.signature(depth1_stage.run_atlas_depth1_stage_v1).parameters),
            ["repository"],
        )
        self.assertEqual(
            list(
                inspect.signature(
                    depth1_stage.recover_atlas_depth1_stage_v1
                ).parameters
            ),
            ["repository"],
        )
        parser = depth1_stage._build_parser()
        parsed = parser.parse_args(["run", "--repository", "/tmp/repo"])
        self.assertEqual(parsed.repository, "/tmp/repo")
        with self.assertRaises(SystemExit):
            parser.parse_args(["run", "--repository", "/tmp/repo", "--depth", "2"])

        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        local_imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.level
        }
        self.assertTrue(
            local_imports.issubset(
                {
                    "atlas_protocol",
                    "atlas_stage_data",
                    "atlas_evidence",
                    "dsl",
                    "engine",
                    "terminal_search",
                }
            )
        )
        self.assertNotIn("agents", local_imports)
        self.assertFalse(
            local_imports.intersection(
                {"atlas", "atlas_history", "play", "solver", "symmetry"}
            )
        )


if __name__ == "__main__":
    unittest.main()
