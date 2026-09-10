"""Fail-closed one-shot runners for the Plan 0010 two-runner experiment.

Scientific selection and evaluation live in :mod:`parity_forge.two_runner` and
:mod:`parity_forge.two_runner_evaluation`.  This module owns only the irreversible
edge: fixed historical bytes, canonical paths, Git lineage, reservations,
attempts, failures, byte seals, and stage ordering.
"""

from __future__ import annotations

import copy
import hashlib
import os
import platform
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Sequence, Tuple

from . import __version__
from .batch import PlayGates
from .capture_boundary_experiments import (
    CAPTURE_BOUNDARY_LOCK_RELATIVE,
    CAPTURE_BOUNDARY_MANIFEST_RELATIVE,
    _canonical_equal,
    _chain_hashes,
    _exact_byte_hashes,
    _frozen_source_chain_hashes as _boundary_source_chain_hashes,
    _git_blob_sha,
    _load_evaluated_registry,
    _load_pinned_exclusion_sources,
    _load_supporting_dependencies,
    _record_failure_preserving_original,
    _require_authenticated_snapshot_unchanged,
    _require_canonical_path,
    _require_chain_unchanged,
    _require_commit_precedes,
    _require_failure_evidence_absent,
    _require_head_unchanged,
    _require_no_symlink_below,
    _validate_frozen_capture_boundary_manifest,
)
from .experiments import _timestamp, _utc_now
from .landscape_experiments import (
    _assert_no_outcome_keys,
    _encoded_json,
    _frozen_source_fingerprints_at_commit,
    _read_json_bytes,
    _recorded_repository_root,
    _require_clean_repository,
    _require_commit_ancestor,
    _require_timestamp,
    _require_tracked,
    _reserve_protocol as _base_reserve_protocol,
    _scan_prior_protocol as _base_scan_prior_protocol,
    _validate_completed_run_attempt,
    _validate_protocol_reservation,
    _write_exclusive,
)
from .two_runner import (
    TWO_RUNNER_CLOSED_PROJECTION_BUNDLE_ROOT,
    TWO_RUNNER_EXECUTABLE_FINGERPRINT_PATHS,
    TWO_RUNNER_EXACT_MAX_STATES,
    TWO_RUNNER_HISTORICAL_ARTIFACT_COUNT,
    TWO_RUNNER_MANIFEST_ID,
    TWO_RUNNER_MANIFEST_PROTOCOL_ID,
    TWO_RUNNER_PAIR_COUNT,
    TWO_RUNNER_PLAN0009_MANIFEST_CHAIN,
    TWO_RUNNER_SOURCE_STATE_BOUND,
    TWO_RUNNER_TREATMENT_STATE_BOUND,
    build_two_runner_closed_projection_bundle,
    build_two_runner_manifest,
    validate_two_runner_closed_projection_bundle,
    validate_two_runner_manifest,
)
from . import two_runner_evaluation as _evaluation


TWO_RUNNER_EXACT_PROTOCOL_ID = "two-runner-v1-paired-exact"
TWO_RUNNER_DEPTH5_PROTOCOL_ID = "two-runner-v1-fixed-depth5"

TWO_RUNNER_CORPUS_RELATIVE = Path("experiments/corpora/two-runner-v1")
TWO_RUNNER_MANIFEST_RESERVATION_RELATIVE = (
    TWO_RUNNER_CORPUS_RELATIVE / "manifest-reservation.json"
)
TWO_RUNNER_MANIFEST_ATTEMPT_RELATIVE = (
    TWO_RUNNER_CORPUS_RELATIVE / "manifest-attempt.json"
)
TWO_RUNNER_EXCLUSION_LEDGER_RELATIVE = (
    TWO_RUNNER_CORPUS_RELATIVE / "exclusion-ledger.json"
)
TWO_RUNNER_MANIFEST_RELATIVE = TWO_RUNNER_CORPUS_RELATIVE / "manifest.json"
TWO_RUNNER_LOCK_RELATIVE = TWO_RUNNER_CORPUS_RELATIVE / "manifest.lock.json"

TWO_RUNNER_DEPTH5_SEEDS = tuple(range(30))
TWO_RUNNER_DEPTH5_DEPTH = 5
TWO_RUNNER_DEPTH5_MAX_NODES = 5_000_000

_PROTOCOL_PLAN_RELATIVE = Path(
    "docs/plans/active/0010-two-runner-existing-dsl-family-viability.md"
)
_FROZEN_PROTOCOL_RELATIVES = (_PROTOCOL_PLAN_RELATIVE,)
_FROZEN_EXECUTABLE_RELATIVES = tuple(
    Path(path) for path in TWO_RUNNER_EXECUTABLE_FINGERPRINT_PATHS
)

