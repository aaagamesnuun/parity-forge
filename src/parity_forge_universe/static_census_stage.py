"""One-shot facade for the Plan-0015 static census.

The stage is the only production caller of ``build_static_census_v1``.  It
publishes a durable reservation and attempt first, invokes the fixed builder
once with no arguments, independently reconstructs its canonical report, and
then seals one immutable lifecycle.  Recovery never invokes the calculator or
any checkpoint API.

The root of trust is a host selecting the independently reviewed source and
creating a fresh operating-system process with the exact launcher documented
by ``_build_parser``.  On the pinned Python 3.9 runtime the host also owns the
raw option spelling: the process exposes its effective security state but not
``sys.orig_argv``.  Code already running inside that Python process, native
memory modification, and hostile source executed before Git authentication are
outside this module's self-attestation boundary.  The bootstrap detects common
mislaunch/prelude forms and capability-bearing extra options, then keeps the
inspected source/cache descriptors live for the complete stage operation.
"""

from __future__ import annotations

# The production CLI enters this source file directly under ``-I -B -S``.
# Keep this bootstrap ahead of every non-builtin import: it proves that the
# repository was not on the startup import path, rejects ignored bytecode or
# extension shadows, and only then appends the inspected source root.  The
# canonical module imported below retains the attestation and is the module
# that exposes the two public operations.
import sys as _source_bootstrap_sys


_source_entry_getframe_v1 = _source_bootstrap_sys._getframe
if (
    _source_entry_getframe_v1.__class__ is not [].append.__class__
    or _source_entry_getframe_v1.__self__ is not _source_bootstrap_sys
    or _source_entry_getframe_v1.__module__ != "sys"
    or _source_entry_getframe_v1.__name__ != "_getframe"
):
    raise RuntimeError("static-census source bootstrap: frame API is not canonical")
_source_entry_frame_v1 = _source_entry_getframe_v1()
_SOURCE_ENTRY_CODE_V1 = _source_entry_frame_v1.f_code
_SOURCE_ENTRY_IS_ROOT_V1 = _source_entry_frame_v1.f_back is None
del _source_entry_frame_v1
del _source_entry_getframe_v1


