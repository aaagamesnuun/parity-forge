"""Exact cut-and-choose DFS with strict, independently checked cut-potential leaves.

Only the certificate method changes. Phi < 1 proves Builder can keep the cut
potential below one, excluding disconnection until finite decisive termination.
The original graph's legal edge set and the prior DFS/arc accounting are intact.
"""

from itertools import product
import time

from .cut_choose import (
    State, apply_action, definition_hash, definition_to_dict, parse_definition,
    terminal,
)
from .cut_choose_search import (
    BudgetExceeded, _clock, _deadline, _key, _limit, _next, _offers, _state,
)


PROOF_FORMAT = "parity-forge:cut-choose-potential-proof:v1"


def _interior(definition):
    boundary = set(definition.left) | set(definition.right)
    interior = tuple(v for v in range(definition.vertices) if v not in boundary)
    if len(interior) > 10:
        raise ValueError("cut certificate supports at most ten nonboundary vertices")
    return interior


def _minimal_cuts(definition, deadline):
    """Enumerate every boundary-compatible bipartition, then filter by subsets."""
    interior = _interior(definition)
    fixed = sum(1 << v for v in definition.left)
    candidates = set()
    for assignment in range(1 << len(interior)):
        _clock(deadline)
        side = fixed | sum(1 << v for j, v in enumerate(interior)
                           if assignment & (1 << j))
        cut = sum(1 << e for e, (u, v) in enumerate(definition.edges)
                  if bool(side & (1 << u)) != bool(side & (1 << v)))
        candidates.add(cut)
    minimal = []
    for cut in sorted(candidates, key=lambda mask: (bin(mask).count("1"), mask)):
        _clock(deadline)
        if not any(previous & cut == previous for previous in minimal):
            minimal.append(cut)
    return tuple(minimal)


def _potential(definition, state, cuts, deadline):
    """Integer numerator of Phi on the exact common denominator 2**edge_count."""
    width = len(definition.edges)
    unresolved = ((1 << width) - 1) ^ (state.secured | state.removed)
    numerator = 0
    for cut in cuts:
        _clock(deadline)
        if not cut & state.secured:
            numerator += 1 << (width - bin(cut & unresolved).count("1"))
    return numerator


def _checker_path(definition, mask, deadline):
    """Independent adjacency flood-fill, never the solver/core's connectivity."""
    _clock(deadline)
    adjacency = [[] for _ in range(definition.vertices)]
    for index, (u, v) in enumerate(definition.edges):
        if mask & (1 << index):
            adjacency[u].append(v)
            adjacency[v].append(u)
    reached = set(definition.left)
    frontier = list(reached)
    while frontier:
        vertex = frontier.pop()
        if vertex in definition.right:
            return True
        for neighbor in adjacency[vertex]:
            if neighbor not in reached:
                reached.add(neighbor)
                frontier.append(neighbor)
    return False


def _checker_cuts(definition, deadline):
    """Independent cut minimality: deletion disconnects; each one-edge restore connects."""
    interior = _interior(definition)
    all_edges = (1 << len(definition.edges)) - 1
    cuts = set()
    for choices in product((False, True), repeat=len(interior)):
        _clock(deadline)
        inside = set(definition.left)
        inside.update(v for v, selected in zip(interior, choices) if selected)
        removed = 0
        for index, (u, v) in enumerate(definition.edges):
            if (u in inside) != (v in inside):
                removed |= 1 << index
        if removed in cuts or _checker_path(definition, all_edges ^ removed, deadline):
            continue
        if all(_checker_path(definition, (all_edges ^ removed) | (1 << e), deadline)
               for e in range(len(definition.edges)) if removed & (1 << e)):
            cuts.add(removed)
    return tuple(sorted(cuts))


def _checker_potential(definition, state, cuts, deadline):
    total = 0
    width = len(definition.edges)
    for cut in cuts:
        _clock(deadline)
        if cut & state.secured:
            continue
        unresolved_count = sum(bool(cut & (1 << e)) and
                               not bool((state.secured | state.removed) & (1 << e))
                               for e in range(width))
        total += 2 ** (width - unresolved_count)
    return total < 2 ** width


