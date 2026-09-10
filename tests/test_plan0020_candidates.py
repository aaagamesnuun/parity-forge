"""Static pilot exposure; executed game fixtures are exclusively 3x3."""

import copy
import hashlib
import json
import unittest
from unittest import mock

from parity_forge.dsl import Player, canonical_json, definition_hash, parse_definition
from parity_forge.engine import apply_action, initial_state, legal_actions
from parity_forge_universe import typed_occupancy as universe
from scripts import plan0020_candidates as candidates


def tiny(first="A", positions=((0, 1), (2, 1))):
    # Different board size mechanically separates all executed fixtures from
    # production definitions, including D4 and role exchange. No builder call.
    pieces = [{"owner": owner, "piece": owner.lower(), "position": list(pos)}
              for owner, pos in zip(("A", "B"), positions)]
    return {
        "schema_version": 4, "name": "plan0020-artificial-3x3",
        "board_size": 3, "first_player": first,
        "max_plies": sum(2 - p["position"][0] if p["owner"] == "A"
                         else 2 * p["position"][0] for p in pieces) + 1,
        "roles": {
            "A": {"action": {"kind": "MOVE_CAPTURE", "piece": "a",
                              "vectors": [[1, -1], [1, 0], [1, 1]]},
                  "goal": {"kind": "REACH_EDGE", "piece": "a", "edge": "BOTTOM"}},
            "B": {"action": {"kind": "PUSH", "piece": "b",
                              "vectors": [[-1, -1], [-1, 0], [-1, 1]]},
                  "goal": {"kind": "REACH_EDGE", "piece": "b", "edge": "TOP"}},
        }, "initial_pieces": pieces,
    }


