"""Replay-only telemetry stage for the frozen Plan-0013 atlas.

Only sampled records already classified COMPLETE are replayed.  This module
does not import an agent, solver, play loop, selector, or another stage module.
The repository entrypoint authenticates parent ledgers and journals before the
replay-only core sees a detached definition, slot, trace, and record.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .agency import derive_replay_telemetry_v1, validate_replay_telemetry_v1
from .atlas_evidence import (
    BodyRef,
    ImmutableEvidenceStore,
    LedgerSpec,
    StageContract,
    StageResultRefs,
    begin_stage,
    block_stage,
    canonical_body_ref,
    canonical_json_bytes,
    domain_identity,
    extract_stage_contract,
    publish_stage_completion_evidence,
    read_authenticated_stage_inputs,
    read_stage_completion_evidence,
    recover_stage,
    seal_completed_stage,
    seal_failed_stage,
)
from .atlas_protocol import (
    ATLAS_ACTION_CANDIDATE_CAP_V1,
    ATLAS_GAME_PLY_CAP_V1,
    ATLAS_SAMPLED_GAME_COUNT_V1,
    iter_frozen_atlas_game_schedule_from_protocol_v1,
)
from .atlas_stage_data import (
    ATLAS_DEPTH1_STRENGTH_ID_V1,
    ATLAS_RANDOM_STRENGTH_ID_V1,
    iter_joined_atlas_game_definitions_v1,
    reconcile_atlas_sampled_status_ledger_v1,
    validate_complete_atlas_trace_v1,
)


ATLAS_TELEMETRY_STAGE_ID_V1 = "REPLAY_TELEMETRY_COMPLETE_TRACES_ONLY"
ATLAS_TELEMETRY_STAGE_PROTOCOL_ID_V1 = (
    "plan0013-atlas-development-telemetry-v1"
)
ATLAS_TELEMETRY_RECORD_VERSION_V1 = 1

_TELEMETRY_PHASE_ID_V1 = "telemetry"
_TELEMETRY_STAGE_SUMMARY_DOMAIN_V1 = (
    b"parity-forge:plan0013:telemetry-stage-summary:v1\0"
)
_EVIDENCE_ROOT_RELATIVE_V1 = (
    "experiments/runs/plan0013-atlas-development-evidence-v2"
)
_RANDOM_PARENT_STAGE_ID_V1 = "RANDOM_ALL_18432_GAMES"
_RANDOM_PARENT_STAGE_PROTOCOL_ID_V1 = "plan0013-atlas-development-random-v1"
_RANDOM_PARENT_PHASE_ID_V1 = "random"
_DEPTH1_PARENT_STAGE_ID_V1 = "TERMINAL_DEPTH1_ALL_18432_GAMES"
_DEPTH1_PARENT_STAGE_PROTOCOL_ID_V1 = (
    "plan0013-atlas-development-terminal-depth1-v1"
)
_DEPTH1_PARENT_PHASE_ID_V1 = "depth1"

_TELEMETRY_RECORD_DOMAIN_V1 = (
    b"parity-forge:plan0013:replay-telemetry-record:v1\0"
)
_RANDOM_RECORD_DOMAIN_V1 = b"parity-forge:plan0013:random-game-record:v1\0"
_DEPTH1_RECORD_DOMAIN_V1 = b"parity-forge:plan0013:depth1-game-record:v1\0"

_TELEMETRY_RECORD_FIELDS = frozenset(
    (
        "record_version",
        "record_kind",
        "status",
        "game_slot_id",
        "sampled_record_root",
        "strength_identity",
        "definition_hash",
        "trace_plies_or_null",
        "telemetry_or_null",
        "contradiction_or_null",
        "error_or_null",
        "record_root",
    )
)
_RANDOM_RECORD_FIELDS = frozenset(
    (
        "record_version",
        "record_kind",
        "strength_identity",
        "status",
        "game_slot_id",
        "profile_slot_id",
        "ordered_role_slot_ids",
        "matched_start_block_id",
        "seed_index",
        "seed",
        "definition_hash",
        "definition_byte_count",
        "agent_a",
        "agent_b",
        "rng_scope",
        "rng_stream",
        "decisions",
        "node_ledger_or_null",
        "complete_trace_or_null",
        "censored_prefix_or_null",
        "record_root",
    )
)
_DEPTH1_RECORD_FIELDS = _RANDOM_RECORD_FIELDS.difference(("decisions",))
_STRUCTURAL_CAPS = {
    "replayed_actions": ATLAS_GAME_PLY_CAP_V1,
    "decision_count": ATLAS_GAME_PLY_CAP_V1,
    "state_observation_count": ATLAS_GAME_PLY_CAP_V1 + 1,
    "successor_evaluations": (
        ATLAS_GAME_PLY_CAP_V1 * ATLAS_ACTION_CANDIDATE_CAP_V1
    ),
    "next_action_observations": (
        ATLAS_GAME_PLY_CAP_V1
        * ATLAS_ACTION_CANDIDATE_CAP_V1
        * ATLAS_ACTION_CANDIDATE_CAP_V1
    ),
}


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


def _record_root(domain: bytes, record: Mapping[str, Any]) -> str:
    unsigned = dict(record)
    supplied = unsigned.pop("record_root", None)
    expected = domain_identity(domain, unsigned)
    if supplied is not None and supplied != expected:
        raise ValueError("raw record root does not reconstruct")
    return expected


def _sampled_record_domain(strength_identity: str) -> bytes:
    if strength_identity == ATLAS_RANDOM_STRENGTH_ID_V1:
        return _RANDOM_RECORD_DOMAIN_V1
    if strength_identity == ATLAS_DEPTH1_STRENGTH_ID_V1:
        return _DEPTH1_RECORD_DOMAIN_V1
    raise ValueError("sampled record has an unknown strength identity")


def _validate_sampled_record_v1(
    game_slot_value: Any, sampled_record_value: Any
) -> Dict[str, Any]:
    game = _json_copy(game_slot_value, "telemetry game slot")
    sampled = _json_copy(sampled_record_value, "sampled game record")
    if type(game) is not dict or type(sampled) is not dict:
        raise TypeError("game slot and sampled record must be exact objects")
    strength = game.get("strength")
    if type(strength) is not dict:
        raise ValueError("game slot strength is missing")
    identity = strength.get("identity")
    expected_fields = (
        _RANDOM_RECORD_FIELDS
        if identity == ATLAS_RANDOM_STRENGTH_ID_V1
        else _DEPTH1_RECORD_FIELDS
        if identity == ATLAS_DEPTH1_STRENGTH_ID_V1
        else None
    )
    if expected_fields is None or set(sampled) != expected_fields:
        raise ValueError("sampled game record fields or strength drifted")
    if (
        sampled["record_version"] != 1
        or sampled["record_kind"] != "SAMPLED_GAME"
        or sampled["strength_identity"] != identity
        or sampled["game_slot_id"] != game.get("slot_id")
        or sampled["profile_slot_id"] != game.get("profile_slot_id")
        or sampled["ordered_role_slot_ids"] != game.get("ordered_role_slot_ids")
        or sampled["matched_start_block_id"] != game.get("matched_start_block_id")
        or sampled["seed_index"] != game.get("seed_index")
        or sampled["seed"] != game.get("seed")
        or sampled["definition_hash"] != game.get("transformed_definition_hash")
        or sampled["agent_a"] != identity
        or sampled["agent_b"] != identity
        or sampled["rng_scope"] != game.get("rng_scope")
        or sampled["rng_stream"] != game.get("rng_stream")
    ):
        raise ValueError("sampled game record differs from its protocol slot")
    allowed_statuses = (
        ("COMPLETE", "INVALID")
        if identity == ATLAS_RANDOM_STRENGTH_ID_V1
        else ("COMPLETE", "INCOMPLETE", "INVALID")
    )
    if sampled["status"] not in allowed_statuses:
        raise ValueError("sampled game record has an unknown status")
    if sampled["status"] in ("COMPLETE", "INCOMPLETE"):
        _exact_int(
            sampled["definition_byte_count"], "sampled definition byte count", 1
        )
    elif sampled["definition_byte_count"] is not None:
        raise ValueError("invalid sampled record must not claim definition bytes")
    if sampled["status"] == "COMPLETE":
        if (
            type(sampled["complete_trace_or_null"]) is not dict
            or sampled["censored_prefix_or_null"] is not None
        ):
            raise ValueError("COMPLETE sampled record lacks a complete trace")
    elif sampled["complete_trace_or_null"] is not None:
        raise ValueError("noncomplete sampled record claims a complete trace")
    if identity == ATLAS_RANDOM_STRENGTH_ID_V1:
        if (
            type(sampled["decisions"]) is not list
            or sampled["node_ledger_or_null"] is not None
        ):
            raise ValueError("random sampled audit fields drifted")
    elif sampled["status"] in ("COMPLETE", "INCOMPLETE") and type(
        sampled["node_ledger_or_null"]
    ) is not dict:
        raise ValueError("depth-1 sampled record lacks its node ledger")
    _sha256(sampled["record_root"], "sampled record root")
    _record_root(_sampled_record_domain(identity), sampled)
    return sampled


def _telemetry_record(
    game: Mapping[str, Any],
    sampled: Mapping[str, Any],
    *,
    status: str,
    trace_plies: Optional[int],
    telemetry: Optional[Mapping[str, Any]],
    contradiction: Optional[Mapping[str, Any]],
    error: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    unsigned = {
        "record_version": ATLAS_TELEMETRY_RECORD_VERSION_V1,
        "record_kind": "REPLAY_TELEMETRY",
        "status": status,
        "game_slot_id": game["slot_id"],
        "sampled_record_root": sampled["record_root"],
        "strength_identity": sampled["strength_identity"],
        "definition_hash": game["transformed_definition_hash"],
        "trace_plies_or_null": trace_plies,
        "telemetry_or_null": telemetry,
        "contradiction_or_null": contradiction,
        "error_or_null": error,
    }
    return {
        **unsigned,
        "record_root": domain_identity(_TELEMETRY_RECORD_DOMAIN_V1, unsigned),
    }


def _error(kind: str, detail: str) -> Dict[str, str]:
    return {"kind": kind, "detail": detail}


def _proof_from_error(error: BaseException) -> bool:
    message = str(error)
    return any(
        marker in message
        for marker in (
            "frozen game ply cap",
            "frozen legal-action cap",
            "telemetry-v1 horizon",
            "counterfactual successor cap",
            "next-action observation cap",
        )
    )


def _work_contradiction(telemetry: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    work = telemetry.get("work")
    decisions = telemetry.get("decisions")
    if type(work) is not dict or type(decisions) is not list:
        return {
            "kind": "TELEMETRY_SCHEMA_DRIFT",
            "field": "work-or-decisions",
        }
    for field, maximum in _STRUCTURAL_CAPS.items():
        observed = work.get(field)
        if type(observed) is not int or observed < 0:
            return {
                "kind": "TELEMETRY_SCHEMA_DRIFT",
                "field": field,
            }
        if observed > maximum:
            return {
                "kind": "TELEMETRY_STRUCTURAL_CAP_EXCEEDED",
                "field": field,
                "observed": observed,
                "maximum": maximum,
            }
    for index, decision in enumerate(decisions):
        if type(decision) is not dict or type(decision.get("legal_count")) is not int:
            return {
                "kind": "TELEMETRY_SCHEMA_DRIFT",
                "field": "decisions[{}].legal_count".format(index),
            }
        if decision["legal_count"] > ATLAS_ACTION_CANDIDATE_CAP_V1:
            return {
                "kind": "TELEMETRY_STRUCTURAL_CAP_EXCEEDED",
                "field": "decisions[{}].legal_count".format(index),
                "observed": decision["legal_count"],
                "maximum": ATLAS_ACTION_CANDIDATE_CAP_V1,
            }
    return None


def derive_atlas_telemetry_record_v1(
    game_slot_value: Any,
    definition_value: Any,
    sampled_record_value: Any,
) -> Dict[str, Any]:
    """Derive one fixed telemetry record from one COMPLETE sampled trace."""

    game = _json_copy(game_slot_value, "telemetry game slot")
    definition = _json_copy(definition_value, "telemetry definition")
    sampled = _validate_sampled_record_v1(game, sampled_record_value)
    if sampled["status"] != "COMPLETE":
        raise ValueError("telemetry derives only from sampled COMPLETE records")
    trace = sampled["complete_trace_or_null"]
    if type(trace) is not dict:
        return _telemetry_record(
            game,
            sampled,
            status="INVALID",
            trace_plies=None,
            telemetry=None,
            contradiction=None,
            error=_error(
                "INVALID_COMPLETE_TRACE",
                "sampled COMPLETE record lacks a complete trace",
            ),
        )
    trace_plies = trace.get("plies") if type(trace.get("plies")) is int else None
    try:
        validated_trace = validate_complete_atlas_trace_v1(definition, trace)
    except (TypeError, ValueError) as failure:
        if _proof_from_error(failure):
            return _telemetry_record(
                game,
                sampled,
                status="PROOF_CONTRADICTION",
                trace_plies=trace_plies,
                telemetry=None,
                contradiction={
                    "kind": "TRACE_STRUCTURAL_CAP_EXCEEDED",
                    "detail": str(failure),
                },
                error=None,
            )
        return _telemetry_record(
            game,
            sampled,
            status="INVALID",
            trace_plies=trace_plies,
            telemetry=None,
            contradiction=None,
            error=_error("INVALID_COMPLETE_TRACE", str(failure)),
        )
    try:
        telemetry_value = derive_replay_telemetry_v1(
            definition, validated_trace["actions"]
        ).to_dict()
        rebuilt = validate_replay_telemetry_v1(definition, telemetry_value).to_dict()
    except (TypeError, ValueError) as failure:
        if _proof_from_error(failure):
            return _telemetry_record(
                game,
                sampled,
                status="PROOF_CONTRADICTION",
                trace_plies=validated_trace["plies"],
                telemetry=None,
                contradiction={
                    "kind": "TELEMETRY_STRUCTURAL_CAP_EXCEEDED",
                    "detail": str(failure),
                },
                error=None,
            )
        return _telemetry_record(
            game,
            sampled,
            status="INVALID",
            trace_plies=validated_trace["plies"],
            telemetry=None,
            contradiction=None,
            error=_error("TELEMETRY_RECONSTRUCTION_FAILED", str(failure)),
        )
    contradiction = _work_contradiction(rebuilt)
    if contradiction is not None:
        status = (
            "PROOF_CONTRADICTION"
            if contradiction["kind"] == "TELEMETRY_STRUCTURAL_CAP_EXCEEDED"
            else "INVALID"
        )
        return _telemetry_record(
            game,
            sampled,
            status=status,
            trace_plies=validated_trace["plies"],
            telemetry=None,
            contradiction=contradiction if status == "PROOF_CONTRADICTION" else None,
            error=contradiction if status == "INVALID" else None,
        )
    terminal = rebuilt.get("terminal")
    if terminal != {
        "ply": validated_trace["plies"],
        "winner": validated_trace["winner"],
        "reason": validated_trace["terminal_reason"],
    }:
        return _telemetry_record(
            game,
            sampled,
            status="INVALID",
            trace_plies=validated_trace["plies"],
            telemetry=None,
            contradiction=None,
            error=_error(
                "TELEMETRY_TERMINAL_MISMATCH",
                "replay telemetry terminal differs from the sampled trace",
            ),
        )
    return _telemetry_record(
        game,
        sampled,
        status="VALIDATED",
        trace_plies=validated_trace["plies"],
        telemetry=rebuilt,
        contradiction=None,
        error=None,
    )


def validate_atlas_telemetry_record_v1(
    game_slot_value: Any,
    definition_value: Any,
    sampled_record_value: Any,
    stored_value: Any,
) -> Dict[str, Any]:
    stored_entry = canonical_json_bytes(stored_value)
    stored = json.loads(stored_entry.decode("utf-8"))
    if type(stored) is not dict or set(stored) != _TELEMETRY_RECORD_FIELDS:
        raise ValueError("stored telemetry record fields drifted")
    _sha256(stored["record_root"], "telemetry record root")
    _record_root(_TELEMETRY_RECORD_DOMAIN_V1, stored)
    rebuilt = derive_atlas_telemetry_record_v1(
        game_slot_value, definition_value, sampled_record_value
    )
    if canonical_json_bytes(rebuilt) != stored_entry:
        raise ValueError("stored telemetry record does not reconstruct")
    if canonical_json_bytes(stored_value) != stored_entry:
        raise ValueError("stored telemetry record changed during validation")
    return _json_copy(rebuilt, "validated telemetry record")


def _body_ref(value: Any, label: str) -> BodyRef:
    if type(value) is not dict or set(value) != {"byte_count", "sha256"}:
        raise ValueError("{} must be an exact body reference".format(label))
    return BodyRef(
        sha256=_sha256(value["sha256"], "{} SHA-256".format(label)),
        byte_count=_exact_int(value["byte_count"], "{} byte count".format(label)),
    )


def _validate_record_catalog_v1(
    ledger_set: Mapping[str, Any], catalog: Mapping[str, Any]
) -> None:
    expected = []
    for ledger in ledger_set.get("ledgers", ()):
        for slot in ledger.get("slots", ()):
            if slot.get("result_ref_or_null") is not None:
                expected.append(
                    {
                        "phase_id": ledger.get("phase_id"),
                        "result_ref": slot["result_ref_or_null"],
                        "slot_id": slot.get("slot_id"),
                        "slot_index": slot.get("slot_index"),
                    }
                )
    if (
        type(catalog) is not dict
        or catalog.get("ordered_record_count") != len(expected)
        or catalog.get("ordered_records") != expected
    ):
        raise ValueError("sampled parent record catalog differs from its ledger")


def _parent_ledger_set_v1(
    store: ImmutableEvidenceStore,
    protocol_value: Any,
    parent_terminal_seal: Mapping[str, Any],
    expected_stage_id: str,
    expected_stage_protocol_id: str,
) -> Tuple[Optional[Dict[str, Any]], str, StageContract]:
    """Read one already-authenticated parent's sealed full/partial ledger."""

    contract = extract_stage_contract(protocol_value, expected_stage_id)
    if contract.stage_protocol_id != expected_stage_protocol_id:
        raise ValueError("sampled parent stage protocol identity drifted")
    payload = (
        parent_terminal_seal.get("payload")
        if type(parent_terminal_seal) is dict
        else None
    )
    if (
        type(payload) is not dict
        or payload.get("stage_id") != expected_stage_id
        or payload.get("stage_protocol_id") != expected_stage_protocol_id
    ):
        raise ValueError("sampled parent terminal coordinates drifted")
    lifecycle = payload.get("lifecycle")
    if lifecycle == "BLOCKED":
        return None, lifecycle, contract
    if lifecycle == "COMPLETED":
        completed = store.read_json(expected_stage_protocol_id, "completed")
        if canonical_body_ref(completed).sha256 != payload.get(
            "completed_root_or_null"
        ):
            raise ValueError("sampled parent completed root differs from its seal")
        if type(completed) is not dict or set(completed) != {
            "artifact_type",
            "attempt_id",
            "reservation_id",
            "result",
            "stage_id",
            "stage_protocol_id",
        }:
            raise ValueError("sampled parent completed artifact fields drifted")
        result = completed["result"]
        if type(result) is not dict or set(result) != {
            "artifact_refs_or_null",
            "summary",
        }:
            raise ValueError("sampled parent completed result fields drifted")
        refs = result["artifact_refs_or_null"]
        if type(refs) is not dict or set(refs) != {
            "record_catalog",
            "status_ledger",
        }:
            raise ValueError("sampled parent completion refs drifted")
        expected_refs = StageResultRefs(
            status_ledger=_body_ref(refs["status_ledger"], "status ledger ref"),
            record_catalog=_body_ref(refs["record_catalog"], "record catalog ref"),
        )
        evidence = read_stage_completion_evidence(store, contract, expected_refs)
        _validate_record_catalog_v1(
            evidence["status_ledger"], evidence["record_catalog"]
        )
        return evidence["status_ledger"], lifecycle, contract
    if lifecycle in ("FAILED", "ORPHANED"):
        partial = store.read_json(expected_stage_protocol_id, "partial_ledger")
        if canonical_body_ref(partial).sha256 != payload.get(
            "partial_evidence_root_or_null"
        ):
            raise ValueError("sampled parent partial ledger differs from its seal")
        return _json_copy(partial, "sampled parent partial ledger"), lifecycle, contract
    raise ValueError("sampled parent terminal lifecycle is invalid")


