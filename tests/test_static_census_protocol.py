import copy
import contextlib
import hashlib
import inspect
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from parity_forge_universe import static_census_protocol as protocol


def _git(repository, *arguments):
    process = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )
    if process.returncode:
        raise AssertionError(process.stderr.decode("utf-8", "replace"))
    return process.stdout


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


class _ClosureRepository:
    def __init__(self, *, stage_suffix=""):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name).resolve()
        _git(self.path, "init", "-q")
        _git(self.path, "config", "user.email", "protocol-test@example.invalid")
        _git(self.path, "config", "user.name", "Protocol Test")

        package = self.path / "src" / "parity_forge_universe"
        _write(package / "__init__.py", "\"\"\"fixture package\"\"\"\n")
        _write(package / "typed_occupancy.py", "VALUE = 1\n")
        _write(
            package / "schema_v4_compiler.py",
            "from . import typed_occupancy\nVALUE = typed_occupancy.VALUE\n",
        )
        _write(
            package / "initial_structure.py",
            "from . import schema_v4_compiler\nfrom . import typed_occupancy\n",
        )
        _write(
            package / "static_census.py",
            "from . import initial_structure\n"
            "from . import schema_v4_compiler\n"
            "from . import typed_occupancy\n",
        )
        self.plan = (
            self.path
            / "docs"
            / "plans"
            / "active"
            / "0015-exhaustive-typed-occupancy-v4-universe.md"
        )
        _write(self.plan, "calculation plan\n")
        _git(self.path, "add", ".")
        _git(self.path, "commit", "-qm", "calculation")
        self.calculation_commit = self._head()
        self.calculation_tree = self._tree()

        _write(self.plan, "preregistered plan\n")
        _git(self.path, "add", str(self.plan.relative_to(self.path)))
        _git(self.path, "commit", "-qm", "preregister")
        self.preregistration_commit = self._head()
        self.preregistration_tree = self._tree()
        self.plan_raw = self.plan.read_bytes()
        self.plan_blob = self._blob(protocol.PLAN0015_ACTIVE_PLAN_PATH_V1)

        _write(self.path / ".gitignore", "*.pyc\n")
        _write(package / "static_census_protocol.py", "VALUE = 1\n")
        _write(
            package / "static_census_evidence.py",
            "from . import static_census_protocol\n",
        )
        _write(package / "static_census_reconstruction.py", "VALUE = 1\n")
        _write(
            package / "static_census_stage.py",
            "from . import static_census\n"
            "from . import static_census_evidence\n"
            "from . import static_census_protocol\n"
            "from . import static_census_reconstruction\n"
            + stage_suffix,
        )
        for name in (
            "evidence",
            "protocol",
            "reconstruction",
            "stage",
        ):
            _write(self.path / "tests" / ("test_static_census_" + name + ".py"), "\n")
        _git(self.path, "add", ".")
        _git(self.path, "commit", "-qm", "implementation")
        self.source_commit = self._head()
        self.source_tree = self._tree()

        records = []
        for path in (
            "src/parity_forge_universe/__init__.py",
            "src/parity_forge_universe/initial_structure.py",
            "src/parity_forge_universe/schema_v4_compiler.py",
            "src/parity_forge_universe/static_census.py",
            "src/parity_forge_universe/typed_occupancy.py",
        ):
            raw = (self.path / path).read_bytes()
            records.append(
                (path, self._blob(path), hashlib.sha256(raw).hexdigest(), len(raw))
            )
        self.calculation_records = tuple(records)

    def _head(self):
        return _git(self.path, "rev-parse", "HEAD^{commit}").decode("ascii").strip()

    def _tree(self):
        return _git(self.path, "rev-parse", "HEAD^{tree}").decode("ascii").strip()

    def _blob(self, path):
        return _git(self.path, "rev-parse", "HEAD:" + path).decode("ascii").strip()

    def patches(self):
        return (
            mock.patch.object(
                protocol,
                "PLAN0015_STATIC_CENSUS_CALCULATION_COMMIT_V1",
                self.calculation_commit,
            ),
            mock.patch.object(
                protocol,
                "PLAN0015_STATIC_CENSUS_CALCULATION_TREE_V1",
                self.calculation_tree,
            ),
            mock.patch.object(
                protocol,
                "PLAN0015_STATIC_CENSUS_PREREGISTRATION_COMMIT_V1",
                self.preregistration_commit,
            ),
            mock.patch.object(
                protocol,
                "PLAN0015_STATIC_CENSUS_PREREGISTRATION_TREE_V1",
                self.preregistration_tree,
            ),
            mock.patch.object(
                protocol,
                "PLAN0015_STATIC_CENSUS_PREREGISTERED_PLAN_BLOB_V1",
                self.plan_blob,
            ),
            mock.patch.object(
                protocol,
                "PLAN0015_STATIC_CENSUS_PREREGISTERED_PLAN_SHA256_V1",
                hashlib.sha256(self.plan_raw).hexdigest(),
            ),
            mock.patch.object(
                protocol,
                "PLAN0015_STATIC_CENSUS_PREREGISTERED_PLAN_BYTE_COUNT_V1",
                len(self.plan_raw),
            ),
            mock.patch.object(
                protocol,
                "FROZEN_CALCULATION_FILE_RECORDS_V1",
                self.calculation_records,
            ),
            # Synthetic repositories exercise the explicitly private core seam;
            # production callers retain the guarded, source-fixed wrappers.
            mock.patch.object(
                protocol,
                "build_static_census_production_closure_v1",
                protocol._build_static_census_production_closure_core_v1,
            ),
            mock.patch.object(
                protocol,
                "validate_static_census_production_closure_v1",
                protocol._validate_static_census_production_closure_core_v1,
            ),
            mock.patch.object(
                protocol,
                "reseal_static_census_production_closure_v1",
                protocol._reseal_static_census_production_closure_core_v1,
            ),
            mock.patch.object(
                protocol,
                "authenticate_static_census_recovery_closure_v1",
                protocol._authenticate_static_census_recovery_closure_core_v1,
            ),
        )

    def __enter__(self):
        self.stack = contextlib.ExitStack()
        for patcher in self.patches():
            self.stack.enter_context(patcher)
        return self

    def __exit__(self, kind, value, traceback):
        self.stack.close()
        self.temporary.cleanup()


