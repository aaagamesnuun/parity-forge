import copy
import hashlib
import json
import unittest

from parity_forge.capture import (
    CAPTURE_MANIFEST_ID,
    CAPTURE_REPLAY_ATTESTATION_VERSION,
    CAPTURE_SOURCE_MANIFEST_ID,
    CAPTURE_SOURCE_MANIFEST_SHA256,
    CAPTURE_STATE_BOUND,
    CaptureManifestContract,
    build_capture_paired_manifest,
    build_capture_paired_result,
    build_capture_profile_evidence,
    build_capture_replay_attestation,
    build_capture_stress_result,
    build_censored_capture_profile_evidence,
    capture_replay_projection,
    capture_state_upper_bound,
    derive_capture_trace,
    evaluate_capture_cases,
    evaluate_capture_pairs,
    normalize_capture_pv,
    select_capture_stress_candidates,
    stress_capture_interactions,
    validate_capture_case_evaluation,
    validate_capture_monotonicity,
    validate_capture_paired_manifest,
    validate_capture_paired_result,
    validate_capture_profile_evidence,
    validate_capture_replay_attestation,
    validate_capture_searched_states,
    validate_capture_stress_result,
)
from parity_forge.batch import PlayGates
from parity_forge.dsl import Player, definition_hash, parse_definition
from parity_forge.landscape_evaluation import evaluate_landscape_cases
from parity_forge.symmetry import d4_canonical_hash


TINY_CONTRACT = CaptureManifestContract(
    source_case_count=2,
    pair_count=2,
    stratum_count=2,
    quota_per_stratum=1,
)


class StepClock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        self.value += 0.125
        return self.value


def _source_definition(name, column):
    return {
        "schema_version": 1,
        "name": name,
        "board_size": 3,
        "first_player": "B",
        "max_plies": 18,
        "roles": {
            "A": {
                "action": {"kind": "PLACE", "piece": "seed"},
                "goal": {
                    "kind": "CONNECT_EDGES",
                    "piece": "seed",
                    "edges": (
                        ["TOP", "BOTTOM"]
                        if column == 0
                        else ["LEFT", "RIGHT"]
                    ),
                },
            },
            "B": {
                "action": {
                    "kind": "MOVE",
                    "piece": "runner",
                    "vectors": (
                        [[-1, 0]] if column == 0 else [[-1, 0], [0, -1]]
                    ),
                },
                "goal": {
                    "kind": "REACH_EDGE",
                    "piece": "runner",
                    "edge": "TOP",
                },
            },
        },
        "initial_pieces": [
            {"owner": "B", "piece": "runner", "position": [1, column]}
        ],
    }


def _source_case(index, column):
    definition = parse_definition(_source_definition("Tiny source {}".format(index), column))
    return {
        "case_id": "tiny-source-{}".format(index),
        "stratum": {
            "first_player": "B",
            "goal_axis_relation": "ALIGNED" if index == 0 else "ORTHOGONAL",
            "runner_start_class": "EDGE_MIDPOINT",
            "max_plies": 18,
            "vector_count_band": "1_TO_3",
        },
        "vector_count": len(definition.role(Player.B).action.vectors),
        "definition_hash": definition_hash(definition),
        "d4_canonical_hash": d4_canonical_hash(definition),
        "definition": definition.to_dict(),
        "selection_rank": 1,
        "selection_score": hashlib.sha256(str(index).encode("ascii")).hexdigest(),
    }


def _tiny_manifest():
    source_cases = [_source_case(0, 0), _source_case(1, 2)]
    manifest = build_capture_paired_manifest(
        {"manifest_id": CAPTURE_SOURCE_MANIFEST_ID, "cases": source_cases},
        CAPTURE_SOURCE_MANIFEST_SHA256,
        {"fixture": "synthetic-tiny"},
        contract=TINY_CONTRACT,
    )
    return source_cases, manifest


def _baseline_case(pair):
    return {
        "case_id": pair["source_case_id"],
        "definition_hash": pair["source_definition_hash"],
        "d4_canonical_hash": pair["source_d4_canonical_hash"],
        "stratum": copy.deepcopy(pair["stratum"]),
        "vector_count": pair["vector_count"],
        "definition": copy.deepcopy(pair["source_definition"]),
    }


def _treatment_case(pair):
    return {
        "pair_id": pair["pair_id"],
        "source_case_id": pair["source_case_id"],
        "definition_hash": pair["treatment_definition_hash"],
        "d4_canonical_hash": pair["treatment_d4_canonical_hash"],
        "stratum": copy.deepcopy(pair["stratum"]),
        "vector_count": pair["vector_count"],
        "definition": copy.deepcopy(pair["treatment_definition"]),
    }