def _validated_phase_rows_v1(
    store: ImmutableEvidenceStore,
    contract: StageContract,
    ledger_set_value: Any,
    phase_id: str,
    expected_slot_ids: Sequence[str],
    allowed_raw_statuses: Sequence[str],
    interrupted_status: str,
    unobserved_status: str,
) -> Tuple[List[Dict[str, Any]], List[str], List[Dict[str, Any]]]:
    """Authenticate a full evidence phase and return raw bodies plus starts."""

    ledger_set = _json_copy(ledger_set_value, "parent status ledger set")
    if type(ledger_set) is not dict or set(ledger_set) != {
        "artifact_type",
        "ledgers",
        "phase_ids",
        "stage_id",
        "stage_protocol_id",
    }:
        raise ValueError("parent status ledger set fields drifted")
    ledgers = ledger_set["ledgers"]
    phase_ids = ledger_set["phase_ids"]
    if (
        ledger_set["artifact_type"] != "ATLAS_FULL_STATUS_LEDGER_SET_V1"
        or ledger_set["stage_id"] != contract.stage_id
        or ledger_set["stage_protocol_id"] != contract.stage_protocol_id
        or type(ledgers) is not list
        or type(phase_ids) is not list
        or phase_ids != [ledger.get("phase_id") for ledger in ledgers]
        or len(set(phase_ids)) != len(phase_ids)
    ):
        raise ValueError("parent status ledger set binding drifted")
    matches = [ledger for ledger in ledgers if ledger.get("phase_id") == phase_id]
    if len(matches) != 1:
        raise ValueError("parent status ledger phase membership drifted")
    ledger = matches[0]
    if type(ledger) is not dict or set(ledger) != {
        "artifact_type",
        "phase_id",
        "slot_count",
        "slots",
        "stage_id",
        "stage_protocol_id",
        "status_counts",
    }:
        raise ValueError("parent phase ledger fields drifted")
    slots = ledger["slots"]
    if (
        ledger["artifact_type"] != "ATLAS_FULL_STATUS_LEDGER_V1"
        or ledger["stage_id"] != contract.stage_id
        or ledger["stage_protocol_id"] != contract.stage_protocol_id
        or ledger["slot_count"] != len(expected_slot_ids)
        or type(slots) is not list
        or len(slots) != len(expected_slot_ids)
    ):
        raise ValueError("parent phase ledger denominator or binding drifted")
    observed: List[Dict[str, Any]] = []
    started: List[str] = []
    raw_records: List[Dict[str, Any]] = []
    statuses: List[str] = []
    allowed_raw = set(allowed_raw_statuses)
    for index, (slot, expected_slot_id) in enumerate(zip(slots, expected_slot_ids)):
        if type(slot) is not dict or set(slot) != {
            "result_ref_or_null",
            "slot_id",
            "slot_index",
            "start_ref_or_null",
            "status",
        }:
            raise ValueError("parent phase slot fields drifted")
        if slot["slot_id"] != expected_slot_id or slot["slot_index"] != index:
            raise ValueError("parent phase slot order or identity drifted")
        status = slot["status"]
        statuses.append(status)
        start_ref_value = slot["start_ref_or_null"]
        result_ref_value = slot["result_ref_or_null"]
        if start_ref_value is not None:
            start_ref = _body_ref(start_ref_value, "parent journal start ref")
            start = store.read_journal_start(
                contract.stage_protocol_id, phase_id, index
            )
            if canonical_body_ref(start) != start_ref or start != {
                "artifact_type": "ATLAS_SLOT_START_V1",
                "phase_id": phase_id,
                "slot_id": expected_slot_id,
                "slot_index": index,
                "stage_protocol_id": contract.stage_protocol_id,
            }:
                raise ValueError("parent journal start does not authenticate")
            started.append(expected_slot_id)
        if result_ref_value is not None:
            if start_ref_value is None or status not in allowed_raw:
                raise ValueError("parent result row has invalid start/status semantics")
            result_ref = _body_ref(result_ref_value, "parent journal result ref")
            envelope = store.read_journal_result(
                contract.stage_protocol_id, phase_id, index
            )
            if canonical_body_ref(envelope) != result_ref:
                raise ValueError("parent journal result does not authenticate")
            if type(envelope) is not dict or set(envelope) != {
                "artifact_type",
                "phase_id",
                "result",
                "slot_id",
                "slot_index",
                "stage_protocol_id",
                "start_ref",
                "status",
            }:
                raise ValueError("parent journal result envelope fields drifted")
            if (
                envelope["artifact_type"] != "ATLAS_SLOT_RESULT_V1"
                or envelope["phase_id"] != phase_id
                or envelope["slot_id"] != expected_slot_id
                or envelope["slot_index"] != index
                or envelope["stage_protocol_id"] != contract.stage_protocol_id
                or envelope["status"] != status
                or envelope["start_ref"] != start_ref_value
                or type(envelope["result"]) is not dict
            ):
                raise ValueError("parent journal result coordinates drifted")
            raw = _json_copy(envelope["result"], "parent raw record")
            if (
                raw.get("game_slot_id") != expected_slot_id
                or raw.get("status") != status
            ):
                raise ValueError(
                    "sampled parent raw record differs from its journal slot"
                )
            root = _sha256(raw.get("record_root"), "parent raw record root")
            observed.append(
                {
                    "slot_id": expected_slot_id,
                    "status": status,
                    "record_root_or_null": root,
                }
            )
            raw_records.append(raw)
        elif start_ref_value is not None:
            if status != interrupted_status:
                raise ValueError("started parent row is not interrupted")
        elif status != unobserved_status:
            raise ValueError("unobserved parent row has an invalid status")
    if ledger["status_counts"] != dict(Counter(statuses)):
        raise ValueError("parent phase status counts do not reconstruct")
    return observed, started, raw_records


