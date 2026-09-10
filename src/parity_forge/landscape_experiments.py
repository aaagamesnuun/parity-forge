"""Fail-closed immutable runners for the preregistered landscape protocol."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from collections import Counter
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence, Tuple

from . import __version__
from .analysis import FailureCode, analyze_definition
from .asymmetry import evaluate_asymmetry
from .audit import sampled_direction
from .batch import PlayGates
from .dsl import GameDefinition, definition_hash, parse_definition
from .engine import replay_dicts
from .experiments import _git_state, _timestamp, _utc_now
from .landscape import build_landscape_manifest
from .landscape_evaluation import (
    DRAW_STRESS_DEPTH,
    DRAW_STRESS_MAX_CANDIDATES,
    DRAW_STRESS_MAX_NODES,
    DRAW_STRESS_SEEDS,
    LANDSCAPE_EXACT_MAX_STATES,
    LANDSCAPE_INSPECTION_ORDINARY_COUNT,
    LANDSCAPE_PLAY_SEEDS,
    _dimension_aggregates,
    evaluate_landscape_cases,
    stress_landscape_draws,
)
from .play import _wilson_interval
from .simplicity import evaluate_simplicity, exceeds_limits


LANDSCAPE_MANIFEST_PROTOCOL_ID = "landscape-v1-manifest-freeze"
LANDSCAPE_RAW_PROTOCOL_ID = "landscape-v1-raw-exact"
LANDSCAPE_DRAW_STRESS_PROTOCOL_ID = "landscape-v1-draw-stress"
LANDSCAPE_MANIFEST_ID = "generator-v2-3x3-landscape-v1"
LANDSCAPE_CORPUS_RELATIVE = Path("experiments/corpora/landscape-v1")
LANDSCAPE_MANIFEST_RELATIVE = LANDSCAPE_CORPUS_RELATIVE / "manifest.json"
LANDSCAPE_LOCK_RELATIVE = LANDSCAPE_CORPUS_RELATIVE / "manifest.lock.json"
LANDSCAPE_MANIFEST_ATTEMPT_RELATIVE = (
    LANDSCAPE_CORPUS_RELATIVE / "manifest-attempt.json"
)

_SOURCE_SPECS = (
    {
        "label": "generator-v1-development",
        "path": Path(
            "experiments/runs/20260830T154155824053Z-batch-g20260831/run.json"
        ),
        "run_id": "20260830T154155824053Z-batch-g20260831",
        "sha256": "b664e133cda42b494d7222735999f0d7b490d9e0108e13743cef8dd20824bb97",
        "experiment_type": "structured-random-generation-screening",
        "generator_seed": 20260831,
        "generator_version": 1,
    },
    {
        "label": "generator-v2-development",
        "path": Path(
            "experiments/runs/20260830T154309225370Z-batch-g20260831/run.json"
        ),
        "run_id": "20260830T154309225370Z-batch-g20260831",
        "sha256": "374bfc58030f0acce32a3edd7ff3d10764fb001d130eda4b1da086550b7cb0f5",
        "experiment_type": "structured-random-generation-screening",
        "generator_seed": 20260831,
        "generator_version": 2,
    },
    {
        "label": "generator-v2-heldout-20260901",
        "path": Path(
            "experiments/runs/20260830T184008717197Z-strong-g20260901/run.json"
        ),
        "run_id": "20260830T184008717197Z-strong-g20260901",
        "sha256": "cdf26f22c93a95f70e413e28257a6afddfaecf21008507a6557e019f2c5357dc",
        "experiment_type": "strong-cascade-held-out-generation",
        "generator_seed": 20260901,
        "generator_version": 2,
    },
)

_MANIFEST_BASE_KEYS = {
    "manifest_id",
    "manifest_version",
    "source_metadata",
    "provenance",
    "selection_protocol",
    "census",
    "strata",
    "cases",
}
_MANIFEST_ADDED_KEYS = {
    "protocol_id",
    "status",
    "created_at",
    "component_versions",
}
_OUTCOME_KEYS = {
    "actual_result",
    "exact",
    "failure_codes",
    "forced_result",
    "play_profiles",
    "results",
    "solve",
    "winner",
}
_FROZEN_PROTOCOL_RELATIVES = (
    Path("docs/plans/active/0006-three-by-three-outcome-landscape.md"),
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
    Path("src/parity_forge/generator.py"),
    Path("src/parity_forge/landscape.py"),
    Path("src/parity_forge/landscape_evaluation.py"),
    Path("src/parity_forge/landscape_experiments.py"),
    Path("src/parity_forge/play.py"),
    Path("src/parity_forge/simplicity.py"),
    Path("src/parity_forge/solver.py"),
    Path("src/parity_forge/symmetry.py"),
)
_FROZEN_SOURCE_RELATIVES = (
    *_FROZEN_PROTOCOL_RELATIVES,
    *_FROZEN_EXECUTABLE_RELATIVES,
)
_EXPECTED_MANIFEST_CENSUS = {
    "raw_definition_count": 36720,
    "raw_d4_orbit_count": 4776,
    "input_known_definition_count": 300,
    "input_unique_known_definition_count": 270,
    "input_relevant_known_d4_orbit_count": 77,
    "matched_known_d4_orbit_count": 55,
    "d4_orbit_count_after_known_exclusion": 4721,
    "raw_vector_count_8_d4_orbit_count": 24,
    "structurally_excluded_vector_count_8_d4_orbit_count": 19,
    "eligible_d4_orbit_count": 4702,
    "stratum_count": 96,
    "quota_per_stratum": 4,
    "minimum_eligible_d4_orbits_per_stratum": 19,
    "maximum_eligible_d4_orbits_per_stratum": 92,
    "selected_case_count": 384,
}
_MANIFEST_COMPONENT_VERSIONS = {
    "parity_forge": __version__,
    "dsl_schema": 1,
    "generator": 2,
    "d4_canonicalization": 1,
    "landscape_selection": 1,
}
_RAW_COMPONENT_VERSIONS = {
    "parity_forge": __version__,
    "dsl_schema": 1,
    "engine": 1,
    "static_evaluator": 1,
    "simplicity_evaluator": 1,
    "asymmetry_evaluator": 1,
    "play_evaluator": 1,
    "random_agent": 1,
    "goal_directed_agent": 1,
    "exact_solver": 1,
    "landscape_evaluator": 1,
}
_STRESS_COMPONENT_VERSIONS = {
    "parity_forge": __version__,
    "dsl_schema": 1,
    "engine": 1,
    "play_evaluator": 1,
    "minimax_agent": 1,
    "landscape_draw_stress": 1,
}
_PROFILE_SUMMARY_KEYS = {
    "profile",
    "agent_a",
    "agent_b",
    "samples",
    "a_wins",
    "b_wins",
    "draws",
    "a_win_rate",
    "b_win_rate",
    "draw_rate",
    "average_plies",
    "decisive_a_share",
    "decisive_a_wilson_95",
    "terminal_reasons",
    "seeds",
}
_RAW_CANDIDATE_KEYS = {
    "manifest_index",
    "case_id",
    "definition_hash",
    "d4_canonical_hash",
    "stratum",
    "vector_count",
    "definition",
    "static",
    "asymmetry",
    "simplicity",
    "simplicity_passes",
    "analysis_gate_passes",
    "cheap_profiles",
    "cheap_failure_codes",
    "exact",
    "timing",
}
_RAW_AGGREGATE_KEYS = {
    "manifest_case_count",
    "static_pass_count",
    "asymmetry_qualifies_count",
    "simplicity_pass_count",
    "analysis_gate_pass_count",
    "cheap_attempted",
    "cheap_evaluated",
    "exact_attempted",
    "exact_completed",
    "exact_censored",
    "exact_censored_hashes",
    "exact_completion_rate",
    "exact_result_histogram",
    "exact_draw_terminal_reason_histogram",
    "static_failure_histogram",
    "cheap_failure_histogram",
    "cheap_exact_direction_confusion",
    "exact_work_states_total",
    "exact_work_states_max",
    "analysis_eligible_exact_draw_count",
    "shape_clean_exact_draw_count",
    "exact_by_dimension",
    "predeclared_assessment",
}


def default_landscape_source_paths(repository: Path) -> Tuple[Path, ...]:
    return tuple(repository / spec["path"] for spec in _SOURCE_SPECS)


def _encoded_json(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _write_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    with path.open("xb") as destination:
        destination.write(_encoded_json(value))


def _read_json_bytes(path: Path, label: str) -> Tuple[bytes, Mapping[str, Any]]:
    try:
        source_bytes = path.read_bytes()
        value = json.loads(source_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("cannot read {} {}: {}".format(label, path, error)) from error
    if not isinstance(value, Mapping):
        raise ValueError("{} must contain a JSON object".format(label))
    return source_bytes, value


def _require_canonical_path(path: Path, repository: Path, relative: Path, label: str) -> None:
    expected = repository.resolve() / relative
    if path.is_symlink() or path.resolve() != expected.resolve():
        raise ValueError("{} must use canonical repository path {}".format(label, expected))


def _recorded_repository_root(value: Any, relative: Path, label: str) -> Path:
    if not isinstance(value, str):
        raise ValueError("{} must be an absolute path".format(label))
    path = Path(value)
    if (
        not path.is_absolute()
        or len(path.parts) <= len(relative.parts)
        or path.parts[-len(relative.parts) :] != relative.parts
    ):
        raise ValueError("{} does not end in {}".format(label, relative))
    return path.parents[len(relative.parts) - 1]


def _require_tracked(path: Path, repository: Path, label: str) -> None:
    try:
        relative = path.resolve().relative_to(repository.resolve())
    except ValueError as error:
        raise ValueError("{} must be inside the repository".format(label)) from error
    try:
        subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", str(relative)],
            cwd=str(repository),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError("{} must be tracked by git".format(label)) from error


def _require_clean_repository(repository: Path) -> str:
    commit, dirty = _git_state(repository)
    if commit == "UNCOMMITTED" or dirty:
        raise ValueError("preregistered landscape work requires a clean committed repository")
    return commit


def _require_timestamp(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("{} must be a UTC timestamp".format(label))
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise ValueError("{} must be a UTC timestamp".format(label)) from error
    return parsed


def _require_commit_ancestor(commit: Any, repository: Path, label: str) -> str:
    if (
        not isinstance(commit, str)
        or len(commit) != 40
        or any(character not in "0123456789abcdef" for character in commit)
    ):
        raise ValueError("{} must be a full lowercase Git commit".format(label))
    try:
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, "HEAD"],
            cwd=str(repository),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError("{} must be an ancestor of the current commit".format(label)) from error
    return commit


def _frozen_executable_fingerprints(repository: Path) -> Mapping[str, str]:
    fingerprints = {}
    for relative in _FROZEN_EXECUTABLE_RELATIVES:
        path = repository / relative
        _require_tracked(path, repository, "frozen executable {}".format(relative))
        try:
            source_bytes = path.read_bytes()
        except OSError as error:
            raise ValueError("cannot read frozen executable {}".format(relative)) from error
        fingerprints[str(relative)] = hashlib.sha256(source_bytes).hexdigest()
    return fingerprints


def _frozen_source_fingerprints_at_commit(
    repository: Path,
    commit: str,
    relatives: Sequence[Path] = _FROZEN_SOURCE_RELATIVES,
) -> Mapping[str, str]:
    fingerprints = {}
    for relative in relatives:
        try:
            source_bytes = subprocess.run(
                ["git", "show", "{}:{}".format(commit, relative)],
                cwd=str(repository),
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            ).stdout
        except (OSError, subprocess.CalledProcessError) as error:
            raise ValueError(
                "frozen source {} is missing at {}".format(relative, commit)
            ) from error
        fingerprints[str(relative)] = hashlib.sha256(source_bytes).hexdigest()
    return fingerprints


def _write_failure(
    path: Path,
    attempt: Mapping[str, Any],
    phase: str,
    error: BaseException,
) -> None:
    failure = {
        **attempt,
        "status": "FAILED",
        "phase": phase,
        "completed_at": _timestamp(_utc_now()),
        "error": {"type": type(error).__name__, "message": str(error)},
    }
    _write_exclusive(path, failure)


def _assert_no_outcome_keys(value: Any, path: str = "manifest") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in _OUTCOME_KEYS:
                raise ValueError("outcome field {}.{} is forbidden".format(path, key))
            _assert_no_outcome_keys(child, "{}.{}".format(path, key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_outcome_keys(child, "{}[{}]".format(path, index))


def _candidate_definitions(record: Mapping[str, Any], label: str) -> Tuple[GameDefinition, ...]:
    results = record.get("results")
    if not isinstance(results, Mapping):
        raise ValueError("{} source is missing results".format(label))
    candidates = results.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != 100:
        raise ValueError("{} source must contain exactly 100 candidates".format(label))
    definitions = []
    seen_hashes = set()
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            raise ValueError("{} candidate must be an object".format(label))
        mapping = candidate.get("definition")
        game_hash = candidate.get("definition_hash")
        if not isinstance(mapping, Mapping) or not isinstance(game_hash, str):
            raise ValueError("{} candidate needs definition and hash".format(label))
        definition = parse_definition(mapping)
        if definition_hash(definition) != game_hash:
            raise ValueError("{} candidate definition hash mismatch".format(label))
        if game_hash in seen_hashes:
            raise ValueError("{} candidate hashes must be unique".format(label))
        seen_hashes.add(game_hash)
        definitions.append(definition)
    return tuple(definitions)


def _load_preregistered_sources(
    source_paths: Sequence[Path], repository: Path
) -> Tuple[Tuple[GameDefinition, ...], Tuple[Mapping[str, Any], ...]]:
    if len(source_paths) != len(_SOURCE_SPECS):
        raise ValueError("landscape manifest requires exactly three source runs")
    known = []
    metadata = []
    for path, spec in zip(source_paths, _SOURCE_SPECS):
        _require_canonical_path(path, repository, spec["path"], spec["label"])
        _require_tracked(path, repository, spec["label"])
        source_bytes, record = _read_json_bytes(path, spec["label"])
        source_hash = hashlib.sha256(source_bytes).hexdigest()
        if source_hash != spec["sha256"]:
            raise ValueError("{} source SHA-256 mismatch".format(spec["label"]))
        if (
            record.get("run_id") != spec["run_id"]
            or record.get("experiment_type") != spec["experiment_type"]
            or record.get("status") != "COMPLETED"
        ):
            raise ValueError("{} source identity or status mismatch".format(spec["label"]))
        configuration = record.get("configuration")
        if not isinstance(configuration, Mapping):
            raise ValueError("{} source is missing configuration".format(spec["label"]))
        generator_configuration = (
            configuration.get("base")
            if spec["experiment_type"] == "strong-cascade-held-out-generation"
            else configuration
        )
        if not isinstance(generator_configuration, Mapping) or (
            generator_configuration.get("generator_seed") != spec["generator_seed"]
            or generator_configuration.get("generator_version") != spec["generator_version"]
            or generator_configuration.get("candidate_count") != 100
        ):
            raise ValueError("{} generator configuration mismatch".format(spec["label"]))
        definitions = _candidate_definitions(record, spec["label"])
        known.extend(definitions)
        metadata.append(
            {
                "label": spec["label"],
                "repo_relative_path": str(spec["path"]),
                "run_id": spec["run_id"],
                "sha256": source_hash,
                "definition_count": len(definitions),
            }
        )
    return tuple(known), tuple(metadata)


def _validate_manifest_lock(
    manifest_path: Path, lock_path: Path
) -> Tuple[bytes, Mapping[str, Any], Mapping[str, Any]]:
    manifest_bytes, manifest = _read_json_bytes(manifest_path, "landscape manifest")
    _, lock = _read_json_bytes(lock_path, "landscape manifest lock")
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
    if (
        lock.get("manifest_id") != LANDSCAPE_MANIFEST_ID
        or lock.get("protocol_id") != LANDSCAPE_MANIFEST_PROTOCOL_ID
        or lock.get("manifest_sha256") != manifest_hash
        or lock.get("manifest_bytes") != len(manifest_bytes)
    ):
        raise ValueError("landscape manifest lock does not match manifest bytes")
    return manifest_bytes, manifest, lock


def _validate_preregistered_manifest_shape(manifest: Mapping[str, Any]) -> None:
    census = manifest.get("census")
    strata = manifest.get("strata")
    cases = manifest.get("cases")
    if not isinstance(census, Mapping):
        raise ValueError("landscape manifest census must be an object")
    for key, expected in _EXPECTED_MANIFEST_CENSUS.items():
        if census.get(key) != expected:
            raise ValueError(
                "landscape manifest census {} differs from preregistration".format(
                    key
                )
            )
    if not isinstance(strata, list) or len(strata) != 96:
        raise ValueError("landscape manifest must contain exactly 96 strata")
    if not isinstance(cases, list) or len(cases) != 384:
        raise ValueError("landscape manifest must contain exactly 384 cases")

    selected_ids = []
    stratum_ids = set()
    eligible_counts = []
    for record in strata:
        if not isinstance(record, Mapping):
            raise ValueError("landscape stratum records must be objects")
        stratum_id = record.get("stratum_id")
        case_ids = record.get("selected_case_ids")
        eligible = record.get("eligible_d4_orbit_count")
        if (
            not isinstance(stratum_id, str)
            or stratum_id in stratum_ids
            or record.get("quota") != 4
            or not isinstance(case_ids, list)
            or len(case_ids) != 4
            or len(set(case_ids)) != 4
            or not all(isinstance(case_id, str) for case_id in case_ids)
            or not isinstance(eligible, int)
        ):
            raise ValueError("landscape stratum quota evidence is malformed")
        stratum_ids.add(stratum_id)
        selected_ids.extend(case_ids)
        eligible_counts.append(eligible)

    case_ids = [
        case.get("case_id") if isinstance(case, Mapping) else None for case in cases
    ]
    orbit_ids = [
        case.get("d4_canonical_hash") if isinstance(case, Mapping) else None
        for case in cases
    ]
    if (
        len(set(selected_ids)) != 384
        or case_ids != selected_ids
        or not all(isinstance(case_id, str) for case_id in case_ids)
        or not all(isinstance(orbit_id, str) for orbit_id in orbit_ids)
        or len(set(orbit_ids)) != 384
        or min(eligible_counts) != 19
        or max(eligible_counts) != 92
    ):
        raise ValueError("landscape manifest stratum selection differs from preregistration")


def _validate_frozen_manifest(
    manifest_path: Path,
    lock_path: Path,
    repository: Path,
) -> Tuple[bytes, Mapping[str, Any]]:
    _require_canonical_path(
        manifest_path, repository, LANDSCAPE_MANIFEST_RELATIVE, "landscape manifest"
    )
    _require_canonical_path(
        lock_path, repository, LANDSCAPE_LOCK_RELATIVE, "landscape manifest lock"
    )
    _require_tracked(manifest_path, repository, "landscape manifest")
    _require_tracked(lock_path, repository, "landscape manifest lock")
    attempt_path = repository / LANDSCAPE_MANIFEST_ATTEMPT_RELATIVE
    _require_canonical_path(
        attempt_path,
        repository,
        LANDSCAPE_MANIFEST_ATTEMPT_RELATIVE,
        "landscape manifest attempt",
    )
    _require_tracked(attempt_path, repository, "landscape manifest attempt")
    _, attempt = _read_json_bytes(attempt_path, "landscape manifest attempt")
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
    if set(attempt) != expected_attempt_keys or (
        attempt.get("run_id") != LANDSCAPE_MANIFEST_ID
        or attempt.get("protocol_id") != LANDSCAPE_MANIFEST_PROTOCOL_ID
        or attempt.get("experiment_type")
        != "outcome-blind-landscape-manifest-freeze"
        or attempt.get("status") != "STARTED"
        or attempt.get("git_dirty") is not False
        or attempt.get("component_versions") != _MANIFEST_COMPONENT_VERSIONS
    ):
        raise ValueError("landscape manifest attempt identity mismatch")
    started_at = _require_timestamp(
        attempt.get("started_at"), "landscape manifest attempt started_at"
    )
    freezer_commit = _require_commit_ancestor(
        attempt.get("git_commit"), repository, "landscape manifest freezer commit"
    )
    environment = attempt.get("environment")
    attempt_configuration = attempt.get("configuration")
    if not isinstance(attempt_configuration, Mapping):
        raise ValueError("landscape manifest attempt configuration mismatch")
    recorded_repository = _recorded_repository_root(
        attempt_configuration.get("destination"),
        LANDSCAPE_CORPUS_RELATIVE,
        "landscape manifest attempt destination",
    )
    if (
        not isinstance(environment, Mapping)
        or set(environment) != {"python", "platform"}
        or not isinstance(environment.get("python"), str)
        or not isinstance(environment.get("platform"), str)
        or set(attempt_configuration)
        != {
            "source_metadata",
            "source_paths",
            "destination",
            "source_files_contain_outcomes",
            "selection_outcome_fields_consulted",
            "outcomes_computed",
        }
        or attempt_configuration.get("source_paths")
        != [
            str(recorded_repository / spec["path"]) for spec in _SOURCE_SPECS
        ]
        or attempt_configuration.get("source_files_contain_outcomes") is not True
        or attempt_configuration.get("selection_outcome_fields_consulted") is not False
        or attempt_configuration.get("outcomes_computed") is not False
    ):
        raise ValueError("landscape manifest attempt configuration mismatch")

    manifest_bytes, manifest, lock = _validate_manifest_lock(manifest_path, lock_path)
    if set(lock) != {
        "manifest_id",
        "protocol_id",
        "manifest_sha256",
        "manifest_bytes",
        "freezer_git_commit",
    } or lock.get("freezer_git_commit") != freezer_commit:
        raise ValueError("landscape manifest lock provenance mismatch")
    if set(manifest) != _MANIFEST_BASE_KEYS | _MANIFEST_ADDED_KEYS:
        raise ValueError("landscape manifest top-level schema mismatch")
    if (
        manifest.get("manifest_id") != LANDSCAPE_MANIFEST_ID
        or manifest.get("manifest_version") != 1
        or manifest.get("protocol_id") != LANDSCAPE_MANIFEST_PROTOCOL_ID
        or manifest.get("status") != "FROZEN"
    ):
        raise ValueError("landscape manifest identity or status mismatch")
    if manifest.get("component_versions") != _MANIFEST_COMPONENT_VERSIONS:
        raise ValueError("landscape manifest component versions mismatch")
    created_at = _require_timestamp(
        manifest.get("created_at"), "landscape manifest created_at"
    )
    if created_at < started_at:
        raise ValueError("landscape manifest predates its attempt")
    _assert_no_outcome_keys(manifest)
    provenance = manifest.get("provenance")
    commit_fingerprints = _frozen_source_fingerprints_at_commit(
        repository, freezer_commit
    )
    current_executable_fingerprints = _frozen_executable_fingerprints(repository)
    recorded_executable_fingerprints = {
        str(relative): commit_fingerprints[str(relative)]
        for relative in _FROZEN_EXECUTABLE_RELATIVES
    }
    expected_provenance = {
        "freezer_git_commit": freezer_commit,
        "freezer_git_dirty": False,
        "created_at": attempt["started_at"],
        "protocol_id": LANDSCAPE_MANIFEST_PROTOCOL_ID,
        "source_files_contain_outcomes": True,
        "selection_outcome_fields_consulted": False,
        "outcomes_computed": False,
        "source_fingerprints": commit_fingerprints,
    }
    if (
        not isinstance(provenance, Mapping)
        or provenance != expected_provenance
        or current_executable_fingerprints != recorded_executable_fingerprints
        or manifest.get("component_versions") != attempt.get("component_versions")
    ):
        raise ValueError("frozen landscape source fingerprint mismatch")
    known, source_metadata = _load_preregistered_sources(
        default_landscape_source_paths(repository), repository
    )
    if (
        manifest.get("source_metadata") != list(source_metadata)
        or attempt_configuration.get("source_metadata") != list(source_metadata)
    ):
        raise ValueError("landscape manifest source metadata mismatch")
    expected = build_landscape_manifest(
        known,
        source_metadata,
        expected_provenance,
    )
    for key in _MANIFEST_BASE_KEYS:
        if manifest[key] != expected[key]:
            raise ValueError("landscape manifest field {} is not reproducible".format(key))
    _validate_preregistered_manifest_shape(manifest)
    return manifest_bytes, manifest


def _scan_prior_protocol(output_root: Path, protocol_id: str) -> None:
    reservation_path = output_root / ".{}.reservation.json".format(protocol_id)
    if reservation_path.exists():
        _, reservation = _read_json_bytes(
            reservation_path, "experiment reservation"
        )
        if reservation.get("protocol_id") != protocol_id:
            raise ValueError("experiment reservation identity mismatch")
        raise ValueError(
            "protocol {} already has evidence at {}".format(
                protocol_id, reservation_path
            )
        )
    if not output_root.exists():
        return
    for run_directory in sorted(output_root.iterdir()):
        if not run_directory.is_dir():
            continue
        for filename in ("attempt.json", "run.json", "failure.json"):
            path = run_directory / filename
            if not path.exists():
                continue
            _, record = _read_json_bytes(path, "experiment evidence")
            if record.get("protocol_id") == protocol_id:
                raise ValueError(
                    "protocol {} already has evidence at {}".format(protocol_id, path)
                )


def _reserve_protocol(
    output_root: Path,
    protocol_id: str,
    run_id: str,
    commit: str,
    started_at: str,
) -> Path:
    reservation_path = output_root / ".{}.reservation.json".format(protocol_id)
    reservation = {
        "protocol_id": protocol_id,
        "run_id": run_id,
        "status": "RESERVED",
        "reserved_at": started_at,
        "git_commit": commit,
    }
    _write_exclusive(reservation_path, reservation)
    return reservation_path


def _validate_protocol_reservation(
    output_root: Path,
    protocol_id: str,
    run_id: str,
    commit: str,
    started_at: str,
    repository: Path,
) -> None:
    reservation_path = output_root / ".{}.reservation.json".format(protocol_id)
    if reservation_path.is_symlink():
        raise ValueError("experiment reservation cannot be a symlink")
    _require_tracked(reservation_path, repository, "experiment reservation")
    _, reservation = _read_json_bytes(reservation_path, "experiment reservation")
    if reservation != {
        "protocol_id": protocol_id,
        "run_id": run_id,
        "status": "RESERVED",
        "reserved_at": started_at,
        "git_commit": commit,
    }:
        raise ValueError("experiment reservation does not match completed run")


def _validate_completed_run_attempt(
    run_path: Path,
    record: Mapping[str, Any],
    repository: Path,
    expected_components: Mapping[str, Any],
) -> Mapping[str, Any]:
    attempt_path = run_path.parent / "attempt.json"
    if attempt_path.is_symlink():
        raise ValueError("completed run attempt cannot be a symlink")
    _require_tracked(attempt_path, repository, "completed run attempt")
    if (run_path.parent / "failure.json").exists():
        raise ValueError("completed run cannot coexist with failure evidence")
    _, attempt = _read_json_bytes(attempt_path, "completed run attempt")
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
    if (
        set(attempt) != expected_attempt_keys
        or attempt.get("status") != "STARTED"
        or attempt.get("git_dirty") is not False
        or attempt.get("component_versions") != expected_components
    ):
        raise ValueError("completed run attempt identity mismatch")
    environment = attempt.get("environment")
    if (
        not isinstance(environment, Mapping)
        or set(environment) != {"python", "platform"}
        or not all(isinstance(value, str) for value in environment.values())
    ):
        raise ValueError("completed run attempt environment mismatch")
    for key in expected_attempt_keys - {"status"}:
        if record.get(key) != attempt.get(key):
            raise ValueError("completed run differs from attempt field {}".format(key))
    if record.get("status") != "COMPLETED":
        raise ValueError("completed run status mismatch")
    started_at = _require_timestamp(
        attempt.get("started_at"), "completed run attempt started_at"
    )
    completed_at = _require_timestamp(
        record.get("completed_at"), "completed run completed_at"
    )
    if completed_at < started_at:
        raise ValueError("completed run predates its attempt")
    _require_commit_ancestor(
        attempt.get("git_commit"), repository, "completed run source commit"
    )
    return attempt


def _validate_profile_summary(
    profile: Any,
    definition: GameDefinition,
    expected_profile: str,
    expected_agent: str,
) -> Mapping[str, Any]:
    if not isinstance(profile, Mapping) or set(profile) != _PROFILE_SUMMARY_KEYS:
        raise ValueError("raw cheap profile schema mismatch")
    samples = profile.get("samples")
    counts = (profile.get("a_wins"), profile.get("b_wins"), profile.get("draws"))
    if (
        profile.get("profile") != expected_profile
        or profile.get("agent_a") != expected_agent
        or profile.get("agent_b") != expected_agent
        or type(samples) is not int
        or samples != len(LANDSCAPE_PLAY_SEEDS)
        or any(type(count) is not int or count < 0 for count in counts)
        or sum(counts) != samples
        or profile.get("seeds") != list(LANDSCAPE_PLAY_SEEDS)
    ):
        raise ValueError("raw cheap profile identity or counts mismatch")
    a_wins, b_wins, draws = counts
    decisive = a_wins + b_wins
    expected_share = a_wins / decisive if decisive else None
    expected_interval = _wilson_interval(a_wins, decisive)
    average_plies = profile.get("average_plies")
    terminal_reasons = profile.get("terminal_reasons")
    if (
        profile.get("a_win_rate") != a_wins / samples
        or profile.get("b_win_rate") != b_wins / samples
        or profile.get("draw_rate") != draws / samples
        or profile.get("decisive_a_share") != expected_share
        or profile.get("decisive_a_wilson_95")
        != (list(expected_interval) if expected_interval is not None else None)
        or not isinstance(average_plies, (int, float))
        or isinstance(average_plies, bool)
        or not 0 <= average_plies <= definition.max_plies
        or not isinstance(terminal_reasons, Mapping)
        or not all(
            isinstance(reason, str)
            and type(count) is int
            and count >= 0
            for reason, count in terminal_reasons.items()
        )
        or sum(terminal_reasons.values()) != samples
    ):
        raise ValueError("raw cheap profile statistics mismatch")
    return profile


def _cheap_failure_codes_from_summaries(
    definition: GameDefinition,
    profiles: Sequence[Mapping[str, Any]],
    gates: PlayGates,
) -> Sequence[str]:
    failures = set()
    shares = []
    for profile in profiles:
        samples = profile["samples"]
        if profile["draws"] / samples > gates.max_draw_rate:
            failures.add(FailureCode.EXCESSIVE_DRAWS.value)
        if profile["average_plies"] < gates.min_average_plies:
            failures.add(FailureCode.TOO_SHORT.value)
        if (
            profile["average_plies"]
            > definition.max_plies * gates.max_average_plies_fraction
        ):
            failures.add(FailureCode.TOO_LONG.value)
        interval = profile["decisive_a_wilson_95"]
        if interval is not None:
            if interval[0] > 0.5 + gates.dominance_interval_margin:
                failures.add(FailureCode.A_DOMINANT.value)
            if interval[1] < 0.5 - gates.dominance_interval_margin:
                failures.add(FailureCode.B_DOMINANT.value)
        if profile["decisive_a_share"] is not None:
            shares.append(profile["decisive_a_share"])
    if shares and max(shares) - min(shares) >= gates.disagreement_threshold:
        failures.add(FailureCode.AGENT_DISAGREEMENT.value)
    return sorted(failures)


def _validate_exact_principal_variation(
    definition: GameDefinition, exact_result: Mapping[str, Any]
) -> None:
    try:
        terminal_state = replay_dicts(
            definition, exact_result["principal_variation"]
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(
            "raw exact principal variation is not a legal replay"
        ) from error
    expected_winner = {
        "A_WIN": "A",
        "B_WIN": "B",
        "DRAW": None,
    }.get(exact_result.get("forced_result"), "UNKNOWN")
    actual_winner = (
        terminal_state.outcome.winner.value
        if terminal_state.outcome is not None
        and terminal_state.outcome.winner is not None
        else None
    )
    if (
        expected_winner == "UNKNOWN"
        or not terminal_state.terminal
        or terminal_state.ply != exact_result.get("principal_variation_plies")
        or terminal_state.outcome is None
        or terminal_state.outcome.reason != exact_result.get("terminal_reason")
        or actual_winner != expected_winner
    ):
        raise ValueError("raw exact principal variation terminal evidence mismatch")


def freeze_landscape_manifest(
    source_paths: Sequence[Path],
    corpus_directory: Path,
    repository: Path,
) -> Path:
    """Freeze the outcome-blind manifest once, before any selected case is solved."""

    _require_canonical_path(
        corpus_directory,
        repository,
        LANDSCAPE_CORPUS_RELATIVE,
        "landscape corpus directory",
    )
    evidence_names = (
        "manifest-attempt.json",
        "manifest.json",
        "manifest.lock.json",
        "manifest-failure.json",
    )
    if any((corpus_directory / name).exists() for name in evidence_names):
        raise ValueError("landscape manifest already has attempt or result evidence")
    known, source_metadata = _load_preregistered_sources(source_paths, repository)
    commit = _require_clean_repository(repository)
    started = _utc_now()
    corpus_directory.mkdir(parents=False, exist_ok=False)
    attempt = {
        "run_id": LANDSCAPE_MANIFEST_ID,
        "protocol_id": LANDSCAPE_MANIFEST_PROTOCOL_ID,
        "experiment_type": "outcome-blind-landscape-manifest-freeze",
        "status": "STARTED",
        "started_at": _timestamp(started),
        "git_commit": commit,
        "git_dirty": False,
        "environment": {"python": sys.version, "platform": platform.platform()},
        "component_versions": _MANIFEST_COMPONENT_VERSIONS,
        "configuration": {
            "source_metadata": list(source_metadata),
            "source_paths": [str(path.resolve()) for path in source_paths],
            "destination": str(corpus_directory.resolve()),
            "source_files_contain_outcomes": True,
            "selection_outcome_fields_consulted": False,
            "outcomes_computed": False,
        },
    }
    attempt_path = corpus_directory / "manifest-attempt.json"
    _write_exclusive(attempt_path, attempt)
    try:
        manifest = build_landscape_manifest(
            known,
            source_metadata,
            {
                "freezer_git_commit": commit,
                "freezer_git_dirty": False,
                "created_at": _timestamp(started),
                "protocol_id": LANDSCAPE_MANIFEST_PROTOCOL_ID,
                "source_files_contain_outcomes": True,
                "selection_outcome_fields_consulted": False,
                "outcomes_computed": False,
                "source_fingerprints": _frozen_source_fingerprints_at_commit(
                    repository, commit
                ),
            },
        )
        manifest.update(
            {
                "protocol_id": LANDSCAPE_MANIFEST_PROTOCOL_ID,
                "status": "FROZEN",
                "created_at": _timestamp(_utc_now()),
                "component_versions": attempt["component_versions"],
            }
        )
        _assert_no_outcome_keys(manifest)
        if set(manifest) != _MANIFEST_BASE_KEYS | _MANIFEST_ADDED_KEYS:
            raise AssertionError("manifest builder produced an unexpected schema")
        _validate_preregistered_manifest_shape(manifest)
        manifest_bytes = _encoded_json(manifest)
        manifest_path = corpus_directory / "manifest.json"
        with manifest_path.open("xb") as destination:
            destination.write(manifest_bytes)
        manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
        lock = {
            "manifest_id": LANDSCAPE_MANIFEST_ID,
            "protocol_id": LANDSCAPE_MANIFEST_PROTOCOL_ID,
            "manifest_sha256": manifest_hash,
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


def run_landscape(
    manifest_path: Path,
    lock_path: Path,
    output_root: Path,
    repository: Path,
) -> Path:
    """Run the immutable raw 384-case exact landscape once."""

    if output_root.resolve() != (repository / "experiments/runs").resolve():
        raise ValueError("landscape evidence must use the repository run directory")
    manifest_bytes, manifest = _validate_frozen_manifest(
        manifest_path, lock_path, repository
    )
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
    commit = _require_clean_repository(repository)
    _scan_prior_protocol(output_root, LANDSCAPE_RAW_PROTOCOL_ID)
    started = _utc_now()
    run_id = "{}-landscape-{}".format(
        started.strftime("%Y%m%dT%H%M%S%fZ"), manifest_hash[:8]
    )
    _reserve_protocol(
        output_root,
        LANDSCAPE_RAW_PROTOCOL_ID,
        run_id,
        commit,
        _timestamp(started),
    )
    run_directory = output_root / run_id
    run_directory.mkdir(parents=False, exist_ok=False)
    component_versions = _RAW_COMPONENT_VERSIONS
    attempt = {
        "run_id": run_id,
        "protocol_id": LANDSCAPE_RAW_PROTOCOL_ID,
        "experiment_type": "frozen-3x3-exact-outcome-landscape",
        "status": "STARTED",
        "started_at": _timestamp(started),
        "git_commit": commit,
        "git_dirty": False,
        "environment": {"python": sys.version, "platform": platform.platform()},
        "component_versions": component_versions,
        "configuration": {
            "manifest_id": manifest["manifest_id"],
            "manifest_path": str(manifest_path.resolve()),
            "manifest_sha256": manifest_hash,
            "play_seeds": list(LANDSCAPE_PLAY_SEEDS),
            "play_gates": asdict(PlayGates()),
            "max_exact_states": LANDSCAPE_EXACT_MAX_STATES,
        },
    }
    _write_exclusive(run_directory / "attempt.json", attempt)
    try:
        result = evaluate_landscape_cases(manifest["cases"])
    except BaseException as error:
        _write_failure(
            run_directory / "failure.json", attempt, "LANDSCAPE_EVALUATION", error
        )
        raise
    try:
        completed = _utc_now()
        expected_executable_fingerprints = {
            str(relative): manifest["provenance"]["source_fingerprints"][
                str(relative)
            ]
            for relative in _FROZEN_EXECUTABLE_RELATIVES
        }
        if (
            _frozen_executable_fingerprints(repository)
            != expected_executable_fingerprints
        ):
            raise ValueError("frozen source changed during landscape evaluation")
        aggregate = result["aggregate"]
        exact_status = aggregate["predeclared_assessment"]["exact_completion"]["status"]
        record = {
            **attempt,
            "status": "COMPLETED",
            "completed_at": _timestamp(completed),
            "hypothesis": "The balanced, outcome-blind equal-stratum sample will reveal whether any sampled generator-v2 3x3 case is an exact draw with acceptable sampled-play shape.",
            "baseline": "Two small generator-v2 batches yielded 34 exact labels, only two ply-cap draws, and no candidate.",
            "treatment": "All 384 frozen D4-distinct cases receive budgeted exact solving; only analysis-gate cases receive frozen cheap play.",
            "expected_result": "All 384 exact attempts complete or remain explicitly censored; outcome and shape distributions are reported without estimating generator prevalence.",
            "actual_result": {**aggregate, "timing": result["timing"]},
            "interpretation": "Exact completion is {}. Outcome frequencies describe this equal-stratum sample only.".format(exact_status),
            "decision": "Commit this raw record before running the separately preregistered exact-draw stress lane.",
            "results": result,
        }
        destination = run_directory / "run.json"
        _write_exclusive(destination, record)
    except BaseException as error:
        _write_failure(
            run_directory / "failure.json", attempt, "COMPLETION_RECORD", error
        )
        raise
    return destination


def run_landscape_draw_stress(
    raw_run_path: Path,
    output_root: Path,
    repository: Path,
) -> Path:
    """Run the separate one-shot depth-5 stress lane over exact draws."""

    if output_root.resolve() != (repository / "experiments/runs").resolve():
        raise ValueError("draw-stress evidence must use the repository run directory")
    if raw_run_path.is_symlink():
        raise ValueError("raw landscape source cannot be a symlink")
    try:
        relative = raw_run_path.resolve().relative_to(output_root.resolve())
    except ValueError as error:
        raise ValueError("raw landscape source must be in the canonical run directory") from error
    if len(relative.parts) != 2 or relative.parts[1] != "run.json":
        raise ValueError("raw landscape source must be <run-id>/run.json")
    _require_tracked(raw_run_path, repository, "raw landscape source")
    raw_bytes, raw_record = _read_json_bytes(raw_run_path, "raw landscape source")
    raw_hash = hashlib.sha256(raw_bytes).hexdigest()
    if (
        raw_record.get("run_id") != relative.parts[0]
        or raw_record.get("protocol_id") != LANDSCAPE_RAW_PROTOCOL_ID
        or raw_record.get("experiment_type") != "frozen-3x3-exact-outcome-landscape"
        or raw_record.get("status") != "COMPLETED"
        or raw_record.get("git_dirty") is not False
    ):
        raise ValueError("raw landscape source identity or status mismatch")
    expected_raw_record_keys = {
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
        "completed_at",
        "hypothesis",
        "baseline",
        "treatment",
        "expected_result",
        "actual_result",
        "interpretation",
        "decision",
        "results",
    }
    if set(raw_record) != expected_raw_record_keys:
        raise ValueError("raw landscape completed record schema mismatch")
    raw_attempt = _validate_completed_run_attempt(
        raw_run_path, raw_record, repository, _RAW_COMPONENT_VERSIONS
    )
    _validate_protocol_reservation(
        output_root,
        LANDSCAPE_RAW_PROTOCOL_ID,
        raw_record["run_id"],
        raw_attempt["git_commit"],
        raw_attempt["started_at"],
        repository,
    )
    configuration = raw_record.get("configuration")
    results = raw_record.get("results")
    if not isinstance(configuration, Mapping) or not isinstance(results, Mapping):
        raise ValueError("raw landscape source is missing configuration or results")
    if set(results) != {"configuration", "aggregate", "timing", "candidates"}:
        raise ValueError("raw landscape result schema mismatch")
    candidates = results.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != 384:
        raise ValueError("raw landscape source must contain exactly 384 candidates")
    expected_play_gates = asdict(PlayGates())
    if (
        set(configuration)
        != {
            "manifest_id",
            "manifest_path",
            "manifest_sha256",
            "play_seeds",
            "play_gates",
            "max_exact_states",
        }
        or configuration.get("manifest_id") != LANDSCAPE_MANIFEST_ID
        or configuration.get("manifest_path")
        != str((repository / LANDSCAPE_MANIFEST_RELATIVE).resolve())
        or configuration.get("play_seeds") != list(LANDSCAPE_PLAY_SEEDS)
        or configuration.get("play_gates") != expected_play_gates
        or configuration.get("max_exact_states") != LANDSCAPE_EXACT_MAX_STATES
    ):
        raise ValueError("raw landscape evaluator configuration mismatch")
    result_configuration = results.get("configuration")
    if (
        not isinstance(result_configuration, Mapping)
        or set(result_configuration)
        != {
            "play_seeds",
            "play_gates",
            "max_exact_states",
            "exact_routing",
            "cheap_routing",
        }
        or result_configuration.get("play_seeds") != list(LANDSCAPE_PLAY_SEEDS)
        or result_configuration.get("play_gates") != expected_play_gates
        or result_configuration.get("max_exact_states")
        != LANDSCAPE_EXACT_MAX_STATES
    ):
        raise ValueError("raw landscape result configuration mismatch")
    manifest_path = repository / LANDSCAPE_MANIFEST_RELATIVE
    lock_path = repository / LANDSCAPE_LOCK_RELATIVE
    manifest_bytes, manifest = _validate_frozen_manifest(
        manifest_path, lock_path, repository
    )
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
    if configuration.get("manifest_sha256") != manifest_hash:
        raise ValueError("raw landscape manifest SHA-256 mismatch")
    manifest_source_fingerprints = manifest["provenance"]["source_fingerprints"]
    expected_executable_fingerprints = {
        str(relative): manifest_source_fingerprints[str(relative)]
        for relative in _FROZEN_EXECUTABLE_RELATIVES
    }
    if _frozen_source_fingerprints_at_commit(
        repository,
        raw_attempt["git_commit"],
        _FROZEN_EXECUTABLE_RELATIVES,
    ) != expected_executable_fingerprints:
        raise ValueError("raw landscape source commit changed frozen components")
    source_aggregate = results.get("aggregate")
    if (
        not isinstance(source_aggregate, Mapping)
        or set(source_aggregate) != _RAW_AGGREGATE_KEYS
        or source_aggregate.get("manifest_case_count") != 384
        or source_aggregate.get("exact_attempted") != 384
    ):
        raise ValueError("raw landscape aggregate differs from protocol")
    if len(manifest["cases"]) != len(candidates):
        raise ValueError("raw landscape candidate count differs from manifest")
    recomputed_exact_histogram: Dict[str, int] = {
        "A_WIN": 0,
        "B_WIN": 0,
        "DRAW": 0,
    }
    recomputed_exact_draw_terminal_reasons: Counter[str] = Counter()
    recomputed_static_failures: Counter[str] = Counter()
    recomputed_cheap_failures: Counter[str] = Counter()
    recomputed_direction_confusion: Dict[str, Counter[str]] = {}
    recomputed_static_passes = 0
    recomputed_asymmetry_qualifies = 0
    recomputed_simplicity_passes = 0
    recomputed_analysis_gate_passes = 0
    recomputed_analysis_draws = 0
    recomputed_shape_clean_draws = 0
    recomputed_exact_work = []
    recomputed_censored_hashes = []
    recomputed_censored = 0
    for index, (manifest_case, candidate) in enumerate(
        zip(manifest["cases"], candidates)
    ):
        if not isinstance(candidate, Mapping):
            raise ValueError("raw landscape candidate {} must be an object".format(index))
        if set(candidate) != _RAW_CANDIDATE_KEYS or candidate.get(
            "manifest_index"
        ) != index:
            raise ValueError("raw landscape candidate schema or index mismatch")
        for key in (
            "case_id",
            "definition_hash",
            "d4_canonical_hash",
            "stratum",
            "vector_count",
            "definition",
        ):
            if candidate.get(key) != manifest_case.get(key):
                raise ValueError(
                    "raw landscape candidate {} field {} differs from manifest".format(
                        index, key
                    )
                )
        definition = parse_definition(candidate["definition"])
        if definition_hash(definition) != candidate["definition_hash"]:
            raise ValueError("raw landscape candidate definition hash mismatch")
        expected_static = analyze_definition(definition).to_dict()
        expected_asymmetry = evaluate_asymmetry(definition).to_dict()
        expected_simplicity = evaluate_simplicity(definition)
        expected_simplicity_mapping = expected_simplicity.to_dict()
        expected_simplicity_passes = not exceeds_limits(expected_simplicity)
        expected_gate_passes = (
            expected_static["passes"]
            and expected_asymmetry["qualifies"]
            and expected_simplicity_passes
        )
        if (
            candidate.get("static") != expected_static
            or candidate.get("asymmetry") != expected_asymmetry
            or candidate.get("simplicity") != expected_simplicity_mapping
            or candidate.get("simplicity_passes") is not expected_simplicity_passes
            or candidate.get("analysis_gate_passes") is not expected_gate_passes
        ):
            raise ValueError("raw landscape structural evidence mismatch")
        recomputed_static_passes += expected_static["passes"]
        recomputed_asymmetry_qualifies += expected_asymmetry["qualifies"]
        recomputed_simplicity_passes += expected_simplicity_passes
        recomputed_analysis_gate_passes += expected_gate_passes
        recomputed_static_failures.update(
            diagnostic["code"] for diagnostic in expected_static["diagnostics"]
        )

        cheap_profiles = candidate.get("cheap_profiles")
        cheap_failure_codes = candidate.get("cheap_failure_codes")
        if not isinstance(cheap_profiles, list) or not isinstance(
            cheap_failure_codes, list
        ) or not all(
            isinstance(code, str) for code in cheap_failure_codes
        ) or cheap_failure_codes != sorted(set(cheap_failure_codes)):
            raise ValueError("raw landscape cheap evidence schema mismatch")
        if expected_gate_passes:
            if len(cheap_profiles) != 2:
                raise ValueError("raw landscape gate pass needs two cheap profiles")
            validated_profiles = (
                _validate_profile_summary(
                    cheap_profiles[0],
                    definition,
                    "weak-random",
                    "random-v1-weak",
                ),
                _validate_profile_summary(
                    cheap_profiles[1],
                    definition,
                    "medium-goal-directed",
                    "goal_directed-v1-medium",
                ),
            )
            expected_cheap_failures = _cheap_failure_codes_from_summaries(
                definition, validated_profiles, PlayGates()
            )
            if cheap_failure_codes != expected_cheap_failures:
                raise ValueError("raw landscape cheap failure codes mismatch")
        elif cheap_profiles or cheap_failure_codes:
            raise ValueError("raw landscape gate rejection cannot contain cheap evidence")
        recomputed_cheap_failures.update(cheap_failure_codes)

        exact = candidate.get("exact")
        if not isinstance(exact, Mapping) or set(exact) != {
            "status",
            "result",
            "budget_observation",
            "elapsed_seconds",
        }:
            raise ValueError("raw landscape candidate is missing exact evidence")
        exact_elapsed = exact.get("elapsed_seconds")
        if not isinstance(exact_elapsed, (int, float)) or isinstance(
            exact_elapsed, bool
        ) or exact_elapsed < 0:
            raise ValueError("raw landscape exact timing is malformed")
        if exact.get("status") == "COMPLETED":
            exact_result = exact.get("result")
            if (
                not isinstance(exact_result, Mapping)
                or set(exact_result)
                != {
                    "value_for_a",
                    "forced_result",
                    "principal_variation",
                    "principal_variation_plies",
                    "terminal_reason",
                    "searched_states",
                    "cache_hits",
                }
                or exact_result.get("forced_result") not in recomputed_exact_histogram
                or exact.get("budget_observation") is not None
                or type(exact_result.get("value_for_a")) is not int
                or exact_result.get("value_for_a")
                != {"A_WIN": 1, "DRAW": 0, "B_WIN": -1}[
                    exact_result.get("forced_result")
                ]
                or not isinstance(exact_result.get("principal_variation"), list)
                or type(exact_result.get("principal_variation_plies")) is not int
                or exact_result.get("principal_variation_plies")
                != len(exact_result.get("principal_variation", ()))
                or exact_result.get("terminal_reason")
                not in {"GOAL", "NO_LEGAL_ACTION", "PLY_LIMIT"}
                or (
                    exact_result.get("forced_result") == "DRAW"
                )
                != (exact_result.get("terminal_reason") == "PLY_LIMIT")
                or type(exact_result.get("searched_states")) is not int
                or not 1
                <= exact_result.get("searched_states")
                <= LANDSCAPE_EXACT_MAX_STATES
                or type(exact_result.get("cache_hits")) is not int
                or exact_result.get("cache_hits") < 0
            ):
                raise ValueError("raw completed exact evidence is malformed")
            _validate_exact_principal_variation(definition, exact_result)
            recomputed_exact_histogram[exact_result["forced_result"]] += 1
            recomputed_exact_work.append(exact_result["searched_states"])
            for profile in cheap_profiles:
                direction = sampled_direction(profile)
                counter = recomputed_direction_confusion.setdefault(
                    profile["profile"], Counter()
                )
                counter[
                    "{}->{}".format(direction, exact_result["forced_result"])
                ] += 1
            if exact_result["forced_result"] == "DRAW":
                recomputed_exact_draw_terminal_reasons[
                    exact_result["terminal_reason"]
                ] += 1
                if expected_gate_passes:
                    recomputed_analysis_draws += 1
                    if not set(cheap_failure_codes).intersection(
                        {
                            FailureCode.EXCESSIVE_DRAWS.value,
                            FailureCode.TOO_SHORT.value,
                            FailureCode.TOO_LONG.value,
                        }
                    ):
                        recomputed_shape_clean_draws += 1
        elif exact.get("status") == "CENSORED_STATE_BUDGET":
            budget = exact.get("budget_observation")
            if (
                exact.get("result") is not None
                or not isinstance(budget, Mapping)
                or set(budget) != {"searched_states", "max_states"}
                or budget.get("searched_states") != LANDSCAPE_EXACT_MAX_STATES
                or budget.get("max_states") != LANDSCAPE_EXACT_MAX_STATES
            ):
                raise ValueError("raw censored exact evidence is malformed")
            recomputed_exact_work.append(budget["searched_states"])
            recomputed_censored_hashes.append(candidate["definition_hash"])
            recomputed_censored += 1
        else:
            raise ValueError("raw landscape exact status is unknown")
        timing = candidate.get("timing")
        if not isinstance(timing, Mapping) or set(timing) != {
            "static_asymmetry_simplicity_seconds",
            "cheap_play_seconds",
        } or any(
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or value < 0
            for value in timing.values()
        ):
            raise ValueError("raw landscape candidate timing is malformed")

    result_timing = results.get("timing")
    actual_result = raw_record.get("actual_result")
    if (
        not isinstance(result_timing, Mapping)
        or set(result_timing)
        != {
            "static_asymmetry_simplicity_seconds",
            "cheap_play_seconds",
            "exact_seconds",
            "total_seconds",
        }
        or any(
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or value < 0
            for value in result_timing.values()
        )
        or not isinstance(actual_result, Mapping)
        or actual_result != {**source_aggregate, "timing": result_timing}
    ):
        raise ValueError("raw landscape completed summary mismatch")
    expected_direction_confusion = {
        profile: dict(sorted(counter.items()))
        for profile, counter in sorted(recomputed_direction_confusion.items())
    }
    expected_exact_assessment = {
        "exact_completion": {
            "status": "SUPPORTED" if recomputed_censored == 0 else "INCONCLUSIVE",
            "reasons": (
                []
                if recomputed_censored == 0
                else ["EXACT_STATE_BUDGET_CENSORING"]
            ),
        }
    }
    if (
        source_aggregate.get("exact_censored") != recomputed_censored
        or source_aggregate.get("exact_censored_hashes")
        != sorted(recomputed_censored_hashes)
        or source_aggregate.get("exact_completed")
        != len(candidates) - recomputed_censored
        or source_aggregate.get("exact_completion_rate")
        != (len(candidates) - recomputed_censored) / len(candidates)
        or source_aggregate.get("exact_result_histogram")
        != recomputed_exact_histogram
        or source_aggregate.get("exact_draw_terminal_reason_histogram")
        != dict(sorted(recomputed_exact_draw_terminal_reasons.items()))
        or source_aggregate.get("static_pass_count") != recomputed_static_passes
        or source_aggregate.get("asymmetry_qualifies_count")
        != recomputed_asymmetry_qualifies
        or source_aggregate.get("simplicity_pass_count")
        != recomputed_simplicity_passes
        or source_aggregate.get("analysis_gate_pass_count")
        != recomputed_analysis_gate_passes
        or source_aggregate.get("cheap_attempted")
        != recomputed_analysis_gate_passes
        or source_aggregate.get("cheap_evaluated")
        != recomputed_analysis_gate_passes
        or source_aggregate.get("static_failure_histogram")
        != dict(sorted(recomputed_static_failures.items()))
        or source_aggregate.get("cheap_failure_histogram")
        != dict(sorted(recomputed_cheap_failures.items()))
        or source_aggregate.get("cheap_exact_direction_confusion")
        != expected_direction_confusion
        or source_aggregate.get("analysis_eligible_exact_draw_count")
        != recomputed_analysis_draws
        or source_aggregate.get("shape_clean_exact_draw_count")
        != recomputed_shape_clean_draws
        or source_aggregate.get("exact_work_states_total")
        != sum(recomputed_exact_work)
        or source_aggregate.get("exact_work_states_max")
        != max(recomputed_exact_work, default=0)
        or source_aggregate.get("exact_by_dimension")
        != _dimension_aggregates(candidates)
        or source_aggregate.get("predeclared_assessment")
        != expected_exact_assessment
    ):
        raise ValueError("raw landscape aggregate does not match candidate evidence")

    commit = _require_clean_repository(repository)
    _scan_prior_protocol(output_root, LANDSCAPE_DRAW_STRESS_PROTOCOL_ID)
    started = _utc_now()
    run_id = "{}-draw-stress-{}".format(
        started.strftime("%Y%m%dT%H%M%S%fZ"), raw_hash[:8]
    )
    _reserve_protocol(
        output_root,
        LANDSCAPE_DRAW_STRESS_PROTOCOL_ID,
        run_id,
        commit,
        _timestamp(started),
    )
    run_directory = output_root / run_id
    run_directory.mkdir(parents=False, exist_ok=False)
    component_versions = _STRESS_COMPONENT_VERSIONS
    attempt = {
        "run_id": run_id,
        "protocol_id": LANDSCAPE_DRAW_STRESS_PROTOCOL_ID,
        "experiment_type": "exact-draw-depth5-landscape-stress",
        "status": "STARTED",
        "started_at": _timestamp(started),
        "git_commit": commit,
        "git_dirty": False,
        "environment": {"python": sys.version, "platform": platform.platform()},
        "component_versions": component_versions,
        "configuration": {
            "source_raw_run_id": raw_record["run_id"],
            "source_raw_run_path": str(raw_run_path.resolve()),
            "source_raw_run_sha256": raw_hash,
            "manifest_sha256": manifest_hash,
            "depth": DRAW_STRESS_DEPTH,
            "seeds": list(DRAW_STRESS_SEEDS),
            "max_nodes_per_candidate": DRAW_STRESS_MAX_NODES,
            "max_candidates": DRAW_STRESS_MAX_CANDIDATES,
            "play_gates": asdict(PlayGates()),
            "inspection_ordinary_count": LANDSCAPE_INSPECTION_ORDINARY_COUNT,
        },
    }
    _write_exclusive(run_directory / "attempt.json", attempt)
    try:
        result = stress_landscape_draws(candidates)
    except BaseException as error:
        _write_failure(
            run_directory / "failure.json", attempt, "DRAW_STRESS_EVALUATION", error
        )
        raise
    try:
        if (
            _frozen_executable_fingerprints(repository)
            != expected_executable_fingerprints
        ):
            raise ValueError("frozen source changed during draw stress")
        result_configuration = result.get("configuration")
        if (
            not isinstance(result_configuration, Mapping)
            or result_configuration.get("depth") != DRAW_STRESS_DEPTH
            or result_configuration.get("seeds") != list(DRAW_STRESS_SEEDS)
            or result_configuration.get("max_nodes_per_candidate")
            != DRAW_STRESS_MAX_NODES
            or result_configuration.get("max_candidates")
            != DRAW_STRESS_MAX_CANDIDATES
            or result_configuration.get("play_gates") != asdict(PlayGates())
        ):
            raise ValueError("draw-stress result configuration mismatch")
        inspection_selection = result.get("inspection_selection")
        if (
            not isinstance(inspection_selection, Mapping)
            or inspection_selection.get("configuration", {}).get("ordinary_count")
            != LANDSCAPE_INSPECTION_ORDINARY_COUNT
        ):
            raise ValueError("draw-stress inspection selection mismatch")
        aggregate = result["aggregate"]
        assessment = aggregate["predeclared_assessment"]["draw_stress"]["status"]
        record = {
            **attempt,
            "status": "COMPLETED",
            "completed_at": _timestamp(_utc_now()),
            "hypothesis": "Depth-5 will leave exact draws non-decisive while exposing whether any shape-clean draw survives the strong profile.",
            "baseline": "Depth-5 matched 34 known forced directions but saw only two development exact draws and no held-out draws.",
            "treatment": "At most 32 exact draws, shape-clean first, receive depth-5 self-play under one cumulative node cap each.",
            "expected_result": "Any exact draw called decisive fails the evaluator; otherwise at least 15 uncensored completions are required for support.",
            "actual_result": {**aggregate, "timing": result["timing"]},
            "interpretation": "The predeclared draw-stress assessment is {}.".format(assessment),
            "decision": aggregate["next_branch"],
            "results": result,
        }
        destination = run_directory / "run.json"
        _write_exclusive(destination, record)
    except BaseException as error:
        _write_failure(
            run_directory / "failure.json", attempt, "COMPLETION_RECORD", error
        )
        raise
    return destination