def _direct_source_bootstrap_v1(
    _sys=_source_bootstrap_sys,
    _entry_code=_SOURCE_ENTRY_CODE_V1,
    _entry_is_root=_SOURCE_ENTRY_IS_ROOT_V1,
):
    # The automatic direct-script branch is a root Python frame.  Ordinary
    # exec/eval/runpy forms leave a caller; simple prefixed root code is caught
    # after canonical disk import by the immutable code-object comparison.
    if not _entry_is_root:
        raise RuntimeError(
            "static-census source bootstrap: direct script has a Python caller"
        )
    if "ctypes" in _sys.modules or "_ctypes" in _sys.modules:
        raise RuntimeError(
            "static-census source bootstrap: native bridge loaded before entry"
        )
    import posix as _posix

    def fail(message):
        raise RuntimeError("static-census source bootstrap: " + message)

    flags = _sys.flags
    if (
        _sys.executable
        != "/Library/Developer/CommandLineTools/usr/bin/python3"
        or tuple(_sys.version_info) != (3, 9, 6, "final", 0)
        or getattr(_sys.implementation, "name", None) != "cpython"
        or getattr(_sys.implementation, "cache_tag", None) != "cpython-39"
        or flags.isolated != 1
        or flags.ignore_environment != 1
        or flags.no_user_site != 1
        or flags.no_site != 1
        or flags.dont_write_bytecode != 1
        or flags.optimize != 0
        or flags.hash_randomization != 1
        or flags.debug != 0
        or flags.inspect != 0
        or flags.interactive != 0
        or flags.verbose != 0
        or flags.bytes_warning != 0
        or flags.quiet != 0
        or flags.dev_mode is not False
        or flags.utf8_mode != 1
    ):
        fail("requires -I -B -S with optimization disabled")

    cache = _sys.pycache_prefix
    if type(cache) is not str or not cache.startswith("/"):
        fail("requires an absolute fresh pycache prefix")
    if (
        type(_sys._xoptions) is not dict
        or _sys._xoptions != {"pycache_prefix": cache}
        or type(_sys.warnoptions) is not list
        or _sys.warnoptions
    ):
        fail("interpreter option surface is not the fixed launcher")
    # Python 3.9 does not expose raw redundant option spelling.  The fresh-host
    # trust boundary owns that exact argv; here we attest the effective flags
    # and every exposed capability-bearing interpreter option.
    original_argv = getattr(_sys, "orig_argv", None)
    if original_argv is not None:
        expected_original = [
            "/usr/bin/python3",
            "-I",
            "-B",
            "-S",
            "-X",
            "pycache_prefix=" + cache,
        ] + list(_sys.argv)
        if type(original_argv) is not list or original_argv != expected_original:
            fail("raw interpreter invocation is not canonical")
    meta_path = _sys.meta_path
    path_hooks = _sys.path_hooks
    if (
        type(meta_path) is not list
        or tuple(
            (getattr(item, "__module__", None), getattr(item, "__name__", None))
            for item in meta_path
        )
        != (
            ("_frozen_importlib", "BuiltinImporter"),
            ("_frozen_importlib", "FrozenImporter"),
            ("_frozen_importlib_external", "PathFinder"),
        )
        or type(path_hooks) is not list
        or tuple(
            (
                getattr(item, "__module__", None),
                getattr(item, "__qualname__", None),
            )
            for item in path_hooks
        )
        != (
            ("zipimport", "zipimporter"),
            (
                "_frozen_importlib_external",
                "FileFinder.path_hook.<locals>.path_hook_for_FileFinder",
            ),
        )
    ):
        fail("startup import machinery is not canonical")
    cache_flags = (
        _posix.O_RDONLY
        | getattr(_posix, "O_DIRECTORY", 0)
        | getattr(_posix, "O_NOFOLLOW", 0)
        | getattr(_posix, "O_NONBLOCK", 0)
    )
    cache_fd = -1
    root_fd = -1
    held_source_directories = []
    source_fd = -1
    package_fd = -1
    ancestry_kqueue = None
    ancestry_event_count = 0
    try:
        cache_fd = _posix.open(cache, cache_flags)
        cache_info = _posix.fstat(cache_fd)
        if (
            cache_info.st_mode & 0o170000 != 0o040000
            or cache_info.st_mode & 0o777 != 0o700
            or cache_info.st_uid != _posix.geteuid()
            or _posix.listdir(cache_fd)
        ):
            fail("pycache prefix is not an empty private owned directory")

        stage_file = globals().get("__file__")
        if (
            type(stage_file) is not str
            or not stage_file.startswith("/")
            or stage_file.rsplit("/", 1)[-1] != "static_census_stage.py"
        ):
            fail("must execute this stage by its absolute source path")
        package = stage_file.rsplit("/", 1)[0]
        if package.rsplit("/", 1)[-1] != "parity_forge_universe":
            fail("stage source is outside the fixed package")
        source = package.rsplit("/", 1)[0]
        if source.rsplit("/", 1)[-1] != "src":
            fail("stage package is outside the fixed source root")

        # Isolated startup paths and the interpreter must be system-owned and
        # unwritable by this process.  A missing final zip entry is harmless
        # only when every existing parent is trusted.
        trusted_startup_path = tuple(_sys.path)
        if not trusted_startup_path:
            fail("isolated startup path is empty")
        def normalize_absolute(candidate):
            parts = []
            for part in candidate.split("/"):
                if part in ("", "."):
                    continue
                if part == "..":
                    if not parts:
                        fail("trusted symlink escapes the filesystem root")
                    parts.pop()
                else:
                    parts.append(part)
            return "/" + "/".join(parts)

        def require_trusted_path(candidate, allow_final_symlink, depth=0):
            if type(candidate) is not str or not candidate.startswith("/"):
                fail("isolated startup path is not absolute")
            components = candidate.split("/")[1:]
            if not components or any(part in ("", ".", "..") for part in components):
                fail("isolated startup path is not canonical")
            current = ""
            for index, component in enumerate(components):
                current += "/" + component
                try:
                    info = _posix.lstat(current)
                except FileNotFoundError:
                    if index != len(components) - 1:
                        fail("isolated startup ancestor is missing")
                    break
                kind = info.st_mode & 0o170000
                if index != len(components) - 1 and kind != 0o040000:
                    fail("isolated startup ancestor is not a directory")
                if info.st_uid != 0 or _posix.access(current, _posix.W_OK):
                    fail("isolated startup path is not trusted")
                if kind == 0o120000:
                    if (
                        index != len(components) - 1
                        or not allow_final_symlink
                        or depth >= 4
                    ):
                        fail("isolated startup path contains a symlink")
                    target = _posix.readlink(current)
                    if not target.startswith("/"):
                        target = current.rsplit("/", 1)[0] + "/" + target
                    require_trusted_path(
                        normalize_absolute(target), True, depth + 1
                    )
                    return

        require_trusted_path(_sys.executable, True)
        for candidate in trusted_startup_path:
            require_trusted_path(candidate, False)
            try:
                startup_fd = _posix.open(candidate, cache_flags)
            except FileNotFoundError:
                continue
            except OSError:
                fail("non-directory startup importer is not permitted")
            try:
                if any(
                    name == "parity_forge_universe"
                    or name.startswith("parity_forge_universe.")
                    for name in _posix.listdir(startup_fd)
                ):
                    fail("startup import path already contains the universe package")
            finally:
                _posix.close(startup_fd)

        # ``select`` is the sole non-builtin bootstrap dependency.  Import it
        # only after every startup search path has been proved system-owned and
        # unwritable by this process.
        import select as _select

        if any(
            name == "parity_forge_universe"
            or name.startswith("parity_forge_universe.")
            for name in _sys.modules
        ):
            fail("universe modules were loaded before source inspection")

        directory_flags = cache_flags

        def state(info):
            return (
                info.st_dev,
                info.st_ino,
                info.st_mode,
                info.st_nlink,
                info.st_size,
                info.st_mtime_ns,
                info.st_ctime_ns,
            )

        def binding(info):
            return (info.st_dev, info.st_ino, info.st_mode)

        root_fd = _posix.open("/", directory_flags)
        root_state = binding(_posix.fstat(root_fd))
        parent_fd = root_fd
        current = ""
        for component in package.split("/")[1:]:
            child_fd = _posix.open(component, directory_flags, dir_fd=parent_fd)
            child_info = _posix.fstat(child_fd)
            named_info = _posix.stat(
                component, dir_fd=parent_fd, follow_symlinks=False
            )
            child_state = binding(child_info)
            if (
                child_info.st_mode & 0o170000 != 0o040000
                or binding(named_info) != child_state
            ):
                fail("source ancestor binding is not a directory")
            held_source_directories.append(
                (parent_fd, component, child_fd, child_state)
            )
            parent_fd = child_fd
            current += "/" + component
            if current == source:
                source_fd = child_fd
            if current == package:
                package_fd = child_fd
        if source_fd < 0 or package_fd < 0:
            fail("source ancestry does not contain the fixed package")
        ancestry_kqueue = _select.kqueue()
        ancestry_changes = [
            _select.kevent(
                record[2],
                filter=_select.KQ_FILTER_VNODE,
                flags=_select.KQ_EV_ADD | _select.KQ_EV_CLEAR,
                fflags=(
                    _select.KQ_NOTE_ATTRIB
                    | _select.KQ_NOTE_DELETE
                    | _select.KQ_NOTE_RENAME
                    | _select.KQ_NOTE_REVOKE
                ),
            )
            for record in held_source_directories
        ]
        ancestry_event_count = len(ancestry_changes)
        if ancestry_kqueue.control(ancestry_changes, 0, 0):
            fail("cannot establish source ancestry event watch")
        source_info = _posix.fstat(source_fd)
        package_info = _posix.fstat(package_fd)
        named_package = _posix.stat(
            "parity_forge_universe", dir_fd=source_fd, follow_symlinks=False
        )
        if (
            source_info.st_mode & 0o170000 != 0o040000
            or package_info.st_mode & 0o170000 != 0o040000
            or (named_package.st_dev, named_package.st_ino)
            != (package_info.st_dev, package_info.st_ino)
        ):
            fail("source package directory binding changed")
        if set(_posix.listdir(source_fd)) != {
            "parity_forge",
            "parity_forge_universe",
        }:
            fail("source root contains an unreviewed import capability")
        legacy_info = _posix.stat(
            "parity_forge", dir_fd=source_fd, follow_symlinks=False
        )
        if legacy_info.st_mode & 0o170000 != 0o040000:
            fail("legacy package binding is not a directory")

        fixed_names = (
            "__init__.py",
            "initial_structure.py",
            "schema_v4_compiler.py",
            "static_census.py",
            "static_census_evidence.py",
            "static_census_protocol.py",
            "static_census_reconstruction.py",
            "static_census_stage.py",
            "typed_occupancy.py",
        )
        if set(_posix.listdir(package_fd)) != set(fixed_names):
            fail("universe package contains an unreviewed import capability")
        file_states = []
        for name in fixed_names:
            info = _posix.stat(name, dir_fd=package_fd, follow_symlinks=False)
            if info.st_mode & 0o170000 != 0o100000:
                fail("universe source entry is not a regular file")
            file_states.append(
                (
                    name,
                    info.st_dev,
                    info.st_ino,
                    info.st_mode,
                    info.st_nlink,
                    info.st_size,
                    info.st_mtime_ns,
                    info.st_ctime_ns,
                )
            )

        main_module = _sys.modules.get("__main__")
        main_loader = globals().get("__loader__")
        token = object()
        attestation = (
            token,
            main_module,
            main_loader,
            stage_file,
            source,
            trusted_startup_path,
            _sys.executable,
            _sys.path,
            cache,
            cache_fd,
            source_fd,
            package_fd,
            state(cache_info),
            state(source_info),
            state(package_info),
            tuple(file_states),
            fixed_names,
            state(_posix.stat(_sys.executable)),
            root_fd,
            root_state,
            tuple(held_source_directories),
            ancestry_kqueue,
            ancestry_event_count,
            meta_path,
            tuple(meta_path),
            path_hooks,
            tuple(path_hooks),
            _sys._xoptions,
            _sys.warnoptions,
        )
        setattr(_sys, "_parity_forge_static_census_bootstrap_v1", attestation)
        _sys.path.append(source)
        from parity_forge_universe import static_census_stage as imported

        # Hold the original directories across import and reject path swaps or
        # source metadata changes before the canonical module can parse a
        # command or touch evidence.
        if ancestry_kqueue.control([], ancestry_event_count, 0):
            fail("source ancestry changed during source loading")
        if tuple(_sys.path) != trusted_startup_path + (source,):
            fail("import path changed during source loading")
        if binding(_posix.fstat(root_fd)) != root_state:
            fail("filesystem anchor changed during source loading")
        for held_parent, name, held_child, child_state in (
            held_source_directories
        ):
            if (
                binding(_posix.fstat(held_child)) != child_state
                or binding(
                    _posix.stat(
                        name,
                        dir_fd=held_parent,
                        follow_symlinks=False,
                    )
                )
                != child_state
            ):
                fail("source ancestor changed during source loading: " + name)
        rebound_source = _posix.stat(source, follow_symlinks=False)
        rebound_package = _posix.stat(package, follow_symlinks=False)
        if (
            (rebound_source.st_dev, rebound_source.st_ino)
            != (source_info.st_dev, source_info.st_ino)
            or (rebound_package.st_dev, rebound_package.st_ino)
            != (package_info.st_dev, package_info.st_ino)
            or set(_posix.listdir(source_fd))
            != {"parity_forge", "parity_forge_universe"}
            or set(_posix.listdir(package_fd)) != set(fixed_names)
        ):
            fail("source tree binding changed during import")
        observed_states = []
        for name in fixed_names:
            info = _posix.stat(name, dir_fd=package_fd, follow_symlinks=False)
            observed_states.append(
                (
                    name,
                    info.st_dev,
                    info.st_ino,
                    info.st_mode,
                    info.st_nlink,
                    info.st_size,
                    info.st_mtime_ns,
                    info.st_ctime_ns,
                )
            )
        if observed_states != file_states:
            fail("universe source changed during import")
        if _posix.listdir(cache_fd):
            fail("module cache appeared during source loading")
        if (
            getattr(imported, "_SOURCE_BOOTSTRAP_ATTESTATION_V1", None)
            is not attestation
        ):
            fail("canonical stage did not retain bootstrap attestation")
        if getattr(imported, "_SOURCE_ENTRY_CODE_V1", None) != _entry_code:
            fail("direct entry code differs from canonical source")
        if "parity_forge" in _sys.modules or any(
            name.startswith("parity_forge.") for name in _sys.modules
        ):
            fail("legacy game package entered the census process")
        return imported.main(_sys.argv[1:])
    finally:
        for _parent, _name, descriptor, _child_state in reversed(
            held_source_directories
        ):
            _posix.close(descriptor)
        if root_fd >= 0:
            _posix.close(root_fd)
        if cache_fd >= 0:
            _posix.close(cache_fd)
        if ancestry_kqueue is not None:
            ancestry_kqueue.close()


if __name__ == "__main__" and __package__ in (None, ""):
    raise SystemExit(_direct_source_bootstrap_v1())

del _direct_source_bootstrap_v1

import argparse
import json
import os
from pathlib import Path
import select
import stat
import sys
from typing import Any, Dict, Optional, Sequence

from . import static_census as census
from . import static_census_evidence as evidence
from . import static_census_protocol as protocol
from . import static_census_reconstruction as reconstruction


_CENSUS_MODULE_V1 = census
_EVIDENCE_MODULE_V1 = evidence
_PROTOCOL_MODULE_V1 = protocol
_RECONSTRUCTION_MODULE_V1 = reconstruction
_PACKAGE_MODULE_V1 = sys.modules[__package__]
_INITIAL_MODULE_V1 = census.initial
_COMPILER_MODULE_V1 = census.compiler
_UNIVERSE_MODULE_V1 = census.universe

_BUILD_CENSUS_V1 = census.build_static_census_v1
_SERIALIZE_REPORT_V1 = census.canonical_static_census_report_json_v1
_REPORT_HASH_V1 = census.static_census_report_hash_v1
_RECONSTRUCT_REPORT_V1 = reconstruction.reconstruct_static_census_report_artifact_v1

