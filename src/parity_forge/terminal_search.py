"""Family-neutral terminal-only depth-limited minimax.

This agent is a new evaluator family.  It deliberately does not reuse or alter
``MinimaxAgent``: the historical agent evaluates nonterminal leaves with goal
progress, while this version assigns every nonterminal cutoff the exact integer
value zero.  The search reads terminal outcomes produced by the engine and never
interprets a goal kind.

The cumulative budget counts expanded states (cache misses).  A root position is
not charged; every searched successor, including terminal and cutoff successors,
is charged on its first ``(GameState, remaining_depth)`` visit within one action
selection.  The transposition cache is discarded after each selection.
"""

from __future__ import annotations

import random
import re
from functools import lru_cache
from typing import Any, Optional, Sequence, Tuple

from .agents import AgentIdentity, SearchBudgetExceeded
from .dsl import ActionKind, GameDefinition, InitialPiece, Player, canonical_json
from .engine import (
    Action,
    GameState,
    Outcome,
    apply_action,
    goal_satisfied,
    legal_actions,
)


TERMINAL_ONLY_MINIMAX_AGENT_VERSION = 1
TERMINAL_ONLY_MINIMAX_AGENT_FAMILY = "terminal_only_minimax"
TERMINAL_ONLY_MINIMAX_MAX_DEPTH = 64

ActionValue = Tuple[Action, int]
_PIECE_IDENTIFIER_V1 = re.compile(r"^[a-z][a-z0-9_]{0,31}$")


def _exact_instance_fields(value: Any, expected: Tuple[str, ...], label: str) -> None:
    try:
        fields = vars(value)
    except TypeError as error:
        raise TypeError("{} fields are unavailable".format(label)) from error
    if type(fields) is not dict or set(fields) != set(expected):
        raise ValueError("{} has noncanonical fields".format(label))


def _validate_piece(
    piece: Any,
    board_size: int,
    allowed_piece_kinds: frozenset,
    index: int,
) -> None:
    label = "state piece {}".format(index)
    if type(piece) is not InitialPiece:
        raise TypeError("{} must be an InitialPiece".format(label))
    _exact_instance_fields(piece, ("owner", "piece", "position"), label)
    if type(piece.owner) is not Player:
        raise TypeError("{} owner must be a Player".format(label))
    if (
        type(piece.piece) is not str
        or _PIECE_IDENTIFIER_V1.fullmatch(piece.piece) is None
    ):
        raise TypeError("{} kind must be a schema-v4 identifier".format(label))
    if piece.piece not in allowed_piece_kinds:
        raise ValueError("{} kind is absent from the definition".format(label))
    position = piece.position
    if (
        type(position) is not tuple
        or len(position) != 2
        or any(type(coordinate) is not int for coordinate in position)
    ):
        raise TypeError("{} position must be a two-integer tuple".format(label))
    if any(coordinate < 0 or coordinate >= board_size for coordinate in position):
        raise ValueError("{} position is outside the board".format(label))


def _validate_outcome(outcome: Any) -> None:
    if type(outcome) is not Outcome:
        raise TypeError("state outcome must be an Outcome")
    _exact_instance_fields(outcome, ("winner", "reason"), "state outcome")
    if outcome.winner is not None and type(outcome.winner) is not Player:
        raise TypeError("state outcome winner must be a Player or None")
    if type(outcome.reason) is not str or outcome.reason not in (
        "GOAL",
        "NO_LEGAL_ACTION",
        "PLY_LIMIT",
    ):
        raise ValueError("state outcome reason is not supported")


def _validate_action(action: Any, board_size: int, index: int) -> None:
    label = "legal action {}".format(index)
    if type(action) is not Action:
        raise TypeError("{} must be an Action".format(label))
    _exact_instance_fields(
        action, ("kind", "to_position", "from_position"), label
    )
    if type(action.kind) is not ActionKind:
        raise TypeError("{} kind must be an ActionKind".format(label))
    for field, position, optional in (
        ("to_position", action.to_position, False),
        ("from_position", action.from_position, True),
    ):
        if optional and position is None:
            continue
        if (
            type(position) is not tuple
            or len(position) != 2
            or any(type(coordinate) is not int for coordinate in position)
        ):
            raise TypeError(
                "{} {} must be a two-integer tuple".format(label, field)
            )
        if any(
            coordinate < 0 or coordinate >= board_size
            for coordinate in position
        ):
            raise ValueError("{} {} is outside the board".format(label, field))


