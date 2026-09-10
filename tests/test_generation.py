import copy
import unittest

from parity_forge.asymmetry import evaluate_asymmetry
from parity_forge.batch import BatchConfig, screen_batch
from parity_forge.dsl import Player, definition_hash, parse_definition
from parity_forge.generator import (
    GeneratorConfig,
    enumerate_v2_four_by_four_max8,
    enumerate_v2_three_by_three,
    generate_definitions,
)

from tests.support import crossing_definition


class GenerationTests(unittest.TestCase):
    def test_asymmetry_uses_mechanics(self) -> None:
        asymmetric = evaluate_asymmetry(parse_definition(crossing_definition()))
        self.assertTrue(asymmetric.qualifies)
        self.assertTrue(asymmetric.action_primitives_differ)

        raw = crossing_definition()
        raw["roles"]["B"]["action"] = {"kind": "PLACE", "piece": "runner"}
        symmetric = evaluate_asymmetry(parse_definition(raw))
        self.assertFalse(symmetric.qualifies)
        self.assertFalse(symmetric.action_primitives_differ)

    def test_generation_is_unique_and_seeded(self) -> None:
        config = GeneratorConfig(seed=99, candidate_count=20, version=1)
        first = generate_definitions(config)
        second = generate_definitions(config)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 20)
        self.assertEqual(len(set(first)), 20)
        self.assertNotEqual(first, generate_definitions(GeneratorConfig(seed=100, candidate_count=20, version=1)))

    def test_v2_starts_runner_opposite_target(self) -> None:
        definitions = generate_definitions(GeneratorConfig(seed=42, candidate_count=50, version=2))
        for definition in definitions:
            start = definition.initial_pieces[0].position
            edge = definition.role(Player.B).goal.edge
            size = definition.board_size
            expected = {
                "TOP": start[0] == size - 1,
                "BOTTOM": start[0] == 0,
                "LEFT": start[1] == size - 1,
                "RIGHT": start[1] == 0,
            }[edge.value]
            self.assertTrue(expected)

    def test_v2_three_by_three_vocabulary_is_complete_and_unique(self) -> None:
        definitions = enumerate_v2_three_by_three()
        self.assertEqual(len(definitions), 36720)
        self.assertEqual(len({definition_hash(item) for item in definitions}), 36720)
        self.assertEqual({item.board_size for item in definitions}, {3})
        self.assertEqual({item.max_plies for item in definitions}, {6, 9, 18})

    def test_v2_four_by_four_max8_vocabulary_is_complete_and_unique(self) -> None:
        definitions = enumerate_v2_four_by_four_max8()
        self.assertEqual(len(definitions), 16320)
        self.assertEqual(len({definition_hash(item) for item in definitions}), 16320)
        self.assertEqual({item.board_size for item in definitions}, {4})
        self.assertEqual({item.max_plies for item in definitions}, {8})

    def test_v2_frozen_seed_hashes_are_unchanged(self) -> None:
        definitions = generate_definitions(
            GeneratorConfig(seed=20260831, candidate_count=8, version=2)
        )
        self.assertEqual(
            [definition_hash(item) for item in definitions],
            [
                "7e2ab00f07e5399a6e9d6b7fa83242889e2fd1445b4444392a28fabd15aa6295",
                "fe1acb2a04854b564ffe99a46f43d2e4e5dbde2cc89b7ab44afb5bd88e7936b8",
                "7ca7f22c6bb47117057babe2fc2beec8faa46dd08e22ea1e7407ccac5622fb36",
                "9de4b0056e19344370426f282750b5ca060f5cd86bd3c6af9a762e5cd50d58e9",
                "4836a9a16b29a6c68c9e476a87f6a96741280ac78328e3f33b64c0f7752fa81e",
                "534741d347be26608b386599294606e7dd8d748dea0f468b5f55f93967cf2436",
                "186a26ac5ef4a86f6e7e8b86b3d10055b6b563c840ec4845ba6b2f9f89ea9063",
                "39b35fe9817dd1ea2dc398c626786e0c0330e654ab639e9c606292ace5786a3d",
            ],
        )

    def test_small_batch_semantics_repeat_exactly(self) -> None:
        config = BatchConfig(generator_seed=7, candidate_count=10, play_seeds=tuple(range(5)), generator_version=2)
        first = screen_batch(config)
        second = screen_batch(config)
        self.assertEqual(first, second)
        self.assertEqual(first["aggregate"]["generated_unique"], 10)
        self.assertLessEqual(first["aggregate"]["play_evaluated"], 10)


if __name__ == "__main__":
    unittest.main()
