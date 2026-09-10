"""Concrete terminal-only depth-1 compute stage for Plan-0013."""

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
    ATLAS_TERMINAL_DEPTH1_ROLE_SLOT_CAP_V1,
    iter_frozen_atlas_game_schedule_from_protocol_v1,
)
from .atlas_stage_data import (
    ATLAS_COMPLETE_TRACE_VERSION_V1,
    ATLAS_DEPTH1_STRENGTH_ID_V1,
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
from .terminal_search import SearchBudgetExceeded, TerminalOnlyMinimaxAgent


ATLAS_DEPTH1_STAGE_ID_V1 = "TERMINAL_DEPTH1_ALL_18432_GAMES"
ATLAS_DEPTH1_STAGE_PROTOCOL_ID_V1 = (
    "plan0013-atlas-development-terminal-depth1-v1"
)
ATLAS_DEPTH1_GAME_RECORD_VERSION_V1 = 1

_DEPTH1_GAME_RECORD_DOMAIN_V1 = (
    b"parity-forge:plan0013:depth1-game-record:v1\0"
)
_DEPTH1_PHASE_ID_V1 = "depth1"
_DEPTH1_STAGE_SUMMARY_DOMAIN_V1 = (
    b"parity-forge:plan0013:depth1-stage-summary:v1\0"
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
        raise ValueError("depth-1 game definition is not a canonical DSL body")
    if definition_hash(definition) != _sha256(
        expected_hash, "depth-1 game definition hash"
    ):
        raise ValueError("depth-1 game definition differs from its schedule hash")
    return definition, body, entry


def _invalid_depth1_game_record_v1(
    game_slot_value: Any, error: BaseException
) -> Dict[str, Any]:
    game_slot = _json_copy(game_slot_value, "invalid depth-1 game slot")
    unsigned = {
        "record_version": ATLAS_DEPTH1_GAME_RECORD_VERSION_V1,
        "record_kind": "SAMPLED_GAME",
        "strength_identity": ATLAS_DEPTH1_STRENGTH_ID_V1,
        "status": "INVALID",
        "game_slot_id": _sha256(
            game_slot.get("slot_id"), "invalid depth-1 game slot identity"
        ),
        "profile_slot_id": game_slot.get("profile_slot_id"),
        "ordered_role_slot_ids": game_slot.get("ordered_role_slot_ids"),
        "matched_start_block_id": game_slot.get("matched_start_block_id"),
        "seed_index": game_slot.get("seed_index"),
        "seed": game_slot.get("seed"),
        "definition_hash": game_slot.get("transformed_definition_hash"),
        "definition_byte_count": None,
        "agent_a": ATLAS_DEPTH1_STRENGTH_ID_V1,
        "agent_b": ATLAS_DEPTH1_STRENGTH_ID_V1,
        "rng_scope": game_slot.get("rng_scope"),
        "rng_stream": game_slot.get("rng_stream"),
        "node_ledger_or_null": None,
        "complete_trace_or_null": None,
        "censored_prefix_or_null": {
            "kind": "DEPTH1_GAME_EXCEPTION",
            "exception_module": type(error).__module__,
            "exception_type": type(error).__qualname__,
            "message": str(error),
        },
    }
    return {
        **unsigned,
        "record_root": domain_identity(_DEPTH1_GAME_RECORD_DOMAIN_V1, unsigned),
    }


def _fresh_depth1_role_agents_v1() -> Dict[Player, TerminalOnlyMinimaxAgent]:
    agents = {
        player: TerminalOnlyMinimaxAgent(
            depth=1,
            max_total_nodes=ATLAS_TERMINAL_DEPTH1_ROLE_SLOT_CAP_V1,
        )
        for player in (Player.A, Player.B)
    }
    if agents[Player.A] is agents[Player.B]:
        raise AssertionError("depth-1 role slots must use distinct instances")
    # This is the one and only reset for each role slot, before seed 0.
    for player in (Player.A, Player.B):
        agents[player].reset_budget()
    return agents


def _validate_depth1_role_agents_v1(
    agents: Any,
) -> Mapping[Player, TerminalOnlyMinimaxAgent]:
    if type(agents) is not dict or set(agents) != {Player.A, Player.B}:
        raise TypeError("depth-1 role agents must be an exact A/B mapping")
    if agents[Player.A] is agents[Player.B]:
        raise ValueError("depth-1 role agents must be distinct instances")
    if any(type(agent) is not TerminalOnlyMinimaxAgent for agent in agents.values()):
        raise TypeError("depth-1 role slots require exact terminal-only agents")
    if any(
        agent.identity.key != ATLAS_DEPTH1_STRENGTH_ID_V1
        or agent.depth != 1
        or agent.max_total_nodes != ATLAS_TERMINAL_DEPTH1_ROLE_SLOT_CAP_V1
        for agent in agents.values()
    ):
        raise ValueError("depth-1 role-agent contract drifted")
    return agents


def _run_depth1_game_v1(
    game_slot_value: Any,
    definition_value: Any,
    agents_value: Any,
) -> Dict[str, Any]:
    """Play one fixed seeded game, retaining a prefix on node exhaustion."""

    game_slot = _json_copy(game_slot_value, "depth-1 game slot")
    if type(game_slot) is not dict:
        raise TypeError("depth-1 game slot must be an exact object")
    game_slot_id = _sha256(game_slot.get("slot_id"), "depth-1 game slot identity")
    strength = game_slot.get("strength")
    if type(strength) is not dict or strength.get("identity") != ATLAS_DEPTH1_STRENGTH_ID_V1:
        raise ValueError("depth-1 strength differs from the frozen protocol")
    if (
        strength.get("depth") != 1
        or strength.get("max_total_nodes_per_role_slot")
        != ATLAS_TERMINAL_DEPTH1_ROLE_SLOT_CAP_V1
    ):
        raise ValueError("depth-1 search controls differ from the frozen protocol")
    seed_index = game_slot.get("seed_index")
    seed = game_slot.get("seed")
    if (
        type(seed_index) is not int
        or not 0 <= seed_index < len(ATLAS_SEEDS_V1)
        or type(seed) is not int
        or seed != ATLAS_SEEDS_V1[seed_index]
    ):
        raise ValueError("depth-1 seed differs from the frozen schedule")
    if (
        game_slot.get("rng_scope") != "fresh-random.Random(seed)-per-game"
        or game_slot.get("rng_stream")
        != "one-stream-shared-by-both-roles-in-ply-order"
    ):
        raise ValueError("depth-1 RNG scope differs from the frozen protocol")
    role_slot_ids = game_slot.get("ordered_role_slot_ids")
    if (
        type(role_slot_ids) is not list
        or len(role_slot_ids) != 2
        or len(set(role_slot_ids)) != 2
    ):
        raise ValueError("depth-1 role-slot identities drifted")
    for index, role_slot_id in enumerate(role_slot_ids):
        _sha256(role_slot_id, "depth-1 role-slot identity {}".format(index))
    agents = _validate_depth1_role_agents_v1(agents_value)
    definition, definition_body, definition_entry = _sealed_definition(
        definition_value, game_slot.get("transformed_definition_hash")
    )

    rng = random.Random(seed)
    state = initial_state(definition)
    actions = []
    decisions = []
    nodes_before_game = {
        Player.A.value: agents[Player.A].total_nodes,
        Player.B.value: agents[Player.B].total_nodes,
    }
    censor = None
    while not state.terminal:
        if state.ply >= ATLAS_GAME_PLY_CAP_V1:
            raise AssertionError("depth-1 game remained nonterminal at the ply cap")
        available = legal_actions(definition, state)
        if not available:
            raise AssertionError("depth-1 game has a nonterminal state without actions")
        if len(available) > ATLAS_ACTION_CANDIDATE_CAP_V1:
            raise AssertionError("depth-1 game exceeds the frozen legal-action cap")
        actor = state.to_move
        agent = agents[actor]
        nodes_before = agent.total_nodes
        try:
            selected = agent.select_action(definition, state, available, rng)
        except SearchBudgetExceeded as error:
            censor = {
                "kind": "ROLE_SLOT_NODE_CAP_EXHAUSTED",
                "ply": state.ply,
                "actor": actor.value,
                "controlled_role_slot_id": role_slot_ids[
                    0 if actor is Player.A else 1
                ],
                "scope": error.scope,
                "visited_nodes": error.visited_nodes,
                "max_nodes": error.max_nodes,
                "slot_nodes_before_decision": nodes_before,
                "slot_nodes_after_decision": agent.total_nodes,
            }
            break
        if type(selected) is not Action or selected not in available:
            raise ValueError("depth-1 agent selected an illegal action")
        if agent.last_expanded_nodes is None or agent.last_cache_hits is None:
            raise AssertionError("depth-1 agent omitted its node audit")
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
                "expanded_nodes": agent.last_expanded_nodes,
                "cache_hits": agent.last_cache_hits,
                "slot_nodes_before": nodes_before,
                "slot_nodes_after": agent.total_nodes,
                "action_values": [
                    {"action": action.to_dict(), "value_for_a": value}
                    for action, value in agent.last_action_values
                ],
            }
        )
        actions.append(selected_body)
        state = apply_action(definition, state, selected)

    nodes_after_game = {
        Player.A.value: agents[Player.A].total_nodes,
        Player.B.value: agents[Player.B].total_nodes,
    }
    node_ledger = {
        "max_total_nodes_per_role_slot": ATLAS_TERMINAL_DEPTH1_ROLE_SLOT_CAP_V1,
        "role_slot_nodes_before_game": nodes_before_game,
        "role_slot_nodes_after_game": nodes_after_game,
        "decisions": decisions,
    }
    if censor is None:
        if state.outcome is None:
            raise AssertionError("depth-1 game did not retain its terminal outcome")
        winner = (
            state.outcome.winner.value if state.outcome.winner is not None else None
        )
        trace = {
            "trace_version": ATLAS_COMPLETE_TRACE_VERSION_V1,
            "definition_hash": definition_hash(definition),
            "actions": actions,
            "plies": len(actions),
            "winner": winner,
            "terminal_reason": state.outcome.reason,
        }
        complete_trace = validate_complete_atlas_trace_v1(definition_body, trace)
        prefix = None
        status = "COMPLETE"
    else:
        complete_trace = None
        status = "INCOMPLETE"
        prefix = {
            "definition_hash": definition_hash(definition),
            "actions": actions,
            "plies": len(actions),
            "next_actor": state.to_move.value,
            "next_ply": state.ply,
            "censor": censor,
        }
    unsigned = {
        "record_version": ATLAS_DEPTH1_GAME_RECORD_VERSION_V1,
        "record_kind": "SAMPLED_GAME",
        "strength_identity": ATLAS_DEPTH1_STRENGTH_ID_V1,
        "status": status,
        "game_slot_id": game_slot_id,
        "profile_slot_id": _sha256(
            game_slot.get("profile_slot_id"), "depth-1 profile-slot identity"
        ),
        "ordered_role_slot_ids": list(role_slot_ids),
        "matched_start_block_id": _sha256(
            game_slot.get("matched_start_block_id"), "depth-1 matched-start identity"
        ),
        "seed_index": seed_index,
        "seed": seed,
        "definition_hash": definition_hash(definition),
        "definition_byte_count": len(definition_entry),
        "agent_a": agents[Player.A].identity.key,
        "agent_b": agents[Player.B].identity.key,
        "rng_scope": game_slot["rng_scope"],
        "rng_stream": game_slot["rng_stream"],
        "node_ledger_or_null": node_ledger,
        "complete_trace_or_null": complete_trace,
        "censored_prefix_or_null": prefix,
    }
    if canonical_json_bytes(definition_value) != definition_entry:
        raise ValueError("depth-1 definition changed during execution")
    return {
        **unsigned,
        "record_root": domain_identity(_DEPTH1_GAME_RECORD_DOMAIN_V1, unsigned),
    }