def _sampled_parent_data_v1(
    store: ImmutableEvidenceStore,
    protocol_value: Any,
    parent_terminal_seal: Mapping[str, Any],
    *,
    stage_id: str,
    stage_protocol_id: str,
    phase_id: str,
    strength_identity: str,
) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]:
    expected_ids = tuple(
        slot["slot_id"]
        for slot in iter_frozen_atlas_game_schedule_from_protocol_v1(protocol_value)
        if slot["strength"]["identity"] == strength_identity
    )
    ledger_set, lifecycle, contract = _parent_ledger_set_v1(
        store,
        protocol_value,
        parent_terminal_seal,
        stage_id,
        stage_protocol_id,
    )
    if lifecycle == "BLOCKED":
        return (
            reconcile_atlas_sampled_status_ledger_v1(
                protocol_value, strength_identity, [], [], blocked=True
            ),
            {},
        )
    if ledger_set.get("phase_ids") != [phase_id]:
        raise ValueError("sampled parent ledger contains an unexpected phase set")
    observed, started, raw_records = _validated_phase_rows_v1(
        store,
        contract,
        ledger_set,
        phase_id,
        expected_ids,
        ("COMPLETE", "INCOMPLETE", "INVALID", "PROOF_CONTRADICTION"),
        "INCOMPLETE",
        "NOT_RUN",
    )
    ledger = reconcile_atlas_sampled_status_ledger_v1(
        protocol_value, strength_identity, observed, started
    )
    for evidence, record in zip(observed, raw_records):
        if (
            record.get("game_slot_id") != evidence["slot_id"]
            or record.get("status") != evidence["status"]
            or record.get("record_root") != evidence["record_root_or_null"]
        ):
            raise ValueError("sampled parent raw record differs from its journal slot")
    raw_by_slot = {record["game_slot_id"]: record for record in raw_records}
    if len(raw_by_slot) != len(raw_records):
        raise ValueError("sampled parent raw records repeat a game slot")
    return ledger, raw_by_slot


