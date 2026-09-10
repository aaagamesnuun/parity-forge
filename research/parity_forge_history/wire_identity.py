"""Bounded, transition-free schema 1--4 wire normalization and identities.

This module accepts exact JSON data, never executable DSL objects.  The schema
and spatial maps are intentionally independent of the legacy package; tests
compare their output with the authoritative parser and D4 implementation.
"""

from __future__ import annotations

import hashlib
import json
import re


MAX_DEFINITION_JSON_BYTES_V1 = 65_536
MAX_DEFINITION_JSON_NODES_V1 = 2_048
MAX_DEFINITION_JSON_DEPTH_V1 = 12
D4_TRANSFORMS_V1 = ("I", "R90", "R180", "R270", "FLR", "FTB", "FD", "FA")

_IDENTIFIER = re.compile(r"[a-z][a-z0-9_]{0,31}\Z")
_BASE_KEYS = (
    "schema_version", "name", "board_size", "first_player", "max_plies",
    "roles", "initial_pieces",
)
_EDGES = ("TOP", "RIGHT", "BOTTOM", "LEFT")
_D4_DOMAIN = b"parity-forge:d4:v1\0"
_NEUTRAL_DOMAIN = b"parity-forge:plan0015:history-role-neutral-definition:v1\0"


class WireDefinitionError(ValueError):
    """The input is not a bounded exact JSON definition in schemas 1--4."""


