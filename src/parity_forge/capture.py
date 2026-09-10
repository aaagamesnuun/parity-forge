"""Pure protocol and evidence helpers for the schema-v3 capture experiment.

This module intentionally contains no filesystem, Git, or reservation I/O.  It
accepts already loaded records and injected clocks, rejects ambiguous evidence,
and returns detached JSON values.  Experiment runners can therefore keep their
one-shot side effects at the edge while using the same functions for construction
and public validation.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Sequence, Set, Tuple

from .agents import GoalDirectedAgent, MinimaxAgent, RandomAgent, SearchBudgetExceeded
from .analysis import FailureCode, analyze_definition
from .asymmetry import evaluate_asymmetry
from .audit import sampled_direction
from .batch import PlayGates, classify_play_failures
from .dsl import (
    ActionKind,
    GameDefinition,
    GoalKind,
    Player,
    definition_hash,
    parse_definition,
)
from .engine import Action, GameState, action_from_dict, apply_action, initial_state
from .play import GameRecord, MatchupResult, evaluate_matchup, play_game
from .simplicity import evaluate_simplicity, exceeds_limits
from .solver import SolveBudgetExceeded, solve_game
from .symmetry import d4_canonical_hash


CAPTURE_MANIFEST_VERSION = 1
CAPTURE_MANIFEST_ID = "generator-v2-3x3-capture-paired-v1"
CAPTURE_PROTOCOL_ID = "capture-v1-paired-manifest-freeze"
CAPTURE_SOURCE_MANIFEST_ID = "generator-v2-3x3-landscape-v1"
CAPTURE_SOURCE_MANIFEST_SHA256 = (
    "f407aefb5fdb8c926db282ff90d2feb1a8666cda3fdbd6925b9f5cc07abd87b1"
)
CAPTURE_SOURCE_CASE_COUNT = 384
CAPTURE_PAIR_COUNT = 128
CAPTURE_STRATUM_COUNT = 32
CAPTURE_QUOTA_PER_STRATUM = 4
CAPTURE_MAX_PLIES = 18
CAPTURE_STATE_BOUND = 43_776
CAPTURE_EXACT_MAX_STATES = 100_000
CAPTURE_PLAY_SEEDS = tuple(range(30))

CAPTURE_REPLAY_ATTESTATION_VERSION = "capture-v1-replay-attestation-v1"
CAPTURE_REPLAY_CASE_DOMAIN = b"capture-v1-replay-case-v1"
CAPTURE_REPLAY_ORDER_DOMAIN = b"capture-v1-replay-order-v1"

CAPTURE_STRESS_DEPTH = 5
CAPTURE_STRESS_MAX_CANDIDATES = 32
CAPTURE_STRESS_MAX_NODES = 5_000_000
CAPTURE_STRESS_SEEDS = tuple(range(30))

_PAIR_FINGERPRINT_DOMAIN = b"capture-v1-pair-v1"
_CAPTURE_SELECTION_PREFIX = "capture-v1-pair:"
_STRESS_CLEAN_PREFIX = "capture-stress-clean-v1:"
_STRESS_OTHER_PREFIX = "capture-stress-other-v1:"
_INSPECTION_CHANGE_PREFIX = "capture-inspection-change-v1:"
_INSPECTION_CONTROL_PREFIX = "capture-inspection-control-v1:"
_FORCED_RESULTS = ("A_WIN", "B_WIN", "DRAW")
_VALUE_BY_RESULT = {"B_WIN": -1, "DRAW": 0, "A_WIN": 1}
_SHAPE_FAILURES = frozenset(
    (
        FailureCode.EXCESSIVE_DRAWS.value,
        FailureCode.TOO_SHORT.value,
        FailureCode.TOO_LONG.value,
    )
)
_SOURCE_CASE_KEYS = frozenset(
    (
        "case_id",
        "stratum",
        "vector_count",
        "definition_hash",
        "d4_canonical_hash",
        "definition",
        "selection_rank",
        "selection_score",
    )
)
_PAIR_KEYS = frozenset(
    (
        "pair_id",
        "source_case_id",
        "source_definition_hash",
        "source_d4_canonical_hash",
        "stratum",
        "vector_count",
        "source_definition",
        "treatment_definition_hash",
        "treatment_d4_canonical_hash",
        "treatment_definition",
        "pair_fingerprint",
        "selection_rank",
        "selection_score",
    )
)
_PROJECTION_KEYS = frozenset(
    (
        "pair_id",
        "case_id",
        "definition_hash",
        "d4_canonical_hash",
        "stratum",
        "vector_count",
        "definition",
        "static",
        "asymmetry",
        "simplicity",
        "simplicity_passes",
        "analysis_gate_passes",
        "cheap_profiles",
        "cheap_failure_codes",
        "exact",
    )
)
_TREATMENT_CANDIDATE_KEYS = frozenset(
    (
        "manifest_index",
        "pair_id",
        "source_case_id",
        "definition_hash",
        "d4_canonical_hash",
        "stratum",
        "vector_count",
        "definition",
        "static",
        "asymmetry",
        "simplicity",
        "simplicity_passes",
        "analysis_gate_passes",
        "cheap_profiles",
        "cheap_capture_evidence",
        "cheap_failure_codes",
        "exact",
        "exact_capture_evidence",
        "timing",
    )
)
_BASELINE_CANDIDATE_KEYS = frozenset(
    (
        "manifest_index",
        "case_id",
        "definition_hash",
        "d4_canonical_hash",
        "stratum",
        "vector_count",
        "definition",
        "static",
        "asymmetry",
        "simplicity",
        "simplicity_passes",
        "analysis_gate_passes",
        "cheap_profiles",
        "cheap_failure_codes",
        "exact",
        "timing",
    )
)


@dataclass(frozen=True)
class CaptureManifestContract:
    """Cardinality contract; tests may use a tiny, explicit analogue."""

    source_case_count: int = CAPTURE_SOURCE_CASE_COUNT
    pair_count: int = CAPTURE_PAIR_COUNT
    stratum_count: int = CAPTURE_STRATUM_COUNT
    quota_per_stratum: int = CAPTURE_QUOTA_PER_STRATUM

    def validate(self) -> None:
        for field, value in asdict(self).items():
            if type(value) is not int or value < 1:
                raise ValueError("{} must be a positive integer".format(field))
        if self.pair_count != self.stratum_count * self.quota_per_stratum:
            raise ValueError("pair count must equal stratum count times quota")


DEFAULT_CAPTURE_MANIFEST_CONTRACT = CaptureManifestContract()


def _json_copy(value: Any, label: str) -> Any:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        raise ValueError("{} must be JSON-serializable".format(label)) from error
    return json.loads(encoded)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _domain_digest(domain: bytes, value: Any) -> str:
    return hashlib.sha256(domain + b"\0" + _canonical_bytes(value)).hexdigest()


def _require_sha256(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError("{} must be a lowercase SHA-256 hex digest".format(label))
    return value


def _exact_keys(value: Any, expected: Iterable[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("{} must be an object".format(label))
    if set(value) != set(expected):
        raise ValueError(
            "{} fields mismatch: expected {}, observed {}".format(
                label, sorted(expected), sorted(value)
            )
        )
    return value


def _strict_bool(value: Any, label: str) -> bool:
    if type(value) is not bool:
        raise ValueError("{} must be a boolean".format(label))
    return value


def _strict_nonnegative_int(value: Any, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("{} must be a nonnegative integer".format(label))
    return value


def _strict_positive_int(value: Any, label: str) -> int:
    value = _strict_nonnegative_int(value, label)
    if value == 0:
        raise ValueError("{} must be positive".format(label))
    return value


def _stratum_identity(value: Any) -> str:
    if not isinstance(value, Mapping) or not value:
        raise ValueError("stratum must be a nonempty object")
    return _canonical_bytes(value).decode("utf-8")


def _validate_seed_sequence(seeds: Sequence[int], label: str) -> Tuple[int, ...]:
    result = tuple(seeds)
    if not result:
        raise ValueError("{} requires at least one seed".format(label))
    if any(type(seed) is not int for seed in result):
        raise ValueError("{} seeds must be integers (not booleans)".format(label))
    if len(set(result)) != len(result):
        raise ValueError("{} seeds must be unique".format(label))
    return result


def _contains_forbidden_outcome_key(value: Any) -> bool:
    forbidden = {
        "actual_result",
        "result",
        "results",
        "outcome",
        "winner",
        "terminal_reason",
        "value_for_a",
        "forced_result",
        "principal_variation",
        "evaluation",
        "evaluations",
        "analysis_gate_passes",
        "cheap_profiles",
        "cheap_failure_codes",
        "failure_codes",
        "play_profiles",
        "solve",
        "exact",
        "assessment",
        "assessments",
    }
    if isinstance(value, Mapping):
        return any(
            key in forbidden or _contains_forbidden_outcome_key(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_forbidden_outcome_key(item) for item in value)
    return False


def _validate_source_family(definition: GameDefinition) -> None:
    if definition.schema_version != 1:
        raise ValueError("capture source definitions must use schema v1")
    if definition.board_size != 3 or definition.max_plies != CAPTURE_MAX_PLIES:
        raise ValueError("capture source definitions must be 3x3 with max_plies 18")
    if definition.terminal_policy is not None:
        raise ValueError("capture source definitions must retain v1 terminal semantics")
    role_a = definition.role(Player.A)
    role_b = definition.role(Player.B)
    if (
        role_a.action.kind is not ActionKind.PLACE
        or role_a.action.piece != "seed"
        or role_a.goal.kind is not GoalKind.CONNECT_EDGES
        or role_a.goal.piece != "seed"
        or role_b.action.kind is not ActionKind.MOVE
        or role_b.action.piece != "runner"
        or not role_b.action.vectors
        or role_b.goal.kind is not GoalKind.REACH_EDGE
        or role_b.goal.piece != "runner"
    ):
        raise ValueError("capture source definition is outside the A-place/B-move family")
    if (
        len(definition.initial_pieces) != 1
        or definition.initial_pieces[0].owner is not Player.B
        or definition.initial_pieces[0].piece != "runner"
    ):
        raise ValueError("capture source definition must contain exactly one B runner")
    row, column = definition.initial_pieces[0].position
    if row not in (0, definition.board_size - 1) and column not in (
        0,
        definition.board_size - 1,
    ):
        raise ValueError("capture source runner must start on the board boundary")


def _vector_count_band(vector_count: int) -> str:
    if 1 <= vector_count <= 3:
        return "1_TO_3"
    if vector_count == 4:
        return "4"
    if vector_count == 5:
        return "5"
    if 6 <= vector_count <= 7:
        return "6_TO_7"
    raise ValueError("capture family requires one to seven movement vectors")


def _source_stratum(definition: GameDefinition) -> Dict[str, Any]:
    role_a = definition.role(Player.A)
    role_b = definition.role(Player.B)
    assert role_b.goal.edge is not None
    row, column = definition.initial_pieces[0].position
    start_class = (
        "CORNER"
        if row in (0, definition.board_size - 1)
        and column in (0, definition.board_size - 1)
        else "EDGE_MIDPOINT"
    )
    return {
        "first_player": definition.first_player.value,
        "goal_axis_relation": (
            "ALIGNED" if role_b.goal.edge in role_a.goal.edges else "ORTHOGONAL"
        ),
        "runner_start_class": start_class,
        "max_plies": definition.max_plies,
        "vector_count_band": _vector_count_band(len(role_b.action.vectors)),
    }


def _capture_treatment(source: GameDefinition) -> GameDefinition:
    mapping = source.to_dict()
    mapping["schema_version"] = 3
    mapping["roles"]["B"]["action"]["kind"] = "MOVE_CAPTURE"
    treatment = parse_definition(mapping)
    _validate_treatment_pair(source, treatment)
    return treatment


def _validate_treatment_pair(
    source: GameDefinition, treatment: GameDefinition
) -> None:
    if treatment.schema_version != 3 or treatment.terminal_policy is not None:
        raise ValueError("capture treatment must be schema v3 with v1 terminal semantics")
    if treatment.role(Player.B).action.kind is not ActionKind.MOVE_CAPTURE:
        raise ValueError("capture treatment role B must use MOVE_CAPTURE")
    reverted = treatment.to_dict()
    reverted["schema_version"] = 1
    reverted["roles"]["B"]["action"]["kind"] = "MOVE"
    if _canonical_bytes(reverted) != _canonical_bytes(source.to_dict()):
        raise ValueError("capture pair changes fields other than schema and B action kind")


def capture_state_upper_bound(definition_value: Any) -> int:
    """Validate the capture family and return its proved board/ply state bound."""

    definition = (
        definition_value
        if isinstance(definition_value, GameDefinition)
        else parse_definition(definition_value)
    )
    if definition.schema_version != 3:
        raise ValueError("state-bound proof applies only to schema-v3 capture treatments")
    source_mapping = definition.to_dict()
    source_mapping["schema_version"] = 1
    source_mapping["roles"]["B"]["action"]["kind"] = "MOVE"
    source = parse_definition(source_mapping)
    _validate_source_family(source)
    _validate_treatment_pair(source, definition)
    non_runner_cells = definition.board_size ** 2 - 1
    board_arrangements = definition.board_size ** 2 * (2 ** non_runner_cells)
    bound = (definition.max_plies + 1) * board_arrangements
    if bound != CAPTURE_STATE_BOUND:
        raise AssertionError("capture structural state proof drifted")
    return bound


def validate_capture_searched_states(value: Any) -> int:
    """Require the public 1..43,776 integer bound; bool is intentionally invalid."""

    if type(value) is not int or not 1 <= value <= CAPTURE_STATE_BOUND:
        raise ValueError(
            "searched_states must be an integer in [1, {}]".format(
                CAPTURE_STATE_BOUND
            )
        )
    return value


def _pair_fingerprint(pair: Mapping[str, Any]) -> str:
    payload = {
        "pair_id": pair["pair_id"],
        "source_case_id": pair["source_case_id"],
        "source_definition_hash": pair["source_definition_hash"],
        "source_d4_canonical_hash": pair["source_d4_canonical_hash"],
        "stratum": pair["stratum"],
        "vector_count": pair["vector_count"],
        "source_definition": pair["source_definition"],
        "treatment_definition_hash": pair["treatment_definition_hash"],
        "treatment_d4_canonical_hash": pair["treatment_d4_canonical_hash"],
        "treatment_definition": pair["treatment_definition"],
        "selection_rank": pair["selection_rank"],
        "selection_score": pair["selection_score"],
    }
    return _domain_digest(_PAIR_FINGERPRINT_DOMAIN, payload)


def _capture_selection_score(source_hash: str) -> str:
    return hashlib.sha256(
        (_CAPTURE_SELECTION_PREFIX + source_hash).encode("ascii")
    ).hexdigest()


def build_capture_paired_manifest(
    source_manifest: Mapping[str, Any],
    source_manifest_sha256: str,
    provenance: Any,
    *,
    contract: CaptureManifestContract = DEFAULT_CAPTURE_MANIFEST_CONTRACT,
) -> Dict[str, Any]:
    """Build a deterministic, evaluation-free capture pairing manifest."""

    contract.validate()
    if not isinstance(source_manifest, Mapping):
        raise ValueError("source manifest must be an object")
    if source_manifest.get("manifest_id") != CAPTURE_SOURCE_MANIFEST_ID:
        raise ValueError("capture manifest must use the frozen landscape manifest")
    source_hash = _require_sha256(source_manifest_sha256, "source manifest hash")
    if source_hash != CAPTURE_SOURCE_MANIFEST_SHA256:
        raise ValueError("capture source manifest hash does not match the frozen value")
    source_cases = source_manifest.get("cases")
    if not isinstance(source_cases, list) or len(source_cases) != contract.source_case_count:
        raise ValueError("capture source manifest case census mismatch")
    provenance_copy = _json_copy(provenance, "provenance")
    if _contains_forbidden_outcome_key(provenance_copy):
        raise ValueError("capture manifest provenance must be outcome-free")

    selected = []
    seen_case_ids: Set[str] = set()
    for source_index, raw_case in enumerate(source_cases):
        case = _exact_keys(raw_case, _SOURCE_CASE_KEYS, "source case")
        case_id = case["case_id"]
        if not isinstance(case_id, str) or not case_id or case_id in seen_case_ids:
            raise ValueError("source case identifiers must be unique nonempty strings")
        seen_case_ids.add(case_id)
        definition = parse_definition(case["definition"])
        if definition_hash(definition) != case["definition_hash"]:
            raise ValueError("source definition hash mismatch for {}".format(case_id))
        if d4_canonical_hash(definition) != case["d4_canonical_hash"]:
            raise ValueError("source D4 hash mismatch for {}".format(case_id))
        if len(definition.role(Player.B).action.vectors) != case["vector_count"]:
            raise ValueError("source vector count mismatch for {}".format(case_id))
        if definition.max_plies != CAPTURE_MAX_PLIES:
            continue
        _validate_source_family(definition)
        if _canonical_bytes(case["stratum"]) != _canonical_bytes(
            _source_stratum(definition)
        ):
            raise ValueError("source stratum mismatch for {}".format(case_id))
        treatment = _capture_treatment(definition)
        pair_id = "capture-v1-pair-{:03d}".format(len(selected) + 1)
        pair = {
            "pair_id": pair_id,
            "source_case_id": case_id,
            "source_definition_hash": case["definition_hash"],
            "source_d4_canonical_hash": case["d4_canonical_hash"],
            "stratum": _json_copy(case["stratum"], "source stratum"),
            "vector_count": case["vector_count"],
            "source_definition": definition.to_dict(),
            "treatment_definition_hash": definition_hash(treatment),
            "treatment_d4_canonical_hash": d4_canonical_hash(treatment),
            "treatment_definition": treatment.to_dict(),
            "selection_rank": case["selection_rank"],
            "selection_score": _capture_selection_score(case["definition_hash"]),
        }
        pair["pair_fingerprint"] = _pair_fingerprint(pair)
        selected.append((source_index, pair))

    if len(selected) != contract.pair_count:
        raise ValueError(
            "capture max_plies=18 pair census mismatch: expected {}, observed {}".format(
                contract.pair_count, len(selected)
            )
        )
    # Membership order is the immutable source-manifest order.  The hash score is
    # recorded as an audit field and never used to consult an outcome.
    pairs = [pair for _, pair in selected]
    strata_counts = Counter(_stratum_identity(pair["stratum"]) for pair in pairs)
    if len(strata_counts) != contract.stratum_count or any(
        count != contract.quota_per_stratum for count in strata_counts.values()
    ):
        raise ValueError("capture paired stratum census or quota mismatch")

    manifest = {
        "manifest_version": CAPTURE_MANIFEST_VERSION,
        "manifest_id": CAPTURE_MANIFEST_ID,
        "protocol_id": CAPTURE_PROTOCOL_ID,
        "status": "FROZEN",
        "source": {
            "manifest_id": CAPTURE_SOURCE_MANIFEST_ID,
            "manifest_sha256": source_hash,
            "source_case_count": contract.source_case_count,
        },
        "selection_protocol": {
            "membership": "all source cases with max_plies=18 in source order",
            "treatment_change": "schema-v1 MOVE to schema-v3 MOVE_CAPTURE for B only",
            "baseline_informed": True,
            "treatment_outcome_free": True,
            "selection_score_prefix": _CAPTURE_SELECTION_PREFIX,
        },
        "state_bound": {
            "board_arrangements_per_ply": 2_304,
            "ply_layers": 19,
            "maximum_states": CAPTURE_STATE_BOUND,
            "exact_execution_cap": CAPTURE_EXACT_MAX_STATES,
        },
        "census": {
            "source_case_count": contract.source_case_count,
            "pair_count": len(pairs),
            "stratum_count": len(strata_counts),
            "quota_per_stratum": contract.quota_per_stratum,
        },
        "provenance": provenance_copy,
        "pairs": pairs,
    }
    validate_capture_paired_manifest(manifest, contract=contract)
    return manifest


def validate_capture_paired_manifest(
    manifest: Mapping[str, Any],
    *,
    contract: CaptureManifestContract = DEFAULT_CAPTURE_MANIFEST_CONTRACT,
) -> Tuple[Dict[str, Any], ...]:
    """Validate and return detached pairs from a capture manifest."""

    contract.validate()
    top = _exact_keys(
        manifest,
        (
            "manifest_version",
            "manifest_id",
            "protocol_id",
            "status",
            "source",
            "selection_protocol",
            "state_bound",
            "census",
            "provenance",
            "pairs",
        ),
        "capture manifest",
    )
    if (
        type(top["manifest_version"]) is not int
        or top["manifest_version"] != CAPTURE_MANIFEST_VERSION
        or top["manifest_id"] != CAPTURE_MANIFEST_ID
        or top["protocol_id"] != CAPTURE_PROTOCOL_ID
        or top["status"] != "FROZEN"
    ):
        raise ValueError("capture manifest identity or status mismatch")
    source = _exact_keys(
        top["source"],
        ("manifest_id", "manifest_sha256", "source_case_count"),
        "capture source",
    )
    if (
        source["manifest_id"] != CAPTURE_SOURCE_MANIFEST_ID
        or _require_sha256(source["manifest_sha256"], "source manifest hash")
        != CAPTURE_SOURCE_MANIFEST_SHA256
        or source["source_case_count"] != contract.source_case_count
    ):
        raise ValueError("capture source identity or census mismatch")
    selection = _exact_keys(
        top["selection_protocol"],
        (
            "membership",
            "treatment_change",
            "baseline_informed",
            "treatment_outcome_free",
            "selection_score_prefix",
        ),
        "selection protocol",
    )
    if (
        selection["membership"]
        != "all source cases with max_plies=18 in source order"
        or selection["treatment_change"]
        != "schema-v1 MOVE to schema-v3 MOVE_CAPTURE for B only"
        or selection["baseline_informed"] is not True
        or selection["treatment_outcome_free"] is not True
        or selection["selection_score_prefix"] != _CAPTURE_SELECTION_PREFIX
    ):
        raise ValueError("capture selection protocol mismatch")
    bound = _exact_keys(
        top["state_bound"],
        (
            "board_arrangements_per_ply",
            "ply_layers",
            "maximum_states",
            "exact_execution_cap",
        ),
        "state bound",
    )
    if dict(bound) != {
        "board_arrangements_per_ply": 2_304,
        "ply_layers": 19,
        "maximum_states": CAPTURE_STATE_BOUND,
        "exact_execution_cap": CAPTURE_EXACT_MAX_STATES,
    }:
        raise ValueError("capture state-bound evidence mismatch")
    census = _exact_keys(
        top["census"],
        ("source_case_count", "pair_count", "stratum_count", "quota_per_stratum"),
        "capture census",
    )
    if dict(census) != {
        "source_case_count": contract.source_case_count,
        "pair_count": contract.pair_count,
        "stratum_count": contract.stratum_count,
        "quota_per_stratum": contract.quota_per_stratum,
    }:
        raise ValueError("capture manifest census mismatch")
    provenance = _json_copy(top["provenance"], "provenance")
    if _contains_forbidden_outcome_key(provenance):
        raise ValueError("capture manifest provenance must be outcome-free")
    raw_pairs = top["pairs"]
    if not isinstance(raw_pairs, list) or len(raw_pairs) != contract.pair_count:
        raise ValueError("capture pair list census mismatch")

    pairs = []
    seen_pair_ids: Set[str] = set()
    seen_source_ids: Set[str] = set()
    seen_source_hashes: Set[str] = set()
    seen_treatment_hashes: Set[str] = set()
    strata = Counter()
    stratum_ranks: Dict[str, Set[int]] = defaultdict(set)
    for index, raw_pair in enumerate(raw_pairs):
        pair = _exact_keys(raw_pair, _PAIR_KEYS, "capture pair")
        expected_pair_id = "capture-v1-pair-{:03d}".format(index + 1)
        if pair["pair_id"] != expected_pair_id:
            raise ValueError("capture pairs must remain in declared source order")
        if pair["pair_id"] in seen_pair_ids or pair["source_case_id"] in seen_source_ids:
            raise ValueError("capture pair/source identifiers must be unique")
        seen_pair_ids.add(pair["pair_id"])
        seen_source_ids.add(pair["source_case_id"])
        source_definition = parse_definition(pair["source_definition"])
        treatment_definition = parse_definition(pair["treatment_definition"])
        _validate_source_family(source_definition)
        _validate_treatment_pair(source_definition, treatment_definition)
        source_hash = definition_hash(source_definition)
        treatment_hash = definition_hash(treatment_definition)
        if (
            pair["source_definition_hash"] != source_hash
            or pair["source_d4_canonical_hash"]
            != d4_canonical_hash(source_definition)
            or pair["treatment_definition_hash"] != treatment_hash
            or pair["treatment_d4_canonical_hash"]
            != d4_canonical_hash(treatment_definition)
        ):
            raise ValueError("capture pair definition or D4 hash mismatch")
        if source_hash in seen_source_hashes or treatment_hash in seen_treatment_hashes:
            raise ValueError("capture definitions must be unique")
        seen_source_hashes.add(source_hash)
        seen_treatment_hashes.add(treatment_hash)
        vector_count = pair["vector_count"]
        if (
            type(vector_count) is not int
            or vector_count != len(source_definition.role(Player.B).action.vectors)
        ):
            raise ValueError("capture pair vector count mismatch")
        rank = pair["selection_rank"]
        if type(rank) is not int or not 1 <= rank <= contract.quota_per_stratum:
            raise ValueError("capture pair selection rank is invalid")
        if pair["selection_score"] != _capture_selection_score(source_hash):
            raise ValueError("capture pair selection score mismatch")
        if pair["pair_fingerprint"] != _pair_fingerprint(pair):
            raise ValueError("capture pair fingerprint mismatch")
        capture_state_upper_bound(treatment_definition)
        if _canonical_bytes(pair["stratum"]) != _canonical_bytes(
            _source_stratum(source_definition)
        ):
            raise ValueError("capture pair stratum does not match its definition")
        stratum_key = _stratum_identity(pair["stratum"])
        strata[stratum_key] += 1
        stratum_ranks[stratum_key].add(rank)
        pairs.append(_json_copy(pair, "capture pair"))
    if len(strata) != contract.stratum_count or any(
        count != contract.quota_per_stratum for count in strata.values()
    ):
        raise ValueError("capture pair stratum census or quota mismatch")
    expected_ranks = set(range(1, contract.quota_per_stratum + 1))
    if any(ranks != expected_ranks for ranks in stratum_ranks.values()):
        raise ValueError("capture pair ranks must cover each stratum quota exactly")
    return tuple(pairs)


def _timing_free_exact(exact: Any) -> Dict[str, Any]:
    exact = _exact_keys(
        exact,
        ("status", "result", "budget_observation", "elapsed_seconds"),
        "baseline exact evidence",
    )
    return {
        "status": _json_copy(exact["status"], "exact status"),
        "result": _json_copy(exact["result"], "exact result"),
        "budget_observation": _json_copy(
            exact["budget_observation"], "exact budget observation"
        ),
    }


def capture_replay_projection(
    pair: Mapping[str, Any], candidate: Mapping[str, Any]
) -> Dict[str, Any]:
    """Return the exact timing-free baseline replay projection from Plan 0008."""

    if not isinstance(pair, Mapping) or not isinstance(candidate, Mapping):
        raise ValueError("replay projection requires pair and candidate objects")
    _exact_keys(candidate, _BASELINE_CANDIDATE_KEYS, "baseline replay candidate")
    _descriptive_candidate_timing((candidate,), "baseline replay")
    expected = {
        "case_id": pair.get("source_case_id"),
        "definition_hash": pair.get("source_definition_hash"),
        "d4_canonical_hash": pair.get("source_d4_canonical_hash"),
        "stratum": pair.get("stratum"),
        "vector_count": pair.get("vector_count"),
        "definition": pair.get("source_definition"),
    }
    for field, value in expected.items():
        if _canonical_bytes(candidate.get(field)) != _canonical_bytes(value):
            raise ValueError("baseline replay identity mismatch at {}".format(field))
    projection = {
        "pair_id": pair.get("pair_id"),
        "case_id": candidate.get("case_id"),
        "definition_hash": candidate.get("definition_hash"),
        "d4_canonical_hash": candidate.get("d4_canonical_hash"),
        "stratum": candidate.get("stratum"),
        "vector_count": candidate.get("vector_count"),
        "definition": candidate.get("definition"),
        "static": candidate.get("static"),
        "asymmetry": candidate.get("asymmetry"),
        "simplicity": candidate.get("simplicity"),
        "simplicity_passes": candidate.get("simplicity_passes"),
        "analysis_gate_passes": candidate.get("analysis_gate_passes"),
        "cheap_profiles": candidate.get("cheap_profiles"),
        "cheap_failure_codes": candidate.get("cheap_failure_codes"),
        "exact": _timing_free_exact(candidate.get("exact")),
    }
    _exact_keys(projection, _PROJECTION_KEYS, "baseline replay projection")
    for boolean_field in ("simplicity_passes", "analysis_gate_passes"):
        _strict_bool(projection[boolean_field], boolean_field)
    return _json_copy(projection, "baseline replay projection")


def _ordered_candidates(
    pairs: Sequence[Mapping[str, Any]],
    candidates: Sequence[Mapping[str, Any]],
    label: str,
    *,
    allow_extra_cases: bool = False,
) -> Tuple[Mapping[str, Any], ...]:
    candidate_tuple = tuple(candidates)
    expected = [pair["source_case_id"] for pair in pairs]
    case_ids = [candidate.get("case_id") for candidate in candidate_tuple]
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("{} candidates contain duplicate case identifiers".format(label))
    if allow_extra_cases:
        by_case_id = {
            candidate.get("case_id"): candidate for candidate in candidate_tuple
        }
        if any(case_id not in by_case_id for case_id in expected):
            raise ValueError("{} candidates are missing required manifest cases".format(label))
        return tuple(by_case_id[case_id] for case_id in expected)
    if len(candidate_tuple) != len(pairs) or case_ids != expected:
        raise ValueError("{} candidates are missing, duplicated, extra, or reordered".format(label))
    return candidate_tuple


def _attestation_side(
    pairs: Sequence[Mapping[str, Any]],
    candidates: Sequence[Mapping[str, Any]],
    label: str,
    *,
    allow_extra_cases: bool = False,
) -> Dict[str, Any]:
    ordered = _ordered_candidates(
        pairs, candidates, label, allow_extra_cases=allow_extra_cases
    )
    case_digests = []
    for pair, candidate in zip(pairs, ordered):
        projection = capture_replay_projection(pair, candidate)
        case_digests.append(
            {
                "pair_id": pair["pair_id"],
                "case_id": pair["source_case_id"],
                "case_digest": _domain_digest(CAPTURE_REPLAY_CASE_DOMAIN, projection),
            }
        )
    ordered_triples = [
        [record["pair_id"], record["case_id"], record["case_digest"]]
        for record in case_digests
    ]
    return {
        "case_digests": case_digests,
        "root_sha256": _domain_digest(CAPTURE_REPLAY_ORDER_DOMAIN, ordered_triples),
    }


def build_capture_replay_attestation(
    pairs: Sequence[Mapping[str, Any]],
    observed_candidates: Sequence[Mapping[str, Any]],
    pinned_candidates: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Independently project both baseline sources and require byte equality."""

    observed = _attestation_side(pairs, observed_candidates, "observed")
    pinned = _attestation_side(
        pairs,
        pinned_candidates,
        "pinned expected",
        allow_extra_cases=True,
    )
    if _canonical_bytes(observed) != _canonical_bytes(pinned):
        raise ValueError("fresh baseline replay differs from pinned expected evidence")
    return {
        "version": CAPTURE_REPLAY_ATTESTATION_VERSION,
        "observed": observed,
        "pinned_expected": pinned,
    }


