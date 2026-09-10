"""Dedicated immutable evidence lifecycle for the Plan-0014 reconstruction.

This module is deliberately capability-free.  It knows how to authenticate and
publish the one-stage evidence chain, but it does not import the assessment
calculation, source binding, outer attestation, any stage facade, or game code.
The caller supplies already-built protocol, closure, binding, and result values.
"""

from __future__ import annotations

import base64
import contextlib
import errno
import fcntl
import hashlib
import os
from pathlib import Path
import re
import stat
from dataclasses import dataclass
from typing import Any, Dict, Iterator, Mapping, Optional, Sequence, Tuple

from .atlas_evidence import (
    BodyRef,
    EvidenceConflictError,
    EvidenceError,
    EvidenceIntegrityError,
    EvidenceLockError,
    canonical_body_ref,
    canonical_json_bytes,
    domain_identity,
    load_canonical_json_bytes,
)


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
    "experiments/runs/"
    "plan0014-plan0013-assessment-reconstruction-evidence-v1"
)

_MAX_ARTIFACT_BYTES = 64 * 1024 * 1024
_SAFE_COMPONENT = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]{0,191}\Z")
_SAFE_INTERNAL_COMPONENT = re.compile(r"\A[A-Za-z0-9.][A-Za-z0-9._-]{0,191}\Z")
_HEX40 = re.compile(r"\A[0-9a-f]{40}\Z")
_HEX64 = re.compile(r"\A[0-9a-f]{64}\Z")
_READABLE_ARTIFACT_MODES = (0o400, 0o644)
_READABLE_EVIDENCE_DIRECTORY_MODES = (0o700, 0o755)

_BOOTSTRAP_FILE = "bootstrap.json"
_CONTRADICTION_FILE = "contradiction.json"
_STAGES_DIRECTORY = "stages"
_LOCKS_DIRECTORY = ".locks"
_PENDING_DIRECTORY = ".pending"

_STAGE_ARTIFACT_FILES = {
    "reservation": "reservation.json",
    "attempt": "attempt.json",
    "completed": "completed.json",
    "failure": "failure.json",
    "orphaned": "orphaned.json",
    "terminal_seal": "terminal-seal.json",
}
_LIFECYCLE_BODY_ARTIFACTS = ("completed", "failure", "orphaned")
_ROOT_CATALOG = frozenset(
    (
        _BOOTSTRAP_FILE,
        _CONTRADICTION_FILE,
        _STAGES_DIRECTORY,
        _LOCKS_DIRECTORY,
        _PENDING_DIRECTORY,
    )
)
_PENDING_TARGETS = {
    "root--bootstrap.json.pending": ("root", _BOOTSTRAP_FILE),
    "root--contradiction.json.pending": ("root", _CONTRADICTION_FILE),
    **{
        "stage--{}.pending".format(filename): ("stage", filename)
        for filename in _STAGE_ARTIFACT_FILES.values()
    },
}

_IDENTITY_PAYLOAD_KEYS = {
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
}

_BOOTSTRAP_ARTIFACT_TYPE = "PLAN0014_RECONSTRUCTION_BOOTSTRAP_V1"
_RESERVATION_ARTIFACT_TYPE = "PLAN0014_RECONSTRUCTION_RESERVATION_V1"
_ATTEMPT_ARTIFACT_TYPE = "PLAN0014_RECONSTRUCTION_ATTEMPT_V1"
_COMPLETED_ARTIFACT_TYPE = "PLAN0014_RECONSTRUCTION_COMPLETED_V1"
_FAILURE_ARTIFACT_TYPE = "PLAN0014_RECONSTRUCTION_FAILURE_V1"
_ORPHANED_ARTIFACT_TYPE = "PLAN0014_RECONSTRUCTION_ORPHANED_V1"
_TERMINAL_ARTIFACT_TYPE = "PLAN0014_RECONSTRUCTION_TERMINAL_SEAL_V1"
_CONTRADICTION_ARTIFACT_TYPE = "PLAN0014_RECONSTRUCTION_CONTRADICTION_V1"


def _safe_component(value: str, label: str) -> str:
    if (
        type(value) is not str
        or _SAFE_COMPONENT.fullmatch(value) is None
        or value in (".", "..")
        or "/" in value
        or "\\" in value
    ):
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


def _exact_mapping(value: Any, label: str) -> Dict[str, Any]:
    if type(value) is not dict:
        raise EvidenceIntegrityError("{} must be an exact object".format(label))
    return value


def _exact_keys(value: Any, keys: Sequence[str], label: str) -> Dict[str, Any]:
    result = _exact_mapping(value, label)
    if set(result) != set(keys):
        raise EvidenceIntegrityError("{} has the wrong keys".format(label))
    return result


def _exact_string(value: Any, label: str) -> str:
    if type(value) is not str or not value:
        raise EvidenceIntegrityError(
            "{} must be a nonempty exact string".format(label)
        )
    return value


def _exact_hex(value: Any, length: int, label: str) -> str:
    text = _exact_string(value, label)
    pattern = _HEX40 if length == 40 else _HEX64
    if pattern.fullmatch(text) is None:
        raise EvidenceIntegrityError("{} must be lowercase hex".format(label))
    return text


def _json_copy(value: Any, label: str) -> Any:
    try:
        return load_canonical_json_bytes(canonical_json_bytes(value))
    except (TypeError, ValueError) as error:
        raise EvidenceIntegrityError("{} is not canonical JSON".format(label)) from error


def _body_ref_dict(value: Any) -> Dict[str, Any]:
    return canonical_body_ref(value).as_dict()


def _validate_body_ref(value: Any, expected: BodyRef, label: str) -> None:
    ref = _exact_keys(value, ("byte_count", "sha256"), label)
    if type(ref["byte_count"]) is not int or ref["byte_count"] < 0:
        raise EvidenceIntegrityError("{} byte count is invalid".format(label))
    _exact_hex(ref["sha256"], 64, "{} SHA-256".format(label))
    if ref != expected.as_dict():
        raise EvidenceIntegrityError("{} does not match its body".format(label))


def _artifact_identity(value: Any, label: str) -> str:
    artifact = _exact_mapping(value, label)
    return _exact_hex(artifact.get("identity"), 64, "{} identity".format(label))


def _artifact_source(value: Any, label: str) -> Tuple[str, str]:
    artifact = _exact_mapping(value, label)
    payload = _exact_mapping(artifact.get("payload"), "{} payload".format(label))
    return (
        _exact_hex(payload.get("source_commit"), 40, "{} source commit".format(label)),
        _exact_hex(payload.get("source_tree"), 40, "{} source tree".format(label)),
    )


def _open_existing_directory_at(
    parent_fd: int,
    name: str,
    *,
    allowed_modes: Optional[Tuple[int, ...]] = (
        _READABLE_EVIDENCE_DIRECTORY_MODES
    ),
) -> int:
    _safe_internal_component(name, "directory")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    try:
        fd = os.open(name, flags, dir_fd=parent_fd)
    except OSError as error:
        raise EvidenceIntegrityError(
            "evidence directory component is unavailable or unsafe"
        ) from error
    info = os.fstat(fd)
    if not stat.S_ISDIR(info.st_mode):
        os.close(fd)
        raise EvidenceIntegrityError("evidence component is not a directory")
    if allowed_modes is not None and stat.S_IMODE(info.st_mode) not in allowed_modes:
        os.close(fd)
        raise EvidenceIntegrityError(
            "evidence directory component has the wrong mode"
        )
    return fd


def _open_or_create_directory_at(
    parent_fd: int,
    name: str,
    *,
    allowed_existing_modes: Tuple[int, ...] = (
        _READABLE_EVIDENCE_DIRECTORY_MODES
    ),
) -> int:
    _safe_internal_component(name, "directory")
    created = False
    try:
        os.mkdir(name, mode=0o700, dir_fd=parent_fd)
        created = True
    except FileExistsError:
        pass
    fd = _open_existing_directory_at(
        parent_fd,
        name,
        allowed_modes=((0o700,) if created else allowed_existing_modes),
    )
    try:
        # A create-intent caller also adopts durability responsibility for an
        # existing directory.  Its creator may have crashed after mkdir but
        # before either fsync, so always persist child metadata and then its
        # parent entry before any later artifact can be published beneath it.
        os.fsync(fd)
        os.fsync(parent_fd)
    except Exception:
        os.close(fd)
        raise
    return fd


def _open_root_directory(root: Path, *, create: bool) -> int:
    absolute = Path(os.path.abspath(os.fspath(root)))
    if absolute.parent == absolute:
        raise EvidenceIntegrityError("evidence root cannot be a filesystem anchor")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    anchor_fd = os.open(absolute.anchor, flags)
    current_fd = anchor_fd
    try:
        components = absolute.parts[1:]
        for index, component in enumerate(components):
            final = index == len(components) - 1
            if final and create:
                next_fd = _open_or_create_directory_at(
                    current_fd,
                    component,
                    allowed_existing_modes=(0o700,),
                )
            else:
                next_fd = _open_existing_directory_at(
                    current_fd,
                    component,
                    allowed_modes=(
                        _READABLE_EVIDENCE_DIRECTORY_MODES if final else None
                    ),
                )
            if current_fd != anchor_fd:
                os.close(current_fd)
            current_fd = next_fd
        result = os.dup(current_fd)
    finally:
        if current_fd != anchor_fd:
            os.close(current_fd)
        os.close(anchor_fd)
    return result


