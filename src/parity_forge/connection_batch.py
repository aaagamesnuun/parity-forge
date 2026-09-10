"""One sealed Plan40 diagnostic; immutable outputs and no implicit retry.

The production CLI accepts only the fixed registered cohort. Tests inject small
synthetic traces/mocks, never play or claim the production cohort.
"""

import argparse
import hashlib
import json
from pathlib import Path
import random
import re
import resource
import time

from .dsl import Player
from .connection import (
    action_to_dict, apply_action, definition_hash, describe_rules, initial_state,
    parse_definition, state_to_dict, termination_certificate,
)
from .connection_search import select_action


REPOSITORY = Path(__file__).resolve().parents[2]
REGISTRATION_PATH = "experiments/proposals/plan0040-connection-baseline-v0.json"
REGISTRATION_SHA256 = "c9ba6db6b00425d014a2a695f46d1552e5d8969c78a626fa27a2d14b34d6d060"
CONTRACT_PATH = "docs/designs/connection-v1.md"
CONTRACT_SHA256 = "a481b1223a181a1a46305802099a087476a6c0623898253829ee6b70f991d73a"
OLD_PINS = "experiments/reports/plan0037-acceptance-evidence/python-source-pins.sha256"
OLD_PINS_SHA256 = "4e96b0de43cd7a309e4f7b3016ac731fc69c7c78bf94b2bf4d6650ecb5036573"
ACCEPTANCE_PATH = "experiments/reports/0040-full-suite-exit-receipt.json"
EVIDENCE_ROOT = "experiments/reports/plan0040-acceptance-evidence"
SEALED_PATH = "experiments/proposals/plan0040-connection-baseline-sealed-v0.json"
SOURCE_PATHS = tuple("src/parity_forge/" + name + ".py" for name in
                     ("connection", "connection_search", "connection_batch")) + tuple(
    "tests/test_" + name + ".py" for name in
    ("connection", "connection_search", "connection_batch"))
FORMAT = "parity-forge:connection-sealed-run:v1"
FULL_COMMAND = "PYTHONPATH=src python3 -m unittest discover -s tests -v"
QUALITY = dict(fairness=False, depth=False, fun=False, human_review_eligible=False)


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _encoded(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode("ascii")


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


def load_json(path, max_bytes=16 * 1024 * 1024):
    if type(max_bytes) is not int or not 0 < max_bytes <= 16 * 1024 * 1024:
        raise ValueError("invalid JSON limit")
    with Path(path).open("rb") as handle:
        raw = handle.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ValueError("JSON byte limit exceeded")
    def reject_constant(value):
        raise ValueError("non-finite JSON number: " + value)
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_object,
                      parse_constant=reject_constant)


def _path(relative):
    relative = Path(relative)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("repository-relative path required")
    path = REPOSITORY.resolve() / relative
    # Reject symlink aliases, including existing parent components.
    if path.resolve() != path.absolute():
        raise ValueError("symlink/alias path is not allowed")
    return path


def source_hashes():
    return {path: _digest(_path(path).read_bytes()) for path in SOURCE_PATHS}


def verify_old_pins():
    raw = _path(OLD_PINS).read_bytes()
    if _digest(raw) != OLD_PINS_SHA256:
        raise ValueError("old source pin inventory changed")
    lines = raw.decode("ascii").splitlines()
    seen = set()
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if not match or match[2] in seen:
            raise ValueError("malformed/duplicate old pin")
        seen.add(match[2])
        if _digest(_path(match[2]).read_bytes()) != match[1]:
            raise ValueError("old source changed: " + match[2])
    if len(seen) != 206:
        raise ValueError("expected all 206 old source pins")


def registered_input():
    raw = _path(REGISTRATION_PATH).read_bytes()
    if _digest(raw) != REGISTRATION_SHA256:
        raise ValueError("prospective registration bytes changed")
    if _digest(_path(CONTRACT_PATH).read_bytes()) != CONTRACT_SHA256:
        raise ValueError("implementation contract changed")
    registration = load_json(_path(REGISTRATION_PATH))
    source = registration["design_source"]
    if _digest(_path(source["path"]).read_bytes()) != source["sha256"]:
        raise ValueError("selected design source changed")
    return registration


