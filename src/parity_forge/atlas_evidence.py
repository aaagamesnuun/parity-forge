"""Fail-closed evidence primitives for the Plan 0013 Atlas stages.

This module deliberately sits on the outcome-free side of the stage boundary.  It
only serializes, authenticates, publishes, and reconciles evidence; it never
accepts a callback and never imports a stage implementation or game machinery.
"""

from __future__ import annotations

import contextlib
import ast
import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, Iterator, Mapping, Optional, Sequence, Tuple

from . import atlas_protocol


__all__ = [
    "ArtifactRef",
    "AuthenticatedStageInputs",
    "BodyRef",
    "ChainSnapshot",
    "EvidenceConflictError",
    "EvidenceError",
    "EvidenceIntegrityError",
    "EvidenceLockError",
    "ImmutableEvidenceStore",
    "LedgerSpec",
    "ManifestBootstrapRefs",
    "ManifestFreezeRefs",
    "ProductionClosure",
    "RecoveryResult",
    "StageResultRefs",
    "StageContract",
    "build_all_production_closures",
    "build_attempt",
    "build_blocked",
    "build_completed",
    "build_failure",
    "build_orphaned",
    "build_production_closure",
    "build_reservation",
    "build_terminal_seal",
    "begin_stage",
    "block_stage",
    "canonical_body_ref",
    "canonical_json_bytes",
    "capture_clean_head",
    "domain_identity",
    "extract_stage_contract",
    "extract_recovery_stage_contract",
    "load_canonical_json_bytes",
    "publish_manifest_freeze",
    "publish_manifest_bootstrap",
    "publish_stage_completion_evidence",
    "read_stage_completion_evidence",
    "read_manifest_freeze",
    "read_manifest_bootstrap",
    "read_authenticated_stage_inputs",
    "reconcile_status_ledger",
    "recover_stage",
    "reseal_production_closure",
    "validate_chain_snapshot",
    "verify_commit_relation",
    "seal_completed_stage",
    "seal_failed_stage",
]


class EvidenceError(RuntimeError):
    """Base class for evidence-boundary failures."""


class EvidenceIntegrityError(EvidenceError):
    """Evidence or source bytes failed authentication."""


class EvidenceConflictError(EvidenceError):
    """An immutable destination already exists with conflicting bytes."""


class EvidenceLockError(EvidenceError):
    """The exclusive stage lock could not be acquired."""


_MAX_CANONICAL_BYTES = 64 * 1024 * 1024
_MAX_JSON_NODES = 2_000_000
_MAX_JSON_DEPTH = 128
_MAX_STRING_BYTES = 8 * 1024 * 1024
_MAX_INT_DIGITS = 256
_SAFE_COMPONENT = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]{0,191}\Z")
_SAFE_INTERNAL_COMPONENT = re.compile(r"\A[A-Za-z0-9.][A-Za-z0-9._-]{0,191}\Z")
_HEX40 = re.compile(r"\A[0-9a-f]{40}\Z")
_HEX64 = re.compile(r"\A[0-9a-f]{64}\Z")
_MANIFEST_BOOTSTRAP_ROOT_DOMAIN = (
    atlas_protocol._MANIFEST_BOOTSTRAP_ROOT_DOMAIN_V1
)


@dataclass(frozen=True)
class BodyRef:
    sha256: str
    byte_count: int

    def as_dict(self) -> Dict[str, Any]:
        return {"byte_count": self.byte_count, "sha256": self.sha256}


@dataclass(frozen=True)
class ArtifactRef:
    artifact_type: str
    identity: str

    def as_dict(self) -> Dict[str, Any]:
        return {"artifact_type": self.artifact_type, "identity": self.identity}


@dataclass(frozen=True)
class ManifestFreezeRefs:
    protocol: BodyRef
    detached_manifest: BodyRef
    production_closures: BodyRef
    experiment_plan: BodyRef

    def as_dict(self) -> Dict[str, Any]:
        return {
            "detached_manifest": self.detached_manifest.as_dict(),
            "experiment_plan": self.experiment_plan.as_dict(),
            "production_closures": self.production_closures.as_dict(),
            "protocol": self.protocol.as_dict(),
        }


@dataclass(frozen=True)
class ManifestBootstrapRefs:
    protocol: BodyRef
    production_closures: BodyRef
    experiment_plan: BodyRef
    catalog: BodyRef

    def as_dict(self) -> Dict[str, Any]:
        return {
            "catalog": self.catalog.as_dict(),
            "experiment_plan": self.experiment_plan.as_dict(),
            "production_closures": self.production_closures.as_dict(),
            "protocol": self.protocol.as_dict(),
        }


@dataclass(frozen=True)
class StageResultRefs:
    status_ledger: BodyRef
    record_catalog: BodyRef

    def as_dict(self) -> Dict[str, Any]:
        return {
            "record_catalog": self.record_catalog.as_dict(),
            "status_ledger": self.status_ledger.as_dict(),
        }


@dataclass(frozen=True)
class AuthenticatedStageInputs:
    contract: "StageContract"
    protocol: Dict[str, Any]
    detached_manifest: Any
    experiment_plan_bytes: bytes
    production_closure: "ProductionClosure"
    ordered_parent_terminal_seals: Tuple[Dict[str, Any], ...]
    manifest_freeze_refs: Optional[ManifestFreezeRefs]
    manifest_bootstrap_refs: ManifestBootstrapRefs
    manifest_lifecycle: str


def _reject_float(_value: str) -> Any:
    raise ValueError("floating-point JSON values are forbidden")


def _parse_int(value: str) -> int:
    digits = value[1:] if value.startswith("-") else value
    if len(digits) > _MAX_INT_DIGITS:
        raise ValueError("JSON integer exceeds the digit limit")
    return int(value)


