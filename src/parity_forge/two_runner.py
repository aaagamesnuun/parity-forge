"""Pure outcome-free construction for the schema-v1 two-runner experiment.

The module accepts only detached DSL definitions, authenticated definition
projections, and identity metadata.  It performs no filesystem, Git, solving, or
play-agent work.  In particular, the treatment stays in the source's stored D4
frame; only its D4 hash is used as an orbit identity.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from functools import lru_cache
from typing import Any, Dict, Iterable, Mapping, Sequence, Set, Tuple

from .analysis import analyze_definition
from .asymmetry import evaluate_asymmetry
from .capture import CAPTURE_EXACT_MAX_STATES, CAPTURE_STATE_BOUND
from .capture_boundary import (
    CAPTURE_BOUNDARY_COVERED_D4_COUNT,
    CAPTURE_BOUNDARY_LANDSCAPE_SOURCE,
    CAPTURE_BOUNDARY_MANIFEST_ID,
    CAPTURE_BOUNDARY_MANIFEST_PROTOCOL_ID,
    project_boundary_definitions,
    project_boundary_exclusion_sources,
    validate_boundary_coverage_projection,
    validate_boundary_definition_projection,
    validate_boundary_exclusion_ledger,
    validate_capture_boundary_manifest,
)
from .dsl import (
    ActionKind,
    DefinitionError,
    Edge,
    GameDefinition,
    GoalKind,
    Player,
    canonical_json,
    definition_hash,
    parse_definition,
)
from .landscape import (
    RAW_D4_ORBIT_COUNT,
    RAW_DEFINITION_COUNT,
    _canonical_orbit_representatives,
)
from .simplicity import evaluate_simplicity, exceeds_limits
from .symmetry import (
    D4_TRANSFORMS,
    canonicalize_d4,
    d4_canonical_hash,
    mechanical_json,
    transform_definition,
)


TWO_RUNNER_MANIFEST_VERSION = 1
TWO_RUNNER_MANIFEST_ID = "two-runner-v1-64-pair-manifest"
TWO_RUNNER_MANIFEST_PROTOCOL_ID = "two-runner-v1-manifest-freeze"
TWO_RUNNER_PAIR_COUNT = 64
TWO_RUNNER_STRATUM_COUNT = 16
TWO_RUNNER_QUOTA_PER_STRATUM = 4

TWO_RUNNER_BASE_EVALUATED_D4_COUNT = CAPTURE_BOUNDARY_COVERED_D4_COUNT
TWO_RUNNER_PLAN0009_SOURCE_D4_COUNT = 64
TWO_RUNNER_EVALUATED_D4_COUNT = 503
TWO_RUNNER_RELEVANT_D4_COUNT = 1_016
TWO_RUNNER_RELEVANT_EXCLUDED_D4_COUNT = 109
TWO_RUNNER_UNUSED_RELEVANT_D4_COUNT = 907
TWO_RUNNER_GATE_VALID_D4_COUNT = 738
TWO_RUNNER_GATE_DISAGREEMENT_COUNT = 59
TWO_RUNNER_TREATMENT_UNIQUE_D4_COUNT = 477
TWO_RUNNER_TREATMENT_SINGLETON_COUNT = 216
TWO_RUNNER_TREATMENT_DOUBLE_COUNT = 261
TWO_RUNNER_MIN_STRATUM_COUNT = 19
TWO_RUNNER_MAX_STRATUM_COUNT = 36
TWO_RUNNER_D4_EQUIVARIANCE_CHECK_COUNT = TWO_RUNNER_RELEVANT_D4_COUNT * len(
    D4_TRANSFORMS
)

TWO_RUNNER_SOURCE_STATE_BOUND = CAPTURE_STATE_BOUND
TWO_RUNNER_TREATMENT_STATE_BOUND = 69_120
TWO_RUNNER_EXACT_MAX_STATES = CAPTURE_EXACT_MAX_STATES
TWO_RUNNER_HISTORICAL_ARTIFACT_COUNT = 21

TWO_RUNNER_PLAN0009_MANIFEST_ARTIFACT = {
    "path": "experiments/corpora/capture-boundary-v1/manifest.json",
    "sha256": "e1b0f6a7aed05264133964954380e6d59b200cfe903888b2d279f2a626ebd78f",
    "identity_kind": "manifest_id",
    "identity": CAPTURE_BOUNDARY_MANIFEST_ID,
}
TWO_RUNNER_PLAN0009_LEDGER_ARTIFACT = {
    "path": "experiments/corpora/capture-boundary-v1/exclusion-ledger.json",
    "sha256": "841789e168baf7446072d189ca272783c944d36d71630421f9fe70ec6a3865ea",
    "identity_kind": "ledger_root",
    "identity": "d257fb039ec8bd8c77ca1f955fcc94dc19658d527047983740eb72772eb36889",
}
TWO_RUNNER_PLAN0009_MANIFEST_CHAIN = (
    {
        "path": "experiments/corpora/capture-boundary-v1/manifest-reservation.json",
        "sha256": "175ec078aec69d781a3d4060a714ce9fcaf81ed6c60ef2c76edfa6b94a22692f",
    },
    {
        "path": "experiments/corpora/capture-boundary-v1/manifest-attempt.json",
        "sha256": "33dcc61b35526d07b760c5138049800910fff860e7ed305155ab3ecfad538d17",
    },
    dict(TWO_RUNNER_PLAN0009_LEDGER_ARTIFACT),
    dict(TWO_RUNNER_PLAN0009_MANIFEST_ARTIFACT),
    {
        "path": "experiments/corpora/capture-boundary-v1/manifest.lock.json",
        "sha256": "5d12680fc87db2cba19aa1b0a160a1eaf3c51be150ad759c44dc365df0d23dc7",
    },
)

# Independently reconstructed and reviewed before any two-runner outcome.
TWO_RUNNER_CLOSED_PROJECTION_BUNDLE_ROOT = (
    "755b5a5d8ae35d8222873275e87860effbdf7ec2266de3799814d20385b12ca3"
)
TWO_RUNNER_EXECUTABLE_FINGERPRINT_PATHS = (
    "src/parity_forge/__init__.py",
    "src/parity_forge/__main__.py",
    "src/parity_forge/agents.py",
    "src/parity_forge/analysis.py",
    "src/parity_forge/asymmetry.py",
    "src/parity_forge/audit.py",
    "src/parity_forge/batch.py",
    "src/parity_forge/calibration.py",
    "src/parity_forge/capture.py",
    "src/parity_forge/capture_boundary.py",
    "src/parity_forge/capture_boundary_evaluation.py",
    "src/parity_forge/capture_boundary_experiments.py",
    "src/parity_forge/capture_experiments.py",
    "src/parity_forge/cascade.py",
    "src/parity_forge/dsl.py",
    "src/parity_forge/engine.py",
    "src/parity_forge/experiments.py",
    "src/parity_forge/generator.py",
    "src/parity_forge/heldout_audit.py",
    "src/parity_forge/landscape.py",
    "src/parity_forge/landscape_evaluation.py",
    "src/parity_forge/landscape_experiments.py",
    "src/parity_forge/play.py",
    "src/parity_forge/simplicity.py",
    "src/parity_forge/solver.py",
    "src/parity_forge/stalemate.py",
    "src/parity_forge/stalemate_experiments.py",
    "src/parity_forge/symmetry.py",
    "src/parity_forge/two_runner.py",
    "src/parity_forge/two_runner_evaluation.py",
    "src/parity_forge/two_runner_experiments.py",
)
TWO_RUNNER_EVALUATED_PROJECTION_ROOT = (
    "7064501b4514b34420e6fe7f0d4927cb6b3fb84e8610cabb510f6265520471d6"
)
TWO_RUNNER_EVALUATED_D4_ROOT = (
    "0c83885bf5eb1e670327ae6618b67805ba3b023a4bab206e7d98d753544ff05a"
)
TWO_RUNNER_HISTORICAL_PROJECTION_ROOT = (
    "0a4a38245c3666f215041d10383112e65c82f40bc5d2f510df2d4418d65c2f91"
)
TWO_RUNNER_HISTORICAL_D4_ROOT = (
    "9c8b2d54659c5021fbc47dfa38cb435ed068132e6e790e5057d86a13f93c07ba"
)
TWO_RUNNER_PLAN0009_SOURCE_PROJECTION_ROOT = (
    "dd5f1291757bd3c761b7d6a633705783bd2014bf22bc7f6514e4832cd11127e8"
)
TWO_RUNNER_PLAN0009_FULL_PROJECTION_ROOT = (
    "c32d83cb397744e3af5e34f8ce504aa60857c84b28e687d131ab6ded3cc85319"
)
TWO_RUNNER_RELEVANT_D4_ROOT = (
    "c8c598979357be9c04bb89d1b95cd10cb6536b853b10a0ee7c8354514d19827e"
)
TWO_RUNNER_REPRESENTATIVE_CHOICE_ROOT = (
    "62ffa9c07ae84c7566330310f9029599b0c8d4e929a39272a583a2d5e4f4f859"
)
TWO_RUNNER_ELIGIBLE_POOL_ROOT = (
    "73dcda3d2845c01113b41ecf8d46b923f044e4ec11c1d80c205644de0028b706"
)
TWO_RUNNER_SELECTION_FINGERPRINT = (
    "8bb8feb104ce58e92729d593464acb6e08e2de9c59154440c15580a66db9eb91"
)
TWO_RUNNER_HISTORICAL_DEFINITION_OCCURRENCE_COUNT = 2_115
TWO_RUNNER_HISTORICAL_UNIQUE_DEFINITION_COUNT = 1_044
TWO_RUNNER_HISTORICAL_UNIQUE_D4_COUNT = 1_040
TWO_RUNNER_STATIC_DEFINITION_COUNT = 6
TWO_RUNNER_STATIC_DEFINITION_PROJECTION_ROOT = (
    "07a2436373ee4f15b88b9c5aec5757484d4ac3bb80e3b0dd99e7ebfc88489e3a"
)
TWO_RUNNER_STATIC_D4_ROOT = (
    "b996b415f2bd1dceb100f249606896b4c4e64fa49046ac1a403aed898ca01d7c"
)

_EXPECTED_STRATUM_COUNTS = {
    "fA-aligned-v1_3": 36,
    "fA-aligned-v4": 35,
    "fA-aligned-v5": 30,
    "fA-aligned-v6_7": 20,
    "fA-orthogonal-v1_3": 35,
    "fA-orthogonal-v4": 34,
    "fA-orthogonal-v5": 30,
    "fA-orthogonal-v6_7": 21,
    "fB-aligned-v1_3": 35,
    "fB-aligned-v4": 33,
    "fB-aligned-v5": 29,
    "fB-aligned-v6_7": 19,
    "fB-orthogonal-v1_3": 36,
    "fB-orthogonal-v4": 34,
    "fB-orthogonal-v5": 29,
    "fB-orthogonal-v6_7": 21,
}

_EVALUATED_D4_DOMAIN = b"two-runner-v1-evaluated-orbits-v1"
_EVALUATED_PROJECTION_DOMAIN = b"two-runner-v1-evaluated-projection-v1"
_HISTORICAL_SOURCE_D4_DOMAIN = b"two-runner-v1-historical-source-d4-v1"
_HISTORICAL_D4_DOMAIN = b"two-runner-v1-historical-d4-v1"
_HISTORICAL_PROJECTION_DOMAIN = b"two-runner-v1-historical-projection-v1"
_RELEVANT_D4_DOMAIN = b"two-runner-v1-relevant-orbits-v1"
_REPRESENTATIVE_CHOICE_DOMAIN = b"two-runner-v1-representative-choice-v1"
_SELECTION_SCORE_DOMAIN = b"two-runner-v1-selection-score-v1"
_ELIGIBLE_POOL_DOMAIN = b"two-runner-v1-eligible-pool-v1"
_ELIGIBLE_POOLS_DOMAIN = b"two-runner-v1-eligible-pools-v1"
_SELECTION_FINGERPRINT_DOMAIN = b"two-runner-v1-selection-fingerprint-v1"
_PAIR_FINGERPRINT_DOMAIN = b"two-runner-v1-pair-v1"
_CLOSED_PROJECTION_BUNDLE_DOMAIN = b"two-runner-v1-closed-projection-bundle-v1"

_FORBIDDEN_SELECTION_KEYS = frozenset(
    (
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
        "timing",
        "elapsed_seconds",
    )
)
_FORBIDDEN_SELECTION_KEY_TERMS = frozenset(
    (
        "outcome",
        "result",
        "winner",
        "terminal",
        "evaluation",
        "evaluate",
        "solver",
        "solve",
        "play",
        "assessment",
        "timing",
        "elapsed",
        "duration",
    )
)
_PLAN_PATH = "docs/plans/active/0010-two-runner-existing-dsl-family-viability.md"
_SELECTION_INPUT_ATTESTATION = "authenticated-definition-projections-only"
_CLOSED_PROJECTION_BUNDLE_PATH = (
    "experiments/corpora/two-runner-v1/exclusion-ledger.json"
)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _json_copy(value: Any, label: str) -> Any:
    try:
        return json.loads(_canonical_bytes(value))
    except (TypeError, ValueError) as error:
        raise ValueError("{} must be finite JSON".format(label)) from error


def _domain_digest(domain: bytes, value: Any) -> str:
    return hashlib.sha256(domain + b"\0" + _canonical_bytes(value)).hexdigest()


def _repository_json_bytes(value: Any) -> bytes:
    try:
        return (
            json.dumps(
                value,
                indent=2,
                sort_keys=True,
                ensure_ascii=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ValueError("authenticated source must be canonical JSON") from error


def _exact_keys(
    value: Any, expected: Iterable[str], label: str
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("{} must be an object".format(label))
    expected_set = set(expected)
    if set(value) != expected_set:
        raise ValueError(
            "{} keys must be exactly {}".format(label, sorted(expected_set))
        )
    return value


def _require_int(value: Any, expected: int | None, label: str) -> int:
    if type(value) is not int:
        raise ValueError("{} must be an integer".format(label))
    if expected is not None and value != expected:
        raise ValueError("{} mismatch".format(label))
    return value


def _require_sha256(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError("{} must be a canonical lowercase SHA-256".format(label))
    return value


def _require_sorted_hashes(value: Any, label: str) -> Tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError("{} must be an array".format(label))
    hashes = tuple(_require_sha256(item, label) for item in value)
    if list(hashes) != sorted(set(hashes)):
        raise ValueError("{} must be unique and lexically ordered".format(label))
    return hashes


def _contains_forbidden_selection_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                return True
            tokens = frozenset(key.lower().replace("-", "_").split("_"))
            if (
                key in _FORBIDDEN_SELECTION_KEYS
                or tokens & _FORBIDDEN_SELECTION_KEY_TERMS
            ):
                return True
            if _contains_forbidden_selection_key(item):
                return True
        return False
    if isinstance(value, (list, tuple)):
        return any(_contains_forbidden_selection_key(item) for item in value)
    return False


def _coerce_definition(value: Any) -> GameDefinition:
    if isinstance(value, GameDefinition):
        return value
    if isinstance(value, Mapping):
        return parse_definition(value)
    raise TypeError("definition must be a GameDefinition or mapping")


def _validated_manifest_provenance(value: Any) -> Dict[str, Any]:
    top = _exact_keys(
        value,
        (
            "freezer_git_commit",
            "freezer_git_dirty",
            "created_at",
            "protocol_id",
            "protocol_plan",
            "protocol_fingerprints",
            "executable_fingerprints",
            "closed_projection_bundle",
            "plan0009_manifest_chain",
            "selection_inputs",
            "independent_review",
        ),
        "two-runner provenance",
    )
    commit = top["freezer_git_commit"]
    if (
        not isinstance(commit, str)
        or len(commit) != 40
        or any(character not in "0123456789abcdef" for character in commit)
    ):
        raise ValueError("freezer commit must be a full lowercase Git SHA")
    if top["freezer_git_dirty"] is not False:
        raise ValueError("two-runner freezer must record a clean Git state")
    created_at = top["created_at"]
    if not isinstance(created_at, str) or not created_at.endswith("Z"):
        raise ValueError("two-runner provenance created_at must be UTC")
    protocol_plan = _exact_keys(
        top["protocol_plan"],
        ("path", "sha256", "git_blob_sha"),
        "two-runner protocol plan",
    )
    plan_sha256 = _require_sha256(
        protocol_plan["sha256"], "two-runner protocol plan SHA-256"
    )
    git_blob_sha = protocol_plan["git_blob_sha"]
    if (
        not isinstance(git_blob_sha, str)
        or len(git_blob_sha) != 40
        or any(character not in "0123456789abcdef" for character in git_blob_sha)
    ):
        raise ValueError("two-runner protocol plan Git blob must be lowercase SHA-1")
    protocol_fingerprints = top["protocol_fingerprints"]
    if (
        not isinstance(protocol_fingerprints, Mapping)
        or set(protocol_fingerprints) != {_PLAN_PATH}
        or protocol_fingerprints.get(_PLAN_PATH) != plan_sha256
    ):
        raise ValueError("two-runner protocol fingerprints mismatch the plan")
    executable_fingerprints = top["executable_fingerprints"]
    if (
        not isinstance(executable_fingerprints, Mapping)
        or set(executable_fingerprints) != set(TWO_RUNNER_EXECUTABLE_FINGERPRINT_PATHS)
    ):
        raise ValueError("two-runner executable fingerprint closure mismatch")
    normalized_executables: Dict[str, str] = {}
    for path, digest in executable_fingerprints.items():
        normalized_executables[path] = _require_sha256(
            digest, "two-runner executable fingerprint"
        )
    if list(normalized_executables) != list(TWO_RUNNER_EXECUTABLE_FINGERPRINT_PATHS):
        raise ValueError("two-runner executable fingerprints must be path ordered")
    closed_bundle = _exact_keys(
        top["closed_projection_bundle"],
        ("path", "bundle_root", "sha256", "bytes"),
        "two-runner closed projection bundle provenance",
    )
    bundle_bytes = _require_int(
        closed_bundle["bytes"], None, "closed projection bundle bytes"
    )
    if bundle_bytes < 1:
        raise ValueError("closed projection bundle bytes must be positive")
    normalized_bundle = {
        "path": _CLOSED_PROJECTION_BUNDLE_PATH,
        "bundle_root": _require_sha256(
            closed_bundle["bundle_root"], "closed projection bundle root"
        ),
        "sha256": _require_sha256(
            closed_bundle["sha256"], "closed projection bundle byte SHA-256"
        ),
        "bytes": bundle_bytes,
    }
    if normalized_bundle["bundle_root"] != TWO_RUNNER_CLOSED_PROJECTION_BUNDLE_ROOT:
        raise ValueError("closed projection bundle root differs from the reviewed root")
    if closed_bundle["path"] != _CLOSED_PROJECTION_BUNDLE_PATH:
        raise ValueError("closed projection bundle path mismatch")
    plan0009_chain = top["plan0009_manifest_chain"]
    if _canonical_bytes(plan0009_chain) != _canonical_bytes(
        TWO_RUNNER_PLAN0009_MANIFEST_CHAIN
    ):
        raise ValueError("Plan-0009 manifest chain differs from frozen bytes")
    expected = {
        "freezer_git_commit": commit,
        "freezer_git_dirty": False,
        "created_at": created_at,
        "protocol_id": TWO_RUNNER_MANIFEST_PROTOCOL_ID,
        "protocol_plan": {
            "path": _PLAN_PATH,
            "sha256": plan_sha256,
            "git_blob_sha": git_blob_sha,
        },
        "protocol_fingerprints": {_PLAN_PATH: plan_sha256},
        "executable_fingerprints": normalized_executables,
        "closed_projection_bundle": normalized_bundle,
        "plan0009_manifest_chain": [
            dict(record) for record in TWO_RUNNER_PLAN0009_MANIFEST_CHAIN
        ],
        "selection_inputs": _SELECTION_INPUT_ATTESTATION,
        "independent_review": "PASSED",
    }
    if _canonical_bytes(top) != _canonical_bytes(expected):
        raise ValueError("two-runner provenance values mismatch the frozen schema")
    return expected


def _opposite_edge_positions(size: int, target: Edge) -> Tuple[Tuple[int, int], ...]:
    if target is Edge.TOP:
        return tuple((size - 1, column) for column in range(size))
    if target is Edge.BOTTOM:
        return tuple((0, column) for column in range(size))
    if target is Edge.LEFT:
        return tuple((row, size - 1) for row in range(size))
    return tuple((row, 0) for row in range(size))


def _opposite_edge_corners(size: int, target: Edge) -> Tuple[Tuple[int, int], ...]:
    positions = _opposite_edge_positions(size, target)
    return (positions[0], positions[-1])


def _validate_one_runner_family(
    definition: GameDefinition,
    *,
    require_corner: bool,
) -> None:
    if (
        definition.schema_version != 1
        or definition.board_size != 3
        or definition.max_plies != 18
        or definition.terminal_policy is not None
    ):
        raise ValueError(
            "two-runner sources must use schema v1 on 3x3 with max_plies 18"
        )
    role_a = definition.role(Player.A)
    role_b = definition.role(Player.B)
    if (
        role_a.action.kind is not ActionKind.PLACE
        or role_a.action.piece != "seed"
        or role_a.goal.kind is not GoalKind.CONNECT_EDGES
        or role_a.goal.piece != "seed"
        or role_b.action.kind is not ActionKind.MOVE
        or role_b.action.piece != "runner"
        or not 1 <= len(role_b.action.vectors) <= 7
        or role_b.goal.kind is not GoalKind.REACH_EDGE
        or role_b.goal.piece != "runner"
        or role_b.goal.edge is None
    ):
        raise ValueError("definition is outside the A-place/B-move source family")
    if (
        len(definition.initial_pieces) != 1
        or definition.initial_pieces[0].owner is not Player.B
        or definition.initial_pieces[0].piece != "runner"
    ):
        raise ValueError("source must contain exactly one B runner")
    position = definition.initial_pieces[0].position
    allowed = (
        _opposite_edge_corners(definition.board_size, role_b.goal.edge)
        if require_corner
        else _opposite_edge_positions(definition.board_size, role_b.goal.edge)
    )
    if position not in allowed:
        qualifier = "corner of the " if require_corner else ""
        raise ValueError(
            "source runner must start at a {}edge opposite its target".format(
                qualifier
            )
        )


def _validate_two_runner_family(definition: GameDefinition) -> None:
    if (
        definition.schema_version != 1
        or definition.board_size != 3
        or definition.max_plies != 18
        or definition.terminal_policy is not None
    ):
        raise ValueError(
            "two-runner treatments must use schema v1 on 3x3 with max_plies 18"
        )
    role_a = definition.role(Player.A)
    role_b = definition.role(Player.B)
    if (
        role_a.action.kind is not ActionKind.PLACE
        or role_a.action.piece != "seed"
        or role_a.goal.kind is not GoalKind.CONNECT_EDGES
        or role_a.goal.piece != "seed"
        or role_b.action.kind is not ActionKind.MOVE
        or role_b.action.piece != "runner"
        or not 1 <= len(role_b.action.vectors) <= 7
        or role_b.goal.kind is not GoalKind.REACH_EDGE
        or role_b.goal.piece != "runner"
        or role_b.goal.edge is None
    ):
        raise ValueError("definition is outside the A-place/B-move treatment family")
    expected_positions = set(
        _opposite_edge_corners(definition.board_size, role_b.goal.edge)
    )
    observed_positions = {
        piece.position
        for piece in definition.initial_pieces
        if piece.owner is Player.B and piece.piece == "runner"
    }
    if (
        len(definition.initial_pieces) != 2
        or len(observed_positions) != 2
        or observed_positions != expected_positions
    ):
        raise ValueError(
            "treatment must contain identical B runners at both opposite-edge corners"
        )


def two_runner_added_position(source_value: Any) -> Tuple[int, int]:
    """Return the other corner selected by the frozen one-variable treatment."""

    source = _coerce_definition(source_value)
    _validate_one_runner_family(source, require_corner=True)
    role_b = source.role(Player.B)
    assert role_b.goal.edge is not None
    original = source.initial_pieces[0].position
    corners = _opposite_edge_corners(source.board_size, role_b.goal.edge)
    return corners[1] if original == corners[0] else corners[0]


def derive_two_runner_treatment(source_value: Any) -> GameDefinition:
    """Append the other identical runner without changing the source D4 frame."""

    source = _coerce_definition(source_value)
    _validate_one_runner_family(source, require_corner=True)
    mapping = source.to_dict()
    mapping["name"] = source.name + "-two-runner"
    mapping["initial_pieces"].append(
        {
            "owner": "B",
            "piece": "runner",
            "position": list(two_runner_added_position(source)),
        }
    )
    treatment = parse_definition(mapping)
    validate_two_runner_pair(source, treatment)
    return treatment


def validate_two_runner_pair(source_value: Any, treatment_value: Any) -> None:
    """Validate the exact same-frame one-to-two-runner edit."""

    source = _coerce_definition(source_value)
    treatment = _coerce_definition(treatment_value)
    _validate_one_runner_family(source, require_corner=True)
    _validate_two_runner_family(treatment)
    expected = source.to_dict()
    expected["name"] = source.name + "-two-runner"
    expected["initial_pieces"].append(
        {
            "owner": "B",
            "piece": "runner",
            "position": list(two_runner_added_position(source)),
        }
    )
    expected_definition = parse_definition(expected)
    if _canonical_bytes(treatment.to_dict()) != _canonical_bytes(
        expected_definition.to_dict()
    ):
        raise ValueError("two-runner pair changes more than name and one setup entry")


def revert_two_runner_pair(
    source_value: Any, treatment_value: Any
) -> GameDefinition:
    """Remove the added runner using the source as the required endpoint witness."""

    source = _coerce_definition(source_value)
    treatment = _coerce_definition(treatment_value)
    validate_two_runner_pair(source, treatment)
    added = two_runner_added_position(source)
    mapping = treatment.to_dict()
    mapping["name"] = source.name
    retained = [
        piece
        for piece in mapping["initial_pieces"]
        if not (
            piece["owner"] == "B"
            and piece["piece"] == "runner"
            and tuple(piece["position"]) == added
        )
    ]
    if len(retained) != 1:
        raise ValueError("source-witnessed removal did not identify one added runner")
    mapping["initial_pieces"] = retained
    restored = parse_definition(mapping)
    if canonical_json(restored) != canonical_json(source):
        raise ValueError("source-witnessed removal did not restore canonical bytes")
    return restored


def validate_two_runner_d4_equivariance(source_value: Any) -> None:
    """Prove derivation and source-witnessed removal commute with every D4 map."""

    source = _coerce_definition(source_value)
    treatment = derive_two_runner_treatment(source)
    for transform in D4_TRANSFORMS:
        transformed_source = transform_definition(source, transform)
        derived_after_transform = derive_two_runner_treatment(transformed_source)
        transformed_treatment = transform_definition(treatment, transform)
        if canonical_json(derived_after_transform) != canonical_json(
            transformed_treatment
        ):
            raise ValueError(
                "two-runner derivation does not commute with {}".format(transform)
            )
        restored = revert_two_runner_pair(
            transformed_source, transformed_treatment
        )
        if canonical_json(restored) != canonical_json(transformed_source):
            raise ValueError(
                "two-runner source-witnessed removal failed after {}".format(
                    transform
                )
            )


def two_runner_natural_terminal_ply_bound(definition_value: Any) -> int:
    """Return the last possible A placement ply before B must be immobile."""

    definition = _coerce_definition(definition_value)
    if len(definition.initial_pieces) == 1:
        _validate_one_runner_family(definition, require_corner=True)
        placements = 8
    elif len(definition.initial_pieces) == 2:
        _validate_two_runner_family(definition)
        placements = 7
    else:
        raise ValueError("natural termination proof requires one or two runners")
    first_a_ply = 1 if definition.first_player is Player.A else 2
    return first_a_ply + 2 * (placements - 1)


def two_runner_state_upper_bound(definition_value: Any) -> int:
    """Return the frozen structural exact-state bound for one or two runners."""

    definition = _coerce_definition(definition_value)
    if len(definition.initial_pieces) == 1:
        _validate_one_runner_family(definition, require_corner=True)
        return TWO_RUNNER_SOURCE_STATE_BOUND
    if len(definition.initial_pieces) == 2:
        _validate_two_runner_family(definition)
        arrangements = 36 * (2**7)
        bound = 15 * arrangements
        if bound != TWO_RUNNER_TREATMENT_STATE_BOUND:
            raise AssertionError("two-runner state proof drifted")
        return bound
    raise ValueError("state proof requires one or two runners")


def validate_two_runner_searched_states(
    value: Any, definition_value: Any
) -> int:
    """Reject bool and require a positive searched-state count within the proof."""

    bound = two_runner_state_upper_bound(definition_value)
    if type(value) is not int or not 1 <= value <= bound:
        raise ValueError("searched states must be an integer within the proved bound")
    return value


def _vector_band(vector_count: int) -> str:
    if 1 <= vector_count <= 3:
        return "v1_3"
    if vector_count == 4:
        return "v4"
    if vector_count == 5:
        return "v5"
    if 6 <= vector_count <= 7:
        return "v6_7"
    raise ValueError("two-runner strata require one to seven movement vectors")


def two_runner_stratum(source_value: Any) -> Dict[str, Any]:
    """Return the frozen three-field structural stratum."""

    source = _coerce_definition(source_value)
    _validate_one_runner_family(source, require_corner=True)
    role_a = source.role(Player.A)
    role_b = source.role(Player.B)
    assert role_b.goal.edge is not None
    return {
        "first_player": source.first_player.value,
        "goal_axis_relation": (
            "ALIGNED" if role_b.goal.edge in role_a.goal.edges else "ORTHOGONAL"
        ),
        "vector_band": _vector_band(len(role_b.action.vectors)),
    }


def _stratum_id(stratum: Mapping[str, Any]) -> str:
    top = _exact_keys(
        stratum,
        ("first_player", "goal_axis_relation", "vector_band"),
        "two-runner stratum",
    )
    if top["first_player"] not in ("A", "B"):
        raise ValueError("two-runner first-player stratum mismatch")
    if top["goal_axis_relation"] not in ("ALIGNED", "ORTHOGONAL"):
        raise ValueError("two-runner goal-axis stratum mismatch")
    if top["vector_band"] not in ("v1_3", "v4", "v5", "v6_7"):
        raise ValueError("two-runner vector-band stratum mismatch")
    return "f{}-{}-{}".format(
        top["first_player"],
        top["goal_axis_relation"].lower(),
        top["vector_band"],
    )


def _validated_artifact(value: Any, label: str) -> Dict[str, str]:
    top = _exact_keys(
        value,
        ("path", "sha256", "identity_kind", "identity"),
        label,
    )
    path = top["path"]
    if (
        not isinstance(path, str)
        or not path
        or path.startswith("/")
        or ".." in path.split("/")
    ):
        raise ValueError("{} path must be canonical and repository-relative".format(label))
    identity_kind = top["identity_kind"]
    identity = top["identity"]
    if not isinstance(identity_kind, str) or not identity_kind:
        raise ValueError("{} identity kind must be nonempty".format(label))
    if not isinstance(identity, str) or not identity:
        raise ValueError("{} identity must be nonempty".format(label))
    return {
        "path": path,
        "sha256": _require_sha256(top["sha256"], label + " SHA"),
        "identity_kind": identity_kind,
        "identity": identity,
    }


def _validated_artifacts(value: Any, label: str) -> Tuple[Dict[str, str], ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError("{} must be an array".format(label))
    artifacts = tuple(
        _validated_artifact(item, "{} entry".format(label)) for item in value
    )
    if [item["path"] for item in artifacts] != sorted(
        {item["path"] for item in artifacts}
    ):
        raise ValueError("{} paths must be unique and ordered".format(label))
    return artifacts


def _validate_plan0009_source_projection(
    value: Mapping[str, Any],
) -> Tuple[Dict[str, Any], ...]:
    records = validate_boundary_definition_projection(value)
    if len(records) != TWO_RUNNER_PLAN0009_SOURCE_D4_COUNT:
        raise ValueError("Plan-0009 source projection must contain exactly 64 records")
    observed: Set[str] = set()
    for record in records:
        definition = parse_definition(record["definition"])
        _validate_one_runner_family(definition, require_corner=False)
        if len(definition.role(Player.B).action.vectors) not in (3, 4):
            raise ValueError("Plan-0009 source projection requires vector count 3 or 4")
        if mechanical_json(definition) != canonicalize_d4(definition).mechanical_json:
            raise ValueError("Plan-0009 sources must use canonical D4 orientation")
        observed.add(record["d4_canonical_hash"])
    if len(observed) != TWO_RUNNER_PLAN0009_SOURCE_D4_COUNT:
        raise ValueError("Plan-0009 source D4 identities must be unique")
    return records


def build_two_runner_evaluated_orbit_projection(
    base_coverage_projection: Mapping[str, Any],
    plan0009_source_projection: Mapping[str, Any],
    dependency_artifacts: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Build the closed 439 + 64 evaluated schema-v1 orbit projection."""

    validate_boundary_coverage_projection(base_coverage_projection)
    plan_records = _validate_plan0009_source_projection(plan0009_source_projection)
    artifacts = _validated_artifacts(
        dependency_artifacts, "evaluated projection dependencies"
    )
    base_hashes = tuple(base_coverage_projection["covered_vocabulary_d4_hashes"])
    plan_hashes = tuple(
        sorted({record["d4_canonical_hash"] for record in plan_records})
    )
    if len(base_hashes) != TWO_RUNNER_BASE_EVALUATED_D4_COUNT:
        raise ValueError("base evaluated-orbit count mismatch")
    intersection = sorted(set(base_hashes) & set(plan_hashes))
    if intersection:
        raise ValueError("base coverage and Plan-0009 sources must be disjoint")
    evaluated = sorted(set(base_hashes) | set(plan_hashes))
    if len(evaluated) != TWO_RUNNER_EVALUATED_D4_COUNT:
        raise ValueError("closed evaluated-orbit count mismatch")
    projection = {
        "projection_version": 1,
        "dependency_artifacts": list(artifacts),
        "base_coverage_root": base_coverage_projection["coverage_root"],
        "base_d4_count": len(base_hashes),
        "base_d4_root": base_coverage_projection["covered_vocabulary_d4_root"],
        "plan0009_source_projection_root": plan0009_source_projection[
            "projection_root"
        ],
        "plan0009_source_d4_count": len(plan_hashes),
        "plan0009_source_d4_root": _domain_digest(
            _EVALUATED_D4_DOMAIN, list(plan_hashes)
        ),
        "intersection_count": len(intersection),
        "evaluated_d4_count": len(evaluated),
        "evaluated_d4_hashes": evaluated,
        "evaluated_d4_root": _domain_digest(_EVALUATED_D4_DOMAIN, evaluated),
    }
    projection["projection_root"] = _domain_digest(
        _EVALUATED_PROJECTION_DOMAIN, projection
    )
    validate_two_runner_evaluated_orbit_projection(projection)
    return _json_copy(projection, "two-runner evaluated projection")


