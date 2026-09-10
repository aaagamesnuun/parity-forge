import ast
import copy
import hashlib
import inspect
import json
import subprocess
import sys
import textwrap
import unittest
from itertools import combinations, product
from math import comb
from pathlib import Path
from unittest import mock

from parity_forge import dsl
from parity_forge.engine import GameState, goal_satisfied, legal_actions
import parity_forge_universe.initial_structure as initial
import parity_forge_universe.schema_v4_compiler as compiler
import parity_forge_universe.typed_occupancy as universe


_BOARD = tuple((row, column) for row in range(3) for column in range(3))
_ACTIONS = (
    "PLACE",
    "MOVE",
    "MOVE_CAPTURE",
    "PUSH",
    "SWAP",
    "HOP",
    "CONVERT",
)
_OWNERS = ("A", "B")
_GOALS = ("CONNECT_EDGES", "REACH_EDGE", "ELIMINATE")
_PROFILES = {
    "NONE": (),
    "ORTHOGONAL_4": ((-1, 0), (0, -1), (0, 1), (1, 0)),
    "DIAGONAL_4": ((-1, -1), (-1, 1), (1, -1), (1, 1)),
    "KING_8": (
        (-1, -1),
        (-1, 0),
        (-1, 1),
        (0, -1),
        (0, 1),
        (1, -1),
        (1, 0),
        (1, 1),
    ),
}
_ACTION_PROFILES = (
    ("PLACE", "NONE"),
    *((action, profile) for action in _ACTIONS[1:] for profile in _PROFILES if profile != "NONE"),
)
_INITIAL_COUNTS = tuple(
    (a_count, b_count)
    for a_count in range(4)
    for b_count in range(4)
    if (a_count, b_count) != (0, 0)
)
_COUNT_STATES = tuple(
    (a_count, b_count)
    for a_count in range(10)
    for b_count in range(10 - a_count)
)
_SETUP_SUPPLIES = {
    (0, 1): 9,
    (0, 2): 36,
    (0, 3): 84,
    (1, 0): 9,
    (1, 1): 72,
    (1, 2): 252,
    (1, 3): 504,
    (2, 0): 36,
    (2, 1): 252,
    (2, 2): 756,
    (2, 3): 1260,
    (3, 0): 84,
    (3, 1): 504,
    (3, 2): 1260,
    (3, 3): 1680,
}
_D4_INVERSES = {
    "I": "I",
    "R90": "R270",
    "R180": "R180",
    "R270": "R90",
    "FLR": "FLR",
    "FTB": "FTB",
    "FD": "FD",
    "FA": "FA",
}
_SETUP_ROWS = None
_OCCUPANCIES = None


def _canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _domain_hash(domain, value):
    return hashlib.sha256(domain + _canonical(value).encode("utf-8")).hexdigest()


def _independent_setup_rows():
    global _SETUP_ROWS
    if _SETUP_ROWS is None:
        rows = []
        for a_count, b_count in _INITIAL_COUNTS:
            for positions_a in combinations(_BOARD, a_count):
                remaining = tuple(cell for cell in _BOARD if cell not in positions_a)
                for positions_b in combinations(remaining, b_count):
                    rows.append((positions_a, positions_b))
        _SETUP_ROWS = tuple(rows)
    return _SETUP_ROWS


def _all_ternary_occupancies():
    global _OCCUPANCIES
    if _OCCUPANCIES is None:
        rows = []
        for assignment in product((0, 1, 2), repeat=9):
            positions_a = tuple(_BOARD[index] for index, value in enumerate(assignment) if value == 1)
            positions_b = tuple(_BOARD[index] for index, value in enumerate(assignment) if value == 2)
            pieces = tuple(
                dsl.InitialPiece(
                    owner=dsl.Player.A if value == 1 else dsl.Player.B,
                    piece="a" if value == 1 else "b",
                    position=_BOARD[index],
                )
                for index, value in enumerate(assignment)
                if value
            )
            rows.append((positions_a, positions_b, pieces))
        _OCCUPANCIES = tuple(rows)
    return _OCCUPANCIES


def _setup(positions_a=((1, 1),), positions_b=((0, 0),)):
    return compiler.TypedSetupV1(1, tuple(positions_a), tuple(positions_b))


def _profile_for_action(action, preferred="ORTHOGONAL_4"):
    return "NONE" if action == "PLACE" else preferred


def _role_payload(action, goal, profile, edges):
    return {
        "action_primitive": action,
        "goal_primitive": goal,
        "vector_profile": profile,
        "target_edges": list(edges),
    }


def _skeleton(
    action_a,
    goal_a,
    profile_a,
    edges_a,
    action_b,
    goal_b,
    profile_b,
    edges_b,
):
    return universe.parse_profiled_skeleton(
        {
            "universe_version": 1,
            "roles": {
                "A": _role_payload(action_a, goal_a, profile_a, edges_a),
                "B": _role_payload(action_b, goal_b, profile_b, edges_b),
            },
        }
    )


def _carrier(skeleton, positions_a=((1, 1),), positions_b=((0, 0),)):
    return compiler.TypedSetupCarrierV1(1, skeleton, _setup(positions_a, positions_b))


def _find_fresh_skeleton(
    action_a,
    profile_a,
    goal_a="REACH_EDGE",
    edges_a=("TOP",),
    *,
    action_b=None,
    profile_b=None,
    goal_b=None,
    edges_b=None,
):
    fillers = (
        ("CONVERT", "REACH_EDGE", "KING_8", ("RIGHT",)),
        ("PUSH", "CONNECT_EDGES", "ORTHOGONAL_4", ("TOP", "BOTTOM")),
        ("PLACE", "REACH_EDGE", "NONE", ("BOTTOM",)),
        ("MOVE_CAPTURE", "ELIMINATE", "DIAGONAL_4", ()),
        ("SWAP", "REACH_EDGE", "DIAGONAL_4", ("LEFT",)),
    )
    if action_b is not None:
        fillers = (
            (
                action_b,
                "REACH_EDGE" if goal_b is None else goal_b,
                _profile_for_action(action_b) if profile_b is None else profile_b,
                ("RIGHT",) if edges_b is None else tuple(edges_b),
            ),
        )
    failures = []
    for candidate_b in fillers:
        try:
            skeleton = _skeleton(
                action_a,
                goal_a,
                profile_a,
                edges_a,
                *candidate_b,
            )
            _carrier(skeleton)
            return skeleton
        except (TypeError, ValueError) as error:
            failures.append(str(error))
    raise AssertionError("no fresh skeleton matched: {}".format(failures))


def _compiled_definition(skeleton):
    member = compiler.TypedDefinitionMemberV1(
        1, _carrier(skeleton), compiler.RoleOwner.A
    )
    encoded = compiler.compile_schema_v4_json_v1(member)
    return dsl.parse_definition(json.loads(encoded))


def _inside(position):
    return 0 <= position[0] < 3 and 0 <= position[1] < 3


def _step(position, vector, factor=1):
    return (
        position[0] + factor * vector[0],
        position[1] + factor * vector[1],
    )


def _edge_cells(edge):
    if edge == "TOP":
        return {(0, column) for column in range(3)}
    if edge == "RIGHT":
        return {(row, 2) for row in range(3)}
    if edge == "BOTTOM":
        return {(2, column) for column in range(3)}
    if edge == "LEFT":
        return {(row, 0) for row in range(3)}
    raise AssertionError(edge)


def _closure(seeds, vectors):
    reached = set(seeds)
    frontier = list(seeds)
    while frontier:
        source = frontier.pop()
        for vector in vectors:
            target = _step(source, vector)
            if _inside(target) and target not in reached:
                reached.add(target)
                frontier.append(target)
    return frozenset(reached)


def _bridging_component_count(positions, edges):
    remaining = set(positions)
    count = 0
    first = _edge_cells(edges[0])
    second = _edge_cells(edges[1])
    while remaining:
        seed = min(remaining)
        component = {seed}
        remaining.remove(seed)
        frontier = [seed]
        while frontier:
            source = frontier.pop()
            for vector in _PROFILES["ORTHOGONAL_4"]:
                target = _step(source, vector)
                if target in remaining:
                    remaining.remove(target)
                    component.add(target)
                    frontier.append(target)
        if component & first and component & second:
            count += 1
    return count


def _goal_oracle(goal, edges, own, opponent):
    if goal == "ELIMINATE":
        return not opponent
    if goal == "REACH_EDGE":
        return bool(set(own) & _edge_cells(edges[0]))
    if goal == "CONNECT_EDGES":
        return _bridging_component_count(own, edges) > 0
    raise AssertionError(goal)


def _legal_oracle(action, vectors, own, opponent):
    own_set = set(own)
    opponent_set = set(opponent)
    occupied = own_set | opponent_set
    records = []

    def add(source, target, branch, dependency=None, direct=False):
        records.append((source, target, branch, dependency, direct))

    if action == "PLACE":
        for target in _BOARD:
            if target not in occupied:
                add(None, target, "EMPTY", None, False)
    else:
        for source in own:
            for vector in vectors:
                adjacent = _step(source, vector)
                landing = _step(source, vector, 2)
                if action == "MOVE":
                    if adjacent not in occupied and _inside(adjacent):
                        add(source, adjacent, "EMPTY")
                elif action == "MOVE_CAPTURE":
                    if adjacent not in occupied and _inside(adjacent):
                        add(source, adjacent, "EMPTY")
                    elif adjacent in opponent_set:
                        add(source, adjacent, "OCCUPIED", "OPPONENT", True)
                elif action == "PUSH":
                    if adjacent not in occupied and _inside(adjacent):
                        add(source, adjacent, "EMPTY")
                    elif adjacent in opponent_set and landing not in occupied and _inside(landing):
                        add(source, adjacent, "OCCUPIED", "OPPONENT", True)
                elif action == "SWAP":
                    if adjacent not in occupied and _inside(adjacent):
                        add(source, adjacent, "EMPTY")
                    elif adjacent in opponent_set:
                        add(source, adjacent, "OCCUPIED", "OPPONENT", True)
                elif action == "HOP":
                    if adjacent not in occupied and _inside(adjacent):
                        add(source, adjacent, "EMPTY")
                    elif adjacent in occupied and landing not in occupied and _inside(landing):
                        dependency = "OPPONENT" if adjacent in opponent_set else "FRIENDLY"
                        add(source, landing, "OCCUPIED", dependency, False)
                elif action == "CONVERT":
                    if adjacent in opponent_set:
                        add(source, adjacent, "OCCUPIED", "OPPONENT", True)
                else:
                    raise AssertionError(action)
    records.sort(key=lambda item: ((-1, -1) if item[0] is None else item[0], item[1]))
    return tuple(records)


def _legal_breakdown_oracle(records):
    empty = sum(record[2] == "EMPTY" for record in records)
    occupied = sum(record[2] == "OCCUPIED" for record in records)
    opponent = sum(record[3] == "OPPONENT" for record in records)
    friendly = sum(record[3] == "FRIENDLY" for record in records)
    direct = sum(record[4] for record in records)
    return {
        "legal_action_count": len(records),
        "empty_destination_action_count": empty,
        "occupied_dependency_action_count": occupied,
        "opponent_dependency_action_count": opponent,
        "friendly_dependency_action_count": friendly,
        "direct_opponent_effect_action_count": direct,
    }