def _telemetry_ledger_spec_v1(
    protocol_value: Any,
    random_ledger: Mapping[str, Any],
    depth1_ledger: Mapping[str, Any],
) -> LedgerSpec:
    statuses = {
        row["slot_id"]: row["status"]
        for row in random_ledger["rows"] + depth1_ledger["rows"]
    }
    ordered_ids = tuple(
        slot["slot_id"]
        for slot in iter_frozen_atlas_game_schedule_from_protocol_v1(protocol_value)
    )
    if len(ordered_ids) != ATLAS_SAMPLED_GAME_COUNT_V1 or set(statuses) != set(
        ordered_ids
    ):
        raise ValueError("sampled parent ledgers do not cover the telemetry schedule")
    preclassified = tuple(
        (index, "NOT_ADMISSIBLE")
        for index, slot_id in enumerate(ordered_ids)
        if statuses[slot_id] != "COMPLETE"
    )
    return LedgerSpec(
        phase_id=_TELEMETRY_PHASE_ID_V1,
        ordered_slot_ids=ordered_ids,
        allowed_result_statuses=(
            "VALIDATED",
            "INVALID",
            "PROOF_CONTRADICTION",
        ),
        interrupted_status="MISSING",
        unobserved_status="MISSING",
        preclassified_statuses=preclassified,
    )


