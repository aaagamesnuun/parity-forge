import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from parity_forge import connection_batch as batch
from parity_forge.connection import (
    Action, action_to_dict, apply_action, initial_state, parse_definition, state_to_dict,
)
from parity_forge.connection_search import Selection


def definition_fixture(first="A"):
    return parse_definition({"format": "parity-forge:connection:v1", "id": "synthetic",
                             "board": {"size": 3, "topology": "RHOMBUS_HEX_CELLS"},
                             "first_player": first, "bridge_credits_A": 3,
                             "conversion_credits_B": 2,
                             "terminal_rule": "OPPOSITE_EDGE_CONNECTION"})


def trace_fixture(conversion=False):
    definition = definition_fixture()
    state = initial_state(definition)
    moves = ([Action("PLACE_ONE", (4,)), Action("PLACE_AND_CONVERT", (1, 4)),
              Action("BRIDGE_PAIR", (6, 7)), Action("PLACE_AND_CONVERT", (8, 7))]
             if conversion else [Action("PLACE_ONE", (c,)) for c in (0, 6, 1, 7, 2)])
    states, actions = [state_to_dict(definition, state)], []
    for action in moves:
        state = apply_action(definition, state, action)
        actions.append(action_to_dict(definition, action))
        states.append(state_to_dict(definition, state))
    return definition, {"actions": actions, "states": states, "plies": len(actions),
                        "winner": state.winner.value, "final_state": states[-1]}


def manifest_fixture():
    return {"format": batch.FORMAT, "registration_sha256": batch.REGISTRATION_SHA256,
            "registration": batch.registered_input(), "source_hashes": batch.source_hashes(),
            "acceptance_path": batch.ACCEPTANCE_PATH, "acceptance_sha256": "f" * 64}


