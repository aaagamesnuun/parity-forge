import ast
import copy
import hashlib
import inspect
import json
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import parity_forge.atlas_agent_benchmark as benchmark_module
from parity_forge.atlas import (
    ATLAS_CANDIDATE_DEFINITION_COUNT_V1,
    ATLAS_DEVELOPMENT_DEFINITION_COUNT_V1,
    ATLAS_PAIRED_UNIVERSE_WITNESS_ROOT_V1,
    ATLAS_SEARCH_ENVELOPE_ROOT_V1,
    ATLAS_SELECTION_PARTITION_ROOT_V1,
)
from parity_forge.atlas_agent_benchmark import (
    ATLAS_AGENT_BENCHMARK_ATLAS_SEPARATION_ROOT_V1,
    ATLAS_AGENT_BENCHMARK_CANONICAL_SHA256_V1,
    ATLAS_AGENT_BENCHMARK_D4_SLOT_COUNT_V1,
    ATLAS_AGENT_BENCHMARK_EVIDENCE_ROOT_V1,
    ATLAS_AGENT_BENCHMARK_FIXTURE_COUNT_V1,
    ATLAS_AGENT_BENCHMARK_FIXTURE_ROOT_V1,
    ATLAS_AGENT_BENCHMARK_LADDER_ROOT_V1,
    ATLAS_AGENT_BENCHMARK_RANDOM_CONFORMANCE_ROOT_V1,
    ATLAS_AGENT_BENCHMARK_RANDOM_GAME_COUNT_V1,
    ATLAS_AGENT_BENCHMARK_ROOT_V1,
    ATLAS_AGENT_BENCHMARK_TERMINAL_CONFORMANCE_ROOT_V1,
    ATLAS_AGENT_BENCHMARK_TERMINAL_GAME_COUNT_V1,
    ATLAS_AGENT_DIAGNOSTIC_DEPTH2_NODE_BOUND_V1,
    ATLAS_AGENT_PRODUCTION_DEPTH1_NODE_CAP_V1,
    build_frozen_atlas_agent_benchmark_v1,
    canonical_frozen_atlas_agent_benchmark_json_v1,
    validate_frozen_atlas_agent_benchmark_v1,
)
from parity_forge.atlas_history import (
    ATLAS_SYNTHETIC_PROJECTION_ROOT_V1,
    PLAN0012_SYNTHETIC_BENCHMARK_ROOT_V1,
    PLAN0012_SYNTHETIC_FIXTURE_IDENTITIES_V1,
)
from parity_forge.symmetry import D4_TRANSFORMS


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "parity_forge"
    / "atlas_agent_benchmark.py"
)

EXPECTED_ROOTS = {
    "fixture": "9a45e26ff2e86a1de0f5b53afd7267b63e7877d29fbd8f0bf071f7a5fc99f565",
    "ladder": "62255ad512d6258250ea7af0b757530dea4e7c991fae8305b88af656ccb65e62",
    "random": "50a0ef2db98b7ade17325b34692a432cae610b9e71850a72385a29494d477576",
    "terminal": "38dce33df7283429705ef4b33b2260be4798cf355b0bc8f6493fc15e19480026",
    "evidence": "5cd0dd2a114e2b503d68131bf3892cd0d513b2d7fed12522c82425d440f8d075",
    "separation": "a82e7640346954412710ec3c2e476243917845cf145ca42353dba0ed16751eba",
    "benchmark": "340e928d5b6ba64743dbcfd252eff951af185bc7c30138ccee333710ded15da0",
    "canonical": "5097d4d516963938a74f0fd020e96d0934943ccc4b0c5a9e0c2056156a2a3ffc",
}

EXPECTED_FIXTURES = {
    "capture-eliminate-one-sided-b-v1": (
        519,
        "ccbf7cfe2076e6d6fbd66aa35f0a9fd1d760f7510a4ef0a1f3b0e5e4b1e66eda",
        "bb61383bd417dc9fa32c7d1717c309f25b8e490a0f6c39051e3db6ac4431770a",
    ),
    "convert-immediate-reconvergence-v1": (
        595,
        "fd2768bc19220de4c5e0c18040982524b034e0215279d8b51b79b9a5c513a079",
        "01425a63068bbbb5720a1dd56ffb5b9b7f38f3905f56ee9b77ae7333c110c9ed",
    ),
    "hop-opponent-dependency-without-direct-effect-v1": (
        494,
        "08536bcae39cf0f8eaaf541ba4e570288572cb9bedac93c43041a2ea0219fd84",
        "454de6d824d820179faad6cde1023804bb2ff9be73d959fca8662836be38f85a",
    ),
    "push-win-draw-loss-v1": (
        539,
        "f3690d6aa29f83f72b9b3208e6c0a5783a43e2711c5f9a1780a72c6cac3c2e49",
        "2a48252b987d917a51df5a2bfb93da3fa6c2d93768facb27f03226b53c3f3578",
    ),
    "swap-simultaneous-connect-v1": (
        590,
        "eaaf30187d95c215c2d330f1e68c92b10ff7718b85e16801de2a15353b8c3db2",
        "1a45490b6055cb99ae06ece0ece46d30891c276e1c1048297349fdadba019cf4",
    ),
}

