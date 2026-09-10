"""Real import closure and source-only historical fixture exclusion witnesses."""

import ast
import builtins
import copy
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

from parity_forge_universe import schema_v4_compiler as compiler
from parity_forge_universe import typed_occupancy as universe


REPOSITORY = Path(__file__).resolve().parents[1]
_CUTOFF_COMMIT = "0d041629bb584f47e7f10f1358f89e6920fee299"
_BENCHMARK_SOURCE_PATH = "src/parity_forge/atlas_agent_benchmark.py"
_BENCHMARK_SOURCE_BLOB = "ef1e99a87be4b0cf2e9e4fe30557b111fa979a7d"
_EXTRA_FIXTURE_ID = "swap-simultaneous-connect-v1"
_EXTRA_FIXTURE_SHA256 = (
    "eaaf30187d95c215c2d330f1e68c92b10ff7718b85e16801de2a15353b8c3db2"
)
_RESEARCH_MODULES = frozenset(
    (
        "research/__init__.py",
        "research/parity_forge_history/__init__.py",
        "research/parity_forge_history/history_cutoff.py",
        "research/parity_forge_history/history_identity.py",
        "research/parity_forge_history/history_pins.py",
        "research/parity_forge_history/wire_identity.py",
    )
)
_STDLIB_IMPORTS = frozenset(
    ("__future__", "collections", "hashlib", "json", "math", "re", "typing")
)
_LOCAL_IMPORTS = frozenset(
    ("history_cutoff", "history_identity", "history_pins", "wire_identity")
)


def _canonical_json(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    )


def _literal_assignment(source, name):
    matches = [
        node.value
        for node in ast.parse(source).body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == name
                for target in node.targets)
    ]
    if len(matches) != 1:
        raise AssertionError("expected one literal assignment for " + name)
    return ast.literal_eval(matches[0])


def _independent_image(source, rotations, reflected, role_swapped, alpha_renamed):
    """Construct D4/R/alpha images without importing historical game code."""
    value = copy.deepcopy(source)

    def vector_image(vector):
        row, column = vector
        if reflected:
            column = -column
        for _ in range(rotations):
            row, column = column, -row
        return [row, column]

    def position_image(position):
        # A 3x3 board is centered at (1, 1), so the same linear map applies.
        row, column = vector_image([position[0] - 1, position[1] - 1])
        return [row + 1, column + 1]

    edge_vectors = {
        "TOP": [-1, 0], "RIGHT": [0, 1],
        "BOTTOM": [1, 0], "LEFT": [0, -1],
    }
    inverse_edges = {tuple(vector): edge for edge, vector in edge_vectors.items()}
    edge_map = {
        edge: inverse_edges[tuple(vector_image(vector))]
        for edge, vector in edge_vectors.items()
    }
    for role in value["roles"].values():
        action = role["action"]
        action["vectors"] = sorted(vector_image(vector) for vector in action["vectors"])
        goal = role["goal"]
        if goal["kind"] == "CONNECT_EDGES":
            goal["edges"] = sorted(edge_map[edge] for edge in goal["edges"])
        else:
            goal["edge"] = edge_map[goal["edge"]]
    for piece in value["initial_pieces"]:
        piece["position"] = position_image(piece["position"])
        if role_swapped:
            piece["owner"] = "B" if piece["owner"] == "A" else "A"
    if role_swapped:
        value["roles"] = {"A": value["roles"]["B"], "B": value["roles"]["A"]}
        value["first_player"] = "B" if value["first_player"] == "A" else "A"
    if alpha_renamed:
        for role in value["roles"].values():
            for field in ("action", "goal"):
                role[field]["piece"] = "renamed_" + role[field]["piece"]
        for piece in value["initial_pieces"]:
            piece["piece"] = "renamed_" + piece["piece"]
    value["initial_pieces"].sort(
        key=lambda piece: (piece["position"], piece["owner"], piece["piece"])
    )
    return value


