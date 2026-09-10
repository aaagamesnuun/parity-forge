import hashlib
import json
import unittest
from dataclasses import FrozenInstanceError

from parity_forge.family import (
    FAMILY_REGISTRY_VERSION,
    FAMILY_SIGNATURE_VERSION,
    NONRETIRED_ACTION_PRIMITIVES_V1,
    ActionPrimitive,
    FamilyRecord,
    FamilyRegistry,
    FamilySignature,
    GoalPrimitive,
    RoleSignature,
    StateKernel,
    TerminalContract,
    TurnStructure,
    canonical_family_registry_json,
    canonical_family_signature_json,
    family_registry_hash,
    family_signature_hash,
    parse_family_record,
    parse_family_registry,
    parse_family_signature,
    validate_nonretired_family_registry,
    validate_nonretired_family_signature,
)


def signature_mapping():
    return {
        "signature_version": 1,
        "state_kernel": "OCCUPANCY",
        "roles": {
            "A": {
                "action_primitive": "PUSH",
                "goal_primitive": "CONNECT_EDGES",
            },
            "B": {
                "action_primitive": "HOP",
                "goal_primitive": "REACH_EDGE",
            },
        },
        "terminal_contract": (
            "ANY_GOAL_ACTION_ACTOR_INITIAL_FIRST_PRIORITY_"
            "PLY_CAP_STUCK_LOSS_V1"
        ),
        "turn_structure": "ALTERNATING_SINGLE_ACTION",
    }


def proposed_plan_0012_cells():
    pairs = (
        ("PUSH", "REACH_EDGE", "HOP", "REACH_EDGE"),
        ("SWAP", "CONNECT_EDGES", "HOP", "REACH_EDGE"),
        ("CONVERT", "CONNECT_EDGES", "PUSH", "REACH_EDGE"),
        ("MOVE_CAPTURE", "ELIMINATE", "HOP", "REACH_EDGE"),
        ("CONVERT", "ELIMINATE", "MOVE_CAPTURE", "ELIMINATE"),
        ("PUSH", "CONNECT_EDGES", "SWAP", "CONNECT_EDGES"),
    )
    cells = []
    for action_a, goal_a, action_b, goal_b in pairs:
        value = signature_mapping()
        value["roles"]["A"] = {
            "action_primitive": action_a,
            "goal_primitive": goal_a,
        }
        value["roles"]["B"] = {
            "action_primitive": action_b,
            "goal_primitive": goal_b,
        }
        cells.append(parse_family_signature(value))
    return tuple(cells)


