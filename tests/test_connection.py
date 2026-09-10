"""Small synthetic tests for the Plan 0040 connection-game core."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import hashlib
import json
import unittest
from unittest.mock import patch

from parity_forge.connection import (
    ACTION_KINDS,
    BRIDGE_PAIR,
    FORMAT,
    NEIGHBOR_DELTAS,
    PLACE_AND_CONVERT,
    PLACE_ONE,
    TERMINAL_RULE,
    TOPOLOGY,
    Action,
    Definition,
    State,
    action_from_dict,
    action_to_dict,
    apply_action,
    definition_hash,
    describe_rules,
    initial_state,
    legal_actions,
    neighbors,
    parse_definition,
    state_from_dict,
    state_to_dict,
    termination_certificate,
    validate_state,
    winner_from_board,
)
from parity_forge.dsl import DefinitionError, Player


def definition_wire(
    *, identifier="synthetic-connection", size=3, first="A", bridge=1, conversion=1
):
    return {
        "format": FORMAT,
        "id": identifier,
        "board": {"size": size, "topology": TOPOLOGY},
        "first_player": first,
        "bridge_credits_A": bridge,
        "conversion_credits_B": conversion,
        "terminal_rule": TERMINAL_RULE,
    }


SMALL = parse_definition(definition_wire())
SMALL_B_FIRST = parse_definition(definition_wire(identifier="synthetic-b", first="B"))
PLAIN_TWO = parse_definition(
    definition_wire(identifier="synthetic-two", size=2, bridge=0, conversion=0)
)


def mask(*cells):
    value = 0
    for cell in cells:
        value |= 1 << cell
    return value


class DefinitionTests(unittest.TestCase):
    def test_strict_parse_and_immutable_value(self):
        self.assertEqual(
            SMALL,
            Definition("synthetic-connection", 3, Player.A, 1, 1),
        )
        self.assertEqual(ACTION_KINDS, (PLACE_ONE, BRIDGE_PAIR, PLACE_AND_CONVERT))
        self.assertEqual(
            NEIGHBOR_DELTAS,
            ((-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0)),
        )
        with self.assertRaises(FrozenInstanceError):
            SMALL.size = 4

    def test_definition_hash_excludes_only_id(self):
        wire = definition_wire()
        canonical = deepcopy(wire)
        del canonical["id"]
        expected = hashlib.sha256(
            json.dumps(
                canonical,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("ascii")
        ).hexdigest()
        self.assertEqual(definition_hash(SMALL), expected)
        self.assertEqual(
            definition_hash(SMALL),
            definition_hash(replace(SMALL, id="renamed-synthetic")),
        )
        self.assertNotEqual(definition_hash(SMALL), definition_hash(SMALL_B_FIRST))

    def test_bad_definition_shapes_tags_and_exact_types_rejected(self):
        top_mutations = [
            ("format", "other"),
            ("id", ""),
            ("id", "Uppercase"),
            ("id", "x" * 81),
            ("first_player", Player.A),
            ("first_player", "C"),
            ("bridge_credits_A", True),
            ("bridge_credits_A", -1),
            ("bridge_credits_A", 10),
            ("conversion_credits_B", 1.0),
            ("conversion_credits_B", -1),
            ("conversion_credits_B", 10),
            ("terminal_rule", "NO_LEGAL_ACTION_LOSES"),
        ]
        for key, value in top_mutations:
            with self.subTest(key=key, value=value):
                wire = definition_wire()
                wire[key] = value
                with self.assertRaises(DefinitionError):
                    parse_definition(wire)
        board_mutations = [
            ("size", True),
            ("size", 1),
            ("size", 20),
            ("topology", "SQUARE"),
        ]
        for key, value in board_mutations:
            with self.subTest(board_key=key, value=value):
                wire = definition_wire()
                wire["board"][key] = value
                with self.assertRaises(DefinitionError):
                    parse_definition(wire)
        for wire in (None, {}, dict(definition_wire(), extra=1)):
            with self.assertRaises(DefinitionError):
                parse_definition(wire)
        missing = definition_wire()
        del missing["first_player"]
        with self.assertRaises(DefinitionError):
            parse_definition(missing)
        extra_board = definition_wire()
        extra_board["board"]["rows"] = 3
        with self.assertRaises(DefinitionError):
            parse_definition(extra_board)

    def test_direct_definition_requires_exact_canonical_types(self):
        bad_values = [
            ("bad id", 3, Player.A, 1, 1),
            ("ok", True, Player.A, 1, 1),
            ("ok", 3, "A", 1, 1),
            ("ok", 3, Player.A, False, 1),
            ("ok", 3, Player.A, 1, 2.0),
        ]
        for values in bad_values:
            with self.subTest(values=values), self.assertRaises(DefinitionError):
                Definition(*values)


class GeometryAndActionTests(unittest.TestCase):
    def test_all_six_hex_directions_and_boundary_clipping(self):
        self.assertEqual(neighbors(SMALL, 4), (1, 2, 3, 5, 6, 7))
        self.assertEqual(neighbors(SMALL, 0), (1, 3))
        self.assertEqual(neighbors(SMALL, 8), (5, 7))
        for cell in (-1, 9, True, 1.0):
            with self.subTest(cell=cell), self.assertRaises(ValueError):
                neighbors(SMALL, cell)

    def test_action_values_and_wire_roundtrip_preserve_conversion_order(self):
        actions = [
            Action(PLACE_ONE, (4,)),
            Action(BRIDGE_PAIR, (6, 7)),
            Action(PLACE_AND_CONVERT, (3, 0)),
        ]
        for action in actions:
            with self.subTest(action=action):
                wire = action_to_dict(SMALL, action)
                self.assertEqual(action_from_dict(SMALL, wire), action)
        conversion_wire = action_to_dict(SMALL, actions[-1])
        self.assertEqual(conversion_wire["cells"], [[1, 0], [0, 0]])
        self.assertEqual(action_from_dict(SMALL, conversion_wire).cells, (3, 0))
        with self.assertRaises(FrozenInstanceError):
            actions[0].kind = BRIDGE_PAIR

    def test_malformed_or_noncanonical_actions_rejected(self):
        constructors = [
            ("UNKNOWN", (0,)),
            (PLACE_ONE, (0, 1)),
            (PLACE_ONE, [0]),
            (BRIDGE_PAIR, (1, 0)),
            (BRIDGE_PAIR, (0, 0)),
            (PLACE_AND_CONVERT, (0, 0)),
            (PLACE_AND_CONVERT, (0, True)),
        ]
        for kind, cells in constructors:
            with self.subTest(kind=kind, cells=cells), self.assertRaises(ValueError):
                Action(kind, cells)
        bad_wires = [
            None,
            {},
            {"kind": PLACE_ONE, "cells": [[0, 0]], "extra": 1},
            {"kind": PLACE_ONE, "cells": [(0, 0)]},
            {"kind": PLACE_ONE, "cells": [[True, 0]]},
            {"kind": PLACE_ONE, "cells": [[3, 0]]},
            {"kind": BRIDGE_PAIR, "cells": [[0, 1], [0, 0]]},
            {"kind": BRIDGE_PAIR, "cells": [[0, 0], [2, 2]]},
            {"kind": PLACE_AND_CONVERT, "cells": [[0, 0], [2, 2]]},
        ]
        for wire in bad_wires:
            with self.subTest(wire=wire), self.assertRaises(ValueError):
                action_from_dict(SMALL, wire)

    def test_canonical_legal_order_and_asymmetric_action_access(self):
        actions = legal_actions(SMALL, initial_state(SMALL))
        self.assertEqual(actions[:9], tuple(Action(PLACE_ONE, (i,)) for i in range(9)))
        self.assertEqual(len(actions), 25)
        self.assertTrue(all(action.kind == BRIDGE_PAIR for action in actions[9:]))
        self.assertEqual(
            tuple(action.cells for action in actions[9:]),
            tuple(sorted(action.cells for action in actions[9:])),
        )

        after_a = apply_action(SMALL, initial_state(SMALL), Action(PLACE_ONE, (0,)))
        b_actions = legal_actions(SMALL, after_a)
        self.assertEqual(
            b_actions[:8],
            tuple(Action(PLACE_ONE, (i,)) for i in range(1, 9)),
        )
        self.assertEqual(
            tuple(action for action in b_actions if action.kind == PLACE_AND_CONVERT),
            (
                Action(PLACE_AND_CONVERT, (1, 0)),
                Action(PLACE_AND_CONVERT, (3, 0)),
            ),
        )
        self.assertFalse(
            any(
                action.kind == PLACE_AND_CONVERT
                for action in legal_actions(SMALL_B_FIRST, initial_state(SMALL_B_FIRST))
            )
        )


class StateAndTransitionTests(unittest.TestCase):
    def test_initial_state_and_state_wire_roundtrip(self):
        initial = initial_state(SMALL)
        self.assertEqual(initial, State(0, 0, 1, 1, Player.A, 0, None))
        self.assertEqual(state_from_dict(SMALL, state_to_dict(SMALL, initial)), initial)

        after_bridge = apply_action(
            SMALL, initial, Action(BRIDGE_PAIR, (0, 1))
        )
        after_conversion = apply_action(
            SMALL, after_bridge, Action(PLACE_AND_CONVERT, (3, 0))
        )
        self.assertEqual(
            state_from_dict(SMALL, state_to_dict(SMALL, after_conversion)),
            after_conversion,
        )
        self.assertEqual(state_to_dict(SMALL, after_conversion)["a"], [[0, 1]])
        self.assertEqual(
            state_to_dict(SMALL, after_conversion)["b"], [[0, 0], [1, 0]]
        )

    def test_state_wire_and_state_invariants_fail_closed(self):
        initial = initial_state(SMALL)
        invalid_states = [
            replace(initial, a=True),
            replace(initial, a=1 << 9),
            replace(initial, a=1, b=1),
            replace(initial, bridge_left=2),
            replace(initial, conversion_left=-1),
            replace(initial, to_move=Player.B),
            replace(initial, plies=1),
            replace(initial, winner=Player.A),
            State(mask(0), 0, 0, 1, Player.B, 1, None),
            State(mask(0), 0, 1, 0, Player.B, 1, None),
            None,
        ]
        for state in invalid_states:
            with self.subTest(state=state), self.assertRaises(ValueError):
                validate_state(SMALL, state)

        wire = state_to_dict(SMALL, initial)
        bad_wires = []
        bad = deepcopy(wire)
        bad["a"] = [[0, 1], [0, 0]]
        bad_wires.append(bad)
        bad = deepcopy(wire)
        bad["a"] = [[0, 0], [0, 0]]
        bad_wires.append(bad)
        bad = deepcopy(wire)
        bad["a"] = [(0, 0)]
        bad_wires.append(bad)
        bad = deepcopy(wire)
        bad["plies"] = True
        bad_wires.append(bad)
        bad = deepcopy(wire)
        bad["winner"] = "DRAW"
        bad_wires.append(bad)
        bad = deepcopy(wire)
        bad["extra"] = 1
        bad_wires.append(bad)
        for bad_wire in bad_wires:
            with self.subTest(wire=bad_wire), self.assertRaises(ValueError):
                state_from_dict(SMALL, bad_wire)

    def test_credit_debit_counts_and_atomic_conversion(self):
        definition = parse_definition(
            definition_wire(
                identifier="atomic-conversion", bridge=0, conversion=1
            )
        )
        before = State(
            a=mask(5, 7, 8),
            b=mask(0, 3),
            bridge_left=0,
            conversion_left=1,
            to_move=Player.B,
            plies=5,
            winner=None,
        )
        validate_state(definition, before)
        result = apply_action(
            definition, before, Action(PLACE_AND_CONVERT, (6, 7))
        )
        self.assertEqual(result.a, mask(5, 8))
        self.assertEqual(result.b, mask(0, 3, 6, 7))
        self.assertEqual(result.conversion_left, 0)
        self.assertEqual(result.plies, 6)
        self.assertIs(result.winner, Player.B)
        self.assertIs(result.to_move, Player.B)

    def test_registered_four_ply_shape_uses_ordered_conversion_targets(self):
        definition = parse_definition(
            definition_wire(
                identifier="four-ply-synthetic", bridge=1, conversion=2
            )
        )
        state = initial_state(definition)
        sequence = (
            Action(PLACE_ONE, (4,)),
            Action(PLACE_AND_CONVERT, (1, 4)),
            Action(BRIDGE_PAIR, (6, 7)),
            Action(PLACE_AND_CONVERT, (8, 7)),
        )
        for index, action in enumerate(sequence):
            state = apply_action(definition, state, action)
            self.assertEqual(state.plies, index + 1)
        self.assertEqual(state.a, mask(6))
        self.assertEqual(state.b, mask(1, 4, 7, 8))
        self.assertIs(state.winner, Player.B)
        self.assertEqual(legal_actions(definition, state), ())
        with self.assertRaises(ValueError):
            apply_action(definition, state, Action(PLACE_ONE, (0,)))

    def test_real_a_and_b_connection_endings(self):
        state = initial_state(PLAIN_TWO)
        for action in (
            Action(PLACE_ONE, (0,)),
            Action(PLACE_ONE, (2,)),
            Action(PLACE_ONE, (1,)),
        ):
            state = apply_action(PLAIN_TWO, state, action)
        self.assertIs(state.winner, Player.A)
        self.assertIs(state.to_move, Player.A)

        b_first = replace(PLAIN_TWO, id="two-b-first", first_player=Player.B)
        state = initial_state(b_first)
        for action in (
            Action(PLACE_ONE, (0,)),
            Action(PLACE_ONE, (1,)),
            Action(PLACE_ONE, (2,)),
        ):
            state = apply_action(b_first, state, action)
        self.assertIs(state.winner, Player.B)
        self.assertIs(state.to_move, Player.B)

    def test_illegal_role_credit_occupancy_and_adjacency_rejected(self):
        initial = initial_state(SMALL)
        bad_initial = [
            Action(PLACE_AND_CONVERT, (1, 0)),
            Action(BRIDGE_PAIR, (0, 8)),
        ]
        for action in bad_initial:
            with self.subTest(action=action), self.assertRaises(ValueError):
                apply_action(SMALL, initial, action)
        after_a = apply_action(SMALL, initial, Action(PLACE_ONE, (0,)))
        for action in (
            Action(PLACE_ONE, (0,)),
            Action(BRIDGE_PAIR, (1, 2)),
            Action(PLACE_AND_CONVERT, (8, 0)),
            Action(PLACE_AND_CONVERT, (1, 2)),
        ):
            with self.subTest(action=action), self.assertRaises(ValueError):
                apply_action(SMALL, after_a, action)

        no_bridge = replace(SMALL, id="no-bridge", bridge_credits_A=0)
        with self.assertRaises(ValueError):
            apply_action(
                no_bridge, initial_state(no_bridge), Action(BRIDGE_PAIR, (0, 1))
            )
        no_conversion = replace(SMALL_B_FIRST, id="no-conversion", conversion_credits_B=0)
        with self.assertRaises(ValueError):
            apply_action(
                no_conversion,
                initial_state(no_conversion),
                Action(PLACE_AND_CONVERT, (1, 0)),
            )


class TerminalAndRuleTests(unittest.TestCase):
    def test_connectivity_is_recomputed_after_ownership_change(self):
        self.assertIs(winner_from_board(SMALL, mask(0, 1, 2), 0), Player.A)
        self.assertIsNone(winner_from_board(SMALL, mask(0, 2), mask(1)))
        self.assertIs(winner_from_board(SMALL, 0, mask(0, 3, 6)), Player.B)
        for a, b in ((True, 0), (-1, 0), (1 << 9, 0), (1, 1)):
            with self.subTest(a=a, b=b), self.assertRaises(ValueError):
                winner_from_board(SMALL, a, b)

    def test_invalid_both_connection_and_full_no_connection_are_errors(self):
        with patch(
            "parity_forge.connection._has_connection", side_effect=(True, True)
        ):
            with self.assertRaisesRegex(ValueError, "both players"):
                winner_from_board(SMALL, mask(0), mask(1))
        with patch("parity_forge.connection._has_connection", return_value=False):
            with self.assertRaisesRegex(ValueError, "full board"):
                winner_from_board(SMALL, mask(0, 2, 4, 6, 8), mask(1, 3, 5, 7))

    def test_no_default_loss_and_termination_certificate(self):
        state = initial_state(SMALL)
        self.assertIsNone(state.winner)
        self.assertTrue(legal_actions(SMALL, state))
        self.assertTrue(all(action.kind in ACTION_KINDS for action in legal_actions(SMALL, state)))
        certificate = termination_certificate(SMALL)
        self.assertEqual(certificate["measure"], "EMPTY_CELL_COUNT")
        self.assertEqual(certificate["initial_measure"], 9)
        self.assertEqual(certificate["minimum_decrease_per_action"], 1)
        self.assertEqual(certificate["maximum_actions"], 9)
        self.assertEqual(certificate["terminal_winners"], ["A", "B"])
        self.assertFalse(certificate["draw_outcome"])
        self.assertFalse(certificate["no_legal_action_winner"])

    def test_rules_are_derived_from_definition(self):
        rules = describe_rules(SMALL_B_FIRST)
        self.assertIsInstance(rules, tuple)
        self.assertIn("3x3", rules[0])
        self.assertIn("B moves first", rules[0])
        self.assertTrue(any("1 bridge credits" in rule for rule in rules))
        self.assertTrue(any("1 conversion credits" in rule for rule in rules))
        self.assertTrue(any("no pass, draw, or no-action loss" in rule for rule in rules))


if __name__ == "__main__":
    unittest.main()
