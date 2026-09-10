"""Synthetic rule calibrations; the original is inspected, never played."""

import hashlib
import json
import unittest
from dataclasses import FrozenInstanceError, replace

from parity_forge.cut_choose import (
    Definition, State, apply_action, connected, definition_hash,
    definition_to_dict, initial_state, legal_actions, original_definition,
    parse_definition, replay, terminal, validate_state,
)


CHAIN = Definition("chain", 3, ((0, 1), (1, 2)), (0,), (2,))
DIRECT = Definition("direct", 4, ((0, 1), (2, 3)), (0,), (1,))
DIAMOND = Definition("diamond", 4, ((0, 1), (0, 2), (1, 3), (2, 3)),
                     (0,), (3,))
DIRECT4 = Definition("direct4", 4, ((0, 1), (0, 2), (1, 2), (2, 3)),
                     (0,), (1,))


class DefinitionTests(unittest.TestCase):
    def test_original_is_exact_graph_and_initial_actions_only(self):
        definition = original_definition()
        self.assertEqual(definition.id, "bridge-cut-choose-4x4-v1")
        self.assertEqual(definition.vertices, 16)
        expected = tuple(sorted((u, v) for u in range(16) for v in range(u + 1, 16)
                                if v - u == 4 or (v - u == 1 and u // 4 == v // 4)))
        self.assertEqual(definition.edges, expected)
        self.assertEqual(len(definition.edges), 24)
        self.assertEqual(definition.left, (0, 4, 8, 12))
        self.assertEqual(definition.right, (3, 7, 11, 15))
        boundary_edges = [(u, v) for u, v in definition.edges
                          if v - u == 4 and u % 4 in (0, 3)]
        self.assertEqual(len(boundary_edges), 6)
        state = initial_state(definition)
        self.assertIsNone(terminal(definition, state))
        actions = legal_actions(definition, state)
        self.assertEqual(len(actions), 276)
        self.assertEqual(actions, tuple(sorted(actions)))

    def test_wire_canonicalization_and_roundtrip(self):
        wire = definition_to_dict(DIAMOND)
        wire["edges"] = [edge[::-1] for edge in reversed(wire["edges"])]
        canonical = parse_definition(wire)
        self.assertEqual(canonical, DIAMOND)
        self.assertEqual(parse_definition(json.loads(json.dumps(
            definition_to_dict(canonical)))), DIAMOND)
        boundary_wire = definition_to_dict(DIRECT4)
        boundary_wire["left"] = [2, 0]
        self.assertEqual(parse_definition(boundary_wire).left, (0, 2))

    def test_hash_excludes_only_id_and_has_exact_prefix(self):
        wire = definition_to_dict(CHAIN)
        del wire["id"]
        expected = hashlib.sha256(b"parity-forge:cut-choose-definition:v1\n" +
                                 json.dumps(wire, sort_keys=True, separators=(",", ":"),
                                            ensure_ascii=False).encode("utf-8")).hexdigest()
        self.assertEqual(definition_hash(CHAIN), expected)
        self.assertEqual(definition_hash(CHAIN), definition_hash(replace(CHAIN, id="別名")))
        self.assertNotEqual(definition_hash(CHAIN), definition_hash(DIRECT))

    def test_bad_wire_shapes_values_and_tags_rejected(self):
        mutations = [
            ("id", ""), ("id", "x" * 81), ("id", False),
            ("vertices", True), ("vertices", 3.0), ("vertices", 1), ("vertices", 33),
            ("edges", []), ("edges", [[0, 1]]),
            ("edges", [[0, 1], [1, 0]]), ("edges", [[0, 0], [1, 2]]),
            ("edges", [[False, 1], [1, 2]]), ("edges", [[0, 3], [1, 2]]),
            ("edges", [[0, 1, 2], [1, 2]]), ("edges", [(0, 1), (1, 2)]),
            ("edges", [[0, 1], [1, 2]] * 17),
            ("left", []), ("left", [0, 0]), ("left", [True]),
            ("left", [2]), ("right", [3]), ("right", [2.0]),
            ("format", "unknown"), ("terminal_rule", "DRAW"),
            ("roles", {"A": "BUILDER", "B": "CUTTER"}),
            ("roles", {"A": "CUTTER", "B": "BUILDER", "C": "OTHER"}),
        ]
        for key, value in mutations:
            with self.subTest(key=key, value=value):
                wire = definition_to_dict(CHAIN)
                wire[key] = value
                with self.assertRaises(ValueError):
                    parse_definition(wire)
        for wire in (None, {}, dict(definition_to_dict(CHAIN), unknown=1)):
            with self.assertRaises(ValueError):
                parse_definition(wire)
        missing = definition_to_dict(CHAIN)
        del missing["roles"]
        with self.assertRaises(ValueError):
            parse_definition(missing)

    def test_direct_definition_must_already_be_canonical_and_immutable(self):
        for fields in ({"edges": ((1, 2), (0, 1))}, {"edges": ((1, 0), (1, 2))},
                       {"edges": [(0, 1), (1, 2)]}, {"left": [0]},
                       {"left": (1, 0)}, {"right": (2, 2)}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                replace(CHAIN, **fields)
        with self.assertRaises(FrozenInstanceError):
            CHAIN.vertices = 4
        wire = definition_to_dict(CHAIN)
        wire["edges"][0][0] = 2
        wire["roles"]["A"] = "OTHER"
        self.assertEqual(definition_to_dict(CHAIN)["roles"]["A"], "CUTTER")
        self.assertEqual(CHAIN.edges[0], (0, 1))


class StateTests(unittest.TestCase):
    def test_connectivity_and_invalid_masks(self):
        self.assertFalse(connected(CHAIN, 0))
        self.assertFalse(connected(CHAIN, 1))
        self.assertTrue(connected(CHAIN, 3))
        self.assertTrue(connected(DIRECT, 1))
        for mask in (-1, 4, True, 1.0):
            with self.assertRaises(ValueError):
                connected(CHAIN, mask)

    def test_offer_locks_choices_without_changing_masks(self):
        state = initial_state(DIAMOND)
        pending = apply_action(DIAMOND, state, (0, 2))
        self.assertEqual(state, State())
        self.assertEqual(pending, State(0, 0, (0, 2)))
        self.assertEqual(legal_actions(DIAMOND, pending), ((0,), (2,)))
        self.assertIsNone(terminal(DIAMOND, pending))
        with self.assertRaises(FrozenInstanceError):
            pending.secured = 1

    def test_choice_resolves_two_edges_and_clears_pending(self):
        for keep, remove in ((0, 2), (2, 0)):
            pending = apply_action(DIAMOND, State(), (0, 2))
            result = apply_action(DIAMOND, pending, (keep,))
            self.assertEqual(result, State(1 << keep, 1 << remove))
            self.assertEqual(bin(result.secured | result.removed).count("1"), 2)
            validate_state(DIAMOND, result)

    def test_invalid_states_rejected(self):
        states = [State(True, 0), State(0, False), State(-1, 0), State(16, 0),
                  State(1.0, 2), State(1, 1), State(1, 0), State(3, 4),
                  State(pending=[]), State(pending=(0,)), State(pending=(0, 1, 2)),
                  State(pending=(True, 2)), State(pending=(2, 0)),
                  State(pending=(0, 0)), State(pending=(-1, 2)),
                  State(pending=(0, 4)), State(1, 2, (0, 2)), None]
        for state in states:
            with self.subTest(state=state), self.assertRaises(ValueError):
                validate_state(DIAMOND, state)
        with self.assertRaises(ValueError):
            validate_state(DIRECT4, State(1, 2, (2, 3)))

    def test_wrong_phase_and_illegal_actions_rejected(self):
        for action in ((0,), (1, 0), (0, 0), (-1, 2), (0, 4),
                       (True, 2), (0.0, 2), [0, 1], (), (0, 1, 2)):
            with self.subTest(action=action), self.assertRaises(ValueError):
                apply_action(DIAMOND, State(), action)
        pending = apply_action(DIAMOND, State(), (0, 2))
        for action in ((1,), (0, 2), (True,), [0], ()):
            with self.subTest(action=action), self.assertRaises(ValueError):
                apply_action(DIAMOND, pending, action)
        with self.assertRaises(ValueError):
            apply_action(DIAMOND, State(1, 2), (0, 2))

    def test_hand_proved_two_edge_winners_and_no_postterminal_move(self):
        for definition, keep, winner in ((CHAIN, 0, "A"), (CHAIN, 1, "A"),
                                          (DIRECT, 0, "B"), (DIRECT, 1, "A")):
            state = replay(definition, [(0, 1), (keep,)])
            self.assertEqual(terminal(definition, state), winner)
            self.assertEqual(legal_actions(definition, state), ())
            with self.assertRaises(ValueError):
                apply_action(definition, state, (0, 1))

    def test_initial_disconnection_is_terminal_a(self):
        definition = Definition("disconnected", 4, ((0, 1), (2, 3)), (0,), (3,))
        self.assertEqual(terminal(definition, State()), "A")
        self.assertEqual(legal_actions(definition, State()), ())
        with self.assertRaises(ValueError):
            validate_state(definition, State(pending=(0, 1)))

    def test_replay_is_deterministic_and_can_end_at_offer(self):
        actions = [(0, 1), (0,), (2, 3)]
        self.assertEqual(replay(DIAMOND, actions), State(1, 2, (2, 3)))
        self.assertEqual(replay(DIAMOND, iter(actions)), replay(DIAMOND, actions))
        self.assertEqual(replay(DIAMOND, []), State())
        self.assertEqual(actions, [(0, 1), (0,), (2, 3)])

    def test_all_legal_calibration_plays_terminate_with_one_winner(self):
        for definition in (CHAIN, DIRECT, DIAMOND, DIRECT4):
            stack = [(State(), 0)]
            while stack:
                state, depth = stack.pop()
                winner = terminal(definition, state)
                if winner is not None:
                    self.assertIn(winner, ("A", "B"))
                    self.assertEqual(state.pending, ())
                    self.assertLessEqual(depth, len(definition.edges))
                    continue
                actions = legal_actions(definition, state)
                self.assertTrue(actions)
                for action in actions:
                    child = apply_action(definition, state, action)
                    before = bin(state.secured | state.removed).count("1")
                    after = bin(child.secured | child.removed).count("1")
                    self.assertEqual(after - before, 2 if state.pending else 0)
                    stack.append((child, depth + 1))


if __name__ == "__main__":
    unittest.main()
