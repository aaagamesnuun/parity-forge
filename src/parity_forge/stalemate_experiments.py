"""Fail-closed one-shot runners for the stalemate-draw experiment.

Scientific behavior lives in :mod:`parity_forge.stalemate`.  This module owns
only historical source pins, Git/byte fingerprints, atomic reservations,
attempt/failure evidence, and stage ordering.
"""

from __future__ import annotations

import copy
import hashlib
import platform
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Sequence, Tuple

from . import __version__
from .batch import PlayGates
from .experiments import _timestamp, _utc_now
from .landscape_evaluation import (
    DRAW_STRESS_DEPTH,
    DRAW_STRESS_MAX_CANDIDATES,
    DRAW_STRESS_MAX_NODES,
    DRAW_STRESS_SEEDS,
    LANDSCAPE_EXACT_MAX_STATES,
    LANDSCAPE_PLAY_SEEDS,
    evaluate_landscape_cases,
)
from .landscape_experiments import (
    LANDSCAPE_MANIFEST_ID,
    LANDSCAPE_MANIFEST_PROTOCOL_ID,
    LANDSCAPE_RAW_PROTOCOL_ID,
    _FROZEN_EXECUTABLE_RELATIVES as _LANDSCAPE_EXECUTABLE_RELATIVES,
    _MANIFEST_COMPONENT_VERSIONS as _LANDSCAPE_MANIFEST_COMPONENT_VERSIONS,
    _RAW_COMPONENT_VERSIONS as _LANDSCAPE_RAW_COMPONENT_VERSIONS,
    _assert_no_outcome_keys,
    _encoded_json,
    _frozen_source_fingerprints_at_commit,
    _read_json_bytes,
    _recorded_repository_root,
    _require_canonical_path,
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
from .stalemate import (
    STALEMATE_MANIFEST_ID,
    STALEMATE_PAIR_COUNT,
    STALEMATE_PROTOCOL_ID,
    STALEMATE_SOURCE_MANIFEST_ID,
    STALEMATE_SOURCE_MANIFEST_SHA256,
    build_stalemate_paired_manifest,
    evaluate_stalemate_pairs,
    stress_stalemate_draws,
    validate_stalemate_baseline_replay,
    validate_stalemate_paired_manifest,
    validate_stalemate_paired_result,
    validate_stalemate_stress_result,
)


# The manifest-stage protocol ID is canonical in stalemate.py. Only these later
# evidence stages are runner-owned identifiers.
STALEMATE_RAW_PROTOCOL_ID = "stalemate-v1-paired-raw-exact"
STALEMATE_DRAW_STRESS_PROTOCOL_ID = "stalemate-v1-draw-stress"

STALEMATE_CORPUS_RELATIVE = Path("experiments/corpora/stalemate-v1")
STALEMATE_MANIFEST_RESERVATION_RELATIVE = (
    STALEMATE_CORPUS_RELATIVE / "manifest-reservation.json"
)
STALEMATE_MANIFEST_ATTEMPT_RELATIVE = (
    STALEMATE_CORPUS_RELATIVE / "manifest-attempt.json"
)
STALEMATE_MANIFEST_RELATIVE = STALEMATE_CORPUS_RELATIVE / "manifest.json"
STALEMATE_LOCK_RELATIVE = STALEMATE_CORPUS_RELATIVE / "manifest.lock.json"

SOURCE_LANDSCAPE_MANIFEST_RELATIVE = Path(
    "experiments/corpora/landscape-v1/manifest.json"
)
SOURCE_LANDSCAPE_LOCK_RELATIVE = Path(
    "experiments/corpora/landscape-v1/manifest.lock.json"
)
SOURCE_LANDSCAPE_ATTEMPT_RELATIVE = Path(
    "experiments/corpora/landscape-v1/manifest-attempt.json"
)
SOURCE_LANDSCAPE_FREEZER_COMMIT = "02174d904cdd27367d22e3d6aadcc9e197b0816e"
SOURCE_LANDSCAPE_ARCHIVE_COMMIT = "d7ddc04b3d4a918ea50ca86971cc8a9ddc201910"

SOURCE_LANDSCAPE_RAW_RUN_ID = "20260830T200230881318Z-landscape-f407aefb"
SOURCE_LANDSCAPE_RAW_RELATIVE = Path(
    "experiments/runs/{}/run.json".format(SOURCE_LANDSCAPE_RAW_RUN_ID)
)
SOURCE_LANDSCAPE_RAW_SHA256 = (
    "1edf571bc140a0cd586340eafee2306bccf6ca3a0816f8809b07edc9ef1a9fa4"
)
SOURCE_LANDSCAPE_RAW_COMMIT = "d7ddc04b3d4a918ea50ca86971cc8a9ddc201910"
SOURCE_LANDSCAPE_RAW_ARCHIVE_COMMIT = (
    "da867573710ba2dc0b064aeb6bc79bdf2cfcb869"
)

_FROZEN_PROTOCOL_RELATIVES = (
    Path("docs/plans/active/0007-stalemate-draw-paired-test.md"),
)
_FROZEN_EXECUTABLE_RELATIVES = (
    Path("src/parity_forge/__init__.py"),
    Path("src/parity_forge/__main__.py"),
    Path("src/parity_forge/agents.py"),
    Path("src/parity_forge/analysis.py"),
    Path("src/parity_forge/asymmetry.py"),
    Path("src/parity_forge/audit.py"),
    Path("src/parity_forge/batch.py"),
    Path("src/parity_forge/dsl.py"),
    Path("src/parity_forge/engine.py"),
    Path("src/parity_forge/experiments.py"),
    Path("src/parity_forge/landscape_evaluation.py"),
    Path("src/parity_forge/landscape_experiments.py"),
    Path("src/parity_forge/play.py"),
    Path("src/parity_forge/simplicity.py"),
    Path("src/parity_forge/solver.py"),
    Path("src/parity_forge/stalemate.py"),
    Path("src/parity_forge/stalemate_experiments.py"),
    Path("src/parity_forge/symmetry.py"),
)

_MANIFEST_COMPONENT_VERSIONS = {
    "parity_forge": __version__,
    "baseline_dsl_schema": 1,
    "treatment_dsl_schema": 2,
    "d4_canonicalization": 1,
    "stalemate_pair_selection": 1,
}
_RAW_COMPONENT_VERSIONS = {
    "parity_forge": __version__,
    "baseline_dsl_schema": 1,
    "treatment_dsl_schema": 2,
    "engine": 2,
    "static_evaluator": 1,
    "simplicity_evaluator": 1,
    "asymmetry_evaluator": 1,
    "play_evaluator": 1,
    "random_agent": 1,
    "goal_directed_agent": 1,
    "exact_solver": 1,
    "stalemate_paired_evaluator": 1,
}
_STRESS_COMPONENT_VERSIONS = {
    "parity_forge": __version__,
    "treatment_dsl_schema": 2,
    "engine": 2,
    "play_evaluator": 1,
    "minimax_agent": 1,
    "stalemate_draw_stress": 1,
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
_COMPLETED_RUN_KEYS = _ATTEMPT_KEYS | _NARRATIVE_KEYS | {"completed_at", "results"}
_MANIFEST_PROVENANCE_KEYS = {
    "freezer_git_commit",
    "freezer_git_dirty",
    "created_at",
    "protocol_id",
    "source_manifest_path",
    "source_manifest_sha256",
    "baseline_outcomes_informed_protocol_design",
    "case_membership_outcome_fields_consulted",
    "source_manifest_contains_outcomes",
    "treatment_outcomes_computed",
    "protocol_fingerprints",
    "executable_fingerprints",
}
_CASE_EVALUATOR_KWARGS = {
    "play_seeds",
    "max_exact_states",
    "gates",
    "clock",
}
_RAW_PHASE_ORDER = (
    "BASELINE_REPLAY",
    "BASELINE_REPLAY_VALIDATION",
    "TREATMENT_EVALUATION",
    "PAIRED_SUMMARY",
)
_PAIRED_RAW_CONFIGURATION_KEYS = {
    "manifest_id",
    "manifest_path",
    "manifest_sha256",
    "source_landscape_raw_run_id",
    "source_landscape_raw_path",
    "source_landscape_raw_sha256",
    "play_seeds",
    "play_gates",
    "max_exact_states",
    "phase_order",
}

ManifestBuilder = Callable[
    [Mapping[str, Any], str, Mapping[str, Any]], Mapping[str, Any]
]
CaseEvaluator = Callable[..., Mapping[str, Any]]
PairedEvaluator = Callable[..., Mapping[str, Any]]
StressEvaluator = Callable[..., Mapping[str, Any]]


def default_source_landscape_manifest_path(repository: Path) -> Path:
    return repository / SOURCE_LANDSCAPE_MANIFEST_RELATIVE


def default_source_landscape_raw_path(repository: Path) -> Path:
    return repository / SOURCE_LANDSCAPE_RAW_RELATIVE


def _sha256(source_bytes: bytes) -> str:
    return hashlib.sha256(source_bytes).hexdigest()


def _current_fingerprints(
    repository: Path,
    relatives: Sequence[Path] = _FROZEN_EXECUTABLE_RELATIVES,
) -> Mapping[str, str]:
    fingerprints: Dict[str, str] = {}
    for relative in relatives:
        path = repository / relative
        _require_tracked(path, repository, "stalemate executable {}".format(relative))
        try:
            source_bytes = path.read_bytes()
        except OSError as error:
            raise ValueError(
                "cannot read stalemate executable {}".format(relative)
            ) from error
        fingerprints[str(relative)] = _sha256(source_bytes)
    return fingerprints


def _require_blob_sha256(
    repository: Path,
    commit: str,
    relative: Path,
    expected_sha256: str,
    label: str,
) -> None:
    _require_commit_ancestor(commit, repository, label + " archive commit")
    historical = _frozen_source_fingerprints_at_commit(
        repository, commit, (relative,)
    )
    if historical[str(relative)] != expected_sha256:
        raise ValueError("{} archive blob SHA-256 mismatch".format(label))


def _validate_source_landscape_manifest(
    manifest_path: Path, repository: Path
) -> Tuple[bytes, Mapping[str, Any]]:
    """Validate the historical manifest without requiring old code at HEAD."""

    _require_canonical_path(
        manifest_path,
        repository,
        SOURCE_LANDSCAPE_MANIFEST_RELATIVE,
        "source landscape manifest",
    )
    _require_tracked(manifest_path, repository, "source landscape manifest")
    manifest_bytes, manifest = _read_json_bytes(
        manifest_path, "source landscape manifest"
    )
    if _sha256(manifest_bytes) != STALEMATE_SOURCE_MANIFEST_SHA256:
        raise ValueError("source landscape manifest SHA-256 mismatch")

    lock_path = repository / SOURCE_LANDSCAPE_LOCK_RELATIVE
    attempt_path = repository / SOURCE_LANDSCAPE_ATTEMPT_RELATIVE
    for path, relative, label in (
        (lock_path, SOURCE_LANDSCAPE_LOCK_RELATIVE, "source landscape lock"),
        (
            attempt_path,
            SOURCE_LANDSCAPE_ATTEMPT_RELATIVE,
            "source landscape attempt",
        ),
    ):
        _require_canonical_path(path, repository, relative, label)
        _require_tracked(path, repository, label)
    _, lock = _read_json_bytes(lock_path, "source landscape lock")
    _, attempt = _read_json_bytes(attempt_path, "source landscape attempt")
    if lock != {
        "freezer_git_commit": SOURCE_LANDSCAPE_FREEZER_COMMIT,
        "manifest_bytes": len(manifest_bytes),
        "manifest_id": LANDSCAPE_MANIFEST_ID,
        "manifest_sha256": STALEMATE_SOURCE_MANIFEST_SHA256,
        "protocol_id": LANDSCAPE_MANIFEST_PROTOCOL_ID,
    }:
        raise ValueError("source landscape manifest lock mismatch")
    if (
        attempt.get("run_id") != LANDSCAPE_MANIFEST_ID
        or attempt.get("protocol_id") != LANDSCAPE_MANIFEST_PROTOCOL_ID
        or attempt.get("status") != "STARTED"
        or attempt.get("git_commit") != SOURCE_LANDSCAPE_FREEZER_COMMIT
        or attempt.get("git_dirty") is not False
        or attempt.get("component_versions")
        != _LANDSCAPE_MANIFEST_COMPONENT_VERSIONS
    ):
        raise ValueError("source landscape manifest attempt mismatch")
    _require_timestamp(attempt.get("started_at"), "source landscape attempt")
    if (
        manifest.get("manifest_id") != STALEMATE_SOURCE_MANIFEST_ID
        or manifest.get("manifest_version") != 1
        or manifest.get("protocol_id") != LANDSCAPE_MANIFEST_PROTOCOL_ID
        or manifest.get("status") != "FROZEN"
        or manifest.get("component_versions")
        != _LANDSCAPE_MANIFEST_COMPONENT_VERSIONS
    ):
        raise ValueError("source landscape manifest identity mismatch")
    _assert_no_outcome_keys(manifest, "source_manifest")
    provenance = manifest.get("provenance")
    if (
        not isinstance(provenance, Mapping)
        or provenance.get("freezer_git_commit")
        != SOURCE_LANDSCAPE_FREEZER_COMMIT
        or provenance.get("selection_outcome_fields_consulted") is not False
        or provenance.get("outcomes_computed") is not False
    ):
        raise ValueError("source landscape manifest provenance mismatch")
    recorded_fingerprints = provenance.get("source_fingerprints")
    if not isinstance(recorded_fingerprints, Mapping):
        raise ValueError("source landscape fingerprints are missing")
    historical = _frozen_source_fingerprints_at_commit(
        repository,
        SOURCE_LANDSCAPE_FREEZER_COMMIT,
        tuple(Path(relative) for relative in recorded_fingerprints),
    )
    if historical != recorded_fingerprints:
        raise ValueError("source landscape historical fingerprints mismatch")
    _require_blob_sha256(
        repository,
        SOURCE_LANDSCAPE_ARCHIVE_COMMIT,
        SOURCE_LANDSCAPE_MANIFEST_RELATIVE,
        STALEMATE_SOURCE_MANIFEST_SHA256,
        "source landscape manifest",
    )
    return manifest_bytes, manifest


def _manifest_provenance(
    repository: Path, commit: str, created_at: str
) -> Mapping[str, Any]:
    return {
        "freezer_git_commit": commit,
        "freezer_git_dirty": False,
        "created_at": created_at,
        "protocol_id": STALEMATE_PROTOCOL_ID,
        "source_manifest_path": str(SOURCE_LANDSCAPE_MANIFEST_RELATIVE),
        "source_manifest_sha256": STALEMATE_SOURCE_MANIFEST_SHA256,
        "baseline_outcomes_informed_protocol_design": True,
        "case_membership_outcome_fields_consulted": False,
        "source_manifest_contains_outcomes": False,
        "treatment_outcomes_computed": False,
        "protocol_fingerprints": _frozen_source_fingerprints_at_commit(
            repository, commit, _FROZEN_PROTOCOL_RELATIVES
        ),
        "executable_fingerprints": _current_fingerprints(repository),
    }


def freeze_stalemate_manifest(
    source_manifest_path: Path,
    corpus_directory: Path,
    repository: Path,
    manifest_builder: ManifestBuilder = build_stalemate_paired_manifest,
) -> Path:
    """Atomically reserve and freeze the treatment-outcome-free manifest once."""

    _require_canonical_path(
        corpus_directory,
        repository,
        STALEMATE_CORPUS_RELATIVE,
        "stalemate corpus directory",
    )
    if corpus_directory.exists():
        raise ValueError("stalemate manifest already has reserved evidence")
    _, source_manifest = _validate_source_landscape_manifest(
        source_manifest_path, repository
    )
    if not callable(manifest_builder):
        raise TypeError("manifest_builder must be callable")
    commit = _require_clean_repository(repository)
    started = _utc_now()
    started_at = _timestamp(started)
    provenance = _manifest_provenance(repository, commit, started_at)

    # Directory creation is the atomic manifest-stage one-shot reservation.
    corpus_directory.mkdir(parents=False, exist_ok=False)
    reservation = {
        "run_id": STALEMATE_MANIFEST_ID,
        "protocol_id": STALEMATE_PROTOCOL_ID,
        "status": "RESERVED",
        "reserved_at": started_at,
        "git_commit": commit,
    }
    _write_exclusive(corpus_directory / "manifest-reservation.json", reservation)
    attempt = {
        "run_id": STALEMATE_MANIFEST_ID,
        "protocol_id": STALEMATE_PROTOCOL_ID,
        "experiment_type": "baseline-informed-treatment-outcome-free-paired-manifest",
        "status": "STARTED",
        "started_at": started_at,
        "git_commit": commit,
        "git_dirty": False,
        "environment": {"python": sys.version, "platform": platform.platform()},
        "component_versions": dict(_MANIFEST_COMPONENT_VERSIONS),
        "configuration": {
            "source_manifest_id": STALEMATE_SOURCE_MANIFEST_ID,
            "source_manifest_path": str(source_manifest_path.resolve()),
            "source_manifest_sha256": STALEMATE_SOURCE_MANIFEST_SHA256,
            "destination": str(corpus_directory.resolve()),
            "baseline_outcomes_informed_protocol_design": True,
            "case_membership_outcome_fields_consulted": False,
            "treatment_outcomes_computed": False,
        },
    }
    _write_exclusive(corpus_directory / "manifest-attempt.json", attempt)
    try:
        expected_manifest = build_stalemate_paired_manifest(
            source_manifest,
            STALEMATE_SOURCE_MANIFEST_SHA256,
            provenance,
        )
        manifest = manifest_builder(
            copy.deepcopy(source_manifest),
            STALEMATE_SOURCE_MANIFEST_SHA256,
            copy.deepcopy(provenance),
        )
        if not isinstance(manifest, Mapping):
            raise ValueError("stalemate manifest builder must return an object")
        if manifest != expected_manifest or manifest.get("provenance") != provenance:
            raise ValueError(
                "stalemate manifest builder output differs from canonical construction"
            )
        validate_stalemate_paired_manifest(manifest)
        _assert_no_outcome_keys(manifest, "stalemate_manifest")
        manifest_bytes = _encoded_json(manifest)
        manifest_path = corpus_directory / "manifest.json"
        with manifest_path.open("xb") as destination:
            destination.write(manifest_bytes)
        lock = {
            "manifest_id": STALEMATE_MANIFEST_ID,
            "protocol_id": STALEMATE_PROTOCOL_ID,
            "manifest_sha256": _sha256(manifest_bytes),
            "manifest_bytes": len(manifest_bytes),
            "freezer_git_commit": commit,
        }
        _write_exclusive(corpus_directory / "manifest.lock.json", lock)
    except BaseException as error:
        _write_failure(
            corpus_directory / "manifest-failure.json",
            attempt,
            "MANIFEST_CONSTRUCTION",
            error,
        )
        raise
    return manifest_path


def _validate_frozen_stalemate_manifest(
    manifest_path: Path, lock_path: Path, repository: Path
) -> Tuple[bytes, Mapping[str, Any]]:
    failure_path = repository / STALEMATE_CORPUS_RELATIVE / "manifest-failure.json"
    if failure_path.exists():
        raise ValueError(
            "stalemate manifest cannot coexist with manifest failure evidence"
        )
    _require_canonical_path(
        manifest_path,
        repository,
        STALEMATE_MANIFEST_RELATIVE,
        "stalemate manifest",
    )
    _require_canonical_path(
        lock_path, repository, STALEMATE_LOCK_RELATIVE, "stalemate manifest lock"
    )
    attempt_path = repository / STALEMATE_MANIFEST_ATTEMPT_RELATIVE
    reservation_path = repository / STALEMATE_MANIFEST_RESERVATION_RELATIVE
    for path, label in (
        (manifest_path, "stalemate manifest"),
        (lock_path, "stalemate manifest lock"),
        (attempt_path, "stalemate manifest attempt"),
        (reservation_path, "stalemate manifest reservation"),
    ):
        _require_tracked(path, repository, label)
    manifest_bytes, manifest = _read_json_bytes(manifest_path, "stalemate manifest")
    if manifest_bytes != _encoded_json(manifest):
        raise ValueError("stalemate manifest bytes are not canonical JSON")
    _, lock = _read_json_bytes(lock_path, "stalemate manifest lock")
    _, attempt = _read_json_bytes(attempt_path, "stalemate manifest attempt")
    _, reservation = _read_json_bytes(
        reservation_path, "stalemate manifest reservation"
    )
    expected_attempt_keys = {
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
    freezer_commit = attempt.get("git_commit")
    if lock != {
        "manifest_id": STALEMATE_MANIFEST_ID,
        "protocol_id": STALEMATE_PROTOCOL_ID,
        "manifest_sha256": _sha256(manifest_bytes),
        "manifest_bytes": len(manifest_bytes),
        "freezer_git_commit": freezer_commit,
    }:
        raise ValueError("stalemate manifest lock does not match exact bytes")
    if reservation != {
        "run_id": STALEMATE_MANIFEST_ID,
        "protocol_id": STALEMATE_PROTOCOL_ID,
        "status": "RESERVED",
        "reserved_at": attempt.get("started_at"),
        "git_commit": freezer_commit,
    }:
        raise ValueError("stalemate manifest reservation mismatch")
    if (
        set(attempt) != expected_attempt_keys
        or attempt.get("run_id") != STALEMATE_MANIFEST_ID
        or attempt.get("protocol_id") != STALEMATE_PROTOCOL_ID
        or attempt.get("experiment_type")
        != "baseline-informed-treatment-outcome-free-paired-manifest"
        or attempt.get("status") != "STARTED"
        or attempt.get("git_dirty") is not False
        or attempt.get("component_versions") != _MANIFEST_COMPONENT_VERSIONS
    ):
        raise ValueError("stalemate manifest attempt mismatch")
    _require_timestamp(
        attempt.get("started_at"), "stalemate manifest attempt started_at"
    )
    environment = attempt.get("environment")
    configuration = attempt.get("configuration")
    if (
        not isinstance(environment, Mapping)
        or set(environment) != {"python", "platform"}
        or not all(isinstance(value, str) for value in environment.values())
        or not isinstance(configuration, Mapping)
        or set(configuration)
        != {
            "source_manifest_id",
            "source_manifest_path",
            "source_manifest_sha256",
            "destination",
            "baseline_outcomes_informed_protocol_design",
            "case_membership_outcome_fields_consulted",
            "treatment_outcomes_computed",
        }
        or configuration.get("source_manifest_id")
        != STALEMATE_SOURCE_MANIFEST_ID
        or configuration.get("source_manifest_sha256")
        != STALEMATE_SOURCE_MANIFEST_SHA256
        or configuration.get("baseline_outcomes_informed_protocol_design")
        is not True
        or configuration.get("case_membership_outcome_fields_consulted")
        is not False
        or configuration.get("treatment_outcomes_computed") is not False
    ):
        raise ValueError("stalemate manifest attempt configuration mismatch")
    recorded_source_root = _recorded_repository_root(
        configuration["source_manifest_path"],
        SOURCE_LANDSCAPE_MANIFEST_RELATIVE,
        "stalemate manifest attempt source",
    )
    recorded_destination_root = _recorded_repository_root(
        configuration["destination"],
        STALEMATE_CORPUS_RELATIVE,
        "stalemate manifest attempt destination",
    )
    if recorded_source_root != recorded_destination_root:
        raise ValueError("stalemate manifest attempt repository roots differ")
    freezer_commit = _require_commit_ancestor(
        freezer_commit, repository, "stalemate manifest freezer commit"
    )
    _, source_manifest = _validate_source_landscape_manifest(
        repository / SOURCE_LANDSCAPE_MANIFEST_RELATIVE, repository
    )
    pairs = validate_stalemate_paired_manifest(manifest)
    if len(pairs) != STALEMATE_PAIR_COUNT:
        raise ValueError("stalemate manifest pair count mismatch")
    _assert_no_outcome_keys(manifest, "stalemate_manifest")
    provenance = manifest.get("provenance")
    if (
        not isinstance(provenance, Mapping)
        or set(provenance) != _MANIFEST_PROVENANCE_KEYS
    ):
        raise ValueError("stalemate manifest provenance schema mismatch")
    expected_protocol = _frozen_source_fingerprints_at_commit(
        repository, freezer_commit, _FROZEN_PROTOCOL_RELATIVES
    )
    if (
        provenance.get("freezer_git_commit") != freezer_commit
        or provenance.get("freezer_git_dirty") is not False
        or provenance.get("created_at") != attempt.get("started_at")
        or provenance.get("protocol_id") != STALEMATE_PROTOCOL_ID
        or provenance.get("protocol_fingerprints") != expected_protocol
        or provenance.get("source_manifest_path")
        != str(SOURCE_LANDSCAPE_MANIFEST_RELATIVE)
        or provenance.get("source_manifest_sha256")
        != STALEMATE_SOURCE_MANIFEST_SHA256
        or provenance.get("baseline_outcomes_informed_protocol_design") is not True
        or provenance.get("case_membership_outcome_fields_consulted") is not False
        or provenance.get("source_manifest_contains_outcomes") is not False
        or provenance.get("treatment_outcomes_computed") is not False
    ):
        raise ValueError("stalemate manifest provenance mismatch")
    expected = build_stalemate_paired_manifest(
        source_manifest, STALEMATE_SOURCE_MANIFEST_SHA256, provenance
    )
    if manifest != expected:
        raise ValueError("stalemate manifest is not reproducible from pinned source")
    executable_fingerprints = provenance.get("executable_fingerprints")
    if (
        not isinstance(executable_fingerprints, Mapping)
        or _current_fingerprints(repository) != executable_fingerprints
    ):
        raise ValueError("stalemate executable fingerprints changed after freeze")
    return manifest_bytes, manifest


def _validate_source_landscape_raw(
    raw_path: Path,
    repository: Path,
    pairs: Sequence[Mapping[str, Any]],
) -> Tuple[bytes, Mapping[str, Any]]:
    _require_canonical_path(
        raw_path,
        repository,
        SOURCE_LANDSCAPE_RAW_RELATIVE,
        "source landscape raw run",
    )
    _require_tracked(raw_path, repository, "source landscape raw run")
    raw_bytes, record = _read_json_bytes(raw_path, "source landscape raw run")
    if _sha256(raw_bytes) != SOURCE_LANDSCAPE_RAW_SHA256:
        raise ValueError("source landscape raw SHA-256 mismatch")
    if (
        record.get("run_id") != SOURCE_LANDSCAPE_RAW_RUN_ID
        or record.get("protocol_id") != LANDSCAPE_RAW_PROTOCOL_ID
        or record.get("experiment_type")
        != "frozen-3x3-exact-outcome-landscape"
        or record.get("status") != "COMPLETED"
        or record.get("git_commit") != SOURCE_LANDSCAPE_RAW_COMMIT
        or record.get("git_dirty") is not False
        or record.get("component_versions") != _LANDSCAPE_RAW_COMPONENT_VERSIONS
    ):
        raise ValueError("source landscape raw identity mismatch")
    attempt = _validate_completed_run_attempt(
        raw_path, record, repository, _LANDSCAPE_RAW_COMPONENT_VERSIONS
    )
    _validate_protocol_reservation(
        repository / "experiments/runs",
        LANDSCAPE_RAW_PROTOCOL_ID,
        SOURCE_LANDSCAPE_RAW_RUN_ID,
        SOURCE_LANDSCAPE_RAW_COMMIT,
        attempt["started_at"],
        repository,
    )
    _require_blob_sha256(
        repository,
        SOURCE_LANDSCAPE_RAW_ARCHIVE_COMMIT,
        SOURCE_LANDSCAPE_RAW_RELATIVE,
        SOURCE_LANDSCAPE_RAW_SHA256,
        "source landscape raw",
    )
    _, source_manifest = _validate_source_landscape_manifest(
        repository / SOURCE_LANDSCAPE_MANIFEST_RELATIVE, repository
    )
    recorded = source_manifest["provenance"]["source_fingerprints"]
    expected_old_executables = {
        str(relative): recorded[str(relative)]
        for relative in _LANDSCAPE_EXECUTABLE_RELATIVES
    }
    historical_raw = _frozen_source_fingerprints_at_commit(
        repository,
        SOURCE_LANDSCAPE_RAW_COMMIT,
        _LANDSCAPE_EXECUTABLE_RELATIVES,
    )
    if historical_raw != expected_old_executables:
        raise ValueError("source landscape raw executable provenance mismatch")
    results = record.get("results")
    candidates = results.get("candidates") if isinstance(results, Mapping) else None
    aggregate = results.get("aggregate") if isinstance(results, Mapping) else None
    if (
        not isinstance(candidates, list)
        or len(candidates) != 384
        or not isinstance(aggregate, Mapping)
        or aggregate.get("manifest_case_count") != 384
        or aggregate.get("exact_attempted") != 384
        or aggregate.get("exact_completed") != 384
    ):
        raise ValueError("source landscape raw result schema mismatch")
    by_case_id: Dict[str, Mapping[str, Any]] = {}
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            raise ValueError("source landscape raw candidates must be objects")
        case_id = candidate.get("case_id")
        if not isinstance(case_id, str) or case_id in by_case_id:
            raise ValueError("source landscape raw case identities must be unique")
        by_case_id[case_id] = candidate
    for pair in pairs:
        candidate = by_case_id.get(pair["source_case_id"])
        if (
            candidate is None
            or candidate.get("definition_hash") != pair["source_definition_hash"]
            or candidate.get("d4_canonical_hash")
            != pair["source_d4_canonical_hash"]
            or candidate.get("definition") != pair["source_definition"]
            or candidate.get("stratum") != pair["stratum"]
            or candidate.get("vector_count") != pair["vector_count"]
        ):
            raise ValueError("source landscape raw pair join mismatch")
    return raw_bytes, record


def _require_same_fingerprints(
    repository: Path, manifest: Mapping[str, Any]
) -> None:
    provenance = manifest.get("provenance")
    expected = (
        provenance.get("executable_fingerprints")
        if isinstance(provenance, Mapping)
        else None
    )
    if (
        not isinstance(expected, Mapping)
        or _current_fingerprints(repository) != expected
    ):
        raise ValueError("stalemate executable fingerprints changed during protocol")


def _require_unchanged_bytes(path: Path, expected_sha256: str, label: str) -> None:
    try:
        source_bytes = path.read_bytes()
    except OSError as error:
        raise ValueError("{} disappeared during evaluation".format(label)) from error
    if _sha256(source_bytes) != expected_sha256:
        raise ValueError("{} bytes changed during evaluation".format(label))


def _validate_stage_cases(
    cases: Sequence[Mapping[str, Any]],
    pairs: Sequence[Mapping[str, Any]],
    treatment: bool,
) -> None:
    """Pin the two evaluator calls to the full ordered manifest identities."""

    if len(cases) != STALEMATE_PAIR_COUNT or len(pairs) != STALEMATE_PAIR_COUNT:
        raise ValueError("paired evaluator stage must contain exactly 128 cases")
    prefix = "treatment" if treatment else "source"
    expected_keys = {
        "case_id",
        "stratum",
        "vector_count",
        "definition_hash",
        "d4_canonical_hash",
        "definition",
    }
    for index, (case, pair) in enumerate(zip(cases, pairs)):
        if not isinstance(case, Mapping) or set(case) != expected_keys:
            raise ValueError(
                "{} evaluator case {} schema mismatch".format(prefix, index)
            )
        expected_case_id = pair["pair_id"] if treatment else pair["source_case_id"]
        if (
            case.get("case_id") != expected_case_id
            or case.get("stratum") != pair["stratum"]
            or case.get("vector_count") != pair["vector_count"]
            or case.get("definition_hash")
            != pair[prefix + "_definition_hash"]
            or case.get("d4_canonical_hash")
            != pair[prefix + "_d4_canonical_hash"]
            or case.get("definition") != pair[prefix + "_definition"]
        ):
            raise ValueError(
                "{} evaluator case {} identity or order mismatch".format(
                    prefix, index
                )
            )


def _validate_stage_evaluator_kwargs(kwargs: Mapping[str, Any]) -> None:
    """Freeze every scientific evaluator argument before either stage runs."""

    if (
        set(kwargs) != _CASE_EVALUATOR_KWARGS
        or not isinstance(kwargs.get("play_seeds"), tuple)
        or kwargs.get("play_seeds") != LANDSCAPE_PLAY_SEEDS
        or type(kwargs.get("max_exact_states")) is not int
        or kwargs.get("max_exact_states") != LANDSCAPE_EXACT_MAX_STATES
        or type(kwargs.get("gates")) is not PlayGates
        or kwargs.get("gates") != PlayGates()
        or not callable(kwargs.get("clock"))
    ):
        raise ValueError("paired case evaluator arguments differ from frozen protocol")


def _assessment_status(
    assessments: Mapping[str, Any], key: str, label: str
) -> str:
    assessment = assessments.get(key)
    status = assessment.get("status") if isinstance(assessment, Mapping) else None
    if not isinstance(status, str):
        raise ValueError("{} assessment {} is missing".format(label, key))
    return status


def _raw_narrative(result: Mapping[str, Any]) -> Mapping[str, Any]:
    aggregate = result.get("aggregate")
    timing = result.get("timing")
    if not isinstance(aggregate, Mapping) or not isinstance(timing, Mapping):
        raise ValueError("paired raw narrative requires aggregate and timing")
    assessments = aggregate.get("predeclared_assessment")
    if not isinstance(assessments, Mapping):
        raise ValueError("paired raw narrative requires assessments")
    exact = _assessment_status(assessments, "exact_completion", "paired raw")
    non_horizon = _assessment_status(
        assessments, "clean_non_horizon", "paired raw"
    )
    semantic = _assessment_status(assessments, "semantic_response", "paired raw")
    overall = _assessment_status(
        assessments, "overall_treatment_discovery", "paired raw"
    )
    if non_horizon == "NOT_SUPPORTED":
        decision = "AUDIT_SEMANTICS_AND_EXHAUSTION_PROOF"
    elif exact != "SUPPORTED":
        decision = "IMPROVE_EXACT_SEARCH_BEFORE_STRESS"
    else:
        decision = "COMMIT_RAW_THEN_RUN_PREDECLARED_STRESS"
    return {
        "hypothesis": (
            "The schema-v2 stalemate-draw policy will create at least four "
            "static-valid post-action exact draws across at least two frozen "
            "strata, with at least one shape-clean draw reaching the stress lane."
        ),
        "baseline": (
            "All 128 pinned schema-v1 max_plies=18 cases are replayed and must "
            "match the historical landscape evidence before treatment evaluation."
        ),
        "treatment": (
            "Each paired schema-v2 definition changes only "
            "terminal_policy.no_legal_action to DRAW and receives frozen static, "
            "cheap-play, and 100000-state exact evaluation."
        ),
        "expected_result": (
            "All 128 treatments complete exactly without PLY_LIMIT; at least four "
            "static-valid post-action stalemate draws span at least two strata."
        ),
        "actual_result": {**dict(aggregate), "timing": timing},
        "interpretation": (
            "Exact completion is {}; clean non-horizon is {}; semantic response "
            "is {}; overall treatment discovery is {} before stress."
        ).format(exact, non_horizon, semantic, overall),
        "decision": decision,
    }


def _stress_narrative(result: Mapping[str, Any]) -> Mapping[str, Any]:
    aggregate = result.get("aggregate")
    timing = result.get("timing")
    if not isinstance(aggregate, Mapping) or not isinstance(timing, Mapping):
        raise ValueError("stalemate stress narrative requires aggregate and timing")
    assessments = aggregate.get("predeclared_assessment")
    if not isinstance(assessments, Mapping):
        raise ValueError("stalemate stress narrative requires assessments")
    general = _assessment_status(
        assessments, "general_draw_stress", "stalemate stress"
    )
    frontier = _assessment_status(
        assessments, "frontier_response", "stalemate stress"
    )
    overall = _assessment_status(
        assessments, "overall_treatment_discovery", "stalemate stress"
    )
    decision = aggregate.get("next_branch")
    if not isinstance(decision, str):
        raise ValueError("stalemate stress next branch is missing")
    return {
        "hypothesis": (
            "Frozen depth-5 self-play will leave exact stalemate draws "
            "non-directional and reveal at least one diagnostic-frontier case."
        ),
        "baseline": (
            "The committed paired raw record supplies the exact, structural, and "
            "cheap-play evidence that fixes stress eligibility and ordering."
        ),
        "treatment": (
            "At most 32 structurally valid post-action stalemate draws, "
            "shape-clean first, receive depth-5 self-play over seeds 0..29 under "
            "one cumulative 5000000-node cap per definition."
        ),
        "expected_result": (
            "At least 15 cases complete without node or candidate-cap censoring, "
            "no exact draw is called directional, and at least one complete "
            "shape-clean diagnostic frontier remains."
        ),
        "actual_result": {**dict(aggregate), "timing": timing},
        "interpretation": (
            "General draw stress is {}; frontier response is {}; overall "
            "treatment discovery is {}."
        ).format(general, frontier, overall),
        "decision": decision,
    }


def _validate_completed_narrative(
    record: Mapping[str, Any],
    result: Mapping[str, Any],
    builder: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    label: str,
) -> None:
    if set(record) != _COMPLETED_RUN_KEYS:
        raise ValueError("{} completed record schema mismatch".format(label))
    expected = builder(result)
    if {key: record.get(key) for key in _NARRATIVE_KEYS} != expected:
        raise ValueError(
            "{} narrative fields do not match result evidence".format(label)
        )


def run_stalemate_paired(
    manifest_path: Path,
    lock_path: Path,
    source_raw_path: Path,
    output_root: Path,
    repository: Path,
    paired_evaluator: PairedEvaluator = evaluate_stalemate_pairs,
    case_evaluator: CaseEvaluator = evaluate_landscape_cases,
) -> Path:
    """Run the immutable paired evaluation with an explicit replay boundary."""

    if output_root.resolve() != (repository / "experiments/runs").resolve():
        raise ValueError("stalemate evidence must use the repository run directory")
    if not callable(paired_evaluator) or not callable(case_evaluator):
        raise TypeError("paired_evaluator and case_evaluator must be callable")
    manifest_bytes, manifest = _validate_frozen_stalemate_manifest(
        manifest_path, lock_path, repository
    )
    pairs = validate_stalemate_paired_manifest(manifest)
    source_raw_bytes, source_raw = _validate_source_landscape_raw(
        source_raw_path, repository, pairs
    )
    pinned_baseline_results = copy.deepcopy(source_raw["results"])
    commit = _require_clean_repository(repository)
    _require_same_fingerprints(repository, manifest)
    _scan_prior_protocol(output_root, STALEMATE_RAW_PROTOCOL_ID)
    started = _utc_now()
    started_at = _timestamp(started)
    manifest_hash = _sha256(manifest_bytes)
    run_id = "{}-stalemate-{}".format(
        started.strftime("%Y%m%dT%H%M%S%fZ"), manifest_hash[:8]
    )
    _reserve_protocol(
        output_root, STALEMATE_RAW_PROTOCOL_ID, run_id, commit, started_at
    )
    run_directory = output_root / run_id
    run_directory.mkdir(parents=False, exist_ok=False)
    attempt = {
        "run_id": run_id,
        "protocol_id": STALEMATE_RAW_PROTOCOL_ID,
        "experiment_type": "stalemate-draw-v1-v2-paired-exact",
        "status": "STARTED",
        "started_at": started_at,
        "git_commit": commit,
        "git_dirty": False,
        "environment": {"python": sys.version, "platform": platform.platform()},
        "component_versions": dict(_RAW_COMPONENT_VERSIONS),
        "configuration": {
            "manifest_id": STALEMATE_MANIFEST_ID,
            "manifest_path": str(manifest_path.resolve()),
            "manifest_sha256": manifest_hash,
            "source_landscape_raw_run_id": SOURCE_LANDSCAPE_RAW_RUN_ID,
            "source_landscape_raw_path": str(source_raw_path.resolve()),
            "source_landscape_raw_sha256": SOURCE_LANDSCAPE_RAW_SHA256,
            "play_seeds": list(LANDSCAPE_PLAY_SEEDS),
            "play_gates": asdict(PlayGates()),
            "max_exact_states": LANDSCAPE_EXACT_MAX_STATES,
            "phase_order": list(_RAW_PHASE_ORDER),
        },
    }
    _write_exclusive(run_directory / "attempt.json", attempt)

    phase = {
        "name": "BASELINE_REPLAY",
        "case_evaluator_calls": 0,
        "baseline_replay_validated": False,
    }

    def staged_case_evaluator(
        cases: Sequence[Mapping[str, Any]], **kwargs: Any
    ) -> Mapping[str, Any]:
        phase["case_evaluator_calls"] += 1
        call_number = phase["case_evaluator_calls"]
        if call_number == 1:
            phase["name"] = "BASELINE_REPLAY"
            _validate_stage_cases(cases, pairs, treatment=False)
            _validate_stage_evaluator_kwargs(kwargs)
        elif call_number == 2:
            phase["name"] = "TREATMENT_EVALUATION"
            if phase["baseline_replay_validated"] is not True:
                raise ValueError(
                    "treatment evaluation requires a fully validated baseline replay"
                )
            _validate_stage_cases(cases, pairs, treatment=True)
            _validate_stage_evaluator_kwargs(kwargs)
            _require_same_fingerprints(repository, manifest)
            _require_unchanged_bytes(manifest_path, manifest_hash, "stalemate manifest")
            _require_unchanged_bytes(
                source_raw_path,
                _sha256(source_raw_bytes),
                "source landscape raw",
            )
        else:
            raise ValueError(
                "paired evaluator invoked the case evaluator more than twice"
            )
        evaluated = case_evaluator(cases, **kwargs)
        if not isinstance(evaluated, Mapping):
            raise ValueError("case evaluator must return an object")
        if call_number == 1:
            phase["name"] = "BASELINE_REPLAY_VALIDATION"
            validate_stalemate_baseline_replay(
                evaluated,
                manifest,
                pinned_baseline_results,
                play_seeds=LANDSCAPE_PLAY_SEEDS,
                max_exact_states=LANDSCAPE_EXACT_MAX_STATES,
                gates=PlayGates(),
            )
            phase["baseline_replay_validated"] = True
        else:
            phase["name"] = "PAIRED_SUMMARY"
        return evaluated

    try:
        result = paired_evaluator(
            copy.deepcopy(manifest),
            copy.deepcopy(pinned_baseline_results),
            play_seeds=LANDSCAPE_PLAY_SEEDS,
            max_exact_states=LANDSCAPE_EXACT_MAX_STATES,
            gates=PlayGates(),
            case_evaluator=staged_case_evaluator,
        )
        if phase["case_evaluator_calls"] != 2:
            phase["name"] = "PAIRED_EVALUATION_CONTRACT"
            raise ValueError(
                "paired evaluator must invoke baseline then treatment exactly once"
            )
        if not isinstance(result, Mapping):
            raise ValueError("paired evaluator must return an object")
        validate_stalemate_paired_result(
            result,
            manifest,
            pinned_baseline_results,
            play_seeds=LANDSCAPE_PLAY_SEEDS,
            max_exact_states=LANDSCAPE_EXACT_MAX_STATES,
            gates=PlayGates(),
        )
        _require_same_fingerprints(repository, manifest)
        _require_unchanged_bytes(manifest_path, manifest_hash, "stalemate manifest")
        _require_unchanged_bytes(
            source_raw_path, _sha256(source_raw_bytes), "source landscape raw"
        )
        phase["name"] = "COMPLETION_RECORD"
        narrative = _raw_narrative(result)
        record = {
            **attempt,
            "status": "COMPLETED",
            "completed_at": _timestamp(_utc_now()),
            **narrative,
            "results": result,
        }
        _validate_completed_narrative(
            record, result, _raw_narrative, "paired raw"
        )
        destination = run_directory / "run.json"
        _write_exclusive(destination, record)
    except BaseException as error:
        _write_failure(
            run_directory / "failure.json", attempt, str(phase["name"]), error
        )
        raise
    return destination


def _validate_paired_raw_configuration(
    configuration: Any,
    manifest: Mapping[str, Any],
) -> None:
    if (
        not isinstance(configuration, Mapping)
        or set(configuration) != _PAIRED_RAW_CONFIGURATION_KEYS
        or configuration.get("manifest_id") != STALEMATE_MANIFEST_ID
        or configuration.get("manifest_sha256")
        != _sha256(_encoded_json(manifest))
        or configuration.get("source_landscape_raw_run_id")
        != SOURCE_LANDSCAPE_RAW_RUN_ID
        or configuration.get("source_landscape_raw_sha256")
        != SOURCE_LANDSCAPE_RAW_SHA256
        or configuration.get("play_seeds") != list(LANDSCAPE_PLAY_SEEDS)
        or configuration.get("play_gates") != asdict(PlayGates())
        or configuration.get("max_exact_states") != LANDSCAPE_EXACT_MAX_STATES
        or configuration.get("phase_order") != list(_RAW_PHASE_ORDER)
    ):
        raise ValueError("paired raw configuration mismatch")
    manifest_root = _recorded_repository_root(
        configuration["manifest_path"],
        STALEMATE_MANIFEST_RELATIVE,
        "paired raw manifest path",
    )
    source_root = _recorded_repository_root(
        configuration["source_landscape_raw_path"],
        SOURCE_LANDSCAPE_RAW_RELATIVE,
        "paired raw historical source path",
    )
    if manifest_root != source_root:
        raise ValueError("paired raw configuration repository roots differ")


def _validate_paired_raw_source(
    raw_run_path: Path,
    output_root: Path,
    repository: Path,
    manifest: Mapping[str, Any],
) -> Tuple[bytes, Mapping[str, Any]]:
    if raw_run_path.is_symlink():
        raise ValueError("paired raw source cannot be a symlink")
    try:
        relative = raw_run_path.resolve().relative_to(output_root.resolve())
    except ValueError as error:
        raise ValueError(
            "paired raw source must be in the canonical run directory"
        ) from error
    if len(relative.parts) != 2 or relative.parts[1] != "run.json":
        raise ValueError("paired raw source must be <run-id>/run.json")
    _require_tracked(raw_run_path, repository, "paired raw source")
    raw_bytes, record = _read_json_bytes(raw_run_path, "paired raw source")
    if (
        set(record) != _COMPLETED_RUN_KEYS
        or record.get("run_id") != relative.parts[0]
        or record.get("protocol_id") != STALEMATE_RAW_PROTOCOL_ID
        or record.get("experiment_type") != "stalemate-draw-v1-v2-paired-exact"
        or record.get("status") != "COMPLETED"
        or record.get("git_dirty") is not False
        or record.get("component_versions") != _RAW_COMPONENT_VERSIONS
    ):
        raise ValueError("paired raw source identity mismatch")
    attempt = _validate_completed_run_attempt(
        raw_run_path, record, repository, _RAW_COMPONENT_VERSIONS
    )
    _validate_protocol_reservation(
        output_root,
        STALEMATE_RAW_PROTOCOL_ID,
        record["run_id"],
        attempt["git_commit"],
        attempt["started_at"],
        repository,
    )
    provenance = manifest["provenance"]
    historical = _frozen_source_fingerprints_at_commit(
        repository,
        attempt["git_commit"],
        tuple(Path(relative) for relative in provenance["executable_fingerprints"]),
    )
    if historical != provenance["executable_fingerprints"]:
        raise ValueError("paired raw source changed frozen executables")
    result = record.get("results")
    if not isinstance(result, Mapping):
        raise ValueError("paired raw source result is missing")
    _validate_paired_result_against_pinned_source(result, manifest, repository)
    _validate_completed_narrative(record, result, _raw_narrative, "paired raw")
    _validate_paired_raw_configuration(record.get("configuration"), manifest)
    return raw_bytes, record


def _validate_paired_result_against_pinned_source(
    result: Mapping[str, Any],
    manifest: Mapping[str, Any],
    repository: Path,
) -> Sequence[Mapping[str, Any]]:
    """Re-read the historical baseline chain before accepting paired raw bytes."""

    pairs = validate_stalemate_paired_manifest(manifest)
    _, pinned_baseline = _validate_source_landscape_raw(
        repository / SOURCE_LANDSCAPE_RAW_RELATIVE,
        repository,
        pairs,
    )
    return validate_stalemate_paired_result(
        result,
        manifest,
        pinned_baseline["results"],
        play_seeds=LANDSCAPE_PLAY_SEEDS,
        max_exact_states=LANDSCAPE_EXACT_MAX_STATES,
        gates=PlayGates(),
    )


def run_stalemate_draw_stress(
    raw_run_path: Path,
    manifest_path: Path,
    lock_path: Path,
    output_root: Path,
    repository: Path,
    stress_evaluator: StressEvaluator = stress_stalemate_draws,
) -> Path:
    """Run the separately reserved stress stage over one committed paired record."""

    if output_root.resolve() != (repository / "experiments/runs").resolve():
        raise ValueError("stalemate stress must use the repository run directory")
    if not callable(stress_evaluator):
        raise TypeError("stress_evaluator must be callable")
    manifest_bytes, manifest = _validate_frozen_stalemate_manifest(
        manifest_path, lock_path, repository
    )
    raw_bytes, raw_record = _validate_paired_raw_source(
        raw_run_path, output_root, repository, manifest
    )
    raw_result = raw_record["results"]
    raw_aggregate = raw_result.get("aggregate")
    if not isinstance(raw_aggregate, Mapping):
        raise ValueError("paired raw aggregate is missing")
    if raw_aggregate.get("ply_limit_result_count"):
        raise ValueError("treatment PLY_LIMIT blocks the one-shot stress protocol")
    if raw_aggregate.get("exact_censored_count"):
        raise ValueError("exact state censoring blocks the one-shot stress protocol")
    commit = _require_clean_repository(repository)
    _require_same_fingerprints(repository, manifest)
    _scan_prior_protocol(output_root, STALEMATE_DRAW_STRESS_PROTOCOL_ID)
    started = _utc_now()
    started_at = _timestamp(started)
    raw_hash = _sha256(raw_bytes)
    run_id = "{}-stalemate-stress-{}".format(
        started.strftime("%Y%m%dT%H%M%S%fZ"), raw_hash[:8]
    )
    _reserve_protocol(
        output_root,
        STALEMATE_DRAW_STRESS_PROTOCOL_ID,
        run_id,
        commit,
        started_at,
    )
    run_directory = output_root / run_id
    run_directory.mkdir(parents=False, exist_ok=False)
    attempt = {
        "run_id": run_id,
        "protocol_id": STALEMATE_DRAW_STRESS_PROTOCOL_ID,
        "experiment_type": "stalemate-draw-depth5-stress",
        "status": "STARTED",
        "started_at": started_at,
        "git_commit": commit,
        "git_dirty": False,
        "environment": {"python": sys.version, "platform": platform.platform()},
        "component_versions": dict(_STRESS_COMPONENT_VERSIONS),
        "configuration": {
            "manifest_id": STALEMATE_MANIFEST_ID,
            "manifest_path": str(manifest_path.resolve()),
            "manifest_sha256": _sha256(manifest_bytes),
            "source_raw_run_id": raw_record["run_id"],
            "source_raw_path": str(raw_run_path.resolve()),
            "source_raw_sha256": raw_hash,
            "seeds": list(DRAW_STRESS_SEEDS),
            "depth": DRAW_STRESS_DEPTH,
            "max_nodes_per_candidate": DRAW_STRESS_MAX_NODES,
            "max_candidates": DRAW_STRESS_MAX_CANDIDATES,
            "play_gates": asdict(PlayGates()),
        },
    }
    _write_exclusive(run_directory / "attempt.json", attempt)
    phase = "DRAW_STRESS_EVALUATION"
    try:
        result = stress_evaluator(
            copy.deepcopy(raw_result),
            seeds=DRAW_STRESS_SEEDS,
            depth=DRAW_STRESS_DEPTH,
            max_nodes_per_candidate=DRAW_STRESS_MAX_NODES,
            max_candidates=DRAW_STRESS_MAX_CANDIDATES,
            gates=PlayGates(),
        )
        if not isinstance(result, Mapping):
            raise ValueError("stress evaluator must return an object")
        validate_stalemate_stress_result(
            result,
            raw_result,
            seeds=DRAW_STRESS_SEEDS,
            depth=DRAW_STRESS_DEPTH,
            max_nodes_per_candidate=DRAW_STRESS_MAX_NODES,
            max_candidates=DRAW_STRESS_MAX_CANDIDATES,
            gates=PlayGates(),
        )
        _require_same_fingerprints(repository, manifest)
        _require_unchanged_bytes(
            manifest_path, _sha256(manifest_bytes), "stalemate manifest"
        )
        _require_unchanged_bytes(raw_run_path, raw_hash, "paired raw source")
        phase = "COMPLETION_RECORD"
        narrative = _stress_narrative(result)
        record = {
            **attempt,
            "status": "COMPLETED",
            "completed_at": _timestamp(_utc_now()),
            **narrative,
            "results": result,
        }
        _validate_completed_narrative(
            record, result, _stress_narrative, "stalemate stress"
        )
        destination = run_directory / "run.json"
        _write_exclusive(destination, record)
    except BaseException as error:
        _write_failure(run_directory / "failure.json", attempt, phase, error)
        raise
    return destination
