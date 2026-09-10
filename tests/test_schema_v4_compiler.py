import ast
import copy
import hashlib
import json
import subprocess
import sys
import textwrap
import unittest
from itertools import combinations
from pathlib import Path
from unittest import mock

from parity_forge import dsl, symmetry
import parity_forge_universe.schema_v4_compiler as compiler
import parity_forge_universe.typed_occupancy as universe


_BOARD_CELLS = tuple((row, column) for row in range(3) for column in range(3))
_COUNT_PAIR_SUPPLIES = {
    (0, 1): 9,
    (0, 2): 36,
    (0, 3): 84,
    (1, 0): 9,
    (1, 1): 72,
    (1, 2): 252,
    (1, 3): 504,
    (2, 0): 36,
    (2, 1): 252,
    (2, 2): 756,
    (2, 3): 1260,
    (3, 0): 84,
    (3, 1): 504,
    (3, 2): 1260,
    (3, 3): 1680,
}
_D4_INVERSES = {
    "I": "I",
    "R90": "R270",
    "R180": "R180",
    "R270": "R90",
    "FLR": "FLR",
    "FTB": "FTB",
    "FD": "FD",
    "FA": "FA",
}
_FRESH_SKELETONS = None
_SETUP_ROWS = None


def _canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _fresh_skeletons():
    global _FRESH_SKELETONS
    if _FRESH_SKELETONS is None:
        _FRESH_SKELETONS = (
            universe.enumerate_fresh_canonical_profiled_skeletons()
        )
    return _FRESH_SKELETONS


def _independent_setup_rows():
    """Return the preregistered lattice without using production enumeration."""

    global _SETUP_ROWS
    if _SETUP_ROWS is None:
        rows = []
        for a_count in range(4):
            for b_count in range(4):
                if not 1 <= a_count + b_count <= 6:
                    continue
                for role_a_positions in combinations(_BOARD_CELLS, a_count):
                    remaining = tuple(
                        position
                        for position in _BOARD_CELLS
                        if position not in role_a_positions
                    )
                    for role_b_positions in combinations(remaining, b_count):
                        rows.append((role_a_positions, role_b_positions))
        _SETUP_ROWS = tuple(rows)
    return _SETUP_ROWS


def _setup(role_a_positions=((0, 0),), role_b_positions=((2, 2),)):
    return compiler.TypedSetupV1(
        compiler.TYPED_SETUP_VERSION_V1,
        tuple(role_a_positions),
        tuple(role_b_positions),
    )


def _carrier(skeleton, setup=None):
    return compiler.TypedSetupCarrierV1(
        compiler.TYPED_SETUP_CARRIER_VERSION_V1,
        skeleton,
        _setup() if setup is None else setup,
    )


def _member(skeleton, first_player=None, setup=None):
    if first_player is None:
        first_player = compiler.RoleOwner.A
    return compiler.TypedDefinitionMemberV1(
        compiler.TYPED_DEFINITION_MEMBER_VERSION_V1,
        _carrier(skeleton, setup),
        first_player,
    )


def _transform_position(position, transform):
    row, column = position
    maximum = 2
    return {
        "I": (row, column),
        "R90": (column, maximum - row),
        "R180": (maximum - row, maximum - column),
        "R270": (maximum - column, row),
        "FLR": (row, maximum - column),
        "FTB": (maximum - row, column),
        "FD": (column, row),
        "FA": (maximum - column, maximum - row),
    }[transform]


def _independent_transformed_setup(row, transform):
    return tuple(
        tuple(sorted(_transform_position(position, transform) for position in side))
        for side in row
    )


def _replace_piece_identifiers(value):
    if type(value) is dict:
        return {
            key: _replace_piece_identifiers(item)
            for key, item in value.items()
        }
    if type(value) is list:
        return [_replace_piece_identifiers(item) for item in value]
    if value == "a":
        return "b"
    if value == "b":
        return "a"
    return value


def _compiled_name(member):
    return "pf15-" + compiler.typed_definition_member_hash_v1(member)


def _owner_swap_dsl(definition, target_name):
    value = json.loads(dsl.canonical_json(definition))
    value["name"] = target_name
    pieces = []
    for piece in value["initial_pieces"]:
        transformed = dict(piece)
        transformed["owner"] = "B" if piece["owner"] == "A" else "A"
        transformed["piece"] = (
            "b" if piece["owner"] == "A" else "a"
        )
        pieces.append(transformed)
    value["initial_pieces"] = pieces
    return dsl.parse_definition(value)


def _complete_role_swap_dsl(definition, target_name):
    value = json.loads(dsl.canonical_json(definition))
    value["name"] = target_name
    value["first_player"] = (
        "B" if value["first_player"] == "A" else "A"
    )
    role_a = _replace_piece_identifiers(value["roles"]["B"])
    role_b = _replace_piece_identifiers(value["roles"]["A"])
    value["roles"] = {"A": role_a, "B": role_b}
    pieces = []
    for piece in value["initial_pieces"]:
        transformed = _replace_piece_identifiers(piece)
        transformed["owner"] = "B" if piece["owner"] == "A" else "A"
        pieces.append(transformed)
    value["initial_pieces"] = pieces
    return dsl.parse_definition(value)


def _toggle_first_player_dsl(definition, target_name):
    value = json.loads(dsl.canonical_json(definition))
    value["name"] = target_name
    value["first_player"] = (
        "B" if value["first_player"] == "A" else "A"
    )
    return dsl.parse_definition(value)


def _compiled_definition(member):
    encoded = compiler.compile_schema_v4_json_v1(member)
    return encoded, dsl.parse_definition(json.loads(encoded))


def _rich_skeleton():
    for skeleton in _fresh_skeletons():
        role = skeleton.role_a
        if (
            role.signature.action_primitive is not universe.ActionPrimitive.PLACE
            and role.vector_profile is universe.VectorProfile.KING_8
            and role.signature.goal_primitive
            is universe.GoalPrimitive.CONNECT_EDGES
        ):
            return skeleton
    raise AssertionError("fresh universe lacks the required rich test skeleton")


