"""Synthetic 3x3 SWAP/PUSH wires and mocks only; never run the fixed wire."""

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from parity_forge.dsl import canonical_json, definition_hash, parse_definition
from scripts import plan0027_screen as screen
from scripts.plan0016_pilot import read_json
from tests.test_plan0021_pilot import fake_exact


def tiny():
    raw = {
        "schema_version": 4,
        "name": "plan0027 synthetic swap-push race",
        "board_size": 3,
        "first_player": "A",
        "max_plies": 7,
        "roles": {
            "A": {
                "action": {
                    "kind": "SWAP",
                    "piece": "a",
                    "vectors": [[0, 1], [1, 0]],
                },
                "goal": {
                    "kind": "REACH_EDGE",
                    "piece": "a",
                    "edge": "BOTTOM",
                },
            },
            "B": {
                "action": {
                    "kind": "PUSH",
                    "piece": "b",
                    "vectors": [[-1, 0], [0, -1]],
                },
                "goal": {
                    "kind": "REACH_EDGE",
                    "piece": "b",
                    "edge": "TOP",
                },
            },
        },
        "initial_pieces": [
            {"owner": "A", "piece": "a", "position": [0, 0]},
            {"owner": "B", "piece": "b", "position": [2, 2]},
        ],
    }
    return json.loads(canonical_json(parse_definition(raw)))


def game(raw, policy_a, policy_b, seed, cap):
    """A fully mocked decisive result with valid T4 audit witnesses."""

    if policy_a == "T4" and policy_b in ("T2", "R"):
        winner = "A"
    elif policy_b == "T4" and policy_a in ("T2", "R"):
        winner = "B"
    else:
        winner = "A" if seed % 2 else "B"
    actions = [
        {"kind": "SWAP", "from": [0, 0], "to": [0, 1]},
        {"kind": "PUSH", "from": [2, 2], "to": [2, 1]},
        {"kind": "SWAP", "from": [0, 2], "to": [1, 2]},
        {"kind": "PUSH", "from": [2, 0], "to": [1, 0]},
    ]
    decisions = []
    for ply, action in enumerate(actions):
        actor = "AB"[ply % 2]
        policy = policy_a if actor == "A" else policy_b
        opponent = "B" if actor == "A" else "A"
        decision = {
            "ply": ply,
            "actor": actor,
            "input_state": {
                "ply": ply,
                "to_move": actor,
                "pieces": [
                    {
                        "owner": actor,
                        "piece": actor.lower(),
                        "position": list(action["from"]),
                    },
                    {
                        "owner": opponent,
                        "piece": opponent.lower(),
                        "position": list(action["to"]),
                    },
                ],
                "outcome": None,
            },
            "selection_status": "SELECTED",
            "selected_action": copy.deepcopy(action),
            "legal_action_count": 2,
        }
        if policy.startswith("T"):
            values = (0, 0) if ply == 0 else (-1, 1)
            decision["last_action_values"] = [
                {"value": value} for value in values
            ]
        decisions.append(decision)
    return {
        "status": "COMPLETE",
        "definition_hash": definition_hash(parse_definition(raw)),
        "first_player": "A",
        "policy_a": policy_a,
        "policy_b": policy_b,
        "seed": seed,
        "max_nodes_per_role": cap,
        "winner": winner,
        "plies": 4,
        "actions": actions,
        "terminal_reason": "GOAL",
        "replay_count": 1,
        "replay_verified": True,
        "nodes_by_role": {
            "A": int(policy_a != "R"),
            "B": int(policy_b != "R"),
        },
        "node_accounting": {
            "A": (
                "UNMETERED_RANDOM_SELECTION_NOT_ZERO_COMPUTE"
                if policy_a == "R"
                else "SEARCH_CACHE_MISSES"
            ),
            "B": (
                "UNMETERED_RANDOM_SELECTION_NOT_ZERO_COMPUTE"
                if policy_b == "R"
                else "SEARCH_CACHE_MISSES"
            ),
        },
        "decisions": decisions,
        "censor": None,
    }


