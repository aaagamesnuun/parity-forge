"""Concrete exact-compute stage for the frozen Plan-0013 atlas.

The production entrypoint accepts only a repository location.  Scientific
coordinates come exclusively from the frozen protocol and detached development
manifest.  The private slot helpers are intentionally schedule-parametric so
synthetic contract tests can exercise the compute boundary without exposing a
production definition or candidate-block body.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

from .atlas_protocol import (
    ATLAS_ACTION_CANDIDATE_CAP_V1,
    ATLAS_DEFINITION_ORIENTATION_COUNT_V1,
    ATLAS_DEVELOPMENT_DEFINITION_COUNT_V1,
    ATLAS_D4_TRANSFORMS_V1,
    ATLAS_GAME_PLY_CAP_V1,
    iter_frozen_atlas_exact_schedule_from_protocol_v1,
    iter_frozen_atlas_orientation_schedule_from_protocol_v1,
)
from .atlas_stage_data import (
    iter_joined_atlas_exact_definitions_v1,
    iter_joined_atlas_orientation_definitions_v1,
)
from .atlas_evidence import (
    ImmutableEvidenceStore,
    LedgerSpec,
    StageContract,
    block_stage,
    begin_stage,
    canonical_json_bytes,
    domain_identity,
    publish_stage_completion_evidence,
    read_authenticated_stage_inputs,
    recover_stage,
    seal_completed_stage,
    seal_failed_stage,
)
from .dsl import Player, definition_hash, parse_definition
from .engine import Action, apply_action, initial_state, legal_actions
from .solver import SolveBudgetExceeded, solve_game
from .symmetry import D4_TRANSFORMS, transform_definition, transform_position


ATLAS_EXACT_STAGE_ID_V1 = "EXACT_ALL_288"
ATLAS_EXACT_STAGE_PROTOCOL_ID_V1 = "plan0013-atlas-development-exact-v1"
ATLAS_EXACT_RECORD_VERSION_V1 = 1
ATLAS_EXACT_PV_RECORD_VERSION_V1 = 1

_EXACT_RECORD_DOMAIN_V1 = b"parity-forge:plan0013:exact-record:v1\0"
_PV_RECORD_DOMAIN_V1 = b"parity-forge:plan0013:exact-pv-record:v1\0"
_EXACT_PHASE_ID_V1 = "exact"
_PV_PHASE_ID_V1 = "exact-pv"
_EXACT_STAGE_SUMMARY_DOMAIN_V1 = (
    b"parity-forge:plan0013:exact-stage-summary:v1\0"
)
_EVIDENCE_ROOT_RELATIVE_V1 = (
    "experiments/runs/plan0013-atlas-development-evidence-v2"
)


def _json_copy(value: Any, label: str) -> Any:
    try:
        return json.loads(canonical_json_bytes(value).decode("utf-8"))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise TypeError("{} must be finite canonical JSON".format(label)) from error


def _sha256(value: Any, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError("{} must be a lowercase SHA-256".format(label))
    return value


def _exact_int(value: Any, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError("{} must be an exact integer >= {}".format(label, minimum))
    return value


def _sealed_definition(value: Any, expected_hash: Any, label: str):
    entry = canonical_json_bytes(value)
    body = json.loads(entry.decode("utf-8"))
    definition = parse_definition(body)
    if canonical_json_bytes(definition.to_dict()) != entry:
        raise ValueError("{} is not a canonical DSL body".format(label))
    if definition_hash(definition) != _sha256(expected_hash, label + " hash"):
        raise ValueError("{} differs from its frozen definition hash".format(label))
    return definition, body, entry


def _record_root(domain: bytes, unsigned: Mapping[str, Any]) -> str:
    return domain_identity(domain, dict(unsigned))


def _exception_evidence(error: BaseException) -> Dict[str, str]:
    return {
        "exception_module": type(error).__module__,
        "exception_type": type(error).__qualname__,
        "message": str(error),
    }


def _invalid_exact_record_v1(slot_value: Any, error: BaseException) -> Dict[str, Any]:
    slot = _json_copy(slot_value, "invalid exact slot")
    unsigned = {
        "record_version": ATLAS_EXACT_RECORD_VERSION_V1,
        "record_kind": "EXACT",
        "slot_id": _sha256(slot.get("slot_id"), "invalid exact slot identity"),
        "definition_hash": slot.get("representative_definition_hash"),
        "definition_byte_count": None,
        "status": "INVALID",
        "max_states": slot.get("max_states"),
        "max_action_candidates_per_state": slot.get(
            "max_action_candidates_per_state"
        ),
        "max_state_action_candidate_evaluations": slot.get(
            "max_state_action_candidate_evaluations"
        ),
        "result_or_null": None,
        "contradiction_or_null": {
            "kind": "EXACT_SLOT_EXCEPTION",
            **_exception_evidence(error),
        },
    }
    return {**unsigned, "record_root": _record_root(_EXACT_RECORD_DOMAIN_V1, unsigned)}


def _invalid_pv_record_v1(
    exact_slot_value: Any, orientation_slot_value: Any, error: BaseException
) -> Dict[str, Any]:
    exact_slot = _json_copy(exact_slot_value, "invalid PV exact slot")
    orientation = _json_copy(orientation_slot_value, "invalid orientation slot")
    unsigned = {
        "record_version": ATLAS_EXACT_PV_RECORD_VERSION_V1,
        "record_kind": "EXACT_PV",
        "status": "INVALID",
        "orientation_slot_id": _sha256(
            orientation.get("slot_id"), "invalid orientation slot identity"
        ),
        "exact_slot_id": _sha256(
            exact_slot.get("slot_id"), "invalid PV exact slot identity"
        ),
        "transform_index": orientation.get("transform_index"),
        "transform": orientation.get("transform"),
        "representative_definition_hash": exact_slot.get(
            "representative_definition_hash"
        ),
        "representative_definition_byte_count": None,
        "transformed_definition_hash": orientation.get(
            "transformed_definition_hash"
        ),
        "transformed_definition_byte_count": None,
        "principal_variation_or_null": None,
        "principal_variation_plies_or_null": None,
        "value_for_a_or_null": None,
        "forced_result_or_null": None,
        "winner_or_null": None,
        "terminal_reason_or_null": None,
        "error_or_null": _exception_evidence(error),
    }
    return {**unsigned, "record_root": _record_root(_PV_RECORD_DOMAIN_V1, unsigned)}


def _transform_action(action: Action, board_size: int, transform: str) -> Action:
    if type(action) is not Action:
        raise TypeError("principal variation action must be an exact Action")
    origin = (
        transform_position(action.from_position, board_size, transform)
        if action.from_position is not None
        else None
    )
    target = transform_position(action.to_position, board_size, transform)
    return Action(kind=action.kind, from_position=origin, to_position=target)


def _solve_exact_slot_v1(
    slot_value: Any, definition_value: Any
) -> Tuple[Dict[str, Any], Any]:
    """Solve one supplied synthetic-or-frozen slot under its own fixed proof."""

    slot = _json_copy(slot_value, "exact slot")
    if type(slot) is not dict:
        raise TypeError("exact slot must be an exact object")
    slot_id = _sha256(slot.get("slot_id"), "exact slot identity")
    definition, _body, definition_entry = _sealed_definition(
        definition_value,
        slot.get("representative_definition_hash"),
        "exact definition",
    )
    max_states = _exact_int(slot.get("max_states"), "exact max states", 1)
    max_actions = _exact_int(
        slot.get("max_action_candidates_per_state"),
        "exact max action candidates per state",
        1,
    )
    if max_actions > ATLAS_ACTION_CANDIDATE_CAP_V1:
        raise ValueError("exact action-candidate cap exceeds the frozen protocol")
    max_state_actions = _exact_int(
        slot.get("max_state_action_candidate_evaluations"),
        "exact state/action-candidate cap",
        1,
    )
    if max_state_actions != max_states * max_actions:
        raise ValueError("exact state/action-candidate proof does not reconstruct")

    try:
        result = solve_game(definition, max_states=max_states)
    except SolveBudgetExceeded as error:
        unsigned = {
            "record_version": ATLAS_EXACT_RECORD_VERSION_V1,
            "record_kind": "EXACT",
            "slot_id": slot_id,
            "definition_hash": definition_hash(definition),
            "definition_byte_count": len(definition_entry),
            "status": "PROOF_CONTRADICTION",
            "max_states": max_states,
            "max_action_candidates_per_state": max_actions,
            "max_state_action_candidate_evaluations": max_state_actions,
            "result_or_null": None,
            "contradiction_or_null": {
                "kind": "EXACT_STATE_CAP_EXHAUSTED",
                "searched_states": error.searched_states,
                "max_states": error.max_states,
            },
        }
        return {**unsigned, "record_root": _record_root(_EXACT_RECORD_DOMAIN_V1, unsigned)}, None

    result_body = result.to_dict()
    if result.searched_states > max_states:
        raise AssertionError("exact solver exceeded the structural state cap")
    if len(result.principal_variation) > ATLAS_GAME_PLY_CAP_V1:
        raise AssertionError("exact principal variation exceeds the game ply cap")
    ceiling = result.searched_states * max_actions
    if ceiling > max_state_actions:
        raise AssertionError("exact state/action-candidate ceiling exceeds its proof")
    unsigned = {
        "record_version": ATLAS_EXACT_RECORD_VERSION_V1,
        "record_kind": "EXACT",
        "slot_id": slot_id,
        "definition_hash": definition_hash(definition),
        "definition_byte_count": len(definition_entry),
        "status": "COMPLETE",
        "max_states": max_states,
        "max_action_candidates_per_state": max_actions,
        "max_state_action_candidate_evaluations": max_state_actions,
        "result_or_null": result_body,
        "contradiction_or_null": None,
    }
    record = {**unsigned, "record_root": _record_root(_EXACT_RECORD_DOMAIN_V1, unsigned)}
    return record, result


def _replay_orientation_pv_v1(
    exact_slot_value: Any,
    orientation_slot_value: Any,
    representative_definition_value: Any,
    orientation_definition_value: Any,
    solve_result: Any,
) -> Dict[str, Any]:
    """Transform and replay one complete exact PV; never solve an orientation."""

    exact_slot = _json_copy(exact_slot_value, "exact slot")
    orientation = _json_copy(orientation_slot_value, "orientation slot")
    if type(exact_slot) is not dict or type(orientation) is not dict:
        raise TypeError("exact and orientation slots must be exact objects")
    exact_slot_id = _sha256(exact_slot.get("slot_id"), "exact slot identity")
    if orientation.get("exact_slot_id") != exact_slot_id:
        raise ValueError("orientation slot is not attached to the exact slot")
    orientation_slot_id = _sha256(
        orientation.get("slot_id"), "orientation slot identity"
    )
    transform_index = _exact_int(
        orientation.get("transform_index"), "orientation transform index"
    )
    if transform_index >= len(ATLAS_D4_TRANSFORMS_V1):
        raise ValueError("orientation transform index is outside the frozen D4 order")
    transform = orientation.get("transform")
    if (
        tuple(D4_TRANSFORMS) != tuple(ATLAS_D4_TRANSFORMS_V1)
        or transform != ATLAS_D4_TRANSFORMS_V1[transform_index]
    ):
        raise ValueError("orientation transform differs from the frozen D4 order")

    representative, _representative_body, representative_entry = _sealed_definition(
        representative_definition_value,
        exact_slot.get("representative_definition_hash"),
        "representative definition",
    )
    transformed, transformed_body, transformed_entry = _sealed_definition(
        orientation_definition_value,
        orientation.get("transformed_definition_hash"),
        "orientation definition",
    )
    expected_transformed = transform_definition(representative, transform)
    if canonical_json_bytes(expected_transformed.to_dict()) != transformed_entry:
        raise ValueError("orientation definition is not the declared D4 transform")

    if solve_result is None:
        raise ValueError("PV replay requires a complete exact result")
    transformed_actions = tuple(
        _transform_action(action, representative.board_size, transform)
        for action in solve_result.principal_variation
    )
    state = initial_state(transformed)
    for action in transformed_actions:
        if state.terminal:
            raise ValueError("transformed PV continues after terminal state")
        available = legal_actions(transformed, state)
        if len(available) > ATLAS_ACTION_CANDIDATE_CAP_V1:
            raise AssertionError("PV replay exceeds the frozen legal-action cap")
        if action not in available:
            raise ValueError("transformed PV contains an illegal action")
        state = apply_action(transformed, state, action)
    if not state.terminal or state.outcome is None:
        raise ValueError("transformed PV does not reach a terminal state")
    winner = state.outcome.winner.value if state.outcome.winner is not None else None
    expected_winner = (
        Player.A.value
        if solve_result.value_for_a == 1
        else Player.B.value
        if solve_result.value_for_a == -1
        else None
    )
    if (
        winner != expected_winner
        or state.outcome.reason != solve_result.terminal_reason
        or state.ply != len(transformed_actions)
    ):
        raise ValueError("transformed PV terminal evidence differs from the exact result")
    unsigned = {
        "record_version": ATLAS_EXACT_PV_RECORD_VERSION_V1,
        "record_kind": "EXACT_PV",
        "status": "VALID",
        "orientation_slot_id": orientation_slot_id,
        "exact_slot_id": exact_slot_id,
        "transform_index": transform_index,
        "transform": transform,
        "representative_definition_hash": definition_hash(representative),
        "representative_definition_byte_count": len(representative_entry),
        "transformed_definition_hash": definition_hash(transformed),
        "transformed_definition_byte_count": len(transformed_entry),
        "principal_variation_or_null": [
            action.to_dict() for action in transformed_actions
        ],
        "principal_variation_plies_or_null": len(transformed_actions),
        "value_for_a_or_null": solve_result.value_for_a,
        "forced_result_or_null": solve_result.forced_result,
        "winner_or_null": winner,
        "terminal_reason_or_null": state.outcome.reason,
        "error_or_null": None,
    }
    # Keep the detached body live only long enough to catch a hostile mutation.
    if canonical_json_bytes(transformed_body) != transformed_entry:
        raise ValueError("orientation definition changed during PV replay")
    return {**unsigned, "record_root": _record_root(_PV_RECORD_DOMAIN_V1, unsigned)}


def _validate_exact_stage_cardinality_v1(
    exact_records: Sequence[Mapping[str, Any]],
    pv_records: Sequence[Mapping[str, Any]],
) -> None:
    if len(exact_records) != ATLAS_DEVELOPMENT_DEFINITION_COUNT_V1:
        raise ValueError("exact stage did not account for all 288 exact slots")
    if len(pv_records) != ATLAS_DEFINITION_ORIENTATION_COUNT_V1:
        raise ValueError("exact stage did not account for all 2,304 PV slots")
    if any(record.get("status") != "COMPLETE" for record in exact_records):
        raise ValueError("exact stage contains a non-complete exact slot")
    if any(record.get("status") != "VALID" for record in pv_records):
        raise ValueError("exact stage contains a non-valid PV replay")


def _exact_ledger_specs_v1(protocol_value: Any) -> Tuple[LedgerSpec, LedgerSpec]:
    exact_ids = tuple(
        slot["slot_id"]
        for slot in iter_frozen_atlas_exact_schedule_from_protocol_v1(protocol_value)
    )
    pv_ids = tuple(
        slot["slot_id"]
        for slot in iter_frozen_atlas_orientation_schedule_from_protocol_v1(
            protocol_value
        )
    )
    return (
        LedgerSpec(
            phase_id=_EXACT_PHASE_ID_V1,
            ordered_slot_ids=exact_ids,
            allowed_result_statuses=(
                "COMPLETE",
                "INVALID",
                "PROOF_CONTRADICTION",
            ),
            interrupted_status="INCOMPLETE",
            unobserved_status="NOT_RUN",
        ),
        LedgerSpec(
            phase_id=_PV_PHASE_ID_V1,
            ordered_slot_ids=pv_ids,
            allowed_result_statuses=("VALID", "INVALID", "PROOF_CONTRADICTION"),
            interrupted_status="INCOMPLETE",
            unobserved_status="NOT_RUN",
        ),
    )


def _execute_exact_journals_v1(
    store: ImmutableEvidenceStore,
    contract: StageContract,
    manifest_value: Any,
    protocol_value: Any,
) -> Dict[str, Any]:
    if contract.stage_id != ATLAS_EXACT_STAGE_ID_V1:
        raise ValueError("exact compute received another stage contract")
    exact_rows = iter_joined_atlas_exact_definitions_v1(
        manifest_value, protocol_value
    )
    orientation_rows = iter_joined_atlas_orientation_definitions_v1(
        manifest_value, protocol_value
    )
    exact_counts = {
        "COMPLETE": 0,
        "INVALID": 0,
        "PROOF_CONTRADICTION": 0,
    }
    pv_counts = {"VALID": 0, "INVALID": 0, "PROOF_CONTRADICTION": 0}
    searched_states = 0
    exact_result_count = 0
    pv_result_count = 0
    for exact_index, joined_exact in enumerate(exact_rows):
        slot = joined_exact["slot"]
        definition_body = joined_exact["definition"]
        if slot.get("definition_index") != exact_index:
            raise ValueError("joined exact schedule order drifted")
        store.publish_journal_start(
            contract.stage_protocol_id,
            _EXACT_PHASE_ID_V1,
            exact_index,
            slot["slot_id"],
        )
        try:
            exact_record, solve_result = _solve_exact_slot_v1(slot, definition_body)
        except Exception as error:
            exact_record = _invalid_exact_record_v1(slot, error)
            solve_result = None
        store.publish_journal_result(
            contract.stage_protocol_id,
            _EXACT_PHASE_ID_V1,
            exact_index,
            slot["slot_id"],
            exact_record["status"],
            exact_record,
        )
        exact_counts[exact_record["status"]] += 1
        exact_result_count += 1
        if exact_record["status"] == "COMPLETE":
            searched_states += exact_record["result_or_null"]["searched_states"]

        attached_orientations = []
        for offset in range(len(ATLAS_D4_TRANSFORMS_V1)):
            try:
                joined_orientation = next(orientation_rows)
            except StopIteration as error:
                raise ValueError("orientation schedule ended before the exact schedule") from error
            orientation = joined_orientation["slot"]
            if (
                orientation.get("exact_slot_id") != slot["slot_id"]
                or orientation.get("transform_index") != offset
            ):
                raise ValueError("joined orientation schedule order drifted")
            attached_orientations.append(joined_orientation)
        if solve_result is None:
            continue
        for joined_orientation in attached_orientations:
            orientation = joined_orientation["slot"]
            pv_index = orientation["orientation_slot_index"]
            store.publish_journal_start(
                contract.stage_protocol_id,
                _PV_PHASE_ID_V1,
                pv_index,
                orientation["slot_id"],
            )
            try:
                pv_record = _replay_orientation_pv_v1(
                    slot,
                    orientation,
                    definition_body,
                    joined_orientation["definition"],
                    solve_result,
                )
            except Exception as error:
                pv_record = _invalid_pv_record_v1(slot, orientation, error)
            store.publish_journal_result(
                contract.stage_protocol_id,
                _PV_PHASE_ID_V1,
                pv_index,
                orientation["slot_id"],
                pv_record["status"],
                pv_record,
            )
            pv_counts[pv_record["status"]] += 1
            pv_result_count += 1
    try:
        next(orientation_rows)
    except StopIteration:
        pass
    else:
        raise ValueError("orientation schedule continues after the exact schedule")
    if exact_result_count != ATLAS_DEVELOPMENT_DEFINITION_COUNT_V1:
        raise ValueError("exact compute did not traverse all 288 exact slots")
    summary = {
        "summary_version": 1,
        "stage_id": ATLAS_EXACT_STAGE_ID_V1,
        "exact_result_count": exact_result_count,
        "pv_result_count": pv_result_count,
        "exact_status_counts": exact_counts,
        "pv_status_counts": pv_counts,
        "searched_states_total": searched_states,
    }
    return {
        **summary,
        "summary_root": domain_identity(_EXACT_STAGE_SUMMARY_DOMAIN_V1, summary),
    }


def _prerequisites_pass_v1(contract: StageContract, parent_seals: Sequence[Any]) -> bool:
    if len(parent_seals) != len(contract.required_parent_terminal_predicates):
        raise ValueError("exact parent terminal count drifted")
    for (stage_id, predicate), seal in zip(
        contract.required_parent_terminal_predicates, parent_seals
    ):
        if seal["payload"]["stage_id"] != stage_id:
            raise ValueError("exact parent terminal order drifted")
        if predicate == "COMPLETED_VALID":
            if seal["payload"]["lifecycle"] != "COMPLETED":
                return False
        elif predicate != "TERMINAL_SEAL_PRESENT":
            raise ValueError("exact parent predicate is unknown")
    return True


def _failure_value(error: BaseException) -> Dict[str, Any]:
    return {
        "kind": "EXACT_STAGE_EXCEPTION",
        **_exception_evidence(error),
    }


def run_atlas_exact_stage_v1(repository: str) -> Dict[str, Any]:
    if type(repository) is not str or not repository:
        raise ValueError("repository must be a nonempty exact string")
    repository_path = Path(repository).resolve()
    evidence_root = repository_path / _EVIDENCE_ROOT_RELATIVE_V1
    with ImmutableEvidenceStore(evidence_root) as store:
        with store.stage_lock(ATLAS_EXACT_STAGE_PROTOCOL_ID_V1):
            inputs = read_authenticated_stage_inputs(store, ATLAS_EXACT_STAGE_ID_V1)
            if inputs.contract.stage_protocol_id != ATLAS_EXACT_STAGE_PROTOCOL_ID_V1:
                raise ValueError("exact stage protocol identity drifted")
            ledger_specs = _exact_ledger_specs_v1(inputs.protocol)
            if not _prerequisites_pass_v1(
                inputs.contract, inputs.ordered_parent_terminal_seals
            ):
                terminal = block_stage(
                    store,
                    repository_path,
                    inputs.contract,
                    inputs.production_closure,
                    inputs.ordered_parent_terminal_seals,
                    inputs.experiment_plan_bytes,
                    ledger_specs,
                )
                return {
                    "lifecycle": "BLOCKED",
                    "stage_id": ATLAS_EXACT_STAGE_ID_V1,
                    "terminal_seal": terminal["identity"],
                }
            begin_stage(
                store,
                repository_path,
                inputs.contract,
                inputs.production_closure,
                inputs.ordered_parent_terminal_seals,
                inputs.experiment_plan_bytes,
                ledger_specs,
            )
            try:
                summary = _execute_exact_journals_v1(
                    store,
                    inputs.contract,
                    inputs.detached_manifest,
                    inputs.protocol,
                )
                if (
                    summary["exact_result_count"]
                    != ATLAS_DEVELOPMENT_DEFINITION_COUNT_V1
                    or summary["pv_result_count"]
                    != ATLAS_DEFINITION_ORIENTATION_COUNT_V1
                    or summary["exact_status_counts"]["COMPLETE"]
                    != ATLAS_DEVELOPMENT_DEFINITION_COUNT_V1
                    or summary["pv_status_counts"]["VALID"]
                    != ATLAS_DEFINITION_ORIENTATION_COUNT_V1
                ):
                    raise ValueError("exact stage completion gate was not met")
                refs = publish_stage_completion_evidence(
                    store, inputs.contract, ledger_specs
                )
            except Exception as error:
                terminal = seal_failed_stage(
                    store,
                    inputs.contract,
                    _failure_value(error),
                    ledger_specs,
                )
                return {
                    "lifecycle": "FAILED",
                    "stage_id": ATLAS_EXACT_STAGE_ID_V1,
                    "terminal_seal": terminal["identity"],
                }
            try:
                terminal = seal_completed_stage(
                    store,
                    repository_path,
                    inputs.contract,
                    inputs.production_closure,
                    inputs.experiment_plan_bytes,
                    summary,
                    refs,
                )
            except Exception as error:
                if store.artifact_exists(
                    ATLAS_EXACT_STAGE_PROTOCOL_ID_V1, "completed"
                ):
                    raise
                terminal = seal_failed_stage(
                    store,
                    inputs.contract,
                    _failure_value(error),
                    ledger_specs,
                )
                return {
                    "lifecycle": "FAILED",
                    "stage_id": ATLAS_EXACT_STAGE_ID_V1,
                    "terminal_seal": terminal["identity"],
                }
            return {
                "lifecycle": "COMPLETED",
                "stage_id": ATLAS_EXACT_STAGE_ID_V1,
                "summary": summary,
                "terminal_seal": terminal["identity"],
            }


def recover_atlas_exact_stage_v1(repository: str) -> Dict[str, Any]:
    if type(repository) is not str or not repository:
        raise ValueError("repository must be a nonempty exact string")
    repository_path = Path(repository).resolve()
    evidence_root = repository_path / _EVIDENCE_ROOT_RELATIVE_V1
    with ImmutableEvidenceStore(evidence_root) as store:
        inputs = read_authenticated_stage_inputs(store, ATLAS_EXACT_STAGE_ID_V1)
        result = recover_stage(
            store,
            inputs.contract,
            _exact_ledger_specs_v1(inputs.protocol),
            repository=repository_path,
        )
        return {
            "action": result.action,
            "lifecycle": result.lifecycle,
            "stage_id": ATLAS_EXACT_STAGE_ID_V1,
            "terminal_seal_or_null": result.terminal_identity,
        }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m parity_forge.atlas_exact_stage")
    parser.add_argument("command", choices=("run", "recover"))
    parser.add_argument("--repository", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _build_parser().parse_args(argv)
    if arguments.command == "run":
        result = run_atlas_exact_stage_v1(arguments.repository)
    else:
        result = recover_atlas_exact_stage_v1(arguments.repository)
    print(canonical_json_bytes(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = (
    "ATLAS_EXACT_PV_RECORD_VERSION_V1",
    "ATLAS_EXACT_RECORD_VERSION_V1",
    "ATLAS_EXACT_STAGE_ID_V1",
    "ATLAS_EXACT_STAGE_PROTOCOL_ID_V1",
    "recover_atlas_exact_stage_v1",
    "run_atlas_exact_stage_v1",
)
