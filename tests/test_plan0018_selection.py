"""Synthetic-only selection tests; engine checks use excluded E/E fixtures."""

import ast
import copy
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

from parity_forge.dsl import canonical_json, parse_definition
from parity_forge.engine import apply_action, initial_state, legal_actions
from parity_forge.symmetry import transform_definition
from parity_forge_universe import schema_v4_compiler as compiler
from parity_forge_universe import typed_occupancy as universe
from research.parity_forge_history import wire_identity
from scripts import plan0018_selection as selection


RAW = b"Plan18 synthetic compact-report double: no production members"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def wire(converter_goal="REACH_EDGE", capturer_goal="ELIMINATE", first="A"):
    def goal(kind, own, other):
        value = {"kind": kind, "piece": other if kind == "ELIMINATE" else own}
        if kind == "REACH_EDGE":
            value["edge"] = "BOTTOM"
        elif kind == "CONNECT_EDGES":
            value["edges"] = ["LEFT", "RIGHT"]
        return value
    return {
        "schema_version": 4, "name": "plan18-synthetic", "board_size": 3,
        "max_plies": 18, "first_player": first,
        "roles": {
            "A": {"action": {"kind": "CONVERT", "piece": "a",
                              "vectors": [[-1, -1], [-1, 0], [-1, 1], [0, -1], [0, 1], [1, -1], [1, 0], [1, 1]]},
                  "goal": goal(converter_goal, "a", "b")},
            "B": {"action": {"kind": "MOVE_CAPTURE", "piece": "b",
                              "vectors": [[-1, 0], [0, -1], [0, 1], [1, 0]]},
                  "goal": goal(capturer_goal, "b", "a")},
        },
        "initial_pieces": [
            {"owner": "B", "piece": "b", "position": [1, 0]},
            {"owner": "A", "piece": "a", "position": [1, 1]},
            {"owner": "B", "piece": "b", "position": [1, 2]},
        ],
    }


def pair(raw=None):
    raw = wire() if raw is None else raw
    return [wire_identity.normalize_definition_v1({**copy.deepcopy(raw), "first_player": first})
            for first in ("A", "B")]


def role_swap(raw):
    value = copy.deepcopy(raw)
    value["roles"] = {"A": value["roles"]["B"], "B": value["roles"]["A"]}
    value["first_player"] = "B" if value["first_player"] == "A" else "A"
    for piece in value["initial_pieces"]:
        piece["owner"] = "B" if piece["owner"] == "A" else "A"
    return wire_identity.normalize_definition_v1(value)


def shard(goals=("REACH_EDGE", "ELIMINATE"), profile="KING_8", supply=10,
          pairs=((1, 2),), converter="A", other_action="MOVE_CAPTURE"):
    def role(action, goal, vectors):
        edges = [] if goal == "ELIMINATE" else ["RIGHT", "LEFT"] if goal == "CONNECT_EDGES" else ["BOTTOM"]
        return {"action_primitive": action, "goal_primitive": goal,
                "vector_profile": vectors, "target_edges": edges}
    roles = {"A": role("CONVERT", goals[0], profile),
             "B": role(other_action, goals[1], "ORTHOGONAL_4")}
    if converter == "B":
        roles = {"A": roles["B"], "B": roles["A"]}
    skeleton = universe.parse_profiled_skeleton({"universe_version": 1, "roles": roles})
    stabilizer = [transform.value for transform in universe.D4Transform
                  if universe.canonical_profiled_skeleton_json(
                      universe.transform_profiled_skeleton(skeleton, transform))
                  == universe.canonical_profiled_skeleton_json(skeleton)]
    return {
        "skeleton": {
            "canonical_profiled_skeleton_json": universe.canonical_profiled_skeleton_json(skeleton),
            "typed_skeleton_hash": universe.profiled_skeleton_hash(skeleton),
            "role_neutral_skeleton_hash": universe.role_neutral_profiled_skeleton_hash(skeleton),
            "role_neutral_semantic_hash": universe.role_neutral_semantic_hash(skeleton.semantic_signature),
            "exact_stabilizer": stabilizer,
        },
        "contact": {name: {"eligible_representative_count": supply if name == "CONTACT" else 0}
                    for name in ("CONTACT", "SEPARATED")},
        "eligible_supply_by_count_pair_and_contact": [
            {"initial_counts": {"A": a, "B": b}, "contact_class": "CONTACT",
             "representative_count": supply, "weighted_count": supply} for a, b in pairs
        ],
    }


