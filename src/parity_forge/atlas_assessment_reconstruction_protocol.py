"""Fixed Plan-0014 protocol and production-source closure.

This module contains commitments only.  It neither opens an evidence store nor
reconstructs the Plan-0013 report.  In particular it never imports a Plan-0013
stage facade, solver, agent, game runner, telemetry generator, selector, or
candidate-block builder.

The production closure is deliberately a new Plan-0014 artifact.  Its builder
binds a clean HEAD, the active-plan blob, the reviewed slice-1 repair blobs, and
the complete recursive local-import closure of the one Plan-0014 entrypoint.
Its validator works from immutable Git objects, so later public recovery does
not require HEAD to remain at the production commit.  ``reseal`` is the stronger
pre-publication check: it additionally requires current closure/plan bytes and
HEAD to remain equal to the reserved source.
"""

from __future__ import annotations

import ast
import hashlib
import os
from pathlib import Path
import re
import stat
import subprocess
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple

from .atlas_evidence import (
    EvidenceIntegrityError,
    canonical_json_bytes,
    capture_clean_head,
    domain_identity,
    load_canonical_json_bytes,
)


PLAN0014_RECONSTRUCTION_PROTOCOL_VERSION_V1 = 1
PLAN0014_RECONSTRUCTION_PROTOCOL_ID_V1 = (
    "plan0014-plan0013-assessment-reconstruction-protocol-v1"
)
PLAN0014_RECONSTRUCTION_EVIDENCE_PROTOCOL_ID_V1 = (
    "plan0014-plan0013-assessment-reconstruction-evidence-v1"
)
PLAN0014_RECONSTRUCTION_STAGE_ID_V1 = "PLAN0013_ASSESSMENT_RECONSTRUCTION"
PLAN0014_RECONSTRUCTION_STAGE_PROTOCOL_ID_V1 = (
    "plan0014-plan0013-assessment-reconstruction-stage-v1"
)
PLAN0014_RECONSTRUCTION_EVIDENCE_ROOT_RELATIVE_V1 = (
    "experiments/runs/plan0014-plan0013-assessment-reconstruction-evidence-v1"
)
PLAN0014_ACTIVE_PLAN_PATH_V1 = (
    "docs/plans/active/0014-post-outcome-atlas-assessment-reconstruction.md"
)

# Short aliases are the shared evidence/attestation contract names.
EVIDENCE_PROTOCOL_ID_V1 = PLAN0014_RECONSTRUCTION_EVIDENCE_PROTOCOL_ID_V1
STAGE_ID_V1 = PLAN0014_RECONSTRUCTION_STAGE_ID_V1
STAGE_PROTOCOL_ID_V1 = PLAN0014_RECONSTRUCTION_STAGE_PROTOCOL_ID_V1
EVIDENCE_ROOT_RELATIVE_V1 = PLAN0014_RECONSTRUCTION_EVIDENCE_ROOT_RELATIVE_V1
ACTIVE_PLAN_PATH_V1 = PLAN0014_ACTIVE_PLAN_PATH_V1

PLAN0013_EVIDENCE_ROOT_RELATIVE_V1 = (
    "experiments/runs/plan0013-atlas-development-evidence-v2"
)
PLAN0013_PROTOCOL_ID_V1 = "plan0013-six-family-development-protocol-v1"
PLAN0013_PROTOCOL_ROOT_V1 = (
    "8126c33f787e63aef07e48fc25a3ed950f4650495e2e512c96d9e33583b8f04c"
)
PLAN0013_PROTOCOL_REF_V1 = {
    "byte_count": 2_220_598,
    "sha256": "b732f174399acb8d52b2f5dddefc36a9f45e0560e94428b85f55998089bc9229",
}
PLAN0013_BOOTSTRAP_ROOT_V1 = (
    "96c7e239c0d96fbd43ac9e592303b3ed72f8576fbdca88c92b8ff2a37d80ea22"
)
PLAN0013_MANIFEST_ROOT_V1 = (
    "ffbb225619855440b83540b7712356f8f3f8b5f18d2ee4ab87b178b86b04f7c3"
)
PLAN0013_SOURCE_COMMIT_V1 = "5e6a865a5d4fe34d4b70eca2e6c546faaf1c5ec1"
PLAN0013_SOURCE_TREE_V1 = "17468fd2d9f986765bd15852753d8f168a482fad"

PLAN0013_ARCHIVE_COMMIT_V1 = "c47db19b8ef3ad762979baa116cbb50a525cc730"
PLAN0013_ARCHIVE_TREE_V1 = "377eac4e151412f94d00332f9ff6f263e8306baa"
PLAN0013_ARCHIVED_EVIDENCE_TREE_V1 = (
    "40f4b65f913a842a43e1b3a092a40cbb9933e489"
)
PLAN0013_ARCHIVED_EVIDENCE_FILE_COUNT_V1 = 152_680
PLAN0013_ARCHIVED_EVIDENCE_TOTAL_BLOB_BYTES_V1 = 601_787_372

PLAN0014_REPAIR_CHECKPOINT_COMMIT_V1 = (
    "734cda958edebdb0b8279fae72148aaf39254a8a"
)
PLAN0014_REPAIR_CHECKPOINT_TREE_V1 = (
    "6fc95500b4b76aaf184db27f924999b023bf42c5"
)
PLAN0014_REPAIR_CHECKPOINT_BLOBS_V1: Tuple[Tuple[str, str], ...] = (
    (
        "src/parity_forge/atlas_assessment_core.py",
        "22eb27f0d688eaa8e56ac4648e1ce37a6b7a551a",
    ),
    (
        "src/parity_forge/atlas_assessment_reconstruction.py",
        "9d2b0ecbae19ee736baeefa0cc1aaee717d4bac2",
    ),
    (
        "src/parity_forge/atlas_assessment_stage.py",
        "ccfb70615cffcb921cd671999cf6ab2cc9170ab4",
    ),
    (
        "src/parity_forge/atlas_evidence.py",
        "b732c2ebf48efdbe96656d610f22da1d0472e104",
    ),
)

# The first complete Plan-0014 implementation checkpoint was rejected before
# any production invocation after an independent audit demonstrated that an
# expected FIFO could block an O_RDONLY open before the regular-file check.
# Keep that rejected boundary explicit rather than silently replacing it.
PLAN0014_REJECTED_IMPLEMENTATION_CHECKPOINT_COMMIT_V1 = (
    "37d95eb94bb50db5e3876c7e949a9cb1c47d58ee"
)
PLAN0014_REJECTED_IMPLEMENTATION_CHECKPOINT_TREE_V1 = (
    "87e470042a98696347d4314a4668201f01aecdfb"
)
PLAN0014_REJECTED_IMPLEMENTATION_PROTOCOL_ROOT_V1 = (
    "5424b2d066843f5e52d70e8395ed594dda1760c3447080e7b515dbccb78f8458"
)
PLAN0014_REJECTED_IMPLEMENTATION_PROTOCOL_CANONICAL_SHA256_V1 = (
    "adb409bac1bdc2eb80e8331b29238b89f41fe3705b9137947d90b0bbb4f6fa88"
)

# Reader hardening is an operational/type-safety change, not a third
# assessment repair.  The protocol module itself necessarily changes again to
# record this checkpoint, so its historical blob is pinned here while the four
# other production modules must remain byte-identical at the final source.
PLAN0014_READER_HARDENING_CHECKPOINT_COMMIT_V1 = (
    "bcec70193963da8f88fff7d4dc34133cf31ed057"
)
PLAN0014_READER_HARDENING_CHECKPOINT_TREE_V1 = (
    "69553e0798d8b229bd3ce8522a77ef83fff44cb0"
)
PLAN0014_READER_HARDENING_PROTOCOL_ID_V1 = (
    "plan0014-nonscientific-reader-hardening-v1"
)
PLAN0014_READER_HARDENING_CHECKPOINT_BLOBS_V1: Tuple[
    Tuple[str, str], ...
] = (
    (
        "src/parity_forge/atlas_assessment_reconstruction_attestation.py",
        "11a11945a93a6edfca67443efd4b83c3b7e42054",
    ),
    (
        "src/parity_forge/atlas_assessment_reconstruction_evidence.py",
        "a09d28917eef1acfdfe2cce8e3dcf2026ec84648",
    ),
    (
        "src/parity_forge/atlas_assessment_reconstruction_protocol.py",
        "aec49c4b7e25b5b08131c43e87f71c60fb3506c9",
    ),
    (
        "src/parity_forge/atlas_assessment_reconstruction_stage.py",
        "19c22f8b1d9dcf548314520fc7236307aa99b9bf",
    ),
    (
        "src/parity_forge/atlas_evidence.py",
        "220d336bf7bc9f9b9b3d667f4034a1dde8cc9bda",
    ),
)
PLAN0014_READER_HARDENING_CHECKPOINT_CHANGED_PATHS_V1 = (
    "src/parity_forge/atlas_assessment_reconstruction_attestation.py",
    "src/parity_forge/atlas_assessment_reconstruction_evidence.py",
    "src/parity_forge/atlas_assessment_reconstruction_protocol.py",
    "src/parity_forge/atlas_assessment_reconstruction_stage.py",
    "src/parity_forge/atlas_evidence.py",
    "tests/test_atlas_assessment_reconstruction_attestation.py",
    "tests/test_atlas_assessment_reconstruction_evidence.py",
    "tests/test_atlas_assessment_reconstruction_protocol.py",
    "tests/test_atlas_evidence_read_only.py",
)

