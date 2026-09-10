"""Spatial D4 canonicalization for square-board DSL definitions.

The ordinary :func:`parity_forge.dsl.definition_hash` remains the exact,
orientation-sensitive identity of a stored definition.  This module provides a
separate, name-independent identity for the eight rotations and reflections of
the same mechanics.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Tuple

from .dsl import (
    GameDefinition,
    VECTOR_ACTION_KINDS,
    canonical_json,
    parse_definition,
)


D4_TRANSFORMS = (
    "I",
    "R90",
    "R180",
    "R270",
    "FLR",
    "FTB",
    "FD",
    "FA",
)

_EDGE_MAPS: Mapping[str, Mapping[str, str]] = {
    "I": {
        "TOP": "TOP",
        "RIGHT": "RIGHT",
        "BOTTOM": "BOTTOM",
        "LEFT": "LEFT",
    },
    "R90": {
        "TOP": "RIGHT",
        "RIGHT": "BOTTOM",
        "BOTTOM": "LEFT",
        "LEFT": "TOP",
    },
    "R180": {
        "TOP": "BOTTOM",
        "RIGHT": "LEFT",
        "BOTTOM": "TOP",
        "LEFT": "RIGHT",
    },
    "R270": {
        "TOP": "LEFT",
        "RIGHT": "TOP",
        "BOTTOM": "RIGHT",
        "LEFT": "BOTTOM",
    },
    # FLR reflects left and right across the board's vertical axis.
    "FLR": {
        "TOP": "TOP",
        "RIGHT": "LEFT",
        "BOTTOM": "BOTTOM",
        "LEFT": "RIGHT",
    },
    # FTB reflects top and bottom across the board's horizontal axis.
    "FTB": {
        "TOP": "BOTTOM",
        "RIGHT": "RIGHT",
        "BOTTOM": "TOP",
        "LEFT": "LEFT",
    },
    # FD and FA reflect across the main and anti-diagonals respectively.
    "FD": {
        "TOP": "LEFT",
        "RIGHT": "BOTTOM",
        "BOTTOM": "RIGHT",
        "LEFT": "TOP",
    },
    "FA": {
        "TOP": "RIGHT",
        "RIGHT": "TOP",
        "BOTTOM": "LEFT",
        "LEFT": "BOTTOM",
    },
}

_HASH_DOMAIN = b"parity-forge:d4:v1\0"
_VECTOR_ACTION_VALUES = frozenset(
    kind.value for kind in VECTOR_ACTION_KINDS
)


def _require_transform(transform: str) -> None:
    if transform not in D4_TRANSFORMS:
        raise ValueError(
            "transform must be one of {}".format(list(D4_TRANSFORMS))
        )


def _transform_position(
    position: Tuple[int, int], board_size: int, transform: str
) -> Tuple[int, int]:
    row, column = position
    maximum = board_size - 1
    return {
        "I": (row, column),
        "R90": (column, maximum - row),
        "R180": (maximum - row, maximum - column),
        "R270": (maximum - column, row),
        "FLR": (row, maximum - column),
        "FTB": (maximum - row, column),
        "FD": (column, row),
        "FA": (maximum - column, maximum - row),
    }[transform]


def transform_position(
    position: Tuple[int, int], board_size: int, transform: str
) -> Tuple[int, int]:
    """Return one board coordinate under the authoritative D4 action.

    Definitions, traces, and high-volume census builders share this public
    primitive so spatial identity cannot drift through duplicate coordinate
    formulae.
    """

    _require_transform(transform)
    if type(board_size) is not int or board_size < 1:
        raise ValueError("board_size must be a positive exact integer")
    if (
        type(position) is not tuple
        or len(position) != 2
        or any(type(coordinate) is not int for coordinate in position)
    ):
        raise TypeError("position must be a pair of exact integers")
    if any(coordinate < 0 or coordinate >= board_size for coordinate in position):
        raise ValueError("position must be in bounds")
    return _transform_position(position, board_size, transform)


def _transform_vector(
    vector: Tuple[int, int], transform: str
) -> Tuple[int, int]:
    row_delta, column_delta = vector
    return {
        "I": (row_delta, column_delta),
        "R90": (column_delta, -row_delta),
        "R180": (-row_delta, -column_delta),
        "R270": (-column_delta, row_delta),
        "FLR": (row_delta, -column_delta),
        "FTB": (-row_delta, column_delta),
        "FD": (column_delta, row_delta),
        "FA": (-column_delta, -row_delta),
    }[transform]


def _transform_definition_value(
    source_value: Mapping[str, Any],
    transform: str,
    name: Optional[str] = None,
) -> GameDefinition:
    _require_transform(transform)
    value: Dict[str, Any] = deepcopy(dict(source_value))
    if name is not None:
        value["name"] = name

    edge_map = _EDGE_MAPS[transform]
    for role in value["roles"].values():
        action = role["action"]
        if action["kind"] in _VECTOR_ACTION_VALUES:
            action["vectors"] = [
                list(_transform_vector(tuple(vector), transform))
                for vector in action["vectors"]
            ]

        goal = role["goal"]
        if goal["kind"] == "CONNECT_EDGES":
            goal["edges"] = [edge_map[edge] for edge in goal["edges"]]
        elif goal["kind"] == "REACH_EDGE":
            goal["edge"] = edge_map[goal["edge"]]
        elif goal["kind"] == "ELIMINATE":
            pass
        else:
            raise AssertionError("validated definition has an unknown goal kind")

    board_size = value["board_size"]
    for piece in value["initial_pieces"]:
        piece["position"] = list(
            transform_position(tuple(piece["position"]), board_size, transform)
        )

    # The strict parser supplies the existing canonical ordering for vectors,
    # edge sets, roles, and initial pieces and re-validates the transformed DSL.
    return parse_definition(value)


def transform_definition(
    definition: GameDefinition,
    transform: str,
    name: Optional[str] = None,
) -> GameDefinition:
    """Return one spatially transformed, fully re-canonicalized definition.

    D4 acts only on the square board.  Player labels, role ownership, the first
    player, the ply limit, piece identifiers, and the schema version are kept.
    Passing ``name=None`` preserves the input name; an explicit name replaces it.
    """

    _require_transform(transform)
    value = json.loads(canonical_json(definition))
    return _transform_definition_value(value, transform, name)


def _mechanical_json_value(value: Mapping[str, Any]) -> str:
    mechanical = dict(value)
    del mechanical["name"]
    return json.dumps(
        mechanical,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def mechanical_json(definition: GameDefinition) -> str:
    """Serialize all definition fields except the non-mechanical display name."""

    return _mechanical_json_value(json.loads(canonical_json(definition)))


@dataclass(frozen=True)
class D4Canonicalization:
    canonical_hash: str
    mechanical_json: str
    transform: str


def canonicalize_d4(definition: GameDefinition) -> D4Canonicalization:
    """Choose the bytewise-minimal mechanical representative of the D4 orbit."""

    source_value = json.loads(canonical_json(definition))
    selected_json: Optional[str] = None
    selected_bytes: Optional[bytes] = None
    selected_transform: Optional[str] = None
    for transform in D4_TRANSFORMS:
        candidate_json = _mechanical_json_value(
            _transform_definition_value(source_value, transform).to_dict()
        )
        candidate_bytes = candidate_json.encode("utf-8")
        # Strict inequality deliberately preserves D4_TRANSFORMS as the tie order.
        if selected_bytes is None or candidate_bytes < selected_bytes:
            selected_json = candidate_json
            selected_bytes = candidate_bytes
            selected_transform = transform

    assert selected_json is not None
    assert selected_bytes is not None
    assert selected_transform is not None
    canonical_hash = hashlib.sha256(_HASH_DOMAIN + selected_bytes).hexdigest()
    return D4Canonicalization(
        canonical_hash=canonical_hash,
        mechanical_json=selected_json,
        transform=selected_transform,
    )


def d4_canonical_hash(definition: GameDefinition) -> str:
    """Return the versioned name-independent hash of a definition's D4 class."""

    return canonicalize_d4(definition).canonical_hash