def _support_oracle(
    action,
    vectors,
    goal,
    edges,
    own,
    opponent,
    opponent_action,
    opponent_vectors,
):
    initial_goal = _goal_oracle(goal, edges, own, opponent)
    if action == "PLACE":
        support = frozenset(_BOARD)
        sources = ["PLACE_WHOLE_BOARD"]
    else:
        support_vectors = set(vectors)
        sources = ["OWN_ACTION_VECTORS"]
        if opponent and opponent_action in ("PUSH", "SWAP"):
            support_vectors.update(opponent_vectors)
            sources.append("OPPONENT_RELOCATION_VECTORS")
        support = _closure(own, tuple(sorted(support_vectors)))
    reach_count = None
    bridge_count = None
    target_count = None
    unreachable_count = None
    if goal == "REACH_EDGE":
        reach_count = len(set(support) & _edge_cells(edges[0]))
        reachable = reach_count > 0
    elif goal == "CONNECT_EDGES":
        bridge_count = _bridging_component_count(support, edges)
        reachable = bridge_count > 0
    else:
        lineage_vectors = (
            opponent_vectors
            if opponent_action in ("MOVE", "MOVE_CAPTURE", "PUSH", "SWAP", "HOP")
            else ()
        )
        target_count = len(opponent)
        unreachable_count = sum(
            not bool(set(support) & set(_closure((target,), lineage_vectors)))
            for target in opponent
        )
        reachable = unreachable_count == 0
    return (
        {
            "support_cell_count": len(support),
            "support_sources": sources,
            "reach_target_cell_count": reach_count,
            "connect_bridging_component_count": bridge_count,
            "eliminate_initial_target_count": target_count,
            "eliminate_unreachable_target_count": unreachable_count,
            "goal_reachable": initial_goal or reachable,
        },
        support,
    )


def _manual_successor(action, record, own, opponent):
    source, target, _branch, dependency, _direct = record
    own_after = set(own)
    opponent_after = set(opponent)
    if action == "PLACE":
        own_after.add(target)
    elif action == "CONVERT":
        opponent_after.remove(target)
        own_after.add(target)
    else:
        own_after.remove(source)
        own_after.add(target)
        if action == "MOVE_CAPTURE" and dependency == "OPPONENT":
            opponent_after.remove(target)
        elif action == "PUSH" and dependency == "OPPONENT":
            opponent_after.remove(target)
            opponent_after.add(
                (2 * target[0] - source[0], 2 * target[1] - source[1])
            )
        elif action == "SWAP" and dependency == "OPPONENT":
            opponent_after.remove(target)
            opponent_after.add(source)
    return frozenset(own_after), frozenset(opponent_after)


def _contact_oracle(positions_a, positions_b, vectors_a, vectors_b):
    set_a = set(positions_a)
    set_b = set(positions_b)
    contacts_a = {
        (source, _step(source, vector))
        for source in positions_a
        for vector in vectors_a
        if _step(source, vector) in set_b
    }
    contacts_b = {
        (_step(source, vector), source)
        for source in positions_b
        for vector in vectors_b
        if _step(source, vector) in set_a
    }
    union = contacts_a | contacts_b
    return {
        "role_a_vector_contact_count": len(contacts_a),
        "role_b_vector_contact_count": len(contacts_b),
        "union_cross_owner_contact_count": len(union),
        "any_cross_owner_contact": bool(union),
        "contact_class": "CONTACT" if union else "SEPARATED",
    }


def _count_successors(action, state, actor, *, loose=False):
    a_count, b_count = state
    own, opponent = (a_count, b_count) if actor == "A" else (b_count, a_count)
    empty = 9 - a_count - b_count
    local = set()
    if action == "PLACE":
        if empty > 0:
            local.add((own + 1, opponent))
    elif action in ("MOVE", "PUSH", "HOP"):
        if own > 0 and (loose or empty > 0):
            local.add((own, opponent))
    elif action == "SWAP":
        if own > 0 and (loose or empty > 0 or opponent > 0):
            local.add((own, opponent))
    elif action == "MOVE_CAPTURE":
        if own > 0 and (loose or empty > 0):
            local.add((own, opponent))
        if own > 0 and opponent > 0:
            local.add((own, opponent - 1))
    elif action == "CONVERT":
        if own > 0 and opponent > 0:
            local.add((own + 1, opponent - 1))
    else:
        raise AssertionError(action)
    return tuple(sorted(pair if actor == "A" else (pair[1], pair[0]) for pair in local))


def _state_weight(state):
    return comb(9, state[0]) * comb(9 - state[0], state[1])


def _count_goal(state, role, goal):
    own, opponent = state if role == "A" else (state[1], state[0])
    if goal == "CONNECT_EDGES":
        return own >= 3
    if goal == "REACH_EDGE":
        return own >= 1
    if goal == "ELIMINATE":
        return opponent == 0
    raise AssertionError(goal)


def _count_entry_oracle(action_a, action_b, initial_counts, first_player, *, loose=False):
    layers = [(initial_counts,)]
    place_action_units = 0
    place_scan_units = 0
    vector_units = {"A": 0, "B": 0}
    for ply in range(18):
        actor = first_player if ply % 2 == 0 else ("B" if first_player == "A" else "A")
        action = action_a if actor == "A" else action_b
        for state in layers[ply]:
            weight = _state_weight(state)
            own = state[0] if actor == "A" else state[1]
            empty = 9 - state[0] - state[1]
            if action == "PLACE":
                place_action_units += weight * empty
                place_scan_units += weight * 9
            else:
                vector_units[actor] += weight * own
        next_layer = tuple(
            sorted(
                {
                    target
                    for state in layers[ply]
                    for target in _count_successors(action, state, actor, loose=loose)
                }
            )
        )
        layers.append(next_layer)
    witnesses = {
        role: {
            goal: next(
                (
                    ply
                    for ply, layer in enumerate(layers)
                    if any(_count_goal(state, role, goal) for state in layer)
                ),
                None,
            )
            for goal in _GOALS
        }
        for role in _OWNERS
    }
    state_sum = sum(_state_weight(state) for layer in layers for state in layer)
    maximum_action = place_action_units + 8 * sum(vector_units.values())
    maximum_scan = place_scan_units + 8 * sum(vector_units.values())
    without_reference = {
        "action_pair": {"A": action_a, "B": action_b},
        "initial_counts": {"A": initial_counts[0], "B": initial_counts[1]},
        "first_player": first_player,
        "layers": [[list(state) for state in layer] for layer in layers],
        "minimum_goal_plies": witnesses,
        "state_weight_sum": state_sum,
        "work_coefficients": {
            "place_action_units": place_action_units,
            "place_scan_units": place_scan_units,
            "vector_actor_units": vector_units,
        },
        "maximum_profile_work": {
            "action_candidate_iterations": maximum_action,
            "scan_candidate_iterations": maximum_scan,
        },
    }
    result = dict(without_reference)
    result["entry_reference"] = _domain_hash(
        b"parity-forge:plan0015:count-lattice-entry:v1\0", without_reference
    )
    # Production orders the reference first only at dict construction time;
    # canonical JSON makes insertion order irrelevant.
    return result


def _count_descriptor_oracle():
    transition_edges = [
        {
            "actor": actor,
            "action": action,
            "from": list(state),
            "to": list(target),
        }
        for actor in _OWNERS
        for action in _ACTIONS
        for state in _COUNT_STATES
        for target in _count_successors(action, state, actor)
    ]
    entries = [
        _count_entry_oracle(action_a, action_b, initial_counts, first_player)
        for action_a in _ACTIONS
        for action_b in _ACTIONS
        for initial_counts in _INITIAL_COUNTS
        for first_player in _OWNERS
    ]
    proof = {
        "count_state_count": 55,
        "directed_transition_edge_count": len(transition_edges),
        "action_pair_count": 49,
        "initial_count_pair_count": 15,
        "tempo_count": 2,
        "entry_count": len(entries),
        "layer_membership_count": sum(
            len(layer) for entry in entries for layer in entry["layers"]
        ),
        "maximum_state_weight_sum": max(entry["state_weight_sum"] for entry in entries),
        "maximum_action_candidate_iterations": max(
            entry["maximum_profile_work"]["action_candidate_iterations"] for entry in entries
        ),
        "maximum_scan_candidate_iterations": max(
            entry["maximum_profile_work"]["scan_candidate_iterations"] for entry in entries
        ),
        "universal_state_ceiling": 373_958,
        "universal_action_work_ceiling": 25_507_872,
        "universal_scan_work_ceiling": 25_507_872,
    }
    return {
        "count_lattice_table_version": 1,
        "horizon_plies": 18,
        "action_order": list(_ACTIONS),
        "initial_count_order": [list(state) for state in _INITIAL_COUNTS],
        "first_player_order": list(_OWNERS),
        "count_state_order": [list(state) for state in _COUNT_STATES],
        "transition_edges": transition_edges,
        "entries": entries,
        "proof": proof,
    }


def _transform_position(position, transform):
    row, column = position
    return {
        "I": (row, column),
        "R90": (column, 2 - row),
        "R180": (2 - row, 2 - column),
        "R270": (2 - column, row),
        "FLR": (row, 2 - column),
        "FTB": (2 - row, column),
        "FD": (column, row),
        "FA": (2 - column, 2 - row),
    }[transform]


def _payload(result):
    # Exhaustive tests use the immutable canonical snapshot to avoid invoking
    # the deliberately expensive public full-rederivation serializer per row.
    return json.loads(result._canonical_payload_json)


def _action_shape_specs():
    targets = {
        ("PLACE", "NONE"): ("CONNECT_EDGES", ("TOP", "BOTTOM")),
        ("MOVE", "ORTHOGONAL_4"): ("CONNECT_EDGES", ("RIGHT", "LEFT")),
        ("MOVE", "DIAGONAL_4"): ("REACH_EDGE", ("TOP",)),
        ("MOVE", "KING_8"): ("REACH_EDGE", ("RIGHT",)),
        ("MOVE_CAPTURE", "ORTHOGONAL_4"): ("REACH_EDGE", ("BOTTOM",)),
        ("MOVE_CAPTURE", "DIAGONAL_4"): ("REACH_EDGE", ("LEFT",)),
        ("MOVE_CAPTURE", "KING_8"): ("ELIMINATE", ()),
    }
    return tuple(
        (
            action,
            profile,
            *targets.get((action, profile), ("REACH_EDGE", ("TOP",))),
        )
        for action, profile in _ACTION_PROFILES
    )


def _role_tuple(profiled_role):
    return (
        profiled_role.signature.action_primitive.value,
        profiled_role.signature.goal_primitive.value,
        tuple(edge.value for edge in profiled_role.goal_target.edges),
        _PROFILES[profiled_role.vector_profile.value],
    )


def _static_descriptor_oracle(role_a, role_b):
    actions = (role_a[0], role_b[0])
    goals = (role_a[1], role_b[1])
    vector_counts = (len(role_a[3]), len(role_b[3]))
    special = ("MOVE_CAPTURE", "PUSH", "SWAP", "HOP")
    concepts = set()
    for action in actions:
        if action == "PLACE":
            concepts.add("PLACE")
        elif action == "CONVERT":
            concepts.add("CONVERT")
        else:
            concepts.add("MOVE")
            if action in special:
                concepts.add(action)
    concepts.update(goals)
    concepts = tuple(sorted(concepts))
    substeps = tuple(
        1
        if action == "PLACE"
        else 3
        if action in ("PUSH", "SWAP", "HOP")
        else 2
        for action in actions
    )
    return {
        "structural": {
            "action_kind_count": len(set(actions)),
            "piece_kind_count": 2,
            "state_variable_count": 4,
            "numeric_parameter_count": 2 + 2 * sum(vector_counts),
            "victory_clause_count": 2,
            "exception_clause_count": 0,
            "phase_count": 1,
        },
        "description_clause": {
            "independent_statement_count": 12 + sum(action in special for action in actions),
            "conditional_clause_count": (
                5
                + int("MOVE_CAPTURE" in actions)
                + actions.count("PUSH")
                + actions.count("SWAP")
                + actions.count("HOP")
            ),
            "exception_clause_count": 0,
        },
        "operational_substep": {
            "maximum_action_parameter_count": 2 if actions == ("PLACE", "PLACE") else 4,
            "tracked_field_count": 5,
            "action_substep_counts": {
                "A": substeps[0],
                "B": substeps[1],
                "total": sum(substeps),
            },
        },
        "primitive_concept": {
            "primitive_concepts": list(concepts),
            "primitive_concept_count": len(concepts),
            "learned_concept_count": len(concepts) + 6,
        },
        "vector_cardinality": {
            "A": vector_counts[0],
            "B": vector_counts[1],
            "total": sum(vector_counts),
            "maximum": max(vector_counts),
        },
    }


