"""One preregistered candidate, fixed finite cascade, and no retries."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess

from parity_forge.dsl import canonical_json, definition_hash, parse_definition
from parity_forge.play import _wilson_interval
from scripts import plan0024_play as play_adapter
from scripts.plan0020_pilot import exact_one, _publish, _utc


PLAN = "docs/plans/active/0024-two-orthogonal-hunters-screen.md"
DATA = (
    "experiments/proposals/"
    "three-runners-two-orthogonal-hunters-v0.json"
)
PROTOCOL = "plan0024-two-orthogonal-hunters-v1"
HASH = "ba966ffe27f3a9ceeccba083ecc23cfb25cb4ade831c206392eacd7de4219b76"
MAX_NODES = MAX_STATES = 100000
BOUND = 23
PLY_LIMIT = 25
CELLS = (
    ("base", "T4", "T4", 300, 16),
    ("base", "T3", "T3", 300, 16),
    ("confirm", "T4", "T4", 400, 16),
    ("sensitivity", "T4", "T2", 400, 8),
    ("sensitivity", "T2", "T4", 400, 8),
    ("simple", "T4", "R", 400, 8),
    ("simple", "R", "T4", 400, 8),
)
PLANNED_GAMES = sum(cell[4] for cell in CELLS)
PLANNED_ATTEMPTS = PLANNED_GAMES + 1


def source_snapshot(repository, clean=False):
    """Pin every tracked Python file together with the active plan and wire."""

    repository = Path(repository)

    def git(*args):
        return subprocess.check_output(
            ("git", "-C", str(repository), *args), text=True
        ).strip()

    if clean and git("status", "--porcelain"):
        raise ValueError("clean registered worktree required")
    tracked = git("ls-files").splitlines()
    paths = sorted(
        path
        for path in tracked
        if path.endswith(".py") or path in (PLAN, DATA)
    )
    if not {PLAN, DATA}.issubset(paths):
        raise ValueError("active plan and proposal must be registered")
    if any(
        path.endswith(".py")
        for path in git(
            "ls-files", "--others", "--exclude-standard"
        ).splitlines()
    ):
        raise ValueError("untracked Python source")
    return {
        "git_commit": git("rev-parse", "HEAD"),
        "sha256": {
            path: hashlib.sha256((repository / path).read_bytes()).hexdigest()
            for path in paths
        },
    }


def load_definition(repository):
    """Read and statically validate the one fixed canonical wire."""

    payload = json.loads((Path(repository) / DATA).read_text())
    rows = payload["definitions"]
    if type(rows) is not list or len(rows) != 1:
        raise ValueError("exactly one fixed definition required")
    raw = rows[0]
    definition = parse_definition(raw)
    if (
        definition_hash(definition) != HASH
        or json.loads(canonical_json(definition)) != raw
        or raw["first_player"] != "A"
        or raw["max_plies"] != PLY_LIMIT
    ):
        raise ValueError("wrong preregistered canonical wire")
    return raw


def schedule():
    """Materialize all 81 potential attempts before any computation."""

    base = {"first_player": "A", "definition_hash": HASH}
    items = [dict(base, kind="exact", max_states=MAX_STATES)]
    for cell, (stage, policy_a, policy_b, start, count) in enumerate(CELLS):
        items.extend(
            dict(
                base,
                kind="game",
                cell=cell,
                stage=stage,
                policy_a=policy_a,
                policy_b=policy_b,
                seed=seed,
                max_nodes_per_role=MAX_NODES,
            )
            for seed in range(start, start + count)
        )
    if len(items) != PLANNED_ATTEMPTS:
        raise ValueError("wrong fixed attempt count")
    return items


def validate_result(item, result):
    """Reject drift, failed evidence, bad replay, or proof-bound violations."""

    if type(result) is not dict:
        raise ValueError("result must be a record")
    game = item["kind"] == "game"
    complete = result.get("status") == "COMPLETE"
    keys = (
        ("first_player", "policy_a", "policy_b", "seed", "max_nodes_per_role")
        if game
        else ("max_states",)
    )
    if result.get("status") not in ("COMPLETE", "UNKNOWN_CENSORED") or any(
        result.get(key) != item[key] for key in keys + ("definition_hash",)
    ):
        raise ValueError("failed record or scheduled condition drift")
    if result.get("replay_count") != int(game or complete):
        raise ValueError("wrong single-replay count")
    if game and result.get("replay_verified") is not True:
        raise ValueError("game prefix replay was not verified")

    if game:
        if (
            type(result.get("plies")) is not int
            or type(result.get("actions")) is not list
            or len(result["actions"]) != result["plies"]
            or type(result.get("decisions")) is not list
        ):
            raise ValueError("invalid selected/applied prefix")
        nodes = result.get("nodes_by_role")
        accounting = result.get("node_accounting")
        if type(nodes) is not dict or type(accounting) is not dict:
            raise ValueError("missing node accounting")
        for actor, policy in (
            ("A", item["policy_a"]),
            ("B", item["policy_b"]),
        ):
            charged = nodes.get(actor)
            if (
                type(charged) is not int
                or not 0 <= charged <= item["max_nodes_per_role"]
                or (policy == "R" and charged != 0)
            ):
                raise ValueError("invalid charged nodes")
            expected = (
                "UNMETERED_RANDOM_SELECTION_NOT_ZERO_COMPUTE"
                if policy == "R"
                else "SEARCH_CACHE_MISSES"
            )
            if accounting.get(actor) != expected:
                raise ValueError("invalid node-accounting label")
        for decision in result["decisions"]:
            actor = decision.get("actor")
            if actor not in ("A", "B"):
                raise ValueError("invalid decision actor")
            policy = item["policy_" + actor.lower()]
            if policy == "T4" and decision.get("selection_status") == "SELECTED":
                values = decision.get("last_action_values")
                legal_count = decision.get("legal_action_count")
                if (
                    type(values) is not list
                    or type(legal_count) is not int
                    or not values
                    or len(values) != legal_count
                    or any(
                        type(value) is not dict
                        or type(value.get("value")) is not int
                        or value["value"] not in (-1, 0, 1)
                        for value in values
                    )
                ):
                    raise ValueError("invalid complete T4 action values")

    if complete:
        wire = result if game else result.get("actual_result")
        if type(wire) is not dict:
            raise ValueError("missing completed result")
        plies = wire.get("plies") if game else wire.get("principal_variation_plies")
        decisive = (
            wire.get("winner") in ("A", "B")
            if game
            else wire.get("value_for_a") in (-1, 1)
        )
        if (
            not decisive
            or type(plies) is not int
            or not 0 <= plies <= BOUND
            or wire.get("terminal_reason")
            not in ("GOAL", "NO_LEGAL_ACTION")
        ):
            raise ValueError("PROOF_INTEGRITY_FAILURE")
    elif game:
        censor = result.get("censor")
        if (
            result.get("winner") is not None
            or result.get("terminal_reason") is not None
            or not 0 <= result["plies"] < BOUND
            or type(censor) is not dict
            or censor.get("role") not in ("A", "B")
            or censor.get("visited_nodes") != item["max_nodes_per_role"]
            or censor.get("max_nodes") != item["max_nodes_per_role"]
            or result["nodes_by_role"].get(censor.get("role"))
            != item["max_nodes_per_role"]
        ):
            raise ValueError("invalid UNKNOWN game prefix")
    elif result.get("actual_result") is not None or result.get("error") != {
        "type": "SolveBudgetExceeded",
        "searched_states": item["max_states"],
        "max_states": item["max_states"],
    }:
        raise ValueError("invalid UNKNOWN exact result")


def short_forced(result):
    """Whether the completed initial T4 selection has a nonzero best value."""

    if result.get("policy_a") != "T4":
        return False
    for decision in result.get("decisions", []):
        if (
            decision.get("ply") == 0
            and decision.get("actor") == "A"
            and decision.get("selection_status") == "SELECTED"
        ):
            values = [value["value"] for value in decision["last_action_values"]]
            return max(values) != 0
    return False


def wilson(wins, count):
    return list(_wilson_interval(wins, count)) if count else None


def summarize(records, disposition=None, failure=None):
    """Summarize every fixed denominator without pooling ordered conditions."""

    games = [
        record
        for record in records
        if record["scheduled"]["kind"] == "game"
    ]
    exact_status = next(
        (
            record["status"]
            for record in records
            if record["scheduled"]["kind"] == "exact"
        ),
        "NOT_STARTED",
    )
    cells = []
    for cell, (stage, policy_a, policy_b, start, count) in enumerate(CELLS):
        mine = [
            record
            for record in games
            if record["scheduled"]["cell"] == cell
        ]
        done = [
            record["result"]
            for record in mine
            if record["status"] == "COMPLETE"
        ]
        a_wins = sum(result["winner"] == "A" for result in done)
        not_started = count - len(mine)
        cells.append(
            {
                "cell": cell,
                "stage": stage,
                "first_player": "A",
                "profile": [policy_a, policy_b],
                "seeds": list(range(start, start + count)),
                "planned": count,
                "attempted": len(mine),
                "completed": len(done),
                "a_wins": a_wins,
                "b_wins": len(done) - a_wins,
                "censored": sum(
                    record["status"] == "UNKNOWN_CENSORED"
                    for record in mine
                ),
                "failed": sum(record["status"] == "FAILED" for record in mine),
                "not_started": not_started,
                "not_started_gate_closed": 0 if failure else not_started,
                "not_started_failure": not_started if failure else 0,
                "statuses": dict(Counter(record["status"] for record in mine)),
                "charged_nodes_by_role": {
                    actor: sum(
                        value
                        for record in mine
                        for value in [
                            (record.get("result") or {})
                            .get("nodes_by_role", {})
                            .get(actor)
                        ]
                        if type(value) is int and value >= 0
                    )
                    for actor in ("A", "B")
                },
                "a_wilson95_descriptive": wilson(a_wins, len(done)),
            }
        )

    witness_games = {"A": 0, "B": 0}
    for record in games:
        if record["status"] != "COMPLETE":
            continue
        for actor in witness_games:
            if record["scheduled"]["policy_" + actor.lower()] != "T4":
                continue
            if any(
                decision.get("actor") == actor
                and decision.get("selection_status") == "SELECTED"
                and {-1, 1}.issubset(
                    value["value"]
                    for value in decision.get("last_action_values", [])
                )
                for decision in record["result"]["decisions"]
            ):
                witness_games[actor] += 1

    base_pass = (
        cells[0]["completed"] == 16
        and 5 <= cells[0]["a_wins"] <= 11
        and cells[1]["completed"] == 16
        and 4 <= cells[1]["a_wins"] <= 12
    )
    ready = (
        exact_status == "UNKNOWN_CENSORED"
        and len(games) == PLANNED_GAMES
        and all(cell["completed"] == cell["planned"] for cell in cells)
        and base_pass
        and 5 <= cells[2]["a_wins"] <= 11
        and cells[3]["a_wins"] >= 6
        and cells[4]["b_wins"] >= 6
        and cells[5]["a_wins"] >= 7
        and cells[6]["b_wins"] >= 7
        and all(count >= 2 for count in witness_games.values())
    )

    if disposition is None and exact_status == "COMPLETE":
        disposition = "TOO_EASILY_SOLVED"
    if disposition is None and any(
        short_forced(record["result"])
        for record in games
        if record["status"] != "FAILED" and record.get("result") is not None
    ):
        disposition = "SHORT_FORCED_RESULT"
    if disposition is None:
        if ready:
            disposition = "HUMAN_REVIEW_ELIGIBLE"
        elif any(
            record["status"] == "UNKNOWN_CENSORED" for record in games
        ):
            disposition = "INSUFFICIENT_EVIDENCE"
        else:
            disposition = "NO_FLAG"

    not_started = PLANNED_ATTEMPTS - len(records)
    total_nodes = {
        actor: sum(cell["charged_nodes_by_role"][actor] for cell in cells)
        for actor in ("A", "B")
    }
    return {
        "protocol": PROTOCOL,
        "execution_status": "FAILED" if failure else "COMPLETE",
        "failure": failure,
        "disposition": "FAILED" if failure else disposition,
        "planned": PLANNED_ATTEMPTS,
        "attempted": len(records),
        "not_started": not_started,
        "not_started_gate_closed": 0 if failure else not_started,
        "not_started_failure": not_started if failure else 0,
        "statuses": dict(Counter(record["status"] for record in records)),
        "exact_status": exact_status,
        "cells": cells,
        "base_pass": base_pass,
        "tactical_choice_witness_games": witness_games,
        "tactical_witness_is_depth_proof": False,
        "charged_nodes_by_role": total_nodes,
        "r_compute": "UNMETERED_RANDOM_SELECTION_NOT_ZERO_COMPUTE",
        "acceptance": "PROVISIONAL_UNTIL_FULL_REGRESSION",
        "fairness_established": False,
        "hardness_established": False,
        "fun_established": False,
    }


def run_pilot(repository, registered_commit):
    """Execute the one immutable prospective cascade from registered source."""

    repository = Path(repository)
    output = repository / "experiments/runs" / PROTOCOL
    if output.exists():
        raise FileExistsError("immutable run exists; no retry or resume")
    if not isinstance(registered_commit, str) or not re.fullmatch(
        "[0-9a-f]{40}", registered_commit
    ):
        raise ValueError("full registration commit required")
    source = source_snapshot(repository, clean=True)
    if source["git_commit"] != registered_commit:
        raise ValueError("wrong registration commit")
    output.mkdir(parents=True, exist_ok=False)

    saved = {}
    records = []
    failure = None
    disposition = None
    current = None

    def save(name, value):
        path = output / name
        _publish(path, value)
        saved[name] = hashlib.sha256(path.read_bytes()).hexdigest()

    def check_source():
        if source_snapshot(repository) != source:
            raise ValueError("registered source drift")

    planned = schedule()
    try:
        save("attempt.json", {"source": source, "started_at": _utc()})
        raw = load_definition(repository)
        save(
            "manifest.json",
            {
                "protocol": PROTOCOL,
                "source": source,
                "definition": raw,
                "schedule": planned,
                "certificate": {
                    "definition_hash": HASH,
                    "max_natural_plies": BOUND,
                    "configured_max_plies": PLY_LIMIT,
                    "ply_limit_unreachable": True,
                    "proof": (
                        "remaining runner-distance starts 12; A moves and B "
                        "captures decrease it, so alternating play ends by 23"
                    ),
                },
                "exposure": (
                    "SOURCE_DESIGNED_DEVELOPMENT_NOT_UNTOUCHED_CONFIRMATION"
                ),
            },
        )
        for ordinal, item in enumerate(planned):
            check_source()
            stem = "{:04d}".format(ordinal)
            save(
                stem + "-attempt.json",
                {"scheduled": item, "started_at": _utc()},
            )
            current = {"scheduled": item, "status": "FAILED", "result": None}
            records.append(current)
            try:
                if item["kind"] == "exact":
                    current["result"] = exact_one(raw, item["max_states"])
                else:
                    current["result"] = play_adapter.play_one(
                        raw,
                        item["policy_a"],
                        item["policy_b"],
                        item["seed"],
                        item["max_nodes_per_role"],
                    )
            except Exception as error:
                current["error"] = {
                    "type": type(error).__name__,
                    "message": str(error),
                }
            try:
                check_source()
                if "error" not in current:
                    validate_result(item, current["result"])
                    current["status"] = current["result"]["status"]
            except Exception as error:
                current["validation_error"] = {
                    "type": type(error).__name__,
                    "message": str(error),
                }
            try:
                save(stem + "-result.json", current)
            except Exception as error:
                current.update(
                    status_before_publication=current["status"],
                    status="FAILED",
                    publication_error=str(error),
                )
                raise
            if current["status"] == "FAILED":
                raise ValueError("stop after failed attempt")

            result = current["result"]
            current = None
            if item["kind"] == "exact" and result["status"] == "COMPLETE":
                disposition = "TOO_EASILY_SOLVED"
            elif item["kind"] == "game" and short_forced(result):
                disposition = "SHORT_FORCED_RESULT"
            elif ordinal == 32 and not summarize(records)["base_pass"]:
                disposition = summarize(records)["disposition"]
            if disposition is not None:
                break

        check_source()
        if any(
            hashlib.sha256((output / name).read_bytes()).hexdigest() != digest
            for name, digest in saved.items()
        ):
            raise ValueError("published artifact drift")
        save(
            "source-verification.json",
            {
                "source": source,
                "matched": True,
                "publication_sha256": dict(saved),
            },
        )
    except Exception as error:
        failure = {
            "type": type(error).__name__,
            "message": str(error),
            "current": current,
        }
        save("failure.json", failure)

    summary = summarize(records, disposition, failure)
    try:
        save("summary.json", summary)
    except Exception as error:
        failure = {
            "type": type(error).__name__,
            "message": str(error),
            "current": current,
        }
        summary = summarize(records, "FAILED", failure)
        save("summary-publication-failure.json", summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registered-commit", required=True)
    arguments = parser.parse_args()
    result = run_pilot(
        Path(__file__).resolve().parents[1], arguments.registered_commit
    )
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(result["execution_status"] == "FAILED")