def validate_registration(registration):
    # Byte-pinned complete input also fixes all schedule, policy and budget fields;
    # JSON encoding comparison distinguishes bool from int (unlike dict equality).
    if _encoded(registration) != _encoded(registered_input()):
        raise ValueError("only the exact prospective registration is admitted")
    definitions = tuple(parse_definition(value) for value in registration["definitions"])
    if [definition_hash(d) for d in definitions] != registration["definition_hashes"]:
        raise ValueError("semantic definition hashes disagree")
    return definitions


def validate_acceptance(source_pins):
    receipt = load_json(_path(ACCEPTANCE_PATH))
    required = {"kind": "observed_full_regression_completion", "plan": "0040",
                "command": FULL_COMMAND, "actual_session_exit_code": 0,
                "source_hashes": source_pins, "source_changed_after_freeze": False,
                "old_source_pin_file_sha256": OLD_PINS_SHA256,
                "independent_source_review": "PASS", "focused_tests": "PASS"}
    for key, value in required.items():
        if key not in receipt or _encoded(receipt[key]) != _encoded(value):
            raise ValueError("unaccepted full regression: " + key)
    if (type(receipt.get("tests_run")) is not int or receipt["tests_run"] < 1 or
            type(receipt.get("actual_session_completion_chunk")) is not str or
            not receipt["actual_session_completion_chunk"]):
        raise ValueError("missing actual regression completion evidence")
    for field, suffix in (("log", "full-suite.log"), ("exit_file", "full-suite.exit")):
        if receipt.get(field) != EVIDENCE_ROOT + "/" + suffix:
            raise ValueError("unexpected regression evidence path")
        raw = _path(receipt[field]).read_bytes()
        if _digest(raw) != receipt.get(field + "_sha256"):
            raise ValueError("regression evidence hash mismatch")
        if field == "exit_file" and raw.strip() != b"0":
            raise ValueError("regression process did not exit successfully")
        if field == "log":
            log = raw.decode("utf-8")
            summary = receipt.get("summary", "")
            if not re.fullmatch(r"OK(?: \(skipped=\d+\))?", summary):
                raise ValueError("full suite is not OK")
            if (not re.search(r"^Ran " + str(receipt["tests_run"]) + r" tests? in [\d.]+s$",
                              log, re.MULTILINE) or summary not in log.splitlines()):
                raise ValueError("regression summary disagrees with log")
    return _digest(_path(ACCEPTANCE_PATH).read_bytes())


def validate_manifest(manifest):
    if type(manifest) is not dict or set(manifest) != {
            "format", "registration_sha256", "registration", "source_hashes",
            "acceptance_path", "acceptance_sha256"}:
        raise ValueError("invalid sealed manifest structure")
    if (manifest["format"] != FORMAT or
            manifest["registration_sha256"] != REGISTRATION_SHA256 or
            manifest["acceptance_path"] != ACCEPTANCE_PATH):
        raise ValueError("sealed input identity mismatch")
    definitions = validate_registration(manifest["registration"])
    pins = source_hashes()
    if manifest["source_hashes"] != pins:
        raise ValueError("six source pins changed")
    verify_old_pins()
    if manifest["acceptance_sha256"] != validate_acceptance(pins):
        raise ValueError("full regression acceptance changed")
    return definitions


def seal_manifest():
    """Create the one executable manifest only after observed suite acceptance."""
    registration = registered_input()
    pins = source_hashes()
    manifest = {"format": FORMAT, "registration_sha256": REGISTRATION_SHA256,
                "registration": registration, "source_hashes": pins,
                "acceptance_path": ACCEPTANCE_PATH,
                "acceptance_sha256": validate_acceptance(pins)}
    validate_manifest(manifest)
    with _path(SEALED_PATH).open("xb") as handle:
        handle.write(_encoded(manifest))
    return manifest


class ReplayInterrupted(Exception):
    def __init__(self, transitions):
        super().__init__("reference CPU limit")
        self.transitions = transitions


