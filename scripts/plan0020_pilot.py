"""One fixed, token-free Plan20 batch. Never resumes or overwrites a run."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import re
import subprocess
import time

from parity_forge.agents import RandomAgent, SearchBudgetExceeded
from parity_forge.dsl import Player, canonical_json, definition_hash, parse_definition
from parity_forge.engine import apply_action, initial_state, legal_actions, replay_dicts
from parity_forge.solver import SolveBudgetExceeded, solve_game
from parity_forge.terminal_search import TerminalOnlyMinimaxAgent
from scripts.plan0016_pilot import canonical_bytes, publish_json, read_json
from scripts.plan0020_candidates import build_candidates, certify_no_draw

PROTOCOL = "plan0020-directional-race-v1"
PLAN = "docs/plans/active/0020-existing-method-directional-race.md"
OUTPUT = "experiments/runs/" + PROTOCOL
CANDIDATE_COUNT = 6
PROFILES = ((0, 0), (2, 2), (3, 3), (3, 2), (2, 3))
SEEDS = tuple(range(4))
MAX_NODES, MAX_STATES = 20000, 100000
ACCEPTANCE = "PROVISIONAL_UNTIL_FULL_REGRESSION"


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _error(error):
    return {"type": type(error).__name__, "message": str(error)}


def _digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _publish(path, value):
    publish_json(path, value)
    if read_json(path) != value:
        raise ValueError("saved record readback differs")


def source_snapshot(repository, clean=False):
    def git(*args):
        return subprocess.check_output(("git", "-C", str(repository), *args), text=True).strip()
    if clean and git("status", "--porcelain"):
        raise ValueError("registered run requires globally clean Git")
    paths = sorted(p for p in git("ls-files").splitlines() if p.endswith(".py") or p == PLAN)
    if PLAN not in paths:
        raise ValueError("active plan must be committed")
    if any(p.endswith(".py") for p in git("ls-files", "--others", "--exclude-standard").splitlines()):
        raise ValueError("untracked Python source")
    return {"git_commit": git("rev-parse", "HEAD"), "plan": PLAN,
            "source_sha256": {p: hashlib.sha256((repository / p).read_bytes()).hexdigest() for p in paths}}


def make_manifest(rows, source):
    if len(rows) != CANDIDATE_COUNT:
        raise ValueError("wrong fixed candidate count")
    seen, games, exact = set(), [], []
    for index, row in enumerate(rows):
        raw = row["definition"]
        definition = parse_definition(raw)
        identity = definition_hash(definition)
        if json.loads(canonical_json(definition)) != raw or identity in seen:
            raise ValueError("noncanonical or duplicate definition")
        seen.add(identity)
        if (row["certificate"] != certify_no_draw(raw)
                or row["first_player"] != raw["first_player"] or raw["first_player"] != "B"):
            raise ValueError("candidate certificate or first player differs")
        base = {"candidate_index": index, "carrier_id": row["carrier_id"],
                "definition_hash": identity, "first_player": row["first_player"]}
        exact.append(dict(base, ordinal=len(exact), max_states=MAX_STATES))
        for pa, pb in PROFILES:
            for seed in SEEDS:
                games.append(dict(base, ordinal=len(games), policy_a=pa, policy_b=pb,
                                  seed=seed, max_nodes_per_role=MAX_NODES))
    return {"protocol_id": PROTOCOL, "acceptance": ACCEPTANCE, "source": source,
            "candidates": rows, "games": games, "exact": exact,
            "exposure": "DESIGNED_DEVELOPMENT_PILOT_NOT_CONFIRMATION"}


def play_one(raw, pa, pb, seed, max_nodes=MAX_NODES):
    """Record a fresh-agent game or censored/failed prefix; replay at most once."""
    if any(type(p) is not int or p not in (0, 2, 3) for p in (pa, pb)):
        raise ValueError("unsupported policy")
    if type(seed) is not int or type(max_nodes) is not int or max_nodes < 1:
        raise ValueError("invalid seed or node cap")
    record = {"status": "STARTED", "actions": [], "decisions": [], "winner": None,
              "terminal_reason": None, "plies": 0, "nodes_by_role": {"A": 0, "B": 0},
              "replay_count": 0, "error": None, "censor": None, "state_after_prefix": None}
    started, state, agents = time.monotonic(), None, {}
    try:
        before_raw = canonical_bytes(raw)
        definition = parse_definition(raw)
        agents = {r: RandomAgent() if p == 0 else TerminalOnlyMinimaxAgent(p, max_nodes)
                  for r, p in ((Player.A, pa), (Player.B, pb))}
        record.update(definition_hash=definition_hash(definition), first_player=definition.first_player.value,
                      policy_a=pa, policy_b=pb, seed=seed, max_nodes_per_role=max_nodes,
                      agents={r.value: a.identity.key for r, a in agents.items()})
        rng, state = random.Random(seed), initial_state(definition)
        while not state.terminal:
            choices, actor = legal_actions(definition, state), state.to_move
            if not choices:
                raise ValueError("nonterminal state has no legal actions")
            agent = agents[actor]
            before = getattr(agent, "total_nodes", 0)
            decision = {"ply": state.ply, "actor": actor.value, "legal_action_count": len(choices),
                        "nodes_before": before, "nodes_after": before, "selected_action": None,
                        "selection_status": "STARTED"}
            record["decisions"].append(decision)
            try:
                action = agent.select_action(definition, state, choices, rng)
                if action not in choices:
                    raise ValueError("illegal selected action")
                decision.update(selected_action=action.to_dict(), selection_status="SELECTED")
                successor = apply_action(definition, state, action)
            except SearchBudgetExceeded as error:
                decision["selection_status"] = "UNKNOWN_CENSORED"
                record.update(status="UNKNOWN_CENSORED", censor={"role": actor.value, "scope": error.scope,
                              "visited_nodes": error.visited_nodes, "max_nodes": error.max_nodes})
                break
            except Exception:
                decision["selection_status"] = "FAILED"
                raise
            finally:
                decision["nodes_after"] = getattr(agent, "total_nodes", 0)
                decision["charged_nodes"] = decision["nodes_after"] - before
            record["actions"].append(action.to_dict())
            state = successor
        if canonical_bytes(raw) != before_raw or definition_hash(definition) != record["definition_hash"]:
            raise ValueError("definition changed during game")
        if record["censor"] is not None:
            censor = record["censor"]
            if (any(type(censor[k]) is not int for k in ("max_nodes", "visited_nodes"))
                    or censor["max_nodes"] != max_nodes or censor["visited_nodes"] != max_nodes
                    or getattr(agents[Player(censor["role"])], "total_nodes", 0) != max_nodes):
                raise ValueError("invalid game censor counters")
        if any(type(getattr(a, "total_nodes", 0)) is not int or not 0 <= getattr(a, "total_nodes", 0) <= max_nodes
               for a in agents.values()):
            raise ValueError("invalid charged game nodes")
        if record["status"] == "STARTED":
            record["status"] = "COMPLETE"
    except Exception as error:
        record.update(status="FAILED", error=_error(error))
    if state is not None:
        try:
            record["replay_count"] += 1
            if replay_dicts(definition, record["actions"]) != state:
                raise ValueError("game prefix replay differs")
        except Exception as error:
            record.update(status="FAILED", replay_error=_error(error))
    record.update(plies=len(record["actions"]), elapsed_seconds=time.monotonic() - started,
                  nodes_by_role={r.value: getattr(a, "total_nodes", 0) for r, a in agents.items()})
    if state is not None:
        record["state_after_prefix"] = state.to_dict()
        if state.outcome is not None:
            record.update(winner=state.outcome.winner.value if state.outcome.winner else None,
                          terminal_reason=state.outcome.reason)
    return record


def exact_one(raw, max_states=MAX_STATES):
    if type(max_states) is not int or max_states < 1:
        raise ValueError("exact cap must be positive")
    record = {"status": "STARTED", "actual_result": None, "replay_count": 0, "error": None,
              "max_states": max_states, "definition_hash": None}
    started = time.monotonic()
    try:
        before = canonical_bytes(raw)
        definition = parse_definition(raw)
        record["definition_hash"] = definition_hash(definition)
        wire = solve_game(definition, max_states=max_states).to_dict()
        record["actual_result"] = wire
        if (type(wire["searched_states"]) is not int or not 1 <= wire["searched_states"] <= max_states
                or type(wire["cache_hits"]) is not int or wire["cache_hits"] < 0
                or type(wire["value_for_a"]) is not int or wire["value_for_a"] not in (-1, 0, 1)
                or type(wire["principal_variation_plies"]) is not int
                or wire["principal_variation_plies"] != len(wire["principal_variation"])):
            raise ValueError("invalid exact counters or value")
        value = wire["value_for_a"]
        if wire["forced_result"] != {-1: "B_WIN", 0: "DRAW", 1: "A_WIN"}[value]:
            raise ValueError("exact value/result disagree")
        record["replay_count"] += 1
        terminal = replay_dicts(definition, wire["principal_variation"])
        expected = {-1: Player.B, 0: None, 1: Player.A}[value]
        if (not terminal.terminal or terminal.ply != wire["principal_variation_plies"]
                or terminal.outcome.winner is not expected or terminal.outcome.reason != wire["terminal_reason"]):
            raise ValueError("exact PV replay disagrees")
        if canonical_bytes(raw) != before or canonical_json(definition) != before.decode():
            raise ValueError("definition changed during exact solve")
        record.update(status="COMPLETE", terminal_state=terminal.to_dict())
    except SolveBudgetExceeded as error:
        record.update(status="UNKNOWN_CENSORED", error={"type": type(error).__name__,
                      "searched_states": error.searched_states, "max_states": error.max_states})
        if (type(error.searched_states) is not int or type(error.max_states) is not int
                or error.searched_states != max_states or error.max_states != max_states):
            record.update(status="FAILED", error={"type": "ValueError", "message": "invalid exact censor counters"})
    except Exception as error:
        record.update(status="FAILED", error=_error(error))
    record["elapsed_seconds"] = time.monotonic() - started
    return record


def summarize(manifest, games, exact, failure=None):
    cells, candidates = [], []
    for index, row in enumerate(manifest["candidates"]):
        mine = [r for r in games if r["scheduled"]["candidate_index"] == index]
        candidate_cells = []
        for pa, pb in PROFILES:
            selected = [r["result"] for r in mine if (r["scheduled"]["policy_a"], r["scheduled"]["policy_b"]) == (pa, pb)]
            done = [r for r in selected if r["status"] == "COMPLETE"]
            cell = {"candidate_index": index, "first_player": row["first_player"], "profile": [pa, pb],
                    "planned": len(SEEDS), "attempted": len(selected), "not_started": len(SEEDS) - len(selected),
                    "statuses": dict(Counter(r["status"] for r in selected)), "completed": len(done),
                    "a_wins": sum(r["winner"] == "A" for r in done), "b_wins": sum(r["winner"] == "B" for r in done),
                    "draws": sum(r["winner"] is None for r in done), "completed_plies": [r["plies"] for r in done]}
            cells.append(cell)
            candidate_cells.append(cell)
        solved = next((r["result"]["status"] for r in exact if r["scheduled"]["candidate_index"] == index), "NOT_STARTED")
        full = all(c["completed"] == len(SEEDS) and not c["draws"] for c in candidate_cells)
        mixed = all(c["a_wins"] and c["b_wins"] for c in candidate_cells if c["profile"] in ([2, 2], [3, 3]))
        disposition = "TOO_EASILY_SOLVED" if solved == "COMPLETE" else "NO_FLAG"
        if failure is None and solved == "UNKNOWN_CENSORED" and full and mixed:
            disposition = "REVIEW_ONLY"
        candidates.append({"candidate_index": index, "first_player": row["first_player"],
                           "exact_status": solved, "disposition": disposition})
    return {"protocol_id": PROTOCOL, "acceptance": ACCEPTANCE, "execution_status": "FAILED" if failure else "COMPLETE",
            "games_planned": len(manifest["games"]), "games_attempted": len(games),
            "games_not_started": len(manifest["games"]) - len(games),
            "game_statuses": dict(Counter(r["result"]["status"] for r in games)),
            "exact_planned": len(manifest["exact"]), "exact_attempted": len(exact),
            "exact_not_started": len(manifest["exact"]) - len(exact),
            "exact_statuses": dict(Counter(r["result"]["status"] for r in exact)),
            "cells": cells, "candidates": candidates, "failure": failure,
            "fairness_established": False, "hardness_established": False, "fun_established": False}


def run_pilot(repository, registered_commit, output=None):
    repository = Path(repository)
    output = repository / OUTPUT if output is None else Path(output)
    if output.exists():
        raise FileExistsError("immutable run already exists; no retry or resume")
    if not isinstance(registered_commit, str) or not re.fullmatch("[0-9a-f]{40}", registered_commit):
        raise ValueError("a full registered commit is required")
    source = source_snapshot(repository, clean=True)
    if source["git_commit"] != registered_commit:
        raise ValueError("HEAD differs from registration")
    def check_source():
        if source_snapshot(repository) != source:
            raise ValueError("registered source or plan drift")
    output.mkdir(parents=True, exist_ok=False)
    for directory in ("games", "exact"):
        (output / directory).mkdir()
    _publish(output / "attempt.json", {"protocol_id": PROTOCOL, "source": source, "started_at": _utc()})
    manifest, rows, current, failure, games, exact = None, None, None, None, [], []
    try:
        rows = build_candidates()
        manifest = make_manifest(rows, source)
        check_source()
        _publish(output / "manifest.json", manifest)
        for kind, destination in (("games", games), ("exact", exact)):
            for scheduled in manifest[kind]:
                check_source()
                current = {"scheduled": scheduled, "result": None}
                stem = output / kind / "{:04d}".format(scheduled["ordinal"])
                _publish(stem.with_name(stem.name + "-attempt.json"),
                         {"scheduled": scheduled, "source_digest": _digest(source), "started_at": _utc()})
                row = rows[scheduled["candidate_index"]]
                try:
                    if kind == "games":
                        result = play_one(row["definition"], scheduled["policy_a"], scheduled["policy_b"], scheduled["seed"], MAX_NODES)
                    else:
                        result = exact_one(row["definition"], MAX_STATES)
                except Exception as error:
                    result = dict(scheduled, status="FAILED", error=_error(error), prefix_available=False)
                current["result"] = result
                try:
                    check_source()
                    bound = row["certificate"]["max_natural_plies"]
                    if result["definition_hash"] != scheduled["definition_hash"]:
                        raise ValueError("result belongs to another definition")
                    if kind == "games" and any(result[k] != scheduled[k] for k in
                            ("first_player", "policy_a", "policy_b", "seed", "max_nodes_per_role")):
                        raise ValueError("game condition differs from schedule")
                    if result["status"] in ("COMPLETE", "UNKNOWN_CENSORED"):
                        expected_replays = int(kind == "games" or result["status"] == "COMPLETE")
                        if result["replay_count"] != expected_replays:
                            raise ValueError("wrong replay count")
                    if result["status"] == "COMPLETE":
                        wire = result if kind == "games" else result["actual_result"]
                        plies = wire["plies"] if kind == "games" else wire["principal_variation_plies"]
                        decisive = wire["winner"] in ("A", "B") if kind == "games" else wire["value_for_a"] in (-1, 1)
                        if not decisive or plies > bound or wire["terminal_reason"] not in ("GOAL", "NO_LEGAL_ACTION"):
                            raise ValueError("PROOF_INTEGRITY_FAILURE")
                    elif result["status"] == "UNKNOWN_CENSORED" and kind == "games" and result["plies"] >= bound:
                        raise ValueError("nonterminal prefix reached natural bound")
                except Exception as error:
                    result["validation_error" if result["status"] == "FAILED" else "error"] = _error(error)
                    result["status"] = "FAILED"
                destination.append(current)
                try:
                    _publish(stem.with_name(stem.name + "-result.json"), current)
                except Exception as error:
                    result.update(status_before_publication=result["status"], status="FAILED",
                                  publication_error=_error(error))
                    raise
                current = None
                if result["status"] not in ("COMPLETE", "UNKNOWN_CENSORED"):
                    raise ValueError("fixed schedule stopped on failed record")
        check_source()
        _publish(output / "source-verification.json", {"source": source, "matched_after_execution": True})
    except Exception as error:
        failure = dict(_error(error), current=current, candidate_prefix=rows if manifest is None else None)
        _publish(output / "failure.json", failure)
    summary = summarize(manifest, games, exact, failure) if manifest else {
        "protocol_id": PROTOCOL, "execution_status": "FAILED", "failure": failure, "acceptance": ACCEPTANCE}
    _publish(output / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run",))
    parser.add_argument("--registered-commit", required=True)
    args = parser.parse_args()
    summary = run_pilot(Path(__file__).resolve().parents[1], args.registered_commit)
    print(json.dumps({k: v for k, v in summary.items() if k != "cells"}, sort_keys=True))
    return int(summary["execution_status"] == "FAILED")


if __name__ == "__main__":
    raise SystemExit(main())
