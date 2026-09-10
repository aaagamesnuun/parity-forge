"""Synthetic/static Plan0030 tests; never execute a frozen production game."""

import copy
from collections import Counter
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

from parity_forge.agents import SearchBudgetExceeded
from parity_forge.dsl import canonical_json, parse_definition
from parity_forge.engine import GameState, Outcome
from scripts import plan0030_preselection as screen


REPOSITORY = Path(__file__).resolve().parents[1]


def rewrite_envelope(path, payload):
    digest = hashlib.sha256(screen.canonical_bytes(payload)).hexdigest()
    path.write_bytes(
        screen.canonical_bytes({"payload": payload, "sha256": digest})
    )


def tiny():
    raw = {
        "schema_version": 4,
        "name": "plan0030 synthetic moving race",
        "board_size": 3,
        "first_player": "A",
        "max_plies": 9,
        "roles": {
            "A": {
                "action": {
                    "kind": "HOP",
                    "piece": "a",
                    "vectors": [[0, 1], [1, -1], [1, 0], [1, 1]],
                },
                "goal": {"kind": "REACH_EDGE", "piece": "a", "edge": "BOTTOM"},
            },
            "B": {
                "action": {
                    "kind": "MOVE",
                    "piece": "b",
                    "vectors": [[-1, -1], [-1, 0], [-1, 1], [0, -1]],
                },
                "goal": {"kind": "REACH_EDGE", "piece": "b", "edge": "TOP"},
            },
        },
        "initial_pieces": [
            {"owner": "A", "piece": "a", "position": [0, 0]},
            {"owner": "A", "piece": "a", "position": [0, 2]},
            {"owner": "B", "piece": "b", "position": [2, 1]},
        ],
    }
    return json.loads(canonical_json(parse_definition(raw)))


def fake_proposal():
    proposal = json.loads((REPOSITORY / screen.DATA).read_text())
    proposal = copy.deepcopy(proposal)
    for row in proposal["ranked_candidates"]:
        row["definition"] = {"synthetic_cell": row["cell"]}
    return proposal


def _row(proposal, cell):
    return proposal["ranked_candidates"][cell - 1]


def short_result(proposal, raw, target, target_ply, seed, cap, values=None):
    row = _row(proposal, raw["synthetic_cell"])
    actions = [
        {"kind": "MOVE", "from": [0, 0], "to": [1, 0]},
        {"kind": "MOVE", "from": [0, 1], "to": [1, 1]},
    ]
    if values is None:
        values = [0, 0] if target == "A" else [-1, 0]
    root = max(values)
    return {
        "status": "COMPLETE",
        "definition_hash": row["definition_hash"],
        "target": target,
        "target_ply": target_ply,
        "seed": seed,
        "max_nodes": cap,
        "agent": "terminal_only_minimax-v1-depth{}".format(target_ply),
        "root_actions": actions,
        "action_values": [
            {"action": action, "value": value}
            for action, value in zip(actions, values)
        ],
        "selected_action": actions[0],
        "root_min": min(values),
        "root_max": max(values),
        "root_value": root,
        "target_utility": {"A": 1, "B": -1}[target],
        "forced_win": root == {"A": 1, "B": -1}[target],
        "expanded_nodes": 2,
        "cache_hits": 0,
        "error": None,
        "replay_count": 0,
    }


def censored_short(proposal, raw, target, target_ply, seed, cap):
    row = _row(proposal, raw["synthetic_cell"])
    return {
        "status": "UNKNOWN_CENSORED",
        "definition_hash": row["definition_hash"],
        "target": target,
        "target_ply": target_ply,
        "seed": seed,
        "max_nodes": cap,
        "agent": "terminal_only_minimax-v1-depth{}".format(target_ply),
        "root_actions": [{"kind": "MOVE", "from": [0, 0], "to": [1, 0]}],
        "action_values": [],
        "selected_action": None,
        "root_min": None,
        "root_max": None,
        "root_value": None,
        "target_utility": {"A": 1, "B": -1}[target],
        "forced_win": None,
        "expanded_nodes": cap,
        "cache_hits": None,
        "error": {
            "type": "SearchBudgetExceeded",
            "scope": "per-slot",
            "searched_nodes": cap,
            "max_nodes": cap,
        },
        "replay_count": 0,
    }


def game_result(proposal, raw, policy_a, policy_b, seed, cap, winner=None, reason="GOAL"):
    row = _row(proposal, raw["synthetic_cell"])
    if winner is None:
        winner = "A" if seed % 2 == 0 else "B"
    action = {"kind": "MOVE", "from": [0, 0], "to": [1, 0]}
    decisions = [{
        "ply": 0,
        "actor": "A",
        "legal_action_count": 1,
        "selected_action": action,
        "selection_status": "SELECTED",
        "nodes_before": 0,
        "nodes_after": 1,
        "charged_nodes": 1,
        "last_action_values": [{"action": action, "value": 0}],
    }]
    observed = {
        "actions": [action],
        "agent_a": screen.POLICY_IDENTITIES[policy_a],
        "agent_b": screen.POLICY_IDENTITIES[policy_b],
        "plies": 1,
        "seed": seed,
        "winner": winner,
        "terminal_reason": reason,
    }
    return {
        "status": "COMPLETE",
        "definition_hash": row["definition_hash"],
        "first_player": "A",
        "policy_a": policy_a,
        "policy_b": policy_b,
        "seed": seed,
        "max_nodes_per_role": cap,
        "agent_a": screen.POLICY_IDENTITIES[policy_a],
        "agent_b": screen.POLICY_IDENTITIES[policy_b],
        "node_accounting": {"A": "SEARCH_CACHE_MISSES", "B": "SEARCH_CACHE_MISSES"},
        "nodes_by_role": {"A": 1, "B": 0},
        "winner": winner,
        "terminal_reason": reason,
        "plies": 1,
        "actions": [action],
        "decisions": decisions,
        "replay_count": 1,
        "replay_verified": True,
        "error": None,
        "censor": None,
        "unconfirmed_action": None,
        "state_after_prefix": {
            "ply": 1,
            "to_move": "B",
            "pieces": [],
            "outcome": {"winner": winner, "reason": reason},
        },
        "observed_game_record": observed,
    }


def unknown_exact(proposal, raw, cap):
    row = _row(proposal, raw["synthetic_cell"])
    return {
        "status": "UNKNOWN_CENSORED",
        "definition_hash": row["definition_hash"],
        "max_states": cap,
        "actual_result": None,
        "replay_count": 0,
        "error": {
            "type": "SolveBudgetExceeded",
            "searched_states": cap,
            "max_states": cap,
        },
    }