def reference_replay(definition, game, cpu_expired=lambda: False):
    """Independent coordinate-set transition/goal implementation, every prefix."""
    n = definition.size
    stones = {"A": set(), "B": set()}
    bridge, convert = definition.bridge_credits_A, definition.conversion_credits_B
    turn, winner, plies = definition.first_player.value, None, 0

    def adjacent(x, y):
        dr, dc = y[0] - x[0], y[1] - x[1]
        return ((dr == 0 and abs(dc) == 1) or (dr == 1 and dc in (-1, 0)) or
                (dr == -1 and dc in (0, 1)))

    def snapshot():
        return {"a": [list(c) for c in sorted(stones["A"])],
                "b": [list(c) for c in sorted(stones["B"])],
                "bridge_left": bridge, "conversion_left": convert,
                "to_move": turn, "plies": plies, "winner": winner}

    def connected(role):
        axis = 1 if role == "A" else 0
        reached = {c for c in stones[role] if c[axis] == 0}
        pending = list(reached)
        while pending:
            if cpu_expired():
                raise ReplayInterrupted(plies)
            current = pending.pop()
            if current[axis] == n - 1:
                return True
            for cell in stones[role] - reached:
                if adjacent(current, cell):
                    reached.add(cell)
                    pending.append(cell)
        return False

    states, actions = game["states"], game["actions"]
    if len(states) != len(actions) + 1 or _encoded(states[0]) != _encoded(snapshot()):
        raise ValueError("reference initial snapshot/count mismatch")
    for index, action in enumerate(actions):
        if cpu_expired():
            raise ReplayInterrupted(plies)
        if winner is not None:
            raise ValueError("reference rejects post-terminal action")
        if type(action) is not dict or set(action) != {"kind", "cells"}:
            raise ValueError("reference action fields")
        cells = action["cells"]
        if type(cells) is not list:
            raise ValueError("reference coordinates must be arrays")
        for cell in cells:
            if (type(cell) is not list or len(cell) != 2 or
                    any(type(v) is not int or not 0 <= v < n for v in cell)):
                raise ValueError("reference coordinate outside board")
        cells = tuple(tuple(c) for c in cells)
        occupied = stones["A"] | stones["B"]
        kind = action["kind"]
        if kind == "PLACE_ONE":
            if len(cells) != 1 or cells[0] in occupied:
                raise ValueError("reference illegal single placement")
            stones[turn].add(cells[0])
        elif kind == "BRIDGE_PAIR":
            if (turn != "A" or bridge <= 0 or len(cells) != 2 or cells[0] >= cells[1]
                    or not adjacent(*cells) or any(c in occupied for c in cells)):
                raise ValueError("reference illegal bridge")
            stones["A"].update(cells)
            bridge -= 1
        elif kind == "PLACE_AND_CONVERT":
            if (turn != "B" or convert <= 0 or len(cells) != 2 or
                    cells[0] in occupied or cells[1] not in stones["A"] or
                    not adjacent(*cells)):
                raise ValueError("reference illegal conversion")
            stones["B"].update(cells)
            stones["A"].remove(cells[1])
            convert -= 1
        else:
            raise ValueError("reference unknown action kind")
        plies += 1
        winners = [role for role in ("A", "B") if connected(role)]
        if len(winners) > 1 or (not winners and len(stones["A"] | stones["B"]) == n*n):
            raise ValueError("reference invalid connection ending")
        winner = winners[0] if winners else None
        if winner is None:
            turn = "B" if turn == "A" else "A"
        if _encoded(states[index + 1]) != _encoded(snapshot()):
            raise ValueError("reference prefix snapshot mismatch at " + str(index + 1))
    if (_encoded(game["final_state"]) != _encoded(snapshot()) or
            type(game["plies"]) is not int or game["plies"] != plies or
            game["winner"] != winner or winner is None):
        raise ValueError("reference completed trace has wrong/missing ending")
    return plies


def _game_identity(definition, profile, seed):
    return {"definition_id": definition.id, "definition_hash": definition_hash(definition),
            "first_player": definition.first_player.value, "profile": profile["label"],
            "A": profile["A"], "B": profile["B"], "seed": seed}