class StaticCensusProtocolGoldenTests(unittest.TestCase):
    def test_protocol_root_sha_size_and_detachment_are_fixed(self):
        value = protocol.build_static_census_protocol_v1()
        raw = protocol.canonical_json_bytes_v1(value)
        self.assertEqual(
            value["identity"], protocol.PLAN0015_STATIC_CENSUS_PROTOCOL_ROOT_V1
        )
        self.assertEqual(
            hashlib.sha256(raw).hexdigest(),
            protocol.PLAN0015_STATIC_CENSUS_PROTOCOL_CANONICAL_SHA256_V1,
        )
        self.assertEqual(
            len(raw), protocol.PLAN0015_STATIC_CENSUS_PROTOCOL_CANONICAL_BYTE_COUNT_V1
        )
        self.assertEqual(
            protocol.validate_static_census_protocol_v1(value), value
        )
        value["payload"]["stage_contract"]["recover_builder_call_count"] = 1
        self.assertEqual(
            protocol.build_static_census_protocol_v1()["payload"]["stage_contract"][
                "recover_builder_call_count"
            ],
            0,
        )

    def test_protocol_rejects_aliases_unknown_fields_and_nested_mutation(self):
        source = protocol.build_static_census_protocol_v1()
        mutations = []
        wrong_version = copy.deepcopy(source)
        wrong_version["payload"]["protocol_version"] = True
        mutations.append(wrong_version)
        extra = copy.deepcopy(source)
        extra["extra"] = None
        mutations.append(extra)
        wrong_root = copy.deepcopy(source)
        wrong_root["identity"] = "0" * 64
        mutations.append(wrong_root)
        changed_count = copy.deepcopy(source)
        changed_count["payload"]["population_contract"][
            "factorized_carrier_count"
        ] += 1
        mutations.append(changed_count)
        for value in mutations:
            with self.subTest(value=value):
                with self.assertRaises(protocol.StaticCensusProtocolError):
                    protocol.validate_static_census_protocol_v1(value)

    def test_identity_domains_and_payload_schemas_are_closed(self):
        value = protocol.build_static_census_protocol_v1()
        schemas = value["payload"]["identity_schemas"]
        self.assertEqual(set(schemas), set(protocol._IDENTITY_DOMAINS_V1))
        self.assertEqual(len({row["domain_hex"] for row in schemas.values()}), 10)
        for kind, row in schemas.items():
            self.assertEqual(row["domain_hex"], protocol.identity_domain_v1(kind).hex())
            self.assertEqual(
                row["payload_keys"], list(protocol.identity_payload_keys_v1(kind))
            )
        for value in (None, True, 1, "unknown"):
            with self.subTest(value=value):
                with self.assertRaises((TypeError, ValueError)):
                    protocol.identity_domain_v1(value)

    def test_protocol_fixes_one_shot_checkpoint_and_report_boundaries(self):
        payload = protocol.build_static_census_protocol_v1()["payload"]
        self.assertEqual(payload["stage_contract"]["builder_call"], "build_static_census_v1()")
        self.assertEqual(payload["stage_contract"]["builder_call_count_after_attempt"], 1)
        self.assertEqual(payload["stage_contract"]["recover_builder_call_count"], 0)
        self.assertIs(payload["lifecycle_contract"]["mutable_checkpoint_is_evidence"], False)
        self.assertEqual(payload["report_contract"]["max_bytes"], 268_435_456)
        self.assertEqual(payload["report_contract"]["max_json_nodes"], 5_000_000)
        self.assertEqual(payload["report_contract"]["max_json_depth"], 32)
        self.assertEqual(
            payload["report_contract"]["synthetic_lower_shape_fixture_bytes"],
            9_462_884,
        )
        self.assertEqual(
            payload["production_closure_contract"]["ordered_exact_recursive_paths"],
            list(protocol.PRODUCTION_CLOSURE_PATHS_V1),
        )

    def test_public_apis_have_no_callback_or_path_injection(self):
        expected = {
            protocol.build_static_census_protocol_v1: (),
            protocol.validate_static_census_protocol_v1: ("value",),
            protocol.resolve_static_census_repository_v1: ("repository",),
            protocol.build_static_census_production_closure_v1: ("repository",),
            protocol.validate_static_census_production_closure_v1: (
                "repository",
                "value",
            ),
            protocol.reseal_static_census_production_closure_v1: (
                "repository",
                "value",
            ),
            protocol.authenticate_static_census_recovery_closure_v1: (
                "repository",
            ),
        }
        for function, names in expected.items():
            with self.subTest(function=function.__name__):
                parameters = inspect.signature(function).parameters
                self.assertEqual(tuple(parameters), names)
                self.assertTrue(
                    all(parameter.default is inspect.Parameter.empty for parameter in parameters.values())
                )

    def test_public_apis_fail_closed_on_internal_runtime_rebinding(self):
        calls = (
            lambda: protocol.resolve_static_census_repository_v1("."),
            protocol.build_static_census_protocol_v1,
            lambda: protocol.validate_static_census_protocol_v1({}),
            lambda: protocol.build_static_census_production_closure_v1("."),
            lambda: protocol.validate_static_census_production_closure_v1(
                ".", {}
            ),
            lambda: protocol.reseal_static_census_production_closure_v1(".", {}),
            lambda: protocol.authenticate_static_census_recovery_closure_v1(
                "."
            ),
        )
        with mock.patch.object(protocol, "_run_git", object()):
            for call in calls:
                with self.subTest(call=call), self.assertRaisesRegex(
                    protocol.StaticCensusProtocolError,
                    "protocol runtime binding changed",
                ):
                    call()

    def test_public_apis_fail_closed_on_in_place_protocol_value_mutation(self):
        original = protocol._IDENTITY_DOMAINS_V1["protocol_root"]
        try:
            protocol._IDENTITY_DOMAINS_V1["protocol_root"] = b"mutated"
            with self.assertRaisesRegex(
                protocol.StaticCensusProtocolError,
                "protocol runtime value changed",
            ):
                protocol.build_static_census_protocol_v1()
        finally:
            protocol._IDENTITY_DOMAINS_V1["protocol_root"] = original


class StaticCensusFrozenSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repository = Path(__file__).resolve().parents[1]

    def test_calculation_checkpoint_and_all_five_blob_records_are_exact(self):
        self.assertEqual(
            _git(self.repository, "rev-parse", protocol.PLAN0015_STATIC_CENSUS_CALCULATION_COMMIT_V1 + "^{tree}")
            .decode("ascii")
            .strip(),
            protocol.PLAN0015_STATIC_CENSUS_CALCULATION_TREE_V1,
        )
        for path, blob, sha256, byte_count in protocol.FROZEN_CALCULATION_FILE_RECORDS_V1:
            with self.subTest(path=path):
                observed_blob = (
                    _git(
                        self.repository,
                        "rev-parse",
                        protocol.PLAN0015_STATIC_CENSUS_CALCULATION_COMMIT_V1 + ":" + path,
                    )
                    .decode("ascii")
                    .strip()
                )
                raw = _git(self.repository, "cat-file", "blob", blob)
                self.assertEqual(observed_blob, blob)
                self.assertEqual(len(raw), byte_count)
                self.assertEqual(hashlib.sha256(raw).hexdigest(), sha256)

    def test_preregistration_commit_tree_and_active_plan_are_exact(self):
        self.assertEqual(
            _git(
                self.repository,
                "rev-parse",
                protocol.PLAN0015_STATIC_CENSUS_PREREGISTRATION_COMMIT_V1 + "^{tree}",
            )
            .decode("ascii")
            .strip(),
            protocol.PLAN0015_STATIC_CENSUS_PREREGISTRATION_TREE_V1,
        )
        blob = (
            _git(
                self.repository,
                "rev-parse",
                protocol.PLAN0015_STATIC_CENSUS_PREREGISTRATION_COMMIT_V1
                + ":"
                + protocol.PLAN0015_ACTIVE_PLAN_PATH_V1,
            )
            .decode("ascii")
            .strip()
        )
        raw = _git(self.repository, "cat-file", "blob", blob)
        self.assertEqual(blob, protocol.PLAN0015_STATIC_CENSUS_PREREGISTERED_PLAN_BLOB_V1)
        self.assertEqual(len(raw), protocol.PLAN0015_STATIC_CENSUS_PREREGISTERED_PLAN_BYTE_COUNT_V1)
        self.assertEqual(
            hashlib.sha256(raw).hexdigest(),
            protocol.PLAN0015_STATIC_CENSUS_PREREGISTERED_PLAN_SHA256_V1,
        )


