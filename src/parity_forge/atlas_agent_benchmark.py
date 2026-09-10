"""Frozen synthetic conformance benchmark for the Plan-0013 common agent.

The five definitions in this module are hand-authored calculation fixtures.
Four reuse exact definitions from the frozen Plan-0012 replay-telemetry
benchmark; one adds dynamic CONNECT, terminal-priority, and minimizing-B probes.
No atlas definition is constructed, solved, searched, or played here.
"""

from __future__ import annotations

import hashlib
import json
import random
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .agents import RandomAgent, SearchBudgetExceeded
from .atlas import (
    ATLAS_CANDIDATE_DEFINITION_COUNT_V1,
    ATLAS_DEVELOPMENT_DEFINITION_COUNT_V1,
    ATLAS_PAIRED_UNIVERSE_WITNESS_ROOT_V1,
    ATLAS_SEARCH_ENVELOPE_ROOT_V1,
    ATLAS_SELECTION_PARTITION_ROOT_V1,
)
from .atlas_history import (
    ATLAS_SYNTHETIC_PROJECTION_ROOT_V1,
    PLAN0012_SYNTHETIC_BENCHMARK_ROOT_V1,
    PLAN0012_SYNTHETIC_FIXTURE_IDENTITIES_V1,
)
from .dsl import (
    GameDefinition,
    GoalKind,
    Player,
    canonical_json,
    definition_hash,
    parse_definition,
)
from .engine import (
    Action,
    GameState,
    apply_action,
    goal_satisfied,
    initial_state,
    legal_actions,
)
from .solver import solve_game
from .symmetry import (
    D4_TRANSFORMS,
    d4_canonical_hash,
    transform_definition,
    transform_position,
)
from .terminal_search import (
    TERMINAL_ONLY_MINIMAX_MAX_DEPTH,
    TerminalOnlyMinimaxAgent,
)


ATLAS_AGENT_BENCHMARK_VERSION_V1 = 1
ATLAS_AGENT_BENCHMARK_ID_V1 = (
    "plan0013-schema-v4-terminal-only-agent-benchmark-v1"
)
ATLAS_AGENT_BENCHMARK_FIXTURE_COUNT_V1 = 5
ATLAS_AGENT_BENCHMARK_D4_SLOT_COUNT_V1 = 40
ATLAS_AGENT_BENCHMARK_RANDOM_GAME_COUNT_V1 = 320
ATLAS_AGENT_BENCHMARK_TERMINAL_GAME_COUNT_V1 = 320
ATLAS_AGENT_BENCHMARK_SEARCH_CAP_V1 = 10_000

# The production ladder authorizes random-v1 and terminal-only depth 1.  Depth 2
# is retained as a conformance probe and a separately reported structural bound,
# not as an authorized atlas strength.
ATLAS_AGENT_PRODUCTION_DEPTH1_NODE_CAP_V1 = 3_456
ATLAS_AGENT_DIAGNOSTIC_DEPTH2_NODE_BOUND_V1 = 169_344


# These are filled from the canonical builders and are intentionally checked at
# every public frozen boundary.  They are not caller-supplied or self-signed.
ATLAS_AGENT_BENCHMARK_FIXTURE_ROOT_V1 = (
    "9a45e26ff2e86a1de0f5b53afd7267b63e7877d29fbd8f0bf071f7a5fc99f565"
)
ATLAS_AGENT_BENCHMARK_LADDER_ROOT_V1 = (
    "62255ad512d6258250ea7af0b757530dea4e7c991fae8305b88af656ccb65e62"
)
ATLAS_AGENT_BENCHMARK_EVIDENCE_ROOT_V1 = (
    "5cd0dd2a114e2b503d68131bf3892cd0d513b2d7fed12522c82425d440f8d075"
)
ATLAS_AGENT_BENCHMARK_RANDOM_CONFORMANCE_ROOT_V1 = (
    "50a0ef2db98b7ade17325b34692a432cae610b9e71850a72385a29494d477576"
)
ATLAS_AGENT_BENCHMARK_TERMINAL_CONFORMANCE_ROOT_V1 = (
    "38dce33df7283429705ef4b33b2260be4798cf355b0bc8f6493fc15e19480026"
)
ATLAS_AGENT_BENCHMARK_ATLAS_SEPARATION_ROOT_V1 = (
    "a82e7640346954412710ec3c2e476243917845cf145ca42353dba0ed16751eba"
)
ATLAS_AGENT_BENCHMARK_ROOT_V1 = (
    "340e928d5b6ba64743dbcfd252eff951af185bc7c30138ccee333710ded15da0"
)
ATLAS_AGENT_BENCHMARK_CANONICAL_SHA256_V1 = (
    "5097d4d516963938a74f0fd020e96d0934943ccc4b0c5a9e0c2056156a2a3ffc"
)


_FIXTURE_ROOT_DOMAIN_V1 = b"parity-forge:plan0013:agent-benchmark-fixtures:v1\0"
_LADDER_ROOT_DOMAIN_V1 = b"parity-forge:plan0013:agent-benchmark-ladder:v1\0"
_EVIDENCE_ROOT_DOMAIN_V1 = b"parity-forge:plan0013:agent-benchmark-evidence:v1\0"
_RANDOM_ROOT_DOMAIN_V1 = b"parity-forge:plan0013:agent-benchmark-random:v1\0"
_TERMINAL_LIFECYCLE_ROOT_DOMAIN_V1 = (
    b"parity-forge:plan0013:agent-benchmark-terminal-lifecycle:v1\0"
)
_SEPARATION_ROOT_DOMAIN_V1 = b"parity-forge:plan0013:agent-benchmark-separation:v1\0"
_BENCHMARK_ROOT_DOMAIN_V1 = b"parity-forge:plan0013:agent-benchmark:v1\0"

_MAX_VALIDATION_DEPTH_V1 = 64
_MAX_VALIDATION_NODES_V1 = 200_000
_MAX_VALIDATION_TEXT_CHARACTERS_V1 = 8_000_000
_MAX_VALIDATION_SINGLE_STRING_CHARACTERS_V1 = 1_000_000
_MAX_VALIDATION_INTEGER_BITS_V1 = 256
_MAX_VALIDATION_CANONICAL_BYTES_V1 = 64_000_000


# fixture_id, provenance, canonical DSL JSON.  Keeping exact canonical strings
# avoids importing test modules or sharing mutable definition objects.
_FIXTURE_SPECS_V1 = (
    (
        "capture-eliminate-one-sided-b-v1",
        "PLAN0012_SYNTHETIC_REUSE",
        '{"board_size":3,"first_player":"A","initial_pieces":'
        '[{"owner":"A","piece":"prey","position":[1,0]},'
        '{"owner":"B","piece":"hunter","position":[1,1]},'
        '{"owner":"A","piece":"mover","position":[2,2]}],'
        '"max_plies":4,"name":"Telemetry capture eliminate v1",'
        '"roles":{"A":{"action":{"kind":"HOP","piece":"mover",'
        '"vectors":[[-1,0]]},"goal":{"edge":"TOP","kind":"REACH_EDGE",'
        '"piece":"mover"}},"B":{"action":{"kind":"MOVE_CAPTURE",'
        '"piece":"hunter","vectors":[[0,-1]]},"goal":{"kind":"ELIMINATE",'
        '"piece":"prey"}}},"schema_version":4}',
    ),
    (
        "convert-immediate-reconvergence-v1",
        "PLAN0012_SYNTHETIC_REUSE",
        '{"board_size":3,"first_player":"A","initial_pieces":'
        '[{"owner":"A","piece":"converter","position":[0,1]},'
        '{"owner":"A","piece":"converter","position":[1,0]},'
        '{"owner":"B","piece":"victim","position":[1,1]},'
        '{"owner":"B","piece":"b","position":[2,2]}],'
        '"max_plies":2,"name":"Telemetry immediate reconvergence v1",'
        '"roles":{"A":{"action":{"kind":"CONVERT","piece":"converter",'
        '"vectors":[[0,1],[1,0]]},"goal":{"edge":"BOTTOM",'
        '"kind":"REACH_EDGE","piece":"converter"}},"B":{"action":'
        '{"kind":"MOVE","piece":"b","vectors":[[-1,0]]},"goal":'
        '{"edge":"TOP","kind":"REACH_EDGE","piece":"b"}}},'
        '"schema_version":4}',
    ),
    (
        "hop-opponent-dependency-without-direct-effect-v1",
        "PLAN0012_SYNTHETIC_REUSE",
        '{"board_size":3,"first_player":"A","initial_pieces":'
        '[{"owner":"A","piece":"hopper","position":[1,0]},'
        '{"owner":"B","piece":"blocker","position":[1,1]}],'
        '"max_plies":1,"name":"Telemetry hop opponent dependency v1",'
        '"roles":{"A":{"action":{"kind":"HOP","piece":"hopper",'
        '"vectors":[[0,1]]},"goal":{"edge":"TOP","kind":"REACH_EDGE",'
        '"piece":"hopper"}},"B":{"action":{"kind":"MOVE",'
        '"piece":"blocker","vectors":[[1,0]]},"goal":{"edge":"BOTTOM",'
        '"kind":"REACH_EDGE","piece":"blocker"}}},"schema_version":4}',
    ),
    (
        "push-win-draw-loss-v1",
        "PLAN0012_SYNTHETIC_REUSE",
        '{"board_size":3,"first_player":"A","initial_pieces":'
        '[{"owner":"A","piece":"p","position":[0,0]},'
        '{"owner":"A","piece":"p","position":[0,2]},'
        '{"owner":"B","piece":"b","position":[1,0]},'
        '{"owner":"A","piece":"p","position":[1,1]}],'
        '"max_plies":1,"name":"Telemetry tri outcome v1",'
        '"roles":{"A":{"action":{"kind":"PUSH","piece":"p",'
        '"vectors":[[1,0]]},"goal":{"edge":"BOTTOM",'
        '"kind":"REACH_EDGE","piece":"p"}},"B":{"action":{"kind":"MOVE",'
        '"piece":"b","vectors":[[0,1]]},"goal":{"edge":"BOTTOM",'
        '"kind":"REACH_EDGE","piece":"b"}}},"schema_version":4}',
    ),
    (
        "swap-simultaneous-connect-v1",
        "PLAN0013_SYNTHETIC_ADDITION",
        '{"board_size":3,"first_player":"A","initial_pieces":'
        '[{"owner":"A","piece":"a","position":[0,1]},'
        '{"owner":"A","piece":"a","position":[1,0]},'
        '{"owner":"B","piece":"b","position":[1,1]},'
        '{"owner":"A","piece":"a","position":[2,1]}],'
        '"max_plies":2,"name":"Terminal-only simultaneous connect v1",'
        '"roles":{"A":{"action":{"kind":"SWAP","piece":"a",'
        '"vectors":[[0,1]]},"goal":{"edges":["BOTTOM","TOP"],'
        '"kind":"CONNECT_EDGES","piece":"a"}},"B":{"action":'
        '{"kind":"MOVE_CAPTURE","piece":"b","vectors":'
        '[[-1,0],[0,-1],[0,1],[1,0]]},"goal":'
        '{"edge":"LEFT","kind":"REACH_EDGE","piece":"b"}}},'
        '"schema_version":4}',
    ),
)


