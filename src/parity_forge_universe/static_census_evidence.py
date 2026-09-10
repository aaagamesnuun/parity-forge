"""Immutable one-shot evidence for the Plan-0015 static census.

This module owns storage and lifecycle mechanics only.  It imports the sealed
protocol and the compact stored-report reconstructor, never the static-census
calculator or the legacy :mod:`parity_forge` package.  Filesystem mutation is
private and requires the opaque authority claimed once by the canonical stage
module; the exported surface is read-only/pure.  Recovery validates an already
published report and may finish its lifecycle, but cannot calculate or resume
a census.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any, Dict, Iterator, Mapping, Optional, Tuple

from . import static_census_protocol as protocol
from . import static_census_reconstruction as reconstruction


_SHA256 = hashlib.sha256
_JSON_DUMPS = json.dumps
_JSON_LOADS = json.loads
_BUILD_PROTOCOL_V1 = protocol.build_static_census_protocol_v1
_VALIDATE_PROTOCOL_V1 = protocol.validate_static_census_protocol_v1
_IDENTITY_DOMAIN_V1 = protocol.identity_domain_v1
_IDENTITY_PAYLOAD_KEYS_V1 = protocol.identity_payload_keys_v1
_FIXED_PROTOCOL_ID_V1 = protocol.PROTOCOL_ID_V1
_FIXED_PROTOCOL_ROOT_V1 = protocol.PROTOCOL_ROOT_V1
_FIXED_EVIDENCE_PROTOCOL_ID_V1 = protocol.EVIDENCE_PROTOCOL_ID_V1
_FIXED_PRODUCTION_CLOSURE_ARTIFACT_TYPE_V1 = (
    protocol.PRODUCTION_CLOSURE_ARTIFACT_TYPE_V1
)
_FIXED_SKELETON_COUNT_V1 = protocol.STATIC_CENSUS_EXPECTED_SKELETON_COUNT_V1
_FIXED_FACTORIZED_CARRIER_COUNT_V1 = (
    protocol.STATIC_CENSUS_EXPECTED_FACTORIZED_CARRIER_COUNT_V1
)
_FIXED_LABELED_SETUP_COUNT_V1 = (
    protocol.STATIC_CENSUS_EXPECTED_LABELED_SETUP_COUNT_V1
)
_FIXED_PAIRED_MEMBER_COUNT_V1 = (
    protocol.STATIC_CENSUS_EXPECTED_PAIRED_MEMBER_COUNT_V1
)
_FIXED_REPORT_MAX_BYTES_V1 = protocol.STATIC_CENSUS_REPORT_MAX_BYTES_V1


EVIDENCE_ROOT_RELATIVE_V1 = protocol.EVIDENCE_ROOT_RELATIVE_V1
STAGE_ID_V1 = protocol.STAGE_ID_V1
STAGE_PROTOCOL_ID_V1 = protocol.STAGE_PROTOCOL_ID_V1

_EVIDENCE_PROTOCOL_ID_V1 = "plan0015-factorized-static-census-evidence-v1"
_PROTOCOL_ARTIFACT_TYPE = "PLAN0015_STATIC_CENSUS_PROTOCOL_V1"
_PRODUCTION_CLOSURE_ARTIFACT_TYPE = (
    "PLAN0015_STATIC_CENSUS_PRODUCTION_CLOSURE_V1"
)
_BOOTSTRAP_ARTIFACT_TYPE = "PLAN0015_STATIC_CENSUS_BOOTSTRAP_V1"
_RESERVATION_ARTIFACT_TYPE = "PLAN0015_STATIC_CENSUS_RESERVATION_V1"
_ATTEMPT_ARTIFACT_TYPE = "PLAN0015_STATIC_CENSUS_ATTEMPT_V1"
_COMPLETED_ARTIFACT_TYPE = "PLAN0015_STATIC_CENSUS_COMPLETED_V1"
_FAILURE_ARTIFACT_TYPE = "PLAN0015_STATIC_CENSUS_FAILURE_V1"
_ORPHANED_ARTIFACT_TYPE = "PLAN0015_STATIC_CENSUS_ORPHANED_V1"
_TERMINAL_ARTIFACT_TYPE = "PLAN0015_STATIC_CENSUS_TERMINAL_SEAL_V1"
_CONTRADICTION_ARTIFACT_TYPE = "PLAN0015_STATIC_CENSUS_CONTRADICTION_V1"

_MAX_ARTIFACT_BYTES = 64 * 1024 * 1024
_MAX_REPORT_BYTES = _FIXED_REPORT_MAX_BYTES_V1
_MAX_JSON_NODES = 250_000
_MAX_JSON_DEPTH = 64
_MAX_FAILURE_TEXT_BYTES = 16 * 1024
_MAX_DIRECTORY_ENTRIES = 32

_READABLE_ARTIFACT_MODES = (0o400, 0o644)
_READABLE_EVIDENCE_DIRECTORY_MODES = (0o700, 0o755)
_SAFE_COMPONENT = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]{0,191}\Z")
_SAFE_INTERNAL_COMPONENT = re.compile(
    r"\A[A-Za-z0-9.][A-Za-z0-9._-]{0,191}\Z"
)
_HEX40 = re.compile(r"\A[0-9a-f]{40}\Z")
_HEX64 = re.compile(r"\A[0-9a-f]{64}\Z")

_BOOTSTRAP_FILE = "bootstrap.json"
_CONTRADICTION_FILE = "contradiction.json"
_STAGES_DIRECTORY = "stages"
_LOCKS_DIRECTORY = ".locks"
_PENDING_DIRECTORY = ".pending"
_STAGE_ARTIFACT_FILES = {
    "reservation": "reservation.json",
    "attempt": "attempt.json",
    "report": "static-census-report.json",
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
    "root--bootstrap.json.pending": ("root", _BOOTSTRAP_FILE, "bootstrap"),
    "root--contradiction.json.pending": (
        "root",
        _CONTRADICTION_FILE,
        "contradiction",
    ),
    **{
        "stage--{}.pending".format(filename): ("stage", filename, artifact)
        for artifact, filename in _STAGE_ARTIFACT_FILES.items()
    },
}

_IDENTITY_KINDS = (
    "bootstrap_root",
    "reservation_id",
    "attempt_id",
    "completed_root",
    "failure_root",
    "orphaned_id",
    "terminal_seal",
    "contradiction_id",
)
_FIXED_IDENTITY_DOMAINS = tuple(
    (kind, _IDENTITY_DOMAIN_V1(kind)) for kind in _IDENTITY_KINDS
)
_FIXED_IDENTITY_PAYLOAD_KEYS = tuple(
    (kind, _IDENTITY_PAYLOAD_KEYS_V1(kind)) for kind in _IDENTITY_KINDS
)
_FIXED_PRODUCTION_CLOSURE_DOMAIN = _IDENTITY_DOMAIN_V1(
    "production_closure_root"
)
_FIXED_PRODUCTION_CLOSURE_KEYS = _IDENTITY_PAYLOAD_KEYS_V1(
    "production_closure_root"
)
_FIXED_BOOTSTRAP_DOMAIN = _IDENTITY_DOMAIN_V1("bootstrap_root")
_FIXED_BOOTSTRAP_KEYS = _IDENTITY_PAYLOAD_KEYS_V1("bootstrap_root")

_STAGE_MODULE_NAME_V1 = __package__ + ".static_census_stage"
_STAGE_SOURCE_PATH_V1 = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "static_census_stage.py")
)


class _StaticCensusMutationCapability:
    """Opaque, identity-only authority held by the canonical stage module."""

    __slots__ = ()


def _build_stage_mutation_gate_v1(
    *,
    _expected_name: str = _STAGE_MODULE_NAME_V1,
    _expected_source: str = _STAGE_SOURCE_PATH_V1,
    _module_table: Dict[str, Any] = sys.modules,
    _getframe: Any = sys._getframe,
    _abspath: Any = os.path.abspath,
) -> Tuple[Any, Any]:
    token = _StaticCensusMutationCapability()
    owner: Optional[Any] = None

    def validate_owner(candidate: Any) -> None:
        if _module_table.get(_expected_name) is not candidate:
            raise StaticCensusEvidenceIntegrityError(
                "mutation capability owner is not the canonical stage module"
            )
        namespace = getattr(candidate, "__dict__", None)
        spec = getattr(candidate, "__spec__", None)
        loader = getattr(candidate, "__loader__", None)
        origin = None if spec is None else getattr(spec, "origin", None)
        spec_loader = None if spec is None else getattr(spec, "loader", None)
        module_file = getattr(candidate, "__file__", None)
        if (
            type(namespace) is not dict
            or getattr(candidate, "__name__", None) != _expected_name
            or type(origin) is not str
            or type(module_file) is not str
            or _abspath(origin) != _expected_source
            or _abspath(module_file) != _expected_source
            or loader is None
            or spec_loader is not loader
        ):
            raise StaticCensusEvidenceIntegrityError(
                "mutation capability owner has an invalid source binding"
            )

    def claim(candidate: Any) -> _StaticCensusMutationCapability:
        nonlocal owner
        if owner is not None:
            raise StaticCensusEvidenceIntegrityError(
                "static-census mutation capability was already claimed"
            )
        validate_owner(candidate)
        caller = _getframe(1)
        try:
            if (
                caller.f_globals is not candidate.__dict__
                or _abspath(caller.f_code.co_filename) != _expected_source
            ):
                raise StaticCensusEvidenceIntegrityError(
                    "mutation capability may be claimed only by the stage source"
                )
        finally:
            del caller
        owner = candidate
        return token

    def require(candidate: Any) -> None:
        if owner is None or candidate is not token:
            raise StaticCensusEvidenceIntegrityError(
                "static-census mutation capability is unavailable"
            )
        validate_owner(owner)

    return claim, require


(
    _claim_stage_mutation_capability_v1,
    _require_mutation_capability_v1,
) = _build_stage_mutation_gate_v1()
del _build_stage_mutation_gate_v1


class StaticCensusEvidenceError(RuntimeError):
    """Base class for the fixed evidence boundary."""


class StaticCensusEvidenceIntegrityError(StaticCensusEvidenceError):
    """Stored evidence, provenance, or a hostile boundary is invalid."""


class StaticCensusEvidenceConflictError(StaticCensusEvidenceError):
    """An immutable publication slot already has another lifecycle value."""


class StaticCensusEvidenceLockError(StaticCensusEvidenceError):
    """The single stage lock is unavailable or not held."""


def _require_protocol_bindings() -> None:
    function_bindings = (
        ("build_static_census_protocol_v1", _BUILD_PROTOCOL_V1),
        ("validate_static_census_protocol_v1", _VALIDATE_PROTOCOL_V1),
        ("identity_domain_v1", _IDENTITY_DOMAIN_V1),
        ("identity_payload_keys_v1", _IDENTITY_PAYLOAD_KEYS_V1),
    )
    for name, expected in function_bindings:
        if getattr(protocol, name, None) is not expected:
            raise StaticCensusEvidenceIntegrityError(
                "static-census protocol function binding changed"
            )
    constant_bindings = (
        ("PROTOCOL_ID_V1", _FIXED_PROTOCOL_ID_V1),
        ("PROTOCOL_ROOT_V1", _FIXED_PROTOCOL_ROOT_V1),
        ("EVIDENCE_PROTOCOL_ID_V1", _FIXED_EVIDENCE_PROTOCOL_ID_V1),
        ("EVIDENCE_ROOT_RELATIVE_V1", EVIDENCE_ROOT_RELATIVE_V1),
        ("STAGE_ID_V1", STAGE_ID_V1),
        ("STAGE_PROTOCOL_ID_V1", STAGE_PROTOCOL_ID_V1),
        (
            "PRODUCTION_CLOSURE_ARTIFACT_TYPE_V1",
            _FIXED_PRODUCTION_CLOSURE_ARTIFACT_TYPE_V1,
        ),
        (
            "STATIC_CENSUS_EXPECTED_SKELETON_COUNT_V1",
            _FIXED_SKELETON_COUNT_V1,
        ),
        (
            "STATIC_CENSUS_EXPECTED_FACTORIZED_CARRIER_COUNT_V1",
            _FIXED_FACTORIZED_CARRIER_COUNT_V1,
        ),
        (
            "STATIC_CENSUS_EXPECTED_LABELED_SETUP_COUNT_V1",
            _FIXED_LABELED_SETUP_COUNT_V1,
        ),
        (
            "STATIC_CENSUS_EXPECTED_PAIRED_MEMBER_COUNT_V1",
            _FIXED_PAIRED_MEMBER_COUNT_V1,
        ),
        ("STATIC_CENSUS_REPORT_MAX_BYTES_V1", _FIXED_REPORT_MAX_BYTES_V1),
    )
    for name, expected in constant_bindings:
        observed = getattr(protocol, name, None)
        if type(observed) is not type(expected) or observed != expected:
            raise StaticCensusEvidenceIntegrityError(
                "static-census protocol constant binding changed"
            )


def _safe_component(value: Any, label: str) -> str:
    if type(value) is not str or _SAFE_COMPONENT.fullmatch(value) is None:
        raise StaticCensusEvidenceIntegrityError(
            "{} is not a safe evidence component".format(label)
        )
    return value


def _safe_internal_component(value: Any, label: str) -> str:
    if (
        type(value) is not str
        or value in (".", "..")
        or _SAFE_INTERNAL_COMPONENT.fullmatch(value) is None
    ):
        raise StaticCensusEvidenceIntegrityError(
            "{} is not a safe internal component".format(label)
        )
    return value


def _exact_string(value: Any, label: str) -> str:
    if type(value) is not str:
        raise StaticCensusEvidenceIntegrityError(
            "{} must be an exact string".format(label)
        )
    return value


def _exact_hex(value: Any, length: int, label: str) -> str:
    text = _exact_string(value, label)
    pattern = _HEX40 if length == 40 else _HEX64
    if pattern.fullmatch(text) is None:
        raise StaticCensusEvidenceIntegrityError(
            "{} must be lowercase hexadecimal".format(label)
        )
    return text


def _exact_keys(value: Any, keys: Tuple[str, ...], label: str) -> Dict[str, Any]:
    if type(value) is not dict or len(value) != len(keys) or set(value) != set(keys):
        raise StaticCensusEvidenceIntegrityError(
            "{} has an invalid exact schema".format(label)
        )
    return value


def _validate_json_tree(
    value: Any,
    label: str,
    *,
    max_nodes: int = _MAX_JSON_NODES,
    max_depth: int = _MAX_JSON_DEPTH,
) -> None:
    if type(max_nodes) is not int or max_nodes < 1:
        raise TypeError("max_nodes must be a positive exact int")
    if type(max_depth) is not int or max_depth < 1:
        raise TypeError("max_depth must be a positive exact int")
    stack = [(value, 0)]
    nodes = 0
    while stack:
        current, depth = stack.pop()
        nodes += 1
        if nodes > max_nodes:
            raise StaticCensusEvidenceIntegrityError(
                "{} exceeds the JSON node limit".format(label)
            )
        if depth > max_depth:
            raise StaticCensusEvidenceIntegrityError(
                "{} exceeds the JSON depth limit".format(label)
            )
        if type(current) is dict:
            for key, child in current.items():
                if type(key) is not str:
                    raise StaticCensusEvidenceIntegrityError(
                        "{} has a non-string JSON key".format(label)
                    )
                stack.append((child, depth + 1))
        elif type(current) is list:
            stack.extend((child, depth + 1) for child in current)
        elif type(current) not in (str, int, bool, type(None)):
            raise StaticCensusEvidenceIntegrityError(
                "{} contains a noncanonical JSON value".format(label)
            )


def _canonical_json_bytes(value: Any) -> bytes:
    _validate_json_tree(value, "canonical JSON")
    try:
        return _JSON_DUMPS(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as error:
        raise StaticCensusEvidenceIntegrityError(
            "value is not canonical JSON"
        ) from error


def _load_canonical_json_bytes(
    raw: Any,
    *,
    label: str = "artifact",
    max_nodes: int = _MAX_JSON_NODES,
    max_depth: int = _MAX_JSON_DEPTH,
) -> Any:
    if type(raw) is not bytes:
        raise TypeError("canonical JSON input must be exact bytes")
    try:
        text = raw.decode("utf-8", "strict")
        value = _JSON_LOADS(text)
    except (UnicodeDecodeError, ValueError, RecursionError) as error:
        raise StaticCensusEvidenceIntegrityError(
            "{} is not valid UTF-8 JSON".format(label)
        ) from error
    _validate_json_tree(
        value, label, max_nodes=max_nodes, max_depth=max_depth
    )
    if _canonical_json_bytes(value) != raw:
        raise StaticCensusEvidenceIntegrityError(
            "{} is not canonical JSON".format(label)
        )
    return value


def _json_copy(value: Any, label: str) -> Any:
    return _load_canonical_json_bytes(_canonical_json_bytes(value), label=label)


def _domain_identity(domain: bytes, payload: Any) -> str:
    if type(domain) is not bytes or not domain.endswith(b"\0"):
        raise StaticCensusEvidenceIntegrityError("identity domain is invalid")
    return _SHA256(domain + _canonical_json_bytes(payload)).hexdigest()


@dataclass(frozen=True)
class StaticCensusBodyRef:
    sha256: str
    byte_count: int

    def __post_init__(self) -> None:
        _exact_hex(self.sha256, 64, "body-reference SHA-256")
        if type(self.byte_count) is not int or self.byte_count < 0:
            raise StaticCensusEvidenceIntegrityError(
                "body-reference byte count is invalid"
            )

    def as_dict(self) -> Dict[str, Any]:
        return {"byte_count": self.byte_count, "sha256": self.sha256}


def _body_ref(raw: bytes) -> StaticCensusBodyRef:
    if type(raw) is not bytes:
        raise TypeError("body must be exact bytes")
    return StaticCensusBodyRef(_SHA256(raw).hexdigest(), len(raw))


def _validate_body_ref(value: Any, label: str) -> StaticCensusBodyRef:
    ref = _exact_keys(value, ("byte_count", "sha256"), label)
    if type(ref["byte_count"]) is not int or ref["byte_count"] < 0:
        raise StaticCensusEvidenceIntegrityError(
            "{} byte count is invalid".format(label)
        )
    return StaticCensusBodyRef(
        _exact_hex(ref["sha256"], 64, "{} SHA-256".format(label)),
        ref["byte_count"],
    )


def _canonical_body_ref(value: Any) -> StaticCensusBodyRef:
    return _body_ref(_canonical_json_bytes(value))


def _entry_exists(parent_fd: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    except OSError as error:
        raise StaticCensusEvidenceIntegrityError(
            "evidence entry is unavailable"
        ) from error
    return True


def _stable_directory_entries(directory_fd: int, label: str) -> set[str]:
    """List one directory while rejecting mutation during the listing."""

    before = os.fstat(directory_fd)
    if not stat.S_ISDIR(before.st_mode):
        raise StaticCensusEvidenceIntegrityError(
            "{} is not a directory".format(label)
        )
    try:
        listed = []
        with os.scandir(directory_fd) as iterator:
            for entry in iterator:
                if len(listed) >= _MAX_DIRECTORY_ENTRIES:
                    raise StaticCensusEvidenceIntegrityError(
                        "{} exceeds the fixed entry bound".format(label)
                    )
                listed.append(entry.name)
    except OSError as error:
        raise StaticCensusEvidenceIntegrityError(
            "{} cannot be listed safely".format(label)
        ) from error
    if any(type(name) is not str for name in listed) or len(listed) != len(
        set(listed)
    ):
        raise StaticCensusEvidenceIntegrityError(
            "{} returned an invalid directory inventory".format(label)
        )
    after = os.fstat(directory_fd)
    before_key = (
        before.st_dev,
        before.st_ino,
        before.st_mode,
        before.st_nlink,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    after_key = (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_nlink,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    if before_key != after_key:
        raise StaticCensusEvidenceIntegrityError(
            "{} changed while being listed".format(label)
        )
    return set(listed)


def _directory_metadata_v1(directory_fd: int, label: str) -> Tuple[int, ...]:
    """Capture mutation-sensitive metadata for one already held directory."""

    try:
        observed = os.fstat(directory_fd)
    except OSError as error:
        raise StaticCensusEvidenceIntegrityError(
            "{} metadata is unavailable".format(label)
        ) from error
    if not stat.S_ISDIR(observed.st_mode):
        raise StaticCensusEvidenceIntegrityError(
            "{} is not a directory".format(label)
        )
    return (
        observed.st_dev,
        observed.st_ino,
        observed.st_mode,
        observed.st_nlink,
        observed.st_size,
        observed.st_mtime_ns,
        observed.st_ctime_ns,
    )


def _require_directory_metadata_v1(
    directory_fd: int, expected: Tuple[int, ...], label: str
) -> None:
    if _directory_metadata_v1(directory_fd, label) != expected:
        raise StaticCensusEvidenceIntegrityError(
            "{} changed across the evidence snapshot".format(label)
        )


def _require_named_directory_binding(
    parent_fd: int, name: str, directory_fd: int, label: str
) -> None:
    """Require a held directory descriptor to remain at its fixed name."""

    _safe_internal_component(name, label)
    try:
        descriptor = os.fstat(directory_fd)
        named = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except OSError as error:
        raise StaticCensusEvidenceIntegrityError(
            "{} path is unavailable".format(label)
        ) from error
    if (
        not stat.S_ISDIR(descriptor.st_mode)
        or not stat.S_ISDIR(named.st_mode)
        or (descriptor.st_dev, descriptor.st_ino)
        != (named.st_dev, named.st_ino)
        or descriptor.st_mode != named.st_mode
    ):
        raise StaticCensusEvidenceIntegrityError(
            "{} path changed".format(label)
        )


def _open_existing_directory_at(
    parent_fd: int,
    name: str,
    *,
    allowed_modes: Optional[Tuple[int, ...]] = _READABLE_EVIDENCE_DIRECTORY_MODES,
) -> int:
    _safe_internal_component(name, "directory")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    fd = -1
    try:
        fd = os.open(name, flags, dir_fd=parent_fd)
        info = os.fstat(fd)
        if not stat.S_ISDIR(info.st_mode):
            raise StaticCensusEvidenceIntegrityError(
                "evidence component is not a directory"
            )
        if allowed_modes is not None and stat.S_IMODE(info.st_mode) not in allowed_modes:
            raise StaticCensusEvidenceIntegrityError(
                "evidence directory component has the wrong mode"
            )
        return fd
    except OSError as error:
        if fd >= 0:
            os.close(fd)
        raise StaticCensusEvidenceIntegrityError(
            "evidence directory component is unavailable or unsafe"
        ) from error
    except BaseException:
        if fd >= 0:
            os.close(fd)
        raise


def _open_or_create_directory_at(
    parent_fd: int,
    name: str,
    *,
    allowed_existing_modes: Tuple[int, ...] = _READABLE_EVIDENCE_DIRECTORY_MODES,
) -> int:
    _safe_internal_component(name, "directory")
    created = False
    try:
        os.mkdir(name, mode=0o700, dir_fd=parent_fd)
        created = True
    except FileExistsError:
        pass
    except OSError as error:
        raise StaticCensusEvidenceIntegrityError(
            "evidence directory cannot be created"
        ) from error
    fd = _open_existing_directory_at(
        parent_fd,
        name,
        allowed_modes=((0o700,) if created else allowed_existing_modes),
    )
    try:
        os.fsync(fd)
        os.fsync(parent_fd)
    except BaseException:
        os.close(fd)
        raise
    return fd


def _open_root_directory(root: Path, *, create: bool) -> int:
    absolute = Path(os.path.abspath(os.fspath(root)))
    if absolute.parent == absolute:
        raise StaticCensusEvidenceIntegrityError(
            "evidence root cannot be a filesystem anchor"
        )
    flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    anchor_fd = current_fd = -1
    try:
        anchor_fd = os.open(absolute.anchor, flags)
        current_fd = anchor_fd
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
        return os.dup(current_fd)
    except OSError as error:
        raise StaticCensusEvidenceIntegrityError(
            "evidence root is unavailable or unsafe"
        ) from error
    finally:
        if current_fd >= 0 and current_fd != anchor_fd:
            os.close(current_fd)
        if anchor_fd >= 0:
            os.close(anchor_fd)


def _read_regular_descriptor(
    fd: int,
    *,
    allowed_link_counts: Tuple[int, ...] = (1,),
    allowed_modes: Tuple[int, ...] = _READABLE_ARTIFACT_MODES,
    expected_size: Optional[int] = None,
    max_bytes: int = _MAX_ARTIFACT_BYTES,
) -> bytes:
    if expected_size is not None and (
        type(expected_size) is not int or expected_size < 0
    ):
        raise TypeError("expected_size must be a nonnegative exact int")
    if type(max_bytes) is not int or max_bytes < 0:
        raise TypeError("max_bytes must be a nonnegative exact int")
    before = os.fstat(fd)
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_nlink not in allowed_link_counts
    ):
        raise StaticCensusEvidenceIntegrityError(
            "immutable artifact has an invalid type or link count"
        )
    if stat.S_IMODE(before.st_mode) not in allowed_modes:
        raise StaticCensusEvidenceIntegrityError(
            "immutable artifact has the wrong mode"
        )
    if expected_size is not None and before.st_size != expected_size:
        raise StaticCensusEvidenceIntegrityError(
            "immutable artifact has the wrong size"
        )
    if before.st_size > max_bytes:
        raise StaticCensusEvidenceIntegrityError(
            "immutable artifact exceeds the byte limit"
        )
    chunks = []
    offset = 0
    remaining = before.st_size
    while remaining:
        chunk = os.pread(fd, min(1024 * 1024, remaining), offset)
        if not chunk:
            raise StaticCensusEvidenceIntegrityError(
                "immutable artifact was truncated while reading"
            )
        chunks.append(chunk)
        offset += len(chunk)
        remaining -= len(chunk)
    if os.pread(fd, 1, offset):
        raise StaticCensusEvidenceIntegrityError(
            "immutable artifact grew while reading"
        )
    after = os.fstat(fd)
    before_key = (
        before.st_dev,
        before.st_ino,
        before.st_mode,
        before.st_nlink,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    after_key = (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_nlink,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    if before_key != after_key:
        raise StaticCensusEvidenceIntegrityError(
            "immutable artifact changed while reading"
        )
    return b"".join(chunks)


def _require_named_regular_binding(
    parent_fd: int, name: str, fd: int, label: str
) -> None:
    _safe_component(name, label)
    try:
        descriptor = os.fstat(fd)
        named = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except OSError as error:
        raise StaticCensusEvidenceIntegrityError(
            "{} path is unavailable".format(label)
        ) from error
    descriptor_key = (
        descriptor.st_dev,
        descriptor.st_ino,
        descriptor.st_mode,
        descriptor.st_nlink,
        descriptor.st_size,
        descriptor.st_mtime_ns,
        descriptor.st_ctime_ns,
    )
    named_key = (
        named.st_dev,
        named.st_ino,
        named.st_mode,
        named.st_nlink,
        named.st_size,
        named.st_mtime_ns,
        named.st_ctime_ns,
    )
    if not stat.S_ISREG(named.st_mode) or descriptor_key != named_key:
        raise StaticCensusEvidenceIntegrityError(
            "{} path changed".format(label)
        )


def _regular_descriptor_metadata_v1(fd: int, label: str) -> Tuple[int, ...]:
    try:
        observed = os.fstat(fd)
    except OSError as error:
        raise StaticCensusEvidenceIntegrityError(
            "{} metadata is unavailable".format(label)
        ) from error
    if not stat.S_ISREG(observed.st_mode):
        raise StaticCensusEvidenceIntegrityError(
            "{} is not a regular file".format(label)
        )
    return (
        observed.st_dev,
        observed.st_ino,
        observed.st_mode,
        observed.st_nlink,
        observed.st_size,
        observed.st_mtime_ns,
        observed.st_ctime_ns,
    )


def _read_regular_at(
    parent_fd: int,
    name: str,
    *,
    allowed_link_counts: Tuple[int, ...] = (1,),
    allowed_modes: Tuple[int, ...] = _READABLE_ARTIFACT_MODES,
    expected_size: Optional[int] = None,
    max_bytes: int = _MAX_ARTIFACT_BYTES,
) -> bytes:
    _safe_component(name, "artifact")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    fd = -1
    try:
        fd = os.open(name, flags, dir_fd=parent_fd)
        raw = _read_regular_descriptor(
            fd,
            allowed_link_counts=allowed_link_counts,
            allowed_modes=allowed_modes,
            expected_size=expected_size,
            max_bytes=max_bytes,
        )
        _require_named_regular_binding(parent_fd, name, fd, "immutable artifact")
        return raw
    except OSError as error:
        raise StaticCensusEvidenceIntegrityError(
            "immutable artifact is unavailable or unsafe"
        ) from error
    finally:
        if fd >= 0:
            os.close(fd)


def _artifact_max_bytes(artifact: str) -> int:
    return _MAX_REPORT_BYTES if artifact == "report" else _MAX_ARTIFACT_BYTES


def _validate_artifact_raw(artifact: str, raw: bytes) -> None:
    if artifact == "report":
        _reconstruct_report(raw)
        return
    _load_canonical_json_bytes(raw, label=artifact)


@dataclass(frozen=True)
class StaticCensusEvidenceContract:
    protocol_id: str
    protocol_root: str
    evidence_protocol_id: str
    stage_id: str
    stage_protocol_id: str
    identity_domains: Tuple[Tuple[str, bytes], ...]
    identity_payload_keys: Tuple[Tuple[str, Tuple[str, ...]], ...]

    def __post_init__(self) -> None:
        coordinates = (
            (self.protocol_id, _FIXED_PROTOCOL_ID_V1, "protocol id"),
            (self.protocol_root, _FIXED_PROTOCOL_ROOT_V1, "protocol root"),
            (
                self.evidence_protocol_id,
                _FIXED_EVIDENCE_PROTOCOL_ID_V1,
                "evidence protocol id",
            ),
            (self.stage_id, STAGE_ID_V1, "stage id"),
            (
                self.stage_protocol_id,
                STAGE_PROTOCOL_ID_V1,
                "stage protocol id",
            ),
        )
        for observed, expected, label in coordinates:
            if type(observed) is not str or observed != expected:
                raise StaticCensusEvidenceIntegrityError(
                    "static-census evidence {} is not fixed".format(label)
                )
        _exact_hex(self.protocol_root, 64, "evidence protocol root")
        if type(self.identity_domains) is not tuple:
            raise StaticCensusEvidenceIntegrityError(
                "identity domain catalog must be an exact tuple"
            )
        for record in self.identity_domains:
            if (
                type(record) is not tuple
                or len(record) != 2
                or type(record[0]) is not str
                or type(record[1]) is not bytes
                or not record[1].endswith(b"\0")
            ):
                raise StaticCensusEvidenceIntegrityError(
                    "identity domain catalog has an invalid record"
                )
        if self.identity_domains != _FIXED_IDENTITY_DOMAINS:
            raise StaticCensusEvidenceIntegrityError(
                "identity domain catalog is not fixed"
            )
        if type(self.identity_payload_keys) is not tuple:
            raise StaticCensusEvidenceIntegrityError(
                "identity schema catalog must be an exact tuple"
            )
        for record in self.identity_payload_keys:
            if (
                type(record) is not tuple
                or len(record) != 2
                or type(record[0]) is not str
                or type(record[1]) is not tuple
                or any(type(key) is not str for key in record[1])
            ):
                raise StaticCensusEvidenceIntegrityError(
                    "identity schema catalog has an invalid record"
                )
        if self.identity_payload_keys != _FIXED_IDENTITY_PAYLOAD_KEYS:
            raise StaticCensusEvidenceIntegrityError(
                "identity schema catalog is not fixed"
            )

    def identity_domain(self, kind: str) -> bytes:
        self.__post_init__()
        if type(kind) is not str:
            raise TypeError("identity kind must be an exact string")
        matches = [value for name, value in self.identity_domains if name == kind]
        if len(matches) != 1:
            raise StaticCensusEvidenceIntegrityError(
                "evidence identity domain is unavailable"
            )
        return matches[0]

    def identity_keys(self, kind: str) -> Tuple[str, ...]:
        self.__post_init__()
        if type(kind) is not str:
            raise TypeError("identity kind must be an exact string")
        matches = [value for name, value in self.identity_payload_keys if name == kind]
        if len(matches) != 1:
            raise StaticCensusEvidenceIntegrityError(
                "evidence identity schema is unavailable"
            )
        return matches[0]


def fixed_static_census_evidence_contract_v1() -> StaticCensusEvidenceContract:
    _require_protocol_bindings()
    value = _VALIDATE_PROTOCOL_V1(_BUILD_PROTOCOL_V1())
    if type(value) is not dict:
        raise StaticCensusEvidenceIntegrityError("protocol validator changed type")
    return StaticCensusEvidenceContract(
        protocol_id=_FIXED_PROTOCOL_ID_V1,
        protocol_root=_FIXED_PROTOCOL_ROOT_V1,
        evidence_protocol_id=_EVIDENCE_PROTOCOL_ID_V1,
        stage_id=STAGE_ID_V1,
        stage_protocol_id=STAGE_PROTOCOL_ID_V1,
        identity_domains=_FIXED_IDENTITY_DOMAINS,
        identity_payload_keys=_FIXED_IDENTITY_PAYLOAD_KEYS,
    )


def _require_fixed_contract(
    value: Any,
) -> StaticCensusEvidenceContract:
    if type(value) is not StaticCensusEvidenceContract:
        raise TypeError("contract must be a StaticCensusEvidenceContract")
    value.__post_init__()
    _require_protocol_bindings()
    return value


class _StaticCensusEvidenceStore:
    """Internal descriptor-bound storage for the sole static-census stage."""

    def __init__(
        self,
        capability: _StaticCensusMutationCapability,
        root: os.PathLike[str],
        *,
        create: bool = False,
    ) -> None:
        _require_mutation_capability_v1(capability)
        if type(create) is not bool:
            raise TypeError("create must be an exact bool")
        self._capability = capability
        self.root = Path(os.path.abspath(os.fspath(root)))
        self._create_operational = create
        self._held_lock = False
        self._held_lock_fd = -1
        self._held_locks_fd = -1
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
        except BaseException:
            os.close(self._root_fd)
            self._root_fd = -1
            raise

    @classmethod
    def _for_run(
        cls,
        capability: _StaticCensusMutationCapability,
        root: os.PathLike[str],
    ) -> "_StaticCensusEvidenceStore":
        return cls(capability, root, create=True)

    @classmethod
    def _for_recovery(
        cls,
        capability: _StaticCensusMutationCapability,
        root: os.PathLike[str],
    ) -> "_StaticCensusEvidenceStore":
        instance = cls(capability, root, create=False)
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
        except BaseException:
            instance.close()
            raise
        return instance

    def close(self) -> None:
        if self._held_lock:
            raise StaticCensusEvidenceLockError(
                "cannot close the evidence store while its lock is held"
            )
        if getattr(self, "_root_fd", -1) >= 0:
            os.close(self._root_fd)
            self._root_fd = -1

    def _require_mutation_capability(
        self, capability: _StaticCensusMutationCapability
    ) -> None:
        _require_mutation_capability_v1(capability)
        if capability is not self._capability:
            raise StaticCensusEvidenceIntegrityError(
                "store mutation capability changed"
            )

    def __enter__(self) -> "_StaticCensusEvidenceStore":
        return self

    def __exit__(self, _type: Any, _value: Any, _traceback: Any) -> None:
        self.close()

    def _require_path_binding(self) -> None:
        observed_fd = -1
        try:
            observed_fd = _open_root_directory(self.root, create=False)
            expected = os.fstat(self._root_fd)
            observed = os.fstat(observed_fd)
            if (expected.st_dev, expected.st_ino) != (
                observed.st_dev,
                observed.st_ino,
            ):
                raise StaticCensusEvidenceIntegrityError(
                    "evidence root path was replaced"
                )
        finally:
            if observed_fd >= 0:
                os.close(observed_fd)

    def _require_open(self) -> None:
        if self._root_fd < 0:
            raise StaticCensusEvidenceError("static-census evidence store is closed")
        self._require_path_binding()

    def _require_lock(self) -> None:
        self._require_open()
        if (
            not self._held_lock
            or self._held_lock_fd < 0
            or self._held_locks_fd < 0
        ):
            raise StaticCensusEvidenceLockError(
                "evidence publication requires the held stage lock"
            )
        try:
            _require_named_directory_binding(
                self._root_fd,
                _LOCKS_DIRECTORY,
                self._held_locks_fd,
                "locks directory",
            )
        except StaticCensusEvidenceIntegrityError as error:
            raise StaticCensusEvidenceLockError(
                "held stage lock directory changed"
            ) from error
        component = STAGE_PROTOCOL_ID_V1 + ".lock"
        try:
            descriptor = os.fstat(self._held_lock_fd)
            named = os.stat(
                component,
                dir_fd=self._held_locks_fd,
                follow_symlinks=False,
            )
        except OSError as error:
            raise StaticCensusEvidenceLockError(
                "held stage lock path is unavailable"
            ) from error
        if (
            (descriptor.st_dev, descriptor.st_ino) != (named.st_dev, named.st_ino)
            or not stat.S_ISREG(named.st_mode)
            or named.st_nlink != 1
            or stat.S_IMODE(named.st_mode) != 0o600
            or named.st_size != 0
        ):
            raise StaticCensusEvidenceLockError(
                "held stage lock path changed"
            )

    @contextlib.contextmanager
    def _stage_lock(
        self,
        capability: _StaticCensusMutationCapability,
        *,
        blocking: bool = False,
    ) -> Iterator[None]:
        self._require_mutation_capability(capability)
        self._require_open()
        if type(blocking) is not bool:
            raise TypeError("blocking must be an exact bool")
        if blocking:
            raise ValueError("the fixed static-census lock is nonblocking")
        if self._held_lock:
            raise StaticCensusEvidenceLockError(
                "static-census evidence lock is not reentrant"
            )
        locks_fd = (
            _open_or_create_directory_at(
                self._root_fd,
                _LOCKS_DIRECTORY,
                allowed_existing_modes=(0o700,),
            )
            if self._create_operational
            else _open_existing_directory_at(
                self._root_fd, _LOCKS_DIRECTORY, allowed_modes=(0o700,)
            )
        )
        lock_fd = -1
        lock_acquired = False
        try:
            component = STAGE_PROTOCOL_ID_V1 + ".lock"
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
                raise StaticCensusEvidenceLockError(
                    "static-census evidence lock is unavailable"
                ) from error
            info = os.fstat(lock_fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_size != 0
            ):
                raise StaticCensusEvidenceIntegrityError(
                    "stage lock must be empty, mode 0600, singly linked, and regular"
                )
            os.fsync(lock_fd)
            os.fsync(locks_fd)
            operation = fcntl.LOCK_EX | fcntl.LOCK_NB
            try:
                fcntl.flock(lock_fd, operation)
            except BlockingIOError as error:
                raise StaticCensusEvidenceLockError(
                    "static-census evidence lock is already held"
                ) from error
            lock_acquired = True
            self._held_lock = True
            self._held_lock_fd = lock_fd
            self._held_locks_fd = locks_fd
            try:
                self._require_lock()
                try:
                    yield
                finally:
                    self._require_lock()
            finally:
                self._held_lock = False
                self._held_lock_fd = -1
                self._held_locks_fd = -1
        finally:
            if lock_fd >= 0:
                try:
                    if lock_acquired:
                        fcntl.flock(lock_fd, fcntl.LOCK_UN)
                finally:
                    os.close(lock_fd)
            os.close(locks_fd)

    @contextlib.contextmanager
    def _pending_fd(
        self,
        *,
        create: bool,
        capability: Optional[_StaticCensusMutationCapability] = None,
    ) -> Iterator[int]:
        if create:
            self._require_mutation_capability(capability)
        self._require_open()
        fd = (
            _open_or_create_directory_at(
                self._root_fd,
                _PENDING_DIRECTORY,
                allowed_existing_modes=(0o700,),
            )
            if create
            else _open_existing_directory_at(
                self._root_fd, _PENDING_DIRECTORY, allowed_modes=(0o700,)
            )
        )
        try:
            yield fd
        finally:
            try:
                _require_named_directory_binding(
                    self._root_fd,
                    _PENDING_DIRECTORY,
                    fd,
                    "pending directory",
                )
                self._require_path_binding()
            finally:
                os.close(fd)

    @contextlib.contextmanager
    def _stage_fd(
        self,
        *,
        create: bool,
        capability: Optional[_StaticCensusMutationCapability] = None,
    ) -> Iterator[int]:
        if create:
            self._require_mutation_capability(capability)
        self._require_open()
        stages_fd = (
            _open_or_create_directory_at(self._root_fd, _STAGES_DIRECTORY)
            if create
            else _open_existing_directory_at(self._root_fd, _STAGES_DIRECTORY)
        )
        try:
            stage_fd = (
                _open_or_create_directory_at(
                    stages_fd, STAGE_PROTOCOL_ID_V1
                )
                if create
                else _open_existing_directory_at(stages_fd, STAGE_PROTOCOL_ID_V1)
            )
            try:
                yield stage_fd
            finally:
                try:
                    _require_named_directory_binding(
                        stages_fd,
                        STAGE_PROTOCOL_ID_V1,
                        stage_fd,
                        "static-census stage directory",
                    )
                finally:
                    os.close(stage_fd)
        finally:
            try:
                _require_named_directory_binding(
                    self._root_fd,
                    _STAGES_DIRECTORY,
                    stages_fd,
                    "stages directory",
                )
                self._require_path_binding()
            finally:
                os.close(stages_fd)

    @contextlib.contextmanager
    def _target_fd(
        self,
        scope: str,
        *,
        create: bool,
        capability: Optional[_StaticCensusMutationCapability] = None,
    ) -> Iterator[int]:
        if create:
            self._require_mutation_capability(capability)
        if scope == "root":
            yield self._root_fd
            return
        if scope != "stage":
            raise ValueError("unknown evidence publication scope")
        with self._stage_fd(
            create=create, capability=capability
        ) as stage_fd:
            yield stage_fd

    def _reconcile_pending_target(
        self,
        capability: _StaticCensusMutationCapability,
        pending_fd: int,
        pending_name: str,
        target_fd: int,
        final_name: str,
        artifact: str,
    ) -> None:
        self._require_mutation_capability(capability)
        pending_exists = _entry_exists(pending_fd, pending_name)
        final_exists = _entry_exists(target_fd, final_name)
        if not pending_exists:
            return
        if not final_exists:
            flags = (
                os.O_RDONLY
                | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_NONBLOCK", 0)
            )
            pending_body_fd = -1
            try:
                pending_body_fd = os.open(
                    pending_name, flags, dir_fd=pending_fd
                )
                info = os.fstat(pending_body_fd)
                if (
                    not stat.S_ISREG(info.st_mode)
                    or info.st_nlink != 1
                    or stat.S_IMODE(info.st_mode) != 0o400
                    or info.st_size > _artifact_max_bytes(artifact)
                ):
                    raise StaticCensusEvidenceIntegrityError(
                        "unpublished pending artifact has invalid metadata"
                    )
                _require_named_regular_binding(
                    pending_fd,
                    pending_name,
                    pending_body_fd,
                    "unpublished pending artifact",
                )
                os.unlink(pending_name, dir_fd=pending_fd)
                os.fsync(pending_fd)
                if _entry_exists(pending_fd, pending_name):
                    raise StaticCensusEvidenceIntegrityError(
                        "pending publication path reappeared during cleanup"
                    )
                after = os.fstat(pending_body_fd)
                if (
                    not stat.S_ISREG(after.st_mode)
                    or after.st_nlink != 0
                    or (
                        after.st_dev,
                        after.st_ino,
                        after.st_mode,
                        after.st_size,
                        after.st_mtime_ns,
                    )
                    != (
                        info.st_dev,
                        info.st_ino,
                        info.st_mode,
                        info.st_size,
                        info.st_mtime_ns,
                    )
                ):
                    raise StaticCensusEvidenceIntegrityError(
                        "unlinked pending publication changed or retained a link"
                    )
            except OSError as error:
                raise StaticCensusEvidenceIntegrityError(
                    "pending publication is unavailable or unsafe"
                ) from error
            finally:
                if pending_body_fd >= 0:
                    os.close(pending_body_fd)
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
                raise StaticCensusEvidenceIntegrityError(
                    "pending and final publication links are inconsistent"
                )
            max_bytes = _artifact_max_bytes(artifact)
            pending_raw = _read_regular_descriptor(
                pending_body_fd,
                allowed_link_counts=(2,),
                allowed_modes=(0o400,),
                max_bytes=max_bytes,
            )
            final_raw = _read_regular_descriptor(
                final_body_fd,
                allowed_link_counts=(2,),
                allowed_modes=(0o400,),
                expected_size=len(pending_raw),
                max_bytes=max_bytes,
            )
            if pending_raw != final_raw:
                raise StaticCensusEvidenceIntegrityError(
                    "pending and final publication bytes are inconsistent"
                )
            _validate_artifact_raw(artifact, final_raw)
            _require_named_regular_binding(
                pending_fd,
                pending_name,
                pending_body_fd,
                "pending publication",
            )
            _require_named_regular_binding(
                target_fd,
                final_name,
                final_body_fd,
                "final publication",
            )
            os.unlink(pending_name, dir_fd=pending_fd)
            os.fsync(pending_fd)
            os.fsync(target_fd)
            if _entry_exists(pending_fd, pending_name):
                raise StaticCensusEvidenceIntegrityError(
                    "pending publication path reappeared during reconciliation"
                )
            reconciled = _read_regular_descriptor(
                final_body_fd,
                allowed_link_counts=(1,),
                allowed_modes=(0o400,),
                expected_size=len(final_raw),
                max_bytes=max_bytes,
            )
            if reconciled != final_raw:
                raise StaticCensusEvidenceIntegrityError(
                    "reconciled immutable artifact bytes changed"
                )
            _require_named_regular_binding(
                target_fd,
                final_name,
                final_body_fd,
                "reconciled publication",
            )
            _validate_artifact_raw(artifact, reconciled)
        except OSError as error:
            raise StaticCensusEvidenceIntegrityError(
                "pending publication links are unavailable or unsafe"
            ) from error
        finally:
            if pending_body_fd >= 0:
                os.close(pending_body_fd)
            if final_body_fd >= 0:
                os.close(final_body_fd)

    def _reconcile_pending_publications(
        self, capability: _StaticCensusMutationCapability
    ) -> None:
        self._require_mutation_capability(capability)
        self._require_lock()
        with self._pending_fd(
            create=self._create_operational,
            capability=(capability if self._create_operational else None),
        ) as pending_fd:
            observed = _stable_directory_entries(
                pending_fd, "pending publication directory"
            )
            if observed - set(_PENDING_TARGETS):
                raise StaticCensusEvidenceIntegrityError(
                    "pending directory contains a noncatalog path"
                )
            for pending_name in sorted(observed):
                scope, final_name, artifact = _PENDING_TARGETS[pending_name]
                try:
                    with self._target_fd(scope, create=False) as target_fd:
                        self._reconcile_pending_target(
                            capability,
                            pending_fd,
                            pending_name,
                            target_fd,
                            final_name,
                            artifact,
                        )
                except StaticCensusEvidenceIntegrityError as error:
                    if (
                        scope == "stage"
                        and isinstance(error.__cause__, FileNotFoundError)
                    ):
                        raise StaticCensusEvidenceIntegrityError(
                            "stage pending artifact exists without its fixed directory"
                        ) from error
                    raise
            if _stable_directory_entries(
                pending_fd, "pending publication directory"
            ):
                raise StaticCensusEvidenceIntegrityError(
                    "pending directory changed during reconciliation"
                )

    def _publish_raw(
        self,
        capability: _StaticCensusMutationCapability,
        scope: str,
        final_name: str,
        pending_name: str,
        artifact: str,
        raw: bytes,
        *,
        idempotent: bool,
    ) -> StaticCensusBodyRef:
        self._require_mutation_capability(capability)
        self._require_lock()
        if artifact != "contradiction" and self.contradiction_exists():
            raise StaticCensusEvidenceIntegrityError(
                "static-census evidence has an immutable contradiction"
            )
        if type(raw) is not bytes:
            raise TypeError("immutable artifact body must be exact bytes")
        if type(idempotent) is not bool:
            raise TypeError("idempotent must be an exact bool")
        if len(raw) > _artifact_max_bytes(artifact):
            raise ValueError("immutable artifact exceeds the byte limit")
        _validate_artifact_raw(artifact, raw)
        with self._pending_fd(
            create=True, capability=capability
        ) as pending_fd, self._target_fd(
            scope, create=True, capability=capability
        ) as target_fd:
            self._reconcile_pending_target(
                capability,
                pending_fd,
                pending_name,
                target_fd,
                final_name,
                artifact,
            )
            if _entry_exists(target_fd, final_name):
                existing = _read_regular_at(
                    target_fd,
                    final_name,
                    max_bytes=_artifact_max_bytes(artifact),
                )
                _validate_artifact_raw(artifact, existing)
                if idempotent and existing == raw:
                    return _body_ref(raw)
                raise StaticCensusEvidenceConflictError(
                    "immutable artifact already exists"
                )

            pending_flags = (
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_NONBLOCK", 0)
            )
            read_flags = (
                os.O_RDONLY
                | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_NONBLOCK", 0)
            )
            pending_body_fd = final_body_fd = -1
            try:
                try:
                    pending_body_fd = os.open(
                        pending_name, pending_flags, 0o400, dir_fd=pending_fd
                    )
                except OSError as error:
                    raise StaticCensusEvidenceConflictError(
                        "pending publication slot already exists"
                    ) from error
                view = memoryview(raw)
                while view:
                    written = os.write(pending_body_fd, view)
                    if written <= 0:
                        raise OSError(errno.EIO, "short immutable evidence write")
                    view = view[written:]
                os.fsync(pending_body_fd)
                os.fchmod(pending_body_fd, 0o400)
                os.fsync(pending_body_fd)
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
                        _require_named_regular_binding(
                            pending_fd,
                            pending_name,
                            pending_body_fd,
                            "unpublished pending artifact",
                        )
                        os.unlink(pending_name, dir_fd=pending_fd)
                        os.fsync(pending_fd)
                    except OSError as cleanup_error:
                        raise StaticCensusEvidenceIntegrityError(
                            "failed to remove an unpublished pending artifact"
                        ) from cleanup_error
                    raise StaticCensusEvidenceConflictError(
                        "immutable artifact already exists"
                    ) from error
                except OSError as error:
                    raise StaticCensusEvidenceIntegrityError(
                        "immutable artifact cannot be linked safely"
                    ) from error

                try:
                    final_body_fd = os.open(
                        final_name, read_flags, dir_fd=target_fd
                    )
                except OSError as error:
                    raise StaticCensusEvidenceIntegrityError(
                        "linked immutable artifact is unavailable or unsafe"
                    ) from error
                pending_info = os.fstat(pending_body_fd)
                final_info = os.fstat(final_body_fd)
                if (
                    not stat.S_ISREG(pending_info.st_mode)
                    or not stat.S_ISREG(final_info.st_mode)
                    or stat.S_IMODE(pending_info.st_mode) != 0o400
                    or stat.S_IMODE(final_info.st_mode) != 0o400
                    or pending_info.st_nlink != 2
                    or final_info.st_nlink != 2
                    or pending_info.st_size != len(raw)
                    or final_info.st_size != len(raw)
                    or (pending_info.st_dev, pending_info.st_ino)
                    != (final_info.st_dev, final_info.st_ino)
                ):
                    raise StaticCensusEvidenceIntegrityError(
                        "linked publication is not the created pending artifact"
                    )
                _require_named_regular_binding(
                    pending_fd,
                    pending_name,
                    pending_body_fd,
                    "linked pending publication",
                )
                _require_named_regular_binding(
                    target_fd,
                    final_name,
                    final_body_fd,
                    "linked final publication",
                )
                linked = _read_regular_descriptor(
                    final_body_fd,
                    allowed_link_counts=(2,),
                    allowed_modes=(0o400,),
                    expected_size=len(raw),
                    max_bytes=_artifact_max_bytes(artifact),
                )
                if linked != raw:
                    raise StaticCensusEvidenceIntegrityError(
                        "linked immutable artifact bytes changed"
                    )
                os.fsync(target_fd)
                _require_named_regular_binding(
                    pending_fd,
                    pending_name,
                    pending_body_fd,
                    "linked pending publication",
                )
                _require_named_regular_binding(
                    target_fd,
                    final_name,
                    final_body_fd,
                    "linked final publication",
                )
                os.unlink(pending_name, dir_fd=pending_fd)
                os.fsync(pending_fd)
                os.fsync(target_fd)
                if _entry_exists(pending_fd, pending_name):
                    raise StaticCensusEvidenceIntegrityError(
                        "pending publication path reappeared after unlink"
                    )
                observed = _read_regular_descriptor(
                    final_body_fd,
                    allowed_link_counts=(1,),
                    allowed_modes=(0o400,),
                    expected_size=len(raw),
                    max_bytes=_artifact_max_bytes(artifact),
                )
                if observed != raw:
                    raise StaticCensusEvidenceIntegrityError(
                        "published immutable artifact bytes changed"
                    )
                _require_named_regular_binding(
                    target_fd,
                    final_name,
                    final_body_fd,
                    "published immutable artifact",
                )
                _validate_artifact_raw(artifact, observed)
            finally:
                if final_body_fd >= 0:
                    os.close(final_body_fd)
                if pending_body_fd >= 0:
                    os.close(pending_body_fd)
        return _body_ref(raw)

    def _publish_bootstrap(
        self, capability: _StaticCensusMutationCapability, value: Any
    ) -> StaticCensusBodyRef:
        self._require_mutation_capability(capability)
        return self._publish_raw(
            capability,
            "root",
            _BOOTSTRAP_FILE,
            "root--bootstrap.json.pending",
            "bootstrap",
            _canonical_json_bytes(value),
            idempotent=True,
        )

    def read_bootstrap(self) -> Dict[str, Any]:
        self._require_open()
        raw = _read_regular_at(self._root_fd, _BOOTSTRAP_FILE)
        value = _load_canonical_json_bytes(raw, label="bootstrap")
        if type(value) is not dict:
            raise StaticCensusEvidenceIntegrityError(
                "bootstrap must be a JSON object"
            )
        return value

    def bootstrap_exists(self) -> bool:
        self._require_open()
        if not _entry_exists(self._root_fd, _BOOTSTRAP_FILE):
            return False
        self.read_bootstrap()
        return True

    def _publish_contradiction(
        self, capability: _StaticCensusMutationCapability, value: Any
    ) -> StaticCensusBodyRef:
        self._require_mutation_capability(capability)
        return self._publish_raw(
            capability,
            "root",
            _CONTRADICTION_FILE,
            "root--contradiction.json.pending",
            "contradiction",
            _canonical_json_bytes(value),
            idempotent=True,
        )

    def contradiction_exists(self) -> bool:
        self._require_open()
        if not _entry_exists(self._root_fd, _CONTRADICTION_FILE):
            return False
        _load_canonical_json_bytes(
            _read_regular_at(self._root_fd, _CONTRADICTION_FILE),
            label="contradiction",
        )
        return True

    def _publish_stage_json(
        self,
        capability: _StaticCensusMutationCapability,
        artifact: str,
        value: Any,
    ) -> StaticCensusBodyRef:
        self._require_mutation_capability(capability)
        if (
            type(artifact) is not str
            or artifact not in _STAGE_ARTIFACT_FILES
            or artifact == "report"
        ):
            raise ValueError("artifact is not a JSON lifecycle slot")
        filename = _STAGE_ARTIFACT_FILES[artifact]
        return self._publish_raw(
            capability,
            "stage",
            filename,
            "stage--{}.pending".format(filename),
            artifact,
            _canonical_json_bytes(value),
            idempotent=False,
        )

    def _publish_report_bytes(
        self, capability: _StaticCensusMutationCapability, raw: bytes
    ) -> StaticCensusBodyRef:
        self._require_mutation_capability(capability)
        filename = _STAGE_ARTIFACT_FILES["report"]
        return self._publish_raw(
            capability,
            "stage",
            filename,
            "stage--{}.pending".format(filename),
            "report",
            raw,
            idempotent=False,
        )

    def read_stage_json(self, artifact: str) -> Any:
        if (
            type(artifact) is not str
            or artifact not in _STAGE_ARTIFACT_FILES
            or artifact == "report"
        ):
            raise ValueError("artifact is not a JSON lifecycle slot")
        with self._stage_fd(create=False) as stage_fd:
            return _load_canonical_json_bytes(
                _read_regular_at(stage_fd, _STAGE_ARTIFACT_FILES[artifact]),
                label=artifact,
            )

    def read_report_bytes(self) -> bytes:
        with self._stage_fd(create=False) as stage_fd:
            raw = _read_regular_at(
                stage_fd,
                _STAGE_ARTIFACT_FILES["report"],
                max_bytes=_MAX_REPORT_BYTES,
            )
        _reconstruct_report(raw)
        return raw

    def stage_artifact_exists(self, artifact: str) -> bool:
        if type(artifact) is not str or artifact not in _STAGE_ARTIFACT_FILES:
            raise ValueError("artifact is not in the fixed stage catalog")
        self._require_open()
        if not _entry_exists(self._root_fd, _STAGES_DIRECTORY):
            self._require_path_binding()
            return False
        stages_fd = _open_existing_directory_at(
            self._root_fd, _STAGES_DIRECTORY
        )
        try:
            entries = _stable_directory_entries(
                stages_fd, "static-census stages directory"
            )
            if entries - {STAGE_PROTOCOL_ID_V1}:
                raise StaticCensusEvidenceIntegrityError(
                    "stages directory contains a noncatalog path"
                )
            if STAGE_PROTOCOL_ID_V1 not in entries:
                if _stable_directory_entries(
                    stages_fd, "static-census stages directory"
                ) != entries:
                    raise StaticCensusEvidenceIntegrityError(
                        "stages directory changed during artifact lookup"
                    )
                return False
            stage_fd = _open_existing_directory_at(
                stages_fd, STAGE_PROTOCOL_ID_V1
            )
            try:
                stage_entries = _stable_directory_entries(
                    stage_fd, "static-census stage directory"
                )
                allowed = set(_STAGE_ARTIFACT_FILES.values())
                if stage_entries - allowed:
                    raise StaticCensusEvidenceIntegrityError(
                        "stage directory contains a noncatalog path"
                    )
                filename = _STAGE_ARTIFACT_FILES[artifact]
                if filename not in stage_entries:
                    return False
                raw = _read_regular_at(
                    stage_fd,
                    filename,
                    max_bytes=_artifact_max_bytes(artifact),
                )
                _validate_artifact_raw(artifact, raw)
                if _stable_directory_entries(
                    stage_fd, "static-census stage directory"
                ) != stage_entries:
                    raise StaticCensusEvidenceIntegrityError(
                        "stage directory changed during artifact lookup"
                    )
                return True
            finally:
                try:
                    _require_named_directory_binding(
                        stages_fd,
                        STAGE_PROTOCOL_ID_V1,
                        stage_fd,
                        "static-census stage directory",
                    )
                finally:
                    os.close(stage_fd)
        finally:
            try:
                _require_named_directory_binding(
                    self._root_fd,
                    _STAGES_DIRECTORY,
                    stages_fd,
                    "stages directory",
                )
                self._require_path_binding()
            finally:
                os.close(stages_fd)

    def _scan_fixed_catalog_snapshot_core(
        self, *, retain_stage_raw: bool
    ) -> Tuple[
        Dict[str, Optional[StaticCensusBodyRef]], Dict[str, bytes]
    ]:
        if type(retain_stage_raw) is not bool:
            raise TypeError("retain_stage_raw must be an exact bool")
        self._require_open()
        result: Dict[str, Optional[StaticCensusBodyRef]] = {
            "bootstrap": None,
            "contradiction": None,
            **{artifact: None for artifact in _STAGE_ARTIFACT_FILES},
        }
        retained_raw: Dict[str, bytes] = {}
        root_metadata = _directory_metadata_v1(
            self._root_fd, "static-census evidence root"
        )
        root_entries = _stable_directory_entries(
            self._root_fd, "static-census evidence root"
        )
        if root_entries - _ROOT_CATALOG:
            raise StaticCensusEvidenceIntegrityError(
                "evidence root contains a noncatalog path"
            )
        if _BOOTSTRAP_FILE in root_entries:
            raw = _read_regular_at(self._root_fd, _BOOTSTRAP_FILE)
            _load_canonical_json_bytes(raw, label="bootstrap")
            result["bootstrap"] = _body_ref(raw)
        if _CONTRADICTION_FILE in root_entries:
            raw = _read_regular_at(self._root_fd, _CONTRADICTION_FILE)
            _load_canonical_json_bytes(raw, label="contradiction")
            result["contradiction"] = _body_ref(raw)
        if _LOCKS_DIRECTORY in root_entries:
            locks_fd = _open_existing_directory_at(
                self._root_fd, _LOCKS_DIRECTORY, allowed_modes=(0o700,)
            )
            try:
                locks_metadata = _directory_metadata_v1(
                    locks_fd, "static-census locks directory"
                )
                entries = _stable_directory_entries(
                    locks_fd, "static-census locks directory"
                )
                allowed = {STAGE_PROTOCOL_ID_V1 + ".lock"}
                if entries - allowed:
                    raise StaticCensusEvidenceIntegrityError(
                        "locks directory contains a noncatalog path"
                    )
                if entries:
                    raw = _read_regular_at(
                        locks_fd,
                        STAGE_PROTOCOL_ID_V1 + ".lock",
                        allowed_modes=(0o600,),
                        expected_size=0,
                        max_bytes=0,
                    )
                    if raw:
                        raise StaticCensusEvidenceIntegrityError(
                            "stage lock must remain empty"
                        )
                if _stable_directory_entries(
                    locks_fd, "static-census locks directory"
                ) != entries:
                    raise StaticCensusEvidenceIntegrityError(
                        "locks directory changed during catalog scan"
                    )
                _require_directory_metadata_v1(
                    locks_fd,
                    locks_metadata,
                    "static-census locks directory",
                )
            finally:
                try:
                    _require_named_directory_binding(
                        self._root_fd,
                        _LOCKS_DIRECTORY,
                        locks_fd,
                        "locks directory",
                    )
                finally:
                    os.close(locks_fd)
        if _PENDING_DIRECTORY in root_entries:
            pending_fd = _open_existing_directory_at(
                self._root_fd, _PENDING_DIRECTORY, allowed_modes=(0o700,)
            )
            try:
                pending_metadata = _directory_metadata_v1(
                    pending_fd, "pending publication directory"
                )
                pending_entries = _stable_directory_entries(
                    pending_fd, "pending publication directory"
                )
                if pending_entries - set(_PENDING_TARGETS):
                    raise StaticCensusEvidenceIntegrityError(
                        "pending directory contains a noncatalog path"
                    )
                if pending_entries:
                    raise StaticCensusEvidenceIntegrityError(
                        "pending publication remains during catalog scan"
                    )
                if _stable_directory_entries(
                    pending_fd, "pending publication directory"
                ) != pending_entries:
                    raise StaticCensusEvidenceIntegrityError(
                        "pending directory changed during catalog scan"
                    )
                _require_directory_metadata_v1(
                    pending_fd,
                    pending_metadata,
                    "pending publication directory",
                )
            finally:
                try:
                    _require_named_directory_binding(
                        self._root_fd,
                        _PENDING_DIRECTORY,
                        pending_fd,
                        "pending directory",
                    )
                finally:
                    os.close(pending_fd)
        if _STAGES_DIRECTORY not in root_entries:
            if _stable_directory_entries(
                self._root_fd, "static-census evidence root"
            ) != root_entries:
                raise StaticCensusEvidenceIntegrityError(
                    "evidence root changed during catalog scan"
                )
            self._require_path_binding()
            _require_directory_metadata_v1(
                self._root_fd,
                root_metadata,
                "static-census evidence root",
            )
            return result, retained_raw
        stages_fd = _open_existing_directory_at(
            self._root_fd, _STAGES_DIRECTORY
        )
        try:
            stages_metadata = _directory_metadata_v1(
                stages_fd, "static-census stages directory"
            )
            entries = _stable_directory_entries(
                stages_fd, "static-census stages directory"
            )
            if entries - {STAGE_PROTOCOL_ID_V1}:
                raise StaticCensusEvidenceIntegrityError(
                    "stages directory contains a noncatalog path"
                )
            if STAGE_PROTOCOL_ID_V1 not in entries:
                if _stable_directory_entries(
                    stages_fd, "static-census stages directory"
                ) != entries:
                    raise StaticCensusEvidenceIntegrityError(
                        "stages directory changed during catalog scan"
                    )
                if _stable_directory_entries(
                    self._root_fd, "static-census evidence root"
                ) != root_entries:
                    raise StaticCensusEvidenceIntegrityError(
                        "evidence root changed during catalog scan"
                    )
                self._require_path_binding()
                _require_directory_metadata_v1(
                    stages_fd,
                    stages_metadata,
                    "static-census stages directory",
                )
                _require_directory_metadata_v1(
                    self._root_fd,
                    root_metadata,
                    "static-census evidence root",
                )
                return result, retained_raw
            stage_fd = _open_existing_directory_at(
                stages_fd, STAGE_PROTOCOL_ID_V1
            )
            try:
                stage_metadata = _directory_metadata_v1(
                    stage_fd, "static-census stage directory"
                )
                stage_entries = _stable_directory_entries(
                    stage_fd, "static-census stage directory"
                )
                allowed_files = set(_STAGE_ARTIFACT_FILES.values())
                if stage_entries - allowed_files:
                    raise StaticCensusEvidenceIntegrityError(
                        "stage directory contains a noncatalog path"
                    )
                by_file = {
                    filename: artifact
                    for artifact, filename in _STAGE_ARTIFACT_FILES.items()
                }
                body_fds: Dict[str, int] = {}
                body_metadata: Dict[str, Tuple[int, ...]] = {}
                read_flags = (
                    os.O_RDONLY
                    | getattr(os, "O_NOFOLLOW", 0)
                    | getattr(os, "O_NONBLOCK", 0)
                )
                try:
                    # Open and bind every catalog entry before reading any body.
                    # Keeping all descriptors alive until every read completes
                    # makes later in-place writes and name swaps observable.
                    for filename in sorted(stage_entries):
                        try:
                            body_fd = os.open(
                                filename, read_flags, dir_fd=stage_fd
                            )
                        except OSError as error:
                            raise StaticCensusEvidenceIntegrityError(
                                "stage artifact is unavailable or unsafe"
                            ) from error
                        body_fds[filename] = body_fd
                        body_metadata[filename] = (
                            _regular_descriptor_metadata_v1(
                                body_fd, "static-census stage artifact"
                            )
                        )
                        _require_named_regular_binding(
                            stage_fd,
                            filename,
                            body_fd,
                            "static-census stage artifact",
                        )
                    for filename in sorted(stage_entries):
                        artifact = by_file[filename]
                        raw = _read_regular_descriptor(
                            body_fds[filename],
                            max_bytes=_artifact_max_bytes(artifact),
                        )
                        _validate_artifact_raw(artifact, raw)
                        result[artifact] = _body_ref(raw)
                        if retain_stage_raw:
                            retained_raw[artifact] = raw
                    for filename in sorted(stage_entries):
                        body_fd = body_fds[filename]
                        if (
                            _regular_descriptor_metadata_v1(
                                body_fd, "static-census stage artifact"
                            )
                            != body_metadata[filename]
                        ):
                            raise StaticCensusEvidenceIntegrityError(
                                "stage artifact changed across the evidence snapshot"
                            )
                        _require_named_regular_binding(
                            stage_fd,
                            filename,
                            body_fd,
                            "static-census stage artifact",
                        )
                finally:
                    for body_fd in body_fds.values():
                        os.close(body_fd)
                if _stable_directory_entries(
                    stage_fd, "static-census stage directory"
                ) != stage_entries:
                    raise StaticCensusEvidenceIntegrityError(
                        "stage directory changed during catalog scan"
                    )
                _require_directory_metadata_v1(
                    stage_fd,
                    stage_metadata,
                    "static-census stage directory",
                )
            finally:
                try:
                    _require_named_directory_binding(
                        stages_fd,
                        STAGE_PROTOCOL_ID_V1,
                        stage_fd,
                        "static-census stage directory",
                    )
                finally:
                    os.close(stage_fd)
            if _stable_directory_entries(
                stages_fd, "static-census stages directory"
            ) != entries:
                raise StaticCensusEvidenceIntegrityError(
                    "stages directory changed during catalog scan"
                )
            _require_directory_metadata_v1(
                stages_fd,
                stages_metadata,
                "static-census stages directory",
            )
        finally:
            try:
                _require_named_directory_binding(
                    self._root_fd,
                    _STAGES_DIRECTORY,
                    stages_fd,
                    "stages directory",
                )
            finally:
                os.close(stages_fd)
        if _stable_directory_entries(
            self._root_fd, "static-census evidence root"
        ) != root_entries:
            raise StaticCensusEvidenceIntegrityError(
                "evidence root changed during catalog scan"
            )
        self._require_path_binding()
        _require_directory_metadata_v1(
            self._root_fd,
            root_metadata,
            "static-census evidence root",
        )
        return result, retained_raw

    def _scan_fixed_catalog_snapshot(
        self, *, retain_stage_raw: bool
    ) -> Tuple[
        Dict[str, Optional[StaticCensusBodyRef]], Dict[str, bytes]
    ]:
        """Capture bootstrap and stage bodies under one descriptor-held view."""

        if type(retain_stage_raw) is not bool:
            raise TypeError("retain_stage_raw must be an exact bool")
        self._require_open()
        root_metadata = _directory_metadata_v1(
            self._root_fd, "static-census evidence root"
        )
        bootstrap_fd = -1
        bootstrap_metadata: Optional[Tuple[int, ...]] = None
        bootstrap_raw: Optional[bytes] = None
        bootstrap_ref: Optional[StaticCensusBodyRef] = None
        bootstrap_present = False
        try:
            bootstrap_present = _entry_exists(
                self._root_fd, _BOOTSTRAP_FILE
            )
            if bootstrap_present:
                read_flags = (
                    os.O_RDONLY
                    | getattr(os, "O_NOFOLLOW", 0)
                    | getattr(os, "O_NONBLOCK", 0)
                )
                try:
                    bootstrap_fd = os.open(
                        _BOOTSTRAP_FILE,
                        read_flags,
                        dir_fd=self._root_fd,
                    )
                except OSError as error:
                    raise StaticCensusEvidenceIntegrityError(
                        "bootstrap is unavailable or unsafe"
                    ) from error
                bootstrap_metadata = _regular_descriptor_metadata_v1(
                    bootstrap_fd, "bootstrap"
                )
                _require_named_regular_binding(
                    self._root_fd,
                    _BOOTSTRAP_FILE,
                    bootstrap_fd,
                    "bootstrap",
                )
                bootstrap_raw = _read_regular_descriptor(bootstrap_fd)
                bootstrap_value = _load_canonical_json_bytes(
                    bootstrap_raw, label="bootstrap"
                )
                if type(bootstrap_value) is not dict:
                    raise StaticCensusEvidenceIntegrityError(
                        "bootstrap must be a JSON object"
                    )
                bootstrap_ref = _body_ref(bootstrap_raw)

            catalog, retained_raw = self._scan_fixed_catalog_snapshot_core(
                retain_stage_raw=retain_stage_raw
            )
            if (catalog["bootstrap"] is not None) != bootstrap_present:
                raise StaticCensusEvidenceIntegrityError(
                    "bootstrap presence changed across the evidence snapshot"
                )
            if bootstrap_present and catalog["bootstrap"] != bootstrap_ref:
                raise StaticCensusEvidenceIntegrityError(
                    "bootstrap changed across the evidence snapshot"
                )
            if retain_stage_raw and bootstrap_raw is not None:
                retained_raw["bootstrap"] = bootstrap_raw
            return catalog, retained_raw
        finally:
            try:
                if bootstrap_fd >= 0:
                    if (
                        _regular_descriptor_metadata_v1(
                            bootstrap_fd, "bootstrap"
                        )
                        != bootstrap_metadata
                    ):
                        raise StaticCensusEvidenceIntegrityError(
                            "bootstrap changed across the evidence snapshot"
                        )
                    _require_named_regular_binding(
                        self._root_fd,
                        _BOOTSTRAP_FILE,
                        bootstrap_fd,
                        "bootstrap",
                    )
                self._require_path_binding()
                _require_directory_metadata_v1(
                    self._root_fd,
                    root_metadata,
                    "static-census evidence root",
                )
            finally:
                if bootstrap_fd >= 0:
                    os.close(bootstrap_fd)

    def scan_fixed_catalog(self) -> Dict[str, Optional[StaticCensusBodyRef]]:
        catalog, _retained_raw = self._scan_fixed_catalog_snapshot(
            retain_stage_raw=False
        )
        return catalog


@contextlib.contextmanager
def _open_recovery_store_v1(
    capability: _StaticCensusMutationCapability,
    root: os.PathLike[str],
) -> Iterator[Optional[_StaticCensusEvidenceStore]]:
    """Open an existing root; a missing root causes no filesystem write."""

    _require_mutation_capability_v1(capability)
    try:
        store = _StaticCensusEvidenceStore._for_recovery(capability, root)
    except StaticCensusEvidenceIntegrityError as error:
        if isinstance(error.__cause__, FileNotFoundError):
            yield None
            return
        raise
    try:
        yield store
    finally:
        store.close()


_RECONSTRUCT_REPORT_V1 = reconstruction.reconstruct_static_census_report_artifact_v1


def _validated_report_summary(value: Any) -> Dict[str, Any]:
    summary = _exact_keys(
        value,
        (
            "report_digest",
            "setup_orbit_table_root",
            "skeleton_authority_root",
            "ordered_shard_commitment_root",
            "population",
            "eligibility",
        ),
        "report summary",
    )
    for key in (
        "report_digest",
        "setup_orbit_table_root",
        "skeleton_authority_root",
        "ordered_shard_commitment_root",
    ):
        _exact_hex(summary[key], 64, "report summary {}".format(key))

    population = _exact_keys(
        summary["population"],
        (
            "skeleton_count",
            "factorized_carrier_count",
            "labeled_setup_count",
            "paired_first_player_member_count",
            "weight_histogram",
        ),
        "report summary population",
    )
    fixed_counts = {
        "skeleton_count": _FIXED_SKELETON_COUNT_V1,
        "factorized_carrier_count": _FIXED_FACTORIZED_CARRIER_COUNT_V1,
        "labeled_setup_count": _FIXED_LABELED_SETUP_COUNT_V1,
        "paired_first_player_member_count": _FIXED_PAIRED_MEMBER_COUNT_V1,
    }
    for key, expected in fixed_counts.items():
        if type(population[key]) is not int or population[key] != expected:
            raise StaticCensusEvidenceIntegrityError(
                "report summary population {} drifted".format(key)
            )
    histogram = _exact_keys(
        population["weight_histogram"],
        ("1", "2", "4", "8"),
        "report summary weight histogram",
    )
    for weight, count in histogram.items():
        if type(count) is not int or count < 0:
            raise StaticCensusEvidenceIntegrityError(
                "report summary weight {} count is invalid".format(weight)
            )
    if (
        sum(histogram.values()) != _FIXED_FACTORIZED_CARRIER_COUNT_V1
        or sum(int(weight) * count for weight, count in histogram.items())
        != _FIXED_LABELED_SETUP_COUNT_V1
        or _FIXED_PAIRED_MEMBER_COUNT_V1
        != 2 * _FIXED_LABELED_SETUP_COUNT_V1
    ):
        raise StaticCensusEvidenceIntegrityError(
            "report summary population arithmetic drifted"
        )

    eligibility = _exact_keys(
        summary["eligibility"],
        (
            "representative_eligible_count",
            "weighted_eligible_count",
            "paired_first_player_eligible_member_count",
        ),
        "report summary eligibility",
    )
    for key, count in eligibility.items():
        if type(count) is not int or count < 0:
            raise StaticCensusEvidenceIntegrityError(
                "report summary {} is invalid".format(key)
            )
    if (
        eligibility["representative_eligible_count"]
        > _FIXED_FACTORIZED_CARRIER_COUNT_V1
        or eligibility["weighted_eligible_count"]
        < eligibility["representative_eligible_count"]
        or eligibility["weighted_eligible_count"]
        > _FIXED_LABELED_SETUP_COUNT_V1
        or eligibility["paired_first_player_eligible_member_count"]
        != 2 * eligibility["weighted_eligible_count"]
    ):
        raise StaticCensusEvidenceIntegrityError(
            "report summary eligibility arithmetic drifted"
        )
    return _json_copy(summary, "report summary")


def _validate_summary_against_report(
    report_value: Any, summary_value: Any
) -> None:
    if type(report_value) is not dict:
        raise StaticCensusEvidenceIntegrityError(
            "reconstructed report changed type"
        )
    summary = _validated_report_summary(summary_value)
    try:
        authorities = report_value["authorities"]
        roots = report_value["roots"]
        population = report_value["population"]
        eligibility = report_value["eligibility"]
        setup_root = authorities["setup_orbit_table"]["descriptor_root"]
        skeleton_root = authorities["skeleton_authority"]["descriptor_root"]
        shard_root = roots["ordered_shard_commitment_root"]
        report_digest = report_value["report_digest"]
    except (KeyError, TypeError) as error:
        raise StaticCensusEvidenceIntegrityError(
            "reconstructed report lacks its summary sources"
        ) from error
    if type(authorities) is not dict or type(roots) is not dict:
        raise StaticCensusEvidenceIntegrityError(
            "reconstructed report summary source changed type"
        )
    expected_scalars = {
        "report_digest": report_digest,
        "setup_orbit_table_root": setup_root,
        "skeleton_authority_root": skeleton_root,
        "ordered_shard_commitment_root": shard_root,
    }
    if any(
        type(value) is not str or value != summary[key]
        for key, value in expected_scalars.items()
    ):
        raise StaticCensusEvidenceIntegrityError(
            "report summary roots do not match the reconstructed report"
        )
    if _canonical_json_bytes(population) != _canonical_json_bytes(
        summary["population"]
    ):
        raise StaticCensusEvidenceIntegrityError(
            "report summary population does not match the reconstructed report"
        )
    if type(eligibility) is not dict:
        raise StaticCensusEvidenceIntegrityError(
            "reconstructed report eligibility changed type"
        )
    selected_eligibility = {
        key: eligibility.get(key) for key in summary["eligibility"]
    }
    if _canonical_json_bytes(selected_eligibility) != _canonical_json_bytes(
        summary["eligibility"]
    ):
        raise StaticCensusEvidenceIntegrityError(
            "report summary eligibility does not match the reconstructed report"
        )


def _reconstruct_report(raw: bytes) -> Dict[str, Any]:
    if (
        reconstruction.reconstruct_static_census_report_artifact_v1
        is not _RECONSTRUCT_REPORT_V1
    ):
        raise StaticCensusEvidenceIntegrityError(
            "stored-report reconstructor binding changed"
        )
    try:
        value = _RECONSTRUCT_REPORT_V1(raw)
    except (TypeError, ValueError) as error:
        raise StaticCensusEvidenceIntegrityError(
            "static-census report reconstruction failed"
        ) from error
    envelope = _exact_keys(
        value,
        ("report", "report_ref", "report_summary"),
        "report reconstruction",
    )
    report_ref = _validate_body_ref(
        envelope["report_ref"], "reconstructed report reference"
    )
    expected_ref = _body_ref(raw)
    if report_ref != expected_ref:
        raise StaticCensusEvidenceIntegrityError(
            "reconstructed report reference does not match its bytes"
        )
    _validate_summary_against_report(
        envelope["report"], envelope["report_summary"]
    )
    # The report may legitimately approach the separately fixed five-million
    # node ceiling.  The reconstructor already returned a detached tree; avoid
    # routing that full tree through this module's much smaller metadata cap.
    return envelope


def _validate_rooted_reference(
    value: Any,
    *,
    kind: str,
    expected_artifact_type: str,
    label: str,
) -> Dict[str, Any]:
    _require_protocol_bindings()
    if kind != "production_closure_root":
        raise StaticCensusEvidenceIntegrityError(
            "unsupported rooted-reference kind"
        )
    envelope = _exact_keys(
        value, ("artifact_type", "identity", "payload"), label
    )
    if _exact_string(
        envelope["artifact_type"], "{} artifact type".format(label)
    ) != expected_artifact_type:
        raise StaticCensusEvidenceIntegrityError(
            "{} artifact type drifted".format(label)
        )
    identity = _exact_hex(
        envelope["identity"], 64, "{} identity".format(label)
    )
    payload = _exact_keys(
        envelope["payload"],
        _FIXED_PRODUCTION_CLOSURE_KEYS,
        "{} payload".format(label),
    )
    if identity != _domain_identity(_FIXED_PRODUCTION_CLOSURE_DOMAIN, payload):
        raise StaticCensusEvidenceIntegrityError(
            "{} identity does not reconstruct".format(label)
        )
    return _json_copy(envelope, label)


def _make_identity_envelope(
    contract: StaticCensusEvidenceContract,
    kind: str,
    artifact_type: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    contract = _require_fixed_contract(contract)
    if tuple(payload) != contract.identity_keys(kind):
        raise StaticCensusEvidenceIntegrityError(
            "{} payload schema drifted".format(kind)
        )
    return {
        "artifact_type": artifact_type,
        "identity": _domain_identity(contract.identity_domain(kind), payload),
        "payload": _json_copy(payload, "{} payload".format(kind)),
    }


def _validate_identity_envelope(
    contract: StaticCensusEvidenceContract,
    value: Any,
    kind: str,
    artifact_type: str,
) -> Dict[str, Any]:
    contract = _require_fixed_contract(contract)
    envelope = _exact_keys(
        value, ("artifact_type", "identity", "payload"), artifact_type
    )
    if _exact_string(
        envelope["artifact_type"], "{} artifact type".format(kind)
    ) != artifact_type:
        raise StaticCensusEvidenceIntegrityError(
            "{} artifact type drifted".format(kind)
        )
    identity = _exact_hex(envelope["identity"], 64, "{} identity".format(kind))
    payload = _exact_keys(
        envelope["payload"], contract.identity_keys(kind), "{} payload".format(kind)
    )
    if identity != _domain_identity(contract.identity_domain(kind), payload):
        raise StaticCensusEvidenceIntegrityError(
            "{} identity does not reconstruct".format(kind)
        )
    return _json_copy(envelope, artifact_type)


def build_bootstrap_v1(
    protocol_value: Any, production_closure_value: Any
) -> Dict[str, Any]:
    """Build the sole bootstrap from an already authenticated protocol/closure."""

    _require_protocol_bindings()
    try:
        protocol_record = _VALIDATE_PROTOCOL_V1(protocol_value)
    except (TypeError, ValueError) as error:
        raise StaticCensusEvidenceIntegrityError(
            "static-census protocol is invalid"
        ) from error
    closure = _validate_rooted_reference(
        production_closure_value,
        kind="production_closure_root",
        expected_artifact_type=_FIXED_PRODUCTION_CLOSURE_ARTIFACT_TYPE_V1,
        label="production closure",
    )
    closure_payload = closure["payload"]
    active_plan_ref = _validate_body_ref(
        closure_payload["active_plan_ref"], "closure active-plan reference"
    ).as_dict()
    if closure_payload["stage_id"] != STAGE_ID_V1:
        raise StaticCensusEvidenceIntegrityError(
            "production closure belongs to another stage"
        )
    source_commit = _exact_hex(
        closure_payload["source_commit"], 40, "production source commit"
    )
    source_tree = _exact_hex(
        closure_payload["source_tree"], 40, "production source tree"
    )
    protocol_ref = _canonical_body_ref(protocol_record).as_dict()
    payload = {
        "active_plan_ref": active_plan_ref,
        "evidence_protocol_id": _FIXED_EVIDENCE_PROTOCOL_ID_V1,
        "production_closure_root": closure["identity"],
        "protocol_id": _FIXED_PROTOCOL_ID_V1,
        "protocol_ref": protocol_ref,
        "protocol_root": _FIXED_PROTOCOL_ROOT_V1,
        "source_commit": source_commit,
        "source_tree": source_tree,
        "stage_id": STAGE_ID_V1,
        "stage_protocol_id": STAGE_PROTOCOL_ID_V1,
    }
    if tuple(payload) != _FIXED_BOOTSTRAP_KEYS:
        raise StaticCensusEvidenceIntegrityError(
            "bootstrap payload schema drifted"
        )
    return {
        "artifact_type": _BOOTSTRAP_ARTIFACT_TYPE,
        "identity": _domain_identity(
            _FIXED_BOOTSTRAP_DOMAIN, payload
        ),
        "payload": _json_copy(payload, "bootstrap payload"),
        "references": {
            "production_closure": closure,
            "protocol": _json_copy(protocol_record, "protocol reference"),
        },
    }


def validate_bootstrap_v1(value: Any) -> Dict[str, Any]:
    _require_protocol_bindings()
    envelope = _exact_keys(
        value,
        ("artifact_type", "identity", "payload", "references"),
        "static-census bootstrap",
    )
    if envelope["artifact_type"] != _BOOTSTRAP_ARTIFACT_TYPE:
        raise StaticCensusEvidenceIntegrityError(
            "static-census bootstrap artifact type drifted"
        )
    _exact_hex(envelope["identity"], 64, "bootstrap identity")
    _exact_keys(
        envelope["payload"],
        _FIXED_BOOTSTRAP_KEYS,
        "bootstrap payload",
    )
    references = _exact_keys(
        envelope["references"],
        ("production_closure", "protocol"),
        "bootstrap references",
    )
    expected = build_bootstrap_v1(
        references["protocol"], references["production_closure"]
    )
    if _canonical_json_bytes(envelope) != _canonical_json_bytes(expected):
        raise StaticCensusEvidenceIntegrityError(
            "static-census bootstrap does not reconstruct"
        )
    return _json_copy(envelope, "validated bootstrap")


def _require_contract_bootstrap(
    contract: StaticCensusEvidenceContract, bootstrap_value: Any
) -> Dict[str, Any]:
    contract = _require_fixed_contract(contract)
    bootstrap = validate_bootstrap_v1(bootstrap_value)
    payload = bootstrap["payload"]
    expected = {
        "evidence_protocol_id": contract.evidence_protocol_id,
        "protocol_id": contract.protocol_id,
        "protocol_root": contract.protocol_root,
        "stage_id": contract.stage_id,
        "stage_protocol_id": contract.stage_protocol_id,
    }
    for key, expected_value in expected.items():
        if payload[key] != expected_value:
            raise StaticCensusEvidenceIntegrityError(
                "bootstrap {} differs from evidence contract".format(key)
            )
    return bootstrap


def build_reservation_v1(
    contract: StaticCensusEvidenceContract, bootstrap_value: Any
) -> Dict[str, Any]:
    bootstrap = _require_contract_bootstrap(contract, bootstrap_value)
    source = bootstrap["payload"]
    payload = {
        "bootstrap_root": bootstrap["identity"],
        "evidence_protocol_id": contract.evidence_protocol_id,
        "production_closure_root": source["production_closure_root"],
        "protocol_id": contract.protocol_id,
        "protocol_root": contract.protocol_root,
        "stage_id": contract.stage_id,
        "stage_protocol_id": contract.stage_protocol_id,
    }
    return _make_identity_envelope(
        contract, "reservation_id", _RESERVATION_ARTIFACT_TYPE, payload
    )


def _validate_reservation_v1(
    contract: StaticCensusEvidenceContract,
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
    if _canonical_json_bytes(reservation) != _canonical_json_bytes(expected):
        raise StaticCensusEvidenceIntegrityError(
            "reservation does not reconstruct from bootstrap"
        )
    return reservation


def build_attempt_v1(
    contract: StaticCensusEvidenceContract,
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
        "stage_id": contract.stage_id,
        "stage_protocol_id": contract.stage_protocol_id,
    }
    return _make_identity_envelope(
        contract, "attempt_id", _ATTEMPT_ARTIFACT_TYPE, payload
    )


def _validate_attempt_v1(
    contract: StaticCensusEvidenceContract,
    bootstrap_value: Any,
    reservation_value: Any,
    attempt_value: Any,
) -> Dict[str, Any]:
    attempt = _validate_identity_envelope(
        contract, attempt_value, "attempt_id", _ATTEMPT_ARTIFACT_TYPE
    )
    payload = attempt["payload"]
    if type(payload["attempt_index"]) is not int or payload["attempt_index"] != 0:
        raise StaticCensusEvidenceIntegrityError("attempt index drifted")
    expected = build_attempt_v1(
        contract, bootstrap_value, reservation_value
    )
    if _canonical_json_bytes(attempt) != _canonical_json_bytes(expected):
        raise StaticCensusEvidenceIntegrityError(
            "attempt does not reconstruct from reservation"
        )
    return attempt


def _report_parts(reconstructed: Any) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    value = _exact_keys(
        reconstructed,
        ("report", "report_ref", "report_summary"),
        "report reconstruction",
    )
    report_ref = _validate_body_ref(value["report_ref"], "report reference")
    if report_ref.byte_count < 1 or report_ref.byte_count > _MAX_REPORT_BYTES:
        raise StaticCensusEvidenceIntegrityError(
            "report reference exceeds the report byte limit"
        )
    _validate_summary_against_report(value["report"], value["report_summary"])
    return report_ref.as_dict(), _validated_report_summary(value["report_summary"])


def build_completed_v1(
    contract: StaticCensusEvidenceContract,
    bootstrap_value: Any,
    reservation_value: Any,
    attempt_value: Any,
    reconstructed_report: Any,
) -> Dict[str, Any]:
    bootstrap = _require_contract_bootstrap(contract, bootstrap_value)
    reservation = _validate_reservation_v1(contract, bootstrap, reservation_value)
    attempt = _validate_attempt_v1(
        contract, bootstrap, reservation, attempt_value
    )
    report_ref, report_summary = _report_parts(reconstructed_report)
    payload = {
        "attempt_id": attempt["identity"],
        "report_ref": report_ref,
        "report_summary": report_summary,
        "reservation_id": reservation["identity"],
        "stage_id": contract.stage_id,
        "stage_protocol_id": contract.stage_protocol_id,
    }
    return _make_identity_envelope(
        contract, "completed_root", _COMPLETED_ARTIFACT_TYPE, payload
    )


def _validate_completed_v1(
    contract: StaticCensusEvidenceContract,
    bootstrap_value: Any,
    reservation_value: Any,
    attempt_value: Any,
    reconstructed_report: Any,
    completed_value: Any,
) -> Dict[str, Any]:
    completed = _validate_identity_envelope(
        contract, completed_value, "completed_root", _COMPLETED_ARTIFACT_TYPE
    )
    expected = build_completed_v1(
        contract,
        bootstrap_value,
        reservation_value,
        attempt_value,
        reconstructed_report,
    )
    if _canonical_json_bytes(completed) != _canonical_json_bytes(expected):
        raise StaticCensusEvidenceIntegrityError(
            "completed body does not reconstruct from report"
        )
    return completed


def _validate_failure_value(value: Any) -> Dict[str, Any]:
    failure = _exact_keys(
        value,
        ("exception_module", "exception_type", "kind", "message"),
        "static-census failure",
    )
    if failure["kind"] != "STATIC_CENSUS_STAGE_EXCEPTION":
        raise StaticCensusEvidenceIntegrityError("failure kind drifted")
    for key in ("exception_module", "exception_type", "message"):
        text = _exact_string(failure[key], "failure {}".format(key))
        try:
            encoded = text.encode("utf-8", "strict")
        except UnicodeEncodeError as error:
            raise StaticCensusEvidenceIntegrityError(
                "failure {} is not valid UTF-8".format(key)
            ) from error
        if not encoded or len(encoded) > _MAX_FAILURE_TEXT_BYTES:
            raise StaticCensusEvidenceIntegrityError(
                "failure {} exceeds its bound".format(key)
            )
    return _json_copy(failure, "failure value")


def _bounded_failure_text(value: Any) -> str:
    try:
        text = str(value)
    except BaseException:
        return "<exception text unavailable>"
    try:
        encoded = text.encode("utf-8", "strict")
    except UnicodeEncodeError:
        return "<exception text is not valid UTF-8>"
    if not encoded:
        return "<empty exception text>"
    if len(encoded) > _MAX_FAILURE_TEXT_BYTES:
        return "<exception text exceeds {} bytes>".format(
            _MAX_FAILURE_TEXT_BYTES
        )
    return text


def failure_value_v1(error: BaseException) -> Dict[str, Any]:
    if not isinstance(error, BaseException):
        raise TypeError("error must be a BaseException")
    return _validate_failure_value(
        {
            "exception_module": _bounded_failure_text(type(error).__module__),
            "exception_type": _bounded_failure_text(type(error).__qualname__),
            "kind": "STATIC_CENSUS_STAGE_EXCEPTION",
            "message": _bounded_failure_text(error),
        }
    )


def build_failure_v1(
    contract: StaticCensusEvidenceContract,
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
    payload = {
        "attempt_id": attempt["identity"],
        "failure": _validate_failure_value(failure_value),
        "reservation_id": reservation["identity"],
        "stage_id": contract.stage_id,
        "stage_protocol_id": contract.stage_protocol_id,
    }
    return _make_identity_envelope(
        contract, "failure_root", _FAILURE_ARTIFACT_TYPE, payload
    )


def _validate_failure_v1(
    contract: StaticCensusEvidenceContract,
    bootstrap_value: Any,
    reservation_value: Any,
    attempt_value: Any,
    failure_value: Any,
) -> Dict[str, Any]:
    failure = _validate_identity_envelope(
        contract, failure_value, "failure_root", _FAILURE_ARTIFACT_TYPE
    )
    expected = build_failure_v1(
        contract,
        bootstrap_value,
        reservation_value,
        attempt_value,
        failure["payload"]["failure"],
    )
    if _canonical_json_bytes(failure) != _canonical_json_bytes(expected):
        raise StaticCensusEvidenceIntegrityError(
            "failure body does not reconstruct"
        )
    return failure


def build_orphaned_v1(
    contract: StaticCensusEvidenceContract,
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
    contract: StaticCensusEvidenceContract,
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
    if _canonical_json_bytes(orphaned) != _canonical_json_bytes(expected):
        raise StaticCensusEvidenceIntegrityError(
            "orphaned body does not reconstruct"
        )
    return orphaned


def build_terminal_seal_v1(
    contract: StaticCensusEvidenceContract,
    bootstrap_value: Any,
    lifecycle: str,
    *,
    reservation: Any,
    attempt: Optional[Any] = None,
    reconstructed_report: Optional[Any] = None,
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
    report_ref: Optional[Dict[str, Any]] = None
    if lifecycle == "COMPLETED":
        if (
            attempt_value is None
            or reconstructed_report is None
            or completed is None
            or failure is not None
            or orphaned is not None
        ):
            raise StaticCensusEvidenceIntegrityError(
                "COMPLETED terminal has incompatible artifacts"
            )
        completed_value = _validate_completed_v1(
            contract,
            bootstrap,
            reservation_value,
            attempt_value,
            reconstructed_report,
            completed,
        )
        completed_root = completed_value["identity"]
        report_ref, _summary = _report_parts(reconstructed_report)
    elif lifecycle == "FAILED":
        if (
            attempt_value is None
            or failure is None
            or reconstructed_report is not None
            or completed is not None
            or orphaned is not None
        ):
            raise StaticCensusEvidenceIntegrityError(
                "FAILED terminal has incompatible artifacts"
            )
        failure_value = _validate_failure_v1(
            contract,
            bootstrap,
            reservation_value,
            attempt_value,
            failure,
        )
        failure_root = failure_value["identity"]
    elif lifecycle == "ORPHANED":
        if (
            orphaned is None
            or reconstructed_report is not None
            or completed is not None
            or failure is not None
        ):
            raise StaticCensusEvidenceIntegrityError(
                "ORPHANED terminal has incompatible artifacts"
            )
        orphaned_value = _validate_orphaned_v1(
            contract,
            bootstrap,
            reservation_value,
            attempt_value,
            orphaned,
        )
        orphaned_id = orphaned_value["identity"]
    else:
        raise ValueError("unknown static-census terminal lifecycle")
    payload = {
        "attempt_id_or_null": (
            None if attempt_value is None else attempt_value["identity"]
        ),
        "completed_root_or_null": completed_root,
        "failure_root_or_null": failure_root,
        "lifecycle": lifecycle,
        "orphaned_id_or_null": orphaned_id,
        "report_ref_or_null": report_ref,
        "reservation_id_or_null": reservation_value["identity"],
        "stage_id": contract.stage_id,
        "stage_protocol_id": contract.stage_protocol_id,
    }
    return _make_identity_envelope(
        contract, "terminal_seal", _TERMINAL_ARTIFACT_TYPE, payload
    )


@dataclass(frozen=True)
class StaticCensusChainSnapshot:
    reservation: Optional[Dict[str, Any]] = None
    attempt: Optional[Dict[str, Any]] = None
    report_bytes: Optional[bytes] = None
    completed: Optional[Dict[str, Any]] = None
    failure: Optional[Dict[str, Any]] = None
    orphaned: Optional[Dict[str, Any]] = None
    terminal_seal: Optional[Dict[str, Any]] = None
    bootstrap_bytes: Optional[bytes] = None
    bootstrap_ref: Optional[StaticCensusBodyRef] = None


def _load_chain_snapshot_with_catalog_v1(
    store: _StaticCensusEvidenceStore,
) -> Tuple[
    Dict[str, Optional[StaticCensusBodyRef]], StaticCensusChainSnapshot
]:
    if type(store) is not _StaticCensusEvidenceStore:
        raise TypeError("store must be an internal static-census evidence store")
    # Bootstrap and every stage body are captured through overlapping held
    # descriptors.  The scan brackets every body read with complete inventories
    # and mutation-sensitive metadata, then rechecks all fixed name bindings
    # before releasing a descriptor.  This prevents separately valid reads from
    # becoming a mixed bootstrap/lifecycle snapshot after a rename or replace.
    catalog, retained_raw = store._scan_fixed_catalog_snapshot(
        retain_stage_raw=True
    )
    if catalog["contradiction"] is not None:
        raise StaticCensusEvidenceIntegrityError(
            "static-census evidence has an immutable contradiction"
        )

    def optional_json(artifact: str) -> Optional[Dict[str, Any]]:
        if catalog[artifact] is None:
            if artifact in retained_raw:
                raise StaticCensusEvidenceIntegrityError(
                    "absent artifact unexpectedly retained bytes"
                )
            return None
        raw = retained_raw.get(artifact)
        if raw is None or _body_ref(raw) != catalog[artifact]:
            raise StaticCensusEvidenceIntegrityError(
                "{} artifact differs from its fixed catalog".format(artifact)
            )
        value = _load_canonical_json_bytes(raw, label=artifact)
        if type(value) is not dict:
            raise StaticCensusEvidenceIntegrityError(
                "{} artifact must be a JSON object".format(artifact)
            )
        return value

    if catalog["bootstrap"] is None:
        if "bootstrap" in retained_raw:
            raise StaticCensusEvidenceIntegrityError(
                "absent bootstrap unexpectedly retained bytes"
            )
        bootstrap_bytes = None
        bootstrap_ref = None
    else:
        bootstrap_bytes = retained_raw.get("bootstrap")
        if (
            bootstrap_bytes is None
            or _body_ref(bootstrap_bytes) != catalog["bootstrap"]
        ):
            raise StaticCensusEvidenceIntegrityError(
                "bootstrap differs from its fixed catalog"
            )
        bootstrap_value = _load_canonical_json_bytes(
            bootstrap_bytes, label="bootstrap"
        )
        if type(bootstrap_value) is not dict:
            raise StaticCensusEvidenceIntegrityError(
                "bootstrap must be a JSON object"
            )
        bootstrap_ref = catalog["bootstrap"]

    if catalog["report"] is None:
        if "report" in retained_raw:
            raise StaticCensusEvidenceIntegrityError(
                "absent report unexpectedly retained bytes"
            )
        report_bytes = None
    else:
        report_bytes = retained_raw.get("report")
        if report_bytes is None or _body_ref(report_bytes) != catalog["report"]:
            raise StaticCensusEvidenceIntegrityError(
                "report differs from its fixed catalog"
            )
        _reconstruct_report(report_bytes)
    snapshot = StaticCensusChainSnapshot(
        reservation=optional_json("reservation"),
        attempt=optional_json("attempt"),
        report_bytes=report_bytes,
        completed=optional_json("completed"),
        failure=optional_json("failure"),
        orphaned=optional_json("orphaned"),
        terminal_seal=optional_json("terminal_seal"),
        bootstrap_bytes=bootstrap_bytes,
        bootstrap_ref=bootstrap_ref,
    )
    return catalog, snapshot


def load_chain_snapshot_v1(
    store: _StaticCensusEvidenceStore,
) -> StaticCensusChainSnapshot:
    _catalog, snapshot = _load_chain_snapshot_with_catalog_v1(store)
    return snapshot


def _load_chain_snapshot_matching_catalog_v1(
    store: _StaticCensusEvidenceStore,
    expected_catalog_value: Any,
) -> StaticCensusChainSnapshot:
    expected = _require_expected_catalog_v1(expected_catalog_value)
    observed, snapshot = _load_chain_snapshot_with_catalog_v1(store)
    if observed != expected:
        raise StaticCensusEvidenceIntegrityError(
            "evidence catalog changed before snapshot validation"
        )
    return snapshot


def validate_chain_snapshot_v1(
    contract: StaticCensusEvidenceContract,
    bootstrap_value: Any,
    snapshot: StaticCensusChainSnapshot,
) -> str:
    """Validate one complete fixed-catalog lifecycle and all cross-references."""

    if type(snapshot) is not StaticCensusChainSnapshot:
        raise TypeError("snapshot must be a StaticCensusChainSnapshot")
    bootstrap = _require_contract_bootstrap(contract, bootstrap_value)
    if (
        type(snapshot.bootstrap_bytes) is not bytes
        or type(snapshot.bootstrap_ref) is not StaticCensusBodyRef
        or _body_ref(snapshot.bootstrap_bytes) != snapshot.bootstrap_ref
    ):
        raise StaticCensusEvidenceIntegrityError(
            "chain snapshot lacks its exact bootstrap body"
        )
    snapshot_bootstrap = _require_contract_bootstrap(
        contract,
        _load_canonical_json_bytes(
            snapshot.bootstrap_bytes, label="snapshot bootstrap"
        ),
    )
    if (
        _canonical_json_bytes(snapshot_bootstrap)
        != _canonical_json_bytes(bootstrap)
    ):
        raise StaticCensusEvidenceIntegrityError(
            "requested bootstrap differs from the evidence snapshot"
        )
    if snapshot.reservation is None:
        if any(
            value is not None
            for value in (
                snapshot.attempt,
                snapshot.report_bytes,
                snapshot.completed,
                snapshot.failure,
                snapshot.orphaned,
                snapshot.terminal_seal,
            )
        ):
            raise StaticCensusEvidenceIntegrityError(
                "stage evidence exists without its reservation"
            )
        return "BOOTSTRAPPED"

    reservation = _validate_reservation_v1(
        contract, bootstrap, snapshot.reservation
    )
    if snapshot.attempt is None:
        if any(
            value is not None
            for value in (
                snapshot.report_bytes,
                snapshot.completed,
                snapshot.failure,
            )
        ):
            raise StaticCensusEvidenceIntegrityError(
                "report or lifecycle body exists without an attempt"
            )
        if snapshot.orphaned is None:
            if snapshot.terminal_seal is not None:
                raise StaticCensusEvidenceIntegrityError(
                    "reservation-only chain has a terminal seal"
                )
            return "RESERVED"
        orphaned = _validate_orphaned_v1(
            contract, bootstrap, reservation, None, snapshot.orphaned
        )
        lifecycle = "ORPHANED"
        expected_terminal = build_terminal_seal_v1(
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
        body_presence = (
            snapshot.completed is not None,
            snapshot.failure is not None,
            snapshot.orphaned is not None,
        )
        if sum(body_presence) > 1:
            raise StaticCensusEvidenceIntegrityError(
                "stage has conflicting lifecycle bodies"
            )
        if snapshot.report_bytes is not None:
            if snapshot.failure is not None or snapshot.orphaned is not None:
                raise StaticCensusEvidenceIntegrityError(
                    "report cannot coexist with failure or orphaned"
                )
            reconstructed = _reconstruct_report(snapshot.report_bytes)
            if snapshot.completed is None:
                if snapshot.terminal_seal is not None:
                    raise StaticCensusEvidenceIntegrityError(
                        "reported chain has a premature terminal seal"
                    )
                return "REPORTED"
            completed = _validate_completed_v1(
                contract,
                bootstrap,
                reservation,
                attempt,
                reconstructed,
                snapshot.completed,
            )
            lifecycle = "COMPLETED"
            expected_terminal = build_terminal_seal_v1(
                contract,
                bootstrap,
                lifecycle,
                reservation=reservation,
                attempt=attempt,
                reconstructed_report=reconstructed,
                completed=completed,
            )
        else:
            if snapshot.completed is not None:
                raise StaticCensusEvidenceIntegrityError(
                    "completed body exists without its report"
                )
            if not any(body_presence):
                if snapshot.terminal_seal is not None:
                    raise StaticCensusEvidenceIntegrityError(
                        "attempt-only chain has a terminal seal"
                    )
                return "ATTEMPTED"
            if snapshot.failure is not None:
                failure = _validate_failure_v1(
                    contract,
                    bootstrap,
                    reservation,
                    attempt,
                    snapshot.failure,
                )
                lifecycle = "FAILED"
                expected_terminal = build_terminal_seal_v1(
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
                expected_terminal = build_terminal_seal_v1(
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
    if _canonical_json_bytes(observed_terminal) != _canonical_json_bytes(
        expected_terminal
    ):
        raise StaticCensusEvidenceIntegrityError(
            "terminal seal does not reconstruct"
        )
    return lifecycle


def _require_no_contradiction(store: _StaticCensusEvidenceStore) -> None:
    if store.contradiction_exists():
        raise StaticCensusEvidenceIntegrityError(
            "static-census evidence has an immutable contradiction"
        )


def _mark_transition_contradiction_v1(
    capability: _StaticCensusMutationCapability,
    store: _StaticCensusEvidenceStore,
    contract: StaticCensusEvidenceContract,
) -> None:
    """Best-effort seal for a caught mutation-edge integrity failure."""

    # A Python-visible publication failure is not a power-loss crash.  It can
    # conservatively consume the stage as contradictory.  First finish any
    # recognizable hard-link window, then derive bootstrap/catalog metadata
    # from one descriptor-held snapshot whenever that remains possible.
    try:
        store._reconcile_pending_publications(capability)
    except BaseException:
        pass
    observed = None
    observed_bootstrap = None
    try:
        observed, snapshot = _load_chain_snapshot_with_catalog_v1(store)
        observed_bootstrap = None
        if snapshot.bootstrap_bytes is not None:
            try:
                observed_bootstrap = _require_contract_bootstrap(
                    contract,
                    _load_canonical_json_bytes(
                        snapshot.bootstrap_bytes,
                        label="transition-failure bootstrap",
                    ),
                )
            except StaticCensusEvidenceIntegrityError:
                observed_bootstrap = None
    except BaseException:
        pass
    try:
        _publish_contradiction(
            capability,
            store,
            contract,
            observed_bootstrap,
            observed,
        )
    except BaseException:
        pass


def _publish_bootstrap_v1(
    capability: _StaticCensusMutationCapability,
    store: _StaticCensusEvidenceStore,
    contract: StaticCensusEvidenceContract,
    value: Any,
    expected_catalog_value: Any,
) -> Tuple[
    StaticCensusBodyRef,
    Dict[str, Optional[StaticCensusBodyRef]],
]:
    _require_mutation_capability_v1(capability)
    if type(store) is not _StaticCensusEvidenceStore:
        raise TypeError("store must be an internal static-census evidence store")
    store._require_lock()
    _require_no_contradiction(store)
    bootstrap = _require_contract_bootstrap(contract, value)
    expected_catalog = _require_expected_catalog_v1(expected_catalog_value)
    try:
        before = _load_mutation_snapshot_matching_catalog_v1(
            capability,
            store,
            contract,
            bootstrap,
            expected_catalog,
        )
        if any(value is not None for value in expected_catalog.values()):
            raise StaticCensusEvidenceConflictError(
                "evidence exists before bootstrap publication"
            )
        if any(
            getattr(before, field) is not None
            for field in (
                "reservation",
                "attempt",
                "report_bytes",
                "completed",
                "failure",
                "orphaned",
                "terminal_seal",
                "bootstrap_bytes",
                "bootstrap_ref",
            )
        ):
            raise StaticCensusEvidenceIntegrityError(
                "empty bootstrap precondition retained evidence"
            )
        published_ref = store._publish_bootstrap(capability, bootstrap)
        published_catalog = dict(expected_catalog)
        published_catalog["bootstrap"] = published_ref
        snapshot = _load_mutation_snapshot_matching_catalog_v1(
            capability,
            store,
            contract,
            bootstrap,
            published_catalog,
        )
        if (
            validate_chain_snapshot_v1(contract, bootstrap, snapshot)
            != "BOOTSTRAPPED"
            or snapshot.bootstrap_bytes != _canonical_json_bytes(bootstrap)
        ):
            raise StaticCensusEvidenceIntegrityError(
                "published bootstrap failed its exact postcondition"
            )
    except BaseException:
        _mark_transition_contradiction_v1(capability, store, contract)
        raise
    return published_ref, published_catalog


def _begin_stage_v1(
    capability: _StaticCensusMutationCapability,
    store: _StaticCensusEvidenceStore,
    contract: StaticCensusEvidenceContract,
    bootstrap_value: Any,
    expected_catalog_value: Any,
) -> Tuple[
    StaticCensusChainSnapshot,
    Dict[str, Optional[StaticCensusBodyRef]],
]:
    """Durably publish the only reservation and attempt before calculation."""

    _require_mutation_capability_v1(capability)
    if type(store) is not _StaticCensusEvidenceStore:
        raise TypeError("store must be an internal static-census evidence store")
    store._require_lock()
    _require_no_contradiction(store)
    bootstrap = _require_contract_bootstrap(contract, bootstrap_value)
    expected_catalog = _require_expected_catalog_v1(expected_catalog_value)
    try:
        before = _load_mutation_snapshot_matching_catalog_v1(
            capability,
            store,
            contract,
            bootstrap,
            expected_catalog,
        )
        if (
            validate_chain_snapshot_v1(contract, bootstrap, before)
            != "BOOTSTRAPPED"
        ):
            raise StaticCensusEvidenceConflictError(
                "static-census stage already has immutable evidence"
            )
        reservation = build_reservation_v1(contract, bootstrap)
        attempt = build_attempt_v1(contract, bootstrap, reservation)
        reservation_ref = store._publish_stage_json(
            capability, "reservation", reservation
        )
        attempt_ref = store._publish_stage_json(
            capability, "attempt", attempt
        )
        attempted_catalog = dict(expected_catalog)
        attempted_catalog["reservation"] = reservation_ref
        attempted_catalog["attempt"] = attempt_ref
        snapshot = _load_mutation_snapshot_matching_catalog_v1(
            capability,
            store,
            contract,
            bootstrap,
            attempted_catalog,
        )
        if (
            validate_chain_snapshot_v1(contract, bootstrap, snapshot)
            != "ATTEMPTED"
        ):
            raise StaticCensusEvidenceIntegrityError(
                "new attempted chain failed validation"
            )
        if (
            _canonical_json_bytes(snapshot.reservation)
            != _canonical_json_bytes(reservation)
            or _canonical_json_bytes(snapshot.attempt)
            != _canonical_json_bytes(attempt)
        ):
            raise StaticCensusEvidenceIntegrityError(
                "published attempted chain differs from its construction"
            )
    except BaseException:
        _mark_transition_contradiction_v1(capability, store, contract)
        raise
    return snapshot, attempted_catalog


def _load_mutation_snapshot_matching_catalog_v1(
    capability: _StaticCensusMutationCapability,
    store: _StaticCensusEvidenceStore,
    contract: StaticCensusEvidenceContract,
    bootstrap_value: Any,
    expected_catalog_value: Any,
) -> StaticCensusChainSnapshot:
    """Bind a mutation edge or leave an immutable contradiction."""

    expected = _require_expected_catalog_v1(expected_catalog_value)
    bootstrap = _require_contract_bootstrap(contract, bootstrap_value)
    try:
        observed, snapshot = _load_chain_snapshot_with_catalog_v1(store)
    except BaseException:
        _mark_transition_contradiction_v1(capability, store, contract)
        raise
    if observed == expected:
        return snapshot
    _mark_transition_contradiction_v1(capability, store, contract)
    raise StaticCensusEvidenceIntegrityError(
        "evidence catalog changed before a pre-report mutation"
    )


def _publish_report_v1(
    capability: _StaticCensusMutationCapability,
    store: _StaticCensusEvidenceStore,
    contract: StaticCensusEvidenceContract,
    bootstrap_value: Any,
    report_bytes: bytes,
    expected_catalog_value: Any,
) -> Tuple[
    Dict[str, Any], Dict[str, Optional[StaticCensusBodyRef]]
]:
    """Publish only a complete independently reconstructed canonical report."""

    _require_mutation_capability_v1(capability)
    if type(store) is not _StaticCensusEvidenceStore:
        raise TypeError("store must be an internal static-census evidence store")
    if type(report_bytes) is not bytes:
        raise TypeError("report_bytes must be exact bytes")
    store._require_lock()
    _require_no_contradiction(store)
    bootstrap = _require_contract_bootstrap(contract, bootstrap_value)
    try:
        snapshot = _load_mutation_snapshot_matching_catalog_v1(
            capability,
            store,
            contract,
            bootstrap,
            expected_catalog_value,
        )
        if (
            validate_chain_snapshot_v1(contract, bootstrap, snapshot)
            != "ATTEMPTED"
        ):
            raise StaticCensusEvidenceConflictError(
                "stage is not an unreported attempted chain"
            )
        expected = _reconstruct_report(report_bytes)
        published_ref = store._publish_report_bytes(capability, report_bytes)
        reported_catalog = _require_expected_catalog_v1(
            expected_catalog_value
        )
        reported_catalog["report"] = published_ref
        reported = _load_mutation_snapshot_matching_catalog_v1(
            capability,
            store,
            contract,
            bootstrap,
            reported_catalog,
        )
        if (
            validate_chain_snapshot_v1(contract, bootstrap, reported)
            != "REPORTED"
        ):
            raise StaticCensusEvidenceIntegrityError(
                "published report did not form a reported chain"
            )
        observed = _reconstruct_report(reported.report_bytes)
        if (
            reported.report_bytes != report_bytes
            or published_ref.as_dict() != observed["report_ref"]
            or _canonical_json_bytes(expected["report_ref"])
            != _canonical_json_bytes(observed["report_ref"])
            or _canonical_json_bytes(expected["report_summary"])
            != _canonical_json_bytes(observed["report_summary"])
        ):
            raise StaticCensusEvidenceIntegrityError(
                "published report differs from its reconstruction"
            )
    except BaseException:
        _mark_transition_contradiction_v1(capability, store, contract)
        raise
    # The exact post-publication catalog is the receipt that binds the next
    # mutation to this report, rather than to a separately valid chain swapped
    # into the fixed stage path after this function returns.
    return observed, reported_catalog


def _seal_completed_v1(
    capability: _StaticCensusMutationCapability,
    store: _StaticCensusEvidenceStore,
    contract: StaticCensusEvidenceContract,
    bootstrap_value: Any,
    expected_report_bytes: bytes,
    expected_catalog_value: Any,
) -> Dict[str, Any]:
    _require_mutation_capability_v1(capability)
    if type(store) is not _StaticCensusEvidenceStore:
        raise TypeError("store must be an internal static-census evidence store")
    if type(expected_report_bytes) is not bytes:
        raise TypeError("expected_report_bytes must be exact bytes")
    store._require_lock()
    _require_no_contradiction(store)
    bootstrap = _require_contract_bootstrap(contract, bootstrap_value)
    expected_catalog = _require_expected_catalog_v1(expected_catalog_value)
    try:
        snapshot = _load_mutation_snapshot_matching_catalog_v1(
            capability,
            store,
            contract,
            bootstrap,
            expected_catalog,
        )
        if (
            validate_chain_snapshot_v1(contract, bootstrap, snapshot)
            != "REPORTED"
        ):
            raise StaticCensusEvidenceConflictError(
                "stage is not a reported chain awaiting completion"
            )
        if snapshot.report_bytes != expected_report_bytes:
            raise StaticCensusEvidenceIntegrityError(
                "reported chain differs from the calculated report"
            )
        reconstructed = _reconstruct_report(expected_report_bytes)
        completed = build_completed_v1(
            contract,
            bootstrap,
            snapshot.reservation,
            snapshot.attempt,
            reconstructed,
        )
        terminal = build_terminal_seal_v1(
            contract,
            bootstrap,
            "COMPLETED",
            reservation=snapshot.reservation,
            attempt=snapshot.attempt,
            reconstructed_report=reconstructed,
            completed=completed,
        )
        completed_ref = store._publish_stage_json(
            capability, "completed", completed
        )
        terminal_ref = store._publish_stage_json(
            capability, "terminal_seal", terminal
        )
        sealed_catalog = dict(expected_catalog)
        sealed_catalog["completed"] = completed_ref
        sealed_catalog["terminal_seal"] = terminal_ref
        sealed = _load_mutation_snapshot_matching_catalog_v1(
            capability,
            store,
            contract,
            bootstrap,
            sealed_catalog,
        )
        if (
            validate_chain_snapshot_v1(contract, bootstrap, sealed)
            != "COMPLETED"
        ):
            raise StaticCensusEvidenceIntegrityError(
                "published completed chain failed validation"
            )
        if (
            sealed.report_bytes != expected_report_bytes
            or _canonical_json_bytes(sealed.completed)
            != _canonical_json_bytes(completed)
            or _canonical_json_bytes(sealed.terminal_seal)
            != _canonical_json_bytes(terminal)
        ):
            raise StaticCensusEvidenceIntegrityError(
                "published completed chain differs from its construction"
            )
    except BaseException:
        _mark_transition_contradiction_v1(capability, store, contract)
        raise
    return sealed.terminal_seal


def _seal_failed_v1(
    capability: _StaticCensusMutationCapability,
    store: _StaticCensusEvidenceStore,
    contract: StaticCensusEvidenceContract,
    bootstrap_value: Any,
    failure_value: Any,
    expected_catalog_value: Any,
) -> Dict[str, Any]:
    _require_mutation_capability_v1(capability)
    if type(store) is not _StaticCensusEvidenceStore:
        raise TypeError("store must be an internal static-census evidence store")
    store._require_lock()
    _require_no_contradiction(store)
    bootstrap = _require_contract_bootstrap(contract, bootstrap_value)
    expected_catalog = _require_expected_catalog_v1(expected_catalog_value)
    try:
        snapshot = _load_mutation_snapshot_matching_catalog_v1(
            capability,
            store,
            contract,
            bootstrap,
            expected_catalog,
        )
        if (
            validate_chain_snapshot_v1(contract, bootstrap, snapshot)
            != "ATTEMPTED"
        ):
            raise StaticCensusEvidenceConflictError(
                "stage is not an unreported attempted chain"
            )
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
        failure_ref = store._publish_stage_json(
            capability, "failure", failure
        )
        terminal_ref = store._publish_stage_json(
            capability, "terminal_seal", terminal
        )
        sealed_catalog = dict(expected_catalog)
        sealed_catalog["failure"] = failure_ref
        sealed_catalog["terminal_seal"] = terminal_ref
        sealed = _load_mutation_snapshot_matching_catalog_v1(
            capability,
            store,
            contract,
            bootstrap,
            sealed_catalog,
        )
        if validate_chain_snapshot_v1(contract, bootstrap, sealed) != "FAILED":
            raise StaticCensusEvidenceIntegrityError(
                "published failed chain failed validation"
            )
        if (
            _canonical_json_bytes(sealed.failure)
            != _canonical_json_bytes(failure)
            or _canonical_json_bytes(sealed.terminal_seal)
            != _canonical_json_bytes(terminal)
        ):
            raise StaticCensusEvidenceIntegrityError(
                "published failed chain differs from its construction"
            )
    except BaseException:
        _mark_transition_contradiction_v1(capability, store, contract)
        raise
    return sealed.terminal_seal


@dataclass(frozen=True)
class StaticCensusRecoveryResult:
    action: str
    lifecycle: Optional[str]
    terminal_identity: Optional[str]
    report_bytes: Optional[bytes] = None


def _catalog_json(
    observed: Optional[Mapping[str, Optional[StaticCensusBodyRef]]]
) -> Dict[str, Any]:
    if observed is None:
        return {}
    result: Dict[str, Any] = {}
    for key in sorted(observed):
        ref = observed[key]
        result[key] = None if ref is None else ref.as_dict()
    return result


def _require_expected_catalog_v1(
    value: Any,
) -> Dict[str, Optional[StaticCensusBodyRef]]:
    expected_keys = {"bootstrap", "contradiction", *_STAGE_ARTIFACT_FILES}
    if type(value) is not dict or set(value) != expected_keys:
        raise StaticCensusEvidenceIntegrityError(
            "expected recovery catalog is not exact"
        )
    result: Dict[str, Optional[StaticCensusBodyRef]] = {}
    for key in value:
        body_ref = value[key]
        if body_ref is not None and type(body_ref) is not StaticCensusBodyRef:
            raise StaticCensusEvidenceIntegrityError(
                "expected recovery catalog contains an invalid body reference"
            )
        result[key] = body_ref
    return result


def _publish_contradiction(
    capability: _StaticCensusMutationCapability,
    store: _StaticCensusEvidenceStore,
    contract: StaticCensusEvidenceContract,
    bootstrap: Optional[Dict[str, Any]],
    observed: Optional[Mapping[str, Optional[StaticCensusBodyRef]]],
) -> None:
    payload = {
        "bootstrap_root_or_null": (
            None if bootstrap is None else bootstrap["identity"]
        ),
        "contradiction_kind": "INVALID_OR_CONFLICTING_STATIC_CENSUS_EVIDENCE",
        "observed_catalog_refs": _catalog_json(observed),
        "stage_id": contract.stage_id,
        "stage_protocol_id": contract.stage_protocol_id,
    }
    contradiction = _make_identity_envelope(
        contract,
        "contradiction_id",
        _CONTRADICTION_ARTIFACT_TYPE,
        payload,
    )
    store._publish_contradiction(capability, contradiction)


def _publish_terminal_for_snapshot(
    capability: _StaticCensusMutationCapability,
    store: _StaticCensusEvidenceStore,
    contract: StaticCensusEvidenceContract,
    bootstrap: Dict[str, Any],
    snapshot: StaticCensusChainSnapshot,
    lifecycle: str,
) -> Dict[str, Any]:
    if lifecycle == "COMPLETED":
        reconstructed = _reconstruct_report(snapshot.report_bytes)
        terminal = build_terminal_seal_v1(
            contract,
            bootstrap,
            lifecycle,
            reservation=snapshot.reservation,
            attempt=snapshot.attempt,
            reconstructed_report=reconstructed,
            completed=snapshot.completed,
        )
    elif lifecycle == "FAILED":
        terminal = build_terminal_seal_v1(
            contract,
            bootstrap,
            lifecycle,
            reservation=snapshot.reservation,
            attempt=snapshot.attempt,
            failure=snapshot.failure,
        )
    elif lifecycle == "ORPHANED":
        terminal = build_terminal_seal_v1(
            contract,
            bootstrap,
            lifecycle,
            reservation=snapshot.reservation,
            attempt=snapshot.attempt,
            orphaned=snapshot.orphaned,
        )
    else:
        raise StaticCensusEvidenceIntegrityError(
            "unrecognized unsealed lifecycle"
        )
    store._publish_stage_json(capability, "terminal_seal", terminal)
    return terminal


def _recover_stage_locked_v1(
    capability: _StaticCensusMutationCapability,
    store: _StaticCensusEvidenceStore,
    contract: StaticCensusEvidenceContract,
    authenticated_bootstrap_value: Optional[Any],
    expected_catalog_value: Optional[Any],
) -> StaticCensusRecoveryResult:
    """Recover lifecycle structure without calculating or resuming a census."""

    _require_mutation_capability_v1(capability)
    if type(store) is not _StaticCensusEvidenceStore:
        raise TypeError("store must be an internal static-census evidence store")
    contract = _require_fixed_contract(contract)
    store._require_lock()
    observed: Optional[Mapping[str, Optional[StaticCensusBodyRef]]] = None
    bootstrap: Optional[Dict[str, Any]] = None
    try:
        _require_no_contradiction(store)
        observed, snapshot = _load_chain_snapshot_with_catalog_v1(store)
        if observed["bootstrap"] is not None:
            bootstrap = _require_contract_bootstrap(
                contract,
                _load_canonical_json_bytes(
                    snapshot.bootstrap_bytes,
                    label="recovery snapshot bootstrap",
                ),
            )
        if expected_catalog_value is None:
            raise StaticCensusEvidenceIntegrityError(
                "recovery cannot mutate without an expected catalog"
            )
        expected_catalog = _require_expected_catalog_v1(
            expected_catalog_value
        )
        if expected_catalog != observed:
            raise StaticCensusEvidenceIntegrityError(
                "evidence catalog changed before recovery"
            )
        if observed["bootstrap"] is None:
            if authenticated_bootstrap_value is not None:
                raise StaticCensusEvidenceIntegrityError(
                    "authenticated bootstrap disappeared before recovery"
                )
            if any(observed[name] is not None for name in _STAGE_ARTIFACT_FILES):
                raise StaticCensusEvidenceIntegrityError(
                    "stage evidence exists without bootstrap"
                )
            return StaticCensusRecoveryResult("NO_EVIDENCE", None, None)
        # Even an unauthenticated caller may name the bootstrap from this
        # exact snapshot in a contradiction record.  It may never use that
        # value for normal lifecycle recovery or publication.
        if authenticated_bootstrap_value is None:
            raise StaticCensusEvidenceIntegrityError(
                "recovery cannot mutate without an authenticated bootstrap"
            )
        authenticated_bootstrap = _require_contract_bootstrap(
            contract,
            authenticated_bootstrap_value,
        )
        state = validate_chain_snapshot_v1(
            contract, authenticated_bootstrap, snapshot
        )
        bootstrap = authenticated_bootstrap
        if state == "BOOTSTRAPPED":
            return StaticCensusRecoveryResult(
                "BOOTSTRAP_ONLY_NO_STAGE", None, None
            )
        if state in ("COMPLETED", "FAILED", "ORPHANED"):
            return StaticCensusRecoveryResult(
                "VERIFIED_NO_OP",
                state,
                snapshot.terminal_seal["identity"],
                snapshot.report_bytes if state == "COMPLETED" else None,
            )
        if state == "REPORTED":
            reconstructed = _reconstruct_report(snapshot.report_bytes)
            completed = build_completed_v1(
                contract,
                bootstrap,
                snapshot.reservation,
                snapshot.attempt,
                reconstructed,
            )
            terminal = build_terminal_seal_v1(
                contract,
                bootstrap,
                "COMPLETED",
                reservation=snapshot.reservation,
                attempt=snapshot.attempt,
                reconstructed_report=reconstructed,
                completed=completed,
            )
            store._publish_stage_json(capability, "completed", completed)
            store._publish_stage_json(capability, "terminal_seal", terminal)
            sealed = load_chain_snapshot_v1(store)
            if (
                validate_chain_snapshot_v1(contract, bootstrap, sealed)
                != "COMPLETED"
                or _canonical_json_bytes(sealed.completed)
                != _canonical_json_bytes(completed)
                or _canonical_json_bytes(sealed.terminal_seal)
                != _canonical_json_bytes(terminal)
            ):
                raise StaticCensusEvidenceIntegrityError(
                    "recovered completed chain failed its postcondition"
                )
            return StaticCensusRecoveryResult(
                "SEALED_REPORTED_COMPLETED",
                "COMPLETED",
                sealed.terminal_seal["identity"],
                sealed.report_bytes,
            )
        if state.endswith("_UNSEALED"):
            lifecycle = state[: -len("_UNSEALED")]
            terminal = _publish_terminal_for_snapshot(
                capability,
                store,
                contract,
                bootstrap,
                snapshot,
                lifecycle,
            )
            sealed = load_chain_snapshot_v1(store)
            if (
                validate_chain_snapshot_v1(contract, bootstrap, sealed)
                != lifecycle
                or _canonical_json_bytes(sealed.terminal_seal)
                != _canonical_json_bytes(terminal)
            ):
                raise StaticCensusEvidenceIntegrityError(
                    "recovered terminal chain failed its postcondition"
                )
            return StaticCensusRecoveryResult(
                "SEALED_EXISTING_" + lifecycle,
                lifecycle,
                sealed.terminal_seal["identity"],
                sealed.report_bytes if lifecycle == "COMPLETED" else None,
            )
        if state not in ("RESERVED", "ATTEMPTED"):
            raise StaticCensusEvidenceIntegrityError(
                "unrecognized recoverable chain state"
            )
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
        store._publish_stage_json(capability, "orphaned", orphaned)
        store._publish_stage_json(capability, "terminal_seal", terminal)
        sealed = load_chain_snapshot_v1(store)
        if (
            validate_chain_snapshot_v1(contract, bootstrap, sealed)
            != "ORPHANED"
            or _canonical_json_bytes(sealed.orphaned)
            != _canonical_json_bytes(orphaned)
            or _canonical_json_bytes(sealed.terminal_seal)
            != _canonical_json_bytes(terminal)
        ):
            raise StaticCensusEvidenceIntegrityError(
                "recovered orphaned chain failed its postcondition"
            )
        return StaticCensusRecoveryResult(
            "SEALED_NEW_ORPHANED",
            "ORPHANED",
            sealed.terminal_seal["identity"],
        )
    except StaticCensusEvidenceLockError:
        raise
    except BaseException as error:
        try:
            _publish_contradiction(
                capability, store, contract, bootstrap, observed
            )
        except (StaticCensusEvidenceConflictError, StaticCensusEvidenceIntegrityError):
            pass
        raise StaticCensusEvidenceIntegrityError(
            "static-census evidence recovery failed closed"
        ) from error


__all__ = (
    "EVIDENCE_ROOT_RELATIVE_V1",
    "STAGE_ID_V1",
    "STAGE_PROTOCOL_ID_V1",
    "StaticCensusBodyRef",
    "StaticCensusChainSnapshot",
    "StaticCensusEvidenceConflictError",
    "StaticCensusEvidenceContract",
    "StaticCensusEvidenceError",
    "StaticCensusEvidenceIntegrityError",
    "StaticCensusEvidenceLockError",
    "StaticCensusRecoveryResult",
    "build_attempt_v1",
    "build_bootstrap_v1",
    "build_completed_v1",
    "build_failure_v1",
    "build_orphaned_v1",
    "build_reservation_v1",
    "build_terminal_seal_v1",
    "failure_value_v1",
    "fixed_static_census_evidence_contract_v1",
    "load_chain_snapshot_v1",
    "validate_bootstrap_v1",
    "validate_chain_snapshot_v1",
)
