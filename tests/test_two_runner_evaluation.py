import copy
import hashlib
import json
import unittest
from unittest.mock import patch

import parity_forge.two_runner_evaluation as evaluation
from parity_forge.agents import AgentIdentity, SearchBudgetExceeded
from parity_forge.batch import PlayGates
from parity_forge.dsl import definition_hash, parse_definition
from parity_forge.engine import Action
from parity_forge.solver import SolveBudgetExceeded, solve_game
from parity_forge.symmetry import d4_canonical_hash
from parity_forge.two_runner import (
    TWO_RUNNER_SOURCE_STATE_BOUND,
    TWO_RUNNER_TREATMENT_STATE_BOUND,
    derive_two_runner_treatment,
    two_runner_added_position,
    two_runner_stratum,
)
from parity_forge.two_runner_evaluation import (
    assess_two_runner_pairs,
    assess_two_runner_response,
    build_censored_two_runner_profile_evidence,
    build_two_runner_depth5_result,
    build_two_runner_profile_evidence,
    derive_two_runner_lineage_trace,
    evaluate_two_runner_depth5,
    evaluate_two_runner_exact,
    two_runner_direction,
    two_runner_schedule,
    validate_two_runner_depth5_result,
    validate_two_runner_exact_result,
    validate_two_runner_lineage_trace,
    validate_two_runner_profile_evidence,
)


def _source_definition(
    index=0,
    *,
    first_player="A",
    original_position=(2, 0),
):
    return {
        "schema_version": 1,
        "name": "Two runner evaluation fixture {}".format(index),
        "board_size": 3,
        "first_player": first_player,
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
                    "vectors": [[-1, 0]],
                },
                "goal": {
                    "kind": "REACH_EDGE",
                    "piece": "runner",
                    "edge": "TOP",
                },
            },
        },
        "initial_pieces": [
            {
                "owner": "B",
                "piece": "runner",
                "position": list(original_position),
            }
        ],
    }


def _stratum_id(stratum):
    return "f{}-{}-{}".format(
        stratum["first_player"],
        stratum["goal_axis_relation"].lower(),
        stratum["vector_band"],
    )


