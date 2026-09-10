"""Pure paired-corpus and evaluation logic for the stalemate-draw experiment.

This module deliberately contains no filesystem, Git, reservation, or command-line
work.  Experiment runners are responsible for pinning bytes and invoking these
functions only at the corresponding sealed stage.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from typing import Any, Callable, DefaultDict, Dict, Mapping, Optional, Sequence, Set, Tuple

from .agents import (
    GoalDirectedAgent,
    MinimaxAgent,
    RandomAgent,
    SearchBudgetExceeded,
)
from .analysis import FailureCode, analyze_definition
from .asymmetry import evaluate_asymmetry
from .audit import sampled_direction
from .batch import PlayGates, classify_play_failures
from .dsl import Player, definition_hash, parse_definition
from .engine import replay_dicts
from .landscape_evaluation import (
    DRAW_STRESS_DEPTH,
    DRAW_STRESS_MAX_CANDIDATES,
    DRAW_STRESS_MAX_NODES,
    DRAW_STRESS_SEEDS,
    LANDSCAPE_EXACT_MAX_STATES,
    LANDSCAPE_PLAY_SEEDS,
    evaluate_landscape_cases,
)
from .play import evaluate_matchup
from .simplicity import evaluate_simplicity, exceeds_limits
from .symmetry import d4_canonical_hash


STALEMATE_MANIFEST_VERSION = 1
STALEMATE_MANIFEST_ID = "generator-v2-3x3-stalemate-paired-v1"
STALEMATE_PROTOCOL_ID = "stalemate-v1-paired-manifest-freeze"
STALEMATE_SOURCE_MANIFEST_ID = "generator-v2-3x3-landscape-v1"
STALEMATE_SOURCE_MANIFEST_SHA256 = (
    "f407aefb5fdb8c926db282ff90d2feb1a8666cda3fdbd6925b9f5cc07abd87b1"
)
STALEMATE_SOURCE_CASE_COUNT = 384
STALEMATE_PAIR_COUNT = 128
STALEMATE_STRATUM_COUNT = 32
STALEMATE_QUOTA_PER_STRATUM = 4
STALEMATE_MAX_PLIES = 18
STALEMATE_INSPECTION_CHANGE_COUNT = 16
STALEMATE_INSPECTION_CONTROL_COUNT = 16

_PAIR_PREFIX = "stalemate-pair-v1:"
_SELECTION_PREFIX = "stalemate-selection-v1:"
_STRESS_CLEAN_PREFIX = "stalemate-stress-clean-v1:"
_STRESS_OTHER_PREFIX = "stalemate-stress-other-v1:"
_INSPECTION_CHANGE_PREFIX = "stalemate-inspection-change-v1:"
_INSPECTION_CONTROL_PREFIX = "stalemate-inspection-control-v1:"
_FORCED_RESULTS = ("A_WIN", "B_WIN", "DRAW")
_EXACT_RESULT_KEYS = {
    "value_for_a",
    "forced_result",
    "principal_variation",
    "principal_variation_plies",
    "terminal_reason",
    "searched_states",
    "cache_hits",
}
_PROFILE_KEYS = {
    "profile",
    "agent_a",
    "agent_b",
    "samples",
    "a_wins",
    "b_wins",
    "draws",
    "a_win_rate",
    "b_win_rate",
    "draw_rate",
    "average_plies",
    "decisive_a_share",
    "decisive_a_wilson_95",
    "terminal_reasons",
    "seeds",
}
_CHEAP_PROFILE_IDENTITIES = (
    ("weak-random", "random-v1-weak"),
    ("medium-goal-directed", "goal_directed-v1-medium"),
)
_SHAPE_FAILURES = {
    FailureCode.EXCESSIVE_DRAWS.value,
    FailureCode.TOO_SHORT.value,
    FailureCode.TOO_LONG.value,
}
_SOURCE_CASE_KEYS = {
    "case_id",
    "stratum",
    "vector_count",
    "selection_score",
    "selection_rank",
    "definition_hash",
    "d4_canonical_hash",
    "definition",
}
_STRATUM_KEYS = {
    "first_player",
    "goal_axis_relation",
    "runner_start_class",
    "max_plies",
    "vector_count_band",
}
_PAIR_KEYS = {
    "pair_index",
    "pair_id",
    "pair_fingerprint",
    "source_case_id",
    "source_definition_hash",
    "source_d4_canonical_hash",
    "source_selection_score",
    "source_selection_rank",
    "treatment_definition_hash",
    "treatment_d4_canonical_hash",
    "stratum",
    "vector_count",
    "source_definition",
    "treatment_definition",
}
_RAW_CANDIDATE_KEYS = {
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
    "pair_index",
    "pair_id",
    "pair_fingerprint",
    "source_case_id",
    "source_definition_hash",
    "source_d4_canonical_hash",
    "baseline_exact",
    "baseline_to_treatment_terminal_reason_transition",
    "principal_variation_plies_delta",
    "natural_exhaustion_bound",
    "cheap_natural_bound_profiles",
    "shape_clean_stalemate_draw",
}
_STRESS_CANDIDATE_KEYS = {
    "pair_id",
    "source_case_id",
    "definition_hash",
    "d4_canonical_hash",
    "stratum",
    "shape_clean",
    "selection_group",
    "selection_score",
    "selection_rank",
    "status",
    "sampled_direction",
    "decisive_misclassification",
    "strong_failure_codes",
    "diagnostic_frontier",
    "expanded_nodes",
    "elapsed_seconds",
    "budget_observation",
    "profile",
    "definition",
}
_MANIFEST_KEYS = {
    "manifest_id",
    "manifest_version",
    "protocol_id",
    "source_manifest_id",
    "source_manifest_sha256",
    "provenance",
    "selection_protocol",
    "census",
    "selection_fingerprint",
    "strata",
    "pairs",
}


def _json_copy(value: Any, label: str) -> Any:
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


def _canonical_bytes(value: Any, label: str) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ValueError("{} must be JSON-serializable".format(label)) from error


def _domain_hash(prefix: str, value: Any, label: str) -> str:
    return hashlib.sha256(prefix.encode("ascii") + _canonical_bytes(value, label)).hexdigest()


def _require_sha256(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError("{} must be a lowercase SHA-256 hex digest".format(label))
    return value


def _same_json_value(left: Any, right: Any) -> bool:
    """Compare JSON-shaped evidence without Python's bool/int equivalence."""

    if isinstance(left, Mapping) or isinstance(right, Mapping):
        if not isinstance(left, Mapping) or not isinstance(right, Mapping):
            return False
        return set(left) == set(right) and all(
            _same_json_value(left[key], right[key]) for key in left
        )
    if isinstance(left, list) or isinstance(right, list):
        if not isinstance(left, list) or not isinstance(right, list):
            return False
        return len(left) == len(right) and all(
            _same_json_value(left_item, right_item)
            for left_item, right_item in zip(left, right)
        )
    return type(left) is type(right) and left == right


def _stratum_identity(stratum: Mapping[str, Any]) -> str:
    return json.dumps(stratum, sort_keys=True, separators=(",", ":"))


def stalemate_natural_exhaustion_bound(
    definition_mapping: Mapping[str, Any],
) -> int:
    """Prove the action-count bound for the frozen monotone-placement family."""

    if not isinstance(definition_mapping, Mapping):
        raise TypeError("stalemate definition must be an object")
    canonical = parse_definition(definition_mapping).to_dict()
    roles = canonical["roles"]
    initial = canonical["initial_pieces"]
    if (
        canonical["board_size"] != 3
        or canonical["max_plies"] != STALEMATE_MAX_PLIES
        or len(initial) != 1
        or initial[0].get("owner") != "B"
        or initial[0].get("piece") != "runner"
        or roles["A"]["action"] != {"kind": "PLACE", "piece": "seed"}
        or roles["B"]["action"].get("kind") != "MOVE"
        or roles["B"]["action"].get("piece") != "runner"
        or not roles["B"]["action"].get("vectors")
    ):
        raise ValueError("definition violates the 3x3 one-runner exhaustion proof")
    empty_cells = canonical["board_size"] ** 2 - len(initial)
    first_player = canonical["first_player"]
    if first_player == "A":
        return 2 * empty_cells - 1
    if first_player == "B":
        return 2 * empty_cells
    raise ValueError("stalemate definition has an unknown first player")


def _validate_source_structure(
    case: Mapping[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any], int]:
    if set(case) != _SOURCE_CASE_KEYS:
        raise ValueError("source landscape case fields do not match the frozen schema")
    case_id = case.get("case_id")
    if not isinstance(case_id, str) or not case_id:
        raise ValueError("source landscape case needs a non-empty case_id")
    _require_sha256(case.get("selection_score"), "source selection_score")
    selection_rank = case.get("selection_rank")
    if (
        not isinstance(selection_rank, int)
        or isinstance(selection_rank, bool)
        or not 1 <= selection_rank <= STALEMATE_QUOTA_PER_STRATUM
    ):
        raise ValueError("source landscape selection_rank is outside the frozen quota")
    source_mapping = case.get("definition")
    if not isinstance(source_mapping, Mapping):
        raise ValueError("source landscape case needs a definition")
    source_value = _json_copy(source_mapping, "source definition")
    if source_value.get("schema_version") != 1 or "terminal_policy" in source_value:
        raise ValueError("stalemate pairs require an immutable schema-v1 source")
    source = parse_definition(source_value)
    canonical_source = source.to_dict()
    if canonical_source != source_value:
        raise ValueError("source definition is not in canonical DSL form")
    if definition_hash(source) != case.get("definition_hash"):
        raise ValueError("source definition hash mismatch for {}".format(case_id))
    if d4_canonical_hash(source) != case.get("d4_canonical_hash"):
        raise ValueError("source D4 hash mismatch for {}".format(case_id))

    try:
        stalemate_natural_exhaustion_bound(canonical_source)
    except ValueError as error:
        raise ValueError(
            "source {} violates the 3x3 one-runner monotone-placement proof".format(
                case_id
            )
        ) from error
    roles = canonical_source["roles"]
    vectors = roles["B"]["action"].get("vectors")
    if not isinstance(vectors, list) or not vectors:
        raise ValueError("source {} needs runner movement vectors".format(case_id))
    vector_count = len(vectors)
    if (
        isinstance(case.get("vector_count"), bool)
        or not isinstance(case.get("vector_count"), int)
        or case.get("vector_count") != vector_count
    ):
        raise ValueError("source vector count mismatch for {}".format(case_id))

    stratum = case.get("stratum")
    if not isinstance(stratum, Mapping) or set(stratum) != _STRATUM_KEYS:
        raise ValueError("source landscape case needs the frozen stratum schema")
    stratum_value = _json_copy(stratum, "source stratum")
    if (
        stratum_value.get("max_plies") != STALEMATE_MAX_PLIES
        or stratum_value.get("first_player") != canonical_source["first_player"]
    ):
        raise ValueError("source stratum mismatch for {}".format(case_id))

    treatment_value = _json_copy(canonical_source, "treatment definition")
    treatment_value["schema_version"] = 2
    treatment_value["terminal_policy"] = {"no_legal_action": "DRAW"}
    treatment = parse_definition(treatment_value)
    canonical_treatment = treatment.to_dict()
    if canonical_treatment != treatment_value:
        raise ValueError("treatment definition is not in canonical DSL form")
    comparison = _json_copy(canonical_treatment, "treatment comparison")
    comparison.pop("terminal_policy")
    comparison["schema_version"] = 1
    if comparison != canonical_source:
        raise ValueError("treatment changes a field outside terminal policy")
    return canonical_source, canonical_treatment, vector_count


def _pair_fingerprint_payload(pair: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "source_case_id": pair["source_case_id"],
        "source_definition_hash": pair["source_definition_hash"],
        "source_d4_canonical_hash": pair["source_d4_canonical_hash"],
        "source_selection_score": pair["source_selection_score"],
        "source_selection_rank": pair["source_selection_rank"],
        "treatment_definition_hash": pair["treatment_definition_hash"],
        "treatment_d4_canonical_hash": pair["treatment_d4_canonical_hash"],
        "stratum": pair["stratum"],
        "vector_count": pair["vector_count"],
    }


def _selection_protocol() -> Dict[str, Any]:
    return {
        "baseline_informed": True,
        "treatment_outcome_free": True,
        "case_membership": "all source cases with stratum.max_plies == 18",
        "source_order_preserved": True,
        "pair_fingerprint": (
            "sha256(stalemate-pair-v1:<canonical pair identity JSON>)"
        ),
        "selection_fingerprint": (
            "sha256(stalemate-selection-v1:<ordered pair fingerprints JSON>)"
        ),
    }


