"""One preregistered candidate, finite cascade, no retries or quality claims."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess

from parity_forge.dsl import canonical_json, definition_hash, parse_definition
from parity_forge.play import _wilson_interval
from scripts.plan0020_pilot import exact_one, _publish, _utc
from scripts.plan0022_play import play_one

PLAN = "docs/plans/active/0022-human-readiness-screen.md"
DATA = "experiments/proposals/link-hop-three-guards-v0.json"
PROTOCOL = "plan0022-link-hop-v1"
HASH = "2ce75c6ef9e4abd5ab4401469a4a3be62a22b29a9e7c314be75bc324015ffc4e"
MAX_NODES = MAX_STATES = 100000
BOUND = 39
CELLS = (("base", "T4", "T4", 100, 16), ("base", "H4", "H4", 100, 16),
         ("confirm", "T4", "T4", 200, 16), ("confirm", "H4", "H4", 200, 16),
         ("cross", "T4", "H4", 200, 8), ("cross", "H4", "T4", 200, 8),
         ("skill", "T4", "T2", 200, 8), ("skill", "T2", "T4", 200, 8),
         ("skill", "H4", "H2", 200, 8), ("skill", "H2", "H4", 200, 8),
         ("trivial", "T4", "G", 200, 8), ("trivial", "G", "T4", 200, 8))


def source_snapshot(repo, clean=False):
    def git(*args):
        return subprocess.check_output(("git", "-C", str(repo), *args), text=True).strip()
    if clean and git("status", "--porcelain"):
        raise ValueError("clean registered worktree required")
    paths = sorted(p for p in git("ls-files").splitlines() if p.endswith(".py") or p in (PLAN, DATA))
    if not {PLAN, DATA}.issubset(paths):
        raise ValueError("plan and data must be registered")
    if any(p.endswith(".py") for p in git("ls-files", "--others", "--exclude-standard").splitlines()):
        raise ValueError("untracked Python source")
    return dict(git_commit=git("rev-parse", "HEAD"), sha256={
        p: hashlib.sha256((repo/p).read_bytes()).hexdigest() for p in paths})


def load_definition(repo):
    rows = json.loads((repo/DATA).read_text())["definitions"]
    if len(rows) != 1:
        raise ValueError("exactly one fixed definition required")
    raw, d = rows[0], parse_definition(rows[0])
    if (definition_hash(d) != HASH or json.loads(canonical_json(d)) != raw
            or raw["first_player"] != "A" or raw["max_plies"] != BOUND + 1):
        raise ValueError("wrong preregistered canonical wire")
    return raw


def schedule():
    base = dict(first_player="A", definition_hash=HASH)
    items = [dict(base, kind="exact", max_states=MAX_STATES)]
    for cell, (stage, a, b, start, count) in enumerate(CELLS):
        items.extend(dict(base, kind="game", cell=cell, stage=stage, policy_a=a, policy_b=b,
                          seed=seed, max_nodes_per_role=MAX_NODES) for seed in range(start, start+count))
    return items


def validate_result(item, r):
    game, complete = item["kind"] == "game", r["status"] == "COMPLETE"
    keys = ("first_player", "policy_a", "policy_b", "seed", "max_nodes_per_role") if game else ("max_states",)
    if r["status"] not in ("COMPLETE", "UNKNOWN_CENSORED") or any(r[k] != item[k] for k in (*keys, "definition_hash")):
        raise ValueError("failed record or condition drift")
    if r["replay_count"] != int(game or complete) or (game and r["replay_verified"] is not True):
        raise ValueError("wrong single-replay verification")
    if game:
        if type(r["plies"]) is not int or len(r["actions"]) != r["plies"]:
            raise ValueError("invalid prefix length")
        for actor, policy in (("A", item["policy_a"]), ("B", item["policy_b"])):
            n = r["nodes_by_role"][actor]
            if type(n) is not int or not 0 <= n <= MAX_NODES or (policy == "G" and n != 0):
                raise ValueError("invalid charged nodes")
        for d in r["decisions"]:
            if item["policy_" + d["actor"].lower()] == "T4" and d["selection_status"] == "SELECTED":
                values = d["last_action_values"]
                if len(values) != d["legal_action_count"] or not values or any(
                        type(v["value"]) is not int or v["value"] not in (-1, 0, 1) for v in values):
                    raise ValueError("invalid complete T4 action values")
    if complete:
        wire = r if game else r["actual_result"]
        plies = wire["plies"] if game else wire["principal_variation_plies"]
        decisive = wire["winner"] in ("A", "B") if game else wire["value_for_a"] in (-1, 1)
        if not decisive or type(plies) is not int or not 0 <= plies <= BOUND or wire["terminal_reason"] not in ("GOAL", "NO_LEGAL_ACTION"):
            raise ValueError("PROOF_INTEGRITY_FAILURE")
    elif game:
        c = r["censor"]
        if (r["winner"] is not None or r["terminal_reason"] is not None or not 0 <= r["plies"] < BOUND
                or c["visited_nodes"] != MAX_NODES or c["max_nodes"] != MAX_NODES
                or r["nodes_by_role"][c["role"]] != MAX_NODES):
            raise ValueError("invalid UNKNOWN game prefix")
    elif r["actual_result"] is not None or r["error"] != dict(
            type="SolveBudgetExceeded", searched_states=MAX_STATES, max_states=MAX_STATES):
        raise ValueError("invalid UNKNOWN exact result")


def short_forced(r):
    return r.get("policy_a") == "T4" and any(
        d["ply"] == 0 and d["actor"] == "A" and d["selection_status"] == "SELECTED"
        and max(v["value"] for v in d["last_action_values"]) != 0 for d in r["decisions"])


def wilson(wins, count):
    return list(_wilson_interval(wins, count)) if count else None


def summarize(records, disposition, failure=None):
    cells, witnesses = [], {"A": 0, "B": 0}
    games = [r for r in records if r["scheduled"]["kind"] == "game"]
    exact_status = next((r["status"] for r in records if r["scheduled"]["kind"] == "exact"), "NOT_STARTED")
    for i, (stage, a, b, start, count) in enumerate(CELLS):
        mine = [r for r in games if r["scheduled"]["cell"] == i]
        done = [r["result"] for r in mine if r["status"] == "COMPLETE"]
        aw = sum(r["winner"] == "A" for r in done)
        cells.append(dict(cell=i, stage=stage, first_player="A", profile=[a, b], seeds=list(range(start, start+count)),
                          planned=count, attempted=len(mine), completed=len(done), a_wins=aw, b_wins=len(done)-aw,
                          censored=sum(r["status"] == "UNKNOWN_CENSORED" for r in mine),
                          failed=sum(r["status"] == "FAILED" for r in mine), not_started=count-len(mine),
                          not_started_gate_closed=0 if failure else count-len(mine),
                          not_started_failure=count-len(mine) if failure else 0,
                          charged_nodes_by_role={actor: sum(n for r in mine for n in [
                              (r["result"] or {}).get("nodes_by_role", {}).get(actor)] if type(n) is int and n >= 0)
                              for actor in ("A", "B")},
                          a_wilson95_descriptive=wilson(aw, len(done)) if stage in ("base", "confirm", "cross") else None))
    for r in games:
        if r["status"] != "COMPLETE":
            continue
        for actor in witnesses:
            if r["scheduled"]["policy_"+actor.lower()] == "T4" and any(
                    d["actor"] == actor and d["selection_status"] == "SELECTED"
                    and {-1, 1}.issubset(v["value"] for v in d["last_action_values"]) for d in r["result"]["decisions"]):
                witnesses[actor] += 1
    cross_n, cross_a = sum(c["completed"] for c in cells[4:6]), sum(c["a_wins"] for c in cells[4:6])
    base_ok = all(c["completed"] == 16 and 4 <= c["a_wins"] <= 12 for c in cells[:2])
    ready = (exact_status == "UNKNOWN_CENSORED" and len(games) == 128
             and all(c["completed"] == c["planned"] for c in cells) and base_ok
             and all(5 <= c["a_wins"] <= 11 for c in cells[2:4]) and 4 <= cross_a <= 12
             and all(c["a_wins" if c["profile"][0].endswith("4") else "b_wins"] >= 6 for c in cells[6:])
             and all(n >= 2 for n in witnesses.values()))
    if disposition is None and any(short_forced(r["result"]) for r in games if r["status"] != "FAILED"):
        disposition = "SHORT_FORCED_RESULT"
    if disposition is None:
        disposition = "HUMAN_REVIEW_ELIGIBLE" if ready else (
            "INSUFFICIENT_EVIDENCE" if any(r["status"] == "UNKNOWN_CENSORED" for r in games) else "NO_FLAG")
    return dict(protocol=PROTOCOL, execution_status="FAILED" if failure else "COMPLETE", failure=failure,
                disposition="FAILED" if failure else disposition, planned=129, attempted=len(records),
                not_started=129-len(records), not_started_gate_closed=0 if failure else 129-len(records),
                not_started_failure=129-len(records) if failure else 0,
                statuses=dict(Counter(r["status"] for r in records)), exact_status=exact_status, cells=cells, base_pass=base_ok,
                cross_combined=dict(completed=cross_n, a_wins=cross_a, b_wins=cross_n-cross_a,
                                    a_wilson95_descriptive=wilson(cross_a, cross_n), not_self_play=True),
                tactical_choice_witness_games=witnesses, tactical_witness_is_depth_proof=False,
                g_compute="UNMETERED_GOAL_PROGRESS_NOT_ZERO_COMPUTE",
                acceptance="PROVISIONAL_UNTIL_FULL_REGRESSION", fairness_established=False,
                hardness_established=False, fun_established=False)


def run_pilot(repository, registered_commit):
    repo, records, failure, disposition = Path(repository), [], None, None
    output = repo/"experiments/runs"/PROTOCOL
    if output.exists():
        raise FileExistsError("immutable run exists; no retry or resume")
    if not isinstance(registered_commit, str) or not re.fullmatch("[0-9a-f]{40}", registered_commit):
        raise ValueError("full registration commit required")
    source = source_snapshot(repo, clean=True)
    if source["git_commit"] != registered_commit:
        raise ValueError("wrong registration commit")
    output.mkdir(parents=True, exist_ok=False)
    saved, current = {}, None
    def save(name, value):
        path = output/name
        _publish(path, value)
        saved[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    def check_source():
        if source_snapshot(repo) != source:
            raise ValueError("registered source drift")
    planned = schedule()
    try:
        save("attempt.json", dict(source=source, started_at=_utc()))
        raw = load_definition(repo)
        save("manifest.json", dict(protocol=PROTOCOL, source=source, definition=raw, schedule=planned,
             certificate=dict(definition_hash=HASH, max_natural_plies=BOUND, ply_limit_unreachable=True,
                              proof="A-first PLACE fills 20 initial empty cells; HOP preserves occupancy; at most 39 plies"),
             exposure="SOURCE_DESIGNED_DEVELOPMENT_NOT_UNTOUCHED_CONFIRMATION"))
        for ordinal, item in enumerate(planned):
            check_source()
            stem = "{:04d}".format(ordinal)
            save(stem+"-attempt.json", dict(scheduled=item, started_at=_utc()))
            current = dict(scheduled=item, status="FAILED", result=None)
            records.append(current)  # Started failures must never become NOT_STARTED.
            try:
                current["result"] = (exact_one(raw, MAX_STATES) if item["kind"] == "exact" else
                                     play_one(raw, item["policy_a"], item["policy_b"], item["seed"], MAX_NODES))
            except Exception as error:
                current["error"] = dict(type=type(error).__name__, message=str(error))
            try:
                check_source()
                if "error" not in current:
                    validate_result(item, current["result"])
                    current["status"] = current["result"]["status"]
            except Exception as error:
                current["validation_error"] = dict(type=type(error).__name__, message=str(error))
            try:
                save(stem+"-result.json", current)
            except Exception as error:
                current.update(status_before_publication=current["status"], status="FAILED", publication_error=str(error))
                raise
            if current["status"] == "FAILED":
                raise ValueError("stop after failed attempt")
            r, current = current["result"], None
            if item["kind"] == "exact" and r["status"] == "COMPLETE":
                disposition = "TOO_EASILY_SOLVED"
            elif item["kind"] == "game" and short_forced(r):
                disposition = "SHORT_FORCED_RESULT"
            elif ordinal == 32 and not summarize(records, None)["base_pass"]:
                disposition = summarize(records, None)["disposition"]
            if disposition is not None:
                break
        check_source()
        if any(hashlib.sha256((output/name).read_bytes()).hexdigest() != digest for name, digest in saved.items()):
            raise ValueError("published artifact drift")
        save("source-verification.json", dict(source=source, matched=True, publication_sha256=dict(saved)))
    except Exception as error:
        failure = dict(type=type(error).__name__, message=str(error), current=current)
        save("failure.json", failure)
    summary = summarize(records, disposition, failure)
    try:
        save("summary.json", summary)
    except Exception as error:
        summary = summarize(records, "FAILED", dict(type=type(error).__name__, message=str(error), current=current))
        save("summary-publication-failure.json", summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registered-commit", required=True)
    args = parser.parse_args()
    result = run_pilot(Path(__file__).resolve().parents[1], args.registered_commit)
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(result["execution_status"] == "FAILED")
