"""One preregistered candidate, fixed finite cascade, and no retries."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess

from parity_forge.dsl import (
    InitialPiece,
    Player,
    canonical_json,
    definition_hash,
    parse_definition,
)
from parity_forge.engine import (
    GameState,
    action_from_dict,
    goal_satisfied,
    initial_state,
    legal_actions,
)
from parity_forge.play import _wilson_interval
from scripts import plan0028_play as play_adapter
from scripts.plan0020_pilot import exact_one, _publish, _utc


PLAN = "docs/plans/active/0028-two-current-cross-weave-screen.md"
DATA = "experiments/proposals/two-current-cross-weave-v0.json"
PROTOCOL = "plan0028-two-current-cross-weave-v1"
HASH = "c84f8cf6c01adb1e13f0668dd97cfc75112f63c4e5b0dbae89a22ea8e6e3100a"
PROPOSAL_SHA256 = (
    "eb4adfdab51b5441fae5c72af9d548884537665e74f978249d07a0866bc9582a"
)
EXPOSURE = (
    "SOURCE_DESIGNED_AFTER_PLAN0027_AND_FOUR_REJECTED_PRESELECTION_WIRES_"
    "WITH_ROOT_ENGINE_AND_INDEPENDENT_BOUNDED_AND_OR_AND_REACHABLE_STATE_"
    "LOWER_BOUND_EXPOSED_NOT_CONFIRMATION"
)
PROPOSAL_STATUS = "FIXED_PROSPECTIVE_NOT_REGISTERED_NOT_PRODUCTION_EXECUTED"
MAX_NODES = MAX_STATES = 100000
INITIAL_PHI = BOUND = 50
PLY_LIMIT = 51
BOARD_SIZE = 5
INITIAL_MOBILITY = {"A": 8, "B": 7}
POLICY_IDENTITIES = {
    "T2": "terminal_only_minimax-v1-depth2",
    "T3": "terminal_only_minimax-v1-depth3",
    "H2": "minimax-v1-depth2",
    "H3": "minimax-v1-depth3",
    "G": "goal_directed-v1-medium",
}
DECISION_NODE_BOUNDS = {"T2": 110, "T3": 1110, "H2": 110, "H3": 1110, "G": 0}
ROLE_GAME_NODE_BOUNDS = {"T2": 2750, "T3": 27750, "H2": 2750, "H3": 27750, "G": 0}
STRUCTURAL_CHARGED_NODES_BOUND = 3596000
CONFIGURED_CHARGED_NODES_CEILING = 16000000
MAX_OUTPUT_FILES = 168
MAX_OUTPUT_FILE_BYTES = 64 * 1024 * 1024
CELLS = (
    ("base", "H3", "H3", 1100, 16),
    ("base", "T3", "T3", 1100, 16),
    ("confirm", "H3", "H3", 1200, 16),
    ("sensitivity", "H3", "H2", 1200, 8),
    ("sensitivity", "H2", "H3", 1200, 8),
    ("simple", "H3", "G", 1200, 8),
    ("simple", "G", "H3", 1200, 8),
)
PLANNED_GAMES = sum(cell[4] for cell in CELLS)
PLANNED_ATTEMPTS = PLANNED_GAMES + 1


def source_snapshot(repository, clean=False):
    """Pin every tracked Python file together with the active plan and wire."""

    repository = Path(repository)

    def git(*args):
        return subprocess.check_output(
            ("git", "-C", str(repository), *args), text=True
        ).strip()

    if clean and git("status", "--porcelain"):
        raise ValueError("clean registered worktree required")
    tracked = git("ls-files").splitlines()
    paths = sorted(
        path
        for path in tracked
        if path.endswith(".py") or path in (PLAN, DATA)
    )
    if not {PLAN, DATA}.issubset(paths):
        raise ValueError("active plan and proposal must be registered")
    if any(
        path.endswith(".py")
        for path in git(
            "ls-files", "--others", "--exclude-standard"
        ).splitlines()
    ):
        raise ValueError("untracked Python source")
    return {
        "git_commit": git("rev-parse", "HEAD"),
        "sha256": {
            path: hashlib.sha256((repository / path).read_bytes()).hexdigest()
            for path in paths
        },
    }


def load_definition(repository):
    """Read and statically validate the one fixed canonical wire."""

    path = Path(repository) / DATA
    raw_bytes = path.read_bytes()
    if hashlib.sha256(raw_bytes).hexdigest() != PROPOSAL_SHA256:
        raise ValueError("wrong preregistered proposal bytes")
    payload = json.loads(raw_bytes)
    if (
        type(payload) is not dict
        or set(payload) != {"status", "exposure", "definitions"}
        or payload.get("status") != PROPOSAL_STATUS
        or payload.get("exposure") != EXPOSURE
    ):
        raise ValueError("wrong preregistered proposal metadata")
    rows = payload["definitions"]
    if type(rows) is not list or len(rows) != 1:
        raise ValueError("exactly one fixed definition required")
    raw = rows[0]
    definition = parse_definition(raw)
    if (
        definition_hash(definition) != HASH
        or json.loads(canonical_json(definition)) != raw
        or raw["first_player"] != "A"
        or raw["max_plies"] != PLY_LIMIT
    ):
        raise ValueError("wrong preregistered canonical wire")
    state = initial_state(definition)
    occupied = _state_pieces(
        state.to_dict(), terminal=False, board_size=definition.board_size
    )
    other = GameState(
        ply=0,
        to_move=Player.B,
        pieces=state.pieces,
        outcome=None,
    )
    if (
        state.terminal
        or _phi(occupied, definition.board_size) != INITIAL_PHI
        or {
            "A": len(legal_actions(definition, state)),
            "B": len(legal_actions(definition, other)),
        }
        != INITIAL_MOBILITY
    ):
        raise ValueError("wrong initial proof or mobility facts")
    return raw


def schedule():
    """Materialize all 81 potential attempts before any computation."""

    base = {"first_player": "A", "definition_hash": HASH}
    items = [dict(base, kind="exact", max_states=MAX_STATES)]
    for cell, (stage, policy_a, policy_b, start, count) in enumerate(CELLS):
        items.extend(
            dict(
                base,
                kind="game",
                cell=cell,
                stage=stage,
                policy_a=policy_a,
                policy_b=policy_b,
                seed=seed,
                max_nodes_per_role=MAX_NODES,
            )
            for seed in range(start, start + count)
        )
    if len(items) != PLANNED_ATTEMPTS:
        raise ValueError("wrong fixed attempt count")
    return items


def _position(value, label, board_size=BOARD_SIZE):
    if (
        type(value) is not list
        or len(value) != 2
        or any(type(coordinate) is not int for coordinate in value)
    ):
        raise ValueError("invalid {} position".format(label))
    position = tuple(value)
    if any(not 0 <= coordinate < board_size for coordinate in position):
        raise ValueError("{} position is outside the fixed board".format(label))
    return position


def _state_pieces(state, *, terminal, board_size=BOARD_SIZE):
    """Validate one saved candidate state and return its complete occupancy."""

    if (
        type(state) is not dict
        or set(state) != {"ply", "to_move", "pieces", "outcome"}
        or type(state.get("ply")) is not int
        or state.get("to_move") not in ("A", "B")
        or type(state.get("pieces")) is not list
    ):
        raise ValueError("invalid saved candidate state")
    outcome = state.get("outcome")
    if terminal:
        if (
            type(outcome) is not dict
            or set(outcome) != {"winner", "reason"}
            or outcome.get("winner") not in ("A", "B")
            or outcome.get("reason") not in ("GOAL", "NO_LEGAL_ACTION")
        ):
            raise ValueError("invalid saved terminal outcome")
    elif outcome is not None:
        raise ValueError("decision input must be nonterminal")

    occupied = {}
    serialized_order = []
    for piece in state["pieces"]:
        if (
            type(piece) is not dict
            or set(piece) != {"owner", "piece", "position"}
            or piece.get("owner") not in ("A", "B")
            or piece.get("piece")
            != ("a" if piece.get("owner") == "A" else "b")
        ):
            raise ValueError("invalid saved decision piece")
        position = _position(piece.get("position"), "piece", board_size)
        if position in occupied:
            raise ValueError("duplicate saved decision position")
        occupied[position] = (piece["owner"], piece["piece"])
        serialized_order.append((position, piece["owner"], piece["piece"]))
    if serialized_order != sorted(serialized_order):
        raise ValueError("saved pieces are not canonical")
    return occupied


def _phi(occupied, board_size=BOARD_SIZE):
    return sum(
        board_size - 1 - position[1]
        if owner == "A"
        else 2 * position[0]
        for position, (owner, _piece) in occupied.items()
    )


def _live_state(ply, to_move, occupied):
    """Build one canonical nonterminal state from already validated saved data."""

    pieces = tuple(
        InitialPiece(owner=Player(owner), piece=piece, position=position)
        for position, (owner, piece) in sorted(occupied.items())
    )
    return GameState(
        ply=ply,
        to_move=Player(to_move),
        pieces=pieces,
        outcome=None,
    )


def _terminal_fact(definition, actor, next_ply, occupied):
    """Evaluate terminal order without replaying or applying a saved action."""

    candidate = _live_state(next_ply, actor.other.value, occupied)
    if goal_satisfied(definition, candidate.pieces, actor):
        return actor.value, "GOAL"
    if goal_satisfied(definition, candidate.pieces, actor.other):
        return actor.other.value, "GOAL"
    if next_ply >= definition.max_plies:
        return None, "PLY_LIMIT"
    if not legal_actions(definition, candidate):
        return actor.value, "NO_LEGAL_ACTION"
    return None


def _candidate_action(actor, raw_action, occupied, board_size=BOARD_SIZE):
    """Validate one recorded legal action and return its realized-effect bit."""

    try:
        action = action_from_dict(raw_action)
    except Exception as error:
        raise ValueError("invalid candidate action") from error
    if action.to_dict() != raw_action:
        raise ValueError("candidate action is not canonical")
    origin = action.from_position
    target = action.to_position
    if origin is None:
        raise ValueError("candidate action requires an origin")
    _position(list(origin), "action from", board_size)
    _position(list(target), "action to", board_size)
    expected_piece = "a" if actor == "A" else "b"
    if occupied.get(origin) != (actor, expected_piece):
        raise ValueError("saved actor does not occupy action origin")

    vector = (target[0] - origin[0], target[1] - origin[1])
    if actor == "A":
        if action.kind.value != "HOP" or target in occupied:
            raise ValueError("invalid A HOP action")
        ordinary = ((0, 1), (1, 1))
        if vector in ordinary:
            return False
        doubled = tuple((2 * row, 2 * column) for row, column in ordinary)
        if vector not in doubled:
            raise ValueError("A HOP has an impossible vector")
        step = (vector[0] // 2, vector[1] // 2)
        intermediate = (origin[0] + step[0], origin[1] + step[1])
        if intermediate not in occupied:
            raise ValueError("two-step A HOP lacks an occupied intermediate")
        return True

    if action.kind.value != "PUSH" or vector not in ((-1, -1), (-1, 0)):
        raise ValueError("invalid B PUSH action")
    target_piece = occupied.get(target)
    if target_piece is None:
        return False
    if target_piece[0] != "A":
        raise ValueError("B PUSH targets a friendly piece")
    landing = (target[0] + vector[0], target[1] + vector[1])
    _position(list(landing), "pushed piece landing", board_size)
    if landing in occupied:
        raise ValueError("B PUSH landing is occupied")
    return True


def _apply_candidate_action(
    actor, raw_action, occupied, board_size=BOARD_SIZE
):
    """Apply the already validated local HOP/PUSH transition to an occupancy."""

    actual = _candidate_action(actor, raw_action, occupied, board_size)
    action = action_from_dict(raw_action)
    origin = action.from_position
    target = action.to_position
    assert origin is not None
    updated = dict(occupied)
    moving = updated.pop(origin)
    if actor == "B" and actual:
        vector = (target[0] - origin[0], target[1] - origin[1])
        pushed = updated.pop(target)
        updated[(target[0] + vector[0], target[1] + vector[1])] = pushed
    updated[target] = moving
    return updated, actual


def _validate_decision(item, decision, definition, expected_state):
    """Validate one exact engine state, its canonical choices, and accounting."""

    if type(decision) is not dict or expected_state.terminal:
        raise ValueError("invalid decision record or terminal decision")
    actor = expected_state.to_move.value
    state = decision.get("input_state")
    if state != expected_state.to_dict():
        raise ValueError("saved decision input differs from the applied prefix")
    occupied = _state_pieces(
        state, terminal=False, board_size=definition.board_size
    )
    if (
        decision.get("ply") != expected_state.ply
        or decision.get("actor") != actor
        or type(decision.get("legal_action_count")) is not int
        or decision["legal_action_count"] < 1
        or type(decision.get("legal_actions")) is not list
        or len(decision["legal_actions"]) != decision["legal_action_count"]
    ):
        raise ValueError("invalid saved decision input or legal-action count")

    expected_legal = [
        action.to_dict() for action in legal_actions(definition, expected_state)
    ]
    if (
        len(expected_legal) > 10
        or decision["legal_actions"] != expected_legal
    ):
        raise ValueError("legal actions differ from the canonical engine tuple")
    for raw_action in decision["legal_actions"]:
        _candidate_action(
            actor, raw_action, occupied, definition.board_size
        )

    status = decision.get("selection_status")
    selected = decision.get("selected_action")
    if status == "SELECTED":
        if selected not in expected_legal:
            raise ValueError("selected action is absent from legal actions")
    elif status == "UNKNOWN_CENSORED":
        if selected is not None:
            raise ValueError("censored decision has an unconfirmed selection")
    else:
        raise ValueError("invalid decision selection status")

    policy = item["policy_" + actor.lower()]
    before = decision.get("nodes_before")
    after = decision.get("nodes_after")
    charged = decision.get("charged_nodes")
    if (
        type(before) is not int
        or type(after) is not int
        or type(charged) is not int
        or not 0 <= before <= after <= item["max_nodes_per_role"]
        or charged != after - before
        or charged > DECISION_NODE_BOUNDS[policy]
        or (policy == "G" and (before, after, charged) != (0, 0, 0))
    ):
        raise ValueError("invalid per-decision node accounting")

    if policy.startswith("T"):
        values = decision.get("last_action_values")
        expected_values = expected_legal if status == "SELECTED" else []
        if (
            type(values) is not list
            or len(values) != len(expected_values)
            or any(
                type(value) is not dict
                or set(value) != {"action", "value"}
                or value.get("action") != legal
                or type(value.get("value")) is not int
                or value["value"] not in (-1, 0, 1)
                for value, legal in zip(values, expected_values)
            )
        ):
            raise ValueError("invalid terminal-only action values")
    elif "last_action_values" in decision:
        raise ValueError("non-terminal-only decision exposes action values")
    return occupied, before, after


def _trace_evidence(item, result, raw):
    """Check saved adjacent states locally, without a second engine replay."""

    definition = parse_definition(raw)
    if definition_hash(definition) != item["definition_hash"]:
        raise ValueError("trace definition differs from the schedule")
    state = initial_state(definition)
    if state.terminal or state.ply != 0 or state.to_move is not Player.A:
        raise ValueError("fixed initial state must be live with A to move")

    actions = result.get("actions")
    decisions = result.get("decisions")
    plies = result.get("plies")
    complete = result.get("status") == "COMPLETE"
    expected_decisions = plies if complete else plies + 1
    if (
        type(actions) is not list
        or type(decisions) is not list
        or type(plies) is not int
        or not 0 <= plies <= BOUND
        or len(actions) != plies
        or len(decisions) != expected_decisions
        or (complete and plies == 0)
        or result.get("unconfirmed_action") is not None
    ):
        raise ValueError("invalid complete/censored decision prefix")

    realized = {"A": False, "B": False}
    node_cursor = {"A": 0, "B": 0}
    for ply, action in enumerate(actions):
        decision = decisions[ply]
        actor = state.to_move.value
        occupied, before_nodes, after_nodes = _validate_decision(
            item, decision, definition, state
        )
        if (
            decision.get("selection_status") != "SELECTED"
            or decision.get("selected_action") != action
            or before_nodes != node_cursor[actor]
        ):
            raise ValueError("decision does not match the applied action")
        node_cursor[actor] = after_nodes

        locally_updated, actual = _apply_candidate_action(
            actor, action, occupied, definition.board_size
        )
        has_next_decision = ply + 1 < len(decisions)
        next_saved = (
            decisions[ply + 1].get("input_state")
            if has_next_decision
            else result.get("state_after_prefix")
        )
        next_occupied = _state_pieces(
            next_saved,
            terminal=not has_next_decision,
            board_size=definition.board_size,
        )
        next_ply = state.ply + 1
        terminal_fact = _terminal_fact(
            definition, state.to_move, next_ply, locally_updated
        )
        if (
            next_saved.get("ply") != next_ply
            or next_saved.get("to_move") != state.to_move.other.value
            or locally_updated != next_occupied
            or (has_next_decision and terminal_fact is not None)
            or (
                not has_next_decision
                and terminal_fact
                != (
                    next_saved["outcome"]["winner"],
                    next_saved["outcome"]["reason"],
                )
            )
        ):
            raise ValueError("saved adjacent states differ from the local transition")
        if _phi(next_occupied, definition.board_size) >= _phi(
            occupied, definition.board_size
        ):
            raise ValueError("candidate Phi did not strictly decrease")
        realized[actor] = realized[actor] or actual
        if has_next_decision:
            state = _live_state(
                next_saved["ply"], next_saved["to_move"], next_occupied
            )
            if state.to_dict() != next_saved:
                raise ValueError("saved next decision state is not canonical")

    if complete:
        terminal_state = result.get("state_after_prefix")
        outcome = terminal_state.get("outcome")
        if (
            terminal_state.get("ply") != plies
            or outcome.get("winner") != result.get("winner")
            or outcome.get("reason") != result.get("terminal_reason")
        ):
            raise ValueError("completed terminal state differs from the saved result")
    else:
        trailing = decisions[-1]
        actor = state.to_move.value
        _occupied, before_nodes, after_nodes = _validate_decision(
            item, trailing, definition, state
        )
        if (
            trailing.get("selection_status") != "UNKNOWN_CENSORED"
            or trailing.get("selected_action") is not None
            or before_nodes != node_cursor[actor]
            or result.get("state_after_prefix") != state.to_dict()
            or result.get("censor", {}).get("role") != actor
        ):
            raise ValueError("invalid terminal censored decision")
        node_cursor[actor] = after_nodes

    nodes = result.get("nodes_by_role")
    for actor in ("A", "B"):
        policy = item["policy_" + actor.lower()]
        if (
            node_cursor[actor] != nodes.get(actor)
            or node_cursor[actor] > ROLE_GAME_NODE_BOUNDS[policy]
        ):
            raise ValueError("role-game structural node bound violated")
    return {"realized_effect": realized}


def game_evidence(item, result, raw):
    """Validate a complete applied trace and derive interaction evidence."""

    if item.get("kind") != "game" or result.get("status") != "COMPLETE":
        raise ValueError("evidence requires one complete scheduled game")
    return _trace_evidence(item, result, raw)


def validate_result(item, result, raw):
    """Reject drift, failed evidence, bad replay, or proof-bound violations."""

    if type(result) is not dict:
        raise ValueError("result must be a record")
    game = item["kind"] == "game"
    complete = result.get("status") == "COMPLETE"
    keys = (
        ("first_player", "policy_a", "policy_b", "seed", "max_nodes_per_role")
        if game
        else ("max_states",)
    )
    if result.get("status") not in ("COMPLETE", "UNKNOWN_CENSORED") or any(
        result.get(key) != item[key] for key in keys + ("definition_hash",)
    ):
        raise ValueError("failed record or scheduled condition drift")
    if result.get("replay_count") != int(game or complete):
        raise ValueError("wrong single-replay count")
    if game and result.get("replay_verified") is not True:
        raise ValueError("game prefix replay was not verified")

    if game:
        if (
            type(result.get("plies")) is not int
            or type(result.get("actions")) is not list
            or len(result["actions"]) != result["plies"]
            or type(result.get("decisions")) is not list
        ):
            raise ValueError("invalid selected/applied prefix")
        nodes = result.get("nodes_by_role")
        accounting = result.get("node_accounting")
        if (
            type(nodes) is not dict
            or set(nodes) != {"A", "B"}
            or type(accounting) is not dict
            or set(accounting) != {"A", "B"}
        ):
            raise ValueError("missing node accounting")
        for actor, policy in (
            ("A", item["policy_a"]),
            ("B", item["policy_b"]),
        ):
            charged = nodes.get(actor)
            if (
                type(charged) is not int
                or not 0 <= charged <= item["max_nodes_per_role"]
                or (policy == "G" and charged != 0)
            ):
                raise ValueError("invalid charged nodes")
            expected = (
                "UNMETERED_GOAL_PROGRESS_NOT_ZERO_COMPUTE"
                if policy == "G"
                else "SEARCH_CACHE_MISSES"
            )
            if accounting.get(actor) != expected:
                raise ValueError("invalid node-accounting label")
            if result.get("agent_" + actor.lower()) != POLICY_IDENTITIES[policy]:
                raise ValueError("wrong existing-agent identity")
        _trace_evidence(item, result, raw)

    if complete:
        wire = result if game else result.get("actual_result")
        if type(wire) is not dict:
            raise ValueError("missing completed result")
        plies = wire.get("plies") if game else wire.get("principal_variation_plies")
        decisive = (
            wire.get("winner") in ("A", "B")
            if game
            else wire.get("value_for_a") in (-1, 1)
        )
        if (
            not decisive
            or type(plies) is not int
            or not 0 <= plies <= BOUND
            or wire.get("terminal_reason")
            not in ("GOAL", "NO_LEGAL_ACTION")
        ):
            raise ValueError("PROOF_INTEGRITY_FAILURE")
    elif game:
        censor = result.get("censor")
        if (
            result.get("winner") is not None
            or result.get("terminal_reason") is not None
            or not 0 <= result["plies"] < BOUND
            or type(censor) is not dict
            or censor.get("role") not in ("A", "B")
            or censor.get("visited_nodes") != item["max_nodes_per_role"]
            or censor.get("max_nodes") != item["max_nodes_per_role"]
            or result["nodes_by_role"].get(censor.get("role"))
            != item["max_nodes_per_role"]
        ):
            raise ValueError("invalid UNKNOWN game prefix")
        raise ValueError(
            "game censor violates the preregistered structural node bound"
        )
    elif result.get("actual_result") is not None or result.get("error") != {
        "type": "SolveBudgetExceeded",
        "searched_states": item["max_states"],
        "max_states": item["max_states"],
    }:
        raise ValueError("invalid UNKNOWN exact result")


def short_forced(result):
    """Whether the completed initial T3 selection has a nonzero best value."""

    if result.get("policy_a") != "T3":
        return False
    for decision in result.get("decisions", []):
        if (
            decision.get("ply") == 0
            and decision.get("actor") == "A"
            and decision.get("selection_status") == "SELECTED"
        ):
            values = [value["value"] for value in decision["last_action_values"]]
            return max(values) != 0
    return False


def wilson(wins, count):
    return list(_wilson_interval(wins, count)) if count else None


def summarize(records, disposition=None, failure=None, raw=None):
    """Summarize every fixed denominator without pooling ordered conditions."""

    games = [
        record
        for record in records
        if record["scheduled"]["kind"] == "game"
    ]
    exact_status = next(
        (
            record["status"]
            for record in records
            if record["scheduled"]["kind"] == "exact"
        ),
        "NOT_STARTED",
    )
    cells = []
    for cell, (stage, policy_a, policy_b, start, count) in enumerate(CELLS):
        mine = [
            record
            for record in games
            if record["scheduled"]["cell"] == cell
        ]
        done = [
            record["result"]
            for record in mine
            if record["status"] == "COMPLETE"
        ]
        a_wins = sum(result["winner"] == "A" for result in done)
        not_started = count - len(mine)
        cells.append(
            {
                "cell": cell,
                "stage": stage,
                "first_player": "A",
                "profile": [policy_a, policy_b],
                "seeds": list(range(start, start + count)),
                "planned": count,
                "attempted": len(mine),
                "completed": len(done),
                "a_wins": a_wins,
                "b_wins": len(done) - a_wins,
                "censored": sum(
                    record["status"] == "UNKNOWN_CENSORED"
                    for record in mine
                ),
                "failed": sum(record["status"] == "FAILED" for record in mine),
                "not_started": not_started,
                "not_started_gate_closed": 0 if failure else not_started,
                "not_started_failure": not_started if failure else 0,
                "statuses": dict(Counter(record["status"] for record in mine)),
                "charged_nodes_by_role": {
                    actor: sum(
                        value
                        for record in mine
                        for value in [
                            (record.get("result") or {})
                            .get("nodes_by_role", {})
                            .get(actor)
                        ]
                        if type(value) is int and value >= 0
                    )
                    for actor in ("A", "B")
                },
                "a_wilson95_descriptive": wilson(a_wins, len(done)),
            }
        )

    realized_effect_games = {"A": 0, "B": 0}
    base_realized_effect_games = {"A": 0, "B": 0}
    goal_wins = {"A": 0, "B": 0}
    base_goal_wins = {"A": 0, "B": 0}
    for record in games:
        if record["status"] != "COMPLETE":
            continue
        if raw is None:
            raise ValueError("fixed definition required to summarize game evidence")
        evidence = game_evidence(record["scheduled"], record["result"], raw)
        is_base = record["scheduled"]["stage"] == "base"
        for actor in realized_effect_games:
            if evidence["realized_effect"][actor]:
                realized_effect_games[actor] += 1
                if is_base:
                    base_realized_effect_games[actor] += 1
        result = record["result"]
        if result["terminal_reason"] == "GOAL":
            winner = result["winner"]
            goal_wins[winner] += 1
            if is_base:
                base_goal_wins[winner] += 1

    base_numeric_pass = (
        cells[0]["completed"] == 16
        and 4 <= cells[0]["a_wins"] <= 12
        and cells[1]["completed"] == 16
        and 4 <= cells[1]["a_wins"] <= 12
    )
    base_interaction_pass = all(
        count >= 4 for count in base_realized_effect_games.values()
    )
    base_goal_pass = all(count >= 2 for count in base_goal_wins.values())
    base_pass = base_numeric_pass and base_interaction_pass and base_goal_pass
    pilot_gates_pass = (
        failure is None
        and exact_status == "UNKNOWN_CENSORED"
        and len(games) == PLANNED_GAMES
        and all(cell["completed"] == cell["planned"] for cell in cells)
        and base_pass
        and 4 <= cells[2]["a_wins"] <= 12
        and cells[3]["a_wins"] >= 6
        and cells[4]["b_wins"] >= 6
        and cells[5]["a_wins"] >= 6
        and cells[6]["b_wins"] >= 6
        and all(count >= 8 for count in realized_effect_games.values())
        and all(count >= 4 for count in goal_wins.values())
    )

    if disposition is None and exact_status == "COMPLETE":
        disposition = "TOO_EASILY_SOLVED"
    if disposition is None and any(
        short_forced(record["result"])
        for record in games
        if record["status"] != "FAILED" and record.get("result") is not None
    ):
        disposition = "SHORT_FORCED_RESULT"
    if disposition is None:
        if pilot_gates_pass:
            disposition = "PILOT_GATES_PASS_AWAITING_AUDIT_REGRESSION"
        elif any(
            record["status"] == "UNKNOWN_CENSORED" for record in games
        ):
            disposition = "INSUFFICIENT_EVIDENCE"
        else:
            disposition = "NO_FLAG"

    not_started = PLANNED_ATTEMPTS - len(records)
    total_nodes = {
        actor: sum(cell["charged_nodes_by_role"][actor] for cell in cells)
        for actor in ("A", "B")
    }
    charged_nodes_total = sum(total_nodes.values())
    if charged_nodes_total > STRUCTURAL_CHARGED_NODES_BOUND:
        raise ValueError("full structural charged-node bound violated")
    return {
        "protocol": PROTOCOL,
        "execution_status": "FAILED" if failure else "COMPLETE",
        "failure": failure,
        "disposition": "FAILED" if failure else disposition,
        "planned": PLANNED_ATTEMPTS,
        "attempted": len(records),
        "not_started": not_started,
        "not_started_gate_closed": 0 if failure else not_started,
        "not_started_failure": not_started if failure else 0,
        "statuses": dict(Counter(record["status"] for record in records)),
        "exact_status": exact_status,
        "cells": cells,
        "base_numeric_pass": base_numeric_pass,
        "base_interaction_pass": base_interaction_pass,
        "base_goal_pass": base_goal_pass,
        "base_pass": base_pass,
        "pilot_gates_pass": pilot_gates_pass,
        "base_realized_effect_games": base_realized_effect_games,
        "base_goal_wins": base_goal_wins,
        "realized_effect_games": realized_effect_games,
        "realized_effect_is_depth_proof": False,
        "goal_wins": goal_wins,
        "charged_nodes_by_role": total_nodes,
        "charged_nodes_total": charged_nodes_total,
        "human_review_eligible": False,
        "operational_resource_policy": {
            "exact_max_cached_states": MAX_STATES,
            "exact_max_depth": PLY_LIMIT,
            "max_children_per_state": 10,
            "max_game_decisions": BOUND,
            "max_legal_actions_per_decision": 10,
            "max_cache_misses_per_role_game": MAX_NODES,
            "structural_charged_nodes_bound": STRUCTURAL_CHARGED_NODES_BOUND,
            "configured_charged_nodes_ceiling": CONFIGURED_CHARGED_NODES_CEILING,
            "max_output_files": MAX_OUTPUT_FILES,
            "max_output_file_bytes": MAX_OUTPUT_FILE_BYTES,
            "wall_seconds_and_rss": "DESCRIPTIVE_ONLY",
            "operational_exception": "FAILED_NOT_UNKNOWN_NO_RETRY",
        },
        "g_compute": "UNMETERED_GOAL_PROGRESS_NOT_ZERO_COMPUTE",
        "acceptance": "PROVISIONAL_UNTIL_FULL_REGRESSION",
        "fairness_established": False,
        "hardness_established": False,
        "fun_established": False,
    }


def run_pilot(repository, registered_commit):
    """Execute the one immutable prospective cascade from registered source."""

    repository = Path(repository)
    output = repository / "experiments/runs" / PROTOCOL
    if output.exists():
        raise FileExistsError("immutable run exists; no retry or resume")
    if not isinstance(registered_commit, str) or not re.fullmatch(
        "[0-9a-f]{40}", registered_commit
    ):
        raise ValueError("full registration commit required")
    source = source_snapshot(repository, clean=True)
    if source["git_commit"] != registered_commit:
        raise ValueError("wrong registration commit")
    output.mkdir(parents=True, exist_ok=False)

    saved = {}
    records = []
    failure = None
    disposition = None
    current = None
    raw = None

    def save(name, value):
        path = output / name
        _publish(path, value)
        saved[name] = hashlib.sha256(path.read_bytes()).hexdigest()

    def check_source():
        if source_snapshot(repository) != source:
            raise ValueError("registered source drift")

    planned = schedule()
    try:
        save("attempt.json", {"source": source, "started_at": _utc()})
        raw = load_definition(repository)
        save(
            "manifest.json",
            {
                "protocol": PROTOCOL,
                "source": source,
                "definition": raw,
                "schedule": planned,
                "certificate": {
                    "definition_hash": HASH,
                    "initial_phi": INITIAL_PHI,
                    "max_natural_plies": BOUND,
                    "configured_max_plies": PLY_LIMIT,
                    "ply_limit_unreachable": True,
                    "proof": (
                        "Phi=sum_A(4-column)+2*sum_B(row) starts 50; "
                        "A ordinary/HOP decreases it 1/2 and B empty/PUSH "
                        "decreases it 2/1-or-2, so every legal play ends by 50"
                    ),
                    "max_legal_actions_per_role": 10,
                    "depth3_nodes_per_decision_bound": 1110,
                    "max_decisions_per_role": 25,
                    "depth3_nodes_per_role_game_bound": 27750,
                    "depth2_nodes_per_role_game_bound": 2750,
                },
                "operational_resource_policy": {
                    "exact_max_cached_states": MAX_STATES,
                    "exact_max_depth": PLY_LIMIT,
                    "max_children_per_state": 10,
                    "max_game_decisions": BOUND,
                    "max_legal_actions_per_decision": 10,
                    "max_cache_misses_per_role_game": MAX_NODES,
                    "depth3_role_games": 128,
                    "depth2_role_games": 16,
                    "unmetered_goal_role_games": 16,
                    "structural_charged_nodes_bound": STRUCTURAL_CHARGED_NODES_BOUND,
                    "configured_charged_nodes_ceiling": CONFIGURED_CHARGED_NODES_CEILING,
                    "max_output_files": MAX_OUTPUT_FILES,
                    "max_output_file_bytes": MAX_OUTPUT_FILE_BYTES,
                    "wall_seconds_and_rss": "DESCRIPTIVE_ONLY",
                    "operational_exception": "FAILED_NOT_UNKNOWN_NO_RETRY",
                },
                "exposure": EXPOSURE,
            },
        )
        for ordinal, item in enumerate(planned):
            check_source()
            stem = "{:04d}".format(ordinal)
            save(
                stem + "-attempt.json",
                {"scheduled": item, "started_at": _utc()},
            )
            current = {"scheduled": item, "status": "FAILED", "result": None}
            records.append(current)
            try:
                if item["kind"] == "exact":
                    current["result"] = exact_one(raw, item["max_states"])
                else:
                    current["result"] = play_adapter.play_one(
                        raw,
                        item["policy_a"],
                        item["policy_b"],
                        item["seed"],
                        item["max_nodes_per_role"],
                    )
            except Exception as error:
                current["error"] = {
                    "type": type(error).__name__,
                    "message": str(error),
                }
            try:
                check_source()
                if "error" not in current:
                    validate_result(item, current["result"], raw)
                    current["status"] = current["result"]["status"]
            except Exception as error:
                current["validation_error"] = {
                    "type": type(error).__name__,
                    "message": str(error),
                }
            try:
                save(stem + "-result.json", current)
            except Exception as error:
                current.update(
                    status_before_publication=current["status"],
                    status="FAILED",
                    publication_error=str(error),
                )
                raise
            if current["status"] == "FAILED":
                raise ValueError("stop after failed attempt")

            result = current["result"]
            current = None
            if item["kind"] == "exact" and result["status"] == "COMPLETE":
                disposition = "TOO_EASILY_SOLVED"
            elif item["kind"] == "game" and short_forced(result):
                disposition = "SHORT_FORCED_RESULT"
            elif ordinal == 32 and not summarize(records, raw=raw)["base_pass"]:
                disposition = summarize(records, raw=raw)["disposition"]
            if disposition is not None:
                break

        check_source()
        if any(
            hashlib.sha256((output / name).read_bytes()).hexdigest() != digest
            for name, digest in saved.items()
        ):
            raise ValueError("published artifact drift")
        save(
            "source-verification.json",
            {
                "source": source,
                "matched": True,
                "publication_sha256": dict(saved),
            },
        )
    except Exception as error:
        failure = {
            "type": type(error).__name__,
            "message": str(error),
            "current": current,
        }
        save("failure.json", failure)

    summary = summarize(records, disposition, failure, raw)
    try:
        save("summary.json", summary)
    except Exception as error:
        failure = {
            "type": type(error).__name__,
            "message": str(error),
            "current": current,
        }
        summary = summarize(records, "FAILED", failure, raw)
        save("summary-publication-failure.json", summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registered-commit", required=True)
    arguments = parser.parse_args()
    result = run_pilot(
        Path(__file__).resolve().parents[1], arguments.registered_commit
    )
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(result["execution_status"] == "FAILED")