class SetupMasterLatticeTests(unittest.TestCase):
    def test_setup_enumeration_remains_outside_the_slice2_production_api(self):
        self.assertNotIn("enumerate_typed_setups_v1", vars(compiler))

    def test_independent_lattice_has_exact_supply_and_fixed_endpoints(self):
        rows = _independent_setup_rows()
        observed = {}
        for role_a_positions, role_b_positions in rows:
            key = (len(role_a_positions), len(role_b_positions))
            observed[key] = observed.get(key, 0) + 1

        self.assertEqual(len(rows), 6798)
        self.assertEqual(observed, _COUNT_PAIR_SUPPLIES)
        self.assertEqual(sum(_COUNT_PAIR_SUPPLIES.values()), 6798)
        self.assertEqual(rows[0], ((), ((0, 0),)))
        self.assertEqual(
            rows[-1],
            (
                ((2, 0), (2, 1), (2, 2)),
                ((1, 0), (1, 1), (1, 2)),
            ),
        )

    def test_every_lattice_row_constructs_parses_hashes_and_detaches(self):
        canonical_values = set()
        observed_hashes = set()
        first_json = None
        last_json = None
        for role_a_positions, role_b_positions in _independent_setup_rows():
            setup = _setup(role_a_positions, role_b_positions)
            expected = {
                "setup_version": 1,
                "positions": {
                    "A": [list(position) for position in role_a_positions],
                    "B": [list(position) for position in role_b_positions],
                },
            }
            self.assertEqual(setup.to_dict(), expected)
            canonical = compiler.canonical_typed_setup_json_v1(setup)
            self.assertEqual(canonical, _canonical(expected))
            parsed = compiler.parse_typed_setup_v1(copy.deepcopy(expected))
            self.assertEqual(parsed, setup)
            self.assertEqual(
                compiler.canonical_typed_setup_json_v1(parsed), canonical
            )
            digest = compiler.typed_setup_hash_v1(setup)
            self.assertRegex(digest, r"^[0-9a-f]{64}$")
            canonical_values.add(canonical)
            observed_hashes.add(digest)
            if first_json is None:
                first_json = canonical
            last_json = canonical

        # Canonical carriers, not hash noncollision, are the identity proof.
        self.assertEqual(len(canonical_values), 6798)
        self.assertEqual(len(observed_hashes), 6798)
        self.assertEqual(
            first_json,
            '{"positions":{"A":[],"B":[[0,0]]},"setup_version":1}',
        )
        self.assertEqual(
            last_json,
            '{"positions":{"A":[[2,0],[2,1],[2,2]],'
            '"B":[[1,0],[1,1],[1,2]]},"setup_version":1}',
        )

    def test_setup_parser_and_constructor_are_strict(self):
        valid = _setup()
        payload = valid.to_dict()

        class IntAlias(int):
            pass

        class TupleAlias(tuple):
            pass

        class DictAlias(dict):
            pass

        class ListAlias(list):
            pass

        class StrAlias(str):
            pass

        invalid_constructors = (
            (True, ((0, 0),), ((2, 2),)),
            (IntAlias(1), ((0, 0),), ((2, 2),)),
            (1, [[0, 0]], ((2, 2),)),
            (1, TupleAlias(((0, 0),)), ((2, 2),)),
            (1, ((0, 0),), TupleAlias(((2, 2),))),
            (1, ((True, 0),), ((2, 2),)),
            (1, ((IntAlias(0), 0),), ((2, 2),)),
            (1, ((0, 0), (0, 0)), ((2, 2),)),
            (1, ((0, 1), (0, 0)), ((2, 2),)),
            (1, ((0, 0),), ((0, 0),)),
            (1, ((-1, 0),), ((2, 2),)),
            (1, ((3, 0),), ((2, 2),)),
            (1, (), ()),
            (1, ((0, 0),) * 4, ()),
            (1, ((0, 0),), ((0, 1),) * 4),
        )
        for arguments in invalid_constructors:
            with self.subTest(arguments=arguments):
                with self.assertRaises((TypeError, ValueError)):
                    compiler.TypedSetupV1(*arguments)

        malformed = []
        extra = copy.deepcopy(payload)
        extra["extra"] = None
        malformed.append(extra)
        missing = copy.deepcopy(payload)
        del missing["positions"]
        malformed.append(missing)
        nested_extra = copy.deepcopy(payload)
        nested_extra["positions"]["C"] = []
        malformed.append(nested_extra)
        wrong_order = copy.deepcopy(payload)
        wrong_order["positions"]["A"] = [[0, 1], [0, 0]]
        malformed.append(wrong_order)
        malformed.extend(
            (
                DictAlias(payload),
                {StrAlias("setup_version"): 1, "positions": payload["positions"]},
                {"setup_version": True, "positions": payload["positions"]},
                {
                    "setup_version": 1,
                    "positions": DictAlias(payload["positions"]),
                },
                {
                    "setup_version": 1,
                    "positions": {"A": ListAlias([[0, 0]]), "B": [[2, 2]]},
                },
                {
                    "setup_version": 1,
                    "positions": {"A": [[False, 0]], "B": [[2, 2]]},
                },
            )
        )
        for value in malformed:
            with self.subTest(value=value):
                with self.assertRaises((TypeError, ValueError)):
                    compiler.parse_typed_setup_v1(value)

    def test_setup_parse_and_serialization_are_deeply_detached(self):
        payload = _setup().to_dict()
        parsed = compiler.parse_typed_setup_v1(payload)
        baseline = compiler.canonical_typed_setup_json_v1(parsed)
        payload["positions"]["A"][0][0] = 1
        payload["positions"]["B"].clear()
        self.assertEqual(compiler.canonical_typed_setup_json_v1(parsed), baseline)

        exported = parsed.to_dict()
        exported["positions"]["A"][0][1] = 2
        self.assertEqual(compiler.canonical_typed_setup_json_v1(parsed), baseline)

    def test_all_setup_d4_images_match_an_independent_oracle(self):
        for row in _independent_setup_rows():
            source = _setup(*row)
            swapped = compiler.owner_swap_typed_setup_v1(source)
            self.assertEqual(
                (swapped.role_a_positions, swapped.role_b_positions),
                (row[1], row[0]),
            )
            self.assertEqual(
                compiler.owner_swap_typed_setup_v1(swapped), source
            )
            for transform in universe.D4Transform:
                with self.subTest(row=row, transform=transform.value):
                    result = compiler.transform_typed_setup_v1(source, transform)
                    expected = _independent_transformed_setup(row, transform.value)
                    self.assertEqual(
                        (result.role_a_positions, result.role_b_positions),
                        expected,
                    )
                    restored = compiler.transform_typed_setup_v1(
                        result,
                        universe.D4Transform(_D4_INVERSES[transform.value]),
                    )
                    self.assertEqual(restored, source)
                    self.assertEqual(
                        compiler.transform_typed_setup_v1(swapped, transform),
                        compiler.owner_swap_typed_setup_v1(result),
                    )


class TypedCarrierBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skeleton = _fresh_skeletons()[0]
        cls.setup = _setup()
        cls.carrier = _carrier(cls.skeleton, cls.setup)
        cls.member = _member(cls.skeleton, setup=cls.setup)

    def test_public_versions_owner_vocabulary_and_pair_order_are_exact(self):
        self.assertEqual(compiler.TYPED_OCCUPANCY_COMPILER_VERSION, 1)
        self.assertEqual(compiler.TYPED_SETUP_VERSION_V1, 1)
        self.assertEqual(compiler.TYPED_SETUP_CARRIER_VERSION_V1, 1)
        self.assertEqual(compiler.TYPED_DEFINITION_MEMBER_VERSION_V1, 1)
        self.assertEqual(
            tuple(owner.value for owner in compiler.RoleOwner), ("A", "B")
        )
        pair = compiler.expand_first_player_pair_v1(self.carrier)
        self.assertIs(type(pair), tuple)
        self.assertEqual(len(pair), 2)
        self.assertIs(pair[0].first_player, compiler.RoleOwner.A)
        self.assertIs(pair[1].first_player, compiler.RoleOwner.B)
        self.assertEqual(pair[0].carrier, pair[1].carrier)

    def test_carrier_and_member_parse_canonical_hash_roundtrip(self):
        carrier_value = self.carrier.to_dict()
        member_value = self.member.to_dict()
        self.assertEqual(
            set(carrier_value), {"carrier_version", "profiled_skeleton", "setup"}
        )
        self.assertEqual(
            set(member_value), {"member_version", "carrier", "first_player"}
        )
        for value, parse, canonical, digest in (
            (
                carrier_value,
                compiler.parse_typed_setup_carrier_v1,
                compiler.canonical_typed_setup_carrier_json_v1,
                compiler.typed_setup_carrier_hash_v1,
            ),
            (
                member_value,
                compiler.parse_typed_definition_member_v1,
                compiler.canonical_typed_definition_member_json_v1,
                compiler.typed_definition_member_hash_v1,
            ),
        ):
            parsed = parse(copy.deepcopy(value))
            self.assertEqual(parsed.to_dict(), value)
            self.assertEqual(canonical(parsed), _canonical(value))
            self.assertRegex(digest(parsed), r"^[0-9a-f]{64}$")

            value.clear()
            self.assertEqual(json.loads(canonical(parsed)), parsed.to_dict())
            exported = parsed.to_dict()
            exported.clear()
            self.assertNotEqual(parsed.to_dict(), {})

    def test_carrier_and_member_parser_reject_unknown_missing_and_alias_types(self):
        class DictAlias(dict):
            pass

        class StrAlias(str):
            pass

        carrier = self.carrier.to_dict()
        member = self.member.to_dict()
        attacks = []
        for baseline, parser in (
            (carrier, compiler.parse_typed_setup_carrier_v1),
            (member, compiler.parse_typed_definition_member_v1),
        ):
            attacks.append((parser, DictAlias(copy.deepcopy(baseline))))
            extra = copy.deepcopy(baseline)
            extra["extra"] = None
            attacks.append((parser, extra))
            missing = copy.deepcopy(baseline)
            del missing[next(iter(missing))]
            attacks.append((parser, missing))
        alias_member = copy.deepcopy(member)
        alias_member["first_player"] = StrAlias("A")
        attacks.append((compiler.parse_typed_definition_member_v1, alias_member))
        bool_member = copy.deepcopy(member)
        bool_member["member_version"] = True
        attacks.append((compiler.parse_typed_definition_member_v1, bool_member))
        bool_carrier = copy.deepcopy(carrier)
        bool_carrier["carrier_version"] = True
        attacks.append((compiler.parse_typed_setup_carrier_v1, bool_carrier))
        skeleton_extra = copy.deepcopy(carrier)
        skeleton_extra["profiled_skeleton"]["extra"] = None
        attacks.append((compiler.parse_typed_setup_carrier_v1, skeleton_extra))

        for parser, value in attacks:
            with self.subTest(parser=parser.__name__, value=value):
                with self.assertRaises((TypeError, ValueError)):
                    parser(value)

    def test_direct_construction_requires_exact_nested_types_and_enums(self):
        class IntAlias(int):
            pass

        class CarrierAlias(compiler.TypedSetupCarrierV1):
            pass

        with self.assertRaises((TypeError, ValueError)):
            compiler.TypedSetupCarrierV1(True, self.skeleton, self.setup)
        with self.assertRaises((TypeError, ValueError)):
            compiler.TypedSetupCarrierV1(IntAlias(1), self.skeleton, self.setup)
        with self.assertRaises((TypeError, ValueError)):
            compiler.TypedSetupCarrierV1(1, self.skeleton.to_dict(), self.setup)
        with self.assertRaises((TypeError, ValueError)):
            compiler.TypedSetupCarrierV1(1, self.skeleton, self.setup.to_dict())
        with self.assertRaises((TypeError, ValueError)):
            compiler.TypedDefinitionMemberV1(True, self.carrier, compiler.RoleOwner.A)
        with self.assertRaises((TypeError, ValueError)):
            compiler.TypedDefinitionMemberV1(1, self.carrier, "A")
        with self.assertRaises((TypeError, ValueError)):
            compiler.TypedDefinitionMemberV1(
                1,
                CarrierAlias(1, self.skeleton, self.setup),
                compiler.RoleOwner.A,
            )

    def test_construction_detaches_nested_typed_values(self):
        setup = _setup()
        carrier = _carrier(self.skeleton, setup)
        member = compiler.TypedDefinitionMemberV1(
            1, carrier, compiler.RoleOwner.A
        )
        baseline_carrier = compiler.canonical_typed_setup_carrier_json_v1(carrier)
        baseline_member = compiler.canonical_typed_definition_member_json_v1(member)

        object.__setattr__(setup, "role_a_positions", ((1, 1),))
        object.__setattr__(carrier, "carrier_version", 2)
        self.assertEqual(
            compiler.canonical_typed_setup_carrier_json_v1(member.carrier),
            baseline_carrier,
        )
        self.assertEqual(
            compiler.canonical_typed_definition_member_json_v1(member),
            baseline_member,
        )

    def test_valid_to_valid_mutation_is_rejected_at_every_public_boundary(self):
        carrier = _carrier(self.skeleton)
        member = compiler.TypedDefinitionMemberV1(1, carrier, compiler.RoleOwner.A)
        object.__setattr__(member, "first_player", compiler.RoleOwner.B)
        operations = (
            compiler.canonical_typed_definition_member_json_v1,
            compiler.typed_definition_member_hash_v1,
            compiler.toggle_first_player_member_v1,
            compiler.compile_schema_v4_json_v1,
        )
        for operation in operations:
            with self.subTest(operation=operation.__name__):
                with self.assertRaises((TypeError, ValueError)):
                    operation(member)

    def test_instance_method_shadows_are_rejected_at_every_nested_boundary(self):
        target_paths = (
            lambda member: member,
            lambda member: member.carrier,
            lambda member: member.carrier.setup,
            lambda member: member.carrier.skeleton,
            lambda member: member.carrier.skeleton.role_a,
            lambda member: member.carrier.skeleton.role_a.signature,
            lambda member: member.carrier.skeleton.role_a.goal_target,
        )
        method_names = ("_assert_unchanged", "_payload_unchecked", "to_dict")
        for target_path in target_paths:
            for method_name in method_names:
                member = _member(self.skeleton)
                target = target_path(member)
                object.__setattr__(target, method_name, lambda: None)
                with self.subTest(
                    target=type(target).__name__, method_name=method_name
                ):
                    with self.assertRaises((TypeError, ValueError)):
                        compiler.compile_schema_v4_json_v1(member)

    def test_transport_orientations_and_complete_swap_are_accepted_exactly(self):
        source = next(
            skeleton
            for skeleton in _fresh_skeletons()
            if universe.profiled_skeleton_d4_stabilizer_size(skeleton) == 1
        )
        source_member = _member(source)
        observed = set()
        for transform in universe.D4Transform:
            transported = compiler.transform_typed_definition_member_v1(
                source_member, transform
            )
            observed.add(
                universe.canonical_profiled_skeleton_json(
                    transported.carrier.skeleton
                )
            )
            projected = compiler.project_compiled_schema_v4_json_v1(
                compiler.compile_schema_v4_json_v1(transported)
            )
            self.assertEqual(projected, transported)
        self.assertEqual(len(observed), 8)

        swapped = compiler.complete_role_swap_typed_definition_member_v1(
            source_member
        )
        self.assertEqual(
            swapped.carrier.skeleton,
            universe.role_swap_profiled_skeleton(source),
        )
        self.assertEqual(
            swapped.carrier.setup,
            compiler.owner_swap_typed_setup_v1(source_member.carrier.setup),
        )
        self.assertIs(swapped.first_player, compiler.RoleOwner.B)
        self.assertEqual(
            compiler.project_compiled_schema_v4_json_v1(
                compiler.compile_schema_v4_json_v1(swapped)
            ),
            swapped,
        )

    def test_old_and_self_isomorphic_skeletons_are_rejected(self):
        rejected = (
            universe.enumerate_plan0013_profiled_region_closure()[0],
            universe.enumerate_self_isomorphic_profiled_skeletons()[0],
        )
        for skeleton in rejected:
            with self.subTest(skeleton=skeleton.to_dict()):
                with self.assertRaises((TypeError, ValueError)):
                    compiler.TypedSetupCarrierV1(1, skeleton, self.setup)
                value = self.carrier.to_dict()
                value["profiled_skeleton"] = skeleton.to_dict()
                with self.assertRaises((TypeError, ValueError)):
                    compiler.parse_typed_setup_carrier_v1(value)


class ExhaustiveCompilerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fresh = _fresh_skeletons()
        cls.boundary_setup = _setup()

    def test_all_1518_skeletons_compile_and_project_both_first_players(self):
        self.assertEqual(len(self.fresh), 1518)
        actions = set()
        goals = set()
        profiles = set()
        exact_member_values = set()
        compiled_values = set()

        for skeleton in self.fresh:
            pair = compiler.expand_first_player_pair_v1(
                _carrier(skeleton, self.boundary_setup)
            )
            self.assertEqual(
                tuple(member.first_player.value for member in pair), ("A", "B")
            )
            for member in pair:
                member_json = compiler.canonical_typed_definition_member_json_v1(
                    member
                )
                encoded, definition = _compiled_definition(member)
                self.assertEqual(encoded, dsl.canonical_json(definition))
                self.assertEqual(
                    compiler.compiled_schema_v4_hash_v1(member),
                    dsl.definition_hash(definition),
                )
                self.assertEqual(
                    compiler.project_compiled_schema_v4_json_v1(encoded), member
                )
                self.assertEqual(definition.schema_version, 4)
                self.assertEqual(definition.board_size, 3)
                self.assertEqual(definition.max_plies, 18)
                self.assertEqual(definition.first_player.value, member.first_player.value)
                self.assertEqual(definition.name, _compiled_name(member))
                exact_member_values.add(member_json)
                compiled_values.add(encoded)

                for owner, profiled_role in (
                    (dsl.Player.A, skeleton.role_a),
                    (dsl.Player.B, skeleton.role_b),
                ):
                    role = definition.role(owner)
                    actions.add(role.action.kind.value)
                    goals.add(role.goal.kind.value)
                    self.assertEqual(
                        role.action.kind.value,
                        profiled_role.signature.action_primitive.value,
                    )
                    expected_vectors = (
                        ()
                        if profiled_role.vector_profile
                        is universe.VectorProfile.NONE
                        else universe.vector_profile_vectors(
                            profiled_role.vector_profile
                        )
                    )
                    self.assertEqual(role.action.vectors, expected_vectors)
                    if profiled_role.vector_profile is not universe.VectorProfile.NONE:
                        profiles.add(profiled_role.vector_profile.value)
                    self.assertEqual(
                        role.goal.kind.value,
                        profiled_role.signature.goal_primitive.value,
                    )
                    target_edges = tuple(
                        edge.value for edge in profiled_role.goal_target.edges
                    )
                    if role.goal.kind is dsl.GoalKind.CONNECT_EDGES:
                        self.assertEqual(
                            frozenset(edge.value for edge in role.goal.edges),
                            frozenset(target_edges),
                        )
                    elif role.goal.kind is dsl.GoalKind.REACH_EDGE:
                        self.assertEqual(role.goal.edge.value, target_edges[0])
                    else:
                        self.assertEqual(target_edges, ())

        self.assertEqual(actions, {item.value for item in universe.ActionPrimitive})
        self.assertEqual(goals, {item.value for item in universe.GoalPrimitive})
        self.assertEqual(
            profiles,
            {item.value for item in universe.enumerate_movement_vector_profiles()},
        )
        self.assertEqual(len(exact_member_values), 2 * 1518)
        self.assertEqual(len(compiled_values), 2 * 1518)

    def test_all_6798_setups_compile_project_and_are_structurally_injective(self):
        skeleton = self.fresh[0]
        exact_members = set()
        compiled_definitions = set()
        observed_count_pairs = {}

        for role_a_positions, role_b_positions in _independent_setup_rows():
            setup = _setup(role_a_positions, role_b_positions)
            member = _member(skeleton, compiler.RoleOwner.A, setup)
            member_json = compiler.canonical_typed_definition_member_json_v1(member)
            encoded, definition = _compiled_definition(member)
            projected = compiler.project_compiled_schema_v4_json_v1(encoded)
            self.assertEqual(projected, member)
            self.assertEqual(encoded, dsl.canonical_json(definition))

            observed_positions = {"A": [], "B": []}
            for piece in definition.initial_pieces:
                observed_positions[piece.owner.value].append(piece.position)
                self.assertEqual(
                    piece.piece,
                    "a" if piece.owner is dsl.Player.A else "b",
                )
            self.assertEqual(tuple(observed_positions["A"]), role_a_positions)
            self.assertEqual(tuple(observed_positions["B"]), role_b_positions)

            pair = (len(role_a_positions), len(role_b_positions))
            observed_count_pairs[pair] = observed_count_pairs.get(pair, 0) + 1
            exact_members.add(member_json)
            compiled_definitions.add(encoded)

        # The full canonical carriers prove injectivity; hashes are not used as
        # a substitute for comparing the complete typed or compiled values.
        self.assertEqual(len(exact_members), 6798)
        self.assertEqual(len(compiled_definitions), 6798)
        self.assertEqual(observed_count_pairs, _COUNT_PAIR_SUPPLIES)

    def test_all_count_pairs_accept_nonplace_zero_actors_and_eliminate_truth_shapes(self):
        skeleton = next(
            item
            for item in self.fresh
            if item.role_a.signature.action_primitive
            is not universe.ActionPrimitive.PLACE
            and item.role_b.signature.action_primitive
            is not universe.ActionPrimitive.PLACE
            and universe.GoalPrimitive.ELIMINATE
            in (
                item.role_a.signature.goal_primitive,
                item.role_b.signature.goal_primitive,
            )
        )
        representatives = {}
        for row in _independent_setup_rows():
            count_pair = (len(row[0]), len(row[1]))
            representatives.setdefault(count_pair, row)
        self.assertEqual(set(representatives), set(_COUNT_PAIR_SUPPLIES))

        observed_zero_nonplace = set()
        observed_initial_true_eliminate_shape = set()
        for count_pair in sorted(representatives):
            setup = _setup(*representatives[count_pair])
            for first_player in (compiler.RoleOwner.A, compiler.RoleOwner.B):
                member = _member(skeleton, first_player, setup)
                encoded = compiler.compile_schema_v4_json_v1(member)
                self.assertEqual(
                    compiler.project_compiled_schema_v4_json_v1(encoded), member
                )
            if 0 in count_pair:
                observed_zero_nonplace.add(count_pair)
            if (
                skeleton.role_a.signature.goal_primitive
                is universe.GoalPrimitive.ELIMINATE
                and count_pair[1] == 0
            ) or (
                skeleton.role_b.signature.goal_primitive
                is universe.GoalPrimitive.ELIMINATE
                and count_pair[0] == 0
            ):
                observed_initial_true_eliminate_shape.add(count_pair)

        self.assertEqual(
            observed_zero_nonplace,
            {pair for pair in _COUNT_PAIR_SUPPLIES if 0 in pair},
        )
        self.assertTrue(observed_initial_true_eliminate_shape)

    def test_all_fresh_skeletons_commute_with_every_d4_transform(self):
        raw_goal_frames = set()
        expected_raw_goal_frames = {
            _canonical(frame.to_dict())
            for frame in universe.enumerate_raw_goal_frames()
        }
        for skeleton in self.fresh:
            source_member = _member(skeleton, setup=self.boundary_setup)
            source_encoded, source_definition = _compiled_definition(source_member)
            self.assertEqual(source_encoded, dsl.canonical_json(source_definition))
            for transform in universe.D4Transform:
                target_member = compiler.transform_typed_definition_member_v1(
                    source_member, transform
                )
                target_encoded, target_definition = _compiled_definition(target_member)
                expected = symmetry.transform_definition(
                    source_definition,
                    transform.value,
                    name=target_definition.name,
                )
                self.assertEqual(target_encoded, dsl.canonical_json(expected))
                self.assertEqual(
                    target_member.carrier.skeleton,
                    universe.transform_profiled_skeleton(skeleton, transform),
                )
                raw_goal_frames.add(
                    _canonical(target_member.carrier.skeleton.goal_frame.to_dict())
                )

        self.assertEqual(raw_goal_frames, expected_raw_goal_frames)
        self.assertEqual(len(raw_goal_frames), 49)

    def test_complete_role_swap_compilation_for_all_fresh_skeletons(self):
        for skeleton in self.fresh:
            source_member = _member(skeleton, setup=self.boundary_setup)
            _source_encoded, source_definition = _compiled_definition(source_member)
            target_member = compiler.complete_role_swap_typed_definition_member_v1(
                source_member
            )
            target_encoded, target_definition = _compiled_definition(target_member)
            expected = _complete_role_swap_dsl(
                source_definition, target_definition.name
            )
            self.assertEqual(target_encoded, dsl.canonical_json(expected))
            self.assertEqual(
                compiler.complete_role_swap_typed_definition_member_v1(
                    target_member
                ),
                source_member,
            )


class TransformAlgebraTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skeleton = _rich_skeleton()
        cls.member = _member(
            cls.skeleton,
            compiler.RoleOwner.A,
            _setup(((0, 0), (1, 1)), ((0, 2), (2, 1))),
        )

    def test_d4_group_composition_and_inverses_match_coordinate_action(self):
        source = self.member
        signatures = {
            transform: tuple(
                _transform_position(position, transform.value)
                for position in _BOARD_CELLS
            )
            for transform in universe.D4Transform
        }
        for first in universe.D4Transform:
            inverse = universe.D4Transform(_D4_INVERSES[first.value])
            self.assertEqual(
                compiler.transform_typed_definition_member_v1(
                    compiler.transform_typed_definition_member_v1(source, first),
                    inverse,
                ),
                source,
            )
            for second in universe.D4Transform:
                composed_signature = tuple(
                    _transform_position(
                        _transform_position(position, first.value), second.value
                    )
                    for position in _BOARD_CELLS
                )
                expected_transform = next(
                    transform
                    for transform, signature in signatures.items()
                    if signature == composed_signature
                )
                actual = compiler.transform_typed_definition_member_v1(
                    compiler.transform_typed_definition_member_v1(source, first),
                    second,
                )
                expected = compiler.transform_typed_definition_member_v1(
                    source, expected_transform
                )
                self.assertEqual(actual, expected)

    def test_owner_role_and_first_player_involutions_and_commutation(self):
        source = self.member
        owner_swap = compiler.owner_swap_typed_definition_member_v1
        role_swap = compiler.complete_role_swap_typed_definition_member_v1
        toggle = compiler.toggle_first_player_member_v1
        self.assertEqual(owner_swap(owner_swap(source)), source)
        self.assertEqual(role_swap(role_swap(source)), source)
        self.assertEqual(toggle(toggle(source)), source)
        self.assertIs(owner_swap(source).first_player, source.first_player)
        self.assertIs(toggle(source).first_player, compiler.RoleOwner.B)

        operations = (owner_swap, role_swap, toggle)
        for index, first in enumerate(operations):
            for second in operations[index + 1 :]:
                with self.subTest(first=first.__name__, second=second.__name__):
                    self.assertEqual(first(second(source)), second(first(source)))

        for transform in universe.D4Transform:
            d4 = lambda value: compiler.transform_typed_definition_member_v1(
                value, transform
            )
            for operation in operations:
                with self.subTest(
                    transform=transform.value, operation=operation.__name__
                ):
                    self.assertEqual(
                        d4(operation(source)), operation(d4(source))
                    )

    def test_owner_role_and_first_player_compilation_match_independent_oracles(self):
        _source_encoded, source_definition = _compiled_definition(self.member)
        cases = (
            (
                compiler.owner_swap_typed_definition_member_v1(self.member),
                _owner_swap_dsl,
            ),
            (
                compiler.complete_role_swap_typed_definition_member_v1(
                    self.member
                ),
                _complete_role_swap_dsl,
            ),
            (
                compiler.toggle_first_player_member_v1(self.member),
                _toggle_first_player_dsl,
            ),
        )
        for target, oracle in cases:
            target_encoded, target_definition = _compiled_definition(target)
            expected = oracle(source_definition, target_definition.name)
            self.assertEqual(target_encoded, dsl.canonical_json(expected))

    def test_transform_boundaries_reject_strings_subclasses_and_mutation(self):
        class TransformAlias(str):
            pass

        for invalid in ("I", TransformAlias("I"), object()):
            with self.subTest(invalid=invalid):
                with self.assertRaises((TypeError, ValueError)):
                    compiler.transform_typed_definition_member_v1(
                        self.member, invalid
                    )


class CompiledInverseBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.member = _member(
            _rich_skeleton(),
            compiler.RoleOwner.A,
            _setup(((0, 0),), ((2, 2),)),
        )
        cls.encoded = compiler.compile_schema_v4_json_v1(cls.member)
        cls.value = json.loads(cls.encoded)

    def test_exact_compiled_shape_and_piece_binding(self):
        value = self.value
        self.assertEqual(
            set(value),
            {
                "schema_version",
                "name",
                "board_size",
                "first_player",
                "max_plies",
                "roles",
                "initial_pieces",
            },
        )
        self.assertEqual(value["schema_version"], 4)
        self.assertEqual(value["board_size"], 3)
        self.assertEqual(value["max_plies"], 18)
        self.assertEqual(value["name"], _compiled_name(self.member))
        self.assertEqual(
            [(piece["owner"], piece["piece"]) for piece in value["initial_pieces"]],
            [("A", "a"), ("B", "b")],
        )

        for owner, own_piece, opposing_piece in (
            ("A", "a", "b"),
            ("B", "b", "a"),
        ):
            role = value["roles"][owner]
            self.assertEqual(role["action"]["piece"], own_piece)
            expected_goal_piece = (
                opposing_piece
                if role["goal"]["kind"] == "ELIMINATE"
                else own_piece
            )
            self.assertEqual(role["goal"]["piece"], expected_goal_piece)

    def test_inverse_requires_exact_canonical_text_without_duplicate_keys(self):
        class StrAlias(str):
            pass

        duplicate = self.encoded.replace(
            '"board_size":3', '"board_size":3,"board_size":3', 1
        )
        nonfinite = self.encoded.replace('"board_size":3', '"board_size":NaN', 1)
        positive_infinity = self.encoded.replace(
            '"board_size":3', '"board_size":Infinity', 1
        )
        negative_infinity = self.encoded.replace(
            '"board_size":3', '"board_size":-Infinity', 1
        )
        overflow_float = self.encoded.replace(
            '"board_size":3', '"board_size":1e309', 1
        )
        integral_float = self.encoded.replace(
            '"schema_version":4', '"schema_version":4.0', 1
        )
        reversed_keys = json.dumps(
            dict(reversed(tuple(self.value.items()))),
            separators=(",", ":"),
        )
        unsorted_vectors_value = copy.deepcopy(self.value)
        unsorted_vectors_value["roles"]["A"]["action"]["vectors"] = list(
            reversed(unsorted_vectors_value["roles"]["A"]["action"]["vectors"])
        )
        unsorted_vectors = json.dumps(
            unsorted_vectors_value, sort_keys=True, separators=(",", ":")
        )
        unsorted_edges_value = copy.deepcopy(self.value)
        unsorted_edges_value["roles"]["A"]["goal"]["edges"] = list(
            reversed(unsorted_edges_value["roles"]["A"]["goal"]["edges"])
        )
        unsorted_edges = json.dumps(
            unsorted_edges_value, sort_keys=True, separators=(",", ":")
        )
        unsorted_pieces_value = copy.deepcopy(self.value)
        unsorted_pieces_value["initial_pieces"].reverse()
        unsorted_pieces = json.dumps(
            unsorted_pieces_value, sort_keys=True, separators=(",", ":")
        )
        deep = '{"x":' + ("[" * 100) + "0" + ("]" * 100) + "}"
        noncanonical = (
            json.dumps(self.value, sort_keys=True, indent=2),
            self.encoded + "\n",
            " " + self.encoded,
            duplicate,
            nonfinite,
            positive_infinity,
            negative_infinity,
            overflow_float,
            integral_float,
            reversed_keys,
            unsorted_vectors,
            unsorted_edges,
            unsorted_pieces,
            deep,
            self.encoded + (" " * 1_100_000),
        )
        for value in noncanonical + (StrAlias(self.encoded), b"not text", None):
            with self.subTest(kind=type(value).__name__, length=getattr(value, "__len__", lambda: 0)()):
                with self.assertRaises((TypeError, ValueError)):
                    compiler.project_compiled_schema_v4_json_v1(value)

    def test_inverse_rejects_canonical_dsl_values_outside_the_compiler_image(self):
        def canonical_valid(mutator):
            value = copy.deepcopy(self.value)
            mutator(value)
            return dsl.canonical_json(dsl.parse_definition(value))

        valid_attacks = (
            ("board size", lambda value: value.__setitem__("board_size", 4)),
            ("max plies", lambda value: value.__setitem__("max_plies", 19)),
            ("name", lambda value: value.__setitem__("name", "pf15-" + "0" * 64)),
            (
                "action piece",
                lambda value: value["roles"]["A"]["action"].__setitem__(
                    "piece", "other_piece"
                ),
            ),
            (
                "goal piece",
                lambda value: value["roles"]["A"]["goal"].__setitem__(
                    "piece", "other_piece"
                ),
            ),
            (
                "vectors",
                lambda value: value["roles"]["A"]["action"].__setitem__(
                    "vectors", [[-1, 0], [0, -1], [0, 1], [1, 0]]
                ),
            ),
            (
                "goal edges",
                lambda value: value["roles"]["A"]["goal"].__setitem__(
                    "edges",
                    ["LEFT", "RIGHT"]
                    if value["roles"]["A"]["goal"]["edges"]
                    == ["BOTTOM", "TOP"]
                    else ["BOTTOM", "TOP"],
                ),
            ),
            (
                "initial owner",
                lambda value: value["initial_pieces"][0].__setitem__("owner", "B"),
            ),
            (
                "initial piece identifier",
                lambda value: value["initial_pieces"][0].__setitem__(
                    "piece", "other_piece"
                ),
            ),
            (
                "initial position",
                lambda value: value["initial_pieces"][0].__setitem__(
                    "position", [1, 1]
                ),
            ),
            (
                "missing initial piece",
                lambda value: value["initial_pieces"].pop(),
            ),
            (
                "extra initial piece",
                lambda value: value["initial_pieces"].append(
                    {"owner": "A", "piece": "a", "position": [1, 1]}
                ),
            ),
        )
        for label, mutator in valid_attacks:
            with self.subTest(label=label):
                encoded = canonical_valid(mutator)
                # The authoritative parser accepts these canonical definitions;
                # rejection therefore comes from the compiler image boundary.
                self.assertEqual(encoded, dsl.canonical_json(dsl.parse_definition(json.loads(encoded))))
                with self.assertRaises((TypeError, ValueError)):
                    compiler.project_compiled_schema_v4_json_v1(encoded)

    def test_inverse_rejects_wrong_fields_types_and_invalid_schema_values(self):
        attacks = []
        for label, mutation in (
            ("schema bool", ("schema_version", True)),
            ("schema version", ("schema_version", 3)),
            ("first player", ("first_player", "C")),
        ):
            value = copy.deepcopy(self.value)
            value[mutation[0]] = mutation[1]
            attacks.append((label, _canonical(value)))
        extra = copy.deepcopy(self.value)
        extra["extra"] = None
        attacks.append(("extra field", _canonical(extra)))
        missing = copy.deepcopy(self.value)
        del missing["roles"]
        attacks.append(("missing field", _canonical(missing)))
        terminal = copy.deepcopy(self.value)
        terminal["terminal_policy"] = {"no_legal_action": "DRAW"}
        attacks.append(("terminal policy", _canonical(terminal)))
        role_extra = copy.deepcopy(self.value)
        role_extra["roles"]["C"] = role_extra["roles"]["A"]
        attacks.append(("role extra", _canonical(role_extra)))

        for label, encoded in attacks:
            with self.subTest(label=label):
                with self.assertRaises((TypeError, ValueError)):
                    compiler.project_compiled_schema_v4_json_v1(encoded)