# Production equivalence is deliberately split.  The first tuple preserves the
# three scientific repair/facade blobs from the reviewed repair checkpoint.
# The historical atlas_evidence blob remains in
# PLAN0014_REPAIR_CHECKPOINT_BLOBS_V1, but production must use its separately
# reviewed nonblocking hardening blob instead.
PLAN0014_REPAIR_PRODUCTION_EQUIVALENCE_BLOBS_V1 = (
    PLAN0014_REPAIR_CHECKPOINT_BLOBS_V1[0],
    PLAN0014_REPAIR_CHECKPOINT_BLOBS_V1[1],
    PLAN0014_REPAIR_CHECKPOINT_BLOBS_V1[2],
)
PLAN0014_READER_HARDENING_PRODUCTION_EQUIVALENCE_BLOBS_V1 = (
    PLAN0014_READER_HARDENING_CHECKPOINT_BLOBS_V1[0],
    PLAN0014_READER_HARDENING_CHECKPOINT_BLOBS_V1[1],
    PLAN0014_READER_HARDENING_CHECKPOINT_BLOBS_V1[3],
    PLAN0014_READER_HARDENING_CHECKPOINT_BLOBS_V1[4],
)

# These pre-existing recursive dependencies are not part of either permitted
# repair.  Pinning them separately prevents a later production checkpoint from
# changing the scientific calculation, DSL, replay engine, or symmetry logic
# while still satisfying the exact 13-path closure allow-list.
PLAN0014_UNCHANGED_PRODUCTION_DEPENDENCY_BLOBS_V1: Tuple[
    Tuple[str, str], ...
] = (
    (
        "src/parity_forge/__init__.py",
        "dd354f2588f985a66dd0014de5805b7ca1bc7781",
    ),
    (
        "src/parity_forge/atlas_protocol.py",
        "5dee4a675d7d3cd475e26d8eca9fbab9c0212284",
    ),
    (
        "src/parity_forge/atlas_stage_data.py",
        "740a6e1b84d0afe7752a2db3366735343f576fbe",
    ),
    (
        "src/parity_forge/dsl.py",
        "647b300dbce9a23f963a72c85aa239988c4740bf",
    ),
    (
        "src/parity_forge/engine.py",
        "9c811c4b1edcdec80001d41deeb57b7f0f0183f2",
    ),
    (
        "src/parity_forge/symmetry.py",
        "daf30190cbf6b7d8f9a68581ca6fdb6ef9657e89",
    ),
)

PLAN0014_CLOSED_DEFECT_IDS_V1 = (
    "PF-0014-D01-EXACT-LIST-PRODUCER",
    "PF-0014-D02-ZERO-LEGAL-OBSERVATION-ACCOUNTING",
)
CLOSED_DEFECT_IDS_V1 = PLAN0014_CLOSED_DEFECT_IDS_V1
PLAN0014_REPAIR_PROTOCOL_ID_V1 = "plan0014-two-defect-assessment-repair-v1"
REPAIR_PROTOCOL_ID_V1 = PLAN0014_REPAIR_PROTOCOL_ID_V1

PLAN0013_ORDERED_TERMINALS_V1: Tuple[Tuple[str, str, str, str], ...] = (
    (
        "OUTCOME_FREE_DEVELOPMENT_MANIFEST",
        "plan0013-atlas-development-manifest-v1",
        "COMPLETED",
        "5ee92d2b10e39683ee790add3066ce71604a2232e8ad6f8508b3ddea71f17e46",
    ),
    (
        "EXACT_ALL_288",
        "plan0013-atlas-development-exact-v1",
        "COMPLETED",
        "6c575e5099b424eb1785e9aee424820e6f9c9e66a5c3fda557d23dad65da6c45",
    ),
    (
        "RANDOM_ALL_18432_GAMES",
        "plan0013-atlas-development-random-v1",
        "COMPLETED",
        "bafc4a527e72be41cf76f33dede82e87116cb1301012678555a8afca48dae9b6",
    ),
    (
        "TERMINAL_DEPTH1_ALL_18432_GAMES",
        "plan0013-atlas-development-terminal-depth1-v1",
        "COMPLETED",
        "f5d1e9374fcc3936c4eb7ddaab6c012931fc276f6c3c5d2adce7f44e778be226",
    ),
    (
        "REPLAY_TELEMETRY_COMPLETE_TRACES_ONLY",
        "plan0013-atlas-development-telemetry-v1",
        "COMPLETED",
        "2869fc5564b80a3bcc0734f031394144073dd8a41f0ceef4d2acf3b80af8f670",
    ),
    (
        "ASSESSMENT_AND_INSPECTION",
        "plan0013-atlas-development-assessment-v1",
        "FAILED",
        "812b8c4bfc9ffbb2fefa750361ebd33d998e9504ea9032b83b95049dc4f8e889",
    ),
)

PLAN0013_ORDERED_TERMINAL_REFS_V1: Tuple[Tuple[str, int], ...] = (
    ("bf6b815017771d5fb13b27692564c096ec05e2b0bacd2addefef40b3fa466db6", 15_571),
    ("2b9ac302d90710dc5a9dce991c22b935d479ba88238069657d6eb26efda7fba6", 42_887),
    ("d8cf86fea6308e0aaae775040dbcf77971649b5cb13c21d9c0ec1dff6ab4aed9", 128_849),
    ("c4399eb5d98ba5a62603e4ab0d996ca233d2cead9389ec0e407243b13278263e", 387_521),
    ("12cbc7f701ccbd07db8ae1909c37297b82fcb54bb5355931a5fee398791f6ed9", 1_161_965),
    ("0f6486c7cd75889fd055d133f4dba9ce116468b3ac904508d77eaf46574789e9", 3_484_941),
)

PLAN0013_ASSESSMENT_RESERVATION_ID_V1 = (
    "91138600dcc40b649e527161ab1d4d49c87e6600928823cf8857c8a17f5f2a6d"
)
PLAN0013_ASSESSMENT_ATTEMPT_ID_V1 = (
    "bffac6f25d063e09839f35e2b09c72c3d3853178029113e8f1b7dcef95219c96"
)
PLAN0013_ASSESSMENT_RESERVATION_REF_V1 = {
    "byte_count": 1_740_429,
    "sha256": "4d7122ae326b3a4fd04eb3014237f3db5cef429ef7296e53b41ca6b730acd3af",
}
PLAN0013_ASSESSMENT_ATTEMPT_REF_V1 = {
    "byte_count": 1_743_221,
    "sha256": "71c9145aa37f5564138727bb25961223a27b94dc71a01430f98a1a2b493ccbe0",
}
PLAN0013_ASSESSMENT_FAILURE_REF_V1 = {
    "byte_count": 504,
    "sha256": "9db7d724cd0d692c0a4347ebfb47579fd758dcb86c0011107ae2e5d98b69385d",
}
PLAN0013_ASSESSMENT_PRODUCTION_CLOSURE_ROOT_V1 = (
    "f7792895c5ad0085f841cc7dce64d0f631df6d5ed8abdd3961ed08334df5b2e4"
)
PLAN0013_ASSESSMENT_FAILURE_V1 = {
    "exception_module": "builtins",
    "exception_type": "TypeError",
    "kind": "ASSESSMENT_STAGE_EXCEPTION",
    "message": "admissible slots must be an exact array",
}


