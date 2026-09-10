"""Pure pre-outcome evaluation protocol for the Plan-0013 atlas.

This module turns the already frozen development selection into identities and
work coordinates only.  It does not directly import or call the engine, solver,
agents, play, replay telemetry, experiment runners, filesystem, Git, or any
outcome layer.  Importing the ``parity_forge`` package may already have loaded
shared DSL/engine modules through package initialization; no object from those
modules is used here.  The later manifest edge is responsible for clean-commit
provenance and for attaching authoritative definition bytes to these frozen
coordinates.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from fractions import Fraction
from functools import lru_cache
from math import gcd
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Sequence, Tuple


ATLAS_PROTOCOL_VERSION_V1 = 1
ATLAS_PROTOCOL_ID_V1 = "plan0013-six-family-development-protocol-v1"

ATLAS_SELECTOR_COMMIT_V1 = (
    "5bce4c031ee674b8a95f7b786ad46d77a3a75161"
)
ATLAS_SELECTOR_TREE_V1 = (
    "3b136ef38fc2752b20596fde13bd223ecba347b6"
)
ATLAS_EVALUATOR_COMMIT_V1 = (
    "d34c383ea68d5356972c15073090f518ba842cfd"
)
ATLAS_EVALUATOR_TREE_V1 = (
    "0cc614e1992029177a504a186b050b8c1635afb0"
)

ATLAS_DEVELOPMENT_PAIR_COUNT_V1 = 144
ATLAS_DEVELOPMENT_DEFINITION_COUNT_V1 = 288
ATLAS_PAIRED_STRATUM_COUNT_V1 = 44
ATLAS_DEFINITION_ORIENTATION_COUNT_V1 = 2_304
ATLAS_SAMPLED_PROFILE_COUNT_V1 = 4_608
ATLAS_SAMPLED_ROLE_SLOT_COUNT_V1 = 9_216
ATLAS_SAMPLED_GAME_COUNT_V1 = 36_864
ATLAS_MATCHED_START_BLOCK_COUNT_V1 = 18_432
ATLAS_EXACT_STATE_CAP_TOTAL_V1 = 19_722_000
ATLAS_EXACT_ACTION_CANDIDATE_CAP_TOTAL_V1 = 592_781_760
ATLAS_TERMINAL_DEPTH1_ROLE_SLOT_CAP_V1 = 3_456
ATLAS_TERMINAL_DEPTH1_ROLE_SLOT_COUNT_V1 = 4_608
ATLAS_TERMINAL_DEPTH1_NODE_CAP_TOTAL_V1 = 15_925_248
ATLAS_GAME_PLY_CAP_V1 = 18
ATLAS_ACTION_CANDIDATE_CAP_V1 = 48

ATLAS_SAMPLED_GAMES_PER_PAIR_STRENGTH_V1 = 128
ATLAS_SAMPLED_MIN_DECISIVE_GAMES_V1 = 64
ATLAS_SAMPLED_MINORITY_SHARE_NUMERATOR_V1 = 7
ATLAS_SAMPLED_MINORITY_SHARE_DENOMINATOR_V1 = 20
ATLAS_FAMILY_FRONTIER_MIN_PAIR_COUNT_V1 = 2
ATLAS_FAMILY_FRONTIER_MIN_STRATUM_COUNT_V1 = 2

ATLAS_D4_TRANSFORMS_V1 = (
    "I",
    "R90",
    "R180",
    "R270",
    "FLR",
    "FTB",
    "FD",
    "FA",
)
ATLAS_MEMBER_ORDER_V1 = ("A_FIRST", "B_FIRST")
ATLAS_ROLE_ORDER_V1 = ("A", "B")
ATLAS_SEEDS_V1 = tuple(range(8))

ATLAS_FAMILY_ORDER_V1 = (
    "push-hop-race-v1",
    "swap-hop-network-v1",
    "convert-push-front-v1",
    "capture-hop-hunt-v1",
    "convert-capture-duel-v1",
    "push-swap-networks-v1",
)
ATLAS_FAMILY_STATE_CAPS_V1 = {
    "push-hop-race-v1": 31_920,
    "swap-hop-network-v1": 31_920,
    "convert-push-front-v1": 67_032,
    "capture-hop-hunt-v1": 67_032,
    "convert-capture-duel-v1": 181_051,
    "push-swap-networks-v1": 31_920,
}

_STRENGTHS_V1 = (
    {
        "strength_index": 0,
        "identity": "random-v1-weak",
        "agent_family": "random",
        "agent_version": 1,
        "strength": "weak",
        "selection_policy": "one-randrange-over-canonical-legal-actions",
        "depth": None,
        "max_total_nodes_per_role_slot": None,
    },
    {
        "strength_index": 1,
        "identity": "terminal_only_minimax-v1-depth1",
        "agent_family": "terminal_only_minimax",
        "agent_version": 1,
        "strength": "depth1",
        "selection_policy": "terminal-utility-full-width-zero-cutoff",
        "depth": 1,
        "max_total_nodes_per_role_slot": (
            ATLAS_TERMINAL_DEPTH1_ROLE_SLOT_CAP_V1
        ),
    },
)

# Selector roots pinned at its reviewed checkpoint.
_UPSTREAM_ROOTS_V1 = {
    "parent_domain_hash": (
        "3456b5873dadfd177639b4c0d062bad6717d328a7ebee88a71f4294f9a5b0bc5"
    ),
    "parent_census_digest": (
        "ade64ebaaf9892848e03c2312786a6ef3825f3c82f4311e16a9c810711d035d2"
    ),
    "parent_case_to_d4_root": (
        "e016d4644645595030914f496372c7d07cf2658def25b6c18394a339589100a6"
    ),
    "parent_eligible_d4_root": (
        "6b96cf4ee19d708c61c941c5759c46db0fb0420f2f820959584dd5f1e34d0108"
    ),
    "ordered_registry_root": (
        "535e9936b7f260ad5dedb7409a6f0ef7a3af6b2ea4b31c9618529dd009298dc5"
    ),
    "search_envelope_root": (
        "eb875a7d0da3319e50b6f662f48366f472348afda42c7a425bf42f5c05f6ead5"
    ),
    "paired_universe_witness_root": (
        "1167ac8d919f7d07ac8ed7680661bea22b3501349ced3be187f5c2518cecab15"
    ),
    "prior_gameplay_projection_root": (
        "b7461dbe226d436e1fd50a33cb0987efdff225626aea8105e99daa9eb4f59e9a"
    ),
    "synthetic_fixture_projection_root": (
        "67658d8b0683ad415f229d4d01a4315aa4ca33f56187c5d0eeecfc8974a70f1f"
    ),
    "history_binding_root": (
        "6e99ceca9008897f0c9f2b006e9541a23c7ed8cf2d5069e54a55bc278f8ab08d"
    ),
    "collision_root": (
        "b6b7f14e82ccc18bcb73dbbbadb2cc302c6d385fc94d8f0d3418da2b84fab354"
    ),
    "selection_partition_root": (
        "de65bf682bc5f0e02dc36eaee9fa932d5cfa77355277c3ce0fa41a6379967830"
    ),
    "selection_canonical_sha256": (
        "b681c32bb06f6a3ab03cd53735a52d8838560a5fbad3e17b0c0e9f3158cb68b5"
    ),
}

# Agent/telemetry calculation roots pinned without importing their
# outcome-capable implementation modules.
_EVALUATOR_ROOTS_V1 = {
    "fixture_root": (
        "9a45e26ff2e86a1de0f5b53afd7267b63e7877d29fbd8f0bf071f7a5fc99f565"
    ),
    "ladder_root": (
        "62255ad512d6258250ea7af0b757530dea4e7c991fae8305b88af656ccb65e62"
    ),
    "random_conformance_root": (
        "50a0ef2db98b7ade17325b34692a432cae610b9e71850a72385a29494d477576"
    ),
    "terminal_conformance_root": (
        "38dce33df7283429705ef4b33b2260be4798cf355b0bc8f6493fc15e19480026"
    ),
    "evidence_root": (
        "5cd0dd2a114e2b503d68131bf3892cd0d513b2d7fed12522c82425d440f8d075"
    ),
    "atlas_separation_root": (
        "a82e7640346954412710ec3c2e476243917845cf145ca42353dba0ed16751eba"
    ),
    "benchmark_root": (
        "340e928d5b6ba64743dbcfd252eff951af185bc7c30138ccee333710ded15da0"
    ),
    "benchmark_canonical_sha256": (
        "5097d4d516963938a74f0fd020e96d0934943ccc4b0c5a9e0c2056156a2a3ffc"
    ),
    "replay_telemetry_benchmark_root": (
        "6789f97e7f0948df9fa66f75933c061a08e029ce49e9d9da33ae57a7b4a59a33"
    ),
}

_SELECTOR_CLOSURE_PATHS_V1 = (
    "src/parity_forge/__init__.py",
    "src/parity_forge/atlas.py",
    "src/parity_forge/atlas_history.py",
    "src/parity_forge/atlas_projection.py",
    "src/parity_forge/dsl.py",
    "src/parity_forge/engine.py",
    "src/parity_forge/family.py",
    "src/parity_forge/feasibility.py",
    "src/parity_forge/feasibility_census.py",
    "src/parity_forge/symmetry.py",
)
_EVALUATOR_CLOSURE_PATHS_V1 = (
    "src/parity_forge/__init__.py",
    "src/parity_forge/agents.py",
    "src/parity_forge/atlas.py",
    "src/parity_forge/atlas_agent_benchmark.py",
    "src/parity_forge/atlas_history.py",
    "src/parity_forge/atlas_projection.py",
    "src/parity_forge/dsl.py",
    "src/parity_forge/engine.py",
    "src/parity_forge/family.py",
    "src/parity_forge/feasibility.py",
    "src/parity_forge/feasibility_census.py",
    "src/parity_forge/solver.py",
    "src/parity_forge/symmetry.py",
    "src/parity_forge/terminal_search.py",
)

_EXACT_SLOT_ID_DOMAIN_V1 = b"parity-forge:plan0013:protocol:exact-slot:v1\0"
_ORIENTATION_SLOT_ID_DOMAIN_V1 = (
    b"parity-forge:plan0013:protocol:orientation-slot:v1\0"
)
_PROFILE_SLOT_ID_DOMAIN_V1 = b"parity-forge:plan0013:protocol:profile-slot:v1\0"
_ROLE_SLOT_ID_DOMAIN_V1 = b"parity-forge:plan0013:protocol:role-slot:v1\0"
_MATCH_BLOCK_ID_DOMAIN_V1 = b"parity-forge:plan0013:protocol:match-block:v1\0"
_GAME_SLOT_ID_DOMAIN_V1 = b"parity-forge:plan0013:protocol:game-slot:v1\0"
_ORDERED_ROOT_DOMAIN_V1 = b"parity-forge:plan0013:protocol:ordered-root:v1\0"
_UPSTREAM_ROOT_DOMAIN_V1 = b"parity-forge:plan0013:protocol:upstream:v1\0"
_SCHEDULE_ROOT_DOMAIN_V1 = b"parity-forge:plan0013:protocol:schedule:v1\0"
_TELEMETRY_ROOT_DOMAIN_V1 = b"parity-forge:plan0013:protocol:telemetry:v1\0"
_CENSOR_ROOT_DOMAIN_V1 = b"parity-forge:plan0013:protocol:censor:v1\0"
_ASSESSMENT_ROOT_DOMAIN_V1 = b"parity-forge:plan0013:protocol:assessment:v1\0"
_INSPECTION_ROOT_DOMAIN_V1 = b"parity-forge:plan0013:protocol:inspection:v1\0"
_INSPECTION_SCORE_DOMAIN_V1 = (
    b"parity-forge:plan0013:protocol:inspection-score:v1\0"
)
_EXECUTION_EVIDENCE_ROOT_DOMAIN_V1 = (
    b"parity-forge:plan0013:protocol:execution-evidence:v1\0"
)
_PRODUCTION_CLOSURE_ROOT_DOMAIN_V1 = (
    b"parity-forge:plan0013:evidence:production-closure:v1\0"
)
_MANIFEST_BOOTSTRAP_ROOT_DOMAIN_V1 = (
    b"parity-forge:plan0013:evidence:manifest-bootstrap:v1\0"
)
_STAGE_RESERVATION_ID_DOMAIN_V1 = (
    b"parity-forge:plan0013:evidence:stage-reservation:v1\0"
)
_STAGE_ATTEMPT_ID_DOMAIN_V1 = (
    b"parity-forge:plan0013:evidence:stage-attempt:v1\0"
)
_STAGE_BLOCKED_ID_DOMAIN_V1 = (
    b"parity-forge:plan0013:evidence:stage-blocked:v1\0"
)
_STAGE_ORPHANED_ID_DOMAIN_V1 = (
    b"parity-forge:plan0013:evidence:stage-orphaned:v1\0"
)
_STAGE_TERMINAL_SEAL_DOMAIN_V1 = (
    b"parity-forge:plan0013:evidence:stage-terminal-seal:v1\0"
)
_PROTOCOL_ROOT_DOMAIN_V1 = b"parity-forge:plan0013:protocol:root:v1\0"

_MAX_SELECTION_JSON_NODES_V1 = 8_000_000
_MAX_SELECTION_JSON_DEPTH_V1 = 64
_MAX_SELECTION_TEXT_CHARACTERS_V1 = 96_000_000
_MAX_SELECTION_SINGLE_STRING_CHARACTERS_V1 = 1_000_000
_MAX_SELECTION_CANONICAL_BYTES_V1 = 128_000_000
_MAX_PROTOCOL_JSON_NODES_V1 = 500_000
_MAX_PROTOCOL_JSON_DEPTH_V1 = 48
_MAX_PROTOCOL_TEXT_CHARACTERS_V1 = 16_000_000
_MAX_PROTOCOL_SINGLE_STRING_CHARACTERS_V1 = 1_000_000
_MAX_PROTOCOL_CANONICAL_BYTES_V1 = 24_000_000
_MAX_JSON_INTEGER_BITS_V1 = 128

# Filled after the independently reviewable builder is computed.  Public build
# and validation fail until all fixed values match.
ATLAS_EXACT_SCHEDULE_ROOT_V1 = (
    "de198bc115453b48f52023ee5fab9cac269005af762fd8bc27302eb68002a1a7"
)
ATLAS_ORIENTATION_SCHEDULE_ROOT_V1 = (
    "931e48a2133dbf3840122ab9aac39aaaa24bb37c65471bf8adc6d758b1afd84e"
)
ATLAS_PROFILE_SCHEDULE_ROOT_V1 = (
    "c2624a0d4ff4902bc6564ad24b95b62cae46c713af3cc4c7e053a32098e726a6"
)
ATLAS_ROLE_SLOT_SCHEDULE_ROOT_V1 = (
    "4d3e945b080cb3dfc463c2b0acbcb4cbc1b0ab64de71f242ef7af24465842b48"
)
ATLAS_GAME_SCHEDULE_ROOT_V1 = (
    "da59e67ae9bb797040da825376ea720f1e78db61ca3c11fe7693155b16c90f18"
)
ATLAS_MATCHED_START_BLOCK_ROOT_V1 = (
    "112babd777bbba042e9ac3a63fe9aeff4e1d41d352c8ab7d145236fb4fefc3ea"
)
ATLAS_TELEMETRY_SCHEDULE_ROOT_V1 = (
    "be0a229ac00ef4e40bc85e43473e2bd71bf7b082ede8eaafe51dd7e1162a2867"
)
ATLAS_PROTOCOL_ROOT_V1 = (
    "8126c33f787e63aef07e48fc25a3ed950f4650495e2e512c96d9e33583b8f04c"
)
ATLAS_PROTOCOL_CANONICAL_SHA256_V1 = (
    "b732f174399acb8d52b2f5dddefc36a9f45e0560e94428b85f55998089bc9229"
)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _digest(domain: bytes, value: Any) -> str:
    return hashlib.sha256(domain + _canonical_bytes(value)).hexdigest()


def _json_copy(value: Any, label: str) -> Any:
    try:
        return json.loads(_canonical_bytes(value).decode("utf-8"))
    except (TypeError, ValueError, json.JSONDecodeError, RecursionError) as error:
        raise TypeError("{} must be finite JSON".format(label)) from error


def _validate_json_tree(
    value: Any,
    label: str,
    *,
    max_nodes: int,
    max_depth: int,
    max_text: int,
    max_string: int,
) -> None:
    active_container_ids = set()
    visited_nodes = 0
    text_characters = 0
    stack = [("visit", value, 0)]
    try:
        while stack:
            operation, current, depth = stack.pop()
            if operation == "leave":
                active_container_ids.remove(id(current))
                continue
            visited_nodes += 1
            if visited_nodes > max_nodes:
                raise ValueError("{} exceeds the fixed JSON node limit".format(label))
            if depth > max_depth:
                raise ValueError("{} exceeds the fixed JSON depth limit".format(label))
            if current is None or type(current) is bool:
                continue
            if type(current) is int:
                if current.bit_length() > _MAX_JSON_INTEGER_BITS_V1:
                    raise ValueError(
                        "{} exceeds the fixed integer bit limit".format(label)
                    )
                continue
            if type(current) is str:
                if len(current) > max_string:
                    raise ValueError("{} exceeds the fixed string limit".format(label))
                text_characters += len(current)
                if text_characters > max_text:
                    raise ValueError("{} exceeds the fixed text limit".format(label))
                continue
            if type(current) not in (list, dict):
                raise TypeError("{} must contain exact finite JSON values".format(label))
            if len(current) > max_nodes - visited_nodes:
                raise ValueError("{} exceeds the fixed JSON node limit".format(label))
            container_id = id(current)
            if container_id in active_container_ids:
                raise ValueError("{} contains a JSON cycle".format(label))
            active_container_ids.add(container_id)
            stack.append(("leave", current, depth))
            if type(current) is list:
                for child in current:
                    stack.append(("visit", child, depth + 1))
            else:
                for key, child in current.items():
                    if type(key) is not str:
                        raise TypeError("{} keys must be exact strings".format(label))
                    if len(key) > max_string:
                        raise ValueError("{} exceeds the fixed key limit".format(label))
                    text_characters += len(key)
                    if text_characters > max_text:
                        raise ValueError("{} exceeds the fixed text limit".format(label))
                    stack.append(("visit", child, depth + 1))
    except RuntimeError as error:
        raise ValueError("{} changed during validation".format(label)) from error


def _seal_selection(value: Any) -> Tuple[Dict[str, Any], bytes]:
    _validate_json_tree(
        value,
        "atlas selection",
        max_nodes=_MAX_SELECTION_JSON_NODES_V1,
        max_depth=_MAX_SELECTION_JSON_DEPTH_V1,
        max_text=_MAX_SELECTION_TEXT_CHARACTERS_V1,
        max_string=_MAX_SELECTION_SINGLE_STRING_CHARACTERS_V1,
    )
    try:
        sealed = _canonical_bytes(value)
    except (TypeError, ValueError, RecursionError) as error:
        raise TypeError("atlas selection must be finite JSON") from error
    if len(sealed) > _MAX_SELECTION_CANONICAL_BYTES_V1:
        raise ValueError("atlas selection exceeds the fixed canonical byte limit")
    if hashlib.sha256(sealed).hexdigest() != _UPSTREAM_ROOTS_V1[
        "selection_canonical_sha256"
    ]:
        raise ValueError("atlas selection differs from the frozen canonical SHA-256")
    detached = json.loads(sealed.decode("utf-8"))
    _validate_selection_semantics(detached)
    return detached, sealed


def _seal_protocol(value: Any) -> bytes:
    _validate_json_tree(
        value,
        "atlas protocol",
        max_nodes=_MAX_PROTOCOL_JSON_NODES_V1,
        max_depth=_MAX_PROTOCOL_JSON_DEPTH_V1,
        max_text=_MAX_PROTOCOL_TEXT_CHARACTERS_V1,
        max_string=_MAX_PROTOCOL_SINGLE_STRING_CHARACTERS_V1,
    )
    try:
        sealed = _canonical_bytes(value)
    except (TypeError, ValueError, RecursionError) as error:
        raise TypeError("atlas protocol must be finite JSON") from error
    if len(sealed) > _MAX_PROTOCOL_CANONICAL_BYTES_V1:
        raise ValueError("atlas protocol exceeds the fixed canonical byte limit")
    return sealed


def _exact_keys(value: Any, expected: Iterable[str], label: str) -> Mapping[str, Any]:
    if type(value) is not dict:
        raise TypeError("{} must be an exact object".format(label))
    expected_set = set(expected)
    if set(value) != expected_set:
        raise ValueError("{} keys differ from the frozen contract".format(label))
    return value


def _exact_int(value: Any, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError("{} must be an exact integer >= {}".format(label, minimum))
    return value


def _sha256(value: Any, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError("{} must be a lowercase SHA-256".format(label))
    return value


def _validate_selection_semantics(selection: Mapping[str, Any]) -> None:
    for key in (
        "ordered_registry_root",
        "search_envelope_root",
        "paired_universe_witness_root",
        "selection_partition_root",
    ):
        expected_key = (
            "selection_partition_root" if key == "selection_partition_root" else key
        )
        if selection.get(key) != _UPSTREAM_ROOTS_V1[expected_key]:
            raise ValueError("atlas selection {} drifted".format(key))
    history = selection.get("history")
    if type(history) is not dict:
        raise TypeError("atlas selection history must be an exact object")
    history_roots = {
        "prior_gameplay_projection_root": "prior_gameplay_projection_root",
        "synthetic_fixture_projection_root": "synthetic_fixture_projection_root",
        "history_binding_root": "history_binding_root",
        "collision_root": "collision_root",
    }
    for field, expected_key in history_roots.items():
        if history.get(field) != _UPSTREAM_ROOTS_V1[expected_key]:
            raise ValueError("atlas selection history {} drifted".format(field))
    census = selection.get("census")
    if type(census) is not dict:
        raise TypeError("atlas selection census must be an exact object")
    if (
        census.get("development_pair_count") != ATLAS_DEVELOPMENT_PAIR_COUNT_V1
        or census.get("development_definition_count")
        != ATLAS_DEVELOPMENT_DEFINITION_COUNT_V1
        or census.get("candidate_pair_count") != ATLAS_DEVELOPMENT_PAIR_COUNT_V1
        or census.get("candidate_definition_count")
        != ATLAS_DEVELOPMENT_DEFINITION_COUNT_V1
    ):
        raise ValueError("atlas selection block census drifted")
    development = selection.get("development_pairs")
    candidate = selection.get("confirmation_candidate_pairs")
    if type(development) is not list or len(development) != ATLAS_DEVELOPMENT_PAIR_COUNT_V1:
        raise ValueError("atlas development pair block drifted")
    if type(candidate) is not list or len(candidate) != ATLAS_DEVELOPMENT_PAIR_COUNT_V1:
        raise ValueError("atlas candidate pair block drifted")
    development_ids = [pair.get("paired_mechanical_d4_identity") for pair in development]
    candidate_ids = [pair.get("paired_mechanical_d4_identity") for pair in candidate]
    if (
        any(type(value) is not str for value in development_ids + candidate_ids)
        or len(set(development_ids)) != len(development_ids)
        or len(set(candidate_ids)) != len(candidate_ids)
        or set(development_ids).intersection(candidate_ids)
    ):
        raise ValueError("atlas selection block identities drifted")


def _ordered_record_root(label: str, records: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    leaf_domain = _ORDERED_ROOT_DOMAIN_V1 + label.encode("ascii") + b":leaf\0"
    root_domain = _ORDERED_ROOT_DOMAIN_V1 + label.encode("ascii") + b":root\0"
    count = 0
    first_id = None
    last_id = None
    leaf_digests = []
    for record in records:
        leaf = _digest(leaf_domain, record)
        leaf_digests.append(leaf)
        record_id = record.get("slot_id") or record.get("block_id")
        if type(record_id) is not str:
            raise AssertionError("ordered schedule record lacks an identity")
        if count == 0:
            first_id = record_id
        last_id = record_id
        count += 1
    return {
        "count": count,
        "first_id": first_id,
        "last_id": last_id,
        "root": _digest(
            root_domain,
            {"count": count, "ordered_leaf_digests": leaf_digests},
        ),
    }


def _build_exact_slots(selection: Mapping[str, Any]) -> List[Dict[str, Any]]:
    slots = []
    family_counts = Counter()
    for pair_index, pair in enumerate(selection["development_pairs"]):
        if pair.get("selection", {}).get("block") != "DEVELOPMENT":
            raise ValueError("protocol input contains a non-development pair")
        identity = _sha256(
            pair.get("paired_mechanical_d4_identity"),
            "paired mechanical identity",
        )
        family_id = pair.get("family_id")
        if family_id not in ATLAS_FAMILY_STATE_CAPS_V1:
            raise ValueError("protocol input contains an unknown family")
        family_counts[family_id] += 1
        proof = pair.get("state_work_proof")
        if type(proof) is not dict:
            raise TypeError("pair state/work proof must be an exact object")
        max_states = _exact_int(
            proof.get("structural_state_upper_bound"),
            "structural state upper bound",
            1,
        )
        if max_states != ATLAS_FAMILY_STATE_CAPS_V1[family_id]:
            raise ValueError("family structural state cap drifted")
        max_action_candidates = _exact_int(
            proof.get("max_action_candidates_per_state"),
            "maximum action candidates per state",
            1,
        )
        state_action_cap = _exact_int(
            proof.get("state_action_candidate_evaluation_upper_bound"),
            "state/action-candidate evaluation upper bound",
            1,
        )
        if state_action_cap != max_states * max_action_candidates:
            raise ValueError("state/action-candidate proof does not reconstruct")
        stratum = _exact_keys(
            pair.get("stratum"),
            ("goal_frame", "setup", "vector_profiles"),
            "pair neutral stratum",
        )
        if stratum["setup"] != {"A_count": 3, "B_count": 3}:
            raise ValueError("protocol input is outside the frozen 3+3 setup")
        if type(stratum["goal_frame"]) is not str or not stratum["goal_frame"]:
            raise ValueError("pair goal frame must be a nonempty string")
        vector_profiles = _exact_keys(
            stratum["vector_profiles"],
            ("A", "B"),
            "pair vector profiles",
        )
        if any(
            type(vector_profiles[role]) is not str or not vector_profiles[role]
            for role in ATLAS_ROLE_ORDER_V1
        ):
            raise ValueError("pair vector profiles must be nonempty strings")
        members = pair.get("members")
        if type(members) is not dict or set(members) != set(ATLAS_MEMBER_ORDER_V1):
            raise ValueError("pair member map drifted")
        for member_index, member_label in enumerate(ATLAS_MEMBER_ORDER_V1):
            member = members[member_label]
            hashes = member.get("representative_d4_slot_definition_hashes")
            if type(hashes) is not list or len(hashes) != len(ATLAS_D4_TRANSFORMS_V1):
                raise ValueError("member D4 orientation hashes drifted")
            for index, digest in enumerate(hashes):
                _sha256(digest, "orientation definition hash")
                if index == 0 and digest != member.get("representative_definition_hash"):
                    raise ValueError("identity orientation differs from representative")
            unsigned = {
                "definition_index": 2 * pair_index + member_index,
                "pair_index": pair_index,
                "member_index": member_index,
                "member": member_label,
                "first_player": member.get("first_player"),
                "paired_mechanical_d4_identity": identity,
                "family_id": family_id,
                "family_signature_hash": _sha256(
                    pair.get("family_signature_hash"), "family signature hash"
                ),
                "paired_stratum_id": pair.get("paired_stratum_id"),
                "goal_frame": stratum["goal_frame"],
                "vector_profiles": dict(vector_profiles),
                "representative_definition_hash": _sha256(
                    member.get("representative_definition_hash"),
                    "representative definition hash",
                ),
                "d4_canonical_hash": _sha256(
                    member.get("d4_canonical_hash"), "member D4 hash"
                ),
                "representative_d4_slot_definition_hashes": list(hashes),
                "representative_d4_slot_definition_root": _sha256(
                    member.get("representative_d4_slot_definition_root"),
                    "member D4 slot root",
                ),
                "state_work_proof_digest": _sha256(
                    pair.get("state_work_proof_digest"), "state proof digest"
                ),
                "max_states": max_states,
                "max_action_candidates_per_state": max_action_candidates,
                "max_state_action_candidate_evaluations": state_action_cap,
            }
            if unsigned["first_player"] != member_label[0]:
                raise ValueError("member first-player label drifted")
            if type(unsigned["paired_stratum_id"]) is not str:
                raise TypeError("paired stratum identity must be a string")
            slots.append(
                {**unsigned, "slot_id": _digest(_EXACT_SLOT_ID_DOMAIN_V1, unsigned)}
            )
    if family_counts != Counter({family_id: 24 for family_id in ATLAS_FAMILY_ORDER_V1}):
        raise ValueError("development family pair exposure drifted")
    if len(slots) != ATLAS_DEVELOPMENT_DEFINITION_COUNT_V1:
        raise AssertionError("exact schedule count drifted")
    if sum(slot["max_states"] for slot in slots) != ATLAS_EXACT_STATE_CAP_TOTAL_V1:
        raise AssertionError("exact schedule state-cap total drifted")
    if sum(
        slot["max_state_action_candidate_evaluations"] for slot in slots
    ) != ATLAS_EXACT_ACTION_CANDIDATE_CAP_TOTAL_V1:
        raise AssertionError("exact schedule state/action-candidate cap total drifted")
    return slots


def _build_orientation_slots(exact_slots: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    slots = []
    for exact in exact_slots:
        hashes = exact["representative_d4_slot_definition_hashes"]
        for transform_index, transform in enumerate(ATLAS_D4_TRANSFORMS_V1):
            transformed_hash = hashes[transform_index]
            unsigned = {
                "orientation_slot_index": (
                    exact["definition_index"] * len(ATLAS_D4_TRANSFORMS_V1)
                    + transform_index
                ),
                "exact_slot_id": exact["slot_id"],
                "definition_index": exact["definition_index"],
                "pair_index": exact["pair_index"],
                "member": exact["member"],
                "paired_mechanical_d4_identity": exact[
                    "paired_mechanical_d4_identity"
                ],
                "family_id": exact["family_id"],
                "paired_stratum_id": exact["paired_stratum_id"],
                "transform_index": transform_index,
                "transform": transform,
                "transformed_definition_hash": transformed_hash,
                "d4_canonical_hash": exact["d4_canonical_hash"],
                "first_duplicate_transform_index": hashes.index(transformed_hash),
            }
            slots.append(
                {
                    **unsigned,
                    "slot_id": _digest(_ORIENTATION_SLOT_ID_DOMAIN_V1, unsigned),
                }
            )
    if len(slots) != ATLAS_DEFINITION_ORIENTATION_COUNT_V1:
        raise AssertionError("orientation schedule count drifted")
    if len({slot["slot_id"] for slot in slots}) != len(slots):
        raise AssertionError("orientation slot identities are not unique")
    return slots


def _build_profile_slots(
    orientation_slots: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    slots = []
    for strength in _STRENGTHS_V1:
        for orientation in orientation_slots:
            unsigned = {
                "profile_slot_index": len(slots),
                "orientation_slot_id": orientation["slot_id"],
                "definition_index": orientation["definition_index"],
                "pair_index": orientation["pair_index"],
                "member": orientation["member"],
                "paired_mechanical_d4_identity": orientation[
                    "paired_mechanical_d4_identity"
                ],
                "family_id": orientation["family_id"],
                "paired_stratum_id": orientation["paired_stratum_id"],
                "transform_index": orientation["transform_index"],
                "transform": orientation["transform"],
                "transformed_definition_hash": orientation[
                    "transformed_definition_hash"
                ],
                "d4_canonical_hash": orientation["d4_canonical_hash"],
                "strength": dict(strength),
                "ordered_roles": list(ATLAS_ROLE_ORDER_V1),
                "ordered_seeds": list(ATLAS_SEEDS_V1),
                "role_slot_count": 2,
                "game_count": 8,
            }
            slots.append(
                {**unsigned, "slot_id": _digest(_PROFILE_SLOT_ID_DOMAIN_V1, unsigned)}
            )
    if len(slots) != ATLAS_SAMPLED_PROFILE_COUNT_V1:
        raise AssertionError("sampled profile schedule count drifted")
    return slots


def _build_role_slots(profile_slots: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    slots = []
    for profile in profile_slots:
        for role_index, role in enumerate(ATLAS_ROLE_ORDER_V1):
            unsigned = {
                "role_slot_index": len(slots),
                "profile_slot_id": profile["slot_id"],
                "orientation_slot_id": profile["orientation_slot_id"],
                "paired_mechanical_d4_identity": profile[
                    "paired_mechanical_d4_identity"
                ],
                "member": profile["member"],
                "transform_index": profile["transform_index"],
                "transform": profile["transform"],
                "strength": dict(profile["strength"]),
                "role_index": role_index,
                "controlled_role": role,
                "ordered_seeds": list(ATLAS_SEEDS_V1),
                "reset_count": (
                    1
                    if profile["strength"]["identity"]
                    == "terminal_only_minimax-v1-depth1"
                    else 0
                ),
                "max_total_nodes": profile["strength"][
                    "max_total_nodes_per_role_slot"
                ],
            }
            slots.append(
                {**unsigned, "slot_id": _digest(_ROLE_SLOT_ID_DOMAIN_V1, unsigned)}
            )
    if len(slots) != ATLAS_SAMPLED_ROLE_SLOT_COUNT_V1:
        raise AssertionError("sampled role schedule count drifted")
    return slots


def _match_block_unsigned(
    orientation_by_coordinate: Mapping[Tuple[int, str, int], Mapping[str, Any]],
    pair_index: int,
    transform_index: int,
    strength: Mapping[str, Any],
    seed_index: int,
) -> Dict[str, Any]:
    members = [
        orientation_by_coordinate[(pair_index, member, transform_index)]
        for member in ATLAS_MEMBER_ORDER_V1
    ]
    if members[0]["paired_mechanical_d4_identity"] != members[1][
        "paired_mechanical_d4_identity"
    ]:
        raise AssertionError("matched-start members do not share a pair identity")
    return {
        "pair_index": pair_index,
        "paired_mechanical_d4_identity": members[0][
            "paired_mechanical_d4_identity"
        ],
        "family_id": members[0]["family_id"],
        "paired_stratum_id": members[0]["paired_stratum_id"],
        "transform_index": transform_index,
        "transform": ATLAS_D4_TRANSFORMS_V1[transform_index],
        "ordered_member_orientation_slot_ids": [
            member["slot_id"] for member in members
        ],
        "ordered_member_definition_hashes": [
            member["transformed_definition_hash"] for member in members
        ],
        "strength": dict(strength),
        "seed_index": seed_index,
        "seed": ATLAS_SEEDS_V1[seed_index],
        "format": "same-roles-two-games-alternating-first-player",
    }


def _build_match_blocks(
    orientation_slots: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    orientation_by_coordinate = {
        (slot["pair_index"], slot["member"], slot["transform_index"]): slot
        for slot in orientation_slots
    }
    blocks = []
    for strength in _STRENGTHS_V1:
        for pair_index in range(ATLAS_DEVELOPMENT_PAIR_COUNT_V1):
            for transform_index in range(len(ATLAS_D4_TRANSFORMS_V1)):
                for seed_index in range(len(ATLAS_SEEDS_V1)):
                    unsigned = _match_block_unsigned(
                        orientation_by_coordinate,
                        pair_index,
                        transform_index,
                        strength,
                        seed_index,
                    )
                    blocks.append(
                        {
                            **unsigned,
                            "block_id": _digest(_MATCH_BLOCK_ID_DOMAIN_V1, unsigned),
                        }
                    )
    if len(blocks) != ATLAS_MATCHED_START_BLOCK_COUNT_V1:
        raise AssertionError("matched-start block count drifted")
    return blocks


def _build_game_slots(
    profile_slots: Sequence[Mapping[str, Any]],
    role_slots: Sequence[Mapping[str, Any]],
    match_blocks: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    roles_by_profile: Dict[str, List[Mapping[str, Any]]] = {}
    for role in role_slots:
        roles_by_profile.setdefault(role["profile_slot_id"], []).append(role)
    block_by_coordinate = {
        (
            block["pair_index"],
            block["transform_index"],
            block["strength"]["strength_index"],
            block["seed_index"],
        ): block
        for block in match_blocks
    }
    games = []
    for profile in profile_slots:
        profile_roles = roles_by_profile[profile["slot_id"]]
        if [role["controlled_role"] for role in profile_roles] != list(
            ATLAS_ROLE_ORDER_V1
        ):
            raise AssertionError("profile role-slot order drifted")
        for seed_index, seed in enumerate(ATLAS_SEEDS_V1):
            block = block_by_coordinate[
                (
                    profile["pair_index"],
                    profile["transform_index"],
                    profile["strength"]["strength_index"],
                    seed_index,
                )
            ]
            unsigned = {
                "game_slot_index": len(games),
                "profile_slot_id": profile["slot_id"],
                "ordered_role_slot_ids": [role["slot_id"] for role in profile_roles],
                "matched_start_block_id": block["block_id"],
                "paired_mechanical_d4_identity": profile[
                    "paired_mechanical_d4_identity"
                ],
                "member": profile["member"],
                "transform_index": profile["transform_index"],
                "transform": profile["transform"],
                "transformed_definition_hash": profile[
                    "transformed_definition_hash"
                ],
                "strength": dict(profile["strength"]),
                "seed_index": seed_index,
                "seed": seed,
                "rng_scope": "fresh-random.Random(seed)-per-game",
                "rng_stream": "one-stream-shared-by-both-roles-in-ply-order",
            }
            games.append(
                {**unsigned, "slot_id": _digest(_GAME_SLOT_ID_DOMAIN_V1, unsigned)}
            )
    if len(games) != ATLAS_SAMPLED_GAME_COUNT_V1:
        raise AssertionError("sampled game schedule count drifted")
    block_member_counts = Counter(
        (game["matched_start_block_id"], game["member"]) for game in games
    )
    if (
        len(block_member_counts) != 2 * ATLAS_MATCHED_START_BLOCK_COUNT_V1
        or any(count != 1 for count in block_member_counts.values())
    ):
        raise AssertionError("matched-start blocks do not contain exactly two games")
    return games


def _schedule_context(selection: Mapping[str, Any]) -> Dict[str, Any]:
    exact = _build_exact_slots(selection)
    orientations = _build_orientation_slots(exact)
    profiles = _build_profile_slots(orientations)
    roles = _build_role_slots(profiles)
    blocks = _build_match_blocks(orientations)
    games = _build_game_slots(profiles, roles, blocks)
    roots = {
        "exact": _ordered_record_root("exact", exact),
        "orientation": _ordered_record_root("orientation", orientations),
        "profile": _ordered_record_root("profile", profiles),
        "role": _ordered_record_root("role", roles),
        "game": _ordered_record_root("game", games),
        "matched_start_block": _ordered_record_root("matched-start", blocks),
    }
    expected_counts = {
        "exact": ATLAS_DEVELOPMENT_DEFINITION_COUNT_V1,
        "orientation": ATLAS_DEFINITION_ORIENTATION_COUNT_V1,
        "profile": ATLAS_SAMPLED_PROFILE_COUNT_V1,
        "role": ATLAS_SAMPLED_ROLE_SLOT_COUNT_V1,
        "game": ATLAS_SAMPLED_GAME_COUNT_V1,
        "matched_start_block": ATLAS_MATCHED_START_BLOCK_COUNT_V1,
    }
    if any(roots[key]["count"] != count for key, count in expected_counts.items()):
        raise AssertionError("one or more schedule coordinate counts drifted")
    return {
        "exact": exact,
        "orientations": orientations,
        "profiles": profiles,
        "roles": roles,
        "blocks": blocks,
        "games": games,
        "roots": roots,
    }


@lru_cache(maxsize=1)
def _cached_schedule_context(selection_json: str) -> Dict[str, Any]:
    return _schedule_context(json.loads(selection_json))


def _upstream_binding() -> Dict[str, Any]:
    value = {
        "selector_commit": ATLAS_SELECTOR_COMMIT_V1,
        "selector_tree": ATLAS_SELECTOR_TREE_V1,
        "selector_closure_paths": list(_SELECTOR_CLOSURE_PATHS_V1),
        "selector_closure_scope": "reviewed-outcome-free-selector-checkpoint",
        "evaluator_commit": ATLAS_EVALUATOR_COMMIT_V1,
        "evaluator_tree": ATLAS_EVALUATOR_TREE_V1,
        "evaluator_closure_paths": list(_EVALUATOR_CLOSURE_PATHS_V1),
        "evaluator_closure_scope": "reviewed-synthetic-benchmark-checkpoint-only",
        "production_execution_closure_replacement": "FORBIDDEN",
        "required_commit_relation": "selector-is-strict-ancestor-of-evaluator",
        "selector_roots": _json_copy(_UPSTREAM_ROOTS_V1, "selector roots"),
        "evaluator_roots": _json_copy(_EVALUATOR_ROOTS_V1, "evaluator roots"),
        "git_verification_owner": "later-outcome-free-manifest-edge",
    }
    value["upstream_binding_root"] = _digest(_UPSTREAM_ROOT_DOMAIN_V1, value)
    return value


def _schedule_section(context: Mapping[str, Any]) -> Dict[str, Any]:
    roots = context["roots"]
    section = {
        "index_origin": 0,
        "development_order": "frozen-selection-development_pairs-order",
        "member_order": list(ATLAS_MEMBER_ORDER_V1),
        "orientation_order": list(ATLAS_D4_TRANSFORMS_V1),
        "strength_order": [strength["identity"] for strength in _STRENGTHS_V1],
        "role_order": list(ATLAS_ROLE_ORDER_V1),
        "seed_order": list(ATLAS_SEEDS_V1),
        "sampled_execution_order": (
            "strength-then-pair-then-member-then-orientation-then-seed"
        ),
        "strength_phase_seal_order": [
            "random-v1-weak",
            "terminal_only_minimax-v1-depth1",
        ],
        "cardinality": {
            "development_pair_count": ATLAS_DEVELOPMENT_PAIR_COUNT_V1,
            "exact_definition_slot_count": ATLAS_DEVELOPMENT_DEFINITION_COUNT_V1,
            "definition_orientation_slot_count": (
                ATLAS_DEFINITION_ORIENTATION_COUNT_V1
            ),
            "sampled_profile_slot_count": ATLAS_SAMPLED_PROFILE_COUNT_V1,
            "sampled_role_slot_count": ATLAS_SAMPLED_ROLE_SLOT_COUNT_V1,
            "sampled_game_slot_count": ATLAS_SAMPLED_GAME_COUNT_V1,
            "matched_start_block_count": ATLAS_MATCHED_START_BLOCK_COUNT_V1,
            "telemetry_trace_slot_count_if_all_games_complete": (
                ATLAS_SAMPLED_GAME_COUNT_V1
            ),
            "candidate_pair_emitted_count": 0,
            "candidate_definition_emitted_count": 0,
            "candidate_profile_slot_count": 0,
            "candidate_game_slot_count": 0,
        },
        "per_family_cardinality": {
            "pair_count": 24,
            "exact_definition_slot_count": 48,
            "definition_orientation_slot_count": 384,
            "sampled_profile_slot_count": 768,
            "sampled_role_slot_count": 1_536,
            "sampled_game_slot_count": 6_144,
            "matched_start_block_count": 3_072,
        },
        "exact_state_cap_total": ATLAS_EXACT_STATE_CAP_TOTAL_V1,
        "exact_state_action_candidate_cap_total": (
            ATLAS_EXACT_ACTION_CANDIDATE_CAP_TOTAL_V1
        ),
        "terminal_depth1_role_slot_count": (
            ATLAS_TERMINAL_DEPTH1_ROLE_SLOT_COUNT_V1
        ),
        "terminal_depth1_node_cap_per_role_slot": (
            ATLAS_TERMINAL_DEPTH1_ROLE_SLOT_CAP_V1
        ),
        "terminal_depth1_node_cap_total": (
            ATLAS_TERMINAL_DEPTH1_NODE_CAP_TOTAL_V1
        ),
        "sampled_ply_cap_total": (
            ATLAS_SAMPLED_GAME_COUNT_V1 * ATLAS_GAME_PLY_CAP_V1
        ),
        "exact_slots": _json_copy(context["exact"], "exact schedule"),
        "orientation_slots": _json_copy(
            context["orientations"], "orientation schedule"
        ),
        "derived_coordinate_roots": _json_copy(roots, "schedule roots"),
        "derived_coordinate_storage": (
            "profiles-roles-games-and-matched-blocks-reconstruct-from-public-fixed-cross-product"
        ),
        "reconstruction_interfaces": {
            "selection_input_iterators": "manifest-preflight-only",
            "outcome_stage_iterators": (
                "validated-frozen-protocol-exact-and-orientation-slots-plus-fixed-"
                "cross-product-no-selection-input"
            ),
            "outcome_stage_input_contains_candidate_definition_bytes": False,
        },
    }
    section["schedule_root"] = _digest(_SCHEDULE_ROOT_DOMAIN_V1, section)
    return section


def _exact_protocol() -> Dict[str, Any]:
    return {
        "solver_identity": "exact-solver-v1",
        "solve_scope": "representative-I-orientation-once-per-member",
        "slot_order": "manifest-pair-order-A_FIRST-then-B_FIRST",
        "slot_count": ATLAS_DEVELOPMENT_DEFINITION_COUNT_V1,
        "max_states_source": "pair.state_work_proof.structural_state_upper_bound",
        "max_action_candidates_source": (
            "pair.state_work_proof.max_action_candidates_per_state"
        ),
        "max_state_action_candidate_evaluations_source": (
            "pair.state_work_proof.state_action_candidate_evaluation_upper_bound"
        ),
        "family_state_caps": _json_copy(ATLAS_FAMILY_STATE_CAPS_V1, "state caps"),
        "total_state_cap": ATLAS_EXACT_STATE_CAP_TOTAL_V1,
        "total_state_action_candidate_cap": (
            ATLAS_EXACT_ACTION_CANDIDATE_CAP_TOTAL_V1
        ),
        "execution": "sequential-fixed-order-all-slots-retained",
        "principal_variation_replay": {
            "orientation_count_per_member": len(ATLAS_D4_TRANSFORMS_V1),
            "orientation_slot_count": ATLAS_DEFINITION_ORIENTATION_COUNT_V1,
            "solve_transformed_orientations": False,
            "transform_and_replay_complete_pv": True,
            "required_invariants": [
                "legal-transformed-action-trace",
                "terminal-ply",
                "terminal-reason",
                "winner",
            ],
            "scalar_value_statement": (
                "derived-from-the-reviewed-D4-game-graph-isomorphism-not-claimed-as-"
                "an-independent-transformed-minimax-solve"
            ),
        },
        "authorization_for_sampled": (
            "all-288-slots-complete-valid-and-all-2304-PV-replays-valid"
        ),
        "ply_limit_semantics": "valid-HORIZON_UNRESOLVED-not-state-censor",
        "state_cap_exhaustion_semantics": "PROOF_CONTRADICTION",
    }


def _sampled_protocol() -> Dict[str, Any]:
    return {
        "ordered_strengths": _json_copy(_STRENGTHS_V1, "sampled strengths"),
        "stronger_route": {
            "status": "NO_STRONGER_STAGE_AUTHORIZED_V1",
            "depth2_status": "SYNTHETIC_CONFORMANCE_ONLY",
            "outcome_informed_strength_addition": "FORBIDDEN",
        },
        "profile_scope": "definition-orientation-strength",
        "role_slot_scope": "definition-orientation-strength-controlled-role",
        "fresh_distinct_role_instances": True,
        "agent_reuse_scope": "one-role-slot-across-ordered-seeds-0-through-7-only",
        "reset_policy": {
            "random-v1-weak": "UNSUPPORTED_STATELESS_AGENT",
            "terminal_only_minimax-v1-depth1": "once-before-seed-0",
        },
        "rng_scope": "fresh-random.Random(seed)-per-game",
        "rng_stream": "one-stream-shared-by-both-roles-in-ply-order",
        "same_seed_across_members_orientations_strengths": True,
        "exact_outcomes_visible_to_agents": False,
        "d4_stabilizer_duplicate_policy": "retain-all-eight-slots",
        "orientation_variation_semantics": "descriptive-not-engine-error",
        "game_ply_cap": ATLAS_GAME_PLY_CAP_V1,
        "legal_action_candidate_cap_per_decision": ATLAS_ACTION_CANDIDATE_CAP_V1,
    }


def _telemetry_protocol(game_root: str) -> Dict[str, Any]:
    section = {
        "telemetry_identity": "replay-telemetry-v1",
        "parent_game_schedule_root": game_root,
        "source": "every-complete-retained-sampled-game-trace",
        "censored_prefix_policy": "FORBIDDEN",
        "exact_principal_variation_channel": "SEPARATE_DESCRIPTIVE_ONLY",
        "admission_routing_or_promotion_use": "NONE_DESCRIPTIVE_ONLY",
        "universal_agency_or_fun_score": "FORBIDDEN",
        "per_game_structural_caps": {
            "replayed_actions": 18,
            "state_observations": 19,
            "legal_actions_per_decision": 48,
            "successor_evaluations": 864,
            "next_action_observations": 41_472,
        },
        "missing_policy": "retain-separate-missing-error-and-censored-denominators",
        "zero_imputation": False,
    }
    section["telemetry_schedule_root"] = _digest(_TELEMETRY_ROOT_DOMAIN_V1, section)
    return section


def _censor_policy() -> Dict[str, Any]:
    section = {
        "preflight_failure": "retry-before-reservation-after-safe-correction",
        "post_reservation_failure": (
            "immutable-failure-evidence-and-new-protocol-version-required"
        ),
        "resume_policy": "NO_IMPLICIT_RESUME_V1",
        "replacement_policy": "NO_SLOT_REPLACEMENT",
        "cap_extension_policy": "NO_POST_OUTCOME_CAP_EXTENSION",
        "partial_prefix_policy": "retain-contiguous-replayable-prefix",
        "later_fixed_slots_after_slot_failure": "continue-and-retain-fixed-order",
        "sampled_stage_gate": "blocked-unless-exact-stage-complete-and-valid",
        "telemetry_stage_gate": (
            "after-both-sampled-terminal-seals-replay-every-complete-trace-even-"
            "when-a-sampled-stage-is-incomplete-or-invalid"
        ),
        "assessment_stage_gate": (
            "always-after-all-upstream-terminal-seals-including-failed-invalid-or-blocked"
        ),
        "proof_contradictions": [
            "exact-state-cap-exhaustion",
            "terminal-depth1-role-slot-node-cap-exhaustion",
            "more-than-48-legal-actions",
            "more-than-18-plies",
            "telemetry-structural-cap-exhaustion",
            "D4-PV-replay-terminal-or-value-disagreement",
        ],
        "normal_horizon_observation": "DRAW-PLY_LIMIT",
        "proof_contradiction_assessment": {
            "exact_solver_exact_pv_and_sampled_channels": "EVIDENCE_INVALID",
            "telemetry_channel": (
                "TELEMETRY_EVIDENCE_INVALID-DESCRIPTIVE-NON_GATE-MANDATORY_INSPECTION"
            ),
        },
        "operational_interruption_assessment": "EVIDENCE_INCOMPLETE",
    }
    section["censor_policy_root"] = _digest(_CENSOR_ROOT_DOMAIN_V1, section)
    return section


def _assessment_protocol() -> Dict[str, Any]:
    section = {
        "claim_level": "FAMILY_FRONTIER_SIGNAL_NOT_FAIR_GAME",
        "manifest_unavailable_meta_report": {
            "admissible_manifest_lifecycles": ["FAILED", "ORPHANED"],
            "required_downstream_lifecycles": {
                "EXACT_ALL_288": "BLOCKED",
                "RANDOM_ALL_18432_GAMES": "BLOCKED",
                "TERMINAL_DEPTH1_ALL_18432_GAMES": "BLOCKED",
                "REPLAY_TELEMETRY_COMPLETE_TRACES_ONLY": "BLOCKED",
            },
            "raw_parent_result_read_count": 0,
            "gameplay_outcome_record_count": 0,
            "candidate_definition_read_or_export_count": 0,
            "fixed_denominators_source": "bootstrap-protocol-constants-only",
            "status": "EXPERIMENT_INVALID_BEFORE_DEVELOPMENT_OUTCOMES",
            "formal_family_or_pair_labels": "FORBIDDEN",
            "terminal_effect": (
                "complete-assessment-stage-with-zero-outcome-meta-report-and-end-plan"
            ),
        },
        "formal_reconstruction_boundary": {
            "owner": "later-manifest-bound-raw-evidence-validator",
            "required_parent_terminal_seals": [
                "protocol_root",
                "manifest_evidence_ref",
                "exact_stage_terminal_seal",
                "random_stage_terminal_seal",
                "terminal_depth1_stage_terminal_seal",
                "telemetry_stage_terminal_seal",
            ],
            "status_ledger_join": {
                "exact": "set-equality-over-all-288-expected-slot-ids",
                "exact_pv_replay": (
                    "set-equality-over-all-2304-expected-orientation-slot-ids-with-"
                    "VALID-INCOMPLETE-INVALID-PROOF_CONTRADICTION-NOT_RUN-or-"
                    "BLOCKED-status"
                ),
                "sampled": "set-equality-over-all-36864-expected-game-slot-ids",
                "telemetry": (
                    "set-equality-over-all-36864-expected-game-slot-ids-with-"
                    "NOT_ADMISSIBLE-iff-no-valid-complete-sampled-trace;-otherwise-"
                    "VALIDATED-MISSING-INVALID-PROOF_CONTRADICTION-or-BLOCKED-with-"
                    "VALIDATED-iff-telemetry-reconstruction-succeeds-and-"
                    "PROOF_CONTRADICTION-iff-a-frozen-structural-cap-is-exceeded"
                ),
                "exact_slot_statuses": [
                    "COMPLETE",
                    "INCOMPLETE",
                    "INVALID",
                    "PROOF_CONTRADICTION",
                    "NOT_RUN",
                    "BLOCKED",
                ],
                "exact_pv_replay_statuses": [
                    "VALID",
                    "INCOMPLETE",
                    "INVALID",
                    "PROOF_CONTRADICTION",
                    "NOT_RUN",
                    "BLOCKED",
                ],
                "sampled_game_statuses": [
                    "COMPLETE",
                    "INCOMPLETE",
                    "INVALID",
                    "PROOF_CONTRADICTION",
                    "NOT_RUN",
                    "BLOCKED",
                ],
                "telemetry_slot_statuses": [
                    "VALIDATED",
                    "NOT_ADMISSIBLE",
                    "MISSING",
                    "INVALID",
                    "PROOF_CONTRADICTION",
                    "BLOCKED",
                ],
                "proof_contradiction_normalization": {
                    "exact_exact_pv_and_sampled": (
                        "retain-distinct-status-and-count-then-map-to-EVIDENCE_INVALID"
                    ),
                    "telemetry": (
                        "retain-distinct-status-and-count-as-descriptive-non-gate-"
                        "TELEMETRY_EVIDENCE_INVALID"
                    ),
                },
                "outcome_evidence": (
                    "duplicate-free-subset-exactly-equal-to-slots-marked-COMPLETE"
                ),
                "support_claim_gate": (
                    "exact-all-288-COMPLETE-valid-plus-all-2304-PV-replays-VALID-"
                    "plus-sampled-all-36864-COMPLETE-valid-with-outcome-evidence-"
                    "set-equality"
                ),
                "failure_reporting": (
                    "reconstruct-invalid-incomplete-not-run-and-blocked-denominators-"
                    "without-imputation"
                ),
            },
            "pair_channel_reconstruction": {
                "shared_reduced_status_priority": [
                    "PROOF_CONTRADICTION",
                    "INVALID",
                    "INCOMPLETE",
                    "BLOCKED",
                    "NOT_RUN",
                    "COMPLETE",
                ],
                "exact": {
                    "scope_per_pair": {
                        "exact_definition_slots": 2,
                        "exact_pv_replay_slots": 16,
                    },
                    "raw_to_reduced_status": {
                        "exact": {
                            "BLOCKED": "BLOCKED",
                            "COMPLETE": "COMPLETE",
                            "INCOMPLETE": "INCOMPLETE",
                            "INVALID": "INVALID",
                            "NOT_RUN": "NOT_RUN",
                            "PROOF_CONTRADICTION": "PROOF_CONTRADICTION",
                        },
                        "exact_pv_replay": {
                            "BLOCKED": "BLOCKED",
                            "INCOMPLETE": "INCOMPLETE",
                            "INVALID": "INVALID",
                            "NOT_RUN": "NOT_RUN",
                            "PROOF_CONTRADICTION": "PROOF_CONTRADICTION",
                            "VALID": "COMPLETE",
                        },
                    },
                    "reducer": (
                        "first-present-status-in-shared_reduced_status_priority-over-"
                        "the-exact-18-slot-multiset"
                    ),
                    "complete_rule": (
                        "both-exact-definition-slots-COMPLETE-and-all-16-PV-replays-VALID"
                    ),
                    "label_rule": (
                        "rebuild-from-the-two-exact-outcomes-only-when-COMPLETE;-"
                        "PROOF_CONTRADICTION-or-INVALID-map-EVIDENCE_INVALID;-all-"
                        "other-noncomplete-statuses-map-EVIDENCE_INCOMPLETE"
                    ),
                },
                "random": {
                    "scope_per_pair": "exactly-128-random-v1-weak-game-slots",
                    "raw_to_reduced_status": {
                        "BLOCKED": "BLOCKED",
                        "COMPLETE": "COMPLETE",
                        "INCOMPLETE": "INCOMPLETE",
                        "INVALID": "INVALID",
                        "NOT_RUN": "NOT_RUN",
                        "PROOF_CONTRADICTION": "PROOF_CONTRADICTION",
                    },
                    "reducer": "first-present-status-in-shared_reduced_status_priority",
                    "complete_rule": (
                        "all-128-slots-COMPLETE-and-outcome-evidence-set-equality"
                    ),
                    "label_rule": (
                        "rebuild-frozen-sampled-strength-label-only-when-COMPLETE;-"
                        "PROOF_CONTRADICTION-or-INVALID-map-EVIDENCE_INVALID;-all-"
                        "other-noncomplete-statuses-map-EVIDENCE_INCOMPLETE"
                    ),
                },
                "terminal_depth1": {
                    "scope_per_pair": (
                        "exactly-128-terminal_only_minimax-v1-depth1-game-slots"
                    ),
                    "raw_to_reduced_status": {
                        "BLOCKED": "BLOCKED",
                        "COMPLETE": "COMPLETE",
                        "INCOMPLETE": "INCOMPLETE",
                        "INVALID": "INVALID",
                        "NOT_RUN": "NOT_RUN",
                        "PROOF_CONTRADICTION": "PROOF_CONTRADICTION",
                    },
                    "reducer": "first-present-status-in-shared_reduced_status_priority",
                    "complete_rule": (
                        "all-128-slots-COMPLETE-and-outcome-evidence-set-equality"
                    ),
                    "label_rule": (
                        "rebuild-frozen-sampled-strength-label-only-when-COMPLETE;-"
                        "PROOF_CONTRADICTION-or-INVALID-map-EVIDENCE_INVALID;-all-"
                        "other-noncomplete-statuses-map-EVIDENCE_INCOMPLETE"
                    ),
                },
                "telemetry": {
                    "scope_per_pair": (
                        "exactly-256-telemetry-slots-for-both-strengths-2-members-"
                        "8-orientations-and-8-seeds"
                    ),
                    "raw_to_reduced_status": {
                        "BLOCKED": "BLOCKED",
                        "INVALID": "INVALID",
                        "MISSING": "INCOMPLETE",
                        "NOT_ADMISSIBLE": "COMPLETE",
                        "PROOF_CONTRADICTION": "PROOF_CONTRADICTION",
                        "VALIDATED": "COMPLETE",
                    },
                    "reducer_priority": [
                        "PROOF_CONTRADICTION",
                        "INVALID",
                        "INCOMPLETE",
                        "BLOCKED",
                        "COMPLETE",
                    ],
                    "complete_rule": (
                        "all-256-raw-statuses-VALIDATED-or-NOT_ADMISSIBLE-and-each-"
                        "VALIDATED-iff-corresponding-sampled-trace-is-valid-complete-"
                        "and-reconstruction-succeeds"
                    ),
                    "post_attempt_failure_fill": (
                        "unreached-valid-complete-sampled-trace-is-MISSING;-unreached-"
                        "nonadmissible-sampled-trace-is-NOT_ADMISSIBLE;-BLOCKED-is-"
                        "reserved-for-a-telemetry-stage-that-never-attempted-because-"
                        "a-closed-prerequisite-gate-failed"
                    ),
                    "formal_effect": (
                        "never-changes-exact-random-terminal-depth1-pair-or-family-"
                        "frontier-labels;-noncomplete-selects-MANDATORY_EXCEPTION-and-"
                        "telemetry-dependent-metrics-follow-their-own-admission-rules"
                    ),
                },
            },
            "telemetry_relation": (
                "non-gate-for-formal-frontier-labels-but-terminal-seal-and-missing-"
                "denominators-are-bound-into-the-final-report"
            ),
            "caller_supplied_aggregate_or_label_is_authoritative": False,
            "leaf_arithmetic_helpers_are_formal_evidence_boundaries": False,
        },
        "fairness_unit": {
            "exact": "one-same-setup-A_FIRST-B_FIRST-pair",
            "sampled": (
                "one-pair-strength-aggregate-of-2-members-times-8-orientations-times-8-seeds"
            ),
            "matched_start_block": (
                "same-roles-two-games-with-A_FIRST-and-B_FIRST-at-fixed-transform-strength-seed"
            ),
            "single_DSL_definition_fairness_claim": False,
            "orientation_or_seed_iid_claim": False,
        },
        "exact_pair_labels": {
            "A_WIN,A_WIN": "A_ROLE_DOMINANT",
            "B_WIN,B_WIN": "B_ROLE_DOMINANT",
            "A_WIN,B_WIN": "FIRST_PLAYER_DOMINANT",
            "B_WIN,A_WIN": "SECOND_PLAYER_DOMINANT",
            "any_DRAW_PLY_LIMIT": "HORIZON_UNRESOLVED",
            "incomplete": "EVIDENCE_INCOMPLETE",
            "invalid": "EVIDENCE_INVALID",
        },
        "unexpected_natural_draw_semantics": (
            "INVALID_EXACT_EVIDENCE-current-atlas-stuck-policy-is-loss"
        ),
        "exact_frontier_eligible_labels": [
            "FIRST_PLAYER_DOMINANT",
            "SECOND_PLAYER_DOMINANT",
        ],
        "sampled_strength_gate": {
            "scheduled_games": ATLAS_SAMPLED_GAMES_PER_PAIR_STRENGTH_V1,
            "required_completed_games": ATLAS_SAMPLED_GAMES_PER_PAIR_STRENGTH_V1,
            "minimum_decisive_games": ATLAS_SAMPLED_MIN_DECISIVE_GAMES_V1,
            "minority_decisive_share": {
                "numerator": ATLAS_SAMPLED_MINORITY_SHARE_NUMERATOR_V1,
                "denominator": ATLAS_SAMPLED_MINORITY_SHARE_DENOMINATOR_V1,
                "integer_test": "20*min(A_wins,B_wins)>=7*(A_wins+B_wins)",
            },
            "passing_label": "WEAK_BALANCE_SIGNAL_V1",
            "required_strengths": [
                "random-v1-weak",
                "terminal_only_minimax-v1-depth1",
            ],
        },
        "pair_frontier_rule": (
            "exact-frontier-eligible-and-both-strengths-WEAK_BALANCE_SIGNAL_V1"
        ),
        "family_frontier_rule": {
            "development_pair_denominator": 24,
            "minimum_pair_frontier_count": ATLAS_FAMILY_FRONTIER_MIN_PAIR_COUNT_V1,
            "minimum_distinct_paired_strata": (
                ATLAS_FAMILY_FRONTIER_MIN_STRATUM_COUNT_V1
            ),
            "supported_label": "SUPPORTED_FAMILY_FRONTIER",
            "complete_negative_label": "NOT_SUPPORTED_COMPLETE",
            "incomplete_label": "INCONCLUSIVE_INCOMPLETE",
            "invalid_label": "EVIDENCE_INVALID",
            "status_priority": [
                "EVIDENCE_INVALID",
                "INCONCLUSIVE_INCOMPLETE",
                "SUPPORTED_FAMILY_FRONTIER",
                "NOT_SUPPORTED_COMPLETE",
            ],
            "complete_negative_scope": (
                "this-fixed-18-ply-six-family-3x3-core-only-not-a-general-family-claim"
            ),
        },
        "assessment_reporting": {
            "dimensions": [
                "definition_index",
                "pair_index",
                "family_id",
                "paired_stratum_id",
                "goal_frame",
                "A_vector_profile",
                "B_vector_profile",
                "first_player",
                "orientation",
                "strength",
                "controlled_role",
            ],
            "fixed_denominators": {
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
            },
            "count_fields": {
                "exact": [
                    "scheduled",
                    "complete",
                    "incomplete",
                    "invalid",
                    "not_run",
                    "blocked",
                    "proof_contradiction",
                    "A_WIN",
                    "B_WIN",
                    "DRAW_PLY_LIMIT",
                    "searched_states",
                    "max_states",
                ],
                "exact_pv_replay": [
                    "scheduled",
                    "valid",
                    "incomplete",
                    "invalid",
                    "not_run",
                    "blocked",
                    "proof_contradiction",
                ],
                "sampled": [
                    "scheduled",
                    "complete",
                    "incomplete",
                    "invalid",
                    "not_run",
                    "blocked",
                    "proof_contradiction",
                    "A_WIN",
                    "B_WIN",
                    "DRAW_PLY_LIMIT",
                    "plies",
                    "search_nodes",
                ],
                "telemetry": [
                    "scheduled_complete_traces",
                    "validated_traces",
                    "not_admissible_traces",
                    "missing_traces",
                    "invalid_traces",
                    "proof_contradiction_traces",
                    "blocked_traces",
                    "decision_count_by_role",
                    "forced_decision_count_by_role",
                    "opponent_dependency_action_count_by_role",
                    "same_game_reciprocal_dependency_count",
                    "repetition_count",
                    "telemetry_work_by_field",
                ],
            },
            "status_count_reconstruction": {
                "exact": (
                    "scheduled=complete+incomplete+invalid+not_run+blocked+"
                    "proof_contradiction"
                ),
                "exact_pv_replay": (
                    "scheduled=valid+incomplete+invalid+not_run+blocked+"
                    "proof_contradiction"
                ),
                "sampled": (
                    "scheduled=complete+incomplete+invalid+not_run+blocked+"
                    "proof_contradiction"
                ),
                "telemetry": (
                    "telemetry_slots_total=validated_traces+not_admissible_traces+"
                    "missing_traces+invalid_traces+proof_contradiction_traces+"
                    "blocked_traces;-scheduled_complete_traces=validated_traces+"
                    "missing_traces+invalid_traces+proof_contradiction_traces"
                ),
            },
            "ratio_encoding": (
                "reduced-numerator-denominator-integers-no-floats-no-zero-imputation"
            ),
            "aggregation": (
                "sum-raw-integer-numerators-and-denominators-never-average-per-slot-ratios"
            ),
            "orientation_pooling": (
                "retain-eight-orientations-and-report-pooled-counts-only-alongside-"
                "orientation-separated-counts"
            ),
            "censoring": (
                "scheduled-complete-incomplete-invalid-and-horizon-denominators-remain-separate"
            ),
            "exact_direction_confusion": {
                "unit": "definition-member-strength-over-8-orientations-times-8-seeds",
                "sampled_direction": {
                    "A_wins>B_wins": "A_DIRECTION",
                    "B_wins>A_wins": "B_DIRECTION",
                    "A_wins==B_wins": "TIED_DIRECTION",
                },
                "confusion": (
                    "exact-A_WIN-with-B_DIRECTION-or-exact-B_WIN-with-A_DIRECTION"
                ),
                "tie": "reported-separately-not-confusion",
                "exact_draw_incomplete_or_invalid": "NOT_APPLICABLE_REPORTED_SEPARATELY",
            },
            "universal_score": "FORBIDDEN",
        },
        "all_supported_families_retained": True,
        "formal_non_gates": [
            "Wilson-confidence-interval",
            "mean-game-length",
            "strength-disagreement",
            "orientation-disagreement",
            "replay-telemetry",
            "simplicity-ranking",
            "human-enjoyment",
        ],
        "agent_adequacy": (
            "exact-direction-confusion-is-descriptive-and-depth1-never-establishes-credible-fairness"
        ),
        "promotion_destination": (
            "new-outcome-exposed-exploratory-development-version-not-confirmation"
        ),
        "confirmation_candidate_allocation": "FORBIDDEN_IN_PROTOCOL_V1",
    }
    section["assessment_root"] = _digest(_ASSESSMENT_ROOT_DOMAIN_V1, section)
    return section


def _inspection_protocol() -> Dict[str, Any]:
    section = {
        "unit": "matched-setup-pair",
        "calculation_owner": (
            "later-manifest-bound-raw-evidence-validator-calls-frozen-private-helpers"
        ),
        "input_contract": {
            "pair_count": ATLAS_DEVELOPMENT_PAIR_COUNT_V1,
            "manifest_index_order_required": True,
            "family_pair_count": 24,
            "required_channel_statuses": [
                "exact",
                "random",
                "terminal_depth1",
                "telemetry",
            ],
            "required_rebuilt_labels": [
                "exact_label",
                "random_label",
                "terminal_depth1_label",
                "pair_assessment",
            ],
            "caller_supplied_metrics_are_formal_evidence": False,
            "raw_schedule_join_required_before_selection": True,
            "pair_channel_status_is_metric_admission_input": False,
            "metric_admission_owner": (
                "rebuild-each-metric-status-from-its-declared-raw-slot-subset-"
                "independently-of-the-mandatory-inspection-channel-status"
            ),
        },
        "metric_admission_status_mapping": {
            "exact_or_sampled_raw": {
                "COMPLETE": "COMPLETE",
                "INCOMPLETE": "INCOMPLETE",
                "INVALID": "INVALID",
                "PROOF_CONTRADICTION": "INVALID",
                "NOT_RUN": "INCOMPLETE",
                "BLOCKED": "INCOMPLETE",
            },
            "telemetry_raw": {
                "VALIDATED": "COMPLETE",
                "NOT_ADMISSIBLE": "INCOMPLETE",
                "MISSING": "INCOMPLETE",
                "INVALID": "INVALID",
                "PROOF_CONTRADICTION": "INVALID",
                "BLOCKED": "INCOMPLETE",
            },
            "subset_reducer_priority": ["INVALID", "INCOMPLETE", "COMPLETE"],
        },
        "fraction_schema": {
            "defined": {
                "keys": ["status", "numerator", "denominator"],
                "status": "DEFINED",
                "denominator": "positive-exact-integer",
                "normal_form": "gcd-reduced-with-zero-exactly-0-over-1",
            },
            "missing": {
                "keys": ["status", "reason"],
                "status": "MISSING",
                "closed_reasons": [
                    "INCOMPLETE_EXACT",
                    "INCOMPLETE_RANDOM",
                    "INCOMPLETE_DEPTH1",
                    "INCOMPLETE_TELEMETRY",
                    "INVALID_EVIDENCE",
                    "ZERO_DECISIVE_RANDOM",
                    "ZERO_DECISIVE_DEPTH1",
                    "ZERO_DECISIVE_ORIENTATION",
                    "ZERO_DECISIONS",
                ],
            },
            "comparison": "exact-integer-cross-multiplication-no-floats",
        },
        "metric_definitions": {
            "exact_state_utilization": {
                "components": "A_FIRST-and-B_FIRST-searched_states/max_states",
                "pair_value": "maximum-member-ratio",
                "source_tie_order": list(ATLAS_MEMBER_ORDER_V1),
                "admission": "both-exact-members-complete-valid",
                "raw_status_scope": "two-exact-solver-slots-only-PV-replays-excluded",
            },
            "strength_role_share_gap": {
                "per_strength": (
                    "A_wins/(A_wins+B_wins)-over-all-128-pair-strength-games"
                ),
                "pair_value": "absolute-random-minus-terminal-depth1-share",
                "admission": "both-strengths-complete-and-both-decisive-denominators-positive",
                "raw_status_scope": (
                    "128-random-plus-128-terminal-depth1-sampled-game-slots-only"
                ),
            },
            "d4_outcome_range": {
                "per_orientation": (
                    "A_wins/(A_wins+B_wins)-over-2-members-times-8-seeds"
                ),
                "pair_strength_value": "maximum-of-eight-shares-minus-minimum-of-eight-shares",
                "source_tie_order": list(ATLAS_D4_TRANSFORMS_V1),
                "admission": (
                    "all-eight-orientations-complete-and-each-decisive-denominator-positive"
                ),
                "raw_status_scope": (
                    "16-sampled-game-slots-per-orientation-for-the-requested-strength"
                ),
            },
            "depth1_ply_limit_rate": {
                "numerator": "terminal-depth1-games-with-terminal_reason-PLY_LIMIT",
                "denominator": ATLAS_SAMPLED_GAMES_PER_PAIR_STRENGTH_V1,
                "admission": "all-128-terminal-depth1-games-complete-valid",
                "raw_status_scope": "128-terminal-depth1-sampled-game-slots-only",
            },
            "forced_decision_fraction": {
                "scope": "terminal-depth1-pair-role",
                "numerator": (
                    "sum-replay-telemetry-role-legal_count_bin_1-over-all-128-games"
                ),
                "denominator": (
                    "sum-replay-telemetry-role-decision_count-over-all-128-games"
                ),
                "weighting": "pooled-decisions-never-mean-of-per-game-fractions",
                "admission": "all-128-depth1-telemetry-records-valid-and-denominator-positive",
                "raw_status_scope": (
                    "128-terminal-depth1-telemetry-slots-only-random-telemetry-excluded"
                ),
            },
            "depth1_reciprocal_dependency_fraction": {
                "numerator": (
                    "depth1-games-where-both-roles-have-at-least-one-opponent-dependency-action"
                ),
                "denominator": ATLAS_SAMPLED_GAMES_PER_PAIR_STRENGTH_V1,
                "zero-decision-complete-game": "FALSE_NOT_MISSING",
                "admission": "all-128-depth1-telemetry-records-valid",
                "raw_status_scope": (
                    "128-terminal-depth1-telemetry-slots-only-random-telemetry-excluded"
                ),
            },
        },
        "union_deduplication_order": "development-manifest-order",
        "retain_all_selection_reasons": True,
        "score_domain_hex": _INSPECTION_SCORE_DOMAIN_V1.hex(),
        "score_payload_keys": [
            "class",
            "direction",
            "group",
            "paired_mechanical_d4_identity",
        ],
        "tie_break_order": [
            "metric-exact-rational-in-requested-direction",
            "inspection-score-ascending",
            "paired-mechanical-d4-identity-ascending",
        ],
        "direction_expansion_order": ["LOW", "HIGH"],
        "missing_metric_policy": "exclude-no-replacement-and-report-missing-count",
        "classes": [
            {
                "class": "MANDATORY_EXCEPTION",
                "source": (
                    "any-channel-noncomplete-exact-horizon-or-either-sampled-"
                    "EXCESSIVE_HORIZON_SIGNAL"
                ),
                "direction": "ALL",
                "group": "GLOBAL",
                "quota": "ALL",
            },
            {
                "class": "PAIR_FRONTIER",
                "source": "formal-pair-frontier-signal",
                "direction": "ALL",
                "group": "GLOBAL",
                "quota": "ALL",
            },
            {
                "class": "ORDINARY_CONTROL",
                "source": "complete-nonfrontier-pairs",
                "direction": "HASH_MIN",
                "group": "PAIRED_STRATUM",
                "quota": 1,
            },
            {
                "class": "EXACT_STATE_UTILIZATION",
                "metric": "exact_state_utilization",
                "direction": "HIGH",
                "group": "FAMILY",
                "quota": 1,
            },
            {
                "class": "STRENGTH_ROLE_SHARE_GAP",
                "metric": "strength_role_share_gap",
                "direction": "HIGH",
                "group": "FAMILY",
                "quota": 1,
            },
            {
                "class": "D4_OUTCOME_RANGE",
                "metric": "d4_outcome_range",
                "direction": "HIGH",
                "group": "FAMILY_X_STRENGTH",
                "quota": 1,
            },
            {
                "class": "DEPTH1_PLY_LIMIT_RATE",
                "metric": "depth1_ply_limit_rate",
                "direction": "LOW_AND_HIGH",
                "group": "FAMILY",
                "quota_per_direction": 1,
            },
            {
                "class": "FORCED_DECISION_FRACTION",
                "metric": "forced_decision_fraction",
                "direction": "LOW_AND_HIGH",
                "group": "FAMILY_X_ROLE",
                "quota_per_direction": 1,
            },
            {
                "class": "DEPTH1_RECIPROCAL_DEPENDENCY_FRACTION",
                "metric": "depth1_reciprocal_dependency_fraction",
                "direction": "LOW_AND_HIGH",
                "group": "FAMILY",
                "quota_per_direction": 1,
            },
        ],
        "human_inspection_effect": (
            "diagnose-future-version-only-never-change-current-formal-label"
        ),
        "selection_builder": "_calculate_atlas_inspection_selection_v1",
        "selection_output": (
            "unsealed-private-calculation-of-per-class-group-population-defined-"
            "missing-selected-counts-plus-manifest-ordered-union-with-all-reasons"
        ),
        "formal_selection_seal_owner": (
            "later-result-validator-after-development-identity-set-and-all-raw-roots-join"
        ),
    }
    section["inspection_root"] = _digest(_INSPECTION_ROOT_DOMAIN_V1, section)
    return section


def _stage_source_closure_policy(stage_id: str) -> Dict[str, Any]:
    universal = (
        "src/parity_forge/__init__.py",
        "src/parity_forge/atlas_protocol.py",
        "src/parity_forge/dsl.py",
        "src/parity_forge/engine.py",
    )
    policies = {
        "OUTCOME_FREE_DEVELOPMENT_MANIFEST": {
            "required_known_paths": tuple(
                dict.fromkeys(universal + _SELECTOR_CLOSURE_PATHS_V1)
            ),
            "forbidden_known_paths": (
                "src/parity_forge/agency.py",
                "src/parity_forge/agents.py",
                "src/parity_forge/play.py",
                "src/parity_forge/solver.py",
                "src/parity_forge/terminal_search.py",
            ),
        },
        "EXACT_ALL_288": {
            "required_known_paths": universal
            + (
                "src/parity_forge/solver.py",
                "src/parity_forge/symmetry.py",
            ),
            "forbidden_known_paths": (
                "src/parity_forge/agency.py",
                "src/parity_forge/agents.py",
                "src/parity_forge/atlas.py",
                "src/parity_forge/atlas_history.py",
                "src/parity_forge/atlas_projection.py",
                "src/parity_forge/feasibility.py",
                "src/parity_forge/feasibility_census.py",
                "src/parity_forge/play.py",
                "src/parity_forge/terminal_search.py",
            ),
        },
        "RANDOM_ALL_18432_GAMES": {
            "required_known_paths": universal
            + (
                "src/parity_forge/agents.py",
            ),
            "forbidden_known_paths": (
                "src/parity_forge/agency.py",
                "src/parity_forge/atlas.py",
                "src/parity_forge/atlas_history.py",
                "src/parity_forge/atlas_projection.py",
                "src/parity_forge/feasibility.py",
                "src/parity_forge/feasibility_census.py",
                "src/parity_forge/play.py",
                "src/parity_forge/solver.py",
                "src/parity_forge/terminal_search.py",
            ),
        },
        "TERMINAL_DEPTH1_ALL_18432_GAMES": {
            "required_known_paths": universal
            + (
                "src/parity_forge/agents.py",
                "src/parity_forge/terminal_search.py",
            ),
            "forbidden_known_paths": (
                "src/parity_forge/agency.py",
                "src/parity_forge/atlas.py",
                "src/parity_forge/atlas_history.py",
                "src/parity_forge/atlas_projection.py",
                "src/parity_forge/feasibility.py",
                "src/parity_forge/feasibility_census.py",
                "src/parity_forge/play.py",
                "src/parity_forge/solver.py",
            ),
        },
        "REPLAY_TELEMETRY_COMPLETE_TRACES_ONLY": {
            "required_known_paths": universal
            + ("src/parity_forge/agency.py",),
            "forbidden_known_paths": (
                "src/parity_forge/agents.py",
                "src/parity_forge/atlas.py",
                "src/parity_forge/atlas_history.py",
                "src/parity_forge/atlas_projection.py",
                "src/parity_forge/feasibility.py",
                "src/parity_forge/feasibility_census.py",
                "src/parity_forge/play.py",
                "src/parity_forge/solver.py",
                "src/parity_forge/terminal_search.py",
            ),
        },
        "ASSESSMENT_AND_INSPECTION": {
            "required_known_paths": universal,
            "forbidden_known_paths": (
                "src/parity_forge/agency.py",
                "src/parity_forge/agents.py",
                "src/parity_forge/atlas.py",
                "src/parity_forge/atlas_history.py",
                "src/parity_forge/atlas_projection.py",
                "src/parity_forge/feasibility.py",
                "src/parity_forge/feasibility_census.py",
                "src/parity_forge/play.py",
                "src/parity_forge/solver.py",
                "src/parity_forge/terminal_search.py",
            ),
        },
    }
    try:
        policy = policies[stage_id]
    except KeyError as error:
        raise AssertionError("unknown development evidence stage") from error
    required_paths = list(policy["required_known_paths"])
    checkpoint_commit = (
        ATLAS_SELECTOR_COMMIT_V1
        if stage_id == "OUTCOME_FREE_DEVELOPMENT_MANIFEST"
        else ATLAS_EVALUATOR_COMMIT_V1
    )
    checkpoint_paths = [
        path
        for path in required_paths
        if path != "src/parity_forge/atlas_protocol.py"
    ]
    return {
        "stage_id": stage_id,
        "required_known_paths": required_paths,
        "forbidden_known_paths": list(policy["forbidden_known_paths"]),
        "checkpoint_blob_equivalence": {
            "reference_commit": checkpoint_commit,
            "paths": checkpoint_paths,
            "required_relation": "byte-identical-Git-blobs-at-production-source-commit",
            "mismatch_policy": (
                "new-reviewed-selector-or-evaluator-checkpoint-and-new-protocol-version-"
                "required-before-reservation"
            ),
        },
        "protocol_and_future_stage_paths": (
            "pin-all-reviewed-blobs-at-the-outcome-free-manifest-source-commit"
        ),
        "protocol_blob_binding": (
            "freeze-current-atlas_protocol.py-blob-in-bootstrap-and-completed-"
            "manifest-copy"
            if stage_id == "OUTCOME_FREE_DEVELOPMENT_MANIFEST"
            else "require-byte-identity-with-bootstrap-frozen-atlas_protocol.py-blob"
        ),
        "sampled_loop_implementation": (
            "new-reviewed-stage-module-reproducing-benchmark-lifecycle-and-all-protocol-ledgers"
            if stage_id
            in ("RANDOM_ALL_18432_GAMES", "TERMINAL_DEPTH1_ALL_18432_GAMES")
            else None
        ),
        "concrete_entrypoint_and_recursive_imports_must_be_bootstrap_frozen": True,
        "definitions_source": (
            "detached-development-manifest-only"
            if stage_id
            not in (
                "OUTCOME_FREE_DEVELOPMENT_MANIFEST",
                "ASSESSMENT_AND_INSPECTION",
            )
            else (
                "sealed-full-selection-validation-with-development-only-export"
                if stage_id == "OUTCOME_FREE_DEVELOPMENT_MANIFEST"
                else (
                    "detached-development-manifest-when-available;-otherwise-frozen-"
                    "bootstrap-protocol-plus-authentic-terminal-chain-for-zero-outcome-"
                    "meta-failure-assessment-only"
                )
            )
        ),
    }


def _execution_evidence_protocol() -> Dict[str, Any]:
    section = {
        "owner": "later-one-shot-experiment-edge",
        "evidence_protocol_version": 2,
        "evidence_protocol_id": "plan0013-atlas-development-evidence-v2",
        "evidence_store_relative_path": (
            "experiments/runs/plan0013-atlas-development-evidence-v2"
        ),
        "evidence_mode": "IMMUTABLE_DEVELOPMENT_NOT_HELD_OUT_CONFIRMATION",
        "candidate_block_access": {
            "protocol_and_manifest_canonical_validation_read": "ALLOWED",
            "definition_export": "FORBIDDEN",
            "outcome_capable_stage_input": "FORBIDDEN",
            "evaluation": "FORBIDDEN",
            "allocation_or_replacement": "FORBIDDEN",
        },
        "full_selection_read_scope": (
            "protocol-and-manifest-preflight-canonical-validation-only-no-candidate-export"
        ),
        "requirements": [
            "clean-HEAD-and-strict-selector-evaluator-ancestry",
            "candidate-neutral-bootstrap-before-manifest-reservation",
            "authenticated-closure-blobs-and-bootstrap-frozen-experiment-plan-blob",
            "development-only-detached-manifest-input-to-evaluators",
            "reservation-before-first-stage-capability",
            "immutable-reservation-attempt-failure-and-completed-artifacts",
            "raw-canonical-byte-SHA-and-length-locks",
            "pre-and-post-execution-source-reseal",
            "no-symlink-internal-write-paths",
        ],
        "outcome_free_manifest_bootstrap": {
            "publication_order": (
                "protocol-then-all-six-production-closures-then-experiment-plan-"
                "then-bootstrap-catalog-before-manifest-stage-reservation"
            ),
            "capability": (
                "candidate-neutral-protocol-commitments-and-code-provenance-only-"
                "no-definition-body-no-outcome"
            ),
            "crash_policy": (
                "idempotently-verify-and-complete-an-identical-prefix-before-"
                "reservation;partial-bootstrap-grants-no-stage-capability"
            ),
            "binding": (
                "catalog-body-refs-plus-protocol-root-plan-SHA-source-commit-tree-"
                "and-self-rooted-all-six-closure-identities"
            ),
            "identity_schema": {
                "domain_hex": _MANIFEST_BOOTSTRAP_ROOT_DOMAIN_V1.hex(),
                "payload_keys": [
                    "artifact_type",
                    "evidence_protocol_id",
                    "experiment_plan_ref",
                    "production_closure_count",
                    "production_closures_ref",
                    "protocol_id",
                    "protocol_ref",
                    "protocol_root",
                    "source_commit",
                    "source_tree",
                ],
            },
            "manifest_completed_relation": (
                "the-later-four-artifact-manifest-freeze-must-byte-match-bootstrap-"
                "protocol-production-closures-and-plan"
            ),
            "manifest_unavailable_relation": (
                "FAILED-or-ORPHANED-manifest-keeps-bootstrap-authentic-so-every-"
                "outcome-stage-can-seal-BLOCKED-and-assessment-can-emit-only-the-"
                "zero-outcome-meta-failure-report"
            ),
        },
        "artifact_identity_schemas": {
            "canonicalization": {
                "encoding": "UTF-8",
                "json": (
                    "RFC8259-finite-tree-sort_keys-true-separators-comma-colon-"
                    "ensure_ascii-false-no-floats-no-duplicate-keys"
                ),
                "identity_formula": "lowercase-hex-SHA256(domain-bytes+canonical-json-bytes)",
                "stage_artifact_body_root_formula": (
                    "lowercase-hex-SHA256-over-the-exact-finite-canonical-JSON-bytes-"
                    "of-the-referenced-immutable-stage-artifact"
                ),
            },
            "production_closure_root": {
                "domain_hex": _PRODUCTION_CLOSURE_ROOT_DOMAIN_V1.hex(),
                "payload_keys": [
                    "manifest_experiment_plan_sha256",
                    "manifest_protocol_blob_identity",
                    "ordered_entrypoint_paths",
                    "ordered_file_records",
                    "source_commit",
                    "source_tree",
                    "stage_id",
                ],
                "ordered_file_record_keys": [
                    "byte_count",
                    "current_sha256",
                    "path",
                    "source_commit_blob_sha1",
                ],
                "path_order": "unique-strict-ascending-ASCII-repository-relative-paths",
                "entrypoint_relation": (
                    "nonempty-subset-of-ordered-file-record-paths-in-strict-ASCII-order"
                ),
                "source_commit_blob_sha1": "lowercase-40-hex-Git-blob-identity",
                "current_sha256": "lowercase-64-hex-over-exact-current-file-bytes",
                "byte_count": "nonnegative-exact-integer-over-same-current-file-bytes",
                "manifest_protocol_blob_identity": (
                    "source_commit_blob_sha1-from-the-unique-ordered-file-record-for-"
                    "src/parity_forge/atlas_protocol.py"
                ),
                "manifest_experiment_plan_sha256": (
                    "lowercase-64-hex-SHA256-over-the-exact-bootstrap-frozen-"
                    "experiment-plan-artifact-bytes"
                ),
            },
            "manifest_evidence_ref": {
                "keys": [
                    "kind",
                    "manifest_completed_root_or_null",
                    "manifest_stage_terminal_seal",
                ],
                "kind_values": ["COMPLETED_MANIFEST", "UNAVAILABLE_MANIFEST"],
                "terminal_seal_encoding": "lowercase-64-hex-terminal-seal-identity",
                "completed_rule": (
                    "COMPLETED_MANIFEST-iff-referenced-manifest-terminal-lifecycle-is-"
                    "COMPLETED-and-manifest_completed_root_or_null-equals-its-"
                    "completed_root"
                ),
                "unavailable_rule": (
                    "UNAVAILABLE_MANIFEST-iff-referenced-manifest-terminal-lifecycle-"
                    "is-FAILED-or-ORPHANED-and-manifest_completed_root_or_null-is-null"
                ),
            },
            "stage_reservation_id": {
                "domain_hex": _STAGE_RESERVATION_ID_DOMAIN_V1.hex(),
                "payload_keys": [
                    "evidence_protocol_id",
                    "manifest_evidence_ref_or_null",
                    "manifest_experiment_plan_sha256",
                    "ordered_parent_terminal_seals",
                    "production_closure_root",
                    "protocol_id",
                    "protocol_root",
                    "stage_id",
                    "stage_protocol_id",
                ],
                "manifest_evidence_ref_rule": (
                    "null-only-for-manifest-stage-reservation;-all-downstream-"
                    "reservations-use-the-canonical-manifest_evidence_ref"
                ),
                "manifest_evidence_ref_stage_policy": {
                    "OUTCOME_FREE_DEVELOPMENT_MANIFEST": "null",
                    "EXACT_ALL_288": "COMPLETED_MANIFEST-only",
                    "RANDOM_ALL_18432_GAMES": "COMPLETED_MANIFEST-only",
                    "TERMINAL_DEPTH1_ALL_18432_GAMES": "COMPLETED_MANIFEST-only",
                    "REPLAY_TELEMETRY_COMPLETE_TRACES_ONLY": (
                        "COMPLETED_MANIFEST-only"
                    ),
                    "ASSESSMENT_AND_INSPECTION": (
                        "COMPLETED_MANIFEST-or-UNAVAILABLE_MANIFEST"
                    ),
                },
                "parent_membership_and_order": (
                    "exactly-equal-to-the-stage-required_parent_terminal_stage_ids-"
                    "mapped-to-terminal-seals-with-no-duplicates"
                ),
                "parent_terminal_seal_element": "lowercase-64-hex-terminal-seal-identity",
            },
            "stage_attempt_id": {
                "domain_hex": _STAGE_ATTEMPT_ID_DOMAIN_V1.hex(),
                "payload_keys": [
                    "attempt_index",
                    "production_closure_root",
                    "reservation_id",
                    "source_commit",
                    "source_tree",
                ],
                "attempt_index": "exact-integer-zero-in-v1",
            },
            "stage_blocked_id": {
                "domain_hex": _STAGE_BLOCKED_ID_DOMAIN_V1.hex(),
                "payload_keys": [
                    "evidence_protocol_id",
                    "failed_prerequisite_stage_id",
                    "manifest_evidence_ref",
                    "prerequisite_terminal_seal",
                    "production_closure_root",
                    "protocol_id",
                    "protocol_root",
                    "stage_id",
                    "stage_protocol_id",
                ],
                "reservation_or_attempt_relation": "both-forbidden",
            },
            "stage_orphaned_id": {
                "domain_hex": _STAGE_ORPHANED_ID_DOMAIN_V1.hex(),
                "payload_keys": [
                    "attempt_id_or_null",
                    "orphan_reason",
                    "partial_evidence_root_or_null",
                    "reservation_id",
                    "stage_id",
                    "stage_protocol_id",
                ],
                "orphan_reason_values": [
                    "ATTEMPT_WITHOUT_TERMINAL_SEAL",
                    "RESERVATION_WITHOUT_ATTEMPT",
                ],
                "reason_attempt_nullability": {
                    "ATTEMPT_WITHOUT_TERMINAL_SEAL": "attempt_id_or_null-is-nonnull",
                    "RESERVATION_WITHOUT_ATTEMPT": "attempt_id_or_null-is-null",
                },
                "partial_evidence_stage_policy": {
                    "EXACT_ALL_288": "nonnull-reconciled-full-fixed-status-ledger-root",
                    "RANDOM_ALL_18432_GAMES": (
                        "nonnull-reconciled-full-fixed-status-ledger-root"
                    ),
                    "TERMINAL_DEPTH1_ALL_18432_GAMES": (
                        "nonnull-reconciled-full-fixed-status-ledger-root"
                    ),
                    "REPLAY_TELEMETRY_COMPLETE_TRACES_ONLY": (
                        "nonnull-reconciled-full-fixed-status-ledger-root"
                    ),
                    "OUTCOME_FREE_DEVELOPMENT_MANIFEST": "null-or-retained-partial-root",
                    "ASSESSMENT_AND_INSPECTION": "null-or-retained-partial-root",
                },
                "creation_gate": (
                    "exclusive-stage-lock-acquired-after-original-process-is-not-live-"
                    "and-no-valid-blocked-completed-failure-or-terminal-artifact-exists"
                ),
                "capability_boundary": (
                    "reconcile-existing-immutable-evidence-only-no-resume-no-new-"
                    "solver-agent-game-telemetry-or-formal-claim;-pure-reconstruction-"
                    "of-an-already-present-completed-assessment-summary-is-validation"
                ),
            },
            "stage_terminal_seal": {
                "domain_hex": _STAGE_TERMINAL_SEAL_DOMAIN_V1.hex(),
                "payload_keys": [
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
                ],
                "lifecycle_values": [
                    "BLOCKED",
                    "ORPHANED",
                    "FAILED",
                    "COMPLETED",
                ],
                "exclusive_nullability": (
                    "BLOCKED-requires-only-blocked-id;-ORPHANED-requires-reservation-"
                    "orphaned-id-and-optional-attempt-and-partial-evidence;-FAILED-"
                    "requires-reservation-attempt-failure-and-partial-evidence-roots;-"
                    "COMPLETED-requires-reservation-attempt-and-completed-roots"
                ),
            },
            "cross_artifact_relations": {
                "equality_relations": [
                    {
                        "left": "stage_reservation.production_closure_root",
                        "relation": "EQUAL",
                        "right": "identity(referenced_production_closure)",
                    },
                    {
                        "left": "stage_reservation.stage_id",
                        "relation": "EQUAL",
                        "right": "referenced_production_closure.stage_id",
                    },
                    {
                        "left": "stage_reservation.manifest_experiment_plan_sha256",
                        "relation": "EQUAL",
                        "right": (
                            "referenced_production_closure."
                            "manifest_experiment_plan_sha256"
                        ),
                    },
                    {
                        "left": "stage_attempt.reservation_id",
                        "relation": "EQUAL",
                        "right": "identity(referenced_stage_reservation)",
                    },
                    {
                        "left": "stage_attempt.production_closure_root",
                        "relation": "EQUAL",
                        "right": "referenced_stage_reservation.production_closure_root",
                    },
                    {
                        "left": "stage_attempt.source_commit",
                        "relation": "EQUAL",
                        "right": "referenced_production_closure.source_commit",
                    },
                    {
                        "left": "stage_attempt.source_tree",
                        "relation": "EQUAL",
                        "right": "referenced_production_closure.source_tree",
                    },
                    {
                        "left": "stage_blocked.production_closure_root",
                        "relation": "EQUAL",
                        "right": "identity(referenced_production_closure)",
                    },
                    {
                        "left": "stage_blocked.stage_id",
                        "relation": "EQUAL",
                        "right": "referenced_production_closure.stage_id",
                    },
                    {
                        "left": "stage_blocked.prerequisite_terminal_seal",
                        "relation": "EQUAL",
                        "right": "identity(referenced_prerequisite_terminal_seal)",
                    },
                    {
                        "left": "stage_blocked.failed_prerequisite_stage_id",
                        "relation": "EQUAL",
                        "right": "referenced_prerequisite_terminal_seal.stage_id",
                    },
                    {
                        "left": "stage_orphaned.reservation_id",
                        "relation": "EQUAL",
                        "right": "identity(referenced_stage_reservation)",
                    },
                    {
                        "left": "stage_orphaned.attempt_id_or_null",
                        "relation": "NULL_OR_EQUAL",
                        "right": "identity(referenced_stage_attempt)",
                    },
                    {
                        "left": "stage_orphaned.partial_evidence_root_or_null",
                        "relation": "NULL_OR_EQUAL",
                        "right": "identity(referenced_partial_evidence_artifact)",
                    },
                    {
                        "left": "stage_terminal_seal.reservation_id_or_null",
                        "relation": "NULL_OR_EQUAL",
                        "right": "identity(referenced_stage_reservation)",
                    },
                    {
                        "left": "stage_terminal_seal.attempt_id_or_null",
                        "relation": "NULL_OR_EQUAL",
                        "right": "identity(referenced_stage_attempt)",
                    },
                    {
                        "left": "stage_terminal_seal.blocked_id_or_null",
                        "relation": "NULL_OR_EQUAL",
                        "right": "identity(referenced_stage_blocked)",
                    },
                    {
                        "left": "stage_terminal_seal.orphaned_id_or_null",
                        "relation": "NULL_OR_EQUAL",
                        "right": "identity(referenced_stage_orphaned)",
                    },
                    {
                        "left": "stage_terminal_seal.completed_root_or_null",
                        "relation": "NULL_OR_EQUAL",
                        "right": "identity(referenced_completed_artifact)",
                    },
                    {
                        "left": "stage_terminal_seal.failure_root_or_null",
                        "relation": "NULL_OR_EQUAL",
                        "right": "identity(referenced_failure_artifact)",
                    },
                    {
                        "left": "stage_terminal_seal.partial_evidence_root_or_null",
                        "relation": "NULL_OR_EQUAL",
                        "right": (
                            "referenced_failure_or_orphaned_artifact."
                            "partial_evidence_root_or_null"
                        ),
                    },
                    {
                        "left": "stage_terminal_seal.stage_id",
                        "relation": "EQUAL",
                        "right": "referenced_lifecycle_artifact.stage_id",
                    },
                    {
                        "left": "stage_terminal_seal.stage_protocol_id",
                        "relation": "EQUAL",
                        "right": "referenced_lifecycle_artifact.stage_protocol_id",
                    },
                ],
                "same_stage_chain_fields": ["stage_id", "stage_protocol_id"],
                "terminal_reference_rule": (
                    "every-nonnull-reference-or-root-equals-the-frozen-identity-of-"
                    "the-referenced-immutable-artifact-and-all-referenced-artifacts-"
                    "belong-to-the-same-stage-chain"
                ),
                "blocked_parent_rule": (
                    "failed-prerequisite-is-in-current-stage-required_parent_terminal_"
                    "stage_ids-and-is-the-first-closed-gate-failure-in-that-order"
                ),
                "manifest_ref_rule": (
                    "every-downstream-manifest_evidence_ref-is-byte-identical;-its-"
                    "terminal-seal-is-the-authentic-OUTCOME_FREE_DEVELOPMENT_MANIFEST-"
                    "seal;-COMPLETED_MANIFEST-root-is-the-same-completed_root-used-as-"
                    "the-detached-manifest-stage-input"
                ),
                "protocol_binding_rule": (
                    "every-reservation-and-blocked-artifact-directly-binds-the-frozen-"
                    "protocol-root-protocol-id-evidence-protocol-id-and-stage-protocol-"
                    "id;-attempt-orphaned-and-terminal-artifacts-inherit-the-same-"
                    "values-through-their-authenticated-same-stage-references"
                ),
                "bootstrap_closure_rule": (
                    "every-reservation-or-blocked-carrier-production-closure-is-byte-"
                    "identical-to-the-same-stage-closure-in-the-authenticated-fixed-"
                    "bootstrap-catalog;-every-embedded-parent-terminal-is-byte-"
                    "identical-to-its-fixed-stage-path-and-recursively-obeys-this-rule"
                ),
                "validation_order": [
                    "canonical-shape-and-domain-identity",
                    "referenced-artifact-existence-and-identity",
                    "same-stage-and-closure-equalities",
                    "bootstrap-catalog-closure-and-fixed-parent-path-equalities",
                    "manifest-evidence-equality",
                    "parent-membership-and-gate",
                ],
            },
        },
        "production_source_binding": {
            "owner": "each-later-concrete-stage-edge",
            "checkpoint_closures_are_not_production_closures": True,
            "required_clean_commit_relations": [
                "frozen-evaluator-d34c383-is-strict-ancestor-of-manifest-source-commit",
                "manifest-source-commit-is-ancestor-or-equal-to-exact-source-commit",
                "exact-source-commit-is-ancestor-or-equal-to-random-source-commit",
                "random-source-commit-is-ancestor-or-equal-to-terminal-depth1-source-commit",
                "terminal-depth1-source-commit-is-ancestor-or-equal-to-telemetry-source-commit",
                "telemetry-source-commit-is-ancestor-or-equal-to-assessment-source-commit",
            ],
            "commit_relation_schema": {
                "checkpoint_edges": [
                    {
                        "ancestor_commit": ATLAS_SELECTOR_COMMIT_V1,
                        "descendant_commit": ATLAS_EVALUATOR_COMMIT_V1,
                        "relation": "STRICT_ANCESTOR",
                    },
                ],
                "stage_edges": [
                    {
                        "ancestor": {
                            "kind": "PINNED_COMMIT",
                            "value": ATLAS_EVALUATOR_COMMIT_V1,
                        },
                        "descendant": {
                            "kind": "STAGE_SOURCE_COMMIT",
                            "stage_id": "OUTCOME_FREE_DEVELOPMENT_MANIFEST",
                        },
                        "relation": "STRICT_ANCESTOR",
                    },
                    {
                        "ancestor": {
                            "kind": "STAGE_SOURCE_COMMIT",
                            "stage_id": "OUTCOME_FREE_DEVELOPMENT_MANIFEST",
                        },
                        "descendant": {
                            "kind": "STAGE_SOURCE_COMMIT",
                            "stage_id": "EXACT_ALL_288",
                        },
                        "relation": "ANCESTOR_OR_EQUAL",
                    },
                    {
                        "ancestor": {
                            "kind": "STAGE_SOURCE_COMMIT",
                            "stage_id": "EXACT_ALL_288",
                        },
                        "descendant": {
                            "kind": "STAGE_SOURCE_COMMIT",
                            "stage_id": "RANDOM_ALL_18432_GAMES",
                        },
                        "relation": "ANCESTOR_OR_EQUAL",
                    },
                    {
                        "ancestor": {
                            "kind": "STAGE_SOURCE_COMMIT",
                            "stage_id": "RANDOM_ALL_18432_GAMES",
                        },
                        "descendant": {
                            "kind": "STAGE_SOURCE_COMMIT",
                            "stage_id": "TERMINAL_DEPTH1_ALL_18432_GAMES",
                        },
                        "relation": "ANCESTOR_OR_EQUAL",
                    },
                    {
                        "ancestor": {
                            "kind": "STAGE_SOURCE_COMMIT",
                            "stage_id": "TERMINAL_DEPTH1_ALL_18432_GAMES",
                        },
                        "descendant": {
                            "kind": "STAGE_SOURCE_COMMIT",
                            "stage_id": "REPLAY_TELEMETRY_COMPLETE_TRACES_ONLY",
                        },
                        "relation": "ANCESTOR_OR_EQUAL",
                    },
                    {
                        "ancestor": {
                            "kind": "STAGE_SOURCE_COMMIT",
                            "stage_id": "REPLAY_TELEMETRY_COMPLETE_TRACES_ONLY",
                        },
                        "descendant": {
                            "kind": "STAGE_SOURCE_COMMIT",
                            "stage_id": "ASSESSMENT_AND_INSPECTION",
                        },
                        "relation": "ANCESTOR_OR_EQUAL",
                    },
                ],
                "tree_binding": "source_tree-equals-Git-tree-of-source_commit",
                "verification": "Git-object-database-not-working-tree-metadata",
            },
            "required_cross_stage_blob_relation": (
                "every-stage-carrier-and-recursive-parent-production-closure-equals-"
                "the-same-stage-bootstrap-frozen-closure"
            ),
            "closure_construction": (
                "explicit-entrypoints-plus-recursive-local-import-graph-including-package-initializer"
            ),
            "universal_required_paths": [
                "src/parity_forge/__init__.py",
                "src/parity_forge/atlas_protocol.py",
                "src/parity_forge/dsl.py",
                "src/parity_forge/engine.py",
            ],
            "stage_specific_required_and_forbidden_paths": "declared-on-each-stage",
            "future_stage_modules": (
                "all-six-concrete-manifest-exact-random-depth1-telemetry-assessment-"
                "entrypoints-and-recursive-imports-must-exist-and-be-blob-frozen-"
                "before-manifest-reservation"
            ),
            "required_evidence_fields": [
                "source_commit",
                "source_tree",
                "ordered_closure_paths",
                "ordered-commit-blob-identities",
                "ordered-current-byte-SHA256-and-lengths",
                "closure_root",
            ],
            "pre_and_post_stage_reseal": True,
            "manifest_freeze_scope": (
                "pre-reservation-candidate-neutral-bootstrap-plus-post-attempt-"
                "development-only-detached-manifest-freeze"
            ),
            "experiment_plan_freeze": {
                "live_source_path": "docs/plans/active/0013-six-family-development-atlas.md",
                "bootstrap_artifact_role": (
                    "immutable-pre-reservation-experiment-plan-byte-copy"
                ),
                "completed_manifest_copy_role": (
                    "immutable-post-attempt-byte-identical-copy"
                ),
                "manifest_fields": ["source_path", "byte_count", "sha256"],
                "copy_rule": (
                    "bootstrap-bytes-exactly-equal-preflight-read-live-source-bytes;-"
                    "completed-manifest-copy-exactly-equals-bootstrap-bytes"
                ),
                "downstream_input": "bootstrap-frozen-artifact-only",
                "manifest_crash_recovery": (
                    "when-reservation-exists-but-stage-local-copy-is-absent-read-exact-"
                    "bytes-only-from-the-authenticated-pre-reservation-bootstrap-"
                    "verify-the-reservation-closure-bound-SHA256-and-create-the-"
                    "immutable-copy-before-FAILED-or-ORPHANED-terminal-seal;-never-"
                    "read-live-worktree-or-Git-source-bytes-and-never-call-an-outcome-"
                    "capability"
                ),
                "live_document_after_manifest": (
                    "may-change-for-project-recordkeeping-and-is-never-runner-input"
                ),
            },
            "downstream_source_policy": (
                "every-production-closure-blob-and-experiment-plan-artifact-comes-"
                "from-the-pre-reservation-bootstrap;completed-manifest-copies-must-"
                "be-byte-identical;-live-documentation-may-evolve-but-cannot-be-"
                "runner-input-or-alter-the-execution-closure"
            ),
            "execution_closure_change_policy": (
                "new-reviewed-protocol-version-and-new-outcome-free-manifest-required"
            ),
        },
        "reservation_contract": {
            "scope": "one-atomic-reservation-per-stage-protocol-id",
            "maximum_reservations_per_stage_protocol_id": 1,
            "creation": "ATOMIC_EXCLUSIVE_BEFORE_ATTEMPT",
            "required_prior_evidence_scan": [
                "blocked",
                "reservation",
                "attempt",
                "failure",
                "completed",
                "orphaned",
                "terminal_seal",
                "contradiction_sidecar",
            ],
            "any_prior_matching_evidence": "BLOCK_NEW_RESERVATION",
            "prerequisite_gate_failure": (
                "ATOMIC-IMMUTABLE-BLOCKED-TERMINAL-SEAL-WITHOUT-RESERVATION-OR-ATTEMPT"
            ),
            "prerequisite_evaluation": {
                "membership_and_order_source": (
                    "stage.required_parent_terminal_stage_ids-exactly"
                ),
                "missing_parent_terminal_seal": (
                    "STAGE-NOT-YET-ELIGIBLE-NO-RESERVATION-ATTEMPT-OR-BLOCKED-ARTIFACT"
                ),
                "closed_gate_failure_selection": (
                    "first-parent-in-required_parent_terminal_stage_ids-whose-sealed-"
                    "evidence-fails-the-stage-prerequisite-gate"
                ),
                "terminal-seal-only_gate": (
                    "any-authentic-terminal-lifecycle-satisfies-presence-and-does-not-"
                    "require-upstream-success"
                ),
                "closed_predicates": {
                    "COMPLETED_VALID": (
                        "terminal-lifecycle-COMPLETED-and-referenced-completed-artifact-"
                        "passes-its-frozen-validator-including-full-fixed-journal-to-"
                        "ledger-reconstruction-and-stage-specific-completion-gate"
                    ),
                    "TERMINAL_SEAL_PRESENT": (
                        "any-authentic-BLOCKED-ORPHANED-FAILED-or-COMPLETED-terminal-seal"
                    ),
                },
            },
            "orphan_reservation": (
                "CONSUMED-NONRESUMABLE-AND-MUST-BE-RECOVERY-SEALED-AS-ORPHANED"
            ),
            "orphan_recovery": {
                "trigger": (
                    "unsealed-stage-evidence-exists-original-process-not-live-and-"
                    "exclusive-stage-lock-acquired"
                ),
                "bootstrap_authentication_gate": (
                    "any-manifest-stage-evidence-requires-the-complete-authenticated-"
                    "bootstrap-before-recovery;-every-nonmanifest-carrier-requires-"
                    "the-same-bootstrap-and-fixed-recursive-parent-chain"
                ),
                "deterministic_precedence": [
                    {
                        "condition": (
                            "any-invalid-artifact-or-more-than-one-exclusive-lifecycle-"
                            "body-or-a-terminal-seal-inconsistent-with-its-references"
                        ),
                        "action": (
                            "FAIL-CLOSED-WITH-IMMUTABLE-EXTERNAL-CONTRADICTION-"
                            "SIDECAR-AND-NO-NEW-STAGE-CAPABILITY"
                        ),
                    },
                    {
                        "condition": (
                            "one-valid-terminal-seal-and-only-artifacts-compatible-"
                            "with-its-declared-exclusive-lifecycle-exist"
                        ),
                        "action": "VERIFY-AND-NO-OP",
                    },
                    {
                        "condition": (
                            "one-valid-blocked-artifact-and-no-reservation-attempt-"
                            "completed-failure-or-terminal-artifact"
                        ),
                        "action": "WRITE-MATCHING-BLOCKED-TERMINAL-SEAL",
                    },
                    {
                        "condition": (
                            "one-valid-completed-artifact-with-its-reservation-and-"
                            "attempt-and-no-blocked-failure-or-terminal-artifact"
                        ),
                        "action": "WRITE-MATCHING-COMPLETED-TERMINAL-SEAL",
                    },
                    {
                        "condition": (
                            "one-valid-failure-artifact-with-its-reservation-and-"
                            "attempt-and-no-blocked-completed-or-terminal-artifact"
                        ),
                        "action": "WRITE-MATCHING-FAILED-TERMINAL-SEAL",
                    },
                    {
                        "condition": (
                            "one-valid-orphaned-artifact-with-its-reservation-and-"
                            "optional-attempt-and-no-blocked-completed-failure-or-"
                            "terminal-artifact"
                        ),
                        "action": "WRITE-MATCHING-ORPHANED-TERMINAL-SEAL",
                    },
                    {
                        "condition": (
                            "reservation-exists-with-optional-attempt-and-no-valid-"
                            "blocked-completed-failure-orphaned-or-terminal-artifact"
                        ),
                        "action": (
                            "WRITE-ONE-IMMUTABLE-STAGE_ORPHANED_ID-AND-ORPHANED-"
                            "TERMINAL-SEAL"
                        ),
                    },
                ],
                "conflicting_or_invalid_terminal_artifacts": (
                    "FAIL-CLOSED-WITH-IMMUTABLE-EXTERNAL-CONTRADICTION-SIDECAR-AND-"
                    "NO-NEW-STAGE-CAPABILITY"
                ),
                "status_ledger_reconciliation": {
                    "common": "retain-every-valid-immutable-record-without-imputation",
                    "caller_ledger_specs": (
                        "non-authoritative-and-must-exactly-equal-the-specs-derived-"
                        "from-the-authenticated-bootstrap-protocol"
                    ),
                    "EXACT_ALL_288": (
                        "mark-interrupted-exact-or-PV-slot-INCOMPLETE-and-every-"
                        "unobserved-fixed-slot-NOT_RUN"
                    ),
                    "RANDOM_ALL_18432_GAMES": (
                        "mark-interrupted-game-INCOMPLETE-and-every-unobserved-fixed-"
                        "game-NOT_RUN"
                    ),
                    "TERMINAL_DEPTH1_ALL_18432_GAMES": (
                        "mark-interrupted-game-INCOMPLETE-and-every-unobserved-fixed-"
                        "game-NOT_RUN"
                    ),
                    "REPLAY_TELEMETRY_COMPLETE_TRACES_ONLY": (
                        "mark-every-interrupted-or-unreached-valid-complete-sampled-"
                        "trace-MISSING-and-every-nonadmissible-sampled-trace-"
                        "NOT_ADMISSIBLE"
                    ),
                    "OUTCOME_FREE_DEVELOPMENT_MANIFEST": "no-slot-ledger",
                    "ASSESSMENT_AND_INSPECTION": (
                        "retain-partial-report-only-and-make-no-formal-label-or-"
                        "inspection-imputation"
                    ),
                },
                "outcome_capable_calls": 0,
                "recovery_stage_capability_calls": 0,
                "resume_or_retry": "FORBIDDEN",
                "downstream_use": "authentic-terminal-seal-that-fails-success-gates",
            },
            "run_directory_collision": "FAIL_WITH_IMMUTABLE_EXTERNAL_SIDECAR",
        },
        "retry_and_resume_contract": {
            "pre_reservation_failure": "RETRY_ALLOWED_AFTER_SAFE_CORRECTION",
            "partial_bootstrap_retry": (
                "ONLY-IDEMPOTENT-COMPLETION-OF-AN-IDENTICAL-CANDIDATE-NEUTRAL-PREFIX"
            ),
            "post_reservation_same_protocol_retry": "FORBIDDEN",
            "post_reservation_resume": "FORBIDDEN_V1",
            "post_reservation_slot_or_phase_replacement": "FORBIDDEN",
            "new_protocol_version_retry": (
                "DEVELOPMENT_ONLY_AFTER_BINDING_ALL_PRIOR_RESERVATION-ATTEMPT-FAILURE-"
                "PARTIAL-EVIDENCE-ROOTS"
            ),
            "confirmation_candidate_reallocation": "FORBIDDEN",
        },
        "artifact_contract": {
            "exclusive_lifecycles": [
                ["blocked", "terminal-seal-BLOCKED"],
                ["reservation", "attempt", "failure", "terminal-seal-FAILED"],
                ["reservation", "attempt", "completed", "terminal-seal-COMPLETED"],
                [
                    "reservation",
                    "attempt-or-null",
                    "orphaned",
                    "terminal-seal-ORPHANED",
                ],
            ],
            "write_mode": "CREATE_NEW_NEVER_OVERWRITE",
            "attempt_written_before_stage_capability": True,
            "failure_written_for_any_caught_post-reservation-exception": True,
            "blocked_written_for_any_failed_prerequisite_gate": True,
            "blocked_stage_slot_status_projection": {
                "EXACT_ALL_288": (
                    "all-288-exact-slots-and-all-2304-PV-replay-slots-BLOCKED"
                ),
                "RANDOM_ALL_18432_GAMES": "all-18432-random-game-slots-BLOCKED",
                "TERMINAL_DEPTH1_ALL_18432_GAMES": (
                    "all-18432-terminal-depth1-game-slots-BLOCKED"
                ),
                "REPLAY_TELEMETRY_COMPLETE_TRACES_ONLY": (
                    "all-36864-telemetry-slots-BLOCKED"
                ),
                "projection_owner": (
                    "formal-validator-reconstructs-from-authentic-BLOCKED-terminal-"
                    "seal-and-frozen-protocol-schedule-no-raw-outcome-imputation"
                ),
            },
            "partial_evidence_retention": "REQUIRED",
            "completed_ledger_revalidation": {
                "journal_relation": (
                    "reconcile-every-fixed-slot-from-immutable-start-and-result-"
                    "journals-and-require-byte-identity-with-the-completed-status-ledger"
                ),
                "stage_status_gates": {
                    "EXACT_ALL_288": (
                        "exact:288-COMPLETE-and-exact-pv:2304-VALID"
                    ),
                    "RANDOM_ALL_18432_GAMES": "random:18432-COMPLETE",
                    "TERMINAL_DEPTH1_ALL_18432_GAMES": (
                        "depth1:18432-COMPLETE"
                    ),
                    "REPLAY_TELEMETRY_COMPLETE_TRACES_ONLY": (
                        "telemetry:36864-accounted-as-journal-result-VALIDATED-or-"
                        "parent-ledger-derived-NOT_ADMISSIBLE;-MISSING-INVALID-"
                        "PROOF_CONTRADICTION-and-BLOCKED-forbidden"
                    ),
                },
                "recovery_and_downstream_gate_use_same_validator": True,
            },
            "completed_assessment_summary_revalidation": {
                "trigger": "assessment-completed-body-already-present",
                "normal_path": (
                    "rebuild-canonical-report-from-authenticated-manifest-and-all-"
                    "fixed-parent-raw-evidence"
                ),
                "manifest_unavailable_path": (
                    "rebuild-zero-outcome-meta-report-from-bootstrap-protocol-and-"
                    "fixed-parent-terminal-chain-without-reading-raw-outcomes"
                ),
                "required_relation": (
                    "stored-completed-summary-byte-identical-to-rebuilt-report-before-"
                    "COMPLETED-terminal-verification-or-publication"
                ),
                "mismatch_policy": "IMMUTABLE-EXTERNAL-CONTRADICTION-FAIL-CLOSED",
            },
            "successful_completion_reseals": [
                "reservation",
                "attempt",
                "all-upstream-evidence",
                "bootstrap-frozen-experiment-plan-and-executable-closure",
                "raw-stage-evidence",
            ],
        },
        "stages": [
            {
                "stage_index": 0,
                "stage_id": "OUTCOME_FREE_DEVELOPMENT_MANIFEST",
                "stage_protocol_id": "plan0013-atlas-development-manifest-v1",
                "prerequisite_stage_id": None,
                "prerequisite_gate": None,
                "required_parent_terminal_stage_ids": [],
                "required_parent_terminal_predicates": {},
                "source_closure_policy": _stage_source_closure_policy(
                    "OUTCOME_FREE_DEVELOPMENT_MANIFEST"
                ),
                "reservation_scope": (
                    "DETACHED_DEVELOPMENT_MANIFEST_EXPORT_AND_FOUR_ARTIFACT_FREEZE"
                ),
                "reservation_timing": (
                    "AFTER_COMPLETE_CANDIDATE_NEUTRAL_BOOTSTRAP_AND_BEFORE_FIRST-"
                    "DEFINITION-BODY-EXPORT"
                ),
                "attempt_timing": "AFTER_RESERVATION_BEFORE_DEFINITION_BODY_EXPORT",
                "capability_boundary": "DEVELOPMENT_DEFINITIONS_ONLY_NO_OUTCOMES",
                "completion_gate": (
                    "DETACHED_MANIFEST_FOUR_ARTIFACT_FREEZE_AND_BYTE_LOCK_PUBLICLY_RECONSTRUCT"
                ),
                "post_reservation_failure_scope": "ENTIRE_STAGE_PERMANENTLY_CONSUMED",
                "resume_policy": "NO_RESUME_V1",
            },
            {
                "stage_index": 1,
                "stage_id": "EXACT_ALL_288",
                "stage_protocol_id": "plan0013-atlas-development-exact-v1",
                "prerequisite_stage_id": "OUTCOME_FREE_DEVELOPMENT_MANIFEST",
                "prerequisite_gate": "COMPLETE_VALID",
                "required_parent_terminal_stage_ids": [
                    "OUTCOME_FREE_DEVELOPMENT_MANIFEST"
                ],
                "required_parent_terminal_predicates": {
                    "OUTCOME_FREE_DEVELOPMENT_MANIFEST": "COMPLETED_VALID"
                },
                "source_closure_policy": _stage_source_closure_policy(
                    "EXACT_ALL_288"
                ),
                "reservation_scope": "ALL_288_EXACT_SLOTS_AND_2304_PV_REPLAYS",
                "reservation_timing": "BEFORE_FIRST_SOLVER_OR_PV_REPLAY_CALL",
                "attempt_timing": "AFTER_RESERVATION_BEFORE_FIRST_SOLVER_CALL",
                "capability_boundary": "FIXED_DEVELOPMENT_EXACT_SCHEDULE_ONLY",
                "completion_gate": "ALL_288_EXACT_AND_2304_PV_SLOTS_COMPLETE_VALID",
                "post_reservation_failure_scope": "ENTIRE_STAGE_PERMANENTLY_CONSUMED",
                "resume_policy": "NO_RESUME_V1",
            },
            {
                "stage_index": 2,
                "stage_id": "RANDOM_ALL_18432_GAMES",
                "stage_protocol_id": "plan0013-atlas-development-random-v1",
                "prerequisite_stage_id": "EXACT_ALL_288",
                "prerequisite_gate": "COMPLETE_VALID_OTHERWISE-WRITE-BLOCKED-LEDGER",
                "required_parent_terminal_stage_ids": [
                    "OUTCOME_FREE_DEVELOPMENT_MANIFEST",
                    "EXACT_ALL_288",
                ],
                "required_parent_terminal_predicates": {
                    "OUTCOME_FREE_DEVELOPMENT_MANIFEST": "COMPLETED_VALID",
                    "EXACT_ALL_288": "COMPLETED_VALID",
                },
                "source_closure_policy": _stage_source_closure_policy(
                    "RANDOM_ALL_18432_GAMES"
                ),
                "reservation_scope": "ALL_18432_RANDOM_GAME_SLOTS",
                "reservation_timing": "BEFORE_FIRST_AGENT_OR_GAME_CALL",
                "attempt_timing": "AFTER_RESERVATION_BEFORE_FIRST_RANDOM_GAME",
                "capability_boundary": "FIXED_RANDOM_DEVELOPMENT_GAME_SCHEDULE_ONLY",
                "scheduled_game_count": 18_432,
                "completion_gate": "ALL_18432_RANDOM_GAME_SLOTS_COMPLETE_VALID_AND_SEALED",
                "post_reservation_failure_scope": "ENTIRE_STAGE_PERMANENTLY_CONSUMED",
                "resume_policy": "NO_RESUME_V1",
            },
            {
                "stage_index": 3,
                "stage_id": "TERMINAL_DEPTH1_ALL_18432_GAMES",
                "stage_protocol_id": "plan0013-atlas-development-terminal-depth1-v1",
                "prerequisite_stage_id": "RANDOM_ALL_18432_GAMES",
                "prerequisite_gate": "COMPLETE_VALID_OTHERWISE-WRITE-BLOCKED-LEDGER",
                "required_parent_terminal_stage_ids": [
                    "OUTCOME_FREE_DEVELOPMENT_MANIFEST",
                    "EXACT_ALL_288",
                    "RANDOM_ALL_18432_GAMES",
                ],
                "required_parent_terminal_predicates": {
                    "OUTCOME_FREE_DEVELOPMENT_MANIFEST": "COMPLETED_VALID",
                    "EXACT_ALL_288": "COMPLETED_VALID",
                    "RANDOM_ALL_18432_GAMES": "COMPLETED_VALID",
                },
                "source_closure_policy": _stage_source_closure_policy(
                    "TERMINAL_DEPTH1_ALL_18432_GAMES"
                ),
                "reservation_scope": "ALL_18432_TERMINAL_DEPTH1_GAME_SLOTS",
                "reservation_timing": "BEFORE_FIRST_AGENT-RESET-SEARCH-OR-GAME-CALL",
                "attempt_timing": "AFTER_RESERVATION_BEFORE_FIRST-ROLE-SLOT-RESET",
                "capability_boundary": (
                    "FIXED_TERMINAL_DEPTH1_DEVELOPMENT_GAME_SCHEDULE_ONLY"
                ),
                "scheduled_game_count": 18_432,
                "completion_gate": (
                    "ALL_18432_TERMINAL_DEPTH1_GAME_SLOTS_COMPLETE_VALID_AND_SEALED"
                ),
                "post_reservation_failure_scope": "ENTIRE_STAGE_PERMANENTLY_CONSUMED",
                "resume_policy": "NO_RESUME_V1",
            },
            {
                "stage_index": 4,
                "stage_id": "REPLAY_TELEMETRY_COMPLETE_TRACES_ONLY",
                "stage_protocol_id": "plan0013-atlas-development-telemetry-v1",
                "prerequisite_stage_id": "TERMINAL_DEPTH1_ALL_18432_GAMES",
                "prerequisite_gate": (
                    "TERMINAL-SEALS-FOR-BOTH-SAMPLED-STAGES-REPLAY-COMPLETE-TRACES-ONLY"
                ),
                "required_parent_terminal_stage_ids": [
                    "OUTCOME_FREE_DEVELOPMENT_MANIFEST",
                    "EXACT_ALL_288",
                    "RANDOM_ALL_18432_GAMES",
                    "TERMINAL_DEPTH1_ALL_18432_GAMES",
                ],
                "required_parent_terminal_predicates": {
                    "OUTCOME_FREE_DEVELOPMENT_MANIFEST": "COMPLETED_VALID",
                    "EXACT_ALL_288": "TERMINAL_SEAL_PRESENT",
                    "RANDOM_ALL_18432_GAMES": "TERMINAL_SEAL_PRESENT",
                    "TERMINAL_DEPTH1_ALL_18432_GAMES": "TERMINAL_SEAL_PRESENT",
                },
                "source_closure_policy": _stage_source_closure_policy(
                    "REPLAY_TELEMETRY_COMPLETE_TRACES_ONLY"
                ),
                "reservation_scope": "ALL_COMPLETE_RETAINED_SAMPLED_TRACES",
                "reservation_timing": "BEFORE_FIRST_TELEMETRY_REPLAY_OR_DERIVATION",
                "attempt_timing": "AFTER_RESERVATION_BEFORE_FIRST_TRACE_REPLAY",
                "capability_boundary": "COMPLETE_DEVELOPMENT_TRACES_ONLY",
                "completion_gate": "ALL_ADMISSIBLE_COMPLETE_TRACES_ACCOUNTED",
                "post_reservation_failure_scope": "ENTIRE_STAGE_PERMANENTLY_CONSUMED",
                "resume_policy": "NO_RESUME_V1",
            },
            {
                "stage_index": 5,
                "stage_id": "ASSESSMENT_AND_INSPECTION",
                "stage_protocol_id": "plan0013-atlas-development-assessment-v1",
                "prerequisite_stage_id": "REPLAY_TELEMETRY_COMPLETE_TRACES_ONLY",
                "prerequisite_gate": (
                    "TERMINAL-SEALS-FOR-ALL-PRIOR-STAGES-INCLUDING-FAILED-INVALID-OR-BLOCKED"
                ),
                "required_parent_terminal_stage_ids": [
                    "OUTCOME_FREE_DEVELOPMENT_MANIFEST",
                    "EXACT_ALL_288",
                    "RANDOM_ALL_18432_GAMES",
                    "TERMINAL_DEPTH1_ALL_18432_GAMES",
                    "REPLAY_TELEMETRY_COMPLETE_TRACES_ONLY",
                ],
                "required_parent_terminal_predicates": {
                    "OUTCOME_FREE_DEVELOPMENT_MANIFEST": "TERMINAL_SEAL_PRESENT",
                    "EXACT_ALL_288": "TERMINAL_SEAL_PRESENT",
                    "RANDOM_ALL_18432_GAMES": "TERMINAL_SEAL_PRESENT",
                    "TERMINAL_DEPTH1_ALL_18432_GAMES": "TERMINAL_SEAL_PRESENT",
                    "REPLAY_TELEMETRY_COMPLETE_TRACES_ONLY": "TERMINAL_SEAL_PRESENT",
                },
                "source_closure_policy": _stage_source_closure_policy(
                    "ASSESSMENT_AND_INSPECTION"
                ),
                "reservation_scope": "COMPLETE_FIXED_ASSESSMENT_AND_INSPECTION",
                "reservation_timing": "BEFORE_FIRST_AGGREGATION_OR_CASE_SELECTION",
                "attempt_timing": "AFTER_RESERVATION_BEFORE_FIRST_AGGREGATION",
                "capability_boundary": "SEALED_DEVELOPMENT_EVIDENCE_ONLY",
                "completion_gate": "FORMAL_LABELS_AND_INSPECTION_UNION_RECONSTRUCT",
                "post_reservation_failure_scope": "ENTIRE_STAGE_PERMANENTLY_CONSUMED",
                "resume_policy": "NO_RESUME_V1",
            },
        ],
    }
    section["execution_evidence_root"] = _digest(
        _EXECUTION_EVIDENCE_ROOT_DOMAIN_V1, section
    )
    return section


def _build_protocol_value(selection: Mapping[str, Any]) -> Dict[str, Any]:
    context = _checked_schedule_context(
        _canonical_bytes(selection).decode("utf-8")
    )
    upstream = _upstream_binding()
    schedule = _schedule_section(context)
    telemetry = _telemetry_protocol(context["roots"]["game"]["root"])
    censor = _censor_policy()
    assessment = _assessment_protocol()
    inspection = _inspection_protocol()
    unsigned = {
        "protocol_version": ATLAS_PROTOCOL_VERSION_V1,
        "protocol_id": ATLAS_PROTOCOL_ID_V1,
        "status": "OUTCOME_FREE_EVALUATION_PROTOCOL",
        "upstream": upstream,
        "capability_boundary": {
            "development_definition_metadata_emitted_count": (
                ATLAS_DEVELOPMENT_DEFINITION_COUNT_V1
            ),
            "development_definition_body_emitted_count": 0,
            "candidate_pair_emitted_count": 0,
            "candidate_definition_emitted_count": 0,
            "candidate_definition_scheduled_count": 0,
            "candidate_definition_evaluated_count": 0,
            "candidate_outcome_count": 0,
            "development_outcome_count": 0,
            "outcome_producing_call_count": 0,
            "selection_validation_reads_candidate_bytes": True,
            "selection_validation_candidate_read_scope": (
                "canonical-SHA-partition-and-disjointness-preflight-only"
            ),
            "outcome_capable_stage_receives_full_selection": False,
            "outcome_stage_schedule_reconstruction": (
                "iter_frozen_atlas_*_from_protocol_v1-only-no-selection-value"
            ),
            "candidate_commitment": (
                "selection-canonical-SHA-and-selection-partition-root-only"
            ),
        },
        "stage_sequence": [
            "OUTCOME_FREE_DEVELOPMENT_MANIFEST",
            "EXACT_ALL_288",
            "RANDOM_ALL_18432_GAMES",
            "TERMINAL_DEPTH1_ALL_18432_GAMES",
            "REPLAY_TELEMETRY_COMPLETE_TRACES_ONLY",
            "ASSESSMENT_AND_INSPECTION",
        ],
        "schedule": schedule,
        "exact_protocol": _exact_protocol(),
        "sampled_protocol": _sampled_protocol(),
        "telemetry_protocol": telemetry,
        "censor_and_failure_policy": censor,
        "assessment_protocol": assessment,
        "inspection_protocol": inspection,
        "manifest_and_run_provenance": _execution_evidence_protocol(),
    }
    unsigned["protocol_root"] = _digest(_PROTOCOL_ROOT_DOMAIN_V1, unsigned)
    return unsigned


def _require_frozen_roots(value: Mapping[str, Any]) -> None:
    observed = {
        "exact": value["schedule"]["derived_coordinate_roots"]["exact"]["root"],
        "orientation": value["schedule"]["derived_coordinate_roots"]["orientation"]["root"],
        "profile": value["schedule"]["derived_coordinate_roots"]["profile"]["root"],
        "role": value["schedule"]["derived_coordinate_roots"]["role"]["root"],
        "game": value["schedule"]["derived_coordinate_roots"]["game"]["root"],
        "matched": value["schedule"]["derived_coordinate_roots"]["matched_start_block"]["root"],
        "telemetry": value["telemetry_protocol"]["telemetry_schedule_root"],
        "protocol": value["protocol_root"],
    }
    expected = {
        "exact": ATLAS_EXACT_SCHEDULE_ROOT_V1,
        "orientation": ATLAS_ORIENTATION_SCHEDULE_ROOT_V1,
        "profile": ATLAS_PROFILE_SCHEDULE_ROOT_V1,
        "role": ATLAS_ROLE_SLOT_SCHEDULE_ROOT_V1,
        "game": ATLAS_GAME_SCHEDULE_ROOT_V1,
        "matched": ATLAS_MATCHED_START_BLOCK_ROOT_V1,
        "telemetry": ATLAS_TELEMETRY_SCHEDULE_ROOT_V1,
        "protocol": ATLAS_PROTOCOL_ROOT_V1,
    }
    if any(not expected[key] or observed[key] != expected[key] for key in expected):
        raise ValueError("frozen atlas protocol root drifted")


def _require_frozen_context_roots(context: Mapping[str, Any]) -> None:
    contracts = (
        (
            "exact",
            "exact",
            "exact",
            ATLAS_DEVELOPMENT_DEFINITION_COUNT_V1,
            ATLAS_EXACT_SCHEDULE_ROOT_V1,
        ),
        (
            "orientations",
            "orientation",
            "orientation",
            ATLAS_DEFINITION_ORIENTATION_COUNT_V1,
            ATLAS_ORIENTATION_SCHEDULE_ROOT_V1,
        ),
        (
            "profiles",
            "profile",
            "profile",
            ATLAS_SAMPLED_PROFILE_COUNT_V1,
            ATLAS_PROFILE_SCHEDULE_ROOT_V1,
        ),
        (
            "roles",
            "role",
            "role",
            ATLAS_SAMPLED_ROLE_SLOT_COUNT_V1,
            ATLAS_ROLE_SLOT_SCHEDULE_ROOT_V1,
        ),
        (
            "games",
            "game",
            "game",
            ATLAS_SAMPLED_GAME_COUNT_V1,
            ATLAS_GAME_SCHEDULE_ROOT_V1,
        ),
        (
            "blocks",
            "matched_start_block",
            "matched-start",
            ATLAS_MATCHED_START_BLOCK_COUNT_V1,
            ATLAS_MATCHED_START_BLOCK_ROOT_V1,
        ),
    )
    try:
        if type(context) is not dict or set(context) != {
            "exact",
            "orientations",
            "profiles",
            "roles",
            "blocks",
            "games",
            "roots",
        }:
            raise ValueError("cached atlas schedule context shape drifted")
        roots = context["roots"]
        if type(roots) is not dict or set(roots) != {
            contract[1] for contract in contracts
        }:
            raise ValueError("cached atlas schedule root map shape drifted")
        for body_key, root_key, root_label, fixed_count, fixed_root in contracts:
            records = context[body_key]
            if type(records) is not list:
                raise TypeError("cached atlas schedule column must be an exact list")
            recomputed = _ordered_record_root(root_label, records)
            stored = roots[root_key]
            if _canonical_bytes(recomputed) != _canonical_bytes(stored):
                raise ValueError(
                    "cached atlas {} schedule root metadata drifted".format(root_key)
                )
            if (
                recomputed["count"] != fixed_count
                or recomputed["root"] != fixed_root
            ):
                raise ValueError(
                    "frozen atlas {} schedule coordinate root drifted".format(root_key)
                )
    except (
        AssertionError,
        AttributeError,
        KeyError,
        RecursionError,
        RuntimeError,
        TypeError,
        UnicodeError,
        ValueError,
    ) as error:
        raise ValueError("cached frozen atlas schedule failed resealing") from error


def _checked_schedule_context(selection_json: str) -> Dict[str, Any]:
    context = _cached_schedule_context(selection_json)
    try:
        _require_frozen_context_roots(context)
        detached = _json_copy(context, "detached frozen atlas schedule context")
        _require_frozen_context_roots(detached)
    except (TypeError, ValueError):
        # A cached context is process-local mutable state.  Once it fails a
        # reseal it must never be reused, even when the caller catches the
        # fail-closed error.  A later call may reconstruct it from sealed input.
        _cached_schedule_context.cache_clear()
        raise
    return detached


def build_frozen_atlas_protocol_v1(selection_value: Any) -> Dict[str, Any]:
    selection, entry = _seal_selection(selection_value)
    protocol = _build_protocol_value(selection)
    _require_frozen_roots(protocol)
    protocol_bytes = _seal_protocol(protocol)
    if hashlib.sha256(protocol_bytes).hexdigest() != ATLAS_PROTOCOL_CANONICAL_SHA256_V1:
        raise ValueError("frozen atlas protocol canonical SHA-256 drifted")
    _selection_after, entry_after = _seal_selection(selection_value)
    if entry_after != entry:
        raise ValueError("atlas selection changed during protocol construction")
    return _json_copy(protocol, "frozen atlas protocol")


def validate_frozen_atlas_protocol_v1(
    value: Any, selection_value: Any
) -> Dict[str, Any]:
    entry = _seal_protocol(value)
    expected = build_frozen_atlas_protocol_v1(selection_value)
    if entry != _canonical_bytes(expected):
        raise ValueError("frozen atlas protocol does not reconstruct")
    if _seal_protocol(value) != entry:
        raise ValueError("frozen atlas protocol changed during validation")
    return _json_copy(expected, "validated frozen atlas protocol")


def canonical_frozen_atlas_protocol_json_v1(
    selection_value: Any, value: Any = None
) -> str:
    protocol = (
        build_frozen_atlas_protocol_v1(selection_value)
        if value is None
        else validate_frozen_atlas_protocol_v1(value, selection_value)
    )
    return _canonical_bytes(protocol).decode("utf-8")


def _context_from_frozen_selection(selection_value: Any) -> Dict[str, Any]:
    selection, entry = _seal_selection(selection_value)
    context = _checked_schedule_context(entry.decode("utf-8"))
    _selection_after, entry_after = _seal_selection(selection_value)
    if entry_after != entry:
        raise ValueError("atlas selection changed during schedule reconstruction")
    return context


def _context_from_frozen_protocol(protocol_value: Any) -> Dict[str, Any]:
    entry = _seal_protocol(protocol_value)
    if hashlib.sha256(entry).hexdigest() != ATLAS_PROTOCOL_CANONICAL_SHA256_V1:
        raise ValueError("atlas protocol differs from the frozen canonical SHA-256")
    protocol = json.loads(entry.decode("utf-8"))
    _require_frozen_roots(protocol)
    schedule = protocol.get("schedule")
    if type(schedule) is not dict:
        raise TypeError("frozen atlas protocol schedule must be an exact object")
    exact = _json_copy(schedule.get("exact_slots"), "protocol exact schedule")
    orientations = _json_copy(
        schedule.get("orientation_slots"), "protocol orientation schedule"
    )
    profiles = _build_profile_slots(orientations)
    roles = _build_role_slots(profiles)
    blocks = _build_match_blocks(orientations)
    games = _build_game_slots(profiles, roles, blocks)
    context = {
        "exact": exact,
        "orientations": orientations,
        "profiles": profiles,
        "roles": roles,
        "blocks": blocks,
        "games": games,
        "roots": {
            "exact": _ordered_record_root("exact", exact),
            "orientation": _ordered_record_root("orientation", orientations),
            "profile": _ordered_record_root("profile", profiles),
            "role": _ordered_record_root("role", roles),
            "game": _ordered_record_root("game", games),
            "matched_start_block": _ordered_record_root(
                "matched-start", blocks
            ),
        },
    }
    _require_frozen_context_roots(context)
    if _canonical_bytes(context["roots"]) != _canonical_bytes(
        schedule.get("derived_coordinate_roots")
    ):
        raise ValueError("protocol-only schedule roots do not reconstruct")
    if _seal_protocol(protocol_value) != entry:
        raise ValueError("atlas protocol changed during schedule reconstruction")
    return context


def iter_frozen_atlas_exact_schedule_v1(
    selection_value: Any,
) -> Iterator[Dict[str, Any]]:
    context = _context_from_frozen_selection(selection_value)
    return iter(_json_copy(context["exact"], "exact schedule iterator"))


def iter_frozen_atlas_orientation_schedule_v1(
    selection_value: Any,
) -> Iterator[Dict[str, Any]]:
    context = _context_from_frozen_selection(selection_value)
    return iter(_json_copy(context["orientations"], "orientation schedule iterator"))


def iter_frozen_atlas_profile_schedule_v1(
    selection_value: Any,
) -> Iterator[Dict[str, Any]]:
    context = _context_from_frozen_selection(selection_value)
    return iter(_json_copy(context["profiles"], "profile schedule iterator"))


def iter_frozen_atlas_role_schedule_v1(
    selection_value: Any,
) -> Iterator[Dict[str, Any]]:
    context = _context_from_frozen_selection(selection_value)
    return iter(_json_copy(context["roles"], "role schedule iterator"))


def iter_frozen_atlas_game_schedule_v1(
    selection_value: Any,
) -> Iterator[Dict[str, Any]]:
    context = _context_from_frozen_selection(selection_value)
    return iter(_json_copy(context["games"], "game schedule iterator"))


def iter_frozen_atlas_matched_start_blocks_v1(
    selection_value: Any,
) -> Iterator[Dict[str, Any]]:
    context = _context_from_frozen_selection(selection_value)
    return iter(_json_copy(context["blocks"], "matched-start iterator"))


def iter_frozen_atlas_exact_schedule_from_protocol_v1(
    protocol_value: Any,
) -> Iterator[Dict[str, Any]]:
    context = _context_from_frozen_protocol(protocol_value)
    return iter(_json_copy(context["exact"], "protocol-only exact iterator"))


def iter_frozen_atlas_orientation_schedule_from_protocol_v1(
    protocol_value: Any,
) -> Iterator[Dict[str, Any]]:
    context = _context_from_frozen_protocol(protocol_value)
    return iter(
        _json_copy(context["orientations"], "protocol-only orientation iterator")
    )


def iter_frozen_atlas_profile_schedule_from_protocol_v1(
    protocol_value: Any,
) -> Iterator[Dict[str, Any]]:
    context = _context_from_frozen_protocol(protocol_value)
    return iter(_json_copy(context["profiles"], "protocol-only profile iterator"))


def iter_frozen_atlas_role_schedule_from_protocol_v1(
    protocol_value: Any,
) -> Iterator[Dict[str, Any]]:
    context = _context_from_frozen_protocol(protocol_value)
    return iter(_json_copy(context["roles"], "protocol-only role iterator"))


def iter_frozen_atlas_game_schedule_from_protocol_v1(
    protocol_value: Any,
) -> Iterator[Dict[str, Any]]:
    context = _context_from_frozen_protocol(protocol_value)
    return iter(_json_copy(context["games"], "protocol-only game iterator"))


def iter_frozen_atlas_matched_start_blocks_from_protocol_v1(
    protocol_value: Any,
) -> Iterator[Dict[str, Any]]:
    context = _context_from_frozen_protocol(protocol_value)
    return iter(_json_copy(context["blocks"], "protocol-only matched-start iterator"))


_EXACT_PAIR_LABELS_V1 = frozenset(
    (
        "A_ROLE_DOMINANT",
        "B_ROLE_DOMINANT",
        "FIRST_PLAYER_DOMINANT",
        "SECOND_PLAYER_DOMINANT",
        "HORIZON_UNRESOLVED",
        "EVIDENCE_INCOMPLETE",
        "EVIDENCE_INVALID",
    )
)
_SAMPLED_STRENGTH_LABELS_V1 = frozenset(
    (
        "WEAK_BALANCE_SIGNAL_V1",
        "EXCESSIVE_HORIZON_SIGNAL",
        "ROLE_IMBALANCE_SIGNAL",
        "EVIDENCE_INCOMPLETE",
        "EVIDENCE_INVALID",
    )
)
_PAIR_ASSESSMENTS_V1 = frozenset(
    (
        "PAIR_FRONTIER_SIGNAL_V1",
        "NO_PAIR_FRONTIER_EXACT",
        "NO_PAIR_FRONTIER_WEAK_PLAY",
        "HORIZON_UNRESOLVED",
        "EVIDENCE_INCOMPLETE",
        "EVIDENCE_INVALID",
    )
)
_INSPECTION_MISSING_REASONS_V1 = frozenset(
    (
        "INCOMPLETE_EXACT",
        "INCOMPLETE_RANDOM",
        "INCOMPLETE_DEPTH1",
        "INCOMPLETE_TELEMETRY",
        "INVALID_EVIDENCE",
        "ZERO_DECISIVE_RANDOM",
        "ZERO_DECISIVE_DEPTH1",
        "ZERO_DECISIVE_ORIENTATION",
        "ZERO_DECISIONS",
    )
)
_INSPECTION_CHANNEL_STATUSES_V1 = frozenset(
    (
        "COMPLETE",
        "INCOMPLETE",
        "INVALID",
        "PROOF_CONTRADICTION",
        "NOT_RUN",
        "BLOCKED",
    )
)


def _defined_fraction_v1(numerator: Any, denominator: Any, label: str) -> Dict[str, Any]:
    numerator = _exact_int(numerator, "{} numerator".format(label))
    denominator = _exact_int(denominator, "{} denominator".format(label), 1)
    if numerator > denominator:
        raise ValueError("{} must be a fraction in [0,1]".format(label))
    common = gcd(numerator, denominator)
    return {
        "status": "DEFINED",
        "numerator": numerator // common,
        "denominator": denominator // common,
    }


def _missing_fraction_v1(reason: Any) -> Dict[str, Any]:
    if reason not in _INSPECTION_MISSING_REASONS_V1:
        raise ValueError("unknown inspection metric missing reason")
    return {"status": "MISSING", "reason": reason}


def _normalize_fraction_v1(value: Any, label: str) -> Dict[str, Any]:
    if type(value) is not dict:
        raise TypeError("{} must be an exact fraction object".format(label))
    status = value.get("status")
    if status == "DEFINED":
        fraction = _exact_keys(
            value,
            ("status", "numerator", "denominator"),
            label,
        )
        normalized = _defined_fraction_v1(
            fraction["numerator"], fraction["denominator"], label
        )
        if _canonical_bytes(normalized) != _canonical_bytes(value):
            raise ValueError("{} is not in reduced canonical form".format(label))
        return normalized
    if status == "MISSING":
        missing = _exact_keys(value, ("status", "reason"), label)
        return _missing_fraction_v1(missing["reason"])
    raise ValueError("{} has an unknown fraction status".format(label))


def _fraction_number_v1(value: Mapping[str, Any]) -> Fraction:
    if value["status"] != "DEFINED":
        raise ValueError("missing inspection metric has no numeric value")
    return Fraction(value["numerator"], value["denominator"])


def _fraction_from_number_v1(value: Fraction, label: str) -> Dict[str, Any]:
    if value < 0 or value > 1:
        raise ValueError("{} must be in [0,1]".format(label))
    return _defined_fraction_v1(value.numerator, value.denominator, label)


def _normalize_inspection_outcomes_v1(
    value: Any, label: str, scheduled_games: int
) -> Dict[str, Any]:
    summary = _exact_keys(
        value,
        (
            "status",
            "scheduled_games",
            "completed_games",
            "a_wins",
            "b_wins",
            "draw_ply_limit",
        ),
        label,
    )
    status = summary["status"]
    if status not in ("COMPLETE", "INCOMPLETE", "INVALID"):
        raise ValueError("{} has an unknown status".format(label))
    scheduled = _exact_int(summary["scheduled_games"], "{} scheduled".format(label), 1)
    completed = _exact_int(summary["completed_games"], "{} completed".format(label))
    a_wins = _exact_int(summary["a_wins"], "{} A wins".format(label))
    b_wins = _exact_int(summary["b_wins"], "{} B wins".format(label))
    draws = _exact_int(
        summary["draw_ply_limit"], "{} PLY_LIMIT draws".format(label)
    )
    if scheduled != scheduled_games:
        raise ValueError("{} scheduled denominator drifted".format(label))
    if completed > scheduled or a_wins + b_wins + draws != completed:
        raise ValueError("{} counts do not reconstruct".format(label))
    if status == "COMPLETE" and completed != scheduled:
        raise ValueError("{} complete evidence lacks scheduled games".format(label))
    if status == "INCOMPLETE" and completed == scheduled:
        raise ValueError("{} incomplete evidence claims every game".format(label))
    return dict(summary)


def _calculate_exact_state_utilization_v1(value: Any) -> Dict[str, Any]:
    members = _exact_keys(
        value,
        ATLAS_MEMBER_ORDER_V1,
        "exact utilization members",
    )
    normalized = []
    for member_label in ATLAS_MEMBER_ORDER_V1:
        member = _exact_keys(
            members[member_label],
            ("status", "searched_states", "max_states"),
            "{} exact utilization".format(member_label),
        )
        if member["status"] not in ("COMPLETE", "INCOMPLETE", "INVALID"):
            raise ValueError("exact utilization has an unknown status")
        normalized.append(member)
    statuses = [member["status"] for member in normalized]
    if "INVALID" in statuses:
        return _missing_fraction_v1("INVALID_EVIDENCE")
    if "INCOMPLETE" in statuses:
        return _missing_fraction_v1("INCOMPLETE_EXACT")
    ratios = []
    for member in normalized:
        searched = _exact_int(member["searched_states"], "searched states", 1)
        maximum = _exact_int(member["max_states"], "maximum states", 1)
        ratios.append(_defined_fraction_v1(searched, maximum, "state utilization"))
    return dict(max(ratios, key=_fraction_number_v1))


def _calculate_strength_role_share_gap_v1(value: Any) -> Dict[str, Any]:
    strengths = _exact_keys(
        value,
        tuple(strength["identity"] for strength in _STRENGTHS_V1),
        "strength role-share inputs",
    )
    normalized = []
    for strength in _STRENGTHS_V1:
        identity = strength["identity"]
        summary = _normalize_inspection_outcomes_v1(
            strengths[identity],
            "{} pair outcomes".format(identity),
            ATLAS_SAMPLED_GAMES_PER_PAIR_STRENGTH_V1,
        )
        normalized.append((identity, summary))
    if any(summary["status"] == "INVALID" for _identity, summary in normalized):
        return _missing_fraction_v1("INVALID_EVIDENCE")
    for identity, summary in normalized:
        if summary["status"] == "INCOMPLETE":
            return _missing_fraction_v1(
                "INCOMPLETE_RANDOM"
                if identity == "random-v1-weak"
                else "INCOMPLETE_DEPTH1"
            )
    shares = []
    for identity, summary in normalized:
        decisive = summary["a_wins"] + summary["b_wins"]
        if decisive == 0:
            return _missing_fraction_v1(
                "ZERO_DECISIVE_RANDOM"
                if identity == "random-v1-weak"
                else "ZERO_DECISIVE_DEPTH1"
            )
        shares.append(Fraction(summary["a_wins"], decisive))
    return _fraction_from_number_v1(abs(shares[0] - shares[1]), "role-share gap")


def _calculate_d4_outcome_range_v1(
    value: Any, strength_identity: Any
) -> Dict[str, Any]:
    valid_strengths = tuple(strength["identity"] for strength in _STRENGTHS_V1)
    if strength_identity not in valid_strengths:
        raise ValueError("unknown inspection strength identity")
    orientations = _exact_keys(
        value,
        ATLAS_D4_TRANSFORMS_V1,
        "D4 outcome summaries",
    )
    normalized = []
    for transform in ATLAS_D4_TRANSFORMS_V1:
        summary = _normalize_inspection_outcomes_v1(
            orientations[transform],
            "{} {} outcomes".format(strength_identity, transform),
            16,
        )
        normalized.append(summary)
    if any(summary["status"] == "INVALID" for summary in normalized):
        return _missing_fraction_v1("INVALID_EVIDENCE")
    if any(summary["status"] == "INCOMPLETE" for summary in normalized):
        return _missing_fraction_v1(
            "INCOMPLETE_RANDOM"
            if strength_identity == "random-v1-weak"
            else "INCOMPLETE_DEPTH1"
        )
    shares = []
    for summary in normalized:
        decisive = summary["a_wins"] + summary["b_wins"]
        if decisive == 0:
            return _missing_fraction_v1("ZERO_DECISIVE_ORIENTATION")
        shares.append(Fraction(summary["a_wins"], decisive))
    return _fraction_from_number_v1(
        max(shares) - min(shares), "D4 outcome range"
    )


def _calculate_depth1_ply_limit_rate_v1(value: Any) -> Dict[str, Any]:
    summary = _normalize_inspection_outcomes_v1(
        value,
        "terminal-depth1 PLY_LIMIT inputs",
        ATLAS_SAMPLED_GAMES_PER_PAIR_STRENGTH_V1,
    )
    if summary["status"] == "INVALID":
        return _missing_fraction_v1("INVALID_EVIDENCE")
    if summary["status"] == "INCOMPLETE":
        return _missing_fraction_v1("INCOMPLETE_DEPTH1")
    return _defined_fraction_v1(
        summary["draw_ply_limit"],
        summary["scheduled_games"],
        "terminal-depth1 PLY_LIMIT rate",
    )


def _calculate_forced_decision_fractions_v1(value: Any) -> Dict[str, Any]:
    roles = _exact_keys(value, ATLAS_ROLE_ORDER_V1, "forced-decision role inputs")
    normalized = {}
    for role in ATLAS_ROLE_ORDER_V1:
        summary = _exact_keys(
            roles[role],
            ("status", "decision_count", "forced_decision_count"),
            "{} forced-decision inputs".format(role),
        )
        if summary["status"] not in ("COMPLETE", "INCOMPLETE", "INVALID"):
            raise ValueError("forced-decision telemetry has an unknown status")
        normalized[role] = summary
    if any(summary["status"] == "INVALID" for summary in normalized.values()):
        return {
            role: _missing_fraction_v1("INVALID_EVIDENCE")
            for role in ATLAS_ROLE_ORDER_V1
        }
    if any(summary["status"] == "INCOMPLETE" for summary in normalized.values()):
        return {
            role: _missing_fraction_v1("INCOMPLETE_TELEMETRY")
            for role in ATLAS_ROLE_ORDER_V1
        }
    result = {}
    for role in ATLAS_ROLE_ORDER_V1:
        summary = normalized[role]
        decisions = _exact_int(summary["decision_count"], "decision count")
        forced = _exact_int(summary["forced_decision_count"], "forced count")
        if forced > decisions:
            raise ValueError("forced decisions exceed all decisions")
        result[role] = (
            _missing_fraction_v1("ZERO_DECISIONS")
            if decisions == 0
            else _defined_fraction_v1(forced, decisions, "forced-decision fraction")
        )
    return result


def _calculate_depth1_reciprocal_dependency_fraction_v1(
    value: Any,
) -> Dict[str, Any]:
    summary = _exact_keys(
        value,
        ("status", "scheduled_games", "completed_games", "reciprocal_games"),
        "reciprocal-dependency inputs",
    )
    status = summary["status"]
    if status not in ("COMPLETE", "INCOMPLETE", "INVALID"):
        raise ValueError("reciprocal-dependency inputs have an unknown status")
    scheduled = _exact_int(summary["scheduled_games"], "reciprocal scheduled", 1)
    completed = _exact_int(summary["completed_games"], "reciprocal completed")
    reciprocal = _exact_int(summary["reciprocal_games"], "reciprocal games")
    if scheduled != ATLAS_SAMPLED_GAMES_PER_PAIR_STRENGTH_V1:
        raise ValueError("reciprocal-dependency denominator drifted")
    if completed > scheduled or reciprocal > completed:
        raise ValueError("reciprocal-dependency counts do not reconstruct")
    if status == "COMPLETE" and completed != scheduled:
        raise ValueError("complete reciprocal telemetry lacks scheduled games")
    if status == "INCOMPLETE" and completed == scheduled:
        raise ValueError("incomplete reciprocal telemetry claims every game")
    if status == "INVALID":
        return _missing_fraction_v1("INVALID_EVIDENCE")
    if status == "INCOMPLETE":
        return _missing_fraction_v1("INCOMPLETE_TELEMETRY")
    return _defined_fraction_v1(
        reciprocal, scheduled, "reciprocal-dependency fraction"
    )


def _normalize_inspection_pair_v1(value: Any, index: int) -> Dict[str, Any]:
    record = _exact_keys(
        value,
        (
            "pair_index",
            "paired_mechanical_d4_identity",
            "family_id",
            "paired_stratum_id",
            "channel_statuses",
            "exact_label",
            "random_label",
            "terminal_depth1_label",
            "pair_assessment",
            "metrics",
        ),
        "inspection pair record {}".format(index),
    )
    pair_index = _exact_int(record["pair_index"], "inspection pair index")
    if pair_index != index:
        raise ValueError("inspection pair records are not in manifest order")
    identity = _sha256(
        record["paired_mechanical_d4_identity"], "inspection pair identity"
    )
    family_id = record["family_id"]
    if family_id not in ATLAS_FAMILY_ORDER_V1:
        raise ValueError("inspection pair has an unknown family")
    stratum_id = record["paired_stratum_id"]
    if type(stratum_id) is not str or not stratum_id:
        raise ValueError("inspection pair stratum must be a nonempty string")
    statuses = _exact_keys(
        record["channel_statuses"],
        ("exact", "random", "terminal_depth1", "telemetry"),
        "inspection channel statuses",
    )
    normalized_statuses = dict(statuses)
    if any(
        status not in _INSPECTION_CHANNEL_STATUSES_V1
        for status in normalized_statuses.values()
    ):
        raise ValueError("inspection pair has an unknown channel status")
    exact_label = record["exact_label"]
    random_label = record["random_label"]
    terminal_label = record["terminal_depth1_label"]
    if exact_label not in _EXACT_PAIR_LABELS_V1:
        raise ValueError("inspection pair has an unknown exact label")
    if random_label not in _SAMPLED_STRENGTH_LABELS_V1:
        raise ValueError("inspection pair has an unknown random label")
    if terminal_label not in _SAMPLED_STRENGTH_LABELS_V1:
        raise ValueError("inspection pair has an unknown terminal-depth1 label")

    def expected_evidence_label(channel_status: str) -> Any:
        if channel_status in ("INVALID", "PROOF_CONTRADICTION"):
            return "EVIDENCE_INVALID"
        if channel_status in ("INCOMPLETE", "NOT_RUN", "BLOCKED"):
            return "EVIDENCE_INCOMPLETE"
        return None

    for channel, label in (
        ("exact", exact_label),
        ("random", random_label),
        ("terminal_depth1", terminal_label),
    ):
        expected = expected_evidence_label(normalized_statuses[channel])
        if expected is None:
            if label in ("EVIDENCE_INVALID", "EVIDENCE_INCOMPLETE"):
                raise ValueError("complete inspection channel has a noncomplete label")
        elif label != expected:
            raise ValueError("inspection channel status and label disagree")
    assessment = record["pair_assessment"]
    if assessment not in _PAIR_ASSESSMENTS_V1:
        raise ValueError("inspection pair has an unknown assessment")
    if assessment != _classify_atlas_pair_frontier_v1(
        exact_label, random_label, terminal_label
    ):
        raise ValueError("inspection pair assessment does not reconstruct from labels")

    metrics = _exact_keys(
        record["metrics"],
        (
            "exact_state_utilization",
            "strength_role_share_gap",
            "d4_outcome_range",
            "depth1_ply_limit_rate",
            "forced_decision_fraction",
            "depth1_reciprocal_dependency_fraction",
        ),
        "inspection pair metrics",
    )
    d4 = _exact_keys(
        metrics["d4_outcome_range"],
        tuple(strength["identity"] for strength in _STRENGTHS_V1),
        "inspection D4 metrics",
    )
    forced = _exact_keys(
        metrics["forced_decision_fraction"],
        ATLAS_ROLE_ORDER_V1,
        "inspection forced-decision metrics",
    )
    normalized_metrics = {
        "exact_state_utilization": _normalize_fraction_v1(
            metrics["exact_state_utilization"], "exact state utilization"
        ),
        "strength_role_share_gap": _normalize_fraction_v1(
            metrics["strength_role_share_gap"], "strength role-share gap"
        ),
        "d4_outcome_range": {
            strength["identity"]: _normalize_fraction_v1(
                d4[strength["identity"]],
                "{} D4 outcome range".format(strength["identity"]),
            )
            for strength in _STRENGTHS_V1
        },
        "depth1_ply_limit_rate": _normalize_fraction_v1(
            metrics["depth1_ply_limit_rate"], "depth1 PLY_LIMIT rate"
        ),
        "forced_decision_fraction": {
            role: _normalize_fraction_v1(
                forced[role], "{} forced-decision fraction".format(role)
            )
            for role in ATLAS_ROLE_ORDER_V1
        },
        "depth1_reciprocal_dependency_fraction": _normalize_fraction_v1(
            metrics["depth1_reciprocal_dependency_fraction"],
            "depth1 reciprocal-dependency fraction",
        ),
    }

    return {
        "pair_index": pair_index,
        "paired_mechanical_d4_identity": identity,
        "family_id": family_id,
        "paired_stratum_id": stratum_id,
        "channel_statuses": normalized_statuses,
        "exact_label": exact_label,
        "random_label": random_label,
        "terminal_depth1_label": terminal_label,
        "pair_assessment": assessment,
        "metrics": normalized_metrics,
    }


def _inspection_group_v1(kind: str, **fields: Any) -> Dict[str, Any]:
    return {"kind": kind, **fields}


def _inspection_score_v1(
    class_name: str,
    direction: str,
    group: Mapping[str, Any],
    pair_identity: str,
) -> str:
    return _digest(
        _INSPECTION_SCORE_DOMAIN_V1,
        {
            "class": class_name,
            "direction": direction,
            "group": dict(group),
            "paired_mechanical_d4_identity": pair_identity,
        },
    )


def _calculate_atlas_inspection_selection_v1(
    pair_records_value: Any,
) -> Dict[str, Any]:
    """Select the frozen descriptive inspection union from normalized rows.

    This is an executable arithmetic/selection helper, not an evidence boundary.
    The later result validator must reconstruct every input row from manifest-
    bound raw slots before calling it.
    """

    if type(pair_records_value) is not list or len(pair_records_value) != (
        ATLAS_DEVELOPMENT_PAIR_COUNT_V1
    ):
        raise ValueError("inspection selection requires exactly 144 pair records")
    records = [
        _normalize_inspection_pair_v1(raw, index)
        for index, raw in enumerate(pair_records_value)
    ]
    identities = [record["paired_mechanical_d4_identity"] for record in records]
    if len(set(identities)) != len(identities):
        raise ValueError("inspection selection repeats a pair identity")
    if Counter(record["family_id"] for record in records) != Counter(
        {family_id: 24 for family_id in ATLAS_FAMILY_ORDER_V1}
    ):
        raise ValueError("inspection family exposure differs from the frozen atlas")
    stratum_order = list(
        dict.fromkeys(record["paired_stratum_id"] for record in records)
    )
    if len(stratum_order) != ATLAS_PAIRED_STRATUM_COUNT_V1:
        raise ValueError("inspection paired-stratum exposure drifted")

    reasons_by_index: Dict[int, List[Dict[str, Any]]] = {
        record["pair_index"]: [] for record in records
    }
    class_summaries = []

    def add_selection(
        class_name: str,
        direction: str,
        group: Mapping[str, Any],
        population: Sequence[Mapping[str, Any]],
        eligible: Sequence[Mapping[str, Any]],
        selected: Sequence[Tuple[Mapping[str, Any], Any]],
        metric_defined_count: Any,
        metric_missing_count: Any,
    ) -> None:
        selected_identities = []
        for rank, (record, metric) in enumerate(selected, 1):
            identity = record["paired_mechanical_d4_identity"]
            score = _inspection_score_v1(
                class_name, direction, group, identity
            )
            reasons_by_index[record["pair_index"]].append(
                {
                    "class": class_name,
                    "direction": direction,
                    "group": dict(group),
                    "rank": rank,
                    "metric": (
                        None
                        if metric is None
                        else _json_copy(metric, "inspection reason metric")
                    ),
                    "tie_score": score,
                }
            )
            selected_identities.append(identity)
        class_summaries.append(
            {
                "class": class_name,
                "direction": direction,
                "group": dict(group),
                "population_count": len(population),
                "eligible_count": len(eligible),
                "metric_defined_count": metric_defined_count,
                "metric_missing_count": metric_missing_count,
                "selected_count": len(selected),
                "selected_pair_identities": selected_identities,
            }
        )

    global_group = _inspection_group_v1("GLOBAL")
    mandatory = [
        record
        for record in records
        if any(status != "COMPLETE" for status in record["channel_statuses"].values())
        or record["exact_label"] == "HORIZON_UNRESOLVED"
        or record["random_label"] == "EXCESSIVE_HORIZON_SIGNAL"
        or record["terminal_depth1_label"] == "EXCESSIVE_HORIZON_SIGNAL"
    ]
    add_selection(
        "MANDATORY_EXCEPTION",
        "ALL",
        global_group,
        records,
        mandatory,
        [(record, None) for record in mandatory],
        None,
        None,
    )
    frontier = [
        record
        for record in records
        if record["pair_assessment"] == "PAIR_FRONTIER_SIGNAL_V1"
    ]
    add_selection(
        "PAIR_FRONTIER",
        "ALL",
        global_group,
        records,
        frontier,
        [(record, None) for record in frontier],
        None,
        None,
    )

    for stratum_id in stratum_order:
        population = [
            record for record in records if record["paired_stratum_id"] == stratum_id
        ]
        eligible = [
            record
            for record in population
            if all(
                status == "COMPLETE"
                for status in record["channel_statuses"].values()
            )
            and record["pair_assessment"]
            in ("NO_PAIR_FRONTIER_EXACT", "NO_PAIR_FRONTIER_WEAK_PLAY")
            and record["random_label"] != "EXCESSIVE_HORIZON_SIGNAL"
            and record["terminal_depth1_label"] != "EXCESSIVE_HORIZON_SIGNAL"
        ]
        group = _inspection_group_v1(
            "PAIRED_STRATUM", paired_stratum_id=stratum_id
        )
        ordered = sorted(
            eligible,
            key=lambda record: (
                _inspection_score_v1(
                    "ORDINARY_CONTROL",
                    "HASH_MIN",
                    group,
                    record["paired_mechanical_d4_identity"],
                ),
                record["paired_mechanical_d4_identity"],
            ),
        )
        add_selection(
            "ORDINARY_CONTROL",
            "HASH_MIN",
            group,
            population,
            eligible,
            [(record, None) for record in ordered[:1]],
            None,
            None,
        )

    def add_metric_extreme(
        class_name: str,
        direction: str,
        group: Mapping[str, Any],
        population: Sequence[Mapping[str, Any]],
        metric_values: Sequence[Tuple[Mapping[str, Any], Mapping[str, Any]]],
    ) -> None:
        defined = [
            (record, metric)
            for record, metric in metric_values
            if metric["status"] == "DEFINED"
        ]
        ordered = sorted(
            defined,
            key=lambda item: (
                (
                    -_fraction_number_v1(item[1])
                    if direction == "HIGH"
                    else _fraction_number_v1(item[1])
                ),
                _inspection_score_v1(
                    class_name,
                    direction,
                    group,
                    item[0]["paired_mechanical_d4_identity"],
                ),
                item[0]["paired_mechanical_d4_identity"],
            ),
        )
        add_selection(
            class_name,
            direction,
            group,
            population,
            [record for record, _metric in defined],
            ordered[:1],
            len(defined),
            len(metric_values) - len(defined),
        )

    for family_id in ATLAS_FAMILY_ORDER_V1:
        family = [record for record in records if record["family_id"] == family_id]
        family_group = _inspection_group_v1("FAMILY", family_id=family_id)
        add_metric_extreme(
            "EXACT_STATE_UTILIZATION",
            "HIGH",
            family_group,
            family,
            [
                (record, record["metrics"]["exact_state_utilization"])
                for record in family
            ],
        )
        add_metric_extreme(
            "STRENGTH_ROLE_SHARE_GAP",
            "HIGH",
            family_group,
            family,
            [
                (record, record["metrics"]["strength_role_share_gap"])
                for record in family
            ],
        )
        for strength in _STRENGTHS_V1:
            identity = strength["identity"]
            group = _inspection_group_v1(
                "FAMILY_X_STRENGTH",
                family_id=family_id,
                strength=identity,
            )
            add_metric_extreme(
                "D4_OUTCOME_RANGE",
                "HIGH",
                group,
                family,
                [
                    (record, record["metrics"]["d4_outcome_range"][identity])
                    for record in family
                ],
            )
        for direction in ("LOW", "HIGH"):
            add_metric_extreme(
                "DEPTH1_PLY_LIMIT_RATE",
                direction,
                family_group,
                family,
                [
                    (record, record["metrics"]["depth1_ply_limit_rate"])
                    for record in family
                ],
            )
        for role in ATLAS_ROLE_ORDER_V1:
            group = _inspection_group_v1(
                "FAMILY_X_ROLE", family_id=family_id, role=role
            )
            for direction in ("LOW", "HIGH"):
                add_metric_extreme(
                    "FORCED_DECISION_FRACTION",
                    direction,
                    group,
                    family,
                    [
                        (
                            record,
                            record["metrics"]["forced_decision_fraction"][role],
                        )
                        for record in family
                    ],
                )
        for direction in ("LOW", "HIGH"):
            add_metric_extreme(
                "DEPTH1_RECIPROCAL_DEPENDENCY_FRACTION",
                direction,
                family_group,
                family,
                [
                    (
                        record,
                        record["metrics"][
                            "depth1_reciprocal_dependency_fraction"
                        ],
                    )
                    for record in family
                ],
            )

    selected_pairs = [
        {
            "pair_index": record["pair_index"],
            "paired_mechanical_d4_identity": record[
                "paired_mechanical_d4_identity"
            ],
            "family_id": record["family_id"],
            "paired_stratum_id": record["paired_stratum_id"],
            "reasons": reasons_by_index[record["pair_index"]],
        }
        for record in records
        if reasons_by_index[record["pair_index"]]
    ]
    unsigned = {
        "inspection_calculation_version": 1,
        "formal_evidence": False,
        "pair_record_count": len(records),
        "class_group_summary_count": len(class_summaries),
        "class_group_summaries": class_summaries,
        "selected_pair_count": len(selected_pairs),
        "selected_pairs": selected_pairs,
    }
    return _json_copy(unsigned, "inspection selection")


def _normalize_exact_member(value: Any, label: str) -> Dict[str, Any]:
    member = _exact_keys(
        value,
        ("status", "forced_result", "terminal_reason"),
        label,
    )
    status = member["status"]
    if status not in ("COMPLETE", "INCOMPLETE", "INVALID"):
        raise ValueError("{} has an unknown status".format(label))
    forced = member["forced_result"]
    reason = member["terminal_reason"]
    if status == "COMPLETE":
        if forced not in ("A_WIN", "B_WIN", "DRAW"):
            raise ValueError("{} has an unknown forced result".format(label))
        if reason not in ("GOAL", "NO_LEGAL_ACTION", "PLY_LIMIT"):
            raise ValueError("{} has an unknown terminal reason".format(label))
        if forced == "DRAW" and reason != "PLY_LIMIT":
            raise ValueError("current atlas permits only PLY_LIMIT exact draws")
        if forced != "DRAW" and reason == "PLY_LIMIT":
            raise ValueError("PLY_LIMIT exact evidence must be a draw")
    elif forced is not None or reason is not None:
        raise ValueError("incomplete or invalid exact evidence must not claim a result")
    return dict(member)


def _classify_atlas_exact_pair_v1(a_first: Any, b_first: Any) -> str:
    a = _normalize_exact_member(a_first, "A-first exact member")
    b = _normalize_exact_member(b_first, "B-first exact member")
    if "INVALID" in (a["status"], b["status"]):
        return "EVIDENCE_INVALID"
    if "INCOMPLETE" in (a["status"], b["status"]):
        return "EVIDENCE_INCOMPLETE"
    if "DRAW" in (a["forced_result"], b["forced_result"]):
        return "HORIZON_UNRESOLVED"
    return {
        ("A_WIN", "A_WIN"): "A_ROLE_DOMINANT",
        ("B_WIN", "B_WIN"): "B_ROLE_DOMINANT",
        ("A_WIN", "B_WIN"): "FIRST_PLAYER_DOMINANT",
        ("B_WIN", "A_WIN"): "SECOND_PLAYER_DOMINANT",
    }[(a["forced_result"], b["forced_result"])]


def _classify_atlas_sampled_strength_v1(summary_value: Any) -> str:
    summary = _exact_keys(
        summary_value,
        ("status", "scheduled_games", "completed_games", "a_wins", "b_wins", "draws"),
        "sampled strength summary",
    )
    status = summary["status"]
    if status not in ("COMPLETE", "INCOMPLETE", "INVALID"):
        raise ValueError("sampled strength summary has an unknown status")
    scheduled = _exact_int(summary["scheduled_games"], "scheduled games", 1)
    completed = _exact_int(summary["completed_games"], "completed games")
    a_wins = _exact_int(summary["a_wins"], "A wins")
    b_wins = _exact_int(summary["b_wins"], "B wins")
    draws = _exact_int(summary["draws"], "draws")
    if scheduled != ATLAS_SAMPLED_GAMES_PER_PAIR_STRENGTH_V1:
        raise ValueError("sampled strength schedule denominator drifted")
    if completed > scheduled or a_wins + b_wins + draws != completed:
        raise ValueError("sampled strength outcome counts do not reconstruct")
    if status == "COMPLETE" and completed != scheduled:
        raise ValueError("complete sampled strength lacks all scheduled games")
    if status == "INCOMPLETE" and completed == scheduled:
        raise ValueError("incomplete sampled strength claims all games")
    if status == "INVALID":
        return "EVIDENCE_INVALID"
    if status == "INCOMPLETE":
        return "EVIDENCE_INCOMPLETE"
    decisive = a_wins + b_wins
    if decisive < ATLAS_SAMPLED_MIN_DECISIVE_GAMES_V1:
        return "EXCESSIVE_HORIZON_SIGNAL"
    if (
        ATLAS_SAMPLED_MINORITY_SHARE_DENOMINATOR_V1 * min(a_wins, b_wins)
        < ATLAS_SAMPLED_MINORITY_SHARE_NUMERATOR_V1 * decisive
    ):
        return "ROLE_IMBALANCE_SIGNAL"
    return "WEAK_BALANCE_SIGNAL_V1"


def _classify_atlas_pair_frontier_v1(
    exact_label: Any, random_label: Any, terminal_depth1_label: Any
) -> str:
    if exact_label not in _EXACT_PAIR_LABELS_V1:
        raise ValueError("unknown exact pair label")
    if random_label not in _SAMPLED_STRENGTH_LABELS_V1:
        raise ValueError("unknown random sampled label")
    if terminal_depth1_label not in _SAMPLED_STRENGTH_LABELS_V1:
        raise ValueError("unknown terminal-depth1 sampled label")
    labels = (exact_label, random_label, terminal_depth1_label)
    if "EVIDENCE_INVALID" in labels:
        return "EVIDENCE_INVALID"
    if "EVIDENCE_INCOMPLETE" in labels:
        return "EVIDENCE_INCOMPLETE"
    if exact_label == "HORIZON_UNRESOLVED":
        return "HORIZON_UNRESOLVED"
    if exact_label not in ("FIRST_PLAYER_DOMINANT", "SECOND_PLAYER_DOMINANT"):
        return "NO_PAIR_FRONTIER_EXACT"
    if random_label != "WEAK_BALANCE_SIGNAL_V1" or terminal_depth1_label != (
        "WEAK_BALANCE_SIGNAL_V1"
    ):
        return "NO_PAIR_FRONTIER_WEAK_PLAY"
    return "PAIR_FRONTIER_SIGNAL_V1"


def _assess_atlas_family_frontier_v1(pair_records_value: Any) -> Dict[str, Any]:
    if type(pair_records_value) is not list or len(pair_records_value) != 24:
        raise ValueError("family assessment requires exactly 24 pair records")
    identities = set()
    frontier_strata = set()
    assessment_counts = Counter()
    for index, raw in enumerate(pair_records_value):
        record = _exact_keys(
            raw,
            ("paired_mechanical_d4_identity", "paired_stratum_id", "assessment"),
            "family pair record {}".format(index),
        )
        identity = _sha256(
            record["paired_mechanical_d4_identity"], "family pair identity"
        )
        if identity in identities:
            raise ValueError("family assessment repeats a pair identity")
        identities.add(identity)
        if type(record["paired_stratum_id"]) is not str or not record[
            "paired_stratum_id"
        ]:
            raise ValueError("family pair stratum identity must be nonempty")
        assessment = record["assessment"]
        if assessment not in _PAIR_ASSESSMENTS_V1:
            raise ValueError("family pair record has an unknown assessment")
        assessment_counts[assessment] += 1
        if assessment == "PAIR_FRONTIER_SIGNAL_V1":
            frontier_strata.add(record["paired_stratum_id"])
    invalid_count = assessment_counts["EVIDENCE_INVALID"]
    incomplete_count = assessment_counts["EVIDENCE_INCOMPLETE"]
    frontier_count = assessment_counts["PAIR_FRONTIER_SIGNAL_V1"]
    if invalid_count:
        status = "EVIDENCE_INVALID"
    elif incomplete_count:
        status = "INCONCLUSIVE_INCOMPLETE"
    elif (
        frontier_count >= ATLAS_FAMILY_FRONTIER_MIN_PAIR_COUNT_V1
        and len(frontier_strata) >= ATLAS_FAMILY_FRONTIER_MIN_STRATUM_COUNT_V1
    ):
        status = "SUPPORTED_FAMILY_FRONTIER"
    else:
        status = "NOT_SUPPORTED_COMPLETE"
    return {
        "formal_evidence": False,
        "status": status,
        "development_pair_count": len(pair_records_value),
        "frontier_pair_count": frontier_count,
        "frontier_distinct_stratum_count": len(frontier_strata),
        "invalid_pair_count": invalid_count,
        "incomplete_pair_count": incomplete_count,
        "assessment_counts": {
            key: assessment_counts.get(key, 0)
            for key in sorted(_PAIR_ASSESSMENTS_V1)
        },
    }


__all__ = (
    "ATLAS_ACTION_CANDIDATE_CAP_V1",
    "ATLAS_EXACT_ACTION_CANDIDATE_CAP_TOTAL_V1",
    "ATLAS_DEFINITION_ORIENTATION_COUNT_V1",
    "ATLAS_DEVELOPMENT_DEFINITION_COUNT_V1",
    "ATLAS_DEVELOPMENT_PAIR_COUNT_V1",
    "ATLAS_D4_TRANSFORMS_V1",
    "ATLAS_EVALUATOR_COMMIT_V1",
    "ATLAS_EXACT_SCHEDULE_ROOT_V1",
    "ATLAS_EXACT_STATE_CAP_TOTAL_V1",
    "ATLAS_FAMILY_FRONTIER_MIN_PAIR_COUNT_V1",
    "ATLAS_FAMILY_FRONTIER_MIN_STRATUM_COUNT_V1",
    "ATLAS_GAME_SCHEDULE_ROOT_V1",
    "ATLAS_MATCHED_START_BLOCK_COUNT_V1",
    "ATLAS_MATCHED_START_BLOCK_ROOT_V1",
    "ATLAS_ORIENTATION_SCHEDULE_ROOT_V1",
    "ATLAS_PROFILE_SCHEDULE_ROOT_V1",
    "ATLAS_PROTOCOL_CANONICAL_SHA256_V1",
    "ATLAS_PROTOCOL_ID_V1",
    "ATLAS_PROTOCOL_ROOT_V1",
    "ATLAS_PROTOCOL_VERSION_V1",
    "ATLAS_ROLE_SLOT_SCHEDULE_ROOT_V1",
    "ATLAS_SAMPLED_GAME_COUNT_V1",
    "ATLAS_SAMPLED_PROFILE_COUNT_V1",
    "ATLAS_SAMPLED_ROLE_SLOT_COUNT_V1",
    "ATLAS_SEEDS_V1",
    "ATLAS_SELECTOR_COMMIT_V1",
    "ATLAS_TELEMETRY_SCHEDULE_ROOT_V1",
    "ATLAS_TERMINAL_DEPTH1_NODE_CAP_TOTAL_V1",
    "ATLAS_TERMINAL_DEPTH1_ROLE_SLOT_CAP_V1",
    "build_frozen_atlas_protocol_v1",
    "canonical_frozen_atlas_protocol_json_v1",
    "iter_frozen_atlas_exact_schedule_from_protocol_v1",
    "iter_frozen_atlas_game_schedule_from_protocol_v1",
    "iter_frozen_atlas_matched_start_blocks_from_protocol_v1",
    "iter_frozen_atlas_orientation_schedule_from_protocol_v1",
    "iter_frozen_atlas_profile_schedule_from_protocol_v1",
    "iter_frozen_atlas_role_schedule_from_protocol_v1",
    "validate_frozen_atlas_protocol_v1",
)
