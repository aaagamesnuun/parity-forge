"""Pure factorized static census for the Plan-0015 typed universe.

The module owns four deliberately narrow calculations:

* the exact 6,798-row owner-labelled setup order and all eight D4 images;
* the five admitted exact skeleton-stabilizer setup quotients;
* one-skeleton-at-a-time aggregation of the sealed initial-structure kernel;
* an in-process immutable prefix checkpoint and output-only final report.

It never applies an action, constructs a gameplay state, observes a terminal or
outcome, reads history, ranks or selects a carrier, or performs filesystem I/O.
Checkpoint values are operational process-local tokens.  They are not parsed
from JSON and are not evidence or an independently trusted resume format.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from itertools import combinations
from math import comb
from typing import Any, Dict, Iterable, List, Optional, Tuple

from . import initial_structure as initial
from . import schema_v4_compiler as compiler
from . import typed_occupancy as universe


STATIC_CENSUS_VERSION_V1 = 1
SETUP_ORBIT_TABLE_VERSION_V1 = 1
STATIC_CENSUS_SHARD_VERSION_V1 = 1
STATIC_CENSUS_CHECKPOINT_VERSION_V1 = 1
STATIC_CENSUS_REPORT_VERSION_V1 = 1


class StaticCensusClosureError(ValueError):
    """A sealed authority, finite domain, factorization, or proof changed."""


Position = Tuple[int, int]
CountPair = Tuple[int, int]
StabilizerSignature = Tuple[str, ...]

_BOARD: Tuple[Position, ...] = tuple(
    (row, column) for row in range(3) for column in range(3)
)
_COUNT_PAIRS: Tuple[CountPair, ...] = tuple(
    (a_count, b_count)
    for a_count in range(4)
    for b_count in range(4)
    if (a_count, b_count) != (0, 0)
)
_COUNT_PAIR_SUPPLIES: Tuple[int, ...] = (
    9,
    36,
    84,
    9,
    72,
    252,
    504,
    36,
    252,
    756,
    1260,
    84,
    504,
    1260,
    1680,
)
_D4_NAMES: Tuple[str, ...] = (
    "I",
    "R90",
    "R180",
    "R270",
    "FLR",
    "FTB",
    "FD",
    "FA",
)
_STABILIZER_SIGNATURES: Tuple[StabilizerSignature, ...] = (
    ("I",),
    ("I", "FLR"),
    ("I", "FTB"),
    ("I", "R180", "FLR", "FTB"),
    _D4_NAMES,
)
_STABILIZER_SKELETON_COUNTS: Tuple[int, ...] = (141, 810, 165, 396, 6)
_SETUP_ORBIT_COUNTS: Tuple[int, ...] = (6798, 3511, 3511, 1827, 970)
_SETUP_WEIGHT_HISTOGRAMS: Tuple[Tuple[Tuple[int, int], ...], ...] = (
    ((1, 6798),),
    ((1, 224), (2, 3287)),
    ((1, 224), (2, 3287)),
    ((1, 20), (2, 225), (4, 1582)),
    ((1, 2), (2, 18), (4, 210), (8, 740)),
)
_FIXED_SETUP_COUNTS: Tuple[int, ...] = (6798, 2, 62, 2, 224, 224, 224, 224)
_GLOBAL_WEIGHT_HISTOGRAM: Tuple[Tuple[int, int], ...] = (
    (1, 1_184_850),
    (2, 3_294_033),
    (4, 627_732),
    (8, 4_440),
)

_EXPECTED_SETUP_COUNT = 6_798
_EXPECTED_SKELETON_COUNT = 1_518
_EXPECTED_FACTORIZED_CARRIER_COUNT = 5_111_055
_EXPECTED_LABELED_SETUP_COUNT = 10_319_364
_EXPECTED_PAIRED_MEMBER_COUNT = 20_638_728
_EXPECTED_ALL_ORDERED_CONTRIBUTION = 11_085_600
_EXPECTED_SELF_ISOMORPHIC_CONTRIBUTION = 215_508
_EXPECTED_OLD_REGION_CONTRIBUTION = 647_982
_EXPECTED_UNIVERSE_DESCRIPTOR_ROOT = (
    "05826dc2da02890f3f562ee2d6febda523c58837affb757b5dff6d62c074e6ab"
)
_EXPECTED_FRESH_SKELETON_ROOT = (
    "ca02a2bbd844962fd83c7190eec69dea51877940ea6f0836c5a00338a3e9e190"
)
_EXPECTED_COUNT_TABLE_ROOT = (
    "de2e65f28be1f60aff4712c23c8681ea7945324886a2954a0f8d8cbfa905d226"
)

# Filled from the independent canonical-table derivation before the module is
# admitted as a sealed implementation.  Empty only while the first construction
# patch is being locally measured; _official_version rejects public use then.
_EXPECTED_SETUP_ORBIT_TABLE_ROOT = (
    "f1bc82d1cfbaac9933e097aba2f4118737e19f7a190f06bc9f0a83add17c2e23"
)
_EXPECTED_SKELETON_AUTHORITY_ROOT = (
    "53221ffdbd42e4c86e9c54eadb6e0659bf71ff350dcdf0944b062ce56c3e1488"
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
_SKELETON_AUTHORITY_ROOT_DOMAIN = (
    b"parity-forge:plan0015:static-census-skeleton-authority:v1\0"
)
_STATIC_LEAF_DOMAIN = b"parity-forge:plan0015:static-census-leaf:v1\0"
_STATIC_SHARD_ROOT_DOMAIN = b"parity-forge:plan0015:static-census-shard:v1\0"
_STATIC_SHARD_SUMMARY_DOMAIN = (
    b"parity-forge:plan0015:static-census-shard-summary:v1\0"
)
_STATIC_CHECKPOINT_DOMAIN = (
    b"parity-forge:plan0015:static-census-checkpoint:v1\0"
)
_STATIC_REPORT_DOMAIN = b"parity-forge:plan0015:static-census-report:v1\0"
_STATIC_REPORT_BODY_DOMAIN = (
    b"parity-forge:plan0015:static-census-report-body:v1\0"
)
_PREPARED_CENSUS_TABLE_DOMAIN = (
    b"parity-forge:plan0015:prepared-static-census-table:v1\0"
)
_STATIC_GROUP_ROOT_DOMAIN = (
    b"parity-forge:plan0015:static-census-descriptor-group:v1\0"
)
_INITIAL_RESULT_DOMAIN = (
    b"parity-forge:plan0015:initial-structure-result:v1\0"
)
_INITIAL_EVIDENCE_DOMAIN = (
    b"parity-forge:plan0015:initial-structure-result-evidence:v1\0"
)
_TYPED_SETUP_HASH_DOMAIN = b"parity-forge:plan0015:typed-setup:v1\0"
_PROFILED_SKELETON_HASH_DOMAIN = (
    b"parity-forge:typed-occupancy:skeleton:v1\0"
)
_ROLE_NEUTRAL_SKELETON_HASH_DOMAIN = (
    b"parity-forge:typed-occupancy:role-neutral-skeleton:v1\0"
)
_ROLE_NEUTRAL_SEMANTIC_HASH_DOMAIN = (
    b"parity-forge:typed-occupancy:role-neutral-semantic:v1\0"
)
_UNIVERSE_FRESH_ROOT_DOMAIN = (
    b"parity-forge:typed-occupancy:fresh-canonical:v1\0"
)
_SKELETON_DESCRIPTOR_ROOT_DOMAIN = (
    _SKELETON_AUTHORITY_ROOT_DOMAIN + b"descriptor\0"
)

_MAX_SNAPSHOT_BYTES = 100_000
_MAX_JSON_NODES = 20_000
_MAX_JSON_DEPTH = 32

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
_CONTACT_CLASSES: Tuple[str, str] = ("CONTACT", "SEPARATED")
_FIRST_PLAYERS: Tuple[str, str] = ("A", "B")
_WORK_FIELDS: Tuple[str, str, str] = (
    "state_weight_sum",
    "action_candidate_iterations",
    "scan_candidate_iterations",
)
_DESCRIPTOR_GROUPS: Tuple[str, ...] = (
    "structural",
    "description_clause",
    "operational_substep",
    "primitive_concept",
    "vector_cardinality",
    "density",
    "contact",
    "dependency",
)


def _canonical_json(
    value: Any,
    _dumps: Any = json.dumps,
    _error: Any = StaticCensusClosureError,
) -> str:
    if json.dumps is not _dumps or StaticCensusClosureError is not _error:
        raise _error("JSON encoder binding changed")
    return _dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _domain_hash(
    domain: bytes,
    canonical: str,
    _sha256: Any = hashlib.sha256,
    _error: Any = StaticCensusClosureError,
) -> str:
    if hashlib.sha256 is not _sha256 or StaticCensusClosureError is not _error:
        raise _error("SHA-256 binding changed")
    return _sha256(domain + canonical.encode("utf-8")).hexdigest()


def _sequence_root(
    domain: bytes,
    canonical_values: Iterable[str],
    _sha256: Any = hashlib.sha256,
    _error: Any = StaticCensusClosureError,
) -> str:
    """Bind ordinal, byte length, and exact canonical bytes for every leaf."""

    if hashlib.sha256 is not _sha256 or StaticCensusClosureError is not _error:
        raise _error("SHA-256 binding changed")
    digest = _sha256(domain)
    for ordinal, canonical in enumerate(canonical_values):
        if type(canonical) is not str:
            raise TypeError("sequence leaves must be exact canonical strings")
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
        raise TypeError("{} must be an exact object".format(label))
    if any(type(key) is not str for key in value):
        raise TypeError("{} keys must be exact strings".format(label))
    return value


def _exact_keys(value: Dict[str, Any], expected: Iterable[str], label: str) -> None:
    expected_set = set(expected)
    if set(value) != expected_set:
        raise ValueError("{} has noncanonical fields".format(label))


def _require_exact_fields(value: Any, expected: Iterable[str], label: str) -> None:
    try:
        fields = vars(value)
    except TypeError as error:
        raise TypeError("{} fields are unavailable".format(label)) from error
    if type(fields) is not dict or set(fields) != set(expected):
        raise TypeError("{} has noncanonical fields".format(label))


def _validate_json_tree(
    value: Any,
    label: str,
    max_nodes: int = _MAX_JSON_NODES,
    max_depth: int = _MAX_JSON_DEPTH,
    _max_nodes: int = _MAX_JSON_NODES,
    _max_depth: int = _MAX_JSON_DEPTH,
    _error: Any = StaticCensusClosureError,
) -> None:
    if (
        _MAX_JSON_NODES != _max_nodes
        or _MAX_JSON_DEPTH != _max_depth
        or StaticCensusClosureError is not _error
    ):
        raise _error("JSON-tree limit binding changed")
    nodes = 0
    active: set[int] = set()

    def visit(item: Any, depth: int) -> None:
        nonlocal nodes
        nodes += 1
        if nodes > max_nodes:
            raise ValueError("{} exceeds the JSON node cap".format(label))
        if depth > max_depth:
            raise ValueError("{} exceeds the JSON depth cap".format(label))
        if item is None or type(item) in (bool, int, str):
            return
        if type(item) not in (dict, list):
            raise TypeError("{} must contain exact JSON values".format(label))
        identity = id(item)
        if identity in active:
            raise ValueError("{} cannot contain a cycle".format(label))
        active.add(identity)
        try:
            children = item.values() if type(item) is dict else item
            for child in children:
                visit(child, depth + 1)
        finally:
            active.remove(identity)

    visit(value, 0)


def _api_guard(
    _compiler_module: Any = compiler,
    _universe_module: Any = universe,
    _initial_module: Any = initial,
    _setup_type: Any = compiler.TypedSetupV1,
    _carrier_type: Any = compiler.TypedSetupCarrierV1,
    _setup_json: Any = compiler.canonical_typed_setup_json_v1,
    _setup_hash: Any = compiler.typed_setup_hash_v1,
    _setup_transform: Any = compiler.transform_typed_setup_v1,
    _carrier_json: Any = compiler.canonical_typed_setup_carrier_json_v1,
    _carrier_hash: Any = compiler.typed_setup_carrier_hash_v1,
    _skeleton_type: Any = universe.ProfiledSkeleton,
    _d4_type: Any = universe.D4Transform,
    _d4_members: Tuple[Any, ...] = (
        universe.D4Transform.I,
        universe.D4Transform.R90,
        universe.D4Transform.R180,
        universe.D4Transform.R270,
        universe.D4Transform.FLR,
        universe.D4Transform.FTB,
        universe.D4Transform.FD,
        universe.D4Transform.FA,
    ),
    _enumerate_fresh: Any = universe.enumerate_fresh_canonical_profiled_skeletons,
    _enumerate_all: Any = universe.enumerate_admitted_profiled_skeletons,
    _is_self: Any = universe.is_role_swap_d4_self_isomorphic,
    _is_old: Any = universe.is_plan0013_profiled_region,
    _transform_skeleton: Any = universe.transform_profiled_skeleton,
    _parse_skeleton: Any = universe.parse_profiled_skeleton,
    _skeleton_json: Any = universe.canonical_profiled_skeleton_json,
    _skeleton_hash: Any = universe.profiled_skeleton_hash,
    _neutral_skeleton_hash: Any = universe.role_neutral_profiled_skeleton_hash,
    _neutral_semantic_hash: Any = universe.role_neutral_semantic_hash,
    _build_descriptor: Any = universe.build_universe_descriptor,
    _descriptor_json: Any = universe.canonical_universe_descriptor_json,
    _prepare: Any = initial.prepare_initial_structure_skeleton_v1,
    _snapshot: Any = initial.derive_prepared_initial_structure_snapshot_v1,
    _build_count: Any = initial.build_count_lattice_descriptor_v1,
    _count_hash: Any = initial.count_lattice_descriptor_hash_v1,
    _error: Any = StaticCensusClosureError,
) -> Tuple[Any, ...]:
    if (
        compiler is not _compiler_module
        or universe is not _universe_module
        or initial is not _initial_module
        or compiler.TypedSetupV1 is not _setup_type
        or compiler.TypedSetupCarrierV1 is not _carrier_type
        or compiler.canonical_typed_setup_json_v1 is not _setup_json
        or compiler.typed_setup_hash_v1 is not _setup_hash
        or compiler.transform_typed_setup_v1 is not _setup_transform
        or compiler.canonical_typed_setup_carrier_json_v1 is not _carrier_json
        or compiler.typed_setup_carrier_hash_v1 is not _carrier_hash
        or universe.ProfiledSkeleton is not _skeleton_type
        or universe.D4Transform is not _d4_type
        or tuple(map(id, tuple(_d4_type))) != tuple(map(id, _d4_members))
        or universe.enumerate_fresh_canonical_profiled_skeletons
        is not _enumerate_fresh
        or universe.enumerate_admitted_profiled_skeletons is not _enumerate_all
        or universe.is_role_swap_d4_self_isomorphic is not _is_self
        or universe.is_plan0013_profiled_region is not _is_old
        or universe.transform_profiled_skeleton is not _transform_skeleton
        or universe.parse_profiled_skeleton is not _parse_skeleton
        or universe.canonical_profiled_skeleton_json is not _skeleton_json
        or universe.profiled_skeleton_hash is not _skeleton_hash
        or universe.role_neutral_profiled_skeleton_hash
        is not _neutral_skeleton_hash
        or universe.role_neutral_semantic_hash is not _neutral_semantic_hash
        or universe.build_universe_descriptor is not _build_descriptor
        or universe.canonical_universe_descriptor_json is not _descriptor_json
        or initial.prepare_initial_structure_skeleton_v1 is not _prepare
        or initial.derive_prepared_initial_structure_snapshot_v1 is not _snapshot
        or initial.build_count_lattice_descriptor_v1 is not _build_count
        or initial.count_lattice_descriptor_hash_v1 is not _count_hash
        or StaticCensusClosureError is not _error
    ):
        raise _error("upstream authority binding changed")
    return (
        _setup_type,
        _carrier_type,
        _setup_json,
        _setup_hash,
        _setup_transform,
        _carrier_json,
        _carrier_hash,
        _d4_members,
        _enumerate_fresh,
        _enumerate_all,
        _is_self,
        _is_old,
        _transform_skeleton,
        _parse_skeleton,
        _skeleton_json,
        _skeleton_hash,
        _neutral_skeleton_hash,
        _neutral_semantic_hash,
        _build_descriptor,
        _descriptor_json,
        _prepare,
        _snapshot,
        _build_count,
        _count_hash,
    )


def _official_version(
    _api: Any = _api_guard,
    _canonical: Any = _canonical_json,
    _hash: Any = _domain_hash,
    _sequence: Any = _sequence_root,
    _json_module: Any = json,
    _hashlib_module: Any = hashlib,
    _json_dumps: Any = json.dumps,
    _json_loads: Any = json.loads,
    _sha256: Any = hashlib.sha256,
    _comb: Any = comb,
    _error: Any = StaticCensusClosureError,
    _static_version: int = STATIC_CENSUS_VERSION_V1,
    _setup_version: int = SETUP_ORBIT_TABLE_VERSION_V1,
    _shard_version: int = STATIC_CENSUS_SHARD_VERSION_V1,
    _checkpoint_version: int = STATIC_CENSUS_CHECKPOINT_VERSION_V1,
    _report_version: int = STATIC_CENSUS_REPORT_VERSION_V1,
    _board: Tuple[Position, ...] = _BOARD,
    _count_pairs: Tuple[CountPair, ...] = _COUNT_PAIRS,
    _count_pair_supplies: Tuple[int, ...] = _COUNT_PAIR_SUPPLIES,
    _d4_names: Tuple[str, ...] = _D4_NAMES,
    _stabilizer_signatures: Tuple[StabilizerSignature, ...] = _STABILIZER_SIGNATURES,
    _expected_setup_count: int = _EXPECTED_SETUP_COUNT,
    _expected_setup_root: str = _EXPECTED_SETUP_ORBIT_TABLE_ROOT,
    _expected_skeleton_root: str = _EXPECTED_SKELETON_AUTHORITY_ROOT,
    _sha_validator: Any = _is_sha256,
) -> int:
    if (
        _api_guard is not _api
        or _canonical_json is not _canonical
        or _domain_hash is not _hash
        or _sequence_root is not _sequence
        or json is not _json_module
        or hashlib is not _hashlib_module
        or json.dumps is not _json_dumps
        or json.loads is not _json_loads
        or hashlib.sha256 is not _sha256
        or comb is not _comb
        or StaticCensusClosureError is not _error
        or STATIC_CENSUS_VERSION_V1 != _static_version
        or SETUP_ORBIT_TABLE_VERSION_V1 != _setup_version
        or STATIC_CENSUS_SHARD_VERSION_V1 != _shard_version
        or STATIC_CENSUS_CHECKPOINT_VERSION_V1 != _checkpoint_version
        or STATIC_CENSUS_REPORT_VERSION_V1 != _report_version
        or _BOARD is not _board
        or _COUNT_PAIRS is not _count_pairs
        or _COUNT_PAIR_SUPPLIES is not _count_pair_supplies
        or _D4_NAMES is not _d4_names
        or _STABILIZER_SIGNATURES is not _stabilizer_signatures
        or _EXPECTED_SETUP_COUNT != _expected_setup_count
        or _EXPECTED_SETUP_ORBIT_TABLE_ROOT != _expected_setup_root
        or _EXPECTED_SKELETON_AUTHORITY_ROOT != _expected_skeleton_root
        or _is_sha256 is not _sha_validator
    ):
        raise _error("static-census authority binding changed")
    _api()
    versions = (
        _static_version,
        _setup_version,
        _shard_version,
        _checkpoint_version,
        _report_version,
    )
    if any(type(value) is not int for value in versions) or versions != (1,) * 5:
        raise _error("static-census version binding changed")
    if (
        _board != tuple((r, c) for r in range(3) for c in range(3))
        or _count_pairs
        != tuple(
            (a, b)
            for a in range(4)
            for b in range(4)
            if (a, b) != (0, 0)
        )
        or _count_pair_supplies
        != tuple(_comb(9, a) * _comb(9 - a, b) for a, b in _count_pairs)
        or sum(_count_pair_supplies) != _expected_setup_count
        or _d4_names != tuple(member.value for member in _api()[7])
        or _stabilizer_signatures[-1] != _d4_names
    ):
        raise _error("static-census finite literals changed")
    if not _sha_validator(_expected_setup_root):
        raise _error("setup-orbit table root changed format")
    if _expected_skeleton_root and not _sha_validator(
        _expected_skeleton_root
    ):
        raise _error("skeleton authority root changed format")
    return 1


def _validate_embedded_descriptor(
    value: Any,
    label: str,
    domain: bytes,
    expected_root: str,
    _exact: Any = _exact_dict,
    _tree: Any = _validate_json_tree,
    _canonical: Any = _canonical_json,
    _hash: Any = _domain_hash,
    _sha_validator: Any = _is_sha256,
    _error: Any = StaticCensusClosureError,
) -> Dict[str, Any]:
    """Authenticate one compact descriptor from its exact embedded JSON body."""

    if (
        _exact_dict is not _exact
        or _validate_json_tree is not _tree
        or _canonical_json is not _canonical
        or _domain_hash is not _hash
        or _is_sha256 is not _sha_validator
        or StaticCensusClosureError is not _error
    ):
        raise _error("descriptor validator binding changed")
    if type(domain) is not bytes or not domain or not domain.endswith(b"\0"):
        raise TypeError("{} domain must be exact NUL-terminated bytes".format(label))
    if not _sha_validator(expected_root):
        raise _error("{} frozen root changed format".format(label))
    descriptor = _exact(value, label)
    _tree(descriptor, label)
    body = dict(descriptor)
    descriptor_root = body.pop("descriptor_root", None)
    if (
        not _sha_validator(descriptor_root)
        or descriptor_root != expected_root
        or descriptor_root != _hash(domain, _canonical(body))
    ):
        raise ValueError("{} root does not reconstruct".format(label))
    return descriptor


# Private immutable setup row:
# ordinal, count-pair index, A positions, B positions, canonical JSON, setup hash,
# eight D4 image ordinals in _D4_NAMES order.
_SetupRow = Tuple[Any, ...]

# Private immutable partition:
# exact stabilizer signature, raw->representative ordinal map, and ordered
# representative (ordinal, orbit weight) records.
_SetupPartition = Tuple[Any, ...]


def _enumerate_setup_position_rows(
    _count_pairs: Tuple[CountPair, ...] = _COUNT_PAIRS,
    _board: Tuple[Position, ...] = _BOARD,
    _supplies: Tuple[int, ...] = _COUNT_PAIR_SUPPLIES,
    _expected_count: int = _EXPECTED_SETUP_COUNT,
    _combinations: Any = combinations,
    _error: Any = StaticCensusClosureError,
) -> Tuple[Tuple[Any, ...], ...]:
    if (
        _COUNT_PAIRS is not _count_pairs
        or _BOARD is not _board
        or _COUNT_PAIR_SUPPLIES is not _supplies
        or _EXPECTED_SETUP_COUNT != _expected_count
        or combinations is not _combinations
        or StaticCensusClosureError is not _error
    ):
        raise _error("setup enumeration binding changed")
    rows: List[Tuple[Any, ...]] = []
    for count_index, (a_count, b_count) in enumerate(_count_pairs):
        before = len(rows)
        for positions_a in _combinations(_board, a_count):
            remaining = tuple(position for position in _board if position not in positions_a)
            for positions_b in _combinations(remaining, b_count):
                rows.append((count_index, tuple(positions_a), tuple(positions_b)))
        if len(rows) - before != _supplies[count_index]:
            raise _error("setup count-pair supply changed")
    if len(rows) != _expected_count:
        raise _error("setup enumeration cardinality changed")
    return tuple(rows)


def _build_setup_material(
    _api: Any = _api_guard,
    _enumerate: Any = _enumerate_setup_position_rows,
    _d4_names: Tuple[str, ...] = _D4_NAMES,
    _signatures: Tuple[StabilizerSignature, ...] = _STABILIZER_SIGNATURES,
    _orbit_counts: Tuple[int, ...] = _SETUP_ORBIT_COUNTS,
    _weight_histograms: Tuple[Tuple[Tuple[int, int], ...], ...] = _SETUP_WEIGHT_HISTOGRAMS,
    _expected_count: int = _EXPECTED_SETUP_COUNT,
    _error: Any = StaticCensusClosureError,
) -> Tuple[Tuple[_SetupRow, ...], Tuple[_SetupPartition, ...]]:
    """Construct the complete setup table without retaining mutable typed values."""

    if (
        _api_guard is not _api
        or _enumerate_setup_position_rows is not _enumerate
        or _D4_NAMES is not _d4_names
        or _STABILIZER_SIGNATURES is not _signatures
        or _SETUP_ORBIT_COUNTS is not _orbit_counts
        or _SETUP_WEIGHT_HISTOGRAMS is not _weight_histograms
        or _EXPECTED_SETUP_COUNT != _expected_count
        or StaticCensusClosureError is not _error
    ):
        raise _error("setup material binding changed")
    api = _api()
    setup_type, _, setup_json, setup_hash, setup_transform = api[:5]
    d4_members = api[7]
    source_rows = _enumerate()
    partial: List[Tuple[Any, ...]] = []
    canonical_to_ordinal: Dict[str, int] = {}
    for ordinal, (count_index, positions_a, positions_b) in enumerate(source_rows):
        setup = setup_type(1, positions_a, positions_b)
        canonical = setup_json(setup)
        identity = setup_hash(setup)
        if canonical in canonical_to_ordinal:
            raise _error("typed setup enumeration is not injective")
        canonical_to_ordinal[canonical] = ordinal
        partial.append(
            (
                ordinal,
                count_index,
                positions_a,
                positions_b,
                canonical,
                identity,
            )
        )

    rows: List[_SetupRow] = []
    for record in partial:
        ordinal, count_index, positions_a, positions_b, canonical, identity = record
        source = setup_type(1, positions_a, positions_b)
        image_ordinals: List[int] = []
        for transform in d4_members:
            transformed = setup_transform(source, transform)
            transformed_json = setup_json(transformed)
            try:
                image_ordinal = canonical_to_ordinal[transformed_json]
            except KeyError as error:
                raise _error(
                    "D4 setup image escaped the 6,798-row domain"
                ) from error
            if partial[image_ordinal][1] != count_index:
                raise _error("D4 changed a setup count pair")
            image_ordinals.append(image_ordinal)
        rows.append(record + (tuple(image_ordinals),))
    frozen_rows = tuple(rows)

    partitions: List[_SetupPartition] = []
    name_to_index = {name: index for index, name in enumerate(_d4_names)}
    for group_index, signature in enumerate(_signatures):
        transform_indexes = tuple(name_to_index[name] for name in signature)
        raw_to_representative: List[int] = []
        for row in frozen_rows:
            image_ordinals = tuple(row[6][index] for index in transform_indexes)
            representative = min(
                set(image_ordinals),
                key=lambda value: frozen_rows[value][4].encode("utf-8"),
            )
            raw_to_representative.append(representative)
        representatives: List[Tuple[int, int]] = []
        for ordinal, representative in enumerate(raw_to_representative):
            if ordinal != representative:
                continue
            orbit_members = {
                frozen_rows[ordinal][6][index] for index in transform_indexes
            }
            weight = len(orbit_members)
            if any(raw_to_representative[item] != ordinal for item in orbit_members):
                raise _error("setup orbit mapping is not closed")
            representatives.append((ordinal, weight))
        observed_histogram: Dict[int, int] = {}
        for _, weight in representatives:
            observed_histogram[weight] = observed_histogram.get(weight, 0) + 1
        if (
            len(representatives) != _orbit_counts[group_index]
            or tuple(sorted(observed_histogram.items()))
            != _weight_histograms[group_index]
            or sum(weight for _, weight in representatives) != _expected_count
        ):
            raise _error("setup subgroup quotient arithmetic changed")
        partitions.append(
            (signature, tuple(raw_to_representative), tuple(representatives))
        )
    return frozen_rows, tuple(partitions)


def _setup_descriptor_from_material(
    rows: Tuple[_SetupRow, ...],
    partitions: Tuple[_SetupPartition, ...],
    _expected_count: int = _EXPECTED_SETUP_COUNT,
    _expected_root: str = _EXPECTED_SETUP_ORBIT_TABLE_ROOT,
    _d4_names: Tuple[str, ...] = _D4_NAMES,
    _count_pairs: Tuple[CountPair, ...] = _COUNT_PAIRS,
    _board: Tuple[Position, ...] = _BOARD,
    _fixed_setup_counts: Tuple[int, ...] = _FIXED_SETUP_COUNTS,
    _signatures: Tuple[StabilizerSignature, ...] = _STABILIZER_SIGNATURES,
    _orbit_counts: Tuple[int, ...] = _SETUP_ORBIT_COUNTS,
    _weight_histograms: Tuple[Tuple[Tuple[int, int], ...], ...] = _SETUP_WEIGHT_HISTOGRAMS,
    _count_pair_supplies: Tuple[int, ...] = _COUNT_PAIR_SUPPLIES,
    _setup_hash_domain: bytes = _TYPED_SETUP_HASH_DOMAIN,
    _descriptor_domain: bytes = _SETUP_DESCRIPTOR_DOMAIN,
    _ordered_setup_domain: bytes = _ORDERED_SETUP_ROOT_DOMAIN,
    _image_domain: bytes = _SETUP_IMAGE_ROOT_DOMAIN,
    _mapping_domain: bytes = _SETUP_GROUP_MAPPING_ROOT_DOMAIN,
    _representative_domain: bytes = _SETUP_GROUP_REPRESENTATIVE_ROOT_DOMAIN,
    _canonical: Any = _canonical_json,
    _hash: Any = _domain_hash,
    _sequence: Any = _sequence_root,
    _sha_validator: Any = _is_sha256,
    _descriptor_validator: Any = _validate_embedded_descriptor,
    _error: Any = StaticCensusClosureError,
) -> Dict[str, Any]:
    if (
        _EXPECTED_SETUP_COUNT != _expected_count
        or _EXPECTED_SETUP_ORBIT_TABLE_ROOT != _expected_root
        or _D4_NAMES is not _d4_names
        or _COUNT_PAIRS is not _count_pairs
        or _BOARD is not _board
        or _FIXED_SETUP_COUNTS is not _fixed_setup_counts
        or _STABILIZER_SIGNATURES is not _signatures
        or _SETUP_ORBIT_COUNTS is not _orbit_counts
        or _SETUP_WEIGHT_HISTOGRAMS is not _weight_histograms
        or _COUNT_PAIR_SUPPLIES is not _count_pair_supplies
        or _TYPED_SETUP_HASH_DOMAIN is not _setup_hash_domain
        or _SETUP_DESCRIPTOR_DOMAIN is not _descriptor_domain
        or _ORDERED_SETUP_ROOT_DOMAIN is not _ordered_setup_domain
        or _SETUP_IMAGE_ROOT_DOMAIN is not _image_domain
        or _SETUP_GROUP_MAPPING_ROOT_DOMAIN is not _mapping_domain
        or _SETUP_GROUP_REPRESENTATIVE_ROOT_DOMAIN is not _representative_domain
        or _canonical_json is not _canonical
        or _domain_hash is not _hash
        or _sequence_root is not _sequence
        or _is_sha256 is not _sha_validator
        or _validate_embedded_descriptor is not _descriptor_validator
        or StaticCensusClosureError is not _error
    ):
        raise _error("setup descriptor binding changed")
    if type(rows) is not tuple or len(rows) != _expected_count:
        raise TypeError("setup table rows changed type or length")
    if type(partitions) is not tuple or len(partitions) != 5:
        raise TypeError("setup table partitions changed type or length")

    fixed_counts = [0] * len(_d4_names)
    ordered_setup_values: List[str] = []
    image_values: List[str] = []
    group_mapping_values: List[str] = []
    for expected_ordinal, row in enumerate(rows):
        if type(row) is not tuple or len(row) != 7:
            raise TypeError("setup table row changed shape")
        ordinal, count_index, positions_a, positions_b, canonical, identity, images = row
        if (
            type(ordinal) is not int
            or ordinal != expected_ordinal
            or type(count_index) is not int
            or not 0 <= count_index < len(_count_pairs)
            or type(positions_a) is not tuple
            or type(positions_b) is not tuple
            or type(canonical) is not str
            or not _sha_validator(identity)
            or type(images) is not tuple
            or len(images) != len(_d4_names)
            or any(type(value) is not int or not 0 <= value < len(rows) for value in images)
        ):
            raise TypeError("setup table row changed type")
        for positions in (positions_a, positions_b):
            if any(
                type(position) is not tuple
                or len(position) != 2
                or any(type(item) is not int for item in position)
                or position not in _board
                for position in positions
            ):
                raise TypeError("setup table positions changed type")
            if positions != tuple(sorted(positions)) or len(set(positions)) != len(positions):
                raise ValueError("setup table positions lost canonical order")
        if set(positions_a).intersection(positions_b):
            raise ValueError("setup table positions became non-disjoint")
        if (len(positions_a), len(positions_b)) != _count_pairs[count_index]:
            raise ValueError("setup table count pair changed")
        expected_payload = {
            "setup_version": 1,
            "positions": {
                "A": [list(position) for position in positions_a],
                "B": [list(position) for position in positions_b],
            },
        }
        if canonical != _canonical(expected_payload):
            raise ValueError("setup table canonical JSON changed")
        if identity != _hash(_setup_hash_domain, canonical):
            raise ValueError("setup table identity changed")
        if images[0] != ordinal:
            raise ValueError("identity transform changed a setup ordinal")
        for transform_index, image_ordinal in enumerate(images):
            if image_ordinal == ordinal:
                fixed_counts[transform_index] += 1
        ordered_setup_values.append(canonical)
        image_values.append(
            _canonical(
                {
                    "ordinal": ordinal,
                    "setup_hash": identity,
                    "image_ordinals": list(images),
                }
            )
        )

    if tuple(fixed_counts) != _fixed_setup_counts:
        raise _error("setup fixed-point counts changed")

    groups: List[Dict[str, Any]] = []
    for group_index, partition in enumerate(partitions):
        if type(partition) is not tuple or len(partition) != 3:
            raise TypeError("setup partition changed shape")
        signature, raw_to_representative, representatives = partition
        if (
            type(signature) is not tuple
            or any(type(name) is not str for name in signature)
            or signature != _signatures[group_index]
            or type(raw_to_representative) is not tuple
            or len(raw_to_representative) != len(rows)
            or type(representatives) is not tuple
        ):
            raise ValueError("setup partition changed authority")
        for record in representatives:
            if (
                type(record) is not tuple
                or len(record) != 2
                or type(record[0]) is not int
                or not 0 <= record[0] < len(rows)
                or type(record[1]) is not int
                or record[1] not in (1, 2, 4, 8)
            ):
                raise TypeError("setup representative record changed type")
        transform_indexes = tuple(_d4_names.index(name) for name in signature)
        representative_records: List[str] = []
        histogram: Dict[int, int] = {}
        seen_representatives = set()
        for ordinal, representative in enumerate(raw_to_representative):
            if type(representative) is not int or not 0 <= representative < len(rows):
                raise TypeError("setup representative ordinal changed type")
            images = {rows[ordinal][6][index] for index in transform_indexes}
            expected = min(images, key=lambda value: rows[value][4].encode("utf-8"))
            if representative != expected:
                raise ValueError("setup representative is not the byte minimum")
            seen_representatives.add(representative)
            group_mapping_values.append(
                _canonical(
                    {
                        "group_index": group_index,
                        "raw_ordinal": ordinal,
                        "representative_ordinal": representative,
                    }
                )
            )
        expected_representatives = []
        for representative in sorted(seen_representatives):
            images = {
                rows[representative][6][index] for index in transform_indexes
            }
            weight = len(images)
            expected_representatives.append((representative, weight))
            histogram[weight] = histogram.get(weight, 0) + 1
            representative_records.append(
                _canonical(
                    {
                        "representative_ordinal": representative,
                        "representative_setup_hash": rows[representative][5],
                        "orbit_weight": weight,
                    }
                )
            )
        if representatives != tuple(expected_representatives):
            raise ValueError("setup representative records changed")
        if (
            len(representatives) != _orbit_counts[group_index]
            or tuple(sorted(histogram.items()))
            != _weight_histograms[group_index]
            or sum(weight for _, weight in representatives) != len(rows)
        ):
            raise _error("setup partition arithmetic changed")
        groups.append(
            {
                "signature": list(signature),
                "setup_orbit_count": len(representatives),
                "weighted_setup_count": sum(weight for _, weight in representatives),
                "weight_histogram": {
                    str(weight): count for weight, count in sorted(histogram.items())
                },
                "ordered_representative_root": _sequence(
                    _representative_domain
                    + group_index.to_bytes(1, "big"),
                    representative_records,
                ),
            }
        )

    body = {
        "setup_orbit_table_version": 1,
        "board": {"rows": 3, "columns": 3, "cell_order": [list(p) for p in _board]},
        "count_pair_order": [list(pair) for pair in _count_pairs],
        "count_pair_supplies": list(_count_pair_supplies),
        "setup_count": len(rows),
        "d4_order": list(_d4_names),
        "fixed_setup_counts": {
            name: fixed_counts[index] for index, name in enumerate(_d4_names)
        },
        "groups": groups,
        "roots": {
            "ordered_setup_root": _sequence(
                _ordered_setup_domain, ordered_setup_values
            ),
            "ordered_d4_image_ordinal_root": _sequence(
                _image_domain, image_values
            ),
            "ordered_group_mapping_root": _sequence(
                _mapping_domain, group_mapping_values
            ),
        },
    }
    result = dict(body)
    result["descriptor_root"] = _hash(
        _descriptor_domain, _canonical(body)
    )
    return _descriptor_validator(
        result,
        "setup table descriptor",
        _descriptor_domain,
        _expected_root,
    )


@dataclass(frozen=True, init=False)
class SetupOrbitTableV1:
    """One strict reusable immutable table for all five setup quotients."""

    table_version: int
    _rows: Tuple[_SetupRow, ...]
    _partitions: Tuple[_SetupPartition, ...]
    _descriptor_json: str
    _construction_snapshot: str

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("SetupOrbitTableV1 values are created only by the builder")


def _make_setup_table(
    rows: Tuple[_SetupRow, ...],
    partitions: Tuple[_SetupPartition, ...],
    descriptor_json: str,
    _table_type: Any = SetupOrbitTableV1,
    _loads: Any = json.loads,
    _exact: Any = _exact_dict,
    _descriptor_validator: Any = _validate_embedded_descriptor,
    _descriptor_domain: bytes = _SETUP_DESCRIPTOR_DOMAIN,
    _expected_root: str = _EXPECTED_SETUP_ORBIT_TABLE_ROOT,
    _error: Any = StaticCensusClosureError,
) -> SetupOrbitTableV1:
    if (
        SetupOrbitTableV1 is not _table_type
        or json.loads is not _loads
        or _exact_dict is not _exact
        or _validate_embedded_descriptor is not _descriptor_validator
        or _SETUP_DESCRIPTOR_DOMAIN is not _descriptor_domain
        or _EXPECTED_SETUP_ORBIT_TABLE_ROOT != _expected_root
        or StaticCensusClosureError is not _error
    ):
        raise _error("setup table maker binding changed")
    descriptor = _descriptor_validator(
        _exact(_loads(descriptor_json), "setup table descriptor"),
        "setup table descriptor",
        _descriptor_domain,
        _expected_root,
    )
    descriptor_root = descriptor.get("descriptor_root")
    value = object.__new__(_table_type)
    object.__setattr__(value, "table_version", 1)
    object.__setattr__(value, "_rows", rows)
    object.__setattr__(value, "_partitions", partitions)
    object.__setattr__(value, "_descriptor_json", descriptor_json)
    object.__setattr__(value, "_construction_snapshot", descriptor_root)
    return value


def _normalize_setup_table(
    value: Any,
    _table_type: Any = SetupOrbitTableV1,
    _fields: Any = _require_exact_fields,
    _descriptor: Any = _setup_descriptor_from_material,
    _descriptor_validator: Any = _validate_embedded_descriptor,
    _descriptor_domain: bytes = _SETUP_DESCRIPTOR_DOMAIN,
    _expected_root: str = _EXPECTED_SETUP_ORBIT_TABLE_ROOT,
    _canonical: Any = _canonical_json,
    _make: Any = _make_setup_table,
    _error: Any = StaticCensusClosureError,
) -> SetupOrbitTableV1:
    if (
        SetupOrbitTableV1 is not _table_type
        or _require_exact_fields is not _fields
        or _setup_descriptor_from_material is not _descriptor
        or _validate_embedded_descriptor is not _descriptor_validator
        or _SETUP_DESCRIPTOR_DOMAIN is not _descriptor_domain
        or _EXPECTED_SETUP_ORBIT_TABLE_ROOT != _expected_root
        or _canonical_json is not _canonical
        or _make_setup_table is not _make
        or StaticCensusClosureError is not _error
    ):
        raise _error("setup table normalizer binding changed")
    if type(value) is not _table_type:
        raise TypeError("setup table must be a SetupOrbitTableV1")
    fields = (
        "table_version",
        "_rows",
        "_partitions",
        "_descriptor_json",
        "_construction_snapshot",
    )
    _fields(value, fields, "setup orbit table")
    snapshot = vars(value).copy()
    if type(snapshot) is not dict or set(snapshot) != set(fields):
        raise TypeError("setup orbit table snapshot changed")
    if type(snapshot["table_version"]) is not int or snapshot["table_version"] != 1:
        raise ValueError("setup orbit table version changed")
    descriptor = _descriptor(
        snapshot["_rows"], snapshot["_partitions"]
    )
    _descriptor_validator(
        descriptor,
        "setup table descriptor",
        _descriptor_domain,
        _expected_root,
    )
    descriptor_json = _canonical(descriptor)
    descriptor_root = descriptor["descriptor_root"]
    if (
        type(snapshot["_descriptor_json"]) is not str
        or snapshot["_descriptor_json"] != descriptor_json
        or type(snapshot["_construction_snapshot"]) is not str
        or snapshot["_construction_snapshot"] != descriptor_root
        or (
            _expected_root
            and descriptor_root != _expected_root
        )
    ):
        raise ValueError("setup orbit table changed after construction")
    return _make(
        snapshot["_rows"], snapshot["_partitions"], descriptor_json
    )


def build_setup_orbit_table_v1(
    _version: Any = _official_version,
    _build: Any = _build_setup_material,
    _descriptor: Any = _setup_descriptor_from_material,
    _canonical: Any = _canonical_json,
    _make: Any = _make_setup_table,
    _error: Any = StaticCensusClosureError,
) -> SetupOrbitTableV1:
    """Reconstruct the complete strict 6,798-row reusable setup table."""

    if (
        _official_version is not _version
        or _build_setup_material is not _build
        or _setup_descriptor_from_material is not _descriptor
        or _canonical_json is not _canonical
        or _make_setup_table is not _make
        or StaticCensusClosureError is not _error
    ):
        raise _error("setup table builder binding changed")
    _version()
    rows, partitions = _build()
    descriptor_json = _canonical(_descriptor(rows, partitions))
    return _make(rows, partitions, descriptor_json)


def setup_orbit_table_descriptor_v1(
    table: SetupOrbitTableV1,
    _normalize: Any = _normalize_setup_table,
    _loads: Any = json.loads,
    _error: Any = StaticCensusClosureError,
) -> Dict[str, Any]:
    """Return the compact detached descriptor; raw rows remain process-local."""

    if (
        _normalize_setup_table is not _normalize
        or json.loads is not _loads
        or StaticCensusClosureError is not _error
    ):
        raise _error("setup table descriptor binding changed")
    source = _normalize(table)
    return _loads(source._descriptor_json)


def setup_orbit_table_hash_v1(
    table: SetupOrbitTableV1,
    _normalize: Any = _normalize_setup_table,
    _error: Any = StaticCensusClosureError,
) -> str:
    """Return the fixed descriptor identity of the complete setup table."""

    if (
        _normalize_setup_table is not _normalize
        or StaticCensusClosureError is not _error
    ):
        raise _error("setup table hash binding changed")
    return _normalize(table)._construction_snapshot


# Private immutable skeleton row:
# ordinal, canonical JSON, ordered hash, role-neutral skeleton hash,
# role-neutral semantic hash, exact stabilizer tuple, setup orbit count, and
# per-skeleton setup weight histogram.
_SkeletonRow = Tuple[Any, ...]


def _universe_fresh_root(
    canonical_values: Tuple[str, ...],
    _sha256: Any = hashlib.sha256,
    _domain: bytes = _UNIVERSE_FRESH_ROOT_DOMAIN,
    _error: Any = StaticCensusClosureError,
) -> str:
    if (
        hashlib.sha256 is not _sha256
        or _UNIVERSE_FRESH_ROOT_DOMAIN is not _domain
        or StaticCensusClosureError is not _error
    ):
        raise _error("fresh-skeleton root binding changed")
    digest = _sha256(_domain)
    digest.update(len(canonical_values).to_bytes(8, "big"))
    for ordinal, canonical in enumerate(canonical_values):
        encoded = canonical.encode("utf-8")
        digest.update(ordinal.to_bytes(8, "big"))
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


_EDGE_NAMES: Tuple[str, str, str, str] = (
    "TOP",
    "RIGHT",
    "BOTTOM",
    "LEFT",
)
_OLD_SEMANTIC_SPECS: Tuple[Tuple[str, str, str, str], ...] = (
    ("PUSH", "REACH_EDGE", "HOP", "REACH_EDGE"),
    ("SWAP", "CONNECT_EDGES", "HOP", "REACH_EDGE"),
    ("CONVERT", "CONNECT_EDGES", "PUSH", "REACH_EDGE"),
    ("MOVE_CAPTURE", "ELIMINATE", "HOP", "REACH_EDGE"),
    ("CONVERT", "ELIMINATE", "MOVE_CAPTURE", "ELIMINATE"),
    ("PUSH", "CONNECT_EDGES", "SWAP", "CONNECT_EDGES"),
)


def _transformed_edge_name(
    edge: str,
    transform: str,
    _edge_names: Tuple[str, ...] = _EDGE_NAMES,
    _d4_names: Tuple[str, ...] = _D4_NAMES,
    _error: Any = StaticCensusClosureError,
) -> str:
    if (
        _EDGE_NAMES is not _edge_names
        or _D4_NAMES is not _d4_names
        or StaticCensusClosureError is not _error
    ):
        raise _error("skeleton edge-transform binding changed")
    if edge not in _edge_names or transform not in _d4_names:
        raise _error("skeleton edge transform escaped its vocabulary")
    index = _edge_names.index(edge)
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
    else:
        target = (1 - index) % 4
    return _edge_names[target]


def _transformed_skeleton_canonical(
    canonical: str,
    transform: str,
    role_swapped: bool = False,
    _d4_names: Tuple[str, ...] = _D4_NAMES,
    _owners: Tuple[str, ...] = _FIRST_PLAYERS,
    _loads: Any = json.loads,
    _exact: Any = _exact_dict,
    _keys: Any = _exact_keys,
    _edge: Any = _transformed_edge_name,
    _canonical: Any = _canonical_json,
    _error: Any = StaticCensusClosureError,
) -> str:
    """Apply the fixed D4/complete-swap action directly to sealed JSON bytes."""

    if (
        _D4_NAMES is not _d4_names
        or _FIRST_PLAYERS is not _owners
        or json.loads is not _loads
        or _exact_dict is not _exact
        or _exact_keys is not _keys
        or _transformed_edge_name is not _edge
        or _canonical_json is not _canonical
        or StaticCensusClosureError is not _error
    ):
        raise _error("canonical skeleton transform binding changed")
    if type(canonical) is not str or transform not in _d4_names:
        raise TypeError("canonical skeleton transform input changed")
    payload = _exact(_loads(canonical), "canonical skeleton")
    if _canonical(payload) != canonical:
        raise ValueError("canonical skeleton bytes changed")
    roles = _exact(payload.get("roles"), "canonical skeleton roles")
    _keys(roles, _owners, "canonical skeleton roles")
    if role_swapped:
        roles["A"], roles["B"] = roles["B"], roles["A"]
    for owner in _owners:
        role = _exact(roles[owner], "canonical skeleton role")
        edges = role.get("target_edges")
        if type(edges) is not list or any(type(edge) is not str for edge in edges):
            raise TypeError("canonical skeleton target edges changed")
        transformed = tuple(
            _edge(edge, transform) for edge in edges
        )
        goal = role.get("goal_primitive")
        if goal == "CONNECT_EDGES":
            edge_set = frozenset(transformed)
            if edge_set == frozenset(("TOP", "BOTTOM")):
                transformed = ("TOP", "BOTTOM")
            elif edge_set == frozenset(("RIGHT", "LEFT")):
                transformed = ("RIGHT", "LEFT")
            else:
                raise _error("CONNECT target lost its opposite axis")
        elif goal == "REACH_EDGE":
            if len(transformed) != 1:
                raise _error("REACH target changed arity")
        elif goal == "ELIMINATE":
            if transformed:
                raise _error("ELIMINATE acquired a target edge")
        else:
            raise _error("skeleton goal escaped its vocabulary")
        role["target_edges"] = list(transformed)
    return _canonical(payload)


def _canonical_stabilizer(
    canonical: str,
    _d4_names: Tuple[str, ...] = _D4_NAMES,
    _transform: Any = _transformed_skeleton_canonical,
    _error: Any = StaticCensusClosureError,
) -> StabilizerSignature:
    if (
        _D4_NAMES is not _d4_names
        or _transformed_skeleton_canonical is not _transform
        or StaticCensusClosureError is not _error
    ):
        raise _error("canonical stabilizer binding changed")
    return tuple(
        transform
        for transform in _d4_names
        if _transform(canonical, transform) == canonical
    )


def _canonical_self_isomorphic(
    canonical: str,
    _d4_names: Tuple[str, ...] = _D4_NAMES,
    _transform: Any = _transformed_skeleton_canonical,
    _error: Any = StaticCensusClosureError,
) -> bool:
    if (
        _D4_NAMES is not _d4_names
        or _transformed_skeleton_canonical is not _transform
        or StaticCensusClosureError is not _error
    ):
        raise _error("self-isomorphism binding changed")
    return any(
        _transform(canonical, transform, True) == canonical
        for transform in _d4_names
    )


def _canonical_old_region(
    canonical: str,
    _loads: Any = json.loads,
    _exact: Any = _exact_dict,
    _old_specs: Tuple[Tuple[str, str, str, str], ...] = _OLD_SEMANTIC_SPECS,
    _error: Any = StaticCensusClosureError,
) -> bool:
    if (
        json.loads is not _loads
        or _exact_dict is not _exact
        or _OLD_SEMANTIC_SPECS is not _old_specs
        or StaticCensusClosureError is not _error
    ):
        raise _error("old-region binding changed")
    payload = _exact(_loads(canonical), "canonical skeleton")
    roles = _exact(payload.get("roles"), "canonical skeleton roles")
    program = (
        roles["A"]["action_primitive"],
        roles["A"]["goal_primitive"],
        roles["B"]["action_primitive"],
        roles["B"]["goal_primitive"],
    )
    reverse = (program[2], program[3], program[0], program[1])
    return program in _old_specs or reverse in _old_specs


def _canonical_role_neutral_semantic_hash(
    canonical: str,
    _loads: Any = json.loads,
    _exact: Any = _exact_dict,
    _owners: Tuple[str, ...] = _FIRST_PLAYERS,
    _canonical: Any = _canonical_json,
    _hash: Any = _domain_hash,
    _domain: bytes = _ROLE_NEUTRAL_SEMANTIC_HASH_DOMAIN,
    _error: Any = StaticCensusClosureError,
) -> str:
    if (
        json.loads is not _loads
        or _exact_dict is not _exact
        or _FIRST_PLAYERS is not _owners
        or _canonical_json is not _canonical
        or _domain_hash is not _hash
        or _ROLE_NEUTRAL_SEMANTIC_HASH_DOMAIN is not _domain
        or StaticCensusClosureError is not _error
    ):
        raise _error("role-neutral semantic binding changed")
    payload = _exact(_loads(canonical), "canonical skeleton")
    roles = _exact(payload.get("roles"), "canonical skeleton roles")
    role_payloads = {
        owner: {
            "action_primitive": roles[owner]["action_primitive"],
            "goal_primitive": roles[owner]["goal_primitive"],
        }
        for owner in _owners
    }
    ordered = {
        "universe_version": payload.get("universe_version"),
        "roles": role_payloads,
    }
    swapped = {
        "universe_version": payload.get("universe_version"),
        "roles": {"A": role_payloads["B"], "B": role_payloads["A"]},
    }
    neutral = min(_canonical(ordered), _canonical(swapped))
    return _hash(_domain, neutral)


def _exact_stabilizer(
    skeleton: universe.ProfiledSkeleton,
    d4_members: Tuple[Any, ...],
    transform_skeleton: Any,
    skeleton_json: Any,
    _d4_names: Tuple[str, ...] = _D4_NAMES,
    _expected_transform: Any = universe.transform_profiled_skeleton,
    _stabilizer: Any = _canonical_stabilizer,
    _error: Any = StaticCensusClosureError,
) -> StabilizerSignature:
    if (
        _D4_NAMES is not _d4_names
        or universe.transform_profiled_skeleton is not _expected_transform
        or _canonical_stabilizer is not _stabilizer
        or StaticCensusClosureError is not _error
    ):
        raise _error("exact stabilizer binding changed")
    canonical = skeleton_json(skeleton)
    if tuple(transform.value for transform in d4_members) != _d4_names:
        raise _error("D4 skeleton transform order changed")
    if transform_skeleton is not _expected_transform:
        raise _error("skeleton transform authority changed")
    signature = _stabilizer(canonical)
    if not signature or signature[0] != "I":
        raise _error("skeleton stabilizer lost the identity")
    return signature


def _setup_orbit_count_for_stabilizer(
    signature: StabilizerSignature,
    _d4_names: Tuple[str, ...] = _D4_NAMES,
    _fixed_counts: Tuple[int, ...] = _FIXED_SETUP_COUNTS,
    _error: Any = StaticCensusClosureError,
) -> int:
    if (
        _D4_NAMES is not _d4_names
        or _FIXED_SETUP_COUNTS is not _fixed_counts
        or StaticCensusClosureError is not _error
    ):
        raise _error("setup-orbit quotient binding changed")
    if (
        type(signature) is not tuple
        or not signature
        or any(type(name) is not str or name not in _d4_names for name in signature)
        or tuple(name for name in _d4_names if name in signature) != signature
    ):
        raise _error("invalid exact stabilizer signature")
    numerator = sum(
        _fixed_counts[_d4_names.index(name)] for name in signature
    )
    if numerator % len(signature):
        raise _error("Burnside setup quotient is not integral")
    return numerator // len(signature)


def _skeleton_authority_descriptor(
    rows: Tuple[_SkeletonRow, ...],
    all_contribution: int,
    self_contribution: int,
    old_contribution: int,
    _expected_count: int = _EXPECTED_SKELETON_COUNT,
    _expected_setup_count: int = _EXPECTED_SETUP_COUNT,
    _expected_factorized_count: int = _EXPECTED_FACTORIZED_CARRIER_COUNT,
    _expected_labeled_count: int = _EXPECTED_LABELED_SETUP_COUNT,
    _expected_all_contribution: int = _EXPECTED_ALL_ORDERED_CONTRIBUTION,
    _expected_self_contribution: int = _EXPECTED_SELF_ISOMORPHIC_CONTRIBUTION,
    _expected_old_contribution: int = _EXPECTED_OLD_REGION_CONTRIBUTION,
    _expected_universe_root: str = _EXPECTED_UNIVERSE_DESCRIPTOR_ROOT,
    _expected_fresh_root: str = _EXPECTED_FRESH_SKELETON_ROOT,
    _expected_root: str = _EXPECTED_SKELETON_AUTHORITY_ROOT,
    _d4_names: Tuple[str, ...] = _D4_NAMES,
    _signatures: Tuple[StabilizerSignature, ...] = _STABILIZER_SIGNATURES,
    _stabilizer_counts: Tuple[int, ...] = _STABILIZER_SKELETON_COUNTS,
    _orbit_counts: Tuple[int, ...] = _SETUP_ORBIT_COUNTS,
    _weight_histograms: Tuple[Tuple[Tuple[int, int], ...], ...] = _SETUP_WEIGHT_HISTOGRAMS,
    _global_histogram: Tuple[Tuple[int, int], ...] = _GLOBAL_WEIGHT_HISTOGRAM,
    _authority_domain: bytes = _SKELETON_AUTHORITY_ROOT_DOMAIN,
    _descriptor_domain: bytes = _SKELETON_DESCRIPTOR_ROOT_DOMAIN,
    _canonical: Any = _canonical_json,
    _hash: Any = _domain_hash,
    _sequence: Any = _sequence_root,
    _sha_validator: Any = _is_sha256,
    _descriptor_validator: Any = _validate_embedded_descriptor,
    _error: Any = StaticCensusClosureError,
) -> Dict[str, Any]:
    if (
        _EXPECTED_SKELETON_COUNT != _expected_count
        or _EXPECTED_SETUP_COUNT != _expected_setup_count
        or _EXPECTED_FACTORIZED_CARRIER_COUNT != _expected_factorized_count
        or _EXPECTED_LABELED_SETUP_COUNT != _expected_labeled_count
        or _EXPECTED_ALL_ORDERED_CONTRIBUTION != _expected_all_contribution
        or _EXPECTED_SELF_ISOMORPHIC_CONTRIBUTION != _expected_self_contribution
        or _EXPECTED_OLD_REGION_CONTRIBUTION != _expected_old_contribution
        or _EXPECTED_UNIVERSE_DESCRIPTOR_ROOT != _expected_universe_root
        or _EXPECTED_FRESH_SKELETON_ROOT != _expected_fresh_root
        or _EXPECTED_SKELETON_AUTHORITY_ROOT != _expected_root
        or _D4_NAMES is not _d4_names
        or _STABILIZER_SIGNATURES is not _signatures
        or _STABILIZER_SKELETON_COUNTS is not _stabilizer_counts
        or _SETUP_ORBIT_COUNTS is not _orbit_counts
        or _SETUP_WEIGHT_HISTOGRAMS is not _weight_histograms
        or _GLOBAL_WEIGHT_HISTOGRAM is not _global_histogram
        or _SKELETON_AUTHORITY_ROOT_DOMAIN is not _authority_domain
        or _SKELETON_DESCRIPTOR_ROOT_DOMAIN is not _descriptor_domain
        or _canonical_json is not _canonical
        or _domain_hash is not _hash
        or _sequence_root is not _sequence
        or _is_sha256 is not _sha_validator
        or _validate_embedded_descriptor is not _descriptor_validator
        or StaticCensusClosureError is not _error
    ):
        raise _error("skeleton authority descriptor binding changed")
    if type(rows) is not tuple or len(rows) != _expected_count:
        raise TypeError("skeleton authority rows changed type or length")
    values: List[str] = []
    stabilizer_counts: Dict[StabilizerSignature, int] = {}
    factorized_count = 0
    weighted_count = 0
    global_weight_bins: Dict[int, int] = {}
    previous_json: Optional[str] = None
    for expected_ordinal, row in enumerate(rows):
        if type(row) is not tuple or len(row) != 8:
            raise TypeError("skeleton authority row changed shape")
        (
            ordinal,
            canonical,
            skeleton_hash,
            neutral_hash,
            semantic_hash,
            stabilizer,
            orbit_count,
            weight_histogram,
        ) = row
        if (
            type(ordinal) is not int
            or ordinal != expected_ordinal
            or type(canonical) is not str
            or not _sha_validator(skeleton_hash)
            or not _sha_validator(neutral_hash)
            or not _sha_validator(semantic_hash)
            or type(stabilizer) is not tuple
            or any(type(name) is not str for name in stabilizer)
            or stabilizer not in _signatures
            or type(orbit_count) is not int
            or type(weight_histogram) is not tuple
            or any(
                type(record) is not tuple
                or len(record) != 2
                or type(record[0]) is not int
                or record[0] not in (1, 2, 4, 8)
                or type(record[1]) is not int
                or record[1] <= 0
                for record in weight_histogram
            )
        ):
            raise TypeError("skeleton authority row changed type")
        group_index = _signatures.index(stabilizer)
        if (
            orbit_count != _orbit_counts[group_index]
            or weight_histogram != _weight_histograms[group_index]
            or sum(count for _, count in weight_histogram) != orbit_count
            or sum(weight * count for weight, count in weight_histogram)
            != _expected_setup_count
        ):
            raise _error("skeleton setup quotient changed")
        if previous_json is not None and canonical <= previous_json:
            raise ValueError("skeleton authority order is not strictly canonical")
        previous_json = canonical
        stabilizer_counts[stabilizer] = stabilizer_counts.get(stabilizer, 0) + 1
        factorized_count += orbit_count
        weighted_count += _expected_setup_count
        for weight, count in weight_histogram:
            global_weight_bins[weight] = global_weight_bins.get(weight, 0) + count
        values.append(
            _canonical(
                {
                    "skeleton_ordinal": ordinal,
                    "skeleton_json": canonical,
                    "typed_skeleton_hash": skeleton_hash,
                    "role_neutral_skeleton_hash": neutral_hash,
                    "role_neutral_semantic_hash": semantic_hash,
                    "exact_stabilizer": list(stabilizer),
                    "setup_orbit_count": orbit_count,
                    "setup_weight_histogram": {
                        str(weight): count for weight, count in weight_histogram
                    },
                }
            )
        )
    observed_stabilizer_counts = tuple(
        stabilizer_counts.get(signature, 0)
        for signature in _signatures
    )
    if observed_stabilizer_counts != _stabilizer_counts:
        raise _error("exact skeleton stabilizer counts changed")
    if (
        factorized_count != _expected_factorized_count
        or weighted_count != _expected_labeled_count
        or tuple(sorted(global_weight_bins.items())) != _global_histogram
        or all_contribution != _expected_all_contribution
        or self_contribution != _expected_self_contribution
        or old_contribution != _expected_old_contribution
        or (all_contribution - self_contribution - old_contribution) % 2
        or (all_contribution - self_contribution - old_contribution) // 2
        != factorized_count
    ):
        raise _error("dual setup-carrier arithmetic changed")
    body = {
        "skeleton_authority_version": 1,
        "universe_descriptor_root": _expected_universe_root,
        "fresh_canonical_skeleton_root": _expected_fresh_root,
        "skeleton_count": len(rows),
        "d4_order": list(_d4_names),
        "exact_stabilizer_groups": [
            {
                "signature": list(signature),
                "skeleton_count": stabilizer_counts[signature],
                "setup_orbit_count_per_skeleton": _orbit_counts[index],
                "setup_weight_histogram_per_skeleton": {
                    str(weight): count
                    for weight, count in _weight_histograms[index]
                },
            }
            for index, signature in enumerate(_signatures)
        ],
        "factorized_carrier_count": factorized_count,
        "labeled_setup_count": weighted_count,
        "paired_first_player_member_count": 2 * weighted_count,
        "global_weight_histogram": {
            str(weight): count for weight, count in sorted(global_weight_bins.items())
        },
        "independent_ordered_population_derivation": {
            "all_ordered_contribution": all_contribution,
            "self_isomorphic_contribution": self_contribution,
            "old_region_contribution": old_contribution,
            "fresh_cross_section_divisor": 2,
            "fresh_factorized_carrier_count": (
                all_contribution - self_contribution - old_contribution
            )
            // 2,
        },
        "ordered_skeleton_authority_root": _sequence(
            _authority_domain, values
        ),
    }
    result = dict(body)
    result["descriptor_root"] = _hash(
        _descriptor_domain,
        _canonical(body),
    )
    return _descriptor_validator(
        result,
        "skeleton authority descriptor",
        _descriptor_domain,
        _expected_root,
    )


def _build_skeleton_authority(
    _api: Any = _api_guard,
    _stabilizer: Any = _canonical_stabilizer,
    _orbit_count: Any = _setup_orbit_count_for_stabilizer,
    _self_isomorphic: Any = _canonical_self_isomorphic,
    _old_region: Any = _canonical_old_region,
    _transform_canonical: Any = _transformed_skeleton_canonical,
    _fresh_root: Any = _universe_fresh_root,
    _hash: Any = _domain_hash,
    _semantic_hash: Any = _canonical_role_neutral_semantic_hash,
    _descriptor: Any = _skeleton_authority_descriptor,
    _canonical: Any = _canonical_json,
    _d4_names: Tuple[str, ...] = _D4_NAMES,
    _signatures: Tuple[StabilizerSignature, ...] = _STABILIZER_SIGNATURES,
    _orbit_counts: Tuple[int, ...] = _SETUP_ORBIT_COUNTS,
    _weight_histograms: Tuple[Tuple[Tuple[int, int], ...], ...] = _SETUP_WEIGHT_HISTOGRAMS,
    _expected_count: int = _EXPECTED_SKELETON_COUNT,
    _expected_fresh_root: str = _EXPECTED_FRESH_SKELETON_ROOT,
    _expected_root: str = _EXPECTED_SKELETON_AUTHORITY_ROOT,
    _profiled_domain: bytes = _PROFILED_SKELETON_HASH_DOMAIN,
    _neutral_domain: bytes = _ROLE_NEUTRAL_SKELETON_HASH_DOMAIN,
    _universe_module: Any = universe,
    _expected_is_self: Any = universe.is_role_swap_d4_self_isomorphic,
    _expected_transform: Any = universe.transform_profiled_skeleton,
    _expected_enumerate_fresh: Any = universe.enumerate_fresh_canonical_profiled_skeletons,
    _expected_is_old: Any = universe.is_plan0013_profiled_region,
    _expected_skeleton_hash: Any = universe.profiled_skeleton_hash,
    _expected_neutral_hash: Any = universe.role_neutral_profiled_skeleton_hash,
    _expected_semantic_hash: Any = universe.role_neutral_semantic_hash,
    _error: Any = StaticCensusClosureError,
) -> Tuple[Tuple[_SkeletonRow, ...], str]:
    if (
        _api_guard is not _api
        or _canonical_stabilizer is not _stabilizer
        or _setup_orbit_count_for_stabilizer is not _orbit_count
        or _canonical_self_isomorphic is not _self_isomorphic
        or _canonical_old_region is not _old_region
        or _transformed_skeleton_canonical is not _transform_canonical
        or _universe_fresh_root is not _fresh_root
        or _domain_hash is not _hash
        or _canonical_role_neutral_semantic_hash is not _semantic_hash
        or _skeleton_authority_descriptor is not _descriptor
        or _canonical_json is not _canonical
        or _D4_NAMES is not _d4_names
        or _STABILIZER_SIGNATURES is not _signatures
        or _SETUP_ORBIT_COUNTS is not _orbit_counts
        or _SETUP_WEIGHT_HISTOGRAMS is not _weight_histograms
        or _EXPECTED_SKELETON_COUNT != _expected_count
        or _EXPECTED_FRESH_SKELETON_ROOT != _expected_fresh_root
        or _EXPECTED_SKELETON_AUTHORITY_ROOT != _expected_root
        or _PROFILED_SKELETON_HASH_DOMAIN is not _profiled_domain
        or _ROLE_NEUTRAL_SKELETON_HASH_DOMAIN is not _neutral_domain
        or universe is not _universe_module
        or universe.is_role_swap_d4_self_isomorphic is not _expected_is_self
        or universe.transform_profiled_skeleton is not _expected_transform
        or universe.enumerate_fresh_canonical_profiled_skeletons
        is not _expected_enumerate_fresh
        or universe.is_plan0013_profiled_region is not _expected_is_old
        or universe.profiled_skeleton_hash is not _expected_skeleton_hash
        or universe.role_neutral_profiled_skeleton_hash is not _expected_neutral_hash
        or universe.role_neutral_semantic_hash is not _expected_semantic_hash
        or StaticCensusClosureError is not _error
    ):
        raise _error("skeleton authority builder binding changed")
    api = _api()
    d4_members = api[7]
    enumerate_fresh = api[8]
    enumerate_all = api[9]
    is_self = api[10]
    is_old = api[11]
    transform_skeleton = api[12]
    skeleton_json = api[14]
    skeleton_hash = api[15]
    neutral_skeleton_hash = api[16]
    neutral_semantic_hash = api[17]

    all_contribution = 0
    self_contribution = 0
    old_contribution = 0
    overlap_count = 0
    fresh_canonical_values: Dict[str, None] = {}
    all_skeletons = enumerate_all()
    if type(all_skeletons) is not tuple or len(all_skeletons) != 3_300:
        raise _error("ordered skeleton enumeration changed")
    for skeleton in all_skeletons:
        canonical = skeleton_json(skeleton)
        stabilizer = _stabilizer(canonical)
        contribution = _orbit_count(stabilizer)
        all_contribution += contribution
        self_member = _self_isomorphic(canonical)
        old_member = _old_region(canonical)
        if self_member:
            self_contribution += contribution
        if old_member:
            old_contribution += contribution
        if self_member and old_member:
            overlap_count += 1
        if not self_member and not old_member:
            neutral_canonical = min(
                _transform_canonical(canonical, transform, swapped)
                for swapped in (False, True)
                for transform in _d4_names
            )
            fresh_canonical_values[neutral_canonical] = None
    canonical_values = tuple(sorted(fresh_canonical_values))
    if (
        len(canonical_values) != _expected_count
        or _fresh_root(canonical_values) != _expected_fresh_root
    ):
        raise _error("fresh skeleton sequence changed")

    rows: List[_SkeletonRow] = []
    for ordinal, canonical in enumerate(canonical_values):
        stabilizer = _stabilizer(canonical)
        if stabilizer not in _signatures:
            raise _error(
                "fresh canonical skeleton has an unregistered exact stabilizer"
            )
        group_index = _signatures.index(stabilizer)
        rows.append(
            (
                ordinal,
                canonical,
                _hash(_profiled_domain, canonical),
                _hash(_neutral_domain, canonical),
                _semantic_hash(canonical),
                stabilizer,
                _orbit_counts[group_index],
                _weight_histograms[group_index],
            )
        )
    if is_self is not _expected_is_self:
        raise _error("role-swap authority changed")
    if transform_skeleton is not _expected_transform:
        raise _error("skeleton transform authority changed")
    if tuple(transform.value for transform in d4_members) != _d4_names:
        raise _error("D4 skeleton transform order changed")
    if enumerate_fresh is not _expected_enumerate_fresh:
        raise _error("fresh skeleton enumeration authority changed")
    if is_old is not _expected_is_old:
        raise _error("old-region authority changed")
    if (
        skeleton_hash is not _expected_skeleton_hash
        or neutral_skeleton_hash is not _expected_neutral_hash
        or neutral_semantic_hash is not _expected_semantic_hash
    ):
        raise _error("skeleton identity authority changed")
    if overlap_count:
        raise _error(
            "self-isomorphic and old-region skeleton populations overlap"
        )

    frozen_rows = tuple(rows)
    descriptor = _descriptor(
        frozen_rows,
        all_contribution,
        self_contribution,
        old_contribution,
    )
    descriptor_json = _canonical(descriptor)
    if (
        _expected_root
        and descriptor["descriptor_root"] != _expected_root
    ):
        raise _error("skeleton authority root changed")
    return frozen_rows, descriptor_json


@dataclass(frozen=True, init=False)
class PreparedStaticCensusTableV1:
    """Process-local immutable union of setup and skeleton authorities.

    This is an operational acceleration token, not a serialized authority.  It
    has no parser and every public consumer reconstructs both committed compact
    descriptors from its immutable material before use.
    """

    table_version: int
    _setup_table: SetupOrbitTableV1
    _skeleton_rows: Tuple[_SkeletonRow, ...]
    _skeleton_descriptor_json: str
    _construction_snapshot: str

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError(
            "PreparedStaticCensusTableV1 values are created only by the preparer"
        )


def _prepared_table_snapshot(
    setup_root: str,
    skeleton_root: str,
    _domain: bytes = _PREPARED_CENSUS_TABLE_DOMAIN,
    _canonical: Any = _canonical_json,
    _hash: Any = _domain_hash,
    _error: Any = StaticCensusClosureError,
) -> str:
    if (
        _PREPARED_CENSUS_TABLE_DOMAIN is not _domain
        or _canonical_json is not _canonical
        or _domain_hash is not _hash
        or StaticCensusClosureError is not _error
    ):
        raise _error("prepared-table snapshot binding changed")
    return _hash(
        _domain,
        _canonical(
            {
                "prepared_static_census_table_version": 1,
                "setup_orbit_table_root": setup_root,
                "skeleton_authority_root": skeleton_root,
            }
        ),
    )


def _make_prepared_table(
    setup_table: SetupOrbitTableV1,
    skeleton_rows: Tuple[_SkeletonRow, ...],
    skeleton_descriptor_json: str,
    _table_type: Any = PreparedStaticCensusTableV1,
    _normalize_setup: Any = _normalize_setup_table,
    _loads: Any = json.loads,
    _exact: Any = _exact_dict,
    _descriptor_validator: Any = _validate_embedded_descriptor,
    _descriptor_domain: bytes = _SKELETON_DESCRIPTOR_ROOT_DOMAIN,
    _expected_root: str = _EXPECTED_SKELETON_AUTHORITY_ROOT,
    _canonical: Any = _canonical_json,
    _snapshot: Any = _prepared_table_snapshot,
    _error: Any = StaticCensusClosureError,
) -> PreparedStaticCensusTableV1:
    if (
        PreparedStaticCensusTableV1 is not _table_type
        or _normalize_setup_table is not _normalize_setup
        or json.loads is not _loads
        or _exact_dict is not _exact
        or _validate_embedded_descriptor is not _descriptor_validator
        or _SKELETON_DESCRIPTOR_ROOT_DOMAIN is not _descriptor_domain
        or _EXPECTED_SKELETON_AUTHORITY_ROOT != _expected_root
        or _canonical_json is not _canonical
        or _prepared_table_snapshot is not _snapshot
        or StaticCensusClosureError is not _error
    ):
        raise _error("prepared-table maker binding changed")
    setup_source = _normalize_setup(setup_table)
    skeleton_descriptor = _descriptor_validator(
        _exact(_loads(skeleton_descriptor_json), "skeleton authority descriptor"),
        "skeleton authority descriptor",
        _descriptor_domain,
        _expected_root,
    )
    if _canonical(skeleton_descriptor) != skeleton_descriptor_json:
        raise ValueError("skeleton authority descriptor is not canonical")
    skeleton_root = skeleton_descriptor.get("descriptor_root")
    if skeleton_root != _expected_root:
        raise _error("skeleton authority root changed")
    value = object.__new__(_table_type)
    object.__setattr__(value, "table_version", 1)
    object.__setattr__(value, "_setup_table", setup_source)
    object.__setattr__(value, "_skeleton_rows", skeleton_rows)
    object.__setattr__(value, "_skeleton_descriptor_json", skeleton_descriptor_json)
    object.__setattr__(
        value,
        "_construction_snapshot",
        _snapshot(
            setup_source._construction_snapshot, skeleton_root
        ),
    )
    return value


def _normalize_prepared_table(
    value: Any,
    _table_type: Any = PreparedStaticCensusTableV1,
    _fields: Any = _require_exact_fields,
    _normalize_setup: Any = _normalize_setup_table,
    _descriptor: Any = _skeleton_authority_descriptor,
    _descriptor_validator: Any = _validate_embedded_descriptor,
    _descriptor_domain: bytes = _SKELETON_DESCRIPTOR_ROOT_DOMAIN,
    _expected_root: str = _EXPECTED_SKELETON_AUTHORITY_ROOT,
    _all_contribution: int = _EXPECTED_ALL_ORDERED_CONTRIBUTION,
    _self_contribution: int = _EXPECTED_SELF_ISOMORPHIC_CONTRIBUTION,
    _old_contribution: int = _EXPECTED_OLD_REGION_CONTRIBUTION,
    _canonical: Any = _canonical_json,
    _snapshot: Any = _prepared_table_snapshot,
    _make: Any = _make_prepared_table,
    _error: Any = StaticCensusClosureError,
) -> PreparedStaticCensusTableV1:
    if (
        PreparedStaticCensusTableV1 is not _table_type
        or _require_exact_fields is not _fields
        or _normalize_setup_table is not _normalize_setup
        or _skeleton_authority_descriptor is not _descriptor
        or _validate_embedded_descriptor is not _descriptor_validator
        or _SKELETON_DESCRIPTOR_ROOT_DOMAIN is not _descriptor_domain
        or _EXPECTED_SKELETON_AUTHORITY_ROOT != _expected_root
        or _EXPECTED_ALL_ORDERED_CONTRIBUTION != _all_contribution
        or _EXPECTED_SELF_ISOMORPHIC_CONTRIBUTION != _self_contribution
        or _EXPECTED_OLD_REGION_CONTRIBUTION != _old_contribution
        or _canonical_json is not _canonical
        or _prepared_table_snapshot is not _snapshot
        or _make_prepared_table is not _make
        or StaticCensusClosureError is not _error
    ):
        raise _error("prepared-table normalizer binding changed")
    if type(value) is not _table_type:
        raise TypeError("prepared table must be a PreparedStaticCensusTableV1")
    fields = (
        "table_version",
        "_setup_table",
        "_skeleton_rows",
        "_skeleton_descriptor_json",
        "_construction_snapshot",
    )
    _fields(value, fields, "prepared static-census table")
    snapshot = vars(value).copy()
    if type(snapshot["table_version"]) is not int or snapshot["table_version"] != 1:
        raise ValueError("prepared static-census table version changed")
    setup_source = _normalize_setup(snapshot["_setup_table"])
    skeleton_descriptor = _descriptor(
        snapshot["_skeleton_rows"],
        _all_contribution,
        _self_contribution,
        _old_contribution,
    )
    _descriptor_validator(
        skeleton_descriptor,
        "skeleton authority descriptor",
        _descriptor_domain,
        _expected_root,
    )
    skeleton_descriptor_json = _canonical(skeleton_descriptor)
    skeleton_root = skeleton_descriptor["descriptor_root"]
    expected_snapshot = _snapshot(
        setup_source._construction_snapshot, skeleton_root
    )
    if (
        skeleton_root != _expected_root
        or type(snapshot["_skeleton_descriptor_json"]) is not str
        or snapshot["_skeleton_descriptor_json"] != skeleton_descriptor_json
        or type(snapshot["_construction_snapshot"]) is not str
        or snapshot["_construction_snapshot"] != expected_snapshot
    ):
        raise ValueError("prepared static-census table changed after construction")
    return _make(
        setup_source, snapshot["_skeleton_rows"], skeleton_descriptor_json
    )


def prepare_static_census_table_v1(
    table: SetupOrbitTableV1 | PreparedStaticCensusTableV1,
    _version: Any = _official_version,
    _normalize_setup: Any = _normalize_setup_table,
    _normalize_prepared: Any = _normalize_prepared_table,
    _build: Any = _build_skeleton_authority,
    _make: Any = _make_prepared_table,
    _prepared_type: Any = PreparedStaticCensusTableV1,
    _error: Any = StaticCensusClosureError,
) -> PreparedStaticCensusTableV1:
    """Prepare both finite authorities once for repeated independent shards."""

    if (
        _official_version is not _version
        or _normalize_setup_table is not _normalize_setup
        or _normalize_prepared_table is not _normalize_prepared
        or _build_skeleton_authority is not _build
        or _make_prepared_table is not _make
        or PreparedStaticCensusTableV1 is not _prepared_type
        or StaticCensusClosureError is not _error
    ):
        raise _error("prepared table dependency binding changed")
    _version()
    if type(table) is _prepared_type:
        return _normalize_prepared(table)
    setup_source = _normalize_setup(table)
    skeleton_rows, skeleton_descriptor_json = _build()
    return _make(
        setup_source, skeleton_rows, skeleton_descriptor_json
    )


def _reason_mask(
    reasons: Any,
    _atoms: Tuple[Tuple[str, str, Optional[str]], ...] = _REASON_ATOMS,
    _exact: Any = _exact_dict,
    _keys: Any = _exact_keys,
    _error: Any = StaticCensusClosureError,
) -> int:
    if (
        _REASON_ATOMS is not _atoms
        or _exact_dict is not _exact
        or _exact_keys is not _keys
        or StaticCensusClosureError is not _error
    ):
        raise _error("reason vocabulary binding changed")
    if type(reasons) is not list:
        raise TypeError("rejection reasons must be an exact list")
    indexes: List[int] = []
    for reason in reasons:
        item = _exact(reason, "rejection reason")
        _keys(item, ("code", "role", "first_player"), "rejection reason")
        atom = (item["code"], item["role"], item["first_player"])
        try:
            index = _atoms.index(atom)
        except ValueError as error:
            raise ValueError("rejection reason escaped the fixed vocabulary") from error
        indexes.append(index)
    if tuple(indexes) != tuple(sorted(set(indexes))):
        raise ValueError("rejection reasons are duplicated or out of canonical order")
    return sum(1 << index for index in indexes)


def _reason_payload(
    mask: int,
    _atoms: Tuple[Tuple[str, str, Optional[str]], ...] = _REASON_ATOMS,
    _mask_count: int = _REASON_MASK_COUNT,
    _error: Any = StaticCensusClosureError,
) -> List[Dict[str, Any]]:
    if (
        _REASON_ATOMS is not _atoms
        or _REASON_MASK_COUNT != _mask_count
        or StaticCensusClosureError is not _error
    ):
        raise _error("reason vocabulary binding changed")
    if type(mask) is not int:
        raise TypeError("reason mask must be an exact integer")
    if not 0 <= mask < _mask_count:
        raise ValueError("reason mask is outside the fixed 12-bit domain")
    return [
        {"code": code, "role": role, "first_player": first_player}
        for index, (code, role, first_player) in enumerate(_atoms)
        if mask & (1 << index)
    ]


def _snapshot_payload(
    canonical: str,
    result_hash: str,
    carrier_canonical: str,
    carrier_hash: str,
    setup_hash: str,
    skeleton_hash: str,
    initial_counts: CountPair,
    _canonical: Any = _canonical_json,
    _hash: Any = _domain_hash,
    _loads: Any = json.loads,
    _tree: Any = _validate_json_tree,
    _mask: Any = _reason_mask,
    _exact: Any = _exact_dict,
    _keys: Any = _exact_keys,
    _max_bytes: int = _MAX_SNAPSHOT_BYTES,
    _result_domain: bytes = _INITIAL_RESULT_DOMAIN,
    _evidence_domain: bytes = _INITIAL_EVIDENCE_DOMAIN,
    _expected_count_root: str = _EXPECTED_COUNT_TABLE_ROOT,
    _first_players: Tuple[str, ...] = _FIRST_PLAYERS,
    _descriptor_groups: Tuple[str, ...] = _DESCRIPTOR_GROUPS,
    _contact_classes: Tuple[str, ...] = _CONTACT_CLASSES,
    _error: Any = StaticCensusClosureError,
) -> Tuple[Dict[str, Any], int]:
    if (
        _canonical_json is not _canonical
        or _domain_hash is not _hash
        or json.loads is not _loads
        or _validate_json_tree is not _tree
        or _reason_mask is not _mask
        or _exact_dict is not _exact
        or _exact_keys is not _keys
        or _MAX_SNAPSHOT_BYTES != _max_bytes
        or _INITIAL_RESULT_DOMAIN is not _result_domain
        or _INITIAL_EVIDENCE_DOMAIN is not _evidence_domain
        or _EXPECTED_COUNT_TABLE_ROOT != _expected_count_root
        or _FIRST_PLAYERS is not _first_players
        or _DESCRIPTOR_GROUPS is not _descriptor_groups
        or _CONTACT_CLASSES is not _contact_classes
        or StaticCensusClosureError is not _error
    ):
        raise _error("snapshot validation binding changed")
    if type(canonical) is not str or len(canonical.encode("utf-8")) > _max_bytes:
        raise ValueError("initial-structure snapshot exceeded its byte cap")
    if result_hash != _hash(_result_domain, canonical):
        raise ValueError("initial-structure snapshot hash changed")
    try:
        payload = _loads(canonical)
    except (TypeError, ValueError) as error:
        raise ValueError("initial-structure snapshot is not exact JSON") from error
    payload = _exact(payload, "initial-structure snapshot")
    _tree(payload, "initial-structure snapshot")
    if _canonical(payload) != canonical:
        raise ValueError("initial-structure snapshot is not canonical")
    _keys(
        payload,
        (
            "initial_structure_result_version",
            "kernel_version",
            "carrier",
            "identities",
            "role_facts",
            "count_lattice",
            "descriptor_groups",
            "rejection_reasons",
            "eligible",
            "evidence_digest",
        ),
        "initial-structure snapshot",
    )
    if (
        type(payload["initial_structure_result_version"]) is not int
        or payload["initial_structure_result_version"] != 1
        or type(payload["kernel_version"]) is not int
        or payload["kernel_version"] != 1
    ):
        raise ValueError("initial-structure snapshot version changed")
    body = dict(payload)
    evidence_digest = body.pop("evidence_digest")
    if evidence_digest != _hash(_evidence_domain, _canonical(body)):
        raise ValueError("initial-structure evidence digest changed")
    expected_carrier = _loads(carrier_canonical)
    if (
        _canonical(expected_carrier) != carrier_canonical
        or _canonical(payload["carrier"]) != carrier_canonical
    ):
        raise ValueError("initial-structure snapshot carrier changed")
    identities = _exact(payload["identities"], "snapshot identities")
    _keys(
        identities,
        (
            "typed_setup_hash",
            "typed_skeleton_hash",
            "typed_carrier_hash",
            "typed_carrier_canonical_byte_count",
        ),
        "snapshot identities",
    )
    if identities != {
        "typed_setup_hash": setup_hash,
        "typed_skeleton_hash": skeleton_hash,
        "typed_carrier_hash": carrier_hash,
        "typed_carrier_canonical_byte_count": len(carrier_canonical.encode("utf-8")),
    }:
        raise ValueError("initial-structure snapshot identities changed")
    count_lattice = _exact(payload["count_lattice"], "snapshot count lattice")
    if (
        type(count_lattice.get("table_version")) is not int
        or count_lattice.get("table_version") != 1
        or count_lattice.get("table_root") != _expected_count_root
    ):
        raise ValueError("initial-structure count-table authority changed")
    counts = _exact(count_lattice.get("initial_counts"), "initial counts")
    if (
        any(type(counts.get(role)) is not int for role in _first_players)
        or counts != {"A": initial_counts[0], "B": initial_counts[1]}
    ):
        raise ValueError("initial-structure initial counts changed")
    references = count_lattice.get("tempo_references")
    if type(references) is not list or len(references) != 2:
        raise ValueError("initial-structure tempo references changed shape")
    if tuple(reference.get("first_player") for reference in references) != _first_players:
        raise ValueError("initial-structure tempo reference order changed")
    groups = _exact(payload["descriptor_groups"], "descriptor groups")
    _keys(groups, _descriptor_groups, "descriptor groups")
    contact = _exact(groups["contact"], "contact descriptor").get("contact_class")
    if contact not in _contact_classes:
        raise ValueError("contact class escaped the fixed vocabulary")
    mask = _mask(payload["rejection_reasons"])
    if type(payload["eligible"]) is not bool or payload["eligible"] is not (mask == 0):
        raise ValueError("eligibility is not exactly the empty reason set")
    return payload, mask


def _new_work_extrema(
    _first_players: Tuple[str, ...] = _FIRST_PLAYERS,
    _work_fields: Tuple[str, ...] = _WORK_FIELDS,
    _error: Any = StaticCensusClosureError,
) -> Dict[str, Dict[str, List[Optional[int]]]]:
    if (
        _FIRST_PLAYERS is not _first_players
        or _WORK_FIELDS is not _work_fields
        or StaticCensusClosureError is not _error
    ):
        raise _error("work-extrema constructor binding changed")
    return {
        first_player: {field: [None, None] for field in _work_fields}
        for first_player in _first_players
    }


def _update_work_extrema(
    extrema: Dict[str, Dict[str, List[Optional[int]]]],
    references: Any,
    _first_players: Tuple[str, ...] = _FIRST_PLAYERS,
    _exact: Any = _exact_dict,
    _error: Any = StaticCensusClosureError,
) -> None:
    if (
        _FIRST_PLAYERS is not _first_players
        or _exact_dict is not _exact
        or StaticCensusClosureError is not _error
    ):
        raise _error("work-extrema update binding changed")
    if type(references) is not list or len(references) != 2:
        raise ValueError("tempo references changed shape")
    for expected_first_player, reference_value in zip(_first_players, references):
        reference = _exact(reference_value, "tempo reference")
        if reference.get("first_player") != expected_first_player:
            raise ValueError("tempo reference order changed")
        work = _exact(reference.get("work"), "tempo work")
        values = {
            "state_weight_sum": reference.get("state_weight_sum"),
            "action_candidate_iterations": work.get("action_candidate_iterations"),
            "scan_candidate_iterations": work.get("scan_candidate_iterations"),
        }
        for field, observed in values.items():
            if type(observed) is not int or observed < 0:
                raise TypeError("tempo work must contain exact nonnegative integers")
            if field == "state_weight_sum" and observed > 115_194:
                raise _error("state work exceeded the sealed ceiling")
            if field != "state_weight_sum" and observed > 2_070_432:
                raise _error("iteration work exceeded the sealed ceiling")
            bounds = extrema[expected_first_player][field]
            bounds[0] = observed if bounds[0] is None else min(bounds[0], observed)
            bounds[1] = observed if bounds[1] is None else max(bounds[1], observed)


def _freeze_work_extrema(
    extrema: Dict[str, Dict[str, List[Optional[int]]]],
    _first_players: Tuple[str, ...] = _FIRST_PLAYERS,
    _work_fields: Tuple[str, ...] = _WORK_FIELDS,
    _error: Any = StaticCensusClosureError,
) -> Dict[str, Any]:
    if (
        _FIRST_PLAYERS is not _first_players
        or _WORK_FIELDS is not _work_fields
        or StaticCensusClosureError is not _error
    ):
        raise _error("work-extrema freeze binding changed")
    result: Dict[str, Any] = {}
    for first_player in _first_players:
        result[first_player] = {}
        for field in _work_fields:
            minimum, maximum = extrema[first_player][field]
            if type(minimum) is not int or type(maximum) is not int or minimum > maximum:
                raise _error("shard work extrema are incomplete")
            result[first_player][field] = {
                "minimum": minimum,
                "maximum": maximum,
            }
    return result


@dataclass(frozen=True, init=False)
class StaticCensusShardV1:
    """One complete skeleton shard, retained only as a compact summary."""

    shard_version: int
    skeleton_ordinal: int
    _summary_json: str
    _construction_snapshot: str

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("StaticCensusShardV1 values are created only by the deriver")


def _make_shard(
    summary: Dict[str, Any],
    _shard_type: Any = StaticCensusShardV1,
    _canonical: Any = _canonical_json,
    _sha_validator: Any = _is_sha256,
    _error: Any = StaticCensusClosureError,
) -> StaticCensusShardV1:
    if (
        StaticCensusShardV1 is not _shard_type
        or _canonical_json is not _canonical
        or _is_sha256 is not _sha_validator
        or StaticCensusClosureError is not _error
    ):
        raise _error("shard maker binding changed")
    canonical = _canonical(summary)
    commitment = summary.get("shard_commitment")
    if not _sha_validator(commitment):
        raise ValueError("static-census shard commitment is invalid")
    value = object.__new__(_shard_type)
    object.__setattr__(value, "shard_version", 1)
    object.__setattr__(value, "skeleton_ordinal", summary["skeleton"]["ordinal"])
    object.__setattr__(value, "_summary_json", canonical)
    object.__setattr__(value, "_construction_snapshot", commitment)
    return value


def _validate_shard_summary(
    summary_value: Any,
    expected_row: Optional[_SkeletonRow] = None,
    expected_setup_root: str = _EXPECTED_SETUP_ORBIT_TABLE_ROOT,
    _api: Any = _api_guard,
    _exact: Any = _exact_dict,
    _tree: Any = _validate_json_tree,
    _keys: Any = _exact_keys,
    _loads: Any = json.loads,
    _canonical: Any = _canonical_json,
    _hash: Any = _domain_hash,
    _sha_validator: Any = _is_sha256,
    _reason: Any = _reason_payload,
    _stabilizer: Any = _canonical_stabilizer,
    _semantic_hash: Any = _canonical_role_neutral_semantic_hash,
    _frozen_setup_root: str = _EXPECTED_SETUP_ORBIT_TABLE_ROOT,
    _expected_skeleton_count: int = _EXPECTED_SKELETON_COUNT,
    _expected_setup_count: int = _EXPECTED_SETUP_COUNT,
    _signatures: Tuple[StabilizerSignature, ...] = _STABILIZER_SIGNATURES,
    _orbit_counts: Tuple[int, ...] = _SETUP_ORBIT_COUNTS,
    _weight_histograms: Tuple[Tuple[Tuple[int, int], ...], ...] = _SETUP_WEIGHT_HISTOGRAMS,
    _reason_mask_count: int = _REASON_MASK_COUNT,
    _contact_classes: Tuple[str, ...] = _CONTACT_CLASSES,
    _count_pairs: Tuple[CountPair, ...] = _COUNT_PAIRS,
    _first_players: Tuple[str, ...] = _FIRST_PLAYERS,
    _work_fields: Tuple[str, ...] = _WORK_FIELDS,
    _descriptor_groups: Tuple[str, ...] = _DESCRIPTOR_GROUPS,
    _profiled_domain: bytes = _PROFILED_SKELETON_HASH_DOMAIN,
    _neutral_domain: bytes = _ROLE_NEUTRAL_SKELETON_HASH_DOMAIN,
    _summary_domain: bytes = _STATIC_SHARD_SUMMARY_DOMAIN,
    _error: Any = StaticCensusClosureError,
) -> Dict[str, Any]:
    if (
        _api_guard is not _api
        or _exact_dict is not _exact
        or _validate_json_tree is not _tree
        or _exact_keys is not _keys
        or json.loads is not _loads
        or _canonical_json is not _canonical
        or _domain_hash is not _hash
        or _is_sha256 is not _sha_validator
        or _reason_payload is not _reason
        or _canonical_stabilizer is not _stabilizer
        or _canonical_role_neutral_semantic_hash is not _semantic_hash
        or _EXPECTED_SETUP_ORBIT_TABLE_ROOT != _frozen_setup_root
        or _EXPECTED_SKELETON_COUNT != _expected_skeleton_count
        or _EXPECTED_SETUP_COUNT != _expected_setup_count
        or _STABILIZER_SIGNATURES is not _signatures
        or _SETUP_ORBIT_COUNTS is not _orbit_counts
        or _SETUP_WEIGHT_HISTOGRAMS is not _weight_histograms
        or _REASON_MASK_COUNT != _reason_mask_count
        or _CONTACT_CLASSES is not _contact_classes
        or _COUNT_PAIRS is not _count_pairs
        or _FIRST_PLAYERS is not _first_players
        or _WORK_FIELDS is not _work_fields
        or _DESCRIPTOR_GROUPS is not _descriptor_groups
        or _PROFILED_SKELETON_HASH_DOMAIN is not _profiled_domain
        or _ROLE_NEUTRAL_SKELETON_HASH_DOMAIN is not _neutral_domain
        or _STATIC_SHARD_SUMMARY_DOMAIN is not _summary_domain
        or StaticCensusClosureError is not _error
    ):
        raise _error("shard-summary validator binding changed")
    if expected_setup_root != _frozen_setup_root:
        raise ValueError("shard setup authority root changed")
    summary = _exact(summary_value, "static-census shard summary")
    _tree(summary, "static-census shard summary")
    _keys(
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
        "static-census shard summary",
    )
    if (
        type(summary["static_census_shard_version"]) is not int
        or summary["static_census_shard_version"] != 1
    ):
        raise ValueError("static-census shard version changed")
    skeleton = _exact(summary["skeleton"], "shard skeleton")
    _keys(
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
    ordinal = skeleton["ordinal"]
    if type(ordinal) is not int or not 0 <= ordinal < _expected_skeleton_count:
        raise ValueError("shard skeleton ordinal is outside the fixed domain")
    skeleton_canonical = skeleton["canonical_profiled_skeleton_json"]
    if type(skeleton_canonical) is not str:
        raise TypeError("shard skeleton canonical JSON changed type")
    try:
        skeleton_payload = _loads(skeleton_canonical)
    except (TypeError, ValueError) as error:
        raise ValueError("shard skeleton canonical JSON is invalid") from error
    _tree(skeleton_payload, "shard canonical skeleton")
    api = _api()
    parsed_skeleton = api[13](skeleton_payload)
    if type(skeleton["exact_stabilizer"]) is not list:
        raise TypeError("shard exact stabilizer changed type")
    observed_stabilizer = _stabilizer(skeleton_canonical)
    if (
        _canonical(skeleton_payload) != skeleton_canonical
        or api[14](parsed_skeleton) != skeleton_canonical
        or skeleton["typed_skeleton_hash"]
        != _hash(_profiled_domain, skeleton_canonical)
        or skeleton["role_neutral_skeleton_hash"]
        != _hash(_neutral_domain, skeleton_canonical)
        or skeleton["role_neutral_semantic_hash"]
        != _semantic_hash(skeleton_canonical)
        or tuple(skeleton["exact_stabilizer"]) != observed_stabilizer
    ):
        raise ValueError("shard skeleton identities changed")
    if expected_row is not None:
        if type(expected_row) is not tuple or len(expected_row) != 8:
            raise TypeError("expected skeleton row changed shape")
        expected_skeleton = {
            "ordinal": expected_row[0],
            "canonical_profiled_skeleton_json": expected_row[1],
            "typed_skeleton_hash": expected_row[2],
            "role_neutral_skeleton_hash": expected_row[3],
            "role_neutral_semantic_hash": expected_row[4],
            "exact_stabilizer": list(expected_row[5]),
        }
        if skeleton != expected_skeleton:
            raise ValueError("shard skeleton authority changed")
    signature = tuple(skeleton["exact_stabilizer"])
    if signature not in _signatures:
        raise ValueError("shard exact stabilizer escaped the fixed domain")
    group_index = _signatures.index(signature)

    setup_orbit = _exact(summary["setup_orbit"], "shard setup orbit")
    _keys(
        setup_orbit,
        (
            "setup_orbit_table_root",
            "representative_count",
            "weighted_setup_count",
            "paired_first_player_member_count",
            "weight_histogram",
        ),
        "shard setup orbit",
    )
    expected_representative_count = _orbit_counts[group_index]
    expected_weight_histogram = {
        str(weight): count for weight, count in _weight_histograms[group_index]
    }
    setup_orbit_numeric_fields = (
        "representative_count",
        "weighted_setup_count",
        "paired_first_player_member_count",
    )
    if any(
        type(setup_orbit[field]) is not int or setup_orbit[field] <= 0
        for field in setup_orbit_numeric_fields
    ):
        raise TypeError("shard setup-orbit counts must be exact positive integers")
    setup_weight_histogram = _exact(
        setup_orbit["weight_histogram"], "shard setup weight histogram"
    )
    if any(
        type(count) is not int or count <= 0
        for count in setup_weight_histogram.values()
    ):
        raise TypeError("shard setup weights must be exact positive integers")
    if setup_orbit != {
        "setup_orbit_table_root": expected_setup_root,
        "representative_count": expected_representative_count,
        "weighted_setup_count": _expected_setup_count,
        "paired_first_player_member_count": 2 * _expected_setup_count,
        "weight_histogram": expected_weight_histogram,
    }:
        raise ValueError("shard setup-orbit arithmetic changed")

    eligibility = _exact(summary["eligibility"], "shard eligibility")
    _keys(
        eligibility,
        (
            "representative_eligible_count",
            "weighted_eligible_count",
            "paired_first_player_eligible_member_count",
            "reason_combinations",
        ),
        "shard eligibility",
    )
    reason_combinations = eligibility["reason_combinations"]
    if type(reason_combinations) is not list:
        raise TypeError("reason combinations must be an exact list")
    aggregate_fields = (
        "representative_eligible_count",
        "weighted_eligible_count",
        "paired_first_player_eligible_member_count",
    )
    if any(
        type(eligibility[field]) is not int or eligibility[field] < 0
        for field in aggregate_fields
    ):
        raise TypeError("shard eligible counts must be exact nonnegative integers")
    reason_rep_total = 0
    reason_weight_total = 0
    eligible_rep = 0
    eligible_weight = 0
    previous_mask = -1
    for combination_value in reason_combinations:
        combination = _exact(combination_value, "reason combination")
        _keys(
            combination,
            ("reason_mask", "reasons", "representative_count", "weighted_count"),
            "reason combination",
        )
        mask = combination["reason_mask"]
        representative_count = combination["representative_count"]
        weighted_count = combination["weighted_count"]
        if (
            type(mask) is not int
            or not previous_mask < mask < _reason_mask_count
            or type(representative_count) is not int
            or representative_count <= 0
            or type(weighted_count) is not int
            or weighted_count <= 0
            or combination["reasons"] != _reason(mask)
        ):
            raise ValueError("reason combination is not canonical")
        previous_mask = mask
        reason_rep_total += representative_count
        reason_weight_total += weighted_count
        if mask == 0:
            eligible_rep = representative_count
            eligible_weight = weighted_count
    if (
        reason_rep_total != expected_representative_count
        or reason_weight_total != _expected_setup_count
        or eligibility["representative_eligible_count"] != eligible_rep
        or eligibility["weighted_eligible_count"] != eligible_weight
        or eligibility["paired_first_player_eligible_member_count"]
        != 2 * eligible_weight
    ):
        raise ValueError("shard reason-combination arithmetic changed")

    contact = _exact(summary["contact"], "shard contact")
    _keys(contact, _contact_classes, "shard contact")
    contact_rep_total = 0
    contact_weight_total = 0
    contact_eligible_rep_total = 0
    contact_eligible_weight_total = 0
    for contact_class in _contact_classes:
        row = _exact(contact[contact_class], "shard contact row")
        _keys(
            row,
            (
                "representative_count",
                "weighted_count",
                "eligible_representative_count",
                "eligible_weighted_count",
            ),
            "shard contact row",
        )
        if any(type(row[field]) is not int or row[field] < 0 for field in row):
            raise TypeError("shard contact counts must be exact nonnegative integers")
        if (
            row["eligible_representative_count"] > row["representative_count"]
            or row["eligible_weighted_count"] > row["weighted_count"]
        ):
            raise ValueError("eligible contact count exceeds its raw count")
        contact_rep_total += row["representative_count"]
        contact_weight_total += row["weighted_count"]
        contact_eligible_rep_total += row["eligible_representative_count"]
        contact_eligible_weight_total += row["eligible_weighted_count"]
    if (
        contact_rep_total != expected_representative_count
        or contact_weight_total != _expected_setup_count
        or contact_eligible_rep_total != eligible_rep
        or contact_eligible_weight_total != eligible_weight
    ):
        raise ValueError("shard contact arithmetic changed")

    supply = summary["eligible_supply_by_count_pair_and_contact"]
    if type(supply) is not list or len(supply) != len(_count_pairs) * 2:
        raise ValueError("eligible supply table changed shape")
    supply_rep_total = 0
    supply_weight_total = 0
    for index, supply_value in enumerate(supply):
        row = _exact(supply_value, "eligible supply row")
        _keys(
            row,
            (
                "initial_counts",
                "contact_class",
                "representative_count",
                "weighted_count",
            ),
            "eligible supply row",
        )
        count_pair = _count_pairs[index // 2]
        contact_class = _contact_classes[index % 2]
        initial_counts = _exact(row["initial_counts"], "eligible supply counts")
        _keys(initial_counts, _first_players, "eligible supply counts")
        if (
            any(
                type(initial_counts[role]) is not int
                for role in _first_players
            )
            or initial_counts != {"A": count_pair[0], "B": count_pair[1]}
            or row["contact_class"] != contact_class
            or type(row["representative_count"]) is not int
            or row["representative_count"] < 0
            or type(row["weighted_count"]) is not int
            or row["weighted_count"] < 0
        ):
            raise ValueError("eligible supply row changed")
        supply_rep_total += row["representative_count"]
        supply_weight_total += row["weighted_count"]
    if supply_rep_total != eligible_rep or supply_weight_total != eligible_weight:
        raise ValueError("eligible supply arithmetic changed")

    work_extrema = _exact(summary["work_extrema"], "shard work extrema")
    _keys(work_extrema, _first_players, "shard work extrema")
    for first_player in _first_players:
        work_row = _exact(work_extrema[first_player], "shard tempo extrema")
        _keys(work_row, _work_fields, "shard tempo extrema")
        for field in _work_fields:
            bounds = _exact(work_row[field], "shard work bounds")
            _keys(bounds, ("minimum", "maximum"), "shard work bounds")
            minimum = bounds["minimum"]
            maximum = bounds["maximum"]
            ceiling = 115_194 if field == "state_weight_sum" else 2_070_432
            if (
                type(minimum) is not int
                or type(maximum) is not int
                or not 0 <= minimum <= maximum <= ceiling
            ):
                raise ValueError("shard work bounds changed")

    roots = _exact(summary["roots"], "shard roots")
    _keys(
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
    if not _sha_validator(roots["ordered_leaf_commitment_root"]):
        raise ValueError("shard leaf commitment root changed format")
    if not _sha_validator(roots["ordered_initial_structure_result_root"]):
        raise ValueError("shard result root changed format")
    if not _sha_validator(roots["ordered_role_facts_root"]):
        raise ValueError("shard role-facts root changed format")
    if not _sha_validator(roots["ordered_count_lattice_root"]):
        raise ValueError("shard count-lattice root changed format")
    group_roots = _exact(
        roots["ordered_descriptor_group_roots"], "descriptor-group roots"
    )
    _keys(group_roots, _descriptor_groups, "descriptor-group roots")
    if any(not _sha_validator(group_roots[name]) for name in _descriptor_groups):
        raise ValueError("descriptor-group root changed format")

    commitment = summary["shard_commitment"]
    body = dict(summary)
    body.pop("shard_commitment")
    expected_commitment = _hash(
        _summary_domain, _canonical(body)
    )
    if commitment != expected_commitment:
        raise ValueError("static-census shard commitment changed")
    return summary


def _normalize_shard(
    value: Any,
    _shard_type: Any = StaticCensusShardV1,
    _fields: Any = _require_exact_fields,
    _loads: Any = json.loads,
    _canonical: Any = _canonical_json,
    _validate: Any = _validate_shard_summary,
    _make: Any = _make_shard,
    _error: Any = StaticCensusClosureError,
) -> StaticCensusShardV1:
    if (
        StaticCensusShardV1 is not _shard_type
        or _require_exact_fields is not _fields
        or json.loads is not _loads
        or _canonical_json is not _canonical
        or _validate_shard_summary is not _validate
        or _make_shard is not _make
        or StaticCensusClosureError is not _error
    ):
        raise _error("shard normalizer binding changed")
    if type(value) is not _shard_type:
        raise TypeError("shard must be a StaticCensusShardV1")
    fields = (
        "shard_version",
        "skeleton_ordinal",
        "_summary_json",
        "_construction_snapshot",
    )
    _fields(value, fields, "static-census shard")
    snapshot = vars(value).copy()
    if type(snapshot["shard_version"]) is not int or snapshot["shard_version"] != 1:
        raise ValueError("static-census shard version changed")
    if type(snapshot["_summary_json"]) is not str:
        raise TypeError("static-census shard summary changed type")
    try:
        summary = _loads(snapshot["_summary_json"])
    except (TypeError, ValueError) as error:
        raise ValueError("static-census shard summary is not JSON") from error
    if _canonical(summary) != snapshot["_summary_json"]:
        raise ValueError("static-census shard summary is not canonical")
    _validate(summary)
    if (
        type(snapshot["skeleton_ordinal"]) is not int
        or snapshot["skeleton_ordinal"] != summary["skeleton"]["ordinal"]
        or type(snapshot["_construction_snapshot"]) is not str
        or snapshot["_construction_snapshot"] != summary["shard_commitment"]
    ):
        raise ValueError("static-census shard changed after construction")
    return _make(summary)


def _derive_shard_core(
    prepared_table: PreparedStaticCensusTableV1,
    skeleton_ordinal: int,
    _api: Any = _api_guard,
    _snapshot: Any = _snapshot_payload,
    _reason: Any = _reason_payload,
    _update_work: Any = _update_work_extrema,
    _freeze_work: Any = _freeze_work_extrema,
    _validate: Any = _validate_shard_summary,
    _make: Any = _make_shard,
    _canonical: Any = _canonical_json,
    _hash: Any = _domain_hash,
    _sha256: Any = hashlib.sha256,
    _loads: Any = json.loads,
    _new_work: Any = _new_work_extrema,
    _prepared_type: Any = PreparedStaticCensusTableV1,
    _expected_skeleton_count: int = _EXPECTED_SKELETON_COUNT,
    _expected_setup_count: int = _EXPECTED_SETUP_COUNT,
    _signatures: Tuple[StabilizerSignature, ...] = _STABILIZER_SIGNATURES,
    _reason_mask_count: int = _REASON_MASK_COUNT,
    _count_pairs: Tuple[CountPair, ...] = _COUNT_PAIRS,
    _contact_classes: Tuple[str, ...] = _CONTACT_CLASSES,
    _descriptor_groups: Tuple[str, ...] = _DESCRIPTOR_GROUPS,
    _leaf_domain: bytes = _STATIC_LEAF_DOMAIN,
    _shard_root_domain: bytes = _STATIC_SHARD_ROOT_DOMAIN,
    _group_root_domain: bytes = _STATIC_GROUP_ROOT_DOMAIN,
    _summary_domain: bytes = _STATIC_SHARD_SUMMARY_DOMAIN,
    _error: Any = StaticCensusClosureError,
) -> StaticCensusShardV1:
    if (
        _api_guard is not _api
        or _snapshot_payload is not _snapshot
        or _reason_payload is not _reason
        or _update_work_extrema is not _update_work
        or _freeze_work_extrema is not _freeze_work
        or _validate_shard_summary is not _validate
        or _make_shard is not _make
        or _canonical_json is not _canonical
        or _domain_hash is not _hash
        or hashlib.sha256 is not _sha256
        or json.loads is not _loads
        or _new_work_extrema is not _new_work
        or PreparedStaticCensusTableV1 is not _prepared_type
        or _EXPECTED_SKELETON_COUNT != _expected_skeleton_count
        or _EXPECTED_SETUP_COUNT != _expected_setup_count
        or _STABILIZER_SIGNATURES is not _signatures
        or _REASON_MASK_COUNT != _reason_mask_count
        or _COUNT_PAIRS is not _count_pairs
        or _CONTACT_CLASSES is not _contact_classes
        or _DESCRIPTOR_GROUPS is not _descriptor_groups
        or _STATIC_LEAF_DOMAIN is not _leaf_domain
        or _STATIC_SHARD_ROOT_DOMAIN is not _shard_root_domain
        or _STATIC_GROUP_ROOT_DOMAIN is not _group_root_domain
        or _STATIC_SHARD_SUMMARY_DOMAIN is not _summary_domain
        or StaticCensusClosureError is not _error
    ):
        raise _error("shard derivation binding changed")
    if type(prepared_table) is not _prepared_type:
        raise TypeError("shard core requires a prepared static-census table")
    source = prepared_table
    if type(skeleton_ordinal) is not int:
        raise TypeError("skeleton ordinal must be an exact integer")
    if not 0 <= skeleton_ordinal < _expected_skeleton_count:
        raise ValueError("skeleton ordinal is outside the fixed domain")
    skeleton_row = source._skeleton_rows[skeleton_ordinal]
    (
        _,
        skeleton_canonical,
        skeleton_hash,
        neutral_hash,
        semantic_hash,
        signature,
        expected_representative_count,
        expected_weight_histogram,
    ) = skeleton_row
    group_index = _signatures.index(signature)
    partition = source._setup_table._partitions[group_index]
    representatives = partition[2]
    if (
        partition[0] != signature
        or len(representatives) != expected_representative_count
    ):
        raise _error("setup stabilizer dispatch changed")

    api = _api()
    setup_type = api[0]
    carrier_type = api[1]
    carrier_json = api[5]
    carrier_hash_function = api[6]
    parse_skeleton = api[13]
    prepare_kernel = api[20]
    snapshot_kernel = api[21]
    skeleton = parse_skeleton(_loads(skeleton_canonical))
    if api[14](skeleton) != skeleton_canonical or api[15](skeleton) != skeleton_hash:
        raise _error("skeleton row does not reconstruct")

    reason_rep = [0] * _reason_mask_count
    reason_weight = [0] * _reason_mask_count
    weight_histogram: Dict[int, int] = {}
    contact_counts = {
        contact_class: {
            "representative_count": 0,
            "weighted_count": 0,
            "eligible_representative_count": 0,
            "eligible_weighted_count": 0,
        }
        for contact_class in _contact_classes
    }
    eligible_supply_rep: Dict[Tuple[int, int, str], int] = {}
    eligible_supply_weight: Dict[Tuple[int, int, str], int] = {}
    extrema = _new_work()
    result_digest = _sha256(
        _leaf_domain + skeleton_ordinal.to_bytes(8, "big")
    )
    leaf_commitment_digest = _sha256(
        _shard_root_domain
        + b"leaf-commitments\0"
        + skeleton_ordinal.to_bytes(8, "big")
    )
    role_digest = _sha256(
        _shard_root_domain + b"role-facts\0" + skeleton_ordinal.to_bytes(8, "big")
    )
    count_digest = _sha256(
        _shard_root_domain + b"count-lattice\0" + skeleton_ordinal.to_bytes(8, "big")
    )
    group_digests = {
        name: _sha256(
            _group_root_domain
            + name.encode("ascii")
            + b"\0"
            + skeleton_ordinal.to_bytes(8, "big")
        )
        for name in _descriptor_groups
    }

    first_setup_ordinal, _ = representatives[0]
    first_setup_row = source._setup_table._rows[first_setup_ordinal]
    first_setup = setup_type(1, first_setup_row[2], first_setup_row[3])
    first_carrier = carrier_type(1, skeleton, first_setup)
    prepared_kernel = prepare_kernel(first_carrier)

    for representative_index, (setup_ordinal, weight) in enumerate(representatives):
        setup_row = source._setup_table._rows[setup_ordinal]
        if (
            type(setup_ordinal) is not int
            or type(weight) is not int
            or weight not in (1, 2, 4, 8)
            or setup_row[0] != setup_ordinal
        ):
            raise _error("setup representative row changed")
        setup = setup_type(1, setup_row[2], setup_row[3])
        if api[2](setup) != setup_row[4] or api[3](setup) != setup_row[5]:
            raise _error("typed setup row does not reconstruct")
        carrier = carrier_type(1, skeleton, setup)
        carrier_canonical = carrier_json(carrier)
        carrier_identity = carrier_hash_function(carrier)
        canonical_result, result_hash = snapshot_kernel(prepared_kernel, carrier)
        payload, mask = _snapshot(
            canonical_result,
            result_hash,
            carrier_canonical,
            carrier_identity,
            setup_row[5],
            skeleton_hash,
            _count_pairs[setup_row[1]],
        )

        encoded = canonical_result.encode("utf-8")
        result_digest.update(representative_index.to_bytes(8, "big"))
        result_digest.update(len(encoded).to_bytes(8, "big"))
        result_digest.update(encoded)
        reason_rep[mask] += 1
        reason_weight[mask] += weight
        weight_histogram[weight] = weight_histogram.get(weight, 0) + 1
        contact_class = payload["descriptor_groups"]["contact"]["contact_class"]
        contact_row = contact_counts[contact_class]
        contact_row["representative_count"] += 1
        contact_row["weighted_count"] += weight
        if mask == 0:
            contact_row["eligible_representative_count"] += 1
            contact_row["eligible_weighted_count"] += weight
            count_pair = _count_pairs[setup_row[1]]
            supply_key = (count_pair[0], count_pair[1], contact_class)
            eligible_supply_rep[supply_key] = eligible_supply_rep.get(supply_key, 0) + 1
            eligible_supply_weight[supply_key] = (
                eligible_supply_weight.get(supply_key, 0) + weight
            )
        _update_work(
            extrema, payload["count_lattice"]["tempo_references"]
        )

        leaf_commitment = _canonical(
            {
                "skeleton_ordinal": skeleton_ordinal,
                "typed_skeleton_hash": skeleton_hash,
                "setup_orbit_table_root": source._setup_table._construction_snapshot,
                "exact_stabilizer": list(signature),
                "representative_index": representative_index,
                "setup_ordinal": setup_ordinal,
                "typed_setup_canonical_json": setup_row[4],
                "typed_setup_hash": setup_row[5],
                "orbit_weight": weight,
                "typed_carrier_hash": carrier_identity,
                "initial_structure_result_hash": result_hash,
                "initial_structure_evidence_digest": payload["evidence_digest"],
                "reason_mask": mask,
                "eligible": payload["eligible"],
                "contact_class": contact_class,
                "initial_counts": payload["count_lattice"]["initial_counts"],
                "tempo_references": payload["count_lattice"]["tempo_references"],
            }
        )
        leaf_commitment_bytes = leaf_commitment.encode("utf-8")
        leaf_commitment_digest.update(representative_index.to_bytes(8, "big"))
        leaf_commitment_digest.update(len(leaf_commitment_bytes).to_bytes(8, "big"))
        leaf_commitment_digest.update(leaf_commitment_bytes)

        rooted_values = (
            (role_digest, payload["role_facts"]),
            (count_digest, payload["count_lattice"]),
        )
        for digest, rooted_value in rooted_values:
            rooted_canonical = _canonical(
                {"orbit_weight": weight, "value": rooted_value}
            )
            rooted_bytes = rooted_canonical.encode("utf-8")
            digest.update(representative_index.to_bytes(8, "big"))
            digest.update(len(rooted_bytes).to_bytes(8, "big"))
            digest.update(rooted_bytes)
        for name in _descriptor_groups:
            group_canonical = _canonical(
                {
                    "orbit_weight": weight,
                    "value": payload["descriptor_groups"][name],
                }
            )
            group_bytes = group_canonical.encode("utf-8")
            group_digests[name].update(representative_index.to_bytes(8, "big"))
            group_digests[name].update(len(group_bytes).to_bytes(8, "big"))
            group_digests[name].update(group_bytes)

    observed_weight_histogram = tuple(sorted(weight_histogram.items()))
    if (
        sum(reason_rep) != expected_representative_count
        or sum(reason_weight) != _expected_setup_count
        or observed_weight_histogram != expected_weight_histogram
    ):
        raise _error("shard factorized arithmetic changed")
    reason_combinations = [
        {
            "reason_mask": mask,
            "reasons": _reason(mask),
            "representative_count": reason_rep[mask],
            "weighted_count": reason_weight[mask],
        }
        for mask in range(_reason_mask_count)
        if reason_rep[mask]
    ]
    eligible_rep = reason_rep[0]
    eligible_weight = reason_weight[0]
    supply_rows = [
        {
            "initial_counts": {"A": count_pair[0], "B": count_pair[1]},
            "contact_class": contact_class,
            "representative_count": eligible_supply_rep.get(
                (count_pair[0], count_pair[1], contact_class), 0
            ),
            "weighted_count": eligible_supply_weight.get(
                (count_pair[0], count_pair[1], contact_class), 0
            ),
        }
        for count_pair in _count_pairs
        for contact_class in _contact_classes
    ]
    body: Dict[str, Any] = {
        "static_census_shard_version": 1,
        "skeleton": {
            "ordinal": skeleton_ordinal,
            "canonical_profiled_skeleton_json": skeleton_canonical,
            "typed_skeleton_hash": skeleton_hash,
            "role_neutral_skeleton_hash": neutral_hash,
            "role_neutral_semantic_hash": semantic_hash,
            "exact_stabilizer": list(signature),
        },
        "setup_orbit": {
            "setup_orbit_table_root": source._setup_table._construction_snapshot,
            "representative_count": expected_representative_count,
            "weighted_setup_count": _expected_setup_count,
            "paired_first_player_member_count": 2 * _expected_setup_count,
            "weight_histogram": {
                str(weight): count for weight, count in observed_weight_histogram
            },
        },
        "eligibility": {
            "representative_eligible_count": eligible_rep,
            "weighted_eligible_count": eligible_weight,
            "paired_first_player_eligible_member_count": 2 * eligible_weight,
            "reason_combinations": reason_combinations,
        },
        "contact": contact_counts,
        "eligible_supply_by_count_pair_and_contact": supply_rows,
        "work_extrema": _freeze_work(extrema),
        "roots": {
            "ordered_leaf_commitment_root": leaf_commitment_digest.hexdigest(),
            "ordered_initial_structure_result_root": result_digest.hexdigest(),
            "ordered_role_facts_root": role_digest.hexdigest(),
            "ordered_count_lattice_root": count_digest.hexdigest(),
            "ordered_descriptor_group_roots": {
                name: group_digests[name].hexdigest()
                for name in _descriptor_groups
            },
        },
    }
    summary = dict(body)
    summary["shard_commitment"] = _hash(
        _summary_domain, _canonical(body)
    )
    _validate(
        summary,
        expected_row=skeleton_row,
        expected_setup_root=source._setup_table._construction_snapshot,
    )
    return _make(summary)


def _derive_shard_from_prepared(
    prepared_table: PreparedStaticCensusTableV1,
    skeleton_ordinal: int,
    _normalize: Any = _normalize_prepared_table,
    _core: Any = _derive_shard_core,
    _error: Any = StaticCensusClosureError,
) -> StaticCensusShardV1:
    if (
        _normalize_prepared_table is not _normalize
        or _derive_shard_core is not _core
        or StaticCensusClosureError is not _error
    ):
        raise _error("prepared shard boundary binding changed")
    source = _normalize(prepared_table)
    return _core(source, skeleton_ordinal)


def derive_static_census_shard_v1(
    table: SetupOrbitTableV1 | PreparedStaticCensusTableV1,
    skeleton_ordinal: int,
    _version: Any = _official_version,
    _prepare: Any = prepare_static_census_table_v1,
    _derive: Any = _derive_shard_core,
    _error: Any = StaticCensusClosureError,
) -> StaticCensusShardV1:
    """Independently derive one complete deterministic skeleton shard."""

    if (
        _official_version is not _version
        or prepare_static_census_table_v1 is not _prepare
        or _derive_shard_core is not _derive
        or StaticCensusClosureError is not _error
    ):
        raise _error("public shard derivation binding changed")
    _version()
    prepared = _prepare(table)
    return _derive(prepared, skeleton_ordinal)


def static_census_shard_summary_v1(
    shard: StaticCensusShardV1,
    _normalize: Any = _normalize_shard,
    _loads: Any = json.loads,
    _error: Any = StaticCensusClosureError,
) -> Dict[str, Any]:
    """Return a detached compact summary for one completed shard."""

    if (
        _normalize_shard is not _normalize
        or json.loads is not _loads
        or StaticCensusClosureError is not _error
    ):
        raise _error("shard summary binding changed")
    source = _normalize(shard)
    return _loads(source._summary_json)


def _skeleton_row_canonical(
    row: _SkeletonRow,
    _canonical: Any = _canonical_json,
    _error: Any = StaticCensusClosureError,
) -> str:
    if _canonical_json is not _canonical or StaticCensusClosureError is not _error:
        raise _error("skeleton-row canonicalizer binding changed")
    return _canonical(
        {
            "skeleton_ordinal": row[0],
            "skeleton_json": row[1],
            "typed_skeleton_hash": row[2],
            "role_neutral_skeleton_hash": row[3],
            "role_neutral_semantic_hash": row[4],
            "exact_stabilizer": list(row[5]),
            "setup_orbit_count": row[6],
            "setup_weight_histogram": {
                str(weight): count for weight, count in row[7]
            },
        }
    )


def _checkpoint_body(
    prepared_table: PreparedStaticCensusTableV1,
    next_skeleton_ordinal: int,
    summary_jsons: Tuple[str, ...],
    representative_reason_counts: Tuple[int, ...],
    weighted_reason_counts: Tuple[int, ...],
    _loads: Any = json.loads,
    _sequence: Any = _sequence_root,
    _row_canonical: Any = _skeleton_row_canonical,
    _expected_skeleton_root: str = _EXPECTED_SKELETON_AUTHORITY_ROOT,
    _expected_skeleton_count: int = _EXPECTED_SKELETON_COUNT,
    _skeleton_domain: bytes = _SKELETON_AUTHORITY_ROOT_DOMAIN,
    _checkpoint_domain: bytes = _STATIC_CHECKPOINT_DOMAIN,
    _error: Any = StaticCensusClosureError,
) -> Dict[str, Any]:
    if (
        json.loads is not _loads
        or _sequence_root is not _sequence
        or _skeleton_row_canonical is not _row_canonical
        or _EXPECTED_SKELETON_AUTHORITY_ROOT != _expected_skeleton_root
        or _EXPECTED_SKELETON_COUNT != _expected_skeleton_count
        or _SKELETON_AUTHORITY_ROOT_DOMAIN is not _skeleton_domain
        or _STATIC_CHECKPOINT_DOMAIN is not _checkpoint_domain
        or StaticCensusClosureError is not _error
    ):
        raise _error("checkpoint-body binding changed")
    commitments: List[str] = []
    processed_representatives = 0
    processed_weighted = 0
    eligible_representatives = 0
    eligible_weighted = 0
    for canonical in summary_jsons:
        summary = _loads(canonical)
        commitments.append(summary["shard_commitment"])
        processed_representatives += summary["setup_orbit"]["representative_count"]
        processed_weighted += summary["setup_orbit"]["weighted_setup_count"]
        eligible_representatives += summary["eligibility"][
            "representative_eligible_count"
        ]
        eligible_weighted += summary["eligibility"]["weighted_eligible_count"]
    return {
        "static_census_checkpoint_version": 1,
        "setup_orbit_table_root": prepared_table._setup_table._construction_snapshot,
        "skeleton_authority_root": _expected_skeleton_root,
        "next_skeleton_ordinal": next_skeleton_ordinal,
        "processed_skeleton_count": next_skeleton_ordinal,
        "remaining_skeleton_count": _expected_skeleton_count - next_skeleton_ordinal,
        "processed_factorized_carrier_count": processed_representatives,
        "processed_labeled_setup_count": processed_weighted,
        "processed_paired_first_player_member_count": 2 * processed_weighted,
        "representative_eligible_count": eligible_representatives,
        "weighted_eligible_count": eligible_weighted,
        "ordered_shard_commitments": commitments,
        "representative_reason_mask_counts": list(representative_reason_counts),
        "weighted_reason_mask_counts": list(weighted_reason_counts),
        "roots": {
            "processed_skeleton_prefix_root": _sequence(
                _skeleton_domain + b"prefix\0",
                (
                    _row_canonical(row)
                    for row in prepared_table._skeleton_rows[:next_skeleton_ordinal]
                ),
            ),
            "ordered_shard_commitment_root": _sequence(
                _checkpoint_domain + b"shards\0", commitments
            ),
        },
    }


@dataclass(frozen=True, init=False)
class StaticCensusCheckpointV1:
    """Immutable process-local prefix token; deliberately has no parser."""

    checkpoint_version: int
    _prepared_table: PreparedStaticCensusTableV1
    next_skeleton_ordinal: int
    _shard_summary_jsons: Tuple[str, ...]
    _representative_reason_counts: Tuple[int, ...]
    _weighted_reason_counts: Tuple[int, ...]
    _construction_snapshot: str

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError(
            "StaticCensusCheckpointV1 values are created only by start/advance"
        )


def _make_checkpoint(
    prepared_table: PreparedStaticCensusTableV1,
    next_skeleton_ordinal: int,
    summary_jsons: Tuple[str, ...],
    representative_reason_counts: Tuple[int, ...],
    weighted_reason_counts: Tuple[int, ...],
    _checkpoint_type: Any = StaticCensusCheckpointV1,
    _body: Any = _checkpoint_body,
    _hash: Any = _domain_hash,
    _canonical: Any = _canonical_json,
    _domain: bytes = _STATIC_CHECKPOINT_DOMAIN,
    _error: Any = StaticCensusClosureError,
) -> StaticCensusCheckpointV1:
    if (
        StaticCensusCheckpointV1 is not _checkpoint_type
        or _checkpoint_body is not _body
        or _domain_hash is not _hash
        or _canonical_json is not _canonical
        or _STATIC_CHECKPOINT_DOMAIN is not _domain
        or StaticCensusClosureError is not _error
    ):
        raise _error("checkpoint maker binding changed")
    body = _body(
        prepared_table,
        next_skeleton_ordinal,
        summary_jsons,
        representative_reason_counts,
        weighted_reason_counts,
    )
    snapshot = _hash(_domain, _canonical(body))
    value = object.__new__(_checkpoint_type)
    object.__setattr__(value, "checkpoint_version", 1)
    object.__setattr__(value, "_prepared_table", prepared_table)
    object.__setattr__(value, "next_skeleton_ordinal", next_skeleton_ordinal)
    object.__setattr__(value, "_shard_summary_jsons", summary_jsons)
    object.__setattr__(
        value, "_representative_reason_counts", representative_reason_counts
    )
    object.__setattr__(value, "_weighted_reason_counts", weighted_reason_counts)
    object.__setattr__(value, "_construction_snapshot", snapshot)
    return value


def _normalize_checkpoint(
    value: Any,
    _checkpoint_type: Any = StaticCensusCheckpointV1,
    _fields: Any = _require_exact_fields,
    _normalize_prepared: Any = _normalize_prepared_table,
    _loads: Any = json.loads,
    _canonical: Any = _canonical_json,
    _validate_shard: Any = _validate_shard_summary,
    _body: Any = _checkpoint_body,
    _hash: Any = _domain_hash,
    _make: Any = _make_checkpoint,
    _expected_skeleton_count: int = _EXPECTED_SKELETON_COUNT,
    _reason_mask_count: int = _REASON_MASK_COUNT,
    _domain: bytes = _STATIC_CHECKPOINT_DOMAIN,
    _error: Any = StaticCensusClosureError,
) -> StaticCensusCheckpointV1:
    if (
        StaticCensusCheckpointV1 is not _checkpoint_type
        or _require_exact_fields is not _fields
        or _normalize_prepared_table is not _normalize_prepared
        or json.loads is not _loads
        or _canonical_json is not _canonical
        or _validate_shard_summary is not _validate_shard
        or _checkpoint_body is not _body
        or _domain_hash is not _hash
        or _make_checkpoint is not _make
        or _EXPECTED_SKELETON_COUNT != _expected_skeleton_count
        or _REASON_MASK_COUNT != _reason_mask_count
        or _STATIC_CHECKPOINT_DOMAIN is not _domain
        or StaticCensusClosureError is not _error
    ):
        raise _error("checkpoint normalizer binding changed")
    if type(value) is not _checkpoint_type:
        raise TypeError("checkpoint must be a StaticCensusCheckpointV1")
    fields = (
        "checkpoint_version",
        "_prepared_table",
        "next_skeleton_ordinal",
        "_shard_summary_jsons",
        "_representative_reason_counts",
        "_weighted_reason_counts",
        "_construction_snapshot",
    )
    _fields(value, fields, "static-census checkpoint")
    snapshot = vars(value).copy()
    if (
        type(snapshot["checkpoint_version"]) is not int
        or snapshot["checkpoint_version"] != 1
        or type(snapshot["next_skeleton_ordinal"]) is not int
        or not 0 <= snapshot["next_skeleton_ordinal"] <= _expected_skeleton_count
        or type(snapshot["_shard_summary_jsons"]) is not tuple
        or len(snapshot["_shard_summary_jsons"])
        != snapshot["next_skeleton_ordinal"]
    ):
        raise ValueError("static-census checkpoint prefix changed")
    prepared = _normalize_prepared(snapshot["_prepared_table"])
    representative_counts = snapshot["_representative_reason_counts"]
    weighted_counts = snapshot["_weighted_reason_counts"]
    for label, counts in (
        ("representative", representative_counts),
        ("weighted", weighted_counts),
    ):
        if (
            type(counts) is not tuple
            or len(counts) != _reason_mask_count
            or any(type(count) is not int or count < 0 for count in counts)
        ):
            raise TypeError("{} reason counts changed".format(label))
    reconstructed_representative = [0] * _reason_mask_count
    reconstructed_weighted = [0] * _reason_mask_count
    canonical_summaries: List[str] = []
    for ordinal, canonical in enumerate(snapshot["_shard_summary_jsons"]):
        if type(canonical) is not str:
            raise TypeError("checkpoint shard summary changed type")
        try:
            summary = _loads(canonical)
        except (TypeError, ValueError) as error:
            raise ValueError("checkpoint shard summary is not JSON") from error
        if _canonical(summary) != canonical:
            raise ValueError("checkpoint shard summary is not canonical")
        _validate_shard(
            summary,
            expected_row=prepared._skeleton_rows[ordinal],
            expected_setup_root=prepared._setup_table._construction_snapshot,
        )
        for combination in summary["eligibility"]["reason_combinations"]:
            mask = combination["reason_mask"]
            reconstructed_representative[mask] += combination[
                "representative_count"
            ]
            reconstructed_weighted[mask] += combination["weighted_count"]
        canonical_summaries.append(canonical)
    if (
        tuple(reconstructed_representative) != representative_counts
        or tuple(reconstructed_weighted) != weighted_counts
    ):
        raise ValueError("checkpoint aggregate reason counts changed")
    body = _body(
        prepared,
        snapshot["next_skeleton_ordinal"],
        tuple(canonical_summaries),
        representative_counts,
        weighted_counts,
    )
    expected_snapshot = _hash(
        _domain, _canonical(body)
    )
    if (
        type(snapshot["_construction_snapshot"]) is not str
        or snapshot["_construction_snapshot"] != expected_snapshot
    ):
        raise ValueError("static-census checkpoint changed after construction")
    return _make(
        prepared,
        snapshot["next_skeleton_ordinal"],
        tuple(canonical_summaries),
        representative_counts,
        weighted_counts,
    )


def start_static_census_checkpoint_v1(
    table: Optional[SetupOrbitTableV1 | PreparedStaticCensusTableV1] = None,
    _version: Any = _official_version,
    _build: Any = build_setup_orbit_table_v1,
    _prepare: Any = prepare_static_census_table_v1,
    _make: Any = _make_checkpoint,
    _reason_mask_count: int = _REASON_MASK_COUNT,
    _error: Any = StaticCensusClosureError,
) -> StaticCensusCheckpointV1:
    """Create the immutable empty prefix for the fixed 1,518-shard run."""

    if (
        _official_version is not _version
        or build_setup_orbit_table_v1 is not _build
        or prepare_static_census_table_v1 is not _prepare
        or _make_checkpoint is not _make
        or _REASON_MASK_COUNT != _reason_mask_count
        or StaticCensusClosureError is not _error
    ):
        raise _error("checkpoint start binding changed")
    _version()
    source_table: SetupOrbitTableV1 | PreparedStaticCensusTableV1
    source_table = _build() if table is None else table
    prepared = _prepare(source_table)
    zeros = (0,) * _reason_mask_count
    return _make(prepared, 0, (), zeros, zeros)


def advance_static_census_checkpoint_v1(
    checkpoint: StaticCensusCheckpointV1,
    _version: Any = _official_version,
    _normalize: Any = _normalize_checkpoint,
    _derive: Any = _derive_shard_core,
    _summary: Any = static_census_shard_summary_v1,
    _canonical: Any = _canonical_json,
    _make: Any = _make_checkpoint,
    _expected_skeleton_count: int = _EXPECTED_SKELETON_COUNT,
    _error: Any = StaticCensusClosureError,
) -> StaticCensusCheckpointV1:
    """Atomically append one shard after fully validating the existing prefix.

    Validation is deliberately O(prefix), so repeating this single-step helper
    for all 1,518 shards is O(shards squared).  It is a strict diagnostic
    boundary, not the production full-census path; use
    :func:`build_static_census_v1` for the linear derivation loop.
    """

    if (
        _official_version is not _version
        or _normalize_checkpoint is not _normalize
        or _derive_shard_core is not _derive
        or static_census_shard_summary_v1 is not _summary
        or _canonical_json is not _canonical
        or _make_checkpoint is not _make
        or _EXPECTED_SKELETON_COUNT != _expected_skeleton_count
        or StaticCensusClosureError is not _error
    ):
        raise _error("checkpoint advance binding changed")
    _version()
    source = _normalize(checkpoint)
    ordinal = source.next_skeleton_ordinal
    if ordinal == _expected_skeleton_count:
        raise ValueError("static-census checkpoint is already complete")
    shard = _derive(source._prepared_table, ordinal)
    summary = _summary(shard)
    canonical = _canonical(summary)
    representative_counts = list(source._representative_reason_counts)
    weighted_counts = list(source._weighted_reason_counts)
    for combination in summary["eligibility"]["reason_combinations"]:
        mask = combination["reason_mask"]
        representative_counts[mask] += combination["representative_count"]
        weighted_counts[mask] += combination["weighted_count"]
    return _make(
        source._prepared_table,
        ordinal + 1,
        source._shard_summary_jsons + (canonical,),
        tuple(representative_counts),
        tuple(weighted_counts),
    )


def static_census_checkpoint_progress_v1(
    checkpoint: StaticCensusCheckpointV1,
    _normalize: Any = _normalize_checkpoint,
    _body: Any = _checkpoint_body,
    _expected_skeleton_count: int = _EXPECTED_SKELETON_COUNT,
    _error: Any = StaticCensusClosureError,
) -> Dict[str, Any]:
    """Return detached progress only; this is not a resume serialization."""

    if (
        _normalize_checkpoint is not _normalize
        or _checkpoint_body is not _body
        or _EXPECTED_SKELETON_COUNT != _expected_skeleton_count
        or StaticCensusClosureError is not _error
    ):
        raise _error("checkpoint progress binding changed")
    source = _normalize(checkpoint)
    body = _body(
        source._prepared_table,
        source.next_skeleton_ordinal,
        source._shard_summary_jsons,
        source._representative_reason_counts,
        source._weighted_reason_counts,
    )
    return {
        "static_census_checkpoint_version": 1,
        "next_skeleton_ordinal": body["next_skeleton_ordinal"],
        "processed_skeleton_count": body["processed_skeleton_count"],
        "remaining_skeleton_count": body["remaining_skeleton_count"],
        "complete": body["next_skeleton_ordinal"] == _expected_skeleton_count,
        "processed_factorized_carrier_count": body[
            "processed_factorized_carrier_count"
        ],
        "processed_labeled_setup_count": body["processed_labeled_setup_count"],
        "processed_paired_first_player_member_count": body[
            "processed_paired_first_player_member_count"
        ],
        "representative_eligible_count": body["representative_eligible_count"],
        "weighted_eligible_count": body["weighted_eligible_count"],
        "setup_orbit_table_root": body["setup_orbit_table_root"],
        "skeleton_authority_root": body["skeleton_authority_root"],
        "processed_skeleton_prefix_root": body["roots"][
            "processed_skeleton_prefix_root"
        ],
        "ordered_shard_commitment_root": body["roots"][
            "ordered_shard_commitment_root"
        ],
    }


def _global_report_body(
    setup_descriptor: Dict[str, Any],
    skeleton_descriptor: Dict[str, Any],
    summary_jsons: Tuple[str, ...],
    _descriptor_validator: Any = _validate_embedded_descriptor,
    _validate_shard: Any = _validate_shard_summary,
    _skeleton_descriptor: Any = _skeleton_authority_descriptor,
    _new_work: Any = _new_work_extrema,
    _freeze_work: Any = _freeze_work_extrema,
    _loads: Any = json.loads,
    _canonical: Any = _canonical_json,
    _sequence: Any = _sequence_root,
    _setup_descriptor_domain: bytes = _SETUP_DESCRIPTOR_DOMAIN,
    _skeleton_descriptor_domain: bytes = _SKELETON_DESCRIPTOR_ROOT_DOMAIN,
    _expected_setup_root: str = _EXPECTED_SETUP_ORBIT_TABLE_ROOT,
    _expected_skeleton_root: str = _EXPECTED_SKELETON_AUTHORITY_ROOT,
    _expected_skeleton_count: int = _EXPECTED_SKELETON_COUNT,
    _expected_factorized_count: int = _EXPECTED_FACTORIZED_CARRIER_COUNT,
    _expected_labeled_count: int = _EXPECTED_LABELED_SETUP_COUNT,
    _expected_paired_count: int = _EXPECTED_PAIRED_MEMBER_COUNT,
    _expected_count_root: str = _EXPECTED_COUNT_TABLE_ROOT,
    _all_contribution: int = _EXPECTED_ALL_ORDERED_CONTRIBUTION,
    _self_contribution: int = _EXPECTED_SELF_ISOMORPHIC_CONTRIBUTION,
    _old_contribution: int = _EXPECTED_OLD_REGION_CONTRIBUTION,
    _global_histogram: Tuple[Tuple[int, int], ...] = _GLOBAL_WEIGHT_HISTOGRAM,
    _reason_mask_count: int = _REASON_MASK_COUNT,
    _contact_classes: Tuple[str, ...] = _CONTACT_CLASSES,
    _count_pairs: Tuple[CountPair, ...] = _COUNT_PAIRS,
    _descriptor_groups: Tuple[str, ...] = _DESCRIPTOR_GROUPS,
    _first_players: Tuple[str, ...] = _FIRST_PLAYERS,
    _work_fields: Tuple[str, ...] = _WORK_FIELDS,
    _signatures: Tuple[StabilizerSignature, ...] = _STABILIZER_SIGNATURES,
    _stabilizer_counts: Tuple[int, ...] = _STABILIZER_SKELETON_COUNTS,
    _orbit_counts: Tuple[int, ...] = _SETUP_ORBIT_COUNTS,
    _weight_histograms: Tuple[Tuple[Tuple[int, int], ...], ...] = _SETUP_WEIGHT_HISTOGRAMS,
    _checkpoint_domain: bytes = _STATIC_CHECKPOINT_DOMAIN,
    _report_domain: bytes = _STATIC_REPORT_BODY_DOMAIN,
    _error: Any = StaticCensusClosureError,
) -> Dict[str, Any]:
    if (
        _validate_embedded_descriptor is not _descriptor_validator
        or _validate_shard_summary is not _validate_shard
        or _skeleton_authority_descriptor is not _skeleton_descriptor
        or _new_work_extrema is not _new_work
        or _freeze_work_extrema is not _freeze_work
        or json.loads is not _loads
        or _canonical_json is not _canonical
        or _sequence_root is not _sequence
        or _SETUP_DESCRIPTOR_DOMAIN is not _setup_descriptor_domain
        or _SKELETON_DESCRIPTOR_ROOT_DOMAIN is not _skeleton_descriptor_domain
        or _EXPECTED_SETUP_ORBIT_TABLE_ROOT != _expected_setup_root
        or _EXPECTED_SKELETON_AUTHORITY_ROOT != _expected_skeleton_root
        or _EXPECTED_SKELETON_COUNT != _expected_skeleton_count
        or _EXPECTED_FACTORIZED_CARRIER_COUNT != _expected_factorized_count
        or _EXPECTED_LABELED_SETUP_COUNT != _expected_labeled_count
        or _EXPECTED_PAIRED_MEMBER_COUNT != _expected_paired_count
        or _EXPECTED_COUNT_TABLE_ROOT != _expected_count_root
        or _EXPECTED_ALL_ORDERED_CONTRIBUTION != _all_contribution
        or _EXPECTED_SELF_ISOMORPHIC_CONTRIBUTION != _self_contribution
        or _EXPECTED_OLD_REGION_CONTRIBUTION != _old_contribution
        or _GLOBAL_WEIGHT_HISTOGRAM is not _global_histogram
        or _REASON_MASK_COUNT != _reason_mask_count
        or _CONTACT_CLASSES is not _contact_classes
        or _COUNT_PAIRS is not _count_pairs
        or _DESCRIPTOR_GROUPS is not _descriptor_groups
        or _FIRST_PLAYERS is not _first_players
        or _WORK_FIELDS is not _work_fields
        or _STABILIZER_SIGNATURES is not _signatures
        or _STABILIZER_SKELETON_COUNTS is not _stabilizer_counts
        or _SETUP_ORBIT_COUNTS is not _orbit_counts
        or _SETUP_WEIGHT_HISTOGRAMS is not _weight_histograms
        or _STATIC_CHECKPOINT_DOMAIN is not _checkpoint_domain
        or _STATIC_REPORT_BODY_DOMAIN is not _report_domain
        or StaticCensusClosureError is not _error
    ):
        raise _error("global report binding changed")
    setup_descriptor = _descriptor_validator(
        setup_descriptor,
        "report setup authority",
        _setup_descriptor_domain,
        _expected_setup_root,
    )
    skeleton_descriptor = _descriptor_validator(
        skeleton_descriptor,
        "report skeleton authority",
        _skeleton_descriptor_domain,
        _expected_skeleton_root,
    )
    if len(summary_jsons) != _expected_skeleton_count:
        raise ValueError("report requires all 1,518 skeleton shards")

    reason_rep = [0] * _reason_mask_count
    reason_weight = [0] * _reason_mask_count
    weight_histogram: Dict[int, int] = {}
    signature_counts: Dict[StabilizerSignature, int] = {}
    contact_counts = {
        contact_class: {
            "representative_count": 0,
            "weighted_count": 0,
            "eligible_representative_count": 0,
            "eligible_weighted_count": 0,
        }
        for contact_class in _contact_classes
    }
    supply_rep: Dict[Tuple[int, int, str], int] = {}
    supply_weight: Dict[Tuple[int, int, str], int] = {}
    extrema = _new_work()
    summaries: List[Dict[str, Any]] = []
    commitments: List[str] = []
    leaf_commitment_roots: List[str] = []
    result_roots: List[str] = []
    role_roots: List[str] = []
    count_roots: List[str] = []
    group_roots: Dict[str, List[str]] = {
        name: [] for name in _descriptor_groups
    }
    skeleton_rows: List[_SkeletonRow] = []

    for ordinal, canonical in enumerate(summary_jsons):
        if type(canonical) is not str:
            raise TypeError("report shard summary changed type")
        try:
            summary = _loads(canonical)
        except (TypeError, ValueError) as error:
            raise ValueError("report shard summary is not JSON") from error
        if _canonical(summary) != canonical:
            raise ValueError("report shard summary is not canonical")
        _validate_shard(
            summary, expected_setup_root=_expected_setup_root
        )
        if summary["skeleton"]["ordinal"] != ordinal:
            raise ValueError("report shard order is not the exact skeleton order")
        skeleton = summary["skeleton"]
        signature = tuple(skeleton["exact_stabilizer"])
        signature_counts[signature] = signature_counts.get(signature, 0) + 1
        group_index = _signatures.index(signature)
        skeleton_rows.append(
            (
                ordinal,
                skeleton["canonical_profiled_skeleton_json"],
                skeleton["typed_skeleton_hash"],
                skeleton["role_neutral_skeleton_hash"],
                skeleton["role_neutral_semantic_hash"],
                signature,
                _orbit_counts[group_index],
                _weight_histograms[group_index],
            )
        )
        for weight_text, count in summary["setup_orbit"]["weight_histogram"].items():
            weight = int(weight_text)
            weight_histogram[weight] = weight_histogram.get(weight, 0) + count
        for combination in summary["eligibility"]["reason_combinations"]:
            mask = combination["reason_mask"]
            reason_rep[mask] += combination["representative_count"]
            reason_weight[mask] += combination["weighted_count"]
        for contact_class in _contact_classes:
            source_contact = summary["contact"][contact_class]
            for field in contact_counts[contact_class]:
                contact_counts[contact_class][field] += source_contact[field]
        for supply_row in summary["eligible_supply_by_count_pair_and_contact"]:
            counts = supply_row["initial_counts"]
            supply_key = (counts["A"], counts["B"], supply_row["contact_class"])
            supply_rep[supply_key] = (
                supply_rep.get(supply_key, 0) + supply_row["representative_count"]
            )
            supply_weight[supply_key] = (
                supply_weight.get(supply_key, 0) + supply_row["weighted_count"]
            )
        for first_player in _first_players:
            for field in _work_fields:
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
        leaf_commitment_roots.append(roots["ordered_leaf_commitment_root"])
        result_roots.append(roots["ordered_initial_structure_result_root"])
        role_roots.append(roots["ordered_role_facts_root"])
        count_roots.append(roots["ordered_count_lattice_root"])
        for name in _descriptor_groups:
            group_roots[name].append(
                roots["ordered_descriptor_group_roots"][name]
            )
        summaries.append(summary)

    if tuple(signature_counts.get(signature, 0) for signature in _signatures) != _stabilizer_counts:
        raise _error("report stabilizer distribution changed")
    if tuple(sorted(weight_histogram.items())) != _global_histogram:
        raise _error("report global setup weights changed")
    if (
        sum(reason_rep) != _expected_factorized_count
        or sum(reason_weight) != _expected_labeled_count
    ):
        raise _error("report reason totals changed")
    reconstructed_skeleton_descriptor = _skeleton_descriptor(
        tuple(skeleton_rows),
        _all_contribution,
        _self_contribution,
        _old_contribution,
    )
    if reconstructed_skeleton_descriptor != skeleton_descriptor:
        raise ValueError("report shards do not reconstruct the skeleton authority")

    eligible_rep = reason_rep[0]
    eligible_weight = reason_weight[0]
    supply_rows = [
        {
            "initial_counts": {"A": count_pair[0], "B": count_pair[1]},
            "contact_class": contact_class,
            "representative_count": supply_rep.get(
                (count_pair[0], count_pair[1], contact_class), 0
            ),
            "weighted_count": supply_weight.get(
                (count_pair[0], count_pair[1], contact_class), 0
            ),
        }
        for count_pair in _count_pairs
        for contact_class in _contact_classes
    ]
    body = {
        "static_census_report_version": 1,
        "authorities": {
            "setup_orbit_table": setup_descriptor,
            "skeleton_authority": skeleton_descriptor,
            "initial_structure_kernel_version": 1,
            "count_lattice_table_root": _expected_count_root,
        },
        "population": {
            "skeleton_count": _expected_skeleton_count,
            "factorized_carrier_count": _expected_factorized_count,
            "labeled_setup_count": _expected_labeled_count,
            "paired_first_player_member_count": _expected_paired_count,
            "weight_histogram": {
                str(weight): count for weight, count in _global_histogram
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
        "work_extrema": _freeze_work(extrema),
        "roots": {
            "ordered_shard_commitment_root": _sequence(
                _checkpoint_domain + b"shards\0", commitments
            ),
            "ordered_leaf_commitment_shard_root": _sequence(
                _report_domain + b"leaf-commitment-shards\0",
                leaf_commitment_roots,
            ),
            "ordered_initial_structure_result_shard_root": _sequence(
                _report_domain + b"result-shards\0", result_roots
            ),
            "ordered_role_facts_shard_root": _sequence(
                _report_domain + b"role-shards\0", role_roots
            ),
            "ordered_count_lattice_shard_root": _sequence(
                _report_domain + b"count-shards\0", count_roots
            ),
            "ordered_descriptor_group_shard_roots": {
                name: _sequence(
                    _report_domain
                    + b"descriptor-shards\0"
                    + name.encode("ascii")
                    + b"\0",
                    group_roots[name],
                )
                for name in _descriptor_groups
            },
        },
        "skeleton_shards": summaries,
    }
    return body


@dataclass(frozen=True, init=False)
class StaticCensusReportV1:
    """Complete output-only report; no public parser accepts stored bytes."""

    report_version: int
    _canonical_payload_json: str
    _construction_snapshot: str

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("StaticCensusReportV1 values are created only by finalization")


def _make_report(
    payload: Dict[str, Any],
    _report_type: Any = StaticCensusReportV1,
    _canonical: Any = _canonical_json,
    _sha_validator: Any = _is_sha256,
    _error: Any = StaticCensusClosureError,
) -> StaticCensusReportV1:
    if (
        StaticCensusReportV1 is not _report_type
        or _canonical_json is not _canonical
        or _is_sha256 is not _sha_validator
        or StaticCensusClosureError is not _error
    ):
        raise _error("report maker binding changed")
    canonical = _canonical(payload)
    digest = payload.get("report_digest")
    if not _sha_validator(digest):
        raise ValueError("static-census report digest is invalid")
    value = object.__new__(_report_type)
    object.__setattr__(value, "report_version", 1)
    object.__setattr__(value, "_canonical_payload_json", canonical)
    object.__setattr__(value, "_construction_snapshot", digest)
    return value


def _validate_report_payload(
    payload_value: Any,
    _exact: Any = _exact_dict,
    _tree: Any = _validate_json_tree,
    _keys: Any = _exact_keys,
    _descriptor_validator: Any = _validate_embedded_descriptor,
    _global: Any = _global_report_body,
    _canonical: Any = _canonical_json,
    _hash: Any = _domain_hash,
    _setup_descriptor_domain: bytes = _SETUP_DESCRIPTOR_DOMAIN,
    _skeleton_descriptor_domain: bytes = _SKELETON_DESCRIPTOR_ROOT_DOMAIN,
    _expected_setup_root: str = _EXPECTED_SETUP_ORBIT_TABLE_ROOT,
    _expected_skeleton_root: str = _EXPECTED_SKELETON_AUTHORITY_ROOT,
    _expected_count_root: str = _EXPECTED_COUNT_TABLE_ROOT,
    _max_depth: int = _MAX_JSON_DEPTH,
    _report_domain: bytes = _STATIC_REPORT_BODY_DOMAIN,
    _error: Any = StaticCensusClosureError,
) -> Dict[str, Any]:
    if (
        _exact_dict is not _exact
        or _validate_json_tree is not _tree
        or _exact_keys is not _keys
        or _validate_embedded_descriptor is not _descriptor_validator
        or _global_report_body is not _global
        or _canonical_json is not _canonical
        or _domain_hash is not _hash
        or _SETUP_DESCRIPTOR_DOMAIN is not _setup_descriptor_domain
        or _SKELETON_DESCRIPTOR_ROOT_DOMAIN is not _skeleton_descriptor_domain
        or _EXPECTED_SETUP_ORBIT_TABLE_ROOT != _expected_setup_root
        or _EXPECTED_SKELETON_AUTHORITY_ROOT != _expected_skeleton_root
        or _EXPECTED_COUNT_TABLE_ROOT != _expected_count_root
        or _MAX_JSON_DEPTH != _max_depth
        or _STATIC_REPORT_BODY_DOMAIN is not _report_domain
        or StaticCensusClosureError is not _error
    ):
        raise _error("report validator binding changed")
    payload = _exact(payload_value, "static-census report")
    _tree(
        payload,
        "static-census report",
        max_nodes=5_000_000,
        max_depth=_max_depth,
    )
    _keys(
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
    if (
        type(payload["static_census_report_version"]) is not int
        or payload["static_census_report_version"] != 1
    ):
        raise ValueError("static-census report version changed")
    authorities = _exact(payload["authorities"], "report authorities")
    _keys(
        authorities,
        (
            "setup_orbit_table",
            "skeleton_authority",
            "initial_structure_kernel_version",
            "count_lattice_table_root",
        ),
        "report authorities",
    )
    if (
        type(authorities["initial_structure_kernel_version"]) is not int
        or authorities["initial_structure_kernel_version"] != 1
        or authorities["count_lattice_table_root"] != _expected_count_root
        or type(payload["skeleton_shards"]) is not list
    ):
        raise ValueError("static-census report authority changed")
    _descriptor_validator(
        authorities["setup_orbit_table"],
        "report setup authority",
        _setup_descriptor_domain,
        _expected_setup_root,
    )
    _descriptor_validator(
        authorities["skeleton_authority"],
        "report skeleton authority",
        _skeleton_descriptor_domain,
        _expected_skeleton_root,
    )
    summary_jsons = tuple(
        _canonical(summary) for summary in payload["skeleton_shards"]
    )
    expected_body = _global(
        authorities["setup_orbit_table"],
        authorities["skeleton_authority"],
        summary_jsons,
    )
    body = dict(payload)
    digest = body.pop("report_digest")
    body_canonical = _canonical(body)
    expected_body_canonical = _canonical(expected_body)
    if body_canonical != expected_body_canonical:
        raise ValueError("static-census report aggregate changed")
    expected_digest = _hash(
        _report_domain, body_canonical
    )
    if digest != expected_digest:
        raise ValueError("static-census report digest changed")
    return payload


def _normalize_report(
    value: Any,
    _report_type: Any = StaticCensusReportV1,
    _fields: Any = _require_exact_fields,
    _loads: Any = json.loads,
    _canonical: Any = _canonical_json,
    _validate: Any = _validate_report_payload,
    _make: Any = _make_report,
    _error: Any = StaticCensusClosureError,
) -> StaticCensusReportV1:
    if (
        StaticCensusReportV1 is not _report_type
        or _require_exact_fields is not _fields
        or json.loads is not _loads
        or _canonical_json is not _canonical
        or _validate_report_payload is not _validate
        or _make_report is not _make
        or StaticCensusClosureError is not _error
    ):
        raise _error("report normalizer binding changed")
    if type(value) is not _report_type:
        raise TypeError("report must be a StaticCensusReportV1")
    fields = ("report_version", "_canonical_payload_json", "_construction_snapshot")
    _fields(value, fields, "static-census report")
    snapshot = vars(value).copy()
    if (
        type(snapshot["report_version"]) is not int
        or snapshot["report_version"] != 1
        or type(snapshot["_canonical_payload_json"]) is not str
    ):
        raise TypeError("static-census report fields changed")
    try:
        payload = _loads(snapshot["_canonical_payload_json"])
    except (TypeError, ValueError) as error:
        raise ValueError("static-census report is not JSON") from error
    if _canonical(payload) != snapshot["_canonical_payload_json"]:
        raise ValueError("static-census report is not canonical")
    _validate(payload)
    if (
        type(snapshot["_construction_snapshot"]) is not str
        or snapshot["_construction_snapshot"] != payload["report_digest"]
    ):
        raise ValueError("static-census report changed after construction")
    return _make(payload)


def finalize_static_census_v1(
    checkpoint: StaticCensusCheckpointV1,
    _version: Any = _official_version,
    _normalize: Any = _normalize_checkpoint,
    _global: Any = _global_report_body,
    _validate: Any = _validate_report_payload,
    _make: Any = _make_report,
    _canonical: Any = _canonical_json,
    _hash: Any = _domain_hash,
    _loads: Any = json.loads,
    _expected_skeleton_count: int = _EXPECTED_SKELETON_COUNT,
    _report_domain: bytes = _STATIC_REPORT_BODY_DOMAIN,
    _error: Any = StaticCensusClosureError,
) -> StaticCensusReportV1:
    """Finalize only the exact complete prefix; partial prefixes are rejected."""

    if (
        _official_version is not _version
        or _normalize_checkpoint is not _normalize
        or _global_report_body is not _global
        or _validate_report_payload is not _validate
        or _make_report is not _make
        or _canonical_json is not _canonical
        or _domain_hash is not _hash
        or json.loads is not _loads
        or _EXPECTED_SKELETON_COUNT != _expected_skeleton_count
        or _STATIC_REPORT_BODY_DOMAIN is not _report_domain
        or StaticCensusClosureError is not _error
    ):
        raise _error("static-census finalization binding changed")
    _version()
    source = _normalize(checkpoint)
    if source.next_skeleton_ordinal != _expected_skeleton_count:
        raise ValueError("static census cannot finalize before all shards complete")
    setup_descriptor = _loads(source._prepared_table._setup_table._descriptor_json)
    skeleton_descriptor = _loads(
        source._prepared_table._skeleton_descriptor_json
    )
    body = _global(
        setup_descriptor,
        skeleton_descriptor,
        source._shard_summary_jsons,
    )
    payload = dict(body)
    payload["report_digest"] = _hash(
        _report_domain, _canonical(body)
    )
    _validate(payload)
    return _make(payload)


def canonical_static_census_report_json_v1(
    report: StaticCensusReportV1,
    _normalize: Any = _normalize_report,
    _error: Any = StaticCensusClosureError,
) -> str:
    """Serialize an exact live output token; no inverse parser is provided."""

    if (
        _normalize_report is not _normalize
        or StaticCensusClosureError is not _error
    ):
        raise _error("static-census report serializer binding changed")
    return _normalize(report)._canonical_payload_json


def static_census_report_hash_v1(
    report: StaticCensusReportV1,
    _normalize: Any = _normalize_report,
    _error: Any = StaticCensusClosureError,
) -> str:
    """Return the report-body digest of an exact live output token."""

    if (
        _normalize_report is not _normalize
        or StaticCensusClosureError is not _error
    ):
        raise _error("static-census report hash binding changed")
    return _normalize(report)._construction_snapshot


def build_static_census_v1(
    table: Optional[SetupOrbitTableV1 | PreparedStaticCensusTableV1] = None,
    _version: Any = _official_version,
    _build_setup: Any = build_setup_orbit_table_v1,
    _prepare: Any = prepare_static_census_table_v1,
    _derive: Any = _derive_shard_core,
    _make: Any = _make_checkpoint,
    _finalize: Any = finalize_static_census_v1,
    _loads: Any = json.loads,
    _expected_skeleton_count: int = _EXPECTED_SKELETON_COUNT,
    _reason_mask_count: int = _REASON_MASK_COUNT,
    _error: Any = StaticCensusClosureError,
) -> StaticCensusReportV1:
    """Run the complete census through one prepared linear derivation loop.

    The authority is prepared once before exactly 1,518 shard derivations.
    Final checkpoint and report construction intentionally revalidate compact
    authorities and shard summaries; they do not revisit the 5,111,055 carrier
    derivations or materialize that carrier domain.
    """

    if (
        _official_version is not _version
        or build_setup_orbit_table_v1 is not _build_setup
        or prepare_static_census_table_v1 is not _prepare
        or _derive_shard_core is not _derive
        or _make_checkpoint is not _make
        or finalize_static_census_v1 is not _finalize
        or json.loads is not _loads
        or _EXPECTED_SKELETON_COUNT != _expected_skeleton_count
        or _REASON_MASK_COUNT != _reason_mask_count
        or StaticCensusClosureError is not _error
    ):
        raise _error("one-shot census binding changed")
    _version()
    source_table: SetupOrbitTableV1 | PreparedStaticCensusTableV1
    source_table = _build_setup() if table is None else table
    prepared = _prepare(source_table)
    summary_jsons: List[str] = []
    representative_counts = [0] * _reason_mask_count
    weighted_counts = [0] * _reason_mask_count
    for ordinal in range(_expected_skeleton_count):
        shard = _derive(prepared, ordinal)
        canonical = shard._summary_json
        summary = _loads(canonical)
        summary_jsons.append(canonical)
        for combination in summary["eligibility"]["reason_combinations"]:
            mask = combination["reason_mask"]
            representative_counts[mask] += combination["representative_count"]
            weighted_counts[mask] += combination["weighted_count"]
    checkpoint = _make(
        prepared,
        _expected_skeleton_count,
        tuple(summary_jsons),
        tuple(representative_counts),
        tuple(weighted_counts),
    )
    return _finalize(checkpoint)


__all__ = [
    "STATIC_CENSUS_VERSION_V1",
    "SETUP_ORBIT_TABLE_VERSION_V1",
    "STATIC_CENSUS_SHARD_VERSION_V1",
    "STATIC_CENSUS_CHECKPOINT_VERSION_V1",
    "STATIC_CENSUS_REPORT_VERSION_V1",
    "StaticCensusClosureError",
    "SetupOrbitTableV1",
    "PreparedStaticCensusTableV1",
    "StaticCensusShardV1",
    "StaticCensusCheckpointV1",
    "StaticCensusReportV1",
    "build_setup_orbit_table_v1",
    "setup_orbit_table_descriptor_v1",
    "setup_orbit_table_hash_v1",
    "prepare_static_census_table_v1",
    "derive_static_census_shard_v1",
    "static_census_shard_summary_v1",
    "start_static_census_checkpoint_v1",
    "advance_static_census_checkpoint_v1",
    "static_census_checkpoint_progress_v1",
    "finalize_static_census_v1",
    "canonical_static_census_report_json_v1",
    "static_census_report_hash_v1",
    "build_static_census_v1",
]
