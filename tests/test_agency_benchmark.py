import copy
import hashlib
import json
import unittest

from parity_forge.agency import derive_replay_telemetry_v1
from parity_forge.dsl import definition_hash, parse_definition
from parity_forge.symmetry import D4_TRANSFORMS, transform_definition


TRACE_DIGEST_DOMAIN = b"parity-forge-agency-trace-v1\0"
BENCHMARK_VERSION = "occupancy-v4-agency-synthetic-benchmark-v1"
BENCHMARK_ROOT_DOMAIN = b"parity-forge-agency-synthetic-benchmark-v1\0"
EXPECTED_BENCHMARK_ROOT = (
    "6789f97e7f0948df9fa66f75933c061a08e029ce49e9d9da33ae57a7b4a59a33"
)


def _trace_digest(definition_value, actions):
    parsed = parse_definition(definition_value)
    projection = {
        "definition_hash": definition_hash(parsed),
        "actions": copy.deepcopy(actions),
    }
    encoded = json.dumps(
        projection,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(TRACE_DIGEST_DOMAIN + encoded).hexdigest()


def _full_board_stuck_definition():
    initial_pieces = []
    for row in range(3):
        for column in range(3):
            if (row, column) == (1, 1):
                initial_pieces.append(
                    {"owner": "B", "piece": "b", "position": [row, column]}
                )
            else:
                initial_pieces.append(
                    {
                        "owner": "A",
                        "piece": "block",
                        "position": [row, column],
                    }
                )
    return {
        "schema_version": 4,
        "name": "Telemetry initial stuck zero v1",
        "board_size": 3,
        "first_player": "A",
        "max_plies": 4,
        "roles": {
            "A": {
                "action": {"kind": "PLACE", "piece": "stone"},
                "goal": {
                    "kind": "CONNECT_EDGES",
                    "piece": "stone",
                    "edges": ["BOTTOM", "TOP"],
                },
            },
            "B": {
                "action": {
                    "kind": "HOP",
                    "piece": "b",
                    "vectors": [[0, 1]],
                },
                "goal": {"kind": "REACH_EDGE", "piece": "b", "edge": "TOP"},
            },
        },
        "initial_pieces": initial_pieces,
    }


FIXTURES = (
    {
        "fixture_id": "initial-stuck-zero-v1",
        "definition": _full_board_stuck_definition(),
        "actions": [],
        "definition_hash": (
            "cb5e91d6873bc2fc847aac453608f041ac2f41d65f6f1921393fd83989d9c809"
        ),
        "trace_digest": (
            "8f2178d1145b1e499f9073e67b25f55745d69c781cca4cd86b46818fff8bee9a"
        ),
        "evidence_digest": (
            "faeb45bf83905825c0169e8eb2ea7b46cac66b4aaa3a2c8c48a257a4128d6c83"
        ),
        "terminal": {"ply": 0, "winner": "B", "reason": "NO_LEGAL_ACTION"},
    },
    {
        "fixture_id": "convert-immediate-reconvergence-v1",
        "definition": {
            "schema_version": 4,
            "name": "Telemetry immediate reconvergence v1",
            "board_size": 3,
            "first_player": "A",
            "max_plies": 2,
            "roles": {
                "A": {
                    "action": {
                        "kind": "CONVERT",
                        "piece": "converter",
                        "vectors": [[0, 1], [1, 0]],
                    },
                    "goal": {
                        "kind": "REACH_EDGE",
                        "piece": "converter",
                        "edge": "BOTTOM",
                    },
                },
                "B": {
                    "action": {
                        "kind": "MOVE",
                        "piece": "b",
                        "vectors": [[-1, 0]],
                    },
                    "goal": {
                        "kind": "REACH_EDGE",
                        "piece": "b",
                        "edge": "TOP",
                    },
                },
            },
            "initial_pieces": [
                {"owner": "A", "piece": "converter", "position": [0, 1]},
                {"owner": "A", "piece": "converter", "position": [1, 0]},
                {"owner": "B", "piece": "victim", "position": [1, 1]},
                {"owner": "B", "piece": "b", "position": [2, 2]},
            ],
        },
        "actions": [
            {"kind": "CONVERT", "from": [0, 1], "to": [1, 1]},
            {"kind": "MOVE", "from": [2, 2], "to": [1, 2]},
        ],
        "definition_hash": (
            "fd2768bc19220de4c5e0c18040982524b034e0215279d8b51b79b9a5c513a079"
        ),
        "trace_digest": (
            "4f6c06261e825af7964f96d813c3a51bb4b40e76661cd61e4c5a69cbe2cd68f9"
        ),
        "evidence_digest": (
            "e22de09d52ff6de4d7a0b68b84776be3dde6d05cf277cce1c216171873265011"
        ),
        "terminal": {"ply": 2, "winner": None, "reason": "PLY_LIMIT"},
    },
    {
        "fixture_id": "push-next-legal-sensitive-v1",
        "definition": {
            "schema_version": 4,
            "name": "Telemetry legal set sensitivity v1",
            "board_size": 3,
            "first_player": "A",
            "max_plies": 2,
            "roles": {
                "A": {
                    "action": {
                        "kind": "PUSH",
                        "piece": "p",
                        "vectors": [[0, 1]],
                    },
                    "goal": {
                        "kind": "REACH_EDGE",
                        "piece": "p",
                        "edge": "RIGHT",
                    },
                },
                "B": {
                    "action": {
                        "kind": "MOVE",
                        "piece": "b",
                        "vectors": [[-1, 0], [1, 0]],
                    },
                    "goal": {
                        "kind": "REACH_EDGE",
                        "piece": "b",
                        "edge": "LEFT",
                    },
                },
            },
            "initial_pieces": [
                {"owner": "A", "piece": "p", "position": [0, 0]},
                {"owner": "A", "piece": "block", "position": [0, 2]},
                {"owner": "A", "piece": "p", "position": [1, 0]},
                {"owner": "B", "piece": "b", "position": [1, 1]},
            ],
        },
        "actions": [
            {"kind": "PUSH", "from": [0, 0], "to": [0, 1]},
            {"kind": "MOVE", "from": [1, 1], "to": [2, 1]},
        ],
        "definition_hash": (
            "1f89f40c81b150def3f42e19304b69585cbe6174dee1bcdd8762d7f01637b48f"
        ),
        "trace_digest": (
            "18a2ca50081f04adf82542911c1fcedb14490f6a926dc9a68e047ffea5ab1fa3"
        ),
        "evidence_digest": (
            "575666d3c4b9bb007a56c7309d1ec540d0f42a11c6692e3f379491af556f51d4"
        ),
        "terminal": {"ply": 2, "winner": None, "reason": "PLY_LIMIT"},
    },
    {
        "fixture_id": "push-win-draw-loss-v1",
        "definition": {
            "schema_version": 4,
            "name": "Telemetry tri outcome v1",
            "board_size": 3,
            "first_player": "A",
            "max_plies": 1,
            "roles": {
                "A": {
                    "action": {
                        "kind": "PUSH",
                        "piece": "p",
                        "vectors": [[1, 0]],
                    },
                    "goal": {
                        "kind": "REACH_EDGE",
                        "piece": "p",
                        "edge": "BOTTOM",
                    },
                },
                "B": {
                    "action": {
                        "kind": "MOVE",
                        "piece": "b",
                        "vectors": [[0, 1]],
                    },
                    "goal": {
                        "kind": "REACH_EDGE",
                        "piece": "b",
                        "edge": "BOTTOM",
                    },
                },
            },
            "initial_pieces": [
                {"owner": "A", "piece": "p", "position": [0, 0]},
                {"owner": "A", "piece": "p", "position": [0, 2]},
                {"owner": "B", "piece": "b", "position": [1, 0]},
                {"owner": "A", "piece": "p", "position": [1, 1]},
            ],
        },
        "actions": [
            {"kind": "PUSH", "from": [0, 2], "to": [1, 2]},
        ],
        "definition_hash": (
            "f3690d6aa29f83f72b9b3208e6c0a5783a43e2711c5f9a1780a72c6cac3c2e49"
        ),
        "trace_digest": (
            "9548b3925414dcf48ed186176178dc8fc02d89b1eff85b684eea7742653ef194"
        ),
        "evidence_digest": (
            "7d59db6dad272cbab51ac2e60167fbd8ba80b44607626c3a36484b2ea2a3806f"
        ),
        "terminal": {"ply": 1, "winner": None, "reason": "PLY_LIMIT"},
    },
    {
        "fixture_id": "capture-eliminate-one-sided-b-v1",
        "definition": {
            "schema_version": 4,
            "name": "Telemetry capture eliminate v1",
            "board_size": 3,
            "first_player": "A",
            "max_plies": 4,
            "roles": {
                "A": {
                    "action": {
                        "kind": "HOP",
                        "piece": "mover",
                        "vectors": [[-1, 0]],
                    },
                    "goal": {
                        "kind": "REACH_EDGE",
                        "piece": "mover",
                        "edge": "TOP",
                    },
                },
                "B": {
                    "action": {
                        "kind": "MOVE_CAPTURE",
                        "piece": "hunter",
                        "vectors": [[0, -1]],
                    },
                    "goal": {"kind": "ELIMINATE", "piece": "prey"},
                },
            },
            "initial_pieces": [
                {"owner": "A", "piece": "prey", "position": [1, 0]},
                {"owner": "B", "piece": "hunter", "position": [1, 1]},
                {"owner": "A", "piece": "mover", "position": [2, 2]},
            ],
        },
        "actions": [
            {"kind": "HOP", "from": [2, 2], "to": [1, 2]},
            {"kind": "MOVE_CAPTURE", "from": [1, 1], "to": [1, 0]},
        ],
        "definition_hash": (
            "ccbf7cfe2076e6d6fbd66aa35f0a9fd1d760f7510a4ef0a1f3b0e5e4b1e66eda"
        ),
        "trace_digest": (
            "f4ce6b1caec637df898a2ea249af9c1070ceca1421f113631b4c5dceca82363f"
        ),
        "evidence_digest": (
            "b849f2037ccdf18914c26d0ddbbec05fca1818c67b6ac16b7189d08f9d39a4c1"
        ),
        "terminal": {"ply": 2, "winner": "B", "reason": "GOAL"},
    },
    {
        "fixture_id": "swap-both-roles-repeat-v1",
        "definition": {
            "schema_version": 4,
            "name": "Telemetry both roles repeat v1",
            "board_size": 3,
            "first_player": "A",
            "max_plies": 3,
            "roles": {
                "A": {
                    "action": {
                        "kind": "SWAP",
                        "piece": "a",
                        "vectors": [[0, 1]],
                    },
                    "goal": {
                        "kind": "REACH_EDGE",
                        "piece": "a",
                        "edge": "TOP",
                    },
                },
                "B": {
                    "action": {
                        "kind": "SWAP",
                        "piece": "b",
                        "vectors": [[0, 1]],
                    },
                    "goal": {
                        "kind": "REACH_EDGE",
                        "piece": "b",
                        "edge": "BOTTOM",
                    },
                },
            },
            "initial_pieces": [
                {"owner": "A", "piece": "a", "position": [1, 0]},
                {"owner": "B", "piece": "b", "position": [1, 1]},
            ],
        },
        "actions": [
            {"kind": "SWAP", "from": [1, 0], "to": [1, 1]},
            {"kind": "SWAP", "from": [1, 0], "to": [1, 1]},
            {"kind": "SWAP", "from": [1, 0], "to": [1, 1]},
        ],
        "definition_hash": (
            "ac4a2b98eba51c0a0037f65fa52f1c101d5f28cd6824d111d3ff6a721d21b7b6"
        ),
        "trace_digest": (
            "a6d5b63fe532789e579d1a22e63bd2118ae88404cff2e5f8aa4650d28d1ea874"
        ),
        "evidence_digest": (
            "708f8eb57f61fb4f25331639d902c655b3413659b4f7eb2f242997500b6f85d6"
        ),
        "terminal": {"ply": 3, "winner": None, "reason": "PLY_LIMIT"},
    },
    {
        "fixture_id": "hop-opponent-dependency-without-direct-effect-v1",
        "definition": {
            "schema_version": 4,
            "name": "Telemetry hop opponent dependency v1",
            "board_size": 3,
            "first_player": "A",
            "max_plies": 1,
            "roles": {
                "A": {
                    "action": {
                        "kind": "HOP",
                        "piece": "hopper",
                        "vectors": [[0, 1]],
                    },
                    "goal": {
                        "kind": "REACH_EDGE",
                        "piece": "hopper",
                        "edge": "TOP",
                    },
                },
                "B": {
                    "action": {
                        "kind": "MOVE",
                        "piece": "blocker",
                        "vectors": [[1, 0]],
                    },
                    "goal": {
                        "kind": "REACH_EDGE",
                        "piece": "blocker",
                        "edge": "BOTTOM",
                    },
                },
            },
            "initial_pieces": [
                {"owner": "A", "piece": "hopper", "position": [1, 0]},
                {"owner": "B", "piece": "blocker", "position": [1, 1]},
            ],
        },
        "actions": [
            {"kind": "HOP", "from": [1, 0], "to": [1, 2]},
        ],
        "definition_hash": (
            "08536bcae39cf0f8eaaf541ba4e570288572cb9bedac93c43041a2ea0219fd84"
        ),
        "trace_digest": (
            "d31860dd9cd08adf1d122f200293e54fcca29ce40bb2a1de754161bfc407a2a2"
        ),
        "evidence_digest": (
            "cc3a465dd3fe4ec8d2a35687764c5405c93b9f9e5c03b630f3e370f8aaada7ad"
        ),
        "terminal": {"ply": 1, "winner": None, "reason": "PLY_LIMIT"},
    },
)


FIXTURE_BY_ID = {fixture["fixture_id"]: fixture for fixture in FIXTURES}


def _benchmark_root():
    payload = {
        "benchmark_version": BENCHMARK_VERSION,
        "fixtures": [
            {
                "fixture_id": fixture["fixture_id"],
                "definition_hash": fixture["definition_hash"],
                "trace_digest": fixture["trace_digest"],
                "evidence_digest": fixture["evidence_digest"],
            }
            for fixture in FIXTURES
        ],
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(BENCHMARK_ROOT_DOMAIN + encoded).hexdigest()


def _telemetry(fixture):
    return derive_replay_telemetry_v1(
        fixture["definition"], fixture["actions"]
    ).to_dict()


def _count(mapping, key):
    return mapping.get(key, 0)


def _assert_effect(test, effect, *, own=0, opponent=0, convert=0, remove=0):
    test.assertEqual(effect["own_movements"], own)
    test.assertEqual(effect["opponent_movements"], opponent)
    test.assertEqual(effect["conversions"], convert)
    test.assertEqual(effect["removals"], remove)


def _transform_position(position, size, transform):
    row, column = position
    maximum = size - 1
    return {
        "I": (row, column),
        "R90": (column, maximum - row),
        "R180": (maximum - row, maximum - column),
        "R270": (maximum - column, row),
        "FLR": (row, maximum - column),
        "FTB": (maximum - row, column),
        "FD": (column, row),
        "FA": (maximum - column, maximum - row),
    }[transform]


def _transform_actions(actions, size, transform):
    transformed = []
    for action in actions:
        result = {"kind": action["kind"]}
        if "from" in action:
            result["from"] = list(
                _transform_position(tuple(action["from"]), size, transform)
            )
        result["to"] = list(
            _transform_position(tuple(action["to"]), size, transform)
        )
        transformed.append(result)
    return transformed


def _metric_projection(value):
    excluded = {
        "definition_hash",
        "actions",
        "chosen_action",
        "pre_state_digest",
        "counterfactual_digest",
        "evidence_digest",
    }

    def project(item):
        if isinstance(item, dict):
            return {
                key: project(child)
                for key, child in item.items()
                if key not in excluded and not key.endswith("_digest")
            }
        if isinstance(item, list):
            return [project(child) for child in item]
        return item

    return project(copy.deepcopy(value))


def _role_swapped_definition(definition):
    result = copy.deepcopy(definition)
    result["name"] = definition["name"] + " role swapped"
    result["first_player"] = "B" if definition["first_player"] == "A" else "A"
    result["roles"] = {
        "A": copy.deepcopy(definition["roles"]["B"]),
        "B": copy.deepcopy(definition["roles"]["A"]),
    }
    for piece in result["initial_pieces"]:
        piece["owner"] = "B" if piece["owner"] == "A" else "A"
    return result


def _unmap_role_swap_metrics(value):
    result = _metric_projection(value)
    result["roles"] = {
        "A": result["roles"]["B"],
        "B": result["roles"]["A"],
    }
    result["roles"]["A"]["player"] = "A"
    result["roles"]["B"]["player"] = "B"
    for decision in result["decisions"]:
        decision["actor"] = "B" if decision["actor"] == "A" else "A"
    winner = result["terminal"]["winner"]
    if winner is not None:
        result["terminal"]["winner"] = "B" if winner == "A" else "A"
    result["direct_effect_status"] = {
        "NONE": "NONE",
        "A_ONLY": "B_ONLY",
        "B_ONLY": "A_ONLY",
        "BOTH_ROLES": "BOTH_ROLES",
    }[result["direct_effect_status"]]
    return result


class ReplayTelemetrySyntheticBenchmarkTests(unittest.TestCase):
    def test_frozen_definitions_actions_and_complete_terminals(self):
        self.assertEqual(len(FIXTURES), 7)
        self.assertEqual(len(FIXTURE_BY_ID), 7)
        self.assertEqual(_benchmark_root(), EXPECTED_BENCHMARK_ROOT)

        for fixture in FIXTURES:
            with self.subTest(fixture=fixture["fixture_id"]):
                parsed = parse_definition(fixture["definition"])
                self.assertEqual(
                    definition_hash(parsed), fixture["definition_hash"]
                )
                self.assertEqual(
                    _trace_digest(fixture["definition"], fixture["actions"]),
                    fixture["trace_digest"],
                )
                stored = _telemetry(fixture)
                self.assertEqual(stored["definition_hash"], fixture["definition_hash"])
                self.assertEqual(stored["actions"], fixture["actions"])
                self.assertEqual(stored["terminal"], fixture["terminal"])
                self.assertEqual(
                    stored["evidence_digest"], fixture["evidence_digest"]
                )

    def test_zero_one_two_plus_forced_and_terminal_summaries(self):
        zero = _telemetry(FIXTURE_BY_ID["initial-stuck-zero-v1"])
        self.assertEqual(
            zero["roles"]["A"]["legal_count_bins"],
            {"0": 1, "1": 0, "2+": 0},
        )
        self.assertEqual(zero["decisions"], [])
        self.assertEqual(zero["longest_forced_run"], 0)

        reconvergent = _telemetry(
            FIXTURE_BY_ID["convert-immediate-reconvergence-v1"]
        )
        self.assertEqual(
            [decision["legal_count"] for decision in reconvergent["decisions"]],
            [2, 1],
        )
        self.assertEqual(
            reconvergent["roles"]["A"]["legal_count_bins"],
            {"0": 0, "1": 0, "2+": 1},
        )
        self.assertEqual(
            reconvergent["roles"]["B"]["legal_count_bins"],
            {"0": 0, "1": 1, "2+": 0},
        )
        self.assertEqual(reconvergent["longest_forced_run"], 1)

        repeated = _telemetry(FIXTURE_BY_ID["swap-both-roles-repeat-v1"])
        self.assertEqual(
            [decision["legal_count"] for decision in repeated["decisions"]],
            [1, 1, 1],
        )
        self.assertEqual(repeated["longest_forced_run"], 3)

    def test_convert_actions_immediately_reconverge(self):
        stored = _telemetry(
            FIXTURE_BY_ID["convert-immediate-reconvergence-v1"]
        )
        decision = stored["decisions"][0]

        self.assertEqual(decision["legal_count"], 2)
        self.assertEqual(_count(decision["legal_action_kind_counts"], "CONVERT"), 2)
        self.assertEqual(_count(decision["legal_effect_mode_counts"], "CONVERT"), 2)
        self.assertEqual(decision["chosen_effect_mode"], "CONVERT")
        _assert_effect(self, decision["chosen_effect"], convert=1)
        self.assertFalse(decision["ordinary_step_available"])
        self.assertFalse(decision["conditional_special_available"])
        self.assertFalse(decision["chosen_conditional_special"])
        self.assertEqual(decision["successor_position_variant_count"], 1)
        self.assertEqual(decision["effect_signature_variant_count"], 1)
        self.assertTrue(decision["immediate_reconvergence"])
        self.assertEqual(decision["redundant_successor_count"], 1)
        self.assertEqual(
            _count(decision["immediate_outcome_class_counts"], "NONTERMINAL"),
            2,
        )
        self.assertFalse(decision["immediate_outcome_sensitive"])
        self.assertEqual(decision["nonterminal_successor_count"], 2)
        self.assertTrue(decision["next_legal_set_comparable"])
        self.assertEqual(decision["next_legal_set_variant_count"], 1)
        self.assertFalse(decision["next_legal_set_sensitive"])
        self.assertEqual(stored["direct_effect_status"], "A_ONLY")

    def test_next_legal_set_sensitivity_is_separate_from_terminal_sensitivity(self):
        stored = _telemetry(FIXTURE_BY_ID["push-next-legal-sensitive-v1"])
        decision = stored["decisions"][0]

        self.assertEqual(decision["legal_count"], 2)
        self.assertEqual(_count(decision["legal_effect_mode_counts"], "ORDINARY_STEP"), 1)
        self.assertEqual(_count(decision["legal_effect_mode_counts"], "PUSH"), 1)
        self.assertTrue(decision["ordinary_step_available"])
        self.assertTrue(decision["conditional_special_available"])
        self.assertFalse(decision["chosen_conditional_special"])
        self.assertEqual(decision["successor_position_variant_count"], 2)
        self.assertEqual(decision["effect_signature_variant_count"], 2)
        self.assertFalse(decision["immediate_reconvergence"])
        self.assertFalse(decision["immediate_outcome_sensitive"])
        self.assertEqual(decision["nonterminal_successor_count"], 2)
        self.assertTrue(decision["next_legal_set_comparable"])
        self.assertEqual(decision["next_legal_set_variant_count"], 2)
        self.assertTrue(decision["next_legal_set_sensitive"])
        self.assertEqual(stored["direct_effect_status"], "NONE")

    def test_immediate_outcomes_are_actor_relative_win_draw_and_loss(self):
        stored = _telemetry(FIXTURE_BY_ID["push-win-draw-loss-v1"])
        decision = stored["decisions"][0]

        self.assertEqual(decision["legal_count"], 3)
        self.assertEqual(_count(decision["legal_effect_mode_counts"], "ORDINARY_STEP"), 2)
        self.assertEqual(_count(decision["legal_effect_mode_counts"], "PUSH"), 1)
        self.assertEqual(
            {
                label: _count(decision["immediate_outcome_class_counts"], label)
                for label in ("ACTOR_WIN", "DRAW", "ACTOR_LOSS", "NONTERMINAL")
            },
            {
                "ACTOR_WIN": 1,
                "DRAW": 1,
                "ACTOR_LOSS": 1,
                "NONTERMINAL": 0,
            },
        )
        self.assertTrue(decision["immediate_outcome_sensitive"])
        self.assertEqual(decision["nonterminal_successor_count"], 0)
        self.assertFalse(decision["next_legal_set_comparable"])
        self.assertIsNone(decision["next_legal_set_variant_count"])
        self.assertIsNone(decision["next_legal_set_sensitive"])
        self.assertEqual(stored["direct_effect_status"], "NONE")

    def test_capture_realizes_b_only_effect_and_eliminate_goal(self):
        stored = _telemetry(
            FIXTURE_BY_ID["capture-eliminate-one-sided-b-v1"]
        )
        first, capture = stored["decisions"]

        self.assertEqual(first["chosen_effect_mode"], "ORDINARY_STEP")
        _assert_effect(self, first["chosen_effect"], own=1)
        self.assertEqual(capture["chosen_effect_mode"], "CAPTURE")
        _assert_effect(self, capture["chosen_effect"], own=1, remove=1)
        self.assertTrue(capture["chosen_effect"]["opponent_dependency"])
        self.assertTrue(capture["chosen_effect"]["realized_opponent_effect"])
        self.assertEqual(
            _count(capture["immediate_outcome_class_counts"], "ACTOR_WIN"), 1
        )
        self.assertEqual(stored["direct_effect_status"], "B_ONLY")
        self.assertEqual(
            stored["terminal"], {"ply": 2, "winner": "B", "reason": "GOAL"}
        )

    def test_both_roles_swap_trace_is_forced_and_repeats_before_terminal(self):
        stored = _telemetry(FIXTURE_BY_ID["swap-both-roles-repeat-v1"])

        self.assertEqual(stored["direct_effect_status"], "BOTH_ROLES")
        self.assertEqual(stored["longest_forced_run"], 3)
        for decision in stored["decisions"]:
            self.assertEqual(decision["chosen_effect_mode"], "SWAP")
            _assert_effect(self, decision["chosen_effect"], own=1, opponent=1)
            self.assertTrue(decision["chosen_effect"]["realized_opponent_effect"])

        repetition = stored["repetition"]
        self.assertTrue(repetition["has_repeated_configuration"])
        self.assertEqual(repetition["first_repeat_ply"], 2)
        self.assertEqual(repetition["first_repeat_period"], 2)
        self.assertTrue(repetition["terminal_configuration_repeated"])
        self.assertEqual(repetition["cycle_prefix_plies"], 2)

    def test_hop_opponent_dependency_is_not_a_direct_effect(self):
        stored = _telemetry(
            FIXTURE_BY_ID["hop-opponent-dependency-without-direct-effect-v1"]
        )
        decision = stored["decisions"][0]

        self.assertEqual(decision["legal_count"], 1)
        self.assertEqual(decision["chosen_effect_mode"], "HOP")
        _assert_effect(self, decision["chosen_effect"], own=1)
        self.assertTrue(decision["chosen_effect"]["opponent_dependency"])
        self.assertFalse(decision["chosen_effect"]["realized_opponent_effect"])
        self.assertTrue(decision["conditional_special_available"])
        self.assertTrue(decision["chosen_conditional_special"])
        self.assertEqual(stored["direct_effect_status"], "NONE")

    def test_all_d4_orientations_preserve_the_metric_projection(self):
        for fixture in FIXTURES:
            base = _metric_projection(_telemetry(fixture))
            definition = parse_definition(fixture["definition"])
            for transform in D4_TRANSFORMS:
                with self.subTest(fixture=fixture["fixture_id"], transform=transform):
                    transformed_definition = transform_definition(
                        definition, transform
                    ).to_dict()
                    transformed_actions = _transform_actions(
                        fixture["actions"],
                        fixture["definition"]["board_size"],
                        transform,
                    )
                    transformed = derive_replay_telemetry_v1(
                        transformed_definition, transformed_actions
                    ).to_dict()
                    self.assertEqual(_metric_projection(transformed), base)

    def test_role_swap_metamorphic_relation_on_both_roles_swap_cycle(self):
        fixture = FIXTURE_BY_ID["swap-both-roles-repeat-v1"]
        base = _metric_projection(_telemetry(fixture))
        swapped = derive_replay_telemetry_v1(
            _role_swapped_definition(fixture["definition"]),
            fixture["actions"],
        ).to_dict()

        self.assertEqual(_unmap_role_swap_metrics(swapped), base)


if __name__ == "__main__":
    unittest.main()
