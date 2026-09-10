"""Small command-line surface for reproducible local checks."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Sequence

from .analysis import analyze_mapping
from .agents import GoalDirectedAgent, RandomAgent
from .batch import BatchConfig
from .cascade import StrongCascadeConfig
from .dsl import DefinitionError, Player, describe_rules, parse_definition
from .experiments import (
    check_static_corpus,
    run_blind_heldout_audit,
    run_exact_batch_audit,
    run_exact_solve,
    run_generation_batch,
    run_minimax_calibration,
    run_play_evaluation,
    run_static_corpus,
    run_strong_generation_batch,
)
from .capture_experiments import (
    CAPTURE_CORPUS_RELATIVE,
    CAPTURE_LOCK_RELATIVE,
    CAPTURE_MANIFEST_RELATIVE,
    freeze_capture_manifest,
    run_capture_interaction_stress,
    run_capture_paired,
)
from .capture_boundary_experiments import (
    CAPTURE_BOUNDARY_CORPUS_RELATIVE,
    CAPTURE_BOUNDARY_LOCK_RELATIVE,
    CAPTURE_BOUNDARY_MANIFEST_RELATIVE,
    freeze_capture_boundary_manifest,
    run_capture_boundary_fixed_depth5,
    run_capture_boundary_paired_exact,
)
from .two_runner_experiments import (
    TWO_RUNNER_CORPUS_RELATIVE,
    TWO_RUNNER_LOCK_RELATIVE,
    TWO_RUNNER_MANIFEST_RELATIVE,
    freeze_two_runner_manifest,
    run_two_runner_fixed_depth5,
    run_two_runner_paired_exact,
)
from .landscape_experiments import (
    LANDSCAPE_CORPUS_RELATIVE,
    LANDSCAPE_LOCK_RELATIVE,
    LANDSCAPE_MANIFEST_RELATIVE,
    default_landscape_source_paths,
    freeze_landscape_manifest,
    run_landscape,
    run_landscape_draw_stress,
)
from .simplicity import evaluate_simplicity
from .stalemate_experiments import (
    SOURCE_LANDSCAPE_MANIFEST_RELATIVE,
    SOURCE_LANDSCAPE_RAW_RELATIVE,
    STALEMATE_CORPUS_RELATIVE,
    STALEMATE_LOCK_RELATIVE,
    STALEMATE_MANIFEST_RELATIVE,
    freeze_stalemate_manifest,
    run_stalemate_draw_stress,
    run_stalemate_paired,
)


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as source:
        return json.load(source)


def _print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def _validate(path: Path) -> int:
    raw = _read_json(path)
    report = analyze_mapping(raw)
    result: Dict[str, Any] = {"static_analysis": report.to_dict()}
    if report.definition_hash is not None:
        definition = parse_definition(raw)
        result["rules"] = list(describe_rules(definition))
        result["simplicity"] = evaluate_simplicity(definition).to_dict()
    _print_json(result)
    return 0 if report.passes else 1


def _check_corpus(path: Path) -> int:
    result = check_static_corpus(_read_json(path))
    _print_json(result)
    return 0 if result["aggregate"]["mismatching_cases"] == 0 else 1


def _run_corpus(path: Path, output: Path, repository: Path) -> int:
    destination = run_static_corpus(path, output, repository)
    print(str(destination))
    record = _read_json(destination)
    return 0 if record["actual_result"]["mismatching_cases"] == 0 else 1


def _run_play(path: Path, case_id: str, samples: int, seed_start: int, output: Path, repository: Path) -> int:
    corpus = _read_json(path)
    matching = [case for case in corpus.get("cases", []) if case.get("id") == case_id]
    if len(matching) != 1:
        raise ValueError("case id must match exactly one corpus case")
    definition = parse_definition(matching[0]["definition"])
    seeds = tuple(range(seed_start, seed_start + samples))
    random_agent = RandomAgent()
    directed_agent = GoalDirectedAgent()
    profiles = (
        ("weak-random", {Player.A: random_agent, Player.B: random_agent}),
        ("medium-goal-directed", {Player.A: directed_agent, Player.B: directed_agent}),
    )
    destination = run_play_evaluation(
        definition,
        profiles,
        seeds,
        output,
        repository,
        source={"corpus_path": str(path.resolve()), "case_id": case_id},
    )
    print(str(destination))
    return 0


def _solve(path: Path, case_id: str, output: Path, repository: Path) -> int:
    corpus = _read_json(path)
    matching = [case for case in corpus.get("cases", []) if case.get("id") == case_id]
    if len(matching) != 1:
        raise ValueError("case id must match exactly one corpus case")
    definition = parse_definition(matching[0]["definition"])
    destination = run_exact_solve(
        definition,
        output,
        repository,
        source={"corpus_path": str(path.resolve()), "case_id": case_id},
    )
    print(str(destination))
    return 0


def _run_batch(generator_version: int, generator_seed: int, candidates: int, samples: int, play_seed_start: int, output: Path, repository: Path) -> int:
    destination = run_generation_batch(
        BatchConfig(
            generator_seed=generator_seed,
            candidate_count=candidates,
            play_seeds=tuple(range(play_seed_start, play_seed_start + samples)),
            generator_version=generator_version,
        ),
        output,
        repository,
    )
    print(str(destination))
    return 0


def _run_strong_batch(
    generator_seed: int,
    candidates: int,
    cheap_samples: int,
    strong_samples: int,
    strong_seed_start: int,
    max_depth5_board_size: int,
    max_depth5_candidates: int,
    max_search_nodes: int,
    max_exact_candidates: int,
    max_exact_states: int,
    development_batch: Path,
    output: Path,
    repository: Path,
) -> int:
    development_bytes = development_batch.read_bytes()
    development_record = json.loads(development_bytes.decode("utf-8"))
    development_hashes = tuple(
        candidate["definition_hash"]
        for candidate in development_record["results"]["candidates"]
    )
    destination = run_strong_generation_batch(
        StrongCascadeConfig(
            base=BatchConfig(
                generator_seed=generator_seed,
                candidate_count=candidates,
                play_seeds=tuple(range(cheap_samples)),
                generator_version=2,
            ),
            strong_seeds=tuple(
                range(strong_seed_start, strong_seed_start + strong_samples)
            ),
            minimax_depth=5,
            max_depth5_board_size=max_depth5_board_size,
            max_depth5_candidates=max_depth5_candidates,
            max_nodes_per_candidate=max_search_nodes,
            exact_max_board_size=3,
            max_exact_candidates=max_exact_candidates,
            max_exact_states=max_exact_states,
            development_definition_hashes=development_hashes,
        ),
        output,
        repository,
        development_source={
            "run_id": development_record["run_id"],
            "path": str(development_batch.resolve()),
            "sha256": hashlib.sha256(development_bytes).hexdigest(),
        },
    )
    print(str(destination))
    return 0


def _audit_exact(batch_run: Path, max_board_size: int, output: Path, repository: Path) -> int:
    destination = run_exact_batch_audit(
        batch_run,
        max_board_size,
        output,
        repository,
    )
    print(str(destination))
    return 0


def _audit_heldout_depth5(
    strong_run: Path,
    samples: int,
    seed_start: int,
    max_search_nodes: int,
    output: Path,
    repository: Path,
) -> int:
    destination = run_blind_heldout_audit(
        strong_run,
        tuple(range(seed_start, seed_start + samples)),
        5,
        max_search_nodes,
        output,
        repository,
        preregistered=True,
    )
    print(str(destination))
    return 0


def _calibrate_minimax(batch_run: Path, audit_run: Path, depth: int, samples: int, seed_start: int, output: Path, repository: Path) -> int:
    destination = run_minimax_calibration(
        batch_run,
        audit_run,
        tuple(range(seed_start, seed_start + samples)),
        depth,
        output,
        repository,
    )
    print(str(destination))
    return 0


def _freeze_landscape(
    corpus_directory: Path,
    repository: Path,
) -> int:
    destination = freeze_landscape_manifest(
        default_landscape_source_paths(repository),
        corpus_directory,
        repository,
    )
    print(str(destination))
    return 0


def _run_landscape(
    manifest: Path,
    lock: Path,
    output: Path,
    repository: Path,
) -> int:
    destination = run_landscape(manifest, lock, output, repository)
    print(str(destination))
    return 0


def _run_landscape_draw_stress(
    raw_run: Path,
    output: Path,
    repository: Path,
) -> int:
    destination = run_landscape_draw_stress(raw_run, output, repository)
    print(str(destination))
    return 0


def _freeze_stalemate_manifest(
    source_manifest: Path,
    corpus_directory: Path,
    repository: Path,
) -> int:
    destination = freeze_stalemate_manifest(
        source_manifest,
        corpus_directory,
        repository,
    )
    print(str(destination))
    return 0


def _run_stalemate_paired(
    manifest: Path,
    lock: Path,
    source_raw: Path,
    output: Path,
    repository: Path,
) -> int:
    destination = run_stalemate_paired(
        manifest,
        lock,
        source_raw,
        output,
        repository,
    )
    print(str(destination))
    return 0


def _run_stalemate_draw_stress(
    raw_run: Path,
    manifest: Path,
    lock: Path,
    output: Path,
    repository: Path,
) -> int:
    destination = run_stalemate_draw_stress(
        raw_run,
        manifest,
        lock,
        output,
        repository,
    )
    print(str(destination))
    return 0


def _freeze_capture_manifest(
    source_manifest: Path,
    corpus_directory: Path,
    repository: Path,
) -> int:
    destination = freeze_capture_manifest(
        source_manifest,
        corpus_directory,
        repository,
    )
    print(str(destination))
    return 0


def _run_capture_paired(
    manifest: Path,
    lock: Path,
    source_raw: Path,
    output: Path,
    repository: Path,
) -> int:
    destination = run_capture_paired(
        manifest,
        lock,
        source_raw,
        output,
        repository,
    )
    print(str(destination))
    return 0


def _run_capture_interaction_stress(
    raw_run: Path,
    manifest: Path,
    lock: Path,
    output: Path,
    repository: Path,
) -> int:
    destination = run_capture_interaction_stress(
        raw_run,
        manifest,
        lock,
        output,
        repository,
    )
    print(str(destination))
    return 0


def _freeze_capture_boundary_manifest(
    corpus_directory: Path,
    repository: Path,
) -> int:
    destination = freeze_capture_boundary_manifest(corpus_directory, repository)
    print(str(destination))
    return 0


def _run_capture_boundary_paired_exact(
    manifest: Path,
    lock: Path,
    output: Path,
    repository: Path,
) -> int:
    destination = run_capture_boundary_paired_exact(
        manifest, lock, output, repository
    )
    print(str(destination))
    return 0


def _run_capture_boundary_fixed_depth5(
    exact_run: Path,
    manifest: Path,
    lock: Path,
    output: Path,
    repository: Path,
) -> int:
    destination = run_capture_boundary_fixed_depth5(
        exact_run, manifest, lock, output, repository
    )
    print(str(destination))
    return 0


def _freeze_two_runner_manifest(
    corpus_directory: Path,
    repository: Path,
) -> int:
    destination = freeze_two_runner_manifest(corpus_directory, repository)
    print(str(destination))
    return 0


def _run_two_runner_paired_exact(
    manifest: Path,
    lock: Path,
    output: Path,
    repository: Path,
) -> int:
    destination = run_two_runner_paired_exact(
        manifest, lock, output, repository
    )
    print(str(destination))
    return 0


def _run_two_runner_fixed_depth5(
    exact_run: Path,
    manifest: Path,
    lock: Path,
    output: Path,
    repository: Path,
) -> int:
    destination = run_two_runner_fixed_depth5(
        exact_run, manifest, lock, output, repository
    )
    print(str(destination))
    return 0


def build_parser() -> argparse.ArgumentParser:
    default_corpus = Path("experiments/corpora/static-v1/corpus.json")
    parser = argparse.ArgumentParser(prog="parity_forge")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="validate and describe one game JSON file")
    validate.add_argument("path", type=Path)
    check = subparsers.add_parser("check-corpus", help="check frozen static expectations without writing a run")
    check.add_argument("--corpus", type=Path, default=default_corpus)
    run = subparsers.add_parser("run-static-corpus", help="write one immutable static experiment record")
    run.add_argument("--corpus", type=Path, default=default_corpus)
    run.add_argument("--output", type=Path, default=Path("experiments/runs"))
    run.add_argument("--repository", type=Path, default=Path.cwd())
    play = subparsers.add_parser("run-play-baseline", help="compare weak and medium agents on one frozen case")
    play.add_argument("--corpus", type=Path, default=default_corpus)
    play.add_argument("--case", default="healthy-crossing-seeds")
    play.add_argument("--samples", type=int, default=200)
    play.add_argument("--seed-start", type=int, default=0)
    play.add_argument("--output", type=Path, default=Path("experiments/runs"))
    play.add_argument("--repository", type=Path, default=Path.cwd())
    solve = subparsers.add_parser("solve", help="exactly solve one frozen corpus case")
    solve.add_argument("--corpus", type=Path, default=default_corpus)
    solve.add_argument("--case", default="healthy-crossing-seeds")
    solve.add_argument("--output", type=Path, default=Path("experiments/runs"))
    solve.add_argument("--repository", type=Path, default=Path.cwd())
    batch = subparsers.add_parser("run-batch", help="generate and screen a reproducible candidate batch")
    batch.add_argument("--generator-version", type=int, choices=(1, 2), default=2)
    batch.add_argument("--generator-seed", type=int, default=20260831)
    batch.add_argument("--candidates", type=int, default=100)
    batch.add_argument("--samples", type=int, default=30)
    batch.add_argument("--play-seed-start", type=int, default=0)
    batch.add_argument("--output", type=Path, default=Path("experiments/runs"))
    batch.add_argument("--repository", type=Path, default=Path.cwd())
    strong = subparsers.add_parser(
        "run-strong-batch", help="run cascade-v2 on a generator-v2 batch"
    )
    strong.add_argument("--generator-seed", type=int, default=20260901)
    strong.add_argument("--candidates", type=int, default=100)
    strong.add_argument("--cheap-samples", type=int, default=30)
    strong.add_argument("--strong-samples", type=int, default=30)
    strong.add_argument("--strong-seed-start", type=int, default=0)
    strong.add_argument("--max-depth5-board-size", type=int, choices=(3, 4), default=4)
    strong.add_argument("--max-depth5-candidates", type=int, default=100)
    strong.add_argument("--max-search-nodes", type=int, default=5000000)
    strong.add_argument("--max-exact-candidates", type=int, default=100)
    strong.add_argument("--max-exact-states", type=int, default=100000)
    strong.add_argument(
        "--development-batch",
        type=Path,
        default=Path(
            "experiments/runs/20260830T154309225370Z-batch-g20260831/run.json"
        ),
    )
    strong.add_argument("--output", type=Path, default=Path("experiments/runs"))
    strong.add_argument("--repository", type=Path, default=Path.cwd())
    audit = subparsers.add_parser("audit-exact", help="exact-solve the tractable subset of a batch run")
    audit.add_argument("batch_run", type=Path)
    audit.add_argument("--max-board-size", type=int, default=3)
    audit.add_argument("--output", type=Path, default=Path("experiments/runs"))
    audit.add_argument("--repository", type=Path, default=Path.cwd())
    blind = subparsers.add_parser(
        "audit-heldout-depth5",
        help="blindly test depth 5 on every exact-completed 3x3 strong-run case",
    )
    blind.add_argument("strong_run", type=Path)
    blind.add_argument("--samples", type=int, default=30)
    blind.add_argument("--seed-start", type=int, default=0)
    blind.add_argument("--max-search-nodes", type=int, default=5000000)
    blind.add_argument("--output", type=Path, default=Path("experiments/runs"))
    blind.add_argument("--repository", type=Path, default=Path.cwd())
    calibrate = subparsers.add_parser("calibrate-minimax", help="test minimax on a frozen exact-audited batch")
    calibrate.add_argument("batch_run", type=Path)
    calibrate.add_argument("audit_run", type=Path)
    calibrate.add_argument("--depth", type=int, default=3)
    calibrate.add_argument("--samples", type=int, default=30)
    calibrate.add_argument("--seed-start", type=int, default=0)
    calibrate.add_argument("--output", type=Path, default=Path("experiments/runs"))
    calibrate.add_argument("--repository", type=Path, default=Path.cwd())
    freeze_landscape = subparsers.add_parser(
        "freeze-landscape-manifest",
        help="freeze the outcome-blind 3x3 landscape manifest exactly once",
    )
    freeze_landscape.add_argument(
        "--corpus-directory",
        type=Path,
        default=LANDSCAPE_CORPUS_RELATIVE,
    )
    freeze_landscape.add_argument("--repository", type=Path, default=Path.cwd())
    landscape = subparsers.add_parser(
        "run-landscape",
        help="run the frozen 384-case raw exact landscape exactly once",
    )
    landscape.add_argument(
        "--manifest", type=Path, default=LANDSCAPE_MANIFEST_RELATIVE
    )
    landscape.add_argument("--lock", type=Path, default=LANDSCAPE_LOCK_RELATIVE)
    landscape.add_argument("--output", type=Path, default=Path("experiments/runs"))
    landscape.add_argument("--repository", type=Path, default=Path.cwd())
    stress = subparsers.add_parser(
        "run-landscape-draw-stress",
        help="stress exact draws from a committed raw landscape run",
    )
    stress.add_argument("raw_run", type=Path)
    stress.add_argument("--output", type=Path, default=Path("experiments/runs"))
    stress.add_argument("--repository", type=Path, default=Path.cwd())
    freeze_stalemate = subparsers.add_parser(
        "freeze-stalemate-manifest",
        help="freeze the treatment-outcome-free stalemate paired manifest once",
    )
    freeze_stalemate.add_argument(
        "--source-manifest",
        type=Path,
        default=SOURCE_LANDSCAPE_MANIFEST_RELATIVE,
    )
    freeze_stalemate.add_argument(
        "--corpus-directory",
        type=Path,
        default=STALEMATE_CORPUS_RELATIVE,
    )
    freeze_stalemate.add_argument("--repository", type=Path, default=Path.cwd())
    stalemate = subparsers.add_parser(
        "run-stalemate-paired",
        help="replay v1 and evaluate the frozen v2 stalemate pairs once",
    )
    stalemate.add_argument(
        "--manifest", type=Path, default=STALEMATE_MANIFEST_RELATIVE
    )
    stalemate.add_argument("--lock", type=Path, default=STALEMATE_LOCK_RELATIVE)
    stalemate.add_argument(
        "--source-raw", type=Path, default=SOURCE_LANDSCAPE_RAW_RELATIVE
    )
    stalemate.add_argument("--output", type=Path, default=Path("experiments/runs"))
    stalemate.add_argument("--repository", type=Path, default=Path.cwd())
    stalemate_stress = subparsers.add_parser(
        "run-stalemate-draw-stress",
        help="stress exact stalemate draws from a committed paired run",
    )
    stalemate_stress.add_argument("raw_run", type=Path)
    stalemate_stress.add_argument(
        "--manifest", type=Path, default=STALEMATE_MANIFEST_RELATIVE
    )
    stalemate_stress.add_argument(
        "--lock", type=Path, default=STALEMATE_LOCK_RELATIVE
    )
    stalemate_stress.add_argument(
        "--output", type=Path, default=Path("experiments/runs")
    )
    stalemate_stress.add_argument("--repository", type=Path, default=Path.cwd())
    freeze_capture = subparsers.add_parser(
        "freeze-capture-manifest",
        help="freeze the treatment-outcome-free capture paired manifest once",
    )
    freeze_capture.add_argument(
        "--source-manifest",
        type=Path,
        default=SOURCE_LANDSCAPE_MANIFEST_RELATIVE,
    )
    freeze_capture.add_argument(
        "--corpus-directory",
        type=Path,
        default=CAPTURE_CORPUS_RELATIVE,
    )
    freeze_capture.add_argument("--repository", type=Path, default=Path.cwd())
    capture = subparsers.add_parser(
        "run-capture-paired",
        help="replay v1 and evaluate the frozen v3 capture pairs once",
    )
    capture.add_argument(
        "--manifest", type=Path, default=CAPTURE_MANIFEST_RELATIVE
    )
    capture.add_argument("--lock", type=Path, default=CAPTURE_LOCK_RELATIVE)
    capture.add_argument(
        "--source-raw", type=Path, default=SOURCE_LANDSCAPE_RAW_RELATIVE
    )
    capture.add_argument("--output", type=Path, default=Path("experiments/runs"))
    capture.add_argument("--repository", type=Path, default=Path.cwd())
    capture_stress = subparsers.add_parser(
        "run-capture-interaction-stress",
        help="stress capture-responsive cases from a committed paired run",
    )
    capture_stress.add_argument("raw_run", type=Path)
    capture_stress.add_argument(
        "--manifest", type=Path, default=CAPTURE_MANIFEST_RELATIVE
    )
    capture_stress.add_argument(
        "--lock", type=Path, default=CAPTURE_LOCK_RELATIVE
    )
    capture_stress.add_argument(
        "--output", type=Path, default=Path("experiments/runs")
    )
    capture_stress.add_argument("--repository", type=Path, default=Path.cwd())
    freeze_capture_boundary = subparsers.add_parser(
        "freeze-capture-boundary-manifest",
        help="freeze the fresh outcome-free capture-boundary manifest once",
    )
    freeze_capture_boundary.add_argument(
        "--corpus-directory",
        type=Path,
        default=CAPTURE_BOUNDARY_CORPUS_RELATIVE,
    )
    freeze_capture_boundary.add_argument(
        "--repository", type=Path, default=Path.cwd()
    )
    capture_boundary_exact = subparsers.add_parser(
        "run-capture-boundary-paired-exact",
        help="solve every frozen capture-boundary source then treatment once",
    )
    capture_boundary_exact.add_argument(
        "--manifest", type=Path, default=CAPTURE_BOUNDARY_MANIFEST_RELATIVE
    )
    capture_boundary_exact.add_argument(
        "--lock", type=Path, default=CAPTURE_BOUNDARY_LOCK_RELATIVE
    )
    capture_boundary_exact.add_argument(
        "--output", type=Path, default=Path("experiments/runs")
    )
    capture_boundary_exact.add_argument(
        "--repository", type=Path, default=Path.cwd()
    )
    capture_boundary_depth5 = subparsers.add_parser(
        "run-capture-boundary-fixed-depth5",
        help="run the fixed source-then-treatment depth-5 schedule once",
    )
    capture_boundary_depth5.add_argument("exact_run", type=Path)
    capture_boundary_depth5.add_argument(
        "--manifest", type=Path, default=CAPTURE_BOUNDARY_MANIFEST_RELATIVE
    )
    capture_boundary_depth5.add_argument(
        "--lock", type=Path, default=CAPTURE_BOUNDARY_LOCK_RELATIVE
    )
    capture_boundary_depth5.add_argument(
        "--output", type=Path, default=Path("experiments/runs")
    )
    capture_boundary_depth5.add_argument(
        "--repository", type=Path, default=Path.cwd()
    )
    freeze_two_runner = subparsers.add_parser(
        "freeze-two-runner-manifest",
        help="freeze the outcome-free two-runner paired manifest once",
    )
    freeze_two_runner.add_argument(
        "--corpus-directory", type=Path, default=TWO_RUNNER_CORPUS_RELATIVE
    )
    freeze_two_runner.add_argument(
        "--repository", type=Path, default=Path.cwd()
    )
    two_runner_exact = subparsers.add_parser(
        "run-two-runner-paired-exact",
        help="solve every frozen two-runner source then treatment once",
    )
    two_runner_exact.add_argument(
        "--manifest", type=Path, default=TWO_RUNNER_MANIFEST_RELATIVE
    )
    two_runner_exact.add_argument(
        "--lock", type=Path, default=TWO_RUNNER_LOCK_RELATIVE
    )
    two_runner_exact.add_argument(
        "--output", type=Path, default=Path("experiments/runs")
    )
    two_runner_exact.add_argument(
        "--repository", type=Path, default=Path.cwd()
    )
    two_runner_depth5 = subparsers.add_parser(
        "run-two-runner-fixed-depth5",
        help="run the fixed two-runner source-then-treatment depth-5 schedule once",
    )
    two_runner_depth5.add_argument("exact_run", type=Path)
    two_runner_depth5.add_argument(
        "--manifest", type=Path, default=TWO_RUNNER_MANIFEST_RELATIVE
    )
    two_runner_depth5.add_argument(
        "--lock", type=Path, default=TWO_RUNNER_LOCK_RELATIVE
    )
    two_runner_depth5.add_argument(
        "--output", type=Path, default=Path("experiments/runs")
    )
    two_runner_depth5.add_argument(
        "--repository", type=Path, default=Path.cwd()
    )
    return parser


def main(argv: Sequence[str] = ()) -> int:
    parser = build_parser()
    arguments = parser.parse_args(list(argv) if argv else None)
    try:
        if arguments.command == "validate":
            return _validate(arguments.path)
        if arguments.command == "check-corpus":
            return _check_corpus(arguments.corpus)
        if arguments.command == "run-static-corpus":
            return _run_corpus(arguments.corpus, arguments.output, arguments.repository)
        if arguments.command == "solve":
            return _solve(arguments.corpus, arguments.case, arguments.output, arguments.repository)
        if arguments.command == "run-batch":
            if arguments.candidates < 1 or arguments.samples < 1:
                raise ValueError("candidates and samples must be at least one")
            return _run_batch(
                arguments.generator_version,
                arguments.generator_seed,
                arguments.candidates,
                arguments.samples,
                arguments.play_seed_start,
                arguments.output,
                arguments.repository,
            )
        if arguments.command == "run-strong-batch":
            if min(
                arguments.candidates,
                arguments.cheap_samples,
                arguments.strong_samples,
                arguments.max_depth5_candidates,
                arguments.max_search_nodes,
                arguments.max_exact_candidates,
                arguments.max_exact_states,
            ) < 1:
                raise ValueError("all sample and candidate budgets must be at least one")
            return _run_strong_batch(
                arguments.generator_seed,
                arguments.candidates,
                arguments.cheap_samples,
                arguments.strong_samples,
                arguments.strong_seed_start,
                arguments.max_depth5_board_size,
                arguments.max_depth5_candidates,
                arguments.max_search_nodes,
                arguments.max_exact_candidates,
                arguments.max_exact_states,
                arguments.development_batch,
                arguments.output,
                arguments.repository,
            )
        if arguments.command == "audit-exact":
            if not 3 <= arguments.max_board_size <= 5:
                raise ValueError("max-board-size must be between 3 and 5")
            return _audit_exact(
                arguments.batch_run,
                arguments.max_board_size,
                arguments.output,
                arguments.repository,
            )
        if arguments.command == "audit-heldout-depth5":
            if arguments.samples < 1 or arguments.max_search_nodes < 1:
                raise ValueError("samples and max-search-nodes must be at least one")
            return _audit_heldout_depth5(
                arguments.strong_run,
                arguments.samples,
                arguments.seed_start,
                arguments.max_search_nodes,
                arguments.output,
                arguments.repository,
            )
        if arguments.command == "calibrate-minimax":
            if arguments.depth < 1 or arguments.samples < 1:
                raise ValueError("depth and samples must be at least one")
            return _calibrate_minimax(
                arguments.batch_run,
                arguments.audit_run,
                arguments.depth,
                arguments.samples,
                arguments.seed_start,
                arguments.output,
                arguments.repository,
            )
        if arguments.command == "freeze-landscape-manifest":
            return _freeze_landscape(
                arguments.corpus_directory,
                arguments.repository,
            )
        if arguments.command == "run-landscape":
            return _run_landscape(
                arguments.manifest,
                arguments.lock,
                arguments.output,
                arguments.repository,
            )
        if arguments.command == "run-landscape-draw-stress":
            return _run_landscape_draw_stress(
                arguments.raw_run,
                arguments.output,
                arguments.repository,
            )
        if arguments.command == "freeze-stalemate-manifest":
            return _freeze_stalemate_manifest(
                arguments.source_manifest,
                arguments.corpus_directory,
                arguments.repository,
            )
        if arguments.command == "run-stalemate-paired":
            return _run_stalemate_paired(
                arguments.manifest,
                arguments.lock,
                arguments.source_raw,
                arguments.output,
                arguments.repository,
            )
        if arguments.command == "run-stalemate-draw-stress":
            return _run_stalemate_draw_stress(
                arguments.raw_run,
                arguments.manifest,
                arguments.lock,
                arguments.output,
                arguments.repository,
            )
        if arguments.command == "freeze-capture-manifest":
            return _freeze_capture_manifest(
                arguments.source_manifest,
                arguments.corpus_directory,
                arguments.repository,
            )
        if arguments.command == "run-capture-paired":
            return _run_capture_paired(
                arguments.manifest,
                arguments.lock,
                arguments.source_raw,
                arguments.output,
                arguments.repository,
            )
        if arguments.command == "run-capture-interaction-stress":
            return _run_capture_interaction_stress(
                arguments.raw_run,
                arguments.manifest,
                arguments.lock,
                arguments.output,
                arguments.repository,
            )
        if arguments.command == "freeze-capture-boundary-manifest":
            return _freeze_capture_boundary_manifest(
                arguments.corpus_directory,
                arguments.repository,
            )
        if arguments.command == "run-capture-boundary-paired-exact":
            return _run_capture_boundary_paired_exact(
                arguments.manifest,
                arguments.lock,
                arguments.output,
                arguments.repository,
            )
        if arguments.command == "run-capture-boundary-fixed-depth5":
            return _run_capture_boundary_fixed_depth5(
                arguments.exact_run,
                arguments.manifest,
                arguments.lock,
                arguments.output,
                arguments.repository,
            )
        if arguments.command == "freeze-two-runner-manifest":
            return _freeze_two_runner_manifest(
                arguments.corpus_directory,
                arguments.repository,
            )
        if arguments.command == "run-two-runner-paired-exact":
            return _run_two_runner_paired_exact(
                arguments.manifest,
                arguments.lock,
                arguments.output,
                arguments.repository,
            )
        if arguments.command == "run-two-runner-fixed-depth5":
            return _run_two_runner_fixed_depth5(
                arguments.exact_run,
                arguments.manifest,
                arguments.lock,
                arguments.output,
                arguments.repository,
            )
        if arguments.samples < 1:
            raise ValueError("samples must be at least one")
        return _run_play(
            arguments.corpus,
            arguments.case,
            arguments.samples,
            arguments.seed_start,
            arguments.output,
            arguments.repository,
        )
    except (OSError, json.JSONDecodeError, DefinitionError, ValueError) as error:
        parser.error(str(error))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
