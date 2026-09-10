import ast
import hashlib
import json
import subprocess
import sys
import textwrap
import unittest
from contextlib import ExitStack
from enum import Enum
from pathlib import Path
from unittest import mock

from parity_forge.family import (
    NONRETIRED_ACTION_PRIMITIVES_V1 as REGISTERED_NONRETIRED_ACTIONS,
    ActionPrimitive as RegisteredActionPrimitive,
    GoalPrimitive as RegisteredGoalPrimitive,
    RoleSignature as RegisteredRoleSignature,
)
import parity_forge_universe.typed_occupancy as universe


ActionPrimitive = universe.ActionPrimitive
GoalPrimitive = universe.GoalPrimitive
RoleSignature = universe.RoleSignature


_ACTION_GOALS = {
    "PLACE": ("C", "R"),
    "MOVE": ("C", "R"),
    "MOVE_CAPTURE": ("C", "R", "E"),
    "PUSH": ("C", "R"),
    "SWAP": ("C", "R"),
    "HOP": ("C", "R"),
    "CONVERT": ("C", "R", "E"),
}
_PROFILE_MULTIPLICITY = {
    action: 1 if action == "PLACE" else 3 for action in _ACTION_GOALS
}
_V4_ACTIONS = frozenset(("PUSH", "SWAP", "HOP", "CONVERT"))
_FRAME_STABILIZERS = {
    ("C", "C"): (4, 4),
    ("C", "R"): (2, 2),
    ("C", "E"): (4,),
    ("R", "C"): (2, 2),
    ("R", "R"): (2, 2, 1),
    ("R", "E"): (2,),
    ("E", "C"): (4,),
    ("E", "R"): (2,),
    ("E", "E"): (8,),
}
_OLD_SPECS = (
    ("PUSH", "R", "HOP", "R"),
    ("SWAP", "C", "HOP", "R"),
    ("CONVERT", "C", "PUSH", "R"),
    ("MOVE_CAPTURE", "E", "HOP", "R"),
    ("CONVERT", "E", "MOVE_CAPTURE", "E"),
    ("PUSH", "C", "SWAP", "C"),
)


def _independent_profiled_histogram():
    counts = {1: 0, 2: 0, 4: 0, 8: 0}
    total = 0
    for action_a, goals_a in _ACTION_GOALS.items():
        for action_b, goals_b in _ACTION_GOALS.items():
            profile_weight = (
                _PROFILE_MULTIPLICITY[action_a]
                * _PROFILE_MULTIPLICITY[action_b]
            )
            for goal_a in goals_a:
                for goal_b in goals_b:
                    if not (
                        {action_a, action_b} & _V4_ACTIONS
                        or "E" in (goal_a, goal_b)
                    ):
                        continue
                    for stabilizer in _FRAME_STABILIZERS[(goal_a, goal_b)]:
                        counts[stabilizer] += profile_weight
                        total += profile_weight
    return total, counts


def _independent_old_histogram():
    counts = {1: 0, 2: 0, 4: 0, 8: 0}
    for action_a, goal_a, action_b, goal_b in _OLD_SPECS:
        weight = (
            _PROFILE_MULTIPLICITY[action_a]
            * _PROFILE_MULTIPLICITY[action_b]
        )
        # Each registered class contributes its source and reverse-role image.
        for stabilizer in _FRAME_STABILIZERS[(goal_a, goal_b)]:
            counts[stabilizer] += 2 * weight
    return counts


