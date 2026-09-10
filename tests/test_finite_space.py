"""Tiny synthetic calibration for the independent finite-space v1 core."""

import copy
import hashlib
import json
import unittest

from parity_forge.dsl import DefinitionError, Player
from parity_forge.finite_space import (
    Action,
    FORMAT,
    HASH_DOMAIN,
    TERMINAL_RULE,
    action_from_dict,
    action_to_dict,
    apply_action,
    asymmetry_witness,
    canonical_json,
    definition_hash,
    definition_to_dict,
    describe_rules,
    free_cells,
    initial_state,
    legal_actions,
    parse_definition,
    replay,
    state_to_dict,
    termination_certificate,
)


def _wire(identifier, rows, cols, role_a, role_b, *, blocked=(), first="A"):
    return {
        "format": FORMAT,
        "id": identifier,
        "board": {"rows": rows, "cols": cols, "blocked": [list(p) for p in blocked]},
        "first_player": first,
        "terminal_rule": TERMINAL_RULE,
        "roles": {"A": role_a, "B": role_b},
    }


def _tile(*shapes):
    return {"kind": "TILE", "shapes": [[list(p) for p in shape] for shape in shapes]}
def _trail(vectors, distance, starts):
    return {
        "kind": "TRAIL",
        "vectors": [list(v) for v in vectors],
        "max_distance": distance,
        "starts": [list(p) for p in starts],
    }
# Shared with the Plan0032 search/batch calibration.  These are syntax fixtures,
# never discovery candidates.
def single_vs_domino_fixture():
    return _wire(
        "tiny-single-vs-domino", 1, 3,
        _tile(((0, 0),)), _tile(((0, 0), (0, 1))),
    )
def domino_vs_single_fixture():
    return _wire(
        "tiny-domino-vs-single", 1, 4,
        _tile(((0, 0), (0, 1))), _tile(((0, 0),)),
    )
def symmetric_domino_fixture():
    return _wire(
        "tiny-symmetric-domino", 1, 4,
        _tile(((0, 0), (0, 1))), _tile(((0, 0), (0, 1))),
    )
def trail_fixture():
    return _wire(
        "tiny-two-vs-three-trails", 2, 6,
        _trail(((0, 1), (0, -1)), 5, ((0, 0), (1, 0))),
        _trail(((0, -1), (0, 1)), 2, ((0, 3), (1, 3), (1, 5))),
    )
def mixed_fixture():
    return _wire(
        "tiny-mixed-orientations", 3, 3,
        _tile(((0, 0), (0, 1)), ((0, 0), (1, 0))),
        _trail(((-1, 0), (0, -1), (0, 1), (1, 0)), 1, ((1, 1),)),
    )
def immobile_fixture():
    return _wire(
        "tiny-initially-immobile", 1, 1,
        _tile(((0, 0),)), _tile(((0, 0),)), blocked=((0, 0),),
    )


