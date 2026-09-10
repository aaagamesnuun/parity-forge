import ast
import hashlib
import inspect
import unittest
from pathlib import Path
from unittest.mock import patch

import parity_forge.atlas_random_stage as random_stage
from parity_forge.agents import RandomAgent
from parity_forge.dsl import Player, definition_hash, parse_definition


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "parity_forge"
    / "atlas_random_stage.py"
)


def _digest(label):
    return hashlib.sha256(label.encode("ascii")).hexdigest()


def _definition():
    return parse_definition(
        {
            "schema_version": 4,
            "name": "Synthetic random stage fixture",
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
        "slot_id": _digest("synthetic-random-game-{}".format(seed)),
        "profile_slot_id": _digest("synthetic-random-profile"),
        "ordered_role_slot_ids": [
            _digest("synthetic-random-role-a"),
            _digest("synthetic-random-role-b"),
        ],
        "matched_start_block_id": _digest("synthetic-random-block-{}".format(seed)),
        "transformed_definition_hash": definition_hash(definition),
        "strength": {"identity": "random-v1-weak"},
        "seed_index": seed,
        "seed": seed,
        "rng_scope": "fresh-random.Random(seed)-per-game",
        "rng_stream": "one-stream-shared-by-both-roles-in-ply-order",
    }


class AtlasRandomStageTests(unittest.TestCase):
    def test_eight_seed_profile_is_deterministic_and_reuses_distinct_role_agents(self):
        definition = _definition()
        agents = random_stage._fresh_random_role_agents_v1()
        self.assertIsNot(agents[Player.A], agents[Player.B])
        seen_instances = {Player.A: set(), Player.B: set()}
        seen_rngs_by_game = []
        original = RandomAgent.select_action

        def recording(agent, game_definition, state, actions, rng):
            seen_instances[state.to_move].add(id(agent))
            seen_rngs_by_game[-1].add(id(rng))
            return original(agent, game_definition, state, actions, rng)

        records = []
        with patch.object(RandomAgent, "select_action", new=recording):
            for seed in range(8):
                seen_rngs_by_game.append(set())
                records.append(
                    random_stage._run_random_game_v1(
                        _game_slot(definition, seed), definition.to_dict(), agents
                    )
                )
        random_stage._validate_random_profile_games_v1(records)
        self.assertEqual(seen_instances[Player.A], {id(agents[Player.A])})
        self.assertEqual(seen_instances[Player.B], {id(agents[Player.B])})
        self.assertTrue(all(len(rngs) == 1 for rngs in seen_rngs_by_game))
        self.assertEqual([record["seed"] for record in records], list(range(8)))
        self.assertTrue(
            all(record["complete_trace_or_null"] is not None for record in records)
        )

        replay_agents = random_stage._fresh_random_role_agents_v1()
        replay = [
            random_stage._run_random_game_v1(
                _game_slot(definition, seed), definition.to_dict(), replay_agents
            )
            for seed in range(8)
        ]
        self.assertEqual(records, replay)

    def test_same_role_instance_for_both_roles_is_rejected(self):
        definition = _definition()
        shared = RandomAgent()
        with self.assertRaisesRegex(ValueError, "distinct"):
            random_stage._run_random_game_v1(
                _game_slot(definition, 0),
                definition.to_dict(),
                {Player.A: shared, Player.B: shared},
            )

    def test_schedule_seed_and_definition_hash_are_fail_closed(self):
        definition = _definition()
        agents = random_stage._fresh_random_role_agents_v1()
        bad_seed = _game_slot(definition, 0)
        bad_seed["seed"] = 1
        with self.assertRaisesRegex(ValueError, "seed"):
            random_stage._run_random_game_v1(
                bad_seed, definition.to_dict(), agents
            )
        bad_hash = _game_slot(definition, 0)
        bad_hash["transformed_definition_hash"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "schedule hash"):
            random_stage._run_random_game_v1(
                bad_hash, definition.to_dict(), agents
            )

    def test_cli_and_import_boundary_expose_no_scientific_controls(self):
        self.assertEqual(
            list(inspect.signature(random_stage.run_atlas_random_stage_v1).parameters),
            ["repository"],
        )
        self.assertEqual(
            list(
                inspect.signature(
                    random_stage.recover_atlas_random_stage_v1
                ).parameters
            ),
            ["repository"],
        )
        parser = random_stage._build_parser()
        parsed = parser.parse_args(["recover", "--repository", "/tmp/repo"])
        self.assertEqual(parsed.command, "recover")
        with self.assertRaises(SystemExit):
            parser.parse_args(["run", "--repository", "/tmp/repo", "--seed", "4"])

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
                    "agents",
                }
            )
        )
        self.assertFalse(
            local_imports.intersection(
                {"atlas", "atlas_history", "play", "solver", "terminal_search"}
            )
        )


if __name__ == "__main__":
    unittest.main()