EXPECTED_BASE_ORACLES = {
    "capture-eliminate-one-sided-b-v1": {
        "exact": (-1, "B_WIN", "GOAL", 2, 3, 2),
        "depth1": (0, 1, 0, (0,)),
        "depth2": (-1, 2, 0, (-1,)),
    },
    "convert-immediate-reconvergence-v1": {
        "exact": (0, "DRAW", "PLY_LIMIT", 2, 3, 3),
        "depth1": (0, 1, 1, (0, 0)),
        "depth2": (0, 2, 1, (0, 0)),
    },
    "hop-opponent-dependency-without-direct-effect-v1": {
        "exact": (0, "DRAW", "PLY_LIMIT", 1, 2, 1),
        "depth1": (0, 1, 0, (0,)),
        "depth2": (0, 1, 0, (0,)),
    },
    "push-win-draw-loss-v1": {
        "exact": (1, "A_WIN", "GOAL", 1, 4, 1),
        "depth1": (1, 3, 0, (-1, 0, 1)),
        "depth2": (1, 3, 0, (-1, 0, 1)),
    },
    "swap-simultaneous-connect-v1": {
        "exact": (1, "A_WIN", "GOAL", 1, 12, 1),
        "depth1": (1, 3, 0, (0, 1, 0)),
        "depth2": (1, 11, 0, (-1, 1, -1)),
    },
}


def _exact_tuple(record):
    return (
        record["value_for_a"],
        record["forced_result"],
        record["terminal_reason"],
        record["principal_variation_plies"],
        record["searched_states"],
        record["cache_hits"],
    )


def _search_tuple(record):
    return (
        record["value_for_a"],
        record["expanded_nodes"],
        record["cache_hits"],
        tuple(row["value_for_a"] for row in record["action_values"]),
    )


def _resign_benchmark_root(snapshot):
    snapshot["benchmark_root"] = benchmark_module._digest(
        benchmark_module._BENCHMARK_ROOT_DOMAIN_V1,
        {
            "benchmark_version": snapshot["benchmark_version"],
            "benchmark_id": snapshot["benchmark_id"],
            "status": snapshot["status"],
            "fixture_root": snapshot["fixture_section"]["fixture_root"],
            "ladder_root": snapshot["ladder_section"]["ladder_root"],
            "evidence_root": snapshot["evidence"]["evidence_root"],
            "atlas_separation_root": snapshot["atlas_separation"][
                "atlas_separation_root"
            ],
            "census": snapshot["census"],
        },
    )


class FrozenAtlasAgentBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = build_frozen_atlas_agent_benchmark_v1()

    def test_fixed_roots_canonical_bytes_and_public_api(self):
        snapshot = self.snapshot
        random_section = snapshot["evidence"]["random_v1_conformance"]
        observed = {
            "fixture": snapshot["fixture_section"]["fixture_root"],
            "ladder": snapshot["ladder_section"]["ladder_root"],
            "random": random_section["random_conformance_root"],
            "terminal": snapshot["evidence"][
                "terminal_only_lifecycle_conformance"
            ]["terminal_conformance_root"],
            "evidence": snapshot["evidence"]["evidence_root"],
            "separation": snapshot["atlas_separation"][
                "atlas_separation_root"
            ],
            "benchmark": snapshot["benchmark_root"],
            "canonical": hashlib.sha256(
                benchmark_module._canonical_bytes(snapshot)
            ).hexdigest(),
        }
        self.assertEqual(observed, EXPECTED_ROOTS)
        self.assertEqual(
            (
                ATLAS_AGENT_BENCHMARK_FIXTURE_ROOT_V1,
                ATLAS_AGENT_BENCHMARK_LADDER_ROOT_V1,
                ATLAS_AGENT_BENCHMARK_RANDOM_CONFORMANCE_ROOT_V1,
                ATLAS_AGENT_BENCHMARK_TERMINAL_CONFORMANCE_ROOT_V1,
                ATLAS_AGENT_BENCHMARK_EVIDENCE_ROOT_V1,
                ATLAS_AGENT_BENCHMARK_ATLAS_SEPARATION_ROOT_V1,
                ATLAS_AGENT_BENCHMARK_ROOT_V1,
                ATLAS_AGENT_BENCHMARK_CANONICAL_SHA256_V1,
            ),
            tuple(EXPECTED_ROOTS.values()),
        )
        encoded = canonical_frozen_atlas_agent_benchmark_json_v1(snapshot)
        self.assertEqual(json.loads(encoded), snapshot)
        self.assertEqual(
            hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
            EXPECTED_ROOTS["canonical"],
        )
        self.assertEqual(len(inspect.signature(
            build_frozen_atlas_agent_benchmark_v1
        ).parameters), 0)
        self.assertEqual(len(inspect.signature(
            validate_frozen_atlas_agent_benchmark_v1
        ).parameters), 1)

    def test_five_fixture_registry_and_parent_provenance_are_exact(self):
        section = self.snapshot["fixture_section"]
        self.assertEqual(section["fixture_count"], 5)
        self.assertEqual(section["fixture_count"],
                         ATLAS_AGENT_BENCHMARK_FIXTURE_COUNT_V1)
        self.assertEqual(section["reused_fixture_count"], 4)
        self.assertEqual(section["new_fixture_count"], 1)
        self.assertEqual(
            section["plan0012_synthetic_benchmark_parent_root"],
            PLAN0012_SYNTHETIC_BENCHMARK_ROOT_V1,
        )
        self.assertEqual(
            section["plan0012_synthetic_identity_projection_root"],
            ATLAS_SYNTHETIC_PROJECTION_ROOT_V1,
        )
        parent_identities = {
            fixture_id: (canonical_bytes, exact_hash, d4_hash)
            for fixture_id, exact_hash, d4_hash, canonical_bytes in (
                PLAN0012_SYNTHETIC_FIXTURE_IDENTITIES_V1
            )
        }
        rows = section["fixtures"]
        self.assertEqual(
            [row["fixture_id"] for row in rows], sorted(EXPECTED_FIXTURES)
        )
        for row in rows:
            expected = EXPECTED_FIXTURES[row["fixture_id"]]
            self.assertEqual(
                (
                    row["canonical_byte_count"],
                    row["definition_hash"],
                    row["d4_hash"],
                ),
                expected,
            )
            self.assertEqual(row["definition"]["schema_version"], 4)
            if row["provenance"] == "PLAN0012_SYNTHETIC_REUSE":
                self.assertEqual(
                    (
                        row["canonical_byte_count"],
                        row["definition_hash"],
                        row["d4_hash"],
                    ),
                    parent_identities[row["fixture_id"]],
                )
        new_rows = [
            row for row in rows
            if row["provenance"] == "PLAN0013_SYNTHETIC_ADDITION"
        ]
        self.assertEqual(
            [row["fixture_id"] for row in new_rows],
            ["swap-simultaneous-connect-v1"],
        )
        for new_row in new_rows:
            self.assertNotIn(new_row["fixture_id"], parent_identities)
            self.assertNotIn(
                new_row["definition_hash"],
                {identity[1] for identity in parent_identities.values()},
            )
            self.assertNotIn(
                new_row["d4_hash"],
                {identity[2] for identity in parent_identities.values()},
            )
        new_row = new_rows[-1]
        self.assertEqual(new_row["definition"]["max_plies"], 2)
        self.assertEqual(
            new_row["definition"]["roles"]["A"],
            {
                "action": {
                    "kind": "SWAP",
                    "piece": "a",
                    "vectors": [[0, 1]],
                },
                "goal": {
                    "kind": "CONNECT_EDGES",
                    "piece": "a",
                    "edges": ["BOTTOM", "TOP"],
                },
            },
        )
        self.assertEqual(
            new_row["definition"]["roles"]["B"]["action"],
            {
                "kind": "MOVE_CAPTURE",
                "piece": "b",
                "vectors": [[-1, 0], [0, -1], [0, 1], [1, 0]],
            },
        )

    def test_exact_and_terminal_search_base_oracles_are_frozen(self):
        base_slots = {
            slot["fixture_id"]: slot
            for slot in self.snapshot["evidence"]["ordered_d4_slots"]
            if slot["transform"] == "I"
        }
        self.assertEqual(set(base_slots), set(EXPECTED_BASE_ORACLES))
        for fixture_id, expected in EXPECTED_BASE_ORACLES.items():
            slot = base_slots[fixture_id]
            self.assertEqual(_exact_tuple(slot["exact"]), expected["exact"])
            self.assertEqual(
                [search["depth"] for search in slot["search"]], [1, 2]
            )
            for search in slot["search"]:
                self.assertEqual(
                    _search_tuple(search),
                    expected["depth{}".format(search["depth"])],
                )
                self.assertEqual(
                    search["agent_identity"],
                    "terminal_only_minimax-v1-depth{}".format(
                        search["depth"]
                    ),
                )
                self.assertEqual(search["total_nodes"],
                                 search["expanded_nodes"])
        capture = base_slots["capture-eliminate-one-sided-b-v1"]
        self.assertEqual(capture["search"][0]["value_for_a"], 0)
        self.assertEqual(capture["search"][1]["value_for_a"], -1)
        self.assertEqual(capture["exact"]["value_for_a"], -1)
        swap = base_slots["swap-simultaneous-connect-v1"]
        self.assertEqual(
            [
                row["value_for_a"]
                for row in swap["search"][0]["action_values"]
            ],
            [0, 1, 0],
        )
        self.assertEqual(
            [
                row["value_for_a"]
                for row in swap["search"][1]["action_values"]
            ],
            [-1, 1, -1],
        )
        self.assertEqual(swap["search"][1]["expanded_nodes"], 11)

    def test_all_forty_d4_slots_preserve_exact_and_search_scalars(self):
        slots = self.snapshot["evidence"]["ordered_d4_slots"]
        self.assertEqual(len(slots), 40)
        self.assertEqual(len(slots), ATLAS_AGENT_BENCHMARK_D4_SLOT_COUNT_V1)
        for fixture_index, fixture_id in enumerate(sorted(EXPECTED_FIXTURES)):
            group = slots[fixture_index * 8:(fixture_index + 1) * 8]
            self.assertEqual([row["fixture_id"] for row in group],
                             [fixture_id] * 8)
            self.assertEqual([row["transform"] for row in group],
                             list(D4_TRANSFORMS))
            self.assertEqual(
                {row["d4_hash"] for row in group},
                {EXPECTED_FIXTURES[fixture_id][2]},
            )
            exact_scalars = {
                _exact_tuple(row["exact"])
                for row in group
            }
            self.assertEqual(exact_scalars,
                             {EXPECTED_BASE_ORACLES[fixture_id]["exact"]})
            for depth_index, depth in enumerate((1, 2)):
                scalars = {
                    (
                        row["search"][depth_index]["value_for_a"],
                        row["search"][depth_index]["expanded_nodes"],
                        row["search"][depth_index]["cache_hits"],
                    )
                    for row in group
                }
                expected = EXPECTED_BASE_ORACLES[fixture_id][
                    "depth{}".format(depth)
                ]
                self.assertEqual(scalars,
                                 {(expected[0], expected[1], expected[2])})
        evidence = self.snapshot["evidence"]
        self.assertEqual(
            evidence["synthetic_exact_forced_result_counts"],
            {"A_WIN": 16, "B_WIN": 8, "DRAW": 16},
        )

    def test_dynamic_action_goal_and_terminal_priority_coverage(self):
        dynamic = self.snapshot["evidence"]["dynamic_coverage"]
        self.assertEqual(dynamic["dynamic_action_kind_count"], 5)
        self.assertEqual(
            dynamic["dynamic_action_kinds"],
            ["CONVERT", "HOP", "MOVE_CAPTURE", "PUSH", "SWAP"],
        )
        self.assertEqual(dynamic["dynamic_goal_kind_count"], 3)
        self.assertEqual(
            dynamic["dynamic_goal_kinds"],
            ["CONNECT_EDGES", "ELIMINATE", "REACH_EDGE"],
        )
        self.assertEqual(
            dynamic["terminal_priority_witnesses"],
            [
                {
                    "priority": "OPPONENT_GOAL_BEFORE_PLY_LIMIT",
                    "fixture_id": "push-win-draw-loss-v1",
                    "actor": "A",
                    "actor_goal_satisfied": False,
                    "opponent_goal_satisfied": True,
                    "winner": "B",
                },
                {
                    "priority": (
                        "ACTOR_GOAL_BEFORE_OPPONENT_GOAL_AND_PLY_LIMIT"
                    ),
                    "fixture_id": "swap-simultaneous-connect-v1",
                    "actor": "A",
                    "actor_goal_satisfied": True,
                    "opponent_goal_satisfied": True,
                    "winner": "A",
                },
            ],
        )
        minimizing = dynamic["minimizing_player_witness"]
        self.assertEqual((minimizing["player"], minimizing["recursive_depth"]),
                         ("B", 2))
        self.assertEqual(
            [row["value_for_a"] for row in minimizing["root_action_values"]],
            [0, -1, 0, 0],
        )
        self.assertEqual(
            minimizing["root_selected_action"],
            {"kind": "MOVE_CAPTURE", "from": [1, 1], "to": [1, 0]},
        )
        self.assertFalse(minimizing["root_unique_best_rng_advanced"])
        self.assertEqual(minimizing["root_expanded_nodes"], 4)
        self.assertEqual(
            [
                row["value_for_a"]
                for row in minimizing["recursive_root_action_values"]
            ],
            [-1, 1, -1],
        )
        self.assertEqual(minimizing["recursive_expanded_nodes"], 11)

    def test_initial_common_ladder_and_lifecycle_are_frozen(self):
        ladder = self.snapshot["ladder_section"]
        production = ladder["production_ladder"]
        strengths = production["ordered_strengths"]
        self.assertEqual(
            [row["identity"] for row in strengths],
            ["random-v1-weak", "terminal_only_minimax-v1-depth1"],
        )
        self.assertNotIn("max_total_nodes_per_slot", strengths[0])
        self.assertEqual(
            strengths[1]["max_total_nodes_per_slot"], 3_456
        )
        self.assertEqual(ATLAS_AGENT_PRODUCTION_DEPTH1_NODE_CAP_V1, 3_456)
        self.assertEqual(production["terminal_depth1_bound_formula"],
                         "8*9*48")
        protocol = ladder["shared_sampled_protocol"]
        self.assertEqual(protocol["ordered_d4_orientations"],
                         list(D4_TRANSFORMS))
        self.assertEqual(protocol["ordered_seeds"], list(range(8)))
        self.assertEqual(protocol["ordered_roles"], ["A", "B"])
        self.assertEqual(
            protocol["fresh_agent_scope"],
            "definition-orientation-strength-role-slot",
        )
        contract = ladder["terminal_only_minimax_contract"]
        self.assertEqual(contract["node_choice_by_player"],
                         {"A": "MAX", "B": "MIN"})
        self.assertEqual(contract["maximum_supported_depth"], 64)
        diagnostic = ladder["diagnostic_conformance"]
        self.assertEqual(diagnostic["benchmark_probe_depths"], [1, 2])
        self.assertEqual(
            diagnostic["depth2_structural_node_bound_per_slot"], 169_344
        )
        self.assertEqual(ATLAS_AGENT_DIAGNOSTIC_DEPTH2_NODE_BOUND_V1,
                         169_344)
        self.assertNotIn(
            "terminal_only_minimax-v1-depth2",
            [row["identity"] for row in strengths],
        )

    def test_random_v1_runs_320_complete_legal_reproducible_games(self):
        section = self.snapshot["evidence"]["random_v1_conformance"]
        games = section["ordered_games"]
        self.assertEqual(section["agent_identity"], "random-v1-weak")
        self.assertEqual(len(games), 320)
        self.assertEqual(len(games),
                         ATLAS_AGENT_BENCHMARK_RANDOM_GAME_COUNT_V1)
        self.assertEqual(section["seeded_replay_count"], 320)
        self.assertEqual(section["seeded_replay_mismatch_count"], 0)
        self.assertEqual(section["illegal_selection_count"], 0)
        self.assertEqual(section["unterminated_game_count"], 0)
        self.assertEqual(section["synthetic_outcome_counts"],
                         {"A_WIN": 40, "B_WIN": 96, "DRAW": 184})
        self.assertEqual(section["terminal_reason_counts"],
                         {"GOAL": 136, "PLY_LIMIT": 184})
        self.assertEqual(Counter(game["seed"] for game in games),
                         {seed: 40 for seed in range(8)})
        self.assertEqual(Counter(game["fixture_id"] for game in games),
                         {fixture_id: 64
                          for fixture_id in EXPECTED_FIXTURES})
        self.assertTrue(all(game["agent_a"] == "random-v1-weak"
                            and game["agent_b"] == "random-v1-weak"
                            for game in games))
        self.assertEqual(section["role_slot_count"], 80)
        self.assertEqual(section["agent_reuse_scope"],
                         "ordered-seeds-0-through-7")
        self.assertEqual(section["reset_policy"],
                         "UNSUPPORTED_STATELESS_AGENT")
        for game in games:
            self.assertEqual(game["plies"], len(game["trace"]))
            self.assertGreaterEqual(game["plies"], 1)
            self.assertIn(game["terminal_reason"],
                          {"GOAL", "PLY_LIMIT"})
            for index, trace in enumerate(game["trace"]):
                self.assertEqual(trace["ply"], index)
                self.assertEqual(trace["actor"], "A" if index % 2 == 0 else "B")
                self.assertGreaterEqual(trace["legal_action_count"], 1)
                self.assertIn(trace["selected_action"]["kind"],
                              {"PUSH", "SWAP", "HOP", "CONVERT",
                               "MOVE_CAPTURE", "MOVE"})

    def test_terminal_only_runs_complete_replayed_cumulative_role_slots(self):
        section = self.snapshot["evidence"][
            "terminal_only_lifecycle_conformance"
        ]
        games = section["ordered_games"]
        slots = section["ordered_role_slots"]
        self.assertEqual(section["agent_identity"],
                         "terminal_only_minimax-v1-depth1")
        self.assertEqual(len(games), 320)
        self.assertEqual(len(games),
                         ATLAS_AGENT_BENCHMARK_TERMINAL_GAME_COUNT_V1)
        self.assertEqual(section["role_slot_count"], 80)
        self.assertEqual(len(slots), 80)
        self.assertEqual(section["seeded_slot_replay_count"], 320)
        self.assertEqual(section["seeded_slot_replay_mismatch_count"], 0)
        self.assertEqual(section["budget_censored_slot_count"], 0)
        self.assertEqual(section["illegal_selection_count"], 0)
        self.assertEqual(section["unterminated_game_count"], 0)
        self.assertEqual(section["synthetic_outcome_counts"],
                         {"A_WIN": 128, "B_WIN": 64, "DRAW": 128})
        self.assertEqual(section["terminal_reason_counts"],
                         {"GOAL": 192, "PLY_LIMIT": 128})
        self.assertEqual(Counter(game["seed"] for game in games),
                         {seed: 40 for seed in range(8)})
        self.assertTrue(all(
            game["agent_a"] == "terminal_only_minimax-v1-depth1"
            and game["agent_b"] == "terminal_only_minimax-v1-depth1"
            and game["plies"] == len(game["trace"])
            and game["plies"] >= 1
            for game in games
        ))
        self.assertEqual(sum(slot["total_expanded_nodes"] for slot in slots),
                         704)
        self.assertEqual(max(slot["total_expanded_nodes"] for slot in slots),
                         24)
        for slot in slots:
            self.assertEqual(slot["ordered_seeds"], list(range(8)))
            self.assertEqual(slot["reset_count"], 1)
            self.assertEqual(slot["completed_game_count"], 8)
            self.assertLessEqual(slot["total_expanded_nodes"],
                                 slot["max_total_nodes"])
            self.assertEqual(slot["max_total_nodes"], 3_456)

    def test_node_budget_censor_reset_and_tie_oracles_are_frozen(self):
        budget = self.snapshot["evidence"]["node_budget_evidence"]
        censored = budget["push_depth1_cap2"]
        self.assertEqual(censored["status"], "NODE_BUDGET_CENSORED")
        self.assertEqual((censored["scope"], censored["visited_nodes"],
                          censored["total_nodes"]), ("per-slot", 2, 2))
        self.assertEqual(
            (censored["last_expanded_nodes"],
             censored["last_cache_hits"],
             censored["last_action_value_count"]),
            (None, None, 0),
        )
        self.assertFalse(censored["rng_advanced"])
        complete = budget["push_depth1_cap3"]
        self.assertEqual((complete["status"], complete["total_nodes"],
                          complete["last_action_value_count"]),
                         ("COMPLETE", 3, 3))
        reconverged = budget["convert_depth1_cap1"]
        self.assertEqual((reconverged["total_nodes"],
                          reconverged["last_cache_hits"]), (1, 1))

        cumulative2 = budget["capture_depth2_cumulative_cap2"]
        self.assertEqual((cumulative2["completed_action_count"],
                          cumulative2["terminal"],
                          cumulative2["total_nodes_before_reset"]),
                         (1, False, 2))
        self.assertEqual(cumulative2["censor"],
                         {"scope": "per-slot", "visited_nodes": 2,
                          "max_total_nodes": 2})
        cumulative3 = budget["capture_depth2_cumulative_cap3"]
        self.assertEqual((cumulative3["completed_action_count"],
                          cumulative3["terminal"],
                          cumulative3["total_nodes_before_reset"]),
                         (2, True, 3))
        for record in (cumulative2, cumulative3):
            self.assertEqual(record["total_nodes_after_reset"], 0)
            self.assertIsNone(record["last_expanded_nodes_after_reset"])
            self.assertIsNone(record["last_cache_hits_after_reset"])
            self.assertEqual(record["last_action_value_count_after_reset"], 0)

        tie = self.snapshot["evidence"]["tie_evidence"]
        self.assertEqual(
            [(row["seed"], row["canonical_best_index"])
             for row in tie["seeded_selections"]],
            [(0, 1), (1, 0)],
        )
        self.assertTrue(tie["seed0_repeat_equal"])
        self.assertTrue(tie["tie_rng_advanced"])
        self.assertFalse(tie["unique_best_rng_advanced"])
        orientation = tie["orientation_sensitivity"]
        self.assertFalse(orientation["selection_is_d4_equivariant"])
        self.assertTrue(orientation["value_for_a_unchanged"])

    def test_atlas_nonintersection_proof_binds_fixed_universe_and_selection(self):
        separation = self.snapshot["atlas_separation"]
        self.assertEqual(separation["proof_kind"],
                         "D4_INVARIANT_FIELD_SEPARATION")
        self.assertEqual(separation["atlas_search_envelope_root"],
                         ATLAS_SEARCH_ENVELOPE_ROOT_V1)
        self.assertEqual(
            separation["atlas_paired_universe_witness_root"],
            ATLAS_PAIRED_UNIVERSE_WITNESS_ROOT_V1,
        )
        self.assertEqual(separation["atlas_selection_partition_root"],
                         ATLAS_SELECTION_PARTITION_ROOT_V1)
        self.assertEqual(separation["atlas_development_definition_count"],
                         ATLAS_DEVELOPMENT_DEFINITION_COUNT_V1)
        self.assertEqual(separation["atlas_candidate_definition_count"],
                         ATLAS_CANDIDATE_DEFINITION_COUNT_V1)
        self.assertEqual(len(separation["fixture_witnesses"]), 5)
        self.assertTrue(all(
            witness["d4_invariant_mismatch_fields"]
            == ["initial_piece_count", "max_plies"]
            and witness["fixture_initial_piece_count"] != 6
            and witness["fixture_max_plies"] != 18
            for witness in separation["fixture_witnesses"]
        ))
        for key in (
            "fixture_exact_collision_count",
            "fixture_d4_collision_count",
            "production_definition_accessed_count",
            "production_outcome_count",
        ):
            self.assertEqual(separation[key], 0)
        self.assertEqual(self.snapshot["evidence"]["production_outcome_count"],
                         0)
        self.assertEqual(self.snapshot["census"]["production_outcome_count"],
                         0)

    def test_builder_solves_only_structurally_separated_synthetic_fixtures(self):
        observed = []
        real_solve = benchmark_module.solve_game

        def recording_solve(definition):
            observed.append((len(definition.initial_pieces),
                             definition.max_plies))
            return real_solve(definition)

        with patch.object(benchmark_module, "solve_game", recording_solve):
            rebuilt = benchmark_module._build_benchmark_snapshot_v1()
        self.assertEqual(rebuilt["benchmark_root"],
                         EXPECTED_ROOTS["benchmark"])
        self.assertEqual(len(observed), 40)
        self.assertTrue(all(piece_count != 6 and max_plies != 18
                            for piece_count, max_plies in observed))

    def test_builder_proves_separation_before_any_evaluation(self):
        class SeparationFailure(RuntimeError):
            pass

        with patch.object(
            benchmark_module,
            "_build_atlas_separation_section",
            side_effect=SeparationFailure("stop before outcomes"),
        ), patch.object(
            benchmark_module, "_build_d4_evidence"
        ) as d4_evidence, patch.object(
            benchmark_module, "_build_random_conformance"
        ) as random_conformance, patch.object(
            benchmark_module, "_build_terminal_lifecycle_conformance"
        ) as terminal_conformance, patch.object(
            benchmark_module, "_build_dynamic_coverage"
        ) as dynamic_coverage, patch.object(
            benchmark_module, "_build_budget_and_tie_evidence"
        ) as budget_and_tie:
            with self.assertRaisesRegex(SeparationFailure,
                                        "stop before outcomes"):
                benchmark_module._build_benchmark_snapshot_v1()
        d4_evidence.assert_not_called()
        random_conformance.assert_not_called()
        terminal_conformance.assert_not_called()
        dynamic_coverage.assert_not_called()
        budget_and_tie.assert_not_called()

    def test_validator_rejects_tamper_unknown_key_and_inner_self_resign(self):
        unknown = copy.deepcopy(self.snapshot)
        unknown["unknown"] = True
        with self.assertRaises(ValueError):
            validate_frozen_atlas_agent_benchmark_v1(unknown)

        resigned = copy.deepcopy(self.snapshot)
        fixture_section = resigned["fixture_section"]
        fixture_section["fixtures"][0]["definition"]["name"] = "forged"
        unsigned_fixture = dict(fixture_section)
        unsigned_fixture.pop("fixture_root")
        fixture_section["fixture_root"] = benchmark_module._digest(
            benchmark_module._FIXTURE_ROOT_DOMAIN_V1, unsigned_fixture
        )
        _resign_benchmark_root(resigned)
        with self.assertRaises(ValueError):
            validate_frozen_atlas_agent_benchmark_v1(resigned)

    def test_validator_rejects_nonexact_cycle_depth_and_node_abuse(self):
        class DictSubclass(dict):
            pass

        for invalid in (
            tuple(),
            {"value": 1.5},
            {"value": float("nan")},
            DictSubclass(self.snapshot),
            {1: "non-string-key"},
        ):
            with self.subTest(invalid_type=type(invalid).__name__):
                with self.assertRaises((TypeError, ValueError)):
                    validate_frozen_atlas_agent_benchmark_v1(invalid)

        cycle = []
        cycle.append(cycle)
        with self.assertRaisesRegex(ValueError, "cycle"):
            validate_frozen_atlas_agent_benchmark_v1(cycle)

        deep = None
        for _ in range(benchmark_module._MAX_VALIDATION_DEPTH_V1 + 1):
            deep = [deep]
        with self.assertRaisesRegex(ValueError, "depth limit"):
            validate_frozen_atlas_agent_benchmark_v1(deep)

        too_many = [None] * benchmark_module._MAX_VALIDATION_NODES_V1
        with self.assertRaisesRegex(ValueError, "node limit"):
            validate_frozen_atlas_agent_benchmark_v1(too_many)

        huge_string = "x" * (
            benchmark_module._MAX_VALIDATION_SINGLE_STRING_CHARACTERS_V1 + 1
        )
        with self.assertRaisesRegex(ValueError, "string limit"):
            validate_frozen_atlas_agent_benchmark_v1(huge_string)

        huge_key = "k" * (
            benchmark_module._MAX_VALIDATION_SINGLE_STRING_CHARACTERS_V1 + 1
        )
        with self.assertRaisesRegex(ValueError, "key limit"):
            validate_frozen_atlas_agent_benchmark_v1({huge_key: None})

        huge_integer = 1 << benchmark_module._MAX_VALIDATION_INTEGER_BITS_V1
        with self.assertRaisesRegex(ValueError, "integer bit limit"):
            validate_frozen_atlas_agent_benchmark_v1(huge_integer)

        with patch.object(
            benchmark_module,
            "_MAX_VALIDATION_CANONICAL_BYTES_V1",
            1,
        ):
            with self.assertRaisesRegex(ValueError, "canonical byte limit"):
                validate_frozen_atlas_agent_benchmark_v1(self.snapshot)

    def test_validator_detects_mutation_between_initial_and_final_seal(self):
        candidate = copy.deepcopy(self.snapshot)
        real_seal = benchmark_module._seal_json_input
        call_count = 0

        def mutate_after_first_seal(value, label):
            nonlocal call_count
            call_count += 1
            sealed = real_seal(value, label)
            if call_count == 1:
                value["status"] = "MUTATED_AFTER_INITIAL_SEAL"
            return sealed

        with patch.object(
            benchmark_module, "_seal_json_input", mutate_after_first_seal
        ):
            with self.assertRaisesRegex(ValueError, "changed during validation"):
                validate_frozen_atlas_agent_benchmark_v1(candidate)

    def test_returns_are_detached_and_canonical_helper_validates_input(self):
        first = build_frozen_atlas_agent_benchmark_v1()
        first["fixture_section"]["fixtures"][0]["definition"]["name"] = "x"
        second = build_frozen_atlas_agent_benchmark_v1()
        self.assertEqual(second, self.snapshot)
        validated = validate_frozen_atlas_agent_benchmark_v1(second)
        self.assertIsNot(validated, second)
        validated["census"]["fixture_count"] = 999
        self.assertEqual(second["census"]["fixture_count"], 5)
        self.assertEqual(canonical_frozen_atlas_agent_benchmark_json_v1(second),
                         canonical_frozen_atlas_agent_benchmark_json_v1())

    def test_source_is_python39_has_no_duplicate_dict_keys_or_forbidden_imports(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(MODULE_PATH), feature_version=(3, 9))
        duplicate_sites = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            literal_keys = [
                key.value
                for key in node.keys
                if isinstance(key, ast.Constant)
                and isinstance(key.value, str)
            ]
            duplicates = sorted(
                key for key, count in Counter(literal_keys).items()
                if count > 1
            )
            if duplicates:
                duplicate_sites.append((node.lineno, duplicates))
        self.assertEqual(duplicate_sites, [])

        imported_modules = set()
        atlas_imported_names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported_modules.add(node.module or "")
                if node.module == "atlas":
                    atlas_imported_names.extend(alias.name for alias in node.names)
        self.assertFalse(any(
            module == "tests" or module.startswith("tests.")
            or module == "play" or module.endswith(".play")
            or module == "experiments" or module.startswith("experiments.")
            for module in imported_modules
        ))
        self.assertTrue(atlas_imported_names)
        self.assertTrue(all(name.startswith("ATLAS_")
                            for name in atlas_imported_names))
        self.assertNotIn("if expected and", source)
        self.assertNotIn("current_path +", source)


if __name__ == "__main__":
    unittest.main()