_CLAIM_EVIDENCE_MUTATION_CAPABILITY_V1 = (
    evidence._claim_stage_mutation_capability_v1
)
_EVIDENCE_MUTATION_CAPABILITY_V1 = _CLAIM_EVIDENCE_MUTATION_CAPABILITY_V1(
    sys.modules[__name__]
)
_EVIDENCE_ROOT_RELATIVE_V1 = evidence.EVIDENCE_ROOT_RELATIVE_V1
_STAGE_ID_V1 = evidence.STAGE_ID_V1
_EVIDENCE_STORE_V1 = evidence._StaticCensusEvidenceStore
_EVIDENCE_INTEGRITY_ERROR_V1 = evidence.StaticCensusEvidenceIntegrityError
_FIXED_EVIDENCE_CONTRACT_V1 = evidence.fixed_static_census_evidence_contract_v1
_OPEN_RECOVERY_STORE_V1 = evidence._open_recovery_store_v1
_VALIDATE_BOOTSTRAP_V1 = evidence.validate_bootstrap_v1
_BUILD_BOOTSTRAP_V1 = evidence.build_bootstrap_v1
_PUBLISH_BOOTSTRAP_V1 = evidence._publish_bootstrap_v1
_BEGIN_STAGE_V1 = evidence._begin_stage_v1
_PUBLISH_REPORT_V1 = evidence._publish_report_v1
_SEAL_COMPLETED_V1 = evidence._seal_completed_v1
_SEAL_FAILED_V1 = evidence._seal_failed_v1
_FAILURE_VALUE_V1 = evidence.failure_value_v1
_LOAD_CHAIN_SNAPSHOT_MATCHING_CATALOG_V1 = (
    evidence._load_chain_snapshot_matching_catalog_v1
)
_VALIDATE_CHAIN_SNAPSHOT_V1 = evidence.validate_chain_snapshot_v1
_RECOVER_STAGE_LOCKED_V1 = evidence._recover_stage_locked_v1

_BUILD_PROTOCOL_V1 = protocol.build_static_census_protocol_v1
_VALIDATE_PROTOCOL_V1 = protocol.validate_static_census_protocol_v1
_RESOLVE_REPOSITORY_V1 = protocol.resolve_static_census_repository_v1
_BUILD_PRODUCTION_CLOSURE_V1 = protocol.build_static_census_production_closure_v1
_AUTHENTICATE_RECOVERY_CLOSURE_V1 = (
    protocol.authenticate_static_census_recovery_closure_v1
)
_STORED_CLOSURE_INTEGRITY_ERROR_V1 = (
    protocol.StaticCensusStoredClosureIntegrityError
)
_VALIDATE_PRODUCTION_CLOSURE_V1 = (
    protocol.validate_static_census_production_closure_v1
)
_RESEAL_PRODUCTION_CLOSURE_V1 = (
    protocol.reseal_static_census_production_closure_v1
)
_PUBLIC_RETURN_CLOSURE_KEY_V1 = "_production_closure_for_final_reseal_v1"

_STAGE_FILE_V1 = __file__
_STAGE_SPEC_V1 = __spec__
_STAGE_SPEC_ORIGIN_V1 = None if __spec__ is None else __spec__.origin
_STAGE_MODULE_V1 = sys.modules[__name__]
_STAGE_LOADER_V1 = __loader__
_SOURCE_LOADER_TYPE_V1 = type(__loader__)
_STAGE_CACHED_V1 = __cached__
_SOURCE_BOOTSTRAP_ATTESTATION_V1 = getattr(
    sys, "_parity_forge_static_census_bootstrap_v1", None
)


class StaticCensusStageError(RuntimeError):
    """The fixed stage facade or its runtime module bindings changed."""


def _require_trusted_source_launcher_v1(
    repository: str,
    command: str,
    _attestation: Any = _SOURCE_BOOTSTRAP_ATTESTATION_V1,
    _sys: Any = sys,
    _abspath: Any = os.path.abspath,
    _access: Any = os.access,
    _fstat: Any = os.fstat,
    _stat: Any = os.stat,
    _listdir: Any = os.listdir,
    _w_ok: int = os.W_OK,
    _isdir: Any = stat.S_ISDIR,
    _isreg: Any = stat.S_ISREG,
    _len: Any = len,
    _error: Any = StaticCensusStageError,
) -> None:
    """Require descriptor-held direct-source production launcher state."""

    if type(_attestation) is not tuple or _len(_attestation) != 29:
        raise _error("public stage requires the trusted direct source launcher")
    (
        _token,
        main_module,
        main_loader,
        stage_file,
        source,
        trusted_startup_path,
        executable,
        path_object,
        cache,
        cache_fd,
        source_fd,
        package_fd,
        cache_state,
        source_state,
        package_state,
        file_states,
        fixed_names,
        interpreter_state,
        root_fd,
        root_state,
        held_source_directories,
        ancestry_kqueue,
        ancestry_event_count,
        meta_path,
        meta_path_entries,
        path_hooks,
        path_hook_entries,
        xoptions,
        warnoptions,
    ) = _attestation

    if (
        getattr(_sys, "_parity_forge_static_census_bootstrap_v1", None)
        is not _attestation
        or _sys.modules.get("__main__") is not main_module
        or _sys.path is not path_object
        or _sys.meta_path is not meta_path
        or tuple(_sys.meta_path) != meta_path_entries
        or _sys.path_hooks is not path_hooks
        or tuple(_sys.path_hooks) != path_hook_entries
        or _sys._xoptions is not xoptions
        or _sys._xoptions != {"pycache_prefix": cache}
        or _sys.warnoptions is not warnoptions
        or _sys.warnoptions
        or _sys.executable != executable
        or executable
        != "/Library/Developer/CommandLineTools/usr/bin/python3"
        or tuple(_sys.version_info) != (3, 9, 6, "final", 0)
        or getattr(_sys.implementation, "name", None) != "cpython"
        or getattr(_sys.implementation, "cache_tag", None) != "cpython-39"
        or type(_sys.argv) is not list
        or tuple(_sys.argv)
        != (stage_file, command, "--repository", repository)
        or type(repository) is not str
        or _abspath(repository) != repository
        or source != repository + os.sep + "src"
        or stage_file
        != source
        + os.sep
        + "parity_forge_universe"
        + os.sep
        + "static_census_stage.py"
        or tuple(_sys.path) != trusted_startup_path + (source,)
        or getattr(main_module, "__name__", None) != "__main__"
        or getattr(main_module, "__file__", None) != stage_file
        or getattr(main_module, "__loader__", None) is not main_loader
        or type(main_loader) is not _SOURCE_LOADER_TYPE_V1
        or getattr(main_module, "__package__", None) not in (None, "")
        or getattr(main_module, "__spec__", None) is not None
        or getattr(main_module, "__cached__", None) is not None
        or cache != _sys.pycache_prefix
        or type(cache_fd) is not int
        or type(source_fd) is not int
        or type(package_fd) is not int
        or type(root_fd) is not int
        or type(fixed_names) is not tuple
        or type(file_states) is not tuple
        or type(held_source_directories) is not tuple
        or type(ancestry_kqueue) is not select.kqueue
        or type(ancestry_event_count) is not int
        or ancestry_event_count != len(held_source_directories)
    ):
        raise _error("trusted source launcher state changed")

    def filesystem_state(
        info: Any,
    ) -> tuple[int, int, int, int, int, int, int]:
        return (
            info.st_dev,
            info.st_ino,
            info.st_mode,
            info.st_nlink,
            info.st_size,
            info.st_mtime_ns,
            info.st_ctime_ns,
        )

    def filesystem_binding(info: Any) -> tuple[int, int, int]:
        return (info.st_dev, info.st_ino, info.st_mode)

    try:
        if ancestry_kqueue.control([], ancestry_event_count, 0):
            raise _error("trusted source ancestry changed")
        cache_info = _fstat(cache_fd)
        source_info = _fstat(source_fd)
        package_info = _fstat(package_fd)
        interpreter_info = _stat(executable)
        if filesystem_binding(_fstat(root_fd)) != root_state:
            raise _error("trusted filesystem anchor changed")
        expected_components = tuple(
            part for part in (source + os.sep + "parity_forge_universe").split(os.sep) if part
        )
        if tuple(record[1] for record in held_source_directories) != expected_components:
            raise _error("trusted source ancestry changed")
        previous_fd = root_fd
        for record in held_source_directories:
            if type(record) is not tuple or len(record) != 4:
                raise _error("trusted source ancestry record changed")
            parent_fd, name, child_fd, child_state = record
            if (
                parent_fd != previous_fd
                or type(parent_fd) is not int
                or type(child_fd) is not int
                or type(name) is not str
                or filesystem_binding(_fstat(child_fd)) != child_state
                or filesystem_binding(
                    _stat(name, dir_fd=parent_fd, follow_symlinks=False)
                )
                != child_state
            ):
                raise _error("trusted source ancestor binding changed")
            previous_fd = child_fd
        if previous_fd != package_fd or not any(
            record[2] == source_fd for record in held_source_directories
        ):
            raise _error("trusted source descriptors changed")
        named_cache = _stat(cache, follow_symlinks=False)
        named_source = _stat(source, follow_symlinks=False)
        named_package = _stat(
            "parity_forge_universe",
            dir_fd=source_fd,
            follow_symlinks=False,
        )
        if (
            filesystem_state(cache_info) != cache_state
            or filesystem_state(named_cache) != cache_state
            or not _isdir(cache_info.st_mode)
            or cache_info.st_mode & 0o777 != 0o700
            or cache_info.st_uid != os.geteuid()
            or _listdir(cache_fd)
            or filesystem_state(source_info) != source_state
            or filesystem_state(named_source) != source_state
            or not _isdir(source_info.st_mode)
            or filesystem_state(package_info) != package_state
            or filesystem_state(named_package) != package_state
            or not _isdir(package_info.st_mode)
            or set(_listdir(source_fd))
            != {"parity_forge", "parity_forge_universe"}
            or set(_listdir(package_fd)) != set(fixed_names)
            or filesystem_state(interpreter_info) != interpreter_state
            or interpreter_info.st_uid != 0
            or not _isreg(interpreter_info.st_mode)
            or _access(executable, _w_ok)
        ):
            raise _error("trusted source launcher binding changed")
        observed_states = []
        for name in fixed_names:
            info = _stat(name, dir_fd=package_fd, follow_symlinks=False)
            if not _isreg(info.st_mode):
                raise _error("trusted source entry type changed")
            observed_states.append((name,) + filesystem_state(info))
        if tuple(observed_states) != file_states:
            raise _error("trusted source entry changed")
    except OSError as error:
        raise _error("trusted source launcher became unavailable") from error

    if "parity_forge" in _sys.modules or any(
        name.startswith("parity_forge.") for name in _sys.modules
    ):
        raise _error("legacy game package entered the census process")


