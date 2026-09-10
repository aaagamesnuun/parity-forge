import copy
import hashlib
import json
import unittest
from unittest.mock import patch

import parity_forge.capture_boundary_evaluation as evaluation
from parity_forge.agents import AgentIdentity, SearchBudgetExceeded
from parity_forge.capture_boundary_evaluation import (
    assess_capture_boundary_pairs,
    assess_capture_boundary_response,
    capture_boundary_direction,
    capture_boundary_schedule,
    evaluate_capture_boundary_depth5,
    evaluate_capture_boundary_exact,
    validate_capture_boundary_depth5_result,
    validate_capture_boundary_exact_result,
)
from parity_forge.dsl import definition_hash, parse_definition
from parity_forge.solver import SolveBudgetExceeded, solve_game
from parity_forge.symmetry import d4_canonical_hash


def _source_definition(index, vector_count):
    vectors = [[-1, 0], [0, 1], [1, 0]]
    if vector_count == 4:
        vectors.append([-1, 1])
    return {
        "schema_version": 1,
        "name": "Boundary tiny {}".format(index),
        "board_size": 3,
        "first_player": "B",
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
                    "kind": "MOVE",
                    "piece": "runner",
                    "vectors": vectors,
                },
                "goal": {
                    "kind": "REACH_EDGE",
                    "piece": "runner",
                    "edge": "TOP",
                },
            },
        },
        "initial_pieces": [
            {"owner": "B", "piece": "runner", "position": [1, 0]}
        ],
    }


def _pair(index, vector_count):
    source = parse_definition(_source_definition(index, vector_count))
    treatment_value = source.to_dict()
    treatment_value["schema_version"] = 3
    treatment_value["roles"]["B"]["action"]["kind"] = "MOVE_CAPTURE"
    treatment = parse_definition(treatment_value)
    return {
        "pair_id": "boundary-pair-{}".format(index),
        "source_case_id": "boundary-source-{}".format(index),
        "stratum": {
            "first_player": "B",
            "goal_axis_relation": "ALIGNED",
            "runner_start_class": "EDGE_MIDPOINT",
            "vector_count": vector_count,
        },
        "vector_count": vector_count,
        "selection_rank": 0,
        "selection_score": "{:064x}".format(index + 1),
        "source_definition": source.to_dict(),
        "source_definition_hash": definition_hash(source),
        "source_d4_canonical_hash": d4_canonical_hash(source),
        "treatment_definition": treatment.to_dict(),
        "treatment_definition_hash": definition_hash(treatment),
        "treatment_d4_canonical_hash": d4_canonical_hash(treatment),
    }


def _manifest():
    return {"manifest_id": "capture-boundary-tiny", "pairs": [_pair(0, 3), _pair(1, 4)]}


class _FirstLegalAgent:
    def __init__(self, depth, max_nodes, censor=False):
        self.identity = AgentIdentity("minimax", 1, "depth{}".format(depth))
        self.max_nodes = max_nodes
        self.censor = censor
        self.total_nodes = 0

    def reset_budget(self):
        self.total_nodes = 0

    def select_action(self, definition, state, actions, rng):
        if self.censor:
            self.total_nodes = self.max_nodes
            raise SearchBudgetExceeded(
                "per-candidate", self.max_nodes, self.max_nodes
            )
        self.total_nodes += 1
        return actions[0]


class _StepClock:
    def __init__(self, step=0.25):
        self.value = 0.0
        self.step = step

    def __call__(self):
        self.value += self.step
        return self.value


def _raw_assessments(primary_count=4, realized_count=4, cycling="NOT_DOMINANT"):
    return {
        "primary_response": {"status": "SUPPORTED", "count": primary_count},
        "realized_response": {"status": "SUPPORTED", "count": realized_count},
        "cycling_dominance": {"status": cycling},
    }


