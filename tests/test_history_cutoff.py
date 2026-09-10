import ast
import subprocess
import unittest
from pathlib import Path

from research.parity_forge_history import history_cutoff as cutoff


REPOSITORY = Path(__file__).resolve().parents[1]


class HistoryCutoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.paths = subprocess.check_output(
            [
                "git",
                "ls-tree",
                "-r",
                "--name-only",
                cutoff.HISTORY_CUTOFF_COMMIT_V1,
                "--",
                "experiments",
            ],
            cwd=REPOSITORY,
            text=True,
        ).splitlines()
        cls.paths = [path for path in cls.paths if path.endswith(".json")]

    def _classify(self, paths=None, **overrides):
        arguments = {
            "cutoff_commit": cutoff.HISTORY_CUTOFF_COMMIT_V1,
            "cutoff_tree": cutoff.HISTORY_CUTOFF_TREE_V1,
            "plan0013_subtree": cutoff.PLAN0013_SUBTREE_V1,
            "plan0014_subtree": cutoff.PLAN0014_SUBTREE_V1,
        }
        arguments.update(overrides)
        return cutoff.classify_history_cutoff_paths_v1(
            self.paths if paths is None else paths, **arguments
        )

    def test_real_cutoff_tree_closes_without_opening_artifacts(self):
        observed = self._classify()
        self.assertEqual(observed["json_path_count"], 152_749)
        self.assertEqual(observed["legacy"]["path_count"], 66)
        self.assertEqual(observed["plan0013"]["path_count"], 152_678)
        self.assertEqual(observed["plan0014"]["path_count"], 5)
        self.assertEqual(observed["plan0013"]["artifacts_opened"], 0)
        self.assertEqual(observed["plan0014"]["artifacts_opened"], 0)

    def test_pinned_git_coordinates_match_the_repository_objects(self):
        tree = subprocess.check_output(
            ["git", "show", "-s", "--format=%T", cutoff.HISTORY_CUTOFF_COMMIT_V1],
            cwd=REPOSITORY,
            text=True,
        ).strip()
        self.assertEqual(tree, cutoff.HISTORY_CUTOFF_TREE_V1)
        for path, expected in (
            (
                "experiments/runs/plan0013-atlas-development-evidence-v2",
                cutoff.PLAN0013_SUBTREE_V1,
            ),
            (
                "experiments/runs/plan0014-plan0013-assessment-reconstruction-evidence-v1",
                cutoff.PLAN0014_SUBTREE_V1,
            ),
        ):
            record = subprocess.check_output(
                ["git", "ls-tree", cutoff.HISTORY_CUTOFF_COMMIT_V1, path],
                cwd=REPOSITORY,
                text=True,
            ).strip()
            mode, object_type, identity_and_path = record.split(None, 2)
            identity, observed_path = identity_and_path.split("\t", 1)
            self.assertEqual((mode, object_type), ("040000", "tree"))
            self.assertEqual(observed_path, path)
            self.assertEqual(identity, expected)

    def test_commit_tree_and_subtree_coordinates_are_exact(self):
        for name, value in (
            ("cutoff_commit", "0" * 40),
            ("cutoff_tree", "0" * 40),
            ("plan0013_subtree", "0" * 40),
            ("plan0014_subtree", "0" * 40),
        ):
            with self.subTest(name=name):
                with self.assertRaisesRegex(cutoff.HistoryCutoffError, "mismatch"):
                    self._classify(**{name: value})

    def test_path_inventory_rejects_omission_addition_reorder_and_substitution(self):
        variants = (
            self.paths[:-1],
            self.paths + ["experiments/unreviewed.json"],
            list(reversed(self.paths)),
            self.paths[:-1] + ["experiments/unreviewed.json"],
        )
        for paths in variants:
            with self.subTest(length=len(paths)):
                with self.assertRaises(cutoff.HistoryCutoffError):
                    self._classify(paths)

    def test_input_types_are_exact(self):
        with self.assertRaisesRegex(TypeError, "list or tuple"):
            self._classify(set(self.paths))
        changed = list(self.paths)
        changed[0] = b"experiments/not-a-string.json"
        with self.assertRaisesRegex(TypeError, "only strings"):
            self._classify(changed)

    def test_module_has_no_filesystem_process_or_dynamic_import_capability(self):
        source = (
            REPOSITORY / "research/parity_forge_history/history_cutoff.py"
        ).read_text()
        tree = ast.parse(source)
        imported = set()
        called = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                imported.add((node.module or "").split(".")[0])
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    called.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    called.add(node.func.attr)
        self.assertTrue(
            imported.isdisjoint(
                {"os", "pathlib", "subprocess", "socket", "urllib", "parity_forge"}
            )
        )
        self.assertTrue(
            called.isdisjoint({"open", "exec", "eval", "compile", "__import__"})
        )


if __name__ == "__main__":
    unittest.main()