def validate_capture_replay_attestation(
    attestation: Mapping[str, Any],
    pairs: Sequence[Mapping[str, Any]],
    observed_candidates: Optional[Sequence[Mapping[str, Any]]] = None,
    pinned_candidates: Optional[Sequence[Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    value = _exact_keys(
        attestation, ("version", "observed", "pinned_expected"), "replay attestation"
    )
    if value["version"] != CAPTURE_REPLAY_ATTESTATION_VERSION:
        raise ValueError("replay attestation version mismatch")
    for label in ("observed", "pinned_expected"):
        side = _exact_keys(
            value[label], ("case_digests", "root_sha256"), "attestation " + label
        )
        digests = side["case_digests"]
        if not isinstance(digests, list) or len(digests) != len(pairs):
            raise ValueError("attestation {} case digest census mismatch".format(label))
        triples = []
        seen = set()
        for pair, raw_record in zip(pairs, digests):
            record = _exact_keys(
                raw_record,
                ("pair_id", "case_id", "case_digest"),
                "attestation case digest",
            )
            identity = (record["pair_id"], record["case_id"])
            if identity in seen or identity != (pair["pair_id"], pair["source_case_id"]):
                raise ValueError("attestation cases are duplicated or reordered")
            seen.add(identity)
            _require_sha256(record["case_digest"], "case digest")
            triples.append([*identity, record["case_digest"]])
        expected_root = _domain_digest(CAPTURE_REPLAY_ORDER_DOMAIN, triples)
        if side["root_sha256"] != expected_root:
            raise ValueError("attestation {} ordered root mismatch".format(label))
    if _canonical_bytes(value["observed"]) != _canonical_bytes(value["pinned_expected"]):
        raise ValueError("observed and pinned replay attestations differ")
    if observed_candidates is not None or pinned_candidates is not None:
        if observed_candidates is None or pinned_candidates is None:
            raise ValueError("both replay candidate sequences are required")
        expected = build_capture_replay_attestation(
            pairs, observed_candidates, pinned_candidates
        )
        if _canonical_bytes(value) != _canonical_bytes(expected):
            raise ValueError("stored replay attestation does not reconstruct")
    return _json_copy(value, "replay attestation")


def validate_capture_baseline_replay(
    pairs: Sequence[Mapping[str, Any]],
    observed_candidates: Sequence[Mapping[str, Any]],
    pinned_candidates: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Named public entry point used by the one-shot raw runner."""

    return build_capture_replay_attestation(
        pairs, observed_candidates, pinned_candidates
    )


def _repetition_key(state: GameState) -> Tuple[Any, ...]:
    pieces = tuple(
        sorted(
            (
                piece.owner.value,
                piece.piece,
                piece.position[0],
                piece.position[1],
            )
            for piece in state.pieces
        )
    )
    return (state.to_move.value, pieces)


def _state_destination_piece(state: GameState, action: Action) -> Any:
    return next(
        (piece for piece in state.pieces if piece.position == action.to_position),
        None,
    )


def derive_capture_trace(
    definition_value: Any,
    actions: Sequence[Any],
    *,
    require_terminal: bool = True,
) -> Dict[str, Any]:
    """Replay actions and derive capture/cycle facts from pre-action states.

    A ``MOVE_CAPTURE`` action into an empty cell is an ordinary move.  It counts
    as a capture only if an opponent occupies its destination immediately before
    application.  This makes aggregate claims independently replayable.
    """

    definition = (
        definition_value
        if isinstance(definition_value, GameDefinition)
        else parse_definition(definition_value)
    )
    if not isinstance(actions, (list, tuple)):
        raise ValueError("capture trace actions must be an array")
    state = initial_state(definition)
    repeated = False
    seen_keys = {_repetition_key(state)}
    capture_plies = []
    capture_cells = []
    replacement_stage: Dict[Tuple[int, int], int] = {}
    replacement_recapture = False
    normalized_actions = []

    for offset, raw_action in enumerate(actions):
        if not isinstance(raw_action, Mapping):
            raise ValueError("capture trace actions must be objects")
        action = action_from_dict(raw_action)
        actor = state.to_move
        destination_piece = _state_destination_piece(state, action)
        is_capture = bool(
            action.kind is ActionKind.MOVE_CAPTURE
            and destination_piece is not None
            and destination_piece.owner is actor.other
        )
        cell = action.to_position
        if (
            actor is Player.A
            and action.kind is ActionKind.PLACE
            and replacement_stage.get(cell) == 1
        ):
            replacement_stage[cell] = 2
        if is_capture:
            capture_plies.append(offset + 1)
            capture_cells.append([cell[0], cell[1]])
            if actor is Player.B and replacement_stage.get(cell) == 2:
                replacement_recapture = True
            if actor is Player.B:
                replacement_stage[cell] = 1
        state = apply_action(definition, state, action)
        normalized_actions.append(action.to_dict())
        key = _repetition_key(state)
        if key in seen_keys:
            repeated = True
        seen_keys.add(key)

    if require_terminal and not state.terminal:
        raise ValueError("capture trace must end at a terminal state")
    terminal_outcome = state.outcome.to_dict() if state.outcome is not None else None
    return {
        "actions": normalized_actions,
        "terminal": state.terminal,
        "terminal_outcome": terminal_outcome,
        "terminal_ply": state.ply if state.terminal else None,
        "capture_count": len(capture_plies),
        "first_capture_ply": capture_plies[0] if capture_plies else None,
        "capture_plies": capture_plies,
        "capture_cells": capture_cells,
        "repeated_position": repeated,
        "replacement_recapture": replacement_recapture,
        "capture_replace_cycle": replacement_recapture and repeated,
    }


def _validate_terminal_claim(
    trace: Mapping[str, Any], outcome: Any, terminal_ply: Any, label: str
) -> None:
    claim = _exact_keys(outcome, ("winner", "reason"), label + " outcome")
    if claim["winner"] not in ("A", "B", None) or not isinstance(
        claim["reason"], str
    ):
        raise ValueError("{} terminal outcome is malformed".format(label))
    if type(terminal_ply) is not int or terminal_ply < 0:
        raise ValueError("{} terminal ply must be a nonnegative integer".format(label))
    if (
        _canonical_bytes(claim) != _canonical_bytes(trace["terminal_outcome"])
        or terminal_ply != trace["terminal_ply"]
    ):
        raise ValueError("{} terminal evidence does not replay".format(label))


def _normalize_game_trace(
    definition: GameDefinition, profile: str, value: Any
) -> Dict[str, Any]:
    if isinstance(value, GameRecord):
        raw = value.to_dict()
        seed = raw["seed"]
        actions = raw["actions"]
        outcome = {"winner": raw["winner"], "reason": raw["terminal_reason"]}
        terminal_ply = raw["plies"]
    else:
        if not isinstance(value, Mapping):
            raise ValueError("sampled game trace must be an object")
        if set(value) == {
            "profile",
            "seed",
            "actions",
            "terminal_outcome",
            "terminal_ply",
            "capture",
        }:
            raw = value
        elif set(value) == {
            "profile",
            "seed",
            "actions",
            "terminal_outcome",
            "terminal_ply",
        }:
            raw = value
        elif set(value) == {
            "seed",
            "agent_a",
            "agent_b",
            "actions",
            "winner",
            "terminal_reason",
            "plies",
        }:
            raw = value
            seed = raw["seed"]
            actions = raw["actions"]
            outcome = {
                "winner": raw["winner"],
                "reason": raw["terminal_reason"],
            }
            terminal_ply = raw["plies"]
            raw = None
        else:
            raise ValueError("sampled game trace fields mismatch")
        if raw is not None and raw["profile"] != profile:
            raise ValueError("sampled game trace profile mismatch")
        if raw is not None:
            seed = raw["seed"]
            actions = raw["actions"]
            outcome = raw["terminal_outcome"]
            terminal_ply = raw["terminal_ply"]
    if type(seed) is not int:
        raise ValueError("sampled game seed must be an integer (not boolean)")
    trace = derive_capture_trace(definition, actions)
    _validate_terminal_claim(trace, outcome, terminal_ply, "sampled game")
    return {
        "profile": profile,
        "seed": seed,
        "actions": trace["actions"],
        "terminal_outcome": trace["terminal_outcome"],
        "terminal_ply": trace["terminal_ply"],
        "capture": {
            key: trace[key]
            for key in (
                "capture_count",
                "first_capture_ply",
                "capture_plies",
                "capture_cells",
                "repeated_position",
                "replacement_recapture",
                "capture_replace_cycle",
            )
        },
    }


def _profile_summary(games: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    histogram = Counter(game["capture"]["capture_count"] for game in games)
    first_plies = [
        game["capture"]["first_capture_ply"]
        for game in games
        if game["capture"]["first_capture_ply"] is not None
    ]
    return {
        "game_count": len(games),
        "capture_count": sum(
            game["capture"]["capture_count"] for game in games
        ),
        "games_with_capture": sum(
            game["capture"]["capture_count"] > 0 for game in games
        ),
        "first_capture_ply": min(first_plies) if first_plies else None,
        "capture_count_histogram": {
            str(count): histogram[count] for count in sorted(histogram)
        },
        "repeated_position_games": sum(
            game["capture"]["repeated_position"] for game in games
        ),
        "replacement_recapture_games": sum(
            game["capture"]["replacement_recapture"] for game in games
        ),
        "capture_replace_cycle_games": sum(
            game["capture"]["capture_replace_cycle"] for game in games
        ),
    }


def _validate_histogram_schema(
    histogram: Any, expected_games: int, label: str
) -> None:
    if not isinstance(histogram, Mapping) or not histogram:
        if expected_games == 0 and histogram == {}:
            return
        raise ValueError("{} capture histogram must be a nonempty object".format(label))
    total = 0
    for key, count in histogram.items():
        if (
            not isinstance(key, str)
            or not key.isdecimal()
            or str(int(key)) != key
        ):
            raise ValueError("{} histogram keys must be canonical decimal strings".format(label))
        total += _strict_nonnegative_int(count, label + " histogram count")
    if total != expected_games:
        raise ValueError("{} histogram must sum to its game count".format(label))


def build_capture_profile_evidence(
    definition_value: Any,
    profile: str,
    games: Sequence[Any],
    expected_seeds: Sequence[int] = CAPTURE_PLAY_SEEDS,
) -> Dict[str, Any]:
    definition = (
        definition_value
        if isinstance(definition_value, GameDefinition)
        else parse_definition(definition_value)
    )
    if not isinstance(profile, str) or not profile:
        raise ValueError("profile must be a nonempty string")
    seeds = _validate_seed_sequence(expected_seeds, "capture profile")
    normalized = tuple(_normalize_game_trace(definition, profile, game) for game in games)
    if tuple(game["seed"] for game in normalized) != seeds:
        raise ValueError("complete capture profile must preserve the full seed order")
    result = {
        "status": "COMPLETED",
        "profile": profile,
        "expected_seeds": list(seeds),
        "completed_seed_prefix": list(seeds),
        "incomplete_seed": None,
        "games": list(normalized),
        "profile_summary": _profile_summary(normalized),
        "partial_summary": None,
        "frontier_metrics": {},
        "budget_observation": None,
    }
    validate_capture_profile_evidence(definition, result, expected_seeds=seeds)
    return result


def build_censored_capture_profile_evidence(
    definition_value: Any,
    profile: str,
    completed_games: Sequence[Any],
    expected_seeds: Sequence[int],
    incomplete_seed: int,
    budget_observation: Mapping[str, Any],
) -> Dict[str, Any]:
    """Seal a node-censored prefix and the one next incomplete seed."""

    definition = (
        definition_value
        if isinstance(definition_value, GameDefinition)
        else parse_definition(definition_value)
    )
    seeds = _validate_seed_sequence(expected_seeds, "censored capture profile")
    if type(incomplete_seed) is not int:
        raise ValueError("incomplete seed must be an integer (not boolean)")
    normalized = tuple(_normalize_game_trace(definition, profile, game) for game in completed_games)
    prefix = tuple(game["seed"] for game in normalized)
    if len(prefix) >= len(seeds) or prefix != seeds[: len(prefix)]:
        raise ValueError("censored games must be a strict completed seed prefix")
    if incomplete_seed != seeds[len(prefix)]:
        raise ValueError("censored record must identify the next incomplete seed")
    budget = _exact_keys(
        budget_observation,
        ("visited_nodes", "max_nodes", "scope"),
        "strong budget observation",
    )
    visited = _strict_nonnegative_int(budget["visited_nodes"], "visited nodes")
    maximum = _strict_positive_int(budget["max_nodes"], "maximum nodes")
    if visited != maximum or budget["scope"] != "per-candidate":
        raise ValueError("strong censor must exhaust the cumulative candidate budget")
    result = {
        "status": "CENSORED_NODE_BUDGET",
        "profile": profile,
        "expected_seeds": list(seeds),
        "completed_seed_prefix": list(prefix),
        "incomplete_seed": incomplete_seed,
        "games": list(normalized),
        "profile_summary": None,
        "partial_summary": _profile_summary(normalized),
        "frontier_metrics": None,
        "budget_observation": _json_copy(budget, "strong budget observation"),
    }
    validate_capture_profile_evidence(definition, result, expected_seeds=seeds)
    return result


def validate_capture_profile_evidence(
    definition_value: Any,
    evidence: Mapping[str, Any],
    *,
    expected_seeds: Optional[Sequence[int]] = None,
) -> Dict[str, Any]:
    definition = (
        definition_value
        if isinstance(definition_value, GameDefinition)
        else parse_definition(definition_value)
    )
    value = _exact_keys(
        evidence,
        (
            "status",
            "profile",
            "expected_seeds",
            "completed_seed_prefix",
            "incomplete_seed",
            "games",
            "profile_summary",
            "partial_summary",
            "frontier_metrics",
            "budget_observation",
        ),
        "capture profile evidence",
    )
    profile = value["profile"]
    if not isinstance(profile, str) or not profile:
        raise ValueError("capture profile label is malformed")
    seeds = _validate_seed_sequence(value["expected_seeds"], "capture profile")
    if expected_seeds is not None and seeds != tuple(expected_seeds):
        raise ValueError("capture profile expected seed sequence mismatch")
    games = value["games"]
    if not isinstance(games, list):
        raise ValueError("capture profile games must be an array")
    normalized = tuple(_normalize_game_trace(definition, profile, game) for game in games)
    # Stored per-game derived fields are also evidence and must reconstruct exactly.
    if _canonical_bytes(games) != _canonical_bytes(normalized):
        raise ValueError("stored per-game capture evidence does not reconstruct")
    game_seeds = tuple(game["seed"] for game in normalized)
    summary = _profile_summary(normalized)
    _validate_histogram_schema(
        summary["capture_count_histogram"], len(normalized), "capture profile"
    )
    if value["status"] == "COMPLETED":
        if (
            game_seeds != seeds
            or value["completed_seed_prefix"] != list(seeds)
            or value["incomplete_seed"] is not None
            or _canonical_bytes(value["profile_summary"])
            != _canonical_bytes(summary)
            or value["partial_summary"] is not None
            or value["frontier_metrics"] != {}
            or value["budget_observation"] is not None
        ):
            raise ValueError("complete capture profile evidence is inconsistent")
    elif value["status"] == "CENSORED_NODE_BUDGET":
        if (
            len(game_seeds) >= len(seeds)
            or game_seeds != seeds[: len(game_seeds)]
            or value["completed_seed_prefix"] != list(game_seeds)
            or value["incomplete_seed"] != seeds[len(game_seeds)]
            or value["profile_summary"] is not None
            or _canonical_bytes(value["partial_summary"])
            != _canonical_bytes(summary)
            or value["frontier_metrics"] is not None
        ):
            raise ValueError("censored capture profile prefix evidence is inconsistent")
        budget = _exact_keys(
            value["budget_observation"],
            ("visited_nodes", "max_nodes", "scope"),
            "strong budget observation",
        )
        if (
            type(budget["visited_nodes"]) is not int
            or type(budget["max_nodes"]) is not int
            or budget["visited_nodes"] != budget["max_nodes"]
            or budget["max_nodes"] < 1
            or budget["scope"] != "per-candidate"
        ):
            raise ValueError("censored strong budget observation is malformed")
    else:
        raise ValueError("capture profile has an unknown status")
    return _json_copy(value, "capture profile evidence")


def _validate_exact_evidence(
    definition: GameDefinition,
    exact: Any,
    *,
    treatment_bound: bool,
) -> Tuple[str, Optional[Dict[str, Any]]]:
    value = _exact_keys(
        exact,
        ("status", "result", "budget_observation", "elapsed_seconds"),
        "exact evidence",
    )
    status = value["status"]
    if status == "CENSORED_STATE_BUDGET":
        budget = _exact_keys(
            value["budget_observation"],
            ("searched_states", "max_states"),
            "exact budget observation",
        )
        if (
            value["result"] is not None
            or type(budget["searched_states"]) is not int
            or type(budget["max_states"]) is not int
            or budget["searched_states"] != budget["max_states"]
            or budget["max_states"] != CAPTURE_EXACT_MAX_STATES
        ):
            raise ValueError("censored exact evidence is malformed")
        return status, None
    if status != "COMPLETED" or value["budget_observation"] is not None:
        raise ValueError("exact evidence has an unknown or inconsistent status")
    result = _exact_keys(
        value["result"],
        (
            "value_for_a",
            "forced_result",
            "principal_variation",
            "principal_variation_plies",
            "terminal_reason",
            "searched_states",
            "cache_hits",
        ),
        "exact result",
    )
    forced = result["forced_result"]
    if (
        forced not in _FORCED_RESULTS
        or type(result["value_for_a"]) is not int
        or result["value_for_a"] != _VALUE_BY_RESULT[forced]
    ):
        raise ValueError("exact value/result encoding mismatch")
    if treatment_bound:
        validate_capture_searched_states(result["searched_states"])
    elif type(result["searched_states"]) is not int or result["searched_states"] < 1:
        raise ValueError("baseline searched_states must be a positive integer")
    if type(result["cache_hits"]) is not int or result["cache_hits"] < 0:
        raise ValueError("exact cache_hits must be a nonnegative integer")
    pv = result["principal_variation"]
    if (
        not isinstance(pv, list)
        or type(result["principal_variation_plies"]) is not int
        or result["principal_variation_plies"] != len(pv)
    ):
        raise ValueError("exact principal variation length mismatch")
    trace = derive_capture_trace(definition, pv)
    expected_winner = {"A_WIN": "A", "B_WIN": "B", "DRAW": None}[forced]
    if (
        trace["terminal_outcome"]["winner"] != expected_winner
        or trace["terminal_outcome"]["reason"] != result["terminal_reason"]
        or trace["terminal_ply"] != result["principal_variation_plies"]
    ):
        raise ValueError("exact principal variation terminal claim does not replay")
    return status, trace


def build_capture_exact_pv_evidence(
    definition_value: Any, exact: Mapping[str, Any]
) -> Optional[Dict[str, Any]]:
    definition = (
        definition_value
        if isinstance(definition_value, GameDefinition)
        else parse_definition(definition_value)
    )
    status, trace = _validate_exact_evidence(
        definition, exact, treatment_bound=definition.schema_version == 3
    )
    if status != "COMPLETED":
        return None
    assert trace is not None
    return {
        "capture_count": trace["capture_count"],
        "first_capture_ply": trace["first_capture_ply"],
        "capture_plies": trace["capture_plies"],
        "capture_cells": trace["capture_cells"],
        "repeated_position": trace["repeated_position"],
        "replacement_recapture": trace["replacement_recapture"],
        "capture_replace_cycle": trace["capture_replace_cycle"],
    }


def normalize_capture_pv(
    baseline_definition_value: Any,
    baseline_actions: Sequence[Any],
    treatment_definition_value: Any,
    treatment_actions: Sequence[Any],
) -> Dict[str, Any]:
    """Walk paired states and count the predeclared normalized PV prefix."""

    baseline_definition = (
        baseline_definition_value
        if isinstance(baseline_definition_value, GameDefinition)
        else parse_definition(baseline_definition_value)
    )
    treatment_definition = (
        treatment_definition_value
        if isinstance(treatment_definition_value, GameDefinition)
        else parse_definition(treatment_definition_value)
    )
    _validate_treatment_pair(baseline_definition, treatment_definition)
    # Full independent replay first prevents ignored malformed suffixes.
    derive_capture_trace(baseline_definition, baseline_actions)
    derive_capture_trace(treatment_definition, treatment_actions)
    baseline_state = initial_state(baseline_definition)
    treatment_state = initial_state(treatment_definition)
    common = 0
    for raw_baseline, raw_treatment in zip(baseline_actions, treatment_actions):
        baseline_action = action_from_dict(raw_baseline)
        treatment_action = action_from_dict(raw_treatment)
        matches = False
        if (
            baseline_action.kind is ActionKind.PLACE
            and treatment_action.kind is ActionKind.PLACE
            and baseline_action.to_position == treatment_action.to_position
        ):
            matches = True
        elif (
            baseline_action.kind is ActionKind.MOVE
            and treatment_action.kind is ActionKind.MOVE_CAPTURE
            and baseline_action.from_position == treatment_action.from_position
            and baseline_action.to_position == treatment_action.to_position
            and _state_destination_piece(treatment_state, treatment_action) is None
        ):
            matches = True
        if not matches:
            break
        baseline_state = apply_action(
            baseline_definition, baseline_state, baseline_action
        )
        treatment_state = apply_action(
            treatment_definition, treatment_state, treatment_action
        )
        common += 1
    baseline_length = len(baseline_actions)
    treatment_length = len(treatment_actions)
    return {
        "common_prefix_plies": common,
        "first_divergence_ply": (
            None
            if common == baseline_length == treatment_length
            else common + 1
        ),
        "baseline_principal_variation_plies": baseline_length,
        "treatment_principal_variation_plies": treatment_length,
        "principal_variation_plies_delta": treatment_length - baseline_length,
    }


def validate_capture_monotonicity(
    baseline_exact: Mapping[str, Any], treatment_exact: Mapping[str, Any]
) -> Dict[str, Any]:
    """Enforce B_WIN < DRAW < A_WIN for every completed treatment solve."""

    baseline = baseline_exact.get("result")
    treatment = treatment_exact.get("result")
    if (
        baseline_exact.get("status") != "COMPLETED"
        or treatment_exact.get("status") != "COMPLETED"
        or not isinstance(baseline, Mapping)
        or not isinstance(treatment, Mapping)
    ):
        raise ValueError("monotonicity requires two completed exact results")
    baseline_result = baseline.get("forced_result")
    treatment_result = treatment.get("forced_result")
    if baseline_result not in _VALUE_BY_RESULT or treatment_result not in _VALUE_BY_RESULT:
        raise ValueError("monotonicity exact result is unknown")
    baseline_value = baseline.get("value_for_a")
    treatment_value = treatment.get("value_for_a")
    if (
        type(baseline_value) is not int
        or baseline_value != _VALUE_BY_RESULT[baseline_result]
        or type(treatment_value) is not int
        or treatment_value != _VALUE_BY_RESULT[treatment_result]
    ):
        raise ValueError("monotonicity exact value encoding mismatch")
    if treatment_value > baseline_value:
        raise ValueError(
            "capture monotonicity violation: {} -> {}".format(
                baseline_result, treatment_result
            )
        )
    return {
        "baseline_value_for_a": baseline_value,
        "treatment_value_for_a": treatment_value,
        "transition": "{}->{}".format(baseline_result, treatment_result),
        "value_changed": baseline_value != treatment_value,
        "monotonic": True,
    }


def _capture_case_identity(case: Mapping[str, Any]) -> Tuple[str, str, str]:
    pair_id = case.get("pair_id")
    source_case_id = case.get("source_case_id")
    game_hash = case.get("definition_hash")
    if not all(isinstance(value, str) and value for value in (pair_id, source_case_id, game_hash)):
        raise ValueError("capture cases need pair, source-case, and definition identifiers")
    return pair_id, source_case_id, game_hash


def evaluate_capture_cases(
    cases: Sequence[Mapping[str, Any]],
    play_seeds: Sequence[int] = CAPTURE_PLAY_SEEDS,
    max_exact_states: int = CAPTURE_EXACT_MAX_STATES,
    gates: PlayGates = PlayGates(),
    clock: Callable[[], float] = time.perf_counter,
) -> Dict[str, Any]:
    """Evaluate already selected capture cases and seal complete game traces.

    This is computation-only: it performs no artifact, reservation, Git, or clock
    persistence.  Exact solving is routed independently of all analysis gates.
    """

    seeds = _validate_seed_sequence(play_seeds, "capture play")
    if type(max_exact_states) is not int or max_exact_states < 1:
        raise ValueError("max_exact_states must be a positive integer")
    if not cases:
        raise ValueError("capture evaluation requires at least one case")
    random_agent = RandomAgent()
    directed_agent = GoalDirectedAgent()
    seen_pairs: Set[str] = set()
    seen_sources: Set[str] = set()
    seen_hashes: Set[str] = set()
    candidates = []
    total_started = clock()
    static_seconds = cheap_seconds = exact_seconds = 0.0

    for manifest_index, case in enumerate(cases):
        if not isinstance(case, Mapping):
            raise ValueError("capture cases must be objects")
        pair_id, source_case_id, game_hash = _capture_case_identity(case)
        if pair_id in seen_pairs or source_case_id in seen_sources or game_hash in seen_hashes:
            raise ValueError("capture case identities and definitions must be unique")
        seen_pairs.add(pair_id)
        seen_sources.add(source_case_id)
        seen_hashes.add(game_hash)
        definition = parse_definition(case.get("definition"))
        if definition_hash(definition) != game_hash:
            raise ValueError("capture case definition hash mismatch")
        if case.get("d4_canonical_hash") != d4_canonical_hash(definition):
            raise ValueError("capture case D4 hash mismatch")
        capture_state_upper_bound(definition)
        vector_count = case.get("vector_count")
        if type(vector_count) is not int or vector_count != len(
            definition.role(Player.B).action.vectors
        ):
            raise ValueError("capture case vector count mismatch")

        static_started = clock()
        static = analyze_definition(definition)
        asymmetry = evaluate_asymmetry(definition)
        simplicity = evaluate_simplicity(definition)
        simplicity_passes = not exceeds_limits(simplicity)
        gate_passes = static.passes and asymmetry.qualifies and simplicity_passes
        static_elapsed = clock() - static_started
        static_seconds += static_elapsed

        cheap_profiles: Tuple[MatchupResult, ...] = ()
        cheap_failures: Set[FailureCode] = set()
        cheap_capture_evidence = []
        cheap_elapsed = 0.0
        if gate_passes:
            cheap_started = clock()
            cheap_profiles = (
                evaluate_matchup(
                    definition,
                    "weak-random",
                    {Player.A: random_agent, Player.B: random_agent},
                    seeds,
                ),
                evaluate_matchup(
                    definition,
                    "medium-goal-directed",
                    {Player.A: directed_agent, Player.B: directed_agent},
                    seeds,
                ),
            )
            cheap_failures = classify_play_failures(definition, cheap_profiles, gates)
            cheap_capture_evidence = [
                build_capture_profile_evidence(
                    definition, profile.profile, profile.records, seeds
                )
                for profile in cheap_profiles
            ]
            cheap_elapsed = clock() - cheap_started
            cheap_seconds += cheap_elapsed

        exact_started = clock()
        exact_result = None
        budget_observation = None
        exact_status = "COMPLETED"
        try:
            solved = solve_game(definition, max_states=max_exact_states)
        except SolveBudgetExceeded as error:
            exact_status = "CENSORED_STATE_BUDGET"
            budget_observation = {
                "searched_states": error.searched_states,
                "max_states": error.max_states,
            }
        else:
            exact_result = solved.to_dict()
            # The mathematical bound is a public integrity contract, not merely a
            # runner cap.  Fail here before returning a candidate that could be
            # interpreted as an experimental observation.
            validate_capture_searched_states(exact_result["searched_states"])
        exact_elapsed = clock() - exact_started
        exact_seconds += exact_elapsed
        exact = {
            "status": exact_status,
            "result": exact_result,
            "budget_observation": budget_observation,
            "elapsed_seconds": exact_elapsed,
        }
        exact_capture = build_capture_exact_pv_evidence(definition, exact)

        candidate = {
            "manifest_index": manifest_index,
            "pair_id": pair_id,
            "source_case_id": source_case_id,
            "definition_hash": game_hash,
            "d4_canonical_hash": case["d4_canonical_hash"],
            "stratum": _json_copy(case.get("stratum"), "capture stratum"),
            "vector_count": vector_count,
            "definition": definition.to_dict(),
            "static": static.to_dict(),
            "asymmetry": asymmetry.to_dict(),
            "simplicity": simplicity.to_dict(),
            "simplicity_passes": simplicity_passes,
            "analysis_gate_passes": gate_passes,
            "cheap_profiles": [
                profile.to_dict(include_records=False) for profile in cheap_profiles
            ],
            "cheap_capture_evidence": cheap_capture_evidence,
            "cheap_failure_codes": sorted(code.value for code in cheap_failures),
            "exact": exact,
            "exact_capture_evidence": exact_capture,
            "timing": {
                "static_asymmetry_simplicity_seconds": static_elapsed,
                "cheap_play_seconds": cheap_elapsed,
            },
        }
        candidates.append(candidate)

    return {
        "configuration": {
            "play_seeds": list(seeds),
            "play_gates": asdict(gates),
            "max_exact_states": max_exact_states,
            "exact_routing": "all capture cases independent of analysis gates",
            "cheap_routing": "static, asymmetry, and simplicity pass only",
            "game_trace_evidence": "complete ordered actions, outcomes, and plies",
        },
        "timing": {
            "static_asymmetry_simplicity_seconds": static_seconds,
            "cheap_play_seconds": cheap_seconds,
            "exact_seconds": exact_seconds,
            "total_seconds": clock() - total_started,
        },
        "candidates": candidates,
    }


def validate_capture_case_evaluation(
    result: Mapping[str, Any],
    cases: Sequence[Mapping[str, Any]],
    *,
    play_seeds: Sequence[int] = CAPTURE_PLAY_SEEDS,
    max_exact_states: int = CAPTURE_EXACT_MAX_STATES,
    gates: PlayGates = PlayGates(),
) -> Dict[str, Any]:
    """Publicly validate the pure treatment-evaluator envelope and candidates."""

    value = _exact_keys(
        result,
        ("configuration", "timing", "candidates"),
        "capture case evaluation",
    )
    seeds = _validate_seed_sequence(play_seeds, "capture evaluation")
    configuration = _exact_keys(
        value["configuration"],
        (
            "play_seeds",
            "play_gates",
            "max_exact_states",
            "exact_routing",
            "cheap_routing",
            "game_trace_evidence",
        ),
        "capture evaluation configuration",
    )
    expected_configuration = {
        "play_seeds": list(seeds),
        "play_gates": asdict(gates),
        "max_exact_states": max_exact_states,
        "exact_routing": "all capture cases independent of analysis gates",
        "cheap_routing": "static, asymmetry, and simplicity pass only",
        "game_trace_evidence": "complete ordered actions, outcomes, and plies",
    }
    if _canonical_bytes(configuration) != _canonical_bytes(expected_configuration):
        raise ValueError("capture evaluation configuration mismatch")
    if len(value["candidates"]) != len(cases):
        raise ValueError("capture evaluation candidate census mismatch")
    for index, (case, candidate) in enumerate(zip(cases, value["candidates"])):
        _exact_keys(
            candidate, _TREATMENT_CANDIDATE_KEYS, "capture evaluation candidate"
        )
        if (
            type(candidate["manifest_index"]) is not int
            or candidate["manifest_index"] != index
            or candidate["pair_id"] != case.get("pair_id")
            or candidate["source_case_id"] != case.get("source_case_id")
            or candidate["definition_hash"] != case.get("definition_hash")
            or candidate["d4_canonical_hash"] != case.get("d4_canonical_hash")
            or _canonical_bytes(candidate["stratum"])
            != _canonical_bytes(case.get("stratum"))
            or type(candidate["vector_count"]) is not int
            or candidate["vector_count"] != case.get("vector_count")
            or _canonical_bytes(candidate["definition"])
            != _canonical_bytes(case.get("definition"))
        ):
            raise ValueError("capture evaluation candidate identity/order mismatch")
        definition = parse_definition(candidate["definition"])
        capture_state_upper_bound(definition)
        evidence = candidate["cheap_capture_evidence"]
        if not isinstance(evidence, list):
            raise ValueError("capture cheap trace evidence must be an array")
        for profile_evidence in evidence:
            validate_capture_profile_evidence(
                definition, profile_evidence, expected_seeds=seeds
            )
        _validate_treatment_analysis_evidence(
            definition,
            candidate,
            evidence,
            expected_seeds=seeds,
            gates=gates,
        )
        _validate_exact_evidence(definition, candidate["exact"], treatment_bound=True)
        expected_capture = build_capture_exact_pv_evidence(
            definition, candidate["exact"]
        )
        if _canonical_bytes(candidate["exact_capture_evidence"]) != _canonical_bytes(
            expected_capture
        ):
            raise ValueError("capture exact PV evidence does not reconstruct")
        _descriptive_candidate_timing((candidate,), "capture evaluation")
    timing = _exact_keys(
        value["timing"],
        (
            "static_asymmetry_simplicity_seconds",
            "cheap_play_seconds",
            "exact_seconds",
            "total_seconds",
        ),
        "capture evaluation timing",
    )
    for field, number in timing.items():
        if (
            isinstance(number, bool)
            or not isinstance(number, (int, float))
            or not math.isfinite(number)
            or number < 0
        ):
            raise ValueError("capture evaluation {} is malformed".format(field))
    for top_field, candidate_field in (
        ("static_asymmetry_simplicity_seconds", "static_asymmetry_simplicity_seconds"),
        ("cheap_play_seconds", "cheap_play_seconds"),
    ):
        expected = sum(
            candidate["timing"][candidate_field] for candidate in value["candidates"]
        )
        if timing[top_field] != expected:
            raise ValueError("capture evaluation timing components do not reconstruct")
    expected_exact = sum(
        candidate["exact"]["elapsed_seconds"] for candidate in value["candidates"]
    )
    if timing["exact_seconds"] != expected_exact:
        raise ValueError("capture evaluation exact timing does not reconstruct")
    component_total = (
        timing["static_asymmetry_simplicity_seconds"]
        + timing["cheap_play_seconds"]
        + timing["exact_seconds"]
    )
    if timing["total_seconds"] < component_total:
        raise ValueError("capture evaluation total timing is smaller than its components")
    return _json_copy(value, "capture case evaluation")


def _candidate_sequence(value: Any, label: str) -> Tuple[Mapping[str, Any], ...]:
    if isinstance(value, Mapping):
        value = value.get("candidates")
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError("{} must provide a nonempty candidate sequence".format(label))
    if not all(isinstance(item, Mapping) for item in value):
        raise ValueError("{} candidates must be objects".format(label))
    return tuple(value)


def _paired_valid(baseline: Mapping[str, Any], treatment: Mapping[str, Any]) -> bool:
    return (
        baseline.get("analysis_gate_passes") is True
        and treatment.get("analysis_gate_passes") is True
    )


def _candidate_exact_result(candidate: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
    exact = candidate["exact"]
    return exact["result"] if exact["status"] == "COMPLETED" else None


def _matchup_from_summary(summary: Mapping[str, Any]) -> MatchupResult:
    return MatchupResult(
        profile=summary["profile"],
        agent_a=summary["agent_a"],
        agent_b=summary["agent_b"],
        # ``MatchupResult.samples`` is deliberately derived from ``records``.
        # Gate reconstruction needs only the cardinality and aggregate fields;
        # opaque placeholders avoid trusting a separately claimed sample count.
        records=tuple(None for _ in range(summary["samples"])),
        a_wins=summary["a_wins"],
        b_wins=summary["b_wins"],
        draws=summary["draws"],
        average_plies=summary["average_plies"],
        decisive_a_share=summary["decisive_a_share"],
        decisive_a_wilson_95=(
            tuple(summary["decisive_a_wilson_95"])
            if summary["decisive_a_wilson_95"] is not None
            else None
        ),
        terminal_reasons=tuple(sorted(summary["terminal_reasons"].items())),
    )


def _validate_treatment_analysis_evidence(
    definition: GameDefinition,
    candidate: Mapping[str, Any],
    cheap_evidence: Sequence[Mapping[str, Any]],
    *,
    expected_seeds: Sequence[int] = CAPTURE_PLAY_SEEDS,
    gates: PlayGates = PlayGates(),
) -> None:
    expected_static = analyze_definition(definition).to_dict()
    expected_asymmetry = evaluate_asymmetry(definition).to_dict()
    expected_simplicity = evaluate_simplicity(definition)
    expected_simplicity_mapping = expected_simplicity.to_dict()
    simplicity_passes = not exceeds_limits(expected_simplicity)
    gate_passes = (
        expected_static["passes"]
        and expected_asymmetry["qualifies"]
        and simplicity_passes
    )
    for field, expected in (
        ("static", expected_static),
        ("asymmetry", expected_asymmetry),
        ("simplicity", expected_simplicity_mapping),
        ("simplicity_passes", simplicity_passes),
        ("analysis_gate_passes", gate_passes),
    ):
        if _canonical_bytes(candidate.get(field)) != _canonical_bytes(expected):
            raise ValueError("treatment {} evidence does not reconstruct".format(field))
    profiles = candidate.get("cheap_profiles")
    failures = candidate.get("cheap_failure_codes")
    if not isinstance(profiles, list) or not isinstance(failures, list):
        raise ValueError("treatment cheap evidence is malformed")
    if not gate_passes:
        if profiles or cheap_evidence or failures:
            raise ValueError("analysis-gate rejects cannot contain cheap play evidence")
        return
    expected_profiles = (
        ("weak-random", "random-v1-weak"),
        ("medium-goal-directed", "goal_directed-v1-medium"),
    )
    if len(profiles) != 2 or len(cheap_evidence) != 2:
        raise ValueError("capture cheap evaluation requires both frozen profiles")
    reconstructed_matchups = []
    for profile, evidence, (profile_name, agent_name) in zip(
        profiles, cheap_evidence, expected_profiles
    ):
        if (
            evidence["profile"] != profile_name
            or profile.get("profile") != profile_name
            or profile.get("agent_a") != agent_name
            or profile.get("agent_b") != agent_name
            or profile.get("seeds") != list(expected_seeds)
        ):
            raise ValueError("capture cheap profile identity or seeds mismatch")
        rebuilt_profile = _profile_summary_from_evidence(
            evidence, agent_a=agent_name, agent_b=agent_name
        )
        if _canonical_bytes(profile) != _canonical_bytes(rebuilt_profile):
            raise ValueError("capture cheap profile aggregate does not reconstruct")
        reconstructed_matchups.append(_matchup_from_summary(rebuilt_profile))
    expected_failures = sorted(
        code.value
        for code in classify_play_failures(
            definition, tuple(reconstructed_matchups), gates
        )
    )
    if failures != expected_failures:
        raise ValueError("capture cheap failure codes do not reconstruct")


def _is_primary_response(candidate: Mapping[str, Any]) -> bool:
    if not candidate["paired_valid"]:
        return False
    baseline = _candidate_exact_result(candidate["baseline"])
    treatment = _candidate_exact_result(candidate["treatment"])
    return bool(
        baseline is not None
        and treatment is not None
        and baseline["forced_result"] == "A_WIN"
        and baseline["terminal_reason"] == "NO_LEGAL_ACTION"
        and treatment["forced_result"] == "B_WIN"
        and treatment["terminal_reason"] == "GOAL"
    )


def _is_realized_capture_response(candidate: Mapping[str, Any]) -> bool:
    treatment = _candidate_exact_result(candidate["treatment"])
    evidence = candidate["exact_capture_evidence"]
    return bool(
        candidate["paired_valid"]
        and treatment is not None
        and treatment["terminal_reason"] != "PLY_LIMIT"
        and evidence is not None
        and evidence["capture_count"] > 0
    )


def _threshold_assessment(
    candidates: Sequence[Mapping[str, Any]], predicate: Callable[[Mapping[str, Any]], bool]
) -> Dict[str, Any]:
    selected = [candidate for candidate in candidates if predicate(candidate)]
    strata = {_stratum_identity(candidate["stratum"]) for candidate in selected}
    count = len(selected)
    if count >= 4 and len(strata) >= 2:
        status = "SUPPORTED"
    elif count == 0:
        status = "NOT_SUPPORTED"
    else:
        status = "INCONCLUSIVE"
    return {
        "status": status,
        "reasons": [],
        "case_count": count,
        "stratum_count": len(strata),
        "definition_hashes": sorted(
            candidate["treatment"]["definition_hash"] for candidate in selected
        ),
    }


def _stratum_breakdown(candidates: Sequence[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    grouped: Dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        grouped[_stratum_identity(candidate["stratum"])].append(candidate)
    result = []
    for key in sorted(grouped):
        group = grouped[key]
        histogram = Counter()
        for candidate in group:
            exact = candidate["treatment"]["exact"]
            histogram[
                exact["result"]["forced_result"]
                if exact["status"] == "COMPLETED"
                else "CENSORED"
            ] += 1
        result.append(
            {
                "stratum": _json_copy(group[0]["stratum"], "stratum"),
                "pair_count": len(group),
                "paired_valid_count": sum(item["paired_valid"] for item in group),
                "primary_response_count": sum(_is_primary_response(item) for item in group),
                "realized_capture_response_count": sum(
                    _is_realized_capture_response(item) for item in group
                ),
                "treatment_exact_result_histogram": {
                    name: histogram.get(name, 0)
                    for name in (*_FORCED_RESULTS, "CENSORED")
                },
            }
        )
    return result


def _dimension_breakdowns(
    candidates: Sequence[Mapping[str, Any]],
) -> Dict[str, list[Dict[str, Any]]]:
    dimensions = (
        "first_player",
        "goal_axis_relation",
        "runner_start_class",
        "max_plies",
        "vector_count_band",
        "vector_count",
    )
    output = {}
    for dimension in dimensions:
        groups: Dict[Any, list[Mapping[str, Any]]] = defaultdict(list)
        for candidate in candidates:
            value = (
                candidate["vector_count"]
                if dimension == "vector_count"
                else candidate["stratum"].get(dimension)
            )
            groups[value].append(candidate)
        records = []
        for value in sorted(groups, key=lambda item: (str(type(item)), str(item))):
            group = groups[value]
            outcomes = Counter()
            for candidate in group:
                result = _candidate_exact_result(candidate["treatment"])
                outcomes[result["forced_result"] if result is not None else "CENSORED"] += 1
            records.append(
                {
                    "value": value,
                    "pair_count": len(group),
                    "paired_valid_count": sum(item["paired_valid"] for item in group),
                    "primary_response_count": sum(_is_primary_response(item) for item in group),
                    "realized_capture_response_count": sum(
                        _is_realized_capture_response(item) for item in group
                    ),
                    "treatment_exact_result_histogram": {
                        name: outcomes.get(name, 0)
                        for name in (*_FORCED_RESULTS, "CENSORED")
                    },
                }
            )
        output[dimension] = records
    return output


def _cycling_assessment(candidates: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    pool = []
    for candidate in candidates:
        if not candidate["paired_valid"] or not candidate.get("value_changed"):
            continue
        baseline = _candidate_exact_result(candidate["baseline"])
        treatment = _candidate_exact_result(candidate["treatment"])
        if (
            baseline is not None
            and baseline["forced_result"] == "A_WIN"
            and baseline["terminal_reason"] == "NO_LEGAL_ACTION"
            and treatment is not None
        ):
            pool.append(candidate)
    ply_count = sum(
        _candidate_exact_result(item["treatment"])["terminal_reason"] == "PLY_LIMIT"
        for item in pool
    )
    nonhorizon_b = sum(
        _candidate_exact_result(item["treatment"])["forced_result"] == "B_WIN"
        and _candidate_exact_result(item["treatment"])["terminal_reason"] != "PLY_LIMIT"
        for item in pool
    )
    descriptive_status = "DOMINANT" if ply_count > nonhorizon_b else "NOT_DOMINANT"
    return {
        "status": descriptive_status,
        "descriptive_status": descriptive_status,
        "reasons": [],
        "pool_count": len(pool),
        "ply_limit_count": ply_count,
        "nonhorizon_b_win_count": nonhorizon_b,
        "definition_hashes": sorted(
            item["treatment"]["definition_hash"] for item in pool
        ),
    }


def select_capture_raw_inspection(
    candidates: Sequence[Mapping[str, Any]],
    *,
    change_count: int = 16,
    control_count: int = 16,
) -> Dict[str, Any]:
    if type(change_count) is not int or type(control_count) is not int or min(
        change_count, control_count
    ) < 0:
        raise ValueError("inspection counts must be nonnegative integers")
    reasons: Dict[str, Set[str]] = defaultdict(set)
    by_hash = {}
    changed = []
    unchanged = []
    exact_censored = []
    ply_limit = []
    for candidate in candidates:
        treatment = candidate["treatment"]
        game_hash = treatment["definition_hash"]
        if game_hash in by_hash:
            raise ValueError("inspection candidates must have unique definitions")
        by_hash[game_hash] = candidate
        exact = treatment["exact"]
        if exact["status"] != "COMPLETED":
            exact_censored.append(game_hash)
            reasons[game_hash].add("EXACT_CENSOR")
            continue
        result = exact["result"]
        if result["terminal_reason"] == "PLY_LIMIT":
            ply_limit.append(game_hash)
            reasons[game_hash].add("PLY_LIMIT")
        if candidate["value_changed"]:
            changed.append(game_hash)
        else:
            unchanged.append(game_hash)
    changed.sort(
        key=lambda item: (
            hashlib.sha256((_INSPECTION_CHANGE_PREFIX + item).encode("ascii")).hexdigest(),
            item,
        )
    )
    unchanged.sort(
        key=lambda item: (
            hashlib.sha256((_INSPECTION_CONTROL_PREFIX + item).encode("ascii")).hexdigest(),
            item,
        )
    )
    for game_hash in changed[:change_count]:
        reasons[game_hash].add("OUTCOME_CHANGE_SAMPLE")
    for game_hash in unchanged[:control_count]:
        reasons[game_hash].add("OUTCOME_UNCHANGED_CONTROL")
    selected = []
    source_order = {
        candidate["treatment"]["definition_hash"]: index
        for index, candidate in enumerate(candidates)
    }
    for game_hash in sorted(reasons, key=lambda item: source_order[item]):
        candidate = by_hash[game_hash]
        selected.append(
            {
                "pair_id": candidate["pair_id"],
                "source_case_id": candidate["source_case_id"],
                "definition_hash": game_hash,
                "reasons": sorted(reasons[game_hash]),
            }
        )
    return {
        "version": "capture-raw-inspection-v1",
        "adaptive_stress_disposition": (
            "BLOCKED_EXACT_CENSOR" if exact_censored else "ELIGIBLE"
        ),
        "selected": selected,
        "pool_counts": {
            "exact_censor": len(exact_censored),
            "ply_limit": len(ply_limit),
            "outcome_changed": len(changed),
            "outcome_unchanged": len(unchanged),
        },
        "requested_counts": {
            "outcome_changed": change_count,
            "outcome_unchanged": control_count,
        },
        "shortfalls": {
            "outcome_changed": max(0, change_count - len(changed)),
            "outcome_unchanged": max(0, control_count - len(unchanged)),
        },
    }


def _build_raw_aggregate(candidates: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    exact_completed = sum(
        candidate["treatment"]["exact"]["status"] == "COMPLETED"
        for candidate in candidates
    )
    exact_censored = len(candidates) - exact_completed
    result_histogram = Counter()
    terminal_histogram = Counter()
    transition_histogram = Counter()
    terminal_transition_histogram = Counter()
    work = []
    cheap_failure_histogram: Counter[str] = Counter()
    cheap_direction_confusion: Dict[str, Counter[str]] = defaultdict(Counter)
    cheap_capture: Dict[str, Dict[str, Any]] = {}
    exact_capture_histogram: Counter[int] = Counter()
    normalized_prefix_histogram: Counter[int] = Counter()
    pv_delta_histogram: Counter[int] = Counter()
    for candidate in candidates:
        baseline = _candidate_exact_result(candidate["baseline"])
        treatment = _candidate_exact_result(candidate["treatment"])
        treatment_candidate = candidate["treatment"]
        cheap_failure_histogram.update(treatment_candidate["cheap_failure_codes"])
        for profile_evidence in treatment_candidate["cheap_capture_evidence"]:
            label = profile_evidence["profile"]
            accumulator = cheap_capture.setdefault(
                label,
                {
                    "profile_count": 0,
                    "game_count": 0,
                    "capture_count": 0,
                    "games_with_capture": 0,
                    "capture_count_histogram": Counter(),
                    "repeated_position_games": 0,
                    "replacement_recapture_games": 0,
                    "capture_replace_cycle_games": 0,
                },
            )
            summary = profile_evidence["profile_summary"]
            accumulator["profile_count"] += 1
            for field in (
                "game_count",
                "capture_count",
                "games_with_capture",
                "repeated_position_games",
                "replacement_recapture_games",
                "capture_replace_cycle_games",
            ):
                accumulator[field] += summary[field]
            for count, frequency in summary["capture_count_histogram"].items():
                accumulator["capture_count_histogram"][int(count)] += frequency
        if treatment is None:
            result_histogram["CENSORED"] += 1
            if baseline is not None:
                transition_histogram[baseline["forced_result"] + "->CENSORED"] += 1
            continue
        result_histogram[treatment["forced_result"]] += 1
        terminal_histogram[treatment["terminal_reason"]] += 1
        work.append(treatment["searched_states"])
        evidence = candidate.get("exact_capture_evidence")
        if isinstance(evidence, Mapping):
            exact_capture_histogram[evidence["capture_count"]] += 1
        normalization = candidate.get("normalized_pv")
        if isinstance(normalization, Mapping):
            normalized_prefix_histogram[normalization["common_prefix_plies"]] += 1
            pv_delta_histogram[normalization["principal_variation_plies_delta"]] += 1
        for profile in treatment_candidate["cheap_profiles"]:
            cheap_direction_confusion[profile["profile"]][
                "{}->{}".format(
                    sampled_direction(profile), treatment["forced_result"]
                )
            ] += 1
        if baseline is not None:
            transition_histogram[
                baseline["forced_result"] + "->" + treatment["forced_result"]
            ] += 1
            terminal_transition_histogram[
                baseline["terminal_reason"] + "->" + treatment["terminal_reason"]
            ] += 1
    exact_assessment = {
        "status": "SUPPORTED" if exact_censored == 0 else "INCONCLUSIVE",
        "reasons": [] if exact_censored == 0 else ["EXACT_STATE_BUDGET_CENSORING"],
    }
    primary = _threshold_assessment(candidates, _is_primary_response)
    realized = _threshold_assessment(candidates, _is_realized_capture_response)
    cycling = _cycling_assessment(candidates)
    if exact_censored:
        for assessment in (primary, realized):
            assessment["status"] = "INCONCLUSIVE"
            assessment["reasons"] = ["EXACT_STATE_BUDGET_CENSORING"]
        cycling["status"] = "INCONCLUSIVE"
        cycling["reasons"] = ["EXACT_STATE_BUDGET_CENSORING"]
    cheap_capture_aggregate = {}
    for profile, accumulator in sorted(cheap_capture.items()):
        histogram = accumulator.pop("capture_count_histogram")
        cheap_capture_aggregate[profile] = {
            **accumulator,
            "capture_count_histogram": {
                str(count): histogram[count] for count in sorted(histogram)
            },
        }
    return {
        "pair_count": len(candidates),
        "baseline_static_pass_count": sum(
            item["baseline"]["static"]["passes"] for item in candidates
        ),
        "treatment_static_pass_count": sum(
            item["treatment"]["static"]["passes"] for item in candidates
        ),
        "baseline_asymmetry_qualifies_count": sum(
            item["baseline"]["asymmetry"]["qualifies"] for item in candidates
        ),
        "treatment_asymmetry_qualifies_count": sum(
            item["treatment"]["asymmetry"]["qualifies"] for item in candidates
        ),
        "baseline_simplicity_pass_count": sum(
            item["baseline"]["simplicity_passes"] for item in candidates
        ),
        "treatment_simplicity_pass_count": sum(
            item["treatment"]["simplicity_passes"] for item in candidates
        ),
        "baseline_analysis_gate_pass_count": sum(
            item["baseline"].get("analysis_gate_passes") is True for item in candidates
        ),
        "treatment_analysis_gate_pass_count": sum(
            item["treatment"].get("analysis_gate_passes") is True for item in candidates
        ),
        "paired_valid_count": sum(item["paired_valid"] for item in candidates),
        "exact_attempted": len(candidates),
        "exact_completed": exact_completed,
        "exact_censored": exact_censored,
        "exact_censored_hashes": sorted(
            item["treatment"]["definition_hash"]
            for item in candidates
            if item["treatment"]["exact"]["status"] != "COMPLETED"
        ),
        "treatment_exact_result_histogram": {
            key: result_histogram.get(key, 0)
            for key in (*_FORCED_RESULTS, "CENSORED")
        },
        "treatment_terminal_reason_histogram": dict(sorted(terminal_histogram.items())),
        "result_transition_histogram": dict(sorted(transition_histogram.items())),
        "terminal_transition_histogram": dict(
            sorted(terminal_transition_histogram.items())
        ),
        "cheap_failure_histogram": dict(sorted(cheap_failure_histogram.items())),
        "cheap_exact_direction_confusion": {
            profile: dict(sorted(confusion.items()))
            for profile, confusion in sorted(cheap_direction_confusion.items())
        },
        "cheap_capture_by_profile": cheap_capture_aggregate,
        "exact_pv_capture_count_histogram": {
            str(count): exact_capture_histogram[count]
            for count in sorted(exact_capture_histogram)
        },
        "normalized_pv_common_prefix_histogram": {
            str(count): normalized_prefix_histogram[count]
            for count in sorted(normalized_prefix_histogram)
        },
        "principal_variation_plies_delta_histogram": {
            str(delta): pv_delta_histogram[delta]
            for delta in sorted(pv_delta_histogram)
        },
        "exact_work_states_total": sum(work),
        "exact_work_states_max": max(work, default=0),
        "monotonicity_checked_count": exact_completed,
        "value_changed_count": sum(item.get("value_changed", False) for item in candidates),
        "capture_threat_without_pv_capture_count": sum(
            item.get("value_changed", False)
            and item.get("exact_capture_evidence") is not None
            and item["exact_capture_evidence"]["capture_count"] == 0
            for item in candidates
        ),
        "treatment_pv_capture_count": sum(
            item.get("exact_capture_evidence") is not None
            and item["exact_capture_evidence"]["capture_count"] > 0
            for item in candidates
        ),
        "treatment_ply_limit_count": sum(
            _candidate_exact_result(item["treatment"]) is not None
            and _candidate_exact_result(item["treatment"])["terminal_reason"] == "PLY_LIMIT"
            for item in candidates
        ),
        "treatment_pv_repeated_position_count": sum(
            item.get("exact_capture_evidence") is not None
            and item["exact_capture_evidence"]["repeated_position"]
            for item in candidates
        ),
        "treatment_pv_replacement_recapture_count": sum(
            item.get("exact_capture_evidence") is not None
            and item["exact_capture_evidence"]["replacement_recapture"]
            for item in candidates
        ),
        "treatment_pv_capture_replace_cycle_count": sum(
            item.get("exact_capture_evidence") is not None
            and item["exact_capture_evidence"]["capture_replace_cycle"]
            for item in candidates
        ),
        "by_stratum": _stratum_breakdown(candidates),
        "by_dimension": _dimension_breakdowns(candidates),
        "predeclared_assessment": {
            "exact_completion": exact_assessment,
            "primary_counterplay_response": primary,
            "realized_capture_response": realized,
            "cycling_dominance": cycling,
        },
    }


def _descriptive_candidate_timing(
    candidates: Sequence[Mapping[str, Any]], label: str
) -> Dict[str, float]:
    static_seconds = cheap_seconds = exact_seconds = 0.0
    for candidate in candidates:
        timing = candidate.get("timing")
        exact = candidate.get("exact")
        if not isinstance(timing, Mapping) or not isinstance(exact, Mapping):
            raise ValueError("{} candidate is missing descriptive timing".format(label))
        _exact_keys(
            timing,
            (
                "static_asymmetry_simplicity_seconds",
                "cheap_play_seconds",
            ),
            label + " candidate timing",
        )
        static_value = timing.get("static_asymmetry_simplicity_seconds")
        cheap_value = timing.get("cheap_play_seconds")
        exact_value = exact.get("elapsed_seconds")
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
            for value in (static_value, cheap_value, exact_value)
        ):
            raise ValueError("{} candidate timing is malformed".format(label))
        static_seconds += float(static_value)
        cheap_seconds += float(cheap_value)
        exact_seconds += float(exact_value)
    return {
        "static_asymmetry_simplicity_seconds": static_seconds,
        "cheap_play_seconds": cheap_seconds,
        "exact_seconds": exact_seconds,
        "total_component_seconds": static_seconds + cheap_seconds + exact_seconds,
    }


def build_capture_paired_result(
    manifest: Mapping[str, Any],
    fresh_baseline_results: Any,
    pinned_baseline_results: Any,
    treatment_results: Any,
    *,
    replay_attestation: Optional[Mapping[str, Any]] = None,
    contract: CaptureManifestContract = DEFAULT_CAPTURE_MANIFEST_CONTRACT,
) -> Dict[str, Any]:
    """Build a deterministic raw paired record from already computed evidence."""

    pairs = validate_capture_paired_manifest(manifest, contract=contract)
    treatment_cases = tuple(
        {
            "pair_id": pair["pair_id"],
            "source_case_id": pair["source_case_id"],
            "definition_hash": pair["treatment_definition_hash"],
            "d4_canonical_hash": pair["treatment_d4_canonical_hash"],
            "stratum": _json_copy(pair["stratum"], "stratum"),
            "vector_count": pair["vector_count"],
            "definition": _json_copy(
                pair["treatment_definition"], "treatment definition"
            ),
        }
        for pair in pairs
    )
    if isinstance(treatment_results, Mapping):
        _exact_keys(
            treatment_results,
            ("configuration", "timing", "candidates"),
            "capture treatment evaluation envelope",
        )
        validate_capture_case_evaluation(
            treatment_results,
            treatment_cases,
            play_seeds=CAPTURE_PLAY_SEEDS,
            max_exact_states=CAPTURE_EXACT_MAX_STATES,
            gates=PlayGates(),
        )
    fresh = _ordered_candidates(
        pairs, _candidate_sequence(fresh_baseline_results, "fresh baseline"), "fresh baseline"
    )
    pinned = _ordered_candidates(
        pairs,
        _candidate_sequence(pinned_baseline_results, "pinned baseline"),
        "pinned baseline",
        allow_extra_cases=True,
    )
    attestation = (
        build_capture_replay_attestation(pairs, fresh, pinned)
        if replay_attestation is None
        else validate_capture_replay_attestation(
            replay_attestation, pairs, fresh, pinned
        )
    )
    treatments = _candidate_sequence(treatment_results, "capture treatment")
    if len(treatments) != len(pairs):
        raise ValueError("capture treatment candidate count mismatch")
    enriched = []
    seen_treatment_hashes = set()
    for index, (pair, baseline, treatment) in enumerate(zip(pairs, fresh, treatments)):
        _exact_keys(
            treatment,
            _TREATMENT_CANDIDATE_KEYS,
            "capture treatment candidate",
        )
        if (
            type(treatment.get("manifest_index")) is not int
            or treatment.get("manifest_index") != index
            or treatment.get("pair_id") != pair["pair_id"]
            or treatment.get("source_case_id") != pair["source_case_id"]
            or treatment.get("definition_hash") != pair["treatment_definition_hash"]
            or treatment.get("d4_canonical_hash") != pair["treatment_d4_canonical_hash"]
            or _canonical_bytes(treatment.get("stratum"))
            != _canonical_bytes(pair["stratum"])
            or type(treatment.get("vector_count")) is not int
            or treatment.get("vector_count") != pair["vector_count"]
            or _canonical_bytes(treatment.get("definition"))
            != _canonical_bytes(pair["treatment_definition"])
        ):
            raise ValueError("capture treatment identity/order mismatch")
        game_hash = treatment["definition_hash"]
        if game_hash in seen_treatment_hashes:
            raise ValueError("capture treatment definitions must be unique")
        seen_treatment_hashes.add(game_hash)
        baseline_definition = parse_definition(pair["source_definition"])
        treatment_definition = parse_definition(pair["treatment_definition"])
        baseline_status, _ = _validate_exact_evidence(
            baseline_definition, baseline["exact"], treatment_bound=False
        )
        treatment_status, _ = _validate_exact_evidence(
            treatment_definition, treatment["exact"], treatment_bound=True
        )
        if baseline_status != "COMPLETED":
            raise ValueError("fresh v1 baseline replay must complete exactly")
        exact_capture = build_capture_exact_pv_evidence(
            treatment_definition, treatment["exact"]
        )
        if _canonical_bytes(treatment.get("exact_capture_evidence")) != _canonical_bytes(
            exact_capture
        ):
            raise ValueError("treatment exact capture evidence does not reconstruct")
        cheap_evidence = treatment.get("cheap_capture_evidence")
        if not isinstance(cheap_evidence, list):
            raise ValueError("treatment cheap capture evidence must be an array")
        if treatment.get("analysis_gate_passes") is True:
            profiles = treatment.get("cheap_profiles")
            if not isinstance(profiles, list) or len(profiles) != len(cheap_evidence):
                raise ValueError("cheap profile/capture evidence census mismatch")
            for profile, evidence in zip(profiles, cheap_evidence):
                validate_capture_profile_evidence(
                    treatment_definition,
                    evidence,
                    expected_seeds=CAPTURE_PLAY_SEEDS,
                )
                if evidence["profile"] != profile.get("profile"):
                    raise ValueError("cheap profile label mismatch")
        elif treatment.get("cheap_profiles") != [] or cheap_evidence != []:
            raise ValueError("analysis-gate rejects cannot contain cheap play")
        _validate_treatment_analysis_evidence(
            treatment_definition, treatment, cheap_evidence
        )
        monotonicity = None
        pv_normalization = None
        value_changed = False
        if treatment_status == "COMPLETED":
            monotonicity = validate_capture_monotonicity(
                baseline["exact"], treatment["exact"]
            )
            value_changed = monotonicity["value_changed"]
            pv_normalization = normalize_capture_pv(
                baseline_definition,
                baseline["exact"]["result"]["principal_variation"],
                treatment_definition,
                treatment["exact"]["result"]["principal_variation"],
            )
        candidate = {
            "manifest_index": index,
            "pair_id": pair["pair_id"],
            "source_case_id": pair["source_case_id"],
            "stratum": _json_copy(pair["stratum"], "stratum"),
            "vector_count": pair["vector_count"],
            "baseline": _json_copy(baseline, "baseline candidate"),
            "treatment": _json_copy(treatment, "treatment candidate"),
            "paired_valid": _paired_valid(baseline, treatment),
            "monotonicity": monotonicity,
            "value_changed": value_changed,
            "exact_capture_evidence": exact_capture,
            "normalized_pv": pv_normalization,
        }
        enriched.append(candidate)
    aggregate = _build_raw_aggregate(enriched)
    inspection = select_capture_raw_inspection(enriched)
    aggregate["adaptive_stress_disposition"] = inspection[
        "adaptive_stress_disposition"
    ]
    return {
        "protocol_id": "capture-v1-raw-paired-evaluation",
        "manifest_id": CAPTURE_MANIFEST_ID,
        "replay_attestation": attestation,
        "aggregate": aggregate,
        "timing": {
            "fresh_baseline": _descriptive_candidate_timing(fresh, "fresh baseline"),
            "treatment": _descriptive_candidate_timing(treatments, "capture treatment"),
            "used_for_assessment": False,
        },
        "pre_stress_inspection": inspection,
        "candidates": enriched,
    }


def validate_capture_paired_result(
    result: Mapping[str, Any],
    manifest: Mapping[str, Any],
    pinned_baseline_results: Any,
    *,
    contract: CaptureManifestContract = DEFAULT_CAPTURE_MANIFEST_CONTRACT,
) -> Dict[str, Any]:
    value = _exact_keys(
        result,
        (
            "protocol_id",
            "manifest_id",
            "replay_attestation",
            "aggregate",
            "timing",
            "pre_stress_inspection",
            "candidates",
        ),
        "capture paired result",
    )
    if (
        value["protocol_id"] != "capture-v1-raw-paired-evaluation"
        or value["manifest_id"] != CAPTURE_MANIFEST_ID
    ):
        raise ValueError("capture paired result identity mismatch")
    candidates = value["candidates"]
    if not isinstance(candidates, list):
        raise ValueError("capture paired candidates must be an array")
    fresh = [candidate.get("baseline") for candidate in candidates]
    treatments = [candidate.get("treatment") for candidate in candidates]
    rebuilt = build_capture_paired_result(
        manifest,
        fresh,
        pinned_baseline_results,
        treatments,
        replay_attestation=value["replay_attestation"],
        contract=contract,
    )
    if _canonical_bytes(value) != _canonical_bytes(rebuilt):
        raise ValueError("capture paired result does not reconstruct")
    return _json_copy(value, "capture paired result")


def evaluate_capture_pairs(
    manifest: Mapping[str, Any],
    pinned_baseline_results: Any,
    *,
    baseline_evaluator: Callable[[Tuple[Dict[str, Any], ...]], Any],
    treatment_evaluator: Callable[[Tuple[Dict[str, Any], ...]], Any],
    contract: CaptureManifestContract = DEFAULT_CAPTURE_MANIFEST_CONTRACT,
) -> Dict[str, Any]:
    """Execute fresh-baseline-first orchestration with a hard attestation barrier."""

    pairs = validate_capture_paired_manifest(manifest, contract=contract)
    source_cases = tuple(
        {
            "case_id": pair["source_case_id"],
            "definition_hash": pair["source_definition_hash"],
            "d4_canonical_hash": pair["source_d4_canonical_hash"],
            "stratum": _json_copy(pair["stratum"], "stratum"),
            "vector_count": pair["vector_count"],
            "definition": _json_copy(pair["source_definition"], "source definition"),
        }
        for pair in pairs
    )
    # This callback must finish, and its result must match the independently
    # projected pinned source, before treatment evaluation is even invoked.
    fresh_result = baseline_evaluator(source_cases)
    fresh = _candidate_sequence(fresh_result, "fresh baseline evaluator")
    pinned = _candidate_sequence(pinned_baseline_results, "pinned baseline")
    attestation = build_capture_replay_attestation(pairs, fresh, pinned)
    treatment_cases = tuple(
        {
            "pair_id": pair["pair_id"],
            "source_case_id": pair["source_case_id"],
            "definition_hash": pair["treatment_definition_hash"],
            "d4_canonical_hash": pair["treatment_d4_canonical_hash"],
            "stratum": _json_copy(pair["stratum"], "stratum"),
            "vector_count": pair["vector_count"],
            "definition": _json_copy(
                pair["treatment_definition"], "treatment definition"
            ),
        }
        for pair in pairs
    )
    treatment_result = treatment_evaluator(treatment_cases)
    if isinstance(treatment_result, Mapping):
        validate_capture_case_evaluation(
            treatment_result,
            treatment_cases,
            play_seeds=CAPTURE_PLAY_SEEDS,
            max_exact_states=CAPTURE_EXACT_MAX_STATES,
            gates=PlayGates(),
        )
    return build_capture_paired_result(
        manifest,
        fresh,
        pinned,
        treatment_result,
        replay_attestation=attestation,
        contract=contract,
    )


def _raw_candidates(value: Any) -> Tuple[Mapping[str, Any], ...]:
    if isinstance(value, Mapping):
        value = value.get("candidates")
    if not isinstance(value, (list, tuple)):
        raise ValueError("raw capture candidates must be an array")
    if not all(isinstance(item, Mapping) for item in value):
        raise ValueError("raw capture candidates must be objects")
    return tuple(value)


def _stress_eligibility(candidate: Mapping[str, Any]) -> bool:
    treatment = candidate.get("treatment")
    if not isinstance(treatment, Mapping) or candidate.get("paired_valid") is not True:
        return False
    exact = treatment.get("exact")
    if not isinstance(exact, Mapping) or exact.get("status") != "COMPLETED":
        return False
    result = exact.get("result")
    capture = candidate.get("exact_capture_evidence")
    return bool(
        isinstance(result, Mapping)
        and result.get("terminal_reason") != "PLY_LIMIT"
        and (
            candidate.get("value_changed") is True
            or (
                isinstance(capture, Mapping)
                and type(capture.get("capture_count")) is int
                and capture["capture_count"] > 0
            )
        )
    )


def _stress_selection_score(game_hash: str, clean: bool) -> str:
    prefix = _STRESS_CLEAN_PREFIX if clean else _STRESS_OTHER_PREFIX
    return hashlib.sha256((prefix + game_hash).encode("ascii")).hexdigest()


def select_capture_stress_candidates(
    raw_result_or_candidates: Any,
    *,
    max_candidates: int = CAPTURE_STRESS_MAX_CANDIDATES,
) -> Dict[str, Any]:
    """Apply the clean-first, hash-ordered, without-replacement stress rule."""

    if type(max_candidates) is not int or max_candidates < 1:
        raise ValueError("stress candidate cap must be a positive integer")
    candidates = _raw_candidates(raw_result_or_candidates)
    eligible = []
    seen_hashes = set()
    for source_index, candidate in enumerate(candidates):
        treatment = candidate.get("treatment")
        if not isinstance(treatment, Mapping):
            raise ValueError("raw candidate is missing treatment evidence")
        game_hash = treatment.get("definition_hash")
        if not isinstance(game_hash, str) or game_hash in seen_hashes:
            raise ValueError("raw treatment hashes must be unique strings")
        seen_hashes.add(game_hash)
        if not _stress_eligibility(candidate):
            continue
        failure_codes = treatment.get("cheap_failure_codes")
        if not isinstance(failure_codes, list) or not all(
            isinstance(code, str) for code in failure_codes
        ):
            raise ValueError("eligible treatment cheap failure codes are malformed")
        clean = not bool(set(failure_codes).intersection(_SHAPE_FAILURES))
        eligible.append(
            {
                "pair_id": candidate["pair_id"],
                "source_case_id": candidate["source_case_id"],
                "definition_hash": game_hash,
                "selection_tier": "CLEAN" if clean else "OTHER",
                "selection_score": _stress_selection_score(game_hash, clean),
                "source_index": source_index,
            }
        )
    eligible.sort(
        key=lambda item: (
            0 if item["selection_tier"] == "CLEAN" else 1,
            item["selection_score"],
            item["definition_hash"],
        )
    )
    selected = eligible[:max_candidates]
    selected_hashes = {item["definition_hash"] for item in selected}
    return {
        "version": "capture-stress-selection-v1",
        "max_candidates": max_candidates,
        "eligible_count": len(eligible),
        "selected_count": len(selected),
        "unselected_eligible_count": max(0, len(eligible) - len(selected)),
        "selected": [
            {
                key: item[key]
                for key in (
                    "pair_id",
                    "source_case_id",
                    "definition_hash",
                    "selection_tier",
                    "selection_score",
                )
            }
            for item in selected
        ],
        "unselected_eligible_hashes": [
            item["definition_hash"]
            for item in eligible
            if item["definition_hash"] not in selected_hashes
        ],
    }


def _wilson_interval(successes: int, samples: int) -> Optional[list[float]]:
    if samples == 0:
        return None
    z = 1.959963984540054
    proportion = successes / samples
    denominator = 1.0 + z * z / samples
    center = (proportion + z * z / (2.0 * samples)) / denominator
    margin = z * (
        proportion * (1.0 - proportion) / samples
        + z * z / (4.0 * samples * samples)
    ) ** 0.5 / denominator
    return [max(0.0, center - margin), min(1.0, center + margin)]


def _profile_summary_from_evidence(
    evidence: Mapping[str, Any], *, agent_a: str, agent_b: str
) -> Dict[str, Any]:
    games = evidence["games"]
    a_wins = sum(game["terminal_outcome"]["winner"] == "A" for game in games)
    b_wins = sum(game["terminal_outcome"]["winner"] == "B" for game in games)
    draws = len(games) - a_wins - b_wins
    decisive = a_wins + b_wins
    reasons = Counter(game["terminal_outcome"]["reason"] for game in games)
    samples = len(games)
    return {
        "profile": evidence["profile"],
        "agent_a": agent_a,
        "agent_b": agent_b,
        "samples": samples,
        "a_wins": a_wins,
        "b_wins": b_wins,
        "draws": draws,
        "a_win_rate": a_wins / samples if samples else None,
        "b_win_rate": b_wins / samples if samples else None,
        "draw_rate": draws / samples if samples else None,
        "average_plies": (
            sum(game["terminal_ply"] for game in games) / samples if samples else None
        ),
        "decisive_a_share": a_wins / decisive if decisive else None,
        "decisive_a_wilson_95": _wilson_interval(a_wins, decisive),
        "terminal_reasons": dict(sorted(reasons.items())),
        "seeds": [game["seed"] for game in games],
    }


def _sampled_profile_from_evidence(evidence: Mapping[str, Any]) -> Dict[str, Any]:
    agent_name = "minimax-v1-depth{}".format(CAPTURE_STRESS_DEPTH)
    return _profile_summary_from_evidence(
        evidence, agent_a=agent_name, agent_b=agent_name
    )


def _strong_failure_codes(
    definition: GameDefinition, profile: Mapping[str, Any], gates: PlayGates
) -> list[str]:
    failures = set()
    samples = profile["samples"]
    if type(samples) is not int or samples < 1:
        raise ValueError("complete strong profile requires at least one sample")
    if profile["draws"] / samples > gates.max_draw_rate:
        failures.add(FailureCode.EXCESSIVE_DRAWS.value)
    if profile["average_plies"] < gates.min_average_plies:
        failures.add(FailureCode.TOO_SHORT.value)
    if profile["average_plies"] > definition.max_plies * gates.max_average_plies_fraction:
        failures.add(FailureCode.TOO_LONG.value)
    interval = profile["decisive_a_wilson_95"]
    if interval is not None:
        if interval[0] > 0.5 + gates.dominance_interval_margin:
            failures.add(FailureCode.A_DOMINANT.value)
        if interval[1] < 0.5 - gates.dominance_interval_margin:
            failures.add(FailureCode.B_DOMINANT.value)
    return sorted(failures)


def _raw_by_treatment_hash(
    candidates: Sequence[Mapping[str, Any]],
) -> Dict[str, Mapping[str, Any]]:
    result = {}
    for candidate in candidates:
        game_hash = candidate["treatment"]["definition_hash"]
        if game_hash in result:
            raise ValueError("raw treatments must be unique")
        result[game_hash] = candidate
    return result


def _stress_input_projection(value: Mapping[str, Any]) -> Dict[str, Any]:
    expected = (
        "pair_id",
        "source_case_id",
        "definition_hash",
        "status",
        "profile_evidence",
        "expanded_nodes",
    )
    if not isinstance(value, Mapping) or not set(expected).issubset(value):
        raise ValueError("stress evaluation is missing required evidence")
    return {key: _json_copy(value[key], "stress " + key) for key in expected}


def _frontier_category(frontier: Sequence[Mapping[str, Any]]) -> str:
    outcomes = {candidate["exact_forced_result"] for candidate in frontier}
    if not outcomes:
        return "EMPTY"
    if outcomes == {"A_WIN"}:
        return "ONE_SIDED_A"
    if outcomes == {"B_WIN"}:
        return "ONE_SIDED_B"
    if outcomes == {"A_WIN", "B_WIN"}:
        return "ROLE_DIVERSE"
    raise ValueError("interaction frontier contains an impossible exact outcome")


def _stress_assessments(
    raw_candidates: Sequence[Mapping[str, Any]],
    selection: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    node_censors = sum(item["status"] == "CENSORED_NODE_BUDGET" for item in candidates)
    direction_mismatches = sum(item.get("direction_match") is False for item in candidates)
    unselected = selection["unselected_eligible_count"]
    completed = len(candidates) - node_censors
    frontier = [item for item in candidates if item.get("interaction_frontier") is True]
    category = _frontier_category(frontier)
    frontier_strata = {_stratum_identity(item["stratum"]) for item in frontier}
    incomplete = bool(node_censors or direction_mismatches or unselected)
    if direction_mismatches:
        strong_status = "NOT_SUPPORTED"
        strong_reasons = ["SAMPLED_DIRECTION_MISMATCH"]
    elif node_censors or unselected:
        strong_status = "INCONCLUSIVE"
        strong_reasons = []
        if node_censors:
            strong_reasons.append("NODE_BUDGET_CENSORING")
        if unselected:
            strong_reasons.append("CANDIDATE_CAP_CENSORING")
    elif completed >= 15:
        strong_status = "SUPPORTED"
        strong_reasons = []
    else:
        strong_status = "INCONCLUSIVE"
        strong_reasons = ["FEWER_THAN_15_COMPLETIONS"]

    raw_assessments = raw_candidates and _build_raw_aggregate(raw_candidates)[
        "predeclared_assessment"
    ]
    assert raw_assessments
    cycling = raw_assessments["cycling_dominance"]
    if incomplete:
        overall = "INCONCLUSIVE"
    elif cycling["status"] == "DOMINANT" or category in {
        "EMPTY",
        "ONE_SIDED_A",
        "ONE_SIDED_B",
    }:
        overall = "NOT_SUPPORTED"
    elif (
        raw_assessments["primary_counterplay_response"]["status"] == "SUPPORTED"
        and raw_assessments["realized_capture_response"]["status"] == "SUPPORTED"
        and category == "ROLE_DIVERSE"
        and len(frontier) >= 4
        and len(frontier_strata) >= 2
    ):
        overall = "SUPPORTED"
    else:
        overall = "INCONCLUSIVE"

    if incomplete:
        next_branch = "INCONCLUSIVE"
    elif cycling["status"] == "DOMINANT":
        next_branch = "REJECT_CYCLING"
    elif category == "ONE_SIDED_B":
        next_branch = "REJECT_ONE_SIDED_B"
    elif category == "ONE_SIDED_A":
        next_branch = "REJECT_ONE_SIDED_A"
    elif category == "EMPTY":
        next_branch = "REASSESS_FAMILY"
    elif overall == "SUPPORTED":
        next_branch = "FREEZE_OUTCOME_BLIND_VALIDATION"
    else:
        next_branch = "FOCUSED_OUTCOME_BLIND_VALIDATION"

    return {
        "general_strong_response": {
            "status": strong_status,
            "completion_count": completed,
            "reasons": strong_reasons,
        },
        "interaction_frontier": {
            "status": "INCONCLUSIVE" if incomplete else "COMPLETE",
            "category": None if incomplete else category,
            "descriptive_category": category,
            "case_count": len(frontier),
            "stratum_count": len(frontier_strata),
            "a_win_count": sum(item["exact_forced_result"] == "A_WIN" for item in frontier),
            "b_win_count": sum(item["exact_forced_result"] == "B_WIN" for item in frontier),
            "definition_hashes": sorted(item["definition_hash"] for item in frontier),
        },
        "overall_interaction_response": {
            "status": overall,
            "next_branch": next_branch,
        },
    }


def extend_capture_stress_inspection(
    raw_result_or_candidates: Any,
    raw_inspection: Mapping[str, Any],
    stress_candidates: Sequence[Mapping[str, Any]],
    selection: Mapping[str, Any],
) -> Dict[str, Any]:
    """Extend, never replace, the frozen raw inspection selection."""

    raw_candidates = _raw_candidates(raw_result_or_candidates)
    by_hash = _raw_by_treatment_hash(raw_candidates)
    raw_value = _exact_keys(
        raw_inspection,
        (
            "version",
            "adaptive_stress_disposition",
            "selected",
            "pool_counts",
            "requested_counts",
            "shortfalls",
        ),
        "raw inspection",
    )
    if raw_value["adaptive_stress_disposition"] != "ELIGIBLE":
        raise ValueError("stress inspection cannot extend a blocked raw selection")
    reasons: Dict[str, Set[str]] = defaultdict(set)
    for item in raw_value["selected"]:
        game_hash = item["definition_hash"]
        if game_hash not in by_hash:
            raise ValueError("raw inspection references an unknown treatment")
        reasons[game_hash].update(item["reasons"])
    for item in selection["selected"]:
        reasons[item["definition_hash"]].add("STRESS_SELECTED")
    for item in stress_candidates:
        game_hash = item["definition_hash"]
        if item["status"] == "CENSORED_NODE_BUDGET":
            reasons[game_hash].add("NODE_CENSOR")
        if item.get("interaction_frontier") is True:
            reasons[game_hash].add("INTERACTION_FRONTIER")
    source_order = {
        candidate["treatment"]["definition_hash"]: index
        for index, candidate in enumerate(raw_candidates)
    }
    selected = []
    for game_hash in sorted(reasons, key=lambda item: source_order[item]):
        candidate = by_hash[game_hash]
        selected.append(
            {
                "pair_id": candidate["pair_id"],
                "source_case_id": candidate["source_case_id"],
                "definition_hash": game_hash,
                "reasons": sorted(reasons[game_hash]),
            }
        )
    return {
        "version": "capture-stress-inspection-v1",
        "raw_selection": _json_copy(raw_value, "raw inspection"),
        "selected": selected,
        "pool_shortfalls": {
            "raw": _json_copy(raw_value["shortfalls"], "raw shortfalls"),
            "stress_unselected_eligible": selection["unselected_eligible_count"],
        },
    }


def build_capture_stress_result(
    raw_result_or_candidates: Any,
    evaluations: Sequence[Mapping[str, Any]],
    *,
    gates: PlayGates = PlayGates(),
    max_candidates: int = CAPTURE_STRESS_MAX_CANDIDATES,
    expected_seeds: Sequence[int] = CAPTURE_STRESS_SEEDS,
    raw_inspection: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Validate stress traces and apply all predeclared assessments in order."""

    raw_candidates = _raw_candidates(raw_result_or_candidates)
    selection = select_capture_stress_candidates(
        raw_candidates, max_candidates=max_candidates
    )
    seeds = _validate_seed_sequence(expected_seeds, "capture stress")
    if not isinstance(evaluations, (list, tuple)):
        raise ValueError("stress evaluations must be an array")
    if len(evaluations) != selection["selected_count"]:
        raise ValueError("stress evaluation count must equal selected count")
    by_hash = _raw_by_treatment_hash(raw_candidates)
    enriched = []
    for index, (selected, raw_evaluation) in enumerate(
        zip(selection["selected"], evaluations)
    ):
        evaluation = _stress_input_projection(raw_evaluation)
        if any(
            evaluation[field] != selected[field]
            for field in ("pair_id", "source_case_id", "definition_hash")
        ):
            raise ValueError("stress evaluation identity/order mismatch")
        raw_candidate = by_hash[selected["definition_hash"]]
        definition = parse_definition(raw_candidate["treatment"]["definition"])
        exact = _candidate_exact_result(raw_candidate["treatment"])
        assert exact is not None
        evidence = validate_capture_profile_evidence(
            definition,
            evaluation["profile_evidence"],
            expected_seeds=seeds,
        )
        if evidence["profile"] != "strong-minimax-depth{}".format(
            CAPTURE_STRESS_DEPTH
        ):
            raise ValueError("stress profile identity mismatch")
        if evidence["status"] != evaluation["status"]:
            raise ValueError("stress evaluation/profile status mismatch")
        expanded_nodes = evaluation["expanded_nodes"]
        if type(expanded_nodes) is not int or not 0 <= expanded_nodes <= CAPTURE_STRESS_MAX_NODES:
            raise ValueError("stress expanded_nodes is outside the frozen cap")
        if evidence["status"] == "CENSORED_NODE_BUDGET":
            if (
                evidence["budget_observation"]["max_nodes"]
                != CAPTURE_STRESS_MAX_NODES
                or expanded_nodes
                != evidence["budget_observation"]["visited_nodes"]
                or expanded_nodes != CAPTURE_STRESS_MAX_NODES
            ):
                raise ValueError("stress censored node counts disagree")
            profile = None
            direction = None
            direction_match = None
            failure_codes = None
            interaction = False
        else:
            if expanded_nodes < 1:
                raise ValueError("completed stress evidence must expand at least one node")
            profile = _sampled_profile_from_evidence(evidence)
            direction = sampled_direction(profile)
            direction_match = direction == exact["forced_result"]
            failure_codes = _strong_failure_codes(definition, profile, gates)
            interaction = bool(
                direction_match
                and not set(failure_codes).intersection(_SHAPE_FAILURES)
                and evidence["profile_summary"]["games_with_capture"] > 0
            )
        enriched.append(
            {
                "selection_index": index,
                "pair_id": selected["pair_id"],
                "source_case_id": selected["source_case_id"],
                "definition_hash": selected["definition_hash"],
                "stratum": _json_copy(raw_candidate["stratum"], "stress stratum"),
                "selection_tier": selected["selection_tier"],
                "selection_score": selected["selection_score"],
                "status": evidence["status"],
                "profile_evidence": evidence,
                "expanded_nodes": expanded_nodes,
                "sampled_profile": profile,
                "sampled_direction": direction,
                "exact_forced_result": exact["forced_result"],
                "direction_match": direction_match,
                "strong_failure_codes": failure_codes,
                "interaction_frontier": interaction,
            }
        )
    assessments = _stress_assessments(raw_candidates, selection, enriched)
    aggregate = {
        "eligible_count": selection["eligible_count"],
        "selected_count": selection["selected_count"],
        "unselected_eligible_count": selection["unselected_eligible_count"],
        "completed_count": sum(item["status"] == "COMPLETED" for item in enriched),
        "node_censored_count": sum(
            item["status"] == "CENSORED_NODE_BUDGET" for item in enriched
        ),
        "direction_mismatch_count": sum(
            item["direction_match"] is False for item in enriched
        ),
        "interaction_frontier_count": sum(
            item["interaction_frontier"] for item in enriched
        ),
        "expanded_nodes_total": sum(item["expanded_nodes"] for item in enriched),
        "expanded_nodes_max": max(
            (item["expanded_nodes"] for item in enriched), default=0
        ),
        "predeclared_assessment": assessments,
    }
    inspection_source = (
        raw_inspection
        if raw_inspection is not None
        else (
            raw_result_or_candidates["pre_stress_inspection"]
            if isinstance(raw_result_or_candidates, Mapping)
            and "pre_stress_inspection" in raw_result_or_candidates
            else select_capture_raw_inspection(raw_candidates)
        )
    )
    inspection = extend_capture_stress_inspection(
        raw_candidates, inspection_source, enriched, selection
    )
    return {
        "protocol_id": "capture-v1-adaptive-interaction-stress",
        "configuration": {
            "depth": CAPTURE_STRESS_DEPTH,
            "seeds": list(seeds),
            "max_nodes_per_definition": CAPTURE_STRESS_MAX_NODES,
            "max_candidates": max_candidates,
            "play_gates": asdict(gates),
        },
        "selection": selection,
        "aggregate": aggregate,
        "inspection": inspection,
        "candidates": enriched,
    }


def validate_capture_stress_result(
    result: Mapping[str, Any],
    raw_result_or_candidates: Any,
    *,
    gates: PlayGates = PlayGates(),
) -> Dict[str, Any]:
    value = _exact_keys(
        result,
        ("protocol_id", "configuration", "selection", "aggregate", "inspection", "candidates"),
        "capture stress result",
    )
    if value["protocol_id"] != "capture-v1-adaptive-interaction-stress":
        raise ValueError("capture stress protocol identity mismatch")
    configuration = _exact_keys(
        value["configuration"],
        ("depth", "seeds", "max_nodes_per_definition", "max_candidates", "play_gates"),
        "capture stress configuration",
    )
    if (
        configuration["depth"] != CAPTURE_STRESS_DEPTH
        or configuration["max_nodes_per_definition"] != CAPTURE_STRESS_MAX_NODES
        or configuration["max_candidates"] != CAPTURE_STRESS_MAX_CANDIDATES
        or _canonical_bytes(configuration["seeds"])
        != _canonical_bytes(list(CAPTURE_STRESS_SEEDS))
        or _canonical_bytes(configuration["play_gates"])
        != _canonical_bytes(asdict(gates))
    ):
        raise ValueError("capture stress frozen configuration mismatch")
    evaluations = [_stress_input_projection(item) for item in value["candidates"]]
    raw_inspection = (
        raw_result_or_candidates["pre_stress_inspection"]
        if isinstance(raw_result_or_candidates, Mapping)
        and "pre_stress_inspection" in raw_result_or_candidates
        else value["inspection"]["raw_selection"]
    )
    rebuilt = build_capture_stress_result(
        raw_result_or_candidates,
        evaluations,
        gates=gates,
        max_candidates=configuration["max_candidates"],
        expected_seeds=configuration["seeds"],
        raw_inspection=raw_inspection,
    )
    if _canonical_bytes(value) != _canonical_bytes(rebuilt):
        raise ValueError("capture stress result does not reconstruct")
    return _json_copy(value, "capture stress result")


def stress_capture_interactions(
    raw_result: Mapping[str, Any],
    *,
    seeds: Sequence[int] = CAPTURE_STRESS_SEEDS,
    depth: int = CAPTURE_STRESS_DEPTH,
    max_nodes: int = CAPTURE_STRESS_MAX_NODES,
    max_candidates: int = CAPTURE_STRESS_MAX_CANDIDATES,
    gates: PlayGates = PlayGates(),
    clock: Callable[[], float] = time.perf_counter,
) -> Dict[str, Any]:
    """Run the selected depth-5 profiles with a cumulative per-case node cap."""

    if depth != CAPTURE_STRESS_DEPTH or max_nodes != CAPTURE_STRESS_MAX_NODES:
        raise ValueError("capture stress must use the frozen depth and node cap")
    seed_tuple = _validate_seed_sequence(seeds, "capture stress")
    if (
        seed_tuple != CAPTURE_STRESS_SEEDS
        or max_candidates != CAPTURE_STRESS_MAX_CANDIDATES
        or gates != PlayGates()
    ):
        raise ValueError("capture stress must use the frozen seeds, gates, and candidate cap")
    raw_candidates = _raw_candidates(raw_result)
    aggregate = raw_result.get("aggregate")
    if not isinstance(aggregate, Mapping):
        raise ValueError("raw result is missing its aggregate exact census")
    censored_hashes = []
    for candidate in raw_candidates:
        treatment = candidate.get("treatment")
        exact = treatment.get("exact") if isinstance(treatment, Mapping) else None
        game_hash = treatment.get("definition_hash") if isinstance(treatment, Mapping) else None
        if not isinstance(exact, Mapping) or not isinstance(game_hash, str):
            raise ValueError("raw candidate is missing treatment exact evidence")
        if exact.get("status") != "COMPLETED":
            censored_hashes.append(game_hash)
    expected_census = {
        "exact_attempted": len(raw_candidates),
        "exact_completed": len(raw_candidates) - len(censored_hashes),
        "exact_censored": len(censored_hashes),
        "exact_censored_hashes": sorted(censored_hashes),
    }
    if any(
        _canonical_bytes(aggregate.get(field)) != _canonical_bytes(expected)
        for field, expected in expected_census.items()
    ):
        raise ValueError("raw aggregate exact census does not reconstruct")
    if censored_hashes:
        raise ValueError("adaptive stress is blocked by exact censoring")
    inspection = raw_result.get("pre_stress_inspection")
    if not isinstance(inspection, Mapping):
        raise ValueError("raw result is missing frozen pre-stress inspection")
    if inspection.get("adaptive_stress_disposition") != "ELIGIBLE":
        raise ValueError("adaptive stress is blocked by exact censoring")
    selection = select_capture_stress_candidates(
        raw_candidates, max_candidates=max_candidates
    )
    by_hash = _raw_by_treatment_hash(raw_candidates)
    evaluations = []
    for selected in selection["selected"]:
        raw_candidate = by_hash[selected["definition_hash"]]
        definition = parse_definition(raw_candidate["treatment"]["definition"])
        agent = MinimaxAgent(depth=depth, max_total_nodes=max_nodes)
        agent.reset_budget()
        records = []
        status = "COMPLETED"
        incomplete_seed = None
        budget_observation = None
        for seed in seed_tuple:
            try:
                record = play_game(
                    definition,
                    {Player.A: agent, Player.B: agent},
                    seed,
                )
            except SearchBudgetExceeded as error:
                if error.scope != "per-candidate":
                    raise
                status = "CENSORED_NODE_BUDGET"
                incomplete_seed = seed
                budget_observation = {
                    "visited_nodes": error.visited_nodes,
                    "max_nodes": error.max_nodes,
                    "scope": error.scope,
                }
                break
            records.append(record)
        profile_name = "strong-minimax-depth{}".format(depth)
        if status == "COMPLETED":
            evidence = build_capture_profile_evidence(
                definition, profile_name, records, seed_tuple
            )
        else:
            assert incomplete_seed is not None and budget_observation is not None
            evidence = build_censored_capture_profile_evidence(
                definition,
                profile_name,
                records,
                seed_tuple,
                incomplete_seed,
                budget_observation,
            )
        evaluations.append(
            {
                "pair_id": selected["pair_id"],
                "source_case_id": selected["source_case_id"],
                "definition_hash": selected["definition_hash"],
                "status": status,
                "profile_evidence": evidence,
                "expanded_nodes": agent.total_nodes,
            }
        )
    return build_capture_stress_result(
        raw_result,
        evaluations,
        gates=gates,
        max_candidates=max_candidates,
        expected_seeds=seed_tuple,
        raw_inspection=inspection,
    )