def _count_reference_oracle(entry, goal_a, goal_b, vector_count_a, vector_count_b):
    coefficients = entry["work_coefficients"]
    vector_units = coefficients["vector_actor_units"]
    vector_work = vector_count_a * vector_units["A"] + vector_count_b * vector_units["B"]
    return {
        "first_player": entry["first_player"],
        "entry_reference": entry["entry_reference"],
        "minimum_goal_plies": {
            "A": entry["minimum_goal_plies"]["A"][goal_a],
            "B": entry["minimum_goal_plies"]["B"][goal_b],
        },
        "state_weight_sum": entry["state_weight_sum"],
        "work": {
            "action_candidate_iterations": coefficients["place_action_units"] + vector_work,
            "scan_candidate_iterations": coefficients["place_scan_units"] + vector_work,
        },
    }


def _reasons_oracle(role_facts, count_references):
    reasons = []
    codes = (
        "ZERO_ACTOR_WITH_NONPLACE",
        "INITIAL_GOAL_SATISFIED",
        "INITIAL_IMMOBILITY",
        "OPTIMISTIC_GOAL_UNREACHABLE",
        "COUNT_LATTICE_GOAL_UNREACHABLE_WITHIN_18",
    )
    for code in codes:
        if code == "COUNT_LATTICE_GOAL_UNREACHABLE_WITHIN_18":
            for role in _OWNERS:
                for reference in count_references:
                    if reference["minimum_goal_plies"][role] is None:
                        reasons.append(
                            {
                                "code": code,
                                "role": role,
                                "first_player": reference["first_player"],
                            }
                        )
            continue
        for role in _OWNERS:
            fact = role_facts[role]
            reject = {
                "ZERO_ACTOR_WITH_NONPLACE": fact["initial_actor_count"] == 0
                and fact["action"] != "PLACE",
                "INITIAL_GOAL_SATISFIED": fact["initial_goal_satisfied"],
                "INITIAL_IMMOBILITY": fact["legal"]["legal_action_count"] == 0,
                "OPTIMISTIC_GOAL_UNREACHABLE": not fact["optimistic_support"]["goal_reachable"],
            }[code]
            if reject:
                reasons.append({"code": code, "role": role, "first_player": None})
    return reasons


class IndependentSetupDomainTests(unittest.TestCase):
    def test_independent_setup_domain_has_fixed_supplies_and_endpoints(self):
        rows = _independent_setup_rows()
        observed = {}
        for positions_a, positions_b in rows:
            key = (len(positions_a), len(positions_b))
            observed[key] = observed.get(key, 0) + 1
        self.assertEqual(len(rows), 6798)
        self.assertEqual(observed, _SETUP_SUPPLIES)
        self.assertEqual(rows[0], ((), ((0, 0),)))
        self.assertEqual(
            rows[-1],
            (
                ((2, 0), (2, 1), (2, 2)),
                ((1, 0), (1, 1), (1, 2)),
            ),
        )


class CountLatticeOracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.expected = _count_descriptor_oracle()
        cls.descriptor = initial.build_count_lattice_descriptor_v1()
        cls.actual = cls.descriptor.to_dict()

    def test_complete_descriptor_matches_independent_matrix_and_schedule_oracle(self):
        self.assertEqual(self.actual, self.expected)
        self.assertEqual(
            self.actual["proof"],
            {
                "count_state_count": 55,
                "directed_transition_edge_count": 610,
                "action_pair_count": 49,
                "initial_count_pair_count": 15,
                "tempo_count": 2,
                "entry_count": 1470,
                "layer_membership_count": 22428,
                "maximum_state_weight_sum": 115194,
                "maximum_action_candidate_iterations": 2070432,
                "maximum_scan_candidate_iterations": 2070432,
                "universal_state_ceiling": 373958,
                "universal_action_work_ceiling": 25507872,
                "universal_scan_work_ceiling": 25507872,
            },
        )

    def test_tight_relation_excludes_exactly_the_loose_full_board_stutters(self):
        tight_edges = sum(
            len(_count_successors(action, state, actor))
            for actor in _OWNERS
            for action in _ACTIONS
            for state in _COUNT_STATES
        )
        loose_edges = sum(
            len(_count_successors(action, state, actor, loose=True))
            for actor in _OWNERS
            for action in _ACTIONS
            for state in _COUNT_STATES
        )
        changed_tables = 0
        changed_memberships = 0
        for action_a in _ACTIONS:
            for action_b in _ACTIONS:
                for counts in _INITIAL_COUNTS:
                    for first in _OWNERS:
                        tight = _count_entry_oracle(action_a, action_b, counts, first)
                        loose = _count_entry_oracle(
                            action_a, action_b, counts, first, loose=True
                        )
                        if tight["layers"] != loose["layers"]:
                            changed_tables += 1
                            changed_memberships += sum(
                                len(
                                    {tuple(state) for state in tight_layer}
                                    ^ {tuple(state) for state in loose_layer}
                                )
                                for tight_layer, loose_layer in zip(
                                    tight["layers"], loose["layers"]
                                )
                            )
        self.assertEqual((tight_edges, loose_edges), (610, 684))
        self.assertEqual((changed_tables, changed_memberships), (192, 336))

        for actor in _OWNERS:
            state = (4, 5)
            own = state if actor == "A" else (state[1], state[0])
            self.assertEqual(_count_successors("MOVE", state, actor), ())
            self.assertEqual(_count_successors("PUSH", state, actor), ())
            self.assertEqual(_count_successors("HOP", state, actor), ())
            expected_swap = (state,) if own[0] and own[1] else ()
            self.assertEqual(_count_successors("SWAP", state, actor), expected_swap)

    def test_ply18_tempo_witnesses_and_work_goldens_are_exact(self):
        by_key = {
            (
                entry["action_pair"]["A"],
                entry["action_pair"]["B"],
                tuple(entry["initial_counts"].values()),
                entry["first_player"],
            ): entry
            for entry in self.actual["entries"]
        }
        a_first = by_key[("PLACE", "MOVE_CAPTURE", (0, 1), "A")]
        b_first = by_key[("PLACE", "MOVE_CAPTURE", (0, 1), "B")]
        self.assertEqual(
            {tuple(state) for state in a_first["layers"][18]},
            {(count, 1) for count in range(8)},
        )
        self.assertEqual(
            {tuple(state) for state in b_first["layers"][18]},
            {(count, 1) for count in range(1, 9)},
        )
        connect_a = by_key[("PLACE", "MOVE", (1, 1), "A")]
        connect_b = by_key[("PLACE", "MOVE", (1, 1), "B")]
        self.assertEqual(connect_a["minimum_goal_plies"]["A"]["CONNECT_EDGES"], 3)
        self.assertEqual(connect_b["minimum_goal_plies"]["A"]["CONNECT_EDGES"], 4)
        self.assertEqual(
            (
                connect_a["state_weight_sum"],
                connect_a["maximum_profile_work"]["action_candidate_iterations"],
                connect_a["maximum_profile_work"]["scan_candidate_iterations"],
            ),
            (4509, 26928, 38358),
        )
        self.assertEqual(
            (
                connect_b["state_weight_sum"],
                connect_b["maximum_profile_work"]["action_candidate_iterations"],
                connect_b["maximum_profile_work"]["scan_candidate_iterations"],
            ),
            (4581, 27504, 38934),
        )
        maxima = [
            entry
            for entry in self.actual["entries"]
            if entry["state_weight_sum"] == 115194
        ]
        self.assertEqual(len(maxima), 2)
        self.assertEqual(
            {
                (
                    item["action_pair"]["A"],
                    item["action_pair"]["B"],
                    tuple(item["initial_counts"].values()),
                    item["first_player"],
                )
                for item in maxima
            },
            {
                ("MOVE_CAPTURE", "MOVE_CAPTURE", (3, 3), "A"),
                ("MOVE_CAPTURE", "MOVE_CAPTURE", (3, 3), "B"),
            },
        )

    def test_descriptor_canonical_identity_detachment_and_mutation_guards(self):
        canonical = initial.canonical_count_lattice_descriptor_json_v1(self.descriptor)
        expected_canonical = _canonical(self.expected)
        expected_hash = hashlib.sha256(
            b"parity-forge:plan0015:count-lattice-table:v1\0"
            + expected_canonical.encode("utf-8")
        ).hexdigest()
        self.assertEqual(canonical, expected_canonical)
        self.assertEqual(initial.count_lattice_descriptor_hash_v1(self.descriptor), expected_hash)
        exported = self.descriptor.to_dict()
        exported["entries"].clear()
        self.assertEqual(len(self.descriptor.to_dict()["entries"]), 1470)

        mutated = initial.build_count_lattice_descriptor_v1()
        object.__setattr__(mutated, "count_lattice_table_version", 2)
        for operation in (
            initial.canonical_count_lattice_descriptor_json_v1,
            initial.count_lattice_descriptor_hash_v1,
        ):
            with self.subTest(operation=operation.__name__):
                with self.assertRaises((TypeError, ValueError)):
                    operation(mutated)