def _object_no_duplicates(pairs: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key: {!r}".format(key))
        result[key] = value
    return result


def _validate_json_tree(
    value: Any,
    *,
    max_nodes: int,
    max_depth: int,
    max_string_bytes: int,
    max_int_digits: int,
) -> None:
    nodes = 0
    active = set()

    def visit(item: Any, depth: int) -> None:
        nonlocal nodes
        nodes += 1
        if nodes > max_nodes:
            raise ValueError("canonical JSON node limit exceeded")
        if depth > max_depth:
            raise ValueError("canonical JSON depth limit exceeded")
        item_type = type(item)
        if item is None or item_type is bool:
            return
        if item_type is int:
            digits = str(abs(item))
            if len(digits) > max_int_digits:
                raise ValueError("canonical JSON integer exceeds the digit limit")
            return
        if item_type is str:
            try:
                encoded = item.encode("utf-8", "strict")
            except UnicodeEncodeError as error:
                raise ValueError("canonical JSON strings must be valid UTF-8") from error
            if len(encoded) > max_string_bytes:
                raise ValueError("canonical JSON string limit exceeded")
            return
        if item_type not in (list, dict):
            raise TypeError("unsupported canonical JSON type: {}".format(item_type.__name__))
        marker = id(item)
        if marker in active:
            raise ValueError("cyclic canonical JSON value")
        active.add(marker)
        try:
            if item_type is list:
                for child in item:
                    visit(child, depth + 1)
            else:
                for key, child in item.items():
                    if type(key) is not str:
                        raise TypeError("canonical JSON object keys must be exact strings")
                    visit(key, depth + 1)
                    visit(child, depth + 1)
        finally:
            active.remove(marker)

    visit(value, 0)


def canonical_json_bytes(
    value: Any,
    *,
    max_bytes: int = _MAX_CANONICAL_BYTES,
    max_nodes: int = _MAX_JSON_NODES,
    max_depth: int = _MAX_JSON_DEPTH,
    max_string_bytes: int = _MAX_STRING_BYTES,
    max_int_digits: int = _MAX_INT_DIGITS,
) -> bytes:
    """Return strict compact canonical JSON bytes for an exact finite tree."""

    for label, limit in (
        ("max_bytes", max_bytes),
        ("max_nodes", max_nodes),
        ("max_depth", max_depth),
        ("max_string_bytes", max_string_bytes),
        ("max_int_digits", max_int_digits),
    ):
        if type(limit) is not int or limit < 1:
            raise ValueError("{} must be a positive exact integer".format(label))
    _validate_json_tree(
        value,
        max_nodes=max_nodes,
        max_depth=max_depth,
        max_string_bytes=max_string_bytes,
        max_int_digits=max_int_digits,
    )
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8", "strict")
    if len(encoded) > max_bytes:
        raise ValueError("canonical JSON byte limit exceeded")
    return encoded


def load_canonical_json_bytes(
    raw: bytes,
    *,
    max_bytes: int = _MAX_CANONICAL_BYTES,
    max_nodes: int = _MAX_JSON_NODES,
    max_depth: int = _MAX_JSON_DEPTH,
    max_string_bytes: int = _MAX_STRING_BYTES,
    max_int_digits: int = _MAX_INT_DIGITS,
) -> Any:
    """Decode JSON only when the supplied bytes already are canonical."""

    if type(raw) is not bytes:
        raise TypeError("canonical JSON input must be exact bytes")
    if len(raw) > max_bytes:
        raise ValueError("canonical JSON byte limit exceeded")
    try:
        text = raw.decode("utf-8", "strict")
        value = json.loads(
            text,
            object_pairs_hook=_object_no_duplicates,
            parse_float=_reject_float,
            parse_int=_parse_int,
            parse_constant=_reject_float,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid UTF-8 JSON") from error
    encoded = canonical_json_bytes(
        value,
        max_bytes=max_bytes,
        max_nodes=max_nodes,
        max_depth=max_depth,
        max_string_bytes=max_string_bytes,
        max_int_digits=max_int_digits,
    )
    if encoded != raw:
        raise ValueError("JSON bytes are not in canonical form")
    return value


def domain_identity(domain: bytes, payload: Any) -> str:
    """Compute a protocol domain-separated identity over a canonical payload."""

    if type(domain) is not bytes or not domain or not domain.endswith(b"\0"):
        raise ValueError("identity domain must be nonempty exact bytes ending in NUL")
    return hashlib.sha256(domain + canonical_json_bytes(payload)).hexdigest()


def canonical_body_ref(value: Any) -> BodyRef:
    raw = canonical_json_bytes(value)
    return BodyRef(hashlib.sha256(raw).hexdigest(), len(raw))


_STAGE_ARTIFACT_FILES = {
    "reservation": "reservation.json",
    "attempt": "attempt.json",
    "blocked": "blocked.json",
    "partial_ledger": "partial-ledger.json",
    "failure": "failure.json",
    "completed": "completed.json",
    "orphaned": "orphaned.json",
    "terminal_seal": "terminal-seal.json",
    "experiment_plan": "experiment-plan.bin",
    "protocol": "protocol.json",
    "detached_manifest": "detached-manifest.json",
    "production_closures": "production-closures.json",
    "status_ledger": "status-ledger.json",
    "record_catalog": "record-catalog.json",
}
_MANIFEST_BOOTSTRAP_FILES = {
    "catalog": "catalog.json",
    "experiment_plan": "experiment-plan.bin",
    "production_closures": "production-closures.json",
    "protocol": "protocol.json",
}
_MANIFEST_STAGE_PROTOCOL_ID = "plan0013-atlas-development-manifest-v1"
_MANIFEST_STAGE_ID = "OUTCOME_FREE_DEVELOPMENT_MANIFEST"
_EXACT_STAGE_ID = "EXACT_ALL_288"
_RANDOM_STAGE_ID = "RANDOM_ALL_18432_GAMES"
_DEPTH1_STAGE_ID = "TERMINAL_DEPTH1_ALL_18432_GAMES"
_TELEMETRY_STAGE_ID = "REPLAY_TELEMETRY_COMPLETE_TRACES_ONLY"
_ASSESSMENT_STAGE_ID = "ASSESSMENT_AND_INSPECTION"
_RANDOM_STRENGTH_ID = "random-v1-weak"
_DEPTH1_STRENGTH_ID = "terminal_only_minimax-v1-depth1"
_STAGE_ID_BY_PROTOCOL_ID = {
    "plan0013-atlas-development-manifest-v1": "OUTCOME_FREE_DEVELOPMENT_MANIFEST",
    "plan0013-atlas-development-exact-v1": "EXACT_ALL_288",
    "plan0013-atlas-development-random-v1": "RANDOM_ALL_18432_GAMES",
    "plan0013-atlas-development-terminal-depth1-v1": "TERMINAL_DEPTH1_ALL_18432_GAMES",
    "plan0013-atlas-development-telemetry-v1": "REPLAY_TELEMETRY_COMPLETE_TRACES_ONLY",
    "plan0013-atlas-development-assessment-v1": "ASSESSMENT_AND_INSPECTION",
}
_LIFECYCLE_ARTIFACTS = {
    "reservation",
    "attempt",
    "blocked",
    "partial_ledger",
    "failure",
    "completed",
    "orphaned",
    "terminal_seal",
}


def _allowed_artifacts(stage_protocol_id: str) -> set:
    try:
        stage_id = _STAGE_ID_BY_PROTOCOL_ID[stage_protocol_id]
    except KeyError as error:
        raise ValueError("stage protocol id is not in the fixed six-stage catalog") from error
    allowed = set(_LIFECYCLE_ARTIFACTS)
    if stage_id == "OUTCOME_FREE_DEVELOPMENT_MANIFEST":
        allowed.update(
            {
                "experiment_plan",
                "protocol",
                "detached_manifest",
                "production_closures",
            }
        )
    if stage_id in (
        "EXACT_ALL_288",
        "RANDOM_ALL_18432_GAMES",
        "TERMINAL_DEPTH1_ALL_18432_GAMES",
        "REPLAY_TELEMETRY_COMPLETE_TRACES_ONLY",
    ):
        allowed.update({"status_ledger", "record_catalog"})
    return allowed


def _safe_component(value: str, label: str) -> str:
    if type(value) is not str or _SAFE_COMPONENT.fullmatch(value) is None:
        raise ValueError("unsafe {} path component".format(label))
    if value in (".", "..") or "/" in value or "\\" in value:
        raise ValueError("unsafe {} path component".format(label))
    return value


def _safe_internal_component(value: str, label: str) -> str:
    if (
        type(value) is not str
        or _SAFE_INTERNAL_COMPONENT.fullmatch(value) is None
        or value in (".", "..")
        or "/" in value
        or "\\" in value
    ):
        raise ValueError("unsafe {} path component".format(label))
    return value


def _open_directory(path: Path, *, create: bool) -> int:
    if create:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(str(path), flags)
    except OSError as error:
        raise EvidenceIntegrityError("evidence directory is unavailable or unsafe") from error
    info = os.fstat(fd)
    if not stat.S_ISDIR(info.st_mode):
        os.close(fd)
        raise EvidenceIntegrityError("evidence root is not a directory")
    return fd


def _open_or_create_dir_at(parent_fd: int, name: str) -> int:
    _safe_internal_component(name, "directory")
    try:
        os.mkdir(name, mode=0o700, dir_fd=parent_fd)
    except FileExistsError:
        pass
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        child_fd = os.open(name, flags, dir_fd=parent_fd)
    except OSError as error:
        raise EvidenceIntegrityError("unsafe evidence directory component") from error
    info = os.fstat(child_fd)
    if not stat.S_ISDIR(info.st_mode):
        os.close(child_fd)
        raise EvidenceIntegrityError("evidence component is not a directory")
    return child_fd


def _open_existing_dir_at(parent_fd: int, name: str) -> int:
    """Open one existing evidence-directory component without mutating it."""

    _safe_internal_component(name, "directory")
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        child_fd = os.open(name, flags, dir_fd=parent_fd)
    except OSError as error:
        raise EvidenceIntegrityError(
            "evidence directory component is unavailable or unsafe"
        ) from error
    info = os.fstat(child_fd)
    if not stat.S_ISDIR(info.st_mode):
        os.close(child_fd)
        raise EvidenceIntegrityError("evidence component is not a directory")
    return child_fd


def _read_regular_at(parent_fd: int, name: str, max_bytes: int) -> bytes:
    _safe_component(name, "artifact")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    try:
        fd = os.open(name, flags, dir_fd=parent_fd)
    except OSError as error:
        raise EvidenceIntegrityError("immutable artifact is unavailable or unsafe") from error
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise EvidenceIntegrityError("immutable artifact must be a singly-linked regular file")
        if before.st_size > max_bytes:
            raise EvidenceIntegrityError("immutable artifact exceeds the byte limit")
        chunks = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(fd, min(1024 * 1024, remaining))
            if not chunk:
                raise EvidenceIntegrityError("immutable artifact was truncated while reading")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(fd, 1):
            raise EvidenceIntegrityError("immutable artifact grew while reading")
        after = os.fstat(fd)
        stable = (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
            before.st_nlink,
        ) == (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
            after.st_nlink,
        )
        if not stable:
            raise EvidenceIntegrityError("immutable artifact changed while reading")
        return b"".join(chunks)
    finally:
        os.close(fd)


def _publish_exclusive_at(parent_fd: int, name: str, raw: bytes) -> None:
    _safe_component(name, "artifact")
    if type(raw) is not bytes:
        raise TypeError("immutable artifact body must be exact bytes")
    temp_name = ".tmp-{}-{}".format(os.getpid(), os.urandom(12).hex())
    temp_fd = -1
    linked = False
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        temp_fd = os.open(temp_name, flags, 0o400, dir_fd=parent_fd)
        view = memoryview(raw)
        while view:
            written = os.write(temp_fd, view)
            if written <= 0:
                raise OSError(errno.EIO, "short immutable evidence write")
            view = view[written:]
        os.fsync(temp_fd)
        os.fchmod(temp_fd, 0o400)
        os.fsync(temp_fd)
        os.close(temp_fd)
        temp_fd = -1
        try:
            os.link(
                temp_name,
                name,
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
                follow_symlinks=False,
            )
        except FileExistsError as error:
            raise EvidenceConflictError("immutable artifact already exists") from error
        linked = True
        os.fsync(parent_fd)
        os.unlink(temp_name, dir_fd=parent_fd)
        linked = False
        os.fsync(parent_fd)
    finally:
        if temp_fd >= 0:
            os.close(temp_fd)
        try:
            os.unlink(temp_name, dir_fd=parent_fd)
        except FileNotFoundError:
            pass
        if linked:
            # The final link is the committed artifact and must never be rolled back.
            try:
                os.fsync(parent_fd)
            except OSError:
                pass


class ImmutableEvidenceStore:
    """Candidate-neutral, fixed-catalog immutable evidence storage."""

    def __init__(self, root: os.PathLike, *, create: bool = True) -> None:
        if type(create) is not bool:
            raise TypeError("create must be an exact bool")
        self.root = Path(root)
        self._writable = create
        self._held_stage_locks = set()
        self._root_fd = _open_directory(self.root, create=create)
        try:
            if create:
                stages_fd = _open_or_create_dir_at(self._root_fd, "stages")
                os.close(stages_fd)
                locks_fd = _open_or_create_dir_at(self._root_fd, ".locks")
                os.close(locks_fd)
                contradictions_fd = _open_or_create_dir_at(
                    self._root_fd, "contradictions"
                )
                os.close(contradictions_fd)
                bootstrap_fd = _open_or_create_dir_at(
                    self._root_fd, "manifest-bootstrap"
                )
                os.close(bootstrap_fd)
                os.fsync(self._root_fd)
            else:
                stages_fd = _open_existing_dir_at(self._root_fd, "stages")
                os.close(stages_fd)
                bootstrap_fd = _open_existing_dir_at(
                    self._root_fd, "manifest-bootstrap"
                )
                os.close(bootstrap_fd)
        except Exception:
            os.close(self._root_fd)
            raise

    @classmethod
    def from_read_only_directory_fd(
        cls, root: os.PathLike, directory_fd: int
    ) -> "ImmutableEvidenceStore":
        """Bind a reader to an already authenticated directory descriptor.

        The descriptor is duplicated so the caller retains ownership.  This
        avoids re-opening a compound path after its components have been
        authenticated with ``openat`` and ``O_NOFOLLOW``.
        """

        if type(directory_fd) is not int or directory_fd < 0:
            raise TypeError("directory fd must be a nonnegative exact integer")
        try:
            access_mode = fcntl.fcntl(directory_fd, fcntl.F_GETFL) & os.O_ACCMODE
        except OSError as error:
            raise EvidenceIntegrityError(
                "read-only evidence directory descriptor is unavailable"
            ) from error
        if access_mode != os.O_RDONLY:
            raise EvidenceIntegrityError(
                "evidence directory descriptor must be opened read-only"
            )
        try:
            root_fd = os.dup(directory_fd)
        except OSError as error:
            raise EvidenceIntegrityError(
                "read-only evidence directory descriptor is unavailable"
            ) from error
        info = os.fstat(root_fd)
        if not stat.S_ISDIR(info.st_mode):
            os.close(root_fd)
            raise EvidenceIntegrityError(
                "read-only evidence descriptor is not a directory"
            )

        instance = cls.__new__(cls)
        instance.root = Path(root)
        instance._writable = False
        instance._held_stage_locks = set()
        instance._root_fd = root_fd
        try:
            stages_fd = _open_existing_dir_at(instance._root_fd, "stages")
            os.close(stages_fd)
            bootstrap_fd = _open_existing_dir_at(
                instance._root_fd, "manifest-bootstrap"
            )
            os.close(bootstrap_fd)
        except Exception:
            os.close(instance._root_fd)
            instance._root_fd = -1
            raise
        return instance

    def close(self) -> None:
        if getattr(self, "_root_fd", -1) >= 0:
            os.close(self._root_fd)
            self._root_fd = -1

    def __enter__(self) -> "ImmutableEvidenceStore":
        return self

    def __exit__(self, _type: Any, _value: Any, _traceback: Any) -> None:
        self.close()

    def _require_open(self) -> None:
        if self._root_fd < 0:
            raise EvidenceError("immutable evidence store is closed")

    def _require_writable(self) -> None:
        self._require_open()
        if not self._writable:
            raise EvidenceError("immutable evidence store is read-only")

    def _require_stage_lock(self, stage_protocol_id: str) -> None:
        self._require_writable()
        if stage_protocol_id not in self._held_stage_locks:
            raise EvidenceLockError("boundary operation requires the held stage lock")

    @contextlib.contextmanager
    def _manifest_bootstrap_fd(self) -> Iterator[int]:
        self._require_open()
        if self._writable:
            directory_fd = _open_or_create_dir_at(
                self._root_fd, "manifest-bootstrap"
            )
        else:
            directory_fd = _open_existing_dir_at(
                self._root_fd, "manifest-bootstrap"
            )
        try:
            yield directory_fd
        finally:
            os.close(directory_fd)

    def publish_manifest_bootstrap_bytes(
        self, artifact: str, raw: bytes
    ) -> BodyRef:
        """Idempotently fill one outcome-free bootstrap slot under its lock."""

        self._require_writable()
        if artifact not in _MANIFEST_BOOTSTRAP_FILES:
            raise ValueError("artifact is not in the fixed manifest bootstrap catalog")
        self._require_stage_lock(_MANIFEST_STAGE_PROTOCOL_ID)
        if type(raw) is not bytes or len(raw) > _MAX_CANONICAL_BYTES:
            raise ValueError("manifest bootstrap artifact bytes are invalid")
        if artifact != "experiment_plan":
            load_canonical_json_bytes(raw)
        name = _MANIFEST_BOOTSTRAP_FILES[artifact]
        with self._manifest_bootstrap_fd() as directory_fd:
            try:
                existing = _read_regular_at(directory_fd, name, _MAX_CANONICAL_BYTES)
            except FileNotFoundError:
                existing = None
            except EvidenceIntegrityError as error:
                if isinstance(error.__cause__, FileNotFoundError):
                    existing = None
                else:
                    raise
            if existing is None:
                try:
                    _publish_exclusive_at(directory_fd, name, raw)
                except EvidenceConflictError:
                    existing = _read_regular_at(
                        directory_fd, name, _MAX_CANONICAL_BYTES
                    )
                    if existing != raw:
                        raise
            elif existing != raw:
                raise EvidenceConflictError(
                    "manifest bootstrap slot already has conflicting bytes"
                )
        return BodyRef(hashlib.sha256(raw).hexdigest(), len(raw))

    def read_manifest_bootstrap_bytes(self, artifact: str) -> bytes:
        if artifact not in _MANIFEST_BOOTSTRAP_FILES:
            raise ValueError("artifact is not in the fixed manifest bootstrap catalog")
        with self._manifest_bootstrap_fd() as directory_fd:
            return _read_regular_at(
                directory_fd,
                _MANIFEST_BOOTSTRAP_FILES[artifact],
                _MAX_CANONICAL_BYTES,
            )

    def scan_manifest_bootstrap(self) -> Dict[str, BodyRef]:
        result = {}
        with self._manifest_bootstrap_fd() as directory_fd:
            observed = set(os.listdir(directory_fd))
            allowed = set(_MANIFEST_BOOTSTRAP_FILES.values())
            if observed - allowed:
                raise EvidenceIntegrityError(
                    "manifest bootstrap contains a noncatalog path"
                )
            for artifact, name in _MANIFEST_BOOTSTRAP_FILES.items():
                raw = _read_regular_at(directory_fd, name, _MAX_CANONICAL_BYTES)
                if artifact != "experiment_plan":
                    load_canonical_json_bytes(raw)
                result[artifact] = BodyRef(
                    hashlib.sha256(raw).hexdigest(), len(raw)
                )
        return result

    @contextlib.contextmanager
    def _stage_fd(self, stage_protocol_id: str, *, create: bool) -> Iterator[int]:
        if create:
            self._require_writable()
        else:
            self._require_open()
        stage_protocol_id = _safe_component(stage_protocol_id, "stage protocol id")
        _allowed_artifacts(stage_protocol_id)
        if self._writable:
            stages_fd = _open_or_create_dir_at(self._root_fd, "stages")
        else:
            stages_fd = _open_existing_dir_at(self._root_fd, "stages")
        try:
            if create:
                stage_fd = _open_or_create_dir_at(stages_fd, stage_protocol_id)
            elif self._writable:
                flags = (
                    os.O_RDONLY
                    | getattr(os, "O_DIRECTORY", 0)
                    | getattr(os, "O_NOFOLLOW", 0)
                )
                stage_fd = os.open(stage_protocol_id, flags, dir_fd=stages_fd)
            else:
                stage_fd = _open_existing_dir_at(stages_fd, stage_protocol_id)
            try:
                yield stage_fd
            finally:
                os.close(stage_fd)
        finally:
            os.close(stages_fd)

    @contextlib.contextmanager
    def stage_lock(self, stage_protocol_id: str, *, blocking: bool = False) -> Iterator[None]:
        """Hold the process-wide exclusive lock for one fixed stage protocol id."""

        self._require_writable()
        stage_protocol_id = _safe_component(stage_protocol_id, "stage protocol id")
        _allowed_artifacts(stage_protocol_id)
        if stage_protocol_id in self._held_stage_locks:
            raise EvidenceLockError("stage evidence lock is not reentrant")
        component = stage_protocol_id + ".lock"
        locks_fd = _open_or_create_dir_at(self._root_fd, ".locks")
        lock_fd = -1
        try:
            flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
            lock_fd = os.open(component, flags, 0o600, dir_fd=locks_fd)
            info = os.fstat(lock_fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise EvidenceIntegrityError("stage lock must be a singly-linked regular file")
            operation = fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB)
            try:
                fcntl.flock(lock_fd, operation)
            except BlockingIOError as error:
                raise EvidenceLockError("stage evidence lock is already held") from error
            self._held_stage_locks.add(stage_protocol_id)
            try:
                yield
            finally:
                self._held_stage_locks.remove(stage_protocol_id)
        finally:
            if lock_fd >= 0:
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_UN)
                finally:
                    os.close(lock_fd)
            os.close(locks_fd)

    def publish_bytes(self, stage_protocol_id: str, artifact: str, raw: bytes) -> BodyRef:
        self._require_writable()
        if artifact not in _STAGE_ARTIFACT_FILES:
            raise ValueError("artifact is not in the fixed stage catalog")
        if artifact not in _allowed_artifacts(stage_protocol_id):
            raise ValueError("artifact is forbidden for this fixed stage")
        self._require_stage_lock(stage_protocol_id)
        if artifact != "experiment_plan":
            load_canonical_json_bytes(raw)
        if len(raw) > _MAX_CANONICAL_BYTES:
            raise ValueError("immutable artifact exceeds the byte limit")
        with self._stage_fd(stage_protocol_id, create=True) as stage_fd:
            _publish_exclusive_at(stage_fd, _STAGE_ARTIFACT_FILES[artifact], raw)
        return BodyRef(hashlib.sha256(raw).hexdigest(), len(raw))

    def publish_json(self, stage_protocol_id: str, artifact: str, value: Any) -> BodyRef:
        self._require_writable()
        if artifact == "experiment_plan":
            raise ValueError("experiment plan must be published as exact bytes")
        return self.publish_bytes(stage_protocol_id, artifact, canonical_json_bytes(value))

    def read_bytes(self, stage_protocol_id: str, artifact: str) -> bytes:
        if artifact not in _STAGE_ARTIFACT_FILES:
            raise ValueError("artifact is not in the fixed stage catalog")
        if artifact not in _allowed_artifacts(stage_protocol_id):
            raise ValueError("artifact is forbidden for this fixed stage")
        with self._stage_fd(stage_protocol_id, create=False) as stage_fd:
            return _read_regular_at(stage_fd, _STAGE_ARTIFACT_FILES[artifact], _MAX_CANONICAL_BYTES)

    def read_json(self, stage_protocol_id: str, artifact: str) -> Any:
        if artifact == "experiment_plan":
            raise ValueError("experiment plan is an exact byte artifact")
        return load_canonical_json_bytes(self.read_bytes(stage_protocol_id, artifact))

    def artifact_exists(self, stage_protocol_id: str, artifact: str) -> bool:
        if artifact not in _STAGE_ARTIFACT_FILES:
            raise ValueError("artifact is not in the fixed stage catalog")
        try:
            self.read_bytes(stage_protocol_id, artifact)
            return True
        except FileNotFoundError:
            return False
        except EvidenceIntegrityError as error:
            cause = error.__cause__
            if isinstance(cause, FileNotFoundError):
                return False
            raise

    def _stage_entry_exists(self, stage_protocol_id: str) -> bool:
        """Check for a fixed stage entry without creating or trusting its type."""

        self._require_open()
        stage_protocol_id = _safe_component(
            stage_protocol_id, "stage protocol id"
        )
        _allowed_artifacts(stage_protocol_id)
        if self._writable:
            stages_fd = _open_or_create_dir_at(self._root_fd, "stages")
        else:
            stages_fd = _open_existing_dir_at(self._root_fd, "stages")
        try:
            try:
                os.stat(
                    stage_protocol_id,
                    dir_fd=stages_fd,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                return False
            return True
        finally:
            os.close(stages_fd)

    def scan_stage(self, stage_protocol_id: str) -> Dict[str, Optional[BodyRef]]:
        """Authenticate every fixed catalog path and report present bodies."""

        result: Dict[str, Optional[BodyRef]] = {}
        allowed_artifacts = _allowed_artifacts(stage_protocol_id)
        for artifact in sorted(allowed_artifacts):
            try:
                raw = self.read_bytes(stage_protocol_id, artifact)
            except FileNotFoundError:
                result[artifact] = None
            except EvidenceIntegrityError as error:
                if isinstance(error.__cause__, FileNotFoundError):
                    result[artifact] = None
                else:
                    raise
            else:
                result[artifact] = BodyRef(hashlib.sha256(raw).hexdigest(), len(raw))
        return result

    def publish_contradiction(self, stage_protocol_id: str, value: Any) -> BodyRef:
        """Publish the one external fail-closed sidecar for a poisoned stage."""

        self._require_writable()
        self._require_stage_lock(stage_protocol_id)
        name = _safe_component(stage_protocol_id, "stage protocol id") + ".json"
        raw = canonical_json_bytes(value)
        directory_fd = _open_or_create_dir_at(self._root_fd, "contradictions")
        try:
            _publish_exclusive_at(directory_fd, name, raw)
        except EvidenceConflictError:
            existing = _read_regular_at(directory_fd, name, _MAX_CANONICAL_BYTES)
            if existing != raw:
                raise
        finally:
            os.close(directory_fd)
        return BodyRef(hashlib.sha256(raw).hexdigest(), len(raw))

    def read_contradiction(self, stage_protocol_id: str) -> Any:
        self._require_open()
        name = _safe_component(stage_protocol_id, "stage protocol id") + ".json"
        if self._writable:
            directory_fd = _open_or_create_dir_at(
                self._root_fd, "contradictions"
            )
        else:
            directory_fd = _open_existing_dir_at(
                self._root_fd, "contradictions"
            )
        try:
            raw = _read_regular_at(directory_fd, name, _MAX_CANONICAL_BYTES)
        finally:
            os.close(directory_fd)
        return load_canonical_json_bytes(raw)

    @contextlib.contextmanager
    def _journal_leaf_fd(
        self,
        stage_protocol_id: str,
        phase_id: str,
        kind: str,
        *,
        create: bool,
    ) -> Iterator[int]:
        if create:
            self._require_writable()
        if kind not in ("starts", "results"):
            raise ValueError("journal kind is not fixed")
        phase_id = _safe_component(phase_id, "journal phase id")
        with self._stage_fd(stage_protocol_id, create=create) as stage_fd:
            if create:
                journal_fd = _open_or_create_dir_at(stage_fd, "journal")
            else:
                flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
                journal_fd = os.open("journal", flags, dir_fd=stage_fd)
            try:
                if create:
                    phase_fd = _open_or_create_dir_at(journal_fd, phase_id)
                else:
                    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
                    phase_fd = os.open(phase_id, flags, dir_fd=journal_fd)
                try:
                    if create:
                        leaf_fd = _open_or_create_dir_at(phase_fd, kind)
                    else:
                        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
                        leaf_fd = os.open(kind, flags, dir_fd=phase_fd)
                    try:
                        yield leaf_fd
                    finally:
                        os.close(leaf_fd)
                finally:
                    os.close(phase_fd)
            finally:
                os.close(journal_fd)

    @staticmethod
    def _journal_name(slot_index: int) -> str:
        if type(slot_index) is not int or slot_index < 0 or slot_index > 99_999_999:
            raise ValueError("journal slot index is outside the fixed range")
        return "{:08d}.json".format(slot_index)

    def publish_journal_start(
        self,
        stage_protocol_id: str,
        phase_id: str,
        slot_index: int,
        slot_id: str,
    ) -> BodyRef:
        self._require_writable()
        self._require_stage_lock(stage_protocol_id)
        body = {
            "artifact_type": "ATLAS_SLOT_START_V1",
            "phase_id": _safe_component(phase_id, "journal phase id"),
            "slot_id": _exact_string(slot_id, "slot id"),
            "slot_index": slot_index,
            "stage_protocol_id": _safe_component(stage_protocol_id, "stage protocol id"),
        }
        raw = canonical_json_bytes(body)
        with self._journal_leaf_fd(stage_protocol_id, phase_id, "starts", create=True) as leaf_fd:
            _publish_exclusive_at(leaf_fd, self._journal_name(slot_index), raw)
        return BodyRef(hashlib.sha256(raw).hexdigest(), len(raw))

    def publish_journal_result(
        self,
        stage_protocol_id: str,
        phase_id: str,
        slot_index: int,
        slot_id: str,
        status: str,
        result: Any,
    ) -> BodyRef:
        self._require_writable()
        self._require_stage_lock(stage_protocol_id)
        start = self.read_journal_start(stage_protocol_id, phase_id, slot_index)
        expected = {
            "artifact_type": "ATLAS_SLOT_START_V1",
            "phase_id": phase_id,
            "slot_id": slot_id,
            "slot_index": slot_index,
            "stage_protocol_id": stage_protocol_id,
        }
        if canonical_json_bytes(start) != canonical_json_bytes(expected):
            raise EvidenceIntegrityError("journal result does not match its immutable start")
        start_ref = canonical_body_ref(start)
        body = {
            "artifact_type": "ATLAS_SLOT_RESULT_V1",
            "phase_id": _safe_component(phase_id, "journal phase id"),
            "result": result,
            "slot_id": _exact_string(slot_id, "slot id"),
            "slot_index": slot_index,
            "stage_protocol_id": _safe_component(stage_protocol_id, "stage protocol id"),
            "start_ref": start_ref.as_dict(),
            "status": _exact_string(status, "journal status"),
        }
        raw = canonical_json_bytes(body)
        with self._journal_leaf_fd(stage_protocol_id, phase_id, "results", create=True) as leaf_fd:
            _publish_exclusive_at(leaf_fd, self._journal_name(slot_index), raw)
        return BodyRef(hashlib.sha256(raw).hexdigest(), len(raw))

    def _read_journal(
        self, stage_protocol_id: str, phase_id: str, kind: str, slot_index: int
    ) -> Any:
        try:
            with self._journal_leaf_fd(stage_protocol_id, phase_id, kind, create=False) as leaf_fd:
                raw = _read_regular_at(leaf_fd, self._journal_name(slot_index), _MAX_CANONICAL_BYTES)
        except FileNotFoundError:
            raise
        except OSError as error:
            if error.errno == errno.ENOENT:
                raise FileNotFoundError from error
            raise
        return load_canonical_json_bytes(raw)

    def read_journal_start(
        self, stage_protocol_id: str, phase_id: str, slot_index: int
    ) -> Any:
        return self._read_journal(stage_protocol_id, phase_id, "starts", slot_index)

    def read_journal_result(
        self, stage_protocol_id: str, phase_id: str, slot_index: int
    ) -> Any:
        return self._read_journal(stage_protocol_id, phase_id, "results", slot_index)

    def scan_fixed_catalog(
        self,
        stage_protocol_id: str,
        ledger_specs: Sequence["LedgerSpec"] = (),
    ) -> Dict[str, Optional[BodyRef]]:
        """Reject every path not prescribed by the stage catalog and ledgers."""

        result = self.scan_stage(stage_protocol_id)
        expected_phases = {spec.phase_id: spec for spec in ledger_specs}
        with self._stage_fd(stage_protocol_id, create=False) as stage_fd:
            observed = set(os.listdir(stage_fd))
            allowed = {
                _STAGE_ARTIFACT_FILES[name]
                for name in _allowed_artifacts(stage_protocol_id)
            } | {"journal"}
            if observed - allowed:
                raise EvidenceIntegrityError("stage directory contains a noncatalog path")
            if "journal" not in observed:
                return result
            journal_fd = os.open(
                "journal",
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=stage_fd,
            )
            try:
                phases = set(os.listdir(journal_fd))
                if phases - set(expected_phases):
                    raise EvidenceIntegrityError("journal contains a noncatalog phase")
                for phase_id in phases:
                    phase_fd = os.open(
                        phase_id,
                        os.O_RDONLY
                        | getattr(os, "O_DIRECTORY", 0)
                        | getattr(os, "O_NOFOLLOW", 0),
                        dir_fd=journal_fd,
                    )
                    try:
                        if set(os.listdir(phase_fd)) - {"starts", "results"}:
                            raise EvidenceIntegrityError("journal phase contains a noncatalog path")
                        spec = expected_phases[phase_id]
                        allowed_names = {
                            self._journal_name(index)
                            for index in range(len(spec.ordered_slot_ids))
                        }
                        for kind in ("starts", "results"):
                            try:
                                leaf_fd = os.open(
                                    kind,
                                    os.O_RDONLY
                                    | getattr(os, "O_DIRECTORY", 0)
                                    | getattr(os, "O_NOFOLLOW", 0),
                                    dir_fd=phase_fd,
                                )
                            except FileNotFoundError:
                                continue
                            try:
                                if set(os.listdir(leaf_fd)) - allowed_names:
                                    raise EvidenceIntegrityError(
                                        "journal contains a noncatalog slot path"
                                    )
                                for name in os.listdir(leaf_fd):
                                    raw = _read_regular_at(
                                        leaf_fd, name, _MAX_CANONICAL_BYTES
                                    )
                                    load_canonical_json_bytes(raw)
                            finally:
                                os.close(leaf_fd)
                    finally:
                        os.close(phase_fd)
            finally:
                os.close(journal_fd)
        return result

    def _journal_has_records(self, stage_protocol_id: str) -> bool:
        """Report whether the already-scanned fixed journal contains a record."""

        with self._stage_fd(stage_protocol_id, create=False) as stage_fd:
            try:
                journal_fd = os.open(
                    "journal",
                    os.O_RDONLY
                    | getattr(os, "O_DIRECTORY", 0)
                    | getattr(os, "O_NOFOLLOW", 0),
                    dir_fd=stage_fd,
                )
            except FileNotFoundError:
                return False
            try:
                for phase_id in os.listdir(journal_fd):
                    phase_fd = os.open(
                        phase_id,
                        os.O_RDONLY
                        | getattr(os, "O_DIRECTORY", 0)
                        | getattr(os, "O_NOFOLLOW", 0),
                        dir_fd=journal_fd,
                    )
                    try:
                        for kind in ("starts", "results"):
                            try:
                                leaf_fd = os.open(
                                    kind,
                                    os.O_RDONLY
                                    | getattr(os, "O_DIRECTORY", 0)
                                    | getattr(os, "O_NOFOLLOW", 0),
                                    dir_fd=phase_fd,
                                )
                            except FileNotFoundError:
                                continue
                            try:
                                if os.listdir(leaf_fd):
                                    return True
                            finally:
                                os.close(leaf_fd)
                    finally:
                        os.close(phase_fd)
            finally:
                os.close(journal_fd)
        return False

@dataclass(frozen=True)
class StageContract:
    stage_index: int
    stage_id: str
    stage_protocol_id: str
    prerequisite_stage_id: Optional[str]
    prerequisite_gate: Optional[str]
    required_parent_terminal_stage_ids: Tuple[str, ...]
    required_parent_terminal_predicates: Tuple[Tuple[str, str], ...]
    required_known_paths: Tuple[str, ...]
    forbidden_known_paths: Tuple[str, ...]
    checkpoint_commit: str
    checkpoint_paths: Tuple[str, ...]
    reservation_scope: str
    reservation_timing: str
    attempt_timing: str
    capability_boundary: str
    completion_gate: str
    protocol_id: str
    protocol_root: str
    evidence_protocol_id: str
    evidence_protocol_version: int
    identity_domains: Tuple[Tuple[str, bytes], ...]
    identity_payload_keys: Tuple[Tuple[str, Tuple[str, ...]], ...]

    def identity_domain(self, name: str) -> bytes:
        try:
            return dict(self.identity_domains)[name]
        except KeyError as error:
            raise ValueError("unknown stage evidence identity schema") from error

    def identity_keys(self, name: str) -> Tuple[str, ...]:
        try:
            return dict(self.identity_payload_keys)[name]
        except KeyError as error:
            raise ValueError("unknown stage evidence identity schema") from error


@dataclass(frozen=True)
class ProductionClosure:
    root: str
    payload: Dict[str, Any]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "artifact_type": "ATLAS_PRODUCTION_CLOSURE_V1",
            "identity": self.root,
            "payload": load_canonical_json_bytes(canonical_json_bytes(self.payload)),
        }


def _exact_mapping(value: Any, label: str) -> Dict[str, Any]:
    if type(value) is not dict:
        raise EvidenceIntegrityError("{} must be an exact object".format(label))
    return value


def _exact_keys(value: Any, expected: Sequence[str], label: str) -> Dict[str, Any]:
    result = _exact_mapping(value, label)
    if set(result) != set(expected):
        raise EvidenceIntegrityError("{} has the wrong keys".format(label))
    return result


def _require_payload_keys(
    payload: Any, expected: Sequence[str], label: str
) -> Dict[str, Any]:
    result = _exact_mapping(payload, "{} payload".format(label))
    if set(result) != set(expected):
        raise EvidenceIntegrityError("{} identity payload has the wrong keys".format(label))
    return result


def _exact_string(value: Any, label: str) -> str:
    if type(value) is not str or not value:
        raise EvidenceIntegrityError("{} must be a nonempty exact string".format(label))
    return value


def _exact_optional_string(value: Any, label: str) -> Optional[str]:
    if value is None:
        return None
    return _exact_string(value, label)


def _exact_hex(value: Any, length: int, label: str) -> str:
    text = _exact_string(value, label)
    pattern = _HEX40 if length == 40 else _HEX64
    if pattern.fullmatch(text) is None:
        raise EvidenceIntegrityError("{} must be lowercase hex".format(label))
    return text


def _string_tuple(value: Any, label: str, *, unique: bool = True) -> Tuple[str, ...]:
    if type(value) is not list:
        raise EvidenceIntegrityError("{} must be an exact list".format(label))
    result = tuple(_exact_string(item, "{} item".format(label)) for item in value)
    if unique and len(set(result)) != len(result):
        raise EvidenceIntegrityError("{} contains duplicates".format(label))
    return result


def _authenticate_protocol(protocol_value: Any) -> Dict[str, Any]:
    raw = canonical_json_bytes(protocol_value)
    if hashlib.sha256(raw).hexdigest() != atlas_protocol.ATLAS_PROTOCOL_CANONICAL_SHA256_V1:
        raise EvidenceIntegrityError("atlas protocol canonical SHA-256 is not frozen")
    protocol = _exact_mapping(load_canonical_json_bytes(raw), "atlas protocol")
    if protocol.get("protocol_id") != atlas_protocol.ATLAS_PROTOCOL_ID_V1:
        raise EvidenceIntegrityError("atlas protocol id is not frozen")
    if protocol.get("protocol_root") != atlas_protocol.ATLAS_PROTOCOL_ROOT_V1:
        raise EvidenceIntegrityError("atlas protocol root is not frozen")
    unsigned = dict(protocol)
    unsigned.pop("protocol_root", None)
    observed_root = domain_identity(atlas_protocol._PROTOCOL_ROOT_DOMAIN_V1, unsigned)
    if observed_root != protocol["protocol_root"]:
        raise EvidenceIntegrityError("atlas protocol self-root does not reconstruct")
    return protocol


def _extract_stage_contract_from_components(
    protocol_id: Any,
    protocol_root: Any,
    sequence_value: Any,
    provenance_value: Any,
    stage_id: str,
) -> StageContract:
    stage_id = _exact_string(stage_id, "stage id")
    provenance = _exact_mapping(
        provenance_value, "manifest and run provenance"
    )
    stages = provenance.get("stages")
    if type(stages) is not list or len(stages) != 6:
        raise EvidenceIntegrityError("atlas evidence protocol must contain six stages")
    sequence = sequence_value
    if type(sequence) is not list or len(sequence) != len(stages):
        raise EvidenceIntegrityError("atlas stage sequence is invalid")
    selected = None
    for index, item in enumerate(stages):
        stage = _exact_mapping(item, "stage contract")
        if stage.get("stage_index") != index or stage.get("stage_id") != sequence[index]:
            raise EvidenceIntegrityError("atlas stage order is invalid")
        if stage.get("stage_id") == stage_id:
            selected = stage
    if selected is None:
        raise ValueError("unknown atlas evidence stage id")
    parents = _string_tuple(
        selected.get("required_parent_terminal_stage_ids"),
        "required parent terminal stage ids",
    )
    predicates_value = _exact_mapping(
        selected.get("required_parent_terminal_predicates"),
        "required parent terminal predicates",
    )
    if set(predicates_value) != set(parents):
        raise EvidenceIntegrityError("parent predicate membership is not exact")
    predicates = tuple(
        (parent, _exact_string(predicates_value[parent], "parent predicate"))
        for parent in parents
    )
    policy = _exact_mapping(selected.get("source_closure_policy"), "source closure policy")
    if policy.get("stage_id") != stage_id:
        raise EvidenceIntegrityError("source closure policy belongs to another stage")
    required = _string_tuple(policy.get("required_known_paths"), "required known paths")
    forbidden = _string_tuple(policy.get("forbidden_known_paths"), "forbidden known paths")
    if set(required) & set(forbidden):
        raise EvidenceIntegrityError("required and forbidden closure paths overlap")
    checkpoint = _exact_mapping(
        policy.get("checkpoint_blob_equivalence"), "checkpoint blob equivalence"
    )
    checkpoint_paths = _string_tuple(checkpoint.get("paths"), "checkpoint paths")
    if not set(checkpoint_paths).issubset(required):
        raise EvidenceIntegrityError("checkpoint paths are not required closure paths")
    schemas = _exact_mapping(provenance.get("artifact_identity_schemas"), "identity schemas")
    schema_names = (
        "production_closure_root",
        "stage_reservation_id",
        "stage_attempt_id",
        "stage_blocked_id",
        "stage_orphaned_id",
        "stage_terminal_seal",
    )
    domains = []
    payload_keys = []
    for schema_name in schema_names:
        schema = _exact_mapping(schemas.get(schema_name), "{} schema".format(schema_name))
        try:
            domain = bytes.fromhex(_exact_string(schema.get("domain_hex"), "domain hex"))
        except ValueError as error:
            raise EvidenceIntegrityError("invalid identity domain hex") from error
        if not domain.endswith(b"\0"):
            raise EvidenceIntegrityError("identity domain is not NUL terminated")
        keys = _string_tuple(schema.get("payload_keys"), "identity payload keys")
        domains.append((schema_name, domain))
        payload_keys.append((schema_name, keys))
    return StageContract(
        stage_index=selected["stage_index"],
        stage_id=stage_id,
        stage_protocol_id=_exact_string(selected.get("stage_protocol_id"), "stage protocol id"),
        prerequisite_stage_id=_exact_optional_string(
            selected.get("prerequisite_stage_id"), "prerequisite stage id"
        ),
        prerequisite_gate=_exact_optional_string(
            selected.get("prerequisite_gate"), "prerequisite gate"
        ),
        required_parent_terminal_stage_ids=parents,
        required_parent_terminal_predicates=predicates,
        required_known_paths=required,
        forbidden_known_paths=forbidden,
        checkpoint_commit=_exact_hex(
            checkpoint.get("reference_commit"), 40, "checkpoint commit"
        ),
        checkpoint_paths=checkpoint_paths,
        reservation_scope=_exact_string(selected.get("reservation_scope"), "reservation scope"),
        reservation_timing=_exact_string(selected.get("reservation_timing"), "reservation timing"),
        attempt_timing=_exact_string(selected.get("attempt_timing"), "attempt timing"),
        capability_boundary=_exact_string(
            selected.get("capability_boundary"), "capability boundary"
        ),
        completion_gate=_exact_string(selected.get("completion_gate"), "completion gate"),
        protocol_id=_exact_string(protocol_id, "protocol id"),
        protocol_root=_exact_hex(protocol_root, 64, "protocol root"),
        evidence_protocol_id=_exact_string(
            provenance.get("evidence_protocol_id"), "evidence protocol id"
        ),
        evidence_protocol_version=provenance.get("evidence_protocol_version"),
        identity_domains=tuple(domains),
        identity_payload_keys=tuple(payload_keys),
    )


def extract_stage_contract(protocol_value: Any, stage_id: str) -> StageContract:
    """Authenticate the protocol without exporting selection/candidate bytes."""

    protocol = _authenticate_protocol(protocol_value)
    return _extract_stage_contract_from_components(
        protocol.get("protocol_id"),
        protocol.get("protocol_root"),
        protocol.get("stage_sequence"),
        protocol.get("manifest_and_run_provenance"),
        stage_id,
    )


def extract_recovery_stage_contract(stage_id: str) -> StageContract:
    """Build a candidate-neutral contract solely for evidence recovery.

    Reconstructing the full frozen selection during recovery would read the
    confirmation candidate block and violate the no-capability recovery rule.
    The evidence section is independent of selection bodies, so it supplies the
    expected contract coordinates; any existing stage evidence is then bound to
    the separately published, fully authenticated manifest bootstrap under lock.
    """

    provenance = atlas_protocol._execution_evidence_protocol()
    stages = _exact_mapping(provenance, "recovery evidence protocol").get("stages")
    if type(stages) is not list:
        raise EvidenceIntegrityError("recovery evidence protocol stages are invalid")
    sequence = [
        _exact_mapping(value, "recovery stage").get("stage_id")
        for value in stages
    ]
    contract = _extract_stage_contract_from_components(
        atlas_protocol.ATLAS_PROTOCOL_ID_V1,
        atlas_protocol.ATLAS_PROTOCOL_ROOT_V1,
        sequence,
        provenance,
        stage_id,
    )
    if contract.evidence_protocol_id != "plan0013-atlas-development-evidence-v2":
        raise EvidenceIntegrityError("recovery evidence protocol identity drifted")
    if (
        type(contract.evidence_protocol_version) is not int
        or contract.evidence_protocol_version != 2
    ):
        raise EvidenceIntegrityError("recovery evidence protocol version drifted")
    return contract


def _run_git(repository: Path, arguments: Sequence[str], *, check: bool = True) -> bytes:
    command = ["git", "-C", str(repository)] + list(arguments)
    process = subprocess.run(
        command,
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )
    if check and process.returncode != 0:
        raise EvidenceIntegrityError(
            "Git evidence check failed: {}".format(process.stderr.decode("utf-8", "replace").strip())
        )
    return process.stdout


def _git_hex(repository: Path, arguments: Sequence[str], length: int, label: str) -> str:
    try:
        value = _run_git(repository, arguments).decode("ascii", "strict").strip()
    except UnicodeDecodeError as error:
        raise EvidenceIntegrityError("{} is not ASCII".format(label)) from error
    return _exact_hex(value, length, label)


def capture_clean_head(repository: os.PathLike) -> Dict[str, str]:
    """Bind a repository to an exact clean HEAD commit and tree."""

    requested = Path(repository).resolve()
    try:
        top = Path(
            _run_git(requested, ["rev-parse", "--show-toplevel"])
            .decode("utf-8", "strict")
            .strip()
        ).resolve()
    except UnicodeDecodeError as error:
        raise EvidenceIntegrityError("Git repository path is not UTF-8") from error
    if top != requested:
        raise EvidenceIntegrityError("repository argument must be the exact Git top level")
    status_bytes = _run_git(top, ["status", "--porcelain=v1", "--untracked-files=all"])
    if status_bytes:
        raise EvidenceIntegrityError("production source repository is not clean")
    source_commit = _git_hex(top, ["rev-parse", "HEAD^{commit}"], 40, "source commit")
    source_tree = _git_hex(top, ["rev-parse", "HEAD^{tree}"], 40, "source tree")
    commit_tree = _git_hex(
        top, ["rev-parse", source_commit + "^{tree}"], 40, "source commit tree"
    )
    if commit_tree != source_tree:
        raise EvidenceIntegrityError("HEAD commit tree does not reconstruct")
    return {"source_commit": source_commit, "source_tree": source_tree}


def verify_commit_relation(
    repository: os.PathLike, ancestor_commit: str, descendant_commit: str
) -> None:
    """Require two commits to exist and the first to be a strict ancestor."""

    repository_path = Path(repository).resolve()
    ancestor = _git_hex(
        repository_path, ["rev-parse", ancestor_commit + "^{commit}"], 40, "ancestor commit"
    )
    descendant = _git_hex(
        repository_path,
        ["rev-parse", descendant_commit + "^{commit}"],
        40,
        "descendant commit",
    )
    if ancestor == descendant:
        raise EvidenceIntegrityError("commit relation must be a strict ancestry relation")
    process = subprocess.run(
        ["git", "-C", str(repository_path), "merge-base", "--is-ancestor", ancestor, descendant],
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )
    if process.returncode != 0:
        raise EvidenceIntegrityError("selector commit is not a strict evaluator ancestor")


def _safe_repo_path(value: str) -> str:
    if type(value) is not str or not value or value.startswith(("/", "\\")):
        raise EvidenceIntegrityError("closure path must be repository-relative")
    if "\\" in value:
        raise EvidenceIntegrityError("closure path uses a noncanonical separator")
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise EvidenceIntegrityError("closure path traverses outside the repository")
    try:
        value.encode("ascii", "strict")
    except UnicodeEncodeError as error:
        raise EvidenceIntegrityError("closure paths must be ASCII") from error
    return value


def _module_path(repository: Path, module_parts: Sequence[str]) -> Optional[str]:
    if not module_parts or module_parts[0] != "parity_forge":
        return None
    base = Path("src").joinpath(*module_parts)
    module_file = repository / base.with_suffix(".py")
    package_file = repository / base / "__init__.py"
    matches = [path for path in (module_file, package_file) if path.is_file()]
    if len(matches) > 1:
        raise EvidenceIntegrityError("ambiguous local Python module")
    if not matches:
        return None
    return matches[0].relative_to(repository).as_posix()


def _module_parts_for_path(path: str) -> Tuple[str, ...]:
    parts = Path(path).parts
    if len(parts) < 3 or parts[0:2] != ("src", "parity_forge") or not path.endswith(".py"):
        raise EvidenceIntegrityError("closure Python path is outside src/parity_forge")
    relative = list(parts[1:])
    if relative[-1] == "__init__.py":
        relative = relative[:-1]
    else:
        relative[-1] = relative[-1][:-3]
    return tuple(relative)


def _package_init_paths(repository: Path, module_parts: Sequence[str]) -> Tuple[str, ...]:
    result = []
    for count in range(1, len(module_parts) + 1):
        path = repository / "src" / Path(*module_parts[:count]) / "__init__.py"
        if path.is_file():
            result.append(path.relative_to(repository).as_posix())
    return tuple(result)


def _local_import_paths(repository: Path, path: str, raw: bytes) -> Tuple[str, ...]:
    try:
        tree = ast.parse(raw.decode("utf-8", "strict"), filename=path)
    except (SyntaxError, UnicodeDecodeError) as error:
        raise EvidenceIntegrityError("closure Python source cannot be parsed") from error
    module_parts = _module_parts_for_path(path)
    is_package = path.endswith("/__init__.py")
    current_package = module_parts if is_package else module_parts[:-1]
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            function = node.func
            dynamic = (
                isinstance(function, ast.Name) and function.id == "__import__"
            ) or (
                isinstance(function, ast.Attribute) and function.attr == "import_module"
            )
            if dynamic:
                raise EvidenceIntegrityError("dynamic imports are forbidden in a production closure")
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
                            raise EvidenceIntegrityError("relative star import is not statically closed")
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
            resolved = _module_path(repository, candidate)
            if resolved is not None:
                found = True
                imports.add(resolved)
                imports.update(_package_init_paths(repository, candidate[:-1]))
        if explicitly_local and candidates and not found:
            # ``from module import symbol`` often has no child module; the base
            # module candidate was included first and counts as resolution.
            first = _module_path(repository, candidates[0])
            if first is None:
                raise EvidenceIntegrityError("local import target is absent from the repository")
    return tuple(sorted(imports, key=lambda item: item.encode("ascii")))


def _read_source_file(repository: Path, path: str) -> bytes:
    safe = _safe_repo_path(path)
    target = repository / safe
    try:
        info = target.lstat()
    except FileNotFoundError as error:
        raise EvidenceIntegrityError("closure file does not exist") from error
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise EvidenceIntegrityError("closure file must be a singly-linked regular file")
    resolved = target.resolve()
    try:
        resolved.relative_to(repository)
    except ValueError as error:
        raise EvidenceIntegrityError("closure path escapes the repository") from error
    raw = target.read_bytes()
    after = target.stat()
    if (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    ):
        raise EvidenceIntegrityError("closure file changed while reading")
    return raw


def _closure_paths(
    repository: Path, entrypoint_paths: Sequence[str]
) -> Tuple[Tuple[str, ...], Dict[str, bytes]]:
    if type(entrypoint_paths) not in (list, tuple) or not entrypoint_paths:
        raise ValueError("production closure requires at least one entrypoint")
    entrypoints = tuple(_safe_repo_path(path) for path in entrypoint_paths)
    if tuple(sorted(set(entrypoints), key=lambda item: item.encode("ascii"))) != entrypoints:
        raise EvidenceIntegrityError("entrypoint paths must be unique strict ASCII order")
    pending = list(entrypoints)
    observed = set()
    contents: Dict[str, bytes] = {}
    while pending:
        path = pending.pop()
        if path in observed:
            continue
        raw = _read_source_file(repository, path)
        observed.add(path)
        contents[path] = raw
        if path.endswith(".py"):
            for dependency in _local_import_paths(repository, path, raw):
                if dependency not in observed:
                    pending.append(dependency)
    ordered = tuple(sorted(observed, key=lambda item: item.encode("ascii")))
    return ordered, contents


def _build_production_closure_at_head(
    repository: Path,
    contract: StageContract,
    entrypoint_paths: Sequence[str],
    manifest_experiment_plan_bytes: bytes,
    source_commit: str,
    source_tree: str,
) -> ProductionClosure:
    if type(manifest_experiment_plan_bytes) is not bytes:
        raise TypeError("manifest experiment plan must be exact bytes")
    if len(manifest_experiment_plan_bytes) > _MAX_CANONICAL_BYTES:
        raise ValueError("manifest experiment plan exceeds the byte limit")
    paths, contents = _closure_paths(repository, entrypoint_paths)
    missing = set(contract.required_known_paths) - set(paths)
    forbidden = set(contract.forbidden_known_paths) & set(paths)
    if missing:
        raise EvidenceIntegrityError("production closure is missing required paths: {}".format(sorted(missing)))
    if forbidden:
        raise EvidenceIntegrityError("production closure contains forbidden paths: {}".format(sorted(forbidden)))
    records = []
    for path in paths:
        commit_blob = _git_hex(
            repository, ["rev-parse", source_commit + ":" + path], 40, "source commit blob"
        )
        commit_bytes = _run_git(repository, ["show", source_commit + ":" + path])
        raw = contents[path]
        if commit_bytes != raw:
            raise EvidenceIntegrityError("current closure bytes differ from the source commit")
        # Avoid a subprocess stdin capability: Git's committed blob was already
        # compared byte-for-byte, so its authenticated id binds these bytes.
        records.append(
            {
                "byte_count": len(raw),
                "current_sha256": hashlib.sha256(raw).hexdigest(),
                "path": path,
                "source_commit_blob_sha1": commit_blob,
            }
        )
    for path in contract.checkpoint_paths:
        current_blob = _git_hex(
            repository, ["rev-parse", source_commit + ":" + path], 40, "production blob"
        )
        checkpoint_blob = _git_hex(
            repository,
            ["rev-parse", contract.checkpoint_commit + ":" + path],
            40,
            "checkpoint blob",
        )
        if current_blob != checkpoint_blob:
            raise EvidenceIntegrityError("production closure differs from its reviewed checkpoint")
    protocol_records = [
        record for record in records if record["path"] == "src/parity_forge/atlas_protocol.py"
    ]
    if len(protocol_records) != 1:
        raise EvidenceIntegrityError("production closure lacks one protocol blob")
    payload = {
        "manifest_experiment_plan_sha256": hashlib.sha256(
            manifest_experiment_plan_bytes
        ).hexdigest(),
        "manifest_protocol_blob_identity": protocol_records[0]["source_commit_blob_sha1"],
        "ordered_entrypoint_paths": list(entrypoint_paths),
        "ordered_file_records": records,
        "source_commit": source_commit,
        "source_tree": source_tree,
        "stage_id": contract.stage_id,
    }
    expected_keys = contract.identity_keys("production_closure_root")
    _require_payload_keys(payload, expected_keys, "production closure")
    root = domain_identity(contract.identity_domain("production_closure_root"), payload)
    return ProductionClosure(root, payload)


def build_production_closure(
    repository: os.PathLike,
    contract: StageContract,
    entrypoint_paths: Sequence[str],
    manifest_experiment_plan_bytes: bytes,
) -> ProductionClosure:
    """Build one closure from a clean HEAD and reviewed checkpoint blobs."""

    repository_path = Path(repository).resolve()
    head = capture_clean_head(repository_path)
    return _build_production_closure_at_head(
        repository_path,
        contract,
        entrypoint_paths,
        manifest_experiment_plan_bytes,
        head["source_commit"],
        head["source_tree"],
    )


def build_all_production_closures(
    repository: os.PathLike,
    contracts: Sequence[StageContract],
    entrypoints_by_stage: Mapping[str, Sequence[str]],
    manifest_experiment_plan_bytes: bytes,
) -> Tuple[ProductionClosure, ...]:
    """Freeze all six concrete stage closures at one clean source commit."""

    if type(contracts) not in (list, tuple) or len(contracts) != 6:
        raise EvidenceIntegrityError("all six stage contracts must be frozen together")
    if type(entrypoints_by_stage) is not dict:
        raise TypeError("stage entrypoints must be an exact mapping")
    ordered = tuple(sorted(contracts, key=lambda item: item.stage_index))
    if tuple(item.stage_index for item in ordered) != tuple(range(6)):
        raise EvidenceIntegrityError("stage contracts are not a complete ordered sequence")
    stage_ids = tuple(item.stage_id for item in ordered)
    if set(entrypoints_by_stage) != set(stage_ids):
        raise EvidenceIntegrityError("entrypoint mapping does not cover exactly all stages")
    repository_path = Path(repository).resolve()
    head = capture_clean_head(repository_path)
    return tuple(
        _build_production_closure_at_head(
            repository_path,
            contract,
            entrypoints_by_stage[contract.stage_id],
            manifest_experiment_plan_bytes,
            head["source_commit"],
            head["source_tree"],
        )
        for contract in ordered
    )


def reseal_production_closure(
    repository: os.PathLike,
    contract: StageContract,
    closure: ProductionClosure,
    manifest_experiment_plan_bytes: bytes,
) -> None:
    """Rebuild a frozen closure byte-for-byte without requiring unrelated cleanliness."""

    if not isinstance(closure, ProductionClosure):
        raise TypeError("closure must be a ProductionClosure")
    repository_path = Path(repository).resolve()
    head_commit = _git_hex(repository_path, ["rev-parse", "HEAD^{commit}"], 40, "HEAD commit")
    head_tree = _git_hex(repository_path, ["rev-parse", "HEAD^{tree}"], 40, "HEAD tree")
    if head_commit != closure.payload.get("source_commit") or head_tree != closure.payload.get(
        "source_tree"
    ):
        raise EvidenceIntegrityError("production HEAD changed after reservation")
    entrypoints = closure.payload.get("ordered_entrypoint_paths")
    if type(entrypoints) is not list:
        raise EvidenceIntegrityError("production closure entrypoints are invalid")
    rebuilt = _build_production_closure_at_head(
        repository_path,
        contract,
        entrypoints,
        manifest_experiment_plan_bytes,
        head_commit,
        head_tree,
    )
    if canonical_json_bytes(rebuilt.as_dict()) != canonical_json_bytes(closure.as_dict()):
        raise EvidenceIntegrityError("production closure failed byte-for-byte reseal")


def _clone_json(value: Any) -> Any:
    return load_canonical_json_bytes(canonical_json_bytes(value))


def _validate_closure(
    contract: StageContract, value: Any
) -> ProductionClosure:
    envelope = _exact_keys(
        value,
        ("artifact_type", "identity", "payload"),
        "production closure envelope",
    )
    if envelope["artifact_type"] != "ATLAS_PRODUCTION_CLOSURE_V1":
        raise EvidenceIntegrityError("production closure artifact type is invalid")
    payload = _require_payload_keys(
        envelope["payload"],
        contract.identity_keys("production_closure_root"),
        "production closure",
    )
    identity = _exact_hex(envelope["identity"], 64, "production closure identity")
    if identity != domain_identity(
        contract.identity_domain("production_closure_root"), payload
    ):
        raise EvidenceIntegrityError("production closure identity does not reconstruct")
    if payload.get("stage_id") != contract.stage_id:
        raise EvidenceIntegrityError("production closure belongs to another stage")
    _exact_hex(payload.get("source_commit"), 40, "closure source commit")
    _exact_hex(payload.get("source_tree"), 40, "closure source tree")
    _exact_hex(
        payload.get("manifest_experiment_plan_sha256"),
        64,
        "closure experiment plan SHA-256",
    )
    _exact_hex(
        payload.get("manifest_protocol_blob_identity"),
        40,
        "closure protocol blob identity",
    )
    entrypoints = _string_tuple(
        payload.get("ordered_entrypoint_paths"), "closure entrypoint paths"
    )
    if tuple(sorted(entrypoints, key=lambda item: item.encode("ascii"))) != entrypoints:
        raise EvidenceIntegrityError("closure entrypoints are not in strict ASCII order")
    records_value = payload.get("ordered_file_records")
    if type(records_value) is not list or not records_value:
        raise EvidenceIntegrityError("closure file records must be a nonempty exact list")
    paths = []
    protocol_blob = None
    for index, item in enumerate(records_value):
        record = _exact_keys(
            item,
            ("byte_count", "current_sha256", "path", "source_commit_blob_sha1"),
            "closure file record",
        )
        path = _safe_repo_path(record["path"])
        paths.append(path)
        if type(record["byte_count"]) is not int or record["byte_count"] < 0:
            raise EvidenceIntegrityError("closure byte count is invalid")
        _exact_hex(record["current_sha256"], 64, "closure current SHA-256")
        blob = _exact_hex(record["source_commit_blob_sha1"], 40, "closure Git blob")
        if path == "src/parity_forge/atlas_protocol.py":
            protocol_blob = blob
    if tuple(sorted(set(paths), key=lambda item: item.encode("ascii"))) != tuple(paths):
        raise EvidenceIntegrityError("closure paths are not unique strict ASCII order")
    if not set(entrypoints).issubset(paths):
        raise EvidenceIntegrityError("closure entrypoints are not closure members")
    if not set(contract.required_known_paths).issubset(paths):
        raise EvidenceIntegrityError("closure omits a required known path")
    if set(contract.forbidden_known_paths) & set(paths):
        raise EvidenceIntegrityError("closure includes a forbidden known path")
    if protocol_blob != payload["manifest_protocol_blob_identity"]:
        raise EvidenceIntegrityError("closure protocol blob binding is inconsistent")
    return ProductionClosure(identity, _clone_json(payload))


def _make_identity_artifact(
    contract: StageContract,
    schema_name: str,
    artifact_type: str,
    payload: Dict[str, Any],
    references: Dict[str, Any],
) -> Dict[str, Any]:
    _require_payload_keys(payload, contract.identity_keys(schema_name), schema_name)
    identity = domain_identity(contract.identity_domain(schema_name), payload)
    return {
        "artifact_type": artifact_type,
        "identity": identity,
        "payload": _clone_json(payload),
        "references": _clone_json(references),
    }


def _validate_identity_artifact(
    contract: StageContract,
    value: Any,
    schema_name: str,
    artifact_type: str,
) -> Dict[str, Any]:
    envelope = _exact_keys(
        value,
        ("artifact_type", "identity", "payload", "references"),
        artifact_type,
    )
    if envelope["artifact_type"] != artifact_type:
        raise EvidenceIntegrityError("{} artifact type is invalid".format(artifact_type))
    payload = _require_payload_keys(
        envelope["payload"], contract.identity_keys(schema_name), schema_name
    )
    identity = _exact_hex(envelope["identity"], 64, "{} identity".format(schema_name))
    expected = domain_identity(contract.identity_domain(schema_name), payload)
    if identity != expected:
        raise EvidenceIntegrityError("{} identity does not reconstruct".format(schema_name))
    _exact_mapping(envelope["references"], "{} references".format(schema_name))
    return envelope


def _validate_terminal_basic(contract: StageContract, value: Any) -> Dict[str, Any]:
    envelope = _validate_identity_artifact(
        contract,
        value,
        "stage_terminal_seal",
        "ATLAS_STAGE_TERMINAL_SEAL_V1",
    )
    payload = envelope["payload"]
    lifecycle = payload.get("lifecycle")
    if lifecycle not in ("BLOCKED", "ORPHANED", "FAILED", "COMPLETED"):
        raise EvidenceIntegrityError("terminal lifecycle is invalid")
    for key in (
        "attempt_id_or_null",
        "blocked_id_or_null",
        "completed_root_or_null",
        "failure_root_or_null",
        "orphaned_id_or_null",
        "partial_evidence_root_or_null",
        "reservation_id_or_null",
    ):
        if payload[key] is not None:
            _exact_hex(payload[key], 64, "terminal {}".format(key))
    expected_nonnull = {
        "BLOCKED": {"blocked_id_or_null"},
        "ORPHANED": {"reservation_id_or_null", "orphaned_id_or_null"},
        "FAILED": {
            "reservation_id_or_null",
            "attempt_id_or_null",
            "failure_root_or_null",
        },
        "COMPLETED": {
            "reservation_id_or_null",
            "attempt_id_or_null",
            "completed_root_or_null",
        },
    }[lifecycle]
    nullable = {
        "attempt_id_or_null",
        "blocked_id_or_null",
        "completed_root_or_null",
        "failure_root_or_null",
        "orphaned_id_or_null",
        "partial_evidence_root_or_null",
        "reservation_id_or_null",
    }
    for key in nullable:
        if key in expected_nonnull and payload[key] is None:
            raise EvidenceIntegrityError("terminal lifecycle is missing a required reference")
        if key not in expected_nonnull:
            allowed_optional = lifecycle == "ORPHANED" and key in (
                "attempt_id_or_null",
                "partial_evidence_root_or_null",
            )
            allowed_optional = allowed_optional or (
                lifecycle == "FAILED" and key == "partial_evidence_root_or_null"
            )
            if not allowed_optional and payload[key] is not None:
                raise EvidenceIntegrityError("terminal lifecycle has a forbidden reference")
    _exact_string(payload.get("stage_id"), "terminal stage id")
    _exact_string(payload.get("stage_protocol_id"), "terminal stage protocol id")
    return envelope


def _ordered_parent_seals(
    contract: StageContract, values: Sequence[Any]
) -> Tuple[Dict[str, Any], ...]:
    if type(values) not in (list, tuple):
        raise TypeError("parent terminal seals must be an exact sequence")
    if len(values) != len(contract.required_parent_terminal_stage_ids):
        raise EvidenceIntegrityError("parent terminal seal membership is not exact")
    result = tuple(_validate_terminal_basic(contract, value) for value in values)
    observed_ids = tuple(item["payload"]["stage_id"] for item in result)
    if observed_ids != contract.required_parent_terminal_stage_ids:
        raise EvidenceIntegrityError("parent terminal seal order is not exact")
    identities = tuple(item["identity"] for item in result)
    if len(set(identities)) != len(identities):
        raise EvidenceIntegrityError("parent terminal seals contain duplicates")
    return result


def _manifest_ref_from_parents(
    contract: StageContract, parents: Sequence[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    if contract.stage_id == "OUTCOME_FREE_DEVELOPMENT_MANIFEST":
        if parents:
            raise EvidenceIntegrityError("manifest stage cannot have parent evidence")
        return None
    manifest = next(
        (
            item
            for item in parents
            if item["payload"]["stage_id"] == "OUTCOME_FREE_DEVELOPMENT_MANIFEST"
        ),
        None,
    )
    if manifest is None:
        raise EvidenceIntegrityError("downstream stage lacks the manifest terminal seal")
    lifecycle = manifest["payload"]["lifecycle"]
    if lifecycle == "COMPLETED":
        return {
            "kind": "COMPLETED_MANIFEST",
            "manifest_completed_root_or_null": manifest["payload"]["completed_root_or_null"],
            "manifest_stage_terminal_seal": manifest["identity"],
        }
    if lifecycle in ("FAILED", "ORPHANED"):
        return {
            "kind": "UNAVAILABLE_MANIFEST",
            "manifest_completed_root_or_null": None,
            "manifest_stage_terminal_seal": manifest["identity"],
        }
    raise EvidenceIntegrityError("manifest terminal lifecycle cannot form a manifest reference")


def _first_failed_parent(
    contract: StageContract, parents: Sequence[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    predicates = dict(contract.required_parent_terminal_predicates)
    for parent in parents:
        predicate = predicates[parent["payload"]["stage_id"]]
        if predicate == "COMPLETED_VALID":
            if parent["payload"]["lifecycle"] != "COMPLETED":
                return parent
        elif predicate == "TERMINAL_SEAL_PRESENT":
            continue
        else:
            raise EvidenceIntegrityError("unknown parent terminal predicate")
    return None


def build_reservation(
    contract: StageContract,
    production_closure: ProductionClosure,
    ordered_parent_terminal_seals: Sequence[Any],
) -> Dict[str, Any]:
    closure = _validate_closure(contract, production_closure.as_dict())
    parents = _ordered_parent_seals(contract, ordered_parent_terminal_seals)
    failed = _first_failed_parent(contract, parents)
    if failed is not None:
        raise EvidenceIntegrityError("a failed prerequisite must be sealed as BLOCKED")
    manifest_ref = _manifest_ref_from_parents(contract, parents)
    if contract.stage_id not in (
        "OUTCOME_FREE_DEVELOPMENT_MANIFEST",
        "ASSESSMENT_AND_INSPECTION",
    ) and manifest_ref["kind"] != "COMPLETED_MANIFEST":
        raise EvidenceIntegrityError("outcome-capable stage requires a completed manifest")
    payload = {
        "evidence_protocol_id": contract.evidence_protocol_id,
        "manifest_evidence_ref_or_null": manifest_ref,
        "manifest_experiment_plan_sha256": closure.payload[
            "manifest_experiment_plan_sha256"
        ],
        "ordered_parent_terminal_seals": [item["identity"] for item in parents],
        "production_closure_root": closure.root,
        "protocol_id": contract.protocol_id,
        "protocol_root": contract.protocol_root,
        "stage_id": contract.stage_id,
        "stage_protocol_id": contract.stage_protocol_id,
    }
    references = {
        "ordered_parent_terminal_seals": list(parents),
        "production_closure": closure.as_dict(),
    }
    return _make_identity_artifact(
        contract,
        "stage_reservation_id",
        "ATLAS_STAGE_RESERVATION_V1",
        payload,
        references,
    )


def build_attempt(
    contract: StageContract,
    reservation: Any,
) -> Dict[str, Any]:
    reservation_value = _validate_identity_artifact(
        contract,
        reservation,
        "stage_reservation_id",
        "ATLAS_STAGE_RESERVATION_V1",
    )
    if reservation_value["payload"].get("stage_id") != contract.stage_id or reservation_value[
        "payload"
    ].get("stage_protocol_id") != contract.stage_protocol_id:
        raise EvidenceIntegrityError("reservation belongs to another stage chain")
    closure = _validate_closure(
        contract, reservation_value["references"].get("production_closure")
    )
    if closure.root != reservation_value["payload"]["production_closure_root"]:
        raise EvidenceIntegrityError("reservation closure reference is inconsistent")
    payload = {
        "attempt_index": 0,
        "production_closure_root": closure.root,
        "reservation_id": reservation_value["identity"],
        "source_commit": closure.payload["source_commit"],
        "source_tree": closure.payload["source_tree"],
    }
    return _make_identity_artifact(
        contract,
        "stage_attempt_id",
        "ATLAS_STAGE_ATTEMPT_V1",
        payload,
        {
            "production_closure": closure.as_dict(),
            "stage_reservation": reservation_value,
        },
    )


def build_blocked(
    contract: StageContract,
    production_closure: ProductionClosure,
    ordered_parent_terminal_seals: Sequence[Any],
) -> Dict[str, Any]:
    closure = _validate_closure(contract, production_closure.as_dict())
    parents = _ordered_parent_seals(contract, ordered_parent_terminal_seals)
    failed = _first_failed_parent(contract, parents)
    if failed is None:
        raise EvidenceIntegrityError("BLOCKED requires the first closed prerequisite failure")
    manifest_ref = _manifest_ref_from_parents(contract, parents)
    payload = {
        "evidence_protocol_id": contract.evidence_protocol_id,
        "failed_prerequisite_stage_id": failed["payload"]["stage_id"],
        "manifest_evidence_ref": manifest_ref,
        "prerequisite_terminal_seal": failed["identity"],
        "production_closure_root": closure.root,
        "protocol_id": contract.protocol_id,
        "protocol_root": contract.protocol_root,
        "stage_id": contract.stage_id,
        "stage_protocol_id": contract.stage_protocol_id,
    }
    return _make_identity_artifact(
        contract,
        "stage_blocked_id",
        "ATLAS_STAGE_BLOCKED_V1",
        payload,
        {
            "ordered_parent_terminal_seals": list(parents),
            "prerequisite_terminal_seal": failed,
            "production_closure": closure.as_dict(),
        },
    )


def _validate_reservation_for_contract(
    contract: StageContract, reservation: Any
) -> Dict[str, Any]:
    envelope = _validate_identity_artifact(
        contract,
        reservation,
        "stage_reservation_id",
        "ATLAS_STAGE_RESERVATION_V1",
    )
    references = envelope["references"]
    parents = references.get("ordered_parent_terminal_seals")
    closure_value = references.get("production_closure")
    if type(parents) is not list or closure_value is None:
        raise EvidenceIntegrityError("reservation references are incomplete")
    closure = _validate_closure(contract, closure_value)
    rebuilt = build_reservation(contract, closure, parents)
    if canonical_json_bytes(rebuilt) != canonical_json_bytes(envelope):
        raise EvidenceIntegrityError("reservation cross-artifact relations do not reconstruct")
    return envelope


def _validate_attempt_for_contract(
    contract: StageContract, reservation: Any, attempt: Any
) -> Dict[str, Any]:
    reservation_value = _validate_reservation_for_contract(contract, reservation)
    envelope = _validate_identity_artifact(
        contract,
        attempt,
        "stage_attempt_id",
        "ATLAS_STAGE_ATTEMPT_V1",
    )
    rebuilt = build_attempt(contract, reservation_value)
    if canonical_json_bytes(rebuilt) != canonical_json_bytes(envelope):
        raise EvidenceIntegrityError("attempt cross-artifact relations do not reconstruct")
    return envelope


def build_completed(
    contract: StageContract,
    reservation: Any,
    attempt: Any,
    result: Any,
) -> Dict[str, Any]:
    reservation_value = _validate_reservation_for_contract(contract, reservation)
    attempt_value = _validate_attempt_for_contract(contract, reservation_value, attempt)
    body = {
        "artifact_type": "ATLAS_STAGE_COMPLETED_V1",
        "attempt_id": attempt_value["identity"],
        "reservation_id": reservation_value["identity"],
        "result": result,
        "stage_id": contract.stage_id,
        "stage_protocol_id": contract.stage_protocol_id,
    }
    canonical_json_bytes(body)
    return body


def _requires_full_partial_ledger(contract: StageContract) -> bool:
    return contract.stage_id in (
        "EXACT_ALL_288",
        "RANDOM_ALL_18432_GAMES",
        "TERMINAL_DEPTH1_ALL_18432_GAMES",
        "REPLAY_TELEMETRY_COMPLETE_TRACES_ONLY",
    )


def build_failure(
    contract: StageContract,
    reservation: Any,
    attempt: Any,
    failure: Any,
    partial_evidence: Optional[Any],
) -> Dict[str, Any]:
    reservation_value = _validate_reservation_for_contract(contract, reservation)
    attempt_value = _validate_attempt_for_contract(contract, reservation_value, attempt)
    if partial_evidence is None:
        partial_root = None
        if _requires_full_partial_ledger(contract):
            raise EvidenceIntegrityError("stage failure requires a reconciled full status ledger")
    else:
        partial_root = canonical_body_ref(partial_evidence).sha256
    body = {
        "artifact_type": "ATLAS_STAGE_FAILURE_V1",
        "attempt_id": attempt_value["identity"],
        "failure": failure,
        "partial_evidence_root_or_null": partial_root,
        "reservation_id": reservation_value["identity"],
        "stage_id": contract.stage_id,
        "stage_protocol_id": contract.stage_protocol_id,
    }
    canonical_json_bytes(body)
    return body


def build_orphaned(
    contract: StageContract,
    reservation: Any,
    attempt: Optional[Any],
    partial_evidence: Optional[Any],
) -> Dict[str, Any]:
    reservation_value = _validate_reservation_for_contract(contract, reservation)
    if attempt is None:
        attempt_value = None
        reason = "RESERVATION_WITHOUT_ATTEMPT"
    else:
        attempt_value = _validate_attempt_for_contract(contract, reservation_value, attempt)
        reason = "ATTEMPT_WITHOUT_TERMINAL_SEAL"
    if partial_evidence is None:
        partial_root = None
        if _requires_full_partial_ledger(contract):
            raise EvidenceIntegrityError("orphan recovery requires a reconciled full status ledger")
    else:
        partial_root = canonical_body_ref(partial_evidence).sha256
    payload = {
        "attempt_id_or_null": None if attempt_value is None else attempt_value["identity"],
        "orphan_reason": reason,
        "partial_evidence_root_or_null": partial_root,
        "reservation_id": reservation_value["identity"],
        "stage_id": contract.stage_id,
        "stage_protocol_id": contract.stage_protocol_id,
    }
    references = {
        "partial_evidence": partial_evidence,
        "stage_attempt": attempt_value,
        "stage_reservation": reservation_value,
    }
    return _make_identity_artifact(
        contract,
        "stage_orphaned_id",
        "ATLAS_STAGE_ORPHANED_V1",
        payload,
        references,
    )


def build_terminal_seal(
    contract: StageContract,
    lifecycle: str,
    *,
    blocked: Optional[Any] = None,
    reservation: Optional[Any] = None,
    attempt: Optional[Any] = None,
    failure: Optional[Any] = None,
    completed: Optional[Any] = None,
    orphaned: Optional[Any] = None,
    partial_evidence: Optional[Any] = None,
) -> Dict[str, Any]:
    lifecycle = _exact_string(lifecycle, "terminal lifecycle")
    blocked_value = None
    reservation_value = None
    attempt_value = None
    orphaned_value = None
    completed_root = None
    failure_root = None
    partial_root = None
    if lifecycle == "BLOCKED":
        if any(item is not None for item in (reservation, attempt, failure, completed, orphaned, partial_evidence)):
            raise EvidenceIntegrityError("BLOCKED terminal has incompatible artifacts")
        blocked_value = _validate_identity_artifact(
            contract, blocked, "stage_blocked_id", "ATLAS_STAGE_BLOCKED_V1"
        )
        if blocked_value["payload"].get("stage_id") != contract.stage_id:
            raise EvidenceIntegrityError("blocked artifact belongs to another stage")
    elif lifecycle in ("FAILED", "COMPLETED", "ORPHANED"):
        if blocked is not None:
            raise EvidenceIntegrityError("reserved terminal cannot reference BLOCKED")
        reservation_value = _validate_reservation_for_contract(contract, reservation)
        if attempt is not None:
            attempt_value = _validate_attempt_for_contract(
                contract, reservation_value, attempt
            )
        if lifecycle in ("FAILED", "COMPLETED") and attempt_value is None:
            raise EvidenceIntegrityError("FAILED/COMPLETED terminal requires an attempt")
        if lifecycle == "COMPLETED":
            if any(item is not None for item in (failure, orphaned, partial_evidence)):
                raise EvidenceIntegrityError("COMPLETED terminal has incompatible artifacts")
            body = _exact_keys(
                completed,
                (
                    "artifact_type",
                    "attempt_id",
                    "reservation_id",
                    "result",
                    "stage_id",
                    "stage_protocol_id",
                ),
                "completed artifact",
            )
            expected = build_completed(contract, reservation_value, attempt_value, body["result"])
            if canonical_json_bytes(expected) != canonical_json_bytes(body):
                raise EvidenceIntegrityError("completed artifact cross-references are invalid")
            completed_root = canonical_body_ref(body).sha256
        elif lifecycle == "FAILED":
            if any(item is not None for item in (completed, orphaned)):
                raise EvidenceIntegrityError("FAILED terminal has incompatible artifacts")
            body = _exact_keys(
                failure,
                (
                    "artifact_type",
                    "attempt_id",
                    "failure",
                    "partial_evidence_root_or_null",
                    "reservation_id",
                    "stage_id",
                    "stage_protocol_id",
                ),
                "failure artifact",
            )
            expected = build_failure(
                contract,
                reservation_value,
                attempt_value,
                body["failure"],
                partial_evidence,
            )
            if canonical_json_bytes(expected) != canonical_json_bytes(body):
                raise EvidenceIntegrityError("failure artifact cross-references are invalid")
            failure_root = canonical_body_ref(body).sha256
            partial_root = body["partial_evidence_root_or_null"]
        else:
            if any(item is not None for item in (failure, completed)):
                raise EvidenceIntegrityError("ORPHANED terminal has incompatible artifacts")
            orphaned_value = _validate_identity_artifact(
                contract,
                orphaned,
                "stage_orphaned_id",
                "ATLAS_STAGE_ORPHANED_V1",
            )
            expected = build_orphaned(
                contract, reservation_value, attempt_value, partial_evidence
            )
            if canonical_json_bytes(expected) != canonical_json_bytes(orphaned_value):
                raise EvidenceIntegrityError("orphaned artifact cross-references are invalid")
            partial_root = orphaned_value["payload"]["partial_evidence_root_or_null"]
    else:
        raise ValueError("unknown terminal lifecycle")
    payload = {
        "attempt_id_or_null": None if attempt_value is None else attempt_value["identity"],
        "blocked_id_or_null": None if blocked_value is None else blocked_value["identity"],
        "completed_root_or_null": completed_root,
        "failure_root_or_null": failure_root,
        "lifecycle": lifecycle,
        "orphaned_id_or_null": None if orphaned_value is None else orphaned_value["identity"],
        "partial_evidence_root_or_null": partial_root,
        "reservation_id_or_null": (
            None if reservation_value is None else reservation_value["identity"]
        ),
        "stage_id": contract.stage_id,
        "stage_protocol_id": contract.stage_protocol_id,
    }
    return _make_identity_artifact(
        contract,
        "stage_terminal_seal",
        "ATLAS_STAGE_TERMINAL_SEAL_V1",
        payload,
        {
            "blocked": blocked_value,
            "completed": completed,
            "failure": failure,
            "orphaned": orphaned_value,
            "partial_evidence": partial_evidence,
            "stage_attempt": attempt_value,
            "stage_reservation": reservation_value,
        },
    )


@dataclass(frozen=True)
class ChainSnapshot:
    production_closure: Optional[ProductionClosure] = None
    reservation: Optional[Dict[str, Any]] = None
    attempt: Optional[Dict[str, Any]] = None
    blocked: Optional[Dict[str, Any]] = None
    partial_evidence: Optional[Any] = None
    failure: Optional[Dict[str, Any]] = None
    completed: Optional[Dict[str, Any]] = None
    orphaned: Optional[Dict[str, Any]] = None
    terminal_seal: Optional[Dict[str, Any]] = None


def _compare_built(expected: Any, observed: Any, label: str) -> None:
    if canonical_json_bytes(expected) != canonical_json_bytes(observed):
        raise EvidenceIntegrityError("{} does not reconstruct".format(label))


def validate_chain_snapshot(contract: StageContract, snapshot: ChainSnapshot) -> str:
    """Validate shape, identities, exclusivity, and every same-chain reference."""

    if not isinstance(snapshot, ChainSnapshot):
        raise TypeError("snapshot must be a ChainSnapshot")
    if snapshot.blocked is not None:
        if any(
            item is not None
            for item in (
                snapshot.reservation,
                snapshot.attempt,
                snapshot.failure,
                snapshot.completed,
                snapshot.orphaned,
                snapshot.partial_evidence,
            )
        ):
            raise EvidenceIntegrityError("BLOCKED chain conflicts with reserved evidence")
        blocked = _validate_identity_artifact(
            contract,
            snapshot.blocked,
            "stage_blocked_id",
            "ATLAS_STAGE_BLOCKED_V1",
        )
        references = blocked["references"]
        closure = _validate_closure(contract, references.get("production_closure"))
        parents = references.get("ordered_parent_terminal_seals")
        if type(parents) is not list:
            raise EvidenceIntegrityError("blocked parent references are absent")
        _compare_built(
            build_blocked(contract, closure, parents), blocked, "blocked artifact"
        )
        if snapshot.production_closure is not None:
            _compare_built(
                snapshot.production_closure.as_dict(), closure.as_dict(), "blocked closure"
            )
        if snapshot.terminal_seal is None:
            return "BLOCKED_UNSEALED"
        expected_terminal = build_terminal_seal(contract, "BLOCKED", blocked=blocked)
        _compare_built(expected_terminal, snapshot.terminal_seal, "BLOCKED terminal seal")
        return "BLOCKED"
    if snapshot.reservation is None:
        if any(
            item is not None
            for item in (
                snapshot.attempt,
                snapshot.failure,
                snapshot.completed,
                snapshot.orphaned,
                snapshot.partial_evidence,
                snapshot.terminal_seal,
            )
        ):
            raise EvidenceIntegrityError("stage evidence exists without a reservation")
        return "EMPTY"
    reservation = _validate_reservation_for_contract(contract, snapshot.reservation)
    closure = _validate_closure(
        contract, reservation["references"]["production_closure"]
    )
    if snapshot.production_closure is not None:
        _compare_built(snapshot.production_closure.as_dict(), closure.as_dict(), "reserved closure")
    if snapshot.attempt is None:
        if any(
            item is not None
            for item in (snapshot.failure, snapshot.completed, snapshot.orphaned)
        ):
            if snapshot.orphaned is None:
                raise EvidenceIntegrityError("lifecycle body requires an attempt")
        if snapshot.orphaned is None:
            if snapshot.terminal_seal is not None:
                raise EvidenceIntegrityError("reservation-only chain cannot have a terminal seal")
            return "RESERVED"
        orphaned_expected = build_orphaned(
            contract, reservation, None, snapshot.partial_evidence
        )
        _compare_built(orphaned_expected, snapshot.orphaned, "orphaned artifact")
        lifecycle = "ORPHANED"
        terminal_expected = build_terminal_seal(
            contract,
            lifecycle,
            reservation=reservation,
            orphaned=snapshot.orphaned,
            partial_evidence=snapshot.partial_evidence,
        )
    else:
        attempt = _validate_attempt_for_contract(contract, reservation, snapshot.attempt)
        bodies = [
            snapshot.failure is not None,
            snapshot.completed is not None,
            snapshot.orphaned is not None,
        ]
        if sum(bodies) > 1:
            raise EvidenceIntegrityError("stage chain has conflicting lifecycle bodies")
        if not any(bodies):
            if snapshot.terminal_seal is not None:
                raise EvidenceIntegrityError("attempt-only chain cannot have a terminal seal")
            return "ATTEMPTED"
        if snapshot.failure is not None:
            body = _exact_mapping(snapshot.failure, "failure artifact")
            expected = build_failure(
                contract,
                reservation,
                attempt,
                body.get("failure"),
                snapshot.partial_evidence,
            )
            _compare_built(expected, body, "failure artifact")
            lifecycle = "FAILED"
            terminal_expected = build_terminal_seal(
                contract,
                lifecycle,
                reservation=reservation,
                attempt=attempt,
                failure=body,
                partial_evidence=snapshot.partial_evidence,
            )
        elif snapshot.completed is not None:
            body = _exact_mapping(snapshot.completed, "completed artifact")
            expected = build_completed(
                contract, reservation, attempt, body.get("result")
            )
            _compare_built(expected, body, "completed artifact")
            lifecycle = "COMPLETED"
            terminal_expected = build_terminal_seal(
                contract,
                lifecycle,
                reservation=reservation,
                attempt=attempt,
                completed=body,
            )
        else:
            expected = build_orphaned(
                contract, reservation, attempt, snapshot.partial_evidence
            )
            _compare_built(expected, snapshot.orphaned, "orphaned artifact")
            lifecycle = "ORPHANED"
            terminal_expected = build_terminal_seal(
                contract,
                lifecycle,
                reservation=reservation,
                attempt=attempt,
                orphaned=snapshot.orphaned,
                partial_evidence=snapshot.partial_evidence,
            )
    if snapshot.terminal_seal is None:
        return lifecycle + "_UNSEALED"
    _compare_built(terminal_expected, snapshot.terminal_seal, "terminal seal")
    return lifecycle


@dataclass(frozen=True)
class LedgerSpec:
    """A fixed, candidate-neutral index schedule for an immutable slot journal."""

    phase_id: str
    ordered_slot_ids: Tuple[str, ...]
    allowed_result_statuses: Tuple[str, ...]
    interrupted_status: str
    unobserved_status: str
    blocked_status: str = "BLOCKED"
    preclassified_statuses: Tuple[Tuple[int, str], ...] = ()

    def __post_init__(self) -> None:
        _safe_component(self.phase_id, "ledger phase id")
        if type(self.ordered_slot_ids) is not tuple or not self.ordered_slot_ids:
            raise ValueError("ledger slots must be a nonempty exact tuple")
        for slot_id in self.ordered_slot_ids:
            _exact_string(slot_id, "ledger slot id")
        if len(set(self.ordered_slot_ids)) != len(self.ordered_slot_ids):
            raise ValueError("ledger slot ids contain duplicates")
        if type(self.allowed_result_statuses) is not tuple or not self.allowed_result_statuses:
            raise ValueError("allowed result statuses must be a nonempty exact tuple")
        for status_value in self.allowed_result_statuses:
            _safe_component(status_value, "ledger result status")
        if len(set(self.allowed_result_statuses)) != len(self.allowed_result_statuses):
            raise ValueError("allowed result statuses contain duplicates")
        for status_value in (
            self.interrupted_status,
            self.unobserved_status,
            self.blocked_status,
        ):
            _safe_component(status_value, "ledger status")
        if type(self.preclassified_statuses) is not tuple:
            raise ValueError("preclassified statuses must be an exact tuple")
        indexes = []
        for item in self.preclassified_statuses:
            if type(item) is not tuple or len(item) != 2:
                raise ValueError("preclassified status must be an index/status pair")
            index, status_value = item
            if type(index) is not int or not 0 <= index < len(self.ordered_slot_ids):
                raise ValueError("preclassified ledger index is outside the schedule")
            _safe_component(status_value, "preclassified ledger status")
            indexes.append(index)
        if len(set(indexes)) != len(indexes):
            raise ValueError("preclassified ledger indexes contain duplicates")


@dataclass(frozen=True)
class _FrozenLedgerSchedule:
    exact_ids: Tuple[str, ...]
    pv_ids: Tuple[str, ...]
    random_ids: Tuple[str, ...]
    depth1_ids: Tuple[str, ...]
    telemetry_ids: Tuple[str, ...]


def _frozen_ledger_schedule_from_canonical_protocol(
    protocol_raw: bytes,
) -> _FrozenLedgerSchedule:
    """Rebuild the candidate-neutral fixed schedules from authenticated protocol bytes."""

    protocol = _authenticate_protocol(load_canonical_json_bytes(protocol_raw))
    exact_ids = tuple(
        _exact_hex(value.get("slot_id"), 64, "exact schedule slot id")
        for value in atlas_protocol.iter_frozen_atlas_exact_schedule_from_protocol_v1(
            protocol
        )
    )
    pv_ids = tuple(
        _exact_hex(value.get("slot_id"), 64, "PV schedule slot id")
        for value in atlas_protocol.iter_frozen_atlas_orientation_schedule_from_protocol_v1(
            protocol
        )
    )
    games = tuple(
        atlas_protocol.iter_frozen_atlas_game_schedule_from_protocol_v1(protocol)
    )
    telemetry_ids = tuple(
        _exact_hex(value.get("slot_id"), 64, "telemetry schedule slot id")
        for value in games
    )
    random_ids = tuple(
        _exact_hex(value.get("slot_id"), 64, "random schedule slot id")
        for value in games
        if _exact_mapping(value.get("strength"), "game strength").get("identity")
        == _RANDOM_STRENGTH_ID
    )
    depth1_ids = tuple(
        _exact_hex(value.get("slot_id"), 64, "depth-1 schedule slot id")
        for value in games
        if _exact_mapping(value.get("strength"), "game strength").get("identity")
        == _DEPTH1_STRENGTH_ID
    )
    expected_counts = (
        (exact_ids, 288, "exact"),
        (pv_ids, 2_304, "PV"),
        (random_ids, 18_432, "random"),
        (depth1_ids, 18_432, "depth-1"),
        (telemetry_ids, 36_864, "telemetry"),
    )
    for values, count, label in expected_counts:
        if len(values) != count or len(set(values)) != count:
            raise EvidenceIntegrityError(
                "{} frozen ledger schedule cardinality drifted".format(label)
            )
    if set(random_ids).intersection(depth1_ids) or set(telemetry_ids) != set(
        random_ids + depth1_ids
    ):
        raise EvidenceIntegrityError("sampled frozen ledger schedules do not partition")
    return _FrozenLedgerSchedule(
        exact_ids=exact_ids,
        pv_ids=pv_ids,
        random_ids=random_ids,
        depth1_ids=depth1_ids,
        telemetry_ids=telemetry_ids,
    )


def _frozen_ledger_schedule(protocol_value: Any) -> _FrozenLedgerSchedule:
    protocol = _authenticate_protocol(protocol_value)
    # Do not memoize this boundary.  Each call must traverse the protocol's
    # public protocol-only iterators so their sealed context is revalidated.
    return _frozen_ledger_schedule_from_canonical_protocol(
        canonical_json_bytes(protocol)
    )


def _base_frozen_ledger_specs(
    contract: StageContract, schedule: _FrozenLedgerSchedule
) -> Tuple[LedgerSpec, ...]:
    if contract.stage_id == _EXACT_STAGE_ID:
        return (
            LedgerSpec(
                "exact",
                schedule.exact_ids,
                ("COMPLETE", "INVALID", "PROOF_CONTRADICTION"),
                "INCOMPLETE",
                "NOT_RUN",
            ),
            LedgerSpec(
                "exact-pv",
                schedule.pv_ids,
                ("VALID", "INVALID", "PROOF_CONTRADICTION"),
                "INCOMPLETE",
                "NOT_RUN",
            ),
        )
    if contract.stage_id == _RANDOM_STAGE_ID:
        return (
            LedgerSpec(
                "random",
                schedule.random_ids,
                ("COMPLETE", "INCOMPLETE", "INVALID", "PROOF_CONTRADICTION"),
                "INCOMPLETE",
                "NOT_RUN",
            ),
        )
    if contract.stage_id == _DEPTH1_STAGE_ID:
        return (
            LedgerSpec(
                "depth1",
                schedule.depth1_ids,
                ("COMPLETE", "INCOMPLETE", "INVALID", "PROOF_CONTRADICTION"),
                "INCOMPLETE",
                "NOT_RUN",
            ),
        )
    raise EvidenceIntegrityError("stage has no fixed base ledger schedule")


def _try_read_journal(
    store: ImmutableEvidenceStore,
    stage_protocol_id: str,
    phase_id: str,
    kind: str,
    slot_index: int,
) -> Optional[Any]:
    try:
        if kind == "start":
            return store.read_journal_start(stage_protocol_id, phase_id, slot_index)
        return store.read_journal_result(stage_protocol_id, phase_id, slot_index)
    except FileNotFoundError:
        return None
    except EvidenceIntegrityError as error:
        if isinstance(error.__cause__, FileNotFoundError):
            return None
        raise


def _validate_body_ref(value: Any, expected: BodyRef, label: str) -> None:
    reference = _exact_keys(value, ("byte_count", "sha256"), label)
    if type(reference["byte_count"]) is not int or reference["byte_count"] < 0:
        raise EvidenceIntegrityError("{} byte count is invalid".format(label))
    _exact_hex(reference["sha256"], 64, "{} SHA-256".format(label))
    if reference != expected.as_dict():
        raise EvidenceIntegrityError("{} does not authenticate its body".format(label))


def reconcile_status_ledger(
    store: ImmutableEvidenceStore,
    contract: StageContract,
    spec: LedgerSpec,
    *,
    blocked: bool = False,
) -> Dict[str, Any]:
    """Reconstruct every fixed status from immutable start/result records only."""

    if not isinstance(store, ImmutableEvidenceStore):
        raise TypeError("store must be an ImmutableEvidenceStore")
    if not isinstance(spec, LedgerSpec):
        raise TypeError("spec must be a LedgerSpec")
    preclassified = dict(spec.preclassified_statuses)
    records = []
    counts: Dict[str, int] = {}
    for index, slot_id in enumerate(spec.ordered_slot_ids):
        start = _try_read_journal(
            store, contract.stage_protocol_id, spec.phase_id, "start", index
        )
        result = _try_read_journal(
            store, contract.stage_protocol_id, spec.phase_id, "result", index
        )
        start_ref = None
        result_ref = None
        if start is not None:
            expected_start = {
                "artifact_type": "ATLAS_SLOT_START_V1",
                "phase_id": spec.phase_id,
                "slot_id": slot_id,
                "slot_index": index,
                "stage_protocol_id": contract.stage_protocol_id,
            }
            _compare_built(expected_start, start, "journal start")
            start_ref = canonical_body_ref(start)
        if result is not None:
            if start is None:
                raise EvidenceIntegrityError("journal result exists without a start")
            result_value = _exact_keys(
                result,
                (
                    "artifact_type",
                    "phase_id",
                    "result",
                    "slot_id",
                    "slot_index",
                    "stage_protocol_id",
                    "start_ref",
                    "status",
                ),
                "journal result",
            )
            if (
                result_value["artifact_type"] != "ATLAS_SLOT_RESULT_V1"
                or result_value["phase_id"] != spec.phase_id
                or result_value["slot_id"] != slot_id
                or result_value["slot_index"] != index
                or result_value["stage_protocol_id"] != contract.stage_protocol_id
            ):
                raise EvidenceIntegrityError("journal result coordinates are invalid")
            _validate_body_ref(result_value["start_ref"], start_ref, "journal start ref")
            status_value = _exact_string(result_value["status"], "journal result status")
            if status_value not in spec.allowed_result_statuses:
                raise EvidenceIntegrityError("journal result status is not allowed")
            result_ref = canonical_body_ref(result_value)
        if blocked:
            if start is not None or result is not None:
                raise EvidenceIntegrityError("BLOCKED ledger cannot retain slot execution evidence")
            status = spec.blocked_status
        elif index in preclassified:
            if start is not None or result is not None:
                raise EvidenceIntegrityError("preclassified slot cannot have journal evidence")
            status = preclassified[index]
        elif result is not None:
            status = result["status"]
        elif start is not None:
            status = spec.interrupted_status
        else:
            status = spec.unobserved_status
        counts[status] = counts.get(status, 0) + 1
        records.append(
            {
                "result_ref_or_null": None if result_ref is None else result_ref.as_dict(),
                "slot_id": slot_id,
                "slot_index": index,
                "start_ref_or_null": None if start_ref is None else start_ref.as_dict(),
                "status": status,
            }
        )
    ledger = {
        "artifact_type": "ATLAS_FULL_STATUS_LEDGER_V1",
        "phase_id": spec.phase_id,
        "slot_count": len(spec.ordered_slot_ids),
        "slots": records,
        "stage_id": contract.stage_id,
        "stage_protocol_id": contract.stage_protocol_id,
        "status_counts": counts,
    }
    canonical_json_bytes(ledger)
    return ledger


def _reconcile_ledger_set(
    store: ImmutableEvidenceStore,
    contract: StageContract,
    ledger_specs: Sequence[LedgerSpec],
    *,
    blocked: bool = False,
) -> Optional[Dict[str, Any]]:
    if type(ledger_specs) not in (list, tuple):
        raise TypeError("ledger specs must be an exact sequence")
    if not ledger_specs:
        if _requires_full_partial_ledger(contract):
            raise EvidenceIntegrityError("stage requires at least one fixed ledger spec")
        return None
    phases = tuple(spec.phase_id for spec in ledger_specs)
    if len(set(phases)) != len(phases):
        raise EvidenceIntegrityError("ledger phase ids contain duplicates")
    ledgers = [
        reconcile_status_ledger(store, contract, spec, blocked=blocked)
        for spec in ledger_specs
    ]
    result = {
        "artifact_type": "ATLAS_FULL_STATUS_LEDGER_SET_V1",
        "ledgers": ledgers,
        "phase_ids": list(phases),
        "stage_id": contract.stage_id,
        "stage_protocol_id": contract.stage_protocol_id,
    }
    canonical_json_bytes(result)
    return result


def _ledger_set_has_journal_evidence(ledger_set: Mapping[str, Any]) -> bool:
    return any(
        slot["start_ref_or_null"] is not None
        or slot["result_ref_or_null"] is not None
        for ledger in ledger_set["ledgers"]
        for slot in ledger["slots"]
    )


def publish_stage_completion_evidence(
    store: ImmutableEvidenceStore,
    contract: StageContract,
    ledger_specs: Sequence[LedgerSpec],
) -> StageResultRefs:
    """Freeze the authoritative all-slot ledger and ordered raw-result catalog."""

    store._require_stage_lock(contract.stage_protocol_id)
    reservation = store.read_json(contract.stage_protocol_id, "reservation")
    attempt = store.read_json(contract.stage_protocol_id, "attempt")
    if validate_chain_snapshot(
        contract, ChainSnapshot(reservation=reservation, attempt=attempt)
    ) != "ATTEMPTED":
        raise EvidenceIntegrityError("completion evidence requires one attempted chain")
    store.scan_fixed_catalog(contract.stage_protocol_id, ledger_specs)
    ledger_set = _reconcile_ledger_set(store, contract, ledger_specs)
    if ledger_set is None:
        raise EvidenceIntegrityError("stage completion evidence requires fixed ledgers")
    ordered_records = []
    for ledger in ledger_set["ledgers"]:
        for slot in ledger["slots"]:
            if slot["result_ref_or_null"] is not None:
                ordered_records.append(
                    {
                        "phase_id": ledger["phase_id"],
                        "result_ref": slot["result_ref_or_null"],
                        "slot_id": slot["slot_id"],
                        "slot_index": slot["slot_index"],
                    }
                )
    ordered_root = hashlib.sha256(canonical_json_bytes(ordered_records)).hexdigest()
    record_catalog = {
        "artifact_type": "ATLAS_RESULT_RECORD_CATALOG_V1",
        "ordered_record_count": len(ordered_records),
        "ordered_record_root": ordered_root,
        "ordered_records": ordered_records,
        "stage_id": contract.stage_id,
        "stage_protocol_id": contract.stage_protocol_id,
    }
    canonical_json_bytes(record_catalog)
    ledger_ref = store.publish_json(
        contract.stage_protocol_id, "status_ledger", ledger_set
    )
    catalog_ref = store.publish_json(
        contract.stage_protocol_id, "record_catalog", record_catalog
    )
    return StageResultRefs(status_ledger=ledger_ref, record_catalog=catalog_ref)


def read_stage_completion_evidence(
    store: ImmutableEvidenceStore,
    contract: StageContract,
    expected_refs: Optional[StageResultRefs] = None,
) -> Dict[str, Any]:
    ledger_raw = store.read_bytes(contract.stage_protocol_id, "status_ledger")
    catalog_raw = store.read_bytes(contract.stage_protocol_id, "record_catalog")
    ledger = load_canonical_json_bytes(ledger_raw)
    catalog = load_canonical_json_bytes(catalog_raw)
    _exact_keys(
        ledger,
        ("artifact_type", "ledgers", "phase_ids", "stage_id", "stage_protocol_id"),
        "status ledger set",
    )
    if (
        ledger["artifact_type"] != "ATLAS_FULL_STATUS_LEDGER_SET_V1"
        or ledger["stage_id"] != contract.stage_id
        or ledger["stage_protocol_id"] != contract.stage_protocol_id
    ):
        raise EvidenceIntegrityError("status ledger belongs to another stage")
    catalog_value = _exact_keys(
        catalog,
        (
            "artifact_type",
            "ordered_record_count",
            "ordered_record_root",
            "ordered_records",
            "stage_id",
            "stage_protocol_id",
        ),
        "record catalog",
    )
    if (
        catalog_value["artifact_type"] != "ATLAS_RESULT_RECORD_CATALOG_V1"
        or catalog_value["stage_id"] != contract.stage_id
        or catalog_value["stage_protocol_id"] != contract.stage_protocol_id
        or type(catalog_value["ordered_records"]) is not list
        or type(catalog_value["ordered_record_count"]) is not int
        or catalog_value["ordered_record_count"] != len(catalog_value["ordered_records"])
        or _exact_hex(
            catalog_value["ordered_record_root"], 64, "ordered record root"
        )
        != hashlib.sha256(
            canonical_json_bytes(catalog_value["ordered_records"])
        ).hexdigest()
    ):
        raise EvidenceIntegrityError("record catalog does not reconstruct")
    expected_records = []
    ledgers = ledger.get("ledgers")
    if type(ledgers) is not list:
        raise EvidenceIntegrityError("status ledger set ledgers are invalid")
    for phase in ledgers:
        phase_value = _exact_mapping(phase, "status ledger phase")
        slots = phase_value.get("slots")
        if type(slots) is not list:
            raise EvidenceIntegrityError("status ledger phase slots are invalid")
        for slot in slots:
            slot_value = _exact_mapping(slot, "status ledger slot")
            result_ref = slot_value.get("result_ref_or_null")
            if result_ref is not None:
                expected_records.append(
                    {
                        "phase_id": phase_value.get("phase_id"),
                        "result_ref": result_ref,
                        "slot_id": slot_value.get("slot_id"),
                        "slot_index": slot_value.get("slot_index"),
                    }
                )
    if catalog_value["ordered_records"] != expected_records:
        raise EvidenceIntegrityError(
            "record catalog differs from the authenticated status ledgers"
        )
    refs = StageResultRefs(
        status_ledger=BodyRef(hashlib.sha256(ledger_raw).hexdigest(), len(ledger_raw)),
        record_catalog=BodyRef(hashlib.sha256(catalog_raw).hexdigest(), len(catalog_raw)),
    )
    if expected_refs is not None and refs != expected_refs:
        raise EvidenceIntegrityError("stage completion evidence refs differ from completed body")
    return {"record_catalog": catalog, "status_ledger": ledger, "refs": refs}


def _validate_closure_set(
    protocol_value: Any,
    manifest_contract: StageContract,
    closures_value: Any,
    experiment_plan_bytes: bytes,
) -> Tuple[ProductionClosure, ...]:
    body = _exact_keys(
        closures_value,
        ("artifact_type", "ordered_closures"),
        "production closure set",
    )
    if body["artifact_type"] != "ATLAS_PRODUCTION_CLOSURE_SET_V1":
        raise EvidenceIntegrityError("production closure set type is invalid")
    values = body["ordered_closures"]
    if type(values) is not list or len(values) != 6:
        raise EvidenceIntegrityError("production closure set must contain all six stages")
    protocol = _authenticate_protocol(protocol_value)
    stage_ids = tuple(protocol["stage_sequence"])
    contracts = tuple(extract_stage_contract(protocol, stage_id) for stage_id in stage_ids)
    closures = tuple(
        _validate_closure(contract, value)
        for contract, value in zip(contracts, values)
    )
    if tuple(item.payload["stage_id"] for item in closures) != stage_ids:
        raise EvidenceIntegrityError("production closure set stage order is invalid")
    plan_sha = hashlib.sha256(experiment_plan_bytes).hexdigest()
    source_commits = {item.payload["source_commit"] for item in closures}
    source_trees = {item.payload["source_tree"] for item in closures}
    plan_shas = {item.payload["manifest_experiment_plan_sha256"] for item in closures}
    protocol_blobs = {item.payload["manifest_protocol_blob_identity"] for item in closures}
    if len(source_commits) != 1 or len(source_trees) != 1:
        raise EvidenceIntegrityError("all stage closures must bind one source commit and tree")
    if plan_shas != {plan_sha}:
        raise EvidenceIntegrityError("closure set does not bind the frozen experiment plan")
    if len(protocol_blobs) != 1:
        raise EvidenceIntegrityError("closure set protocol blobs differ across stages")
    overlapping: Dict[str, bytes] = {}
    for closure in closures:
        for record in closure.payload["ordered_file_records"]:
            path = record["path"]
            encoded = canonical_json_bytes(record)
            if path in overlapping and overlapping[path] != encoded:
                raise EvidenceIntegrityError("overlapping closure blobs differ across stages")
            overlapping[path] = encoded
    manifest_closure = closures[manifest_contract.stage_index]
    if manifest_closure.payload["stage_id"] != manifest_contract.stage_id:
        raise EvidenceIntegrityError("manifest closure is not at its frozen stage index")
    return closures


def publish_manifest_bootstrap(
    store: ImmutableEvidenceStore,
    manifest_contract: StageContract,
    protocol_value: Any,
    production_closures: Sequence[ProductionClosure],
    experiment_plan_bytes: bytes,
) -> ManifestBootstrapRefs:
    """Freeze candidate-neutral execution inputs before manifest reservation.

    This pre-stage operation is idempotent because it grants no definition or
    outcome capability.  A crash may leave a prefix of identical immutable
    files; the next preflight verifies and completes that prefix before any
    one-shot reservation is created.
    """

    if manifest_contract.stage_id != "OUTCOME_FREE_DEVELOPMENT_MANIFEST":
        raise EvidenceIntegrityError("bootstrap belongs to the manifest stage")
    store._require_stage_lock(manifest_contract.stage_protocol_id)
    if manifest_contract.stage_protocol_id != _MANIFEST_STAGE_PROTOCOL_ID:
        raise EvidenceIntegrityError("manifest bootstrap stage path drifted")
    protocol = _authenticate_protocol(protocol_value)
    if extract_stage_contract(protocol, manifest_contract.stage_id) != manifest_contract:
        raise EvidenceIntegrityError("bootstrap manifest contract differs from protocol")
    if type(production_closures) not in (list, tuple):
        raise TypeError("production closures must be an exact sequence")
    closure_set = {
        "artifact_type": "ATLAS_PRODUCTION_CLOSURE_SET_V1",
        "ordered_closures": [value.as_dict() for value in production_closures],
    }
    closures = _validate_closure_set(
        protocol, manifest_contract, closure_set, experiment_plan_bytes
    )
    protocol_raw = canonical_json_bytes(protocol)
    closures_raw = canonical_json_bytes(closure_set)
    protocol_ref = store.publish_manifest_bootstrap_bytes(
        "protocol", protocol_raw
    )
    closures_ref = store.publish_manifest_bootstrap_bytes(
        "production_closures", closures_raw
    )
    plan_ref = store.publish_manifest_bootstrap_bytes(
        "experiment_plan", experiment_plan_bytes
    )
    first = closures[0]
    unsigned = {
        "artifact_type": "ATLAS_MANIFEST_BOOTSTRAP_V1",
        "evidence_protocol_id": manifest_contract.evidence_protocol_id,
        "experiment_plan_ref": plan_ref.as_dict(),
        "production_closure_count": len(closures),
        "production_closures_ref": closures_ref.as_dict(),
        "protocol_id": manifest_contract.protocol_id,
        "protocol_ref": protocol_ref.as_dict(),
        "protocol_root": manifest_contract.protocol_root,
        "source_commit": first.payload["source_commit"],
        "source_tree": first.payload["source_tree"],
    }
    catalog = {
        **unsigned,
        "bootstrap_root": domain_identity(
            _MANIFEST_BOOTSTRAP_ROOT_DOMAIN, unsigned
        ),
    }
    catalog_ref = store.publish_manifest_bootstrap_bytes(
        "catalog", canonical_json_bytes(catalog)
    )
    refs = ManifestBootstrapRefs(
        protocol=protocol_ref,
        production_closures=closures_ref,
        experiment_plan=plan_ref,
        catalog=catalog_ref,
    )
    observed = read_manifest_bootstrap(store, manifest_contract)
    if observed["refs"] != refs:
        raise EvidenceIntegrityError("manifest bootstrap refs did not reseal")
    return refs


def read_manifest_bootstrap(
    store: ImmutableEvidenceStore,
    manifest_contract: Optional[StageContract] = None,
) -> Dict[str, Any]:
    """Read and authenticate the pre-reservation candidate-neutral bootstrap."""

    protocol_raw = store.read_manifest_bootstrap_bytes("protocol")
    closures_raw = store.read_manifest_bootstrap_bytes("production_closures")
    plan_raw = store.read_manifest_bootstrap_bytes("experiment_plan")
    catalog_raw = store.read_manifest_bootstrap_bytes("catalog")
    protocol = _authenticate_protocol(load_canonical_json_bytes(protocol_raw))
    contract = extract_stage_contract(
        protocol, "OUTCOME_FREE_DEVELOPMENT_MANIFEST"
    )
    if manifest_contract is not None and contract != manifest_contract:
        raise EvidenceIntegrityError("bootstrap contract differs from caller contract")
    closure_set = load_canonical_json_bytes(closures_raw)
    closures = _validate_closure_set(protocol, contract, closure_set, plan_raw)
    catalog = _exact_keys(
        load_canonical_json_bytes(catalog_raw),
        (
            "artifact_type",
            "bootstrap_root",
            "evidence_protocol_id",
            "experiment_plan_ref",
            "production_closure_count",
            "production_closures_ref",
            "protocol_id",
            "protocol_ref",
            "protocol_root",
            "source_commit",
            "source_tree",
        ),
        "manifest bootstrap catalog",
    )
    unsigned = dict(catalog)
    bootstrap_root = unsigned.pop("bootstrap_root")
    provenance = _exact_mapping(
        protocol.get("manifest_and_run_provenance"),
        "manifest bootstrap evidence protocol",
    )
    bootstrap_protocol = _exact_mapping(
        provenance.get("outcome_free_manifest_bootstrap"),
        "manifest bootstrap protocol section",
    )
    identity_schema = _exact_keys(
        bootstrap_protocol.get("identity_schema"),
        ("domain_hex", "payload_keys"),
        "manifest bootstrap identity schema",
    )
    if (
        identity_schema["domain_hex"] != _MANIFEST_BOOTSTRAP_ROOT_DOMAIN.hex()
        or identity_schema["payload_keys"] != sorted(unsigned)
    ):
        raise EvidenceIntegrityError("manifest bootstrap identity schema drifted")
    if (
        catalog["artifact_type"] != "ATLAS_MANIFEST_BOOTSTRAP_V1"
        or catalog["evidence_protocol_id"] != contract.evidence_protocol_id
        or catalog["protocol_id"] != contract.protocol_id
        or catalog["protocol_root"] != contract.protocol_root
        or catalog["production_closure_count"] != len(closures)
        or catalog["source_commit"] != closures[0].payload["source_commit"]
        or catalog["source_tree"] != closures[0].payload["source_tree"]
        or bootstrap_root
        != domain_identity(_MANIFEST_BOOTSTRAP_ROOT_DOMAIN, unsigned)
    ):
        raise EvidenceIntegrityError("manifest bootstrap catalog did not reconstruct")
    refs = ManifestBootstrapRefs(
        protocol=BodyRef(hashlib.sha256(protocol_raw).hexdigest(), len(protocol_raw)),
        production_closures=BodyRef(
            hashlib.sha256(closures_raw).hexdigest(), len(closures_raw)
        ),
        experiment_plan=BodyRef(hashlib.sha256(plan_raw).hexdigest(), len(plan_raw)),
        catalog=BodyRef(hashlib.sha256(catalog_raw).hexdigest(), len(catalog_raw)),
    )
    if (
        catalog["protocol_ref"] != refs.protocol.as_dict()
        or catalog["production_closures_ref"]
        != refs.production_closures.as_dict()
        or catalog["experiment_plan_ref"] != refs.experiment_plan.as_dict()
    ):
        raise EvidenceIntegrityError("manifest bootstrap body refs differ")
    scanned = store.scan_manifest_bootstrap()
    if any(scanned[name] != getattr(refs, name) for name in scanned):
        raise EvidenceIntegrityError("manifest bootstrap fixed catalog differs")
    return {
        "catalog": catalog,
        "experiment_plan_bytes": plan_raw,
        "production_closures": closure_set,
        "protocol": protocol,
        "refs": refs,
    }


def publish_manifest_freeze(
    store: ImmutableEvidenceStore,
    manifest_contract: StageContract,
    protocol_value: Any,
    detached_manifest: Any,
    production_closures: Sequence[ProductionClosure],
    experiment_plan_bytes: bytes,
) -> ManifestFreezeRefs:
    """Publish the four fixed manifest artifacts after reservation and attempt."""

    if manifest_contract.stage_id != "OUTCOME_FREE_DEVELOPMENT_MANIFEST":
        raise EvidenceIntegrityError("manifest freeze can only be published by the manifest stage")
    store._require_stage_lock(manifest_contract.stage_protocol_id)
    reservation = store.read_json(manifest_contract.stage_protocol_id, "reservation")
    attempt = store.read_json(manifest_contract.stage_protocol_id, "attempt")
    state = validate_chain_snapshot(
        manifest_contract,
        ChainSnapshot(reservation=reservation, attempt=attempt),
    )
    if state != "ATTEMPTED":
        raise EvidenceIntegrityError("manifest freeze requires one live attempted chain")
    protocol = _authenticate_protocol(protocol_value)
    extracted = extract_stage_contract(protocol, manifest_contract.stage_id)
    if extracted != manifest_contract:
        raise EvidenceIntegrityError("manifest contract differs from the frozen protocol")
    if type(production_closures) not in (list, tuple):
        raise TypeError("production closures must be an exact sequence")
    closure_set = {
        "artifact_type": "ATLAS_PRODUCTION_CLOSURE_SET_V1",
        "ordered_closures": [item.as_dict() for item in production_closures],
    }
    _validate_closure_set(protocol, manifest_contract, closure_set, experiment_plan_bytes)
    bootstrap = read_manifest_bootstrap(store, manifest_contract)
    if (
        canonical_json_bytes(bootstrap["protocol"])
        != canonical_json_bytes(protocol)
        or canonical_json_bytes(bootstrap["production_closures"])
        != canonical_json_bytes(closure_set)
        or bootstrap["experiment_plan_bytes"] != experiment_plan_bytes
    ):
        raise EvidenceIntegrityError(
            "manifest freeze differs from its pre-reservation bootstrap"
        )
    canonical_json_bytes(detached_manifest)
    expected_plan_ref = BodyRef(
        hashlib.sha256(experiment_plan_bytes).hexdigest(), len(experiment_plan_bytes)
    )
    try:
        existing_plan = store.read_bytes(manifest_contract.stage_protocol_id, "experiment_plan")
    except (FileNotFoundError, EvidenceIntegrityError) as error:
        if isinstance(error, EvidenceIntegrityError) and not isinstance(
            error.__cause__, FileNotFoundError
        ):
            raise
        plan_ref = store.publish_bytes(
            manifest_contract.stage_protocol_id, "experiment_plan", experiment_plan_bytes
        )
    else:
        if existing_plan != experiment_plan_bytes:
            raise EvidenceIntegrityError("immutable experiment plan bytes differ")
        plan_ref = expected_plan_ref
    protocol_ref = store.publish_json(
        manifest_contract.stage_protocol_id, "protocol", protocol
    )
    detached_ref = store.publish_json(
        manifest_contract.stage_protocol_id, "detached_manifest", detached_manifest
    )
    closures_ref = store.publish_json(
        manifest_contract.stage_protocol_id, "production_closures", closure_set
    )
    if plan_ref != expected_plan_ref:
        raise EvidenceIntegrityError("experiment plan body reference is inconsistent")
    return ManifestFreezeRefs(
        protocol=protocol_ref,
        detached_manifest=detached_ref,
        production_closures=closures_ref,
        experiment_plan=plan_ref,
    )


def read_manifest_freeze(
    store: ImmutableEvidenceStore,
    manifest_contract: StageContract,
) -> Dict[str, Any]:
    """Re-read and authenticate all four manifest freeze artifacts."""

    if manifest_contract.stage_id != "OUTCOME_FREE_DEVELOPMENT_MANIFEST":
        raise EvidenceIntegrityError("manifest freeze belongs to the manifest stage")
    protocol_raw = store.read_bytes(manifest_contract.stage_protocol_id, "protocol")
    detached_raw = store.read_bytes(
        manifest_contract.stage_protocol_id, "detached_manifest"
    )
    closures_raw = store.read_bytes(
        manifest_contract.stage_protocol_id, "production_closures"
    )
    plan_raw = store.read_bytes(manifest_contract.stage_protocol_id, "experiment_plan")
    protocol = load_canonical_json_bytes(protocol_raw)
    detached_manifest = load_canonical_json_bytes(detached_raw)
    closure_set = load_canonical_json_bytes(closures_raw)
    _validate_closure_set(protocol, manifest_contract, closure_set, plan_raw)
    bootstrap = read_manifest_bootstrap(store, manifest_contract)
    if (
        protocol_raw
        != canonical_json_bytes(bootstrap["protocol"])
        or closures_raw
        != canonical_json_bytes(bootstrap["production_closures"])
        or plan_raw != bootstrap["experiment_plan_bytes"]
    ):
        raise EvidenceIntegrityError(
            "manifest freeze differs from its outcome-free bootstrap"
        )
    refs = ManifestFreezeRefs(
        protocol=BodyRef(hashlib.sha256(protocol_raw).hexdigest(), len(protocol_raw)),
        detached_manifest=BodyRef(
            hashlib.sha256(detached_raw).hexdigest(), len(detached_raw)
        ),
        production_closures=BodyRef(
            hashlib.sha256(closures_raw).hexdigest(), len(closures_raw)
        ),
        experiment_plan=BodyRef(hashlib.sha256(plan_raw).hexdigest(), len(plan_raw)),
    )
    return {
        "detached_manifest": detached_manifest,
        "experiment_plan_bytes": plan_raw,
        "production_closures": closure_set,
        "protocol": protocol,
        "refs": refs,
    }


def read_authenticated_stage_inputs(
    store: ImmutableEvidenceStore,
    stage_id: str,
) -> AuthenticatedStageInputs:
    """Return only detached, authenticated inputs for one frozen stage.

    The full selection is neither accepted nor returned.  Every parent is read
    from its fixed stage path and its complete terminal chain is reconstructed.
    """

    bootstrap = read_manifest_bootstrap(store)
    protocol = bootstrap["protocol"]
    contracts_by_stage = {
        value: extract_stage_contract(protocol, value)
        for value in protocol["stage_sequence"]
    }
    closure_values = bootstrap["production_closures"]["ordered_closures"]
    bootstrap_closures_by_stage = {
        stage_id: _validate_closure(
            contract, closure_values[contract.stage_index]
        )
        for stage_id, contract in contracts_by_stage.items()
    }
    manifest_contract = extract_stage_contract(
        protocol, "OUTCOME_FREE_DEVELOPMENT_MANIFEST"
    )
    if manifest_contract.stage_protocol_id != _MANIFEST_STAGE_PROTOCOL_ID:
        raise EvidenceIntegrityError("manifest fixed path differs from the protocol")
    _require_no_contradiction(store, manifest_contract.stage_protocol_id)
    manifest_snapshot = _load_chain_snapshot(store, manifest_contract)
    manifest_lifecycle = validate_chain_snapshot(
        manifest_contract, manifest_snapshot
    )
    bootstrap_manifest_closure = bootstrap_closures_by_stage[
        manifest_contract.stage_id
    ]
    if manifest_snapshot.production_closure is None:
        raise EvidenceIntegrityError(
            "development manifest terminal lacks its reserved production closure"
        )
    _compare_built(
        bootstrap_manifest_closure.as_dict(),
        manifest_snapshot.production_closure.as_dict(),
        "fixed-path manifest reservation closure from bootstrap",
    )
    if manifest_lifecycle == "COMPLETED":
        freeze = read_manifest_freeze(store, manifest_contract)
        completed_result = _exact_keys(
            manifest_snapshot.completed["result"],
            ("artifact_refs_or_null", "summary"),
            "manifest completed result",
        )
        if completed_result["artifact_refs_or_null"] != freeze["refs"].as_dict():
            raise EvidenceIntegrityError(
                "manifest completed refs differ from frozen artifacts"
            )
        detached_manifest = freeze["detached_manifest"]
        freeze_refs: Optional[ManifestFreezeRefs] = freeze["refs"]
    elif manifest_lifecycle in ("FAILED", "ORPHANED"):
        detached_manifest = None
        freeze_refs = None
    else:
        raise EvidenceIntegrityError(
            "development manifest lacks an authentic terminal lifecycle"
        )
    target_contract = extract_stage_contract(protocol, stage_id)
    if target_contract.stage_id == manifest_contract.stage_id:
        raise EvidenceIntegrityError(
            "manifest stage does not consume its own authenticated inputs"
        )
    _require_no_contradiction(store, target_contract.stage_protocol_id)
    target_closure = _validate_closure(
        target_contract, closure_values[target_contract.stage_index]
    )
    if target_closure.payload["manifest_experiment_plan_sha256"] != hashlib.sha256(
        bootstrap["experiment_plan_bytes"]
    ).hexdigest():
        raise EvidenceIntegrityError("target closure does not bind the manifest plan")
    outcome_stage_ids = {
        _EXACT_STAGE_ID,
        _RANDOM_STAGE_ID,
        _DEPTH1_STAGE_ID,
        _TELEMETRY_STAGE_ID,
    }
    schedule = (
        _frozen_ledger_schedule(protocol)
        if outcome_stage_ids.intersection(
            target_contract.required_parent_terminal_stage_ids
        )
        else None
    )
    parent_seals = []
    validated_parent_stages = set()
    for parent_stage_id in target_contract.required_parent_terminal_stage_ids:
        parent_contract = contracts_by_stage[parent_stage_id]
        parent_snapshot = _load_chain_snapshot(store, parent_contract)
        state = validate_chain_snapshot(parent_contract, parent_snapshot)
        if state not in ("BLOCKED", "ORPHANED", "FAILED", "COMPLETED"):
            raise EvidenceIntegrityError("required parent lacks an authentic terminal seal")
        _validate_fixed_parent_references(
            store,
            protocol,
            parent_contract,
            parent_snapshot,
            contracts_by_stage,
            bootstrap_closures_by_stage,
            schedule,
            validated_stage_ids=validated_parent_stages,
        )
        parent_seals.append(parent_snapshot.terminal_seal)
    _ordered_parent_seals(target_contract, parent_seals)
    # Gate semantics are deliberately not collapsed here: callers use
    # ``build_reservation`` for a passing gate or ``build_blocked`` for its first
    # closed failure, both over this exact ordered tuple.
    return AuthenticatedStageInputs(
        contract=target_contract,
        protocol=protocol,
        detached_manifest=detached_manifest,
        experiment_plan_bytes=bootstrap["experiment_plan_bytes"],
        production_closure=target_closure,
        ordered_parent_terminal_seals=tuple(parent_seals),
        manifest_freeze_refs=freeze_refs,
        manifest_bootstrap_refs=bootstrap["refs"],
        manifest_lifecycle=manifest_lifecycle,
    )


def _optional_stage_json(
    store: ImmutableEvidenceStore, stage_protocol_id: str, artifact: str
) -> Optional[Any]:
    try:
        return store.read_json(stage_protocol_id, artifact)
    except FileNotFoundError:
        return None
    except EvidenceIntegrityError as error:
        if isinstance(error.__cause__, FileNotFoundError):
            return None
        raise


def _optional_stage_bytes(
    store: ImmutableEvidenceStore, stage_protocol_id: str, artifact: str
) -> Optional[bytes]:
    try:
        return store.read_bytes(stage_protocol_id, artifact)
    except FileNotFoundError:
        return None
    except EvidenceIntegrityError as error:
        if isinstance(error.__cause__, FileNotFoundError):
            return None
        raise


def _load_chain_snapshot(
    store: ImmutableEvidenceStore, contract: StageContract
) -> ChainSnapshot:
    stage_protocol_id = contract.stage_protocol_id
    reservation = _optional_stage_json(store, stage_protocol_id, "reservation")
    blocked = _optional_stage_json(store, stage_protocol_id, "blocked")
    closure_value = None
    if reservation is not None:
        references = _exact_mapping(reservation, "reservation").get("references")
        if type(references) is dict:
            closure_value = references.get("production_closure")
    elif blocked is not None:
        references = _exact_mapping(blocked, "blocked").get("references")
        if type(references) is dict:
            closure_value = references.get("production_closure")
    closure = None if closure_value is None else _validate_closure(contract, closure_value)
    return ChainSnapshot(
        production_closure=closure,
        reservation=reservation,
        attempt=_optional_stage_json(store, stage_protocol_id, "attempt"),
        blocked=blocked,
        partial_evidence=_optional_stage_json(store, stage_protocol_id, "partial_ledger"),
        failure=_optional_stage_json(store, stage_protocol_id, "failure"),
        completed=_optional_stage_json(store, stage_protocol_id, "completed"),
        orphaned=_optional_stage_json(store, stage_protocol_id, "orphaned"),
        terminal_seal=_optional_stage_json(store, stage_protocol_id, "terminal_seal"),
    )


def _require_no_contradiction(
    store: ImmutableEvidenceStore, stage_protocol_id: str
) -> None:
    try:
        store.read_contradiction(stage_protocol_id)
    except FileNotFoundError:
        return
    except EvidenceIntegrityError as error:
        if isinstance(error.__cause__, FileNotFoundError):
            return
        raise
    raise EvidenceIntegrityError("stage has an immutable contradiction sidecar")


def _require_fresh_stage(
    store: ImmutableEvidenceStore,
    contract: StageContract,
    ledger_specs: Sequence[LedgerSpec],
) -> None:
    _require_no_contradiction(store, contract.stage_protocol_id)
    try:
        store.scan_fixed_catalog(contract.stage_protocol_id, ledger_specs)
    except FileNotFoundError:
        return
    except EvidenceIntegrityError as error:
        if isinstance(error.__cause__, FileNotFoundError):
            return
        raise
    raise EvidenceConflictError("stage protocol id already has immutable evidence")


def begin_stage(
    store: ImmutableEvidenceStore,
    repository: os.PathLike,
    contract: StageContract,
    production_closure: ProductionClosure,
    ordered_parent_terminal_seals: Sequence[Any],
    experiment_plan_bytes: bytes,
    ledger_specs: Sequence[LedgerSpec] = (),
) -> ChainSnapshot:
    """Reserve and attempt exactly once; caller must hold the stage lock."""

    store._require_stage_lock(contract.stage_protocol_id)
    _require_fresh_stage(store, contract, ledger_specs)
    reseal_production_closure(
        repository, contract, production_closure, experiment_plan_bytes
    )
    reservation = build_reservation(
        contract, production_closure, ordered_parent_terminal_seals
    )
    # Reservation is deliberately the first stage-path write.
    store.publish_json(contract.stage_protocol_id, "reservation", reservation)
    if contract.stage_id == "OUTCOME_FREE_DEVELOPMENT_MANIFEST":
        store.publish_bytes(
            contract.stage_protocol_id, "experiment_plan", experiment_plan_bytes
        )
    attempt = build_attempt(contract, reservation)
    store.publish_json(contract.stage_protocol_id, "attempt", attempt)
    snapshot = ChainSnapshot(
        production_closure=production_closure,
        reservation=reservation,
        attempt=attempt,
    )
    if validate_chain_snapshot(contract, snapshot) != "ATTEMPTED":
        raise EvidenceIntegrityError("new attempted stage chain failed validation")
    return snapshot


def block_stage(
    store: ImmutableEvidenceStore,
    repository: os.PathLike,
    contract: StageContract,
    production_closure: ProductionClosure,
    ordered_parent_terminal_seals: Sequence[Any],
    experiment_plan_bytes: bytes,
    ledger_specs: Sequence[LedgerSpec] = (),
) -> Dict[str, Any]:
    """Seal a closed prerequisite gate without reservation or capability."""

    store._require_stage_lock(contract.stage_protocol_id)
    _require_fresh_stage(store, contract, ledger_specs)
    reseal_production_closure(
        repository, contract, production_closure, experiment_plan_bytes
    )
    blocked = build_blocked(
        contract, production_closure, ordered_parent_terminal_seals
    )
    terminal = build_terminal_seal(contract, "BLOCKED", blocked=blocked)
    # Everything that can fail semantically was checked before the first write.
    store.publish_json(contract.stage_protocol_id, "blocked", blocked)
    store.publish_json(contract.stage_protocol_id, "terminal_seal", terminal)
    snapshot = ChainSnapshot(
        production_closure=production_closure,
        blocked=blocked,
        terminal_seal=terminal,
    )
    if validate_chain_snapshot(contract, snapshot) != "BLOCKED":
        raise EvidenceIntegrityError("new BLOCKED chain failed validation")
    return terminal


def _validate_completion_refs(
    store: ImmutableEvidenceStore,
    contract: StageContract,
    artifact_refs: Optional[Any],
) -> Optional[Dict[str, Any]]:
    if contract.stage_id == "OUTCOME_FREE_DEVELOPMENT_MANIFEST":
        if not isinstance(artifact_refs, ManifestFreezeRefs):
            raise EvidenceIntegrityError("manifest completion requires four freeze BodyRefs")
        observed = read_manifest_freeze(store, contract)["refs"]
        if observed != artifact_refs:
            raise EvidenceIntegrityError("manifest completion BodyRefs do not reseal")
        return artifact_refs.as_dict()
    if _requires_full_partial_ledger(contract):
        if not isinstance(artifact_refs, StageResultRefs):
            raise EvidenceIntegrityError("outcome stage completion requires ledger/catalog BodyRefs")
        observed = read_stage_completion_evidence(store, contract, artifact_refs)["refs"]
        return observed.as_dict()
    if artifact_refs is not None:
        if not hasattr(artifact_refs, "as_dict"):
            raise TypeError("completion artifact refs are invalid")
        return _clone_json(artifact_refs.as_dict())
    return None


def _body_ref_from_value(value: Any, label: str) -> BodyRef:
    body = _exact_keys(value, ("byte_count", "sha256"), label)
    byte_count = body["byte_count"]
    if type(byte_count) is not int or byte_count < 0:
        raise EvidenceIntegrityError("{} byte count is invalid".format(label))
    return BodyRef(
        sha256=_exact_hex(body["sha256"], 64, label + " SHA-256"),
        byte_count=byte_count,
    )


def _authenticate_completed_external_refs(
    store: ImmutableEvidenceStore,
    contract: StageContract,
    completed_value: Any,
    ledger_specs: Optional[Sequence[LedgerSpec]] = None,
) -> None:
    completed = _exact_keys(
        completed_value,
        (
            "artifact_type",
            "attempt_id",
            "reservation_id",
            "result",
            "stage_id",
            "stage_protocol_id",
        ),
        "completed artifact",
    )
    if (
        completed["artifact_type"] != "ATLAS_STAGE_COMPLETED_V1"
        or completed["stage_id"] != contract.stage_id
        or completed["stage_protocol_id"] != contract.stage_protocol_id
    ):
        raise EvidenceIntegrityError("completed artifact belongs to another stage")
    result = _exact_keys(
        completed["result"],
        ("artifact_refs_or_null", "summary"),
        "completed result",
    )
    refs = result["artifact_refs_or_null"]
    if contract.stage_id == "OUTCOME_FREE_DEVELOPMENT_MANIFEST":
        body = _exact_keys(
            refs,
            (
                "detached_manifest",
                "experiment_plan",
                "production_closures",
                "protocol",
            ),
            "manifest completion refs",
        )
        parsed = ManifestFreezeRefs(
            protocol=_body_ref_from_value(body["protocol"], "protocol ref"),
            detached_manifest=_body_ref_from_value(
                body["detached_manifest"], "detached manifest ref"
            ),
            production_closures=_body_ref_from_value(
                body["production_closures"], "production closures ref"
            ),
            experiment_plan=_body_ref_from_value(
                body["experiment_plan"], "experiment plan ref"
            ),
        )
        _validate_completion_refs(store, contract, parsed)
    elif _requires_full_partial_ledger(contract):
        body = _exact_keys(
            refs,
            ("record_catalog", "status_ledger"),
            "outcome completion refs",
        )
        parsed = StageResultRefs(
            status_ledger=_body_ref_from_value(
                body["status_ledger"], "status ledger ref"
            ),
            record_catalog=_body_ref_from_value(
                body["record_catalog"], "record catalog ref"
            ),
        )
        _validate_completion_refs(store, contract, parsed)
        if ledger_specs is not None:
            rebuilt = _reconcile_ledger_set(store, contract, ledger_specs)
            observed = store.read_json(contract.stage_protocol_id, "status_ledger")
            _compare_built(
                rebuilt,
                observed,
                "completed status ledger from immutable journals",
            )
    elif refs is not None:
        raise EvidenceIntegrityError(
            "assessment completion must not reference an external result artifact"
        )


def _reconciled_terminal_ledger_set(
    store: ImmutableEvidenceStore,
    contract: StageContract,
    snapshot: ChainSnapshot,
    lifecycle: str,
    ledger_specs: Sequence[LedgerSpec],
) -> Dict[str, Any]:
    """Rebuild a terminal stage ledger solely from its immutable journals."""

    observed = store.scan_fixed_catalog(contract.stage_protocol_id, ledger_specs)
    if lifecycle == "BLOCKED":
        compatible = {"blocked", "terminal_seal"}
        if any(
            reference is not None and artifact not in compatible
            for artifact, reference in observed.items()
        ):
            raise EvidenceIntegrityError(
                "BLOCKED stage retains an incompatible fixed-catalog artifact"
            )
        rebuilt = _reconcile_ledger_set(
            store, contract, ledger_specs, blocked=True
        )
    else:
        rebuilt = _reconcile_ledger_set(store, contract, ledger_specs)
    if rebuilt is None:
        raise EvidenceIntegrityError("terminal stage lacks a fixed ledger schedule")
    if lifecycle == "COMPLETED":
        observed = store.read_json(contract.stage_protocol_id, "status_ledger")
        _compare_built(
            rebuilt,
            observed,
            "completed status ledger from immutable journals",
        )
    elif lifecycle in ("FAILED", "ORPHANED"):
        if snapshot.partial_evidence is None:
            raise EvidenceIntegrityError(
                "noncompleted outcome terminal lacks its partial ledger"
            )
        _compare_built(
            rebuilt,
            snapshot.partial_evidence,
            "terminal partial ledger from immutable journals",
        )
    elif lifecycle != "BLOCKED":
        raise EvidenceIntegrityError("ledger reconstruction requires a terminal lifecycle")
    return rebuilt


def _require_frozen_completion_gate(
    contract: StageContract,
    ledger_set: Mapping[str, Any],
    ledger_specs: Sequence[LedgerSpec],
) -> None:
    phases = tuple(ledger_set["phase_ids"])
    if phases != tuple(spec.phase_id for spec in ledger_specs):
        raise EvidenceIntegrityError("completed ledger phase order is not frozen")
    ledgers = ledger_set["ledgers"]
    if type(ledgers) is not list or len(ledgers) != len(ledger_specs):
        raise EvidenceIntegrityError("completed ledger phase count is not frozen")
    statuses_by_phase = {
        ledger["phase_id"]: tuple(slot["status"] for slot in ledger["slots"])
        for ledger in ledgers
    }
    if contract.stage_id == _EXACT_STAGE_ID:
        if (
            len(statuses_by_phase.get("exact", ())) != 288
            or set(statuses_by_phase["exact"]) != {"COMPLETE"}
            or len(statuses_by_phase.get("exact-pv", ())) != 2_304
            or set(statuses_by_phase["exact-pv"]) != {"VALID"}
        ):
            raise EvidenceIntegrityError(
                "exact COMPLETED ledger fails its all-slot frozen gate"
            )
        return
    if contract.stage_id == _RANDOM_STAGE_ID:
        statuses = statuses_by_phase.get("random", ())
        if len(statuses) != 18_432 or set(statuses) != {"COMPLETE"}:
            raise EvidenceIntegrityError(
                "random COMPLETED ledger fails its all-slot frozen gate"
            )
        return
    if contract.stage_id == _DEPTH1_STAGE_ID:
        statuses = statuses_by_phase.get("depth1", ())
        if len(statuses) != 18_432 or set(statuses) != {"COMPLETE"}:
            raise EvidenceIntegrityError(
                "depth-1 COMPLETED ledger fails its all-slot frozen gate"
            )
        return
    if contract.stage_id == _TELEMETRY_STAGE_ID:
        statuses = statuses_by_phase.get("telemetry", ())
        if len(statuses) != 36_864:
            raise EvidenceIntegrityError("telemetry COMPLETED denominator drifted")
        preclassified = dict(ledger_specs[0].preclassified_statuses)
        for index, status in enumerate(statuses):
            if index in preclassified:
                if status != "NOT_ADMISSIBLE":
                    raise EvidenceIntegrityError(
                        "telemetry parent-derived preclassification drifted"
                    )
            elif status != "VALIDATED":
                raise EvidenceIntegrityError(
                    "telemetry COMPLETED has a nonvalidated admissible slot"
                )
        return
    raise EvidenceIntegrityError("stage has no frozen outcome completion gate")


def _sampled_parent_ledger_for_telemetry(
    store: ImmutableEvidenceStore,
    protocol_value: Mapping[str, Any],
    contract: StageContract,
    contracts_by_stage: Mapping[str, StageContract],
    schedule: _FrozenLedgerSchedule,
) -> Dict[str, Any]:
    snapshot = _load_chain_snapshot(store, contract)
    lifecycle = validate_chain_snapshot(contract, snapshot)
    if lifecycle not in ("BLOCKED", "ORPHANED", "FAILED", "COMPLETED"):
        raise EvidenceIntegrityError(
            "telemetry sampled parent lacks an authentic terminal lifecycle"
        )
    specs = _base_frozen_ledger_specs(contract, schedule)
    if lifecycle == "COMPLETED":
        completed_ledger = _validate_completed_stage_evidence(
            store,
            protocol_value,
            contract,
            snapshot.completed,
            contracts_by_stage,
            schedule,
        )
        if completed_ledger is None:
            raise EvidenceIntegrityError("sampled completed parent lacks a ledger")
        return completed_ledger
    return _reconciled_terminal_ledger_set(
        store, contract, snapshot, lifecycle, specs
    )


def _frozen_completion_ledger_specs(
    store: ImmutableEvidenceStore,
    protocol_value: Mapping[str, Any],
    contract: StageContract,
    contracts_by_stage: Mapping[str, StageContract],
    schedule: _FrozenLedgerSchedule,
) -> Tuple[LedgerSpec, ...]:
    if contract.stage_id in (_EXACT_STAGE_ID, _RANDOM_STAGE_ID, _DEPTH1_STAGE_ID):
        return _base_frozen_ledger_specs(contract, schedule)
    if contract.stage_id != _TELEMETRY_STAGE_ID:
        return ()
    sampled_statuses: Dict[str, str] = {}
    for stage_id, expected_phase in (
        (_RANDOM_STAGE_ID, "random"),
        (_DEPTH1_STAGE_ID, "depth1"),
    ):
        parent_contract = contracts_by_stage.get(stage_id)
        if not isinstance(parent_contract, StageContract):
            raise EvidenceIntegrityError(
                "telemetry sampled parent contract is absent"
            )
        ledger_set = _sampled_parent_ledger_for_telemetry(
            store,
            protocol_value,
            parent_contract,
            contracts_by_stage,
            schedule,
        )
        if ledger_set["phase_ids"] != [expected_phase]:
            raise EvidenceIntegrityError(
                "telemetry sampled parent phase set drifted"
            )
        for slot in ledger_set["ledgers"][0]["slots"]:
            slot_id = slot["slot_id"]
            if slot_id in sampled_statuses:
                raise EvidenceIntegrityError(
                    "telemetry sampled parent slots overlap"
                )
            sampled_statuses[slot_id] = slot["status"]
    if set(sampled_statuses) != set(schedule.telemetry_ids):
        raise EvidenceIntegrityError(
            "telemetry sampled parents do not cover its fixed schedule"
        )
    preclassified = tuple(
        (index, "NOT_ADMISSIBLE")
        for index, slot_id in enumerate(schedule.telemetry_ids)
        if sampled_statuses[slot_id] != "COMPLETE"
    )
    return (
        LedgerSpec(
            "telemetry",
            schedule.telemetry_ids,
            ("VALIDATED", "INVALID", "PROOF_CONTRADICTION"),
            "MISSING",
            "MISSING",
            preclassified_statuses=preclassified,
        ),
    )


def _validate_completed_stage_evidence(
    store: ImmutableEvidenceStore,
    protocol_value: Mapping[str, Any],
    contract: StageContract,
    completed_value: Any,
    contracts_by_stage: Mapping[str, StageContract],
    schedule: Optional[_FrozenLedgerSchedule],
) -> Optional[Dict[str, Any]]:
    """Apply the frozen COMPLETED validator shared by gates and recovery."""

    _authenticate_completed_external_refs(store, contract, completed_value)
    if contract.stage_id in (_MANIFEST_STAGE_ID, _ASSESSMENT_STAGE_ID):
        return None
    if schedule is None:
        schedule = _frozen_ledger_schedule(protocol_value)
    specs = _frozen_completion_ledger_specs(
        store, protocol_value, contract, contracts_by_stage, schedule
    )
    if not specs:
        raise EvidenceIntegrityError("outcome COMPLETED stage lacks frozen ledger specs")
    snapshot = _load_chain_snapshot(store, contract)
    if validate_chain_snapshot(contract, snapshot) not in (
        "COMPLETED",
        "COMPLETED_UNSEALED",
    ):
        raise EvidenceIntegrityError("completed validator lacks its fixed stage chain")
    rebuilt = _reconciled_terminal_ledger_set(
        store, contract, snapshot, "COMPLETED", specs
    )
    _require_frozen_completion_gate(contract, rebuilt, specs)
    return rebuilt


def _validate_fixed_parent_references(
    store: ImmutableEvidenceStore,
    protocol_value: Mapping[str, Any],
    contract: StageContract,
    snapshot: ChainSnapshot,
    contracts_by_stage: Mapping[str, StageContract],
    bootstrap_closures_by_stage: Mapping[str, ProductionClosure],
    schedule: Optional[_FrozenLedgerSchedule],
    *,
    validated_stage_ids: Optional[set] = None,
    visiting_stage_ids: Tuple[str, ...] = (),
) -> None:
    """Bind every embedded ancestor seal to its immutable fixed-path chain.

    Terminal-seal identities are public hashes, so validating an embedded seal
    in isolation is insufficient: a self-consistent alternate ancestor could
    otherwise authorize a descendant.  This walk compares the complete
    embedded envelope byte-for-byte with the terminal at the parent's fixed
    stage path, validates that parent's complete chain, and repeats to the
    manifest root.
    """

    if not isinstance(snapshot, ChainSnapshot):
        raise TypeError("snapshot must be a ChainSnapshot")
    if type(contracts_by_stage) is not dict:
        raise TypeError("stage contract catalog must be an exact mapping")
    if type(bootstrap_closures_by_stage) is not dict:
        raise TypeError("bootstrap closure catalog must be an exact mapping")
    _require_no_contradiction(store, contract.stage_protocol_id)
    if validated_stage_ids is None:
        validated_stage_ids = set()
    if type(validated_stage_ids) is not set:
        raise TypeError("validated stage ids must be an exact set")
    if contract.stage_id in visiting_stage_ids:
        raise EvidenceIntegrityError("stage parent graph contains a cycle")
    if contract.stage_id in validated_stage_ids:
        return
    if snapshot.reservation is not None and snapshot.blocked is not None:
        raise EvidenceIntegrityError(
            "stage cannot carry both reservation and blocked parent references"
        )
    carrier = (
        snapshot.reservation
        if snapshot.reservation is not None
        else snapshot.blocked
    )
    if carrier is None:
        if contract.required_parent_terminal_stage_ids:
            raise EvidenceIntegrityError(
                "stage evidence lacks its required parent reference carrier"
            )
        validated_stage_ids.add(contract.stage_id)
        return
    expected_closure = bootstrap_closures_by_stage.get(contract.stage_id)
    if not isinstance(expected_closure, ProductionClosure):
        raise EvidenceIntegrityError(
            "stage bootstrap closure is absent from the frozen catalog"
        )
    if snapshot.production_closure is None:
        raise EvidenceIntegrityError("stage parent carrier lacks a production closure")
    _compare_built(
        expected_closure.as_dict(),
        snapshot.production_closure.as_dict(),
        "stage carrier production closure from bootstrap",
    )
    carrier_value = _exact_mapping(carrier, "stage parent reference carrier")
    references = _exact_mapping(
        carrier_value.get("references"), "stage parent reference carrier references"
    )
    embedded_parents = _ordered_parent_seals(
        contract, references.get("ordered_parent_terminal_seals")
    )
    next_visiting = visiting_stage_ids + (contract.stage_id,)
    for parent_stage_id, embedded_parent in zip(
        contract.required_parent_terminal_stage_ids, embedded_parents
    ):
        parent_contract = contracts_by_stage.get(parent_stage_id)
        if not isinstance(parent_contract, StageContract):
            raise EvidenceIntegrityError(
                "required parent contract is absent from the frozen catalog"
            )
        if (
            parent_contract.stage_id != parent_stage_id
            or parent_contract.stage_index >= contract.stage_index
        ):
            raise EvidenceIntegrityError("stage parent contract order is invalid")
        parent_snapshot = _load_chain_snapshot(store, parent_contract)
        parent_state = validate_chain_snapshot(parent_contract, parent_snapshot)
        if parent_state not in ("BLOCKED", "ORPHANED", "FAILED", "COMPLETED"):
            raise EvidenceIntegrityError(
                "embedded parent lacks an authentic fixed-path terminal chain"
            )
        _compare_built(
            parent_snapshot.terminal_seal,
            embedded_parent,
            "embedded parent terminal seal at fixed stage path",
        )
        _validate_fixed_parent_references(
            store,
            protocol_value,
            parent_contract,
            parent_snapshot,
            contracts_by_stage,
            bootstrap_closures_by_stage,
            schedule,
            validated_stage_ids=validated_stage_ids,
            visiting_stage_ids=next_visiting,
        )
    state = validate_chain_snapshot(contract, snapshot)
    if snapshot.completed is not None:
        _validate_completed_stage_evidence(
            store,
            protocol_value,
            contract,
            snapshot.completed,
            contracts_by_stage,
            schedule,
        )
    elif contract.stage_id in (
        _EXACT_STAGE_ID,
        _RANDOM_STAGE_ID,
        _DEPTH1_STAGE_ID,
        _TELEMETRY_STAGE_ID,
    ) and state in (
        "BLOCKED",
        "BLOCKED_UNSEALED",
        "FAILED",
        "FAILED_UNSEALED",
        "ORPHANED",
        "ORPHANED_UNSEALED",
    ):
        if schedule is None:
            raise EvidenceIntegrityError(
                "terminal outcome validation lacks its frozen schedule"
            )
        specs = _frozen_completion_ledger_specs(
            store, protocol_value, contract, contracts_by_stage, schedule
        )
        lifecycle = state.split("_", 1)[0]
        _reconciled_terminal_ledger_set(
            store, contract, snapshot, lifecycle, specs
        )
    validated_stage_ids.add(contract.stage_id)


def seal_completed_stage(
    store: ImmutableEvidenceStore,
    repository: os.PathLike,
    contract: StageContract,
    production_closure: ProductionClosure,
    experiment_plan_bytes: bytes,
    summary: Any,
    artifact_refs: Optional[Any] = None,
) -> Dict[str, Any]:
    """Reseal source and referenced bodies, then publish COMPLETED and its seal."""

    store._require_stage_lock(contract.stage_protocol_id)
    _require_no_contradiction(store, contract.stage_protocol_id)
    snapshot = _load_chain_snapshot(store, contract)
    if validate_chain_snapshot(contract, snapshot) != "ATTEMPTED":
        raise EvidenceConflictError("stage is not an unsealed attempted chain")
    _compare_built(
        production_closure.as_dict(),
        snapshot.production_closure.as_dict(),
        "completion production closure",
    )
    reseal_production_closure(
        repository, contract, production_closure, experiment_plan_bytes
    )
    refs_value = _validate_completion_refs(store, contract, artifact_refs)
    result = {"artifact_refs_or_null": refs_value, "summary": summary}
    completed = build_completed(
        contract, snapshot.reservation, snapshot.attempt, result
    )
    terminal = build_terminal_seal(
        contract,
        "COMPLETED",
        reservation=snapshot.reservation,
        attempt=snapshot.attempt,
        completed=completed,
    )
    # No semantic operation follows the first lifecycle-body publish.
    store.publish_json(contract.stage_protocol_id, "completed", completed)
    store.publish_json(contract.stage_protocol_id, "terminal_seal", terminal)
    return terminal


def seal_failed_stage(
    store: ImmutableEvidenceStore,
    contract: StageContract,
    failure_value: Any,
    ledger_specs: Sequence[LedgerSpec] = (),
) -> Dict[str, Any]:
    """Reconcile retained evidence, then publish FAILED and its terminal seal."""

    store._require_stage_lock(contract.stage_protocol_id)
    _require_no_contradiction(store, contract.stage_protocol_id)
    snapshot = _load_chain_snapshot(store, contract)
    if validate_chain_snapshot(contract, snapshot) != "ATTEMPTED":
        raise EvidenceConflictError("stage is not an unsealed attempted chain")
    partial = _reconcile_ledger_set(store, contract, ledger_specs)
    failure = build_failure(
        contract,
        snapshot.reservation,
        snapshot.attempt,
        failure_value,
        partial,
    )
    terminal = build_terminal_seal(
        contract,
        "FAILED",
        reservation=snapshot.reservation,
        attempt=snapshot.attempt,
        failure=failure,
        partial_evidence=partial,
    )
    if partial is not None:
        store.publish_json(contract.stage_protocol_id, "partial_ledger", partial)
    store.publish_json(contract.stage_protocol_id, "failure", failure)
    store.publish_json(contract.stage_protocol_id, "terminal_seal", terminal)
    return terminal


@dataclass(frozen=True)
class RecoveryResult:
    action: str
    lifecycle: Optional[str]
    terminal_identity: Optional[str]


def _validate_recovery_completed_summary_expectation(
    contract: StageContract,
    snapshot: ChainSnapshot,
    expected_completed_summary: Optional[Any],
) -> None:
    """Bind assessment recovery to an independently reconstructed summary."""

    if contract.stage_id != _ASSESSMENT_STAGE_ID:
        if expected_completed_summary is not None:
            raise EvidenceIntegrityError(
                "completed summary expectation is restricted to assessment recovery"
            )
        return
    if snapshot.completed is None:
        if expected_completed_summary is not None:
            raise EvidenceIntegrityError(
                "assessment recovery received an unexpected completed summary"
            )
        return
    if expected_completed_summary is None:
        raise EvidenceIntegrityError(
            "assessment completed recovery requires its expected summary"
        )
    completed = _exact_keys(
        snapshot.completed,
        (
            "artifact_type",
            "attempt_id",
            "reservation_id",
            "result",
            "stage_id",
            "stage_protocol_id",
        ),
        "assessment completed artifact",
    )
    result = _exact_keys(
        completed["result"],
        ("artifact_refs_or_null", "summary"),
        "assessment completed result",
    )
    if canonical_json_bytes(expected_completed_summary) != canonical_json_bytes(
        result["summary"]
    ):
        raise EvidenceIntegrityError(
            "assessment completed summary does not reconstruct"
        )


def _restore_manifest_plan_from_bootstrap(
    store: ImmutableEvidenceStore,
    contract: StageContract,
    closure: ProductionClosure,
    manifest_bootstrap: Optional[Mapping[str, Any]],
) -> None:
    if contract.stage_id != "OUTCOME_FREE_DEVELOPMENT_MANIFEST":
        return
    if manifest_bootstrap is None:
        raise EvidenceIntegrityError(
            "manifest plan recovery requires its authenticated bootstrap"
        )
    raw = manifest_bootstrap["experiment_plan_bytes"]
    if type(raw) is not bytes:
        raise EvidenceIntegrityError("manifest bootstrap plan bytes are invalid")
    if hashlib.sha256(raw).hexdigest() != closure.payload[
        "manifest_experiment_plan_sha256"
    ]:
        raise EvidenceIntegrityError(
            "manifest bootstrap plan does not match reservation"
        )
    existing = _optional_stage_bytes(
        store, contract.stage_protocol_id, "experiment_plan"
    )
    if existing is not None:
        if existing != raw:
            raise EvidenceIntegrityError(
                "manifest experiment plan copy differs from its bootstrap"
            )
        return
    store.publish_bytes(contract.stage_protocol_id, "experiment_plan", raw)


def _publish_recovery_contradiction(
    store: ImmutableEvidenceStore,
    contract: StageContract,
    observed: Optional[Mapping[str, Optional[BodyRef]]],
) -> None:
    catalog = {}
    if observed is not None:
        catalog = {
            key: None if value is None else value.as_dict()
            for key, value in sorted(observed.items())
        }
    store.publish_contradiction(
        contract.stage_protocol_id,
        {
            "artifact_type": "ATLAS_STAGE_CONTRADICTION_V1",
            "observed_catalog": catalog,
            "reason": "INVALID_OR_CONFLICTING_STAGE_EVIDENCE",
            "stage_id": contract.stage_id,
            "stage_protocol_id": contract.stage_protocol_id,
        },
    )


def _authenticated_outcome_recovery_context(
    store: ImmutableEvidenceStore,
    contract: StageContract,
    ledger_specs: Sequence[LedgerSpec],
) -> Tuple[
    Dict[str, Any],
    Dict[str, Any],
    Dict[str, StageContract],
    _FrozenLedgerSchedule,
    Tuple[LedgerSpec, ...],
]:
    """Derive authoritative outcome recovery specs from the frozen bootstrap."""

    bootstrap = read_manifest_bootstrap(store)
    protocol = bootstrap["protocol"]
    contracts_by_stage = {
        stage_id: extract_stage_contract(protocol, stage_id)
        for stage_id in protocol["stage_sequence"]
    }
    if contracts_by_stage.get(contract.stage_id) != contract:
        raise EvidenceIntegrityError(
            "recovery contract differs from the manifest bootstrap"
        )
    schedule = _frozen_ledger_schedule(protocol)
    fixed_specs = _frozen_completion_ledger_specs(
        store,
        protocol,
        contract,
        contracts_by_stage,
        schedule,
    )
    if tuple(ledger_specs) != fixed_specs:
        raise EvidenceIntegrityError(
            "caller recovery ledger specs differ from the frozen protocol"
        )
    return bootstrap, protocol, contracts_by_stage, schedule, fixed_specs


def recover_stage(
    store: ImmutableEvidenceStore,
    contract: StageContract,
    ledger_specs: Sequence[LedgerSpec] = (),
    *,
    repository: Optional[os.PathLike] = None,
    expected_completed_summary: Optional[Any] = None,
) -> RecoveryResult:
    """Apply frozen recovery precedence without invoking any stage capability."""

    if type(ledger_specs) not in (list, tuple):
        raise TypeError("recovery ledger specs must be an exact sequence")
    outcome_stage_ids = (
        _EXACT_STAGE_ID,
        _RANDOM_STAGE_ID,
        _DEPTH1_STAGE_ID,
        _TELEMETRY_STAGE_ID,
    )
    observed = None
    with store.stage_lock(contract.stage_protocol_id, blocking=False):
        _require_no_contradiction(store, contract.stage_protocol_id)
        if not store._stage_entry_exists(contract.stage_protocol_id):
            if contract.stage_id not in outcome_stage_ids and ledger_specs:
                raise EvidenceIntegrityError(
                    "stage without a fixed outcome ledger received recovery specs"
                )
            if (
                contract.stage_id != _ASSESSMENT_STAGE_ID
                and expected_completed_summary is not None
            ):
                raise EvidenceIntegrityError(
                    "completed summary expectation is restricted to assessment recovery"
                )
            if contract.stage_id in outcome_stage_ids:
                _authenticated_outcome_recovery_context(
                    store, contract, ledger_specs
                )
            _validate_recovery_completed_summary_expectation(
                contract, ChainSnapshot(), expected_completed_summary
            )
            return RecoveryResult("NO_EVIDENCE", None, None)
        try:
            _require_no_contradiction(store, contract.stage_protocol_id)
            if contract.stage_id not in outcome_stage_ids and ledger_specs:
                raise EvidenceIntegrityError(
                    "stage without a fixed outcome ledger received recovery specs"
                )
            if (
                contract.stage_id != _ASSESSMENT_STAGE_ID
                and expected_completed_summary is not None
            ):
                raise EvidenceIntegrityError(
                    "completed summary expectation is restricted to assessment recovery"
                )

            manifest_bootstrap = None
            bootstrap = None
            recovery_protocol = None
            contracts_by_stage: Dict[str, StageContract] = {}
            schedule = None
            fixed_recovery_ledger_specs: Tuple[LedgerSpec, ...] = ()
            if contract.stage_id in outcome_stage_ids:
                (
                    bootstrap,
                    recovery_protocol,
                    contracts_by_stage,
                    schedule,
                    fixed_recovery_ledger_specs,
                ) = _authenticated_outcome_recovery_context(
                    store, contract, ledger_specs
                )

            try:
                observed = store.scan_fixed_catalog(
                    contract.stage_protocol_id, fixed_recovery_ledger_specs
                )
            except FileNotFoundError as error:
                raise EvidenceIntegrityError(
                    "fixed stage entry disappeared during recovery"
                ) from error
            except EvidenceIntegrityError as error:
                if isinstance(error.__cause__, FileNotFoundError):
                    raise EvidenceIntegrityError(
                        "fixed stage entry disappeared during recovery"
                    ) from error
                raise
            if contract.stage_id == "OUTCOME_FREE_DEVELOPMENT_MANIFEST":
                if any(value is not None for value in observed.values()):
                    manifest_bootstrap = read_manifest_bootstrap(store, contract)
                    recovery_protocol = manifest_bootstrap["protocol"]
                    contracts_by_stage = {
                        stage_id: extract_stage_contract(
                            recovery_protocol, stage_id
                        )
                        for stage_id in recovery_protocol["stage_sequence"]
                    }
                protocol_value = _optional_stage_json(
                    store, contract.stage_protocol_id, "protocol"
                )
                if protocol_value is None:
                    impossible_without_protocol = (
                        "detached_manifest",
                        "production_closures",
                        "completed",
                    )
                    if any(observed.get(name) is not None for name in impossible_without_protocol):
                        raise EvidenceIntegrityError(
                            "manifest freeze evidence exists without its protocol"
                        )
                else:
                    observed_contract = extract_stage_contract(
                        protocol_value, contract.stage_id
                    )
                    if observed_contract != contract:
                        raise EvidenceIntegrityError(
                            "manifest recovery contract differs from published protocol"
                        )
                    if manifest_bootstrap is None or canonical_json_bytes(
                        protocol_value
                    ) != canonical_json_bytes(manifest_bootstrap["protocol"]):
                        raise EvidenceIntegrityError(
                            "published manifest protocol differs from its bootstrap"
                        )
            raw_snapshot = _load_chain_snapshot(store, contract)
            if (
                raw_snapshot.reservation is None
                and raw_snapshot.blocked is None
            ):
                if store._journal_has_records(contract.stage_protocol_id):
                    raise EvidenceIntegrityError(
                        "slot journal evidence exists without a lifecycle root"
                    )
                if any(value is not None for value in observed.values()):
                    raise EvidenceIntegrityError(
                        "stage artifact exists without a lifecycle root"
                    )
            if manifest_bootstrap is not None:
                if (
                    raw_snapshot.reservation is None
                    and raw_snapshot.blocked is None
                ):
                    raise EvidenceIntegrityError(
                        "manifest stage artifact exists without a lifecycle root"
                    )
                if raw_snapshot.reservation is not None:
                    closure_values = manifest_bootstrap["production_closures"][
                        "ordered_closures"
                    ]
                    bootstrap_closure = _validate_closure(
                        contract, closure_values[contract.stage_index]
                    )
                    _compare_built(
                        bootstrap_closure.as_dict(),
                        raw_snapshot.production_closure.as_dict(),
                        "manifest reservation closure from bootstrap",
                    )
            if contract.required_parent_terminal_stage_ids and (
                raw_snapshot.reservation is not None
                or raw_snapshot.blocked is not None
            ):
                if bootstrap is None:
                    bootstrap = read_manifest_bootstrap(store)
                recovery_protocol = bootstrap["protocol"]
                contracts_by_stage = {
                    stage_id: extract_stage_contract(
                        recovery_protocol, stage_id
                    )
                    for stage_id in recovery_protocol["stage_sequence"]
                }
                if schedule is None and {
                    _EXACT_STAGE_ID,
                    _RANDOM_STAGE_ID,
                    _DEPTH1_STAGE_ID,
                    _TELEMETRY_STAGE_ID,
                }.intersection(contract.required_parent_terminal_stage_ids):
                    schedule = _frozen_ledger_schedule(recovery_protocol)
                closure_values = bootstrap["production_closures"][
                    "ordered_closures"
                ]
                bootstrap_closures_by_stage = {
                    stage_id: _validate_closure(
                        stage_contract,
                        closure_values[stage_contract.stage_index],
                    )
                    for stage_id, stage_contract in contracts_by_stage.items()
                }
                if contracts_by_stage.get(contract.stage_id) != contract:
                    raise EvidenceIntegrityError(
                        "recovery contract differs from the manifest bootstrap"
                    )
                _validate_fixed_parent_references(
                    store,
                    recovery_protocol,
                    contract,
                    raw_snapshot,
                    contracts_by_stage,
                    bootstrap_closures_by_stage,
                    schedule,
                )
            if raw_snapshot.reservation is not None and raw_snapshot.production_closure is not None:
                _restore_manifest_plan_from_bootstrap(
                    store,
                    contract,
                    raw_snapshot.production_closure,
                    manifest_bootstrap,
                )
                if manifest_bootstrap is not None:
                    stage_plan = store.read_bytes(
                        contract.stage_protocol_id, "experiment_plan"
                    )
                    if stage_plan != manifest_bootstrap["experiment_plan_bytes"]:
                        raise EvidenceIntegrityError(
                            "manifest stage plan differs from its bootstrap"
                        )
                    if observed.get("production_closures") is not None:
                        stage_closures = store.read_json(
                            contract.stage_protocol_id, "production_closures"
                        )
                        if canonical_json_bytes(stage_closures) != canonical_json_bytes(
                            manifest_bootstrap["production_closures"]
                        ):
                            raise EvidenceIntegrityError(
                                "manifest closure set differs from its bootstrap"
                            )
            needs_partial = _requires_full_partial_ledger(contract) and (
                raw_snapshot.failure is not None
                or raw_snapshot.orphaned is not None
                or (
                    raw_snapshot.reservation is not None
                    and raw_snapshot.completed is None
                    and raw_snapshot.terminal_seal is None
                )
            )
            if needs_partial:
                if not fixed_recovery_ledger_specs:
                    raise EvidenceIntegrityError(
                        "outcome partial recovery lacks frozen ledger specs"
                    )
                reconciled = _reconcile_ledger_set(
                    store, contract, fixed_recovery_ledger_specs
                )
                if (
                    raw_snapshot.attempt is None
                    and _ledger_set_has_journal_evidence(reconciled)
                ):
                    raise EvidenceIntegrityError(
                        "slot journal evidence exists before the stage attempt"
                    )
                if raw_snapshot.partial_evidence is None:
                    store.publish_json(
                        contract.stage_protocol_id, "partial_ledger", reconciled
                    )
                else:
                    _compare_built(
                        reconciled,
                        raw_snapshot.partial_evidence,
                        "reconciled partial ledger",
                    )
                raw_snapshot = _load_chain_snapshot(store, contract)
            if (
                raw_snapshot.completed is not None
                and contract.stage_id == _MANIFEST_STAGE_ID
            ):
                if recovery_protocol is None:
                    raise EvidenceIntegrityError(
                        "manifest completed recovery lacks its bootstrap protocol"
                    )
                _validate_completed_stage_evidence(
                    store,
                    recovery_protocol,
                    contract,
                    raw_snapshot.completed,
                    contracts_by_stage,
                    schedule,
                )
            state = validate_chain_snapshot(contract, raw_snapshot)
            _validate_recovery_completed_summary_expectation(
                contract, raw_snapshot, expected_completed_summary
            )
            if state in ("BLOCKED", "ORPHANED", "FAILED", "COMPLETED"):
                return RecoveryResult(
                    "VERIFIED_NO_OP",
                    state,
                    raw_snapshot.terminal_seal["identity"],
                )
            if state == "EMPTY":
                return RecoveryResult("NO_EVIDENCE", None, None)
            if state.endswith("_UNSEALED"):
                lifecycle = state[: -len("_UNSEALED")]
                terminal = build_terminal_seal(
                    contract,
                    lifecycle,
                    blocked=raw_snapshot.blocked,
                    reservation=raw_snapshot.reservation,
                    attempt=raw_snapshot.attempt,
                    failure=raw_snapshot.failure,
                    completed=raw_snapshot.completed,
                    orphaned=raw_snapshot.orphaned,
                    partial_evidence=raw_snapshot.partial_evidence,
                )
                store.publish_json(
                    contract.stage_protocol_id, "terminal_seal", terminal
                )
                return RecoveryResult(
                    "SEALED_EXISTING_" + lifecycle,
                    lifecycle,
                    terminal["identity"],
                )
            if state not in ("RESERVED", "ATTEMPTED"):
                raise EvidenceIntegrityError("unrecognized recoverable stage state")
            orphaned = build_orphaned(
                contract,
                raw_snapshot.reservation,
                raw_snapshot.attempt,
                raw_snapshot.partial_evidence,
            )
            terminal = build_terminal_seal(
                contract,
                "ORPHANED",
                reservation=raw_snapshot.reservation,
                attempt=raw_snapshot.attempt,
                orphaned=orphaned,
                partial_evidence=raw_snapshot.partial_evidence,
            )
            store.publish_json(contract.stage_protocol_id, "orphaned", orphaned)
            store.publish_json(contract.stage_protocol_id, "terminal_seal", terminal)
            return RecoveryResult("SEALED_NEW_ORPHANED", "ORPHANED", terminal["identity"])
        except EvidenceLockError:
            raise
        except Exception as error:
            try:
                _publish_recovery_contradiction(store, contract, observed)
            except EvidenceConflictError:
                pass
            raise EvidenceIntegrityError("stage recovery failed closed") from error
