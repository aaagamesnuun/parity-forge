"""Small, immutable exploratory pilot; no production census or legacy mutation.

Run from the repository root: PYTHONPATH=src python3 -m scripts.plan0016_pilot run
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Dict, List

from parity_forge.dsl import canonical_json, definition_hash, describe_rules, parse_definition
from parity_forge.engine import replay_dicts
from parity_forge.symmetry import D4_TRANSFORMS, transform_definition

from scripts.plan0016_play import PilotPlayError, play_one, summarize_games
from scripts.plan0016_selection import select_pilot


PROTOCOL = "plan0016-exploratory-pilot-v1"
POLICIES = ((0, 0), (1, 1), (2, 2), (2, 1), (1, 2))
PLAN = "docs/plans/active/0016-small-exploratory-game-pilot.md"
REPORT = ("experiments/runs/plan0015-factorized-static-census-evidence-v1/"
          "stages/plan0015-factorized-static-census-stage-v1/static-census-report.json")
OUTPUT = "experiments/runs/plan0016-exploratory-pilot-v1"
MAX_ARTIFACT_BYTES = 64 * 1024 * 1024


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def publish_bytes(path: Path, raw: bytes) -> None:
    """Atomically publish once; an existing destination is never replaced."""
    if len(raw) > MAX_ARTIFACT_BYTES:
        raise ValueError("artifact exceeds pilot byte ceiling")
    descriptor, temporary = tempfile.mkstemp(prefix=".pending-", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
        directory = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        os.unlink(temporary)


def publish_json(path: Path, value: Any) -> None:
    publish_bytes(path, canonical_bytes({"payload": value, "sha256": _digest(value)}))


def read_json(path: Path) -> Any:
    with path.open("rb") as stream:
        raw = stream.read(MAX_ARTIFACT_BYTES + 1)
    if len(raw) > MAX_ARTIFACT_BYTES:
        raise ValueError("artifact exceeds pilot byte ceiling")
    envelope = json.loads(raw)
    if (type(envelope) is not dict or set(envelope) != {"payload", "sha256"}
            or canonical_bytes(envelope) != raw
            or _digest(envelope["payload"]) != envelope["sha256"]):
        raise ValueError("pilot artifact digest or canonical bytes changed")
    return envelope["payload"]


def source_snapshot(repository: Path) -> Dict[str, Any]:
    def git(*args: str) -> str:
        return subprocess.check_output(("git", "-C", str(repository), *args), text=True).strip()
    if git("diff", "--name-only", "HEAD", "--", "src", "research", "scripts", "tests", PLAN):
        raise ValueError("commit implementation and plan before pilot execution")
    if git("ls-files", "--others", "--exclude-standard", "--", "src", "research", "scripts", "tests"):
        raise ValueError("untracked implementation files before pilot execution")
    paths = git("ls-files", "--", "src", "research", "scripts", "tests", PLAN).splitlines()
    return {"git_commit": git("rev-parse", "HEAD"),
            "source_sha256": {path: hashlib.sha256((repository / path).read_bytes()).hexdigest()
                              for path in paths if path.endswith(".py") or path == PLAN}}


def make_manifest(selection: Dict[str, Any], source: Dict[str, Any]) -> Dict[str, Any]:
    """Materialize the entire bounded schedule before a single game is played."""
    if len(selection["selected"]) > 24:
        raise ValueError("pilot carrier ceiling exceeded")
    definitions: Dict[str, Any] = {}
    schedule: List[Dict[str, Any]] = []
    for carrier_index, carrier in enumerate(selection["selected"]):
        bases = carrier["definitions"]
        if len(bases) != 2 or [d["first_player"] for d in bases] != ["A", "B"]:
            raise ValueError("expected separate A-first/B-first definitions")
        for base in bases:
            definition = parse_definition(base)
            if (definition.schema_version, definition.board_size, definition.max_plies) != (4, 3, 18):
                raise ValueError("selected definition escaped the registered envelope")
            if json.loads(canonical_json(definition)) != base:
                raise ValueError("selected definition is not canonical")
            for orientation in D4_TRANSFORMS:
                oriented = transform_definition(definition, orientation)
                identity = definition_hash(oriented)
                definitions[identity] = json.loads(canonical_json(oriented))
                for seed in (0, 1):
                    for policy_a, policy_b in POLICIES:
                        schedule.append({"ordinal": len(schedule), "carrier_index": carrier_index,
                                         "carrier_id": carrier["carrier_id"],
                                         "first_player": base["first_player"],
                                         "orientation": orientation, "seed": seed,
                                         "policy_a": policy_a, "policy_b": policy_b,
                                         "definition_hash": identity})
    return {"protocol_id": PROTOCOL, "source": source, "selection": selection,
            "definitions": definitions, "schedule": schedule,
            "max_nodes_per_role_game": 5000,
            "acceptance": "PROVISIONAL_UNTIL_FULL_REGRESSION"}


def summarize_run(manifest: Dict[str, Any], records: List[Dict[str, Any]]) -> Dict[str, Any]:
    if manifest["protocol_id"] == PROTOCOL:
        if manifest != make_manifest(manifest["selection"], manifest["source"]):
            raise ValueError("manifest differs from the registered schedule")
    elif manifest["protocol_id"] != "CALIBRATION_ONLY":
        raise ValueError("unknown pilot protocol")
    schedule = manifest["schedule"]
    if len(records) > len(schedule):
        raise ValueError("too many game records")
    for ordinal, record in enumerate(records):
        if record["scheduled"] != schedule[ordinal]:
            raise ValueError("record is not the manifest's exact ordered prefix")
        game = record["game"]
        for key in ("definition_hash", "first_player", "policy_a", "policy_b", "seed"):
            if game[key] != schedule[ordinal][key]:
                raise ValueError("record condition differs from the manifest")
    conditions = []
    for carrier_index, carrier in enumerate(manifest["selection"]["selected"]):
        for first in ("A", "B"):
            planned = [s for s in schedule if s["carrier_index"] == carrier_index and s["first_player"] == first]
            rows = [r for r in records if r["scheduled"]["carrier_index"] == carrier_index
                    and r["scheduled"]["first_player"] == first]
            profiles = []
            for pa, pb in POLICIES:
                subgroup = [r for r in rows if (r["game"]["policy_a"], r["game"]["policy_b"]) == (pa, pb)]
                profile = {"policy_a": pa, "policy_b": pb,
                           "summary": summarize_games([r["game"] for r in subgroup], 16),
                           "orientations": []}
                for orientation in D4_TRANSFORMS:
                    games = [r["game"] for r in subgroup if r["scheduled"]["orientation"] == orientation]
                    profile["orientations"].append({"orientation": orientation,
                                                    "summary": summarize_games(games, 2)})
                profiles.append(profile)
            complete = len(rows) == len(planned) == 80 and all(r["game"]["status"] == "COMPLETE" for r in rows)
            both = all(min(p["summary"]["a_wins"], p["summary"]["b_wins"]) > 0
                       for p in profiles if (p["policy_a"], p["policy_b"]) in ((1, 1), (2, 2)))
            conditions.append({"carrier_index": carrier_index, "carrier_id": carrier["carrier_id"],
                               "first_player": first, "planned_games": len(planned),
                               "status": "FURTHER_DIAGNOSIS" if complete and both else "OBSERVATIONS_ONLY",
                               "profiles": profiles})
    statuses = Counter(r["game"]["status"] for r in records)
    return {"protocol_id": PROTOCOL, "acceptance": manifest["acceptance"],
            "execution_status": "FAILED" if statuses["FAILED"] else (
                "SCHEDULE_COMPLETE" if len(records) == len(schedule) else "INCOMPLETE"),
            "planned_games": len(schedule), "complete_games": statuses["COMPLETE"],
            "censored_games": statuses["SEARCH_CENSORED"], "failed_games": statuses["FAILED"],
            "not_started_games": len(schedule) - len(records), "conditions": conditions,
            "further_diagnosis_count": sum(c["status"] == "FURTHER_DIAGNOSIS" for c in conditions),
            "claims": {"fair_game": False, "human_skill_calibrated": False, "confirmation": False}}


def render_report(manifest: Dict[str, Any], summary: Dict[str, Any]) -> str:
    lines = ["# Plan 0016 — 小規模ゲーム探索", "",
             "コード・結果の正式受入れは全回帰テスト通過後です。公平性・面白さの認定ではありません。", "",
             "- 選定: {} carrier / 最大24。空枠は補充していません。".format(len(manifest["selection"]["selected"])),
             "- 予定{}局、完了{}局、計算打切り{}局、失敗{}局、未実施{}局。".format(
                 summary["planned_games"], summary["complete_games"], summary["censored_games"],
                 summary["failed_games"], summary["not_started_games"]),
             "- 追加診断対象: {}先手固定条件。これは合格ゲーム数ではありません。".format(summary["further_diagnosis_count"]),
             "", "全条件・全向きの結果は [summary.json](summary.json)、選択理由と予定表は [manifest.json](manifest.json) に保存。",
             "向き・seedは独立標本とみなさず、先手の異なる結果は合算しません。", ""]
    flagged = [c for c in summary["conditions"] if c["status"] == "FURTHER_DIAGNOSIS"]
    examples = flagged if flagged else summary["conditions"]
    seen = set()
    for condition in examples:
        if condition["carrier_index"] in seen:
            continue
        seen.add(condition["carrier_index"])
        carrier = manifest["selection"]["selected"][condition["carrier_index"]]
        base = next(d for d in carrier["definitions"] if d["first_player"] == condition["first_player"])
        board = [["·"] * 3 for _ in range(3)]
        for piece in base["initial_pieces"]:
            row, column = piece["position"]
            board[row][column] = piece["owner"]
        lines += ["## 例{} — {}先手 / {}".format(len(seen), condition["first_player"], condition["status"]),
                  "", "```text", *[" ".join(row) for row in board], "```", "",
                  "DSL由来の完全ルール（既存説明器の英語原文）:", ""]
        lines += ["- " + rule for rule in describe_rules(parse_definition(base))]
        lines += ["", "| A深さ/B深さ（0=random） | A勝 | B勝 | 引分 | 計算打切り | 完了 |",
                  "| --- | ---: | ---: | ---: | ---: | ---: |"]
        for profile in condition["profiles"]:
            value = profile["summary"]
            lines.append("| {}/{} | {} | {} | {} | {} | {} |".format(profile["policy_a"], profile["policy_b"],
                         value["a_wins"], value["b_wins"], value["draws"],
                         value["search_censored"], value["completed"]))
        lines.append("")
        if len(seen) == 3:
            break
    return "\n".join(lines) + "\n"


def execute_manifest(output: Path, manifest: Dict[str, Any]) -> Dict[str, Any]:
    output.mkdir(exist_ok=False)
    (output / "games").mkdir()
    publish_json(output / "manifest.json", manifest)
    records = []
    for scheduled in manifest["schedule"]:
        try:
            game = play_one(manifest["definitions"][scheduled["definition_hash"]],
                            scheduled["policy_a"], scheduled["policy_b"], scheduled["seed"],
                            manifest["max_nodes_per_role_game"])
        except PilotPlayError as error:
            game = error.partial_record
        record = {"scheduled": scheduled, "game": game}
        publish_json(output / "games" / "{:04d}.json".format(scheduled["ordinal"]), record)
        records.append(record)
        if game["status"] == "FAILED":
            break
        if len(records) % 100 == 0:
            print("recorded {}/{} games".format(len(records), len(manifest["schedule"])), flush=True)
    summary = summarize_run(manifest, records)
    publish_json(output / "summary.json", summary)
    publish_bytes(output / "report.md", render_report(manifest, summary).encode("utf-8"))
    return summary


def inspect_run(output: Path) -> Dict[str, Any]:
    """Read/replay a preserved prefix; never select, resume, or play again."""
    manifest = read_json(output / "manifest.json")
    paths = sorted((output / "games").glob("*.json"))
    if [path.name for path in paths] != ["{:04d}.json".format(i) for i in range(len(paths))]:
        raise ValueError("saved game records are not an unbroken ordinal prefix")
    records = [read_json(path) for path in paths]
    summary = summarize_run(manifest, records)
    for row in records:
        game, scheduled = row["game"], row["scheduled"]
        definition = parse_definition(manifest["definitions"][scheduled["definition_hash"]])
        if definition_hash(definition) != scheduled["definition_hash"]:
            raise ValueError("saved definition identity changed")
        state = replay_dicts(definition, game["actions"])
        if state.ply != game["plies"]:
            raise ValueError("saved prefix length changed")
        if game["status"] != "FAILED" and state.to_dict() != game["state_after_prefix"]:
            raise ValueError("saved state is not the replayed prefix")
        if game["status"] == "COMPLETE":
            if not state.terminal or state.outcome.reason != game["terminal_reason"]:
                raise ValueError("saved completed terminal differs from replay")
            winner = state.outcome.winner.value if state.outcome.winner else None
            if winner != game["winner"]:
                raise ValueError("saved winner differs from replay")
        elif game["status"] == "SEARCH_CENSORED" and state.terminal:
            raise ValueError("saved censor has a terminal prefix")
    if (output / "summary.json").exists() and read_json(output / "summary.json") != summary:
        raise ValueError("saved summary does not reconstruct from game records")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "inspect"))
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    output = repository / OUTPUT
    if args.command == "inspect":
        summary = inspect_run(output)
        print(json.dumps({k: v for k, v in summary.items() if k != "conditions"}, sort_keys=True))
        return
    if output.exists():
        raise FileExistsError("existing pilot remains immutable; do not repeat it")
    source = source_snapshot(repository)
    selection = select_pilot((repository / REPORT).read_bytes())
    manifest = make_manifest(selection, source)
    if source_snapshot(repository) != source:
        raise ValueError("source changed during selection")
    summary = execute_manifest(output, manifest)
    if source_snapshot(repository) != source:
        raise ValueError("source changed during gameplay; results remain provisional")
    publish_json(output / "source-verification.json", {"source": source, "matched_after_execution": True})
    print(json.dumps({k: v for k, v in summary.items() if k != "conditions"}, sort_keys=True))


if __name__ == "__main__":
    main()