def previous_manifest(definitions=None, identity_change=False):
    definitions = pair(wire("ELIMINATE", "ELIMINATE")) if definitions is None else definitions
    identities = selection._definition_identities(definitions)
    if identity_change:
        identities[0]["exact_hash"] = "0" * 64
    payload = {
        "protocol_id": "plan0016-exploratory-pilot-v1",
        "selection": {"selected": [{"carrier_id": "prior-synthetic-carrier",
                                      "definitions": definitions, "definition_identities": identities}]},
    }
    return canonical({"payload": payload, "sha256": hashlib.sha256(canonical(payload)).hexdigest()})


def snapshot(carrier, eligible=True, contact="CONTACT"):
    facts = {
        "identities": {"typed_carrier_hash": compiler.typed_setup_carrier_hash_v1(carrier),
                       "typed_skeleton_hash": universe.profiled_skeleton_hash(carrier.skeleton)},
        "descriptor_groups": {"contact": {"contact_class": contact}},
        "rejection_reasons": [] if eligible else [{"code": "SYNTHETIC_STATIC_REJECTION"}],
        "eligible": eligible, "evidence_digest": "e" * 64,
    }
    return canonical(facts).decode(), "f" * 64


class CertificateTests(unittest.TestCase):
    def test_both_first_players_and_converter_role_have_exact_natural_bounds(self):
        for swapped in (False, True):
            for first in ("A", "B"):
                value = wire(first=first)
                if swapped:
                    value = role_swap(value)
                before = copy.deepcopy(value)
                certificate = selection.certify_no_draw(value)
                converter = "B" if swapped else "A"
                self.assertEqual(certificate["converter_role"], converter)
                self.assertEqual(certificate["initial_opponent_count"], 2)
                self.assertEqual(certificate["max_natural_plies"], 3 if value["first_player"] == converter else 4)
                self.assertTrue(certificate["every_legal_play_finite_decisive"])
                self.assertTrue(certificate["ply_limit_unreachable"])
                self.assertEqual(certificate["definition_hash"], hashlib.sha256(canonical(before)).hexdigest())
                self.assertEqual(value, before)

    def test_wider_certificate_envelope_is_bounded_below_eighteen(self):
        value = wire(first="B")
        value["initial_pieces"] = [{"owner": "A" if cell == 4 else "B",
                                    "piece": "a" if cell == 4 else "b",
                                    "position": list(divmod(cell, 3))} for cell in range(9)]
        result = selection.certify_no_draw(value)
        self.assertEqual((result["initial_opponent_count"], result["max_natural_plies"]), (8, 16))

    def test_malformed_and_out_of_proof_scope_wires_fail_closed(self):
        mutations = [
            lambda v: v.update(schema_version=True),
            lambda v: v.update(schema_version=3),
            lambda v: v.update(board_size=4),
            lambda v: v.update(max_plies=4),
            lambda v: v.update(max_plies=16),
            lambda v: v.update(terminal_policy={"no_legal_action": "DRAW"}),
            lambda v: v["roles"]["B"]["action"].update(kind="CONVERT"),
            lambda v: v["roles"]["B"]["action"].update(kind="PUSH"),
            lambda v: v["roles"]["B"]["action"].update(piece="a"),
            lambda v: v["roles"]["A"]["goal"].update(piece="b"),
            lambda v: v["roles"]["B"]["goal"].update(piece="b"),
            lambda v: v["roles"]["A"]["action"].update(vectors=[[0, 0]]),
            lambda v: v["roles"]["A"]["action"].update(vectors=[[1, True]]),
            lambda v: v["roles"]["A"]["action"].update(vectors=[[2, 0]]),
            lambda v: v["initial_pieces"][0].update(piece="third"),
            lambda v: v["initial_pieces"][0].update(position=[3, 0]),
            lambda v: v["initial_pieces"][0].update(position=[1, 1]),
            lambda v: v.update(initial_pieces=[p for p in v["initial_pieces"] if p["owner"] == "A"]),
            lambda v: v.update(initial_pieces=[p for p in v["initial_pieces"] if p["owner"] == "B"]),
        ]
        for index, mutate in enumerate(mutations):
            value = wire()
            mutate(value)
            with self.subTest(index=index), self.assertRaises(ValueError):
                selection.certify_no_draw(value)
        with self.assertRaises(ValueError):
            selection.certify_no_draw(type("HiddenDict", (dict,), {})(wire()))

    def test_all_legal_branches_on_excluded_ee_calibration_have_unique_winner(self):
        # These actual transitions are confined to the old E/E semantic region,
        # which the unchanged public compiler rejects for prospective members.
        excluded = shard(goals=("ELIMINATE", "ELIMINATE"))
        skeleton = universe.parse_profiled_skeleton(json.loads(
            excluded["skeleton"]["canonical_profiled_skeleton_json"]))
        with self.assertRaisesRegex(ValueError, "Plan-0013"):
            compiler.TypedSetupCarrierV1(1, skeleton,
                compiler.TypedSetupV1(1, ((1, 1),), ((1, 0), (1, 2))))
        terminal_winners, terminal_lengths = set(), set()
        for first in ("A", "B"):
            raw = wire("ELIMINATE", "ELIMINATE", first)
            certificate = selection.certify_no_draw(raw)
            definition = parse_definition(raw)
            visited = set()
            def check(state):
                if state in visited:
                    return
                visited.add(state)
                self.assertLessEqual(state.ply, certificate["max_natural_plies"])
                if state.terminal:
                    self.assertIn(state.outcome.winner.value, ("A", "B"))
                    self.assertNotEqual(state.outcome.reason, "PLY_LIMIT")
                    terminal_winners.add(state.outcome.winner.value)
                    terminal_lengths.add(state.ply)
                    return
                choices = legal_actions(definition, state)
                self.assertTrue(choices)
                for action in choices:
                    successor = apply_action(definition, state, action)
                    before = sum(p.owner.value == "B" for p in state.pieces)
                    after = sum(p.owner.value == "B" for p in successor.pieces)
                    self.assertEqual(after, before - (state.to_move.value == "A"))
                    check(successor)
            check(initial_state(definition))
            self.assertLess(len(visited), 300)
        self.assertEqual(terminal_winners, {"A", "B"})
        self.assertIn(1, terminal_lengths)  # Capturer can eliminate C immediately.
        self.assertIn(3, terminal_lengths)  # Converter's second turn exhausts N.

    def test_pure_selector_import_has_no_legacy_engine_or_gameplay_capability(self):
        completed = subprocess.run([sys.executable, "-c",
            "import sys; import scripts.plan0018_selection; "
            "assert not any(n == 'parity_forge' or n.startswith('parity_forge.') for n in sys.modules)"],
            capture_output=True, text=True, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        source = Path(selection.__file__).read_text()
        tree = ast.parse(source)
        calls = {node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
                 for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, (ast.Name, ast.Attribute))}
        self.assertFalse({"apply_action", "legal_actions", "solve_game", "play_game", "build_static_census_report_v1"} & calls)