def _read_regular_at(
    parent_fd: int,
    name: str,
    *,
    allowed_link_counts: Tuple[int, ...] = (1,),
    allowed_modes: Tuple[int, ...] = _READABLE_ARTIFACT_MODES,
    expected_size: Optional[int] = None,
) -> bytes:
    _safe_component(name, "artifact")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    try:
        fd = os.open(name, flags, dir_fd=parent_fd)
    except OSError as error:
        raise EvidenceIntegrityError(
            "immutable artifact is unavailable or unsafe"
        ) from error
    try:
        before = os.fstat(fd)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink not in allowed_link_counts
        ):
            raise EvidenceIntegrityError(
                "immutable artifact has an invalid type or link count"
            )
        if stat.S_IMODE(before.st_mode) not in allowed_modes:
            raise EvidenceIntegrityError("immutable artifact has the wrong mode")
        if expected_size is not None and before.st_size != expected_size:
            raise EvidenceIntegrityError("immutable artifact has the wrong size")
        if before.st_size > _MAX_ARTIFACT_BYTES:
            raise EvidenceIntegrityError("immutable artifact exceeds the byte limit")
        chunks = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(fd, min(1024 * 1024, remaining))
            if not chunk:
                raise EvidenceIntegrityError(
                    "immutable artifact was truncated while reading"
                )
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(fd, 1):
            raise EvidenceIntegrityError("immutable artifact grew while reading")
        after = os.fstat(fd)
        if (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
            before.st_nlink,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
            after.st_nlink,
        ):
            raise EvidenceIntegrityError("immutable artifact changed while reading")
        return b"".join(chunks)
    finally:
        os.close(fd)


