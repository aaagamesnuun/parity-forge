"""Bounded, audit-only adapters around the unchanged public game loop."""

import json
import time

from parity_forge.agents import GoalDirectedAgent, MinimaxAgent, SearchBudgetExceeded
from parity_forge.dsl import Player, canonical_json, definition_hash, parse_definition
from parity_forge.engine import replay_dicts
from parity_forge.play import play_game
from parity_forge.terminal_search import TerminalOnlyMinimaxAgent

POLICIES = ("T2", "T4", "H2", "H4", "G")


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _agent(policy, cap):
    if policy == "G":
        return GoalDirectedAgent()
    if policy.startswith("T"):
        return TerminalOnlyMinimaxAgent(int(policy[1]), cap)
    return MinimaxAgent(depth=int(policy[1]), max_total_nodes=cap)


class _AuditAgent:
    def __init__(self, underlying, policy, shared, cap):
        self.underlying, self.policy, self.shared, self.cap = underlying, policy, shared, cap
        self.identity = underlying.identity

    @property
    def total_nodes(self):
        # GoalDirectedAgent does real work but exposes no search-node meter.
        return 0 if self.policy == "G" else self.underlying.total_nodes

    def select_action(self, definition, state, choices, rng):
        self.shared["last_input"] = state
        before = self.total_nodes
        decision = {"ply": state.ply, "actor": state.to_move.value, "input_state": state.to_dict(),
                    "legal_action_count": len(choices), "selected_action": None,
                    "nodes_before": before, "nodes_after": before, "charged_nodes": 0,
                    "selection_status": "STARTED"}
        self.shared["decisions"].append(decision)
        try:
            if state.ply != len(self.shared["selected"]) or not choices:
                raise ValueError("game loop prefix or legal choices inconsistent")
            if type(choices) is not tuple or choices != tuple(sorted(set(choices), key=lambda a: a.sort_key())):
                raise ValueError("choices must be the canonical unique action tuple")
            selected = self.underlying.select_action(definition, state, choices, rng)
            if selected not in choices:
                raise ValueError("agent selected an illegal action")
            decision.update(selected_action=selected.to_dict(), selection_status="SELECTED")
            self.shared["selected"].append(selected.to_dict())
            return selected
        except SearchBudgetExceeded:
            decision["selection_status"] = "UNKNOWN_CENSORED"
            raise
        except Exception:
            decision["selection_status"] = "FAILED"
            raise
        finally:
            after = self.total_nodes
            decision.update(nodes_after=after, charged_nodes=after - before)
            if self.policy.startswith("T"):
                decision["last_action_values"] = [
                    {"action": action.to_dict(), "value": value}
                    for action, value in self.underlying.last_action_values]
            if type(before) is not int or type(after) is not int or not 0 <= before <= after <= self.cap:
                decision["selection_status"] = "FAILED"
                raise ValueError("invalid charged search nodes")