class AuthoritativeFormulaDifferentialTests(unittest.TestCase):
    _LEGAL_AGGREGATE_GOLDENS = {
        ("PLACE", "NONE"): (59049, 59049, 0, 0, 0, 0),
        ("MOVE", "ORTHOGONAL_4"): (52488, 52488, 0, 0, 0, 0),
        ("MOVE", "DIAGONAL_4"): (34992, 34992, 0, 0, 0, 0),
        ("MOVE", "KING_8"): (87480, 87480, 0, 0, 0, 0),
        ("MOVE_CAPTURE", "ORTHOGONAL_4"): (104976, 52488, 52488, 52488, 0, 52488),
        ("MOVE_CAPTURE", "DIAGONAL_4"): (69984, 34992, 34992, 34992, 0, 34992),
        ("MOVE_CAPTURE", "KING_8"): (174960, 87480, 87480, 87480, 0, 87480),
        ("PUSH", "ORTHOGONAL_4"): (61236, 52488, 8748, 8748, 0, 8748),
        ("PUSH", "DIAGONAL_4"): (37908, 34992, 2916, 2916, 0, 2916),
        ("PUSH", "KING_8"): (99144, 87480, 11664, 11664, 0, 11664),
        ("SWAP", "ORTHOGONAL_4"): (104976, 52488, 52488, 52488, 0, 52488),
        ("SWAP", "DIAGONAL_4"): (69984, 34992, 34992, 34992, 0, 34992),
        ("SWAP", "KING_8"): (174960, 87480, 87480, 87480, 0, 87480),
        ("HOP", "ORTHOGONAL_4"): (69984, 52488, 17496, 8748, 8748, 0),
        ("HOP", "DIAGONAL_4"): (40824, 34992, 5832, 2916, 2916, 0),
        ("HOP", "KING_8"): (110808, 87480, 23328, 11664, 11664, 0),
        ("CONVERT", "ORTHOGONAL_4"): (52488, 0, 52488, 52488, 0, 52488),
        ("CONVERT", "DIAGONAL_4"): (34992, 0, 34992, 34992, 0, 34992),
        ("CONVERT", "KING_8"): (87480, 0, 87480, 87480, 0, 87480),
    }

    @classmethod
    def setUpClass(cls):
        cls.shapes = []
        for action, profile, goal, edges in _action_shape_specs():
            skeleton = _find_fresh_skeleton(action, profile, goal, edges)
            cls.shapes.append(
                (action, profile, goal, edges, skeleton, _compiled_definition(skeleton))
            )

    def test_all_19_action_profiles_on_all_ternary_boards_match_engine_and_dependencies(self):
        self.assertEqual(len(self.shapes), 19)
        total_legal = 0
        for action, profile, goal, edges, skeleton, definition in self.shapes:
            vectors = _PROFILES[profile]
            role_b = _role_tuple(skeleton.role_b)
            aggregate = [0, 0, 0, 0, 0, 0]
            for positions_a, positions_b, pieces in _all_ternary_occupancies():
                records = _legal_oracle(action, vectors, positions_a, positions_b)
                expected_breakdown = _legal_breakdown_oracle(records)
                state = GameState(
                    ply=0,
                    to_move=dsl.Player.A,
                    pieces=pieces,
                    outcome=None,
                )
                observed_actions = legal_actions(definition, state)
                self.assertEqual(
                    tuple((item.from_position, item.to_position) for item in observed_actions),
                    tuple((item[0], item[1]) for item in records),
                )
                self.assertEqual(
                    initial._legal_breakdown(
                        action, vectors, positions_a, positions_b
                    ),
                    expected_breakdown,
                )
                expected_support_a, support_a = _support_oracle(
                    action,
                    vectors,
                    goal,
                    edges,
                    positions_a,
                    positions_b,
                    role_b[0],
                    role_b[3],
                )
                self.assertEqual(
                    initial._support_value(
                        action,
                        vectors,
                        goal,
                        edges,
                        positions_a,
                        positions_b,
                        role_b[0],
                        role_b[3],
                        _goal_oracle(goal, edges, positions_a, positions_b),
                    ),
                    expected_support_a,
                )
                _expected_support_b, support_b = _support_oracle(
                    role_b[0],
                    role_b[3],
                    role_b[1],
                    role_b[2],
                    positions_b,
                    positions_a,
                    action,
                    vectors,
                )
                for record in records:
                    own_after, opponent_after = _manual_successor(
                        action, record, positions_a, positions_b
                    )
                    self.assertTrue(own_after <= support_a)
                    self.assertTrue(opponent_after <= support_b)

                values = (
                    expected_breakdown["legal_action_count"],
                    expected_breakdown["empty_destination_action_count"],
                    expected_breakdown["occupied_dependency_action_count"],
                    expected_breakdown["opponent_dependency_action_count"],
                    expected_breakdown["friendly_dependency_action_count"],
                    expected_breakdown["direct_opponent_effect_action_count"],
                )
                aggregate = [left + right for left, right in zip(aggregate, values)]
            with self.subTest(action=action, profile=profile):
                self.assertEqual(tuple(aggregate), self._LEGAL_AGGREGATE_GOLDENS[(action, profile)])
            total_legal += aggregate[0]
        self.assertEqual(total_legal, 1_528_713)

    def test_all_seven_goal_targets_on_all_ternary_boards_match_engine(self):
        targets = (
            ("CONNECT_EDGES", ("TOP", "BOTTOM"), 2539),
            ("CONNECT_EDGES", ("RIGHT", "LEFT"), 2539),
            ("REACH_EDGE", ("TOP",), 13851),
            ("REACH_EDGE", ("RIGHT",), 13851),
            ("REACH_EDGE", ("BOTTOM",), 13851),
            ("REACH_EDGE", ("LEFT",), 13851),
            ("ELIMINATE", (), 512),
        )
        for goal, edges, truth_golden in targets:
            action = "MOVE_CAPTURE" if goal == "ELIMINATE" else "PUSH"
            skeleton = _find_fresh_skeleton(
                action,
                "ORTHOGONAL_4",
                goal,
                edges,
            )
            definition = _compiled_definition(skeleton)
            truth_count = 0
            for positions_a, positions_b, pieces in _all_ternary_occupancies():
                expected = _goal_oracle(goal, edges, positions_a, positions_b)
                self.assertEqual(
                    initial._initial_goal(goal, edges, positions_a, positions_b),
                    expected,
                )
                self.assertEqual(
                    goal_satisfied(definition, pieces, dsl.Player.A), expected
                )
                truth_count += expected
            with self.subTest(goal=goal, edges=edges):
                self.assertEqual(truth_count, truth_golden)


class PublicMasterDomainDifferentialTests(unittest.TestCase):
    _MASTER_AGGREGATE_GOLDENS = {
        ("PLACE", "NONE"): (29124, 29124, 0, 0, 0, 0),
        ("MOVE", "ORTHOGONAL_4"): (21696, 21696, 0, 0, 0, 0),
        ("MOVE", "DIAGONAL_4"): (14464, 14464, 0, 0, 0, 0),
        ("MOVE", "KING_8"): (36160, 36160, 0, 0, 0, 0),
        ("MOVE_CAPTURE", "ORTHOGONAL_4"): (34152, 21696, 12456, 12456, 0, 12456),
        ("MOVE_CAPTURE", "DIAGONAL_4"): (22768, 14464, 8304, 8304, 0, 8304),
        ("MOVE_CAPTURE", "KING_8"): (56920, 36160, 20760, 20760, 0, 20760),
        ("PUSH", "ORTHOGONAL_4"): (25092, 21696, 3396, 3396, 0, 3396),
        ("PUSH", "DIAGONAL_4"): (15596, 14464, 1132, 1132, 0, 1132),
        ("PUSH", "KING_8"): (40688, 36160, 4528, 4528, 0, 4528),
        ("SWAP", "ORTHOGONAL_4"): (34152, 21696, 12456, 12456, 0, 12456),
        ("SWAP", "DIAGONAL_4"): (22768, 14464, 8304, 8304, 0, 8304),
        ("SWAP", "KING_8"): (56920, 36160, 20760, 20760, 0, 20760),
        ("HOP", "ORTHOGONAL_4"): (27468, 21696, 5772, 3396, 2376, 0),
        ("HOP", "DIAGONAL_4"): (16388, 14464, 1924, 1132, 792, 0),
        ("HOP", "KING_8"): (43856, 36160, 7696, 4528, 3168, 0),
        ("CONVERT", "ORTHOGONAL_4"): (12456, 0, 12456, 12456, 0, 12456),
        ("CONVERT", "DIAGONAL_4"): (8304, 0, 8304, 8304, 0, 8304),
        ("CONVERT", "KING_8"): (20760, 0, 20760, 20760, 0, 20760),
    }

    @classmethod
    def setUpClass(cls):
        expected_descriptor = _count_descriptor_oracle()
        cls.entry_map = {
            (
                entry["action_pair"]["A"],
                entry["action_pair"]["B"],
                entry["initial_counts"]["A"],
                entry["initial_counts"]["B"],
                entry["first_player"],
            ): entry
            for entry in expected_descriptor["entries"]
        }
        cls.table_root = hashlib.sha256(
            b"parity-forge:plan0015:count-lattice-table:v1\0"
            + _canonical(expected_descriptor).encode("utf-8")
        ).hexdigest()

    def test_all_19_action_profiles_across_all_6798_master_setups(self):
        observed_targets = set()
        for action, profile, goal, edges in _action_shape_specs():
            skeleton = _find_fresh_skeleton(action, profile, goal, edges)
            role_a = _role_tuple(skeleton.role_a)
            role_b = _role_tuple(skeleton.role_b)
            prepared = initial.prepare_initial_structure_skeleton_v1(
                _carrier(skeleton)
            )
            aggregate = [0, 0, 0, 0, 0, 0]
            goal_true_count = 0
            for positions_a, positions_b in _independent_setup_rows():
                carrier = _carrier(skeleton, positions_a, positions_b)
                value = _payload(
                    initial.derive_prepared_initial_structure_result_v1(
                        prepared, carrier
                    )
                )
                expected_facts = {}
                supports = {}
                for owner, own_role, opponent_role, own, opponent in (
                    ("A", role_a, role_b, positions_a, positions_b),
                    ("B", role_b, role_a, positions_b, positions_a),
                ):
                    records = _legal_oracle(own_role[0], own_role[3], own, opponent)
                    legal = _legal_breakdown_oracle(records)
                    support, support_cells = _support_oracle(
                        own_role[0],
                        own_role[3],
                        own_role[1],
                        own_role[2],
                        own,
                        opponent,
                        opponent_role[0],
                        opponent_role[3],
                    )
                    supports[owner] = support_cells
                    expected_facts[owner] = {
                        "role": owner,
                        "action": own_role[0],
                        "goal": own_role[1],
                        "target_edges": list(own_role[2]),
                        "initial_actor_count": len(own),
                        "initial_opponent_count": len(opponent),
                        "initial_goal_satisfied": _goal_oracle(
                            own_role[1], own_role[2], own, opponent
                        ),
                        "legal": legal,
                        "optimistic_support": support,
                    }
                self.assertEqual(value["role_facts"], expected_facts)

                counts = (len(positions_a), len(positions_b))
                expected_references = []
                for first in _OWNERS:
                    entry = self.entry_map[
                        (role_a[0], role_b[0], counts[0], counts[1], first)
                    ]
                    expected_references.append(
                        _count_reference_oracle(
                            entry,
                            role_a[1],
                            role_b[1],
                            len(role_a[3]),
                            len(role_b[3]),
                        )
                    )
                self.assertEqual(
                    value["count_lattice"],
                    {
                        "table_version": 1,
                        "table_root": self.table_root,
                        "action_pair": {"A": role_a[0], "B": role_b[0]},
                        "initial_counts": {"A": counts[0], "B": counts[1]},
                        "tempo_references": expected_references,
                    },
                )
                expected_reasons = _reasons_oracle(expected_facts, expected_references)
                self.assertEqual(value["rejection_reasons"], expected_reasons)
                self.assertEqual(value["eligible"], not expected_reasons)

                static = _static_descriptor_oracle(role_a, role_b)
                static["operational_substep"]["initial_legal_action_counts"] = {
                    "A": expected_facts["A"]["legal"]["legal_action_count"],
                    "B": expected_facts["B"]["legal"]["legal_action_count"],
                    "total": sum(
                        expected_facts[owner]["legal"]["legal_action_count"]
                        for owner in _OWNERS
                    ),
                }
                occupied = sum(counts)
                static["density"] = {
                    "initial_piece_counts": {"A": counts[0], "B": counts[1]},
                    "initial_occupied_count": occupied,
                    "initial_empty_cell_count": 9 - occupied,
                    "role_piece_fractions": {
                        "A": {"numerator": counts[0], "denominator": 9},
                        "B": {"numerator": counts[1], "denominator": 9},
                    },
                    "initial_occupancy_fraction": {"numerator": occupied, "denominator": 9},
                    "initial_empty_fraction": {"numerator": 9 - occupied, "denominator": 9},
                }
                static["contact"] = _contact_oracle(
                    positions_a, positions_b, role_a[3], role_b[3]
                )
                static["dependency"] = {
                    owner: expected_facts[owner]["legal"] for owner in _OWNERS
                }
                self.assertEqual(value["descriptor_groups"], static)

                self.assertEqual(
                    value["identities"],
                    {
                        "typed_setup_hash": compiler.typed_setup_hash_v1(carrier.setup),
                        "typed_skeleton_hash": universe.profiled_skeleton_hash(skeleton),
                        "typed_carrier_hash": compiler.typed_setup_carrier_hash_v1(carrier),
                        "typed_carrier_canonical_byte_count": len(
                            compiler.canonical_typed_setup_carrier_json_v1(carrier).encode("utf-8")
                        ),
                    },
                )
                body = dict(value)
                evidence_digest = body.pop("evidence_digest")
                self.assertEqual(
                    evidence_digest,
                    hashlib.sha256(
                        b"parity-forge:plan0015:initial-structure-result-evidence:v1\0"
                        + _canonical(body).encode("utf-8")
                    ).hexdigest(),
                )

                records_a = _legal_oracle(action, role_a[3], positions_a, positions_b)
                for record in records_a:
                    own_after, opponent_after = _manual_successor(
                        action, record, positions_a, positions_b
                    )
                    self.assertTrue(own_after <= supports["A"])
                    self.assertTrue(opponent_after <= supports["B"])
                legal = expected_facts["A"]["legal"]
                values = tuple(legal[key] for key in (
                    "legal_action_count",
                    "empty_destination_action_count",
                    "occupied_dependency_action_count",
                    "opponent_dependency_action_count",
                    "friendly_dependency_action_count",
                    "direct_opponent_effect_action_count",
                ))
                aggregate = [left + right for left, right in zip(aggregate, values)]
                goal_true_count += expected_facts["A"]["initial_goal_satisfied"]

            with self.subTest(action=action, profile=profile, goal=goal, edges=edges):
                self.assertEqual(tuple(aggregate), self._MASTER_AGGREGATE_GOLDENS[(action, profile)])
                expected_goal_count = {
                    ("CONNECT_EDGES", ("TOP", "BOTTOM")): 126,
                    ("CONNECT_EDGES", ("RIGHT", "LEFT")): 126,
                    ("REACH_EDGE", ("TOP",)): 4311,
                    ("REACH_EDGE", ("RIGHT",)): 4311,
                    ("REACH_EDGE", ("BOTTOM",)): 4311,
                    ("REACH_EDGE", ("LEFT",)): 4311,
                    ("ELIMINATE", ()): 129,
                }[(goal, edges)]
                self.assertEqual(goal_true_count, expected_goal_count)
            observed_targets.add((goal, edges))
        self.assertEqual(
            observed_targets,
            {
                ("CONNECT_EDGES", ("TOP", "BOTTOM")),
                ("CONNECT_EDGES", ("RIGHT", "LEFT")),
                ("REACH_EDGE", ("TOP",)),
                ("REACH_EDGE", ("RIGHT",)),
                ("REACH_EDGE", ("BOTTOM",)),
                ("REACH_EDGE", ("LEFT",)),
                ("ELIMINATE", ()),
            },
        )


class PublicKernelContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skeleton = _skeleton(
            "CONVERT",
            "CONNECT_EDGES",
            "DIAGONAL_4",
            ("RIGHT", "LEFT"),
            "CONVERT",
            "CONNECT_EDGES",
            "KING_8",
            ("RIGHT", "LEFT"),
        )
        cls.carrier = _carrier(
            cls.skeleton,
            ((0, 0), (1, 1), (2, 0)),
            ((0, 1), (2, 2)),
        )
        cls.prepared = initial.prepare_initial_structure_skeleton_v1(cls.carrier)
        cls.result = initial.derive_prepared_initial_structure_result_v1(
            cls.prepared, cls.carrier
        )
        cls.value = cls.result.to_dict()

    def test_public_versions_shape_and_prepared_equivalence(self):
        self.assertEqual(
            (
                initial.INITIAL_STRUCTURE_KERNEL_VERSION_V1,
                initial.INITIAL_STRUCTURE_RESULT_VERSION_V1,
                initial.PREPARED_INITIAL_STRUCTURE_VERSION_V1,
                initial.COUNT_LATTICE_TABLE_VERSION_V1,
            ),
            (1, 1, 1, 1),
        )
        self.assertEqual(
            set(self.value),
            {
                "carrier",
                "count_lattice",
                "descriptor_groups",
                "eligible",
                "evidence_digest",
                "identities",
                "initial_structure_result_version",
                "kernel_version",
                "rejection_reasons",
                "role_facts",
            },
        )
        ordinary = initial.derive_initial_structure_result_v1(self.carrier)
        self.assertEqual(
            initial.canonical_initial_structure_result_json_v1(ordinary),
            initial.canonical_initial_structure_result_json_v1(self.result),
        )
        self.assertEqual(tuple(self.value["role_facts"]), ("A", "B"))
        self.assertEqual(
            tuple(reference["first_player"] for reference in self.value["count_lattice"]["tempo_references"]),
            ("A", "B"),
        )
        self.assertEqual(self.value["eligible"], not self.value["rejection_reasons"])

    def test_exact_role_density_contact_and_dependency_facts(self):
        positions_a = self.carrier.setup.role_a_positions
        positions_b = self.carrier.setup.role_b_positions
        roles = {
            "A": (
                "CONVERT",
                _PROFILES["DIAGONAL_4"],
                "CONNECT_EDGES",
                ("RIGHT", "LEFT"),
                positions_a,
                positions_b,
                "CONVERT",
                _PROFILES["KING_8"],
            ),
            "B": (
                "CONVERT",
                _PROFILES["KING_8"],
                "CONNECT_EDGES",
                ("RIGHT", "LEFT"),
                positions_b,
                positions_a,
                "CONVERT",
                _PROFILES["DIAGONAL_4"],
            ),
        }
        for owner, data in roles.items():
            action, vectors, goal, edges, own, opponent, opponent_action, opponent_vectors = data
            records = _legal_oracle(action, vectors, own, opponent)
            support, _cells = _support_oracle(
                action,
                vectors,
                goal,
                edges,
                own,
                opponent,
                opponent_action,
                opponent_vectors,
            )
            fact = self.value["role_facts"][owner]
            self.assertEqual(fact["initial_goal_satisfied"], _goal_oracle(goal, edges, own, opponent))
            self.assertEqual(fact["legal"], _legal_breakdown_oracle(records))
            self.assertEqual(fact["optimistic_support"], support)
            self.assertEqual(self.value["descriptor_groups"]["dependency"][owner], fact["legal"])

        density = self.value["descriptor_groups"]["density"]
        self.assertEqual(
            density,
            {
                "initial_piece_counts": {"A": 3, "B": 2},
                "initial_occupied_count": 5,
                "initial_empty_cell_count": 4,
                "role_piece_fractions": {
                    "A": {"numerator": 3, "denominator": 9},
                    "B": {"numerator": 2, "denominator": 9},
                },
                "initial_occupancy_fraction": {"numerator": 5, "denominator": 9},
                "initial_empty_fraction": {"numerator": 4, "denominator": 9},
            },
        )
        self.assertEqual(
            self.value["descriptor_groups"]["contact"],
            _contact_oracle(
                positions_a,
                positions_b,
                _PROFILES["DIAGONAL_4"],
                _PROFILES["KING_8"],
            ),
        )

    def test_result_roundtrip_canonical_hash_validation_and_detachment(self):
        parsed = initial.parse_initial_structure_result_v1(copy.deepcopy(self.value))
        canonical = initial.canonical_initial_structure_result_json_v1(parsed)
        self.assertEqual(canonical, _canonical(self.value))
        self.assertEqual(
            initial.initial_structure_result_hash_v1(parsed),
            hashlib.sha256(
                b"parity-forge:plan0015:initial-structure-result:v1\0"
                + canonical.encode("utf-8")
            ).hexdigest(),
        )
        validated = initial.validate_initial_structure_result_v1(self.carrier, parsed)
        self.assertEqual(initial.canonical_initial_structure_result_json_v1(validated), canonical)
        exported = parsed.to_dict()
        exported["role_facts"].clear()
        self.assertEqual(set(parsed.to_dict()["role_facts"]), {"A", "B"})

    def test_fresh_prepared_snapshot_matches_the_fully_revalidated_result(self):
        snapshot = initial.derive_prepared_initial_structure_snapshot_v1(
            self.prepared, self.carrier
        )
        self.assertIs(type(snapshot), tuple)
        self.assertEqual(len(snapshot), 2)
        self.assertTrue(all(type(item) is str for item in snapshot))
        canonical, result_hash = snapshot
        self.assertEqual(canonical, self.result._canonical_payload_json)
        self.assertEqual(
            self.prepared.skeleton_hash,
            hashlib.sha256(
                b"parity-forge:typed-occupancy:skeleton:v1\0"
                + self.prepared.skeleton_json.encode("utf-8")
            ).hexdigest(),
        )
        self.assertEqual(
            result_hash,
            initial.initial_structure_result_hash_v1(self.result),
        )
        detached = json.loads(canonical)
        self.assertEqual(
            detached["identities"],
            {
                "typed_setup_hash": compiler.typed_setup_hash_v1(
                    self.carrier.setup
                ),
                "typed_skeleton_hash": universe.profiled_skeleton_hash(
                    self.carrier.skeleton
                ),
                "typed_carrier_hash": compiler.typed_setup_carrier_hash_v1(
                    self.carrier
                ),
                "typed_carrier_canonical_byte_count": len(
                    compiler.canonical_typed_setup_carrier_json_v1(
                        self.carrier
                    ).encode("utf-8")
                ),
            },
        )
        detached["role_facts"].clear()
        self.assertEqual(
            set(json.loads(snapshot[0])["role_facts"]),
            {"A", "B"},
        )

        other = _carrier(_find_fresh_skeleton("PUSH", "KING_8"))
        with self.assertRaises((TypeError, ValueError)):
            initial.derive_prepared_initial_structure_snapshot_v1(
                self.prepared, other
            )

        for target, name, replacement in (
            (initial, "_derive_payload", lambda *_args, **_kwargs: {}),
            (initial, "_detach_carrier", lambda *_args, **_kwargs: ()),
            (initial, "_canonical_json", lambda _value: "{}"),
            (initial, "_domain_hash", lambda *_args: "0" * 64),
        ):
            with self.subTest(name=name):
                with mock.patch.object(target, name, replacement):
                    with self.assertRaises(initial.InitialStructureClosureError):
                        initial.derive_prepared_initial_structure_snapshot_v1(
                            self.prepared, self.carrier
                        )

    def test_fresh_snapshot_detaches_caller_carrier_and_prepared_state(self):
        carrier = _carrier(self.skeleton, ((1, 1),), ((0, 0),))
        original_setup = compiler.canonical_typed_setup_json_v1(carrier.setup)
        replacement_carrier = _carrier(
            self.skeleton,
            ((0, 0), (1, 1), (2, 2)),
            ((0, 1), (2, 1)),
        )
        prepared = initial.prepare_initial_structure_skeleton_v1(carrier)
        other_carrier = _carrier(
            _find_fresh_skeleton("PUSH", "KING_8"),
            ((1, 1),),
            ((0, 0),),
        )
        other_prepared = initial.prepare_initial_structure_skeleton_v1(
            other_carrier
        )
        source_lines, source_start = inspect.getsourcelines(initial._derive_payload)
        target_line = source_start + next(
            index
            for index, line in enumerate(source_lines)
            if "role_a, role_b =" in line
        )
        changed = {"done": False}

        def mutate_callers(frame, event, _argument):
            if (
                not changed["done"]
                and event == "line"
                and frame.f_code is initial._derive_payload.__code__
                and frame.f_lineno == target_line
            ):
                object.__setattr__(carrier, "setup", replacement_carrier.setup)
                object.__setattr__(
                    carrier,
                    "_construction_snapshot",
                    replacement_carrier._construction_snapshot,
                )
                for name, value in vars(other_prepared).items():
                    object.__setattr__(prepared, name, value)
                changed["done"] = True
            return mutate_callers

        sys.settrace(mutate_callers)
        try:
            canonical, _result_hash = (
                initial.derive_prepared_initial_structure_snapshot_v1(
                    prepared, carrier
                )
            )
        finally:
            sys.settrace(None)
        self.assertTrue(changed["done"])
        payload = json.loads(canonical)
        self.assertEqual(payload["carrier"]["setup"], json.loads(original_setup))
        reparsed = initial.parse_initial_structure_result_v1(payload)
        self.assertEqual(
            initial.canonical_initial_structure_result_json_v1(reparsed),
            canonical,
        )

    def test_compiler_canonicalizer_race_cannot_smuggle_invalid_setup(self):
        class InvalidSetup:
            def _payload_unchecked(self):
                return {
                    "setup_version": 1,
                    "positions": {"A": [[99, 99]], "B": []},
                }

        carrier = _carrier(self.skeleton, ((1, 1),), ((0, 0),))
        prepared = initial.prepare_initial_structure_skeleton_v1(carrier)
        source_lines, source_start = inspect.getsourcelines(
            compiler.canonical_typed_setup_carrier_json_v1
        )
        target_line = source_start + next(
            index
            for index, line in enumerate(source_lines)
            if "return _canonical_json" in line
        )
        changed = {"done": False}

        def mutate_after_validation(frame, event, _argument):
            if (
                not changed["done"]
                and event == "line"
                and frame.f_code
                is compiler.canonical_typed_setup_carrier_json_v1.__code__
                and frame.f_lineno == target_line
            ):
                object.__setattr__(carrier, "setup", InvalidSetup())
                changed["done"] = True
            return mutate_after_validation

        sys.settrace(mutate_after_validation)
        try:
            with self.assertRaises((TypeError, ValueError)):
                initial.derive_prepared_initial_structure_snapshot_v1(
                    prepared, carrier
                )
        finally:
            sys.settrace(None)
        self.assertTrue(changed["done"])

    def test_shared_leaf_callable_rebindings_fail_closed(self):
        attacks = (
            (json, "loads", lambda _value: {}),
            (json, "dumps", lambda *_args, **_kwargs: "{}"),
            (hashlib, "sha256", lambda *_args, **_kwargs: object()),
            (compiler, "_canonical_json", lambda _value: "{}"),
            (compiler, "_domain_hash", lambda *_args: "0" * 64),
            (compiler, "parse_typed_setup_v1", lambda _value: self.carrier.setup),
            (universe, "parse_profiled_skeleton", lambda _value: self.skeleton),
            (
                compiler,
                "_require_fresh_transport_skeleton",
                lambda _value: self.skeleton,
            ),
        )
        for target, name, replacement in attacks:
            with self.subTest(target=target.__name__, name=name):
                with mock.patch.object(target, name, replacement):
                    with self.assertRaises(initial.InitialStructureClosureError):
                        initial.derive_prepared_initial_structure_snapshot_v1(
                            self.prepared, self.carrier
                        )

    def test_every_derived_field_tamper_and_unknown_field_fail_full_rederivation(self):
        attacks = []
        extra = copy.deepcopy(self.value)
        extra["score"] = 0
        attacks.append(extra)
        legal = copy.deepcopy(self.value)
        legal["role_facts"]["A"]["legal"]["legal_action_count"] += 1
        attacks.append(legal)
        digest = copy.deepcopy(self.value)
        digest["evidence_digest"] = "0" * 64
        attacks.append(digest)
        reason = copy.deepcopy(self.value)
        reason["rejection_reasons"].append(
            {"code": "INITIAL_IMMOBILITY", "role": "A", "first_player": None}
        )
        attacks.append(reason)
        tempo = copy.deepcopy(self.value)
        tempo["count_lattice"]["tempo_references"].reverse()
        attacks.append(tempo)
        for value in attacks:
            with self.subTest(keys=tuple(value)):
                with self.assertRaises((TypeError, ValueError)):
                    initial.parse_initial_structure_result_v1(value)

    def test_prepared_mismatch_and_hostile_mutation_fail_closed(self):
        other_skeleton = _find_fresh_skeleton("PUSH", "KING_8")
        other = _carrier(other_skeleton)
        with self.assertRaises((TypeError, ValueError)):
            initial.derive_prepared_initial_structure_result_v1(self.prepared, other)

        prepared = initial.prepare_initial_structure_skeleton_v1(self.carrier)
        object.__setattr__(prepared, "skeleton_hash", "0" * 64)
        with self.assertRaises((TypeError, ValueError)):
            initial.derive_prepared_initial_structure_result_v1(prepared, self.carrier)

        prepared = initial.prepare_initial_structure_skeleton_v1(self.carrier)
        object.__setattr__(prepared, "skeleton_hash", "0" * 64)
        object.__setattr__(
            prepared,
            "_construction_snapshot",
            initial._domain_hash(
                initial._RESULT_EVIDENCE_DOMAIN,
                initial._canonical_json(
                    initial._prepared_snapshot_payload(
                        prepared.skeleton_json,
                        prepared.skeleton_hash,
                        prepared._role_data,
                        prepared._count_rows,
                        prepared._static_descriptor_json,
                        prepared.count_lattice_table_root,
                    )
                ),
            ),
        )
        with self.assertRaises((TypeError, ValueError)):
            initial.derive_prepared_initial_structure_result_v1(
                prepared, self.carrier
            )

        result = initial.derive_prepared_initial_structure_result_v1(
            self.prepared, self.carrier
        )
        object.__setattr__(result, "_canonical_payload_json", "{}")
        for operation in (
            initial.canonical_initial_structure_result_json_v1,
            initial.initial_structure_result_hash_v1,
        ):
            with self.subTest(operation=operation.__name__):
                with self.assertRaises((TypeError, ValueError)):
                    operation(result)

    def test_public_class_method_and_version_rebindings_fail_closed(self):
        operations = (
            (
                initial,
                "INITIAL_STRUCTURE_KERNEL_VERSION_V1",
                2,
                lambda: initial.derive_initial_structure_result_v1(self.carrier),
            ),
            (
                initial,
                "PreparedInitialStructureSkeletonV1",
                object,
                lambda: initial.prepare_initial_structure_skeleton_v1(self.carrier),
            ),
            (
                initial.InitialStructureResultV1,
                "_assert_unchanged",
                lambda _self: None,
                lambda: initial.initial_structure_result_hash_v1(self.result),
            ),
            (
                initial.CountLatticeDescriptorV1,
                "to_dict",
                lambda _self: {},
                lambda: initial.count_lattice_descriptor_hash_v1(
                    initial.build_count_lattice_descriptor_v1()
                ),
            ),
        )
        for target, name, replacement, operation in operations:
            with self.subTest(target=getattr(target, "__name__", repr(target)), name=name):
                with mock.patch.object(target, name, replacement):
                    with self.assertRaises((TypeError, ValueError)):
                        operation()

    def test_instance_method_shadows_and_direct_constructor_aliases_fail_closed(self):
        class IntAlias(int):
            pass

        class DictAlias(dict):
            pass

        descriptor_payload = initial.build_count_lattice_descriptor_v1().to_dict()
        constructor_attacks = (
            lambda: initial.PreparedInitialStructureSkeletonV1(True, self.carrier),
            lambda: initial.PreparedInitialStructureSkeletonV1(IntAlias(1), self.carrier),
            lambda: initial.InitialStructureResultV1(True, self.value),
            lambda: initial.InitialStructureResultV1(IntAlias(1), self.value),
            lambda: initial.InitialStructureResultV1(1, DictAlias(self.value)),
            lambda: initial.CountLatticeDescriptorV1(True, descriptor_payload),
            lambda: initial.CountLatticeDescriptorV1(IntAlias(1), descriptor_payload),
            lambda: initial.CountLatticeDescriptorV1(1, DictAlias(descriptor_payload)),
        )
        for attack in constructor_attacks:
            with self.subTest(attack=repr(attack)):
                with self.assertRaises((TypeError, ValueError)):
                    attack()

        prepared = initial.prepare_initial_structure_skeleton_v1(self.carrier)
        object.__setattr__(prepared, "_assert_unchanged", lambda: None)
        with self.assertRaises((TypeError, ValueError)):
            initial.derive_prepared_initial_structure_result_v1(
                prepared, self.carrier
            )

        for method_name in ("_assert_unchanged", "to_dict"):
            result = initial.derive_prepared_initial_structure_result_v1(
                self.prepared, self.carrier
            )
            object.__setattr__(result, method_name, lambda: None)
            with self.subTest(target="result", method=method_name):
                with self.assertRaises((TypeError, ValueError)):
                    initial.initial_structure_result_hash_v1(result)

            descriptor = initial.build_count_lattice_descriptor_v1()
            object.__setattr__(descriptor, method_name, lambda: None)
            with self.subTest(target="descriptor", method=method_name):
                with self.assertRaises((TypeError, ValueError)):
                    initial.count_lattice_descriptor_hash_v1(descriptor)

    def test_internal_formula_and_sibling_authority_rebindings_fail_closed(self):
        cases = (
            (
                initial,
                "_legal_breakdown",
                lambda *_args, **_kwargs: {},
                lambda: initial.derive_initial_structure_result_v1(self.carrier),
            ),
            (
                initial,
                "_support_value",
                lambda *_args, **_kwargs: {},
                lambda: initial.derive_initial_structure_result_v1(self.carrier),
            ),
            (
                initial,
                "_carrier_payload_positions",
                lambda *_args, **_kwargs: ((), ()),
                lambda: initial.derive_prepared_initial_structure_snapshot_v1(
                    self.prepared, self.carrier
                ),
            ),
            (
                compiler,
                "TypedSetupCarrierV1",
                object,
                lambda: initial.derive_initial_structure_result_v1(self.carrier),
            ),
            (
                universe.ProfiledSkeleton,
                "to_dict",
                lambda _self: {},
                lambda: initial.prepare_initial_structure_skeleton_v1(self.carrier),
            ),
            (
                universe,
                "canonical_profiled_skeleton_json",
                lambda _value: "{}",
                lambda: initial.derive_prepared_initial_structure_snapshot_v1(
                    self.prepared, self.carrier
                ),
            ),
            (
                universe,
                "profiled_skeleton_hash",
                lambda _value: "0" * 64,
                lambda: initial.derive_prepared_initial_structure_snapshot_v1(
                    self.prepared, self.carrier
                ),
            ),
        )
        for target, name, replacement, operation in cases:
            with self.subTest(target=getattr(target, "__name__", repr(target)), name=name):
                with mock.patch.object(target, name, replacement):
                    with self.assertRaises((TypeError, ValueError)):
                        operation()

    def test_geometry_and_result_domain_constant_rebindings_fail_closed(self):
        constants = (
            "_BOARD",
            "_ORTHOGONAL",
            "_DIAGONAL",
            "_KING",
        )
        for name in constants:
            original = getattr(initial, name)
            replacement = tuple(list(original))
            self.assertEqual(replacement, original)
            self.assertIsNot(replacement, original)
            with self.subTest(name=name):
                with mock.patch.object(initial, name, replacement):
                    with self.assertRaises(initial.InitialStructureClosureError):
                        initial.derive_initial_structure_result_v1(self.carrier)

        for name in (
            "_RESULT_DOMAIN",
            "_RESULT_EVIDENCE_DOMAIN",
            "_PROFILED_SKELETON_HASH_DOMAIN",
            "_TYPED_SETUP_HASH_DOMAIN",
            "_TYPED_CARRIER_HASH_DOMAIN",
        ):
            replacement = getattr(initial, name) + b"changed"
            with self.subTest(name=name):
                with mock.patch.object(initial, name, replacement):
                    with self.assertRaises(initial.InitialStructureClosureError):
                        initial.derive_initial_structure_result_v1(self.carrier)

    def test_fake_count_row_and_outer_tuple_are_rejected_before_prepared_derivation(self):
        class FakeRow(tuple):
            pass

        class FakeRows(tuple):
            pass

        prepared = initial.prepare_initial_structure_skeleton_v1(self.carrier)
        rows = list(prepared._count_rows)
        rows[0] = FakeRow(rows[0])
        object.__setattr__(prepared, "_count_rows", tuple(rows))
        with self.assertRaises((TypeError, ValueError)):
            initial.derive_prepared_initial_structure_result_v1(
                prepared, self.carrier
            )

        prepared = initial.prepare_initial_structure_skeleton_v1(self.carrier)
        object.__setattr__(prepared, "_count_rows", FakeRows(prepared._count_rows))
        with self.assertRaises((TypeError, ValueError)):
            initial.derive_prepared_initial_structure_result_v1(
                prepared, self.carrier
            )

    def test_to_dict_cannot_be_bypassed_by_rebinding_public_normalizers(self):
        result = initial.derive_prepared_initial_structure_result_v1(
            self.prepared, self.carrier
        )
        object.__setattr__(result, "_canonical_payload_json", "{}")
        with mock.patch.object(initial, "_normalize_result", lambda value: value):
            with self.assertRaises((TypeError, ValueError)):
                result.to_dict()

        descriptor = initial.build_count_lattice_descriptor_v1()
        object.__setattr__(descriptor, "count_lattice_table_version", 2)
        with mock.patch.object(
            initial, "_normalize_count_descriptor", lambda value: value
        ):
            with self.assertRaises((TypeError, ValueError)):
                descriptor.to_dict()

    def test_count_constructor_rejects_nested_exact_payload_subclasses(self):
        class DictAlias(dict):
            pass

        class ListAlias(list):
            pass

        baseline = initial.build_count_lattice_descriptor_v1().to_dict()
        nested_dict = copy.deepcopy(baseline)
        nested_dict["proof"] = DictAlias(nested_dict["proof"])
        nested_list = copy.deepcopy(baseline)
        nested_list["action_order"] = ListAlias(nested_list["action_order"])
        deeply_nested_list = copy.deepcopy(baseline)
        deeply_nested_list["entries"][0]["layers"][0] = ListAlias(
            deeply_nested_list["entries"][0]["layers"][0]
        )
        for payload in (nested_dict, nested_list, deeply_nested_list):
            with self.subTest(kind=type(payload).__name__):
                with self.assertRaises((TypeError, ValueError)):
                    initial.CountLatticeDescriptorV1(1, payload)