def build_stalemate_paired_manifest(
    landscape_manifest: Mapping[str, Any],
    source_manifest_sha256: str,
    provenance: Any,
) -> Dict[str, Any]:
    """Transform all frozen 18-ply landscape cases without evaluating outcomes."""

    if not isinstance(landscape_manifest, Mapping):
        raise TypeError("landscape_manifest must be an object")
    if landscape_manifest.get("manifest_id") != STALEMATE_SOURCE_MANIFEST_ID:
        raise ValueError("stalemate pairs require the frozen landscape-v1 manifest")
    if not isinstance(provenance, Mapping):
        raise TypeError("provenance must be an object")
    source_hash = _require_sha256(source_manifest_sha256, "source_manifest_sha256")
    if source_hash != STALEMATE_SOURCE_MANIFEST_SHA256:
        raise ValueError("stalemate pairs require the frozen landscape manifest bytes")
    raw_cases = landscape_manifest.get("cases")
    if not isinstance(raw_cases, list) or len(raw_cases) != STALEMATE_SOURCE_CASE_COUNT:
        raise ValueError(
            "source landscape must contain exactly {} cases".format(
                STALEMATE_SOURCE_CASE_COUNT
            )
        )

    selected = []
    for raw_case in raw_cases:
        if not isinstance(raw_case, Mapping):
            raise ValueError("source landscape cases must be objects")
        stratum = raw_case.get("stratum")
        if not isinstance(stratum, Mapping):
            raise ValueError("source landscape case needs a stratum")
        if stratum.get("max_plies") == STALEMATE_MAX_PLIES:
            selected.append(raw_case)
    if len(selected) != STALEMATE_PAIR_COUNT:
        raise ValueError(
            "stalemate selection must contain exactly {} pairs".format(
                STALEMATE_PAIR_COUNT
            )
        )

    pairs = []
    seen_source_ids: Set[str] = set()
    seen_source_hashes: Set[str] = set()
    seen_source_orbits: Set[str] = set()
    seen_treatment_hashes: Set[str] = set()
    seen_treatment_orbits: Set[str] = set()
    strata: DefaultDict[str, list[str]] = defaultdict(list)
    for pair_index, source_case in enumerate(selected):
        source_mapping, treatment_mapping, vector_count = _validate_source_structure(
            source_case
        )
        source = parse_definition(source_mapping)
        treatment = parse_definition(treatment_mapping)
        source_id = source_case["case_id"]
        source_hash_value = definition_hash(source)
        source_orbit = d4_canonical_hash(source)
        treatment_hash = definition_hash(treatment)
        treatment_orbit = d4_canonical_hash(treatment)
        if source_id in seen_source_ids:
            raise ValueError("duplicate source case_id in stalemate selection")
        if source_hash_value in seen_source_hashes or source_orbit in seen_source_orbits:
            raise ValueError("duplicate source definition or D4 orbit in stalemate selection")
        if treatment_hash in seen_treatment_hashes or treatment_orbit in seen_treatment_orbits:
            raise ValueError("duplicate treatment definition or D4 orbit")
        if treatment_hash == source_hash_value or treatment_orbit == source_orbit:
            raise ValueError("terminal treatment must have distinct DSL and D4 identities")
        seen_source_ids.add(source_id)
        seen_source_hashes.add(source_hash_value)
        seen_source_orbits.add(source_orbit)
        seen_treatment_hashes.add(treatment_hash)
        seen_treatment_orbits.add(treatment_orbit)

        pair = {
            "pair_index": pair_index,
            "pair_id": "stalemate-v1-pair-{:03d}".format(pair_index + 1),
            "source_case_id": source_id,
            "source_definition_hash": source_hash_value,
            "source_d4_canonical_hash": source_orbit,
            "source_selection_score": source_case["selection_score"],
            "source_selection_rank": source_case["selection_rank"],
            "treatment_definition_hash": treatment_hash,
            "treatment_d4_canonical_hash": treatment_orbit,
            "stratum": _json_copy(source_case["stratum"], "pair stratum"),
            "vector_count": vector_count,
            "source_definition": source_mapping,
            "treatment_definition": treatment_mapping,
        }
        pair["pair_fingerprint"] = _domain_hash(
            _PAIR_PREFIX, _pair_fingerprint_payload(pair), "pair fingerprint"
        )
        pairs.append(pair)
        strata[_stratum_identity(pair["stratum"])].append(pair["pair_id"])

    if len(strata) != STALEMATE_STRATUM_COUNT:
        raise ValueError(
            "stalemate selection must contain exactly {} strata".format(
                STALEMATE_STRATUM_COUNT
            )
        )
    if any(len(pair_ids) != STALEMATE_QUOTA_PER_STRATUM for pair_ids in strata.values()):
        raise ValueError(
            "every stalemate stratum must contain exactly {} pairs".format(
                STALEMATE_QUOTA_PER_STRATUM
            )
        )
    selection_payload = [
        {
            "pair_index": pair["pair_index"],
            "pair_id": pair["pair_id"],
            "pair_fingerprint": pair["pair_fingerprint"],
        }
        for pair in pairs
    ]
    selection_fingerprint = _domain_hash(
        _SELECTION_PREFIX, selection_payload, "selection fingerprint"
    )
    manifest = {
        "manifest_id": STALEMATE_MANIFEST_ID,
        "manifest_version": STALEMATE_MANIFEST_VERSION,
        "protocol_id": STALEMATE_PROTOCOL_ID,
        "source_manifest_id": STALEMATE_SOURCE_MANIFEST_ID,
        "source_manifest_sha256": source_hash,
        "provenance": _json_copy(provenance, "provenance"),
        "selection_protocol": _selection_protocol(),
        "census": {
            "source_case_count": len(raw_cases),
            "pair_count": len(pairs),
            "stratum_count": len(strata),
            "quota_per_stratum": STALEMATE_QUOTA_PER_STRATUM,
        },
        "selection_fingerprint": selection_fingerprint,
        "strata": [
            {
                "stratum": json.loads(identity),
                "pair_ids": list(pair_ids),
                "pair_count": len(pair_ids),
            }
            for identity, pair_ids in sorted(strata.items())
        ],
        "pairs": pairs,
    }
    validate_stalemate_paired_manifest(manifest)
    return manifest


def validate_stalemate_paired_manifest(
    manifest: Mapping[str, Any],
) -> Tuple[Mapping[str, Any], ...]:
    """Validate the complete frozen 128-pair/32-stratum manifest contract."""

    if not isinstance(manifest, Mapping):
        raise TypeError("paired manifest must be an object")
    if set(manifest) != _MANIFEST_KEYS:
        raise ValueError("paired manifest fields do not match the frozen schema")
    if (
        manifest.get("manifest_id") != STALEMATE_MANIFEST_ID
        or isinstance(manifest.get("manifest_version"), bool)
        or not isinstance(manifest.get("manifest_version"), int)
        or manifest.get("manifest_version") != STALEMATE_MANIFEST_VERSION
        or manifest.get("protocol_id") != STALEMATE_PROTOCOL_ID
    ):
        raise ValueError("paired manifest identity mismatch")
    if manifest.get("source_manifest_id") != STALEMATE_SOURCE_MANIFEST_ID:
        raise ValueError("paired manifest source identity mismatch")
    if (
        _require_sha256(
            manifest.get("source_manifest_sha256"), "source_manifest_sha256"
        )
        != STALEMATE_SOURCE_MANIFEST_SHA256
    ):
        raise ValueError("paired manifest source byte hash mismatch")
    if manifest.get("selection_protocol") != _selection_protocol():
        raise ValueError("paired manifest selection protocol mismatch")
    if not isinstance(manifest.get("provenance"), Mapping):
        raise ValueError("paired manifest provenance must be an object")
    _json_copy(manifest["provenance"], "paired manifest provenance")
    pairs = manifest.get("pairs")
    if not isinstance(pairs, list) or len(pairs) != STALEMATE_PAIR_COUNT:
        raise ValueError(
            "paired manifest must contain exactly {} pairs".format(
                STALEMATE_PAIR_COUNT
            )
        )
    seen_ids: Set[str] = set()
    seen_source_ids: Set[str] = set()
    seen_source_hashes: Set[str] = set()
    seen_source_orbits: Set[str] = set()
    seen_treatment_hashes: Set[str] = set()
    seen_treatment_orbits: Set[str] = set()
    strata: DefaultDict[str, list[str]] = defaultdict(list)
    fingerprints = []
    for expected_index, pair in enumerate(pairs):
        if not isinstance(pair, Mapping) or set(pair) != _PAIR_KEYS:
            raise ValueError("paired manifest pair schema mismatch")
        if (
            isinstance(pair.get("pair_index"), bool)
            or not isinstance(pair.get("pair_index"), int)
            or pair.get("pair_index") != expected_index
        ):
            raise ValueError("paired manifest pair indices must be contiguous")
        pair_id = pair.get("pair_id")
        if (
            pair_id != "stalemate-v1-pair-{:03d}".format(expected_index + 1)
            or pair_id in seen_ids
        ):
            raise ValueError("paired manifest pair IDs must be unique")
        seen_ids.add(pair_id)
        expected_fingerprint = _domain_hash(
            _PAIR_PREFIX, _pair_fingerprint_payload(pair), "pair fingerprint"
        )
        if pair.get("pair_fingerprint") != expected_fingerprint:
            raise ValueError("paired manifest pair fingerprint mismatch")
        source_mapping, treatment_mapping, vector_count = _validate_source_structure(
            {
                "case_id": pair["source_case_id"],
                "stratum": pair["stratum"],
                "vector_count": pair["vector_count"],
                "selection_score": pair["source_selection_score"],
                "selection_rank": pair["source_selection_rank"],
                "definition_hash": pair["source_definition_hash"],
                "d4_canonical_hash": pair["source_d4_canonical_hash"],
                "definition": pair["source_definition"],
            }
        )
        if source_mapping != pair["source_definition"]:
            raise ValueError("paired manifest source definition mismatch")
        if treatment_mapping != pair["treatment_definition"]:
            raise ValueError("paired manifest treatment definition mismatch")
        treatment = parse_definition(treatment_mapping)
        if (
            definition_hash(treatment) != pair["treatment_definition_hash"]
            or d4_canonical_hash(treatment) != pair["treatment_d4_canonical_hash"]
            or vector_count != pair["vector_count"]
        ):
            raise ValueError("paired manifest treatment identity mismatch")
        source_id = pair["source_case_id"]
        source_hash = pair["source_definition_hash"]
        source_orbit = pair["source_d4_canonical_hash"]
        treatment_hash = pair["treatment_definition_hash"]
        treatment_orbit = pair["treatment_d4_canonical_hash"]
        if (
            source_id in seen_source_ids
            or source_hash in seen_source_hashes
            or source_orbit in seen_source_orbits
            or treatment_hash in seen_treatment_hashes
            or treatment_orbit in seen_treatment_orbits
        ):
            raise ValueError("paired manifest definitions and D4 orbits must be unique")
        seen_source_ids.add(source_id)
        seen_source_hashes.add(source_hash)
        seen_source_orbits.add(source_orbit)
        seen_treatment_hashes.add(treatment_hash)
        seen_treatment_orbits.add(treatment_orbit)
        strata[_stratum_identity(pair["stratum"])].append(pair_id)
        fingerprints.append(
            {
                "pair_index": expected_index,
                "pair_id": pair_id,
                "pair_fingerprint": expected_fingerprint,
            }
        )
    expected_selection = _domain_hash(
        _SELECTION_PREFIX, fingerprints, "selection fingerprint"
    )
    if manifest.get("selection_fingerprint") != expected_selection:
        raise ValueError("paired manifest selection fingerprint mismatch")
    if len(strata) != STALEMATE_STRATUM_COUNT or any(
        len(pair_ids) != STALEMATE_QUOTA_PER_STRATUM
        for pair_ids in strata.values()
    ):
        raise ValueError(
            "paired manifest must contain {} strata with {} pairs each".format(
                STALEMATE_STRATUM_COUNT, STALEMATE_QUOTA_PER_STRATUM
            )
        )
    expected_census = {
        "source_case_count": STALEMATE_SOURCE_CASE_COUNT,
        "pair_count": STALEMATE_PAIR_COUNT,
        "stratum_count": STALEMATE_STRATUM_COUNT,
        "quota_per_stratum": STALEMATE_QUOTA_PER_STRATUM,
    }
    if not _same_json_value(manifest.get("census"), expected_census):
        raise ValueError("paired manifest census mismatch")
    expected_strata = [
        {
            "stratum": json.loads(identity),
            "pair_ids": list(pair_ids),
            "pair_count": len(pair_ids),
        }
        for identity, pair_ids in sorted(strata.items())
    ]
    if not _same_json_value(manifest.get("strata"), expected_strata):
        raise ValueError("paired manifest stratum index mismatch")
    return tuple(pairs)


def _case_from_pair(pair: Mapping[str, Any], treatment: bool) -> Dict[str, Any]:
    prefix = "treatment" if treatment else "source"
    return {
        "case_id": pair["pair_id"] if treatment else pair["source_case_id"],
        "stratum": _json_copy(pair["stratum"], "pair stratum"),
        "vector_count": pair["vector_count"],
        "definition_hash": pair[prefix + "_definition_hash"],
        "d4_canonical_hash": pair[prefix + "_d4_canonical_hash"],
        "definition": _json_copy(pair[prefix + "_definition"], prefix + " definition"),
    }


def _baseline_evidence(candidate: Mapping[str, Any]) -> Dict[str, Any]:
    exact = candidate.get("exact")
    if not isinstance(exact, Mapping):
        raise ValueError("baseline candidate is missing exact evidence")
    return {
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
        "exact": {
            "status": exact.get("status"),
            "result": exact.get("result"),
            "budget_observation": exact.get("budget_observation"),
        },
    }


def _baseline_candidates_by_case(
    baseline_results: Mapping[str, Any],
) -> Dict[str, Mapping[str, Any]]:
    if not isinstance(baseline_results, Mapping):
        raise TypeError("baseline_results must be an object")
    candidates = baseline_results.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("baseline results need candidates")
    by_case: Dict[str, Mapping[str, Any]] = {}
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            raise ValueError("baseline candidates must be objects")
        case_id = candidate.get("case_id")
        if not isinstance(case_id, str) or case_id in by_case:
            raise ValueError("baseline candidates need unique case IDs")
        by_case[case_id] = candidate
    if len(by_case) != STALEMATE_SOURCE_CASE_COUNT:
        raise ValueError(
            "baseline results must contain exactly {} source candidates".format(
                STALEMATE_SOURCE_CASE_COUNT
            )
        )
    return by_case


