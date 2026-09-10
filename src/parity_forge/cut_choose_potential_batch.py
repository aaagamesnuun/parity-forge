"""Pinned cut-potential diagnostic; frozen Plan34 records are never reused."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import re
import sys
import time

from .cut_choose import (definition_hash, definition_to_dict, original_definition,
                         parse_definition)
from .cut_choose_search import BudgetExceeded
from .cut_choose_potential import solve, verify_proof
from .cut_choose_batch import (
    _keys, load_manifest, _digest, _integer, _json, _write, _utc, _git_provenance,
)


FORMAT = "parity-forge:cut-choose-potential-experiment:v1"
REPOSITORY = Path(__file__).resolve().parents[2]
SOURCE_CHAT = "experiments/proposals/plan0033-cut-choose-chat-source.json"
SOURCE_PATHS = tuple("src/parity_forge/" + name + ".py" for name in
                     ("cut_choose", "cut_choose_search", "cut_choose_batch",
                      "cut_choose_potential", "cut_choose_potential_batch")) + (
    "tests/test_cut_choose_potential.py", "tests/test_cut_choose_potential_batch.py")
RESULT_KEYS = {"status", "winner", "reason", "nodes", "transitions", "proof_arcs",
               "proof", "cut_count", "potential_checks", "potential_leaves"}


def source_hashes(repo_root=REPOSITORY):
    return {path: _digest(Path(repo_root) / path) for path in SOURCE_PATHS}


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


def _validate_result(result, limits):
    _keys(result, RESULT_KEYS)
    for name in ("nodes", "transitions", "proof_arcs"):
        _integer(result[name], 0, limits[name])
    _integer(result["cut_count"], 0, 1024)
    _integer(result["potential_checks"], 0, result["nodes"])
    _integer(result["potential_leaves"], 0, result["potential_checks"])
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
              "nodes": 0, "transitions": 0, "proof_arcs": 0, "proof": None,
              "cut_count": 0, "potential_checks": 0, "potential_leaves": 0}
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