def _execute_telemetry_journal_v1(
    store: ImmutableEvidenceStore,
    contract: StageContract,
    manifest_value: Any,
    protocol_value: Any,
    random_ledger: Mapping[str, Any],
    depth1_ledger: Mapping[str, Any],
    sampled_by_slot: Mapping[str, Mapping[str, Any]],
) -> Dict[str, Any]:
    if contract.stage_id != ATLAS_TELEMETRY_STAGE_ID_V1:
        raise ValueError("telemetry compute received another stage contract")
    rows = {
        row["slot_id"]: row
        for row in random_ledger["rows"] + depth1_ledger["rows"]
    }
    status_counts = {
        "VALIDATED": 0,
        "NOT_ADMISSIBLE": 0,
        "MISSING": 0,
        "INVALID": 0,
        "PROOF_CONTRADICTION": 0,
    }
    result_count = 0
    joined_count = 0
    for index, joined in enumerate(
        iter_joined_atlas_game_definitions_v1(manifest_value, protocol_value)
    ):
        joined_count += 1
        game = joined["slot"]
        row = rows[game["slot_id"]]
        if row["status"] != "COMPLETE":
            status_counts["NOT_ADMISSIBLE"] += 1
            continue
        sampled = sampled_by_slot.get(game["slot_id"])
        if sampled is None:
            raise ValueError("COMPLETE sampled slot lacks authenticated raw evidence")
        sampled = _validate_sampled_record_v1(game, sampled)
        store.publish_journal_start(
            contract.stage_protocol_id,
            _TELEMETRY_PHASE_ID_V1,
            index,
            game["slot_id"],
        )
        record = derive_atlas_telemetry_record_v1(
            game, joined["definition"], sampled
        )
        validate_atlas_telemetry_record_v1(
            game, joined["definition"], sampled, record
        )
        store.publish_journal_result(
            contract.stage_protocol_id,
            _TELEMETRY_PHASE_ID_V1,
            index,
            game["slot_id"],
            record["status"],
            record,
        )
        status_counts[record["status"]] += 1
        result_count += 1
    if joined_count != ATLAS_SAMPLED_GAME_COUNT_V1:
        raise ValueError("telemetry did not traverse all fixed game slots")
    if result_count + status_counts["NOT_ADMISSIBLE"] != joined_count:
        raise ValueError("telemetry did not account for every fixed game slot")
    summary = {
        "summary_version": 1,
        "stage_id": ATLAS_TELEMETRY_STAGE_ID_V1,
        "slot_count": joined_count,
        "result_count": result_count,
        "status_counts": status_counts,
    }
    return {
        **summary,
        "summary_root": domain_identity(
            _TELEMETRY_STAGE_SUMMARY_DOMAIN_V1, summary
        ),
    }


