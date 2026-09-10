"""Read/validation core for the Plan-0013 atlas assessment.

All labels, metrics, and inspection reasons are rebuilt from fixed ledgers and
authenticated raw records.  Caller-supplied aggregates are never inputs.  The
private arithmetic helpers in :mod:`atlas_protocol` are invoked only inside a
validator after the raw schedule join has completed.  Evidence lifecycle and
publication operations deliberately remain in :mod:`atlas_assessment_stage`.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from . import atlas_protocol as _protocol
from .atlas_evidence import (
    BodyRef,
    ImmutableEvidenceStore,
    StageContract,
    StageResultRefs,
    canonical_body_ref,
    canonical_json_bytes,
    domain_identity,
    extract_stage_contract,
    read_stage_completion_evidence,
)
from .atlas_protocol import (
    ATLAS_DEFINITION_ORIENTATION_COUNT_V1,
    ATLAS_DEVELOPMENT_DEFINITION_COUNT_V1,
    ATLAS_DEVELOPMENT_PAIR_COUNT_V1,
    ATLAS_D4_TRANSFORMS_V1,
    ATLAS_FAMILY_ORDER_V1,
    ATLAS_PROTOCOL_ID_V1,
    ATLAS_PROTOCOL_ROOT_V1,
    ATLAS_SAMPLED_GAME_COUNT_V1,
    iter_frozen_atlas_exact_schedule_from_protocol_v1,
    iter_frozen_atlas_game_schedule_from_protocol_v1,
    iter_frozen_atlas_orientation_schedule_from_protocol_v1,
)
from .atlas_stage_data import (
    ATLAS_DEPTH1_STRENGTH_ID_V1,
    ATLAS_RANDOM_STRENGTH_ID_V1,
    iter_joined_atlas_game_definitions_v1,
    reconcile_atlas_exact_status_ledger_v1,
    reconcile_atlas_pv_status_ledger_v1,
    reconcile_atlas_sampled_status_ledger_v1,
    reconcile_atlas_telemetry_status_ledger_v1,
    validate_atlas_exact_status_ledger_v1,
    validate_atlas_pv_status_ledger_v1,
    validate_atlas_sampled_status_ledger_v1,
    validate_atlas_telemetry_status_ledger_v1,
    validate_complete_atlas_trace_v1,
    validate_detached_atlas_development_manifest_v1,
)


ATLAS_ASSESSMENT_STAGE_ID_V1 = "ASSESSMENT_AND_INSPECTION"
ATLAS_ASSESSMENT_STAGE_PROTOCOL_ID_V1 = (
    "plan0013-atlas-development-assessment-v1"
)
ATLAS_ASSESSMENT_REPORT_VERSION_V1 = 1

_EVIDENCE_ROOT_RELATIVE_V1 = (
    "experiments/runs/plan0013-atlas-development-evidence-v2"
)
_EXACT_PARENT = (
    "EXACT_ALL_288",
    "plan0013-atlas-development-exact-v1",
)
_RANDOM_PARENT = (
    "RANDOM_ALL_18432_GAMES",
    "plan0013-atlas-development-random-v1",
)
_DEPTH1_PARENT = (
    "TERMINAL_DEPTH1_ALL_18432_GAMES",
    "plan0013-atlas-development-terminal-depth1-v1",
)
_TELEMETRY_PARENT = (
    "REPLAY_TELEMETRY_COMPLETE_TRACES_ONLY",
    "plan0013-atlas-development-telemetry-v1",
)
_MANIFEST_PARENT = (
    "OUTCOME_FREE_DEVELOPMENT_MANIFEST",
    "plan0013-atlas-development-manifest-v1",
)
_META_PARENT_ORDER_V1 = (
    _MANIFEST_PARENT,
    _EXACT_PARENT,
    _RANDOM_PARENT,
    _DEPTH1_PARENT,
    _TELEMETRY_PARENT,
)

_REPORT_ROOT_DOMAIN_V1 = b"parity-forge:plan0013:assessment-report:v1\0"
_META_FAILURE_REPORT_ROOT_DOMAIN_V1 = (
    b"parity-forge:plan0013:assessment-meta-failure-report:v1\0"
)
_REPORT_INPUT_ROOT_DOMAIN_V1 = b"parity-forge:plan0013:assessment-input:v1\0"
_EXACT_RECORD_DOMAIN_V1 = b"parity-forge:plan0013:exact-record:v1\0"
_PV_RECORD_DOMAIN_V1 = b"parity-forge:plan0013:exact-pv-record:v1\0"
_RANDOM_RECORD_DOMAIN_V1 = b"parity-forge:plan0013:random-game-record:v1\0"
_DEPTH1_RECORD_DOMAIN_V1 = b"parity-forge:plan0013:depth1-game-record:v1\0"
_TELEMETRY_RECORD_DOMAIN_V1 = (
    b"parity-forge:plan0013:replay-telemetry-record:v1\0"
)

_EXACT_RECORD_FIELDS = frozenset(
    (
        "record_version",
        "record_kind",
        "slot_id",
        "definition_hash",
        "definition_byte_count",
        "status",
        "max_states",
        "max_action_candidates_per_state",
        "max_state_action_candidate_evaluations",
        "result_or_null",
        "contradiction_or_null",
        "record_root",
    )
)
_PV_RECORD_FIELDS = frozenset(
    (
        "record_version",
        "record_kind",
        "status",
        "orientation_slot_id",
        "exact_slot_id",
        "transform_index",
        "transform",
        "representative_definition_hash",
        "representative_definition_byte_count",
        "transformed_definition_hash",
        "transformed_definition_byte_count",
        "principal_variation_or_null",
        "principal_variation_plies_or_null",
        "value_for_a_or_null",
        "forced_result_or_null",
        "winner_or_null",
        "terminal_reason_or_null",
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

_REDUCED_PRIORITY = (
    "PROOF_CONTRADICTION",
    "INVALID",
    "INCOMPLETE",
    "BLOCKED",
    "NOT_RUN",
    "COMPLETE",
)
_FORMAL_CHANNELS = ("exact", "random", "terminal_depth1")


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


def _exact_fields(value: Any, fields: Iterable[str], label: str) -> Dict[str, Any]:
    if type(value) is not dict or set(value) != set(fields):
        raise ValueError("{} fields drifted".format(label))
    return value


def _verify_record_root(record: Mapping[str, Any], domain: bytes, label: str) -> str:
    root = _sha256(record.get("record_root"), "{} root".format(label))
    unsigned = dict(record)
    del unsigned["record_root"]
    if domain_identity(domain, unsigned) != root:
        raise ValueError("{} root does not reconstruct".format(label))
    return root


def _ordered_input_root(label: str, records: Sequence[Mapping[str, Any]]) -> str:
    return domain_identity(
        _REPORT_INPUT_ROOT_DOMAIN_V1,
        {
            "channel": label,
            "ordered_record_roots": [record["record_root"] for record in records],
        },
    )


def _raw_ledger_rows(ledger: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {
        row["slot_id"]: row
        for row in ledger["rows"]
        if row["origin"] == "RAW_RECORD"
    }


def _bind_records_to_ledger(
    records_value: Any,
    ledger: Mapping[str, Any],
    *,
    id_field: str,
    fields: Iterable[str],
    domain: bytes,
    label: str,
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    if type(records_value) is not list:
        raise TypeError("{} records must be an exact array".format(label))
    records = [_json_copy(record, "{} record".format(label)) for record in records_value]
    by_slot = {}
    for record in records:
        _exact_fields(record, fields, "{} record".format(label))
        slot_id = _sha256(record[id_field], "{} slot identity".format(label))
        if slot_id in by_slot:
            raise ValueError("{} records repeat a slot".format(label))
        _verify_record_root(record, domain, label)
        by_slot[slot_id] = record
    raw_rows = _raw_ledger_rows(ledger)
    if set(by_slot) != set(raw_rows):
        raise ValueError("{} record set differs from RAW_RECORD ledger rows".format(label))
    for slot_id, row in raw_rows.items():
        record = by_slot[slot_id]
        if (
            record["status"] != row["status"]
            or record["record_root"] != row["record_root_or_null"]
        ):
            raise ValueError("{} record differs from its ledger row".format(label))
    return records, by_slot


def _body_ref(value: Any, label: str) -> BodyRef:
    reference = _exact_fields(value, ("byte_count", "sha256"), label)
    return BodyRef(
        sha256=_sha256(reference["sha256"], "{} SHA-256".format(label)),
        byte_count=_exact_int(reference["byte_count"], "{} byte count".format(label)),
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
        raise ValueError("assessment parent record catalog differs from its ledger")


def _sealed_parent_ledger_set_v1(
    store: ImmutableEvidenceStore,
    protocol_value: Any,
    terminal_seal: Mapping[str, Any],
    stage_id: str,
    stage_protocol_id: str,
) -> Tuple[Optional[Dict[str, Any]], str, StageContract]:
    contract = extract_stage_contract(protocol_value, stage_id)
    if contract.stage_protocol_id != stage_protocol_id:
        raise ValueError("assessment parent stage protocol identity drifted")
    payload = terminal_seal.get("payload") if type(terminal_seal) is dict else None
    if (
        type(payload) is not dict
        or payload.get("stage_id") != stage_id
        or payload.get("stage_protocol_id") != stage_protocol_id
    ):
        raise ValueError("assessment parent terminal coordinates drifted")
    lifecycle = payload.get("lifecycle")
    if lifecycle == "BLOCKED":
        return None, lifecycle, contract
    if lifecycle == "COMPLETED":
        completed = store.read_json(stage_protocol_id, "completed")
        if canonical_body_ref(completed).sha256 != payload.get(
            "completed_root_or_null"
        ):
            raise ValueError("assessment parent completed root differs from its seal")
        completed = _exact_fields(
            completed,
            (
                "artifact_type",
                "attempt_id",
                "reservation_id",
                "result",
                "stage_id",
                "stage_protocol_id",
            ),
            "assessment parent completed artifact",
        )
        result = _exact_fields(
            completed["result"],
            ("artifact_refs_or_null", "summary"),
            "assessment parent completed result",
        )
        refs = _exact_fields(
            result["artifact_refs_or_null"],
            ("record_catalog", "status_ledger"),
            "assessment parent result refs",
        )
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
        partial = store.read_json(stage_protocol_id, "partial_ledger")
        if canonical_body_ref(partial).sha256 != payload.get(
            "partial_evidence_root_or_null"
        ):
            raise ValueError("assessment parent partial ledger differs from its seal")
        return _json_copy(partial, "assessment parent partial ledger"), lifecycle, contract
    raise ValueError("assessment parent lifecycle is invalid")


def _phase_projection_v1(
    store: ImmutableEvidenceStore,
    contract: StageContract,
    ledger_set_value: Any,
    phase_id: str,
    expected_slot_ids: Sequence[str],
    raw_statuses: Sequence[str],
    interrupted_status: str,
    unobserved_status: str,
    *,
    preclassified_slot_ids: Sequence[str] = (),
    preclassified_status: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], List[str], List[Dict[str, Any]]]:
    ledger_set = _exact_fields(
        _json_copy(ledger_set_value, "assessment parent ledger set"),
        ("artifact_type", "ledgers", "phase_ids", "stage_id", "stage_protocol_id"),
        "assessment parent ledger set",
    )
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
        raise ValueError("assessment parent ledger-set binding drifted")
    matches = [ledger for ledger in ledgers if ledger.get("phase_id") == phase_id]
    if len(matches) != 1:
        raise ValueError("assessment parent ledger phase membership drifted")
    ledger = _exact_fields(
        matches[0],
        (
            "artifact_type",
            "phase_id",
            "slot_count",
            "slots",
            "stage_id",
            "stage_protocol_id",
            "status_counts",
        ),
        "assessment parent phase ledger",
    )
    slots = ledger["slots"]
    if (
        ledger["artifact_type"] != "ATLAS_FULL_STATUS_LEDGER_V1"
        or ledger["stage_id"] != contract.stage_id
        or ledger["stage_protocol_id"] != contract.stage_protocol_id
        or ledger["phase_id"] != phase_id
        or ledger["slot_count"] != len(expected_slot_ids)
        or type(slots) is not list
        or len(slots) != len(expected_slot_ids)
    ):
        raise ValueError("assessment parent phase binding drifted")
    preclassified = set(preclassified_slot_ids)
    if not preclassified.issubset(expected_slot_ids):
        raise ValueError("assessment preclassification is outside the phase schedule")
    if preclassified and preclassified_status is None:
        raise ValueError("assessment preclassification configuration is inconsistent")
    allowed_raw = set(raw_statuses)
    observed: List[Dict[str, Any]] = []
    started: List[str] = []
    records: List[Dict[str, Any]] = []
    statuses: List[str] = []
    for index, (slot, slot_id) in enumerate(zip(slots, expected_slot_ids)):
        slot = _exact_fields(
            slot,
            (
                "result_ref_or_null",
                "slot_id",
                "slot_index",
                "start_ref_or_null",
                "status",
            ),
            "assessment parent phase slot",
        )
        if slot["slot_id"] != slot_id or slot["slot_index"] != index:
            raise ValueError("assessment parent slot order or identity drifted")
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
                "slot_id": slot_id,
                "slot_index": index,
                "stage_protocol_id": contract.stage_protocol_id,
            }:
                raise ValueError("assessment parent journal start does not authenticate")
            started.append(slot_id)
        if result_ref_value is not None:
            if start_ref_value is None or status not in allowed_raw:
                raise ValueError("assessment parent result row semantics drifted")
            result_ref = _body_ref(result_ref_value, "parent journal result ref")
            envelope = store.read_journal_result(
                contract.stage_protocol_id, phase_id, index
            )
            if canonical_body_ref(envelope) != result_ref:
                raise ValueError("assessment parent result does not authenticate")
            envelope = _exact_fields(
                envelope,
                (
                    "artifact_type",
                    "phase_id",
                    "result",
                    "slot_id",
                    "slot_index",
                    "stage_protocol_id",
                    "start_ref",
                    "status",
                ),
                "assessment parent journal result",
            )
            if (
                envelope["artifact_type"] != "ATLAS_SLOT_RESULT_V1"
                or envelope["phase_id"] != phase_id
                or envelope["slot_id"] != slot_id
                or envelope["slot_index"] != index
                or envelope["stage_protocol_id"] != contract.stage_protocol_id
                or envelope["start_ref"] != start_ref_value
                or envelope["status"] != status
                or type(envelope["result"]) is not dict
            ):
                raise ValueError("assessment parent result coordinates drifted")
            record = _json_copy(envelope["result"], "assessment parent raw record")
            observed.append(
                {
                    "slot_id": slot_id,
                    "status": status,
                    "record_root_or_null": _sha256(
                        record.get("record_root"), "assessment parent raw root"
                    ),
                }
            )
            records.append(record)
        elif start_ref_value is not None:
            if status != interrupted_status:
                raise ValueError("assessment parent started row status drifted")
        else:
            expected = (
                preclassified_status if slot_id in preclassified else unobserved_status
            )
            if status != expected:
                raise ValueError("assessment parent unobserved row status drifted")
    if ledger["status_counts"] != dict(Counter(statuses)):
        raise ValueError("assessment parent status counts do not reconstruct")
    return observed, started, records


def _metric_subset_status(statuses: Sequence[str], *, telemetry: bool = False) -> str:
    mapped = []
    for status in statuses:
        if telemetry:
            if status in ("INVALID", "PROOF_CONTRADICTION"):
                mapped.append("INVALID")
            elif status == "VALIDATED":
                mapped.append("COMPLETE")
            else:
                mapped.append("INCOMPLETE")
        else:
            if status in ("INVALID", "PROOF_CONTRADICTION"):
                mapped.append("INVALID")
            elif status == "COMPLETE":
                mapped.append("COMPLETE")
            else:
                mapped.append("INCOMPLETE")
    if "INVALID" in mapped:
        return "INVALID"
    if "INCOMPLETE" in mapped:
        return "INCOMPLETE"
    return "COMPLETE"


def _reduced_channel_status(statuses: Sequence[str], *, telemetry: bool = False) -> str:
    if telemetry:
        mapped = [
            "COMPLETE"
            if status in ("VALIDATED", "NOT_ADMISSIBLE")
            else "INCOMPLETE"
            if status == "MISSING"
            else status
            for status in statuses
        ]
        priority = (
            "PROOF_CONTRADICTION",
            "INVALID",
            "INCOMPLETE",
            "BLOCKED",
            "COMPLETE",
        )
    else:
        mapped = ["COMPLETE" if status == "VALID" else status for status in statuses]
        priority = _REDUCED_PRIORITY
    for status in priority:
        if status in mapped:
            return status
    raise ValueError("channel status multiset is empty or unknown")


def _evidence_label(channel_status: str) -> Optional[str]:
    if channel_status in ("INVALID", "PROOF_CONTRADICTION"):
        return "EVIDENCE_INVALID"
    if channel_status in ("INCOMPLETE", "NOT_RUN", "BLOCKED"):
        return "EVIDENCE_INCOMPLETE"
    if channel_status != "COMPLETE":
        raise ValueError("unknown reduced channel status")
    return None


def _empty_outcome_counts() -> Dict[str, int]:
    return {"A": 0, "B": 0, "DRAW_PLY_LIMIT": 0, "completed": 0, "plies": 0}


def _sampled_summary(status: str, counts: Mapping[str, int]) -> Dict[str, Any]:
    return {
        "status": status,
        "scheduled_games": 128,
        "completed_games": counts["completed"],
        "a_wins": counts["A"],
        "b_wins": counts["B"],
        "draws": counts["DRAW_PLY_LIMIT"],
    }


def _inspection_outcome_summary(
    status: str, scheduled: int, counts: Mapping[str, int]
) -> Dict[str, Any]:
    return {
        "status": status,
        "scheduled_games": scheduled,
        "completed_games": counts["completed"],
        "a_wins": counts["A"],
        "b_wins": counts["B"],
        "draw_ply_limit": counts["DRAW_PLY_LIMIT"],
    }


def _validate_exact_record(record: Mapping[str, Any], slot: Mapping[str, Any]) -> None:
    if (
        record["record_version"] != 1
        or record["record_kind"] != "EXACT"
        or record["slot_id"] != slot["slot_id"]
        or record["definition_hash"] != slot["representative_definition_hash"]
        or record["max_states"] != slot["max_states"]
        or record["max_action_candidates_per_state"]
        != slot["max_action_candidates_per_state"]
        or record["max_state_action_candidate_evaluations"]
        != slot["max_state_action_candidate_evaluations"]
    ):
        raise ValueError("exact record differs from its protocol slot")
    status = record["status"]
    result = record["result_or_null"]
    contradiction = record["contradiction_or_null"]
    if status == "COMPLETE":
        _exact_int(record["definition_byte_count"], "exact definition byte count", 1)
        result = _exact_fields(
            result,
            (
                "value_for_a",
                "forced_result",
                "principal_variation",
                "principal_variation_plies",
                "terminal_reason",
                "searched_states",
                "cache_hits",
            ),
            "exact result",
        )
        if contradiction is not None:
            raise ValueError("complete exact record contains a contradiction")
        value = result["value_for_a"]
        forced = result["forced_result"]
        if (value, forced) not in ((1, "A_WIN"), (-1, "B_WIN"), (0, "DRAW")):
            raise ValueError("exact result value and forced result disagree")
        reason = result["terminal_reason"]
        if reason not in ("GOAL", "NO_LEGAL_ACTION", "PLY_LIMIT"):
            raise ValueError("exact result has an unknown terminal reason")
        if (forced == "DRAW") != (reason == "PLY_LIMIT"):
            raise ValueError("current atlas exact draw semantics drifted")
        searched = _exact_int(result["searched_states"], "searched states", 1)
        if searched > slot["max_states"]:
            raise ValueError("exact result exceeds its state cap")
        _exact_int(result["cache_hits"], "exact cache hits")
        pv = result["principal_variation"]
        if type(pv) is not list or result["principal_variation_plies"] != len(pv):
            raise ValueError("exact principal variation count drifted")
    elif status in ("INVALID", "PROOF_CONTRADICTION"):
        if result is not None or type(contradiction) is not dict:
            raise ValueError("failed exact record does not retain failure evidence")
        if status == "INVALID":
            if record["definition_byte_count"] is not None:
                raise ValueError("invalid exact record claims definition bytes")
        else:
            _exact_int(
                record["definition_byte_count"], "exact definition byte count", 1
            )
    else:
        raise ValueError("exact raw record has an unknown status")


def _validate_pv_record(
    record: Mapping[str, Any], orientation: Mapping[str, Any]
) -> None:
    if (
        record["record_version"] != 1
        or record["record_kind"] != "EXACT_PV"
        or record["orientation_slot_id"] != orientation["slot_id"]
        or record["exact_slot_id"] != orientation["exact_slot_id"]
        or record["transform_index"] != orientation["transform_index"]
        or record["transform"] != orientation["transform"]
        or record["transformed_definition_hash"]
        != orientation["transformed_definition_hash"]
    ):
        raise ValueError("PV record differs from its protocol orientation")
    required_replay = (
        "principal_variation_or_null",
        "principal_variation_plies_or_null",
        "value_for_a_or_null",
        "forced_result_or_null",
        "terminal_reason_or_null",
    )
    if record["status"] == "VALID":
        _exact_int(
            record["representative_definition_byte_count"],
            "PV representative definition byte count",
            1,
        )
        _exact_int(
            record["transformed_definition_byte_count"],
            "PV transformed definition byte count",
            1,
        )
        if record["error_or_null"] is not None or any(
            record[key] is None for key in required_replay
        ):
            raise ValueError("VALID PV record lacks replay evidence")
        pv = record["principal_variation_or_null"]
        if type(pv) is not list or record["principal_variation_plies_or_null"] != len(pv):
            raise ValueError("PV replay count drifted")
        value = record["value_for_a_or_null"]
        forced = record["forced_result_or_null"]
        winner = record["winner_or_null"]
        if (value, forced, winner) not in (
            (1, "A_WIN", "A"),
            (-1, "B_WIN", "B"),
            (0, "DRAW", None),
        ):
            raise ValueError("PV value, forced result, and winner disagree")
        if record["terminal_reason_or_null"] not in (
            "GOAL",
            "NO_LEGAL_ACTION",
            "PLY_LIMIT",
        ):
            raise ValueError("PV replay has an unknown terminal reason")
        if (forced == "DRAW") != (
            record["terminal_reason_or_null"] == "PLY_LIMIT"
        ):
            raise ValueError("PV replay draw semantics drifted")
    elif record["status"] in ("INVALID", "PROOF_CONTRADICTION"):
        if record["error_or_null"] is None or any(
            record[key] is not None for key in required_replay + ("winner_or_null",)
        ):
            raise ValueError("failed PV record claims replay evidence")
        if (
            record["representative_definition_byte_count"] is not None
            or record["transformed_definition_byte_count"] is not None
        ):
            raise ValueError("failed PV record claims definition bytes")
    else:
        raise ValueError("PV raw record has an unknown status")


def _validate_sampled_record(
    record: Mapping[str, Any], game: Mapping[str, Any], strength: str
) -> None:
    if (
        record["record_version"] != 1
        or record["record_kind"] != "SAMPLED_GAME"
        or record["strength_identity"] != strength
        or record["game_slot_id"] != game["slot_id"]
        or record["profile_slot_id"] != game["profile_slot_id"]
        or record["ordered_role_slot_ids"] != game["ordered_role_slot_ids"]
        or record["matched_start_block_id"] != game["matched_start_block_id"]
        or record["seed_index"] != game["seed_index"]
        or record["seed"] != game["seed"]
        or record["definition_hash"] != game["transformed_definition_hash"]
        or record["agent_a"] != strength
        or record["agent_b"] != strength
        or record["rng_scope"] != game["rng_scope"]
        or record["rng_stream"] != game["rng_stream"]
    ):
        raise ValueError("sampled record differs from its protocol game")
    allowed = (
        ("COMPLETE", "INVALID")
        if strength == ATLAS_RANDOM_STRENGTH_ID_V1
        else ("COMPLETE", "INCOMPLETE", "INVALID")
    )
    if record["status"] not in allowed:
        raise ValueError("sampled raw record has an unknown status")
    if record["status"] in ("COMPLETE", "INCOMPLETE"):
        _exact_int(record["definition_byte_count"], "sampled definition byte count", 1)
    elif record["definition_byte_count"] is not None:
        raise ValueError("invalid sampled record must not claim definition bytes")
    if record["status"] == "COMPLETE":
        if type(record["complete_trace_or_null"]) is not dict or record[
            "censored_prefix_or_null"
        ] is not None:
            raise ValueError("COMPLETE sampled record lacks a complete trace")
    elif record["complete_trace_or_null"] is not None:
        raise ValueError("noncomplete sampled record claims a complete trace")
    if strength == ATLAS_RANDOM_STRENGTH_ID_V1:
        if (
            type(record["decisions"]) is not list
            or record["node_ledger_or_null"] is not None
        ):
            raise ValueError("random sampled audit fields drifted")
    elif record["status"] in ("COMPLETE", "INCOMPLETE") and type(
        record["node_ledger_or_null"]
    ) is not dict:
        raise ValueError("depth-1 sampled record lacks its node ledger")


def _validate_telemetry_record(
    record: Mapping[str, Any], game: Mapping[str, Any], sampled: Mapping[str, Any]
) -> None:
    if (
        record["record_version"] != 1
        or record["record_kind"] != "REPLAY_TELEMETRY"
        or record["game_slot_id"] != game["slot_id"]
        or record["sampled_record_root"] != sampled["record_root"]
        or record["strength_identity"] != sampled["strength_identity"]
        or record["definition_hash"] != game["transformed_definition_hash"]
    ):
        raise ValueError("telemetry record differs from sampled evidence")
    status = record["status"]
    if status == "VALIDATED":
        if (
            type(record["telemetry_or_null"]) is not dict
            or record["contradiction_or_null"] is not None
            or record["error_or_null"] is not None
            or type(record["trace_plies_or_null"]) is not int
            or not 0 <= record["trace_plies_or_null"] <= 18
        ):
            raise ValueError("VALIDATED telemetry record lacks telemetry")
        telemetry = record["telemetry_or_null"]
        trace = sampled.get("complete_trace_or_null")
        work = telemetry.get("work")
        terminal = telemetry.get("terminal")
        if (
            type(trace) is not dict
            or type(work) is not dict
            or work.get("replayed_actions") != record["trace_plies_or_null"]
            or terminal
            != {
                "ply": trace.get("plies"),
                "winner": trace.get("winner"),
                "reason": trace.get("terminal_reason"),
            }
            or record["trace_plies_or_null"] != trace.get("plies")
            or telemetry.get("definition_hash") != record["definition_hash"]
        ):
            raise ValueError("VALIDATED telemetry differs from its sampled trace")
    elif status == "PROOF_CONTRADICTION":
        if (
            record["telemetry_or_null"] is not None
            or type(record["contradiction_or_null"]) is not dict
            or record["error_or_null"] is not None
        ):
            raise ValueError("telemetry proof contradiction shape drifted")
    elif status == "INVALID":
        if (
            record["telemetry_or_null"] is not None
            or record["contradiction_or_null"] is not None
            or type(record["error_or_null"]) is not dict
        ):
            raise ValueError("invalid telemetry record shape drifted")
    else:
        raise ValueError("telemetry raw record has an unknown status")


def _add_outcome(counts: Dict[str, int], trace: Mapping[str, Any]) -> None:
    winner = trace["winner"]
    reason = trace["terminal_reason"]
    if winner in ("A", "B"):
        if reason == "PLY_LIMIT":
            raise ValueError("sampled PLY_LIMIT terminal cannot have a winner")
        counts[winner] += 1
    elif winner is None and reason == "PLY_LIMIT":
        counts["DRAW_PLY_LIMIT"] += 1
    else:
        raise ValueError("sampled trace has an unsupported natural draw")
    counts["completed"] += 1
    counts["plies"] += trace["plies"]


def _telemetry_metric_values(record: Mapping[str, Any]) -> Dict[str, Any]:
    telemetry = record["telemetry_or_null"]
    roles = _exact_fields(telemetry.get("roles"), ("A", "B"), "telemetry roles")
    result = {"roles": {}, "reciprocal": False, "repetitions": 0, "work": {}}
    dependencies = []
    for role in ("A", "B"):
        role_value = roles[role]
        if type(role_value) is not dict:
            raise ValueError("telemetry role must be an exact object")
        decisions = _exact_int(role_value.get("decision_count"), "role decisions")
        observations = _exact_int(
            role_value.get("legal_observation_count"),
            "role legal observations",
        )
        bins = role_value.get("legal_count_bins")
        if type(bins) is not dict or set(bins) != {"0", "1", "2+"}:
            raise ValueError("telemetry legal-count bins drifted")
        bin_counts = {
            key: _exact_int(value, "telemetry legal-count bin")
            for key, value in bins.items()
        }
        if sum(bin_counts.values()) != observations:
            raise ValueError("telemetry legal-count bins do not sum to observations")
        if bin_counts["1"] + bin_counts["2+"] != decisions:
            raise ValueError(
                "telemetry positive legal-count bins do not sum to decisions"
            )
        if observations != decisions + bin_counts["0"]:
            raise ValueError("telemetry legal observations do not reconstruct")
        forced = bin_counts["1"]
        if forced > decisions:
            raise ValueError("forced decisions exceed role decisions")
        dependency = _exact_int(
            role_value.get("opponent_dependency_actions"),
            "opponent dependency actions",
        )
        if dependency > decisions:
            raise ValueError("opponent-dependency actions exceed role decisions")
        result["roles"][role] = {"decisions": decisions, "forced": forced}
        dependencies.append(dependency)
    result["reciprocal"] = all(value > 0 for value in dependencies)
    repetition = telemetry.get("repetition")
    if type(repetition) is not dict:
        raise ValueError("telemetry repetition evidence is missing")
    result["repetitions"] = _exact_int(
        repetition.get("repeat_event_count"), "repetition events"
    )
    work = telemetry.get("work")
    expected_work = (
        "replayed_actions",
        "decision_count",
        "state_observation_count",
        "successor_evaluations",
        "next_action_observations",
    )
    _exact_fields(work, expected_work, "telemetry work")
    result["work"] = {
        field: _exact_int(work[field], "telemetry work {}".format(field))
        for field in expected_work
    }
    telemetry_decisions = telemetry.get("decisions")
    if type(telemetry_decisions) is not list:
        raise ValueError("telemetry decisions are missing")
    role_decisions = sum(value["decisions"] for value in result["roles"].values())
    if (
        result["work"]["decision_count"] != role_decisions
        or result["work"]["decision_count"] != len(telemetry_decisions)
        or result["work"]["replayed_actions"] != len(telemetry_decisions)
        or result["work"]["state_observation_count"]
        != result["work"]["replayed_actions"] + 1
    ):
        raise ValueError("telemetry work totals do not reconstruct")
    if result["work"]["replayed_actions"] > 18 or result["work"][
        "decision_count"
    ] > 18 or result["work"][
        "state_observation_count"
    ] > 19 or result["work"]["successor_evaluations"] > 864 or result[
        "work"
    ]["next_action_observations"] > 41_472:
        raise ValueError("VALIDATED telemetry exceeds a frozen structural cap")
    return result


def _pair_accumulator(exact: Mapping[str, Any]) -> Dict[str, Any]:
    strengths = (ATLAS_RANDOM_STRENGTH_ID_V1, ATLAS_DEPTH1_STRENGTH_ID_V1)
    return {
        "pair_index": exact["pair_index"],
        "paired_mechanical_d4_identity": exact["paired_mechanical_d4_identity"],
        "family_id": exact["family_id"],
        "paired_stratum_id": exact["paired_stratum_id"],
        "exact_statuses": [],
        "pv_statuses": [],
        "exact_members": {},
        "exact_utilization": {},
        "sampled_statuses": {identity: [] for identity in strengths},
        "sampled_counts": {identity: _empty_outcome_counts() for identity in strengths},
        "orientation_statuses": {
            identity: {transform: [] for transform in ATLAS_D4_TRANSFORMS_V1}
            for identity in strengths
        },
        "orientation_counts": {
            identity: {
                transform: _empty_outcome_counts()
                for transform in ATLAS_D4_TRANSFORMS_V1
            }
            for identity in strengths
        },
        "telemetry_statuses": [],
        "depth1_telemetry_statuses": [],
        "forced": {
            "A": {"decisions": 0, "forced": 0},
            "B": {"decisions": 0, "forced": 0},
        },
        "reciprocal_games": 0,
    }


def _validate_protocol_raw_inputs_v1(
    manifest_value: Any,
    protocol_value: Any,
    exact_ledger_value: Any,
    pv_ledger_value: Any,
    random_ledger_value: Any,
    depth1_ledger_value: Any,
    telemetry_ledger_value: Any,
    exact_records_value: Any,
    pv_records_value: Any,
    random_records_value: Any,
    depth1_records_value: Any,
    telemetry_records_value: Any,
) -> Dict[str, Any]:
    manifest = validate_detached_atlas_development_manifest_v1(
        manifest_value, protocol_value
    )
    exact_ledger = validate_atlas_exact_status_ledger_v1(
        exact_ledger_value, protocol_value
    )
    pv_ledger = validate_atlas_pv_status_ledger_v1(pv_ledger_value, protocol_value)
    random_ledger = validate_atlas_sampled_status_ledger_v1(
        random_ledger_value, protocol_value, ATLAS_RANDOM_STRENGTH_ID_V1
    )
    depth1_ledger = validate_atlas_sampled_status_ledger_v1(
        depth1_ledger_value, protocol_value, ATLAS_DEPTH1_STRENGTH_ID_V1
    )
    telemetry_ledger = validate_atlas_telemetry_status_ledger_v1(
        telemetry_ledger_value, protocol_value
    )
    exact_records, exact_by_id = _bind_records_to_ledger(
        exact_records_value,
        exact_ledger,
        id_field="slot_id",
        fields=_EXACT_RECORD_FIELDS,
        domain=_EXACT_RECORD_DOMAIN_V1,
        label="exact",
    )
    pv_records, pv_by_id = _bind_records_to_ledger(
        pv_records_value,
        pv_ledger,
        id_field="orientation_slot_id",
        fields=_PV_RECORD_FIELDS,
        domain=_PV_RECORD_DOMAIN_V1,
        label="PV",
    )
    random_records, random_by_id = _bind_records_to_ledger(
        random_records_value,
        random_ledger,
        id_field="game_slot_id",
        fields=_RANDOM_RECORD_FIELDS,
        domain=_RANDOM_RECORD_DOMAIN_V1,
        label="random",
    )
    depth1_records, depth1_by_id = _bind_records_to_ledger(
        depth1_records_value,
        depth1_ledger,
        id_field="game_slot_id",
        fields=_DEPTH1_RECORD_FIELDS,
        domain=_DEPTH1_RECORD_DOMAIN_V1,
        label="terminal-depth1",
    )
    telemetry_records, telemetry_by_id = _bind_records_to_ledger(
        telemetry_records_value,
        telemetry_ledger,
        id_field="game_slot_id",
        fields=_TELEMETRY_RECORD_FIELDS,
        domain=_TELEMETRY_RECORD_DOMAIN_V1,
        label="telemetry",
    )

    exact_schedule = list(iter_frozen_atlas_exact_schedule_from_protocol_v1(protocol_value))
    orientations = list(
        iter_frozen_atlas_orientation_schedule_from_protocol_v1(protocol_value)
    )
    exact_rows = {row["slot_id"]: row for row in exact_ledger["rows"]}
    pv_rows = {row["slot_id"]: row for row in pv_ledger["rows"]}
    pairs: Dict[str, Dict[str, Any]] = {}
    exact_schedule_by_id = {slot["slot_id"]: slot for slot in exact_schedule}
    for slot in exact_schedule:
        pair = pairs.setdefault(
            slot["paired_mechanical_d4_identity"], _pair_accumulator(slot)
        )
        ledger_row = exact_rows[slot["slot_id"]]
        pair["exact_statuses"].append(ledger_row["status"])
        record = exact_by_id.get(slot["slot_id"])
        if record is not None:
            _validate_exact_record(record, slot)
        if ledger_row["status"] == "COMPLETE":
            if record is None:
                raise ValueError("COMPLETE exact slot lacks a raw record")
            result = record["result_or_null"]
            pair["exact_members"][slot["member"]] = {
                "status": "COMPLETE",
                "forced_result": result["forced_result"],
                "terminal_reason": result["terminal_reason"],
            }
            pair["exact_utilization"][slot["member"]] = {
                "status": "COMPLETE",
                "searched_states": result["searched_states"],
                "max_states": slot["max_states"],
            }
        else:
            normalized = (
                "INVALID"
                if ledger_row["status"] in ("INVALID", "PROOF_CONTRADICTION")
                else "INCOMPLETE"
            )
            pair["exact_members"][slot["member"]] = {
                "status": normalized,
                "forced_result": None,
                "terminal_reason": None,
            }
            pair["exact_utilization"][slot["member"]] = {
                "status": normalized,
                "searched_states": 0,
                "max_states": slot["max_states"],
            }
    if len(pairs) != ATLAS_DEVELOPMENT_PAIR_COUNT_V1:
        raise ValueError("exact schedule pair denominator drifted")
    for orientation in orientations:
        exact = exact_schedule_by_id[orientation["exact_slot_id"]]
        pair = pairs[exact["paired_mechanical_d4_identity"]]
        row = pv_rows[orientation["slot_id"]]
        pair["pv_statuses"].append(row["status"])
        record = pv_by_id.get(orientation["slot_id"])
        if record is not None:
            _validate_pv_record(record, orientation)
            if record["representative_definition_hash"] != exact[
                "representative_definition_hash"
            ]:
                raise ValueError("PV representative definition hash drifted")
        if row["status"] == "VALID":
            exact_record = exact_by_id.get(orientation["exact_slot_id"])
            if exact_record is None or exact_record["status"] != "COMPLETE":
                raise ValueError("VALID PV record lacks a COMPLETE exact parent")
            if (
                record["forced_result_or_null"]
                != exact_record["result_or_null"]["forced_result"]
                or record["terminal_reason_or_null"]
                != exact_record["result_or_null"]["terminal_reason"]
                or record["value_for_a_or_null"]
                != exact_record["result_or_null"]["value_for_a"]
            ):
                raise ValueError("PV outcome differs from its exact parent")

    random_rows = {row["slot_id"]: row for row in random_ledger["rows"]}
    depth1_rows = {row["slot_id"]: row for row in depth1_ledger["rows"]}
    telemetry_rows = {row["slot_id"]: row for row in telemetry_ledger["rows"]}
    telemetry_all_blocked = all(
        row["status"] == "BLOCKED" for row in telemetry_ledger["rows"]
    )
    joined_count = 0
    for joined in iter_joined_atlas_game_definitions_v1(manifest, protocol_value):
        joined_count += 1
        game = joined["slot"]
        identity = game["strength"]["identity"]
        sampled_rows = (
            random_rows if identity == ATLAS_RANDOM_STRENGTH_ID_V1 else depth1_rows
        )
        sampled_by_id = (
            random_by_id if identity == ATLAS_RANDOM_STRENGTH_ID_V1 else depth1_by_id
        )
        row = sampled_rows[game["slot_id"]]
        sampled = sampled_by_id.get(game["slot_id"])
        if sampled is not None:
            _validate_sampled_record(sampled, game, identity)
        pair = pairs[game["paired_mechanical_d4_identity"]]
        pair["sampled_statuses"][identity].append(row["status"])
        pair["orientation_statuses"][identity][game["transform"]].append(
            row["status"]
        )
        if row["status"] == "COMPLETE":
            if sampled is None:
                raise ValueError("COMPLETE sampled slot lacks a raw record")
            trace = validate_complete_atlas_trace_v1(
                joined["definition"], sampled["complete_trace_or_null"]
            )
            _add_outcome(pair["sampled_counts"][identity], trace)
            _add_outcome(pair["orientation_counts"][identity][game["transform"]], trace)

        telemetry_row = telemetry_rows[game["slot_id"]]
        pair["telemetry_statuses"].append(telemetry_row["status"])
        if identity == ATLAS_DEPTH1_STRENGTH_ID_V1:
            pair["depth1_telemetry_statuses"].append(telemetry_row["status"])
        admissible = row["status"] == "COMPLETE"
        if not telemetry_all_blocked:
            if admissible and telemetry_row["status"] == "NOT_ADMISSIBLE":
                raise ValueError("COMPLETE sampled trace is telemetry-NOT_ADMISSIBLE")
            if not admissible and telemetry_row["status"] != "NOT_ADMISSIBLE":
                raise ValueError("noncomplete sampled trace is telemetry-admissible")
        telemetry_record = telemetry_by_id.get(game["slot_id"])
        if telemetry_record is not None:
            if sampled is None:
                raise ValueError("telemetry raw record lacks sampled raw evidence")
            _validate_telemetry_record(telemetry_record, game, sampled)
        if telemetry_row["status"] == "VALIDATED":
            values = _telemetry_metric_values(telemetry_record)
            if identity == ATLAS_DEPTH1_STRENGTH_ID_V1:
                for role in ("A", "B"):
                    pair["forced"][role]["decisions"] += values["roles"][role][
                        "decisions"
                    ]
                    pair["forced"][role]["forced"] += values["roles"][role][
                        "forced"
                    ]
                pair["reciprocal_games"] += int(values["reciprocal"])
    if joined_count != ATLAS_SAMPLED_GAME_COUNT_V1:
        raise ValueError("game schedule denominator drifted")

    pair_inputs = []
    for pair in sorted(pairs.values(), key=lambda value: value["pair_index"]):
        channel_statuses = {
            "exact": _reduced_channel_status(
                pair["exact_statuses"] + pair["pv_statuses"]
            ),
            "random": _reduced_channel_status(
                pair["sampled_statuses"][ATLAS_RANDOM_STRENGTH_ID_V1]
            ),
            "terminal_depth1": _reduced_channel_status(
                pair["sampled_statuses"][ATLAS_DEPTH1_STRENGTH_ID_V1]
            ),
            "telemetry": _reduced_channel_status(
                pair["telemetry_statuses"], telemetry=True
            ),
        }
        sampled_summaries = {}
        d4_summaries = {}
        for identity in (ATLAS_RANDOM_STRENGTH_ID_V1, ATLAS_DEPTH1_STRENGTH_ID_V1):
            status = _metric_subset_status(pair["sampled_statuses"][identity])
            sampled_summaries[identity] = _sampled_summary(
                status, pair["sampled_counts"][identity]
            )
            d4_summaries[identity] = {}
            for transform in ATLAS_D4_TRANSFORMS_V1:
                orientation_status = _metric_subset_status(
                    pair["orientation_statuses"][identity][transform]
                )
                d4_summaries[identity][transform] = _inspection_outcome_summary(
                    orientation_status,
                    16,
                    pair["orientation_counts"][identity][transform],
                )
        telemetry_metric_status = _metric_subset_status(
            pair["depth1_telemetry_statuses"], telemetry=True
        )
        pair_inputs.append(
            {
                "pair_index": pair["pair_index"],
                "paired_mechanical_d4_identity": pair[
                    "paired_mechanical_d4_identity"
                ],
                "family_id": pair["family_id"],
                "paired_stratum_id": pair["paired_stratum_id"],
                "channel_statuses": channel_statuses,
                "exact_members": pair["exact_members"],
                "exact_utilization": pair["exact_utilization"],
                "sampled_summaries": sampled_summaries,
                "d4_summaries": d4_summaries,
                "depth1_ply_summary": _inspection_outcome_summary(
                    _metric_subset_status(
                        pair["sampled_statuses"][ATLAS_DEPTH1_STRENGTH_ID_V1]
                    ),
                    128,
                    pair["sampled_counts"][ATLAS_DEPTH1_STRENGTH_ID_V1],
                ),
                "forced_input": {
                    role: {
                        "status": telemetry_metric_status,
                        "decision_count": pair["forced"][role]["decisions"],
                        "forced_decision_count": pair["forced"][role]["forced"],
                    }
                    for role in ("A", "B")
                },
                "reciprocal_input": {
                    "status": telemetry_metric_status,
                    "scheduled_games": 128,
                    "completed_games": sum(
                        status == "VALIDATED"
                        for status in pair["depth1_telemetry_statuses"]
                    ),
                    "reciprocal_games": pair["reciprocal_games"],
                },
            }
        )

    channel_counts = {
        "exact": exact_ledger["status_counts"],
        "exact_pv_replay": pv_ledger["status_counts"],
        "random": random_ledger["status_counts"],
        "terminal_depth1": depth1_ledger["status_counts"],
        "telemetry": telemetry_ledger["status_counts"],
    }
    input_roots = {
        "exact_ledger_root": exact_ledger["ledger_root"],
        "pv_ledger_root": pv_ledger["ledger_root"],
        "random_ledger_root": random_ledger["ledger_root"],
        "depth1_ledger_root": depth1_ledger["ledger_root"],
        "telemetry_ledger_root": telemetry_ledger["ledger_root"],
        "exact_records_root": _ordered_input_root("exact", exact_records),
        "pv_records_root": _ordered_input_root("exact-pv", pv_records),
        "random_records_root": _ordered_input_root("random", random_records),
        "depth1_records_root": _ordered_input_root("terminal-depth1", depth1_records),
        "telemetry_records_root": _ordered_input_root("telemetry", telemetry_records),
    }
    return {
        "manifest_root": manifest["manifest_root"],
        "input_roots": input_roots,
        "channel_counts": channel_counts,
        "pair_inputs": pair_inputs,
    }


def _fixed_denominators() -> Dict[str, int]:
    return {
        "exact_definition_slots": 288,
        "exact_pv_replay_slots": 2_304,
        "exact_pair_slots": 144,
        "sampled_games_total": 36_864,
        "telemetry_slots_total": 36_864,
        "sampled_games_per_strength": 18_432,
        "sampled_games_per_pair_strength": 128,
        "matched_start_blocks_total": 18_432,
        "matched_start_blocks_per_pair_strength": 64,
        "games_per_member_pair_strength": 64,
        "games_per_orientation_pair_strength": 16,
        "games_per_seed_pair_strength": 16,
    }


def _meta_terminal_projection_v1(
    terminal_value: Any,
    expected_stage: Tuple[str, str],
    expected_lifecycle: Sequence[str],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    terminal = _exact_fields(
        _json_copy(terminal_value, "meta-failure parent terminal seal"),
        ("artifact_type", "identity", "payload", "references"),
        "meta-failure parent terminal seal",
    )
    if terminal["artifact_type"] != "ATLAS_STAGE_TERMINAL_SEAL_V1":
        raise ValueError("meta-failure parent is not a terminal seal")
    identity = _sha256(terminal["identity"], "meta-failure terminal identity")
    payload = _exact_fields(
        terminal["payload"],
        (
            "attempt_id_or_null",
            "blocked_id_or_null",
            "completed_root_or_null",
            "failure_root_or_null",
            "lifecycle",
            "orphaned_id_or_null",
            "partial_evidence_root_or_null",
            "reservation_id_or_null",
            "stage_id",
            "stage_protocol_id",
        ),
        "meta-failure terminal payload",
    )
    if (
        payload["stage_id"] != expected_stage[0]
        or payload["stage_protocol_id"] != expected_stage[1]
        or payload["lifecycle"] not in expected_lifecycle
    ):
        raise ValueError("meta-failure terminal stage or lifecycle drifted")
    return terminal, {
        "stage_id": expected_stage[0],
        "stage_protocol_id": expected_stage[1],
        "lifecycle": payload["lifecycle"],
        "terminal_seal_identity": identity,
    }


def _validate_blocked_meta_parent_v1(
    terminal: Mapping[str, Any],
    preceding_terminals: Sequence[Mapping[str, Any]],
    manifest_terminal_identity: str,
) -> None:
    payload = terminal["payload"]
    references = _exact_fields(
        terminal["references"],
        (
            "blocked",
            "completed",
            "failure",
            "orphaned",
            "partial_evidence",
            "stage_attempt",
            "stage_reservation",
        ),
        "BLOCKED terminal references",
    )
    if any(
        references[key] is not None
        for key in (
            "completed",
            "failure",
            "orphaned",
            "partial_evidence",
            "stage_attempt",
            "stage_reservation",
        )
    ):
        raise ValueError("BLOCKED meta parent retains incompatible evidence")
    blocked = _exact_fields(
        references["blocked"],
        ("artifact_type", "identity", "payload", "references"),
        "BLOCKED meta parent artifact",
    )
    if (
        blocked["artifact_type"] != "ATLAS_STAGE_BLOCKED_V1"
        or _sha256(blocked["identity"], "BLOCKED artifact identity")
        != payload["blocked_id_or_null"]
    ):
        raise ValueError("BLOCKED meta parent identity drifted")
    blocked_payload = blocked["payload"]
    if (
        type(blocked_payload) is not dict
        or blocked_payload.get("stage_id") != payload["stage_id"]
        or blocked_payload.get("stage_protocol_id") != payload["stage_protocol_id"]
        or blocked_payload.get("failed_prerequisite_stage_id")
        != _MANIFEST_PARENT[0]
        or blocked_payload.get("prerequisite_terminal_seal")
        != manifest_terminal_identity
    ):
        raise ValueError("BLOCKED meta parent prerequisite binding drifted")
    blocked_references = blocked["references"]
    if type(blocked_references) is not dict:
        raise ValueError("BLOCKED meta parent references are missing")
    ordered = blocked_references.get("ordered_parent_terminal_seals")
    if type(ordered) is not list or [
        value.get("identity") if type(value) is dict else None for value in ordered
    ] != [value["identity"] for value in preceding_terminals]:
        raise ValueError("BLOCKED meta parent chain differs from prior terminals")
    prerequisite = blocked_references.get("prerequisite_terminal_seal")
    if (
        type(prerequisite) is not dict
        or prerequisite.get("identity") != manifest_terminal_identity
    ):
        raise ValueError("BLOCKED meta parent points at another prerequisite")


def _validate_manifest_unavailable_meta_report_v1(
    stored_value: Any,
    protocol_value: Any,
    parent_terminal_seals_value: Any,
) -> Dict[str, Any]:
    """Rebuild a candidate-neutral report without reading any outcome artifact."""

    protocol = _json_copy(protocol_value, "meta-failure protocol")
    if (
        type(protocol) is not dict
        or protocol.get("protocol_id") != ATLAS_PROTOCOL_ID_V1
        or protocol.get("protocol_root") != ATLAS_PROTOCOL_ROOT_V1
    ):
        raise ValueError("meta-failure protocol identity drifted")
    if type(parent_terminal_seals_value) not in (list, tuple):
        raise TypeError("meta-failure parent terminals must be an exact sequence")
    if len(parent_terminal_seals_value) != len(_META_PARENT_ORDER_V1):
        raise ValueError("meta-failure report requires all five parent terminals")
    terminals = []
    projections = []
    for index, (terminal_value, expected_stage) in enumerate(
        zip(parent_terminal_seals_value, _META_PARENT_ORDER_V1)
    ):
        allowed_lifecycles = ("FAILED", "ORPHANED") if index == 0 else ("BLOCKED",)
        terminal, projection = _meta_terminal_projection_v1(
            terminal_value, expected_stage, allowed_lifecycles
        )
        terminals.append(terminal)
        projections.append(projection)
    identities = [value["terminal_seal_identity"] for value in projections]
    if len(set(identities)) != len(identities):
        raise ValueError("meta-failure parent terminal identities repeat")
    for index, terminal in enumerate(terminals[1:], 1):
        _validate_blocked_meta_parent_v1(
            terminal, terminals[:index], identities[0]
        )
    unsigned = {
        "report_version": ATLAS_ASSESSMENT_REPORT_VERSION_V1,
        "report_id": "plan0013-atlas-development-manifest-unavailable-v1",
        "report_kind": "MANIFEST_UNAVAILABLE_META_FAILURE",
        "status": "EXPERIMENT_INVALID_BEFORE_DEVELOPMENT_OUTCOMES",
        "claim_level": "EXPERIMENT_VALIDITY_ONLY_NO_GAMEPLAY_CLAIM",
        "protocol_id": ATLAS_PROTOCOL_ID_V1,
        "protocol_root": ATLAS_PROTOCOL_ROOT_V1,
        "manifest_root_or_null": None,
        "fixed_denominators": _fixed_denominators(),
        "fixed_denominators_source": "bootstrap-protocol-constants-only",
        "gameplay_outcome_record_count": 0,
        "candidate_definition_read_or_export_count": 0,
        "raw_parent_result_read_count": 0,
        "formal_pair_assessment_count": 0,
        "formal_family_or_pair_labels": "FORBIDDEN",
        "inspection_selected_pair_count": 0,
        "manifest_terminal": projections[0],
        "blocked_downstream_terminals": projections[1:],
    }
    expected = {
        **unsigned,
        "report_root": domain_identity(
            _META_FAILURE_REPORT_ROOT_DOMAIN_V1, unsigned
        ),
    }
    if stored_value is not None:
        stored_entry = canonical_json_bytes(stored_value)
        if stored_entry != canonical_json_bytes(expected):
            raise ValueError("meta-failure report does not reconstruct")
        if canonical_json_bytes(stored_value) != stored_entry:
            raise ValueError("meta-failure report changed during validation")
    return _json_copy(expected, "validated meta-failure report")


def _build_manifest_unavailable_meta_report_v1(
    protocol_value: Any, parent_terminal_seals_value: Any
) -> Dict[str, Any]:
    return _validate_manifest_unavailable_meta_report_v1(
        None, protocol_value, parent_terminal_seals_value
    )


def _validate_reconstructed_assessment_v1(
    stored_value: Any,
    *,
    protocol_id: str,
    protocol_root: str,
    manifest_root: str,
    input_roots: Mapping[str, Any],
    channel_counts: Mapping[str, Any],
    pair_inputs: Any,
) -> Dict[str, Any]:
    """Formal validator; this is the sole caller of protocol private helpers."""

    if type(pair_inputs) is not list or len(pair_inputs) != ATLAS_DEVELOPMENT_PAIR_COUNT_V1:
        raise ValueError("formal assessment requires exactly 144 reconstructed pairs")
    pairs = []
    for index, raw in enumerate(pair_inputs):
        value = _json_copy(raw, "reconstructed pair input")
        if value.get("pair_index") != index:
            raise ValueError("reconstructed pair inputs are not in manifest order")
        statuses = value["channel_statuses"]
        exact_error = _evidence_label(statuses["exact"])
        random_error = _evidence_label(statuses["random"])
        depth_error = _evidence_label(statuses["terminal_depth1"])
        exact_label = (
            exact_error
            if exact_error is not None
            else _protocol._classify_atlas_exact_pair_v1(
                value["exact_members"]["A_FIRST"],
                value["exact_members"]["B_FIRST"],
            )
        )
        random_label = (
            random_error
            if random_error is not None
            else _protocol._classify_atlas_sampled_strength_v1(
                value["sampled_summaries"][ATLAS_RANDOM_STRENGTH_ID_V1]
            )
        )
        depth_label = (
            depth_error
            if depth_error is not None
            else _protocol._classify_atlas_sampled_strength_v1(
                value["sampled_summaries"][ATLAS_DEPTH1_STRENGTH_ID_V1]
            )
        )
        assessment = _protocol._classify_atlas_pair_frontier_v1(
            exact_label, random_label, depth_label
        )
        metrics = {
            "exact_state_utilization": _protocol._calculate_exact_state_utilization_v1(
                value["exact_utilization"]
            ),
            "strength_role_share_gap": _protocol._calculate_strength_role_share_gap_v1(
                {
                    identity: _inspection_outcome_summary(
                        summary["status"], 128, {
                            "completed": summary["completed_games"],
                            "A": summary["a_wins"],
                            "B": summary["b_wins"],
                            "DRAW_PLY_LIMIT": summary["draws"],
                        }
                    )
                    for identity, summary in value["sampled_summaries"].items()
                }
            ),
            "d4_outcome_range": {
                identity: _protocol._calculate_d4_outcome_range_v1(
                    value["d4_summaries"][identity], identity
                )
                for identity in (
                    ATLAS_RANDOM_STRENGTH_ID_V1,
                    ATLAS_DEPTH1_STRENGTH_ID_V1,
                )
            },
            "depth1_ply_limit_rate": _protocol._calculate_depth1_ply_limit_rate_v1(
                value["depth1_ply_summary"]
            ),
            "forced_decision_fraction": _protocol._calculate_forced_decision_fractions_v1(
                value["forced_input"]
            ),
            "depth1_reciprocal_dependency_fraction": (
                _protocol._calculate_depth1_reciprocal_dependency_fraction_v1(
                    value["reciprocal_input"]
                )
            ),
        }
        pairs.append(
            {
                "pair_index": index,
                "paired_mechanical_d4_identity": value[
                    "paired_mechanical_d4_identity"
                ],
                "family_id": value["family_id"],
                "paired_stratum_id": value["paired_stratum_id"],
                "channel_statuses": statuses,
                "exact_label": exact_label,
                "random_label": random_label,
                "terminal_depth1_label": depth_label,
                "pair_assessment": assessment,
                "metrics": metrics,
            }
        )

    families = []
    for family_id in ATLAS_FAMILY_ORDER_V1:
        family_pairs = [pair for pair in pairs if pair["family_id"] == family_id]
        calculation = _protocol._assess_atlas_family_frontier_v1(
            [
                {
                    "paired_mechanical_d4_identity": pair[
                        "paired_mechanical_d4_identity"
                    ],
                    "paired_stratum_id": pair["paired_stratum_id"],
                    "assessment": pair["pair_assessment"],
                }
                for pair in family_pairs
            ]
        )
        calculation["formal_evidence"] = True
        families.append({"family_id": family_id, **calculation})
    inspection = _protocol._calculate_atlas_inspection_selection_v1(pairs)

    formal_statuses = [
        pair["channel_statuses"][channel]
        for pair in pairs
        for channel in _FORMAL_CHANNELS
    ]
    telemetry_statuses = [pair["channel_statuses"]["telemetry"] for pair in pairs]
    if any(status in ("INVALID", "PROOF_CONTRADICTION") for status in formal_statuses):
        report_status = "EVIDENCE_INVALID"
    elif any(status != "COMPLETE" for status in formal_statuses):
        report_status = "INCONCLUSIVE_INCOMPLETE"
    elif any(status != "COMPLETE" for status in telemetry_statuses):
        report_status = "FORMAL_COMPLETE_WITH_TELEMETRY_EXCEPTION"
    else:
        report_status = "FORMAL_COMPLETE"
    unsigned = {
        "report_version": ATLAS_ASSESSMENT_REPORT_VERSION_V1,
        "report_id": "plan0013-atlas-development-assessment-report-v1",
        "status": report_status,
        "claim_level": "FAMILY_FRONTIER_SIGNAL_NOT_FAIR_GAME",
        "formal_evidence": True,
        "protocol_id": protocol_id,
        "protocol_root": protocol_root,
        "manifest_root": _sha256(manifest_root, "assessment manifest root"),
        "input_roots": _json_copy(input_roots, "assessment input roots"),
        "fixed_denominators": _fixed_denominators(),
        "channel_counts": _json_copy(channel_counts, "assessment channel counts"),
        "pair_count": len(pairs),
        "pairs": pairs,
        "family_count": len(families),
        "families": families,
        "inspection_selection_formally_bound": True,
        "inspection_selection": inspection,
    }
    expected = {
        **unsigned,
        "report_root": domain_identity(_REPORT_ROOT_DOMAIN_V1, unsigned),
    }
    if stored_value is not None:
        entry = canonical_json_bytes(stored_value)
        if entry != canonical_json_bytes(expected):
            raise ValueError("assessment report does not reconstruct from raw evidence")
        if canonical_json_bytes(stored_value) != entry:
            raise ValueError("assessment report changed during validation")
    return _json_copy(expected, "validated assessment report")


def _validate_atlas_assessment_report_v1(
    stored_value: Any,
    manifest_value: Any,
    protocol_value: Any,
    exact_ledger_value: Any,
    pv_ledger_value: Any,
    random_ledger_value: Any,
    depth1_ledger_value: Any,
    telemetry_ledger_value: Any,
    exact_records_value: Any,
    pv_records_value: Any,
    random_records_value: Any,
    depth1_records_value: Any,
    telemetry_records_value: Any,
) -> Dict[str, Any]:
    reconstructed = _validate_protocol_raw_inputs_v1(
        manifest_value,
        protocol_value,
        exact_ledger_value,
        pv_ledger_value,
        random_ledger_value,
        depth1_ledger_value,
        telemetry_ledger_value,
        exact_records_value,
        pv_records_value,
        random_records_value,
        depth1_records_value,
        telemetry_records_value,
    )
    return _validate_reconstructed_assessment_v1(
        stored_value,
        protocol_id=ATLAS_PROTOCOL_ID_V1,
        protocol_root=ATLAS_PROTOCOL_ROOT_V1,
        manifest_root=reconstructed["manifest_root"],
        input_roots=reconstructed["input_roots"],
        channel_counts=reconstructed["channel_counts"],
        pair_inputs=reconstructed["pair_inputs"],
    )


def _build_atlas_assessment_report_v1(
    manifest_value: Any,
    protocol_value: Any,
    exact_ledger_value: Any,
    pv_ledger_value: Any,
    random_ledger_value: Any,
    depth1_ledger_value: Any,
    telemetry_ledger_value: Any,
    exact_records_value: Any,
    pv_records_value: Any,
    random_records_value: Any,
    depth1_records_value: Any,
    telemetry_records_value: Any,
) -> Dict[str, Any]:
    return _validate_atlas_assessment_report_v1(
        None,
        manifest_value,
        protocol_value,
        exact_ledger_value,
        pv_ledger_value,
        random_ledger_value,
        depth1_ledger_value,
        telemetry_ledger_value,
        exact_records_value,
        pv_records_value,
        random_records_value,
        depth1_records_value,
        telemetry_records_value,
    )


def _assessment_parent_inputs_v1(
    store: ImmutableEvidenceStore,
    protocol_value: Any,
    parent_terminal_seals: Sequence[Mapping[str, Any]],
) -> Tuple[Any, ...]:
    by_stage = {
        seal["payload"]["stage_id"]: seal for seal in parent_terminal_seals
    }
    if len(by_stage) != len(parent_terminal_seals):
        raise ValueError("assessment parent terminal seals repeat a stage")

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
    all_games = tuple(
        iter_frozen_atlas_game_schedule_from_protocol_v1(protocol_value)
    )
    random_ids = tuple(
        slot["slot_id"]
        for slot in all_games
        if slot["strength"]["identity"] == ATLAS_RANDOM_STRENGTH_ID_V1
    )
    depth1_ids = tuple(
        slot["slot_id"]
        for slot in all_games
        if slot["strength"]["identity"] == ATLAS_DEPTH1_STRENGTH_ID_V1
    )
    telemetry_ids = tuple(slot["slot_id"] for slot in all_games)

    exact_set, exact_lifecycle, exact_contract = _sealed_parent_ledger_set_v1(
        store,
        protocol_value,
        by_stage[_EXACT_PARENT[0]],
        *_EXACT_PARENT,
    )
    if exact_lifecycle == "BLOCKED":
        exact_ledger = reconcile_atlas_exact_status_ledger_v1(
            protocol_value, [], [], blocked=True
        )
        pv_ledger = reconcile_atlas_pv_status_ledger_v1(
            protocol_value, [], [], blocked=True
        )
        exact_records: List[Dict[str, Any]] = []
        pv_records: List[Dict[str, Any]] = []
    else:
        if exact_set["phase_ids"] != ["exact", "exact-pv"]:
            raise ValueError("exact parent phase set drifted")
        exact_observed, exact_started, exact_records = _phase_projection_v1(
            store,
            exact_contract,
            exact_set,
            "exact",
            exact_ids,
            ("COMPLETE", "INCOMPLETE", "INVALID", "PROOF_CONTRADICTION"),
            "INCOMPLETE",
            "NOT_RUN",
        )
        pv_observed, pv_started, pv_records = _phase_projection_v1(
            store,
            exact_contract,
            exact_set,
            "exact-pv",
            pv_ids,
            ("VALID", "INCOMPLETE", "INVALID", "PROOF_CONTRADICTION"),
            "INCOMPLETE",
            "NOT_RUN",
        )
        exact_ledger = reconcile_atlas_exact_status_ledger_v1(
            protocol_value, exact_observed, exact_started
        )
        pv_ledger = reconcile_atlas_pv_status_ledger_v1(
            protocol_value, pv_observed, pv_started
        )

    sampled_values = []
    sampled_records = []
    for stage, phase_id, strength, expected_ids in (
        (_RANDOM_PARENT, "random", ATLAS_RANDOM_STRENGTH_ID_V1, random_ids),
        (_DEPTH1_PARENT, "depth1", ATLAS_DEPTH1_STRENGTH_ID_V1, depth1_ids),
    ):
        ledger_set, lifecycle, contract = _sealed_parent_ledger_set_v1(
            store, protocol_value, by_stage[stage[0]], *stage
        )
        if lifecycle == "BLOCKED":
            ledger = reconcile_atlas_sampled_status_ledger_v1(
                protocol_value, strength, [], [], blocked=True
            )
            records: List[Dict[str, Any]] = []
        else:
            if ledger_set["phase_ids"] != [phase_id]:
                raise ValueError("sampled parent phase set drifted")
            observed, started, records = _phase_projection_v1(
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
                protocol_value, strength, observed, started
            )
        sampled_values.append(ledger)
        sampled_records.append(records)
    random_ledger, depth1_ledger = sampled_values
    random_records, depth1_records = sampled_records

    sampled_statuses = {
        row["slot_id"]: row["status"]
        for row in random_ledger["rows"] + depth1_ledger["rows"]
    }
    admissible = [
        slot_id for slot_id in telemetry_ids if sampled_statuses[slot_id] == "COMPLETE"
    ]
    nonadmissible = [
        slot_id for slot_id in telemetry_ids if sampled_statuses[slot_id] != "COMPLETE"
    ]
    telemetry_set, telemetry_lifecycle, telemetry_contract = (
        _sealed_parent_ledger_set_v1(
            store,
            protocol_value,
            by_stage[_TELEMETRY_PARENT[0]],
            *_TELEMETRY_PARENT,
        )
    )
    if telemetry_lifecycle == "BLOCKED":
        telemetry_ledger = reconcile_atlas_telemetry_status_ledger_v1(
            protocol_value, [], [], admissible, blocked=True
        )
        telemetry_records: List[Dict[str, Any]] = []
    else:
        if telemetry_set["phase_ids"] != ["telemetry"]:
            raise ValueError("telemetry parent phase set drifted")
        telemetry_observed, telemetry_started, telemetry_records = (
            _phase_projection_v1(
                store,
                telemetry_contract,
                telemetry_set,
                "telemetry",
                telemetry_ids,
                ("VALIDATED", "INVALID", "PROOF_CONTRADICTION"),
                "MISSING",
                "MISSING",
                preclassified_slot_ids=nonadmissible,
                preclassified_status="NOT_ADMISSIBLE",
            )
        )
        telemetry_ledger = reconcile_atlas_telemetry_status_ledger_v1(
            protocol_value,
            telemetry_observed,
            telemetry_started,
            admissible,
        )
    return (
        exact_ledger,
        pv_ledger,
        random_ledger,
        depth1_ledger,
        telemetry_ledger,
        exact_records,
        pv_records,
        random_records,
        depth1_records,
        telemetry_records,
    )


def _assessment_prerequisites_v1(
    contract: StageContract, parent_seals: Sequence[Any]
) -> None:
    if len(parent_seals) != len(contract.required_parent_terminal_predicates):
        raise ValueError("assessment parent terminal count drifted")
    for (stage_id, predicate), seal in zip(
        contract.required_parent_terminal_predicates, parent_seals
    ):
        if seal["payload"]["stage_id"] != stage_id:
            raise ValueError("assessment parent terminal order drifted")
        if predicate != "TERMINAL_SEAL_PRESENT":
            raise ValueError("assessment parent predicate must be terminal-seal-present")
