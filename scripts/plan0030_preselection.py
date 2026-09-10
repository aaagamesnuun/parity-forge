"""One registered, bounded Plan 0030 four-structure preselection.

The module is deliberately Plan-specific.  It authenticates the frozen cohort,
materializes all 56 slots before computation, and uses only the already accepted
game/exact adapters plus terminal-only search and a small deterministic FIFO
prefix enumerator.  A run is immutable and cannot be resumed or retried.
"""

from __future__ import annotations

import argparse
from collections import Counter, deque
import hashlib
import inspect
import json
from pathlib import Path
import random
import re
import subprocess

from parity_forge.agents import SearchBudgetExceeded
from parity_forge.dsl import Player, canonical_json, definition_hash, parse_definition
from parity_forge.engine import GameState, apply_action, initial_state, legal_actions
from parity_forge.terminal_search import TerminalOnlyMinimaxAgent
from scripts import plan0024_play as play_adapter
from scripts.plan0016_pilot import canonical_bytes, read_json
from scripts.plan0020_pilot import exact_one, _publish, _utc


PLAN = "docs/plans/active/0030-admission-first-four-structure-preselection.md"
DATA = "experiments/proposals/plan0030-four-structure-preselection-v0.json"
DESIGN_DATA = "experiments/proposals/plan0030-design-drafts-v0.json"
PROTOCOL = "plan0030-admission-first-four-structure-preselection-v1"
OUTPUT = "experiments/runs/" + PROTOCOL
PROPOSAL_SHA256 = "d547bc5dee706f2a5480f4f2e8c7ac021e8ba2eec9abbda6fbac2a0ab48fcd15"
PROPOSAL_STATUS = "FIXED_PROSPECTIVE_NOT_REGISTERED_NOT_PRODUCTION_EXECUTED"

MAX_NODES = MAX_STATES = 100000
BFS_STOP = 100001
MAX_ATTEMPTS = 56
MAX_FILES = 118
MAX_BFS_BYTES = 8 * 1024 * 1024
MAX_OTHER_BYTES = 2 * 1024 * 1024
MAX_PUBLISHED_BYTES = 272629760
MAX_ERROR_TYPE_BYTES = 256
MAX_ERROR_MESSAGE_BYTES = 4096
POLICY_ORDER = ("T2_T2", "T3_T3")
POLICY_IDENTITIES = {
    "T2": "terminal_only_minimax-v1-depth2",
    "T3": "terminal_only_minimax-v1-depth3",
}
STAGE_ORDER = (
    "SHORT_FOUR",
    "POLICY_GAMES",
    "EXACT",
    "BFS_PREFIX",
    "SHORT_SEVEN",
)
SHORT_STAGE = {
    "SHORT_FOUR": (4, {"A": 7, "B": 8}),
    "SHORT_SEVEN": (7, {"A": 13, "B": 14}),
}
RESOURCE_CEILINGS = {
    "short_query_misses": 1600000,
    "exact_searched_states": 400000,
    "configured_game_agent_nodes": 6400000,
    "bfs_transitions": 6000060,
    "adapter_internal_replay_transitions": 1584,
    "actual_game_plies": 1408,
    "t2_schedule_structural_nodes": 165120,
    "t3_schedule_structural_nodes": 2487120,
    "combined_schedule_structural_nodes": 2652240,
    "all_game_role_calls_at_t3_conservative_bound": 4974240,
}


def _sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def _bounded_text(value, maximum_bytes):
    text = str(value)
    encoded = text.encode("utf-8")
    if len(encoded) <= maximum_bytes:
        return text, None
    digest = _sha256(encoded)
    suffix = "...[truncated bytes={} sha256={}]".format(len(encoded), digest)
    budget = maximum_bytes - len(suffix.encode("utf-8"))
    prefix = encoded[:budget].decode("utf-8", errors="ignore")
    bounded = prefix + suffix
    if len(bounded.encode("utf-8")) > maximum_bytes:
        raise AssertionError("bounded text exceeds its byte ceiling")
    return bounded, {"original_bytes": len(encoded), "sha256": digest}


def _error(error):
    error_type, type_truncation = _bounded_text(
        type(error).__name__, MAX_ERROR_TYPE_BYTES
    )
    try:
        rendered = str(error)
    except Exception as rendering_error:
        rendered = "<unprintable exception; renderer={}>".format(
            type(rendering_error).__name__
        )
    if not rendered:
        rendered = "<no exception message>"
    message, message_truncation = _bounded_text(
        rendered, MAX_ERROR_MESSAGE_BYTES
    )
    result = {"type": error_type, "message": message}
    if type_truncation is not None:
        result["type_truncated"] = type_truncation
    if message_truncation is not None:
        result["message_truncated"] = message_truncation
    return result


def _source_digest(source):
    return _sha256(canonical_bytes(source))


def source_snapshot(repository, clean=False):
    """Pin every tracked Python file and both authoritative Plan records."""

    repository = Path(repository)

    def git(*arguments):
        return subprocess.check_output(
            ("git", "-C", str(repository), *arguments), text=True
        ).strip()

    if clean and git("status", "--porcelain"):
        raise ValueError("clean registered worktree required")
    tracked = git("ls-files").splitlines()
    required = {PLAN, DATA, DESIGN_DATA}
    paths = sorted(path for path in tracked if path.endswith(".py") or path in required)
    if not required.issubset(paths):
        raise ValueError("active plan and both frozen proposal records must be registered")
    untracked_python = [
        path
        for path in git("ls-files", "--others", "--exclude-standard").splitlines()
        if path.endswith(".py")
    ]
    if untracked_python:
        raise ValueError("untracked Python source")
    return {
        "git_commit": git("rev-parse", "HEAD"),
        "plan": PLAN,
        "proposal": DATA,
        "design_record": DESIGN_DATA,
        "source_sha256": {
            path: _sha256((repository / path).read_bytes()) for path in paths
        },
    }


def _entrypoint_hash(value):
    return _sha256(inspect.getsource(value).encode("utf-8"))


def dependency_snapshot(source):
    """Name every directly reused entry point and its registered source."""

    entries = {
        "scripts.plan0024_play.play_one": (play_adapter.play_one, "scripts/plan0024_play.py"),
        "scripts.plan0020_pilot.exact_one": (exact_one, "scripts/plan0020_pilot.py"),
        "scripts.plan0020_pilot._publish": (_publish, "scripts/plan0020_pilot.py"),
        "scripts.plan0020_pilot._utc": (_utc, "scripts/plan0020_pilot.py"),
        "parity_forge.terminal_search.TerminalOnlyMinimaxAgent": (
            TerminalOnlyMinimaxAgent,
            "src/parity_forge/terminal_search.py",
        ),
        "parity_forge.engine.initial_state": (initial_state, "src/parity_forge/engine.py"),
        "parity_forge.engine.legal_actions": (legal_actions, "src/parity_forge/engine.py"),
        "parity_forge.engine.apply_action": (apply_action, "src/parity_forge/engine.py"),
        "parity_forge.dsl.parse_definition": (parse_definition, "src/parity_forge/dsl.py"),
        "parity_forge.dsl.canonical_json": (canonical_json, "src/parity_forge/dsl.py"),
        "parity_forge.dsl.definition_hash": (definition_hash, "src/parity_forge/dsl.py"),
        "scripts.plan0016_pilot.read_json": (read_json, "scripts/plan0016_pilot.py"),
        "scripts.plan0016_pilot.canonical_bytes": (
            canonical_bytes,
            "scripts/plan0016_pilot.py",
        ),
        "parity_forge.agents.SearchBudgetExceeded": (
            SearchBudgetExceeded,
            "src/parity_forge/agents.py",
        ),
        "parity_forge.dsl.Player": (Player, "src/parity_forge/dsl.py"),
        "parity_forge.engine.GameState": (GameState, "src/parity_forge/engine.py"),
    }
    pins = source.get("source_sha256")
    if type(pins) is not dict:
        raise ValueError("source snapshot lacks file pins")
    result = {}
    for name, (value, path) in entries.items():
        if path not in pins:
            raise ValueError("direct dependency is absent from source pins: " + path)
        result[name] = {
            "path": path,
            "file_sha256": pins[path],
            "entrypoint_sha256": _entrypoint_hash(value),
        }
    return result