class ConnectionBatchTests(unittest.TestCase):
    def test_strict_json_duplicate_nonfinite_and_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.json"
            for value in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}'):
                path.write_text(value)
                with self.assertRaises(ValueError):
                    batch.load_json(path)
            path.write_text('{"a":1}')
            self.assertEqual(batch.load_json(path), {"a": 1})
            for limit in (True, 0, 2, 16777217):
                with self.assertRaises(ValueError):
                    batch.load_json(path, limit)

    def test_exact_registration_rejects_every_component_mutation(self):
        registration = batch.registered_input()
        self.assertEqual(len(batch.validate_registration(registration)), 2)
        for key in registration:
            changed = copy.deepcopy(registration)
            changed[key] = None
            with self.subTest(key=key), self.assertRaises(ValueError):
                batch.validate_registration(changed)
        changed = copy.deepcopy(registration)
        changed["limits"]["batches"] = True
        with self.assertRaises(ValueError):
            batch.validate_registration(changed)

    def test_schedule_order_is_profile_seed_then_first_a_b(self):
        registration = batch.registered_input()
        definitions = batch.validate_registration(registration)
        rows = list(batch.scheduled_games(registration, definitions))
        self.assertEqual(len(rows), 16)
        self.assertEqual([(d.first_player.value, p["label"], s) for d, p, s in rows[:4]],
                         [("A", "search-self", 40000), ("B", "search-self", 40000),
                          ("A", "search-self", 40001), ("B", "search-self", 40001)])
        self.assertEqual(len({(d.id, p["A"], p["B"], s) for d, p, s in rows}), 16)

    def test_all_old_pins_and_six_new_pins(self):
        batch.verify_old_pins()
        self.assertEqual(set(batch.source_hashes()), set(batch.SOURCE_PATHS))
        self.assertEqual(len(batch.source_hashes()), 6)

    def test_manifest_requires_current_source_and_actual_acceptance(self):
        manifest = manifest_fixture()
        with patch.object(batch, "validate_acceptance", return_value="f" * 64):
            self.assertEqual(len(batch.validate_manifest(manifest)), 2)
            for key, value in (("source_hashes", {}), ("acceptance_sha256", "x"),
                               ("registration_sha256", "x"), ("acceptance_path", "other")):
                invalid = copy.deepcopy(manifest)
                invalid[key] = value
                with self.subTest(key=key), self.assertRaises(ValueError):
                    batch.validate_manifest(invalid)
        with patch.object(batch, "validate_acceptance", side_effect=ValueError("not completed")):
            with self.assertRaises(ValueError):
                batch.validate_manifest(manifest)

    def test_acceptance_binds_log_exit_sources_and_observed_process(self):
        pins = {"synthetic-source": "x"}
        with tempfile.TemporaryDirectory() as directory, patch.object(batch, "REPOSITORY", Path(directory)):
            evidence = Path(directory) / batch.EVIDENCE_ROOT
            evidence.mkdir(parents=True)
            log = b"Ran 1504 tests in 12.345s\n\nOK (skipped=2)\n"
            (evidence / "full-suite.log").write_bytes(log)
            (evidence / "full-suite.exit").write_bytes(b"0\n")
            receipt = {"kind": "observed_full_regression_completion", "plan": "0040",
                       "command": batch.FULL_COMMAND, "actual_session_exit_code": 0,
                       "source_hashes": pins, "source_changed_after_freeze": False,
                       "old_source_pin_file_sha256": batch.OLD_PINS_SHA256,
                       "independent_source_review": "PASS", "focused_tests": "PASS",
                       "tests_run": 1504, "actual_session_completion_chunk": "synthetic",
                       "summary": "OK (skipped=2)", "log": batch.EVIDENCE_ROOT + "/full-suite.log",
                       "log_sha256": batch._digest(log),
                       "exit_file": batch.EVIDENCE_ROOT + "/full-suite.exit",
                       "exit_file_sha256": batch._digest(b"0\n")}
            path = Path(directory) / batch.ACCEPTANCE_PATH
            path.write_text(json.dumps(receipt))
            self.assertEqual(batch.validate_acceptance(pins), batch._digest(path.read_bytes()))
            for key, value in (("actual_session_exit_code", False), ("source_hashes", {}),
                               ("actual_session_completion_chunk", ""), ("summary", "FAILED"),
                               ("tests_run", 1503), ("log_sha256", "x")):
                changed = dict(receipt, **{key: value})
                path.write_text(json.dumps(changed))
                with self.subTest(key=key), self.assertRaises(ValueError):
                    batch.validate_acceptance(pins)

    def test_reference_independent_single_and_conversion_ending(self):
        for convert in (False, True):
            definition, game = trace_fixture(convert)
            with patch.object(batch, "apply_action", side_effect=AssertionError("must not reuse core")):
                self.assertEqual(batch.reference_replay(definition, game), game["plies"])
            self.assertEqual(game["winner"], "B" if convert else "A")
            self.assertEqual(game["final_state"]["to_move"], game["winner"])

    def test_reference_checks_every_prefix_and_conversion_order(self):
        definition, game = trace_fixture(True)
        altered = []
        value = copy.deepcopy(game); value["states"][1]["bridge_left"] = 0; altered.append(value)
        value = copy.deepcopy(game); value["states"][2]["a"] = [[1, 1]]; altered.append(value)
        value = copy.deepcopy(game); value["actions"][-1]["cells"].reverse(); altered.append(value)
        value = copy.deepcopy(game); value["states"][0]["plies"] = False; altered.append(value)
        value = copy.deepcopy(game); value["final_state"]["winner"] = "A"; altered.append(value)
        value = copy.deepcopy(game); value["actions"].append(value["actions"][0]); value["states"].append(value["states"][-1]); altered.append(value)
        for value in altered:
            with self.assertRaises(ValueError):
                batch.reference_replay(definition, value)
        with self.assertRaises(batch.ReplayInterrupted) as caught:
            batch.reference_replay(definition, game, lambda: True)
        self.assertEqual(caught.exception.transitions, 0)

    def test_game_records_mocked_actions_and_replays_once(self):
        definition, expected = trace_fixture()
        selections = [Selection(Action("PLACE_ONE", (c,)), 1, 3, False, False, False)
                      for c in (0, 6, 1, 7, 2)]
        with patch.object(batch, "select_action", side_effect=selections), patch.object(
                batch, "reference_replay", wraps=batch.reference_replay) as replay:
            game = batch.play_game(definition, {"label": "synthetic", "A": "random-v1", "B": "random-v1"},
                                   12, batch.registered_input()["search"])
        self.assertEqual(game["status"], "COMPLETE")
        self.assertEqual(game["actions"], expected["actions"])
        self.assertEqual(game["search_transitions"], 15)
        self.assertEqual(game["actual_applied_game_actions"], 5)
        self.assertEqual(game["reference_replay_transitions"], 5)
        replay.assert_called_once()

    def test_compute_limits_are_unknown_and_unapplied(self):
        definition, search = definition_fixture(), batch.registered_input()["search"]
        profile = {"label": "synthetic", "A": "random-v1", "B": "random-v1"}
        for cpu, limits, selection in (
                (lambda: True, search, None),
                (lambda: False, dict(search, max_search_transitions_per_game=0), None),
                (lambda: False, search, Selection(None, 1, 4, False, False, True))):
            with patch.object(batch, "select_action", return_value=selection):
                game = batch.play_game(definition, profile, 1, limits, cpu)
            self.assertEqual((game["status"], game["winner"], game["plies"]), ("UNKNOWN", None, 0))
        with patch.object(batch, "select_action", return_value=Selection(Action("PLACE_ONE", (0,)), 1, 32769, False, False, False)):
            game = batch.play_game(definition, profile, 1, search)
        self.assertEqual(game["status"], "FAILED_TECHNICAL")

    def test_empty_cpu_preserves_all_scheduled_slots_without_policy_calls(self):
        registration = batch.registered_input()
        with patch.object(batch, "play_game", side_effect=AssertionError("no game allowed")):
            report = batch.evaluate(registration, batch.validate_registration(registration), lambda: True)
        self.assertEqual(len(report["games"]), 16)
        self.assertTrue(all(g["status"] == "NOT_STARTED" for g in report["games"]))
        self.assertFalse(any(report["quality_flags"].values()))

    def test_output_budget_is_cumulative_and_exclusive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            budget = batch.OutputBudget(15)
            budget.save(root / "one.json", {"a": 1})
            with self.assertRaises(FileExistsError):
                budget.save(root / "one.json", {})
            with self.assertRaises(ValueError):
                budget.save(root / "two.json", {"a": 1})
            self.assertFalse((root / "two.json").exists())
            self.assertLessEqual(budget.used, 15)

    def test_run_claim_is_exclusive_and_failure_preserves_no_retry(self):
        manifest = manifest_fixture()
        for failure in (False, True):
            with tempfile.TemporaryDirectory() as directory, patch.object(batch, "REPOSITORY", Path(directory)), patch.object(
                    batch, "validate_manifest", return_value=()), patch.object(batch, "_install_cpu_limit"), patch.object(
                    batch, "source_hashes", return_value=manifest["source_hashes"]), patch.object(batch, "verify_old_pins"), patch.object(
                    batch, "evaluate", side_effect=ValueError("synthetic failure") if failure else None,
                    return_value={"games": [], "quality_flags": dict(batch.QUALITY)}) as evaluate:
                if failure:
                    with self.assertRaises(ValueError):
                        batch.run_batch(manifest)
                else:
                    batch.run_batch(manifest)
                output = Path(directory) / manifest["registration"]["execution"]["output"]
                claim = Path(directory) / manifest["registration"]["execution"]["claim"]
                self.assertTrue(claim.exists())
                self.assertTrue((output / ("failure.json" if failure else "runtime.json")).exists())
                before = claim.read_bytes()
                with self.assertRaises(FileExistsError):
                    batch.run_batch(manifest)
                self.assertEqual(claim.read_bytes(), before)
                evaluate.assert_called_once()

    def test_path_alias_and_parent_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(batch, "REPOSITORY", Path(directory)):
            root = Path(directory)
            (root / "real").mkdir()
            (root / "alias").symlink_to(root / "real", target_is_directory=True)
            for path in ("../escape", "/absolute", "alias/child"):
                with self.assertRaises(ValueError):
                    batch._path(path)

    def test_lower_inherited_cpu_limit_is_rejected_before_claim(self):
        with patch.object(batch.resource, "getrlimit", return_value=(100, 100)), patch.object(
                batch.resource, "setrlimit") as install:
            with self.assertRaisesRegex(ValueError, "inherited CPU"):
                batch._install_cpu_limit(14400)
            install.assert_not_called()
        with patch.object(batch.resource, "getrlimit", return_value=(20000, 20000)), patch.object(
                batch.resource, "setrlimit") as install, patch.object(batch.time, "process_time", return_value=0):
            batch._install_cpu_limit(14400)
            install.assert_called_once_with(batch.resource.RLIMIT_CPU, (14400, 14400))


if __name__ == "__main__":
    unittest.main()