class DescriptorReasonAndSimplicityTests(unittest.TestCase):
    def test_static_descriptor_groups_match_independent_formula_and_dsl_prose(self):
        for action_a, profile_a in _ACTION_PROFILES:
            for action_b, profile_b in _ACTION_PROFILES:
                role_a = (
                    action_a,
                    "REACH_EDGE",
                    ("TOP",),
                    _PROFILES[profile_a],
                )
                role_b = (
                    action_b,
                    "CONNECT_EDGES",
                    ("RIGHT", "LEFT"),
                    _PROFILES[profile_b],
                )
                with self.subTest(
                    action_a=action_a,
                    profile_a=profile_a,
                    action_b=action_b,
                    profile_b=profile_b,
                ):
                    self.assertEqual(
                        initial._static_descriptor_payload(role_a, role_b),
                        _static_descriptor_oracle(role_a, role_b),
                    )

        for action, profile, goal, edges in _action_shape_specs():
            skeleton = _find_fresh_skeleton(action, profile, goal, edges)
            carrier = _carrier(skeleton, ((1, 1),), ((2, 2),))
            value = initial.derive_initial_structure_result_v1(carrier).to_dict()
            definition = _compiled_definition(skeleton)
            expected = _static_descriptor_oracle(
                _role_tuple(skeleton.role_a), _role_tuple(skeleton.role_b)
            )
            for group in (
                "structural",
                "description_clause",
                "primitive_concept",
                "vector_cardinality",
            ):
                self.assertEqual(value["descriptor_groups"][group], expected[group])
            observed_operational = copy.deepcopy(
                value["descriptor_groups"]["operational_substep"]
            )
            observed_operational.pop("initial_legal_action_counts")
            self.assertEqual(observed_operational, expected["operational_substep"])
            self.assertEqual(
                value["descriptor_groups"]["description_clause"]["independent_statement_count"],
                len(dsl.describe_rules(definition)),
            )

            forbidden = {
                "score",
                "rank",
                "candidate",
                "selection",
                "history",
                "outcome",
                "winner",
            }

            def keys(tree):
                if type(tree) is dict:
                    for key, child in tree.items():
                        yield key
                        yield from keys(child)
                elif type(tree) is list:
                    for child in tree:
                        yield from keys(child)

            self.assertTrue(forbidden.isdisjoint(set(keys(value))))

    def test_overlapping_reasons_are_complete_typed_and_in_fixed_order(self):
        skeleton = _find_fresh_skeleton(
            "MOVE_CAPTURE",
            "DIAGONAL_4",
            "ELIMINATE",
            (),
            action_b="PLACE",
            profile_b="NONE",
            goal_b="REACH_EDGE",
            edges_b=("TOP",),
        )
        value = initial.derive_initial_structure_result_v1(
            _carrier(skeleton, (), ((0, 0),))
        ).to_dict()
        self.assertEqual(
            value["rejection_reasons"],
            [
                {
                    "code": "ZERO_ACTOR_WITH_NONPLACE",
                    "role": "A",
                    "first_player": None,
                },
                {
                    "code": "INITIAL_GOAL_SATISFIED",
                    "role": "B",
                    "first_player": None,
                },
                {
                    "code": "INITIAL_IMMOBILITY",
                    "role": "A",
                    "first_player": None,
                },
                {
                    "code": "OPTIMISTIC_GOAL_UNREACHABLE",
                    "role": "A",
                    "first_player": None,
                },
                {
                    "code": "COUNT_LATTICE_GOAL_UNREACHABLE_WITHIN_18",
                    "role": "A",
                    "first_player": "A",
                },
                {
                    "code": "COUNT_LATTICE_GOAL_UNREACHABLE_WITHIN_18",
                    "role": "A",
                    "first_player": "B",
                },
            ],
        )
        self.assertFalse(value["eligible"])
        self.assertTrue(
            all(
                (reason["first_player"] is not None)
                == (reason["code"] == "COUNT_LATTICE_GOAL_UNREACHABLE_WITHIN_18")
                for reason in value["rejection_reasons"]
            )
        )