def complete_exact(proposal, raw, cap):
    row = _row(proposal, raw["synthetic_cell"])
    action = {"kind": "MOVE", "from": [0, 0], "to": [1, 0]}
    return {
        "status": "COMPLETE",
        "definition_hash": row["definition_hash"],
        "max_states": cap,
        "replay_count": 1,
        "error": None,
        "terminal_state": {
            "ply": 1,
            "to_move": "B",
            "pieces": [],
            "outcome": {"winner": "A", "reason": "GOAL"},
        },
        "actual_result": {
            "value_for_a": 1,
            "forced_result": "A_WIN",
            "principal_variation": [action],
            "principal_variation_plies": 1,
            "searched_states": 2,
            "cache_hits": 0,
            "terminal_reason": "GOAL",
        },
    }


def bfs_result(proposal, raw, stop, maximum_branching, exhausted=False):
    row = _row(proposal, raw["synthetic_cell"])
    seen = stop - 1 if exhausted else stop
    return {
        "status": "EXHAUSTED" if exhausted else "PREFIX_LIMIT_REACHED",
        "definition_hash": row["definition_hash"],
        "stop_after_seen_states": stop,
        "maximum_branching": maximum_branching,
        "seen_states": seen,
        "expanded_states": max(0, seen - 1),
        "terminal_states": 1 if seen > 1 else 0,
        "terminal_states_by_winner": {
            "A": 1 if seen > 1 else 0,
            "B": 0,
        },
        "terminal_states_by_reason": {
            "GOAL": 1 if seen > 1 else 0,
            "NO_LEGAL_ACTION": 0,
        },
        "draw_terminal_states": 0,
        "ply_limit_terminal_states": 0,
        "transitions": max(0, seen - 1),
        "max_queue_references": 1,
        "stored_edges": 0,
        "state_digests": [hashlib.sha256(str(index).encode()).hexdigest() for index in range(seen)],
        "rolling_transition_sha256": hashlib.sha256(b"transitions").hexdigest(),
        "identity_model": "FULL_GAME_STATE_PLY_TO_MOVE_PIECES_OUTCOME",
        "queue_order": "FIFO_CANONICAL_ACTION_TUPLE",
        "state_digest_algorithm": "SHA256_CANONICAL_STATE_DICT_V1",
        "transition_digest_algorithm": "SHA256_CONCAT_CANONICAL_FROM_ACTION_TO_V1",
        "transition_digest_includes_duplicates": True,
        "terminal_states_expanded": False,
        "error": None,
        "replay_count": 0,
    }


class _FakeTerminalAgent:
    values = (-1, 0)

    def __init__(self, depth, cap):
        self.depth = depth
        self.cap = cap
        self.total_nodes = 0
        self.last_action_values = ()
        self.last_expanded_nodes = None
        self.last_cache_hits = None
        self.identity = SimpleNamespace(key="terminal_only_minimax-v1-depth{}".format(depth))

    def select_action(self, definition, state, actions, rng):
        values = tuple(self.values[index % len(self.values)] for index in range(len(actions)))
        self.last_action_values = tuple(zip(actions, values))
        self.total_nodes = self.last_expanded_nodes = 2
        self.last_cache_hits = 0
        return actions[0]


