"""One-shot Plan-0014 assessment-reconstruction lifecycle facade.

This is the only production entrypoint for the separately versioned
post-failure reconstruction.  It creates no gameplay, solver, agent, sampling,
telemetry-generation, selection, or candidate-block capability.  The first run
authenticates every input before publishing a reservation and attempt; recovery
never resumes an interrupted calculation.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
from typing import Any, Dict, Optional, Sequence

from .atlas_assessment_reconstruction_attestation import (
    build_plan0014_source_binding_v1,
    reconstruct_plan0014_assessment_artifacts_v1,
    validate_plan0014_source_binding_v1,
)
from .atlas_assessment_reconstruction_evidence import (
    PLAN0014_RECONSTRUCTION_EVIDENCE_ROOT_RELATIVE_V1,
    PLAN0014_RECONSTRUCTION_STAGE_ID_V1,
    ReconstructionEvidenceContract,
    ReconstructionEvidenceStore,
    ReconstructionRecoveryResult,
    begin_stage_v1,
    build_bootstrap_v1,
    failure_value_v1,
    fixed_reconstruction_evidence_contract_v1,
    load_chain_snapshot_v1,
    open_recovery_store_v1,
    publish_bootstrap_v1,
    recover_stage_locked_v1,
    seal_completed_v1,
    seal_failed_v1,
    validate_bootstrap_v1,
    validate_chain_snapshot_v1,
)
from .atlas_assessment_reconstruction_protocol import (
    ACTIVE_PLAN_PATH_V1,
    _read_current_regular,
    build_plan0014_assessment_reconstruction_protocol_v1,
    build_plan0014_production_closure_v1,
    reseal_plan0014_production_closure_v1,
    validate_plan0014_assessment_reconstruction_protocol_v1,
    validate_plan0014_production_closure_v1,
)
from .atlas_evidence import (
    EvidenceIntegrityError,
    canonical_json_bytes,
)


def _repository_path_v1(repository: str) -> Path:
    """Return only the exact Git top-level path, without inspecting HEAD."""

    if type(repository) is not str or not repository:
        raise ValueError("repository must be a nonempty exact string")
    requested = Path(os.path.abspath(repository))
    process = subprocess.run(
        ["git", "-C", str(requested), "rev-parse", "--show-toplevel"],
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )
    if process.returncode != 0:
        raise EvidenceIntegrityError(
            "Git top-level check failed: {}".format(
                process.stderr.decode("utf-8", "replace").strip()
            )
        )
    try:
        observed = Path(process.stdout.decode("utf-8", "strict").strip())
    except UnicodeDecodeError as error:
        raise EvidenceIntegrityError("Git top-level path is not UTF-8") from error
    if observed != requested:
        raise EvidenceIntegrityError("repository must be the exact Git top level")
    return requested


def _read_active_plan_v1(repository: Path, expected_size: int) -> bytes:
    """Read the current active plan as one stable, singly linked regular file."""

    raw = _read_current_regular(repository, ACTIVE_PLAN_PATH_V1, expected_size)
    try:
        raw.decode("utf-8", "strict")
    except UnicodeDecodeError as error:
        raise EvidenceIntegrityError("active plan is not valid UTF-8") from error
    return raw


def _recovery_dict_v1(result: ReconstructionRecoveryResult) -> Dict[str, Any]:
    return {
        "action": result.action,
        "lifecycle": result.lifecycle,
        "stage_id": PLAN0014_RECONSTRUCTION_STAGE_ID_V1,
        "terminal_seal_or_null": result.terminal_identity,
    }


def _validate_recorded_bootstrap_inputs_v1(
    repository: Path, bootstrap_value: Any
) -> Dict[str, Any]:
    """Authenticate stored source objects without requiring the current HEAD."""

    bootstrap = validate_bootstrap_v1(bootstrap_value)
    references = bootstrap["references"]
    validate_plan0014_production_closure_v1(
        str(repository), references["production_closure"]
    )
    validate_plan0014_source_binding_v1(
        references["source_binding"], str(repository)
    )
    return bootstrap


def _fresh_completed_result_v1(
    repository: Path, bootstrap: Dict[str, Any]
) -> Dict[str, Any]:
    """Reconstruct once and require the old-source binding to remain identical."""

    artifacts = reconstruct_plan0014_assessment_artifacts_v1(str(repository))
    if type(artifacts) is not dict or set(artifacts) != {"result", "source_binding"}:
        raise EvidenceIntegrityError(
            "assessment reconstruction artifact envelope drifted"
        )
    if canonical_json_bytes(artifacts["source_binding"]) != canonical_json_bytes(
        bootstrap["references"]["source_binding"]
    ):
        raise EvidenceIntegrityError(
            "assessment reconstruction source binding differs from bootstrap"
        )
    result = artifacts["result"]
    if type(result) is not dict or set(result) != {
        "inner_report",
        "outer_attestation",
    }:
        raise EvidenceIntegrityError("assessment reconstruction result shape drifted")
    return result


def _recover_with_held_lock_v1(
    store: ReconstructionEvidenceStore,
    contract: ReconstructionEvidenceContract,
    repository: Path,
) -> ReconstructionRecoveryResult:
    """Select recovery inputs and mutate the chain under one uninterrupted lock."""

    store.reconcile_pending_publications()
    catalog = store.scan_fixed_catalog()
    if catalog["bootstrap"] is None:
        return recover_stage_locked_v1(store, contract)

    bootstrap = _validate_recorded_bootstrap_inputs_v1(
        repository, store.read_bootstrap()
    )
    try:
        state = validate_chain_snapshot_v1(
            contract, bootstrap, load_chain_snapshot_v1(store)
        )
    except Exception:
        # The evidence primitive owns contradiction publication and the stable
        # fail-closed error shape.  No report calculation is attempted here.
        return recover_stage_locked_v1(store, contract)

    expected_completed_result = None
    if state in ("COMPLETED", "COMPLETED_UNSEALED"):
        expected_completed_result = _fresh_completed_result_v1(
            repository, bootstrap
        )
    return recover_stage_locked_v1(
        store,
        contract,
        expected_completed_result=expected_completed_result,
    )


def _recover_existing_root_v1(
    repository: Path,
    evidence_root: Path,
    contract: ReconstructionEvidenceContract,
) -> Optional[Dict[str, Any]]:
    """Recover an existing root, or return ``None`` without creating one."""

    with open_recovery_store_v1(evidence_root) as store:
        if store is None:
            return None
        with store.stage_lock(blocking=False):
            return _recovery_dict_v1(
                _recover_with_held_lock_v1(store, contract, repository)
            )


def _calculate_and_seal_attempt_v1(
    store: ReconstructionEvidenceStore,
    contract: ReconstructionEvidenceContract,
    repository: Path,
    bootstrap: Dict[str, Any],
    production_closure: Dict[str, Any],
) -> Dict[str, Any]:
    """Calculate once after ATTEMPTED and seal exactly one lifecycle."""

    try:
        result = _fresh_completed_result_v1(repository, bootstrap)
        reseal_plan0014_production_closure_v1(
            str(repository), production_closure
        )
        terminal = seal_completed_v1(store, contract, bootstrap, result)
    except Exception as error:
        # Reconcile publication windows before deciding whether failure is
        # still an admissible lifecycle.  Once completed.json exists, no
        # exception may replace it with FAILED.
        store.reconcile_pending_publications()
        observed = store.scan_fixed_catalog()
        if observed["completed"] is not None:
            raise
        terminal = seal_failed_v1(
            store,
            contract,
            bootstrap,
            failure_value_v1(error),
        )
        return {
            "lifecycle": "FAILED",
            "stage_id": PLAN0014_RECONSTRUCTION_STAGE_ID_V1,
            "terminal_seal": terminal["identity"],
        }
    return {
        "lifecycle": "COMPLETED",
        "result": result,
        "stage_id": PLAN0014_RECONSTRUCTION_STAGE_ID_V1,
        "terminal_seal": terminal["identity"],
    }


def _run_existing_with_held_lock_v1(
    store: ReconstructionEvidenceStore,
    contract: ReconstructionEvidenceContract,
    repository: Path,
) -> Optional[Dict[str, Any]]:
    """Continue only a pre-attempt chain; recover every later chain."""

    store.reconcile_pending_publications()
    catalog = store.scan_fixed_catalog()
    if not any(reference is not None for reference in catalog.values()):
        # Operational directories are not evidence.  The caller may perform a
        # fresh preflight and return to this root under a new lock.
        return None
    if catalog["bootstrap"] is None or catalog["contradiction"] is not None:
        return _recovery_dict_v1(
            _recover_with_held_lock_v1(store, contract, repository)
        )

    bootstrap = _validate_recorded_bootstrap_inputs_v1(
        repository, store.read_bootstrap()
    )
    try:
        state = validate_chain_snapshot_v1(
            contract, bootstrap, load_chain_snapshot_v1(store)
        )
    except Exception:
        return _recovery_dict_v1(
            _recover_with_held_lock_v1(store, contract, repository)
        )
    if state != "BOOTSTRAPPED":
        return _recovery_dict_v1(
            _recover_with_held_lock_v1(store, contract, repository)
        )

    # A bootstrap contains no attempt and therefore has consumed no one-shot
    # calculation.  Reauthenticate its recorded source against Git/current
    # closure bytes before publishing the sole reservation and attempt.
    production_closure = bootstrap["references"]["production_closure"]
    reseal_plan0014_production_closure_v1(
        str(repository), production_closure
    )
    begin_stage_v1(store, contract, bootstrap)
    return _calculate_and_seal_attempt_v1(
        store, contract, repository, bootstrap, production_closure
    )


def _run_existing_root_v1(
    repository: Path,
    evidence_root: Path,
    contract: ReconstructionEvidenceContract,
) -> Optional[Dict[str, Any]]:
    """Continue/recover an existing root, or request a fresh preflight."""

    with open_recovery_store_v1(evidence_root) as store:
        if store is None:
            return None
        with store.stage_lock(blocking=False):
            return _run_existing_with_held_lock_v1(
                store, contract, repository
            )


def run_atlas_assessment_reconstruction_stage_v1(
    repository: str,
) -> Dict[str, Any]:
    """Run the post-failure calculation at most once and seal its own lifecycle."""

    repository_path = _repository_path_v1(repository)
    evidence_root = (
        repository_path / PLAN0014_RECONSTRUCTION_EVIDENCE_ROOT_RELATIVE_V1
    )
    contract = fixed_reconstruction_evidence_contract_v1()

    existing = _run_existing_root_v1(
        repository_path, evidence_root, contract
    )
    if existing is not None:
        return existing

    protocol = validate_plan0014_assessment_reconstruction_protocol_v1(
        build_plan0014_assessment_reconstruction_protocol_v1()
    )
    production_closure = build_plan0014_production_closure_v1(
        str(repository_path)
    )
    active_plan_bytes = _read_active_plan_v1(
        repository_path,
        production_closure["payload"]["active_plan_ref"]["byte_count"],
    )

    # Source authentication completes before the new evidence root exists and
    # before any report construction is possible.
    source_binding = build_plan0014_source_binding_v1(str(repository_path))
    bootstrap = build_bootstrap_v1(
        protocol,
        active_plan_bytes,
        production_closure,
        source_binding,
    )

    with ReconstructionEvidenceStore.for_run(evidence_root) as store:
        with store.stage_lock(blocking=False):
            store.reconcile_pending_publications()
            catalog = store.scan_fixed_catalog()
            existing_artifact = any(
                reference is not None for reference in catalog.values()
            )
            if existing_artifact:
                return _run_existing_with_held_lock_v1(
                    store, contract, repository_path
                )

            # The source binding can take minutes to construct.  Rebuild it
            # and reseal HEAD, closure files, and active-plan bytes immediately
            # before the first immutable publication, so drift consumes no
            # reservation or attempt.
            validate_plan0014_source_binding_v1(
                source_binding, str(repository_path)
            )
            reseal_plan0014_production_closure_v1(
                str(repository_path), production_closure
            )

            publish_bootstrap_v1(store, bootstrap)
            begin_stage_v1(store, contract, bootstrap)
            return _calculate_and_seal_attempt_v1(
                store,
                contract,
                repository_path,
                bootstrap,
                production_closure,
            )


def recover_atlas_assessment_reconstruction_stage_v1(
    repository: str,
) -> Dict[str, Any]:
    """Recover without creating a missing root or resuming an interrupted run."""

    repository_path = _repository_path_v1(repository)
    evidence_root = (
        repository_path / PLAN0014_RECONSTRUCTION_EVIDENCE_ROOT_RELATIVE_V1
    )
    contract = fixed_reconstruction_evidence_contract_v1()
    result = _recover_existing_root_v1(
        repository_path, evidence_root, contract
    )
    if result is not None:
        return result
    return _recovery_dict_v1(
        ReconstructionRecoveryResult("NO_EVIDENCE", None, None)
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m parity_forge.atlas_assessment_reconstruction_stage"
    )
    parser.add_argument("command", choices=("run", "recover"))
    parser.add_argument("--repository", required=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = _build_parser().parse_args(argv)
    result = (
        run_atlas_assessment_reconstruction_stage_v1(arguments.repository)
        if arguments.command == "run"
        else recover_atlas_assessment_reconstruction_stage_v1(
            arguments.repository
        )
    )
    print(canonical_json_bytes(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = (
    "PLAN0014_RECONSTRUCTION_STAGE_ID_V1",
    "recover_atlas_assessment_reconstruction_stage_v1",
    "run_atlas_assessment_reconstruction_stage_v1",
)