def _entry_exists(parent_fd: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    return True


@dataclass(frozen=True)
class ReconstructionEvidenceContract:
    protocol_id: str
    protocol_root: str
    evidence_protocol_id: str
    stage_id: str
    stage_protocol_id: str
    identity_domains: Tuple[Tuple[str, bytes], ...]
    identity_payload_keys: Tuple[Tuple[str, Tuple[str, ...]], ...]

    def __post_init__(self) -> None:
        if self.protocol_id != PLAN0014_RECONSTRUCTION_PROTOCOL_ID_V1:
            raise ValueError("reconstruction protocol id is not fixed")
        _exact_hex(self.protocol_root, 64, "reconstruction protocol root")
        if (
            self.evidence_protocol_id
            != PLAN0014_RECONSTRUCTION_EVIDENCE_PROTOCOL_ID_V1
            or self.stage_id != PLAN0014_RECONSTRUCTION_STAGE_ID_V1
            or self.stage_protocol_id
            != PLAN0014_RECONSTRUCTION_STAGE_PROTOCOL_ID_V1
        ):
            raise ValueError("reconstruction evidence coordinates are not fixed")
        domains = dict(self.identity_domains)
        if set(domains) != set(_IDENTITY_PAYLOAD_KEYS):
            raise ValueError("reconstruction identity domain catalog is not exact")
        if len(domains) != len(self.identity_domains):
            raise ValueError("reconstruction identity domains repeat a kind")
        if len(set(domains.values())) != len(domains):
            raise ValueError("reconstruction identity domains must be unique")
        for value in domains.values():
            if type(value) is not bytes or not value or not value.endswith(b"\0"):
                raise ValueError("reconstruction identity domain is invalid")
        keys = dict(self.identity_payload_keys)
        if keys != _IDENTITY_PAYLOAD_KEYS:
            raise ValueError("reconstruction identity payload keys are not fixed")
        if len(keys) != len(self.identity_payload_keys):
            raise ValueError("reconstruction identity payload schemas repeat a kind")

    def identity_domain(self, kind: str) -> bytes:
        try:
            return dict(self.identity_domains)[kind]
        except KeyError as error:
            raise ValueError("unknown reconstruction identity kind") from error

    def identity_keys(self, kind: str) -> Tuple[str, ...]:
        try:
            return dict(self.identity_payload_keys)[kind]
        except KeyError as error:
            raise ValueError("unknown reconstruction identity kind") from error


def fixed_reconstruction_evidence_contract_v1() -> ReconstructionEvidenceContract:
    """Build the evidence contract from the independently authenticated protocol."""

    from . import atlas_assessment_reconstruction_protocol as protocol

    return ReconstructionEvidenceContract(
        protocol_id=protocol.PLAN0014_RECONSTRUCTION_PROTOCOL_ID_V1,
        protocol_root=protocol.PLAN0014_RECONSTRUCTION_PROTOCOL_ROOT_V1,
        evidence_protocol_id=protocol.PLAN0014_RECONSTRUCTION_EVIDENCE_PROTOCOL_ID_V1,
        stage_id=protocol.PLAN0014_RECONSTRUCTION_STAGE_ID_V1,
        stage_protocol_id=protocol.PLAN0014_RECONSTRUCTION_STAGE_PROTOCOL_ID_V1,
        identity_domains=tuple(
            (kind, protocol.identity_domain_v1(kind))
            for kind in _IDENTITY_PAYLOAD_KEYS
        ),
        identity_payload_keys=tuple(
            (kind, protocol.identity_payload_keys_v1(kind))
            for kind in _IDENTITY_PAYLOAD_KEYS
        ),
    )


class ReconstructionEvidenceStore:
    """Descriptor-bound storage for the single Plan-0014 evidence stage."""

    def __init__(self, root: os.PathLike, *, create: bool = False) -> None:
        if type(create) is not bool:
            raise TypeError("create must be an exact bool")
        self.root = Path(os.path.abspath(os.fspath(root)))
        self._create_operational = create
        self._held_lock = False
        self._root_fd = _open_root_directory(self.root, create=create)
        try:
            if create:
                for name in (_LOCKS_DIRECTORY, _PENDING_DIRECTORY):
                    fd = _open_or_create_directory_at(
                        self._root_fd,
                        name,
                        allowed_existing_modes=(0o700,),
                    )
                    os.close(fd)
                os.fsync(self._root_fd)
        except Exception:
            os.close(self._root_fd)
            self._root_fd = -1
            raise

    @classmethod
    def for_run(cls, root: os.PathLike) -> "ReconstructionEvidenceStore":
        return cls(root, create=True)

    @classmethod
    def for_recovery(cls, root: os.PathLike) -> "ReconstructionEvidenceStore":
        instance = cls(root, create=False)
        try:
            for name in (_LOCKS_DIRECTORY, _PENDING_DIRECTORY):
                fd = _open_or_create_directory_at(
                    instance._root_fd,
                    name,
                    allowed_existing_modes=(0o700,),
                )
                os.close(fd)
            os.fsync(instance._root_fd)
            instance._create_operational = True
        except Exception:
            instance.close()
            raise
        return instance

    def close(self) -> None:
        if getattr(self, "_root_fd", -1) >= 0:
            os.close(self._root_fd)
            self._root_fd = -1

    def __enter__(self) -> "ReconstructionEvidenceStore":
        return self

    def __exit__(self, _type: Any, _value: Any, _traceback: Any) -> None:
        self.close()

    def _require_open(self) -> None:
        if self._root_fd < 0:
            raise EvidenceError("reconstruction evidence store is closed")

    def _require_lock(self) -> None:
        self._require_open()
        if not self._held_lock:
            raise EvidenceLockError("evidence publication requires the held stage lock")

    @contextlib.contextmanager
    def stage_lock(self, *, blocking: bool = False) -> Iterator[None]:
        """Hold the only process-wide lock in the dedicated store."""

        self._require_open()
        if type(blocking) is not bool:
            raise TypeError("blocking must be an exact bool")
        if self._held_lock:
            raise EvidenceLockError("reconstruction evidence lock is not reentrant")
        if self._create_operational:
            locks_fd = _open_or_create_directory_at(
                self._root_fd,
                _LOCKS_DIRECTORY,
                allowed_existing_modes=(0o700,),
            )
        else:
            locks_fd = _open_existing_directory_at(
                self._root_fd,
                _LOCKS_DIRECTORY,
                allowed_modes=(0o700,),
            )
        lock_fd = -1
        lock_acquired = False
        try:
            component = PLAN0014_RECONSTRUCTION_STAGE_PROTOCOL_ID_V1 + ".lock"
            # The lock body is deliberately empty and never writable through
            # this descriptor.  Opening read-only also lets mode drift reach
            # the exact metadata check below instead of becoming an ambiguous
            # permission error first.
            flags = (
                os.O_RDONLY
                | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_NONBLOCK", 0)
            )
            if self._create_operational:
                flags |= os.O_CREAT
            try:
                lock_fd = os.open(component, flags, 0o600, dir_fd=locks_fd)
            except OSError as error:
                raise EvidenceLockError(
                    "reconstruction evidence lock is unavailable"
                ) from error
            info = os.fstat(lock_fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_size != 0
            ):
                raise EvidenceIntegrityError(
                    "reconstruction stage lock must be empty, mode 0600, "
                    "singly linked, and regular"
                )
            operation = fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB)
            try:
                fcntl.flock(lock_fd, operation)
            except BlockingIOError as error:
                raise EvidenceLockError(
                    "reconstruction evidence lock is already held"
                ) from error
            lock_acquired = True
            self._held_lock = True
            try:
                yield
            finally:
                self._held_lock = False
        finally:
            if lock_fd >= 0:
                try:
                    if lock_acquired:
                        fcntl.flock(lock_fd, fcntl.LOCK_UN)
                finally:
                    os.close(lock_fd)
            os.close(locks_fd)

    @contextlib.contextmanager
    def _pending_fd(self, *, create: bool) -> Iterator[int]:
        self._require_open()
        fd = (
            _open_or_create_directory_at(
                self._root_fd,
                _PENDING_DIRECTORY,
                allowed_existing_modes=(0o700,),
            )
            if create
            else _open_existing_directory_at(
                self._root_fd,
                _PENDING_DIRECTORY,
                allowed_modes=(0o700,),
            )
        )
        try:
            yield fd
        finally:
            os.close(fd)

    @contextlib.contextmanager
    def _stage_fd(self, *, create: bool) -> Iterator[int]:
        self._require_open()
        stages_fd = (
            _open_or_create_directory_at(self._root_fd, _STAGES_DIRECTORY)
            if create
            else _open_existing_directory_at(self._root_fd, _STAGES_DIRECTORY)
        )
        try:
            stage_fd = (
                _open_or_create_directory_at(
                    stages_fd, PLAN0014_RECONSTRUCTION_STAGE_PROTOCOL_ID_V1
                )
                if create
                else _open_existing_directory_at(
                    stages_fd, PLAN0014_RECONSTRUCTION_STAGE_PROTOCOL_ID_V1
                )
            )
            try:
                yield stage_fd
            finally:
                os.close(stage_fd)
        finally:
            os.close(stages_fd)

    @contextlib.contextmanager
    def _target_fd(self, scope: str, *, create: bool) -> Iterator[int]:
        if scope == "root":
            yield self._root_fd
            return
        if scope != "stage":
            raise ValueError("unknown reconstruction evidence publication scope")
        with self._stage_fd(create=create) as stage_fd:
            yield stage_fd

    def _reconcile_pending_target(
        self,
        pending_fd: int,
        pending_name: str,
        target_fd: int,
        final_name: str,
    ) -> None:
        pending_exists = _entry_exists(pending_fd, pending_name)
        final_exists = _entry_exists(target_fd, final_name)
        if not pending_exists:
            return
        if not final_exists:
            try:
                info = os.stat(
                    pending_name, dir_fd=pending_fd, follow_symlinks=False
                )
            except OSError as error:
                raise EvidenceIntegrityError(
                    "pending publication is unavailable or unsafe"
                ) from error
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or stat.S_IMODE(info.st_mode) != 0o400
            ):
                raise EvidenceIntegrityError(
                    "unpublished pending artifact has invalid mode, type, "
                    "or link count"
                )
            os.unlink(pending_name, dir_fd=pending_fd)
            os.fsync(pending_fd)
            return

        flags = (
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0)
        )
        pending_body_fd = final_body_fd = -1
        try:
            pending_body_fd = os.open(pending_name, flags, dir_fd=pending_fd)
            final_body_fd = os.open(final_name, flags, dir_fd=target_fd)
            pending_info = os.fstat(pending_body_fd)
            final_info = os.fstat(final_body_fd)
            if (
                not stat.S_ISREG(pending_info.st_mode)
                or not stat.S_ISREG(final_info.st_mode)
                or stat.S_IMODE(pending_info.st_mode) != 0o400
                or stat.S_IMODE(final_info.st_mode) != 0o400
                or pending_info.st_nlink != 2
                or final_info.st_nlink != 2
                or (pending_info.st_dev, pending_info.st_ino)
                != (final_info.st_dev, final_info.st_ino)
            ):
                raise EvidenceIntegrityError(
                    "pending and final publication links are inconsistent"
                )
        except OSError as error:
            raise EvidenceIntegrityError(
                "pending publication links are unavailable or unsafe"
            ) from error
        finally:
            if pending_body_fd >= 0:
                os.close(pending_body_fd)
            if final_body_fd >= 0:
                os.close(final_body_fd)
        pending_raw = _read_regular_at(
            pending_fd,
            pending_name,
            allowed_link_counts=(2,),
            allowed_modes=(0o400,),
        )
        final_raw = _read_regular_at(
            target_fd, final_name, allowed_link_counts=(2,)
        )
        if pending_raw != final_raw:
            raise EvidenceIntegrityError(
                "pending and final publication bytes are inconsistent"
            )
        try:
            load_canonical_json_bytes(final_raw)
        except (TypeError, ValueError) as error:
            raise EvidenceIntegrityError(
                "linked pending publication is not canonical JSON"
            ) from error
        os.unlink(pending_name, dir_fd=pending_fd)
        os.fsync(pending_fd)
        os.fsync(target_fd)
        _read_regular_at(target_fd, final_name)

    def reconcile_pending_publications(self) -> None:
        """Finish or discard only recognized interrupted atomic publications."""

        self._require_lock()
        with self._pending_fd(create=self._create_operational) as pending_fd:
            observed = set(os.listdir(pending_fd))
            unknown = observed - set(_PENDING_TARGETS)
            if unknown:
                raise EvidenceIntegrityError(
                    "pending publication directory contains a noncatalog path"
                )
            for pending_name in sorted(observed):
                scope, final_name = _PENDING_TARGETS[pending_name]
                try:
                    with self._target_fd(scope, create=False) as target_fd:
                        self._reconcile_pending_target(
                            pending_fd, pending_name, target_fd, final_name
                        )
                except EvidenceIntegrityError as error:
                    if (
                        scope == "stage"
                        and isinstance(error.__cause__, FileNotFoundError)
                    ):
                        raise EvidenceIntegrityError(
                            "stage pending artifact exists without its fixed directory"
                        ) from error
                    raise

    def _publish_canonical(
        self,
        scope: str,
        final_name: str,
        pending_name: str,
        raw: bytes,
        *,
        idempotent: bool,
    ) -> BodyRef:
        self._require_lock()
        if type(raw) is not bytes:
            raise TypeError("immutable artifact body must be exact bytes")
        if len(raw) > _MAX_ARTIFACT_BYTES:
            raise ValueError("immutable artifact exceeds the byte limit")
        load_canonical_json_bytes(raw)
        with self._pending_fd(create=True) as pending_fd, self._target_fd(
            scope, create=True
        ) as target_fd:
            self._reconcile_pending_target(
                pending_fd, pending_name, target_fd, final_name
            )
            if _entry_exists(target_fd, final_name):
                existing = _read_regular_at(target_fd, final_name)
                if idempotent and existing == raw:
                    return BodyRef(hashlib.sha256(raw).hexdigest(), len(raw))
                raise EvidenceConflictError("immutable artifact already exists")

            flags = (
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | getattr(os, "O_NOFOLLOW", 0)
            )
            try:
                pending_body_fd = os.open(
                    pending_name, flags, 0o400, dir_fd=pending_fd
                )
            except OSError as error:
                raise EvidenceConflictError(
                    "pending publication slot already exists"
                ) from error
            try:
                view = memoryview(raw)
                while view:
                    written = os.write(pending_body_fd, view)
                    if written <= 0:
                        raise OSError(errno.EIO, "short immutable evidence write")
                    view = view[written:]
                os.fsync(pending_body_fd)
                os.fchmod(pending_body_fd, 0o400)
                os.fsync(pending_body_fd)
            finally:
                os.close(pending_body_fd)
            try:
                os.link(
                    pending_name,
                    final_name,
                    src_dir_fd=pending_fd,
                    dst_dir_fd=target_fd,
                    follow_symlinks=False,
                )
            except FileExistsError as error:
                try:
                    os.unlink(pending_name, dir_fd=pending_fd)
                    os.fsync(pending_fd)
                except OSError as cleanup_error:
                    raise EvidenceIntegrityError(
                        "failed to remove an unpublished pending artifact"
                    ) from cleanup_error
                raise EvidenceConflictError(
                    "immutable artifact already exists"
                ) from error
            os.fsync(target_fd)
            os.unlink(pending_name, dir_fd=pending_fd)
            os.fsync(pending_fd)
            os.fsync(target_fd)
            observed = _read_regular_at(target_fd, final_name)
            if observed != raw:
                raise EvidenceIntegrityError(
                    "published immutable artifact bytes changed"
                )
        return BodyRef(hashlib.sha256(raw).hexdigest(), len(raw))

    def publish_bootstrap(self, value: Any) -> BodyRef:
        raw = canonical_json_bytes(value)
        return self._publish_canonical(
            "root",
            _BOOTSTRAP_FILE,
            "root--bootstrap.json.pending",
            raw,
            idempotent=True,
        )

    def read_bootstrap(self) -> Dict[str, Any]:
        self._require_open()
        try:
            value = load_canonical_json_bytes(
                _read_regular_at(self._root_fd, _BOOTSTRAP_FILE)
            )
        except (TypeError, ValueError) as error:
            raise EvidenceIntegrityError(
                "reconstruction bootstrap is not canonical"
            ) from error
        return _exact_mapping(value, "reconstruction bootstrap")

    def bootstrap_exists(self) -> bool:
        self._require_open()
        if not _entry_exists(self._root_fd, _BOOTSTRAP_FILE):
            return False
        self.read_bootstrap()
        return True

    def publish_stage_json(self, artifact: str, value: Any) -> BodyRef:
        if artifact not in _STAGE_ARTIFACT_FILES:
            raise ValueError("artifact is not in the fixed reconstruction catalog")
        filename = _STAGE_ARTIFACT_FILES[artifact]
        return self._publish_canonical(
            "stage",
            filename,
            "stage--{}.pending".format(filename),
            canonical_json_bytes(value),
            idempotent=False,
        )

    def read_stage_json(self, artifact: str) -> Any:
        if artifact not in _STAGE_ARTIFACT_FILES:
            raise ValueError("artifact is not in the fixed reconstruction catalog")
        with self._stage_fd(create=False) as stage_fd:
            try:
                return load_canonical_json_bytes(
                    _read_regular_at(stage_fd, _STAGE_ARTIFACT_FILES[artifact])
                )
            except (TypeError, ValueError) as error:
                raise EvidenceIntegrityError(
                    "reconstruction stage artifact is not canonical"
                ) from error

    def stage_artifact_exists(self, artifact: str) -> bool:
        if artifact not in _STAGE_ARTIFACT_FILES:
            raise ValueError("artifact is not in the fixed reconstruction catalog")
        try:
            self.read_stage_json(artifact)
            return True
        except EvidenceIntegrityError as error:
            if isinstance(error.__cause__, FileNotFoundError):
                return False
            raise

    def stage_entry_exists(self) -> bool:
        self._require_open()
        if not _entry_exists(self._root_fd, _STAGES_DIRECTORY):
            return False
        stages_fd = _open_existing_directory_at(self._root_fd, _STAGES_DIRECTORY)
        try:
            return _entry_exists(
                stages_fd, PLAN0014_RECONSTRUCTION_STAGE_PROTOCOL_ID_V1
            )
        finally:
            os.close(stages_fd)

    def publish_contradiction(self, value: Any) -> BodyRef:
        return self._publish_canonical(
            "root",
            _CONTRADICTION_FILE,
            "root--contradiction.json.pending",
            canonical_json_bytes(value),
            idempotent=True,
        )

    def read_contradiction(self) -> Any:
        self._require_open()
        try:
            return load_canonical_json_bytes(
                _read_regular_at(self._root_fd, _CONTRADICTION_FILE)
            )
        except (TypeError, ValueError) as error:
            raise EvidenceIntegrityError(
                "reconstruction contradiction is not canonical"
            ) from error

    def contradiction_exists(self) -> bool:
        self._require_open()
        if not _entry_exists(self._root_fd, _CONTRADICTION_FILE):
            return False
        self.read_contradiction()
        return True

    def scan_fixed_catalog(self) -> Dict[str, Optional[BodyRef]]:
        """Reject every unknown path and report the fixed evidence bodies."""

        self._require_open()
        root_entries = set(os.listdir(self._root_fd))
        if root_entries - _ROOT_CATALOG:
            raise EvidenceIntegrityError(
                "reconstruction evidence root contains a noncatalog path"
            )
        if _LOCKS_DIRECTORY in root_entries:
            locks_fd = _open_existing_directory_at(
                self._root_fd,
                _LOCKS_DIRECTORY,
                allowed_modes=(0o700,),
            )
            try:
                allowed_lock = (
                    PLAN0014_RECONSTRUCTION_STAGE_PROTOCOL_ID_V1 + ".lock"
                )
                if set(os.listdir(locks_fd)) - {allowed_lock}:
                    raise EvidenceIntegrityError(
                        "reconstruction lock directory contains a noncatalog path"
                    )
                if _entry_exists(locks_fd, allowed_lock):
                    _read_regular_at(
                        locks_fd,
                        allowed_lock,
                        allowed_modes=(0o600,),
                        expected_size=0,
                    )
            finally:
                os.close(locks_fd)
        if _PENDING_DIRECTORY in root_entries:
            pending_fd = _open_existing_directory_at(
                self._root_fd,
                _PENDING_DIRECTORY,
                allowed_modes=(0o700,),
            )
            try:
                if set(os.listdir(pending_fd)) - set(_PENDING_TARGETS):
                    raise EvidenceIntegrityError(
                        "pending publication directory contains a noncatalog path"
                    )
            finally:
                os.close(pending_fd)
        result: Dict[str, Optional[BodyRef]] = {
            "bootstrap": None,
            "contradiction": None,
            **{artifact: None for artifact in _STAGE_ARTIFACT_FILES},
        }
        if _BOOTSTRAP_FILE in root_entries:
            raw = _read_regular_at(self._root_fd, _BOOTSTRAP_FILE)
            load_canonical_json_bytes(raw)
            result["bootstrap"] = BodyRef(hashlib.sha256(raw).hexdigest(), len(raw))
        if _CONTRADICTION_FILE in root_entries:
            raw = _read_regular_at(self._root_fd, _CONTRADICTION_FILE)
            load_canonical_json_bytes(raw)
            result["contradiction"] = BodyRef(
                hashlib.sha256(raw).hexdigest(), len(raw)
            )
        if _STAGES_DIRECTORY not in root_entries:
            return result
        stages_fd = _open_existing_directory_at(self._root_fd, _STAGES_DIRECTORY)
        try:
            entries = set(os.listdir(stages_fd))
            allowed_stage = PLAN0014_RECONSTRUCTION_STAGE_PROTOCOL_ID_V1
            if entries - {allowed_stage}:
                raise EvidenceIntegrityError(
                    "reconstruction stages directory contains a noncatalog path"
                )
            if allowed_stage not in entries:
                return result
            stage_fd = _open_existing_directory_at(stages_fd, allowed_stage)
            try:
                stage_entries = set(os.listdir(stage_fd))
                allowed_files = set(_STAGE_ARTIFACT_FILES.values())
                if stage_entries - allowed_files:
                    raise EvidenceIntegrityError(
                        "reconstruction stage contains a noncatalog path"
                    )
                by_file = {
                    filename: artifact
                    for artifact, filename in _STAGE_ARTIFACT_FILES.items()
                }
                for filename in stage_entries:
                    raw = _read_regular_at(stage_fd, filename)
                    load_canonical_json_bytes(raw)
                    result[by_file[filename]] = BodyRef(
                        hashlib.sha256(raw).hexdigest(), len(raw)
                    )
            finally:
                os.close(stage_fd)
        finally:
            os.close(stages_fd)
        return result