class TransformCovarianceTests(unittest.TestCase):
    @staticmethod
    def _without_target(fact):
        value = copy.deepcopy(fact)
        value.pop("target_edges")
        return value

    def test_d4_covariance_for_all_transforms_and_heterogeneous_primitives(self):
        skeletons = (
            _find_fresh_skeleton(
                "MOVE",
                "DIAGONAL_4",
                "CONNECT_EDGES",
                ("TOP", "BOTTOM"),
                action_b="SWAP",
                profile_b="ORTHOGONAL_4",
                goal_b="REACH_EDGE",
                edges_b=("RIGHT",),
            ),
            _find_fresh_skeleton(
                "PUSH",
                "KING_8",
                "REACH_EDGE",
                ("LEFT",),
                action_b="CONVERT",
                profile_b="DIAGONAL_4",
                goal_b="REACH_EDGE",
                edges_b=("RIGHT",),
            ),
            _find_fresh_skeleton(
                "PLACE",
                "NONE",
                "REACH_EDGE",
                ("BOTTOM",),
                action_b="MOVE_CAPTURE",
                profile_b="KING_8",
                goal_b="ELIMINATE",
                edges_b=(),
            ),
        )
        setup_rows = (
            (((0, 0), (1, 2)), ((0, 2), (2, 1))),
            (((0, 1),), ((1, 0), (2, 2))),
        )
        for skeleton in skeletons:
            for positions_a, positions_b in setup_rows:
                source_carrier = _carrier(skeleton, positions_a, positions_b)
                source = initial.derive_initial_structure_result_v1(
                    source_carrier
                ).to_dict()
                for transform in universe.D4Transform:
                    target_carrier = compiler.transform_typed_setup_carrier_v1(
                        source_carrier, transform
                    )
                    target = initial.derive_initial_structure_result_v1(
                        target_carrier
                    ).to_dict()
                    with self.subTest(
                        action=skeleton.role_a.signature.action_primitive.value,
                        transform=transform.value,
                    ):
                        for owner in _OWNERS:
                            self.assertEqual(
                                self._without_target(target["role_facts"][owner]),
                                self._without_target(source["role_facts"][owner]),
                            )
                        self.assertEqual(
                            target["count_lattice"], source["count_lattice"]
                        )
                        self.assertEqual(
                            target["descriptor_groups"], source["descriptor_groups"]
                        )
                        self.assertEqual(
                            target["rejection_reasons"], source["rejection_reasons"]
                        )
                        self.assertEqual(target["eligible"], source["eligible"])
                        expected_positions_a = sorted(
                            _transform_position(position, transform.value)
                            for position in positions_a
                        )
                        expected_positions_b = sorted(
                            _transform_position(position, transform.value)
                            for position in positions_b
                        )
                        self.assertEqual(
                            target["carrier"]["setup"]["positions"],
                            {
                                "A": [list(position) for position in expected_positions_a],
                                "B": [list(position) for position in expected_positions_b],
                            },
                        )

    def test_complete_role_swap_covariance_exchanges_every_role_local_field(self):
        skeleton = _find_fresh_skeleton(
            "HOP",
            "DIAGONAL_4",
            "CONNECT_EDGES",
            ("TOP", "BOTTOM"),
            action_b="CONVERT",
            profile_b="KING_8",
            goal_b="ELIMINATE",
            edges_b=(),
        )
        source_carrier = _carrier(
            skeleton,
            ((0, 1), (2, 0)),
            ((0, 0), (1, 1), (2, 2)),
        )
        target_carrier = compiler.complete_role_swap_typed_setup_carrier_v1(
            source_carrier
        )
        source = initial.derive_initial_structure_result_v1(source_carrier).to_dict()
        target = initial.derive_initial_structure_result_v1(target_carrier).to_dict()
        for target_owner, source_owner in (("A", "B"), ("B", "A")):
            expected = copy.deepcopy(source["role_facts"][source_owner])
            expected["role"] = target_owner
            self.assertEqual(target["role_facts"][target_owner], expected)

        for group in ("structural", "description_clause", "primitive_concept"):
            self.assertEqual(
                target["descriptor_groups"][group],
                source["descriptor_groups"][group],
            )
        for group, key in (
            ("vector_cardinality", None),
            ("dependency", None),
        ):
            self.assertEqual(
                target["descriptor_groups"][group]["A"],
                source["descriptor_groups"][group]["B"],
            )
            self.assertEqual(
                target["descriptor_groups"][group]["B"],
                source["descriptor_groups"][group]["A"],
            )
        target_density = target["descriptor_groups"]["density"]
        source_density = source["descriptor_groups"]["density"]
        self.assertEqual(
            target_density["initial_piece_counts"],
            {"A": source_density["initial_piece_counts"]["B"], "B": source_density["initial_piece_counts"]["A"]},
        )
        self.assertEqual(
            target_density["role_piece_fractions"],
            {"A": source_density["role_piece_fractions"]["B"], "B": source_density["role_piece_fractions"]["A"]},
        )
        self.assertEqual(
            target["descriptor_groups"]["contact"]["role_a_vector_contact_count"],
            source["descriptor_groups"]["contact"]["role_b_vector_contact_count"],
        )
        self.assertEqual(
            target["descriptor_groups"]["contact"]["role_b_vector_contact_count"],
            source["descriptor_groups"]["contact"]["role_a_vector_contact_count"],
        )
        self.assertEqual(target["eligible"], source["eligible"])

        transformed_reasons = [
            {
                "code": reason["code"],
                "role": "B" if reason["role"] == "A" else "A",
                "first_player": (
                    None
                    if reason["first_player"] is None
                    else ("B" if reason["first_player"] == "A" else "A")
                ),
            }
            for reason in source["rejection_reasons"]
        ]
        order = {
            code: index
            for index, code in enumerate(
                (
                    "ZERO_ACTOR_WITH_NONPLACE",
                    "INITIAL_GOAL_SATISFIED",
                    "INITIAL_IMMOBILITY",
                    "OPTIMISTIC_GOAL_UNREACHABLE",
                    "COUNT_LATTICE_GOAL_UNREACHABLE_WITHIN_18",
                )
            )
        }
        transformed_reasons.sort(
            key=lambda reason: (
                order[reason["code"]],
                _OWNERS.index(reason["role"]),
                -1
                if reason["first_player"] is None
                else _OWNERS.index(reason["first_player"]),
            )
        )
        self.assertEqual(target["rejection_reasons"], transformed_reasons)

        self.assertEqual(
            compiler.complete_role_swap_typed_setup_carrier_v1(target_carrier),
            source_carrier,
        )

    def test_owner_only_swap_is_not_declared_as_an_invariance(self):
        skeleton = _find_fresh_skeleton(
            "PLACE",
            "NONE",
            "REACH_EDGE",
            ("TOP",),
            action_b="CONVERT",
            profile_b="KING_8",
            goal_b="CONNECT_EDGES",
            edges_b=("RIGHT", "LEFT"),
        )
        source_carrier = _carrier(skeleton, (), ((0, 0), (2, 2)))
        target_carrier = compiler.owner_swap_typed_setup_carrier_v1(source_carrier)
        source = initial.derive_initial_structure_result_v1(source_carrier).to_dict()
        target = initial.derive_initial_structure_result_v1(target_carrier).to_dict()
        self.assertEqual(target_carrier.skeleton, source_carrier.skeleton)
        self.assertNotEqual(target["role_facts"], source["role_facts"])