def _require_source_only_runtime_v1(
    _flags: Any = sys.flags,
    _pycache_prefix: Optional[str] = sys.pycache_prefix,
    _abspath: Any = os.path.abspath,
    _open: Any = os.open,
    _fstat: Any = os.fstat,
    _listdir: Any = os.listdir,
    _close: Any = os.close,
    _geteuid: Any = os.geteuid,
    _isdir: Any = stat.S_ISDIR,
    _imode: Any = stat.S_IMODE,
    _error: Any = StaticCensusStageError,
) -> None:
    """Require the fixed fresh-cache interpreter boundary for public use."""

    if (
        _flags.isolated != 1
        or _flags.ignore_environment != 1
        or _flags.no_user_site != 1
        or _flags.no_site != 1
        or _flags.dont_write_bytecode != 1
        or _flags.optimize != 0
        or _flags.debug != 0
        or _flags.inspect != 0
        or _flags.interactive != 0
        or _flags.verbose != 0
        or _flags.bytes_warning != 0
        or _flags.quiet != 0
        or _flags.dev_mode is not False
        or _flags.utf8_mode != 1
    ):
        raise _error(
            "public stage requires the source-only isolated interpreter"
        )
    if (
        type(_pycache_prefix) is not str
        or not _pycache_prefix
        or _abspath(_pycache_prefix) != _pycache_prefix
    ):
        raise _error("public stage requires an absolute fresh pycache prefix")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    descriptor = -1
    try:
        descriptor = _open(_pycache_prefix, flags)
        info = _fstat(descriptor)
        if (
            not _isdir(info.st_mode)
            or _imode(info.st_mode) != 0o700
            or info.st_uid != _geteuid()
        ):
            raise _error(
                "public stage pycache prefix must be a private owned directory"
            )
        if _listdir(descriptor):
            raise _error("public stage pycache prefix is not empty")
    except OSError as error:
        raise _error("public stage pycache prefix is unavailable") from error
    finally:
        if descriptor >= 0:
            _close(descriptor)


def _make_runtime_binding_guard_v1(
    namespace: Dict[str, Any],
    stage_spec: Any,
    stage_spec_origin: Optional[str],
    catalog_bindings: Sequence[tuple[str, Any]],
    namespace_identity_bindings: Sequence[tuple[str, Any]],
    namespace_value_bindings: Sequence[tuple[str, Any]],
    dependency_identity_bindings: Sequence[tuple[Any, str, Any]],
    dependency_value_bindings: Sequence[tuple[Any, str, Any]],
    builtin_bindings: Sequence[tuple[str, Any]],
    *,
    _error: Any = StaticCensusStageError,
    _getattr: Any = getattr,
    _type: Any = type,
) -> Any:
    """Capture the guard's expectations outside its mutable module globals."""

    def require_runtime_bindings_v1() -> None:
        if any(
            namespace.get(name) is not expected
            for name, expected in catalog_bindings
        ):
            raise _error("production binding catalog changed")
        if any(
            namespace.get(name) is not expected
            for name, expected in namespace_identity_bindings
        ):
            raise _error("stage-local production binding changed")
        for name, expected in namespace_value_bindings:
            observed = namespace.get(name)
            if _type(observed) is not _type(expected) or observed != expected:
                raise _error("production stage constant changed")
        if any(
            _getattr(owner, name, None) is not expected
            for owner, name, expected in dependency_identity_bindings
        ):
            raise _error("production dependency binding changed")
        for owner, name, expected in dependency_value_bindings:
            observed = _getattr(owner, name, None)
            if _type(observed) is not _type(expected) or observed != expected:
                raise _error("production evidence coordinate changed")
        for name, expected in builtin_bindings:
            if name in namespace and namespace[name] is not expected:
                raise _error("production builtin binding changed")
        observed_spec = namespace.get("__spec__")
        if (
            observed_spec is not stage_spec
            or _getattr(observed_spec, "origin", None) != stage_spec_origin
        ):
            raise _error("production stage loader origin changed")

    return require_runtime_bindings_v1


def _repository_path_v1(
    repository: str,
    _resolve: Any = _RESOLVE_REPOSITORY_V1,
) -> Path:
    return _resolve(repository)


def _validate_runtime_origins_v1(
    repository: Path,
    _path_type: Any = Path,
    _abspath: Any = os.path.abspath,
    _getattr: Any = getattr,
    _stage_file: str = _STAGE_FILE_V1,
    _stage_spec: Any = _STAGE_SPEC_V1,
    _stage_spec_origin: Optional[str] = _STAGE_SPEC_ORIGIN_V1,
    _stage_module: Any = _STAGE_MODULE_V1,
    _stage_loader: Any = _STAGE_LOADER_V1,
    _stage_cached: Optional[str] = _STAGE_CACHED_V1,
    _loader_type: Any = _SOURCE_LOADER_TYPE_V1,
    _pycache_prefix: Optional[str] = sys.pycache_prefix,
    _sys_modules: Dict[str, Any] = sys.modules,
    _lexists: Any = os.path.lexists,
    _separator: str = os.sep,
    _modules: Sequence[tuple[str, Any, str, Any, Any, Optional[str]]] = (
        (
            "parity_forge_universe",
            _PACKAGE_MODULE_V1,
            "__init__.py",
            _PACKAGE_MODULE_V1.__loader__,
            _PACKAGE_MODULE_V1.__spec__,
            _PACKAGE_MODULE_V1.__cached__,
        ),
        (
            "parity_forge_universe.initial_structure",
            _INITIAL_MODULE_V1,
            "initial_structure.py",
            _INITIAL_MODULE_V1.__loader__,
            _INITIAL_MODULE_V1.__spec__,
            _INITIAL_MODULE_V1.__cached__,
        ),
        (
            "parity_forge_universe.schema_v4_compiler",
            _COMPILER_MODULE_V1,
            "schema_v4_compiler.py",
            _COMPILER_MODULE_V1.__loader__,
            _COMPILER_MODULE_V1.__spec__,
            _COMPILER_MODULE_V1.__cached__,
        ),
        (
            "parity_forge_universe.static_census",
            _CENSUS_MODULE_V1,
            "static_census.py",
            _CENSUS_MODULE_V1.__loader__,
            _CENSUS_MODULE_V1.__spec__,
            _CENSUS_MODULE_V1.__cached__,
        ),
        (
            "parity_forge_universe.static_census_evidence",
            _EVIDENCE_MODULE_V1,
            "static_census_evidence.py",
            _EVIDENCE_MODULE_V1.__loader__,
            _EVIDENCE_MODULE_V1.__spec__,
            _EVIDENCE_MODULE_V1.__cached__,
        ),
        (
            "parity_forge_universe.static_census_protocol",
            _PROTOCOL_MODULE_V1,
            "static_census_protocol.py",
            _PROTOCOL_MODULE_V1.__loader__,
            _PROTOCOL_MODULE_V1.__spec__,
            _PROTOCOL_MODULE_V1.__cached__,
        ),
        (
            "parity_forge_universe.static_census_reconstruction",
            _RECONSTRUCTION_MODULE_V1,
            "static_census_reconstruction.py",
            _RECONSTRUCTION_MODULE_V1.__loader__,
            _RECONSTRUCTION_MODULE_V1.__spec__,
            _RECONSTRUCTION_MODULE_V1.__cached__,
        ),
        (
            "parity_forge_universe.typed_occupancy",
            _UNIVERSE_MODULE_V1,
            "typed_occupancy.py",
            _UNIVERSE_MODULE_V1.__loader__,
            _UNIVERSE_MODULE_V1.__spec__,
            _UNIVERSE_MODULE_V1.__cached__,
        ),
    ),
    _error: Any = StaticCensusStageError,
) -> None:
    package = repository / "src" / "parity_forge_universe"
    expected_stage = package / "static_census_stage.py"
    if (
        _path_type(_abspath(_stage_file)) != expected_stage
        or type(_stage_spec_origin) is not str
        or _path_type(_abspath(_stage_spec_origin)) != expected_stage
        or _sys_modules.get(_stage_spec.name) is not _stage_module
        or type(_stage_loader) is not _loader_type
        or _stage_spec.loader is not _stage_loader
    ):
        raise _error("production stage origin changed")
    for name, module, filename, loader, spec, cached in _modules:
        origin = _getattr(module, "__file__", None)
        spec_origin = _getattr(spec, "origin", None)
        expected = package / filename
        if (
            _sys_modules.get(name) is not module
            or type(origin) is not str
            or _path_type(_abspath(origin)) != expected
            or type(spec_origin) is not str
            or _path_type(_abspath(spec_origin)) != expected
            or _getattr(module, "__loader__", None) is not loader
            or _getattr(module, "__spec__", None) is not spec
            or type(loader) is not _loader_type
            or _getattr(spec, "loader", None) is not loader
            or _getattr(module, "__cached__", None) != cached
            or _getattr(spec, "cached", None) != cached
        ):
            raise _error("production module origin changed")
    if type(_pycache_prefix) is not str:
        raise _error("production pycache prefix changed")
    prefix = _abspath(_pycache_prefix).rstrip(_separator) + _separator
    cache_records = ((_stage_cached, _stage_spec.cached),) + tuple(
        (cached, spec.cached)
        for _name, _module, _filename, _loader, spec, cached in _modules
    )
    if any(
        type(cached) is not str
        or cached != spec_cached
        or not _abspath(cached).startswith(prefix)
        or _lexists(cached)
        for cached, spec_cached in cache_records
    ):
        raise _error("production module cache is present or escaped its prefix")


