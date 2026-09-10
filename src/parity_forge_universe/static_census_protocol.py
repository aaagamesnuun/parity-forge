"""Fixed Plan-0015 static-census protocol and executable source closure.

This module contains commitments and source-authentication code only.  It does
not import or execute the census, reconstruct a stored report, or open the
evidence store.  The one production stage is joined to those capabilities only
by :mod:`parity_forge_universe.static_census_stage`.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import subprocess
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


class StaticCensusProtocolError(ValueError):
    """A fixed protocol, Git source, or current source byte changed."""


class StaticCensusStoredClosureIntegrityError(StaticCensusProtocolError):
    """A stored production-closure value is structurally or canonically invalid."""


class _StaticCensusSourceSemanticError(StaticCensusProtocolError):
    """Available Git source is not an authorized production closure."""


PLAN0015_STATIC_CENSUS_PROTOCOL_VERSION_V1 = 1
PLAN0015_STATIC_CENSUS_PROTOCOL_ID_V1 = (
    "plan0015-factorized-static-census-reconstruction-protocol-v1"
)
PLAN0015_STATIC_CENSUS_EVIDENCE_PROTOCOL_ID_V1 = (
    "plan0015-factorized-static-census-evidence-v1"
)
PLAN0015_STATIC_CENSUS_STAGE_ID_V1 = "PLAN0015_FACTORIZED_STATIC_CENSUS"
PLAN0015_STATIC_CENSUS_STAGE_PROTOCOL_ID_V1 = (
    "plan0015-factorized-static-census-stage-v1"
)
PLAN0015_STATIC_CENSUS_EVIDENCE_ROOT_RELATIVE_V1 = (
    "experiments/runs/plan0015-factorized-static-census-evidence-v1"
)
PLAN0015_ACTIVE_PLAN_PATH_V1 = (
    "docs/plans/active/0015-exhaustive-typed-occupancy-v4-universe.md"
)

# This is the calculation implementation checkpoint.  Its five production
# modules are byte-invariant across the evidence-edge implementation.
PLAN0015_STATIC_CENSUS_CALCULATION_COMMIT_V1 = (
    "27b3f751bb70f1f13ddc67b086d382a7f14d3234"
)
PLAN0015_STATIC_CENSUS_CALCULATION_TREE_V1 = (
    "04169503305befe6502713d624c3d68baa4527bd"
)

# This is the first commit containing the preregistration.  The production
# source must be a merge-free descendant with exactly the fixed change surface
# below.  The active plan itself may not change after this point.
PLAN0015_STATIC_CENSUS_PREREGISTRATION_COMMIT_V1 = (
    "46191022159d5bcc3e6112bda6fc0736c9d5036b"
)
PLAN0015_STATIC_CENSUS_PREREGISTRATION_TREE_V1 = (
    "1b8c5d72d8b648d206742486639b53fa8df4926f"
)
PLAN0015_STATIC_CENSUS_PREREGISTERED_PLAN_BLOB_V1 = (
    "df30a3d641fcae68ad90a80b141bc6aea0bcc695"
)
PLAN0015_STATIC_CENSUS_PREREGISTERED_PLAN_SHA256_V1 = (
    "832b7815bba6b10cfa0a83b12efa3a0a7725548c4882d52afa29729175dbaf98"
)
PLAN0015_STATIC_CENSUS_PREREGISTERED_PLAN_BYTE_COUNT_V1 = 34_153

STATIC_CENSUS_REPORT_MAX_BYTES_V1 = 256 * 1024 * 1024
STATIC_CENSUS_REPORT_MAX_JSON_NODES_V1 = 5_000_000
STATIC_CENSUS_REPORT_MAX_JSON_DEPTH_V1 = 32
STATIC_CENSUS_SYNTHETIC_REPORT_BYTE_COUNT_V1 = 9_462_884

STATIC_CENSUS_EXPECTED_SKELETON_COUNT_V1 = 1_518
STATIC_CENSUS_EXPECTED_FACTORIZED_CARRIER_COUNT_V1 = 5_111_055
STATIC_CENSUS_EXPECTED_LABELED_SETUP_COUNT_V1 = 10_319_364
STATIC_CENSUS_EXPECTED_PAIRED_MEMBER_COUNT_V1 = 20_638_728
STATIC_CENSUS_EXPECTED_SETUP_ORBIT_TABLE_ROOT_V1 = (
    "f1bc82d1cfbaac9933e097aba2f4118737e19f7a190f06bc9f0a83add17c2e23"
)
STATIC_CENSUS_EXPECTED_SKELETON_AUTHORITY_ROOT_V1 = (
    "53221ffdbd42e4c86e9c54eadb6e0659bf71ff350dcdf0944b062ce56c3e1488"
)
STATIC_CENSUS_EXPECTED_UNIVERSE_DESCRIPTOR_ROOT_V1 = (
    "05826dc2da02890f3f562ee2d6febda523c58837affb757b5dff6d62c074e6ab"
)
STATIC_CENSUS_EXPECTED_FRESH_SKELETON_ROOT_V1 = (
    "ca02a2bbd844962fd83c7190eec69dea51877940ea6f0836c5a00338a3e9e190"
)
STATIC_CENSUS_EXPECTED_COUNT_TABLE_ROOT_V1 = (
    "de2e65f28be1f60aff4712c23c8681ea7945324886a2954a0f8d8cbfa905d226"
)


FROZEN_CALCULATION_FILE_RECORDS_V1: Tuple[
    Tuple[str, str, str, int], ...
] = (
    (
        "src/parity_forge_universe/__init__.py",
        "6a7aba9eb4e114302414390c217d8dc3bb755bd3",
        "bdf01c663c0d86032f9c437f545d7bf8f3efb5cb4639ce0b529a9356ac224573",
        71,
    ),
    (
        "src/parity_forge_universe/initial_structure.py",
        "c7d806aa38c3a8152ae6289f64e3cba0765a7ac1",
        "90ef3cf8cbe4a9a764fd845358810610326c315810fbc66ce4543d130241b5a7",
        91_862,
    ),
    (
        "src/parity_forge_universe/schema_v4_compiler.py",
        "95bb75811abb57b7474fb453d6c420f435a1251a",
        "aab2505691c226fdf03c9764987b3b692879db709301be3de83ae032610b10d3",
        59_252,
    ),
    (
        "src/parity_forge_universe/static_census.py",
        "fd5fb486ea33fac840b2951ff0a3680a3c221058",
        "f7205f8113b37d28bd003884438fb88bb19eb2a608fb12263c979faa2670d460",
        170_839,
    ),
    (
        "src/parity_forge_universe/typed_occupancy.py",
        "55cc8f7c99979495cd0e9d7f4ce2085d400771f7",
        "a85dee9328279227200f2e43b6b6a12bafdf2f183f4b8db4c68180c8998aeba7",
        119_728,
    ),
)

PRODUCTION_ENTRYPOINT_PATHS_V1: Tuple[str, ...] = (
    "src/parity_forge_universe/static_census_stage.py",
)
PRODUCTION_CLOSURE_PATHS_V1: Tuple[str, ...] = (
    "src/parity_forge_universe/__init__.py",
    "src/parity_forge_universe/initial_structure.py",
    "src/parity_forge_universe/schema_v4_compiler.py",
    "src/parity_forge_universe/static_census.py",
    "src/parity_forge_universe/static_census_evidence.py",
    "src/parity_forge_universe/static_census_protocol.py",
    "src/parity_forge_universe/static_census_reconstruction.py",
    "src/parity_forge_universe/static_census_stage.py",
    "src/parity_forge_universe/typed_occupancy.py",
)
PERMITTED_IMPLEMENTATION_CHANGED_PATHS_V1: Tuple[str, ...] = (
    ".gitignore",
    "src/parity_forge_universe/static_census_evidence.py",
    "src/parity_forge_universe/static_census_protocol.py",
    "src/parity_forge_universe/static_census_reconstruction.py",
    "src/parity_forge_universe/static_census_stage.py",
    "tests/test_static_census_evidence.py",
    "tests/test_static_census_protocol.py",
    "tests/test_static_census_reconstruction.py",
    "tests/test_static_census_stage.py",
)


_PROTOCOL_ARTIFACT_TYPE = "PLAN0015_STATIC_CENSUS_PROTOCOL_V1"
_PRODUCTION_CLOSURE_ARTIFACT_TYPE = (
    "PLAN0015_STATIC_CENSUS_PRODUCTION_CLOSURE_V1"
)
_HEX40 = re.compile(r"\A[0-9a-f]{40}\Z")
_HEX64 = re.compile(r"\A[0-9a-f]{64}\Z")
_SAFE_REPO_COMPONENT = re.compile(r"\A[A-Za-z0-9_][A-Za-z0-9._-]{0,191}\Z")
_READABLE_SOURCE_MODES = (0o444, 0o644)
_MAX_GIT_OUTPUT_BYTES = 16 * 1024 * 1024
_MAX_GIT_RUNTIME_SECONDS_V1 = 60
_MAX_GIT_INDEX_BYTES_V1 = 512 * 1024 * 1024
_MAX_GIT_PACKED_REFS_BYTES_V1 = 64 * 1024 * 1024
_MAX_GIT_REF_BYTES_V1 = 4096
_MAX_GIT_METADATA_ENTRIES_V1 = 1_000_000
_MAX_GIT_METADATA_DEPTH_V1 = 32
_MAX_SOURCE_ANCESTRY_COMMITS_V1 = 256
_MAX_LOCAL_GIT_CONFIG_BYTES_V1 = 1024 * 1024
_MAX_PACK_DIRECTORY_ENTRIES_V1 = 16_384
_MAX_WORKTREE_ATTRIBUTE_SCAN_ENTRIES_V1 = 1_000_000
_MAX_WORKTREE_ATTRIBUTE_SCAN_DEPTH_V1 = 64
_FIXED_GIT_PATH_V1 = "/usr/bin:/bin"
_FIXED_GIT_EXECUTABLE_CANDIDATES_V1 = ("/usr/bin/git", "/bin/git")
_PREEXISTING_OPERATIONAL_LOCK_PATHS_V1 = (
    "experiments/runs/plan0013-atlas-development-evidence-v2/.locks/"
    "plan0013-atlas-development-assessment-v1.lock",
    "experiments/runs/plan0013-atlas-development-evidence-v2/.locks/"
    "plan0013-atlas-development-exact-v1.lock",
    "experiments/runs/plan0013-atlas-development-evidence-v2/.locks/"
    "plan0013-atlas-development-manifest-v1.lock",
    "experiments/runs/plan0013-atlas-development-evidence-v2/.locks/"
    "plan0013-atlas-development-random-v1.lock",
    "experiments/runs/plan0013-atlas-development-evidence-v2/.locks/"
    "plan0013-atlas-development-telemetry-v1.lock",
    "experiments/runs/plan0013-atlas-development-evidence-v2/.locks/"
    "plan0013-atlas-development-terminal-depth1-v1.lock",
    "experiments/runs/plan0014-plan0013-assessment-reconstruction-evidence-v1/"
    ".locks/plan0014-plan0013-assessment-reconstruction-stage-v1.lock",
)


def _git_executable_state_v1(path: str) -> Tuple[int, ...]:
    if type(path) is not str or not os.path.isabs(path):
        raise StaticCensusProtocolError("Git executable path is not fixed absolute")
    try:
        info = os.stat(path, follow_symlinks=False)
    except OSError as error:
        raise StaticCensusProtocolError("fixed Git executable is unavailable") from error
    if not stat.S_ISREG(info.st_mode) or not info.st_mode & 0o111:
        raise StaticCensusProtocolError("fixed Git executable is not executable")
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _capture_git_executable_v1() -> Tuple[str, Tuple[int, ...]]:
    for candidate in _FIXED_GIT_EXECUTABLE_CANDIDATES_V1:
        resolved = os.path.realpath(candidate)
        try:
            state = _git_executable_state_v1(resolved)
        except StaticCensusProtocolError:
            continue
        return resolved, state
    raise StaticCensusProtocolError("no fixed system Git executable is available")


_GIT_EXECUTABLE_V1, _GIT_EXECUTABLE_STATE_V1 = _capture_git_executable_v1()


def _source_attribute_paths_v1() -> Tuple[str, ...]:
    paths = {".gitattributes"}
    targets = (
        *PRODUCTION_CLOSURE_PATHS_V1,
        *PERMITTED_IMPLEMENTATION_CHANGED_PATHS_V1,
        PLAN0015_ACTIVE_PLAN_PATH_V1,
    )
    for target in targets:
        components = target.split("/")[:-1]
        for depth in range(1, len(components) + 1):
            paths.add("{}/.gitattributes".format("/".join(components[:depth])))
    return tuple(sorted(paths, key=lambda value: value.encode("utf-8")))


_SOURCE_ATTRIBUTE_PATHS_V1 = _source_attribute_paths_v1()


_IDENTITY_DOMAINS_V1: Dict[str, bytes] = {
    kind: (
        "parity-forge:plan0015:factorized-static-census:{}:v1\0".format(
            kind.replace("_", "-")
        ).encode("ascii")
    )
    for kind in (
        "protocol_root",
        "production_closure_root",
        "bootstrap_root",
        "reservation_id",
        "attempt_id",
        "completed_root",
        "failure_root",
        "orphaned_id",
        "terminal_seal",
        "contradiction_id",
    )
}

_IDENTITY_PAYLOAD_KEYS_V1: Dict[str, Tuple[str, ...]] = {
    "protocol_root": (
        "active_plan_path",
        "artifact_type",
        "calculation_checkpoint",
        "capability_contract",
        "evidence_protocol_id",
        "evidence_protocol_version",
        "evidence_store_relative_path",
        "identity_schemas",
        "lifecycle_contract",
        "population_contract",
        "production_closure_contract",
        "protocol_id",
        "protocol_version",
        "report_contract",
        "stage_contract",
    ),
    "production_closure_root": (
        "active_plan_ref",
        "calculation_checkpoint_commit",
        "calculation_checkpoint_tree",
        "ordered_entrypoint_paths",
        "ordered_file_records",
        "preregistration_commit",
        "preregistration_tree",
        "protocol_module_blob_identity",
        "source_commit",
        "source_tree",
        "stage_id",
    ),
    "bootstrap_root": (
        "active_plan_ref",
        "evidence_protocol_id",
        "production_closure_root",
        "protocol_id",
        "protocol_ref",
        "protocol_root",
        "source_commit",
        "source_tree",
        "stage_id",
        "stage_protocol_id",
    ),
    "reservation_id": (
        "bootstrap_root",
        "evidence_protocol_id",
        "production_closure_root",
        "protocol_id",
        "protocol_root",
        "stage_id",
        "stage_protocol_id",
    ),
    "attempt_id": (
        "attempt_index",
        "production_closure_root",
        "reservation_id",
        "source_commit",
        "source_tree",
        "stage_id",
        "stage_protocol_id",
    ),
    "completed_root": (
        "attempt_id",
        "report_ref",
        "report_summary",
        "reservation_id",
        "stage_id",
        "stage_protocol_id",
    ),
    "failure_root": (
        "attempt_id",
        "failure",
        "reservation_id",
        "stage_id",
        "stage_protocol_id",
    ),
    "orphaned_id": (
        "attempt_id_or_null",
        "orphan_reason",
        "reservation_id",
        "stage_id",
        "stage_protocol_id",
    ),
    "terminal_seal": (
        "attempt_id_or_null",
        "completed_root_or_null",
        "failure_root_or_null",
        "lifecycle",
        "orphaned_id_or_null",
        "report_ref_or_null",
        "reservation_id_or_null",
        "stage_id",
        "stage_protocol_id",
    ),
    "contradiction_id": (
        "bootstrap_root_or_null",
        "contradiction_kind",
        "observed_catalog_refs",
        "stage_id",
        "stage_protocol_id",
    ),
}


def identity_domain_v1(kind: str) -> bytes:
    """Return the fixed domain for one exact identity kind."""

    if type(kind) is not str:
        raise TypeError("identity kind must be an exact string")
    try:
        return _IDENTITY_DOMAINS_V1[kind]
    except KeyError as error:
        raise ValueError("unknown static-census identity kind") from error


def identity_payload_keys_v1(kind: str) -> Tuple[str, ...]:
    """Return the fixed payload field order for one identity kind."""

    if type(kind) is not str:
        raise TypeError("identity kind must be an exact string")
    try:
        return _IDENTITY_PAYLOAD_KEYS_V1[kind]
    except KeyError as error:
        raise ValueError("unknown static-census identity kind") from error


def _validate_json_tree(
    value: Any, *, max_nodes: int = 200_000, max_depth: int = 64
) -> None:
    nodes = 0
    active: set[int] = set()

    def visit(item: Any, depth: int) -> None:
        nonlocal nodes
        nodes += 1
        if nodes > max_nodes:
            raise StaticCensusProtocolError("protocol JSON exceeds its node cap")
        if depth > max_depth:
            raise StaticCensusProtocolError("protocol JSON exceeds its depth cap")
        if item is None or type(item) in (bool, int, str):
            return
        if type(item) not in (dict, list):
            raise StaticCensusProtocolError(
                "protocol value contains a non-exact JSON type"
            )
        if type(item) is dict and any(type(key) is not str for key in item):
            raise StaticCensusProtocolError("protocol object key is not an exact string")
        identity = id(item)
        if identity in active:
            raise StaticCensusProtocolError("protocol value contains a cycle")
        active.add(identity)
        try:
            children = item.values() if type(item) is dict else item
            for child in children:
                visit(child, depth + 1)
        finally:
            active.remove(identity)

    visit(value, 0)


def canonical_json_bytes_v1(value: Any) -> bytes:
    """Encode an exact JSON tree using the protocol's only wire format."""

    _validate_json_tree(value)
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as error:
        raise StaticCensusProtocolError("value is not canonical JSON") from error


