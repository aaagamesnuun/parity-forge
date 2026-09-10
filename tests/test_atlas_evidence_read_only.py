from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import parity_forge.atlas_evidence as atlas_evidence
from parity_forge.atlas_evidence import (
    EvidenceError,
    EvidenceIntegrityError,
    ImmutableEvidenceStore,
    canonical_json_bytes,
)


_MANIFEST_STAGE_PROTOCOL_ID = "plan0013-atlas-development-manifest-v1"


def _filesystem_inventory(root: Path):
    """Capture mutation-relevant metadata and file bytes, excluding access time."""

    if not root.exists() and not root.is_symlink():
        return ()
    records = []
    for path in (root, *sorted(root.rglob("*"))):
        relative = "." if path == root else path.relative_to(root).as_posix()
        info = path.lstat()
        digest = None
        target = None
        if stat.S_ISREG(info.st_mode):
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        elif stat.S_ISLNK(info.st_mode):
            target = os.readlink(path)
        records.append(
            (
                relative,
                stat.S_IFMT(info.st_mode),
                stat.S_IMODE(info.st_mode),
                info.st_ino,
                info.st_nlink,
                info.st_size,
                info.st_mtime_ns,
                info.st_ctime_ns,
                digest,
                target,
            )
        )
    return tuple(records)


def _make_readable_store(parent: Path) -> Path:
    root = parent / "evidence"
    stage = root / "stages" / _MANIFEST_STAGE_PROTOCOL_ID
    bootstrap = root / "manifest-bootstrap"
    stage.mkdir(parents=True)
    bootstrap.mkdir()
    (stage / "reservation.json").write_bytes(canonical_json_bytes({"x": 1}))
    (bootstrap / "protocol.json").write_bytes(canonical_json_bytes({"p": 1}))
    return root


def _assert_fixed_artifact_fifo_fails_without_blocking(
    testcase: unittest.TestCase, root: Path
) -> None:
    source_root = Path(__file__).resolve().parents[1] / "src"
    environment = dict(os.environ)
    prior_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = str(source_root) + (
        "" if not prior_pythonpath else os.pathsep + prior_pythonpath
    )
    script = r"""
from pathlib import Path
import sys

from parity_forge.atlas_evidence import (
    EvidenceIntegrityError,
    ImmutableEvidenceStore,
)

root = Path(sys.argv[1])
stage_protocol_id = sys.argv[2]
try:
    with ImmutableEvidenceStore(root, create=False) as store:
        store.read_json(stage_protocol_id, "reservation")
except EvidenceIntegrityError:
    raise SystemExit(0)
except BaseException as error:
    print(type(error).__name__ + ": " + str(error), file=sys.stderr)
    raise SystemExit(4)
raise SystemExit(5)
"""
    result = subprocess.run(
        (sys.executable, "-c", script, str(root), _MANIFEST_STAGE_PROTOCOL_ID),
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
        timeout=2,
    )
    testcase.assertEqual(
        result.returncode,
        0,
        result.stderr.decode("utf-8", "replace"),
    )