def validate_two_runner_evaluated_orbit_projection(
    value: Any,
    base_coverage_projection: Mapping[str, Any] | None = None,
    plan0009_source_projection: Mapping[str, Any] | None = None,
    *,
    dependency_artifacts: Sequence[Mapping[str, Any]] | None = None,
) -> Tuple[str, ...]:
    """Validate the closed evaluated projection, optionally reconstructing it."""

    top = _exact_keys(
        value,
        (
            "projection_version",
            "dependency_artifacts",
            "base_coverage_root",
            "base_d4_count",
            "base_d4_root",
            "plan0009_source_projection_root",
            "plan0009_source_d4_count",
            "plan0009_source_d4_root",
            "intersection_count",
            "evaluated_d4_count",
            "evaluated_d4_hashes",
            "evaluated_d4_root",
            "projection_root",
        ),
        "two-runner evaluated projection",
    )
    _require_int(top["projection_version"], 1, "evaluated projection version")
    _validated_artifacts(top["dependency_artifacts"], "evaluated dependencies")
    _require_sha256(top["base_coverage_root"], "base coverage root")
    _require_int(
        top["base_d4_count"],
        TWO_RUNNER_BASE_EVALUATED_D4_COUNT,
        "base D4 count",
    )
    _require_sha256(top["base_d4_root"], "base D4 root")
    _require_sha256(
        top["plan0009_source_projection_root"], "Plan-0009 projection root"
    )
    _require_int(
        top["plan0009_source_d4_count"],
        TWO_RUNNER_PLAN0009_SOURCE_D4_COUNT,
        "Plan-0009 source D4 count",
    )
    _require_sha256(top["plan0009_source_d4_root"], "Plan-0009 source D4 root")
    _require_int(top["intersection_count"], 0, "evaluated intersection count")
    hashes = _require_sorted_hashes(
        top["evaluated_d4_hashes"], "evaluated D4 hashes"
    )
    _require_int(
        top["evaluated_d4_count"],
        TWO_RUNNER_EVALUATED_D4_COUNT,
        "evaluated D4 count",
    )
    if len(hashes) != TWO_RUNNER_EVALUATED_D4_COUNT:
        raise ValueError("evaluated D4 array count mismatch")
    if top["evaluated_d4_root"] != _domain_digest(
        _EVALUATED_D4_DOMAIN, list(hashes)
    ):
        raise ValueError("evaluated D4 root mismatch")
    unsigned = dict(top)
    projection_root = unsigned.pop("projection_root")
    if _require_sha256(projection_root, "evaluated projection root") != _domain_digest(
        _EVALUATED_PROJECTION_DOMAIN, unsigned
    ):
        raise ValueError("evaluated projection root mismatch")
    if (
        TWO_RUNNER_EVALUATED_PROJECTION_ROOT
        and projection_root != TWO_RUNNER_EVALUATED_PROJECTION_ROOT
    ):
        raise ValueError("evaluated projection differs from the frozen root")
    if (
        projection_root == TWO_RUNNER_EVALUATED_PROJECTION_ROOT
        and top["evaluated_d4_root"] != TWO_RUNNER_EVALUATED_D4_ROOT
    ):
        raise ValueError("evaluated D4 root differs from the frozen value")
    supplied = (base_coverage_projection, plan0009_source_projection)
    if any(item is None for item in supplied) and not all(item is None for item in supplied):
        raise ValueError("evaluated reconstruction requires both source projections")
    if all(item is not None for item in supplied):
        expected_dependencies = (
            dependency_artifacts
            if dependency_artifacts is not None
            else top["dependency_artifacts"]
        )
        expected = build_two_runner_evaluated_orbit_projection(
            base_coverage_projection,  # type: ignore[arg-type]
            plan0009_source_projection,  # type: ignore[arg-type]
            expected_dependencies,
        )
        if _canonical_bytes(top) != _canonical_bytes(expected):
            raise ValueError("evaluated projection does not match reconstruction")
    return hashes