class CapabilityAndProvenanceTests(unittest.TestCase):
    def test_frozen_slice1_sources_and_descriptor_are_unchanged(self):
        project_root = Path(__file__).resolve().parents[1]
        expected = {
            project_root / "src" / "parity_forge_universe" / "__init__.py": (
                "bdf01c663c0d86032f9c437f545d7bf8f3efb5cb4639ce0b529a9356ac224573"
            ),
            project_root
            / "src"
            / "parity_forge_universe"
            / "typed_occupancy.py": (
                "a85dee9328279227200f2e43b6b6a12bafdf2f183f4b8db4c68180c8998aeba7"
            ),
            project_root / "src" / "parity_forge" / "__init__.py": (
                "c734c6201b5115bdf7c46859bc38e34748a346f47f8d9e04b93c20a1546c850e"
            ),
        }
        for path, expected_sha256 in expected.items():
            with self.subTest(path=str(path)):
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(), expected_sha256
                )
        self.assertEqual(
            universe.build_universe_descriptor().descriptor_root,
            "05826dc2da02890f3f562ee2d6febda523c58837affb757b5dff6d62c074e6ab",
        )

    def test_isolated_import_and_runtime_have_exact_pure_closure(self):
        source_root = str(Path(__file__).resolve().parents[1] / "src")
        code = textwrap.dedent(
            """
            import builtins
            import importlib.abc
            import os
            import socket
            import sys
            sys.path.insert(0, {source_root!r})
            allowed = {{
                "parity_forge_universe",
                "parity_forge_universe.typed_occupancy",
                "parity_forge_universe.schema_v4_compiler",
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
                raise RuntimeError("forbidden compiler I/O")
            builtins.open = fail_io
            os.open = fail_io
            socket.socket = fail_io
            import parity_forge_universe.schema_v4_compiler as compiler
            import parity_forge_universe.typed_occupancy as universe
            skeleton = universe.enumerate_fresh_canonical_profiled_skeletons()[0]
            setup = compiler.TypedSetupV1(1, ((0, 0),), ((2, 2),))
            carrier = compiler.TypedSetupCarrierV1(1, skeleton, setup)
            member = compiler.TypedDefinitionMemberV1(
                1, carrier, compiler.RoleOwner.A
            )
            encoded = compiler.compile_schema_v4_json_v1(member)
            assert compiler.project_compiled_schema_v4_json_v1(encoded) == member
            loaded = {{
                name for name in sys.modules
                if name == "parity_forge"
                or name.startswith("parity_forge.")
                or name == "parity_forge_universe"
                or name.startswith("parity_forge_universe.")
            }}
            assert loaded == allowed, sorted(loaded)
            """
        ).format(source_root=source_root)
        completed = subprocess.run(
            [sys.executable, "-I", "-c", code],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_production_ast_has_no_io_dynamic_import_or_gameplay_capability(self):
        package_root = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "parity_forge_universe"
        )
        source_paths = (
            package_root / "__init__.py",
            package_root / "typed_occupancy.py",
            package_root / "schema_v4_compiler.py",
        )
        forbidden_imports = {
            "asyncio",
            "http",
            "importlib",
            "multiprocessing",
            "os",
            "pathlib",
            "requests",
            "shutil",
            "socket",
            "subprocess",
            "urllib",
        }
        forbidden_names = {
            "engine",
            "apply_action",
            "legal_actions",
            "terminal_status",
            "goal_satisfied",
            "solver",
            "solve_game",
            "agent",
            "play",
            "play_game",
            "replay",
            "telemetry",
            "atlas",
            "candidate",
            "selection",
            "outcome",
            "winner",
        }
        forbidden_calls = forbidden_names | {
            "__import__",
            "compile",
            "eval",
            "exec",
            "open",
        }
        nodes = []
        imported = set()
        for source_path in source_paths:
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
            nodes.extend(ast.walk(tree))
        for node in nodes:
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                imported.add((node.module or "").split(".")[0])
        self.assertTrue(forbidden_imports.isdisjoint(imported), sorted(imported))

        referenced_names = {
            node.id for node in nodes if isinstance(node, ast.Name)
        }
        called_names = {
            node.func.id
            for node in nodes
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        called_attributes = {
            node.func.attr
            for node in nodes
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        self.assertTrue(forbidden_names.isdisjoint(referenced_names))
        self.assertTrue(forbidden_calls.isdisjoint(called_names))
        self.assertTrue(forbidden_calls.isdisjoint(called_attributes))

    def test_public_version_bindings_fail_closed_when_rebound(self):
        skeleton = _fresh_skeletons()[0]
        setup = _setup()
        carrier = _carrier(skeleton, setup)
        member = _member(skeleton, setup=setup)
        cases = (
            (
                "TYPED_SETUP_VERSION_V1",
                lambda: compiler.canonical_typed_setup_json_v1(setup),
            ),
            (
                "TYPED_SETUP_CARRIER_VERSION_V1",
                lambda: compiler.canonical_typed_setup_carrier_json_v1(carrier),
            ),
            (
                "TYPED_DEFINITION_MEMBER_VERSION_V1",
                lambda: compiler.canonical_typed_definition_member_json_v1(member),
            ),
            (
                "TYPED_OCCUPANCY_COMPILER_VERSION",
                lambda: compiler.compile_schema_v4_json_v1(member),
            ),
        )
        for name, operation in cases:
            for replacement in (True, 2):
                with self.subTest(name=name, replacement=replacement):
                    with mock.patch.object(compiler, name, replacement):
                        with self.assertRaises((TypeError, ValueError)):
                            operation()

    def test_typed_class_and_validation_method_rebindings_fail_closed(self):
        skeleton = _fresh_skeletons()[0]
        setup = _setup()
        carrier = _carrier(skeleton, setup)
        member = _member(skeleton, setup=setup)
        cases = (
            (
                compiler,
                "TypedSetupV1",
                object,
                lambda: compiler.canonical_typed_setup_json_v1(setup),
            ),
            (
                compiler,
                "TypedSetupCarrierV1",
                object,
                lambda: compiler.canonical_typed_setup_carrier_json_v1(carrier),
            ),
            (
                compiler,
                "TypedDefinitionMemberV1",
                object,
                lambda: compiler.compile_schema_v4_json_v1(member),
            ),
            (
                compiler.TypedSetupV1,
                "_assert_unchanged",
                lambda _self: None,
                lambda: compiler.canonical_typed_setup_json_v1(setup),
            ),
            (
                compiler.TypedSetupCarrierV1,
                "_payload_unchecked",
                lambda _self: {},
                lambda: compiler.canonical_typed_setup_carrier_json_v1(carrier),
            ),
            (
                compiler.TypedDefinitionMemberV1,
                "_assert_unchanged",
                lambda _self: None,
                lambda: compiler.compile_schema_v4_json_v1(member),
            ),
            (
                universe.ProfiledSkeleton,
                "to_dict",
                lambda _self: {},
                lambda: compiler.compile_schema_v4_json_v1(member),
            ),
            (
                universe.ProfiledRole,
                "_assert_unchanged",
                lambda _self: None,
                lambda: compiler.compile_schema_v4_json_v1(member),
            ),
        )
        for target, name, replacement, operation in cases:
            with self.subTest(target=getattr(target, "__name__", repr(target)), name=name):
                with mock.patch.object(target, name, replacement):
                    with self.assertRaises((TypeError, ValueError)):
                        operation()

    def test_role_owner_registry_class_and_same_payload_clone_attacks_fail_closed(self):
        skeleton = _fresh_skeletons()[0]
        carrier = _carrier(skeleton)
        member_map = compiler.RoleOwner._member_map_
        value_map = compiler.RoleOwner._value2member_map_
        saved_member_map = dict(member_map)
        saved_value_map = dict(value_map)
        try:
            member_map["FORGED_ALIAS"] = compiler.RoleOwner.A
            with self.assertRaises(compiler.CompilerClosureError):
                compiler.TypedDefinitionMemberV1(1, carrier, compiler.RoleOwner.A)
        finally:
            member_map.clear()
            member_map.update(saved_member_map)

        foreign = __import__("enum").Enum(
            "RoleOwner", (("A", "A"), ("B", "B")), type=str
        )
        with mock.patch.object(compiler, "RoleOwner", foreign):
            with self.assertRaises(compiler.CompilerClosureError):
                compiler.parse_typed_definition_member_v1(
                    _member(skeleton).to_dict()
                )

        owner_type = compiler.RoleOwner
        original = owner_type.A
        forged = str.__new__(owner_type, "A")
        object.__setattr__(forged, "_name_", "A")
        object.__setattr__(forged, "_value_", "A")
        try:
            type.__setattr__(owner_type, "A", forged)
            member_map["A"] = forged
            value_map["A"] = forged
            with self.assertRaises(compiler.CompilerClosureError):
                compiler.TypedDefinitionMemberV1(1, carrier, forged)
        finally:
            type.__setattr__(owner_type, "A", original)
            member_map.clear()
            member_map.update(saved_member_map)
            value_map.clear()
            value_map.update(saved_value_map)

    def test_d4_registry_class_and_same_payload_clone_attacks_fail_closed(self):
        skeleton = _fresh_skeletons()[0]
        setup = _setup()
        enum_type = universe.D4Transform
        member_map = enum_type._member_map_
        value_map = enum_type._value2member_map_
        saved_member_map = dict(member_map)
        saved_value_map = dict(value_map)
        try:
            member_map["FORGED_ALIAS"] = enum_type.I
            with self.assertRaises(universe.UniverseClosureError):
                compiler.transform_typed_setup_v1(setup, enum_type.I)
        finally:
            member_map.clear()
            member_map.update(saved_member_map)

        foreign = __import__("enum").Enum(
            "D4Transform",
            tuple((name, name) for name in _D4_INVERSES),
            type=str,
        )
        with mock.patch.object(universe, "D4Transform", foreign):
            with self.assertRaises(compiler.CompilerClosureError):
                compiler.transform_typed_setup_v1(setup, enum_type.I)

        original = enum_type.I
        forged = str.__new__(enum_type, "I")
        object.__setattr__(forged, "_name_", "I")
        object.__setattr__(forged, "_value_", "I")
        try:
            type.__setattr__(enum_type, "I", forged)
            member_map["I"] = forged
            value_map["I"] = forged
            with self.assertRaises(universe.UniverseClosureError):
                compiler.transform_typed_setup_v1(setup, forged)
        finally:
            type.__setattr__(enum_type, "I", original)
            member_map.clear()
            member_map.update(saved_member_map)
            value_map.clear()
            value_map.update(saved_value_map)


if __name__ == "__main__":
    unittest.main()