def _validate_evaluator_exact_evidence(
    candidate: Mapping[str, Any],
    definition: Any,
    max_exact_states: int,
    label: str,
) -> None:
    exact = candidate.get("exact")
    if not isinstance(exact, Mapping) or set(exact) != {
        "status",
        "result",
        "budget_observation",
        "elapsed_seconds",
    }:
        raise ValueError("{} exact evidence schema mismatch".format(label))
    elapsed = exact["elapsed_seconds"]
    if (
        isinstance(elapsed, bool)
        or not isinstance(elapsed, (int, float))
        or not math.isfinite(elapsed)
        or elapsed < 0
    ):
        raise ValueError("{} exact elapsed time is malformed".format(label))
    status = exact["status"]
    result = exact["result"]
    observation = exact["budget_observation"]
    if status == "CENSORED_STATE_BUDGET":
        if (
            result is not None
            or not isinstance(observation, Mapping)
            or set(observation) != {"searched_states", "max_states"}
        ):
            raise ValueError("{} exact budget evidence is malformed".format(label))
        searched = observation["searched_states"]
        maximum = observation["max_states"]
        if (
            isinstance(searched, bool)
            or isinstance(maximum, bool)
            or not isinstance(searched, int)
            or not isinstance(maximum, int)
            or searched != maximum
            or maximum != max_exact_states
        ):
            raise ValueError("{} exact budget values are malformed".format(label))
        return
    if status != "COMPLETED" or observation is not None:
        raise ValueError("{} exact status is malformed".format(label))
    if not isinstance(result, Mapping) or set(result) != _EXACT_RESULT_KEYS:
        raise ValueError("{} exact result schema mismatch".format(label))
    value = result["value_for_a"]
    forced_result = result["forced_result"]
    expected_forced = {-1: "B_WIN", 0: "DRAW", 1: "A_WIN"}
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or expected_forced.get(value) != forced_result
    ):
        raise ValueError("{} exact value/result mismatch".format(label))
    pv = result["principal_variation"]
    pv_plies = result["principal_variation_plies"]
    searched = result["searched_states"]
    cache_hits = result["cache_hits"]
    if (
        not isinstance(pv, list)
        or isinstance(pv_plies, bool)
        or not isinstance(pv_plies, int)
        or pv_plies < 0
        or len(pv) != pv_plies
        or isinstance(searched, bool)
        or not isinstance(searched, int)
        or searched < 1
        or searched > max_exact_states
        or isinstance(cache_hits, bool)
        or not isinstance(cache_hits, int)
        or cache_hits < 0
        or result["terminal_reason"]
        not in {"GOAL", "PLY_LIMIT", "NO_LEGAL_ACTION"}
    ):
        raise ValueError("{} exact result values are malformed".format(label))
    try:
        terminal = replay_dicts(definition, pv)
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("{} exact principal variation is not legal".format(label)) from error
    expected_winner = {"A_WIN": "A", "B_WIN": "B", "DRAW": None}[
        forced_result
    ]
    actual_winner = (
        terminal.outcome.winner.value
        if terminal.outcome is not None and terminal.outcome.winner is not None
        else None
    )
    if (
        not terminal.terminal
        or terminal.ply != pv_plies
        or terminal.outcome is None
        or terminal.outcome.reason != result["terminal_reason"]
        or actual_winner != expected_winner
    ):
        raise ValueError("{} exact principal variation terminal mismatch".format(label))


def _failure_codes_from_profiles(
    definition: Any,
    profiles: Sequence[Mapping[str, Any]],
    gates: PlayGates,
) -> Sequence[str]:
    failures: Set[str] = set()
    shares = []
    for profile in profiles:
        samples = profile["samples"]
        if profile["draws"] / samples > gates.max_draw_rate:
            failures.add(FailureCode.EXCESSIVE_DRAWS.value)
        if profile["average_plies"] < gates.min_average_plies:
            failures.add(FailureCode.TOO_SHORT.value)
        if (
            profile["average_plies"]
            > definition.max_plies * gates.max_average_plies_fraction
        ):
            failures.add(FailureCode.TOO_LONG.value)
        interval = profile["decisive_a_wilson_95"]
        if interval is not None:
            if interval[0] > 0.5 + gates.dominance_interval_margin:
                failures.add(FailureCode.A_DOMINANT.value)
            if interval[1] < 0.5 - gates.dominance_interval_margin:
                failures.add(FailureCode.B_DOMINANT.value)
        if profile["decisive_a_share"] is not None:
            shares.append(profile["decisive_a_share"])
    if shares and max(shares) - min(shares) >= gates.disagreement_threshold:
        failures.add(FailureCode.AGENT_DISAGREEMENT.value)
    return sorted(failures)


def _wilson_interval(successes: int, samples: int) -> Sequence[float]:
    z = 1.959963984540054
    proportion = successes / samples
    denominator = 1.0 + z * z / samples
    center = (proportion + z * z / (2.0 * samples)) / denominator
    margin = z * math.sqrt(
        proportion * (1.0 - proportion) / samples
        + z * z / (4.0 * samples * samples)
    ) / denominator
    return [max(0.0, center - margin), min(1.0, center + margin)]


def _validate_terminal_reason_outcome_consistency(
    definition: Any,
    a_wins: int,
    b_wins: int,
    draws: int,
    terminal_reasons: Mapping[str, int],
    label: str,
) -> None:
    """Tie terminal-reason totals to the schema's winner semantics."""

    decisive = a_wins + b_wins
    goals = terminal_reasons.get("GOAL", 0)
    ply_limits = terminal_reasons.get("PLY_LIMIT", 0)
    no_actions = terminal_reasons.get("NO_LEGAL_ACTION", 0)
    if definition.terminal_policy is None:
        expected_decisive = goals + no_actions
        expected_draws = ply_limits
    else:
        expected_decisive = goals
        expected_draws = ply_limits + no_actions
    if decisive != expected_decisive or draws != expected_draws:
        raise ValueError(
            "{} terminal reasons contradict outcome counts".format(label)
        )


def _validate_sampled_natural_exhaustion(
    definition: Any,
    average_plies: float,
    terminal_reasons: Mapping[str, int],
    label: str,
) -> None:
    bound = stalemate_natural_exhaustion_bound(definition.to_dict())
    if terminal_reasons.get("PLY_LIMIT", 0) != 0 or average_plies > bound:
        raise ValueError(
            "{} sampled play contradicts the natural exhaustion bound".format(
                label
            )
        )


def _validate_profile_mappings(
    candidate: Mapping[str, Any],
    definition: Any,
    play_seeds: Sequence[int],
    gates: PlayGates,
    require_profiles: bool,
    label: str,
) -> None:
    profiles = candidate.get("cheap_profiles")
    failures = candidate.get("cheap_failure_codes")
    if not isinstance(profiles, list) or not isinstance(failures, list):
        raise ValueError("{} cheap evidence is malformed".format(label))
    if not profiles:
        if require_profiles or failures:
            raise ValueError("{} is missing required cheap profiles".format(label))
        return
    if len(profiles) != len(_CHEAP_PROFILE_IDENTITIES):
        raise ValueError("{} cheap profile count mismatch".format(label))
    seed_list = list(play_seeds)
    for profile, (expected_label, expected_agent) in zip(
        profiles, _CHEAP_PROFILE_IDENTITIES
    ):
        if not isinstance(profile, Mapping) or set(profile) != _PROFILE_KEYS:
            raise ValueError("{} cheap profile schema mismatch".format(label))
        if (
            profile["profile"] != expected_label
            or profile["agent_a"] != expected_agent
            or profile["agent_b"] != expected_agent
            or profile["seeds"] != seed_list
            or profile["samples"] != len(seed_list)
        ):
            raise ValueError("{} cheap profile identity mismatch".format(label))
        counts = (profile["a_wins"], profile["b_wins"], profile["draws"])
        if any(
            isinstance(count, bool) or not isinstance(count, int) or count < 0
            for count in counts
        ) or sum(counts) != len(seed_list):
            raise ValueError("{} cheap profile counts are malformed".format(label))
        a_wins, b_wins, draws = counts
        decisive = a_wins + b_wins
        expected_share = a_wins / decisive if decisive else None
        expected_rates = (a_wins / len(seed_list), b_wins / len(seed_list), draws / len(seed_list))
        if (
            profile["a_win_rate"] != expected_rates[0]
            or profile["b_win_rate"] != expected_rates[1]
            or profile["draw_rate"] != expected_rates[2]
            or profile["decisive_a_share"] != expected_share
            or isinstance(profile["average_plies"], bool)
            or not isinstance(profile["average_plies"], (int, float))
            or not math.isfinite(profile["average_plies"])
            or not 0 <= profile["average_plies"] <= definition.max_plies
        ):
            raise ValueError("{} cheap profile rates are malformed".format(label))
        interval = profile["decisive_a_wilson_95"]
        if decisive == 0:
            if interval is not None:
                raise ValueError("{} cheap decisive interval is malformed".format(label))
        elif interval != _wilson_interval(a_wins, decisive):
            raise ValueError("{} cheap decisive interval is malformed".format(label))
        terminal_reasons = profile["terminal_reasons"]
        if (
            not isinstance(terminal_reasons, Mapping)
            or not all(
                isinstance(reason, str)
                and reason in {"GOAL", "PLY_LIMIT", "NO_LEGAL_ACTION"}
                and isinstance(count, int)
                and not isinstance(count, bool)
                and count >= 0
                for reason, count in terminal_reasons.items()
            )
            or sum(terminal_reasons.values()) != len(seed_list)
        ):
            raise ValueError("{} cheap terminal reasons are malformed".format(label))
        _validate_terminal_reason_outcome_consistency(
            definition,
            a_wins,
            b_wins,
            draws,
            terminal_reasons,
            label,
        )
        _validate_sampled_natural_exhaustion(
            definition,
            profile["average_plies"],
            terminal_reasons,
            label,
        )
    expected_failures = _failure_codes_from_profiles(definition, profiles, gates)
    if failures != expected_failures:
        raise ValueError("{} cheap failure evidence mismatch".format(label))


def _validate_candidate_reports(
    candidate: Mapping[str, Any],
    expected: Mapping[str, Any],
    play_seeds: Sequence[int],
    max_exact_states: int,
    gates: PlayGates,
    label: str,
) -> None:
    candidate_timing = candidate.get("timing")
    if (
        not isinstance(candidate_timing, Mapping)
        or set(candidate_timing)
        != {
            "static_asymmetry_simplicity_seconds",
            "cheap_play_seconds",
        }
        or any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
            for value in candidate_timing.values()
        )
    ):
        raise ValueError("{} candidate timing is malformed".format(label))
    definition = parse_definition(expected["definition"])
    static = analyze_definition(definition).to_dict()
    asymmetry = evaluate_asymmetry(definition).to_dict()
    simplicity_report = evaluate_simplicity(definition)
    simplicity = simplicity_report.to_dict()
    simplicity_passes = not exceeds_limits(simplicity_report)
    gate_passes = static["passes"] and asymmetry["qualifies"] and simplicity_passes
    if (
        candidate.get("static") != static
        or candidate.get("asymmetry") != asymmetry
        or candidate.get("simplicity") != simplicity
        or candidate.get("simplicity_passes") is not simplicity_passes
        or candidate.get("analysis_gate_passes") is not gate_passes
    ):
        raise ValueError("{} deterministic report mismatch".format(label))
    _validate_evaluator_exact_evidence(
        candidate, definition, max_exact_states, label
    )
    _validate_profile_mappings(
        candidate,
        definition,
        play_seeds,
        gates,
        require_profiles=gate_passes,
        label=label,
    )


def _validated_case_evaluation_candidates(
    evaluation: Mapping[str, Any],
    expected_cases: Sequence[Mapping[str, Any]],
    play_seeds: Sequence[int],
    max_exact_states: int,
    gates: PlayGates,
    label: str,
) -> Sequence[Mapping[str, Any]]:
    if not isinstance(evaluation, Mapping):
        raise ValueError("{} evaluator result must be an object".format(label))
    expected_configuration = {
        "play_seeds": list(play_seeds),
        "play_gates": asdict(gates),
        "max_exact_states": max_exact_states,
        "exact_routing": "all manifest cases independent of other gates",
        "cheap_routing": "static, asymmetry, and simplicity pass only",
    }
    if not _same_json_value(evaluation.get("configuration"), expected_configuration):
        raise ValueError("{} evaluator configuration mismatch".format(label))
    timing = evaluation.get("timing")
    timing_keys = {
        "static_asymmetry_simplicity_seconds",
        "cheap_play_seconds",
        "exact_seconds",
        "total_seconds",
    }
    if (
        not isinstance(timing, Mapping)
        or set(timing) != timing_keys
        or any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
            for value in timing.values()
        )
        or timing["total_seconds"]
        < max(
            timing["static_asymmetry_simplicity_seconds"],
            timing["cheap_play_seconds"],
            timing["exact_seconds"],
        )
    ):
        raise ValueError("{} evaluator timing evidence is malformed".format(label))
    candidates = evaluation.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != len(expected_cases):
        raise ValueError(
            "{} evaluator candidate count must equal the paired corpus".format(label)
        )
    aggregate = evaluation.get("aggregate")
    if (
        not isinstance(aggregate, Mapping)
        or isinstance(aggregate.get("manifest_case_count"), bool)
        or not isinstance(aggregate.get("manifest_case_count"), int)
        or aggregate.get("manifest_case_count") != len(expected_cases)
    ):
        raise ValueError("{} evaluator aggregate denominator mismatch".format(label))
    for index, (candidate, expected) in enumerate(zip(candidates, expected_cases)):
        if not isinstance(candidate, Mapping):
            raise ValueError("{} evaluator candidates must be objects".format(label))
        if (
            isinstance(candidate.get("manifest_index"), bool)
            or not isinstance(candidate.get("manifest_index"), int)
            or isinstance(candidate.get("vector_count"), bool)
            or not isinstance(candidate.get("vector_count"), int)
        ):
            raise ValueError("{} evaluator integer identity is malformed".format(label))
        expected_identity = {
            "manifest_index": index,
            "case_id": expected["case_id"],
            "definition_hash": expected["definition_hash"],
            "d4_canonical_hash": expected["d4_canonical_hash"],
            "stratum": expected["stratum"],
            "vector_count": expected["vector_count"],
            "definition": expected["definition"],
        }
        observed_identity = {
            key: candidate.get(key) for key in expected_identity
        }
        if not _same_json_value(observed_identity, expected_identity):
            raise ValueError(
                "{} evaluator candidate identity/order mismatch at index {}".format(
                    label, index
                )
            )
        _validate_candidate_reports(
            candidate,
            expected,
            play_seeds,
            max_exact_states,
            gates,
            "{} index {}".format(label, index),
        )
    return candidates