_EXPECTED_FIXTURE_GOLDENS_V1 = {
    "capture-eliminate-one-sided-b-v1": {
        "canonical_byte_count": 519,
        "definition_hash": "ccbf7cfe2076e6d6fbd66aa35f0a9fd1d760f7510a4ef0a1f3b0e5e4b1e66eda",
        "d4_hash": "bb61383bd417dc9fa32c7d1717c309f25b8e490a0f6c39051e3db6ac4431770a",
        "exact": ("B_WIN", "GOAL", 2, 3, 2),
        "depth1": (0, 1, (0,)),
        "depth2": (-1, 2, (-1,)),
    },
    "convert-immediate-reconvergence-v1": {
        "canonical_byte_count": 595,
        "definition_hash": "fd2768bc19220de4c5e0c18040982524b034e0215279d8b51b79b9a5c513a079",
        "d4_hash": "01425a63068bbbb5720a1dd56ffb5b9b7f38f3905f56ee9b77ae7333c110c9ed",
        "exact": ("DRAW", "PLY_LIMIT", 2, 3, 3),
        "depth1": (0, 1, (0, 0)),
        "depth2": (0, 2, (0, 0)),
    },
    "hop-opponent-dependency-without-direct-effect-v1": {
        "canonical_byte_count": 494,
        "definition_hash": "08536bcae39cf0f8eaaf541ba4e570288572cb9bedac93c43041a2ea0219fd84",
        "d4_hash": "454de6d824d820179faad6cde1023804bb2ff9be73d959fca8662836be38f85a",
        "exact": ("DRAW", "PLY_LIMIT", 1, 2, 1),
        "depth1": (0, 1, (0,)),
        "depth2": (0, 1, (0,)),
    },
    "push-win-draw-loss-v1": {
        "canonical_byte_count": 539,
        "definition_hash": "f3690d6aa29f83f72b9b3208e6c0a5783a43e2711c5f9a1780a72c6cac3c2e49",
        "d4_hash": "2a48252b987d917a51df5a2bfb93da3fa6c2d93768facb27f03226b53c3f3578",
        "exact": ("A_WIN", "GOAL", 1, 4, 1),
        "depth1": (1, 3, (-1, 0, 1)),
        "depth2": (1, 3, (-1, 0, 1)),
    },
    "swap-simultaneous-connect-v1": {
        "canonical_byte_count": 590,
        "definition_hash": "eaaf30187d95c215c2d330f1e68c92b10ff7718b85e16801de2a15353b8c3db2",
        "d4_hash": "1a45490b6055cb99ae06ece0ece46d30891c276e1c1048297349fdadba019cf4",
        "exact": ("A_WIN", "GOAL", 1, 12, 1),
        "depth1": (1, 3, (0, 1, 0)),
        "depth2": (1, 11, (-1, 1, -1)),
    },
}


