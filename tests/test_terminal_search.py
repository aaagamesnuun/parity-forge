import ast
import random
import unittest
from pathlib import Path

from parity_forge.agents import AgentIdentity, SearchBudgetExceeded
from parity_forge.dsl import InitialPiece, Player, parse_definition
from parity_forge.engine import (
    Action,
    GameState,
    Outcome,
    apply_action,
    goal_satisfied,
    initial_state,
    legal_actions,
)
from parity_forge.symmetry import (
    D4_TRANSFORMS,
    transform_definition,
    transform_position,
)
from parity_forge.terminal_search import (
    TERMINAL_ONLY_MINIMAX_MAX_DEPTH,
    TerminalOnlyMinimaxAgent,
)

from tests.support import crossing_definition
from tests.test_agency_benchmark import FIXTURE_BY_ID


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "parity_forge"
    / "terminal_search.py"
)


def _fixture_definition(fixture_id):
    return parse_definition(FIXTURE_BY_ID[fixture_id]["definition"])


def _simultaneous_connect_definition():
    return parse_definition(
        {
            "schema_version": 4,
            "name": "Terminal-only simultaneous connect v1",
            "board_size": 3,
            "first_player": "A",
            "max_plies": 1,
            "roles": {
                "A": {
                    "action": {
                        "kind": "SWAP",
                        "piece": "a",
                        "vectors": [[0, 1]],
                    },
                    "goal": {
                        "kind": "CONNECT_EDGES",
                        "piece": "a",
                        "edges": ["BOTTOM", "TOP"],
                    },
                },
                "B": {
                    "action": {
                        "kind": "MOVE",
                        "piece": "b",
                        "vectors": [[0, -1]],
                    },
                    "goal": {
                        "kind": "REACH_EDGE",
                        "piece": "b",
                        "edge": "LEFT",
                    },
                },
            },
            "initial_pieces": [
                {"owner": "A", "piece": "a", "position": [0, 1]},
                {"owner": "A", "piece": "a", "position": [1, 0]},
                {"owner": "A", "piece": "a", "position": [2, 1]},
                {"owner": "B", "piece": "b", "position": [1, 1]},
            ],
        }
    )


def _full_width_definition():
    return parse_definition(
        {
            "schema_version": 4,
            "name": "Terminal-only full-width v1",
            "board_size": 3,
            "first_player": "A",
            "max_plies": 2,
            "roles": {
                "A": {
                    "action": {
                        "kind": "PUSH",
                        "piece": "a",
                        "vectors": [[0, 1], [1, 0]],
                    },
                    "goal": {
                        "kind": "REACH_EDGE",
                        "piece": "never_a",
                        "edge": "BOTTOM",
                    },
                },
                "B": {
                    "action": {
                        "kind": "MOVE",
                        "piece": "b",
                        "vectors": [[-1, 0], [0, -1]],
                    },
                    "goal": {
                        "kind": "REACH_EDGE",
                        "piece": "never_b",
                        "edge": "TOP",
                    },
                },
            },
            "initial_pieces": [
                {"owner": "A", "piece": "a", "position": [0, 0]},
                {"owner": "A", "piece": "a", "position": [1, 0]},
                {"owner": "B", "piece": "b", "position": [2, 2]},
            ],
        }
    )


def _transform_action(action, board_size, transform):
    origin = (
        transform_position(action.from_position, board_size, transform)
        if action.from_position is not None
        else None
    )
    return Action(
        kind=action.kind,
        from_position=origin,
        to_position=transform_position(
            action.to_position, board_size, transform
        ),
    )