def load_proposal(repository):
    """Authenticate and statically parse the exact frozen prospective cohort."""

    repository = Path(repository)
    raw_bytes = (repository / DATA).read_bytes()
    if _sha256(raw_bytes) != PROPOSAL_SHA256:
        raise ValueError("frozen Plan0030 proposal bytes differ")
    proposal = json.loads(raw_bytes)
    if (
        type(proposal) is not dict
        or proposal.get("status") != PROPOSAL_STATUS
        or proposal.get("registration_status") != "NOT_REGISTERED"
        or proposal.get("production_count") != 0
        or proposal.get("protocol_id") != PROTOCOL
        or proposal.get("policy_order") != list(POLICY_ORDER)
        or proposal.get("stage_order") != list(STAGE_ORDER)
    ):
        raise ValueError("frozen Plan0030 proposal metadata differs")
    design = proposal.get("design_record")
    if (
        type(design) is not dict
        or design.get("path") != DESIGN_DATA
        or not re.fullmatch(r"[0-9a-f]{64}", str(design.get("sha256")))
        or _sha256((repository / DESIGN_DATA).read_bytes()) != design["sha256"]
    ):
        raise ValueError("frozen design-record pin differs")
    limits = proposal.get("limits")
    required_limits = {
        "short_query_max_nodes": MAX_NODES,
        "game_max_nodes_per_role": MAX_NODES,
        "exact_max_states": MAX_STATES,
        "bfs_stop_after_seen_states": BFS_STOP,
        "maximum_attempts": MAX_ATTEMPTS,
        "maximum_run_artifact_files": MAX_FILES,
        "maximum_published_bytes": MAX_PUBLISHED_BYTES,
        "maximum_bfs_result_bytes": MAX_BFS_BYTES,
        "maximum_other_result_bytes": MAX_OTHER_BYTES,
    }
    if type(limits) is not dict or any(limits.get(k) != v for k, v in required_limits.items()):
        raise ValueError("frozen operational limits differ")
    resources = proposal.get("resource_ceilings")
    if type(resources) is not dict or any(resources.get(k) != v for k, v in RESOURCE_CEILINGS.items()):
        raise ValueError("frozen resource arithmetic differs")
    if proposal.get("policy_identities") != POLICY_IDENTITIES:
        raise ValueError("frozen existing-agent identities differ")

    rows = proposal.get("ranked_candidates")
    if type(rows) is not list or len(rows) != 4:
        raise ValueError("exactly four ranked candidates required")
    hashes = set()
    seeds = []
    expected_t3 = (72300, 93990, 72300, 72300)
    for index, row in enumerate(rows, 1):
        if type(row) is not dict or row.get("rank") != index or row.get("cell") != index:
            raise ValueError("candidate rank/cell order differs")
        raw = row.get("definition")
        definition = parse_definition(raw)
        identity = definition_hash(definition)
        if (
            json.loads(canonical_json(definition)) != raw
            or identity != row.get("definition_hash")
            or identity in hashes
            or definition.first_player is not Player.A
            or definition.max_plies != row.get("max_natural_plies") + 1
            or row.get("maximum_branching") != 15
            or row.get("t3_nodes_per_role") != expected_t3[index - 1]
        ):
            raise ValueError("candidate canonical identity or fixed bounds differ")
        hashes.add(identity)
        cell_seeds = row.get("seeds")
        if type(cell_seeds) is not dict or set(cell_seeds) != {
            "short_four", "T2_T2", "T3_T3", "short_seven"
        }:
            raise ValueError("candidate seed cells differ")
        for short in ("short_four", "short_seven"):
            if type(cell_seeds[short]) is not dict or set(cell_seeds[short]) != {"A", "B"}:
                raise ValueError("short-query seeds differ")
            seeds.extend(cell_seeds[short][target] for target in ("A", "B"))
        for policy in POLICY_ORDER:
            if type(cell_seeds[policy]) is not list or len(cell_seeds[policy]) != 4:
                raise ValueError("game seeds differ")
            seeds.extend(cell_seeds[policy])
    if len(seeds) != 48 or any(type(seed) is not int for seed in seeds) or len(set(seeds)) != 48:
        raise ValueError("all 48 RNG/game seeds must be unique exact integers")
    if make_schedule(proposal) != make_schedule(proposal):
        raise AssertionError("schedule is nondeterministic")
    return proposal


def make_schedule(proposal):
    """Materialize the exact 56-slot stage-major schedule without computation."""

    rows = proposal.get("ranked_candidates")
    if type(rows) is not list or len(rows) != 4:
        raise ValueError("four proposal rows required for the schedule")
    schedule = []

    def add(row, **fields):
        schedule.append(
            {
                "ordinal": len(schedule),
                "rank": row["rank"],
                "cell": row["cell"],
                "definition_hash": row["definition_hash"],
                **fields,
            }
        )

    for stage in ("SHORT_FOUR",):
        decisions, plies = SHORT_STAGE[stage]
        for row in rows:
            for target in ("A", "B"):
                add(
                    row,
                    kind="short_query",
                    stage=stage,
                    target=target,
                    target_decisions=decisions,
                    target_ply=plies[target],
                    seed=row["seeds"]["short_four"][target],
                    max_nodes=MAX_NODES,
                )
    for row in rows:
        for profile in POLICY_ORDER:
            policy = profile[:2]
            for seed in row["seeds"][profile]:
                add(
                    row,
                    kind="game",
                    stage="POLICY_GAMES",
                    profile=profile,
                    policy_a=policy,
                    policy_b=policy,
                    seed=seed,
                    max_nodes_per_role=MAX_NODES,
                )
    for row in rows:
        add(row, kind="exact", stage="EXACT", max_states=MAX_STATES)
    for row in rows:
        add(
            row,
            kind="bfs_prefix",
            stage="BFS_PREFIX",
            stop_after_seen_states=BFS_STOP,
            maximum_branching=row["maximum_branching"],
        )
    decisions, plies = SHORT_STAGE["SHORT_SEVEN"]
    for row in rows:
        for target in ("A", "B"):
            add(
                row,
                kind="short_query",
                stage="SHORT_SEVEN",
                target=target,
                target_decisions=decisions,
                target_ply=plies[target],
                seed=row["seeds"]["short_seven"][target],
                max_nodes=MAX_NODES,
            )
    if (
        len(schedule) != MAX_ATTEMPTS
        or [item["ordinal"] for item in schedule] != list(range(MAX_ATTEMPTS))
        or Counter(item["kind"] for item in schedule)
        != {"short_query": 16, "game": 32, "exact": 4, "bfs_prefix": 4}
        or [stage for stage in STAGE_ORDER for _ in [0] if any(
            item["stage"] == stage for item in schedule
        )] != list(STAGE_ORDER)
    ):
        raise ValueError("fixed Plan0030 schedule differs")
    if [item["stage"] for item in schedule] != sorted(
        (item["stage"] for item in schedule), key=STAGE_ORDER.index
    ):
        raise ValueError("schedule stage barriers differ")
    seeded = [item["seed"] for item in schedule if "seed" in item]
    if len(seeded) != 48 or len(set(seeded)) != 48:
        raise ValueError("schedule must consume the 48 frozen seeds exactly once")
    return schedule


def short_query(raw, target, target_ply, seed, max_nodes=MAX_NODES):
    """Run one fresh terminal-only root query; never apply the selected action."""

    record = {
        "status": "STARTED",
        "definition_hash": None,
        "target": target,
        "target_ply": target_ply,
        "seed": seed,
        "max_nodes": max_nodes,
        "agent": None,
        "root_actions": [],
        "action_values": [],
        "selected_action": None,
        "root_min": None,
        "root_max": None,
        "root_value": None,
        "target_utility": {"A": 1, "B": -1}.get(target),
        "forced_win": None,
        "expanded_nodes": None,
        "cache_hits": None,
        "error": None,
        "replay_count": 0,
    }
    try:
        if (
            target not in ("A", "B")
            or type(target_ply) is not int
            or target_ply not in (7, 8, 13, 14)
            or target_ply % 2 != (1 if target == "A" else 0)
            or type(seed) is not int
            or type(max_nodes) is not int
            or max_nodes < 1
        ):
            raise ValueError("invalid fixed short-query condition")
        before = canonical_bytes(raw)
        definition = parse_definition(raw)
        record["definition_hash"] = definition_hash(definition)
        state = initial_state(definition)
        if state.terminal or state.to_move is not Player.A:
            raise ValueError("short query requires a live A-root initial state")
        choices = legal_actions(definition, state)
        canonical = tuple(sorted(set(choices), key=lambda action: action.sort_key()))
        if type(choices) is not tuple or not choices or choices != canonical:
            raise ValueError("initial legal actions are not the canonical unique tuple")
        record["root_actions"] = [action.to_dict() for action in choices]
        agent = TerminalOnlyMinimaxAgent(target_ply, max_nodes)
        record["agent"] = agent.identity.key
        try:
            selected = agent.select_action(
                definition, state, choices, random.Random(seed)
            )
        except SearchBudgetExceeded as error:
            if (
                error.visited_nodes != max_nodes
                or error.max_nodes != max_nodes
                or agent.total_nodes != max_nodes
                or agent.last_action_values
            ):
                raise ValueError("invalid short-query censor") from error
            record.update(
                status="UNKNOWN_CENSORED",
                expanded_nodes=max_nodes,
                error={
                    "type": type(error).__name__,
                    "scope": error.scope,
                    "searched_nodes": error.visited_nodes,
                    "max_nodes": error.max_nodes,
                },
            )
        else:
            values = agent.last_action_values
            if tuple(action for action, _value in values) != choices:
                raise ValueError("short-query root values differ from initial choices")
            raw_values = [value for _action, value in values]
            if not raw_values or any(type(value) is not int or value not in (-1, 0, 1) for value in raw_values):
                raise ValueError("invalid short-query utility")
            # All frozen definitions start with A.  In particular, B force is
            # max(values)==-1, not min(values)==-1.
            root_value = max(raw_values)
            record.update(
                status="COMPLETE",
                action_values=[
                    {"action": action.to_dict(), "value": value}
                    for action, value in values
                ],
                selected_action=selected.to_dict(),
                root_min=min(raw_values),
                root_max=max(raw_values),
                root_value=root_value,
                forced_win=root_value == record["target_utility"],
                expanded_nodes=agent.last_expanded_nodes,
                cache_hits=agent.last_cache_hits,
            )
            if agent.total_nodes != agent.last_expanded_nodes:
                raise ValueError("fresh short-query node accounting differs")
        if canonical_bytes(raw) != before or canonical_json(definition).encode("utf-8") != before:
            raise ValueError("definition drift during short query")
    except Exception as error:
        record.update(status="FAILED", error=_error(error))
    return record


def validate_short_result(item, result):
    if type(result) is not dict or result.get("status") not in ("COMPLETE", "UNKNOWN_CENSORED"):
        raise ValueError("short query failed")
    for key in ("definition_hash", "target", "target_ply", "seed", "max_nodes"):
        if result.get(key) != item.get(key):
            raise ValueError("short-query condition drift")
    if result.get("agent") != "terminal_only_minimax-v1-depth{}".format(item["target_ply"]):
        raise ValueError("short-query agent identity differs")
    actions = result.get("root_actions")
    if type(actions) is not list or not actions or len({canonical_bytes(a) for a in actions}) != len(actions):
        raise ValueError("invalid short-query root actions")
    if type(result.get("replay_count")) is not int or result["replay_count"] != 0:
        raise ValueError("short query must not replay")
    if result["status"] == "UNKNOWN_CENSORED":
        if (
            result.get("action_values") != []
            or result.get("selected_action") is not None
            or result.get("root_min") is not None
            or result.get("root_max") is not None
            or result.get("root_value") is not None
            or type(result.get("target_utility")) is not int
            or result.get("target_utility")
            != {"A": 1, "B": -1}[item["target"]]
            or result.get("forced_win") is not None
            or result.get("expanded_nodes") != item["max_nodes"]
            or result.get("cache_hits") is not None
            or result.get("error") != {
                "type": "SearchBudgetExceeded",
                "scope": "per-slot",
                "searched_nodes": item["max_nodes"],
                "max_nodes": item["max_nodes"],
            }
        ):
            raise ValueError("invalid short-query UNKNOWN wire")
        return
    values = result.get("action_values")
    raw_values = [entry.get("value") for entry in values] if type(values) is list else []
    if (
        len(values) != len(actions)
        or any(
            type(entry) is not dict
            or set(entry) != {"action", "value"}
            or entry.get("action") != action
            or type(entry.get("value")) is not int
            or entry["value"] not in (-1, 0, 1)
            for entry, action in zip(values, actions)
        )
        or result.get("selected_action") not in actions
        or type(result.get("root_min")) is not int
        or result.get("root_min") != min(raw_values)
        or type(result.get("root_max")) is not int
        or result.get("root_max") != max(raw_values)
        or type(result.get("root_value")) is not int
        or result.get("root_value") != max(raw_values)
        or type(result.get("target_utility")) is not int
        or result.get("target_utility") != {"A": 1, "B": -1}[item["target"]]
        or type(result.get("forced_win")) is not bool
        or result.get("forced_win") is not (max(raw_values) == result["target_utility"])
        or type(result.get("expanded_nodes")) is not int
        or not 1 <= result["expanded_nodes"] <= item["max_nodes"]
        or type(result.get("cache_hits")) is not int
        or result["cache_hits"] < 0
        or result.get("error") is not None
    ):
        raise ValueError("invalid completed short-query evidence")


