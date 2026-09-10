"""Data-driven finite-space experiments; no model calls or implicit retries.

Run with python3 -m parity_forge.finite_space_batch --manifest FILE --output DIR.
The manifest pins definitions, policies, budgets and source *before* any game.
Output directories are exclusive. CPU/game limits never manufacture a winner.
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
from .finite_space import (
    action_from_dict, action_to_dict, apply_action, asymmetry_witness, definition_hash,
    describe_rules, free_cells, initial_state, parse_definition, replay,
    state_to_dict, termination_certificate,
)
from .finite_space_search import POLICIES, select_action, short_win


FORMAT = "parity-forge:finite-space-batch:v1"
REPOSITORY = Path(__file__).resolve().parents[2]
RUN_ROOT = REPOSITORY / "experiments" / "runs" / "finite-space-campaign-v1"
SOURCE_PATHS = tuple(
    "src/parity_forge/" + name + ".py" for name in
    ("__init__", "dsl", "engine", "finite_space", "finite_space_search", "finite_space_batch")
) + tuple("tests/test_" + name + ".py" for name in
          ("finite_space", "finite_space_search", "finite_space_batch"))


def source_hashes():
    return {path: hashlib.sha256((REPOSITORY / path).read_bytes()).hexdigest()
            for path in SOURCE_PATHS}


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


def load_json(path, max_bytes=2 * 1024 * 1024):
    if type(max_bytes) is not int or not 1 <= max_bytes <= 16 * 1024 * 1024:
        raise ValueError("invalid JSON byte limit")
    raw = Path(path).read_bytes()
    if len(raw) > max_bytes:
        raise ValueError("JSON exceeds its byte limit")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_object,
                      parse_constant=lambda value: (_ for _ in ()).throw(
                          ValueError("non-finite JSON number: " + value)))


def _keys(value, expected):
    if type(value) is not dict or set(value) != set(expected):
        raise ValueError("unexpected manifest keys; expected " + repr(tuple(expected)))


def _int(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("integer outside permitted resource range")


def validate_manifest(manifest):
    _keys(manifest, ("format", "run_id", "episode", "definitions", "definition_hashes", "origins",
                     "profiles", "search", "proof", "limits", "source_hashes"))
    if manifest["format"] != FORMAT:
        raise ValueError("wrong batch format")
    if (type(manifest["run_id"]) is not str or
            not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", manifest["run_id"])):
        raise ValueError("invalid run id")
    _int(manifest["episode"], 1, 3)
    definitions = manifest["definitions"]
    if type(definitions) is not list or not 1 <= len(definitions) <= 8:
        raise ValueError("this campaign batch needs 1..8 definitions")
    parsed = tuple(parse_definition(wire) for wire in definitions)
    families = [definition.roles[0].kind for definition in parsed]
    if any(definition.roles[0].kind != definition.roles[1].kind for definition in parsed):
        raise ValueError("this campaign registers only same-kind TILE or TRAIL skeletons")
    if any(families.count(kind) > 4 for kind in ("TILE", "TRAIL")):
        raise ValueError("at most four definitions per skeleton")
    origins = manifest["origins"]
    if type(origins) is not list or len(origins) != len(parsed):
        raise ValueError("one origin record is required for every definition")
    for origin, family in zip(origins, families):
        _keys(origin, ("family", "source", "change"))
        if origin["family"] != family or any(type(value) is not str or not 1 <= len(value) <= 2048
                                             for value in origin.values()):
            raise ValueError("invalid origin or variant description")
    hashes = [definition_hash(definition) for definition in parsed]
    if manifest["definition_hashes"] != hashes or len(set(hashes)) != len(hashes):
        raise ValueError("definition hashes mismatch or duplicate semantics")
    search = manifest["search"]
    _keys(search, ("max_nodes", "max_depth", "game_max_nodes"))
    _int(search["max_nodes"], 1, 100_000)
    _int(search["max_depth"], 1, 8)
    _int(search["game_max_nodes"], 1, 1_000_000)
    _keys(manifest["proof"], ("max_plies", "max_nodes"))
    _int(manifest["proof"]["max_plies"], 1, 16)
    _int(manifest["proof"]["max_nodes"], 1, 100_000)
    limits = manifest["limits"]
    _keys(limits, ("max_games", "cpu_seconds", "max_output_bytes"))
    _int(limits["max_games"], 1, 160)
    _int(limits["cpu_seconds"], 1, 14_400)
    _int(limits["max_output_bytes"], 1024, 16 * 1024 * 1024)
    profiles = manifest["profiles"]
    if type(profiles) is not list or not 1 <= len(profiles) <= 8:
        raise ValueError("need 1..8 profiles")
    seen_labels, seen_games, games_per_definition = set(), set(), 0
    for profile in profiles:
        _keys(profile, ("label", "A", "B", "seeds"))
        if (type(profile["label"]) is not str or not profile["label"] or
                profile["label"] in seen_labels):
            raise ValueError("profile labels must be unique and nonempty")
        seen_labels.add(profile["label"])
        if profile["A"] not in POLICIES or profile["B"] not in POLICIES:
            raise ValueError("unknown policy")
        seeds = profile["seeds"]
        if type(seeds) is not list or not 1 <= len(seeds) <= 16:
            raise ValueError("each profile needs 1..16 seeds")
        for seed in seeds:
            _int(seed, 0, 2**31 - 1)
            game_key = (profile["A"], profile["B"], seed)
            if game_key in seen_games:
                raise ValueError("duplicate deterministic game under a different label")
            seen_games.add(game_key)
        if len(set(seeds)) != len(seeds):
            raise ValueError("duplicate seed inside profile")
        games_per_definition += len(seeds)
    if games_per_definition > 8:
        raise ValueError("initial diagnostic is capped at eight games per definition")
    if games_per_definition * len(parsed) > limits["max_games"]:
        raise ValueError("schedule exceeds declared game budget")
    if manifest["source_hashes"] != source_hashes():
        raise ValueError("source pin mismatch; register before execution")
    return parsed


def play_game(definition, profile, seed, search, cpu_expired=lambda: False):
    state = initial_state(definition)
    initial_capacity = free_cells(definition, state)
    actions, decisions, used = [], [], 0
    rngs = {Player.A: random.Random(seed * 2), Player.B: random.Random(seed * 2 + 1)}
    status, reason = "COMPLETE", "NO_LEGAL_ACTION"
    while state.winner is None:
        if len(actions) >= initial_capacity:
            raise AssertionError("structural termination bound violated")
        policy = profile[state.to_move.value]
        remaining = search["game_max_nodes"] - used
        if cpu_expired() or (remaining <= 0 and policy != "random-v1"):
            status, reason = "UNKNOWN", "EXTERNAL_COMPUTE_LIMIT"
            break
        action, info = select_action(
            definition, state, policy, rngs[state.to_move],
            min(search["max_nodes"], remaining), search["max_depth"], cpu_expired)
        if cpu_expired():
            status, reason = "UNKNOWN", "EXTERNAL_COMPUTE_LIMIT"
            used += info["nodes"]
            decisions.append(dict(info, player=state.to_move.value, applied=False))
            break
        used += info["nodes"]
        decisions.append(dict(info, player=state.to_move.value, applied=True))
        actions.append(action_to_dict(definition, action))
        state = apply_action(definition, state, action)
    replayed = replay(definition, actions)
    if replayed != state:
        raise AssertionError("saved action replay differs from direct game")
    return {
        "profile": profile["label"], "A": profile["A"], "B": profile["B"],
        "seed": seed, "status": status, "reason": reason,
        "winner": state.winner.value if state.winner is not None else None,
        "plies": len(actions), "nodes": used, "actions": actions,
        "decisions": decisions, "final_state": state_to_dict(definition, state),
        "replay_transitions": len(actions),
    }


def evaluate(manifest, definitions, cpu_expired):
    results, slots = [], 0
    expected = sum(len(profile["seeds"]) for profile in manifest["profiles"])
    for definition in definitions:
        witness = asymmetry_witness(definition)
        row = {
            "id": definition.id, "definition_hash": definition_hash(definition),
            "termination": termination_certificate(definition),
            "asymmetry": witness, "rules_ja": list(describe_rules(definition)),
            "proofs": [], "games": [], "warnings": [],
            "human_review_eligible": False,
            "scheduled_games": expected,
        }
        if not witness["mechanically_asymmetric"]:
            row["disposition"] = "INSUFFICIENT_EVIDENCE"
            row["warnings"].append("MECHANICAL_ASYMMETRY_NOT_ESTABLISHED")
        elif initial_state(definition).winner is not None:
            row["disposition"] = "PROVED_DEFECT"
            row["warnings"].append("INITIAL_STATE_TERMINAL")
        else:
            for player in Player:
                if cpu_expired():
                    break
                row["proofs"].append(short_win(
                    definition, player, cpu_expired=cpu_expired, **manifest["proof"]))
            forced = any(proof["forced_win"] is True for proof in row["proofs"])
            if forced:
                row["disposition"] = "PROVED_DEFECT"
                row["warnings"].append("FORCED_WIN_WITHIN_DECLARED_HORIZON")
            else:
                for profile in manifest["profiles"]:
                    for seed in profile["seeds"]:
                        if cpu_expired():
                            break
                        row["games"].append(play_game(
                            definition, profile, seed, manifest["search"], cpu_expired))
                        slots += 1
                complete = [game for game in row["games"] if game["status"] == "COMPLETE"]
                row["wins"] = {role: sum(game["winner"] == role for game in complete)
                               for role in ("A", "B")}
                proof_complete = (len(row["proofs"]) == 2 and
                                  all(p["status"] == "COMPLETE" for p in row["proofs"]))
                row["disposition"] = (
                    "FURTHER_REVIEW" if proof_complete and len(complete) == expected
                    else "INSUFFICIENT_EVIDENCE")
                if complete and min(row["wins"].values()) == 0:
                    row["warnings"].append("OBSERVED_ONE_SIDED_SAMPLE_NOT_A_PROOF")
                if any(d["fallback"] for g in row["games"] for d in g["decisions"]):
                    row["warnings"].append("SOME_POLICY_DECISIONS_USED_RANDOM_FALLBACK")
        row["not_started_games"] = expected - len(row["games"])
        if row["not_started_games"]:
            row["not_started_reason"] = (
                "CPU_LIMIT" if cpu_expired() else row["warnings"][0])
        results.append(row)
    return {
        "format": FORMAT, "run_id": manifest["run_id"], "episode": manifest["episode"],
        "results": results, "game_count": slots, "human_review_eligible": False,
        "scheduled_games": expected * len(definitions),
        "not_started_games": expected * len(definitions) - slots,
        "claims": {"fairness": False, "depth": False, "fun": False},
    }


def _encoded(value, limit):
    encoded = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                          allow_nan=False) + "\n").encode("utf-8")
    if len(encoded) > limit:
        raise ValueError("output exceeds registered byte limit")
    return encoded


def _save(path, value, limit):
    encoded = _encoded(value, limit)
    with path.open("xb") as handle:
        handle.write(encoded)


def run_batch(manifest, output):
    definitions = validate_manifest(manifest)
    output = Path(output)
    expected = RUN_ROOT / manifest["run_id"]
    if output.resolve() != expected.resolve():
        raise ValueError("output must be the canonical campaign run_id directory")
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(str(output))
    episode = manifest["episode"]
    if episode > 1:
        previous = load_json(RUN_ROOT / ("episode-{}.json".format(episode - 1)))
        previous_dir = RUN_ROOT / previous["run_id"]
        runtime = load_json(previous_dir / "runtime.json")
        if (previous_dir / "failure.json").exists() or runtime["status"] != "COMPLETED":
            raise ValueError("previous episode failed technical completion")
        for filename, hash_key in (("results.json", "results_sha256"),
                                   ("registration.json", "manifest_sha256")):
            saved = load_json(previous_dir / filename, 16 * 1024 * 1024)
            digest = hashlib.sha256((previous_dir / filename).read_bytes()).hexdigest()
            if digest != runtime[hash_key] or saved["run_id"] != previous["run_id"]:
                raise ValueError("previous episode evidence changed")
        if previous["manifest_sha256"] != runtime["manifest_sha256"]:
            raise ValueError("previous episode claim and registration disagree")
    maximum = manifest["limits"]["max_output_bytes"]
    manifest_digest = hashlib.sha256(_encoded(manifest, maximum)).hexdigest()
    # Exclusive episode claim also blocks repeated IDs at another path and a
    # second run with a fresh ID in the same episode. Never remove failed claims.
    _save(RUN_ROOT / ("episode-{}.json".format(episode)),
          {"run_id": manifest["run_id"], "episode": episode,
           "manifest_sha256": manifest_digest}, 1024)
    output.mkdir(exist_ok=False)
    started = time.process_time()
    expired = lambda: time.process_time() - started >= manifest["limits"]["cpu_seconds"]
    try:
        _save(output / "registration.json", manifest, maximum)
        report = evaluate(manifest, definitions, expired)
        if source_hashes() != manifest["source_hashes"]:
            raise ValueError("source changed during execution")
        _save(output / "results.json", report, maximum)
        _save(output / "runtime.json", {
            "cpu_seconds": time.process_time() - started,
            "cpu_limit_reached": expired(), "status": "COMPLETED",
            "manifest_sha256": hashlib.sha256(
                (output / "registration.json").read_bytes()).hexdigest(),
            "results_sha256": hashlib.sha256((output / "results.json").read_bytes()).hexdigest(),
        }, maximum)
    except Exception as exc:
        _save(output / "failure.json", {
            "status": "FAILED_TECHNICAL", "error_type": type(exc).__name__,
            "message": str(exc), "cpu_seconds": time.process_time() - started,
        }, maximum)
        raise
    return report


def terminal_play(definition, human="A", seed=0, input_fn=input, output_fn=print):
    """Unscored local prototype; never automatic human evidence or a batch run."""
    if human not in ("A", "B", "both"):
        raise ValueError("human must be A, B or both")
    state, rng = initial_state(definition), random.Random(seed)
    output_fn("未認定の試作です。公平性・深さ・面白さは未確認です。")
    for line in describe_rules(definition):
        output_fn(line)
    output_fn("座標は0始まり。配置: r,c r,c ... / 移動: from_r,from_c to_r,to_c / q:終了")
    while True:
        output_fn("   " + " ".join(str(col) for col in range(definition.cols)))
        for row in range(definition.rows):
            cells = []
            for col in range(definition.cols):
                cell = row * definition.cols + col
                cells.append("A" if cell in state.a else "B" if cell in state.b
                             else "#" if state.closed & (1 << cell) else ".")
            output_fn(str(row) + "  " + " ".join(cells))
        if state.winner is not None:
            output_fn("勝者: " + state.winner.value)
            return state
        if human == "both" or state.to_move.value == human:
            raw = input_fn(state.to_move.value + "> ").strip()
            if raw.lower() == "q":
                return state
            try:
                points = [list(map(int, point.split(","))) for point in raw.split()]
                kind = definition.role(state.to_move).kind
                if kind == "TILE":
                    wire = {"kind": kind, "cells": sorted(points)}
                elif len(points) == 2:
                    wire = {"kind": kind, "from": points[0], "to": points[1]}
                else:
                    raise ValueError("移動には出発点と到着点が必要です")
                state = apply_action(definition, state, action_from_dict(definition, wire))
            except (ValueError, TypeError) as error:
                output_fn("入力できません: " + str(error))
        else:
            action, info = select_action(definition, state, "mobility-search-v1", rng, 512, 2)
            output_fn("AI " + state.to_move.value + ": " +
                      json.dumps(action_to_dict(definition, action)) +
                      " / 完了深さ=" + str(info["completed_depth"]))
            state = apply_action(definition, state, action)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--manifest", type=Path)
    mode.add_argument("--play-rule", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--human", choices=("A", "B", "both"), default="A")
    args = parser.parse_args()
    if args.play_rule:
        terminal_play(parse_definition(load_json(args.play_rule)), args.human)
        return
    if args.output is None:
        parser.error("--manifest requires --output")
    manifest = load_json(args.manifest)
    validate_manifest(manifest)
    # CLI worker only: OS CPU limit is a hard backstop around cooperative
    # checks. A killed worker has no accepted completion and is never retried.
    cpu_cap = manifest["limits"]["cpu_seconds"]
    _, hard = resource.getrlimit(resource.RLIMIT_CPU)
    if hard != resource.RLIM_INFINITY:
        cpu_cap = min(cpu_cap, hard)
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_cap, cpu_cap))
    result = run_batch(manifest, args.output)
    print(json.dumps({"run_id": result["run_id"], "game_count": result["game_count"],
                      "dispositions": [row["disposition"] for row in result["results"]]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