def _validate_depth1_profile_games_v1(
    records: Sequence[Mapping[str, Any]],
) -> None:
    if not 1 <= len(records) <= len(ATLAS_SEEDS_V1):
        raise ValueError("depth-1 profile retained an impossible game count")
    if [record.get("seed") for record in records] != list(
        ATLAS_SEEDS_V1[: len(records)]
    ):
        raise ValueError("depth-1 profile seed prefix drifted")
    profile_ids = {record.get("profile_slot_id") for record in records}
    role_ids = {tuple(record.get("ordered_role_slot_ids", ())) for record in records}
    if len(profile_ids) != 1 or len(role_ids) != 1:
        raise ValueError("depth-1 profile lifecycle coordinates drifted")
    incomplete = [index for index, record in enumerate(records) if record.get("status") == "INCOMPLETE"]
    if incomplete and incomplete != [len(records) - 1]:
        raise ValueError("depth-1 censor must terminate its profile seed prefix")
    if any(record.get("status") not in ("COMPLETE", "INCOMPLETE") for record in records):
        raise ValueError("depth-1 profile contains an unknown raw status")


def _depth1_ledger_spec_v1(protocol_value: Any) -> LedgerSpec:
    slot_ids = tuple(
        slot["slot_id"]
        for slot in iter_frozen_atlas_game_schedule_from_protocol_v1(protocol_value)
        if slot["strength"]["identity"] == ATLAS_DEPTH1_STRENGTH_ID_V1
    )
    return LedgerSpec(
        phase_id=_DEPTH1_PHASE_ID_V1,
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


def _execute_depth1_journal_v1(
    store: ImmutableEvidenceStore,
    contract: StageContract,
    manifest_value: Any,
    protocol_value: Any,
) -> Dict[str, Any]:
    if contract.stage_id != ATLAS_DEPTH1_STAGE_ID_V1:
        raise ValueError("depth-1 compute received another stage contract")
    status_counts = {
        "COMPLETE": 0,
        "INCOMPLETE": 0,
        "INVALID": 0,
        "PROOF_CONTRADICTION": 0,
    }
    outcome_counts = {"A_WIN": 0, "B_WIN": 0, "DRAW": 0}
    result_count = 0
    scheduled_count = 0
    total_plies = 0
    total_expanded_nodes = 0
    current_profile_id = None
    agents = None
    profile_records = []
    profile_closed = False
    for joined in iter_joined_atlas_game_definitions_v1(
        manifest_value, protocol_value
    ):
        game_slot = joined["slot"]
        if game_slot["strength"]["identity"] != ATLAS_DEPTH1_STRENGTH_ID_V1:
            continue
        journal_index = scheduled_count
        scheduled_count += 1
        if game_slot["profile_slot_id"] != current_profile_id:
            if profile_records and all(
                record["status"] in ("COMPLETE", "INCOMPLETE")
                for record in profile_records
            ):
                _validate_depth1_profile_games_v1(profile_records)
            current_profile_id = game_slot["profile_slot_id"]
            agents = _fresh_depth1_role_agents_v1()
            profile_records = []
            profile_closed = False
        if profile_closed:
            continue
        store.publish_journal_start(
            contract.stage_protocol_id,
            _DEPTH1_PHASE_ID_V1,
            journal_index,
            game_slot["slot_id"],
        )
        try:
            record = _run_depth1_game_v1(
                game_slot, joined["definition"], agents
            )
        except Exception as error:
            record = _invalid_depth1_game_record_v1(game_slot, error)
        store.publish_journal_result(
            contract.stage_protocol_id,
            _DEPTH1_PHASE_ID_V1,
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
        if record["node_ledger_or_null"] is not None:
            before = record["node_ledger_or_null"]["role_slot_nodes_before_game"]
            after = record["node_ledger_or_null"]["role_slot_nodes_after_game"]
            total_expanded_nodes += (after["A"] - before["A"]) + (
                after["B"] - before["B"]
            )
        if record["status"] != "COMPLETE":
            profile_closed = True
    if profile_records and all(
        record["status"] in ("COMPLETE", "INCOMPLETE")
        for record in profile_records
    ):
        _validate_depth1_profile_games_v1(profile_records)
    expected = ATLAS_SAMPLED_GAME_COUNT_V1 // 2
    if scheduled_count != expected:
        raise ValueError("depth-1 compute did not traverse all 18,432 game slots")
    summary = {
        "summary_version": 1,
        "stage_id": ATLAS_DEPTH1_STAGE_ID_V1,
        "scheduled_count": scheduled_count,
        "result_count": result_count,
        "unobserved_count": expected - result_count,
        "status_counts": status_counts,
        "outcome_counts": outcome_counts,
        "completed_ply_total": total_plies,
        "expanded_node_total": total_expanded_nodes,
    }
    return {
        **summary,
        "summary_root": domain_identity(_DEPTH1_STAGE_SUMMARY_DOMAIN_V1, summary),
    }


def _prerequisites_pass_v1(contract: StageContract, parent_seals: Sequence[Any]) -> bool:
    if len(parent_seals) != len(contract.required_parent_terminal_predicates):
        raise ValueError("depth-1 parent terminal count drifted")
    for (stage_id, predicate), seal in zip(
        contract.required_parent_terminal_predicates, parent_seals
    ):
        if seal["payload"]["stage_id"] != stage_id:
            raise ValueError("depth-1 parent terminal order drifted")
        if predicate == "COMPLETED_VALID":
            if seal["payload"]["lifecycle"] != "COMPLETED":
                return False
        elif predicate != "TERMINAL_SEAL_PRESENT":
            raise ValueError("depth-1 parent predicate is unknown")
    return True


def _failure_value(error: BaseException) -> Dict[str, Any]:
    return {
        "kind": "DEPTH1_STAGE_EXCEPTION",
        "exception_module": type(error).__module__,
        "exception_type": type(error).__qualname__,
        "message": str(error),
    }


def run_atlas_depth1_stage_v1(repository: str) -> Dict[str, Any]:
    if type(repository) is not str or not repository:
        raise ValueError("repository must be a nonempty exact string")
    repository_path = Path(repository).resolve()
    evidence_root = repository_path / _EVIDENCE_ROOT_RELATIVE_V1
    with ImmutableEvidenceStore(evidence_root) as store:
        with store.stage_lock(ATLAS_DEPTH1_STAGE_PROTOCOL_ID_V1):
            inputs = read_authenticated_stage_inputs(store, ATLAS_DEPTH1_STAGE_ID_V1)
            if inputs.contract.stage_protocol_id != ATLAS_DEPTH1_STAGE_PROTOCOL_ID_V1:
                raise ValueError("depth-1 stage protocol identity drifted")
            ledger_specs = (_depth1_ledger_spec_v1(inputs.protocol),)
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
                    "stage_id": ATLAS_DEPTH1_STAGE_ID_V1,
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
                summary = _execute_depth1_journal_v1(
                    store,
                    inputs.contract,
                    inputs.detached_manifest,
                    inputs.protocol,
                )
                expected = ATLAS_SAMPLED_GAME_COUNT_V1 // 2
                if (
                    summary["result_count"] != expected
                    or summary["unobserved_count"] != 0
                    or summary["status_counts"]["COMPLETE"] != expected
                ):
                    raise ValueError("depth-1 stage completion gate was not met")
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
                    "stage_id": ATLAS_DEPTH1_STAGE_ID_V1,
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
                    ATLAS_DEPTH1_STAGE_PROTOCOL_ID_V1, "completed"
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
                    "stage_id": ATLAS_DEPTH1_STAGE_ID_V1,
                    "terminal_seal": terminal["identity"],
                }
            return {
                "lifecycle": "COMPLETED",
                "stage_id": ATLAS_DEPTH1_STAGE_ID_V1,
                "summary": summary,
                "terminal_seal": terminal["identity"],
            }


def recover_atlas_depth1_stage_v1(repository: str) -> Dict[str, Any]:
    if type(repository) is not str or not repository:
        raise ValueError("repository must be a nonempty exact string")
    repository_path = Path(repository).resolve()
    evidence_root = repository_path / _EVIDENCE_ROOT_RELATIVE_V1
    with ImmutableEvidenceStore(evidence_root) as store:
        inputs = read_authenticated_stage_inputs(store, ATLAS_DEPTH1_STAGE_ID_V1)
        result = recover_stage(
            store,
            inputs.contract,
            (_depth1_ledger_spec_v1(inputs.protocol),),
            repository=repository_path,
        )
        return {
            "action": result.action,
            "lifecycle": result.lifecycle,
            "stage_id": ATLAS_DEPTH1_STAGE_ID_V1,
            "terminal_seal_or_null": result.terminal_identity,
        }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m parity_forge.atlas_depth1_stage")
    parser.add_argument("command", choices=("run", "recover"))
    parser.add_argument("--repository", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _build_parser().parse_args(argv)
    if arguments.command == "run":
        result = run_atlas_depth1_stage_v1(arguments.repository)
    else:
        result = recover_atlas_depth1_stage_v1(arguments.repository)
    print(canonical_json_bytes(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = (
    "ATLAS_DEPTH1_GAME_RECORD_VERSION_V1",
    "ATLAS_DEPTH1_STAGE_ID_V1",
    "ATLAS_DEPTH1_STAGE_PROTOCOL_ID_V1",
    "recover_atlas_depth1_stage_v1",
    "run_atlas_depth1_stage_v1",
)
