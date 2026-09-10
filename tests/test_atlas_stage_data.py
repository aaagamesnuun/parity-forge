import ast
import copy
import hashlib
import json
import unittest
from pathlib import Path

import parity_forge.atlas_stage_data as stage_data
from parity_forge.atlas_protocol import ATLAS_D4_TRANSFORMS_V1
from parity_forge.dsl import definition_hash, parse_definition
from parity_forge.symmetry import d4_canonical_hash, transform_definition

from tests.support import crossing_definition


def _sha(label):
    return hashlib.sha256(label.encode("ascii")).hexdigest()


def _synthetic_manifest_inputs():
    raw_a = crossing_definition()
    raw_a["name"] = "Synthetic A-first"
    raw_a["max_plies"] = 5
    raw_b = copy.deepcopy(raw_a)
    raw_b["name"] = "Synthetic B-first"
    raw_b["first_player"] = "B"
    definitions = [parse_definition(raw_a), parse_definition(raw_b)]
    pair_identity = _sha("development-pair")
    members = {}
    exact = []
    orientations = []
    for definition_index, (label, definition) in enumerate(
        zip(("A_FIRST", "B_FIRST"), definitions)
    ):
        exact_slot_id = _sha("exact-{}".format(definition_index))
        representative_hash = definition_hash(definition)
        canonical_hash = d4_canonical_hash(definition)
        hashes = [
            definition_hash(transform_definition(definition, transform))
            for transform in ATLAS_D4_TRANSFORMS_V1
        ]
        members[label] = {
            "first_player": label[0],
            "representative_definition_hash": representative_hash,
            "representative_definition": definition.to_dict(),
            "candidate_poison_not_for_output": _sha("poison-{}".format(label)),
        }
        exact.append(
            {
                "definition_index": definition_index,
                "pair_index": 0,
                "member_index": definition_index,
                "member": label,
                "first_player": label[0],
                "paired_mechanical_d4_identity": pair_identity,
                "representative_definition_hash": representative_hash,
                "d4_canonical_hash": canonical_hash,
                "slot_id": exact_slot_id,
            }
        )
        for transform_index, (transform, transformed_hash) in enumerate(
            zip(ATLAS_D4_TRANSFORMS_V1, hashes)
        ):
            orientations.append(
                {
                    "orientation_slot_index": 8 * definition_index
                    + transform_index,
                    "exact_slot_id": exact_slot_id,
                    "definition_index": definition_index,
                    "pair_index": 0,
                    "member": label,
                    "transform_index": transform_index,
                    "transform": transform,
                    "transformed_definition_hash": transformed_hash,
                    "d4_canonical_hash": canonical_hash,
                    "first_duplicate_transform_index": hashes.index(
                        transformed_hash
                    ),
                    "slot_id": _sha(
                        "orientation-{}-{}".format(
                            definition_index, transform_index
                        )
                    ),
                }
            )
    pairs = [
        {
            "paired_mechanical_d4_identity": pair_identity,
            "members": members,
            "confirmation_candidate_pairs": [
                {"candidate_id": _sha("must-not-leak")}
            ],
        }
    ]
    return pairs, exact, orientations


def _build_synthetic_manifest():
    pairs, exact, orientations = _synthetic_manifest_inputs()
    manifest = stage_data._build_manifest_from_schedules(
        pairs,
        exact,
        orientations,
        protocol_id="synthetic-protocol-v1",
        protocol_root=_sha("protocol"),
        selection_canonical_sha256=_sha("selection"),
        selection_partition_root=_sha("partition"),
    )
    return pairs, exact, orientations, manifest