def _validate_state(definition: GameDefinition, state: Any) -> GameState:
    if type(state) is not GameState:
        raise TypeError("terminal-only search state must be a GameState")
    _exact_instance_fields(
        state, ("ply", "to_move", "pieces", "outcome"), "search state"
    )
    if type(state.ply) is not int or not 0 <= state.ply <= definition.max_plies:
        raise ValueError("search state ply must be an in-range exact integer")
    if type(state.to_move) is not Player:
        raise TypeError("search state to_move must be a Player")
    expected_to_move = (
        definition.first_player
        if state.ply % 2 == 0
        else definition.first_player.other
    )
    if state.to_move is not expected_to_move:
        raise ValueError("search state to_move does not match ply parity")
    if type(state.pieces) is not tuple:
        raise TypeError("search state pieces must be a tuple")
    allowed_piece_kinds = frozenset(
        [piece.piece for piece in definition.initial_pieces]
        + [
            definition.role(player).action.piece
            for player in (Player.A, Player.B)
        ]
    )
    for index, piece in enumerate(state.pieces):
        _validate_piece(
            piece, definition.board_size, allowed_piece_kinds, index
        )
    canonical = tuple(
        sorted(
            state.pieces,
            key=lambda piece: (piece.position, piece.owner.value, piece.piece),
        )
    )
    if state.pieces != canonical:
        raise ValueError("search state pieces must use canonical order")
    positions = tuple(piece.position for piece in state.pieces)
    if len(set(positions)) != len(positions):
        raise ValueError("search state pieces cannot share a position")
    if state.outcome is not None:
        _validate_outcome(state.outcome)
    elif state.ply >= definition.max_plies:
        raise ValueError("nonterminal search state cannot reach the ply limit")
    elif any(
        goal_satisfied(definition, state.pieces, player)
        for player in (Player.A, Player.B)
    ):
        raise ValueError("nonterminal search state cannot satisfy either goal")
    return state


def _terminal_value_for_a(state: GameState) -> int:
    outcome = state.outcome
    if outcome is None:
        raise ValueError("terminal utility requires a terminal state")
    if outcome.winner is Player.A:
        return 1
    if outcome.winner is Player.B:
        return -1
    return 0