_IDENTITY_DOMAINS_V1: Dict[str, bytes] = {
    kind: (
        "parity-forge:plan0014:plan0013-assessment-reconstruction:{}:v1\0".format(
            kind.replace("_", "-")
        ).encode("ascii")
    )
    for kind in (
        "repair_protocol_root",
        "protocol_root",
        "source_binding_root",
        "archive_live_inventory_root",
        "production_closure_root",
        "bootstrap_root",
        "reservation_id",
        "attempt_id",
        "orphaned_id",
        "terminal_seal",
        "inspection_selection_root",
        "attestation_root",
    )
}

_IDENTITY_PAYLOAD_KEYS_V1: Dict[str, Tuple[str, ...]] = {
    "protocol_root": (
        "active_plan_path",
        "artifact_type",
        "attestation_contract",
        "capability_contract",
        "evidence_protocol_id",
        "evidence_protocol_version",
        "evidence_store_relative_path",
        "identity_schemas",
        "lifecycle_contract",
        "production_closure_contract",
        "protocol_id",
        "protocol_version",
        "repair_protocol",
        "source_chain",
        "stage",
    ),
    "repair_protocol_root": (
        "closed_defect_ids",
        "integration_correction_count",
        "repair_protocol_id",
        "repair_protocol_version",
        "repairs",
        "scientific_rule_change_count",
    ),
    "production_closure_root": (
        "active_plan_ref",
        "ordered_entrypoint_paths",
        "ordered_file_records",
        "protocol_module_blob_identity",
        "repair_checkpoint_commit",
        "repair_checkpoint_tree",
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
        "repair_checkpoint_commit",
        "repair_checkpoint_tree",
        "source_binding_root",
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
        "source_binding_root",
        "stage_id",
        "stage_protocol_id",
    ),
    "attempt_id": (
        "attempt_index",
        "production_closure_root",
        "reservation_id",
        "source_commit",
        "source_tree",
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
        "reservation_id_or_null",
        "stage_id",
        "stage_protocol_id",
    ),
    "archive_live_inventory_root": (
        "ordered_file_records",
    ),
    "source_binding_root": (
        "archive",
        "archive_live_inventory",
        "bootstrap",
        "evidence_store_relative_path",
        "failed_assessment",
        "ordered_stage_terminals",
        "repair_checkpoint",
        "source_binding_id",
        "source_binding_version",
    ),
    "inspection_selection_root": (
        "inner_report_body_ref",
        "inspection_selection",
        "inspection_selection_body_ref",
    ),
    "attestation_root": (
        "artifact_type",
        "attestation_id",
        "attestation_version",
        "claim_level",
        "execution_counts",
        "epistemic_status",
        "inner_report",
        "inspection_selection",
        "original_stage_completed_body_count",
        "original_stage_lifecycle",
        "original_stage_terminal_identity",
        "reconstruction_protocol_id",
        "reconstruction_protocol_root",
        "repair_boundary",
        "repair_protocol_id",
        "repair_protocol_root",
        "source_binding_root",
    ),
}


def identity_domain_v1(kind: str) -> bytes:
    """Return one fixed domain; unknown or non-exact names fail closed."""

    if type(kind) is not str:
        raise TypeError("identity kind must be an exact string")
    try:
        return _IDENTITY_DOMAINS_V1[kind]
    except KeyError as error:
        raise ValueError("unknown Plan-0014 identity kind") from error


def identity_payload_keys_v1(kind: str) -> Tuple[str, ...]:
    """Return the exact payload-key tuple for one identity schema."""

    if type(kind) is not str:
        raise TypeError("identity kind must be an exact string")
    try:
        return _IDENTITY_PAYLOAD_KEYS_V1[kind]
    except KeyError as error:
        raise ValueError("unknown Plan-0014 identity kind") from error


def _repair_protocol_payload_v1() -> Dict[str, Any]:
    return {
        "closed_defect_ids": list(PLAN0014_CLOSED_DEFECT_IDS_V1),
        "integration_correction_count": 2,
        "repair_protocol_id": PLAN0014_REPAIR_PROTOCOL_ID_V1,
        "repair_protocol_version": 1,
        "repairs": [
            {
                "boundary": "telemetry-ledger-admissibility-producer",
                "container_contract": "exact-builtins-list",
                "defect_id": PLAN0014_CLOSED_DEFECT_IDS_V1[0],
                "semantic_change": "NONE",
            },
            {
                "bin_zero_decision_contribution": 0,
                "defect_id": PLAN0014_CLOSED_DEFECT_IDS_V1[1],
                "identities": [
                    "sum(legal_count_bins)==legal_observation_count",
                    "bin[1]+bin[2+]==decision_count",
                    "legal_observation_count==decision_count+bin[0]",
                ],
                "semantic_change": "AUTHORITATIVE-TERMINAL-OBSERVATION-ACCOUNTING",
            },
        ],
        "scientific_rule_change_count": 0,
    }


PLAN0014_REPAIR_PROTOCOL_ROOT_V1 = (
    "4dcc7ee7663c1b1975c13b6bded28d6ff66d4273cc529d97e111b645bfe6f9dc"
)
REPAIR_PROTOCOL_ROOT_V1 = PLAN0014_REPAIR_PROTOCOL_ROOT_V1


PRODUCTION_ENTRYPOINT_PATHS_V1 = (
    "src/parity_forge/atlas_assessment_reconstruction_stage.py",
)
PRODUCTION_CLOSURE_PATHS_V1 = (
    "src/parity_forge/__init__.py",
    "src/parity_forge/atlas_assessment_core.py",
    "src/parity_forge/atlas_assessment_reconstruction.py",
    "src/parity_forge/atlas_assessment_reconstruction_attestation.py",
    "src/parity_forge/atlas_assessment_reconstruction_evidence.py",
    "src/parity_forge/atlas_assessment_reconstruction_protocol.py",
    "src/parity_forge/atlas_assessment_reconstruction_stage.py",
    "src/parity_forge/atlas_evidence.py",
    "src/parity_forge/atlas_protocol.py",
    "src/parity_forge/atlas_stage_data.py",
    "src/parity_forge/dsl.py",
    "src/parity_forge/engine.py",
    "src/parity_forge/symmetry.py",
)
PRODUCTION_FORBIDDEN_PATHS_V1 = (
    "src/parity_forge/agency.py",
    "src/parity_forge/agents.py",
    "src/parity_forge/atlas.py",
    "src/parity_forge/atlas_assessment_stage.py",
    "src/parity_forge/atlas_depth1_stage.py",
    "src/parity_forge/atlas_exact_stage.py",
    "src/parity_forge/atlas_manifest_stage.py",
    "src/parity_forge/atlas_projection.py",
    "src/parity_forge/atlas_random_stage.py",
    "src/parity_forge/atlas_telemetry_stage.py",
    "src/parity_forge/play.py",
    "src/parity_forge/solver.py",
    "src/parity_forge/terminal_search.py",
)

_PROTOCOL_MODULE_PATH_V1 = (
    "src/parity_forge/atlas_assessment_reconstruction_protocol.py"
)
_HEX40 = re.compile(r"\A[0-9a-f]{40}\Z")
_HEX64 = re.compile(r"\A[0-9a-f]{64}\Z")


def _body_ref(value: bytes) -> Dict[str, Any]:
    return {"byte_count": len(value), "sha256": hashlib.sha256(value).hexdigest()}