def _json_copy(value: Any) -> Any:
    return json.loads(canonical_json_bytes_v1(value).decode("utf-8"))


def _body_ref(raw: bytes) -> Dict[str, Any]:
    if type(raw) is not bytes:
        raise TypeError("body reference input must be exact bytes")
    return {"byte_count": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def _domain_identity(kind: str, payload: Any) -> str:
    return hashlib.sha256(
        identity_domain_v1(kind) + canonical_json_bytes_v1(payload)
    ).hexdigest()


def _frozen_calculation_records() -> List[Dict[str, Any]]:
    return [
        {
            "byte_count": byte_count,
            "git_blob_sha1": blob,
            "path": path,
            "sha256": sha256,
        }
        for path, blob, sha256, byte_count in FROZEN_CALCULATION_FILE_RECORDS_V1
    ]


def _protocol_payload_v1() -> Dict[str, Any]:
    return {
        "active_plan_path": PLAN0015_ACTIVE_PLAN_PATH_V1,
        "artifact_type": _PROTOCOL_ARTIFACT_TYPE,
        "calculation_checkpoint": {
            "commit": PLAN0015_STATIC_CENSUS_CALCULATION_COMMIT_V1,
            "ordered_file_records": _frozen_calculation_records(),
            "tree": PLAN0015_STATIC_CENSUS_CALCULATION_TREE_V1,
        },
        "capability_contract": {
            "calculation_allowed": [
                "enumerate-fixed-typed-universe",
                "derive-static-initial-structure",
                "aggregate-factorized-static-census",
            ],
            "evidence_edge_allowed": [
                "authenticate-git-source",
                "reconstruct-bounded-stored-report",
                "publish-fixed-immutable-evidence",
            ],
            "forbidden": [
                "import-parity-forge-legacy-package",
                "apply-action-or-run-game",
                "compute-terminal-or-outcome",
                "invoke-solver-agent-replay-or-telemetry",
                "read-history-selection-or-candidate-artifact",
                "rank-score-or-partition-carriers",
                "network-or-dynamic-import",
            ],
            "claim_level": (
                "OUTCOME_FREE_STATIC_NECESSARY_CONDITION_CENSUS_ONLY_"
                "NO_FAIRNESS_STRATEGY_QUALITY_FUN_OR_CANDIDATE_CLAIM"
            ),
        },
        "evidence_protocol_id": PLAN0015_STATIC_CENSUS_EVIDENCE_PROTOCOL_ID_V1,
        "evidence_protocol_version": 1,
        "evidence_store_relative_path": (
            PLAN0015_STATIC_CENSUS_EVIDENCE_ROOT_RELATIVE_V1
        ),
        "identity_schemas": {
            kind: {
                "domain_hex": identity_domain_v1(kind).hex(),
                "payload_keys": list(identity_payload_keys_v1(kind)),
            }
            for kind in sorted(_IDENTITY_DOMAINS_V1)
        },
        "lifecycle_contract": {
            "artifact_order": [
                "bootstrap",
                "reservation",
                "attempt",
                "static-census-report-or-failure-or-orphaned",
                "completed-after-report",
                "terminal-seal",
            ],
            "attempt_index": 0,
            "bootstrap_only_run_may_continue": True,
            "completed_precludes_failure_replacement": True,
            "fixed_stage_files": [
                "reservation.json",
                "attempt.json",
                "static-census-report.json",
                "completed.json",
                "failure.json",
                "orphaned.json",
                "terminal-seal.json",
            ],
            "mutable_checkpoint_is_evidence": False,
            "report_precludes_failure_replacement": True,
            "reservation_or_attempt_recovery": "SEAL_ORPHANED_NEVER_RESUME",
            "terminal_run_and_recover_action": "VERIFIED_NO_OP",
        },
        "population_contract": {
            "count_lattice_table_root": STATIC_CENSUS_EXPECTED_COUNT_TABLE_ROOT_V1,
            "factorized_carrier_count": (
                STATIC_CENSUS_EXPECTED_FACTORIZED_CARRIER_COUNT_V1
            ),
            "fresh_canonical_skeleton_root": (
                STATIC_CENSUS_EXPECTED_FRESH_SKELETON_ROOT_V1
            ),
            "labeled_setup_count": STATIC_CENSUS_EXPECTED_LABELED_SETUP_COUNT_V1,
            "paired_first_player_member_count": (
                STATIC_CENSUS_EXPECTED_PAIRED_MEMBER_COUNT_V1
            ),
            "setup_orbit_table_root": (
                STATIC_CENSUS_EXPECTED_SETUP_ORBIT_TABLE_ROOT_V1
            ),
            "skeleton_authority_root": (
                STATIC_CENSUS_EXPECTED_SKELETON_AUTHORITY_ROOT_V1
            ),
            "skeleton_count": STATIC_CENSUS_EXPECTED_SKELETON_COUNT_V1,
            "universe_descriptor_root": (
                STATIC_CENSUS_EXPECTED_UNIVERSE_DESCRIPTOR_ROOT_V1
            ),
        },
        "production_closure_contract": {
            "artifact_type": _PRODUCTION_CLOSURE_ARTIFACT_TYPE,
            "calculation_files_are_exact_checkpoint_blobs": True,
            "ordered_entrypoint_paths": list(PRODUCTION_ENTRYPOINT_PATHS_V1),
            "ordered_exact_recursive_paths": list(PRODUCTION_CLOSURE_PATHS_V1),
            "permitted_implementation_changed_paths": list(
                PERMITTED_IMPLEMENTATION_CHANGED_PATHS_V1
            ),
            "preregistered_active_plan_ref": {
                "byte_count": (
                    PLAN0015_STATIC_CENSUS_PREREGISTERED_PLAN_BYTE_COUNT_V1
                ),
                "git_blob_sha1": (
                    PLAN0015_STATIC_CENSUS_PREREGISTERED_PLAN_BLOB_V1
                ),
                "sha256": PLAN0015_STATIC_CENSUS_PREREGISTERED_PLAN_SHA256_V1,
            },
            "preregistration_commit": (
                PLAN0015_STATIC_CENSUS_PREREGISTRATION_COMMIT_V1
            ),
            "preregistration_tree": PLAN0015_STATIC_CENSUS_PREREGISTRATION_TREE_V1,
            "source_history": "STRICT_MERGE_FREE_DESCENDANT",
        },
        "protocol_id": PLAN0015_STATIC_CENSUS_PROTOCOL_ID_V1,
        "protocol_version": PLAN0015_STATIC_CENSUS_PROTOCOL_VERSION_V1,
        "report_contract": {
            "artifact_filename": "static-census-report.json",
            "canonical_source_function": "canonical_static_census_report_json_v1",
            "completed_summary_keys": [
                "report_digest",
                "setup_orbit_table_root",
                "skeleton_authority_root",
                "ordered_shard_commitment_root",
                "population",
                "eligibility",
            ],
            "embedded_digest_function": "static_census_report_hash_v1",
            "max_bytes": STATIC_CENSUS_REPORT_MAX_BYTES_V1,
            "max_json_depth": STATIC_CENSUS_REPORT_MAX_JSON_DEPTH_V1,
            "max_json_nodes": STATIC_CENSUS_REPORT_MAX_JSON_NODES_V1,
            "recovery_leaf_semantic_rerun": False,
            "recovery_reconstructs_all_shard_and_aggregate_roots": True,
            "synthetic_lower_shape_fixture_bytes": (
                STATIC_CENSUS_SYNTHETIC_REPORT_BYTE_COUNT_V1
            ),
            "whole_file_hash": "SHA256_RAW_CANONICAL_UTF8",
        },
        "stage_contract": {
            "builder_call": "build_static_census_v1()",
            "builder_call_count_after_attempt": 1,
            "cli_module": "parity_forge_universe.static_census_stage",
            "commands": ["run", "recover"],
            "public_recover_function": "recover_static_census_stage_v1",
            "public_run_function": "run_static_census_stage_v1",
            "recover_builder_call_count": 0,
            "stage_id": PLAN0015_STATIC_CENSUS_STAGE_ID_V1,
            "stage_protocol_id": PLAN0015_STATIC_CENSUS_STAGE_PROTOCOL_ID_V1,
            "user_arguments": ["repository"],
        },
    }


def _unchecked_protocol_v1() -> Dict[str, Any]:
    payload = _protocol_payload_v1()
    if tuple(payload) != identity_payload_keys_v1("protocol_root"):
        raise StaticCensusProtocolError("protocol payload field order drifted")
    return {
        "artifact_type": _PROTOCOL_ARTIFACT_TYPE,
        "identity": _domain_identity("protocol_root", payload),
        "payload": payload,
    }


# Filled only after the complete protocol payload above was fixed.  These values
# intentionally do not commit to the later production source commit; that source
# is self-bound by its production-closure record.
PLAN0015_STATIC_CENSUS_PROTOCOL_ROOT_V1 = (
    "4636f6ee40189cb91855a7ed3e82070131c0915790043e4c4a81fc3ca124501b"
)
PLAN0015_STATIC_CENSUS_PROTOCOL_CANONICAL_SHA256_V1 = (
    "77047ed11ea03c09f0e5f5712b615b1c5a2a842d6ef9f818d6a3597a6d54b6de"
)
PLAN0015_STATIC_CENSUS_PROTOCOL_CANONICAL_BYTE_COUNT_V1 = 9_630


def build_static_census_protocol_v1() -> Dict[str, Any]:
    """Return the one fixed, outcome-free Plan-0015 evidence protocol."""

    value = _unchecked_protocol_v1()
    raw = canonical_json_bytes_v1(value)
    if (
        value["identity"] != PLAN0015_STATIC_CENSUS_PROTOCOL_ROOT_V1
        or hashlib.sha256(raw).hexdigest()
        != PLAN0015_STATIC_CENSUS_PROTOCOL_CANONICAL_SHA256_V1
        or len(raw) != PLAN0015_STATIC_CENSUS_PROTOCOL_CANONICAL_BYTE_COUNT_V1
    ):
        raise StaticCensusProtocolError("fixed static-census protocol drifted")
    return _json_copy(value)


def validate_static_census_protocol_v1(value: Any) -> Dict[str, Any]:
    """Strictly validate and reconstruct the fixed protocol value."""

    if type(value) is not dict or set(value) != {
        "artifact_type",
        "identity",
        "payload",
    }:
        raise StaticCensusProtocolError("protocol envelope is not exact")
    observed = canonical_json_bytes_v1(value)
    expected = canonical_json_bytes_v1(build_static_census_protocol_v1())
    if observed != expected:
        raise StaticCensusProtocolError("protocol does not reconstruct exactly")
    return _json_copy(value)


def _safe_repo_path(value: str) -> str:
    if type(value) is not str or not value or value.startswith("/"):
        raise StaticCensusProtocolError("repository-relative path is invalid")
    components = value.split("/")
    if any(
        component in ("", ".", "..")
        or _SAFE_REPO_COMPONENT.fullmatch(component) is None
        or "\\" in component
        for component in components
    ):
        raise StaticCensusProtocolError("repository-relative path is unsafe")
    return value


def _git_environment() -> Dict[str, str]:
    # Git exposes repository, object, index, config, namespace, pathspec, and
    # replacement controls through its environment.  Loader, executable-search,
    # and global-configuration variables are capabilities too, so inherit none
    # of the ambient process environment and install one exact inert map.
    return {
        "GIT_ALLOW_PROTOCOL": "",
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_NO_LAZY_FETCH": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_PAGER": "cat",
        "GIT_PROTOCOL_FROM_USER": "0",
        "GIT_TERMINAL_PROMPT": "0",
        "LANG": "C",
        "LC_ALL": "C",
        "PATH": _FIXED_GIT_PATH_V1,
    }


def _run_bounded_subprocess_v1(
    command: Sequence[str],
    environment: Dict[str, str],
    *,
    max_output_bytes: int,
    timeout_seconds: float,
    _popen: Any = subprocess.Popen,
    _selector_type: Any = selectors.DefaultSelector,
    _monotonic: Any = time.monotonic,
) -> subprocess.CompletedProcess:
    """Run one child with concurrent hard-bounded output and wall time."""

    if type(max_output_bytes) is not int or max_output_bytes < 0:
        raise TypeError("process output bound must be a nonnegative exact int")
    if (
        type(timeout_seconds) not in (int, float)
        or type(timeout_seconds) is bool
        or timeout_seconds <= 0
    ):
        raise TypeError("process timeout must be a positive number")
    process = None
    selector = None
    streams = []
    command_list = list(command)
    try:
        process = _popen(
            command_list,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            env=environment,
            start_new_session=True,
        )
        if process.stdout is None or process.stderr is None:
            raise StaticCensusProtocolError("Git output pipes are unavailable")
        selector = _selector_type()
        buffers = {"stdout": bytearray(), "stderr": bytearray()}
        for label, stream in (
            ("stdout", process.stdout),
            ("stderr", process.stderr),
        ):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, label)
            streams.append(stream)
        deadline = _monotonic() + timeout_seconds
        while selector.get_map():
            remaining = deadline - _monotonic()
            if remaining <= 0:
                raise StaticCensusProtocolError("Git source check timed out")
            events = selector.select(remaining)
            if not events:
                continue
            for key, _mask in events:
                label = key.data
                buffer = buffers[label]
                read_size = min(64 * 1024, max_output_bytes + 1 - len(buffer))
                try:
                    chunk = os.read(key.fd, read_size)
                except BlockingIOError:
                    continue
                if not chunk:
                    selector.unregister(key.fileobj)
                    key.fileobj.close()
                    continue
                buffer.extend(chunk)
                if len(buffer) > max_output_bytes:
                    raise StaticCensusProtocolError(
                        "Git source response exceeds its byte cap"
                    )
        remaining = deadline - _monotonic()
        if remaining <= 0:
            raise StaticCensusProtocolError("Git source check timed out")
        try:
            returncode = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired as error:
            raise StaticCensusProtocolError("Git source check timed out") from error
        return subprocess.CompletedProcess(
            command_list,
            returncode,
            stdout=bytes(buffers["stdout"]),
            stderr=bytes(buffers["stderr"]),
        )
    finally:
        if selector is not None:
            selector.close()
        for stream in streams:
            if not stream.closed:
                stream.close()
        if process is not None and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except (OSError, ProcessLookupError):
                try:
                    process.kill()
                except OSError:
                    pass
            try:
                process.wait(timeout=1)
            except (OSError, subprocess.TimeoutExpired):
                pass