def _complete_static_valid_cheap_evidence(
    treatment: Dict[str, Any],
    play_seeds: Sequence[int],
    gates: PlayGates,
    clock: Callable[[], float],
) -> None:
    """Extend the reusable landscape evaluator to this plan's static-only lane."""

    random_agent = RandomAgent()
    directed_agent = GoalDirectedAgent()
    extra_seconds = 0.0
    for candidate in treatment["candidates"]:
        static_passes = _static_passes(candidate)
        profiles = candidate.get("cheap_profiles")
        if not isinstance(profiles, list):
            raise ValueError("treatment cheap profile evidence is malformed")
        if not static_passes:
            if profiles:
                raise ValueError("static-rejected treatment received cheap play")
            continue
        if profiles:
            continue
        definition = parse_definition(candidate["definition"])
        started = clock()
        evaluated = (
            evaluate_matchup(
                definition,
                "weak-random",
                {Player.A: random_agent, Player.B: random_agent},
                play_seeds,
            ),
            evaluate_matchup(
                definition,
                "medium-goal-directed",
                {Player.A: directed_agent, Player.B: directed_agent},
                play_seeds,
            ),
        )
        elapsed = clock() - started
        extra_seconds += elapsed
        candidate["cheap_profiles"] = [
            profile.to_dict(include_records=False) for profile in evaluated
        ]
        candidate["cheap_failure_codes"] = sorted(
            code.value
            for code in classify_play_failures(definition, evaluated, gates)
        )
        candidate["timing"]["cheap_play_seconds"] = elapsed

    cheap_failures: Counter[str] = Counter()
    direction_confusion: Dict[str, Counter[str]] = defaultdict(Counter)
    cheap_count = 0
    for candidate in treatment["candidates"]:
        definition = parse_definition(candidate["definition"])
        _validate_profile_mappings(
            candidate,
            definition,
            play_seeds,
            gates,
            require_profiles=_static_passes(candidate),
            label="treatment static-valid cheap evidence",
        )
        profiles = candidate["cheap_profiles"]
        if profiles:
            cheap_count += 1
            cheap_failures.update(candidate["cheap_failure_codes"])
        status, result = _exact_status(candidate)
        if status != "COMPLETED" or result is None:
            continue
        for profile in profiles:
            direction_confusion[profile["profile"]][
                "{}->{}".format(
                    sampled_direction(profile), result["forced_result"]
                )
            ] += 1
    aggregate = treatment["aggregate"]
    aggregate["cheap_attempted"] = cheap_count
    aggregate["cheap_evaluated"] = cheap_count
    aggregate["cheap_failure_histogram"] = dict(sorted(cheap_failures.items()))
    aggregate["cheap_exact_direction_confusion"] = {
        profile: dict(sorted(counter.items()))
        for profile, counter in sorted(direction_confusion.items())
    }
    timing = treatment["timing"]
    timing["cheap_play_seconds"] += extra_seconds
    timing["total_seconds"] += extra_seconds
    treatment["configuration"]["cheap_routing"] = "static passes only"


def _validate_baseline_configuration(
    baseline_results: Mapping[str, Any],
    play_seeds: Sequence[int],
    max_exact_states: int,
    gates: PlayGates,
) -> None:
    configuration = baseline_results.get("configuration")
    if not isinstance(configuration, Mapping):
        raise ValueError("baseline results need configuration")
    expected = {
        "play_seeds": list(play_seeds),
        "play_gates": asdict(gates),
        "max_exact_states": max_exact_states,
        "exact_routing": "all manifest cases independent of other gates",
        "cheap_routing": "static, asymmetry, and simplicity pass only",
    }
    if dict(configuration) != expected:
        raise ValueError("baseline evaluation configuration mismatch")


def _exact_status(candidate: Mapping[str, Any]) -> Tuple[str, Optional[Mapping[str, Any]]]:
    exact = candidate.get("exact")
    if not isinstance(exact, Mapping):
        raise ValueError("candidate is missing exact evidence")
    status = exact.get("status")
    result = exact.get("result")
    observation = exact.get("budget_observation")
    if status == "COMPLETED":
        if (
            not isinstance(result, Mapping)
            or result.get("forced_result") not in _FORCED_RESULTS
            or not isinstance(result.get("principal_variation_plies"), int)
            or not isinstance(result.get("terminal_reason"), str)
            or observation is not None
        ):
            raise ValueError("completed exact evidence is malformed")
        return status, result
    if status == "CENSORED_STATE_BUDGET":
        if result is not None or not isinstance(observation, Mapping):
            raise ValueError("censored exact evidence is malformed")
        return status, None
    raise ValueError("candidate exact status is unknown")


def _natural_exhaustion_bound(candidate: Mapping[str, Any]) -> int:
    stratum = candidate.get("stratum")
    if not isinstance(stratum, Mapping):
        raise ValueError("candidate is missing stratum")
    first = stratum.get("first_player")
    definition_mapping = candidate.get("definition")
    if not isinstance(definition_mapping, Mapping):
        raise ValueError("candidate is missing its definition")
    bound = stalemate_natural_exhaustion_bound(definition_mapping)
    expected = 15 if first == "A" else 16 if first == "B" else None
    if expected is None or bound != expected:
        raise ValueError("stalemate stratum disagrees with the exhaustion proof")
    return bound


def _static_passes(candidate: Mapping[str, Any]) -> bool:
    static = candidate.get("static")
    if not isinstance(static, Mapping) or not isinstance(static.get("passes"), bool):
        raise ValueError("candidate static evidence is malformed")
    return static["passes"]


def _completed_baseline_result(candidate: Mapping[str, Any]) -> Mapping[str, Any]:
    baseline = candidate.get("baseline_exact")
    if not isinstance(baseline, Mapping) or baseline.get("status") != "COMPLETED":
        raise ValueError("paired candidate is missing completed baseline exact evidence")
    result = baseline.get("result")
    if (
        not isinstance(result, Mapping)
        or result.get("forced_result") not in _FORCED_RESULTS
        or not isinstance(result.get("principal_variation_plies"), int)
        or not isinstance(result.get("terminal_reason"), str)
        or baseline.get("budget_observation") is not None
    ):
        raise ValueError("paired candidate baseline result is malformed")
    return result


def _shape_clean_stalemate(candidate: Mapping[str, Any]) -> bool:
    status, result = _exact_status(candidate)
    failures = candidate.get("cheap_failure_codes")
    gate_passes = candidate.get("analysis_gate_passes")
    profiles = candidate.get("cheap_profiles")
    if not isinstance(failures, list) or not all(isinstance(code, str) for code in failures):
        raise ValueError("candidate cheap failure evidence is malformed")
    if not isinstance(gate_passes, bool):
        raise ValueError("candidate gate evidence is malformed")
    static_passes = _static_passes(candidate)
    if not static_passes:
        if profiles != [] or failures != []:
            raise ValueError("static-rejected candidate received cheap evidence")
        return False
    if (
        not isinstance(profiles, list)
        or len(profiles) != len(_CHEAP_PROFILE_IDENTITIES)
        or [profile.get("profile") for profile in profiles if isinstance(profile, Mapping)]
        != [identity[0] for identity in _CHEAP_PROFILE_IDENTITIES]
    ):
        raise ValueError("candidate is missing the two frozen cheap profiles")
    return bool(
        status == "COMPLETED"
        and result is not None
        and result["forced_result"] == "DRAW"
        and result["terminal_reason"] == "NO_LEGAL_ACTION"
        and result["principal_variation_plies"] > 0
        and gate_passes
        and not set(failures).intersection(_SHAPE_FAILURES)
    )


