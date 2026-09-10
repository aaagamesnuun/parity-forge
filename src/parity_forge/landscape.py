"""Outcome-blind construction of the generator-v2 3x3 landscape corpus."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from functools import lru_cache
from typing import Any, DefaultDict, Dict, Mapping, Sequence, Tuple

from .dsl import GameDefinition, Player, definition_hash, parse_definition
from .generator import enumerate_v2_three_by_three
from .symmetry import canonicalize_d4, d4_canonical_hash, mechanical_json


LANDSCAPE_VERSION = 1
LANDSCAPE_SELECTION_PREFIX = "landscape-v1:"
LANDSCAPE_QUOTA_PER_STRATUM = 4
RAW_DEFINITION_COUNT = 36720
RAW_D4_ORBIT_COUNT = 4776

_FIRST_PLAYERS = ("A", "B")
_GOAL_AXIS_RELATIONS = ("ALIGNED", "ORTHOGONAL")
_RUNNER_START_CLASSES = ("EDGE_MIDPOINT", "CORNER")
_MAX_PLIES = (6, 9, 18)
_VECTOR_COUNT_BANDS = ("1_TO_3", "4", "5", "6_TO_7")

StratumKey = Tuple[str, str, str, int, str]


def _json_copy(value: Any, label: str) -> Any:
    """Return a deterministic detached JSON value or reject unsuitable metadata."""

    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    except (TypeError, ValueError) as error:
        raise ValueError("{} must be JSON-serializable".format(label)) from error
    return json.loads(encoded)


def _coerce_definition(value: Any) -> GameDefinition:
    if isinstance(value, GameDefinition):
        return value
    if isinstance(value, Mapping):
        return parse_definition(value)
    raise TypeError("known definitions must be GameDefinition values or mappings")


def _vector_count_band(vector_count: int) -> str:
    if 1 <= vector_count <= 3:
        return "1_TO_3"
    if vector_count == 4:
        return "4"
    if vector_count == 5:
        return "5"
    if 6 <= vector_count <= 7:
        return "6_TO_7"
    raise ValueError("eligible landscape definitions require one to seven vectors")


def _stratum_key(definition: GameDefinition) -> StratumKey:
    if definition.board_size != 3:
        raise ValueError("landscape strata require a 3x3 definition")
    role_a = definition.role(Player.A)
    role_b = definition.role(Player.B)
    if role_b.goal.edge is None:
        raise ValueError("landscape role B must have a reach-edge goal")
    relation = (
        "ALIGNED" if role_b.goal.edge in role_a.goal.edges else "ORTHOGONAL"
    )
    if len(definition.initial_pieces) != 1:
        raise ValueError("landscape definitions require one initial runner")
    row, column = definition.initial_pieces[0].position
    start_class = (
        "CORNER"
        if row in (0, definition.board_size - 1)
        and column in (0, definition.board_size - 1)
        else "EDGE_MIDPOINT"
    )
    return (
        definition.first_player.value,
        relation,
        start_class,
        definition.max_plies,
        _vector_count_band(len(role_b.action.vectors)),
    )


def _stratum_dict(key: StratumKey) -> Dict[str, Any]:
    first, relation, start_class, max_plies, vector_band = key
    return {
        "first_player": first,
        "goal_axis_relation": relation,
        "runner_start_class": start_class,
        "max_plies": max_plies,
        "vector_count_band": vector_band,
    }


def _stratum_id(key: StratumKey) -> str:
    first, relation, start_class, max_plies, vector_band = key
    return "f{}-{}-{}-p{}-v{}".format(
        first,
        relation.lower(),
        start_class.lower(),
        max_plies,
        vector_band.lower(),
    )


def _stratum_keys() -> Tuple[StratumKey, ...]:
    return tuple(
        (first, relation, start_class, max_plies, vector_band)
        for first in _FIRST_PLAYERS
        for relation in _GOAL_AXIS_RELATIONS
        for start_class in _RUNNER_START_CLASSES
        for max_plies in _MAX_PLIES
        for vector_band in _VECTOR_COUNT_BANDS
    )


@lru_cache(maxsize=1)
def _canonical_orbit_representatives() -> Tuple[Tuple[str, GameDefinition], ...]:
    """Return one canonical-orientation definition for every full-vocabulary orbit."""

    definitions = enumerate_v2_three_by_three()
    if len(definitions) != RAW_DEFINITION_COUNT:
        raise AssertionError(
            "generator-v2 3x3 vocabulary drifted from {} to {} definitions".format(
                RAW_DEFINITION_COUNT, len(definitions)
            )
        )

    representatives: Dict[str, GameDefinition] = {}
    representative_hashes: Dict[str, str] = {}
    observed_orbits = set()
    for definition in definitions:
        canonical = canonicalize_d4(definition)
        orbit_hash = canonical.canonical_hash
        observed_orbits.add(orbit_hash)
        if mechanical_json(definition) != canonical.mechanical_json:
            continue
        game_hash = definition_hash(definition)
        if (
            orbit_hash not in representatives
            or game_hash < representative_hashes[orbit_hash]
        ):
            representatives[orbit_hash] = definition
            representative_hashes[orbit_hash] = game_hash

    if len(observed_orbits) != RAW_D4_ORBIT_COUNT:
        raise AssertionError(
            "generator-v2 3x3 D4 census drifted from {} to {} orbits".format(
                RAW_D4_ORBIT_COUNT, len(observed_orbits)
            )
        )
    missing = observed_orbits - set(representatives)
    if missing:
        raise AssertionError(
            "{} D4 orbits lack a generator-v2 canonical orientation".format(
                len(missing)
            )
        )
    return tuple(sorted(representatives.items()))


def _selection_score(orbit_hash: str) -> str:
    return hashlib.sha256(
        (LANDSCAPE_SELECTION_PREFIX + orbit_hash).encode("ascii")
    ).hexdigest()


def build_landscape_manifest(
    known_definitions: Sequence[Any],
    source_metadata: Any,
    provenance: Any,
) -> Dict[str, Any]:
    """Build the deterministic, outcome-free 384-case landscape manifest.

    Every D4 orbit containing a supplied known definition is removed. The complete
    remaining generator-v2 vocabulary is represented in canonical D4 orientation,
    eight-vector orbits are structurally excluded, and four representatives are
    selected per predeclared stratum without consulting any evaluation outcome.
    """

    known = tuple(_coerce_definition(value) for value in known_definitions)
    unique_known_hashes = {definition_hash(definition) for definition in known}
    relevant_known = tuple(
        definition
        for definition in known
        if definition.board_size == 3 and definition.max_plies in _MAX_PLIES
    )
    input_known_orbits = {
        d4_canonical_hash(definition) for definition in relevant_known
    }

    orbit_representatives = dict(_canonical_orbit_representatives())
    raw_orbit_hashes = set(orbit_representatives)
    matched_known_orbits = input_known_orbits & raw_orbit_hashes
    after_known = raw_orbit_hashes - matched_known_orbits

    raw_eight_vector_orbits = {
        orbit_hash
        for orbit_hash, definition in orbit_representatives.items()
        if len(definition.role(Player.B).action.vectors) == 8
    }
    structurally_excluded = after_known & raw_eight_vector_orbits
    eligible_orbit_hashes = after_known - raw_eight_vector_orbits

    eligible_by_stratum: DefaultDict[
        StratumKey, list[Tuple[str, str, GameDefinition]]
    ] = defaultdict(list)
    for orbit_hash in sorted(eligible_orbit_hashes):
        definition = orbit_representatives[orbit_hash]
        key = _stratum_key(definition)
        eligible_by_stratum[key].append(
            (_selection_score(orbit_hash), orbit_hash, definition)
        )
    for candidates in eligible_by_stratum.values():
        candidates.sort(key=lambda item: (item[0], item[1]))

    keys = _stratum_keys()
    if len(keys) != 96:
        raise AssertionError("landscape protocol must define exactly 96 strata")
    short = [
        (key, len(eligible_by_stratum[key]))
        for key in keys
        if len(eligible_by_stratum[key]) < LANDSCAPE_QUOTA_PER_STRATUM
    ]
    if short:
        detail = ", ".join(
            "{}={}".format(_stratum_id(key), count) for key, count in short
        )
        raise ValueError("landscape quota cannot be filled: " + detail)

    cases = []
    strata = []
    for key in keys:
        stratum_id = _stratum_id(key)
        candidates = eligible_by_stratum[key]
        selected_case_ids = []
        for rank, (score, orbit_hash, definition) in enumerate(
            candidates[:LANDSCAPE_QUOTA_PER_STRATUM], start=1
        ):
            case_id = "landscape-v1-{}-r{:02d}".format(stratum_id, rank)
            selected_case_ids.append(case_id)
            game_hash = definition_hash(definition)
            if d4_canonical_hash(definition) != orbit_hash:
                raise AssertionError("selected definition changed D4 orbit")
            canonical = canonicalize_d4(definition)
            if mechanical_json(definition) != canonical.mechanical_json:
                raise AssertionError("selected definition is not in canonical D4 orientation")
            cases.append(
                {
                    "case_id": case_id,
                    "stratum": _stratum_dict(key),
                    "vector_count": len(
                        definition.role(Player.B).action.vectors
                    ),
                    "selection_score": score,
                    "selection_rank": rank,
                    "definition_hash": game_hash,
                    "d4_canonical_hash": orbit_hash,
                    "definition": definition.to_dict(),
                }
            )
        strata.append(
            {
                "stratum_id": stratum_id,
                "stratum": _stratum_dict(key),
                "eligible_d4_orbit_count": len(candidates),
                "quota": LANDSCAPE_QUOTA_PER_STRATUM,
                "selected_case_ids": selected_case_ids,
            }
        )

    eligible_counts = [record["eligible_d4_orbit_count"] for record in strata]
    if len(cases) != 96 * LANDSCAPE_QUOTA_PER_STRATUM:
        raise AssertionError("landscape selection must contain exactly 384 cases")

    return {
        "manifest_id": "generator-v2-3x3-landscape-v1",
        "manifest_version": LANDSCAPE_VERSION,
        "source_metadata": _json_copy(source_metadata, "source_metadata"),
        "provenance": _json_copy(provenance, "provenance"),
        "selection_protocol": {
            "outcome_blind": True,
            "d4_representative": "canonical_mechanical_orientation_then_minimum_definition_hash",
            "selection_order": (
                "sha256(landscape-v1:<d4_canonical_hash>), then d4_canonical_hash"
            ),
            "quota_per_stratum": LANDSCAPE_QUOTA_PER_STRATUM,
            "structural_exclusion": "VECTOR_COUNT_8",
            "vector_count_bands": list(_VECTOR_COUNT_BANDS),
        },
        "census": {
            "raw_definition_count": len(enumerate_v2_three_by_three()),
            "raw_d4_orbit_count": len(raw_orbit_hashes),
            "input_known_definition_count": len(known),
            "input_unique_known_definition_count": len(unique_known_hashes),
            "input_relevant_known_d4_orbit_count": len(input_known_orbits),
            "matched_known_d4_orbit_count": len(matched_known_orbits),
            "d4_orbit_count_after_known_exclusion": len(after_known),
            "raw_vector_count_8_d4_orbit_count": len(raw_eight_vector_orbits),
            "structurally_excluded_vector_count_8_d4_orbit_count": len(
                structurally_excluded
            ),
            "eligible_d4_orbit_count": len(eligible_orbit_hashes),
            "stratum_count": len(strata),
            "quota_per_stratum": LANDSCAPE_QUOTA_PER_STRATUM,
            "minimum_eligible_d4_orbits_per_stratum": min(eligible_counts),
            "maximum_eligible_d4_orbits_per_stratum": max(eligible_counts),
            "selected_case_count": len(cases),
        },
        "strata": strata,
        "cases": cases,
    }