def play_game(definition, profile, seed, search, cpu_expired=lambda: False):
    state = initial_state(definition)
    game = dict(_game_identity(definition, profile, seed), status="UNKNOWN", reason=None,
                actions=[], decisions=[], states=[state_to_dict(definition, state)],
                search_transitions=0, actual_applied_game_actions=0,
                reference_replay_transitions=0, reference_replay="NOT_STARTED")
    rngs = {Player.A: random.Random(2*seed), Player.B: random.Random(2*seed + 1)}
    try:
        while state.winner is None:
            remaining = search["max_search_transitions_per_game"] - game["search_transitions"]
            if cpu_expired() or remaining <= 0:
                game["reason"] = "CPU_LIMIT" if cpu_expired() else "GAME_TRANSITION_LIMIT"
                break
            if state.plies >= definition.size ** 2:
                raise ValueError("all-play termination bound violated")
            policy = profile[state.to_move.value]
            decision_limit = min(search["max_transitions_per_decision"], remaining)
            selected = select_action(definition, state, policy, rngs[state.to_move],
                                     decision_limit,
                                     search["max_depth"], cpu_expired)
            if (type(selected.search_transitions) is not int or
                    not 0 <= selected.search_transitions <= decision_limit):
                raise ValueError("policy violated speculative transition budget")
            game["search_transitions"] += selected.search_transitions
            decision = {"player": state.to_move.value, "policy": policy,
                        "action": action_to_dict(definition, selected.action)
                        if selected.action is not None else None,
                        "completed_depth": selected.completed_depth,
                        "search_transitions": selected.search_transitions,
                        "budget_exhausted": selected.budget_exhausted,
                        "fallback": selected.fallback, "cpu_expired": selected.cpu_expired,
                        "applied": False}
            game["decisions"].append(decision)
            if selected.cpu_expired or cpu_expired():
                game["reason"] = "CPU_LIMIT"
                break
            if selected.action is None:
                raise ValueError("nonterminal policy returned no action")
            state = apply_action(definition, state, selected.action)
            decision["applied"] = True
            game["actions"].append(decision["action"])
            game["states"].append(state_to_dict(definition, state))
            game["actual_applied_game_actions"] += 1
        game.update(final_state=state_to_dict(definition, state), plies=state.plies,
                    winner=state.winner.value if state.winner else None,
                    credit_usage={"A": definition.bridge_credits_A - state.bridge_left,
                                  "B": definition.conversion_credits_B - state.conversion_left})
        if state.winner is not None:
            try:
                game["reference_replay"] = "RUNNING"
                game["reference_replay_transitions"] = None
                game["reference_replay_transitions"] = reference_replay(definition, game, cpu_expired)
                game.update(status="COMPLETE", reason="OPPOSITE_EDGE_CONNECTION",
                            reference_replay="PASS")
            except ReplayInterrupted as exc:
                game.update(status="UNKNOWN", reason="REFERENCE_CPU_LIMIT", winner=None,
                            reference_replay="INTERRUPTED",
                            reference_replay_transitions=exc.transitions)
    except Exception as exc:
        game.update(status="FAILED_TECHNICAL", reason=type(exc).__name__ + ": " + str(exc),
                    final_state=state_to_dict(definition, state), plies=state.plies, winner=None,
                    credit_usage={"A": definition.bridge_credits_A - state.bridge_left,
                                  "B": definition.conversion_credits_B - state.conversion_left})
        if game["reference_replay"] == "RUNNING":
            game["reference_replay"] = "FAILED_TECHNICAL"
    return game


def scheduled_games(registration, definitions):
    for profile in registration["profiles"]:
        for seed in profile["seeds"]:
            for definition in definitions:
                yield definition, profile, seed


def evaluate(registration, definitions, cpu_expired, save_game=lambda index, game: None):
    games, stopped = [], False
    for index, (definition, profile, seed) in enumerate(scheduled_games(registration, definitions)):
        if stopped or cpu_expired():
            game = dict(_game_identity(definition, profile, seed), status="NOT_STARTED",
                        reason="BATCH_STOPPED", winner=None)
        else:
            game = play_game(definition, profile, seed, registration["search"], cpu_expired)
            stopped = game["status"] == "FAILED_TECHNICAL"
        games.append(game)
        save_game(index, game)
    rows = []
    for definition in definitions:
        subset = [g for g in games if g["definition_id"] == definition.id]
        completed = [g for g in subset if g["status"] == "COMPLETE"]
        rows.append({"definition_id": definition.id, "first_player": definition.first_player.value,
                     "definition_hash": definition_hash(definition),
                     "role_wins": {p: sum(g["winner"] == p for g in completed) for p in ("A", "B")},
                     "first_player_wins": sum(g["winner"] == definition.first_player.value for g in completed),
                     "status_counts": {s: sum(g["status"] == s for g in subset) for s in
                                       ("COMPLETE", "UNKNOWN", "NOT_STARTED", "FAILED_TECHNICAL")},
                     "rules": describe_rules(definition),
                     "termination": termination_certificate(definition)})
    return {"registration_id": registration["registration_id"], "games": games,
            "per_definition": rows, "quality_flags": dict(QUALITY)}