@contextlib.contextmanager
def open_recovery_store_v1(
    root: os.PathLike,
) -> Iterator[Optional[ReconstructionEvidenceStore]]:
    """Open an existing store, yielding ``None`` when no root exists.

    The missing-root case performs no mkdir, lock creation, or artifact write.
    """

    try:
        store = ReconstructionEvidenceStore.for_recovery(root)
    except EvidenceIntegrityError as error:
        if isinstance(error.__cause__, FileNotFoundError):
            yield None
            return
        raise
    try:
        yield store
    finally:
        store.close()


def _fixed_protocol_module() -> Any:
    from . import atlas_assessment_reconstruction_protocol as protocol

    return protocol


def _validate_rooted_reference(
    value: Any,
    *,
    kind: str,
    expected_artifact_type: Optional[str],
    label: str,
) -> Dict[str, Any]:
    protocol = _fixed_protocol_module()
    envelope = _exact_keys(
        value, ("artifact_type", "identity", "payload"), label
    )
    artifact_type = _exact_string(
        envelope["artifact_type"], "{} artifact type".format(label)
    )
    if expected_artifact_type is not None and artifact_type != expected_artifact_type:
        raise EvidenceIntegrityError("{} artifact type drifted".format(label))
    identity = _exact_hex(envelope["identity"], 64, "{} identity".format(label))
    payload = _exact_keys(
        envelope["payload"], protocol.identity_payload_keys_v1(kind), "{} payload".format(label)
    )
    if identity != domain_identity(protocol.identity_domain_v1(kind), payload):
        raise EvidenceIntegrityError("{} identity does not reconstruct".format(label))
    return _json_copy(envelope, label)