class GrammarArithmeticTests(unittest.TestCase):
    def test_pure_vocabulary_matches_the_frozen_family_boundary(self):
        registered_actions = tuple(
            action.value
            for action in RegisteredActionPrimitive
            if action is not RegisteredActionPrimitive.CAPTURE_STEP
        )
        self.assertEqual(
            tuple(action.value for action in ActionPrimitive),
            registered_actions,
        )
        self.assertEqual(
            {action.value for action in ActionPrimitive},
            {action.value for action in REGISTERED_NONRETIRED_ACTIONS},
        )
        self.assertEqual(
            tuple(goal.value for goal in GoalPrimitive),
            tuple(goal.value for goal in RegisteredGoalPrimitive),
        )
        for atom in universe.enumerate_role_atoms():
            registered = RegisteredRoleSignature(
                RegisteredActionPrimitive(atom.action_primitive.value),
                RegisteredGoalPrimitive(atom.goal_primitive.value),
            )
            self.assertEqual(atom.to_dict(), registered.to_dict())

    def test_independent_semantic_closed_form(self):
        atom_count = sum(len(goals) for goals in _ACTION_GOALS.values())
        legacy_spatial_atom_count = sum(
            len(tuple(goal for goal in goals if goal != "E"))
            for action, goals in _ACTION_GOALS.items()
            if action not in _V4_ACTIONS
        )
        ordered_count = atom_count**2
        rejected_count = legacy_spatial_atom_count**2
        admitted_count = ordered_count - rejected_count
        fixed_by_swap = atom_count - legacy_spatial_atom_count
        neutral_count = (admitted_count + fixed_by_swap) // 2

        self.assertEqual(atom_count, 16)
        self.assertEqual(legacy_spatial_atom_count, 6)
        self.assertEqual(
            (
                len(universe.enumerate_role_atoms()),
                len(universe.enumerate_ordered_semantic_signatures()),
                rejected_count,
                len(universe.enumerate_admitted_semantic_signatures()),
                fixed_by_swap,
                len(universe.enumerate_role_neutral_semantic_classes()),
                len(universe.enumerate_fresh_semantic_classes()),
            ),
            (16, 256, 36, 220, 10, 115, 109),
        )
        self.assertEqual((admitted_count, neutral_count), (220, 115))

    def test_independent_profiled_and_burnside_arithmetic(self):
        ordered_count, all_histogram = _independent_profiled_histogram()
        self_histogram = {1: 12, 2: 24, 4: 24, 8: 6}
        old_histogram = _independent_old_histogram()
        fresh_histogram = {
            stabilizer: (
                all_histogram[stabilizer]
                - self_histogram[stabilizer]
                - old_histogram[stabilizer]
            )
            // 2
            for stabilizer in all_histogram
        }

        self.assertEqual(ordered_count, 3300)
        self.assertEqual(all_histogram, {1: 312, 2: 2100, 4: 852, 8: 36})
        self.assertEqual(sum(self_histogram.values()), 66)
        self.assertEqual(old_histogram, {1: 18, 2: 126, 4: 36, 8: 18})
        self.assertEqual(sum(old_histogram.values()), 198)
        self.assertEqual(fresh_histogram, {1: 141, 2: 975, 4: 396, 8: 6})
        self.assertEqual(sum(fresh_histogram.values()), 1518)

        ordered = universe.enumerate_admitted_profiled_skeletons()
        self_isomorphic = universe.enumerate_self_isomorphic_profiled_skeletons()
        old = universe.enumerate_plan0013_profiled_region_closure()
        fresh = universe.enumerate_fresh_canonical_profiled_skeletons()
        self.assertEqual(
            (len(ordered), len(self_isomorphic), len(old), len(fresh)),
            (3300, 66, 198, 1518),
        )

        def observed(values):
            result = {}
            for value in values:
                size = universe.profiled_skeleton_d4_stabilizer_size(value)
                result[size] = result.get(size, 0) + 1
            return result

        self.assertEqual(observed(ordered), all_histogram)
        self.assertEqual(observed(self_isomorphic), self_histogram)
        self.assertEqual(observed(old), old_histogram)
        self.assertEqual(observed(fresh), fresh_histogram)
        self.assertEqual((3300 - 66 - 198) // 2, 1518)


class SpatialQuotientTests(unittest.TestCase):
    def test_goal_frames_are_the_complete_14_and_10_quotients(self):
        raw_frames = universe.enumerate_raw_goal_frames()
        frames = universe.enumerate_goal_frames()
        expected = (
            ("CONNECT_CONNECT_SAME_AXIS", 4),
            ("CONNECT_CONNECT_PERPENDICULAR", 4),
            ("CONNECT_REACH_ALIGNED", 2),
            ("CONNECT_REACH_PERPENDICULAR", 2),
            ("CONNECT_ELIMINATE", 4),
            ("REACH_CONNECT_ALIGNED", 2),
            ("REACH_CONNECT_PERPENDICULAR", 2),
            ("REACH_REACH_SAME", 2),
            ("REACH_REACH_OPPOSITE", 2),
            ("REACH_REACH_ADJACENT", 1),
            ("REACH_ELIMINATE", 2),
            ("ELIMINATE_CONNECT", 4),
            ("ELIMINATE_REACH", 2),
            ("ELIMINATE_ELIMINATE", 8),
        )
        self.assertEqual(
            tuple(
                (frame.kind.value, universe.goal_frame_d4_stabilizer_size(frame))
                for frame in frames
            ),
            expected,
        )
        self.assertEqual(len(raw_frames), (2 + 4 + 1) ** 2)
        self.assertEqual(len({json.dumps(frame.to_dict(), sort_keys=True) for frame in raw_frames}), 49)
        self.assertEqual(len(universe.enumerate_role_neutral_goal_frames()), 10)
        self.assertEqual(
            sum(
                1
                for _goal_a in ("C", "R", "E")
                for _goal_b in ("C", "R", "E")
            ),
            9,
        )

        # Each representative is the byte-minimum of its full ordered D4 orbit.
        for frame in frames:
            images = [
                universe.transform_goal_frame(frame, transform).to_dict()
                for transform in universe.D4Transform
            ]
            encoded = [
                json.dumps(value, sort_keys=True, separators=(",", ":"))
                for value in images
            ]
            self.assertEqual(
                json.dumps(frame.to_dict(), sort_keys=True, separators=(",", ":")),
                min(encoded),
            )

    def test_vector_profiles_exhaust_all_nonempty_invariant_moore_subsets(self):
        expected_by_name = {
            "ORTHOGONAL_4": frozenset(
                ((-1, 0), (0, -1), (0, 1), (1, 0))
            ),
            "DIAGONAL_4": frozenset(
                ((-1, -1), (-1, 1), (1, -1), (1, 1))
            ),
            "KING_8": frozenset(
                (row, column)
                for row in (-1, 0, 1)
                for column in (-1, 0, 1)
                if (row, column) != (0, 0)
            ),
        }
        expected = set(expected_by_name.values())
        derived = {
            frozenset(vectors)
            for vectors in universe.enumerate_d4_invariant_vector_sets()
        }
        self.assertEqual(derived, expected)
        profiles = universe.enumerate_movement_vector_profiles()
        self.assertEqual(
            tuple(profile.value for profile in profiles),
            ("ORTHOGONAL_4", "DIAGONAL_4", "KING_8"),
        )
        self.assertEqual(
            {frozenset(universe.vector_profile_vectors(profile)) for profile in profiles},
            expected,
        )
        self.assertEqual(
            {
                profile.value: frozenset(
                    universe.vector_profile_vectors(profile)
                )
                for profile in profiles
            },
            expected_by_name,
        )
        self.assertEqual(
            universe.vector_profile_vectors(universe.VectorProfile.NONE), ()
        )

    def test_named_d4_actions_have_the_preregistered_edge_meaning(self):
        expected_top_image = {
            "I": "TOP",
            "R90": "RIGHT",
            "R180": "BOTTOM",
            "R270": "LEFT",
            "FLR": "TOP",
            "FTB": "BOTTOM",
            "FD": "LEFT",
            "FA": "RIGHT",
        }
        source = universe.GoalFrame(
            universe.GoalTarget(
                GoalPrimitive.REACH_EDGE, (universe.BoardEdge.TOP,)
            ),
            universe.GoalTarget(GoalPrimitive.ELIMINATE, ()),
        )
        observed = {}
        for transform in universe.D4Transform:
            transformed = universe.transform_goal_frame(source, transform)
            observed[transform.value] = transformed.role_a.edges[0].value
        self.assertEqual(observed, expected_top_image)

    def test_d4_inverses_restore_every_goal_frame(self):
        inverse = {
            "I": "I",
            "R90": "R270",
            "R180": "R180",
            "R270": "R90",
            "FLR": "FLR",
            "FTB": "FTB",
            "FD": "FD",
            "FA": "FA",
        }
        for frame in universe.enumerate_goal_frames():
            for transform in universe.D4Transform:
                restored = universe.transform_goal_frame(
                    universe.transform_goal_frame(frame, transform),
                    universe.D4Transform(inverse[transform.value]),
                )
                self.assertEqual(restored, frame)


class CanonicalSkeletonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ordered = universe.enumerate_admitted_profiled_skeletons()

    def test_every_ordered_source_has_an_exact_inverse_witness(self):
        canonical_hashes = set()
        for source in self.ordered:
            result = universe.canonicalize_profiled_skeleton(source)
            self.assertEqual(
                universe.reconstruct_profiled_skeleton_source(result.witness), source
            )
            self.assertEqual(result.witness.source_goal_frame, source.goal_frame)
            self.assertEqual(
                result.witness.source_vector_profiles, source.vector_profiles
            )
            self.assertEqual(
                result.canonical_json,
                universe.canonical_profiled_skeleton_json(result.witness.canonical),
            )
            self.assertEqual(
                result.canonical_hash,
                hashlib.sha256(
                    b"parity-forge:typed-occupancy:role-neutral-skeleton:v1\0"
                    + result.canonical_json.encode("utf-8")
                ).hexdigest(),
            )
            canonical_hashes.add(result.canonical_hash)
        # Includes 66 fixed points plus half of the other ordered skeletons.
        self.assertEqual(len(canonical_hashes), (3300 + 66) // 2)

    def test_canonical_identity_is_d4_and_complete_swap_invariant(self):
        for index, source in enumerate(self.ordered[::37]):
            transform = tuple(universe.D4Transform)[index % 8]
            transformed = universe.transform_profiled_skeleton(source, transform)
            swapped = universe.role_swap_profiled_skeleton(transformed)
            expected = universe.role_neutral_profiled_skeleton_hash(source)
            self.assertEqual(
                universe.role_neutral_profiled_skeleton_hash(transformed), expected
            )
            self.assertEqual(
                universe.role_neutral_profiled_skeleton_hash(swapped), expected
            )

    def test_self_isomorphism_uses_the_ordered_orbit_not_neutral_hash(self):
        self_values = universe.enumerate_self_isomorphic_profiled_skeletons()
        self.assertEqual(len(self_values), 66)
        for skeleton in self_values:
            self.assertEqual(skeleton.role_a.signature, skeleton.role_b.signature)
            self.assertIs(
                skeleton.role_a.vector_profile, skeleton.role_b.vector_profile
            )

        source = next(
            skeleton
            for skeleton in self_values
            if skeleton.role_a.vector_profile
            is universe.VectorProfile.ORTHOGONAL_4
        )
        unequal_profile = universe.ProfiledSkeleton(
            source.universe_version,
            source.role_a,
            universe.ProfiledRole(
                source.role_b.signature,
                universe.VectorProfile.KING_8,
                source.role_b.goal_target,
            ),
        )
        self.assertFalse(
            universe.is_role_swap_d4_self_isomorphic(unequal_profile)
        )
        self.assertEqual(
            universe.role_neutral_profiled_skeleton_hash(unequal_profile),
            universe.role_neutral_profiled_skeleton_hash(
                universe.role_swap_profiled_skeleton(unequal_profile)
            ),
        )

        adjacent = next(
            skeleton
            for skeleton in self_values
            if skeleton.goal_frame.kind
            is universe.GoalFrameKind.REACH_REACH_ADJACENT
        )
        self.assertEqual(
            universe.profiled_skeleton_d4_stabilizer_size(adjacent), 1
        )
        self.assertTrue(universe.is_role_swap_d4_self_isomorphic(adjacent))

    def test_exact_and_role_neutral_hash_domains_are_distinct(self):
        source = next(
            skeleton
            for skeleton in self.ordered
            if universe.profiled_skeleton_d4_stabilizer_size(skeleton) == 1
            and not universe.is_role_swap_d4_self_isomorphic(skeleton)
        )
        transformed = universe.transform_profiled_skeleton(
            source, universe.D4Transform.R90
        )
        self.assertNotEqual(
            universe.profiled_skeleton_hash(source),
            universe.profiled_skeleton_hash(transformed),
        )
        self.assertEqual(
            universe.role_neutral_profiled_skeleton_hash(source),
            universe.role_neutral_profiled_skeleton_hash(transformed),
        )
        self.assertNotEqual(
            universe.profiled_skeleton_hash(
                universe.canonicalize_profiled_skeleton(source).witness.canonical
            ),
            universe.role_neutral_profiled_skeleton_hash(source),
        )


class OldRegionFirewallTests(unittest.TestCase):
    def test_six_public_semantic_classes_close_under_swap(self):
        old = universe.enumerate_plan0013_semantic_classes()
        self.assertEqual(len(old), 6)
        neutral_hashes = set()
        ordered_hashes = set()
        for source in old:
            swapped = universe.role_swap_semantic_signature(source)
            self.assertTrue(universe.is_plan0013_semantic_region(source))
            self.assertTrue(universe.is_plan0013_semantic_region(swapped))
            neutral_hashes.add(universe.role_neutral_semantic_hash(source))
            ordered_hashes.add(universe.semantic_signature_hash(source))
            ordered_hashes.add(universe.semantic_signature_hash(swapped))
            self.assertEqual(
                universe.role_neutral_semantic_hash(source),
                universe.role_neutral_semantic_hash(swapped),
            )
        self.assertEqual(len(neutral_hashes), 6)
        self.assertEqual(len(ordered_hashes), 12)

        fresh_hashes = {
            universe.role_neutral_semantic_hash(signature)
            for signature in universe.enumerate_fresh_semantic_classes()
        }
        self.assertTrue(neutral_hashes.isdisjoint(fresh_hashes))

    def test_old_profiled_closure_is_198_ordered_and_99_neutral(self):
        closure = universe.enumerate_plan0013_profiled_region_closure()
        self.assertEqual(len(closure), 198)
        self.assertTrue(all(universe.is_plan0013_profiled_region(s) for s in closure))
        self.assertEqual(
            len(
                {
                    universe.role_neutral_profiled_skeleton_hash(skeleton)
                    for skeleton in closure
                }
            ),
            99,
        )
        self.assertTrue(
            set(closure).isdisjoint(
                universe.enumerate_self_isomorphic_profiled_skeletons()
            )
        )

    def test_exact_old_membership_and_one_field_near_neighbor(self):
        expected_ordered = set()
        goal_names = {"C": "CONNECT_EDGES", "R": "REACH_EDGE", "E": "ELIMINATE"}
        for action_a, goal_a, action_b, goal_b in _OLD_SPECS:
            source = (action_a, goal_names[goal_a], action_b, goal_names[goal_b])
            expected_ordered.add(source)
            expected_ordered.add((source[2], source[3], source[0], source[1]))

        observed = set()
        for signature in universe.enumerate_admitted_semantic_signatures():
            key = (
                signature.role_a.action_primitive.value,
                signature.role_a.goal_primitive.value,
                signature.role_b.action_primitive.value,
                signature.role_b.goal_primitive.value,
            )
            if universe.is_plan0013_semantic_region(signature):
                observed.add(key)
        self.assertEqual(observed, expected_ordered)

        neighbor = universe.SemanticSignature(
            1,
            RoleSignature(ActionPrimitive.PUSH, GoalPrimitive.CONNECT_EDGES),
            RoleSignature(ActionPrimitive.HOP, GoalPrimitive.REACH_EDGE),
        )
        self.assertFalse(universe.is_plan0013_semantic_region(neighbor))


class StrictBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.source = universe.enumerate_admitted_profiled_skeletons()[0]
        self.raw = json.loads(
            universe.canonical_profiled_skeleton_json(self.source)
        )

    def test_strict_parser_roundtrip_and_input_detachment(self):
        parsed = universe.parse_profiled_skeleton(self.raw)
        canonical = universe.canonical_profiled_skeleton_json(parsed)
        self.assertEqual(parsed, self.source)
        self.raw["roles"]["A"]["target_edges"].append("LEFT")
        self.assertEqual(
            universe.canonical_profiled_skeleton_json(parsed), canonical
        )

    def test_parser_rejects_nonexact_types_unknowns_and_aliases(self):
        class DictAlias(dict):
            pass

        with self.assertRaisesRegex(TypeError, "exact object"):
            universe.parse_profiled_skeleton(DictAlias(self.raw))

        cases = []
        raw = json.loads(universe.canonical_profiled_skeleton_json(self.source))
        raw["universe_version"] = True
        cases.append((raw, TypeError))
        raw = json.loads(universe.canonical_profiled_skeleton_json(self.source))
        raw["unknown"] = 1
        cases.append((raw, ValueError))
        raw = json.loads(universe.canonical_profiled_skeleton_json(self.source))
        del raw["roles"]["B"]["goal_primitive"]
        cases.append((raw, ValueError))
        raw = json.loads(universe.canonical_profiled_skeleton_json(self.source))
        raw["roles"]["A"]["target_edges"] = tuple(
            raw["roles"]["A"]["target_edges"]
        )
        cases.append((raw, TypeError))
        raw = json.loads(universe.canonical_profiled_skeleton_json(self.source))
        raw["roles"]["A"]["action_primitive"] = ActionPrimitive.PUSH
        cases.append((raw, TypeError))
        raw = json.loads(universe.canonical_profiled_skeleton_json(self.source))
        raw["roles"]["A"]["action_primitive"] = "CAPTURE_STEP"
        cases.append((raw, ValueError))
        for value, error_type in cases:
            with self.subTest(value=value, error_type=error_type):
                with self.assertRaises(error_type):
                    universe.parse_profiled_skeleton(value)

    def test_parser_rejects_noncanonical_edges_and_profiles(self):
        connect = next(
            skeleton
            for skeleton in universe.enumerate_admitted_profiled_skeletons()
            if skeleton.role_a.signature.goal_primitive
            is GoalPrimitive.CONNECT_EDGES
        )
        raw = json.loads(universe.canonical_profiled_skeleton_json(connect))
        raw["roles"]["A"]["target_edges"].reverse()
        with self.assertRaisesRegex(ValueError, "canonical opposite-edge axis"):
            universe.parse_profiled_skeleton(raw)

        raw = json.loads(universe.canonical_profiled_skeleton_json(connect))
        raw["roles"]["A"]["vector_profile"] = "NONE"
        if raw["roles"]["A"]["action_primitive"] == "PLACE":
            raw["roles"]["B"]["vector_profile"] = "NONE"
        with self.assertRaisesRegex(ValueError, "non-PLACE"):
            universe.parse_profiled_skeleton(raw)

    def test_parser_rejects_poisoned_enum_value_lookup_tables(self):
        semantic_raw = {
            "universe_version": 1,
            "roles": {
                "A": {
                    "action_primitive": "PUSH",
                    "goal_primitive": "REACH_EDGE",
                },
                "B": {
                    "action_primitive": "HOP",
                    "goal_primitive": "REACH_EDGE",
                },
            },
        }
        with mock.patch.dict(
            ActionPrimitive._value2member_map_,
            {"PUSH": ActionPrimitive.SWAP},
        ):
            with self.assertRaisesRegex(ValueError, "value map changed"):
                universe.parse_semantic_signature(semantic_raw)

        raw = json.loads(universe.canonical_profiled_skeleton_json(self.source))
        edge_name = raw["roles"]["A"]["target_edges"][0]
        wrong_edge = next(
            edge for edge in universe.BoardEdge if edge.value != edge_name
        )
        with mock.patch.dict(
            universe.BoardEdge._value2member_map_, {edge_name: wrong_edge}
        ):
            with self.assertRaisesRegex(ValueError, "value map changed"):
                universe.parse_profiled_skeleton(raw)

    def test_incoherent_eliminate_and_legacy_only_pairs_fail_closed(self):
        raw_signature = {
            "universe_version": 1,
            "roles": {
                "A": {
                    "action_primitive": "PLACE",
                    "goal_primitive": "ELIMINATE",
                },
                "B": {
                    "action_primitive": "PUSH",
                    "goal_primitive": "REACH_EDGE",
                },
            },
        }
        with self.assertRaisesRegex(ValueError, "ELIMINATE requires"):
            universe.parse_semantic_signature(raw_signature)

        target = universe.GoalTarget(
            GoalPrimitive.REACH_EDGE, (universe.BoardEdge.TOP,)
        )
        with self.assertRaisesRegex(ValueError, "schema-v4"):
            universe.ProfiledSkeleton(
                1,
                universe.ProfiledRole(
                    RoleSignature(ActionPrimitive.PLACE, GoalPrimitive.REACH_EDGE),
                    universe.VectorProfile.NONE,
                    target,
                ),
                universe.ProfiledRole(
                    RoleSignature(ActionPrimitive.MOVE, GoalPrimitive.REACH_EDGE),
                    universe.VectorProfile.ORTHOGONAL_4,
                    target,
                ),
            )

    def test_mutated_and_hidden_exact_type_objects_are_rejected(self):
        source = universe.parse_profiled_skeleton(
            json.loads(universe.canonical_profiled_skeleton_json(self.source))
        )
        object.__setattr__(source, "hidden_field", "forged")
        with self.assertRaisesRegex(ValueError, "noncanonical fields"):
            universe.canonical_profiled_skeleton_json(source)

        source = universe.parse_profiled_skeleton(
            json.loads(universe.canonical_profiled_skeleton_json(self.source))
        )
        object.__setattr__(source.role_a.goal_target, "edges", [])
        with self.assertRaises((TypeError, ValueError)):
            universe.canonical_profiled_skeleton_json(source)

        result = universe.canonicalize_profiled_skeleton(self.source)
        object.__setattr__(
            result.witness, "inverse_transform", universe.D4Transform.R90
        )
        with self.assertRaises(ValueError):
            universe.reconstruct_profiled_skeleton_source(result.witness)

    def test_valid_to_valid_nested_mutation_is_rejected_at_identity_boundaries(self):
        source = next(
            skeleton
            for skeleton in universe.enumerate_admitted_profiled_skeletons()
            if skeleton.role_a.signature.action_primitive is ActionPrimitive.PUSH
            and skeleton.role_a.signature.goal_primitive
            is GoalPrimitive.CONNECT_EDGES
        )
        object.__setattr__(
            source.role_a.signature, "action_primitive", ActionPrimitive.SWAP
        )
        operations = (
            universe.canonical_profiled_skeleton_json,
            universe.profiled_skeleton_hash,
            universe.canonicalize_profiled_skeleton,
            universe.role_neutral_profiled_skeleton_hash,
            universe.role_swap_profiled_skeleton,
            universe.is_role_swap_d4_self_isomorphic,
            universe.profiled_skeleton_d4_stabilizer_size,
            universe.is_plan0013_profiled_region,
        )
        for operation in operations:
            with self.subTest(operation=operation.__name__):
                with self.assertRaises(ValueError):
                    operation(source)
        with self.assertRaises(ValueError):
            universe.transform_profiled_skeleton(source, universe.D4Transform.I)

    def test_all_value_constructors_detach_their_inputs(self):
        role_a = RoleSignature(ActionPrimitive.PUSH, GoalPrimitive.REACH_EDGE)
        role_b = RoleSignature(ActionPrimitive.HOP, GoalPrimitive.REACH_EDGE)
        target_a = universe.GoalTarget(
            GoalPrimitive.REACH_EDGE, (universe.BoardEdge.TOP,)
        )
        target_b = universe.GoalTarget(
            GoalPrimitive.REACH_EDGE, (universe.BoardEdge.BOTTOM,)
        )
        semantic = universe.SemanticSignature(1, role_a, role_b)
        frame = universe.GoalFrame(target_a, target_b)
        profiled_a = universe.ProfiledRole(
            role_a, universe.VectorProfile.ORTHOGONAL_4, target_a
        )
        profiled_b = universe.ProfiledRole(
            role_b, universe.VectorProfile.KING_8, target_b
        )
        skeleton = universe.ProfiledSkeleton(1, profiled_a, profiled_b)
        semantic_before = universe.canonical_semantic_signature_json(semantic)
        frame_before = frame.to_dict()
        skeleton_before = universe.canonical_profiled_skeleton_json(skeleton)

        object.__setattr__(role_a, "action_primitive", ActionPrimitive.SWAP)
        object.__setattr__(target_a, "edges", (universe.BoardEdge.LEFT,))
        object.__setattr__(profiled_b.signature, "action_primitive", ActionPrimitive.SWAP)

        self.assertEqual(
            universe.canonical_semantic_signature_json(semantic), semantic_before
        )
        self.assertEqual(frame.to_dict(), frame_before)
        self.assertEqual(
            universe.canonical_profiled_skeleton_json(skeleton), skeleton_before
        )

        result = universe.canonicalize_profiled_skeleton(skeleton)
        copied = universe.SkeletonCanonicalization(
            result.canonical_hash, result.canonical_json, result.witness
        )
        object.__setattr__(result.witness.source.role_a.signature, "action_primitive", ActionPrimitive.SWAP)
        self.assertEqual(copied.to_dict()["canonical_hash"], copied.canonical_hash)

    def test_invalid_forged_nested_target_is_rejected_by_parent_constructor(self):
        target = universe.GoalTarget(
            GoalPrimitive.REACH_EDGE, (universe.BoardEdge.TOP,)
        )
        object.__setattr__(target, "edges", ())
        with self.assertRaises((TypeError, ValueError)):
            universe.ProfiledRole(
                RoleSignature(ActionPrimitive.PUSH, GoalPrimitive.REACH_EDGE),
                universe.VectorProfile.ORTHOGONAL_4,
                target,
            )

    def test_role_atom_is_strict_coherent_and_mutation_evident(self):
        for action in (
            ActionPrimitive.PLACE,
            ActionPrimitive.MOVE,
            ActionPrimitive.PUSH,
            ActionPrimitive.SWAP,
            ActionPrimitive.HOP,
        ):
            with self.subTest(action=action.value):
                with self.assertRaisesRegex(ValueError, "ELIMINATE requires"):
                    RoleSignature(action, GoalPrimitive.ELIMINATE)

        role = RoleSignature(ActionPrimitive.PUSH, GoalPrimitive.REACH_EDGE)
        object.__setattr__(role, "action_primitive", ActionPrimitive.SWAP)
        with self.assertRaisesRegex(ValueError, "changed after construction"):
            role.to_dict()
        with self.assertRaises(ValueError):
            universe.SemanticSignature(
                1,
                role,
                RoleSignature(ActionPrimitive.HOP, GoalPrimitive.REACH_EDGE),
            )

        role = RoleSignature(ActionPrimitive.PUSH, GoalPrimitive.REACH_EDGE)
        object.__setattr__(
            role, "action_primitive", RegisteredActionPrimitive.SWAP
        )
        with self.assertRaises(TypeError):
            role.to_dict()

        role = RoleSignature(ActionPrimitive.PUSH, GoalPrimitive.REACH_EDGE)
        object.__setattr__(role, "hidden_field", "forged")
        with self.assertRaisesRegex(ValueError, "noncanonical fields"):
            role.to_dict()

        role = RoleSignature(ActionPrimitive.PUSH, GoalPrimitive.REACH_EDGE)
        original_action_value = ActionPrimitive.PUSH.value
        object.__setattr__(ActionPrimitive.PUSH, "_value_", "SWAP")
        try:
            with self.assertRaisesRegex(
                ValueError, "action primitive vocabulary changed"
            ):
                role.to_dict()
            with self.assertRaisesRegex(
                ValueError, "action primitive vocabulary changed"
            ):
                RoleSignature(
                    ActionPrimitive.PUSH, GoalPrimitive.REACH_EDGE
                )
        finally:
            object.__setattr__(
                ActionPrimitive.PUSH, "_value_", original_action_value
            )

        role = RoleSignature(ActionPrimitive.PUSH, GoalPrimitive.REACH_EDGE)
        original_goal_value = GoalPrimitive.REACH_EDGE.value
        object.__setattr__(GoalPrimitive.REACH_EDGE, "_value_", "ELIMINATE")
        try:
            with self.assertRaisesRegex(
                ValueError, "goal primitive vocabulary changed"
            ):
                role.to_dict()
        finally:
            object.__setattr__(
                GoalPrimitive.REACH_EDGE, "_value_", original_goal_value
            )

    def test_every_serialized_enum_rejects_singleton_value_tampering(self):
        role = RoleSignature(ActionPrimitive.PUSH, GoalPrimitive.REACH_EDGE)
        reach = universe.GoalTarget(
            GoalPrimitive.REACH_EDGE, (universe.BoardEdge.TOP,)
        )
        eliminate = universe.GoalTarget(GoalPrimitive.ELIMINATE, ())
        frame = universe.GoalFrame(reach, eliminate)
        profiled = universe.ProfiledRole(
            role, universe.VectorProfile.ORTHOGONAL_4, reach
        )

        class StringAlias(str):
            pass

        def rejects(
            member, attribute, forged_value, operation, expected_error
        ):
            original_value = getattr(member, attribute)
            object.__setattr__(member, attribute, forged_value)
            try:
                with self.assertRaisesRegex(
                    (expected_error, universe.UniverseClosureError), "vocabulary"
                ):
                    operation()
            finally:
                object.__setattr__(member, attribute, original_value)

        cases = (
            (
                ActionPrimitive.PUSH,
                "FORGED_ACTION",
                role.to_dict,
            ),
            (
                GoalPrimitive.REACH_EDGE,
                "FORGED_GOAL",
                reach.to_dict,
            ),
            (
                universe.BoardEdge.TOP,
                "FORGED_EDGE",
                reach.to_dict,
            ),
            (
                universe.VectorProfile.ORTHOGONAL_4,
                "FORGED_PROFILE",
                profiled.to_dict,
            ),
            (
                universe.VectorProfile.ORTHOGONAL_4,
                "FORGED_PROFILE",
                universe.enumerate_movement_vector_profiles,
            ),
            (
                universe.D4Transform.R90,
                "FORGED_TRANSFORM",
                lambda: universe.transform_goal_frame(
                    frame, universe.D4Transform.R90
                ),
            ),
            (
                universe.GoalFrameKind.REACH_ELIMINATE,
                "FORGED_FRAME_KIND",
                lambda: frame.kind,
            ),
        )
        for member, forged_value, operation in cases:
            member_name = member.name
            for attribute in ("_value_", "_name_"):
                original_value = getattr(member, attribute)
                foreign_type = Enum(
                    "Foreign{}{}".format(member_name, attribute),
                    {"TOKEN": original_value},
                    type=str,
                )
                carriers = (
                    ("different exact string", forged_value, ValueError),
                    (
                        "same-valued string subclass",
                        StringAlias(original_value),
                        TypeError,
                    ),
                    (
                        "same-valued foreign enum",
                        foreign_type.TOKEN,
                        TypeError,
                    ),
                )
                for carrier, replacement, expected_error in carriers:
                    with self.subTest(
                        member=member_name,
                        attribute=attribute,
                        carrier=carrier,
                    ):
                        rejects(
                            member,
                            attribute,
                            replacement,
                            operation,
                            expected_error,
                        )

    def test_enumerated_values_do_not_share_mutable_identity_carriers(self):
        signatures = universe.enumerate_ordered_semantic_signatures()
        role_ids = [id(role) for signature in signatures for role in signature.roles]
        self.assertEqual(len(role_ids), len(set(role_ids)))

        skeletons = universe.enumerate_admitted_profiled_skeletons()
        profiled_roles = [
            role for skeleton in skeletons for role in (skeleton.role_a, skeleton.role_b)
        ]
        self.assertEqual(
            len(profiled_roles), len({id(role) for role in profiled_roles})
        )
        nested_roles = [role.signature for role in profiled_roles]
        nested_targets = [role.goal_target for role in profiled_roles]
        self.assertEqual(len(nested_roles), len({id(role) for role in nested_roles}))
        self.assertEqual(
            len(nested_targets), len({id(target) for target in nested_targets})
        )


class SealedAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.atoms = universe.enumerate_role_atoms()
        cls.signature = universe.SemanticSignature(1, cls.atoms[0], cls.atoms[-1])

    def test_all_enum_registry_carriers_fail_closed(self):
        cases = (
            (ActionPrimitive, universe.enumerate_role_atoms),
            (GoalPrimitive, universe.enumerate_raw_goal_frames),
            (universe.BoardEdge, universe.enumerate_raw_goal_frames),
            (universe.D4Transform, universe.enumerate_d4_invariant_vector_sets),
            (universe.VectorProfile, universe.enumerate_movement_vector_profiles),
            (universe.GoalFrameKind, universe.enumerate_goal_frames),
        )
        for enum_type, public_call in cases:
            member_names = enum_type._member_names_
            saved_names = list(member_names)
            name_attacks = (
                ("reverse", list(reversed(saved_names))),
                ("drop", saved_names[:-1]),
                ("duplicate", saved_names[:-1] + [saved_names[-2]]),
            )
            for attack_name, poison in name_attacks:
                with self.subTest(
                    enum=enum_type.__name__,
                    carrier="_member_names_",
                    attack=attack_name,
                ):
                    try:
                        member_names[:] = poison
                        with self.assertRaises(universe.UniverseClosureError):
                            public_call()
                    finally:
                        member_names[:] = saved_names

            for carrier_name in ("_member_map_", "_value2member_map_"):
                carrier = getattr(enum_type, carrier_name)
                saved = dict(carrier)
                keys = list(saved)
                swapped = dict(saved)
                swapped[keys[0]], swapped[keys[1]] = (
                    swapped[keys[1]],
                    swapped[keys[0]],
                )
                extra = dict(saved)
                extra["FORGED_ALIAS"] = saved[keys[0]]
                for attack_name, poison in (
                    ("wrong-target", swapped),
                    ("extra-alias", extra),
                ):
                    with self.subTest(
                        enum=enum_type.__name__,
                        carrier=carrier_name,
                        attack=attack_name,
                    ):
                        try:
                            carrier.clear()
                            carrier.update(poison)
                            with self.assertRaises(universe.UniverseClosureError):
                                public_call()
                        finally:
                            carrier.clear()
                            carrier.update(saved)

    def test_public_version_binding_and_input_fail_closed(self):
        baseline = universe.canonical_semantic_signature_json(self.signature)

        class IntAlias(int):
            pass

        for forged_binding in (2, True, IntAlias(1), "1"):
            with self.subTest(binding=forged_binding):
                with mock.patch.object(
                    universe,
                    "TYPED_OCCUPANCY_UNIVERSE_VERSION",
                    forged_binding,
                ):
                    with self.assertRaises(universe.UniverseClosureError):
                        universe.SemanticSignature(1, self.atoms[0], self.atoms[-1])
                    with self.assertRaises(universe.UniverseClosureError):
                        universe.canonical_semantic_signature_json(self.signature)
                    with self.assertRaises(universe.UniverseClosureError):
                        universe.enumerate_ordered_semantic_signatures()

        for forged_input in (2, True, IntAlias(1), 1.0):
            with self.subTest(input=forged_input):
                with self.assertRaises((TypeError, ValueError)):
                    universe.SemanticSignature(
                        forged_input, self.atoms[0], self.atoms[-1]
                    )
        self.assertEqual(
            universe.canonical_semantic_signature_json(self.signature), baseline
        )

    def test_public_enumerators_reject_foreign_enum_class_rebindings(self):
        cases = (
            ("ActionPrimitive", universe.enumerate_role_atoms),
            ("GoalPrimitive", universe.enumerate_raw_goal_frames),
            ("BoardEdge", universe.enumerate_raw_goal_frames),
            ("D4Transform", universe.enumerate_d4_invariant_vector_sets),
            ("VectorProfile", universe.enumerate_movement_vector_profiles),
            ("GoalFrameKind", universe.enumerate_goal_frames),
        )
        for binding, public_call in cases:
            enum_type = getattr(universe, binding)
            foreign = Enum(
                enum_type.__name__,
                [(name, name) for name in enum_type._member_names_],
                type=str,
                module=universe.__name__,
            )
            with self.subTest(enum=binding):
                with mock.patch.object(universe, binding, foreign):
                    with self.assertRaises(universe.UniverseClosureError):
                        public_call()

    def test_public_enum_value_boundaries_reject_registry_aliases(self):
        target = universe.GoalTarget(
            GoalPrimitive.REACH_EDGE, (universe.BoardEdge.TOP,)
        )
        frame = universe.GoalFrame(target, target)
        role = RoleSignature(ActionPrimitive.PUSH, GoalPrimitive.REACH_EDGE)
        cases = (
            (
                ActionPrimitive,
                ActionPrimitive.PUSH,
                lambda: RoleSignature(
                    ActionPrimitive["FORGED_ALIAS"], GoalPrimitive.REACH_EDGE
                ),
            ),
            (
                GoalPrimitive,
                GoalPrimitive.REACH_EDGE,
                lambda: RoleSignature(
                    ActionPrimitive.PUSH, GoalPrimitive["FORGED_ALIAS"]
                ),
            ),
            (
                universe.BoardEdge,
                universe.BoardEdge.TOP,
                lambda: universe.GoalTarget(
                    GoalPrimitive.REACH_EDGE,
                    (universe.BoardEdge["FORGED_ALIAS"],),
                ),
            ),
            (
                universe.D4Transform,
                universe.D4Transform.I,
                lambda: universe.transform_goal_frame(
                    frame, universe.D4Transform["FORGED_ALIAS"]
                ),
            ),
            (
                universe.VectorProfile,
                universe.VectorProfile.ORTHOGONAL_4,
                lambda: universe.ProfiledRole(
                    role,
                    universe.VectorProfile["FORGED_ALIAS"],
                    target,
                ),
            ),
            (
                universe.GoalFrameKind,
                universe.GoalFrameKind.REACH_REACH_SAME,
                lambda: frame.kind,
            ),
        )
        for enum_type, aliased_member, public_call in cases:
            member_map = enum_type._member_map_
            saved = dict(member_map)
            with self.subTest(enum=enum_type.__name__):
                try:
                    member_map["FORGED_ALIAS"] = aliased_member
                    with self.assertRaises(universe.UniverseClosureError):
                        public_call()
                finally:
                    member_map.clear()
                    member_map.update(saved)

    def test_consistent_non_enum_member_forgery_fails_closed(self):
        class FakeMember:
            def __init__(self, name):
                self._name_ = name
                self._value_ = name

            @property
            def name(self):
                return self._name_

            @property
            def value(self):
                return self._value_

        enum_type = universe.VectorProfile
        name = "ORTHOGONAL_4"
        original_member = enum_type.ORTHOGONAL_4
        original_member_map = dict(enum_type._member_map_)
        original_value_map = dict(enum_type._value2member_map_)
        forged = FakeMember(name)
        try:
            type.__setattr__(enum_type, name, forged)
            enum_type._member_map_[name] = forged
            enum_type._value2member_map_[name] = forged
            with self.assertRaises(universe.UniverseClosureError):
                universe.enumerate_movement_vector_profiles()
        finally:
            type.__setattr__(enum_type, name, original_member)
            enum_type._member_map_.clear()
            enum_type._member_map_.update(original_member_map)
            enum_type._value2member_map_.clear()
            enum_type._value2member_map_.update(original_value_map)

    def test_consistent_exact_member_permutations_fail_closed(self):
        cases = (
            (ActionPrimitive, universe.enumerate_role_atoms),
            (GoalPrimitive, universe.enumerate_raw_goal_frames),
            (universe.BoardEdge, universe.enumerate_raw_goal_frames),
            (universe.D4Transform, universe.enumerate_d4_invariant_vector_sets),
            (universe.VectorProfile, universe.enumerate_movement_vector_profiles),
            (universe.GoalFrameKind, universe.enumerate_goal_frames),
        )
        for enum_type, public_call in cases:
            names = list(enum_type._member_names_)
            first_name, second_name = names[:2]
            first = enum_type.__dict__[first_name]
            second = enum_type.__dict__[second_name]
            member_map = enum_type._member_map_
            value_map = enum_type._value2member_map_
            saved_member_map = dict(member_map)
            saved_value_map = dict(value_map)
            saved_carriers = (
                first.__dict__["_name_"],
                first.__dict__["_value_"],
                second.__dict__["_name_"],
                second.__dict__["_value_"],
            )
            with self.subTest(enum=enum_type.__name__):
                try:
                    type.__setattr__(enum_type, first_name, second)
                    type.__setattr__(enum_type, second_name, first)
                    object.__setattr__(second, "_name_", first_name)
                    object.__setattr__(second, "_value_", first_name)
                    object.__setattr__(first, "_name_", second_name)
                    object.__setattr__(first, "_value_", second_name)
                    member_map[first_name] = second
                    member_map[second_name] = first
                    value_map[first_name] = second
                    value_map[second_name] = first
                    with self.assertRaisesRegex(
                        universe.UniverseClosureError,
                        "member identity carrier changed",
                    ):
                        public_call()
                finally:
                    object.__setattr__(first, "_name_", saved_carriers[0])
                    object.__setattr__(first, "_value_", saved_carriers[1])
                    object.__setattr__(second, "_name_", saved_carriers[2])
                    object.__setattr__(second, "_value_", saved_carriers[3])
                    type.__setattr__(enum_type, first_name, first)
                    type.__setattr__(enum_type, second_name, second)
                    member_map.clear()
                    member_map.update(saved_member_map)
                    value_map.clear()
                    value_map.update(saved_value_map)

    def test_consistent_exact_forged_singletons_fail_closed(self):
        cases = (
            (ActionPrimitive, universe.enumerate_role_atoms),
            (GoalPrimitive, universe.enumerate_raw_goal_frames),
            (universe.BoardEdge, universe.enumerate_raw_goal_frames),
            (universe.D4Transform, universe.enumerate_d4_invariant_vector_sets),
            (universe.VectorProfile, universe.enumerate_movement_vector_profiles),
            (universe.GoalFrameKind, universe.enumerate_goal_frames),
        )
        for enum_type, public_call in cases:
            name = enum_type._member_names_[0]
            original = enum_type.__dict__[name]
            member_map = enum_type._member_map_
            value_map = enum_type._value2member_map_
            saved_member_map = dict(member_map)
            saved_value_map = dict(value_map)
            forged = str.__new__(enum_type, name)
            object.__setattr__(forged, "_name_", name)
            object.__setattr__(forged, "_value_", name)
            with self.subTest(enum=enum_type.__name__):
                try:
                    type.__setattr__(enum_type, name, forged)
                    member_map[name] = forged
                    value_map[name] = forged
                    with self.assertRaises(universe.UniverseClosureError):
                        public_call()
                finally:
                    type.__setattr__(enum_type, name, original)
                    member_map.clear()
                    member_map.update(saved_member_map)
                    value_map.clear()
                    value_map.update(saved_value_map)


class DescriptorAndCapabilityTests(unittest.TestCase):
    _REMOVED_SEMANTIC_AUTHORITIES = (
        "_ACTIVE_ACTIONS",
        "_SCHEMA_V4_ACTIONS",
        "_MATERIAL_REDUCING_ACTIONS",
        "_SPATIAL_GOALS",
        "_EDGE_ORDER",
        "_CONNECT_AXES",
        "_OPPOSITE_EDGE",
        "_EDGE_MAP",
        "_INVERSE_TRANSFORM",
        "_MOORE_VECTORS",
        "_ORTHOGONAL_VECTORS",
        "_DIAGONAL_VECTORS",
        "_PROFILE_VECTOR_SETS",
        "_PLAN0013_SEMANTIC_SPECS",
    )
    _REMOVED_CERTIFICATION_AUTHORITIES = (
        "_SEMANTIC_HASH_DOMAIN",
        "_ROLE_NEUTRAL_SEMANTIC_HASH_DOMAIN",
        "_SKELETON_HASH_DOMAIN",
        "_ROLE_NEUTRAL_SKELETON_HASH_DOMAIN",
        "_ROLE_ATOM_ROOT_DOMAIN",
        "_ORDERED_SEMANTIC_ROOT_DOMAIN",
        "_GOAL_FRAME_ROOT_DOMAIN",
        "_RAW_GOAL_FRAME_ROOT_DOMAIN",
        "_ROLE_NEUTRAL_GOAL_FRAME_ROOT_DOMAIN",
        "_ADMITTED_SIGNATURE_ROOT_DOMAIN",
        "_ROLE_NEUTRAL_SEMANTIC_ROOT_DOMAIN",
        "_FRESH_SEMANTIC_ROOT_DOMAIN",
        "_OLD_SEMANTIC_ROOT_DOMAIN",
        "_SEMANTIC_MAPPING_ROOT_DOMAIN",
        "_VECTOR_PROFILE_DEFINITION_ROOT_DOMAIN",
        "_D4_DEFINITION_ROOT_DOMAIN",
        "_ORDERED_SKELETON_ROOT_DOMAIN",
        "_SELF_ISOMORPHIC_ROOT_DOMAIN",
        "_OLD_REGION_ROOT_DOMAIN",
        "_OLD_REGION_NEUTRAL_ROOT_DOMAIN",
        "_FRESH_CANONICAL_ROOT_DOMAIN",
        "_FULL_WITNESS_MAPPING_ROOT_DOMAIN",
        "_DESCRIPTOR_ROOT_DOMAIN",
        "_EXPECTED_COUNTS",
        "_EXPECTED_HISTOGRAMS",
        "_EXPECTED_ROOTS",
        "_EXPECTED_DESCRIPTOR_ROOT",
    )

    @classmethod
    def setUpClass(cls):
        cls.descriptor = universe.build_universe_descriptor()

    def test_descriptor_counts_histograms_and_roots_are_golden(self):
        descriptor = self.descriptor
        self.assertEqual(dict(descriptor.counts), {
            "admitted_ordered_profiled_skeleton_count": 3300,
            "admitted_ordered_signature_count": 220,
            "fresh_canonical_skeleton_count": 1518,
            "fresh_semantic_class_count": 109,
            "legacy_rejected_ordered_signature_count": 36,
            "movement_vector_profile_count": 3,
            "old_region_ordered_skeleton_count": 198,
            "old_region_role_neutral_skeleton_count": 99,
            "old_semantic_class_count": 6,
            "ordered_goal_frame_count": 14,
            "ordered_semantic_product_count": 256,
            "role_atom_count": 16,
            "role_neutral_goal_frame_count": 10,
            "role_neutral_semantic_class_count": 115,
            "role_swap_fixed_signature_count": 10,
            "self_isomorphic_ordered_skeleton_count": 66,
        })
        histograms = {
            name: dict(entries) for name, entries in descriptor.histograms
        }
        self.assertEqual(
            histograms["goal_frame_d4_stabilizer"],
            {"1": 1, "2": 8, "4": 4, "8": 1},
        )
        self.assertEqual(
            histograms["all_skeleton_d4_stabilizer"],
            {"1": 312, "2": 2100, "4": 852, "8": 36},
        )
        self.assertEqual(
            histograms["self_isomorphic_d4_stabilizer"],
            {"1": 12, "2": 24, "4": 24, "8": 6},
        )
        self.assertEqual(
            histograms["old_region_d4_stabilizer"],
            {"1": 18, "2": 126, "4": 36, "8": 18},
        )
        self.assertEqual(
            histograms["fresh_canonical_d4_stabilizer"],
            {"1": 141, "2": 975, "4": 396, "8": 6},
        )
        self.assertEqual(dict(descriptor.roots), {
            "admitted_signature_root": "1ac9fe901ca02b209915d717fa936cee11d6b9a3d8b081317fc134d0a9a141c4",
            "d4_definition_root": "b89efcb15a66b71a584ffae101716104c616aa3235e36eb3086bee02be4d464e",
            "fresh_canonical_skeleton_root": "ca02a2bbd844962fd83c7190eec69dea51877940ea6f0836c5a00338a3e9e190",
            "fresh_semantic_root": "d24dd0d6c2e5f923e5b6b758125f311e590d319c6e03069cc76d1a9ac001df91",
            "full_witness_mapping_root": "6095576351eb9c937efa3a14a03bd376b0ca11a102aac99922bb00895eb68389",
            "goal_frame_root": "5e5185604ea940301150e6144d3834619786318b76e49433eafef142327a4164",
            "old_region_ordered_skeleton_root": "6c678dffab9dbcdec4a21b2c8c8cef4a61e57a4ee21ae2a1906d5b574060fdc2",
            "old_region_role_neutral_skeleton_root": "a75aa32b576d1a8988bb8def141211877f53e5f2fda55e71e884eb70f9d45ff8",
            "old_semantic_root": "f2747aa13ed6419df0bbfda4110cadafb2c779cb3709420dfc2cb963fe6c4464",
            "ordered_profiled_skeleton_root": "3170c498af35c6f2b13bbdfc7297e3527160ae0cbc1fe602cbe3a89b2bae1d78",
            "ordered_semantic_signature_root": "e03dc3a28577649444b45c3f540ddbd8ea622a1df686b9069218db17083cc9e0",
            "raw_goal_frame_root": "47128e2a247272fc4bce152ebfb06a81b8df7d50544bd621d5ae79ca5a78a338",
            "role_atom_root": "f2286dfc7c0e1d4053612bf37e4e1bfc87c4d9b4ace616cc6007cf9df820e2b0",
            "role_neutral_goal_frame_root": "c6e806e6b9f1d50ac891931d5f1772bf4ad733bf370eaa009e8bb13e9b8146db",
            "role_neutral_semantic_root": "64704a4f9434167e26df82ed1222b42165e59ae5f1ec73c445eb9aa337ef0cf4",
            "self_isomorphic_ordered_skeleton_root": "7825bb7a70ee9d373d2a6971bd991bba5d60e8ce3f251a0a00f416d56cb8c539",
            "semantic_mapping_root": "7079e33bb347bfe0316c3b5c356fda9827ed9a557363016f3c01e6c04f1fe20b",
            "vector_profile_definition_root": "dc2c19b42ba6514fd16dd4e76b7c4c995f5b94c824defc19e6bf96c3cd17bb3f",
        })
        self.assertEqual(
            descriptor.descriptor_root,
            "05826dc2da02890f3f562ee2d6febda523c58837affb757b5dff6d62c074e6ab",
        )
        self.assertEqual(
            {name for name, _digest in descriptor.roots},
            {name for name, _first, _last in descriptor.endpoints},
        )
        canonical = universe.canonical_universe_descriptor_json(descriptor)
        self.assertEqual(json.loads(canonical), descriptor.to_dict())

    def test_descriptor_mutation_breaks_the_seal(self):
        source = self.descriptor
        descriptor = universe.UniverseDescriptor(
            source.universe_version,
            source.counts,
            source.histograms,
            source.roots,
            source.endpoints,
            source.descriptor_root,
        )
        object.__setattr__(descriptor, "descriptor_root", "0" * 64)
        with self.assertRaises(ValueError):
            universe.canonical_universe_descriptor_json(descriptor)

    def test_descriptor_methods_reject_hidden_duplicate_and_reordered_carriers(self):
        source = self.descriptor

        class IntAlias(int):
            pass

        class StrAlias(str):
            pass

        def fresh_descriptor():
            return universe.UniverseDescriptor(
                source.universe_version,
                source.counts,
                source.histograms,
                source.roots,
                source.endpoints,
                source.descriptor_root,
            )

        mutations = {
            "histogram duplicate shadow": (
                "histograms",
                ((source.histograms[0][0], (("forged", 1),)),)
                + source.histograms,
            ),
            "root duplicate shadow": (
                "roots",
                ((source.roots[0][0], "0" * 64),) + source.roots,
            ),
            "endpoint duplicate shadow": (
                "endpoints",
                ((source.endpoints[0][0], "forged-first", "forged-last"),)
                + source.endpoints,
            ),
            "histogram reorder": (
                "histograms",
                tuple(reversed(source.histograms)),
            ),
            "root reorder": ("roots", tuple(reversed(source.roots))),
            "endpoint reorder": (
                "endpoints",
                tuple(reversed(source.endpoints)),
            ),
            "version integer alias": ("universe_version", IntAlias(1)),
            "histogram name string alias": (
                "histograms",
                (
                    (
                        StrAlias(source.histograms[0][0]),
                        source.histograms[0][1],
                    ),
                )
                + source.histograms[1:],
            ),
        }
        for label, (field_name, replacement) in mutations.items():
            operations = (
                ("payload_dict", lambda value: value.payload_dict()),
                ("to_dict", lambda value: value.to_dict()),
                (
                    "canonical_json",
                    universe.canonical_universe_descriptor_json,
                ),
            )
            for operation_name, operation in operations:
                with self.subTest(label=label, operation=operation_name):
                    descriptor = fresh_descriptor()
                    object.__setattr__(descriptor, field_name, replacement)
                    with self.assertRaises((TypeError, ValueError)):
                        operation(descriptor)

    def test_empty_self_sealed_descriptor_and_nonexact_shapes_are_rejected(self):
        empty_payload = {
            "universe_version": 1,
            "counts": {},
            "histograms": {},
            "roots": {},
            "endpoints": {},
        }
        empty_root = hashlib.sha256(
            b"parity-forge:typed-occupancy:descriptor:v1\0"
            + json.dumps(
                empty_payload, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()
        with self.assertRaises(universe.UniverseClosureError):
            universe.UniverseDescriptor(1, (), (), (), (), empty_root)

        descriptor = self.descriptor
        with self.assertRaises(TypeError):
            universe.UniverseDescriptor(
                1,
                list(descriptor.counts),
                descriptor.histograms,
                descriptor.roots,
                descriptor.endpoints,
                descriptor.descriptor_root,
            )
        malformed_roots = (list(descriptor.roots[0]),) + descriptor.roots[1:]
        with self.assertRaises(TypeError):
            universe.UniverseDescriptor(
                1,
                descriptor.counts,
                descriptor.histograms,
                malformed_roots,
                descriptor.endpoints,
                descriptor.descriptor_root,
            )
        uppercase_roots = (
            (descriptor.roots[0][0], descriptor.roots[0][1].upper()),
        ) + descriptor.roots[1:]
        with self.assertRaises(ValueError):
            universe.UniverseDescriptor(
                1,
                descriptor.counts,
                descriptor.histograms,
                uppercase_roots,
                descriptor.endpoints,
                descriptor.descriptor_root,
            )

    def test_canonicalization_constructors_reject_forged_values(self):
        source = universe.enumerate_admitted_profiled_skeletons()[37]
        result = universe.canonicalize_profiled_skeleton(source)
        with self.assertRaises(ValueError):
            universe.SkeletonCanonicalization(
                "z" * 64, result.canonical_json, result.witness
            )
        with self.assertRaises(ValueError):
            universe.SkeletonCanonicalization(
                result.canonical_hash, "not-json", result.witness
            )
        with self.assertRaises(ValueError):
            universe.SkeletonCanonicalization(
                "0" * 64, result.canonical_json, result.witness
            )

        wrong_transform = next(
            transform
            for transform in universe.D4Transform
            if transform is not result.witness.transform
        )
        inverse_names = {
            "I": "I",
            "R90": "R270",
            "R180": "R180",
            "R270": "R90",
            "FLR": "FLR",
            "FTB": "FTB",
            "FD": "FD",
            "FA": "FA",
        }
        with self.assertRaises(ValueError):
            universe.SkeletonOrbitWitness(
                result.witness.source,
                result.witness.canonical,
                wrong_transform,
                universe.D4Transform(inverse_names[wrong_transform.value]),
                result.witness.role_swapped,
                result.witness.source_goal_frame,
                result.witness.source_vector_profiles,
            )

    def test_witness_rejects_valid_forward_map_with_nonminimum_tie_break(self):
        source = universe.enumerate_admitted_profiled_skeletons()[0]
        result = universe.canonicalize_profiled_skeleton(source)
        alternate = universe.D4Transform.R180
        self.assertIs(result.witness.transform, universe.D4Transform.I)
        self.assertFalse(result.witness.role_swapped)
        self.assertEqual(
            universe.transform_profiled_skeleton(source, alternate),
            result.witness.canonical,
        )
        with self.assertRaisesRegex(ValueError, "byte minimum"):
            universe.SkeletonOrbitWitness(
                source,
                result.witness.canonical,
                alternate,
                alternate,
                False,
                source.goal_frame,
                source.vector_profiles,
            )

    def test_ordered_root_frames_count_ordinal_length_and_endpoints(self):
        domain = b"independent-test-domain\0"
        values = ("alpha", "beta", "gamma")
        digest = hashlib.sha256(domain)
        digest.update(len(values).to_bytes(8, "big"))
        for ordinal, value in enumerate(values):
            encoded = value.encode("utf-8")
            digest.update(ordinal.to_bytes(8, "big"))
            digest.update(len(encoded).to_bytes(8, "big"))
            digest.update(encoded)
        root = universe._sequence_root(domain, values)
        self.assertEqual(root, digest.hexdigest())
        self.assertNotEqual(root, universe._sequence_root(domain, tuple(reversed(values))))
        self.assertNotEqual(root, universe._sequence_root(domain, values[:-1]))
        self.assertNotEqual(root, universe._sequence_root(domain, values + (values[-1],)))

        endpoints = {
            name: (first, last)
            for name, first, last in self.descriptor.endpoints
        }
        self.assertEqual(
            endpoints["role_atom_root"],
            (
                '{"action_primitive":"PLACE","goal_primitive":"CONNECT_EDGES"}',
                '{"action_primitive":"CONVERT","goal_primitive":"ELIMINATE"}',
            ),
        )
        self.assertEqual(
            endpoints["vector_profile_definition_root"],
            (
                '{"profile":"NONE","vectors":[]}',
                '{"profile":"KING_8","vectors":[[-1,-1],[-1,0],[-1,1],[0,-1],[0,1],[1,-1],[1,0],[1,1]]}',
            ),
        )

    def test_semantic_choice_code_mutation_breaks_official_descriptor(self):
        def choose_max(signature):
            swapped = universe.SemanticSignature(
                signature.universe_version, signature.role_b, signature.role_a
            )
            return max(
                (signature, swapped),
                key=lambda item: json.dumps(
                    item.to_dict(), sort_keys=True, separators=(",", ":")
                ),
            )

        with mock.patch.object(
            universe, "_role_neutral_semantic_choice", choose_max
        ):
            with self.assertRaises(universe.UniverseClosureError):
                universe.build_universe_descriptor()

    def test_removed_data_authority_shadows_are_inert(self):
        authority_names = (
            self._REMOVED_SEMANTIC_AUTHORITIES
            + self._REMOVED_CERTIFICATION_AUTHORITIES
        )
        for name in authority_names:
            self.assertNotIn(name, vars(universe))

        source = universe.enumerate_admitted_profiled_skeletons()[17]
        signature = source.semantic_signature
        frame = source.goal_frame
        baselines = {
            "atoms": tuple(atom.to_dict() for atom in universe.enumerate_role_atoms()),
            "raw_frames": tuple(
                item.to_dict() for item in universe.enumerate_raw_goal_frames()
            ),
            "profiles": tuple(
                (
                    profile.value,
                    universe.vector_profile_vectors(profile),
                )
                for profile in universe.enumerate_movement_vector_profiles()
            ),
            "old": tuple(
                item.to_dict()
                for item in universe.enumerate_plan0013_semantic_classes()
            ),
            "transformed_frame": universe.transform_goal_frame(
                frame, universe.D4Transform.R90
            ).to_dict(),
            "semantic_hash": universe.semantic_signature_hash(signature),
            "neutral_semantic_hash": universe.role_neutral_semantic_hash(signature),
            "skeleton_hash": universe.profiled_skeleton_hash(source),
            "neutral_skeleton_hash": universe.role_neutral_profiled_skeleton_hash(
                source
            ),
        }

        with ExitStack() as stack:
            for name in authority_names:
                poison = b"forged-domain" if name.endswith("_DOMAIN") else object()
                stack.enter_context(
                    mock.patch.object(universe, name, poison, create=True)
                )
            observed = {
                "atoms": tuple(
                    atom.to_dict() for atom in universe.enumerate_role_atoms()
                ),
                "raw_frames": tuple(
                    item.to_dict() for item in universe.enumerate_raw_goal_frames()
                ),
                "profiles": tuple(
                    (
                        profile.value,
                        universe.vector_profile_vectors(profile),
                    )
                    for profile in universe.enumerate_movement_vector_profiles()
                ),
                "old": tuple(
                    item.to_dict()
                    for item in universe.enumerate_plan0013_semantic_classes()
                ),
                "transformed_frame": universe.transform_goal_frame(
                    frame, universe.D4Transform.R90
                ).to_dict(),
                "semantic_hash": universe.semantic_signature_hash(signature),
                "neutral_semantic_hash": universe.role_neutral_semantic_hash(
                    signature
                ),
                "skeleton_hash": universe.profiled_skeleton_hash(source),
                "neutral_skeleton_hash": (
                    universe.role_neutral_profiled_skeleton_hash(source)
                ),
            }
            rebuilt = universe.build_universe_descriptor()
        self.assertEqual(observed, baselines)
        self.assertEqual(rebuilt, self.descriptor)

    def test_expected_goldens_are_fresh_and_detached(self):
        counts = universe._expected_counts()
        histograms = universe._expected_histograms()
        roots = universe._expected_roots()
        counts.clear()
        histograms["all_skeleton_d4_stabilizer"].clear()
        roots.clear()
        self.assertEqual(len(universe._expected_counts()), 16)
        self.assertEqual(
            universe._expected_histograms()["all_skeleton_d4_stabilizer"],
            {"1": 312, "2": 2100, "4": 852, "8": 36},
        )
        self.assertEqual(len(universe._expected_roots()), 18)

    def test_forged_endpoint_and_matching_shadow_seal_are_rejected(self):
        source = self.descriptor
        endpoints = list(source.endpoints)
        name, first, last = endpoints[0]
        forged_first = "forged:" + first
        endpoints[0] = (name, forged_first, last)
        forged_endpoints = tuple(endpoints)
        payload = source.payload_dict()
        payload["endpoints"][name]["first"] = forged_first
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        forged_root = hashlib.sha256(
            b"parity-forge:typed-occupancy:descriptor:v1\0" + encoded
        ).hexdigest()
        with mock.patch.object(
            universe, "_EXPECTED_DESCRIPTOR_ROOT", forged_root, create=True
        ), mock.patch.object(
            universe,
            "_DESCRIPTOR_ROOT_DOMAIN",
            b"parity-forge:typed-occupancy:descriptor:v1\0",
            create=True,
        ):
            with self.assertRaises(universe.UniverseClosureError):
                universe.UniverseDescriptor(
                    1,
                    source.counts,
                    source.histograms,
                    source.roots,
                    forged_endpoints,
                    forged_root,
                )

    def test_runtime_descriptor_reconstruction_performs_no_io(self):
        with mock.patch("builtins.open", side_effect=AssertionError("file I/O")), mock.patch(
            "os.open", side_effect=AssertionError("descriptor I/O")
        ), mock.patch("socket.socket", side_effect=AssertionError("network I/O")):
            descriptor = universe.build_universe_descriptor()
        self.assertEqual(descriptor.descriptor_root, self.descriptor.descriptor_root)

    def test_isolated_import_has_the_exact_pure_module_closure(self):
        source_root = str(Path(__file__).resolve().parents[1] / "src")
        code = textwrap.dedent(
            f"""
            import builtins
            import importlib.abc
            import os
            import socket
            import sys
            sys.path.insert(0, {source_root!r})
            allowed = {{
                "parity_forge_universe",
                "parity_forge_universe.typed_occupancy",
            }}
            class Poison(importlib.abc.MetaPathFinder):
                def find_spec(self, fullname, path=None, target=None):
                    if fullname == "parity_forge" or fullname.startswith("parity_forge."):
                        raise RuntimeError("forbidden legacy package import: " + fullname)
                    if fullname.startswith("parity_forge_universe.") and fullname not in allowed:
                        raise RuntimeError("forbidden transitive import: " + fullname)
                    return None
            sys.meta_path.insert(0, Poison())
            def fail_io(*args, **kwargs):
                raise RuntimeError("forbidden import-time I/O")
            builtins.open = fail_io
            os.open = fail_io
            socket.socket = fail_io
            import parity_forge_universe.typed_occupancy
            loaded = {{
                name for name in sys.modules
                if name == "parity_forge"
                or name.startswith("parity_forge.")
                or name == "parity_forge_universe"
                or name.startswith("parity_forge_universe.")
            }}
            assert loaded == allowed, sorted(loaded)
            """
        )
        completed = subprocess.run(
            [sys.executable, "-I", "-c", code],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_production_imports_and_calls_have_no_forbidden_capability(self):
        package_root = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "parity_forge_universe"
        )
        source_paths = (
            package_root / "__init__.py",
            package_root / "typed_occupancy.py",
        )
        allowed_modules = {
            "__future__",
            "hashlib",
            "json",
            "dataclasses",
            "enum",
            "itertools",
            "typing",
        }
        imported_modules = set()
        nodes = []
        for source_path in source_paths:
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
            nodes.extend(ast.walk(tree))
        for node in nodes:
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported_modules.add(node.module)
        self.assertEqual(imported_modules - allowed_modules, set())

        forbidden_names = {
            "engine",
            "apply_action",
            "terminal_status",
            "solver",
            "solve_game",
            "agent",
            "play",
            "play_game",
            "replay",
            "telemetry",
            "atlas",
            "selection",
        }
        referenced = {
            node.id for node in nodes if isinstance(node, ast.Name)
        }
        called_attributes = {
            node.func.attr
            for node in nodes
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        called_names = {
            node.func.id
            for node in nodes
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertTrue(forbidden_names.isdisjoint(referenced))
        self.assertTrue(forbidden_names.isdisjoint(called_attributes))
        self.assertTrue(forbidden_names.isdisjoint(called_names))


if __name__ == "__main__":
    unittest.main()