class TerminalOnlyMinimaxAgent:
    """Full-width bounded minimax with zero-valued nonterminal cutoffs."""

    __slots__ = (
        "_depth",
        "_identity",
        "_last_action_values",
        "_last_cache_hits",
        "_last_expanded_nodes",
        "_max_total_nodes",
        "_total_nodes",
    )

    def __init__(self, depth: int, max_total_nodes: int) -> None:
        if (
            type(depth) is not int
            or not 1 <= depth <= TERMINAL_ONLY_MINIMAX_MAX_DEPTH
        ):
            raise ValueError(
                "terminal-only search depth must be an integer in [1, {}]".format(
                    TERMINAL_ONLY_MINIMAX_MAX_DEPTH
                )
            )
        if type(max_total_nodes) is not int or max_total_nodes < 1:
            raise ValueError(
                "terminal-only max_total_nodes must be an integer >= 1"
            )
        self._depth = depth
        self._max_total_nodes = max_total_nodes
        self._total_nodes = 0
        self._identity = AgentIdentity(
            family=TERMINAL_ONLY_MINIMAX_AGENT_FAMILY,
            version=TERMINAL_ONLY_MINIMAX_AGENT_VERSION,
            strength="depth{}".format(depth),
        )
        self._clear_last_audit()

    @property
    def identity(self) -> AgentIdentity:
        return self._identity

    @property
    def depth(self) -> int:
        return self._depth

    @property
    def max_total_nodes(self) -> int:
        return self._max_total_nodes

    @property
    def total_nodes(self) -> int:
        return self._total_nodes

    @property
    def last_expanded_nodes(self) -> Optional[int]:
        return self._last_expanded_nodes

    @property
    def last_cache_hits(self) -> Optional[int]:
        return self._last_cache_hits

    @property
    def last_action_values(self) -> Tuple[ActionValue, ...]:
        return self._last_action_values

    def _clear_last_audit(self) -> None:
        self._last_expanded_nodes = None
        self._last_cache_hits = None
        self._last_action_values = ()

    def _validate_contract(self) -> None:
        if (
            type(self._depth) is not int
            or not 1 <= self._depth <= TERMINAL_ONLY_MINIMAX_MAX_DEPTH
        ):
            raise ValueError("terminal-only agent depth drifted")
        if type(self._max_total_nodes) is not int or self._max_total_nodes < 1:
            raise ValueError("terminal-only agent node cap drifted")
        if (
            type(self._total_nodes) is not int
            or not 0 <= self._total_nodes <= self._max_total_nodes
        ):
            raise ValueError("terminal-only agent cumulative nodes drifted")
        if type(self._identity) is not AgentIdentity:
            raise ValueError("terminal-only agent identity drifted")
        _exact_instance_fields(
            self._identity, ("family", "version", "strength"), "agent identity"
        )
        if (
            type(self._identity.family) is not str
            or self._identity.family != TERMINAL_ONLY_MINIMAX_AGENT_FAMILY
            or type(self._identity.version) is not int
            or self._identity.version != TERMINAL_ONLY_MINIMAX_AGENT_VERSION
            or type(self._identity.strength) is not str
            or self._identity.strength != "depth{}".format(self._depth)
        ):
            raise ValueError("terminal-only agent identity drifted")

    def reset_budget(self) -> None:
        self._clear_last_audit()
        self._validate_contract()
        self._total_nodes = 0

    def _validate_inputs(
        self,
        definition: Any,
        state: Any,
        actions: Any,
        rng: Any,
    ) -> Tuple[GameDefinition, GameState, Tuple[Action, ...], random.Random]:
        if type(definition) is not GameDefinition:
            raise TypeError("terminal-only search requires a GameDefinition")
        # canonical_json reparses schema-v4's complete strict object graph and
        # rejects forged or hidden fields without applying an action.
        canonical_json(definition)
        if type(definition.schema_version) is not int or definition.schema_version != 4:
            raise ValueError("terminal-only minimax v1 supports only schema v4")
        validated_state = _validate_state(definition, state)
        if validated_state.terminal:
            raise ValueError("terminal-only agent cannot act in a terminal state")
        if type(actions) is not tuple:
            raise TypeError("legal actions must be the canonical action tuple")
        for index, action in enumerate(actions):
            _validate_action(action, definition.board_size, index)
            action.sort_key()
        expected_actions = legal_actions(definition, validated_state)
        if not expected_actions:
            raise ValueError("nonterminal search state must have a legal action")
        if actions != expected_actions:
            raise ValueError(
                "legal actions must exactly match the canonical engine tuple"
            )
        if type(rng) is not random.Random:
            raise TypeError("terminal-only search requires an exact random.Random")
        return definition, validated_state, expected_actions, rng

    def select_action(
        self,
        definition: GameDefinition,
        state: GameState,
        actions: Sequence[Action],
        rng: random.Random,
    ) -> Action:
        """Select one canonical best action under the frozen v1 contract."""

        # Clear before every boundary check so no failed call can expose audit
        # evidence from an earlier successful selection.
        self._clear_last_audit()
        self._validate_contract()
        definition, state, canonical_actions, rng = self._validate_inputs(
            definition, state, actions, rng
        )

        expanded_nodes = 0

        @lru_cache(maxsize=None)
        def search(candidate: GameState, remaining: int) -> int:
            nonlocal expanded_nodes
            if self._total_nodes >= self._max_total_nodes:
                raise SearchBudgetExceeded(
                    "per-slot", self._total_nodes, self._max_total_nodes
                )
            self._total_nodes += 1
            expanded_nodes += 1
            if candidate.outcome is not None:
                return _terminal_value_for_a(candidate)
            if remaining == 0:
                return 0
            child_actions = legal_actions(definition, candidate)
            if not child_actions:
                raise AssertionError(
                    "engine returned a nonterminal state without actions"
                )
            child_values = tuple(
                search(
                    apply_action(definition, candidate, action),
                    remaining - 1,
                )
                for action in child_actions
            )
            return (
                max(child_values)
                if candidate.to_move is Player.A
                else min(child_values)
            )

        action_values = tuple(
            (
                action,
                search(
                    apply_action(definition, state, action),
                    self._depth - 1,
                ),
            )
            for action in canonical_actions
        )
        target = (
            max(value for _, value in action_values)
            if state.to_move is Player.A
            else min(value for _, value in action_values)
        )
        best_actions = tuple(
            action for action, value in action_values if value == target
        )
        if len(best_actions) == 1:
            selected = best_actions[0]
        else:
            selected = best_actions[rng.randrange(len(best_actions))]

        cache = search.cache_info()
        if cache.misses != expanded_nodes:
            raise AssertionError("terminal-only cache/node accounting drifted")
        self._last_expanded_nodes = expanded_nodes
        self._last_cache_hits = cache.hits
        self._last_action_values = action_values
        return selected


__all__ = [
    "TERMINAL_ONLY_MINIMAX_AGENT_FAMILY",
    "TERMINAL_ONLY_MINIMAX_AGENT_VERSION",
    "TERMINAL_ONLY_MINIMAX_MAX_DEPTH",
    "TerminalOnlyMinimaxAgent",
]
