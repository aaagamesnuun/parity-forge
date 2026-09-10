import copy
import unittest
from itertools import product

from parity_forge.analysis import FailureCode, analyze_definition
from parity_forge.dsl import ActionKind, InitialPiece, Player, parse_definition
from parity_forge.engine import (
    Action,
    GameState,
    IllegalAction,
    action_from_dict,
    apply_action,
    initial_state,
    legal_actions,
    replay,
    replay_dicts,
)
from parity_forge.solver import solve_game

from tests.support import crossing_definition


def push_definition():
    return {
        "schema_version": 4,
        "name": "Push probe",
        "board_size": 3,
        "first_player": "A",
        "max_plies": 20,
        "roles": {
            "A": {
                "action": {
                    "kind": "PUSH",
                    "piece": "pusher",
                    "vectors": [[0, 1]],
                },
                "goal": {
                    "kind": "CONNECT_EDGES",
                    "piece": "pusher",
                    "edges": ["TOP", "BOTTOM"],
                },
            },
            "B": {
                "action": {
                    "kind": "PUSH",
                    "piece": "runner",
                    "vectors": [[1, 0]],
                },
                "goal": {
                    "kind": "CONNECT_EDGES",
                    "piece": "runner",
                    "edges": ["LEFT", "RIGHT"],
                },
            },
        },
        "initial_pieces": [
            {"owner": "A", "piece": "pusher", "position": [0, 0]},
            {"owner": "A", "piece": "pusher", "position": [1, 0]},
            {"owner": "B", "piece": "runner", "position": [1, 1]},
        ],
    }


class EngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.definition = parse_definition(crossing_definition())

    def test_initial_state_and_actions_are_deterministic(self) -> None:
        state = initial_state(self.definition)
        self.assertEqual(state.ply, 0)
        self.assertEqual(state.to_move, Player.A)
        self.assertEqual(len(legal_actions(self.definition, state)), 8)
        self.assertEqual(legal_actions(self.definition, state)[0], Action.place(0, 0))
        self.assertEqual(legal_actions(self.definition, state), legal_actions(self.definition, state))

    def test_place_then_move(self) -> None:
        state = apply_action(self.definition, initial_state(self.definition), Action.place(0, 0))
        self.assertEqual(state.to_move, Player.B)
        self.assertEqual(
            legal_actions(self.definition, state),
            (
                Action.move((2, 1), (1, 1)),
                Action.move((2, 1), (2, 0)),
                Action.move((2, 1), (2, 2)),
            ),
        )
        moved = apply_action(self.definition, state, Action.move((2, 1), (1, 1)))
        self.assertEqual(moved.ply, 2)
        self.assertEqual(moved.to_move, Player.A)

    def test_connection_goal_terminates(self) -> None:
        actions = [
            Action.place(0, 0),
            Action.move((2, 1), (2, 2)),
            Action.place(1, 0),
            Action.move((2, 2), (1, 2)),
            Action.place(2, 0),
        ]
        state = replay(self.definition, actions)
        self.assertTrue(state.terminal)
        self.assertEqual(state.outcome.winner, Player.A)
        self.assertEqual(state.outcome.reason, "GOAL")
        self.assertEqual(state.ply, 5)

    def test_reach_goal_terminates(self) -> None:
        actions = [
            Action.place(0, 0),
            Action.move((2, 1), (1, 1)),
            Action.place(2, 0),
            Action.move((1, 1), (0, 1)),
        ]
        state = replay(self.definition, actions)
        self.assertEqual(state.outcome.winner, Player.B)
        self.assertEqual(state.outcome.reason, "GOAL")

    def test_ply_limit_draw(self) -> None:
        raw = crossing_definition()
        raw["max_plies"] = 2
        definition = parse_definition(raw)
        state = replay(
            definition,
            [Action.place(0, 0), Action.move((2, 1), (1, 1))],
        )
        self.assertTrue(state.terminal)
        self.assertIsNone(state.outcome.winner)
        self.assertEqual(state.outcome.reason, "PLY_LIMIT")

    def test_schema_v2_initial_immobility_is_a_draw_but_remains_diagnostic(self) -> None:
        raw = crossing_definition()
        raw["first_player"] = "B"
        raw["roles"]["B"]["action"]["vectors"] = [[1, 0]]
        v1 = parse_definition(raw)
        v1_state = initial_state(v1)
        self.assertEqual(v1_state.outcome.winner, Player.A)
        self.assertEqual(v1_state.outcome.reason, "NO_LEGAL_ACTION")

        raw["schema_version"] = 2
        raw["terminal_policy"] = {"no_legal_action": "DRAW"}
        v2 = parse_definition(raw)
        v2_state = initial_state(v2)
        self.assertIsNone(v2_state.outcome.winner)
        self.assertEqual(v2_state.outcome.reason, "NO_LEGAL_ACTION")
        self.assertIn(
            FailureCode.NO_LEGAL_MOVE_AT_START,
            analyze_definition(v2).failure_codes,
        )

        solved = solve_game(v2)
        self.assertEqual(solved.forced_result, "DRAW")
        self.assertEqual(solved.principal_variation, ())
        self.assertEqual(solved.terminal_reason, "NO_LEGAL_ACTION")

    def test_schema_v2_post_action_immobility_is_a_draw(self) -> None:
        raw = crossing_definition()
        raw["roles"]["B"]["action"]["vectors"] = [[1, 0]]
        v1 = parse_definition(raw)
        v1_state = apply_action(v1, initial_state(v1), Action.place(0, 0))
        self.assertEqual(v1_state.outcome.winner, Player.A)
        self.assertEqual(v1_state.outcome.reason, "NO_LEGAL_ACTION")
        self.assertEqual(solve_game(v1).forced_result, "A_WIN")

        raw["schema_version"] = 2
        raw["terminal_policy"] = {"no_legal_action": "DRAW"}
        v2 = parse_definition(raw)
        v2_state = apply_action(v2, initial_state(v2), Action.place(0, 0))
        self.assertIsNone(v2_state.outcome.winner)
        self.assertEqual(v2_state.outcome.reason, "NO_LEGAL_ACTION")
        solved = solve_game(v2)
        self.assertEqual(solved.forced_result, "DRAW")
        self.assertEqual(len(solved.principal_variation), 1)
        self.assertEqual(solved.terminal_reason, "NO_LEGAL_ACTION")

    def test_schema_v2_terminal_precedence_is_goal_then_ply_then_stalemate(self) -> None:
        goal_raw = crossing_definition()
        goal_raw["schema_version"] = 2
        goal_raw["terminal_policy"] = {"no_legal_action": "DRAW"}
        goal_raw["max_plies"] = 1
        goal_raw["roles"]["B"]["action"]["vectors"] = [[1, 0]]
        goal_raw["initial_pieces"].extend(
            [
                {"owner": "A", "piece": "seed", "position": [0, 0]},
                {"owner": "A", "piece": "seed", "position": [1, 0]},
            ]
        )
        goal_definition = parse_definition(goal_raw)
        goal_state = apply_action(
            goal_definition,
            initial_state(goal_definition),
            Action.place(2, 0),
        )
        self.assertEqual(goal_state.outcome.winner, Player.A)
        self.assertEqual(goal_state.outcome.reason, "GOAL")

        ply_raw = crossing_definition()
        ply_raw["schema_version"] = 2
        ply_raw["terminal_policy"] = {"no_legal_action": "DRAW"}
        ply_raw["max_plies"] = 1
        ply_raw["roles"]["B"]["action"]["vectors"] = [[1, 0]]
        ply_definition = parse_definition(ply_raw)
        ply_state = apply_action(
            ply_definition,
            initial_state(ply_definition),
            Action.place(0, 0),
        )
        self.assertIsNone(ply_state.outcome.winner)
        self.assertEqual(ply_state.outcome.reason, "PLY_LIMIT")

    def test_illegal_action_and_action_after_terminal_are_rejected(self) -> None:
        with self.assertRaises(IllegalAction):
            apply_action(self.definition, initial_state(self.definition), Action.place(2, 1))
        terminal = replay(
            self.definition,
            [
                Action.place(0, 0),
                Action.move((2, 1), (2, 2)),
                Action.place(1, 0),
                Action.move((2, 2), (1, 2)),
                Action.place(2, 0),
            ],
        )
        with self.assertRaisesRegex(IllegalAction, "terminal"):
            apply_action(self.definition, terminal, Action.place(0, 1))

    def test_recorded_actions_replay_identically(self) -> None:
        actions = [
            Action.place(0, 0),
            Action.move((2, 1), (1, 1)),
        ]
        expected = replay(self.definition, actions)
        actual = replay_dicts(self.definition, [action.to_dict() for action in actions])
        self.assertEqual(actual, expected)
        self.assertEqual(action_from_dict(actions[1].to_dict()), actions[1])