def _summary_from_reconstruction_v1(reconstructed: Dict[str, Any]) -> Dict[str, Any]:
    if type(reconstructed) is not dict or set(reconstructed) != {
        "report",
        "report_ref",
        "report_summary",
    }:
        raise StaticCensusStageError("report reconstruction envelope changed")
    summary = reconstructed["report_summary"]
    if type(summary) is not dict:
        raise StaticCensusStageError("report reconstruction summary changed")
    return summary


def _terminal_result_v1(
    action: str,
    lifecycle: Optional[str],
    terminal_identity: Optional[str],
    reconstructed: Optional[Dict[str, Any]] = None,
    production_closure: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        _PUBLIC_RETURN_CLOSURE_KEY_V1: production_closure,
        "action": action,
        "lifecycle": lifecycle,
        "stage_id": _STAGE_ID_V1,
        "terminal_seal_or_null": terminal_identity,
    }
    if reconstructed is not None:
        result["report_ref"] = reconstructed["report_ref"]
        result["report_summary"] = _summary_from_reconstruction_v1(reconstructed)
    return result


def _recovery_result_v1(
    result: evidence.StaticCensusRecoveryResult,
    production_closure: Dict[str, Any],
) -> Dict[str, Any]:
    reconstructed = None
    if result.lifecycle == "COMPLETED":
        if type(result.report_bytes) is not bytes:
            raise StaticCensusStageError(
                "completed recovery lacks its validated report bytes"
            )
        reconstructed = _RECONSTRUCT_REPORT_V1(result.report_bytes)
    elif result.report_bytes is not None:
        raise StaticCensusStageError(
            "non-completed recovery unexpectedly carries report bytes"
        )
    return _terminal_result_v1(
        result.action,
        result.lifecycle,
        result.terminal_identity,
        reconstructed,
        production_closure,
    )


def _validate_recorded_bootstrap_v1(
    repository: Path,
    store: evidence._StaticCensusEvidenceStore,
) -> Dict[str, Any]:
    bootstrap = _VALIDATE_BOOTSTRAP_V1(store.read_bootstrap())
    references = bootstrap["references"]
    _VALIDATE_PROTOCOL_V1(references["protocol"])
    _VALIDATE_PRODUCTION_CLOSURE_V1(
        str(repository), references["production_closure"]
    )
    return bootstrap


def _authenticate_current_source_v1(repository: Path) -> Dict[str, Any]:
    """Build and immediately reseal the current reviewed production closure."""

    return _AUTHENTICATE_RECOVERY_CLOSURE_V1(str(repository))


def _recover_with_held_lock_v1(
    store: evidence._StaticCensusEvidenceStore,
    contract: evidence.StaticCensusEvidenceContract,
    repository: Path,
    _cap: Any = _EVIDENCE_MUTATION_CAPABILITY_V1,
) -> Dict[str, Any]:
    # Reconciliation can finish a pending hard-link publication.  Authenticate
    # the current implementation before even that first recoverable mutation,
    # including when no valid stored bootstrap can supply a closure reference.
    current_closure = _authenticate_current_source_v1(repository)
    try:
        store._reconcile_pending_publications(
            _cap
        )
        catalog = store.scan_fixed_catalog()
    except BaseException:
        # The evidence primitive owns durable contradiction publication for a
        # malformed catalog or interrupted publication window.
        _RESEAL_PRODUCTION_CLOSURE_V1(str(repository), current_closure)
        result = _RECOVER_STAGE_LOCKED_V1(
            _cap, store, contract, None, None
        )
        response = _recovery_result_v1(result, current_closure)
        if result.lifecycle in ("COMPLETED", "FAILED", "ORPHANED"):
            _RESEAL_PRODUCTION_CLOSURE_V1(
                str(repository), current_closure
            )
        return response
    bootstrap = None
    if catalog["bootstrap"] is not None:
        try:
            bootstrap = _validate_recorded_bootstrap_v1(repository, store)
        except _STORED_CLOSURE_INTEGRITY_ERROR_V1 as error:
            # The current repository was authenticated independently above,
            # so this dedicated error means the stored closure value itself
            # drifted.  It is evidence identity corruption, not an ambient Git
            # outage, and must become a durable contradiction.
            _RESEAL_PRODUCTION_CLOSURE_V1(str(repository), current_closure)
            try:
                _RECOVER_STAGE_LOCKED_V1(
                    _cap, store, contract, None, catalog
                )
            except _EVIDENCE_INTEGRITY_ERROR_V1:
                pass
            raise _EVIDENCE_INTEGRITY_ERROR_V1(
                "stored production closure failed closed"
            ) from error
        except _EVIDENCE_INTEGRITY_ERROR_V1:
            # An invalid stored bootstrap is an intrinsic evidence identity
            # contradiction.  Ambient Git/source lookup failures remain
            # write-free protocol errors and deliberately escape this branch.
            _RESEAL_PRODUCTION_CLOSURE_V1(str(repository), current_closure)
            _RECOVER_STAGE_LOCKED_V1(
                _cap, store, contract, None, catalog
            )
            raise _EVIDENCE_INTEGRITY_ERROR_V1(
                "invalid stored bootstrap disappeared during recovery"
            )
    closure = current_closure
    if any(value is not None for value in catalog.values()):
        # A merely present terminal is not yet a verified no-op and therefore
        # cannot suppress the current-source check before recovery.  When the
        # bootstrap is valid, reseal its exact recorded closure; otherwise use
        # the independently rebuilt current closure authenticated above.
        closure = (
            current_closure
            if bootstrap is None
            else bootstrap["references"]["production_closure"]
        )
        _RESEAL_PRODUCTION_CLOSURE_V1(str(repository), closure)
    result = _RECOVER_STAGE_LOCKED_V1(
        _cap, store, contract, bootstrap, catalog
    )
    response = _recovery_result_v1(result, closure)
    if result.lifecycle in ("COMPLETED", "FAILED", "ORPHANED"):
        # A recovery mutation receives a second check; a verified no-op gets
        # its sole current-source check here, immediately before return.
        _RESEAL_PRODUCTION_CLOSURE_V1(
            str(repository),
            closure,
        )
    return response


def _calculate_and_seal_v1(
    store: evidence._StaticCensusEvidenceStore,
    contract: evidence.StaticCensusEvidenceContract,
    repository: Path,
    bootstrap: Dict[str, Any],
    production_closure: Dict[str, Any],
    attempted_catalog: Dict[str, Any],
    _build: Any = _BUILD_CENSUS_V1,
    _serialize: Any = _SERIALIZE_REPORT_V1,
    _report_hash: Any = _REPORT_HASH_V1,
    _reconstruct: Any = _RECONSTRUCT_REPORT_V1,
    _reseal: Any = _RESEAL_PRODUCTION_CLOSURE_V1,
    _publish_report: Any = _PUBLISH_REPORT_V1,
    _seal_completed: Any = _SEAL_COMPLETED_V1,
    _seal_failed: Any = _SEAL_FAILED_V1,
    _failure_value: Any = _FAILURE_VALUE_V1,
    _cap: Any = _EVIDENCE_MUTATION_CAPABILITY_V1,
    _fixed_dependencies: tuple[Any, ...] = (
        _BUILD_CENSUS_V1,
        _SERIALIZE_REPORT_V1,
        _REPORT_HASH_V1,
        _RECONSTRUCT_REPORT_V1,
        _RESEAL_PRODUCTION_CLOSURE_V1,
        _PUBLISH_REPORT_V1,
        _SEAL_COMPLETED_V1,
        _SEAL_FAILED_V1,
        _FAILURE_VALUE_V1,
    ),
) -> Dict[str, Any]:
    def require_calculation_bindings() -> None:
        observed_dependencies = (
            _build,
            _serialize,
            _report_hash,
            _reconstruct,
            _reseal,
            _publish_report,
            _seal_completed,
            _seal_failed,
            _failure_value,
        )
        if any(
            observed is not expected
            for observed, expected in zip(
                observed_dependencies, _fixed_dependencies
            )
        ):
            # This function is private; explicit dependency arguments form its
            # test-only seam.  The public stage calls it only with the captured
            # production defaults, whose live bindings are checked below.
            return
        if (
            census.build_static_census_v1 is not _build
            or census.canonical_static_census_report_json_v1 is not _serialize
            or census.static_census_report_hash_v1 is not _report_hash
            or reconstruction.reconstruct_static_census_report_artifact_v1
            is not _reconstruct
            or protocol.reseal_static_census_production_closure_v1 is not _reseal
            or evidence._publish_report_v1 is not _publish_report
            or evidence._seal_completed_v1 is not _seal_completed
            or evidence._seal_failed_v1 is not _seal_failed
            or evidence.failure_value_v1 is not _failure_value
        ):
            raise StaticCensusStageError("production calculation binding changed")

    require_calculation_bindings()
    report_publication_started = False

    try:
        report = _build()
        require_calculation_bindings()
        canonical = _serialize(report)
        if type(canonical) is not str:
            raise StaticCensusStageError("static-census serializer changed type")
        try:
            report_bytes = canonical.encode("utf-8", "strict")
        except UnicodeEncodeError as error:
            raise StaticCensusStageError("static-census report is not UTF-8") from error
        reconstructed = _reconstruct(report_bytes)
        if _report_hash(report) != _summary_from_reconstruction_v1(
            reconstructed
        )["report_digest"]:
            raise StaticCensusStageError("live and reconstructed report digests differ")
        require_calculation_bindings()

        # The calculation is complete but no result is public yet.  Current
        # source, HEAD, tree, and active-plan bytes must still match bootstrap.
        _reseal(str(repository), production_closure)
        require_calculation_bindings()
        # From this point onward, a report may have reached its immutable
        # destination even if a later path-binding or postcondition check
        # raises.  Failure is therefore permanently inadmissible.
        report_publication_started = True
        published_reconstruction, report_catalog = _publish_report(
            _cap,
            store,
            contract,
            bootstrap,
            report_bytes,
            attempted_catalog,
        )
        if (
            type(published_reconstruction) is not dict
            or type(report_catalog) is not dict
            or _summary_from_reconstruction_v1(published_reconstruction)
            != _summary_from_reconstruction_v1(reconstructed)
            or published_reconstruction.get("report_ref")
            != reconstructed.get("report_ref")
        ):
            raise StaticCensusStageError(
                "published report receipt differs from calculation"
            )
        require_calculation_bindings()
        terminal = _seal_completed(
            _cap,
            store,
            contract,
            bootstrap,
            report_bytes,
            report_catalog,
        )

        # The seal helper returns only after a descriptor-backed postcondition
        # proves the exact calculated report and completed terminal.  Do not
        # rescan/recover here: a separately valid chain could be swapped into
        # the fixed path between those operations and be mutated instead.
        require_calculation_bindings()
        response = _terminal_result_v1(
            "COMPLETED",
            "COMPLETED",
            terminal["identity"],
            reconstructed,
            production_closure,
        )
        require_calculation_bindings()
        _reseal(str(repository), production_closure)
        return response
    except BaseException as error:
        # Once report publication starts, completion has precedence and
        # failure is permanently inadmissible.
        if report_publication_started:
            _reseal(str(repository), production_closure)
            raise
        failure_value = _failure_value(error)
        _reseal(str(repository), production_closure)
        # Do not adopt a fresh catalog after calculation began.  Any pending
        # publication or path swap must be judged against the exact ATTEMPTED
        # receipt; the evidence primitive turns a mismatch into contradiction
        # without ever publishing failure over a report.
        _reseal(str(repository), production_closure)
        terminal = _seal_failed(
            _cap,
            store,
            contract,
            bootstrap,
            failure_value,
            attempted_catalog,
        )
        response = _terminal_result_v1(
            "FAILED",
            "FAILED",
            terminal["identity"],
            production_closure=production_closure,
        )
        require_calculation_bindings()
        _reseal(str(repository), production_closure)
        return response


