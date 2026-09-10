"""Immutable, local experiment runners."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence, Tuple

from . import __version__
from .analysis import analyze_mapping
from .agents import Agent
from .audit import exact_audit
from .batch import BatchConfig, PlayGates, screen_batch
from .calibration import calibrate_minimax
from .cascade import AdmissionPolicy, StrongCascadeConfig, screen_strong_batch
from .dsl import GameDefinition, Player, definition_hash
from .heldout_audit import blind_depth5_audit
from .play import evaluate_matchup, profile_disagreement
from .solver import solve_game
from .simplicity import DEFAULT_LIMITS


HELDOUT_PROTOCOL_ID = "cascade-v2-heldout-seed-20260901"
HELDOUT_BLIND_PROTOCOL_ID = "cascade-v2-heldout-blind-depth5"
HELDOUT_DEVELOPMENT_RUN_ID = "20260830T154309225370Z-batch-g20260831"
HELDOUT_DEVELOPMENT_SHA256 = (
    "374bfc58030f0acce32a3edd7ff3d10764fb001d130eda4b1da086550b7cb0f5"
)
HELDOUT_DEVELOPMENT_DEFINITIONS_SHA256 = (
    "a05c37f6d78ccdfc9fb0d3a50dfa88ea5ec50d0dba1557181e11df9fefb82909"
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _git_state(repository: Path) -> Tuple[str, bool]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repository),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        commit = "UNCOMMITTED"
    try:
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(repository),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        ).stdout
        dirty = bool(status.strip())
    except (OSError, subprocess.CalledProcessError):
        dirty = True
    return commit, dirty


def _write_failed_record(
    run_directory: Path,
    attempt: Mapping[str, Any],
    error: BaseException,
) -> None:
    failed = {
        **attempt,
        "status": "FAILED",
        "completed_at": _timestamp(_utc_now()),
        "error": {"type": type(error).__name__, "message": str(error)},
    }
    (run_directory / "failure.json").write_text(
        json.dumps(failed, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def check_static_corpus(corpus: Mapping[str, Any]) -> Dict[str, Any]:
    cases = corpus.get("cases")
    if not isinstance(cases, list):
        raise ValueError("corpus.cases must be an array")
    results = []
    histogram: Counter[str] = Counter()
    for case in cases:
        if not isinstance(case, Mapping):
            raise ValueError("each corpus case must be an object")
        case_id = case.get("id")
        expected = case.get("expected_failures")
        definition = case.get("definition")
        if not isinstance(case_id, str) or not isinstance(expected, list) or not isinstance(definition, Mapping):
            raise ValueError("each corpus case needs id, expected_failures, and definition")
        report = analyze_mapping(definition)
        actual = [code.value for code in report.failure_codes]
        histogram.update(actual)
        results.append(
            {
                "case_id": case_id,
                "expected_failures": sorted(expected),
                "actual_failures": sorted(actual),
                "matches_expectation": set(expected) == set(actual),
                "definition_hash": report.definition_hash,
            }
        )
    matches = sum(result["matches_expectation"] for result in results)
    return {
        "corpus_id": corpus.get("corpus_id"),
        "cases": results,
        "aggregate": {
            "case_count": len(results),
            "matching_cases": matches,
            "mismatching_cases": len(results) - matches,
            "failure_histogram": dict(sorted(histogram.items())),
        },
    }


def run_static_corpus(
    corpus_path: Path,
    output_root: Path,
    repository: Path,
) -> Path:
    """Evaluate a frozen corpus and create one never-overwritten run directory."""

    started = _utc_now()
    corpus_bytes = corpus_path.read_bytes()
    corpus_hash = hashlib.sha256(corpus_bytes).hexdigest()
    corpus = json.loads(corpus_bytes.decode("utf-8"))
    if corpus.get("frozen") is not True:
        raise ValueError("significant corpus runs require a corpus marked frozen")
    results = check_static_corpus(corpus)
    completed = _utc_now()
    short_hash = corpus_hash[:8]
    run_id = "{}-static-{}".format(started.strftime("%Y%m%dT%H%M%S%fZ"), short_hash)
    run_directory = output_root / run_id
    run_directory.mkdir(parents=True, exist_ok=False)
    commit, dirty = _git_state(repository)
    record = {
        "run_id": run_id,
        "experiment_type": "frozen-static-corpus",
        "status": "COMPLETED",
        "started_at": _timestamp(started),
        "completed_at": _timestamp(completed),
        "git_commit": commit,
        "git_dirty": dirty,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
        },
        "component_versions": {
            "parity_forge": __version__,
            "dsl_schema": 1,
            "static_evaluator": 1,
            "simplicity_evaluator": 1,
        },
        "configuration": {
            "corpus_path": str(corpus_path.resolve()),
            "corpus_sha256": corpus_hash,
            "complexity_limits": {
                "max_piece_types": DEFAULT_LIMITS.max_piece_types,
                "max_numeric_parameters": DEFAULT_LIMITS.max_numeric_parameters,
                "max_independent_statements": DEFAULT_LIMITS.max_independent_statements,
                "max_initial_legal_actions": DEFAULT_LIMITS.max_initial_legal_actions,
            },
            "seeds": [],
        },
        "hypothesis": "The v1 static evaluator reproduces all predeclared frozen-corpus classifications.",
        "baseline": "Expected labels authored before the first evaluator run.",
        "treatment": "DSL parser, static evaluator v1, and simplicity evaluator v1.",
        "expected_result": "Every case exactly matches its expected failure-code set.",
        "actual_result": results["aggregate"],
        "interpretation": (
            "The evaluator satisfies the initial frozen static contract."
            if results["aggregate"]["mismatching_cases"] == 0
            else "At least one evaluator behavior disagrees with the frozen contract."
        ),
        "decision": (
            "Proceed to play-based evaluation while preserving this baseline."
            if results["aggregate"]["mismatching_cases"] == 0
            else "Do not proceed until mismatches are diagnosed without rewriting evidence."
        ),
        "results": results,
    }
    destination = run_directory / "run.json"
    destination.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def run_play_evaluation(
    definition: GameDefinition,
    profiles: Sequence[Tuple[str, Mapping[Player, Agent]]],
    seeds: Sequence[int],
    output_root: Path,
    repository: Path,
    source: Mapping[str, Any],
) -> Path:
    """Run frozen-definition matchups and preserve game-level traces."""

    if not profiles:
        raise ValueError("at least one agent profile is required")
    started = _utc_now()
    results = [
        evaluate_matchup(definition, label, agents, seeds)
        for label, agents in profiles
    ]
    completed = _utc_now()
    game_hash = definition_hash(definition)
    run_id = "{}-play-{}".format(started.strftime("%Y%m%dT%H%M%S%fZ"), game_hash[:8])
    run_directory = output_root / run_id
    run_directory.mkdir(parents=True, exist_ok=False)
    commit, dirty = _git_state(repository)
    aggregate = [result.to_dict(include_records=False) for result in results]
    disagreement = profile_disagreement(results)
    record = {
        "run_id": run_id,
        "experiment_type": "frozen-definition-agent-comparison",
        "status": "COMPLETED",
        "started_at": _timestamp(started),
        "completed_at": _timestamp(completed),
        "git_commit": commit,
        "git_dirty": dirty,
        "environment": {"python": sys.version, "platform": platform.platform()},
        "component_versions": {
            "parity_forge": __version__,
            "dsl_schema": 1,
            "engine": 1,
            "play_evaluator": 1,
        },
        "configuration": {
            "definition_hash": game_hash,
            "definition": definition.to_dict(),
            "source": dict(source),
            "seeds": list(seeds),
            "profiles": [
                {
                    "label": label,
                    "agent_a": agents[Player.A].identity.key,
                    "agent_b": agents[Player.B].identity.key,
                }
                for label, agents in profiles
            ],
        },
        "hypothesis": "Role outcomes will change materially between random and one-ply goal-directed play if static survival hides strength-sensitive advantage.",
        "baseline": "Random-v1 self-play on a frozen static survivor.",
        "treatment": "Goal-directed-v1 self-play with the same definition and seed list.",
        "expected_result": "Repetition is exact; wins, draws, uncertainty, and lengths remain separate; a >=0.15 decisive-share shift is flagged.",
        "actual_result": {
            "profiles": aggregate,
            "agent_disagreement": disagreement,
        },
        "interpretation": (
            "Agent profiles materially disagree; apparent balance is strength-sensitive."
            if disagreement
            else "No material point-estimate disagreement was observed at these two cheap profiles."
        ),
        "decision": (
            "Treat the candidate as evaluator-sensitive and add stronger/alternative policies before qualification."
            if disagreement
            else "Preserve the candidate for stronger evaluation without claiming fairness."
        ),
        "results": [result.to_dict(include_records=True) for result in results],
    }
    destination = run_directory / "run.json"
    destination.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def run_exact_solve(
    definition: GameDefinition,
    output_root: Path,
    repository: Path,
    source: Mapping[str, Any],
) -> Path:
    """Solve one frozen definition and preserve the proof-search result."""

    started = _utc_now()
    result = solve_game(definition)
    completed = _utc_now()
    game_hash = definition_hash(definition)
    run_id = "{}-solve-{}".format(started.strftime("%Y%m%dT%H%M%S%fZ"), game_hash[:8])
    run_directory = output_root / run_id
    run_directory.mkdir(parents=True, exist_ok=False)
    commit, dirty = _git_state(repository)
    record = {
        "run_id": run_id,
        "experiment_type": "exact-finite-game-solve",
        "status": "COMPLETED",
        "started_at": _timestamp(started),
        "completed_at": _timestamp(completed),
        "git_commit": commit,
        "git_dirty": dirty,
        "environment": {"python": sys.version, "platform": platform.platform()},
        "component_versions": {
            "parity_forge": __version__,
            "dsl_schema": 1,
            "engine": 1,
            "exact_solver": 1,
        },
        "configuration": {
            "definition_hash": game_hash,
            "definition": definition.to_dict(),
            "source": dict(source),
            "seeds": [],
            "algorithm": "full-width memoized minimax to terminal state",
        },
        "hypothesis": "Exact optimal play will resolve whether the agent-profile reversal hides a forced role result.",
        "baseline": "Random and goal-directed profiles materially disagreed on the frozen definition.",
        "treatment": "Exhaustive finite-horizon minimax using only engine transitions.",
        "expected_result": "A proven forced A win, B win, or draw from the initial state.",
        "actual_result": result.to_dict(),
        "interpretation": "The reported result is exact for DSL v1 semantics and this definition, not an estimate from sampled play.",
        "decision": (
            "Reject this candidate as a forced role win and retain it as an agent-sensitivity benchmark."
            if result.forced_result != "DRAW"
            else "Retain for richer strategic diagnostics; a forced draw is not by itself a good game."
        ),
    }
    destination = run_directory / "run.json"
    destination.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def run_generation_batch(
    config: BatchConfig,
    output_root: Path,
    repository: Path,
) -> Path:
    """Generate, screen, and preserve one candidate batch."""

    started = _utc_now()
    result = screen_batch(config)
    completed = _utc_now()
    run_id = "{}-batch-g{}".format(
        started.strftime("%Y%m%dT%H%M%S%fZ"), config.generator_seed
    )
    run_directory = output_root / run_id
    run_directory.mkdir(parents=True, exist_ok=False)
    commit, dirty = _git_state(repository)
    aggregate = result["aggregate"]
    record = {
        "run_id": run_id,
        "experiment_type": "structured-random-generation-screening",
        "status": "COMPLETED",
        "started_at": _timestamp(started),
        "completed_at": _timestamp(completed),
        "git_commit": commit,
        "git_dirty": dirty,
        "environment": {"python": sys.version, "platform": platform.platform()},
        "component_versions": {
            "parity_forge": __version__,
            "dsl_schema": 1,
            "engine": 1,
            "generator": config.generator_version,
            "static_evaluator": 1,
            "simplicity_evaluator": 1,
            "asymmetry_evaluator": 1,
            "play_evaluator": 1,
            "random_agent": 1,
            "goal_directed_agent": 1,
        },
        "configuration": result["configuration"],
        "hypothesis": "Structured v1 variation will yield an auditable mixture of cheap failures and a small provisional frontier.",
        "baseline": "No generated batch; one hand-authored static survivor was an exact forced A win.",
        "treatment": "Generator-v1 definitions screened by the frozen lexicographic cascade.",
        "expected_result": "Every generated definition is unique and reproducible; static rejects avoid play compute; survivors are few and inspectable.",
        "actual_result": aggregate,
        "interpretation": "{} of {} definitions reached sampled play; {} survived provisional gates.".format(
            aggregate["play_evaluated"],
            aggregate["generated_unique"],
            aggregate["provisional_survivors"],
        ),
        "decision": "Inspect the frontier and evaluator disagreements before changing the generator or evaluator.",
        "results": result,
    }
    destination = run_directory / "run.json"
    destination.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def run_strong_generation_batch(
    config: StrongCascadeConfig,
    output_root: Path,
    repository: Path,
    development_source: Mapping[str, Any],
) -> Path:
    """Run the one-shot preregistered strong cascade with attempt evidence."""

    expected_configuration = {
        "generator_seed": 20260901,
        "candidate_count": 100,
        "play_seeds": tuple(range(30)),
        "generator_version": 2,
        "strong_seeds": tuple(range(30)),
        "minimax_depth": 5,
        "max_depth5_board_size": 4,
        "max_depth5_candidates": 100,
        "max_nodes_per_candidate": 5000000,
        "exact_max_board_size": 3,
        "max_exact_candidates": 100,
        "max_exact_states": 100000,
    }
    actual_configuration = {
        "generator_seed": config.base.generator_seed,
        "candidate_count": config.base.candidate_count,
        "play_seeds": config.base.play_seeds,
        "generator_version": config.base.generator_version,
        "strong_seeds": config.strong_seeds,
        "minimax_depth": config.minimax_depth,
        "max_depth5_board_size": config.max_depth5_board_size,
        "max_depth5_candidates": config.max_depth5_candidates,
        "max_nodes_per_candidate": config.max_nodes_per_candidate,
        "exact_max_board_size": config.exact_max_board_size,
        "max_exact_candidates": config.max_exact_candidates,
        "max_exact_states": config.max_exact_states,
    }
    mismatched = sorted(
        key
        for key, expected in expected_configuration.items()
        if actual_configuration[key] != expected
    )
    if mismatched:
        raise ValueError(
            "held-out configuration differs from preregistration: {}".format(
                ", ".join(mismatched)
            )
        )
    if config.base.gates != PlayGates():
        raise ValueError("held-out play gates differ from preregistration")
    if config.admission != AdmissionPolicy():
        raise ValueError("held-out admission policy differs from preregistration")
    development_fingerprint = hashlib.sha256(
        "\n".join(sorted(config.development_definition_hashes)).encode("ascii")
    ).hexdigest()
    if (
        len(set(config.development_definition_hashes)) != 100
        or development_fingerprint != HELDOUT_DEVELOPMENT_DEFINITIONS_SHA256
    ):
        raise ValueError("held-out development definition set does not match preregistration")
    if (
        development_source.get("run_id") != HELDOUT_DEVELOPMENT_RUN_ID
        or development_source.get("sha256") != HELDOUT_DEVELOPMENT_SHA256
    ):
        raise ValueError("held-out development source does not match preregistration")
    source_path_value = development_source.get("path")
    if not isinstance(source_path_value, str):
        raise ValueError("held-out development source needs its exact path")
    source_bytes = Path(source_path_value).read_bytes()
    source_record = json.loads(source_bytes.decode("utf-8"))
    if (
        hashlib.sha256(source_bytes).hexdigest() != HELDOUT_DEVELOPMENT_SHA256
        or source_record.get("run_id") != HELDOUT_DEVELOPMENT_RUN_ID
    ):
        raise ValueError("held-out development source file does not match preregistration")
    if output_root.resolve() != repository.resolve() / "experiments" / "runs":
        raise ValueError("held-out evidence must use the repository experiment-run directory")

    for evidence_path in tuple(output_root.glob("*/attempt.json")) + tuple(
        output_root.glob("*/run.json")
    ):
        try:
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        prior_protocol = evidence.get("protocol_id") == HELDOUT_PROTOCOL_ID
        prior_legacy_run = (
            evidence.get("experiment_type")
            == "strong-cascade-held-out-generation"
            and evidence.get("configuration", {})
            .get("base", {})
            .get("generator_seed")
            == 20260901
        )
        if prior_protocol or prior_legacy_run:
            raise ValueError(
                "held-out seed 20260901 already has attempt evidence at {}".format(
                    evidence_path
                )
            )

    commit, dirty = _git_state(repository)
    if commit == "UNCOMMITTED" or dirty:
        raise ValueError("held-out run requires a clean committed repository")

    started = _utc_now()
    run_id = "{}-strong-g{}".format(
        started.strftime("%Y%m%dT%H%M%S%fZ"), config.base.generator_seed
    )
    run_directory = output_root / run_id
    run_directory.mkdir(parents=True, exist_ok=False)
    component_versions = {
        "parity_forge": __version__,
        "dsl_schema": 1,
        "engine": 1,
        "generator": config.base.generator_version,
        "static_evaluator": 1,
        "simplicity_evaluator": 1,
        "asymmetry_evaluator": 1,
        "play_evaluator": 1,
        "random_agent": 1,
        "goal_directed_agent": 1,
        "minimax_agent": 1,
        "exact_solver": 1,
        "strong_cascade": 2,
    }
    attempt = {
        "run_id": run_id,
        "protocol_id": HELDOUT_PROTOCOL_ID,
        "experiment_type": "strong-cascade-held-out-generation",
        "status": "STARTED",
        "started_at": _timestamp(started),
        "git_commit": commit,
        "git_dirty": dirty,
        "environment": {"python": sys.version, "platform": platform.platform()},
        "component_versions": component_versions,
        "configuration": {
            "strong_cascade": asdict(config),
            "development_source": dict(development_source),
        },
    }
    (run_directory / "attempt.json").write_text(
        json.dumps(attempt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    try:
        result = screen_strong_batch(config)
    except BaseException as error:
        _write_failed_record(run_directory, attempt, error)
        raise
    try:
        completed = _utc_now()
        aggregate = result["aggregate"]
        record = {
            "run_id": run_id,
            "protocol_id": HELDOUT_PROTOCOL_ID,
            "experiment_type": "strong-cascade-held-out-generation",
            "status": "COMPLETED",
            "started_at": _timestamp(started),
            "completed_at": _timestamp(completed),
            "git_commit": commit,
            "git_dirty": dirty,
            "environment": {"python": sys.version, "platform": platform.platform()},
            "component_versions": component_versions,
            "configuration": {
                **result["configuration"],
                "development_source": dict(development_source),
            },
            "hypothesis": "The predeclared uncertainty admission rule will retain plausible fair cases while concentrating depth-5 and exact compute on a minority of a held-out generator-v2 batch.",
            "baseline": "Generator-v2 seed 20260831: 57 cheap-play cases, 25 policy admissions, 2/2 exact draws retained, and only 1/18 forced wins admitted.",
            "treatment": "Cascade-v2 on an unseen generator seed: all cheap-play 3x3 cases route directly to exact solving; admitted boards above 3 through size {} and exact draws receive depth-5; larger boards are budget-deferred.".format(config.max_depth5_board_size),
            "expected_result": "Admission is at most 50%; at least 90% of selected depth-5 attempts complete; every eligible 3x3 exact solve completes; at least two exact draws occur and all were admitted.",
            "actual_result": {**aggregate, "timing": result["timing"]},
            "interpretation": "{} of {} cheap-play cases met the admission rule; {} unique cases entered admission or exact-audit lanes, {} were evaluated at depth 5, {} exactly, and {} survived strong gates. The predeclared primary assessment is {}.".format(
                aggregate["late_stage_admitted"],
                aggregate["novel_cheap_play_evaluated"],
                aggregate["late_stage_routed"],
                aggregate["depth5_evaluated"],
                aggregate["exact_evaluated"],
                aggregate["strong_survivors"],
                aggregate["predeclared_assessment"]["overall"],
            ),
            "decision": "Inspect every strong survivor and budget deferral before changing the generator, admission policy, or evaluator.",
            "results": result,
        }
        destination = run_directory / "run.json"
        destination.write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    except BaseException as error:
        _write_failed_record(run_directory, attempt, error)
        raise
    return destination


def run_blind_heldout_audit(
    strong_run_path: Path,
    seeds: Sequence[int],
    depth: int,
    max_nodes_per_candidate: int,
    output_root: Path,
    repository: Path,
    preregistered: bool = False,
) -> Path:
    """Blindly evaluate every exact-completed 3x3 case from a strong run."""

    strong_bytes = strong_run_path.read_bytes()
    strong_hash = hashlib.sha256(strong_bytes).hexdigest()
    strong_record = json.loads(strong_bytes.decode("utf-8"))
    if strong_record.get("experiment_type") != "strong-cascade-held-out-generation":
        raise ValueError("source must be a strong-cascade held-out run")
    if strong_record.get("status") != "COMPLETED":
        raise ValueError("source strong-cascade run must be complete")
    if preregistered:
        source_configuration = strong_record.get("configuration", {})
        source_base = source_configuration.get("base", {})
        if (
            strong_record.get("protocol_id") != HELDOUT_PROTOCOL_ID
            or strong_record.get("git_dirty") is not False
            or source_configuration.get("cascade_version") != 2
            or source_base.get("generator_seed") != 20260901
            or source_base.get("candidate_count") != 100
            or source_configuration.get("strong_seeds") != list(range(30))
            or source_configuration.get("max_nodes_per_candidate") != 5000000
            or source_configuration.get("max_exact_states") != 100000
            or tuple(seeds) != tuple(range(30))
            or depth != 5
            or max_nodes_per_candidate != 5000000
        ):
            raise ValueError("blind audit differs from its preregistered protocol")
        if output_root.resolve() != repository.resolve() / "experiments" / "runs":
            raise ValueError("blind held-out evidence must use the repository run directory")
        if strong_run_path.resolve().parent.parent != output_root.resolve():
            raise ValueError("blind audit source must be a canonical repository run")
        for evidence_path in tuple(output_root.glob("*/attempt.json")) + tuple(
            output_root.glob("*/run.json")
        ):
            try:
                evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if evidence.get("protocol_id") == HELDOUT_BLIND_PROTOCOL_ID:
                raise ValueError(
                    "blind held-out audit already has attempt evidence at {}".format(
                        evidence_path
                    )
                )

    commit, dirty = _git_state(repository)
    if preregistered and (commit == "UNCOMMITTED" or dirty):
        raise ValueError("blind held-out audit requires a clean committed repository")
    started = _utc_now()
    run_id = "{}-blind-depth5-{}".format(
        started.strftime("%Y%m%dT%H%M%S%fZ"), strong_hash[:8]
    )
    run_directory = output_root / run_id
    run_directory.mkdir(parents=True, exist_ok=False)
    protocol_id = (
        HELDOUT_BLIND_PROTOCOL_ID
        if preregistered
        else "unregistered-blind-depth5"
    )
    component_versions = {
        "parity_forge": __version__,
        "dsl_schema": 1,
        "engine": 1,
        "play_evaluator": 1,
        "minimax_agent": 1,
        "blind_audit": 1,
    }
    attempt = {
        "run_id": run_id,
        "protocol_id": protocol_id,
        "experiment_type": "blind-depth5-audit-of-strong-heldout",
        "status": "STARTED",
        "started_at": _timestamp(started),
        "git_commit": commit,
        "git_dirty": dirty,
        "environment": {"python": sys.version, "platform": platform.platform()},
        "component_versions": component_versions,
        "configuration": {
            "source_strong_run_id": strong_record["run_id"],
            "source_strong_run_path": str(strong_run_path.resolve()),
            "source_strong_run_sha256": strong_hash,
            "depth": depth,
            "seeds": list(seeds),
            "max_nodes_per_candidate": max_nodes_per_candidate,
        },
    }
    (run_directory / "attempt.json").write_text(
        json.dumps(attempt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    try:
        result = blind_depth5_audit(
            strong_record["results"]["candidates"],
            seeds,
            max_nodes_per_candidate,
            depth=depth,
        )
    except BaseException as error:
        _write_failed_record(run_directory, attempt, error)
        raise
    try:
        completed = _utc_now()
        aggregate = result["aggregate"]
        observed_draw_failure = (
            aggregate["exact_draw_decisive_misclassifications"] > 0
        )
        inconclusive = (
            aggregate["deferred_count"] > 0 or aggregate["evaluated_count"] < 15
        )
        supported = (
            not inconclusive
            and aggregate["direction_accuracy"] is not None
            and aggregate["direction_accuracy"] >= 0.90
            and not observed_draw_failure
        )
        predeclared_outcome = (
            "NOT_SUPPORTED"
            if observed_draw_failure
            else "INCONCLUSIVE" if inconclusive
            else "SUPPORTED" if supported else "NOT_SUPPORTED"
        )
        actual_result = {**aggregate, "predeclared_outcome": predeclared_outcome}
        if observed_draw_failure:
            interpretation = (
                "Depth-5 called at least one completed exact draw decisive, which is "
                "a predeclared evaluator failure even if other cases were censored."
            )
            decision = (
                "Do not trust minimax-v1-depth5 as the strong direction evaluator; "
                "diagnose the preserved exact-draw error before changing the policy."
            )
        elif inconclusive:
            interpretation = (
                "The blind audit is inconclusive because fewer than 15 exact cases "
                "completed or at least one case exhausted its node budget."
            )
            decision = (
                "Do not promote or reject depth-5 accuracy from this audit; preserve "
                "the result and design a new preregistered evaluation."
            )
        elif supported:
            interpretation = (
                "Depth-5 met the predeclared held-out direction threshold without "
                "calling an exact draw decisive."
            )
            decision = (
                "Retain minimax-v1-depth5 as a late diagnostic while preserving "
                "exact audits and the separate admission policy."
            )
        else:
            interpretation = (
                "Depth-5 failed the predeclared held-out direction or exact-draw "
                "misclassification threshold."
            )
            decision = (
                "Do not trust minimax-v1-depth5 as the strong direction evaluator; "
                "diagnose errors on this frozen audit before changing the next policy."
            )
        record = {
            "run_id": run_id,
            "protocol_id": protocol_id,
            "experiment_type": "blind-depth5-audit-of-strong-heldout",
            "status": "COMPLETED",
            "started_at": _timestamp(started),
            "completed_at": _timestamp(completed),
            "git_commit": commit,
            "git_dirty": dirty,
            "environment": {"python": sys.version, "platform": platform.platform()},
            "component_versions": component_versions,
            "configuration": {
                **result["configuration"],
                "source_strong_run_id": strong_record["run_id"],
                "source_strong_run_path": str(strong_run_path.resolve()),
                "source_strong_run_sha256": strong_hash,
            },
            "hypothesis": "On at least 15 exactly solved held-out 3x3 cases, minimax-v1-depth5 will match exact direction at least 90% of the time and never call an exact draw decisive.",
            "baseline": "On development exact-v1, minimax-v1-depth5 matched 20/20 exact directions.",
            "treatment": "Admission-blind depth-5 play on every exact-completed held-out 3x3 definition using the predeclared seeds and cumulative node cap.",
            "expected_result": "All eligible cases complete; direction accuracy is at least 90%; no exact draw receives a decisive sampled direction.",
            "actual_result": actual_result,
            "interpretation": interpretation,
            "decision": decision,
            "results": result,
        }
        destination = run_directory / "run.json"
        destination.write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    except BaseException as error:
        _write_failed_record(run_directory, attempt, error)
        raise
    return destination


def run_exact_batch_audit(
    batch_run_path: Path,
    max_board_size: int,
    output_root: Path,
    repository: Path,
) -> Path:
    """Exact-solve the tractable, play-evaluated subset of a preserved batch."""

    started = _utc_now()
    batch_bytes = batch_run_path.read_bytes()
    batch_hash = hashlib.sha256(batch_bytes).hexdigest()
    batch_record = json.loads(batch_bytes.decode("utf-8"))
    candidates = batch_record["results"]["candidates"]
    result = exact_audit(candidates, max_board_size=max_board_size)
    completed = _utc_now()
    run_id = "{}-audit-{}".format(started.strftime("%Y%m%dT%H%M%S%fZ"), batch_hash[:8])
    run_directory = output_root / run_id
    run_directory.mkdir(parents=True, exist_ok=False)
    commit, dirty = _git_state(repository)
    record = {
        "run_id": run_id,
        "experiment_type": "exact-audit-of-sampled-batch",
        "status": "COMPLETED",
        "started_at": _timestamp(started),
        "completed_at": _timestamp(completed),
        "git_commit": commit,
        "git_dirty": dirty,
        "environment": {"python": sys.version, "platform": platform.platform()},
        "component_versions": {
            "parity_forge": __version__,
            "dsl_schema": 1,
            "engine": 1,
            "exact_solver": 1,
        },
        "configuration": {
            "source_batch_run_id": batch_record["run_id"],
            "source_batch_path": str(batch_run_path.resolve()),
            "source_batch_sha256": batch_hash,
            "max_board_size": max_board_size,
            "seeds": [],
        },
        "hypothesis": "Exact results for tractable generated cases will quantify how often each sampled profile points toward the wrong role.",
        "baseline": "Frozen sampled outcomes from the selected generation batch.",
        "treatment": "Full-width memoized minimax for every play-evaluated candidate within the board-size budget.",
        "expected_result": "Forced-result distribution and per-profile direction confusion without changing any evaluator.",
        "actual_result": {
            "audited_count": result["audited_count"],
            "forced_result_histogram": result["forced_result_histogram"],
            "profile_direction_confusion": result["profile_direction_confusion"],
        },
        "interpretation": "Sampled direction is diagnostic only; exact results determine forced optimal-play outcomes for this audited subset.",
        "decision": "Use the confusion table to choose the next evaluator experiment; do not tune the generator against sampled false positives.",
        "results": result,
    }
    destination = run_directory / "run.json"
    destination.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def run_minimax_calibration(
    batch_run_path: Path,
    audit_run_path: Path,
    seeds: Sequence[int],
    depth: int,
    output_root: Path,
    repository: Path,
) -> Path:
    """Evaluate minimax-v1 on the unchanged exact-audit candidate set."""

    started = _utc_now()
    batch_bytes = batch_run_path.read_bytes()
    audit_bytes = audit_run_path.read_bytes()
    batch_record = json.loads(batch_bytes.decode("utf-8"))
    audit_record = json.loads(audit_bytes.decode("utf-8"))
    expected_batch = audit_record["configuration"]["source_batch_run_id"]
    if batch_record["run_id"] != expected_batch:
        raise ValueError("audit run does not refer to the supplied batch run")
    result = calibrate_minimax(
        batch_record["results"]["candidates"],
        audit_record["results"]["candidates"],
        seeds,
        depth,
    )
    completed = _utc_now()
    combined_hash = hashlib.sha256(batch_bytes + audit_bytes).hexdigest()
    run_id = "{}-calibrate-{}".format(
        started.strftime("%Y%m%dT%H%M%S%fZ"), combined_hash[:8]
    )
    run_directory = output_root / run_id
    run_directory.mkdir(parents=True, exist_ok=False)
    commit, dirty = _git_state(repository)
    record = {
        "run_id": run_id,
        "experiment_type": "agent-calibration-on-frozen-exact-corpus",
        "status": "COMPLETED",
        "started_at": _timestamp(started),
        "completed_at": _timestamp(completed),
        "git_commit": commit,
        "git_dirty": dirty,
        "environment": {"python": sys.version, "platform": platform.platform()},
        "component_versions": {
            "parity_forge": __version__,
            "dsl_schema": 1,
            "engine": 1,
            "play_evaluator": 1,
            "minimax_agent": 1,
        },
        "configuration": {
            "source_batch_run_id": batch_record["run_id"],
            "source_audit_run_id": audit_record["run_id"],
            "source_sha256": combined_hash,
            "depth": depth,
            "seeds": list(seeds),
        },
        "hypothesis": "Depth-limited zero-sum search will point toward exact forced results more often than goal-directed-v1 on the frozen 3x3 corpus.",
        "baseline": audit_record["actual_result"]["profile_direction_confusion"],
        "treatment": "Minimax-v1 at fixed depth {} with identical rules and candidate corpus.".format(depth),
        "expected_result": "Direction accuracy exceeds goal-directed-v1's 12/20 without changing candidates or exact labels.",
        "actual_result": {
            "audited_count": result["audited_count"],
            "matching_directions": result["matching_directions"],
            "direction_accuracy": result["direction_accuracy"],
            "direction_confusion": result["direction_confusion"],
        },
        "interpretation": (
            "The new agent exceeds the declared 12/20 baseline."
            if result["matching_directions"] > 12
            else "The new agent does not exceed the declared 12/20 baseline."
        ),
        "decision": (
            "Add the policy as a distinct stronger cascade profile; retain exact audits."
            if result["matching_directions"] > 12
            else "Do not promote the policy; diagnose its confusion before further evaluator changes."
        ),
        "results": result,
    }
    destination = run_directory / "run.json"
    destination.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination
