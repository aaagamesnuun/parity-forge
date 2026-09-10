"""Two fixed capture/hop conditions; reuse the existing bounded recorders."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess

from parity_forge.dsl import canonical_json, definition_hash, parse_definition
from scripts.plan0020_pilot import play_one, exact_one, _publish, _utc

PLAN = "docs/plans/active/0021-capture-hop-trial.md"
DATA = "experiments/proposals/capture-hop-full-ranks-v0.json"
PROTOCOL = "plan0021-capture-hop-v1"
HASHES = ("a5e674e625aa0d2cac9858ef288e96d68ca68799801d7a4e8d12dc29139efe4c",
          "699e3053d0e44615c0e41031097ae26b89deeb09128596c1039736fb5498a639")
PROFILES, SEEDS = ((0, 0), (2, 2), (3, 3)), tuple(range(4))
MAX_NODES, MAX_STATES = 100000, 100000


def certify(raw):
    """Sum of forward distances strictly decreases; no quality claim."""
    d = parse_definition(raw)
    w = json.loads(canonical_json(d))
    if w["schema_version"] != 4:
        raise ValueError("schema4 required")
    for role, kind, dr, edge in (("A", "MOVE_CAPTURE", 1, "BOTTOM"), ("B", "HOP", -1, "TOP")):
        expected = {"action": {"kind": kind, "piece": role.lower(), "vectors": [[dr, c] for c in (-1, 0, 1)]},
                    "goal": {"kind": "REACH_EDGE", "piece": role.lower(), "edge": edge}}
        if w["roles"][role] != expected:
            raise ValueError("role outside capture/hop theorem")
    if any(p["piece"] != p["owner"].lower() for p in w["initial_pieces"]):
        raise ValueError("uncontrolled piece type")
    if {p["owner"] for p in w["initial_pieces"]} != {"A", "B"}:
        raise ValueError("both owners required initially")
    bound = sum(w["board_size"]-1-p["position"][0] if p["owner"] == "A" else p["position"][0]
                for p in w["initial_pieces"])
    if not bound < w["max_plies"]:
        raise ValueError("natural termination must precede cap")
    return dict(definition_hash=definition_hash(d), max_natural_plies=bound,
                every_legal_play_finite_decisive=True, ply_limit_unreachable=True)


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


def load_definitions(repo):
    rows = json.loads((repo/DATA).read_text())["definitions"]
    if tuple(definition_hash(parse_definition(w)) for w in rows) != HASHES:
        raise ValueError("wrong preregistered definition set")
    for w in rows:
        if json.loads(canonical_json(parse_definition(w))) != w:
            raise ValueError("noncanonical wire")
        certify(w)
    return rows


def schedule(rows):
    items = []
    for i, w in enumerate(rows):
        base = dict(candidate=i, first_player=w["first_player"], definition_hash=definition_hash(parse_definition(w)))
        items.append(dict(base, kind="exact", max_states=MAX_STATES))
        items.extend(dict(base, kind="game", policy_a=a, policy_b=b, seed=s, max_nodes_per_role=MAX_NODES)
                     for a, b in PROFILES for s in SEEDS)
    return items


def validate_result(item, result, bound):
    if result["definition_hash"] != item["definition_hash"]:
        raise ValueError("wrong definition result")
    if result["status"] not in ("COMPLETE", "UNKNOWN_CENSORED"):
        raise ValueError("record failed")
    game = item["kind"] == "game"
    for key in (("first_player", "policy_a", "policy_b", "seed", "max_nodes_per_role") if game else ("max_states",)):
        if result[key] != item[key]:
            raise ValueError("result condition differs")
    if result["replay_count"] != int(game or result["status"] == "COMPLETE"):
        raise ValueError("wrong replay count")
    if result["status"] == "COMPLETE":
        wire = result if game else result["actual_result"]
        plies = wire["plies"] if game else wire["principal_variation_plies"]
        decisive = wire["winner"] in ("A", "B") if game else wire["value_for_a"] in (-1, 1)
        if not decisive or not 0 <= plies <= bound or wire["terminal_reason"] not in ("GOAL", "NO_LEGAL_ACTION"):
            raise ValueError("PROOF_INTEGRITY_FAILURE")
    elif game and not 0 <= result["plies"] < bound:
        raise ValueError("censored prefix violates natural bound")


def summarize(rows, planned, records, failure):
    cells, dispositions = [], []
    for i, w in enumerate(rows):
        mine = [r for r in records if r["scheduled"]["candidate"] == i]
        exact = next((r["result"]["status"] for r in mine if r["scheduled"]["kind"] == "exact"), "NOT_STARTED")
        for a, b in PROFILES:
            games = [r["result"] for r in mine if r["scheduled"]["kind"] == "game"
                     and (r["scheduled"]["policy_a"], r["scheduled"]["policy_b"]) == (a, b)]
            done = [g for g in games if g["status"] == "COMPLETE"]
            cells.append(dict(candidate=i, first_player=w["first_player"], profile=[a, b],
                              planned=len(SEEDS), attempted=len(games), completed=len(done),
                              a_wins=sum(g["winner"] == "A" for g in done), b_wins=sum(g["winner"] == "B" for g in done)))
        strong = cells[-1]
        ready = failure is None and all(c["completed"] == len(SEEDS) for c in cells[-len(PROFILES):])
        flag = "TOO_EASILY_SOLVED" if exact == "COMPLETE" else "NO_FLAG"
        if ready and exact == "UNKNOWN_CENSORED" and strong["a_wins"] and strong["b_wins"]:
            flag = "TRIAL_REVIEW_ONLY"
        dispositions.append(dict(candidate=i, first_player=w["first_player"], exact_status=exact, disposition=flag))
    return dict(protocol=PROTOCOL, execution_status="FAILED" if failure else "COMPLETE", failure=failure,
                planned=len(planned), attempted=len(records), not_started=len(planned)-len(records),
                statuses=dict(Counter(r["result"]["status"] for r in records)), cells=cells, candidates=dispositions,
                acceptance="PROVISIONAL_UNTIL_FULL_REGRESSION", fairness_established=False,
                hardness_established=False, fun_established=False)


def run_pilot(repository, registered_commit):
    repo = Path(repository)
    output = repo/"experiments/runs"/PROTOCOL
    if output.exists():
        raise FileExistsError("immutable run exists; no retry or resume")
    if not isinstance(registered_commit, str) or not re.fullmatch("[0-9a-f]{40}", registered_commit):
        raise ValueError("full registered commit required")
    source = source_snapshot(repo, clean=True)
    if source["git_commit"] != registered_commit:
        raise ValueError("wrong registration commit")
    output.mkdir(parents=True, exist_ok=False)
    _publish(output/"attempt.json", dict(source=source, started_at=_utc()))
    rows, planned, records, failure, current = [], [], [], None, None
    try:
        rows = load_definitions(repo)
        planned = schedule(rows)
        _publish(output/"manifest.json", dict(protocol=PROTOCOL, source=source, definitions=rows,
                 certificates=[certify(w) for w in rows], schedule=planned,
                 exposure="DESIGNED_DEVELOPMENT_PILOT_NOT_CONFIRMATION"))
        for ordinal, item in enumerate(planned):
            if source_snapshot(repo) != source:
                raise ValueError("source drift before attempt")
            current = dict(scheduled=item, result=None)
            stem = "{:04d}".format(ordinal)
            _publish(output/(stem+"-attempt.json"), dict(scheduled=item, started_at=_utc()))
            try:
                w = rows[item["candidate"]]
                result = (exact_one(w, MAX_STATES) if item["kind"] == "exact" else
                          play_one(w, item["policy_a"], item["policy_b"], item["seed"], MAX_NODES))
            except Exception as error:
                result = dict(status="FAILED", error=str(error), prefix_available=False)
            current["result"] = result
            records.append(current)
            try:
                if source_snapshot(repo) != source:
                    raise ValueError("source drift after attempt")
                validate_result(item, result, certify(w)["max_natural_plies"])
            except Exception as error:
                result.update(status="FAILED", validation_error=str(error))
            try:
                _publish(output/(stem+"-result.json"), current)
            except Exception as error:
                result.update(status_before_publication=result["status"], status="FAILED", publication_error=str(error))
                raise
            current = None
            if result["status"] == "FAILED":
                raise ValueError("stop after failed record")
        if source_snapshot(repo) != source:
            raise ValueError("final source drift")
        _publish(output/"source-verification.json", dict(source=source, matched=True))
    except Exception as error:
        failure = dict(type=type(error).__name__, message=str(error), current=current)
        _publish(output/"failure.json", failure)
    summary = summarize(rows, planned, records, failure)
    _publish(output/"summary.json", summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registered-commit", required=True)
    args = parser.parse_args()
    result = run_pilot(Path(__file__).resolve().parents[1], args.registered_commit)
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(result["execution_status"] == "FAILED")