def validate_game_result(item, result, row):
    if type(result) is not dict or result.get("status") != "COMPLETE":
        raise ValueError("game censor/failure contradicts the admitted T3 bound")
    for key in (
        "definition_hash", "policy_a", "policy_b", "seed", "max_nodes_per_role"
    ):
        if result.get(key) != item.get(key):
            raise ValueError("game condition drift")
    if result.get("first_player") != "A":
        raise ValueError("game first player differs")
    for role in ("A", "B"):
        policy = item["policy_" + role.lower()]
        if result.get("agent_" + role.lower()) != POLICY_IDENTITIES[policy]:
            raise ValueError("game existing-agent identity differs")
        nodes = (result.get("nodes_by_role") or {}).get(role)
        structural = row[policy.lower() + "_nodes_per_role"]
        if (
            type(nodes) is not int
            or not 0 <= nodes <= structural
            or nodes > item["max_nodes_per_role"]
        ):
            raise ValueError("invalid game role node accounting")
        if (result.get("node_accounting") or {}).get(role) != "SEARCH_CACHE_MISSES":
            raise ValueError("invalid game node-accounting label")
    plies = result.get("plies")
    actions = result.get("actions")
    decisions = result.get("decisions")
    terminal = result.get("state_after_prefix")
    observed = result.get("observed_game_record")
    if (
        result.get("winner") not in ("A", "B")
        or result.get("terminal_reason") not in ("GOAL", "NO_LEGAL_ACTION")
        or type(plies) is not int
        or not 1 <= plies <= row["max_natural_plies"]
        or type(actions) is not list
        or len(actions) != plies
        or type(decisions) is not list
        or len(decisions) != plies
        or type(result.get("replay_count")) is not int
        or result["replay_count"] != 1
        or result.get("replay_verified") is not True
        or result.get("censor") is not None
        or result.get("error") is not None
        or result.get("unconfirmed_action") is not None
        or "verification_error" in result
        or type(terminal) is not dict
        or type(terminal.get("ply")) is not int
        or terminal.get("ply") != plies
        or type(terminal.get("outcome")) is not dict
        or terminal["outcome"].get("winner") != result["winner"]
        or terminal["outcome"].get("reason") != result["terminal_reason"]
        or type(observed) is not dict
        or observed.get("actions") != actions
        or type(observed.get("plies")) is not int
        or observed.get("plies") != plies
        or observed.get("winner") != result["winner"]
        or observed.get("terminal_reason") != result["terminal_reason"]
        or observed.get("seed") != item["seed"]
        or observed.get("agent_a") != result.get("agent_a")
        or observed.get("agent_b") != result.get("agent_b")
    ):
        raise ValueError("game violates decisive proof/replay bounds")
    node_cursor = {"A": 0, "B": 0}
    for ply, (action, decision) in enumerate(zip(actions, decisions)):
        actor = "A" if ply % 2 == 0 else "B"
        values = decision.get("last_action_values") if type(decision) is dict else None
        if (
            type(decision) is not dict
            or type(decision.get("ply")) is not int
            or decision.get("ply") != ply
            or decision.get("actor") != actor
            or decision.get("selection_status") != "SELECTED"
            or decision.get("selected_action") != action
            or type(decision.get("legal_action_count")) is not int
            or not 1 <= decision["legal_action_count"] <= row["maximum_branching"]
            or type(decision.get("nodes_before")) is not int
            or decision.get("nodes_before") != node_cursor[actor]
            or type(decision.get("nodes_after")) is not int
            or type(decision.get("charged_nodes")) is not int
            or not 0 <= decision["nodes_before"] <= decision["nodes_after"]
            or decision["nodes_after"] - decision["nodes_before"]
            != decision["charged_nodes"]
            or type(values) is not list
            or len(values) != decision["legal_action_count"]
            or any(
                type(value) is not dict
                or set(value) != {"action", "value"}
                or type(value.get("value")) is not int
                or value["value"] not in (-1, 0, 1)
                for value in values
            )
            or action not in [value["action"] for value in values]
        ):
            raise ValueError("invalid game decision audit trail")
        node_cursor[actor] = decision["nodes_after"]
    if node_cursor != result["nodes_by_role"]:
        raise ValueError("game decision/role node totals differ")


def validate_exact_result(item, result, row):
    if type(result) is not dict or result.get("status") not in ("COMPLETE", "UNKNOWN_CENSORED"):
        raise ValueError("exact call failed")
    if result.get("definition_hash") != item["definition_hash"] or result.get("max_states") != item["max_states"]:
        raise ValueError("exact condition drift")
    if result["status"] == "UNKNOWN_CENSORED":
        if (
            result.get("actual_result") is not None
            or type(result.get("replay_count")) is not int
            or result["replay_count"] != 0
            or result.get("error") != {
                "type": "SolveBudgetExceeded",
                "searched_states": item["max_states"],
                "max_states": item["max_states"],
            }
        ):
            raise ValueError("invalid exact UNKNOWN wire")
        return
    wire = result.get("actual_result")
    pv = wire.get("principal_variation") if type(wire) is dict else None
    terminal = result.get("terminal_state")
    if (
        type(wire) is not dict
        or type(wire.get("value_for_a")) is not int
        or wire.get("value_for_a") not in (-1, 1)
        or wire.get("forced_result") not in ("A_WIN", "B_WIN")
        or wire.get("forced_result") != {1: "A_WIN", -1: "B_WIN"}[wire["value_for_a"]]
        or type(wire.get("principal_variation_plies")) is not int
        or not 1 <= wire["principal_variation_plies"] <= row["max_natural_plies"]
        or type(pv) is not list
        or len(pv) != wire["principal_variation_plies"]
        or type(wire.get("searched_states")) is not int
        or not 1 <= wire["searched_states"] <= item["max_states"]
        or type(wire.get("cache_hits")) is not int
        or wire["cache_hits"] < 0
        or wire.get("terminal_reason") not in ("GOAL", "NO_LEGAL_ACTION")
        or type(result.get("replay_count")) is not int
        or result["replay_count"] != 1
        or result.get("error") is not None
        or type(terminal) is not dict
        or type(terminal.get("ply")) is not int
        or terminal.get("ply") != wire.get("principal_variation_plies")
        or type(terminal.get("outcome")) is not dict
        or terminal["outcome"].get("winner")
        != {1: "A", -1: "B"}[wire.get("value_for_a")]
        or terminal["outcome"].get("reason") != wire.get("terminal_reason")
    ):
        raise ValueError("exact COMPLETE contradicts D-055 or replay bounds")


def _state_digest(state):
    return _sha256(canonical_bytes(state.to_dict()))


def bfs_prefix(raw, stop_after_seen_states=BFS_STOP, maximum_branching=15):
    """Enumerate one exact-GameState FIFO prefix, storing no graph edges."""

    result = {
        "status": "STARTED",
        "definition_hash": None,
        "stop_after_seen_states": stop_after_seen_states,
        "maximum_branching": maximum_branching,
        "seen_states": 0,
        "expanded_states": 0,
        "terminal_states": 0,
        "terminal_states_by_winner": {"A": 0, "B": 0},
        "terminal_states_by_reason": {"GOAL": 0, "NO_LEGAL_ACTION": 0},
        "draw_terminal_states": 0,
        "ply_limit_terminal_states": 0,
        "transitions": 0,
        "max_queue_references": 0,
        "stored_edges": 0,
        "state_digests": [],
        "rolling_transition_sha256": hashlib.sha256(b"").hexdigest(),
        "identity_model": "FULL_GAME_STATE_PLY_TO_MOVE_PIECES_OUTCOME",
        "queue_order": "FIFO_CANONICAL_ACTION_TUPLE",
        "state_digest_algorithm": "SHA256_CANONICAL_STATE_DICT_V1",
        "transition_digest_algorithm": "SHA256_CONCAT_CANONICAL_FROM_ACTION_TO_V1",
        "transition_digest_includes_duplicates": True,
        "terminal_states_expanded": False,
        "error": None,
        "replay_count": 0,
    }
    try:
        if type(stop_after_seen_states) is not int or stop_after_seen_states < 2:
            raise ValueError("invalid BFS state stop")
        if type(maximum_branching) is not int or maximum_branching < 1:
            raise ValueError("invalid BFS branch bound")
        before = canonical_bytes(raw)
        definition = parse_definition(raw)
        result["definition_hash"] = definition_hash(definition)
        root = initial_state(definition)
        if root.terminal:
            raise ValueError("fixed BFS root must be nonterminal")
        seen = {root}
        queue = deque((root,))
        digest = _state_digest(root)
        digest_set = {digest}
        state_digests = [digest]
        rolling = hashlib.sha256()
        terminal_count = 0
        terminal_by_winner = {"A": 0, "B": 0}
        terminal_by_reason = {"GOAL": 0, "NO_LEGAL_ACTION": 0}
        max_queue = 1
        transitions = 0
        expanded = 0
        while queue and len(seen) < stop_after_seen_states:
            state = queue.popleft()
            if state.terminal:
                raise AssertionError("terminal state was enqueued for expansion")
            expanded += 1
            actions = legal_actions(definition, state)
            canonical = tuple(sorted(set(actions), key=lambda action: action.sort_key()))
            if type(actions) is not tuple or not actions or actions != canonical:
                raise ValueError("BFS legal actions are not the canonical unique tuple")
            if len(actions) > maximum_branching:
                raise ValueError("BFS maximum branching bound violated")
            parent_digest = _state_digest(state)
            for action in actions:
                child = apply_action(definition, state, action)
                transitions += 1
                child_digest = _state_digest(child)
                rolling.update(
                    canonical_bytes(
                        {
                            "from": parent_digest,
                            "action": action.to_dict(),
                            "to": child_digest,
                        }
                    )
                )
                if child in seen:
                    continue
                if child_digest in digest_set:
                    raise ValueError("distinct GameStates share a saved digest")
                seen.add(child)
                digest_set.add(child_digest)
                state_digests.append(child_digest)
                if child.terminal:
                    outcome = child.outcome
                    if (
                        outcome is None
                        or outcome.winner not in (Player.A, Player.B)
                        or outcome.reason not in ("GOAL", "NO_LEGAL_ACTION")
                    ):
                        raise ValueError(
                            "BFS encountered a draw, PLY_LIMIT, or winnerless terminal"
                        )
                    terminal_count += 1
                    terminal_by_winner[outcome.winner.value] += 1
                    terminal_by_reason[outcome.reason] += 1
                else:
                    queue.append(child)
                    max_queue = max(max_queue, len(queue))
                if len(seen) == stop_after_seen_states:
                    break
        result.update(
            status=(
                "PREFIX_LIMIT_REACHED"
                if len(seen) == stop_after_seen_states
                else "EXHAUSTED"
            ),
            seen_states=len(seen),
            expanded_states=expanded,
            terminal_states=terminal_count,
            terminal_states_by_winner=terminal_by_winner,
            terminal_states_by_reason=terminal_by_reason,
            draw_terminal_states=0,
            ply_limit_terminal_states=0,
            transitions=transitions,
            max_queue_references=max_queue,
            state_digests=state_digests,
            rolling_transition_sha256=rolling.hexdigest(),
        )
        if canonical_bytes(raw) != before or canonical_json(definition).encode("utf-8") != before:
            raise ValueError("definition drift during BFS")
    except Exception as error:
        result.update(status="FAILED", error=_error(error))
    return result