class TerminalOnlyMinimaxAgentTests(unittest.TestCase):
    def assert_empty_audit(self, agent):
        self.assertIsNone(agent.last_expanded_nodes)
        self.assertIsNone(agent.last_cache_hits)
        self.assertEqual(agent.last_action_values, ())

    def assert_rejected_without_work(
        self, agent, definition, state, actions, rng, exception_type
    ):
        nodes_before = agent.total_nodes
        rng_before = rng.getstate()
        with self.assertRaises(exception_type):
            agent.select_action(definition, state, actions, rng)
        self.assertEqual(agent.total_nodes, nodes_before)
        self.assertEqual(rng.getstate(), rng_before)
        self.assert_empty_audit(agent)

    def test_constructor_identity_and_read_only_audit_contract(self):
        for invalid_depth in (
            True,
            False,
            0,
            -1,
            TERMINAL_ONLY_MINIMAX_MAX_DEPTH + 1,
            1.0,
            "1",
            None,
        ):
            with self.subTest(depth=invalid_depth):
                with self.assertRaises(ValueError):
                    TerminalOnlyMinimaxAgent(invalid_depth, 1)
        for invalid_cap in (True, False, 0, -1, 1.0, "1", None):
            with self.subTest(max_total_nodes=invalid_cap):
                with self.assertRaises(ValueError):
                    TerminalOnlyMinimaxAgent(1, invalid_cap)

        agent = TerminalOnlyMinimaxAgent(depth=2, max_total_nodes=17)
        self.assertEqual(TERMINAL_ONLY_MINIMAX_MAX_DEPTH, 64)
        self.assertEqual(
            TerminalOnlyMinimaxAgent(
                depth=TERMINAL_ONLY_MINIMAX_MAX_DEPTH,
                max_total_nodes=1,
            ).depth,
            64,
        )
        self.assertEqual(
            agent.identity,
            AgentIdentity(
                family="terminal_only_minimax",
                version=1,
                strength="depth2",
            ),
        )
        self.assertEqual(agent.identity.key, "terminal_only_minimax-v1-depth2")
        self.assertEqual(agent.depth, 2)
        self.assertEqual(agent.max_total_nodes, 17)
        self.assertEqual(agent.total_nodes, 0)
        self.assert_empty_audit(agent)

        for attribute, value in (
            ("depth", 3),
            ("max_total_nodes", 18),
            ("total_nodes", 1),
            ("identity", agent.identity),
            ("last_expanded_nodes", 1),
            ("last_cache_hits", 1),
            ("last_action_values", ()),
        ):
            with self.subTest(attribute=attribute):
                with self.assertRaises(AttributeError):
                    setattr(agent, attribute, value)

    def test_schema_state_action_and_rng_boundaries_reject_before_work(self):
        definition = _fixture_definition("convert-immediate-reconvergence-v1")
        state = initial_state(definition)
        actions = legal_actions(definition, state)
        self.assertEqual(len(actions), 2)
        agent = TerminalOnlyMinimaxAgent(depth=1, max_total_nodes=20)

        for malformed_actions in (
            list(actions),
            tuple(reversed(actions)),
            actions[:1],
            actions + (actions[0],),
            (),
        ):
            with self.subTest(actions=malformed_actions):
                self.assert_rejected_without_work(
                    agent,
                    definition,
                    state,
                    malformed_actions,
                    random.Random(9),
                    (TypeError, ValueError),
                )

        forged_action = object.__new__(Action)
        object.__setattr__(forged_action, "kind", actions[0].kind)
        object.__setattr__(
            forged_action,
            "from_position",
            (False, actions[0].from_position[1]),
        )
        object.__setattr__(forged_action, "to_position", actions[0].to_position)
        self.assertEqual(forged_action, actions[0])
        self.assert_rejected_without_work(
            agent,
            definition,
            state,
            (forged_action, actions[1]),
            random.Random(9),
            TypeError,
        )

        malformed_ply = GameState(
            ply=True,
            to_move=state.to_move,
            pieces=state.pieces,
            outcome=None,
        )
        self.assert_rejected_without_work(
            agent,
            definition,
            malformed_ply,
            actions,
            random.Random(9),
            ValueError,
        )

        wrong_turn = GameState(
            ply=0,
            to_move=Player.B,
            pieces=state.pieces,
            outcome=None,
        )
        self.assert_rejected_without_work(
            agent,
            definition,
            wrong_turn,
            legal_actions(definition, wrong_turn),
            random.Random(9),
            ValueError,
        )

        malformed_piece = InitialPiece(
            owner=Player.A,
            piece="converter",
            position=(True, 1),
        )
        malformed_pieces = GameState(
            ply=state.ply,
            to_move=state.to_move,
            pieces=(malformed_piece,) + state.pieces[1:],
            outcome=None,
        )
        self.assert_rejected_without_work(
            agent,
            definition,
            malformed_pieces,
            actions,
            random.Random(9),
            TypeError,
        )

        for bad_kind, error_type in (
            ("bad kind", TypeError),
            ("unknown_kind", ValueError),
        ):
            forged_kind_piece = InitialPiece(
                owner=state.pieces[0].owner,
                piece=bad_kind,
                position=state.pieces[0].position,
            )
            forged_kind_state = GameState(
                ply=state.ply,
                to_move=state.to_move,
                pieces=(forged_kind_piece,) + state.pieces[1:],
                outcome=None,
            )
            self.assert_rejected_without_work(
                agent,
                definition,
                forged_kind_state,
                actions,
                random.Random(9),
                error_type,
            )

        malformed_outcome = GameState(
            ply=state.ply,
            to_move=state.to_move,
            pieces=state.pieces,
            outcome=Outcome(winner=True, reason="GOAL"),
        )
        self.assert_rejected_without_work(
            agent,
            definition,
            malformed_outcome,
            actions,
            random.Random(9),
            TypeError,
        )

        subclass_rng = type("RandomSubclass", (random.Random,), {})()
        subclass_state = subclass_rng.getstate()
        with self.assertRaises(TypeError):
            agent.select_action(definition, state, actions, subclass_rng)
        self.assertEqual(subclass_rng.getstate(), subclass_state)
        self.assertEqual(agent.total_nodes, 0)
        self.assert_empty_audit(agent)

        schema_v1 = parse_definition(crossing_definition())
        schema_v1_state = initial_state(schema_v1)
        self.assert_rejected_without_work(
            agent,
            schema_v1,
            schema_v1_state,
            legal_actions(schema_v1, schema_v1_state),
            random.Random(9),
            ValueError,
        )

        capture = _fixture_definition("capture-eliminate-one-sided-b-v1")
        capture_state = initial_state(capture)
        capture_state = apply_action(
            capture, capture_state, legal_actions(capture, capture_state)[0]
        )
        capture_state = apply_action(
            capture, capture_state, legal_actions(capture, capture_state)[0]
        )
        self.assertEqual(capture_state.outcome.winner, Player.B)
        forged_nonterminal = GameState(
            ply=capture_state.ply,
            to_move=capture_state.to_move,
            pieces=capture_state.pieces,
            outcome=None,
        )
        self.assert_rejected_without_work(
            agent,
            capture,
            forged_nonterminal,
            legal_actions(capture, forged_nonterminal),
            random.Random(9),
            ValueError,
        )

    def test_push_terminal_utilities_root_accounting_and_unique_best_rng(self):
        definition = _fixture_definition("push-win-draw-loss-v1")
        state = initial_state(definition)
        actions = legal_actions(definition, state)
        rng = random.Random(27)
        rng_before = rng.getstate()
        agent = TerminalOnlyMinimaxAgent(depth=1, max_total_nodes=3)

        selected = agent.select_action(definition, state, actions, rng)

        self.assertEqual(selected, Action.push((1, 1), (2, 1)))
        self.assertEqual(rng.getstate(), rng_before)
        self.assertEqual(agent.last_expanded_nodes, 3)
        self.assertEqual(agent.last_cache_hits, 0)
        self.assertEqual(agent.total_nodes, 3)
        self.assertEqual(
            agent.last_action_values,
            tuple(zip(actions, (-1, 0, 1))),
        )

    def test_convert_reconvergence_per_select_cache_and_seeded_ties(self):
        definition = _fixture_definition("convert-immediate-reconvergence-v1")
        state = initial_state(definition)
        actions = legal_actions(definition, state)
        agent = TerminalOnlyMinimaxAgent(depth=1, max_total_nodes=2)

        seed_zero = random.Random(0)
        seed_zero_before = seed_zero.getstate()
        self.assertEqual(
            agent.select_action(definition, state, actions, seed_zero),
            actions[1],
        )
        self.assertNotEqual(seed_zero.getstate(), seed_zero_before)
        self.assertEqual(agent.last_expanded_nodes, 1)
        self.assertEqual(agent.last_cache_hits, 1)
        self.assertEqual(agent.last_action_values, tuple(zip(actions, (0, 0))))
        self.assertEqual(agent.total_nodes, 1)

        seed_one = random.Random(1)
        self.assertEqual(
            agent.select_action(definition, state, actions, seed_one),
            actions[0],
        )
        self.assertEqual(agent.last_expanded_nodes, 1)
        self.assertEqual(agent.last_cache_hits, 1)
        self.assertEqual(agent.total_nodes, 2)

        depth_two = TerminalOnlyMinimaxAgent(depth=2, max_total_nodes=2)
        depth_two.select_action(
            definition, state, actions, random.Random(0)
        )
        self.assertEqual(depth_two.last_expanded_nodes, 2)
        self.assertEqual(depth_two.last_cache_hits, 1)
        self.assertEqual(
            depth_two.last_action_values, tuple(zip(actions, (0, 0)))
        )

    def test_nonterminal_cutoff_and_eliminate_terminal_are_exact(self):
        definition = _fixture_definition("capture-eliminate-one-sided-b-v1")
        state = initial_state(definition)
        actions = legal_actions(definition, state)

        cutoff = TerminalOnlyMinimaxAgent(depth=1, max_total_nodes=1)
        self.assertEqual(
            cutoff.select_action(definition, state, actions, random.Random(0)),
            actions[0],
        )
        self.assertEqual(cutoff.last_action_values, ((actions[0], 0),))
        self.assertEqual(cutoff.last_expanded_nodes, 1)

        exact = TerminalOnlyMinimaxAgent(depth=2, max_total_nodes=2)
        selected = exact.select_action(
            definition, state, actions, random.Random(0)
        )
        self.assertEqual(selected, actions[0])
        self.assertEqual(exact.last_action_values, ((actions[0], -1),))
        self.assertEqual(exact.last_expanded_nodes, 2)

        b_state = apply_action(definition, state, selected)
        b_actions = legal_actions(definition, b_state)
        self.assertEqual(len(b_actions), 1)
        b_agent = TerminalOnlyMinimaxAgent(depth=1, max_total_nodes=1)
        self.assertEqual(
            b_agent.select_action(
                definition, b_state, b_actions, random.Random(0)
            ),
            Action.move_capture((1, 1), (1, 0)),
        )
        self.assertEqual(b_agent.last_action_values, ((b_actions[0], -1),))

    def test_hop_action_is_supported_without_nonterminal_heuristic(self):
        definition = _fixture_definition(
            "hop-opponent-dependency-without-direct-effect-v1"
        )
        state = initial_state(definition)
        actions = legal_actions(definition, state)
        agent = TerminalOnlyMinimaxAgent(depth=1, max_total_nodes=1)
        rng = random.Random(4)
        rng_before = rng.getstate()

        self.assertEqual(
            agent.select_action(definition, state, actions, rng),
            Action.hop((1, 0), (1, 2)),
        )
        self.assertEqual(agent.last_action_values, ((actions[0], 0),))
        self.assertEqual(agent.last_expanded_nodes, 1)
        self.assertEqual(rng.getstate(), rng_before)

    def test_schema_v4_place_created_piece_is_accepted_on_the_next_turn(self):
        definition = parse_definition(
            {
                "schema_version": 4,
                "name": "Terminal-only PLACE reachability v1",
                "board_size": 3,
                "first_player": "A",
                "max_plies": 3,
                "roles": {
                    "A": {
                        "action": {"kind": "PLACE", "piece": "stone"},
                        "goal": {
                            "kind": "REACH_EDGE",
                            "piece": "stone",
                            "edge": "BOTTOM",
                        },
                    },
                    "B": {
                        "action": {
                            "kind": "HOP",
                            "piece": "hopper",
                            "vectors": [[0, 1]],
                        },
                        "goal": {
                            "kind": "REACH_EDGE",
                            "piece": "hopper",
                            "edge": "RIGHT",
                        },
                    },
                },
                "initial_pieces": [
                    {"owner": "B", "piece": "hopper", "position": [1, 0]},
                    {"owner": "A", "piece": "blocker", "position": [1, 1]},
                ],
            }
        )
        state = initial_state(definition)
        state = apply_action(definition, state, Action.place(0, 0))
        actions = legal_actions(definition, state)
        agent = TerminalOnlyMinimaxAgent(
            depth=1, max_total_nodes=len(actions)
        )
        selected = agent.select_action(
            definition, state, actions, random.Random(0)
        )
        self.assertIn(selected, actions)
        self.assertEqual(agent.last_expanded_nodes, len(actions))

    def test_depth_two_search_expands_the_complete_tree_without_pruning(self):
        definition = _full_width_definition()
        state = initial_state(definition)
        actions = legal_actions(definition, state)
        self.assertEqual(len(actions), 3)
        self.assertEqual(
            tuple(
                len(legal_actions(definition, apply_action(definition, state, action)))
                for action in actions
            ),
            (2, 2, 2),
        )
        agent = TerminalOnlyMinimaxAgent(depth=2, max_total_nodes=9)

        selected = agent.select_action(
            definition, state, actions, random.Random(0)
        )

        self.assertIn(selected, actions)
        self.assertEqual(agent.last_action_values, tuple(zip(actions, (0, 0, 0))))
        # Three root successors plus all six terminal grandchildren.  With the
        # all-zero leaves, ordinary alpha-beta would prune later B branches.
        self.assertEqual(agent.last_expanded_nodes, 9)
        self.assertEqual(agent.last_cache_hits, 0)

    def test_swap_simultaneous_goals_use_actor_priority(self):
        definition = _simultaneous_connect_definition()
        state = initial_state(definition)
        actions = legal_actions(definition, state)
        central = Action.swap((1, 0), (1, 1))
        result = apply_action(definition, state, central)

        self.assertTrue(goal_satisfied(definition, result.pieces, Player.A))
        self.assertTrue(goal_satisfied(definition, result.pieces, Player.B))
        self.assertEqual(result.outcome, Outcome(winner=Player.A, reason="GOAL"))

        agent = TerminalOnlyMinimaxAgent(depth=1, max_total_nodes=3)
        rng = random.Random(31)
        rng_before = rng.getstate()
        self.assertEqual(
            agent.select_action(definition, state, actions, rng), central
        )
        self.assertEqual(
            agent.last_action_values, tuple(zip(actions, (0, 1, 0)))
        )
        self.assertEqual(agent.last_expanded_nodes, 3)
        self.assertEqual(agent.last_cache_hits, 0)
        self.assertEqual(rng.getstate(), rng_before)

    def test_budget_is_cumulative_per_slot_and_reset_clears_audit(self):
        push = _fixture_definition("push-win-draw-loss-v1")
        push_state = initial_state(push)
        push_actions = legal_actions(push, push_state)
        rng = random.Random(5)
        rng_before = rng.getstate()
        insufficient = TerminalOnlyMinimaxAgent(depth=1, max_total_nodes=2)

        with self.assertRaises(SearchBudgetExceeded) as raised:
            insufficient.select_action(push, push_state, push_actions, rng)
        self.assertIs(type(raised.exception), SearchBudgetExceeded)
        self.assertEqual(raised.exception.scope, "per-slot")
        self.assertEqual(raised.exception.visited_nodes, 2)
        self.assertEqual(raised.exception.max_nodes, 2)
        self.assertEqual(insufficient.total_nodes, 2)
        self.assertEqual(rng.getstate(), rng_before)
        self.assert_empty_audit(insufficient)

        sufficient = TerminalOnlyMinimaxAgent(depth=1, max_total_nodes=3)
        sufficient.select_action(push, push_state, push_actions, random.Random(5))
        self.assertEqual(sufficient.total_nodes, 3)
        with self.assertRaises(SearchBudgetExceeded) as second:
            sufficient.select_action(
                push, push_state, push_actions, random.Random(5)
            )
        self.assertEqual(second.exception.scope, "per-slot")
        self.assertEqual(second.exception.visited_nodes, 3)
        self.assert_empty_audit(sufficient)

        sufficient.reset_budget()
        self.assertEqual(sufficient.total_nodes, 0)
        self.assert_empty_audit(sufficient)
        sufficient.select_action(push, push_state, push_actions, random.Random(5))
        self.assertEqual(sufficient.total_nodes, 3)

    def test_one_agent_can_spend_one_cumulative_slot_across_both_roles(self):
        definition = _fixture_definition("capture-eliminate-one-sided-b-v1")
        state = initial_state(definition)
        actions = legal_actions(definition, state)
        agent = TerminalOnlyMinimaxAgent(depth=2, max_total_nodes=3)

        first = agent.select_action(
            definition, state, actions, random.Random(0)
        )
        self.assertEqual(agent.last_expanded_nodes, 2)
        self.assertEqual(agent.total_nodes, 2)
        b_state = apply_action(definition, state, first)
        b_actions = legal_actions(definition, b_state)
        agent.select_action(definition, b_state, b_actions, random.Random(0))
        self.assertEqual(agent.last_expanded_nodes, 1)
        self.assertEqual(agent.total_nodes, 3)

        capped = TerminalOnlyMinimaxAgent(depth=2, max_total_nodes=2)
        first = capped.select_action(
            definition, state, actions, random.Random(0)
        )
        b_state = apply_action(definition, state, first)
        with self.assertRaises(SearchBudgetExceeded) as raised:
            capped.select_action(
                definition,
                b_state,
                legal_actions(definition, b_state),
                random.Random(0),
            )
        self.assertEqual(raised.exception.scope, "per-slot")
        self.assertEqual(raised.exception.visited_nodes, 2)
        self.assert_empty_audit(capped)

    def test_invalid_call_after_success_does_not_leave_stale_audit(self):
        definition = _fixture_definition("convert-immediate-reconvergence-v1")
        state = initial_state(definition)
        actions = legal_actions(definition, state)
        agent = TerminalOnlyMinimaxAgent(depth=1, max_total_nodes=2)
        agent.select_action(definition, state, actions, random.Random(0))
        self.assertEqual(agent.last_expanded_nodes, 1)

        self.assert_rejected_without_work(
            agent,
            definition,
            state,
            tuple(reversed(actions)),
            random.Random(0),
            ValueError,
        )

        drifted = TerminalOnlyMinimaxAgent(depth=1, max_total_nodes=2)
        object.__setattr__(drifted, "_depth", True)
        self.assert_rejected_without_work(
            drifted,
            definition,
            state,
            actions,
            random.Random(0),
            ValueError,
        )

        identity_drifted = TerminalOnlyMinimaxAgent(
            depth=1, max_total_nodes=2
        )
        object.__setattr__(identity_drifted.identity, "version", True)
        self.assert_rejected_without_work(
            identity_drifted,
            definition,
            state,
            actions,
            random.Random(0),
            ValueError,
        )

    def test_all_five_actions_and_three_goals_are_d4_stable(self):
        cases = (
            ("push-win-draw-loss-v1", 1, 1, 3, (-1, 0, 1)),
            ("convert-immediate-reconvergence-v1", 1, 0, 1, (0, 0)),
            ("capture-eliminate-one-sided-b-v1", 1, 0, 1, (0,)),
            (
                "hop-opponent-dependency-without-direct-effect-v1",
                1,
                0,
                1,
                (0,),
            ),
        )
        definitions = [
            (
                fixture_id,
                _fixture_definition(fixture_id),
                depth,
                expected_value,
                expected_nodes,
                expected_scores,
            )
            for (
                fixture_id,
                depth,
                expected_value,
                expected_nodes,
                expected_scores,
            ) in cases
        ]
        definitions.append(
            (
                "swap-simultaneous-connect-v1",
                _simultaneous_connect_definition(),
                1,
                1,
                3,
                (0, 0, 1),
            )
        )

        for (
            fixture_id,
            definition,
            depth,
            expected_value,
            expected_nodes,
            expected_scores,
        ) in definitions:
            base_state = initial_state(definition)
            base_actions = legal_actions(definition, base_state)
            base_agent = TerminalOnlyMinimaxAgent(depth, 100)
            base_selected = base_agent.select_action(
                definition, base_state, base_actions, random.Random(0)
            )
            is_unique = sum(
                value == expected_value
                for _, value in base_agent.last_action_values
            ) == 1

            for transform in D4_TRANSFORMS:
                with self.subTest(fixture=fixture_id, transform=transform):
                    transformed = transform_definition(definition, transform)
                    state = initial_state(transformed)
                    actions = legal_actions(transformed, state)
                    agent = TerminalOnlyMinimaxAgent(depth, 100)
                    selected = agent.select_action(
                        transformed, state, actions, random.Random(0)
                    )
                    selected_value = dict(agent.last_action_values)[selected]
                    self.assertEqual(selected_value, expected_value)
                    self.assertEqual(agent.last_expanded_nodes, expected_nodes)
                    self.assertEqual(
                        tuple(sorted(value for _, value in agent.last_action_values)),
                        expected_scores,
                    )
                    if is_unique:
                        self.assertEqual(
                            selected,
                            _transform_action(
                                base_selected,
                                definition.board_size,
                                transform,
                            ),
                        )

        capture = _fixture_definition("capture-eliminate-one-sided-b-v1")
        for transform in D4_TRANSFORMS:
            with self.subTest(fixture="capture-depth2", transform=transform):
                transformed = transform_definition(capture, transform)
                state = initial_state(transformed)
                actions = legal_actions(transformed, state)
                agent = TerminalOnlyMinimaxAgent(depth=2, max_total_nodes=2)
                selected = agent.select_action(
                    transformed, state, actions, random.Random(0)
                )
                self.assertEqual(dict(agent.last_action_values)[selected], -1)
                self.assertEqual(agent.last_expanded_nodes, 2)

    def test_module_is_python39_and_has_no_heuristic_or_family_coupling(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(MODULE_PATH), feature_version=(3, 9))
        imported_modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        imported_modules.update(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        banned_modules = {
            "analysis",
            "atlas",
            "exact_solver",
            "solver",
        }
        self.assertTrue(
            all(
                module.split(".")[-1] not in banned_modules
                for module in imported_modules
            )
        )
        loaded_names = {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name)
        }
        loaded_attributes = {
            node.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
        }
        self.assertNotIn("GoalKind", loaded_names)
        self.assertNotIn("goal_progress", loaded_names)
        self.assertNotIn("MinimaxAgent", loaded_names)
        self.assertNotIn("GoalKind", loaded_attributes)
        self.assertNotIn("goal_progress", loaded_attributes)
        self.assertNotIn("MinimaxAgent", loaded_attributes)
        self.assertTrue({"alpha", "beta"}.isdisjoint(loaded_names))

        search_functions = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "search"
        ]
        self.assertEqual(len(search_functions), 1)
        self.assertEqual(
            [argument.arg for argument in search_functions[0].args.args],
            ["candidate", "remaining"],
        )
        for family_id in (
            "push-hop-race-v1",
            "swap-hop-network-v1",
            "convert-push-front-v1",
            "capture-hop-hunt-v1",
            "convert-capture-duel-v1",
            "push-swap-networks-v1",
        ):
            self.assertNotIn(family_id, source)


if __name__ == "__main__":
    unittest.main()