def build_bootstrap_v1(
    protocol_value: Any,
    active_plan_bytes: bytes,
    production_closure: Any,
    source_binding: Any,
) -> Dict[str, Any]:
    """Build one atomic bootstrap from four already available inputs."""

    protocol_module = _fixed_protocol_module()
    protocol = protocol_module.validate_plan0014_assessment_reconstruction_protocol_v1(
        protocol_value
    )
    if type(active_plan_bytes) is not bytes:
        raise TypeError("active plan bytes must be exact bytes")
    try:
        active_plan_bytes.decode("utf-8", "strict")
    except UnicodeDecodeError as error:
        raise EvidenceIntegrityError("active plan bytes must be valid UTF-8") from error
    closure = _validate_rooted_reference(
        production_closure,
        kind="production_closure_root",
        expected_artifact_type="PLAN0014_RECONSTRUCTION_PRODUCTION_CLOSURE_V1",
        label="production closure",
    )
    binding = _validate_rooted_reference(
        source_binding,
        kind="source_binding_root",
        expected_artifact_type="PLAN0014_RECONSTRUCTION_SOURCE_BINDING_V1",
        label="source binding",
    )
    active_plan_ref = BodyRef(
        hashlib.sha256(active_plan_bytes).hexdigest(), len(active_plan_bytes)
    ).as_dict()
    closure_payload = closure["payload"]
    if closure_payload["active_plan_ref"] != active_plan_ref:
        raise EvidenceIntegrityError(
            "production closure active-plan reference does not match"
        )
    if closure_payload["stage_id"] != PLAN0014_RECONSTRUCTION_STAGE_ID_V1:
        raise EvidenceIntegrityError("production closure belongs to another stage")
    repair = _exact_mapping(
        _exact_mapping(protocol.get("source_chain"), "protocol source chain").get(
            "repair_checkpoint"
        ),
        "protocol repair checkpoint",
    )
    repair_commit = _exact_hex(
        repair.get("commit"), 40, "protocol repair checkpoint commit"
    )
    repair_tree = _exact_hex(
        repair.get("tree"), 40, "protocol repair checkpoint tree"
    )
    if (
        closure_payload["repair_checkpoint_commit"] != repair_commit
        or closure_payload["repair_checkpoint_tree"] != repair_tree
    ):
        raise EvidenceIntegrityError(
            "production closure repair checkpoint does not match protocol"
        )
    source_commit, source_tree = _artifact_source(closure, "production closure")
    protocol_ref = canonical_body_ref(protocol).as_dict()
    payload = {
        "active_plan_ref": active_plan_ref,
        "evidence_protocol_id": PLAN0014_RECONSTRUCTION_EVIDENCE_PROTOCOL_ID_V1,
        "production_closure_root": closure["identity"],
        "protocol_id": PLAN0014_RECONSTRUCTION_PROTOCOL_ID_V1,
        "protocol_ref": protocol_ref,
        "protocol_root": protocol_module.PLAN0014_RECONSTRUCTION_PROTOCOL_ROOT_V1,
        "repair_checkpoint_commit": repair_commit,
        "repair_checkpoint_tree": repair_tree,
        "source_binding_root": binding["identity"],
        "source_commit": source_commit,
        "source_tree": source_tree,
        "stage_id": PLAN0014_RECONSTRUCTION_STAGE_ID_V1,
        "stage_protocol_id": PLAN0014_RECONSTRUCTION_STAGE_PROTOCOL_ID_V1,
    }
    if tuple(payload) != protocol_module.identity_payload_keys_v1("bootstrap_root"):
        raise EvidenceIntegrityError("bootstrap payload schema drifted")
    references = {
        "active_plan_base64": base64.b64encode(active_plan_bytes).decode("ascii"),
        "production_closure": closure,
        "protocol": protocol,
        "source_binding": binding,
    }
    return {
        "artifact_type": _BOOTSTRAP_ARTIFACT_TYPE,
        "identity": domain_identity(
            protocol_module.identity_domain_v1("bootstrap_root"), payload
        ),
        "payload": _json_copy(payload, "bootstrap payload"),
        "references": _json_copy(references, "bootstrap references"),
    }


def validate_bootstrap_v1(value: Any) -> Dict[str, Any]:
    """Authenticate every bootstrap cross-reference without filesystem access."""

    protocol_module = _fixed_protocol_module()
    envelope = _exact_keys(
        value,
        ("artifact_type", "identity", "payload", "references"),
        "reconstruction bootstrap",
    )
    if envelope["artifact_type"] != _BOOTSTRAP_ARTIFACT_TYPE:
        raise EvidenceIntegrityError("reconstruction bootstrap artifact type drifted")
    identity = _exact_hex(
        envelope["identity"], 64, "reconstruction bootstrap identity"
    )
    payload = _exact_keys(
        envelope["payload"],
        protocol_module.identity_payload_keys_v1("bootstrap_root"),
        "reconstruction bootstrap payload",
    )
    if identity != domain_identity(
        protocol_module.identity_domain_v1("bootstrap_root"), payload
    ):
        raise EvidenceIntegrityError("reconstruction bootstrap identity does not reconstruct")
    references = _exact_keys(
        envelope["references"],
        ("active_plan_base64", "production_closure", "protocol", "source_binding"),
        "reconstruction bootstrap references",
    )
    encoded_plan = _exact_string(
        references["active_plan_base64"], "active plan base64"
    )
    try:
        active_plan_bytes = base64.b64decode(
            encoded_plan.encode("ascii", "strict"), validate=True
        )
    except (UnicodeEncodeError, ValueError) as error:
        raise EvidenceIntegrityError("active plan base64 is invalid") from error
    if base64.b64encode(active_plan_bytes).decode("ascii") != encoded_plan:
        raise EvidenceIntegrityError("active plan base64 is not canonical")
    _validate_body_ref(
        payload["active_plan_ref"],
        BodyRef(hashlib.sha256(active_plan_bytes).hexdigest(), len(active_plan_bytes)),
        "active plan reference",
    )
    protocol = protocol_module.validate_plan0014_assessment_reconstruction_protocol_v1(
        references["protocol"]
    )
    _validate_body_ref(
        payload["protocol_ref"], canonical_body_ref(protocol), "protocol reference"
    )
    closure = _validate_rooted_reference(
        references["production_closure"],
        kind="production_closure_root",
        expected_artifact_type="PLAN0014_RECONSTRUCTION_PRODUCTION_CLOSURE_V1",
        label="production closure",
    )
    binding = _validate_rooted_reference(
        references["source_binding"],
        kind="source_binding_root",
        expected_artifact_type="PLAN0014_RECONSTRUCTION_SOURCE_BINDING_V1",
        label="source binding",
    )
    expected = build_bootstrap_v1(
        protocol, active_plan_bytes, closure, binding
    )
    if canonical_json_bytes(expected) != canonical_json_bytes(envelope):
        raise EvidenceIntegrityError(
            "reconstruction bootstrap cross-references do not reconstruct"
        )
    return _json_copy(envelope, "validated reconstruction bootstrap")


