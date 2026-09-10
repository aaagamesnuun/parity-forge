"""Authenticated source binding and outer attestation for Plan 0014.

The old Plan-0013 V2 evidence is opened once, through a descriptor-bound
read-only store.  The same source session authenticates the archived/live
inventory, the five completed parents, the failed assessment chain, and the
unchanged inner report.  This module has no evidence-writing or gameplay
capability; the later one-shot lifecycle owns publication.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
from pathlib import Path
import stat
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Mapping, Sequence, Tuple

from .atlas_assessment_core import (
    ATLAS_ASSESSMENT_STAGE_ID_V1,
    ATLAS_ASSESSMENT_STAGE_PROTOCOL_ID_V1,
    _assessment_parent_inputs_v1,
    _assessment_prerequisites_v1,
    _build_atlas_assessment_report_v1,
)
from .atlas_assessment_reconstruction import (
    PLAN0013_ATLAS_EVIDENCE_ROOT_RELATIVE_V1,
    _open_existing_store_path_v1,
    _require_five_completed_parents_v1,
)
from .atlas_assessment_reconstruction_protocol import (
    PLAN0014_CLOSED_DEFECT_IDS_V1,
    PLAN0014_RECONSTRUCTION_PROTOCOL_ID_V1,
    PLAN0014_RECONSTRUCTION_PROTOCOL_ROOT_V1,
    PLAN0014_REPAIR_PROTOCOL_ID_V1,
    PLAN0014_REPAIR_PROTOCOL_ROOT_V1,
    identity_domain_v1,
)
from .atlas_evidence import (
    BodyRef,
    ChainSnapshot,
    EvidenceIntegrityError,
    ImmutableEvidenceStore,
    _load_chain_snapshot,
    canonical_body_ref,
    canonical_json_bytes,
    domain_identity,
    load_canonical_json_bytes,
    read_authenticated_stage_inputs,
    read_manifest_bootstrap,
    validate_chain_snapshot,
)


PLAN0014_SOURCE_BINDING_VERSION_V1 = 1
PLAN0014_SOURCE_BINDING_ID_V1 = (
    "plan0014-plan0013-assessment-reconstruction-source-binding-v1"
)
PLAN0014_SOURCE_BINDING_ARTIFACT_TYPE_V1 = (
    "PLAN0014_RECONSTRUCTION_SOURCE_BINDING_V1"
)
PLAN0014_ATTESTATION_VERSION_V1 = 1
PLAN0014_ATTESTATION_ID_V1 = (
    "plan0014-plan0013-assessment-reconstruction-attestation-v1"
)
PLAN0014_ATTESTATION_ARTIFACT_TYPE_V1 = (
    "PLAN0014_PLAN0013_ASSESSMENT_RECONSTRUCTION_ATTESTATION_V1"
)
PLAN0014_EPISTEMIC_STATUS_V1 = (
    "POST_FAILURE_MECHANICAL_RECONSTRUCTION_NOT_CONFIRMATION"
)
PLAN0014_ATTESTATION_CLAIM_LEVEL_V1 = (
    "POST_FAILURE_CALCULATION_ONLY_NO_FAIRNESS_STRATEGY_FUN_OR_CONFIRMATION_CLAIM"
)

PLAN0013_ARCHIVE_COMMIT_V1 = "c47db19b8ef3ad762979baa116cbb50a525cc730"
PLAN0013_ARCHIVE_TREE_V1 = "377eac4e151412f94d00332f9ff6f263e8306baa"
PLAN0013_ARCHIVE_EVIDENCE_SUBTREE_V1 = (
    "40f4b65f913a842a43e1b3a092a40cbb9933e489"
)
PLAN0014_REPAIR_CHECKPOINT_COMMIT_V1 = (
    "734cda958edebdb0b8279fae72148aaf39254a8a"
)
PLAN0014_REPAIR_CHECKPOINT_TREE_V1 = (
    "6fc95500b4b76aaf184db27f924999b023bf42c5"
)
PLAN0013_SOURCE_COMMIT_V1 = "5e6a865a5d4fe34d4b70eca2e6c546faaf1c5ec1"
PLAN0013_SOURCE_TREE_V1 = "17468fd2d9f986765bd15852753d8f168a482fad"
PLAN0013_BOOTSTRAP_ROOT_V1 = (
    "96c7e239c0d96fbd43ac9e592303b3ed72f8576fbdca88c92b8ff2a37d80ea22"
)
PLAN0013_PROTOCOL_ROOT_V1 = (
    "8126c33f787e63aef07e48fc25a3ed950f4650495e2e512c96d9e33583b8f04c"
)
PLAN0013_PROTOCOL_BODY_REF_V1 = BodyRef(
    "b732f174399acb8d52b2f5dddefc36a9f45e0560e94428b85f55998089bc9229",
    2_220_598,
)
PLAN0013_MANIFEST_ROOT_V1 = (
    "ffbb225619855440b83540b7712356f8f3f8b5f18d2ee4ab87b178b86b04f7c3"
)
PLAN0013_ARCHIVE_FILE_COUNT_V1 = 152_680
PLAN0013_ARCHIVE_TOTAL_BYTES_V1 = 601_787_372

_ASSESSMENT_RESERVATION_ID_V1 = (
    "91138600dcc40b649e527161ab1d4d49c87e6600928823cf8857c8a17f5f2a6d"
)
_ASSESSMENT_ATTEMPT_ID_V1 = (
    "bffac6f25d063e09839f35e2b09c72c3d3853178029113e8f1b7dcef95219c96"
)
_ASSESSMENT_CLOSURE_ROOT_V1 = (
    "f7792895c5ad0085f841cc7dce64d0f631df6d5ed8abdd3961ed08334df5b2e4"
)
_ASSESSMENT_FAILURE_REF_V1 = BodyRef(
    "9db7d724cd0d692c0a4347ebfb47579fd758dcb86c0011107ae2e5d98b69385d",
    504,
)
_ASSESSMENT_RESERVATION_REF_V1 = BodyRef(
    "4d7122ae326b3a4fd04eb3014237f3db5cef429ef7296e53b41ca6b730acd3af",
    1_740_429,
)
_ASSESSMENT_ATTEMPT_REF_V1 = BodyRef(
    "71c9145aa37f5564138727bb25961223a27b94dc71a01430f98a1a2b493ccbe0",
    1_743_221,
)

_STAGE_PINS_V1: Tuple[Tuple[str, str, str, str, BodyRef, BodyRef], ...] = (
    (
        "OUTCOME_FREE_DEVELOPMENT_MANIFEST",
        "plan0013-atlas-development-manifest-v1",
        "COMPLETED",
        "5ee92d2b10e39683ee790add3066ce71604a2232e8ad6f8508b3ddea71f17e46",
        BodyRef(
            "bf6b815017771d5fb13b27692564c096ec05e2b0bacd2addefef40b3fa466db6",
            15_571,
        ),
        BodyRef(
            "9fea44d3f334df290d232de7f21e142ba433bffd4c2a4634864ada439bef6375",
            1_932,
        ),
    ),
    (
        "EXACT_ALL_288",
        "plan0013-atlas-development-exact-v1",
        "COMPLETED",
        "6c575e5099b424eb1785e9aee424820e6f9c9e66a5c3fda557d23dad65da6c45",
        BodyRef(
            "2b9ac302d90710dc5a9dce991c22b935d479ba88238069657d6eb26efda7fba6",
            42_887,
        ),
        BodyRef(
            "5ab61a0ed63fa071e8fa0ddacbf096373887ff96e626fe4186edb4be3172c86e",
            925,
        ),
    ),
    (
        "RANDOM_ALL_18432_GAMES",
        "plan0013-atlas-development-random-v1",
        "COMPLETED",
        "bafc4a527e72be41cf76f33dede82e87116cb1301012678555a8afca48dae9b6",
        BodyRef(
            "d8cf86fea6308e0aaae775040dbcf77971649b5cb13c21d9c0ec1dff6ab4aed9",
            128_849,
        ),
        BodyRef(
            "68e91684c811acf904fbf05d105959d2a6d188243d542b211806b0ab879f6f49",
            914,
        ),
    ),
    (
        "TERMINAL_DEPTH1_ALL_18432_GAMES",
        "plan0013-atlas-development-terminal-depth1-v1",
        "COMPLETED",
        "f5d1e9374fcc3936c4eb7ddaab6c012931fc276f6c3c5d2adce7f44e778be226",
        BodyRef(
            "c4399eb5d98ba5a62603e4ab0d996ca233d2cead9389ec0e407243b13278263e",
            387_521,
        ),
        BodyRef(
            "3dd7f27d01f4fc244486a73749bdbed575e16e888ba17ad984ae14f97c14dfec",
            1_014,
        ),
    ),
    (
        "REPLAY_TELEMETRY_COMPLETE_TRACES_ONLY",
        "plan0013-atlas-development-telemetry-v1",
        "COMPLETED",
        "2869fc5564b80a3bcc0734f031394144073dd8a41f0ceef4d2acf3b80af8f670",
        BodyRef(
            "12cbc7f701ccbd07db8ae1909c37297b82fcb54bb5355931a5fee398791f6ed9",
            1_161_965,
        ),
        BodyRef(
            "e6904af99a1b2348e3e4aa3b0adcb690da52ddcd8cc6017475be43030aa79936",
            898,
        ),
    ),
    (
        "ASSESSMENT_AND_INSPECTION",
        "plan0013-atlas-development-assessment-v1",
        "FAILED",
        "812b8c4bfc9ffbb2fefa750361ebd33d998e9504ea9032b83b95049dc4f8e889",
        BodyRef(
            "0f6486c7cd75889fd055d133f4dba9ce116468b3ac904508d77eaf46574789e9",
            3_484_941,
        ),
        _ASSESSMENT_FAILURE_REF_V1,
    ),
)

_EXPECTED_LOCK_FILES_V1 = frozenset(
    stage_protocol_id + ".lock" for _, stage_protocol_id, _, _, _, _ in _STAGE_PINS_V1
)
_READ_ONLY_FLAGS = (
    os.O_RDONLY
    | getattr(os, "O_NOFOLLOW", 0)
    | getattr(os, "O_NONBLOCK", 0)
)
_DIRECTORY_FLAGS = _READ_ONLY_FLAGS | getattr(os, "O_DIRECTORY", 0)
_MAX_UNPINNED_SOURCE_FILE_BYTES_V1 = 64 * 1024 * 1024
_HEX40 = frozenset("0123456789abcdef")
_HEX64 = _HEX40


@dataclass(frozen=True)
class Plan0013AssessmentSourceSession:
    repository: Path
    evidence_root: Path
    evidence_root_fd: int
    store: ImmutableEvidenceStore


def _exact_fields(value: Any, fields: Sequence[str], label: str) -> Dict[str, Any]:
    if type(value) is not dict:
        raise TypeError("{} must be an exact object".format(label))
    if set(value) != set(fields):
        raise ValueError("{} fields mismatch".format(label))
    return value


def _exact_nonnegative_int(value: Any, label: str) -> int:
    if type(value) is not int or value < 0:
        raise TypeError("{} must be a nonnegative exact integer".format(label))
    return value


def _hex(value: Any, length: int, label: str) -> str:
    alphabet = _HEX40 if length == 40 else _HEX64
    if type(value) is not str or len(value) != length or any(c not in alphabet for c in value):
        raise TypeError("{} must be lowercase {}-hex".format(label, length))
    return value


def _body_ref_from_value(value: Any, label: str) -> BodyRef:
    ref = _exact_fields(value, ("byte_count", "sha256"), label)
    return BodyRef(
        _hex(ref["sha256"], 64, label + " SHA-256"),
        _exact_nonnegative_int(ref["byte_count"], label + " byte count"),
    )


def _detached(value: Any, label: str) -> Any:
    try:
        return load_canonical_json_bytes(canonical_json_bytes(value))
    except (TypeError, ValueError) as error:
        raise type(error)("{}: {}".format(label, error)) from error


def _raw_ref(raw: bytes) -> BodyRef:
    return BodyRef(hashlib.sha256(raw).hexdigest(), len(raw))


def _read_all_regular_at(
    parent_fd: int,
    name: str,
    *,
    allowed_modes: Tuple[int, ...] = (0o400, 0o644),
    expected_size: int | None = None,
) -> bytes:
    try:
        fd = os.open(name, _READ_ONLY_FLAGS, dir_fd=parent_fd)
    except OSError as error:
        raise EvidenceIntegrityError(
            "source inventory file is unavailable or unsafe"
        ) from error
    try:
        before = os.fstat(fd)
        mode = stat.S_IMODE(before.st_mode)
        size_limit = (
            expected_size
            if expected_size is not None
            else _MAX_UNPINNED_SOURCE_FILE_BYTES_V1
        )
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or mode not in allowed_modes
            or (expected_size is not None and before.st_size != expected_size)
            or before.st_size > size_limit
        ):
            raise EvidenceIntegrityError("source inventory file shape drifted")
        chunks = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(fd, min(1024 * 1024, remaining))
            if not chunk:
                raise EvidenceIntegrityError(
                    "source inventory file was truncated while read"
                )
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(fd, 1):
            raise EvidenceIntegrityError("source inventory file grew while read")
        after = os.fstat(fd)
        if (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
            before.st_mode,
            before.st_nlink,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
            after.st_mode,
            after.st_nlink,
        ):
            raise EvidenceIntegrityError("source inventory file changed while read")
        raw = b"".join(chunks)
        if len(raw) != before.st_size:
            raise EvidenceIntegrityError("source inventory file size drifted")
        return raw
    finally:
        os.close(fd)


def _git_blob_identity(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw
    ).hexdigest()


def _run_git(repository: Path, arguments: Sequence[str], *, check: bool = True) -> bytes:
    process = subprocess.run(
        ("git", "-C", str(repository), *arguments),
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and process.returncode != 0:
        raise EvidenceIntegrityError("fixed Git source relation is unavailable")
    return process.stdout


def _git_object(repository: Path, expression: str, length: int) -> str:
    raw = _run_git(repository, ("rev-parse", "--verify", expression)).strip()
    try:
        value = raw.decode("ascii", "strict")
    except UnicodeDecodeError as error:
        raise EvidenceIntegrityError("fixed Git identity is not ASCII") from error
    return _hex(value, length, "fixed Git identity")


def _require_git_ancestor(repository: Path, ancestor: str, descendant: str) -> None:
    process = subprocess.run(
        ("git", "-C", str(repository), "merge-base", "--is-ancestor", ancestor, descendant),
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.returncode != 0:
        raise EvidenceIntegrityError("fixed Git ancestry is absent")


def _archive_inventory_records_v1(repository: Path) -> List[Dict[str, Any]]:
    prefix = PLAN0013_ATLAS_EVIDENCE_ROOT_RELATIVE_V1 + "/"
    raw = _run_git(
        repository,
        (
            "ls-tree",
            "-r",
            "-z",
            "-l",
            PLAN0013_ARCHIVE_COMMIT_V1,
            "--",
            PLAN0013_ATLAS_EVIDENCE_ROOT_RELATIVE_V1,
        ),
    )
    records = []
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        metadata, separator, path_raw = entry.partition(b"\t")
        if not separator:
            raise EvidenceIntegrityError("archived inventory record is malformed")
        parts = metadata.split()
        if len(parts) != 4 or parts[1] != b"blob":
            raise EvidenceIntegrityError("archived evidence contains a non-blob entry")
        try:
            mode = parts[0].decode("ascii")
            git_blob = parts[2].decode("ascii")
            byte_count = int(parts[3].decode("ascii"))
            full_path = path_raw.decode("utf-8", "strict")
        except (UnicodeDecodeError, ValueError) as error:
            raise EvidenceIntegrityError("archived inventory encoding drifted") from error
        if mode != "100644" or not full_path.startswith(prefix):
            raise EvidenceIntegrityError("archived evidence mode or path drifted")
        relative = full_path[len(prefix) :]
        if not relative or relative.startswith(".locks/"):
            raise EvidenceIntegrityError("operational lock entered the archive")
        records.append(
            {
                "byte_count": byte_count,
                "git_blob_sha1": _hex(git_blob, 40, "archive Git blob"),
                "mode": mode,
                "path": relative,
            }
        )
    paths = [record["path"] for record in records]
    if paths != sorted(set(paths)):
        raise EvidenceIntegrityError("archived evidence paths are not unique and ordered")
    return records


def _open_directory_at(parent_fd: int, name: str) -> int:
    try:
        fd = os.open(name, _DIRECTORY_FLAGS, dir_fd=parent_fd)
    except OSError as error:
        raise EvidenceIntegrityError(
            "source inventory directory is unavailable or unsafe"
        ) from error
    info = os.fstat(fd)
    mode = stat.S_IMODE(info.st_mode)
    if not stat.S_ISDIR(info.st_mode) or mode not in (0o700, 0o755):
        os.close(fd)
        raise EvidenceIntegrityError("source inventory path is not a directory")
    return fd


def _validate_operational_directories_v1(
    root_fd: int, root_names: Sequence[str]
) -> None:
    if ".locks" in root_names:
        locks_fd = _open_directory_at(root_fd, ".locks")
        try:
            before = tuple(sorted(os.listdir(locks_fd)))
            if set(before) != _EXPECTED_LOCK_FILES_V1:
                raise EvidenceIntegrityError("operational lock inventory drifted")
            for name in before:
                _read_all_regular_at(
                    locks_fd,
                    name,
                    allowed_modes=(0o600,),
                    expected_size=0,
                )
            if before != tuple(sorted(os.listdir(locks_fd))):
                raise EvidenceIntegrityError(
                    "operational lock inventory changed while read"
                )
        finally:
            os.close(locks_fd)
    if "contradictions" in root_names:
        contradictions_fd = _open_directory_at(root_fd, "contradictions")
        try:
            if os.listdir(contradictions_fd):
                raise EvidenceIntegrityError("old evidence has a contradiction sidecar")
        finally:
            os.close(contradictions_fd)


def _live_inventory_records_v1(
    root_fd: int,
    expected_records: Sequence[Mapping[str, Any]] | None = None,
) -> Tuple[List[Dict[str, Any]], Tuple[str, ...]]:
    records: List[Dict[str, Any]] = []
    directories = set()
    expected_sizes = (
        None
        if expected_records is None
        else {record["path"]: record["byte_count"] for record in expected_records}
    )

    root_info = os.fstat(root_fd)
    if (
        not stat.S_ISDIR(root_info.st_mode)
        or stat.S_IMODE(root_info.st_mode) not in (0o700, 0o755)
    ):
        raise EvidenceIntegrityError("old evidence root mode or type drifted")

    def visit(directory_fd: int, prefix: str) -> None:
        before_info = os.fstat(directory_fd)
        before_names = tuple(sorted(os.listdir(directory_fd)))
        for name in before_names:
            relative = name if not prefix else prefix + "/" + name
            if not prefix and name in (".locks", "contradictions"):
                continue
            info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode):
                child_fd = _open_directory_at(directory_fd, name)
                directories.add(relative)
                try:
                    visit(child_fd, relative)
                finally:
                    os.close(child_fd)
            elif stat.S_ISREG(info.st_mode):
                if expected_sizes is not None and relative not in expected_sizes:
                    raise EvidenceIntegrityError(
                        "source inventory has an unexpected regular file"
                    )
                raw = _read_all_regular_at(
                    directory_fd,
                    name,
                    expected_size=(
                        None
                        if expected_sizes is None
                        else expected_sizes[relative]
                    ),
                )
                records.append(
                    {
                        "byte_count": len(raw),
                        "git_blob_sha1": _git_blob_identity(raw),
                        "mode": "100644",
                        "path": relative,
                    }
                )
            else:
                raise EvidenceIntegrityError("source inventory has a non-regular path")
        after_info = os.fstat(directory_fd)
        if before_names != tuple(sorted(os.listdir(directory_fd))) or (
            before_info.st_dev,
            before_info.st_ino,
            before_info.st_mtime_ns,
            before_info.st_ctime_ns,
        ) != (
            after_info.st_dev,
            after_info.st_ino,
            after_info.st_mtime_ns,
            after_info.st_ctime_ns,
        ):
            raise EvidenceIntegrityError("source inventory directory changed while read")

    root_info = os.fstat(root_fd)
    root_mode = stat.S_IMODE(root_info.st_mode)
    if (
        not stat.S_ISDIR(root_info.st_mode)
        or root_mode & ~0o777
        or root_mode & 0o500 != 0o500
    ):
        raise EvidenceIntegrityError("old evidence root is not a readable directory")
    root_names = set(os.listdir(root_fd))
    required = {"manifest-bootstrap", "stages"}
    optional = {".locks", "contradictions"}
    if not required.issubset(root_names) or root_names - required - optional:
        raise EvidenceIntegrityError("old evidence root inventory drifted")
    _validate_operational_directories_v1(root_fd, tuple(root_names))
    visit(root_fd, "")
    records.sort(key=lambda value: value["path"])
    if expected_sizes is not None and {
        record["path"] for record in records
    } != set(expected_sizes):
        raise EvidenceIntegrityError("source inventory path set drifted")
    return records, tuple(sorted(directories))


def _inventory_root_v1(records: Sequence[Mapping[str, Any]]) -> str:
    return domain_identity(
        identity_domain_v1("archive_live_inventory_root"),
        {"ordered_file_records": list(records)},
    )


def _archive_live_inventory_v1(session: Plan0013AssessmentSourceSession) -> Dict[str, Any]:
    repository = session.repository
    if _git_object(repository, PLAN0013_ARCHIVE_COMMIT_V1 + "^{commit}", 40) != PLAN0013_ARCHIVE_COMMIT_V1:
        raise EvidenceIntegrityError("archive commit drifted")
    if _git_object(repository, PLAN0013_ARCHIVE_COMMIT_V1 + "^{tree}", 40) != PLAN0013_ARCHIVE_TREE_V1:
        raise EvidenceIntegrityError("archive tree drifted")
    if _git_object(repository, PLAN0013_ARCHIVE_COMMIT_V1 + "^", 40) != PLAN0013_SOURCE_COMMIT_V1:
        raise EvidenceIntegrityError("archive commit is not the fixed source child")
    if _git_object(repository, PLAN0013_SOURCE_COMMIT_V1 + "^{tree}", 40) != PLAN0013_SOURCE_TREE_V1:
        raise EvidenceIntegrityError("old source tree drifted")
    subtree_expression = (
        PLAN0013_ARCHIVE_COMMIT_V1
        + ":"
        + PLAN0013_ATLAS_EVIDENCE_ROOT_RELATIVE_V1
    )
    if _git_object(repository, subtree_expression, 40) != PLAN0013_ARCHIVE_EVIDENCE_SUBTREE_V1:
        raise EvidenceIntegrityError("archived evidence subtree drifted")
    if _git_object(repository, PLAN0014_REPAIR_CHECKPOINT_COMMIT_V1 + "^{commit}", 40) != PLAN0014_REPAIR_CHECKPOINT_COMMIT_V1:
        raise EvidenceIntegrityError("repair checkpoint commit drifted")
    if _git_object(repository, PLAN0014_REPAIR_CHECKPOINT_COMMIT_V1 + "^{tree}", 40) != PLAN0014_REPAIR_CHECKPOINT_TREE_V1:
        raise EvidenceIntegrityError("repair checkpoint tree drifted")
    _require_git_ancestor(repository, PLAN0013_ARCHIVE_COMMIT_V1, PLAN0014_REPAIR_CHECKPOINT_COMMIT_V1)
    if _git_object(repository, PLAN0014_REPAIR_CHECKPOINT_COMMIT_V1 + "^", 40) != PLAN0013_ARCHIVE_COMMIT_V1:
        raise EvidenceIntegrityError("repair checkpoint is not the fixed archive child")

    archived = _archive_inventory_records_v1(repository)
    live, live_directories = _live_inventory_records_v1(
        session.evidence_root_fd, archived
    )
    if archived != live:
        raise EvidenceIntegrityError("live V2 evidence differs from its fixed archive")
    archive_directories = {
        "/".join(record["path"].split("/")[:index])
        for record in archived
        for index in range(1, len(record["path"].split("/")))
    }
    if tuple(sorted(archive_directories)) != live_directories:
        raise EvidenceIntegrityError("live V2 directory inventory differs from its archive")
    file_count = len(archived)
    total_bytes = sum(record["byte_count"] for record in archived)
    if file_count != PLAN0013_ARCHIVE_FILE_COUNT_V1 or total_bytes != PLAN0013_ARCHIVE_TOTAL_BYTES_V1:
        raise EvidenceIntegrityError("fixed archive inventory totals drifted")
    inventory_root = _inventory_root_v1(archived)
    return {
        "archive_file_count": file_count,
        "archive_total_bytes": total_bytes,
        "archive_inventory_root": inventory_root,
        "archive_git_subtree": PLAN0013_ARCHIVE_EVIDENCE_SUBTREE_V1,
        "live_file_count": file_count,
        "live_total_bytes": total_bytes,
        "live_inventory_root": inventory_root,
        "live_git_subtree": PLAN0013_ARCHIVE_EVIDENCE_SUBTREE_V1,
        "excluded_operational_paths": [".locks", "contradictions"],
    }


@contextlib.contextmanager
def open_plan0013_assessment_source_session_v1(
    repository: str,
) -> Iterator[Plan0013AssessmentSourceSession]:
    if type(repository) is not str or not repository:
        raise ValueError("repository must be a nonempty exact string")
    repository_path = Path(os.path.abspath(repository))
    try:
        git_top = Path(
            _run_git(repository_path, ("rev-parse", "--show-toplevel"))
            .decode("utf-8", "strict")
            .strip()
        )
    except UnicodeDecodeError as error:
        raise EvidenceIntegrityError("Git top-level path is not UTF-8") from error
    if git_top != repository_path:
        raise ValueError("repository must be the exact Git top-level directory")
    evidence_root = repository_path / PLAN0013_ATLAS_EVIDENCE_ROOT_RELATIVE_V1
    with _open_existing_store_path_v1(repository_path) as evidence_root_fd:
        with ImmutableEvidenceStore.from_read_only_directory_fd(
            evidence_root, evidence_root_fd
        ) as store:
            yield Plan0013AssessmentSourceSession(
                repository_path, evidence_root, evidence_root_fd, store
            )


def _terminal_projection_v1(
    store: ImmutableEvidenceStore,
    terminal: Any,
    pin: Tuple[str, str, str, str, BodyRef, BodyRef],
) -> Dict[str, Any]:
    stage_id, stage_protocol_id, lifecycle, identity, terminal_ref, result_ref = pin
    value = _detached(terminal, "old terminal")
    if (
        value.get("identity") != identity
        or value.get("payload", {}).get("stage_id") != stage_id
        or value.get("payload", {}).get("stage_protocol_id") != stage_protocol_id
        or value.get("payload", {}).get("lifecycle") != lifecycle
    ):
        raise EvidenceIntegrityError("fixed old terminal identity or lifecycle drifted")
    terminal_raw = store.read_bytes(stage_protocol_id, "terminal_seal")
    if load_canonical_json_bytes(terminal_raw) != value or _raw_ref(terminal_raw) != terminal_ref:
        raise EvidenceIntegrityError("fixed old terminal body drifted")
    artifact = "completed" if lifecycle == "COMPLETED" else "failure"
    result_raw = store.read_bytes(stage_protocol_id, artifact)
    if _raw_ref(result_raw) != result_ref:
        raise EvidenceIntegrityError("fixed old terminal result body drifted")
    result_root_key = (
        "completed_root_or_null" if lifecycle == "COMPLETED" else "failure_root_or_null"
    )
    if value["payload"][result_root_key] != result_ref.sha256:
        raise EvidenceIntegrityError("old terminal result BodyRef differs from its payload")
    return {
        "stage_id": stage_id,
        "stage_protocol_id": stage_protocol_id,
        "lifecycle": lifecycle,
        "terminal_seal_identity": identity,
        "terminal_body_ref": terminal_ref.as_dict(),
        "result_body_ref": result_ref.as_dict(),
    }


def _failed_assessment_projection_v1(
    session: Plan0013AssessmentSourceSession,
    inputs: Any,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    snapshot = _load_chain_snapshot(session.store, inputs.contract)
    if validate_chain_snapshot(inputs.contract, snapshot) != "FAILED":
        raise EvidenceIntegrityError("old assessment is not sealed FAILED")
    if not isinstance(snapshot, ChainSnapshot):
        raise EvidenceIntegrityError("old assessment snapshot is invalid")
    if any(
        value is not None
        for value in (
            snapshot.blocked,
            snapshot.completed,
            snapshot.orphaned,
            snapshot.partial_evidence,
        )
    ):
        raise EvidenceIntegrityError("old assessment retains an incompatible result")
    if snapshot.reservation is None or snapshot.attempt is None or snapshot.failure is None:
        raise EvidenceIntegrityError("old assessment failure chain is incomplete")
    reservation_raw = session.store.read_bytes(
        ATLAS_ASSESSMENT_STAGE_PROTOCOL_ID_V1, "reservation"
    )
    attempt_raw = session.store.read_bytes(
        ATLAS_ASSESSMENT_STAGE_PROTOCOL_ID_V1, "attempt"
    )
    failure_raw = session.store.read_bytes(
        ATLAS_ASSESSMENT_STAGE_PROTOCOL_ID_V1, "failure"
    )
    if (
        snapshot.reservation.get("identity") != _ASSESSMENT_RESERVATION_ID_V1
        or _raw_ref(reservation_raw) != _ASSESSMENT_RESERVATION_REF_V1
        or snapshot.attempt.get("identity") != _ASSESSMENT_ATTEMPT_ID_V1
        or _raw_ref(attempt_raw) != _ASSESSMENT_ATTEMPT_REF_V1
        or _raw_ref(failure_raw) != _ASSESSMENT_FAILURE_REF_V1
    ):
        raise EvidenceIntegrityError("old assessment reservation/attempt/failure drifted")
    closure = snapshot.production_closure
    if closure is None or closure.root != _ASSESSMENT_CLOSURE_ROOT_V1:
        raise EvidenceIntegrityError("old assessment production closure drifted")
    embedded = snapshot.reservation["references"]["ordered_parent_terminal_seals"]
    parents = list(inputs.ordered_parent_terminal_seals)
    if type(embedded) is not list or len(embedded) != 5:
        raise EvidenceIntegrityError("old assessment reservation parents drifted")
    for expected, observed in zip(parents, embedded):
        if canonical_json_bytes(expected) != canonical_json_bytes(observed):
            raise EvidenceIntegrityError("old assessment embedded parent differs from fixed path")
    failure_value = snapshot.failure["failure"]
    if failure_value != {
        "exception_module": "builtins",
        "exception_type": "TypeError",
        "kind": "ASSESSMENT_STAGE_EXCEPTION",
        "message": "admissible slots must be an exact array",
    }:
        raise EvidenceIntegrityError("old assessment exception drifted")
    return snapshot.terminal_seal, {
        "reservation_id": _ASSESSMENT_RESERVATION_ID_V1,
        "reservation_body_ref": _ASSESSMENT_RESERVATION_REF_V1.as_dict(),
        "attempt_id": _ASSESSMENT_ATTEMPT_ID_V1,
        "attempt_body_ref": _ASSESSMENT_ATTEMPT_REF_V1.as_dict(),
        "failure_body_ref": _ASSESSMENT_FAILURE_REF_V1.as_dict(),
        "production_closure_root": _ASSESSMENT_CLOSURE_ROOT_V1,
        "embedded_parent_terminal_match_count": 5,
        "partial_evidence_root_or_null": None,
        "exception": failure_value,
    }


def _source_binding_from_session_v1(
    session: Plan0013AssessmentSourceSession,
) -> Tuple[Dict[str, Any], Any]:
    inputs = read_authenticated_stage_inputs(
        session.store, ATLAS_ASSESSMENT_STAGE_ID_V1
    )
    if inputs.contract.stage_protocol_id != ATLAS_ASSESSMENT_STAGE_PROTOCOL_ID_V1:
        raise EvidenceIntegrityError("old assessment stage protocol drifted")
    _assessment_prerequisites_v1(
        inputs.contract, inputs.ordered_parent_terminal_seals
    )
    parents = tuple(inputs.ordered_parent_terminal_seals)
    _require_five_completed_parents_v1(parents)
    if inputs.detached_manifest is None:
        raise EvidenceIntegrityError("completed Plan-0013 manifest is unavailable")

    failed_terminal, failed_projection = _failed_assessment_projection_v1(
        session, inputs
    )
    all_terminals = (*parents, failed_terminal)
    projections = [
        _terminal_projection_v1(session.store, terminal, pin)
        for terminal, pin in zip(all_terminals, _STAGE_PINS_V1)
    ]
    bootstrap = read_manifest_bootstrap(session.store)
    catalog = bootstrap["catalog"]
    manifest_root = inputs.detached_manifest.get("manifest_root")
    if (
        catalog.get("bootstrap_root") != PLAN0013_BOOTSTRAP_ROOT_V1
        or catalog.get("protocol_root") != PLAN0013_PROTOCOL_ROOT_V1
        or bootstrap["refs"].protocol != PLAN0013_PROTOCOL_BODY_REF_V1
        or catalog.get("source_commit") != PLAN0013_SOURCE_COMMIT_V1
        or catalog.get("source_tree") != PLAN0013_SOURCE_TREE_V1
        or manifest_root != PLAN0013_MANIFEST_ROOT_V1
    ):
        raise EvidenceIntegrityError("old bootstrap, protocol, or manifest root drifted")
    payload = {
        "source_binding_version": PLAN0014_SOURCE_BINDING_VERSION_V1,
        "source_binding_id": PLAN0014_SOURCE_BINDING_ID_V1,
        "evidence_store_relative_path": PLAN0013_ATLAS_EVIDENCE_ROOT_RELATIVE_V1,
        "archive": {
            "commit": PLAN0013_ARCHIVE_COMMIT_V1,
            "tree": PLAN0013_ARCHIVE_TREE_V1,
            "evidence_subtree": PLAN0013_ARCHIVE_EVIDENCE_SUBTREE_V1,
        },
        "repair_checkpoint": {
            "commit": PLAN0014_REPAIR_CHECKPOINT_COMMIT_V1,
            "tree": PLAN0014_REPAIR_CHECKPOINT_TREE_V1,
        },
        "archive_live_inventory": _archive_live_inventory_v1(session),
        "bootstrap": {
            "bootstrap_root": PLAN0013_BOOTSTRAP_ROOT_V1,
            "protocol_root": PLAN0013_PROTOCOL_ROOT_V1,
            "protocol_body_ref": PLAN0013_PROTOCOL_BODY_REF_V1.as_dict(),
            "manifest_root": PLAN0013_MANIFEST_ROOT_V1,
            "source_commit": PLAN0013_SOURCE_COMMIT_V1,
            "source_tree": PLAN0013_SOURCE_TREE_V1,
        },
        "ordered_stage_terminals": projections,
        "failed_assessment": failed_projection,
    }
    binding = {
        "artifact_type": PLAN0014_SOURCE_BINDING_ARTIFACT_TYPE_V1,
        "identity": domain_identity(
            identity_domain_v1("source_binding_root"), payload
        ),
        "payload": payload,
    }
    return _detached(binding, "Plan-0014 source binding"), inputs


def build_plan0014_source_binding_v1(repository: str) -> Dict[str, Any]:
    with open_plan0013_assessment_source_session_v1(repository) as session:
        binding, _inputs = _source_binding_from_session_v1(session)
        return binding


def _execution_counts_v1() -> Dict[str, int]:
    return {
        "candidate_block_access_count": 0,
        "candidate_block_allocation_count": 0,
        "candidate_block_evaluation_count": 0,
        "candidate_block_export_count": 0,
        "outcome_generation_count": 0,
        "sampled_game_generation_count": 0,
        "solver_invocation_count": 0,
        "telemetry_generation_count": 0,
    }


def _validate_source_binding_shape_v1(value: Any) -> Dict[str, Any]:
    entry = canonical_json_bytes(value)
    binding = load_canonical_json_bytes(entry)
    envelope = _exact_fields(
        binding,
        (
            "artifact_type",
            "identity",
            "payload",
        ),
        "source binding",
    )
    if envelope["artifact_type"] != PLAN0014_SOURCE_BINDING_ARTIFACT_TYPE_V1:
        raise ValueError("source binding artifact type drifted")
    payload = _exact_fields(
        envelope["payload"],
        (
            "source_binding_version",
            "source_binding_id",
            "evidence_store_relative_path",
            "archive",
            "repair_checkpoint",
            "archive_live_inventory",
            "bootstrap",
            "ordered_stage_terminals",
            "failed_assessment",
        ),
        "source binding payload",
    )
    observed_root = _hex(envelope["identity"], 64, "source binding root")
    if observed_root != domain_identity(identity_domain_v1("source_binding_root"), payload):
        raise ValueError("source binding root does not reconstruct")
    if (
        type(payload["source_binding_version"]) is not int
        or payload["source_binding_version"] != PLAN0014_SOURCE_BINDING_VERSION_V1
        or payload["source_binding_id"] != PLAN0014_SOURCE_BINDING_ID_V1
        or payload["evidence_store_relative_path"] != PLAN0013_ATLAS_EVIDENCE_ROOT_RELATIVE_V1
    ):
        raise ValueError("source binding identity drifted")
    archive = _exact_fields(
        payload["archive"],
        ("commit", "tree", "evidence_subtree"),
        "source archive",
    )
    if archive != {
        "commit": PLAN0013_ARCHIVE_COMMIT_V1,
        "tree": PLAN0013_ARCHIVE_TREE_V1,
        "evidence_subtree": PLAN0013_ARCHIVE_EVIDENCE_SUBTREE_V1,
    }:
        raise ValueError("source archive identity drifted")
    repair = _exact_fields(
        payload["repair_checkpoint"],
        ("commit", "tree"),
        "repair checkpoint",
    )
    if repair != {
        "commit": PLAN0014_REPAIR_CHECKPOINT_COMMIT_V1,
        "tree": PLAN0014_REPAIR_CHECKPOINT_TREE_V1,
    }:
        raise ValueError("repair checkpoint identity drifted")
    inventory = _exact_fields(
        payload["archive_live_inventory"],
        (
            "archive_file_count",
            "archive_total_bytes",
            "archive_inventory_root",
            "archive_git_subtree",
            "live_file_count",
            "live_total_bytes",
            "live_inventory_root",
            "live_git_subtree",
            "excluded_operational_paths",
        ),
        "archive/live inventory",
    )
    for key in (
        "archive_file_count",
        "archive_total_bytes",
        "live_file_count",
        "live_total_bytes",
    ):
        _exact_nonnegative_int(inventory[key], "inventory " + key)
    for key in ("archive_inventory_root", "live_inventory_root"):
        _hex(inventory[key], 64, "inventory root")
    for key in ("archive_git_subtree", "live_git_subtree"):
        _hex(inventory[key], 40, "inventory Git subtree")
    if (
        inventory["archive_file_count"] != PLAN0013_ARCHIVE_FILE_COUNT_V1
        or inventory["live_file_count"] != PLAN0013_ARCHIVE_FILE_COUNT_V1
        or inventory["archive_total_bytes"] != PLAN0013_ARCHIVE_TOTAL_BYTES_V1
        or inventory["live_total_bytes"] != PLAN0013_ARCHIVE_TOTAL_BYTES_V1
        or inventory["archive_inventory_root"] != inventory["live_inventory_root"]
        or inventory["archive_git_subtree"] != PLAN0013_ARCHIVE_EVIDENCE_SUBTREE_V1
        or inventory["live_git_subtree"] != PLAN0013_ARCHIVE_EVIDENCE_SUBTREE_V1
        or type(inventory["excluded_operational_paths"]) is not list
        or inventory["excluded_operational_paths"] != [".locks", "contradictions"]
    ):
        raise ValueError("archive/live inventory relation drifted")
    bootstrap = _exact_fields(
        payload["bootstrap"],
        (
            "bootstrap_root",
            "protocol_root",
            "protocol_body_ref",
            "manifest_root",
            "source_commit",
            "source_tree",
        ),
        "old bootstrap projection",
    )
    if (
        bootstrap["bootstrap_root"] != PLAN0013_BOOTSTRAP_ROOT_V1
        or bootstrap["protocol_root"] != PLAN0013_PROTOCOL_ROOT_V1
        or _body_ref_from_value(
            bootstrap["protocol_body_ref"], "old protocol ref"
        )
        != PLAN0013_PROTOCOL_BODY_REF_V1
        or bootstrap["manifest_root"] != PLAN0013_MANIFEST_ROOT_V1
        or bootstrap["source_commit"] != PLAN0013_SOURCE_COMMIT_V1
        or bootstrap["source_tree"] != PLAN0013_SOURCE_TREE_V1
    ):
        raise ValueError("old bootstrap projection drifted")
    terminals = payload["ordered_stage_terminals"]
    if type(terminals) is not list or len(terminals) != len(_STAGE_PINS_V1):
        raise TypeError("source terminals must be the exact six-element array")
    for index, (terminal, pin) in enumerate(zip(terminals, _STAGE_PINS_V1)):
        projected = _exact_fields(
            terminal,
            (
                "stage_id",
                "stage_protocol_id",
                "lifecycle",
                "terminal_seal_identity",
                "terminal_body_ref",
                "result_body_ref",
            ),
            "source terminal {}".format(index),
        )
        stage_id, stage_protocol_id, lifecycle, identity, terminal_ref, result_ref = pin
        if (
            projected["stage_id"] != stage_id
            or projected["stage_protocol_id"] != stage_protocol_id
            or projected["lifecycle"] != lifecycle
            or projected["terminal_seal_identity"] != identity
            or _body_ref_from_value(
                projected["terminal_body_ref"], "source terminal body ref"
            )
            != terminal_ref
            or _body_ref_from_value(
                projected["result_body_ref"], "source result body ref"
            )
            != result_ref
        ):
            raise ValueError("source terminal projection drifted")
    failed = _exact_fields(
        payload["failed_assessment"],
        (
            "reservation_id",
            "reservation_body_ref",
            "attempt_id",
            "attempt_body_ref",
            "failure_body_ref",
            "production_closure_root",
            "embedded_parent_terminal_match_count",
            "partial_evidence_root_or_null",
            "exception",
        ),
        "failed assessment projection",
    )
    exception = _exact_fields(
        failed["exception"],
        ("exception_module", "exception_type", "kind", "message"),
        "failed assessment exception",
    )
    if (
        failed["reservation_id"] != _ASSESSMENT_RESERVATION_ID_V1
        or _body_ref_from_value(
            failed["reservation_body_ref"], "assessment reservation ref"
        )
        != _ASSESSMENT_RESERVATION_REF_V1
        or failed["attempt_id"] != _ASSESSMENT_ATTEMPT_ID_V1
        or _body_ref_from_value(
            failed["attempt_body_ref"], "assessment attempt ref"
        )
        != _ASSESSMENT_ATTEMPT_REF_V1
        or _body_ref_from_value(
            failed["failure_body_ref"], "assessment failure ref"
        )
        != _ASSESSMENT_FAILURE_REF_V1
        or failed["production_closure_root"] != _ASSESSMENT_CLOSURE_ROOT_V1
        or type(failed["embedded_parent_terminal_match_count"]) is not int
        or failed["embedded_parent_terminal_match_count"] != 5
        or failed["partial_evidence_root_or_null"] is not None
        or exception
        != {
            "exception_module": "builtins",
            "exception_type": "TypeError",
            "kind": "ASSESSMENT_STAGE_EXCEPTION",
            "message": "admissible slots must be an exact array",
        }
    ):
        raise ValueError("failed assessment projection drifted")
    if entry != canonical_json_bytes(value):
        raise ValueError("source binding changed during validation")
    return envelope


def build_plan0014_outer_attestation_v1(
    source_binding_value: Any,
    inner_report_value: Any,
) -> Dict[str, Any]:
    binding = _validate_source_binding_shape_v1(source_binding_value)
    inner_entry = canonical_json_bytes(inner_report_value)
    inner = load_canonical_json_bytes(inner_entry)
    if type(inner) is not dict:
        raise TypeError("inner report must be an exact object")
    for field in ("report_root", "status", "claim_level", "inspection_selection"):
        if field not in inner:
            raise ValueError("inner report lacks {}".format(field))
    report_root = _hex(inner["report_root"], 64, "inner report root")
    if type(inner["status"]) is not str or not inner["status"]:
        raise TypeError("inner report status must be a nonempty exact string")
    if inner["claim_level"] != "FAMILY_FRONTIER_SIGNAL_NOT_FAIR_GAME":
        raise ValueError("inner report claim level drifted")
    inner_ref = _raw_ref(inner_entry)
    inspection = _detached(inner["inspection_selection"], "inspection selection")
    inspection_ref = canonical_body_ref(inspection)
    inspection_payload = {
        "inner_report_body_ref": inner_ref.as_dict(),
        "inspection_selection_body_ref": inspection_ref.as_dict(),
        "inspection_selection": inspection,
    }
    inspection_root = domain_identity(
        identity_domain_v1("inspection_selection_root"), inspection_payload
    )
    unsigned = {
        "artifact_type": PLAN0014_ATTESTATION_ARTIFACT_TYPE_V1,
        "attestation_version": PLAN0014_ATTESTATION_VERSION_V1,
        "attestation_id": PLAN0014_ATTESTATION_ID_V1,
        "reconstruction_protocol_id": PLAN0014_RECONSTRUCTION_PROTOCOL_ID_V1,
        "reconstruction_protocol_root": PLAN0014_RECONSTRUCTION_PROTOCOL_ROOT_V1,
        "repair_protocol_id": PLAN0014_REPAIR_PROTOCOL_ID_V1,
        "repair_protocol_root": PLAN0014_REPAIR_PROTOCOL_ROOT_V1,
        "source_binding_root": binding["identity"],
        "original_stage_lifecycle": "FAILED",
        "original_stage_terminal_identity": _STAGE_PINS_V1[-1][3],
        "original_stage_completed_body_count": 0,
        "epistemic_status": PLAN0014_EPISTEMIC_STATUS_V1,
        "claim_level": PLAN0014_ATTESTATION_CLAIM_LEVEL_V1,
        "repair_boundary": {
            "closed_defect_ids": list(PLAN0014_CLOSED_DEFECT_IDS_V1),
            "integration_correction_count": 2,
            "scientific_rule_change_count": 0,
        },
        "execution_counts": _execution_counts_v1(),
        "inner_report": {
            "body_ref": inner_ref.as_dict(),
            "claim_level": inner["claim_level"],
            "report_root": report_root,
            "status": inner["status"],
        },
        "inspection_selection": {
            "body_ref": inspection_ref.as_dict(),
            "root": inspection_root,
        },
    }
    return {
        **unsigned,
        "attestation_root": domain_identity(
            identity_domain_v1("attestation_root"), unsigned
        ),
    }


def validate_plan0014_outer_attestation_v1(
    stored_value: Any,
    source_binding_value: Any,
    inner_report_value: Any,
) -> Dict[str, Any]:
    entry = canonical_json_bytes(stored_value)
    expected = build_plan0014_outer_attestation_v1(
        source_binding_value, inner_report_value
    )
    if entry != canonical_json_bytes(expected):
        raise ValueError("outer attestation does not reconstruct")
    if entry != canonical_json_bytes(stored_value):
        raise ValueError("outer attestation changed during validation")
    return _detached(expected, "validated outer attestation")


def _inner_report_from_inputs_v1(session: Plan0013AssessmentSourceSession, inputs: Any) -> Dict[str, Any]:
    parent_values = _assessment_parent_inputs_v1(
        session.store,
        inputs.protocol,
        tuple(inputs.ordered_parent_terminal_seals),
    )
    return _build_atlas_assessment_report_v1(
        inputs.detached_manifest,
        inputs.protocol,
        *parent_values,
    )


def reconstruct_plan0014_assessment_artifacts_v1(repository: str) -> Dict[str, Any]:
    """Rebuild source binding, unchanged inner report, and outer attestation."""

    with open_plan0013_assessment_source_session_v1(repository) as session:
        source_binding, inputs = _source_binding_from_session_v1(session)
        inner_report = _inner_report_from_inputs_v1(session, inputs)
        resealed_binding, _resealed_inputs = _source_binding_from_session_v1(session)
        if canonical_json_bytes(resealed_binding) != canonical_json_bytes(source_binding):
            raise EvidenceIntegrityError(
                "old source binding changed during report reconstruction"
            )
        outer = build_plan0014_outer_attestation_v1(
            resealed_binding, inner_report
        )
        return {
            "source_binding": resealed_binding,
            "result": {
                "inner_report": inner_report,
                "outer_attestation": outer,
            },
        }


def validate_plan0014_assessment_result_v1(
    stored_value: Any,
    repository: str,
) -> Dict[str, Any]:
    """Validate a stored result only by rebuilding it from fixed old evidence."""

    entry = canonical_json_bytes(stored_value)
    expected = reconstruct_plan0014_assessment_artifacts_v1(repository)["result"]
    if entry != canonical_json_bytes(expected):
        raise ValueError("assessment reconstruction result does not reconstruct")
    if entry != canonical_json_bytes(stored_value):
        raise ValueError("assessment reconstruction result changed during validation")
    return _detached(expected, "validated assessment reconstruction result")


def validate_plan0014_source_binding_v1(
    stored_value: Any,
    repository: str,
) -> Dict[str, Any]:
    entry = canonical_json_bytes(stored_value)
    expected = build_plan0014_source_binding_v1(repository)
    if entry != canonical_json_bytes(expected):
        raise ValueError("source binding does not reconstruct from fixed evidence")
    if entry != canonical_json_bytes(stored_value):
        raise ValueError("source binding changed during validation")
    return _detached(expected, "validated source binding")


__all__ = (
    "PLAN0013_ARCHIVE_COMMIT_V1",
    "PLAN0013_ARCHIVE_EVIDENCE_SUBTREE_V1",
    "PLAN0013_ARCHIVE_TREE_V1",
    "PLAN0014_ATTESTATION_ARTIFACT_TYPE_V1",
    "PLAN0014_ATTESTATION_CLAIM_LEVEL_V1",
    "PLAN0014_ATTESTATION_ID_V1",
    "PLAN0014_ATTESTATION_VERSION_V1",
    "PLAN0014_EPISTEMIC_STATUS_V1",
    "PLAN0014_REPAIR_CHECKPOINT_COMMIT_V1",
    "PLAN0014_REPAIR_CHECKPOINT_TREE_V1",
    "PLAN0014_SOURCE_BINDING_ID_V1",
    "PLAN0014_SOURCE_BINDING_ARTIFACT_TYPE_V1",
    "PLAN0014_SOURCE_BINDING_VERSION_V1",
    "Plan0013AssessmentSourceSession",
    "build_plan0014_outer_attestation_v1",
    "build_plan0014_source_binding_v1",
    "open_plan0013_assessment_source_session_v1",
    "reconstruct_plan0014_assessment_artifacts_v1",
    "validate_plan0014_assessment_result_v1",
    "validate_plan0014_outer_attestation_v1",
    "validate_plan0014_source_binding_v1",
)