class StaticCensusProductionClosureTests(unittest.TestCase):
    def test_clean_exact_changed_surface_builds_validates_and_reseals(self):
        with _ClosureRepository() as fixture:
            closure = protocol.build_static_census_production_closure_v1(
                str(fixture.path)
            )
            self.assertEqual(
                [row["path"] for row in closure["payload"]["ordered_file_records"]],
                list(protocol.PRODUCTION_CLOSURE_PATHS_V1),
            )
            self.assertEqual(
                closure["payload"]["source_commit"], fixture.source_commit
            )
            self.assertEqual(
                protocol.validate_static_census_production_closure_v1(
                    str(fixture.path), closure
                ),
                closure,
            )
            protocol.reseal_static_census_production_closure_v1(
                str(fixture.path), closure
            )

            allowed = (
                fixture.path
                / protocol.PLAN0015_STATIC_CENSUS_EVIDENCE_ROOT_RELATIVE_V1
                / "stages"
                / "report.json"
            )
            _write(allowed, "evidence\n")
            protocol.reseal_static_census_production_closure_v1(
                str(fixture.path), closure
            )

    def test_recovery_authentication_allows_only_the_fixed_evidence_root(self):
        with _ClosureRepository() as fixture:
            expected = protocol.build_static_census_production_closure_v1(
                str(fixture.path)
            )
            evidence_file = (
                fixture.path
                / protocol.PLAN0015_STATIC_CENSUS_EVIDENCE_ROOT_RELATIVE_V1
                / "bootstrap.json"
            )
            _write(evidence_file, "existing evidence\n")

            with self.assertRaisesRegex(
                protocol.StaticCensusProtocolError, "not clean"
            ):
                protocol.build_static_census_production_closure_v1(
                    str(fixture.path)
                )
            self.assertEqual(
                protocol.authenticate_static_census_recovery_closure_v1(
                    str(fixture.path)
                ),
                expected,
            )

            _write(fixture.path / "ignored.pyc", "unreviewed\n")
            with self.assertRaisesRegex(
                protocol.StaticCensusProtocolError, "not clean"
            ):
                protocol.authenticate_static_census_recovery_closure_v1(
                    str(fixture.path)
                )

    def test_build_rejects_dirty_source_and_non_top_repository(self):
        with _ClosureRepository() as fixture:
            outside = fixture.path / "outside.txt"
            _write(outside, "dirty\n")
            with self.assertRaisesRegex(
                protocol.StaticCensusProtocolError, "not clean"
            ):
                protocol.build_static_census_production_closure_v1(
                    str(fixture.path)
                )
            outside.unlink()
            with self.assertRaises(protocol.StaticCensusProtocolError):
                protocol.build_static_census_production_closure_v1(
                    str(fixture.path / "src")
                )

    def test_git_runner_removes_every_ambient_git_capability(self):
        poisoned = {
            "GIT_ALTERNATE_OBJECT_DIRECTORIES": "/tmp/alternate-objects",
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_GLOBAL": "/tmp/host-global-config",
            "GIT_CONFIG_KEY_0": "core.fsmonitor",
            "GIT_CONFIG_VALUE_0": "/tmp/host-fsmonitor",
            "GIT_DIR": "/tmp/wrong-git-dir",
            "GIT_INDEX_FILE": "/tmp/wrong-index",
            "GIT_OBJECT_DIRECTORY": "/tmp/wrong-objects",
            "GIT_REPLACE_REF_BASE": "refs/host-replacements/",
            "GIT_SHALLOW_FILE": "/tmp/wrong-shallow-file",
            "GIT_WORK_TREE": "/tmp/wrong-work-tree",
            "git_lowercase_probe": "must also disappear",
        }
        expected = {
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
            "PATH": protocol._FIXED_GIT_PATH_V1,
        }
        with _ClosureRepository() as fixture, mock.patch.dict(
            os.environ, poisoned, clear=False
        ):
            environment = protocol._git_environment()
            self.assertEqual(environment, expected)
            closure = protocol.build_static_census_production_closure_v1(
                str(fixture.path)
            )
            self.assertEqual(
                closure["payload"]["source_commit"], fixture.source_commit
            )

    def test_fixed_absolute_git_ignores_fake_path_and_resolver_returns_path(self):
        fixture = _ClosureRepository()
        try:
            temporary_context = tempfile.TemporaryDirectory()
            temporary = temporary_context.name
            fake_git = Path(temporary) / "git"
            _write(fake_git, "#!/bin/sh\nexit 97\n")
            fake_git.chmod(0o755)
            with mock.patch.dict(os.environ, {"PATH": temporary}, clear=False):
                resolved = protocol.resolve_static_census_repository_v1(
                    str(fixture.path)
                )
            self.assertIs(type(resolved), type(fixture.path))
            self.assertTrue(resolved.is_absolute())
            self.assertEqual(resolved, fixture.path)
        finally:
            if "temporary_context" in locals():
                temporary_context.cleanup()
            fixture.temporary.cleanup()

    def test_repository_resolver_allows_an_absent_optional_index(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory).resolve()
            _git(repository, "init", "-q")
            self.assertFalse((repository / ".git" / "index").exists())
            self.assertEqual(
                protocol.resolve_static_census_repository_v1(str(repository)),
                repository,
            )

    def test_repository_capabilities_are_audited_before_first_git_probe(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory).resolve()
            events = []

            def audit(observed):
                self.assertEqual(observed, repository)
                events.append("audit")

            def run_git(observed, arguments):
                self.assertEqual(observed, repository)
                self.assertEqual(arguments, ("rev-parse", "--show-toplevel"))
                events.append("git")
                return subprocess.CompletedProcess(
                    (), 0, stdout=(str(repository) + "\n").encode("utf-8"), stderr=b""
                )

            with mock.patch.object(
                protocol, "_require_closed_git_repository_v1", audit
            ):
                self.assertEqual(
                    protocol._repository_path(
                        str(repository), _run_git_v1=run_git
                    ),
                    repository,
                )
            self.assertEqual(events, ["audit", "git", "audit"])

    def test_fixed_git_executable_identity_drift_fails_closed(self):
        with _ClosureRepository() as fixture:
            drifted = list(protocol._GIT_EXECUTABLE_STATE_V1)
            drifted[-1] += 1
            with self.assertRaisesRegex(
                protocol.StaticCensusProtocolError,
                "Git executable identity changed",
            ):
                protocol._run_git(
                    fixture.path,
                    ("rev-parse", "--show-toplevel"),
                    _executable_state=tuple(drifted),
                )

    def test_git_runner_bounds_output_and_wall_time(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            noisy = root / "noisy-git"
            _write(noisy, "#!/bin/sh\nprintf '0123456789abcdefX'\n")
            noisy.chmod(0o700)
            with self.assertRaisesRegex(
                protocol.StaticCensusProtocolError, "byte cap"
            ):
                protocol._run_git(
                    root,
                    ("version",),
                    _executable=str(noisy),
                    _executable_state=(1,),
                    _read_executable_state=lambda _path: (1,),
                    _max_output_bytes=16,
                )

            hanging = root / "hanging-git"
            _write(hanging, "#!/bin/sh\nwhile :; do :; done\n")
            hanging.chmod(0o700)
            with self.assertRaisesRegex(
                protocol.StaticCensusProtocolError, "timed out"
            ):
                protocol._run_git(
                    root,
                    ("version",),
                    _executable=str(hanging),
                    _executable_state=(2,),
                    _read_executable_state=lambda _path: (2,),
                    _timeout_seconds=0.05,
                )

    def test_object_store_and_repository_attribute_capabilities_are_rejected(self):
        def write_shallow(fixture):
            _write(fixture.path / ".git" / "shallow", fixture.source_commit + "\n")

        def write_alternates(fixture):
            _write(
                fixture.path / ".git" / "objects" / "info" / "alternates",
                "/tmp/alternate-objects\n",
            )

        def write_http_alternates(fixture):
            _write(
                fixture.path / ".git" / "objects" / "info" / "http-alternates",
                "https://example.invalid/objects\n",
            )

        def write_promisor(fixture):
            _write(
                fixture.path / ".git" / "objects" / "pack" / "attack.promisor",
                "",
            )

        def write_casefold_promisor(fixture):
            _write(
                fixture.path / ".git" / "objects" / "pack" / "attack.PROMISOR",
                "",
            )

        def configure_partial_clone(fixture):
            _git(
                fixture.path,
                "config",
                "remote.origin.partialclonefilter",
                "blob:none",
            )

        def configure_promisor(fixture):
            _git(fixture.path, "config", "remote.origin.promisor", "true")

        def configure_external_excludes(fixture):
            _git(
                fixture.path,
                "config",
                "core.excludesFile",
                "/tmp/protocol-test-excludes",
            )

        def write_info_attributes(fixture):
            _write(
                fixture.path / ".git" / "info" / "attributes",
                "* filter=attack\n",
            )

        def replace_head_with_fifo(fixture):
            head = fixture.path / ".git" / "HEAD"
            head.unlink()
            os.mkfifo(head)

        def replace_index_with_symlink(fixture):
            index = fixture.path / ".git" / "index"
            index.unlink()
            index.symlink_to("/dev/null")

        def write_loose_object_fifo(fixture):
            target = fixture.path / ".git" / "objects" / "aa" / ("b" * 38)
            target.parent.mkdir(exist_ok=True)
            os.mkfifo(target)

        def write_ref_symlink(fixture):
            target = fixture.path / ".git" / "refs" / "heads" / "attack"
            target.symlink_to("main")

        cases = (
            ("shallow", write_shallow, "shallow repository marker"),
            ("alternates", write_alternates, "alternate object store"),
            (
                "http-alternates",
                write_http_alternates,
                "HTTP alternate object store",
            ),
            ("promisor-pack", write_promisor, "promisor object packs"),
            (
                "casefold-promisor-pack",
                write_casefold_promisor,
                "promisor object packs",
            ),
            (
                "partial-clone-config",
                configure_partial_clone,
                "forbidden capability",
            ),
            (
                "promisor-config",
                configure_promisor,
                "forbidden capability",
            ),
            (
                "external-excludes-config",
                configure_external_excludes,
                "forbidden capability",
            ),
            (
                "info-attributes",
                write_info_attributes,
                "repository-local attribute file",
            ),
            ("head-fifo", replace_head_with_fifo, "Git HEAD"),
            ("index-symlink", replace_index_with_symlink, "Git index"),
            (
                "loose-object-fifo",
                write_loose_object_fifo,
                "Git object store",
            ),
            ("ref-symlink", write_ref_symlink, "Git refs"),
        )
        for label, install, message in cases:
            with self.subTest(label=label), _ClosureRepository() as fixture:
                install(fixture)
                with self.assertRaisesRegex(
                    protocol.StaticCensusProtocolError, message
                ):
                    protocol._require_closed_git_repository_v1(fixture.path)

    def test_clean_filter_configuration_is_rejected_without_execution(self):
        with _ClosureRepository() as fixture:
            sentinel = fixture.path / "filter-was-executed"
            _git(
                fixture.path,
                "config",
                "filter.attack.clean",
                "touch {}".format(sentinel),
            )
            _write(
                fixture.path
                / "src"
                / "parity_forge_universe"
                / ".gitattributes",
                "*.py filter=attack\n",
            )
            with self.assertRaisesRegex(
                protocol.StaticCensusProtocolError, "forbidden capability"
            ):
                protocol.build_static_census_production_closure_v1(
                    str(fixture.path)
                )
            self.assertFalse(sentinel.exists())

    def test_nested_current_gitattributes_is_rejected_by_descriptor_scan(self):
        with _ClosureRepository() as fixture:
            _write(
                fixture.path / "experiments" / "nested" / ".gitattributes",
                "* -text\n",
            )
            with self.assertRaisesRegex(
                protocol.StaticCensusProtocolError,
                "current source attribute file is forbidden",
            ):
                protocol._require_absent_current_source_attributes_v1(
                    fixture.path
                )

    def test_current_gitattributes_scan_is_case_insensitive(self):
        for name in (".GITATTRIBUTES", ".GitAttributes"):
            with self.subTest(name=name), _ClosureRepository() as fixture:
                _write(
                    fixture.path / "experiments" / "nested" / name,
                    "* -text\n",
                )
                with self.assertRaisesRegex(
                    protocol.StaticCensusProtocolError,
                    "current source attribute file is forbidden",
                ):
                    protocol._require_absent_current_source_attributes_v1(
                        fixture.path
                    )

    def test_ignored_untracked_paths_cannot_evade_clean_head(self):
        def install_root_ignore(fixture):
            _write(fixture.path / "src" / "hidden.pyc", "attack\n")

        def install_info_exclude(fixture):
            _write(fixture.path / ".git" / "info" / "exclude", "hidden-secret\n")
            _write(fixture.path / "hidden-secret", "attack\n")

        def install_nested_ignore(fixture):
            _write(fixture.path / "scratch" / ".gitignore", "*\n")
            _write(fixture.path / "scratch" / "hidden-secret", "attack\n")

        for label, install in (
            ("tracked-root-gitignore", install_root_ignore),
            ("git-info-exclude", install_info_exclude),
            ("untracked-nested-gitignore", install_nested_ignore),
        ):
            with self.subTest(label=label), _ClosureRepository() as fixture:
                install(fixture)
                with self.assertRaisesRegex(
                    protocol.StaticCensusProtocolError,
                    "production source repository is not clean",
                ):
                    protocol.build_static_census_production_closure_v1(
                        str(fixture.path)
                    )

    def test_untracked_special_file_cannot_evade_clean_head(self):
        if not hasattr(os, "mkfifo"):
            self.skipTest("FIFO creation is unavailable")
        with _ClosureRepository() as fixture:
            os.mkfifo(fixture.path / "ignored-special.pyc")
            with self.assertRaisesRegex(
                protocol.StaticCensusProtocolError,
                "production worktree contains a special file",
            ):
                protocol.build_static_census_production_closure_v1(
                    str(fixture.path)
                )

    def test_replace_ref_cannot_forge_actual_ancestry(self):
        with _ClosureRepository() as fixture:
            unrelated = (
                _git(
                    fixture.path,
                    "commit-tree",
                    fixture.source_tree,
                    "-p",
                    fixture.calculation_commit,
                    "-m",
                    "unrelated implementation",
                )
                .decode("ascii")
                .strip()
            )
            _git(
                fixture.path,
                "replace",
                "--graft",
                unrelated,
                fixture.preregistration_commit,
            )
            # The ordinary revision view is forged into an acceptable ancestry.
            _git(
                fixture.path,
                "merge-base",
                "--is-ancestor",
                fixture.preregistration_commit,
                unrelated,
            )
            _git(fixture.path, "checkout", "--detach", "-q", unrelated)
            with self.assertRaisesRegex(
                protocol.StaticCensusProtocolError,
                "does not descend from preregistration",
            ):
                protocol.build_static_census_production_closure_v1(
                    str(fixture.path)
                )

    def test_graft_cannot_hide_an_actual_merge_parent(self):
        with _ClosureRepository() as fixture:
            merge = (
                _git(
                    fixture.path,
                    "commit-tree",
                    fixture.source_tree,
                    "-p",
                    fixture.preregistration_commit,
                    "-p",
                    fixture.calculation_commit,
                    "-m",
                    "hidden merge",
                )
                .decode("ascii")
                .strip()
            )
            grafts = fixture.path / ".git" / "info" / "grafts"
            _write(grafts, "{} {}\n".format(merge, fixture.preregistration_commit))
            self.assertEqual(
                _git(
                    fixture.path,
                    "rev-list",
                    "--merges",
                    fixture.preregistration_commit + ".." + merge,
                ),
                b"",
            )
            _git(fixture.path, "checkout", "--detach", "-q", merge)
            with self.assertRaisesRegex(
                protocol.StaticCensusProtocolError, "contains a merge"
            ):
                protocol.build_static_census_production_closure_v1(
                    str(fixture.path)
                )

    def test_actual_ancestry_walk_has_a_hard_bound(self):
        parents = mock.Mock(
            side_effect=[
                ("2" * 40,),
                ("3" * 40,),
                ("4" * 40,),
            ]
        )
        with mock.patch.object(
            protocol, "_MAX_SOURCE_ANCESTRY_COMMITS_V1", 3
        ), mock.patch.object(protocol, "_actual_commit_parents", parents):
            with self.assertRaisesRegex(
                protocol.StaticCensusProtocolError, "traversal bound"
            ):
                protocol._require_actual_linear_ancestry(
                    Path("/unused"), "1" * 40, "f" * 40
                )
        self.assertEqual(parents.call_count, 3)

    def test_reseal_rejects_untracked_outside_root_and_tracked_byte_drift(self):
        with _ClosureRepository() as fixture:
            closure = protocol.build_static_census_production_closure_v1(
                str(fixture.path)
            )
            outside = fixture.path / "outside.txt"
            _write(outside, "dirty\n")
            with self.assertRaisesRegex(
                protocol.StaticCensusProtocolError, "outside the fixed evidence root"
            ):
                protocol.reseal_static_census_production_closure_v1(
                    str(fixture.path), closure
                )
            outside.unlink()
            target = (
                fixture.path
                / "src"
                / "parity_forge_universe"
                / "static_census.py"
            )
            target.write_text(
                target.read_text(encoding="utf-8") + "# drift\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                protocol.StaticCensusProtocolError, "tracked worktree changed"
            ):
                protocol.reseal_static_census_production_closure_v1(
                    str(fixture.path), closure
                )

    def test_reseal_rereads_head_and_tree_after_the_final_worktree_check(self):
        with _ClosureRepository() as fixture:
            closure = protocol.build_static_census_production_closure_v1(
                str(fixture.path)
            )
            _write(fixture.path / "later.txt", "later\n")
            _git(fixture.path, "add", "later.txt")
            _git(fixture.path, "commit", "-qm", "later")
            later_commit = fixture._head()
            _git(
                fixture.path,
                "checkout",
                "--detach",
                "-q",
                fixture.source_commit,
            )
            original = protocol._require_reseal_worktree
            calls = []

            def check_then_switch(repository):
                original(repository)
                calls.append(None)
                if len(calls) == 2:
                    _git(repository, "checkout", "--detach", "-q", later_commit)

            with mock.patch.object(
                protocol,
                "_require_reseal_worktree",
                side_effect=check_then_switch,
            ), self.assertRaisesRegex(
                protocol.StaticCensusProtocolError,
                "HEAD changed after closure reservation",
            ):
                protocol.reseal_static_census_production_closure_v1(
                    str(fixture.path), closure
                )
            self.assertEqual(len(calls), 2)

    def test_validator_rebuilds_from_stored_commit_and_rejects_forgery(self):
        with _ClosureRepository() as fixture:
            closure = protocol.build_static_census_production_closure_v1(
                str(fixture.path)
            )
            _write(fixture.path / "later.txt", "later\n")
            _git(fixture.path, "add", "later.txt")
            _git(fixture.path, "commit", "-qm", "later")
            later_commit = fixture._head()
            later_tree = fixture._tree()
            later_blob = _git(
                fixture.path, "rev-parse", "HEAD:later.txt"
            ).decode("ascii").strip()
            self.assertEqual(
                protocol.validate_static_census_production_closure_v1(
                    str(fixture.path), closure
                ),
                closure,
            )
            forged = copy.deepcopy(closure)
            forged["payload"]["ordered_file_records"][0]["sha256"] = "0" * 64
            with self.assertRaises(
                protocol.StaticCensusStoredClosureIntegrityError
            ):
                protocol.validate_static_census_production_closure_v1(
                    str(fixture.path), forged
                )

            resigned = copy.deepcopy(forged)
            resigned["identity"] = protocol._domain_identity(
                "production_closure_root", resigned["payload"]
            )
            with self.assertRaises(
                protocol.StaticCensusStoredClosureIntegrityError
            ):
                protocol.validate_static_census_production_closure_v1(
                    str(fixture.path), resigned
                )

            malformed = copy.deepcopy(closure)
            malformed["payload"]["source_commit"] = "not-a-commit"
            malformed["identity"] = protocol._domain_identity(
                "production_closure_root", malformed["payload"]
            )
            with self.assertRaises(
                protocol.StaticCensusStoredClosureIntegrityError
            ):
                protocol.validate_static_census_production_closure_v1(
                    str(fixture.path), malformed
                )

            mismatched_coordinate = copy.deepcopy(closure)
            mismatched_coordinate["payload"]["source_tree"] = later_tree
            mismatched_coordinate["identity"] = protocol._domain_identity(
                "production_closure_root", mismatched_coordinate["payload"]
            )
            with self.assertRaises(
                protocol.StaticCensusStoredClosureIntegrityError
            ):
                protocol.validate_static_census_production_closure_v1(
                    str(fixture.path), mismatched_coordinate
                )

            unauthorized_source = copy.deepcopy(closure)
            unauthorized_source["payload"]["source_commit"] = later_commit
            unauthorized_source["payload"]["source_tree"] = later_tree
            unauthorized_source["identity"] = protocol._domain_identity(
                "production_closure_root", unauthorized_source["payload"]
            )
            with self.assertRaisesRegex(
                protocol.StaticCensusStoredClosureIntegrityError,
                "unauthorized source",
            ) as unauthorized:
                protocol.validate_static_census_production_closure_v1(
                    str(fixture.path), unauthorized_source
                )
            self.assertIsInstance(
                unauthorized.exception.__cause__,
                protocol._StaticCensusSourceSemanticError,
            )
            self.assertIn(
                "changed-path set drifted",
                str(unauthorized.exception.__cause__),
            )

            noncommit_source = copy.deepcopy(closure)
            noncommit_source["payload"]["source_commit"] = later_blob
            noncommit_source["payload"]["source_tree"] = later_tree
            noncommit_source["identity"] = protocol._domain_identity(
                "production_closure_root", noncommit_source["payload"]
            )
            with self.assertRaisesRegex(
                protocol.StaticCensusStoredClosureIntegrityError,
                "not a commit",
            ):
                protocol.validate_static_census_production_closure_v1(
                    str(fixture.path), noncommit_source
                )

            object_path = (
                fixture.path
                / ".git"
                / "objects"
                / fixture.source_commit[:2]
                / fixture.source_commit[2:]
            )
            unavailable_path = object_path.with_name(object_path.name + ".missing")
            object_path.rename(unavailable_path)
            try:
                with self.assertRaises(
                    protocol.StaticCensusProtocolError
                ) as raised:
                    protocol.validate_static_census_production_closure_v1(
                        str(fixture.path), closure
                    )
                self.assertNotIsInstance(
                    raised.exception,
                    protocol.StaticCensusStoredClosureIntegrityError,
                )
            finally:
                unavailable_path.rename(object_path)

    def test_dynamic_import_and_legacy_package_import_fail_closed(self):
        for source in ("__import__('parity_forge_universe.typed_occupancy')\n", "import parity_forge.engine\n"):
            with self.subTest(source=source), _ClosureRepository(
                stage_suffix=source
            ) as fixture:
                with self.assertRaisesRegex(
                    protocol.StaticCensusProtocolError,
                    "dynamic import|legacy package",
                ):
                    protocol.build_static_census_production_closure_v1(
                        str(fixture.path)
                    )

    def test_symlinked_git_source_is_rejected(self):
        with _ClosureRepository() as fixture:
            source = (
                fixture.path
                / "src"
                / "parity_forge_universe"
                / "static_census_reconstruction.py"
            )
            source.unlink()
            source.symlink_to("typed_occupancy.py")
            _git(fixture.path, "add", "src/parity_forge_universe/static_census_reconstruction.py")
            _git(fixture.path, "commit", "-qm", "make source a symlink")
            # The extra source commit is still a merge-free descendant, but its
            # Git mode cannot masquerade as a regular production source blob.
            with self.assertRaisesRegex(
                protocol.StaticCensusProtocolError,
                "nonexecutable regular Git blob|changed-path set",
            ):
                protocol.build_static_census_production_closure_v1(
                    str(fixture.path)
                )

    def test_current_reader_rejects_symlink_fifo_hardlink_and_growth(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            regular = root / "regular.py"
            _write(regular, "x = 1\n")
            raw = regular.read_bytes()
            self.assertEqual(
                protocol._read_current_regular(root, "regular.py", len(raw)), raw
            )

            alias = root / "alias.py"
            alias.symlink_to(regular)
            with self.assertRaises(protocol.StaticCensusProtocolError):
                protocol._read_current_regular(root, "alias.py", len(raw))

            hardlink = root / "hardlink.py"
            os.link(regular, hardlink)
            with self.assertRaises(protocol.StaticCensusProtocolError):
                protocol._read_current_regular(root, "regular.py", len(raw))
            hardlink.unlink()

            if hasattr(os, "mkfifo"):
                fifo = root / "fifo.py"
                os.mkfifo(fifo)
                with self.assertRaises(protocol.StaticCensusProtocolError):
                    protocol._read_current_regular(root, "fifo.py", 0)

    def test_current_reader_rejects_ancestor_directory_swap_and_restore(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source_directory = root / "source"
            source = source_directory / "module.py"
            _write(source, "original\n")
            raw = source.read_bytes()
            moved = root / "held-source"
            replacement = root / "replacement-source"
            original_read = os.read
            swapped = False

            def read_after_directory_aba(fd, count):
                nonlocal swapped
                if not swapped:
                    swapped = True
                    source_directory.rename(moved)
                    _write(source, "forged!!\n")
                    source_directory.rename(replacement)
                    moved.rename(source_directory)
                return original_read(fd, count)

            with mock.patch.object(
                protocol.os, "read", side_effect=read_after_directory_aba
            ), self.assertRaisesRegex(
                protocol.StaticCensusProtocolError,
                "ancestor changed while reading",
            ):
                protocol._read_current_regular(
                    root, "source/module.py", len(raw)
                )
            self.assertTrue(swapped)


if __name__ == "__main__":
    unittest.main()