_MANIFEST_COMPONENT_VERSIONS = {
    "parity_forge": __version__,
    "baseline_dsl_schema": 1,
    "treatment_dsl_schema": 1,
    "d4_canonicalization": 1,
    "two_runner_selection": 1,
    "closed_projection_bundle": 1,
}
_EXACT_COMPONENT_VERSIONS = {
    "parity_forge": __version__,
    "baseline_dsl_schema": 1,
    "treatment_dsl_schema": 1,
    "engine": 3,
    "exact_solver": 1,
    "two_runner_exact": 1,
    "runner_lineage": 1,
}
_DEPTH5_COMPONENT_VERSIONS = {
    "parity_forge": __version__,
    "baseline_dsl_schema": 1,
    "treatment_dsl_schema": 1,
    "engine": 3,
    "play_evaluator": 1,
    "minimax_agent": 1,
    "two_runner_depth5": 1,
    "runner_lineage": 1,
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


def _merged_chain_hashes(
    *snapshots: Mapping[str, str],
) -> Mapping[str, str]:
    """Merge authenticated snapshots without masking inconsistent duplicates."""

    merged: Dict[str, str] = {}
    for snapshot in snapshots:
        for path, digest in snapshot.items():
            previous = merged.get(path)
            if previous is not None and previous != digest:
                raise ValueError("authenticated chain has inconsistent duplicate bytes")
            merged[path] = digest
    return merged


def _scan_prior_protocol(output_root: Path, protocol_id: str) -> None:
    """Reject hidden, broken-link, and ordinary prior one-shot evidence."""

    reservation = output_root / ".{}.reservation.json".format(protocol_id)
    _require_no_symlink_below(reservation, output_root, "protocol reservation")
    if reservation.is_symlink():
        raise ValueError("protocol reservation cannot be a symlink")
    if output_root.exists():
        for run_directory in output_root.iterdir():
            if run_directory.is_symlink():
                raise ValueError("experiment output cannot contain an internal symlink")
            if not run_directory.is_dir():
                continue
            for filename in ("attempt.json", "run.json", "failure.json"):
                evidence = run_directory / filename
                if evidence.is_symlink():
                    raise ValueError("experiment evidence cannot be a symlink")
    _base_scan_prior_protocol(output_root, protocol_id)


def _reserve_protocol(
    output_root: Path,
    protocol_id: str,
    run_id: str,
    commit: str,
    started_at: str,
) -> Path:
    """Create the canonical reservation without following a broken link."""

    reservation = output_root / ".{}.reservation.json".format(protocol_id)
    _require_no_symlink_below(reservation, output_root, "protocol reservation")
    if reservation.exists() or reservation.is_symlink():
        raise ValueError("protocol already has reservation evidence")
    return _base_reserve_protocol(
        output_root, protocol_id, run_id, commit, started_at
    )


def _manifest_chain_paths(repository: Path) -> Tuple[Path, ...]:
    return (
        repository / TWO_RUNNER_MANIFEST_RESERVATION_RELATIVE,
        repository / TWO_RUNNER_MANIFEST_ATTEMPT_RELATIVE,
        repository / TWO_RUNNER_EXCLUSION_LEDGER_RELATIVE,
        repository / TWO_RUNNER_MANIFEST_RELATIVE,
        repository / TWO_RUNNER_LOCK_RELATIVE,
    )


def _plan0009_chain_paths(repository: Path) -> Tuple[Path, ...]:
    return tuple(repository / Path(record["path"]) for record in TWO_RUNNER_PLAN0009_MANIFEST_CHAIN)


def _frozen_worktree_paths(repository: Path) -> Tuple[Path, ...]:
    return tuple(
        repository / relative
        for relative in (*_FROZEN_PROTOCOL_RELATIVES, *_FROZEN_EXECUTABLE_RELATIVES)
    )


def _authenticated_frozen_worktree_hashes(
    repository: Path, commit: str
) -> Mapping[str, str]:
    """Bind current protocol/executable bytes directly to commit blobs."""

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
    observed = _chain_hashes(_frozen_worktree_paths(repository), anchor=repository)
    observed_relative = {
        str(Path(absolute).resolve().relative_to(repository.resolve())): digest
        for absolute, digest in observed.items()
    }
    if not _canonical_equal(observed_relative, expected):
        raise ValueError("two-runner worktree differs from authenticated commit blobs")
    return observed


def _plan0009_manifest_chain(
    repository: Path,
) -> Tuple[Mapping[str, Any], Tuple[Mapping[str, Any], ...], Mapping[str, str]]:
    """Authenticate the outcome-free Plan 0009 chain, never its outcome runs."""

    paths = _plan0009_chain_paths(repository)
    entries = []
    metadata = []
    manifest: Mapping[str, Any] | None = None
    for path, spec in zip(paths, TWO_RUNNER_PLAN0009_MANIFEST_CHAIN):
        relative = Path(spec["path"])
        _require_canonical_path(path, repository, relative, "Plan-0009 manifest chain")
        _require_tracked(path, repository, "Plan-0009 manifest chain")
        source_bytes, value = _read_json_bytes(path, "Plan-0009 manifest chain")
        if source_bytes != _encoded_json(value):
            raise ValueError("Plan-0009 manifest chain is not canonical JSON")
        if _sha256(source_bytes) != spec["sha256"]:
            raise ValueError("Plan-0009 manifest chain SHA-256 mismatch")
        entries.append((path, source_bytes))
        metadata.append(dict(spec))
        if relative == CAPTURE_BOUNDARY_MANIFEST_RELATIVE:
            manifest = value
    if manifest is None:
        raise ValueError("Plan-0009 outcome-free manifest is missing")
    validated_bytes, validated_manifest, _ = _validate_frozen_capture_boundary_manifest(
        repository / CAPTURE_BOUNDARY_MANIFEST_RELATIVE,
        repository / CAPTURE_BOUNDARY_LOCK_RELATIVE,
        repository,
    )
    if (
        validated_bytes != (repository / CAPTURE_BOUNDARY_MANIFEST_RELATIVE).read_bytes()
        or not _canonical_equal(validated_manifest, manifest)
    ):
        raise ValueError("Plan-0009 manifest chain does not match public reconstruction")
    hashes = _exact_byte_hashes(
        tuple(entries), "Plan-0009 manifest chain", anchor=repository
    )
    return manifest, tuple(metadata), hashes


def _closed_projection_inputs(repository: Path) -> Mapping[str, Any]:
    source_records, source_metadata = _load_pinned_exclusion_sources(repository)
    supporting_records, supporting_metadata = _load_supporting_dependencies(repository)
    coverage_records, coverage_registry = _load_evaluated_registry(repository)
    plan0009_manifest, plan0009_chain, plan0009_hashes = _plan0009_manifest_chain(
        repository
    )
    return {
        "source_records": source_records,
        "source_metadata": source_metadata,
        "supporting_dependency_records": supporting_records,
        "supporting_dependency_metadata": supporting_metadata,
        "coverage_records": coverage_records,
        "coverage_registry": coverage_registry,
        "plan0009_manifest": plan0009_manifest,
        "plan0009_manifest_chain": plan0009_chain,
        "plan0009_chain_hashes": plan0009_hashes,
    }


def _closed_source_chain_hashes(
    repository: Path, plan0009_hashes: Mapping[str, str] | None = None
) -> Mapping[str, str]:
    hashes = dict(_boundary_source_chain_hashes(repository))
    observed_plan0009 = (
        dict(plan0009_hashes)
        if plan0009_hashes is not None
        else dict(_plan0009_manifest_chain(repository)[2])
    )
    for path, digest in observed_plan0009.items():
        previous = hashes.get(path)
        if previous is not None and previous != digest:
            raise ValueError("two-runner source chain has inconsistent duplicate bytes")
        hashes[path] = digest
    return hashes


def _manifest_configuration(corpus_directory: Path) -> Mapping[str, Any]:
    return {
        "destination": str(corpus_directory.resolve()),
        "closed_projection_bundle_root": TWO_RUNNER_CLOSED_PROJECTION_BUNDLE_ROOT,
        "historical_artifact_count": TWO_RUNNER_HISTORICAL_ARTIFACT_COUNT,
        "pair_count": TWO_RUNNER_PAIR_COUNT,
        "case_membership_outcome_fields_consulted": False,
        "two_runner_treatment_outcomes_computed": False,
    }


def _manifest_provenance(
    repository: Path,
    commit: str,
    created_at: str,
    ledger_bytes: bytes,
    closed_bundle: Mapping[str, Any],
    plan0009_chain: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any]:
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
        "protocol_id": TWO_RUNNER_MANIFEST_PROTOCOL_ID,
        "protocol_plan": {
            "path": str(_PROTOCOL_PLAN_RELATIVE),
            "sha256": plan_sha,
            "git_blob_sha": _git_blob_sha(
                repository, commit, _PROTOCOL_PLAN_RELATIVE
            ),
        },
        "protocol_fingerprints": protocol_fingerprints,
        "executable_fingerprints": executable_fingerprints,
        "closed_projection_bundle": {
            "path": str(TWO_RUNNER_EXCLUSION_LEDGER_RELATIVE),
            "bundle_root": closed_bundle["bundle_root"],
            "sha256": _sha256(ledger_bytes),
            "bytes": len(ledger_bytes),
        },
        "plan0009_manifest_chain": copy.deepcopy(list(plan0009_chain)),
        "selection_inputs": "authenticated-definition-projections-only",
        "independent_review": "PASSED",
    }