class SelectionTests(unittest.TestCase):
    def run_selection(self, shards, derive=None, compiled=None, rank=None, previous=None):
        previous = previous_manifest() if previous is None else previous
        report = {"skeleton_shards": copy.deepcopy(shards)}
        original = copy.deepcopy(report)
        proof = {"report": report, "report_ref": {"byte_count": len(RAW), "sha256": hashlib.sha256(RAW).hexdigest()}}
        with ExitStack() as stack:
            for name, value in (("REPORT_BYTES", len(RAW)), ("REPORT_SHA256", hashlib.sha256(RAW).hexdigest()),
                                ("PREVIOUS_MANIFEST_BYTES", len(previous)),
                                ("PREVIOUS_MANIFEST_SHA256", hashlib.sha256(previous).hexdigest()),
                                ("PREVIOUS_CARRIER_COUNT", 1)):
                stack.enter_context(mock.patch.object(selection, name, value))
            rebuild = stack.enter_context(mock.patch.object(selection.reconstruction,
                "reconstruct_static_census_report_artifact_v1", return_value=proof))
            if derive is not None:
                stack.enter_context(mock.patch.object(selection.initial, "prepare_initial_structure_skeleton_v1", return_value=object()))
                stack.enter_context(mock.patch.object(selection.initial, "derive_prepared_initial_structure_snapshot_v1",
                    side_effect=lambda token, carrier: derive(carrier)))
            if compiled is not None:
                stack.enter_context(mock.patch.object(selection, "_compile_pair", side_effect=compiled))
            if rank is not None:
                stack.enter_context(mock.patch.object(selection, "_rank", side_effect=rank))
            result = selection.select_pilot(RAW, previous)
            rebuild.assert_called_once_with(RAW)
        self.assertEqual(report, original)
        return result

    def test_both_inputs_are_pinned_before_report_reconstruction(self):
        with mock.patch.object(selection.reconstruction, "reconstruct_static_census_report_artifact_v1") as rebuild:
            with self.assertRaises(selection.SelectionError) as caught:
                selection.select_pilot(bytearray(RAW), b"")
            self.assertIsInstance(caught.exception.__cause__, TypeError)
            self.assertEqual(caught.exception.partial_selection["selected"], [])
            with self.assertRaisesRegex(selection.SelectionError, "byte count"):
                selection.select_pilot(RAW, b"")
            with mock.patch.object(selection, "REPORT_BYTES", len(RAW)):
                with self.assertRaisesRegex(selection.SelectionError, "SHA-256"):
                    selection.select_pilot(RAW, b"")
                with mock.patch.object(selection, "REPORT_SHA256", hashlib.sha256(RAW).hexdigest()):
                    with self.assertRaisesRegex(selection.SelectionError, "previous manifest byte count"):
                        selection.select_pilot(RAW, b"")
                    with mock.patch.object(selection, "PREVIOUS_MANIFEST_BYTES", 1):
                        with self.assertRaisesRegex(selection.SelectionError, "previous manifest SHA-256"):
                            selection.select_pilot(RAW, b"x")
            rebuild.assert_not_called()

    def test_prior_envelope_and_all_identity_fields_are_revalidated(self):
        with self.assertRaisesRegex(selection.SelectionError, "identities do not reconstruct"):
            self.run_selection([], previous=previous_manifest(identity_change=True))
        previous = json.loads(previous_manifest())
        previous["sha256"] = "0" * 64
        with self.assertRaisesRegex(selection.SelectionError, "envelope or payload digest"):
            self.run_selection([], previous=canonical(previous))

    def test_all_eight_ordered_goals_sixteen_slots_and_out_of_scope_accounting(self):
        rows = [shard(goals=goals, supply=0) for goals in selection.GOAL_PAIRS]
        rows += [shard(goals=("ELIMINATE", "ELIMINATE"), supply=0),
                 shard(goals=("REACH_EDGE", "REACH_EDGE"), other_action="HOP", supply=0)]
        result = self.run_selection(rows)
        self.assertEqual(len(result["slots"]), 16)
        self.assertEqual([(row["goal_pair"], row["slot"]) for row in result["slots"]],
                         [(list(goals), slot) for goals in selection.GOAL_PAIRS for slot in range(2)])
        self.assertEqual(result["coverage"]["slot_dispositions"], {"STATIC_ZERO": 16})
        self.assertEqual(result["coverage"]["in_scope_semantic_class_count"], 8)
        self.assertEqual(result["coverage"]["out_of_scope_semantic_class_count"], 2)
        self.assertEqual(result["attempts"], [])
        self.assertEqual(result["selected"], [])

    def test_rank_domains_ties_round_robin_and_all_resource_pairs(self):
        rows = [shard(profile=profile, pairs=((2, 3), (1, 2)))
                for profile in ("ORTHOGONAL_4", "KING_8")]
        result = self.run_selection(rows, derive=lambda c: snapshot(c, False),
            rank=lambda kind, value: ("0" * 64, canonical(value)))
        self.assertEqual(len(result["attempts"]), 128)
        for slot in [row for row in result["slots"] if row["skeleton_ranking"]]:
            ranking = slot["skeleton_ranking"]
            self.assertEqual([r["canonical_rank_json"] for r in ranking], sorted(r["canonical_rank_json"] for r in ranking))
            attempts = [row for row in result["attempts"] if row["slot"] == slot["slot"]]
            for t, row in enumerate(attempts):
                self.assertEqual(row["skeleton_hash"], ranking[t % 2]["skeleton_hash"])
                self.assertEqual(row["skeleton_visit"], t // 2)
                self.assertEqual(row["initial_counts"], [[1, 2], [2, 3]][(t // 2) % 2])
                self.assertEqual(row["cell_order"], list(range(9)))
        value = {"goal_pair": ["REACH_EDGE", "ELIMINATE"], "slot": 0}
        for kind in ("skeleton", "cell"):
            self.assertEqual(selection._rank(kind, value), (hashlib.sha256(
                ("parity-forge:plan0018:pilot:" + kind + ":v1\0").encode() + canonical(value)).hexdigest(), canonical(value)))

    def test_static_and_contact_rejections_never_compile_or_certify(self):
        for eligible, contact, reason in ((False, "CONTACT", "STATIC_REJECTED"),
                                         (True, "SEPARATED", "CONTACT_MISMATCH")):
            compiled = mock.Mock(side_effect=AssertionError("must not compile"))
            result = self.run_selection([shard()], derive=lambda c: snapshot(c, eligible, contact), compiled=compiled)
            self.assertEqual({row["disposition"] for row in result["attempts"]}, {reason})
            self.assertEqual(len(result["attempts"]), 128)
            compiled.assert_not_called()

    def test_previous_exact_d4_and_alpha_role_duplicates_consume_all_attempts(self):
        base = pair()
        transformed = pair(json.loads(canonical_json(transform_definition(parse_definition(base[0]), "R90"))))
        renamed = [role_swap(value) for value in base]
        for value in renamed:
            fields = [role[key] for role in value["roles"].values() for key in ("action", "goal")] + value["initial_pieces"]
            for field in fields:
                field["piece"] = {"a": "alpha", "b": "beta"}[field["piece"]]
        renamed.sort(key=lambda value: value["first_player"])
        for definitions, expected in ((base, set(selection.IDENTITY_FIELDS)),
                                      (transformed, {"d4_hash", "role_neutral_hash"}),
                                      (renamed, {"role_neutral_hash"})):
            with self.subTest(expected=expected):
                result = self.run_selection([shard()], derive=snapshot,
                    compiled=lambda c: copy.deepcopy(definitions), previous=previous_manifest(base))
                self.assertEqual(result["selected"], [])
                self.assertEqual(len(result["attempts"]), 128)
                for row in result["attempts"]:
                    self.assertEqual(row["disposition"], "DUPLICATE_PREVIOUS_MANIFEST")
                    self.assertEqual(set(row["duplicate_relations"]["previous_manifest"]), expected)

    def test_within_run_duplicates_and_class_representation_are_retained(self):
        result = self.run_selection([shard()], derive=snapshot, compiled=lambda c: pair())
        self.assertEqual(len(result["selected"]), 1)
        self.assertEqual(len(result["attempts"]), 65)
        self.assertEqual(result["attempts"][0]["disposition"], "ACCEPTED")
        self.assertEqual({r["disposition"] for r in result["attempts"][1:]}, {"DUPLICATE_ACCEPTED_CARRIER"})
        row = result["coverage"]["classes"][0]
        self.assertEqual((row["disposition"], row["assigned_slot_count"], row["represented_carrier_count"], row["attempt_count"]),
                         ("REPRESENTED", 2, 1, 65))
        self.assertEqual([c["first_player"] for c in result["selected"][0]["no_draw_certificates"]], ["A", "B"])

    def test_converter_b_uses_mechanism_order_without_relabeling_source(self):
        values = pair(role_swap(wire()))
        result = self.run_selection([shard(converter="B", pairs=((2, 1),))],
            derive=snapshot, compiled=lambda c: copy.deepcopy(values))
        row = result["selected"][0]
        self.assertEqual((row["converter_role"], row["opponent_role"]), ("B", "A"))
        self.assertEqual(row["goal_pair"], ["REACH_EDGE", "ELIMINATE"])
        self.assertEqual(row["definitions"], values)
        self.assertEqual([c["max_natural_plies"] for c in row["no_draw_certificates"]], [4, 3])

    def test_real_public_static_kernel_and_compiler_path_without_gameplay(self):
        result = self.run_selection([shard(goals=("REACH_EDGE", "REACH_EDGE"), pairs=((1, 2), (2, 2)))])
        self.assertGreater(len(result["selected"]), 0)
        for row in result["selected"]:
            self.assertTrue(row["static_facts"]["eligible"])
            for value, certificate in zip(row["definitions"], row["no_draw_certificates"]):
                self.assertEqual(certificate, selection.certify_no_draw(value))
                self.assertLessEqual(certificate["max_natural_plies"], 6)
                self.assertEqual(canonical_json(parse_definition(value)).encode(), canonical(value))
            source = result["attempts"][next(i for i, attempt in enumerate(result["attempts"]) if attempt["carrier_id"] == row["carrier_id"])]
            setup = compiler.TypedSetupV1(1, tuple(map(tuple, source["source_positions"]["A"])), tuple(map(tuple, source["source_positions"]["B"])))
            images = [compiler.transform_typed_setup_v1(setup, universe.D4Transform(t)) for t in source["exact_stabilizer"]]
            self.assertEqual(source["canonical_setup"], min(images, key=compiler.canonical_typed_setup_json_v1).to_dict())

    def test_unexpected_static_or_certificate_failure_stops_selection(self):
        with self.assertRaisesRegex(RuntimeError, "synthetic failure"):
            self.run_selection([shard()], derive=lambda c: (_ for _ in ()).throw(RuntimeError("synthetic failure")))
        wrong = pair()
        wrong[0]["max_plies"] = 4
        with self.assertRaisesRegex(selection.SelectionError, "max_plies 18"):
            self.run_selection([shard()], derive=snapshot, compiled=lambda c: wrong)

    def test_second_slot_static_failure_preserves_accepted_and_rejected_prefix(self):
        calls = []
        def derive(carrier):
            calls.append(carrier)
            if len(calls) == 3:
                raise RuntimeError("failure after accepted and rejected attempts")
            return snapshot(carrier, eligible=len(calls) == 1)
        with self.assertRaisesRegex(selection.SelectionError, "after accepted and rejected") as caught:
            self.run_selection([shard()], derive=derive, compiled=lambda c: pair())
        partial = caught.exception.partial_selection
        self.assertFalse(partial["completed"])
        self.assertEqual(len(calls), 3)
        self.assertEqual(len(partial["selected"]), 1)
        self.assertEqual(partial["selected"][0]["definitions"], pair())
        self.assertEqual([r["disposition"] for r in partial["attempts"]], ["ACCEPTED", "STATIC_REJECTED"])
        self.assertEqual((partial["current_attempt"]["slot"], partial["current_attempt"]["attempt"]), (1, 1))
        self.assertIn("carrier_id", partial["current_attempt"])
        self.assertIn("canonical_setup", partial["current_attempt"])
        self.assertNotIn("static_facts", partial["attempts"][0])
        self.assertEqual(json.loads(canonical(partial)), partial)

    def test_second_slot_certificate_failure_retains_both_observed_definitions(self):
        calls = []
        def compiled(carrier):
            values = pair()
            calls.append(carrier)
            if len(calls) == 2:
                values[1]["max_plies"] = 4
            return values
        with self.assertRaisesRegex(selection.SelectionError, "max_plies 18") as caught:
            self.run_selection([shard()], derive=snapshot, compiled=compiled)
        partial = caught.exception.partial_selection
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(partial["selected"]), 1)
        current = partial["current_attempt"]
        self.assertEqual((current["disposition"], current["failed_during"]), ("FAILED", "CERTIFYING"))
        self.assertEqual([value["max_plies"] for value in current["definitions"]], [18, 4])
        self.assertEqual(len(current["definition_identities"]), 2)
        self.assertEqual(len(current["no_draw_certificates"]), 1)

    def test_later_compile_failure_retains_first_observed_wire_without_retry(self):
        calls = []
        def compiled(carrier):
            calls.append(carrier)
            yield pair()[0]
            if len(calls) == 2:
                raise RuntimeError("second wire compilation failed")
            yield pair()[1]
        with self.assertRaisesRegex(selection.SelectionError, "second wire") as caught:
            self.run_selection([shard()], derive=snapshot, compiled=compiled)
        partial = caught.exception.partial_selection
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(partial["selected"]), 1)
        self.assertEqual(partial["current_attempt"]["definitions"], [pair()[0]])


if __name__ == "__main__":
    unittest.main()