def _source_chain_protocol_v1() -> Dict[str, Any]:
    return {
        "archive": {
            "archive_commit": PLAN0013_ARCHIVE_COMMIT_V1,
            "archive_evidence_tree": PLAN0013_ARCHIVED_EVIDENCE_TREE_V1,
            "archive_parent_commit": PLAN0013_SOURCE_COMMIT_V1,
            "archive_tree": PLAN0013_ARCHIVE_TREE_V1,
            "live_inventory_calculation_record_keys": [
                "path",
                "mode",
                "git_blob_sha1",
                "byte_count",
            ],
            "live_inventory_persistence": (
                "COMPACT-ROOT-COUNT-TOTAL-BYTES-ONLY-NO-ORDERED-RECORDS"
            ),
            "tracked_evidence_file_count": PLAN0013_ARCHIVED_EVIDENCE_FILE_COUNT_V1,
            "tracked_evidence_total_blob_bytes": (
                PLAN0013_ARCHIVED_EVIDENCE_TOTAL_BLOB_BYTES_V1
            ),
        },
        "old_source": {
            "source_commit": PLAN0013_SOURCE_COMMIT_V1,
            "source_tree": PLAN0013_SOURCE_TREE_V1,
        },
        "reader_hardening_checkpoint": {
            "assessment_integration_correction_count": 0,
            "commit": PLAN0014_READER_HARDENING_CHECKPOINT_COMMIT_V1,
            "hardening_id": PLAN0014_READER_HARDENING_PROTOCOL_ID_V1,
            "ordered_blob_bindings": [
                {"git_blob_sha1": blob, "path": path}
                for path, blob in (
                    PLAN0014_READER_HARDENING_CHECKPOINT_BLOBS_V1
                )
            ],
            "ordered_changed_paths": list(
                PLAN0014_READER_HARDENING_CHECKPOINT_CHANGED_PATHS_V1
            ),
            "parent_commit": (
                PLAN0014_REJECTED_IMPLEMENTATION_CHECKPOINT_COMMIT_V1
            ),
            "purpose": (
                "FAIL-CLOSED-NONBLOCKING-REGULAR-FILE-AND-SOURCE-READS"
            ),
            "scientific_rule_change_count": 0,
            "tree": PLAN0014_READER_HARDENING_CHECKPOINT_TREE_V1,
        },
        "rejected_initial_implementation": {
            "canonical_protocol_sha256": (
                PLAN0014_REJECTED_IMPLEMENTATION_PROTOCOL_CANONICAL_SHA256_V1
            ),
            "commit": PLAN0014_REJECTED_IMPLEMENTATION_CHECKPOINT_COMMIT_V1,
            "finding": "P2-BLOCKING-SPECIAL-FILE-OPEN-BEFORE-TYPE-CHECK",
            "parent_commit": PLAN0014_REPAIR_CHECKPOINT_COMMIT_V1,
            "production_invocation_count": 0,
            "protocol_root": PLAN0014_REJECTED_IMPLEMENTATION_PROTOCOL_ROOT_V1,
            "status": "REJECTED_PRE_RUN",
            "tree": PLAN0014_REJECTED_IMPLEMENTATION_CHECKPOINT_TREE_V1,
        },
        "repair_checkpoint": {
            "commit": PLAN0014_REPAIR_CHECKPOINT_COMMIT_V1,
            "ordered_blob_bindings": [
                {"git_blob_sha1": blob, "path": path}
                for path, blob in PLAN0014_REPAIR_CHECKPOINT_BLOBS_V1
            ],
            "ordered_unchanged_dependency_blob_bindings": [
                {"git_blob_sha1": blob, "path": path}
                for path, blob in (
                    PLAN0014_UNCHANGED_PRODUCTION_DEPENDENCY_BLOBS_V1
                )
            ],
            "parent_commit": PLAN0013_ARCHIVE_COMMIT_V1,
            "tree": PLAN0014_REPAIR_CHECKPOINT_TREE_V1,
        },
        "final_source_contract": {
            "exact_single_parent_commit": (
                PLAN0014_READER_HARDENING_CHECKPOINT_COMMIT_V1
            ),
            "protocol_module_binding": (
                "SELF-BOUND-BY-FINAL-PRODUCTION-CLOSURE-RECORD"
            ),
            "reader_hardening_equivalence_count": len(
                PLAN0014_READER_HARDENING_PRODUCTION_EQUIVALENCE_BLOBS_V1
            ),
            "scientific_repair_equivalence_count": len(
                PLAN0014_REPAIR_PRODUCTION_EQUIVALENCE_BLOBS_V1
            ),
        },
        "v2_evidence": {
            "assessment_attempt_id": PLAN0013_ASSESSMENT_ATTEMPT_ID_V1,
            "assessment_attempt_ref": dict(PLAN0013_ASSESSMENT_ATTEMPT_REF_V1),
            "assessment_failure": dict(PLAN0013_ASSESSMENT_FAILURE_V1),
            "assessment_failure_ref": dict(PLAN0013_ASSESSMENT_FAILURE_REF_V1),
            "assessment_production_closure_root": (
                PLAN0013_ASSESSMENT_PRODUCTION_CLOSURE_ROOT_V1
            ),
            "assessment_reservation_id": PLAN0013_ASSESSMENT_RESERVATION_ID_V1,
            "assessment_reservation_ref": dict(
                PLAN0013_ASSESSMENT_RESERVATION_REF_V1
            ),
            "bootstrap_root": PLAN0013_BOOTSTRAP_ROOT_V1,
            "evidence_root_relative": PLAN0013_EVIDENCE_ROOT_RELATIVE_V1,
            "manifest_root": PLAN0013_MANIFEST_ROOT_V1,
            "ordered_terminals": [
                {
                    "lifecycle": lifecycle,
                    "stage_id": stage_id,
                    "stage_protocol_id": stage_protocol_id,
                    "terminal_ref": {
                        "byte_count": terminal_ref[1],
                        "sha256": terminal_ref[0],
                    },
                    "terminal_identity": terminal_identity,
                }
                for (
                    stage_id,
                    stage_protocol_id,
                    lifecycle,
                    terminal_identity,
                ), terminal_ref in zip(
                    PLAN0013_ORDERED_TERMINALS_V1,
                    PLAN0013_ORDERED_TERMINAL_REFS_V1,
                )
            ],
            "protocol_id": PLAN0013_PROTOCOL_ID_V1,
            "protocol_ref": dict(PLAN0013_PROTOCOL_REF_V1),
            "protocol_root": PLAN0013_PROTOCOL_ROOT_V1,
        },
    }


def _protocol_unsigned_v1() -> Dict[str, Any]:
    repair = _repair_protocol_payload_v1()
    return {
        "active_plan_path": PLAN0014_ACTIVE_PLAN_PATH_V1,
        "artifact_type": "PLAN0014_ASSESSMENT_RECONSTRUCTION_PROTOCOL_V1",
        "attestation_contract": {
            "claim_level": (
                "POST_FAILURE_CALCULATION_ONLY_NO_FAIRNESS_STRATEGY_FUN_OR_CONFIRMATION_CLAIM"
            ),
            "epistemic_status": (
                "POST_FAILURE_MECHANICAL_RECONSTRUCTION_NOT_CONFIRMATION"
            ),
            "inner_report_claim_level": "FAMILY_FRONTIER_SIGNAL_NOT_FAIR_GAME",
            "inner_report_is_unmodified_plan0013_value": True,
            "original_stage_lifecycle": "FAILED",
            "protocol_pins_outcome_digest": False,
            "public_validation_rebuilds_from_old_raw_evidence": True,
        },
        "capability_contract": {
            "allowed": [
                "authenticate-archived-evidence",
                "validate-retained-traces",
                "reconstruct-frozen-report-and-inspection",
                "publish-plan0014-attestation-only",
            ],
            "forbidden": [
                "call-plan0013-run-or-recover",
                "generate-gameplay",
                "invoke-solver-or-agent",
                "generate-telemetry",
                "invoke-candidate-selector",
                "read-export-allocate-or-evaluate-confirmation-candidate-block",
            ],
            "zero_count_names": [
                "outcome_generation_count",
                "solver_invocation_count",
                "sampled_game_generation_count",
                "telemetry_generation_count",
                "candidate_block_access_count",
                "candidate_block_export_count",
                "candidate_block_evaluation_count",
                "candidate_block_allocation_count",
            ],
        },
        "evidence_protocol_id": EVIDENCE_PROTOCOL_ID_V1,
        "evidence_protocol_version": 1,
        "evidence_store_relative_path": EVIDENCE_ROOT_RELATIVE_V1,
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
                "completed-or-failure-or-orphaned",
                "terminal-seal",
            ],
            "bootstrap_envelope": "artifact_type-identity-payload-references",
            "completed_precludes_failure_replacement": True,
            "partial_evidence": "FORBIDDEN",
            "recovery_calculation_resume": "FORBIDDEN",
            "terminal_run_action": "VERIFIED_NOOP",
        },
        "production_closure_contract": {
            "artifact_type": "PLAN0014_RECONSTRUCTION_PRODUCTION_CLOSURE_V1",
            "ordered_entrypoint_paths": list(PRODUCTION_ENTRYPOINT_PATHS_V1),
            "ordered_exact_recursive_paths": list(PRODUCTION_CLOSURE_PATHS_V1),
            "ordered_forbidden_paths": list(PRODUCTION_FORBIDDEN_PATHS_V1),
            "repair_blob_equivalence_required": True,
            "repair_blob_equivalence_scope": (
                "THREE-SCIENTIFIC-REPAIR-AND-HISTORICAL-FACADE-BLOBS"
            ),
            "reader_hardening_blob_equivalence_required": True,
            "reader_hardening_blob_equivalence_scope": (
                "FOUR-NONPROTOCOL-PRODUCTION-BLOBS"
            ),
        },
        "protocol_id": PLAN0014_RECONSTRUCTION_PROTOCOL_ID_V1,
        "protocol_version": PLAN0014_RECONSTRUCTION_PROTOCOL_VERSION_V1,
        "repair_protocol": {
            **repair,
            "repair_protocol_root": PLAN0014_REPAIR_PROTOCOL_ROOT_V1,
        },
        "source_chain": _source_chain_protocol_v1(),
        "stage": {
            "command_arguments": ["command", "--repository"],
            "commands": ["run", "recover"],
            "stage_id": STAGE_ID_V1,
            "stage_index": 0,
            "stage_protocol_id": STAGE_PROTOCOL_ID_V1,
        },
    }