def validate_bfs_result(item, result):
    if type(result) is not dict or result.get("status") not in (
        "PREFIX_LIMIT_REACHED", "EXHAUSTED"
    ):
        raise ValueError("BFS prefix failed")
    for key in ("definition_hash", "stop_after_seen_states", "maximum_branching"):
        if result.get(key) != item.get(key):
            raise ValueError("BFS condition drift")
    seen = result.get("seen_states")
    digests = result.get("state_digests")
    if (
        type(seen) is not int
        or not 1 <= seen <= item["stop_after_seen_states"]
        or type(digests) is not list
        or len(digests) != seen
        or len(set(digests)) != seen
        or any(type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None for value in digests)
        or type(result.get("rolling_transition_sha256")) is not str
        or re.fullmatch(
            r"[0-9a-f]{64}", result["rolling_transition_sha256"]
        ) is None
        or type(result.get("transitions")) is not int
        or not 0 <= result["transitions"] <= item["stop_after_seen_states"] * item["maximum_branching"]
        or type(result.get("expanded_states")) is not int
        or not 0 <= result["expanded_states"] <= seen
        or type(result.get("terminal_states")) is not int
        or not 0 <= result["terminal_states"] <= seen
        or type(result.get("terminal_states_by_winner")) is not dict
        or type(result.get("terminal_states_by_reason")) is not dict
        or result.get("terminal_states_by_winner")
        != {
            "A": result["terminal_states_by_winner"].get("A"),
            "B": result["terminal_states_by_winner"].get("B"),
        }
        or result.get("terminal_states_by_reason")
        != {
            "GOAL": result["terminal_states_by_reason"].get("GOAL"),
            "NO_LEGAL_ACTION": result["terminal_states_by_reason"].get(
                "NO_LEGAL_ACTION"
            ),
        }
        or any(
            type(value) is not int or value < 0
            for value in result["terminal_states_by_winner"].values()
        )
        or any(
            type(value) is not int or value < 0
            for value in result["terminal_states_by_reason"].values()
        )
        or sum(result["terminal_states_by_winner"].values())
        != result["terminal_states"]
        or sum(result["terminal_states_by_reason"].values())
        != result["terminal_states"]
        or type(result.get("draw_terminal_states")) is not int
        or result["draw_terminal_states"] != 0
        or type(result.get("ply_limit_terminal_states")) is not int
        or result["ply_limit_terminal_states"] != 0
        or type(result.get("max_queue_references")) is not int
        or not 0 <= result["max_queue_references"] <= seen
        or type(result.get("stored_edges")) is not int
        or result["stored_edges"] != 0
        or type(result.get("replay_count")) is not int
        or result["replay_count"] != 0
        or result.get("error") is not None
        or result.get("identity_model") != "FULL_GAME_STATE_PLY_TO_MOVE_PIECES_OUTCOME"
        or result.get("queue_order") != "FIFO_CANONICAL_ACTION_TUPLE"
        or result.get("state_digest_algorithm") != "SHA256_CANONICAL_STATE_DICT_V1"
        or result.get("transition_digest_algorithm")
        != "SHA256_CONCAT_CANONICAL_FROM_ACTION_TO_V1"
        or result.get("transition_digest_includes_duplicates") is not True
        or result.get("terminal_states_expanded") is not False
    ):
        raise ValueError("invalid BFS prefix evidence")
    if result["status"] == "PREFIX_LIMIT_REACHED" and seen != item["stop_after_seen_states"]:
        raise ValueError("BFS prefix-limit count differs")
    if result["expanded_states"] + result["terminal_states"] > seen:
        raise ValueError("BFS state partition exceeds the seen-state count")
    if result["transitions"] < seen - 1:
        raise ValueError("BFS transitions cannot discover the reported states")
    if result["status"] == "EXHAUSTED":
        if seen >= item["stop_after_seen_states"]:
            raise ValueError("BFS exhaustion count differs")
        if result["expanded_states"] + result["terminal_states"] != seen:
            raise ValueError("exhausted BFS has pending nonterminal states")


def _policy_gate(results):
    if len(results) != 8:
        raise ValueError("policy gate requires both four-game cells")
    by_profile = {}
    for profile in POLICY_ORDER:
        mine = [result for item, result in results if item["profile"] == profile]
        if len(mine) != 4:
            raise ValueError("policy game cell denominator differs")
        a_wins = sum(result["winner"] == "A" for result in mine)
        by_profile[profile] = {
            "completed": len(mine),
            "a_wins": a_wins,
            "b_wins": len(mine) - a_wins,
        }
    goal = [result for _item, result in results if result["terminal_reason"] == "GOAL"]
    passed = (
        all(1 <= cell["a_wins"] <= 3 for cell in by_profile.values())
        and len(goal) >= 4
        and any(result["winner"] == "A" for result in goal)
        and any(result["winner"] == "B" for result in goal)
    )
    return {
        "passed": passed,
        "profiles": by_profile,
        "goal_endings": len(goal),
        "a_goal_endings": sum(result["winner"] == "A" for result in goal),
        "b_goal_endings": sum(result["winner"] == "B" for result in goal),
    }


def execute_cascade(
    proposal,
    *,
    source_digest,
    before_attempt,
    after_result,
    check_source,
    short_runner=None,
    game_runner=None,
    exact_runner=None,
    bfs_runner=None,
):
    """Execute the schedule once with all barriers and immutable close labels."""

    short_runner = short_query if short_runner is None else short_runner
    game_runner = play_adapter.play_one if game_runner is None else game_runner
    exact_runner = exact_one if exact_runner is None else exact_runner
    bfs_runner = bfs_prefix if bfs_runner is None else bfs_runner
    schedule = make_schedule(proposal)
    rows = {row["cell"]: row for row in proposal["ranked_candidates"]}
    dispositions = {cell: None for cell in rows}
    policy_results = {cell: [] for cell in rows}
    records = []
    technical_failure = None

    for item in schedule:
        before_attempt(item)
        cell = item["cell"]
        if technical_failure is not None:
            record = {
                "scheduled": item,
                "source_digest": source_digest,
                "status": "NOT_STARTED_FAILURE",
                "result": None,
            }
            records.append(record)
            after_result(item, record)
            continue
        if dispositions[cell] is not None:
            record = {
                "scheduled": item,
                "source_digest": source_digest,
                "status": "NOT_STARTED_GATE_CLOSED",
                "result": None,
                "cell_disposition": dispositions[cell],
            }
            records.append(record)
            after_result(item, record)
            continue

        result = None
        try:
            check_source()
            raw = rows[cell]["definition"]
            if item["kind"] == "short_query":
                result = short_runner(
                    raw,
                    item["target"],
                    item["target_ply"],
                    item["seed"],
                    item["max_nodes"],
                )
                validate_short_result(item, result)
            elif item["kind"] == "game":
                result = game_runner(
                    raw,
                    item["policy_a"],
                    item["policy_b"],
                    item["seed"],
                    item["max_nodes_per_role"],
                )
                validate_game_result(item, result, rows[cell])
            elif item["kind"] == "exact":
                result = exact_runner(raw, item["max_states"])
                validate_exact_result(item, result, rows[cell])
            elif item["kind"] == "bfs_prefix":
                result = bfs_runner(
                    raw,
                    item["stop_after_seen_states"],
                    item["maximum_branching"],
                )
                validate_bfs_result(item, result)
            else:
                raise AssertionError("unknown scheduled kind")
            check_source()
        except Exception as error:
            error_wire = _error(error)
            technical_failure = {
                **error_wire,
                "ordinal": item["ordinal"],
                "stage": item["stage"],
                "cell": cell,
            }
            record = {
                "scheduled": item,
                "source_digest": source_digest,
                "status": "FAILED_TECHNICAL",
                "result": result,
                "error": error_wire,
            }
            records.append(record)
            after_result(item, record)
            continue

        record = {
            "scheduled": item,
            "source_digest": source_digest,
            "status": result["status"],
            "result": result,
        }
        if item["kind"] == "short_query":
            if result["status"] == "UNKNOWN_CENSORED":
                dispositions[cell] = "NOT_SELECTED_EVIDENCE_INCOMPLETE"
            elif result["forced_win"]:
                dispositions[cell] = "NOT_SELECTED_SHORT_FORCED_WIN"
            if dispositions[cell] is not None:
                record["cell_disposition"] = dispositions[cell]
        elif item["kind"] == "game":
            policy_results[cell].append((item, result))
            if len(policy_results[cell]) == 8:
                gate = _policy_gate(policy_results[cell])
                record["policy_gate"] = gate
                if not gate["passed"]:
                    dispositions[cell] = "NOT_SELECTED_POLICY_GATE"
                    record["cell_disposition"] = dispositions[cell]
        elif item["kind"] == "exact" and result["status"] == "COMPLETE":
            dispositions[cell] = "NOT_SELECTED_TOO_EASILY_SOLVED"
            record["cell_disposition"] = dispositions[cell]
        elif item["kind"] == "bfs_prefix" and result["status"] == "EXHAUSTED":
            technical_failure = {
                "type": "ExactBfsStateModelContradiction",
                "message": "exact UNKNOWN but canonical BFS exhausted at or below 100000 states",
                "ordinal": item["ordinal"],
                "stage": item["stage"],
                "cell": cell,
            }
            record["status"] = "FAILED_TECHNICAL"
            record["error"] = dict(technical_failure)
        records.append(record)
        after_result(item, record)
        if record.get("status") == "FAILED_TECHNICAL" and technical_failure is None:
            error = record.get("error") or {
                "type": "PublicationEnvelopeError",
                "message": "result publication failed",
            }
            technical_failure = {
                "type": error.get("type", "PublicationEnvelopeError"),
                "message": error.get("message", "result publication failed"),
                "ordinal": item["ordinal"],
                "stage": item["stage"],
                "cell": cell,
            }

    if technical_failure is None:
        survivors = [cell for cell in sorted(rows) if dispositions[cell] is None]
        if survivors:
            dispositions[survivors[0]] = "PRESELECTED_TECHNICAL_ACCEPTANCE_PENDING"
            for cell in survivors[1:]:
                dispositions[cell] = "NOT_SELECTED_FIXED_RANK"
    return records, dispositions, technical_failure


