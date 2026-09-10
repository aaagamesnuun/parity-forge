"""Evidence lifecycle facade for the frozen Plan-0013 atlas assessment.

The report calculation and authenticated parent read path live in
:mod:`atlas_assessment_core`.  This module retains the historical run/recover
entrypoints and their write-capable evidence lifecycle, while explicitly
aliasing the calculation functions used by those entrypoints and existing
callers.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from .atlas_assessment_core import (
    ATLAS_ASSESSMENT_REPORT_VERSION_V1,
    ATLAS_ASSESSMENT_STAGE_ID_V1,
    ATLAS_ASSESSMENT_STAGE_PROTOCOL_ID_V1,
    ATLAS_PROTOCOL_ID_V1,
    ATLAS_PROTOCOL_ROOT_V1,
    _EVIDENCE_ROOT_RELATIVE_V1,
    _MANIFEST_PARENT,
    _META_PARENT_ORDER_V1,
    _assessment_parent_inputs_v1,
    _assessment_prerequisites_v1,
    _build_atlas_assessment_report_v1,
    _build_manifest_unavailable_meta_report_v1,
    _telemetry_metric_values,
    _validate_manifest_unavailable_meta_report_v1,
    _validate_pv_record,
    _validate_reconstructed_assessment_v1,
)
from .atlas_evidence import (
    ImmutableEvidenceStore,
    begin_stage,
    canonical_json_bytes,
    read_authenticated_stage_inputs,
    recover_stage,
    seal_completed_stage,
    seal_failed_stage,
)


def _failure_value(error: BaseException) -> Dict[str, Any]:
    return {
        "kind": "ASSESSMENT_STAGE_EXCEPTION",
        "exception_module": type(error).__module__,
        "exception_type": type(error).__qualname__,
        "message": str(error),
    }


def run_atlas_assessment_stage_v1(repository: str) -> Dict[str, Any]:
    if type(repository) is not str or not repository:
        raise ValueError("repository must be a nonempty exact string")
    repository_path = Path(repository).resolve()
    evidence_root = repository_path / _EVIDENCE_ROOT_RELATIVE_V1
    with ImmutableEvidenceStore(evidence_root) as store:
        with store.stage_lock(ATLAS_ASSESSMENT_STAGE_PROTOCOL_ID_V1):
            inputs = read_authenticated_stage_inputs(
                store, ATLAS_ASSESSMENT_STAGE_ID_V1
            )
            if (
                inputs.contract.stage_protocol_id
                != ATLAS_ASSESSMENT_STAGE_PROTOCOL_ID_V1
            ):
                raise ValueError("assessment stage protocol identity drifted")
            _assessment_prerequisites_v1(
                inputs.contract, inputs.ordered_parent_terminal_seals
            )
            begin_stage(
                store,
                repository_path,
                inputs.contract,
                inputs.production_closure,
                inputs.ordered_parent_terminal_seals,
                inputs.experiment_plan_bytes,
                (),
            )
            try:
                if inputs.detached_manifest is None:
                    report = _build_manifest_unavailable_meta_report_v1(
                        inputs.protocol,
                        inputs.ordered_parent_terminal_seals,
                    )
                else:
                    parent_values = _assessment_parent_inputs_v1(
                        store,
                        inputs.protocol,
                        inputs.ordered_parent_terminal_seals,
                    )
                    report = _build_atlas_assessment_report_v1(
                        inputs.detached_manifest,
                        inputs.protocol,
                        *parent_values,
                    )
            except Exception as error:
                terminal = seal_failed_stage(
                    store, inputs.contract, _failure_value(error), ()
                )
                return {
                    "lifecycle": "FAILED",
                    "stage_id": ATLAS_ASSESSMENT_STAGE_ID_V1,
                    "terminal_seal": terminal["identity"],
                }
            try:
                terminal = seal_completed_stage(
                    store,
                    repository_path,
                    inputs.contract,
                    inputs.production_closure,
                    inputs.experiment_plan_bytes,
                    report,
                    None,
                )
            except Exception as error:
                if store.artifact_exists(
                    ATLAS_ASSESSMENT_STAGE_PROTOCOL_ID_V1, "completed"
                ):
                    raise
                terminal = seal_failed_stage(
                    store, inputs.contract, _failure_value(error), ()
                )
                return {
                    "lifecycle": "FAILED",
                    "stage_id": ATLAS_ASSESSMENT_STAGE_ID_V1,
                    "terminal_seal": terminal["identity"],
                }
            return {
                "lifecycle": "COMPLETED",
                "stage_id": ATLAS_ASSESSMENT_STAGE_ID_V1,
                "summary": report,
                "terminal_seal": terminal["identity"],
            }


def _expected_completed_summary_for_recovery_v1(
    store: ImmutableEvidenceStore, inputs: Any
) -> Optional[Dict[str, Any]]:
    """Rebuild a completed report only when a completed body already exists."""

    if not store.artifact_exists(
        ATLAS_ASSESSMENT_STAGE_PROTOCOL_ID_V1, "completed"
    ):
        return None
    if inputs.detached_manifest is None:
        return _build_manifest_unavailable_meta_report_v1(
            inputs.protocol,
            inputs.ordered_parent_terminal_seals,
        )
    parent_values = _assessment_parent_inputs_v1(
        store,
        inputs.protocol,
        inputs.ordered_parent_terminal_seals,
    )
    return _build_atlas_assessment_report_v1(
        inputs.detached_manifest,
        inputs.protocol,
        *parent_values,
    )


def recover_atlas_assessment_stage_v1(repository: str) -> Dict[str, Any]:
    if type(repository) is not str or not repository:
        raise ValueError("repository must be a nonempty exact string")
    repository_path = Path(repository).resolve()
    evidence_root = repository_path / _EVIDENCE_ROOT_RELATIVE_V1
    with ImmutableEvidenceStore(evidence_root) as store:
        inputs = read_authenticated_stage_inputs(
            store, ATLAS_ASSESSMENT_STAGE_ID_V1
        )
        expected_completed_summary = _expected_completed_summary_for_recovery_v1(
            store, inputs
        )
        result = recover_stage(
            store,
            inputs.contract,
            (),
            repository=repository_path,
            expected_completed_summary=expected_completed_summary,
        )
        return {
            "action": result.action,
            "lifecycle": result.lifecycle,
            "stage_id": ATLAS_ASSESSMENT_STAGE_ID_V1,
            "terminal_seal_or_null": result.terminal_identity,
        }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m parity_forge.atlas_assessment_stage"
    )
    parser.add_argument("command", choices=("run", "recover"))
    parser.add_argument("--repository", required=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = _build_parser().parse_args(argv)
    result = (
        run_atlas_assessment_stage_v1(arguments.repository)
        if arguments.command == "run"
        else recover_atlas_assessment_stage_v1(arguments.repository)
    )
    print(canonical_json_bytes(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = (
    "ATLAS_ASSESSMENT_REPORT_VERSION_V1",
    "ATLAS_ASSESSMENT_STAGE_ID_V1",
    "ATLAS_ASSESSMENT_STAGE_PROTOCOL_ID_V1",
    "recover_atlas_assessment_stage_v1",
    "run_atlas_assessment_stage_v1",
)