def exact_complete(raw, cap, value=1, plies=2, reason="GOAL"):
    return {
        "status": "COMPLETE",
        "definition_hash": definition_hash(parse_definition(raw)),
        "max_states": cap,
        "replay_count": 1,
        "actual_result": {
            "value_for_a": value,
            "principal_variation_plies": plies,
            "terminal_reason": reason,
        },
    }


def censor(raw, policy_a, policy_b, seed, cap, role="A"):
    result = game(raw, policy_a, policy_b, seed, cap)
    result.update(
        status="UNKNOWN_CENSORED",
        winner=None,
        terminal_reason=None,
        plies=0,
        actions=[],
        decisions=[],
        censor={
            "role": role,
            "scope": "game",
            "visited_nodes": cap,
            "max_nodes": cap,
        },
    )
    result["nodes_by_role"][role] = cap
    return result


def set_effect(result, actor, present):
    """Set whether one actor has any occupied-destination action in a mock."""

    opponent = "B" if actor == "A" else "A"
    actor_decisions = [
        decision for decision in result["decisions"]
        if decision["actor"] == actor
    ]
    for decision in actor_decisions:
        target = decision["selected_action"]["to"]
        decision["input_state"]["pieces"] = [
            piece for piece in decision["input_state"]["pieces"]
            if piece["position"] != target
        ]
    if present:
        decision = actor_decisions[0]
        decision["input_state"]["pieces"].append(
            {
                "owner": opponent,
                "piece": opponent.lower(),
                "position": list(decision["selected_action"]["to"]),
            }
        )


def set_first_action_horizontal(result, actor, horizontal):
    """Change an actor's first mock action while keeping selected/applied equal."""

    decision = next(
        decision for decision in result["decisions"]
        if decision["actor"] == actor
    )
    action = decision["selected_action"]
    old_target = list(action["to"])
    if actor == "A":
        new_target = [0, 1] if horizontal else [1, 0]
    else:
        new_target = [2, 1] if horizontal else [1, 2]
    action["to"] = new_target
    result["actions"][decision["ply"]] = copy.deepcopy(action)
    for piece in decision["input_state"]["pieces"]:
        if piece["position"] == old_target:
            piece["position"] = list(new_target)


