"""Read-only reconstruction of the failed Plan-0013 assessment report.

This module deliberately exposes no evidence lifecycle operation.  It reads the
fixed V2 store, authenticates the five completed assessment parents through the
production parent join, and returns the report computed by the frozen Plan-0013
assessment rules.  It does not publish an attestation; that is a later Plan-0014
slice.
"""

from __future__ import annotations

import contextlib
import errno
import os
import stat
from pathlib import Path
from typing import Any, Dict, Iterator, Tuple

from .atlas_assessment_core import (
    ATLAS_ASSESSMENT_STAGE_ID_V1,
    ATLAS_ASSESSMENT_STAGE_PROTOCOL_ID_V1,
    _assessment_parent_inputs_v1,
    _assessment_prerequisites_v1,
    _build_atlas_assessment_report_v1,
)
from .atlas_evidence import ImmutableEvidenceStore, read_authenticated_stage_inputs


PLAN0013_ATLAS_EVIDENCE_ROOT_RELATIVE_V1 = (
    "experiments/runs/plan0013-atlas-development-evidence-v2"
)
PLAN0013_ASSESSMENT_COMPLETED_PARENT_COUNT_V1 = 5

_EXISTING_STORE_PATH_V1: Tuple[str, ...] = (
    "experiments",
    "runs",
    "plan0013-atlas-development-evidence-v2",
)
_REQUIRED_STORE_DIRECTORIES_V1: Tuple[str, ...] = (
    "stages",
    "manifest-bootstrap",
)
_READ_ONLY_DIRECTORY_FLAGS_V1 = (
    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
)


def _open_existing_directory_at_v1(parent_fd: int, name: str) -> int:
    try:
        child_fd = os.open(
            name, _READ_ONLY_DIRECTORY_FLAGS_V1, dir_fd=parent_fd
        )
    except FileNotFoundError:
        raise
    except OSError as error:
        if error.errno in (errno.ELOOP, errno.ENOTDIR):
            raise ValueError(
                "the fixed Plan-0013 V2 evidence store must use real directories"
            ) from error
        raise
    info = os.fstat(child_fd)
    if not stat.S_ISDIR(info.st_mode):
        os.close(child_fd)
        raise ValueError(
            "the fixed Plan-0013 V2 evidence store must use real directories"
        )
    return child_fd


@contextlib.contextmanager
def _open_existing_store_path_v1(repository_path: Path) -> Iterator[int]:
    """Open the fixed store one real directory component at a time."""

    if not repository_path.is_absolute():
        raise ValueError("repository path must be absolute")
    try:
        anchor_fd = os.open(
            repository_path.anchor, _READ_ONLY_DIRECTORY_FLAGS_V1
        )
    except FileNotFoundError as error:
        raise FileNotFoundError(
            "the fixed Plan-0013 V2 evidence store is incomplete"
        ) from error
    except OSError as error:
        raise ValueError("repository must be a real directory") from error
    current_fd = anchor_fd
    try:
        components = (
            tuple(repository_path.parts[1:]) + _EXISTING_STORE_PATH_V1
        )
        for component in components:
            try:
                next_fd = _open_existing_directory_at_v1(current_fd, component)
            except FileNotFoundError as error:
                raise FileNotFoundError(
                    "the fixed Plan-0013 V2 evidence store is incomplete"
                ) from error
            if current_fd != anchor_fd:
                os.close(current_fd)
            current_fd = next_fd
        yield current_fd
    finally:
        if current_fd != anchor_fd:
            os.close(current_fd)
        os.close(anchor_fd)


@contextlib.contextmanager
def _open_existing_v2_store_v1(
    repository_path: Path, evidence_root: Path
) -> Iterator[ImmutableEvidenceStore]:
    """Yield a reader bound to the exact directory descriptor just validated."""

    with _open_existing_store_path_v1(repository_path) as evidence_root_fd:
        try:
            for component in _REQUIRED_STORE_DIRECTORIES_V1:
                directory_fd = _open_existing_directory_at_v1(
                    evidence_root_fd, component
                )
                os.close(directory_fd)
        except FileNotFoundError as error:
            raise FileNotFoundError(
                "the fixed Plan-0013 V2 evidence store is incomplete"
            ) from error
        except NotADirectoryError as error:
            raise ValueError(
                "the fixed Plan-0013 V2 evidence store must use real directories"
            ) from error
        with ImmutableEvidenceStore.from_read_only_directory_fd(
            evidence_root, evidence_root_fd
        ) as store:
            yield store


def _require_five_completed_parents_v1(parent_terminal_seals: Tuple[Any, ...]) -> None:
    if len(parent_terminal_seals) != PLAN0013_ASSESSMENT_COMPLETED_PARENT_COUNT_V1:
        raise ValueError("Plan-0013 assessment must have exactly five parents")
    for seal in parent_terminal_seals:
        if seal["payload"]["lifecycle"] != "COMPLETED":
            raise ValueError("Plan-0013 assessment parent is not completed")


def reconstruct_plan0013_atlas_assessment_report_v1(
    repository: str,
) -> Dict[str, Any]:
    """Rebuild the frozen report from the five immutable V2 parent stages.

    ``repository`` is the only input.  The evidence location, target stage,
    parent identities, protocol, schedules, raw ledgers, and report rules all
    come from the fixed authenticated Plan-0013 chain.
    """

    if type(repository) is not str or not repository:
        raise ValueError("repository must be a nonempty exact string")
    repository_path = Path(os.path.abspath(repository))
    evidence_root = repository_path / PLAN0013_ATLAS_EVIDENCE_ROOT_RELATIVE_V1

    with _open_existing_v2_store_v1(repository_path, evidence_root) as store:
        inputs = read_authenticated_stage_inputs(
            store, ATLAS_ASSESSMENT_STAGE_ID_V1
        )
        if (
            inputs.contract.stage_protocol_id
            != ATLAS_ASSESSMENT_STAGE_PROTOCOL_ID_V1
        ):
            raise ValueError("assessment stage protocol identity drifted")
        _assessment_prerequisites_v1(
            inputs.contract, inputs.ordered_parent_terminal_seals
        )
        parent_terminal_seals = tuple(inputs.ordered_parent_terminal_seals)
        _require_five_completed_parents_v1(parent_terminal_seals)
        if inputs.detached_manifest is None:
            raise ValueError("completed Plan-0013 manifest is unavailable")
        parent_values = _assessment_parent_inputs_v1(
            store,
            inputs.protocol,
            parent_terminal_seals,
        )
        return _build_atlas_assessment_report_v1(
            inputs.detached_manifest,
            inputs.protocol,
            *parent_values,
        )


__all__ = (
    "PLAN0013_ASSESSMENT_COMPLETED_PARENT_COUNT_V1",
    "PLAN0013_ATLAS_EVIDENCE_ROOT_RELATIVE_V1",
    "reconstruct_plan0013_atlas_assessment_report_v1",
)
