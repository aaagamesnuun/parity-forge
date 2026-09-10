import ast
import copy
import hashlib
import json
import subprocess
import sys
import textwrap
import unittest
from collections import Counter
from itertools import combinations
from pathlib import Path
from unittest import mock

import parity_forge_universe.initial_structure as initial
import parity_forge_universe.schema_v4_compiler as compiler
import parity_forge_universe.static_census as census
import parity_forge_universe.typed_occupancy as universe


_BOARD = tuple((row, column) for row in range(3) for column in range(3))
_D4 = ("I", "R90", "R180", "R270", "FLR", "FTB", "FD", "FA")
_SUBGROUPS = (
    ("I",),
    ("I", "FLR"),
    ("I", "FTB"),
    ("I", "R180", "FLR", "FTB"),
    _D4,
)
_EXPECTED_FIXED_SETUPS = {
    "I": 6798,
    "R90": 2,
    "R180": 62,
    "R270": 2,
    "FLR": 224,
    "FTB": 224,
    "FD": 224,
    "FA": 224,
}
_EXPECTED_ORBIT_HISTOGRAMS = {
    ("I",): {1: 6798},
    ("I", "FLR"): {1: 224, 2: 3287},
    ("I", "FTB"): {1: 224, 2: 3287},
    ("I", "R180", "FLR", "FTB"): {1: 20, 2: 225, 4: 1582},
    _D4: {1: 2, 2: 18, 4: 210, 8: 740},
}
_EXPECTED_SKELETON_HISTOGRAM = {
    ("I",): 141,
    ("I", "FLR"): 810,
    ("I", "FTB"): 165,
    ("I", "R180", "FLR", "FTB"): 396,
    _D4: 6,
}
_REPRESENTATIVE_SKELETONS = {
    ("I", "R180", "FLR", "FTB"): (
        0,
        "bcc7300ad679111412340d96ec451657da4e4b94e934d0831522fd9b84c87835",
    ),
    ("I", "FLR"): (
        7,
        "c06aa6b99e26f302ae3dcab456c9ce0a1595867b2df0dcd55a0443c9b1553a7a",
    ),
    ("I", "FTB"): (
        10,
        "8b35d4f9d135e909b12bdc825d0d45f0e6fe1fe4573c179127cd4583021b1904",
    ),
    _D4: (
        216,
        "27d3360b34f4901de80c0b142bd961979749c0239091eacc92275158b73d2821",
    ),
    ("I",): (
        326,
        "eee8d14d9937b2e37bd332e79efcb272d03cbc99ed37aa802ff01886f406c9b3",
    ),
}
_REASON_ATOMS = (
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
_ROLE_SWAP_BIT = (1, 0, 3, 2, 5, 4, 7, 6, 11, 10, 9, 8)
_SETUP_DOMAIN = b"parity-forge:plan0015:typed-setup:v1\0"
_RESULT_DOMAIN = b"parity-forge:plan0015:initial-structure-result:v1\0"
_RESULT_EVIDENCE_DOMAIN = (
    b"parity-forge:plan0015:initial-structure-result-evidence:v1\0"
)
_PROFILED_SKELETON_HASH_DOMAIN = (
    b"parity-forge:typed-occupancy:skeleton:v1\0"
)
_ROLE_NEUTRAL_SKELETON_HASH_DOMAIN = (
    b"parity-forge:typed-occupancy:role-neutral-skeleton:v1\0"
)
_SETUP_DESCRIPTOR_DOMAIN = (
    b"parity-forge:plan0015:setup-orbit-table-descriptor:v1\0"
)
_ORDERED_SETUP_ROOT_DOMAIN = (
    b"parity-forge:plan0015:ordered-typed-setups:v1\0"
)
_SETUP_IMAGE_ROOT_DOMAIN = (
    b"parity-forge:plan0015:setup-d4-image-ordinals:v1\0"
)
_SETUP_GROUP_MAPPING_ROOT_DOMAIN = (
    b"parity-forge:plan0015:setup-group-mapping:v1\0"
)
_SETUP_GROUP_REPRESENTATIVE_ROOT_DOMAIN = (
    b"parity-forge:plan0015:setup-group-representatives:v1\0"
)
_STATIC_LEAF_DOMAIN = b"parity-forge:plan0015:static-census-leaf:v1\0"
_STATIC_SHARD_ROOT_DOMAIN = b"parity-forge:plan0015:static-census-shard:v1\0"
_STATIC_SHARD_SUMMARY_DOMAIN = (
    b"parity-forge:plan0015:static-census-shard-summary:v1\0"
)
_STATIC_GROUP_ROOT_DOMAIN = (
    b"parity-forge:plan0015:static-census-descriptor-group:v1\0"
)
_STATIC_REPORT_BODY_DOMAIN = (
    b"parity-forge:plan0015:static-census-report-body:v1\0"
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

_SETUP_ROWS = None
_SETUP_JSON = None
_SETUP_INDEX = None
_ORBIT_PARTITIONS = {}
_FRESH_SKELETONS = None
_SKELETON_STABILIZERS = None
_PRODUCTION_SETUP_TABLE = None
_PRODUCTION_PREPARED_TABLE = None
_PRODUCTION_SHARDS = {}
_SHARD_ORACLES = {}
_SETUP_DESCRIPTOR = None
_SYNTHETIC_SUMMARY_JSONS = None
_SYNTHETIC_COMPLETE_CHECKPOINT = None
_SYNTHETIC_COMPLETE_REPORT = None
_SYNTHETIC_SUPPLY_BY_SUBGROUP = {}


def _canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _domain_hash(domain, canonical):
    return hashlib.sha256(domain + canonical.encode("utf-8")).hexdigest()


def _sequence_root(domain, canonical_values):
    values = tuple(canonical_values)
    digest = hashlib.sha256(domain)
    for ordinal, canonical in enumerate(values):
        encoded = canonical.encode("utf-8")
        digest.update(ordinal.to_bytes(8, "big"))
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def _independent_setup_rows():
    global _SETUP_ROWS, _SETUP_JSON, _SETUP_INDEX
    if _SETUP_ROWS is None:
        rows = []
        for a_count in range(4):
            for b_count in range(4):
                if (a_count, b_count) == (0, 0):
                    continue
                for positions_a in combinations(_BOARD, a_count):
                    remaining = tuple(
                        cell for cell in _BOARD if cell not in positions_a
                    )
                    for positions_b in combinations(remaining, b_count):
                        rows.append((positions_a, positions_b))
        _SETUP_ROWS = tuple(rows)
        _SETUP_JSON = tuple(_setup_json_uncached(row) for row in _SETUP_ROWS)
        _SETUP_INDEX = {row: ordinal for ordinal, row in enumerate(_SETUP_ROWS)}
    return _SETUP_ROWS


def _setup_payload(row):
    positions_a, positions_b = row
    return {
        "setup_version": 1,
        "positions": {
            "A": [list(position) for position in positions_a],
            "B": [list(position) for position in positions_b],
        },
    }


def _setup_json_uncached(row):
    return _canonical(_setup_payload(row))


def _setup_json(ordinal):
    _independent_setup_rows()
    return _SETUP_JSON[ordinal]


def _transform_position(position, transform):
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
    raise AssertionError("unknown independent transform: {}".format(transform))


def _transform_setup(row, transform):
    return tuple(
        tuple(sorted(_transform_position(position, transform) for position in owner))
        for owner in row
    )


def _setup_image_ordinal(ordinal, transform):
    rows = _independent_setup_rows()
    return _SETUP_INDEX[_transform_setup(rows[ordinal], transform)]


def _permutation_cycle_lengths(transform):
    permutation = {
        cell: _transform_position(cell, transform)
        for cell in _BOARD
    }
    remaining = set(_BOARD)
    lengths = []
    while remaining:
        start = min(remaining)
        cursor = start
        length = 0
        while True:
            remaining.remove(cursor)
            length += 1
            cursor = permutation[cursor]
            if cursor == start:
                break
        lengths.append(length)
    return tuple(sorted(lengths))


def _fixed_setup_polynomial_count(transform):
    coefficients = {(0, 0): 1}
    for cycle_length in _permutation_cycle_lengths(transform):
        next_coefficients = {}
        for (a_count, b_count), multiplicity in coefficients.items():
            for target in (
                (a_count, b_count),
                (a_count + cycle_length, b_count),
                (a_count, b_count + cycle_length),
            ):
                if target[0] <= 3 and target[1] <= 3:
                    next_coefficients[target] = (
                        next_coefficients.get(target, 0) + multiplicity
                    )
        coefficients = next_coefficients
    return sum(
        multiplicity
        for counts, multiplicity in coefficients.items()
        if counts != (0, 0)
    )


def _independent_orbit_partition(subgroup):
    subgroup = tuple(subgroup)
    if subgroup not in _ORBIT_PARTITIONS:
        rows = _independent_setup_rows()
        representative_by_row = []
        image_ordinals_by_row = []
        for ordinal in range(len(rows)):
            images = tuple(
                sorted({_setup_image_ordinal(ordinal, transform) for transform in subgroup})
            )
            representative = min(images, key=lambda item: _setup_json(item).encode("utf-8"))
            representative_by_row.append(representative)
            image_ordinals_by_row.append(images)
        representatives = tuple(
            ordinal
            for ordinal, representative in enumerate(representative_by_row)
            if ordinal == representative
        )
        weights = {
            representative: len(image_ordinals_by_row[representative])
            for representative in representatives
        }
        _ORBIT_PARTITIONS[subgroup] = {
            "representative_by_row": tuple(representative_by_row),
            "images_by_row": tuple(image_ordinals_by_row),
            "representatives": representatives,
            "weights": weights,
            "histogram": dict(sorted(Counter(weights.values()).items())),
        }
    return _ORBIT_PARTITIONS[subgroup]


def _independent_setup_descriptor():
    global _SETUP_DESCRIPTOR
    if _SETUP_DESCRIPTOR is None:
        rows = _independent_setup_rows()
        images = tuple(
            tuple(_setup_image_ordinal(ordinal, transform) for transform in _D4)
            for ordinal in range(len(rows))
        )
        image_values = tuple(
            _canonical(
                {
                    "ordinal": ordinal,
                    "setup_hash": _domain_hash(_SETUP_DOMAIN, _setup_json(ordinal)),
                    "image_ordinals": list(images[ordinal]),
                }
            )
            for ordinal in range(len(rows))
        )
        mapping_values = []
        groups = []
        for group_index, subgroup in enumerate(_SUBGROUPS):
            partition = _independent_orbit_partition(subgroup)
            for ordinal, representative in enumerate(
                partition["representative_by_row"]
            ):
                mapping_values.append(
                    _canonical(
                        {
                            "group_index": group_index,
                            "raw_ordinal": ordinal,
                            "representative_ordinal": representative,
                        }
                    )
                )
            representative_values = tuple(
                _canonical(
                    {
                        "representative_ordinal": representative,
                        "representative_setup_hash": _domain_hash(
                            _SETUP_DOMAIN, _setup_json(representative)
                        ),
                        "orbit_weight": partition["weights"][representative],
                    }
                )
                for representative in partition["representatives"]
            )
            groups.append(
                {
                    "signature": list(subgroup),
                    "setup_orbit_count": len(partition["representatives"]),
                    "weighted_setup_count": sum(partition["weights"].values()),
                    "weight_histogram": {
                        str(weight): count
                        for weight, count in partition["histogram"].items()
                    },
                    "ordered_representative_root": _sequence_root(
                        _SETUP_GROUP_REPRESENTATIVE_ROOT_DOMAIN
                        + group_index.to_bytes(1, "big"),
                        representative_values,
                    ),
                }
            )
        count_pairs = tuple(
            (a_count, b_count)
            for a_count in range(4)
            for b_count in range(4)
            if (a_count, b_count) != (0, 0)
        )
        body = {
            "setup_orbit_table_version": 1,
            "board": {
                "rows": 3,
                "columns": 3,
                "cell_order": [list(position) for position in _BOARD],
            },
            "count_pair_order": [list(pair) for pair in count_pairs],
            "count_pair_supplies": [
                _comb(9, pair[0]) * _comb(9 - pair[0], pair[1])
                for pair in count_pairs
            ],
            "setup_count": len(rows),
            "d4_order": list(_D4),
            "fixed_setup_counts": dict(_EXPECTED_FIXED_SETUPS),
            "groups": groups,
            "roots": {
                "ordered_setup_root": _sequence_root(
                    _ORDERED_SETUP_ROOT_DOMAIN, _SETUP_JSON
                ),
                "ordered_d4_image_ordinal_root": _sequence_root(
                    _SETUP_IMAGE_ROOT_DOMAIN, image_values
                ),
                "ordered_group_mapping_root": _sequence_root(
                    _SETUP_GROUP_MAPPING_ROOT_DOMAIN, mapping_values
                ),
            },
        }
        _SETUP_DESCRIPTOR = dict(body)
        _SETUP_DESCRIPTOR["descriptor_root"] = _domain_hash(
            _SETUP_DESCRIPTOR_DOMAIN, _canonical(body)
        )
    return copy.deepcopy(_SETUP_DESCRIPTOR)


_EDGE_INDEX = {"TOP": 0, "RIGHT": 1, "BOTTOM": 2, "LEFT": 3}
_EDGE_BY_INDEX = ("TOP", "RIGHT", "BOTTOM", "LEFT")


def _transform_edge(edge, transform):
    index = _EDGE_INDEX[edge]
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
        raise AssertionError("unknown independent transform: {}".format(transform))
    return _EDGE_BY_INDEX[target]


def _transform_skeleton_payload(payload, transform):
    transformed = copy.deepcopy(payload)
    for owner in ("A", "B"):
        role = transformed["roles"][owner]
        edges = tuple(_transform_edge(edge, transform) for edge in role["target_edges"])
        if role["goal_primitive"] == "CONNECT_EDGES":
            edge_set = frozenset(edges)
            if edge_set == frozenset(("TOP", "BOTTOM")):
                edges = ("TOP", "BOTTOM")
            elif edge_set == frozenset(("RIGHT", "LEFT")):
                edges = ("RIGHT", "LEFT")
            else:
                raise AssertionError("independent CONNECT transform lost its axis")
        role["target_edges"] = list(edges)
    return transformed


def _fresh_skeletons():
    global _FRESH_SKELETONS
    if _FRESH_SKELETONS is None:
        _FRESH_SKELETONS = universe.enumerate_fresh_canonical_profiled_skeletons()
    return _FRESH_SKELETONS


def _independent_skeleton_stabilizers():
    global _SKELETON_STABILIZERS
    if _SKELETON_STABILIZERS is None:
        values = []
        for skeleton in _fresh_skeletons():
            canonical = universe.canonical_profiled_skeleton_json(skeleton)
            payload = json.loads(canonical)
            stabilizer = tuple(
                transform
                for transform in _D4
                if _canonical(_transform_skeleton_payload(payload, transform))
                == canonical
            )
            values.append(stabilizer)
        _SKELETON_STABILIZERS = tuple(values)
    return _SKELETON_STABILIZERS


def _independent_skeleton_stabilizer(skeleton):
    canonical = universe.canonical_profiled_skeleton_json(skeleton)
    payload = json.loads(canonical)
    return tuple(
        transform
        for transform in _D4
        if _canonical(_transform_skeleton_payload(payload, transform)) == canonical
    )


def _ordered_burnside_carrier_count(skeletons):
    carrier_count = 0
    for skeleton in skeletons:
        stabilizer = _independent_skeleton_stabilizer(skeleton)
        fixed_setup_sum = sum(
            _EXPECTED_FIXED_SETUPS[transform]
            for transform in stabilizer
        )
        if fixed_setup_sum % len(stabilizer):
            raise AssertionError("skeleton setup Burnside sum is not integral")
        carrier_count += fixed_setup_sum // len(stabilizer)
    return carrier_count


def _independent_reason_mask(reasons):
    if type(reasons) is not list:
        raise TypeError("reasons must be an exact list")
    observed = []
    for reason in reasons:
        if type(reason) is not dict or set(reason) != {
            "code",
            "role",
            "first_player",
        }:
            raise ValueError("reason is not an exact structured atom")
        atom = (reason["code"], reason["role"], reason["first_player"])
        if atom not in _REASON_ATOMS:
            raise ValueError("reason escaped the closed 12-atom vocabulary")
        observed.append(atom)
    indexes = tuple(_REASON_ATOMS.index(atom) for atom in observed)
    if indexes != tuple(sorted(set(indexes))):
        raise ValueError("reasons are duplicated or out of canonical order")
    return sum(1 << index for index in indexes)


def _reason_payload(mask):
    if type(mask) is not int or not 0 <= mask < (1 << len(_REASON_ATOMS)):
        raise ValueError("reason mask is outside the closed domain")
    return [
        {"code": code, "role": role, "first_player": first_player}
        for index, (code, role, first_player) in enumerate(_REASON_ATOMS)
        if mask & (1 << index)
    ]


def _role_swap_reason_mask(mask):
    result = 0
    for source_bit, target_bit in enumerate(_ROLE_SWAP_BIT):
        if mask & (1 << source_bit):
            result |= 1 << target_bit
    return result


def _typed_setup(row):
    return compiler.TypedSetupV1(1, tuple(row[0]), tuple(row[1]))


def _typed_carrier(skeleton, row):
    return compiler.TypedSetupCarrierV1(1, skeleton, _typed_setup(row))


def _snapshot(prepared, skeleton, row):
    canonical, digest = initial.derive_prepared_initial_structure_snapshot_v1(
        prepared, _typed_carrier(skeleton, row)
    )
    if digest != _domain_hash(_RESULT_DOMAIN, canonical):
        raise AssertionError("initial-structure snapshot hash disagrees")
    payload = json.loads(canonical)
    if _canonical(payload) != canonical:
        raise AssertionError("initial-structure snapshot is not canonical")
    return payload, digest


def _empty_shard_aggregate(
    skeleton_ordinal,
    skeleton_hash,
    subgroup,
    setup_table_root,
    include_roots=True,
    retain_leaf_values=False,
):
    ordinal_bytes = skeleton_ordinal.to_bytes(8, "big")
    aggregate = {
        "representative_count": 0,
        "weighted_setup_count": 0,
        "weight_histogram": Counter(),
        "representative_reason_counts": Counter(),
        "weighted_reason_counts": Counter(),
        "representative_contact_counts": Counter(),
        "weighted_contact_counts": Counter(),
        "eligible_representative_contact_counts": Counter(),
        "eligible_weighted_contact_counts": Counter(),
        "eligible_supply_representative": Counter(),
        "eligible_supply_weighted": Counter(),
        "work_extrema": {
            first_player: {
                name: [None, None]
                for name in (
                    "state_weight_sum",
                    "action_candidate_iterations",
                    "scan_candidate_iterations",
                )
            }
            for first_player in ("A", "B")
        },
    }
    if include_roots:
        aggregate["result_digest"] = hashlib.sha256(
            _STATIC_LEAF_DOMAIN + ordinal_bytes
        )
        aggregate["role_digest"] = hashlib.sha256(
            _STATIC_SHARD_ROOT_DOMAIN + b"role-facts\0" + ordinal_bytes
        )
        aggregate["count_digest"] = hashlib.sha256(
            _STATIC_SHARD_ROOT_DOMAIN + b"count-lattice\0" + ordinal_bytes
        )
        aggregate["leaf_digest"] = hashlib.sha256(
            _STATIC_SHARD_ROOT_DOMAIN + b"leaf-commitments\0" + ordinal_bytes
        )
        aggregate["leaf_context"] = {
            "skeleton_ordinal": skeleton_ordinal,
            "typed_skeleton_hash": skeleton_hash,
            "setup_orbit_table_root": setup_table_root,
            "exact_stabilizer": list(subgroup),
        }
        if retain_leaf_values:
            aggregate["leaf_values"] = []
        aggregate["group_digests"] = {
            name: hashlib.sha256(
                _STATIC_GROUP_ROOT_DOMAIN
                + name.encode("ascii")
                + b"\0"
                + ordinal_bytes
            )
            for name in _DESCRIPTOR_GROUPS
        }
    return aggregate


def _observe_snapshot(aggregate, payload, result_hash, setup_ordinal, weight):
    representative_index = aggregate["representative_count"]
    if "result_digest" in aggregate:
        result_bytes = _canonical(payload).encode("utf-8")
        aggregate["result_digest"].update(representative_index.to_bytes(8, "big"))
        aggregate["result_digest"].update(len(result_bytes).to_bytes(8, "big"))
        aggregate["result_digest"].update(result_bytes)
    mask = _independent_reason_mask(payload["rejection_reasons"])
    if payload["eligible"] is not (mask == 0):
        raise AssertionError("eligibility is not exactly empty reasons")
    if "leaf_digest" in aggregate:
        leaf = dict(aggregate["leaf_context"])
        leaf.update(
            {
                "representative_index": representative_index,
                "setup_ordinal": setup_ordinal,
                "typed_setup_canonical_json": _setup_json(setup_ordinal),
                "typed_setup_hash": payload["identities"]["typed_setup_hash"],
                "orbit_weight": weight,
                "typed_carrier_hash": payload["identities"]["typed_carrier_hash"],
                "initial_structure_result_hash": result_hash,
                "initial_structure_evidence_digest": payload["evidence_digest"],
                "reason_mask": mask,
                "eligible": payload["eligible"],
                "contact_class": payload["descriptor_groups"]["contact"][
                    "contact_class"
                ],
                "initial_counts": payload["count_lattice"]["initial_counts"],
                "tempo_references": payload["count_lattice"][
                    "tempo_references"
                ],
            }
        )
        leaf_canonical = _canonical(leaf)
        leaf_bytes = leaf_canonical.encode("utf-8")
        aggregate["leaf_digest"].update(representative_index.to_bytes(8, "big"))
        aggregate["leaf_digest"].update(len(leaf_bytes).to_bytes(8, "big"))
        aggregate["leaf_digest"].update(leaf_bytes)
        if "leaf_values" in aggregate:
            aggregate["leaf_values"].append(leaf_canonical)
    aggregate["representative_count"] += 1
    aggregate["weighted_setup_count"] += weight
    aggregate["weight_histogram"][weight] += 1
    aggregate["representative_reason_counts"][mask] += 1
    aggregate["weighted_reason_counts"][mask] += weight
    contact = payload["descriptor_groups"]["contact"]["contact_class"]
    aggregate["representative_contact_counts"][contact] += 1
    aggregate["weighted_contact_counts"][contact] += weight
    if mask == 0:
        aggregate["eligible_representative_contact_counts"][contact] += 1
        aggregate["eligible_weighted_contact_counts"][contact] += weight
        counts = payload["count_lattice"]["initial_counts"]
        key = (counts["A"], counts["B"], contact)
        aggregate["eligible_supply_representative"][key] += 1
        aggregate["eligible_supply_weighted"][key] += weight
    for reference in payload["count_lattice"]["tempo_references"]:
        first_player = reference["first_player"]
        values = {
            "state_weight_sum": reference["state_weight_sum"],
            "action_candidate_iterations": reference["work"][
                "action_candidate_iterations"
            ],
            "scan_candidate_iterations": reference["work"][
                "scan_candidate_iterations"
            ],
        }
        for name, value in values.items():
            bounds = aggregate["work_extrema"][first_player][name]
            bounds[0] = value if bounds[0] is None else min(bounds[0], value)
            bounds[1] = value if bounds[1] is None else max(bounds[1], value)

    if "result_digest" in aggregate:
        for digest, value in (
            (aggregate["role_digest"], payload["role_facts"]),
            (aggregate["count_digest"], payload["count_lattice"]),
        ):
            encoded = _canonical({"orbit_weight": weight, "value": value}).encode(
                "utf-8"
            )
            digest.update(representative_index.to_bytes(8, "big"))
            digest.update(len(encoded).to_bytes(8, "big"))
            digest.update(encoded)
        for name in _DESCRIPTOR_GROUPS:
            encoded = _canonical(
                {
                    "orbit_weight": weight,
                    "value": payload["descriptor_groups"][name],
                }
            ).encode("utf-8")
            digest = aggregate["group_digests"][name]
            digest.update(representative_index.to_bytes(8, "big"))
            digest.update(len(encoded).to_bytes(8, "big"))
            digest.update(encoded)


def _freeze_aggregate(aggregate):
    result = {
        "representative_count": aggregate["representative_count"],
        "weighted_setup_count": aggregate["weighted_setup_count"],
        "weight_histogram": dict(sorted(aggregate["weight_histogram"].items())),
        "representative_reason_counts": dict(
            sorted(aggregate["representative_reason_counts"].items())
        ),
        "weighted_reason_counts": dict(
            sorted(aggregate["weighted_reason_counts"].items())
        ),
        "representative_contact_counts": dict(
            sorted(aggregate["representative_contact_counts"].items())
        ),
        "weighted_contact_counts": dict(
            sorted(aggregate["weighted_contact_counts"].items())
        ),
        "eligible_representative_contact_counts": dict(
            sorted(aggregate["eligible_representative_contact_counts"].items())
        ),
        "eligible_weighted_contact_counts": dict(
            sorted(aggregate["eligible_weighted_contact_counts"].items())
        ),
        "eligible_supply_representative": dict(
            sorted(aggregate["eligible_supply_representative"].items())
        ),
        "eligible_supply_weighted": dict(
            sorted(aggregate["eligible_supply_weighted"].items())
        ),
        "work_extrema": copy.deepcopy(aggregate["work_extrema"]),
    }
    if "result_digest" in aggregate:
        result["roots"] = {
            "ordered_leaf_commitment_root": aggregate["leaf_digest"].hexdigest(),
            "ordered_initial_structure_result_root": aggregate[
                "result_digest"
            ].hexdigest(),
            "ordered_role_facts_root": aggregate["role_digest"].hexdigest(),
            "ordered_count_lattice_root": aggregate["count_digest"].hexdigest(),
            "ordered_descriptor_group_roots": {
                name: aggregate["group_digests"][name].hexdigest()
                for name in _DESCRIPTOR_GROUPS
            },
        }
        if "leaf_values" in aggregate:
            result["leaf_values"] = tuple(aggregate["leaf_values"])
    return result


def _independent_shard_aggregate(skeleton_ordinal, raw=False):
    key = (skeleton_ordinal, raw)
    if key not in _SHARD_ORACLES:
        skeleton = _fresh_skeletons()[skeleton_ordinal]
        subgroup = _independent_skeleton_stabilizers()[skeleton_ordinal]
        rows = _independent_setup_rows()
        prepared = initial.prepare_initial_structure_skeleton_v1(
            _typed_carrier(skeleton, rows[0])
        )
        aggregate = _empty_shard_aggregate(
            skeleton_ordinal,
            universe.profiled_skeleton_hash(skeleton),
            subgroup,
            _independent_setup_descriptor()["descriptor_root"],
            include_roots=not raw,
            retain_leaf_values=(skeleton_ordinal == 216 and not raw),
        )
        if raw:
            work = ((ordinal, 1) for ordinal in range(len(rows)))
        else:
            partition = _independent_orbit_partition(subgroup)
            work = (
                (ordinal, partition["weights"][ordinal])
                for ordinal in partition["representatives"]
            )
        for ordinal, weight in work:
            payload, result_hash = _snapshot(prepared, skeleton, rows[ordinal])
            _observe_snapshot(
                aggregate, payload, result_hash, ordinal, weight
            )
        _SHARD_ORACLES[key] = _freeze_aggregate(aggregate)
    return _SHARD_ORACLES[key]


def _production_setup_table():
    global _PRODUCTION_SETUP_TABLE
    if _PRODUCTION_SETUP_TABLE is None:
        _PRODUCTION_SETUP_TABLE = census.build_setup_orbit_table_v1()
    return _PRODUCTION_SETUP_TABLE


def _production_prepared_table():
    global _PRODUCTION_PREPARED_TABLE
    if _PRODUCTION_PREPARED_TABLE is None:
        _PRODUCTION_PREPARED_TABLE = census.prepare_static_census_table_v1(
            _production_setup_table()
        )
    return _PRODUCTION_PREPARED_TABLE


def _production_shard(ordinal):
    if ordinal not in _PRODUCTION_SHARDS:
        _PRODUCTION_SHARDS[ordinal] = census.derive_static_census_shard_v1(
            _production_prepared_table(), ordinal
        )
    return _PRODUCTION_SHARDS[ordinal]


def _exact_field_clone(value):
    cloned = object.__new__(type(value))
    for name, field_value in vars(value).items():
        object.__setattr__(cloned, name, field_value)
    return cloned


def _synthetic_root(ordinal, label):
    digest = hashlib.sha256(
        b"parity-forge:test:static-census-synthetic-root:v1\0"
    )
    digest.update(ordinal.to_bytes(8, "big"))
    digest.update(label.encode("ascii"))
    return digest.hexdigest()


def _synthetic_supply_by_count_pair(prepared, subgroup):
    subgroup = tuple(subgroup)
    if subgroup not in _SYNTHETIC_SUPPLY_BY_SUBGROUP:
        group_index = _SUBGROUPS.index(subgroup)
        representatives = prepared._setup_table._partitions[group_index][2]
        representative_counts = [0] * 15
        weighted_counts = [0] * 15
        for setup_ordinal, weight in representatives:
            count_index = prepared._setup_table._rows[setup_ordinal][1]
            representative_counts[count_index] += 1
            weighted_counts[count_index] += weight
        if sum(representative_counts) != len(representatives):
            raise AssertionError("synthetic representative supply is incomplete")
        if sum(weighted_counts) != 6798:
            raise AssertionError("synthetic weighted supply is incomplete")
        _SYNTHETIC_SUPPLY_BY_SUBGROUP[subgroup] = (
            tuple(representative_counts),
            tuple(weighted_counts),
        )
    return _SYNTHETIC_SUPPLY_BY_SUBGROUP[subgroup]


def _synthetic_shard_summary(prepared, skeleton_ordinal):
    row = prepared._skeleton_rows[skeleton_ordinal]
    subgroup = tuple(row[5])
    representative_count = row[6]
    representative_supply, weighted_supply = _synthetic_supply_by_count_pair(
        prepared, subgroup
    )
    setup_root = prepared._setup_table._construction_snapshot
    supply_rows = []
    count_pairs = tuple(
        (a_count, b_count)
        for a_count in range(4)
        for b_count in range(4)
        if (a_count, b_count) != (0, 0)
    )
    for count_index, count_pair in enumerate(count_pairs):
        for contact_class in ("CONTACT", "SEPARATED"):
            separated = contact_class == "SEPARATED"
            supply_rows.append(
                {
                    "initial_counts": {
                        "A": count_pair[0],
                        "B": count_pair[1],
                    },
                    "contact_class": contact_class,
                    "representative_count": (
                        representative_supply[count_index] if separated else 0
                    ),
                    "weighted_count": (
                        weighted_supply[count_index] if separated else 0
                    ),
                }
            )
    roots = {
        "ordered_leaf_commitment_root": _synthetic_root(
            skeleton_ordinal, "leaf"
        ),
        "ordered_initial_structure_result_root": _synthetic_root(
            skeleton_ordinal, "result"
        ),
        "ordered_role_facts_root": _synthetic_root(skeleton_ordinal, "role"),
        "ordered_count_lattice_root": _synthetic_root(
            skeleton_ordinal, "count"
        ),
        "ordered_descriptor_group_roots": {
            name: _synthetic_root(skeleton_ordinal, "group-" + name)
            for name in _DESCRIPTOR_GROUPS
        },
    }
    body = {
        "static_census_shard_version": 1,
        "skeleton": {
            "ordinal": skeleton_ordinal,
            "canonical_profiled_skeleton_json": row[1],
            "typed_skeleton_hash": row[2],
            "role_neutral_skeleton_hash": row[3],
            "role_neutral_semantic_hash": row[4],
            "exact_stabilizer": list(subgroup),
        },
        "setup_orbit": {
            "setup_orbit_table_root": setup_root,
            "representative_count": representative_count,
            "weighted_setup_count": 6798,
            "paired_first_player_member_count": 13596,
            "weight_histogram": {
                str(weight): count for weight, count in row[7]
            },
        },
        "eligibility": {
            "representative_eligible_count": representative_count,
            "weighted_eligible_count": 6798,
            "paired_first_player_eligible_member_count": 13596,
            "reason_combinations": [
                {
                    "reason_mask": 0,
                    "reasons": [],
                    "representative_count": representative_count,
                    "weighted_count": 6798,
                }
            ],
        },
        "contact": {
            "CONTACT": {
                "representative_count": 0,
                "weighted_count": 0,
                "eligible_representative_count": 0,
                "eligible_weighted_count": 0,
            },
            "SEPARATED": {
                "representative_count": representative_count,
                "weighted_count": 6798,
                "eligible_representative_count": representative_count,
                "eligible_weighted_count": 6798,
            },
        },
        "eligible_supply_by_count_pair_and_contact": supply_rows,
        "work_extrema": {
            first_player: {
                field: {"minimum": 0, "maximum": 0}
                for field in (
                    "state_weight_sum",
                    "action_candidate_iterations",
                    "scan_candidate_iterations",
                )
            }
            for first_player in ("A", "B")
        },
        "roots": roots,
    }
    summary = dict(body)
    summary["shard_commitment"] = _domain_hash(
        _STATIC_SHARD_SUMMARY_DOMAIN, _canonical(body)
    )
    return summary


def _synthetic_complete_summary_jsons():
    global _SYNTHETIC_SUMMARY_JSONS
    if _SYNTHETIC_SUMMARY_JSONS is None:
        prepared = _production_prepared_table()
        _SYNTHETIC_SUMMARY_JSONS = tuple(
            _canonical(_synthetic_shard_summary(prepared, ordinal))
            for ordinal in range(1518)
        )
    return _SYNTHETIC_SUMMARY_JSONS


def _synthetic_complete_checkpoint():
    global _SYNTHETIC_COMPLETE_CHECKPOINT
    if _SYNTHETIC_COMPLETE_CHECKPOINT is None:
        prepared = _production_prepared_table()
        representative_counts = [0] * (1 << len(_REASON_ATOMS))
        weighted_counts = [0] * (1 << len(_REASON_ATOMS))
        representative_counts[0] = 5_111_055
        weighted_counts[0] = 10_319_364
        _SYNTHETIC_COMPLETE_CHECKPOINT = census._make_checkpoint(
            prepared,
            1518,
            _synthetic_complete_summary_jsons(),
            tuple(representative_counts),
            tuple(weighted_counts),
        )
    return _SYNTHETIC_COMPLETE_CHECKPOINT


def _synthetic_complete_report():
    global _SYNTHETIC_COMPLETE_REPORT
    if _SYNTHETIC_COMPLETE_REPORT is None:
        _SYNTHETIC_COMPLETE_REPORT = census.finalize_static_census_v1(
            _synthetic_complete_checkpoint()
        )
    return _SYNTHETIC_COMPLETE_REPORT


def _retokenize_shard(summary):
    body = copy.deepcopy(summary)
    body.pop("shard_commitment", None)
    payload = dict(body)
    payload["shard_commitment"] = _domain_hash(
        _STATIC_SHARD_SUMMARY_DOMAIN, _canonical(body)
    )
    token = object.__new__(census.StaticCensusShardV1)
    object.__setattr__(token, "shard_version", 1)
    object.__setattr__(token, "skeleton_ordinal", payload["skeleton"]["ordinal"])
    object.__setattr__(token, "_summary_json", _canonical(payload))
    object.__setattr__(token, "_construction_snapshot", payload["shard_commitment"])
    return token


def _retokenize_report(payload):
    body = copy.deepcopy(payload)
    body.pop("report_digest", None)
    result = dict(body)
    result["report_digest"] = _domain_hash(
        _STATIC_REPORT_BODY_DOMAIN, _canonical(body)
    )
    token = object.__new__(census.StaticCensusReportV1)
    object.__setattr__(token, "report_version", 1)
    object.__setattr__(token, "_canonical_payload_json", _canonical(result))
    object.__setattr__(token, "_construction_snapshot", result["report_digest"])
    return token


def _assert_summary_matches_oracle(test_case, skeleton_ordinal, summary, oracle):
    skeleton = _fresh_skeletons()[skeleton_ordinal]
    subgroup = _independent_skeleton_stabilizers()[skeleton_ordinal]
    expected_skeleton = {
        "ordinal": skeleton_ordinal,
        "canonical_profiled_skeleton_json": (
            universe.canonical_profiled_skeleton_json(skeleton)
        ),
        "typed_skeleton_hash": universe.profiled_skeleton_hash(skeleton),
        "role_neutral_skeleton_hash": (
            universe.role_neutral_profiled_skeleton_hash(skeleton)
        ),
        "role_neutral_semantic_hash": universe.role_neutral_semantic_hash(
            skeleton.semantic_signature
        ),
        "exact_stabilizer": list(subgroup),
    }
    test_case.assertEqual(summary["skeleton"], expected_skeleton)
    test_case.assertEqual(
        summary["setup_orbit"],
        {
            "setup_orbit_table_root": _independent_setup_descriptor()[
                "descriptor_root"
            ],
            "representative_count": oracle["representative_count"],
            "weighted_setup_count": oracle["weighted_setup_count"],
            "paired_first_player_member_count": 2
            * oracle["weighted_setup_count"],
            "weight_histogram": {
                str(weight): count
                for weight, count in oracle["weight_histogram"].items()
            },
        },
    )

    reason_combinations = [
        {
            "reason_mask": mask,
            "reasons": _reason_payload(mask),
            "representative_count": count,
            "weighted_count": oracle["weighted_reason_counts"][mask],
        }
        for mask, count in oracle["representative_reason_counts"].items()
    ]
    eligible_representatives = oracle["representative_reason_counts"].get(0, 0)
    eligible_weighted = oracle["weighted_reason_counts"].get(0, 0)
    test_case.assertEqual(
        summary["eligibility"],
        {
            "representative_eligible_count": eligible_representatives,
            "weighted_eligible_count": eligible_weighted,
            "paired_first_player_eligible_member_count": 2 * eligible_weighted,
            "reason_combinations": reason_combinations,
        },
    )

    expected_contact = {}
    for contact in ("CONTACT", "SEPARATED"):
        expected_contact[contact] = {
            "representative_count": oracle[
                "representative_contact_counts"
            ].get(contact, 0),
            "weighted_count": oracle["weighted_contact_counts"].get(contact, 0),
            "eligible_representative_count": oracle[
                "eligible_representative_contact_counts"
            ].get(contact, 0),
            "eligible_weighted_count": oracle[
                "eligible_weighted_contact_counts"
            ].get(contact, 0),
        }
    test_case.assertEqual(summary["contact"], expected_contact)

    count_pairs = tuple(
        (a_count, b_count)
        for a_count in range(4)
        for b_count in range(4)
        if (a_count, b_count) != (0, 0)
    )
    expected_supply = []
    for a_count, b_count in count_pairs:
        for contact in ("CONTACT", "SEPARATED"):
            key = (a_count, b_count, contact)
            expected_supply.append(
                {
                    "initial_counts": {"A": a_count, "B": b_count},
                    "contact_class": contact,
                    "representative_count": oracle[
                        "eligible_supply_representative"
                    ].get(key, 0),
                    "weighted_count": oracle["eligible_supply_weighted"].get(
                        key, 0
                    ),
                }
            )
    test_case.assertEqual(
        summary["eligible_supply_by_count_pair_and_contact"], expected_supply
    )

    expected_extrema = {
        first_player: {
            field: {"minimum": bounds[0], "maximum": bounds[1]}
            for field, bounds in oracle["work_extrema"][first_player].items()
        }
        for first_player in ("A", "B")
    }
    test_case.assertEqual(summary["work_extrema"], expected_extrema)
    test_case.assertEqual(summary["roots"], oracle["roots"])
    body = dict(summary)
    commitment = body.pop("shard_commitment")
    test_case.assertEqual(
        commitment,
        _domain_hash(_STATIC_SHARD_SUMMARY_DOMAIN, _canonical(body)),
    )


class IndependentSetupOrbitOracleTests(unittest.TestCase):
    def test_coordinate_maps_form_d4_and_each_registered_signature_is_a_subgroup(self):
        permutations = {
            transform: tuple(_transform_position(cell, transform) for cell in _BOARD)
            for transform in _D4
        }
        self.assertEqual(len(set(permutations.values())), 8)
        for left in _D4:
            for right in _D4:
                composed = tuple(
                    _transform_position(
                        _transform_position(cell, right), left
                    )
                    for cell in _BOARD
                )
                self.assertIn(composed, permutations.values())
        for subgroup in _SUBGROUPS:
            subgroup_permutations = {permutations[name] for name in subgroup}
            for left in subgroup:
                for right in subgroup:
                    composed = tuple(
                        _transform_position(
                            _transform_position(cell, right), left
                        )
                        for cell in _BOARD
                    )
                    self.assertIn(composed, subgroup_permutations)

    def test_setup_domain_order_supply_and_endpoints(self):
        rows = _independent_setup_rows()
        supplies = Counter((len(row[0]), len(row[1])) for row in rows)
        self.assertEqual(len(rows), 6798)
        self.assertEqual(
            supplies,
            Counter(
                {
                    (a_count, b_count): (
                        _comb(9, a_count) * _comb(9 - a_count, b_count)
                    )
                    for a_count in range(4)
                    for b_count in range(4)
                    if (a_count, b_count) != (0, 0)
                }
            ),
        )
        self.assertEqual(rows[0], ((), ((0, 0),)))
        self.assertEqual(
            rows[-1],
            (
                ((2, 0), (2, 1), (2, 2)),
                ((1, 0), (1, 1), (1, 2)),
            ),
        )
        self.assertEqual(len(set(rows)), 6798)
        self.assertEqual(len(set(_SETUP_JSON)), 6798)

    def test_fixed_points_match_cycle_polynomial_and_direct_enumeration(self):
        rows = _independent_setup_rows()
        direct = {
            transform: sum(
                _transform_setup(row, transform) == row for row in rows
            )
            for transform in _D4
        }
        polynomial = {
            transform: _fixed_setup_polynomial_count(transform)
            for transform in _D4
        }
        self.assertEqual(direct, _EXPECTED_FIXED_SETUPS)
        self.assertEqual(polynomial, _EXPECTED_FIXED_SETUPS)
        self.assertEqual(_permutation_cycle_lengths("I"), (1,) * 9)
        self.assertEqual(_permutation_cycle_lengths("R90"), (1, 4, 4))
        self.assertEqual(_permutation_cycle_lengths("R180"), (1, 2, 2, 2, 2))
        self.assertEqual(_permutation_cycle_lengths("FLR"), (1, 1, 1, 2, 2, 2))

    def test_all_five_partitions_cover_once_and_match_burnside(self):
        for subgroup in _SUBGROUPS:
            partition = _independent_orbit_partition(subgroup)
            expected_orbit_count = sum(
                _EXPECTED_FIXED_SETUPS[transform] for transform in subgroup
            ) // len(subgroup)
            with self.subTest(subgroup=subgroup):
                self.assertEqual(
                    partition["histogram"], _EXPECTED_ORBIT_HISTOGRAMS[subgroup]
                )
                self.assertEqual(
                    len(partition["representatives"]), expected_orbit_count
                )
                self.assertEqual(
                    sum(partition["weights"].values()), 6798
                )
                for ordinal, representative in enumerate(
                    partition["representative_by_row"]
                ):
                    images = partition["images_by_row"][ordinal]
                    self.assertIn(ordinal, images)
                    self.assertEqual(
                        representative,
                        min(
                            images,
                            key=lambda item: _setup_json(item).encode("utf-8"),
                        ),
                    )
                    self.assertEqual(
                        partition["representative_by_row"][representative],
                        representative,
                    )

    def test_representative_uses_bytes_not_hash_and_exact_reflection_tuple(self):
        rows = _independent_setup_rows()
        corner = _SETUP_INDEX[((), ((0, 0),))]
        images = _independent_orbit_partition(_D4)["images_by_row"][corner]
        byte_minimum = min(images, key=lambda item: _setup_json(item).encode("utf-8"))
        hash_minimum = min(
            images,
            key=lambda item: _domain_hash(_SETUP_DOMAIN, _setup_json(item)),
        )
        self.assertEqual(rows[byte_minimum], ((), ((0, 0),)))
        self.assertEqual(rows[hash_minimum], ((), ((2, 0),)))
        self.assertNotEqual(byte_minimum, hash_minimum)

        top_middle = _SETUP_INDEX[(((0, 1),), ())]
        flr = _independent_orbit_partition(("I", "FLR"))
        ftb = _independent_orbit_partition(("I", "FTB"))
        self.assertEqual(flr["weights"][flr["representative_by_row"][top_middle]], 1)
        self.assertEqual(ftb["weights"][ftb["representative_by_row"][top_middle]], 2)

        owner_swapped = _SETUP_INDEX[(((0, 0),), ())]
        for subgroup in _SUBGROUPS:
            partition = _independent_orbit_partition(subgroup)
            self.assertNotEqual(
                partition["representative_by_row"][corner],
                partition["representative_by_row"][owner_swapped],
            )


class ProductionSetupOrbitTableTests(unittest.TestCase):
    def test_public_descriptor_matches_the_independent_table_byte_for_byte(self):
        table = _production_setup_table()
        self.assertIs(type(table), census.SetupOrbitTableV1)
        observed = census.setup_orbit_table_descriptor_v1(table)
        expected = _independent_setup_descriptor()
        self.assertEqual(observed, expected)
        self.assertEqual(census.setup_orbit_table_hash_v1(table), expected["descriptor_root"])

        observed["setup_count"] = -1
        observed["groups"].clear()
        self.assertEqual(census.setup_orbit_table_descriptor_v1(table), expected)

    def test_table_rejects_mutation_and_instance_method_shadowing(self):
        for field, replacement in (
            ("table_version", True),
            ("_construction_snapshot", "0" * 64),
            ("_assert_unchanged", lambda: None),
        ):
            table = _exact_field_clone(_production_setup_table())
            object.__setattr__(table, field, replacement)
            with self.subTest(field=field):
                with self.assertRaises((TypeError, ValueError)):
                    census.setup_orbit_table_descriptor_v1(table)

    def test_nested_partition_records_reject_boolean_numeric_aliases(self):
        class TupleSubclass(tuple):
            pass

        source = _production_setup_table()
        for label, target, replacement in (
            ("representative_ordinal", "record", (False, 1)),
            ("orbit_weight", "record", (0, True)),
            ("record_type", "record", TupleSubclass((0, 1))),
            (
                "signature_type",
                "signature",
                TupleSubclass(source._partitions[0][0]),
            ),
        ):
            hostile = _exact_field_clone(source)
            partitions = list(hostile._partitions)
            partition = list(partitions[0])
            if target == "signature":
                partition[0] = replacement
            else:
                representatives = list(partition[2])
                representatives[0] = replacement
                partition[2] = tuple(representatives)
            partitions[0] = tuple(partition)
            object.__setattr__(hostile, "_partitions", tuple(partitions))
            for public in (
                census.setup_orbit_table_descriptor_v1,
                census.setup_orbit_table_hash_v1,
                census.prepare_static_census_table_v1,
            ):
                with self.subTest(field=label, public=public.__name__):
                    with self.assertRaises((TypeError, ValueError)):
                        public(hostile)

    def test_prepared_table_is_constructor_closed_and_rejects_mutation(self):
        with self.assertRaises(TypeError):
            census.PreparedStaticCensusTableV1()
        prepared = _production_prepared_table()
        self.assertIs(type(prepared), census.PreparedStaticCensusTableV1)
        self.assertIsNot(
            census.prepare_static_census_table_v1(prepared),
            prepared,
        )
        for field, replacement in (
            ("table_version", True),
            ("_construction_snapshot", "0" * 64),
            ("_assert_unchanged", lambda: None),
        ):
            hostile = _exact_field_clone(prepared)
            object.__setattr__(hostile, field, replacement)
            with self.subTest(field=field):
                with self.assertRaises((TypeError, ValueError)):
                    census.prepare_static_census_table_v1(hostile)

    def test_prepared_nested_skeleton_records_require_exact_tuples(self):
        class TupleSubclass(tuple):
            pass

        source = _production_prepared_table()
        for label in ("stabilizer", "weight_record"):
            hostile = _exact_field_clone(source)
            rows = list(hostile._skeleton_rows)
            row = list(rows[0])
            if label == "stabilizer":
                row[5] = TupleSubclass(row[5])
            else:
                histogram = list(row[7])
                histogram[0] = TupleSubclass(histogram[0])
                row[7] = tuple(histogram)
            rows[0] = tuple(row)
            object.__setattr__(hostile, "_skeleton_rows", tuple(rows))
            with self.subTest(field=label):
                with self.assertRaises((TypeError, ValueError)):
                    census.prepare_static_census_table_v1(hostile)

    def test_transitive_descriptor_helpers_cannot_hide_table_mutation(self):
        source = _production_setup_table()
        descriptor = census.setup_orbit_table_descriptor_v1(source)
        hostile = _exact_field_clone(source)
        rows = list(hostile._rows)
        changed = list(rows[0])
        changed[5] = "0" * 64
        rows[0] = tuple(changed)
        object.__setattr__(hostile, "_rows", tuple(rows))

        with mock.patch.object(
            census,
            "_setup_descriptor_from_material",
            return_value=copy.deepcopy(descriptor),
        ):
            for public in (
                census.setup_orbit_table_descriptor_v1,
                census.setup_orbit_table_hash_v1,
            ):
                with self.subTest(public=public.__name__):
                    with self.assertRaises((TypeError, ValueError)):
                        public(hostile)

    def test_transitive_skeleton_helper_cannot_hide_prepared_mutation(self):
        source = _production_prepared_table()
        descriptor = json.loads(source._skeleton_descriptor_json)
        hostile = _exact_field_clone(source)
        rows = list(hostile._skeleton_rows)
        changed = list(rows[0])
        changed[2] = "0" * 64
        rows[0] = tuple(changed)
        object.__setattr__(hostile, "_skeleton_rows", tuple(rows))

        with mock.patch.object(
            census,
            "_skeleton_authority_descriptor",
            return_value=copy.deepcopy(descriptor),
        ):
            with self.assertRaises((TypeError, ValueError)):
                census.prepare_static_census_table_v1(hostile)


class SkeletonAndGlobalAccountingOracleTests(unittest.TestCase):
    def test_all_1518_exact_stabilizers_and_fixed_witnesses(self):
        skeletons = _fresh_skeletons()
        stabilizers = _independent_skeleton_stabilizers()
        self.assertEqual(len(skeletons), 1518)
        self.assertEqual(Counter(stabilizers), Counter(_EXPECTED_SKELETON_HISTOGRAM))
        self.assertTrue(all(stabilizer in _SUBGROUPS for stabilizer in stabilizers))
        for subgroup, (ordinal, expected_hash) in _REPRESENTATIVE_SKELETONS.items():
            with self.subTest(subgroup=subgroup):
                self.assertEqual(stabilizers[ordinal], subgroup)
                self.assertEqual(
                    universe.profiled_skeleton_hash(skeletons[ordinal]),
                    expected_hash,
                )

    def test_global_orbit_and_weight_accounting(self):
        skeleton_counts = Counter(_independent_skeleton_stabilizers())
        weight_bins = Counter()
        representative_count = 0
        for subgroup, skeleton_count in skeleton_counts.items():
            histogram = _EXPECTED_ORBIT_HISTOGRAMS[subgroup]
            representative_count += skeleton_count * sum(histogram.values())
            for weight, count in histogram.items():
                weight_bins[weight] += skeleton_count * count
        self.assertEqual(
            dict(sorted(weight_bins.items())),
            {1: 1_184_850, 2: 3_294_033, 4: 627_732, 8: 4_440},
        )
        self.assertEqual(representative_count, 5_111_055)
        self.assertEqual(sum(weight * count for weight, count in weight_bins.items()), 10_319_364)
        self.assertEqual(
            2 * sum(weight * count for weight, count in weight_bins.items()),
            20_638_728,
        )
        self.assertEqual(
            11_085_600 - 215_508 - 647_982,
            2 * representative_count,
        )

    def test_ordered_population_burnside_independently_reconstructs_total(self):
        admitted = universe.enumerate_admitted_profiled_skeletons()
        self_isomorphic = universe.enumerate_self_isomorphic_profiled_skeletons()
        old_region = universe.enumerate_plan0013_profiled_region_closure()
        self.assertEqual((len(admitted), len(self_isomorphic), len(old_region)), (3300, 66, 198))
        values = (
            _ordered_burnside_carrier_count(admitted),
            _ordered_burnside_carrier_count(self_isomorphic),
            _ordered_burnside_carrier_count(old_region),
        )
        self.assertEqual(values, (11_085_600, 215_508, 647_982))
        self.assertEqual((values[0] - values[1] - values[2]) // 2, 5_111_055)


class IndependentReasonCodecTests(unittest.TestCase):
    def test_all_masks_roundtrip_and_complete_role_swap_is_an_involution(self):
        for mask in range(1 << len(_REASON_ATOMS)):
            reasons = _reason_payload(mask)
            self.assertEqual(_independent_reason_mask(reasons), mask)
            self.assertEqual(census._reason_payload(mask), reasons)
            self.assertEqual(census._reason_mask(copy.deepcopy(reasons)), mask)
            swapped = _role_swap_reason_mask(mask)
            self.assertEqual(_role_swap_reason_mask(swapped), mask)
            self.assertEqual(swapped == 0, mask == 0)

    def test_codec_rejects_duplicates_reordering_and_unknown_atoms(self):
        valid = _reason_payload((1 << 0) | (1 << 8))
        invalid = (
            list(reversed(valid)),
            valid + [copy.deepcopy(valid[0])],
            [{"code": "UNKNOWN", "role": "A", "first_player": None}],
            [{"code": "INITIAL_IMMOBILITY", "role": "A"}],
        )
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises((TypeError, ValueError)):
                    _independent_reason_mask(value)
                with self.assertRaises((TypeError, ValueError)):
                    census._reason_mask(copy.deepcopy(value))
        for mask in (True, -1, 1 << len(_REASON_ATOMS)):
            with self.subTest(mask=mask):
                with self.assertRaises((TypeError, ValueError)):
                    census._reason_payload(mask)


class TransformMaskCovarianceTests(unittest.TestCase):
    def test_reason_mask_and_contact_are_d4_invariant(self):
        skeleton = _fresh_skeletons()[_REPRESENTATIVE_SKELETONS[("I",)][0]]
        row = (((0, 0), (1, 2)), ((0, 2), (2, 1)))
        carrier = _typed_carrier(skeleton, row)
        source = initial.derive_initial_structure_result_v1(carrier).to_dict()
        source_mask = _independent_reason_mask(source["rejection_reasons"])
        for transform in universe.D4Transform:
            target_carrier = compiler.transform_typed_setup_carrier_v1(
                carrier, transform
            )
            target = initial.derive_initial_structure_result_v1(
                target_carrier
            ).to_dict()
            with self.subTest(transform=transform.value):
                self.assertEqual(
                    _independent_reason_mask(target["rejection_reasons"]),
                    source_mask,
                )
                self.assertEqual(
                    target["descriptor_groups"]["contact"],
                    source["descriptor_groups"]["contact"],
                )

    def test_complete_role_swap_uses_the_fixed_bit_permutation(self):
        rows = _independent_setup_rows()
        setup_ordinals = (0, _SETUP_INDEX[(((0, 1),), ())], len(rows) - 1)
        for subgroup, (skeleton_ordinal, _) in _REPRESENTATIVE_SKELETONS.items():
            skeleton = _fresh_skeletons()[skeleton_ordinal]
            for setup_ordinal in setup_ordinals:
                source_carrier = _typed_carrier(skeleton, rows[setup_ordinal])
                target_carrier = compiler.complete_role_swap_typed_setup_carrier_v1(
                    source_carrier
                )
                source = initial.derive_initial_structure_result_v1(
                    source_carrier
                ).to_dict()
                target = initial.derive_initial_structure_result_v1(
                    target_carrier
                ).to_dict()
                source_mask = _independent_reason_mask(source["rejection_reasons"])
                target_mask = _independent_reason_mask(target["rejection_reasons"])
                with self.subTest(subgroup=subgroup, setup=setup_ordinal):
                    self.assertEqual(target_mask, _role_swap_reason_mask(source_mask))
                    self.assertEqual(target["eligible"], source["eligible"])
                    self.assertEqual(
                        target["descriptor_groups"]["contact"]["contact_class"],
                        source["descriptor_groups"]["contact"]["contact_class"],
                    )


class ProductionSelectedShardDifferentialTests(unittest.TestCase):
    def test_initial_snapshot_rejects_boolean_numeric_aliases(self):
        prepared = _production_prepared_table()
        skeleton_row = prepared._skeleton_rows[0]
        setup_row = prepared._setup_table._rows[0]
        skeleton = universe.parse_profiled_skeleton(
            json.loads(skeleton_row[1])
        )
        setup = compiler.TypedSetupV1(1, setup_row[2], setup_row[3])
        carrier = compiler.TypedSetupCarrierV1(1, skeleton, setup)
        carrier_canonical = compiler.canonical_typed_setup_carrier_json_v1(
            carrier
        )
        carrier_hash = compiler.typed_setup_carrier_hash_v1(carrier)
        prepared_kernel = initial.prepare_initial_structure_skeleton_v1(carrier)
        canonical, result_hash = (
            initial.derive_prepared_initial_structure_snapshot_v1(
                prepared_kernel, carrier
            )
        )
        base = json.loads(canonical)
        initial_counts = (len(setup_row[2]), len(setup_row[3]))
        census._snapshot_payload(
            canonical,
            result_hash,
            carrier_canonical,
            carrier_hash,
            setup_row[5],
            skeleton_row[2],
            initial_counts,
        )

        mutations = {
            "carrier_version": lambda payload: payload["carrier"].__setitem__(
                "carrier_version", True
            ),
            "count_table_version": lambda payload: payload[
                "count_lattice"
            ].__setitem__("table_version", True),
            "initial_counts": lambda payload: payload["count_lattice"].__setitem__(
                "initial_counts", {"A": False, "B": True}
            ),
        }
        for label, mutate in mutations.items():
            payload = copy.deepcopy(base)
            mutate(payload)
            body = dict(payload)
            body.pop("evidence_digest")
            payload["evidence_digest"] = _domain_hash(
                _RESULT_EVIDENCE_DOMAIN, _canonical(body)
            )
            hostile_canonical = _canonical(payload)
            hostile_result_hash = _domain_hash(
                _RESULT_DOMAIN, hostile_canonical
            )
            with self.subTest(field=label):
                with self.assertRaises((TypeError, ValueError)):
                    census._snapshot_payload(
                        hostile_canonical,
                        hostile_result_hash,
                        carrier_canonical,
                        carrier_hash,
                        setup_row[5],
                        skeleton_row[2],
                        initial_counts,
                    )

    def test_selected_five_stabilizer_shards_match_independent_oracles(self):
        for subgroup, (skeleton_ordinal, _) in _REPRESENTATIVE_SKELETONS.items():
            with self.subTest(subgroup=subgroup, ordinal=skeleton_ordinal):
                shard = _production_shard(skeleton_ordinal)
                self.assertIs(type(shard), census.StaticCensusShardV1)
                summary = census.static_census_shard_summary_v1(shard)
                oracle = _independent_shard_aggregate(skeleton_ordinal)
                _assert_summary_matches_oracle(
                    self, skeleton_ordinal, summary, oracle
                )

                summary["eligibility"]["reason_combinations"].clear()
                summary["roots"].clear()
                fresh = census.static_census_shard_summary_v1(shard)
                self.assertTrue(fresh["eligibility"]["reason_combinations"])
                self.assertEqual(fresh["roots"], oracle["roots"])

    def test_z_d4_weighted_shard_matches_all_6798_raw_setups(self):
        skeleton_ordinal = _REPRESENTATIVE_SKELETONS[_D4][0]
        factored = _independent_shard_aggregate(skeleton_ordinal)
        raw = _independent_shard_aggregate(skeleton_ordinal, raw=True)
        summary = census.static_census_shard_summary_v1(
            _production_shard(skeleton_ordinal)
        )

        self.assertEqual(raw["representative_count"], 6798)
        self.assertEqual(factored["representative_count"], 970)
        self.assertEqual(factored["weighted_setup_count"], 6798)
        self.assertEqual(
            raw["representative_reason_counts"],
            factored["weighted_reason_counts"],
        )
        self.assertEqual(
            raw["representative_contact_counts"],
            factored["weighted_contact_counts"],
        )
        self.assertEqual(
            raw["eligible_representative_contact_counts"],
            factored["eligible_weighted_contact_counts"],
        )
        self.assertEqual(
            raw["eligible_supply_representative"],
            factored["eligible_supply_weighted"],
        )
        self.assertEqual(raw["work_extrema"], factored["work_extrema"])
        self.assertEqual(
            summary["eligibility"]["weighted_eligible_count"],
            raw["representative_reason_counts"].get(0, 0),
        )

        leaf_values = factored["leaf_values"]
        leaf_domain = (
            _STATIC_SHARD_ROOT_DOMAIN
            + b"leaf-commitments\0"
            + skeleton_ordinal.to_bytes(8, "big")
        )
        production_root = summary["roots"]["ordered_leaf_commitment_root"]
        self.assertEqual(len(leaf_values), 970)
        self.assertEqual(_sequence_root(leaf_domain, leaf_values), production_root)

        dropped = leaf_values[1:]
        reordered = (leaf_values[1], leaf_values[0]) + leaf_values[2:]
        changed_leaf = json.loads(leaf_values[0])
        changed_leaf["orbit_weight"] = (
            2 if changed_leaf["orbit_weight"] == 1 else 1
        )
        reweighted = (_canonical(changed_leaf),) + leaf_values[1:]
        altered_roots = {
            _sequence_root(leaf_domain, dropped),
            _sequence_root(leaf_domain, reordered),
            _sequence_root(leaf_domain, reweighted),
        }
        self.assertEqual(len(altered_roots), 3)
        self.assertNotIn(production_root, altered_roots)

    def test_shard_is_constructor_closed_and_rejects_hostile_mutation(self):
        with self.assertRaises(TypeError):
            census.StaticCensusShardV1()
        source = _production_shard(_REPRESENTATIVE_SKELETONS[_D4][0])
        for field, replacement in (
            ("shard_version", True),
            ("skeleton_ordinal", -1),
            ("_summary_json", "{}"),
            ("_construction_snapshot", "0" * 64),
            ("_assert_unchanged", lambda: None),
        ):
            hostile = _exact_field_clone(source)
            object.__setattr__(hostile, field, replacement)
            with self.subTest(field=field):
                with self.assertRaises((TypeError, ValueError)):
                    census.static_census_shard_summary_v1(hostile)

    def test_shard_ordinal_boundary_is_exact(self):
        prepared = _production_prepared_table()
        for ordinal in (True, -1, 1518):
            with self.subTest(ordinal=ordinal):
                with self.assertRaises((TypeError, ValueError)):
                    census.derive_static_census_shard_v1(prepared, ordinal)

    def test_standalone_shard_rederives_all_skeleton_identity_fields(self):
        prepared = _production_prepared_table()
        skeleton_ordinal = next(
            row[0]
            for row in prepared._skeleton_rows
            if row[5] == ("I", "FLR")
        )
        source = _synthetic_shard_summary(prepared, skeleton_ordinal)
        mutations = {
            "role_neutral_skeleton_hash": lambda summary: summary["skeleton"].__setitem__(
                "role_neutral_skeleton_hash", "0" * 64
            ),
            "role_neutral_semantic_hash": lambda summary: summary["skeleton"].__setitem__(
                "role_neutral_semantic_hash", "0" * 64
            ),
            "exact_stabilizer": lambda summary: summary["skeleton"].__setitem__(
                "exact_stabilizer", ["I", "FTB"]
            ),
        }
        for label, mutate in mutations.items():
            hostile_summary = copy.deepcopy(source)
            mutate(hostile_summary)
            hostile = _retokenize_shard(hostile_summary)
            with self.subTest(field=label):
                with self.assertRaises((TypeError, ValueError)):
                    census.static_census_shard_summary_v1(hostile)

    def test_standalone_shard_rejects_boolean_numeric_aliases(self):
        prepared = _production_prepared_table()
        source = _synthetic_shard_summary(prepared, 0)

        hostile_skeleton = copy.deepcopy(source)
        skeleton_payload = json.loads(
            hostile_skeleton["skeleton"]["canonical_profiled_skeleton_json"]
        )
        skeleton_payload["universe_version"] = True
        skeleton_canonical = _canonical(skeleton_payload)
        hostile_skeleton["skeleton"][
            "canonical_profiled_skeleton_json"
        ] = skeleton_canonical
        hostile_skeleton["skeleton"]["typed_skeleton_hash"] = _domain_hash(
            _PROFILED_SKELETON_HASH_DOMAIN, skeleton_canonical
        )
        hostile_skeleton["skeleton"][
            "role_neutral_skeleton_hash"
        ] = _domain_hash(_ROLE_NEUTRAL_SKELETON_HASH_DOMAIN, skeleton_canonical)
        hostile_skeleton["skeleton"][
            "role_neutral_semantic_hash"
        ] = census._canonical_role_neutral_semantic_hash(skeleton_canonical)
        hostile_skeleton["skeleton"]["exact_stabilizer"] = list(
            census._canonical_stabilizer(skeleton_canonical)
        )
        with self.assertRaises((TypeError, ValueError)):
            census.static_census_shard_summary_v1(
                _retokenize_shard(hostile_skeleton)
            )

        for field in (
            "representative_count",
            "weighted_setup_count",
            "paired_first_player_member_count",
        ):
            hostile_orbit = copy.deepcopy(source)
            hostile_orbit["setup_orbit"][field] = True
            with self.subTest(setup_orbit_field=field):
                with self.assertRaises((TypeError, ValueError)):
                    census.static_census_shard_summary_v1(
                        _retokenize_shard(hostile_orbit)
                    )
        for weight in source["setup_orbit"]["weight_histogram"]:
            hostile_histogram = copy.deepcopy(source)
            hostile_histogram["setup_orbit"]["weight_histogram"][weight] = True
            with self.subTest(setup_weight=weight):
                with self.assertRaises((TypeError, ValueError)):
                    census.static_census_shard_summary_v1(
                        _retokenize_shard(hostile_histogram)
                    )

        hostile_counts = copy.deepcopy(source)
        hostile_counts["eligible_supply_by_count_pair_and_contact"][0][
            "initial_counts"
        ] = {"A": False, "B": True}
        with self.assertRaises((TypeError, ValueError)):
            census.static_census_shard_summary_v1(
                _retokenize_shard(hostile_counts)
            )

        rejected = copy.deepcopy(source)
        representative_count = rejected["setup_orbit"]["representative_count"]
        rejected["eligibility"] = {
            "representative_eligible_count": 0,
            "weighted_eligible_count": 0,
            "paired_first_player_eligible_member_count": 0,
            "reason_combinations": [
                {
                    "reason_mask": 1,
                    "reasons": [
                        {
                            "code": "ZERO_ACTOR_WITH_NONPLACE",
                            "role": "A",
                            "first_player": None,
                        }
                    ],
                    "representative_count": representative_count,
                    "weighted_count": 6798,
                }
            ],
        }
        for contact_row in rejected["contact"].values():
            contact_row["eligible_representative_count"] = 0
            contact_row["eligible_weighted_count"] = 0
        for supply_row in rejected["eligible_supply_by_count_pair_and_contact"]:
            supply_row["representative_count"] = 0
            supply_row["weighted_count"] = 0
        census.static_census_shard_summary_v1(_retokenize_shard(rejected))

        rejected["eligibility"]["representative_eligible_count"] = False
        with self.assertRaises((TypeError, ValueError)):
            census.static_census_shard_summary_v1(
                _retokenize_shard(rejected)
            )


class StaticCensusCheckpointTests(unittest.TestCase):
    def test_one_shard_resume_is_immutable_and_partial_finalize_is_rejected(self):
        with self.assertRaises(TypeError):
            census.StaticCensusCheckpointV1()
        checkpoint = census.start_static_census_checkpoint_v1(
            _production_prepared_table()
        )
        before = census.static_census_checkpoint_progress_v1(checkpoint)
        self.assertEqual(
            (
                before["next_skeleton_ordinal"],
                before["processed_skeleton_count"],
                before["remaining_skeleton_count"],
                before["processed_factorized_carrier_count"],
                before["processed_labeled_setup_count"],
                before["complete"],
            ),
            (0, 0, 1518, 0, 0, False),
        )
        with self.assertRaises(ValueError):
            census.finalize_static_census_v1(checkpoint)

        resumed = census.advance_static_census_checkpoint_v1(checkpoint)
        after = census.static_census_checkpoint_progress_v1(resumed)
        shard_zero = census.static_census_shard_summary_v1(_production_shard(0))
        self.assertEqual(census.static_census_checkpoint_progress_v1(checkpoint), before)
        self.assertEqual(after["next_skeleton_ordinal"], 1)
        self.assertEqual(after["processed_skeleton_count"], 1)
        self.assertEqual(after["remaining_skeleton_count"], 1517)
        self.assertEqual(
            after["processed_factorized_carrier_count"],
            shard_zero["setup_orbit"]["representative_count"],
        )
        self.assertEqual(after["processed_labeled_setup_count"], 6798)
        self.assertEqual(after["processed_paired_first_player_member_count"], 13596)
        self.assertEqual(
            after["representative_eligible_count"],
            shard_zero["eligibility"]["representative_eligible_count"],
        )
        self.assertEqual(
            after["weighted_eligible_count"],
            shard_zero["eligibility"]["weighted_eligible_count"],
        )
        self.assertNotEqual(
            after["processed_skeleton_prefix_root"],
            before["processed_skeleton_prefix_root"],
        )
        self.assertNotEqual(
            after["ordered_shard_commitment_root"],
            before["ordered_shard_commitment_root"],
        )
        after["next_skeleton_ordinal"] = 1518
        self.assertEqual(
            census.static_census_checkpoint_progress_v1(resumed)[
                "next_skeleton_ordinal"
            ],
            1,
        )
        with self.assertRaises(ValueError):
            census.finalize_static_census_v1(resumed)

        self.assertIs(type(resumed._shard_summary_jsons), tuple)
        self.assertEqual(len(resumed._shard_summary_jsons), 1)
        self.assertIs(type(resumed._representative_reason_counts), tuple)
        self.assertEqual(len(resumed._representative_reason_counts), 4096)
        self.assertIs(type(resumed._weighted_reason_counts), tuple)
        self.assertEqual(len(resumed._weighted_reason_counts), 4096)

    def test_checkpoint_rejects_tamper_and_instance_method_shadowing(self):
        checkpoint = census.start_static_census_checkpoint_v1(
            _production_prepared_table()
        )
        for field, replacement in (
            ("checkpoint_version", True),
            ("next_skeleton_ordinal", 1),
            ("_representative_reason_counts", (0,) * 4095),
            ("_construction_snapshot", "0" * 64),
            ("_assert_unchanged", lambda: None),
        ):
            hostile = _exact_field_clone(checkpoint)
            object.__setattr__(hostile, field, replacement)
            with self.subTest(field=field):
                with self.assertRaises((TypeError, ValueError)):
                    census.static_census_checkpoint_progress_v1(hostile)


class SyntheticCompleteReportTests(unittest.TestCase):
    def test_complete_compact_checkpoint_finalizes_and_report_is_detached(self):
        with self.assertRaises(TypeError):
            census.StaticCensusReportV1()
        report = _synthetic_complete_report()
        canonical = census.canonical_static_census_report_json_v1(report)
        payload = json.loads(canonical)
        self.assertEqual(
            payload["population"],
            {
                "skeleton_count": 1518,
                "factorized_carrier_count": 5_111_055,
                "labeled_setup_count": 10_319_364,
                "paired_first_player_member_count": 20_638_728,
                "weight_histogram": {
                    "1": 1_184_850,
                    "2": 3_294_033,
                    "4": 627_732,
                    "8": 4_440,
                },
            },
        )
        self.assertEqual(len(payload["skeleton_shards"]), 1518)
        self.assertEqual(
            len(payload["eligibility"]["representative_reason_mask_counts"]),
            4096,
        )
        self.assertEqual(
            len(payload["eligibility"]["weighted_reason_mask_counts"]),
            4096,
        )
        self.assertEqual(
            census.static_census_report_hash_v1(report),
            payload["report_digest"],
        )
        body = copy.deepcopy(payload)
        digest = body.pop("report_digest")
        self.assertEqual(
            digest,
            _domain_hash(_STATIC_REPORT_BODY_DOMAIN, _canonical(body)),
        )

        payload["population"]["skeleton_count"] = -1
        payload["skeleton_shards"].clear()
        self.assertEqual(
            census.canonical_static_census_report_json_v1(report), canonical
        )

    def test_report_recomputes_embedded_setup_descriptor_identity(self):
        report = _synthetic_complete_report()
        payload = json.loads(
            census.canonical_static_census_report_json_v1(report)
        )
        payload["authorities"]["setup_orbit_table"]["setup_count"] = 0
        hostile = _retokenize_report(payload)
        for public in (
            census.canonical_static_census_report_json_v1,
            census.static_census_report_hash_v1,
        ):
            with self.subTest(public=public.__name__):
                with self.assertRaises((TypeError, ValueError)):
                    public(hostile)

    def test_report_rejects_boolean_numeric_aliases_with_the_old_digest(self):
        report = _synthetic_complete_report()
        source = json.loads(
            census.canonical_static_census_report_json_v1(report)
        )
        mutations = {
            "kernel_version": lambda payload: payload["authorities"].__setitem__(
                "initial_structure_kernel_version", True
            ),
            "aggregate_zero": lambda payload: payload["contact"][
                "CONTACT"
            ].__setitem__("representative_count", False),
            "reason_zero": lambda payload: payload["eligibility"][
                "representative_reason_mask_counts"
            ].__setitem__(1, False),
        }
        for label, mutate in mutations.items():
            payload = copy.deepcopy(source)
            mutate(payload)
            hostile = _exact_field_clone(report)
            object.__setattr__(
                hostile, "_canonical_payload_json", _canonical(payload)
            )
            with self.subTest(field=label):
                with self.assertRaises((TypeError, ValueError)):
                    census.canonical_static_census_report_json_v1(hostile)


class OneShotBuildPathTests(unittest.TestCase):
    def test_one_shot_builder_prepares_once_and_derives_one_linear_pass(self):
        source_table = object()
        prepared = object()
        checkpoint = object()
        expected_report = object()
        prepare_calls = []
        derive_ordinals = []
        make_calls = []
        finalize_calls = []

        def prepare(value):
            prepare_calls.append(value)
            return prepared

        def derive(value, ordinal):
            self.assertIs(value, prepared)
            derive_ordinals.append(ordinal)
            shard = type("SyntheticShard", (), {})()
            shard._summary_json = _canonical(
                {
                    "eligibility": {
                        "reason_combinations": [
                            {
                                "reason_mask": 0,
                                "representative_count": 1,
                                "weighted_count": 2,
                            }
                        ]
                    }
                }
            )
            return shard

        def make(value, next_ordinal, summaries, representative, weighted):
            make_calls.append(
                (value, next_ordinal, len(summaries), representative, weighted)
            )
            return checkpoint

        def finalize(value):
            finalize_calls.append(value)
            return expected_report

        with mock.patch.object(census, "prepare_static_census_table_v1", prepare), mock.patch.object(
            census, "_derive_shard_core", derive
        ), mock.patch.object(census, "_make_checkpoint", make), mock.patch.object(
            census, "finalize_static_census_v1", finalize
        ):
            observed = census.build_static_census_v1(
                source_table,
                _prepare=prepare,
                _derive=derive,
                _make=make,
                _finalize=finalize,
            )

        self.assertIs(observed, expected_report)
        self.assertEqual(prepare_calls, [source_table])
        self.assertEqual(derive_ordinals, list(range(1518)))
        self.assertEqual(len(make_calls), 1)
        self.assertIs(make_calls[0][0], prepared)
        self.assertEqual(make_calls[0][1:3], (1518, 1518))
        self.assertEqual(make_calls[0][3][0], 1518)
        self.assertEqual(make_calls[0][4][0], 3036)
        self.assertTrue(all(value == 0 for value in make_calls[0][3][1:]))
        self.assertTrue(all(value == 0 for value in make_calls[0][4][1:]))
        self.assertEqual(finalize_calls, [checkpoint])


class StaticCensusHostileBoundaryTests(unittest.TestCase):
    def test_public_entrypoints_reject_rebound_upstream_authorities(self):
        replacements = (
            (compiler, "transform_typed_setup_v1"),
            (universe, "enumerate_fresh_canonical_profiled_skeletons"),
            (initial, "derive_prepared_initial_structure_snapshot_v1"),
        )
        for module, name in replacements:
            with self.subTest(module=module.__name__, name=name):
                with mock.patch.object(module, name, lambda *args, **kwargs: ()):
                    with self.assertRaises(census.StaticCensusClosureError):
                        census.build_setup_orbit_table_v1()

    def test_public_entrypoints_reject_rebound_json_and_hash_authorities(self):
        for module, name in ((json, "dumps"), (hashlib, "sha256")):
            with self.subTest(name=name):
                original = getattr(module, name)

                def rebound(*args, _original=original, **kwargs):
                    return _original(*args, **kwargs)

                with mock.patch.object(module, name, rebound):
                    with self.assertRaises(census.StaticCensusClosureError):
                        census.build_setup_orbit_table_v1()


class CapabilityIsolationTests(unittest.TestCase):
    def test_isolated_import_and_setup_table_have_no_legacy_or_io_capability(self):
        source_root = str(Path(__file__).resolve().parents[1] / "src")
        code = textwrap.dedent(
            """
            import builtins
            import importlib.abc
            import os
            import socket
            import sys
            sys.path.insert(0, {source_root!r})
            allowed = {{
                "parity_forge_universe",
                "parity_forge_universe.typed_occupancy",
                "parity_forge_universe.schema_v4_compiler",
                "parity_forge_universe.initial_structure",
                "parity_forge_universe.static_census",
            }}
            class Poison(importlib.abc.MetaPathFinder):
                def find_spec(self, fullname, path=None, target=None):
                    if fullname == "parity_forge" or fullname.startswith("parity_forge."):
                        raise RuntimeError("forbidden legacy import: " + fullname)
                    if fullname.startswith("parity_forge_universe.") and fullname not in allowed:
                        raise RuntimeError("forbidden sibling import: " + fullname)
                    return None
            sys.meta_path.insert(0, Poison())
            def fail_io(*args, **kwargs):
                raise RuntimeError("forbidden static-census I/O")
            builtins.open = fail_io
            os.open = fail_io
            socket.socket = fail_io
            import parity_forge_universe.static_census as census
            table = census.build_setup_orbit_table_v1()
            descriptor = census.setup_orbit_table_descriptor_v1(table)
            assert descriptor["setup_count"] == 6798
            loaded = {{
                name for name in sys.modules
                if name == "parity_forge"
                or name.startswith("parity_forge.")
                or name == "parity_forge_universe"
                or name.startswith("parity_forge_universe.")
            }}
            assert loaded == allowed, sorted(loaded)
            """
        ).format(source_root=source_root)
        completed = subprocess.run(
            [sys.executable, "-I", "-c", code],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_production_ast_excludes_gameplay_outcome_io_and_dynamic_imports(self):
        package_root = (
            Path(__file__).resolve().parents[1] / "src" / "parity_forge_universe"
        )
        source_paths = (
            package_root / "__init__.py",
            package_root / "typed_occupancy.py",
            package_root / "schema_v4_compiler.py",
            package_root / "initial_structure.py",
            package_root / "static_census.py",
        )
        forbidden_imports = {
            "asyncio",
            "http",
            "importlib",
            "multiprocessing",
            "os",
            "pathlib",
            "requests",
            "shutil",
            "socket",
            "subprocess",
            "urllib",
        }
        forbidden_names = {
            "GameState",
            "Outcome",
            "engine",
            "apply_action",
            "initial_state",
            "legal_actions",
            "goal_satisfied",
            "terminal_status",
            "solver",
            "solve_game",
            "agent",
            "play",
            "play_game",
            "replay",
            "telemetry",
            "history",
            "selection",
            "candidate",
            "outcome",
            "winner",
            "rank",
            "score",
        }
        forbidden_calls = forbidden_names | {
            "__import__",
            "compile",
            "eval",
            "exec",
            "open",
        }
        imported = set()
        names = set()
        calls = set()
        for source_path in source_paths:
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    imported.add((node.module or "").split(".")[0])
                elif isinstance(node, ast.Name):
                    names.add(node.id)
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        calls.add(node.func.id)
                    elif isinstance(node.func, ast.Attribute):
                        calls.add(node.func.attr)
        self.assertTrue(forbidden_imports.isdisjoint(imported), sorted(imported))
        self.assertTrue(
            forbidden_names.isdisjoint(names), sorted(forbidden_names & names)
        )
        self.assertTrue(
            forbidden_calls.isdisjoint(calls), sorted(forbidden_calls & calls)
        )


def _comb(n, k):
    if not 0 <= k <= n:
        return 0
    numerator = 1
    denominator = 1
    for offset in range(1, k + 1):
        numerator *= n - k + offset
        denominator *= offset
    return numerator // denominator


if __name__ == "__main__":
    unittest.main()
