"""One immutable, structurally no-draw pilot; run/inspect from the repo root."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import time

from parity_forge.dsl import canonical_json, definition_hash, parse_definition
from parity_forge.engine import replay_dicts
from parity_forge.solver import SolveBudgetExceeded, solve_game
from parity_forge.symmetry import D4_TRANSFORMS, transform_definition
from scripts.plan0016_pilot import canonical_bytes, publish_json, read_json
from scripts.plan0016_play import PilotPlayError, play_one, summarize_games
from scripts.plan0018_selection import SelectionError, certify_no_draw, select_pilot


PROTOCOL = "plan0018-no-draw-convert-capture-v1"
PLAN = "docs/plans/active/0018-no-draw-convert-capture-pilot.md"
OUTPUT = "experiments/runs/" + PROTOCOL
REPORT = ("experiments/runs/plan0015-factorized-static-census-evidence-v1/stages/"
          "plan0015-factorized-static-census-stage-v1/static-census-report.json")
PREVIOUS = "experiments/runs/plan0016-exploratory-pilot-v1/manifest.json"
POLICIES = ((0, 0), (1, 1), (2, 2), (2, 1), (1, 2))
ACCEPTANCE = "PROVISIONAL_UNTIL_FULL_REGRESSION"
STOP = ("FAILED", "PROOF_INTEGRITY_FAILURE")


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def source_snapshot(repository):
    def git(*args):
        return subprocess.check_output(("git", "-C", str(repository), *args), text=True).strip()
    scope = ("src", "research", "scripts", "tests", PLAN)
    if git("diff", "--name-only", "HEAD", "--", *scope):
        raise ValueError("commit source/tests/registered plan before execution")
    if git("ls-files", "--others", "--exclude-standard", "--", *scope):
        raise ValueError("untracked source/tests/registered plan")
    paths = git("ls-files", "--", *scope).splitlines()
    if PLAN not in paths:
        raise ValueError("registered plan is not committed")
    return {"git_commit": git("rev-parse", "HEAD"), "plan": PLAN,
            "git_dirty": bool(git("status", "--porcelain")),
            "source_sha256": {p: hashlib.sha256((repository / p).read_bytes()).hexdigest()
                              for p in paths if p.endswith(".py") or p == PLAN}}


def make_manifest(selection, attempt):
    if attempt["protocol_id"] != PROTOCOL or len(selection["selected"]) > 16:
        raise ValueError("wrong protocol or carrier ceiling")
    definitions, schedule, exact_schedule = {}, [], []
    for ci, carrier in enumerate(selection["selected"]):
        bases = carrier["definitions"]
        if len(bases) != 2 or [d["first_player"] for d in bases] != ["A", "B"]:
            raise ValueError("expected separate A-first/B-first definitions")
        mechanics = [{k: v for k, v in d.items() if k not in ("name", "first_player")} for d in bases]
        if mechanics[0] != mechanics[1]:
            raise ValueError("first-player members differ in mechanics")
        certificates = [certify_no_draw(raw) for raw in bases]
        if certificates != carrier["no_draw_certificates"]:
            raise ValueError("no-draw certificates do not reconstruct")
        for raw, certificate in zip(bases, certificates):
            definition = parse_definition(raw)
            if json.loads(canonical_json(definition)) != raw:
                raise ValueError("noncanonical selected DSL")
            if max(certificate["initial_counts"].values()) > 3:
                raise ValueError("selected definition exceeds compiler material envelope")
            condition = {"carrier_index": ci, "carrier_id": carrier["carrier_id"],
                         "first_player": raw["first_player"],
                         "max_natural_plies": certificate["max_natural_plies"]}
            identity = definition_hash(definition)
            if identity != certificate["definition_hash"]:
                raise ValueError("certificate definition identity differs")
            exact_schedule.append(dict(condition, ordinal=len(exact_schedule),
                                       definition_hash=identity, max_states=100000))
            for orientation in D4_TRANSFORMS:
                oriented = transform_definition(definition, orientation)
                identity = definition_hash(oriented)
                definitions[identity] = json.loads(canonical_json(oriented))
                for seed in (0, 1):
                    for pa, pb in POLICIES:
                        schedule.append(dict(condition, ordinal=len(schedule), orientation=orientation,
                                             seed=seed, policy_a=pa, policy_b=pb, definition_hash=identity))
    return {"protocol_id": PROTOCOL, "acceptance": ACCEPTANCE, "attempt": attempt,
            "selection": selection, "definitions": definitions, "schedule": schedule,
            "exact_schedule": exact_schedule, "max_nodes_per_role_game": 5000}


def _game_status(game, scheduled):
    if game["status"] not in ("COMPLETE", "SEARCH_CENSORED", "FAILED"):
        raise ValueError("unknown game status")
    if game["status"] == "COMPLETE" and (
            game["winner"] not in ("A", "B")
            or game["plies"] > scheduled["max_natural_plies"]):
        return "PROOF_INTEGRITY_FAILURE"
    if game["status"] == "SEARCH_CENSORED" and game["plies"] >= scheduled["max_natural_plies"]:
        return "PROOF_INTEGRITY_FAILURE"
    return game["status"]


def _exact_status(wire, scheduled):
    if (type(wire["value_for_a"]) is not int or type(wire["principal_variation_plies"]) is not int
            or wire["principal_variation_plies"] < 0
            or (wire["forced_result"], wire["value_for_a"]) not in (("A_WIN", 1), ("B_WIN", -1), ("DRAW", 0))):
        raise ValueError("inconsistent exact value")
    if wire["forced_result"] == "DRAW" or wire["principal_variation_plies"] > scheduled["max_natural_plies"]:
        return "PROOF_INTEGRITY_FAILURE"
    return "COMPLETE"


def _check_exact(record):
    if record["status"] not in ("COMPLETE", "UNKNOWN_CENSORED", *STOP):
        raise ValueError("unknown exact status")
    wire = record["actual_result"]
    if record["status"] == "UNKNOWN_CENSORED":
        if (wire is not None or record["verification"] is not None
                or record["error"] != {"type": "SolveBudgetExceeded", "searched_states": 100000, "max_states": 100000}):
            raise ValueError("exact censor differs from the registered state budget")
    if record["status"] in ("COMPLETE", "PROOF_INTEGRITY_FAILURE"):
        if record["status"] != _exact_status(wire, record["scheduled"]):
            raise ValueError("exact proof disposition changed")
        if (type(wire["searched_states"]) is not int or not 0 < wire["searched_states"] <= 100000
                or type(wire["cache_hits"]) is not int or wire["cache_hits"] < 0
                or type(wire["principal_variation"]) is not list
                or len(wire["principal_variation"]) != wire["principal_variation_plies"]):
            raise ValueError("exact counter or recorded PV length differs")
        verification = record["verification"]
        state = verification["terminal_state"]
        winner = state["outcome"]["winner"]
        value = {"A": 1, "B": -1, None: 0}[winner]
        if (verification["external_replay_count"] != 1 or not verification["source_unchanged"]
                or state["ply"] != wire["principal_variation_plies"]
                or state["outcome"]["reason"] != wire["terminal_reason"]
                or value != wire["value_for_a"]):
            raise ValueError("saved exact replay verification disagrees")


def summarize_run(manifest, records, exact_records, failure=None, exact_attempts=None):
    if canonical_bytes(manifest) != canonical_bytes(make_manifest(manifest["selection"], manifest["attempt"])):
        raise ValueError("manifest differs from registered schedules/certificates")
    for rows, schedule in ((records, manifest["schedule"]), (exact_records, manifest["exact_schedule"])):
        if len(rows) > len(schedule) or any(canonical_bytes(r["scheduled"]) != canonical_bytes(schedule[i]) for i, r in enumerate(rows)):
            raise ValueError("records are not the exact ordered prefix")
        if any(r["status"] in STOP for r in rows[:-1]):
            raise ValueError("record follows a stopping failure")
    for record in records:
        game, scheduled = record["game"], record["scheduled"]
        if any(type(game[k]) is not type(scheduled[k]) or game[k] != scheduled[k]
               for k in ("definition_hash", "first_player", "policy_a", "policy_b", "seed")):
            raise ValueError("game condition differs from schedule")
        if (type(game["max_nodes_per_role"]) is not int or game["max_nodes_per_role"] != 5000
                or any(type(n) is not int or not 0 <= n <= 5000 for n in game["nodes_by_role"].values())):
            raise ValueError("game search budget differs from registration")
        if record["status"] != _game_status(game, scheduled):
            raise ValueError("game proof disposition changed")
    if exact_records and (len(records) != len(manifest["schedule"]) or any(r["status"] in STOP for r in records)):
        raise ValueError("exact work preceded a finished nonfailed gameplay schedule")
    for record in exact_records:
        _check_exact(record)
    attempt_count = len(exact_records) if exact_attempts is None else exact_attempts
    conditions = []
    for target in manifest["exact_schedule"]:
        matching = lambda row: all(row["scheduled"][k] == target[k] for k in ("carrier_index", "first_player"))
        rows = [r for r in records if matching(r)]
        exact = next((r for r in exact_records if matching(r)), None)
        profiles = []
        for pa, pb in POLICIES:
            subgroup = [r for r in rows if (r["game"]["policy_a"], r["game"]["policy_b"]) == (pa, pb)]
            def describe(group, planned):
                games = [dict(r["game"], status="FAILED") if r["status"] in STOP else r["game"] for r in group]
                return summarize_games(games, planned)
            profiles.append({"policy_a": pa, "policy_b": pb, "summary": describe(subgroup, 16),
                             "orientations": [{"orientation": o, "summary": describe(
                                 [r for r in subgroup if r["scheduled"]["orientation"] == o], 2)}
                                              for o in D4_TRANSFORMS]})
        flag = (len(rows) == 80 and all(r["status"] == "COMPLETE" for r in rows)
                and exact is not None and exact["status"] == "COMPLETE"
                and all(min(p["summary"]["a_wins"], p["summary"]["b_wins"]) > 0
                        for p in profiles if (p["policy_a"], p["policy_b"]) in ((1, 1), (2, 2))))
        conditions.append({"condition": target, "no_draw_certificate":
                           manifest["selection"]["selected"][target["carrier_index"]]["no_draw_certificates"][
                               0 if target["first_player"] == "A" else 1],
                           "profiles": profiles, "exact": exact,
                           "exact_status": exact["status"] if exact is not None else (
                               "ATTEMPTED_NO_RESULT" if target["ordinal"] < attempt_count else "NOT_STARTED"),
                           "status": "FURTHER_DIAGNOSIS" if flag else "OBSERVATIONS_ONLY"})
    statuses = Counter(r["status"] for r in records + exact_records)
    failed = failure is not None or any(statuses[s] for s in STOP)
    complete = len(records) == len(manifest["schedule"]) and len(exact_records) == len(manifest["exact_schedule"])
    return {"protocol_id": PROTOCOL, "acceptance": ACCEPTANCE,
            "execution_status": "FAILED" if failed else ("SCHEDULE_COMPLETE" if complete else "INCOMPLETE"),
            "game_statuses": dict(Counter(r["status"] for r in records)),
            "exact_statuses": dict(Counter(r["status"] for r in exact_records)),
            "planned_games": len(manifest["schedule"]), "not_started_games": len(manifest["schedule"]) - len(records),
            "planned_exact": len(manifest["exact_schedule"]), "unrecorded_exact": len(manifest["exact_schedule"]) - len(exact_records),
            "exact_attempts": attempt_count,
            "failure": failure, "conditions": conditions,
            "further_diagnosis_count": sum(c["status"] == "FURTHER_DIAGNOSIS" for c in conditions),
            "claims": {"fair_game": False, "human_skill_calibrated": False, "confirmation": False}}


def _exact_one(output, scheduled, raw, check_source, source):
    started = time.monotonic()
    publish_json(output / "{:04d}-attempt.json".format(scheduled["ordinal"]),
                 {"scheduled": scheduled, "started_at": _utc(), "source_digest": _digest(source)})
    record = {"scheduled": scheduled, "actual_result": None, "verification": None, "error": None}
    try:
        definition = parse_definition(raw)
        wire = solve_game(definition, max_states=scheduled["max_states"]).to_dict()
        record["actual_result"] = wire
        terminal = replay_dicts(definition, wire["principal_variation"])
        if (not terminal.terminal or terminal.ply != wire["principal_variation_plies"]
                or terminal.outcome.reason != wire["terminal_reason"]
                or {1: "A", -1: "B", 0: None}[wire["value_for_a"]] !=
                   (terminal.outcome.winner.value if terminal.outcome.winner else None)):
            raise ValueError("exact PV replay disagrees with result")
        record.update(status=_exact_status(wire, scheduled), verification={
            "terminal_state": terminal.to_dict(), "external_replay_count": 1, "source_unchanged": True})
    except SolveBudgetExceeded as error:
        record.update(status="UNKNOWN_CENSORED", error={
            "type": type(error).__name__, "searched_states": error.searched_states, "max_states": error.max_states})
    except Exception as error:
        record.update(status="FAILED", error={"type": type(error).__name__, "message": str(error)})
    try:
        check_source()
    except Exception as error:
        record.update(status="FAILED", error={"type": type(error).__name__, "message": str(error)})
        if record["verification"] is not None:
            record["verification"]["source_unchanged"] = False
    try:
        _check_exact(record)
    except Exception as error:
        record.update(status="FAILED", error={"type": type(error).__name__, "message": str(error)})
    record.update(completed_at=_utc(), elapsed_seconds=time.monotonic() - started)
    publish_json(output / "{:04d}-result.json".format(scheduled["ordinal"]), record)
    return record


def run_pilot(repository, output=None):
    output = repository / OUTPUT if output is None else output
    if output.exists():
        raise FileExistsError("existing attempt is immutable; no resume/repeat")
    source = source_snapshot(repository)
    if source["git_dirty"]:
        raise ValueError("start the registered pilot from a globally clean Git checkout")
    paths = {"report": repository / REPORT, "previous_manifest": repository / PREVIOUS}
    inputs = {key: path.read_bytes() for key, path in paths.items()}
    hashes = {key: hashlib.sha256(raw).hexdigest() for key, raw in inputs.items()}
    def check_source():
        current = source_snapshot(repository)
        if current["source_sha256"] != source["source_sha256"]:
            raise ValueError("registered source/plan changed")
    def check_inputs():
        if any(hashlib.sha256(path.read_bytes()).hexdigest() != hashes[key] for key, path in paths.items()):
            raise ValueError("selection input bytes changed")
    output.mkdir(exist_ok=False)
    for directory in ("games", "exact"):
        (output / directory).mkdir()
    attempt = {"protocol_id": PROTOCOL, "status": "STARTED", "started_at": _utc(),
               "acceptance": ACCEPTANCE, "source": source, "input_sha256": hashes,
               "environment": {"host": platform.node(), "python": platform.python_version()},
               "exposure": "OUTCOME_INFORMED_RESTRICTION_NOT_CONFIRMATION"}
    publish_json(output / "attempt.json", attempt)
    selection, manifest, records, exact_records, failure, stage = None, None, [], [], None, "SELECTION"
    try:
        selection = select_pilot(inputs["report"], inputs["previous_manifest"])
        check_inputs()
        check_source()
        manifest = make_manifest(selection, attempt)
        publish_json(output / "manifest.json", manifest)
        stage = "GAMEPLAY"
        for scheduled in manifest["schedule"]:
            try:
                game = play_one(manifest["definitions"][scheduled["definition_hash"]],
                                scheduled["policy_a"], scheduled["policy_b"], scheduled["seed"], 5000)
            except PilotPlayError as error:
                game = error.partial_record
            record = {"scheduled": scheduled, "game": game, "status": _game_status(game, scheduled)}
            publish_json(output / "games" / "{:04d}.json".format(scheduled["ordinal"]), record)
            records.append(record)
            if record["status"] in STOP:
                raise RuntimeError("gameplay stopped: " + record["status"])
        check_source()
        if not any(r["status"] in STOP for r in records):
            stage = "EXACT"
            for scheduled in manifest["exact_schedule"]:
                record = _exact_one(output / "exact", scheduled,
                                    manifest["definitions"][scheduled["definition_hash"]], check_source, source)
                exact_records.append(record)
                if record["status"] in STOP:
                    raise RuntimeError("exact work stopped: " + record["status"])
        check_inputs()
        check_source()
        publish_json(output / "source-verification.json", {"source": source, "matched_after_execution": True,
                                                          "input_sha256": hashes})
    except Exception as error:
        failure = {"stage": stage, "type": type(error).__name__, "message": str(error), "finished_at": _utc()}
        if not (output / "manifest.json").exists():
            manifest = None
            prefix = error.partial_selection if isinstance(error, SelectionError) else selection
            if prefix is not None:
                publish_json(output / "selection-failure-prefix.json", prefix)
                failure["partial_selection_sha256"] = _digest(prefix)
        publish_json(output / "failure.json", failure)
    attempts_count = len(list((output / "exact").glob("*-attempt.json")))
    summary = (summarize_run(manifest, records, exact_records, failure, attempts_count) if manifest is not None else
               {"protocol_id": PROTOCOL, "acceptance": ACCEPTANCE, "execution_status": "FAILED", "failure": failure})
    publish_json(output / "summary.json", summary)
    return summary


def inspect_run(output):
    """Reconstruct records; replay games only, never exact PVs or policies."""
    attempt = read_json(output / "attempt.json")
    if attempt["protocol_id"] != PROTOCOL:
        raise ValueError("unexpected attempt protocol")
    failure = read_json(output / "failure.json") if (output / "failure.json").exists() else None
    if failure is not None and "partial_selection_sha256" in failure:
        if _digest(read_json(output / "selection-failure-prefix.json")) != failure["partial_selection_sha256"]:
            raise ValueError("saved selection failure prefix differs")
    if not (output / "manifest.json").exists():
        summary = {"protocol_id": PROTOCOL, "acceptance": ACCEPTANCE,
                   "execution_status": "FAILED" if failure else "INCOMPLETE", "failure": failure}
        if (output / "summary.json").exists() and read_json(output / "summary.json") != summary:
            raise ValueError("preselection failure summary differs")
        return summary
    manifest = read_json(output / "manifest.json")
    if manifest["attempt"] != attempt:
        raise ValueError("manifest attempt differs from preselection record")
    def prefix(directory, suffix):
        paths = sorted(directory.glob("*" + suffix))
        if [p.name for p in paths] != ["{:04d}{}".format(i, suffix) for i in range(len(paths))]:
            raise ValueError("saved records are not an unbroken ordinal prefix")
        return [read_json(p) for p in paths]
    records = prefix(output / "games", ".json")
    exact_records = prefix(output / "exact", "-result.json")
    exact_attempts = prefix(output / "exact", "-attempt.json")
    if not len(exact_records) <= len(exact_attempts) <= min(len(exact_records) + 1, len(manifest["exact_schedule"])):
        raise ValueError("exact attempts/results do not form a single attempt prefix")
    if exact_attempts and (len(records) != len(manifest["schedule"]) or any(r["status"] in STOP for r in records)):
        raise ValueError("exact attempt preceded completed gameplay schedule")
    for i, row in enumerate(exact_attempts):
        if row["scheduled"] != manifest["exact_schedule"][i] or row["source_digest"] != _digest(attempt["source"]):
            raise ValueError("exact attempt differs from manifest/source")
    summary = summarize_run(manifest, records, exact_records, failure, len(exact_attempts))
    for record in records:
        game = record["game"]
        definition = parse_definition(manifest["definitions"][record["scheduled"]["definition_hash"]])
        state = replay_dicts(definition, game["actions"])
        if state.ply != game["plies"] or (game["status"] != "FAILED" and state.to_dict() != game["state_after_prefix"]):
            raise ValueError("saved game prefix differs from replay")
        if game["status"] == "COMPLETE" and (not state.terminal or state.outcome.reason != game["terminal_reason"]
                or (state.outcome.winner.value if state.outcome.winner else None) != game["winner"]):
            raise ValueError("saved game terminal differs from replay")
        if game["status"] == "SEARCH_CENSORED" and state.terminal:
            raise ValueError("saved censor has terminal prefix")
    if (output / "source-verification.json").exists():
        verification = read_json(output / "source-verification.json")
        if verification != {"source": attempt["source"], "matched_after_execution": True,
                            "input_sha256": attempt["input_sha256"]}:
            raise ValueError("saved source verification differs")
    elif summary["execution_status"] == "SCHEDULE_COMPLETE":
        raise ValueError("finished schedule lacks final source verification")
    if (output / "summary.json").exists() and read_json(output / "summary.json") != summary:
        raise ValueError("saved summary does not reconstruct")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "inspect"))
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    summary = run_pilot(repository) if args.command == "run" else inspect_run(repository / OUTPUT)
    print(json.dumps({k: v for k, v in summary.items() if k != "conditions"}, sort_keys=True))
    return 1 if summary["execution_status"] == "FAILED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