def _prerequisites_pass_v1(
    contract: StageContract, parent_seals: Sequence[Any]
) -> bool:
    if len(parent_seals) != len(contract.required_parent_terminal_predicates):
        raise ValueError("telemetry parent terminal count drifted")
    for (stage_id, predicate), seal in zip(
        contract.required_parent_terminal_predicates, parent_seals
    ):
        if seal["payload"]["stage_id"] != stage_id:
            raise ValueError("telemetry parent terminal order drifted")
        if predicate == "COMPLETED_VALID":
            if seal["payload"]["lifecycle"] != "COMPLETED":
                return False
        elif predicate != "TERMINAL_SEAL_PRESENT":
            raise ValueError("telemetry parent predicate is unknown")
    return True


def _failure_value(error: BaseException) -> Dict[str, Any]:
    return {
        "kind": "TELEMETRY_STAGE_EXCEPTION",
        "exception_module": type(error).__module__,
        "exception_type": type(error).__qualname__,
        "message": str(error),
    }


def _sampled_inputs_from_parents_v1(
    store: ImmutableEvidenceStore,
    protocol_value: Any,
    parent_seals: Sequence[Mapping[str, Any]],
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Dict[str, Any]]]:
    by_stage = {seal["payload"]["stage_id"]: seal for seal in parent_seals}
    random_ledger, random_records = _sampled_parent_data_v1(
        store,
        protocol_value,
        by_stage[_RANDOM_PARENT_STAGE_ID_V1],
        stage_id=_RANDOM_PARENT_STAGE_ID_V1,
        stage_protocol_id=_RANDOM_PARENT_STAGE_PROTOCOL_ID_V1,
        phase_id=_RANDOM_PARENT_PHASE_ID_V1,
        strength_identity=ATLAS_RANDOM_STRENGTH_ID_V1,
    )
    depth1_ledger, depth1_records = _sampled_parent_data_v1(
        store,
        protocol_value,
        by_stage[_DEPTH1_PARENT_STAGE_ID_V1],
        stage_id=_DEPTH1_PARENT_STAGE_ID_V1,
        stage_protocol_id=_DEPTH1_PARENT_STAGE_PROTOCOL_ID_V1,
        phase_id=_DEPTH1_PARENT_PHASE_ID_V1,
        strength_identity=ATLAS_DEPTH1_STRENGTH_ID_V1,
    )
    overlap = set(random_records).intersection(depth1_records)
    if overlap:
        raise ValueError("sampled parent game identities overlap strengths")
    return random_ledger, depth1_ledger, {**random_records, **depth1_records}


