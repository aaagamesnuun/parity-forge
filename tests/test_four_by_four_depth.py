import copy
import inspect
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

import parity_forge.four_by_four_calibration as calibration
import parity_forge.four_by_four_depth as depth_evaluation
import parity_forge.four_by_four_evaluation as exact_evaluation
from parity_forge.agents import AgentIdentity, SearchBudgetExceeded
from parity_forge.dsl import definition_hash
from parity_forge.engine import apply_action, initial_state, legal_actions
from parity_forge.four_by_four_calibration import (
    FOUR_BY_FOUR_CASE_COUNT,
    build_four_by_four_calibration_manifest,
    build_four_by_four_closed_history_projection,
)


REPOSITORY = Path(__file__).resolve().parents[1]


def _provenance():
    plan_path = "docs/plans/active/0011-four-by-four-evaluator-transfer-calibration.md"
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


class _StepClock:
    def __init__(self, step=1.0):
        self.value = 0.0
        self.step = step

    def __call__(self):
        self.value += self.step
        return self.value


class _FirstActionRolloutSolver:
    """Legal deterministic test double; it does not perform minimax search."""

    def __init__(self):
        self.calls = []

    def __call__(self, definition, *, max_states):
        self.calls.append((definition_hash(definition), max_states))
        state = initial_state(definition)
        actions = []
        while not state.terminal:
            action = legal_actions(definition, state)[0]
            actions.append(action)
            state = apply_action(definition, state, action)
        assert state.outcome is not None
        winner = state.outcome.winner.value if state.outcome.winner else None
        forced = {"A": "A_WIN", "B": "B_WIN", None: "DRAW"}[winner]
        return {
            "value_for_a": {"A_WIN": 1, "B_WIN": -1, "DRAW": 0}[forced],
            "forced_result": forced,
            "principal_variation": [action.to_dict() for action in actions],
            "principal_variation_plies": len(actions),
            "terminal_reason": state.outcome.reason,
            "searched_states": len(actions) + 1,
            "cache_hits": len(actions),
        }


class _FirstLegalAgent:
    """Cheap deterministic depth-5-shaped agent used only through the private seam."""

    def __init__(self, depth, max_nodes, *, censor_game=None):
        self.identity = AgentIdentity("minimax", 1, "depth{}".format(depth))
        self.depth = depth
        self.max_nodes = max_nodes
        self.max_total_nodes = max_nodes
        self.max_nodes_per_move = 0
        self.censor_game = censor_game
        self.total_nodes = 17
        self.reset_calls = 0
        self.games_started = 0
        self.select_calls = 0
        self.roles_seen = set()

    def reset_budget(self):
        self.reset_calls += 1
        self.total_nodes = 0

    def select_action(self, definition, state, actions, rng):
        if state.ply == 0:
            self.games_started += 1
        self.select_calls += 1
        self.roles_seen.add(state.to_move.value)
        if self.censor_game == self.games_started:
            self.total_nodes = self.max_nodes
            raise SearchBudgetExceeded(
                "per-candidate", self.total_nodes, self.max_nodes
            )
        # Minimax visits at least each legal root candidate before choosing.
        self.total_nodes += len(actions)
        return actions[0]


class FourByFourDepthEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ledger_path = REPOSITORY / calibration.FOUR_BY_FOUR_LEDGER_PATH
        ledger_bytes = ledger_path.read_bytes()
        ledger = json.loads(ledger_bytes)
        historical_bytes = {
            path: (REPOSITORY / path).read_bytes()
            for path in ledger["historical_artifact_paths"]
        }
        plan0010_bytes = (
            REPOSITORY / calibration.FOUR_BY_FOUR_PLAN0010_MANIFEST_PATH
        ).read_bytes()
        cls.history = build_four_by_four_closed_history_projection(
            ledger_bytes, historical_bytes, plan0010_bytes
        )
        cls.manifest = build_four_by_four_calibration_manifest(
            cls.history, _provenance()
        )
        cls.exact_result = exact_evaluation._evaluate_four_by_four_exact(
            cls.manifest,
            cls.history,
            solver=_FirstActionRolloutSolver(),
            clock=_StepClock(),
        )
        cls.agents = []
        cls.factory_entries = []

        def factory(**kwargs):
            cls.factory_entries.append(copy.deepcopy(kwargs["schedule_entry"]))
            agent = _FirstLegalAgent(kwargs["depth"], kwargs["max_nodes"])
            cls.agents.append(agent)
            return agent

        cls.result = depth_evaluation._evaluate_four_by_four_depth5(
            cls.manifest,
            cls.history,
            cls.exact_result,
            agent_factory=factory,
            clock=_StepClock(),
        )

    def test_fixture_has_predeclared_sufficient_exact_coverage(self):
        assessment = self.exact_result["assessment"]
        self.assertEqual(assessment["status"], "SUFFICIENT_LABEL_COVERAGE")
        self.assertEqual(assessment["depth5_disposition"], "ELIGIBLE")
        self.assertEqual(
            assessment["observed"]["label_counts"],
            {"A_WIN": 9, "B_WIN": 7, "HORIZON_DRAW": 16},
        )

    def test_fixed_schedule_fresh_reset_agents_and_cumulative_ledgers(self):
        schedule = depth_evaluation.four_by_four_depth5_schedule(
            self.manifest, self.history, self.exact_result
        )
        self.assertEqual(len(schedule), FOUR_BY_FOUR_CASE_COUNT)
        self.assertEqual(
            [entry["case_id"] for entry in schedule],
            [case["case_id"] for case in self.manifest["cases"]],
        )
        for entry in schedule:
            self.assertNotIn("calibration_label", entry)
            self.assertNotIn("forced_result", entry)
            self.assertNotIn("terminal_reason", entry)
            self.assertNotIn("principal_variation_trace_digest", entry)
        self.assertEqual(self.factory_entries, schedule)

        self.assertEqual(len(self.agents), FOUR_BY_FOUR_CASE_COUNT)
        self.assertEqual(len({id(agent) for agent in self.agents}), 32)
        self.assertEqual([agent.depth for agent in self.agents], [5] * 32)
        self.assertEqual(
            {agent.max_nodes for agent in self.agents},
            {5_000_000},
        )
        self.assertEqual([agent.reset_calls for agent in self.agents], [1] * 32)
        self.assertTrue(all(agent.games_started == 30 for agent in self.agents))
        self.assertTrue(all(agent.roles_seen == {"A", "B"} for agent in self.agents))

        self.assertEqual(len(self.result["slots"]), 32)
        for slot in self.result["slots"]:
            evidence = slot["profile_evidence"]
            self.assertEqual(evidence["completed_seed_prefix"], list(range(30)))
            self.assertEqual([game["seed"] for game in evidence["games"]], list(range(30)))
            self.assertEqual([row["seed"] for row in slot["game_nodes"]], list(range(30)))
            before = 0
            total = 0
            for row in slot["game_nodes"]:
                self.assertEqual(row["nodes_before"], before)
                self.assertEqual(row["nodes_used"], row["nodes_after"] - before)
                self.assertGreater(row["nodes_used"], 0)
                before = row["nodes_after"]
                total += row["nodes_used"]
            self.assertEqual(slot["expanded_nodes"], total)
            self.assertEqual(slot["expanded_nodes"], before)
            self.assertIsNone(slot["incomplete_attempt"])

        self.assertEqual(
            depth_evaluation.validate_four_by_four_depth5_result(
                self.result, self.manifest, self.history, self.exact_result
            ),
            self.result,
        )

    def test_sampled_ply_limit_is_a_normal_draw_and_all_cases_are_inspected(self):
        horizon_games = [
            game
            for slot in self.result["slots"]
            for game in slot["profile_evidence"]["games"]
            if game["terminal_outcome"]["reason"] == "PLY_LIMIT"
        ]
        self.assertGreater(len(horizon_games), 0)
        self.assertTrue(
            all(
                game["terminal_outcome"]["winner"] is None
                and game["terminal_ply"] == 8
                for game in horizon_games
            )
        )
        self.assertEqual(len(self.result["inspection"]["rows"]), 32)
        self.assertEqual(
            [row["case_id"] for row in self.result["inspection"]["rows"]],
            [case["case_id"] for case in self.manifest["cases"]],
        )

    def test_node_censor_keeps_prefix_and_later_cases_continue(self):
        agents = []

        def factory(**kwargs):
            agent = _FirstLegalAgent(
                kwargs["depth"],
                kwargs["max_nodes"],
                censor_game=2 if not agents else None,
            )
            agents.append(agent)
            return agent

        result = depth_evaluation._evaluate_four_by_four_depth5(
            self.manifest,
            self.history,
            self.exact_result,
            agent_factory=factory,
            clock=_StepClock(),
        )
        self.assertEqual(len(agents), 32)
        first = result["slots"][0]
        self.assertEqual(first["status"], "INCOMPLETE_NODE_CENSOR")
        self.assertEqual(first["profile_evidence"]["completed_seed_prefix"], [0])
        self.assertEqual(first["incomplete_attempt"]["seed"], 1)
        self.assertEqual(first["incomplete_attempt"]["final_cumulative_nodes"], 5_000_000)
        self.assertEqual(first["incomplete_attempt"]["scope"], "per-candidate")
        self.assertEqual(result["slots"][1]["status"], "COMPLETED")
        self.assertEqual(result["assessment"]["status"], "INCONCLUSIVE_NODE_BUDGET")
        self.assertEqual(len(result["inspection"]["rows"]), 32)
        self.assertIn("NODE_CENSOR", result["inspection"]["rows"][0]["reasons"])
        depth_evaluation.validate_four_by_four_depth5_result(
            result, self.manifest, self.history, self.exact_result
        )

        # Reaching the cumulative cap on the prior completed game permits the
        # next seed to be censored before it completes an action.
        zero_node_slots = copy.deepcopy(result["slots"])
        first_slot = zero_node_slots[0]
        first_game_nodes = first_slot["game_nodes"][0]
        first_game_nodes["nodes_after"] = 5_000_000
        first_game_nodes["nodes_used"] = 5_000_000
        first_slot["incomplete_attempt"]["nodes_before_seed"] = 5_000_000
        first_slot["incomplete_attempt"]["nodes_consumed"] = 0
        normalized_zero = depth_evaluation._normalize_profile_slot(
            self.exact_result["cases"][0],
            result["schedule"][0],
            first_slot,
        )
        self.assertEqual(normalized_zero["incomplete_attempt"]["nodes_consumed"], 0)

        # A completed action prefix cannot consume fewer nodes than the root
        # candidates that the fixed MinimaxAgent necessarily examined.
        impossible_slots = copy.deepcopy(zero_node_slots)
        definition = self.manifest["cases"][0]["definition"]
        state = initial_state(
            calibration.validate_four_by_four_calibration_definition(definition)
        )
        prefix_action = legal_actions(
            calibration.validate_four_by_four_calibration_definition(definition),
            state,
        )[0]
        prefix_trace = depth_evaluation.derive_four_by_four_depth5_trace(
            definition, [prefix_action.to_dict()], require_terminal=False
        )
        self.assertFalse(prefix_trace["is_terminal"])
        impossible_attempt = impossible_slots[0]["incomplete_attempt"]
        impossible_attempt["completed_action_prefix"] = prefix_trace["actions"]
        impossible_attempt["trace"] = prefix_trace
        with self.assertRaisesRegex(ValueError, "incomplete .* does not reconstruct"):
            depth_evaluation._normalize_profile_slot(
                self.exact_result["cases"][0],
                result["schedule"][0],
                impossible_slots[0],
            )

    def test_factory_cannot_reuse_an_agent_and_exact_gate_precedes_factory(self):
        reused = _FirstLegalAgent(5, 5_000_000)
        with self.assertRaises(ValueError):
            depth_evaluation._evaluate_four_by_four_depth5(
                self.manifest,
                self.history,
                self.exact_result,
                agent_factory=lambda **kwargs: reused,
                clock=_StepClock(),
            )

        invalid_exact = copy.deepcopy(self.exact_result)
        invalid_exact["assessment"]["depth5_disposition"] = "BLOCKED_LABEL_COVERAGE"
        calls = []
        with self.assertRaises(ValueError):
            depth_evaluation._evaluate_four_by_four_depth5(
                self.manifest,
                self.history,
                invalid_exact,
                agent_factory=lambda **kwargs: calls.append(kwargs),
                clock=_StepClock(),
            )
        self.assertEqual(calls, [])

    def test_factory_input_mutation_stops_before_the_next_case(self):
        manifest = copy.deepcopy(self.manifest)
        agents = []

        def factory(**kwargs):
            manifest["cases"][1]["case_id"] = "poisoned-by-agent-factory"
            agent = _FirstLegalAgent(kwargs["depth"], kwargs["max_nodes"])
            agents.append(agent)
            return agent

        with self.assertRaisesRegex(ValueError, "mutated the frozen manifest"):
            depth_evaluation._evaluate_four_by_four_depth5(
                manifest,
                self.history,
                self.exact_result,
                agent_factory=factory,
                clock=_StepClock(),
            )
        self.assertEqual(len(agents), 1)
        self.assertEqual(agents[0].reset_calls, 0)
        self.assertEqual(agents[0].select_calls, 0)

    def test_invalid_agent_configuration_is_rejected_before_reset_or_select(self):
        agents = []

        def factory(**kwargs):
            agent = _FirstLegalAgent(kwargs["depth"], kwargs["max_nodes"])
            agent.max_total_nodes = True
            agents.append(agent)
            return agent

        with self.assertRaisesRegex(ValueError, "configuration is not frozen"):
            depth_evaluation._evaluate_four_by_four_depth5(
                self.manifest,
                self.history,
                self.exact_result,
                agent_factory=factory,
                clock=_StepClock(),
            )
        self.assertEqual(len(agents), 1)
        self.assertEqual(agents[0].reset_calls, 0)
        self.assertEqual(agents[0].select_calls, 0)

    def test_agent_contract_and_node_increment_remain_fixed_during_play(self):
        drifting_agents = []

        def drifting_factory(**kwargs):
            agent = _FirstLegalAgent(kwargs["depth"], kwargs["max_nodes"])
            original = agent.select_action

            def select_action(*args):
                action = original(*args)
                agent.max_total_nodes = True
                return action

            agent.select_action = select_action
            drifting_agents.append(agent)
            return agent

        with self.assertRaisesRegex(ValueError, "configuration is not frozen"):
            depth_evaluation._evaluate_four_by_four_depth5(
                self.manifest,
                self.history,
                self.exact_result,
                agent_factory=drifting_factory,
                clock=_StepClock(),
            )
        self.assertEqual(drifting_agents[0].select_calls, 1)

        stagnant_agents = []

        def stagnant_factory(**kwargs):
            agent = _FirstLegalAgent(kwargs["depth"], kwargs["max_nodes"])

            def select_action(definition, state, actions, rng):
                agent.select_calls += 1
                return actions[0]

            agent.select_action = select_action
            stagnant_agents.append(agent)
            return agent

        with self.assertRaisesRegex(ValueError, "action node accounting mismatch"):
            depth_evaluation._evaluate_four_by_four_depth5(
                self.manifest,
                self.history,
                self.exact_result,
                agent_factory=stagnant_factory,
                clock=_StepClock(),
            )
        self.assertEqual(stagnant_agents[0].select_calls, 1)

    def test_raw_and_derived_tampering_is_reconstructed_fail_closed(self):
        mutations = (
            lambda value: value["slots"][0].update({"schedule_index": True}),
            lambda value: value["slots"][0].update({"agent_identity": "poison"}),
            lambda value: value["slots"][0]["profile_evidence"]["games"][0].update(
                {"seed": True}
            ),
            lambda value: value["slots"][0]["game_nodes"][0].update(
                {"nodes_used": True}
            ),
            lambda value: value["slots"][0]["profile_evidence"]["games"][0][
                "actions"
            ][0].update({"to": [9, 9]}),
            lambda value: value["slots"][0].update({"elapsed_seconds": float("nan")}),
            lambda value: value["slots"].reverse(),
            lambda value: value["slots"].pop(),
            lambda value: value["cases"][0].update({"sampled_direction": "POISON"}),
            lambda value: value["aggregate"].update({"evidence_digest": "f" * 64}),
            lambda value: value["assessment"].update({"status": "POISON"}),
            lambda value: value["inspection"]["rows"].pop(),
            lambda value: value["timing"].update({"total_seconds": -1}),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                altered = copy.deepcopy(self.result)
                mutation(altered)
                with self.assertRaises(ValueError):
                    depth_evaluation.validate_four_by_four_depth5_result(
                        altered, self.manifest, self.history, self.exact_result
                    )

        overflowing = copy.deepcopy(self.result["slots"])
        for slot in overflowing:
            slot["elapsed_seconds"] = 1e308
        with self.assertRaises(ValueError):
            depth_evaluation.build_four_by_four_depth5_result(
                self.manifest, self.history, self.exact_result, overflowing
            )

    def test_hostile_result_copy_cannot_retime_the_upstream_exact_input(self):
        exact = copy.deepcopy(self.exact_result)

        class MutatingResult(dict):
            def items(inner_self):
                exact["timing"]["total_seconds"] += 1.0
                return super().items()

        hostile = MutatingResult(copy.deepcopy(self.result))
        with self.assertRaisesRegex(ValueError, "mutated the upstream exact result"):
            depth_evaluation.validate_four_by_four_depth5_result(
                hostile, self.manifest, self.history, exact
            )

    def test_assessment_and_breakdown_shape_are_fixed(self):
        self.assertEqual(
            self.result["assessment"]["status"],
            "SUPPORTED_4X4_DEPTH5_TRANSFER",
        )
        self.assertEqual(
            self.result["assessment"]["next_branch"],
            "PLAN_OUTCOME_BLIND_4X4_FAMILY_VIABILITY",
        )
        self.assertTrue(
            any(case["shape_failure_codes"] for case in self.result["cases"])
        )
        confusion = self.result["assessment"]["decisive_direction_confusion"]
        self.assertEqual(
            set(confusion),
            {"A_WIN", "B_WIN"},
        )
        for row in confusion.values():
            self.assertEqual(
                set(row), {"A_WIN", "B_WIN", "DRAW_OR_BALANCED", "NODE_CENSOR"}
            )
        self.assertEqual(
            set(self.result["assessment"]["exact_draw_sampled_directions"]),
            {"A_WIN", "B_WIN", "DRAW_OR_BALANCED", "NODE_CENSOR"},
        )
        self.assertEqual(
            set(self.result["aggregate"]["confusion"]["by_exact_label"]),
            {"A_WIN", "B_WIN", "HORIZON_DRAW"},
        )
        breakdowns = self.result["aggregate"]["breakdowns"]
        self.assertEqual(set(breakdowns["by_first_player"]), {"A", "B"})
        self.assertEqual(
            set(breakdowns["by_goal_axis_relation"]), {"ALIGNED", "ORTHOGONAL"}
        )
        self.assertEqual(
            set(breakdowns["by_runner_start_class"]), {"CORNER", "EDGE_INTERIOR"}
        )
        self.assertEqual(
            set(breakdowns["by_vector_band"]), {"v1_3", "v4", "v5", "v6_7"}
        )
        self.assertEqual(len(breakdowns["by_stratum"]), 32)

    def test_assessment_90_percent_draw_error_and_censor_priority(self):
        records = []
        for index, stratum_id in enumerate(depth_evaluation._ORDERED_STRATUM_IDS):
            label = (
                "A_WIN"
                if index < 10
                else "B_WIN"
                if index < 20
                else "HORIZON_DRAW"
            )
            direction = label if label != "HORIZON_DRAW" else "DRAW_OR_BALANCED"
            records.append(
                {
                    "case_index": index,
                    "case_id": "four-by-four-calibration-v1-" + stratum_id,
                    "stratum_id": stratum_id,
                    "profile_status": "COMPLETED",
                    "calibration_label": label,
                    "sampled_direction": direction,
                }
            )

        exactly_ninety = copy.deepcopy(records)
        exactly_ninety[0]["sampled_direction"] = "B_WIN"
        exactly_ninety[10]["sampled_direction"] = "A_WIN"
        assessment = depth_evaluation.assess_four_by_four_depth5_transfer(
            exactly_ninety
        )
        self.assertEqual(
            assessment["status"], "SUPPORTED_4X4_DEPTH5_TRANSFER"
        )
        self.assertEqual(
            assessment["observed"]["decisive_direction_match_count"], 18
        )
        self.assertEqual(
            assessment["observed"]["decisive_direction_accuracy"], 0.9
        )

        below = copy.deepcopy(exactly_ninety)
        below[1]["sampled_direction"] = "B_WIN"
        self.assertEqual(
            depth_evaluation.assess_four_by_four_depth5_transfer(below)["status"],
            "NOT_SUPPORTED_4X4_DEPTH5_TRANSFER",
        )

        draw_error = copy.deepcopy(records)
        draw_error[20]["sampled_direction"] = "A_WIN"
        assessed_draw = depth_evaluation.assess_four_by_four_depth5_transfer(
            draw_error
        )
        self.assertEqual(
            assessed_draw["status"], "NOT_SUPPORTED_4X4_DEPTH5_TRANSFER"
        )
        self.assertEqual(
            assessed_draw["observed"]["exact_draw_decisive_error_count"], 1
        )
        self.assertEqual(
            assessed_draw["exact_draw_decisive_error_case_ids"],
            [
                "four-by-four-calibration-v1-"
                + depth_evaluation._ORDERED_STRATUM_IDS[20]
            ],
        )

        censored = copy.deepcopy(draw_error)
        censored[0]["profile_status"] = "INCOMPLETE_NODE_CENSOR"
        censored[0]["sampled_direction"] = None
        assessed_censor = depth_evaluation.assess_four_by_four_depth5_transfer(
            censored
        )
        self.assertEqual(
            assessed_censor["status"], "INCONCLUSIVE_NODE_BUDGET"
        )
        self.assertEqual(
            assessed_censor["next_branch"], "RETIRE_PLACE_VS_MOVE_FAMILY"
        )

        insufficient = copy.deepcopy(records)
        for record in insufficient:
            record["calibration_label"] = "A_WIN"
            record["sampled_direction"] = "A_WIN"
        with self.assertRaisesRegex(ValueError, "sufficient exact labels"):
            depth_evaluation.assess_four_by_four_depth5_transfer(insufficient)

    def test_trace_terminal_flag_is_strictly_boolean(self):
        case = self.result["cases"][0]
        game = self.result["slots"][0]["profile_evidence"]["games"][0]
        with self.assertRaisesRegex(ValueError, "must be a boolean"):
            depth_evaluation.derive_four_by_four_depth5_trace(
                case["definition"], game["actions"], require_terminal=1
            )

    def test_public_signature_and_import_boundary_are_fixed(self):
        self.assertEqual(
            list(inspect.signature(depth_evaluation.four_by_four_depth5_schedule).parameters),
            ["manifest", "historical_projection", "exact_result"],
        )
        self.assertEqual(
            list(inspect.signature(depth_evaluation.evaluate_four_by_four_depth5).parameters),
            ["manifest", "historical_projection", "exact_result"],
        )
        self.assertEqual(
            list(inspect.signature(depth_evaluation.build_four_by_four_depth5_result).parameters),
            ["manifest", "historical_projection", "exact_result", "profile_slots"],
        )
        self.assertEqual(
            list(inspect.signature(depth_evaluation.validate_four_by_four_depth5_result).parameters),
            ["result", "manifest", "historical_projection", "exact_result"],
        )

        sentinel = {"fixed": "result"}
        with mock.patch.object(
            depth_evaluation,
            "_evaluate_four_by_four_depth5",
            return_value=sentinel,
        ) as executor:
            self.assertIs(
                depth_evaluation.evaluate_four_by_four_depth5(
                    self.manifest, self.history, self.exact_result
                ),
                sentinel,
            )
        _, keywords = executor.call_args
        self.assertIsNone(keywords["agent_factory"])
        self.assertIs(keywords["clock"], depth_evaluation.time.perf_counter)
        self.assertNotIn("_evaluate_four_by_four_depth5", depth_evaluation.__all__)

        script = """
import json, sys
import parity_forge.four_by_four_depth
print(json.dumps(sorted(name for name in (
    'parity_forge.play', 'parity_forge.experiments',
    'parity_forge.landscape_experiments', 'parity_forge.two_runner_experiments',
    'parity_forge.capture_boundary_experiments', 'subprocess'
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