def verify_proof(definition, proof, arc_limit=1000000, cpu_seconds=1800):
    """Verify cuts, strict potential, terminals and branch quantifiers independently."""
    _limit(arc_limit, "arc limit")
    deadline = _deadline(cpu_seconds)
    definition = parse_definition(definition_to_dict(definition))
    _interior(definition)
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
    pending, seen, arcs, leaves = [proof["root"]], set(), 0, 0
    cuts = None
    while pending:
        _clock(deadline)
        key = pending.pop()
        if key in seen:
            continue
        state = _state(key, definition)
        if key not in nodes:
            raise ValueError("missing proof node")
        node = nodes[key]
        if (type(node) is not dict or set(node) != {"winner", "kind", "replies"} or
                node["winner"] != proof["winner"] or type(node["winner"]) is not str or
                type(node["kind"]) is not str or
                node["kind"] not in ("TERMINAL", "CUT_POTENTIAL", "BRANCH") or
                type(node["replies"]) is not list):
            raise ValueError("invalid node fields")
        seen.add(key)
        replies = node["replies"]
        actual = None
        if _checker_path(definition, state.secured, deadline):
            actual = "B"
        elif not _checker_path(definition,
                               ((1 << len(definition.edges)) - 1) ^ state.removed, deadline):
            actual = "A"
        if actual is not None:
            if actual != node["winner"] or replies or node["kind"] != "TERMINAL":
                raise ValueError("false terminal leaf or continuation after terminal")
            continue
        if node["kind"] == "TERMINAL":
            raise ValueError("nonterminal state claimed terminal")
        if node["kind"] == "CUT_POTENTIAL":
            if node["winner"] != "B" or replies:
                raise ValueError("potential leaf must be B with no replies")
            if cuts is None:
                cuts = _checker_cuts(definition, deadline)
            if not _checker_potential(definition, state, cuts, deadline):
                raise ValueError("potential is not strictly below one")
            leaves += 1
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
    _clock(deadline)
    return {"status": "PASS", "nodes": len(seen), "arcs": arcs,
            "winner": proof["winner"], "potential_leaves": leaves}


def solve(definition, node_limit, transition_limit, proof_arc_limit=1000000,
          cpu_seconds=1800):
    """Prior lexical exact DFS with just one added, sufficient B leaf condition."""
    for value, name in ((node_limit, "node limit"), (transition_limit, "transition limit"),
                        (proof_arc_limit, "proof arc limit")):
        _limit(value, name)
    deadline = _deadline(cpu_seconds)
    definition = parse_definition(definition_to_dict(definition))
    _interior(definition)
    cache = {}
    counts = {"nodes": 0, "transitions": 0, "proof_arcs": 0,
              "cut_count": 0, "potential_checks": 0, "potential_leaves": 0}
    retained_arcs = 0
    cuts = ()

    def reserve():
        nonlocal retained_arcs
        if retained_arcs >= proof_arc_limit:
            raise BudgetExceeded("PROOF_ARC_LIMIT")
        retained_arcs += 1
        counts["proof_arcs"] = max(counts["proof_arcs"], retained_arcs)

    def release(number):
        nonlocal retained_arcs
        retained_arcs -= number

    def save(state, winner, kind, replies):
        cache[(state.secured, state.removed)] = (winner, kind, replies)
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
        counts["potential_checks"] += 1
        if _potential(definition, state, cuts, deadline) < (1 << len(definition.edges)):
            counts["potential_leaves"] += 1
            return save(state, "B", "CUT_POTENTIAL", ())
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
                return save(state, "A", "BRANCH", tuple(cutter_replies))
        return save(state, "B", "BRANCH", tuple(builder_replies))

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
                nodes[key] = {"winner": winner, "kind": "TERMINAL", "replies": []}
                continue
            value, kind, replies = record
            if value != winner:
                raise ValueError("inconsistent internal proof winner")
            nodes[key] = {"winner": winner, "kind": kind, "replies": [
                {"offer": list(offer), "keep": keep, "child": _key(s, r)}
                for offer, keep, s, r in replies]}
            stack.extend(State(s, r) for _, _, s, r in replies)
        return {"format": PROOF_FORMAT, "definition_hash": definition_hash(definition),
                "root": "0:0", "winner": winner, "nodes": nodes}

    try:
        cuts = _minimal_cuts(definition, deadline)
        counts["cut_count"] = len(cuts)
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