class ImmutableEvidenceStoreReadOnlyTests(unittest.TestCase):
    def test_fixed_artifact_fifo_fails_closed_without_blocking(self):
        with tempfile.TemporaryDirectory() as directory:
            root = _make_readable_store(Path(directory))
            reservation = (
                root
                / "stages"
                / _MANIFEST_STAGE_PROTOCOL_ID
                / "reservation.json"
            )
            reservation.unlink()
            os.mkfifo(reservation, mode=0o400)

            _assert_fixed_artifact_fifo_fails_without_blocking(self, root)

    def test_authenticated_directory_fd_prevents_path_swap(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = _make_readable_store(parent)
            flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            directory_fd = os.open(root, flags)
            self.addCleanup(os.close, directory_fd)
            authenticated_inode = os.fstat(directory_fd).st_ino

            original = parent / "authenticated-evidence"
            root.rename(original)
            replacement = _make_readable_store(parent)
            replacement_stage = (
                replacement / "stages" / _MANIFEST_STAGE_PROTOCOL_ID
            )
            (replacement_stage / "reservation.json").write_bytes(
                canonical_json_bytes({"x": 2})
            )

            with mock.patch.object(
                os, "mkdir", side_effect=AssertionError("read-only mkdir")
            ), mock.patch.object(
                os, "fsync", side_effect=AssertionError("read-only fsync")
            ):
                with ImmutableEvidenceStore.from_read_only_directory_fd(
                    root, directory_fd
                ) as store:
                    self.assertEqual(
                        os.fstat(store._root_fd).st_ino,
                        authenticated_inode,
                    )
                    self.assertEqual(
                        store.read_json(
                            _MANIFEST_STAGE_PROTOCOL_ID, "reservation"
                        ),
                        {"x": 1},
                    )

            self.assertEqual(
                canonical_json_bytes({"x": 2}),
                (replacement_stage / "reservation.json").read_bytes(),
            )

    def test_reads_without_creating_optional_directories_or_mutating_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = _make_readable_store(Path(directory))
            before = _filesystem_inventory(root)

            with mock.patch.object(
                os, "mkdir", side_effect=AssertionError("read-only mkdir")
            ), mock.patch.object(
                os, "fsync", side_effect=AssertionError("read-only fsync")
            ), mock.patch.object(
                atlas_evidence,
                "_publish_exclusive_at",
                side_effect=AssertionError("read-only publish"),
            ) as publish:
                with ImmutableEvidenceStore(root, create=False) as store:
                    self.assertEqual(
                        store.read_json(
                            _MANIFEST_STAGE_PROTOCOL_ID, "reservation"
                        ),
                        {"x": 1},
                    )
                    self.assertEqual(
                        store.read_manifest_bootstrap_bytes("protocol"),
                        canonical_json_bytes({"p": 1}),
                    )
                    self.assertTrue(
                        store.artifact_exists(
                            _MANIFEST_STAGE_PROTOCOL_ID, "reservation"
                        )
                    )
                    self.assertFalse(
                        store.artifact_exists(
                            _MANIFEST_STAGE_PROTOCOL_ID, "attempt"
                        )
                    )
                    self.assertTrue(
                        store._stage_entry_exists(_MANIFEST_STAGE_PROTOCOL_ID)
                    )

                    with self.assertRaises(EvidenceIntegrityError) as missing:
                        store.read_contradiction(_MANIFEST_STAGE_PROTOCOL_ID)
                    self.assertIsInstance(
                        missing.exception.__cause__, FileNotFoundError
                    )
                    atlas_evidence._require_no_contradiction(
                        store, _MANIFEST_STAGE_PROTOCOL_ID
                    )

                    with self.assertRaises(EvidenceError):
                        with store.stage_lock(_MANIFEST_STAGE_PROTOCOL_ID):
                            pass
                    with self.assertRaises(EvidenceError):
                        store.publish_manifest_bootstrap_bytes("protocol", b"{}")
                    with self.assertRaises(EvidenceError):
                        store.publish_bytes(
                            _MANIFEST_STAGE_PROTOCOL_ID, "reservation", b"{}"
                        )
                    with self.assertRaises(EvidenceError):
                        store.publish_json(
                            _MANIFEST_STAGE_PROTOCOL_ID, "reservation", {}
                        )
                    with self.assertRaises(EvidenceError):
                        store.publish_contradiction(
                            _MANIFEST_STAGE_PROTOCOL_ID, {"x": 1}
                        )
                    with self.assertRaises(EvidenceError):
                        store.publish_journal_start(
                            _MANIFEST_STAGE_PROTOCOL_ID,
                            "exact",
                            0,
                            "slot-0",
                        )
                    with self.assertRaises(EvidenceError):
                        store.publish_journal_result(
                            _MANIFEST_STAGE_PROTOCOL_ID,
                            "exact",
                            0,
                            "slot-0",
                            "COMPLETE",
                            {},
                        )
                    with self.assertRaises(EvidenceError):
                        with store._stage_fd(
                            _MANIFEST_STAGE_PROTOCOL_ID, create=True
                        ):
                            pass
                    with self.assertRaises(EvidenceError):
                        with store._journal_leaf_fd(
                            _MANIFEST_STAGE_PROTOCOL_ID,
                            "exact",
                            "starts",
                            create=True,
                        ):
                            pass

                publish.assert_not_called()

            self.assertEqual(_filesystem_inventory(root), before)
            self.assertFalse((root / ".locks").exists())
            self.assertFalse((root / "contradictions").exists())

    def test_missing_required_directories_fail_without_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            missing_root = parent / "missing"
            before = _filesystem_inventory(parent)
            with self.assertRaises(EvidenceIntegrityError) as missing:
                ImmutableEvidenceStore(missing_root, create=False)
            self.assertIsInstance(missing.exception.__cause__, FileNotFoundError)
            self.assertEqual(_filesystem_inventory(parent), before)

            root = parent / "evidence"
            root.mkdir()
            before = _filesystem_inventory(root)
            with self.assertRaises(EvidenceIntegrityError) as missing:
                ImmutableEvidenceStore(root, create=False)
            self.assertIsInstance(missing.exception.__cause__, FileNotFoundError)
            self.assertEqual(_filesystem_inventory(root), before)

            (root / "stages").mkdir()
            before = _filesystem_inventory(root)
            with self.assertRaises(EvidenceIntegrityError) as missing:
                ImmutableEvidenceStore(root, create=False)
            self.assertIsInstance(missing.exception.__cause__, FileNotFoundError)
            self.assertEqual(_filesystem_inventory(root), before)

    def test_existing_directory_reads_reject_symlink_components(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            outside = parent / "outside"
            outside.mkdir()

            root = parent / "unsafe-top-level"
            root.mkdir()
            (root / "stages").symlink_to(outside, target_is_directory=True)
            (root / "manifest-bootstrap").mkdir()
            with self.assertRaises(EvidenceIntegrityError):
                ImmutableEvidenceStore(root, create=False)

            readable = _make_readable_store(parent / "nested")
            stage = readable / "stages" / _MANIFEST_STAGE_PROTOCOL_ID
            (stage / "reservation.json").unlink()
            stage.rmdir()
            stage.symlink_to(outside, target_is_directory=True)
            (readable / "contradictions").symlink_to(
                outside, target_is_directory=True
            )
            before = _filesystem_inventory(readable)
            with ImmutableEvidenceStore(readable, create=False) as store:
                with self.assertRaises(EvidenceIntegrityError):
                    store.read_json(
                        _MANIFEST_STAGE_PROTOCOL_ID, "reservation"
                    )
                with self.assertRaises(EvidenceIntegrityError):
                    store.read_contradiction(_MANIFEST_STAGE_PROTOCOL_ID)
            self.assertEqual(_filesystem_inventory(readable), before)

    def test_default_mode_still_creates_and_publishes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "evidence"
            with ImmutableEvidenceStore(root) as store:
                self.assertEqual(
                    {path.name for path in root.iterdir()},
                    {
                        ".locks",
                        "contradictions",
                        "manifest-bootstrap",
                        "stages",
                    },
                )
                with store.stage_lock(_MANIFEST_STAGE_PROTOCOL_ID):
                    store.publish_json(
                        _MANIFEST_STAGE_PROTOCOL_ID, "reservation", {"x": 1}
                    )
                self.assertEqual(
                    store.read_json(
                        _MANIFEST_STAGE_PROTOCOL_ID, "reservation"
                    ),
                    {"x": 1},
                )

    def test_create_flag_is_strict(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(TypeError):
                ImmutableEvidenceStore(Path(directory) / "evidence", create=1)
            for invalid in (True, -1, 1.0):
                with self.subTest(directory_fd=invalid):
                    with self.assertRaises(TypeError):
                        ImmutableEvidenceStore.from_read_only_directory_fd(
                            Path(directory) / "evidence", invalid
                        )

            file_path = Path(directory) / "not-a-directory"
            file_path.write_bytes(b"x")
            file_fd = os.open(file_path, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                with self.assertRaises(EvidenceIntegrityError):
                    ImmutableEvidenceStore.from_read_only_directory_fd(
                        file_path, file_fd
                    )
            finally:
                os.close(file_fd)


if __name__ == "__main__":
    unittest.main()