def classify_saved_records(proposal, records, external_failure=None):
    """Rebuild every gate from saved wires without calling a game/search engine."""

    schedule = make_schedule(proposal)
    if type(records) is not list or len(records) != len(schedule):
        raise ValueError("saved cascade must contain all 56 result records")
    rows = {row["cell"]: row for row in proposal["ranked_candidates"]}
    dispositions = {cell: None for cell in rows}
    policy_results = {cell: [] for cell in rows}
    technical = None
    source_digests = set()
    for item, record in zip(schedule, records):
        if type(record) is not dict or record.get("scheduled") != item:
            raise ValueError("saved result is not the exact ordered schedule")
        digest = record.get("source_digest")
        if type(digest) is not str or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise ValueError("saved result source digest is invalid")
        source_digests.add(digest)
        cell = item["cell"]
        status = record.get("status")
        result = record.get("result")
        if technical is not None:
            if status != "NOT_STARTED_FAILURE" or result is not None:
                raise ValueError("slot after technical failure is not failure-closed")
            continue
        # A global publisher failure can occur while writing an otherwise
        # ordinary scientific-gate closure.  That technical stop takes
        # precedence over the already-computed cell disposition.
        if status == "NOT_STARTED_FAILURE" and external_failure is not None:
            if result is not None:
                raise ValueError("external-failure closure contains a result")
            technical = external_failure
            continue
        if status == "FAILED_TECHNICAL":
            error = record.get("error")
            if (
                type(error) is not dict
                or type(error.get("type")) is not str
                or not error["type"]
                or len(error["type"].encode("utf-8")) > MAX_ERROR_TYPE_BYTES
                or type(error.get("message")) is not str
                or not error["message"]
                or len(error["message"].encode("utf-8"))
                > MAX_ERROR_MESSAGE_BYTES
            ):
                raise ValueError("technical result lacks a compact error")
            if item["kind"] == "bfs_prefix" and type(result) is dict and result.get("status") == "EXHAUSTED":
                validate_bfs_result(item, result)
                if error.get("type") != "ExactBfsStateModelContradiction":
                    raise ValueError("BFS exhaustion has the wrong technical label")
            technical = {
                "type": error["type"],
                "message": error["message"],
            }
            for key in ("type_truncated", "message_truncated"):
                if key in error:
                    metadata = error[key]
                    if (
                        type(metadata) is not dict
                        or set(metadata) != {"original_bytes", "sha256"}
                        or type(metadata.get("original_bytes")) is not int
                        or metadata["original_bytes"] < 1
                        or type(metadata.get("sha256")) is not str
                        or re.fullmatch(r"[0-9a-f]{64}", metadata["sha256"])
                        is None
                    ):
                        raise ValueError("technical error truncation metadata differs")
                    technical[key] = metadata
            technical.update(
                ordinal=item["ordinal"],
                stage=item["stage"],
                cell=cell,
            )
            continue
        if dispositions[cell] is not None:
            if (
                status != "NOT_STARTED_GATE_CLOSED"
                or result is not None
                or record.get("cell_disposition") != dispositions[cell]
            ):
                raise ValueError("slot after scientific gate is not gate-closed")
            continue
        if status in ("NOT_STARTED_FAILURE", "NOT_STARTED_GATE_CLOSED") or type(result) is not dict:
            raise ValueError("open saved slot was not computed")
        row = rows[cell]
        if item["kind"] == "short_query":
            validate_short_result(item, result)
            if status != result["status"]:
                raise ValueError("short wrapper/result statuses differ")
            if result["status"] == "UNKNOWN_CENSORED":
                dispositions[cell] = "NOT_SELECTED_EVIDENCE_INCOMPLETE"
            elif result["forced_win"]:
                dispositions[cell] = "NOT_SELECTED_SHORT_FORCED_WIN"
            expected = dispositions[cell]
            if record.get("cell_disposition") != expected:
                raise ValueError("short-query disposition differs")
        elif item["kind"] == "game":
            validate_game_result(item, result, row)
            if status != "COMPLETE":
                raise ValueError("game wrapper status differs")
            policy_results[cell].append((item, result))
            if len(policy_results[cell]) == 8:
                gate = _policy_gate(policy_results[cell])
                if record.get("policy_gate") != gate:
                    raise ValueError("saved policy gate differs")
                if not gate["passed"]:
                    dispositions[cell] = "NOT_SELECTED_POLICY_GATE"
                    if record.get("cell_disposition") != dispositions[cell]:
                        raise ValueError("policy disposition differs")
                elif "cell_disposition" in record:
                    raise ValueError("passing policy cell has a disposition")
            elif "policy_gate" in record or "cell_disposition" in record:
                raise ValueError("policy gate was evaluated before all eight games")
        elif item["kind"] == "exact":
            validate_exact_result(item, result, row)
            if status != result["status"]:
                raise ValueError("exact wrapper/result statuses differ")
            if result["status"] == "COMPLETE":
                dispositions[cell] = "NOT_SELECTED_TOO_EASILY_SOLVED"
                if record.get("cell_disposition") != dispositions[cell]:
                    raise ValueError("exact disposition differs")
            elif "cell_disposition" in record:
                raise ValueError("exact UNKNOWN has a disposition")
        elif item["kind"] == "bfs_prefix":
            validate_bfs_result(item, result)
            if status != "PREFIX_LIMIT_REACHED" or result["status"] != status:
                raise ValueError("only the full BFS prefix may pass its barrier")
            if "cell_disposition" in record:
                raise ValueError("passing BFS prefix has a disposition")
        else:
            raise AssertionError("unknown saved schedule kind")
    if len(source_digests) != 1:
        raise ValueError("saved result source digests differ")
    if technical is None:
        survivors = [cell for cell in sorted(rows) if dispositions[cell] is None]
        if survivors:
            dispositions[survivors[0]] = "PRESELECTED_TECHNICAL_ACCEPTANCE_PENDING"
            for cell in survivors[1:]:
                dispositions[cell] = "NOT_SELECTED_FIXED_RANK"
    return dispositions, technical, source_digests.pop()