def freeze_two_runner_manifest(corpus_directory: Path, repository: Path) -> Path:
    """Reserve and freeze the reviewed outcome-free 64-pair manifest once."""

    _require_canonical_path(
        corpus_directory,
        repository,
        TWO_RUNNER_CORPUS_RELATIVE,
        "two-runner corpus directory",
    )
    if corpus_directory.exists() or corpus_directory.is_symlink():
        raise ValueError("two-runner manifest already has reserved evidence")
    commit = _require_clean_repository(repository)
    frozen_worktree_hashes = _authenticated_frozen_worktree_hashes(repository, commit)
    started_at = _timestamp(_utc_now())
    corpus_directory.mkdir(parents=False, exist_ok=False)
    reservation = {
        "run_id": TWO_RUNNER_MANIFEST_ID,
        "protocol_id": TWO_RUNNER_MANIFEST_PROTOCOL_ID,
        "status": "RESERVED",
        "reserved_at": started_at,
        "git_commit": commit,
    }
    attempt = {
        "run_id": TWO_RUNNER_MANIFEST_ID,
        "protocol_id": TWO_RUNNER_MANIFEST_PROTOCOL_ID,
        "experiment_type": "two-runner-v1-outcome-free-paired-manifest",
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
        _write_exclusive(corpus_directory / "manifest-reservation.json", reservation)
        _write_exclusive(corpus_directory / "manifest-attempt.json", attempt)
        phase = "CLOSED_SOURCE_AUTHENTICATION"
        inputs = _closed_projection_inputs(repository)
        source_hashes = _closed_source_chain_hashes(
            repository, inputs["plan0009_chain_hashes"]
        )
        phase = "CLOSED_PROJECTION_RECONSTRUCTION"
        builder_inputs = {
            key: copy.deepcopy(inputs[key])
            for key in (
                "source_records",
                "source_metadata",
                "supporting_dependency_records",
                "supporting_dependency_metadata",
                "coverage_records",
                "coverage_registry",
                "plan0009_manifest",
            )
        }
        closed_bundle = build_two_runner_closed_projection_bundle(**builder_inputs)
        validate_two_runner_closed_projection_bundle(closed_bundle, **builder_inputs)
        if closed_bundle.get("bundle_root") != TWO_RUNNER_CLOSED_PROJECTION_BUNDLE_ROOT:
            raise ValueError("two-runner closed projection bundle root mismatch")
        _assert_no_outcome_keys(closed_bundle, "two_runner_closed_projection_bundle")
        ledger_bytes = _encoded_json(closed_bundle)
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
        stage_hashes = _exact_byte_hashes(
            stage_evidence_entries,
            "two-runner manifest stage evidence",
            anchor=repository,
        )
        phase = "MANIFEST_CONSTRUCTION"
        provenance = _manifest_provenance(
            repository,
            commit,
            started_at,
            ledger_bytes,
            closed_bundle,
            inputs["plan0009_manifest_chain"],
        )
        evaluated = closed_bundle["evaluated_orbit_projection"]
        historical = closed_bundle["historical_definition_projection"]
        manifest = build_two_runner_manifest(
            copy.deepcopy(evaluated),
            copy.deepcopy(historical),
            copy.deepcopy(provenance),
        )
        pairs = validate_two_runner_manifest(manifest, evaluated, historical)
        if len(pairs) != TWO_RUNNER_PAIR_COUNT:
            raise ValueError("two-runner manifest pair count mismatch")
        if not _canonical_equal(manifest.get("provenance"), provenance):
            raise ValueError("two-runner manifest provenance mismatch")
        if manifest["source"]["closed_projection_bundle_root"] != closed_bundle[
            "bundle_root"
        ]:
            raise ValueError("two-runner manifest does not bind the closed bundle")
        _require_authenticated_snapshot_unchanged(
            frozen_worktree_hashes,
            _authenticated_frozen_worktree_hashes(repository, commit),
            "frozen worktree",
        )
        _require_authenticated_snapshot_unchanged(
            source_hashes,
            _closed_source_chain_hashes(repository),
            "two-runner source chain",
        )
        _require_authenticated_snapshot_unchanged(
            stage_hashes,
            _exact_byte_hashes(
                stage_evidence_entries,
                "two-runner manifest stage evidence",
                anchor=repository,
            ),
            "two-runner manifest stage evidence",
        )
        _require_failure_evidence_absent(
            (corpus_directory / "manifest-failure.json",)
        )
        _require_head_unchanged(repository, commit)
        phase = "MANIFEST_COMPLETION_RECORD"
        manifest_bytes = _encoded_json(manifest)
        manifest_path = corpus_directory / "manifest.json"
        with manifest_path.open("xb") as destination:
            destination.write(manifest_bytes)
        lock = {
            "manifest_id": TWO_RUNNER_MANIFEST_ID,
            "protocol_id": TWO_RUNNER_MANIFEST_PROTOCOL_ID,
            "projection_bundle_root": closed_bundle["bundle_root"],
            "projection_bundle_sha256": _sha256(ledger_bytes),
            "projection_bundle_bytes": len(ledger_bytes),
            "manifest_sha256": _sha256(manifest_bytes),
            "manifest_bytes": len(manifest_bytes),
            "freezer_git_commit": commit,
        }
        lock_path = corpus_directory / "manifest.lock.json"
        _write_exclusive(lock_path, lock)
        completed_chain_hashes = _exact_byte_hashes(
            (
                *stage_evidence_entries,
                (manifest_path, manifest_bytes),
                (lock_path, _encoded_json(lock)),
            ),
            "two-runner completed manifest chain",
            anchor=repository,
        )
        _require_chain_unchanged(stage_hashes)
        _require_authenticated_snapshot_unchanged(
            frozen_worktree_hashes,
            _authenticated_frozen_worktree_hashes(repository, commit),
            "frozen worktree",
        )
        _require_authenticated_snapshot_unchanged(
            source_hashes,
            _closed_source_chain_hashes(repository),
            "two-runner source chain",
        )
        _require_failure_evidence_absent(
            (corpus_directory / "manifest-failure.json",)
        )
        _require_head_unchanged(repository, commit)
        _require_chain_unchanged(
            _merged_chain_hashes(
                completed_chain_hashes, frozen_worktree_hashes, source_hashes
            )
        )
    except BaseException as error:
        _record_failure_preserving_original(
            corpus_directory / "manifest-failure.json", attempt, phase, error
        )
        raise
    return manifest_path


def _require_frozen_lineage(
    repository: Path, manifest: Mapping[str, Any], current_commit: str
) -> None:
    provenance = manifest.get("provenance")
    if not isinstance(provenance, Mapping):
        raise ValueError("two-runner manifest provenance is missing")
    freezer_commit = _require_commit_ancestor(
        provenance.get("freezer_git_commit"),
        repository,
        "two-runner freezer commit",
    )
    _require_commit_ancestor(current_commit, repository, "two-runner stage commit")
    _require_commit_precedes(
        freezer_commit,
        current_commit,
        repository,
        "two-runner freezer-to-stage lineage",
    )
    protocol = provenance.get("protocol_fingerprints")
    executables = provenance.get("executable_fingerprints")
    if not isinstance(protocol, Mapping) or not isinstance(executables, Mapping):
        raise ValueError("two-runner frozen fingerprints are missing")
    protocol_paths = tuple(Path(path) for path in protocol)
    executable_paths = tuple(Path(path) for path in executables)
    for commit, label in ((freezer_commit, "freezer"), (current_commit, "stage")):
        if not _canonical_equal(
            _frozen_source_fingerprints_at_commit(repository, commit, protocol_paths),
            protocol,
        ) or not _canonical_equal(
            _frozen_source_fingerprints_at_commit(
                repository, commit, executable_paths
            ),
            executables,
        ):
            raise ValueError(
                "two-runner {} commit changed frozen sources".format(label)
            )
    plan = provenance.get("protocol_plan")
    if (
        not isinstance(plan, Mapping)
        or plan.get("path") != str(_PROTOCOL_PLAN_RELATIVE)
        or plan.get("sha256") != protocol.get(str(_PROTOCOL_PLAN_RELATIVE))
        or plan.get("git_blob_sha")
        != _git_blob_sha(repository, freezer_commit, _PROTOCOL_PLAN_RELATIVE)
    ):
        raise ValueError("two-runner historical protocol plan mismatch")


def _validate_frozen_two_runner_manifest(
    manifest_path: Path, lock_path: Path, repository: Path
) -> Tuple[bytes, Mapping[str, Any], Mapping[str, Any], Mapping[str, str]]:
    failure_path = repository / TWO_RUNNER_CORPUS_RELATIVE / "manifest-failure.json"
    _require_failure_evidence_absent((failure_path,))
    _require_canonical_path(
        manifest_path, repository, TWO_RUNNER_MANIFEST_RELATIVE, "two-runner manifest"
    )
    _require_canonical_path(
        lock_path, repository, TWO_RUNNER_LOCK_RELATIVE, "two-runner manifest lock"
    )
    chain = _manifest_chain_paths(repository)
    relatives = (
        TWO_RUNNER_MANIFEST_RESERVATION_RELATIVE,
        TWO_RUNNER_MANIFEST_ATTEMPT_RELATIVE,
        TWO_RUNNER_EXCLUSION_LEDGER_RELATIVE,
        TWO_RUNNER_MANIFEST_RELATIVE,
        TWO_RUNNER_LOCK_RELATIVE,
    )
    values = []
    chain_entries = []
    for path, relative in zip(chain, relatives):
        _require_canonical_path(path, repository, relative, "two-runner manifest chain")
        _require_tracked(path, repository, "two-runner manifest chain")
        source_bytes, value = _read_json_bytes(path, "two-runner manifest chain")
        if source_bytes != _encoded_json(value):
            raise ValueError("two-runner manifest chain is not canonical JSON")
        values.append(value)
        chain_entries.append((path, source_bytes))
    reservation, attempt, ledger, manifest, lock = values
    reservation_bytes, attempt_bytes, ledger_bytes, manifest_bytes, lock_bytes = (
        source_bytes for _, source_bytes in chain_entries
    )
    authenticated_chain_hashes = _exact_byte_hashes(
        tuple(chain_entries), "two-runner frozen manifest chain", anchor=repository
    )
    freezer_commit = attempt.get("git_commit")
    expected_reservation = {
        "run_id": TWO_RUNNER_MANIFEST_ID,
        "protocol_id": TWO_RUNNER_MANIFEST_PROTOCOL_ID,
        "status": "RESERVED",
        "reserved_at": attempt.get("started_at"),
        "git_commit": freezer_commit,
    }
    expected_lock = {
        "manifest_id": TWO_RUNNER_MANIFEST_ID,
        "protocol_id": TWO_RUNNER_MANIFEST_PROTOCOL_ID,
        "projection_bundle_root": ledger.get("bundle_root")
        if isinstance(ledger, Mapping)
        else None,
        "projection_bundle_sha256": _sha256(ledger_bytes),
        "projection_bundle_bytes": len(ledger_bytes),
        "manifest_sha256": _sha256(manifest_bytes),
        "manifest_bytes": len(manifest_bytes),
        "freezer_git_commit": freezer_commit,
    }
    if not _canonical_equal(reservation, expected_reservation):
        raise ValueError("two-runner manifest reservation mismatch")
    if not _canonical_equal(lock, expected_lock):
        raise ValueError("two-runner manifest lock does not match exact bytes")
    if (
        set(attempt) != _ATTEMPT_KEYS
        or attempt.get("run_id") != TWO_RUNNER_MANIFEST_ID
        or attempt.get("protocol_id") != TWO_RUNNER_MANIFEST_PROTOCOL_ID
        or attempt.get("experiment_type")
        != "two-runner-v1-outcome-free-paired-manifest"
        or attempt.get("status") != "STARTED"
        or attempt.get("git_dirty") is not False
        or not _canonical_equal(
            attempt.get("component_versions"), _MANIFEST_COMPONENT_VERSIONS
        )
        or not _canonical_equal(
            attempt.get("configuration"),
            _manifest_configuration(repository / TWO_RUNNER_CORPUS_RELATIVE),
        )
    ):
        raise ValueError("two-runner manifest attempt mismatch")
    environment = attempt.get("environment")
    if (
        not isinstance(environment, Mapping)
        or set(environment) != {"python", "platform"}
        or not all(isinstance(value, str) for value in environment.values())
    ):
        raise ValueError("two-runner manifest environment mismatch")
    _require_timestamp(attempt.get("started_at"), "two-runner manifest start")
    _require_commit_ancestor(
        freezer_commit, repository, "two-runner manifest freezer commit"
    )
    inputs = _closed_projection_inputs(repository)
    source_hashes = _closed_source_chain_hashes(
        repository, inputs["plan0009_chain_hashes"]
    )
    builder_inputs = {
        key: copy.deepcopy(inputs[key])
        for key in (
            "source_records",
            "source_metadata",
            "supporting_dependency_records",
            "supporting_dependency_metadata",
            "coverage_records",
            "coverage_registry",
            "plan0009_manifest",
        )
    }
    reconstructed = build_two_runner_closed_projection_bundle(**builder_inputs)
    if not _canonical_equal(ledger, reconstructed):
        raise ValueError("two-runner closed projection bundle is not reproducible")
    projections = validate_two_runner_closed_projection_bundle(
        ledger, **builder_inputs
    )
    if ledger["bundle_root"] != TWO_RUNNER_CLOSED_PROJECTION_BUNDLE_ROOT:
        raise ValueError("two-runner closed projection bundle root mismatch")
    expected_provenance = _manifest_provenance(
        repository,
        freezer_commit,
        attempt["started_at"],
        ledger_bytes,
        ledger,
        inputs["plan0009_manifest_chain"],
    )
    pairs = validate_two_runner_manifest(
        manifest,
        projections["evaluated_orbit_projection"],
        projections["historical_definition_projection"],
    )
    if len(pairs) != TWO_RUNNER_PAIR_COUNT:
        raise ValueError("two-runner manifest pair count mismatch")
    if not _canonical_equal(manifest.get("provenance"), expected_provenance):
        raise ValueError("two-runner manifest provenance is not reproducible")
    if manifest["source"]["closed_projection_bundle_root"] != ledger["bundle_root"]:
        raise ValueError("two-runner manifest closed-bundle reference mismatch")
    _assert_no_outcome_keys(ledger, "two_runner_closed_projection_bundle")
    _require_authenticated_snapshot_unchanged(
        authenticated_chain_hashes,
        _exact_byte_hashes(
            tuple(chain_entries),
            "two-runner frozen manifest chain",
            anchor=repository,
        ),
        "two-runner frozen manifest chain",
    )
    _require_authenticated_snapshot_unchanged(
        source_hashes,
        _closed_source_chain_hashes(repository),
        "two-runner source chain",
    )
    _require_failure_evidence_absent((failure_path,))
    complete_chain_hashes = _merged_chain_hashes(
        authenticated_chain_hashes, source_hashes
    )
    return manifest_bytes, manifest, ledger, complete_chain_hashes


def _manifest_validator(
    closed_bundle: Mapping[str, Any],
) -> Callable[[Any], Any]:
    evaluated = copy.deepcopy(closed_bundle["evaluated_orbit_projection"])
    historical = copy.deepcopy(closed_bundle["historical_definition_projection"])

    def validate(value: Any) -> Any:
        return validate_two_runner_manifest(value, evaluated, historical)

    return validate


def _exact_configuration(
    manifest_path: Path, manifest_bytes: bytes
) -> Mapping[str, Any]:
    return {
        "manifest_id": TWO_RUNNER_MANIFEST_ID,
        "manifest_path": str(manifest_path.resolve()),
        "manifest_sha256": _sha256(manifest_bytes),
        "closed_projection_bundle_root": TWO_RUNNER_CLOSED_PROJECTION_BUNDLE_ROOT,
        "pair_count": TWO_RUNNER_PAIR_COUNT,
        "max_exact_states": TWO_RUNNER_EXACT_MAX_STATES,
        "source_structural_state_bound": TWO_RUNNER_SOURCE_STATE_BOUND,
        "treatment_structural_state_bound": TWO_RUNNER_TREATMENT_STATE_BOUND,
        "phase_order": [
            "SOURCE_EXACT",
            "SOURCE_SEAL",
            "TREATMENT_EXACT",
            "PAIRED_RESULT",
        ],
    }


def _depth5_configuration(
    manifest_path: Path,
    manifest_bytes: bytes,
    exact_path: Path,
    exact_bytes: bytes,
    exact_record: Mapping[str, Any],
) -> Mapping[str, Any]:
    return {
        "manifest_id": TWO_RUNNER_MANIFEST_ID,
        "manifest_path": str(manifest_path.resolve()),
        "manifest_sha256": _sha256(manifest_bytes),
        "closed_projection_bundle_root": TWO_RUNNER_CLOSED_PROJECTION_BUNDLE_ROOT,
        "source_exact_run_id": exact_record["run_id"],
        "source_exact_path": str(exact_path.resolve()),
        "source_exact_sha256": _sha256(exact_bytes),
        "pair_count": TWO_RUNNER_PAIR_COUNT,
        "profile_count": TWO_RUNNER_PAIR_COUNT * 2,
        "seeds": list(TWO_RUNNER_DEPTH5_SEEDS),
        "depth": TWO_RUNNER_DEPTH5_DEPTH,
        "max_nodes_per_definition": TWO_RUNNER_DEPTH5_MAX_NODES,
        "play_gates": asdict(PlayGates()),
        "phase_order": [
            "SOURCE_DEPTH5",
            "SOURCE_SEAL",
            "TREATMENT_DEPTH5",
            "PAIRED_RESULT",
        ],
        "adaptive_eligibility": False,
        "candidate_cap": None,
        "replacement": False,
    }


def _validate_exact_configuration(
    configuration: Any, manifest: Mapping[str, Any]
) -> None:
    expected_keys = {
        "manifest_id",
        "manifest_path",
        "manifest_sha256",
        "closed_projection_bundle_root",
        "pair_count",
        "max_exact_states",
        "source_structural_state_bound",
        "treatment_structural_state_bound",
        "phase_order",
    }
    if not isinstance(configuration, Mapping) or set(configuration) != expected_keys:
        raise ValueError("two-runner exact configuration schema mismatch")
    expected = _exact_configuration(
        Path(str(configuration.get("manifest_path"))), _encoded_json(manifest)
    )
    if not _canonical_equal(configuration, expected):
        raise ValueError("two-runner exact configuration mismatch")
    _recorded_repository_root(
        configuration["manifest_path"],
        TWO_RUNNER_MANIFEST_RELATIVE,
        "two-runner exact manifest path",
    )


def _validate_depth5_configuration(
    configuration: Any,
    manifest: Mapping[str, Any],
    exact_record: Mapping[str, Any],
) -> None:
    if not isinstance(configuration, Mapping):
        raise ValueError("two-runner depth5 configuration schema mismatch")
    expected = _depth5_configuration(
        Path(str(configuration.get("manifest_path"))),
        _encoded_json(manifest),
        Path(str(configuration.get("source_exact_path"))),
        _encoded_json(exact_record),
        exact_record,
    )
    if set(configuration) != set(expected) or not _canonical_equal(
        configuration, expected
    ):
        raise ValueError("two-runner depth5 configuration mismatch")
    manifest_root = _recorded_repository_root(
        configuration["manifest_path"],
        TWO_RUNNER_MANIFEST_RELATIVE,
        "two-runner depth5 manifest path",
    )
    exact_relative = Path("experiments/runs") / str(exact_record["run_id"]) / "run.json"
    exact_root = _recorded_repository_root(
        configuration["source_exact_path"],
        exact_relative,
        "two-runner depth5 exact path",
    )
    if manifest_root != exact_root:
        raise ValueError("two-runner depth5 configuration roots differ")


def _exact_narrative(result: Mapping[str, Any]) -> Mapping[str, Any]:
    aggregate = result.get("aggregate")
    timing = result.get("timing")
    if not isinstance(aggregate, Mapping) or not isinstance(timing, Mapping):
        raise ValueError("two-runner exact narrative requires aggregate and timing")
    censored = aggregate.get("exact_censored_count")
    if type(censored) is not int or censored < 0:
        raise ValueError("two-runner exact censor count is missing")
    return {
        "hypothesis": "A second ordinary B runner may create non-dominant counterplay without changing schema-v1 rules.",
        "baseline": "All 64 one-runner sources are solved and sealed before treatment.",
        "treatment": "All 64 same-frame two-runner treatments are then solved under the fixed cap.",
        "expected_result": "All 128 exact slots complete below their proved structural bounds without PLY_LIMIT.",
        "actual_result": {**dict(aggregate), "timing": dict(timing)},
        "interpretation": (
            "Exact evidence is complete."
            if censored == 0
            else "Exact censoring makes downstream conclusions inconclusive."
        ),
        "decision": (
            "COMMIT_EXACT_THEN_RUN_FIXED_DEPTH5"
            if censored == 0
            else "STOP_BEFORE_DEPTH5_AND_AUDIT_EXACT_BOUND"
        ),
    }


def _depth5_narrative(result: Mapping[str, Any]) -> Mapping[str, Any]:
    aggregate = result.get("aggregate")
    timing = result.get("timing")
    if not isinstance(aggregate, Mapping) or not isinstance(timing, Mapping):
        raise ValueError("two-runner depth5 narrative requires aggregate and timing")
    assessments = aggregate.get("assessments")
    overall = assessments.get("overall") if isinstance(assessments, Mapping) else None
    return {
        "hypothesis": "Fixed depth-5 play tests whether two-runner choice survives without role dominance.",
        "baseline": "Every source profile is attempted and sealed before treatment play.",
        "treatment": "Every treatment receives the same fixed seeds, fresh agent, and cumulative node cap.",
        "expected_result": "The complete fixed schedule reconstructs engagement, frontier, and candidate assessments.",
        "actual_result": {**dict(aggregate), "timing": dict(timing)},
        "interpretation": "The result is interpreted only through the frozen Plan 0010 priority.",
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
    expected_reservation = {
        "protocol_id": TWO_RUNNER_EXACT_PROTOCOL_ID,
        "run_id": record.get("run_id"),
        "status": "RESERVED",
        "reserved_at": attempt.get("started_at"),
        "git_commit": attempt.get("git_commit"),
    }
    return _exact_byte_hashes(
        (
            (
                output_root
                / ".{}.reservation.json".format(TWO_RUNNER_EXACT_PROTOCOL_ID),
                _encoded_json(expected_reservation),
            ),
            (exact_run_path.parent / "attempt.json", _encoded_json(attempt)),
            (exact_run_path, _encoded_json(record)),
        ),
        "two-runner exact upstream chain",
        anchor=output_root,
    )


def run_two_runner_paired_exact(
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
        "two-runner exact output",
    )
    manifest_bytes, manifest, closed_bundle, manifest_chain_hashes = (
        _validate_frozen_two_runner_manifest(manifest_path, lock_path, repository)
    )
    commit = _require_clean_repository(repository)
    _require_frozen_lineage(repository, manifest, commit)
    _require_chain_unchanged(manifest_chain_hashes)
    manifest_failure = repository / TWO_RUNNER_CORPUS_RELATIVE / "manifest-failure.json"
    protocol_failure = output_root / ".{}.failure.json".format(
        TWO_RUNNER_EXACT_PROTOCOL_ID
    )
    _require_failure_evidence_absent((manifest_failure, protocol_failure))
    _scan_prior_protocol(output_root, TWO_RUNNER_EXACT_PROTOCOL_ID)
    frozen_worktree_hashes = _authenticated_frozen_worktree_hashes(repository, commit)
    source_hashes = _closed_source_chain_hashes(repository)
    chain_hashes = _merged_chain_hashes(manifest_chain_hashes, source_hashes)
    started = _utc_now()
    started_at = _timestamp(started)
    run_id = "{}-two-runner-exact-{}".format(
        started.strftime("%Y%m%dT%H%M%S%fZ"), _sha256(manifest_bytes)[:8]
    )
    attempt = {
        "run_id": run_id,
        "protocol_id": TWO_RUNNER_EXACT_PROTOCOL_ID,
        "experiment_type": "two-runner-v1-paired-exact",
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
        output_root, TWO_RUNNER_EXACT_PROTOCOL_ID, run_id, commit, started_at
    )
    run_directory = output_root / run_id
    try:
        run_directory.mkdir(parents=False, exist_ok=False)
    except BaseException as error:
        _record_failure_preserving_original(
            protocol_failure, attempt, "EXACT_RUN_DIRECTORY_SETUP", error
        )
        raise
    try:
        _write_exclusive(run_directory / "attempt.json", attempt)
    except BaseException as error:
        _record_failure_preserving_original(
            run_directory / "failure.json", attempt, "EXACT_SETUP", error
        )
        raise
    run_failure = run_directory / "failure.json"
    reservation_path = output_root / ".{}.reservation.json".format(
        TWO_RUNNER_EXACT_PROTOCOL_ID
    )
    stage_entries = (
        (
            reservation_path,
            _encoded_json(
                {
                    "protocol_id": TWO_RUNNER_EXACT_PROTOCOL_ID,
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
        stage_hashes = _exact_byte_hashes(
            stage_entries, "two-runner exact stage evidence", anchor=output_root
        )
        phase = "PAIRED_EXACT_EVALUATION"
        validator = _manifest_validator(closed_bundle)
        result = _evaluation.evaluate_two_runner_exact(
            copy.deepcopy(manifest),
            manifest_validator=validator,
            expected_pair_count=TWO_RUNNER_PAIR_COUNT,
            max_states=TWO_RUNNER_EXACT_MAX_STATES,
        )
        if not isinstance(result, Mapping):
            raise ValueError("two-runner exact evaluator must return an object")
        _evaluation.validate_two_runner_exact_result(
            result,
            manifest,
            manifest_validator=validator,
            expected_pair_count=TWO_RUNNER_PAIR_COUNT,
            max_states=TWO_RUNNER_EXACT_MAX_STATES,
        )
        _require_frozen_lineage(repository, manifest, commit)
        _require_authenticated_snapshot_unchanged(
            frozen_worktree_hashes,
            _authenticated_frozen_worktree_hashes(repository, commit),
            "frozen worktree",
        )
        _require_chain_unchanged(chain_hashes)
        _require_authenticated_snapshot_unchanged(
            source_hashes,
            _closed_source_chain_hashes(repository),
            "two-runner source chain",
        )
        _require_authenticated_snapshot_unchanged(
            stage_hashes,
            _exact_byte_hashes(
                stage_entries,
                "two-runner exact stage evidence",
                anchor=output_root,
            ),
            "two-runner exact stage evidence",
        )
        _require_failure_evidence_absent(
            (manifest_failure, protocol_failure, run_failure)
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
            record, result, _exact_narrative, "two-runner exact"
        )
        destination = run_directory / "run.json"
        _write_exclusive(destination, record)
        completed_chain_hashes = _exact_byte_hashes(
            (*stage_entries, (destination, _encoded_json(record))),
            "two-runner completed exact chain",
            anchor=output_root,
        )
        _require_chain_unchanged(stage_hashes)
        _require_chain_unchanged(chain_hashes)
        _require_authenticated_snapshot_unchanged(
            frozen_worktree_hashes,
            _authenticated_frozen_worktree_hashes(repository, commit),
            "frozen worktree",
        )
        _require_authenticated_snapshot_unchanged(
            source_hashes,
            _closed_source_chain_hashes(repository),
            "two-runner source chain",
        )
        _require_failure_evidence_absent(
            (manifest_failure, protocol_failure, run_failure)
        )
        _require_head_unchanged(repository, commit)
        _require_chain_unchanged(
            _merged_chain_hashes(
                completed_chain_hashes,
                chain_hashes,
                frozen_worktree_hashes,
                source_hashes,
            )
        )
    except BaseException as error:
        _record_failure_preserving_original(run_failure, attempt, phase, error)
        raise
    return destination


def _validate_two_runner_exact_source(
    exact_run_path: Path,
    output_root: Path,
    repository: Path,
    manifest: Mapping[str, Any],
    closed_bundle: Mapping[str, Any],
) -> Tuple[bytes, Mapping[str, Any], Mapping[str, str]]:
    protocol_failure = output_root / ".{}.failure.json".format(
        TWO_RUNNER_EXACT_PROTOCOL_ID
    )
    run_failure = exact_run_path.parent / "failure.json"
    _require_failure_evidence_absent((protocol_failure, run_failure))
    _require_no_symlink_below(
        exact_run_path, output_root, "two-runner exact source"
    )
    if exact_run_path.is_symlink():
        raise ValueError("two-runner exact source cannot be a symlink")
    try:
        relative = exact_run_path.resolve().relative_to(output_root.resolve())
    except ValueError as error:
        raise ValueError("two-runner exact source must be in run directory") from error
    if len(relative.parts) != 2 or relative.parts[1] != "run.json":
        raise ValueError("two-runner exact source must be <run-id>/run.json")
    _require_tracked(exact_run_path, repository, "two-runner exact source")
    exact_bytes, record = _read_json_bytes(exact_run_path, "two-runner exact source")
    if exact_bytes != _encoded_json(record):
        raise ValueError("two-runner exact source is not canonical JSON")
    if (
        set(record) != _COMPLETED_RUN_KEYS
        or record.get("run_id") != relative.parts[0]
        or record.get("protocol_id") != TWO_RUNNER_EXACT_PROTOCOL_ID
        or record.get("experiment_type") != "two-runner-v1-paired-exact"
        or record.get("status") != "COMPLETED"
        or record.get("git_dirty") is not False
        or not _canonical_equal(
            record.get("component_versions"), _EXACT_COMPONENT_VERSIONS
        )
    ):
        raise ValueError("two-runner exact source identity mismatch")
    attempt = _validate_completed_run_attempt(
        exact_run_path, record, repository, _EXACT_COMPONENT_VERSIONS
    )
    _require_type_sensitive_attempt_match(attempt, record, "two-runner exact")
    _validate_protocol_reservation(
        output_root,
        TWO_RUNNER_EXACT_PROTOCOL_ID,
        record["run_id"],
        attempt["git_commit"],
        attempt["started_at"],
        repository,
    )
    authenticated_hashes = _require_exact_source_chain_canonical(
        exact_run_path, output_root, record, attempt
    )
    _require_commit_ancestor(
        attempt["git_commit"], repository, "two-runner exact source commit"
    )
    _require_frozen_lineage(repository, manifest, attempt["git_commit"])
    _validate_exact_configuration(record.get("configuration"), manifest)
    exact_manifest_root = _recorded_repository_root(
        record["configuration"]["manifest_path"],
        TWO_RUNNER_MANIFEST_RELATIVE,
        "two-runner exact manifest path",
    )
    if exact_manifest_root.resolve() != repository.resolve():
        raise ValueError("two-runner exact configuration root mismatch")
    result = record.get("results")
    if not isinstance(result, Mapping):
        raise ValueError("two-runner exact result is missing")
    validator = _manifest_validator(closed_bundle)
    _evaluation.validate_two_runner_exact_result(
        result,
        manifest,
        manifest_validator=validator,
        expected_pair_count=TWO_RUNNER_PAIR_COUNT,
        max_states=TWO_RUNNER_EXACT_MAX_STATES,
    )
    _validate_completed_narrative(record, result, _exact_narrative, "two-runner exact")
    _require_authenticated_snapshot_unchanged(
        authenticated_hashes,
        _require_exact_source_chain_canonical(
            exact_run_path, output_root, record, attempt
        ),
        "two-runner exact upstream chain",
    )
    _require_failure_evidence_absent((protocol_failure, run_failure))
    return exact_bytes, record, authenticated_hashes


def _require_exact_complete_for_depth5(result: Mapping[str, Any]) -> None:
    aggregate = result.get("aggregate")
    count = (
        aggregate.get("exact_censored_count")
        if isinstance(aggregate, Mapping)
        else None
    )
    if type(count) is not int or count < 0:
        raise ValueError("two-runner exact censor count is missing")
    if count != 0:
        raise ValueError("exact censoring blocks two-runner depth5 before reservation")


def run_two_runner_fixed_depth5(
    exact_run_path: Path,
    manifest_path: Path,
    lock_path: Path,
    output_root: Path,
    repository: Path,
) -> Path:
    """Run all source then treatment depth-5 profiles exactly once."""

    _require_canonical_path(
        output_root,
        repository,
        Path("experiments/runs"),
        "two-runner depth5 output",
    )
    manifest_bytes, manifest, closed_bundle, manifest_chain_hashes = (
        _validate_frozen_two_runner_manifest(manifest_path, lock_path, repository)
    )
    exact_bytes, exact_record, exact_chain_hashes = _validate_two_runner_exact_source(
        exact_run_path, output_root, repository, manifest, closed_bundle
    )
    exact_result = exact_record["results"]
    _require_exact_complete_for_depth5(exact_result)
    commit = _require_clean_repository(repository)
    _require_frozen_lineage(repository, manifest, commit)
    _require_commit_ancestor(
        exact_record["git_commit"], repository, "two-runner exact run commit"
    )
    _require_commit_precedes(
        exact_record["git_commit"],
        commit,
        repository,
        "two-runner exact-to-depth5 lineage",
    )
    _require_chain_unchanged(manifest_chain_hashes)
    _require_chain_unchanged(exact_chain_hashes)
    manifest_failure = repository / TWO_RUNNER_CORPUS_RELATIVE / "manifest-failure.json"
    exact_protocol_failure = output_root / ".{}.failure.json".format(
        TWO_RUNNER_EXACT_PROTOCOL_ID
    )
    exact_run_failure = exact_run_path.parent / "failure.json"
    depth_protocol_failure = output_root / ".{}.failure.json".format(
        TWO_RUNNER_DEPTH5_PROTOCOL_ID
    )
    _require_failure_evidence_absent(
        (
            manifest_failure,
            exact_protocol_failure,
            exact_run_failure,
            depth_protocol_failure,
        )
    )
    _scan_prior_protocol(output_root, TWO_RUNNER_DEPTH5_PROTOCOL_ID)
    frozen_worktree_hashes = _authenticated_frozen_worktree_hashes(repository, commit)
    source_hashes = _closed_source_chain_hashes(repository)
    chain_hashes = _merged_chain_hashes(
        manifest_chain_hashes, exact_chain_hashes, source_hashes
    )
    started = _utc_now()
    started_at = _timestamp(started)
    run_id = "{}-two-runner-depth5-{}".format(
        started.strftime("%Y%m%dT%H%M%S%fZ"), _sha256(exact_bytes)[:8]
    )
    attempt = {
        "run_id": run_id,
        "protocol_id": TWO_RUNNER_DEPTH5_PROTOCOL_ID,
        "experiment_type": "two-runner-v1-fixed-depth5",
        "status": "STARTED",
        "started_at": started_at,
        "git_commit": commit,
        "git_dirty": False,
        "environment": {"python": sys.version, "platform": platform.platform()},
        "component_versions": dict(_DEPTH5_COMPONENT_VERSIONS),
        "configuration": _depth5_configuration(
            manifest_path, manifest_bytes, exact_run_path, exact_bytes, exact_record
        ),
    }
    _validate_depth5_configuration(attempt["configuration"], manifest, exact_record)
    _reserve_protocol(
        output_root, TWO_RUNNER_DEPTH5_PROTOCOL_ID, run_id, commit, started_at
    )
    run_directory = output_root / run_id
    try:
        run_directory.mkdir(parents=False, exist_ok=False)
    except BaseException as error:
        _record_failure_preserving_original(
            depth_protocol_failure, attempt, "DEPTH5_RUN_DIRECTORY_SETUP", error
        )
        raise
    try:
        _write_exclusive(run_directory / "attempt.json", attempt)
    except BaseException as error:
        _record_failure_preserving_original(
            run_directory / "failure.json", attempt, "DEPTH5_SETUP", error
        )
        raise
    depth_run_failure = run_directory / "failure.json"
    reservation_path = output_root / ".{}.reservation.json".format(
        TWO_RUNNER_DEPTH5_PROTOCOL_ID
    )
    stage_entries = (
        (
            reservation_path,
            _encoded_json(
                {
                    "protocol_id": TWO_RUNNER_DEPTH5_PROTOCOL_ID,
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
        stage_hashes = _exact_byte_hashes(
            stage_entries, "two-runner depth5 stage evidence", anchor=output_root
        )
        phase = "FIXED_DEPTH5_EVALUATION"
        validator = _manifest_validator(closed_bundle)
        result = _evaluation.evaluate_two_runner_depth5(
            copy.deepcopy(manifest),
            copy.deepcopy(exact_result),
            manifest_validator=validator,
            expected_pair_count=TWO_RUNNER_PAIR_COUNT,
            seeds=TWO_RUNNER_DEPTH5_SEEDS,
            depth=TWO_RUNNER_DEPTH5_DEPTH,
            max_nodes=TWO_RUNNER_DEPTH5_MAX_NODES,
            gates=PlayGates(),
        )
        if not isinstance(result, Mapping):
            raise ValueError("two-runner depth5 evaluator must return an object")
        _evaluation.validate_two_runner_depth5_result(
            result,
            manifest,
            exact_result,
            manifest_validator=validator,
            expected_pair_count=TWO_RUNNER_PAIR_COUNT,
            seeds=TWO_RUNNER_DEPTH5_SEEDS,
            depth=TWO_RUNNER_DEPTH5_DEPTH,
            max_nodes=TWO_RUNNER_DEPTH5_MAX_NODES,
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
            source_hashes,
            _closed_source_chain_hashes(repository),
            "two-runner source chain",
        )
        _require_authenticated_snapshot_unchanged(
            stage_hashes,
            _exact_byte_hashes(
                stage_entries,
                "two-runner depth5 stage evidence",
                anchor=output_root,
            ),
            "two-runner depth5 stage evidence",
        )
        _require_failure_evidence_absent(
            (
                manifest_failure,
                exact_protocol_failure,
                exact_run_failure,
                depth_protocol_failure,
                depth_run_failure,
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
            record, result, _depth5_narrative, "two-runner depth5"
        )
        destination = run_directory / "run.json"
        _write_exclusive(destination, record)
        completed_chain_hashes = _exact_byte_hashes(
            (*stage_entries, (destination, _encoded_json(record))),
            "two-runner completed depth5 chain",
            anchor=output_root,
        )
        _require_chain_unchanged(stage_hashes)
        _require_chain_unchanged(chain_hashes)
        _require_authenticated_snapshot_unchanged(
            frozen_worktree_hashes,
            _authenticated_frozen_worktree_hashes(repository, commit),
            "frozen worktree",
        )
        _require_authenticated_snapshot_unchanged(
            source_hashes,
            _closed_source_chain_hashes(repository),
            "two-runner source chain",
        )
        _require_failure_evidence_absent(
            (
                manifest_failure,
                exact_protocol_failure,
                exact_run_failure,
                depth_protocol_failure,
                depth_run_failure,
            )
        )
        _require_head_unchanged(repository, commit)
        _require_chain_unchanged(
            _merged_chain_hashes(
                completed_chain_hashes,
                chain_hashes,
                frozen_worktree_hashes,
                source_hashes,
            )
        )
    except BaseException as error:
        _record_failure_preserving_original(depth_run_failure, attempt, phase, error)
        raise
    return destination


if getattr(_evaluation, "TWO_RUNNER_EXACT_PROTOCOL_ID", None) != TWO_RUNNER_EXACT_PROTOCOL_ID:
    raise RuntimeError("two-runner exact protocol ID mismatch")
if getattr(_evaluation, "TWO_RUNNER_DEPTH5_PROTOCOL_ID", None) != TWO_RUNNER_DEPTH5_PROTOCOL_ID:
    raise RuntimeError("two-runner depth5 protocol ID mismatch")
if getattr(_evaluation, "TWO_RUNNER_SEEDS", None) != TWO_RUNNER_DEPTH5_SEEDS:
    raise RuntimeError("two-runner depth5 seeds mismatch")
if getattr(_evaluation, "TWO_RUNNER_DEPTH", None) != TWO_RUNNER_DEPTH5_DEPTH:
    raise RuntimeError("two-runner depth mismatch")
if getattr(_evaluation, "TWO_RUNNER_MAX_NODES", None) != TWO_RUNNER_DEPTH5_MAX_NODES:
    raise RuntimeError("two-runner depth5 node cap mismatch")


__all__ = (
    "TWO_RUNNER_MANIFEST_PROTOCOL_ID",
    "TWO_RUNNER_EXACT_PROTOCOL_ID",
    "TWO_RUNNER_DEPTH5_PROTOCOL_ID",
    "TWO_RUNNER_CORPUS_RELATIVE",
    "TWO_RUNNER_EXCLUSION_LEDGER_RELATIVE",
    "TWO_RUNNER_MANIFEST_RELATIVE",
    "TWO_RUNNER_LOCK_RELATIVE",
    "freeze_two_runner_manifest",
    "run_two_runner_paired_exact",
    "run_two_runner_fixed_depth5",
)