def _assessment_records(mode="boundary", candidate=True):
    records = []
    for cell in range(8):
        structural_cell = "cell-{}".format(cell)
        for vector_count in (3, 4):
            for rank in range(4):
                if mode == "boundary":
                    forced = "B_WIN" if vector_count == 4 or rank < 2 else "A_WIN"
                    frontier = True
                elif mode == "overcorrection":
                    forced = (
                        "B_WIN"
                        if vector_count == 3
                        or rank < (4 if cell < 4 else 3)
                        else "A_WIN"
                    )
                    frontier = forced == "B_WIN"
                else:
                    forced = "A_WIN"
                    frontier = False
                candidate_shaped = bool(
                    candidate
                    and mode == "boundary"
                    and cell < 2
                    and (
                        (vector_count == 3 and rank == 2)
                        or (vector_count == 4 and rank == 0)
                    )
                )
                records.append(
                    {
                        "pair_id": "{}-{}-{}".format(cell, vector_count, rank),
                        "stratum": {
                            "first_player": "A" if cell < 4 else "B",
                            "goal_axis_relation": (
                                "ALIGNED" if cell % 4 < 2 else "ORTHOGONAL"
                            ),
                            "runner_start_class": (
                                "CORNER" if cell % 2 == 0 else "EDGE_MIDPOINT"
                            ),
                            "vector_count": vector_count,
                        },
                        "structural_cell": structural_cell,
                        "vector_count": vector_count,
                        "treatment_exact_forced_result": forced,
                        "exact_horizon": False,
                        "node_censored": False,
                        "direction_mismatch": False,
                        "interaction_frontier": frontier,
                        "candidate_shaped": candidate_shaped,
                    }
                )
    return records


