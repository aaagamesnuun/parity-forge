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
import parity_forge.four_by_four_evaluation as evaluation
from parity_forge.dsl import Edge, Player, definition_hash
from parity_forge.engine import Action, apply_action, initial_state, legal_actions
from parity_forge.four_by_four_calibration import (
    FOUR_BY_FOUR_CASE_COUNT,
    FOUR_BY_FOUR_EXACT_MAX_STATES,
    build_four_by_four_calibration_manifest,
    build_four_by_four_closed_history_projection,
    four_by_four_state_upper_bound,
)
from parity_forge.four_by_four_evaluation import (
    assess_four_by_four_exact_coverage,
    build_four_by_four_exact_result,
    derive_four_by_four_exact_trace,
    four_by_four_exact_schedule,
    validate_four_by_four_exact_evidence,
    validate_four_by_four_exact_result,
)
from parity_forge.generator import enumerate_v2_four_by_four_max8
from parity_forge.solver import SolveBudgetExceeded


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


class StepClock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        self.value += 1.0
        return self.value


class DeterministicRolloutSolver:
    """A non-minimax test double that returns one legal terminal trace."""

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
        winner = state.outcome.winner.value if state.outcome.winner else None
        forced = {"A": "A_WIN", "B": "B_WIN", None: "DRAW"}[winner]
        value = {"A_WIN": 1, "B_WIN": -1, "DRAW": 0}[forced]
        return {
            "value_for_a": value,
            "forced_result": forced,
            "principal_variation": [action.to_dict() for action in actions],
            "principal_variation_plies": len(actions),
            "terminal_reason": state.outcome.reason,
            "searched_states": len(actions) + 1,
            "cache_hits": len(actions),
        }


def _exact_payload(definition, actions, searched_states=None, cache_hits=None):
    action_dicts = [action.to_dict() for action in actions]
    trace = derive_four_by_four_exact_trace(definition, action_dicts)
    winner = trace["terminal_outcome"]["winner"]
    forced = {"A": "A_WIN", "B": "B_WIN", None: "DRAW"}[winner]
    searched_states = (
        len(action_dicts) + 1 if searched_states is None else searched_states
    )
    cache_hits = len(action_dicts) if cache_hits is None else cache_hits
    return {
        "status": "COMPLETED",
        "result": {
            "value_for_a": {"A_WIN": 1, "B_WIN": -1, "DRAW": 0}[forced],
            "forced_result": forced,
            "principal_variation": action_dicts,
            "principal_variation_plies": len(action_dicts),
            "terminal_reason": trace["terminal_outcome"]["reason"],
            "searched_states": searched_states,
            "cache_hits": cache_hits,
        },
        "budget_observation": None,
    }


def _coverage_records(labels):
    records = []
    for stratum_id, label in zip(evaluation._ORDERED_STRATUM_IDS, labels):
        forced, reason = {
            "A_WIN": ("A_WIN", "GOAL"),
            "B_WIN": ("B_WIN", "NO_LEGAL_ACTION"),
            "HORIZON_DRAW": ("DRAW", "PLY_LIMIT"),
        }[label]
        records.append(
            {
                "case_id": "four-by-four-calibration-v1-" + stratum_id,
                "stratum_id": stratum_id,
                "status": "COMPLETED",
                "forced_result": forced,
                "terminal_reason": reason,
            }
        )
    return records