def _dimension_records(candidates: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    dimensions = (
        "first_player",
        "goal_axis_relation",
        "runner_start_class",
        "max_plies",
        "vector_count_band",
        "vector_count",
    )
    grouped: Dict[str, DefaultDict[Any, Dict[str, Counter[str]]]] = {
        dimension: defaultdict(
            lambda: {
                "outcome": Counter(),
                "terminal_reason": Counter(),
                "transition": Counter(),
            }
        )
        for dimension in dimensions
    }
    for candidate in candidates:
        status, result = _exact_status(candidate)
        baseline_result = _completed_baseline_result(candidate)
        treatment_outcome = result["forced_result"] if result is not None else "CENSORED"
        transition = "{}->{}".format(
            baseline_result.get("forced_result"), treatment_outcome
        )
        stratum = candidate["stratum"]
        values = {**stratum, "vector_count": candidate["vector_count"]}
        for dimension in dimensions:
            bucket = grouped[dimension][values[dimension]]
            bucket["outcome"][treatment_outcome] += 1
            bucket["transition"][transition] += 1
            if result is not None:
                bucket["terminal_reason"][result["terminal_reason"]] += 1
    output = {}
    for dimension in dimensions:
        records = []
        for value, counters in sorted(grouped[dimension].items()):
            records.append(
                {
                    "value": value,
                    "case_count": sum(counters["outcome"].values()),
                    "treatment_result_histogram": dict(sorted(counters["outcome"].items())),
                    "treatment_terminal_reason_histogram": dict(
                        sorted(counters["terminal_reason"].items())
                    ),
                    "baseline_to_treatment_transition_histogram": dict(
                        sorted(counters["transition"].items())
                    ),
                }
            )
        output[dimension] = records
    return output


def _natural_play_aggregate(candidates: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    by_profile: DefaultDict[str, Dict[str, Any]] = defaultdict(
        lambda: {
            "profile_count": 0,
            "game_count": 0,
            "total_plies": 0.0,
            "natural_bound_game_weight": 0,
            "candidate_average_fraction_sum": 0.0,
            "candidate_average_fraction_max": 0.0,
            "candidate_average_at_or_above_85pct_count": 0,
        }
    )
    for candidate in candidates:
        bound = candidate["natural_exhaustion_bound"]
        for profile in candidate.get("cheap_profiles", []):
            label = profile.get("profile")
            samples = profile.get("samples")
            average = profile.get("average_plies")
            if (
                not isinstance(label, str)
                or not isinstance(samples, int)
                or samples < 1
                or not isinstance(average, (int, float))
            ):
                raise ValueError("cheap profile is malformed")
            fraction = average / bound
            bucket = by_profile[label]
            bucket["profile_count"] += 1
            bucket["game_count"] += samples
            bucket["total_plies"] += average * samples
            bucket["natural_bound_game_weight"] += bound * samples
            bucket["candidate_average_fraction_sum"] += fraction
            bucket["candidate_average_fraction_max"] = max(
                bucket["candidate_average_fraction_max"], fraction
            )
            if fraction >= 0.85:
                bucket["candidate_average_at_or_above_85pct_count"] += 1
    result = {}
    for label, bucket in sorted(by_profile.items()):
        count = bucket["profile_count"]
        result[label] = {
            "profile_count": count,
            "game_count": bucket["game_count"],
            "average_plies": bucket["total_plies"] / bucket["game_count"],
            "weighted_natural_bound_fraction": (
                bucket["total_plies"] / bucket["natural_bound_game_weight"]
            ),
            "mean_candidate_average_natural_bound_fraction": (
                bucket["candidate_average_fraction_sum"] / count
            ),
            "max_candidate_average_natural_bound_fraction": bucket[
                "candidate_average_fraction_max"
            ],
            "candidate_average_at_or_above_85pct_count": bucket[
                "candidate_average_at_or_above_85pct_count"
            ],
        }
    return result


def _aggregate_treatment_candidate_evidence(
    candidates: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    static_failures: Counter[str] = Counter()
    cheap_failures: Counter[str] = Counter()
    direction_confusion: Dict[str, Counter[str]] = defaultdict(Counter)
    exact_work = []
    exact_completed = 0
    for candidate in candidates:
        static_failures.update(
            diagnostic["code"] for diagnostic in candidate["static"]["diagnostics"]
        )
        cheap_failures.update(candidate["cheap_failure_codes"])
        status, result = _exact_status(candidate)
        exact = candidate["exact"]
        if status == "COMPLETED":
            assert result is not None
            exact_completed += 1
            exact_work.append(result["searched_states"])
            for profile in candidate["cheap_profiles"]:
                direction_confusion[profile["profile"]][
                    "{}->{}".format(
                        sampled_direction(profile), result["forced_result"]
                    )
                ] += 1
        else:
            exact_work.append(exact["budget_observation"]["searched_states"])
    return {
        "static_pass_count": sum(
            candidate["static"]["passes"] for candidate in candidates
        ),
        "asymmetry_qualifies_count": sum(
            candidate["asymmetry"]["qualifies"] for candidate in candidates
        ),
        "simplicity_pass_count": sum(
            candidate["simplicity_passes"] for candidate in candidates
        ),
        "analysis_gate_pass_count": sum(
            candidate["analysis_gate_passes"] for candidate in candidates
        ),
        "cheap_attempted": sum(
            bool(candidate["cheap_profiles"]) for candidate in candidates
        ),
        "cheap_evaluated": sum(
            bool(candidate["cheap_profiles"]) for candidate in candidates
        ),
        "static_failure_histogram": dict(sorted(static_failures.items())),
        "cheap_failure_histogram": dict(sorted(cheap_failures.items())),
        "cheap_exact_direction_confusion": {
            profile: dict(sorted(counter.items()))
            for profile, counter in sorted(direction_confusion.items())
        },
        "exact_attempted": len(candidates),
        "exact_completed": exact_completed,
        "exact_completion_rate": exact_completed / len(candidates),
        "exact_work_states_total": sum(exact_work),
        "exact_work_states_max": max(exact_work, default=0),
    }


def _landscape_dimension_aggregates(
    candidates: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    dimensions = (
        "first_player",
        "goal_axis_relation",
        "runner_start_class",
        "max_plies",
        "vector_count_band",
        "vector_count",
    )
    grouped: Dict[str, DefaultDict[Any, Counter[str]]] = {
        dimension: defaultdict(Counter) for dimension in dimensions
    }
    for candidate in candidates:
        status, result = _exact_status(candidate)
        outcome = result["forced_result"] if status == "COMPLETED" else "CENSORED"
        values = {**candidate["stratum"], "vector_count": candidate["vector_count"]}
        for dimension in dimensions:
            grouped[dimension][values[dimension]][outcome] += 1
    output = {}
    for dimension in dimensions:
        records = []
        for value, counter in sorted(grouped[dimension].items()):
            histogram = {
                result: counter.get(result, 0)
                for result in (*_FORCED_RESULTS, "CENSORED")
            }
            records.append(
                {
                    "value": value,
                    "case_count": sum(histogram.values()),
                    "exact_result_histogram": histogram,
                }
            )
        output[dimension] = records
    return output


def _expected_landscape_aggregate(
    candidates: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    common = _aggregate_treatment_candidate_evidence(candidates)
    exact_histogram: Counter[str] = Counter()
    draw_reasons: Counter[str] = Counter()
    censored_hashes = []
    analysis_draws = 0
    shape_clean_draws = 0
    for candidate in candidates:
        status, result = _exact_status(candidate)
        if status != "COMPLETED":
            censored_hashes.append(candidate["definition_hash"])
            continue
        assert result is not None
        exact_histogram[result["forced_result"]] += 1
        if result["forced_result"] == "DRAW":
            draw_reasons[result["terminal_reason"]] += 1
            if candidate["analysis_gate_passes"]:
                analysis_draws += 1
                if not set(candidate["cheap_failure_codes"]).intersection(
                    _SHAPE_FAILURES
                ):
                    shape_clean_draws += 1
    exact_completed = common["exact_completed"]
    exact_censored = len(candidates) - exact_completed
    return {
        "manifest_case_count": len(candidates),
        "static_pass_count": common["static_pass_count"],
        "asymmetry_qualifies_count": common["asymmetry_qualifies_count"],
        "simplicity_pass_count": common["simplicity_pass_count"],
        "analysis_gate_pass_count": common["analysis_gate_pass_count"],
        "cheap_attempted": common["cheap_attempted"],
        "cheap_evaluated": common["cheap_evaluated"],
        "exact_attempted": len(candidates),
        "exact_completed": exact_completed,
        "exact_censored": exact_censored,
        "exact_censored_hashes": sorted(censored_hashes),
        "exact_completion_rate": exact_completed / len(candidates),
        "exact_result_histogram": {
            result: exact_histogram.get(result, 0) for result in _FORCED_RESULTS
        },
        "exact_draw_terminal_reason_histogram": dict(sorted(draw_reasons.items())),
        "static_failure_histogram": common["static_failure_histogram"],
        "cheap_failure_histogram": common["cheap_failure_histogram"],
        "cheap_exact_direction_confusion": common["cheap_exact_direction_confusion"],
        "exact_work_states_total": common["exact_work_states_total"],
        "exact_work_states_max": common["exact_work_states_max"],
        "analysis_eligible_exact_draw_count": analysis_draws,
        "shape_clean_exact_draw_count": shape_clean_draws,
        "exact_by_dimension": _landscape_dimension_aggregates(candidates),
        "predeclared_assessment": {
            "exact_completion": {
                "status": "SUPPORTED" if exact_censored == 0 else "INCONCLUSIVE",
                "reasons": (
                    [] if exact_censored == 0 else ["EXACT_STATE_BUDGET_CENSORING"]
                ),
            }
        },
    }


def _semantic_counts(candidates: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    exact_censored = 0
    exact_censored_hashes = []
    ply_limit_hashes = []
    initial_draw_hashes = []
    post_action_draw_hashes = []
    static_valid_post_action_hashes = []
    shape_clean_hashes = []
    semantic_strata = set()
    treatment_histogram: Counter[str] = Counter()
    terminal_histogram: Counter[str] = Counter()
    transition_histogram: Counter[str] = Counter()
    terminal_transition_histogram: Counter[str] = Counter()
    pv_delta_histogram: Counter[int] = Counter()
    pv_increased = 0
    pv_unchanged = 0
    pv_decreased = 0
    for candidate in candidates:
        status, result = _exact_status(candidate)
        baseline_result = _completed_baseline_result(candidate)
        computed_shape_clean = _shape_clean_stalemate(candidate)
        if candidate.get("shape_clean_stalemate_draw") is not computed_shape_clean:
            raise ValueError("stored shape-clean evidence does not match raw evidence")
        if status != "COMPLETED":
            exact_censored += 1
            exact_censored_hashes.append(candidate["definition_hash"])
            transition_histogram[
                "{}->CENSORED".format(baseline_result["forced_result"])
            ] += 1
            terminal_transition_histogram[
                "{}->CENSORED".format(baseline_result["terminal_reason"])
            ] += 1
            continue
        assert result is not None
        outcome = result["forced_result"]
        reason = result["terminal_reason"]
        treatment_histogram[outcome] += 1
        terminal_histogram[reason] += 1
        transition_histogram[
            "{}->{}".format(baseline_result["forced_result"], outcome)
        ] += 1
        terminal_transition_histogram[
            "{}->{}".format(baseline_result["terminal_reason"], reason)
        ] += 1
        pv_delta = (
            result["principal_variation_plies"]
            - baseline_result["principal_variation_plies"]
        )
        pv_delta_histogram[pv_delta] += 1
        if pv_delta > 0:
            pv_increased += 1
        elif pv_delta < 0:
            pv_decreased += 1
        else:
            pv_unchanged += 1
        if reason == "PLY_LIMIT":
            ply_limit_hashes.append(candidate["definition_hash"])
        if outcome == "DRAW" and reason == "NO_LEGAL_ACTION":
            if result["principal_variation_plies"] == 0:
                initial_draw_hashes.append(candidate["definition_hash"])
            else:
                post_action_draw_hashes.append(candidate["definition_hash"])
                if _static_passes(candidate):
                    static_valid_post_action_hashes.append(candidate["definition_hash"])
                    semantic_strata.add(_stratum_identity(candidate["stratum"]))
        if computed_shape_clean:
            shape_clean_hashes.append(candidate["definition_hash"])
    return {
        "exact_censored_count": exact_censored,
        "exact_censored_hashes": sorted(exact_censored_hashes),
        "ply_limit_result_count": len(ply_limit_hashes),
        "ply_limit_result_hashes": sorted(ply_limit_hashes),
        "initial_immobility_draw_count": len(initial_draw_hashes),
        "initial_immobility_draw_hashes": sorted(initial_draw_hashes),
        "post_action_stalemate_draw_count": len(post_action_draw_hashes),
        "post_action_stalemate_draw_hashes": sorted(post_action_draw_hashes),
        "static_valid_post_action_stalemate_draw_count": len(
            static_valid_post_action_hashes
        ),
        "static_valid_post_action_stalemate_draw_hashes": sorted(
            static_valid_post_action_hashes
        ),
        "static_valid_post_action_stalemate_draw_stratum_count": len(
            semantic_strata
        ),
        "shape_clean_stalemate_draw_count": len(shape_clean_hashes),
        "shape_clean_stalemate_draw_hashes": sorted(shape_clean_hashes),
        "treatment_result_histogram": dict(sorted(treatment_histogram.items())),
        "treatment_terminal_reason_histogram": dict(sorted(terminal_histogram.items())),
        "baseline_to_treatment_transition_histogram": dict(
            sorted(transition_histogram.items())
        ),
        "baseline_to_treatment_terminal_reason_transition_histogram": dict(
            sorted(terminal_transition_histogram.items())
        ),
        "principal_variation_plies_delta_histogram": {
            str(delta): count for delta, count in sorted(pv_delta_histogram.items())
        },
        "principal_variation_plies_increased_count": pv_increased,
        "principal_variation_plies_unchanged_count": pv_unchanged,
        "principal_variation_plies_decreased_count": pv_decreased,
    }


def _raw_assessments(counts: Mapping[str, Any], pair_count: int) -> Dict[str, Any]:
    ply_limit = counts["ply_limit_result_count"]
    censored = counts["exact_censored_count"]
    semantic_count = counts["static_valid_post_action_stalemate_draw_count"]
    semantic_strata = counts[
        "static_valid_post_action_stalemate_draw_stratum_count"
    ]
    exact_completion = {
        "status": "SUPPORTED" if censored == 0 else "INCONCLUSIVE",
        "reasons": [] if censored == 0 else ["EXACT_STATE_BUDGET_CENSORING"],
    }
    if ply_limit:
        non_horizon = {
            "status": "NOT_SUPPORTED",
            "reasons": ["TREATMENT_PLY_LIMIT_RESULT"],
        }
        semantic = {
            "status": "NOT_EVALUATED",
            "reasons": ["NON_HORIZON_PROOF_FAILURE"],
        }
        overall = {
            "status": "NOT_SUPPORTED",
            "reasons": ["TREATMENT_PLY_LIMIT_RESULT"],
        }
    elif censored:
        non_horizon = {
            "status": "INCONCLUSIVE",
            "reasons": ["EXACT_STATE_BUDGET_CENSORING"],
        }
        semantic = {
            "status": "INCONCLUSIVE",
            "reasons": ["EXACT_STATE_BUDGET_CENSORING"],
        }
        overall = {
            "status": "INCONCLUSIVE",
            "reasons": ["EXACT_STATE_BUDGET_CENSORING"],
        }
    else:
        non_horizon = {"status": "SUPPORTED", "reasons": []}
        if semantic_count >= 4 and semantic_strata >= 2:
            semantic_status = "SUPPORTED"
            semantic_reasons = []
        elif semantic_count == 0:
            semantic_status = "NOT_SUPPORTED"
            semantic_reasons = ["NO_STATIC_VALID_POST_ACTION_STALEMATE_DRAW"]
        else:
            semantic_status = "INCONCLUSIVE"
            semantic_reasons = ["FEWER_THAN_4_DRAWS_OR_2_STRATA"]
        semantic = {"status": semantic_status, "reasons": semantic_reasons}
        overall = {
            "status": "INCONCLUSIVE",
            "reasons": ["DRAW_STRESS_NOT_RUN"],
        }
    return {
        "exact_completion": exact_completion,
        "clean_non_horizon": non_horizon,
        "semantic_response": semantic,
        "overall_treatment_discovery": overall,
        "exact_completed_count": pair_count - censored,
    }


def _raw_configuration(
    play_seeds: Sequence[int], max_exact_states: int, gates: PlayGates
) -> Dict[str, Any]:
    return {
        "play_seeds": list(play_seeds),
        "play_gates": asdict(gates),
        "max_exact_states": max_exact_states,
        "exact_routing": "all manifest cases independent of other gates",
        "cheap_routing": "static passes only",
        "natural_exhaustion_bound": {"A_FIRST": 15, "B_FIRST": 16},
        "shape_clean": (
            "static/asymmetry/simplicity pass; exact post-action "
            "NO_LEGAL_ACTION draw; no frozen cheap duration/draw failure"
        ),
        "semantic_response_static_validity": "static.passes == true",
        "duration_interpretation": (
            "TOO_LONG remains relative to max_plies=18; natural-bound "
            "fractions are descriptive only and do not affect selection"
        ),
    }


def _expected_raw_aggregate(
    candidates: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    counts = _semantic_counts(candidates)
    return {
        "pair_count": len(candidates),
        "v1_replay_match_count": len(candidates),
        **counts,
        **_aggregate_treatment_candidate_evidence(candidates),
        "by_dimension": _dimension_records(candidates),
        "sampled_play_natural_bound": _natural_play_aggregate(candidates),
        "predeclared_assessment": _raw_assessments(counts, len(candidates)),
    }


def _validate_landscape_timing(value: Any, label: str) -> None:
    keys = {
        "static_asymmetry_simplicity_seconds",
        "cheap_play_seconds",
        "exact_seconds",
        "total_seconds",
    }
    if (
        not isinstance(value, Mapping)
        or set(value) != keys
        or any(
            isinstance(item, bool)
            or not isinstance(item, (int, float))
            or not math.isfinite(item)
            or item < 0
            for item in value.values()
        )
        or value["total_seconds"]
        < max(
            value["static_asymmetry_simplicity_seconds"],
            value["cheap_play_seconds"],
            value["exact_seconds"],
        )
    ):
        raise ValueError("{} timing evidence is malformed".format(label))


def _validate_candidate_timing_totals(
    timing: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    label: str,
) -> None:
    expected = {
        "static_asymmetry_simplicity_seconds": sum(
            candidate["timing"]["static_asymmetry_simplicity_seconds"]
            for candidate in candidates
        ),
        "cheap_play_seconds": sum(
            candidate["timing"]["cheap_play_seconds"] for candidate in candidates
        ),
        "exact_seconds": sum(
            candidate["exact"]["elapsed_seconds"] for candidate in candidates
        ),
    }
    if any(
        not math.isclose(
            timing[key], expected_value, rel_tol=1e-12, abs_tol=1e-9
        )
        for key, expected_value in expected.items()
    ):
        raise ValueError("{} timing totals do not match candidate evidence".format(label))
    phase_total = sum(timing[key] for key in expected)
    tolerance = max(1e-9, 1e-12 * max(1.0, phase_total))
    if timing["total_seconds"] + tolerance < phase_total:
        raise ValueError("{} total timing is below its phase totals".format(label))


def validate_stalemate_baseline_replay(
    replay: Mapping[str, Any],
    paired_manifest: Mapping[str, Any],
    baseline_results: Mapping[str, Any],
    play_seeds: Sequence[int] = LANDSCAPE_PLAY_SEEDS,
    max_exact_states: int = LANDSCAPE_EXACT_MAX_STATES,
    gates: PlayGates = PlayGates(),
) -> Tuple[Mapping[str, Any], ...]:
    """Validate the complete v1 replay boundary before any treatment call."""

    pairs = validate_stalemate_paired_manifest(paired_manifest)
    _validate_baseline_configuration(
        baseline_results, play_seeds, max_exact_states, gates
    )
    expected_by_case = _baseline_candidates_by_case(baseline_results)
    source_cases = tuple(_case_from_pair(pair, treatment=False) for pair in pairs)
    replay_candidates = _validated_case_evaluation_candidates(
        replay,
        source_cases,
        play_seeds,
        max_exact_states,
        gates,
        "v1 replay",
    )
    expected_selected = []
    for pair in pairs:
        expected = expected_by_case.get(pair["source_case_id"])
        if expected is None:
            raise ValueError(
                "frozen baseline is missing {}".format(pair["source_case_id"])
            )
        expected_selected.append(expected)
    if len(expected_selected) != len(pairs):
        raise ValueError("frozen baseline selected-source denominator mismatch")
    for candidate, expected in zip(replay_candidates, expected_selected):
        if not _same_json_value(
            _baseline_evidence(candidate), _baseline_evidence(expected)
        ):
            raise ValueError(
                "v1 baseline replay mismatch for {}".format(candidate["case_id"])
            )
    if not _same_json_value(
        replay.get("aggregate"), _expected_landscape_aggregate(replay_candidates)
    ):
        raise ValueError("v1 baseline replay aggregate mismatch")
    _validate_candidate_timing_totals(
        replay["timing"], replay_candidates, "v1 baseline replay"
    )
    return tuple(replay_candidates)


def validate_stalemate_paired_result(
    result: Mapping[str, Any],
    paired_manifest: Mapping[str, Any],
    baseline_results: Mapping[str, Any],
    play_seeds: Sequence[int] = LANDSCAPE_PLAY_SEEDS,
    max_exact_states: int = LANDSCAPE_EXACT_MAX_STATES,
    gates: PlayGates = PlayGates(),
) -> Tuple[Mapping[str, Any], ...]:
    """Validate a sealed raw result entirely from paired candidate evidence."""

    pairs = validate_stalemate_paired_manifest(paired_manifest)
    _validate_baseline_configuration(
        baseline_results, play_seeds, max_exact_states, gates
    )
    baseline_by_case = _baseline_candidates_by_case(baseline_results)
    if not isinstance(result, Mapping) or set(result) != {
        "configuration",
        "aggregate",
        "timing",
        "candidates",
    }:
        raise ValueError("stalemate raw result schema mismatch")
    if not _same_json_value(
        result.get("configuration"),
        _raw_configuration(play_seeds, max_exact_states, gates),
    ):
        raise ValueError("stalemate raw configuration mismatch")
    timing = result.get("timing")
    if not isinstance(timing, Mapping) or set(timing) != {"v1_replay", "treatment"}:
        raise ValueError("stalemate raw timing schema mismatch")
    _validate_landscape_timing(timing["v1_replay"], "v1 replay")
    _validate_landscape_timing(timing["treatment"], "treatment")
    candidates = result.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != len(pairs):
        raise ValueError("stalemate raw candidate denominator mismatch")

    for index, (pair, candidate) in enumerate(zip(pairs, candidates)):
        if not isinstance(candidate, Mapping) or set(candidate) != _RAW_CANDIDATE_KEYS:
            raise ValueError("stalemate raw candidate schema mismatch at {}".format(index))
        if (
            isinstance(candidate.get("manifest_index"), bool)
            or not isinstance(candidate.get("manifest_index"), int)
            or isinstance(candidate.get("pair_index"), bool)
            or not isinstance(candidate.get("pair_index"), int)
            or isinstance(candidate.get("vector_count"), bool)
            or not isinstance(candidate.get("vector_count"), int)
        ):
            raise ValueError("stalemate raw integer identity is malformed")
        source_case = _case_from_pair(pair, treatment=False)
        treatment_case = _case_from_pair(pair, treatment=True)
        baseline = baseline_by_case.get(pair["source_case_id"])
        if baseline is None:
            raise ValueError("stalemate raw baseline join is incomplete")
        source_identity = {
            key: baseline.get(key)
            for key in (
                "case_id",
                "definition_hash",
                "d4_canonical_hash",
                "stratum",
                "vector_count",
                "definition",
            )
        }
        expected_source_identity = {
            key: source_case[key] for key in source_identity
        }
        if source_identity != expected_source_identity:
            raise ValueError("stalemate raw baseline identity mismatch")
        _validate_candidate_reports(
            baseline,
            source_case,
            play_seeds,
            max_exact_states,
            gates,
            "frozen baseline {}".format(pair["source_case_id"]),
        )
        expected_treatment_identity = {
            "manifest_index": index,
            "case_id": treatment_case["case_id"],
            "definition_hash": treatment_case["definition_hash"],
            "d4_canonical_hash": treatment_case["d4_canonical_hash"],
            "stratum": treatment_case["stratum"],
            "vector_count": treatment_case["vector_count"],
            "definition": treatment_case["definition"],
        }
        if not _same_json_value(
            {
                key: candidate.get(key) for key in expected_treatment_identity
            },
            expected_treatment_identity,
        ):
            raise ValueError("stalemate raw treatment identity mismatch")
        _validate_candidate_reports(
            candidate,
            treatment_case,
            play_seeds,
            max_exact_states,
            gates,
            "treatment {}".format(pair["pair_id"]),
        )
        definition = parse_definition(treatment_case["definition"])
        _validate_profile_mappings(
            candidate,
            definition,
            play_seeds,
            gates,
            require_profiles=_static_passes(candidate),
            label="treatment static-valid {}".format(pair["pair_id"]),
        )
        expected_pair_fields = {
            "pair_index": pair["pair_index"],
            "pair_id": pair["pair_id"],
            "pair_fingerprint": pair["pair_fingerprint"],
            "source_case_id": pair["source_case_id"],
            "source_definition_hash": pair["source_definition_hash"],
            "source_d4_canonical_hash": pair["source_d4_canonical_hash"],
        }
        if not _same_json_value(
            {key: candidate.get(key) for key in expected_pair_fields},
            expected_pair_fields,
        ):
            raise ValueError("stalemate raw pair identity mismatch")
        expected_baseline_exact = {
            "status": baseline["exact"]["status"],
            "result": baseline["exact"]["result"],
            "budget_observation": baseline["exact"]["budget_observation"],
        }
        if candidate.get("baseline_exact") != expected_baseline_exact:
            raise ValueError("stalemate raw baseline exact join mismatch")
        baseline_result = _completed_baseline_result(candidate)
        treatment_status, treatment_exact = _exact_status(candidate)
        if treatment_status == "COMPLETED":
            assert treatment_exact is not None
            expected_transition = "{}->{}".format(
                baseline_result["terminal_reason"],
                treatment_exact["terminal_reason"],
            )
            expected_delta = (
                treatment_exact["principal_variation_plies"]
                - baseline_result["principal_variation_plies"]
            )
        else:
            expected_transition = "{}->CENSORED".format(
                baseline_result["terminal_reason"]
            )
            expected_delta = None
        if (
            candidate.get("baseline_to_treatment_terminal_reason_transition")
            != expected_transition
            or candidate.get("principal_variation_plies_delta") != expected_delta
        ):
            raise ValueError("stalemate raw paired delta mismatch")
        bound = _natural_exhaustion_bound(candidate)
        expected_natural_profiles = [
            {
                "profile": profile["profile"],
                "average_plies": profile["average_plies"],
                "natural_exhaustion_bound": bound,
                "average_plies_fraction_of_natural_bound": (
                    profile["average_plies"] / bound
                ),
            }
            for profile in candidate["cheap_profiles"]
        ]
        if (
            candidate.get("natural_exhaustion_bound") != bound
            or candidate.get("cheap_natural_bound_profiles")
            != expected_natural_profiles
            or candidate.get("shape_clean_stalemate_draw")
            is not _shape_clean_stalemate(candidate)
        ):
            raise ValueError("stalemate raw derived candidate evidence mismatch")

    expected_aggregate = _expected_raw_aggregate(candidates)
    if not _same_json_value(result.get("aggregate"), expected_aggregate):
        raise ValueError("stalemate raw aggregate mismatch")
    _validate_candidate_timing_totals(
        timing["treatment"], candidates, "stalemate treatment"
    )
    return tuple(candidates)


def evaluate_stalemate_pairs(
    paired_manifest: Mapping[str, Any],
    baseline_results: Mapping[str, Any],
    play_seeds: Sequence[int] = LANDSCAPE_PLAY_SEEDS,
    max_exact_states: int = LANDSCAPE_EXACT_MAX_STATES,
    gates: PlayGates = PlayGates(),
    clock: Callable[[], float] = time.perf_counter,
    case_evaluator: Callable[..., Dict[str, Any]] = evaluate_landscape_cases,
) -> Dict[str, Any]:
    """Replay every v1 pair exactly, then evaluate the v2 treatment corpus."""

    pairs = validate_stalemate_paired_manifest(paired_manifest)
    _validate_baseline_configuration(
        baseline_results, play_seeds, max_exact_states, gates
    )
    expected_by_case = _baseline_candidates_by_case(baseline_results)
    source_cases = tuple(_case_from_pair(pair, treatment=False) for pair in pairs)
    replay = case_evaluator(
        source_cases,
        play_seeds=play_seeds,
        max_exact_states=max_exact_states,
        gates=gates,
        clock=clock,
    )
    validate_stalemate_baseline_replay(
        replay,
        paired_manifest,
        baseline_results,
        play_seeds=play_seeds,
        max_exact_states=max_exact_states,
        gates=gates,
    )

    treatment_cases = tuple(_case_from_pair(pair, treatment=True) for pair in pairs)
    treatment = case_evaluator(
        treatment_cases,
        play_seeds=play_seeds,
        max_exact_states=max_exact_states,
        gates=gates,
        clock=clock,
    )
    treatment_candidates = _validated_case_evaluation_candidates(
        treatment,
        treatment_cases,
        play_seeds,
        max_exact_states,
        gates,
        "treatment",
    )
    _complete_static_valid_cheap_evidence(
        treatment,
        play_seeds=play_seeds,
        gates=gates,
        clock=clock,
    )
    expected_by_source = {
        pair["source_case_id"]: expected_by_case[pair["source_case_id"]]
        for pair in pairs
    }
    output_candidates = []
    for pair, candidate in zip(pairs, treatment_candidates):
        baseline_candidate = expected_by_source[pair["source_case_id"]]
        enriched = _json_copy(candidate, "treatment candidate")
        enriched["pair_index"] = pair["pair_index"]
        enriched["pair_id"] = pair["pair_id"]
        enriched["pair_fingerprint"] = pair["pair_fingerprint"]
        enriched["source_case_id"] = pair["source_case_id"]
        enriched["source_definition_hash"] = pair["source_definition_hash"]
        enriched["source_d4_canonical_hash"] = pair["source_d4_canonical_hash"]
        enriched["baseline_exact"] = _json_copy(
            {
                "status": baseline_candidate["exact"]["status"],
                "result": baseline_candidate["exact"]["result"],
                "budget_observation": baseline_candidate["exact"][
                    "budget_observation"
                ],
            },
            "baseline exact evidence",
        )
        baseline_result = _completed_baseline_result(enriched)
        treatment_status, treatment_result = _exact_status(enriched)
        if treatment_status == "COMPLETED":
            assert treatment_result is not None
            enriched["baseline_to_treatment_terminal_reason_transition"] = (
                "{}->{}".format(
                    baseline_result["terminal_reason"],
                    treatment_result["terminal_reason"],
                )
            )
            enriched["principal_variation_plies_delta"] = (
                treatment_result["principal_variation_plies"]
                - baseline_result["principal_variation_plies"]
            )
        else:
            enriched["baseline_to_treatment_terminal_reason_transition"] = (
                "{}->CENSORED".format(baseline_result["terminal_reason"])
            )
            enriched["principal_variation_plies_delta"] = None
        bound = _natural_exhaustion_bound(enriched)
        enriched["natural_exhaustion_bound"] = bound
        enriched["cheap_natural_bound_profiles"] = [
            {
                "profile": profile["profile"],
                "average_plies": profile["average_plies"],
                "natural_exhaustion_bound": bound,
                "average_plies_fraction_of_natural_bound": (
                    profile["average_plies"] / bound
                ),
            }
            for profile in enriched["cheap_profiles"]
        ]
        enriched["shape_clean_stalemate_draw"] = _shape_clean_stalemate(enriched)
        output_candidates.append(enriched)

    result = {
        "configuration": _raw_configuration(play_seeds, max_exact_states, gates),
        "aggregate": _expected_raw_aggregate(output_candidates),
        "timing": {
            "v1_replay": _json_copy(replay["timing"], "v1 replay timing"),
            "treatment": _json_copy(treatment["timing"], "treatment timing"),
        },
        "candidates": output_candidates,
    }
    validate_stalemate_paired_result(
        result,
        paired_manifest,
        baseline_results,
        play_seeds=play_seeds,
        max_exact_states=max_exact_states,
        gates=gates,
    )
    return result


def _stress_selection_score(game_hash: str, shape_clean: bool) -> str:
    prefix = _STRESS_CLEAN_PREFIX if shape_clean else _STRESS_OTHER_PREFIX
    return hashlib.sha256((prefix + game_hash).encode("ascii")).hexdigest()


def select_stalemate_stress_candidates(
    raw_candidates: Sequence[Mapping[str, Any]],
    max_candidates: int = DRAW_STRESS_MAX_CANDIDATES,
) -> Dict[str, Any]:
    if max_candidates < 1:
        raise ValueError("stalemate stress max_candidates must be at least one")
    eligible = []
    seen_hashes: Set[str] = set()
    for candidate in raw_candidates:
        if not isinstance(candidate, Mapping):
            raise ValueError("raw stalemate candidates must be objects")
        game_hash = candidate.get("definition_hash")
        if not isinstance(game_hash, str) or game_hash in seen_hashes:
            raise ValueError("raw stalemate candidates need unique definition hashes")
        seen_hashes.add(game_hash)
        status, result = _exact_status(candidate)
        if status != "COMPLETED" or result is None:
            continue
        if (
            not _static_passes(candidate)
            or result["forced_result"] != "DRAW"
            or result["terminal_reason"] != "NO_LEGAL_ACTION"
            or result["principal_variation_plies"] <= 0
        ):
            continue
        shape_clean = _shape_clean_stalemate(candidate)
        eligible.append(
            {
                "candidate": candidate,
                "shape_clean": shape_clean,
                "selection_group": "SHAPE_CLEAN" if shape_clean else "OTHER_DRAW",
                "selection_score": _stress_selection_score(game_hash, shape_clean),
            }
        )
    eligible.sort(
        key=lambda item: (
            not item["shape_clean"],
            item["selection_score"],
            item["candidate"]["definition_hash"],
        )
    )
    selected = eligible[:max_candidates]
    for rank, item in enumerate(selected, start=1):
        item["selection_rank"] = rank
    return {
        "eligible": eligible,
        "selected": selected,
        "unselected": eligible[max_candidates:],
    }


def _inspection_score(prefix: str, game_hash: str) -> str:
    return hashlib.sha256((prefix + game_hash).encode("ascii")).hexdigest()


def select_stalemate_inspection_cases(
    raw_candidates: Sequence[Mapping[str, Any]],
    stress_candidates: Sequence[Mapping[str, Any]],
    change_count: int = STALEMATE_INSPECTION_CHANGE_COUNT,
    control_count: int = STALEMATE_INSPECTION_CONTROL_COUNT,
) -> Dict[str, Any]:
    if change_count < 0 or control_count < 0:
        raise ValueError("inspection counts cannot be negative")
    raw_by_hash: Dict[str, Mapping[str, Any]] = {}
    raw_order = []
    reasons: DefaultDict[str, Set[str]] = defaultdict(set)
    changed = []
    unchanged = []
    for candidate in raw_candidates:
        game_hash = candidate.get("definition_hash")
        if not isinstance(game_hash, str) or game_hash in raw_by_hash:
            raise ValueError("inspection raw candidates need unique hashes")
        raw_by_hash[game_hash] = candidate
        raw_order.append(game_hash)
        status, result = _exact_status(candidate)
        if status != "COMPLETED":
            reasons[game_hash].add("EXACT_CENSORED")
            continue
        baseline = candidate.get("baseline_exact")
        if not isinstance(baseline, Mapping) or baseline.get("status") != "COMPLETED":
            raise ValueError("inspection candidate is missing baseline exact evidence")
        baseline_result = baseline.get("result")
        if not isinstance(baseline_result, Mapping):
            raise ValueError("inspection baseline result is malformed")
        assert result is not None
        is_changed = baseline_result.get("forced_result") != result["forced_result"]
        score = _inspection_score(
            _INSPECTION_CHANGE_PREFIX if is_changed else _INSPECTION_CONTROL_PREFIX,
            game_hash,
        )
        (changed if is_changed else unchanged).append((score, game_hash))

    seen_stress = set()
    for record in stress_candidates:
        game_hash = record.get("definition_hash")
        if game_hash not in raw_by_hash or game_hash in seen_stress:
            raise ValueError("inspection stress candidate does not match raw evidence")
        seen_stress.add(game_hash)
        reasons[game_hash].add("STRESS_SELECTED")
        status = record.get("status")
        if status == "CENSORED_NODE_BUDGET":
            reasons[game_hash].add("DEPTH5_CENSORED")
        elif status != "EVALUATED":
            raise ValueError("inspection stress status is unknown")
        if record.get("diagnostic_frontier") is True:
            reasons[game_hash].add("DIAGNOSTIC_FRONTIER")

    changed.sort()
    unchanged.sort()
    for _, game_hash in changed[:change_count]:
        reasons[game_hash].add("OUTCOME_CHANGED_HASH_SAMPLE")
    for _, game_hash in unchanged[:control_count]:
        reasons[game_hash].add("OUTCOME_UNCHANGED_HASH_CONTROL")

    records = []
    for game_hash in raw_order:
        if not reasons[game_hash]:
            continue
        candidate = raw_by_hash[game_hash]
        records.append(
            {
                "pair_id": candidate.get("pair_id"),
                "source_case_id": candidate.get("source_case_id"),
                "treatment_definition_hash": game_hash,
                "reasons": sorted(reasons[game_hash]),
                "change_selection_score": _inspection_score(
                    _INSPECTION_CHANGE_PREFIX, game_hash
                ),
                "control_selection_score": _inspection_score(
                    _INSPECTION_CONTROL_PREFIX, game_hash
                ),
            }
        )
    return {
        "configuration": {
            "change_count": change_count,
            "control_count": control_count,
            "change_order": (
                "sha256(stalemate-inspection-change-v1:<treatment hash>)"
            ),
            "control_order": (
                "sha256(stalemate-inspection-control-v1:<treatment hash>)"
            ),
        },
        "aggregate": {
            "selected_case_count": len(records),
            "changed_pool_count": len(changed),
            "unchanged_pool_count": len(unchanged),
            "changed_hash_sample_count": sum(
                "OUTCOME_CHANGED_HASH_SAMPLE" in record["reasons"]
                for record in records
            ),
            "unchanged_hash_control_count": sum(
                "OUTCOME_UNCHANGED_HASH_CONTROL" in record["reasons"]
                for record in records
            ),
            "changed_hash_sample_shortfall": max(0, change_count - len(changed)),
            "unchanged_hash_control_shortfall": max(
                0, control_count - len(unchanged)
            ),
        },
        "cases": records,
    }


def _final_assessments(
    raw_candidates: Sequence[Mapping[str, Any]],
    selection: Mapping[str, Any],
    stress_records: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    counts = _semantic_counts(raw_candidates)
    raw_assessments = _raw_assessments(counts, len(raw_candidates))
    exact_censored = counts["exact_censored_count"]
    ply_limit = counts["ply_limit_result_count"]
    evaluated = sum(record["status"] == "EVALUATED" for record in stress_records)
    node_censored = len(stress_records) - evaluated
    directional = [
        record
        for record in stress_records
        if record.get("decisive_misclassification") is True
    ]
    unselected = selection["unselected"]
    unselected_clean = sum(item["shape_clean"] for item in unselected)
    deferred_clean = sum(
        record["shape_clean"] and record["status"] != "EVALUATED"
        for record in stress_records
    )
    frontier = [record for record in stress_records if record["diagnostic_frontier"]]

    if directional:
        general = {
            "status": "NOT_SUPPORTED",
            "reasons": ["EXACT_DRAW_CALLED_DIRECTIONAL"],
        }
    elif unselected or node_censored or evaluated < 15:
        reasons = []
        if unselected:
            reasons.append("DRAW_CANDIDATE_CAP_CENSORING")
        if node_censored:
            reasons.append("DEPTH5_NODE_BUDGET_CENSORING")
        if evaluated < 15:
            reasons.append("FEWER_THAN_15_COMPLETIONS")
        general = {"status": "INCONCLUSIVE", "reasons": reasons}
    else:
        general = {"status": "SUPPORTED", "reasons": []}

    if ply_limit:
        frontier_response = {
            "status": "NOT_EVALUATED",
            "reasons": ["NON_HORIZON_PROOF_FAILURE"],
        }
        overall = {
            "status": "NOT_SUPPORTED",
            "reasons": ["TREATMENT_PLY_LIMIT_RESULT"],
        }
    elif exact_censored:
        frontier_response = {
            "status": "INCONCLUSIVE",
            "reasons": ["EXACT_STATE_BUDGET_CENSORING"],
        }
        overall = {
            "status": "INCONCLUSIVE",
            "reasons": ["EXACT_STATE_BUDGET_CENSORING"],
        }
    elif directional:
        frontier_response = {
            "status": "INCONCLUSIVE",
            "reasons": ["EVALUATOR_ERROR"],
        }
        overall = {
            "status": "INCONCLUSIVE",
            "reasons": ["EVALUATOR_ERROR"],
        }
    elif unselected_clean or deferred_clean:
        reasons = []
        if unselected_clean:
            reasons.append("SHAPE_CLEAN_DRAW_CANDIDATE_CAP")
        if deferred_clean:
            reasons.append("SHAPE_CLEAN_DRAW_NODE_BUDGET")
        frontier_response = {"status": "INCONCLUSIVE", "reasons": reasons}
        overall = {"status": "INCONCLUSIVE", "reasons": reasons}
    else:
        frontier_status = "SUPPORTED" if frontier else "NOT_SUPPORTED"
        frontier_response = {"status": frontier_status, "reasons": []}
        semantic_status = raw_assessments["semantic_response"]["status"]
        if semantic_status == "SUPPORTED" and frontier_status == "SUPPORTED":
            overall_status = "SUPPORTED"
        elif "NOT_SUPPORTED" in (semantic_status, frontier_status):
            overall_status = "NOT_SUPPORTED"
        else:
            overall_status = "INCONCLUSIVE"
        overall = {"status": overall_status, "reasons": []}
    return {
        **raw_assessments,
        "general_draw_stress": general,
        "frontier_response": frontier_response,
        "overall_treatment_discovery": overall,
    }


def _stress_configuration(
    seeds: Sequence[int],
    depth: int,
    max_nodes_per_candidate: int,
    max_candidates: int,
    gates: PlayGates,
) -> Dict[str, Any]:
    return {
        "depth": depth,
        "seeds": list(seeds),
        "max_nodes_per_candidate": max_nodes_per_candidate,
        "max_candidates": max_candidates,
        "play_gates": asdict(gates),
        "direction_rule": (
            "DRAW_OR_BALANCED only for no decisive games or exact A/B tie"
        ),
        "selection": (
            "shape-clean by sha256(stalemate-stress-clean-v1:<hash>), "
            "then other valid stalemate draws by "
            "sha256(stalemate-stress-other-v1:<hash>)"
        ),
    }


def _expected_stress_aggregate(
    raw_candidates: Sequence[Mapping[str, Any]],
    selection: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    counts = _semantic_counts(raw_candidates)
    assessments = _final_assessments(raw_candidates, selection, records)
    frontier = [record for record in records if record["diagnostic_frontier"]]
    frontier_strata = {
        _stratum_identity(record["stratum"]) for record in frontier
    }
    if counts["ply_limit_result_count"]:
        next_branch = "AUDIT_SEMANTICS_AND_EXHAUSTION_PROOF"
    elif counts["exact_censored_count"]:
        next_branch = "IMPROVE_EXACT_SEARCH"
    elif any(record.get("decisive_misclassification") is True for record in records):
        next_branch = "PRIORITIZE_INDEPENDENT_SOLVER_OR_LEAF_FAMILY"
    elif assessments["frontier_response"]["status"] == "INCONCLUSIVE":
        next_branch = "FRONTIER_INCONCLUSIVE"
    elif len(frontier) >= 4 and len(frontier_strata) >= 2:
        next_branch = "FREEZE_OUTCOME_BLIND_VALIDATION_CORPUS"
    elif len(frontier) >= 4:
        next_branch = "FREEZE_SINGLE_STRATUM_VALIDATION_CORPUS"
    elif frontier:
        next_branch = "FREEZE_FOCUSED_OUTCOME_BLIND_VALIDATION"
    else:
        next_branch = "DESIGN_DIRECT_INTERACTION_TEST"

    evaluated = sum(record["status"] == "EVALUATED" for record in records)
    node_censored = len(records) - evaluated
    unselected = selection["unselected"]
    directional_hashes = sorted(
        record["definition_hash"]
        for record in records
        if record.get("decisive_misclassification") is True
    )
    failure_histogram: Counter[str] = Counter()
    direction_histogram: Counter[str] = Counter()
    for record in records:
        failure_histogram.update(record["strong_failure_codes"])
        if record["sampled_direction"] is not None:
            direction_histogram[record["sampled_direction"]] += 1
    return {
        "raw_exact_censored_count": counts["exact_censored_count"],
        "raw_ply_limit_result_count": counts["ply_limit_result_count"],
        "eligible_draw_count": len(selection["eligible"]),
        "selected_draw_count": len(records),
        "unselected_draw_count": len(unselected),
        "unselected_draw_hashes": sorted(
            item["candidate"]["definition_hash"] for item in unselected
        ),
        "shape_clean_eligible_count": sum(
            item["shape_clean"] for item in selection["eligible"]
        ),
        "shape_clean_selected_count": sum(record["shape_clean"] for record in records),
        "shape_clean_unselected_count": sum(
            item["shape_clean"] for item in unselected
        ),
        "evaluated_count": evaluated,
        "node_budget_censored_count": node_censored,
        "node_budget_censored_hashes": sorted(
            record["definition_hash"]
            for record in records
            if record["status"] == "CENSORED_NODE_BUDGET"
        ),
        "sampled_direction_histogram": dict(sorted(direction_histogram.items())),
        "directional_error_count": len(directional_hashes),
        "directional_error_hashes": directional_hashes,
        "strong_failure_histogram": dict(sorted(failure_histogram.items())),
        "diagnostic_frontier_count": len(frontier),
        "diagnostic_frontier_hashes": sorted(
            record["definition_hash"] for record in frontier
        ),
        "diagnostic_frontier_stratum_count": len(frontier_strata),
        "expanded_nodes_total": sum(record["expanded_nodes"] for record in records),
        "expanded_nodes_max": max(
            (record["expanded_nodes"] for record in records), default=0
        ),
        "predeclared_assessment": assessments,
        "next_branch": next_branch,
    }


def _validate_stress_profile_mapping(
    profile: Any,
    definition: Any,
    seeds: Sequence[int],
    gates: PlayGates,
    label: str,
) -> Sequence[str]:
    if not isinstance(profile, Mapping) or set(profile) != _PROFILE_KEYS:
        raise ValueError("{} profile schema mismatch".format(label))
    seed_list = list(seeds)
    if (
        profile["profile"] != "stress-minimax-depth5"
        or profile["agent_a"] != "minimax-v1-depth5"
        or profile["agent_b"] != "minimax-v1-depth5"
        or profile["seeds"] != seed_list
        or profile["samples"] != len(seed_list)
    ):
        raise ValueError("{} profile identity mismatch".format(label))
    counts = (profile["a_wins"], profile["b_wins"], profile["draws"])
    if any(
        isinstance(count, bool) or not isinstance(count, int) or count < 0
        for count in counts
    ) or sum(counts) != len(seed_list):
        raise ValueError("{} profile counts are malformed".format(label))
    a_wins, b_wins, draws = counts
    decisive = a_wins + b_wins
    expected_share = a_wins / decisive if decisive else None
    if (
        profile["a_win_rate"] != a_wins / len(seed_list)
        or profile["b_win_rate"] != b_wins / len(seed_list)
        or profile["draw_rate"] != draws / len(seed_list)
        or profile["decisive_a_share"] != expected_share
        or isinstance(profile["average_plies"], bool)
        or not isinstance(profile["average_plies"], (int, float))
        or not math.isfinite(profile["average_plies"])
        or not 0 <= profile["average_plies"] <= definition.max_plies
    ):
        raise ValueError("{} profile rates are malformed".format(label))
    interval = profile["decisive_a_wilson_95"]
    if (decisive == 0 and interval is not None) or (
        decisive > 0 and interval != _wilson_interval(a_wins, decisive)
    ):
        raise ValueError("{} profile Wilson interval mismatch".format(label))
    reasons = profile["terminal_reasons"]
    if (
        not isinstance(reasons, Mapping)
        or not all(
            reason in {"GOAL", "PLY_LIMIT", "NO_LEGAL_ACTION"}
            and isinstance(count, int)
            and not isinstance(count, bool)
            and count >= 0
            for reason, count in reasons.items()
        )
        or sum(reasons.values()) != len(seed_list)
    ):
        raise ValueError("{} profile terminal reasons are malformed".format(label))
    _validate_terminal_reason_outcome_consistency(
        definition,
        a_wins,
        b_wins,
        draws,
        reasons,
        label,
    )
    _validate_sampled_natural_exhaustion(
        definition,
        profile["average_plies"],
        reasons,
        label,
    )
    return _failure_codes_from_profiles(definition, (profile,), gates)


def validate_stalemate_stress_result(
    result: Mapping[str, Any],
    raw_result: Mapping[str, Any],
    seeds: Sequence[int] = DRAW_STRESS_SEEDS,
    depth: int = DRAW_STRESS_DEPTH,
    max_nodes_per_candidate: int = DRAW_STRESS_MAX_NODES,
    max_candidates: int = DRAW_STRESS_MAX_CANDIDATES,
    gates: PlayGates = PlayGates(),
    inspection_change_count: int = STALEMATE_INSPECTION_CHANGE_COUNT,
    inspection_control_count: int = STALEMATE_INSPECTION_CONTROL_COUNT,
) -> Tuple[Mapping[str, Any], ...]:
    """Reconstruct and validate a sealed adaptive stress result."""

    if depth != DRAW_STRESS_DEPTH:
        raise ValueError("stalemate draw stress freezes depth at 5")
    seed_tuple = tuple(seeds)
    if not seed_tuple or len(set(seed_tuple)) != len(seed_tuple):
        raise ValueError("stalemate stress seeds must be non-empty and unique")
    if max_nodes_per_candidate < 1 or max_candidates < 1:
        raise ValueError("stalemate stress caps must be positive")
    if not isinstance(raw_result, Mapping):
        raise TypeError("raw_result must be an object")
    raw_candidates = raw_result.get("candidates")
    if not isinstance(raw_candidates, list) or not raw_candidates:
        raise ValueError("raw stalemate result needs candidates")
    if not isinstance(result, Mapping) or set(result) != {
        "configuration",
        "aggregate",
        "timing",
        "candidates",
        "inspection_selection",
    }:
        raise ValueError("stalemate stress result schema mismatch")
    expected_configuration = _stress_configuration(
        seed_tuple, depth, max_nodes_per_candidate, max_candidates, gates
    )
    if not _same_json_value(result.get("configuration"), expected_configuration):
        raise ValueError("stalemate stress configuration mismatch")
    timing = result.get("timing")
    if (
        not isinstance(timing, Mapping)
        or set(timing) != {"total_seconds"}
        or isinstance(timing["total_seconds"], bool)
        or not isinstance(timing["total_seconds"], (int, float))
        or not math.isfinite(timing["total_seconds"])
        or timing["total_seconds"] < 0
    ):
        raise ValueError("stalemate stress timing evidence is malformed")

    selection = select_stalemate_stress_candidates(raw_candidates, max_candidates)
    counts = _semantic_counts(raw_candidates)
    records = result.get("candidates")
    expected_count = (
        0 if counts["ply_limit_result_count"] else len(selection["selected"])
    )
    if not isinstance(records, list) or len(records) != expected_count:
        raise ValueError("stalemate stress candidate denominator mismatch")
    for index, (selected, record) in enumerate(zip(selection["selected"], records)):
        if not isinstance(record, Mapping) or set(record) != _STRESS_CANDIDATE_KEYS:
            raise ValueError("stalemate stress candidate schema mismatch")
        if (
            isinstance(record.get("selection_rank"), bool)
            or not isinstance(record.get("selection_rank"), int)
        ):
            raise ValueError("stalemate stress selection rank is malformed")
        source = selected["candidate"]
        definition = parse_definition(source["definition"])
        if (
            definition_hash(definition) != source["definition_hash"]
            or record["definition"] != definition.to_dict()
        ):
            raise ValueError("stalemate stress definition identity mismatch")
        expected_identity = {
            "pair_id": source.get("pair_id"),
            "source_case_id": source.get("source_case_id"),
            "definition_hash": source["definition_hash"],
            "d4_canonical_hash": source["d4_canonical_hash"],
            "stratum": source["stratum"],
            "shape_clean": selected["shape_clean"],
            "selection_group": selected["selection_group"],
            "selection_score": selected["selection_score"],
            "selection_rank": index + 1,
        }
        if not _same_json_value(
            {key: record.get(key) for key in expected_identity}, expected_identity
        ):
            raise ValueError("stalemate stress selection identity mismatch")
        expanded = record["expanded_nodes"]
        elapsed = record["elapsed_seconds"]
        if (
            isinstance(expanded, bool)
            or not isinstance(expanded, int)
            or not 0 <= expanded <= max_nodes_per_candidate
            or isinstance(elapsed, bool)
            or not isinstance(elapsed, (int, float))
            or not math.isfinite(elapsed)
            or elapsed < 0
        ):
            raise ValueError("stalemate stress work evidence is malformed")
        if record["status"] == "EVALUATED":
            if record["budget_observation"] is not None:
                raise ValueError("evaluated stress candidate has budget evidence")
            failures = _validate_stress_profile_mapping(
                record["profile"], definition, seed_tuple, gates, "stress index {}".format(index)
            )
            direction = sampled_direction(record["profile"])
            directional = direction in {"A_WIN", "B_WIN"}
            frontier = bool(selected["shape_clean"] and not directional and not failures)
            if (
                record["sampled_direction"] != direction
                or record["decisive_misclassification"] is not directional
                or record["strong_failure_codes"] != failures
                or record["diagnostic_frontier"] is not frontier
            ):
                raise ValueError("stalemate stress assessment evidence mismatch")
        elif record["status"] == "CENSORED_NODE_BUDGET":
            observation = record["budget_observation"]
            if (
                record["profile"] is not None
                or record["sampled_direction"] is not None
                or record["decisive_misclassification"] is not None
                or record["strong_failure_codes"] != []
                or record["diagnostic_frontier"] is not False
                or not isinstance(observation, Mapping)
                or set(observation) != {"scope", "visited_nodes", "max_nodes"}
                or observation["scope"] != "per-candidate"
                or observation["visited_nodes"] != max_nodes_per_candidate
                or observation["max_nodes"] != max_nodes_per_candidate
                or expanded != max_nodes_per_candidate
            ):
                raise ValueError("stalemate stress node censor evidence mismatch")
        else:
            raise ValueError("stalemate stress candidate status is unknown")

    expected_aggregate = _expected_stress_aggregate(
        raw_candidates, selection, records
    )
    if not _same_json_value(result.get("aggregate"), expected_aggregate):
        raise ValueError("stalemate stress aggregate mismatch")
    expected_inspection = select_stalemate_inspection_cases(
        raw_candidates,
        records,
        change_count=inspection_change_count,
        control_count=inspection_control_count,
    )
    if not _same_json_value(result.get("inspection_selection"), expected_inspection):
        raise ValueError("stalemate stress inspection selection mismatch")
    elapsed_total = sum(record["elapsed_seconds"] for record in records)
    tolerance = max(1e-9, 1e-12 * max(1.0, elapsed_total))
    if timing["total_seconds"] + tolerance < elapsed_total:
        raise ValueError(
            "stalemate stress total timing is below candidate elapsed evidence"
        )
    return tuple(records)


def stress_stalemate_draws(
    raw_result: Mapping[str, Any],
    seeds: Sequence[int] = DRAW_STRESS_SEEDS,
    depth: int = DRAW_STRESS_DEPTH,
    max_nodes_per_candidate: int = DRAW_STRESS_MAX_NODES,
    max_candidates: int = DRAW_STRESS_MAX_CANDIDATES,
    gates: PlayGates = PlayGates(),
    inspection_change_count: int = STALEMATE_INSPECTION_CHANGE_COUNT,
    inspection_control_count: int = STALEMATE_INSPECTION_CONTROL_COUNT,
    clock: Callable[[], float] = time.perf_counter,
) -> Dict[str, Any]:
    """Stress structurally valid treatment stalemate draws and apply plan 0007."""

    if not isinstance(raw_result, Mapping):
        raise TypeError("raw_result must be an object")
    raw_candidates = raw_result.get("candidates")
    if not isinstance(raw_candidates, list) or not raw_candidates:
        raise ValueError("raw stalemate result needs candidates")
    if depth != DRAW_STRESS_DEPTH:
        raise ValueError("stalemate draw stress freezes depth at 5")
    seed_tuple = tuple(seeds)
    if not seed_tuple or len(set(seed_tuple)) != len(seed_tuple):
        raise ValueError("stalemate stress seeds must be non-empty and unique")
    if max_nodes_per_candidate < 1:
        raise ValueError("max_nodes_per_candidate must be at least one")
    counts = _semantic_counts(raw_candidates)
    selection = select_stalemate_stress_candidates(raw_candidates, max_candidates)
    records = []
    total_started = clock()

    # A ply-limit result violates the structural proof.  Do not generate adaptive
    # evidence from a corpus whose treatment semantics are already invalid.
    if counts["ply_limit_result_count"] == 0:
        for selected in selection["selected"]:
            source = selected["candidate"]
            definition = parse_definition(source["definition"])
            if definition_hash(definition) != source["definition_hash"]:
                raise ValueError("stalemate stress definition hash mismatch")
            agent = MinimaxAgent(depth=depth, max_total_nodes=max_nodes_per_candidate)
            started = clock()
            try:
                profile = evaluate_matchup(
                    definition,
                    "stress-minimax-depth5",
                    {Player.A: agent, Player.B: agent},
                    seed_tuple,
                )
            except SearchBudgetExceeded as error:
                elapsed = clock() - started
                records.append(
                    {
                        "pair_id": source.get("pair_id"),
                        "source_case_id": source.get("source_case_id"),
                        "definition_hash": source["definition_hash"],
                        "d4_canonical_hash": source["d4_canonical_hash"],
                        "stratum": _json_copy(source["stratum"], "stress stratum"),
                        "shape_clean": selected["shape_clean"],
                        "selection_group": selected["selection_group"],
                        "selection_score": selected["selection_score"],
                        "selection_rank": selected["selection_rank"],
                        "status": "CENSORED_NODE_BUDGET",
                        "sampled_direction": None,
                        "decisive_misclassification": None,
                        "strong_failure_codes": [],
                        "diagnostic_frontier": False,
                        "expanded_nodes": agent.total_nodes,
                        "elapsed_seconds": elapsed,
                        "budget_observation": {
                            "scope": error.scope,
                            "visited_nodes": error.visited_nodes,
                            "max_nodes": error.max_nodes,
                        },
                        "profile": None,
                        "definition": definition.to_dict(),
                    }
                )
                continue
            elapsed = clock() - started
            profile_mapping = profile.to_dict(include_records=False)
            direction = sampled_direction(profile_mapping)
            directional = direction in {"A_WIN", "B_WIN"}
            failures = sorted(
                code.value
                for code in classify_play_failures(definition, (profile,), gates)
            )
            records.append(
                {
                    "pair_id": source.get("pair_id"),
                    "source_case_id": source.get("source_case_id"),
                    "definition_hash": source["definition_hash"],
                    "d4_canonical_hash": source["d4_canonical_hash"],
                    "stratum": _json_copy(source["stratum"], "stress stratum"),
                    "shape_clean": selected["shape_clean"],
                    "selection_group": selected["selection_group"],
                    "selection_score": selected["selection_score"],
                    "selection_rank": selected["selection_rank"],
                    "status": "EVALUATED",
                    "sampled_direction": direction,
                    "decisive_misclassification": directional,
                    "strong_failure_codes": failures,
                    "diagnostic_frontier": bool(
                        selected["shape_clean"]
                        and not directional
                        and not failures
                    ),
                    "expanded_nodes": agent.total_nodes,
                    "elapsed_seconds": elapsed,
                    "budget_observation": None,
                    "profile": profile_mapping,
                    "definition": definition.to_dict(),
                }
            )

    return {
        "configuration": _stress_configuration(
            seed_tuple, depth, max_nodes_per_candidate, max_candidates, gates
        ),
        "aggregate": _expected_stress_aggregate(
            raw_candidates, selection, records
        ),
        "timing": {"total_seconds": clock() - total_started},
        "candidates": records,
        "inspection_selection": select_stalemate_inspection_cases(
            raw_candidates,
            records,
            change_count=inspection_change_count,
            control_count=inspection_control_count,
        ),
    }