def _make_identity_envelope(
    contract: ReconstructionEvidenceContract,
    kind: str,
    artifact_type: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    if tuple(payload) != contract.identity_keys(kind):
        raise EvidenceIntegrityError("{} payload schema drifted".format(kind))
    return {
        "artifact_type": artifact_type,
        "identity": domain_identity(contract.identity_domain(kind), payload),
        "payload": _json_copy(payload, "{} payload".format(kind)),
    }


def _validate_identity_envelope(
    contract: ReconstructionEvidenceContract,
    value: Any,
    kind: str,
    artifact_type: str,
) -> Dict[str, Any]:
    envelope = _exact_keys(
        value, ("artifact_type", "identity", "payload"), artifact_type
    )
    if envelope["artifact_type"] != artifact_type:
        raise EvidenceIntegrityError("{} artifact type drifted".format(artifact_type))
    identity = _exact_hex(envelope["identity"], 64, "{} identity".format(kind))
    payload = _exact_keys(
        envelope["payload"], contract.identity_keys(kind), "{} payload".format(kind)
    )
    if identity != domain_identity(contract.identity_domain(kind), payload):
        raise EvidenceIntegrityError("{} identity does not reconstruct".format(kind))
    return _json_copy(envelope, artifact_type)


def _require_contract_bootstrap(
    contract: ReconstructionEvidenceContract, bootstrap_value: Any
) -> Dict[str, Any]:
    if not isinstance(contract, ReconstructionEvidenceContract):
        raise TypeError("contract must be a ReconstructionEvidenceContract")
    bootstrap = validate_bootstrap_v1(bootstrap_value)
    payload = bootstrap["payload"]
    expected = {
        "evidence_protocol_id": contract.evidence_protocol_id,
        "protocol_id": contract.protocol_id,
        "protocol_root": contract.protocol_root,
        "stage_id": contract.stage_id,
        "stage_protocol_id": contract.stage_protocol_id,
    }
    for key, value in expected.items():
        if payload[key] != value:
            raise EvidenceIntegrityError(
                "bootstrap {} differs from the evidence contract".format(key)
            )
    return bootstrap


def build_reservation_v1(
    contract: ReconstructionEvidenceContract, bootstrap_value: Any
) -> Dict[str, Any]:
    bootstrap = _require_contract_bootstrap(contract, bootstrap_value)
    source = bootstrap["payload"]
    payload = {
        "bootstrap_root": bootstrap["identity"],
        "evidence_protocol_id": contract.evidence_protocol_id,
        "production_closure_root": source["production_closure_root"],
        "protocol_id": contract.protocol_id,
        "protocol_root": contract.protocol_root,
        "source_binding_root": source["source_binding_root"],
        "stage_id": contract.stage_id,
        "stage_protocol_id": contract.stage_protocol_id,
    }
    return _make_identity_envelope(
        contract, "reservation_id", _RESERVATION_ARTIFACT_TYPE, payload
    )


def _validate_reservation_v1(
    contract: ReconstructionEvidenceContract,
    bootstrap_value: Any,
    reservation_value: Any,
) -> Dict[str, Any]:
    reservation = _validate_identity_envelope(
        contract,
        reservation_value,
        "reservation_id",
        _RESERVATION_ARTIFACT_TYPE,
    )
    expected = build_reservation_v1(contract, bootstrap_value)
    if canonical_json_bytes(reservation) != canonical_json_bytes(expected):
        raise EvidenceIntegrityError("reservation does not reconstruct from bootstrap")
    return reservation


def build_attempt_v1(
    contract: ReconstructionEvidenceContract,
    bootstrap_value: Any,
    reservation_value: Any,
) -> Dict[str, Any]:
    bootstrap = _require_contract_bootstrap(contract, bootstrap_value)
    reservation = _validate_reservation_v1(
        contract, bootstrap, reservation_value
    )
    source = bootstrap["payload"]
    payload = {
        "attempt_index": 0,
        "production_closure_root": source["production_closure_root"],
        "reservation_id": reservation["identity"],
        "source_commit": source["source_commit"],
        "source_tree": source["source_tree"],
    }
    return _make_identity_envelope(
        contract, "attempt_id", _ATTEMPT_ARTIFACT_TYPE, payload
    )


def _validate_attempt_v1(
    contract: ReconstructionEvidenceContract,
    bootstrap_value: Any,
    reservation_value: Any,
    attempt_value: Any,
) -> Dict[str, Any]:
    attempt = _validate_identity_envelope(
        contract, attempt_value, "attempt_id", _ATTEMPT_ARTIFACT_TYPE
    )
    expected = build_attempt_v1(
        contract, bootstrap_value, reservation_value
    )
    if canonical_json_bytes(attempt) != canonical_json_bytes(expected):
        raise EvidenceIntegrityError("attempt does not reconstruct from reservation")
    return attempt


def build_completed_v1(
    contract: ReconstructionEvidenceContract,
    bootstrap_value: Any,
    reservation_value: Any,
    attempt_value: Any,
    result: Any,
) -> Dict[str, Any]:
    bootstrap = _require_contract_bootstrap(contract, bootstrap_value)
    reservation = _validate_reservation_v1(contract, bootstrap, reservation_value)
    attempt = _validate_attempt_v1(
        contract, bootstrap, reservation, attempt_value
    )
    result_value = _exact_keys(
        result,
        ("inner_report", "outer_attestation"),
        "reconstruction completed result",
    )
    body = {
        "artifact_type": _COMPLETED_ARTIFACT_TYPE,
        "attempt_id": attempt["identity"],
        "reservation_id": reservation["identity"],
        "result": _json_copy(result_value, "reconstruction completed result"),
        "stage_id": contract.stage_id,
        "stage_protocol_id": contract.stage_protocol_id,
    }
    canonical_json_bytes(body)
    return body


def _validate_failure_value(value: Any) -> Dict[str, Any]:
    failure = _exact_keys(
        value,
        ("exception_module", "exception_type", "kind", "message"),
        "reconstruction failure value",
    )
    if failure["kind"] != "RECONSTRUCTION_STAGE_EXCEPTION":
        raise EvidenceIntegrityError("reconstruction failure kind drifted")
    _exact_string(failure["exception_module"], "failure exception module")
    _exact_string(failure["exception_type"], "failure exception type")
    if type(failure["message"]) is not str:
        raise EvidenceIntegrityError("failure message must be an exact string")
    return _json_copy(failure, "reconstruction failure value")


def failure_value_v1(error: BaseException) -> Dict[str, Any]:
    if not isinstance(error, BaseException):
        raise TypeError("error must be a BaseException")
    return {
        "exception_module": type(error).__module__,
        "exception_type": type(error).__qualname__,
        "kind": "RECONSTRUCTION_STAGE_EXCEPTION",
        "message": str(error),
    }


def build_failure_v1(
    contract: ReconstructionEvidenceContract,
    bootstrap_value: Any,
    reservation_value: Any,
    attempt_value: Any,
    failure_value: Any,
) -> Dict[str, Any]:
    bootstrap = _require_contract_bootstrap(contract, bootstrap_value)
    reservation = _validate_reservation_v1(contract, bootstrap, reservation_value)
    attempt = _validate_attempt_v1(
        contract, bootstrap, reservation, attempt_value
    )
    body = {
        "artifact_type": _FAILURE_ARTIFACT_TYPE,
        "attempt_id": attempt["identity"],
        "failure": _validate_failure_value(failure_value),
        "reservation_id": reservation["identity"],
        "stage_id": contract.stage_id,
        "stage_protocol_id": contract.stage_protocol_id,
    }
    canonical_json_bytes(body)
    return body


def build_orphaned_v1(
    contract: ReconstructionEvidenceContract,
    bootstrap_value: Any,
    reservation_value: Any,
    attempt_value: Optional[Any],
) -> Dict[str, Any]:
    bootstrap = _require_contract_bootstrap(contract, bootstrap_value)
    reservation = _validate_reservation_v1(contract, bootstrap, reservation_value)
    if attempt_value is None:
        attempt = None
        reason = "RESERVATION_WITHOUT_ATTEMPT"
    else:
        attempt = _validate_attempt_v1(
            contract, bootstrap, reservation, attempt_value
        )
        reason = "ATTEMPT_WITHOUT_LIFECYCLE_BODY"
    payload = {
        "attempt_id_or_null": None if attempt is None else attempt["identity"],
        "orphan_reason": reason,
        "reservation_id": reservation["identity"],
        "stage_id": contract.stage_id,
        "stage_protocol_id": contract.stage_protocol_id,
    }
    return _make_identity_envelope(
        contract, "orphaned_id", _ORPHANED_ARTIFACT_TYPE, payload
    )


def _validate_orphaned_v1(
    contract: ReconstructionEvidenceContract,
    bootstrap_value: Any,
    reservation_value: Any,
    attempt_value: Optional[Any],
    orphaned_value: Any,
) -> Dict[str, Any]:
    orphaned = _validate_identity_envelope(
        contract, orphaned_value, "orphaned_id", _ORPHANED_ARTIFACT_TYPE
    )
    expected = build_orphaned_v1(
        contract, bootstrap_value, reservation_value, attempt_value
    )
    if canonical_json_bytes(orphaned) != canonical_json_bytes(expected):
        raise EvidenceIntegrityError("orphaned artifact does not reconstruct")
    return orphaned


def build_terminal_seal_v1(
    contract: ReconstructionEvidenceContract,
    bootstrap_value: Any,
    lifecycle: str,
    *,
    reservation: Any,
    attempt: Optional[Any] = None,
    completed: Optional[Any] = None,
    failure: Optional[Any] = None,
    orphaned: Optional[Any] = None,
) -> Dict[str, Any]:
    bootstrap = _require_contract_bootstrap(contract, bootstrap_value)
    reservation_value = _validate_reservation_v1(
        contract, bootstrap, reservation
    )
    attempt_value = None
    if attempt is not None:
        attempt_value = _validate_attempt_v1(
            contract, bootstrap, reservation_value, attempt
        )
    completed_root = failure_root = orphaned_id = None
    if lifecycle == "COMPLETED":
        if attempt_value is None or failure is not None or orphaned is not None:
            raise EvidenceIntegrityError("COMPLETED terminal has incompatible artifacts")
        completed_value = _exact_keys(
            completed,
            (
                "artifact_type",
                "attempt_id",
                "reservation_id",
                "result",
                "stage_id",
                "stage_protocol_id",
            ),
            "completed body",
        )
        expected_completed = build_completed_v1(
            contract,
            bootstrap,
            reservation_value,
            attempt_value,
            completed_value["result"],
        )
        if canonical_json_bytes(completed_value) != canonical_json_bytes(
            expected_completed
        ):
            raise EvidenceIntegrityError("completed body does not reconstruct")
        completed_root = canonical_body_ref(completed_value).sha256
    elif lifecycle == "FAILED":
        if attempt_value is None or completed is not None or orphaned is not None:
            raise EvidenceIntegrityError("FAILED terminal has incompatible artifacts")
        failure_body = _exact_keys(
            failure,
            (
                "artifact_type",
                "attempt_id",
                "failure",
                "reservation_id",
                "stage_id",
                "stage_protocol_id",
            ),
            "failure body",
        )
        expected_failure = build_failure_v1(
            contract,
            bootstrap,
            reservation_value,
            attempt_value,
            failure_body["failure"],
        )
        if canonical_json_bytes(failure_body) != canonical_json_bytes(
            expected_failure
        ):
            raise EvidenceIntegrityError("failure body does not reconstruct")
        failure_root = canonical_body_ref(failure_body).sha256
    elif lifecycle == "ORPHANED":
        if completed is not None or failure is not None:
            raise EvidenceIntegrityError("ORPHANED terminal has incompatible artifacts")
        orphaned_value = _validate_orphaned_v1(
            contract,
            bootstrap,
            reservation_value,
            attempt_value,
            orphaned,
        )
        orphaned_id = orphaned_value["identity"]
    else:
        raise ValueError("unknown reconstruction terminal lifecycle")
    payload = {
        "attempt_id_or_null": (
            None if attempt_value is None else attempt_value["identity"]
        ),
        "completed_root_or_null": completed_root,
        "failure_root_or_null": failure_root,
        "lifecycle": lifecycle,
        "orphaned_id_or_null": orphaned_id,
        "reservation_id_or_null": reservation_value["identity"],
        "stage_id": contract.stage_id,
        "stage_protocol_id": contract.stage_protocol_id,
    }
    return _make_identity_envelope(
        contract, "terminal_seal", _TERMINAL_ARTIFACT_TYPE, payload
    )


@dataclass(frozen=True)
class ReconstructionChainSnapshot:
    reservation: Optional[Dict[str, Any]] = None
    attempt: Optional[Dict[str, Any]] = None
    completed: Optional[Dict[str, Any]] = None
    failure: Optional[Dict[str, Any]] = None
    orphaned: Optional[Dict[str, Any]] = None
    terminal_seal: Optional[Dict[str, Any]] = None


def load_chain_snapshot_v1(
    store: ReconstructionEvidenceStore,
) -> ReconstructionChainSnapshot:
    if not isinstance(store, ReconstructionEvidenceStore):
        raise TypeError("store must be a ReconstructionEvidenceStore")

    def optional(artifact: str) -> Optional[Any]:
        try:
            return store.read_stage_json(artifact)
        except EvidenceIntegrityError as error:
            if isinstance(error.__cause__, FileNotFoundError):
                return None
            raise

    return ReconstructionChainSnapshot(
        reservation=optional("reservation"),
        attempt=optional("attempt"),
        completed=optional("completed"),
        failure=optional("failure"),
        orphaned=optional("orphaned"),
        terminal_seal=optional("terminal_seal"),
    )


def validate_chain_snapshot_v1(
    contract: ReconstructionEvidenceContract,
    bootstrap_value: Any,
    snapshot: ReconstructionChainSnapshot,
) -> str:
    """Validate exact lifecycle shape and every same-chain reference."""

    bootstrap = _require_contract_bootstrap(contract, bootstrap_value)
    if not isinstance(snapshot, ReconstructionChainSnapshot):
        raise TypeError("snapshot must be a ReconstructionChainSnapshot")
    if snapshot.reservation is None:
        if any(
            value is not None
            for value in (
                snapshot.attempt,
                snapshot.completed,
                snapshot.failure,
                snapshot.orphaned,
                snapshot.terminal_seal,
            )
        ):
            raise EvidenceIntegrityError(
                "stage evidence exists without its reservation"
            )
        return "BOOTSTRAPPED"
    reservation = _validate_reservation_v1(
        contract, bootstrap, snapshot.reservation
    )
    if snapshot.attempt is None:
        if snapshot.completed is not None or snapshot.failure is not None:
            raise EvidenceIntegrityError("lifecycle body requires an attempt")
        if snapshot.orphaned is None:
            if snapshot.terminal_seal is not None:
                raise EvidenceIntegrityError(
                    "reservation-only chain cannot have a terminal seal"
                )
            return "RESERVED"
        orphaned = _validate_orphaned_v1(
            contract, bootstrap, reservation, None, snapshot.orphaned
        )
        lifecycle = "ORPHANED"
        terminal = build_terminal_seal_v1(
            contract,
            bootstrap,
            lifecycle,
            reservation=reservation,
            orphaned=orphaned,
        )
    else:
        attempt = _validate_attempt_v1(
            contract, bootstrap, reservation, snapshot.attempt
        )
        bodies = (
            snapshot.completed is not None,
            snapshot.failure is not None,
            snapshot.orphaned is not None,
        )
        if sum(bodies) > 1:
            raise EvidenceIntegrityError("stage has conflicting lifecycle bodies")
        if not any(bodies):
            if snapshot.terminal_seal is not None:
                raise EvidenceIntegrityError(
                    "attempt-only chain cannot have a terminal seal"
                )
            return "ATTEMPTED"
        if snapshot.completed is not None:
            completed = _exact_mapping(snapshot.completed, "completed body")
            expected = build_completed_v1(
                contract,
                bootstrap,
                reservation,
                attempt,
                completed.get("result"),
            )
            if canonical_json_bytes(completed) != canonical_json_bytes(expected):
                raise EvidenceIntegrityError("completed body does not reconstruct")
            lifecycle = "COMPLETED"
            terminal = build_terminal_seal_v1(
                contract,
                bootstrap,
                lifecycle,
                reservation=reservation,
                attempt=attempt,
                completed=completed,
            )
        elif snapshot.failure is not None:
            failure = _exact_mapping(snapshot.failure, "failure body")
            expected = build_failure_v1(
                contract,
                bootstrap,
                reservation,
                attempt,
                failure.get("failure"),
            )
            if canonical_json_bytes(failure) != canonical_json_bytes(expected):
                raise EvidenceIntegrityError("failure body does not reconstruct")
            lifecycle = "FAILED"
            terminal = build_terminal_seal_v1(
                contract,
                bootstrap,
                lifecycle,
                reservation=reservation,
                attempt=attempt,
                failure=failure,
            )
        else:
            orphaned = _validate_orphaned_v1(
                contract,
                bootstrap,
                reservation,
                attempt,
                snapshot.orphaned,
            )
            lifecycle = "ORPHANED"
            terminal = build_terminal_seal_v1(
                contract,
                bootstrap,
                lifecycle,
                reservation=reservation,
                attempt=attempt,
                orphaned=orphaned,
            )
    if snapshot.terminal_seal is None:
        return lifecycle + "_UNSEALED"
    observed_terminal = _validate_identity_envelope(
        contract,
        snapshot.terminal_seal,
        "terminal_seal",
        _TERMINAL_ARTIFACT_TYPE,
    )
    if canonical_json_bytes(observed_terminal) != canonical_json_bytes(terminal):
        raise EvidenceIntegrityError("terminal seal does not reconstruct")
    return lifecycle


def _require_no_contradiction(store: ReconstructionEvidenceStore) -> None:
    if store.contradiction_exists():
        raise EvidenceIntegrityError(
            "reconstruction stage has an immutable contradiction"
        )


def publish_bootstrap_v1(
    store: ReconstructionEvidenceStore, value: Any
) -> BodyRef:
    if not isinstance(store, ReconstructionEvidenceStore):
        raise TypeError("store must be a ReconstructionEvidenceStore")
    store._require_lock()
    store.reconcile_pending_publications()
    _require_no_contradiction(store)
    bootstrap = validate_bootstrap_v1(value)
    catalog = store.scan_fixed_catalog()
    if any(
        catalog[name] is not None
        for name in _STAGE_ARTIFACT_FILES
    ):
        raise EvidenceConflictError(
            "stage evidence exists before bootstrap publication"
        )
    return store.publish_bootstrap(bootstrap)


def begin_stage_v1(
    store: ReconstructionEvidenceStore,
    contract: ReconstructionEvidenceContract,
    bootstrap_value: Any,
) -> ReconstructionChainSnapshot:
    """Publish the sole reservation and attempt before any calculation."""

    if not isinstance(store, ReconstructionEvidenceStore):
        raise TypeError("store must be a ReconstructionEvidenceStore")
    store._require_lock()
    store.reconcile_pending_publications()
    _require_no_contradiction(store)
    bootstrap = _require_contract_bootstrap(contract, bootstrap_value)
    stored_bootstrap = validate_bootstrap_v1(store.read_bootstrap())
    if canonical_json_bytes(stored_bootstrap) != canonical_json_bytes(bootstrap):
        raise EvidenceConflictError("stored bootstrap differs from requested bootstrap")
    catalog = store.scan_fixed_catalog()
    if any(catalog[name] is not None for name in _STAGE_ARTIFACT_FILES):
        raise EvidenceConflictError("reconstruction stage already has immutable evidence")
    reservation = build_reservation_v1(contract, bootstrap)
    attempt = build_attempt_v1(contract, bootstrap, reservation)
    store.publish_stage_json("reservation", reservation)
    store.publish_stage_json("attempt", attempt)
    snapshot = ReconstructionChainSnapshot(
        reservation=reservation,
        attempt=attempt,
    )
    if validate_chain_snapshot_v1(contract, bootstrap, snapshot) != "ATTEMPTED":
        raise EvidenceIntegrityError("new attempted chain failed validation")
    return snapshot


def seal_completed_v1(
    store: ReconstructionEvidenceStore,
    contract: ReconstructionEvidenceContract,
    bootstrap_value: Any,
    result: Any,
) -> Dict[str, Any]:
    """Publish one completed body and terminal; never replace it with failure."""

    if not isinstance(store, ReconstructionEvidenceStore):
        raise TypeError("store must be a ReconstructionEvidenceStore")
    store._require_lock()
    store.reconcile_pending_publications()
    _require_no_contradiction(store)
    bootstrap = _require_contract_bootstrap(contract, bootstrap_value)
    snapshot = load_chain_snapshot_v1(store)
    if validate_chain_snapshot_v1(contract, bootstrap, snapshot) != "ATTEMPTED":
        raise EvidenceConflictError("stage is not an unsealed attempted chain")
    completed = build_completed_v1(
        contract,
        bootstrap,
        snapshot.reservation,
        snapshot.attempt,
        result,
    )
    terminal = build_terminal_seal_v1(
        contract,
        bootstrap,
        "COMPLETED",
        reservation=snapshot.reservation,
        attempt=snapshot.attempt,
        completed=completed,
    )
    store.publish_stage_json("completed", completed)
    store.publish_stage_json("terminal_seal", terminal)
    return terminal


def seal_failed_v1(
    store: ReconstructionEvidenceStore,
    contract: ReconstructionEvidenceContract,
    bootstrap_value: Any,
    failure_value: Any,
) -> Dict[str, Any]:
    """Publish one precomputed failure and terminal from ATTEMPTED only."""

    if not isinstance(store, ReconstructionEvidenceStore):
        raise TypeError("store must be a ReconstructionEvidenceStore")
    store._require_lock()
    store.reconcile_pending_publications()
    _require_no_contradiction(store)
    bootstrap = _require_contract_bootstrap(contract, bootstrap_value)
    snapshot = load_chain_snapshot_v1(store)
    if validate_chain_snapshot_v1(contract, bootstrap, snapshot) != "ATTEMPTED":
        raise EvidenceConflictError("stage is not an unsealed attempted chain")
    failure = build_failure_v1(
        contract,
        bootstrap,
        snapshot.reservation,
        snapshot.attempt,
        failure_value,
    )
    terminal = build_terminal_seal_v1(
        contract,
        bootstrap,
        "FAILED",
        reservation=snapshot.reservation,
        attempt=snapshot.attempt,
        failure=failure,
    )
    store.publish_stage_json("failure", failure)
    store.publish_stage_json("terminal_seal", terminal)
    return terminal


@dataclass(frozen=True)
class ReconstructionRecoveryResult:
    action: str
    lifecycle: Optional[str]
    terminal_identity: Optional[str]


def _publish_contradiction(
    store: ReconstructionEvidenceStore,
    observed: Optional[Mapping[str, Optional[BodyRef]]],
) -> None:
    catalog = {}
    if observed is not None:
        catalog = {
            key: None if ref is None else ref.as_dict()
            for key, ref in sorted(observed.items())
        }
    value = {
        "artifact_type": _CONTRADICTION_ARTIFACT_TYPE,
        "observed_catalog": catalog,
        "reason": "INVALID_OR_CONFLICTING_RECONSTRUCTION_EVIDENCE",
        "stage_id": PLAN0014_RECONSTRUCTION_STAGE_ID_V1,
        "stage_protocol_id": PLAN0014_RECONSTRUCTION_STAGE_PROTOCOL_ID_V1,
    }
    store.publish_contradiction(value)


def recover_stage_locked_v1(
    store: ReconstructionEvidenceStore,
    contract: ReconstructionEvidenceContract,
    *,
    expected_completed_result: Optional[Any] = None,
) -> ReconstructionRecoveryResult:
    """Recover structure while the caller holds the stage lock.

    A caller may supply an independently rebuilt completed result only when a
    completed body exists.  No callback is accepted, keeping calculation
    capability outside this module.
    """

    if not isinstance(store, ReconstructionEvidenceStore):
        raise TypeError("store must be a ReconstructionEvidenceStore")
    store._require_lock()
    observed: Optional[Mapping[str, Optional[BodyRef]]] = None
    trusted_bootstrap = False
    try:
        store.reconcile_pending_publications()
        _require_no_contradiction(store)
        observed = store.scan_fixed_catalog()
        if observed["bootstrap"] is None:
            if expected_completed_result is not None:
                raise EvidenceIntegrityError(
                    "completed expectation was supplied without evidence"
                )
            if any(observed[name] is not None for name in _STAGE_ARTIFACT_FILES):
                raise EvidenceIntegrityError(
                    "stage evidence exists without bootstrap"
                )
            return ReconstructionRecoveryResult("NO_EVIDENCE", None, None)
        bootstrap = _require_contract_bootstrap(contract, store.read_bootstrap())
        trusted_bootstrap = True
        snapshot = load_chain_snapshot_v1(store)
        state = validate_chain_snapshot_v1(contract, bootstrap, snapshot)
        completed_state = state in ("COMPLETED", "COMPLETED_UNSEALED")
        if completed_state:
            if expected_completed_result is None:
                raise EvidenceIntegrityError(
                    "completed recovery requires an independently rebuilt result"
                )
            expected_completed = build_completed_v1(
                contract,
                bootstrap,
                snapshot.reservation,
                snapshot.attempt,
                expected_completed_result,
            )
            if canonical_json_bytes(expected_completed) != canonical_json_bytes(
                snapshot.completed
            ):
                raise EvidenceIntegrityError(
                    "completed result does not match independent reconstruction"
                )
        elif expected_completed_result is not None:
            raise EvidenceIntegrityError(
                "completed expectation was supplied to a noncompleted chain"
            )
        if state == "BOOTSTRAPPED":
            return ReconstructionRecoveryResult(
                "BOOTSTRAP_ONLY_NO_STAGE", None, None
            )
        if state in ("COMPLETED", "FAILED", "ORPHANED"):
            return ReconstructionRecoveryResult(
                "VERIFIED_NO_OP",
                state,
                snapshot.terminal_seal["identity"],
            )
        if state.endswith("_UNSEALED"):
            lifecycle = state[: -len("_UNSEALED")]
            terminal = build_terminal_seal_v1(
                contract,
                bootstrap,
                lifecycle,
                reservation=snapshot.reservation,
                attempt=snapshot.attempt,
                completed=snapshot.completed,
                failure=snapshot.failure,
                orphaned=snapshot.orphaned,
            )
            store.publish_stage_json("terminal_seal", terminal)
            return ReconstructionRecoveryResult(
                "SEALED_EXISTING_" + lifecycle,
                lifecycle,
                terminal["identity"],
            )
        if state not in ("RESERVED", "ATTEMPTED"):
            raise EvidenceIntegrityError("unrecognized recoverable chain state")
        orphaned = build_orphaned_v1(
            contract,
            bootstrap,
            snapshot.reservation,
            snapshot.attempt,
        )
        terminal = build_terminal_seal_v1(
            contract,
            bootstrap,
            "ORPHANED",
            reservation=snapshot.reservation,
            attempt=snapshot.attempt,
            orphaned=orphaned,
        )
        store.publish_stage_json("orphaned", orphaned)
        store.publish_stage_json("terminal_seal", terminal)
        return ReconstructionRecoveryResult(
            "SEALED_NEW_ORPHANED", "ORPHANED", terminal["identity"]
        )
    except EvidenceLockError:
        raise
    except Exception as error:
        if trusted_bootstrap:
            try:
                _publish_contradiction(store, observed)
            except EvidenceConflictError:
                pass
        raise EvidenceIntegrityError(
            "reconstruction stage recovery failed closed"
        ) from error


def recover_stage_v1(
    store: ReconstructionEvidenceStore,
    contract: ReconstructionEvidenceContract,
    *,
    expected_completed_result: Optional[Any] = None,
) -> ReconstructionRecoveryResult:
    """Acquire the stage lock and invoke the locked recovery primitive."""

    if not isinstance(store, ReconstructionEvidenceStore):
        raise TypeError("store must be a ReconstructionEvidenceStore")
    with store.stage_lock(blocking=False):
        return recover_stage_locked_v1(
            store,
            contract,
            expected_completed_result=expected_completed_result,
        )


__all__ = (
    "PLAN0014_RECONSTRUCTION_EVIDENCE_PROTOCOL_ID_V1",
    "PLAN0014_RECONSTRUCTION_EVIDENCE_ROOT_RELATIVE_V1",
    "PLAN0014_RECONSTRUCTION_PROTOCOL_ID_V1",
    "PLAN0014_RECONSTRUCTION_STAGE_ID_V1",
    "PLAN0014_RECONSTRUCTION_STAGE_PROTOCOL_ID_V1",
    "ReconstructionChainSnapshot",
    "ReconstructionEvidenceContract",
    "ReconstructionEvidenceStore",
    "ReconstructionRecoveryResult",
    "begin_stage_v1",
    "build_attempt_v1",
    "build_bootstrap_v1",
    "build_completed_v1",
    "build_failure_v1",
    "build_orphaned_v1",
    "build_reservation_v1",
    "build_terminal_seal_v1",
    "failure_value_v1",
    "fixed_reconstruction_evidence_contract_v1",
    "load_chain_snapshot_v1",
    "open_recovery_store_v1",
    "publish_bootstrap_v1",
    "recover_stage_locked_v1",
    "recover_stage_v1",
    "seal_completed_v1",
    "seal_failed_v1",
    "validate_bootstrap_v1",
    "validate_chain_snapshot_v1",
)
