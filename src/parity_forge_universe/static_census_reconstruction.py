"""Independent stored-report reconstruction for Plan-0015 static census v1.

This module is deliberately standard-library-only and does not import
``parity_forge`` or :mod:`parity_forge_universe.static_census`.  It accepts the
exact canonical bytes emitted by ``canonical_static_census_report_json_v1`` and
reconstructs their compact proof from the 1,518 retained shard summaries.  It
never traverses the 5,111,055 carrier leaves and therefore proves stored-report
integrity and aggregate reconstruction, not an independent leaf-semantic rerun.

``reconstruct_static_census_report_artifact_v1(raw)`` returns a freshly
detached exact dictionary with precisely these keys::

    {
        "report": <parsed complete report>,
        "report_ref": {
            "byte_count": <len(raw)>,
            "sha256": <ordinary SHA-256 of all raw bytes>,
        },
        "report_summary": {
            "report_digest": <domain-separated report-body digest>,
            "setup_orbit_table_root": <pinned setup authority root>,
            "skeleton_authority_root": <pinned skeleton authority root>,
            "ordered_shard_commitment_root": <all 1,518 shard commitments>,
            "population": <detached report population>,
            "eligibility": {
                "representative_eligible_count": <int>,
                "weighted_eligible_count": <int>,
                "paired_first_player_eligible_member_count": <int>,
            },
        },
    }

The ``report_ref`` is computed from the supplied bytes; the evidence lifecycle
must compare it byte-for-byte with its immutable filesystem body reference.
No path, callback, table, live report token, or resume value is accepted here.
"""

from __future__ import annotations

import copy
import hashlib
import json
from itertools import combinations
from math import comb
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


STATIC_CENSUS_REPORT_MAX_BYTES_V1 = 256 * 1024 * 1024
STATIC_CENSUS_REPORT_MAX_JSON_NODES_V1 = 5_000_000
STATIC_CENSUS_REPORT_MAX_JSON_DEPTH_V1 = 32


class StaticCensusReconstructionError(ValueError):
    """Stored bytes escaped the fixed static-census report contract."""


Position = Tuple[int, int]
CountPair = Tuple[int, int]
Stabilizer = Tuple[str, ...]
SkeletonRow = Tuple[Any, ...]
SetupWeightTables = Tuple[
    Tuple[Tuple[Tuple[int, int], ...], ...], ...
]

_BOARD: Tuple[Position, ...] = tuple(
    (row, column) for row in range(3) for column in range(3)
)
_COUNT_PAIRS: Tuple[CountPair, ...] = tuple(
    (a_count, b_count)
    for a_count in range(4)
    for b_count in range(4)
    if (a_count, b_count) != (0, 0)
)
_COUNT_PAIR_SUPPLIES: Tuple[int, ...] = tuple(
    comb(9, a_count) * comb(9 - a_count, b_count)
    for a_count, b_count in _COUNT_PAIRS
)
_D4: Tuple[str, ...] = (
    "I",
    "R90",
    "R180",
    "R270",
    "FLR",
    "FTB",
    "FD",
    "FA",
)
_STABILIZERS: Tuple[Stabilizer, ...] = (
    ("I",),
    ("I", "FLR"),
    ("I", "FTB"),
    ("I", "R180", "FLR", "FTB"),
    _D4,
)
_STABILIZER_SKELETON_COUNTS = (141, 810, 165, 396, 6)
_SETUP_ORBIT_COUNTS = (6798, 3511, 3511, 1827, 970)
_SETUP_WEIGHT_HISTOGRAMS: Tuple[Tuple[Tuple[int, int], ...], ...] = (
    ((1, 6798),),
    ((1, 224), (2, 3287)),
    ((1, 224), (2, 3287)),
    ((1, 20), (2, 225), (4, 1582)),
    ((1, 2), (2, 18), (4, 210), (8, 740)),
)
_FIXED_SETUP_COUNTS = (6798, 2, 62, 2, 224, 224, 224, 224)
_GLOBAL_WEIGHT_HISTOGRAM = (
    (1, 1_184_850),
    (2, 3_294_033),
    (4, 627_732),
    (8, 4_440),
)
_EXPECTED_SETUP_COUNT = 6_798
_EXPECTED_SKELETON_COUNT = 1_518
_EXPECTED_FACTORIZED_COUNT = 5_111_055
_EXPECTED_LABELED_COUNT = 10_319_364
_EXPECTED_PAIRED_COUNT = 20_638_728
_EXPECTED_ALL_ORDERED = 11_085_600
_EXPECTED_SELF_ISOMORPHIC = 215_508
_EXPECTED_OLD_REGION = 647_982

_EXPECTED_UNIVERSE_ROOT = (
    "05826dc2da02890f3f562ee2d6febda523c58837affb757b5dff6d62c074e6ab"
)
_EXPECTED_FRESH_SKELETON_ROOT = (
    "ca02a2bbd844962fd83c7190eec69dea51877940ea6f0836c5a00338a3e9e190"
)
_EXPECTED_COUNT_TABLE_ROOT = (
    "de2e65f28be1f60aff4712c23c8681ea7945324886a2954a0f8d8cbfa905d226"
)
_EXPECTED_SETUP_ROOT = (
    "f1bc82d1cfbaac9933e097aba2f4118737e19f7a190f06bc9f0a83add17c2e23"
)
_EXPECTED_SKELETON_ROOT = (
    "53221ffdbd42e4c86e9c54eadb6e0659bf71ff350dcdf0944b062ce56c3e1488"
)

_REASON_ATOMS: Tuple[Tuple[str, str, Optional[str]], ...] = (
    ("ZERO_ACTOR_WITH_NONPLACE", "A", None),
    ("ZERO_ACTOR_WITH_NONPLACE", "B", None),
    ("INITIAL_GOAL_SATISFIED", "A", None),
    ("INITIAL_GOAL_SATISFIED", "B", None),
    ("INITIAL_IMMOBILITY", "A", None),
    ("INITIAL_IMMOBILITY", "B", None),
    ("OPTIMISTIC_GOAL_UNREACHABLE", "A", None),
    ("OPTIMISTIC_GOAL_UNREACHABLE", "B", None),
    ("COUNT_LATTICE_GOAL_UNREACHABLE_WITHIN_18", "A", "A"),
    ("COUNT_LATTICE_GOAL_UNREACHABLE_WITHIN_18", "A", "B"),
    ("COUNT_LATTICE_GOAL_UNREACHABLE_WITHIN_18", "B", "A"),
    ("COUNT_LATTICE_GOAL_UNREACHABLE_WITHIN_18", "B", "B"),
)
_REASON_MASK_COUNT = 1 << len(_REASON_ATOMS)
_CONTACT_CLASSES = ("CONTACT", "SEPARATED")
_FIRST_PLAYERS = ("A", "B")
_WORK_FIELDS = (
    "state_weight_sum",
    "action_candidate_iterations",
    "scan_candidate_iterations",
)
_DESCRIPTOR_GROUPS = (
    "structural",
    "description_clause",
    "operational_substep",
    "primitive_concept",
    "vector_cardinality",
    "density",
    "contact",
    "dependency",
)

_ACTIONS = (
    "PLACE",
    "MOVE",
    "MOVE_CAPTURE",
    "PUSH",
    "SWAP",
    "HOP",
    "CONVERT",
)
_GOALS = ("CONNECT_EDGES", "REACH_EDGE", "ELIMINATE")
_PROFILES = ("NONE", "ORTHOGONAL_4", "DIAGONAL_4", "KING_8")
_EDGES = ("TOP", "RIGHT", "BOTTOM", "LEFT")
_V4_ACTIONS = ("PUSH", "SWAP", "HOP", "CONVERT")
_OLD_SEMANTIC_SPECS = (
    ("PUSH", "REACH_EDGE", "HOP", "REACH_EDGE"),
    ("SWAP", "CONNECT_EDGES", "HOP", "REACH_EDGE"),
    ("CONVERT", "CONNECT_EDGES", "PUSH", "REACH_EDGE"),
    ("MOVE_CAPTURE", "ELIMINATE", "HOP", "REACH_EDGE"),
    ("CONVERT", "ELIMINATE", "MOVE_CAPTURE", "ELIMINATE"),
    ("PUSH", "CONNECT_EDGES", "SWAP", "CONNECT_EDGES"),
)