def run_atlas_telemetry_stage_v1(repository: str) -> Dict[str, Any]:
    if type(repository) is not str or not repository:
        raise ValueError("repository must be a nonempty exact string")
    repository_path = Path(repository).resolve()
    evidence_root = repository_path / _EVIDENCE_ROOT_RELATIVE_V1
    with ImmutableEvidenceStore(evidence_root) as store:
        with store.stage_lock(ATLAS_TELEMETRY_STAGE_PROTOCOL_ID_V1):
            inputs = read_authenticated_stage_inputs(
                store, ATLAS_TELEMETRY_STAGE_ID_V1
            )
            if (
                inputs.contract.stage_protocol_id
                != ATLAS_TELEMETRY_STAGE_PROTOCOL_ID_V1
            ):
                raise ValueError("telemetry stage protocol identity drifted")
            random_ledger, depth1_ledger, sampled = _sampled_inputs_from_parents_v1(
                store, inputs.protocol, inputs.ordered_parent_terminal_seals
            )
            ledger_spec = _telemetry_ledger_spec_v1(
                inputs.protocol, random_ledger, depth1_ledger
            )
            ledger_specs = (ledger_spec,)
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
                    "stage_id": ATLAS_TELEMETRY_STAGE_ID_V1,
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
                summary = _execute_telemetry_journal_v1(
                    store,
                    inputs.contract,
                    inputs.detached_manifest,
                    inputs.protocol,
                    random_ledger,
                    depth1_ledger,
                    sampled,
                )
                status_counts = summary["status_counts"]
                if (
                    summary["slot_count"] != ATLAS_SAMPLED_GAME_COUNT_V1
                    or status_counts.get("VALIDATED", 0)
                    + status_counts.get("NOT_ADMISSIBLE", 0)
                    != ATLAS_SAMPLED_GAME_COUNT_V1
                    or summary["result_count"]
                    != status_counts.get("VALIDATED", 0)
                    or any(
                        status_counts.get(status, 0)
                        for status in (
                            "MISSING",
                            "INVALID",
                            "PROOF_CONTRADICTION",
                        )
                    )
                ):
                    raise ValueError("telemetry completion gate was not met")
                refs = publish_stage_completion_evidence(
                    store, inputs.contract, ledger_specs
                )
            except Exception as error:
                terminal = seal_failed_stage(
                    store, inputs.contract, _failure_value(error), ledger_specs
                )
                return {
                    "lifecycle": "FAILED",
                    "stage_id": ATLAS_TELEMETRY_STAGE_ID_V1,
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
                    ATLAS_TELEMETRY_STAGE_PROTOCOL_ID_V1, "completed"
                ):
                    raise
                terminal = seal_failed_stage(
                    store, inputs.contract, _failure_value(error), ledger_specs
                )
                return {
                    "lifecycle": "FAILED",
                    "stage_id": ATLAS_TELEMETRY_STAGE_ID_V1,
                    "terminal_seal": terminal["identity"],
                }
            return {
                "lifecycle": "COMPLETED",
                "stage_id": ATLAS_TELEMETRY_STAGE_ID_V1,
                "summary": summary,
                "terminal_seal": terminal["identity"],
            }