def summarize(records, dispositions, failure=None, publication=None):
    """Summarize bounded evidence without copying any BFS state-digest list."""

    candidates = []
    for cell in sorted(dispositions):
        mine = [record for record in records if record["scheduled"]["cell"] == cell]
        games = [record["result"] for record in mine if record["scheduled"]["kind"] == "game" and record["status"] == "COMPLETE"]
        exact = next(
            (
                record["result"]
                for record in mine
                if record["scheduled"]["kind"] == "exact"
                and record.get("status") in ("COMPLETE", "UNKNOWN_CENSORED")
                and type(record.get("result")) is dict
                and record["result"].get("status")
                in ("COMPLETE", "UNKNOWN_CENSORED")
            ),
            None,
        )
        bfs = next(
            (
                record["result"]
                for record in mine
                if record["scheduled"]["kind"] == "bfs_prefix"
                and record.get("status")
                in ("PREFIX_LIMIT_REACHED", "EXHAUSTED")
                and type(record.get("result")) is dict
                and record["result"].get("status")
                in ("PREFIX_LIMIT_REACHED", "EXHAUSTED")
            ),
            None,
        )
        candidates.append(
            {
                "cell": cell,
                "disposition": dispositions[cell],
                "attempt_statuses": dict(Counter(record["status"] for record in mine)),
                "games_completed": len(games),
                "a_wins": sum(game["winner"] == "A" for game in games),
                "b_wins": sum(game["winner"] == "B" for game in games),
                "goal_endings": sum(game["terminal_reason"] == "GOAL" for game in games),
                "exact_status": None if exact is None else exact["status"],
                "bfs": None if bfs is None else {
                    "status": bfs["status"],
                    "seen_states": bfs["seen_states"],
                    "transitions": bfs["transitions"],
                    "rolling_transition_sha256": bfs["rolling_transition_sha256"],
                    "state_digest_count": len(bfs["state_digests"]),
                },
            }
        )
    selected = [
        row
        for row in candidates
        if row["disposition"] == "PRESELECTED_TECHNICAL_ACCEPTANCE_PENDING"
    ]
    completed_games = [
        record["result"]
        for record in records
        if record["scheduled"]["kind"] == "game"
        and record["status"] == "COMPLETE"
    ]
    def reported_integer(value):
        return value if type(value) is int and value >= 0 else 0

    exact_states = 0
    exact_replay_plies = 0
    short_nodes = game_nodes = bfs_transitions = game_plies = 0
    for record in records:
        result = record.get("result")
        if type(result) is not dict:
            continue
        kind = record["scheduled"]["kind"]
        if kind == "short_query":
            short_nodes += reported_integer(result.get("expanded_nodes"))
        elif kind == "game":
            nodes = result.get("nodes_by_role")
            if type(nodes) is dict:
                game_nodes += sum(reported_integer(nodes.get(role)) for role in ("A", "B"))
            game_plies += reported_integer(result.get("plies"))
        elif kind == "exact":
            if result.get("status") == "UNKNOWN_CENSORED":
                error = result.get("error")
                if type(error) is dict:
                    exact_states += reported_integer(error.get("searched_states"))
            else:
                wire = result.get("actual_result")
                if type(wire) is dict:
                    exact_states += reported_integer(wire.get("searched_states"))
                    exact_replay_plies += reported_integer(
                        wire.get("principal_variation_plies")
                    )
        elif kind == "bfs_prefix":
            bfs_transitions += reported_integer(result.get("transitions"))
    resource_usage = {
        "short_query_misses": short_nodes,
        "configured_game_agent_nodes": game_nodes,
        "exact_searched_states": exact_states,
        "bfs_transitions": bfs_transitions,
        "adapter_internal_replay_transitions": game_plies + exact_replay_plies,
        "actual_game_plies": game_plies,
    }
    resource_violations = {
        key: {"reported": used, "ceiling": RESOURCE_CEILINGS[key]}
        for key, used in resource_usage.items()
        if used > RESOURCE_CEILINGS[key]
    }
    if resource_violations and failure is None:
        raise ValueError("aggregate resource ceiling violated")
    return {
        "protocol": PROTOCOL,
        "execution_status": "FAILED_TECHNICAL" if failure else "COMPLETE",
        "failure": failure,
        "scientific_disposition": (
            "FAILED_TECHNICAL"
            if failure
            else "PRESELECTION_SURVIVOR_AWAITING_TECHNICAL_ACCEPTANCE"
            if selected
            else "NO_SELECTION"
        ),
        "planned": MAX_ATTEMPTS,
        "records": len(records),
        "statuses": dict(Counter(record["status"] for record in records)),
        "candidates": candidates,
        "selected_cell": selected[0]["cell"] if selected else None,
        "resource_ceilings": dict(RESOURCE_CEILINGS),
        "resource_usage": resource_usage,
        "resource_ceiling_violations": resource_violations,
        "publication": publication,
        "technical_acceptance": "PROVISIONAL_UNTIL_FULL_REGRESSION",
        "human_review_eligible": False,
        "fairness_established": False,
        "hardness_established": False,
        "fun_established": False,
    }


class _Publisher:
    """Apply Plan0030's per-envelope, total-byte and file-count ceilings."""

    def __init__(self, output):
        self.output = Path(output)
        self.sha256 = {}
        self.bytes = 0

    def envelope_size(self, value):
        payload_digest = _sha256(canonical_bytes(value))
        return len(canonical_bytes({"payload": value, "sha256": payload_digest}))

    def can_publish(self, value, *, bfs=False):
        size = self.envelope_size(value)
        limit = MAX_BFS_BYTES if bfs else MAX_OTHER_BYTES
        return (
            len(self.sha256) < MAX_FILES
            and size <= limit
            and self.bytes + size <= MAX_PUBLISHED_BYTES
        )

    def publish(self, name, value, *, bfs=False):
        if name in self.sha256 or len(self.sha256) >= MAX_FILES:
            raise ValueError("publication path reused or file ceiling exceeded")
        path = self.output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        payload_digest = _sha256(canonical_bytes(value))
        envelope = canonical_bytes({"payload": value, "sha256": payload_digest})
        limit = MAX_BFS_BYTES if bfs else MAX_OTHER_BYTES
        if len(envelope) > limit or self.bytes + len(envelope) > MAX_PUBLISHED_BYTES:
            raise ValueError("Plan0030 publication byte ceiling exceeded")
        try:
            _publish(path, value)
        except Exception:
            # The accepted publisher links atomically and then reads back.  An
            # exception can therefore occur after the exact envelope is already
            # durable.  Account for that immutable file, but still propagate the
            # publication failure so the run closes technically.
            if path.exists() and path.read_bytes() == envelope:
                self.sha256[name] = _sha256(envelope)
                self.bytes += len(envelope)
            raise
        saved = path.read_bytes()
        if saved != envelope:
            raise ValueError("published envelope bytes differ")
        self.sha256[name] = _sha256(saved)
        self.bytes += len(saved)

    def adopt(self, name, *, bfs=False):
        """Account for an atomically saved envelope after a local readback error."""

        if name in self.sha256 or len(self.sha256) >= MAX_FILES:
            raise ValueError("publication path reused or file ceiling exceeded")
        path = self.output / name
        value = read_json(path)
        raw = path.read_bytes()
        limit = MAX_BFS_BYTES if bfs else MAX_OTHER_BYTES
        if len(raw) > limit or self.bytes + len(raw) > MAX_PUBLISHED_BYTES:
            raise ValueError("adopted artifact exceeds Plan0030 publication ceiling")
        self.sha256[name] = _sha256(raw)
        self.bytes += len(raw)
        return value

    def facts(self):
        return {"files": len(self.sha256), "bytes": self.bytes, "sha256": dict(self.sha256)}