_SETUP_DESCRIPTOR_DOMAIN = (
    b"parity-forge:plan0015:setup-orbit-table-descriptor:v1\0"
)
_ORDERED_SETUP_ROOT_DOMAIN = b"parity-forge:plan0015:ordered-typed-setups:v1\0"
_SETUP_IMAGE_ROOT_DOMAIN = (
    b"parity-forge:plan0015:setup-d4-image-ordinals:v1\0"
)
_SETUP_GROUP_MAPPING_ROOT_DOMAIN = (
    b"parity-forge:plan0015:setup-group-mapping:v1\0"
)
_SETUP_GROUP_REPRESENTATIVE_ROOT_DOMAIN = (
    b"parity-forge:plan0015:setup-group-representatives:v1\0"
)
_SKELETON_AUTHORITY_ROOT_DOMAIN = (
    b"parity-forge:plan0015:static-census-skeleton-authority:v1\0"
)
_SKELETON_DESCRIPTOR_ROOT_DOMAIN = (
    _SKELETON_AUTHORITY_ROOT_DOMAIN + b"descriptor\0"
)
_STATIC_SHARD_SUMMARY_DOMAIN = (
    b"parity-forge:plan0015:static-census-shard-summary:v1\0"
)
_STATIC_CHECKPOINT_DOMAIN = b"parity-forge:plan0015:static-census-checkpoint:v1\0"
_STATIC_REPORT_BODY_DOMAIN = (
    b"parity-forge:plan0015:static-census-report-body:v1\0"
)
_STATIC_REPORT_ROOT_DOMAIN = _STATIC_REPORT_BODY_DOMAIN
_TYPED_SETUP_HASH_DOMAIN = b"parity-forge:plan0015:typed-setup:v1\0"
_PROFILED_SKELETON_HASH_DOMAIN = b"parity-forge:typed-occupancy:skeleton:v1\0"
_ROLE_NEUTRAL_SKELETON_HASH_DOMAIN = (
    b"parity-forge:typed-occupancy:role-neutral-skeleton:v1\0"
)
_ROLE_NEUTRAL_SEMANTIC_HASH_DOMAIN = (
    b"parity-forge:typed-occupancy:role-neutral-semantic:v1\0"
)
_UNIVERSE_FRESH_ROOT_DOMAIN = (
    b"parity-forge:typed-occupancy:fresh-canonical:v1\0"
)


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _domain_hash(domain: bytes, canonical: str) -> str:
    return hashlib.sha256(domain + canonical.encode("utf-8")).hexdigest()


def _sequence_root(domain: bytes, values: Iterable[str]) -> str:
    digest = hashlib.sha256(domain)
    for ordinal, canonical in enumerate(values):
        if type(canonical) is not str:
            raise StaticCensusReconstructionError(
                "sequence values must be exact strings"
            )
        encoded = canonical.encode("utf-8")
        digest.update(ordinal.to_bytes(8, "big"))
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def _fresh_root(values: Sequence[str]) -> str:
    digest = hashlib.sha256(_UNIVERSE_FRESH_ROOT_DOMAIN)
    digest.update(len(values).to_bytes(8, "big"))
    for ordinal, canonical in enumerate(values):
        encoded = canonical.encode("utf-8")
        digest.update(ordinal.to_bytes(8, "big"))
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def _is_sha256(value: Any) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _exact_dict(value: Any, label: str) -> Dict[str, Any]:
    if type(value) is not dict:
        raise StaticCensusReconstructionError(label + " must be an exact object")
    if any(type(key) is not str for key in value):
        raise StaticCensusReconstructionError(label + " keys changed type")
    return value


def _exact_keys(value: Dict[str, Any], keys: Sequence[str], label: str) -> None:
    if set(value) != set(keys):
        raise StaticCensusReconstructionError(label + " has noncanonical fields")


def _exact_int(
    value: Any,
    label: str,
    *,
    minimum: Optional[int] = None,
    maximum: Optional[int] = None,
) -> int:
    if type(value) is not int:
        raise StaticCensusReconstructionError(label + " must be an exact integer")
    if minimum is not None and value < minimum:
        raise StaticCensusReconstructionError(label + " is below its minimum")
    if maximum is not None and value > maximum:
        raise StaticCensusReconstructionError(label + " exceeds its maximum")
    return value