def _evaluated_tiny():
    _, manifest = _tiny_manifest()
    pairs = validate_capture_paired_manifest(manifest, contract=TINY_CONTRACT)
    baseline = evaluate_landscape_cases(
        tuple(_baseline_case(pair) for pair in pairs),
        clock=StepClock(),
    )
    treatment = evaluate_capture_cases(
        tuple(_treatment_case(pair) for pair in pairs),
        clock=StepClock(),
    )
    return manifest, pairs, baseline, treatment


def _capture_definition():
    return {
        "schema_version": 3,
        "name": "Synthetic capture trace",
        "board_size": 3,
        "first_player": "A",
        "max_plies": 18,
        "roles": {
            "A": {
                "action": {"kind": "PLACE", "piece": "seed"},
                "goal": {
                    "kind": "CONNECT_EDGES",
                    "piece": "seed",
                    "edges": ["TOP", "BOTTOM"],
                },
            },
            "B": {
                "action": {
                    "kind": "MOVE_CAPTURE",
                    "piece": "runner",
                    "vectors": [[0, -1], [0, 1]],
                },
                "goal": {
                    "kind": "REACH_EDGE",
                    "piece": "runner",
                    "edge": "LEFT",
                },
            },
        },
        "initial_pieces": [
            {"owner": "B", "piece": "runner", "position": [1, 1]}
        ],
    }


def _dual_outcome_definition():
    return {
        "schema_version": 3,
        "name": "Synthetic dual outcome",
        "board_size": 3,
        "first_player": "A",
        "max_plies": 18,
        "roles": {
            "A": {
                "action": {"kind": "PLACE", "piece": "seed"},
                "goal": {
                    "kind": "CONNECT_EDGES",
                    "piece": "seed",
                    "edges": ["LEFT", "RIGHT"],
                },
            },
            "B": {
                "action": {
                    "kind": "MOVE_CAPTURE",
                    "piece": "runner",
                    "vectors": [[-1, 0], [0, -1], [0, 1]],
                },
                "goal": {
                    "kind": "REACH_EDGE",
                    "piece": "runner",
                    "edge": "TOP",
                },
            },
        },
        "initial_pieces": [
            {"owner": "B", "piece": "runner", "position": [2, 1]}
        ],
    }


class CaptureManifestTests(unittest.TestCase):
    def test_tiny_builder_is_deterministic_outcome_free_and_exactly_paired(self):
        source_cases, first = _tiny_manifest()
        second = build_capture_paired_manifest(
            {"manifest_id": CAPTURE_SOURCE_MANIFEST_ID, "cases": source_cases},
            CAPTURE_SOURCE_MANIFEST_SHA256,
            {"fixture": "synthetic-tiny"},
            contract=TINY_CONTRACT,
        )
        pairs = validate_capture_paired_manifest(first, contract=TINY_CONTRACT)

        self.assertEqual(first, second)
        self.assertEqual(first["manifest_id"], CAPTURE_MANIFEST_ID)
        self.assertEqual(len(pairs), 2)
        self.assertNotIn('"result"', json.dumps(first, sort_keys=True))
        for pair in pairs:
            self.assertEqual(pair["source_definition"]["schema_version"], 1)
            self.assertEqual(pair["treatment_definition"]["schema_version"], 3)
            self.assertEqual(
                pair["treatment_definition"]["roles"]["B"]["action"]["kind"],
                "MOVE_CAPTURE",
            )

    def test_manifest_rejects_outcome_bearing_provenance(self):
        source_cases = [_source_case(0, 0), _source_case(1, 2)]
        with self.assertRaisesRegex(ValueError, "outcome-free"):
            build_capture_paired_manifest(
                {"manifest_id": CAPTURE_SOURCE_MANIFEST_ID, "cases": source_cases},
                CAPTURE_SOURCE_MANIFEST_SHA256,
                {"result": "B_WIN"},
                contract=TINY_CONTRACT,
            )

    def test_validator_rejects_duplicate_rank_within_a_stratum_even_with_new_fingerprint(self):
        contract = CaptureManifestContract(
            source_case_count=2,
            pair_count=2,
            stratum_count=1,
            quota_per_stratum=2,
        )
        cases = [_source_case(0, 0), _source_case(1, 2)]
        second_definition = copy.deepcopy(cases[1]["definition"])
        second_definition["roles"]["A"]["goal"]["edges"] = ["TOP", "BOTTOM"]
        parsed = parse_definition(second_definition)
        cases[1].update(
            {
                "definition": parsed.to_dict(),
                "definition_hash": definition_hash(parsed),
                "d4_canonical_hash": d4_canonical_hash(parsed),
                "stratum": copy.deepcopy(cases[0]["stratum"]),
                "selection_rank": 2,
            }
        )
        manifest = build_capture_paired_manifest(
            {"manifest_id": CAPTURE_SOURCE_MANIFEST_ID, "cases": cases},
            CAPTURE_SOURCE_MANIFEST_SHA256,
            {"fixture": "rank-census"},
            contract=contract,
        )
        tampered = copy.deepcopy(manifest)
        pair = tampered["pairs"][1]
        pair["selection_rank"] = 1
        payload = {
            key: pair[key]
            for key in (
                "pair_id",
                "source_case_id",
                "source_definition_hash",
                "source_d4_canonical_hash",
                "stratum",
                "vector_count",
                "source_definition",
                "treatment_definition_hash",
                "treatment_d4_canonical_hash",
                "treatment_definition",
                "selection_rank",
                "selection_score",
            )
        }
        canonical = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        pair["pair_fingerprint"] = hashlib.sha256(
            b"capture-v1-pair-v1\0" + canonical
        ).hexdigest()
        with self.assertRaisesRegex(ValueError, "ranks must cover"):
            validate_capture_paired_manifest(tampered, contract=contract)

    def test_structural_state_bound_and_strict_integer_validator(self):
        _, manifest = _tiny_manifest()
        treatment = manifest["pairs"][0]["treatment_definition"]
        self.assertEqual(capture_state_upper_bound(treatment), CAPTURE_STATE_BOUND)
        self.assertEqual(validate_capture_searched_states(CAPTURE_STATE_BOUND), CAPTURE_STATE_BOUND)
        for invalid in (True, 0, CAPTURE_STATE_BOUND + 1, 1.0):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    validate_capture_searched_states(invalid)