def _run_existing_with_held_lock_v1(
    store: evidence._StaticCensusEvidenceStore,
    contract: evidence.StaticCensusEvidenceContract,
    repository: Path,
    _cap: Any = _EVIDENCE_MUTATION_CAPABILITY_V1,
    expected_initial_catalog: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    current_closure = _authenticate_current_source_v1(repository)
    _RESEAL_PRODUCTION_CLOSURE_V1(str(repository), current_closure)
    try:
        if expected_initial_catalog is None:
            store._reconcile_pending_publications(
                _cap
            )
        catalog = store.scan_fixed_catalog()
    except BaseException:
        _RESEAL_PRODUCTION_CLOSURE_V1(str(repository), current_closure)
        _RECOVER_STAGE_LOCKED_V1(
            _cap, store, contract, None, None
        )
        raise StaticCensusStageError(
            "existing evidence catalog failed closed"
        )
    if (
        expected_initial_catalog is not None
        and (
            type(expected_initial_catalog) is not dict
            or catalog != expected_initial_catalog
        )
    ):
        _RESEAL_PRODUCTION_CLOSURE_V1(str(repository), current_closure)
        _RECOVER_STAGE_LOCKED_V1(
            _cap,
            store,
            contract,
            None,
            expected_initial_catalog,
        )
        raise StaticCensusStageError(
            "existing evidence changed before authenticated processing"
        )
    if not any(value is not None for value in catalog.values()):
        return None
    if catalog["bootstrap"] is None or catalog["contradiction"] is not None:
        _RESEAL_PRODUCTION_CLOSURE_V1(str(repository), current_closure)
        _RECOVER_STAGE_LOCKED_V1(
            _cap, store, contract, None, catalog
        )
        raise StaticCensusStageError(
            "existing evidence lacks an authenticated bootstrap"
        )

    try:
        bootstrap = _validate_recorded_bootstrap_v1(repository, store)
    except _STORED_CLOSURE_INTEGRITY_ERROR_V1 as error:
        _RESEAL_PRODUCTION_CLOSURE_V1(str(repository), current_closure)
        try:
            _RECOVER_STAGE_LOCKED_V1(
                _cap, store, contract, None, catalog
            )
        except _EVIDENCE_INTEGRITY_ERROR_V1:
            pass
        raise _EVIDENCE_INTEGRITY_ERROR_V1(
            "stored production closure failed closed"
        ) from error
    except _EVIDENCE_INTEGRITY_ERROR_V1:
        _RESEAL_PRODUCTION_CLOSURE_V1(str(repository), current_closure)
        _RECOVER_STAGE_LOCKED_V1(
            _cap, store, contract, None, catalog
        )
        raise StaticCensusStageError(
            "invalid existing bootstrap disappeared during recovery"
        )
    try:
        state = _VALIDATE_CHAIN_SNAPSHOT_V1(
            contract,
            bootstrap,
            _LOAD_CHAIN_SNAPSHOT_MATCHING_CATALOG_V1(store, catalog),
        )
    except BaseException:
        closure = bootstrap["references"]["production_closure"]
        _RESEAL_PRODUCTION_CLOSURE_V1(str(repository), closure)
        _RECOVER_STAGE_LOCKED_V1(
            _cap, store, contract, bootstrap, catalog
        )
        raise StaticCensusStageError(
            "existing evidence changed before its bound recovery"
        )
    if state != "BOOTSTRAPPED":
        closure = bootstrap["references"]["production_closure"]
        _RESEAL_PRODUCTION_CLOSURE_V1(str(repository), closure)
        result = _RECOVER_STAGE_LOCKED_V1(
            _cap, store, contract, bootstrap, catalog
        )
        response = _recovery_result_v1(result, closure)
        if result.lifecycle in ("COMPLETED", "FAILED", "ORPHANED"):
            _RESEAL_PRODUCTION_CLOSURE_V1(str(repository), closure)
        return response

    production_closure = bootstrap["references"]["production_closure"]
    _RESEAL_PRODUCTION_CLOSURE_V1(str(repository), production_closure)
    _attempted_snapshot, attempted_catalog = _BEGIN_STAGE_V1(
        _cap, store, contract, bootstrap, catalog
    )
    return _calculate_and_seal_v1(
        store,
        contract,
        repository,
        bootstrap,
        production_closure,
        attempted_catalog,
        _cap=_cap,
    )


def _run_existing_root_v1(
    repository: Path,
    evidence_root: Path,
    contract: evidence.StaticCensusEvidenceContract,
    _cap: Any = _EVIDENCE_MUTATION_CAPABILITY_V1,
) -> Optional[Dict[str, Any]]:
    _require_runtime_bindings_v1()
    _require_source_only_runtime_v1()
    _require_trusted_source_launcher_v1(str(repository), "run")
    with _OPEN_RECOVERY_STORE_V1(
        _cap, evidence_root
    ) as store:
        if store is None:
            return None
        with store._stage_lock(
            _cap, blocking=False
        ):
            return _run_existing_with_held_lock_v1(
                store, contract, repository, _cap
            )


def _run_static_census_stage_impl_v1(
    repository: str,
    _cap: Any = _EVIDENCE_MUTATION_CAPABILITY_V1,
) -> Dict[str, Any]:
    _require_runtime_bindings_v1()
    _require_source_only_runtime_v1()
    _require_trusted_source_launcher_v1(repository, "run")
    repository_path = _repository_path_v1(repository)
    _validate_runtime_origins_v1(repository_path)
    evidence_root = repository_path / _EVIDENCE_ROOT_RELATIVE_V1
    contract = _FIXED_EVIDENCE_CONTRACT_V1()

    existing = _run_existing_root_v1(
        repository_path, evidence_root, contract, _cap
    )
    if existing is not None:
        return existing

    protocol_value = _VALIDATE_PROTOCOL_V1(_BUILD_PROTOCOL_V1())
    production_closure = _AUTHENTICATE_RECOVERY_CLOSURE_V1(
        str(repository_path)
    )
    bootstrap = _BUILD_BOOTSTRAP_V1(protocol_value, production_closure)

    with _EVIDENCE_STORE_V1._for_run(
        _cap, evidence_root
    ) as store:
        with store._stage_lock(
            _cap, blocking=False
        ):
            _RESEAL_PRODUCTION_CLOSURE_V1(
                str(repository_path), production_closure
            )
            try:
                store._reconcile_pending_publications(
                    _cap
                )
                catalog = store.scan_fixed_catalog()
            except BaseException:
                _RESEAL_PRODUCTION_CLOSURE_V1(
                    str(repository_path), production_closure
                )
                _RECOVER_STAGE_LOCKED_V1(
                    _cap, store, contract, None, None
                )
                raise StaticCensusStageError(
                    "fresh evidence catalog failed closed"
                )
            if any(value is not None for value in catalog.values()):
                return _run_existing_with_held_lock_v1(
                    store,
                    contract,
                    repository_path,
                    _cap,
                    expected_initial_catalog=catalog,
                )

            # Creation of operational directories precedes this reseal, but no
            # evidence identity or attempt exists.  A failure consumes nothing.
            _RESEAL_PRODUCTION_CLOSURE_V1(
                str(repository_path), production_closure
            )
            _bootstrap_ref, bootstrap_catalog = _PUBLISH_BOOTSTRAP_V1(
                _cap,
                store,
                contract,
                bootstrap,
                catalog,
            )
            _attempted_snapshot, attempted_catalog = _BEGIN_STAGE_V1(
                _cap,
                store,
                contract,
                bootstrap,
                bootstrap_catalog,
            )
            return _calculate_and_seal_v1(
                store,
                contract,
                repository_path,
                bootstrap,
                production_closure,
                attempted_catalog,
                _cap=_cap,
            )


def _recover_static_census_stage_impl_v1(
    repository: str,
    _cap: Any = _EVIDENCE_MUTATION_CAPABILITY_V1,
) -> Dict[str, Any]:
    _require_runtime_bindings_v1()
    _require_source_only_runtime_v1()
    _require_trusted_source_launcher_v1(repository, "recover")
    repository_path = _repository_path_v1(repository)
    _validate_runtime_origins_v1(repository_path)
    evidence_root = repository_path / _EVIDENCE_ROOT_RELATIVE_V1
    contract = _FIXED_EVIDENCE_CONTRACT_V1()
    with _OPEN_RECOVERY_STORE_V1(
        _cap, evidence_root
    ) as store:
        if store is None:
            return _terminal_result_v1("NO_EVIDENCE", None, None)
        with store._stage_lock(
            _cap, blocking=False
        ):
            return _recover_with_held_lock_v1(
                store, contract, repository_path, _cap
            )


def _fixed_public_entrypoint(
    implementation: Any,
    global_name: str,
    command: str,
    runtime_guard: Any,
    source_runtime_guard: Any,
    source_launcher_guard: Any,
    reseal: Any,
    return_closure_key: str,
    _namespace: Dict[str, Any] = globals(),
    _error: Any = StaticCensusStageError,
) -> Any:
    def invoke(repository: str) -> Dict[str, Any]:
        if (
            _namespace.get(global_name) is not implementation
            or _namespace.get("_require_runtime_bindings_v1") is not runtime_guard
        ):
            raise _error("stage implementation binding changed")
        runtime_guard()
        source_runtime_guard()
        source_launcher_guard(repository, command)
        result = implementation(repository)
        if type(result) is not dict or return_closure_key not in result:
            raise _error("stage implementation return envelope changed")
        production_closure = result.pop(return_closure_key)
        runtime_guard()
        source_runtime_guard()
        source_launcher_guard(repository, command)
        if production_closure is not None:
            # This is deliberately the final effect before the public return:
            # all evidence/lock cleanup and every post-execution guard already
            # completed inside the implementation and above.
            reseal(repository, production_closure)
        return result

    return invoke


_STAGE_LOCAL_BINDINGS_V1 = (
    ("_require_trusted_source_launcher_v1", _require_trusted_source_launcher_v1),
    ("_require_source_only_runtime_v1", _require_source_only_runtime_v1),
    ("_repository_path_v1", _repository_path_v1),
    ("_validate_runtime_origins_v1", _validate_runtime_origins_v1),
    ("_summary_from_reconstruction_v1", _summary_from_reconstruction_v1),
    ("_terminal_result_v1", _terminal_result_v1),
    ("_recovery_result_v1", _recovery_result_v1),
    ("_validate_recorded_bootstrap_v1", _validate_recorded_bootstrap_v1),
    ("_authenticate_current_source_v1", _authenticate_current_source_v1),
    ("_recover_with_held_lock_v1", _recover_with_held_lock_v1),
    ("_calculate_and_seal_v1", _calculate_and_seal_v1),
    ("_run_existing_with_held_lock_v1", _run_existing_with_held_lock_v1),
    ("_run_existing_root_v1", _run_existing_root_v1),
    ("_run_static_census_stage_impl_v1", _run_static_census_stage_impl_v1),
    ("_recover_static_census_stage_impl_v1", _recover_static_census_stage_impl_v1),
    ("_fixed_public_entrypoint", _fixed_public_entrypoint),
)
_STAGE_NAMESPACE_IDENTITY_BINDINGS_V1 = (
    ("argparse", argparse),
    ("json", json),
    ("os", os),
    ("Path", Path),
    ("select", select),
    ("stat", stat),
    ("sys", sys),
    ("census", census),
    ("evidence", evidence),
    ("protocol", protocol),
    ("reconstruction", reconstruction),
    ("_CENSUS_MODULE_V1", _CENSUS_MODULE_V1),
    ("_EVIDENCE_MODULE_V1", _EVIDENCE_MODULE_V1),
    ("_PROTOCOL_MODULE_V1", _PROTOCOL_MODULE_V1),
    ("_RECONSTRUCTION_MODULE_V1", _RECONSTRUCTION_MODULE_V1),
    ("_PACKAGE_MODULE_V1", _PACKAGE_MODULE_V1),
    ("_INITIAL_MODULE_V1", _INITIAL_MODULE_V1),
    ("_COMPILER_MODULE_V1", _COMPILER_MODULE_V1),
    ("_UNIVERSE_MODULE_V1", _UNIVERSE_MODULE_V1),
    ("_BUILD_CENSUS_V1", _BUILD_CENSUS_V1),
    ("_SERIALIZE_REPORT_V1", _SERIALIZE_REPORT_V1),
    ("_REPORT_HASH_V1", _REPORT_HASH_V1),
    ("_RECONSTRUCT_REPORT_V1", _RECONSTRUCT_REPORT_V1),
    ("_EVIDENCE_STORE_V1", _EVIDENCE_STORE_V1),
    ("_EVIDENCE_INTEGRITY_ERROR_V1", _EVIDENCE_INTEGRITY_ERROR_V1),
    ("_FIXED_EVIDENCE_CONTRACT_V1", _FIXED_EVIDENCE_CONTRACT_V1),
    ("_OPEN_RECOVERY_STORE_V1", _OPEN_RECOVERY_STORE_V1),
    ("_VALIDATE_BOOTSTRAP_V1", _VALIDATE_BOOTSTRAP_V1),
    ("_BUILD_BOOTSTRAP_V1", _BUILD_BOOTSTRAP_V1),
    ("_PUBLISH_BOOTSTRAP_V1", _PUBLISH_BOOTSTRAP_V1),
    ("_BEGIN_STAGE_V1", _BEGIN_STAGE_V1),
    ("_PUBLISH_REPORT_V1", _PUBLISH_REPORT_V1),
    ("_SEAL_COMPLETED_V1", _SEAL_COMPLETED_V1),
    ("_SEAL_FAILED_V1", _SEAL_FAILED_V1),
    ("_FAILURE_VALUE_V1", _FAILURE_VALUE_V1),
    (
        "_LOAD_CHAIN_SNAPSHOT_MATCHING_CATALOG_V1",
        _LOAD_CHAIN_SNAPSHOT_MATCHING_CATALOG_V1,
    ),
    ("_VALIDATE_CHAIN_SNAPSHOT_V1", _VALIDATE_CHAIN_SNAPSHOT_V1),
    ("_RECOVER_STAGE_LOCKED_V1", _RECOVER_STAGE_LOCKED_V1),
    ("_BUILD_PROTOCOL_V1", _BUILD_PROTOCOL_V1),
    ("_VALIDATE_PROTOCOL_V1", _VALIDATE_PROTOCOL_V1),
    ("_RESOLVE_REPOSITORY_V1", _RESOLVE_REPOSITORY_V1),
    ("_BUILD_PRODUCTION_CLOSURE_V1", _BUILD_PRODUCTION_CLOSURE_V1),
    (
        "_AUTHENTICATE_RECOVERY_CLOSURE_V1",
        _AUTHENTICATE_RECOVERY_CLOSURE_V1,
    ),
    (
        "_STORED_CLOSURE_INTEGRITY_ERROR_V1",
        _STORED_CLOSURE_INTEGRITY_ERROR_V1,
    ),
    ("_VALIDATE_PRODUCTION_CLOSURE_V1", _VALIDATE_PRODUCTION_CLOSURE_V1),
    ("_RESEAL_PRODUCTION_CLOSURE_V1", _RESEAL_PRODUCTION_CLOSURE_V1),
    ("_STAGE_SPEC_V1", _STAGE_SPEC_V1),
    ("_STAGE_MODULE_V1", _STAGE_MODULE_V1),
    ("_STAGE_LOADER_V1", _STAGE_LOADER_V1),
    ("_SOURCE_LOADER_TYPE_V1", _SOURCE_LOADER_TYPE_V1),
    ("_SOURCE_BOOTSTRAP_ATTESTATION_V1", _SOURCE_BOOTSTRAP_ATTESTATION_V1),
    ("__loader__", _STAGE_LOADER_V1),
    ("StaticCensusStageError", StaticCensusStageError),
)
_STAGE_NAMESPACE_VALUE_BINDINGS_V1 = (
    ("__file__", _STAGE_FILE_V1),
    ("__cached__", _STAGE_CACHED_V1),
    ("_STAGE_FILE_V1", _STAGE_FILE_V1),
    ("_STAGE_CACHED_V1", _STAGE_CACHED_V1),
    ("_STAGE_SPEC_ORIGIN_V1", _STAGE_SPEC_ORIGIN_V1),
    ("_EVIDENCE_ROOT_RELATIVE_V1", _EVIDENCE_ROOT_RELATIVE_V1),
    ("_STAGE_ID_V1", _STAGE_ID_V1),
    ("_PUBLIC_RETURN_CLOSURE_KEY_V1", _PUBLIC_RETURN_CLOSURE_KEY_V1),
)
_STAGE_DEPENDENCY_IDENTITY_BINDINGS_V1 = (
    (census, "build_static_census_v1", _BUILD_CENSUS_V1),
    (census, "canonical_static_census_report_json_v1", _SERIALIZE_REPORT_V1),
    (census, "static_census_report_hash_v1", _REPORT_HASH_V1),
    (census, "initial", _INITIAL_MODULE_V1),
    (census, "compiler", _COMPILER_MODULE_V1),
    (census, "universe", _UNIVERSE_MODULE_V1),
    (
        reconstruction,
        "reconstruct_static_census_report_artifact_v1",
        _RECONSTRUCT_REPORT_V1,
    ),
    (
        evidence,
        "_claim_stage_mutation_capability_v1",
        _CLAIM_EVIDENCE_MUTATION_CAPABILITY_V1,
    ),
    (evidence, "_StaticCensusEvidenceStore", _EVIDENCE_STORE_V1),
    (
        evidence,
        "StaticCensusEvidenceIntegrityError",
        _EVIDENCE_INTEGRITY_ERROR_V1,
    ),
    (
        evidence,
        "fixed_static_census_evidence_contract_v1",
        _FIXED_EVIDENCE_CONTRACT_V1,
    ),
    (evidence, "_open_recovery_store_v1", _OPEN_RECOVERY_STORE_V1),
    (evidence, "validate_bootstrap_v1", _VALIDATE_BOOTSTRAP_V1),
    (evidence, "build_bootstrap_v1", _BUILD_BOOTSTRAP_V1),
    (evidence, "_publish_bootstrap_v1", _PUBLISH_BOOTSTRAP_V1),
    (evidence, "_begin_stage_v1", _BEGIN_STAGE_V1),
    (evidence, "_publish_report_v1", _PUBLISH_REPORT_V1),
    (evidence, "_seal_completed_v1", _SEAL_COMPLETED_V1),
    (evidence, "_seal_failed_v1", _SEAL_FAILED_V1),
    (evidence, "failure_value_v1", _FAILURE_VALUE_V1),
    (
        evidence,
        "_load_chain_snapshot_matching_catalog_v1",
        _LOAD_CHAIN_SNAPSHOT_MATCHING_CATALOG_V1,
    ),
    (evidence, "validate_chain_snapshot_v1", _VALIDATE_CHAIN_SNAPSHOT_V1),
    (evidence, "_recover_stage_locked_v1", _RECOVER_STAGE_LOCKED_V1),
    (protocol, "build_static_census_protocol_v1", _BUILD_PROTOCOL_V1),
    (protocol, "validate_static_census_protocol_v1", _VALIDATE_PROTOCOL_V1),
    (protocol, "resolve_static_census_repository_v1", _RESOLVE_REPOSITORY_V1),
    (
        protocol,
        "build_static_census_production_closure_v1",
        _BUILD_PRODUCTION_CLOSURE_V1,
    ),
    (
        protocol,
        "authenticate_static_census_recovery_closure_v1",
        _AUTHENTICATE_RECOVERY_CLOSURE_V1,
    ),
    (
        protocol,
        "StaticCensusStoredClosureIntegrityError",
        _STORED_CLOSURE_INTEGRITY_ERROR_V1,
    ),
    (
        protocol,
        "validate_static_census_production_closure_v1",
        _VALIDATE_PRODUCTION_CLOSURE_V1,
    ),
    (
        protocol,
        "reseal_static_census_production_closure_v1",
        _RESEAL_PRODUCTION_CLOSURE_V1,
    ),
    (os, "path", os.path),
    (os.path, "abspath", os.path.abspath),
    (os.path, "lexists", os.path.lexists),
    (select, "kqueue", select.kqueue),
    (os, "access", os.access),
    (os, "close", os.close),
    (os, "fstat", os.fstat),
    (os, "geteuid", os.geteuid),
    (os, "listdir", os.listdir),
    (os, "open", os.open),
    (os, "stat", os.stat),
    (stat, "S_IMODE", stat.S_IMODE),
    (stat, "S_ISDIR", stat.S_ISDIR),
    (stat, "S_ISREG", stat.S_ISREG),
    (json, "dumps", json.dumps),
    (argparse, "ArgumentParser", argparse.ArgumentParser),
    (sys, "argv", sys.argv),
    (sys, "implementation", sys.implementation),
    (sys, "meta_path", sys.meta_path),
    (sys, "modules", sys.modules),
    (sys, "path", sys.path),
    (sys, "path_hooks", sys.path_hooks),
    (sys, "warnoptions", sys.warnoptions),
    (sys, "_xoptions", sys._xoptions),
)
_STAGE_DEPENDENCY_VALUE_BINDINGS_V1 = (
    (evidence, "EVIDENCE_ROOT_RELATIVE_V1", _EVIDENCE_ROOT_RELATIVE_V1),
    (evidence, "STAGE_ID_V1", _STAGE_ID_V1),
    (os, "O_DIRECTORY", getattr(os, "O_DIRECTORY", 0)),
    (os, "O_NOFOLLOW", getattr(os, "O_NOFOLLOW", 0)),
    (os, "O_NONBLOCK", getattr(os, "O_NONBLOCK", 0)),
    (os, "O_RDONLY", os.O_RDONLY),
    (os, "sep", os.sep),
    (os, "W_OK", os.W_OK),
    (sys, "flags", sys.flags),
    (sys, "executable", sys.executable),
    (sys, "pycache_prefix", sys.pycache_prefix),
    (sys, "version_info", sys.version_info),
)
_STAGE_BUILTIN_BINDINGS_V1 = (
    ("BaseException", BaseException),
    ("OSError", OSError),
    ("UnicodeDecodeError", UnicodeDecodeError),
    ("UnicodeEncodeError", UnicodeEncodeError),
    ("ValueError", ValueError),
    ("any", any),
    ("dict", dict),
    ("getattr", getattr),
    ("globals", globals),
    ("int", int),
    ("list", list),
    ("len", len),
    ("print", print),
    ("set", set),
    ("str", str),
    ("tuple", tuple),
    ("type", type),
    ("zip", zip),
)
_STAGE_CATALOG_BINDINGS_V1 = (
    ("_STAGE_LOCAL_BINDINGS_V1", _STAGE_LOCAL_BINDINGS_V1),
    (
        "_STAGE_NAMESPACE_IDENTITY_BINDINGS_V1",
        _STAGE_NAMESPACE_IDENTITY_BINDINGS_V1,
    ),
    ("_STAGE_NAMESPACE_VALUE_BINDINGS_V1", _STAGE_NAMESPACE_VALUE_BINDINGS_V1),
    (
        "_STAGE_DEPENDENCY_IDENTITY_BINDINGS_V1",
        _STAGE_DEPENDENCY_IDENTITY_BINDINGS_V1,
    ),
    (
        "_STAGE_DEPENDENCY_VALUE_BINDINGS_V1",
        _STAGE_DEPENDENCY_VALUE_BINDINGS_V1,
    ),
    ("_STAGE_BUILTIN_BINDINGS_V1", _STAGE_BUILTIN_BINDINGS_V1),
)

_require_runtime_bindings_v1 = _make_runtime_binding_guard_v1(
    globals(),
    _STAGE_SPEC_V1,
    _STAGE_SPEC_ORIGIN_V1,
    _STAGE_CATALOG_BINDINGS_V1,
    _STAGE_NAMESPACE_IDENTITY_BINDINGS_V1 + _STAGE_LOCAL_BINDINGS_V1,
    _STAGE_NAMESPACE_VALUE_BINDINGS_V1,
    _STAGE_DEPENDENCY_IDENTITY_BINDINGS_V1,
    _STAGE_DEPENDENCY_VALUE_BINDINGS_V1,
    _STAGE_BUILTIN_BINDINGS_V1,
)
del _make_runtime_binding_guard_v1


run_static_census_stage_v1 = _fixed_public_entrypoint(
    _run_static_census_stage_impl_v1,
    "_run_static_census_stage_impl_v1",
    "run",
    _require_runtime_bindings_v1,
    _require_source_only_runtime_v1,
    _require_trusted_source_launcher_v1,
    _RESEAL_PRODUCTION_CLOSURE_V1,
    _PUBLIC_RETURN_CLOSURE_KEY_V1,
)
recover_static_census_stage_v1 = _fixed_public_entrypoint(
    _recover_static_census_stage_impl_v1,
    "_recover_static_census_stage_impl_v1",
    "recover",
    _require_runtime_bindings_v1,
    _require_source_only_runtime_v1,
    _require_trusted_source_launcher_v1,
    _RESEAL_PRODUCTION_CLOSURE_V1,
    _PUBLIC_RETURN_CLOSURE_KEY_V1,
)

# The opaque evidence mutation capability is retained only by private function
# defaults/closures.  It is intentionally absent from the stage module's
# ordinary namespace and cannot be obtained through the public API surface.
del _EVIDENCE_MUTATION_CAPABILITY_V1
del _CLAIM_EVIDENCE_MUTATION_CAPABILITY_V1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=(
            "/usr/bin/python3 -I -B -S -X "
            "pycache_prefix=<fresh-private-empty-directory> "
            "/absolute/repository/src/parity_forge_universe/"
            "static_census_stage.py"
        )
    )
    parser.add_argument("command", choices=("run", "recover"))
    parser.add_argument("--repository", required=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = _build_parser().parse_args(argv)
    result = (
        run_static_census_stage_v1(arguments.repository)
        if arguments.command == "run"
        else recover_static_census_stage_v1(arguments.repository)
    )
    print(
        json.dumps(
            result,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = (
    "StaticCensusStageError",
    "recover_static_census_stage_v1",
    "run_static_census_stage_v1",
)
