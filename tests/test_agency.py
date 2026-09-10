import ast
import copy
import inspect
import unittest
from collections.abc import Mapping
from unittest import mock

import parity_forge.agency as agency_module
from parity_forge.agency import (
    _position_key,
    derive_replay_telemetry_v1,
    validate_replay_telemetry_v1,
)
from parity_forge.dsl import InitialPiece, Player
from parity_forge.engine import GameState, Outcome


VECTORS = [[0, 1]]


def _action_spec(kind, piece, vectors=None):
    result = {"kind": kind, "piece": piece}
    if kind != "PLACE":
        result["vectors"] = copy.deepcopy(vectors if vectors is not None else VECTORS)
    return result


def _reach_goal(piece="unreachable_goal"):
    return {"kind": "REACH_EDGE", "piece": piece, "edge": "TOP"}


def _piece(owner, piece, row, column):
    return {
        "owner": owner,
        "piece": piece,
        "position": [row, column],
    }


def _definition(
    *,
    a_kind="PUSH",
    b_kind="PUSH",
    a_piece="a_actor",
    b_piece="b_actor",
    a_vectors=None,
    b_vectors=None,
    a_goal=None,
    b_goal=None,
    pieces=(),
    max_plies=1,
    schema_version=4,
):
    initial_pieces = copy.deepcopy(list(pieces))
    initial_pieces.sort(
        key=lambda value: (
            value["position"],
            value["owner"],
            value["piece"],
        )
    )
    return {
        "schema_version": schema_version,
        "name": "Replay telemetry probe",
        "board_size": 3,
        "first_player": "A",
        "max_plies": max_plies,
        "roles": {
            "A": {
                "action": _action_spec(a_kind, a_piece, a_vectors),
                "goal": copy.deepcopy(a_goal or _reach_goal()),
            },
            "B": {
                "action": _action_spec(b_kind, b_piece, b_vectors),
                "goal": copy.deepcopy(b_goal or _reach_goal()),
            },
        },
        "initial_pieces": initial_pieces,
    }


def _one_ply_definition(kind, *, occupied_target=False):
    pieces = [_piece("A", "actor", 1, 0), _piece("B", "b_actor", 2, 0)]
    if occupied_target:
        pieces.append(_piece("B", "target", 1, 1))
    return _definition(
        a_kind=kind,
        a_piece="actor",
        pieces=pieces,
        max_plies=1,
    )


def _action(kind, origin=(1, 0), target=(1, 1)):
    result = {"kind": kind, "to": list(target)}
    if kind != "PLACE":
        result["from"] = list(origin)
    return result


def _telemetry_dict(definition, actions):
    telemetry = derive_replay_telemetry_v1(definition, actions)
    first = telemetry.to_dict()
    second = telemetry.to_dict()
    if first is second:
        raise AssertionError("to_dict() must return a detached value")
    return telemetry, first


class _DictSubclass(dict):
    pass


class _ListSubclass(list):
    pass


class _NeverEndingActions:
    def __init__(self, action, maximum_pulls):
        self.action = action
        self.maximum_pulls = maximum_pulls
        self.pulls = 0

    def __iter__(self):
        return self

    def __next__(self):
        self.pulls += 1
        if self.pulls > self.maximum_pulls:
            raise AssertionError("the action iterable was pulled past its public cap")
        return copy.deepcopy(self.action)


class ReplayTelemetryBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.definition = _one_ply_definition("PUSH")
        self.action = _action("PUSH")

    def test_schema_v4_complete_trace_round_trips_through_public_validator(self):
        telemetry, stored = _telemetry_dict(self.definition, [self.action])
        validated = validate_replay_telemetry_v1(self.definition, stored)

        self.assertEqual(validated.to_dict(), telemetry.to_dict())
        self.assertEqual(stored["telemetry_version"], 1)
        self.assertEqual(stored["dsl_schema_version"], 4)
        self.assertEqual(stored["actions"], [self.action])
        self.assertEqual(stored["terminal"]["ply"], 1)
        self.assertEqual(stored["terminal"]["reason"], "PLY_LIMIT")
        self.assertIsNone(stored["terminal"]["winner"])

    def test_v1_emitted_vocabularies_are_exact_golden_values(self):
        _, stored = _telemetry_dict(self.definition, [self.action])

        self.assertEqual(
            stored["action_vocabulary"],
            ["PLACE", "MOVE", "MOVE_CAPTURE", "PUSH", "SWAP", "HOP", "CONVERT"],
        )
        self.assertEqual(
            stored["goal_vocabulary"],
            ["CONNECT_EDGES", "REACH_EDGE", "ELIMINATE"],
        )
        self.assertEqual(
            stored["terminal_reason_vocabulary"],
            ["GOAL", "NO_LEGAL_ACTION", "PLY_LIMIT"],
        )
        self.assertEqual(
            stored["effect_mode_vocabulary"],
            [
                "PLACE",
                "ORDINARY_STEP",
                "CAPTURE",
                "PUSH",
                "SWAP",
                "HOP",
                "CONVERT",
            ],
        )
        self.assertEqual(
            stored["outcome_class_vocabulary"],
            ["NONTERMINAL", "ACTOR_WIN", "DRAW", "ACTOR_LOSS"],
        )
        self.assertEqual(
            stored["direct_effect_status_vocabulary"],
            ["NONE", "A_ONLY", "B_ONLY", "BOTH_ROLES"],
        )
        self.assertEqual(
            (
                agency_module.MAX_LEGAL_ACTIONS_PER_DECISION_V1,
                agency_module.MAX_COUNTERFACTUAL_SUCCESSORS_V1,
                agency_module.MAX_NEXT_ACTION_OBSERVATIONS_V1,
                agency_module.MAX_REPLAY_ACTIONS_V1,
                agency_module.MAX_STORED_JSON_NODES_V1,
                agency_module.MAX_STORED_JSON_DEPTH_V1,
            ),
            (200, 200_000, 40_000_000, 1_000, 1_000_000, 32),
        )

    def test_only_schema_v4_is_admitted(self):
        legacy = copy.deepcopy(self.definition)
        legacy["schema_version"] = 3
        legacy["roles"]["A"]["action"]["kind"] = "MOVE_CAPTURE"
        legacy["roles"]["B"]["action"]["kind"] = "MOVE"

        with self.assertRaises(ValueError):
            derive_replay_telemetry_v1(legacy, [_action("MOVE_CAPTURE")])

    def test_action_container_rejects_mapping_text_and_bytes(self):
        for value in ({"0": self.action}, "PUSH", b"PUSH"):
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(ValueError):
                    derive_replay_telemetry_v1(self.definition, value)

    def test_each_recorded_action_must_be_an_exact_dict(self):
        bad_values = (
            _DictSubclass(self.action),
            MappingProxy(self.action),
            [self.action],
            "PUSH",
            None,
        )
        for value in bad_values:
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(ValueError):
                    derive_replay_telemetry_v1(self.definition, [value])

    def test_action_coordinates_must_be_exact_two_integer_lists(self):
        mutations = (
            lambda value: value.__setitem__("from", (1, 0)),
            lambda value: value.__setitem__("to", (1, 1)),
            lambda value: value.__setitem__("from", _ListSubclass([1, 0])),
            lambda value: value.__setitem__("to", _ListSubclass([1, 1])),
            lambda value: value.__setitem__("from", [True, 0]),
            lambda value: value.__setitem__("to", [1, False]),
            lambda value: value.__setitem__("from", [1]),
            lambda value: value.__setitem__("to", [1, 1, 0]),
        )
        for mutate in mutations:
            bad = copy.deepcopy(self.action)
            mutate(bad)
            with self.subTest(action=bad):
                with self.assertRaises(ValueError):
                    derive_replay_telemetry_v1(self.definition, [bad])

    def test_action_fields_are_exact_and_kind_is_closed(self):
        bad_actions = []
        missing = copy.deepcopy(self.action)
        del missing["from"]
        bad_actions.append(missing)
        extra = copy.deepcopy(self.action)
        extra["target_kind"] = "target"
        bad_actions.append(extra)
        unknown = copy.deepcopy(self.action)
        unknown["kind"] = "CAPTURE_STEP"
        bad_actions.append(unknown)
        wrong_place = {"kind": "PLACE", "from": [1, 0], "to": [1, 1]}
        bad_actions.append(wrong_place)

        for bad in bad_actions:
            with self.subTest(action=bad):
                with self.assertRaises(ValueError):
                    derive_replay_telemetry_v1(self.definition, [bad])

    def test_trace_must_be_complete_exactly_at_the_first_terminal_state(self):
        with self.assertRaises(ValueError):
            derive_replay_telemetry_v1(self.definition, [])
        with self.assertRaises(ValueError):
            derive_replay_telemetry_v1(
                self.definition,
                [self.action, copy.deepcopy(self.action)],
            )

        illegal = _action("PUSH", origin=(1, 0), target=(0, 0))
        with self.assertRaises(ValueError):
            derive_replay_telemetry_v1(self.definition, [illegal])

    def test_initial_terminal_accepts_only_the_empty_trace(self):
        initial_goal = _definition(
            pieces=(
                _piece("A", "goal", 0, 0),
                _piece("A", "a_actor", 1, 0),
                _piece("B", "b_actor", 2, 0),
            ),
            a_goal=_reach_goal("goal"),
            max_plies=4,
        )

        _, stored = _telemetry_dict(initial_goal, [])
        self.assertEqual(stored["actions"], [])
        self.assertEqual(stored["decisions"], [])
        self.assertEqual(stored["terminal"]["ply"], 0)
        self.assertEqual(stored["terminal"]["reason"], "GOAL")
        self.assertEqual(stored["terminal"]["winner"], "A")

        with self.assertRaises(ValueError):
            derive_replay_telemetry_v1(initial_goal, [self.action])

    def test_initial_no_legal_action_is_a_complete_empty_trace(self):
        no_action = _definition(
            pieces=(_piece("B", "b_actor", 2, 0),),
            max_plies=4,
        )

        _, stored = _telemetry_dict(no_action, [])
        self.assertEqual(stored["decisions"], [])
        self.assertEqual(stored["terminal"]["ply"], 0)
        self.assertEqual(stored["terminal"]["reason"], "NO_LEGAL_ACTION")
        self.assertEqual(stored["terminal"]["winner"], "B")

    def test_general_iterable_is_bounded_by_max_plies_plus_one_pulls(self):
        source = _NeverEndingActions(self.action, maximum_pulls=2)
        with self.assertRaises(ValueError):
            derive_replay_telemetry_v1(self.definition, source)
        self.assertLessEqual(source.pulls, self.definition["max_plies"] + 1)

    def test_outputs_are_detached_from_definition_actions_and_to_dict_results(self):
        definition = copy.deepcopy(self.definition)
        actions = [copy.deepcopy(self.action)]
        telemetry, expected = _telemetry_dict(definition, actions)

        definition["name"] = "mutated after derivation"
        definition["initial_pieces"][0]["position"][0] = 0
        actions[0]["to"][1] = 2
        self.assertEqual(telemetry.to_dict(), expected)

        exposed = telemetry.to_dict()
        exposed["actions"][0]["to"][1] = 2
        exposed["decisions"].clear()
        self.assertEqual(telemetry.to_dict(), expected)

    def test_definition_mutation_during_action_iteration_fails_closed(self):
        definition = copy.deepcopy(self.definition)

        def mutating_actions():
            definition["name"] = "retimed definition"
            yield copy.deepcopy(self.action)

        with self.assertRaises(ValueError):
            derive_replay_telemetry_v1(definition, mutating_actions())

    def test_validator_rebuilds_every_claim_from_stored_actions(self):
        _, stored = _telemetry_dict(self.definition, [self.action])
        mutations = []

        changed_version = copy.deepcopy(stored)
        changed_version["telemetry_version"] = 2
        mutations.append(changed_version)

        changed_action = copy.deepcopy(stored)
        changed_action["actions"][0]["to"] = [1, 2]
        mutations.append(changed_action)

        changed_terminal = copy.deepcopy(stored)
        changed_terminal["terminal"]["reason"] = "GOAL"
        mutations.append(changed_terminal)

        changed_decision = copy.deepcopy(stored)
        changed_decision["decisions"][0]["legal_count"] += 1
        mutations.append(changed_decision)

        changed_digest = copy.deepcopy(stored)
        changed_digest["evidence_digest"] = "0" * 64
        mutations.append(changed_digest)

        extra = copy.deepcopy(stored)
        extra["unregistered_observation"] = True
        mutations.append(extra)

        for index, tampered in enumerate(mutations):
            with self.subTest(index=index):
                with self.assertRaises(ValueError):
                    validate_replay_telemetry_v1(self.definition, tampered)

    def test_validator_rejects_nonexact_stored_container(self):
        telemetry, stored = _telemetry_dict(self.definition, [self.action])
        with self.assertRaises(ValueError):
            validate_replay_telemetry_v1(self.definition, telemetry)
        with self.assertRaises(ValueError):
            validate_replay_telemetry_v1(
                self.definition,
                _DictSubclass(stored),
            )

    def test_validator_rejects_over_horizon_actions_before_parsing_them(self):
        _, stored = _telemetry_dict(self.definition, [self.action])
        stored["actions"] = [copy.deepcopy(self.action) for _ in range(10_000)]

        with mock.patch.object(
            agency_module,
            "_parse_exact_action",
            wraps=agency_module._parse_exact_action,
        ) as parser:
            with self.assertRaisesRegex(ValueError, "horizon"):
                validate_replay_telemetry_v1(self.definition, stored)
        parser.assert_not_called()

    def test_validator_seals_stored_evidence_before_definition_callbacks(self):
        _, stored = _telemetry_dict(self.definition, [self.action])
        stored["terminal"]["reason"] = "GOAL"
        hostile_definition = MutatingMappingProxy(
            self.definition,
            lambda: stored["terminal"].__setitem__("reason", "PLY_LIMIT"),
        )

        with self.assertRaisesRegex(ValueError, "mutated"):
            validate_replay_telemetry_v1(hostile_definition, stored)

    def test_validator_rejects_cyclic_or_overdeep_stored_json(self):
        _, stored = _telemetry_dict(self.definition, [self.action])
        stored["roles"]["A"]["cycle"] = stored["roles"]["A"]
        with self.assertRaisesRegex(ValueError, "cycle"):
            validate_replay_telemetry_v1(self.definition, stored)

        _, overdeep = _telemetry_dict(self.definition, [self.action])
        nested = []
        cursor = nested
        for _ in range(40):
            child = []
            cursor.append(child)
            cursor = child
        overdeep["roles"]["A"]["overdeep"] = nested
        with self.assertRaisesRegex(ValueError, "depth"):
            validate_replay_telemetry_v1(self.definition, overdeep)

    def test_counterfactual_work_caps_fail_closed(self):
        with mock.patch.object(
            agency_module, "MAX_COUNTERFACTUAL_SUCCESSORS_V1", 0
        ):
            with self.assertRaisesRegex(ValueError, "successor cap"):
                derive_replay_telemetry_v1(self.definition, [self.action])

        two_ply = _definition(
            a_kind="PUSH",
            b_kind="PUSH",
            a_piece="a_actor",
            b_piece="b_actor",
            a_vectors=[[0, 1]],
            b_vectors=[[0, -1]],
            pieces=(
                _piece("A", "a_actor", 0, 0),
                _piece("B", "b_actor", 2, 2),
            ),
            max_plies=2,
        )
        trace = [
            _action("PUSH", origin=(0, 0), target=(0, 1)),
            _action("PUSH", origin=(2, 2), target=(2, 1)),
        ]
        with mock.patch.object(
            agency_module, "MAX_NEXT_ACTION_OBSERVATIONS_V1", 0
        ):
            with self.assertRaisesRegex(ValueError, "next-action observation cap"):
                derive_replay_telemetry_v1(two_ply, trace)

    def test_agency_module_imports_no_agent_solver_or_play_layer(self):
        tree = ast.parse(inspect.getsource(agency_module))
        relative_modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.level > 0
        }
        self.assertEqual(relative_modules, {"dsl", "engine"})
        absolute_project_imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                absolute_project_imports.update(
                    alias.name
                    for alias in node.names
                    if alias.name == "parity_forge"
                    or alias.name.startswith("parity_forge.")
                )
            elif (
                isinstance(node, ast.ImportFrom)
                and node.level == 0
                and node.module is not None
                and (
                    node.module == "parity_forge"
                    or node.module.startswith("parity_forge.")
                )
            ):
                absolute_project_imports.add(node.module)
        self.assertEqual(absolute_project_imports, set())


