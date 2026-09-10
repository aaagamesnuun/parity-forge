"""Faithful fixed-role cut-and-choose edge rules; no search or tie policy."""

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from itertools import combinations


FORMAT = "parity-forge:cut-choose:v1"
TERMINAL_RULE = "SECURED_CONNECTS_ELSE_POTENTIAL_DISCONNECTED"
ROLES = {"A": "CUTTER", "B": "BUILDER"}
_KEYS = {"format", "id", "vertices", "edges", "left", "right", "roles",
         "terminal_rule"}


def _integer(value, label, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("invalid " + label)
    return value


@dataclass(frozen=True)
class Definition:
    id: str
    vertices: int
    edges: tuple
    left: tuple
    right: tuple

    def __post_init__(self):
        if type(self.id) is not str or not 1 <= len(self.id) <= 80:
            raise ValueError("invalid id")
        _integer(self.vertices, "vertices", 2, 32)
        if (type(self.edges) is not tuple or not self.edges or
                len(self.edges) > 32 or len(self.edges) % 2):
            raise ValueError("edges must be a nonempty even canonical tuple")
        for edge in self.edges:
            if type(edge) is not tuple or len(edge) != 2:
                raise ValueError("invalid edge")
            u, v = edge
            _integer(u, "edge endpoint", 0, self.vertices - 1)
            _integer(v, "edge endpoint", 0, self.vertices - 1)
            if u >= v:
                raise ValueError("edge endpoints must increase")
        if self.edges != tuple(sorted(set(self.edges))):
            raise ValueError("edges must be distinct and sorted")
        for boundary in (self.left, self.right):
            if type(boundary) is not tuple or not boundary:
                raise ValueError("boundary must be a nonempty canonical tuple")
            for vertex in boundary:
                _integer(vertex, "boundary vertex", 0, self.vertices - 1)
            if boundary != tuple(sorted(set(boundary))):
                raise ValueError("boundary must be distinct and sorted")
        if set(self.left) & set(self.right):
            raise ValueError("boundaries must be disjoint")


@dataclass(frozen=True)
class State:
    secured: int = 0
    removed: int = 0
    pending: tuple = ()


def _require_definition(definition):
    if not isinstance(definition, Definition):
        raise ValueError("expected Definition")


def parse_definition(mapping):
    if not isinstance(mapping, Mapping) or set(mapping) != _KEYS:
        raise ValueError("incorrect definition keys")
    if (mapping["format"] != FORMAT or
            mapping["terminal_rule"] != TERMINAL_RULE or
            not isinstance(mapping["roles"], Mapping) or
            dict(mapping["roles"]) != ROLES):
        raise ValueError("incorrect rule tags")
    vertices = _integer(mapping["vertices"], "vertices", 2, 32)
    raw_edges = mapping["edges"]
    if type(raw_edges) is not list or not raw_edges or len(raw_edges) > 32:
        raise ValueError("invalid edges list")
    edges = []
    for edge in raw_edges:
        if type(edge) is not list or len(edge) != 2:
            raise ValueError("invalid edge pair")
        u, v = (_integer(x, "edge endpoint", 0, vertices - 1) for x in edge)
        edges.append((min(u, v), max(u, v)))
    boundaries = []
    for name in ("left", "right"):
        boundary = mapping[name]
        if type(boundary) is not list or not boundary:
            raise ValueError("invalid boundary list")
        boundaries.append(tuple(sorted(
            _integer(x, "boundary vertex", 0, vertices - 1) for x in boundary)))
    return Definition(mapping["id"], vertices, tuple(sorted(edges)), *boundaries)


def definition_to_dict(definition):
    _require_definition(definition)
    return {"format": FORMAT, "id": definition.id,
            "vertices": definition.vertices,
            "edges": [list(edge) for edge in definition.edges],
            "left": list(definition.left), "right": list(definition.right),
            "roles": dict(ROLES), "terminal_rule": TERMINAL_RULE}


def definition_hash(definition):
    wire = definition_to_dict(definition)
    del wire["id"]
    canonical = json.dumps(wire, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(
        b"parity-forge:cut-choose-definition:v1\n" + canonical).hexdigest()


def original_definition():
    edges = []
    for row in range(4):
        for column in range(4):
            vertex = 4 * row + column
            if column < 3:
                edges.append((vertex, vertex + 1))
            if row < 3:
                edges.append((vertex, vertex + 4))
    return Definition("bridge-cut-choose-4x4-v1", 16, tuple(sorted(edges)),
                      (0, 4, 8, 12), (3, 7, 11, 15))


def initial_state(definition):
    _require_definition(definition)
    return State()


def connected(definition, edge_mask):
    _require_definition(definition)
    _integer(edge_mask, "edge mask", 0, (1 << len(definition.edges)) - 1)
    adjacency = [[] for _ in range(definition.vertices)]
    for index, (u, v) in enumerate(definition.edges):
        if edge_mask & (1 << index):
            adjacency[u].append(v)
            adjacency[v].append(u)
    seen = set(definition.left)
    frontier = list(definition.left)
    target = set(definition.right)
    while frontier:
        vertex = frontier.pop()
        if vertex in target:
            return True
        for neighbor in adjacency[vertex]:
            if neighbor not in seen:
                seen.add(neighbor)
                frontier.append(neighbor)
    return False


def _winner(definition, state):
    if connected(definition, state.secured):
        return "B"
    if not connected(definition,
                     ((1 << len(definition.edges)) - 1) ^ state.removed):
        return "A"
    return None


def validate_state(definition, state):
    _require_definition(definition)
    if not isinstance(state, State):
        raise ValueError("expected State")
    maximum = (1 << len(definition.edges)) - 1
    for mask in (state.secured, state.removed):
        _integer(mask, "state mask", 0, maximum)
    if (state.secured & state.removed or
            bin(state.secured).count("1") != bin(state.removed).count("1")):
        raise ValueError("resolved masks must be disjoint and equal size")
    if type(state.pending) is not tuple or len(state.pending) not in (0, 2):
        raise ValueError("pending must be empty or an increasing pair")
    if state.pending:
        for index in state.pending:
            _integer(index, "pending edge", 0, len(definition.edges) - 1)
            if (state.secured | state.removed) & (1 << index):
                raise ValueError("pending edge is already resolved")
        if state.pending[0] >= state.pending[1]:
            raise ValueError("pending edges must increase")
        if _winner(definition, state) is not None:
            raise ValueError("terminal state cannot have a pending offer")


def terminal(definition, state):
    validate_state(definition, state)
    return _winner(definition, state)


def legal_actions(definition, state):
    validate_state(definition, state)
    if _winner(definition, state) is not None:
        return ()
    if state.pending:
        return tuple((index,) for index in state.pending)
    unresolved = [i for i in range(len(definition.edges))
                  if not (state.secured | state.removed) & (1 << i)]
    return tuple(combinations(unresolved, 2))


def apply_action(definition, state, action):
    validate_state(definition, state)
    if _winner(definition, state) is not None:
        raise ValueError("cannot act after terminal")
    if type(action) is not tuple or any(type(x) is not int for x in action):
        raise ValueError("action must be an integer tuple")
    if state.pending:
        if len(action) != 1 or action[0] not in state.pending:
            raise ValueError("choice must select exactly one pending edge")
        keep = action[0]
        remove = state.pending[1] if keep == state.pending[0] else state.pending[0]
        result = State(state.secured | (1 << keep),
                       state.removed | (1 << remove))
    else:
        if (len(action) != 2 or not 0 <= action[0] < action[1] < len(definition.edges)
                or any((state.secured | state.removed) & (1 << i) for i in action)):
            raise ValueError("offer must be an unresolved increasing pair")
        result = State(state.secured, state.removed, action)
    validate_state(definition, result)
    return result


def replay(definition, actions):
    state = initial_state(definition)
    for action in actions:
        state = apply_action(definition, state, action)
    return state
