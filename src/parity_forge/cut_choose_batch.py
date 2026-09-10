"""One immutable, pinned diagnostic for the original cut-and-choose game."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import re
import subprocess
import sys
import time

from .cut_choose import (definition_hash, definition_to_dict, original_definition,
                         parse_definition)
from .cut_choose_search import BudgetExceeded, solve, verify_proof


FORMAT = "parity-forge:cut-choose-experiment:v1"
REPOSITORY = Path(__file__).resolve().parents[2]
SOURCE_CHAT = "experiments/proposals/plan0033-cut-choose-chat-source.json"
SOURCE_PATHS = tuple("src/parity_forge/" + name + ".py" for name in
                     ("cut_choose", "cut_choose_search", "cut_choose_batch")) + tuple(
    "tests/test_" + name + ".py" for name in
    ("cut_choose", "cut_choose_search", "cut_choose_batch"))
RESULT_KEYS = {"status", "winner", "reason", "nodes", "transitions", "proof_arcs", "proof"}


def _keys(value, expected):
    if type(value) is not dict or set(value) != set(expected):
        raise ValueError("unexpected object keys")


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


def _constant(value):
    raise ValueError("non-finite JSON constant: " + value)


def load_manifest(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(65537)
    if len(raw) > 65536:
        raise ValueError("manifest exceeds 64 KiB")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_object,
                      parse_constant=_constant)


def _digest(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def source_hashes(repo_root=REPOSITORY):
    return {path: _digest(Path(repo_root) / path) for path in SOURCE_PATHS}


def _integer(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("invalid integer resource limit")


def _pins(manifest, repo_root):
    if manifest["source_pins"] != source_hashes(repo_root):
        raise ValueError("source pin drift")
    if manifest["source_chat_sha256"] != _digest(Path(repo_root) / SOURCE_CHAT):
        raise ValueError("source chat drift")


def validate_manifest(manifest, repo_root=REPOSITORY):
    _keys(manifest, ("format", "id", "definition", "definition_sha256",
                     "source_chat_sha256", "source_pins", "query", "limits"))
    if manifest["format"] != FORMAT or manifest["query"] != "EXACT_INITIAL_WINNER":
        raise ValueError("unsupported experiment format or query")
    if (type(manifest["id"]) is not str or
            not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,79}", manifest["id"])):
        raise ValueError("unsafe run id")
    definition = parse_definition(manifest["definition"])
    original = original_definition()
    if (manifest["definition"] != definition_to_dict(original) or
            definition_hash(definition) != definition_hash(original)):
        raise ValueError("only the unchanged original definition is admitted")
    if manifest["definition_sha256"] != definition_hash(definition):
        raise ValueError("definition hash mismatch")
    _keys(manifest["source_pins"], SOURCE_PATHS)
    for value in list(manifest["source_pins"].values()) + [manifest["source_chat_sha256"]]:
        if type(value) is not str or not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ValueError("invalid SHA256 pin")
    limits = manifest["limits"]
    _keys(limits, ("nodes", "transitions", "proof_arcs", "cpu_seconds", "output_bytes"))
    for name, high in (("nodes", 300000), ("transitions", 6000000),
                       ("proof_arcs", 1000000)):
        _integer(limits[name], 0, high)
    _integer(limits["output_bytes"], 4096, 16777216)
    cpu = limits["cpu_seconds"]
    if type(cpu) not in (int, float) or not math.isfinite(cpu) or not 0 < cpu <= 1800:
        raise ValueError("invalid CPU limit")
    _pins(manifest, repo_root)
    return definition


def _json(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def _write(path, payload):
    with Path(path).open("xb") as stream:
        stream.write(payload)


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _git_provenance(repo_root):
    def git(*args):
        return subprocess.check_output(["git", "-C", str(repo_root), *args],
                                       stderr=subprocess.PIPE).decode("utf-8").strip()
    return {"head": git("rev-parse", "HEAD"),
            "dirty": bool(git("status", "--porcelain", "--untracked-files=all"))}


def _validate_result(result, limits):
    _keys(result, RESULT_KEYS)
    for name in ("nodes", "transitions", "proof_arcs"):
        _integer(result[name], 0, limits[name])
    if result["status"] == "COMPLETE":
        if (result["winner"] not in ("A", "B") or result["reason"] != "PROVED" or
                type(result["proof"]) is not dict):
            raise ValueError("invalid complete solver result")
    elif result["status"] == "UNKNOWN":
        if (result["winner"] is not None or result["proof"] is not None or
                result["reason"] not in ("NODE_LIMIT", "TRANSITION_LIMIT",
                                          "PROOF_ARC_LIMIT", "CPU_LIMIT")):
            raise ValueError("invalid unknown solver result")
    else:
        raise ValueError("invalid solver status")


def _unknown(result, reason):
    return dict(result, status="UNKNOWN", winner=None, proof=None, reason=reason)


def run(manifest_path, output_root, *, repo_root=REPOSITORY):
    """Claim exactly once; an exception or interruption never releases the claim."""
    started = time.process_time()
    manifest = load_manifest(manifest_path)
    definition = validate_manifest(manifest, repo_root)
    limits = manifest["limits"]
    deadline = started + limits["cpu_seconds"]
    directory = Path(output_root) / manifest["id"]
    directory.mkdir(parents=True, exist_ok=True)
    claim = _json({"id": manifest["id"], "claimed_at": _utc()})
    _write(directory / "claim.json", claim)
    result = {"status": "UNKNOWN", "winner": None, "reason": "CPU_LIMIT",
              "nodes": 0, "transitions": 0, "proof_arcs": 0, "proof": None}
    try:
        registration = _json({"manifest": manifest, "registered_at": _utc(),
                              "git": _git_provenance(repo_root),
                              "python": sys.version, "platform": platform.platform()})
        _write(directory / "registration.json", registration)
        remaining = deadline - time.process_time()
        if remaining > 0:
            result = solve(definition, node_limit=limits["nodes"],
                           transition_limit=limits["transitions"],
                           proof_arc_limit=limits["proof_arcs"],
                           cpu_seconds=remaining)
            _validate_result(result, limits)
        check = None
        if result["status"] == "COMPLETE":
            remaining = deadline - time.process_time()
            if remaining <= 0:
                result = _unknown(result, "CPU_LIMIT")
            else:
                try:
                    check = verify_proof(definition, result["proof"],
                                         arc_limit=limits["proof_arcs"], cpu_seconds=remaining)
                except BudgetExceeded as exc:
                    result = _unknown(result, exc.reason)
                else:
                    if check.get("status") != "PASS" or check.get("winner") != result["winner"]:
                        raise ValueError("independent proof checker did not confirm winner")
        _pins(manifest, repo_root)
        payload = _json(result)
        if result["status"] == "COMPLETE" and time.process_time() >= deadline:
            result = _unknown(result, "CPU_LIMIT")
            check, payload = None, _json(result)

        def receipt_for(data):
            digest = hashlib.sha256(data).hexdigest()
            return _json({"completed_at": _utc(), "cpu_seconds": time.process_time() - started,
                          "result_sha256": digest,
                          "proof_check": check, "source_pins_verified": True})

        receipt = receipt_for(payload)
        if result["status"] == "COMPLETE" and time.process_time() >= deadline:
            result = _unknown(result, "CPU_LIMIT")
            check, payload = None, _json(result)
            receipt = receipt_for(payload)
        if len(claim) + len(registration) + len(payload) + len(receipt) > limits["output_bytes"]:
            if result["status"] == "COMPLETE":
                result = _unknown(result, "RESULT_BYTE_LIMIT")
            check, payload = None, _json(result)
            receipt = receipt_for(payload)
        if len(claim) + len(registration) + len(payload) + len(receipt) > limits["output_bytes"]:
            raise ValueError("output ceiling cannot hold registration and minimal result")
        _write(directory / "result.json", payload)
        _write(directory / "receipt.json", receipt)
        return result
    except Exception as exc:
        _write(directory / "failure.json", _json({"failed_at": _utc(),
               "exception": type(exc).__name__, "message": str(exc)[:1000],
               "cpu_seconds": time.process_time() - started}))
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        result = run(args.manifest, args.output)
    except Exception as exc:
        print(type(exc).__name__ + ": " + str(exc), file=sys.stderr)
        return 1
    print(json.dumps({key: result[key] for key in ("status", "winner", "reason")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