class MappingProxy(Mapping):
    def __init__(self, value):
        self._value = value

    def __getitem__(self, key):
        return self._value[key]

    def __iter__(self):
        return iter(self._value)

    def __len__(self):
        return len(self._value)


class MutatingMappingProxy(MappingProxy):
    def __init__(self, value, mutate):
        super().__init__(value)
        self._mutate = mutate
        self._mutated = False

    def __getitem__(self, key):
        if not self._mutated:
            self._mutated = True
            self._mutate()
        return super().__getitem__(key)


class ReplayTelemetryMeaningTests(unittest.TestCase):
    def test_repetition_key_ignores_only_ply_and_outcome(self):
        base_piece = InitialPiece(Player.A, "stone", (1, 1))
        base = GameState(ply=0, to_move=Player.A, pieces=(base_piece,))
        same_position = GameState(
            ply=99,
            to_move=Player.A,
            pieces=(base_piece,),
            outcome=Outcome(winner=None, reason="PLY_LIMIT"),
        )
        self.assertEqual(_position_key(base), _position_key(same_position))

        variants = (
            GameState(ply=0, to_move=Player.B, pieces=(base_piece,)),
            GameState(
                ply=0,
                to_move=Player.A,
                pieces=(InitialPiece(Player.B, "stone", (1, 1)),),
            ),
            GameState(
                ply=0,
                to_move=Player.A,
                pieces=(InitialPiece(Player.A, "other", (1, 1)),),
            ),
            GameState(
                ply=0,
                to_move=Player.A,
                pieces=(InitialPiece(Player.A, "stone", (1, 2)),),
            ),
        )
        for variant in variants:
            self.assertNotEqual(_position_key(base), _position_key(variant))

    def test_effect_modes_and_chosen_effect_deltas_cover_the_fixed_vocabulary(self):
        cases = (
            (
                "PLACE",
                False,
                _action("PLACE", target=(1, 1)),
                "PLACE",
                {
                    "own_placements": 1,
                    "own_movements": 0,
                    "opponent_movements": 0,
                    "conversions": 0,
                    "removals": 0,
                    "opponent_dependency": False,
                    "realized_opponent_effect": False,
                },
            ),
            (
                "MOVE",
                False,
                _action("MOVE"),
                "ORDINARY_STEP",
                {
                    "own_placements": 0,
                    "own_movements": 1,
                    "opponent_movements": 0,
                    "conversions": 0,
                    "removals": 0,
                    "opponent_dependency": False,
                    "realized_opponent_effect": False,
                },
            ),
            (
                "MOVE_CAPTURE",
                False,
                _action("MOVE_CAPTURE"),
                "ORDINARY_STEP",
                {
                    "own_placements": 0,
                    "own_movements": 1,
                    "opponent_movements": 0,
                    "conversions": 0,
                    "removals": 0,
                    "opponent_dependency": False,
                    "realized_opponent_effect": False,
                },
            ),
            (
                "MOVE_CAPTURE",
                True,
                _action("MOVE_CAPTURE"),
                "CAPTURE",
                {
                    "own_placements": 0,
                    "own_movements": 1,
                    "opponent_movements": 0,
                    "conversions": 0,
                    "removals": 1,
                    "opponent_dependency": True,
                    "realized_opponent_effect": True,
                },
            ),
            (
                "PUSH",
                False,
                _action("PUSH"),
                "ORDINARY_STEP",
                {
                    "own_placements": 0,
                    "own_movements": 1,
                    "opponent_movements": 0,
                    "conversions": 0,
                    "removals": 0,
                    "opponent_dependency": False,
                    "realized_opponent_effect": False,
                },
            ),
            (
                "PUSH",
                True,
                _action("PUSH"),
                "PUSH",
                {
                    "own_placements": 0,
                    "own_movements": 1,
                    "opponent_movements": 1,
                    "conversions": 0,
                    "removals": 0,
                    "opponent_dependency": True,
                    "realized_opponent_effect": True,
                },
            ),
            (
                "SWAP",
                False,
                _action("SWAP"),
                "ORDINARY_STEP",
                {
                    "own_placements": 0,
                    "own_movements": 1,
                    "opponent_movements": 0,
                    "conversions": 0,
                    "removals": 0,
                    "opponent_dependency": False,
                    "realized_opponent_effect": False,
                },
            ),
            (
                "SWAP",
                True,
                _action("SWAP"),
                "SWAP",
                {
                    "own_placements": 0,
                    "own_movements": 1,
                    "opponent_movements": 1,
                    "conversions": 0,
                    "removals": 0,
                    "opponent_dependency": True,
                    "realized_opponent_effect": True,
                },
            ),
            (
                "HOP",
                False,
                _action("HOP"),
                "ORDINARY_STEP",
                {
                    "own_placements": 0,
                    "own_movements": 1,
                    "opponent_movements": 0,
                    "conversions": 0,
                    "removals": 0,
                    "opponent_dependency": False,
                    "realized_opponent_effect": False,
                },
            ),
            (
                "HOP",
                True,
                _action("HOP", target=(1, 2)),
                "HOP",
                {
                    "own_placements": 0,
                    "own_movements": 1,
                    "opponent_movements": 0,
                    "conversions": 0,
                    "removals": 0,
                    "opponent_dependency": True,
                    "realized_opponent_effect": False,
                },
            ),
            (
                "CONVERT",
                True,
                _action("CONVERT"),
                "CONVERT",
                {
                    "own_placements": 0,
                    "own_movements": 0,
                    "opponent_movements": 0,
                    "conversions": 1,
                    "removals": 0,
                    "opponent_dependency": True,
                    "realized_opponent_effect": True,
                },
            ),
        )

        for kind, occupied, action, expected_mode, expected_effect in cases:
            with self.subTest(kind=kind, occupied=occupied):
                definition = _one_ply_definition(kind, occupied_target=occupied)
                _, stored = _telemetry_dict(definition, [action])
                decision = stored["decisions"][0]
                self.assertEqual(decision["chosen_effect_mode"], expected_mode)
                for key, value in expected_effect.items():
                    self.assertEqual(decision["chosen_effect"][key], value)
                expected_deltas = {
                    "PLACE": (1, 0, 1),
                    "CAPTURE": (0, -1, -1),
                    "CONVERT": (1, -1, 0),
                }.get(expected_mode, (0, 0, 0))
                self.assertEqual(
                    (
                        decision["chosen_effect"]["own_piece_count_delta"],
                        decision["chosen_effect"]["opponent_piece_count_delta"],
                        decision["chosen_effect"]["occupied_cell_delta"],
                    ),
                    expected_deltas,
                )
                self.assertEqual(
                    (
                        stored["roles"]["A"]["own_piece_count_delta"],
                        stored["roles"]["A"]["opponent_piece_count_delta"],
                        stored["roles"]["A"]["occupied_cell_delta"],
                    ),
                    expected_deltas,
                )

    def test_empty_target_push_swap_and_move_capture_are_ordinary_not_special(self):
        for kind in ("MOVE_CAPTURE", "PUSH", "SWAP"):
            with self.subTest(kind=kind):
                _, stored = _telemetry_dict(
                    _one_ply_definition(kind),
                    [_action(kind)],
                )
                decision = stored["decisions"][0]
                self.assertEqual(decision["chosen_effect_mode"], "ORDINARY_STEP")
                self.assertFalse(decision["chosen_conditional_special"])
                self.assertFalse(decision["chosen_effect"]["opponent_dependency"])
                self.assertFalse(
                    decision["chosen_effect"]["realized_opponent_effect"]
                )

    def test_hop_dependency_is_not_mislabeled_as_a_direct_opponent_effect(self):
        definition = _one_ply_definition("HOP", occupied_target=True)
        _, stored = _telemetry_dict(
            definition,
            [_action("HOP", target=(1, 2))],
        )
        decision = stored["decisions"][0]

        self.assertEqual(decision["chosen_effect_mode"], "HOP")
        self.assertTrue(decision["chosen_effect"]["opponent_dependency"])
        self.assertFalse(
            decision["chosen_effect"]["realized_opponent_effect"]
        )
        self.assertEqual(stored["direct_effect_status"], "NONE")

    def test_legal_action_bins_distinguish_zero_one_and_two_plus(self):
        no_action = _definition(
            pieces=(_piece("B", "b_actor", 2, 0),),
            max_plies=4,
        )
        _, zero = _telemetry_dict(no_action, [])

        one_definition = _one_ply_definition("PUSH")
        _, one = _telemetry_dict(one_definition, [_action("PUSH")])

        two_definition = _definition(
            a_kind="PUSH",
            a_piece="actor",
            a_vectors=[[0, 1], [1, 0]],
            pieces=(
                _piece("A", "actor", 0, 0),
                _piece("B", "b_actor", 2, 2),
            ),
            max_plies=1,
        )
        _, two = _telemetry_dict(
            two_definition,
            [_action("PUSH", origin=(0, 0), target=(0, 1))],
        )

        self.assertEqual(zero["roles"]["A"]["legal_count_bins"], {"0": 1, "1": 0, "2+": 0})
        self.assertEqual(zero["roles"]["A"]["legal_action_count_min"], 0)
        self.assertEqual(zero["roles"]["A"]["legal_action_count_max"], 0)
        self.assertIsNone(zero["roles"]["A"]["forced_fraction"])
        self.assertEqual(one["roles"]["A"]["legal_count_bins"], {"0": 0, "1": 1, "2+": 0})
        self.assertEqual(
            one["roles"]["A"]["forced_fraction"],
            {"numerator": 1, "denominator": 1},
        )
        self.assertEqual(two["roles"]["A"]["legal_count_bins"], {"0": 0, "1": 0, "2+": 1})
        self.assertEqual(
            two["roles"]["A"]["forced_fraction"],
            {"numerator": 0, "denominator": 1},
        )
        self.assertEqual(two["decisions"][0]["successor_position_variant_count"], 2)
        self.assertEqual(two["decisions"][0]["effect_signature_variant_count"], 1)
        self.assertFalse(two["decisions"][0]["immediate_reconvergence"])

    def test_only_no_legal_action_contributes_a_zero_legal_observation(self):
        goal_terminal = _definition(
            pieces=(
                _piece("A", "goal", 0, 0),
                _piece("A", "a_actor", 1, 0),
                _piece("B", "b_actor", 2, 0),
            ),
            a_goal=_reach_goal("goal"),
            max_plies=3,
        )
        _, goal = _telemetry_dict(goal_terminal, [])

        _, ply_limit = _telemetry_dict(
            _one_ply_definition("PUSH"),
            [_action("PUSH")],
        )

        no_action = _definition(
            pieces=(_piece("B", "b_actor", 2, 0),),
            max_plies=3,
        )
        _, stuck = _telemetry_dict(no_action, [])

        self.assertEqual(goal["roles"]["A"]["legal_count_bins"]["0"], 0)
        self.assertEqual(ply_limit["roles"]["B"]["legal_count_bins"]["0"], 0)
        self.assertEqual(stuck["roles"]["A"]["legal_count_bins"]["0"], 1)

    def test_forced_run_terminal_and_work_accounting_follow_the_trace(self):
        definition = _definition(
            a_kind="PUSH",
            b_kind="PUSH",
            a_piece="a_actor",
            b_piece="b_actor",
            a_vectors=[[0, 1]],
            b_vectors=[[0, -1]],
            pieces=(
                _piece("A", "a_actor", 0, 0),
                _piece("B", "b_actor", 2, 2),
            ),
            max_plies=3,
        )
        actions = [
            _action("PUSH", origin=(0, 0), target=(0, 1)),
            _action("PUSH", origin=(2, 2), target=(2, 1)),
            _action("PUSH", origin=(0, 1), target=(0, 2)),
        ]
        _, stored = _telemetry_dict(definition, actions)

        self.assertEqual([item["legal_count"] for item in stored["decisions"]], [1, 1, 1])
        self.assertEqual(stored["longest_forced_run"], 3)
        self.assertEqual(stored["terminal"], {"ply": 3, "winner": None, "reason": "PLY_LIMIT"})
        self.assertEqual(stored["work"]["replayed_actions"], 3)
        self.assertEqual(stored["work"]["decision_count"], 3)
        self.assertEqual(stored["work"]["successor_evaluations"], 3)
        self.assertEqual(
            stored["roles"]["A"]["action_count"]
            + stored["roles"]["B"]["action_count"],
            len(actions),
        )
        for player in ("A", "B"):
            self.assertEqual(
                stored["roles"][player]["decision_count"],
                stored["roles"][player]["action_count"],
            )

    def test_repetition_key_ignores_ply_and_terminal_outcome_but_cycle_prefix_does_not(self):
        definition = _definition(
            a_kind="PUSH",
            b_kind="PUSH",
            a_piece="a_actor",
            b_piece="b_actor",
            a_vectors=[[0, -1], [0, 1]],
            b_vectors=[[0, -1], [0, 1]],
            pieces=(
                _piece("A", "a_actor", 0, 0),
                _piece("B", "b_actor", 2, 2),
            ),
            max_plies=5,
        )
        actions = [
            _action("PUSH", origin=(0, 0), target=(0, 1)),
            _action("PUSH", origin=(2, 2), target=(2, 1)),
            _action("PUSH", origin=(0, 1), target=(0, 0)),
            _action("PUSH", origin=(2, 1), target=(2, 2)),
            _action("PUSH", origin=(0, 0), target=(0, 1)),
        ]
        _, stored = _telemetry_dict(definition, actions)
        repetition = stored["repetition"]

        self.assertTrue(repetition["has_repeated_configuration"])
        self.assertEqual(repetition["first_repeat_ply"], 4)
        self.assertEqual(repetition["first_repeat_period"], 4)
        self.assertTrue(repetition["terminal_configuration_repeated"])
        self.assertEqual(repetition["cycle_prefix_plies"], 4)

    def test_repeat_period_uses_the_previous_occurrence_not_only_the_first(self):
        definition = _definition(
            a_kind="SWAP",
            b_kind="SWAP",
            a_piece="a_actor",
            b_piece="b_actor",
            a_vectors=[[-1, 0], [0, 1], [1, 0]],
            b_vectors=[[-1, 0], [0, 1], [1, 0]],
            pieces=(
                _piece("A", "a_actor", 1, 0),
                _piece("B", "b_actor", 1, 1),
            ),
            max_plies=6,
        )
        actions = [
            _action("SWAP", origin=(1, 0), target=(2, 0)),
            _action("SWAP", origin=(1, 1), target=(2, 1)),
            _action("SWAP", origin=(2, 0), target=(1, 0)),
            _action("SWAP", origin=(2, 1), target=(1, 1)),
            _action("SWAP", origin=(1, 0), target=(1, 1)),
            _action("SWAP", origin=(1, 0), target=(1, 1)),
        ]

        _, stored = _telemetry_dict(definition, actions)
        repetition = stored["repetition"]
        self.assertEqual(repetition["first_repeat_ply"], 4)
        self.assertEqual(repetition["shortest_period"], 2)
        self.assertEqual(
            [
                (
                    event["ply"],
                    event["first_seen_ply"],
                    event["previous_seen_ply"],
                    event["period"],
                )
                for event in repetition["events"]
                if event["ply"] in (4, 6)
            ],
            [(4, 0, 0, 4), (6, 0, 4, 2)],
        )


if __name__ == "__main__":
    unittest.main()