class CandidateTests(unittest.TestCase):
    def test_static_builder_order_counts_hashes_and_reproducibility(self):
        with mock.patch("parity_forge.engine.initial_state", side_effect=AssertionError), \
                mock.patch("parity_forge.engine.apply_action", side_effect=AssertionError):
            rows = candidates.build_candidates()
            self.assertEqual(rows, candidates.build_candidates())
        self.assertEqual(len(rows), 6)
        self.assertEqual(len({r["carrier_id"] for r in rows}), 6)
        self.assertEqual(len({r["certificate"]["definition_hash"] for r in rows}), 6)
        expected = [(n, counts, first) for n in (4, 5)
                    for counts in ((2, 3), (2, 4), (3, 4)) for first in ("B",)]
        for row, (size, counts, first) in zip(rows, expected):
            value = row["definition"]
            self.assertEqual((value["board_size"], row["first_player"]), (size, first))
            self.assertEqual(value["first_player"], first)
            self.assertEqual(value, json.loads(canonical_json(parse_definition(value))))
            self.assertEqual(row["certificate"], candidates.certify_no_draw(value))
            self.assertEqual(row["certificate"]["definition_hash"],
                             definition_hash(parse_definition(value)))
            self.assertEqual(value["max_plies"], (size - 1) * (counts[0] + 2 * counts[1]) + 1)
            for owner, count, rank_row in (("A", counts[0], 0), ("B", counts[1], size - 1)):
                columns = sorted(range(size), key=lambda col: (hashlib.sha256(
                    json.dumps(["plan0020", size, list(counts), owner, col],
                               separators=(",", ":")).encode()).hexdigest(), col))
                actual = [p["position"] for p in value["initial_pieces"] if p["owner"] == owner]
                self.assertEqual(actual, [[rank_row, col] for col in sorted(columns[:count])])
        rows[0]["definition"]["roles"]["A"]["action"]["vectors"].clear()
        self.assertTrue(rows[1]["definition"]["roles"]["A"]["action"]["vectors"])

    def test_old_six_semantic_exclusion_in_both_role_orders(self):
        roles = {"A": {"action_primitive": "MOVE_CAPTURE", "goal_primitive": "REACH_EDGE"},
                 "B": {"action_primitive": "PUSH", "goal_primitive": "REACH_EDGE"}}
        for value in (roles, {"A": roles["B"], "B": roles["A"]}):
            signature = universe.parse_semantic_signature({"universe_version": 1, "roles": value})
            self.assertFalse(universe.is_plan0013_semantic_region(signature))

    def test_certificate_canonicalizes_without_mutation(self):
        value = tiny()
        expected = candidates.certify_no_draw(value)
        value["initial_pieces"].reverse()
        value["roles"]["A"]["action"]["vectors"].reverse()
        before = copy.deepcopy(value)
        self.assertEqual(expected, candidates.certify_no_draw(value))
        self.assertEqual(value, before)

    def test_certificate_rejects_invalid_or_out_of_theorem_wires(self):
        mutations = (
            lambda w: w.update(schema_version=3), lambda w: w.update(board_size=True),
            lambda w: w.update(board_size=6), lambda w: w.update(extra=0),
            lambda w: w.update(terminal_policy={"no_legal_action": "DRAW"}),
            lambda w: w.update(max_plies=w["max_plies"] - 1),
            lambda w: w.update(first_player="C"),
            lambda w: w["roles"]["A"]["action"].update(kind="MOVE"),
            lambda w: w["roles"]["B"]["action"].update(vectors=[[0, 1]]),
            lambda w: w["roles"]["A"]["action"].update(vectors=[[1, 0]]),
            lambda w: w["roles"]["A"]["goal"].update(edge="TOP"),
            lambda w: w["roles"]["B"]["goal"].update(piece="a"),
            lambda w: w["initial_pieces"][0].update(piece="b"),
            lambda w: w["initial_pieces"][0].update(position=[-1, 0]),
            lambda w: w["initial_pieces"].append(copy.deepcopy(w["initial_pieces"][0])),
            lambda w: w["initial_pieces"].pop(),
        )
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                value = tiny()
                mutate(value)
                with self.assertRaises(ValueError):
                    candidates.certify_no_draw(value)

    def test_all_tiny_branches_decrease_potential_and_finish_decisively(self):
        kinds, reasons, winners = set(), set(), set()
        for positions in (((0, 1), (2, 1)), ((0, 0), (1, 2))):
            for first in ("A", "B"):
                raw = tiny(first, positions)
                self.assertEqual(raw["board_size"], 3)  # Never execute production boards.
                certificate = candidates.certify_no_draw(raw)
                definition = parse_definition(raw)
                stack, seen = [initial_state(definition)], set()

                def phi(state):
                    return sum(2 - p.position[0] if p.owner is Player.A
                               else 2 * p.position[0] for p in state.pieces)

                while stack:
                    state = stack.pop()
                    if state in seen:
                        continue
                    seen.add(state)
                    self.assertLess(len(seen), 2000)
                    self.assertLessEqual(state.ply, certificate["max_natural_plies"])
                    self.assertLess(state.ply, definition.max_plies)
                    if state.terminal:
                        self.assertIn(state.outcome.winner, (Player.A, Player.B))
                        self.assertIn(state.outcome.reason, ("GOAL", "NO_LEGAL_ACTION"))
                        reasons.add(state.outcome.reason)
                        winners.add(state.outcome.winner)
                        continue
                    actions = legal_actions(definition, state)
                    self.assertTrue(actions)
                    for action in actions:
                        child = apply_action(definition, state, action)
                        self.assertLess(phi(child), phi(state))
                        self.assertGreaterEqual(phi(child), 0)
                        if len(child.pieces) < len(state.pieces):
                            kinds.add("capture")
                        elif any(p.position == action.to_position and p.owner is state.to_move.other
                                 for p in state.pieces):
                            kinds.add("push")
                        else:
                            kinds.add("empty_move")
                        stack.append(child)
        self.assertEqual(kinds, {"capture", "push", "empty_move"})
        self.assertEqual(reasons, {"GOAL", "NO_LEGAL_ACTION"})
        self.assertEqual(winners, {Player.A, Player.B})


if __name__ == "__main__":
    unittest.main()