def _run_git(
    repository: Path,
    arguments: Sequence[str],
    *,
    check: bool = True,
    _executable: str = _GIT_EXECUTABLE_V1,
    _executable_state: Tuple[int, ...] = _GIT_EXECUTABLE_STATE_V1,
    _read_executable_state: Any = _git_executable_state_v1,
    _execute: Any = _run_bounded_subprocess_v1,
    _environment: Any = _git_environment,
    _max_output_bytes: int = _MAX_GIT_OUTPUT_BYTES,
    _timeout_seconds: float = _MAX_GIT_RUNTIME_SECONDS_V1,
) -> subprocess.CompletedProcess:
    if type(arguments) not in (tuple, list) or any(
        type(argument) is not str for argument in arguments
    ):
        raise TypeError("Git arguments must be exact strings")
    if _read_executable_state(_executable) != _executable_state:
        raise StaticCensusProtocolError("fixed Git executable identity changed")
    command = [
        _executable,
        "--no-pager",
        "--no-replace-objects",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.untrackedCache=false",
        "-c",
        "core.preloadIndex=false",
        "-c",
        "core.attributesFile=/dev/null",
        "-c",
        "protocol.allow=never",
        "-c",
        "protocol.file.allow=never",
        "-C",
        str(repository),
        *arguments,
    ]
    try:
        process = _execute(
            command,
            _environment(),
            max_output_bytes=_max_output_bytes,
            timeout_seconds=_timeout_seconds,
        )
    except OSError as error:
        raise StaticCensusProtocolError("fixed Git executable failed") from error
    if _read_executable_state(_executable) != _executable_state:
        raise StaticCensusProtocolError("fixed Git executable identity changed")
    if check and process.returncode != 0:
        message = process.stderr[:4096].decode("utf-8", "replace").strip()
        raise StaticCensusProtocolError("Git source check failed: {}".format(message))
    return process


def _filesystem_state_v1(info: Any) -> Tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _read_bounded_regular_descriptor_v1(
    descriptor: int, max_bytes: int, label: str
) -> Tuple[bytes, Tuple[int, ...]]:
    before = os.fstat(descriptor)
    mode = stat.S_IMODE(before.st_mode)
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or not mode & 0o400
        or mode & 0o022
        or before.st_size > max_bytes
    ):
        raise StaticCensusProtocolError("{} is not a bounded private file".format(label))
    chunks = []
    offset = 0
    while offset < before.st_size:
        chunk = os.pread(
            descriptor, min(1024 * 1024, before.st_size - offset), offset
        )
        if not chunk:
            raise StaticCensusProtocolError("{} was truncated".format(label))
        chunks.append(chunk)
        offset += len(chunk)
    if os.pread(descriptor, 1, offset):
        raise StaticCensusProtocolError("{} grew while reading".format(label))
    after = os.fstat(descriptor)
    state = _filesystem_state_v1(before)
    if _filesystem_state_v1(after) != state:
        raise StaticCensusProtocolError("{} changed while reading".format(label))
    return b"".join(chunks), state


def _require_absent_entry_v1(parent_fd: int, name: str, label: str) -> None:
    try:
        os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    except OSError as error:
        raise StaticCensusProtocolError("{} cannot be inspected".format(label)) from error
    raise StaticCensusProtocolError("{} is forbidden".format(label))


