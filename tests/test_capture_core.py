import json
import unittest

from parity_forge.analysis import FailureCode, analyze_definition
from parity_forge.asymmetry import evaluate_asymmetry
from parity_forge.dsl import (
    ActionKind,
    DefinitionError,
    Player,
    canonical_json,
    definition_hash,
    describe_rules,
    parse_definition,
)
from parity_forge.engine import (
    Action,
    IllegalAction,
    action_from_dict,
    apply_action,
    initial_state,
    legal_actions,
    replay,
    replay_dicts,
)
from parity_forge.simplicity import evaluate_simplicity, exceeds_limits
from parity_forge.solver import solve_game
from parity_forge.symmetry import D4_TRANSFORMS, d4_canonical_hash, transform_definition

from tests.support import crossing_definition


def capture_definition():
    raw = crossing_definition()
    raw["schema_version"] = 3
    raw["roles"]["B"]["action"]["kind"] = "MOVE_CAPTURE"
    return raw


def immediate_capture_goal_definition():
    raw = capture_definition()
    raw["first_player"] = "B"
    raw["max_plies"] = 1
    raw["initial_pieces"] = [
        {"owner": "A", "piece": "seed", "position": [0, 1]},
        {"owner": "B", "piece": "runner", "position": [1, 1]},
    ]
    return raw


class CaptureDslTests(unittest.TestCase):
    def test_schema_v3_is_strict_and_round_trips_canonically(self) -> None:
        definition = parse_definition(capture_definition())
        reparsed = parse_definition(json.loads(canonical_json(definition)))

        self.assertEqual(definition, reparsed)
        self.assertEqual(definition.schema_version, 3)
        self.assertIsNone(definition.terminal_policy)
        self.assertEqual(
            definition.role(Player.B).action.kind,
            ActionKind.MOVE_CAPTURE,
        )
        self.assertEqual(definition.to_dict(), reparsed.to_dict())
        self.assertEqual(
            canonical_json(definition),
            '{"board_size":3,"first_player":"A","initial_pieces":['
            '{"owner":"B","piece":"runner","position":[2,1]}],'
            '"max_plies":20,"name":"Crossing Seeds","roles":{'
            '"A":{"action":{"kind":"PLACE","piece":"seed"},"goal":{'
            '"edges":["BOTTOM","TOP"],"kind":"CONNECT_EDGES",'
            '"piece":"seed"}},"B":{"action":{"kind":"MOVE_CAPTURE",'
            '"piece":"runner","vectors":[[-1,0],[0,-1],[0,1],[1,0]]},'
            '"goal":{"edge":"TOP","kind":"REACH_EDGE",'
            '"piece":"runner"}}},"schema_version":3}',
        )
        self.assertEqual(
            definition_hash(definition),
            "8eff6699c4baa64cfd20ae3e2e9ba4fe3f5a16c1e2686ca8025fb6ba41fa59eb",
        )
        self.assertNotEqual(
            definition_hash(definition),
            definition_hash(parse_definition(crossing_definition())),
        )

        for schema_version in (1, 2):
            with self.subTest(schema_version=schema_version):
                raw = capture_definition()
                raw["schema_version"] = schema_version
                if schema_version == 2:
                    raw["terminal_policy"] = {"no_legal_action": "DRAW"}
                with self.assertRaisesRegex(
                    DefinitionError, "kind must be one of.*PLACE.*MOVE"
                ):
                    parse_definition(raw)

        no_capture = crossing_definition()
        no_capture["schema_version"] = 3
        with self.assertRaisesRegex(DefinitionError, "require.*MOVE_CAPTURE"):
            parse_definition(no_capture)

        terminal_policy = capture_definition()
        terminal_policy["terminal_policy"] = {"no_legal_action": "DRAW"}
        with self.assertRaisesRegex(DefinitionError, "unknown.*terminal_policy"):
            parse_definition(terminal_policy)

    def test_capture_prose_is_one_independent_statement(self) -> None:
        definition = parse_definition(capture_definition())
        self.assertEqual(
            describe_rules(definition),
            (
                "Use a 3 by 3 board.",
                "Start with B runner at (2, 1).",
                "A moves first; turns alternate.",
                "A places one seed in any empty cell.",
                "A wins after its action by orthogonally connecting bottom and top with seed pieces.",
                "B moves one owned runner by one of [(-1, 0), (0, -1), (0, 1), (1, 0)] to an empty in-bounds cell.",
                "B may also move that runner by one of those vectors into an in-bounds cell occupied by one opponent piece, remove that piece, and finish the move there.",
                "B wins after its action when an owned runner reaches the top edge.",
                "A player with no legal action loses.",
                "If no one wins within 20 plies, the game is a draw.",
            ),
        )


class CaptureEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.definition = parse_definition(capture_definition())

    def test_empty_moves_and_opponent_captures_keep_capture_kind(self) -> None:
        state = apply_action(
            self.definition,
            initial_state(self.definition),
            Action.place(1, 1),
        )
        self.assertEqual(
            legal_actions(self.definition, state),
            (
                Action.move_capture((2, 1), (1, 1)),
                Action.move_capture((2, 1), (2, 0)),
                Action.move_capture((2, 1), (2, 2)),
            ),
        )
        self.assertTrue(
            all(
                action.kind is ActionKind.MOVE_CAPTURE
                for action in legal_actions(self.definition, state)
            )
        )
        with self.assertRaises(IllegalAction):
            apply_action(
                self.definition,
                state,
                Action.move((2, 1), (1, 1)),
            )

    def test_capture_removes_only_the_destination_opponent(self) -> None:
        raw = capture_definition()
        raw["initial_pieces"].append(
            {"owner": "A", "piece": "seed", "position": [0, 0]}
        )
        definition = parse_definition(raw)
        state = apply_action(
            definition,
            initial_state(definition),
            Action.place(1, 1),
        )
        captured = apply_action(
            definition,
            state,
            Action.move_capture((2, 1), (1, 1)),
        )
        self.assertEqual(
            tuple(
                (piece.owner, piece.piece, piece.position)
                for piece in captured.pieces
            ),
            (
                (Player.A, "seed", (0, 0)),
                (Player.B, "runner", (1, 1)),
            ),
        )

    def test_own_occupied_destination_remains_illegal(self) -> None:
        raw = capture_definition()
        raw["initial_pieces"].append(
            {"owner": "B", "piece": "blocker", "position": [1, 1]}
        )
        definition = parse_definition(raw)
        state = apply_action(
            definition,
            initial_state(definition),
            Action.place(0, 0),
        )
        blocked = Action.move_capture((2, 1), (1, 1))
        self.assertNotIn(blocked, legal_actions(definition, state))
        with self.assertRaises(IllegalAction):
            apply_action(definition, state, blocked)

    def test_empty_capture_move_preserves_v1_transition(self) -> None:
        v1 = parse_definition(crossing_definition())
        v1_state = replay(
            v1,
            [Action.place(0, 0), Action.move((2, 1), (1, 1))],
        )
        v3_state = replay(
            self.definition,
            [
                Action.place(0, 0),
                Action.move_capture((2, 1), (1, 1)),
            ],
        )
        self.assertEqual(v3_state, v1_state)
        with self.assertRaises(IllegalAction):
            replay(
                v1,
                [
                    Action.place(0, 0),
                    Action.move_capture((2, 1), (1, 1)),
                ],
            )

    def test_capture_action_serialization_and_replay_preserve_kind(self) -> None:
        action = Action.move_capture((2, 1), (1, 1))
        self.assertEqual(
            action.to_dict(),
            {"kind": "MOVE_CAPTURE", "from": [2, 1], "to": [1, 1]},
        )
        self.assertEqual(action_from_dict(action.to_dict()), action)

        actions = [Action.place(1, 1), action]
        self.assertEqual(
            replay_dicts(
                self.definition,
                [item.to_dict() for item in actions],
            ),
            replay(self.definition, actions),
        )

    def test_schema_v3_terminal_precedence_and_v1_stalemate_semantics(self) -> None:
        goal_definition = parse_definition(immediate_capture_goal_definition())
        goal_action = Action.move_capture((1, 1), (0, 1))
        goal_state = apply_action(
            goal_definition,
            initial_state(goal_definition),
            goal_action,
        )
        self.assertEqual(goal_state.outcome.winner, Player.B)
        self.assertEqual(goal_state.outcome.reason, "GOAL")

        ply_raw = capture_definition()
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

        stalemate_raw = capture_definition()
        stalemate_raw["roles"]["B"]["action"]["vectors"] = [[1, 0]]
        stalemate_definition = parse_definition(stalemate_raw)
        stalemate_state = apply_action(
            stalemate_definition,
            initial_state(stalemate_definition),
            Action.place(0, 0),
        )
        self.assertEqual(stalemate_state.outcome.winner, Player.A)
        self.assertEqual(stalemate_state.outcome.reason, "NO_LEGAL_ACTION")