def _computed_protocol_v1() -> Dict[str, Any]:
    unsigned = _protocol_unsigned_v1()
    return {
        **unsigned,
        "protocol_root": domain_identity(identity_domain_v1("protocol_root"), unsigned),
    }


PLAN0014_RECONSTRUCTION_PROTOCOL_ROOT_V1 = (
    "b412e0af7f36850f06199a3d21897195b26d1eb4ef417616debca57a3185d38d"
)
PLAN0014_RECONSTRUCTION_PROTOCOL_CANONICAL_SHA256_V1 = (
    "0aeb2bf4a3e6d0caa048f4e4238981738ebfb0287c63f938e86b47d9984ecfd1"
)


def build_plan0014_assessment_reconstruction_protocol_v1() -> Dict[str, Any]:
    """Build the exact fixed protocol and enforce its two golden digests."""

    if domain_identity(
        identity_domain_v1("repair_protocol_root"), _repair_protocol_payload_v1()
    ) != PLAN0014_REPAIR_PROTOCOL_ROOT_V1:
        raise EvidenceIntegrityError("Plan-0014 repair protocol root drifted")
    value = _computed_protocol_v1()
    raw = canonical_json_bytes(value)
    if value["protocol_root"] != PLAN0014_RECONSTRUCTION_PROTOCOL_ROOT_V1:
        raise EvidenceIntegrityError("Plan-0014 protocol root drifted")
    if hashlib.sha256(raw).hexdigest() != (
        PLAN0014_RECONSTRUCTION_PROTOCOL_CANONICAL_SHA256_V1
    ):
        raise EvidenceIntegrityError("Plan-0014 protocol canonical SHA-256 drifted")
    return load_canonical_json_bytes(raw)


def validate_plan0014_assessment_reconstruction_protocol_v1(
    value: Any,
) -> Dict[str, Any]:
    """Require exact typed canonical equivalence with the fixed protocol."""

    try:
        raw = canonical_json_bytes(value)
    except (TypeError, ValueError) as error:
        raise EvidenceIntegrityError("Plan-0014 protocol is not canonical JSON") from error
    expected = build_plan0014_assessment_reconstruction_protocol_v1()
    if raw != canonical_json_bytes(expected):
        raise EvidenceIntegrityError("Plan-0014 protocol differs from the fixed value")
    return load_canonical_json_bytes(raw)


def _exact_hex(value: Any, length: int, label: str) -> str:
    pattern = _HEX40 if length == 40 else _HEX64
    if type(value) is not str or pattern.fullmatch(value) is None:
        raise EvidenceIntegrityError("{} must be lowercase hex".format(label))
    return value


def _exact_dict(value: Any, keys: Iterable[str], label: str) -> Dict[str, Any]:
    if type(value) is not dict or set(value) != set(keys):
        raise EvidenceIntegrityError("{} schema drifted".format(label))
    return value


def _repository_path(repository: str) -> Path:
    if type(repository) is not str or not repository:
        raise ValueError("repository must be a nonempty exact string")
    requested = Path(os.path.abspath(repository))
    output = _run_git(requested, ("rev-parse", "--show-toplevel"))
    try:
        top = Path(output.decode("utf-8", "strict").strip())
    except UnicodeDecodeError as error:
        raise EvidenceIntegrityError("Git top level is not UTF-8") from error
    if top != requested:
        raise EvidenceIntegrityError("repository must be the exact Git top level")
    return requested


def _run_git(
    repository: Path, arguments: Sequence[str], *, check: bool = True
) -> bytes:
    process = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )
    if check and process.returncode != 0:
        raise EvidenceIntegrityError(
            "Git source check failed: {}".format(
                process.stderr.decode("utf-8", "replace").strip()
            )
        )
    return process.stdout


def _git_hex(repository: Path, arguments: Sequence[str], label: str) -> str:
    try:
        value = _run_git(repository, arguments).decode("ascii", "strict").strip()
    except UnicodeDecodeError as error:
        raise EvidenceIntegrityError("{} is not ASCII".format(label)) from error
    return _exact_hex(value, 40, label)


def _git_bytes(repository: Path, commit: str, path: str) -> bytes:
    return _run_git(repository, ("show", "{}:{}".format(commit, path)))


def _git_path_kind(repository: Path, commit: str, path: str) -> Optional[str]:
    process = subprocess.run(
        ["git", "-C", str(repository), "cat-file", "-t", "{}:{}".format(commit, path)],
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )
    if process.returncode != 0:
        return None
    try:
        return process.stdout.decode("ascii", "strict").strip()
    except UnicodeDecodeError as error:
        raise EvidenceIntegrityError("Git object type is not ASCII") from error