_DYNAMIC_ACTION_WITNESSES_V1 = (
    (
        "PUSH",
        "push-win-draw-loss-v1",
        (),
        {"kind": "PUSH", "from": [0, 0], "to": [1, 0]},
    ),
    (
        "SWAP",
        "swap-simultaneous-connect-v1",
        (),
        {"kind": "SWAP", "from": [1, 0], "to": [1, 1]},
    ),
    (
        "HOP",
        "hop-opponent-dependency-without-direct-effect-v1",
        (),
        {"kind": "HOP", "from": [1, 0], "to": [1, 2]},
    ),
    (
        "CONVERT",
        "convert-immediate-reconvergence-v1",
        (),
        {"kind": "CONVERT", "from": [0, 1], "to": [1, 1]},
    ),
    (
        "MOVE_CAPTURE",
        "capture-eliminate-one-sided-b-v1",
        ({"kind": "HOP", "from": [2, 2], "to": [1, 2]},),
        {"kind": "MOVE_CAPTURE", "from": [1, 1], "to": [1, 0]},
    ),
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
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise TypeError("{} must be finite JSON".format(label)) from error


def _validate_json_tree(value: Any, path: str = "benchmark") -> None:
    active_container_ids = set()
    visited_nodes = 0
    text_characters = 0
    stack = [("visit", value, path, 0)]
    while stack:
        operation, current, current_path, depth = stack.pop()
        if operation == "leave":
            active_container_ids.remove(id(current))
            continue

        visited_nodes += 1
        if visited_nodes > _MAX_VALIDATION_NODES_V1:
            raise ValueError(
                "{} exceeds the fixed JSON node limit".format(path)
            )
        if depth > _MAX_VALIDATION_DEPTH_V1:
            raise ValueError(
                "{} exceeds the fixed JSON depth limit".format(path)
            )
        if current is None or type(current) is bool:
            continue
        if type(current) is int:
            if current.bit_length() > _MAX_VALIDATION_INTEGER_BITS_V1:
                raise ValueError(
                    "{} exceeds the fixed integer bit limit".format(path)
                )
            continue
        if type(current) is str:
            if len(current) > _MAX_VALIDATION_SINGLE_STRING_CHARACTERS_V1:
                raise ValueError(
                    "{} exceeds the fixed string limit".format(path)
                )
            text_characters += len(current)
            if text_characters > _MAX_VALIDATION_TEXT_CHARACTERS_V1:
                raise ValueError(
                    "{} exceeds the fixed text limit".format(path)
                )
            continue
        if type(current) not in (list, dict):
            raise TypeError(
                "{} must contain exact finite JSON values".format(current_path)
            )
        if len(current) > _MAX_VALIDATION_NODES_V1 - visited_nodes:
            raise ValueError(
                "{} exceeds the fixed JSON node limit".format(path)
            )

        container_id = id(current)
        if container_id in active_container_ids:
            raise ValueError("{} contains a JSON cycle".format(path))
        active_container_ids.add(container_id)
        stack.append(("leave", current, current_path, depth))
        if type(current) is list:
            for index in range(len(current) - 1, -1, -1):
                stack.append(
                    (
                        "visit",
                        current[index],
                        path,
                        depth + 1,
                    )
                )
        else:
            items = list(current.items())
            for key, child in reversed(items):
                if type(key) is not str:
                    raise TypeError(
                        "{} keys must be exact strings".format(current_path)
                    )
                if len(key) > _MAX_VALIDATION_SINGLE_STRING_CHARACTERS_V1:
                    raise ValueError(
                        "{} exceeds the fixed key limit".format(path)
                    )
                text_characters += len(key)
                if text_characters > _MAX_VALIDATION_TEXT_CHARACTERS_V1:
                    raise ValueError(
                        "{} exceeds the fixed text limit".format(path)
                    )
                stack.append(
                    ("visit", child, path, depth + 1)
                )


def _seal_json_input(value: Any, label: str) -> bytes:
    _validate_json_tree(value, label)
    try:
        sealed = _canonical_bytes(value)
    except (TypeError, ValueError, RecursionError) as error:
        raise TypeError("{} must be finite JSON".format(label)) from error
    if len(sealed) > _MAX_VALIDATION_CANONICAL_BYTES_V1:
        raise ValueError("{} exceeds the fixed canonical byte limit".format(label))
    return sealed


def _fixture_definitions_v1() -> Tuple[Tuple[str, str, GameDefinition], ...]:
    parent_identities = {
        fixture_id: (exact_hash, d4_hash, canonical_byte_count)
        for (
            fixture_id,
            exact_hash,
            d4_hash,
            canonical_byte_count,
        ) in PLAN0012_SYNTHETIC_FIXTURE_IDENTITIES_V1
    }
    records = []
    for fixture_id, provenance, encoded in _FIXTURE_SPECS_V1:
        raw = json.loads(encoded)
        definition = parse_definition(raw)
        if canonical_json(definition) != encoded:
            raise AssertionError("fixture {} is not canonical".format(fixture_id))
        expected = _EXPECTED_FIXTURE_GOLDENS_V1[fixture_id]
        observed_identity = (
            definition_hash(definition),
            d4_canonical_hash(definition),
            len(encoded.encode("utf-8")),
        )
        if observed_identity != (
            expected["definition_hash"],
            expected["d4_hash"],
            expected["canonical_byte_count"],
        ):
            raise AssertionError("fixture {} identity drifted".format(fixture_id))
        if provenance == "PLAN0012_SYNTHETIC_REUSE":
            if parent_identities.get(fixture_id) != observed_identity:
                raise AssertionError(
                    "fixture {} does not match Plan-0012 identity evidence".format(
                        fixture_id
                    )
                )
        elif provenance == "PLAN0013_SYNTHETIC_ADDITION":
            parent_exact_hashes = {
                identity[0] for identity in parent_identities.values()
            }
            parent_d4_hashes = {
                identity[1] for identity in parent_identities.values()
            }
            if (
                fixture_id in parent_identities
                or observed_identity[0] in parent_exact_hashes
                or observed_identity[1] in parent_d4_hashes
            ):
                raise AssertionError(
                    "new fixture {} collides with Plan-0012 evidence".format(
                        fixture_id
                    )
                )
        else:
            raise AssertionError("fixture provenance is not frozen")
        records.append((fixture_id, provenance, definition))
    if tuple(item[0] for item in records) != tuple(
        sorted(_EXPECTED_FIXTURE_GOLDENS_V1)
    ):
        raise AssertionError("fixture registry order or membership drifted")
    return tuple(records)


def _action_from_record(
    definition: GameDefinition, state: GameState, record: Mapping[str, Any]
) -> Action:
    matches = tuple(
        action for action in legal_actions(definition, state)
        if action.to_dict() == dict(record)
    )
    if len(matches) != 1:
        raise AssertionError("dynamic witness action is not uniquely legal")
    return matches[0]


def _transform_action_dict(
    action: Mapping[str, Any], board_size: int, transform: str
) -> Dict[str, Any]:
    result: Dict[str, Any] = {"kind": action["kind"]}
    if "from" in action:
        result["from"] = list(
            transform_position(tuple(action["from"]), board_size, transform)
        )
    result["to"] = list(
        transform_position(tuple(action["to"]), board_size, transform)
    )
    return result


def _ordered_action_values(
    values: Sequence[Tuple[Action, int]]
) -> List[Dict[str, Any]]:
    return [
        {"action": action.to_dict(), "value_for_a": value}
        for action, value in values
    ]


def _root_value(
    player: Player, action_values: Sequence[Tuple[Action, int]]
) -> int:
    values = tuple(value for _, value in action_values)
    return max(values) if player is Player.A else min(values)


def _run_search(
    definition: GameDefinition, depth: int, seed: int
) -> Dict[str, Any]:
    agent = TerminalOnlyMinimaxAgent(
        depth=depth,
        max_total_nodes=ATLAS_AGENT_BENCHMARK_SEARCH_CAP_V1,
    )
    state = initial_state(definition)
    actions = legal_actions(definition, state)
    rng = random.Random(seed)
    rng_before = rng.getstate()
    selected = agent.select_action(definition, state, actions, rng)
    action_values = agent.last_action_values
    if (
        agent.last_expanded_nodes is None
        or agent.last_cache_hits is None
        or not action_values
    ):
        raise AssertionError("terminal-only search did not retain evidence")
    value = _root_value(state.to_move, action_values)
    best = tuple(
        action for action, action_value in action_values if action_value == value
    )
    return {
        "agent_identity": agent.identity.key,
        "depth": depth,
        "seed": seed,
        "selected_action": selected.to_dict(),
        "action_values": _ordered_action_values(action_values),
        "best_actions": [action.to_dict() for action in best],
        "value_for_a": value,
        "expanded_nodes": agent.last_expanded_nodes,
        "cache_hits": agent.last_cache_hits,
        "total_nodes": agent.total_nodes,
        "rng_advanced": rng.getstate() != rng_before,
    }


def _exact_summary(result: Any) -> Dict[str, Any]:
    return {
        "value_for_a": result.value_for_a,
        "forced_result": result.forced_result,
        "principal_variation": [
            action.to_dict() for action in result.principal_variation
        ],
        "principal_variation_plies": len(result.principal_variation),
        "terminal_reason": result.terminal_reason,
        "searched_states": result.searched_states,
        "cache_hits": result.cache_hits,
    }


def _run_random_self_play(
    definition: GameDefinition,
    seed: int,
    agents: Mapping[Player, RandomAgent],
) -> Dict[str, Any]:
    if type(agents) is not dict or set(agents) != {Player.A, Player.B}:
        raise AssertionError("random role-agent slot mapping drifted")
    if agents[Player.A] is agents[Player.B]:
        raise AssertionError("random role agents must be fresh distinct instances")
    if any(type(agent) is not RandomAgent for agent in agents.values()):
        raise AssertionError("random role-agent slot type drifted")
    if (
        agents[Player.A].identity.key != "random-v1-weak"
        or agents[Player.B].identity.key != "random-v1-weak"
    ):
        raise AssertionError("random-v1 identity drifted")

    state = initial_state(definition)
    rng = random.Random(seed)
    trace = []
    while not state.terminal:
        actions = legal_actions(definition, state)
        if not actions:
            raise AssertionError("nonterminal benchmark state has no legal action")
        actor = state.to_move
        selected = agents[actor].select_action(definition, state, actions, rng)
        if type(selected) is not Action or selected not in actions:
            raise AssertionError("random-v1 selected an illegal action")
        trace.append(
            {
                "ply": state.ply,
                "actor": actor.value,
                "legal_action_count": len(actions),
                "selected_action": selected.to_dict(),
            }
        )
        state = apply_action(definition, state, selected)
    if state.outcome is None:
        raise AssertionError("random-v1 benchmark game did not terminate")
    return {
        "seed": seed,
        "agent_a": agents[Player.A].identity.key,
        "agent_b": agents[Player.B].identity.key,
        "trace": trace,
        "plies": len(trace),
        "winner": (
            state.outcome.winner.value
            if state.outcome.winner is not None
            else None
        ),
        "terminal_reason": state.outcome.reason,
    }


def _build_random_conformance(
    fixtures: Sequence[Tuple[str, str, GameDefinition]]
) -> Dict[str, Any]:
    games = []
    terminal_reasons: Dict[str, int] = {}
    outcomes = {"A_WIN": 0, "B_WIN": 0, "DRAW": 0}
    for fixture_id, _, base in fixtures:
        for transform in D4_TRANSFORMS:
            definition = transform_definition(base, transform)
            primary_agents = {Player.A: RandomAgent(), Player.B: RandomAgent()}
            replay_agents = {Player.A: RandomAgent(), Player.B: RandomAgent()}
            for seed in range(8):
                first = _run_random_self_play(
                    definition, seed, primary_agents
                )
                second = _run_random_self_play(
                    definition, seed, replay_agents
                )
                if first != second:
                    raise AssertionError("random-v1 seeded replay drifted")
                outcome_key = (
                    "DRAW" if first["winner"] is None
                    else "{}_WIN".format(first["winner"])
                )
                outcomes[outcome_key] += 1
                reason = first["terminal_reason"]
                terminal_reasons[reason] = terminal_reasons.get(reason, 0) + 1
                games.append(
                    {
                        "fixture_id": fixture_id,
                        "transform": transform,
                        "transformed_definition_hash": definition_hash(
                            definition
                        ),
                        **first,
                    }
                )
    if len(games) != ATLAS_AGENT_BENCHMARK_RANDOM_GAME_COUNT_V1:
        raise AssertionError("random-v1 conformance game count drifted")
    if any(game["plies"] < 1 for game in games):
        raise AssertionError("random-v1 conformance contains an empty game")
    section = {
        "conformance_version": ATLAS_AGENT_BENCHMARK_VERSION_V1,
        "status": "COMPLETE_SYNTHETIC_RANDOM_SELF_PLAY",
        "agent_identity": "random-v1-weak",
        "fixture_count": len(fixtures),
        "d4_orientation_count": len(D4_TRANSFORMS),
        "seeds": list(range(8)),
        "game_count": len(games),
        "role_slot_count": len(fixtures) * len(D4_TRANSFORMS) * 2,
        "fresh_role_instances_per_definition_orientation": 2,
        "agent_reuse_scope": "ordered-seeds-0-through-7",
        "reset_policy": "UNSUPPORTED_STATELESS_AGENT",
        "shared_rng_stream_per_game": True,
        "seeded_replay_count": len(games),
        "seeded_replay_mismatch_count": 0,
        "illegal_selection_count": 0,
        "unterminated_game_count": 0,
        "synthetic_outcome_counts": outcomes,
        "terminal_reason_counts": {
            key: terminal_reasons[key] for key in sorted(terminal_reasons)
        },
        "ordered_games": games,
    }
    section["random_conformance_root"] = _digest(
        _RANDOM_ROOT_DOMAIN_V1, section
    )
    return section


def _run_terminal_self_play(
    definition: GameDefinition,
    seed: int,
    agents: Mapping[Player, TerminalOnlyMinimaxAgent],
) -> Dict[str, Any]:
    if type(agents) is not dict or set(agents) != {Player.A, Player.B}:
        raise AssertionError("terminal role-agent slot mapping drifted")
    if agents[Player.A] is agents[Player.B]:
        raise AssertionError("terminal role agents must be distinct instances")
    if any(
        type(agent) is not TerminalOnlyMinimaxAgent
        or agent.identity.key != "terminal_only_minimax-v1-depth1"
        or agent.max_total_nodes != ATLAS_AGENT_PRODUCTION_DEPTH1_NODE_CAP_V1
        for agent in agents.values()
    ):
        raise AssertionError("terminal role-agent slot contract drifted")

    state = initial_state(definition)
    rng = random.Random(seed)
    trace = []
    while not state.terminal:
        actions = legal_actions(definition, state)
        if not actions:
            raise AssertionError("nonterminal benchmark state has no legal action")
        actor = state.to_move
        agent = agents[actor]
        nodes_before = agent.total_nodes
        selected = agent.select_action(definition, state, actions, rng)
        if type(selected) is not Action or selected not in actions:
            raise AssertionError("terminal-only agent selected an illegal action")
        if agent.last_expanded_nodes is None or agent.last_cache_hits is None:
            raise AssertionError("terminal-only lifecycle audit is incomplete")
        trace.append(
            {
                "ply": state.ply,
                "actor": actor.value,
                "legal_action_count": len(actions),
                "selected_action": selected.to_dict(),
                "expanded_nodes": agent.last_expanded_nodes,
                "cache_hits": agent.last_cache_hits,
                "slot_nodes_before": nodes_before,
                "slot_nodes_after": agent.total_nodes,
            }
        )
        state = apply_action(definition, state, selected)
    if state.outcome is None:
        raise AssertionError("terminal-only benchmark game did not terminate")
    return {
        "seed": seed,
        "agent_a": agents[Player.A].identity.key,
        "agent_b": agents[Player.B].identity.key,
        "trace": trace,
        "plies": len(trace),
        "winner": (
            state.outcome.winner.value
            if state.outcome.winner is not None
            else None
        ),
        "terminal_reason": state.outcome.reason,
    }


def _fresh_terminal_role_slots() -> Dict[Player, TerminalOnlyMinimaxAgent]:
    agents = {
        player: TerminalOnlyMinimaxAgent(
            depth=1,
            max_total_nodes=ATLAS_AGENT_PRODUCTION_DEPTH1_NODE_CAP_V1,
        )
        for player in (Player.A, Player.B)
    }
    for agent in agents.values():
        agent.reset_budget()
    return agents


def _build_terminal_lifecycle_conformance(
    fixtures: Sequence[Tuple[str, str, GameDefinition]]
) -> Dict[str, Any]:
    games = []
    role_slots = []
    terminal_reasons: Dict[str, int] = {}
    outcomes = {"A_WIN": 0, "B_WIN": 0, "DRAW": 0}
    for fixture_id, _, base in fixtures:
        for transform in D4_TRANSFORMS:
            definition = transform_definition(base, transform)
            primary_agents = _fresh_terminal_role_slots()
            replay_agents = _fresh_terminal_role_slots()
            orientation_games = []
            for seed in range(8):
                first = _run_terminal_self_play(
                    definition, seed, primary_agents
                )
                second = _run_terminal_self_play(
                    definition, seed, replay_agents
                )
                if first != second:
                    raise AssertionError(
                        "terminal-only seeded slot replay drifted"
                    )
                outcome_key = (
                    "DRAW" if first["winner"] is None
                    else "{}_WIN".format(first["winner"])
                )
                outcomes[outcome_key] += 1
                reason = first["terminal_reason"]
                terminal_reasons[reason] = terminal_reasons.get(reason, 0) + 1
                orientation_games.append(first)
                games.append(
                    {
                        "fixture_id": fixture_id,
                        "transform": transform,
                        "transformed_definition_hash": definition_hash(
                            definition
                        ),
                        **first,
                    }
                )
            for player in (Player.A, Player.B):
                primary = primary_agents[player]
                replay = replay_agents[player]
                controlled_turns = sum(
                    trace["actor"] == player.value
                    for game in orientation_games
                    for trace in game["trace"]
                )
                if (
                    primary.total_nodes != replay.total_nodes
                    or primary.total_nodes
                    > ATLAS_AGENT_PRODUCTION_DEPTH1_NODE_CAP_V1
                ):
                    raise AssertionError(
                        "terminal-only cumulative role-slot budget drifted"
                    )
                role_slots.append(
                    {
                        "fixture_id": fixture_id,
                        "transform": transform,
                        "role": player.value,
                        "agent_identity": primary.identity.key,
                        "ordered_seeds": list(range(8)),
                        "reset_count": 1,
                        "completed_game_count": 8,
                        "controlled_turn_count": controlled_turns,
                        "total_expanded_nodes": primary.total_nodes,
                        "max_total_nodes": primary.max_total_nodes,
                    }
                )
    if len(games) != ATLAS_AGENT_BENCHMARK_TERMINAL_GAME_COUNT_V1:
        raise AssertionError("terminal-only conformance game count drifted")
    if any(game["plies"] < 1 for game in games):
        raise AssertionError("terminal-only conformance contains an empty game")
    if len(role_slots) != len(fixtures) * len(D4_TRANSFORMS) * 2:
        raise AssertionError("terminal-only role-slot count drifted")
    section = {
        "conformance_version": ATLAS_AGENT_BENCHMARK_VERSION_V1,
        "status": "COMPLETE_SYNTHETIC_TERMINAL_ONLY_SELF_PLAY",
        "agent_identity": "terminal_only_minimax-v1-depth1",
        "fixture_count": len(fixtures),
        "d4_orientation_count": len(D4_TRANSFORMS),
        "seeds": list(range(8)),
        "game_count": len(games),
        "role_slot_count": len(role_slots),
        "fresh_role_instances_per_definition_orientation": 2,
        "agent_reuse_scope": "ordered-seeds-0-through-7",
        "reset_count_per_role_slot": 1,
        "shared_rng_stream_per_game": True,
        "seeded_slot_replay_count": len(games),
        "seeded_slot_replay_mismatch_count": 0,
        "budget_censored_slot_count": 0,
        "illegal_selection_count": 0,
        "unterminated_game_count": 0,
        "synthetic_outcome_counts": outcomes,
        "terminal_reason_counts": {
            key: terminal_reasons[key] for key in sorted(terminal_reasons)
        },
        "ordered_role_slots": role_slots,
        "ordered_games": games,
    }
    section["terminal_conformance_root"] = _digest(
        _TERMINAL_LIFECYCLE_ROOT_DOMAIN_V1, section
    )
    return section


def _search_summary_for_slot(
    definition: GameDefinition, depth: int
) -> Dict[str, Any]:
    first = _run_search(definition, depth, 0)
    second = _run_search(definition, depth, 1)
    stable_keys = (
        "agent_identity",
        "depth",
        "action_values",
        "best_actions",
        "value_for_a",
        "expanded_nodes",
        "cache_hits",
        "total_nodes",
    )
    if any(first[key] != second[key] for key in stable_keys):
        raise AssertionError("seed changed deterministic search evidence")
    return {
        key: first[key]
        for key in stable_keys
    } | {
        "selections": [
            {
                "seed": record["seed"],
                "selected_action": record["selected_action"],
                "rng_advanced": record["rng_advanced"],
            }
            for record in (first, second)
        ]
    }


def _validate_base_golden(
    fixture_id: str,
    exact: Mapping[str, Any],
    searches: Sequence[Mapping[str, Any]],
) -> None:
    expected = _EXPECTED_FIXTURE_GOLDENS_V1[fixture_id]
    exact_tuple = (
        exact["forced_result"],
        exact["terminal_reason"],
        exact["principal_variation_plies"],
        exact["searched_states"],
        exact["cache_hits"],
    )
    if exact_tuple != expected["exact"]:
        raise AssertionError("fixture {} exact oracle drifted".format(fixture_id))
    for search in searches:
        scores = tuple(
            row["value_for_a"] for row in search["action_values"]
        )
        observed = (
            search["value_for_a"],
            search["expanded_nodes"],
            scores,
        )
        if observed != expected["depth{}".format(search["depth"])]:
            raise AssertionError(
                "fixture {} depth {} oracle drifted".format(
                    fixture_id, search["depth"]
                )
            )


def _action_value_map(rows: Iterable[Mapping[str, Any]]) -> Dict[str, int]:
    return {
        _canonical_bytes(row["action"]).decode("utf-8"): row["value_for_a"]
        for row in rows
    }


def _transformed_action_value_map(
    rows: Iterable[Mapping[str, Any]], board_size: int, transform: str
) -> Dict[str, int]:
    return {
        _canonical_bytes(
            _transform_action_dict(row["action"], board_size, transform)
        ).decode("utf-8"): row["value_for_a"]
        for row in rows
    }


def _build_fixture_section(
    fixtures: Sequence[Tuple[str, str, GameDefinition]]
) -> Dict[str, Any]:
    rows = []
    for fixture_id, provenance, definition in fixtures:
        encoded = canonical_json(definition)
        rows.append(
            {
                "fixture_id": fixture_id,
                "provenance": provenance,
                "definition": json.loads(encoded),
                "canonical_byte_count": len(encoded.encode("utf-8")),
                "definition_hash": definition_hash(definition),
                "d4_hash": d4_canonical_hash(definition),
            }
        )
    section = {
        "fixture_version": ATLAS_AGENT_BENCHMARK_VERSION_V1,
        "plan0012_synthetic_benchmark_parent_root": (
            PLAN0012_SYNTHETIC_BENCHMARK_ROOT_V1
        ),
        "plan0012_synthetic_identity_projection_root": (
            ATLAS_SYNTHETIC_PROJECTION_ROOT_V1
        ),
        "fixture_count": len(rows),
        "reused_fixture_count": sum(
            row["provenance"] == "PLAN0012_SYNTHETIC_REUSE" for row in rows
        ),
        "new_fixture_count": sum(
            row["provenance"] == "PLAN0013_SYNTHETIC_ADDITION" for row in rows
        ),
        "fixtures": rows,
    }
    section["fixture_root"] = _digest(_FIXTURE_ROOT_DOMAIN_V1, section)
    return section


def _build_ladder_section() -> Dict[str, Any]:
    shared_protocol = {
        "canonical_legal_action_order": "engine-action-sort-key-v1",
        "ordered_d4_orientations": list(D4_TRANSFORMS),
        "ordered_seeds": list(range(8)),
        "ordered_roles": ["A", "B"],
        "fresh_agent_scope": "definition-orientation-strength-role-slot",
        "agent_reuse_within_slot": "ordered-seeds-0-through-7-only",
        "agent_reuse_outside_slot": False,
        "rng_scope": "fresh-random.Random(seed)-per-complete-game",
        "rng_stream": "one-stream-shared-by-both-roles-in-ply-order",
        "reset_policy": "once-before-fixed-seed-sequence-when-supported",
    }
    terminal_contract = {
        "algorithm_family": "terminal_only_minimax",
        "algorithm_version": 1,
        "terminal_utility_for_a": {
            "A_WIN": 1,
            "B_WIN": -1,
            "DRAW": 0,
        },
        "nonterminal_cutoff_value_for_a": 0,
        "node_choice_by_player": {"A": "MAX", "B": "MIN"},
        "maximum_supported_depth": TERMINAL_ONLY_MINIMAX_MAX_DEPTH,
        "canonical_root_action_order": "engine-action-sort-key-v1",
        "cache_scope": "one-select-action-call",
        "cache_key": ["game_state", "remaining_depth"],
        "expanded_node_unit": "one-cache-miss-successor-state-root-excluded",
        "budget_check": "before-cache-miss-expansion",
        "budget_scope": "per-slot-cumulative",
        "tie_policy": "one-seeded-randrange-over-canonical-best-actions",
        "unique_best_rng_consumption": 0,
    }
    production = {
        "status": "RANDOM_AND_DEPTH1_AUTHORIZED_PRE_OUTCOME",
        "ordered_strengths": [
            {
                "identity": "random-v1-weak",
                "agent_family": "random",
                "agent_version": 1,
                "strength": "weak",
                "selection_policy": (
                    "one-randrange-over-canonical-legal-actions"
                ),
            },
            {
                "identity": "terminal_only_minimax-v1-depth1",
                "agent_family": "terminal_only_minimax",
                "agent_version": 1,
                "strength": "depth1",
                "depth": 1,
                "max_total_nodes_per_slot": (
                    ATLAS_AGENT_PRODUCTION_DEPTH1_NODE_CAP_V1
                ),
            }
        ],
        "slot_seed_count": 8,
        "controlled_turn_bound_per_game": 9,
        "action_candidate_bound_per_turn": 48,
        "terminal_depth1_bound_formula": "8*9*48",
        "random_node_budget": "NOT_APPLICABLE",
    }
    diagnostic = {
        "benchmark_probe_depths": [1, 2],
        "isolated_selection_scope": "fresh-agent-per-seed-probe",
        "benchmark_max_total_nodes": ATLAS_AGENT_BENCHMARK_SEARCH_CAP_V1,
        "depth2_status": "CONFORMANCE_ONLY_NOT_AUTHORIZED_FOR_ATLAS",
        "depth2_structural_node_bound_per_slot": (
            ATLAS_AGENT_DIAGNOSTIC_DEPTH2_NODE_BOUND_V1
        ),
        "depth2_bound_formula": "8*9*(48+48*48)",
    }
    section = {
        "ladder_version": ATLAS_AGENT_BENCHMARK_VERSION_V1,
        "shared_sampled_protocol": shared_protocol,
        "terminal_only_minimax_contract": terminal_contract,
        "production_ladder": production,
        "diagnostic_conformance": diagnostic,
    }
    section["ladder_root"] = _digest(_LADDER_ROOT_DOMAIN_V1, section)
    return section


def _build_d4_evidence(
    fixtures: Sequence[Tuple[str, str, GameDefinition]]
) -> List[Dict[str, Any]]:
    slots = []
    base_by_fixture: Dict[str, Dict[str, Any]] = {}
    for fixture_id, _, base in fixtures:
        expected = _EXPECTED_FIXTURE_GOLDENS_V1[fixture_id]
        for transform in D4_TRANSFORMS:
            definition = transform_definition(base, transform)
            if d4_canonical_hash(definition) != expected["d4_hash"]:
                raise AssertionError("fixture D4 identity drifted")
            exact = _exact_summary(solve_game(definition))
            searches = [
                _search_summary_for_slot(definition, depth)
                for depth in (1, 2)
            ]
            slot = {
                "fixture_id": fixture_id,
                "transform": transform,
                "transformed_definition_hash": definition_hash(definition),
                "d4_hash": d4_canonical_hash(definition),
                "exact": exact,
                "search": searches,
            }
            if transform == "I":
                _validate_base_golden(fixture_id, exact, searches)
                base_by_fixture[fixture_id] = slot
            else:
                baseline = base_by_fixture[fixture_id]
                invariant_exact_keys = (
                    "value_for_a",
                    "forced_result",
                    "principal_variation_plies",
                    "terminal_reason",
                    "searched_states",
                    "cache_hits",
                )
                if any(
                    exact[key] != baseline["exact"][key]
                    for key in invariant_exact_keys
                ):
                    raise AssertionError("exact D4 oracle drifted")
                if fixture_id != "convert-immediate-reconvergence-v1":
                    transformed_pv = [
                        _transform_action_dict(
                            action, base.board_size, transform
                        )
                        for action in baseline["exact"]["principal_variation"]
                    ]
                    if transformed_pv != exact["principal_variation"]:
                        raise AssertionError("unique exact PV is not D4-covariant")
                for search, base_search in zip(
                    searches, baseline["search"]
                ):
                    invariant_search_keys = (
                        "agent_identity",
                        "depth",
                        "value_for_a",
                        "expanded_nodes",
                        "cache_hits",
                        "total_nodes",
                    )
                    if any(
                        search[key] != base_search[key]
                        for key in invariant_search_keys
                    ):
                        raise AssertionError("search D4 scalar oracle drifted")
                    expected_map = _transformed_action_value_map(
                        base_search["action_values"],
                        base.board_size,
                        transform,
                    )
                    if _action_value_map(search["action_values"]) != expected_map:
                        raise AssertionError("search action values are not D4-covariant")
            slots.append(slot)
    if len(slots) != ATLAS_AGENT_BENCHMARK_D4_SLOT_COUNT_V1:
        raise AssertionError("D4 benchmark slot count drifted")
    return slots


def _build_dynamic_coverage(
    fixtures: Sequence[Tuple[str, str, GameDefinition]]
) -> Dict[str, Any]:
    definitions = {fixture_id: definition for fixture_id, _, definition in fixtures}
    action_witnesses = []
    for kind, fixture_id, prefix_records, action_record in (
        _DYNAMIC_ACTION_WITNESSES_V1
    ):
        definition = definitions[fixture_id]
        state = initial_state(definition)
        prefix = []
        for record in prefix_records:
            action = _action_from_record(definition, state, record)
            prefix.append(action.to_dict())
            state = apply_action(definition, state, action)
        action = _action_from_record(definition, state, action_record)
        after = apply_action(definition, state, action)
        action_witnesses.append(
            {
                "action_kind": kind,
                "fixture_id": fixture_id,
                "prefix": prefix,
                "action": action.to_dict(),
                "before_pieces": [piece.to_dict() for piece in state.pieces],
                "after_pieces": [piece.to_dict() for piece in after.pieces],
                "outcome": (
                    after.outcome.to_dict() if after.outcome is not None else None
                ),
            }
        )
    observed_actions = sorted(row["action_kind"] for row in action_witnesses)
    expected_actions = sorted(
        ("PUSH", "SWAP", "HOP", "CONVERT", "MOVE_CAPTURE")
    )
    if observed_actions != expected_actions:
        raise AssertionError("dynamic action coverage drifted")

    goal_witness_specs = (
        (
            "REACH_EDGE",
            "push-win-draw-loss-v1",
            (),
            {"kind": "PUSH", "from": [1, 1], "to": [2, 1]},
            Player.A,
        ),
        (
            "CONNECT_EDGES",
            "swap-simultaneous-connect-v1",
            (),
            {"kind": "SWAP", "from": [1, 0], "to": [1, 1]},
            Player.A,
        ),
        (
            "ELIMINATE",
            "capture-eliminate-one-sided-b-v1",
            ({"kind": "HOP", "from": [2, 2], "to": [1, 2]},),
            {"kind": "MOVE_CAPTURE", "from": [1, 1], "to": [1, 0]},
            Player.B,
        ),
    )
    goal_witnesses = []
    for kind, fixture_id, prefix_records, action_record, winner in goal_witness_specs:
        definition = definitions[fixture_id]
        state = initial_state(definition)
        prefix = []
        for record in prefix_records:
            action = _action_from_record(definition, state, record)
            prefix.append(action.to_dict())
            state = apply_action(definition, state, action)
        action = _action_from_record(definition, state, action_record)
        after = apply_action(definition, state, action)
        if (
            after.outcome is None
            or after.outcome.winner is not winner
            or after.outcome.reason != "GOAL"
            or definition.role(winner).goal.kind.value != kind
            or not goal_satisfied(definition, after.pieces, winner)
        ):
            raise AssertionError("dynamic goal coverage drifted")
        goal_witnesses.append(
            {
                "goal_kind": kind,
                "fixture_id": fixture_id,
                "prefix": prefix,
                "action": action.to_dict(),
                "winner": winner.value,
                "terminal_reason": after.outcome.reason,
            }
        )
    if sorted(row["goal_kind"] for row in goal_witnesses) != sorted(
        kind.value for kind in GoalKind
    ):
        raise AssertionError("dynamic goal-kind coverage is incomplete")

    push = definitions["push-win-draw-loss-v1"]
    push_state = initial_state(push)
    push_loss = apply_action(
        push,
        push_state,
        _action_from_record(
            push,
            push_state,
            {"kind": "PUSH", "from": [0, 0], "to": [1, 0]},
        ),
    )
    swap = definitions["swap-simultaneous-connect-v1"]
    swap_state = initial_state(swap)
    swap_both = apply_action(
        swap,
        swap_state,
        _action_from_record(
            swap,
            swap_state,
            {"kind": "SWAP", "from": [1, 0], "to": [1, 1]},
        ),
    )
    if (
        push_loss.outcome is None
        or push_loss.outcome.winner is not Player.B
        or goal_satisfied(push, push_loss.pieces, Player.A)
        or not goal_satisfied(push, push_loss.pieces, Player.B)
    ):
        raise AssertionError("opponent-priority witness drifted")
    if (
        swap_both.outcome is None
        or swap_both.outcome.winner is not Player.A
        or not goal_satisfied(swap, swap_both.pieces, Player.A)
        or not goal_satisfied(swap, swap_both.pieces, Player.B)
    ):
        raise AssertionError("actor-priority witness drifted")

    side_swap = _action_from_record(
        swap,
        swap_state,
        {"kind": "SWAP", "from": [0, 1], "to": [0, 2]},
    )
    b_state = apply_action(swap, swap_state, side_swap)
    b_actions = legal_actions(swap, b_state)
    b_agent = TerminalOnlyMinimaxAgent(depth=1, max_total_nodes=4)
    b_rng = random.Random(0)
    b_rng_before = b_rng.getstate()
    b_selected = b_agent.select_action(swap, b_state, b_actions, b_rng)
    recursive_agent = TerminalOnlyMinimaxAgent(depth=2, max_total_nodes=11)
    recursive_agent.select_action(
        swap, swap_state, legal_actions(swap, swap_state), random.Random(0)
    )
    b_values = _ordered_action_values(b_agent.last_action_values)
    recursive_values = _ordered_action_values(
        recursive_agent.last_action_values
    )
    if (
        b_state.to_move is not Player.B
        or [row["value_for_a"] for row in b_values] != [0, -1, 0, 0]
        or b_selected.to_dict()
        != {"kind": "MOVE_CAPTURE", "from": [1, 1], "to": [1, 0]}
        or b_rng.getstate() != b_rng_before
        or [row["value_for_a"] for row in recursive_values]
        != [-1, 1, -1]
    ):
        raise AssertionError("minimizing-player witness drifted")

    return {
        "dynamic_action_kind_count": len(action_witnesses),
        "dynamic_action_kinds": observed_actions,
        "dynamic_action_witnesses": action_witnesses,
        "dynamic_goal_kind_count": len(goal_witnesses),
        "dynamic_goal_kinds": sorted(
            row["goal_kind"] for row in goal_witnesses
        ),
        "dynamic_goal_witnesses": goal_witnesses,
        "terminal_priority_witnesses": [
            {
                "priority": "OPPONENT_GOAL_BEFORE_PLY_LIMIT",
                "fixture_id": "push-win-draw-loss-v1",
                "actor": "A",
                "actor_goal_satisfied": False,
                "opponent_goal_satisfied": True,
                "winner": "B",
            },
            {
                "priority": "ACTOR_GOAL_BEFORE_OPPONENT_GOAL_AND_PLY_LIMIT",
                "fixture_id": "swap-simultaneous-connect-v1",
                "actor": "A",
                "actor_goal_satisfied": True,
                "opponent_goal_satisfied": True,
                "winner": "A",
            },
        ],
        "minimizing_player_witness": {
            "fixture_id": "swap-simultaneous-connect-v1",
            "player": "B",
            "root_prefix": [side_swap.to_dict()],
            "root_action_values": b_values,
            "root_selected_action": b_selected.to_dict(),
            "root_expanded_nodes": b_agent.last_expanded_nodes,
            "root_unique_best_rng_advanced": b_rng.getstate() != b_rng_before,
            "recursive_depth": 2,
            "recursive_root_action_values": recursive_values,
            "recursive_expanded_nodes": recursive_agent.last_expanded_nodes,
        },
    }


def _budget_attempt(
    definition: GameDefinition, depth: int, cap: int, seed: int
) -> Dict[str, Any]:
    agent = TerminalOnlyMinimaxAgent(depth=depth, max_total_nodes=cap)
    state = initial_state(definition)
    rng = random.Random(seed)
    before = rng.getstate()
    try:
        selected = agent.select_action(
            definition, state, legal_actions(definition, state), rng
        )
    except SearchBudgetExceeded as error:
        return {
            "status": "NODE_BUDGET_CENSORED",
            "depth": depth,
            "max_total_nodes": cap,
            "scope": error.scope,
            "visited_nodes": error.visited_nodes,
            "total_nodes": agent.total_nodes,
            "selected_action": None,
            "last_expanded_nodes": agent.last_expanded_nodes,
            "last_cache_hits": agent.last_cache_hits,
            "last_action_value_count": len(agent.last_action_values),
            "rng_advanced": rng.getstate() != before,
        }
    return {
        "status": "COMPLETE",
        "depth": depth,
        "max_total_nodes": cap,
        "scope": None,
        "visited_nodes": None,
        "total_nodes": agent.total_nodes,
        "selected_action": selected.to_dict(),
        "last_expanded_nodes": agent.last_expanded_nodes,
        "last_cache_hits": agent.last_cache_hits,
        "last_action_value_count": len(agent.last_action_values),
        "rng_advanced": rng.getstate() != before,
    }


def _cumulative_capture_attempt(
    definition: GameDefinition, cap: int
) -> Dict[str, Any]:
    agent = TerminalOnlyMinimaxAgent(depth=2, max_total_nodes=cap)
    rng = random.Random(0)
    state = initial_state(definition)
    actions = []
    status = "COMPLETE"
    censor = None
    while not state.terminal:
        try:
            action = agent.select_action(
                definition, state, legal_actions(definition, state), rng
            )
        except SearchBudgetExceeded as error:
            status = "NODE_BUDGET_CENSORED"
            censor = {
                "scope": error.scope,
                "visited_nodes": error.visited_nodes,
                "max_total_nodes": error.max_nodes,
            }
            break
        actions.append(action.to_dict())
        state = apply_action(definition, state, action)
    before_reset = agent.total_nodes
    last_before_reset = {
        "last_expanded_nodes": agent.last_expanded_nodes,
        "last_cache_hits": agent.last_cache_hits,
        "last_action_value_count": len(agent.last_action_values),
    }
    agent.reset_budget()
    return {
        "status": status,
        "depth": 2,
        "max_total_nodes": cap,
        "completed_actions": actions,
        "completed_action_count": len(actions),
        "terminal": state.terminal,
        "outcome": state.outcome.to_dict() if state.outcome is not None else None,
        "censor": censor,
        "total_nodes_before_reset": before_reset,
        **last_before_reset,
        "total_nodes_after_reset": agent.total_nodes,
        "last_expanded_nodes_after_reset": agent.last_expanded_nodes,
        "last_cache_hits_after_reset": agent.last_cache_hits,
        "last_action_value_count_after_reset": len(agent.last_action_values),
    }


def _build_budget_and_tie_evidence(
    fixtures: Sequence[Tuple[str, str, GameDefinition]]
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    definitions = {fixture_id: definition for fixture_id, _, definition in fixtures}
    push = definitions["push-win-draw-loss-v1"]
    capture = definitions["capture-eliminate-one-sided-b-v1"]
    convert = definitions["convert-immediate-reconvergence-v1"]
    budget = {
        "push_depth1_cap2": _budget_attempt(push, 1, 2, 0),
        "push_depth1_cap3": _budget_attempt(push, 1, 3, 0),
        "convert_depth1_cap1": _budget_attempt(convert, 1, 1, 0),
        "capture_depth2_cumulative_cap2": _cumulative_capture_attempt(
            capture, 2
        ),
        "capture_depth2_cumulative_cap3": _cumulative_capture_attempt(
            capture, 3
        ),
    }
    if (
        budget["push_depth1_cap2"]["status"] != "NODE_BUDGET_CENSORED"
        or budget["push_depth1_cap2"]["visited_nodes"] != 2
        or budget["push_depth1_cap2"]["scope"] != "per-slot"
        or budget["push_depth1_cap2"]["rng_advanced"]
        or budget["push_depth1_cap3"]["status"] != "COMPLETE"
        or budget["push_depth1_cap3"]["total_nodes"] != 3
        or budget["convert_depth1_cap1"]["status"] != "COMPLETE"
        or budget["convert_depth1_cap1"]["total_nodes"] != 1
        or budget["capture_depth2_cumulative_cap2"]["completed_action_count"]
        != 1
        or budget["capture_depth2_cumulative_cap2"]["terminal"]
        or budget["capture_depth2_cumulative_cap3"]["completed_action_count"]
        != 2
        or not budget["capture_depth2_cumulative_cap3"]["terminal"]
        or budget["capture_depth2_cumulative_cap3"]["outcome"]
        != {"winner": "B", "reason": "GOAL"}
    ):
        raise AssertionError("node-budget oracle drifted")

    base_seed0 = _run_search(convert, 1, 0)
    base_seed1 = _run_search(convert, 1, 1)
    repeated_seed0 = _run_search(convert, 1, 0)
    rotated = transform_definition(convert, "R90")
    rotated_seed0 = _run_search(rotated, 1, 0)
    transformed_base_selection = _transform_action_dict(
        base_seed0["selected_action"], convert.board_size, "R90"
    )
    unique_push = _run_search(push, 1, 0)
    tie = {
        "fixture_id": "convert-immediate-reconvergence-v1",
        "canonical_best_action_count": 2,
        "seeded_selections": [
            {
                "seed": 0,
                "canonical_best_index": 1,
                "selected_action": base_seed0["selected_action"],
            },
            {
                "seed": 1,
                "canonical_best_index": 0,
                "selected_action": base_seed1["selected_action"],
            },
        ],
        "seed0_repeat_equal": (
            repeated_seed0["selected_action"]
            == base_seed0["selected_action"]
        ),
        "tie_rng_advanced": base_seed0["rng_advanced"],
        "unique_best_fixture_id": "push-win-draw-loss-v1",
        "unique_best_rng_advanced": unique_push["rng_advanced"],
        "orientation_sensitivity": {
            "transform": "R90",
            "transformed_base_selected_action": transformed_base_selection,
            "fresh_transformed_selected_action": rotated_seed0[
                "selected_action"
            ],
            "selection_is_d4_equivariant": (
                transformed_base_selection
                == rotated_seed0["selected_action"]
            ),
            "value_for_a_unchanged": (
                base_seed0["value_for_a"] == rotated_seed0["value_for_a"]
            ),
        },
    }
    if (
        base_seed0["selected_action"]
        != {"kind": "CONVERT", "from": [1, 0], "to": [1, 1]}
        or base_seed1["selected_action"]
        != {"kind": "CONVERT", "from": [0, 1], "to": [1, 1]}
        or not tie["seed0_repeat_equal"]
        or not tie["tie_rng_advanced"]
        or tie["unique_best_rng_advanced"]
        or tie["orientation_sensitivity"]["selection_is_d4_equivariant"]
        or not tie["orientation_sensitivity"]["value_for_a_unchanged"]
    ):
        raise AssertionError("seeded tie oracle drifted")
    return budget, tie


def _build_atlas_separation_section(
    fixtures: Sequence[Tuple[str, str, GameDefinition]]
) -> Dict[str, Any]:
    witnesses = []
    for fixture_id, _, definition in fixtures:
        mismatches = []
        if len(definition.initial_pieces) != 6:
            mismatches.append("initial_piece_count")
        if definition.max_plies != 18:
            mismatches.append("max_plies")
        if mismatches != ["initial_piece_count", "max_plies"]:
            raise AssertionError("fixture is not structurally outside the atlas")
        witnesses.append(
            {
                "fixture_id": fixture_id,
                "fixture_initial_piece_count": len(definition.initial_pieces),
                "fixture_max_plies": definition.max_plies,
                "atlas_initial_piece_count": 6,
                "atlas_max_plies": 18,
                "d4_invariant_mismatch_fields": mismatches,
            }
        )
    section = {
        "proof_version": 1,
        "proof_kind": "D4_INVARIANT_FIELD_SEPARATION",
        "atlas_search_envelope_root": ATLAS_SEARCH_ENVELOPE_ROOT_V1,
        "atlas_paired_universe_witness_root": (
            ATLAS_PAIRED_UNIVERSE_WITNESS_ROOT_V1
        ),
        "atlas_selection_partition_root": ATLAS_SELECTION_PARTITION_ROOT_V1,
        "atlas_development_definition_count": (
            ATLAS_DEVELOPMENT_DEFINITION_COUNT_V1
        ),
        "atlas_candidate_definition_count": (
            ATLAS_CANDIDATE_DEFINITION_COUNT_V1
        ),
        "atlas_definition_contract": {
            "schema_version": 4,
            "board_size": 3,
            "initial_piece_count": 6,
            "max_plies": 18,
        },
        "d4_preserved_fields": [
            "schema_version",
            "board_size",
            "initial_piece_count",
            "max_plies",
        ],
        "fixture_witnesses": witnesses,
        "fixture_exact_collision_count": 0,
        "fixture_d4_collision_count": 0,
        "production_definition_accessed_count": 0,
        "production_outcome_count": 0,
    }
    section["atlas_separation_root"] = _digest(
        _SEPARATION_ROOT_DOMAIN_V1, section
    )
    return section


def _build_benchmark_snapshot_v1() -> Dict[str, Any]:
    fixtures = _fixture_definitions_v1()
    # Prove D4-invariant nonintersection before any exact solve, search, or play.
    separation = _build_atlas_separation_section(fixtures)
    fixture_section = _build_fixture_section(fixtures)
    ladder_section = _build_ladder_section()
    slots = _build_d4_evidence(fixtures)
    random_conformance = _build_random_conformance(fixtures)
    terminal_conformance = _build_terminal_lifecycle_conformance(fixtures)
    dynamic = _build_dynamic_coverage(fixtures)
    budget, tie = _build_budget_and_tie_evidence(fixtures)
    exact_outcomes = {
        "A_WIN": 0,
        "B_WIN": 0,
        "DRAW": 0,
    }
    for slot in slots:
        exact_outcomes[slot["exact"]["forced_result"]] += 1
    if set(exact_outcomes) != {"A_WIN", "B_WIN", "DRAW"} or any(
        count == 0 for count in exact_outcomes.values()
    ):
        raise AssertionError("forced win/loss/draw coverage is incomplete")
    evidence = {
        "evidence_version": ATLAS_AGENT_BENCHMARK_VERSION_V1,
        "d4_slot_count": len(slots),
        "synthetic_exact_outcome_count": len(slots),
        "synthetic_exact_forced_result_counts": exact_outcomes,
        "ordered_d4_slots": slots,
        "random_v1_conformance": random_conformance,
        "terminal_only_lifecycle_conformance": terminal_conformance,
        "dynamic_coverage": dynamic,
        "node_budget_evidence": budget,
        "tie_evidence": tie,
        "production_outcome_count": 0,
    }
    evidence["evidence_root"] = _digest(_EVIDENCE_ROOT_DOMAIN_V1, evidence)
    unsigned = {
        "benchmark_version": ATLAS_AGENT_BENCHMARK_VERSION_V1,
        "benchmark_id": ATLAS_AGENT_BENCHMARK_ID_V1,
        "status": "FROZEN_SYNTHETIC_CONFORMANCE_NO_PRODUCTION_OUTCOME",
        "fixture_section": fixture_section,
        "ladder_section": ladder_section,
        "evidence": evidence,
        "atlas_separation": separation,
        "census": {
            "fixture_count": len(fixtures),
            "d4_slot_count": len(slots),
            "search_depth_count": 2,
            "random_conformance_game_count": random_conformance[
                "game_count"
            ],
            "terminal_conformance_game_count": terminal_conformance[
                "game_count"
            ],
            "terminal_conformance_role_slot_count": terminal_conformance[
                "role_slot_count"
            ],
            "dynamic_action_kind_count": dynamic[
                "dynamic_action_kind_count"
            ],
            "dynamic_goal_kind_count": dynamic["dynamic_goal_kind_count"],
            "production_definition_accessed_count": 0,
            "production_outcome_count": 0,
        },
    }
    unsigned["benchmark_root"] = _digest(
        _BENCHMARK_ROOT_DOMAIN_V1,
        {
            "benchmark_version": unsigned["benchmark_version"],
            "benchmark_id": unsigned["benchmark_id"],
            "status": unsigned["status"],
            "fixture_root": fixture_section["fixture_root"],
            "ladder_root": ladder_section["ladder_root"],
            "evidence_root": evidence["evidence_root"],
            "atlas_separation_root": separation["atlas_separation_root"],
            "census": unsigned["census"],
        },
    )
    return unsigned


def _require_frozen_roots(snapshot: Mapping[str, Any]) -> None:
    checks = (
        (
            "fixture",
            snapshot["fixture_section"]["fixture_root"],
            ATLAS_AGENT_BENCHMARK_FIXTURE_ROOT_V1,
        ),
        (
            "ladder",
            snapshot["ladder_section"]["ladder_root"],
            ATLAS_AGENT_BENCHMARK_LADDER_ROOT_V1,
        ),
        (
            "evidence",
            snapshot["evidence"]["evidence_root"],
            ATLAS_AGENT_BENCHMARK_EVIDENCE_ROOT_V1,
        ),
        (
            "random conformance",
            snapshot["evidence"]["random_v1_conformance"][
                "random_conformance_root"
            ],
            ATLAS_AGENT_BENCHMARK_RANDOM_CONFORMANCE_ROOT_V1,
        ),
        (
            "terminal lifecycle conformance",
            snapshot["evidence"]["terminal_only_lifecycle_conformance"][
                "terminal_conformance_root"
            ],
            ATLAS_AGENT_BENCHMARK_TERMINAL_CONFORMANCE_ROOT_V1,
        ),
        (
            "atlas separation",
            snapshot["atlas_separation"]["atlas_separation_root"],
            ATLAS_AGENT_BENCHMARK_ATLAS_SEPARATION_ROOT_V1,
        ),
        ("benchmark", snapshot["benchmark_root"], ATLAS_AGENT_BENCHMARK_ROOT_V1),
    )
    for label, observed, expected in checks:
        if observed != expected:
            raise ValueError("frozen agent benchmark {} root drifted".format(label))
    canonical_sha = hashlib.sha256(_canonical_bytes(snapshot)).hexdigest()
    if canonical_sha != ATLAS_AGENT_BENCHMARK_CANONICAL_SHA256_V1:
        raise ValueError("frozen agent benchmark canonical SHA-256 drifted")


def build_frozen_atlas_agent_benchmark_v1() -> Dict[str, Any]:
    """Reconstruct the fixed synthetic benchmark without caller capabilities."""

    snapshot = _build_benchmark_snapshot_v1()
    _require_frozen_roots(snapshot)
    return _json_copy(snapshot, "frozen atlas agent benchmark")


def validate_frozen_atlas_agent_benchmark_v1(value: Any) -> Dict[str, Any]:
    """Strictly reconstruct and validate one frozen benchmark snapshot."""

    sealed = _seal_json_input(value, "frozen atlas agent benchmark")
    detached = json.loads(sealed.decode("utf-8"))
    _validate_json_tree(detached, "detached frozen atlas agent benchmark")
    expected = build_frozen_atlas_agent_benchmark_v1()
    if _canonical_bytes(detached) != _canonical_bytes(expected):
        raise ValueError("frozen atlas agent benchmark does not reconstruct")
    if _seal_json_input(value, "frozen atlas agent benchmark") != sealed:
        raise ValueError("frozen atlas agent benchmark changed during validation")
    return _json_copy(expected, "validated frozen atlas agent benchmark")


def canonical_frozen_atlas_agent_benchmark_json_v1(
    value: Optional[Any] = None,
) -> str:
    """Return canonical JSON only for the fixed benchmark version."""

    snapshot = (
        build_frozen_atlas_agent_benchmark_v1()
        if value is None
        else validate_frozen_atlas_agent_benchmark_v1(value)
    )
    return _canonical_bytes(snapshot).decode("utf-8")


__all__ = (
    "ATLAS_AGENT_BENCHMARK_ATLAS_SEPARATION_ROOT_V1",
    "ATLAS_AGENT_BENCHMARK_CANONICAL_SHA256_V1",
    "ATLAS_AGENT_BENCHMARK_D4_SLOT_COUNT_V1",
    "ATLAS_AGENT_BENCHMARK_EVIDENCE_ROOT_V1",
    "ATLAS_AGENT_BENCHMARK_FIXTURE_COUNT_V1",
    "ATLAS_AGENT_BENCHMARK_FIXTURE_ROOT_V1",
    "ATLAS_AGENT_BENCHMARK_ID_V1",
    "ATLAS_AGENT_BENCHMARK_LADDER_ROOT_V1",
    "ATLAS_AGENT_BENCHMARK_RANDOM_CONFORMANCE_ROOT_V1",
    "ATLAS_AGENT_BENCHMARK_RANDOM_GAME_COUNT_V1",
    "ATLAS_AGENT_BENCHMARK_ROOT_V1",
    "ATLAS_AGENT_BENCHMARK_TERMINAL_CONFORMANCE_ROOT_V1",
    "ATLAS_AGENT_BENCHMARK_TERMINAL_GAME_COUNT_V1",
    "ATLAS_AGENT_DIAGNOSTIC_DEPTH2_NODE_BOUND_V1",
    "ATLAS_AGENT_PRODUCTION_DEPTH1_NODE_CAP_V1",
    "build_frozen_atlas_agent_benchmark_v1",
    "canonical_frozen_atlas_agent_benchmark_json_v1",
    "validate_frozen_atlas_agent_benchmark_v1",
)
