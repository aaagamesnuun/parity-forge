"""Outcome-free manifest stage for the frozen Plan-0013 atlas.

This is the only production stage allowed to reconstruct the full selection.
It authenticates the closed historical inventory at its pinned Git commit,
rebuilds the reviewed selection and protocol, reserves the one-shot manifest
stage, and only then exports development definitions into the detached
manifest.  Candidate-block definitions never cross this module boundary.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from .atlas import (
    ATLAS_CANONICAL_SELECTION_SHA256_V1,
    ATLAS_SELECTION_PARTITION_ROOT_V1,
    build_frozen_atlas_selection_snapshot_v1,
    validate_frozen_atlas_selection_snapshot_v1,
)
from .atlas_evidence import (
    ImmutableEvidenceStore,
    ProductionClosure,
    StageContract,
    begin_stage,
    build_all_production_closures,
    canonical_json_bytes,
    capture_clean_head,
    extract_stage_contract,
    extract_recovery_stage_contract,
    publish_manifest_bootstrap,
    publish_manifest_freeze,
    recover_stage,
    reseal_production_closure,
    seal_completed_stage,
    seal_failed_stage,
    verify_commit_relation,
)
from .atlas_history import (
    ATLAS_HISTORY_CUTOFF_COMMIT_V1,
    ATLAS_HISTORY_CUTOFF_TREE_V1,
    ATLAS_HISTORY_INVENTORY_V1,
    build_prior_gameplay_exposure_projection_v1,
    build_synthetic_fixture_exposure_projection_v1,
)
from .atlas_protocol import (
    ATLAS_DEFINITION_ORIENTATION_COUNT_V1,
    ATLAS_DEVELOPMENT_DEFINITION_COUNT_V1,
    ATLAS_DEVELOPMENT_PAIR_COUNT_V1,
    ATLAS_EVALUATOR_COMMIT_V1,
    ATLAS_PROTOCOL_CANONICAL_SHA256_V1,
    ATLAS_PROTOCOL_ID_V1,
    ATLAS_PROTOCOL_ROOT_V1,
    ATLAS_SELECTOR_COMMIT_V1,
    build_frozen_atlas_protocol_v1,
    validate_frozen_atlas_protocol_v1,
)
from .atlas_stage_data import (
    ATLAS_DETACHED_MANIFEST_ID_V1,
    build_detached_atlas_development_manifest_v1,
    validate_detached_atlas_development_manifest_v1,
)


ATLAS_MANIFEST_STAGE_ID_V1 = "OUTCOME_FREE_DEVELOPMENT_MANIFEST"
ATLAS_MANIFEST_STAGE_PROTOCOL_ID_V1 = (
    "plan0013-atlas-development-manifest-v1"
)
ATLAS_MANIFEST_STAGE_SUMMARY_VERSION_V1 = 1

_EVIDENCE_ROOT_RELATIVE_V1 = (
    "experiments/runs/plan0013-atlas-development-evidence-v2"
)
_EXPERIMENT_PLAN_PATH_V1 = (
    "docs/plans/active/0013-six-family-development-atlas.md"
)

# The exact entrypoint set is itself part of the manifest-stage closure.  Each
# value is a one-element, already ASCII-sorted tuple as required by the closure
# builder.  There is intentionally no package-wide dispatcher importing all
# stages, because that would collapse their capability boundaries.
ATLAS_PRODUCTION_ENTRYPOINTS_V1 = {
    "OUTCOME_FREE_DEVELOPMENT_MANIFEST": (
        "src/parity_forge/atlas_manifest_stage.py",
    ),
    "EXACT_ALL_288": ("src/parity_forge/atlas_exact_stage.py",),
    "RANDOM_ALL_18432_GAMES": ("src/parity_forge/atlas_random_stage.py",),
    "TERMINAL_DEPTH1_ALL_18432_GAMES": (
        "src/parity_forge/atlas_depth1_stage.py",
    ),
    "REPLAY_TELEMETRY_COMPLETE_TRACES_ONLY": (
        "src/parity_forge/atlas_telemetry_stage.py",
    ),
    "ASSESSMENT_AND_INSPECTION": (
        "src/parity_forge/atlas_assessment_stage.py",
    ),
}


@dataclass(frozen=True)
class _ManifestPreflight:
    repository: Path
    selection: Dict[str, Any]
    protocol: Dict[str, Any]
    contract: StageContract
    contracts: Tuple[StageContract, ...]
    closures: Tuple[ProductionClosure, ...]
    experiment_plan_bytes: bytes


def _run_git(repository: Path, arguments: Sequence[str]) -> bytes:
    process = subprocess.run(
        ["git", "-C", str(repository)] + list(arguments),
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )
    if process.returncode != 0:
        raise ValueError(
            "manifest Git preflight failed: {}".format(
                process.stderr.decode("utf-8", "replace").strip()
            )
        )
    return process.stdout


def _exact_repository(repository: str) -> Path:
    if type(repository) is not str or not repository:
        raise ValueError("repository must be a nonempty exact string")
    requested = Path(repository).resolve()
    try:
        top = Path(
            _run_git(requested, ("rev-parse", "--show-toplevel"))
            .decode("utf-8", "strict")
            .strip()
        ).resolve()
    except UnicodeDecodeError as error:
        raise ValueError("Git repository path is not UTF-8") from error
    if top != requested:
        raise ValueError("repository must be the exact Git top level")
    return requested


def _read_history_sources(repository: Path) -> Dict[str, bytes]:
    try:
        cutoff_tree = (
            _run_git(
                repository,
                ("rev-parse", ATLAS_HISTORY_CUTOFF_COMMIT_V1 + "^{tree}"),
            )
            .decode("ascii", "strict")
            .strip()
        )
    except UnicodeDecodeError as error:
        raise ValueError("history cutoff tree identity is not ASCII") from error
    if cutoff_tree != ATLAS_HISTORY_CUTOFF_TREE_V1:
        raise ValueError("history cutoff commit tree differs from its frozen identity")
    return {
        path: _run_git(
            repository, ("show", ATLAS_HISTORY_CUTOFF_COMMIT_V1 + ":" + path)
        )
        for path, _digest, _byte_count in ATLAS_HISTORY_INVENTORY_V1
    }


def _rebuild_selection_and_protocol(
    repository: Path,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    prior = build_prior_gameplay_exposure_projection_v1(
        _read_history_sources(repository)
    )
    synthetic = build_synthetic_fixture_exposure_projection_v1()
    selection = build_frozen_atlas_selection_snapshot_v1(prior, synthetic)
    validate_frozen_atlas_selection_snapshot_v1(selection, prior, synthetic)
    if (
        hashlib.sha256(canonical_json_bytes(selection)).hexdigest()
        != ATLAS_CANONICAL_SELECTION_SHA256_V1
        or selection.get("selection_partition_root")
        != ATLAS_SELECTION_PARTITION_ROOT_V1
    ):
        raise ValueError("frozen selection commitments did not reconstruct")
    protocol = build_frozen_atlas_protocol_v1(selection)
    validate_frozen_atlas_protocol_v1(protocol, selection)
    if (
        protocol.get("protocol_id") != ATLAS_PROTOCOL_ID_V1
        or protocol.get("protocol_root") != ATLAS_PROTOCOL_ROOT_V1
        or hashlib.sha256(canonical_json_bytes(protocol)).hexdigest()
        != ATLAS_PROTOCOL_CANONICAL_SHA256_V1
    ):
        raise ValueError("frozen atlas protocol commitments did not reconstruct")
    return selection, protocol


def _read_clean_experiment_plan(
    repository: Path, source_commit: str
) -> bytes:
    live = (repository / _EXPERIMENT_PLAN_PATH_V1).read_bytes()
    committed = _run_git(
        repository, ("show", source_commit + ":" + _EXPERIMENT_PLAN_PATH_V1)
    )
    if live != committed:
        raise ValueError("live experiment plan differs from clean HEAD")
    return live


def _manifest_preflight(repository: str) -> _ManifestPreflight:
    repository_path = _exact_repository(repository)
    head = capture_clean_head(repository_path)
    verify_commit_relation(
        repository_path, ATLAS_SELECTOR_COMMIT_V1, ATLAS_EVALUATOR_COMMIT_V1
    )
    verify_commit_relation(
        repository_path, ATLAS_EVALUATOR_COMMIT_V1, head["source_commit"]
    )
    selection, protocol = _rebuild_selection_and_protocol(repository_path)
    contracts = tuple(
        extract_stage_contract(protocol, stage_id)
        for stage_id in protocol["stage_sequence"]
    )
    if tuple(contract.stage_index for contract in contracts) != tuple(range(6)):
        raise ValueError("frozen stage contract sequence did not reconstruct")
    contract = contracts[0]
    if (
        contract.stage_id != ATLAS_MANIFEST_STAGE_ID_V1
        or contract.stage_protocol_id != ATLAS_MANIFEST_STAGE_PROTOCOL_ID_V1
    ):
        raise ValueError("manifest stage contract identity drifted")
    plan = _read_clean_experiment_plan(repository_path, head["source_commit"])
    closures = build_all_production_closures(
        repository_path,
        contracts,
        ATLAS_PRODUCTION_ENTRYPOINTS_V1,
        plan,
    )
    if any(
        closure.payload["source_commit"] != head["source_commit"]
        or closure.payload["source_tree"] != head["source_tree"]
        for closure in closures
    ):
        raise ValueError("production closures do not share the clean preflight HEAD")
    return _ManifestPreflight(
        repository=repository_path,
        selection=selection,
        protocol=protocol,
        contract=contract,
        contracts=contracts,
        closures=closures,
        experiment_plan_bytes=plan,
    )


def _manifest_summary(
    preflight: _ManifestPreflight, manifest: Mapping[str, Any]
) -> Dict[str, Any]:
    first_closure = preflight.closures[0]
    return {
        "summary_version": ATLAS_MANIFEST_STAGE_SUMMARY_VERSION_V1,
        "summary_kind": "OUTCOME_FREE_DEVELOPMENT_MANIFEST",
        "protocol_id": ATLAS_PROTOCOL_ID_V1,
        "protocol_root": ATLAS_PROTOCOL_ROOT_V1,
        "manifest_id": ATLAS_DETACHED_MANIFEST_ID_V1,
        "manifest_root": manifest["manifest_root"],
        "development_pair_count": manifest["development_pair_count"],
        "development_definition_count": manifest["development_definition_count"],
        "orientation_definition_count": manifest["orientation_definition_count"],
        "production_closure_count": len(preflight.closures),
        "ordered_production_closure_roots": [
            closure.root for closure in preflight.closures
        ],
        "source_commit": first_closure.payload["source_commit"],
        "source_tree": first_closure.payload["source_tree"],
        "gameplay_outcome_count": 0,
        "candidate_definition_export_count": 0,
    }


def _manifest_failure(error: BaseException) -> Dict[str, str]:
    # Do not persist exception text: a validation error may contain a private
    # candidate identity.  The closed class and type are enough to distinguish
    # implementation failure from a completed scientific result.
    return {
        "kind": "MANIFEST_STAGE_EXCEPTION",
        "exception_module": type(error).__module__,
        "exception_type": type(error).__qualname__,
    }


def _reseal_all_production_closures(preflight: _ManifestPreflight) -> None:
    """Recheck every future stage blob immediately before completion."""

    if len(preflight.contracts) != 6 or len(preflight.closures) != 6:
        raise ValueError("manifest completion requires all six production closures")
    for contract, closure in zip(preflight.contracts, preflight.closures):
        if contract.stage_id != closure.payload.get("stage_id"):
            raise ValueError("production closure order differs from stage contracts")
        reseal_production_closure(
            preflight.repository,
            contract,
            closure,
            preflight.experiment_plan_bytes,
        )


def run_atlas_manifest_stage_v1(repository: str) -> Dict[str, Any]:
    preflight = _manifest_preflight(repository)
    evidence_root = preflight.repository / _EVIDENCE_ROOT_RELATIVE_V1
    with ImmutableEvidenceStore(evidence_root) as store:
        with store.stage_lock(preflight.contract.stage_protocol_id):
            publish_manifest_bootstrap(
                store,
                preflight.contract,
                preflight.protocol,
                preflight.closures,
                preflight.experiment_plan_bytes,
            )
            begin_stage(
                store,
                preflight.repository,
                preflight.contract,
                preflight.closures[0],
                (),
                preflight.experiment_plan_bytes,
            )
            try:
                manifest = build_detached_atlas_development_manifest_v1(
                    preflight.selection, preflight.protocol
                )
                manifest = validate_detached_atlas_development_manifest_v1(
                    manifest, preflight.protocol
                )
                if (
                    manifest["development_pair_count"]
                    != ATLAS_DEVELOPMENT_PAIR_COUNT_V1
                    or manifest["development_definition_count"]
                    != ATLAS_DEVELOPMENT_DEFINITION_COUNT_V1
                    or manifest["orientation_definition_count"]
                    != ATLAS_DEFINITION_ORIENTATION_COUNT_V1
                ):
                    raise ValueError("detached manifest fixed denominator drifted")
                refs = publish_manifest_freeze(
                    store,
                    preflight.contract,
                    preflight.protocol,
                    manifest,
                    preflight.closures,
                    preflight.experiment_plan_bytes,
                )
                summary = _manifest_summary(preflight, manifest)
                _reseal_all_production_closures(preflight)
                terminal = seal_completed_stage(
                    store,
                    preflight.repository,
                    preflight.contract,
                    preflight.closures[0],
                    preflight.experiment_plan_bytes,
                    summary,
                    refs,
                )
            except Exception as error:
                # Once COMPLETED exists, recovery owns the tiny seal-publication
                # crash window.  Publishing FAILED beside it would create a
                # contradictory immutable chain.
                if store.artifact_exists(
                    preflight.contract.stage_protocol_id, "completed"
                ):
                    raise
                terminal = seal_failed_stage(
                    store, preflight.contract, _manifest_failure(error)
                )
                return {
                    "lifecycle": "FAILED",
                    "stage_id": ATLAS_MANIFEST_STAGE_ID_V1,
                    "terminal_seal": terminal["identity"],
                }
    return {
        "lifecycle": "COMPLETED",
        "stage_id": ATLAS_MANIFEST_STAGE_ID_V1,
        "summary": summary,
        "terminal_seal": terminal["identity"],
    }


def recover_atlas_manifest_stage_v1(repository: str) -> Dict[str, Any]:
    repository_path = _exact_repository(repository)
    evidence_root = repository_path / _EVIDENCE_ROOT_RELATIVE_V1
    with ImmutableEvidenceStore(evidence_root) as store:
        contract = extract_recovery_stage_contract(ATLAS_MANIFEST_STAGE_ID_V1)
        if contract.stage_protocol_id != ATLAS_MANIFEST_STAGE_PROTOCOL_ID_V1:
            raise ValueError("manifest recovery contract identity drifted")
        result = recover_stage(store, contract, repository=repository_path)
    return {
        "action": result.action,
        "lifecycle": result.lifecycle,
        "stage_id": ATLAS_MANIFEST_STAGE_ID_V1,
        "terminal_seal_or_null": result.terminal_identity,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m parity_forge.atlas_manifest_stage"
    )
    parser.add_argument("command", choices=("run", "recover"))
    parser.add_argument("--repository", required=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = _build_parser().parse_args(argv)
    result = (
        run_atlas_manifest_stage_v1(arguments.repository)
        if arguments.command == "run"
        else recover_atlas_manifest_stage_v1(arguments.repository)
    )
    print(canonical_json_bytes(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = (
    "ATLAS_MANIFEST_STAGE_ID_V1",
    "ATLAS_MANIFEST_STAGE_PROTOCOL_ID_V1",
    "ATLAS_MANIFEST_STAGE_SUMMARY_VERSION_V1",
    "ATLAS_PRODUCTION_ENTRYPOINTS_V1",
    "recover_atlas_manifest_stage_v1",
    "run_atlas_manifest_stage_v1",
)
