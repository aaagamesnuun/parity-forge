"""Fail-closed filesystem runners for the capture vector-boundary replication.

Scientific selection and evaluation deliberately live in
``capture_boundary`` and ``capture_boundary_evaluation``.  This module owns the
irreversible boundary: pinned historical bytes, Git ancestry, canonical paths,
one-shot reservations, immutable attempts/runs/failures, and stage ordering.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import platform
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Sequence, Tuple

from . import __version__
from .batch import PlayGates
from .capture_boundary import (
    BOUNDARY_MANIFEST_ID,
    build_capture_boundary_manifest,
    project_boundary_exclusion_sources,
    validate_capture_boundary_manifest,
)
from .capture_boundary_evaluation import (
    evaluate_capture_boundary_depth5,
    evaluate_capture_boundary_exact,
    validate_capture_boundary_depth5_result,
    validate_capture_boundary_exact_result,
)
from .experiments import _timestamp, _utc_now
from .landscape_experiments import (
    _assert_no_outcome_keys,
    _encoded_json,
    _frozen_source_fingerprints_at_commit,
    _read_json_bytes,
    _recorded_repository_root,
    _require_canonical_path as _base_require_canonical_path,
    _require_clean_repository,
    _require_commit_ancestor,
    _require_timestamp,
    _require_tracked,
    _reserve_protocol,
    _scan_prior_protocol,
    _validate_completed_run_attempt,
    _validate_protocol_reservation,
    _write_exclusive,
    _write_failure,
)


CAPTURE_BOUNDARY_MANIFEST_PROTOCOL_ID = "capture-boundary-v1-manifest-freeze"
CAPTURE_BOUNDARY_EXACT_PROTOCOL_ID = "capture-boundary-v1-paired-exact"
CAPTURE_BOUNDARY_DEPTH5_PROTOCOL_ID = "capture-boundary-v1-fixed-depth5"

CAPTURE_BOUNDARY_CORPUS_RELATIVE = Path(
    "experiments/corpora/capture-boundary-v1"
)
CAPTURE_BOUNDARY_MANIFEST_RESERVATION_RELATIVE = (
    CAPTURE_BOUNDARY_CORPUS_RELATIVE / "manifest-reservation.json"
)
CAPTURE_BOUNDARY_MANIFEST_ATTEMPT_RELATIVE = (
    CAPTURE_BOUNDARY_CORPUS_RELATIVE / "manifest-attempt.json"
)
CAPTURE_BOUNDARY_EXCLUSION_LEDGER_RELATIVE = (
    CAPTURE_BOUNDARY_CORPUS_RELATIVE / "exclusion-ledger.json"
)
CAPTURE_BOUNDARY_MANIFEST_RELATIVE = (
    CAPTURE_BOUNDARY_CORPUS_RELATIVE / "manifest.json"
)
CAPTURE_BOUNDARY_LOCK_RELATIVE = (
    CAPTURE_BOUNDARY_CORPUS_RELATIVE / "manifest.lock.json"
)

CAPTURE_BOUNDARY_PAIR_COUNT = 64
CAPTURE_BOUNDARY_EXACT_MAX_STATES = 100_000
CAPTURE_BOUNDARY_STRUCTURAL_STATE_BOUND = 43_776
CAPTURE_BOUNDARY_DEPTH5_SEEDS = tuple(range(30))
CAPTURE_BOUNDARY_DEPTH5_DEPTH = 5
CAPTURE_BOUNDARY_DEPTH5_MAX_NODES = 5_000_000

CAPTURE_BOUNDARY_EVALUATED_CUTOFF_COMMIT = (
    "034759a0f8072db7462b009b3f160ec176212fd1"
)
CAPTURE_BOUNDARY_EVALUATED_RUN_COUNT = 16
CAPTURE_BOUNDARY_EVALUATED_REGISTRY_ROOT = (
    "e85f0360182efcfcb7abf90fccafba912c440c8923883b1362031006724828a7"
)
_REGISTRY_DOMAIN = b"capture-boundary-v1-evaluated-run-registry-v1\0"

_PROTOCOL_PLAN_RELATIVE = Path(
    "docs/plans/active/0009-fresh-capture-vector-boundary-replication.md"
)
_FROZEN_PROTOCOL_RELATIVES = (_PROTOCOL_PLAN_RELATIVE,)
_FROZEN_EXECUTABLE_RELATIVES = (
    Path("src/parity_forge/__init__.py"),
    Path("src/parity_forge/__main__.py"),
    Path("src/parity_forge/agents.py"),
    Path("src/parity_forge/analysis.py"),
    Path("src/parity_forge/asymmetry.py"),
    Path("src/parity_forge/audit.py"),
    Path("src/parity_forge/batch.py"),
    Path("src/parity_forge/capture.py"),
    Path("src/parity_forge/capture_boundary.py"),
    Path("src/parity_forge/capture_boundary_evaluation.py"),
    Path("src/parity_forge/capture_boundary_experiments.py"),
    Path("src/parity_forge/dsl.py"),
    Path("src/parity_forge/engine.py"),
    Path("src/parity_forge/experiments.py"),
    Path("src/parity_forge/generator.py"),
    Path("src/parity_forge/landscape.py"),
    Path("src/parity_forge/landscape_evaluation.py"),
    Path("src/parity_forge/landscape_experiments.py"),
    Path("src/parity_forge/play.py"),
    Path("src/parity_forge/simplicity.py"),
    Path("src/parity_forge/solver.py"),
    Path("src/parity_forge/symmetry.py"),
)

_PINNED_EXCLUSION_SPECS = (
    {
        "label": "generator-v1-development",
        "path": Path(
            "experiments/runs/20260830T154155824053Z-batch-g20260831/run.json"
        ),
        "sha256": "b664e133cda42b494d7222735999f0d7b490d9e0108e13743cef8dd20824bb97",
        "identity_key": "run_id",
        "identity": "20260830T154155824053Z-batch-g20260831",
        "experiment_type": "structured-random-generation-screening",
        "status": "COMPLETED",
    },
    {
        "label": "generator-v2-development",
        "path": Path(
            "experiments/runs/20260830T154309225370Z-batch-g20260831/run.json"
        ),
        "sha256": "374bfc58030f0acce32a3edd7ff3d10764fb001d130eda4b1da086550b7cb0f5",
        "identity_key": "run_id",
        "identity": "20260830T154309225370Z-batch-g20260831",
        "experiment_type": "structured-random-generation-screening",
        "status": "COMPLETED",
    },
    {
        "label": "generator-v2-heldout-20260901",
        "path": Path(
            "experiments/runs/20260830T184008717197Z-strong-g20260901/run.json"
        ),
        "sha256": "cdf26f22c93a95f70e413e28257a6afddfaecf21008507a6557e019f2c5357dc",
        "identity_key": "run_id",
        "identity": "20260830T184008717197Z-strong-g20260901",
        "experiment_type": "strong-cascade-held-out-generation",
        "status": "COMPLETED",
    },
    {
        "label": "landscape-v1-manifest",
        "path": Path("experiments/corpora/landscape-v1/manifest.json"),
        "sha256": "f407aefb5fdb8c926db282ff90d2feb1a8666cda3fdbd6925b9f5cc07abd87b1",
        "identity_key": "manifest_id",
        "identity": "generator-v2-3x3-landscape-v1",
        "experiment_type": None,
        "status": "FROZEN",
    },
)

_PLAN0008_CHAIN_SPECS = (
    {
        "label": "Plan 0008 manifest reservation",
        "path": Path("experiments/corpora/capture-v1/manifest-reservation.json"),
        "sha256": "3f67d49fe50e2c6897a689c9c3b9bd8bfbd1154c961a6e49b4608aa7fd7c2cbe",
    },
    {
        "label": "Plan 0008 manifest attempt",
        "path": Path("experiments/corpora/capture-v1/manifest-attempt.json"),
        "sha256": "5f65911bc875495b81f5a9032c1ea218d7214402eb40f8ac814a54861b197c8f",
    },
    {
        "label": "Plan 0008 outcome-free manifest",
        "path": Path("experiments/corpora/capture-v1/manifest.json"),
        "sha256": "6bc466453f60bc4ae2a6401fc76a77eebe4a7ebee82111e53ac4463400588f4f",
    },
    {
        "label": "Plan 0008 manifest lock",
        "path": Path("experiments/corpora/capture-v1/manifest.lock.json"),
        "sha256": "496a87ac1f169d7d6b19c29bf176a7af6f11ddc481578fcdab889b46f79b429f",
    },
)

_SUPPORTING_DEPENDENCY_SPECS = (
    {
        "label": "frozen static corpus",
        "path": Path("experiments/corpora/static-v1/corpus.json"),
        "sha256": "4ad81a4019f072a6f47d88e86f1761c0f55ef792f647d1348d292085496ce208",
        "identity_kind": "corpus_id",
        "identity": "static-v1-2026-08-31",
        "protocol_id": None,
        "status": None,
        "frozen": True,
    },
    {
        "label": "frozen stalemate manifest",
        "path": Path("experiments/corpora/stalemate-v1/manifest.json"),
        "sha256": "ed9a9b93ad234f4375ded0e135f5436c82fb127988784a86aa33ab4f776ff176",
        "identity_kind": "manifest_id",
        "identity": "generator-v2-3x3-stalemate-paired-v1",
        "protocol_id": "stalemate-v1-paired-manifest-freeze",
        "status": None,
        "frozen": None,
    },
    {
        "label": "frozen capture manifest",
        "path": Path("experiments/corpora/capture-v1/manifest.json"),
        "sha256": "6bc466453f60bc4ae2a6401fc76a77eebe4a7ebee82111e53ac4463400588f4f",
        "identity_kind": "manifest_id",
        "identity": "generator-v2-3x3-capture-paired-v1",
        "protocol_id": "capture-v1-paired-manifest-freeze",
        "status": "FROZEN",
        "frozen": None,
    },
)

_MANIFEST_COMPONENT_VERSIONS = {
    "parity_forge": __version__,
    "baseline_dsl_schema": 1,
    "treatment_dsl_schema": 3,
    "d4_canonicalization": 1,
    "capture_boundary_selection": 1,
    "evaluated_orbit_exclusion": 1,
}
_EXACT_COMPONENT_VERSIONS = {
    "parity_forge": __version__,
    "baseline_dsl_schema": 1,
    "treatment_dsl_schema": 3,
    "engine": 3,
    "exact_solver": 1,
    "capture_boundary_exact": 1,
}
_DEPTH5_COMPONENT_VERSIONS = {
    "parity_forge": __version__,
    "baseline_dsl_schema": 1,
    "treatment_dsl_schema": 3,
    "engine": 3,
    "play_evaluator": 1,
    "minimax_agent": 1,
    "capture_boundary_depth5": 1,
}

_ATTEMPT_KEYS = {
    "run_id",
    "protocol_id",
    "experiment_type",
    "status",
    "started_at",
    "git_commit",
    "git_dirty",
    "environment",
    "component_versions",
    "configuration",
}
_NARRATIVE_KEYS = {
    "hypothesis",
    "baseline",
    "treatment",
    "expected_result",
    "actual_result",
    "interpretation",
    "decision",
}
_COMPLETED_RUN_KEYS = _ATTEMPT_KEYS | _NARRATIVE_KEYS | {
    "completed_at",
    "results",
}

def _sha256(source_bytes: bytes) -> str:
    return hashlib.sha256(source_bytes).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _canonical_equal(left: Any, right: Any) -> bool:
    """Compare JSON values without Python's ``True == 1`` coercion."""
    try:
        return _canonical_json(left) == _canonical_json(right)
    except (TypeError, ValueError) as error:
        raise ValueError("evidence must be canonical-JSON compatible") from error