class ScreenTests(unittest.TestCase):
    def run_mocked(self, repository, play=game, exact=fake_exact, snapshot=None):
        source = {"git_commit": "a" * 40, "sha256": {"synthetic.py": "pinned"}}
        with mock.patch.object(
            screen, "HASH", definition_hash(parse_definition(tiny()))
        ), mock.patch.object(
            screen,
            "source_snapshot",
            side_effect=snapshot or (lambda *args, **kwargs: source),
        ), mock.patch.object(
            screen, "load_definition", return_value=tiny()
        ), mock.patch.object(
            screen.play_adapter, "play_one", side_effect=play
        ) as games, mock.patch.object(
            screen, "exact_one", side_effect=exact
        ) as solves:
            result = screen.run_pilot(repository, "a" * 40)
        return result, games.call_count, solves.call_count

    def records_with_counts(self, counts):
        records = []
        for item in screen.schedule():
            if item["kind"] == "exact":
                result = {
                    "status": "UNKNOWN_CENSORED",
                    "definition_hash": item["definition_hash"],
                }
            else:
                result = game(
                    tiny(),
                    item["policy_a"],
                    item["policy_b"],
                    item["seed"],
                    item["max_nodes_per_role"],
                )
                offset = item["seed"] - screen.CELLS[item["cell"]][3]
                result["winner"] = "A" if offset < counts[item["cell"]] else "B"
            records.append(
                {"scheduled": item, "status": result["status"], "result": result}
            )
        return records

    def test_schedule_is_exactly_prospective_and_saved_before_first_call(self):
        planned = screen.schedule()
        self.assertEqual(
            (
                screen.PLAN,
                screen.DATA,
                screen.PROTOCOL,
                screen.HASH,
                screen.EXPOSURE,
                screen.PROPOSAL_STATUS,
            ),
            (
                "docs/plans/active/0027-three-currents-swap-push-screen.md",
                (
                    "experiments/proposals/"
                    "three-currents-swap-push-v0.json"
                ),
                "plan0027-three-currents-swap-push-v1",
                "aa3079277a9089aa8758fa04f0d81be09544af39ba9338524cf97e6f98490209",
                (
                    "SOURCE_DESIGNED_AFTER_PLAN0024_0026_PUBLIC_TRACE_DIAGNOSIS_AND_"
                    "PREREGISTRATION_GOAL_EFFECT_AND_SHADOW_COUNTERLINES_AND_TWO_BOUNDED_"
                    "AND_OR_TRAVERSALS_EXPOSED_NOT_CONFIRMATION"
                ),
                "FIXED_PROSPECTIVE_NOT_REGISTERED_NOT_PRODUCTION_EXECUTED",
            ),
        )
        self.assertEqual((len(planned), screen.PLANNED_GAMES), (81, 80))
        self.assertEqual(planned[0]["kind"], "exact")
        self.assertEqual([item["stage"] for item in planned[1:33]], ["base"] * 32)
        self.assertEqual(
            [item["stage"] for item in planned[33:]],
            ["confirm"] * 16
            + ["sensitivity"] * 16
            + ["simple"] * 16,
        )
        self.assertEqual(
            [(item["policy_a"], item["policy_b"]) for item in planned[1:]],
            [("T4", "T4")] * 16
            + [("T3", "T3")] * 16
            + [("T4", "T4")] * 16
            + [("T4", "T2")] * 8
            + [("T2", "T4")] * 8
            + [("T4", "R")] * 8
            + [("R", "T4")] * 8,
        )
        self.assertEqual(
            [item["seed"] for item in planned[1:]],
            list(range(900, 916)) * 2
            + list(range(1000, 1016))
            + list(range(1000, 1008)) * 4,
        )
        self.assertEqual(len({json.dumps(item, sort_keys=True) for item in planned}), 81)

        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)

            def exact_after_manifest(raw, cap):
                manifest = read_json(
                    repository / "experiments/runs" / screen.PROTOCOL / "manifest.json"
                )
                self.assertEqual(manifest["schedule"], screen.schedule())
                self.assertEqual(manifest["exposure"], screen.EXPOSURE)
                self.assertEqual(
                    manifest["certificate"],
                    {
                        "definition_hash": screen.HASH,
                        "max_natural_plies": 54,
                        "configured_max_plies": 55,
                        "ply_limit_unreachable": True,
                        "proof": (
                            "weighted potential Phi starts 54; A empty/SWAP "
                            "decreases it 1/3 and B empty/PUSH decreases it 2/1, "
                            "so every legal play ends by 54"
                        ),
                    },
                )
                return exact_complete(raw, cap)

            result, games, solves = self.run_mocked(repository, exact=exact_after_manifest)
            self.assertEqual((games, solves), (0, 1))
            self.assertEqual(result["disposition"], "TOO_EASILY_SOLVED")

    def test_full_positive_run_readback_statuses_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            result, games, solves = self.run_mocked(repository)
            self.assertEqual((games, solves, result["attempted"]), (80, 1, 81))
            self.assertEqual((result["not_started"], len(result["cells"])), (0, 7))
            self.assertEqual(result["disposition"], "HUMAN_REVIEW_ELIGIBLE")
            self.assertEqual(result["statuses"], {"UNKNOWN_CENSORED": 1, "COMPLETE": 80})
            self.assertEqual(result["cells"][0]["charged_nodes_by_role"], {"A": 16, "B": 16})
            self.assertTrue(all(cell["a_wilson95_descriptive"] for cell in result["cells"]))
            self.assertGreaterEqual(result["tactical_choice_witness_games"]["A"], 2)
            self.assertGreaterEqual(result["tactical_choice_witness_games"]["B"], 2)
            self.assertEqual(result["realized_effect_games"], {"A": 80, "B": 80})
            self.assertEqual(
                result["t4_horizontal_selection_games"], {"A": 48, "B": 48}
            )
            self.assertFalse(result["realized_effect_is_depth_proof"])
            self.assertFalse(result["horizontal_selection_is_depth_proof"])
            self.assertFalse(
                any(
                    result[name + "_established"]
                    for name in ("fairness", "hardness", "fun")
                )
            )
            output = repository / "experiments/runs" / screen.PROTOCOL
            self.assertEqual(read_json(output / "summary.json"), result)
            verification = read_json(output / "source-verification.json")
            self.assertTrue(verification["matched"])
            self.assertEqual(len(verification["publication_sha256"]), 164)
            for name, digest in verification["publication_sha256"].items():
                self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), digest)
            with self.assertRaises(FileExistsError):
                self.run_mocked(repository)

    def test_exact_short_and_base_cascade_gates(self):
        cases = (
            ("exact", "TOO_EASILY_SOLVED", 0),
            ("short_loss", "SHORT_FORCED_RESULT", 1),
            ("short_win", "SHORT_FORCED_RESULT", 1),
            ("base_t4_low", "NO_FLAG", 32),
            ("base_t4_high", "NO_FLAG", 32),
            ("base_t3_low", "NO_FLAG", 32),
            ("base_t3_high", "NO_FLAG", 32),
            ("base_censor", "INSUFFICIENT_EVIDENCE", 32),
        )
        for mode, disposition, expected_games in cases:
            def solve(raw, cap):
                return exact_complete(raw, cap) if mode == "exact" else fake_exact(raw, cap)

            def play(raw, policy_a, policy_b, seed, cap):
                result = game(raw, policy_a, policy_b, seed, cap)
                if mode == "short_loss" and policy_a == policy_b == "T4" and seed == 900:
                    result["decisions"][0]["last_action_values"] = [
                        {"value": -1}, {"value": -1}
                    ]
                elif mode == "short_win" and policy_a == policy_b == "T4" and seed == 900:
                    result["decisions"][0]["last_action_values"] = [
                        {"value": 0}, {"value": 1}
                    ]
                elif mode == "base_t4_low" and policy_a == policy_b == "T4":
                    result["winner"] = "A" if seed < 904 else "B"
                elif mode == "base_t4_high" and policy_a == policy_b == "T4":
                    result["winner"] = "A" if seed < 912 else "B"
                elif mode == "base_t3_low" and policy_a == policy_b == "T3":
                    result["winner"] = "A" if seed < 903 else "B"
                elif mode == "base_t3_high" and policy_a == policy_b == "T3":
                    result["winner"] = "A" if seed < 913 else "B"
                elif mode == "base_censor" and policy_a == policy_b == "T4" and seed == 900:
                    result = censor(raw, policy_a, policy_b, seed, cap)
                return result

            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temporary:
                result, games, solves = self.run_mocked(Path(temporary), play, solve)
                self.assertEqual(
                    (result["execution_status"], result["disposition"], games, solves),
                    ("COMPLETE", disposition, expected_games, 1),
                )
                self.assertEqual(result["not_started_gate_closed"], 80 - expected_games)
                self.assertEqual(
                    sum(cell["not_started"] for cell in result["cells"]),
                    80 - expected_games,
                )

    def test_opened_final_block_runs_all_games_even_if_censored(self):
        def play(raw, policy_a, policy_b, seed, cap):
            if (policy_a, policy_b, seed) == ("R", "T4", 1000):
                return censor(raw, policy_a, policy_b, seed, cap, role="B")
            return game(raw, policy_a, policy_b, seed, cap)

        with tempfile.TemporaryDirectory() as temporary:
            result, games, _ = self.run_mocked(Path(temporary), play=play)
            self.assertEqual((games, result["attempted"], result["not_started"]), (80, 81, 0))
            self.assertEqual(result["disposition"], "INSUFFICIENT_EVIDENCE")
            self.assertEqual(result["cells"][6]["censored"], 1)

    def test_every_human_threshold_edge_is_separate(self):
        passing = [8, 8, 8, 6, 2, 7, 1]
        self.assertEqual(
            screen.summarize(self.records_with_counts(passing))["disposition"],
            "HUMAN_REVIEW_ELIGIBLE",
        )
        pass_edges = (
            (0, 5), (0, 11), (1, 4), (1, 12), (2, 5), (2, 11),
            (3, 6), (4, 2), (5, 7), (6, 1),
        )
        fail_edges = (
            (0, 4), (0, 12), (1, 3), (1, 13), (2, 4), (2, 12),
            (3, 5), (4, 3), (5, 6), (6, 2),
        )
        for cell, wins in pass_edges:
            counts = list(passing)
            counts[cell] = wins
            with self.subTest(kind="pass", cell=cell, wins=wins):
                self.assertEqual(
                    screen.summarize(self.records_with_counts(counts))["disposition"],
                    "HUMAN_REVIEW_ELIGIBLE",
                )
        for cell, wins in fail_edges:
            counts = list(passing)
            counts[cell] = wins
            with self.subTest(kind="fail", cell=cell, wins=wins):
                self.assertEqual(
                    screen.summarize(self.records_with_counts(counts))["disposition"],
                    "NO_FLAG",
                )

    def test_tactical_witness_threshold_counts_distinct_games(self):
        records = self.records_with_counts([8, 8, 8, 6, 2, 7, 1])
        for record in records:
            if record["scheduled"]["kind"] != "game":
                continue
            for decision in record["result"]["decisions"]:
                if decision["actor"] == "A" and record["scheduled"]["policy_a"] == "T4":
                    decision["last_action_values"] = [{"value": 0}, {"value": 0}]
        first = next(
            record for record in records
            if record["scheduled"].get("policy_a") == "T4"
        )
        first["result"]["decisions"][2]["last_action_values"] = [
            {"value": -1}, {"value": 1}
        ]
        self.assertEqual(screen.summarize(records)["disposition"], "NO_FLAG")
        second = next(
            record for record in records
            if record is not first and record["scheduled"].get("policy_a") == "T4"
        )
        second["result"]["decisions"][2]["last_action_values"] = [
            {"value": -1}, {"value": 1}
        ]
        self.assertEqual(
            screen.summarize(records)["disposition"], "HUMAN_REVIEW_ELIGIBLE"
        )

    def test_interaction_gates_require_two_distinct_complete_games(self):
        passing = [8, 8, 8, 6, 2, 7, 1]
        for category, actor in (
            ("effect", "A"),
            ("effect", "B"),
            ("horizontal", "A"),
            ("horizontal", "B"),
        ):
            records = self.records_with_counts(passing)
            games = [
                record for record in records
                if record["scheduled"]["kind"] == "game"
            ]
            if category == "effect":
                for record in games:
                    set_effect(record["result"], actor, False)
                eligible = games
                field = "realized_effect_games"
                setter = lambda record, value: set_effect(
                    record["result"], actor, value
                )
            else:
                for record in games:
                    set_first_action_horizontal(record["result"], actor, False)
                eligible = [
                    record for record in games
                    if record["scheduled"]["policy_" + actor.lower()] == "T4"
                ]
                field = "t4_horizontal_selection_games"
                setter = lambda record, value: set_first_action_horizontal(
                    record["result"], actor, value
                )

            setter(eligible[0], True)
            with self.subTest(category=category, actor=actor, games=1):
                summary = screen.summarize(records)
                self.assertEqual(summary[field][actor], 1)
                self.assertEqual(summary["disposition"], "NO_FLAG")
            setter(eligible[1], True)
            with self.subTest(category=category, actor=actor, games=2):
                summary = screen.summarize(records)
                self.assertEqual(summary[field][actor], 2)
                self.assertEqual(
                    summary["disposition"], "HUMAN_REVIEW_ELIGIBLE"
                )

        records = self.records_with_counts(passing)
        first_game = next(
            record for record in records
            if record["scheduled"]["kind"] == "game"
        )
        first_game["status"] = "UNKNOWN_CENSORED"
        item = first_game["scheduled"]
        first_game["result"] = censor(
            tiny(),
            item["policy_a"],
            item["policy_b"],
            item["seed"],
            item["max_nodes_per_role"],
        )
        first_game["result"]["definition_hash"] = item["definition_hash"]
        screen.validate_result(item, first_game["result"])
        summary = screen.summarize(records)
        self.assertEqual(summary["realized_effect_games"], {"A": 79, "B": 79})
        self.assertEqual(
            summary["t4_horizontal_selection_games"], {"A": 47, "B": 47}
        )

    def test_candidate_evidence_is_occupied_destination_not_action_kind(self):
        raw = tiny()
        item = {
            "kind": "game",
            "first_player": "A",
            "definition_hash": definition_hash(parse_definition(raw)),
            "policy_a": "T4",
            "policy_b": "R",
            "seed": 1,
            "max_nodes_per_role": screen.MAX_NODES,
        }
        result = game(raw, "T4", "R", 1, screen.MAX_NODES)
        evidence = screen.game_evidence(item, result)
        self.assertEqual(evidence["realized_effect"], {"A": True, "B": True})
        self.assertEqual(
            evidence["t4_horizontal_selection"], {"A": True, "B": False}
        )

        set_effect(result, "A", False)
        evidence = screen.game_evidence(item, result)
        self.assertFalse(evidence["realized_effect"]["A"])
        self.assertTrue(evidence["t4_horizontal_selection"]["A"])
        set_effect(result, "A", True)
        set_first_action_horizontal(result, "A", False)
        evidence = screen.game_evidence(item, result)
        self.assertTrue(evidence["realized_effect"]["A"])
        self.assertFalse(evidence["t4_horizontal_selection"]["A"])

    def test_candidate_evidence_malformed_records_fail_closed(self):
        raw = tiny()
        item = {
            "kind": "game",
            "first_player": "A",
            "definition_hash": definition_hash(parse_definition(raw)),
            "policy_a": "T4",
            "policy_b": "T4",
            "seed": 1,
            "max_nodes_per_role": screen.MAX_NODES,
        }
        valid = game(raw, "T4", "T4", 1, screen.MAX_NODES)
        screen.validate_result(item, valid)

        def wrong_selected(result):
            result["decisions"][0]["selected_action"]["to"] = [1, 0]

        def wrong_kind(result):
            result["actions"][0]["kind"] = "PUSH"
            result["decisions"][0]["selected_action"]["kind"] = "PUSH"

        def missing_origin(result):
            result["decisions"][0]["input_state"]["pieces"] = []

        def friendly_target(result):
            piece = result["decisions"][0]["input_state"]["pieces"][1]
            piece.update(owner="A", piece="a")

        def duplicate_position(result):
            state = result["decisions"][0]["input_state"]
            state["pieces"].append(copy.deepcopy(state["pieces"][0]))

        for mutate in (
            lambda result: result["decisions"].pop(),
            lambda result: result["decisions"][0].update(
                selection_status="STARTED"
            ),
            wrong_selected,
            lambda result: result["decisions"][0]["input_state"].update(ply=1),
            wrong_kind,
            lambda result: result["actions"][0].update(to=[1, 1]),
            missing_origin,
            friendly_target,
            duplicate_position,
        ):
            result = copy.deepcopy(valid)
            mutate(result)
            with self.assertRaises(ValueError):
                screen.validate_result(item, result)

    def test_result_validation_exact_censor_node_and_replay_edges(self):
        raw = tiny()
        game_item = {
            "kind": "game",
            "first_player": "A",
            "definition_hash": definition_hash(parse_definition(raw)),
            "policy_a": "R",
            "policy_b": "T4",
            "seed": 1,
            "max_nodes_per_role": screen.MAX_NODES,
        }
        valid = game(raw, "R", "T4", 1, screen.MAX_NODES)
        screen.validate_result(game_item, valid)
        for mutate in (
            lambda result: result["nodes_by_role"].update(A=1),
            lambda result: result["node_accounting"].update(A="ZERO_COMPUTE"),
            lambda result: result["nodes_by_role"].update(B=screen.MAX_NODES + 1),
            lambda result: result.update(replay_count=2),
            lambda result: result.update(winner=None),
            lambda result: result.update(
                plies=screen.BOUND + 1,
                actions=[{}] * (screen.BOUND + 1),
            ),
            lambda result: result.update(terminal_reason="PLY_LIMIT"),
        ):
            result = copy.deepcopy(valid)
            mutate(result)
            with self.assertRaises(ValueError):
                screen.validate_result(game_item, result)

        censored = censor(raw, "R", "T4", 1, screen.MAX_NODES, role="B")
        screen.validate_result(game_item, censored)
        censored["plies"] = screen.BOUND
        censored["actions"] = [{}] * screen.BOUND
        with self.assertRaises(ValueError):
            screen.validate_result(game_item, censored)

        exact_item = {
            "kind": "exact",
            "definition_hash": definition_hash(parse_definition(raw)),
            "max_states": screen.MAX_STATES,
        }
        screen.validate_result(exact_item, fake_exact(raw, screen.MAX_STATES))
        for result in (
            exact_complete(raw, screen.MAX_STATES, value=0),
            exact_complete(raw, screen.MAX_STATES, plies=screen.BOUND + 1),
            exact_complete(raw, screen.MAX_STATES, reason="PLY_LIMIT"),
        ):
            with self.assertRaises(ValueError):
                screen.validate_result(exact_item, result)
        bad_unknown = fake_exact(raw, screen.MAX_STATES)
        bad_unknown["error"]["searched_states"] -= 1
        with self.assertRaises(ValueError):
            screen.validate_result(exact_item, bad_unknown)

    def test_started_failures_stop_and_account_for_every_remaining_attempt(self):
        for mode in ("exception", "draw", "bound", "replay", "source", "publication"):
            calls = []
            snapshots = []
            original_publish = screen._publish

            def play(raw, policy_a, policy_b, seed, cap):
                calls.append(1)
                if mode == "exception":
                    raise RuntimeError("synthetic failure")
                result = game(raw, policy_a, policy_b, seed, cap)
                if mode == "draw":
                    result.update(winner=None, terminal_reason="PLY_LIMIT")
                elif mode == "bound":
                    result.update(
                        plies=screen.BOUND + 1,
                        actions=[{}] * (screen.BOUND + 1),
                    )
                elif mode == "replay":
                    result["replay_count"] = 2
                return result

            def snapshot(*args, **kwargs):
                snapshots.append(1)
                changed = mode == "source" and calls
                return {
                    "git_commit": "a" * 40,
                    "sha256": {"synthetic.py": "changed" if changed else "pinned"},
                }

            def publish(path, value):
                if mode == "publication" and path.name == "0001-result.json":
                    raise OSError("synthetic disk failure")
                original_publish(path, value)

            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temporary, mock.patch.object(
                screen, "_publish", side_effect=publish
            ):
                repository = Path(temporary)
                result, games, solves = self.run_mocked(
                    repository, play=play, snapshot=snapshot
                )
                self.assertEqual((games, solves, result["execution_status"]), (1, 1, "FAILED"))
                self.assertEqual(
                    (result["attempted"], result["statuses"]["FAILED"], result["not_started_failure"]),
                    (2, 1, 79),
                )
                self.assertEqual(result["not_started_gate_closed"], 0)
                failure = read_json(
                    repository / "experiments/runs" / screen.PROTOCOL / "failure.json"
                )
                self.assertIsNotNone(failure["current"])
                if mode == "publication":
                    self.assertEqual(failure["current"]["result"]["plies"], 4)

    def test_artifact_and_final_summary_publication_failures_cannot_promote(self):
        for mode in ("artifact", "summary"):
            original_publish = screen._publish

            def publish(path, value):
                if mode == "summary" and path.name == "summary.json":
                    raise OSError("synthetic finalization failure")
                original_publish(path, value)
                if mode == "artifact" and path.name == "0001-result.json":
                    (path.parent / "manifest.json").write_text("changed")

            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temporary, mock.patch.object(
                screen, "_publish", side_effect=publish
            ):
                repository = Path(temporary)
                result, games, _ = self.run_mocked(repository)
                self.assertEqual((games, result["execution_status"], result["disposition"]), (80, "FAILED", "FAILED"))
                name = (
                    "summary-publication-failure.json"
                    if mode == "summary"
                    else "summary.json"
                )
                self.assertEqual(
                    read_json(repository / "experiments/runs" / screen.PROTOCOL / name),
                    result,
                )

    def test_real_git_pins_and_fixed_wire_load_use_synthetic_3x3_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            raw = copy.deepcopy(tiny())
            raw["max_plies"] = screen.PLY_LIMIT
            raw = json.loads(canonical_json(parse_definition(raw)))
            files = (
                (screen.PLAN, "synthetic plan"),
                (
                    screen.DATA,
                    json.dumps(
                        {
                            "status": screen.PROPOSAL_STATUS,
                            "exposure": screen.EXPOSURE,
                            "definitions": [raw],
                        }
                    ),
                ),
                ("source.py", "# synthetic"),
            )
            for name, contents in files:
                path = repository / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(contents)

            def git(*args):
                return subprocess.check_output(
                    ("git", "-C", temporary, *args), text=True
                ).strip()

            git("init", "-q")
            git("add", ".")
            git(
                "-c", "user.name=Test",
                "-c", "user.email=test@example.invalid",
                "-c", "commit.gpgsign=false",
                "-c", "core.hooksPath=/dev/null",
                "commit", "-qm", "synthetic",
            )
            pins = screen.source_snapshot(repository, clean=True)
            self.assertEqual(set(pins["sha256"]), {screen.PLAN, screen.DATA, "source.py"})
            self.assertRegex(pins["git_commit"], r"^[0-9a-f]{40}$")
            data_path = repository / screen.DATA
            original_data = data_path.read_text()
            with mock.patch.object(screen, "HASH", definition_hash(parse_definition(raw))):
                self.assertEqual(screen.load_definition(repository), raw)
                payload = json.loads(original_data)
                payload["exposure"] = "wrong"
                data_path.write_text(json.dumps(payload))
                with self.assertRaises(ValueError):
                    screen.load_definition(repository)
                data_path.write_text(original_data)
            with self.assertRaises(ValueError):
                screen.load_definition(repository)
            (repository / "source.py").write_text("# changed")
            self.assertNotEqual(screen.source_snapshot(repository), pins)
            with self.assertRaises(ValueError):
                screen.source_snapshot(repository, clean=True)
            (repository / "extra.py").write_text("# untracked")
            with self.assertRaises(ValueError):
                screen.source_snapshot(repository)


if __name__ == "__main__":
    unittest.main()
