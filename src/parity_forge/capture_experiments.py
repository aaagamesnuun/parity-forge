"""Fail-closed one-shot runners for the B move-capture experiment.

Scientific construction and assessment live in :mod:`parity_forge.capture`.
This module owns only historical source pins, Git and byte attestations, atomic
reservations, attempt/failure records, and the baseline-before-treatment boundary.
"""

from __future__ import annotations

import copy
import hashlib
import platform
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Sequence, Tuple

from . import __version__
from .batch import PlayGates
from .capture import (
    CAPTURE_MANIFEST_ID,
    CAPTURE_PAIR_COUNT,
    CAPTURE_PROTOCOL_ID,
    CAPTURE_EXACT_MAX_STATES,
    CAPTURE_PLAY_SEEDS,
    CAPTURE_REPLAY_ATTESTATION_VERSION,
    CAPTURE_SOURCE_MANIFEST_ID,
    CAPTURE_SOURCE_MANIFEST_SHA256,
    CAPTURE_STATE_BOUND,
    CAPTURE_STRESS_DEPTH,
    CAPTURE_STRESS_MAX_CANDIDATES,
    CAPTURE_STRESS_MAX_NODES,
    CAPTURE_STRESS_SEEDS,
    build_capture_paired_manifest,
    evaluate_capture_cases,
    evaluate_capture_pairs,
    stress_capture_interactions,
    validate_capture_baseline_replay,
    validate_capture_case_evaluation,
    validate_capture_paired_manifest,
    validate_capture_paired_result,
    validate_capture_stress_result,
)
from .experiments import _timestamp, _utc_now
from .landscape_evaluation import evaluate_landscape_cases
from .landscape_experiments import (
    LANDSCAPE_RAW_PROTOCOL_ID,
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
from .stalemate_experiments import (
    SOURCE_LANDSCAPE_ATTEMPT_RELATIVE,
    SOURCE_LANDSCAPE_LOCK_RELATIVE,
    SOURCE_LANDSCAPE_MANIFEST_RELATIVE,
    SOURCE_LANDSCAPE_RAW_RELATIVE,
    SOURCE_LANDSCAPE_RAW_RUN_ID,
    SOURCE_LANDSCAPE_RAW_SHA256,
    _validate_source_landscape_manifest,
    _validate_source_landscape_raw,
)


CAPTURE_RAW_PROTOCOL_ID = "capture-v1-paired-raw-exact"
CAPTURE_STRESS_PROTOCOL_ID = "capture-v1-interaction-stress"

CAPTURE_CORPUS_RELATIVE = Path("experiments/corpora/capture-v1")
CAPTURE_MANIFEST_RESERVATION_RELATIVE = (
    CAPTURE_CORPUS_RELATIVE / "manifest-reservation.json"
)
CAPTURE_MANIFEST_ATTEMPT_RELATIVE = (
    CAPTURE_CORPUS_RELATIVE / "manifest-attempt.json"
)
CAPTURE_MANIFEST_RELATIVE = CAPTURE_CORPUS_RELATIVE / "manifest.json"
CAPTURE_LOCK_RELATIVE = CAPTURE_CORPUS_RELATIVE / "manifest.lock.json"

_FROZEN_PROTOCOL_RELATIVES = (
    Path("docs/plans/active/0008-b-move-capture-counterplay-test.md"),
)
_FROZEN_EXECUTABLE_RELATIVES = (
    Path("src/parity_forge/__init__.py"),
    Path("src/parity_forge/__main__.py"),
    Path("src/parity_forge/agents.py"),
    Path("src/parity_forge/analysis.py"),
    Path("src/parity_forge/asymmetry.py"),
    Path("src/parity_forge/audit.py"),
    Path("src/parity_forge/batch.py"),
    Path("src/parity_forge/capture.py"),
    Path("src/parity_forge/capture_experiments.py"),
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
    "treatment_dsl_schema": 3,
    "d4_canonicalization": 1,
    "capture_pair_selection": 1,
}
_RAW_COMPONENT_VERSIONS = {
    "parity_forge": __version__,
    "baseline_dsl_schema": 1,
    "treatment_dsl_schema": 3,
    "engine": 3,
    "static_evaluator": 2,
    "simplicity_evaluator": 2,
    "asymmetry_evaluator": 2,
    "play_evaluator": 1,
    "random_agent": 1,
    "goal_directed_agent": 1,
    "exact_solver": 1,
    "capture_paired_evaluator": 1,
    "replay_attestation": 1,
}
_STRESS_COMPONENT_VERSIONS = {
    "parity_forge": __version__,
    "treatment_dsl_schema": 3,
    "engine": 3,
    "play_evaluator": 1,
    "minimax_agent": 1,
    "capture_interaction_stress": 1,
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
_MANIFEST_PROVENANCE_KEYS = {
    "freezer_git_commit",
    "freezer_git_dirty",
    "created_at",
    "protocol_id",
    "source_manifest_path",
    "source_manifest_sha256",
    "baseline_outcomes_informed_protocol_design",
    "stalemate_outcomes_informed_protocol_design",
    "case_membership_outcome_fields_consulted",
    "source_manifest_contains_outcomes",
    "capture_treatment_outcomes_computed",
    "protocol_fingerprints",
    "executable_fingerprints",
}
_RAW_PHASE_ORDER = (
    "BASELINE_REPLAY",
    "BASELINE_REPLAY_ATTESTATION",
    "TREATMENT_EVALUATION",
    "PAIRED_SUMMARY",
)
_RAW_CONFIGURATION_KEYS = {
    "manifest_id",
    "manifest_path",
    "manifest_sha256",
    "source_landscape_raw_run_id",
    "source_landscape_raw_path",
    "source_landscape_raw_sha256",
    "play_seeds",
    "play_gates",
    "max_exact_states",
    "structural_state_bound",
    "replay_attestation_version",
    "phase_order",
}
_STRESS_CONFIGURATION_KEYS = {
    "manifest_id",
    "manifest_path",
    "manifest_sha256",
    "source_raw_run_id",
    "source_raw_path",
    "source_raw_sha256",
    "seeds",
    "depth",
    "max_nodes_per_candidate",
    "max_candidates",
    "play_gates",
}

ManifestBuilder = Callable[
    [Mapping[str, Any], str, Mapping[str, Any]], Mapping[str, Any]
]
BatchEvaluator = Callable[..., Mapping[str, Any]]
PairedEvaluator = Callable[..., Mapping[str, Any]]
StressEvaluator = Callable[..., Mapping[str, Any]]


def _sha256(source_bytes: bytes) -> str:
    return hashlib.sha256(source_bytes).hexdigest()


def default_source_landscape_manifest_path(repository: Path) -> Path:
    return repository / SOURCE_LANDSCAPE_MANIFEST_RELATIVE


def default_source_landscape_raw_path(repository: Path) -> Path:
    return repository / SOURCE_LANDSCAPE_RAW_RELATIVE


def _current_fingerprints(
    repository: Path,
    relatives: Sequence[Path] = _FROZEN_EXECUTABLE_RELATIVES,
) -> Mapping[str, str]:
    fingerprints: Dict[str, str] = {}
    for relative in relatives:
        path = repository / relative
        _require_tracked(path, repository, "capture executable {}".format(relative))
        try:
            source_bytes = path.read_bytes()
        except OSError as error:
            raise ValueError(
                "cannot read capture executable {}".format(relative)
            ) from error
        fingerprints[str(relative)] = _sha256(source_bytes)
    return fingerprints


def _current_protocol_fingerprints(repository: Path) -> Mapping[str, str]:
    return _current_fingerprints(repository, _FROZEN_PROTOCOL_RELATIVES)


def _manifest_provenance(
    repository: Path, commit: str, created_at: str
) -> Mapping[str, Any]:
    return {
        "freezer_git_commit": commit,
        "freezer_git_dirty": False,
        "created_at": created_at,
        "protocol_id": CAPTURE_PROTOCOL_ID,
        "source_manifest_path": str(SOURCE_LANDSCAPE_MANIFEST_RELATIVE),
        "source_manifest_sha256": CAPTURE_SOURCE_MANIFEST_SHA256,
        "baseline_outcomes_informed_protocol_design": True,
        "stalemate_outcomes_informed_protocol_design": True,
        "case_membership_outcome_fields_consulted": False,
        "source_manifest_contains_outcomes": False,
        "capture_treatment_outcomes_computed": False,
        "protocol_fingerprints": _current_protocol_fingerprints(repository),
        "executable_fingerprints": _current_fingerprints(repository),
    }


def freeze_capture_manifest(
    source_manifest_path: Path,
    corpus_directory: Path,
    repository: Path,
    manifest_builder: ManifestBuilder = build_capture_paired_manifest,
) -> Path:
    """Atomically reserve and freeze the capture-treatment-outcome-free manifest."""

    _require_canonical_path(
        corpus_directory,
        repository,
        CAPTURE_CORPUS_RELATIVE,
        "capture corpus directory",
    )
    if corpus_directory.exists():
        raise ValueError("capture manifest already has reserved evidence")
    source_bytes, source_manifest = _validate_source_landscape_manifest(
        source_manifest_path, repository
    )
    if _sha256(source_bytes) != CAPTURE_SOURCE_MANIFEST_SHA256:
        raise ValueError("capture source landscape manifest SHA-256 mismatch")
    if source_manifest.get("manifest_id") != CAPTURE_SOURCE_MANIFEST_ID:
        raise ValueError("capture source landscape manifest identity mismatch")
    if not callable(manifest_builder):
        raise TypeError("manifest_builder must be callable")
    commit = _require_clean_repository(repository)
    started_at = _timestamp(_utc_now())
    provenance = _manifest_provenance(repository, commit, started_at)

    corpus_directory.mkdir(parents=False, exist_ok=False)
    reservation = {
        "run_id": CAPTURE_MANIFEST_ID,
        "protocol_id": CAPTURE_PROTOCOL_ID,
        "status": "RESERVED",
        "reserved_at": started_at,
        "git_commit": commit,
    }
    attempt = {
        "run_id": CAPTURE_MANIFEST_ID,
        "protocol_id": CAPTURE_PROTOCOL_ID,
        "experiment_type": (
            "baseline-informed-capture-treatment-outcome-free-paired-manifest"
        ),
        "status": "STARTED",
        "started_at": started_at,
        "git_commit": commit,
        "git_dirty": False,
        "environment": {"python": sys.version, "platform": platform.platform()},
        "component_versions": dict(_MANIFEST_COMPONENT_VERSIONS),
        "configuration": {
            "source_manifest_id": CAPTURE_SOURCE_MANIFEST_ID,
            "source_manifest_path": str(source_manifest_path.resolve()),
            "source_manifest_sha256": CAPTURE_SOURCE_MANIFEST_SHA256,
            "destination": str(corpus_directory.resolve()),
            "baseline_outcomes_informed_protocol_design": True,
            "stalemate_outcomes_informed_protocol_design": True,
            "case_membership_outcome_fields_consulted": False,
            "capture_treatment_outcomes_computed": False,
        },
    }
    phase = "MANIFEST_SETUP"
    try:
        _write_exclusive(
            corpus_directory / "manifest-reservation.json", reservation
        )
        _write_exclusive(corpus_directory / "manifest-attempt.json", attempt)
        phase = "MANIFEST_CONSTRUCTION"
        expected = build_capture_paired_manifest(
            source_manifest,
            CAPTURE_SOURCE_MANIFEST_SHA256,
            provenance,
        )
        manifest = manifest_builder(
            copy.deepcopy(source_manifest),
            CAPTURE_SOURCE_MANIFEST_SHA256,
            copy.deepcopy(provenance),
        )
        if not isinstance(manifest, Mapping):
            raise ValueError("capture manifest builder must return an object")
        if manifest != expected or manifest.get("provenance") != provenance:
            raise ValueError(
                "capture manifest builder output differs from canonical construction"
            )
        validate_capture_paired_manifest(manifest)
        _assert_no_outcome_keys(manifest, "capture_manifest")
        manifest_bytes = _encoded_json(manifest)
        manifest_path = corpus_directory / "manifest.json"
        with manifest_path.open("xb") as destination:
            destination.write(manifest_bytes)
        lock = {
            "manifest_id": CAPTURE_MANIFEST_ID,
            "protocol_id": CAPTURE_PROTOCOL_ID,
            "manifest_sha256": _sha256(manifest_bytes),
            "manifest_bytes": len(manifest_bytes),
            "freezer_git_commit": commit,
        }
        _write_exclusive(corpus_directory / "manifest.lock.json", lock)
    except BaseException as error:
        _record_failure_preserving_original(
            corpus_directory / "manifest-failure.json",
            attempt,
            phase,
            error,
        )
        raise
    return manifest_path


def _require_same_fingerprints(
    repository: Path, manifest: Mapping[str, Any]
) -> None:
    provenance = manifest.get("provenance")
    if not isinstance(provenance, Mapping):
        raise ValueError("capture manifest provenance is missing")
    if (
        provenance.get("protocol_fingerprints")
        != _current_protocol_fingerprints(repository)
        or provenance.get("executable_fingerprints")
        != _current_fingerprints(repository)
    ):
        raise ValueError("capture protocol or executable fingerprints changed")


def _require_unchanged_bytes(
    path: Path, expected_sha256: str, label: str
) -> None:
    try:
        source_bytes = path.read_bytes()
    except OSError as error:
        raise ValueError("{} disappeared during evaluation".format(label)) from error
    if _sha256(source_bytes) != expected_sha256:
        raise ValueError("{} bytes changed during evaluation".format(label))


def _chain_hashes(paths: Sequence[Path]) -> Mapping[str, str]:
    result: Dict[str, str] = {}
    for path in paths:
        try:
            result[str(path.resolve())] = _sha256(path.read_bytes())
        except OSError as error:
            raise ValueError("evidence chain file is unreadable: {}".format(path)) from error
    return result


def _require_chain_unchanged(hashes: Mapping[str, str]) -> None:
    for absolute, expected in hashes.items():
        _require_unchanged_bytes(Path(absolute), expected, "evidence chain file")


def _record_failure_preserving_original(
    path: Path,
    attempt: Mapping[str, Any],
    phase: str,
    error: BaseException,
) -> None:
    """Write exclusive failure evidence without silently losing the root cause."""

    try:
        _write_failure(path, attempt, phase, error)
    except BaseException as evidence_error:
        raise RuntimeError(
            "{} failed and its failure evidence could not be written: {}".format(
                phase, evidence_error
            )
        ) from error


def _capture_manifest_chain_paths(repository: Path) -> Tuple[Path, ...]:
    return (
        repository / CAPTURE_MANIFEST_RESERVATION_RELATIVE,
        repository / CAPTURE_MANIFEST_ATTEMPT_RELATIVE,
        repository / CAPTURE_MANIFEST_RELATIVE,
        repository / CAPTURE_LOCK_RELATIVE,
    )


def _source_landscape_chain_paths(repository: Path) -> Tuple[Path, ...]:
    """List every mutable working-tree file read by the historical validators."""

    return (
        repository / SOURCE_LANDSCAPE_MANIFEST_RELATIVE,
        repository / SOURCE_LANDSCAPE_LOCK_RELATIVE,
        repository / SOURCE_LANDSCAPE_ATTEMPT_RELATIVE,
        repository
        / "experiments/runs/.{}.reservation.json".format(
            LANDSCAPE_RAW_PROTOCOL_ID
        ),
        repository / SOURCE_LANDSCAPE_RAW_RELATIVE.parent / "attempt.json",
        repository / SOURCE_LANDSCAPE_RAW_RELATIVE,
    )


def _case_from_pair(pair: Mapping[str, Any], treatment: bool) -> Dict[str, Any]:
    prefix = "treatment" if treatment else "source"
    identity = (
        {
            "pair_id": pair["pair_id"],
            "source_case_id": pair["source_case_id"],
        }
        if treatment
        else {"case_id": pair["source_case_id"]}
    )
    return {
        **identity,
        "stratum": copy.deepcopy(pair["stratum"]),
        "vector_count": pair["vector_count"],
        "definition_hash": pair[prefix + "_definition_hash"],
        "d4_canonical_hash": pair[prefix + "_d4_canonical_hash"],
        "definition": copy.deepcopy(pair[prefix + "_definition"]),
    }


def _validate_stage_cases(
    cases: Sequence[Mapping[str, Any]],
    pairs: Sequence[Mapping[str, Any]],
    treatment: bool,
) -> None:
    if len(cases) != CAPTURE_PAIR_COUNT or len(pairs) != CAPTURE_PAIR_COUNT:
        raise ValueError("capture evaluator stage must contain exactly 128 cases")
    prefix = "treatment" if treatment else "source"
    expected_keys = {
        "stratum",
        "vector_count",
        "definition_hash",
        "d4_canonical_hash",
        "definition",
    }
    expected_keys.update(
        {"pair_id", "source_case_id"} if treatment else {"case_id"}
    )
    for index, (case, pair) in enumerate(zip(cases, pairs)):
        if not isinstance(case, Mapping) or set(case) != expected_keys:
            raise ValueError("{} evaluator case {} schema mismatch".format(prefix, index))
        if (
            (
                treatment
                and (
                    case.get("pair_id") != pair["pair_id"]
                    or case.get("source_case_id") != pair["source_case_id"]
                )
            )
            or (not treatment and case.get("case_id") != pair["source_case_id"])
            or case.get("stratum") != pair["stratum"]
            or case.get("vector_count") != pair["vector_count"]
            or case.get("definition_hash") != pair[prefix + "_definition_hash"]
            or case.get("d4_canonical_hash")
            != pair[prefix + "_d4_canonical_hash"]
            or case.get("definition") != pair[prefix + "_definition"]
        ):
            raise ValueError(
                "{} evaluator case {} identity or order mismatch".format(
                    prefix, index
                )
            )


def _assessment_status(
    assessments: Mapping[str, Any], key: str, label: str
) -> str:
    assessment = assessments.get(key)
    status = assessment.get("status") if isinstance(assessment, Mapping) else None
    if not isinstance(status, str):
        raise ValueError("{} assessment {} is missing".format(label, key))
    return status


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
        raise ValueError("{} narrative fields do not match result".format(label))


def _evaluator_candidates(value: Any, label: str) -> Tuple[Mapping[str, Any], ...]:
    candidates = value.get("candidates") if isinstance(value, Mapping) else value
    if not isinstance(candidates, (list, tuple)):
        raise ValueError("{} must provide a candidate sequence".format(label))
    if not all(isinstance(candidate, Mapping) for candidate in candidates):
        raise ValueError("{} candidates must be objects".format(label))
    return tuple(candidates)


def _pinned_baseline_candidates(
    baseline_results: Mapping[str, Any], pairs: Sequence[Mapping[str, Any]]
) -> Tuple[Mapping[str, Any], ...]:
    all_candidates = _evaluator_candidates(baseline_results, "pinned baseline")
    by_case: Dict[str, Mapping[str, Any]] = {}
    for candidate in all_candidates:
        case_id = candidate.get("case_id")
        if not isinstance(case_id, str) or case_id in by_case:
            raise ValueError("pinned baseline case identities must be unique")
        by_case[case_id] = candidate
    selected = []
    for pair in pairs:
        candidate = by_case.get(pair["source_case_id"])
        if candidate is None:
            raise ValueError("pinned baseline is missing a capture source case")
        selected.append(candidate)
    return tuple(selected)


def _raw_narrative(result: Mapping[str, Any]) -> Mapping[str, Any]:
    aggregate = result.get("aggregate")
    timing = result.get("timing")
    if not isinstance(aggregate, Mapping) or not isinstance(timing, Mapping):
        raise ValueError("capture raw narrative requires aggregate and timing")
    assessments = aggregate.get("predeclared_assessment")
    if not isinstance(assessments, Mapping):
        raise ValueError("capture raw narrative requires assessments")
    exact = _assessment_status(assessments, "exact_completion", "capture raw")
    primary = _assessment_status(
        assessments, "primary_counterplay_response", "capture raw"
    )
    realized = _assessment_status(
        assessments, "realized_capture_response", "capture raw"
    )
    disposition = aggregate.get("adaptive_stress_disposition")
    if disposition not in ("ELIGIBLE", "BLOCKED_EXACT_CENSOR"):
        raise ValueError("capture raw stress disposition is missing")
    decision = (
        "AUDIT_STATE_BOUND_OR_SOLVER"
        if disposition == "BLOCKED_EXACT_CENSOR"
        else "COMMIT_RAW_THEN_RUN_PREDECLARED_STRESS"
    )
    return {
        "hypothesis": (
            "B move-capture will produce at least four paired-valid non-horizon "
            "containment responses and four realized-capture PVs across two strata."
        ),
        "baseline": (
            "All 128 pinned schema-v1 cases are freshly replayed and sealed in a "
            "timing-free observed-versus-pinned attestation before treatment."
        ),
        "treatment": (
            "Each schema-v3 pair changes only B MOVE to MOVE_CAPTURE under "
            "schema-v1 terminal semantics and a 100000-state exact cap."
        ),
        "expected_result": (
            "All treatments complete within the proved 43776-state bound and "
            "show multi-stratum non-horizon capture counterplay."
        ),
        "actual_result": {**dict(aggregate), "timing": timing},
        "interpretation": (
            "Exact completion is {}; primary response is {}; realized-capture "
            "response is {}; adaptive stress is {}."
        ).format(exact, primary, realized, disposition),
        "decision": decision,
    }


def _stress_narrative(result: Mapping[str, Any]) -> Mapping[str, Any]:
    aggregate = result.get("aggregate")
    if not isinstance(aggregate, Mapping):
        raise ValueError("capture stress narrative requires aggregate")
    assessments = aggregate.get("predeclared_assessment")
    if not isinstance(assessments, Mapping):
        raise ValueError("capture stress narrative requires assessments")
    general = _assessment_status(
        assessments, "general_strong_response", "capture stress"
    )
    frontier = _assessment_status(
        assessments, "interaction_frontier", "capture stress"
    )
    overall = _assessment_status(
        assessments, "overall_interaction_response", "capture stress"
    )
    overall_assessment = assessments.get("overall_interaction_response")
    decision = (
        overall_assessment.get("next_branch")
        if isinstance(overall_assessment, Mapping)
        else None
    )
    if not isinstance(decision, str):
        raise ValueError("capture stress next branch is missing")
    return {
        "hypothesis": (
            "Depth-5 play will reproduce exact direction, execute capture, and "
            "leave a role-diverse shape-clean interaction frontier."
        ),
        "baseline": (
            "The committed paired raw record fixes exact response, paired validity, "
            "capture evidence, eligibility, and deterministic ordering."
        ),
        "treatment": (
            "At most 32 eligible schema-v3 cases receive depth-5 self-play over "
            "seeds 0..29 with a cumulative 5000000-node cap per case."
        ),
        "expected_result": (
            "At least 15 profiles complete without censor or direction mismatch, "
            "and capture-engaged frontier cases include exact wins for both roles."
        ),
        "actual_result": dict(aggregate),
        "interpretation": (
            "General strong response is {}; frontier response is {}; overall "
            "interaction response is {}."
        ).format(general, frontier, overall),
        "decision": decision,
    }


def _validate_frozen_capture_manifest(
    manifest_path: Path, lock_path: Path, repository: Path
) -> Tuple[bytes, Mapping[str, Any]]:
    failure_path = repository / CAPTURE_CORPUS_RELATIVE / "manifest-failure.json"
    if failure_path.exists():
        raise ValueError("capture manifest cannot coexist with failure evidence")
    _require_canonical_path(
        manifest_path,
        repository,
        CAPTURE_MANIFEST_RELATIVE,
        "capture manifest",
    )
    _require_canonical_path(
        lock_path, repository, CAPTURE_LOCK_RELATIVE, "capture manifest lock"
    )
    attempt_path = repository / CAPTURE_MANIFEST_ATTEMPT_RELATIVE
    reservation_path = repository / CAPTURE_MANIFEST_RESERVATION_RELATIVE
    for path, label in (
        (manifest_path, "capture manifest"),
        (lock_path, "capture manifest lock"),
        (attempt_path, "capture manifest attempt"),
        (reservation_path, "capture manifest reservation"),
    ):
        _require_tracked(path, repository, label)
    manifest_bytes, manifest = _read_json_bytes(manifest_path, "capture manifest")
    if manifest_bytes != _encoded_json(manifest):
        raise ValueError("capture manifest bytes are not canonical JSON")
    _, lock = _read_json_bytes(lock_path, "capture manifest lock")
    _, attempt = _read_json_bytes(attempt_path, "capture manifest attempt")
    _, reservation = _read_json_bytes(
        reservation_path, "capture manifest reservation"
    )
    freezer_commit = attempt.get("git_commit")
    if lock != {
        "manifest_id": CAPTURE_MANIFEST_ID,
        "protocol_id": CAPTURE_PROTOCOL_ID,
        "manifest_sha256": _sha256(manifest_bytes),
        "manifest_bytes": len(manifest_bytes),
        "freezer_git_commit": freezer_commit,
    }:
        raise ValueError("capture manifest lock does not match exact bytes")
    if reservation != {
        "run_id": CAPTURE_MANIFEST_ID,
        "protocol_id": CAPTURE_PROTOCOL_ID,
        "status": "RESERVED",
        "reserved_at": attempt.get("started_at"),
        "git_commit": freezer_commit,
    }:
        raise ValueError("capture manifest reservation mismatch")
    expected_configuration_keys = {
        "source_manifest_id",
        "source_manifest_path",
        "source_manifest_sha256",
        "destination",
        "baseline_outcomes_informed_protocol_design",
        "stalemate_outcomes_informed_protocol_design",
        "case_membership_outcome_fields_consulted",
        "capture_treatment_outcomes_computed",
    }
    configuration = attempt.get("configuration")
    environment = attempt.get("environment")
    if (
        set(attempt) != _ATTEMPT_KEYS
        or attempt.get("run_id") != CAPTURE_MANIFEST_ID
        or attempt.get("protocol_id") != CAPTURE_PROTOCOL_ID
        or attempt.get("experiment_type")
        != "baseline-informed-capture-treatment-outcome-free-paired-manifest"
        or attempt.get("status") != "STARTED"
        or attempt.get("git_dirty") is not False
        or _encoded_json(attempt.get("component_versions"))
        != _encoded_json(_MANIFEST_COMPONENT_VERSIONS)
        or not isinstance(environment, Mapping)
        or set(environment) != {"python", "platform"}
        or not all(isinstance(value, str) for value in environment.values())
        or not isinstance(configuration, Mapping)
        or set(configuration) != expected_configuration_keys
        or configuration.get("source_manifest_id")
        != CAPTURE_SOURCE_MANIFEST_ID
        or configuration.get("source_manifest_sha256")
        != CAPTURE_SOURCE_MANIFEST_SHA256
        or configuration.get("baseline_outcomes_informed_protocol_design")
        is not True
        or configuration.get("stalemate_outcomes_informed_protocol_design")
        is not True
        or configuration.get("case_membership_outcome_fields_consulted")
        is not False
        or configuration.get("capture_treatment_outcomes_computed") is not False
    ):
        raise ValueError("capture manifest attempt mismatch")
    _require_timestamp(attempt.get("started_at"), "capture manifest attempt")
    source_root = _recorded_repository_root(
        configuration["source_manifest_path"],
        SOURCE_LANDSCAPE_MANIFEST_RELATIVE,
        "capture manifest attempt source",
    )
    destination_root = _recorded_repository_root(
        configuration["destination"],
        CAPTURE_CORPUS_RELATIVE,
        "capture manifest attempt destination",
    )
    if source_root != destination_root:
        raise ValueError("capture manifest attempt repository roots differ")
    freezer_commit = _require_commit_ancestor(
        freezer_commit, repository, "capture manifest freezer commit"
    )
    _, source_manifest = _validate_source_landscape_manifest(
        repository / SOURCE_LANDSCAPE_MANIFEST_RELATIVE, repository
    )
    pairs = validate_capture_paired_manifest(manifest)
    if len(pairs) != CAPTURE_PAIR_COUNT:
        raise ValueError("capture manifest pair count mismatch")
    _assert_no_outcome_keys(manifest, "capture_manifest")
    provenance = manifest.get("provenance")
    if (
        not isinstance(provenance, Mapping)
        or set(provenance) != _MANIFEST_PROVENANCE_KEYS
    ):
        raise ValueError("capture manifest provenance schema mismatch")
    expected_protocol = _frozen_source_fingerprints_at_commit(
        repository, freezer_commit, _FROZEN_PROTOCOL_RELATIVES
    )
    expected_executables = _frozen_source_fingerprints_at_commit(
        repository, freezer_commit, _FROZEN_EXECUTABLE_RELATIVES
    )
    if (
        provenance.get("freezer_git_commit") != freezer_commit
        or provenance.get("freezer_git_dirty") is not False
        or provenance.get("created_at") != attempt.get("started_at")
        or provenance.get("protocol_id") != CAPTURE_PROTOCOL_ID
        or provenance.get("source_manifest_path")
        != str(SOURCE_LANDSCAPE_MANIFEST_RELATIVE)
        or provenance.get("source_manifest_sha256")
        != CAPTURE_SOURCE_MANIFEST_SHA256
        or provenance.get("baseline_outcomes_informed_protocol_design") is not True
        or provenance.get("stalemate_outcomes_informed_protocol_design") is not True
        or provenance.get("case_membership_outcome_fields_consulted") is not False
        or provenance.get("source_manifest_contains_outcomes") is not False
        or provenance.get("capture_treatment_outcomes_computed") is not False
        or provenance.get("protocol_fingerprints") != expected_protocol
        or provenance.get("executable_fingerprints") != expected_executables
    ):
        raise ValueError("capture manifest provenance mismatch")
    expected = build_capture_paired_manifest(
        source_manifest, CAPTURE_SOURCE_MANIFEST_SHA256, provenance
    )
    if manifest != expected:
        raise ValueError("capture manifest is not reproducible from pinned source")
    _require_same_fingerprints(repository, manifest)
    return manifest_bytes, manifest


def _validate_capture_raw_configuration(
    configuration: Any, manifest: Mapping[str, Any]
) -> None:
    if (
        not isinstance(configuration, Mapping)
        or set(configuration) != _RAW_CONFIGURATION_KEYS
        or configuration.get("manifest_id") != CAPTURE_MANIFEST_ID
        or configuration.get("manifest_sha256")
        != _sha256(_encoded_json(manifest))
        or configuration.get("source_landscape_raw_run_id")
        != SOURCE_LANDSCAPE_RAW_RUN_ID
        or configuration.get("source_landscape_raw_sha256")
        != SOURCE_LANDSCAPE_RAW_SHA256
        or _encoded_json(configuration.get("play_seeds"))
        != _encoded_json(list(CAPTURE_PLAY_SEEDS))
        or _encoded_json(configuration.get("play_gates"))
        != _encoded_json(asdict(PlayGates()))
        or configuration.get("max_exact_states") != CAPTURE_EXACT_MAX_STATES
        or configuration.get("structural_state_bound") != CAPTURE_STATE_BOUND
        or configuration.get("replay_attestation_version")
        != CAPTURE_REPLAY_ATTESTATION_VERSION
        or _encoded_json(configuration.get("phase_order"))
        != _encoded_json(list(_RAW_PHASE_ORDER))
    ):
        raise ValueError("capture paired raw configuration mismatch")
    manifest_root = _recorded_repository_root(
        configuration["manifest_path"],
        CAPTURE_MANIFEST_RELATIVE,
        "capture paired raw manifest path",
    )
    source_root = _recorded_repository_root(
        configuration["source_landscape_raw_path"],
        SOURCE_LANDSCAPE_RAW_RELATIVE,
        "capture paired raw historical source path",
    )
    if manifest_root != source_root:
        raise ValueError("capture paired raw configuration roots differ")


def _validate_capture_result_against_pinned_source(
    result: Mapping[str, Any],
    manifest: Mapping[str, Any],
    repository: Path,
) -> Mapping[str, Any]:
    """Re-read the immutable landscape chain before trusting capture raw."""

    pairs = validate_capture_paired_manifest(manifest)
    _, pinned_record = _validate_source_landscape_raw(
        repository / SOURCE_LANDSCAPE_RAW_RELATIVE,
        repository,
        pairs,
    )
    validated = validate_capture_paired_result(
        result,
        manifest,
        pinned_record["results"],
    )
    return validated


def _validate_capture_paired_raw_source(
    raw_run_path: Path,
    output_root: Path,
    repository: Path,
    manifest: Mapping[str, Any],
) -> Tuple[bytes, Mapping[str, Any]]:
    protocol_failure = output_root / ".{}.failure.json".format(
        CAPTURE_RAW_PROTOCOL_ID
    )
    if protocol_failure.exists():
        raise ValueError(
            "capture paired raw cannot coexist with protocol setup failure evidence"
        )
    if raw_run_path.is_symlink():
        raise ValueError("capture paired raw source cannot be a symlink")
    try:
        relative = raw_run_path.resolve().relative_to(output_root.resolve())
    except ValueError as error:
        raise ValueError(
            "capture paired raw source must be in the canonical run directory"
        ) from error
    if len(relative.parts) != 2 or relative.parts[1] != "run.json":
        raise ValueError("capture paired raw source must be <run-id>/run.json")
    _require_tracked(raw_run_path, repository, "capture paired raw source")
    raw_bytes, record = _read_json_bytes(raw_run_path, "capture paired raw source")
    if raw_bytes != _encoded_json(record):
        raise ValueError("capture paired raw source bytes are not canonical JSON")
    if (
        set(record) != _COMPLETED_RUN_KEYS
        or record.get("run_id") != relative.parts[0]
        or record.get("protocol_id") != CAPTURE_RAW_PROTOCOL_ID
        or record.get("experiment_type") != "capture-v1-v3-paired-exact"
        or record.get("status") != "COMPLETED"
        or record.get("git_dirty") is not False
        or _encoded_json(record.get("component_versions"))
        != _encoded_json(_RAW_COMPONENT_VERSIONS)
    ):
        raise ValueError("capture paired raw source identity mismatch")
    attempt = _validate_completed_run_attempt(
        raw_run_path,
        record,
        repository,
        _RAW_COMPONENT_VERSIONS,
    )
    _validate_protocol_reservation(
        output_root,
        CAPTURE_RAW_PROTOCOL_ID,
        record["run_id"],
        attempt["git_commit"],
        attempt["started_at"],
        repository,
    )
    provenance = manifest["provenance"]
    historical_protocol = _frozen_source_fingerprints_at_commit(
        repository,
        attempt["git_commit"],
        tuple(Path(relative) for relative in provenance["protocol_fingerprints"]),
    )
    historical_executables = _frozen_source_fingerprints_at_commit(
        repository,
        attempt["git_commit"],
        tuple(Path(relative) for relative in provenance["executable_fingerprints"]),
    )
    if (
        historical_protocol != provenance["protocol_fingerprints"]
        or historical_executables != provenance["executable_fingerprints"]
    ):
        raise ValueError("capture paired raw changed frozen protocol sources")
    result = record.get("results")
    if not isinstance(result, Mapping):
        raise ValueError("capture paired raw result is missing")
    _validate_capture_result_against_pinned_source(result, manifest, repository)
    _validate_completed_narrative(record, result, _raw_narrative, "capture paired raw")
    _validate_capture_raw_configuration(record.get("configuration"), manifest)
    return raw_bytes, record


def _validate_capture_stress_configuration(
    configuration: Any,
    manifest: Mapping[str, Any],
    raw_record: Mapping[str, Any],
) -> None:
    if (
        not isinstance(configuration, Mapping)
        or set(configuration) != _STRESS_CONFIGURATION_KEYS
        or configuration.get("manifest_id") != CAPTURE_MANIFEST_ID
        or configuration.get("manifest_sha256")
        != _sha256(_encoded_json(manifest))
        or configuration.get("source_raw_run_id") != raw_record.get("run_id")
        or configuration.get("source_raw_sha256")
        != _sha256(_encoded_json(raw_record))
        or _encoded_json(configuration.get("seeds"))
        != _encoded_json(list(CAPTURE_STRESS_SEEDS))
        or configuration.get("depth") != CAPTURE_STRESS_DEPTH
        or configuration.get("max_nodes_per_candidate")
        != CAPTURE_STRESS_MAX_NODES
        or configuration.get("max_candidates")
        != CAPTURE_STRESS_MAX_CANDIDATES
        or _encoded_json(configuration.get("play_gates"))
        != _encoded_json(asdict(PlayGates()))
    ):
        raise ValueError("capture interaction stress configuration mismatch")
    manifest_root = _recorded_repository_root(
        configuration["manifest_path"],
        CAPTURE_MANIFEST_RELATIVE,
        "capture stress manifest path",
    )
    raw_relative = Path("experiments/runs") / str(raw_record["run_id"]) / "run.json"
    raw_root = _recorded_repository_root(
        configuration["source_raw_path"],
        raw_relative,
        "capture stress raw source path",
    )
    if manifest_root != raw_root:
        raise ValueError("capture stress configuration roots differ")


def run_capture_paired(
    manifest_path: Path,
    lock_path: Path,
    source_raw_path: Path,
    output_root: Path,
    repository: Path,
    paired_evaluator: PairedEvaluator = evaluate_capture_pairs,
    baseline_evaluator: BatchEvaluator = evaluate_landscape_cases,
    treatment_evaluator: BatchEvaluator = evaluate_capture_cases,
) -> Path:
    """Run the one-shot v1 replay and v3 capture evaluation in frozen order."""

    if output_root.resolve() != (repository / "experiments/runs").resolve():
        raise ValueError("capture evidence must use the repository run directory")
    if not all(
        callable(item)
        for item in (paired_evaluator, baseline_evaluator, treatment_evaluator)
    ):
        raise TypeError("capture evaluators must be callable")
    manifest_bytes, manifest = _validate_frozen_capture_manifest(
        manifest_path, lock_path, repository
    )
    pairs = validate_capture_paired_manifest(manifest)
    source_raw_bytes, source_raw = _validate_source_landscape_raw(
        source_raw_path, repository, pairs
    )
    pinned_baseline_results = copy.deepcopy(source_raw["results"])
    commit = _require_clean_repository(repository)
    _require_same_fingerprints(repository, manifest)
    _scan_prior_protocol(output_root, CAPTURE_RAW_PROTOCOL_ID)
    chain_paths = (
        *_capture_manifest_chain_paths(repository),
        *_source_landscape_chain_paths(repository),
    )
    chain_hashes = _chain_hashes(chain_paths)
    started = _utc_now()
    started_at = _timestamp(started)
    manifest_hash = _sha256(manifest_bytes)
    run_id = "{}-capture-{}".format(
        started.strftime("%Y%m%dT%H%M%S%fZ"), manifest_hash[:8]
    )
    attempt = {
        "run_id": run_id,
        "protocol_id": CAPTURE_RAW_PROTOCOL_ID,
        "experiment_type": "capture-v1-v3-paired-exact",
        "status": "STARTED",
        "started_at": started_at,
        "git_commit": commit,
        "git_dirty": False,
        "environment": {"python": sys.version, "platform": platform.platform()},
        "component_versions": dict(_RAW_COMPONENT_VERSIONS),
        "configuration": {
            "manifest_id": CAPTURE_MANIFEST_ID,
            "manifest_path": str(manifest_path.resolve()),
            "manifest_sha256": manifest_hash,
            "source_landscape_raw_run_id": SOURCE_LANDSCAPE_RAW_RUN_ID,
            "source_landscape_raw_path": str(source_raw_path.resolve()),
            "source_landscape_raw_sha256": SOURCE_LANDSCAPE_RAW_SHA256,
            "play_seeds": list(CAPTURE_PLAY_SEEDS),
            "play_gates": asdict(PlayGates()),
            "max_exact_states": CAPTURE_EXACT_MAX_STATES,
            "structural_state_bound": CAPTURE_STATE_BOUND,
            "replay_attestation_version": CAPTURE_REPLAY_ATTESTATION_VERSION,
            "phase_order": list(_RAW_PHASE_ORDER),
        },
    }
    _validate_capture_raw_configuration(attempt["configuration"], manifest)
    _reserve_protocol(
        output_root, CAPTURE_RAW_PROTOCOL_ID, run_id, commit, started_at
    )
    run_directory = output_root / run_id
    try:
        run_directory.mkdir(parents=False, exist_ok=False)
    except BaseException as error:
        _record_failure_preserving_original(
            output_root / ".{}.failure.json".format(CAPTURE_RAW_PROTOCOL_ID),
            attempt,
            "RAW_RUN_DIRECTORY_SETUP",
            error,
        )
        raise
    try:
        _write_exclusive(run_directory / "attempt.json", attempt)
    except BaseException as error:
        _record_failure_preserving_original(
            run_directory / "failure.json", attempt, "RAW_SETUP", error
        )
        raise
    phase: Dict[str, Any] = {
        "name": "BASELINE_REPLAY",
        "baseline_calls": 0,
        "treatment_calls": 0,
        "baseline_attested": False,
    }

    def staged_baseline_evaluator(
        cases: Sequence[Mapping[str, Any]],
    ) -> Mapping[str, Any]:
        phase["baseline_calls"] += 1
        if phase["baseline_calls"] != 1 or phase["treatment_calls"] != 0:
            raise ValueError("baseline evaluator must be invoked exactly once and first")
        phase["name"] = "BASELINE_REPLAY"
        _validate_stage_cases(cases, pairs, treatment=False)
        evaluated = baseline_evaluator(
            copy.deepcopy(cases),
            play_seeds=CAPTURE_PLAY_SEEDS,
            max_exact_states=CAPTURE_EXACT_MAX_STATES,
            gates=PlayGates(),
            clock=time.perf_counter,
        )
        if not isinstance(evaluated, Mapping):
            raise ValueError("baseline evaluator must return an object")
        phase["name"] = "BASELINE_REPLAY_ATTESTATION"
        observed = _evaluator_candidates(evaluated, "fresh baseline")
        validate_capture_baseline_replay(
            pairs,
            observed,
            _evaluator_candidates(pinned_baseline_results, "pinned baseline"),
        )
        phase["baseline_attested"] = True
        return evaluated

    def staged_treatment_evaluator(
        cases: Sequence[Mapping[str, Any]],
    ) -> Mapping[str, Any]:
        phase["treatment_calls"] += 1
        phase["name"] = "TREATMENT_EVALUATION_CONTRACT"
        if phase["treatment_calls"] != 1:
            raise ValueError("treatment evaluator must be invoked exactly once")
        if phase["baseline_calls"] != 1 or phase["baseline_attested"] is not True:
            raise ValueError("treatment evaluation requires an attested baseline replay")
        phase["name"] = "TREATMENT_EVALUATION"
        _validate_stage_cases(cases, pairs, treatment=True)
        _require_same_fingerprints(repository, manifest)
        _require_chain_unchanged(chain_hashes)
        evaluated = treatment_evaluator(
            copy.deepcopy(cases),
            play_seeds=CAPTURE_PLAY_SEEDS,
            max_exact_states=CAPTURE_EXACT_MAX_STATES,
            gates=PlayGates(),
            clock=time.perf_counter,
        )
        if not isinstance(evaluated, Mapping):
            raise ValueError("treatment evaluator must return an object")
        validate_capture_case_evaluation(
            evaluated,
            cases,
            play_seeds=CAPTURE_PLAY_SEEDS,
            max_exact_states=CAPTURE_EXACT_MAX_STATES,
            gates=PlayGates(),
        )
        phase["name"] = "PAIRED_SUMMARY"
        return evaluated

    try:
        result = paired_evaluator(
            copy.deepcopy(manifest),
            copy.deepcopy(pinned_baseline_results),
            baseline_evaluator=staged_baseline_evaluator,
            treatment_evaluator=staged_treatment_evaluator,
        )
        if (
            phase["baseline_calls"] != 1
            or phase["treatment_calls"] != 1
            or phase["baseline_attested"] is not True
        ):
            phase["name"] = "PAIRED_EVALUATION_CONTRACT"
            raise ValueError(
                "paired evaluator must invoke attested baseline then treatment once"
            )
        if not isinstance(result, Mapping):
            raise ValueError("paired evaluator must return an object")
        validate_capture_paired_result(
            result,
            manifest,
            pinned_baseline_results,
        )
        _require_same_fingerprints(repository, manifest)
        _require_chain_unchanged(chain_hashes)
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
            record, result, _raw_narrative, "capture paired raw"
        )
        destination = run_directory / "run.json"
        _write_exclusive(destination, record)
    except BaseException as error:
        _record_failure_preserving_original(
            run_directory / "failure.json",
            attempt,
            str(phase["name"]),
            error,
        )
        raise
    return destination


def run_capture_interaction_stress(
    raw_run_path: Path,
    manifest_path: Path,
    lock_path: Path,
    output_root: Path,
    repository: Path,
    stress_evaluator: StressEvaluator = stress_capture_interactions,
) -> Path:
    """Run the separately reserved depth-5 capture interaction stress."""

    if output_root.resolve() != (repository / "experiments/runs").resolve():
        raise ValueError("capture stress must use the repository run directory")
    if not callable(stress_evaluator):
        raise TypeError("stress_evaluator must be callable")
    manifest_bytes, manifest = _validate_frozen_capture_manifest(
        manifest_path, lock_path, repository
    )
    raw_bytes, raw_record = _validate_capture_paired_raw_source(
        raw_run_path, output_root, repository, manifest
    )
    raw_result = raw_record["results"]
    raw_aggregate = raw_result.get("aggregate")
    inspection = raw_result.get("pre_stress_inspection")
    if not isinstance(raw_aggregate, Mapping) or not isinstance(inspection, Mapping):
        raise ValueError("capture paired raw stress evidence is missing")
    if (
        raw_aggregate.get("exact_censored") != 0
        or raw_aggregate.get("adaptive_stress_disposition") != "ELIGIBLE"
        or inspection.get("adaptive_stress_disposition") != "ELIGIBLE"
    ):
        raise ValueError("exact censoring blocks capture stress before reservation")
    commit = _require_clean_repository(repository)
    _require_same_fingerprints(repository, manifest)
    _scan_prior_protocol(output_root, CAPTURE_STRESS_PROTOCOL_ID)
    raw_reservation = output_root / ".{}.reservation.json".format(
        CAPTURE_RAW_PROTOCOL_ID
    )
    chain_hashes = _chain_hashes(
        (
            *_capture_manifest_chain_paths(repository),
            *_source_landscape_chain_paths(repository),
            raw_reservation,
            raw_run_path.parent / "attempt.json",
            raw_run_path,
        )
    )
    started = _utc_now()
    started_at = _timestamp(started)
    raw_hash = _sha256(raw_bytes)
    run_id = "{}-capture-stress-{}".format(
        started.strftime("%Y%m%dT%H%M%S%fZ"), raw_hash[:8]
    )
    attempt = {
        "run_id": run_id,
        "protocol_id": CAPTURE_STRESS_PROTOCOL_ID,
        "experiment_type": "capture-v1-depth5-interaction-stress",
        "status": "STARTED",
        "started_at": started_at,
        "git_commit": commit,
        "git_dirty": False,
        "environment": {"python": sys.version, "platform": platform.platform()},
        "component_versions": dict(_STRESS_COMPONENT_VERSIONS),
        "configuration": {
            "manifest_id": CAPTURE_MANIFEST_ID,
            "manifest_path": str(manifest_path.resolve()),
            "manifest_sha256": _sha256(manifest_bytes),
            "source_raw_run_id": raw_record["run_id"],
            "source_raw_path": str(raw_run_path.resolve()),
            "source_raw_sha256": raw_hash,
            "seeds": list(CAPTURE_STRESS_SEEDS),
            "depth": CAPTURE_STRESS_DEPTH,
            "max_nodes_per_candidate": CAPTURE_STRESS_MAX_NODES,
            "max_candidates": CAPTURE_STRESS_MAX_CANDIDATES,
            "play_gates": asdict(PlayGates()),
        },
    }
    _validate_capture_stress_configuration(
        attempt["configuration"], manifest, raw_record
    )
    _reserve_protocol(
        output_root,
        CAPTURE_STRESS_PROTOCOL_ID,
        run_id,
        commit,
        started_at,
    )
    run_directory = output_root / run_id
    try:
        run_directory.mkdir(parents=False, exist_ok=False)
    except BaseException as error:
        _record_failure_preserving_original(
            output_root / ".{}.failure.json".format(CAPTURE_STRESS_PROTOCOL_ID),
            attempt,
            "STRESS_RUN_DIRECTORY_SETUP",
            error,
        )
        raise
    try:
        _write_exclusive(run_directory / "attempt.json", attempt)
    except BaseException as error:
        _record_failure_preserving_original(
            run_directory / "failure.json", attempt, "STRESS_SETUP", error
        )
        raise
    phase = "INTERACTION_STRESS_EVALUATION"
    try:
        result = stress_evaluator(
            copy.deepcopy(raw_result),
            seeds=CAPTURE_STRESS_SEEDS,
            depth=CAPTURE_STRESS_DEPTH,
            max_nodes=CAPTURE_STRESS_MAX_NODES,
            max_candidates=CAPTURE_STRESS_MAX_CANDIDATES,
            gates=PlayGates(),
            clock=time.perf_counter,
        )
        if not isinstance(result, Mapping):
            raise ValueError("capture stress evaluator must return an object")
        validate_capture_stress_result(result, raw_result, gates=PlayGates())
        _require_same_fingerprints(repository, manifest)
        _require_chain_unchanged(chain_hashes)
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
            record, result, _stress_narrative, "capture interaction stress"
        )
        destination = run_directory / "run.json"
        _write_exclusive(destination, record)
    except BaseException as error:
        _record_failure_preserving_original(
            run_directory / "failure.json", attempt, phase, error
        )
        raise
    return destination