class CaptureReplayTests(unittest.TestCase):
    def test_literal_384_pinned_candidates_project_to_128_manifest_pairs(self):
        _, tiny_pairs, baseline, _ = _evaluated_tiny()
        template_pair = tiny_pairs[0]
        template_candidate = baseline["candidates"][0]
        pairs = []
        observed = []
        for index in range(128):
            case_id = "synthetic-required-{:03d}".format(index)
            game_hash = "{:064x}".format(index + 1)
            orbit_hash = "{:064x}".format(index + 1001)
            stratum = {"synthetic_stratum": index // 4, "max_plies": 18}
            pair = {
                **copy.deepcopy(template_pair),
                "pair_id": "capture-v1-pair-{:03d}".format(index + 1),
                "source_case_id": case_id,
                "source_definition_hash": game_hash,
                "source_d4_canonical_hash": orbit_hash,
                "stratum": stratum,
            }
            candidate = copy.deepcopy(template_candidate)
            candidate.update(
                {
                    "case_id": case_id,
                    "definition_hash": game_hash,
                    "d4_canonical_hash": orbit_hash,
                    "stratum": copy.deepcopy(stratum),
                }
            )
            pairs.append(pair)
            observed.append(candidate)
        extras = [
            {"case_id": "synthetic-extra-{:03d}".format(index)}
            for index in range(256)
        ]
        pinned = []
        for index, candidate in enumerate(observed):
            pinned.append(extras[index])
            pinned.append(copy.deepcopy(candidate))
        pinned.extend(extras[128:])
        self.assertEqual(len(pinned), 384)

        attestation = build_capture_replay_attestation(pairs, observed, pinned)
        self.assertEqual(len(attestation["pinned_expected"]["case_digests"]), 128)
        self.assertEqual(
            attestation["observed"]["root_sha256"],
            attestation["pinned_expected"]["root_sha256"],
        )

    def test_full_source_candidate_list_is_projected_to_manifest_order(self):
        manifest, pairs, baseline, _ = _evaluated_tiny()
        observed = baseline["candidates"]
        pinned_required = copy.deepcopy(observed)
        for candidate in pinned_required:
            candidate["exact"]["elapsed_seconds"] += 99.0
            candidate["timing"]["cheap_play_seconds"] += 99.0
        extras = [
            {"case_id": "historical-extra-before"},
            {"case_id": "historical-extra-between"},
        ]
        pinned_full = [extras[0], pinned_required[1], extras[1], pinned_required[0]]

        attestation = build_capture_replay_attestation(pairs, observed, pinned_full)
        self.assertEqual(attestation["version"], CAPTURE_REPLAY_ATTESTATION_VERSION)
        self.assertEqual(
            attestation["observed"]["root_sha256"],
            attestation["pinned_expected"]["root_sha256"],
        )
        validate_capture_replay_attestation(attestation, pairs, observed, pinned_full)

    def test_replay_digest_uses_nul_domain_and_canonical_utf8_projection(self):
        _, pairs, baseline, _ = _evaluated_tiny()
        projection = capture_replay_projection(pairs[0], baseline["candidates"][0])
        canonical = json.dumps(
            projection, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        expected = hashlib.sha256(
            b"capture-v1-replay-case-v1\0" + canonical
        ).hexdigest()
        attestation = build_capture_replay_attestation(
            pairs, baseline["candidates"], baseline["candidates"]
        )
        self.assertEqual(attestation["observed"]["case_digests"][0]["case_digest"], expected)

    def test_treatment_callback_is_not_called_before_attestation_passes(self):
        manifest, _, baseline, _ = _evaluated_tiny()
        bad_fresh = copy.deepcopy(baseline)
        bad_fresh["candidates"][0]["static"]["passes"] = not bad_fresh["candidates"][0]["static"]["passes"]
        treatment_called = []

        def treatment(_cases):
            treatment_called.append(True)
            raise AssertionError("must not be called")

        with self.assertRaisesRegex(ValueError, "differs"):
            evaluate_capture_pairs(
                manifest,
                baseline,
                baseline_evaluator=lambda _cases: bad_fresh,
                treatment_evaluator=treatment,
                contract=TINY_CONTRACT,
            )
        self.assertEqual(treatment_called, [])


class CaptureTraceTests(unittest.TestCase):
    def test_capture_is_derived_from_pre_action_occupancy(self):
        definition = _capture_definition()
        actions = [
            {"kind": "PLACE", "to": [1, 0]},
            {"kind": "MOVE_CAPTURE", "from": [1, 1], "to": [1, 0]},
        ]
        trace = derive_capture_trace(definition, actions)
        self.assertEqual(trace["capture_count"], 1)
        self.assertEqual(trace["first_capture_ply"], 2)
        self.assertEqual(trace["capture_plies"], [2])
        self.assertEqual(trace["terminal_outcome"], {"winner": "B", "reason": "GOAL"})

    def test_empty_move_capture_does_not_count_as_capture(self):
        definition = _capture_definition()
        actions = [
            {"kind": "PLACE", "to": [2, 2]},
            {"kind": "MOVE_CAPTURE", "from": [1, 1], "to": [1, 0]},
        ]
        trace = derive_capture_trace(definition, actions)
        self.assertEqual(trace["capture_count"], 0)
        self.assertIsNone(trace["first_capture_ply"])

    def test_replacement_recapture_requires_board_plus_side_repetition(self):
        definition = copy.deepcopy(_capture_definition())
        definition["roles"]["B"]["goal"]["edge"] = "TOP"
        actions = [
            {"kind": "PLACE", "to": [1, 0]},
            {"kind": "MOVE_CAPTURE", "from": [1, 1], "to": [1, 0]},
            {"kind": "PLACE", "to": [1, 1]},
            {"kind": "MOVE_CAPTURE", "from": [1, 0], "to": [1, 1]},
            {"kind": "PLACE", "to": [1, 0]},
            {"kind": "MOVE_CAPTURE", "from": [1, 1], "to": [1, 0]},
        ]
        trace = derive_capture_trace(definition, actions, require_terminal=False)
        self.assertTrue(trace["repeated_position"])
        self.assertTrue(trace["replacement_recapture"])
        self.assertTrue(trace["capture_replace_cycle"])

    def test_profile_histogram_and_censored_prefix_are_replayable(self):
        definition = _capture_definition()
        game = {
            "profile": "tiny-profile",
            "seed": 10,
            "actions": [
                {"kind": "PLACE", "to": [1, 0]},
                {"kind": "MOVE_CAPTURE", "from": [1, 1], "to": [1, 0]},
            ],
            "terminal_outcome": {"winner": "B", "reason": "GOAL"},
            "terminal_ply": 2,
        }
        complete = build_capture_profile_evidence(
            definition, "tiny-profile", [game], (10,)
        )
        self.assertEqual(complete["profile_summary"]["capture_count_histogram"], {"1": 1})
        validate_capture_profile_evidence(definition, complete, expected_seeds=(10,))

        censored = build_censored_capture_profile_evidence(
            definition,
            "tiny-profile",
            [game],
            (10, 11),
            11,
            {"visited_nodes": 5, "max_nodes": 5, "scope": "per-candidate"},
        )
        self.assertEqual(censored["completed_seed_prefix"], [10])
        self.assertEqual(censored["incomplete_seed"], 11)
        self.assertIsNone(censored["profile_summary"])
        self.assertIsNone(censored["frontier_metrics"])
        validate_capture_profile_evidence(definition, censored, expected_seeds=(10, 11))

        tampered = copy.deepcopy(complete)
        tampered["profile_summary"]["capture_count_histogram"] = {"01": 1}
        with self.assertRaises(ValueError):
            validate_capture_profile_evidence(definition, tampered, expected_seeds=(10,))

    def test_normalized_pv_matches_only_empty_treatment_moves(self):
        treatment = _capture_definition()
        baseline = copy.deepcopy(treatment)
        baseline["schema_version"] = 1
        baseline["roles"]["B"]["action"]["kind"] = "MOVE"
        baseline_actions = [
            {"kind": "PLACE", "to": [2, 2]},
            {"kind": "MOVE", "from": [1, 1], "to": [1, 0]},
        ]
        treatment_actions = [
            {"kind": "PLACE", "to": [2, 2]},
            {"kind": "MOVE_CAPTURE", "from": [1, 1], "to": [1, 0]},
        ]
        normalized = normalize_capture_pv(
            baseline, baseline_actions, treatment, treatment_actions
        )
        self.assertEqual(normalized["common_prefix_plies"], 2)
        self.assertIsNone(normalized["first_divergence_ply"])

        realized = [
            {"kind": "PLACE", "to": [1, 0]},
            {"kind": "MOVE_CAPTURE", "from": [1, 1], "to": [1, 0]},
        ]
        divergent = normalize_capture_pv(
            baseline, baseline_actions, treatment, realized
        )
        self.assertEqual(divergent["common_prefix_plies"], 0)
        self.assertEqual(divergent["first_divergence_ply"], 1)

    def test_monotonicity_uses_b_win_draw_a_win_order(self):
        baseline = {"status": "COMPLETED", "result": {"forced_result": "A_WIN", "value_for_a": 1}}
        treatment = {"status": "COMPLETED", "result": {"forced_result": "DRAW", "value_for_a": 0}}
        self.assertTrue(validate_capture_monotonicity(baseline, treatment)["monotonic"])
        with self.assertRaisesRegex(ValueError, "monotonicity violation"):
            validate_capture_monotonicity(
                {"status": "COMPLETED", "result": {"forced_result": "B_WIN", "value_for_a": -1}},
                {"status": "COMPLETED", "result": {"forced_result": "DRAW", "value_for_a": 0}},
            )


class CaptureRawTests(unittest.TestCase):
    def test_treatment_evaluation_envelope_and_reports_are_publicly_reconstructed(self):
        _, pairs, _, treatment = _evaluated_tiny()
        cases = tuple(_treatment_case(pair) for pair in pairs)
        validate_capture_case_evaluation(treatment, cases)

        tampered_configuration = copy.deepcopy(treatment)
        tampered_configuration["configuration"]["play_seeds"] = [0]
        with self.assertRaisesRegex(ValueError, "configuration mismatch"):
            validate_capture_case_evaluation(tampered_configuration, cases)

        tampered_timing = copy.deepcopy(treatment)
        tampered_timing["timing"]["total_seconds"] = 0.0
        with self.assertRaisesRegex(ValueError, "smaller than its components"):
            validate_capture_case_evaluation(tampered_timing, cases)

    def test_raw_builder_rejects_report_profile_failure_and_trace_tampering(self):
        manifest, _, baseline, treatment = _evaluated_tiny()
        mutations = []

        static = copy.deepcopy(treatment)
        static["candidates"][0]["static"]["passes"] = not static["candidates"][0]["static"]["passes"]
        mutations.append(static)

        profile = copy.deepcopy(treatment)
        profile["candidates"][0]["cheap_profiles"][0]["b_wins"] -= 1
        mutations.append(profile)

        failures = copy.deepcopy(treatment)
        failures["candidates"][0]["cheap_failure_codes"].append("TOO_LONG")
        mutations.append(failures)

        trace = copy.deepcopy(treatment)
        trace["candidates"][0]["cheap_capture_evidence"][0]["games"][0]["capture"]["capture_count"] += 1
        mutations.append(trace)

        unknown_field = copy.deepcopy(treatment)
        unknown_field["candidates"][0]["unregistered_observation"] = 1
        mutations.append(unknown_field)

        for index, tampered in enumerate(mutations):
            with self.subTest(index=index):
                with self.assertRaises(ValueError):
                    build_capture_paired_result(
                        manifest,
                        baseline,
                        baseline,
                        tampered,
                        contract=TINY_CONTRACT,
                    )

    def test_any_exact_censor_forces_all_raw_response_conclusions_inconclusive(self):
        manifest, _, baseline, treatment = _evaluated_tiny()
        censored = copy.deepcopy(treatment)
        candidate = censored["candidates"][0]
        candidate["exact"] = {
            "status": "CENSORED_STATE_BUDGET",
            "result": None,
            "budget_observation": {
                "searched_states": 100000,
                "max_states": 100000,
            },
            "elapsed_seconds": candidate["exact"]["elapsed_seconds"],
        }
        candidate["exact_capture_evidence"] = None
        result = build_capture_paired_result(
            manifest,
            baseline,
            baseline,
            censored,
            contract=TINY_CONTRACT,
        )
        assessments = result["aggregate"]["predeclared_assessment"]
        self.assertEqual(result["aggregate"]["adaptive_stress_disposition"], "BLOCKED_EXACT_CENSOR")
        for key in (
            "primary_counterplay_response",
            "realized_capture_response",
            "cycling_dominance",
        ):
            self.assertEqual(assessments[key]["status"], "INCONCLUSIVE")
            self.assertEqual(assessments[key]["reasons"], ["EXACT_STATE_BUDGET_CENSORING"])

    def test_raw_result_reconstructs_and_retains_descriptive_timing(self):
        manifest, _, baseline, treatment = _evaluated_tiny()
        pinned_full = [
            {"case_id": "historical-extra"},
            *copy.deepcopy(baseline["candidates"]),
        ]
        result = build_capture_paired_result(
            manifest,
            baseline,
            pinned_full,
            treatment,
            contract=TINY_CONTRACT,
        )
        validated = validate_capture_paired_result(
            result,
            manifest,
            pinned_full,
            contract=TINY_CONTRACT,
        )
        self.assertEqual(validated["aggregate"]["exact_completed"], 2)
        self.assertEqual(validated["aggregate"]["adaptive_stress_disposition"], "ELIGIBLE")
        self.assertIn("primary_counterplay_response", validated["aggregate"]["predeclared_assessment"])
        self.assertFalse(validated["timing"]["used_for_assessment"])
        self.assertGreater(validated["timing"]["treatment"]["total_component_seconds"], 0)

    def test_evaluate_pairs_accepts_full_pinned_source_and_runs_in_order(self):
        manifest, pairs, baseline, _ = _evaluated_tiny()
        events = []
        pinned_full = [{"case_id": "unselected"}, *baseline["candidates"]]

        def baseline_callback(cases):
            events.append(("baseline", [case["case_id"] for case in cases]))
            return baseline

        def treatment_callback(cases):
            events.append(("treatment", [case["source_case_id"] for case in cases]))
            return evaluate_capture_cases(cases, clock=StepClock())

        result = evaluate_capture_pairs(
            manifest,
            pinned_full,
            baseline_evaluator=baseline_callback,
            treatment_evaluator=treatment_callback,
            contract=TINY_CONTRACT,
        )
        expected_ids = [pair["source_case_id"] for pair in pairs]
        self.assertEqual(events, [("baseline", expected_ids), ("treatment", expected_ids)])
        self.assertEqual(result["aggregate"]["pair_count"], 2)


def _stress_raw_candidate(definition_mapping):
    definition = parse_definition(definition_mapping)
    game_hash = definition_hash(definition)
    stratum = {"fixture": "dual", "max_plies": 18}
    return {
        "manifest_index": 0,
        "pair_id": "stress-pair",
        "source_case_id": "stress-source",
        "stratum": stratum,
        "vector_count": len(definition.role(Player.B).action.vectors),
        "baseline": {
            "analysis_gate_passes": True,
            "static": {"passes": True},
            "asymmetry": {"qualifies": True},
            "simplicity_passes": True,
            "exact": {
                "status": "COMPLETED",
                "result": {
                    "forced_result": "A_WIN",
                    "terminal_reason": "NO_LEGAL_ACTION",
                    "searched_states": 10,
                },
            },
        },
        "treatment": {
            "definition_hash": game_hash,
            "definition": definition.to_dict(),
            "analysis_gate_passes": True,
            "static": {"passes": True},
            "asymmetry": {"qualifies": True},
            "simplicity_passes": True,
            "cheap_profiles": [],
            "cheap_capture_evidence": [],
            "cheap_failure_codes": [],
            "exact": {
                "status": "COMPLETED",
                "result": {
                    "forced_result": "B_WIN",
                    "terminal_reason": "GOAL",
                    "searched_states": 20,
                },
            },
        },
        "paired_valid": True,
        "value_changed": True,
        "exact_capture_evidence": {
            "capture_count": 1,
            "repeated_position": False,
            "replacement_recapture": False,
            "capture_replace_cycle": False,
        },
        "normalized_pv": None,
        "monotonicity": {"monotonic": True},
    }


class CaptureStressTests(unittest.TestCase):
    def test_stress_entry_rejects_nonfrozen_configuration_before_work(self):
        custom_gates = PlayGates(max_draw_rate=0.49)
        cases = (
            {"seeds": [0]},
            {"max_candidates": 33},
            {"gates": custom_gates},
        )
        for arguments in cases:
            with self.subTest(arguments=arguments):
                with self.assertRaisesRegex(ValueError, "frozen seeds, gates"):
                    stress_capture_interactions({}, **arguments)

    def test_stress_entry_reconstructs_exact_census_before_work(self):
        manifest, _, baseline, treatment = _evaluated_tiny()
        raw = build_capture_paired_result(
            manifest,
            baseline,
            baseline,
            treatment,
            contract=TINY_CONTRACT,
        )
        raw["pre_stress_inspection"]["adaptive_stress_disposition"] = "ELIGIBLE"

        aggregate_tampered = copy.deepcopy(raw)
        aggregate_tampered["aggregate"]["exact_completed"] -= 1
        with self.assertRaisesRegex(ValueError, "exact census does not reconstruct"):
            stress_capture_interactions(aggregate_tampered)

        candidate_censored = copy.deepcopy(raw)
        candidate_censored["candidates"][0]["treatment"]["exact"]["status"] = (
            "CENSORED_STATE_BUDGET"
        )
        candidate_censored["aggregate"]["exact_completed"] -= 1
        candidate_censored["aggregate"]["exact_censored"] += 1
        candidate_censored["aggregate"]["exact_censored_hashes"] = [
            candidate_censored["candidates"][0]["treatment"]["definition_hash"]
        ]
        with self.assertRaisesRegex(ValueError, "blocked by exact censoring"):
            stress_capture_interactions(candidate_censored)

    def test_clean_first_selection_and_candidate_cap_are_explicit(self):
        base = _stress_raw_candidate(_dual_outcome_definition())
        candidates = []
        for index, failures in enumerate(([], ["A_DOMINANT"], ["TOO_LONG"])):
            item = copy.deepcopy(base)
            item["pair_id"] = "p{}".format(index)
            item["source_case_id"] = "s{}".format(index)
            item["treatment"]["definition_hash"] = "{:064x}".format(index + 1)
            item["treatment"]["cheap_failure_codes"] = failures
            candidates.append(item)
        selection = select_capture_stress_candidates(candidates, max_candidates=2)
        self.assertEqual(selection["eligible_count"], 3)
        self.assertEqual(selection["selected_count"], 2)
        self.assertEqual(selection["unselected_eligible_count"], 1)
        self.assertEqual(
            [item["selection_tier"] for item in selection["selected"]],
            ["CLEAN", "CLEAN"],
        )

    def test_balanced_direction_is_mismatch_and_makes_overall_inconclusive(self):
        definition = _dual_outcome_definition()
        raw_candidate = _stress_raw_candidate(definition)
        a_actions = [
            {"kind": "PLACE", "to": [0, 0]},
            {"kind": "MOVE_CAPTURE", "from": [2, 1], "to": [2, 0]},
            {"kind": "PLACE", "to": [0, 1]},
            {"kind": "MOVE_CAPTURE", "from": [2, 0], "to": [1, 0]},
            {"kind": "PLACE", "to": [0, 2]},
        ]
        b_actions = [
            {"kind": "PLACE", "to": [1, 2]},
            {"kind": "MOVE_CAPTURE", "from": [2, 1], "to": [1, 1]},
            {"kind": "PLACE", "to": [2, 2]},
            {"kind": "MOVE_CAPTURE", "from": [1, 1], "to": [0, 1]},
        ]
        games = []
        for seed in range(30):
            a_win = seed % 2 == 0
            games.append(
                {
                    "profile": "strong-minimax-depth5",
                    "seed": seed,
                    "actions": a_actions if a_win else b_actions,
                    "terminal_outcome": {
                        "winner": "A" if a_win else "B",
                        "reason": "GOAL",
                    },
                    "terminal_ply": 5 if a_win else 4,
                }
            )
        evidence = build_capture_profile_evidence(
            definition, "strong-minimax-depth5", games
        )
        evaluation = {
            "pair_id": raw_candidate["pair_id"],
            "source_case_id": raw_candidate["source_case_id"],
            "definition_hash": raw_candidate["treatment"]["definition_hash"],
            "status": "COMPLETED",
            "profile_evidence": evidence,
            "expanded_nodes": 123,
        }
        result = build_capture_stress_result([raw_candidate], [evaluation])
        assessment = result["aggregate"]["predeclared_assessment"]
        self.assertEqual(result["candidates"][0]["sampled_direction"], "DRAW_OR_BALANCED")
        self.assertFalse(result["candidates"][0]["direction_match"])
        self.assertEqual(assessment["general_strong_response"]["status"], "NOT_SUPPORTED")
        self.assertEqual(assessment["interaction_frontier"]["status"], "INCONCLUSIVE")
        self.assertEqual(assessment["overall_interaction_response"]["status"], "INCONCLUSIVE")
        validate_capture_stress_result(result, [raw_candidate])

    def test_capture_engaged_dominance_can_form_one_sided_b_frontier(self):
        definition = _dual_outcome_definition()
        raw_candidate = _stress_raw_candidate(definition)
        actions = [
            {"kind": "PLACE", "to": [1, 1]},
            {"kind": "MOVE_CAPTURE", "from": [2, 1], "to": [1, 1]},
            {"kind": "PLACE", "to": [2, 2]},
            {"kind": "MOVE_CAPTURE", "from": [1, 1], "to": [0, 1]},
        ]
        games = [
            {
                "profile": "strong-minimax-depth5",
                "seed": seed,
                "actions": actions,
                "terminal_outcome": {"winner": "B", "reason": "GOAL"},
                "terminal_ply": 4,
            }
            for seed in range(30)
        ]
        evidence = build_capture_profile_evidence(
            definition, "strong-minimax-depth5", games
        )
        evaluation = {
            "pair_id": raw_candidate["pair_id"],
            "source_case_id": raw_candidate["source_case_id"],
            "definition_hash": raw_candidate["treatment"]["definition_hash"],
            "status": "COMPLETED",
            "profile_evidence": evidence,
            "expanded_nodes": 456,
        }
        result = build_capture_stress_result([raw_candidate], [evaluation])
        candidate = result["candidates"][0]
        assessment = result["aggregate"]["predeclared_assessment"]
        self.assertIn("B_DOMINANT", candidate["strong_failure_codes"])
        self.assertTrue(candidate["interaction_frontier"])
        self.assertEqual(assessment["interaction_frontier"]["category"], "ONE_SIDED_B")
        self.assertEqual(assessment["overall_interaction_response"]["status"], "NOT_SUPPORTED")
        self.assertEqual(assessment["overall_interaction_response"]["next_branch"], "REJECT_ONE_SIDED_B")
        validate_capture_stress_result(result, [raw_candidate])

    def test_node_censor_seals_completed_prefix_next_seed_and_blocks_frontier(self):
        definition = _dual_outcome_definition()
        raw_candidate = _stress_raw_candidate(definition)
        game = {
            "profile": "strong-minimax-depth5",
            "seed": 0,
            "actions": [
                {"kind": "PLACE", "to": [1, 2]},
                {"kind": "MOVE_CAPTURE", "from": [2, 1], "to": [1, 1]},
                {"kind": "PLACE", "to": [2, 2]},
                {"kind": "MOVE_CAPTURE", "from": [1, 1], "to": [0, 1]},
            ],
            "terminal_outcome": {"winner": "B", "reason": "GOAL"},
            "terminal_ply": 4,
        }
        evidence = build_censored_capture_profile_evidence(
            definition,
            "strong-minimax-depth5",
            [game],
            tuple(range(30)),
            1,
            {
                "visited_nodes": 5000000,
                "max_nodes": 5000000,
                "scope": "per-candidate",
            },
        )
        evaluation = {
            "pair_id": raw_candidate["pair_id"],
            "source_case_id": raw_candidate["source_case_id"],
            "definition_hash": raw_candidate["treatment"]["definition_hash"],
            "status": "CENSORED_NODE_BUDGET",
            "profile_evidence": evidence,
            "expanded_nodes": 5000000,
        }
        result = build_capture_stress_result([raw_candidate], [evaluation])
        assessment = result["aggregate"]["predeclared_assessment"]
        self.assertEqual(result["aggregate"]["node_censored_count"], 1)
        self.assertEqual(assessment["interaction_frontier"]["status"], "INCONCLUSIVE")
        self.assertEqual(assessment["overall_interaction_response"]["status"], "INCONCLUSIVE")
        reasons = result["inspection"]["selected"][0]["reasons"]
        self.assertIn("NODE_CENSOR", reasons)
        self.assertIn("STRESS_SELECTED", reasons)
        validate_capture_stress_result(result, [raw_candidate])

    def test_stress_validator_rejects_nonfrozen_seeds_and_candidate_cap(self):
        manifest, _, baseline, treatment = _evaluated_tiny()
        raw = build_capture_paired_result(
            manifest,
            baseline,
            baseline,
            treatment,
            contract=TINY_CONTRACT,
        )
        result = build_capture_stress_result(raw, [])
        validate_capture_stress_result(result, raw)
        for field, replacement in (("seeds", [0]), ("max_candidates", 31)):
            tampered = copy.deepcopy(result)
            tampered["configuration"][field] = replacement
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, "frozen configuration"):
                    validate_capture_stress_result(tampered, raw)


if __name__ == "__main__":
    unittest.main()