def _require_fixed_git_chain(repository: Path, source_commit: str) -> None:
    checks = (
        (PLAN0013_SOURCE_COMMIT_V1, PLAN0013_SOURCE_TREE_V1, "Plan-0013 source"),
        (PLAN0013_ARCHIVE_COMMIT_V1, PLAN0013_ARCHIVE_TREE_V1, "Plan-0013 archive"),
        (
            PLAN0014_REPAIR_CHECKPOINT_COMMIT_V1,
            PLAN0014_REPAIR_CHECKPOINT_TREE_V1,
            "Plan-0014 repair checkpoint",
        ),
        (
            PLAN0014_REJECTED_IMPLEMENTATION_CHECKPOINT_COMMIT_V1,
            PLAN0014_REJECTED_IMPLEMENTATION_CHECKPOINT_TREE_V1,
            "Plan-0014 rejected implementation checkpoint",
        ),
        (
            PLAN0014_READER_HARDENING_CHECKPOINT_COMMIT_V1,
            PLAN0014_READER_HARDENING_CHECKPOINT_TREE_V1,
            "Plan-0014 reader-hardening checkpoint",
        ),
    )
    for commit, tree, label in checks:
        if _git_hex(repository, ("rev-parse", commit + "^{commit}"), label + " commit") != commit:
            raise EvidenceIntegrityError(label + " commit drifted")
        if _git_hex(repository, ("rev-parse", commit + "^{tree}"), label + " tree") != tree:
            raise EvidenceIntegrityError(label + " tree drifted")
    archive_parents = _run_git(
        repository, ("show", "-s", "--format=%P", PLAN0013_ARCHIVE_COMMIT_V1)
    ).decode("ascii", "strict").strip().split()
    if archive_parents != [PLAN0013_SOURCE_COMMIT_V1]:
        raise EvidenceIntegrityError("archive commit parent drifted")
    repair_parents = _run_git(
        repository,
        ("show", "-s", "--format=%P", PLAN0014_REPAIR_CHECKPOINT_COMMIT_V1),
    ).decode("ascii", "strict").strip().split()
    if repair_parents != [PLAN0013_ARCHIVE_COMMIT_V1]:
        raise EvidenceIntegrityError("repair checkpoint parent drifted")
    rejected_parents = _run_git(
        repository,
        (
            "show",
            "-s",
            "--format=%P",
            PLAN0014_REJECTED_IMPLEMENTATION_CHECKPOINT_COMMIT_V1,
        ),
    ).decode("ascii", "strict").strip().split()
    if rejected_parents != [PLAN0014_REPAIR_CHECKPOINT_COMMIT_V1]:
        raise EvidenceIntegrityError("rejected implementation parent drifted")
    hardening_parents = _run_git(
        repository,
        (
            "show",
            "-s",
            "--format=%P",
            PLAN0014_READER_HARDENING_CHECKPOINT_COMMIT_V1,
        ),
    ).decode("ascii", "strict").strip().split()
    if hardening_parents != [
        PLAN0014_REJECTED_IMPLEMENTATION_CHECKPOINT_COMMIT_V1
    ]:
        raise EvidenceIntegrityError("reader-hardening checkpoint parent drifted")
    source_parents = _run_git(
        repository, ("show", "-s", "--format=%P", source_commit)
    ).decode("ascii", "strict").strip().split()
    if source_parents != [PLAN0014_READER_HARDENING_CHECKPOINT_COMMIT_V1]:
        raise EvidenceIntegrityError(
            "production source must be the direct reader-hardening child"
        )

    for commit, label in (
        (PLAN0013_ARCHIVE_COMMIT_V1, "archive"),
        (PLAN0014_REPAIR_CHECKPOINT_COMMIT_V1, "repair"),
        (
            PLAN0014_REJECTED_IMPLEMENTATION_CHECKPOINT_COMMIT_V1,
            "rejected implementation",
        ),
        (
            PLAN0014_READER_HARDENING_CHECKPOINT_COMMIT_V1,
            "reader hardening",
        ),
        (source_commit, "production"),
    ):
        observed_subtree = _git_hex(
            repository,
            (
                "rev-parse",
                commit + ":" + PLAN0013_EVIDENCE_ROOT_RELATIVE_V1,
            ),
            label + " evidence subtree",
        )
        if observed_subtree != PLAN0013_ARCHIVED_EVIDENCE_TREE_V1:
            raise EvidenceIntegrityError("archived V2 evidence subtree drifted")

    for commit in (
        PLAN0014_REJECTED_IMPLEMENTATION_CHECKPOINT_COMMIT_V1,
        PLAN0014_READER_HARDENING_CHECKPOINT_COMMIT_V1,
        source_commit,
    ):
        if _git_path_kind(
            repository,
            commit,
            PLAN0014_RECONSTRUCTION_EVIDENCE_ROOT_RELATIVE_V1,
        ) is not None:
            raise EvidenceIntegrityError(
                "Plan-0014 production evidence predates its audited source"
            )

    for path, expected_blob in (
        PLAN0014_REPAIR_CHECKPOINT_BLOBS_V1
        + PLAN0014_UNCHANGED_PRODUCTION_DEPENDENCY_BLOBS_V1
    ):
        observed = _git_hex(
            repository,
            ("rev-parse", PLAN0014_REPAIR_CHECKPOINT_COMMIT_V1 + ":" + path),
            "repair checkpoint blob",
        )
        if observed != expected_blob:
            raise EvidenceIntegrityError("reviewed repair checkpoint blob drifted")
    for path, expected_blob in PLAN0014_READER_HARDENING_CHECKPOINT_BLOBS_V1:
        observed = _git_hex(
            repository,
            (
                "rev-parse",
                PLAN0014_READER_HARDENING_CHECKPOINT_COMMIT_V1 + ":" + path,
            ),
            "reader-hardening checkpoint blob",
        )
        if observed != expected_blob:
            raise EvidenceIntegrityError("reviewed reader-hardening blob drifted")
    try:
        hardening_changed_paths = tuple(
            _run_git(
                repository,
                (
                    "diff-tree",
                    "--no-commit-id",
                    "--name-only",
                    "--no-renames",
                    "-r",
                    PLAN0014_READER_HARDENING_CHECKPOINT_COMMIT_V1,
                ),
            )
            .decode("utf-8", "strict")
            .splitlines()
        )
    except UnicodeDecodeError as error:
        raise EvidenceIntegrityError(
            "reader-hardening changed paths are not UTF-8"
        ) from error
    if hardening_changed_paths != (
        PLAN0014_READER_HARDENING_CHECKPOINT_CHANGED_PATHS_V1
    ):
        raise EvidenceIntegrityError("reader-hardening change surface drifted")


def _safe_repo_path(value: Any) -> str:
    if type(value) is not str or not value or value.startswith(("/", "\\")):
        raise EvidenceIntegrityError("closure path must be repository-relative")
    if "\\" in value:
        raise EvidenceIntegrityError("closure path has a noncanonical separator")
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise EvidenceIntegrityError("closure path escapes the repository")
    try:
        value.encode("ascii", "strict")
    except UnicodeEncodeError as error:
        raise EvidenceIntegrityError("closure path must be ASCII") from error
    return value


def _module_parts(path: str) -> Tuple[str, ...]:
    parts = Path(path).parts
    if len(parts) < 3 or parts[:2] != ("src", "parity_forge") or not path.endswith(".py"):
        raise EvidenceIntegrityError("closure Python path is outside parity_forge")
    result = list(parts[1:])
    if result[-1] == "__init__.py":
        result = result[:-1]
    else:
        result[-1] = result[-1][:-3]
    return tuple(result)


def _module_path_at_commit(
    repository: Path, commit: str, module_parts: Sequence[str]
) -> Optional[str]:
    if not module_parts or module_parts[0] != "parity_forge":
        return None
    base = Path("src").joinpath(*module_parts)
    candidates = (base.with_suffix(".py").as_posix(), (base / "__init__.py").as_posix())
    matches = [
        path for path in candidates if _git_path_kind(repository, commit, path) == "blob"
    ]
    if len(matches) > 1:
        raise EvidenceIntegrityError("ambiguous local module at production commit")
    return None if not matches else matches[0]


def _package_init_paths_at_commit(
    repository: Path, commit: str, module_parts: Sequence[str]
) -> Tuple[str, ...]:
    result = []
    for count in range(1, len(module_parts) + 1):
        path = (Path("src") / Path(*module_parts[:count]) / "__init__.py").as_posix()
        if _git_path_kind(repository, commit, path) == "blob":
            result.append(path)
    return tuple(result)


def _local_import_paths_at_commit(
    repository: Path, commit: str, path: str, raw: bytes
) -> Tuple[str, ...]:
    try:
        tree = ast.parse(raw.decode("utf-8", "strict"), filename=path)
    except (SyntaxError, UnicodeDecodeError) as error:
        raise EvidenceIntegrityError("closure Python source is not parseable UTF-8") from error
    module_parts = _module_parts(path)
    current_package = module_parts if path.endswith("/__init__.py") else module_parts[:-1]
    imports = set()
    for node in ast.walk(tree):
        # The closure must be recoverable from statically resolved imports.  It
        # is not enough to reject only direct ``__import__(...)`` calls: aliases
        # imported from importlib/builtins, saved function objects, and
        # eval/exec can otherwise conceal a local capability edge from the
        # recursive walk.  None of these reflective facilities is needed by the
        # fixed report-only path, so reject their presence rather than trying to
        # prove each possible data flow.
        if isinstance(node, ast.Import) and any(
            alias.name.split(".", 1)[0] in ("builtins", "importlib")
            for alias in node.names
        ):
            raise EvidenceIntegrityError(
                "dynamic imports are forbidden in production closure"
            )
        if isinstance(node, ast.ImportFrom) and (
            (node.module or "").split(".", 1)[0] in ("builtins", "importlib")
            or any(
                alias.name in ("__import__", "compile", "eval", "exec")
                for alias in node.names
            )
        ):
            raise EvidenceIntegrityError(
                "dynamic imports are forbidden in production closure"
            )
        if isinstance(node, ast.Name) and node.id in (
            "__builtins__",
            "__import__",
        ):
            raise EvidenceIntegrityError(
                "dynamic imports are forbidden in production closure"
            )
        if isinstance(node, ast.Attribute) and node.attr in (
            "__import__",
            "import_module",
        ):
            raise EvidenceIntegrityError(
                "dynamic imports are forbidden in production closure"
            )
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in ("compile", "eval", "exec")
        ):
            raise EvidenceIntegrityError(
                "dynamic imports are forbidden in production closure"
            )
        candidates = []
        explicitly_local = False
        if isinstance(node, ast.Import):
            for alias in node.names:
                parts = tuple(alias.name.split("."))
                if parts and parts[0] == "parity_forge":
                    explicitly_local = True
                    candidates.append(parts)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                explicitly_local = True
                remove = node.level - 1
                if remove > len(current_package):
                    raise EvidenceIntegrityError("relative import escapes parity_forge")
                base = current_package[: len(current_package) - remove]
                if node.module:
                    base = base + tuple(node.module.split("."))
                    candidates.append(base)
                    for alias in node.names:
                        if alias.name != "*":
                            candidates.append(base + tuple(alias.name.split(".")))
                else:
                    for alias in node.names:
                        if alias.name == "*":
                            raise EvidenceIntegrityError("relative star import is forbidden")
                        candidates.append(base + tuple(alias.name.split(".")))
            elif node.module and node.module.split(".")[0] == "parity_forge":
                explicitly_local = True
                base = tuple(node.module.split("."))
                candidates.append(base)
                for alias in node.names:
                    if alias.name != "*":
                        candidates.append(base + tuple(alias.name.split(".")))
        found = False
        for candidate in candidates:
            resolved = _module_path_at_commit(repository, commit, candidate)
            if resolved is not None:
                found = True
                imports.add(resolved)
                imports.update(
                    _package_init_paths_at_commit(repository, commit, candidate[:-1])
                )
        if explicitly_local and candidates and not found:
            if _module_path_at_commit(repository, commit, candidates[0]) is None:
                raise EvidenceIntegrityError("local import target is absent at production commit")
    return tuple(sorted(imports, key=lambda item: item.encode("ascii")))


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
        if _git_path_kind(repository, commit, path) != "blob":
            raise EvidenceIntegrityError("production closure path is absent at source commit")
        raw = _git_bytes(repository, commit, path)
        observed.add(path)
        contents[path] = raw
        if path.endswith(".py"):
            pending.extend(
                dependency
                for dependency in _local_import_paths_at_commit(
                    repository, commit, path, raw
                )
                if dependency not in observed
            )
    ordered = tuple(sorted(observed, key=lambda item: item.encode("ascii")))
    if ordered != PRODUCTION_CLOSURE_PATHS_V1:
        raise EvidenceIntegrityError("production recursive closure path set drifted")
    if set(ordered).intersection(PRODUCTION_FORBIDDEN_PATHS_V1):
        raise EvidenceIntegrityError("production closure contains a forbidden capability path")
    return ordered, contents