class FiniteSpaceTests(unittest.TestCase):
    def test_strict_parse_and_malformed_values(self):
        valid = mixed_fixture()
        parsed = parse_definition(valid)
        self.assertEqual(definition_to_dict(parsed), valid)

        bad = []
        value = copy.deepcopy(valid); value["extra"] = 1; bad.append(value)
        value = copy.deepcopy(valid); value["board"]["rows"] = True; bad.append(value)
        value = copy.deepcopy(valid); value["board"]["blocked"] = [[0, 0], [0, 0]]; bad.append(value)
        value = copy.deepcopy(valid); value["board"]["blocked"] = [[3, 0]]; bad.append(value)
        value = copy.deepcopy(valid); value["roles"]["A"]["extra"] = 1; bad.append(value)
        value = copy.deepcopy(valid); value["roles"]["A"]["shapes"] = [[[0, 0], [2, 0]]]; bad.append(value)
        value = copy.deepcopy(valid); value["roles"]["A"]["shapes"] = [[[0, 0], [0, 0]]]; bad.append(value)
        value = copy.deepcopy(valid); value["roles"]["B"]["vectors"] = [[0, 0]]; bad.append(value)
        value = copy.deepcopy(valid); value["roles"]["B"]["vectors"] = [[0, 1], [0, 1]]; bad.append(value)
        value = trail_fixture(); value["roles"]["B"]["starts"][0] = [0, 0]; bad.append(value)
        for malformed in bad:
            with self.subTest(malformed=malformed):
                with self.assertRaises(DefinitionError):
                    parse_definition(malformed)
        forged = parse_definition(single_vs_domino_fixture())
        object.__setattr__(forged.roles[0], "max_distance", False)
        with self.assertRaises(DefinitionError):
            definition_to_dict(forged)

    def test_canonical_order_and_id_free_semantic_hash(self):
        raw = trail_fixture()
        raw["board"]["blocked"] = [[0, 5], [0, 4]]
        raw["roles"]["A"]["vectors"].reverse()
        raw["roles"]["B"]["starts"].reverse()
        definition = parse_definition(raw)
        wire = definition_to_dict(definition)
        self.assertEqual(wire["board"]["blocked"], [[0, 4], [0, 5]])
        self.assertEqual(wire["roles"]["A"]["vectors"], [[0, -1], [0, 1]])
        renamed = copy.deepcopy(wire); renamed["id"] = "renamed-only"
        self.assertEqual(definition_hash(definition), definition_hash(parse_definition(renamed)))
        semantic = copy.deepcopy(wire); semantic["roles"]["A"]["max_distance"] = 4
        self.assertNotEqual(definition_hash(definition), definition_hash(parse_definition(semantic)))
        without_id = copy.deepcopy(wire); del without_id["id"]
        expected = hashlib.sha256(
            HASH_DOMAIN + json.dumps(without_id, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        self.assertEqual(definition_hash(definition), expected)
        self.assertEqual(json.loads(canonical_json(definition)), wire)

    def test_explicit_tile_orientations_have_hand_counted_placements(self):
        definition = parse_definition(mixed_fixture())
        actions = legal_actions(definition, initial_state(definition))
        self.assertEqual(len(actions), 8)
        self.assertEqual(actions, tuple(sorted(set(actions))))
        self.assertTrue(all(action.kind == "TILE" and len(action.cells) == 2 for action in actions))
        rendered = [action_to_dict(definition, action)["cells"] for action in actions]
        self.assertIn([[0, 0], [0, 1]], rendered)
        self.assertIn([[0, 0], [1, 0]], rendered)
        self.assertNotIn([[0, 0], [1, 1]], rendered)
        poisoned = actions[0]
        object.__setattr__(poisoned, "cells", (0, 2))  # canonical, but not either shape
        with self.assertRaises(ValueError):
            apply_action(definition, initial_state(definition), poisoned)
        fresh = legal_actions(definition, initial_state(definition))
        self.assertEqual(len(fresh), 8)
        self.assertNotIn(Action("TILE", cells=(0, 2)), fresh)

    def test_trail_rays_stop_at_pieces_and_closed_cells(self):
        definition = parse_definition(trail_fixture())
        state = initial_state(definition)
        a_actions = legal_actions(definition, state)
        from_top_left = [action.destination for action in a_actions if action.source == 0]
        self.assertEqual(from_top_left, [1, 2])  # B at index3 stops the ray.
        b_actions = legal_actions(definition, state, Player.B)
        self.assertIn(Action("TRAIL", source=9, destination=10), b_actions)
        self.assertNotIn(Action("TRAIL", source=9, destination=11), b_actions)  # own B piece

        moved = apply_action(definition, state, Action("TRAIL", source=0, destination=2))
        self.assertTrue(moved.closed & 1)
        self.assertNotIn(0, moved.a)
        self.assertFalse(any(action.destination == 0 for action in legal_actions(definition, moved, Player.A)))
        self.assertEqual(free_cells(definition, moved), free_cells(definition, state) - 1)

    def test_no_legal_action_has_one_winner_including_initially(self):
        definition = parse_definition(immobile_fixture())
        state = initial_state(definition)
        self.assertEqual(state.winner, Player.B)
        self.assertEqual(legal_actions(definition, state), ())
        self.assertEqual(state_to_dict(definition, state)["winner"], "B")
        with self.assertRaises(ValueError):
            apply_action(definition, state, Action("TILE", cells=(0,)))
        forged_live = type(state)(state.closed, state.a, state.b, state.to_move, state.plies)
        with self.assertRaises(ValueError):
            free_cells(definition, forged_live)

        single = parse_definition(single_vs_domino_fixture())
        single_start = initial_state(single)
        forged_terminal = type(single_start)(
            single_start.closed, single_start.a, single_start.b,
            single_start.to_move, single_start.plies, Player.B,
        )
        with self.assertRaises(ValueError):
            state_to_dict(single, forged_terminal)
        terminal = apply_action(single, single_start, Action("TILE", cells=(1,)))
        self.assertEqual(terminal.winner, Player.A)
        self.assertEqual(terminal.to_move, Player.B)

    def test_capacity_decreases_by_tile_area_and_one_trail_origin(self):
        definition = parse_definition(mixed_fixture())
        start = initial_state(definition)
        tiled = apply_action(definition, start, Action("TILE", cells=(0, 1)))
        self.assertEqual(free_cells(definition, start) - free_cells(definition, tiled), 2)
        trail = Action("TRAIL", source=4, destination=7)
        moved = apply_action(definition, tiled, trail)
        self.assertEqual(free_cells(definition, tiled) - free_cells(definition, moved), 1)
        self.assertTrue(moved.closed & (1 << 4))
        certificate = termination_certificate(definition)
        self.assertEqual(certificate["proof_type"], "STRICT_EMPTY_CAPACITY")
        self.assertEqual(certificate["initial_capacity"], free_cells(definition, start))
        self.assertEqual(certificate["maximum_legal_plies"], free_cells(definition, start))

    def test_all_tiny_continuations_end_inside_capacity_bound(self):
        definitions = [
            parse_definition(single_vs_domino_fixture()),
            parse_definition(domino_vs_single_fixture()),
            parse_definition(symmetric_domino_fixture()),
            parse_definition(trail_fixture()),
            parse_definition(mixed_fixture()),
        ]
        aggregate = 0
        for definition in definitions:
            initial = initial_state(definition)
            cap = free_cells(definition, initial)
            pending, seen = [initial], set()
            terminals = 0
            while pending:
                state = pending.pop()
                if state in seen:
                    continue
                seen.add(state); aggregate += 1
                self.assertLessEqual(aggregate, 100000)
                self.assertLessEqual(state.plies, cap)
                if state.winner is not None:
                    terminals += 1
                    self.assertIn(state.winner, (Player.A, Player.B))
                    continue
                before = free_cells(definition, state)
                actions = legal_actions(definition, state)
                self.assertTrue(actions)
                for action in actions:
                    successor = apply_action(definition, state, action)
                    self.assertLess(free_cells(definition, successor), before)
                    pending.append(successor)
            self.assertGreater(terminals, 0)

    def test_action_serialization_replay_and_illegal_records(self):
        definition = parse_definition(domino_vs_single_fixture())
        first = Action("TILE", cells=(0, 1))
        state = apply_action(definition, initial_state(definition), first)
        second = legal_actions(definition, state)[0]
        direct = apply_action(definition, state, second)
        wires = [action_to_dict(definition, first), action_to_dict(definition, second)]
        self.assertEqual(replay(definition, wires), direct)
        self.assertEqual(action_from_dict(definition, wires[0]), first)
        with self.assertRaises((ValueError, DefinitionError)):
            action_from_dict(definition, {"kind": "TILE", "cells": [[0, 1], [0, 0]]})
        with self.assertRaises(ValueError):
            replay(definition, wires + [wires[1]])
        with self.assertRaises(ValueError):
            apply_action(definition, initial_state(definition), Action("TILE", cells=(0,)))

        trails = parse_definition(trail_fixture())
        forged = legal_actions(trails, initial_state(trails))[0]
        object.__setattr__(forged, "destination", True)  # bool equals integer1
        with self.assertRaises(ValueError):
            apply_action(trails, initial_state(trails), forged)
        with self.assertRaises(ValueError):
            action_to_dict(trails, forged)

    def test_asymmetry_uses_capabilities_modulo_isometry(self):
        symmetric = parse_definition(symmetric_domino_fixture())
        self.assertEqual(asymmetry_witness(symmetric)["reason"], "NOT_ESTABLISHED")

        rotated = _wire(
            "rotated-equal-dominoes", 2, 2,
            _tile(((0, 0), (0, 1))), _tile(((0, 0), (1, 0))),
        )
        self.assertFalse(asymmetry_witness(parse_definition(rotated))["mechanically_asymmetric"])
        trail = parse_definition(trail_fixture())
        self.assertEqual(asymmetry_witness(trail)["reason"], "DIFFERENT_TRAIL_PIECE_COUNTS")
        renamed_starts = trail_fixture()
        renamed_starts["roles"]["B"] = copy.deepcopy(renamed_starts["roles"]["A"])
        renamed_starts["roles"]["B"]["starts"] = [[0, 5], [1, 5]]
        self.assertFalse(asymmetry_witness(parse_definition(renamed_starts))["mechanically_asymmetric"])
        self.assertEqual(asymmetry_witness(parse_definition(mixed_fixture()))["reason"], "DIFFERENT_ACTION_KINDS")

        clipped = _wire(
            "range-clipped-equivalence", 7, 7,
            _trail(((0, 1),), 6, ((0, 0),)), _trail(((1, 0),), 7, ((6, 6),)),
        )
        self.assertFalse(asymmetry_witness(parse_definition(clipped))["mechanically_asymmetric"])
        rectangular = _wire(
            "rectangular-direction-conservative", 2, 7,
            _trail(((0, 1),), 6, ((0, 0),)), _trail(((-1, 0),), 6, ((1, 6),)),
        )
        self.assertFalse(asymmetry_witness(parse_definition(rectangular))["mechanically_asymmetric"])
        unusable = _wire(
            "unusable-directions-equivalence", 1, 4,
            _trail(((-1, 0),), 2, ((0, 0),)), _trail(((-1, 0), (1, 0)), 2, ((0, 3),)),
        )
        self.assertFalse(asymmetry_witness(parse_definition(unusable))["mechanically_asymmetric"])
        effective_range = _wire(
            "effective-range-difference", 1, 7,
            _trail(((0, 1),), 2, ((0, 0),)), _trail(((0, -1),), 3, ((0, 6),)),
        )
        self.assertEqual(asymmetry_witness(parse_definition(effective_range))["reason"],
                         "INEQUIVALENT_TRAIL_EFFECTIVE_RANGES")

    def test_values_are_immutable_hashable_and_rules_are_japanese(self):
        definition = parse_definition(mixed_fixture())
        state = initial_state(definition)
        self.assertIsInstance(hash(definition), int)
        self.assertIsInstance(hash(state), int)
        self.assertIsInstance(hash(legal_actions(definition, state)[0]), int)
        with self.assertRaises(Exception):
            definition.rows = 9
        rules = describe_rules(definition)
        self.assertIsInstance(rules, tuple)
        self.assertTrue(any("引き分け" in line for line in rules))
        self.assertTrue(any("永久閉鎖" in line for line in rules))


if __name__ == "__main__":
    unittest.main()
