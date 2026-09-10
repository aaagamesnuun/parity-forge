import ast
import copy
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import unittest
from unittest import mock

from parity_forge.dsl import canonical_json, parse_definition
from parity_forge.symmetry import D4_TRANSFORMS, transform_definition
from parity_forge_universe import initial_structure as initial
from parity_forge_universe import schema_v4_compiler as compiler
from parity_forge_universe import typed_occupancy as universe
from research.parity_forge_history import history_identity, history_pins, wire_identity
from scripts import plan0016_selection as selection
from tests.test_agency_benchmark import FIXTURES


RAW = b"synthetic compact-report test double, never production evidence"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def shard(action="CONVERT", profile="ORTHOGONAL_4", supply=10,
          pairs=((1, 1),), contact="CONTACT"):
    source = {
        "universe_version": 1,
        "roles": {
            "A": {"action_primitive": action, "goal_primitive": "REACH_EDGE",
                  "vector_profile": profile, "target_edges": ["BOTTOM"]},
            "B": {"action_primitive": "HOP", "goal_primitive": "REACH_EDGE",
                  "vector_profile": "ORTHOGONAL_4", "target_edges": ["BOTTOM"]},
        },
    }
    skeleton = universe.parse_profiled_skeleton(source)
    return {
        "skeleton": {
            "canonical_profiled_skeleton_json":
                universe.canonical_profiled_skeleton_json(skeleton),
            "typed_skeleton_hash": universe.profiled_skeleton_hash(skeleton),
            "role_neutral_skeleton_hash":
                universe.role_neutral_profiled_skeleton_hash(skeleton),
            "role_neutral_semantic_hash":
                universe.role_neutral_semantic_hash(skeleton.semantic_signature),
            "exact_stabilizer": ["I", "FLR"],
        },
        "contact": {
            name: {"eligible_representative_count": supply if name == contact else 0}
            for name in selection.CONTACT_CLASSES
        },
        "eligible_supply_by_count_pair_and_contact": [
            {"initial_counts": {"A": a, "B": b}, "contact_class": contact,
             "representative_count": supply, "weighted_count": supply}
            for a, b in pairs
        ],
    }


def short_pair(index=1):
    source = FIXTURES[index]["definition"]
    values = []
    for owner in ("A", "B"):
        value = copy.deepcopy(source)
        value["first_player"] = owner
        values.append(wire_identity.normalize_definition_v1(value))
    return values


def snapshot(carrier, eligible=True, contact="CONTACT"):
    facts = {
        "identities": {
            "typed_carrier_hash": compiler.typed_setup_carrier_hash_v1(carrier),
            "typed_skeleton_hash": universe.profiled_skeleton_hash(carrier.skeleton),
        },
        "descriptor_groups": {"contact": {"contact_class": contact}},
        "rejection_reasons": [] if eligible else [
            {"code": "INITIAL_IMMOBILITY", "role": "A", "first_player": None}
        ],
        "eligible": eligible,
        "evidence_digest": "e" * 64,
    }
    return canonical(facts).decode(), "f" * 64