class HistoryCapabilityBoundaryTests(unittest.TestCase):
    def test_each_public_import_rejects_any_legacy_package_dependency(self):
        # A new interpreter is necessary: discovery has already imported the
        # legacy engine for unrelated tests and would otherwise mask regressions.
        script = """
import builtins
import sys
original_import = builtins.__import__
def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name == 'parity_forge' or name.startswith('parity_forge.'):
        raise AssertionError('forbidden legacy import: ' + name)
    return original_import(name, globals, locals, fromlist, level)
builtins.__import__ = guarded_import
original_import(sys.argv[1], fromlist=['*'])
assert not any(name == 'parity_forge' or name.startswith('parity_forge.')
               for name in sys.modules)
"""
        for module in (
            "research.parity_forge_history.history_cutoff",
            "research.parity_forge_history.history_identity",
        ):
            with self.subTest(module=module):
                completed = subprocess.run(
                    [sys.executable, "-c", script, module],
                    cwd=REPOSITORY, capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_production_research_closure_has_only_declared_pure_dependencies(self):
        observed = {
            str(path.relative_to(REPOSITORY))
            for path in (REPOSITORY / "research").rglob("*.py")
        }
        self.assertEqual(observed, _RESEARCH_MODULES)
        forbidden_calls = {
            "open", "exec", "eval", "__import__", "__subclasses__",
            "read", "read_text", "read_bytes", "write", "write_text",
            "write_bytes", "system", "popen", "connect", "urlopen",
        }
        for path in sorted(observed):
            with self.subTest(path=path):
                tree = ast.parse((REPOSITORY / path).read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            self.assertIn(alias.name, _STDLIB_IMPORTS)
                    elif isinstance(node, ast.ImportFrom):
                        if node.level:
                            self.assertEqual(node.level, 1)
                            if node.module is None:
                                for alias in node.names:
                                    self.assertIn(alias.name, _LOCAL_IMPORTS)
                            else:
                                self.assertIn(node.module, _LOCAL_IMPORTS)
                        else:
                            self.assertIn(node.module, _STDLIB_IMPORTS)
                    elif isinstance(node, ast.Call):
                        call = node.func
                        if isinstance(call, ast.Name):
                            self.assertNotIn(call.id, forbidden_calls | {"compile"})
                        elif isinstance(call, ast.Attribute):
                            self.assertNotIn(call.attr, forbidden_calls)
                            if call.attr == "compile":
                                self.assertIsInstance(call.value, ast.Name)
                                self.assertEqual(call.value.id, "re")


class HistoricalExtraFixtureExclusionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Read a single pinned source blob, never an experiment or benchmark run.
        cls.source = subprocess.check_output(
            ["git", "show", _CUTOFF_COMMIT + ":" + _BENCHMARK_SOURCE_PATH],
            cwd=REPOSITORY,
        )
        cls.specs = _literal_assignment(cls.source, "_FIXTURE_SPECS_V1")
        additions = [row for row in cls.specs if row[1] == "PLAN0013_SYNTHETIC_ADDITION"]
        if len(additions) != 1 or additions[0][0] != _EXTRA_FIXTURE_ID:
            raise AssertionError("historical synthetic addition inventory changed")
        cls.fixture_bytes = additions[0][2].encode("utf-8")
        cls.definition = json.loads(cls.fixture_bytes)

    def test_extra_fixture_is_authenticated_source_only_and_separate_from_seven(self):
        git_header = b"blob " + str(len(self.source)).encode("ascii") + b"\0"
        self.assertEqual(
            hashlib.sha1(git_header + self.source).hexdigest(), _BENCHMARK_SOURCE_BLOB
        )
        self.assertEqual((REPOSITORY / _BENCHMARK_SOURCE_PATH).read_bytes(), self.source)
        self.assertEqual(len(self.specs), 5)
        self.assertEqual(sum(row[1] == "PLAN0012_SYNTHETIC_REUSE" for row in self.specs), 4)
        self.assertEqual(len(self.fixture_bytes), 590)
        self.assertEqual(hashlib.sha256(self.fixture_bytes).hexdigest(), _EXTRA_FIXTURE_SHA256)
        self.assertEqual(_canonical_json(self.definition).encode("utf-8"), self.fixture_bytes)
        pins_source = (REPOSITORY / "research/parity_forge_history/history_pins.py").read_text()
        seven = _literal_assignment(pins_source, "PLAN0012_SYNTHETIC_FIXTURE_IDENTITIES_V1")
        self.assertEqual(len(seven), 7)
        self.assertNotIn(_EXTRA_FIXTURE_ID, {row[0] for row in seven})

    def test_all_spatial_role_and_kind_relabelings_remain_outside_plan0015(self):
        admitted_profiles = {
            frozenset(universe.vector_profile_vectors(profile))
            for profile in (
                universe.VectorProfile.ORTHOGONAL_4,
                universe.VectorProfile.DIAGONAL_4,
                universe.VectorProfile.KING_8,
            )
        }
        self.assertEqual({len(profile) for profile in admitted_profiles}, {4, 8})
        swap_profiles = set()
        for rotations in range(4):
            for reflected in (False, True):
                for role_swapped in (False, True):
                    for alpha_renamed in (False, True):
                        image = _independent_image(
                            self.definition, rotations, reflected, role_swapped,
                            alpha_renamed,
                        )
                        self.assertEqual(image["max_plies"], 2)
                        with self.assertRaisesRegex(ValueError, "max_plies 18"):
                            compiler.project_compiled_schema_v4_json_v1(_canonical_json(image))
                        swap = next(role["action"] for role in image["roles"].values()
                                    if role["action"]["kind"] == "SWAP")
                        profile = frozenset(tuple(vector) for vector in swap["vectors"])
                        self.assertEqual(len(profile), 1)
                        self.assertNotIn(profile, admitted_profiles)
                        swap_profiles.add(profile)
        self.assertEqual(len(swap_profiles), 4)
        # Every global alpha renaming changes only piece strings, never either
        # invariant above; arbitrary label bijections cannot repair this gap.


if __name__ == "__main__":
    unittest.main()
