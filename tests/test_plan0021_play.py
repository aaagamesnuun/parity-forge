"""Injected terminal I/O on artificial 3x3 wires only; never play proposal data."""

import unittest
from unittest import mock

from parity_forge.agents import SearchBudgetExceeded
from parity_forge.terminal_search import TerminalOnlyMinimaxAgent
from scripts import plan0021_play as console


def tiny(loop=False):
    return {"schema_version": 4, "name": "console-calibration", "board_size": 3,
            "first_player": "A", "max_plies": 5 if loop else 1,
            "roles": {role: {"action": {"kind": "SWAP" if loop else kind, "piece": role.lower(),
                                         "vectors": [[0, -1], [0, 1]] if loop else vectors},
                             "goal": {"kind": "REACH_EDGE", "piece": role.lower(), "edge": edge}}
                      for role, kind, vectors, edge in (("A", "MOVE_CAPTURE", [[1, 0]], "BOTTOM"),
                                                       ("B", "HOP", [[-1, 0]], "TOP"))},
            "initial_pieces": [{"owner": "A", "piece": "a", "position": [1, 0]},
                               {"owner": "B", "piece": "b", "position": [1, 1] if loop else [2, 2]}]}


class ConsoleTests(unittest.TestCase):
    def test_human_move_invalid_input_and_last_ply_goal(self):
        answers, output = iter(("bad", "0", "99", "1")), []
        result = console.play_console(tiny(), input_fn=lambda _: next(answers), output_fn=output.append)
        self.assertEqual(result, {"status": "COMPLETE", "winner": "A", "terminal_reason": "GOAL", "plies": 1})
        self.assertEqual(sum("番号、またはq" in line for line in output), 3)
        self.assertIn("1: (2,1) → (3,1)", output)

    def test_quit_eof_and_ai_budget_are_interruptions_without_winner(self):
        for input_fn in (lambda _: "q", mock.Mock(side_effect=EOFError)):
            output = []
            result = console.play_console(tiny(), input_fn=input_fn, output_fn=output.append)
            self.assertEqual((result["status"], result["winner"], result["terminal_reason"]), ("ABORTED", None, None))
            self.assertIn("中断", output[-1])
        with mock.patch.object(console, "TerminalOnlyMinimaxAgent") as factory:
            factory.return_value.select_action.side_effect = SearchBudgetExceeded("per-slot", 20000, 20000)
            result = console.play_console(tiny(), human="B", input_fn=mock.Mock(side_effect=AssertionError), output_fn=lambda _: None)
        self.assertEqual((result["status"], result["winner"], result["plies"]), ("ABORTED", None, 0))
        factory.assert_called_once_with(3, 20000)

    def test_fresh_ai_per_decision_and_seed_zero_reproducibility(self):
        outputs = []
        for _ in range(2):
            output = []
            with mock.patch.object(console, "TerminalOnlyMinimaxAgent", wraps=TerminalOnlyMinimaxAgent) as factory:
                result = console.play_console(tiny(loop=True), input_fn=lambda _: "1", output_fn=output.append)
            self.assertEqual(factory.call_args_list, [mock.call(3, 20000), mock.call(3, 20000)])
            self.assertEqual(result["status"], "TERMINAL_WITHOUT_WINNER")
            self.assertEqual(result["terminal_reason"], "PLY_LIMIT")
            outputs.append(output)
        self.assertEqual(*outputs)

    def test_cli_loads_selected_first_and_default_human_without_play(self):
        a, b = tiny(), tiny()
        b["first_player"] = "B"
        with mock.patch("scripts.plan0021_pilot.load_definitions", return_value=[a, b]) as load, \
                mock.patch.object(console, "play_console") as play:
            console.main(["--first", "B"])
            play.assert_called_once_with(b, "A")
            load.assert_called_once()
        with mock.patch("scripts.plan0021_pilot.load_definitions", return_value=[a, b]), \
                mock.patch.object(console, "play_console") as play:
            console.main(["--first", "A", "--human", "B"])
            play.assert_called_once_with(a, "B")


if __name__ == "__main__":
    unittest.main()