class SelectionTests(unittest.TestCase):
    def run_selection(self, shards, derive=None, compile_pair=None, rank=None):
        report = {"skeleton_shards": copy.deepcopy(shards)}
        original = copy.deepcopy(report)
        proof = {
            "report": report,
            "report_ref": {"byte_count": len(RAW), "sha256": hashlib.sha256(RAW).hexdigest()},
        }
        with mock.patch.object(selection, "REPORT_BYTES", len(RAW)), \
             mock.patch.object(selection, "REPORT_SHA256", hashlib.sha256(RAW).hexdigest()), \
             mock.patch.object(selection.reconstruction,
                               "reconstruct_static_census_report_artifact_v1",
                               return_value=proof) as rebuild:
            # Doubles are absent from the actual public compiler/kernel test.
            with ExitStack() as stack:
                if derive is not None:
                    stack.enter_context(mock.patch.object(
                        selection.initial, "prepare_initial_structure_skeleton_v1",
                        return_value=object()))
                    stack.enter_context(mock.patch.object(
                        selection.initial, "derive_prepared_initial_structure_snapshot_v1",
                        side_effect=lambda token, carrier: derive(carrier)))
                if compile_pair is not None:
                    stack.enter_context(mock.patch.object(
                        selection, "_compile_pair", side_effect=compile_pair))
                if rank is not None:
                    stack.enter_context(mock.patch.object(selection, "_rank",
                                                          side_effect=rank))
                result = selection.select_pilot(RAW)
            rebuild.assert_called_once_with(RAW)
        self.assertEqual(report, original)
        return result

    def test_report_is_authenticated_before_public_reconstruction(self):
        with mock.patch.object(selection.reconstruction,
                               "reconstruct_static_census_report_artifact_v1") as rebuild:
            with self.assertRaises(TypeError):
                selection.select_pilot(bytearray(RAW))
            with self.assertRaisesRegex(ValueError, "byte count"):
                selection.select_pilot(RAW)
            with mock.patch.object(selection, "REPORT_BYTES", len(RAW)):
                with self.assertRaisesRegex(ValueError, "SHA-256"):
                    selection.select_pilot(RAW)
            rebuild.assert_not_called()

    def test_rank_bytes_match_independent_domain_and_json_calculation(self):
        value = {"goal_pair": ["ELIMINATE", "REACH_EDGE"],
                 "contact_class": "CONTACT", "semantic_hash": "a" * 64}
        encoded = canonical(value)
        expected = hashlib.sha256(
            b"parity-forge:plan0016:pilot:semantic:v1\0" + encoded
        ).hexdigest()
        self.assertEqual(selection._rank("semantic", value), (expected, encoded))
        self.assertNotEqual(expected, hashlib.sha256(
            b"parity-forge:plan0016:pilot:semantic:v1\\0" + encoded
        ).hexdigest())

    def test_zero_supply_preserves_all_macro_slots_and_class_denominator(self):
        result = self.run_selection([shard(supply=0)])
        self.assertEqual(len(result["slots"]), 24)
        self.assertEqual(result["attempts"], [])
        self.assertEqual(result["selected"], [])
        self.assertEqual(result["coverage"]["semantic_class_count"], 1)
        self.assertEqual(result["coverage"]["classes"][0]["disposition"], "STATIC_ZERO")
        self.assertEqual(result["coverage"]["slot_dispositions"], {"STATIC_ZERO": 24})
        expected = [(list(goals), contact, slot)
                    for goals in selection.GOAL_PAIRS
                    for contact in selection.CONTACT_CLASSES for slot in range(2)]
        self.assertEqual([(row["goal_pair"], row["contact_class"], row["slot"])
                          for row in result["slots"]], expected)

    def test_static_and_contact_rejections_do_not_compile(self):
        for eligible, contact, disposition in (
            (False, "CONTACT", "STATIC_REJECTED"),
            (True, "SEPARATED", "CONTACT_MISMATCH"),
        ):
            with self.subTest(disposition=disposition):
                compiled = mock.Mock(side_effect=AssertionError("must not compile"))
                result = self.run_selection(
                    [shard()], derive=lambda c: snapshot(c, eligible, contact),
                    compile_pair=compiled,
                )
                self.assertEqual(len(result["attempts"]), 128)
                self.assertEqual({r["disposition"] for r in result["attempts"]},
                                 {disposition})
                self.assertEqual(result["selected"], [])
                active = [row for row in result["slots"] if row["semantic_hash"]]
                self.assertEqual([row["attempt_count"] for row in active], [64, 64])
                self.assertEqual({row["disposition"] for row in active},
                                 {"BOUNDED_SAMPLE_EMPTY"})
                compiled.assert_not_called()

    def test_rank_ties_use_canonical_objects_and_no_failed_class_backfill(self):
        rows = [shard(action=action) for action in ("CONVERT", "SWAP", "MOVE_CAPTURE")]
        result = self.run_selection(
            rows, derive=lambda c: snapshot(c, False),
            rank=lambda kind, value: ("0" * 64, canonical(value)),
        )
        active = [row for row in result["slots"] if row["semantic_hash"]]
        expected = sorted(row["skeleton"]["role_neutral_semantic_hash"] for row in rows)
        self.assertEqual([row["semantic_hash"] for row in active], expected[:2])
        self.assertEqual({row["semantic_hash"] for row in result["attempts"]},
                         set(expected[:2]))
        unassigned = [row for row in result["coverage"]["classes"]
                      if row["disposition"] == "NOT_ASSIGNED_BY_FIXED_RANK"]
        self.assertEqual([row["semantic_hash"] for row in unassigned], expected[2:])
        for row in result["attempts"]:
            self.assertEqual(row["cell_order"], list(range(9)))

    def test_skeleton_and_resource_round_robin_are_zero_based(self):
        rows = [shard(profile=profile, pairs=((1, 1), (2, 1)))
                for profile in ("ORTHOGONAL_4", "KING_8")]
        result = self.run_selection(rows, derive=lambda c: snapshot(c, False))
        for slot in (0, 1):
            slot_record = next(row for row in result["slots"]
                               if row["semantic_hash"] and row["slot"] == slot)
            sequence = slot_record["skeleton_ranking"]
            attempts = [row for row in result["attempts"] if row["slot"] == slot]
            for t, attempt in enumerate(attempts):
                self.assertEqual(attempt["skeleton_hash"],
                                 sequence[t % 2]["skeleton_hash"])
                self.assertEqual(attempt["skeleton_visit"], t // 2)
                self.assertEqual(attempt["initial_counts"],
                                 [[1, 1], [2, 1]][(t // 2) % 2])

    def test_source_cells_and_stabilizer_canonicalization_are_reconstructable(self):
        result = self.run_selection([shard()], derive=lambda c: snapshot(c, False))
        for row in result["attempts"][:8]:
            base = {key: row[key] for key in
                    ("goal_pair", "contact_class", "slot", "attempt", "skeleton_hash")}
            expected = sorted(range(9), key=lambda cell: (
                hashlib.sha256(b"parity-forge:plan0016:pilot:cell:v1\0" +
                               canonical({**base, "cell": cell})).hexdigest(),
                canonical({**base, "cell": cell}),
            ))
            self.assertEqual(row["cell_order"], expected)
            self.assertEqual(row["source_positions"]["A"], [list(divmod(expected[0], 3))])
            self.assertEqual(row["source_positions"]["B"], [list(divmod(expected[1], 3))])
            source = compiler.TypedSetupV1(
                1, tuple(map(tuple, row["source_positions"]["A"])),
                tuple(map(tuple, row["source_positions"]["B"])),
            )
            candidates = [compiler.transform_typed_setup_v1(source, universe.D4Transform(g))
                          for g in row["exact_stabilizer"]]
            expected_setup = min(candidates, key=compiler.canonical_typed_setup_json_v1)
            self.assertEqual(row["canonical_setup"], expected_setup.to_dict())

    def test_exact_d4_and_neutral_duplicates_consume_attempts_without_backfill(self):
        def same_short_definition(_carrier):
            pair = short_pair()
            # Different display names cannot conceal D4 or alpha-role duplicates.
            for value in pair:
                value["name"] = "duplicate-name-" + str(same_short_definition.calls)
            same_short_definition.calls += 1
            return pair
        same_short_definition.calls = 0
        result = self.run_selection([shard()], derive=snapshot,
                                    compile_pair=same_short_definition)
        self.assertEqual(len(result["selected"]), 1)
        self.assertEqual(len(result["attempts"]), 65)
        active = [row for row in result["slots"] if row["semantic_hash"]]
        self.assertEqual([r["disposition"] for r in active],
                         ["SELECTED", "BOUNDED_SAMPLE_EMPTY"])
        for row in result["attempts"][1:]:
            self.assertEqual(row["disposition"], "DUPLICATE_ACCEPTED_CARRIER")
            self.assertNotIn("exact_hash", row["duplicate_relations"])
            self.assertIn("d4_hash", row["duplicate_relations"])
            self.assertIn("role_neutral_hash", row["duplicate_relations"])

    def test_two_distinct_short_fixture_pairs_are_retained_in_first_player_order(self):
        pairs = iter((short_pair(1), short_pair(5)))
        result = self.run_selection([shard()], derive=snapshot,
                                    compile_pair=lambda c: next(pairs))
        self.assertEqual(result["coverage"]["selected_carrier_count"], 2)
        self.assertEqual(result["coverage"]["selected_definition_count"], 4)
        self.assertEqual([row["selection_index"] for row in result["selected"]], [0, 1])
        for row in result["selected"]:
            self.assertEqual([value["first_player"] for value in row["definitions"]],
                             ["A", "B"])
            self.assertEqual([value["first_player"] for value in row["definition_identities"]],
                             ["A", "B"])
            for definition, identity in zip(row["definitions"], row["definition_identities"]):
                self.assertLess(definition["max_plies"], 18)
                self.assertEqual(identity["exact_hash"],
                                 hashlib.sha256(canonical(definition)).hexdigest())
        self.assertFalse(result["exposure_boundary"]["gameplay_outcomes_used_for_selection"])
        self.assertEqual(result["exposure_boundary"]["history_projection_root"],
                         history_identity.HISTORY_PROJECTION_ROOT_V1)

    def test_exact_duplicate_relation_is_retained(self):
        result = self.run_selection([shard()], derive=snapshot,
                                    compile_pair=lambda c: short_pair())
        self.assertEqual(len(result["selected"]), 1)
        for row in result["attempts"][1:]:
            self.assertEqual(set(row["duplicate_relations"]),
                             {"exact_hash", "d4_hash", "role_neutral_hash"})

    def test_global_alpha_role_swap_duplicate_checks_both_first_players(self):
        original = short_pair()
        swapped = copy.deepcopy(original)
        for definition in swapped:
            definition["roles"] = {
                "A": definition["roles"]["B"], "B": definition["roles"]["A"]}
            definition["first_player"] = (
                "B" if definition["first_player"] == "A" else "A")
            for piece in definition["initial_pieces"]:
                piece["owner"] = "B" if piece["owner"] == "A" else "A"
            fields = [role[field] for role in definition["roles"].values()
                      for field in ("action", "goal")] + definition["initial_pieces"]
            names = {name: "alias_" + str(i) for i, name in enumerate(
                sorted({field["piece"] for field in fields}))}
            for field in fields:
                field["piece"] = names[field["piece"]]
        swapped.sort(key=lambda value: value["first_player"])
        calls = [original]
        result = self.run_selection(
            [shard()], derive=snapshot,
            compile_pair=lambda c: copy.deepcopy(calls.pop() if calls else swapped))
        self.assertEqual(len(result["selected"]), 1)
        for row in result["attempts"][1:]:
            self.assertEqual(set(row["duplicate_relations"]), {"role_neutral_hash"})

    def test_public_compiler_kernel_path_on_synthetic_report_without_gameplay(self):
        # Static typed examples are permitted; this is not the pinned production report.
        result = self.run_selection([shard()])
        self.assertGreater(len(result["selected"]), 0)
        for row in result["selected"]:
            self.assertTrue(row["static_facts"]["eligible"])
            for value in row["definitions"]:
                self.assertEqual((value["schema_version"], value["max_plies"]), (4, 18))
                parsed = parse_definition(value)
                self.assertEqual(canonical_json(parsed).encode(), canonical(value))
            setup = compiler.parse_typed_setup_v1(
                row["static_facts"]["carrier"]["setup"])
            skeleton = universe.parse_profiled_skeleton(
                row["static_facts"]["carrier"]["profiled_skeleton"])
            carrier = compiler.TypedSetupCarrierV1(1, skeleton, setup)
            independently_rederived = initial.derive_initial_structure_result_v1(carrier)
            self.assertEqual(json.loads(initial.canonical_initial_structure_result_json_v1(
                independently_rederived)), row["static_facts"])

    def test_errors_stop_instead_of_silently_turning_into_sampling_shortfall(self):
        with self.assertRaisesRegex(RuntimeError, "fixture failure"):
            self.run_selection([shard()], derive=lambda c: (
                (_ for _ in ()).throw(RuntimeError("fixture failure"))))


class NamedHistorySeparationTests(unittest.TestCase):
    def test_named_seven_fixtures_match_pins_and_have_invariant_short_horizons(self):
        pins = {row[0]: row for row in history_pins.PLAN0012_SYNTHETIC_FIXTURE_IDENTITIES_V1}
        self.assertEqual({row["fixture_id"] for row in FIXTURES}, set(pins))
        for fixture in FIXTURES:
            definition = parse_definition(fixture["definition"])
            raw = canonical_json(definition).encode()
            pin = pins[fixture["fixture_id"]]
            self.assertEqual((hashlib.sha256(raw).hexdigest(), len(raw)), (pin[1], pin[3]))
            self.assertIn(definition.max_plies, (1, 2, 3, 4))
            source = json.loads(raw)
            neutral = wire_identity.role_neutral_definition_hash_v1(source)
            for transform in D4_TRANSFORMS:
                image = json.loads(canonical_json(transform_definition(definition, transform)))
                self.assertEqual(image["max_plies"], source["max_plies"])
                image["roles"] = {"A": image["roles"]["B"], "B": image["roles"]["A"]}
                image["first_player"] = "B" if image["first_player"] == "A" else "A"
                for piece in image["initial_pieces"]:
                    piece["owner"] = "B" if piece["owner"] == "A" else "A"
                fields = [role[field] for role in image["roles"].values()
                          for field in ("action", "goal")] + image["initial_pieces"]
                labels = {label: "renamed_" + str(i) for i, label in
                          enumerate(sorted({field["piece"] for field in fields}))}
                for field in fields:
                    field["piece"] = labels[field["piece"]]
                self.assertEqual(image["max_plies"], source["max_plies"])
                self.assertEqual(wire_identity.role_neutral_definition_hash_v1(image), neutral)
        self.assertEqual(history_identity.HISTORY_SCHEMA_UNIQUE_COUNTS_V1,
                         ((1, 852), (2, 128), (3, 192), (4, 7)))

    def test_named_eighth_fixture_is_source_pinned_and_separate_from_compiler_horizon(self):
        path = Path(__file__).resolve().parents[1] / "src/parity_forge/atlas_agent_benchmark.py"
        raw = path.read_bytes()
        self.assertEqual(hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest(),
                         "ef1e99a87be4b0cf2e9e4fe30557b111fa979a7d")
        assignment = next(node for node in ast.parse(raw).body
                          if isinstance(node, ast.Assign) and
                          any(isinstance(target, ast.Name) and target.id == "_FIXTURE_SPECS_V1"
                              for target in node.targets))
        specs = ast.literal_eval(assignment.value)
        extra = [row for row in specs if row[1] == "PLAN0013_SYNTHETIC_ADDITION"]
        self.assertEqual(len(extra), 1)
        self.assertEqual(extra[0][0], "swap-simultaneous-connect-v1")
        fixture_raw = extra[0][2].encode()
        self.assertEqual(hashlib.sha256(fixture_raw).hexdigest(),
                         "eaaf30187d95c215c2d330f1e68c92b10ff7718b85e16801de2a15353b8c3db2")
        value = json.loads(fixture_raw)
        self.assertEqual(value["max_plies"], 2)
        for transform in D4_TRANSFORMS:
            image = transform_definition(parse_definition(value), transform)
            self.assertEqual(image.max_plies, 2)
            with self.assertRaisesRegex(ValueError, "max_plies 18"):
                compiler.project_compiled_schema_v4_json_v1(canonical_json(image))

    def test_public_compiler_excludes_entire_old_six_and_role_swaps(self):
        setup = compiler.TypedSetupV1(1, ((0, 0),), ((1, 1),))
        for semantic in universe.enumerate_plan0013_semantic_classes():
            def role(atom):
                edges = (() if atom.goal_primitive is universe.GoalPrimitive.ELIMINATE else
                         (universe.BoardEdge.TOP, universe.BoardEdge.BOTTOM)
                         if atom.goal_primitive is universe.GoalPrimitive.CONNECT_EDGES else
                         (universe.BoardEdge.TOP,))
                return universe.ProfiledRole(
                    atom, universe.VectorProfile.ORTHOGONAL_4,
                    universe.GoalTarget(atom.goal_primitive, edges))
            skeleton = universe.ProfiledSkeleton(1, role(semantic.role_a), role(semantic.role_b))
            for image in (skeleton, universe.role_swap_profiled_skeleton(skeleton)):
                with self.assertRaisesRegex(ValueError, "Plan-0013"):
                    compiler.TypedSetupCarrierV1(1, image, setup)


if __name__ == "__main__":
    unittest.main()
