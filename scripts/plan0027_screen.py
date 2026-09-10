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


PLAN = "docs/plans/active/0027-three-currents-swap-push-screen.md"
DATA = (
    "experiments/proposals/"
    "three-currents-swap-push-v0.json"
)
PROTOCOL = "plan0027-three-currents-swap-push-v1"
HASH = "aa3079277a9089aa8758fa04f0d81be09544af39ba9338524cf97e6f98490209"
EXPOSURE = (
    "SOURCE_DESIGNED_AFTER_PLAN0024_0026_PUBLIC_TRACE_DIAGNOSIS_AND_"
    "PREREGISTRATION_GOAL_EFFECT_AND_SHADOW_COUNTERLINES_AND_TWO_BOUNDED_"
    "AND_OR_TRAVERSALS_EXPOSED_NOT_CONFIRMATION"
)
PROPOSAL_STATUS = "FIXED_PROSPECTIVE_NOT_REGISTERED_NOT_PRODUCTION_EXECUTED"
MAX_NODES = MAX_STATES = 100000
BOUND = 54
PLY_LIMIT = 55
CELLS = (
    ("base", "T4", "T4", 900, 16),
    ("base", "T3", "T3", 900, 16),
    ("confirm", "T4", "T4", 1000, 16),
    ("sensitivity", "T4", "T2", 1000, 8),
    ("sensitivity", "T2", "T4", 1000, 8),
    ("simple", "T4", "R", 1000, 8),
    ("simple", "R", "T4", 1000, 8),
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
    if (
        type(payload) is not dict
        or set(payload) != {"status", "exposure", "definitions"}
        or payload.get("status") != PROPOSAL_STATUS
        or payload.get("exposure") != EXPOSURE
    ):
        raise ValueError("wrong preregistered proposal metadata")
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
            game_evidence(item, result)

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


def _position(value, label):
    if (
        type(value) is not list
        or len(value) != 2
        or any(type(coordinate) is not int for coordinate in value)
    ):
        raise ValueError("invalid {} position".format(label))
    return tuple(value)


def game_evidence(item, result):
    """Validate applied decisions and derive candidate-specific game evidence."""

    if item.get("kind") != "game" or result.get("status") != "COMPLETE":
        raise ValueError("evidence requires one complete scheduled game")
    actions = result.get("actions")
    decisions = result.get("decisions")
    plies = result.get("plies")
    if (
        type(actions) is not list
        or type(decisions) is not list
        or type(plies) is not int
        or len(actions) != plies
        or len(decisions) != plies
    ):
        raise ValueError("complete game evidence must cover every applied ply")

    expected_kind = {"A": "SWAP", "B": "PUSH"}
    allowed_vector = {
        "A": {(0, 1), (1, 0)},
        "B": {(-1, 0), (0, -1)},
    }
    horizontal_vector = {"A": (0, 1), "B": (0, -1)}
    evidence = {
        "realized_effect": {"A": False, "B": False},
        "t4_horizontal_selection": {"A": False, "B": False},
    }

    for ply, (decision, action) in enumerate(zip(decisions, actions)):
        actor = "A" if ply % 2 == 0 else "B"
        if (
            type(decision) is not dict
            or decision.get("ply") != ply
            or decision.get("actor") != actor
            or decision.get("selection_status") != "SELECTED"
            or decision.get("selected_action") != action
        ):
            raise ValueError("decision does not match the applied action")
        state = decision.get("input_state")
        if (
            type(state) is not dict
            or set(state) != {"ply", "to_move", "pieces", "outcome"}
            or state.get("ply") != ply
            or state.get("to_move") != actor
            or state.get("outcome") is not None
            or type(state.get("pieces")) is not list
        ):
            raise ValueError("invalid saved decision input state")
        if (
            type(action) is not dict
            or set(action) != {"kind", "from", "to"}
            or action.get("kind") != expected_kind[actor]
        ):
            raise ValueError("invalid candidate action evidence")
        origin = _position(action.get("from"), "action from")
        target = _position(action.get("to"), "action to")
        vector = (target[0] - origin[0], target[1] - origin[1])
        if vector not in allowed_vector[actor]:
            raise ValueError("candidate action has an impossible vector")

        occupied = {}
        for piece in state["pieces"]:
            if (
                type(piece) is not dict
                or set(piece) != {"owner", "piece", "position"}
                or piece.get("owner") not in ("A", "B")
                or type(piece.get("piece")) is not str
                or not piece["piece"]
            ):
                raise ValueError("invalid saved decision piece")
            position = _position(piece.get("position"), "piece")
            if position in occupied:
                raise ValueError("duplicate saved decision position")
            occupied[position] = piece["owner"]
        if occupied.get(origin) != actor:
            raise ValueError("saved actor does not occupy action origin")
        target_owner = occupied.get(target)
        if target_owner == actor:
            raise ValueError("candidate action targets a friendly piece")
        if target_owner is not None:
            evidence["realized_effect"][actor] = True

        policy = item["policy_" + actor.lower()]
        if policy == "T4" and vector == horizontal_vector[actor]:
            evidence["t4_horizontal_selection"][actor] = True

    return evidence


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
    realized_effect_games = {"A": 0, "B": 0}
    t4_horizontal_selection_games = {"A": 0, "B": 0}
    for record in games:
        if record["status"] != "COMPLETE":
            continue
        evidence = game_evidence(record["scheduled"], record["result"])
        for actor in witness_games:
            if evidence["realized_effect"][actor]:
                realized_effect_games[actor] += 1
            if evidence["t4_horizontal_selection"][actor]:
                t4_horizontal_selection_games[actor] += 1
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
        and all(count >= 2 for count in realized_effect_games.values())
        and all(
            count >= 2 for count in t4_horizontal_selection_games.values()
        )
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
        "realized_effect_games": realized_effect_games,
        "realized_effect_is_depth_proof": False,
        "t4_horizontal_selection_games": t4_horizontal_selection_games,
        "horizontal_selection_is_depth_proof": False,
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
                        "weighted potential Phi starts 54; A empty/SWAP "
                        "decreases it 1/3 and B empty/PUSH decreases it 2/1, "
                        "so every legal play ends by 54"
                    ),
                },
                "exposure": EXPOSURE,
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
