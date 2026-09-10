"""Only the four frozen synthetic calibrations; never enumerate or play the original."""

from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch

from parity_forge.cut_choose import (
    Definition, State, apply_action, definition_hash, legal_actions, terminal,
)
from parity_forge import cut_choose_potential as potential
from parity_forge.cut_choose_search import BudgetExceeded


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


def single_leaf(definition, winner, kind):
    return {"format": potential.PROOF_FORMAT, "definition_hash": definition_hash(definition),
            "root": "0:0", "winner": winner,
            "nodes": {"0:0": {"winner": winner, "kind": kind, "replies": []}}}


class CutPotentialTests(unittest.TestCase):
    def test_complete_minimal_cut_families_match_hand_truth(self):
        for definition, expected in ((CHAIN, {1, 2}), (DIRECT, {1}),
                                     (DIAMOND, {3, 6, 9, 12}), (DIRECT4, {3, 5})):
            with self.subTest(definition=definition.id):
                self.assertEqual(set(potential._minimal_cuts(definition, float("inf"))), expected)
                self.assertEqual(set(potential._checker_cuts(definition, float("inf"))), expected)

    def test_strict_threshold_and_potential_leaf_node_charge(self):
        for definition in (DIRECT, DIRECT4):
            result = potential.solve(definition, 1, 0, proof_arc_limit=0)
            self.assertEqual(result["status"], "COMPLETE")
            self.assertEqual(result["winner"], "B")
            self.assertEqual(result["nodes"], 1)
            self.assertEqual(result["potential_checks"], 1)
            self.assertEqual(result["potential_leaves"], 1)
            self.assertEqual(result["transitions"], 0)
            self.assertEqual(result["proof_arcs"], 0)
            self.assertEqual(result["proof"]["nodes"]["0:0"]["kind"], "CUT_POTENTIAL")
            self.assertEqual(potential.verify_proof(definition, result["proof"], 0)
                             ["potential_leaves"], 1)
            unknown = potential.solve(definition, 0, 0, proof_arc_limit=0)
            self.assertEqual(unknown["reason"], "NODE_LIMIT")
            self.assertEqual(unknown["potential_checks"], 0)
        for definition in (CHAIN, DIAMOND):
            cuts = potential._minimal_cuts(definition, float("inf"))
            self.assertEqual(potential._potential(definition, State(), cuts, float("inf")),
                             1 << len(definition.edges))
            with self.assertRaises(ValueError):
                potential.verify_proof(definition, single_leaf(definition, "B", "CUT_POTENTIAL"))

    def test_calibrations_match_reference_and_are_deterministic(self):
        for definition, winner, cuts in ((CHAIN, "A", 2), (DIRECT, "B", 1),
                                         (DIAMOND, "A", 4), (DIRECT4, "B", 2)):
            result = potential.solve(definition, 10000, 100000)
            self.assertEqual(result["winner"], winner)
            self.assertEqual(result["status"], "COMPLETE")
            self.assertEqual(result["winner"], reference_winner(definition))
            self.assertEqual(result["cut_count"], cuts)
            self.assertEqual(result["potential_checks"], result["nodes"])
            self.assertEqual(result, potential.solve(definition, result["nodes"],
                              result["transitions"], result["proof_arcs"]))
            check = potential.verify_proof(definition, result["proof"])
            self.assertLessEqual(check["arcs"], result["proof_arcs"])
            self.assertLessEqual(check["potential_leaves"], result["potential_leaves"])

    def test_potential_average_and_sufficiency_on_calibration_states(self):
        for definition in (CHAIN, DIRECT, DIAMOND, DIRECT4):
            cuts = potential._minimal_cuts(definition, float("inf"))
            stack, seen = [State()], set()
            while stack:
                state = stack.pop()
                if state in seen or terminal(definition, state) is not None:
                    continue
                seen.add(state)
                before = potential._potential(definition, state, cuts, float("inf"))
                if before < 1 << len(definition.edges):
                    self.assertEqual(reference_winner(definition, state), "B")
                for offer in legal_actions(definition, state):
                    staged = apply_action(definition, state, offer)
                    children = [apply_action(definition, staged, (keep,)) for keep in offer]
                    after = [potential._potential(definition, child, cuts, float("inf"))
                             for child in children]
                    self.assertLessEqual(sum(after), 2 * before)
                    stack.extend(children)

    def test_budget_boundaries_and_temporary_reply_charge(self):
        full = potential.solve(DIAMOND, 10000, 100000)
        for field in ("node_limit", "transition_limit", "proof_arc_limit"):
            limits = dict(node_limit=10000, transition_limit=100000, proof_arc_limit=1000000)
            counter = {"node_limit": "nodes", "transition_limit": "transitions",
                       "proof_arc_limit": "proof_arcs"}[field]
            limits[field] = full[counter] - 1
            result = potential.solve(DIAMOND, **limits)
            self.assertEqual(result["status"], "UNKNOWN")
            self.assertIsNone(result["winner"])
            self.assertIsNone(result["proof"])
            self.assertLessEqual(result[counter], limits[field])
        result = potential.solve(CHAIN, 1, 100, proof_arc_limit=0)
        self.assertEqual(result["reason"], "PROOF_ARC_LIMIT")
        self.assertEqual(result["nodes"], 1)
        self.assertEqual(result["transitions"], 1)
        self.assertEqual(result["proof_arcs"], 0)

    def test_bad_limits_and_unsupported_cut_work_are_rejected(self):
        for value in (-1, True, 1.0):
            for field in ("node_limit", "transition_limit", "proof_arc_limit"):
                limits = dict(node_limit=100, transition_limit=100, proof_arc_limit=100)
                limits[field] = value
                with self.assertRaises(ValueError):
                    potential.solve(CHAIN, **limits)
        for cpu in (0, -1, True, float("inf"), float("nan")):
            with self.assertRaises(ValueError):
                potential.solve(CHAIN, 100, 100, cpu_seconds=cpu)
        unsupported = replace(DIRECT, vertices=13)
        for enumerator in (potential._minimal_cuts, potential._checker_cuts):
            with self.assertRaises(ValueError):
                enumerator(unsupported, float("inf"))

    def test_cpu_bound_in_cut_generation_and_checker(self):
        with patch("parity_forge.cut_choose_potential.time.process_time", side_effect=[0, 2]):
            result = potential.solve(CHAIN, 100, 100, cpu_seconds=1)
        self.assertEqual(result["reason"], "CPU_LIMIT")
        self.assertEqual(result["cut_count"], 0)
        self.assertEqual(result["nodes"], 0)
        proof = single_leaf(DIRECT, "B", "CUT_POTENTIAL")
        with patch("parity_forge.cut_choose_potential.time.process_time", side_effect=[0, 2]):
            with self.assertRaises(BudgetExceeded):
                potential.verify_proof(DIRECT, proof, cpu_seconds=1)

    def test_cpu_expiring_at_checker_handoff_is_unknown(self):
        with patch.object(potential, "_clock"), \
                patch("parity_forge.cut_choose_potential.time.process_time", side_effect=[0, 2]), \
                patch.object(potential, "verify_proof") as checker:
            result = potential.solve(CHAIN, 100, 100, cpu_seconds=1)
        self.assertEqual(result["reason"], "CPU_LIMIT")
        self.assertIsNone(result["proof"])
        checker.assert_not_called()

    def test_checker_never_trusts_solver_cuts_potential_or_terminality(self):
        proof = single_leaf(DIRECT4, "B", "CUT_POTENTIAL")
        with patch.object(potential, "solve", side_effect=AssertionError("no solve")), \
                patch.object(potential, "_minimal_cuts", side_effect=AssertionError("no cuts")), \
                patch.object(potential, "_potential", side_effect=AssertionError("no potential")), \
                patch.object(potential, "terminal", side_effect=AssertionError("no terminal")):
            self.assertEqual(potential.verify_proof(DIRECT4, proof)["status"], "PASS")

    def test_false_leaf_types_and_claimed_potential_values_are_rejected(self):
        for definition, winner, kind in ((CHAIN, "A", "CUT_POTENTIAL"),
                                          (DIRECT, "B", "TERMINAL"),
                                          (DIRECT, "B", "BRANCH"),
                                          (DIRECT, "B", "OTHER")):
            with self.assertRaises(ValueError):
                potential.verify_proof(definition, single_leaf(definition, winner, kind))
        proof = single_leaf(DIRECT, "B", "CUT_POTENTIAL")
        proof["nodes"]["0:0"]["weight"] = 0
        with self.assertRaises(ValueError):
            potential.verify_proof(DIRECT, proof)
        proof = potential.solve(CHAIN, 100, 100)["proof"]
        key = next(key for key in proof["nodes"] if key != "0:0")
        proof["nodes"][key]["kind"] = "CUT_POTENTIAL"
        with self.assertRaises(ValueError):
            potential.verify_proof(CHAIN, proof)

    def test_branch_reply_tampering_rejected(self):
        original = potential.solve(CHAIN, 100, 100)["proof"]
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
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                potential.verify_proof(CHAIN, proof)

    def test_b_branch_covers_every_offer_and_may_end_at_potential_leaves(self):
        proof = single_leaf(DIRECT4, "B", "BRANCH")
        for offer in legal_actions(DIRECT4, State()):
            keep = offer[0]
            child = apply_action(DIRECT4, apply_action(DIRECT4, State(), offer), (keep,))
            key = str(child.secured) + ":" + str(child.removed)
            kind = "TERMINAL" if 0 in offer else "CUT_POTENTIAL"
            proof["nodes"][key] = {"winner": "B", "kind": kind, "replies": []}
            proof["nodes"]["0:0"]["replies"].append(
                {"offer": list(offer), "keep": keep, "child": key})
        receipt = potential.verify_proof(DIRECT4, proof)
        self.assertEqual(receipt["arcs"], 6)
        self.assertEqual(receipt["potential_leaves"], 3)
        with self.assertRaises(BudgetExceeded):
            potential.verify_proof(DIRECT4, proof, arc_limit=5)
        for mode in ("missing", "duplicate"):
            changed = deepcopy(proof)
            replies = changed["nodes"]["0:0"]["replies"]
            if mode == "missing": replies.pop()
            else: replies.append(deepcopy(replies[0]))
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                potential.verify_proof(DIRECT4, changed)

    def test_binding_orphan_and_work_caps_rejected(self):
        original = potential.solve(CHAIN, 100, 100)["proof"]
        for mode in ("hash", "root", "winner", "orphan", "postterminal", "extra"):
            proof = deepcopy(original)
            key = next(key for key in proof["nodes"] if key != "0:0")
            if mode == "hash": proof["definition_hash"] = "bad"
            elif mode == "root": proof["root"] = "00:0"
            elif mode == "winner": proof["nodes"][key]["winner"] = "B"
            elif mode == "orphan": proof["nodes"]["3:0"] = deepcopy(proof["nodes"][key])
            elif mode == "postterminal":
                proof["nodes"][key]["replies"] = deepcopy(proof["nodes"]["0:0"]["replies"])
            else: proof["nodes"]["0:0"]["extra"] = 1
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                potential.verify_proof(CHAIN, proof)
        with self.assertRaises(BudgetExceeded):
            potential.verify_proof(CHAIN, original, arc_limit=0)


if __name__ == "__main__":
    unittest.main()