def build_two_runner_historical_definition_projection(
    sources: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Union only strict definition projections from the closed history graph."""

    if not isinstance(sources, (list, tuple)) or not sources:
        raise ValueError("historical projection requires at least one source")
    records = []
    all_definition_hashes: Set[str] = set()
    all_d4_hashes: Set[str] = set()
    occurrence_count = 0
    for raw_source in sources:
        source = _exact_keys(
            raw_source,
            ("artifact", "definition_projection"),
            "historical projection source",
        )
        artifact = _validated_artifact(
            source["artifact"], "historical source artifact"
        )
        projected = validate_boundary_definition_projection(
            source["definition_projection"]
        )
        definition_hashes = sorted(
            {record["definition_hash"] for record in projected}
        )
        d4_hashes = sorted({record["d4_canonical_hash"] for record in projected})
        occurrence_count += len(projected)
        all_definition_hashes.update(definition_hashes)
        all_d4_hashes.update(d4_hashes)
        records.append(
            {
                "artifact": artifact,
                "definition_projection_root": source["definition_projection"][
                    "projection_root"
                ],
                "definition_occurrence_count": len(projected),
                "unique_definition_count": len(definition_hashes),
                "unique_d4_count": len(d4_hashes),
                "unique_d4_root": _domain_digest(
                    _HISTORICAL_SOURCE_D4_DOMAIN, d4_hashes
                ),
            }
        )
    records.sort(key=lambda record: record["artifact"]["path"])
    paths = [record["artifact"]["path"] for record in records]
    if paths != sorted(set(paths)):
        raise ValueError("historical projection source paths must be unique")
    d4_hashes = sorted(all_d4_hashes)
    projection = {
        "projection_version": 1,
        "source_count": len(records),
        "definition_occurrence_count": occurrence_count,
        "unique_definition_count": len(all_definition_hashes),
        "unique_d4_count": len(d4_hashes),
        "unique_d4_hashes": d4_hashes,
        "unique_d4_root": _domain_digest(_HISTORICAL_D4_DOMAIN, d4_hashes),
        "sources": records,
    }
    projection["projection_root"] = _domain_digest(
        _HISTORICAL_PROJECTION_DOMAIN, projection
    )
    validate_two_runner_historical_definition_projection(projection)
    return _json_copy(projection, "two-runner historical projection")


def validate_two_runner_historical_definition_projection(
    value: Any,
    sources: Sequence[Mapping[str, Any]] | None = None,
) -> Tuple[str, ...]:
    """Validate a definition-only historical union and optionally reconstruct it."""

    top = _exact_keys(
        value,
        (
            "projection_version",
            "source_count",
            "definition_occurrence_count",
            "unique_definition_count",
            "unique_d4_count",
            "unique_d4_hashes",
            "unique_d4_root",
            "sources",
            "projection_root",
        ),
        "two-runner historical projection",
    )
    _require_int(top["projection_version"], 1, "historical projection version")
    if not isinstance(top["sources"], list) or not top["sources"]:
        raise ValueError("historical projection sources must be a nonempty array")
    source_records = []
    paths = []
    occurrence_sum = 0
    for raw_record in top["sources"]:
        record = _exact_keys(
            raw_record,
            (
                "artifact",
                "definition_projection_root",
                "definition_occurrence_count",
                "unique_definition_count",
                "unique_d4_count",
                "unique_d4_root",
            ),
            "historical projection record",
        )
        artifact = _validated_artifact(
            record["artifact"], "historical projection artifact"
        )
        paths.append(artifact["path"])
        _require_sha256(
            record["definition_projection_root"], "definition projection root"
        )
        occurrence = _require_int(
            record["definition_occurrence_count"],
            None,
            "historical definition occurrence count",
        )
        unique_definition_count = _require_int(
            record["unique_definition_count"],
            None,
            "historical unique definition count",
        )
        unique_d4_count = _require_int(
            record["unique_d4_count"], None, "historical source D4 count"
        )
        if min(occurrence, unique_definition_count, unique_d4_count) < 0:
            raise ValueError("historical projection counts must be nonnegative")
        if unique_definition_count > occurrence or unique_d4_count > occurrence:
            raise ValueError("historical unique counts cannot exceed occurrences")
        _require_sha256(record["unique_d4_root"], "historical source D4 root")
        occurrence_sum += occurrence
        source_records.append(_json_copy(record, "historical projection record"))
    if paths != sorted(set(paths)):
        raise ValueError("historical projection records must be unique and ordered")
    _require_int(top["source_count"], len(source_records), "historical source count")
    _require_int(
        top["definition_occurrence_count"],
        occurrence_sum,
        "historical occurrence total",
    )
    unique_definition_count = _require_int(
        top["unique_definition_count"], None, "historical unique definition total"
    )
    if not 0 <= unique_definition_count <= occurrence_sum:
        raise ValueError("historical unique definition total is invalid")
    hashes = _require_sorted_hashes(
        top["unique_d4_hashes"], "historical D4 hashes"
    )
    _require_int(top["unique_d4_count"], len(hashes), "historical D4 count")
    if top["unique_d4_root"] != _domain_digest(
        _HISTORICAL_D4_DOMAIN, list(hashes)
    ):
        raise ValueError("historical D4 root mismatch")
    unsigned = dict(top)
    projection_root = unsigned.pop("projection_root")
    if _require_sha256(projection_root, "historical projection root") != _domain_digest(
        _HISTORICAL_PROJECTION_DOMAIN, unsigned
    ):
        raise ValueError("historical projection root mismatch")
    if (
        TWO_RUNNER_HISTORICAL_PROJECTION_ROOT
        and projection_root != TWO_RUNNER_HISTORICAL_PROJECTION_ROOT
    ):
        raise ValueError("historical projection differs from the frozen root")
    if projection_root == TWO_RUNNER_HISTORICAL_PROJECTION_ROOT:
        if top["unique_d4_root"] != TWO_RUNNER_HISTORICAL_D4_ROOT:
            raise ValueError("historical D4 root differs from the frozen value")
        _require_int(
            top["definition_occurrence_count"],
            TWO_RUNNER_HISTORICAL_DEFINITION_OCCURRENCE_COUNT,
            "frozen historical occurrence count",
        )
        _require_int(
            top["unique_definition_count"],
            TWO_RUNNER_HISTORICAL_UNIQUE_DEFINITION_COUNT,
            "frozen historical unique-definition count",
        )
        _require_int(
            top["unique_d4_count"],
            TWO_RUNNER_HISTORICAL_UNIQUE_D4_COUNT,
            "frozen historical unique-D4 count",
        )
    if sources is not None:
        expected = build_two_runner_historical_definition_projection(sources)
        if _canonical_bytes(top) != _canonical_bytes(expected):
            raise ValueError("historical projection does not match reconstruction")
    return hashes


def _validate_plan0009_full_projection(
    projection: Mapping[str, Any], pairs: Sequence[Mapping[str, Any]]
) -> None:
    records = validate_boundary_definition_projection(projection)
    if len(records) != TWO_RUNNER_PAIR_COUNT * 2:
        raise ValueError("Plan-0009 full projection must contain 128 definitions")
    by_path = {record["json_path"]: record for record in records}
    expected_paths = set()
    for index, pair in enumerate(pairs):
        for side in ("source", "treatment"):
            path = "/pairs/{}/{}_definition".format(index, side)
            expected_paths.add(path)
            record = by_path.get(path)
            if record is None:
                raise ValueError("Plan-0009 full projection omits a pair definition")
            if (
                record["definition_hash"] != pair[side + "_definition_hash"]
                or record["d4_canonical_hash"]
                != pair[side + "_d4_canonical_hash"]
                or _canonical_bytes(record["definition"])
                != _canonical_bytes(pair[side + "_definition"])
            ):
                raise ValueError("Plan-0009 full projection pair identity mismatch")
    if set(by_path) != expected_paths:
        raise ValueError("Plan-0009 full projection contains an unexpected definition")


def _project_static_corpus_supported_definitions(
    value: Mapping[str, Any],
) -> Dict[str, Any]:
    """Project the six valid static fixtures and attest the one invalid fixture."""

    top = _exact_keys(
        value,
        ("corpus_id", "frozen", "purpose", "cases"),
        "static corpus",
    )
    if top["corpus_id"] != "static-v1-2026-08-31" or top["frozen"] is not True:
        raise ValueError("static corpus identity or frozen marker mismatch")
    if not isinstance(top["purpose"], str) or not top["purpose"]:
        raise ValueError("static corpus purpose must be nonempty")
    expected_failures = {
        "healthy-crossing-seeds": [],
        "full-board-no-opening": ["NO_LEGAL_MOVE_AT_START"],
        "missing-runner": ["UNREACHABLE_WIN_CONDITION"],
        "initial-connection": ["TRIVIAL_FORCED_RESULT"],
        "same-action-roles": ["TOO_SYMMETRIC"],
        "over-parameterized-movement": ["TOO_COMPLEX"],
        "invalid-board-size": ["INVALID_DEFINITION"],
    }
    if not isinstance(top["cases"], list) or len(top["cases"]) != len(
        expected_failures
    ):
        raise ValueError("static corpus case census mismatch")
    valid_definitions = []
    observed_ids = []
    for raw_case in top["cases"]:
        case = _exact_keys(
            raw_case,
            ("id", "expected_failures", "definition"),
            "static corpus case",
        )
        case_id = case["id"]
        if not isinstance(case_id, str) or case_id not in expected_failures:
            raise ValueError("static corpus case identity mismatch")
        observed_ids.append(case_id)
        if _canonical_bytes(case["expected_failures"]) != _canonical_bytes(
            expected_failures[case_id]
        ):
            raise ValueError("static corpus expected-failure contract mismatch")
        if case_id == "invalid-board-size":
            try:
                parse_definition(case["definition"])
            except DefinitionError:
                continue
            raise ValueError("static invalid-board fixture unexpectedly parsed")
        valid_definitions.append(parse_definition(case["definition"]).to_dict())
    if observed_ids != list(expected_failures):
        raise ValueError("static corpus cases must retain frozen order")
    projection = project_boundary_definitions(valid_definitions)
    records = validate_boundary_definition_projection(projection)
    if len(records) != 6 or len(
        {record["d4_canonical_hash"] for record in records}
    ) != 6:
        raise ValueError("static corpus valid-definition projection census mismatch")
    return projection


def build_two_runner_closed_projection_bundle(
    source_records: Sequence[Mapping[str, Any]],
    source_metadata: Sequence[Mapping[str, Any]],
    supporting_dependency_records: Sequence[Mapping[str, Any]],
    supporting_dependency_metadata: Sequence[Mapping[str, Any]],
    coverage_records: Sequence[Mapping[str, Any]],
    coverage_registry: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    plan0009_manifest: Mapping[str, Any],
) -> Dict[str, Any]:
    """Authenticate the fixed old graph and derive both Plan-0010 projections.

    This is the sole full-record adapter.  The inherited Plan-0009 closed-world
    validator authenticates the sixteen run records and four dependency artifacts.
    The frozen Plan-0009 manifest is then publicly reconstructed before its 64
    source definitions are extracted.  Only strict definition/identity projections
    cross into the selectors above.
    """

    base_bundle = project_boundary_exclusion_sources(
        source_records,
        source_metadata,
        supporting_dependency_records,
        supporting_dependency_metadata,
        coverage_records,
        coverage_registry,
    )
    coverage = base_bundle["coverage_projection"]
    exclusion_ledger = base_bundle["exclusion_ledger"]
    validate_boundary_coverage_projection(coverage)
    validate_boundary_exclusion_ledger(exclusion_ledger)

    if (
        hashlib.sha256(_repository_json_bytes(plan0009_manifest)).hexdigest()
        != TWO_RUNNER_PLAN0009_MANIFEST_ARTIFACT["sha256"]
        or plan0009_manifest.get("manifest_id") != CAPTURE_BOUNDARY_MANIFEST_ID
        or plan0009_manifest.get("protocol_id")
        != CAPTURE_BOUNDARY_MANIFEST_PROTOCOL_ID
        or plan0009_manifest.get("status") != "FROZEN"
    ):
        raise ValueError("Plan-0009 manifest bytes, identity, or status mismatch")
    if (
        not isinstance(supporting_dependency_records, (list, tuple))
        or len(supporting_dependency_records) != 3
    ):
        raise ValueError("closed projection requires three supporting dependencies")
    plan0008_manifest = supporting_dependency_records[2]
    pairs = validate_capture_boundary_manifest(
        plan0009_manifest,
        exclusion_ledger,
        coverage,
        plan0008_manifest,
    )
    if len(pairs) != TWO_RUNNER_PLAN0009_SOURCE_D4_COUNT:
        raise ValueError("Plan-0009 validated pair count mismatch")
    plan0009_source_projection = project_boundary_definitions(
        [pair["source_definition"] for pair in pairs]
    )
    _validate_plan0009_source_projection(plan0009_source_projection)
    plan0009_full_projection = project_boundary_definitions(plan0009_manifest)
    _validate_plan0009_full_projection(plan0009_full_projection, pairs)

    evaluated_dependencies = sorted(
        (
            dict(TWO_RUNNER_PLAN0009_LEDGER_ARTIFACT),
            dict(TWO_RUNNER_PLAN0009_MANIFEST_ARTIFACT),
        ),
        key=lambda artifact: artifact["path"],
    )
    evaluated = build_two_runner_evaluated_orbit_projection(
        coverage,
        plan0009_source_projection,
        evaluated_dependencies,
    )

    if not isinstance(coverage_records, (list, tuple)) or len(coverage_records) != 16:
        raise ValueError("closed history requires exactly sixteen run records")
    coverage_sources = []
    for record, coverage_record in zip(coverage_records, coverage["records"]):
        artifact = {
            "path": coverage_record["path"],
            "sha256": coverage_record["sha256"],
            "identity_kind": "run_id",
            "identity": coverage_record["path"].split("/")[-2],
        }
        coverage_sources.append(
            {
                "artifact": artifact,
                "definition_projection": project_boundary_definitions(record),
            }
        )

    if (
        not isinstance(supporting_dependency_metadata, (list, tuple))
        or len(supporting_dependency_metadata) != 3
        or not isinstance(source_records, (list, tuple))
        or len(source_records) != 4
    ):
        raise ValueError("closed history dependency cardinality mismatch")
    supporting_sources = []
    for record, metadata in zip(
        supporting_dependency_records, supporting_dependency_metadata
    ):
        artifact = _validated_artifact(metadata, "closed supporting artifact")
        # The pinned static corpus contains six valid DSL definitions plus one
        # deliberate invalid-board-size fixture.  Authenticate the latter's
        # expected failure while retaining every valid definition in full history.
        definition_projection = (
            _project_static_corpus_supported_definitions(record)
            if artifact["path"] == "experiments/corpora/static-v1/corpus.json"
            else project_boundary_definitions(record)
        )
        supporting_sources.append(
            {
                "artifact": artifact,
                "definition_projection": definition_projection,
            }
        )
    landscape_source = {
        "artifact": {
            "path": CAPTURE_BOUNDARY_LANDSCAPE_SOURCE[0],
            "sha256": CAPTURE_BOUNDARY_LANDSCAPE_SOURCE[1],
            "identity_kind": "manifest_id",
            "identity": "generator-v2-3x3-landscape-v1",
        },
        "definition_projection": project_boundary_definitions(source_records[3]),
    }
    plan0009_source = {
        "artifact": dict(TWO_RUNNER_PLAN0009_MANIFEST_ARTIFACT),
        "definition_projection": plan0009_full_projection,
    }
    historical_sources = sorted(
        coverage_sources
        + supporting_sources
        + [landscape_source, plan0009_source],
        key=lambda source: source["artifact"]["path"],
    )
    if len(historical_sources) != TWO_RUNNER_HISTORICAL_ARTIFACT_COUNT:
        raise AssertionError("closed historical artifact count drifted")
    historical = build_two_runner_historical_definition_projection(
        historical_sources
    )
    if not set(evaluated["evaluated_d4_hashes"]) <= set(
        historical["unique_d4_hashes"]
    ):
        raise ValueError("closed full history omits an evaluated source orbit")

    historical_paths = [
        record["artifact"]["path"] for record in historical["sources"]
    ]
    bundle = {
        "bundle_version": 1,
        "base_coverage_root": coverage["coverage_root"],
        "base_exclusion_ledger_root": exclusion_ledger["ledger_root"],
        "plan0009_manifest_artifact": dict(
            TWO_RUNNER_PLAN0009_MANIFEST_ARTIFACT
        ),
        "plan0009_source_projection_root": plan0009_source_projection[
            "projection_root"
        ],
        "plan0009_full_definition_projection_root": plan0009_full_projection[
            "projection_root"
        ],
        "historical_artifact_count": len(historical_paths),
        "historical_artifact_paths": historical_paths,
        "evaluated_orbit_projection": evaluated,
        "historical_definition_projection": historical,
    }
    bundle["bundle_root"] = _domain_digest(
        _CLOSED_PROJECTION_BUNDLE_DOMAIN, bundle
    )
    validate_two_runner_closed_projection_bundle(bundle)
    return _json_copy(bundle, "two-runner closed projection bundle")


def validate_two_runner_closed_projection_bundle(
    value: Any,
    source_records: Sequence[Mapping[str, Any]] | None = None,
    source_metadata: Sequence[Mapping[str, Any]] | None = None,
    supporting_dependency_records: Sequence[Mapping[str, Any]] | None = None,
    supporting_dependency_metadata: Sequence[Mapping[str, Any]] | None = None,
    coverage_records: Sequence[Mapping[str, Any]] | None = None,
    coverage_registry: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
    plan0009_manifest: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Validate and optionally reconstruct the fixed closed projection bundle."""

    top = _exact_keys(
        value,
        (
            "bundle_version",
            "base_coverage_root",
            "base_exclusion_ledger_root",
            "plan0009_manifest_artifact",
            "plan0009_source_projection_root",
            "plan0009_full_definition_projection_root",
            "historical_artifact_count",
            "historical_artifact_paths",
            "evaluated_orbit_projection",
            "historical_definition_projection",
            "bundle_root",
        ),
        "two-runner closed projection bundle",
    )
    _require_int(top["bundle_version"], 1, "closed bundle version")
    _require_sha256(top["base_coverage_root"], "closed base coverage root")
    _require_sha256(
        top["base_exclusion_ledger_root"], "closed exclusion ledger root"
    )
    if _canonical_bytes(top["plan0009_manifest_artifact"]) != _canonical_bytes(
        TWO_RUNNER_PLAN0009_MANIFEST_ARTIFACT
    ):
        raise ValueError("closed bundle Plan-0009 artifact mismatch")
    _require_sha256(
        top["plan0009_source_projection_root"],
        "closed Plan-0009 source projection root",
    )
    _require_sha256(
        top["plan0009_full_definition_projection_root"],
        "closed Plan-0009 full projection root",
    )
    if (
        top["plan0009_source_projection_root"]
        != TWO_RUNNER_PLAN0009_SOURCE_PROJECTION_ROOT
        or top["plan0009_full_definition_projection_root"]
        != TWO_RUNNER_PLAN0009_FULL_PROJECTION_ROOT
    ):
        raise ValueError("closed Plan-0009 projection roots differ from frozen values")
    _require_int(
        top["historical_artifact_count"],
        TWO_RUNNER_HISTORICAL_ARTIFACT_COUNT,
        "closed historical artifact count",
    )
    if not isinstance(top["historical_artifact_paths"], list):
        raise ValueError("closed historical artifact paths must be an array")
    paths = top["historical_artifact_paths"]
    if (
        len(paths) != TWO_RUNNER_HISTORICAL_ARTIFACT_COUNT
        or paths != sorted(set(paths))
        or any(not isinstance(path, str) for path in paths)
    ):
        raise ValueError("closed historical artifact paths mismatch")
    evaluated_hashes = validate_two_runner_evaluated_orbit_projection(
        top["evaluated_orbit_projection"]
    )
    historical_hashes = validate_two_runner_historical_definition_projection(
        top["historical_definition_projection"]
    )
    static_records = [
        record
        for record in top["historical_definition_projection"]["sources"]
        if record["artifact"]["path"]
        == "experiments/corpora/static-v1/corpus.json"
    ]
    if len(static_records) != 1:
        raise ValueError("closed history must contain the static corpus exactly once")
    static_record = static_records[0]
    for field in (
        "definition_occurrence_count",
        "unique_definition_count",
        "unique_d4_count",
    ):
        _require_int(
            static_record[field],
            TWO_RUNNER_STATIC_DEFINITION_COUNT,
            "closed static corpus {}".format(field),
        )
    if (
        static_record["definition_projection_root"]
        != TWO_RUNNER_STATIC_DEFINITION_PROJECTION_ROOT
        or static_record["unique_d4_root"] != TWO_RUNNER_STATIC_D4_ROOT
    ):
        raise ValueError("closed static corpus projection differs from frozen values")
    if top["base_coverage_root"] != top["evaluated_orbit_projection"][
        "base_coverage_root"
    ]:
        raise ValueError("closed bundle base coverage reference mismatch")
    if top["plan0009_source_projection_root"] != top[
        "evaluated_orbit_projection"
    ]["plan0009_source_projection_root"]:
        raise ValueError("closed bundle Plan-0009 source reference mismatch")
    if paths != [
        record["artifact"]["path"]
        for record in top["historical_definition_projection"]["sources"]
    ]:
        raise ValueError("closed historical path projection mismatch")
    if TWO_RUNNER_PLAN0009_MANIFEST_ARTIFACT["path"] not in paths:
        raise ValueError("closed history omits the Plan-0009 manifest")
    if not set(evaluated_hashes) <= set(historical_hashes):
        raise ValueError("closed history omits an evaluated D4 identity")
    dependencies = top["evaluated_orbit_projection"]["dependency_artifacts"]
    expected_dependencies = sorted(
        (
            dict(TWO_RUNNER_PLAN0009_LEDGER_ARTIFACT),
            dict(TWO_RUNNER_PLAN0009_MANIFEST_ARTIFACT),
        ),
        key=lambda artifact: artifact["path"],
    )
    if _canonical_bytes(dependencies) != _canonical_bytes(expected_dependencies):
        raise ValueError("closed evaluated dependencies mismatch")
    unsigned = dict(top)
    bundle_root = unsigned.pop("bundle_root")
    if _require_sha256(bundle_root, "closed bundle root") != _domain_digest(
        _CLOSED_PROJECTION_BUNDLE_DOMAIN, unsigned
    ):
        raise ValueError("closed projection bundle root mismatch")
    if (
        TWO_RUNNER_CLOSED_PROJECTION_BUNDLE_ROOT
        and bundle_root != TWO_RUNNER_CLOSED_PROJECTION_BUNDLE_ROOT
    ):
        raise ValueError("closed projection bundle differs from the frozen root")

    reconstruction = (
        source_records,
        source_metadata,
        supporting_dependency_records,
        supporting_dependency_metadata,
        coverage_records,
        coverage_registry,
        plan0009_manifest,
    )
    if any(item is None for item in reconstruction) and not all(
        item is None for item in reconstruction
    ):
        raise ValueError("closed bundle reconstruction requires every raw input")
    if all(item is not None for item in reconstruction):
        expected = build_two_runner_closed_projection_bundle(
            source_records,  # type: ignore[arg-type]
            source_metadata,  # type: ignore[arg-type]
            supporting_dependency_records,  # type: ignore[arg-type]
            supporting_dependency_metadata,  # type: ignore[arg-type]
            coverage_records,  # type: ignore[arg-type]
            coverage_registry,  # type: ignore[arg-type]
            plan0009_manifest,  # type: ignore[arg-type]
        )
        if _canonical_bytes(top) != _canonical_bytes(expected):
            raise ValueError("closed projection bundle does not match reconstruction")
    return {
        "evaluated_orbit_projection": _json_copy(
            top["evaluated_orbit_projection"], "closed evaluated projection"
        ),
        "historical_definition_projection": _json_copy(
            top["historical_definition_projection"],
            "closed historical projection",
        ),
    }


def _passes_gates(definition: GameDefinition) -> bool:
    return (
        analyze_definition(definition).passes
        and evaluate_asymmetry(definition).qualifies
        and not exceeds_limits(evaluate_simplicity(definition))
    )


def _selection_score(
    source_d4_hash: str,
    treatment_d4_hash: str,
    stratum: Mapping[str, Any],
) -> str:
    return _domain_digest(
        _SELECTION_SCORE_DOMAIN,
        {
            "source_d4_canonical_hash": source_d4_hash,
            "treatment_d4_canonical_hash": treatment_d4_hash,
            "stratum": stratum,
        },
    )


def _pair_fingerprint(pair: Mapping[str, Any]) -> str:
    payload = dict(pair)
    payload.pop("pair_fingerprint", None)
    return _domain_digest(_PAIR_FINGERPRINT_DOMAIN, payload)


@lru_cache(maxsize=4)
def _selection_snapshot_json(
    excluded_hashes: Tuple[str, ...], historical_hashes: Tuple[str, ...]
) -> str:
    excluded = set(excluded_hashes)
    historical = set(historical_hashes)
    if not excluded <= historical:
        raise ValueError(
            "full historical projection must contain every evaluated source orbit"
        )
    relevant = []
    remaining = []
    paired_valid = []
    source_fail_treatment_pass = 0
    source_pass_treatment_fail = 0
    both_fail = 0
    d4_equivariance_checks = 0
    for source_d4_hash, source in _canonical_orbit_representatives():
        try:
            _validate_one_runner_family(source, require_corner=True)
        except ValueError:
            continue
        validate_two_runner_d4_equivariance(source)
        d4_equivariance_checks += len(D4_TRANSFORMS)
        relevant.append(source_d4_hash)
        if source_d4_hash in excluded:
            continue
        remaining.append(source_d4_hash)
        treatment = derive_two_runner_treatment(source)
        source_passes = _passes_gates(source)
        treatment_passes = _passes_gates(treatment)
        if source_passes and not treatment_passes:
            source_pass_treatment_fail += 1
        elif treatment_passes and not source_passes:
            source_fail_treatment_pass += 1
        elif not source_passes and not treatment_passes:
            both_fail += 1
        if not (source_passes and treatment_passes):
            continue
        stratum = two_runner_stratum(source)
        paired_valid.append(
            (
                source_d4_hash,
                d4_canonical_hash(treatment),
                source,
                treatment,
                stratum,
            )
        )

    if len(relevant) != TWO_RUNNER_RELEVANT_D4_COUNT:
        raise ValueError("relevant source-orbit census mismatch")
    if d4_equivariance_checks != TWO_RUNNER_D4_EQUIVARIANCE_CHECK_COUNT:
        raise ValueError("D4 equivariance proof census mismatch")
    relevant_excluded = set(relevant) & excluded
    unexpected_historical_sources = (set(relevant) & historical) - excluded
    if unexpected_historical_sources:
        raise ValueError(
            "full historical projection contains a relevant source absent from "
            "the evaluated-orbit projection"
        )
    if len(relevant_excluded) != TWO_RUNNER_RELEVANT_EXCLUDED_D4_COUNT:
        raise ValueError("relevant exclusion census mismatch")
    if len(remaining) != TWO_RUNNER_UNUSED_RELEVANT_D4_COUNT:
        raise ValueError("unused relevant source-orbit census mismatch")
    if len(paired_valid) != TWO_RUNNER_GATE_VALID_D4_COUNT:
        raise ValueError("paired gate-valid census mismatch")
    if (
        source_fail_treatment_pass + source_pass_treatment_fail
        != TWO_RUNNER_GATE_DISAGREEMENT_COUNT
        or source_fail_treatment_pass != TWO_RUNNER_GATE_DISAGREEMENT_COUNT
        or source_pass_treatment_fail != 0
        or both_fail != 110
    ):
        raise ValueError("source/treatment gate-disagreement census mismatch")

    by_treatment: Dict[
        str,
        list[
            Tuple[
                str,
                str,
                GameDefinition,
                GameDefinition,
                Dict[str, Any],
            ]
        ],
    ] = defaultdict(list)
    for candidate in paired_valid:
        by_treatment[candidate[1]].append(candidate)
    if len(by_treatment) != TWO_RUNNER_TREATMENT_UNIQUE_D4_COUNT:
        raise ValueError("treatment-unique census mismatch")
    size_counts = defaultdict(int)
    for candidates in by_treatment.values():
        size_counts[len(candidates)] += 1
    if dict(size_counts) != {
        1: TWO_RUNNER_TREATMENT_SINGLETON_COUNT,
        2: TWO_RUNNER_TREATMENT_DOUBLE_COUNT,
    }:
        raise ValueError("treatment collision multiplicity census mismatch")

    representative_choices = []
    representatives = []
    for treatment_d4_hash in sorted(by_treatment):
        candidates = sorted(by_treatment[treatment_d4_hash], key=lambda item: item[0])
        stratum_ids = {_stratum_id(candidate[4]) for candidate in candidates}
        if len(stratum_ids) != 1:
            raise ValueError("treatment collision group crosses structural strata")
        selected = candidates[0]
        representative_choices.append(
            {
                "treatment_d4_canonical_hash": treatment_d4_hash,
                "eligible_source_d4_canonical_hashes": [
                    candidate[0] for candidate in candidates
                ],
                "selected_source_d4_canonical_hash": selected[0],
            }
        )
        representatives.append(selected)

    collisions = []
    for source_d4, treatment_d4, _, _, _ in representatives:
        if source_d4 in historical or treatment_d4 in historical:
            collisions.append((source_d4, treatment_d4))
    if collisions:
        raise ValueError(
            "fresh representative source/treatment collides with historical definitions"
        )

    by_stratum: Dict[
        str,
        list[
            Tuple[
                str,
                str,
                str,
                GameDefinition,
                GameDefinition,
                Dict[str, Any],
            ]
        ],
    ] = defaultdict(list)
    for source_d4, treatment_d4, source, treatment, stratum in representatives:
        score = _selection_score(source_d4, treatment_d4, stratum)
        by_stratum[_stratum_id(stratum)].append(
            (score, source_d4, treatment_d4, source, treatment, stratum)
        )
    for candidates in by_stratum.values():
        candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    observed_counts = {
        stratum_id: len(candidates)
        for stratum_id, candidates in sorted(by_stratum.items())
    }
    if observed_counts != _EXPECTED_STRATUM_COUNTS:
        raise ValueError("eligible per-stratum census mismatch")

    eligible_pool_payload = []
    eligible_pools = []
    pairs = []
    selected_fingerprint_payload = []
    for stratum_id in sorted(by_stratum):
        candidates = by_stratum[stratum_id]
        stratum = _json_copy(candidates[0][5], "eligible stratum")
        ordered_identities = [
            {
                "selection_score": candidate[0],
                "source_d4_canonical_hash": candidate[1],
                "treatment_d4_canonical_hash": candidate[2],
            }
            for candidate in candidates
        ]
        pool_root = _domain_digest(_ELIGIBLE_POOL_DOMAIN, ordered_identities)
        selected_pair_ids = []
        for rank, candidate in enumerate(candidates[:TWO_RUNNER_QUOTA_PER_STRATUM]):
            score, source_d4, treatment_d4, source, treatment, pair_stratum = candidate
            if mechanical_json(source) != canonicalize_d4(source).mechanical_json:
                raise ValueError("selected source is not in canonical D4 orientation")
            validate_two_runner_pair(source, treatment)
            two_runner_state_upper_bound(source)
            two_runner_state_upper_bound(treatment)
            index = len(pairs) + 1
            pair_id = "two-runner-v1-pair-{:03d}".format(index)
            pair = {
                "pair_id": pair_id,
                "source_case_id": "two-runner-v1-source-{:03d}".format(index),
                "stratum_id": stratum_id,
                "stratum": _json_copy(pair_stratum, "pair stratum"),
                "selection_rank": rank,
                "selection_score": score,
                "source_definition_hash": definition_hash(source),
                "source_d4_canonical_hash": source_d4,
                "source_definition": source.to_dict(),
                "treatment_definition_hash": definition_hash(treatment),
                "treatment_d4_canonical_hash": treatment_d4,
                "treatment_definition": treatment.to_dict(),
                "added_runner_position": list(two_runner_added_position(source)),
                "piece_multiplicity_delta": 1,
            }
            pair["pair_fingerprint"] = _pair_fingerprint(pair)
            pairs.append(pair)
            selected_pair_ids.append(pair_id)
            selected_fingerprint_payload.append(
                {
                    "stratum_id": stratum_id,
                    "source_d4_canonical_hash": source_d4,
                    "treatment_d4_canonical_hash": treatment_d4,
                }
            )
        eligible_pool_payload.append(
            {
                "stratum_id": stratum_id,
                "stratum": stratum,
                "ordered_pair_identities": ordered_identities,
            }
        )
        eligible_pools.append(
            {
                "stratum_id": stratum_id,
                "stratum": stratum,
                "eligible_count": len(candidates),
                "ordered_pair_root": pool_root,
                "quota": TWO_RUNNER_QUOTA_PER_STRATUM,
                "selected_pair_ids": selected_pair_ids,
            }
        )
    if len(pairs) != TWO_RUNNER_PAIR_COUNT:
        raise ValueError("selected pair census mismatch")

    snapshot = {
        "census": {
            "raw_definition_count": RAW_DEFINITION_COUNT,
            "raw_d4_orbit_count": RAW_D4_ORBIT_COUNT,
            "evaluated_source_d4_count": len(excluded_hashes),
            "relevant_source_d4_count": len(relevant),
            "relevant_excluded_source_d4_count": len(relevant_excluded),
            "unused_relevant_source_d4_count": len(remaining),
            "paired_gate_valid_d4_count": len(paired_valid),
            "source_treatment_gate_disagreement_count": (
                source_fail_treatment_pass + source_pass_treatment_fail
            ),
            "source_fail_treatment_pass_count": source_fail_treatment_pass,
            "source_pass_treatment_fail_count": source_pass_treatment_fail,
            "both_gate_fail_count": both_fail,
            "treatment_unique_d4_count": len(representatives),
            "treatment_singleton_count": size_counts[1],
            "treatment_double_count": size_counts[2],
            "stratum_count": len(by_stratum),
            "minimum_eligible_stratum_count": min(observed_counts.values()),
            "maximum_eligible_stratum_count": max(observed_counts.values()),
            "quota_per_stratum": TWO_RUNNER_QUOTA_PER_STRATUM,
            "pair_count": len(pairs),
            "historical_collision_count": 0,
            "d4_equivariance_check_count": d4_equivariance_checks,
        },
        "relevant_source_d4_root": _domain_digest(
            _RELEVANT_D4_DOMAIN, sorted(relevant)
        ),
        "representative_choice_count": len(representative_choices),
        "representative_choice_root": _domain_digest(
            _REPRESENTATIVE_CHOICE_DOMAIN, representative_choices
        ),
        "representative_choices": representative_choices,
        "eligible_pool_root": _domain_digest(
            _ELIGIBLE_POOLS_DOMAIN, eligible_pool_payload
        ),
        "selection_fingerprint": _domain_digest(
            _SELECTION_FINGERPRINT_DOMAIN, selected_fingerprint_payload
        ),
        "eligible_pools": eligible_pools,
        "pairs": pairs,
    }
    return _canonical_bytes(snapshot).decode("utf-8")


def build_two_runner_planning_snapshot(
    evaluated_orbit_projection: Mapping[str, Any],
    historical_definition_projection: Mapping[str, Any],
) -> Dict[str, Any]:
    """Reproduce the complete outcome-free census and deterministic selection."""

    excluded = validate_two_runner_evaluated_orbit_projection(
        evaluated_orbit_projection
    )
    historical = validate_two_runner_historical_definition_projection(
        historical_definition_projection
    )
    snapshot = json.loads(_selection_snapshot_json(excluded, historical))
    frozen_roots = (
        (
            "relevant source D4 root",
            TWO_RUNNER_RELEVANT_D4_ROOT,
            snapshot["relevant_source_d4_root"],
        ),
        (
            "representative-choice root",
            TWO_RUNNER_REPRESENTATIVE_CHOICE_ROOT,
            snapshot["representative_choice_root"],
        ),
        (
            "eligible-pool root",
            TWO_RUNNER_ELIGIBLE_POOL_ROOT,
            snapshot["eligible_pool_root"],
        ),
        (
            "selection fingerprint",
            TWO_RUNNER_SELECTION_FINGERPRINT,
            snapshot["selection_fingerprint"],
        ),
    )
    for label, frozen, observed in frozen_roots:
        if frozen and observed != frozen:
            raise ValueError("{} differs from the frozen value".format(label))
    if _contains_forbidden_selection_key(snapshot):
        raise AssertionError("two-runner planning snapshot exposed outcome/timing data")
    return snapshot


def _require_frozen_manifest_roots(
    evaluated_orbit_projection: Mapping[str, Any],
    historical_definition_projection: Mapping[str, Any],
    snapshot: Mapping[str, Any],
) -> None:
    bindings = (
        (
            "evaluated projection root",
            TWO_RUNNER_EVALUATED_PROJECTION_ROOT,
            evaluated_orbit_projection["projection_root"],
        ),
        (
            "historical projection root",
            TWO_RUNNER_HISTORICAL_PROJECTION_ROOT,
            historical_definition_projection["projection_root"],
        ),
        (
            "relevant source D4 root",
            TWO_RUNNER_RELEVANT_D4_ROOT,
            snapshot["relevant_source_d4_root"],
        ),
        (
            "representative-choice root",
            TWO_RUNNER_REPRESENTATIVE_CHOICE_ROOT,
            snapshot["representative_choice_root"],
        ),
        (
            "eligible-pool root",
            TWO_RUNNER_ELIGIBLE_POOL_ROOT,
            snapshot["eligible_pool_root"],
        ),
        (
            "selection fingerprint",
            TWO_RUNNER_SELECTION_FINGERPRINT,
            snapshot["selection_fingerprint"],
        ),
    )
    for label, frozen, observed in bindings:
        if not frozen:
            raise ValueError(
                "production manifest is disabled until {} is frozen".format(label)
            )
        _require_sha256(frozen, "frozen " + label)
        if observed != frozen:
            raise ValueError("{} differs from the frozen value".format(label))


def _construct_two_runner_manifest(
    evaluated_orbit_projection: Mapping[str, Any],
    historical_definition_projection: Mapping[str, Any],
    provenance: Any,
) -> Dict[str, Any]:
    snapshot = build_two_runner_planning_snapshot(
        evaluated_orbit_projection, historical_definition_projection
    )
    _require_frozen_manifest_roots(
        evaluated_orbit_projection, historical_definition_projection, snapshot
    )
    provenance_copy = _validated_manifest_provenance(provenance)
    if _contains_forbidden_selection_key(provenance_copy):
        raise ValueError("two-runner provenance must be outcome- and timing-free")
    manifest = {
        "manifest_version": TWO_RUNNER_MANIFEST_VERSION,
        "manifest_id": TWO_RUNNER_MANIFEST_ID,
        "protocol_id": TWO_RUNNER_MANIFEST_PROTOCOL_ID,
        "status": "FROZEN",
        "source": {
            "closed_projection_bundle_root": TWO_RUNNER_CLOSED_PROJECTION_BUNDLE_ROOT,
            "evaluated_orbit_projection_root": evaluated_orbit_projection[
                "projection_root"
            ],
            "historical_definition_projection_root": historical_definition_projection[
                "projection_root"
            ],
        },
        "selection_protocol": {
            "membership": (
                "four lowest domain-separated identity scores per ordered stratum "
                "after treatment-D4 representative selection"
            ),
            "representative_choice": (
                "lexically smallest source D4 hash within each paired-valid "
                "treatment D4 orbit"
            ),
            "representative_choice_root": snapshot[
                "representative_choice_root"
            ],
            "eligible_pool_root": snapshot["eligible_pool_root"],
            "selection_fingerprint": snapshot["selection_fingerprint"],
            "source_orientation": "canonical D4 mechanical orientation",
            "treatment_orientation": "same stored frame as source; never independently canonicalized",
            "case_membership_outcome_fields_consulted": False,
            "treatment_outcomes_computed": False,
        },
        "state_bound": {
            "source_maximum_states": TWO_RUNNER_SOURCE_STATE_BOUND,
            "treatment_board_arrangements_per_ply": 4_608,
            "treatment_ply_layers": 15,
            "treatment_maximum_states": TWO_RUNNER_TREATMENT_STATE_BOUND,
            "exact_execution_cap": TWO_RUNNER_EXACT_MAX_STATES,
            "source_natural_terminal_ply": {"A": 15, "B": 16},
            "treatment_natural_terminal_ply": {"A": 13, "B": 14},
        },
        "census": snapshot["census"],
        "eligible_pools": snapshot["eligible_pools"],
        "provenance": provenance_copy,
        "pairs": snapshot["pairs"],
    }
    return _json_copy(manifest, "two-runner manifest")


def build_two_runner_manifest(
    evaluated_orbit_projection: Mapping[str, Any],
    historical_definition_projection: Mapping[str, Any],
    provenance: Any,
) -> Dict[str, Any]:
    """Build a deterministic four-per-stratum outcome-free manifest."""

    manifest = _construct_two_runner_manifest(
        evaluated_orbit_projection,
        historical_definition_projection,
        provenance,
    )
    validate_two_runner_manifest(
        manifest,
        evaluated_orbit_projection,
        historical_definition_projection,
    )
    return manifest


def validate_two_runner_manifest(
    manifest: Any,
    evaluated_orbit_projection: Mapping[str, Any],
    historical_definition_projection: Mapping[str, Any],
) -> Tuple[Dict[str, Any], ...]:
    """Publicly reconstruct membership and return detached ordered pairs."""

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
            "eligible_pools",
            "provenance",
            "pairs",
        ),
        "two-runner manifest",
    )
    _require_int(
        top["manifest_version"], TWO_RUNNER_MANIFEST_VERSION, "manifest version"
    )
    if (
        top["manifest_id"] != TWO_RUNNER_MANIFEST_ID
        or top["protocol_id"] != TWO_RUNNER_MANIFEST_PROTOCOL_ID
        or top["status"] != "FROZEN"
    ):
        raise ValueError("two-runner manifest identity or status mismatch")
    expected = _construct_two_runner_manifest(
        evaluated_orbit_projection,
        historical_definition_projection,
        top["provenance"],
    )
    if _canonical_bytes(top) != _canonical_bytes(expected):
        raise ValueError("two-runner manifest does not match public reconstruction")
    return tuple(_json_copy(pair, "two-runner pair") for pair in top["pairs"])