class DetachedManifestTests(unittest.TestCase):
    def test_synthetic_manifest_binds_bodies_to_all_exact_and_d4_slots(self):
        pairs, exact, orientations, manifest = _build_synthetic_manifest()
        validated = stage_data._validate_manifest_from_schedules(
            manifest,
            exact,
            orientations,
            protocol_id="synthetic-protocol-v1",
            protocol_root=_sha("protocol"),
            selection_canonical_sha256=_sha("selection"),
            selection_partition_root=_sha("partition"),
            fixed_counts=False,
        )
        self.assertEqual(validated, manifest)
        self.assertEqual(len(manifest["definitions"]), 2)
        self.assertEqual(
            [len(entry["orientations"]) for entry in manifest["definitions"]],
            [8, 8],
        )
        encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
        self.assertNotIn(_sha("must-not-leak"), encoded)
        self.assertNotIn("confirmation_candidate_pairs", encoded)
        self.assertNotIn("candidate_poison_not_for_output", encoded)
        self.assertIn(pairs[0]["paired_mechanical_d4_identity"], encoded)

    def test_manifest_is_detached_and_hash_or_coordinate_tampering_fails(self):
        pairs, exact, orientations, manifest = _build_synthetic_manifest()
        original_pairs = copy.deepcopy(pairs)
        manifest["definitions"][0]["representative_definition"]["name"] = "mutated"
        self.assertEqual(pairs, original_pairs)

        _pairs, exact, orientations, clean = _build_synthetic_manifest()
        bad_hash = copy.deepcopy(clean)
        bad_hash["definitions"][0]["orientations"][0][
            "transformed_definition_hash"
        ] = _sha("forged")
        with self.assertRaises(ValueError):
            stage_data._validate_manifest_from_schedules(
                bad_hash,
                exact,
                orientations,
                protocol_id="synthetic-protocol-v1",
                protocol_root=_sha("protocol"),
                selection_canonical_sha256=_sha("selection"),
                selection_partition_root=_sha("partition"),
                fixed_counts=False,
            )

        bad_order = copy.deepcopy(clean)
        bad_order["definitions"][0]["orientations"].reverse()
        with self.assertRaises(ValueError):
            stage_data._validate_manifest_from_schedules(
                bad_order,
                exact,
                orientations,
                protocol_id="synthetic-protocol-v1",
                protocol_root=_sha("protocol"),
                selection_canonical_sha256=_sha("selection"),
                selection_partition_root=_sha("partition"),
                fixed_counts=False,
            )

    def test_manifest_validator_rejects_extra_fields_and_non_json_values(self):
        _pairs, exact, orientations, manifest = _build_synthetic_manifest()
        manifest["unexpected"] = True
        with self.assertRaises(ValueError):
            stage_data._validate_manifest_from_schedules(
                manifest,
                exact,
                orientations,
                protocol_id="synthetic-protocol-v1",
                protocol_root=_sha("protocol"),
                selection_canonical_sha256=_sha("selection"),
                selection_partition_root=_sha("partition"),
                fixed_counts=False,
            )
        cyclic = {}
        cyclic["self"] = cyclic
        with self.assertRaises(ValueError):
            stage_data._strict_json_bytes(cyclic, "cycle")
        with self.assertRaises(TypeError):
            stage_data._strict_json_bytes({"float": 1.0}, "float")


class StatusLedgerTests(unittest.TestCase):
    def setUp(self):
        self.ids = [_sha("slot-a"), _sha("slot-b"), _sha("slot-c")]
        self.parent = _sha("parent")
        self.subset = stage_data._ordered_slot_root("EXACT", self.ids)

    def test_exact_reconciliation_keeps_raw_interrupted_and_not_run_distinct(self):
        observed = [
            {
                "slot_id": self.ids[0],
                "status": "COMPLETE",
                "record_root_or_null": _sha("raw-a"),
            }
        ]
        ledger = stage_data._reconcile_ledger(
            "EXACT",
            self.ids,
            self.parent,
            self.subset,
            None,
            observed,
            [self.ids[0], self.ids[1]],
            blocked=False,
        )
        validated = stage_data._validate_ledger(
            ledger,
            "EXACT",
            self.ids,
            self.parent,
            self.subset,
            None,
        )
        self.assertEqual(validated, ledger)
        self.assertEqual(
            [(row["status"], row["origin"]) for row in ledger["rows"]],
            [
                ("COMPLETE", "RAW_RECORD"),
                ("INCOMPLETE", "RECONCILED_STARTED"),
                ("NOT_RUN", "RECONCILED_UNOBSERVED"),
            ],
        )
        self.assertEqual(sum(ledger["status_counts"].values()), 3)

    def test_telemetry_reconciliation_separates_missing_and_nonadmissible(self):
        subset = stage_data._ordered_slot_root("TELEMETRY", self.ids)
        observed = [
            {
                "slot_id": self.ids[0],
                "status": "VALIDATED",
                "record_root_or_null": _sha("telemetry-a"),
            }
        ]
        ledger = stage_data._reconcile_ledger(
            "TELEMETRY",
            self.ids,
            self.parent,
            subset,
            None,
            observed,
            [self.ids[0]],
            blocked=False,
            admissible_value=[self.ids[0], self.ids[1]],
        )
        self.assertEqual(
            [row["status"] for row in ledger["rows"]],
            ["VALIDATED", "MISSING", "NOT_ADMISSIBLE"],
        )
        stage_data._validate_ledger(
            ledger, "TELEMETRY", self.ids, self.parent, subset, None
        )

    def test_blocked_reconciliation_closes_every_fixed_slot(self):
        ledger = stage_data._reconcile_ledger(
            "EXACT",
            self.ids,
            self.parent,
            self.subset,
            None,
            [],
            [],
            blocked=True,
        )
        self.assertEqual({row["status"] for row in ledger["rows"]}, {"BLOCKED"})
        self.assertEqual(ledger["status_counts"]["BLOCKED"], len(self.ids))

    def test_reconciliation_and_validation_fail_closed(self):
        with self.assertRaises(ValueError):
            stage_data._reconcile_ledger(
                "EXACT",
                self.ids,
                self.parent,
                self.subset,
                None,
                [
                    {
                        "slot_id": self.ids[0],
                        "status": "COMPLETE",
                        "record_root_or_null": _sha("raw"),
                    }
                ],
                [],
                blocked=False,
            )
        ledger = stage_data._reconcile_ledger(
            "EXACT",
            self.ids,
            self.parent,
            self.subset,
            None,
            [],
            [],
            blocked=False,
        )
        ledger["rows"][0]["origin"] = "RAW_RECORD"
        with self.assertRaises(ValueError):
            stage_data._validate_ledger(
                ledger,
                "EXACT",
                self.ids,
                self.parent,
                self.subset,
                None,
            )


