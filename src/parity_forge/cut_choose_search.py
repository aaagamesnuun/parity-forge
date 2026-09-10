"""Budgeted exact round-state search with a separately reconstructed proof check."""

import math
import time
from itertools import combinations

from .cut_choose import (
    State, apply_action, definition_hash, definition_to_dict, parse_definition,
    terminal, validate_state,
)


PROOF_FORMAT = "parity-forge:cut-choose-proof:v1"


class BudgetExceeded(ValueError):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def _limit(value, name):
    if type(value) is not int or value < 0:
        raise ValueError("invalid " + name)
    return value


def _deadline(seconds):
    if (type(seconds) not in (int, float) or not math.isfinite(seconds)
            or seconds <= 0):
        raise ValueError("invalid CPU seconds")
    return time.process_time() + seconds


def _clock(deadline):
    if time.process_time() >= deadline:
        raise BudgetExceeded("CPU_LIMIT")


def _key(secured, removed):
    return str(secured) + ":" + str(removed)


def _state(key, definition):
    if type(key) is not str or len(key) > 24:
        raise ValueError("invalid state key")
    parts = key.split(":")
    if len(parts) != 2 or any(not p.isascii() or not p.isdecimal() for p in parts):
        raise ValueError("invalid state key")
    secured, removed = map(int, parts)
    if _key(secured, removed) != key:
        raise ValueError("state key is not canonical")
    state = State(secured, removed)
    validate_state(definition, state)
    return state


def _offers(definition, state):
    return combinations((i for i in range(len(definition.edges))
                         if not (state.secured | state.removed) & (1 << i)), 2)


def _next(state, offer, keep):
    remove = offer[1] if keep == offer[0] else offer[0]
    return State(state.secured | (1 << keep), state.removed | (1 << remove))


def _independent_winner(definition, state):
    """Do not use the search/core's graph traversal or any claimed winner."""
    def has_path(mask):
        reached = set(definition.left)
        changed = True
        while changed:
            changed = False
            for i, (u, v) in enumerate(definition.edges):
                if mask & (1 << i) and ((u in reached) != (v in reached)):
                    reached.update((u, v))
                    changed = True
        return bool(reached.intersection(definition.right))
    if has_path(state.secured):
        return "B"
    if not has_path(((1 << len(definition.edges)) - 1) ^ state.removed):
        return "A"
    return None


def verify_proof(definition, proof, arc_limit=1000000, cpu_seconds=1800):
    """Check graph, terminality, universal replies and transitions from scratch."""
    _limit(arc_limit, "arc limit")
    deadline = _deadline(cpu_seconds)
    definition = parse_definition(definition_to_dict(definition))
    if (type(proof) is not dict or set(proof) !=
            {"format", "definition_hash", "root", "winner", "nodes"}):
        raise ValueError("invalid proof fields")
    if (proof["format"] != PROOF_FORMAT or proof["root"] != "0:0" or
            proof["definition_hash"] != definition_hash(definition) or
            type(proof["winner"]) is not str or proof["winner"] not in ("A", "B")):
        raise ValueError("invalid proof binding")
    nodes = proof["nodes"]
    if type(nodes) is not dict or not nodes:
        raise ValueError("invalid proof nodes")
    if len(nodes) > arc_limit + 1:
        raise BudgetExceeded("PROOF_ARC_LIMIT")
    pending, seen, arcs = [proof["root"]], set(), 0
    while pending:
        _clock(deadline)
        key = pending.pop()
        if key in seen:
            continue
        state = _state(key, definition)
        if key not in nodes:
            raise ValueError("missing proof node")
        node = nodes[key]
        if (type(node) is not dict or set(node) != {"winner", "replies"} or
                node["winner"] != proof["winner"] or type(node["winner"]) is not str or
                type(node["replies"]) is not list):
            raise ValueError("invalid node fields")
        seen.add(key)
        replies = node["replies"]
        actual = _independent_winner(definition, state)
        if actual is not None:
            if actual != node["winner"] or replies:
                raise ValueError("false terminal leaf or continuation after terminal")
            continue
        legal = set(_offers(definition, state))
        covered = {}
        for reply in replies:
            _clock(deadline)
            if arcs >= arc_limit:
                raise BudgetExceeded("PROOF_ARC_LIMIT")
            arcs += 1
            if (type(reply) is not dict or set(reply) != {"offer", "keep", "child"}
                    or type(reply["offer"]) is not list or len(reply["offer"]) != 2
                    or any(type(x) is not int for x in reply["offer"])
                    or type(reply["keep"]) is not int or type(reply["child"]) is not str):
                raise ValueError("invalid reply fields")
            offer, keep = tuple(reply["offer"]), reply["keep"]
            if offer not in legal or keep not in offer:
                raise ValueError("illegal proof reply")
            keeps = covered.setdefault(offer, set())
            if keep in keeps:
                raise ValueError("duplicate proof reply")
            keeps.add(keep)
            child = _next(state, offer, keep)
            staged = apply_action(definition, state, offer)
            if apply_action(definition, staged, (keep,)) != child:
                raise ValueError("core and independent transition differ")
            expected = _key(child.secured, child.removed)
            if reply["child"] != expected:
                raise ValueError("wrong successor")
            pending.append(expected)
        if node["winner"] == "A":
            if len(covered) != 1 or any(set(offer) != keeps
                                        for offer, keeps in covered.items()):
                raise ValueError("A proof needs both choices for one offer")
        elif set(covered) != legal or any(len(keeps) != 1 for keeps in covered.values()):
            raise ValueError("B proof must cover every offer once")
    if seen != set(nodes):
        raise ValueError("orphan proof nodes")
    return {"status": "PASS", "nodes": len(seen), "arcs": arcs,
            "winner": proof["winner"]}