class SchemaV4PushEngineTests(unittest.TestCase):
    def test_push_legality_matches_local_reference_for_all_3x3_occupancies(
        self,
    ) -> None:
        raw = push_definition()
        raw["initial_pieces"] = []
        raw["roles"]["A"]["action"]["vectors"] = [
            [row_delta, column_delta]
            for row_delta in (-1, 0, 1)
            for column_delta in (-1, 0, 1)
            if (row_delta, column_delta) != (0, 0)
        ]
        definition = parse_definition(raw)
        cells = tuple((row, column) for row in range(3) for column in range(3))
        checked = 0

        for origin in cells:
            other_cells = tuple(cell for cell in cells if cell != origin)
            for labels in product(range(3), repeat=len(other_cells)):
                pieces = [InitialPiece(Player.A, "pusher", origin)]
                occupied = {origin: Player.A}
                for position, label in zip(other_cells, labels):
                    if label == 1:
                        pieces.append(InitialPiece(Player.A, "block", position))
                        occupied[position] = Player.A
                    elif label == 2:
                        pieces.append(InitialPiece(Player.B, "target", position))
                        occupied[position] = Player.B
                state = GameState(
                    ply=0,
                    to_move=Player.A,
                    pieces=tuple(
                        sorted(
                            pieces,
                            key=lambda piece: (
                                piece.position,
                                piece.owner.value,
                                piece.piece,
                            ),
                        )
                    ),
                )

                expected = []
                for row_delta, column_delta in definition.role(
                    Player.A
                ).action.vectors:
                    destination = (
                        origin[0] + row_delta,
                        origin[1] + column_delta,
                    )
                    if not all(0 <= coordinate < 3 for coordinate in destination):
                        continue
                    if destination not in occupied:
                        expected.append(Action.push(origin, destination))
                        continue
                    landing = (
                        destination[0] + row_delta,
                        destination[1] + column_delta,
                    )
                    if (
                        occupied[destination] is Player.B
                        and all(0 <= coordinate < 3 for coordinate in landing)
                        and landing not in occupied
                    ):
                        expected.append(Action.push(origin, destination))

                self.assertEqual(
                    legal_actions(definition, state),
                    tuple(sorted(expected, key=Action.sort_key)),
                )
                checked += 1

        self.assertEqual(checked, 59049)

    def test_direct_action_construction_rejects_kind_and_position_spoofing(
        self,
    ) -> None:
        invalid_actions = (
            lambda: Action(  # type: ignore[arg-type]
                kind="PUSH",
                from_position=(1, 0),
                to_position=(1, 1),
            ),
            lambda: Action(
                kind=ActionKind.PUSH,
                from_position=(True, 0),
                to_position=(1, 1),
            ),
            lambda: Action(
                kind=ActionKind.PUSH,
                from_position=(1, 0),
                to_position=[1, 1],  # type: ignore[arg-type]
            ),
            lambda: Action(
                kind=ActionKind.PUSH,
                from_position=None,
                to_position=(1, 1),
            ),
            lambda: Action(
                kind=ActionKind.PLACE,
                from_position=(1, 0),
                to_position=(1, 1),
            ),
        )
        for make_action in invalid_actions:
            with self.subTest(make_action=make_action):
                with self.assertRaises(IllegalAction):
                    make_action()

    def test_action_mutation_cannot_bypass_transition_or_serialization(self) -> None:
        definition = parse_definition(push_definition())
        state = initial_state(definition)

        forged_kind = Action.push((1, 0), (1, 1))
        object.__setattr__(forged_kind, "kind", "PUSH")
        forged_position = Action.push((1, 0), (1, 1))
        object.__setattr__(forged_position, "to_position", (True, 1))

        for action in (forged_kind, forged_position):
            with self.subTest(action=action):
                with self.assertRaises(IllegalAction):
                    apply_action(definition, state, action)
                with self.assertRaises(IllegalAction):
                    action.to_dict()

    def test_action_boundaries_reject_hidden_or_missing_fields(self) -> None:
        definition = parse_definition(push_definition())
        state = initial_state(definition)
        hidden = Action.push((1, 0), (1, 1))
        object.__setattr__(hidden, "landing", (1, 2))
        missing = Action.push((1, 0), (1, 1))
        object.__delattr__(missing, "kind")
        blank = object.__new__(Action)

        for label, action in (
            ("hidden", hidden),
            ("missing", missing),
            ("blank", blank),
        ):
            with self.subTest(label=label, boundary="serialize"):
                with self.assertRaises(IllegalAction):
                    action.to_dict()
            with self.subTest(label=label, boundary="sort"):
                with self.assertRaises(IllegalAction):
                    action.sort_key()
            with self.subTest(label=label, boundary="transition"):
                with self.assertRaises(IllegalAction):
                    apply_action(definition, state, action)

    def test_push_has_ordinary_and_special_legal_transitions(self) -> None:
        definition = parse_definition(push_definition())
        state = initial_state(definition)
        ordinary = Action.push((0, 0), (0, 1))
        special = Action.push((1, 0), (1, 1))

        self.assertEqual(legal_actions(definition, state), (ordinary, special))
        self.assertTrue(
            all(
                action.kind is ActionKind.PUSH
                for action in legal_actions(definition, state)
            )
        )
        with self.assertRaisesRegex(IllegalAction, "not legal"):
            apply_action(
                definition,
                state,
                Action.move((0, 0), (0, 1)),
            )

        ordinary_state = apply_action(definition, state, ordinary)
        self.assertEqual(
            tuple(
                (piece.owner, piece.piece, piece.position)
                for piece in ordinary_state.pieces
            ),
            (
                (Player.A, "pusher", (0, 1)),
                (Player.A, "pusher", (1, 0)),
                (Player.B, "runner", (1, 1)),
            ),
        )

        special_state = apply_action(definition, state, special)
        self.assertEqual(
            tuple(
                (piece.owner, piece.piece, piece.position)
                for piece in special_state.pieces
            ),
            (
                (Player.A, "pusher", (0, 0)),
                (Player.A, "pusher", (1, 1)),
                (Player.B, "runner", (1, 2)),
            ),
        )

    def test_push_rejects_occupied_landing_boundary_friendly_and_wrong_vector(
        self,
    ) -> None:
        raw = push_definition()
        raw["board_size"] = 4
        raw["roles"]["A"]["goal"] = {
            "kind": "REACH_EDGE",
            "piece": "goal_a",
            "edge": "TOP",
        }
        raw["roles"]["B"]["goal"] = {
            "kind": "REACH_EDGE",
            "piece": "goal_b",
            "edge": "TOP",
        }
        raw["initial_pieces"] = [
            {"owner": "A", "piece": "pusher", "position": [0, 0]},
            {"owner": "B", "piece": "runner", "position": [0, 1]},
            {"owner": "A", "piece": "block", "position": [0, 2]},
            {"owner": "A", "piece": "pusher", "position": [1, 2]},
            {"owner": "B", "piece": "runner", "position": [1, 3]},
            {"owner": "A", "piece": "pusher", "position": [2, 0]},
            {"owner": "A", "piece": "block", "position": [2, 1]},
            {"owner": "A", "piece": "pusher", "position": [3, 0]},
        ]
        definition = parse_definition(raw)
        state = initial_state(definition)
        valid = Action.push((3, 0), (3, 1))
        invalid = {
            "occupied landing": Action.push((0, 0), (0, 1)),
            "off-board landing": Action.push((1, 2), (1, 3)),
            "friendly destination": Action.push((2, 0), (2, 1)),
            "undeclared vector": Action.push((3, 0), (3, 2)),
        }

        self.assertEqual(legal_actions(definition, state), (valid,))
        for label, action in invalid.items():
            with self.subTest(label=label):
                self.assertNotIn(action, legal_actions(definition, state))
                with self.assertRaisesRegex(IllegalAction, "not legal"):
                    apply_action(definition, state, action)

    def test_push_action_serialization_and_replay_preserve_kind(self) -> None:
        definition = parse_definition(push_definition())
        action = Action.push((1, 0), (1, 1))

        self.assertEqual(
            action.to_dict(),
            {"kind": "PUSH", "from": [1, 0], "to": [1, 1]},
        )
        self.assertEqual(action_from_dict(action.to_dict()), action)
        self.assertEqual(
            replay_dicts(definition, [action.to_dict()]),
            replay(definition, [action]),
        )

    def test_schema_v4_opponent_goal_precedes_ply_limit_and_stuck(self) -> None:
        raw = push_definition()
        raw["max_plies"] = 1
        raw["roles"]["A"]["goal"] = {
            "kind": "REACH_EDGE",
            "piece": "goal_a",
            "edge": "TOP",
        }
        raw["roles"]["B"]["action"] = {
            "kind": "MOVE",
            "piece": "runner",
            "vectors": [[0, 1]],
        }
        raw["roles"]["B"]["goal"] = {
            "kind": "REACH_EDGE",
            "piece": "runner",
            "edge": "RIGHT",
        }
        raw["initial_pieces"] = [
            {"owner": "A", "piece": "pusher", "position": [1, 0]},
            {"owner": "B", "piece": "runner", "position": [1, 1]},
        ]
        definition = parse_definition(raw)

        state = apply_action(
            definition,
            initial_state(definition),
            Action.push((1, 0), (1, 1)),
        )
        self.assertEqual(state.outcome.winner, Player.B)
        self.assertEqual(state.outcome.reason, "GOAL")

    def test_schema_v4_simultaneous_goals_favor_actor(self) -> None:
        raw = push_definition()
        raw["max_plies"] = 1
        raw["roles"]["B"]["action"] = {
            "kind": "MOVE",
            "piece": "runner",
            "vectors": [[0, 1]],
        }
        raw["roles"]["B"]["goal"] = {
            "kind": "REACH_EDGE",
            "piece": "runner",
            "edge": "RIGHT",
        }
        raw["initial_pieces"] = [
            {"owner": "A", "piece": "pusher", "position": [0, 1]},
            {"owner": "A", "piece": "pusher", "position": [1, 0]},
            {"owner": "B", "piece": "runner", "position": [1, 1]},
            {"owner": "A", "piece": "pusher", "position": [2, 1]},
        ]
        definition = parse_definition(raw)

        state = apply_action(
            definition,
            initial_state(definition),
            Action.push((1, 0), (1, 1)),
        )
        self.assertEqual(state.outcome.winner, Player.A)
        self.assertEqual(state.outcome.reason, "GOAL")

    def test_schema_v4_initial_goals_precede_mobility_in_turn_order(self) -> None:
        both_raw = push_definition()
        both_raw["first_player"] = "B"
        both_raw["roles"]["A"]["goal"] = {
            "kind": "REACH_EDGE",
            "piece": "pusher",
            "edge": "TOP",
        }
        both_raw["roles"]["B"]["action"] = {
            "kind": "MOVE",
            "piece": "runner",
            "vectors": [[1, 0]],
        }
        both_raw["roles"]["B"]["goal"] = {
            "kind": "REACH_EDGE",
            "piece": "runner",
            "edge": "BOTTOM",
        }
        both_raw["initial_pieces"] = [
            {"owner": "A", "piece": "pusher", "position": [0, 0]},
            {"owner": "B", "piece": "runner", "position": [2, 2]},
        ]

        both = initial_state(parse_definition(both_raw))
        self.assertEqual(both.outcome.winner, Player.B)
        self.assertEqual(both.outcome.reason, "GOAL")

        second_only_raw = copy.deepcopy(both_raw)
        second_only_raw["roles"]["B"]["goal"] = {
            "kind": "REACH_EDGE",
            "piece": "runner",
            "edge": "TOP",
        }
        second_only = initial_state(parse_definition(second_only_raw))
        self.assertEqual(second_only.outcome.winner, Player.A)
        self.assertEqual(second_only.outcome.reason, "GOAL")

    def test_schema_v4_initial_immobility_loses_after_both_goal_checks(self) -> None:
        raw = push_definition()
        raw["roles"]["A"]["goal"] = {
            "kind": "REACH_EDGE",
            "piece": "goal_a",
            "edge": "TOP",
        }
        raw["roles"]["B"]["goal"] = {
            "kind": "REACH_EDGE",
            "piece": "goal_b",
            "edge": "TOP",
        }
        raw["initial_pieces"] = [
            {"owner": "B", "piece": "runner", "position": [1, 1]},
        ]

        state = initial_state(parse_definition(raw))

        self.assertEqual(state.outcome.winner, Player.B)
        self.assertEqual(state.outcome.reason, "NO_LEGAL_ACTION")

    def test_schema_v4_ply_limit_precedes_next_player_immobility(self) -> None:
        raw = push_definition()
        raw["roles"]["A"]["goal"] = {
            "kind": "REACH_EDGE",
            "piece": "goal_a",
            "edge": "TOP",
        }
        raw["roles"]["B"]["action"] = {
            "kind": "MOVE",
            "piece": "runner",
            "vectors": [[1, 0]],
        }
        raw["roles"]["B"]["goal"] = {
            "kind": "REACH_EDGE",
            "piece": "goal_b",
            "edge": "TOP",
        }
        raw["initial_pieces"] = [
            {"owner": "A", "piece": "pusher", "position": [1, 0]},
            {"owner": "B", "piece": "runner", "position": [2, 2]},
        ]

        raw["max_plies"] = 1
        ply_definition = parse_definition(raw)
        ply_state = apply_action(
            ply_definition,
            initial_state(ply_definition),
            Action.push((1, 0), (1, 1)),
        )
        self.assertIsNone(ply_state.outcome.winner)
        self.assertEqual(ply_state.outcome.reason, "PLY_LIMIT")

        raw["max_plies"] = 2
        stuck_definition = parse_definition(raw)
        stuck_state = apply_action(
            stuck_definition,
            initial_state(stuck_definition),
            Action.push((1, 0), (1, 1)),
        )
        self.assertEqual(stuck_state.outcome.winner, Player.A)
        self.assertEqual(stuck_state.outcome.reason, "NO_LEGAL_ACTION")

    def test_schemas_v1_to_v3_keep_actor_only_goal_checks(self) -> None:
        for schema_version in (1, 2, 3):
            with self.subTest(schema_version=schema_version):
                raw = crossing_definition()
                raw["schema_version"] = schema_version
                raw["roles"]["B"]["goal"]["edge"] = "BOTTOM"
                if schema_version == 2:
                    raw["terminal_policy"] = {"no_legal_action": "DRAW"}
                elif schema_version == 3:
                    raw["roles"]["B"]["action"]["kind"] = "MOVE_CAPTURE"
                definition = parse_definition(raw)

                initial = initial_state(definition)
                self.assertFalse(initial.terminal)
                after_a_action = apply_action(
                    definition,
                    initial,
                    Action.place(0, 0),
                )
                self.assertFalse(after_a_action.terminal)


if __name__ == "__main__":
    unittest.main()
