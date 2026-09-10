import hashlib
import json
import unittest

from parity_forge.dsl import Player, definition_hash, parse_definition
from parity_forge.solver import solve_game
from parity_forge.symmetry import (
    D4_TRANSFORMS,
    canonicalize_d4,
    d4_canonical_hash,
    mechanical_json,
    transform_definition,
    transform_position,
)

from tests.support import crossing_definition


def asymmetric_definition():
    raw = crossing_definition()
    raw["name"] = "Asymmetric D4 fixture"
    raw["board_size"] = 5
    raw["max_plies"] = 15
    raw["initial_pieces"][0]["position"] = [4, 1]
    raw["roles"]["B"]["action"]["vectors"] = [
        [-1, -1],
        [-1, 0],
        [0, 1],
    ]
    return parse_definition(raw)


def asymmetric_exact_definition():
    raw = crossing_definition()
    raw["name"] = "Asymmetric exact D4 fixture"
    raw["max_plies"] = 9
    raw["initial_pieces"][0]["position"] = [2, 0]
    raw["roles"]["B"]["action"]["vectors"] = [
        [-1, -1],
        [-1, 0],
        [0, 1],
    ]
    return parse_definition(raw)


class SymmetryTests(unittest.TestCase):
    def test_public_position_transform_covers_the_complete_3x3_board(self) -> None:
        expected_indices = {
            "I": (0, 1, 2, 3, 4, 5, 6, 7, 8),
            "R90": (2, 5, 8, 1, 4, 7, 0, 3, 6),
            "R180": (8, 7, 6, 5, 4, 3, 2, 1, 0),
            "R270": (6, 3, 0, 7, 4, 1, 8, 5, 2),
            "FLR": (2, 1, 0, 5, 4, 3, 8, 7, 6),
            "FTB": (6, 7, 8, 3, 4, 5, 0, 1, 2),
            "FD": (0, 3, 6, 1, 4, 7, 2, 5, 8),
            "FA": (8, 5, 2, 7, 4, 1, 6, 3, 0),
        }
        positions = tuple((index // 3, index % 3) for index in range(9))
        for transform in D4_TRANSFORMS:
            with self.subTest(transform=transform):
                observed = tuple(
                    3 * row + column
                    for row, column in (
                        transform_position(position, 3, transform)
                        for position in positions
                    )
                )
                self.assertEqual(observed, expected_indices[transform])

        with self.assertRaises(ValueError):
            transform_position((0, 0), 3, "R45")
        with self.assertRaises(TypeError):
            transform_position([0, 0], 3, "I")
        with self.assertRaises(ValueError):
            transform_position((3, 0), 3, "I")

    def test_transform_table_covers_positions_edges_and_vectors(self) -> None:
        definition = asymmetric_definition()
        expected_positions = {
            "I": (4, 1),
            "R90": (1, 0),
            "R180": (0, 3),
            "R270": (3, 4),
            "FLR": (4, 3),
            "FTB": (0, 1),
            "FD": (1, 4),
            "FA": (3, 0),
        }
        expected_connection_edges = {
            "I": {"TOP", "BOTTOM"},
            "R90": {"LEFT", "RIGHT"},
            "R180": {"TOP", "BOTTOM"},
            "R270": {"LEFT", "RIGHT"},
            "FLR": {"TOP", "BOTTOM"},
            "FTB": {"TOP", "BOTTOM"},
            "FD": {"LEFT", "RIGHT"},
            "FA": {"LEFT", "RIGHT"},
        }
        expected_target_edges = {
            "I": "TOP",
            "R90": "RIGHT",
            "R180": "BOTTOM",
            "R270": "LEFT",
            "FLR": "TOP",
            "FTB": "BOTTOM",
            "FD": "LEFT",
            "FA": "RIGHT",
        }
        expected_vectors = {
            "I": ((-1, -1), (-1, 0), (0, 1)),
            "R90": ((-1, 1), (0, 1), (1, 0)),
            "R180": ((0, -1), (1, 0), (1, 1)),
            "R270": ((-1, 0), (0, -1), (1, -1)),
            "FLR": ((-1, 0), (-1, 1), (0, -1)),
            "FTB": ((0, 1), (1, -1), (1, 0)),
            "FD": ((-1, -1), (0, -1), (1, 0)),
            "FA": ((-1, 0), (0, 1), (1, 1)),
        }

        self.assertEqual(D4_TRANSFORMS, tuple(expected_positions))
        for transform in D4_TRANSFORMS:
            with self.subTest(transform=transform):
                transformed = transform_definition(definition, transform)
                self.assertEqual(
                    transformed.initial_pieces[0].position,
                    expected_positions[transform],
                )
                self.assertEqual(
                    {edge.value for edge in transformed.role(Player.A).goal.edges},
                    expected_connection_edges[transform],
                )
                self.assertEqual(
                    transformed.role(Player.B).goal.edge.value,
                    expected_target_edges[transform],
                )
                self.assertEqual(
                    transformed.role(Player.B).action.vectors,
                    expected_vectors[transform],
                )

    def test_transform_preserves_non_spatial_fields_and_name_contract(self) -> None:
        definition = asymmetric_definition()
        transformed = transform_definition(definition, "R90")
        renamed = transform_definition(definition, "R90", name="Rotated fixture")

        self.assertEqual(transformed.name, definition.name)
        self.assertEqual(renamed.name, "Rotated fixture")
        self.assertEqual(transformed.schema_version, definition.schema_version)
        self.assertEqual(transformed.board_size, definition.board_size)
        self.assertEqual(transformed.first_player, definition.first_player)
        self.assertEqual(transformed.max_plies, definition.max_plies)
        self.assertEqual(
            transformed.initial_pieces[0].owner,
            definition.initial_pieces[0].owner,
        )
        self.assertEqual(
            transformed.role(Player.A).action.piece,
            definition.role(Player.A).action.piece,
        )
        with self.assertRaisesRegex(ValueError, "transform must be one of"):
            transform_definition(definition, "R45")

    def test_rotations_and_reflections_obey_group_identities(self) -> None:
        definition = asymmetric_definition()
        rotated = definition
        for _ in range(4):
            rotated = transform_definition(rotated, "R90")
        self.assertEqual(mechanical_json(rotated), mechanical_json(definition))

        for reflection in ("FLR", "FTB", "FD", "FA"):
            with self.subTest(reflection=reflection):
                twice = transform_definition(
                    transform_definition(definition, reflection), reflection
                )
                self.assertEqual(mechanical_json(twice), mechanical_json(definition))

    def test_all_d4_compositions_close_on_the_frozen_transform_table(self) -> None:
        definition = asymmetric_definition()
        representatives = {
            mechanical_json(transform_definition(definition, transform)): transform
            for transform in D4_TRANSFORMS
        }
        self.assertEqual(len(representatives), 8)
        for first in D4_TRANSFORMS:
            for second in D4_TRANSFORMS:
                with self.subTest(first=first, second=second):
                    composed = mechanical_json(
                        transform_definition(
                            transform_definition(definition, first), second
                        )
                    )
                    self.assertIn(composed, representatives)

    def test_mechanical_json_excludes_only_name(self) -> None:
        definition = asymmetric_definition()
        raw = definition.to_dict()
        raw["name"] = "A different display name"
        renamed = parse_definition(raw)

        self.assertNotEqual(definition_hash(definition), definition_hash(renamed))
        self.assertEqual(mechanical_json(definition), mechanical_json(renamed))
        payload = json.loads(mechanical_json(definition))
        expected = definition.to_dict()
        del expected["name"]
        self.assertEqual(payload, expected)

    def test_d4_canonicalization_is_invariant_and_uses_frozen_hash_domain(self) -> None:
        definition = asymmetric_definition()
        baseline = canonicalize_d4(definition)
        self.assertEqual(
            baseline.canonical_hash,
            hashlib.sha256(
                b"parity-forge:d4:v1\0"
                + baseline.mechanical_json.encode("utf-8")
            ).hexdigest(),
        )
        self.assertEqual(len({
            mechanical_json(transform_definition(definition, transform))
            for transform in D4_TRANSFORMS
        }), 8)

        original_hash = definition_hash(definition)
        for transform in D4_TRANSFORMS:
            with self.subTest(transform=transform):
                transformed = transform_definition(definition, transform)
                candidate = canonicalize_d4(transformed)
                self.assertEqual(candidate.canonical_hash, baseline.canonical_hash)
                self.assertEqual(candidate.mechanical_json, baseline.mechanical_json)
                self.assertEqual(d4_canonical_hash(transformed), baseline.canonical_hash)
        # D4 utilities never redefine or mutate the exact stored-definition hash.
        self.assertEqual(definition_hash(definition), original_hash)
        self.assertNotEqual(
            definition_hash(definition),
            definition_hash(transform_definition(definition, "R90")),
        )

    def test_canonical_representative_is_idempotent(self) -> None:
        definition = asymmetric_definition()
        first = canonicalize_d4(definition)
        representative = transform_definition(definition, first.transform)
        second = canonicalize_d4(representative)
        self.assertEqual(second.canonical_hash, first.canonical_hash)
        self.assertEqual(second.mechanical_json, first.mechanical_json)
        self.assertEqual(second.transform, "I")

    def test_fixed_transform_order_breaks_symmetric_ties(self) -> None:
        definition = parse_definition(crossing_definition())
        canonical = canonicalize_d4(definition)
        self.assertEqual(
            canonical.canonical_hash,
            "fffbc3b49d6c040eb4318597955c140dbbabae9903a35d85132b6d040a1b1a97",
        )
        # R180 and FTB produce the same minimal mechanics for this fixture.
        self.assertEqual(canonical.transform, "R180")
        self.assertEqual(
            mechanical_json(transform_definition(definition, "R180")),
            mechanical_json(transform_definition(definition, "FTB")),
        )

    def test_non_spatial_semantic_changes_do_not_collapse(self) -> None:
        definition = asymmetric_definition()
        first_player = definition.to_dict()
        first_player["first_player"] = "B"
        ply_limit = definition.to_dict()
        ply_limit["max_plies"] += 1

        baseline = d4_canonical_hash(definition)
        self.assertNotEqual(
            d4_canonical_hash(parse_definition(first_player)), baseline
        )
        self.assertNotEqual(d4_canonical_hash(parse_definition(ply_limit)), baseline)

    def test_schema_v2_terminal_policy_is_preserved_and_has_distinct_d4_identity(self) -> None:
        v1 = asymmetric_definition()
        raw = v1.to_dict()
        raw["schema_version"] = 2
        raw["terminal_policy"] = {"no_legal_action": "DRAW"}
        v2 = parse_definition(raw)

        self.assertNotEqual(d4_canonical_hash(v2), d4_canonical_hash(v1))
        baseline = d4_canonical_hash(v2)
        self.assertEqual(
            baseline,
            "87223dcc8e49759da06aea2f018e7b119a234ffef06e0703ff66c68133ef80f4",
        )
        for transform in D4_TRANSFORMS:
            with self.subTest(transform=transform):
                transformed = transform_definition(v2, transform)
                self.assertEqual(transformed.schema_version, 2)
                self.assertEqual(
                    transformed.to_dict()["terminal_policy"],
                    {"no_legal_action": "DRAW"},
                )
                self.assertEqual(d4_canonical_hash(transformed), baseline)

    def test_schema_v2_exact_stalemate_is_invariant_across_d4_orbit(self) -> None:
        raw = crossing_definition()
        raw["schema_version"] = 2
        raw["terminal_policy"] = {"no_legal_action": "DRAW"}
        raw["roles"]["B"]["action"]["vectors"] = [[1, 0]]
        definition = parse_definition(raw)

        for transform in D4_TRANSFORMS:
            with self.subTest(transform=transform):
                transformed = transform_definition(definition, transform)
                solved = solve_game(transformed)
                self.assertEqual(solved.forced_result, "DRAW")
                self.assertEqual(solved.terminal_reason, "NO_LEGAL_ACTION")
                self.assertEqual(len(solved.principal_variation), 1)

    def test_all_initial_pieces_are_transformed_and_reordered(self) -> None:
        raw = asymmetric_definition().to_dict()
        raw["initial_pieces"].extend(
            [
                {"owner": "A", "piece": "seed", "position": [0, 4]},
                {"owner": "A", "piece": "seed", "position": [3, 2]},
            ]
        )
        definition = parse_definition(raw)
        transformed = transform_definition(definition, "R90")
        actual = [piece.position for piece in transformed.initial_pieces]
        self.assertEqual(actual, [(1, 0), (2, 1), (4, 4)])

    def test_exact_outcome_is_invariant_across_d4_orbit(self) -> None:
        definition = asymmetric_exact_definition()
        forced_result = solve_game(definition).forced_result
        self.assertEqual(forced_result, "A_WIN")
        for transform in D4_TRANSFORMS:
            with self.subTest(transform=transform):
                transformed = transform_definition(definition, transform)
                self.assertEqual(solve_game(transformed).forced_result, forced_result)


if __name__ == "__main__":
    unittest.main()