def _canonical_bytes(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _preflight(value):
    """Bound traversal before serializing, comparing or interpreting input."""
    remaining_nodes = MAX_DEFINITION_JSON_NODES_V1
    string_bytes = 0
    active = set()

    def visit(item, depth):
        nonlocal remaining_nodes, string_bytes
        remaining_nodes -= 1
        if remaining_nodes < 0 or depth > MAX_DEFINITION_JSON_DEPTH_V1:
            raise WireDefinitionError("definition JSON structure exceeds limits")
        kind = type(item)
        if kind is str:
            if len(item) > MAX_DEFINITION_JSON_BYTES_V1:
                raise WireDefinitionError("definition JSON string exceeds limit")
            try:
                string_bytes += len(item.encode("utf-8"))
            except UnicodeEncodeError as error:
                raise WireDefinitionError("definition JSON requires UTF-8 strings") from error
            if string_bytes > MAX_DEFINITION_JSON_BYTES_V1:
                raise WireDefinitionError("definition JSON strings exceed limit")
            return
        if kind is int:
            if item.bit_length() > 64:
                raise WireDefinitionError("definition JSON integer exceeds limit")
            return
        if item is None or kind is bool:
            return
        if kind not in (dict, list):
            raise WireDefinitionError("definition requires exact JSON types")
        if len(item) > MAX_DEFINITION_JSON_NODES_V1:
            raise WireDefinitionError("definition JSON container exceeds limit")
        identity = id(item)
        if identity in active:
            raise WireDefinitionError("definition JSON cannot contain a cycle")
        active.add(identity)
        try:
            if kind is dict:
                for key, child in item.items():
                    if type(key) is not str:
                        raise WireDefinitionError("definition JSON keys must be exact strings")
                    visit(key, depth + 1)
                    visit(child, depth + 1)
            else:
                for child in item:
                    visit(child, depth + 1)
        finally:
            active.remove(identity)

    if type(value) is not dict:
        raise WireDefinitionError("definition must be an exact JSON object")
    visit(value, 0)
    encoded = _canonical_bytes(value)
    if len(encoded) > MAX_DEFINITION_JSON_BYTES_V1:
        raise WireDefinitionError("definition JSON bytes exceed limit")
    return encoded


def _keys(value, expected, label):
    if type(value) is not dict or set(value) != set(expected):
        raise WireDefinitionError(label + " keys mismatch")


def _integer(value, minimum, maximum, label):
    if type(value) is not int or not minimum <= value <= maximum:
        raise WireDefinitionError(label + " must be an exact integer in range")
    return value


def _enum(value, allowed, label):
    if type(value) is not str or value not in allowed:
        raise WireDefinitionError(label + " is not an admitted string")
    return value


def _piece(value):
    if type(value) is not str or _IDENTIFIER.fullmatch(value) is None:
        raise WireDefinitionError("piece must be a DSL identifier")
    return value


def _position(value, minimum, maximum, label):
    if type(value) is not list or len(value) != 2:
        raise WireDefinitionError(label + " must contain two integers")
    return [_integer(item, minimum, maximum, label) for item in value]


def _role(value, version):
    _keys(value, ("action", "goal"), "role")
    action = value["action"]
    if type(action) is not dict:
        raise WireDefinitionError("action must be an object")
    allowed = ("PLACE", "MOVE")
    if version >= 3:
        allowed += ("MOVE_CAPTURE",)
    if version == 4:
        allowed += ("PUSH", "SWAP", "HOP", "CONVERT")
    action_kind = _enum(action.get("kind"), allowed, "action kind")
    action_keys = ("kind", "piece")
    if action_kind != "PLACE":
        action_keys += ("vectors",)
    _keys(action, action_keys, "action")
    normalized_action = {"kind": action_kind, "piece": _piece(action["piece"])}
    if action_kind != "PLACE":
        vectors = action["vectors"]
        if type(vectors) is not list or not 1 <= len(vectors) <= 8:
            raise WireDefinitionError("action vectors must contain one through eight offsets")
        vectors = [_position(vector, -1, 1, "vector") for vector in vectors]
        distinct = {tuple(vector) for vector in vectors}
        if (0, 0) in distinct or len(distinct) != len(vectors):
            raise WireDefinitionError("action vectors contain a zero or duplicate offset")
        normalized_action["vectors"] = sorted(vectors)

    goal = value["goal"]
    if type(goal) is not dict:
        raise WireDefinitionError("goal must be an object")
    allowed_goals = ("CONNECT_EDGES", "REACH_EDGE")
    if version == 4:
        allowed_goals += ("ELIMINATE",)
    goal_kind = _enum(goal.get("kind"), allowed_goals, "goal kind")
    goal_keys = ("kind", "piece")
    if goal_kind == "CONNECT_EDGES":
        goal_keys += ("edges",)
    elif goal_kind == "REACH_EDGE":
        goal_keys += ("edge",)
    _keys(goal, goal_keys, "goal")
    normalized_goal = {"kind": goal_kind, "piece": _piece(goal["piece"])}
    if goal_kind == "CONNECT_EDGES":
        edges = goal["edges"]
        if type(edges) is not list or len(edges) != 2:
            raise WireDefinitionError("connection edges must contain two strings")
        edges = [_enum(edge, _EDGES, "edge") for edge in edges]
        if set(edges) not in ({"TOP", "BOTTOM"}, {"LEFT", "RIGHT"}):
            raise WireDefinitionError("connection edges must be opposite")
        normalized_goal["edges"] = sorted(edges)
    elif goal_kind == "REACH_EDGE":
        normalized_goal["edge"] = _enum(goal["edge"], _EDGES, "edge")
    return {"action": normalized_action, "goal": normalized_goal}


def normalize_definition_v1(mapping):
    """Return detached parser-normalized JSON, rejecting non-wire carriers."""
    mapping = json.loads(_preflight(mapping))
    version = _integer(mapping.get("schema_version"), 1, 4, "schema version")
    _keys(mapping, _BASE_KEYS + (("terminal_policy",) if version == 2 else ()), "definition")
    name = mapping["name"]
    if type(name) is not str or not name.strip() or len(name) > 120:
        raise WireDefinitionError("name must have one through 120 characters")
    board_size = _integer(mapping["board_size"], 3, 5, "board size")
    first_player = _enum(mapping["first_player"], ("A", "B"), "first player")
    max_plies = _integer(mapping["max_plies"], 1, 1000, "max plies")
    _keys(mapping["roles"], ("A", "B"), "roles")
    roles = {owner: _role(mapping["roles"][owner], version) for owner in ("A", "B")}
    action_kinds = {role["action"]["kind"] for role in roles.values()}
    if version == 3 and "MOVE_CAPTURE" not in action_kinds:
        raise WireDefinitionError("schema 3 requires MOVE_CAPTURE")
    if version == 4 and not (
        action_kinds & {"PUSH", "SWAP", "HOP", "CONVERT"}
        or any(role["goal"]["kind"] == "ELIMINATE" for role in roles.values())
    ):
        raise WireDefinitionError("schema 4 requires a v4 action or ELIMINATE")
    raw_pieces = mapping["initial_pieces"]
    if type(raw_pieces) is not list or len(raw_pieces) > board_size * board_size:
        raise WireDefinitionError("initial pieces must be a board-bounded array")
    pieces = []
    occupied = set()
    for value in raw_pieces:
        _keys(value, ("owner", "piece", "position"), "initial piece")
        position = _position(value["position"], 0, board_size - 1, "piece position")
        if tuple(position) in occupied:
            raise WireDefinitionError("initial pieces cannot share a position")
        occupied.add(tuple(position))
        pieces.append({
            "owner": _enum(value["owner"], ("A", "B"), "piece owner"),
            "piece": _piece(value["piece"]), "position": position,
        })
    pieces.sort(key=lambda piece: (piece["position"], piece["owner"], piece["piece"]))
    result = {
        "schema_version": version, "name": name.strip(), "board_size": board_size,
        "first_player": first_player, "max_plies": max_plies, "roles": roles,
        "initial_pieces": pieces,
    }
    if version == 2:
        policy = mapping["terminal_policy"]
        _keys(policy, ("no_legal_action",), "terminal policy")
        result["terminal_policy"] = {
            "no_legal_action": _enum(policy["no_legal_action"], ("DRAW",), "terminal policy")
        }
    return result


def definition_hash_v1(mapping):
    """The unchanged schema-v1--v4 exact DSL SHA-256, including name."""
    return hashlib.sha256(_canonical_bytes(normalize_definition_v1(mapping))).hexdigest()


def _transform_coordinate(row, column, maximum, index):
    return (
        (row, column), (column, maximum - row),
        (maximum - row, maximum - column), (maximum - column, row),
        (row, maximum - column), (maximum - row, column),
        (column, row), (maximum - column, maximum - row),
    )[index]


def _transformed(source, index, swap=False):
    value = json.loads(_canonical_bytes(source))
    # Derive edge transport from the same linear coordinate action.
    edge_vectors = ((-1, 0), (0, 1), (1, 0), (0, -1))
    edge_map = {
        edge: _EDGES[edge_vectors.index(_transform_coordinate(*vector, 0, index))]
        for edge, vector in zip(_EDGES, edge_vectors)
    }
    for role in value["roles"].values():
        action = role["action"]
        if action["kind"] != "PLACE":
            action["vectors"] = sorted(
                list(_transform_coordinate(*vector, 0, index))
                for vector in action["vectors"]
            )
        goal = role["goal"]
        if goal["kind"] == "CONNECT_EDGES":
            goal["edges"] = sorted(edge_map[edge] for edge in goal["edges"])
        elif goal["kind"] == "REACH_EDGE":
            goal["edge"] = edge_map[goal["edge"]]
    for piece in value["initial_pieces"]:
        piece["position"] = list(_transform_coordinate(
            *piece["position"], value["board_size"] - 1, index
        ))
        if swap:
            piece["owner"] = "B" if piece["owner"] == "A" else "A"
    value["initial_pieces"].sort(
        key=lambda piece: (piece["position"], piece["owner"], piece["piece"])
    )
    if swap:
        value["roles"] = {"A": value["roles"]["B"], "B": value["roles"]["A"]}
        value["first_player"] = "B" if value["first_player"] == "A" else "A"
    del value["name"]
    return value


def d4_definition_hash_v1(mapping):
    """The unchanged name-free spatial D4 identity of the exact wire."""
    source = normalize_definition_v1(mapping)
    representative = min(_canonical_bytes(_transformed(source, index)) for index in range(8))
    return hashlib.sha256(_D4_DOMAIN + representative).hexdigest()


def _alpha_normalize(value):
    # Piece labels are global kinds, not owner-local types. Preserve every
    # equality relation, including foreign-owned initial pieces and ELIMINATE
    # targets. Additional kinds are ordered by first canonical board occurrence.
    labels = {}
    fields = [value["roles"][owner][field] for field in ("action", "goal") for owner in ("A", "B")]
    fields.extend(value["initial_pieces"])
    for field in fields:
        label = field["piece"]
        if label not in labels:
            labels[label] = "k" + str(len(labels))
        field["piece"] = labels[label]
    return value


def role_neutral_definition_hash_v1(mapping):
    """Hash D4, complete role relabeling and global piece-kind alpha aliases.

    Alpha normalization is applied separately after each spatial/role image.
    Thus all kind equality relations survive while the compiler's a/b rename
    under complete role exchange creates no new mechanical identity.
    """
    source = normalize_definition_v1(mapping)
    representative = min(
        _canonical_bytes(_alpha_normalize(_transformed(source, index, swap)))
        for swap in (False, True) for index in range(8)
    )
    return hashlib.sha256(_NEUTRAL_DOMAIN + representative).hexdigest()


__all__ = (
    "WireDefinitionError", "normalize_definition_v1", "definition_hash_v1",
    "d4_definition_hash_v1", "role_neutral_definition_hash_v1",
)