class Plan0030Tests(unittest.TestCase):
    def patch_mocked_run(
        self,
        stack,
        proposal,
        *,
        short=None,
        game=None,
        exact=None,
        bfs=None,
        publish=None,
    ):
        source = {
            "git_commit": "a" * 40,
            "plan": screen.PLAN,
            "proposal": screen.DATA,
            "design_record": screen.DESIGN_DATA,
            "source_sha256": {"synthetic.py": "b" * 64},
        }
        stack.enter_context(mock.patch.object(screen, "BFS_STOP", 5))
        stack.enter_context(mock.patch.object(screen, "source_snapshot", return_value=source))
        stack.enter_context(mock.patch.object(screen, "load_proposal", return_value=proposal))
        stack.enter_context(mock.patch.object(screen, "dependency_snapshot", return_value={"synthetic": {"file_sha256": "b" * 64}}))
        stack.enter_context(mock.patch.object(screen, "short_query", side_effect=short or (lambda *args: short_result(proposal, *args))))
        stack.enter_context(mock.patch.object(screen.play_adapter, "play_one", side_effect=game or (lambda *args: game_result(proposal, *args))))
        stack.enter_context(mock.patch.object(screen, "exact_one", side_effect=exact or (lambda *args: unknown_exact(proposal, *args))))
        stack.enter_context(mock.patch.object(screen, "bfs_prefix", side_effect=bfs or (lambda *args: bfs_result(proposal, *args))))
        if publish is not None:
            stack.enter_context(mock.patch.object(screen, "_publish", side_effect=publish))
        return source

    def test_frozen_proposal_hash_and_static_schedule(self):
        raw = (REPOSITORY / screen.DATA).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), screen.PROPOSAL_SHA256)
        proposal = screen.load_proposal(REPOSITORY)
        planned = screen.make_schedule(proposal)
        self.assertEqual(len(planned), 56)
        self.assertEqual([item["stage"] for item in planned[:8]], ["SHORT_FOUR"] * 8)
        self.assertEqual([item["stage"] for item in planned[8:40]], ["POLICY_GAMES"] * 32)
        self.assertEqual([item["stage"] for item in planned[40:44]], ["EXACT"] * 4)
        self.assertEqual([item["stage"] for item in planned[44:48]], ["BFS_PREFIX"] * 4)
        self.assertEqual([item["stage"] for item in planned[48:]], ["SHORT_SEVEN"] * 8)
        seeds = [item["seed"] for item in planned if "seed" in item]
        self.assertEqual((len(seeds), len(set(seeds))), (48, 48))

    def test_source_has_no_forbidden_production_imports(self):
        source = (REPOSITORY / "scripts/plan0030_preselection.py").read_text()
        for forbidden in ("replay_dicts", "play_game", "solve_game", "plan0028"):
            self.assertNotIn(forbidden, source)

    def test_b_target_uses_a_root_max_not_min(self):
        with mock.patch.object(screen, "TerminalOnlyMinimaxAgent", _FakeTerminalAgent):
            _FakeTerminalAgent.values = (-1, 0)
            mixed = screen.short_query(tiny(), "B", 8, 1, 100)
            self.assertEqual((mixed["root_min"], mixed["root_max"]), (-1, 0))
            self.assertFalse(mixed["forced_win"])
            _FakeTerminalAgent.values = (-1,)
            all_losing = screen.short_query(tiny(), "B", 8, 1, 100)
            self.assertEqual(all_losing["root_value"], -1)
            self.assertTrue(all_losing["forced_win"])

    def test_short_query_strict_budget_censor(self):
        class Censored(_FakeTerminalAgent):
            def select_action(self, definition, state, actions, rng):
                self.total_nodes = self.cap
                raise SearchBudgetExceeded("per-slot", self.cap, self.cap)

        with mock.patch.object(screen, "TerminalOnlyMinimaxAgent", Censored):
            result = screen.short_query(tiny(), "A", 7, 4, 9)
        self.assertEqual(result["status"], "UNKNOWN_CENSORED")
        self.assertEqual(result["expanded_nodes"], 9)

    def test_short_validator_rejects_b_min_error(self):
        proposal = fake_proposal()
        item = screen.make_schedule(proposal)[1]
        result = short_result(proposal, {"synthetic_cell": 1}, "B", 8, item["seed"], 100000)
        result["forced_win"] = True
        with self.assertRaises(ValueError):
            screen.validate_short_result(item, result)

    def test_game_role_structural_bound_and_exact_wire(self):
        proposal = fake_proposal()
        game_item = screen.make_schedule(proposal)[8]
        row = _row(proposal, 1)
        result = game_result(proposal, row["definition"], "T2", "T2", game_item["seed"], 100000)
        screen.validate_game_result(game_item, result, row)
        result["nodes_by_role"]["A"] = row["t2_nodes_per_role"] + 1
        with self.assertRaises(ValueError):
            screen.validate_game_result(game_item, result, row)
        exact_item = screen.make_schedule(proposal)[40]
        unknown = unknown_exact(proposal, row["definition"], 100000)
        screen.validate_exact_result(exact_item, unknown, row)
        complete = complete_exact(proposal, row["definition"], 100000)
        screen.validate_exact_result(exact_item, complete, row)
        complete["actual_result"]["principal_variation"] = []
        with self.assertRaises(ValueError):
            screen.validate_exact_result(exact_item, complete, row)

    def test_validator_rejects_bool_integer_aliases_and_zero_ply_exact(self):
        proposal = fake_proposal()
        row = _row(proposal, 1)

        short_item = screen.make_schedule(proposal)[0]
        short = short_result(
            proposal,
            row["definition"],
            "A",
            short_item["target_ply"],
            short_item["seed"],
            short_item["max_nodes"],
        )
        short["replay_count"] = False
        short["root_value"] = False
        with self.assertRaises(ValueError):
            screen.validate_short_result(short_item, short)

        short_unknown = censored_short(
            proposal,
            row["definition"],
            "A",
            short_item["target_ply"],
            short_item["seed"],
            short_item["max_nodes"],
        )
        short_unknown["target_utility"] = True
        with self.assertRaises(ValueError):
            screen.validate_short_result(short_item, short_unknown)

        game_item = screen.make_schedule(proposal)[8]
        game = game_result(
            proposal,
            row["definition"],
            "T2",
            "T2",
            game_item["seed"],
            game_item["max_nodes_per_role"],
        )
        game["replay_count"] = True
        game["decisions"][0]["ply"] = False
        with self.assertRaises(ValueError):
            screen.validate_game_result(game_item, game, row)

        exact_item = screen.make_schedule(proposal)[40]
        unknown = unknown_exact(
            proposal, row["definition"], exact_item["max_states"]
        )
        unknown["replay_count"] = False
        with self.assertRaises(ValueError):
            screen.validate_exact_result(exact_item, unknown, row)

        exact = complete_exact(proposal, row["definition"], exact_item["max_states"])
        exact["replay_count"] = True
        exact["actual_result"]["principal_variation"] = []
        exact["actual_result"]["principal_variation_plies"] = 0
        exact["terminal_state"]["ply"] = 0
        with self.assertRaises(ValueError):
            screen.validate_exact_result(exact_item, exact, row)

        bfs_item = screen.make_schedule(proposal)[44]
        bfs = bfs_result(
            proposal,
            row["definition"],
            bfs_item["stop_after_seen_states"],
            bfs_item["maximum_branching"],
        )
        bfs["stored_edges"] = False
        bfs["replay_count"] = False
        bfs["draw_terminal_states"] = False
        bfs["ply_limit_terminal_states"] = False
        with self.assertRaises(ValueError):
            screen.validate_bfs_result(bfs_item, bfs)

        integer_digest = bfs_result(
            proposal,
            row["definition"],
            bfs_item["stop_after_seen_states"],
            bfs_item["maximum_branching"],
        )
        integer_digest["rolling_transition_sha256"] = int("1" * 64)
        with self.assertRaises(ValueError):
            screen.validate_bfs_result(bfs_item, integer_digest)

    def test_accepted_dependency_wires_on_mechanically_separate_tiny_fixture(self):
        raw = tiny()
        identity = screen.definition_hash(screen.parse_definition(raw))
        row = {
            "maximum_branching": 15,
            "max_natural_plies": raw["max_plies"] - 1,
            "t2_nodes_per_role": 100000,
            "t3_nodes_per_role": 100000,
        }

        short_item = {
            "definition_hash": identity,
            "target": "A",
            "target_ply": 7,
            "seed": 7,
            "max_nodes": 100000,
        }
        screen.validate_short_result(
            short_item, screen.short_query(raw, "A", 7, 7, 100000)
        )

        game_item = {
            "definition_hash": identity,
            "policy_a": "T2",
            "policy_b": "T2",
            "seed": 7,
            "max_nodes_per_role": 100000,
        }
        screen.validate_game_result(
            game_item,
            screen.play_adapter.play_one(raw, "T2", "T2", 7, 100000),
            row,
        )

        exact_item = {"definition_hash": identity, "max_states": 100000}
        screen.validate_exact_result(
            exact_item, screen.exact_one(raw, 100000), row
        )

    def test_policy_gate_boundaries_and_goal_roles(self):
        results = []
        for profile in screen.POLICY_ORDER:
            for index, winner in enumerate(("A", "B", "A", "B")):
                results.append(({"profile": profile}, {"winner": winner, "terminal_reason": "GOAL" if index < 2 else "NO_LEGAL_ACTION"}))
        self.assertTrue(screen._policy_gate(results)["passed"])
        for _item, result in results:
            result["terminal_reason"] = "NO_LEGAL_ACTION"
        self.assertFalse(screen._policy_gate(results)["passed"])
        for item, result in results:
            if item["profile"] == "T2_T2":
                result.update(winner="A", terminal_reason="GOAL")
        self.assertFalse(screen._policy_gate(results)["passed"])

    def test_fifo_bfs_tiny_and_digest_collision(self):
        result = screen.bfs_prefix(tiny(), 1000, 8)
        self.assertIn(result["status"], ("PREFIX_LIMIT_REACHED", "EXHAUSTED"))
        self.assertEqual(result["seen_states"], len(result["state_digests"]))
        self.assertEqual(len(result["state_digests"]), len(set(result["state_digests"])))
        self.assertEqual(result["stored_edges"], 0)
        self.assertGreater(result["terminal_states"], 0)
        if result["status"] == "EXHAUSTED":
            self.assertEqual(result["expanded_states"] + result["terminal_states"], result["seen_states"])
        with mock.patch.object(screen, "_state_digest", return_value="0" * 64):
            collision = screen.bfs_prefix(tiny(), 10, 8)
        self.assertEqual(collision["status"], "FAILED")
        self.assertIn("share a saved digest", collision["error"]["message"])

    def test_bfs_rejects_ply_limit_and_winnerless_terminal(self):
        capped = tiny()
        capped["max_plies"] = 2
        capped = json.loads(canonical_json(parse_definition(capped)))
        ply_limit = screen.bfs_prefix(capped, 20, 8)
        self.assertEqual(ply_limit["status"], "FAILED")
        self.assertIn("PLY_LIMIT", ply_limit["error"]["message"])

        def winnerless(_definition, state, _action):
            return GameState(
                ply=state.ply + 1,
                to_move=state.to_move.other,
                pieces=state.pieces,
                outcome=Outcome(winner=None, reason="NO_LEGAL_ACTION"),
            )

        with mock.patch.object(screen, "apply_action", side_effect=winnerless):
            draw = screen.bfs_prefix(tiny(), 10, 8)
        self.assertEqual(draw["status"], "FAILED")
        self.assertIn("winnerless", draw["error"]["message"])

    def run_cascade(self, *, short=None, game=None, exact=None, bfs=None):
        proposal = fake_proposal()
        attempts = []
        records = []
        with mock.patch.object(screen, "BFS_STOP", 5):
            result = screen.execute_cascade(
                proposal,
                source_digest="s" * 64,
                before_attempt=lambda item: attempts.append(item),
                after_result=lambda _item, record: records.append(record),
                check_source=lambda: None,
                short_runner=short or (lambda *args: short_result(proposal, *args)),
                game_runner=game or (lambda *args: game_result(proposal, *args)),
                exact_runner=exact or (lambda *args: unknown_exact(proposal, *args)),
                bfs_runner=bfs or (lambda *args: bfs_result(proposal, *args)),
            )
        self.assertEqual((len(attempts), len(records)), (56, 56))
        return proposal, result, records

    def test_happy_cascade_calls_every_slot_and_fixed_rank(self):
        calls = Counter()
        proposal = fake_proposal()

        def short(*args):
            calls["short"] += 1
            return short_result(proposal, *args)

        def game(*args):
            calls["game"] += 1
            return game_result(proposal, *args)

        def exact(*args):
            calls["exact"] += 1
            return unknown_exact(proposal, *args)

        def bfs(*args):
            calls["bfs"] += 1
            return bfs_result(proposal, *args)

        _proposal, (records, dispositions, failure), emitted = self.run_cascade(short=short, game=game, exact=exact, bfs=bfs)
        self.assertIsNone(failure)
        self.assertEqual(calls, {"short": 16, "game": 32, "exact": 4, "bfs": 4})
        self.assertEqual(dispositions[1], "PRESELECTED_TECHNICAL_ACCEPTANCE_PENDING")
        self.assertEqual([dispositions[index] for index in (2, 3, 4)], ["NOT_SELECTED_FIXED_RANK"] * 3)
        self.assertEqual(records, emitted)
        summary = screen.summarize(records, dispositions)
        self.assertFalse(summary["human_review_eligible"])
        self.assertNotIn("state_digests", json.dumps(summary))

    def test_short_force_and_cap_close_second_target_and_later_stages(self):
        proposal = fake_proposal()
        short_calls = Counter()

        def short(raw, target, ply, seed, cap):
            cell = raw["synthetic_cell"]
            short_calls[cell] += 1
            if cell == 1:
                return short_result(proposal, raw, target, ply, seed, cap, [1, 1])
            if cell == 2:
                return censored_short(proposal, raw, target, ply, seed, cap)
            return short_result(proposal, raw, target, ply, seed, cap)

        _proposal, (records, dispositions, failure), _emitted = self.run_cascade(short=short)
        self.assertIsNone(failure)
        self.assertEqual(short_calls[1], 1)
        self.assertEqual(short_calls[2], 1)
        self.assertEqual(dispositions[1], "NOT_SELECTED_SHORT_FORCED_WIN")
        self.assertEqual(dispositions[2], "NOT_SELECTED_EVIDENCE_INCOMPLETE")
        cell1 = [record for record in records if record["scheduled"]["cell"] == 1]
        self.assertEqual(sum(record["status"] == "NOT_STARTED_GATE_CLOSED" for record in cell1), 13)

    def test_policy_miss_still_finishes_eight_games(self):
        proposal = fake_proposal()
        calls = Counter()

        def game(raw, *args):
            calls[raw["synthetic_cell"]] += 1
            return game_result(
                proposal,
                raw,
                *args,
                winner="A" if raw["synthetic_cell"] == 1 else None,
            )

        _proposal, (_records, dispositions, failure), _emitted = self.run_cascade(game=game)
        self.assertIsNone(failure)
        self.assertEqual(calls[1], 8)
        self.assertEqual(dispositions[1], "NOT_SELECTED_POLICY_GATE")

    def test_exact_malformed_is_global_technical_stop(self):
        proposal = fake_proposal()

        def exact(raw, cap):
            result = complete_exact(proposal, raw, cap)
            if raw["synthetic_cell"] == 1:
                result["actual_result"]["terminal_reason"] = "PLY_LIMIT"
            return result

        _proposal, (records, _dispositions, failure), _emitted = self.run_cascade(exact=exact)
        self.assertEqual(failure["stage"], "EXACT")
        self.assertEqual(records[40]["status"], "FAILED_TECHNICAL")
        self.assertTrue(all(record["status"] == "NOT_STARTED_FAILURE" for record in records[41:]))
        records[40]["error"] = {}
        with self.assertRaises(ValueError):
            screen.classify_saved_records(
                proposal, records, external_failure=failure
            )

    def test_bfs_exhaustion_after_exact_unknown_is_technical(self):
        proposal = fake_proposal()

        def bfs(raw, stop, maximum):
            return bfs_result(proposal, raw, stop, maximum, exhausted=True)

        _proposal, (records, _dispositions, failure), _emitted = self.run_cascade(bfs=bfs)
        self.assertEqual(failure["type"], "ExactBfsStateModelContradiction")
        self.assertEqual(records[44]["status"], "FAILED_TECHNICAL")
        self.assertTrue(all(record["status"] == "NOT_STARTED_FAILURE" for record in records[45:]))

    def test_malformed_bfs_failure_still_has_a_safe_summary(self):
        def malformed(_raw, _stop, _maximum):
            return {"status": "PREFIX_LIMIT_REACHED", "transitions": 3}

        _proposal, (records, dispositions, failure), _emitted = self.run_cascade(bfs=malformed)
        self.assertEqual(failure["stage"], "BFS_PREFIX")
        summary = screen.summarize(records, dispositions, failure)
        self.assertEqual(summary["execution_status"], "FAILED_TECHNICAL")
        self.assertEqual(summary["resource_usage"]["bfs_transitions"], 3)
        self.assertIsNone(summary["candidates"][0]["bfs"])

    def test_game_failure_is_technical_not_unknown(self):
        proposal = fake_proposal()
        calls = 0

        def failed_game(*args):
            nonlocal calls
            calls += 1
            return {"status": "FAILED"}

        _proposal, (records, _dispositions, failure), _emitted = self.run_cascade(game=failed_game)
        self.assertEqual(calls, 1)
        self.assertEqual(failure["stage"], "POLICY_GAMES")
        self.assertEqual(records[8]["status"], "FAILED_TECHNICAL")
        self.assertTrue(all(record["status"] == "NOT_STARTED_FAILURE" for record in records[9:]))

    def test_publisher_measures_final_envelope_before_publish(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            publisher = screen._Publisher(output)
            with self.assertRaises(ValueError):
                publisher.publish("oversize.json", {"value": "x" * screen.MAX_OTHER_BYTES})
            self.assertFalse((output / "oversize.json").exists())
            self.assertEqual(publisher.facts()["files"], 0)

    def test_bootstrap_publication_pre_and_post_write_closes_without_runners(self):
        proposal = fake_proposal()
        real_publish = screen._publish
        for target in ("run-attempt.json", "manifest.json"):
            for post_write in (False, True):
                with self.subTest(target=target, post_write=post_write):
                    failed = False
                    attempted_payloads = []
                    calls = Counter()

                    def forbidden(kind):
                        def invoke(*_args):
                            calls[kind] += 1
                            raise AssertionError("bootstrap failure started production")

                        return invoke

                    def flaky(path, value):
                        nonlocal failed
                        if path.name == target:
                            attempted_payloads.append(screen.canonical_bytes(value))
                            if not failed:
                                failed = True
                                if post_write:
                                    real_publish(path, value)
                                raise OSError("synthetic bootstrap publication failure")
                        return real_publish(path, value)

                    with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
                        output = Path(temporary) / "run"
                        self.patch_mocked_run(
                            stack,
                            proposal,
                            short=forbidden("short"),
                            game=forbidden("game"),
                            exact=forbidden("exact"),
                            bfs=forbidden("bfs"),
                            publish=flaky,
                        )
                        summary = screen.run_pilot(
                            REPOSITORY, "a" * 40, output
                        )
                        self.assertEqual(
                            summary["execution_status"], "FAILED_TECHNICAL"
                        )
                        self.assertEqual(calls, {})
                        self.assertEqual(
                            len(attempted_payloads), 1 if post_write else 2
                        )
                        self.assertEqual(
                            len(set(attempted_payloads)), 1
                        )
                        results = [
                            screen.read_json(
                                output
                                / "attempts/{:04d}-result.json".format(index)
                            )
                            for index in range(56)
                        ]
                        self.assertTrue(
                            all(
                                row["status"] == "NOT_STARTED_FAILURE"
                                for row in results
                            )
                        )
                        self.assertEqual(
                            screen.audit_run(
                                REPOSITORY, "a" * 40, output
                            )["status"],
                            "PASS",
                        )

    def test_run_timestamp_failure_precedes_output_and_attempt_timestamp_recovers(self):
        proposal = fake_proposal()
        with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
            output = Path(temporary) / "no-output"
            self.patch_mocked_run(stack, proposal)
            stack.enter_context(
                mock.patch.object(
                    screen, "_utc", side_effect=ValueError("synthetic clock failure")
                )
            )
            with self.assertRaises(ValueError):
                screen.run_pilot(REPOSITORY, "a" * 40, output)
            self.assertFalse(output.exists())

        utc_calls = 0
        short_calls = 0

        def flaky_utc():
            nonlocal utc_calls
            utc_calls += 1
            if utc_calls == 2:
                raise OSError("synthetic attempt timestamp failure")
            return "2026-09-08T00:00:{:02d}Z".format(utc_calls)

        def forbidden_short(*_args):
            nonlocal short_calls
            short_calls += 1
            raise AssertionError("timestamp failure started production")

        with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
            output = Path(temporary) / "recovered"
            self.patch_mocked_run(stack, proposal, short=forbidden_short)
            stack.enter_context(mock.patch.object(screen, "_utc", side_effect=flaky_utc))
            summary = screen.run_pilot(REPOSITORY, "a" * 40, output)
            self.assertEqual(short_calls, 0)
            self.assertEqual(summary["execution_status"], "FAILED_TECHNICAL")
            results = [
                screen.read_json(output / "attempts/{:04d}-result.json".format(index))
                for index in range(56)
            ]
            self.assertTrue(
                all(row["status"] == "NOT_STARTED_FAILURE" for row in results)
            )
            self.assertEqual(
                screen.audit_run(REPOSITORY, "a" * 40, output)["status"], "PASS"
            )

    def test_huge_runner_exception_is_bounded_closed_and_auditable(self):
        proposal = fake_proposal()
        message = "x" * (screen.MAX_OTHER_BYTES + 17)

        def huge_error(*_args):
            raise ValueError(message)

        with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
            output = Path(temporary) / "run"
            self.patch_mocked_run(stack, proposal, short=huge_error)
            summary = screen.run_pilot(REPOSITORY, "a" * 40, output)
            self.assertEqual(summary["execution_status"], "FAILED_TECHNICAL")
            self.assertEqual(
                len(list((output / "attempts").glob("*-result.json"))), 56
            )
            failure = screen.read_json(output / "failure.json")
            self.assertEqual(
                failure["message_truncated"]["original_bytes"],
                len(message.encode("utf-8")),
            )
            self.assertEqual(
                failure["message_truncated"]["sha256"],
                hashlib.sha256(message.encode("utf-8")).hexdigest(),
            )
            for path in output.rglob("*"):
                if path.is_file():
                    limit = (
                        screen.MAX_BFS_BYTES
                        if path.name.endswith("-result.json")
                        and "0044" <= path.name[:4] <= "0047"
                        else screen.MAX_OTHER_BYTES
                    )
                    self.assertLessEqual(len(path.read_bytes()), limit)
            self.assertEqual(
                screen.audit_run(REPOSITORY, "a" * 40, output)["status"], "PASS"
            )

    def test_mocked_run_publishes_all_56_pairs_and_read_only_audit(self):
        proposal = fake_proposal()
        source = {
            "git_commit": "a" * 40,
            "plan": screen.PLAN,
            "proposal": screen.DATA,
            "design_record": screen.DESIGN_DATA,
            "source_sha256": {"synthetic.py": "b" * 64},
        }
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "run"
            patches = (
                mock.patch.object(screen, "BFS_STOP", 5),
                mock.patch.object(screen, "source_snapshot", return_value=source),
                mock.patch.object(screen, "load_proposal", return_value=proposal),
                mock.patch.object(screen, "dependency_snapshot", return_value={"synthetic": {"file_sha256": "b" * 64}}),
                mock.patch.object(screen, "short_query", side_effect=lambda *args: short_result(proposal, *args)),
                mock.patch.object(screen.play_adapter, "play_one", side_effect=lambda *args: game_result(proposal, *args)),
                mock.patch.object(screen, "exact_one", side_effect=lambda *args: unknown_exact(proposal, *args)),
                mock.patch.object(screen, "bfs_prefix", side_effect=lambda *args: bfs_result(proposal, *args)),
            )
            for patcher in patches:
                patcher.start()
            try:
                summary = screen.run_pilot(REPOSITORY, "a" * 40, output)
                self.assertEqual(summary["execution_status"], "COMPLETE")
                files = [path for path in output.rglob("*") if path.is_file()]
                self.assertEqual(len(files), 116)
                audited = screen.audit_run(REPOSITORY, "a" * 40, output)
                self.assertEqual(audited["status"], "PASS")
                self.assertEqual(audited["production_calls"], 0)
                summary_path = output / "summary.json"
                original_summary = summary_path.read_bytes()
                fabricated = screen.read_json(summary_path)
                fabricated["failure"] = {
                    "type": "Fabricated",
                    "message": "not backed by failure.json",
                }
                fabricated["execution_status"] = "FAILED_TECHNICAL"
                fabricated["scientific_disposition"] = "FAILED_TECHNICAL"
                rewrite_envelope(summary_path, fabricated)
                with self.assertRaises(ValueError):
                    screen.audit_run(REPOSITORY, "a" * 40, output)
                summary_path.write_bytes(original_summary)
                verification_path = output / "source-verification.json"
                verification_bytes = verification_path.read_bytes()
                verification_path.unlink()
                with self.assertRaises(ValueError):
                    screen.audit_run(REPOSITORY, "a" * 40, output)
                verification_path.write_bytes(verification_bytes)

                manifest_path = output / "manifest.json"
                manifest_bytes = manifest_path.read_bytes()
                manifest = screen.read_json(manifest_path)
                manifest["protocol"] = "semantic-tamper"
                rewrite_envelope(manifest_path, manifest)
                verification = screen.read_json(verification_path)
                verification["publication_sha256"]["manifest.json"] = (
                    hashlib.sha256(manifest_path.read_bytes()).hexdigest()
                )
                rewrite_envelope(verification_path, verification)
                with self.assertRaises(ValueError):
                    screen.audit_run(REPOSITORY, "a" * 40, output)
                manifest_path.write_bytes(manifest_bytes)
                verification_path.write_bytes(verification_bytes)
            finally:
                for patcher in reversed(patches):
                    patcher.stop()

    def test_oversize_result_is_compact_technical_and_all_slots_close(self):
        proposal = fake_proposal()

        def oversized(*args):
            result = short_result(proposal, *args)
            result["untrusted_padding"] = "x" * screen.MAX_OTHER_BYTES
            return result

        with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
            output = Path(temporary) / "run"
            self.patch_mocked_run(stack, proposal, short=oversized)
            summary = screen.run_pilot(REPOSITORY, "a" * 40, output)
            self.assertEqual(summary["execution_status"], "FAILED_TECHNICAL")
            results = [
                screen.read_json(output / "attempts/{:04d}-result.json".format(index))
                for index in range(56)
            ]
            self.assertEqual(results[0]["status"], "FAILED_TECHNICAL")
            self.assertIsNone(results[0]["result"])
            self.assertEqual(results[0]["error"]["type"], "PublicationEnvelopeTooLarge")
            self.assertTrue(all(row["status"] == "NOT_STARTED_FAILURE" for row in results[1:]))
            self.assertNotIn("untrusted_padding", json.dumps(screen.read_json(output / "failure.json")))
            self.assertEqual(screen.audit_run(REPOSITORY, "a" * 40, output)["status"], "PASS")

    def test_one_shot_publisher_error_recovers_pairs_and_audits(self):
        proposal = fake_proposal()
        real_publish = screen._publish
        calls = 0

        def flaky(path, value):
            nonlocal calls
            if path.name == "0000-attempt.json" and calls == 0:
                calls += 1
                raise OSError("synthetic one-shot publication failure")
            return real_publish(path, value)

        with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
            output = Path(temporary) / "run"
            self.patch_mocked_run(stack, proposal, publish=flaky)
            summary = screen.run_pilot(REPOSITORY, "a" * 40, output)
            self.assertEqual(summary["execution_status"], "FAILED_TECHNICAL")
            self.assertEqual(len(list((output / "attempts").glob("*-attempt.json"))), 56)
            self.assertEqual(len(list((output / "attempts").glob("*-result.json"))), 56)
            self.assertEqual(screen.audit_run(REPOSITORY, "a" * 40, output)["status"], "PASS")

    def test_failure_artifact_publication_pre_and_post_write_audits(self):
        proposal = fake_proposal()
        real_publish = screen._publish
        for post_write in (False, True):
            with self.subTest(post_write=post_write):
                failed = False
                calls = 0

                def malformed_short(*_args):
                    nonlocal calls
                    calls += 1
                    return {"status": "FAILED"}

                def flaky(path, value):
                    nonlocal failed
                    if path.name == "failure.json" and not failed:
                        failed = True
                        if post_write:
                            real_publish(path, value)
                        raise OSError(
                            "synthetic failure-artifact publication failure"
                        )
                    return real_publish(path, value)

                with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
                    output = Path(temporary) / "run"
                    self.patch_mocked_run(
                        stack, proposal, short=malformed_short, publish=flaky
                    )
                    summary = screen.run_pilot(REPOSITORY, "a" * 40, output)
                    self.assertEqual(calls, 1)
                    self.assertEqual(summary["execution_status"], "FAILED_TECHNICAL")
                    self.assertIn("FAILURE_PUBLICATION", json.dumps(summary["failure"]))
                    saved_failure = screen.read_json(output / "failure.json")
                    self.assertEqual(
                        saved_failure == summary["failure"], not post_write
                    )
                    self.assertEqual(
                        screen.audit_run(REPOSITORY, "a" * 40, output)["status"],
                        "PASS",
                    )

    def test_publication_failure_after_prior_technical_stop_audits(self):
        proposal = fake_proposal()
        real_publish = screen._publish
        for target in ("0001-attempt.json", "0001-result.json"):
            for post_write in (False, True):
                with self.subTest(target=target, post_write=post_write):
                    failed = False

                    def malformed_short(*_args):
                        return {"status": "FAILED"}

                    def flaky(path, value):
                        nonlocal failed
                        if path.name == target and not failed:
                            failed = True
                            if post_write:
                                real_publish(path, value)
                            raise OSError(
                                "synthetic closure publication failure"
                            )
                        return real_publish(path, value)

                    with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
                        output = Path(temporary) / "run"
                        self.patch_mocked_run(
                            stack,
                            proposal,
                            short=malformed_short,
                            publish=flaky,
                        )
                        summary = screen.run_pilot(
                            REPOSITORY, "a" * 40, output
                        )
                        self.assertEqual(
                            summary["execution_status"], "FAILED_TECHNICAL"
                        )
                        results = [
                            screen.read_json(
                                output
                                / "attempts/{:04d}-result.json".format(index)
                            )
                            for index in range(56)
                        ]
                        self.assertEqual(results[0]["status"], "FAILED_TECHNICAL")
                        self.assertTrue(
                            all(
                                row["status"] == "NOT_STARTED_FAILURE"
                                for row in results[1:]
                            )
                        )
                        self.assertEqual(
                            screen.audit_run(
                                REPOSITORY, "a" * 40, output
                            )["status"],
                            "PASS",
                        )

    def test_audit_rejects_unanchored_failure_and_wrong_publication_locus(self):
        proposal = fake_proposal()

        def replace_failure_and_summary(output, failure):
            failure_path = output / "failure.json"
            rewrite_envelope(failure_path, failure)
            records = [
                screen.read_json(
                    output / "attempts/{:04d}-result.json".format(index)
                )
                for index in range(56)
            ]
            dispositions = screen.classify_saved_records(
                proposal, records, external_failure=failure
            )[0]
            before = {
                str(path.relative_to(output))
                for path in output.rglob("*")
                if path.is_file() and path.name != "summary.json"
            }
            publication = {
                "files_before_summary": len(before),
                "bytes_before_summary": sum(
                    len((output / name).read_bytes()) for name in before
                ),
                "maximum_files": screen.MAX_FILES,
                "maximum_bytes": screen.MAX_PUBLISHED_BYTES,
            }
            rewrite_envelope(
                output / "summary.json",
                screen.summarize(
                    records, dispositions, failure, publication=publication
                ),
            )

        with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
            output = Path(temporary) / "healthy"
            self.patch_mocked_run(stack, proposal)
            screen.run_pilot(REPOSITORY, "a" * 40, output)
            replace_failure_and_summary(
                output, {"type": "Fabricated", "message": "no recorded event"}
            )
            with self.assertRaises(ValueError):
                screen.audit_run(REPOSITORY, "a" * 40, output)

        real_publish = screen._publish
        failed = False

        def flaky(path, value):
            nonlocal failed
            if path.name == "0000-attempt.json" and not failed:
                failed = True
                raise OSError("synthetic attempt publication failure")
            return real_publish(path, value)

        with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
            output = Path(temporary) / "wrong-locus"
            self.patch_mocked_run(stack, proposal, publish=flaky)
            screen.run_pilot(REPOSITORY, "a" * 40, output)
            failure = screen.read_json(output / "failure.json")
            failure["publication_context"]["ordinal"] = 5
            replace_failure_and_summary(output, failure)
            with self.assertRaises(ValueError):
                screen.audit_run(REPOSITORY, "a" * 40, output)

    def test_post_write_result_error_keeps_locus_and_closes_remaining_slots(self):
        proposal = fake_proposal()
        real_publish = screen._publish
        failed = False
        short_calls = 0

        def short(*args):
            nonlocal short_calls
            short_calls += 1
            return short_result(proposal, *args)

        def flaky(path, value):
            nonlocal failed
            if path.name == "0000-result.json" and not failed:
                failed = True
                real_publish(path, value)
                raise OSError("synthetic post-write result publication failure")
            return real_publish(path, value)

        with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
            output = Path(temporary) / "run"
            self.patch_mocked_run(stack, proposal, short=short, publish=flaky)
            summary = screen.run_pilot(REPOSITORY, "a" * 40, output)
            self.assertEqual(summary["execution_status"], "FAILED_TECHNICAL")
            results = [
                screen.read_json(output / "attempts/{:04d}-result.json".format(index))
                for index in range(56)
            ]
            self.assertEqual(results[0]["status"], "COMPLETE")
            self.assertTrue(
                all(row["status"] == "NOT_STARTED_FAILURE" for row in results[1:])
            )
            self.assertEqual(short_calls, 1)
            failure = screen.read_json(output / "failure.json")
            context = failure["publication_context"]
            self.assertEqual(context, {"phase": "RESULT_PUBLICATION", "ordinal": 0})
            self.assertEqual(screen.audit_run(REPOSITORY, "a" * 40, output)["status"], "PASS")

    def test_gate_closure_publication_failure_pre_and_post_write_audits(self):
        proposal = fake_proposal()
        real_publish = screen._publish

        def short(raw, target, target_ply, seed, cap):
            values = [1, 1] if raw["synthetic_cell"] == 1 else None
            return short_result(
                proposal, raw, target, target_ply, seed, cap, values
            )

        for post_write in (False, True):
            with self.subTest(post_write=post_write):
                failed = False

                def flaky(path, value):
                    nonlocal failed
                    if path.name == "0001-result.json" and not failed:
                        failed = True
                        if post_write:
                            real_publish(path, value)
                        raise OSError(
                            "synthetic gate-closure publication failure"
                        )
                    return real_publish(path, value)

                with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
                    output = Path(temporary) / "run"
                    self.patch_mocked_run(
                        stack, proposal, short=short, publish=flaky
                    )
                    summary = screen.run_pilot(REPOSITORY, "a" * 40, output)
                    self.assertEqual(summary["execution_status"], "FAILED_TECHNICAL")
                    results = [
                        screen.read_json(
                            output
                            / "attempts/{:04d}-result.json".format(index)
                        )
                        for index in range(56)
                    ]
                    self.assertEqual(
                        results[1]["status"],
                        (
                            "NOT_STARTED_GATE_CLOSED"
                            if post_write
                            else "FAILED_TECHNICAL"
                        ),
                    )
                    self.assertTrue(
                        all(
                            row["status"] == "NOT_STARTED_FAILURE"
                            for row in results[2:]
                        )
                    )
                    self.assertEqual(
                        screen.audit_run(REPOSITORY, "a" * 40, output)["status"],
                        "PASS",
                    )

    def test_summary_publication_failure_topology_audits(self):
        proposal = fake_proposal()
        original = screen._Publisher.publish
        failed = False

        def flaky_summary(self, name, value, *, bfs=False):
            nonlocal failed
            if name == "summary.json" and not failed:
                failed = True
                raise OSError("synthetic summary failure")
            return original(self, name, value, bfs=bfs)

        with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
            output = Path(temporary) / "run"
            self.patch_mocked_run(stack, proposal)
            stack.enter_context(mock.patch.object(screen._Publisher, "publish", new=flaky_summary))
            summary = screen.run_pilot(REPOSITORY, "a" * 40, output)
            self.assertEqual(summary["execution_status"], "FAILED_TECHNICAL")
            self.assertFalse((output / "summary.json").exists())
            self.assertTrue((output / "summary-publication-failure.json").exists())
            self.assertEqual(screen.audit_run(REPOSITORY, "a" * 40, output)["status"], "PASS")

    def test_post_write_summary_failure_topology_audits(self):
        proposal = fake_proposal()
        real_publish = screen._publish
        failed = False

        def flaky(path, value):
            nonlocal failed
            if path.name == "summary.json" and not failed:
                failed = True
                real_publish(path, value)
                raise OSError("synthetic post-write summary publication failure")
            return real_publish(path, value)

        with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
            output = Path(temporary) / "run"
            self.patch_mocked_run(stack, proposal, publish=flaky)
            summary = screen.run_pilot(REPOSITORY, "a" * 40, output)
            self.assertEqual(summary["execution_status"], "FAILED_TECHNICAL")
            self.assertTrue((output / "summary.json").exists())
            self.assertTrue((output / "summary-publication-failure.json").exists())
            self.assertEqual(screen.audit_run(REPOSITORY, "a" * 40, output)["status"], "PASS")

    def test_fallback_summary_publication_pre_and_post_write_audits(self):
        proposal = fake_proposal()
        original_publish = screen._Publisher.publish
        real_publish = screen._publish
        for post_write in (False, True):
            with self.subTest(post_write=post_write):
                primary_failed = False
                fallback_failed = False

                def fail_primary(self, name, value, *, bfs=False):
                    nonlocal primary_failed
                    if name == "summary.json" and not primary_failed:
                        primary_failed = True
                        raise OSError("synthetic primary-summary failure")
                    return original_publish(self, name, value, bfs=bfs)

                def fail_fallback(path, value):
                    nonlocal fallback_failed
                    if (
                        path.name == "summary-publication-failure.json"
                        and not fallback_failed
                    ):
                        fallback_failed = True
                        if post_write:
                            real_publish(path, value)
                        raise OSError("synthetic fallback-summary failure")
                    return real_publish(path, value)

                with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
                    output = Path(temporary) / "run"
                    self.patch_mocked_run(stack, proposal, publish=fail_fallback)
                    stack.enter_context(
                        mock.patch.object(
                            screen._Publisher, "publish", new=fail_primary
                        )
                    )
                    summary = screen.run_pilot(REPOSITORY, "a" * 40, output)
                    self.assertEqual(summary["execution_status"], "FAILED_TECHNICAL")
                    self.assertTrue(
                        (output / "summary-publication-failure.json").exists()
                    )
                    if not post_write:
                        self.assertIn(
                            "SUMMARY_FALLBACK_PUBLICATION",
                            json.dumps(summary["failure"]),
                        )
                    self.assertEqual(
                        screen.audit_run(REPOSITORY, "a" * 40, output)["status"],
                        "PASS",
                    )

    def test_source_verification_publication_failure_closes_and_audits(self):
        proposal = fake_proposal()
        real_publish = screen._publish
        for post_write in (False, True):
            with self.subTest(post_write=post_write):
                failed = False

                def flaky(path, value):
                    nonlocal failed
                    if path.name == "source-verification.json" and not failed:
                        failed = True
                        if post_write:
                            real_publish(path, value)
                        raise OSError(
                            "synthetic source-verification publication failure"
                        )
                    return real_publish(path, value)

                with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
                    output = Path(temporary) / "run"
                    self.patch_mocked_run(stack, proposal, publish=flaky)
                    summary = screen.run_pilot(REPOSITORY, "a" * 40, output)
                    self.assertEqual(summary["execution_status"], "FAILED_TECHNICAL")
                    self.assertEqual(
                        (output / "source-verification.json").exists(), post_write
                    )
                    self.assertEqual(
                        len(list((output / "attempts").glob("*-attempt.json"))), 56
                    )
                    self.assertEqual(
                        len(list((output / "attempts").glob("*-result.json"))), 56
                    )
                    self.assertEqual(
                        screen.audit_run(REPOSITORY, "a" * 40, output)["status"],
                        "PASS",
                    )


if __name__ == "__main__":
    unittest.main()