class FourByFourExactEvaluationTests(unittest.TestCase):
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
        cls.rollout_solver = DeterministicRolloutSolver()
        cls.result = evaluation._evaluate_four_by_four_exact(
            cls.manifest,
            cls.history,
            solver=cls.rollout_solver,
            clock=StepClock(),
        )

        definitions = enumerate_v2_four_by_four_max8()
        cls.horizontal_a_first = next(
            definition
            for definition in definitions
            if definition.first_player is Player.A
            and definition.role(Player.A).goal.edges == (Edge.LEFT, Edge.RIGHT)
            and definition.role(Player.B).goal.edge is Edge.TOP
            and definition.initial_pieces[0].position == (3, 0)
            and set(definition.role(Player.B).action.vectors)
            == {(0, -1), (0, 1)}
        )
        cls.horizontal_b_first = next(
            definition
            for definition in definitions
            if definition.first_player is Player.B
            and definition.role(Player.A).goal.edges == (Edge.LEFT, Edge.RIGHT)
            and definition.role(Player.B).goal.edge is Edge.TOP
            and definition.initial_pieces[0].position == (3, 0)
            and set(definition.role(Player.B).action.vectors)
            == {(0, -1), (0, 1)}
        )
        cls.vertical_a_first = next(
            definition
            for definition in definitions
            if definition.first_player is Player.A
            and definition.role(Player.A).goal.edges == (Edge.LEFT, Edge.RIGHT)
            and definition.role(Player.B).goal.edge is Edge.TOP
            and definition.initial_pieces[0].position == (3, 0)
            and set(definition.role(Player.B).action.vectors) == {(-1, 0)}
        )

    def test_fixed_schedule_and_full_raw_result_reconstruct(self):
        schedule = four_by_four_exact_schedule(self.manifest, self.history)
        self.assertEqual(len(schedule), FOUR_BY_FOUR_CASE_COUNT)
        self.assertEqual(
            [entry["case_id"] for entry in schedule],
            [case["case_id"] for case in self.manifest["cases"]],
        )
        self.assertEqual(
            [call[0] for call in self.rollout_solver.calls],
            [case["definition_hash"] for case in self.manifest["cases"]],
        )
        self.assertEqual(
            {call[1] for call in self.rollout_solver.calls},
            {FOUR_BY_FOUR_EXACT_MAX_STATES},
        )

        result = self.result
        self.assertEqual(result["aggregate"]["exact_attempted"], 32)
        self.assertEqual(result["aggregate"]["exact_completed"], 32)
        self.assertEqual(result["aggregate"]["exact_censored_count"], 0)
        self.assertEqual(len(result["slots"]), 32)
        self.assertEqual(len(result["cases"]), 32)
        self.assertEqual(len(result["inspection"]["rows"]), 32)
        self.assertEqual(result["timing"]["total_seconds"], 32.0)
        self.assertEqual(len(result["aggregate"]["evidence_digest"]), 64)
        self.assertTrue(
            all("definition" in row for row in result["inspection"]["rows"])
        )
        self.assertEqual(
            validate_four_by_four_exact_result(
                result, self.manifest, self.history
            ),
            result,
        )

        retimed_slots = copy.deepcopy(result["slots"])
        for slot in retimed_slots:
            slot["elapsed_seconds"] += 0.5
        retimed = build_four_by_four_exact_result(
            self.manifest, self.history, retimed_slots
        )
        self.assertEqual(
            retimed["aggregate"]["evidence_digest"],
            result["aggregate"]["evidence_digest"],
        )
        self.assertNotEqual(retimed["timing"], result["timing"])

    def test_horizon_draw_and_decisive_goal_semantics_replay(self):
        draw_actions = (
            Action.place(0, 0),
            Action.move((3, 0), (3, 1)),
            Action.place(1, 2),
            Action.move((3, 1), (3, 0)),
            Action.place(2, 0),
            Action.move((3, 0), (3, 1)),
            Action.place(0, 2),
            Action.move((3, 1), (3, 0)),
        )
        a_win_actions = (
            Action.place(0, 0),
            Action.move((3, 0), (3, 1)),
            Action.place(0, 1),
            Action.move((3, 1), (3, 0)),
            Action.place(0, 2),
            Action.move((3, 0), (3, 1)),
            Action.place(0, 3),
        )
        b_win_actions = (
            Action.place(0, 3),
            Action.move((3, 0), (2, 0)),
            Action.place(1, 3),
            Action.move((2, 0), (1, 0)),
            Action.place(2, 3),
            Action.move((1, 0), (0, 0)),
        )
        ply8_goal_actions = (
            Action.move((3, 0), (3, 1)),
            Action.place(0, 0),
            Action.move((3, 1), (3, 0)),
            Action.place(0, 1),
            Action.move((3, 0), (3, 1)),
            Action.place(0, 2),
            Action.move((3, 1), (3, 0)),
            Action.place(0, 3),
        )
        no_legal_action = (Action.place(3, 1),)
        examples = (
            (self.horizontal_a_first, draw_actions, "DRAW", "PLY_LIMIT", 8),
            (self.horizontal_a_first, a_win_actions, "A_WIN", "GOAL", 7),
            (self.vertical_a_first, b_win_actions, "B_WIN", "GOAL", 6),
            (self.horizontal_b_first, ply8_goal_actions, "A_WIN", "GOAL", 8),
            (
                self.horizontal_a_first,
                no_legal_action,
                "A_WIN",
                "NO_LEGAL_ACTION",
                1,
            ),
        )
        for definition, actions, forced, reason, plies in examples:
            with self.subTest(forced=forced, reason=reason, plies=plies):
                validated = validate_four_by_four_exact_evidence(
                    definition, _exact_payload(definition, actions)
                )
                self.assertEqual(validated["exact"]["result"]["forced_result"], forced)
                self.assertEqual(validated["exact"]["result"]["terminal_reason"], reason)
                self.assertEqual(
                    validated["principal_variation_trace"]["terminal_ply"], plies
                )
                self.assertEqual(
                    len(validated["principal_variation_trace"]["trace_digest"]), 64
                )
        at_bound = _exact_payload(
            self.horizontal_a_first,
            draw_actions,
            searched_states=four_by_four_state_upper_bound(
                self.horizontal_a_first
            ),
        )
        validate_four_by_four_exact_evidence(
            self.horizontal_a_first, at_bound
        )

    def test_exact_evidence_rejects_forged_claims_types_and_censor(self):
        actions = (
            Action.place(0, 0),
            Action.move((3, 0), (3, 1)),
            Action.place(1, 2),
            Action.move((3, 1), (3, 0)),
            Action.place(2, 0),
            Action.move((3, 0), (3, 1)),
            Action.place(0, 2),
            Action.move((3, 1), (3, 0)),
        )
        base = _exact_payload(self.horizontal_a_first, actions)
        mutations = (
            lambda value: value["result"].update(
                {"forced_result": "A_WIN", "value_for_a": 1}
            ),
            lambda value: value["result"].update({"terminal_reason": "GOAL"}),
            lambda value: value["result"].update(
                {"principal_variation_plies": True}
            ),
            lambda value: value["result"].update({"searched_states": True}),
            lambda value: value["result"].update({"cache_hits": True}),
            lambda value: value["result"].update(
                {"searched_states": len(actions)}
            ),
            lambda value: value["result"].update(
                {"cache_hits": len(actions) - 1}
            ),
            lambda value: value["result"].update(
                {
                    "searched_states": four_by_four_state_upper_bound(
                        self.horizontal_a_first
                    )
                    + 1
                }
            ),
            lambda value: value["result"]["principal_variation"][0].update(
                {"to": [9, 9]}
            ),
            lambda value: value.update({"extra": None}),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                altered = copy.deepcopy(base)
                mutation(altered)
                with self.assertRaises(ValueError):
                    validate_four_by_four_exact_evidence(
                        self.horizontal_a_first, altered
                    )

        censor = {
            "status": "CENSORED_STATE_BUDGET",
            "result": None,
            "budget_observation": {
                "searched_states": FOUR_BY_FOUR_EXACT_MAX_STATES,
                "max_states": FOUR_BY_FOUR_EXACT_MAX_STATES,
            },
        }
        with self.assertRaisesRegex(ValueError, "structural proof"):
            validate_four_by_four_exact_evidence(
                self.horizontal_a_first, censor
            )
        censored_slots = copy.deepcopy(self.result["slots"])
        censored_slots[0]["exact"] = censor
        with self.assertRaisesRegex(ValueError, "structural proof"):
            build_four_by_four_exact_result(
                self.manifest, self.history, censored_slots
            )

        nonterminal = copy.deepcopy(base)
        nonterminal["result"]["principal_variation"].pop()
        nonterminal["result"]["principal_variation_plies"] -= 1
        with self.assertRaisesRegex(ValueError, "terminal state"):
            validate_four_by_four_exact_evidence(
                self.horizontal_a_first, nonterminal
            )

        terminal_actions = (
            Action.place(0, 0),
            Action.move((3, 0), (3, 1)),
            Action.place(0, 1),
            Action.move((3, 1), (3, 0)),
            Action.place(0, 2),
            Action.move((3, 0), (3, 1)),
            Action.place(0, 3),
        )
        terminal_then_extra = _exact_payload(
            self.horizontal_a_first, terminal_actions
        )
        terminal_then_extra["result"]["principal_variation"].append(
            Action.move((3, 1), (3, 0)).to_dict()
        )
        terminal_then_extra["result"]["principal_variation_plies"] += 1
        with self.assertRaisesRegex(ValueError, "illegal action"):
            validate_four_by_four_exact_evidence(
                self.horizontal_a_first, terminal_then_extra
            )

    def test_coverage_thresholds_are_fixed_and_complete_only(self):
        minimum_pass = _coverage_records(
            ["A_WIN"] * 7 + ["B_WIN"] * 8 + ["HORIZON_DRAW"] * 17
        )
        assessment = assess_four_by_four_exact_coverage(minimum_pass)
        self.assertEqual(assessment["status"], "SUFFICIENT_LABEL_COVERAGE")
        self.assertEqual(assessment["observed"]["decisive_count"], 15)
        self.assertEqual(assessment["depth5_disposition"], "ELIGIBLE")

        exact_a_b_floor = _coverage_records(
            ["A_WIN"] * 4 + ["B_WIN"] * 11 + ["HORIZON_DRAW"] * 17
        )
        self.assertEqual(
            assess_four_by_four_exact_coverage(exact_a_b_floor)["status"],
            "SUFFICIENT_LABEL_COVERAGE",
        )

        failures = (
            (["A_WIN"] * 3 + ["B_WIN"] * 12 + ["HORIZON_DRAW"] * 17, "A_WIN_COUNT_BELOW_4"),
            (["A_WIN"] * 12 + ["B_WIN"] * 3 + ["HORIZON_DRAW"] * 17, "B_WIN_COUNT_BELOW_4"),
            (["A_WIN"] * 7 + ["B_WIN"] * 7 + ["HORIZON_DRAW"] * 18, "DECISIVE_COUNT_BELOW_15"),
            (["A_WIN"] * 14 + ["B_WIN"] * 15 + ["HORIZON_DRAW"] * 3, "HORIZON_DRAW_COUNT_BELOW_4"),
        )
        for labels, code in failures:
            with self.subTest(code=code):
                failed = assess_four_by_four_exact_coverage(
                    _coverage_records(labels)
                )
                self.assertEqual(failed["status"], "INCONCLUSIVE_LABEL_COVERAGE")
                self.assertIn(code, failed["shortfalls"])
                self.assertEqual(
                    failed["next_branch"], "RETIRE_PLACE_VS_MOVE_FAMILY"
                )

        censored = _coverage_records(
            ["A_WIN"] * 7 + ["B_WIN"] * 8 + ["HORIZON_DRAW"] * 17
        )
        censored[0].update(
            {"status": "CENSORED_STATE_BUDGET", "forced_result": None, "terminal_reason": None}
        )
        with self.assertRaises(ValueError):
            assess_four_by_four_exact_coverage(censored)
        reordered = list(reversed(minimum_pass))
        with self.assertRaisesRegex(ValueError, "frozen strata"):
            assess_four_by_four_exact_coverage(reordered)

    def test_state_censor_and_solver_error_stop_before_the_next_case(self):
        calls = []

        def censor_solver(definition, *, max_states):
            calls.append(definition_hash(definition))
            raise SolveBudgetExceeded(max_states, max_states)

        with self.assertRaises(SolveBudgetExceeded):
            evaluation._evaluate_four_by_four_exact(
                self.manifest,
                self.history,
                solver=censor_solver,
                clock=StepClock(),
            )
        self.assertEqual(len(calls), 1)

        calls.clear()

        def broken_solver(definition, *, max_states):
            calls.append(definition_hash(definition))
            raise RuntimeError("solver defect")

        with self.assertRaisesRegex(RuntimeError, "solver defect"):
            evaluation._evaluate_four_by_four_exact(
                self.manifest,
                self.history,
                solver=broken_solver,
                clock=StepClock(),
            )
        self.assertEqual(len(calls), 1)

        calls.clear()

        def malformed_solver(definition, *, max_states):
            calls.append(definition_hash(definition))
            return {"not": "SolveResult evidence"}

        with self.assertRaises(ValueError):
            evaluation._evaluate_four_by_four_exact(
                self.manifest,
                self.history,
                solver=malformed_solver,
                clock=StepClock(),
            )
        self.assertEqual(len(calls), 1)

    def test_result_validator_rejects_raw_and_derived_tampering(self):
        mutations = (
            lambda value: value.update({"result_version": True}),
            lambda value: value["slots"][0].update({"schedule_index": True}),
            lambda value: value["slots"][0].update({"case_index": True}),
            lambda value: value["slots"][0].update({"elapsed_seconds": True}),
            lambda value: value["slots"].reverse(),
            lambda value: value["slots"].pop(),
            lambda value: value["slots"].__setitem__(1, value["slots"][0]),
            lambda value: value["slots"][0]["exact"]["result"].update(
                {"searched_states": True}
            ),
            lambda value: value["slots"][0].update({"unknown": None}),
            lambda value: value["cases"][0].update({"forced_result": "POISON"}),
            lambda value: value["aggregate"].update({"evidence_digest": "f" * 64}),
            lambda value: value["assessment"].update(
                {"status": "POISON"}
            ),
            lambda value: value["inspection"]["rows"].pop(),
            lambda value: value["timing"].update({"total_seconds": -1}),
            lambda value: value.update({"outcome": "A_WIN"}),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                altered = copy.deepcopy(self.result)
                mutation(altered)
                with self.assertRaises(ValueError):
                    validate_four_by_four_exact_result(
                        altered, self.manifest, self.history
                    )

        altered = copy.deepcopy(self.result)
        altered["slots"][0]["elapsed_seconds"] = float("nan")
        with self.assertRaises(ValueError):
            validate_four_by_four_exact_result(
                altered, self.manifest, self.history
            )

        overflowing_slots = copy.deepcopy(self.result["slots"])
        for slot in overflowing_slots:
            slot["elapsed_seconds"] = 1e308
        with self.assertRaisesRegex(ValueError, "total timing"):
            build_four_by_four_exact_result(
                self.manifest, self.history, overflowing_slots
            )

        resigned = copy.deepcopy(self.result)
        first_result = resigned["slots"][0]["exact"]["result"]
        if first_result["forced_result"] == "A_WIN":
            first_result.update({"forced_result": "B_WIN", "value_for_a": -1})
        else:
            first_result.update({"forced_result": "A_WIN", "value_for_a": 1})
        resigned["aggregate"]["evidence_digest"] = evaluation._exact_slots_digest(
            resigned["slots"]
        )
        with self.assertRaises(ValueError):
            validate_four_by_four_exact_result(
                resigned, self.manifest, self.history
            )

    def test_manifest_and_history_mutation_or_replacement_fail_before_solver(self):
        poisoned = copy.deepcopy(self.manifest)
        poisoned["cases"][0]["outcome"] = "DRAW"
        calls = []

        def solver(definition, *, max_states):
            calls.append(definition_hash(definition))
            raise AssertionError("must not run")

        with self.assertRaises(ValueError):
            evaluation._evaluate_four_by_four_exact(
                poisoned, self.history, solver=solver, clock=StepClock()
            )
        self.assertEqual(calls, [])

        def replace_cases(manifest, history):
            return tuple(reversed(manifest["cases"]))

        with mock.patch.object(
            evaluation,
            "validate_four_by_four_calibration_manifest",
            side_effect=replace_cases,
        ), self.assertRaisesRegex(ValueError, "replaced"):
            four_by_four_exact_schedule(self.manifest, self.history)

        mutated_manifest = copy.deepcopy(self.manifest)

        def mutate_manifest(manifest, history):
            manifest["cases"].reverse()
            return tuple(manifest["cases"])

        with mock.patch.object(
            evaluation,
            "validate_four_by_four_calibration_manifest",
            side_effect=mutate_manifest,
        ), self.assertRaisesRegex(ValueError, "mutated"):
            four_by_four_exact_schedule(mutated_manifest, self.history)

        mutated_history = copy.deepcopy(self.history)

        def mutate_history(manifest, history):
            history["source_count"] = 0
            return tuple(manifest["cases"])

        with mock.patch.object(
            evaluation,
            "validate_four_by_four_calibration_manifest",
            side_effect=mutate_history,
        ), self.assertRaisesRegex(ValueError, "closed-history"):
            four_by_four_exact_schedule(self.manifest, mutated_history)

    def test_solver_cannot_mutate_inputs_between_slots(self):
        manifest = copy.deepcopy(self.manifest)
        calls = []

        def mutating_solver(definition, *, max_states):
            calls.append(definition_hash(definition))
            manifest["cases"][1]["case_id"] = "poisoned"
            return DeterministicRolloutSolver()(definition, max_states=max_states)

        with self.assertRaisesRegex(ValueError, "solver mutated"):
            evaluation._evaluate_four_by_four_exact(
                manifest,
                self.history,
                solver=mutating_solver,
                clock=StepClock(),
            )
        self.assertEqual(len(calls), 1)

        history = copy.deepcopy(self.history)
        calls.clear()

        def history_mutating_solver(definition, *, max_states):
            calls.append(definition_hash(definition))
            history["source_count"] = 0
            raise RuntimeError("solver failed after history mutation")

        with self.assertRaisesRegex(ValueError, "closed-history"):
            evaluation._evaluate_four_by_four_exact(
                self.manifest,
                history,
                solver=history_mutating_solver,
                clock=StepClock(),
            )
        self.assertEqual(len(calls), 1)

    def test_injected_conversion_and_clock_cannot_hide_input_mutation(self):
        manifest = copy.deepcopy(self.manifest)
        calls = []

        class MutatingResult:
            def to_dict(self):
                manifest["cases"][1]["case_id"] = "poisoned-by-conversion"
                raise RuntimeError("conversion failed")

        def conversion_solver(definition, *, max_states):
            calls.append(definition_hash(definition))
            return MutatingResult()

        with self.assertRaisesRegex(ValueError, "solver mutated"):
            evaluation._evaluate_four_by_four_exact(
                manifest,
                self.history,
                solver=conversion_solver,
                clock=StepClock(),
            )
        self.assertEqual(len(calls), 1)

        manifest = copy.deepcopy(self.manifest)
        calls.clear()
        clock_calls = 0

        def second_call_mutating_clock():
            nonlocal clock_calls
            clock_calls += 1
            if clock_calls == 2:
                manifest["cases"][1]["case_id"] = "poisoned-by-clock"
            return float(clock_calls)

        def solver(definition, *, max_states):
            calls.append(definition_hash(definition))
            return DeterministicRolloutSolver()(definition, max_states=max_states)

        with self.assertRaisesRegex(ValueError, "solver mutated"):
            evaluation._evaluate_four_by_four_exact(
                manifest,
                self.history,
                solver=solver,
                clock=second_call_mutating_clock,
            )
        self.assertEqual(len(calls), 1)

    def test_public_surface_is_fixed_and_import_has_no_agent_or_filesystem_edge(self):
        signature = inspect.signature(evaluation.evaluate_four_by_four_exact)
        self.assertEqual(list(signature.parameters), ["manifest", "historical_projection"])

        expected = {"fixed": "result"}
        with mock.patch.object(
            evaluation, "_evaluate_four_by_four_exact", return_value=expected
        ) as executor:
            self.assertIs(
                evaluation.evaluate_four_by_four_exact(self.manifest, self.history),
                expected,
            )
        _, keywords = executor.call_args
        self.assertIs(keywords["solver"], evaluation.solve_game)
        self.assertIs(keywords["clock"], evaluation.time.perf_counter)

        script = """
import json, sys
import parity_forge.four_by_four_evaluation
print(json.dumps(sorted(name for name in (
    'parity_forge.agents', 'parity_forge.play', 'parity_forge.experiments',
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