def _pair(index, *, first_player="A"):
    source = parse_definition(
        _source_definition(index, first_player=first_player)
    )
    treatment = derive_two_runner_treatment(source)
    stratum = two_runner_stratum(source)
    pair = {
        "pair_id": "two-runner-test-pair-{:03d}".format(index),
        "source_case_id": "two-runner-test-source-{:03d}".format(index),
        "stratum_id": _stratum_id(stratum),
        "stratum": stratum,
        "selection_rank": 0,
        "selection_score": "{:064x}".format(index + 1),
        "source_definition_hash": definition_hash(source),
        "source_d4_canonical_hash": d4_canonical_hash(source),
        "source_definition": source.to_dict(),
        "treatment_definition_hash": definition_hash(treatment),
        "treatment_d4_canonical_hash": d4_canonical_hash(treatment),
        "treatment_definition": treatment.to_dict(),
        "added_runner_position": list(two_runner_added_position(source)),
        "piece_multiplicity_delta": 1,
    }
    payload = json.dumps(
        pair,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    pair["pair_fingerprint"] = hashlib.sha256(
        b"two-runner-v1-pair-v1\0" + payload
    ).hexdigest()
    return pair


def _manifest():
    return {
        "manifest_id": "two-runner-v1-test-manifest",
        "pairs": [_pair(0, first_player="A"), _pair(1, first_player="B")],
    }


class _StepClock:
    def __init__(self, step=0.25):
        self.value = 0.0
        self.step = step

    def __call__(self):
        self.value += self.step
        return self.value


class _FirstLegalAgent:
    def __init__(self, depth, max_nodes, *, censor=False):
        self.identity = AgentIdentity("minimax", 1, "depth{}".format(depth))
        self.max_nodes = max_nodes
        self.censor = censor
        self.total_nodes = 17
        self.reset_calls = 0

    def reset_budget(self):
        self.reset_calls += 1
        self.total_nodes = 0

    def select_action(self, definition, state, actions, rng):
        if self.censor:
            self.total_nodes = self.max_nodes
            raise SearchBudgetExceeded(
                "per-candidate", self.max_nodes, self.max_nodes
            )
        self.total_nodes += 1
        return actions[0]


def _game(seed, actions, winner="B", reason="GOAL"):
    return {
        "seed": seed,
        "actions": [action.to_dict() for action in actions],
        "terminal_outcome": {"winner": winner, "reason": reason},
        "terminal_ply": len(actions),
    }


class TwoRunnerLineageTests(unittest.TestCase):
    def test_lineage_is_source_witnessed_and_same_trace_engagement_is_rebuilt(self):
        source = parse_definition(_source_definition())
        treatment = derive_two_runner_treatment(source)
        actions = [
            Action.place(1, 1).to_dict(),
            Action.move((2, 0), (1, 0)).to_dict(),
            Action.place(2, 1).to_dict(),
            Action.move((2, 2), (1, 2)).to_dict(),
            Action.place(0, 2).to_dict(),
            Action.move((1, 0), (0, 0)).to_dict(),
        ]

        trace = derive_two_runner_lineage_trace(source, treatment, actions)

        self.assertEqual(trace["side"], "TREATMENT")
        self.assertEqual(
            [event["selected_lineage"] for event in trace["b_decisions"]],
            ["ORIGINAL", "ADDED", "ORIGINAL"],
        )
        self.assertGreater(
            trace["b_decisions"][0]["legal_action_counts"]["ORIGINAL"], 0
        )
        self.assertGreater(
            trace["b_decisions"][0]["legal_action_counts"]["ADDED"], 0
        )
        self.assertGreaterEqual(
            trace["summary"]["both_lineage_decision_count"], 2
        )
        self.assertTrue(trace["summary"]["original_moved"])
        self.assertTrue(trace["summary"]["added_moved"])
        self.assertTrue(trace["summary"]["both_lineages_moved"])
        self.assertTrue(trace["summary"]["two_runner_engaged"])
        validate_two_runner_lineage_trace(source, treatment, trace)

        tampered = copy.deepcopy(trace)
        tampered["b_decisions"][0]["selected_lineage"] = "ADDED"
        with self.assertRaises(ValueError):
            validate_two_runner_lineage_trace(source, treatment, tampered)

        tampered = copy.deepcopy(trace)
        tampered["b_decisions"][0]["legal_action_counts"]["ORIGINAL"] += 1
        with self.assertRaisesRegex(ValueError, "does not reconstruct"):
            validate_two_runner_lineage_trace(source, treatment, tampered)

    def test_sorted_treatment_piece_order_does_not_define_original(self):
        source = parse_definition(
            _source_definition(original_position=(2, 2))
        )
        treatment = derive_two_runner_treatment(source)
        self.assertEqual(treatment.initial_pieces[0].position, (2, 0))
        actions = [
            Action.place(0, 0).to_dict(),
            Action.move((2, 2), (1, 2)).to_dict(),
            Action.place(1, 0).to_dict(),
            Action.move((1, 2), (0, 2)).to_dict(),
        ]

        trace = derive_two_runner_lineage_trace(source, treatment, actions)

        self.assertEqual(
            [event["selected_lineage"] for event in trace["b_decisions"]],
            ["ORIGINAL", "ORIGINAL"],
        )
        self.assertTrue(trace["summary"]["original_moved"])
        self.assertFalse(trace["summary"]["added_moved"])
        self.assertFalse(trace["summary"]["two_runner_engaged"])

    def test_source_trace_has_no_added_lineage(self):
        source = parse_definition(_source_definition())
        actions = [
            Action.place(1, 1).to_dict(),
            Action.move((2, 0), (1, 0)).to_dict(),
            Action.place(2, 1).to_dict(),
            Action.move((1, 0), (0, 0)).to_dict(),
        ]

        trace = derive_two_runner_lineage_trace(source, source, actions)

        self.assertEqual(trace["side"], "SOURCE")
        self.assertIsNone(trace["start_positions"]["ADDED"])
        self.assertEqual(trace["summary"]["added_move_count"], 0)
        self.assertEqual(trace["summary"]["both_lineage_decision_count"], 0)
        self.assertFalse(trace["summary"]["two_runner_engaged"])


class TwoRunnerExactTests(unittest.TestCase):
    def test_schedule_and_exact_evaluation_are_source_then_treatment(self):
        manifest = _manifest()
        calls = []

        def recording_solver(definition, max_states):
            calls.append(len(definition.initial_pieces))
            return solve_game(definition, max_states=max_states)

        result = evaluate_two_runner_exact(
            manifest,
            expected_pair_count=2,
            solver=recording_solver,
            clock=_StepClock(),
        )

        self.assertEqual(calls, [1, 1, 2, 2])
        self.assertEqual(
            [slot["side"] for slot in result["slots"]],
            ["SOURCE", "SOURCE", "TREATMENT", "TREATMENT"],
        )
        self.assertEqual(result["aggregate"]["exact_censored_count"], 0)
        self.assertIs(type(result["aggregate"]["exact_censored_count"]), int)
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
        self.assertEqual(
            set(breakdowns["by_vector_band"]),
            {"v1_3", "v4", "v5", "v6_7"},
        )
        self.assertEqual(set(breakdowns["by_first_player"]), {"A", "B"})
        self.assertEqual(
            set(breakdowns["by_goal_axis_relation"]),
            {"ALIGNED", "ORTHOGONAL"},
        )
        self.assertEqual(
            set(breakdowns["by_structural_cell"]),
            {"fA-aligned", "fA-orthogonal", "fB-aligned", "fB-orthogonal"},
        )
        self.assertEqual(
            set(result["inspection"]["pools"]),
            {
                "{}_{}".format(band, group)
                for band in ("v1_3", "v4", "v5", "v6_7")
                for group in ("change", "control")
            },
        )
        for pair in result["pairs"]:
            self.assertNotEqual(
                pair["source_exact"]["result"]["terminal_reason"], "PLY_LIMIT"
            )
            self.assertNotEqual(
                pair["treatment_exact"]["result"]["terminal_reason"],
                "PLY_LIMIT",
            )
            self.assertEqual(pair["piece_multiplicity_delta"], 1)
            self.assertEqual(pair["source_pv_lineage"]["side"], "SOURCE")
            self.assertEqual(
                pair["treatment_pv_lineage"]["side"], "TREATMENT"
            )
        validate_two_runner_exact_result(
            result, manifest, expected_pair_count=2
        )

        retimed = copy.deepcopy(result)
        for slot in retimed["slots"]:
            slot["elapsed_seconds"] = 7.0
        retimed["timing"] = {
            "source_seconds": 14.0,
            "treatment_seconds": 14.0,
            "total_seconds": 28.0,
        }
        validate_two_runner_exact_result(
            retimed, manifest, expected_pair_count=2
        )
        retimed["timing"]["total_seconds"] = 29.0
        with self.assertRaisesRegex(ValueError, "slot timings"):
            validate_two_runner_exact_result(
                retimed, manifest, expected_pair_count=2
            )

    def test_exact_censor_keeps_its_slot_and_later_attempts_continue(self):
        manifest = _manifest()
        calls = []

        def censor_first(definition, max_states):
            calls.append(len(definition.initial_pieces))
            if len(calls) == 1:
                raise SolveBudgetExceeded(max_states, max_states)
            return solve_game(definition, max_states=max_states)

        result = evaluate_two_runner_exact(
            manifest,
            expected_pair_count=2,
            max_states=TWO_RUNNER_SOURCE_STATE_BOUND - 1,
            solver=censor_first,
        )

        self.assertEqual(calls, [1, 1, 2, 2])
        self.assertEqual(result["aggregate"]["exact_censored_count"], 1)
        self.assertEqual(result["aggregate"]["exact_censored_slots"], [0])
        self.assertEqual(
            result["aggregate"]["raw_assessments"]["overall"]["status"],
            "INCONCLUSIVE_EXACT_CENSOR",
        )
        validate_two_runner_exact_result(
            result,
            manifest,
            expected_pair_count=2,
            max_states=TWO_RUNNER_SOURCE_STATE_BOUND - 1,
        )

    def test_default_cap_censor_contradicts_the_structural_state_proof(self):
        manifest = _manifest()
        calls = []

        def impossible_censor(definition, max_states):
            calls.append(len(definition.initial_pieces))
            raise SolveBudgetExceeded(max_states, max_states)

        with self.assertRaisesRegex(ValueError, "side-specific proved bound"):
            evaluate_two_runner_exact(
                manifest,
                expected_pair_count=2,
                solver=impossible_censor,
            )
        self.assertEqual(calls, [1, 1])

    def test_censor_at_the_structural_bound_is_also_impossible(self):
        manifest = _manifest()

        def impossible_boundary_censor(definition, max_states):
            raise SolveBudgetExceeded(max_states, max_states)

        with self.assertRaisesRegex(ValueError, "beyond the side-specific"):
            evaluate_two_runner_exact(
                manifest,
                expected_pair_count=2,
                max_states=TWO_RUNNER_SOURCE_STATE_BOUND,
                solver=impossible_boundary_censor,
            )

    def test_malformed_source_phase_stops_before_treatment(self):
        manifest = _manifest()
        calls = []

        def invalid_first_source(definition, max_states):
            calls.append(len(definition.initial_pieces))
            result = solve_game(definition, max_states=max_states).to_dict()
            if len(calls) == 1:
                result["searched_states"] = True
            return result

        with self.assertRaisesRegex(ValueError, "searched.states"):
            evaluate_two_runner_exact(
                manifest,
                expected_pair_count=2,
                solver=invalid_first_source,
            )
        self.assertEqual(calls, [1, 1])

    def test_exact_validator_rejects_side_bounds_ply_limit_and_derived_tampering(self):
        manifest = _manifest()
        result = evaluate_two_runner_exact(manifest, expected_pair_count=2)

        for slot_index, searched_states in (
            (0, TWO_RUNNER_SOURCE_STATE_BOUND + 1),
            (2, TWO_RUNNER_TREATMENT_STATE_BOUND + 1),
            (2, True),
            (2, 0),
        ):
            with self.subTest(slot=slot_index, searched_states=searched_states):
                tampered = copy.deepcopy(result)
                tampered["slots"][slot_index]["exact"]["result"][
                    "searched_states"
                ] = searched_states
                with self.assertRaisesRegex(ValueError, "searched.states"):
                    validate_two_runner_exact_result(
                        tampered, manifest, expected_pair_count=2
                    )

        tampered = copy.deepcopy(result)
        tampered["slots"][0]["exact"]["result"]["cache_hits"] = True
        with self.assertRaisesRegex(ValueError, "cache_hits"):
            validate_two_runner_exact_result(
                tampered, manifest, expected_pair_count=2
            )

        for slot_index in (0, 2):
            with self.subTest(slot=slot_index, terminal="PLY_LIMIT"):
                tampered = copy.deepcopy(result)
                tampered["slots"][slot_index]["exact"]["result"][
                    "terminal_reason"
                ] = "PLY_LIMIT"
                with self.assertRaisesRegex(ValueError, "PLY_LIMIT"):
                    validate_two_runner_exact_result(
                        tampered, manifest, expected_pair_count=2
                    )

        tampered = copy.deepcopy(result)
        tampered["aggregate"]["exact_censored_count"] = True
        with self.assertRaisesRegex(ValueError, "reconstruct"):
            validate_two_runner_exact_result(
                tampered, manifest, expected_pair_count=2
            )

    def test_response_threshold_is_four_cases_across_two_strata(self):
        strata = (
            "fA-aligned-v1_3",
            "fA-aligned-v4",
            "fA-orthogonal-v1_3",
        )
        records = [
            {
                "pair_id": "p{}".format(index),
                "stratum_id": strata[index // 2],
                "containment_response": index < 4,
                "exact_engagement_response": index < 3,
            }
            for index in range(5)
        ]

        containment = assess_two_runner_response(
            records, "containment_response"
        )
        engagement = assess_two_runner_response(
            records, "exact_engagement_response"
        )

        self.assertEqual(containment["status"], "SUPPORTED")
        self.assertEqual(containment["count"], 4)
        self.assertEqual(containment["stratum_count"], 2)
        self.assertEqual(engagement["status"], "INCONCLUSIVE")

        for malformed in (
            {**records[0], "containment_response": 1},
            {**records[0], "stratum_id": "unknown"},
            {key: value for key, value in records[0].items() if key != "containment_response"},
        ):
            with self.subTest(malformed=malformed):
                with self.assertRaises(ValueError):
                    assess_two_runner_response(
                        [malformed], "containment_response"
                    )

        with self.assertRaisesRegex(ValueError, "boolean"):
            assess_two_runner_response(
                records, "containment_response", exact_censored=1
            )

    def test_schedule_rejects_reordering_and_duplicate_pair_identity(self):
        manifest = _manifest()
        schedule = two_runner_schedule(manifest, expected_pair_count=2)
        self.assertEqual(
            [entry["side"] for entry in schedule],
            ["SOURCE", "SOURCE", "TREATMENT", "TREATMENT"],
        )

        duplicate = copy.deepcopy(manifest)
        duplicate["pairs"][1]["pair_id"] = duplicate["pairs"][0]["pair_id"]
        with self.assertRaises(ValueError):
            two_runner_schedule(duplicate, expected_pair_count=2)

        with self.assertRaisesRegex(ValueError, "replaced"):
            two_runner_schedule(
                manifest,
                expected_pair_count=2,
                manifest_validator=lambda value: tuple(reversed(value["pairs"])),
            )

        mutating_manifest = copy.deepcopy(manifest)

        def mutating_validator(value):
            value["pairs"].reverse()
            return value

        with self.assertRaisesRegex(ValueError, "mutated"):
            two_runner_schedule(
                mutating_manifest,
                expected_pair_count=2,
                manifest_validator=mutating_validator,
            )

        with self.assertRaisesRegex(ValueError, "expected_pair_count"):
            two_runner_schedule(manifest, expected_pair_count=True)


class TwoRunnerProfileEvidenceTests(unittest.TestCase):
    def test_engagement_must_occur_within_one_completed_game(self):
        source = parse_definition(_source_definition())
        treatment = derive_two_runner_treatment(source)
        added_only = _game(
            0,
            (
                Action.place(1, 0),
                Action.move((2, 2), (1, 2)),
                Action.place(2, 1),
                Action.move((1, 2), (0, 2)),
            ),
        )
        choice_only = _game(
            1,
            (
                Action.place(1, 1),
                Action.move((2, 0), (1, 0)),
                Action.place(2, 1),
                Action.move((1, 0), (0, 0)),
            ),
        )

        evidence = build_two_runner_profile_evidence(
            source,
            treatment,
            "minimax-v1-depth5",
            (added_only, choice_only),
            (0, 1),
        )

        summary = evidence["profile_summary"]
        self.assertEqual(summary["games_with_added_move"], 1)
        self.assertEqual(summary["games_with_both_lineage_decision"], 1)
        self.assertEqual(summary["engaged_game_count"], 0)
        self.assertEqual(summary["engaged_seeds"], [])
        validate_two_runner_profile_evidence(
            source, treatment, evidence, expected_seeds=(0, 1)
        )

        tampered = copy.deepcopy(evidence)
        tampered["games"][0]["lineage"]["summary"][
            "two_runner_engaged"
        ] = True
        with self.assertRaisesRegex(ValueError, "lineage trace|reconstruct"):
            validate_two_runner_profile_evidence(
                source, treatment, tampered, expected_seeds=(0, 1)
            )

    def test_sampled_ply_limit_is_an_integrity_failure_on_both_sides(self):
        source = parse_definition(_source_definition())
        treatment = derive_two_runner_treatment(source)
        source_game = _game(
            0,
            (
                Action.place(1, 1),
                Action.move((2, 0), (1, 0)),
                Action.place(2, 1),
                Action.move((1, 0), (0, 0)),
            ),
        )
        treatment_game = _game(
            0,
            (
                Action.place(1, 1),
                Action.move((2, 0), (1, 0)),
                Action.place(2, 1),
                Action.move((2, 2), (1, 2)),
                Action.place(0, 2),
                Action.move((1, 0), (0, 0)),
            ),
        )
        for definition, game in (
            (source, source_game),
            (treatment, treatment_game),
        ):
            with self.subTest(runners=len(definition.initial_pieces)):
                game["terminal_outcome"]["reason"] = "PLY_LIMIT"
                with self.assertRaisesRegex(ValueError, "PLY_LIMIT"):
                    build_two_runner_profile_evidence(
                        source,
                        definition,
                        "minimax-v1-depth5",
                        (game,),
                        (0,),
                    )

    def test_direction_rejects_horizon_and_requires_decisive_match(self):
        profile = {"decisive_a_share": 1.0}
        exact = {"forced_result": "A_WIN"}
        self.assertTrue(
            two_runner_direction(profile, exact, "GOAL")["direction_match"]
        )
        mismatch = two_runner_direction(
            profile, {"forced_result": "DRAW"}, "NO_LEGAL_ACTION"
        )
        self.assertFalse(mismatch["direction_match"])
        censored = two_runner_direction(
            None,
            exact,
            "GOAL",
            profile_status="INCOMPLETE_NODE_CENSOR",
        )
        self.assertIsNone(censored["direction_match"])
        with self.assertRaisesRegex(ValueError, "PLY_LIMIT"):
            two_runner_direction(profile, exact, "PLY_LIMIT")


class TwoRunnerDepthTests(unittest.TestCase):
    def _exact(self):
        return evaluate_two_runner_exact(_manifest(), expected_pair_count=2)

    def test_fixed_schedule_uses_one_fresh_reset_agent_per_definition(self):
        manifest = _manifest()
        exact = self._exact()
        agents = []
        calls = []

        def factory(definition, depth, max_nodes, schedule_entry):
            calls.append((len(definition.initial_pieces), schedule_entry["side"]))
            agent = _FirstLegalAgent(depth, max_nodes)
            agents.append(agent)
            return agent

        result = evaluate_two_runner_depth5(
            manifest,
            exact,
            expected_pair_count=2,
            seeds=tuple(range(30)),
            depth=1,
            max_nodes=1_000,
            agent_factory=factory,
            clock=_StepClock(),
        )

        self.assertEqual(
            calls,
            [
                (1, "SOURCE"),
                (1, "SOURCE"),
                (2, "TREATMENT"),
                (2, "TREATMENT"),
            ],
        )
        self.assertEqual([agent.reset_calls for agent in agents], [1, 1, 1, 1])
        self.assertEqual(
            [slot["side"] for slot in result["slots"]],
            ["SOURCE", "SOURCE", "TREATMENT", "TREATMENT"],
        )
        self.assertEqual(result["aggregate"]["node_censored"], 0)
        self.assertEqual(result["aggregate"]["strong_frontier_count"], 1)
        self.assertEqual(result["aggregate"]["candidate_shaped_count"], 0)
        first_pair = result["pairs"][0]
        self.assertIn("TOO_SHORT", first_pair["source_profile"]["failure_codes"])
        self.assertIn(
            "A_DOMINANT", first_pair["treatment_profile"]["failure_codes"]
        )
        self.assertTrue(first_pair["treatment_same_game_engagement"])
        self.assertTrue(first_pair["strong_frontier"])
        self.assertFalse(first_pair["candidate_shaped"])
        self.assertEqual(
            result["aggregate"]["assessments"]["overall"]["status"],
            "INCONCLUSIVE",
        )
        self.assertEqual(
            result["inspection"]["reason_order"],
            [
                "EXACT_CENSOR",
                "NODE_CENSOR",
                "DIRECTION_MISMATCH",
                "CONTAINMENT_RESPONSE",
                "EXACT_ENGAGEMENT_RESPONSE",
                "STRONG_FRONTIER",
                "CANDIDATE_SHAPED",
                "OUTCOME_CHANGE_SAMPLE",
                "OUTCOME_UNCHANGED_CONTROL",
                "STRATUM_FLOOR",
            ],
        )
        breakdowns = result["aggregate"]["breakdowns"]
        self.assertEqual(
            set(breakdowns["by_vector_band"]),
            {"v1_3", "v4", "v5", "v6_7"},
        )
        self.assertEqual(set(breakdowns["by_first_player"]), {"A", "B"})
        self.assertEqual(
            set(breakdowns["by_goal_axis_relation"]),
            {"ALIGNED", "ORTHOGONAL"},
        )
        self.assertEqual(
            set(breakdowns["by_structural_cell"]),
            {"fA-aligned", "fA-orthogonal", "fB-aligned", "fB-orthogonal"},
        )
        self.assertEqual(len(breakdowns["by_stratum"]), 16)
        validate_two_runner_depth5_result(
            result,
            manifest,
            exact,
            expected_pair_count=2,
            seeds=tuple(range(30)),
            depth=1,
            max_nodes=1_000,
        )

    def test_node_censor_preserves_prefix_and_continues_later_definitions(self):
        manifest = _manifest()
        exact = self._exact()
        agents = []

        def factory(definition, depth, max_nodes, schedule_entry):
            agent = _FirstLegalAgent(
                depth,
                max_nodes,
                censor=not agents,
            )
            agents.append(agent)
            return agent

        result = evaluate_two_runner_depth5(
            manifest,
            exact,
            expected_pair_count=2,
            seeds=(0, 1),
            depth=1,
            max_nodes=100,
            agent_factory=factory,
        )

        self.assertEqual(len(agents), 4)
        first = result["slots"][0]
        self.assertEqual(first["status"], "INCOMPLETE_NODE_CENSOR")
        self.assertEqual(first["profile_evidence"]["completed_seed_prefix"], [])
        self.assertEqual(first["incomplete_attempt"]["seed"], 0)
        self.assertFalse(
            first["incomplete_attempt"]["lineage_prefix"]["terminal"][
                "is_terminal"
            ]
        )
        self.assertEqual(result["aggregate"]["node_censored"], 1)
        self.assertEqual(
            result["aggregate"]["assessments"]["overall"]["status"],
            "INCONCLUSIVE",
        )
        validate_two_runner_depth5_result(
            result,
            manifest,
            exact,
            expected_pair_count=2,
            seeds=(0, 1),
            depth=1,
            max_nodes=100,
        )

        tampered = copy.deepcopy(result)
        tampered["slots"][0]["incomplete_attempt"]["lineage_prefix"][
            "summary"
        ]["two_runner_engaged"] = True
        with self.assertRaises(ValueError):
            validate_two_runner_depth5_result(
                tampered,
                manifest,
                exact,
                expected_pair_count=2,
                seeds=(0, 1),
                depth=1,
                max_nodes=100,
            )

    def test_node_cap_is_cumulative_across_completed_seed_games(self):
        class CumulativeCapAgent(_FirstLegalAgent):
            def select_action(self, definition, state, actions, rng):
                if self.total_nodes >= self.max_nodes:
                    raise SearchBudgetExceeded(
                        "per-candidate", self.total_nodes, self.max_nodes
                    )
                self.total_nodes += 1
                return actions[0]

        manifest = _manifest()
        exact = self._exact()
        result = evaluate_two_runner_depth5(
            manifest,
            exact,
            expected_pair_count=2,
            seeds=(0, 1),
            depth=1,
            max_nodes=4,
            agent_factory=lambda definition, depth, max_nodes, schedule_entry: CumulativeCapAgent(
                depth, max_nodes
            ),
        )

        first = result["slots"][0]
        self.assertEqual(first["profile_evidence"]["completed_seed_prefix"], [0])
        self.assertEqual(first["incomplete_attempt"]["seed"], 1)
        self.assertEqual(first["incomplete_attempt"]["nodes_before_seed"], 3)
        self.assertEqual(first["incomplete_attempt"]["nodes_consumed"], 1)
        self.assertEqual(first["expanded_nodes"], 4)
        self.assertEqual(
            len(first["incomplete_attempt"]["completed_action_prefix"]), 1
        )
        validate_two_runner_depth5_result(
            result,
            manifest,
            exact,
            expected_pair_count=2,
            seeds=(0, 1),
            depth=1,
            max_nodes=4,
        )

    def test_exact_pv_and_cross_game_or_cannot_substitute_for_same_game_engagement(self):
        manifest = {"manifest_id": "one-pair", "pairs": [_pair(0)]}
        exact = evaluate_two_runner_exact(manifest, expected_pair_count=1)
        self.assertTrue(exact["pairs"][0]["exact_engagement_response"])
        pair = manifest["pairs"][0]
        source = parse_definition(pair["source_definition"])
        treatment = parse_definition(pair["treatment_definition"])
        source_actions = (
            Action.place(0, 0),
            Action.move((2, 0), (1, 0)),
            Action.place(0, 1),
        )
        source_games = tuple(
            _game(seed, source_actions, winner="A", reason="NO_LEGAL_ACTION")
            for seed in (0, 1)
        )
        added_only = _game(
            0,
            (
                Action.place(1, 0),
                Action.move((2, 2), (1, 2)),
                Action.place(0, 2),
            ),
            winner="A",
            reason="NO_LEGAL_ACTION",
        )
        choice_only = _game(
            1,
            (
                Action.place(0, 0),
                Action.move((2, 0), (1, 0)),
                Action.place(1, 2),
            ),
            winner="A",
            reason="NO_LEGAL_ACTION",
        )
        source_evidence = build_two_runner_profile_evidence(
            source,
            source,
            "minimax-v1-depth5",
            source_games,
            (0, 1),
        )
        treatment_evidence = build_two_runner_profile_evidence(
            source,
            treatment,
            "minimax-v1-depth5",
            (added_only, choice_only),
            (0, 1),
        )
        self.assertEqual(treatment_evidence["profile_summary"]["engaged_game_count"], 0)
        schedule = two_runner_schedule(manifest, expected_pair_count=1)

        def slot(entry, evidence):
            return {
                **entry,
                "status": "COMPLETED",
                "agent_identity": "minimax-v1-depth5",
                "profile_evidence": evidence,
                "game_nodes": [
                    {
                        "seed": seed,
                        "nodes_before": seed,
                        "nodes_after": seed + 1,
                        "nodes_used": 1,
                    }
                    for seed in (0, 1)
                ],
                "incomplete_attempt": None,
                "expanded_nodes": 2,
                "elapsed_seconds": 0.0,
            }

        result = build_two_runner_depth5_result(
            manifest,
            exact,
            (
                slot(schedule[0], source_evidence),
                slot(schedule[1], treatment_evidence),
            ),
            expected_pair_count=1,
            seeds=(0, 1),
            depth=5,
            max_nodes=100,
            gates=PlayGates(min_average_plies=0.0),
        )
        record = result["pairs"][0]
        self.assertFalse(record["treatment_same_game_engagement"])
        self.assertFalse(record["strong_frontier"])

    def test_engaged_censored_prefix_cannot_enter_the_frontier(self):
        manifest = {"manifest_id": "one-pair", "pairs": [_pair(0)]}
        exact = evaluate_two_runner_exact(manifest, expected_pair_count=1)
        pair = manifest["pairs"][0]
        source = parse_definition(pair["source_definition"])
        treatment = parse_definition(pair["treatment_definition"])
        source_game = _game(
            0,
            (
                Action.place(0, 0),
                Action.move((2, 0), (1, 0)),
                Action.place(0, 1),
            ),
            winner="A",
            reason="NO_LEGAL_ACTION",
        )
        source_evidence = build_two_runner_profile_evidence(
            source,
            source,
            "minimax-v1-depth5",
            (source_game,),
            (0,),
        )
        treatment_evidence = build_censored_two_runner_profile_evidence(
            source,
            treatment,
            "minimax-v1-depth5",
            (),
            (0,),
            0,
            {"visited_nodes": 100, "max_nodes": 100, "scope": "per-candidate"},
        )
        prefix_actions = [
            Action.place(1, 1).to_dict(),
            Action.move((2, 0), (1, 0)).to_dict(),
            Action.place(2, 1).to_dict(),
            Action.move((2, 2), (1, 2)).to_dict(),
        ]
        prefix = derive_two_runner_lineage_trace(
            source, treatment, prefix_actions, require_terminal=False
        )
        self.assertTrue(prefix["summary"]["two_runner_engaged"])
        schedule = two_runner_schedule(manifest, expected_pair_count=1)
        source_slot = {
            **schedule[0],
            "status": "COMPLETED",
            "agent_identity": "minimax-v1-depth5",
            "profile_evidence": source_evidence,
            "game_nodes": [
                {
                    "seed": 0,
                    "nodes_before": 0,
                    "nodes_after": 1,
                    "nodes_used": 1,
                }
            ],
            "incomplete_attempt": None,
            "expanded_nodes": 1,
            "elapsed_seconds": 0.0,
        }
        treatment_slot = {
            **schedule[1],
            "status": "INCOMPLETE_NODE_CENSOR",
            "agent_identity": "minimax-v1-depth5",
            "profile_evidence": treatment_evidence,
            "game_nodes": [],
            "incomplete_attempt": {
                "seed": 0,
                "completed_action_prefix": prefix_actions,
                "lineage_prefix": prefix,
                "nodes_before_seed": 0,
                "nodes_consumed": 100,
                "final_cumulative_nodes": 100,
                "limit": 100,
                "scope": "per-candidate",
            },
            "expanded_nodes": 100,
            "elapsed_seconds": 0.0,
        }
        result = build_two_runner_depth5_result(
            manifest,
            exact,
            (source_slot, treatment_slot),
            expected_pair_count=1,
            seeds=(0,),
            depth=5,
            max_nodes=100,
        )
        record = result["pairs"][0]
        self.assertIsNone(record["treatment_same_game_engagement"])
        self.assertFalse(record["strong_frontier"])
        self.assertEqual(
            result["aggregate"]["assessments"]["overall"]["status"],
            "INCONCLUSIVE",
        )

    def test_treatment_shape_failure_excludes_frontier(self):
        manifest = {"manifest_id": "one-pair", "pairs": [_pair(0)]}
        exact = evaluate_two_runner_exact(manifest, expected_pair_count=1)
        result = evaluate_two_runner_depth5(
            manifest,
            exact,
            expected_pair_count=1,
            seeds=tuple(range(30)),
            depth=1,
            max_nodes=1_000,
            gates=PlayGates(min_average_plies=6.0),
            agent_factory=lambda definition, depth, max_nodes, schedule_entry: _FirstLegalAgent(
                depth, max_nodes
            ),
        )
        record = result["pairs"][0]
        self.assertTrue(record["treatment_same_game_engagement"])
        self.assertIn("TOO_SHORT", record["treatment_profile"]["failure_codes"])
        self.assertFalse(record["strong_frontier"])

    def test_exact_censor_or_invalid_exact_blocks_before_agent_construction(self):
        manifest = _manifest()
        exact = self._exact()
        exact["aggregate"]["exact_censored_count"] = 1
        calls = []

        with self.assertRaises(ValueError):
            evaluate_two_runner_depth5(
                manifest,
                exact,
                expected_pair_count=2,
                seeds=(0,),
                depth=1,
                max_nodes=100,
                agent_factory=lambda **kwargs: calls.append(kwargs),
            )
        self.assertEqual(calls, [])

    def test_source_phase_normalization_failure_stops_before_treatment(self):
        manifest = _manifest()
        exact = self._exact()
        calls = []

        def factory(definition, depth, max_nodes, schedule_entry):
            calls.append((len(definition.initial_pieces), schedule_entry["side"]))
            return _FirstLegalAgent(depth, max_nodes)

        original = evaluation._normalize_profile_slot

        def reject_first_source(pair, expected, raw_slot, **kwargs):
            slot = copy.deepcopy(raw_slot)
            if expected["side"] == "SOURCE" and expected["pair_index"] == 0:
                slot["game_nodes"][0]["nodes_used"] = 0
            return original(pair, expected, slot, **kwargs)

        with patch.object(
            evaluation,
            "_normalize_profile_slot",
            side_effect=reject_first_source,
        ), self.assertRaisesRegex(ValueError, "nodes_used"):
            evaluate_two_runner_depth5(
                manifest,
                exact,
                expected_pair_count=2,
                seeds=(0,),
                depth=1,
                max_nodes=100,
                agent_factory=factory,
            )
        self.assertEqual(calls, [(1, "SOURCE"), (1, "SOURCE")])

    def test_candidate_thresholds_and_incomplete_priority(self):
        raw = {
            "containment_response": {"status": "SUPPORTED", "count": 4},
            "exact_engagement_response": {"status": "SUPPORTED", "count": 4},
        }

        def records(count, *, node=False, roles=("A_WIN", "B_WIN")):
            return [
                {
                    "pair_id": "p{}".format(index),
                    "structural_cell": (
                        "fA-aligned" if index < 2 else "fB-orthogonal"
                    ),
                    "treatment_exact_forced_result": roles[index % len(roles)],
                    "node_censored": node and index == 0,
                    "direction_mismatch": False,
                    "strong_frontier": True,
                    "candidate_shaped": True,
                }
                for index in range(count)
            ]

        supported = assess_two_runner_pairs(records(4), raw)
        self.assertEqual(
            supported["overall"]["status"], "SUPPORTED_TWO_RUNNER_SETUP"
        )
        short = assess_two_runner_pairs(records(3), raw)
        self.assertEqual(short["candidate_shape"]["status"], "INCONCLUSIVE")
        zero_records = records(1)
        zero_records[0]["strong_frontier"] = False
        zero_records[0]["candidate_shaped"] = False
        zero = assess_two_runner_pairs(zero_records, raw)
        self.assertEqual(
            zero["overall"]["status"], "NOT_SUPPORTED_TWO_RUNNER_SETUP"
        )
        incomplete = assess_two_runner_pairs(records(4, node=True), raw)
        self.assertEqual(incomplete["overall"]["status"], "INCONCLUSIVE")
        self.assertEqual(
            incomplete["strong_evidence"]["incomplete_reason"], "NODE_CENSOR"
        )

        one_cell_records = records(4)
        for record in one_cell_records:
            record["structural_cell"] = "fA-aligned"
        one_cell = assess_two_runner_pairs(one_cell_records, raw)
        self.assertEqual(one_cell["candidate_shape"]["status"], "INCONCLUSIVE")
        self.assertEqual(one_cell["overall"]["status"], "INCONCLUSIVE")

        one_role = assess_two_runner_pairs(records(4, roles=("A_WIN",)), raw)
        self.assertEqual(one_role["candidate_shape"]["status"], "INCONCLUSIVE")
        self.assertEqual(one_role["overall"]["status"], "INCONCLUSIVE")

        mismatched_records = records(4)
        mismatched_records[0]["direction_mismatch"] = True
        mismatched = assess_two_runner_pairs(mismatched_records, raw)
        self.assertEqual(mismatched["overall"]["status"], "INCONCLUSIVE")
        self.assertEqual(
            mismatched["strong_evidence"]["incomplete_reason"],
            "DIRECTION_MISMATCH",
        )

        boolean_confusion = records(1)
        boolean_confusion[0]["node_censored"] = 1
        with self.assertRaisesRegex(ValueError, "must be boolean"):
            assess_two_runner_pairs(boolean_confusion, raw)

    def test_inspection_pool_score_binds_both_d4_identities(self):
        pair = _pair(0)
        normalized = {
            "source_d4_canonical_hash": pair["source_d4_canonical_hash"],
            "treatment_d4_canonical_hash": pair["treatment_d4_canonical_hash"],
        }
        baseline = evaluation._inspection_score(
            evaluation._CHANGE_INSPECTION_DOMAIN, normalized
        )

        changed_source = dict(normalized)
        changed_source["source_d4_canonical_hash"] = "0" * 64
        changed_treatment = dict(normalized)
        changed_treatment["treatment_d4_canonical_hash"] = "f" * 64

        self.assertNotEqual(
            baseline,
            evaluation._inspection_score(
                evaluation._CHANGE_INSPECTION_DOMAIN, changed_source
            ),
        )
        self.assertNotEqual(
            baseline,
            evaluation._inspection_score(
                evaluation._CHANGE_INSPECTION_DOMAIN, changed_treatment
            ),
        )

    def test_depth_validator_rebuilds_lineage_aggregates_and_seals(self):
        manifest = _manifest()
        exact = self._exact()
        result = evaluate_two_runner_depth5(
            manifest,
            exact,
            expected_pair_count=2,
            seeds=(0, 1),
            depth=1,
            max_nodes=100,
            agent_factory=lambda definition, depth, max_nodes, schedule_entry: _FirstLegalAgent(
                depth, max_nodes
            ),
        )

        tampered = copy.deepcopy(result)
        tampered["slots"][2]["profile_evidence"]["games"][0]["lineage"][
            "summary"
        ]["added_move_count"] += 1
        with self.assertRaises(ValueError):
            validate_two_runner_depth5_result(
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
        with self.assertRaisesRegex(ValueError, "reconstruct"):
            validate_two_runner_depth5_result(
                tampered,
                manifest,
                exact,
                expected_pair_count=2,
                seeds=(0, 1),
                depth=1,
                max_nodes=100,
            )

        tampered = copy.deepcopy(result)
        tampered["inspection"]["reason_order"][4] = "ENGAGEMENT_RESPONSE"
        with self.assertRaisesRegex(ValueError, "reconstruct"):
            validate_two_runner_depth5_result(
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