def solve(definition, node_limit, transition_limit, proof_arc_limit=1000000,
          cpu_seconds=1800):
    """One exact DFS; UNKNOWN is an external stop, never a position value."""
    for value, name in ((node_limit, "node limit"), (transition_limit, "transition limit"),
                        (proof_arc_limit, "proof arc limit")):
        _limit(value, name)
    deadline = _deadline(cpu_seconds)
    definition = parse_definition(definition_to_dict(definition))
    cache = {}
    counts = {"nodes": 0, "transitions": 0, "proof_arcs": 0}
    retained_arcs = 0

    def reserve():
        nonlocal retained_arcs
        if retained_arcs >= proof_arc_limit:
            raise BudgetExceeded("PROOF_ARC_LIMIT")
        retained_arcs += 1
        counts["proof_arcs"] = max(counts["proof_arcs"], retained_arcs)

    def release(number):
        nonlocal retained_arcs
        retained_arcs -= number

    def save(state, winner, replies):
        cache[(state.secured, state.removed)] = (winner, replies)
        return winner

    def visit(state):
        _clock(deadline)
        key = (state.secured, state.removed)
        if key in cache:
            return cache[key][0]
        winner = terminal(definition, state)
        if winner is not None:
            return winner
        if counts["nodes"] >= node_limit:
            raise BudgetExceeded("NODE_LIMIT")
        counts["nodes"] += 1
        builder_replies = []
        for offer in _offers(definition, state):
            cutter_replies = []
            for keep in offer:
                _clock(deadline)
                if counts["transitions"] >= transition_limit:
                    raise BudgetExceeded("TRANSITION_LIMIT")
                counts["transitions"] += 1
                child = _next(state, offer, keep)
                child_winner = visit(child)
                reply = (offer, keep, child.secured, child.removed)
                if child_winner == "B":
                    release(len(cutter_replies))
                    reserve()
                    builder_replies.append(reply)
                    break
                reserve()
                cutter_replies.append(reply)
            else:
                release(len(builder_replies))
                return save(state, "A", tuple(cutter_replies))
        return save(state, "B", tuple(builder_replies))

    def certificate(winner):
        nodes, stack = {}, [State()]
        while stack:
            _clock(deadline)
            state = stack.pop()
            key = _key(state.secured, state.removed)
            if key in nodes:
                continue
            record = cache.get((state.secured, state.removed))
            if record is None:
                if terminal(definition, state) != winner:
                    raise ValueError("incomplete internal proof")
                nodes[key] = {"winner": winner, "replies": []}
                continue
            value, replies = record
            if value != winner:
                raise ValueError("inconsistent internal proof winner")
            nodes[key] = {"winner": winner, "replies": [
                {"offer": list(offer), "keep": keep, "child": _key(s, r)}
                for offer, keep, s, r in replies]}
            stack.extend(State(s, r) for _, _, s, r in replies)
        return {"format": PROOF_FORMAT, "definition_hash": definition_hash(definition),
                "root": "0:0", "winner": winner, "nodes": nodes}

    try:
        winner = visit(State())
        proof = certificate(winner)
        remaining = deadline - time.process_time()
        if remaining <= 0:
            raise BudgetExceeded("CPU_LIMIT")
        verify_proof(definition, proof, proof_arc_limit, remaining)
        _clock(deadline)
        return dict(status="COMPLETE", winner=winner, reason="PROVED", proof=proof, **counts)
    except BudgetExceeded as error:
        return dict(status="UNKNOWN", winner=None, reason=error.reason, proof=None, **counts)