class FamilySignatureTests(unittest.TestCase):
    def test_strict_roundtrip_and_canonical_role_order(self):
        value = signature_mapping()
        signature = parse_family_signature(value)

        self.assertEqual(signature.signature_version, FAMILY_SIGNATURE_VERSION)
        self.assertEqual(signature.state_kernel, StateKernel.OCCUPANCY)
        self.assertEqual(
            signature.roles,
            (("A", signature.role_a), ("B", signature.role_b)),
        )
        self.assertEqual(list(signature.to_dict()["roles"]), ["A", "B"])
        self.assertEqual(signature.to_dict(), value)
        self.assertEqual(parse_family_signature(signature.to_dict()), signature)
        self.assertEqual(
            canonical_family_signature_json(signature),
            json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ),
        )

    def test_semantic_hash_is_stable_domain_separated_and_sensitive(self):
        signature = parse_family_signature(signature_mapping())
        digest = family_signature_hash(signature)
        self.assertEqual(
            canonical_family_signature_json(signature),
            '{"roles":{"A":{"action_primitive":"PUSH",'
            '"goal_primitive":"CONNECT_EDGES"},"B":{'
            '"action_primitive":"HOP","goal_primitive":"REACH_EDGE"}},'
            '"signature_version":1,"state_kernel":"OCCUPANCY",'
            '"terminal_contract":"ANY_GOAL_ACTION_ACTOR_INITIAL_FIRST_'
            'PRIORITY_PLY_CAP_STUCK_LOSS_V1","turn_structure":'
            '"ALTERNATING_SINGLE_ACTION"}',
        )
        self.assertEqual(
            digest,
            "fd3a6b8f394efac6c7e6c0a60053e5ceba012ae4f75b4b12454be75c6c66362e",
        )
        self.assertEqual(len(digest), 64)
        self.assertEqual(digest, family_signature_hash(signature))
        self.assertNotEqual(
            digest,
            hashlib.sha256(
                canonical_family_signature_json(signature).encode("utf-8")
            ).hexdigest(),
        )

        for path, replacement in (
            (("roles", "A", "action_primitive"), "SWAP"),
            (("roles", "B", "goal_primitive"), "ELIMINATE"),
            (("terminal_contract",), "ACTOR_GOAL_PLY_CAP_STUCK_LOSS_V1"),
        ):
            with self.subTest(path=path):
                changed = signature_mapping()
                target = changed
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = replacement
                self.assertNotEqual(
                    digest, family_signature_hash(parse_family_signature(changed))
                )

    def test_registry_id_is_not_part_of_semantic_identity(self):
        signature = parse_family_signature(signature_mapping())
        first = FamilyRecord("push-hop", signature)
        alias = FamilyRecord("renamed-family", signature)
        self.assertEqual(first.semantic_hash, alias.semantic_hash)
        self.assertNotIn("family_id", canonical_family_signature_json(signature))
        with self.assertRaisesRegex(ValueError, "aliases the same semantic signature"):
            FamilyRegistry((first, alias))

    def test_signature_rejects_unknown_free_form_or_generation_fields(self):
        for field, value in (
            ("display_name", "Push Hop"),
            ("callback", "run_me"),
            ("board_sizes", [3]),
            ("setup_template", "draft"),
            ("outcomes", []),
        ):
            with self.subTest(field=field):
                candidate = signature_mapping()
                candidate[field] = value
                with self.assertRaisesRegex(ValueError, "unknown"):
                    parse_family_signature(candidate)

    def test_unknown_missing_and_malformed_fields_are_rejected(self):
        for field in tuple(signature_mapping()):
            with self.subTest(missing=field):
                value = signature_mapping()
                del value[field]
                with self.assertRaisesRegex(ValueError, "missing"):
                    parse_family_signature(value)

        missing_role = signature_mapping()
        del missing_role["roles"]["B"]
        with self.assertRaisesRegex(ValueError, "missing"):
            parse_family_signature(missing_role)

        extra_role = signature_mapping()
        extra_role["roles"]["C"] = dict(extra_role["roles"]["A"])
        with self.assertRaisesRegex(ValueError, "unknown"):
            parse_family_signature(extra_role)

        extra_role_field = signature_mapping()
        extra_role_field["roles"]["A"]["predicate"] = "arbitrary"
        with self.assertRaisesRegex(ValueError, "unknown"):
            parse_family_signature(extra_role_field)

        invalid_ludeme = signature_mapping()
        invalid_ludeme["roles"]["A"]["action_primitive"] = "SCRIPT"
        with self.assertRaisesRegex(ValueError, "must be one of"):
            parse_family_signature(invalid_ludeme)

        for reserved in ("REMOVE", "ORIENT", "FOLLOW"):
            with self.subTest(reserved_action=reserved):
                value = signature_mapping()
                value["roles"]["A"]["action_primitive"] = reserved
                with self.assertRaisesRegex(ValueError, "must be one of"):
                    parse_family_signature(value)
        for reserved in ("DIRECTED_CONNECT",):
            with self.subTest(reserved_goal=reserved):
                value = signature_mapping()
                value["roles"]["A"]["goal_primitive"] = reserved
                with self.assertRaisesRegex(ValueError, "must be one of"):
                    parse_family_signature(value)

        reserved_kernel = signature_mapping()
        reserved_kernel["state_kernel"] = "FINITE_RESERVE"
        with self.assertRaisesRegex(ValueError, "must be one of"):
            parse_family_signature(reserved_kernel)

    def test_bool_enum_and_non_string_spoofing_are_rejected(self):
        for invalid in (True, False, 1.0, "1", None):
            with self.subTest(version=invalid):
                value = signature_mapping()
                value["signature_version"] = invalid
                with self.assertRaises((TypeError, ValueError)):
                    parse_family_signature(value)

        for invalid in (True, 1, ActionPrimitive.PUSH, lambda: None, object()):
            with self.subTest(action=repr(invalid)):
                value = signature_mapping()
                value["roles"]["A"]["action_primitive"] = invalid
                with self.assertRaises(TypeError):
                    parse_family_signature(value)

    def test_values_are_frozen_detached_and_revalidated_at_hash_boundary(self):
        value = signature_mapping()
        signature = parse_family_signature(value)
        before = canonical_family_signature_json(signature)
        value["state_kernel"] = "not-a-kernel"
        value["roles"].clear()
        self.assertEqual(canonical_family_signature_json(signature), before)

        with self.assertRaises(FrozenInstanceError):
            signature.state_kernel = StateKernel.OCCUPANCY
        with self.assertRaises(FrozenInstanceError):
            signature.role_a.action_primitive = ActionPrimitive.SWAP

        object.__setattr__(signature, "signature_version", 99)
        with self.assertRaisesRegex(ValueError, "parser-normalized"):
            canonical_family_signature_json(signature)
        with self.assertRaisesRegex(ValueError, "parser-normalized"):
            family_signature_hash(signature)

    def test_direct_construction_requires_exact_types(self):
        role = RoleSignature(ActionPrimitive.PUSH, GoalPrimitive.REACH_EDGE)
        with self.assertRaises(TypeError):
            RoleSignature("PUSH", GoalPrimitive.REACH_EDGE)
        with self.assertRaises(TypeError):
            FamilySignature(
                signature_version=True,
                state_kernel=StateKernel.OCCUPANCY,
                role_a=role,
                role_b=role,
                terminal_contract=(
                    TerminalContract.ANY_GOAL_ACTION_ACTOR_INITIAL_FIRST_PRIORITY_PLY_CAP_STUCK_LOSS_V1
                ),
                turn_structure=TurnStructure.ALTERNATING_SINGLE_ACTION,
            )

    def test_proposed_six_cells_are_representable_unique_and_non_place_move(self):
        cells = proposed_plan_0012_cells()
        self.assertEqual(len(cells), 6)
        self.assertEqual(len({family_signature_hash(cell) for cell in cells}), 6)
        self.assertIs(
            cells[3].role_a.action_primitive,
            ActionPrimitive.MOVE_CAPTURE,
        )
        self.assertIs(
            cells[4].role_b.action_primitive,
            ActionPrimitive.MOVE_CAPTURE,
        )
        for cell in cells:
            self.assertIsNot(cell.role_a.action_primitive, ActionPrimitive.PLACE)
            self.assertIsNot(cell.role_b.action_primitive, ActionPrimitive.MOVE)
            self.assertNotIn(
                ActionPrimitive.CAPTURE_STEP,
                (
                    cell.role_a.action_primitive,
                    cell.role_b.action_primitive,
                ),
            )
            self.assertIs(
                cell.terminal_contract,
                TerminalContract.ANY_GOAL_ACTION_ACTOR_INITIAL_FIRST_PRIORITY_PLY_CAP_STUCK_LOSS_V1,
            )
            self.assertEqual(validate_nonretired_family_signature(cell), cell)

    def test_retired_capture_step_is_readable_but_not_emittable(self):
        retired_value = signature_mapping()
        retired_value["roles"]["A"]["action_primitive"] = "CAPTURE_STEP"
        retired = parse_family_signature(retired_value)

        self.assertEqual(retired.to_dict(), retired_value)
        self.assertEqual(parse_family_signature(retired.to_dict()), retired)
        self.assertEqual(
            canonical_family_signature_json(retired),
            json.dumps(
                retired_value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ),
        )
        self.assertEqual(
            family_signature_hash(retired),
            "f60327049e08908de3e6e9457230c9096d193b1c31a2b54058d79dcc130a69b4",
        )
        self.assertEqual(
            set(ActionPrimitive) - set(NONRETIRED_ACTION_PRIMITIVES_V1),
            {ActionPrimitive.CAPTURE_STEP},
        )
        with self.assertRaisesRegex(
            ValueError,
            "CAPTURE_STEP is retired; use MOVE_CAPTURE",
        ):
            validate_nonretired_family_signature(retired)

        retired_b_value = signature_mapping()
        retired_b_value["roles"]["B"]["action_primitive"] = "CAPTURE_STEP"
        with self.assertRaisesRegex(ValueError, "family role B"):
            validate_nonretired_family_signature(
                parse_family_signature(retired_b_value)
            )

        historical_registry = FamilyRegistry(
            (FamilyRecord("retired-capture", retired),)
        )
        self.assertEqual(
            parse_family_registry(historical_registry.to_dict()),
            historical_registry,
        )
        with self.assertRaisesRegex(
            ValueError,
            "family record retired-capture uses a retired primitive",
        ):
            validate_nonretired_family_registry(historical_registry)

        active_registry = FamilyRegistry(
            FamilyRecord("active-{}".format(index), signature)
            for index, signature in enumerate(proposed_plan_0012_cells())
        )
        self.assertEqual(
            validate_nonretired_family_registry(active_registry),
            active_registry,
        )

    def test_record_parser_is_strict(self):
        value = {"family_id": "push-hop-v1", "signature": signature_mapping()}
        record = parse_family_record(value)
        self.assertEqual(record.to_dict(), value)
        for invalid in (
            "Push-Hop",
            "push_hop",
            "push--hop",
            "push-hop-",
            "",
            True,
        ):
            with self.subTest(identifier=repr(invalid)):
                with self.assertRaises(ValueError):
                    parse_family_record(
                        {"family_id": invalid, "signature": signature_mapping()}
                    )

        unknown = dict(value)
        unknown["display_name"] = "Push Hop"
        with self.assertRaisesRegex(ValueError, "unknown"):
            parse_family_record(unknown)

    def test_registry_roundtrip_order_hash_and_detachment(self):
        first = parse_family_signature(signature_mapping())
        second_value = signature_mapping()
        second_value["roles"]["A"]["action_primitive"] = "SWAP"
        second = parse_family_signature(second_value)
        source = [
            FamilyRecord("push-hop", first),
            FamilyRecord("swap-hop", second),
        ]
        registry = FamilyRegistry(source)
        source.clear()

        self.assertEqual(len(registry), 2)
        self.assertEqual(registry.family_ids, ("push-hop", "swap-hop"))
        self.assertEqual(tuple(registry), registry.records)
        self.assertEqual(registry.get("swap-hop").signature, second)
        self.assertEqual(parse_family_registry(registry.to_dict()), registry)
        self.assertEqual(
            registry.to_dict()["registry_version"], FAMILY_REGISTRY_VERSION
        )

        canonical = canonical_family_registry_json(registry)
        self.assertEqual(
            canonical,
            json.dumps(
                registry.to_dict(),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ),
        )
        digest = family_registry_hash(registry)
        self.assertEqual(len(digest), 64)
        self.assertNotEqual(
            digest,
            family_registry_hash(FamilyRegistry(tuple(reversed(registry.records)))),
        )
        self.assertNotEqual(
            digest, hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        )

        one_record = FamilyRegistry((FamilyRecord("push-hop", first),))
        self.assertEqual(
            canonical_family_registry_json(one_record),
            '{"records":[{"family_id":"push-hop","signature":{'
            '"roles":{"A":{"action_primitive":"PUSH",'
            '"goal_primitive":"CONNECT_EDGES"},"B":{'
            '"action_primitive":"HOP","goal_primitive":"REACH_EDGE"}},'
            '"signature_version":1,"state_kernel":"OCCUPANCY",'
            '"terminal_contract":"ANY_GOAL_ACTION_ACTOR_INITIAL_FIRST_'
            'PRIORITY_PLY_CAP_STUCK_LOSS_V1","turn_structure":'
            '"ALTERNATING_SINGLE_ACTION"}}],"registry_version":1}',
        )
        self.assertEqual(
            family_registry_hash(one_record),
            "ed5e47dbb29ffe419a4b33ae926d906053247615300f6daa36c51ccc23adc3cb",
        )

        with self.assertRaises(FrozenInstanceError):
            registry.records = ()
        with self.assertRaises(KeyError):
            registry.get("missing")
        with self.assertRaises(TypeError):
            registry.get(True)

    def test_registry_rejects_duplicates_arbitrary_values_and_bad_schema(self):
        first = parse_family_signature(signature_mapping())
        changed = signature_mapping()
        changed["roles"]["A"]["action_primitive"] = "SWAP"
        second = parse_family_signature(changed)
        with self.assertRaisesRegex(ValueError, "duplicate family_id"):
            FamilyRegistry(
                (FamilyRecord("same", first), FamilyRecord("same", second))
            )
        with self.assertRaisesRegex(ValueError, "aliases"):
            FamilyRegistry(
                (FamilyRecord("first", first), FamilyRecord("second", first))
            )
        with self.assertRaises(TypeError):
            FamilyRegistry((FamilyRecord("valid", first), lambda: None))
        with self.assertRaises(TypeError):
            FamilyRegistry(3)

        bad_version = FamilyRegistry((FamilyRecord("valid", first),)).to_dict()
        bad_version["registry_version"] = True
        with self.assertRaises(TypeError):
            parse_family_registry(bad_version)
        tuple_records = FamilyRegistry((FamilyRecord("valid", first),)).to_dict()
        tuple_records["records"] = tuple(tuple_records["records"])
        with self.assertRaisesRegex(TypeError, "array"):
            parse_family_registry(tuple_records)

    def test_registry_detaches_and_rejects_low_level_forgery(self):
        signature = parse_family_signature(signature_mapping())
        record = FamilyRecord("push-hop", signature)
        registry = FamilyRegistry((record,))
        self.assertIsNot(registry.records[0], record)
        self.assertIsNot(registry.records[0].signature, signature)

        object.__setattr__(signature, "signature_version", 99)
        self.assertEqual(registry.records[0].signature.signature_version, 1)

        object.__setattr__(registry.records[0].signature, "signature_version", 99)
        with self.assertRaisesRegex(ValueError, "parser-normalized"):
            canonical_family_registry_json(registry)

        fresh_registry = FamilyRegistry(
            (
                FamilyRecord(
                    "push-hop",
                    parse_family_signature(signature_mapping()),
                ),
            )
        )
        object.__setattr__(
            fresh_registry.records[0].signature.role_a,
            "action_primitive",
            ActionPrimitive.SWAP,
        )
        with self.assertRaisesRegex(ValueError, "changed after construction"):
            fresh_registry.to_dict()
        with self.assertRaisesRegex(ValueError, "changed after construction"):
            tuple(fresh_registry)
        with self.assertRaisesRegex(ValueError, "changed after construction"):
            fresh_registry.get("push-hop")
        with self.assertRaisesRegex(ValueError, "parser-normalized"):
            canonical_family_registry_json(fresh_registry)

    def test_public_canonical_functions_reject_arbitrary_objects(self):
        for value in (signature_mapping(), object(), lambda: None, None):
            with self.subTest(value=repr(value)):
                with self.assertRaises(TypeError):
                    canonical_family_signature_json(value)
                with self.assertRaises(TypeError):
                    family_signature_hash(value)
                with self.assertRaises(TypeError):
                    canonical_family_registry_json(value)
                with self.assertRaises(TypeError):
                    family_registry_hash(value)


if __name__ == "__main__":
    unittest.main()