def _record_failure_preserving_original(
    path: Path,
    attempt: Mapping[str, Any],
    phase: str,
    error: BaseException,
) -> None:
    try:
        _write_failure(path, attempt, phase, error)
    except BaseException as evidence_error:
        raise RuntimeError(
            "{} failed and its failure evidence could not be written: {}".format(
                phase, evidence_error
            )
        ) from error


def _require_no_symlink_below(
    path: Path, anchor: Path, label: str
) -> None:
    """Reject symlinks below a trusted root while allowing outer OS aliases."""

    logical_anchor = Path(os.path.abspath(str(anchor)))
    logical_path = Path(os.path.abspath(str(path)))
    try:
        relative = logical_path.relative_to(logical_anchor)
    except ValueError as error:
        raise ValueError("{} must remain below its trusted root".format(label)) from error
    current = anchor.resolve()
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("{} cannot contain an internal symlink".format(label))


def _require_canonical_path(
    path: Path, repository: Path, relative: Path, label: str
) -> None:
    _base_require_canonical_path(path, repository, relative, label)
    _require_no_symlink_below(repository / relative, repository, label)


def _chain_hashes(
    paths: Sequence[Path], *, anchor: Path | None = None
) -> Mapping[str, str]:
    hashes: Dict[str, str] = {}
    for path in paths:
        if anchor is not None:
            _require_no_symlink_below(path, anchor, "evidence chain")
        if path.is_symlink():
            raise ValueError("evidence chain cannot contain a symlink")
        try:
            hashes[str(path.resolve())] = _sha256(path.read_bytes())
        except OSError as error:
            raise ValueError(
                "evidence chain file is unreadable: {}".format(path)
            ) from error
    return hashes


def _require_chain_unchanged(hashes: Mapping[str, str]) -> None:
    for absolute, expected in hashes.items():
        path = Path(absolute)
        if path.is_symlink() or path.resolve() != path:
            raise ValueError("evidence chain path changed during evaluation")
        try:
            observed = _sha256(path.read_bytes())
        except OSError as error:
            raise ValueError("evidence chain file disappeared") from error
        if observed != expected:
            raise ValueError("evidence chain bytes changed during evaluation")


def _exact_byte_hashes(
    entries: Sequence[Tuple[Path, bytes]], label: str, *, anchor: Path | None = None
) -> Mapping[str, str]:
    """Authenticate current bytes against constructed evidence, then snapshot."""

    hashes: Dict[str, str] = {}
    for path, expected_bytes in entries:
        if anchor is not None:
            _require_no_symlink_below(path, anchor, label)
        if path.is_symlink():
            raise ValueError("{} cannot contain a symlink".format(label))
        try:
            observed_bytes = path.read_bytes()
        except OSError as error:
            raise ValueError("{} is unreadable: {}".format(label, path)) from error
        if observed_bytes != expected_bytes:
            raise ValueError("{} bytes do not match constructed evidence".format(label))
        hashes[str(path.resolve())] = _sha256(expected_bytes)
    return hashes


def _authenticated_frozen_worktree_hashes(
    repository: Path, commit: str
) -> Mapping[str, str]:
    """Bind current protocol/executable bytes directly to their commit blobs."""

    for relative in (*_FROZEN_PROTOCOL_RELATIVES, *_FROZEN_EXECUTABLE_RELATIVES):
        path = repository / relative
        _require_canonical_path(path, repository, relative, "frozen worktree source")
        _require_tracked(path, repository, "frozen worktree source")
    expected = {
        **_frozen_source_fingerprints_at_commit(
            repository, commit, _FROZEN_PROTOCOL_RELATIVES
        ),
        **_frozen_source_fingerprints_at_commit(
            repository, commit, _FROZEN_EXECUTABLE_RELATIVES
        ),
    }
    observed = _chain_hashes(
        _frozen_worktree_paths(repository), anchor=repository
    )
    observed_relative = {
        str(path.relative_to(repository.resolve())): digest
        for absolute, digest in observed.items()
        for path in (Path(absolute).resolve(),)
    }
    if not _canonical_equal(observed_relative, expected):
        raise ValueError("frozen worktree differs from authenticated commit blobs")
    return observed


def _require_authenticated_snapshot_unchanged(
    snapshot: Mapping[str, str], observed: Mapping[str, str], label: str
) -> None:
    if not _canonical_equal(snapshot, observed):
        raise ValueError("{} changed during the stage".format(label))


def _require_failure_evidence_absent(paths: Sequence[Path]) -> None:
    if any(path.exists() or path.is_symlink() for path in paths):
        raise ValueError("stage cannot complete beside failure evidence")


def _current_fingerprints(
    repository: Path, relatives: Sequence[Path]
) -> Mapping[str, str]:
    fingerprints: Dict[str, str] = {}
    for relative in relatives:
        path = repository / relative
        _require_tracked(path, repository, "frozen source {}".format(relative))
        try:
            fingerprints[str(relative)] = _sha256(path.read_bytes())
        except OSError as error:
            raise ValueError("cannot read frozen source {}".format(relative)) from error
    return fingerprints