class OutputBudget:
    def __init__(self, maximum):
        self.maximum, self.used = maximum, 0

    def save(self, path, value, reserve=0):
        raw = _encoded(value)
        if self.used + len(raw) + reserve > self.maximum:
            raise ValueError("cumulative raw-output ceiling exceeded")
        with Path(path).open("xb") as handle:
            # Reserve before writing: even a partial I/O failure may have emitted bytes.
            self.used += len(raw)
            handle.write(raw)


def _install_cpu_limit(limit):
    _, hard = resource.getrlimit(resource.RLIMIT_CPU)
    if hard != resource.RLIM_INFINITY and hard < limit:
        raise ValueError("inherited CPU hard limit is below the registered budget")
    ceiling = int(limit)
    if time.process_time() >= ceiling:
        raise ValueError("worker CPU budget already exhausted")
    resource.setrlimit(resource.RLIMIT_CPU, (ceiling, ceiling))


def run_batch(manifest):
    registration = manifest["registration"]
    # Absolute process CPU covers imports, validation, generation and finalization;
    # cooperative one-second reserve allows saving UNKNOWN before the hard cap.
    _install_cpu_limit(14400)
    definitions = validate_manifest(manifest)
    ceiling = registration["limits"]["cpu_seconds"]
    expired = lambda: time.process_time() >= ceiling - 1
    if expired():
        raise ValueError("no worker CPU budget before claim")
    root = _path(registration["execution"]["run_root"])
    claim = _path(registration["execution"]["claim"])
    output = _path(registration["execution"]["output"])
    if output.exists() or output.is_symlink() or claim.exists() or claim.is_symlink():
        raise FileExistsError("one-shot claim/output already exists; no retry")
    root.mkdir(parents=True, exist_ok=True)
    budget = OutputBudget(registration["limits"]["max_output_bytes"])
    manifest_digest = _digest(_encoded(manifest))
    budget.save(claim, {"run_id": registration["execution"]["run_id"],
                        "manifest_sha256": manifest_digest}, reserve=8192)
    owns_output = False
    try:
        output.mkdir(exist_ok=False)
        owns_output = True
        budget.save(output / "registration.json", manifest, reserve=8192)
        def save_game(index, game):
            budget.save(output / "game-{:02d}.json".format(index + 1), game, reserve=8192)
        report = evaluate(registration, definitions, expired, save_game)
        validate_manifest(manifest)
        budget.save(output / "results.json", report, reserve=8192)
        if any(g["status"] == "FAILED_TECHNICAL" for g in report["games"]):
            raise ValueError("one or more games failed technical validation")
        runtime = {"status": "COMPLETED", "cpu_seconds": time.process_time(),
                   "cpu_limit_reached": expired(), "manifest_sha256": manifest_digest,
                   "results_sha256": _digest((output / "results.json").read_bytes()),
                   "raw_bytes_before_runtime": budget.used,
                   "process_exit_observed": False}
        budget.save(output / "runtime.json", runtime)
    except Exception as exc:
        # An output-dir race must not write into another owner's directory.
        failure_path = output / "failure.json" if owns_output else root / "batch-1-failure.json"
        budget.save(failure_path, {"status": "FAILED_TECHNICAL", "error_type": type(exc).__name__,
                                  "message": str(exc)[:1024], "cpu_seconds": time.process_time()})
        raise
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seal", action="store_true", help="seal after observed full-suite acceptance")
    args = parser.parse_args()
    if args.seal:
        seal_manifest()
    else:
        run_batch(load_json(_path(SEALED_PATH)))


if __name__ == "__main__":
    main()
