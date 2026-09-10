"""Pure initial-structure authority for the Plan-0015 typed universe.

The module derives only facts available from one typed 3x3 setup: initial goal
truth, legal/dependency counts, monotone necessary-condition supports, a tight
count relaxation, and finite structural work.  It never constructs a game
state, applies an action, or observes an outcome.

Production imports are deliberately limited to the standard library and the
two sealed sibling modules.  Full count-lattice layers live in one immutable
shared descriptor; per-carrier results retain only domain-separated references
and the role-goal witnesses selected from that table.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from math import comb
from typing import Any, Dict, Iterable, List, Optional, Tuple

from . import schema_v4_compiler as compiler
from . import typed_occupancy as universe


INITIAL_STRUCTURE_KERNEL_VERSION_V1 = 1
INITIAL_STRUCTURE_RESULT_VERSION_V1 = 1
PREPARED_INITIAL_STRUCTURE_VERSION_V1 = 1
COUNT_LATTICE_TABLE_VERSION_V1 = 1


class InitialStructureClosureError(ValueError):
    """A sealed vocabulary, authority, table, or derived proof changed."""


Position = Tuple[int, int]
CountState = Tuple[int, int]

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
_EDGES = ("TOP", "RIGHT", "BOTTOM", "LEFT")
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
_BOARD = tuple((row, column) for row in range(3) for column in range(3))
_ORTHOGONAL = ((-1, 0), (0, -1), (0, 1), (1, 0))
_DIAGONAL = ((-1, -1), (-1, 1), (1, -1), (1, 1))
_KING = tuple(sorted(_ORTHOGONAL + _DIAGONAL))

_REASON_CODES = (
    "ZERO_ACTOR_WITH_NONPLACE",
    "INITIAL_GOAL_SATISFIED",
    "INITIAL_IMMOBILITY",
    "OPTIMISTIC_GOAL_UNREACHABLE",
    "COUNT_LATTICE_GOAL_UNREACHABLE_WITHIN_18",
)

_RESULT_DOMAIN = b"parity-forge:plan0015:initial-structure-result:v1\0"
_RESULT_EVIDENCE_DOMAIN = (
    b"parity-forge:plan0015:initial-structure-result-evidence:v1\0"
)
_COUNT_TABLE_DOMAIN = b"parity-forge:plan0015:count-lattice-table:v1\0"
_COUNT_ENTRY_DOMAIN = b"parity-forge:plan0015:count-lattice-entry:v1\0"
_PROFILED_SKELETON_HASH_DOMAIN = b"parity-forge:typed-occupancy:skeleton:v1\0"
_TYPED_SETUP_HASH_DOMAIN = b"parity-forge:plan0015:typed-setup:v1\0"
_TYPED_CARRIER_HASH_DOMAIN = b"parity-forge:plan0015:typed-setup-carrier:v1\0"

_MAX_RESULT_JSON_BYTES = 100_000
_MAX_RESULT_JSON_NODES = 20_000
_MAX_RESULT_JSON_DEPTH = 32
_MAX_COUNT_TABLE_JSON_NODES = 200_000
_MAX_COUNT_TABLE_JSON_DEPTH = 8


def _canonical_json(value: Any, _dumps: Any = json.dumps) -> str:
    if json.dumps is not _dumps:
        raise InitialStructureClosureError("JSON encoder binding changed")
    return _dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _domain_hash(
    domain: bytes, canonical: str, _sha256: Any = hashlib.sha256
) -> str:
    if hashlib.sha256 is not _sha256:
        raise InitialStructureClosureError("SHA-256 binding changed")
    return _sha256(domain + canonical.encode("utf-8")).hexdigest()


def _exact_dict(value: Any, label: str) -> Dict[str, Any]:
    if type(value) is not dict:
        raise TypeError("{} must be an exact object".format(label))
    if any(type(key) is not str for key in value):
        raise TypeError("{} keys must be exact strings".format(label))
    return value


def _exact_keys(value: Dict[str, Any], expected: Iterable[str], label: str) -> None:
    expected_set = set(expected)
    if set(value) != expected_set:
        missing = sorted(expected_set - set(value))
        extra = sorted(set(value) - expected_set)
        details = []
        if missing:
            details.append("missing {}".format(missing))
        if extra:
            details.append("unknown {}".format(extra))
        raise ValueError("{} has {}".format(label, ", ".join(details)))


def _validate_json_tree(
    value: Any,
    label: str,
    max_nodes: int = _MAX_RESULT_JSON_NODES,
    max_depth: int = _MAX_RESULT_JSON_DEPTH,
) -> None:
    nodes = 0
    active: set[int] = set()

    def visit(item: Any, depth: int) -> None:
        nonlocal nodes
        nodes += 1
        if nodes > max_nodes:
            raise ValueError("{} exceeds the JSON node cap".format(label))
        if depth > max_depth:
            raise ValueError("{} exceeds the JSON depth cap".format(label))
        if item is None or type(item) in (bool, int, str):
            return
        if type(item) not in (dict, list):
            raise TypeError("{} must contain only exact JSON values".format(label))
        identity = id(item)
        if identity in active:
            raise ValueError("{} cannot contain a cycle".format(label))
        active.add(identity)
        try:
            children = item.values() if type(item) is dict else item
            for child in children:
                visit(child, depth + 1)
        finally:
            active.remove(identity)

    visit(value, 0)


def _require_exact_fields(value: Any, expected: Iterable[str], label: str) -> None:
    try:
        fields = vars(value)
    except TypeError as error:
        raise TypeError("{} fields are unavailable".format(label)) from error
    if type(fields) is not dict or set(fields) != set(expected):
        raise TypeError("{} has noncanonical fields".format(label))


def _compiler_api(
    _module: Any = compiler,
    _carrier_type: Any = compiler.TypedSetupCarrierV1,
    _normalize: Any = compiler._normalize_carrier,
    _parse: Any = compiler.parse_typed_setup_carrier_v1,
    _canonical: Any = compiler.canonical_typed_setup_carrier_json_v1,
    _carrier_hash: Any = compiler.typed_setup_carrier_hash_v1,
    _setup_hash: Any = compiler.typed_setup_hash_v1,
    _compiler_canonical_leaf: Any = compiler._canonical_json,
    _compiler_hash_leaf: Any = compiler._domain_hash,
    _setup_parser_leaf: Any = compiler.parse_typed_setup_v1,
) -> Tuple[Any, Any, Any, Any, Any]:
    if (
        compiler is not _module
        or _module.TypedSetupCarrierV1 is not _carrier_type
        or _module._normalize_carrier is not _normalize
        or _module.parse_typed_setup_carrier_v1 is not _parse
        or _module.canonical_typed_setup_carrier_json_v1 is not _canonical
        or _module.typed_setup_carrier_hash_v1 is not _carrier_hash
        or _module.typed_setup_hash_v1 is not _setup_hash
        or _module._canonical_json is not _compiler_canonical_leaf
        or _module._domain_hash is not _compiler_hash_leaf
        or _module.parse_typed_setup_v1 is not _setup_parser_leaf
    ):
        raise InitialStructureClosureError("typed compiler authority binding changed")
    return _normalize, _parse, _canonical, _carrier_hash, _setup_hash


def _universe_api(
    _module: Any = universe,
    _skeleton_type: Any = universe.ProfiledSkeleton,
    _action_type: Any = universe.ActionPrimitive,
    _goal_type: Any = universe.GoalPrimitive,
    _edge_type: Any = universe.BoardEdge,
    _profile_type: Any = universe.VectorProfile,
    _action_members: Tuple[Any, ...] = (
        universe.ActionPrimitive.PLACE,
        universe.ActionPrimitive.MOVE,
        universe.ActionPrimitive.MOVE_CAPTURE,
        universe.ActionPrimitive.PUSH,
        universe.ActionPrimitive.SWAP,
        universe.ActionPrimitive.HOP,
        universe.ActionPrimitive.CONVERT,
    ),
    _goal_members: Tuple[Any, ...] = (
        universe.GoalPrimitive.CONNECT_EDGES,
        universe.GoalPrimitive.REACH_EDGE,
        universe.GoalPrimitive.ELIMINATE,
    ),
    _edge_members: Tuple[Any, ...] = (
        universe.BoardEdge.TOP,
        universe.BoardEdge.RIGHT,
        universe.BoardEdge.BOTTOM,
        universe.BoardEdge.LEFT,
    ),
    _profile_members: Tuple[Any, ...] = (
        universe.VectorProfile.NONE,
        universe.VectorProfile.ORTHOGONAL_4,
        universe.VectorProfile.DIAGONAL_4,
        universe.VectorProfile.KING_8,
    ),
    _parse: Any = universe.parse_profiled_skeleton,
    _fresh: Any = compiler._require_fresh_transport_skeleton,
    _canonical: Any = universe.canonical_profiled_skeleton_json,
    _skeleton_hash: Any = universe.profiled_skeleton_hash,
) -> Tuple[Any, Any]:
    if (
        universe is not _module
        or _module.ProfiledSkeleton is not _skeleton_type
        or _module.ActionPrimitive is not _action_type
        or _module.GoalPrimitive is not _goal_type
        or _module.BoardEdge is not _edge_type
        or _module.VectorProfile is not _profile_type
        or tuple(map(id, tuple(_action_type))) != tuple(map(id, _action_members))
        or tuple(map(id, tuple(_goal_type))) != tuple(map(id, _goal_members))
        or tuple(map(id, tuple(_edge_type))) != tuple(map(id, _edge_members))
        or tuple(map(id, tuple(_profile_type))) != tuple(map(id, _profile_members))
        or _module.parse_profiled_skeleton is not _parse
        or compiler._require_fresh_transport_skeleton is not _fresh
        or _module.canonical_profiled_skeleton_json is not _canonical
        or _module.profiled_skeleton_hash is not _skeleton_hash
    ):
        raise InitialStructureClosureError("typed universe authority binding changed")
    return _canonical, _skeleton_hash


def _official_version(
    _compiler: Any = _compiler_api,
    _universe: Any = _universe_api,
    _canonical: Any = _canonical_json,
    _hash: Any = _domain_hash,
    _json_module: Any = json,
    _hashlib_module: Any = hashlib,
    _json_dumps: Any = json.dumps,
    _json_loads: Any = json.loads,
    _sha256: Any = hashlib.sha256,
    _actions: Tuple[str, ...] = _ACTIONS,
    _owners: Tuple[str, ...] = _OWNERS,
    _goals: Tuple[str, ...] = _GOALS,
    _edges: Tuple[str, ...] = _EDGES,
    _initial_counts: Tuple[CountState, ...] = _INITIAL_COUNTS,
    _count_states: Tuple[CountState, ...] = _COUNT_STATES,
    _board: Tuple[Position, ...] = _BOARD,
    _orthogonal: Tuple[Position, ...] = _ORTHOGONAL,
    _diagonal: Tuple[Position, ...] = _DIAGONAL,
    _king: Tuple[Position, ...] = _KING,
    _reason_codes: Tuple[str, ...] = _REASON_CODES,
    _result_domain: bytes = _RESULT_DOMAIN,
    _result_evidence_domain: bytes = _RESULT_EVIDENCE_DOMAIN,
    _count_table_domain: bytes = _COUNT_TABLE_DOMAIN,
    _count_entry_domain: bytes = _COUNT_ENTRY_DOMAIN,
    _profiled_skeleton_hash_domain: bytes = _PROFILED_SKELETON_HASH_DOMAIN,
    _typed_setup_hash_domain: bytes = _TYPED_SETUP_HASH_DOMAIN,
    _typed_carrier_hash_domain: bytes = _TYPED_CARRIER_HASH_DOMAIN,
) -> int:
    if (
        _compiler_api is not _compiler
        or _universe_api is not _universe
        or _canonical_json is not _canonical
        or _domain_hash is not _hash
        or json is not _json_module
        or hashlib is not _hashlib_module
        or json.dumps is not _json_dumps
        or json.loads is not _json_loads
        or hashlib.sha256 is not _sha256
        or _ACTIONS is not _actions
        or _OWNERS is not _owners
        or _GOALS is not _goals
        or _EDGES is not _edges
        or _INITIAL_COUNTS is not _initial_counts
        or _COUNT_STATES is not _count_states
        or _BOARD is not _board
        or _ORTHOGONAL is not _orthogonal
        or _DIAGONAL is not _diagonal
        or _KING is not _king
        or _REASON_CODES is not _reason_codes
        or _RESULT_DOMAIN is not _result_domain
        or _RESULT_EVIDENCE_DOMAIN is not _result_evidence_domain
        or _COUNT_TABLE_DOMAIN is not _count_table_domain
        or _COUNT_ENTRY_DOMAIN is not _count_entry_domain
        or _PROFILED_SKELETON_HASH_DOMAIN is not _profiled_skeleton_hash_domain
        or _TYPED_SETUP_HASH_DOMAIN is not _typed_setup_hash_domain
        or _TYPED_CARRIER_HASH_DOMAIN is not _typed_carrier_hash_domain
    ):
        raise InitialStructureClosureError("authority guard binding changed")
    _compiler()
    _universe()
    values = (
        INITIAL_STRUCTURE_KERNEL_VERSION_V1,
        INITIAL_STRUCTURE_RESULT_VERSION_V1,
        PREPARED_INITIAL_STRUCTURE_VERSION_V1,
        COUNT_LATTICE_TABLE_VERSION_V1,
        _MAX_RESULT_JSON_BYTES,
        _MAX_RESULT_JSON_NODES,
        _MAX_RESULT_JSON_DEPTH,
        _MAX_COUNT_TABLE_JSON_NODES,
        _MAX_COUNT_TABLE_JSON_DEPTH,
    )
    if any(type(value) is not int for value in values):
        raise InitialStructureClosureError("initial-structure integer binding changed")
    if values[:4] != (1, 1, 1, 1) or values[4:] != (
        100_000,
        20_000,
        32,
        200_000,
        8,
    ):
        raise InitialStructureClosureError("initial-structure version binding changed")
    return 1


def _action_name(action: Any) -> str:
    if action is universe.ActionPrimitive.PLACE:
        return "PLACE"
    if action is universe.ActionPrimitive.MOVE:
        return "MOVE"
    if action is universe.ActionPrimitive.MOVE_CAPTURE:
        return "MOVE_CAPTURE"
    if action is universe.ActionPrimitive.PUSH:
        return "PUSH"
    if action is universe.ActionPrimitive.SWAP:
        return "SWAP"
    if action is universe.ActionPrimitive.HOP:
        return "HOP"
    if action is universe.ActionPrimitive.CONVERT:
        return "CONVERT"
    raise InitialStructureClosureError("typed action vocabulary changed")


def _goal_name(goal: Any) -> str:
    if goal is universe.GoalPrimitive.CONNECT_EDGES:
        return "CONNECT_EDGES"
    if goal is universe.GoalPrimitive.REACH_EDGE:
        return "REACH_EDGE"
    if goal is universe.GoalPrimitive.ELIMINATE:
        return "ELIMINATE"
    raise InitialStructureClosureError("typed goal vocabulary changed")


def _edge_name(edge: Any) -> str:
    if edge is universe.BoardEdge.TOP:
        return "TOP"
    if edge is universe.BoardEdge.RIGHT:
        return "RIGHT"
    if edge is universe.BoardEdge.BOTTOM:
        return "BOTTOM"
    if edge is universe.BoardEdge.LEFT:
        return "LEFT"
    raise InitialStructureClosureError("typed edge vocabulary changed")


def _profile_vectors(profile: Any) -> Tuple[Position, ...]:
    if profile is universe.VectorProfile.NONE:
        return ()
    if profile is universe.VectorProfile.ORTHOGONAL_4:
        return _ORTHOGONAL
    if profile is universe.VectorProfile.DIAGONAL_4:
        return _DIAGONAL
    if profile is universe.VectorProfile.KING_8:
        return _KING
    raise InitialStructureClosureError("typed vector-profile vocabulary changed")


def _in_bounds(position: Position) -> bool:
    return 0 <= position[0] < 3 and 0 <= position[1] < 3


def _step(position: Position, vector: Position, factor: int = 1) -> Position:
    return (
        position[0] + factor * vector[0],
        position[1] + factor * vector[1],
    )


def _edge_cells(edge: str) -> frozenset[Position]:
    if edge == "TOP":
        return frozenset((0, column) for column in range(3))
    if edge == "RIGHT":
        return frozenset((row, 2) for row in range(3))
    if edge == "BOTTOM":
        return frozenset((2, column) for column in range(3))
    if edge == "LEFT":
        return frozenset((row, 0) for row in range(3))
    raise InitialStructureClosureError("edge escaped the closed vocabulary")


def _closure(
    seeds: Tuple[Position, ...],
    vectors: Tuple[Position, ...],
    _step_position: Any = _step,
    _inside: Any = _in_bounds,
) -> Tuple[Position, ...]:
    if _step is not _step_position or _in_bounds is not _inside:
        raise InitialStructureClosureError("support geometry binding changed")
    reached = set(seeds)
    frontier = list(seeds)
    while frontier:
        source = frontier.pop()
        for vector in vectors:
            target = _step_position(source, vector)
            if _inside(target) and target not in reached:
                reached.add(target)
                frontier.append(target)
    return tuple(sorted(reached))


def _connects_edges(
    positions: Iterable[Position],
    edges: Tuple[str, ...],
    _cells: Any = _edge_cells,
    _step_position: Any = _step,
) -> bool:
    if _edge_cells is not _cells or _step is not _step_position:
        raise InitialStructureClosureError("connection geometry binding changed")
    owned = set(positions)
    if len(edges) != 2:
        raise InitialStructureClosureError("CONNECT target lost its two edges")
    starts = owned.intersection(_cells(edges[0]))
    targets = owned.intersection(_cells(edges[1]))
    if not starts or not targets:
        return False
    reached = set(starts)
    frontier = list(starts)
    while frontier:
        source = frontier.pop()
        for vector in _ORTHOGONAL:
            target = _step_position(source, vector)
            if target in owned and target not in reached:
                reached.add(target)
                frontier.append(target)
    return bool(reached.intersection(targets))


def _bridging_component_count(
    positions: Iterable[Position],
    edges: Tuple[str, ...],
    _cells: Any = _edge_cells,
    _step_position: Any = _step,
) -> int:
    if _edge_cells is not _cells or _step is not _step_position:
        raise InitialStructureClosureError("bridge geometry binding changed")
    owned = set(positions)
    if len(edges) != 2:
        raise InitialStructureClosureError("CONNECT target lost its two edges")
    remaining = set(owned)
    count = 0
    first_edge = _cells(edges[0])
    second_edge = _cells(edges[1])
    while remaining:
        seed = min(remaining)
        component = {seed}
        frontier = [seed]
        remaining.remove(seed)
        while frontier:
            source = frontier.pop()
            for vector in _ORTHOGONAL:
                target = _step_position(source, vector)
                if target in remaining:
                    remaining.remove(target)
                    component.add(target)
                    frontier.append(target)
        if component.intersection(first_edge) and component.intersection(second_edge):
            count += 1
    return count


def _initial_goal(
    goal: str,
    edges: Tuple[str, ...],
    own: Tuple[Position, ...],
    opponent: Tuple[Position, ...],
    _connect: Any = _connects_edges,
    _cells: Any = _edge_cells,
) -> bool:
    if _connects_edges is not _connect or _edge_cells is not _cells:
        raise InitialStructureClosureError("initial-goal geometry binding changed")
    if goal == "CONNECT_EDGES":
        return _connect(own, edges)
    if goal == "REACH_EDGE":
        if len(edges) != 1:
            raise InitialStructureClosureError("REACH target lost its edge")
        return bool(set(own).intersection(_cells(edges[0])))
    if goal == "ELIMINATE":
        if edges:
            raise InitialStructureClosureError("ELIMINATE acquired an edge")
        return not opponent
    raise InitialStructureClosureError("goal escaped the closed vocabulary")


def _legal_breakdown(
    action: str,
    vectors: Tuple[Position, ...],
    own: Tuple[Position, ...],
    opponent: Tuple[Position, ...],
    _step_position: Any = _step,
    _board: Tuple[Position, ...] = _BOARD,
) -> Dict[str, int]:
    if _step is not _step_position or _BOARD is not _board:
        raise InitialStructureClosureError("legal-count geometry binding changed")
    own_set = set(own)
    opponent_set = set(opponent)
    occupied = own_set | opponent_set
    empty = set(_board) - occupied
    empty_destination = 0
    opponent_dependency = 0
    friendly_dependency = 0
    direct_opponent_effect = 0

    if action == "PLACE":
        empty_destination = len(empty)
    else:
        for source in own:
            for vector in vectors:
                adjacent = _step_position(source, vector)
                landing = _step_position(source, vector, 2)
                if action == "MOVE":
                    if adjacent in empty:
                        empty_destination += 1
                elif action == "MOVE_CAPTURE":
                    if adjacent in empty:
                        empty_destination += 1
                    elif adjacent in opponent_set:
                        opponent_dependency += 1
                        direct_opponent_effect += 1
                elif action == "PUSH":
                    if adjacent in empty:
                        empty_destination += 1
                    elif adjacent in opponent_set and landing in empty:
                        opponent_dependency += 1
                        direct_opponent_effect += 1
                elif action == "SWAP":
                    if adjacent in empty:
                        empty_destination += 1
                    elif adjacent in opponent_set:
                        opponent_dependency += 1
                        direct_opponent_effect += 1
                elif action == "HOP":
                    if adjacent in empty:
                        empty_destination += 1
                    elif adjacent in opponent_set and landing in empty:
                        opponent_dependency += 1
                    elif adjacent in own_set and landing in empty:
                        friendly_dependency += 1
                elif action == "CONVERT":
                    if adjacent in opponent_set:
                        opponent_dependency += 1
                        direct_opponent_effect += 1
                else:
                    raise InitialStructureClosureError(
                        "action escaped the legal-count vocabulary"
                    )

    occupied_dependency = opponent_dependency + friendly_dependency
    legal = empty_destination + occupied_dependency
    if legal < 0 or direct_opponent_effect > opponent_dependency:
        raise InitialStructureClosureError("legal dependency arithmetic failed")
    return {
        "legal_action_count": legal,
        "empty_destination_action_count": empty_destination,
        "occupied_dependency_action_count": occupied_dependency,
        "opponent_dependency_action_count": opponent_dependency,
        "friendly_dependency_action_count": friendly_dependency,
        "direct_opponent_effect_action_count": direct_opponent_effect,
    }


def _support_value(
    action: str,
    vectors: Tuple[Position, ...],
    goal: str,
    edges: Tuple[str, ...],
    own: Tuple[Position, ...],
    opponent: Tuple[Position, ...],
    opponent_action: str,
    opponent_vectors: Tuple[Position, ...],
    initial_goal: bool,
    _closure_value: Any = _closure,
    _bridge: Any = _bridging_component_count,
    _cells: Any = _edge_cells,
    _board: Tuple[Position, ...] = _BOARD,
) -> Dict[str, Any]:
    if (
        _closure is not _closure_value
        or _bridging_component_count is not _bridge
        or _edge_cells is not _cells
        or _BOARD is not _board
    ):
        raise InitialStructureClosureError("optimistic-support binding changed")
    if action == "PLACE":
        support = _board
        support_sources = ("PLACE_WHOLE_BOARD",)
    else:
        support_vectors = list(vectors)
        support_sources = ["OWN_ACTION_VECTORS"]
        if opponent and opponent_action in ("PUSH", "SWAP"):
            support_vectors.extend(opponent_vectors)
            support_sources.append("OPPONENT_RELOCATION_VECTORS")
        support = _closure_value(own, tuple(sorted(set(support_vectors))))
        support_sources = tuple(support_sources)

    reach_target_count: Optional[int] = None
    connect_bridging_count: Optional[int] = None
    eliminate_target_count: Optional[int] = None
    eliminate_unreachable_count: Optional[int] = None
    if goal == "CONNECT_EDGES":
        connect_bridging_count = _bridge(support, edges)
        reachable = connect_bridging_count > 0
    elif goal == "REACH_EDGE":
        reach_target_count = len(set(support).intersection(_cells(edges[0])))
        reachable = reach_target_count > 0
    elif goal == "ELIMINATE":
        if opponent_action in (
            "MOVE",
            "MOVE_CAPTURE",
            "PUSH",
            "SWAP",
            "HOP",
        ):
            lineage_vectors = opponent_vectors
        else:
            lineage_vectors = ()
        support_set = set(support)
        eliminate_target_count = len(opponent)
        eliminate_unreachable_count = 0
        for target in opponent:
            lineage = _closure_value((target,), lineage_vectors)
            intersects = bool(support_set.intersection(lineage))
            if not intersects:
                eliminate_unreachable_count += 1
        reachable = eliminate_unreachable_count == 0
    else:
        raise InitialStructureClosureError("goal escaped the support vocabulary")
    reachable = initial_goal or reachable
    return {
        "support_cell_count": len(support),
        "support_sources": list(support_sources),
        "reach_target_cell_count": reach_target_count,
        "connect_bridging_component_count": connect_bridging_count,
        "eliminate_initial_target_count": eliminate_target_count,
        "eliminate_unreachable_target_count": eliminate_unreachable_count,
        "goal_reachable": reachable,
    }


def _contact_value(
    positions_a: Tuple[Position, ...],
    positions_b: Tuple[Position, ...],
    vectors_a: Tuple[Position, ...],
    vectors_b: Tuple[Position, ...],
    _step_position: Any = _step,
) -> Dict[str, Any]:
    if _step is not _step_position:
        raise InitialStructureClosureError("contact geometry binding changed")
    b_set = set(positions_b)
    a_set = set(positions_a)
    contacts_a = {
        (source, _step_position(source, vector))
        for source in positions_a
        for vector in vectors_a
        if _step_position(source, vector) in b_set
    }
    contacts_b = {
        (_step_position(source, vector), source)
        for source in positions_b
        for vector in vectors_b
        if _step_position(source, vector) in a_set
    }
    union = contacts_a | contacts_b
    return {
        "role_a_vector_contact_count": len(contacts_a),
        "role_b_vector_contact_count": len(contacts_b),
        "union_cross_owner_contact_count": len(union),
        "any_cross_owner_contact": bool(union),
        "contact_class": "CONTACT" if union else "SEPARATED",
    }


def _next_count_states(
    state: CountState, actor: str, action: str
) -> Tuple[CountState, ...]:
    a_count, b_count = state
    own, opponent = (
        (a_count, b_count) if actor == "A" else (b_count, a_count)
    )
    empty = 9 - a_count - b_count
    local: List[Tuple[int, int]] = []
    if action == "PLACE":
        if empty > 0:
            local.append((own + 1, opponent))
    elif action in ("MOVE", "PUSH", "HOP"):
        if own > 0 and empty > 0:
            local.append((own, opponent))
    elif action == "SWAP":
        if own > 0 and (empty > 0 or opponent > 0):
            local.append((own, opponent))
    elif action == "MOVE_CAPTURE":
        if own > 0 and empty > 0:
            local.append((own, opponent))
        if own > 0 and opponent > 0:
            local.append((own, opponent - 1))
    elif action == "CONVERT":
        if own > 0 and opponent > 0:
            local.append((own + 1, opponent - 1))
    else:
        raise InitialStructureClosureError("action escaped the count vocabulary")
    absolute = tuple(
        sorted(
            {
                pair if actor == "A" else (pair[1], pair[0])
                for pair in local
            }
        )
    )
    if any(item not in _COUNT_STATES for item in absolute):
        raise InitialStructureClosureError("count transition left the 55-state domain")
    return absolute


def _state_weight(state: CountState) -> int:
    a_count, b_count = state
    return comb(9, a_count) * comb(9 - a_count, b_count)


def _goal_count_satisfied(state: CountState, role: str, goal: str) -> bool:
    a_count, b_count = state
    own, opponent = (
        (a_count, b_count) if role == "A" else (b_count, a_count)
    )
    if goal == "REACH_EDGE":
        return own >= 1
    if goal == "CONNECT_EDGES":
        return own >= 3
    if goal == "ELIMINATE":
        return opponent == 0
    raise InitialStructureClosureError("goal escaped the count vocabulary")


# One private table row is a deeply immutable tuple:
# (A action, B action, initial counts, first player, layers, all goal witnesses,
#  state sum, place-action units, place-scan units, A/B vector-actor units,
#  max-vector action/scan work, entry reference).
_TableRow = Tuple[Any, ...]


def _table_row_payload(row: _TableRow) -> Dict[str, Any]:
    (
        action_a,
        action_b,
        initial,
        first_player,
        layers,
        witnesses,
        state_sum,
        place_action_units,
        place_scan_units,
        vector_a_units,
        vector_b_units,
        max_action_work,
        max_scan_work,
        entry_reference,
    ) = row
    return {
        "entry_reference": entry_reference,
        "action_pair": {"A": action_a, "B": action_b},
        "initial_counts": {"A": initial[0], "B": initial[1]},
        "first_player": first_player,
        "layers": [
            [list(state) for state in layer]
            for layer in layers
        ],
        "minimum_goal_plies": {
            "A": {
                "CONNECT_EDGES": witnesses[0],
                "REACH_EDGE": witnesses[1],
                "ELIMINATE": witnesses[2],
            },
            "B": {
                "CONNECT_EDGES": witnesses[3],
                "REACH_EDGE": witnesses[4],
                "ELIMINATE": witnesses[5],
            },
        },
        "state_weight_sum": state_sum,
        "work_coefficients": {
            "place_action_units": place_action_units,
            "place_scan_units": place_scan_units,
            "vector_actor_units": {
                "A": vector_a_units,
                "B": vector_b_units,
            },
        },
        "maximum_profile_work": {
            "action_candidate_iterations": max_action_work,
            "scan_candidate_iterations": max_scan_work,
        },
    }


def _make_table_row(
    action_a: str,
    action_b: str,
    initial: CountState,
    first_player: str,
) -> _TableRow:
    layers: List[Tuple[CountState, ...]] = [(initial,)]
    place_action_units = 0
    place_scan_units = 0
    vector_a_units = 0
    vector_b_units = 0
    for ply in range(18):
        actor = (
            first_player
            if ply % 2 == 0
            else ("B" if first_player == "A" else "A")
        )
        action = action_a if actor == "A" else action_b
        for state in layers[ply]:
            weight = _state_weight(state)
            own = state[0] if actor == "A" else state[1]
            empty = 9 - state[0] - state[1]
            if action == "PLACE":
                place_action_units += weight * empty
                place_scan_units += weight * 9
            elif actor == "A":
                vector_a_units += weight * own
            else:
                vector_b_units += weight * own
        next_layer = tuple(
            sorted(
                {
                    target
                    for state in layers[ply]
                    for target in _next_count_states(state, actor, action)
                }
            )
        )
        layers.append(next_layer)
    frozen_layers = tuple(layers)
    witnesses: List[Optional[int]] = []
    for role in _OWNERS:
        for goal in _GOALS:
            witness = next(
                (
                    ply
                    for ply, layer in enumerate(frozen_layers)
                    if any(
                        _goal_count_satisfied(state, role, goal)
                        for state in layer
                    )
                ),
                None,
            )
            witnesses.append(witness)
    state_sum = sum(
        _state_weight(state) for layer in frozen_layers for state in layer
    )
    max_action_work = (
        place_action_units + 8 * vector_a_units + 8 * vector_b_units
    )
    max_scan_work = place_scan_units + 8 * vector_a_units + 8 * vector_b_units
    without_reference: _TableRow = (
        action_a,
        action_b,
        initial,
        first_player,
        frozen_layers,
        tuple(witnesses),
        state_sum,
        place_action_units,
        place_scan_units,
        vector_a_units,
        vector_b_units,
        max_action_work,
        max_scan_work,
        "",
    )
    payload = _table_row_payload(without_reference)
    payload.pop("entry_reference")
    reference = _domain_hash(_COUNT_ENTRY_DOMAIN, _canonical_json(payload))
    return without_reference[:-1] + (reference,)


def _build_table_rows() -> Tuple[_TableRow, ...]:
    rows = tuple(
        _make_table_row(action_a, action_b, initial, first_player)
        for action_a in _ACTIONS
        for action_b in _ACTIONS
        for initial in _INITIAL_COUNTS
        for first_player in _OWNERS
    )
    if len(rows) != 49 * 15 * 2:
        raise InitialStructureClosureError("count table entry cardinality changed")
    return rows


def _transition_edge_payload() -> List[Dict[str, Any]]:
    return [
        {
            "actor": actor,
            "action": action,
            "from": list(state),
            "to": list(target),
        }
        for actor in _OWNERS
        for action in _ACTIONS
        for state in _COUNT_STATES
        for target in _next_count_states(state, actor, action)
    ]


def _table_payload(rows: Tuple[_TableRow, ...]) -> Dict[str, Any]:
    edge_payload = _transition_edge_payload()
    memberships = sum(len(layer) for row in rows for layer in row[4])
    maximum_state_sum = max(row[6] for row in rows)
    maximum_action_work = max(row[11] for row in rows)
    maximum_scan_work = max(row[12] for row in rows)
    proof = {
        "count_state_count": len(_COUNT_STATES),
        "directed_transition_edge_count": len(edge_payload),
        "action_pair_count": len(_ACTIONS) ** 2,
        "initial_count_pair_count": len(_INITIAL_COUNTS),
        "tempo_count": len(_OWNERS),
        "entry_count": len(rows),
        "layer_membership_count": memberships,
        "maximum_state_weight_sum": maximum_state_sum,
        "maximum_action_candidate_iterations": maximum_action_work,
        "maximum_scan_candidate_iterations": maximum_scan_work,
        "universal_state_ceiling": 373_958,
        "universal_action_work_ceiling": 25_507_872,
        "universal_scan_work_ceiling": 25_507_872,
    }
    expected = {
        "count_state_count": 55,
        "directed_transition_edge_count": 610,
        "action_pair_count": 49,
        "initial_count_pair_count": 15,
        "tempo_count": 2,
        "entry_count": 1_470,
        "layer_membership_count": 22_428,
        "maximum_state_weight_sum": 115_194,
        "maximum_action_candidate_iterations": 2_070_432,
        "maximum_scan_candidate_iterations": 2_070_432,
        "universal_state_ceiling": 373_958,
        "universal_action_work_ceiling": 25_507_872,
        "universal_scan_work_ceiling": 25_507_872,
    }
    if proof != expected:
        raise InitialStructureClosureError(
            "tight count-lattice proof constants changed: {!r}".format(proof)
        )
    return {
        "count_lattice_table_version": 1,
        "horizon_plies": 18,
        "action_order": list(_ACTIONS),
        "initial_count_order": [list(state) for state in _INITIAL_COUNTS],
        "first_player_order": list(_OWNERS),
        "count_state_order": [list(state) for state in _COUNT_STATES],
        "transition_edges": edge_payload,
        "entries": [_table_row_payload(row) for row in rows],
        "proof": proof,
    }


_COUNT_TABLE_ROWS = _build_table_rows()
_COUNT_TABLE_CANONICAL = _canonical_json(_table_payload(_COUNT_TABLE_ROWS))
_COUNT_TABLE_HASH = _domain_hash(_COUNT_TABLE_DOMAIN, _COUNT_TABLE_CANONICAL)


def _official_table_material(
    _rows: Tuple[_TableRow, ...] = _COUNT_TABLE_ROWS,
    _canonical: str = _COUNT_TABLE_CANONICAL,
    _table_hash: str = _COUNT_TABLE_HASH,
    _domain: bytes = _COUNT_TABLE_DOMAIN,
    _hash: Any = _domain_hash,
) -> Tuple[Tuple[_TableRow, ...], str, str]:
    if (
        _COUNT_TABLE_ROWS is not _rows
        or _COUNT_TABLE_CANONICAL is not _canonical
        or _COUNT_TABLE_HASH is not _table_hash
        or _COUNT_TABLE_DOMAIN is not _domain
        or _domain_hash is not _hash
    ):
        raise InitialStructureClosureError("count-lattice table binding changed")
    return _rows, _canonical, _table_hash


def _table_row(
    action_a: str,
    action_b: str,
    initial: CountState,
    first_player: str,
) -> _TableRow:
    rows, _, _ = _official_table_material()
    try:
        action_pair_index = _ACTIONS.index(action_a) * 7 + _ACTIONS.index(action_b)
        initial_index = _INITIAL_COUNTS.index(initial)
        tempo_index = _OWNERS.index(first_player)
    except ValueError as error:
        raise InitialStructureClosureError("count-lattice lookup key changed") from error
    index = ((action_pair_index * 15) + initial_index) * 2 + tempo_index
    row = rows[index]
    if row[:4] != (action_a, action_b, initial, first_player):
        raise InitialStructureClosureError("count-lattice row ordering changed")
    return row


@dataclass(frozen=True, init=False)
class CountLatticeDescriptorV1:
    """The complete immutable 49x15x2 tight count table and its layers."""

    count_lattice_table_version: int
    _canonical_payload_json: str
    _construction_snapshot: str

    def __init__(
        self,
        count_lattice_table_version: int,
        payload: Any,
        _version: Any = _official_version,
        _table: Any = _official_table_material,
        _tree: Any = _validate_json_tree,
    ) -> None:
        if (
            _official_version is not _version
            or _official_table_material is not _table
            or _validate_json_tree is not _tree
        ):
            raise InitialStructureClosureError("count descriptor authority binding changed")
        _version()
        if type(count_lattice_table_version) is not int:
            raise TypeError("count-lattice table version must be an exact integer")
        if count_lattice_table_version != 1:
            raise ValueError("count-lattice table version must equal 1")
        _exact_dict(payload, "count-lattice descriptor")
        _tree(
            payload,
            "count-lattice descriptor",
            _MAX_COUNT_TABLE_JSON_NODES,
            _MAX_COUNT_TABLE_JSON_DEPTH,
        )
        canonical = _canonical_json(payload)
        _, official, _ = _table()
        if canonical != official:
            raise ValueError("count-lattice descriptor is not the sealed table")
        object.__setattr__(self, "count_lattice_table_version", 1)
        object.__setattr__(self, "_canonical_payload_json", canonical)
        object.__setattr__(
            self,
            "_construction_snapshot",
            _domain_hash(_COUNT_TABLE_DOMAIN, canonical),
        )

    def _assert_unchanged(
        self,
        _table: Any = _official_table_material,
    ) -> None:
        if _official_table_material is not _table:
            raise InitialStructureClosureError("count descriptor table binding changed")
        _require_exact_fields(
            self,
            (
                "count_lattice_table_version",
                "_canonical_payload_json",
                "_construction_snapshot",
            ),
            "count-lattice descriptor",
        )
        _, canonical, table_hash = _table()
        if (
            type(self.count_lattice_table_version) is not int
            or self.count_lattice_table_version != 1
            or type(self._canonical_payload_json) is not str
            or self._canonical_payload_json != canonical
            or type(self._construction_snapshot) is not str
            or self._construction_snapshot != table_hash
        ):
            raise ValueError("count-lattice descriptor changed after construction")

    def to_dict(
        self,
        _table: Any = _official_table_material,
        _fields: Any = _require_exact_fields,
        _json_module: Any = json,
    ) -> Dict[str, Any]:
        if (
            _official_table_material is not _table
            or _require_exact_fields is not _fields
            or json is not _json_module
        ):
            raise InitialStructureClosureError(
                "count descriptor exporter binding changed"
            )
        _fields(
            self,
            (
                "count_lattice_table_version",
                "_canonical_payload_json",
                "_construction_snapshot",
            ),
            "count-lattice descriptor",
        )
        _, canonical, table_hash = _table()
        if (
            type(self) is not CountLatticeDescriptorV1
            or type(self.count_lattice_table_version) is not int
            or self.count_lattice_table_version != 1
            or type(self._canonical_payload_json) is not str
            or self._canonical_payload_json != canonical
            or type(self._construction_snapshot) is not str
            or self._construction_snapshot != table_hash
        ):
            raise ValueError("count-lattice descriptor changed after construction")
        return _json_module.loads(canonical)


def _normalize_count_descriptor(
    value: Any,
    _descriptor_type: Any = CountLatticeDescriptorV1,
    _assert: Any = CountLatticeDescriptorV1._assert_unchanged,
    _to_dict: Any = CountLatticeDescriptorV1.to_dict,
) -> CountLatticeDescriptorV1:
    if (
        CountLatticeDescriptorV1 is not _descriptor_type
        or _descriptor_type._assert_unchanged is not _assert
        or _descriptor_type.to_dict is not _to_dict
    ):
        raise InitialStructureClosureError("count descriptor class binding changed")
    if type(value) is not _descriptor_type:
        raise TypeError("descriptor must be a CountLatticeDescriptorV1")
    _assert(value)
    return value


def _make_count_descriptor_unchecked(
    _table: Any = _official_table_material,
) -> CountLatticeDescriptorV1:
    if _official_table_material is not _table:
        raise InitialStructureClosureError("count descriptor table binding changed")
    _, canonical, table_hash = _table()
    value = object.__new__(CountLatticeDescriptorV1)
    object.__setattr__(value, "count_lattice_table_version", 1)
    object.__setattr__(value, "_canonical_payload_json", canonical)
    object.__setattr__(value, "_construction_snapshot", table_hash)
    return value


def build_count_lattice_descriptor_v1(
    _make: Any = _make_count_descriptor_unchecked,
    _version: Any = _official_version,
    _table: Any = _official_table_material,
) -> CountLatticeDescriptorV1:
    """Return a detached immutable view of the sealed complete count table."""

    if (
        _official_version is not _version
        or _official_table_material is not _table
    ):
        raise InitialStructureClosureError("version guard binding changed")
    _version()
    if _make_count_descriptor_unchecked is not _make:
        raise InitialStructureClosureError("count descriptor builder binding changed")
    return _make()


def canonical_count_lattice_descriptor_json_v1(
    descriptor: CountLatticeDescriptorV1,
    _normalize: Any = _normalize_count_descriptor,
) -> str:
    """Return the exact canonical JSON for the full count-lattice descriptor."""

    if _normalize_count_descriptor is not _normalize:
        raise InitialStructureClosureError("count serializer binding changed")
    return _normalize(descriptor)._canonical_payload_json


def count_lattice_descriptor_hash_v1(
    descriptor: CountLatticeDescriptorV1,
    _normalize: Any = _normalize_count_descriptor,
    _hash: Any = _domain_hash,
) -> str:
    """Return the domain-separated identity of the complete tight table."""

    if _normalize_count_descriptor is not _normalize or _domain_hash is not _hash:
        raise InitialStructureClosureError("count hash validator binding changed")
    source = _normalize(descriptor)
    return _hash(_COUNT_TABLE_DOMAIN, source._canonical_payload_json)


def _detach_carrier(
    value: Any,
    _api: Any = _compiler_api,
    _loads: Any = json.loads,
    _canonical: Any = _canonical_json,
) -> Tuple[str, Dict[str, Any]]:
    if (
        _compiler_api is not _api
        or json.loads is not _loads
        or _canonical_json is not _canonical
    ):
        raise InitialStructureClosureError("carrier authority guard binding changed")
    _, _, canonicalize, _, _ = _api()
    canonical = canonicalize(value)
    payload = _loads(canonical)
    if type(payload) is not dict or _canonical(payload) != canonical:
        raise InitialStructureClosureError("canonical carrier detachment changed")
    _api()
    return canonical, payload


def _carrier_payload_positions(
    value: Any,
    _exact: Any = _exact_dict,
    _keys: Any = _exact_keys,
    _owners: Tuple[str, str] = _OWNERS,
) -> Tuple[Tuple[Position, ...], Tuple[Position, ...]]:
    """Validate the detached compiler image needed by the hot-path kernel."""

    if (
        _exact_dict is not _exact
        or _exact_keys is not _keys
        or _OWNERS is not _owners
    ):
        raise InitialStructureClosureError("carrier payload validator binding changed")
    carrier = _exact(value, "canonical carrier")
    _keys(
        carrier,
        ("carrier_version", "profiled_skeleton", "setup"),
        "canonical carrier",
    )
    if type(carrier["carrier_version"]) is not int or carrier["carrier_version"] != 1:
        raise ValueError("canonical carrier version changed")
    _exact(carrier["profiled_skeleton"], "canonical profiled skeleton")
    setup = _exact(carrier["setup"], "canonical setup")
    _keys(setup, ("setup_version", "positions"), "canonical setup")
    if type(setup["setup_version"]) is not int or setup["setup_version"] != 1:
        raise ValueError("canonical setup version changed")
    positions = _exact(setup["positions"], "canonical setup positions")
    _keys(positions, _owners, "canonical setup positions")

    normalized: List[Tuple[Position, ...]] = []
    for owner in _owners:
        source = positions[owner]
        if type(source) is not list or len(source) > 3:
            raise TypeError("canonical setup positions must be bounded exact arrays")
        converted: List[Position] = []
        for position in source:
            if (
                type(position) is not list
                or len(position) != 2
                or type(position[0]) is not int
                or type(position[1]) is not int
            ):
                raise TypeError("canonical setup coordinates changed type")
            row, column = position
            if not (0 <= row < 3 and 0 <= column < 3):
                raise ValueError("canonical setup coordinate left the 3x3 board")
            converted.append((row, column))
        result = tuple(converted)
        if result != tuple(sorted(result)) or len(set(result)) != len(result):
            raise ValueError("canonical setup positions lost canonical order")
        normalized.append(result)
    positions_a, positions_b = normalized
    if not positions_a and not positions_b:
        raise ValueError("canonical setup cannot be empty")
    if set(positions_a).intersection(positions_b):
        raise ValueError("canonical setup positions must be disjoint")
    return positions_a, positions_b


def _role_data(
    role: Any,
    _action: Any = _action_name,
    _goal: Any = _goal_name,
    _edge: Any = _edge_name,
    _vectors: Any = _profile_vectors,
) -> Tuple[Any, ...]:
    if (
        _action_name is not _action
        or _goal_name is not _goal
        or _edge_name is not _edge
        or _profile_vectors is not _vectors
    ):
        raise InitialStructureClosureError("role-data vocabulary binding changed")
    action = _action(role.signature.action_primitive)
    goal = _goal(role.signature.goal_primitive)
    edges = tuple(_edge(edge) for edge in role.goal_target.edges)
    vectors = _vectors(role.vector_profile)
    if (action == "PLACE") != (not vectors):
        raise InitialStructureClosureError("action/profile coherence changed")
    if goal == "CONNECT_EDGES" and edges not in (
        ("TOP", "BOTTOM"),
        ("RIGHT", "LEFT"),
    ):
        raise InitialStructureClosureError("CONNECT target axis changed")
    if goal == "REACH_EDGE" and (
        len(edges) != 1 or edges[0] not in _EDGES
    ):
        raise InitialStructureClosureError("REACH target changed")
    if goal == "ELIMINATE" and edges:
        raise InitialStructureClosureError("ELIMINATE target changed")
    return (action, goal, edges, vectors)


def _static_descriptor_payload(
    role_a: Tuple[Any, ...], role_b: Tuple[Any, ...]
) -> Dict[str, Any]:
    actions = (role_a[0], role_b[0])
    goals = (role_a[1], role_b[1])
    vector_counts = (len(role_a[3]), len(role_b[3]))
    special_statement_actions = ("MOVE_CAPTURE", "PUSH", "SWAP", "HOP")
    action_concepts = set()
    for action in actions:
        if action == "PLACE":
            action_concepts.add("PLACE")
        elif action == "CONVERT":
            action_concepts.add("CONVERT")
        else:
            action_concepts.add("MOVE")
            if action in special_statement_actions:
                action_concepts.add(action)
    primitive_concepts = tuple(sorted(action_concepts | set(goals)))
    action_substeps = tuple(
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
            "independent_statement_count": 12
            + sum(action in special_statement_actions for action in actions),
            "conditional_clause_count": 5
            + int("MOVE_CAPTURE" in actions)
            + actions.count("PUSH")
            + actions.count("SWAP")
            + actions.count("HOP"),
            "exception_clause_count": 0,
        },
        "operational_substep": {
            "maximum_action_parameter_count": (
                2 if actions == ("PLACE", "PLACE") else 4
            ),
            "tracked_field_count": 5,
            "action_substep_counts": {
                "A": action_substeps[0],
                "B": action_substeps[1],
                "total": sum(action_substeps),
            },
        },
        "primitive_concept": {
            "primitive_concepts": list(primitive_concepts),
            "primitive_concept_count": len(primitive_concepts),
            "learned_concept_count": len(primitive_concepts) + 6,
        },
        "vector_cardinality": {
            "A": vector_counts[0],
            "B": vector_counts[1],
            "total": sum(vector_counts),
            "maximum": max(vector_counts),
        },
    }


def _role_data_from_skeleton_json(
    skeleton_json: str,
    _canonical: Any = _canonical_json,
    _json_module: Any = json,
    _loads: Any = json.loads,
    _actions: Tuple[str, ...] = _ACTIONS,
    _goals: Tuple[str, ...] = _GOALS,
    _edges: Tuple[str, ...] = _EDGES,
    _orthogonal: Tuple[Position, ...] = _ORTHOGONAL,
    _diagonal: Tuple[Position, ...] = _DIAGONAL,
    _king: Tuple[Position, ...] = _KING,
) -> Tuple[Tuple[Any, ...], Tuple[Any, ...]]:
    """Recheck cached role facts from canonical bytes without rebuilding types."""

    if (
        _canonical_json is not _canonical
        or json is not _json_module
        or json.loads is not _loads
        or _ACTIONS is not _actions
        or _GOALS is not _goals
        or _EDGES is not _edges
        or _ORTHOGONAL is not _orthogonal
        or _DIAGONAL is not _diagonal
        or _KING is not _king
    ):
        raise InitialStructureClosureError("prepared literal authority binding changed")
    if type(skeleton_json) is not str:
        raise TypeError("prepared skeleton JSON must be an exact string")
    payload = _loads(skeleton_json)
    root = _exact_dict(payload, "prepared skeleton JSON")
    _exact_keys(root, ("universe_version", "roles"), "prepared skeleton JSON")
    if type(root["universe_version"]) is not int or root["universe_version"] != 1:
        raise ValueError("prepared skeleton JSON version changed")
    roles = _exact_dict(root["roles"], "prepared skeleton roles")
    _exact_keys(roles, _OWNERS, "prepared skeleton roles")
    profile_vectors = {
        "NONE": (),
        "ORTHOGONAL_4": _orthogonal,
        "DIAGONAL_4": _diagonal,
        "KING_8": _king,
    }
    result: List[Tuple[Any, ...]] = []
    for owner in _OWNERS:
        role = _exact_dict(roles[owner], "prepared skeleton role " + owner)
        _exact_keys(
            role,
            (
                "action_primitive",
                "goal_primitive",
                "target_edges",
                "vector_profile",
            ),
            "prepared skeleton role " + owner,
        )
        action = role["action_primitive"]
        goal = role["goal_primitive"]
        profile = role["vector_profile"]
        target_edges = role["target_edges"]
        if (
            type(action) is not str
            or action not in _actions
            or type(goal) is not str
            or goal not in _goals
            or type(profile) is not str
            or profile not in profile_vectors
            or type(target_edges) is not list
            or any(type(edge) is not str or edge not in _edges for edge in target_edges)
        ):
            raise ValueError("prepared skeleton role vocabulary changed")
        vectors = profile_vectors[profile]
        if (action == "PLACE") != (profile == "NONE"):
            raise ValueError("prepared skeleton action/profile coherence changed")
        edges_tuple = tuple(target_edges)
        if goal == "CONNECT_EDGES" and edges_tuple not in (
            ("TOP", "BOTTOM"),
            ("RIGHT", "LEFT"),
        ):
            raise ValueError("prepared CONNECT target changed")
        if goal == "REACH_EDGE" and len(edges_tuple) != 1:
            raise ValueError("prepared REACH target changed")
        if goal == "ELIMINATE" and edges_tuple:
            raise ValueError("prepared ELIMINATE target changed")
        result.append((action, goal, edges_tuple, vectors))
    if _canonical(root) != skeleton_json:
        raise ValueError("prepared skeleton JSON lost canonical bytes")
    return (result[0], result[1])


def _prepared_snapshot_payload(
    skeleton_json: str,
    skeleton_hash: str,
    role_data: Tuple[Tuple[Any, ...], Tuple[Any, ...]],
    table_rows: Tuple[_TableRow, ...],
    static_descriptor_json: str,
    count_table_root: str,
) -> Dict[str, Any]:
    return {
        "skeleton_json": skeleton_json,
        "skeleton_hash": skeleton_hash,
        "roles": [
            {
                "action": role[0],
                "goal": role[1],
                "edges": list(role[2]),
                "vectors": [list(vector) for vector in role[3]],
            }
            for role in role_data
        ],
        "count_entry_references": [row[13] for row in table_rows],
        "static_descriptor_json": static_descriptor_json,
        "count_table_root": count_table_root,
    }


def _prepare_components(
    carrier: Any,
    _detach: Any = _detach_carrier,
    _compiler: Any = _compiler_api,
    _universe: Any = _universe_api,
    _role: Any = _role_data,
    _row: Any = _table_row,
    _static: Any = _static_descriptor_payload,
    _table: Any = _official_table_material,
) -> Tuple[str, str, Tuple[Tuple[Any, ...], Tuple[Any, ...]], Tuple[_TableRow, ...], str, str]:
    if (
        _detach_carrier is not _detach
        or _compiler_api is not _compiler
        or _universe_api is not _universe
        or _role_data is not _role
        or _table_row is not _row
        or _static_descriptor_payload is not _static
        or _official_table_material is not _table
    ):
        raise InitialStructureClosureError("prepared dependency binding changed")
    canonical_carrier, carrier_payload = _detach(carrier)
    _, parse_carrier, canonicalize_carrier, _, _ = _compiler()
    source = parse_carrier(carrier_payload)
    if (
        type(source) is not compiler.TypedSetupCarrierV1
        or canonicalize_carrier(source) != canonical_carrier
    ):
        raise InitialStructureClosureError("prepared carrier detachment changed")
    canonical_skeleton, hash_skeleton = _universe()
    skeleton_json = canonical_skeleton(source.skeleton)
    skeleton_hash = hash_skeleton(source.skeleton)
    roles = (_role(source.skeleton.role_a), _role(source.skeleton.role_b))
    action_a, action_b = roles[0][0], roles[1][0]
    rows = tuple(
        _row(action_a, action_b, initial, first)
        for initial in _INITIAL_COUNTS
        for first in _OWNERS
    )
    static_json = _canonical_json(_static(roles[0], roles[1]))
    _, _, table_root = _table()
    return skeleton_json, skeleton_hash, roles, rows, static_json, table_root


def _validate_prepared_skeleton_authority(
    skeleton_json: str,
    skeleton_hash: str,
    role_data: Tuple[Tuple[Any, ...], Tuple[Any, ...]],
    _parse: Any = universe.parse_profiled_skeleton,
    _canonical: Any = universe.canonical_profiled_skeleton_json,
    _hash: Any = universe.profiled_skeleton_hash,
    _fresh: Any = compiler._require_fresh_transport_skeleton,
    _role: Any = _role_data,
    _loads: Any = json.loads,
) -> None:
    if (
        universe.parse_profiled_skeleton is not _parse
        or universe.canonical_profiled_skeleton_json is not _canonical
        or universe.profiled_skeleton_hash is not _hash
        or compiler._require_fresh_transport_skeleton is not _fresh
        or _role_data is not _role
        or json.loads is not _loads
    ):
        raise InitialStructureClosureError("prepared skeleton authority binding changed")
    skeleton = _fresh(_parse(_loads(skeleton_json)))
    if _canonical(skeleton) != skeleton_json:
        raise ValueError("prepared skeleton JSON is not an exact fresh identity")
    expected_roles = (_role(skeleton.role_a), _role(skeleton.role_b))
    if _hash(skeleton) != skeleton_hash or expected_roles != role_data:
        raise ValueError("prepared skeleton authority fields disagree")


@dataclass(frozen=True, init=False)
class PreparedInitialStructureSkeletonV1:
    """Ephemeral immutable token for repeated setups of one skeleton shard."""

    prepared_version: int
    skeleton_json: str
    skeleton_hash: str
    _role_data: Tuple[Tuple[Any, ...], Tuple[Any, ...]]
    _count_rows: Tuple[_TableRow, ...]
    _static_descriptor_json: str
    count_lattice_table_root: str
    _construction_snapshot: str

    def __init__(
        self,
        prepared_version: int,
        carrier: Any,
        _prepare: Any = _prepare_components,
        _version: Any = _official_version,
        _skeleton_authority: Any = _validate_prepared_skeleton_authority,
    ) -> None:
        if (
            _prepare_components is not _prepare
            or _official_version is not _version
            or _validate_prepared_skeleton_authority is not _skeleton_authority
        ):
            raise InitialStructureClosureError("prepared component binding changed")
        if type(prepared_version) is not int:
            raise TypeError("prepared version must be an exact integer")
        if prepared_version != _version():
            raise ValueError("prepared version must equal 1")
        (
            skeleton_json,
            skeleton_hash,
            roles,
            rows,
            static_json,
            table_root,
        ) = _prepare(carrier)
        _skeleton_authority(skeleton_json, skeleton_hash, roles)
        object.__setattr__(self, "prepared_version", 1)
        object.__setattr__(self, "skeleton_json", skeleton_json)
        object.__setattr__(self, "skeleton_hash", skeleton_hash)
        object.__setattr__(self, "_role_data", roles)
        object.__setattr__(self, "_count_rows", rows)
        object.__setattr__(self, "_static_descriptor_json", static_json)
        object.__setattr__(self, "count_lattice_table_root", table_root)
        object.__setattr__(
            self,
            "_construction_snapshot",
            _domain_hash(
                _RESULT_EVIDENCE_DOMAIN,
                _canonical_json(
                    _prepared_snapshot_payload(
                        skeleton_json,
                        skeleton_hash,
                        roles,
                        rows,
                        static_json,
                        table_root,
                    )
                ),
            ),
        )

    def _assert_unchanged(
        self,
        _row: Any = _table_row,
        _static: Any = _static_descriptor_payload,
        _literal_roles: Any = _role_data_from_skeleton_json,
        _snapshot: Any = _prepared_snapshot_payload,
        _table: Any = _official_table_material,
        _hash: Any = _domain_hash,
        _canonical: Any = _canonical_json,
        _skeleton_hash_domain: bytes = _PROFILED_SKELETON_HASH_DOMAIN,
        _snapshot_hash_domain: bytes = _RESULT_EVIDENCE_DOMAIN,
    ) -> None:
        if (
            _table_row is not _row
            or _static_descriptor_payload is not _static
            or _role_data_from_skeleton_json is not _literal_roles
            or _prepared_snapshot_payload is not _snapshot
            or _official_table_material is not _table
            or _domain_hash is not _hash
            or _canonical_json is not _canonical
            or _PROFILED_SKELETON_HASH_DOMAIN is not _skeleton_hash_domain
            or _RESULT_EVIDENCE_DOMAIN is not _snapshot_hash_domain
        ):
            raise InitialStructureClosureError("prepared validator binding changed")
        _require_exact_fields(
            self,
            (
                "prepared_version",
                "skeleton_json",
                "skeleton_hash",
                "_role_data",
                "_count_rows",
                "_static_descriptor_json",
                "count_lattice_table_root",
                "_construction_snapshot",
            ),
            "prepared initial-structure skeleton",
        )
        if type(self.prepared_version) is not int or self.prepared_version != 1:
            raise ValueError("prepared version changed after construction")
        if (
            type(self.skeleton_json) is not str
            or type(self.skeleton_hash) is not str
            or type(self._role_data) is not tuple
            or len(self._role_data) != 2
            or type(self._count_rows) is not tuple
            or len(self._count_rows) != 30
            or type(self._static_descriptor_json) is not str
            or type(self.count_lattice_table_root) is not str
            or type(self._construction_snapshot) is not str
        ):
            raise TypeError("prepared skeleton field type changed")
        for role in self._role_data:
            if (
                type(role) is not tuple
                or len(role) != 4
                or type(role[0]) is not str
                or type(role[1]) is not str
                or type(role[2]) is not tuple
                or type(role[3]) is not tuple
                or any(type(edge) is not str for edge in role[2])
                or any(
                    type(vector) is not tuple
                    or len(vector) != 2
                    or any(type(item) is not int for item in vector)
                    for vector in role[3]
                )
            ):
                raise TypeError("prepared role data changed type")
        if self._role_data != _literal_roles(self.skeleton_json):
            raise ValueError("prepared role data disagrees with its skeleton bytes")
        actions = (self._role_data[0][0], self._role_data[1][0])
        expected_rows = tuple(
            _row(actions[0], actions[1], initial, first)
            for initial in _INITIAL_COUNTS
            for first in _OWNERS
        )
        if any(
            type(observed) is not tuple
            or len(observed) != 14
            or observed is not expected
            for observed, expected in zip(self._count_rows, expected_rows)
        ):
            raise TypeError("prepared count rows changed identity or type")
        expected_static = _canonical(_static(self._role_data[0], self._role_data[1]))
        _, _, table_root = _table()
        expected_snapshot = _hash(
            _snapshot_hash_domain,
            _canonical(
                _snapshot(
                    self.skeleton_json,
                    self.skeleton_hash,
                    self._role_data,
                    self._count_rows,
                    self._static_descriptor_json,
                    self.count_lattice_table_root,
                )
            ),
        )
        if (
            self.skeleton_hash
            != _hash(_skeleton_hash_domain, self.skeleton_json)
            or self._static_descriptor_json != expected_static
            or self.count_lattice_table_root != table_root
            or self._construction_snapshot != expected_snapshot
        ):
            raise ValueError("prepared skeleton changed after construction")


def _normalize_prepared(
    value: Any,
    _prepared_type: Any = PreparedInitialStructureSkeletonV1,
    _assert: Any = PreparedInitialStructureSkeletonV1._assert_unchanged,
    _fields: Any = _require_exact_fields,
) -> PreparedInitialStructureSkeletonV1:
    if (
        PreparedInitialStructureSkeletonV1 is not _prepared_type
        or _prepared_type._assert_unchanged is not _assert
        or _require_exact_fields is not _fields
    ):
        raise InitialStructureClosureError("prepared skeleton class binding changed")
    if type(value) is not _prepared_type:
        raise TypeError("prepared must be a PreparedInitialStructureSkeletonV1")
    expected_fields = (
        "prepared_version",
        "skeleton_json",
        "skeleton_hash",
        "_role_data",
        "_count_rows",
        "_static_descriptor_json",
        "count_lattice_table_root",
        "_construction_snapshot",
    )
    _fields(value, expected_fields, "prepared initial-structure skeleton")
    field_snapshot = vars(value).copy()
    if type(field_snapshot) is not dict or set(field_snapshot) != set(expected_fields):
        raise TypeError("prepared initial-structure skeleton snapshot changed")
    detached = object.__new__(_prepared_type)
    for name in expected_fields:
        object.__setattr__(detached, name, field_snapshot[name])
    _assert(detached)
    return detached


def prepare_initial_structure_skeleton_v1(
    carrier: compiler.TypedSetupCarrierV1,
    _prepared_type: Any = PreparedInitialStructureSkeletonV1,
    _version: Any = _official_version,
) -> PreparedInitialStructureSkeletonV1:
    """Validate one carrier and prepare immutable data shared by its shard."""

    if _official_version is not _version:
        raise InitialStructureClosureError("version guard binding changed")
    _version()
    if PreparedInitialStructureSkeletonV1 is not _prepared_type:
        raise InitialStructureClosureError("prepared constructor binding changed")
    return _prepared_type(1, carrier)


def _count_reference_value(
    row: _TableRow,
    goal_a: str,
    goal_b: str,
    vector_count_a: int,
    vector_count_b: int,
) -> Dict[str, Any]:
    goal_indexes = {
        "CONNECT_EDGES": 0,
        "REACH_EDGE": 1,
        "ELIMINATE": 2,
    }
    witness_a = row[5][goal_indexes[goal_a]]
    witness_b = row[5][3 + goal_indexes[goal_b]]
    action_work = row[7] + vector_count_a * row[9] + vector_count_b * row[10]
    scan_work = row[8] + vector_count_a * row[9] + vector_count_b * row[10]
    if (
        row[6] > 115_194
        or action_work > 2_070_432
        or scan_work > 2_070_432
        or action_work > 25_507_872
        or scan_work > 25_507_872
    ):
        raise InitialStructureClosureError("per-schedule work proof exceeded its bound")
    return {
        "first_player": row[3],
        "entry_reference": row[13],
        "minimum_goal_plies": {"A": witness_a, "B": witness_b},
        "state_weight_sum": row[6],
        "work": {
            "action_candidate_iterations": action_work,
            "scan_candidate_iterations": scan_work,
        },
    }


def _role_fact(
    role: str,
    role_data: Tuple[Any, ...],
    opponent_data: Tuple[Any, ...],
    own: Tuple[Position, ...],
    opponent: Tuple[Position, ...],
    _initial: Any = _initial_goal,
    _legal: Any = _legal_breakdown,
    _support: Any = _support_value,
) -> Dict[str, Any]:
    if (
        _initial_goal is not _initial
        or _legal_breakdown is not _legal
        or _support_value is not _support
    ):
        raise InitialStructureClosureError("role-fact dependency binding changed")
    action, goal, edges, vectors = role_data
    opponent_action, _, _, opponent_vectors = opponent_data
    initial_goal = _initial(goal, edges, own, opponent)
    legal = _legal(action, vectors, own, opponent)
    support = _support(
        action,
        vectors,
        goal,
        edges,
        own,
        opponent,
        opponent_action,
        opponent_vectors,
        initial_goal,
    )
    return {
        "role": role,
        "action": action,
        "goal": goal,
        "target_edges": list(edges),
        "initial_actor_count": len(own),
        "initial_opponent_count": len(opponent),
        "initial_goal_satisfied": initial_goal,
        "legal": legal,
        "optimistic_support": support,
    }


def _rejection_reasons(
    role_facts: Dict[str, Dict[str, Any]],
    count_references: Tuple[Dict[str, Any], Dict[str, Any]],
    _codes: Tuple[str, ...] = _REASON_CODES,
    _owners: Tuple[str, str] = _OWNERS,
) -> List[Dict[str, Any]]:
    if _REASON_CODES is not _codes or _OWNERS is not _owners:
        raise InitialStructureClosureError("rejection vocabulary binding changed")
    reasons: List[Dict[str, Any]] = []
    for code in _codes:
        if code == "COUNT_LATTICE_GOAL_UNREACHABLE_WITHIN_18":
            for role in _owners:
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
        for role in _owners:
            fact = role_facts[role]
            reject = False
            if code == "ZERO_ACTOR_WITH_NONPLACE":
                reject = fact["initial_actor_count"] == 0 and fact["action"] != "PLACE"
            elif code == "INITIAL_GOAL_SATISFIED":
                reject = fact["initial_goal_satisfied"]
            elif code == "INITIAL_IMMOBILITY":
                reject = fact["legal"]["legal_action_count"] == 0
            elif code == "OPTIMISTIC_GOAL_UNREACHABLE":
                reject = not fact["optimistic_support"]["goal_reachable"]
            else:  # pragma: no cover - closed tuple above
                raise InitialStructureClosureError("rejection vocabulary changed")
            if reject:
                reasons.append({"code": code, "role": role, "first_player": None})
    return reasons


def _derive_payload(
    prepared: PreparedInitialStructureSkeletonV1,
    carrier_canonical: str,
    carrier_payload: Dict[str, Any],
    _normalize: Any = _normalize_prepared,
    _canonical: Any = _canonical_json,
    _role: Any = _role_fact,
    _count: Any = _count_reference_value,
    _reasons: Any = _rejection_reasons,
    _contact: Any = _contact_value,
    _compiler: Any = _compiler_api,
    _loads: Any = json.loads,
    _hash: Any = _domain_hash,
    _setup_hash_domain: bytes = _TYPED_SETUP_HASH_DOMAIN,
    _carrier_hash_domain: bytes = _TYPED_CARRIER_HASH_DOMAIN,
    _result_evidence_domain: bytes = _RESULT_EVIDENCE_DOMAIN,
    _positions: Any = _carrier_payload_positions,
) -> Dict[str, Any]:
    if (
        _normalize_prepared is not _normalize
        or _canonical_json is not _canonical
        or _role_fact is not _role
        or _count_reference_value is not _count
        or _rejection_reasons is not _reasons
        or _contact_value is not _contact
        or _compiler_api is not _compiler
        or json.loads is not _loads
        or _domain_hash is not _hash
        or _TYPED_SETUP_HASH_DOMAIN is not _setup_hash_domain
        or _TYPED_CARRIER_HASH_DOMAIN is not _carrier_hash_domain
        or _RESULT_EVIDENCE_DOMAIN is not _result_evidence_domain
        or _carrier_payload_positions is not _positions
    ):
        raise InitialStructureClosureError("result derivation binding changed")
    source_prepared = _normalize(prepared)
    positions_a, positions_b = _positions(carrier_payload)
    skeleton_json = _canonical(carrier_payload["profiled_skeleton"])
    skeleton_hash = source_prepared.skeleton_hash
    if skeleton_json != source_prepared.skeleton_json:
        raise ValueError("prepared skeleton does not match the carrier skeleton")
    role_a, role_b = source_prepared._role_data
    role_facts = {
        "A": _role("A", role_a, role_b, positions_a, positions_b),
        "B": _role("B", role_b, role_a, positions_b, positions_a),
    }
    initial_counts = (len(positions_a), len(positions_b))
    try:
        initial_index = _INITIAL_COUNTS.index(initial_counts)
    except ValueError as error:
        raise InitialStructureClosureError("carrier setup left the initial count table") from error
    rows = (
        source_prepared._count_rows[initial_index * 2],
        source_prepared._count_rows[initial_index * 2 + 1],
    )
    if tuple(row[:4] for row in rows) != (
        (role_a[0], role_b[0], initial_counts, "A"),
        (role_a[0], role_b[0], initial_counts, "B"),
    ):
        raise InitialStructureClosureError("prepared count reference ordering changed")
    count_references = tuple(
        _count(
            row,
            role_a[1],
            role_b[1],
            len(role_a[3]),
            len(role_b[3]),
        )
        for row in rows
    )
    reasons = _reasons(role_facts, count_references)  # type: ignore[arg-type]

    occupied = len(positions_a) + len(positions_b)
    descriptor_groups = _loads(source_prepared._static_descriptor_json)
    descriptor_groups["operational_substep"]["initial_legal_action_counts"] = {
        "A": role_facts["A"]["legal"]["legal_action_count"],
        "B": role_facts["B"]["legal"]["legal_action_count"],
        "total": sum(
            role_facts[role]["legal"]["legal_action_count"] for role in _OWNERS
        ),
    }
    descriptor_groups["density"] = {
        "initial_piece_counts": {"A": len(positions_a), "B": len(positions_b)},
        "initial_occupied_count": occupied,
        "initial_empty_cell_count": 9 - occupied,
        "role_piece_fractions": {
            "A": {"numerator": len(positions_a), "denominator": 9},
            "B": {"numerator": len(positions_b), "denominator": 9},
        },
        "initial_occupancy_fraction": {"numerator": occupied, "denominator": 9},
        "initial_empty_fraction": {"numerator": 9 - occupied, "denominator": 9},
    }
    descriptor_groups["contact"] = _contact(
        positions_a, positions_b, role_a[3], role_b[3]
    )
    descriptor_groups["dependency"] = {
        role: dict(role_facts[role]["legal"]) for role in _OWNERS
    }

    _compiler()
    setup_json = _canonical(carrier_payload["setup"])
    body = {
        "initial_structure_result_version": 1,
        "kernel_version": 1,
        "carrier": carrier_payload,
        "identities": {
            "typed_setup_hash": _hash(_setup_hash_domain, setup_json),
            "typed_skeleton_hash": skeleton_hash,
            "typed_carrier_hash": _hash(_carrier_hash_domain, carrier_canonical),
            "typed_carrier_canonical_byte_count": len(
                carrier_canonical.encode("utf-8")
            ),
        },
        "role_facts": role_facts,
        "count_lattice": {
            "table_version": 1,
            "table_root": source_prepared.count_lattice_table_root,
            "action_pair": {"A": role_a[0], "B": role_b[0]},
            "initial_counts": {"A": initial_counts[0], "B": initial_counts[1]},
            "tempo_references": list(count_references),
        },
        "descriptor_groups": descriptor_groups,
        "rejection_reasons": reasons,
        "eligible": not reasons,
    }
    evidence_digest = _hash(_result_evidence_domain, _canonical(body))
    result = dict(body)
    result["evidence_digest"] = evidence_digest
    return result


def _derive_from_carrier(
    carrier: Any,
    prepared: Optional[PreparedInitialStructureSkeletonV1] = None,
    _api: Any = _compiler_api,
    _detach: Any = _detach_carrier,
    _prepared_type: Any = PreparedInitialStructureSkeletonV1,
    _normalize: Any = _normalize_prepared,
    _derive: Any = _derive_payload,
) -> Dict[str, Any]:
    if (
        _compiler_api is not _api
        or _detach_carrier is not _detach
        or PreparedInitialStructureSkeletonV1 is not _prepared_type
        or _normalize_prepared is not _normalize
        or _derive_payload is not _derive
    ):
        raise InitialStructureClosureError("carrier derivation binding changed")
    if type(carrier) is dict:
        _, parse, _, _, _ = _api()
        carrier = parse(carrier)
    canonical, payload = _detach(carrier)
    if prepared is None:
        _, parse, canonicalize, _, _ = _api()
        detached = parse(payload)
        if (
            type(detached) is not compiler.TypedSetupCarrierV1
            or canonicalize(detached) != canonical
        ):
            raise InitialStructureClosureError("result carrier detachment changed")
        prepared_value = _prepared_type(1, detached)
    else:
        prepared_value = _normalize(prepared)
    return _derive(prepared_value, canonical, payload)


def _validate_result_payload(
    value: Any,
    _derive: Any = _derive_from_carrier,
) -> str:
    if _derive_from_carrier is not _derive:
        raise InitialStructureClosureError("result rederivation binding changed")
    payload = _exact_dict(value, "initial-structure result")
    _validate_json_tree(payload, "initial-structure result")
    canonical = _canonical_json(payload)
    if len(canonical.encode("utf-8")) > _MAX_RESULT_JSON_BYTES:
        raise ValueError("initial-structure result exceeds the byte cap")
    if "carrier" not in payload:
        raise ValueError("initial-structure result is missing carrier")
    expected = _derive(payload["carrier"])
    if canonical != _canonical_json(expected):
        raise ValueError("initial-structure result does not match full rederivation")
    return canonical


@dataclass(frozen=True, init=False)
class InitialStructureResultV1:
    """One strict, immutable, completely rederivable carrier observation."""

    result_version: int
    _canonical_payload_json: str
    _construction_snapshot: str

    def __init__(
        self,
        result_version: int,
        payload: Any,
        _validate: Any = _validate_result_payload,
        _version: Any = _official_version,
    ) -> None:
        if _official_version is not _version:
            raise InitialStructureClosureError("version guard binding changed")
        _version()
        if _validate_result_payload is not _validate:
            raise InitialStructureClosureError("result validator binding changed")
        if type(result_version) is not int:
            raise TypeError("result version must be an exact integer")
        if result_version != 1:
            raise ValueError("result version must equal 1")
        canonical = _validate(payload)
        object.__setattr__(self, "result_version", 1)
        object.__setattr__(self, "_canonical_payload_json", canonical)
        object.__setattr__(
            self,
            "_construction_snapshot",
            _domain_hash(_RESULT_DOMAIN, canonical),
        )

    def _assert_unchanged(
        self,
        _validate: Any = _validate_result_payload,
        _loads: Any = json.loads,
    ) -> None:
        if _validate_result_payload is not _validate or json.loads is not _loads:
            raise InitialStructureClosureError("result validator binding changed")
        _require_exact_fields(
            self,
            ("result_version", "_canonical_payload_json", "_construction_snapshot"),
            "initial-structure result",
        )
        if (
            type(self.result_version) is not int
            or self.result_version != 1
            or type(self._canonical_payload_json) is not str
            or type(self._construction_snapshot) is not str
        ):
            raise TypeError("initial-structure result field type changed")
        canonical = _validate(_loads(self._canonical_payload_json))
        if (
            canonical != self._canonical_payload_json
            or self._construction_snapshot != _domain_hash(_RESULT_DOMAIN, canonical)
        ):
            raise ValueError("initial-structure result changed after construction")

    def to_dict(
        self,
        _validate: Any = _validate_result_payload,
        _fields: Any = _require_exact_fields,
        _hash: Any = _domain_hash,
        _json_module: Any = json,
        _loads: Any = json.loads,
        _result_domain: bytes = _RESULT_DOMAIN,
    ) -> Dict[str, Any]:
        if (
            _validate_result_payload is not _validate
            or _require_exact_fields is not _fields
            or _domain_hash is not _hash
            or json is not _json_module
            or json.loads is not _loads
            or _RESULT_DOMAIN is not _result_domain
        ):
            raise InitialStructureClosureError("result exporter binding changed")
        _fields(
            self,
            ("result_version", "_canonical_payload_json", "_construction_snapshot"),
            "initial-structure result",
        )
        if (
            type(self) is not InitialStructureResultV1
            or type(self.result_version) is not int
            or self.result_version != 1
            or type(self._canonical_payload_json) is not str
            or type(self._construction_snapshot) is not str
        ):
            raise TypeError("initial-structure result field type changed")
        canonical = _validate(_loads(self._canonical_payload_json))
        if (
            canonical != self._canonical_payload_json
            or self._construction_snapshot != _hash(_result_domain, canonical)
        ):
            raise ValueError("initial-structure result changed after construction")
        return _loads(canonical)


def _normalize_result(
    value: Any,
    _result_type: Any = InitialStructureResultV1,
    _assert: Any = InitialStructureResultV1._assert_unchanged,
    _to_dict: Any = InitialStructureResultV1.to_dict,
) -> InitialStructureResultV1:
    if (
        InitialStructureResultV1 is not _result_type
        or _result_type._assert_unchanged is not _assert
        or _result_type.to_dict is not _to_dict
    ):
        raise InitialStructureClosureError("result class binding changed")
    if type(value) is not _result_type:
        raise TypeError("result must be an InitialStructureResultV1")
    _assert(value)
    return value


def _make_result_unchecked(
    payload: Dict[str, Any],
    _canonical: Any = _canonical_json,
    _hash: Any = _domain_hash,
    _result_domain: bytes = _RESULT_DOMAIN,
) -> InitialStructureResultV1:
    if (
        _canonical_json is not _canonical
        or _domain_hash is not _hash
        or _RESULT_DOMAIN is not _result_domain
    ):
        raise InitialStructureClosureError("unchecked result maker binding changed")
    canonical = _canonical(payload)
    value = object.__new__(InitialStructureResultV1)
    object.__setattr__(value, "result_version", 1)
    object.__setattr__(value, "_canonical_payload_json", canonical)
    object.__setattr__(
        value, "_construction_snapshot", _hash(_result_domain, canonical)
    )
    return value


def derive_prepared_initial_structure_result_v1(
    prepared: PreparedInitialStructureSkeletonV1,
    carrier: compiler.TypedSetupCarrierV1,
    _derive: Any = _derive_payload,
    _make: Any = _make_result_unchecked,
    _version: Any = _official_version,
    _normalize: Any = _normalize_prepared,
    _detach: Any = _detach_carrier,
) -> InitialStructureResultV1:
    """Derive one carrier using an independently validated one-shard token."""

    if (
        _official_version is not _version
        or _normalize_prepared is not _normalize
        or _detach_carrier is not _detach
    ):
        raise InitialStructureClosureError("prepared public dependency binding changed")
    _version()
    if _derive_payload is not _derive or _make_result_unchecked is not _make:
        raise InitialStructureClosureError("prepared derivation binding changed")
    canonical, payload = _detach(carrier)
    result_payload = _derive(prepared, canonical, payload)
    return _make(result_payload)


def derive_prepared_initial_structure_snapshot_v1(
    prepared: PreparedInitialStructureSkeletonV1,
    carrier: compiler.TypedSetupCarrierV1,
    _derive: Any = _derive_payload,
    _version: Any = _official_version,
    _detach: Any = _detach_carrier,
    _canonical: Any = _canonical_json,
    _hash: Any = _domain_hash,
    _result_domain: bytes = _RESULT_DOMAIN,
) -> Tuple[str, str]:
    """Derive one fresh canonical result and hash without revalidating it twice.

    The returned exact tuple is ``(canonical_result_json, result_hash)``.  It is
    an output-only bridge for the streaming census: no parser accepts it as
    authority, and the strict prepared/carrier boundaries are crossed on every
    call.
    """

    if (
        _official_version is not _version
        or _detach_carrier is not _detach
        or _canonical_json is not _canonical
        or _domain_hash is not _hash
        or _RESULT_DOMAIN is not _result_domain
    ):
        raise InitialStructureClosureError("prepared snapshot dependency binding changed")
    _version()
    if _derive_payload is not _derive:
        raise InitialStructureClosureError("prepared snapshot derivation binding changed")
    carrier_canonical, carrier_payload = _detach(carrier)
    result_payload = _derive(prepared, carrier_canonical, carrier_payload)
    canonical_result = _canonical(result_payload)
    return (canonical_result, _hash(_result_domain, canonical_result))


def derive_initial_structure_result_v1(
    carrier: compiler.TypedSetupCarrierV1,
    _prepare: Any = prepare_initial_structure_skeleton_v1,
    _derive: Any = derive_prepared_initial_structure_result_v1,
    _version: Any = _official_version,
) -> InitialStructureResultV1:
    """Derive all fixed initial-structure facts for one strict typed carrier."""

    if _official_version is not _version:
        raise InitialStructureClosureError("version guard binding changed")
    _version()
    if (
        prepare_initial_structure_skeleton_v1 is not _prepare
        or derive_prepared_initial_structure_result_v1 is not _derive
    ):
        raise InitialStructureClosureError("one-carrier derivation binding changed")
    prepared = _prepare(carrier)
    return _derive(prepared, carrier)


def parse_initial_structure_result_v1(
    value: Any,
    _result_type: Any = InitialStructureResultV1,
    _version: Any = _official_version,
) -> InitialStructureResultV1:
    """Parse only an exact JSON-compatible result that fully rederives."""

    if _official_version is not _version:
        raise InitialStructureClosureError("version guard binding changed")
    _version()
    if InitialStructureResultV1 is not _result_type:
        raise InitialStructureClosureError("result parser class binding changed")
    payload = _exact_dict(value, "initial-structure result")
    version = payload.get("initial_structure_result_version")
    if type(version) is not int:
        raise TypeError("initial-structure result version must be an exact integer")
    return _result_type(version, payload)


def canonical_initial_structure_result_json_v1(
    result: InitialStructureResultV1,
    _normalize: Any = _normalize_result,
) -> str:
    """Return exact canonical JSON after complete result rederivation."""

    if _normalize_result is not _normalize:
        raise InitialStructureClosureError("result serializer binding changed")
    return _normalize(result)._canonical_payload_json


def initial_structure_result_hash_v1(
    result: InitialStructureResultV1,
    _normalize: Any = _normalize_result,
    _hash: Any = _domain_hash,
    _result_domain: bytes = _RESULT_DOMAIN,
) -> str:
    """Return the domain-separated identity of one revalidated result."""

    if (
        _normalize_result is not _normalize
        or _domain_hash is not _hash
        or _RESULT_DOMAIN is not _result_domain
    ):
        raise InitialStructureClosureError("result hash validator binding changed")
    source = _normalize(result)
    return _hash(_result_domain, source._canonical_payload_json)


def validate_initial_structure_result_v1(
    carrier: compiler.TypedSetupCarrierV1,
    result_or_exact_dict: Any,
    _parse: Any = parse_initial_structure_result_v1,
    _derive: Any = derive_initial_structure_result_v1,
    _version: Any = _official_version,
    _normalize: Any = _normalize_result,
) -> InitialStructureResultV1:
    """Recompute every field; a stored digest is never treated as authority."""

    if (
        _official_version is not _version
        or _normalize_result is not _normalize
    ):
        raise InitialStructureClosureError("result public validation binding changed")
    _version()
    if (
        parse_initial_structure_result_v1 is not _parse
        or derive_initial_structure_result_v1 is not _derive
    ):
        raise InitialStructureClosureError("result validation binding changed")
    if type(result_or_exact_dict) is dict:
        observed = _parse(result_or_exact_dict)
    else:
        observed = _normalize(result_or_exact_dict)
    expected = _derive(carrier)
    if observed._canonical_payload_json != expected._canonical_payload_json:
        raise ValueError("initial-structure result does not match the supplied carrier")
    return expected


__all__ = (
    "INITIAL_STRUCTURE_KERNEL_VERSION_V1",
    "INITIAL_STRUCTURE_RESULT_VERSION_V1",
    "PREPARED_INITIAL_STRUCTURE_VERSION_V1",
    "COUNT_LATTICE_TABLE_VERSION_V1",
    "InitialStructureClosureError",
    "PreparedInitialStructureSkeletonV1",
    "InitialStructureResultV1",
    "CountLatticeDescriptorV1",
    "prepare_initial_structure_skeleton_v1",
    "derive_initial_structure_result_v1",
    "derive_prepared_initial_structure_result_v1",
    "derive_prepared_initial_structure_snapshot_v1",
    "parse_initial_structure_result_v1",
    "canonical_initial_structure_result_json_v1",
    "initial_structure_result_hash_v1",
    "validate_initial_structure_result_v1",
    "build_count_lattice_descriptor_v1",
    "canonical_count_lattice_descriptor_json_v1",
    "count_lattice_descriptor_hash_v1",
)