def _read_safe_git_metadata_file_v1(
    parent_fd: int,
    name: str,
    label: str,
    *,
    max_bytes: int,
    required: bool,
    read_contents: bool = True,
) -> Optional[bytes]:
    """Read one bounded Git metadata file without following or blocking on it."""

    file_flags = (
        os.O_RDONLY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    descriptor = -1
    try:
        try:
            descriptor = os.open(name, file_flags, dir_fd=parent_fd)
        except FileNotFoundError:
            if required:
                raise StaticCensusProtocolError(
                    "required {} is absent".format(label)
                )
            return None
        if type(read_contents) is not bool:
            raise TypeError("read_contents must be an exact bool")
        if read_contents:
            raw, state = _read_bounded_regular_descriptor_v1(
                descriptor, max_bytes, label
            )
        else:
            observed = os.fstat(descriptor)
            mode = stat.S_IMODE(observed.st_mode)
            if (
                not stat.S_ISREG(observed.st_mode)
                or observed.st_nlink != 1
                or not mode & 0o400
                or mode & 0o022
                or observed.st_size > max_bytes
            ):
                raise StaticCensusProtocolError(
                    "{} is not a bounded private file".format(label)
                )
            state = _filesystem_state_v1(observed)
            raw = b""
        named = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if _filesystem_state_v1(named) != state:
            raise StaticCensusProtocolError("{} path changed".format(label))
        return raw
    except OSError as error:
        raise StaticCensusProtocolError(
            "{} is unavailable or unsafe".format(label)
        ) from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _require_safe_git_metadata_tree_v1(
    directory_fd: int,
    label: str,
    *,
    max_file_bytes: Optional[int],
) -> None:
    """Descriptor-scan a Git metadata subtree and reject active file types."""

    directory_flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    file_flags = (
        os.O_RDONLY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    seen = set()
    entry_count = 0

    def scan(current_fd: int, depth: int) -> None:
        nonlocal entry_count
        if depth > _MAX_GIT_METADATA_DEPTH_V1:
            raise StaticCensusProtocolError(
                "{} exceeds its depth bound".format(label)
            )
        before = os.fstat(current_fd)
        if not stat.S_ISDIR(before.st_mode):
            raise StaticCensusProtocolError("{} is not a directory".format(label))
        identity = (before.st_dev, before.st_ino)
        if identity in seen:
            raise StaticCensusProtocolError("{} contains a directory alias".format(label))
        seen.add(identity)
        try:
            try:
                with os.scandir(current_fd) as iterator:
                    names = []
                    for entry in iterator:
                        entry_count += 1
                        if entry_count > _MAX_GIT_METADATA_ENTRIES_V1:
                            raise StaticCensusProtocolError(
                                "{} exceeds its entry bound".format(label)
                            )
                        if type(entry.name) is not str:
                            raise StaticCensusProtocolError(
                                "{} returned a non-text name".format(label)
                            )
                        names.append(entry.name)
            except OSError as error:
                raise StaticCensusProtocolError(
                    "{} cannot be listed safely".format(label)
                ) from error
            if len(names) != len(set(names)):
                raise StaticCensusProtocolError(
                    "{} returned duplicate entries".format(label)
                )
            for name in sorted(names, key=lambda value: value.encode("utf-8")):
                named = os.stat(name, dir_fd=current_fd, follow_symlinks=False)
                if stat.S_ISDIR(named.st_mode):
                    child_fd = -1
                    try:
                        child_fd = os.open(
                            name, directory_flags, dir_fd=current_fd
                        )
                        opened = os.fstat(child_fd)
                        if _filesystem_state_v1(opened) != _filesystem_state_v1(
                            named
                        ):
                            raise StaticCensusProtocolError(
                                "{} directory binding changed".format(label)
                            )
                        scan(child_fd, depth + 1)
                        rebound = os.stat(
                            name, dir_fd=current_fd, follow_symlinks=False
                        )
                        if _filesystem_state_v1(rebound) != _filesystem_state_v1(
                            os.fstat(child_fd)
                        ):
                            raise StaticCensusProtocolError(
                                "{} directory binding changed".format(label)
                            )
                    finally:
                        if child_fd >= 0:
                            os.close(child_fd)
                    continue
                descriptor = -1
                try:
                    descriptor = os.open(name, file_flags, dir_fd=current_fd)
                    opened = os.fstat(descriptor)
                    mode = stat.S_IMODE(opened.st_mode)
                    if (
                        not stat.S_ISREG(opened.st_mode)
                        or opened.st_nlink != 1
                        or not mode & 0o400
                        or mode & 0o022
                        or (
                            max_file_bytes is not None
                            and opened.st_size > max_file_bytes
                        )
                        or _filesystem_state_v1(opened)
                        != _filesystem_state_v1(named)
                    ):
                        raise StaticCensusProtocolError(
                            "{} contains an unsafe metadata file".format(label)
                        )
                    rebound = os.stat(
                        name, dir_fd=current_fd, follow_symlinks=False
                    )
                    if _filesystem_state_v1(rebound) != _filesystem_state_v1(
                        os.fstat(descriptor)
                    ):
                        raise StaticCensusProtocolError(
                            "{} metadata binding changed".format(label)
                        )
                except OSError as error:
                    raise StaticCensusProtocolError(
                        "{} contains unavailable or unsafe metadata".format(label)
                    ) from error
                finally:
                    if descriptor >= 0:
                        os.close(descriptor)
            if _filesystem_state_v1(os.fstat(current_fd)) != _filesystem_state_v1(
                before
            ):
                raise StaticCensusProtocolError(
                    "{} changed while being inspected".format(label)
                )
        finally:
            seen.remove(identity)

    scan(directory_fd, 0)


def _validate_local_git_config_v1(raw: bytes) -> None:
    if raw and not raw.endswith(b"\0"):
        raise StaticCensusProtocolError("local Git config output is not canonical")
    records: List[Tuple[bytes, bytes]] = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        key, separator, value = record.partition(b"\n")
        if separator != b"\n" or not key or any(byte > 0x7F for byte in key):
            raise StaticCensusProtocolError("local Git config output is malformed")
        lowered = key.lower()
        records.append((lowered, value))
        if (
            lowered.startswith((b"filter.", b"include.", b"includeif."))
            or b"partialclone" in lowered
            or b"promisor" in lowered
            or lowered
            in (
                b"core.alternaterefscommand",
                b"core.attributesfile",
                b"core.excludesfile",
                b"core.fsmonitor",
                b"core.gitproxy",
                b"core.sparsecheckout",
                b"core.sparsecheckoutcone",
                b"core.sshcommand",
                b"core.worktree",
                b"diff.external",
            )
            or (
                lowered.startswith(b"diff.")
                and lowered.endswith((b".command", b".textconv"))
            )
        ):
            raise StaticCensusProtocolError(
                "local Git config contains a forbidden capability"
            )
    values: Dict[bytes, List[bytes]] = {}
    for key, value in records:
        values.setdefault(key, []).append(value.lower())
    if values.get(b"core.repositoryformatversion") != [b"0"]:
        raise StaticCensusProtocolError("Git repository format is not fixed SHA-1")
    if values.get(b"core.bare") != [b"false"]:
        raise StaticCensusProtocolError("bare Git repositories are forbidden")


def _require_closed_git_repository_v1(repository: Path) -> None:
    """Reject object/config capabilities before authenticating Git objects."""

    directory_flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    file_flags = (
        os.O_RDONLY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    parent_fd = config_fd = -1
    held_directories: List[Tuple[int, str, int, Tuple[int, ...]]] = []

    def open_directory(parent: int, name: str, *, required: bool) -> int:
        descriptor = -1
        try:
            descriptor = os.open(name, directory_flags, dir_fd=parent)
        except FileNotFoundError:
            if required:
                raise StaticCensusProtocolError(
                    "required Git metadata directory is absent"
                )
            return -1
        except OSError as error:
            raise StaticCensusProtocolError(
                "Git metadata directory is unavailable or unsafe"
            ) from error
        try:
            observed = os.fstat(descriptor)
            named = os.stat(name, dir_fd=parent, follow_symlinks=False)
            state = _filesystem_state_v1(observed)
            if (
                not stat.S_ISDIR(observed.st_mode)
                or not stat.S_ISDIR(named.st_mode)
                or _filesystem_state_v1(named) != state
            ):
                raise StaticCensusProtocolError("Git metadata directory changed")
            held_directories.append((parent, name, descriptor, state))
            return descriptor
        except BaseException:
            os.close(descriptor)
            raise

    try:
        parent_fd = os.open(str(repository.parent), directory_flags)
        repository_fd = open_directory(parent_fd, repository.name, required=True)
        git_fd = open_directory(repository_fd, ".git", required=True)
        info_fd = open_directory(git_fd, "info", required=False)
        objects_fd = open_directory(git_fd, "objects", required=True)
        objects_info_fd = open_directory(objects_fd, "info", required=False)
        pack_fd = open_directory(objects_fd, "pack", required=False)
        refs_fd = open_directory(git_fd, "refs", required=False)

        _require_absent_entry_v1(git_fd, "shallow", "shallow repository marker")
        if info_fd >= 0:
            _require_absent_entry_v1(
                info_fd, "attributes", "repository-local attribute file"
            )
        if objects_info_fd >= 0:
            _require_absent_entry_v1(
                objects_info_fd, "alternates", "alternate object store"
            )
            _require_absent_entry_v1(
                objects_info_fd, "http-alternates", "HTTP alternate object store"
            )
        if pack_fd >= 0:
            before_pack = os.fstat(pack_fd)
            try:
                with os.scandir(pack_fd) as iterator:
                    entries = []
                    for entry in iterator:
                        if len(entries) >= _MAX_PACK_DIRECTORY_ENTRIES_V1:
                            raise StaticCensusProtocolError(
                                "Git pack directory exceeds its entry bound"
                            )
                        entries.append(entry.name)
            except OSError as error:
                raise StaticCensusProtocolError(
                    "Git pack directory cannot be inspected"
                ) from error
            if any(
                type(name) is not str or name.casefold().endswith(".promisor")
                for name in entries
            ):
                raise StaticCensusProtocolError(
                    "promisor object packs are forbidden"
                )
            if _filesystem_state_v1(os.fstat(pack_fd)) != _filesystem_state_v1(
                before_pack
            ):
                raise StaticCensusProtocolError(
                    "Git pack directory changed while inspecting it"
                )

        head_raw = _read_safe_git_metadata_file_v1(
            git_fd,
            "HEAD",
            "Git HEAD",
            max_bytes=_MAX_GIT_REF_BYTES_V1,
            required=True,
        )
        if head_raw is None or re.fullmatch(
            rb"(?:[0-9a-f]{40}|ref: refs/[A-Za-z0-9._/-]+)\n", head_raw
        ) is None or b".." in head_raw or b"//" in head_raw:
            raise StaticCensusProtocolError("Git HEAD is not canonical")
        _read_safe_git_metadata_file_v1(
            git_fd,
            "index",
            "Git index",
            max_bytes=_MAX_GIT_INDEX_BYTES_V1,
            required=False,
            read_contents=False,
        )
        _read_safe_git_metadata_file_v1(
            git_fd,
            "packed-refs",
            "Git packed refs",
            max_bytes=_MAX_GIT_PACKED_REFS_BYTES_V1,
            required=False,
            read_contents=False,
        )
        if refs_fd >= 0:
            _require_safe_git_metadata_tree_v1(
                refs_fd,
                "Git refs",
                max_file_bytes=_MAX_GIT_REF_BYTES_V1,
            )
        _require_safe_git_metadata_tree_v1(
            objects_fd,
            "Git object store",
            max_file_bytes=None,
        )

        config_fd = os.open("config", file_flags, dir_fd=git_fd)
        _config_raw, config_state = _read_bounded_regular_descriptor_v1(
            config_fd, _MAX_LOCAL_GIT_CONFIG_BYTES_V1, "local Git config"
        )
        config_output = _run_git(
            repository,
            ("config", "--local", "--no-includes", "--null", "--list"),
        ).stdout
        _validate_local_git_config_v1(config_output)
        descriptor = os.fstat(config_fd)
        named = os.stat("config", dir_fd=git_fd, follow_symlinks=False)
        if (
            _filesystem_state_v1(descriptor) != config_state
            or _filesystem_state_v1(named) != config_state
        ):
            raise StaticCensusProtocolError("local Git config path changed")
        for parent, name, descriptor_fd, initial_state in reversed(
            held_directories
        ):
            descriptor = os.fstat(descriptor_fd)
            named = os.stat(name, dir_fd=parent, follow_symlinks=False)
            descriptor_state = _filesystem_state_v1(descriptor)
            if (
                not stat.S_ISDIR(descriptor.st_mode)
                or not stat.S_ISDIR(named.st_mode)
                or descriptor_state != initial_state
                or _filesystem_state_v1(named) != descriptor_state
            ):
                raise StaticCensusProtocolError("Git metadata path changed")
    except OSError as error:
        raise StaticCensusProtocolError(
            "Git metadata is unavailable or unsafe"
        ) from error
    finally:
        if config_fd >= 0:
            os.close(config_fd)
        for _parent, _name, descriptor_fd, _state in reversed(held_directories):
            os.close(descriptor_fd)
        if parent_fd >= 0:
            os.close(parent_fd)


def _repository_path(
    repository: str,
    _path_type: Any = Path,
    _abspath: Any = os.path.abspath,
    _run_git_v1: Any = _run_git,
) -> Path:
    if type(repository) is not str or not repository:
        raise TypeError("repository must be a nonempty exact string")
    requested = _path_type(_abspath(repository))
    # Authenticate the requested path's local repository capabilities before
    # the first Git process is allowed to read that repository's config or
    # object metadata.  The top-level check below must not be the probe that
    # discovers a hostile repository.
    _require_closed_git_repository_v1(requested)
    process = _run_git_v1(requested, ("rev-parse", "--show-toplevel"))
    try:
        text = process.stdout.decode("utf-8", "strict")
    except UnicodeDecodeError as error:
        raise StaticCensusProtocolError("Git top-level path is not UTF-8") from error
    if not text.endswith("\n") or text.count("\n") != 1:
        raise StaticCensusProtocolError("Git top-level response is not canonical")
    observed = _path_type(_abspath(text[:-1]))
    if observed != requested:
        raise StaticCensusProtocolError("repository must be the exact Git top level")
    # Close the path/config race across the top-level query as well.
    _require_closed_git_repository_v1(requested)
    return requested


def _make_repository_resolver_v1(resolve: Any) -> Any:
    """Close the public repository resolver over the authenticated Git runner."""

    def resolve_static_census_repository_v1(repository: str) -> Path:
        return resolve(repository)

    return resolve_static_census_repository_v1


resolve_static_census_repository_v1 = _make_repository_resolver_v1(_repository_path)


def _require_absent_current_source_attributes_v1(repository: Path) -> None:
    directory_flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    root_fd = -1
    seen = set()
    entry_count = 0

    def scan(directory_fd: int, depth: int) -> None:
        nonlocal entry_count
        if depth > _MAX_WORKTREE_ATTRIBUTE_SCAN_DEPTH_V1:
            raise StaticCensusProtocolError(
                "worktree attribute scan exceeds its depth bound"
            )
        before = os.fstat(directory_fd)
        if not stat.S_ISDIR(before.st_mode):
            raise StaticCensusProtocolError("worktree entry is not a directory")
        identity = (before.st_dev, before.st_ino)
        if identity in seen:
            raise StaticCensusProtocolError("worktree directory alias is forbidden")
        seen.add(identity)
        try:
            try:
                with os.scandir(directory_fd) as iterator:
                    names = []
                    for entry in iterator:
                        entry_count += 1
                        if entry_count > _MAX_WORKTREE_ATTRIBUTE_SCAN_ENTRIES_V1:
                            raise StaticCensusProtocolError(
                                "worktree attribute scan exceeds its entry bound"
                            )
                        if type(entry.name) is not str:
                            raise StaticCensusProtocolError(
                                "worktree returned a non-text path"
                            )
                        names.append(entry.name)
            except OSError as error:
                raise StaticCensusProtocolError(
                    "worktree cannot be scanned safely"
                ) from error
            if len(names) != len(set(names)):
                raise StaticCensusProtocolError(
                    "worktree returned duplicate directory entries"
                )
            for name in sorted(names, key=lambda value: value.encode("utf-8")):
                folded_name = name.casefold()
                if folded_name == ".git":
                    continue
                if folded_name == ".gitattributes":
                    raise StaticCensusProtocolError(
                        "current source attribute file is forbidden"
                    )
                named = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                if not (
                    stat.S_ISDIR(named.st_mode)
                    or stat.S_ISREG(named.st_mode)
                    or stat.S_ISLNK(named.st_mode)
                ):
                    raise StaticCensusProtocolError(
                        "production worktree contains a special file"
                    )
                if not stat.S_ISDIR(named.st_mode):
                    continue
                child_fd = -1
                try:
                    child_fd = os.open(name, directory_flags, dir_fd=directory_fd)
                    observed = os.fstat(child_fd)
                    if (
                        not stat.S_ISDIR(observed.st_mode)
                        or (observed.st_dev, observed.st_ino)
                        != (named.st_dev, named.st_ino)
                    ):
                        raise StaticCensusProtocolError(
                            "worktree directory binding changed"
                        )
                    scan(child_fd, depth + 1)
                    descriptor = os.fstat(child_fd)
                    rebound = os.stat(
                        name, dir_fd=directory_fd, follow_symlinks=False
                    )
                    if (
                        not stat.S_ISDIR(rebound.st_mode)
                        or _filesystem_state_v1(rebound)
                        != _filesystem_state_v1(descriptor)
                    ):
                        raise StaticCensusProtocolError(
                            "worktree directory binding changed"
                        )
                finally:
                    if child_fd >= 0:
                        os.close(child_fd)
            if _filesystem_state_v1(os.fstat(directory_fd)) != _filesystem_state_v1(
                before
            ):
                raise StaticCensusProtocolError(
                    "worktree changed during attribute scan"
                )
        finally:
            seen.remove(identity)

    try:
        root_fd = os.open(str(repository), directory_flags)
        scan(root_fd, 0)
    except OSError as error:
        raise StaticCensusProtocolError(
            "current source attribute path is unavailable or unsafe"
        ) from error
    finally:
        if root_fd >= 0:
            os.close(root_fd)


def _require_absent_commit_source_attributes_v1(
    repository: Path, commit: str
) -> None:
    commit = _git_ascii_value(commit, _HEX40, "source commit")
    for path in _SOURCE_ATTRIBUTE_PATHS_V1:
        if _git_path_exists_at_commit(repository, commit, path):
            raise _StaticCensusSourceSemanticError(
                "production source contains a forbidden attribute file"
            )


def _git_ascii(
    repository: Path, arguments: Sequence[str], pattern: re.Pattern, label: str
) -> str:
    raw = _run_git(repository, arguments).stdout
    try:
        value = raw.decode("ascii", "strict").strip()
    except UnicodeDecodeError as error:
        raise StaticCensusProtocolError("{} is not ASCII".format(label)) from error
    if pattern.fullmatch(value) is None:
        raise StaticCensusProtocolError("{} has invalid syntax".format(label))
    return value


def _git_hex40(repository: Path, arguments: Sequence[str], label: str) -> str:
    return _git_ascii(repository, arguments, _HEX40, label)


def _git_object_type_v1(repository: Path, identity: str, label: str) -> str:
    """Read an available object's exact Git type; lookup failures stay ambient."""

    identity = _git_ascii_value(identity, _HEX40, label + " identity")
    raw = _run_git(repository, ("cat-file", "-t", identity)).stdout
    if not raw.endswith(b"\n") or raw.count(b"\n") != 1:
        raise StaticCensusProtocolError("{} type response is malformed".format(label))
    try:
        object_type = raw[:-1].decode("ascii", "strict")
    except UnicodeDecodeError as error:
        raise StaticCensusProtocolError("{} type is not ASCII".format(label)) from error
    if object_type not in ("blob", "commit", "tag", "tree"):
        raise StaticCensusProtocolError("{} type is unrecognized".format(label))
    return object_type


def _git_blob_bytes(repository: Path, commit: str, path: str) -> bytes:
    commit = _git_ascii_value(commit, _HEX40, "source commit")
    path = _safe_repo_path(path)
    process = _run_git(repository, ("cat-file", "blob", "{}:{}".format(commit, path)))
    return bytes(process.stdout)


def _git_ascii_value(value: str, pattern: re.Pattern, label: str) -> str:
    if type(value) is not str or pattern.fullmatch(value) is None:
        raise StaticCensusProtocolError("{} has invalid syntax".format(label))
    return value


def _git_blob_identity(repository: Path, commit: str, path: str) -> str:
    return _git_hex40(
        repository,
        ("rev-parse", "{}:{}".format(commit, _safe_repo_path(path))),
        "Git blob identity",
    )


def _git_path_mode(repository: Path, commit: str, path: str) -> str:
    process = _run_git(
        repository,
        ("ls-tree", "-z", commit, "--", _safe_repo_path(path)),
    )
    raw = process.stdout
    if not raw:
        raise _StaticCensusSourceSemanticError("Git source path is absent")
    if not raw.endswith(b"\0") or raw.count(b"\0") != 1:
        raise StaticCensusProtocolError("Git source path response is malformed")
    header, separator, observed_path = raw[:-1].partition(b"\t")
    fields = header.split(b" ")
    if separator != b"\t" or len(fields) != 3:
        raise StaticCensusProtocolError("Git tree record is malformed")
    try:
        mode = fields[0].decode("ascii", "strict")
        kind = fields[1].decode("ascii", "strict")
        decoded_path = observed_path.decode("utf-8", "strict")
    except UnicodeDecodeError as error:
        raise StaticCensusProtocolError("Git tree record is not textual") from error
    if mode != "100644" or kind != "blob" or decoded_path != path:
        raise _StaticCensusSourceSemanticError(
            "production source must be a nonexecutable regular Git blob"
        )
    return mode


def _git_path_exists_at_commit(
    repository: Path, commit: str, path: str
) -> bool:
    """Distinguish an absent path from an unavailable/corrupt object graph."""

    inspected_path = (
        path if path in _SOURCE_ATTRIBUTE_PATHS_V1 else _safe_repo_path(path)
    )
    process = _run_git(
        repository,
        ("ls-tree", "-z", commit, "--", inspected_path),
    )
    raw = process.stdout
    if not raw:
        return False
    if not raw.endswith(b"\0") or raw.count(b"\0") != 1:
        raise StaticCensusProtocolError("Git source path response is malformed")
    return True


def _module_path_at_commit(
    repository: Path, commit: str, components: Tuple[str, ...]
) -> Optional[str]:
    if not components or any(
        _SAFE_REPO_COMPONENT.fullmatch(component) is None for component in components
    ):
        return None
    candidates = (
        "src/{}.py".format("/".join(components)),
        "src/{}/__init__.py".format("/".join(components)),
    )
    for candidate in candidates:
        if _git_path_exists_at_commit(repository, commit, candidate):
            _git_path_mode(repository, commit, candidate)
            return candidate
    return None


def _package_init_paths_at_commit(
    repository: Path, commit: str, components: Tuple[str, ...]
) -> Tuple[str, ...]:
    paths: List[str] = []
    for length in range(1, len(components) + 1):
        candidate = "src/{}/__init__.py".format("/".join(components[:length]))
        if _git_path_exists_at_commit(repository, commit, candidate):
            _git_path_mode(repository, commit, candidate)
            paths.append(candidate)
    return tuple(paths)


def _local_import_paths_at_commit(
    repository: Path, commit: str, path: str, raw: bytes
) -> Tuple[str, ...]:
    try:
        source = raw.decode("utf-8", "strict")
        tree = ast.parse(source, filename=path)
    except (UnicodeDecodeError, SyntaxError) as error:
        raise _StaticCensusSourceSemanticError(
            "production Python source is invalid"
        ) from error
    module_components = tuple(path[4:-3].split("/"))
    package_components = (
        module_components[:-1]
        if module_components[-1] != "__init__"
        else module_components[:-1]
    )
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            function = node.func
            if (
                isinstance(function, ast.Name)
                and function.id in ("__import__", "eval", "exec")
            ) or (
                isinstance(function, ast.Attribute)
                and function.attr == "import_module"
            ):
                raise _StaticCensusSourceSemanticError(
                    "production closure contains a dynamic import or execution call"
                )
        candidates: List[Tuple[str, ...]] = []
        explicitly_local = False
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "parity_forge" or alias.name.startswith(
                    "parity_forge."
                ):
                    raise _StaticCensusSourceSemanticError(
                        "production closure imports the legacy package"
                    )
                if alias.name == "parity_forge_universe" or alias.name.startswith(
                    "parity_forge_universe."
                ):
                    explicitly_local = True
                    candidates.append(tuple(alias.name.split(".")))
        elif isinstance(node, ast.ImportFrom):
            if node.module == "parity_forge" or (
                node.module is not None and node.module.startswith("parity_forge.")
            ):
                raise _StaticCensusSourceSemanticError(
                    "production closure imports the legacy package"
                )
            if any(alias.name == "*" for alias in node.names):
                raise _StaticCensusSourceSemanticError(
                    "production closure contains a wildcard import"
                )
            if node.level:
                explicitly_local = True
                climb = node.level - 1
                if climb > len(package_components):
                    raise _StaticCensusSourceSemanticError(
                        "relative import escapes the package"
                    )
                base = package_components[: len(package_components) - climb]
                if node.module:
                    base += tuple(node.module.split("."))
                    candidates.append(base)
                else:
                    for alias in node.names:
                        candidates.append(base + tuple(alias.name.split(".")))
            elif node.module == "parity_forge_universe" or (
                node.module is not None
                and node.module.startswith("parity_forge_universe.")
            ):
                explicitly_local = True
                base = tuple(node.module.split("."))
                candidates.append(base)
                for alias in node.names:
                    candidates.append(base + tuple(alias.name.split(".")))
        found = False
        for candidate in candidates:
            resolved = _module_path_at_commit(repository, commit, candidate)
            if resolved is not None:
                found = True
                imports.add(resolved)
                imports.update(
                    _package_init_paths_at_commit(
                        repository, commit, candidate[:-1]
                    )
                )
        if explicitly_local and candidates and not found:
            raise _StaticCensusSourceSemanticError(
                "local import target is absent at the production commit"
            )
    return tuple(sorted(imports, key=lambda item: item.encode("utf-8")))


def _recursive_paths_at_commit(
    repository: Path, commit: str
) -> Tuple[Tuple[str, ...], Dict[str, bytes]]:
    pending = list(PRODUCTION_ENTRYPOINT_PATHS_V1)
    observed = set()
    contents: Dict[str, bytes] = {}
    while pending:
        path = _safe_repo_path(pending.pop())
        if path in observed:
            continue
        _git_path_mode(repository, commit, path)
        raw = _git_blob_bytes(repository, commit, path)
        observed.add(path)
        contents[path] = raw
        if path.endswith(".py"):
            pending.extend(
                imported
                for imported in _local_import_paths_at_commit(
                    repository, commit, path, raw
                )
                if imported not in observed
            )
    ordered = tuple(sorted(observed, key=lambda item: item.encode("utf-8")))
    if ordered != PRODUCTION_CLOSURE_PATHS_V1:
        raise _StaticCensusSourceSemanticError(
            "production recursive closure path set drifted"
        )
    return ordered, contents


def _require_exact_commit(repository: Path, commit: str, tree: str, label: str) -> None:
    observed_commit = _git_hex40(
        repository, ("rev-parse", commit + "^{commit}"), label + " commit"
    )
    observed_tree = _git_hex40(
        repository, ("rev-parse", commit + "^{tree}"), label + " tree"
    )
    if observed_commit != commit or observed_tree != tree:
        raise _StaticCensusSourceSemanticError(
            "{} identity changed".format(label)
        )


def _actual_commit_parents(repository: Path, commit: str) -> Tuple[str, ...]:
    """Read parent headers from the named stored object, never a revision view."""

    commit = _git_ascii_value(commit, _HEX40, "history commit")
    raw = bytes(_run_git(repository, ("cat-file", "commit", commit)).stdout)
    framed = b"commit " + str(len(raw)).encode("ascii") + b"\0" + raw
    if hashlib.sha1(framed).hexdigest() != commit:
        raise StaticCensusProtocolError("Git returned a substituted commit object")
    headers, separator, _message = raw.partition(b"\n\n")
    lines = headers.split(b"\n")
    if separator != b"\n\n" or not lines or re.fullmatch(
        rb"tree [0-9a-f]{40}", lines[0]
    ) is None:
        raise StaticCensusProtocolError("Git commit object is malformed")
    parents: List[str] = []
    for line in lines[1:]:
        if not line.startswith(b"parent"):
            continue
        if re.fullmatch(rb"parent [0-9a-f]{40}", line) is None:
            raise StaticCensusProtocolError("Git commit parent is malformed")
        parents.append(line[7:].decode("ascii"))
    return tuple(parents)


def _require_actual_linear_ancestry(
    repository: Path, source_commit: str, ancestor_commit: str
) -> None:
    """Follow a bounded chain of actual one-parent commit objects."""

    current = _git_ascii_value(source_commit, _HEX40, "source commit")
    ancestor = _git_ascii_value(ancestor_commit, _HEX40, "ancestor commit")
    if current == ancestor:
        raise _StaticCensusSourceSemanticError(
            "production source must strictly descend from preregistration"
        )
    seen = {current}
    for _depth in range(_MAX_SOURCE_ANCESTRY_COMMITS_V1):
        parents = _actual_commit_parents(repository, current)
        if len(parents) > 1:
            raise _StaticCensusSourceSemanticError(
                "production implementation history contains a merge"
            )
        if not parents:
            raise _StaticCensusSourceSemanticError(
                "production source does not descend from preregistration"
            )
        current = parents[0]
        if current == ancestor:
            return
        if current in seen:
            raise _StaticCensusSourceSemanticError(
                "production history contains a cycle"
            )
        seen.add(current)
    raise _StaticCensusSourceSemanticError(
        "production history exceeds its ancestry traversal bound"
    )


def _require_source_history(repository: Path, source_commit: str) -> None:
    _require_exact_commit(
        repository,
        PLAN0015_STATIC_CENSUS_CALCULATION_COMMIT_V1,
        PLAN0015_STATIC_CENSUS_CALCULATION_TREE_V1,
        "calculation checkpoint",
    )
    _require_exact_commit(
        repository,
        PLAN0015_STATIC_CENSUS_PREREGISTRATION_COMMIT_V1,
        PLAN0015_STATIC_CENSUS_PREREGISTRATION_TREE_V1,
        "preregistration checkpoint",
    )
    _require_actual_linear_ancestry(
        repository,
        source_commit,
        PLAN0015_STATIC_CENSUS_PREREGISTRATION_COMMIT_V1,
    )
    changed_raw = _run_git(
        repository,
        (
            "diff",
            "--no-ext-diff",
            "--no-textconv",
            "--name-only",
            "--no-renames",
            "-z",
            PLAN0015_STATIC_CENSUS_PREREGISTRATION_COMMIT_V1,
            source_commit,
            "--",
        ),
    ).stdout
    if changed_raw and not changed_raw.endswith(b"\0"):
        raise _StaticCensusSourceSemanticError(
            "changed-path output is not canonical"
        )
    try:
        changed = tuple(
            sorted(
                (
                    item.decode("utf-8", "strict")
                    for item in changed_raw.split(b"\0")
                    if item
                ),
                key=lambda item: item.encode("utf-8"),
            )
        )
    except UnicodeDecodeError as error:
        raise _StaticCensusSourceSemanticError(
            "changed path is not UTF-8"
        ) from error
    if changed != PERMITTED_IMPLEMENTATION_CHANGED_PATHS_V1:
        raise _StaticCensusSourceSemanticError(
            "production implementation changed-path set drifted"
        )


def _require_frozen_source_bytes(repository: Path, source_commit: str) -> None:
    for path, expected_blob, expected_sha256, expected_size in (
        FROZEN_CALCULATION_FILE_RECORDS_V1
    ):
        _git_path_mode(repository, source_commit, path)
        raw = _git_blob_bytes(repository, source_commit, path)
        if (
            _git_blob_identity(repository, source_commit, path) != expected_blob
            or len(raw) != expected_size
            or hashlib.sha256(raw).hexdigest() != expected_sha256
        ):
            raise _StaticCensusSourceSemanticError(
                "production source changes a sealed calculation blob"
            )
    plan_path = PLAN0015_ACTIVE_PLAN_PATH_V1
    _git_path_mode(repository, source_commit, plan_path)
    plan_raw = _git_blob_bytes(repository, source_commit, plan_path)
    if (
        _git_blob_identity(repository, source_commit, plan_path)
        != PLAN0015_STATIC_CENSUS_PREREGISTERED_PLAN_BLOB_V1
        or len(plan_raw) != PLAN0015_STATIC_CENSUS_PREREGISTERED_PLAN_BYTE_COUNT_V1
        or hashlib.sha256(plan_raw).hexdigest()
        != PLAN0015_STATIC_CENSUS_PREREGISTERED_PLAN_SHA256_V1
    ):
        raise _StaticCensusSourceSemanticError(
            "production source changes the preregistered active plan"
        )


def _build_closure_at_commit(
    repository: Path, source_commit: str, source_tree: str
) -> Dict[str, Any]:
    source_commit = _git_ascii_value(source_commit, _HEX40, "source commit")
    source_tree = _git_ascii_value(source_tree, _HEX40, "source tree")
    _require_exact_commit(repository, source_commit, source_tree, "production source")
    _require_absent_commit_source_attributes_v1(repository, source_commit)
    _require_source_history(repository, source_commit)
    _require_frozen_source_bytes(repository, source_commit)
    paths, contents = _recursive_paths_at_commit(repository, source_commit)
    records = [
        {
            "byte_count": len(contents[path]),
            "git_blob_sha1": _git_blob_identity(repository, source_commit, path),
            "path": path,
            "sha256": hashlib.sha256(contents[path]).hexdigest(),
        }
        for path in paths
    ]
    protocol_records = [
        record
        for record in records
        if record["path"]
        == "src/parity_forge_universe/static_census_protocol.py"
    ]
    if len(protocol_records) != 1:
        raise _StaticCensusSourceSemanticError(
            "production closure lacks its protocol module"
        )
    plan_raw = _git_blob_bytes(
        repository, source_commit, PLAN0015_ACTIVE_PLAN_PATH_V1
    )
    payload = {
        "active_plan_ref": _body_ref(plan_raw),
        "calculation_checkpoint_commit": (
            PLAN0015_STATIC_CENSUS_CALCULATION_COMMIT_V1
        ),
        "calculation_checkpoint_tree": PLAN0015_STATIC_CENSUS_CALCULATION_TREE_V1,
        "ordered_entrypoint_paths": list(PRODUCTION_ENTRYPOINT_PATHS_V1),
        "ordered_file_records": records,
        "preregistration_commit": (
            PLAN0015_STATIC_CENSUS_PREREGISTRATION_COMMIT_V1
        ),
        "preregistration_tree": PLAN0015_STATIC_CENSUS_PREREGISTRATION_TREE_V1,
        "protocol_module_blob_identity": protocol_records[0]["git_blob_sha1"],
        "source_commit": source_commit,
        "source_tree": source_tree,
        "stage_id": PLAN0015_STATIC_CENSUS_STAGE_ID_V1,
    }
    if tuple(payload) != identity_payload_keys_v1("production_closure_root"):
        raise _StaticCensusSourceSemanticError(
            "production closure payload schema drifted"
        )
    return {
        "artifact_type": _PRODUCTION_CLOSURE_ARTIFACT_TYPE,
        "identity": _domain_identity("production_closure_root", payload),
        "payload": payload,
    }


def _untracked_paths_v1(repository: Path) -> Tuple[str, ...]:
    raw = _run_git(repository, ("ls-files", "--others", "-z", "--")).stdout
    if raw and not raw.endswith(b"\0"):
        raise StaticCensusProtocolError("untracked-path output is not canonical")
    try:
        paths = tuple(
            item.decode("utf-8", "strict") for item in raw.split(b"\0") if item
        )
    except UnicodeDecodeError as error:
        raise StaticCensusProtocolError("untracked path is not UTF-8") from error
    if len(paths) != len(set(paths)):
        raise StaticCensusProtocolError("untracked-path output contains duplicates")
    return paths


def _allowed_operational_untracked_v1(path: str, *, allow_evidence: bool) -> bool:
    if path in _PREEXISTING_OPERATIONAL_LOCK_PATHS_V1:
        return True
    evidence_root = PLAN0015_STATIC_CENSUS_EVIDENCE_ROOT_RELATIVE_V1
    return allow_evidence and (
        path == evidence_root or path.startswith(evidence_root + "/")
    )


def _require_clean_head(
    repository: Path, *, allow_evidence: bool = False
) -> Tuple[str, str]:
    if type(allow_evidence) is not bool:
        raise TypeError("allow_evidence must be an exact bool")
    _require_closed_git_repository_v1(repository)
    _require_absent_current_source_attributes_v1(repository)
    for arguments in (
        (
            "diff",
            "--no-ext-diff",
            "--no-textconv",
            "--ignore-submodules=none",
            "--quiet",
            "HEAD",
            "--",
        ),
        (
            "diff",
            "--cached",
            "--no-ext-diff",
            "--no-textconv",
            "--ignore-submodules=none",
            "--quiet",
            "HEAD",
            "--",
        ),
    ):
        process = _run_git(repository, arguments, check=False)
        if process.returncode not in (0, 1):
            raise StaticCensusProtocolError("production source status check failed")
        if process.returncode == 1:
            raise StaticCensusProtocolError(
                "production source repository is not clean"
            )
    if any(
        not _allowed_operational_untracked_v1(
            path, allow_evidence=allow_evidence
        )
        for path in _untracked_paths_v1(repository)
    ):
        raise StaticCensusProtocolError("production source repository is not clean")
    commit = _git_hex40(
        repository, ("rev-parse", "HEAD^{commit}"), "production HEAD commit"
    )
    tree = _git_hex40(
        repository, ("rev-parse", "HEAD^{tree}"), "production HEAD tree"
    )
    return commit, tree


def build_static_census_production_closure_v1(repository: str) -> Dict[str, Any]:
    """Build the exact recursive closure from one clean production HEAD."""

    repository_path = _repository_path(repository)
    source_commit, source_tree = _require_clean_head(repository_path)
    return _json_copy(
        _build_closure_at_commit(repository_path, source_commit, source_tree)
    )


def validate_static_census_production_closure_v1(
    repository: str, value: Any
) -> Dict[str, Any]:
    """Rebuild a stored closure only from its immutable Git source commit."""

    if type(value) is not dict or set(value) != {
        "artifact_type",
        "identity",
        "payload",
    }:
        raise StaticCensusStoredClosureIntegrityError(
            "stored production closure envelope is not exact"
        )
    if value["artifact_type"] != _PRODUCTION_CLOSURE_ARTIFACT_TYPE:
        raise StaticCensusStoredClosureIntegrityError(
            "stored production closure artifact type drifted"
        )
    if type(value["payload"]) is not dict or tuple(value["payload"]) != (
        identity_payload_keys_v1("production_closure_root")
    ):
        raise StaticCensusStoredClosureIntegrityError(
            "stored production closure payload is not exact"
        )
    try:
        stored_identity = _git_ascii_value(
            value["identity"], _HEX64, "stored production closure identity"
        )
        reconstructed_identity = _domain_identity(
            "production_closure_root", value["payload"]
        )
        source_commit = _git_ascii_value(
            value["payload"].get("source_commit"), _HEX40, "stored source commit"
        )
        source_tree = _git_ascii_value(
            value["payload"].get("source_tree"), _HEX40, "stored source tree"
        )
    except StaticCensusProtocolError as error:
        raise StaticCensusStoredClosureIntegrityError(
            "stored production closure identity or source coordinate is invalid"
        ) from error
    if stored_identity != reconstructed_identity:
        raise StaticCensusStoredClosureIntegrityError(
            "stored production closure identity does not reconstruct"
        )
    repository_path = _repository_path(repository)
    # Keep an available-but-mismatched stored commit/tree coordinate in the
    # intrinsic evidence-integrity domain.  A missing/corrupt object or failed
    # Git probe still escapes below as the ordinary protocol/source error.
    if (
        _git_object_type_v1(
            repository_path, source_commit, "stored production source"
        )
        != "commit"
    ):
        raise StaticCensusStoredClosureIntegrityError(
            "stored production source identity is not a commit"
        )
    observed_source_commit = _git_hex40(
        repository_path,
        ("rev-parse", source_commit + "^{commit}"),
        "stored production source commit",
    )
    observed_source_tree = _git_hex40(
        repository_path,
        ("rev-parse", source_commit + "^{tree}"),
        "stored production source tree",
    )
    if observed_source_commit != source_commit or observed_source_tree != source_tree:
        raise StaticCensusStoredClosureIntegrityError(
            "stored production source commit/tree coordinate does not reconstruct"
        )
    try:
        expected = _build_closure_at_commit(
            repository_path, source_commit, source_tree
        )
    except _StaticCensusSourceSemanticError as error:
        raise StaticCensusStoredClosureIntegrityError(
            "stored production closure names unauthorized source"
        ) from error
    try:
        matches = canonical_json_bytes_v1(value) == canonical_json_bytes_v1(expected)
    except StaticCensusProtocolError as error:
        raise StaticCensusStoredClosureIntegrityError(
            "stored production closure is not canonical"
        ) from error
    if not matches:
        raise StaticCensusStoredClosureIntegrityError(
            "stored production closure does not reconstruct from Git"
        )
    return _json_copy(value)


def _read_current_regular(repository: Path, path: str, expected_size: int) -> bytes:
    path = _safe_repo_path(path)
    if type(expected_size) is not int or expected_size < 0:
        raise StaticCensusProtocolError("current source size is invalid")
    directory_flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    file_flags = (
        os.O_RDONLY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    absolute = Path(os.path.abspath(os.fspath(repository)))
    if absolute.parent == absolute:
        raise StaticCensusProtocolError("repository cannot be a filesystem anchor")
    anchor_fd = directory_fd = file_fd = -1
    held_directories: List[Tuple[int, str, int, Tuple[int, ...]]] = []

    def metadata_state(info: Any) -> Tuple[int, ...]:
        return (
            info.st_dev,
            info.st_ino,
            info.st_mode,
            info.st_nlink,
            info.st_size,
            info.st_mtime_ns,
            info.st_ctime_ns,
        )

    def open_directory(parent_fd: int, component: str) -> int:
        child_fd = -1
        try:
            child_fd = os.open(component, directory_flags, dir_fd=parent_fd)
            info = os.fstat(child_fd)
            if not stat.S_ISDIR(info.st_mode):
                raise StaticCensusProtocolError(
                    "current source ancestor is not a directory"
                )
            held_directories.append(
                (parent_fd, component, child_fd, metadata_state(info))
            )
            return child_fd
        except BaseException:
            if child_fd >= 0:
                os.close(child_fd)
            raise

    try:
        anchor_fd = os.open(absolute.anchor, directory_flags)
        directory_fd = anchor_fd
        for component in absolute.parts[1:]:
            directory_fd = open_directory(directory_fd, component)
        for component in path.split("/")[:-1]:
            directory_fd = open_directory(directory_fd, component)
        file_name = path.split("/")[-1]
        file_fd = os.open(file_name, file_flags, dir_fd=directory_fd)
        before = os.fstat(file_fd)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or stat.S_IMODE(before.st_mode) not in _READABLE_SOURCE_MODES
            or before.st_size != expected_size
        ):
            raise StaticCensusProtocolError(
                "current source must be an exact-size singly-linked regular file"
            )
        chunks = []
        remaining = expected_size
        while remaining:
            chunk = os.read(file_fd, min(1024 * 1024, remaining))
            if not chunk:
                raise StaticCensusProtocolError(
                    "current source was truncated while reading"
                )
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(file_fd, 1):
            raise StaticCensusProtocolError("current source grew while reading")
        after = os.fstat(file_fd)
        before_state = metadata_state(before)
        after_state = metadata_state(after)
        if before_state != after_state:
            raise StaticCensusProtocolError("current source changed while reading")
        named_file = os.stat(file_name, dir_fd=directory_fd, follow_symlinks=False)
        if not stat.S_ISREG(named_file.st_mode) or metadata_state(named_file) != after_state:
            raise StaticCensusProtocolError("current source path changed while reading")
        for parent_fd, component, child_fd, initial_state in reversed(
            held_directories
        ):
            descriptor = os.fstat(child_fd)
            named = os.stat(component, dir_fd=parent_fd, follow_symlinks=False)
            descriptor_state = metadata_state(descriptor)
            if (
                not stat.S_ISDIR(descriptor.st_mode)
                or not stat.S_ISDIR(named.st_mode)
                or descriptor_state != initial_state
                or metadata_state(named) != descriptor_state
            ):
                raise StaticCensusProtocolError(
                    "current source ancestor changed while reading"
                )
        return b"".join(chunks)
    except OSError as error:
        raise StaticCensusProtocolError(
            "current source path is unavailable or unsafe"
        ) from error
    finally:
        if file_fd >= 0:
            os.close(file_fd)
        for _parent_fd, _component, child_fd, _initial_state in reversed(
            held_directories
        ):
            os.close(child_fd)
        if anchor_fd >= 0:
            os.close(anchor_fd)


def _require_reseal_worktree(repository: Path) -> None:
    _require_closed_git_repository_v1(repository)
    _require_absent_current_source_attributes_v1(repository)
    for arguments, label in (
        (
            (
                "diff",
                "--no-ext-diff",
                "--no-textconv",
                "--ignore-submodules=none",
                "--quiet",
                "HEAD",
                "--",
            ),
            "tracked worktree",
        ),
        (
            (
                "diff",
                "--cached",
                "--no-ext-diff",
                "--no-textconv",
                "--ignore-submodules=none",
                "--quiet",
                "HEAD",
                "--",
            ),
            "index",
        ),
    ):
        process = _run_git(repository, arguments, check=False)
        if process.returncode == 1:
            raise StaticCensusProtocolError("{} changed during production".format(label))
        if process.returncode != 0:
            raise StaticCensusProtocolError("{} status check failed".format(label))
    if any(
        not _allowed_operational_untracked_v1(path, allow_evidence=True)
        for path in _untracked_paths_v1(repository)
    ):
        raise StaticCensusProtocolError(
            "untracked path outside the fixed evidence root appeared"
        )


def _require_reseal_head(repository: Path, source_commit: str, source_tree: str) -> None:
    head_commit = _git_hex40(
        repository, ("rev-parse", "HEAD^{commit}"), "current HEAD commit"
    )
    head_tree = _git_hex40(
        repository, ("rev-parse", "HEAD^{tree}"), "current HEAD tree"
    )
    if head_commit != source_commit or head_tree != source_tree:
        raise StaticCensusProtocolError(
            "production HEAD changed after closure reservation"
        )


def reseal_static_census_production_closure_v1(
    repository: str, value: Any
) -> None:
    """Require current HEAD, tree, bytes, and non-evidence dirt to stay fixed."""

    repository_path = _repository_path(repository)
    closure = validate_static_census_production_closure_v1(repository, value)
    payload = closure["payload"]
    _require_reseal_head(
        repository_path, payload["source_commit"], payload["source_tree"]
    )
    _require_reseal_worktree(repository_path)
    for record in payload["ordered_file_records"]:
        if type(record) is not dict or set(record) != {
            "byte_count",
            "git_blob_sha1",
            "path",
            "sha256",
        }:
            raise StaticCensusProtocolError("production source record is not exact")
        raw = _read_current_regular(
            repository_path, record["path"], record["byte_count"]
        )
        if (
            len(raw) != record["byte_count"]
            or hashlib.sha256(raw).hexdigest() != record["sha256"]
        ):
            raise StaticCensusProtocolError("current production closure bytes drifted")
    plan_raw = _read_current_regular(
        repository_path,
        PLAN0015_ACTIVE_PLAN_PATH_V1,
        payload["active_plan_ref"]["byte_count"],
    )
    if _body_ref(plan_raw) != payload["active_plan_ref"]:
        raise StaticCensusProtocolError("current active-plan bytes drifted")
    _require_reseal_worktree(repository_path)
    _require_reseal_head(
        repository_path, payload["source_commit"], payload["source_tree"]
    )


def authenticate_static_census_recovery_closure_v1(
    repository: str,
) -> Dict[str, Any]:
    """Build and reseal current source while admitting only this stage's evidence."""

    repository_path = _repository_path(repository)
    source_commit, source_tree = _require_clean_head(
        repository_path, allow_evidence=True
    )
    closure = _json_copy(
        _build_closure_at_commit(repository_path, source_commit, source_tree)
    )
    reseal_static_census_production_closure_v1(repository, closure)
    return closure


# Short aliases are the shared stage/evidence contract names.
PROTOCOL_ID_V1 = PLAN0015_STATIC_CENSUS_PROTOCOL_ID_V1
PROTOCOL_ROOT_V1 = PLAN0015_STATIC_CENSUS_PROTOCOL_ROOT_V1
PROTOCOL_ARTIFACT_TYPE_V1 = _PROTOCOL_ARTIFACT_TYPE
PRODUCTION_CLOSURE_ARTIFACT_TYPE_V1 = _PRODUCTION_CLOSURE_ARTIFACT_TYPE
EVIDENCE_PROTOCOL_ID_V1 = PLAN0015_STATIC_CENSUS_EVIDENCE_PROTOCOL_ID_V1
EVIDENCE_ROOT_RELATIVE_V1 = PLAN0015_STATIC_CENSUS_EVIDENCE_ROOT_RELATIVE_V1
STAGE_ID_V1 = PLAN0015_STATIC_CENSUS_STAGE_ID_V1
STAGE_PROTOCOL_ID_V1 = PLAN0015_STATIC_CENSUS_STAGE_PROTOCOL_ID_V1
ACTIVE_PLAN_PATH_V1 = PLAN0015_ACTIVE_PLAN_PATH_V1


def _make_guarded_protocol_apis_v1(
    namespace: Dict[str, Any],
    resolve_repository_impl: Any,
    build_protocol_impl: Any,
    validate_protocol_impl: Any,
    build_closure_impl: Any,
    validate_closure_impl: Any,
    reseal_closure_impl: Any,
    authenticate_recovery_impl: Any,
    *,
    _error: Any = StaticCensusProtocolError,
    _getattr: Any = getattr,
    _type: Any = type,
) -> Tuple[Any, ...]:
    """Close public APIs over implementations and a fixed runtime catalog."""

    unsupported = object()

    def freeze(value: Any) -> Any:
        value_type = _type(value)
        if value is None or value_type in (bool, int, str, bytes):
            return (value_type, value)
        if value_type is tuple:
            frozen = tuple(freeze(item) for item in value)
            if unsupported in frozen:
                return unsupported
            return (tuple, frozen)
        if value_type is list:
            frozen = tuple(freeze(item) for item in value)
            if unsupported in frozen:
                return unsupported
            return (list, frozen)
        if value_type is dict:
            frozen_items = tuple(
                (freeze(key), freeze(item)) for key, item in value.items()
            )
            if any(
                frozen_item is unsupported
                for pair in frozen_items
                for frozen_item in pair
            ):
                return unsupported
            return (dict, frozen_items)
        return unsupported

    public_names = (
        "resolve_static_census_repository_v1",
        "build_static_census_protocol_v1",
        "validate_static_census_protocol_v1",
        "build_static_census_production_closure_v1",
        "validate_static_census_production_closure_v1",
        "reseal_static_census_production_closure_v1",
        "authenticate_static_census_recovery_closure_v1",
    )
    identity_bindings: Tuple[Tuple[str, Any], ...] = ()
    value_bindings: Tuple[Tuple[str, Any], ...] = ()

    dependency_identity_bindings = tuple(
        (owner, name, _getattr(owner, name))
        for owner, names in (
            (ast, ("Attribute", "Call", "Import", "ImportFrom", "Name", "parse", "walk")),
            (hashlib, ("sha1", "sha256")),
            (json, ("dumps", "loads")),
            (
                os,
                (
                    "close",
                    "fspath",
                    "fstat",
                    "killpg",
                    "open",
                    "pread",
                    "read",
                    "scandir",
                    "set_blocking",
                    "stat",
                ),
            ),
            (os.path, ("abspath", "isabs", "realpath")),
            (selectors, ("DefaultSelector",)),
            (stat, ("S_IMODE", "S_ISDIR", "S_ISLNK", "S_ISREG")),
            (subprocess, ("CompletedProcess", "Popen", "TimeoutExpired", "run")),
            (time, ("monotonic",)),
        )
        for name in names
    )
    dependency_value_bindings = tuple(
        (owner, name, _getattr(owner, name, None))
        for owner, names in (
            (
                os,
                (
                    "O_DIRECTORY",
                    "O_NOFOLLOW",
                    "O_NONBLOCK",
                    "O_RDONLY",
                    "devnull",
                ),
            ),
            (selectors, ("EVENT_READ",)),
            (signal, ("SIGKILL",)),
            (subprocess, ("DEVNULL", "PIPE")),
        )
        for name in names
    )
    builtin_bindings = tuple(
        (name, value)
        for name, value in (
            ("BaseException", BaseException),
            ("BlockingIOError", BlockingIOError),
            ("FileNotFoundError", FileNotFoundError),
            ("KeyError", KeyError),
            ("OSError", OSError),
            ("ProcessLookupError", ProcessLookupError),
            ("SyntaxError", SyntaxError),
            ("TypeError", TypeError),
            ("UnicodeDecodeError", UnicodeDecodeError),
            ("UnicodeError", UnicodeError),
            ("ValueError", ValueError),
            ("any", any),
            ("bool", bool),
            ("bytearray", bytearray),
            ("bytes", bytes),
            ("dict", dict),
            ("float", float),
            ("getattr", getattr),
            ("id", id),
            ("int", int),
            ("isinstance", isinstance),
            ("len", len),
            ("list", list),
            ("min", min),
            ("object", object),
            ("range", range),
            ("set", set),
            ("sorted", sorted),
            ("str", str),
            ("tuple", tuple),
            ("type", type),
        )
    )

    def require_runtime_bindings_v1() -> None:
        if any(
            namespace.get(name) is not expected
            for name, expected in identity_bindings
        ):
            raise _error("protocol runtime binding changed")
        if any(
            freeze(namespace.get(name, unsupported)) != expected
            for name, expected in value_bindings
        ):
            raise _error("protocol runtime value changed")
        if any(
            _getattr(owner, name, None) is not expected
            for owner, name, expected in dependency_identity_bindings
        ):
            raise _error("protocol dependency binding changed")
        for owner, name, expected in dependency_value_bindings:
            observed = _getattr(owner, name, None)
            if _type(observed) is not _type(expected) or observed != expected:
                raise _error("protocol dependency value changed")
        if any(
            name in namespace and namespace[name] is not expected
            for name, expected in builtin_bindings
        ):
            raise _error("protocol builtin binding changed")

    def invoke(implementation: Any, *arguments: Any) -> Any:
        require_runtime_bindings_v1()
        result = implementation(*arguments)
        require_runtime_bindings_v1()
        return result

    def resolve_static_census_repository_v1(repository: str) -> Path:
        return invoke(resolve_repository_impl, repository)

    def build_static_census_protocol_v1() -> Dict[str, Any]:
        return invoke(build_protocol_impl)

    def validate_static_census_protocol_v1(value: Any) -> Dict[str, Any]:
        return invoke(validate_protocol_impl, value)

    def build_static_census_production_closure_v1(repository: str) -> Dict[str, Any]:
        return invoke(build_closure_impl, repository)

    def validate_static_census_production_closure_v1(
        repository: str, value: Any
    ) -> Dict[str, Any]:
        return invoke(validate_closure_impl, repository, value)

    def reseal_static_census_production_closure_v1(
        repository: str, value: Any
    ) -> None:
        return invoke(reseal_closure_impl, repository, value)

    def authenticate_static_census_recovery_closure_v1(
        repository: str,
    ) -> Dict[str, Any]:
        return invoke(authenticate_recovery_impl, repository)

    wrappers = {
        "resolve_static_census_repository_v1": resolve_static_census_repository_v1,
        "build_static_census_protocol_v1": build_static_census_protocol_v1,
        "validate_static_census_protocol_v1": validate_static_census_protocol_v1,
        "build_static_census_production_closure_v1": (
            build_static_census_production_closure_v1
        ),
        "validate_static_census_production_closure_v1": (
            validate_static_census_production_closure_v1
        ),
        "reseal_static_census_production_closure_v1": (
            reseal_static_census_production_closure_v1
        ),
        "authenticate_static_census_recovery_closure_v1": (
            authenticate_static_census_recovery_closure_v1
        ),
    }
    identity_bindings = tuple(
        (name, wrappers[name] if name in wrappers else value)
        for name, value in namespace.items()
        if not name.startswith("__")
        and name not in (
            "_make_guarded_protocol_apis_v1",
        )
    )
    value_bindings = tuple(
        (name, frozen)
        for name, value in namespace.items()
        if not name.startswith("__")
        and name not in public_names
        and (frozen := freeze(value)) is not unsupported
    )
    return (
        require_runtime_bindings_v1,
        resolve_repository_impl,
        build_protocol_impl,
        validate_protocol_impl,
        build_closure_impl,
        validate_closure_impl,
        reseal_closure_impl,
        authenticate_recovery_impl,
        resolve_static_census_repository_v1,
        build_static_census_protocol_v1,
        validate_static_census_protocol_v1,
        build_static_census_production_closure_v1,
        validate_static_census_production_closure_v1,
        reseal_static_census_production_closure_v1,
        authenticate_static_census_recovery_closure_v1,
    )


(
    _require_protocol_runtime_bindings_v1,
    _resolve_static_census_repository_core_v1,
    _build_static_census_protocol_core_v1,
    _validate_static_census_protocol_core_v1,
    _build_static_census_production_closure_core_v1,
    _validate_static_census_production_closure_core_v1,
    _reseal_static_census_production_closure_core_v1,
    _authenticate_static_census_recovery_closure_core_v1,
    resolve_static_census_repository_v1,
    build_static_census_protocol_v1,
    validate_static_census_protocol_v1,
    build_static_census_production_closure_v1,
    validate_static_census_production_closure_v1,
    reseal_static_census_production_closure_v1,
    authenticate_static_census_recovery_closure_v1,
) = _make_guarded_protocol_apis_v1(
    globals(),
    resolve_static_census_repository_v1,
    build_static_census_protocol_v1,
    validate_static_census_protocol_v1,
    build_static_census_production_closure_v1,
    validate_static_census_production_closure_v1,
    reseal_static_census_production_closure_v1,
    authenticate_static_census_recovery_closure_v1,
)


__all__ = (
    "ACTIVE_PLAN_PATH_V1",
    "EVIDENCE_PROTOCOL_ID_V1",
    "EVIDENCE_ROOT_RELATIVE_V1",
    "FROZEN_CALCULATION_FILE_RECORDS_V1",
    "PERMITTED_IMPLEMENTATION_CHANGED_PATHS_V1",
    "PLAN0015_ACTIVE_PLAN_PATH_V1",
    "PLAN0015_STATIC_CENSUS_CALCULATION_COMMIT_V1",
    "PLAN0015_STATIC_CENSUS_CALCULATION_TREE_V1",
    "PLAN0015_STATIC_CENSUS_EVIDENCE_PROTOCOL_ID_V1",
    "PLAN0015_STATIC_CENSUS_EVIDENCE_ROOT_RELATIVE_V1",
    "PLAN0015_STATIC_CENSUS_PREREGISTRATION_COMMIT_V1",
    "PLAN0015_STATIC_CENSUS_PREREGISTRATION_TREE_V1",
    "PLAN0015_STATIC_CENSUS_PROTOCOL_CANONICAL_BYTE_COUNT_V1",
    "PLAN0015_STATIC_CENSUS_PROTOCOL_CANONICAL_SHA256_V1",
    "PLAN0015_STATIC_CENSUS_PROTOCOL_ID_V1",
    "PLAN0015_STATIC_CENSUS_PROTOCOL_ROOT_V1",
    "PLAN0015_STATIC_CENSUS_PROTOCOL_VERSION_V1",
    "PLAN0015_STATIC_CENSUS_STAGE_ID_V1",
    "PLAN0015_STATIC_CENSUS_STAGE_PROTOCOL_ID_V1",
    "PRODUCTION_CLOSURE_PATHS_V1",
    "PRODUCTION_CLOSURE_ARTIFACT_TYPE_V1",
    "PRODUCTION_ENTRYPOINT_PATHS_V1",
    "PROTOCOL_ARTIFACT_TYPE_V1",
    "PROTOCOL_ID_V1",
    "PROTOCOL_ROOT_V1",
    "STAGE_ID_V1",
    "STAGE_PROTOCOL_ID_V1",
    "STATIC_CENSUS_REPORT_MAX_BYTES_V1",
    "STATIC_CENSUS_REPORT_MAX_JSON_DEPTH_V1",
    "STATIC_CENSUS_REPORT_MAX_JSON_NODES_V1",
    "StaticCensusProtocolError",
    "StaticCensusStoredClosureIntegrityError",
    "authenticate_static_census_recovery_closure_v1",
    "build_static_census_production_closure_v1",
    "build_static_census_protocol_v1",
    "canonical_json_bytes_v1",
    "identity_domain_v1",
    "identity_payload_keys_v1",
    "resolve_static_census_repository_v1",
    "reseal_static_census_production_closure_v1",
    "validate_static_census_production_closure_v1",
    "validate_static_census_protocol_v1",
)