def _build_production_closure_at_commit_v1(
    repository: Path, source_commit: str, source_tree: str
) -> Dict[str, Any]:
    source_commit = _exact_hex(source_commit, 40, "production source commit")
    source_tree = _exact_hex(source_tree, 40, "production source tree")
    if _git_hex(repository, ("rev-parse", source_commit + "^{commit}"), "source commit") != source_commit:
        raise EvidenceIntegrityError("production source commit does not resolve exactly")
    if _git_hex(repository, ("rev-parse", source_commit + "^{tree}"), "source tree") != source_tree:
        raise EvidenceIntegrityError("production source tree does not reconstruct")
    _require_fixed_git_chain(repository, source_commit)
    archive_subtree = _git_hex(
        repository,
        ("rev-parse", source_commit + ":" + PLAN0013_EVIDENCE_ROOT_RELATIVE_V1),
        "production archived evidence subtree",
    )
    if archive_subtree != PLAN0013_ARCHIVED_EVIDENCE_TREE_V1:
        raise EvidenceIntegrityError("production commit changes archived V2 evidence")
    paths, contents = _recursive_paths_at_commit(repository, source_commit)
    records = []
    for path in paths:
        raw = contents[path]
        records.append(
            {
                "byte_count": len(raw),
                "git_blob_sha1": _git_hex(
                    repository,
                    ("rev-parse", source_commit + ":" + path),
                    "production source blob",
                ),
                "path": path,
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    for path, repair_blob in PLAN0014_REPAIR_PRODUCTION_EQUIVALENCE_BLOBS_V1:
        production_blob = _git_hex(
            repository,
            ("rev-parse", source_commit + ":" + path),
            "production repair blob",
        )
        if production_blob != repair_blob:
            raise EvidenceIntegrityError("production source changes reviewed repair bytes")
    for (
        path,
        hardening_blob,
    ) in PLAN0014_READER_HARDENING_PRODUCTION_EQUIVALENCE_BLOBS_V1:
        production_blob = _git_hex(
            repository,
            ("rev-parse", source_commit + ":" + path),
            "production reader-hardening blob",
        )
        if production_blob != hardening_blob:
            raise EvidenceIntegrityError(
                "production source changes reviewed reader-hardening bytes"
            )
    for path, frozen_blob in PLAN0014_UNCHANGED_PRODUCTION_DEPENDENCY_BLOBS_V1:
        production_blob = _git_hex(
            repository,
            ("rev-parse", source_commit + ":" + path),
            "production unchanged dependency blob",
        )
        if production_blob != frozen_blob:
            raise EvidenceIntegrityError(
                "production source changes a frozen pre-existing dependency"
            )
    plan_raw = _git_bytes(repository, source_commit, ACTIVE_PLAN_PATH_V1)
    protocol_records = [
        record for record in records if record["path"] == _PROTOCOL_MODULE_PATH_V1
    ]
    if len(protocol_records) != 1:
        raise EvidenceIntegrityError("production closure lacks its protocol module")
    payload = {
        "active_plan_ref": _body_ref(plan_raw),
        "ordered_entrypoint_paths": list(PRODUCTION_ENTRYPOINT_PATHS_V1),
        "ordered_file_records": records,
        "protocol_module_blob_identity": protocol_records[0]["git_blob_sha1"],
        "repair_checkpoint_commit": PLAN0014_REPAIR_CHECKPOINT_COMMIT_V1,
        "repair_checkpoint_tree": PLAN0014_REPAIR_CHECKPOINT_TREE_V1,
        "source_commit": source_commit,
        "source_tree": source_tree,
        "stage_id": STAGE_ID_V1,
    }
    if tuple(sorted(payload)) != tuple(sorted(identity_payload_keys_v1("production_closure_root"))):
        raise EvidenceIntegrityError("production closure payload schema drifted")
    identity = domain_identity(identity_domain_v1("production_closure_root"), payload)
    return {
        "artifact_type": "PLAN0014_RECONSTRUCTION_PRODUCTION_CLOSURE_V1",
        "identity": identity,
        "payload": load_canonical_json_bytes(canonical_json_bytes(payload)),
    }


def build_plan0014_production_closure_v1(repository: str) -> Dict[str, Any]:
    """Build the closure at an exact clean HEAD; accepts no injected path/callback."""

    repository_path = _repository_path(repository)
    head = capture_clean_head(repository_path)
    return _build_production_closure_at_commit_v1(
        repository_path, head["source_commit"], head["source_tree"]
    )


def validate_plan0014_production_closure_v1(
    repository: str, value: Any
) -> Dict[str, Any]:
    """Rebuild a stored closure solely from its authenticated Git source commit."""

    repository_path = _repository_path(repository)
    envelope = _exact_dict(
        value, ("artifact_type", "identity", "payload"), "production closure"
    )
    if envelope["artifact_type"] != "PLAN0014_RECONSTRUCTION_PRODUCTION_CLOSURE_V1":
        raise EvidenceIntegrityError("production closure artifact type drifted")
    identity = _exact_hex(envelope["identity"], 64, "production closure identity")
    payload = _exact_dict(
        envelope["payload"],
        identity_payload_keys_v1("production_closure_root"),
        "production closure payload",
    )
    if identity != domain_identity(identity_domain_v1("production_closure_root"), payload):
        raise EvidenceIntegrityError("production closure identity does not reconstruct")
    source_commit = _exact_hex(payload["source_commit"], 40, "production source commit")
    source_tree = _exact_hex(payload["source_tree"], 40, "production source tree")
    expected = _build_production_closure_at_commit_v1(
        repository_path, source_commit, source_tree
    )
    if canonical_json_bytes(envelope) != canonical_json_bytes(expected):
        raise EvidenceIntegrityError("production closure does not reconstruct from Git")
    return load_canonical_json_bytes(canonical_json_bytes(envelope))


def _read_current_regular(
    repository: Path, path: str, expected_size: int
) -> bytes:
    path = _safe_repo_path(path)
    if type(expected_size) is not int or expected_size < 0:
        raise EvidenceIntegrityError("current production source size is invalid")
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
    absolute_repository = Path(os.path.abspath(os.fspath(repository)))
    if absolute_repository.parent == absolute_repository:
        raise EvidenceIntegrityError("repository cannot be a filesystem anchor")
    anchor_fd = directory_fd = file_fd = -1

    def open_directory_component(parent_fd: int, component: str) -> int:
        child_fd = -1
        try:
            child_fd = os.open(component, directory_flags, dir_fd=parent_fd)
            if not stat.S_ISDIR(os.fstat(child_fd).st_mode):
                raise EvidenceIntegrityError(
                    "current production source ancestor is not a directory"
                )
            return child_fd
        except BaseException:
            if child_fd >= 0:
                os.close(child_fd)
            raise

    try:
        anchor_fd = os.open(absolute_repository.anchor, directory_flags)
        directory_fd = anchor_fd
        for component in absolute_repository.parts[1:]:
            next_fd = open_directory_component(directory_fd, component)
            if directory_fd != anchor_fd:
                os.close(directory_fd)
            directory_fd = next_fd
        for component in path.split("/")[:-1]:
            next_fd = open_directory_component(directory_fd, component)
            os.close(directory_fd)
            directory_fd = next_fd
        file_fd = os.open(path.split("/")[-1], file_flags, dir_fd=directory_fd)
        before = os.fstat(file_fd)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_size != expected_size
        ):
            raise EvidenceIntegrityError(
                "current production source must be an exact-size singly-linked regular file"
            )
        chunks = []
        remaining = expected_size
        while remaining:
            chunk = os.read(file_fd, min(1024 * 1024, remaining))
            if not chunk:
                raise EvidenceIntegrityError(
                    "current production source was truncated while reading"
                )
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(file_fd, 1):
            raise EvidenceIntegrityError("current production source grew while reading")
        after = os.fstat(file_fd)
        if (
            before.st_dev,
            before.st_ino,
            before.st_mode,
            before.st_nlink,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_nlink,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ):
            raise EvidenceIntegrityError(
                "current production source changed while reading"
            )
        return b"".join(chunks)
    except OSError as error:
        raise EvidenceIntegrityError(
            "current production source path is unavailable or unsafe"
        ) from error
    finally:
        if file_fd >= 0:
            os.close(file_fd)
        if directory_fd >= 0 and directory_fd != anchor_fd:
            os.close(directory_fd)
        if anchor_fd >= 0:
            os.close(anchor_fd)


def reseal_plan0014_production_closure_v1(repository: str, value: Any) -> None:
    """Require current HEAD and current closure/plan bytes to equal the stored source."""

    repository_path = _repository_path(repository)
    closure = validate_plan0014_production_closure_v1(repository, value)
    payload = closure["payload"]
    head_commit = _git_hex(repository_path, ("rev-parse", "HEAD^{commit}"), "HEAD commit")
    head_tree = _git_hex(repository_path, ("rev-parse", "HEAD^{tree}"), "HEAD tree")
    if head_commit != payload["source_commit"] or head_tree != payload["source_tree"]:
        raise EvidenceIntegrityError("production HEAD changed after closure reservation")
    for record in payload["ordered_file_records"]:
        raw = _read_current_regular(
            repository_path, record["path"], record["byte_count"]
        )
        if (
            len(raw) != record["byte_count"]
            or hashlib.sha256(raw).hexdigest() != record["sha256"]
        ):
            raise EvidenceIntegrityError("current production closure bytes drifted")
    plan_raw = _read_current_regular(
        repository_path,
        ACTIVE_PLAN_PATH_V1,
        payload["active_plan_ref"]["byte_count"],
    )
    if _body_ref(plan_raw) != payload["active_plan_ref"]:
        raise EvidenceIntegrityError("current active-plan bytes drifted")


__all__ = (
    "ACTIVE_PLAN_PATH_V1",
    "CLOSED_DEFECT_IDS_V1",
    "EVIDENCE_PROTOCOL_ID_V1",
    "EVIDENCE_ROOT_RELATIVE_V1",
    "PLAN0013_ARCHIVED_EVIDENCE_FILE_COUNT_V1",
    "PLAN0013_ARCHIVED_EVIDENCE_TREE_V1",
    "PLAN0013_ARCHIVE_COMMIT_V1",
    "PLAN0013_ARCHIVE_TREE_V1",
    "PLAN0013_ASSESSMENT_ATTEMPT_ID_V1",
    "PLAN0013_ASSESSMENT_FAILURE_REF_V1",
    "PLAN0013_ASSESSMENT_FAILURE_V1",
    "PLAN0013_ASSESSMENT_PRODUCTION_CLOSURE_ROOT_V1",
    "PLAN0013_ASSESSMENT_RESERVATION_ID_V1",
    "PLAN0013_BOOTSTRAP_ROOT_V1",
    "PLAN0013_EVIDENCE_ROOT_RELATIVE_V1",
    "PLAN0013_MANIFEST_ROOT_V1",
    "PLAN0013_ORDERED_TERMINALS_V1",
    "PLAN0013_PROTOCOL_ID_V1",
    "PLAN0013_PROTOCOL_REF_V1",
    "PLAN0013_PROTOCOL_ROOT_V1",
    "PLAN0013_SOURCE_COMMIT_V1",
    "PLAN0013_SOURCE_TREE_V1",
    "PLAN0014_ACTIVE_PLAN_PATH_V1",
    "PLAN0014_CLOSED_DEFECT_IDS_V1",
    "PLAN0014_RECONSTRUCTION_EVIDENCE_PROTOCOL_ID_V1",
    "PLAN0014_RECONSTRUCTION_EVIDENCE_ROOT_RELATIVE_V1",
    "PLAN0014_RECONSTRUCTION_PROTOCOL_CANONICAL_SHA256_V1",
    "PLAN0014_RECONSTRUCTION_PROTOCOL_ID_V1",
    "PLAN0014_RECONSTRUCTION_PROTOCOL_ROOT_V1",
    "PLAN0014_RECONSTRUCTION_PROTOCOL_VERSION_V1",
    "PLAN0014_RECONSTRUCTION_STAGE_ID_V1",
    "PLAN0014_RECONSTRUCTION_STAGE_PROTOCOL_ID_V1",
    "PLAN0014_READER_HARDENING_CHECKPOINT_BLOBS_V1",
    "PLAN0014_READER_HARDENING_CHECKPOINT_CHANGED_PATHS_V1",
    "PLAN0014_READER_HARDENING_CHECKPOINT_COMMIT_V1",
    "PLAN0014_READER_HARDENING_CHECKPOINT_TREE_V1",
    "PLAN0014_READER_HARDENING_PRODUCTION_EQUIVALENCE_BLOBS_V1",
    "PLAN0014_READER_HARDENING_PROTOCOL_ID_V1",
    "PLAN0014_REJECTED_IMPLEMENTATION_CHECKPOINT_COMMIT_V1",
    "PLAN0014_REJECTED_IMPLEMENTATION_CHECKPOINT_TREE_V1",
    "PLAN0014_REJECTED_IMPLEMENTATION_PROTOCOL_CANONICAL_SHA256_V1",
    "PLAN0014_REJECTED_IMPLEMENTATION_PROTOCOL_ROOT_V1",
    "PLAN0014_REPAIR_CHECKPOINT_BLOBS_V1",
    "PLAN0014_REPAIR_CHECKPOINT_COMMIT_V1",
    "PLAN0014_REPAIR_CHECKPOINT_TREE_V1",
    "PLAN0014_REPAIR_PRODUCTION_EQUIVALENCE_BLOBS_V1",
    "PLAN0014_UNCHANGED_PRODUCTION_DEPENDENCY_BLOBS_V1",
    "PLAN0014_REPAIR_PROTOCOL_ID_V1",
    "PLAN0014_REPAIR_PROTOCOL_ROOT_V1",
    "PRODUCTION_CLOSURE_PATHS_V1",
    "PRODUCTION_ENTRYPOINT_PATHS_V1",
    "PRODUCTION_FORBIDDEN_PATHS_V1",
    "REPAIR_PROTOCOL_ID_V1",
    "REPAIR_PROTOCOL_ROOT_V1",
    "STAGE_ID_V1",
    "STAGE_PROTOCOL_ID_V1",
    "build_plan0014_assessment_reconstruction_protocol_v1",
    "build_plan0014_production_closure_v1",
    "identity_domain_v1",
    "identity_payload_keys_v1",
    "reseal_plan0014_production_closure_v1",
    "validate_plan0014_assessment_reconstruction_protocol_v1",
    "validate_plan0014_production_closure_v1",
)