def _git_blob_sha(repository: Path, commit: str, relative: Path) -> str:
    try:
        value = subprocess.run(
            ["git", "rev-parse", "{}:{}".format(commit, relative)],
            cwd=str(repository),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError(
            "frozen protocol plan is missing from Git commit"
        ) from error
    if (
        len(value) != 40
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError("frozen protocol plan Git blob SHA is invalid")
    return value


def _git_show_bytes(repository: Path, commit: str, relative: Path) -> bytes:
    try:
        return subprocess.run(
            ["git", "show", "{}:{}".format(commit, relative)],
            cwd=str(repository),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError(
            "cannot reconstruct {} at evaluated cutoff".format(relative)
        ) from error


def _require_commit_precedes(
    ancestor: Any, descendant: Any, repository: Path, label: str
) -> None:
    """Require an explicit ancestor edge between two authenticated commits."""

    for value, role in ((ancestor, "ancestor"), (descendant, "descendant")):
        if (
            not isinstance(value, str)
            or len(value) != 40
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise ValueError("{} {} must be a full lowercase Git commit".format(label, role))
    if ancestor == descendant:
        raise ValueError("{} requires a later descendant commit".format(label))
    try:
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor, descendant],
            cwd=str(repository),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError(
            "{} must preserve direct experiment ancestry".format(label)
        ) from error


def _require_head_unchanged(repository: Path, expected_commit: str) -> None:
    """Reject a stage whose checked-out commit moved after reservation."""

    if (
        not isinstance(expected_commit, str)
        or len(expected_commit) != 40
        or any(character not in "0123456789abcdef" for character in expected_commit)
    ):
        raise ValueError("stage start commit must be a full lowercase Git commit")
    try:
        observed = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=str(repository),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError("cannot authenticate the current Git HEAD") from error
    if observed != expected_commit:
        raise ValueError("Git HEAD changed after the stage was reserved")


def _manifest_chain_paths(repository: Path) -> Tuple[Path, ...]:
    return (
        repository / CAPTURE_BOUNDARY_MANIFEST_RESERVATION_RELATIVE,
        repository / CAPTURE_BOUNDARY_MANIFEST_ATTEMPT_RELATIVE,
        repository / CAPTURE_BOUNDARY_EXCLUSION_LEDGER_RELATIVE,
        repository / CAPTURE_BOUNDARY_MANIFEST_RELATIVE,
        repository / CAPTURE_BOUNDARY_LOCK_RELATIVE,
    )


def _frozen_worktree_paths(repository: Path) -> Tuple[Path, ...]:
    """Return every protocol/executable path that must stay byte-stable."""

    return tuple(
        repository / relative
        for relative in (*_FROZEN_PROTOCOL_RELATIVES, *_FROZEN_EXECUTABLE_RELATIVES)
    )


def _plan0008_chain_paths(repository: Path) -> Tuple[Path, ...]:
    return tuple(repository / spec["path"] for spec in _PLAN0008_CHAIN_SPECS)


def _pinned_exclusion_paths(repository: Path) -> Tuple[Path, ...]:
    return tuple(repository / spec["path"] for spec in _PINNED_EXCLUSION_SPECS)


def _supporting_dependency_paths(repository: Path) -> Tuple[Path, ...]:
    return tuple(repository / spec["path"] for spec in _SUPPORTING_DEPENDENCY_SPECS)


def _frozen_source_chain_hashes(repository: Path) -> Mapping[str, str]:
    """Capture and reauthenticate every mutable upstream file read by freeze."""

    specs = (
        *_PINNED_EXCLUSION_SPECS,
        *_SUPPORTING_DEPENDENCY_SPECS,
        *_PLAN0008_CHAIN_SPECS,
    )
    for spec in specs:
        path = repository / spec["path"]
        _require_canonical_path(path, repository, spec["path"], "frozen source chain")
        _require_tracked(path, repository, "frozen source chain")
    paths = tuple(repository / spec["path"] for spec in specs)
    observed = _chain_hashes(paths, anchor=repository)
    expected: Dict[str, str] = {}
    for spec in specs:
        absolute = str((repository / spec["path"]).resolve())
        previous = expected.get(absolute)
        if previous is not None and previous != spec["sha256"]:
            raise ValueError("frozen source chain contains inconsistent duplicate pins")
        expected[absolute] = spec["sha256"]
    if not _canonical_equal(observed, expected):
        raise ValueError("frozen source chain changed during authentication")
    return observed


def _load_pinned_exclusion_sources(
    repository: Path,
) -> Tuple[Tuple[Mapping[str, Any], ...], Tuple[Mapping[str, Any], ...]]:
    records = []
    metadata = []
    for spec in _PINNED_EXCLUSION_SPECS:
        path = repository / spec["path"]
        _require_canonical_path(path, repository, spec["path"], spec["label"])
        _require_tracked(path, repository, spec["label"])
        source_bytes, record = _read_json_bytes(path, spec["label"])
        if _sha256(source_bytes) != spec["sha256"]:
            raise ValueError("{} SHA-256 mismatch".format(spec["label"]))
        if source_bytes != _encoded_json(record):
            raise ValueError("{} bytes are not canonical JSON".format(spec["label"]))
        if (
            record.get(spec["identity_key"]) != spec["identity"]
            or record.get("status") != spec["status"]
            or (
                spec["experiment_type"] is not None
                and record.get("experiment_type") != spec["experiment_type"]
            )
        ):
            raise ValueError("{} identity or status mismatch".format(spec["label"]))
        records.append(record)
        metadata.append(
            {
                "label": spec["label"],
                "path": str(spec["path"]),
                "sha256": spec["sha256"],
                spec["identity_key"]: spec["identity"],
            }
        )
    return tuple(records), tuple(metadata)


def _load_supporting_dependencies(
    repository: Path,
) -> Tuple[Tuple[Mapping[str, Any], ...], Tuple[Mapping[str, Any], ...]]:
    """Authenticate the three non-run files needed by the closed-world audit."""

    records = []
    metadata = []
    for spec in _SUPPORTING_DEPENDENCY_SPECS:
        path = repository / spec["path"]
        _require_canonical_path(path, repository, spec["path"], spec["label"])
        _require_tracked(path, repository, spec["label"])
        source_bytes, record = _read_json_bytes(path, spec["label"])
        if _sha256(source_bytes) != spec["sha256"]:
            raise ValueError("{} SHA-256 mismatch".format(spec["label"]))
        if record.get(spec["identity_kind"]) != spec["identity"]:
            raise ValueError("{} identity mismatch".format(spec["label"]))
        if (
            spec["protocol_id"] is not None
            and record.get("protocol_id") != spec["protocol_id"]
        ):
            raise ValueError("{} protocol mismatch".format(spec["label"]))
        if spec["status"] is not None and record.get("status") != spec["status"]:
            raise ValueError("{} frozen status mismatch".format(spec["label"]))
        if spec["frozen"] is not None and record.get("frozen") is not spec["frozen"]:
            raise ValueError("{} frozen marker mismatch".format(spec["label"]))
        records.append(record)
        metadata.append(
            {
                "path": str(spec["path"]),
                "sha256": spec["sha256"],
                "identity_kind": spec["identity_kind"],
                "identity": spec["identity"],
            }
        )
    return tuple(records), tuple(metadata)


def _load_plan0008_manifest_chain(
    repository: Path,
) -> Tuple[Mapping[str, Any], Tuple[Mapping[str, Any], ...]]:
    chain_metadata = []
    manifest: Mapping[str, Any] | None = None
    for spec in _PLAN0008_CHAIN_SPECS:
        path = repository / spec["path"]
        _require_canonical_path(path, repository, spec["path"], spec["label"])
        _require_tracked(path, repository, spec["label"])
        source_bytes, record = _read_json_bytes(path, spec["label"])
        if _sha256(source_bytes) != spec["sha256"]:
            raise ValueError("{} SHA-256 mismatch".format(spec["label"]))
        if source_bytes != _encoded_json(record):
            raise ValueError("{} bytes are not canonical JSON".format(spec["label"]))
        chain_metadata.append(
            {
                "label": spec["label"],
                "path": str(spec["path"]),
                "sha256": spec["sha256"],
            }
        )
        if spec["path"].name == "manifest.json":
            manifest = record
    if manifest is None:
        raise ValueError("Plan 0008 outcome-free manifest is missing")
    _assert_no_outcome_keys(manifest, "plan0008_manifest")
    return manifest, tuple(chain_metadata)


def _load_evaluated_registry(
    repository: Path,
) -> Tuple[Tuple[Mapping[str, Any], ...], Tuple[Mapping[str, str], ...]]:
    cutoff = _require_commit_ancestor(
        CAPTURE_BOUNDARY_EVALUATED_CUTOFF_COMMIT,
        repository,
        "capture boundary evaluated-evidence cutoff",
    )
    try:
        output = subprocess.run(
            [
                "git",
                "ls-tree",
                "-r",
                "--name-only",
                cutoff,
                "--",
                "experiments/runs",
            ],
            cwd=str(repository),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError("cannot enumerate evaluated-evidence cutoff") from error
    relatives = tuple(
        sorted(
            Path(line)
            for line in output.splitlines()
            if line.startswith("experiments/runs/")
            and len(Path(line).parts) == 4
            and Path(line).name == "run.json"
        )
    )
    if len(relatives) != CAPTURE_BOUNDARY_EVALUATED_RUN_COUNT:
        raise ValueError("evaluated-run cutoff must contain exactly 16 run records")
    records = []
    entries = []
    for relative in relatives:
        source_bytes = _git_show_bytes(repository, cutoff, relative)
        try:
            record = json.loads(source_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError(
                "evaluated cutoff record is not valid JSON: {}".format(relative)
            ) from error
        if not isinstance(record, Mapping):
            raise ValueError("evaluated cutoff record must be an object")
        records.append(record)
        entries.append({"path": str(relative), "sha256": _sha256(source_bytes)})
    payload = _canonical_json(entries)
    root = _sha256(_REGISTRY_DOMAIN + payload)
    if root != CAPTURE_BOUNDARY_EVALUATED_REGISTRY_ROOT:
        raise ValueError("evaluated-run registry root mismatch")
    return tuple(records), tuple(entries)


def _manifest_provenance(
    repository: Path,
    commit: str,
    created_at: str,
    source_metadata: Sequence[Mapping[str, Any]],
    supporting_dependency_metadata: Sequence[Mapping[str, Any]],
    coverage_registry: Sequence[Mapping[str, str]],
    plan0008_chain: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any]:
    # Read the committed blobs, not mutable working-tree bytes.  At freeze the
    # repository is clean; at later stages this reconstructs the historical
    # attestation even though the active-plan path itself is mutable metadata.
    protocol_fingerprints = _frozen_source_fingerprints_at_commit(
        repository, commit, _FROZEN_PROTOCOL_RELATIVES
    )
    executable_fingerprints = _frozen_source_fingerprints_at_commit(
        repository, commit, _FROZEN_EXECUTABLE_RELATIVES
    )
    plan_sha = protocol_fingerprints[str(_PROTOCOL_PLAN_RELATIVE)]
    return {
        "freezer_git_commit": commit,
        "freezer_git_dirty": False,
        "created_at": created_at,
        "protocol_id": CAPTURE_BOUNDARY_MANIFEST_PROTOCOL_ID,
        "protocol_plan": {
            "path": str(_PROTOCOL_PLAN_RELATIVE),
            "sha256": plan_sha,
            "git_blob_sha": _git_blob_sha(
                repository, commit, _PROTOCOL_PLAN_RELATIVE
            ),
        },
        "protocol_fingerprints": protocol_fingerprints,
        "executable_fingerprints": executable_fingerprints,
        "exclusion_source_metadata": copy.deepcopy(list(source_metadata)),
        "supporting_dependency_metadata": copy.deepcopy(
            list(supporting_dependency_metadata)
        ),
        "evaluated_run_registry": {
            "cutoff_commit": CAPTURE_BOUNDARY_EVALUATED_CUTOFF_COMMIT,
            "run_count": len(coverage_registry),
            "root_sha256": CAPTURE_BOUNDARY_EVALUATED_REGISTRY_ROOT,
            "entries": copy.deepcopy(list(coverage_registry)),
        },
        "plan0008_manifest_chain": copy.deepcopy(list(plan0008_chain)),
        "prior_capture_outcomes_informed_protocol_design": True,
        "case_membership_outcome_fields_consulted": False,
        "capture_treatment_outcomes_computed": False,
    }


def _manifest_configuration(corpus_directory: Path) -> Mapping[str, Any]:
    return {
        "destination": str(corpus_directory.resolve()),
        "evaluated_cutoff_commit": CAPTURE_BOUNDARY_EVALUATED_CUTOFF_COMMIT,
        "evaluated_run_count": CAPTURE_BOUNDARY_EVALUATED_RUN_COUNT,
        "evaluated_run_registry_root": CAPTURE_BOUNDARY_EVALUATED_REGISTRY_ROOT,
        "supporting_dependency_count": len(_SUPPORTING_DEPENDENCY_SPECS),
        "pair_count": CAPTURE_BOUNDARY_PAIR_COUNT,
        "case_membership_outcome_fields_consulted": False,
        "capture_treatment_outcomes_computed": False,
    }


def freeze_capture_boundary_manifest(
    corpus_directory: Path,
    repository: Path,
) -> Path:
    """Reserve and freeze the fresh 64-pair outcome-blind manifest exactly once."""

    _require_canonical_path(
        corpus_directory,
        repository,
        CAPTURE_BOUNDARY_CORPUS_RELATIVE,
        "capture boundary corpus directory",
    )
    if corpus_directory.exists():
        raise ValueError("capture boundary manifest already has reserved evidence")
    commit = _require_clean_repository(repository)
    frozen_worktree_hashes = _authenticated_frozen_worktree_hashes(
        repository, commit
    )
    started_at = _timestamp(_utc_now())
    corpus_directory.mkdir(parents=False, exist_ok=False)
    reservation = {
        "run_id": BOUNDARY_MANIFEST_ID,
        "protocol_id": CAPTURE_BOUNDARY_MANIFEST_PROTOCOL_ID,
        "status": "RESERVED",
        "reserved_at": started_at,
        "git_commit": commit,
    }
    attempt = {
        "run_id": BOUNDARY_MANIFEST_ID,
        "protocol_id": CAPTURE_BOUNDARY_MANIFEST_PROTOCOL_ID,
        "experiment_type": "capture-boundary-v1-outcome-free-paired-manifest",
        "status": "STARTED",
        "started_at": started_at,
        "git_commit": commit,
        "git_dirty": False,
        "environment": {"python": sys.version, "platform": platform.platform()},
        "component_versions": dict(_MANIFEST_COMPONENT_VERSIONS),
        "configuration": _manifest_configuration(corpus_directory),
    }
    phase = "MANIFEST_SETUP"
    try:
        _write_exclusive(
            corpus_directory / "manifest-reservation.json", reservation
        )
        _write_exclusive(corpus_directory / "manifest-attempt.json", attempt)
        phase = "EXCLUSION_SOURCE_AUTHENTICATION"
        source_records, source_metadata = _load_pinned_exclusion_sources(repository)
        supporting_records, supporting_metadata = _load_supporting_dependencies(
            repository
        )
        coverage_records, coverage_registry = _load_evaluated_registry(repository)
        plan0008_manifest, plan0008_chain = _load_plan0008_manifest_chain(repository)
        frozen_source_hashes = _frozen_source_chain_hashes(repository)
        phase = "EXCLUSION_PROJECTION"
        projection_bundle = project_boundary_exclusion_sources(
            copy.deepcopy(source_records),
            copy.deepcopy(source_metadata),
            copy.deepcopy(supporting_records),
            copy.deepcopy(supporting_metadata),
            copy.deepcopy(coverage_records),
            copy.deepcopy(coverage_registry),
        )
        if (
            not isinstance(projection_bundle, Mapping)
            or set(projection_bundle)
            != {"exclusion_ledger", "coverage_projection"}
            or not isinstance(projection_bundle.get("exclusion_ledger"), Mapping)
            or not isinstance(projection_bundle.get("coverage_projection"), Mapping)
        ):
            raise ValueError(
                "capture boundary projection must provide exclusion ledger and coverage"
            )
        exclusion_ledger = projection_bundle["exclusion_ledger"]
        coverage_projection = projection_bundle["coverage_projection"]
        _assert_no_outcome_keys(
            projection_bundle, "capture_boundary_exclusion_projection"
        )
        ledger_bytes = _encoded_json(projection_bundle)
        ledger_path = corpus_directory / "exclusion-ledger.json"
        with ledger_path.open("xb") as destination:
            destination.write(ledger_bytes)
        stage_evidence_entries = (
            (
                corpus_directory / "manifest-reservation.json",
                _encoded_json(reservation),
            ),
            (corpus_directory / "manifest-attempt.json", _encoded_json(attempt)),
            (ledger_path, ledger_bytes),
        )
        phase = "MANIFEST_STAGE_EVIDENCE_SEAL"
        stage_evidence_hashes = _exact_byte_hashes(
            stage_evidence_entries,
            "capture boundary manifest stage evidence",
            anchor=repository,
        )
        phase = "MANIFEST_CONSTRUCTION"
        provenance = _manifest_provenance(
            repository,
            commit,
            started_at,
            source_metadata,
            supporting_metadata,
            coverage_registry,
            plan0008_chain,
        )
        manifest = build_capture_boundary_manifest(
            copy.deepcopy(exclusion_ledger),
            copy.deepcopy(coverage_projection),
            copy.deepcopy(plan0008_manifest),
            copy.deepcopy(provenance),
        )
        if not isinstance(manifest, Mapping):
            raise ValueError("capture boundary manifest builder must return an object")
        validate_capture_boundary_manifest(
            manifest,
            exclusion_ledger,
            coverage_projection,
            plan0008_manifest,
        )
        if not _canonical_equal(manifest.get("provenance"), provenance):
            raise ValueError("capture boundary manifest provenance mismatch")
        _assert_no_outcome_keys(manifest, "capture_boundary_manifest")
        _require_authenticated_snapshot_unchanged(
            frozen_worktree_hashes,
            _authenticated_frozen_worktree_hashes(repository, commit),
            "frozen worktree",
        )
        _require_authenticated_snapshot_unchanged(
            frozen_source_hashes,
            _frozen_source_chain_hashes(repository),
            "frozen source chain",
        )
        _require_authenticated_snapshot_unchanged(
            stage_evidence_hashes,
            _exact_byte_hashes(
                stage_evidence_entries,
                "capture boundary manifest stage evidence",
                anchor=repository,
            ),
            "capture boundary manifest stage evidence",
        )
        _require_failure_evidence_absent(
            (corpus_directory / "manifest-failure.json",)
        )
        _require_head_unchanged(repository, commit)
        manifest_bytes = _encoded_json(manifest)
        manifest_path = corpus_directory / "manifest.json"
        with manifest_path.open("xb") as destination:
            destination.write(manifest_bytes)
        lock = {
            "manifest_id": BOUNDARY_MANIFEST_ID,
            "protocol_id": CAPTURE_BOUNDARY_MANIFEST_PROTOCOL_ID,
            "exclusion_ledger_sha256": _sha256(ledger_bytes),
            "exclusion_ledger_bytes": len(ledger_bytes),
            "manifest_sha256": _sha256(manifest_bytes),
            "manifest_bytes": len(manifest_bytes),
            "freezer_git_commit": commit,
        }
        lock_path = corpus_directory / "manifest.lock.json"
        _write_exclusive(lock_path, lock)
        _exact_byte_hashes(
            (
                *stage_evidence_entries,
                (manifest_path, manifest_bytes),
                (lock_path, _encoded_json(lock)),
            ),
            "capture boundary completed manifest chain",
            anchor=repository,
        )
        _require_chain_unchanged(stage_evidence_hashes)
        _require_authenticated_snapshot_unchanged(
            frozen_worktree_hashes,
            _authenticated_frozen_worktree_hashes(repository, commit),
            "frozen worktree",
        )
        _require_authenticated_snapshot_unchanged(
            frozen_source_hashes,
            _frozen_source_chain_hashes(repository),
            "frozen source chain",
        )
        _require_failure_evidence_absent(
            (corpus_directory / "manifest-failure.json",)
        )
        _require_head_unchanged(repository, commit)
    except BaseException as error:
        _record_failure_preserving_original(
            corpus_directory / "manifest-failure.json", attempt, phase, error
        )
        raise
    return manifest_path


def _require_frozen_lineage(
    repository: Path,
    manifest: Mapping[str, Any],
    current_commit: str,
) -> None:
    provenance = manifest.get("provenance")
    if not isinstance(provenance, Mapping):
        raise ValueError("capture boundary manifest provenance is missing")
    freezer_commit = _require_commit_ancestor(
        provenance.get("freezer_git_commit"),
        repository,
        "capture boundary freezer commit",
    )
    _require_commit_ancestor(
        current_commit, repository, "capture boundary stage commit"
    )
    _require_commit_precedes(
        freezer_commit,
        current_commit,
        repository,
        "capture boundary freezer-to-stage lineage",
    )
    protocol = provenance.get("protocol_fingerprints")
    executables = provenance.get("executable_fingerprints")
    if not isinstance(protocol, Mapping) or not isinstance(executables, Mapping):
        raise ValueError("capture boundary frozen fingerprints are missing")
    protocol_paths = tuple(Path(value) for value in protocol)
    executable_paths = tuple(Path(value) for value in executables)
    for commit, label in (
        (freezer_commit, "freezer"),
        (current_commit, "stage"),
    ):
        if not _canonical_equal(
            _frozen_source_fingerprints_at_commit(
                repository, commit, protocol_paths
            ),
            protocol,
        ) or not _canonical_equal(
            _frozen_source_fingerprints_at_commit(
                repository, commit, executable_paths
            ),
            executables,
        ):
            raise ValueError(
                "capture boundary {} commit changed frozen sources".format(label)
            )
    plan = provenance.get("protocol_plan")
    if (
        not isinstance(plan, Mapping)
        or plan.get("path") != str(_PROTOCOL_PLAN_RELATIVE)
        or plan.get("sha256") != protocol.get(str(_PROTOCOL_PLAN_RELATIVE))
        or plan.get("git_blob_sha")
        != _git_blob_sha(repository, freezer_commit, _PROTOCOL_PLAN_RELATIVE)
    ):
        raise ValueError("capture boundary historical protocol plan mismatch")


def _validate_frozen_capture_boundary_manifest(
    manifest_path: Path,
    lock_path: Path,
    repository: Path,
) -> Tuple[bytes, Mapping[str, Any], Mapping[str, str]]:
    failure_path = repository / CAPTURE_BOUNDARY_CORPUS_RELATIVE / "manifest-failure.json"
    if failure_path.exists() or failure_path.is_symlink():
        raise ValueError("capture boundary manifest cannot coexist with failure evidence")
    _require_canonical_path(
        manifest_path,
        repository,
        CAPTURE_BOUNDARY_MANIFEST_RELATIVE,
        "capture boundary manifest",
    )
    _require_canonical_path(
        lock_path,
        repository,
        CAPTURE_BOUNDARY_LOCK_RELATIVE,
        "capture boundary manifest lock",
    )
    chain = _manifest_chain_paths(repository)
    chain_relatives = (
        CAPTURE_BOUNDARY_MANIFEST_RESERVATION_RELATIVE,
        CAPTURE_BOUNDARY_MANIFEST_ATTEMPT_RELATIVE,
        CAPTURE_BOUNDARY_EXCLUSION_LEDGER_RELATIVE,
        CAPTURE_BOUNDARY_MANIFEST_RELATIVE,
        CAPTURE_BOUNDARY_LOCK_RELATIVE,
    )
    for path, relative in zip(chain, chain_relatives):
        _require_canonical_path(
            path, repository, relative, "capture boundary manifest chain"
        )
        _require_tracked(path, repository, "capture boundary manifest chain")
    reservation_bytes, reservation = _read_json_bytes(
        chain[0], "capture boundary manifest reservation"
    )
    attempt_bytes, attempt = _read_json_bytes(
        chain[1], "capture boundary manifest attempt"
    )
    ledger_bytes, ledger = _read_json_bytes(
        chain[2], "capture boundary exclusion ledger"
    )
    manifest_bytes, manifest = _read_json_bytes(
        chain[3], "capture boundary manifest"
    )
    lock_bytes, lock = _read_json_bytes(chain[4], "capture boundary manifest lock")
    chain_entries = tuple(
        zip(
            chain,
            (
                reservation_bytes,
                attempt_bytes,
                ledger_bytes,
                manifest_bytes,
                lock_bytes,
            ),
        )
    )
    authenticated_chain_hashes = _exact_byte_hashes(
        chain_entries,
        "capture boundary frozen manifest chain",
        anchor=repository,
    )
    for source_bytes, value, label in (
        (reservation_bytes, reservation, "reservation"),
        (attempt_bytes, attempt, "attempt"),
        (ledger_bytes, ledger, "ledger"),
        (manifest_bytes, manifest, "manifest"),
        (lock_bytes, lock, "lock"),
    ):
        if source_bytes != _encoded_json(value):
            raise ValueError(
                "capture boundary manifest {} is not canonical JSON".format(label)
            )
    freezer_commit = attempt.get("git_commit")
    expected_reservation = {
        "run_id": BOUNDARY_MANIFEST_ID,
        "protocol_id": CAPTURE_BOUNDARY_MANIFEST_PROTOCOL_ID,
        "status": "RESERVED",
        "reserved_at": attempt.get("started_at"),
        "git_commit": freezer_commit,
    }
    expected_lock = {
        "manifest_id": BOUNDARY_MANIFEST_ID,
        "protocol_id": CAPTURE_BOUNDARY_MANIFEST_PROTOCOL_ID,
        "exclusion_ledger_sha256": _sha256(ledger_bytes),
        "exclusion_ledger_bytes": len(ledger_bytes),
        "manifest_sha256": _sha256(manifest_bytes),
        "manifest_bytes": len(manifest_bytes),
        "freezer_git_commit": freezer_commit,
    }
    if not _canonical_equal(reservation, expected_reservation):
        raise ValueError("capture boundary manifest reservation mismatch")
    if not _canonical_equal(lock, expected_lock):
        raise ValueError("capture boundary manifest lock does not match exact bytes")
    if (
        set(attempt) != _ATTEMPT_KEYS
        or attempt.get("run_id") != BOUNDARY_MANIFEST_ID
        or attempt.get("protocol_id") != CAPTURE_BOUNDARY_MANIFEST_PROTOCOL_ID
        or attempt.get("experiment_type")
        != "capture-boundary-v1-outcome-free-paired-manifest"
        or attempt.get("status") != "STARTED"
        or attempt.get("git_dirty") is not False
        or not _canonical_equal(
            attempt.get("component_versions"), _MANIFEST_COMPONENT_VERSIONS
        )
        or not _canonical_equal(
            attempt.get("configuration"),
            _manifest_configuration(repository / CAPTURE_BOUNDARY_CORPUS_RELATIVE),
        )
    ):
        raise ValueError("capture boundary manifest attempt mismatch")
    environment = attempt.get("environment")
    if (
        not isinstance(environment, Mapping)
        or set(environment) != {"python", "platform"}
        or not all(isinstance(value, str) for value in environment.values())
    ):
        raise ValueError("capture boundary manifest environment mismatch")
    _require_timestamp(attempt.get("started_at"), "capture boundary manifest start")
    _require_commit_ancestor(
        freezer_commit, repository, "capture boundary manifest freezer commit"
    )
    source_records, source_metadata = _load_pinned_exclusion_sources(repository)
    supporting_records, supporting_metadata = _load_supporting_dependencies(
        repository
    )
    coverage_records, coverage_registry = _load_evaluated_registry(repository)
    plan0008_manifest, plan0008_chain = _load_plan0008_manifest_chain(repository)
    projection_bundle = project_boundary_exclusion_sources(
        copy.deepcopy(source_records),
        copy.deepcopy(source_metadata),
        copy.deepcopy(supporting_records),
        copy.deepcopy(supporting_metadata),
        copy.deepcopy(coverage_records),
        copy.deepcopy(coverage_registry),
    )
    if (
        not isinstance(projection_bundle, Mapping)
        or set(projection_bundle) != {"exclusion_ledger", "coverage_projection"}
        or not _canonical_equal(ledger, projection_bundle)
    ):
        raise ValueError("capture boundary exclusion ledger is not reproducible")
    exclusion_ledger = projection_bundle["exclusion_ledger"]
    coverage_projection = projection_bundle["coverage_projection"]
    validate_capture_boundary_manifest(
        manifest,
        exclusion_ledger,
        coverage_projection,
        plan0008_manifest,
    )
    expected_provenance = _manifest_provenance(
        repository,
        freezer_commit,
        attempt["started_at"],
        source_metadata,
        supporting_metadata,
        coverage_registry,
        plan0008_chain,
    )
    if not _canonical_equal(manifest.get("provenance"), expected_provenance):
        raise ValueError("capture boundary manifest provenance is not reproducible")
    _assert_no_outcome_keys(ledger, "capture_boundary_exclusion_ledger")
    _assert_no_outcome_keys(manifest, "capture_boundary_manifest")
    _require_authenticated_snapshot_unchanged(
        authenticated_chain_hashes,
        _exact_byte_hashes(
            chain_entries,
            "capture boundary frozen manifest chain",
            anchor=repository,
        ),
        "capture boundary frozen manifest chain",
    )
    _require_failure_evidence_absent((failure_path,))
    return manifest_bytes, manifest, authenticated_chain_hashes


def _exact_configuration(
    manifest_path: Path, manifest_bytes: bytes
) -> Mapping[str, Any]:
    return {
        "manifest_id": BOUNDARY_MANIFEST_ID,
        "manifest_path": str(manifest_path.resolve()),
        "manifest_sha256": _sha256(manifest_bytes),
        "pair_count": CAPTURE_BOUNDARY_PAIR_COUNT,
        "max_exact_states": CAPTURE_BOUNDARY_EXACT_MAX_STATES,
        "structural_state_bound": CAPTURE_BOUNDARY_STRUCTURAL_STATE_BOUND,
        "phase_order": ["SOURCE_EXACT", "SOURCE_SEAL", "TREATMENT_EXACT", "PAIRED_RESULT"],
    }


def _depth5_configuration(
    manifest_path: Path,
    manifest_bytes: bytes,
    exact_path: Path,
    exact_bytes: bytes,
    exact_record: Mapping[str, Any],
) -> Mapping[str, Any]:
    return {
        "manifest_id": BOUNDARY_MANIFEST_ID,
        "manifest_path": str(manifest_path.resolve()),
        "manifest_sha256": _sha256(manifest_bytes),
        "source_exact_run_id": exact_record["run_id"],
        "source_exact_path": str(exact_path.resolve()),
        "source_exact_sha256": _sha256(exact_bytes),
        "pair_count": CAPTURE_BOUNDARY_PAIR_COUNT,
        "profile_count": CAPTURE_BOUNDARY_PAIR_COUNT * 2,
        "seeds": list(CAPTURE_BOUNDARY_DEPTH5_SEEDS),
        "depth": CAPTURE_BOUNDARY_DEPTH5_DEPTH,
        "max_nodes_per_definition": CAPTURE_BOUNDARY_DEPTH5_MAX_NODES,
        "play_gates": asdict(PlayGates()),
        "phase_order": ["SOURCE_DEPTH5", "SOURCE_SEAL", "TREATMENT_DEPTH5", "PAIRED_RESULT"],
        "adaptive_eligibility": False,
        "candidate_cap": None,
        "replacement": False,
    }


def _validate_exact_configuration(
    configuration: Any,
    manifest: Mapping[str, Any],
) -> None:
    expected_keys = {
        "manifest_id",
        "manifest_path",
        "manifest_sha256",
        "pair_count",
        "max_exact_states",
        "structural_state_bound",
        "phase_order",
    }
    if not isinstance(configuration, Mapping) or set(configuration) != expected_keys:
        raise ValueError("capture boundary exact configuration schema mismatch")
    if (
        configuration.get("manifest_id") != BOUNDARY_MANIFEST_ID
        or configuration.get("manifest_sha256") != _sha256(_encoded_json(manifest))
        or not _canonical_equal(
            configuration.get("pair_count"), CAPTURE_BOUNDARY_PAIR_COUNT
        )
        or not _canonical_equal(
            configuration.get("max_exact_states"), CAPTURE_BOUNDARY_EXACT_MAX_STATES
        )
        or not _canonical_equal(
            configuration.get("structural_state_bound"),
            CAPTURE_BOUNDARY_STRUCTURAL_STATE_BOUND,
        )
        or not _canonical_equal(
            configuration.get("phase_order"),
            ["SOURCE_EXACT", "SOURCE_SEAL", "TREATMENT_EXACT", "PAIRED_RESULT"],
        )
    ):
        raise ValueError("capture boundary exact configuration mismatch")
    _recorded_repository_root(
        configuration["manifest_path"],
        CAPTURE_BOUNDARY_MANIFEST_RELATIVE,
        "capture boundary exact manifest path",
    )


def _validate_depth5_configuration(
    configuration: Any,
    manifest: Mapping[str, Any],
    exact_record: Mapping[str, Any],
) -> None:
    expected = _depth5_configuration(
        Path(str(configuration.get("manifest_path")))
        if isinstance(configuration, Mapping)
        else Path("."),
        _encoded_json(manifest),
        Path(str(configuration.get("source_exact_path")))
        if isinstance(configuration, Mapping)
        else Path("."),
        _encoded_json(exact_record),
        exact_record,
    )
    if not isinstance(configuration, Mapping) or set(configuration) != set(expected):
        raise ValueError("capture boundary depth5 configuration schema mismatch")
    if not _canonical_equal(configuration, expected):
        raise ValueError("capture boundary depth5 configuration mismatch")
    manifest_root = _recorded_repository_root(
        configuration["manifest_path"],
        CAPTURE_BOUNDARY_MANIFEST_RELATIVE,
        "capture boundary depth5 manifest path",
    )
    exact_relative = (
        Path("experiments/runs") / str(exact_record["run_id"]) / "run.json"
    )
    exact_root = _recorded_repository_root(
        configuration["source_exact_path"],
        exact_relative,
        "capture boundary depth5 exact path",
    )
    if manifest_root != exact_root:
        raise ValueError("capture boundary depth5 configuration roots differ")


def _exact_narrative(result: Mapping[str, Any]) -> Mapping[str, Any]:
    aggregate = result.get("aggregate")
    timing = result.get("timing")
    if not isinstance(aggregate, Mapping) or not isinstance(timing, Mapping):
        raise ValueError("capture boundary exact narrative requires aggregate and timing")
    exact_censored = aggregate.get("exact_censored_count")
    if type(exact_censored) is not int or exact_censored < 0:
        raise ValueError("capture boundary exact censor count is missing")
    return {
        "hypothesis": "Fresh paired capture cases reproduce a three-to-four-vector exact boundary.",
        "baseline": "All 64 schema-v1 sources are solved and sealed before treatment.",
        "treatment": "All 64 paired schema-v3 capture treatments are then solved under the fixed cap.",
        "expected_result": "All 128 exact solves complete within the proved 43776-state bound.",
        "actual_result": {**dict(aggregate), "timing": dict(timing)},
        "interpretation": (
            "Exact evidence is complete."
            if exact_censored == 0
            else "Exact censoring makes every preregistered response inconclusive."
        ),
        "decision": (
            "COMMIT_EXACT_THEN_RUN_FIXED_DEPTH5"
            if exact_censored == 0
            else "STOP_BEFORE_DEPTH5_AND_AUDIT_EXACT_BOUND"
        ),
    }


def _depth5_narrative(result: Mapping[str, Any]) -> Mapping[str, Any]:
    aggregate = result.get("aggregate")
    timing = result.get("timing")
    if not isinstance(aggregate, Mapping) or not isinstance(timing, Mapping):
        raise ValueError("capture boundary depth5 narrative requires aggregate and timing")
    assessments = aggregate.get("assessments")
    overall = assessments.get("overall") if isinstance(assessments, Mapping) else None
    return {
        "hypothesis": "Fixed depth-5 play distinguishes a useful capture boundary from a dominance cliff.",
        "baseline": "Every one of the 64 source profiles is attempted before any treatment profile.",
        "treatment": "Every one of the 64 treatment profiles receives its own fixed 30-seed node budget.",
        "expected_result": "The full fixed schedule completes and reconstructs all frozen assessments.",
        "actual_result": {**dict(aggregate), "timing": dict(timing)},
        "interpretation": "The result is interpreted only through the frozen assessment priority.",
        "decision": (
            overall.get("next_branch")
            if isinstance(overall, Mapping)
            and isinstance(overall.get("next_branch"), str)
            else "FOLLOW_FROZEN_ASSESSMENT"
        ),
    }


def _validate_completed_narrative(
    record: Mapping[str, Any],
    result: Mapping[str, Any],
    builder: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    label: str,
) -> None:
    if set(record) != _COMPLETED_RUN_KEYS:
        raise ValueError("{} completed record schema mismatch".format(label))
    if not _canonical_equal(
        {key: record.get(key) for key in _NARRATIVE_KEYS}, builder(result)
    ):
        raise ValueError("{} narrative fields do not match result".format(label))


def _require_type_sensitive_attempt_match(
    attempt: Mapping[str, Any], record: Mapping[str, Any], label: str
) -> None:
    expected = {
        key: ("STARTED" if key == "status" else record.get(key))
        for key in _ATTEMPT_KEYS
    }
    if not _canonical_equal(attempt, expected):
        raise ValueError("{} attempt differs from completed record".format(label))


def _require_exact_source_chain_canonical(
    exact_run_path: Path,
    output_root: Path,
    record: Mapping[str, Any],
    attempt: Mapping[str, Any],
) -> Mapping[str, str]:
    """Authenticate all three exact-source records by their canonical bytes."""

    expected_reservation = {
        "protocol_id": CAPTURE_BOUNDARY_EXACT_PROTOCOL_ID,
        "run_id": record.get("run_id"),
        "status": "RESERVED",
        "reserved_at": attempt.get("started_at"),
        "git_commit": attempt.get("git_commit"),
    }
    return _exact_byte_hashes(
        (
            (
                output_root
                / ".{}.reservation.json".format(
                    CAPTURE_BOUNDARY_EXACT_PROTOCOL_ID
                ),
                _encoded_json(expected_reservation),
            ),
            (exact_run_path.parent / "attempt.json", _encoded_json(attempt)),
            (exact_run_path, _encoded_json(record)),
        ),
        "capture boundary exact upstream chain",
        anchor=output_root,
    )


def run_capture_boundary_paired_exact(
    manifest_path: Path,
    lock_path: Path,
    output_root: Path,
    repository: Path,
) -> Path:
    """Run the fixed all-source-then-all-treatment exact schedule once."""

    _require_canonical_path(
        output_root,
        repository,
        Path("experiments/runs"),
        "capture boundary exact output",
    )
    manifest_bytes, manifest, manifest_chain_hashes = (
        _validate_frozen_capture_boundary_manifest(
            manifest_path, lock_path, repository
        )
    )
    commit = _require_clean_repository(repository)
    _require_frozen_lineage(repository, manifest, commit)
    _require_chain_unchanged(manifest_chain_hashes)
    manifest_failure_path = (
        repository / CAPTURE_BOUNDARY_CORPUS_RELATIVE / "manifest-failure.json"
    )
    protocol_failure_path = (
        output_root
        / ".{}.failure.json".format(CAPTURE_BOUNDARY_EXACT_PROTOCOL_ID)
    )
    _require_failure_evidence_absent(
        (manifest_failure_path, protocol_failure_path)
    )
    _scan_prior_protocol(output_root, CAPTURE_BOUNDARY_EXACT_PROTOCOL_ID)
    frozen_worktree_hashes = _authenticated_frozen_worktree_hashes(
        repository, commit
    )
    chain_hashes = dict(manifest_chain_hashes)
    frozen_source_hashes = _frozen_source_chain_hashes(repository)
    chain_hashes.update(frozen_source_hashes)
    started = _utc_now()
    started_at = _timestamp(started)
    run_id = "{}-capture-boundary-exact-{}".format(
        started.strftime("%Y%m%dT%H%M%S%fZ"), _sha256(manifest_bytes)[:8]
    )
    attempt = {
        "run_id": run_id,
        "protocol_id": CAPTURE_BOUNDARY_EXACT_PROTOCOL_ID,
        "experiment_type": "capture-boundary-v1-paired-exact",
        "status": "STARTED",
        "started_at": started_at,
        "git_commit": commit,
        "git_dirty": False,
        "environment": {"python": sys.version, "platform": platform.platform()},
        "component_versions": dict(_EXACT_COMPONENT_VERSIONS),
        "configuration": _exact_configuration(manifest_path, manifest_bytes),
    }
    _validate_exact_configuration(attempt["configuration"], manifest)
    _reserve_protocol(
        output_root,
        CAPTURE_BOUNDARY_EXACT_PROTOCOL_ID,
        run_id,
        commit,
        started_at,
    )
    run_directory = output_root / run_id
    try:
        run_directory.mkdir(parents=False, exist_ok=False)
    except BaseException as error:
        _record_failure_preserving_original(
            output_root
            / ".{}.failure.json".format(CAPTURE_BOUNDARY_EXACT_PROTOCOL_ID),
            attempt,
            "EXACT_RUN_DIRECTORY_SETUP",
            error,
        )
        raise
    try:
        _write_exclusive(run_directory / "attempt.json", attempt)
    except BaseException as error:
        _record_failure_preserving_original(
            run_directory / "failure.json", attempt, "EXACT_SETUP", error
        )
        raise
    run_failure_path = run_directory / "failure.json"
    reservation_path = output_root / ".{}.reservation.json".format(
        CAPTURE_BOUNDARY_EXACT_PROTOCOL_ID
    )
    stage_evidence_entries = (
        (
            reservation_path,
            _encoded_json(
                {
                    "protocol_id": CAPTURE_BOUNDARY_EXACT_PROTOCOL_ID,
                    "run_id": run_id,
                    "status": "RESERVED",
                    "reserved_at": started_at,
                    "git_commit": commit,
                }
            ),
        ),
        (run_directory / "attempt.json", _encoded_json(attempt)),
    )
    phase = "EXACT_STAGE_EVIDENCE_SEAL"
    try:
        stage_evidence_hashes = _exact_byte_hashes(
            stage_evidence_entries,
            "capture boundary exact stage evidence",
            anchor=output_root,
        )
        phase = "PAIRED_EXACT_EVALUATION"
        result = evaluate_capture_boundary_exact(
            copy.deepcopy(manifest),
            expected_pair_count=CAPTURE_BOUNDARY_PAIR_COUNT,
            max_states=CAPTURE_BOUNDARY_EXACT_MAX_STATES,
        )
        if not isinstance(result, Mapping):
            raise ValueError("capture boundary exact evaluator must return an object")
        validate_capture_boundary_exact_result(
            result,
            manifest,
            expected_pair_count=CAPTURE_BOUNDARY_PAIR_COUNT,
            max_states=CAPTURE_BOUNDARY_EXACT_MAX_STATES,
        )
        _require_frozen_lineage(repository, manifest, commit)
        _require_authenticated_snapshot_unchanged(
            frozen_worktree_hashes,
            _authenticated_frozen_worktree_hashes(repository, commit),
            "frozen worktree",
        )
        _require_chain_unchanged(chain_hashes)
        _require_authenticated_snapshot_unchanged(
            frozen_source_hashes,
            _frozen_source_chain_hashes(repository),
            "frozen source chain",
        )
        _require_authenticated_snapshot_unchanged(
            stage_evidence_hashes,
            _exact_byte_hashes(
                stage_evidence_entries,
                "capture boundary exact stage evidence",
                anchor=output_root,
            ),
            "capture boundary exact stage evidence",
        )
        _require_failure_evidence_absent(
            (
                manifest_failure_path,
                protocol_failure_path,
                run_failure_path,
            )
        )
        _require_head_unchanged(repository, commit)
        phase = "EXACT_COMPLETION_RECORD"
        record = {
            **attempt,
            "status": "COMPLETED",
            "completed_at": _timestamp(_utc_now()),
            **_exact_narrative(result),
            "results": result,
        }
        _validate_completed_narrative(
            record, result, _exact_narrative, "capture boundary exact"
        )
        destination = run_directory / "run.json"
        _write_exclusive(destination, record)
        _exact_byte_hashes(
            (*stage_evidence_entries, (destination, _encoded_json(record))),
            "capture boundary completed exact chain",
            anchor=output_root,
        )
        _require_chain_unchanged(stage_evidence_hashes)
        _require_chain_unchanged(chain_hashes)
        _require_authenticated_snapshot_unchanged(
            frozen_worktree_hashes,
            _authenticated_frozen_worktree_hashes(repository, commit),
            "frozen worktree",
        )
        _require_authenticated_snapshot_unchanged(
            frozen_source_hashes,
            _frozen_source_chain_hashes(repository),
            "frozen source chain",
        )
        _require_failure_evidence_absent(
            (
                manifest_failure_path,
                protocol_failure_path,
                run_failure_path,
            )
        )
        _require_head_unchanged(repository, commit)
    except BaseException as error:
        _record_failure_preserving_original(
            run_directory / "failure.json", attempt, phase, error
        )
        raise
    return destination


def _validate_capture_boundary_exact_source(
    exact_run_path: Path,
    output_root: Path,
    repository: Path,
    manifest: Mapping[str, Any],
) -> Tuple[bytes, Mapping[str, Any], Mapping[str, str]]:
    protocol_failure = output_root / ".{}.failure.json".format(
        CAPTURE_BOUNDARY_EXACT_PROTOCOL_ID
    )
    _require_failure_evidence_absent(
        (protocol_failure, exact_run_path.parent / "failure.json")
    )
    if exact_run_path.is_symlink():
        raise ValueError("capture boundary exact source cannot be a symlink")
    try:
        relative = exact_run_path.resolve().relative_to(output_root.resolve())
    except ValueError as error:
        raise ValueError("capture boundary exact source must be in run directory") from error
    if len(relative.parts) != 2 or relative.parts[1] != "run.json":
        raise ValueError("capture boundary exact source must be <run-id>/run.json")
    _require_tracked(exact_run_path, repository, "capture boundary exact source")
    exact_bytes, record = _read_json_bytes(
        exact_run_path, "capture boundary exact source"
    )
    if exact_bytes != _encoded_json(record):
        raise ValueError("capture boundary exact source is not canonical JSON")
    if (
        set(record) != _COMPLETED_RUN_KEYS
        or record.get("run_id") != relative.parts[0]
        or record.get("protocol_id") != CAPTURE_BOUNDARY_EXACT_PROTOCOL_ID
        or record.get("experiment_type") != "capture-boundary-v1-paired-exact"
        or record.get("status") != "COMPLETED"
        or record.get("git_dirty") is not False
        or not _canonical_equal(
            record.get("component_versions"), _EXACT_COMPONENT_VERSIONS
        )
    ):
        raise ValueError("capture boundary exact source identity mismatch")
    attempt = _validate_completed_run_attempt(
        exact_run_path, record, repository, _EXACT_COMPONENT_VERSIONS
    )
    _require_type_sensitive_attempt_match(
        attempt, record, "capture boundary exact"
    )
    _validate_protocol_reservation(
        output_root,
        CAPTURE_BOUNDARY_EXACT_PROTOCOL_ID,
        record["run_id"],
        attempt["git_commit"],
        attempt["started_at"],
        repository,
    )
    authenticated_chain_hashes = _require_exact_source_chain_canonical(
        exact_run_path, output_root, record, attempt
    )
    _require_commit_ancestor(
        attempt["git_commit"], repository, "capture boundary exact source commit"
    )
    _require_frozen_lineage(repository, manifest, attempt["git_commit"])
    _validate_exact_configuration(record.get("configuration"), manifest)
    exact_manifest_root = _recorded_repository_root(
        record["configuration"]["manifest_path"],
        CAPTURE_BOUNDARY_MANIFEST_RELATIVE,
        "capture boundary exact manifest path",
    )
    if exact_manifest_root.resolve() != repository.resolve():
        raise ValueError("capture boundary exact configuration root mismatch")
    result = record.get("results")
    if not isinstance(result, Mapping):
        raise ValueError("capture boundary exact result is missing")
    validate_capture_boundary_exact_result(
        result,
        manifest,
        expected_pair_count=CAPTURE_BOUNDARY_PAIR_COUNT,
        max_states=CAPTURE_BOUNDARY_EXACT_MAX_STATES,
    )
    _validate_completed_narrative(
        record, result, _exact_narrative, "capture boundary exact"
    )
    _require_authenticated_snapshot_unchanged(
        authenticated_chain_hashes,
        _require_exact_source_chain_canonical(
            exact_run_path, output_root, record, attempt
        ),
        "capture boundary exact upstream chain",
    )
    _require_failure_evidence_absent(
        (protocol_failure, exact_run_path.parent / "failure.json")
    )
    return exact_bytes, record, authenticated_chain_hashes


def _require_exact_complete_for_depth5(result: Mapping[str, Any]) -> None:
    aggregate = result.get("aggregate")
    count = (
        aggregate.get("exact_censored_count")
        if isinstance(aggregate, Mapping)
        else None
    )
    if type(count) is not int or count < 0:
        raise ValueError("capture boundary exact censor count is missing")
    if count != 0:
        raise ValueError("exact censoring blocks capture boundary depth5 before reservation")


def run_capture_boundary_fixed_depth5(
    exact_run_path: Path,
    manifest_path: Path,
    lock_path: Path,
    output_root: Path,
    repository: Path,
) -> Path:
    """Run all 64 source then all 64 treatment depth-5 profiles exactly once."""

    _require_canonical_path(
        output_root,
        repository,
        Path("experiments/runs"),
        "capture boundary depth5 output",
    )
    manifest_bytes, manifest, manifest_chain_hashes = (
        _validate_frozen_capture_boundary_manifest(
            manifest_path, lock_path, repository
        )
    )
    exact_bytes, exact_record, exact_chain_hashes = (
        _validate_capture_boundary_exact_source(
            exact_run_path, output_root, repository, manifest
        )
    )
    exact_result = exact_record["results"]
    _require_exact_complete_for_depth5(exact_result)
    commit = _require_clean_repository(repository)
    _require_frozen_lineage(repository, manifest, commit)
    _require_commit_ancestor(
        exact_record["git_commit"], repository, "capture boundary exact run commit"
    )
    _require_commit_precedes(
        exact_record["git_commit"],
        commit,
        repository,
        "capture boundary exact-to-depth5 lineage",
    )
    _require_chain_unchanged(manifest_chain_hashes)
    _require_chain_unchanged(exact_chain_hashes)
    manifest_failure_path = (
        repository / CAPTURE_BOUNDARY_CORPUS_RELATIVE / "manifest-failure.json"
    )
    exact_protocol_failure_path = (
        output_root
        / ".{}.failure.json".format(CAPTURE_BOUNDARY_EXACT_PROTOCOL_ID)
    )
    exact_run_failure_path = exact_run_path.parent / "failure.json"
    depth_protocol_failure_path = (
        output_root
        / ".{}.failure.json".format(CAPTURE_BOUNDARY_DEPTH5_PROTOCOL_ID)
    )
    _require_failure_evidence_absent(
        (
            manifest_failure_path,
            exact_protocol_failure_path,
            exact_run_failure_path,
            depth_protocol_failure_path,
        )
    )
    _scan_prior_protocol(output_root, CAPTURE_BOUNDARY_DEPTH5_PROTOCOL_ID)
    frozen_worktree_hashes = _authenticated_frozen_worktree_hashes(
        repository, commit
    )
    chain_hashes = dict(manifest_chain_hashes)
    chain_hashes.update(exact_chain_hashes)
    frozen_source_hashes = _frozen_source_chain_hashes(repository)
    chain_hashes.update(frozen_source_hashes)
    started = _utc_now()
    started_at = _timestamp(started)
    run_id = "{}-capture-boundary-depth5-{}".format(
        started.strftime("%Y%m%dT%H%M%S%fZ"), _sha256(exact_bytes)[:8]
    )
    attempt = {
        "run_id": run_id,
        "protocol_id": CAPTURE_BOUNDARY_DEPTH5_PROTOCOL_ID,
        "experiment_type": "capture-boundary-v1-fixed-depth5",
        "status": "STARTED",
        "started_at": started_at,
        "git_commit": commit,
        "git_dirty": False,
        "environment": {"python": sys.version, "platform": platform.platform()},
        "component_versions": dict(_DEPTH5_COMPONENT_VERSIONS),
        "configuration": _depth5_configuration(
            manifest_path,
            manifest_bytes,
            exact_run_path,
            exact_bytes,
            exact_record,
        ),
    }
    _validate_depth5_configuration(attempt["configuration"], manifest, exact_record)
    _reserve_protocol(
        output_root,
        CAPTURE_BOUNDARY_DEPTH5_PROTOCOL_ID,
        run_id,
        commit,
        started_at,
    )
    run_directory = output_root / run_id
    try:
        run_directory.mkdir(parents=False, exist_ok=False)
    except BaseException as error:
        _record_failure_preserving_original(
            output_root
            / ".{}.failure.json".format(CAPTURE_BOUNDARY_DEPTH5_PROTOCOL_ID),
            attempt,
            "DEPTH5_RUN_DIRECTORY_SETUP",
            error,
        )
        raise
    try:
        _write_exclusive(run_directory / "attempt.json", attempt)
    except BaseException as error:
        _record_failure_preserving_original(
            run_directory / "failure.json", attempt, "DEPTH5_SETUP", error
        )
        raise
    depth_run_failure_path = run_directory / "failure.json"
    depth5_reservation_path = output_root / ".{}.reservation.json".format(
        CAPTURE_BOUNDARY_DEPTH5_PROTOCOL_ID
    )
    stage_evidence_entries = (
        (
            depth5_reservation_path,
            _encoded_json(
                {
                    "protocol_id": CAPTURE_BOUNDARY_DEPTH5_PROTOCOL_ID,
                    "run_id": run_id,
                    "status": "RESERVED",
                    "reserved_at": started_at,
                    "git_commit": commit,
                }
            ),
        ),
        (run_directory / "attempt.json", _encoded_json(attempt)),
    )
    phase = "DEPTH5_STAGE_EVIDENCE_SEAL"
    try:
        stage_evidence_hashes = _exact_byte_hashes(
            stage_evidence_entries,
            "capture boundary depth5 stage evidence",
            anchor=output_root,
        )
        phase = "FIXED_DEPTH5_EVALUATION"
        result = evaluate_capture_boundary_depth5(
            copy.deepcopy(manifest),
            copy.deepcopy(exact_result),
            expected_pair_count=CAPTURE_BOUNDARY_PAIR_COUNT,
            seeds=CAPTURE_BOUNDARY_DEPTH5_SEEDS,
            depth=CAPTURE_BOUNDARY_DEPTH5_DEPTH,
            max_nodes=CAPTURE_BOUNDARY_DEPTH5_MAX_NODES,
            gates=PlayGates(),
        )
        if not isinstance(result, Mapping):
            raise ValueError("capture boundary depth5 evaluator must return an object")
        validate_capture_boundary_depth5_result(
            result,
            manifest,
            exact_result,
            expected_pair_count=CAPTURE_BOUNDARY_PAIR_COUNT,
            seeds=CAPTURE_BOUNDARY_DEPTH5_SEEDS,
            depth=CAPTURE_BOUNDARY_DEPTH5_DEPTH,
            max_nodes=CAPTURE_BOUNDARY_DEPTH5_MAX_NODES,
            gates=PlayGates(),
        )
        _require_frozen_lineage(repository, manifest, commit)
        _require_authenticated_snapshot_unchanged(
            frozen_worktree_hashes,
            _authenticated_frozen_worktree_hashes(repository, commit),
            "frozen worktree",
        )
        _require_chain_unchanged(chain_hashes)
        _require_authenticated_snapshot_unchanged(
            frozen_source_hashes,
            _frozen_source_chain_hashes(repository),
            "frozen source chain",
        )
        _require_authenticated_snapshot_unchanged(
            stage_evidence_hashes,
            _exact_byte_hashes(
                stage_evidence_entries,
                "capture boundary depth5 stage evidence",
                anchor=output_root,
            ),
            "capture boundary depth5 stage evidence",
        )
        _require_failure_evidence_absent(
            (
                manifest_failure_path,
                exact_protocol_failure_path,
                exact_run_failure_path,
                depth_protocol_failure_path,
                depth_run_failure_path,
            )
        )
        _require_head_unchanged(repository, commit)
        phase = "DEPTH5_COMPLETION_RECORD"
        record = {
            **attempt,
            "status": "COMPLETED",
            "completed_at": _timestamp(_utc_now()),
            **_depth5_narrative(result),
            "results": result,
        }
        _validate_completed_narrative(
            record, result, _depth5_narrative, "capture boundary depth5"
        )
        destination = run_directory / "run.json"
        _write_exclusive(destination, record)
        _exact_byte_hashes(
            (*stage_evidence_entries, (destination, _encoded_json(record))),
            "capture boundary completed depth5 chain",
            anchor=output_root,
        )
        _require_chain_unchanged(stage_evidence_hashes)
        _require_chain_unchanged(chain_hashes)
        _require_authenticated_snapshot_unchanged(
            frozen_worktree_hashes,
            _authenticated_frozen_worktree_hashes(repository, commit),
            "frozen worktree",
        )
        _require_authenticated_snapshot_unchanged(
            frozen_source_hashes,
            _frozen_source_chain_hashes(repository),
            "frozen source chain",
        )
        _require_failure_evidence_absent(
            (
                manifest_failure_path,
                exact_protocol_failure_path,
                exact_run_failure_path,
                depth_protocol_failure_path,
                depth_run_failure_path,
            )
        )
        _require_head_unchanged(repository, commit)
    except BaseException as error:
        _record_failure_preserving_original(
            run_directory / "failure.json", attempt, phase, error
        )
        raise
    return destination


if len(
    {
        CAPTURE_BOUNDARY_MANIFEST_PROTOCOL_ID,
        CAPTURE_BOUNDARY_EXACT_PROTOCOL_ID,
        CAPTURE_BOUNDARY_DEPTH5_PROTOCOL_ID,
    }
) != 3:
    raise RuntimeError("capture boundary stages require three distinct protocol IDs")