class CaptureBoundaryExactTests(unittest.TestCase):
    def test_schedule_is_all_sources_then_all_treatments(self):
        manifest = _manifest()
        calls = []

        def recording_solver(definition, max_states):
            calls.append(definition.schema_version)
            return solve_game(definition, max_states=max_states)

        result = evaluate_capture_boundary_exact(
            manifest,
            expected_pair_count=2,
            solver=recording_solver,
            clock=_StepClock(),
        )
        self.assertEqual(calls, [1, 1, 3, 3])
        self.assertEqual(
            [slot["side"] for slot in result["slots"]],
            ["SOURCE", "SOURCE", "TREATMENT", "TREATMENT"],
        )
        self.assertEqual(result["aggregate"]["exact_censored_count"], 0)
        self.assertIs(
            type(result["aggregate"]["exact_censored_count"]), int
        )
        self.assertEqual(
            [slot["elapsed_seconds"] for slot in result["slots"]],
            [0.25, 0.25, 0.25, 0.25],
        )
        self.assertEqual(
            result["timing"],
            {
                "source_seconds": 0.5,
                "treatment_seconds": 0.5,
                "total_seconds": 1.0,
            },
        )
        breakdowns = result["aggregate"]["breakdowns"]
        self.assertEqual(breakdowns["all"]["pair_count"], 2)
        self.assertEqual(breakdowns["by_vector"]["v3"]["pair_count"], 1)
        self.assertEqual(breakdowns["by_vector"]["v4"]["pair_count"], 1)
        self.assertEqual(len(breakdowns["by_structural_cell"]), 1)
        exact_all = breakdowns["all"]
        self.assertEqual(
            sum(exact_all["normalized_pv_common_prefix_histogram"].values()),
            exact_all["paired_completed_count"],
        )
        self.assertEqual(
            sum(exact_all["principal_variation_plies_delta_histogram"].values()),
            exact_all["paired_completed_count"],
        )
        expected_value_changes = sum(
            pair["monotonicity"]["value_changed"] for pair in result["pairs"]
        )
        self.assertEqual(exact_all["value_changed_count"], expected_value_changes)
        self.assertEqual(
            exact_all["capture_threat_without_pv_capture_count"],
            sum(
                pair["monotonicity"]["value_changed"]
                and pair["treatment_pv_capture"]["capture_count"] == 0
                for pair in result["pairs"]
            ),
        )
        for side in ("source", "treatment"):
            side_summary = exact_all[side]
            self.assertIn("null", side_summary["first_capture_ply_histogram"])
            self.assertEqual(
                sum(side_summary["pv_capture_count_histogram"].values()),
                side_summary["completed_count"],
            )
            self.assertEqual(
                sum(side_summary["first_capture_ply_histogram"].values()),
                side_summary["completed_count"],
            )
        validate_capture_boundary_exact_result(
            result, manifest, expected_pair_count=2
        )

        # Timing is descriptive: a consistently retimed result has identical
        # reconstructive evidence, while an inconsistent summary is rejected.
        retimed = copy.deepcopy(result)
        for slot in retimed["slots"]:
            slot["elapsed_seconds"] = 7.0
        retimed["timing"] = {
            "source_seconds": 14.0,
            "treatment_seconds": 14.0,
            "total_seconds": 28.0,
        }
        validate_capture_boundary_exact_result(
            retimed, manifest, expected_pair_count=2
        )
        retimed["timing"]["total_seconds"] = 29.0
        with self.assertRaisesRegex(ValueError, "slot timings"):
            validate_capture_boundary_exact_result(
                retimed, manifest, expected_pair_count=2
            )

        noncanonical = copy.deepcopy(manifest)
        noncanonical["pairs"][0]["source_definition_hash"] = noncanonical[
            "pairs"
        ][0]["source_definition_hash"].upper()
        with self.assertRaisesRegex(ValueError, "canonical lowercase"):
            capture_boundary_schedule(noncanonical, expected_pair_count=2)

    def test_exact_censor_keeps_its_slot_and_later_attempts_continue(self):
        manifest = _manifest()
        calls = []

        def censor_first(definition, max_states):
            calls.append(definition.schema_version)
            if len(calls) == 1:
                raise SolveBudgetExceeded(max_states, max_states)
            return solve_game(definition, max_states=max_states)

        result = evaluate_capture_boundary_exact(
            manifest,
            expected_pair_count=2,
            solver=censor_first,
        )
        self.assertEqual(calls, [1, 1, 3, 3])
        self.assertEqual(result["aggregate"]["exact_censored_count"], 1)
        self.assertEqual(result["aggregate"]["exact_censored_slots"], [0])
        self.assertEqual(
            result["aggregate"]["raw_assessments"]["overall"]["status"],
            "INCONCLUSIVE_EXACT_CENSOR",
        )
        validate_capture_boundary_exact_result(
            result, manifest, expected_pair_count=2
        )

        # A completed treatment can independently expose a horizon even when its
        # paired source was censored.  The exact-only inspection must retain both
        # facts while change/control pools remain paired-complete only.
        records = copy.deepcopy(result["pairs"])
        records[0]["treatment_exact"]["result"]["terminal_reason"] = "PLY_LIMIT"
        manifest_pairs = []
        for index, raw_pair in enumerate(manifest["pairs"]):
            pair = copy.deepcopy(raw_pair)
            pair["stratum_id"] = evaluation._normalize_pair(raw_pair, index)[
                "stratum_id"
            ]
            manifest_pairs.append(pair)
        inspection = evaluation.build_capture_boundary_inspection(
            records,
            manifest_pairs=manifest_pairs,
            exact_censored=True,
        )
        reasons = next(
            row["reasons"]
            for row in inspection["selected"]
            if row["pair_id"] == records[0]["pair_id"]
        )
        self.assertEqual(reasons[:2], ["EXACT_CENSOR", "EXACT_HORIZON"])

    def test_invalid_source_evidence_stops_before_any_treatment(self):
        manifest = _manifest()
        calls = []

        def invalid_first_source(definition, max_states):
            calls.append(definition.schema_version)
            result = solve_game(definition, max_states=max_states).to_dict()
            if len(calls) == 1:
                result["searched_states"] = True
            return result

        with self.assertRaisesRegex(ValueError, "searched_states"):
            evaluate_capture_boundary_exact(
                manifest,
                expected_pair_count=2,
                solver=invalid_first_source,
                clock=_StepClock(),
            )
        self.assertEqual(calls, [1, 1])

    def test_exact_validator_rejects_derived_and_state_tampering(self):
        manifest = _manifest()
        result = evaluate_capture_boundary_exact(manifest, expected_pair_count=2)
        tampered = copy.deepcopy(result)
        tampered["aggregate"]["exact_censored_count"] = True
        with self.assertRaises(ValueError):
            validate_capture_boundary_exact_result(
                tampered, manifest, expected_pair_count=2
            )

        tampered = copy.deepcopy(result)
        tampered["slots"][0]["exact"]["result"]["searched_states"] = 43_777
        with self.assertRaisesRegex(ValueError, "searched_states"):
            validate_capture_boundary_exact_result(
                tampered, manifest, expected_pair_count=2
            )

        tampered = copy.deepcopy(result)
        tampered["aggregate"]["breakdowns"]["all"]["source"][
            "searched_states_total"
        ] += 1
        with self.assertRaisesRegex(ValueError, "does not reconstruct"):
            validate_capture_boundary_exact_result(
                tampered, manifest, expected_pair_count=2
            )

        tampered = copy.deepcopy(result)
        tampered["aggregate"]["breakdowns"]["all"][
            "normalized_pv_common_prefix_histogram"
        ]["999"] = 1
        with self.assertRaisesRegex(ValueError, "does not reconstruct"):
            validate_capture_boundary_exact_result(
                tampered, manifest, expected_pair_count=2
            )

        tampered = copy.deepcopy(result)
        tampered["aggregate"]["breakdowns"]["all"]["treatment"][
            "first_capture_ply_histogram"
        ]["null"] += 1
        with self.assertRaisesRegex(ValueError, "does not reconstruct"):
            validate_capture_boundary_exact_result(
                tampered, manifest, expected_pair_count=2
            )

    def test_response_threshold_is_at_least_four_across_two_strata(self):
        records = [
            {
                "pair_id": "p{}".format(index),
                "stratum_id": "s{}".format(index // 2),
                "primary_response": True,
                "realized_response": index < 3,
            }
            for index in range(5)
        ]
        primary = assess_capture_boundary_response(records, "primary_response")
        realized = assess_capture_boundary_response(records, "realized_response")
        self.assertEqual(primary["status"], "SUPPORTED")
        self.assertEqual(primary["count"], 5)
        self.assertEqual(realized["status"], "INCONCLUSIVE")


class CaptureBoundaryDepthTests(unittest.TestCase):
    def test_invalid_source_profile_stops_before_any_treatment_agent(self):
        manifest = _manifest()
        exact = evaluate_capture_boundary_exact(manifest, expected_pair_count=2)
        factory_calls = []

        def factory(definition, depth, max_nodes, schedule_entry):
            factory_calls.append((definition.schema_version, schedule_entry["side"]))
            return _FirstLegalAgent(depth, max_nodes)

        original_normalizer = evaluation._normalize_profile_slot

        def reject_tampered_source(pair, expected, raw_slot, **kwargs):
            slot = copy.deepcopy(raw_slot)
            if expected["side"] == "SOURCE" and expected["pair_index"] == 0:
                slot["game_nodes"][0]["nodes_used"] = 0
            return original_normalizer(pair, expected, slot, **kwargs)

        with patch.object(
            evaluation,
            "_normalize_profile_slot",
            side_effect=reject_tampered_source,
        ), self.assertRaisesRegex(ValueError, "nodes_used"):
            evaluate_capture_boundary_depth5(
                manifest,
                exact,
                expected_pair_count=2,
                seeds=(0, 1),
                depth=1,
                max_nodes=100,
                agent_factory=factory,
                clock=_StepClock(),
            )
        self.assertEqual(
            factory_calls,
            [(1, "SOURCE"), (1, "SOURCE")],
        )

    def test_node_censor_preserves_prefix_and_does_not_stop_schedule(self):
        manifest = _manifest()
        exact = evaluate_capture_boundary_exact(manifest, expected_pair_count=2)
        calls = []

        def factory(definition, depth, max_nodes, schedule_entry):
            calls.append((definition.schema_version, schedule_entry["side"]))
            return _FirstLegalAgent(depth, max_nodes, censor=len(calls) == 1)

        result = evaluate_capture_boundary_depth5(
            manifest,
            exact,
            expected_pair_count=2,
            seeds=(0, 1),
            depth=1,
            max_nodes=50,
            agent_factory=factory,
        )
        self.assertEqual(
            calls,
            [(1, "SOURCE"), (1, "SOURCE"), (3, "TREATMENT"), (3, "TREATMENT")],
        )
        self.assertEqual(result["aggregate"]["node_censored"], 1)
        first = result["slots"][0]
        self.assertEqual(first["status"], "INCOMPLETE_NODE_CENSOR")
        self.assertEqual(first["profile_evidence"]["completed_seed_prefix"], [])
        self.assertEqual(first["incomplete_attempt"]["seed"], 0)
        self.assertIn(
            "NODE_CENSOR",
            next(
                row["reasons"]
                for row in result["inspection"]["selected"]
                if row["pair_id"] == first["pair_id"]
            ),
        )
        self.assertEqual(
            result["aggregate"]["descriptive_profiles"]["source"][
                "censored_prefixes"
            ]["definition_count"],
            1,
        )
        censored_nodes = result["aggregate"]["descriptive_profiles"]["source"][
            "censored_prefixes"
        ]
        self.assertEqual(censored_nodes["completed_game_nodes"], 0)
        self.assertEqual(censored_nodes["incomplete_attempt_nodes"], 50)
        self.assertEqual(censored_nodes["expanded_nodes_total"], 50)
        self.assertEqual(result["aggregate"]["incomplete_attempt_nodes_total"], 50)
        self.assertEqual(
            result["aggregate"]["expanded_nodes_total"],
            result["aggregate"]["completed_game_nodes_total"]
            + result["aggregate"]["incomplete_attempt_nodes_total"],
        )
        self.assertEqual(
            result["aggregate"]["breakdowns"]["all"]["node_censor_count"], 1
        )
        self.assertEqual(
            result["aggregate"]["assessments"]["overall"]["status"],
            "INCONCLUSIVE",
        )
        validate_capture_boundary_depth5_result(
            result,
            manifest,
            exact,
            expected_pair_count=2,
            seeds=(0, 1),
            depth=1,
            max_nodes=50,
        )
        tampered = copy.deepcopy(result)
        tampered["aggregate"]["incomplete_attempt_nodes_total"] += 1
        with self.assertRaisesRegex(ValueError, "does not reconstruct"):
            validate_capture_boundary_depth5_result(
                tampered,
                manifest,
                exact,
                expected_pair_count=2,
                seeds=(0, 1),
                depth=1,
                max_nodes=50,
            )

    def test_sampled_ply_limit_is_not_exact_horizon(self):
        sampled = {
            "decisive_a_share": 1.0,
            "terminal_reasons": {"GOAL": 1, "PLY_LIMIT": 1},
        }
        exact = {"forced_result": "A_WIN"}
        non_horizon = capture_boundary_direction(sampled, exact, "GOAL")
        horizon = capture_boundary_direction(sampled, exact, "PLY_LIMIT")
        self.assertEqual(non_horizon["status"], "MATCH")
        self.assertTrue(non_horizon["direction_match"])
        self.assertEqual(horizon["status"], "NOT_APPLICABLE_HORIZON")
        self.assertIsNone(horizon["sampled_direction"])
        censored_horizon = capture_boundary_direction(
            None, exact, "PLY_LIMIT", profile_status="INCOMPLETE_NODE_CENSOR"
        )
        self.assertEqual(
            censored_horizon["status"], "NOT_APPLICABLE_HORIZON"
        )

        exact_draw = capture_boundary_direction(sampled, {"forced_result": "DRAW"}, "GOAL")
        self.assertEqual(exact_draw["status"], "MISMATCH")
        self.assertFalse(exact_draw["direction_match"])

    def test_boundary_composite_thresholds_and_priority(self):
        supported = assess_capture_boundary_pairs(
            _assessment_records("boundary", candidate=True), _raw_assessments()
        )
        self.assertEqual(
            supported["mechanical_boundary"]["status"],
            "SUPPORTED_VECTOR_BOUNDARY",
        )
        self.assertEqual(supported["candidate_shape"]["status"], "SUPPORTED")
        self.assertEqual(supported["overall"]["status"], "SUPPORTED")

        supported_with_draw_records = _assessment_records(
            "boundary", candidate=True
        )
        extra_candidate = next(
            record
            for record in supported_with_draw_records
            if record["structural_cell"] == "cell-0"
            and record["vector_count"] == 3
            and not record["candidate_shaped"]
            and record["treatment_exact_forced_result"] == "A_WIN"
        )
        extra_candidate["treatment_exact_forced_result"] = "DRAW"
        extra_candidate["candidate_shaped"] = True
        supported_with_draw = assess_capture_boundary_pairs(
            supported_with_draw_records, _raw_assessments()
        )
        self.assertEqual(
            supported_with_draw["candidate_shape"]["status"], "SUPPORTED"
        )

        cliff = assess_capture_boundary_pairs(
            _assessment_records("boundary", candidate=False), _raw_assessments()
        )
        self.assertEqual(cliff["overall"]["status"], "NOT_SUPPORTED")
        self.assertTrue(cliff["overall"]["dominance_cliff"])

        overcorrection = assess_capture_boundary_pairs(
            _assessment_records("overcorrection", candidate=False),
            _raw_assessments(),
        )
        self.assertEqual(overcorrection["overall"]["status"], "OVERCORRECTION")

        cycling_records = _assessment_records("boundary", candidate=True)
        cycling_records[0]["exact_horizon"] = True
        cycling = assess_capture_boundary_pairs(
            cycling_records, _raw_assessments(cycling="DOMINANT")
        )
        self.assertEqual(cycling["overall"]["status"], "REJECT_CYCLING")

    def test_depth_validator_reconstructs_profiles_inspection_and_aggregates(self):
        manifest = _manifest()
        exact = evaluate_capture_boundary_exact(manifest, expected_pair_count=2)
        result = evaluate_capture_boundary_depth5(
            manifest,
            exact,
            expected_pair_count=2,
            seeds=(0, 1),
            depth=1,
            max_nodes=100,
            agent_factory=lambda definition, depth, max_nodes, schedule_entry: _FirstLegalAgent(
                depth, max_nodes
            ),
            clock=_StepClock(),
        )
        self.assertEqual(result["timing"]["total_seconds"], 1.0)
        completed_bucket = result["aggregate"]["breakdowns"]["all"]["treatment"][
            "completed"
        ]
        self.assertIn("null", completed_bucket["first_capture_ply_histogram"])
        self.assertEqual(
            sum(completed_bucket["first_capture_ply_histogram"].values()),
            completed_bucket["game_count"],
        )
        for side, domain in (
            ("source", b"capture-boundary-v1-source-depth5-slots-v1\0"),
            ("treatment", b"capture-boundary-v1-treatment-depth5-slots-v1\0"),
        ):
            start = 0 if side == "source" else 2
            slots = result["slots"][start : start + 2]
            payload = [
                {
                    key: value
                    for key, value in slot.items()
                    if key != "elapsed_seconds"
                }
                for slot in slots
            ]
            expected_digest = hashlib.sha256(
                domain
                + json.dumps(
                    payload,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                    allow_nan=False,
                ).encode("utf-8")
            ).hexdigest()
            self.assertEqual(
                result["aggregate"]["{}_evidence_digest".format(side)],
                expected_digest,
            )
        validate_capture_boundary_depth5_result(
            result,
            manifest,
            exact,
            expected_pair_count=2,
            seeds=(0, 1),
            depth=1,
            max_nodes=100,
        )
        retimed_exact = copy.deepcopy(exact)
        for slot in retimed_exact["slots"]:
            slot["elapsed_seconds"] = 3.0
        retimed_exact["timing"] = {
            "source_seconds": 6.0,
            "treatment_seconds": 6.0,
            "total_seconds": 12.0,
        }
        validate_capture_boundary_depth5_result(
            result,
            manifest,
            retimed_exact,
            expected_pair_count=2,
            seeds=(0, 1),
            depth=1,
            max_nodes=100,
        )
        tampered = copy.deepcopy(result)
        tampered["slots"][0]["profile_evidence"]["games"][0]["capture"][
            "capture_count"
        ] += 1
        with self.assertRaises(ValueError):
            validate_capture_boundary_depth5_result(
                tampered,
                manifest,
                exact,
                expected_pair_count=2,
                seeds=(0, 1),
                depth=1,
                max_nodes=100,
            )

        forged_profile = copy.deepcopy(result)
        forged_profile["slots"][0]["profile_evidence"]["profile"] = (
            "forged-profile"
        )
        for game in forged_profile["slots"][0]["profile_evidence"]["games"]:
            game["profile"] = "forged-profile"
        with self.assertRaisesRegex(ValueError, "profile evidence identity"):
            validate_capture_boundary_depth5_result(
                forged_profile,
                manifest,
                exact,
                expected_pair_count=2,
                seeds=(0, 1),
                depth=1,
                max_nodes=100,
            )

        altered_exact_cap = copy.deepcopy(exact)
        altered_exact_cap["configuration"]["max_states"] = 99_999
        with self.assertRaisesRegex(ValueError, "exact result|configuration"):
            evaluation.build_capture_boundary_depth5_result(
                manifest,
                altered_exact_cap,
                result["slots"],
                expected_pair_count=2,
                seeds=(0, 1),
                depth=1,
                max_nodes=100,
            )

        tampered = copy.deepcopy(result)
        tampered["slots"][0]["game_nodes"][0]["nodes_used"] = 0
        with self.assertRaisesRegex(ValueError, "nodes_used"):
            validate_capture_boundary_depth5_result(
                tampered,
                manifest,
                exact,
                expected_pair_count=2,
                seeds=(0, 1),
                depth=1,
                max_nodes=100,
            )

        tampered = copy.deepcopy(result)
        tampered["aggregate"]["breakdowns"]["by_vector"]["v3"][
            "candidate_shaped_count"
        ] += 1
        with self.assertRaisesRegex(ValueError, "does not reconstruct"):
            validate_capture_boundary_depth5_result(
                tampered,
                manifest,
                exact,
                expected_pair_count=2,
                seeds=(0, 1),
                depth=1,
                max_nodes=100,
            )

        tampered = copy.deepcopy(result)
        tampered["aggregate"]["source_evidence_digest"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "does not reconstruct"):
            validate_capture_boundary_depth5_result(
                tampered,
                manifest,
                exact,
                expected_pair_count=2,
                seeds=(0, 1),
                depth=1,
                max_nodes=100,
            )

        tampered = copy.deepcopy(result)
        tampered["aggregate"]["breakdowns"]["all"]["treatment"]["completed"][
            "first_capture_ply_histogram"
        ]["null"] += 1
        with self.assertRaisesRegex(ValueError, "does not reconstruct"):
            validate_capture_boundary_depth5_result(
                tampered,
                manifest,
                exact,
                expected_pair_count=2,
                seeds=(0, 1),
                depth=1,
                max_nodes=100,
            )


if __name__ == "__main__":
    unittest.main()
