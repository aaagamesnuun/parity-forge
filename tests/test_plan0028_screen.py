"""Synthetic 3x3 HOP/PUSH traces and mocks only; never run the fixed wire."""

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from parity_forge.dsl import canonical_json, definition_hash, parse_definition
from parity_forge.engine import action_from_dict, apply_action, initial_state, legal_actions
from scripts import plan0028_screen as screen
from scripts.plan0016_pilot import read_json
from tests.test_plan0021_pilot import fake_exact


def tiny():
    raw = {
        "schema_version": 4,
        "name": "plan0028 synthetic hop-push weave",
        "board_size": 3,
        "first_player": "A",
        "max_plies": 13,
        "roles": {
            "A": {
                "action": {
                    "kind": "HOP",
                    "piece": "a",
                    "vectors": [[0, 1], [1, 1]],
                },
                "goal": {
                    "kind": "CONNECT_EDGES",
                    "piece": "a",
                    "edges": ["TOP", "BOTTOM"],
                },
            },
            "B": {
                "action": {
                    "kind": "PUSH",
                    "piece": "b",
                    "vectors": [[-1, -1], [-1, 0]],
                },
                "goal": {
                    "kind": "CONNECT_EDGES",
                    "piece": "b",
                    "edges": ["LEFT", "RIGHT"],
                },
            },
        },
        "initial_pieces": [
            {"owner": "A", "piece": "a", "position": [0, 0]},
            {"owner": "A", "piece": "a", "position": [0, 1]},
            {"owner": "A", "piece": "a", "position": [1, 0]},
            {"owner": "B", "piece": "b", "position": [1, 1]},
            {"owner": "B", "piece": "b", "position": [2, 0]},
            {"owner": "B", "piece": "b", "position": [2, 2]},
        ],
    }
    return json.loads(canonical_json(parse_definition(raw)))


def _decision(state, legal, selected, policy, before):
    actor = state.to_move.value
    charged = int(policy != "G")
    decision = {
        "ply": state.ply,
        "actor": actor,
        "input_state": state.to_dict(),
        "legal_action_count": len(legal),
        "legal_actions": copy.deepcopy(legal),
        "selected_action": copy.deepcopy(selected),
        "nodes_before": before,
        "nodes_after": before + charged,
        "charged_nodes": charged,
        "selection_status": "SELECTED",
    }
    if policy.startswith("T"):
        decision["last_action_values"] = [
            {"action": copy.deepcopy(action), "value": 0} for action in legal
        ]
    return decision


PATHS = {
    ("A", "GOAL", False, False): (
        ("HOP", (0, 1), (0, 2)),
        ("PUSH", (1, 1), (0, 1)),
        ("HOP", (1, 0), (2, 1)),
        ("PUSH", (2, 0), (1, 0)),
        ("HOP", (0, 0), (1, 1)),
        ("PUSH", (1, 0), (0, 0)),
        ("HOP", (1, 1), (1, 2)),
        ("PUSH", (2, 2), (1, 1)),
        ("HOP", (2, 1), (2, 2)),
    ),
    ("A", "GOAL", True, False): (
        ("HOP", (0, 1), (0, 2)),
        ("PUSH", (2, 2), (1, 2)),
        ("HOP", (0, 0), (2, 2)),
        ("PUSH", (1, 2), (0, 1)),
        ("HOP", (1, 0), (1, 2)),
    ),
    ("A", "GOAL", True, True): (
        ("HOP", (0, 1), (1, 2)),
        ("PUSH", (2, 2), (1, 2)),
        ("HOP", (0, 0), (2, 2)),
        ("PUSH", (1, 2), (0, 1)),
        ("HOP", (1, 0), (1, 2)),
    ),
    ("B", "GOAL", False, True): (
        ("HOP", (0, 1), (0, 2)),
        ("PUSH", (2, 2), (1, 2)),
        ("HOP", (0, 0), (0, 1)),
        ("PUSH", (2, 0), (1, 0)),
    ),
    ("B", "GOAL", True, False): (
        ("HOP", (0, 0), (0, 2)),
        ("PUSH", (2, 2), (1, 2)),
        ("HOP", (1, 0), (2, 1)),
        ("PUSH", (2, 0), (1, 0)),
    ),
    ("B", "GOAL", True, True): (
        ("HOP", (0, 1), (0, 2)),
        ("PUSH", (2, 2), (1, 2)),
        ("HOP", (0, 0), (2, 2)),
        ("PUSH", (2, 0), (1, 0)),
    ),
    ("A", "NO_LEGAL_ACTION", False, True): (
        ("HOP", (0, 1), (0, 2)),
        ("PUSH", (1, 1), (0, 1)),
        ("HOP", (0, 0), (1, 1)),
        ("PUSH", (2, 2), (1, 1)),
        ("HOP", (1, 0), (2, 1)),
        ("PUSH", (2, 0), (1, 0)),
        ("HOP", (2, 1), (2, 2)),
    ),
    ("B", "NO_LEGAL_ACTION", True, True): (
        ("HOP", (1, 0), (1, 2)),
        ("PUSH", (2, 2), (1, 2)),
        ("HOP", (0, 0), (2, 2)),
        ("PUSH", (1, 1), (0, 0)),
    ),
}