def run_pilot(repository, registered_commit, output=None):
    """Run exactly one immutable registered preselection."""

    repository = Path(repository)
    output = repository / OUTPUT if output is None else Path(output)
    if output.exists():
        raise FileExistsError("immutable Plan0030 run exists; no retry or resume")
    if type(registered_commit) is not str or re.fullmatch(r"[0-9a-f]{40}", registered_commit) is None:
        raise ValueError("full registration commit required")
    source = source_snapshot(repository, clean=True)
    if source["git_commit"] != registered_commit:
        raise ValueError("HEAD differs from Plan0030 registration")
    proposal = load_proposal(repository)
    schedule = make_schedule(proposal)
    dependencies = dependency_snapshot(source)
    source_digest = _source_digest(source)
    run_started_at = _utc()
    output.mkdir(parents=True, exist_ok=False)
    publisher = _Publisher(output)

    def check_source():
        if source_snapshot(repository) != source:
            raise ValueError("registered Plan0030 source drift")

    # Construct bootstrap values once.  A one-shot publisher exception may be
    # raised either before or after its atomic link; recovery must therefore
    # reuse these exact values rather than generating a second timestamp.
    run_attempt_payload = {
        "protocol": PROTOCOL,
        "source": source,
        "started_at": run_started_at,
    }
    manifest_payload = {
            "protocol": PROTOCOL,
            "source": source,
            "source_digest": source_digest,
            "direct_dependencies": dependencies,
            "proposal_sha256": PROPOSAL_SHA256,
            "proposal": proposal,
            "schedule": schedule,
            "resource_ceilings": RESOURCE_CEILINGS,
            "acceptance": "PROVISIONAL_UNTIL_FULL_REGRESSION",
    }
    bootstrap_payloads = (
        ("run-attempt.json", run_attempt_payload),
        ("manifest.json", manifest_payload),
    )

    records = []
    dispositions = {row["cell"]: None for row in proposal["ranked_candidates"]}
    failure = None
    bootstrap_failed = False
    publication_context = {"phase": "BEFORE_CASCADE", "ordinal": None}

    def ensure_bootstrap(name, payload):
        """Recover one bootstrap envelope without changing its payload bytes."""

        path = output / name
        if name in publisher.sha256:
            if read_json(path) != payload:
                raise ValueError("durable bootstrap payload differs")
            return
        if path.exists():
            if publisher.adopt(name) != payload:
                raise ValueError("adopted bootstrap payload differs")
            return
        publisher.publish(name, payload)

    bootstrap_name = None
    try:
        for bootstrap_name, payload in bootstrap_payloads:
            publisher.publish(bootstrap_name, payload)
    except Exception as error:
        failure = {
            **_error(error),
            "phase": "BOOTSTRAP_PUBLICATION",
            "publication_path": bootstrap_name,
            "durable_envelope": bootstrap_name in publisher.sha256,
        }
        bootstrap_failed = True
        try:
            for name, payload in bootstrap_payloads:
                ensure_bootstrap(name, payload)
        except Exception as recovery_error:
            raise RuntimeError(
                "persistent bootstrap publication failure; no production call started"
            ) from recovery_error

    def before(item):
        publication_context.update(phase="ATTEMPT_PUBLICATION", ordinal=item["ordinal"])
        publisher.publish(
            "attempts/{:04d}-attempt.json".format(item["ordinal"]),
            {"scheduled": item, "source_digest": source_digest, "started_at": _utc()},
        )

    def after(item, record):
        publication_context.update(phase="RESULT_PUBLICATION", ordinal=item["ordinal"])
        name = "attempts/{:04d}-result.json".format(item["ordinal"])
        bfs = item["kind"] == "bfs_prefix" and record.get("result") is not None
        if not publisher.can_publish(record, bfs=bfs):
            record.clear()
            record.update(
                scheduled=item,
                source_digest=source_digest,
                status="FAILED_TECHNICAL",
                result=None,
                error={
                    "type": "PublicationEnvelopeTooLarge",
                    "message": "attempt result exceeded its frozen publication ceiling",
                },
            )
            bfs = False
        publisher.publish(name, record, bfs=bfs)

    def recover_schedule(closure_reason):
        """Adopt completed evidence and failure-close every missing slot."""

        recovered = []
        failure_closure_started = False
        for item in schedule:
            attempt_name = "attempts/{:04d}-attempt.json".format(item["ordinal"])
            result_name = "attempts/{:04d}-result.json".format(item["ordinal"])
            attempt_preexisting = (
                attempt_name in publisher.sha256 or (output / attempt_name).exists()
            )
            for name, bfs in (
                (attempt_name, False),
                (result_name, item["kind"] == "bfs_prefix"),
            ):
                if name not in publisher.sha256 and (output / name).exists():
                    publisher.adopt(name, bfs=bfs)
            if attempt_name not in publisher.sha256:
                publisher.publish(
                    attempt_name,
                    {
                        "scheduled": item,
                        "source_digest": source_digest,
                        "started_at": _utc(),
                        "closure_reason": closure_reason,
                    },
                )
            if result_name in publisher.sha256:
                recovered_record = read_json(output / result_name)
                recovered.append(recovered_record)
                failure_closure_started = (
                    failure_closure_started
                    or recovered_record.get("status") == "FAILED_TECHNICAL"
                )
            else:
                not_started = failure_closure_started or not attempt_preexisting
                closure = {
                    "scheduled": item,
                    "source_digest": source_digest,
                    "status": (
                        "NOT_STARTED_FAILURE"
                        if not_started
                        else "FAILED_TECHNICAL"
                    ),
                    "result": None,
                }
                if not not_started:
                    closure["error"] = {
                        "type": "PublicationFailure",
                        "message": "result envelope was not durably published",
                    }
                failure_closure_started = True
                publisher.publish(result_name, closure)
                recovered.append(closure)
        return recovered

    if bootstrap_failed:
        try:
            records = recover_schedule("BOOTSTRAP_PUBLICATION_FAILURE")
        except Exception as closure_error:
            raise RuntimeError(
                "persistent publication failure while closing unstarted schedule"
            ) from closure_error
    else:
        try:
            records, dispositions, failure = execute_cascade(
                proposal,
                source_digest=source_digest,
                before_attempt=before,
                after_result=after,
                check_source=check_source,
            )
        except Exception as error:
            failure = {
                **_error(error),
                "phase": "CASCADE_OR_PUBLICATION",
                "publication_context": dict(publication_context),
            }
            # No game/search call is repeated.  If storage still works, recover
            # any atomically written envelope and close every missing slot.
            try:
                records = recover_schedule("PUBLICATION_FAILURE")
            except Exception as closure_error:
                failure = {
                    "type": "PublicationRecoveryFailure",
                    "message": "could not publish all remaining failure closures",
                    "primary": failure,
                    "recovery": _error(closure_error),
                }

    try:
        rebuilt_dispositions, rebuilt_failure, saved_source_digest = classify_saved_records(
            proposal, records, external_failure=failure
        )
        if saved_source_digest != source_digest:
            raise ValueError("saved cascade source digest differs")
        dispositions = rebuilt_dispositions
        if rebuilt_failure is not None:
            if failure is None:
                failure = rebuilt_failure
            elif failure != rebuilt_failure:
                failure = {
                    "type": "MultipleTechnicalFailures",
                    "message": "publication and reconstructed cascade both failed",
                    "primary": failure,
                    "saved_cascade": rebuilt_failure,
                }
    except Exception as error:
        validation_failure = {**_error(error), "phase": "SAVED_CASCADE_VALIDATION"}
        failure = (
            validation_failure
            if failure is None
            else {
                "type": "MultipleTechnicalFailures",
                "message": "cascade/publication and saved validation both failed",
                "primary": failure,
                "saved_validation": validation_failure,
            }
        )

    verification_error = None
    try:
        check_source()
        if any(_sha256((output / name).read_bytes()) != digest for name, digest in publisher.sha256.items()):
            raise ValueError("published Plan0030 artifact drift")
    except Exception as error:
        verification_error = {**_error(error), "phase": "SOURCE_VERIFICATION"}
        failure = (
            verification_error
            if failure is None
            else {
                "type": "MultipleTechnicalFailures",
                "message": "cascade/publication and source verification both failed",
                "primary": failure,
                "source_verification": verification_error,
            }
        )
    if verification_error is None:
        try:
            publisher.publish(
                "source-verification.json",
                {
                    "source": source,
                    "matched": True,
                    "publication_sha256": dict(publisher.sha256),
                },
            )
        except Exception as error:
            verification_error = {
                **_error(error),
                "phase": "SOURCE_VERIFICATION_PUBLICATION",
                "durable_envelope": "source-verification.json"
                in publisher.sha256,
            }
            failure = (
                verification_error
                if failure is None
                else {
                    "type": "MultipleTechnicalFailures",
                    "message": "earlier and source-verification publication failures",
                    "primary": failure,
                    "source_verification_publication": verification_error,
                }
            )

    def combine_failure(primary, event, message, field):
        if primary is None:
            return event
        return {
            "type": "MultipleTechnicalFailures",
            "message": message,
            "primary": primary,
            field: event,
        }

    def publish_failure_artifact(current_failure):
        """Publish failure.json and retain a one-shot publication exception."""

        name = "failure.json"
        attempted_digest = _sha256(canonical_bytes(current_failure))
        try:
            publisher.publish(name, current_failure)
            return current_failure
        except Exception as error:
            durable = name in publisher.sha256
            path = output / name
            if not durable and path.exists():
                saved = publisher.adopt(name)
                if saved != current_failure:
                    raise ValueError("durable failure payload differs") from error
                durable = True
            publication_failure = {
                **_error(error),
                "phase": "FAILURE_PUBLICATION",
                "durable_envelope": durable,
                "attempted_failure_sha256": attempted_digest,
            }
            combined = combine_failure(
                current_failure,
                publication_failure,
                "earlier failure and failure-artifact publication both failed",
                "failure_publication",
            )
            if not durable:
                # A pre-write one-shot failure left the immutable path unused;
                # publish the augmented failure exactly once at that path.
                publisher.publish(name, combined)
            return combined

    # The verification map intentionally covers the complete 56-pair evidence
    # existing before this later failure/summary closeout layer.
    if failure is not None:
        failure = publish_failure_artifact(failure)

    summary = summarize(records, dispositions, failure, publication={
        "files_before_summary": len(publisher.sha256),
        "bytes_before_summary": publisher.bytes,
        "maximum_files": MAX_FILES,
        "maximum_bytes": MAX_PUBLISHED_BYTES,
    })
    try:
        publisher.publish("summary.json", summary)
    except Exception as error:
        summary_failure = {**_error(error), "phase": "SUMMARY_PUBLICATION"}
        failure = (
            summary_failure
            if failure is None
            else {
                "type": "MultipleTechnicalFailures",
                "message": "earlier failure and summary publication both failed",
                "primary": failure,
                "summary_publication": summary_failure,
            }
        )
        if "failure.json" not in publisher.sha256:
            failure = publish_failure_artifact(failure)
        summary = summarize(
            records,
            dispositions,
            failure,
            publication={
                "files_before_summary": len(publisher.sha256),
                "bytes_before_summary": publisher.bytes,
                "maximum_files": MAX_FILES,
                "maximum_bytes": MAX_PUBLISHED_BYTES,
            },
        )
        fallback_name = "summary-publication-failure.json"
        try:
            publisher.publish(fallback_name, summary)
        except Exception as fallback_error:
            durable = fallback_name in publisher.sha256
            fallback_path = output / fallback_name
            if not durable and fallback_path.exists():
                saved = publisher.adopt(fallback_name)
                if saved != summary:
                    raise ValueError("durable fallback summary differs") from fallback_error
                durable = True
            if not durable:
                fallback_failure = {
                    **_error(fallback_error),
                    "phase": "SUMMARY_FALLBACK_PUBLICATION",
                    "durable_envelope": False,
                }
                failure = combine_failure(
                    failure,
                    fallback_failure,
                    "earlier failure and fallback-summary publication both failed",
                    "fallback_summary_publication",
                )
                summary = summarize(
                    records,
                    dispositions,
                    failure,
                    publication={
                        "files_before_summary": len(publisher.sha256),
                        "bytes_before_summary": publisher.bytes,
                        "maximum_files": MAX_FILES,
                        "maximum_bytes": MAX_PUBLISHED_BYTES,
                    },
                )
                publisher.publish(fallback_name, summary)
    return summary