class PairAwareSupportTests(unittest.TestCase):
    def test_static_swap_counterexample_defeats_role_local_weak_closure(self):
        skeleton = _find_fresh_skeleton(
            "MOVE",
            "DIAGONAL_4",
            "CONNECT_EDGES",
            ("TOP", "BOTTOM"),
            action_b="SWAP",
            profile_b="ORTHOGONAL_4",
            goal_b="REACH_EDGE",
            edges_b=("RIGHT",),
        )
        positions_a = ((0, 1), (1, 0), (2, 1))
        positions_b = ((1, 1),)
        carrier = _carrier(skeleton, positions_a, positions_b)
        value = initial.derive_initial_structure_result_v1(carrier).to_dict()
        weak = _closure(positions_a, _PROFILES["DIAGONAL_4"])
        strong = _closure(
            positions_a,
            _PROFILES["DIAGONAL_4"] + _PROFILES["ORTHOGONAL_4"],
        )
        self.assertFalse(_goal_oracle("CONNECT_EDGES", ("TOP", "BOTTOM"), weak, positions_b))
        self.assertTrue(_goal_oracle("CONNECT_EDGES", ("TOP", "BOTTOM"), strong, positions_b))
        self.assertFalse(value["role_facts"]["A"]["initial_goal_satisfied"])
        self.assertEqual(
            value["role_facts"]["A"]["optimistic_support"],
            _support_oracle(
                "MOVE",
                _PROFILES["DIAGONAL_4"],
                "CONNECT_EDGES",
                ("TOP", "BOTTOM"),
                positions_a,
                positions_b,
                "SWAP",
                _PROFILES["ORTHOGONAL_4"],
            )[0],
        )
        self.assertTrue(value["role_facts"]["A"]["optimistic_support"]["goal_reachable"])

        swap = next(
            record
            for record in _legal_oracle(
                "SWAP", _PROFILES["ORTHOGONAL_4"], positions_b, positions_a
            )
            if record[0] == (1, 1) and record[1] == (1, 0)
        )
        b_after, a_after = _manual_successor("SWAP", swap, positions_b, positions_a)
        self.assertTrue(
            _goal_oracle("CONNECT_EDGES", ("TOP", "BOTTOM"), a_after, b_after)
        )

    def test_eliminate_lineages_remain_per_target_for_all_opponent_actions(self):
        positions_a = ((0, 0),)
        positions_b = ((0, 1), (2, 2))
        for opponent_action, opponent_profile in _ACTION_PROFILES:
            eliminator_action = (
                "CONVERT"
                if opponent_action == "HOP"
                else "MOVE_CAPTURE"
            )
            eliminator_profile = "DIAGONAL_4"
            skeleton = _find_fresh_skeleton(
                eliminator_action,
                eliminator_profile,
                "ELIMINATE",
                (),
                action_b=opponent_action,
                profile_b=opponent_profile,
                goal_b="REACH_EDGE",
                edges_b=("RIGHT",),
            )
            value = initial.derive_initial_structure_result_v1(
                _carrier(skeleton, positions_a, positions_b)
            ).to_dict()
            expected, _ = _support_oracle(
                eliminator_action,
                _PROFILES[eliminator_profile],
                "ELIMINATE",
                (),
                positions_a,
                positions_b,
                opponent_action,
                _PROFILES[opponent_profile],
            )
            with self.subTest(action=opponent_action, profile=opponent_profile):
                self.assertEqual(value["role_facts"]["A"]["optimistic_support"], expected)
                self.assertEqual(expected["eliminate_initial_target_count"], 2)
                expected_unreachable = (
                    1
                    if opponent_action in ("PLACE", "CONVERT")
                    or opponent_profile == "DIAGONAL_4"
                    else 0
                )
                self.assertEqual(
                    expected["eliminate_unreachable_target_count"],
                    expected_unreachable,
                )
                self.assertEqual(
                    expected["goal_reachable"], expected_unreachable == 0
                )


class CapabilityIsolationTests(unittest.TestCase):
    def test_isolated_import_and_representative_runtime_have_no_legacy_or_io_capability(self):
        source_root = str(Path(__file__).resolve().parents[1] / "src")
        code = textwrap.dedent(
            """
            import builtins
            import importlib.abc
            import os
            import socket
            import sys
            sys.path.insert(0, {source_root!r})
            allowed = {{
                "parity_forge_universe",
                "parity_forge_universe.typed_occupancy",
                "parity_forge_universe.schema_v4_compiler",
                "parity_forge_universe.initial_structure",
            }}
            class Poison(importlib.abc.MetaPathFinder):
                def find_spec(self, fullname, path=None, target=None):
                    if fullname == "parity_forge" or fullname.startswith("parity_forge."):
                        raise RuntimeError("forbidden legacy import: " + fullname)
                    if fullname.startswith("parity_forge_universe.") and fullname not in allowed:
                        raise RuntimeError("forbidden sibling import: " + fullname)
                    return None
            sys.meta_path.insert(0, Poison())
            def fail_io(*args, **kwargs):
                raise RuntimeError("forbidden initial-structure I/O")
            builtins.open = fail_io
            os.open = fail_io
            socket.socket = fail_io
            import parity_forge_universe.initial_structure as initial
            import parity_forge_universe.schema_v4_compiler as compiler
            import parity_forge_universe.typed_occupancy as universe
            skeleton = universe.parse_profiled_skeleton({skeleton!r})
            setup = compiler.TypedSetupV1(1, ((1, 1),), ((0, 0),))
            carrier = compiler.TypedSetupCarrierV1(1, skeleton, setup)
            prepared = initial.prepare_initial_structure_skeleton_v1(carrier)
            result = initial.derive_prepared_initial_structure_result_v1(prepared, carrier)
            payload = result.to_dict()
            assert initial.parse_initial_structure_result_v1(payload).to_dict() == payload
            descriptor = initial.build_count_lattice_descriptor_v1()
            assert len(descriptor.to_dict()["entries"]) == 1470
            loaded = {{
                name for name in sys.modules
                if name == "parity_forge"
                or name.startswith("parity_forge.")
                or name == "parity_forge_universe"
                or name.startswith("parity_forge_universe.")
            }}
            assert loaded == allowed, sorted(loaded)
            """
        ).format(source_root=source_root, skeleton=_skeleton(
            "CONVERT",
            "CONNECT_EDGES",
            "DIAGONAL_4",
            ("RIGHT", "LEFT"),
            "CONVERT",
            "CONNECT_EDGES",
            "KING_8",
            ("RIGHT", "LEFT"),
        ).to_dict())
        completed = subprocess.run(
            [sys.executable, "-I", "-c", code],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_production_ast_excludes_gameplay_outcome_io_and_dynamic_imports(self):
        package_root = Path(__file__).resolve().parents[1] / "src" / "parity_forge_universe"
        source_paths = (
            package_root / "__init__.py",
            package_root / "typed_occupancy.py",
            package_root / "schema_v4_compiler.py",
            package_root / "initial_structure.py",
        )
        forbidden_imports = {
            "asyncio",
            "http",
            "importlib",
            "multiprocessing",
            "os",
            "pathlib",
            "requests",
            "shutil",
            "socket",
            "subprocess",
            "urllib",
        }
        forbidden_names = {
            "GameState",
            "Outcome",
            "engine",
            "apply_action",
            "initial_state",
            "legal_actions",
            "goal_satisfied",
            "terminal_status",
            "solver",
            "solve_game",
            "agent",
            "play",
            "play_game",
            "replay",
            "telemetry",
            "history",
            "selection",
            "candidate",
            "outcome",
            "winner",
            "rank",
            "score",
        }
        forbidden_calls = forbidden_names | {"__import__", "compile", "eval", "exec", "open"}
        imported = set()
        names = set()
        calls = set()
        for source_path in source_paths:
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    imported.add((node.module or "").split(".")[0])
                elif isinstance(node, ast.Name):
                    names.add(node.id)
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        calls.add(node.func.id)
                    elif isinstance(node.func, ast.Attribute):
                        calls.add(node.func.attr)
        self.assertTrue(forbidden_imports.isdisjoint(imported), sorted(imported))
        self.assertTrue(forbidden_names.isdisjoint(names), sorted(forbidden_names & names))
        self.assertTrue(forbidden_calls.isdisjoint(calls), sorted(forbidden_calls & calls))


if __name__ == "__main__":
    unittest.main()