def play_one(raw, policy_a, policy_b, seed, max_nodes):
    """Return a completed game or a verified UNKNOWN/FAILED observed prefix.

    Invalid configuration raises before play. Each completed/observed prefix
    gets at most one replay; an unconfirmed selection is never applied here.
    Candidate-specific natural bounds and scientific judgments belong upstream.
    """
    if any(type(p) is not str or p not in POLICIES for p in (policy_a, policy_b)):
        raise ValueError("unsupported policy")
    if type(seed) is not int or type(max_nodes) is not int or max_nodes < 1:
        raise ValueError("integer seed and positive integer node cap required")
    snapshot = _canonical(raw)
    definition = parse_definition(raw)
    if definition.schema_version != 4:
        raise ValueError("schema4 required")
    definition_snapshot = canonical_json(definition)
    shared = {"selected": [], "decisions": [], "last_input": None}
    agents = {role: _AuditAgent(_agent(policy, max_nodes), policy, shared, max_nodes)
              for role, policy in ((Player.A, policy_a), (Player.B, policy_b))}
    result = {"definition_hash": definition_hash(definition), "first_player": definition.first_player.value,
              "policy_a": policy_a, "policy_b": policy_b, "seed": seed, "max_nodes_per_role": max_nodes,
              "agent_a": agents[Player.A].identity.key, "agent_b": agents[Player.B].identity.key,
              "status": "STARTED", "actions": [], "plies": 0, "winner": None, "terminal_reason": None,
              "decisions": shared["decisions"], "state_after_prefix": None, "unconfirmed_action": None,
              "censor": None, "error": None, "replay_count": 0, "replay_verified": False,
              "node_accounting": {role.value: "UNMETERED_GOAL_PROGRESS_NOT_ZERO_COMPUTE" if agent.policy == "G"
                                  else "SEARCH_CACHE_MISSES" for role, agent in agents.items()}}
    started, completed = time.monotonic(), None
    try:
        completed = play_game(definition, agents, seed).to_dict()
        result["observed_game_record"] = completed
        if completed["actions"] != shared["selected"]:
            raise ValueError("returned actions differ from audited selections")
        if any(completed[k] != result[k] for k in ("seed", "agent_a", "agent_b")):
            raise ValueError("returned game identity differs")
        result.update(status="COMPLETE", actions=completed["actions"], plies=completed["plies"],
                      winner=completed["winner"], terminal_reason=completed["terminal_reason"])
    except SearchBudgetExceeded as error:
        state = shared["last_input"]
        actor = state.to_move if state is not None else None
        if (actor is None or agents[actor].policy == "G" or type(error.visited_nodes) is not int
                or type(error.max_nodes) is not int or error.visited_nodes != max_nodes
                or error.max_nodes != max_nodes or agents[actor].total_nodes != max_nodes):
            result.update(status="FAILED", error={"type": "ValueError", "message": "invalid budget censor"})
            if shared["decisions"]:
                shared["decisions"][-1]["selection_status"] = "FAILED"
        else:
            result.update(status="UNKNOWN_CENSORED", censor={"role": actor.value, "scope": error.scope,
                          "visited_nodes": error.visited_nodes, "max_nodes": error.max_nodes})
    except Exception as error:
        result.update(status="FAILED", error={"type": type(error).__name__, "message": str(error)})

    # Only a following selection's input confirms the previous action applied.
    # Completion instead supplies the public GameRecord's full action sequence.
    target = shared["last_input"]
    if result["status"] != "COMPLETE" and target is not None:
        result.update(actions=shared["selected"][:target.ply], plies=target.ply,
                      state_after_prefix=target.to_dict(), winner=None, terminal_reason=None)
        if len(shared["selected"]) > target.ply:
            result["unconfirmed_action"] = shared["selected"][target.ply]
    try:
        if result["status"] == "COMPLETE" or target is not None:
            result["replay_count"] += 1
            replayed = replay_dicts(definition, result["actions"])
            if result["status"] == "COMPLETE":
                outcome = replayed.outcome
                if (not replayed.terminal or replayed.ply != result["plies"]
                        or (outcome.winner.value if outcome.winner else None) != result["winner"]
                        or outcome.reason != result["terminal_reason"]):
                    raise ValueError("completed game replay differs")
            elif replayed != target or (result["status"] == "UNKNOWN_CENSORED" and replayed.terminal):
                raise ValueError("observed prefix replay differs")
            result.update(state_after_prefix=replayed.to_dict(), replay_verified=True)
        if _canonical(raw) != snapshot or canonical_json(definition) != definition_snapshot:
            raise ValueError("definition drift during play")
    except Exception as error:
        result.update(status="FAILED", verification_error={"type": type(error).__name__, "message": str(error)})
    result.update(nodes_by_role={r.value: a.total_nodes for r, a in agents.items()},
                  elapsed_seconds=time.monotonic() - started)
    return result