def audit_run(repository, registered_commit, output=None):
    """Read-only saved/source audit; it performs no game/search/BFS computation."""

    repository = Path(repository)
    output = repository / OUTPUT if output is None else Path(output)
    proposal = load_proposal(repository)
    schedule = make_schedule(proposal)
    run_attempt = read_json(output / "run-attempt.json")
    manifest = read_json(output / "manifest.json")
    source = source_snapshot(repository)
    if (
        run_attempt.get("source") != source
        or run_attempt.get("protocol") != PROTOCOL
        or type(run_attempt.get("started_at")) is not str
        or source.get("git_commit") != registered_commit
        or manifest.get("source") != source
        or manifest.get("source_digest") != _source_digest(source)
        or manifest.get("protocol") != PROTOCOL
        or manifest.get("proposal_sha256") != PROPOSAL_SHA256
        or manifest.get("proposal") != proposal
        or manifest.get("schedule") != schedule
        or manifest.get("resource_ceilings") != RESOURCE_CEILINGS
        or manifest.get("acceptance") != "PROVISIONAL_UNTIL_FULL_REGRESSION"
        or manifest.get("direct_dependencies") != dependency_snapshot(source)
    ):
        raise ValueError("saved manifest/source audit differs")
    records = []
    expected_files = {"run-attempt.json", "manifest.json"}
    bfs_result_names = set()
    for item in schedule:
        attempt_name = "attempts/{:04d}-attempt.json".format(item["ordinal"])
        result_name = "attempts/{:04d}-result.json".format(item["ordinal"])
        if item["kind"] == "bfs_prefix":
            bfs_result_names.add(result_name)
        attempt = read_json(output / attempt_name)
        record = read_json(output / result_name)
        if (
            attempt.get("scheduled") != item
            or attempt.get("source_digest") != manifest["source_digest"]
            or type(attempt.get("started_at")) is not str
        ):
            raise ValueError("saved attempt differs from schedule/source")
        if record.get("scheduled") != item or record.get("source_digest") != manifest["source_digest"]:
            raise ValueError("saved result differs from schedule/source")
        records.append(record)
        expected_files.update((attempt_name, result_name))

    failure_path = output / "failure.json"
    saved_failure = read_json(failure_path) if failure_path.exists() else None
    if saved_failure is not None:
        expected_files.add("failure.json")

    dispositions, cascade_failure, record_source_digest = classify_saved_records(
        proposal, records, external_failure=saved_failure
    )
    if record_source_digest != manifest["source_digest"]:
        raise ValueError("saved result/manifest source digests differ")

    summary_path = output / "summary.json"
    fallback_path = output / "summary-publication-failure.json"
    if not summary_path.exists() and not fallback_path.exists():
        raise ValueError("a final summary artifact is required")
    summary_name = (
        "summary-publication-failure.json"
        if fallback_path.exists()
        else "summary.json"
    )
    summary = read_json(output / summary_name)
    expected_files.add(summary_name)
    primary_summary = None
    if summary_name == "summary-publication-failure.json" and summary_path.exists():
        primary_summary = read_json(summary_path)
        expected_files.add("summary.json")
    effective_failure = summary.get("failure")

    def contains_failure(container, expected):
        if container == expected:
            return True
        if type(container) is dict:
            return any(contains_failure(value, expected) for value in container.values())
        if type(container) is list:
            return any(contains_failure(value, expected) for value in container)
        return False

    def phase_events(value, phase):
        found = []
        if type(value) is dict:
            if value.get("phase") == phase:
                found.append(value)
            for child in value.values():
                found.extend(phase_events(child, phase))
        elif type(value) is list:
            for child in value:
                found.extend(phase_events(child, phase))
        return found

    def contains_phase(value, phase):
        return bool(phase_events(value, phase))

    failure_locus = next(
        (
            record["scheduled"]["ordinal"]
            for record in records
            if record.get("status")
            in ("FAILED_TECHNICAL", "NOT_STARTED_FAILURE")
        ),
        None,
    )
    failure_locus_status = (
        None if failure_locus is None else records[failure_locus].get("status")
    )

    def valid_cascade_publication_event(event):
        context = event.get("publication_context")
        if (
            type(context) is not dict
            or set(context) != {"phase", "ordinal"}
            or context.get("phase")
            not in ("ATTEMPT_PUBLICATION", "RESULT_PUBLICATION")
            or type(context.get("ordinal")) is not int
            or not 0 <= context["ordinal"] < MAX_ATTEMPTS
        ):
            return False
        ordinal = context["ordinal"]
        if failure_locus is None:
            return (
                context["phase"] == "RESULT_PUBLICATION"
                and ordinal == 55
                and records[ordinal].get("status")
                not in ("FAILED_TECHNICAL", "NOT_STARTED_FAILURE")
            )
        if failure_locus_status == "NOT_STARTED_FAILURE":
            if context["phase"] == "ATTEMPT_PUBLICATION":
                return ordinal == failure_locus
            return ordinal == failure_locus - 1
        if ordinal < failure_locus:
            return False
        local_status = records[ordinal].get("status")
        if context["phase"] == "ATTEMPT_PUBLICATION":
            return local_status in ("FAILED_TECHNICAL", "NOT_STARTED_FAILURE")
        if local_status in ("FAILED_TECHNICAL", "NOT_STARTED_FAILURE"):
            return True
        return ordinal == 55 or records[ordinal + 1].get("status") == "NOT_STARTED_FAILURE"

    cascade_publication_events = phase_events(
        saved_failure, "CASCADE_OR_PUBLICATION"
    )
    if any(
        not valid_cascade_publication_event(event)
        for event in cascade_publication_events
    ):
        raise ValueError("cascade publication context differs from failure locus")

    verification_exists = (output / "source-verification.json").exists()
    source_verification_events = phase_events(
        saved_failure, "SOURCE_VERIFICATION"
    )
    source_publication_events = phase_events(
        saved_failure, "SOURCE_VERIFICATION_PUBLICATION"
    )
    if source_verification_events and verification_exists:
        raise ValueError("source verification failure has a verification artifact")
    if any(
        type(event.get("durable_envelope")) is not bool
        or event["durable_envelope"] != verification_exists
        for event in source_publication_events
    ):
        raise ValueError("source-verification publication topology differs")

    bootstrap_events = phase_events(saved_failure, "BOOTSTRAP_PUBLICATION")
    if any(
        event.get("publication_path")
        not in ("run-attempt.json", "manifest.json")
        or type(event.get("durable_envelope")) is not bool
        for event in bootstrap_events
    ):
        raise ValueError("bootstrap publication failure is malformed")

    failure_publication_events = phase_events(
        effective_failure, "FAILURE_PUBLICATION"
    )
    if any(
        type(event.get("durable_envelope")) is not bool
        or type(event.get("attempted_failure_sha256")) is not str
        or re.fullmatch(
            r"[0-9a-f]{64}", event["attempted_failure_sha256"]
        ) is None
        for event in failure_publication_events
    ):
        raise ValueError("failure-artifact publication event is malformed")

    if (effective_failure is None) != (saved_failure is None):
        raise ValueError("summary/failure artifact presence differs")
    if cascade_failure is not None and not contains_failure(effective_failure, cascade_failure):
        raise ValueError("cascade failure is absent from the summary")
    if saved_failure is not None and not contains_failure(effective_failure, saved_failure):
        raise ValueError("failure artifact is absent from the summary")

    # A saved failure must be anchored either in an independently reconstructible
    # FAILED_TECHNICAL record, in the first external-failure closure, or in one
    # of the narrowly defined post-cascade publication phases.
    if saved_failure is not None:
        if failure_locus_status == "FAILED_TECHNICAL":
            if cascade_failure is None or not contains_failure(
                saved_failure, cascade_failure
            ):
                raise ValueError("saved failure is not anchored to its record")
        elif failure_locus_status == "NOT_STARTED_FAILURE":
            bootstrap_anchor = bool(bootstrap_events) and failure_locus == 0
            cascade_anchor = any(
                valid_cascade_publication_event(event)
                for event in cascade_publication_events
            )
            if not (bootstrap_anchor or cascade_anchor):
                raise ValueError("external failure closure lacks its event locus")
        else:
            source_anchor = bool(
                source_verification_events or source_publication_events
            )
            summary_anchor = (
                summary_name == "summary-publication-failure.json"
                and contains_phase(saved_failure, "SUMMARY_PUBLICATION")
            )
            last_result_anchor = any(
                valid_cascade_publication_event(event)
                for event in cascade_publication_events
            )
            if not (source_anchor or summary_anchor or last_result_anchor):
                raise ValueError("saved failure lacks an allowed late-phase anchor")
    if summary_name == "summary-publication-failure.json" and (
        type(effective_failure) is not dict
        or "SUMMARY_PUBLICATION" not in json.dumps(effective_failure, sort_keys=True)
    ):
        raise ValueError("summary-publication fallback lacks its technical failure")
    if summary_name == "summary.json" and effective_failure != saved_failure:
        saved_digest = (
            None
            if saved_failure is None
            else _sha256(canonical_bytes(saved_failure))
        )
        if not any(
            event.get("durable_envelope") is True
            and event.get("attempted_failure_sha256") == saved_digest
            for event in failure_publication_events
        ):
            raise ValueError("ordinary summary/failure artifact values differ")
    expected_summary = summarize(
        records,
        dispositions,
        effective_failure,
        publication=summary.get("publication"),
    )
    if summary != expected_summary:
        raise ValueError("saved summary/gates/resources differ")
    if primary_summary is not None:
        expected_primary = summarize(
            records,
            dispositions,
            primary_summary.get("failure"),
            publication=primary_summary.get("publication"),
        )
        if primary_summary != expected_primary:
            raise ValueError("durable pre-error summary differs")

    verification_path = output / "source-verification.json"
    verification = None
    if verification_path.exists():
        verification = read_json(verification_path)
        expected_files.add("source-verification.json")
        if verification.get("source") != source or verification.get("matched") is not True:
            raise ValueError("saved source verification differs")
    else:
        if not (
            contains_phase(effective_failure, "SOURCE_VERIFICATION")
            or contains_phase(
                effective_failure, "SOURCE_VERIFICATION_PUBLICATION"
            )
        ):
            raise ValueError("source verification is absent without its recorded failure")

    actual_files = {
        str(path.relative_to(output)) for path in output.rglob("*") if path.is_file()
    }
    if actual_files != expected_files or len(actual_files) > MAX_FILES:
        raise ValueError("run artifact file set differs")
    total = 0
    for name in sorted(actual_files):
        raw = (output / name).read_bytes()
        cap = MAX_BFS_BYTES if name in bfs_result_names else MAX_OTHER_BYTES
        if len(raw) > cap:
            raise ValueError("saved artifact exceeds its envelope cap")
        total += len(raw)
    if total > MAX_PUBLISHED_BYTES:
        raise ValueError("saved publication total exceeds ceiling")
    before_summary_names = actual_files - {summary_name}
    before_summary_bytes = sum(
        len((output / name).read_bytes()) for name in before_summary_names
    )
    if summary.get("publication") != {
        "files_before_summary": len(before_summary_names),
        "bytes_before_summary": before_summary_bytes,
        "maximum_files": MAX_FILES,
        "maximum_bytes": MAX_PUBLISHED_BYTES,
    }:
        raise ValueError("summary publication accounting differs from saved bytes")
    if primary_summary is not None:
        primary_before_names = actual_files - {
            "summary.json",
            "summary-publication-failure.json",
        }
        if primary_summary.get("failure") is None:
            primary_before_names.discard("failure.json")
        primary_before_bytes = sum(
            len((output / name).read_bytes()) for name in primary_before_names
        )
        if primary_summary.get("publication") != {
            "files_before_summary": len(primary_before_names),
            "bytes_before_summary": primary_before_bytes,
            "maximum_files": MAX_FILES,
            "maximum_bytes": MAX_PUBLISHED_BYTES,
        }:
            raise ValueError("durable pre-error summary publication facts differ")
    if verification is not None:
        hashes = verification.get("publication_sha256")
        verified_names = actual_files - {
            "source-verification.json",
            "failure.json",
            "summary.json",
            "summary-publication-failure.json",
        }
        if type(hashes) is not dict or set(hashes) != verified_names:
            raise ValueError("source-verification publication coverage differs")
        for name, digest in hashes.items():
            if _sha256((output / name).read_bytes()) != digest:
                raise ValueError("saved publication digest differs")
    return {
        "status": "PASS",
        "protocol": PROTOCOL,
        "records": len(records),
        "files": len(actual_files),
        "published_bytes": total,
        "production_calls": 0,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "audit"))
    parser.add_argument("--registered-commit", required=True)
    arguments = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    if arguments.command == "audit":
        result = audit_run(repository, arguments.registered_commit)
    else:
        result = run_pilot(repository, arguments.registered_commit)
    print(json.dumps(result, sort_keys=True))
    if arguments.command == "audit":
        return 0 if result.get("status") == "PASS" else 1
    return 0 if result.get("execution_status") == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