def game(
    raw,
    policy_a,
    policy_b,
    seed,
    cap,
    *,
    effect_a=True,
    effect_b=True,
    winner=None,
    reason="GOAL",
):
    """A mocked result built only from one fixed synthetic engine trace."""

    if winner is None:
        if (policy_a, policy_b) in (("H3", "H2"), ("H3", "G")):
            winner = "A"
        elif (policy_a, policy_b) in (("H2", "H3"), ("G", "H3")):
            winner = "B"
        else:
            winner = "A" if seed % 2 else "B"

    requested = (winner, reason, effect_a, effect_b)
    if requested not in PATHS:
        if winner == "A" and not effect_a:
            requested = (winner, reason, False, False)
        else:
            raise ValueError("synthetic trace combination is unavailable")
    path = PATHS[requested]
    definition = parse_definition(raw)
    state = initial_state(definition)
    actions = []
    decisions = []
    nodes = {"A": 0, "B": 0}
    for kind, origin, target in path:
        actor = state.to_move.value
        policy = policy_a if actor == "A" else policy_b
        action = {"kind": kind, "from": list(origin), "to": list(target)}
        legal = [candidate.to_dict() for candidate in legal_actions(definition, state)]
        self_action = action_from_dict(action)
        if self_action not in legal_actions(definition, state):
            raise AssertionError("hard-coded synthetic action became illegal")
        decisions.append(_decision(state, legal, action, policy, nodes[actor]))
        nodes[actor] = decisions[-1]["nodes_after"]
        actions.append(action)
        state = apply_action(definition, state, self_action)
    if (
        not state.terminal
        or state.outcome.winner.value != winner
        or state.outcome.reason != reason
    ):
        raise AssertionError("hard-coded synthetic terminal path drifted")
    return {
        "status": "COMPLETE",
        "definition_hash": definition_hash(parse_definition(raw)),
        "first_player": "A",
        "policy_a": policy_a,
        "policy_b": policy_b,
        "seed": seed,
        "max_nodes_per_role": cap,
        "winner": winner,
        "plies": len(actions),
        "actions": actions,
        "terminal_reason": reason,
        "replay_count": 1,
        "replay_verified": True,
        "state_after_prefix": state.to_dict(),
        "unconfirmed_action": None,
        "nodes_by_role": nodes,
        "agent_a": screen.POLICY_IDENTITIES[policy_a],
        "agent_b": screen.POLICY_IDENTITIES[policy_b],
        "node_accounting": {
            "A": (
                "UNMETERED_GOAL_PROGRESS_NOT_ZERO_COMPUTE"
                if policy_a == "G"
                else "SEARCH_CACHE_MISSES"
            ),
            "B": (
                "UNMETERED_GOAL_PROGRESS_NOT_ZERO_COMPUTE"
                if policy_b == "G"
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
    index = 0 if role == "A" else 1
    decision = copy.deepcopy(result["decisions"][index])
    decision.update(selection_status="UNKNOWN_CENSORED", selected_action=None)
    decision.update(nodes_after=cap, charged_nodes=cap - decision["nodes_before"])
    if decision.get("last_action_values") is not None:
        decision["last_action_values"] = []
    decisions = copy.deepcopy(result["decisions"][:index]) + [decision]
    actions = copy.deepcopy(result["actions"][:index])
    result.update(
        status="UNKNOWN_CENSORED",
        winner=None,
        terminal_reason=None,
        plies=index,
        actions=actions,
        decisions=decisions,
        state_after_prefix=copy.deepcopy(decision["input_state"]),
        censor={
            "role": role,
            "scope": "game",
            "visited_nodes": cap,
            "max_nodes": cap,
        },
    )
    result["nodes_by_role"] = {
        "A": decisions[0]["nodes_after"] if index else 0,
        "B": 0,
    }
    result["nodes_by_role"][role] = cap
    return result


def replace_effect(result, actor, present):
    if present:
        effect_a, effect_b = True, True
    elif actor == "A":
        effect_a = False
        effect_b = result["winner"] == "B"
    else:
        effect_a, effect_b = True, False
    replacement = game(
        tiny(),
        result["policy_a"],
        result["policy_b"],
        result["seed"],
        result["max_nodes_per_role"],
        effect_a=effect_a,
        effect_b=effect_b,
        winner=result["winner"],
        reason=result["terminal_reason"],
    )
    replacement["definition_hash"] = result["definition_hash"]
    result.clear()
    result.update(replacement)


def replace_reason(result, reason):
    if reason == "GOAL":
        effects = (True, True)
    elif result["winner"] == "A":
        effects = (False, True)
    else:
        effects = (True, True)
    replacement = game(
        tiny(),
        result["policy_a"],
        result["policy_b"],
        result["seed"],
        result["max_nodes_per_role"],
        effect_a=effects[0],
        effect_b=effects[1],
        winner=result["winner"],
        reason=reason,
    )
    replacement["definition_hash"] = result["definition_hash"]
    result.clear()
    result.update(replacement)


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
        identity = definition_hash(parse_definition(tiny()))
        with mock.patch.object(screen, "HASH", identity):
            planned = screen.schedule()
        for item in planned:
            if item["kind"] == "exact":
                result = {
                    "status": "UNKNOWN_CENSORED",
                    "definition_hash": item["definition_hash"],
                }
            else:
                offset = item["seed"] - screen.CELLS[item["cell"]][3]
                winner = "A" if offset < counts[item["cell"]] else "B"
                result = game(
                    tiny(),
                    item["policy_a"],
                    item["policy_b"],
                    item["seed"],
                    item["max_nodes_per_role"],
                    winner=winner,
                )
                result["definition_hash"] = item["definition_hash"]
            records.append(
                {"scheduled": item, "status": result["status"], "result": result}
            )
        return records

    def test_schedule_protocol_and_manifest_are_fixed_before_first_call(self):
        planned = screen.schedule()
        self.assertEqual(
            (
                screen.PLAN,
                screen.DATA,
                screen.PROTOCOL,
                screen.HASH,
                screen.PROPOSAL_SHA256,
                screen.EXPOSURE,
                screen.PROPOSAL_STATUS,
            ),
            (
                "docs/plans/active/0028-two-current-cross-weave-screen.md",
                "experiments/proposals/two-current-cross-weave-v0.json",
                "plan0028-two-current-cross-weave-v1",
                "c84f8cf6c01adb1e13f0668dd97cfc75112f63c4e5b0dbae89a22ea8e6e3100a",
                "eb4adfdab51b5441fae5c72af9d548884537665e74f978249d07a0866bc9582a",
                (
                    "SOURCE_DESIGNED_AFTER_PLAN0027_AND_FOUR_REJECTED_"
                    "PRESELECTION_WIRES_WITH_ROOT_ENGINE_AND_INDEPENDENT_"
                    "BOUNDED_AND_OR_AND_REACHABLE_STATE_LOWER_BOUND_"
                    "EXPOSED_NOT_CONFIRMATION"
                ),
                "FIXED_PROSPECTIVE_NOT_REGISTERED_NOT_PRODUCTION_EXECUTED",
            ),
        )
        self.assertEqual((len(planned), screen.PLANNED_GAMES), (81, 80))
        self.assertEqual([item["stage"] for item in planned[1:33]], ["base"] * 32)
        self.assertEqual(
            [(item["policy_a"], item["policy_b"]) for item in planned[1:]],
            [("H3", "H3")] * 16
            + [("T3", "T3")] * 16
            + [("H3", "H3")] * 16
            + [("H3", "H2")] * 8
            + [("H2", "H3")] * 8
            + [("H3", "G")] * 8
            + [("G", "H3")] * 8,
        )
        self.assertEqual(
            [item["seed"] for item in planned[1:]],
            list(range(1100, 1116)) * 2
            + list(range(1200, 1216))
            + list(range(1200, 1208)) * 4,
        )
        self.assertEqual(
            len({json.dumps(item, sort_keys=True) for item in planned}), 81
        )

        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)

            def exact_after_manifest(raw, cap):
                manifest = read_json(
                    repository
                    / "experiments/runs"
                    / screen.PROTOCOL
                    / "manifest.json"
                )
                self.assertEqual(manifest["schedule"], screen.schedule())
                self.assertEqual(manifest["exposure"], screen.EXPOSURE)
                certificate = manifest["certificate"]
                self.assertEqual(
                    (
                        certificate["initial_phi"],
                        certificate["max_natural_plies"],
                        certificate["configured_max_plies"],
                        certificate["depth3_nodes_per_role_game_bound"],
                        certificate["depth2_nodes_per_role_game_bound"],
                    ),
                    (50, 50, 51, 27750, 2750),
                )
                return exact_complete(raw, cap)

            result, games, solves = self.run_mocked(
                repository, exact=exact_after_manifest
            )
            self.assertEqual((games, solves), (0, 1))
            self.assertEqual(result["disposition"], "TOO_EASILY_SOLVED")

    def test_full_positive_run_is_only_a_provisional_pilot_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            result, games, solves = self.run_mocked(repository)
            self.assertEqual((games, solves, result["attempted"]), (80, 1, 81))
            self.assertEqual(result["not_started"], 0)
            self.assertEqual(
                result["disposition"],
                "PILOT_GATES_PASS_AWAITING_AUDIT_REGRESSION",
            )
            self.assertTrue(result["pilot_gates_pass"])
            self.assertFalse(result["human_review_eligible"])
            self.assertEqual(
                result["statuses"], {"UNKNOWN_CENSORED": 1, "COMPLETE": 80}
            )
            self.assertEqual(result["base_realized_effect_games"], {"A": 32, "B": 32})
            self.assertEqual(result["realized_effect_games"], {"A": 80, "B": 80})
            self.assertEqual(result["base_goal_wins"], {"A": 16, "B": 16})
            self.assertEqual(result["goal_wins"], {"A": 40, "B": 40})
            self.assertEqual(
                result["charged_nodes_total"],
                sum(result["charged_nodes_by_role"].values()),
            )
            self.assertLessEqual(result["charged_nodes_total"], 3596000)
            resources = result["operational_resource_policy"]
            self.assertEqual(
                (
                    resources["structural_charged_nodes_bound"],
                    resources["configured_charged_nodes_ceiling"],
                    resources["max_output_files"],
                    resources["max_output_file_bytes"],
                ),
                (3596000, 16000000, 168, 64 * 1024 * 1024),
            )
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
                self.assertEqual(
                    hashlib.sha256((output / name).read_bytes()).hexdigest(),
                    digest,
                )
            with self.assertRaises(FileExistsError):
                self.run_mocked(repository)

    def test_exact_short_base_numeric_effect_goal_and_censor_gates(self):
        cases = (
            ("exact", "TOO_EASILY_SOLVED", 0),
            ("short_loss", "SHORT_FORCED_RESULT", 17),
            ("short_win", "SHORT_FORCED_RESULT", 17),
            ("base_h3_low", "NO_FLAG", 32),
            ("base_h3_high", "NO_FLAG", 32),
            ("base_t3_low", "NO_FLAG", 32),
            ("base_t3_high", "NO_FLAG", 32),
            ("effect_a", "NO_FLAG", 32),
            ("effect_b", "NO_FLAG", 32),
            ("goal_a", "NO_FLAG", 32),
            ("goal_b", "NO_FLAG", 32),
            ("base_censor", "FAILED", 1),
        )
        for mode, disposition, expected_games in cases:
            def solve(raw, cap):
                return exact_complete(raw, cap) if mode == "exact" else fake_exact(raw, cap)

            def play(raw, policy_a, policy_b, seed, cap):
                result = game(raw, policy_a, policy_b, seed, cap)
                if mode.startswith("short") and policy_a == policy_b == "T3":
                    value = -1 if mode == "short_loss" else 1
                    result["decisions"][0]["last_action_values"] = [
                        {"action": copy.deepcopy(action), "value": value}
                        for action in result["decisions"][0]["legal_actions"]
                    ]
                elif mode == "base_h3_low" and policy_a == policy_b == "H3":
                    result = game(
                        raw, policy_a, policy_b, seed, cap,
                        winner="A" if seed < 1103 else "B",
                    )
                elif mode == "base_h3_high" and policy_a == policy_b == "H3":
                    result = game(
                        raw, policy_a, policy_b, seed, cap,
                        winner="A" if seed < 1113 else "B",
                    )
                elif mode == "base_t3_low" and policy_a == policy_b == "T3":
                    result = game(
                        raw, policy_a, policy_b, seed, cap,
                        winner="A" if seed < 1103 else "B",
                    )
                elif mode == "base_t3_high" and policy_a == policy_b == "T3":
                    result = game(
                        raw, policy_a, policy_b, seed, cap,
                        winner="A" if seed < 1113 else "B",
                    )
                elif mode == "effect_a":
                    result = game(raw, policy_a, policy_b, seed, cap, effect_a=False)
                elif mode == "effect_b":
                    result = game(raw, policy_a, policy_b, seed, cap, effect_b=False)
                elif mode == "goal_a" and result["winner"] == "A":
                    replace_reason(result, "NO_LEGAL_ACTION")
                elif mode == "goal_b" and result["winner"] == "B":
                    replace_reason(result, "NO_LEGAL_ACTION")
                elif mode == "base_censor" and policy_a == policy_b == "H3" and seed == 1100:
                    result = censor(raw, policy_a, policy_b, seed, cap)
                return result

            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temporary:
                result, games, solves = self.run_mocked(
                    Path(temporary), play, solve
                )
                execution = "FAILED" if mode == "base_censor" else "COMPLETE"
                self.assertEqual(
                    (result["execution_status"], result["disposition"], games, solves),
                    (execution, disposition, expected_games, 1),
                )
                if mode == "base_censor":
                    self.assertEqual(result["not_started_failure"], 79)
                    self.assertEqual(result["not_started_gate_closed"], 0)
                else:
                    self.assertEqual(
                        result["not_started_gate_closed"], 80 - expected_games
                    )

    def test_structurally_impossible_final_censor_stops_as_failure(self):
        def play(raw, policy_a, policy_b, seed, cap):
            if (policy_a, policy_b, seed) == ("G", "H3", 1200):
                return censor(raw, policy_a, policy_b, seed, cap, role="A")
            return game(raw, policy_a, policy_b, seed, cap)

        with tempfile.TemporaryDirectory() as temporary:
            result, games, _ = self.run_mocked(Path(temporary), play=play)
            self.assertEqual((games, result["attempted"], result["not_started"]), (73, 74, 7))
            self.assertEqual(
                (result["execution_status"], result["disposition"]),
                ("FAILED", "FAILED"),
            )
            self.assertEqual(result["not_started_failure"], 7)

    def test_every_fixed_numerical_threshold_edge_is_separate(self):
        passing = [8, 8, 8, 6, 2, 6, 2]
        summary = screen.summarize(self.records_with_counts(passing), raw=tiny())
        self.assertTrue(summary["pilot_gates_pass"])
        self.assertFalse(summary["human_review_eligible"])
        pass_edges = (
            (0, 4), (0, 12), (1, 4), (1, 12), (2, 4), (2, 12),
            (3, 6), (4, 2), (5, 6), (6, 2),
        )
        fail_edges = (
            (0, 3), (0, 13), (1, 3), (1, 13), (2, 3), (2, 13),
            (3, 5), (4, 3), (5, 5), (6, 3),
        )
        for cell, wins in pass_edges:
            counts = list(passing)
            counts[cell] = wins
            with self.subTest(kind="pass", cell=cell, wins=wins):
                self.assertTrue(
                    screen.summarize(self.records_with_counts(counts), raw=tiny())[
                        "pilot_gates_pass"
                    ]
                )
        for cell, wins in fail_edges:
            counts = list(passing)
            counts[cell] = wins
            with self.subTest(kind="fail", cell=cell, wins=wins):
                summary = screen.summarize(self.records_with_counts(counts), raw=tiny())
                self.assertFalse(summary["pilot_gates_pass"])
                self.assertEqual(summary["disposition"], "NO_FLAG")

    def test_interaction_gates_count_distinct_complete_games(self):
        passing = [8, 8, 8, 6, 2, 6, 2]
        for actor in ("A", "B"):
            records = self.records_with_counts(passing)
            games = [r for r in records if r["scheduled"]["kind"] == "game"]
            for record in games:
                replace_effect(record["result"], actor, False)
            base = [r for r in games if r["scheduled"]["stage"] == "base"]
            final = [r for r in games if r["scheduled"]["stage"] != "base"]
            for record in base[:4] + final[:3]:
                replace_effect(record["result"], actor, True)
            with self.subTest(actor=actor, full=7):
                summary = screen.summarize(records, raw=tiny())
                self.assertEqual(summary["base_realized_effect_games"][actor], 4)
                self.assertEqual(summary["realized_effect_games"][actor], 7)
                self.assertFalse(summary["pilot_gates_pass"])
            replace_effect(final[3]["result"], actor, True)
            with self.subTest(actor=actor, full=8):
                self.assertTrue(screen.summarize(records, raw=tiny())["pilot_gates_pass"])

            records = self.records_with_counts(passing)
            games = [r for r in records if r["scheduled"]["kind"] == "game"]
            for record in games:
                replace_effect(record["result"], actor, False)
            base = [r for r in games if r["scheduled"]["stage"] == "base"]
            final = [r for r in games if r["scheduled"]["stage"] != "base"]
            for record in base[:3] + final[:5]:
                replace_effect(record["result"], actor, True)
            summary = screen.summarize(records, raw=tiny())
            self.assertEqual(summary["realized_effect_games"][actor], 8)
            self.assertFalse(summary["base_interaction_pass"])
            self.assertFalse(summary["pilot_gates_pass"])

    def test_goal_win_gates_are_base_limited_then_full_schedule(self):
        passing = [8, 8, 8, 6, 2, 6, 2]
        records = self.records_with_counts(passing)
        games = [r for r in records if r["scheduled"]["kind"] == "game"]
        for record in games:
            replace_reason(record["result"], "NO_LEGAL_ACTION")
        chosen = {}
        for actor in ("A", "B"):
            base = [
                r for r in games
                if r["scheduled"]["stage"] == "base"
                and r["result"]["winner"] == actor
            ]
            final = [
                r for r in games
                if r["scheduled"]["stage"] != "base"
                and r["result"]["winner"] == actor
            ]
            chosen[actor] = base[:2] + final[:2]
            for record in chosen[actor]:
                replace_reason(record["result"], "GOAL")
        summary = screen.summarize(records, raw=tiny())
        self.assertEqual(summary["base_goal_wins"], {"A": 2, "B": 2})
        self.assertEqual(summary["goal_wins"], {"A": 4, "B": 4})
        self.assertTrue(summary["pilot_gates_pass"])

        replace_reason(chosen["A"][-1]["result"], "NO_LEGAL_ACTION")
        self.assertFalse(screen.summarize(records, raw=tiny())["pilot_gates_pass"])
        replace_reason(chosen["A"][-1]["result"], "GOAL")
        replace_reason(chosen["B"][0]["result"], "NO_LEGAL_ACTION")
        extra = next(
            r for r in games
            if r["scheduled"]["stage"] != "base"
            and r["result"]["winner"] == "B"
            and r not in chosen["B"]
        )
        replace_reason(extra["result"], "GOAL")
        summary = screen.summarize(records, raw=tiny())
        self.assertEqual(summary["goal_wins"]["B"], 4)
        self.assertFalse(summary["base_goal_pass"])
        self.assertFalse(summary["pilot_gates_pass"])

    def test_actual_effects_require_saved_geometry_and_occupancy(self):
        raw = tiny()
        item = {
            "kind": "game",
            "first_player": "A",
            "definition_hash": definition_hash(parse_definition(raw)),
            "policy_a": "H3",
            "policy_b": "H3",
            "seed": 1,
            "max_nodes_per_role": screen.MAX_NODES,
        }
        result = game(raw, "H3", "H3", 1, screen.MAX_NODES)
        self.assertFalse(hasattr(screen, "apply_action"))
        with mock.patch(
            "parity_forge.engine.apply_action",
            side_effect=AssertionError("screen evidence must not replay actions"),
        ):
            self.assertEqual(
                screen.game_evidence(item, result, raw)["realized_effect"],
                {"A": True, "B": True},
            )
        for effect_a, effect_b, winner in (
            (False, True, "B"),
            (True, False, "A"),
            (False, False, "A"),
        ):
            result = game(
                raw,
                "H3",
                "H3",
                1,
                screen.MAX_NODES,
                effect_a=effect_a,
                effect_b=effect_b,
                winner=winner,
            )
            self.assertEqual(
                screen.game_evidence(item, result, raw)["realized_effect"],
                {"A": effect_a, "B": effect_b},
            )

    def test_legal_action_and_applied_trace_corruption_fail_closed(self):
        raw = tiny()
        item = {
            "kind": "game",
            "first_player": "A",
            "definition_hash": definition_hash(parse_definition(raw)),
            "policy_a": "T3",
            "policy_b": "T3",
            "seed": 1,
            "max_nodes_per_role": screen.MAX_NODES,
        }
        valid = game(raw, "T3", "T3", 1, screen.MAX_NODES)
        screen.validate_result(item, valid, raw)

        def absent_selected(result):
            result["decisions"][0]["legal_actions"].pop(0)
            result["decisions"][0]["legal_action_count"] -= 1
            result["decisions"][0]["last_action_values"].pop(0)

        def invalid_legal_vector(result):
            legal = result["decisions"][0]["legal_actions"][1]
            legal["to"] = [2, 1]
            result["decisions"][0]["last_action_values"][1]["action"] = copy.deepcopy(legal)

        def omit_unselected_legal(result):
            result["decisions"][0]["legal_actions"].pop()
            result["decisions"][0]["last_action_values"].pop()
            result["decisions"][0]["legal_action_count"] -= 1

        def add_legal(result):
            extra = copy.deepcopy(result["decisions"][0]["legal_actions"][-1])
            result["decisions"][0]["legal_actions"].append(extra)
            result["decisions"][0]["last_action_values"].append(
                {"action": copy.deepcopy(extra), "value": 0}
            )
            result["decisions"][0]["legal_action_count"] += 1

        def alternate_initial_state(result):
            piece = result["decisions"][0]["input_state"]["pieces"][0]
            piece["position"] = [2, 1]

        def missing_hop_intermediate(result):
            state = result["decisions"][0]["input_state"]
            state["pieces"] = [p for p in state["pieces"] if p["position"] != [0, 1]]

        def bad_push_target(result):
            target = result["decisions"][1]["selected_action"]["to"]
            piece = next(
                p for p in result["decisions"][1]["input_state"]["pieces"]
                if p["position"] == target
            )
            piece.update(owner="B", piece="b")

        for mutate in (
            lambda result: result["decisions"][0].update(legal_action_count=3),
            lambda result: result["decisions"][0]["legal_actions"].reverse(),
            absent_selected,
            omit_unselected_legal,
            add_legal,
            invalid_legal_vector,
            alternate_initial_state,
            missing_hop_intermediate,
            bad_push_target,
            lambda result: result["decisions"][0]["last_action_values"][0].update(value=2),
            lambda result: result["decisions"][0]["last_action_values"][0].update(action={}),
            lambda result: result["decisions"][0].update(nodes_before=1),
            lambda result: result["decisions"][0].update(charged_nodes=2),
            lambda result: result["nodes_by_role"].update(A=999),
            lambda result: result.update(agent_a="wrong-agent"),
            lambda result: result["decisions"][0]["selected_action"].update(to=[1, 1]),
            lambda result: result["state_after_prefix"]["pieces"].pop(),
            lambda result: result["state_after_prefix"]["outcome"].update(winner="B"),
        ):
            result = copy.deepcopy(valid)
            mutate(result)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                screen.validate_result(item, result, raw)

    def test_result_validation_exact_censor_node_and_replay_edges(self):
        raw = tiny()
        game_item = {
            "kind": "game",
            "first_player": "A",
            "definition_hash": definition_hash(parse_definition(raw)),
            "policy_a": "G",
            "policy_b": "H3",
            "seed": 1,
            "max_nodes_per_role": screen.MAX_NODES,
        }
        valid = game(raw, "G", "H3", 1, screen.MAX_NODES)
        screen.validate_result(game_item, valid, raw)
        terminal_item = dict(game_item, policy_a="T2", policy_b="T2")
        terminal_valid = game(raw, "T2", "T2", 1, screen.MAX_NODES)
        screen.validate_result(terminal_item, terminal_valid, raw)
        for mutate in (
            lambda result: result["nodes_by_role"].update(A=1),
            lambda result: result["node_accounting"].update(A="ZERO_COMPUTE"),
            lambda result: result["nodes_by_role"].update(B=screen.MAX_NODES + 1),
            lambda result: result.update(replay_count=2),
            lambda result: result.update(winner=None),
            lambda result: result.update(terminal_reason="PLY_LIMIT"),
            lambda result: result.update(
                plies=0,
                actions=[],
                decisions=[],
                state_after_prefix=copy.deepcopy(
                    result["decisions"][0]["input_state"]
                ),
            ),
        ):
            result = copy.deepcopy(valid)
            mutate(result)
            with self.assertRaises(ValueError):
                screen.validate_result(game_item, result, raw)

        censored = censor(raw, "G", "H3", 1, screen.MAX_NODES, role="B")
        with self.assertRaises(ValueError):
            screen.validate_result(game_item, censored, raw)

    def test_censored_prefix_chain_is_checked_before_rejection(self):
        raw = tiny()
        cap = 100
        item = {
            "kind": "game",
            "first_player": "A",
            "definition_hash": definition_hash(parse_definition(raw)),
            "policy_a": "H3",
            "policy_b": "H3",
            "seed": 1,
            "max_nodes_per_role": cap,
        }
        valid = censor(raw, "H3", "H3", 1, cap, role="B")
        evidence = screen._trace_evidence(item, valid, raw)
        self.assertEqual(evidence["realized_effect"], {"A": False, "B": False})
        with self.assertRaisesRegex(ValueError, "structural node bound"):
            screen.validate_result(item, valid, raw)

        for mutate in (
            lambda result: result["decisions"].pop(),
            lambda result: result["actions"][0].update(to=[1, 1]),
            lambda result: result["state_after_prefix"].update(ply=2),
            lambda result: result["decisions"][-1].update(
                selection_status="SELECTED"
            ),
            lambda result: result["censor"].update(role="A"),
            lambda result: result["decisions"][0]["input_state"]["pieces"].pop(),
        ):
            result = copy.deepcopy(valid)
            mutate(result)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                screen._trace_evidence(item, result, raw)

        exact_item = {
            "kind": "exact",
            "definition_hash": definition_hash(parse_definition(raw)),
            "max_states": screen.MAX_STATES,
        }
        screen.validate_result(exact_item, fake_exact(raw, screen.MAX_STATES), raw)
        for result in (
            exact_complete(raw, screen.MAX_STATES, value=0),
            exact_complete(raw, screen.MAX_STATES, plies=screen.BOUND + 1),
            exact_complete(raw, screen.MAX_STATES, reason="PLY_LIMIT"),
        ):
            with self.assertRaises(ValueError):
                screen.validate_result(exact_item, result, raw)
        bad_unknown = fake_exact(raw, screen.MAX_STATES)
        bad_unknown["error"]["searched_states"] -= 1
        with self.assertRaises(ValueError):
            screen.validate_result(exact_item, bad_unknown, raw)

    def test_started_failures_and_publication_failures_never_promote(self):
        for mode in ("exception", "draw", "bound", "replay", "source", "publication"):
            calls = []
            original_publish = screen._publish

            def play(raw, policy_a, policy_b, seed, cap):
                calls.append(1)
                if mode == "exception":
                    raise RuntimeError("synthetic failure")
                result = game(raw, policy_a, policy_b, seed, cap)
                if mode == "draw":
                    result.update(winner=None, terminal_reason="PLY_LIMIT")
                elif mode == "bound":
                    result.update(plies=screen.BOUND + 1, actions=[{}] * (screen.BOUND + 1))
                elif mode == "replay":
                    result["replay_count"] = 2
                return result

            def snapshot(*args, **kwargs):
                changed = mode == "source" and calls
                return {
                    "git_commit": "a" * 40,
                    "sha256": {"synthetic.py": "changed" if changed else "pinned"},
                }

            def publish(path, value):
                if mode == "publication" and path.name == "0001-result.json":
                    raise OSError("synthetic disk failure")
                original_publish(path, value)

            with self.subTest(
                mode=mode
            ), tempfile.TemporaryDirectory() as temporary, mock.patch.object(
                screen, "_publish", side_effect=publish
            ):
                repository = Path(temporary)
                result, games, solves = self.run_mocked(
                    repository, play=play, snapshot=snapshot
                )
                self.assertEqual((games, solves, result["execution_status"]), (1, 1, "FAILED"))
                self.assertEqual(
                    (
                        result["attempted"],
                        result["statuses"]["FAILED"],
                        result["not_started_failure"],
                    ),
                    (2, 1, 79),
                )
                self.assertFalse(result["pilot_gates_pass"])
                self.assertFalse(result["human_review_eligible"])
                failure = read_json(
                    repository / "experiments/runs" / screen.PROTOCOL / "failure.json"
                )
                self.assertIsNotNone(failure["current"])

        for mode in ("artifact", "summary"):
            original_publish = screen._publish

            def publish(path, value):
                if mode == "summary" and path.name == "summary.json":
                    raise OSError("synthetic finalization failure")
                original_publish(path, value)
                if mode == "artifact" and path.name == "0001-result.json":
                    (path.parent / "manifest.json").write_text("changed")

            with self.subTest(
                mode=mode
            ), tempfile.TemporaryDirectory() as temporary, mock.patch.object(
                screen, "_publish", side_effect=publish
            ):
                repository = Path(temporary)
                result, games, _ = self.run_mocked(repository)
                self.assertEqual(
                    (games, result["execution_status"], result["disposition"]),
                    (80, "FAILED", "FAILED"),
                )
                self.assertFalse(result["pilot_gates_pass"])
                self.assertFalse(result["human_review_eligible"])

    def test_two_post_creation_finalization_failures_fit_file_ceiling(self):
        original_publish = screen._publish

        def publish(path, value):
            original_publish(path, value)
            if path.name in ("source-verification.json", "summary.json"):
                raise OSError("synthetic failure after destination creation")

        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(
            screen, "_publish", side_effect=publish
        ):
            repository = Path(temporary)
            result, games, solves = self.run_mocked(repository)
            output = repository / "experiments/runs" / screen.PROTOCOL
            self.assertEqual(
                (games, solves, len(tuple(output.iterdir()))),
                (80, 1, 168),
            )
            self.assertEqual(
                (result["execution_status"], result["disposition"]),
                ("FAILED", "FAILED"),
            )
            self.assertFalse(result["pilot_gates_pass"])
            self.assertFalse(result["human_review_eligible"])
            self.assertEqual(
                read_json(output / "summary-publication-failure.json"), result
            )

    def test_real_git_pins_and_fixed_wire_load_use_synthetic_3x3_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            raw = copy.deepcopy(tiny())
            raw["max_plies"] = screen.PLY_LIMIT
            raw = json.loads(canonical_json(parse_definition(raw)))
            payload = {
                "status": screen.PROPOSAL_STATUS,
                "exposure": screen.EXPOSURE,
                "definitions": [raw],
            }
            files = (
                (screen.PLAN, "synthetic plan"),
                (screen.DATA, json.dumps(payload)),
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
            self.assertEqual(
                set(pins["sha256"]), {screen.PLAN, screen.DATA, "source.py"}
            )
            self.assertRegex(pins["git_commit"], r"^[0-9a-f]{40}$")
            data_path = repository / screen.DATA
            data_hash = hashlib.sha256(data_path.read_bytes()).hexdigest()
            with mock.patch.object(
                screen, "HASH", definition_hash(parse_definition(raw))
            ), mock.patch.object(
                screen, "PROPOSAL_SHA256", data_hash
            ), mock.patch.object(
                screen, "INITIAL_PHI", 15
            ), mock.patch.object(
                screen, "INITIAL_MOBILITY", {"A": 5, "B": 1}
            ):
                self.assertEqual(screen.load_definition(repository), raw)
                changed = copy.deepcopy(payload)
                changed["exposure"] = "wrong"
                data_path.write_text(json.dumps(changed))
                changed_hash = hashlib.sha256(data_path.read_bytes()).hexdigest()
                with mock.patch.object(
                    screen, "PROPOSAL_SHA256", changed_hash
                ), self.assertRaises(ValueError):
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
