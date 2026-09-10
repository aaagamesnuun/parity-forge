"""Local, unsaved terminal play; never part of an experimental game schedule."""

import argparse
from pathlib import Path
import random

from parity_forge.agents import SearchBudgetExceeded
from parity_forge.dsl import Player, parse_definition
from parity_forge.engine import apply_action, initial_state, legal_actions
from parity_forge.terminal_search import TerminalOnlyMinimaxAgent


def _action_label(action):
    target = "({},{})".format(*(v + 1 for v in action.to_position))
    source = "({},{}) → ".format(*(v + 1 for v in action.from_position)) if action.from_position else ""
    return source + target


def play_console(raw, human="A", *, input_fn=input, output_fn=print):
    """Play one supplied wire. The AI gets a fresh depth-3/20,000-node budget."""
    human = Player(human)
    definition, rng = parse_definition(raw), random.Random(0)
    state = initial_state(definition)

    def interrupted(reason):
        output_fn("中断：" + reason + "。勝敗は記録しません。")
        return {"status": "ABORTED", "winner": None, "terminal_reason": None,
                "plies": state.ply, "reason": reason}

    output_fn("あなたは{}、AIは{}。座標は（行,列）、番号で選択、qで中断。".format(human.value, human.other.value))
    while True:
        occupied = {p.position: p.owner.value for p in state.pieces}
        output_fn("    " + " ".join(str(c + 1) for c in range(definition.board_size)))
        for row in range(definition.board_size):
            output_fn("{} | {}".format(row + 1, " ".join(occupied.get((row, col), ".") for col in range(definition.board_size))))
        if state.terminal:
            winner = state.outcome.winner
            reason = {"GOAL": "目標到達", "NO_LEGAL_ACTION": "相手が行動不能", "PLY_LIMIT": "手数上限"}.get(state.outcome.reason, state.outcome.reason)
            output_fn("{}（{}）".format(winner.value + "の勝ち" if winner else "勝者のない終端", reason))
            return {"status": "COMPLETE" if winner else "TERMINAL_WITHOUT_WINNER",
                    "winner": winner.value if winner else None, "terminal_reason": state.outcome.reason, "plies": state.ply}
        choices = legal_actions(definition, state)
        if not choices:
            return interrupted("非終端なのに合法手がありません")
        output_fn("{}の手番".format(state.to_move.value))
        if state.to_move is human:
            for index, action in enumerate(choices, 1):
                output_fn("{}: {}".format(index, _action_label(action)))
            while True:
                try:
                    text = input_fn("手の番号（qで中断）: ").strip()
                except (EOFError, KeyboardInterrupt):
                    return interrupted("入力が終了しました")
                if text.lower() == "q":
                    return interrupted("利用者が終了しました")
                try:
                    index = int(text)
                except ValueError:
                    index = 0
                if 1 <= index <= len(choices):
                    action = choices[index - 1]
                    break
                output_fn("1〜{}の番号、またはqを入力してください。".format(len(choices)))
        else:
            try:
                agent = TerminalOnlyMinimaxAgent(3, 20000)
                action = agent.select_action(definition, state, choices, rng)
            except SearchBudgetExceeded:
                return interrupted("AIが今回の判断の計算上限20,000ノードに達しました")
            except KeyboardInterrupt:
                return interrupted("AIの計算を中断しました")
            if action not in choices:
                return interrupted("AIの選択が合法手ではありません")
            output_fn("AI: " + _action_label(action))
        state = apply_action(definition, state, action)


def main(argv=None):
    from scripts.plan0021_pilot import load_definitions
    parser = argparse.ArgumentParser(description="捕獲役Aと飛び越し役Bの端末試遊（保存なし）")
    parser.add_argument("--first", choices=("A", "B"), required=True)
    parser.add_argument("--human", choices=("A", "B"), default="A")
    args = parser.parse_args(argv)
    rows = load_definitions(Path(__file__).resolve().parents[1])
    raw = next(row for row in rows if row["first_player"] == args.first)
    play_console(raw, args.human)


if __name__ == "__main__":
    main()