class CaptureEvaluatorIntegrationTests(unittest.TestCase):
    def test_simplicity_reports_only_the_preregistered_deltas(self) -> None:
        baseline = evaluate_simplicity(parse_definition(crossing_definition()))
        treatment = evaluate_simplicity(parse_definition(capture_definition()))

        self.assertEqual(treatment.structural.action_types, baseline.structural.action_types)
        self.assertEqual(treatment.structural.piece_types, baseline.structural.piece_types)
        self.assertEqual(
            treatment.structural.numeric_parameters,
            baseline.structural.numeric_parameters,
        )
        self.assertEqual(
            treatment.structural.action_substeps,
            baseline.structural.action_substeps,
        )
        self.assertEqual(
            treatment.structural.primitive_concepts,
            baseline.structural.primitive_concepts + 1,
        )
        self.assertEqual(
            treatment.description.independent_statements,
            baseline.description.independent_statements + 1,
        )
        self.assertEqual(
            treatment.description.conditional_clauses,
            baseline.description.conditional_clauses + 1,
        )
        self.assertEqual(
            treatment.description.learned_concepts,
            baseline.description.learned_concepts + 1,
        )
        self.assertEqual(
            treatment.operational.max_action_parameters,
            baseline.operational.max_action_parameters,
        )
        self.assertFalse(exceeds_limits(treatment))

    def test_static_and_asymmetry_treat_capture_as_movement(self) -> None:
        definition = parse_definition(capture_definition())
        static = analyze_definition(definition)
        asymmetry = evaluate_asymmetry(definition)

        self.assertNotIn(
            FailureCode.UNREACHABLE_WIN_CONDITION,
            static.failure_codes,
        )
        self.assertTrue(asymmetry.action_primitives_differ)
        self.assertTrue(asymmetry.mobility_rights_differ)
        self.assertTrue(asymmetry.qualifies)

    def test_d4_transforms_capture_vectors_and_preserves_identity(self) -> None:
        raw = capture_definition()
        raw["board_size"] = 5
        raw["initial_pieces"][0]["position"] = [4, 1]
        raw["roles"]["B"]["action"]["vectors"] = [
            [-1, -1],
            [-1, 0],
            [0, 1],
        ]
        definition = parse_definition(raw)
        baseline = d4_canonical_hash(definition)

        rotated = transform_definition(definition, "R90")
        self.assertEqual(
            rotated.role(Player.B).action.vectors,
            ((-1, 1), (0, 1), (1, 0)),
        )
        for transform in D4_TRANSFORMS:
            with self.subTest(transform=transform):
                transformed = transform_definition(definition, transform)
                self.assertEqual(
                    transformed.role(Player.B).action.kind,
                    ActionKind.MOVE_CAPTURE,
                )
                self.assertEqual(d4_canonical_hash(transformed), baseline)

    def test_capture_exact_outcome_is_d4_invariant(self) -> None:
        definition = parse_definition(immediate_capture_goal_definition())
        for transform in D4_TRANSFORMS:
            with self.subTest(transform=transform):
                solved = solve_game(transform_definition(definition, transform))
                self.assertEqual(solved.forced_result, "B_WIN")
                self.assertEqual(solved.terminal_reason, "GOAL")
                self.assertEqual(len(solved.principal_variation), 1)
                self.assertEqual(
                    solved.principal_variation[0].kind,
                    ActionKind.MOVE_CAPTURE,
                )

    def test_exact_solver_emits_a_replayable_capture(self) -> None:
        definition = parse_definition(immediate_capture_goal_definition())
        solved = solve_game(definition)

        self.assertEqual(solved.forced_result, "B_WIN")
        self.assertEqual(solved.terminal_reason, "GOAL")
        self.assertEqual(
            solved.principal_variation,
            (Action.move_capture((1, 1), (0, 1)),),
        )
        terminal = replay_dicts(
            definition,
            solved.to_dict()["principal_variation"],
        )
        self.assertEqual(terminal.outcome.winner, Player.B)
        self.assertEqual(terminal.outcome.reason, "GOAL")


if __name__ == "__main__":
    unittest.main()
