"""Four hand-solved graph controls and falsified proof certificates; no original search."""

from copy import deepcopy
from unittest.mock import patch
import unittest

from parity_forge.cut_choose import Definition, State, apply_action, legal_actions, terminal
from parity_forge.cut_choose_search import BudgetExceeded, solve, verify_proof


CHAIN = Definition("chain", 3, ((0, 1), (1, 2)), (0,), (2,))
DIRECT = Definition("direct", 4, ((0, 1), (2, 3)), (0,), (1,))
DIAMOND = Definition("diamond", 4, ((0, 1), (0, 2), (1, 3), (2, 3)), (0,), (3,))
DIRECT4 = Definition("direct4", 4, ((0, 1), (0, 2), (1, 2), (2, 3)), (0,), (1,))


def reference_winner(definition, state=State()):
    winner = terminal(definition, state)
    if winner is not None:
        return winner
    actor = "B" if state.pending else "A"
    values = [reference_winner(definition, apply_action(definition, state, action))
              for action in legal_actions(definition, state)]
    return actor if actor in values else ("A" if actor == "B" else "B")


class CutChooseSearchTests(unittest.TestCase):
    def test_exact_winners_match_hand_truth_and_separate_phase_tree(self):
        for definition, winner in ((CHAIN, "A"), (DIRECT, "B"),
                                   (DIAMOND, "A"), (DIRECT4, "B")):
            with self.subTest(definition=definition.id):
                result = solve(definition, 10000, 100000)
                self.assertEqual(result["status"], "COMPLETE")
                self.assertEqual(result["winner"], winner)
                self.assertEqual(result["winner"], reference_winner(definition))
                receipt = verify_proof(definition, result["proof"])
                self.assertEqual(receipt["status"], "PASS")
                self.assertLessEqual(receipt["arcs"], result["proof_arcs"])

    def test_a_has_both_choices_and_b_all_offers(self):
        a = solve(CHAIN, 100, 100)["proof"]
        self.assertEqual(len(a["nodes"]["0:0"]["replies"]), 2)
        self.assertEqual({r["keep"] for r in a["nodes"]["0:0"]["replies"]}, {0, 1})
        b = solve(DIRECT4, 100, 1000)["proof"]
        replies = b["nodes"]["0:0"]["replies"]
        self.assertEqual(len(replies), 6)
        self.assertEqual({tuple(r["offer"]) for r in replies},
                         set(legal_actions(DIRECT4, State())))

    def test_zero_node_and_transition_budgets_never_fake_winner(self):
        for nodes, transitions, reason, used in ((0, 100, "NODE_LIMIT", 0),
                                                (10, 0, "TRANSITION_LIMIT", 1)):
            result = solve(DIAMOND, nodes, transitions)
            self.assertEqual(result["status"], "UNKNOWN")
            self.assertEqual(result["reason"], reason)
            self.assertIsNone(result["winner"])
            self.assertIsNone(result["proof"])
            self.assertEqual(result["nodes"], used)
            self.assertEqual(result["transitions"], 0)

    def test_exact_budget_boundaries_and_determinism(self):
        full = solve(DIAMOND, 10000, 100000)
        again = solve(DIAMOND, full["nodes"], full["transitions"], full["proof_arcs"])
        self.assertEqual(full, again)
        for kwargs in ({"node_limit": full["nodes"] - 1},
                       {"transition_limit": full["transitions"] - 1},
                       {"proof_arc_limit": full["proof_arcs"] - 1}):
            limits = dict(node_limit=10000, transition_limit=100000, proof_arc_limit=1000000)
            limits.update(kwargs)
            result = solve(DIAMOND, **limits)
            self.assertEqual(result["status"], "UNKNOWN")
            self.assertIsNone(result["proof"])
            self.assertLessEqual(result["nodes"], limits["node_limit"])
            self.assertLessEqual(result["transitions"], limits["transition_limit"])
            self.assertLessEqual(result["proof_arcs"], limits["proof_arc_limit"])

    def test_invalid_limits_and_cpu(self):
        for value in (-1, True, 1.0):
            for field in ("node_limit", "transition_limit", "proof_arc_limit"):
                limits = dict(node_limit=100, transition_limit=100, proof_arc_limit=100)
                limits[field] = value
                with self.assertRaises(ValueError):
                    solve(CHAIN, **limits)
        for value in (0, -1, True, float("inf"), float("nan")):
            with self.assertRaises(ValueError):
                solve(CHAIN, 100, 100, cpu_seconds=value)

    def test_temporary_replies_charge_arc_budget_before_later_node_exhaustion(self):
        result = solve(DIRECT4, 1, 100, proof_arc_limit=0)
        self.assertEqual(result["reason"], "PROOF_ARC_LIMIT")
        self.assertEqual(result["nodes"], 1)
        self.assertEqual(result["transitions"], 1)
        self.assertEqual(result["proof_arcs"], 0)

    def test_cpu_expiring_at_checker_handoff_remains_unknown(self):
        with patch("parity_forge.cut_choose_search._clock"), \
                patch("parity_forge.cut_choose_search.time.process_time", side_effect=[0, 2]), \
                patch("parity_forge.cut_choose_search.verify_proof") as checker:
            result = solve(CHAIN, 100, 100, cpu_seconds=1)
        self.assertEqual(result["reason"], "CPU_LIMIT")
        self.assertIsNone(result["winner"])
        checker.assert_not_called()

    def test_cpu_limit_is_unknown_in_search_and_exception_in_checker(self):
        with patch("parity_forge.cut_choose_search.time.process_time", side_effect=[0, 2]):
            result = solve(CHAIN, 100, 100, cpu_seconds=1)
        self.assertEqual(result["reason"], "CPU_LIMIT")
        self.assertIsNone(result["winner"])
        proof = solve(CHAIN, 100, 100)["proof"]
        with patch("parity_forge.cut_choose_search.time.process_time", side_effect=[0, 2]):
            with self.assertRaises(BudgetExceeded) as error:
                verify_proof(CHAIN, proof, cpu_seconds=1)
        self.assertEqual(error.exception.reason, "CPU_LIMIT")

    def test_missing_duplicate_or_wrong_successor_rejected(self):
        for definition in (CHAIN, DIRECT4):
            original = solve(definition, 1000, 10000)["proof"]
            for mode in ("missing", "duplicate", "child", "keep", "order", "bool", "leaf"):
                proof = deepcopy(original)
                replies = proof["nodes"]["0:0"]["replies"]
                if mode == "missing": replies.pop()
                elif mode == "duplicate": replies.append(deepcopy(replies[0]))
                elif mode == "child": replies[0]["child"] = "0:0"
                elif mode == "keep": replies[0]["keep"] = 99
                elif mode == "order": replies[0]["offer"].reverse()
                elif mode == "bool": replies[0]["keep"] = False
                else: replies.clear()
                with self.subTest(graph=definition.id, mode=mode), self.assertRaises(ValueError):
                    verify_proof(definition, proof)

    def test_binding_orphan_false_winner_and_postterminal_rejected(self):
        original = solve(CHAIN, 100, 100)["proof"]
        for mode in ("hash", "root", "winner", "orphan", "postterminal", "noncanonical", "extra"):
            proof = deepcopy(original)
            terminal_key = next(k for k in proof["nodes"] if k != "0:0")
            if mode == "hash": proof["definition_hash"] = "bad"
            elif mode == "root": proof["root"] = "00:0"
            elif mode == "winner": proof["nodes"][terminal_key]["winner"] = "B"
            elif mode == "orphan": proof["nodes"]["3:0"] = {"winner": "A", "replies": []}
            elif mode == "postterminal":
                proof["nodes"][terminal_key]["replies"] = deepcopy(proof["nodes"]["0:0"]["replies"])
            elif mode == "noncanonical":
                proof["nodes"]["0:0"]["replies"][0]["child"] = "01:2"
            else: proof["nodes"]["0:0"]["extra"] = 1
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                verify_proof(CHAIN, proof)

    def test_checker_work_cap_and_no_solver_dependency(self):
        proof = solve(CHAIN, 100, 100)["proof"]
        with self.assertRaises(BudgetExceeded):
            verify_proof(CHAIN, proof, arc_limit=0)
        with patch("parity_forge.cut_choose_search.solve", side_effect=AssertionError("must not solve")), \
                patch("parity_forge.cut_choose_search.terminal", side_effect=AssertionError("independent terminal")):
            self.assertEqual(verify_proof(CHAIN, proof)["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