class CompleteTraceReplayTests(unittest.TestCase):
    def setUp(self):
        raw = crossing_definition()
        raw["max_plies"] = 5
        self.definition = parse_definition(raw).to_dict()
        self.actions = [
            {"kind": "PLACE", "to": [0, 0]},
            {"kind": "MOVE", "from": [2, 1], "to": [2, 2]},
            {"kind": "PLACE", "to": [1, 0]},
            {"kind": "MOVE", "from": [2, 2], "to": [1, 2]},
            {"kind": "PLACE", "to": [2, 0]},
        ]
        self.trace = {
            "trace_version": 1,
            "definition_hash": definition_hash(parse_definition(self.definition)),
            "actions": self.actions,
            "plies": 5,
            "winner": "A",
            "terminal_reason": "GOAL",
        }

    def test_complete_trace_is_replayed_to_the_claimed_terminal(self):
        definition_before = copy.deepcopy(self.definition)
        trace_before = copy.deepcopy(self.trace)
        validated = stage_data.validate_complete_atlas_trace_v1(
            self.definition, self.trace
        )
        self.assertEqual(validated, self.trace)
        self.assertEqual(self.definition, definition_before)
        self.assertEqual(self.trace, trace_before)

    def test_nonterminal_illegal_and_false_terminal_claims_fail(self):
        nonterminal = copy.deepcopy(self.trace)
        nonterminal["actions"] = nonterminal["actions"][:1]
        nonterminal["plies"] = 1
        nonterminal["winner"] = None
        nonterminal["terminal_reason"] = "PLY_LIMIT"
        with self.assertRaises(ValueError):
            stage_data.validate_complete_atlas_trace_v1(
                self.definition, nonterminal
            )

        illegal = copy.deepcopy(self.trace)
        illegal["actions"][0]["to"] = [9, 9]
        with self.assertRaises(ValueError):
            stage_data.validate_complete_atlas_trace_v1(self.definition, illegal)

        false_winner = copy.deepcopy(self.trace)
        false_winner["winner"] = "B"
        with self.assertRaises(ValueError):
            stage_data.validate_complete_atlas_trace_v1(
                self.definition, false_winner
            )


class CapabilityBoundaryTests(unittest.TestCase):
    def test_module_does_not_import_forbidden_capabilities(self):
        path = Path(stage_data.__file__)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        forbidden = {
            "atlas",
            "atlas_history",
            "atlas_projection",
            "feasibility",
            "solver",
            "agents",
            "terminal_search",
            "agency",
            "play",
            "experiment",
            "experiments",
            "evidence",
        }
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.rsplit(".", 1)[-1] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.rsplit(".", 1)[-1])
        self.assertTrue(imported.isdisjoint(forbidden), imported.intersection(forbidden))

    def test_public_surface_is_explicit_and_contains_no_execution_function(self):
        self.assertFalse(
            any(
                token in name
                for name in stage_data.__all__
                for token in ("solve", "play", "assess", "inspect")
            )
        )
        self.assertIn(
            "join_game_slot_to_manifest_definition_v1", stage_data.__all__
        )


if __name__ == "__main__":
    unittest.main()