__all__ = (
    "TWO_RUNNER_MANIFEST_ID",
    "TWO_RUNNER_MANIFEST_PROTOCOL_ID",
    "TWO_RUNNER_PAIR_COUNT",
    "TWO_RUNNER_STRATUM_COUNT",
    "TWO_RUNNER_QUOTA_PER_STRATUM",
    "TWO_RUNNER_EVALUATED_D4_COUNT",
    "TWO_RUNNER_RELEVANT_D4_COUNT",
    "TWO_RUNNER_UNUSED_RELEVANT_D4_COUNT",
    "TWO_RUNNER_GATE_VALID_D4_COUNT",
    "TWO_RUNNER_TREATMENT_UNIQUE_D4_COUNT",
    "TWO_RUNNER_SOURCE_STATE_BOUND",
    "TWO_RUNNER_TREATMENT_STATE_BOUND",
    "TWO_RUNNER_EXECUTABLE_FINGERPRINT_PATHS",
    "TWO_RUNNER_PLAN0009_MANIFEST_ARTIFACT",
    "TWO_RUNNER_PLAN0009_MANIFEST_CHAIN",
    "TWO_RUNNER_PLAN0009_LEDGER_ARTIFACT",
    "derive_two_runner_treatment",
    "validate_two_runner_pair",
    "revert_two_runner_pair",
    "validate_two_runner_d4_equivariance",
    "two_runner_added_position",
    "two_runner_stratum",
    "two_runner_state_upper_bound",
    "two_runner_natural_terminal_ply_bound",
    "validate_two_runner_searched_states",
    "build_two_runner_evaluated_orbit_projection",
    "validate_two_runner_evaluated_orbit_projection",
    "build_two_runner_historical_definition_projection",
    "validate_two_runner_historical_definition_projection",
    "build_two_runner_closed_projection_bundle",
    "validate_two_runner_closed_projection_bundle",
    "build_two_runner_planning_snapshot",
    "build_two_runner_manifest",
    "validate_two_runner_manifest",
)