def _pairs_object(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StaticCensusReconstructionError("JSON contains a duplicate key")
        result[key] = value
    return result


def _reject_float(_: str) -> Any:
    raise StaticCensusReconstructionError("JSON floating-point values are forbidden")


def _reject_constant(_: str) -> Any:
    raise StaticCensusReconstructionError("JSON non-finite values are forbidden")


def _loads_exact(text: str, label: str) -> Any:
    try:
        return json.loads(
            text,
            object_pairs_hook=_pairs_object,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except StaticCensusReconstructionError:
        raise
    except (TypeError, ValueError, json.JSONDecodeError, RecursionError) as error:
        raise StaticCensusReconstructionError(label + " is not exact JSON") from error


def _validate_json_tree(value: Any) -> None:
    nodes = 0

    def visit(item: Any, depth: int) -> None:
        nonlocal nodes
        nodes += 1
        if nodes > STATIC_CENSUS_REPORT_MAX_JSON_NODES_V1:
            raise StaticCensusReconstructionError("report exceeds the JSON node cap")
        if depth > STATIC_CENSUS_REPORT_MAX_JSON_DEPTH_V1:
            raise StaticCensusReconstructionError("report exceeds the JSON depth cap")
        if item is None or type(item) in (bool, int, str):
            return
        if type(item) is dict:
            children = item.values()
        elif type(item) is list:
            children = item
        else:
            raise StaticCensusReconstructionError(
                "report contains a noncanonical JSON value"
            )
        for child in children:
            visit(child, depth + 1)

    visit(value, 0)


def _weight_pair_is_feasible(
    representative_count: int,
    weighted_count: int,
    histogram: Tuple[Tuple[int, int], ...],
) -> bool:
    """Return whether one bucket can be a subset of the fixed orbit multiset."""

    capacities = {weight: count for weight, count in histogram}
    if (
        representative_count < 0
        or weighted_count < representative_count
        or representative_count > sum(capacities.values())
    ):
        return False
    extra = weighted_count - representative_count

    def feasible_124(count: int, excess: int) -> bool:
        if count < 0 or excess < 0 or excess > 3 * count:
            return False
        count_1 = capacities.get(1, 0)
        count_2 = capacities.get(2, 0)
        count_4 = capacities.get(4, 0)
        lower_4 = max(
            0,
            (excess - count_2 + 2) // 3,
            (excess - count + 1) // 2,
        )
        upper_4 = min(
            count_4,
            count,
            excess // 3,
            (count_1 + excess - count) // 2,
        )
        return lower_4 <= upper_4

    maximum_8 = min(capacities.get(8, 0), representative_count, extra // 7)
    minimum_8 = max(
        0,
        representative_count
        - capacities.get(1, 0)
        - capacities.get(2, 0)
        - capacities.get(4, 0),
        (extra - 3 * representative_count + 3) // 4,
    )
    return any(
        feasible_124(representative_count - count_8, extra - 7 * count_8)
        for count_8 in range(minimum_8, maximum_8 + 1)
    )


def _bucket_weight_allocations(
    representative_count: int,
    weighted_count: int,
    histogram: Tuple[Tuple[int, int], ...],
) -> Tuple[Tuple[int, int, int, int], ...]:
    """Enumerate the small low-weight coordinates for one exact bucket."""

    if not _weight_pair_is_feasible(
        representative_count, weighted_count, histogram
    ):
        return ()
    capacities = {weight: count for weight, count in histogram}
    maximum_weight = max(capacities)
    allocations: List[Tuple[int, int, int, int]] = []
    if maximum_weight == 1:
        allocations.append((representative_count, 0, 0, 0))
    elif maximum_weight == 2:
        count_2 = weighted_count - representative_count
        allocations.append((representative_count - count_2, count_2, 0, 0))
    elif maximum_weight == 4:
        deficit = 4 * representative_count - weighted_count
        for count_1 in range(min(capacities.get(1, 0), representative_count) + 1):
            remaining = deficit - 3 * count_1
            if remaining < 0 or remaining % 2:
                continue
            count_2 = remaining // 2
            count_4 = representative_count - count_1 - count_2
            if (
                0 <= count_2 <= capacities.get(2, 0)
                and 0 <= count_4 <= capacities.get(4, 0)
            ):
                allocations.append((count_1, count_2, count_4, 0))
    elif maximum_weight == 8:
        deficit = 8 * representative_count - weighted_count
        for count_1 in range(min(capacities.get(1, 0), representative_count) + 1):
            maximum_2 = min(
                capacities.get(2, 0), representative_count - count_1
            )
            for count_2 in range(maximum_2 + 1):
                remaining = deficit - 7 * count_1 - 6 * count_2
                if remaining < 0 or remaining % 4:
                    continue
                count_4 = remaining // 4
                count_8 = representative_count - count_1 - count_2 - count_4
                if (
                    0 <= count_4 <= capacities.get(4, 0)
                    and 0 <= count_8 <= capacities.get(8, 0)
                ):
                    allocations.append((count_1, count_2, count_4, count_8))
    return tuple(allocations)


def _bucket_partition_is_feasible(
    buckets: Sequence[Tuple[int, int]],
    histogram: Tuple[Tuple[int, int], ...],
    *,
    consume_all: bool,
) -> bool:
    """Prove that all buckets share one bounded orbit-weight inventory."""

    capacities_by_weight = {weight: count for weight, count in histogram}
    capacities = tuple(capacities_by_weight.get(weight, 0) for weight in (1, 2, 4, 8))
    options = [
        _bucket_weight_allocations(representative, weighted, histogram)
        for representative, weighted in buckets
    ]
    if any(not values for values in options):
        return False
    total_representatives = sum(pair[0] for pair in buckets)
    total_weight = sum(pair[1] for pair in buckets)
    if consume_all and (
        total_representatives != sum(capacities)
        or total_weight
        != sum(weight * capacities[index] for index, weight in enumerate((1, 2, 4, 8)))
    ):
        return False
    maximum_weight = max(capacities_by_weight)
    if maximum_weight <= 2:
        used = tuple(sum(values[0][index] for values in options) for index in range(4))
        return used == capacities if consume_all else all(
            used[index] <= capacities[index] for index in range(4)
        )
    if maximum_weight == 4:
        reachable_ones = {0}
        for values in options:
            reachable_ones = {
                used + allocation[0]
                for used in reachable_ones
                for allocation in values
                if used + allocation[0] <= capacities[0]
            }
            if not reachable_ones:
                return False
        for count_1 in reachable_ones:
            deficit = 4 * total_representatives - total_weight
            remaining = deficit - 3 * count_1
            if remaining < 0 or remaining % 2:
                continue
            count_2 = remaining // 2
            count_4 = total_representatives - count_1 - count_2
            used = (count_1, count_2, count_4, 0)
            if consume_all:
                if used == capacities:
                    return True
            elif all(0 <= used[index] <= capacities[index] for index in range(4)):
                return True
        return False

    reachable = {(0, 0, 0)}
    processed_representatives = 0
    for values, bucket in zip(options, buckets):
        processed_representatives += bucket[0]
        next_reachable = set()
        for used_1, used_2, used_4 in reachable:
            for allocation in values:
                candidate = (
                    used_1 + allocation[0],
                    used_2 + allocation[1],
                    used_4 + allocation[2],
                )
                used_8 = processed_representatives - sum(candidate)
                if (
                    candidate[0] <= capacities[0]
                    and candidate[1] <= capacities[1]
                    and candidate[2] <= capacities[2]
                    and used_8 <= capacities[3]
                ):
                    next_reachable.add(candidate)
        if not next_reachable:
            return False
        reachable = next_reachable
    if consume_all:
        return capacities[:3] in reachable
    return any(
        total_representatives - sum(candidate) <= capacities[3]
        for candidate in reachable
    )


def _transform_position(position: Position, transform: str) -> Position:
    row, column = position
    if transform == "I":
        return position
    if transform == "R90":
        return (column, 2 - row)
    if transform == "R180":
        return (2 - row, 2 - column)
    if transform == "R270":
        return (2 - column, row)
    if transform == "FLR":
        return (row, 2 - column)
    if transform == "FTB":
        return (2 - row, column)
    if transform == "FD":
        return (column, row)
    if transform == "FA":
        return (2 - column, 2 - row)
    raise StaticCensusReconstructionError("unknown D4 transform")


def _build_setup_descriptor() -> Tuple[Dict[str, Any], SetupWeightTables]:
    source_rows: List[Tuple[int, Tuple[Position, ...], Tuple[Position, ...]]] = []
    for count_index, (a_count, b_count) in enumerate(_COUNT_PAIRS):
        before = len(source_rows)
        for positions_a in combinations(_BOARD, a_count):
            remaining = tuple(cell for cell in _BOARD if cell not in positions_a)
            for positions_b in combinations(remaining, b_count):
                source_rows.append((count_index, positions_a, positions_b))
        if len(source_rows) - before != _COUNT_PAIR_SUPPLIES[count_index]:
            raise StaticCensusReconstructionError("setup supply derivation changed")
    if len(source_rows) != _EXPECTED_SETUP_COUNT:
        raise StaticCensusReconstructionError("setup enumeration changed")

    records: List[Tuple[Any, ...]] = []
    identity_to_ordinal: Dict[Tuple[Any, Any], int] = {}
    for ordinal, (count_index, positions_a, positions_b) in enumerate(source_rows):
        payload = {
            "setup_version": 1,
            "positions": {
                "A": [list(position) for position in positions_a],
                "B": [list(position) for position in positions_b],
            },
        }
        canonical = _canonical(payload)
        setup_hash = _domain_hash(_TYPED_SETUP_HASH_DOMAIN, canonical)
        key = (positions_a, positions_b)
        if key in identity_to_ordinal:
            raise StaticCensusReconstructionError("setup enumeration aliased")
        identity_to_ordinal[key] = ordinal
        records.append(
            (ordinal, count_index, positions_a, positions_b, canonical, setup_hash)
        )

    rows: List[Tuple[Any, ...]] = []
    for record in records:
        image_ordinals = []
        for transform in _D4:
            transformed_a = tuple(
                sorted(_transform_position(position, transform) for position in record[2])
            )
            transformed_b = tuple(
                sorted(_transform_position(position, transform) for position in record[3])
            )
            image_ordinals.append(
                identity_to_ordinal[(transformed_a, transformed_b)]
            )
        rows.append(record + (tuple(image_ordinals),))

    fixed_counts = tuple(
        sum(row[6][index] == row[0] for row in rows)
        for index in range(len(_D4))
    )
    if fixed_counts != _FIXED_SETUP_COUNTS:
        raise StaticCensusReconstructionError("setup fixed-point counts changed")

    ordered_setup_values = [row[4] for row in rows]
    image_values = [
        _canonical(
            {
                "ordinal": row[0],
                "setup_hash": row[5],
                "image_ordinals": list(row[6]),
            }
        )
        for row in rows
    ]
    group_mapping_values: List[str] = []
    groups: List[Dict[str, Any]] = []
    group_pair_histograms: List[Tuple[Tuple[Tuple[int, int], ...], ...]] = []
    name_indexes = {name: index for index, name in enumerate(_D4)}
    for group_index, signature in enumerate(_STABILIZERS):
        transform_indexes = tuple(name_indexes[name] for name in signature)
        raw_to_representative: List[int] = []
        for row in rows:
            images = {row[6][index] for index in transform_indexes}
            representative = min(images, key=lambda item: rows[item][4].encode("utf-8"))
            raw_to_representative.append(representative)
            group_mapping_values.append(
                _canonical(
                    {
                        "group_index": group_index,
                        "raw_ordinal": row[0],
                        "representative_ordinal": representative,
                    }
                )
            )
        representative_values: List[str] = []
        histogram: Dict[int, int] = {}
        pair_histograms: List[Dict[int, int]] = [dict() for _ in _COUNT_PAIRS]
        for representative in sorted(set(raw_to_representative)):
            images = {rows[representative][6][index] for index in transform_indexes}
            weight = len(images)
            histogram[weight] = histogram.get(weight, 0) + 1
            count_index = rows[representative][1]
            pair_histogram = pair_histograms[count_index]
            pair_histogram[weight] = pair_histogram.get(weight, 0) + 1
            representative_values.append(
                _canonical(
                    {
                        "representative_ordinal": representative,
                        "representative_setup_hash": rows[representative][5],
                        "orbit_weight": weight,
                    }
                )
            )
        observed = tuple(sorted(histogram.items()))
        frozen_pair_histograms = tuple(
            tuple(sorted(pair_histogram.items()))
            for pair_histogram in pair_histograms
        )
        if (
            len(representative_values) != _SETUP_ORBIT_COUNTS[group_index]
            or observed != _SETUP_WEIGHT_HISTOGRAMS[group_index]
            or sum(weight * count for weight, count in observed)
            != _EXPECTED_SETUP_COUNT
        ):
            raise StaticCensusReconstructionError("setup quotient changed")
        if any(
            sum(weight * count for weight, count in pair_histogram)
            != _COUNT_PAIR_SUPPLIES[index]
            for index, pair_histogram in enumerate(frozen_pair_histograms)
        ):
            raise StaticCensusReconstructionError("setup count-pair quotient changed")
        group_pair_histograms.append(frozen_pair_histograms)
        groups.append(
            {
                "signature": list(signature),
                "setup_orbit_count": len(representative_values),
                "weighted_setup_count": _EXPECTED_SETUP_COUNT,
                "weight_histogram": {
                    str(weight): count for weight, count in observed
                },
                "ordered_representative_root": _sequence_root(
                    _SETUP_GROUP_REPRESENTATIVE_ROOT_DOMAIN
                    + group_index.to_bytes(1, "big"),
                    representative_values,
                ),
            }
        )

    body = {
        "setup_orbit_table_version": 1,
        "board": {
            "rows": 3,
            "columns": 3,
            "cell_order": [list(position) for position in _BOARD],
        },
        "count_pair_order": [list(pair) for pair in _COUNT_PAIRS],
        "count_pair_supplies": list(_COUNT_PAIR_SUPPLIES),
        "setup_count": _EXPECTED_SETUP_COUNT,
        "d4_order": list(_D4),
        "fixed_setup_counts": {
            name: fixed_counts[index] for index, name in enumerate(_D4)
        },
        "groups": groups,
        "roots": {
            "ordered_setup_root": _sequence_root(
                _ORDERED_SETUP_ROOT_DOMAIN, ordered_setup_values
            ),
            "ordered_d4_image_ordinal_root": _sequence_root(
                _SETUP_IMAGE_ROOT_DOMAIN, image_values
            ),
            "ordered_group_mapping_root": _sequence_root(
                _SETUP_GROUP_MAPPING_ROOT_DOMAIN, group_mapping_values
            ),
        },
    }
    descriptor = dict(body)
    descriptor["descriptor_root"] = _domain_hash(
        _SETUP_DESCRIPTOR_DOMAIN, _canonical(body)
    )
    if descriptor["descriptor_root"] != _EXPECTED_SETUP_ROOT:
        raise StaticCensusReconstructionError("pinned setup descriptor changed")
    return descriptor, tuple(group_pair_histograms)


def _transform_edge(edge: str, transform: str) -> str:
    index = _EDGES.index(edge)
    if transform == "I":
        target = index
    elif transform == "R90":
        target = (index + 1) % 4
    elif transform == "R180":
        target = (index + 2) % 4
    elif transform == "R270":
        target = (index + 3) % 4
    elif transform == "FLR":
        target = (-index) % 4
    elif transform == "FTB":
        target = (2 - index) % 4
    elif transform == "FD":
        target = (3 - index) % 4
    elif transform == "FA":
        target = (1 - index) % 4
    else:
        raise StaticCensusReconstructionError("unknown D4 transform")
    return _EDGES[target]


def _validate_role(role_value: Any, label: str) -> Dict[str, Any]:
    role = _exact_dict(role_value, label)
    _exact_keys(
        role,
        ("action_primitive", "goal_primitive", "vector_profile", "target_edges"),
        label,
    )
    action = role["action_primitive"]
    goal = role["goal_primitive"]
    profile = role["vector_profile"]
    edges = role["target_edges"]
    if type(action) is not str or action not in _ACTIONS:
        raise StaticCensusReconstructionError(label + " action changed")
    if type(goal) is not str or goal not in _GOALS:
        raise StaticCensusReconstructionError(label + " goal changed")
    if type(profile) is not str or profile not in _PROFILES:
        raise StaticCensusReconstructionError(label + " profile changed")
    if type(edges) is not list or any(
        type(edge) is not str or edge not in _EDGES for edge in edges
    ):
        raise StaticCensusReconstructionError(label + " target edges changed")
    if goal == "CONNECT_EDGES" and edges not in (
        ["TOP", "BOTTOM"],
        ["RIGHT", "LEFT"],
    ):
        raise StaticCensusReconstructionError(label + " CONNECT target changed")
    if goal == "REACH_EDGE" and len(edges) != 1:
        raise StaticCensusReconstructionError(label + " REACH target changed")
    if goal == "ELIMINATE" and edges:
        raise StaticCensusReconstructionError(label + " ELIMINATE target changed")
    if goal == "ELIMINATE" and action not in ("MOVE_CAPTURE", "CONVERT"):
        raise StaticCensusReconstructionError(label + " role is incoherent")
    if action == "PLACE":
        if profile != "NONE":
            raise StaticCensusReconstructionError(label + " PLACE profile changed")
    elif profile == "NONE":
        raise StaticCensusReconstructionError(label + " movement profile changed")
    return role


def _validate_skeleton_json(canonical: Any) -> Tuple[Dict[str, Any], Stabilizer]:
    if type(canonical) is not str:
        raise StaticCensusReconstructionError("skeleton JSON changed type")
    payload = _loads_exact(canonical, "skeleton JSON")
    _validate_json_tree(payload)
    skeleton = _exact_dict(payload, "skeleton")
    _exact_keys(skeleton, ("universe_version", "roles"), "skeleton")
    if type(skeleton["universe_version"]) is not int or skeleton["universe_version"] != 1:
        raise StaticCensusReconstructionError("skeleton version changed")
    roles = _exact_dict(skeleton["roles"], "skeleton roles")
    _exact_keys(roles, _FIRST_PLAYERS, "skeleton roles")
    role_a = _validate_role(roles["A"], "skeleton role A")
    role_b = _validate_role(roles["B"], "skeleton role B")
    if not (
        role_a["action_primitive"] in _V4_ACTIONS
        or role_b["action_primitive"] in _V4_ACTIONS
        or role_a["goal_primitive"] == "ELIMINATE"
        or role_b["goal_primitive"] == "ELIMINATE"
    ):
        raise StaticCensusReconstructionError("skeleton escaped v4 admission")
    if _canonical(skeleton) != canonical:
        raise StaticCensusReconstructionError("skeleton JSON is not canonical")

    def transformed(transform: str, swapped: bool) -> str:
        source_roles = (role_b, role_a) if swapped else (role_a, role_b)
        result_roles: Dict[str, Any] = {}
        for owner, source in zip(_FIRST_PLAYERS, source_roles):
            target = dict(source)
            edges = [_transform_edge(edge, transform) for edge in source["target_edges"]]
            if source["goal_primitive"] == "CONNECT_EDGES":
                edge_set = frozenset(edges)
                if edge_set == frozenset(("TOP", "BOTTOM")):
                    edges = ["TOP", "BOTTOM"]
                elif edge_set == frozenset(("RIGHT", "LEFT")):
                    edges = ["RIGHT", "LEFT"]
                else:
                    raise StaticCensusReconstructionError(
                        "D4 transform broke a CONNECT target"
                    )
            target["target_edges"] = edges
            result_roles[owner] = target
        return _canonical({"universe_version": 1, "roles": result_roles})

    all_images = [
        transformed(transform, swapped)
        for swapped in (False, True)
        for transform in _D4
    ]
    if canonical != min(all_images):
        raise StaticCensusReconstructionError("skeleton is not role-neutral canonical")
    if any(transformed(transform, True) == canonical for transform in _D4):
        raise StaticCensusReconstructionError("skeleton became role-swap self-isomorphic")
    stabilizer = tuple(
        transform for transform in _D4 if transformed(transform, False) == canonical
    )
    if stabilizer not in _STABILIZERS:
        raise StaticCensusReconstructionError("skeleton stabilizer escaped the domain")
    program = (
        role_a["action_primitive"],
        role_a["goal_primitive"],
        role_b["action_primitive"],
        role_b["goal_primitive"],
    )
    reverse = (program[2], program[3], program[0], program[1])
    if program in _OLD_SEMANTIC_SPECS or reverse in _OLD_SEMANTIC_SPECS:
        raise StaticCensusReconstructionError("skeleton entered an old semantic region")
    return skeleton, stabilizer


def _semantic_hash(skeleton: Dict[str, Any]) -> str:
    roles = skeleton["roles"]
    role_payloads = {
        owner: {
            "action_primitive": roles[owner]["action_primitive"],
            "goal_primitive": roles[owner]["goal_primitive"],
        }
        for owner in _FIRST_PLAYERS
    }
    ordered = {"universe_version": 1, "roles": role_payloads}
    swapped = {
        "universe_version": 1,
        "roles": {"A": role_payloads["B"], "B": role_payloads["A"]},
    }
    return _domain_hash(
        _ROLE_NEUTRAL_SEMANTIC_HASH_DOMAIN,
        min(_canonical(ordered), _canonical(swapped)),
    )


def _reason_payload(mask: int) -> List[Dict[str, Any]]:
    return [
        {"code": code, "role": role, "first_player": first_player}
        for index, (code, role, first_player) in enumerate(_REASON_ATOMS)
        if mask & (1 << index)
    ]


def _validate_shard(
    summary_value: Any,
    ordinal: int,
    setup_weight_tables: SetupWeightTables,
) -> SkeletonRow:
    summary = _exact_dict(summary_value, "shard summary")
    _exact_keys(
        summary,
        (
            "static_census_shard_version",
            "skeleton",
            "setup_orbit",
            "eligibility",
            "contact",
            "eligible_supply_by_count_pair_and_contact",
            "work_extrema",
            "roots",
            "shard_commitment",
        ),
        "shard summary",
    )
    if type(summary["static_census_shard_version"]) is not int or summary[
        "static_census_shard_version"
    ] != 1:
        raise StaticCensusReconstructionError("shard version changed")

    skeleton = _exact_dict(summary["skeleton"], "shard skeleton")
    _exact_keys(
        skeleton,
        (
            "ordinal",
            "canonical_profiled_skeleton_json",
            "typed_skeleton_hash",
            "role_neutral_skeleton_hash",
            "role_neutral_semantic_hash",
            "exact_stabilizer",
        ),
        "shard skeleton",
    )
    if type(skeleton["ordinal"]) is not int or skeleton["ordinal"] != ordinal:
        raise StaticCensusReconstructionError("shard order changed")
    canonical = skeleton["canonical_profiled_skeleton_json"]
    skeleton_payload, stabilizer = _validate_skeleton_json(canonical)
    if type(skeleton["exact_stabilizer"]) is not list or any(
        type(name) is not str for name in skeleton["exact_stabilizer"]
    ):
        raise StaticCensusReconstructionError("shard stabilizer changed type")
    if tuple(skeleton["exact_stabilizer"]) != stabilizer:
        raise StaticCensusReconstructionError("shard stabilizer changed")
    typed_hash = _domain_hash(_PROFILED_SKELETON_HASH_DOMAIN, canonical)
    neutral_hash = _domain_hash(_ROLE_NEUTRAL_SKELETON_HASH_DOMAIN, canonical)
    semantic_hash = _semantic_hash(skeleton_payload)
    if skeleton["typed_skeleton_hash"] != typed_hash:
        raise StaticCensusReconstructionError("typed skeleton hash changed")
    if skeleton["role_neutral_skeleton_hash"] != neutral_hash:
        raise StaticCensusReconstructionError("neutral skeleton hash changed")
    if skeleton["role_neutral_semantic_hash"] != semantic_hash:
        raise StaticCensusReconstructionError("semantic hash changed")
    group_index = _STABILIZERS.index(stabilizer)
    expected_orbit_count = _SETUP_ORBIT_COUNTS[group_index]
    expected_histogram = _SETUP_WEIGHT_HISTOGRAMS[group_index]
    pair_histograms = setup_weight_tables[group_index]

    setup = _exact_dict(summary["setup_orbit"], "shard setup orbit")
    _exact_keys(
        setup,
        (
            "setup_orbit_table_root",
            "representative_count",
            "weighted_setup_count",
            "paired_first_player_member_count",
            "weight_histogram",
        ),
        "shard setup orbit",
    )
    expected_setup = {
        "setup_orbit_table_root": _EXPECTED_SETUP_ROOT,
        "representative_count": expected_orbit_count,
        "weighted_setup_count": _EXPECTED_SETUP_COUNT,
        "paired_first_player_member_count": 2 * _EXPECTED_SETUP_COUNT,
        "weight_histogram": {
            str(weight): count for weight, count in expected_histogram
        },
    }
    for field in (
        "representative_count",
        "weighted_setup_count",
        "paired_first_player_member_count",
    ):
        _exact_int(setup[field], "shard " + field, minimum=1)
    histogram = _exact_dict(setup["weight_histogram"], "shard weight histogram")
    if any(type(key) is not str or type(value) is not int for key, value in histogram.items()):
        raise StaticCensusReconstructionError("shard weight histogram changed type")
    if setup != expected_setup:
        raise StaticCensusReconstructionError("shard setup arithmetic changed")

    eligibility = _exact_dict(summary["eligibility"], "shard eligibility")
    _exact_keys(
        eligibility,
        (
            "representative_eligible_count",
            "weighted_eligible_count",
            "paired_first_player_eligible_member_count",
            "reason_combinations",
        ),
        "shard eligibility",
    )
    for field in (
        "representative_eligible_count",
        "weighted_eligible_count",
        "paired_first_player_eligible_member_count",
    ):
        _exact_int(eligibility[field], "shard " + field, minimum=0)
    combinations_value = eligibility["reason_combinations"]
    if type(combinations_value) is not list:
        raise StaticCensusReconstructionError("reason combinations changed type")
    previous_mask = -1
    representative_total = weighted_total = 0
    eligible_representative = eligible_weighted = 0
    reason_histogram: List[Tuple[int, int, int]] = []
    for combination_value in combinations_value:
        combination = _exact_dict(combination_value, "reason combination")
        _exact_keys(
            combination,
            ("reason_mask", "reasons", "representative_count", "weighted_count"),
            "reason combination",
        )
        mask = _exact_int(
            combination["reason_mask"],
            "reason mask",
            minimum=0,
            maximum=_REASON_MASK_COUNT - 1,
        )
        representative_count = _exact_int(
            combination["representative_count"],
            "reason representative count",
            minimum=1,
        )
        weighted_count = _exact_int(
            combination["weighted_count"], "reason weighted count", minimum=1
        )
        if (
            mask <= previous_mask
            or combination["reasons"] != _reason_payload(mask)
            or not _weight_pair_is_feasible(
                representative_count, weighted_count, expected_histogram
            )
        ):
            raise StaticCensusReconstructionError("reason combination changed")
        previous_mask = mask
        representative_total += representative_count
        weighted_total += weighted_count
        reason_histogram.append((mask, representative_count, weighted_count))
        if mask == 0:
            eligible_representative = representative_count
            eligible_weighted = weighted_count
    if (
        representative_total != expected_orbit_count
        or weighted_total != _EXPECTED_SETUP_COUNT
        or eligibility["representative_eligible_count"] != eligible_representative
        or eligibility["weighted_eligible_count"] != eligible_weighted
        or eligibility["paired_first_player_eligible_member_count"]
        != 2 * eligible_weighted
    ):
        raise StaticCensusReconstructionError("shard reason arithmetic changed")
    if not _bucket_partition_is_feasible(
        [(representative, weighted) for _, representative, weighted in reason_histogram],
        expected_histogram,
        consume_all=True,
    ):
        raise StaticCensusReconstructionError("shard reason weights do not partition")

    contact = _exact_dict(summary["contact"], "shard contact")
    _exact_keys(contact, _CONTACT_CLASSES, "shard contact")
    contact_rep = contact_weight = eligible_contact_rep = eligible_contact_weight = 0
    eligible_contact_pairs: Dict[str, Tuple[int, int]] = {}
    for contact_class in _CONTACT_CLASSES:
        row = _exact_dict(contact[contact_class], "shard contact row")
        _exact_keys(
            row,
            (
                "representative_count",
                "weighted_count",
                "eligible_representative_count",
                "eligible_weighted_count",
            ),
            "shard contact row",
        )
        for field in row:
            _exact_int(row[field], "shard contact " + field, minimum=0)
        if (
            row["eligible_representative_count"] > row["representative_count"]
            or row["eligible_weighted_count"] > row["weighted_count"]
            or not _weight_pair_is_feasible(
                row["representative_count"],
                row["weighted_count"],
                expected_histogram,
            )
            or not _weight_pair_is_feasible(
                row["eligible_representative_count"],
                row["eligible_weighted_count"],
                expected_histogram,
            )
        ):
            raise StaticCensusReconstructionError("eligible contact exceeds total")
        eligible_contact_pairs[contact_class] = (
            row["eligible_representative_count"],
            row["eligible_weighted_count"],
        )
        contact_rep += row["representative_count"]
        contact_weight += row["weighted_count"]
        eligible_contact_rep += row["eligible_representative_count"]
        eligible_contact_weight += row["eligible_weighted_count"]
    if (
        contact_rep != expected_orbit_count
        or contact_weight != _EXPECTED_SETUP_COUNT
        or eligible_contact_rep != eligible_representative
        or eligible_contact_weight != eligible_weighted
    ):
        raise StaticCensusReconstructionError("shard contact arithmetic changed")
    contact_partition = []
    for contact_class in _CONTACT_CLASSES:
        row = contact[contact_class]
        contact_partition.extend(
            (
                (
                    row["eligible_representative_count"],
                    row["eligible_weighted_count"],
                ),
                (
                    row["representative_count"]
                    - row["eligible_representative_count"],
                    row["weighted_count"] - row["eligible_weighted_count"],
                ),
            )
        )
    if not _bucket_partition_is_feasible(
        contact_partition, expected_histogram, consume_all=True
    ):
        raise StaticCensusReconstructionError("shard contact weights do not partition")

    supply = summary["eligible_supply_by_count_pair_and_contact"]
    if type(supply) is not list or len(supply) != len(_COUNT_PAIRS) * 2:
        raise StaticCensusReconstructionError("shard supply shape changed")
    supply_rep = supply_weight = 0
    supply_by_contact = {
        contact_class: [0, 0] for contact_class in _CONTACT_CLASSES
    }
    supply_by_pair = [[0, 0] for _ in _COUNT_PAIRS]
    supply_buckets_by_pair: List[List[Tuple[int, int]]] = [
        [] for _ in _COUNT_PAIRS
    ]
    for index, row_value in enumerate(supply):
        row = _exact_dict(row_value, "shard supply row")
        _exact_keys(
            row,
            ("initial_counts", "contact_class", "representative_count", "weighted_count"),
            "shard supply row",
        )
        counts = _exact_dict(row["initial_counts"], "shard supply counts")
        _exact_keys(counts, _FIRST_PLAYERS, "shard supply counts")
        expected_pair = _COUNT_PAIRS[index // 2]
        expected_contact = _CONTACT_CLASSES[index % 2]
        if (
            type(counts["A"]) is not int
            or type(counts["B"]) is not int
            or counts != {"A": expected_pair[0], "B": expected_pair[1]}
            or row["contact_class"] != expected_contact
        ):
            raise StaticCensusReconstructionError("shard supply coordinate changed")
        representative_supply = _exact_int(
            row["representative_count"], "shard supply representative", minimum=0
        )
        weighted_supply = _exact_int(
            row["weighted_count"], "shard supply weighted", minimum=0
        )
        if not _weight_pair_is_feasible(
            representative_supply, weighted_supply, expected_histogram
        ):
            raise StaticCensusReconstructionError("shard supply weight changed")
        supply_rep += representative_supply
        supply_weight += weighted_supply
        supply_by_contact[expected_contact][0] += representative_supply
        supply_by_contact[expected_contact][1] += weighted_supply
        supply_by_pair[index // 2][0] += representative_supply
        supply_by_pair[index // 2][1] += weighted_supply
        supply_buckets_by_pair[index // 2].append(
            (representative_supply, weighted_supply)
        )
    if (
        supply_rep != eligible_representative
        or supply_weight != eligible_weighted
        or any(
            tuple(supply_by_contact[contact_class])
            != eligible_contact_pairs[contact_class]
            for contact_class in _CONTACT_CLASSES
        )
        or any(
            representative_count > weighted_count
            or weighted_count > _COUNT_PAIR_SUPPLIES[index]
            for index, (representative_count, weighted_count) in enumerate(
                supply_by_pair
            )
        )
        or any(
            not _bucket_partition_is_feasible(
                supply_buckets_by_pair[index],
                pair_histograms[index],
                consume_all=False,
            )
            for index in range(len(_COUNT_PAIRS))
        )
    ):
        raise StaticCensusReconstructionError("shard supply arithmetic changed")

    work = _exact_dict(summary["work_extrema"], "shard work extrema")
    _exact_keys(work, _FIRST_PLAYERS, "shard work extrema")
    for first_player in _FIRST_PLAYERS:
        tempo = _exact_dict(work[first_player], "shard tempo work")
        _exact_keys(tempo, _WORK_FIELDS, "shard tempo work")
        for field in _WORK_FIELDS:
            bounds = _exact_dict(tempo[field], "shard work bounds")
            _exact_keys(bounds, ("minimum", "maximum"), "shard work bounds")
            ceiling = 115_194 if field == "state_weight_sum" else 2_070_432
            minimum = _exact_int(
                bounds["minimum"], "shard work minimum", minimum=0, maximum=ceiling
            )
            maximum = _exact_int(
                bounds["maximum"], "shard work maximum", minimum=0, maximum=ceiling
            )
            if minimum > maximum:
                raise StaticCensusReconstructionError("shard work bounds inverted")

    roots = _exact_dict(summary["roots"], "shard roots")
    _exact_keys(
        roots,
        (
            "ordered_leaf_commitment_root",
            "ordered_initial_structure_result_root",
            "ordered_role_facts_root",
            "ordered_count_lattice_root",
            "ordered_descriptor_group_roots",
        ),
        "shard roots",
    )
    for field in (
        "ordered_leaf_commitment_root",
        "ordered_initial_structure_result_root",
        "ordered_role_facts_root",
        "ordered_count_lattice_root",
    ):
        if not _is_sha256(roots[field]):
            raise StaticCensusReconstructionError("shard root changed format")
    group_roots = _exact_dict(
        roots["ordered_descriptor_group_roots"], "shard descriptor roots"
    )
    _exact_keys(group_roots, _DESCRIPTOR_GROUPS, "shard descriptor roots")
    if any(not _is_sha256(group_roots[name]) for name in _DESCRIPTOR_GROUPS):
        raise StaticCensusReconstructionError("shard descriptor root changed format")

    commitment = summary["shard_commitment"]
    if not _is_sha256(commitment):
        raise StaticCensusReconstructionError("shard commitment changed format")
    shard_body = dict(summary)
    shard_body.pop("shard_commitment")
    if commitment != _domain_hash(_STATIC_SHARD_SUMMARY_DOMAIN, _canonical(shard_body)):
        raise StaticCensusReconstructionError("shard commitment changed")

    return (
        ordinal,
        canonical,
        typed_hash,
        neutral_hash,
        semantic_hash,
        stabilizer,
        expected_orbit_count,
        expected_histogram,
    )


def _build_skeleton_descriptor(rows: Sequence[SkeletonRow]) -> Dict[str, Any]:
    if len(rows) != _EXPECTED_SKELETON_COUNT:
        raise StaticCensusReconstructionError("skeleton authority is incomplete")
    canonicals = [row[1] for row in rows]
    if _fresh_root(canonicals) != _EXPECTED_FRESH_SKELETON_ROOT:
        raise StaticCensusReconstructionError("fresh skeleton root changed")
    if len({row[4] for row in rows}) != 109:
        raise StaticCensusReconstructionError("fresh semantic class count changed")
    values: List[str] = []
    stabilizer_counts: Dict[Stabilizer, int] = {}
    global_weights: Dict[int, int] = {}
    factorized = weighted = 0
    previous: Optional[str] = None
    for expected_ordinal, row in enumerate(rows):
        if row[0] != expected_ordinal or (previous is not None and row[1] <= previous):
            raise StaticCensusReconstructionError("skeleton authority order changed")
        previous = row[1]
        stabilizer = row[5]
        stabilizer_counts[stabilizer] = stabilizer_counts.get(stabilizer, 0) + 1
        factorized += row[6]
        weighted += _EXPECTED_SETUP_COUNT
        for weight, count in row[7]:
            global_weights[weight] = global_weights.get(weight, 0) + count
        values.append(
            _canonical(
                {
                    "skeleton_ordinal": row[0],
                    "skeleton_json": row[1],
                    "typed_skeleton_hash": row[2],
                    "role_neutral_skeleton_hash": row[3],
                    "role_neutral_semantic_hash": row[4],
                    "exact_stabilizer": list(stabilizer),
                    "setup_orbit_count": row[6],
                    "setup_weight_histogram": {
                        str(weight): count for weight, count in row[7]
                    },
                }
            )
        )
    if tuple(stabilizer_counts.get(value, 0) for value in _STABILIZERS) != (
        _STABILIZER_SKELETON_COUNTS
    ):
        raise StaticCensusReconstructionError("skeleton stabilizer counts changed")
    if (
        factorized != _EXPECTED_FACTORIZED_COUNT
        or weighted != _EXPECTED_LABELED_COUNT
        or tuple(sorted(global_weights.items())) != _GLOBAL_WEIGHT_HISTOGRAM
        or (_EXPECTED_ALL_ORDERED - _EXPECTED_SELF_ISOMORPHIC - _EXPECTED_OLD_REGION)
        // 2
        != factorized
    ):
        raise StaticCensusReconstructionError("skeleton population changed")
    body = {
        "skeleton_authority_version": 1,
        "universe_descriptor_root": _EXPECTED_UNIVERSE_ROOT,
        "fresh_canonical_skeleton_root": _EXPECTED_FRESH_SKELETON_ROOT,
        "skeleton_count": _EXPECTED_SKELETON_COUNT,
        "d4_order": list(_D4),
        "exact_stabilizer_groups": [
            {
                "signature": list(signature),
                "skeleton_count": stabilizer_counts[signature],
                "setup_orbit_count_per_skeleton": _SETUP_ORBIT_COUNTS[index],
                "setup_weight_histogram_per_skeleton": {
                    str(weight): count
                    for weight, count in _SETUP_WEIGHT_HISTOGRAMS[index]
                },
            }
            for index, signature in enumerate(_STABILIZERS)
        ],
        "factorized_carrier_count": factorized,
        "labeled_setup_count": weighted,
        "paired_first_player_member_count": 2 * weighted,
        "global_weight_histogram": {
            str(weight): count for weight, count in sorted(global_weights.items())
        },
        "independent_ordered_population_derivation": {
            "all_ordered_contribution": _EXPECTED_ALL_ORDERED,
            "self_isomorphic_contribution": _EXPECTED_SELF_ISOMORPHIC,
            "old_region_contribution": _EXPECTED_OLD_REGION,
            "fresh_cross_section_divisor": 2,
            "fresh_factorized_carrier_count": factorized,
        },
        "ordered_skeleton_authority_root": _sequence_root(
            _SKELETON_AUTHORITY_ROOT_DOMAIN, values
        ),
    }
    descriptor = dict(body)
    descriptor["descriptor_root"] = _domain_hash(
        _SKELETON_DESCRIPTOR_ROOT_DOMAIN, _canonical(body)
    )
    if descriptor["descriptor_root"] != _EXPECTED_SKELETON_ROOT:
        raise StaticCensusReconstructionError("pinned skeleton descriptor changed")
    return descriptor


def _new_work_extrema() -> Dict[str, Dict[str, List[Optional[int]]]]:
    return {
        first_player: {field: [None, None] for field in _WORK_FIELDS}
        for first_player in _FIRST_PLAYERS
    }


def _freeze_work_extrema(
    extrema: Dict[str, Dict[str, List[Optional[int]]]]
) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for first_player in _FIRST_PLAYERS:
        result[first_player] = {}
        for field in _WORK_FIELDS:
            minimum, maximum = extrema[first_player][field]
            if type(minimum) is not int or type(maximum) is not int:
                raise StaticCensusReconstructionError("global work extrema are incomplete")
            result[first_player][field] = {"minimum": minimum, "maximum": maximum}
    return result


def _reconstruct_report(payload_value: Any) -> Dict[str, Any]:
    payload = _exact_dict(payload_value, "static-census report")
    _exact_keys(
        payload,
        (
            "static_census_report_version",
            "authorities",
            "population",
            "eligibility",
            "contact",
            "eligible_supply_by_count_pair_and_contact",
            "work_extrema",
            "roots",
            "skeleton_shards",
            "report_digest",
        ),
        "static-census report",
    )
    if type(payload["static_census_report_version"]) is not int or payload[
        "static_census_report_version"
    ] != 1:
        raise StaticCensusReconstructionError("report version changed")
    authorities = _exact_dict(payload["authorities"], "report authorities")
    _exact_keys(
        authorities,
        (
            "setup_orbit_table",
            "skeleton_authority",
            "initial_structure_kernel_version",
            "count_lattice_table_root",
        ),
        "report authorities",
    )
    if type(authorities["initial_structure_kernel_version"]) is not int or authorities[
        "initial_structure_kernel_version"
    ] != 1:
        raise StaticCensusReconstructionError("kernel version changed")
    if authorities["count_lattice_table_root"] != _EXPECTED_COUNT_TABLE_ROOT:
        raise StaticCensusReconstructionError("count-table authority changed")
    expected_setup_descriptor, setup_weight_tables = _build_setup_descriptor()
    if _canonical(authorities["setup_orbit_table"]) != _canonical(
        expected_setup_descriptor
    ):
        raise StaticCensusReconstructionError("setup descriptor changed")

    shards = payload["skeleton_shards"]
    if type(shards) is not list or len(shards) != _EXPECTED_SKELETON_COUNT:
        raise StaticCensusReconstructionError("report shard sequence changed")
    reason_rep = [0] * _REASON_MASK_COUNT
    reason_weight = [0] * _REASON_MASK_COUNT
    global_weights: Dict[int, int] = {}
    contact_counts = {
        contact: {
            "representative_count": 0,
            "weighted_count": 0,
            "eligible_representative_count": 0,
            "eligible_weighted_count": 0,
        }
        for contact in _CONTACT_CLASSES
    }
    supply_rep: Dict[Tuple[int, int, str], int] = {}
    supply_weight: Dict[Tuple[int, int, str], int] = {}
    extrema = _new_work_extrema()
    commitments: List[str] = []
    leaf_roots: List[str] = []
    result_roots: List[str] = []
    role_roots: List[str] = []
    count_roots: List[str] = []
    group_roots: Dict[str, List[str]] = {
        name: [] for name in _DESCRIPTOR_GROUPS
    }
    skeleton_rows: List[SkeletonRow] = []

    for ordinal, summary in enumerate(shards):
        skeleton_rows.append(
            _validate_shard(summary, ordinal, setup_weight_tables)
        )
        setup_histogram = summary["setup_orbit"]["weight_histogram"]
        for weight_text, count in setup_histogram.items():
            weight = int(weight_text)
            global_weights[weight] = global_weights.get(weight, 0) + count
        for combination in summary["eligibility"]["reason_combinations"]:
            mask = combination["reason_mask"]
            reason_rep[mask] += combination["representative_count"]
            reason_weight[mask] += combination["weighted_count"]
        for contact in _CONTACT_CLASSES:
            source = summary["contact"][contact]
            for field in contact_counts[contact]:
                contact_counts[contact][field] += source[field]
        for row in summary["eligible_supply_by_count_pair_and_contact"]:
            counts = row["initial_counts"]
            key = (counts["A"], counts["B"], row["contact_class"])
            supply_rep[key] = supply_rep.get(key, 0) + row["representative_count"]
            supply_weight[key] = supply_weight.get(key, 0) + row["weighted_count"]
        for first_player in _FIRST_PLAYERS:
            for field in _WORK_FIELDS:
                bounds = summary["work_extrema"][first_player][field]
                target = extrema[first_player][field]
                target[0] = (
                    bounds["minimum"]
                    if target[0] is None
                    else min(target[0], bounds["minimum"])
                )
                target[1] = (
                    bounds["maximum"]
                    if target[1] is None
                    else max(target[1], bounds["maximum"])
                )
        roots = summary["roots"]
        commitments.append(summary["shard_commitment"])
        leaf_roots.append(roots["ordered_leaf_commitment_root"])
        result_roots.append(roots["ordered_initial_structure_result_root"])
        role_roots.append(roots["ordered_role_facts_root"])
        count_roots.append(roots["ordered_count_lattice_root"])
        for name in _DESCRIPTOR_GROUPS:
            group_roots[name].append(roots["ordered_descriptor_group_roots"][name])

    if tuple(sorted(global_weights.items())) != _GLOBAL_WEIGHT_HISTOGRAM:
        raise StaticCensusReconstructionError("global setup weights changed")
    if sum(reason_rep) != _EXPECTED_FACTORIZED_COUNT or sum(reason_weight) != (
        _EXPECTED_LABELED_COUNT
    ):
        raise StaticCensusReconstructionError("global reason totals changed")
    expected_skeleton_descriptor = _build_skeleton_descriptor(skeleton_rows)
    if _canonical(authorities["skeleton_authority"]) != _canonical(
        expected_skeleton_descriptor
    ):
        raise StaticCensusReconstructionError("skeleton descriptor changed")

    eligible_rep = reason_rep[0]
    eligible_weight = reason_weight[0]
    supply_rows = [
        {
            "initial_counts": {"A": pair[0], "B": pair[1]},
            "contact_class": contact,
            "representative_count": supply_rep.get((pair[0], pair[1], contact), 0),
            "weighted_count": supply_weight.get((pair[0], pair[1], contact), 0),
        }
        for pair in _COUNT_PAIRS
        for contact in _CONTACT_CLASSES
    ]
    expected_body = {
        "static_census_report_version": 1,
        "authorities": {
            "setup_orbit_table": expected_setup_descriptor,
            "skeleton_authority": expected_skeleton_descriptor,
            "initial_structure_kernel_version": 1,
            "count_lattice_table_root": _EXPECTED_COUNT_TABLE_ROOT,
        },
        "population": {
            "skeleton_count": _EXPECTED_SKELETON_COUNT,
            "factorized_carrier_count": _EXPECTED_FACTORIZED_COUNT,
            "labeled_setup_count": _EXPECTED_LABELED_COUNT,
            "paired_first_player_member_count": _EXPECTED_PAIRED_COUNT,
            "weight_histogram": {
                str(weight): count for weight, count in _GLOBAL_WEIGHT_HISTOGRAM
            },
        },
        "eligibility": {
            "representative_eligible_count": eligible_rep,
            "weighted_eligible_count": eligible_weight,
            "paired_first_player_eligible_member_count": 2 * eligible_weight,
            "representative_reason_mask_counts": reason_rep,
            "weighted_reason_mask_counts": reason_weight,
        },
        "contact": contact_counts,
        "eligible_supply_by_count_pair_and_contact": supply_rows,
        "work_extrema": _freeze_work_extrema(extrema),
        "roots": {
            "ordered_shard_commitment_root": _sequence_root(
                _STATIC_CHECKPOINT_DOMAIN + b"shards\0", commitments
            ),
            "ordered_leaf_commitment_shard_root": _sequence_root(
                _STATIC_REPORT_ROOT_DOMAIN + b"leaf-commitment-shards\0", leaf_roots
            ),
            "ordered_initial_structure_result_shard_root": _sequence_root(
                _STATIC_REPORT_ROOT_DOMAIN + b"result-shards\0", result_roots
            ),
            "ordered_role_facts_shard_root": _sequence_root(
                _STATIC_REPORT_ROOT_DOMAIN + b"role-shards\0", role_roots
            ),
            "ordered_count_lattice_shard_root": _sequence_root(
                _STATIC_REPORT_ROOT_DOMAIN + b"count-shards\0", count_roots
            ),
            "ordered_descriptor_group_shard_roots": {
                name: _sequence_root(
                    _STATIC_REPORT_ROOT_DOMAIN
                    + b"descriptor-shards\0"
                    + name.encode("ascii")
                    + b"\0",
                    group_roots[name],
                )
                for name in _DESCRIPTOR_GROUPS
            },
        },
        "skeleton_shards": shards,
    }
    body = dict(payload)
    report_digest = body.pop("report_digest")
    if not _is_sha256(report_digest):
        raise StaticCensusReconstructionError("report digest changed format")
    body_canonical = _canonical(body)
    if body_canonical != _canonical(expected_body):
        raise StaticCensusReconstructionError("report body does not reconstruct")
    if report_digest != _domain_hash(_STATIC_REPORT_BODY_DOMAIN, body_canonical):
        raise StaticCensusReconstructionError("report digest changed")
    return payload


def _reconstruct_artifact_v1(raw: bytes) -> Dict[str, Any]:
    """Reconstruct one exact stored report without revisiting carrier leaves."""

    if type(raw) is not bytes:
        raise TypeError("raw report must be exact bytes")
    if not raw:
        raise StaticCensusReconstructionError("raw report is empty")
    if len(raw) > STATIC_CENSUS_REPORT_MAX_BYTES_V1:
        raise StaticCensusReconstructionError("raw report exceeds the byte cap")
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as error:
        raise StaticCensusReconstructionError("raw report is not UTF-8") from error
    payload = _loads_exact(text, "static-census report")
    _validate_json_tree(payload)
    if _canonical(payload).encode("utf-8") != raw:
        raise StaticCensusReconstructionError("raw report bytes are not canonical")
    report = _reconstruct_report(payload)
    report_ref = {
        "byte_count": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    eligibility = report["eligibility"]
    summary = {
        "report_digest": report["report_digest"],
        "setup_orbit_table_root": report["authorities"]["setup_orbit_table"][
            "descriptor_root"
        ],
        "skeleton_authority_root": report["authorities"]["skeleton_authority"][
            "descriptor_root"
        ],
        "ordered_shard_commitment_root": report["roots"][
            "ordered_shard_commitment_root"
        ],
        "population": copy.deepcopy(report["population"]),
        "eligibility": {
            "representative_eligible_count": eligibility[
                "representative_eligible_count"
            ],
            "weighted_eligible_count": eligibility["weighted_eligible_count"],
            "paired_first_player_eligible_member_count": eligibility[
                "paired_first_player_eligible_member_count"
            ],
        },
    }
    return {
        "report": report,
        "report_ref": report_ref,
        "report_summary": summary,
    }


_RECONSTRUCTION_FUNCTION_BINDINGS = (
    ("StaticCensusReconstructionError", StaticCensusReconstructionError),
    ("_canonical", _canonical),
    ("_domain_hash", _domain_hash),
    ("_sequence_root", _sequence_root),
    ("_fresh_root", _fresh_root),
    ("_is_sha256", _is_sha256),
    ("_exact_dict", _exact_dict),
    ("_exact_keys", _exact_keys),
    ("_exact_int", _exact_int),
    ("_pairs_object", _pairs_object),
    ("_reject_float", _reject_float),
    ("_reject_constant", _reject_constant),
    ("_loads_exact", _loads_exact),
    ("_validate_json_tree", _validate_json_tree),
    ("_weight_pair_is_feasible", _weight_pair_is_feasible),
    ("_bucket_weight_allocations", _bucket_weight_allocations),
    ("_bucket_partition_is_feasible", _bucket_partition_is_feasible),
    ("_transform_position", _transform_position),
    ("_build_setup_descriptor", _build_setup_descriptor),
    ("_transform_edge", _transform_edge),
    ("_validate_role", _validate_role),
    ("_validate_skeleton_json", _validate_skeleton_json),
    ("_semantic_hash", _semantic_hash),
    ("_reason_payload", _reason_payload),
    ("_validate_shard", _validate_shard),
    ("_build_skeleton_descriptor", _build_skeleton_descriptor),
    ("_new_work_extrema", _new_work_extrema),
    ("_freeze_work_extrema", _freeze_work_extrema),
    ("_reconstruct_report", _reconstruct_report),
)
_RECONSTRUCTION_CONSTANT_BINDINGS = (
    ("STATIC_CENSUS_REPORT_MAX_BYTES_V1", STATIC_CENSUS_REPORT_MAX_BYTES_V1),
    (
        "STATIC_CENSUS_REPORT_MAX_JSON_NODES_V1",
        STATIC_CENSUS_REPORT_MAX_JSON_NODES_V1,
    ),
    (
        "STATIC_CENSUS_REPORT_MAX_JSON_DEPTH_V1",
        STATIC_CENSUS_REPORT_MAX_JSON_DEPTH_V1,
    ),
    ("_BOARD", _BOARD),
    ("_COUNT_PAIRS", _COUNT_PAIRS),
    ("_COUNT_PAIR_SUPPLIES", _COUNT_PAIR_SUPPLIES),
    ("_D4", _D4),
    ("_STABILIZERS", _STABILIZERS),
    ("_STABILIZER_SKELETON_COUNTS", _STABILIZER_SKELETON_COUNTS),
    ("_SETUP_ORBIT_COUNTS", _SETUP_ORBIT_COUNTS),
    ("_SETUP_WEIGHT_HISTOGRAMS", _SETUP_WEIGHT_HISTOGRAMS),
    ("_FIXED_SETUP_COUNTS", _FIXED_SETUP_COUNTS),
    ("_GLOBAL_WEIGHT_HISTOGRAM", _GLOBAL_WEIGHT_HISTOGRAM),
    ("_EXPECTED_SETUP_COUNT", _EXPECTED_SETUP_COUNT),
    ("_EXPECTED_SKELETON_COUNT", _EXPECTED_SKELETON_COUNT),
    ("_EXPECTED_FACTORIZED_COUNT", _EXPECTED_FACTORIZED_COUNT),
    ("_EXPECTED_LABELED_COUNT", _EXPECTED_LABELED_COUNT),
    ("_EXPECTED_PAIRED_COUNT", _EXPECTED_PAIRED_COUNT),
    ("_EXPECTED_ALL_ORDERED", _EXPECTED_ALL_ORDERED),
    ("_EXPECTED_SELF_ISOMORPHIC", _EXPECTED_SELF_ISOMORPHIC),
    ("_EXPECTED_OLD_REGION", _EXPECTED_OLD_REGION),
    ("_REASON_ATOMS", _REASON_ATOMS),
    ("_REASON_MASK_COUNT", _REASON_MASK_COUNT),
    ("_CONTACT_CLASSES", _CONTACT_CLASSES),
    ("_FIRST_PLAYERS", _FIRST_PLAYERS),
    ("_WORK_FIELDS", _WORK_FIELDS),
    ("_DESCRIPTOR_GROUPS", _DESCRIPTOR_GROUPS),
    ("_ACTIONS", _ACTIONS),
    ("_GOALS", _GOALS),
    ("_PROFILES", _PROFILES),
    ("_EDGES", _EDGES),
    ("_V4_ACTIONS", _V4_ACTIONS),
    ("_OLD_SEMANTIC_SPECS", _OLD_SEMANTIC_SPECS),
    ("_EXPECTED_UNIVERSE_ROOT", _EXPECTED_UNIVERSE_ROOT),
    ("_EXPECTED_FRESH_SKELETON_ROOT", _EXPECTED_FRESH_SKELETON_ROOT),
    ("_EXPECTED_COUNT_TABLE_ROOT", _EXPECTED_COUNT_TABLE_ROOT),
    ("_EXPECTED_SETUP_ROOT", _EXPECTED_SETUP_ROOT),
    ("_EXPECTED_SKELETON_ROOT", _EXPECTED_SKELETON_ROOT),
    ("_SETUP_DESCRIPTOR_DOMAIN", _SETUP_DESCRIPTOR_DOMAIN),
    ("_ORDERED_SETUP_ROOT_DOMAIN", _ORDERED_SETUP_ROOT_DOMAIN),
    ("_SETUP_IMAGE_ROOT_DOMAIN", _SETUP_IMAGE_ROOT_DOMAIN),
    ("_SETUP_GROUP_MAPPING_ROOT_DOMAIN", _SETUP_GROUP_MAPPING_ROOT_DOMAIN),
    (
        "_SETUP_GROUP_REPRESENTATIVE_ROOT_DOMAIN",
        _SETUP_GROUP_REPRESENTATIVE_ROOT_DOMAIN,
    ),
    ("_SKELETON_AUTHORITY_ROOT_DOMAIN", _SKELETON_AUTHORITY_ROOT_DOMAIN),
    ("_SKELETON_DESCRIPTOR_ROOT_DOMAIN", _SKELETON_DESCRIPTOR_ROOT_DOMAIN),
    ("_STATIC_SHARD_SUMMARY_DOMAIN", _STATIC_SHARD_SUMMARY_DOMAIN),
    ("_STATIC_CHECKPOINT_DOMAIN", _STATIC_CHECKPOINT_DOMAIN),
    ("_STATIC_REPORT_BODY_DOMAIN", _STATIC_REPORT_BODY_DOMAIN),
    ("_STATIC_REPORT_ROOT_DOMAIN", _STATIC_REPORT_ROOT_DOMAIN),
    ("_TYPED_SETUP_HASH_DOMAIN", _TYPED_SETUP_HASH_DOMAIN),
    ("_PROFILED_SKELETON_HASH_DOMAIN", _PROFILED_SKELETON_HASH_DOMAIN),
    ("_ROLE_NEUTRAL_SKELETON_HASH_DOMAIN", _ROLE_NEUTRAL_SKELETON_HASH_DOMAIN),
    ("_ROLE_NEUTRAL_SEMANTIC_HASH_DOMAIN", _ROLE_NEUTRAL_SEMANTIC_HASH_DOMAIN),
    ("_UNIVERSE_FRESH_ROOT_DOMAIN", _UNIVERSE_FRESH_ROOT_DOMAIN),
)
_BUILTIN_BINDINGS = (
    ("RecursionError", RecursionError),
    ("TypeError", TypeError),
    ("UnicodeDecodeError", UnicodeDecodeError),
    ("ValueError", ValueError),
    ("all", all),
    ("any", any),
    ("bool", bool),
    ("bytes", bytes),
    ("dict", dict),
    ("enumerate", enumerate),
    ("frozenset", frozenset),
    ("globals", globals),
    ("int", int),
    ("len", len),
    ("list", list),
    ("max", max),
    ("min", min),
    ("range", range),
    ("set", set),
    ("sorted", sorted),
    ("str", str),
    ("sum", sum),
    ("tuple", tuple),
    ("type", type),
    ("zip", zip),
)


def _assert_reconstruction_bindings(
    _function_bindings: Tuple[Tuple[str, Any], ...] = _RECONSTRUCTION_FUNCTION_BINDINGS,
    _constant_bindings: Tuple[Tuple[str, Any], ...] = _RECONSTRUCTION_CONSTANT_BINDINGS,
    _builtin_bindings: Tuple[Tuple[str, Any], ...] = _BUILTIN_BINDINGS,
    _namespace: Dict[str, Any] = globals(),
    _error: Any = StaticCensusReconstructionError,
    _type: Any = type,
    _json_loads: Any = json.loads,
    _json_dumps: Any = json.dumps,
    _sha256: Any = hashlib.sha256,
    _deepcopy: Any = copy.deepcopy,
    _combinations: Any = combinations,
    _comb: Any = comb,
) -> None:
    for name, expected in _builtin_bindings:
        if name in _namespace and _namespace[name] is not expected:
            raise _error("reconstruction builtin binding changed")
    for name, expected in _function_bindings:
        if _namespace.get(name) is not expected:
            raise _error("reconstruction function binding changed")
    for name, expected in _constant_bindings:
        observed = _namespace.get(name)
        if _type(observed) is not _type(expected) or observed != expected:
            raise _error("reconstruction constant binding changed")
    if (
        json.loads is not _json_loads
        or json.dumps is not _json_dumps
        or hashlib.sha256 is not _sha256
        or copy.deepcopy is not _deepcopy
        or combinations is not _combinations
        or comb is not _comb
    ):
        raise _error("reconstruction standard-library binding changed")


def _make_public_reconstructor(
    implementation: Any, guard: Any
) -> Any:
    def reconstruct_static_census_report_artifact_v1(
        raw: bytes,
    ) -> Dict[str, Any]:
        """Reconstruct one exact stored report without revisiting carrier leaves."""

        guard()
        return implementation(raw)

    return reconstruct_static_census_report_artifact_v1


reconstruct_static_census_report_artifact_v1 = _make_public_reconstructor(
    _reconstruct_artifact_v1, _assert_reconstruction_bindings
)
del _make_public_reconstructor


__all__ = (
    "STATIC_CENSUS_REPORT_MAX_BYTES_V1",
    "STATIC_CENSUS_REPORT_MAX_JSON_NODES_V1",
    "STATIC_CENSUS_REPORT_MAX_JSON_DEPTH_V1",
    "StaticCensusReconstructionError",
    "reconstruct_static_census_report_artifact_v1",
)
