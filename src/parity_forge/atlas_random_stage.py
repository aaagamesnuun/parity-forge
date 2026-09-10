"""Concrete random-play compute stage for the frozen Plan-0013 atlas."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

from .atlas_protocol import (
    ATLAS_ACTION_CANDIDATE_CAP_V1,
    ATLAS_GAME_PLY_CAP_V1,
    ATLAS_SAMPLED_GAME_COUNT_V1,
    ATLAS_SEEDS_V1,
    iter_frozen_atlas_game_schedule_from_protocol_v1,
)
from .atlas_stage_data import (
    ATLAS_COMPLETE_TRACE_VERSION_V1,
    ATLAS_RANDOM_STRENGTH_ID_V1,
    iter_joined_atlas_game_definitions_v1,
    validate_complete_atlas_trace_v1,
)
from .atlas_evidence import (
    ImmutableEvidenceStore,
    LedgerSpec,
    StageContract,
    begin_stage,
    block_stage,
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
from .agents import RandomAgent


ATLAS_RANDOM_STAGE_ID_V1 = "RANDOM_ALL_18432_GAMES"
ATLAS_RANDOM_STAGE_PROTOCOL_ID_V1 = "plan0013-atlas-development-random-v1"
ATLAS_RANDOM_GAME_RECORD_VERSION_V1 = 1

_RANDOM_GAME_RECORD_DOMAIN_V1 = (
    b"parity-forge:plan0013:random-game-record:v1\0"
)
_RANDOM_PHASE_ID_V1 = "random"
_RANDOM_STAGE_SUMMARY_DOMAIN_V1 = (
    b"parity-forge:plan0013:random-stage-summary:v1\0"
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


def _sealed_definition(value: Any, expected_hash: Any):
    entry = canonical_json_bytes(value)
    body = json.loads(entry.decode("utf-8"))
    definition = parse_definition(body)
    if canonical_json_bytes(definition.to_dict()) != entry:
        raise ValueError("random game definition is not a canonical DSL body")
    if definition_hash(definition) != _sha256(
        expected_hash, "random game definition hash"
    ):
        raise ValueError("random game definition differs from its schedule hash")
    return definition, body, entry


def _invalid_random_game_record_v1(
    game_slot_value: Any, error: BaseException
) -> Dict[str, Any]:
    game_slot = _json_copy(game_slot_value, "invalid random game slot")
    unsigned = {
        "record_version": ATLAS_RANDOM_GAME_RECORD_VERSION_V1,
        "record_kind": "SAMPLED_GAME",
        "strength_identity": ATLAS_RANDOM_STRENGTH_ID_V1,
        "status": "INVALID",
        "game_slot_id": _sha256(
            game_slot.get("slot_id"), "invalid random game slot identity"
        ),
        "profile_slot_id": game_slot.get("profile_slot_id"),
        "ordered_role_slot_ids": game_slot.get("ordered_role_slot_ids"),
        "matched_start_block_id": game_slot.get("matched_start_block_id"),
        "seed_index": game_slot.get("seed_index"),
        "seed": game_slot.get("seed"),
        "definition_hash": game_slot.get("transformed_definition_hash"),
        "definition_byte_count": None,
        "agent_a": ATLAS_RANDOM_STRENGTH_ID_V1,
        "agent_b": ATLAS_RANDOM_STRENGTH_ID_V1,
        "rng_scope": game_slot.get("rng_scope"),
        "rng_stream": game_slot.get("rng_stream"),
        "decisions": [],
        "node_ledger_or_null": None,
        "complete_trace_or_null": None,
        "censored_prefix_or_null": {
            "kind": "RANDOM_GAME_EXCEPTION",
            "exception_module": type(error).__module__,
            "exception_type": type(error).__qualname__,
            "message": str(error),
        },
    }
    return {
        **unsigned,
        "record_root": domain_identity(_RANDOM_GAME_RECORD_DOMAIN_V1, unsigned),
    }


def _fresh_random_role_agents_v1() -> Dict[Player, RandomAgent]:
    agents = {Player.A: RandomAgent(), Player.B: RandomAgent()}
    if agents[Player.A] is agents[Player.B]:
        raise AssertionError("random role slots must use distinct agent instances")
    return agents


def _validate_random_role_agents_v1(agents: Any) -> Mapping[Player, RandomAgent]:
    if type(agents) is not dict or set(agents) != {Player.A, Player.B}:
        raise TypeError("random role agents must be an exact A/B mapping")
    if agents[Player.A] is agents[Player.B]:
        raise ValueError("random role agents must be distinct instances")
    if any(type(agent) is not RandomAgent for agent in agents.values()):
        raise TypeError("random role slots require exact RandomAgent instances")
    if any(
        agent.identity.key != ATLAS_RANDOM_STRENGTH_ID_V1
        for agent in agents.values()
    ):
        raise ValueError("random role-agent identity drifted")
    return agents


def _run_random_game_v1(
    game_slot_value: Any,
    definition_value: Any,
    agents_value: Any,
) -> Dict[str, Any]:
    """Play one fixed game with a fresh shared seed stream.

    ``agents_value`` is an internal lifecycle object, not a production
    injection point.  The production driver constructs exactly one distinct A/B
    pair per profile and reuses it for seeds 0 through 7.
    """

    game_slot = _json_copy(game_slot_value, "random game slot")
    if type(game_slot) is not dict:
        raise TypeError("random game slot must be an exact object")
    game_slot_id = _sha256(game_slot.get("slot_id"), "random game slot identity")
    strength = game_slot.get("strength")
    if type(strength) is not dict or strength.get("identity") != ATLAS_RANDOM_STRENGTH_ID_V1:
        raise ValueError("random game slot strength differs from the frozen protocol")
    seed_index = game_slot.get("seed_index")
    seed = game_slot.get("seed")
    if (
        type(seed_index) is not int
        or not 0 <= seed_index < len(ATLAS_SEEDS_V1)
        or type(seed) is not int
        or seed != ATLAS_SEEDS_V1[seed_index]
    ):
        raise ValueError("random game seed differs from the frozen schedule")
    if (
        game_slot.get("rng_scope") != "fresh-random.Random(seed)-per-game"
        or game_slot.get("rng_stream")
        != "one-stream-shared-by-both-roles-in-ply-order"
    ):
        raise ValueError("random game RNG scope differs from the frozen protocol")
    role_slot_ids = game_slot.get("ordered_role_slot_ids")
    if (
        type(role_slot_ids) is not list
        or len(role_slot_ids) != 2
        or len(set(role_slot_ids)) != 2
    ):
        raise ValueError("random game role-slot identities drifted")
    for index, role_slot_id in enumerate(role_slot_ids):
        _sha256(role_slot_id, "random role-slot identity {}".format(index))
    agents = _validate_random_role_agents_v1(agents_value)
    definition, definition_body, definition_entry = _sealed_definition(
        definition_value, game_slot.get("transformed_definition_hash")
    )

    rng = random.Random(seed)
    state = initial_state(definition)
    actions = []
    decisions = []
    while not state.terminal:
        if state.ply >= ATLAS_GAME_PLY_CAP_V1:
            raise AssertionError("random game remained nonterminal at the ply cap")
        available = legal_actions(definition, state)
        if not available:
            raise AssertionError("random game has a nonterminal state without actions")
        if len(available) > ATLAS_ACTION_CANDIDATE_CAP_V1:
            raise AssertionError("random game exceeds the frozen legal-action cap")
        actor = state.to_move
        selected = agents[actor].select_action(definition, state, available, rng)
        if type(selected) is not Action or selected not in available:
            raise ValueError("random agent selected an illegal action")
        selected_body = selected.to_dict()
        decisions.append(
            {
                "ply": state.ply,
                "actor": actor.value,
                "controlled_role_slot_id": role_slot_ids[
                    0 if actor is Player.A else 1
                ],
                "legal_action_count": len(available),
                "selected_action": selected_body,
            }
        )
        actions.append(selected_body)
        state = apply_action(definition, state, selected)
    if state.outcome is None:
        raise AssertionError("random game did not retain its terminal outcome")
    winner = state.outcome.winner.value if state.outcome.winner is not None else None
    trace = {
        "trace_version": ATLAS_COMPLETE_TRACE_VERSION_V1,
        "definition_hash": definition_hash(definition),
        "actions": actions,
        "plies": len(actions),
        "winner": winner,
        "terminal_reason": state.outcome.reason,
    }
    validated_trace = validate_complete_atlas_trace_v1(definition_body, trace)
    unsigned = {
        "record_version": ATLAS_RANDOM_GAME_RECORD_VERSION_V1,
        "record_kind": "SAMPLED_GAME",
        "strength_identity": ATLAS_RANDOM_STRENGTH_ID_V1,
        "status": "COMPLETE",
        "game_slot_id": game_slot_id,
        "profile_slot_id": _sha256(
            game_slot.get("profile_slot_id"), "random profile-slot identity"
        ),
        "ordered_role_slot_ids": list(role_slot_ids),
        "matched_start_block_id": _sha256(
            game_slot.get("matched_start_block_id"), "random matched-start identity"
        ),
        "seed_index": seed_index,
        "seed": seed,
        "definition_hash": definition_hash(definition),
        "definition_byte_count": len(definition_entry),
        "agent_a": agents[Player.A].identity.key,
        "agent_b": agents[Player.B].identity.key,
        "rng_scope": game_slot["rng_scope"],
        "rng_stream": game_slot["rng_stream"],
        "decisions": decisions,
        "node_ledger_or_null": None,
        "complete_trace_or_null": validated_trace,
        "censored_prefix_or_null": None,
    }
    if canonical_json_bytes(definition_value) != definition_entry:
        raise ValueError("random game definition changed during execution")
    return {
        **unsigned,
        "record_root": domain_identity(_RANDOM_GAME_RECORD_DOMAIN_V1, unsigned),
    }


def _validate_random_profile_games_v1(records: Sequence[Mapping[str, Any]]) -> None:
    if len(records) != len(ATLAS_SEEDS_V1):
        raise ValueError("random profile must retain exactly eight seeded games")
    profile_ids = {record.get("profile_slot_id") for record in records}
    role_ids = {tuple(record.get("ordered_role_slot_ids", ())) for record in records}
    if len(profile_ids) != 1 or len(role_ids) != 1:
        raise ValueError("random profile lifecycle coordinates drifted")
    if [record.get("seed") for record in records] != list(ATLAS_SEEDS_V1):
        raise ValueError("random profile seed order drifted")
    if any(record.get("status") != "COMPLETE" for record in records):
        raise ValueError("random profile contains an incomplete game")


def _random_ledger_spec_v1(protocol_value: Any) -> LedgerSpec:
    slot_ids = tuple(
        slot["slot_id"]
        for slot in iter_frozen_atlas_game_schedule_from_protocol_v1(protocol_value)
        if slot["strength"]["identity"] == ATLAS_RANDOM_STRENGTH_ID_V1
    )
    return LedgerSpec(
        phase_id=_RANDOM_PHASE_ID_V1,
        ordered_slot_ids=slot_ids,
        allowed_result_statuses=(
            "COMPLETE",
            "INCOMPLETE",
            "INVALID",
            "PROOF_CONTRADICTION",
        ),
        interrupted_status="INCOMPLETE",
        unobserved_status="NOT_RUN",
    )


def _execute_random_journal_v1(
    store: ImmutableEvidenceStore,
    contract: StageContract,
    manifest_value: Any,
    protocol_value: Any,
) -> Dict[str, Any]:
    if contract.stage_id != ATLAS_RANDOM_STAGE_ID_V1:
        raise ValueError("random compute received another stage contract")
    status_counts = {
        "COMPLETE": 0,
        "INCOMPLETE": 0,
        "INVALID": 0,
        "PROOF_CONTRADICTION": 0,
    }
    outcome_counts = {"A_WIN": 0, "B_WIN": 0, "DRAW": 0}
    total_plies = 0
    result_count = 0
    current_profile_id = None
    agents = None
    profile_records = []
    for joined in iter_joined_atlas_game_definitions_v1(
        manifest_value, protocol_value
    ):
        game_slot = joined["slot"]
        if game_slot["strength"]["identity"] != ATLAS_RANDOM_STRENGTH_ID_V1:
            continue
        if game_slot["profile_slot_id"] != current_profile_id:
            if profile_records and all(
                record["status"] == "COMPLETE" for record in profile_records
            ):
                _validate_random_profile_games_v1(profile_records)
            current_profile_id = game_slot["profile_slot_id"]
            agents = _fresh_random_role_agents_v1()
            profile_records = []
        journal_index = result_count
        store.publish_journal_start(
            contract.stage_protocol_id,
            _RANDOM_PHASE_ID_V1,
            journal_index,
            game_slot["slot_id"],
        )
        try:
            record = _run_random_game_v1(
                game_slot, joined["definition"], agents
            )
        except Exception as error:
            record = _invalid_random_game_record_v1(game_slot, error)
        store.publish_journal_result(
            contract.stage_protocol_id,
            _RANDOM_PHASE_ID_V1,
            journal_index,
            game_slot["slot_id"],
            record["status"],
            record,
        )
        status_counts[record["status"]] += 1
        result_count += 1
        profile_records.append(record)
        if record["status"] == "COMPLETE":
            trace = record["complete_trace_or_null"]
            total_plies += trace["plies"]
            winner = trace["winner"]
            outcome_counts[
                "DRAW" if winner is None else "{}_WIN".format(winner)
            ] += 1
    if profile_records and all(
        record["status"] == "COMPLETE" for record in profile_records
    ):
        _validate_random_profile_games_v1(profile_records)
    if result_count != ATLAS_SAMPLED_GAME_COUNT_V1 // 2:
        raise ValueError("random compute did not traverse all 18,432 game slots")
    summary = {
        "summary_version": 1,
        "stage_id": ATLAS_RANDOM_STAGE_ID_V1,
        "result_count": result_count,
        "status_counts": status_counts,
        "outcome_counts": outcome_counts,
        "completed_ply_total": total_plies,
    }
    return {
        **summary,
        "summary_root": domain_identity(_RANDOM_STAGE_SUMMARY_DOMAIN_V1, summary),
    }


def _prerequisites_pass_v1(contract: StageContract, parent_seals: Sequence[Any]) -> bool:
    if len(parent_seals) != len(contract.required_parent_terminal_predicates):
        raise ValueError("random parent terminal count drifted")
    for (stage_id, predicate), seal in zip(
        contract.required_parent_terminal_predicates, parent_seals
    ):
        if seal["payload"]["stage_id"] != stage_id:
            raise ValueError("random parent terminal order drifted")
        if predicate == "COMPLETED_VALID":
            if seal["payload"]["lifecycle"] != "COMPLETED":
                return False
        elif predicate != "TERMINAL_SEAL_PRESENT":
            raise ValueError("random parent predicate is unknown")
    return True


def _failure_value(error: BaseException) -> Dict[str, Any]:
    return {
        "kind": "RANDOM_STAGE_EXCEPTION",
        "exception_module": type(error).__module__,
        "exception_type": type(error).__qualname__,
        "message": str(error),
    }


def run_atlas_random_stage_v1(repository: str) -> Dict[str, Any]:
    if type(repository) is not str or not repository:
        raise ValueError("repository must be a nonempty exact string")
    repository_path = Path(repository).resolve()
    evidence_root = repository_path / _EVIDENCE_ROOT_RELATIVE_V1
    with ImmutableEvidenceStore(evidence_root) as store:
        with store.stage_lock(ATLAS_RANDOM_STAGE_PROTOCOL_ID_V1):
            inputs = read_authenticated_stage_inputs(store, ATLAS_RANDOM_STAGE_ID_V1)
            if inputs.contract.stage_protocol_id != ATLAS_RANDOM_STAGE_PROTOCOL_ID_V1:
                raise ValueError("random stage protocol identity drifted")
            ledger_specs = (_random_ledger_spec_v1(inputs.protocol),)
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
                    "stage_id": ATLAS_RANDOM_STAGE_ID_V1,
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
                summary = _execute_random_journal_v1(
                    store,
                    inputs.contract,
                    inputs.detached_manifest,
                    inputs.protocol,
                )
                expected = ATLAS_SAMPLED_GAME_COUNT_V1 // 2
                if (
                    summary["result_count"] != expected
                    or summary["status_counts"]["COMPLETE"] != expected
                ):
                    raise ValueError("random stage completion gate was not met")
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
                    "stage_id": ATLAS_RANDOM_STAGE_ID_V1,
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
                    ATLAS_RANDOM_STAGE_PROTOCOL_ID_V1, "completed"
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
                    "stage_id": ATLAS_RANDOM_STAGE_ID_V1,
                    "terminal_seal": terminal["identity"],
                }
            return {
                "lifecycle": "COMPLETED",
                "stage_id": ATLAS_RANDOM_STAGE_ID_V1,
                "summary": summary,
                "terminal_seal": terminal["identity"],
            }


def recover_atlas_random_stage_v1(repository: str) -> Dict[str, Any]:
    if type(repository) is not str or not repository:
        raise ValueError("repository must be a nonempty exact string")
    repository_path = Path(repository).resolve()
    evidence_root = repository_path / _EVIDENCE_ROOT_RELATIVE_V1
    with ImmutableEvidenceStore(evidence_root) as store:
        inputs = read_authenticated_stage_inputs(store, ATLAS_RANDOM_STAGE_ID_V1)
        result = recover_stage(
            store,
            inputs.contract,
            (_random_ledger_spec_v1(inputs.protocol),),
            repository=repository_path,
        )
        return {
            "action": result.action,
            "lifecycle": result.lifecycle,
            "stage_id": ATLAS_RANDOM_STAGE_ID_V1,
            "terminal_seal_or_null": result.terminal_identity,
        }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m parity_forge.atlas_random_stage")
    parser.add_argument("command", choices=("run", "recover"))
    parser.add_argument("--repository", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _build_parser().parse_args(argv)
    if arguments.command == "run":
        result = run_atlas_random_stage_v1(arguments.repository)
    else:
        result = recover_atlas_random_stage_v1(arguments.repository)
    print(canonical_json_bytes(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = (
    "ATLAS_RANDOM_GAME_RECORD_VERSION_V1",
    "ATLAS_RANDOM_STAGE_ID_V1",
    "ATLAS_RANDOM_STAGE_PROTOCOL_ID_V1",
    "recover_atlas_random_stage_v1",
    "run_atlas_random_stage_v1",
)
