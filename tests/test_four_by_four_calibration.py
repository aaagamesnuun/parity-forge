import copy
import json
import os
import subprocess
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

import parity_forge.four_by_four_calibration as calibration
from parity_forge.dsl import Player, parse_definition
from parity_forge.symmetry import canonicalize_d4, mechanical_json
from parity_forge.four_by_four_calibration import (
    FOUR_BY_FOUR_A_FIRST_STATE_BOUND,
    FOUR_BY_FOUR_B_FIRST_STATE_BOUND,
    FOUR_BY_FOUR_CASE_COUNT,
    FOUR_BY_FOUR_CLOSED_HISTORY_PROJECTION_ROOT,
    FOUR_BY_FOUR_ELIGIBLE_POOL_ROOT,
    FOUR_BY_FOUR_FIXED_CORPUS_STATE_BOUND,
    FOUR_BY_FOUR_FRESH_GATE_VALID_D4_COUNT,
    FOUR_BY_FOUR_GATE_VALID_D4_COUNT,
    FOUR_BY_FOUR_PLAN0010_MANIFEST_PATH,
    FOUR_BY_FOUR_RAW_D4_ORBIT_COUNT,
    FOUR_BY_FOUR_RAW_DEFINITION_COUNT,
    FOUR_BY_FOUR_SELECTION_FINGERPRINT,
    build_four_by_four_calibration_manifest,
    build_four_by_four_closed_history_projection,
    build_four_by_four_planning_snapshot,
    build_four_by_four_state_bound_proof,
    four_by_four_calibration_stratum,
    four_by_four_state_proof,
    four_by_four_state_upper_bound,
    validate_four_by_four_calibration_definition,
    validate_four_by_four_calibration_manifest,
    validate_four_by_four_closed_history_projection,
    validate_four_by_four_planning_snapshot,
    validate_four_by_four_searched_states,
    validate_four_by_four_state_bound_proof,
)


REPOSITORY = Path(__file__).resolve().parents[1]


def _provenance():
    plan_path = (
        "docs/plans/active/0011-four-by-four-evaluator-transfer-calibration.md"
    )
    return {
        "freezer_git_commit": "0" * 40,
        "freezer_git_dirty": False,
        "created_at": "2026-08-31T00:00:00Z",
        "protocol_id": calibration.FOUR_BY_FOUR_CALIBRATION_MANIFEST_PROTOCOL_ID,
        "protocol_plan": {
            "path": plan_path,
            "sha256": "1" * 64,
            "git_blob_sha": "2" * 40,
        },
        "protocol_fingerprints": {plan_path: "1" * 64},
        "executable_fingerprints": {
            path: "3" * 64
            for path in calibration.FOUR_BY_FOUR_MANIFEST_EXECUTABLE_FINGERPRINT_PATHS
        },
        "closed_history": {
            "projection_root": calibration.FOUR_BY_FOUR_CLOSED_HISTORY_PROJECTION_ROOT,
            "ledger_path": calibration.FOUR_BY_FOUR_LEDGER_PATH,
            "ledger_sha256": calibration.FOUR_BY_FOUR_LEDGER_SHA256,
            "ledger_bytes": calibration.FOUR_BY_FOUR_LEDGER_BYTES,
            "ledger_bundle_root": calibration.FOUR_BY_FOUR_LEDGER_BUNDLE_ROOT,
            "plan0010_manifest_path": calibration.FOUR_BY_FOUR_PLAN0010_MANIFEST_PATH,
            "plan0010_manifest_sha256": calibration.FOUR_BY_FOUR_PLAN0010_MANIFEST_SHA256,
            "plan0010_manifest_bytes": calibration.FOUR_BY_FOUR_PLAN0010_MANIFEST_BYTES,
        },
        "selection_inputs": "authenticated-definition-projections-only",
        "independent_review": "PASSED",
    }


class FourByFourCalibrationProductionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ledger_path = REPOSITORY / calibration.FOUR_BY_FOUR_LEDGER_PATH
        cls.ledger_bytes = ledger_path.read_bytes()
        ledger = json.loads(cls.ledger_bytes)
        cls.historical_bytes = {
            path: (REPOSITORY / path).read_bytes()
            for path in ledger["historical_artifact_paths"]
        }
        cls.plan0010_bytes = (
            REPOSITORY / calibration.FOUR_BY_FOUR_PLAN0010_MANIFEST_PATH
        ).read_bytes()
        cls.history = build_four_by_four_closed_history_projection(
            cls.ledger_bytes, cls.historical_bytes, cls.plan0010_bytes
        )
        cls.snapshot = build_four_by_four_planning_snapshot(cls.history)
        cls.manifest = build_four_by_four_calibration_manifest(
            cls.history, _provenance()
        )

    def test_closed_history_replays_all_pinned_bytes_and_extends_plan0010(self):
        self.assertEqual(
            self.history["projection_root"],
            FOUR_BY_FOUR_CLOSED_HISTORY_PROJECTION_ROOT,
        )
        self.assertEqual(self.history["source_count"], 22)
        self.assertEqual(self.history["definition_occurrence_count"], 2243)
        self.assertEqual(self.history["unique_definition_count"], 1172)
        self.assertEqual(self.history["unique_d4_count"], 1168)
        self.assertEqual(self.history["max8_definition_occurrence_count"], 35)
        self.assertEqual(self.history["max8_unique_d4_count"], 31)
        self.assertEqual(
            self.history["plan0010_manifest"]["definition_projection_root"],
            "037718c74144bf19c55d354ae7e377306e0553882c786766d6fa4751c5cc7463",
        )
        self.assertEqual(
            validate_four_by_four_closed_history_projection(
                self.history,
                self.ledger_bytes,
                self.historical_bytes,
                self.plan0010_bytes,
            ),
            tuple(self.history["max8_unique_d4_hashes"]),
        )
        plan0010_source = next(
            source
            for source in self.history["sources"]
            if source["artifact"]["path"] == FOUR_BY_FOUR_PLAN0010_MANIFEST_PATH
        )
        self.assertEqual(plan0010_source["definition_occurrence_count"], 128)
        self.assertEqual(plan0010_source["max8_unique_d4_count"], 0)

    def test_closed_history_rejects_open_or_changed_source_capabilities(self):
        missing = dict(self.historical_bytes)
        missing.pop(next(iter(missing)))
        with self.assertRaisesRegex(ValueError, "21-path graph"):
            build_four_by_four_closed_history_projection(
                self.ledger_bytes, missing, self.plan0010_bytes
            )

        extra = dict(self.historical_bytes)
        extra["experiments/runs/unreviewed/run.json"] = b"{}"
        with self.assertRaisesRegex(ValueError, "21-path graph"):
            build_four_by_four_closed_history_projection(
                self.ledger_bytes, extra, self.plan0010_bytes
            )

        wrong_type = dict(self.historical_bytes)
        path = next(iter(wrong_type))
        wrong_type[path] = bytearray(wrong_type[path])
        with self.assertRaisesRegex(TypeError, "immutable bytes"):
            build_four_by_four_closed_history_projection(
                self.ledger_bytes, wrong_type, self.plan0010_bytes
            )

        changed = dict(self.historical_bytes)
        path = next(iter(changed))
        changed[path] = changed[path] + b" "
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            build_four_by_four_closed_history_projection(
                self.ledger_bytes, changed, self.plan0010_bytes
            )

        with self.assertRaisesRegex(ValueError, "byte length"):
            build_four_by_four_closed_history_projection(
                self.ledger_bytes + b" ",
                self.historical_bytes,
                self.plan0010_bytes,
            )
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            build_four_by_four_closed_history_projection(
                self.ledger_bytes,
                self.historical_bytes,
                self.plan0010_bytes[:-1] + b" ",
            )

    def test_closed_history_rejects_inner_self_resigning(self):
        altered = copy.deepcopy(self.history)
        altered["plan0010_manifest"]["definition_projection_root"] = "f" * 64
        unsigned = dict(altered)
        unsigned.pop("projection_root")
        altered["projection_root"] = calibration._domain_digest(
            calibration._CLOSED_HISTORY_PROJECTION_DOMAIN, unsigned
        )
        with self.assertRaisesRegex(ValueError, "frozen root"):
            validate_four_by_four_closed_history_projection(altered)

    def test_planning_census_and_every_stratum_pool_are_frozen(self):
        census = self.snapshot["census"]
        self.assertEqual(census["raw_definition_count"], FOUR_BY_FOUR_RAW_DEFINITION_COUNT)
        self.assertEqual(census["raw_d4_orbit_count"], FOUR_BY_FOUR_RAW_D4_ORBIT_COUNT)
        self.assertEqual(census["gate_valid_d4_orbit_count"], FOUR_BY_FOUR_GATE_VALID_D4_COUNT)
        self.assertEqual(census["native_historical_d4_count"], 22)
        self.assertEqual(census["historical_gate_valid_exclusion_count"], 14)
        self.assertEqual(census["historical_gate_invalid_intersection_count"], 8)
        self.assertEqual(census["fresh_gate_valid_d4_orbit_count"], FOUR_BY_FOUR_FRESH_GATE_VALID_D4_COUNT)
        self.assertEqual(census["stratum_count"], 32)
        self.assertEqual(census["minimum_eligible_d4_orbits_per_stratum"], 35)
        self.assertEqual(census["maximum_eligible_d4_orbits_per_stratum"], 61)
        self.assertEqual(census["selected_case_count"], FOUR_BY_FOUR_CASE_COUNT)
        self.assertEqual(self.snapshot["eligible_pool_root"], FOUR_BY_FOUR_ELIGIBLE_POOL_ROOT)
        self.assertEqual(self.snapshot["selection_fingerprint"], FOUR_BY_FOUR_SELECTION_FINGERPRINT)
        self.assertEqual(
            {pool["stratum_id"]: pool["eligible_count"] for pool in self.snapshot["eligible_pools"]},
            calibration._EXPECTED_STRATUM_COUNTS,
        )

    def test_history_exclusions_reconstruct_carriers_and_overlap(self):
        exclusions = self.snapshot["history_exclusions"]
        expected_hashes = [
            "0622380440a10e75d348a063d1113211a74d71e06b9e717b3a7758950562c0cd",
            "16ca19629df380a57422e1d2802502dd2aaf313c2acdd698014866e323162302",
            "22246ae1186bbd4faa32b9a47d942f636f2bbce8cdd8bc321ff51dcd3124696e",
            "3f1a52410307ecd7a98031b7018d4692276c5deccc28727efb914526a33eaec0",
            "573eae659f92e05c4f60d543f5eba50dee9d47ab25d7161b1ba63f504ae40134",
            "57c91599d5b60e9c86a172c0845a821e3b79c7deaa163b7ffb790b87a688b5da",
            "62a1fda392a68a3a447b4fdcc1cca8606acecab6d979113ee33f6d59e928eddf",
            "67fc34d05b4fedd9a90efeeade31124b5f0927a5f59a440060f907a0fd3d8627",
            "7d3179ddc75a3d8a960fb9786f444789db14ecb4410dfb1b09484f0829f3bce0",
            "8a4d7798cb89d64abe5329f938ead3ffe16eedc7a78312169a7c6b94eca1bd0e",
            "b59737d520b8f004d4d0084bbbe7c47a6f638f975731d979af241bcd610be5de",
            "b726fd2798228fbb2f35c5cc2c6799cd298621eeea68ef57f99ae1c66ba01b19",
            "e348566a35408215ab425cc6fea78d28c33d4de18f8ec3faf0a36b6bc9139e03",
            "ed27fa76708968a788e9b7de204c036885fa67940ab28cb99de8b93018756e7f",
        ]
        self.assertEqual(exclusions["gate_valid_exclusion_d4_hashes"], expected_hashes)
        self.assertEqual(exclusions["gate_valid_source_occurrence_count"], 15)
        self.assertEqual(exclusions["gate_valid_overlap_count"], 1)
        self.assertEqual(exclusions["gate_valid_carrier_count"], 3)
        self.assertEqual(
            {item["path"]: item["gate_valid_exclusion_count"] for item in exclusions["gate_valid_carriers"]},
            calibration._EXPECTED_GATE_VALID_HISTORY_CARRIERS,
        )
        overlap = expected_hashes[1]
        carriers = [
            item["path"]
            for item in exclusions["gate_valid_carriers"]
            if overlap in item["gate_valid_exclusion_d4_hashes"]
        ]
        self.assertEqual(
            carriers,
            [
                "experiments/runs/20260830T154155824053Z-batch-g20260831/run.json",
                "experiments/runs/20260830T154309225370Z-batch-g20260831/run.json",
            ],
        )

    def test_selected_cases_are_canonical_unique_fresh_and_state_bounded(self):
        cases = self.snapshot["cases"]
        historical = set(self.history["unique_d4_hashes"])
        self.assertEqual(len(cases), FOUR_BY_FOUR_CASE_COUNT)
        self.assertEqual(len({case["definition_hash"] for case in cases}), 32)
        self.assertEqual(len({case["d4_canonical_hash"] for case in cases}), 32)
        self.assertEqual([case["selection_rank"] for case in cases], [1] * 32)
        for case in cases:
            definition = parse_definition(case["definition"])
            validate_four_by_four_calibration_definition(definition)
            self.assertEqual(
                mechanical_json(definition), canonicalize_d4(definition).mechanical_json
            )
            self.assertNotIn(case["d4_canonical_hash"], historical)
            self.assertEqual(case["state_bound"], four_by_four_state_upper_bound(definition))
            self.assertEqual(
                case["case_fingerprint"], calibration._case_fingerprint(case)
            )
        self.assertEqual(
            {case["definition"]["first_player"] for case in cases}, {"A", "B"}
        )

    def test_state_bound_proof_is_public_exact_and_typed(self):
        proof = build_four_by_four_state_bound_proof()
        self.assertEqual(
            proof["first_player_proofs"]["A"]["state_bound"],
            FOUR_BY_FOUR_A_FIRST_STATE_BOUND,
        )
        self.assertEqual(
            proof["first_player_proofs"]["B"]["state_bound"],
            FOUR_BY_FOUR_B_FIRST_STATE_BOUND,
        )
        self.assertEqual(
            proof["fixed_corpus_state_bound"], FOUR_BY_FOUR_FIXED_CORPUS_STATE_BOUND
        )
        for case in (self.snapshot["cases"][0], self.snapshot["cases"][16]):
            definition = parse_definition(case["definition"])
            case_proof = four_by_four_state_proof(definition)
            self.assertEqual(case_proof["state_bound"], case["state_bound"])
            self.assertGreater(case_proof["cap_margin"], 0)
            self.assertEqual(
                validate_four_by_four_searched_states(case["state_bound"], definition),
                case["state_bound"],
            )
            with self.assertRaises(ValueError):
                validate_four_by_four_searched_states(True, definition)
            with self.assertRaises(ValueError):
                validate_four_by_four_searched_states(case["state_bound"] + 1, definition)

        altered = copy.deepcopy(proof)
        altered["first_player_proofs"]["A"]["state_bound"] = True
        with self.assertRaises(ValueError):
            validate_four_by_four_state_bound_proof(altered)
        altered = copy.deepcopy(proof)
        altered["ply_layers"][0] = False
        with self.assertRaises(ValueError):
            validate_four_by_four_state_bound_proof(altered)
        altered = copy.deepcopy(proof)
        altered["first_player_proofs"]["A"]["a_seed_counts"][1] = True
        with self.assertRaises(ValueError):
            validate_four_by_four_state_bound_proof(altered)

    def test_stratum_and_family_validation_reject_non_native_mechanics(self):
        definition = parse_definition(self.snapshot["cases"][0]["definition"])
        self.assertEqual(four_by_four_calibration_stratum(definition), self.snapshot["cases"][0]["stratum"])
        altered = definition.to_dict()
        altered["roles"]["B"]["action"]["vectors"][0] = [2, 0]
        with self.assertRaises(ValueError):
            validate_four_by_four_calibration_definition(altered)
        with self.assertRaisesRegex(ValueError, "strict DSL parser"):
            validate_four_by_four_calibration_definition(
                replace(definition, first_player="A")
            )
        with self.assertRaisesRegex(ValueError, "strict DSL parser"):
            validate_four_by_four_calibration_definition(
                replace(definition, name="")
            )

    def test_snapshot_is_deterministic_detached_and_rejects_tampering(self):
        validate_four_by_four_planning_snapshot(self.snapshot, self.history)
        round_trip = json.loads(json.dumps(self.snapshot, sort_keys=True))
        validate_four_by_four_planning_snapshot(round_trip, self.history)
        detached = build_four_by_four_planning_snapshot(self.history)
        detached["cases"][0]["selection_rank"] = 999
        rebuilt = build_four_by_four_planning_snapshot(self.history)
        self.assertEqual(rebuilt["cases"][0]["selection_rank"], 1)

        mutations = (
            lambda value: value["census"].update({"raw_definition_count": True}),
            lambda value: value["eligible_pools"][0].update({"eligible_count": 1}),
            lambda value: value["cases"][0].update({"selection_score": "f" * 64}),
            lambda value: value["cases"][0]["definition"].update({"name": "changed"}),
            lambda value: value.update({"winner": "A"}),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                altered = copy.deepcopy(self.snapshot)
                mutation(altered)
                with self.assertRaises(ValueError):
                    validate_four_by_four_planning_snapshot(altered, self.history)

    def test_manifest_reconstructs_and_rejects_metadata_or_case_poison(self):
        cases = validate_four_by_four_calibration_manifest(
            self.manifest, self.history
        )
        self.assertEqual(len(cases), 32)
        self.assertFalse(
            self.manifest["selection_protocol"][
                "case_membership_outcome_fields_consulted"
            ]
        )
        self.assertFalse(
            self.manifest["selection_protocol"]["selected_outcomes_computed"]
        )
        second = build_four_by_four_calibration_manifest(
            self.history, _provenance()
        )
        self.assertEqual(self.manifest, second)

        mutations = (
            lambda value: value.update({"winner": "A"}),
            lambda value: value.update({"manifest_version": True}),
            lambda value: value["cases"][0].update({"result": "A_WIN"}),
            lambda value: value["provenance"].update({"outcome": "DRAW"}),
            lambda value: value["provenance"]["closed_history"].update(
                {"ledger_bytes": True}
            ),
            lambda value: value["provenance"]["executable_fingerprints"].pop(
                calibration.FOUR_BY_FOUR_MANIFEST_EXECUTABLE_FINGERPRINT_PATHS[0]
            ),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                altered = copy.deepcopy(self.manifest)
                mutation(altered)
                with self.assertRaises(ValueError):
                    validate_four_by_four_calibration_manifest(
                        altered, self.history
                    )

    def test_manifest_build_fails_if_a_reviewed_root_is_missing_or_wrong(self):
        with mock.patch.object(
            calibration, "FOUR_BY_FOUR_ELIGIBLE_POOL_ROOT", ""
        ), self.assertRaisesRegex(ValueError, "disabled until"):
            build_four_by_four_calibration_manifest(self.history, _provenance())
        with mock.patch.object(
            calibration, "FOUR_BY_FOUR_ELIGIBLE_POOL_ROOT", "f" * 64
        ), self.assertRaisesRegex(ValueError, "frozen value"):
            build_four_by_four_calibration_manifest(self.history, _provenance())

    def test_pure_module_import_does_not_load_solver_play_or_agents(self):
        script = """
import json, sys
import parity_forge.four_by_four_calibration
print(json.dumps(sorted(name for name in (
    'parity_forge.solver', 'parity_forge.play', 'parity_forge.agents'
) if name in sys.modules)))
"""
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(REPOSITORY / "src")
        output = subprocess.check_output(
            [sys.executable, "-c", script],
            cwd=REPOSITORY,
            env=environment,
            text=True,
        )
        self.assertEqual(json.loads(output), [])


if __name__ == "__main__":
    unittest.main()