def recover_atlas_telemetry_stage_v1(repository: str) -> Dict[str, Any]:
    if type(repository) is not str or not repository:
        raise ValueError("repository must be a nonempty exact string")
    repository_path = Path(repository).resolve()
    evidence_root = repository_path / _EVIDENCE_ROOT_RELATIVE_V1
    with ImmutableEvidenceStore(evidence_root) as store:
        inputs = read_authenticated_stage_inputs(store, ATLAS_TELEMETRY_STAGE_ID_V1)
        random_ledger, depth1_ledger, _sampled = _sampled_inputs_from_parents_v1(
            store, inputs.protocol, inputs.ordered_parent_terminal_seals
        )
        result = recover_stage(
            store,
            inputs.contract,
            (_telemetry_ledger_spec_v1(inputs.protocol, random_ledger, depth1_ledger),),
            repository=repository_path,
        )
        return {
            "action": result.action,
            "lifecycle": result.lifecycle,
            "stage_id": ATLAS_TELEMETRY_STAGE_ID_V1,
            "terminal_seal_or_null": result.terminal_identity,
        }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m parity_forge.atlas_telemetry_stage"
    )
    parser.add_argument("command", choices=("run", "recover"))
    parser.add_argument("--repository", required=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = _build_parser().parse_args(argv)
    result = (
        run_atlas_telemetry_stage_v1(arguments.repository)
        if arguments.command == "run"
        else recover_atlas_telemetry_stage_v1(arguments.repository)
    )
    print(canonical_json_bytes(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = (
    "ATLAS_TELEMETRY_RECORD_VERSION_V1",
    "ATLAS_TELEMETRY_STAGE_ID_V1",
    "ATLAS_TELEMETRY_STAGE_PROTOCOL_ID_V1",
    "derive_atlas_telemetry_record_v1",
    "recover_atlas_telemetry_stage_v1",
    "run_atlas_telemetry_stage_v1",
    "validate_atlas_telemetry_record_v1",
)
