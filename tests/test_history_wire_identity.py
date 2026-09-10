import ast
import copy
import hashlib
import itertools
import json
import runpy
import subprocess
import unittest
from pathlib import Path

from parity_forge import atlas_history as legacy
from parity_forge import dsl, symmetry
from research.parity_forge_history import wire_identity as wire


REPOSITORY = Path(__file__).resolve().parents[1]


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _definition_values(value):
    if type(value) is dict:
        if set(("schema_version", "name", "board_size", "roles", "initial_pieces")) <= set(value):
            try:
                dsl.parse_definition(value)
            except (ValueError, TypeError):
                return
            yield value
            return
        for child in value.values():
            yield from _definition_values(child)
    elif type(value) is list:
        for child in value:
            yield from _definition_values(child)


def _rename(value, names):
    result = copy.deepcopy(value)
    for role in result["roles"].values():
        for field in ("action", "goal"):
            role[field]["piece"] = names[role[field]["piece"]]
    for piece in result["initial_pieces"]:
        piece["piece"] = names[piece["piece"]]
    return result


def _swap(value, rename=False):
    result = copy.deepcopy(value)
    result["roles"] = {"A": result["roles"]["B"], "B": result["roles"]["A"]}
    result["first_player"] = "B" if result["first_player"] == "A" else "A"
    for piece in result["initial_pieces"]:
        piece["owner"] = "B" if piece["owner"] == "A" else "A"
    if rename:
        result = _rename(result, {"a": "b", "b": "a"})
    return result


def _neutral_oracle(value):
    options = []
    for raw in (value, _swap(value)):
        definition = dsl.parse_definition(raw)
        for transform in symmetry.D4_TRANSFORMS:
            current = symmetry.transform_definition(definition, transform).to_dict()
            labels = [current["roles"][owner][field]["piece"] for field in ("action", "goal") for owner in ("A", "B")]
            labels += [piece["piece"] for piece in current["initial_pieces"]]
            unique = list(dict.fromkeys(labels))
            renamed = _rename(current, {label: "k{}".format(index) for index, label in enumerate(unique)})
            del renamed["name"]
            options.append(_canonical(renamed))
    return hashlib.sha256(b"parity-forge:plan0015:history-role-neutral-definition:v1\0" + min(options)).hexdigest()


class HistoryWireIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.values = {}
        cls.occurrences = 0
        # Only the frozen 66-source allow-list is opened. No Plan-0013 or
        # Plan-0014 evidence member or candidate builder participates.
        for path, expected_sha, expected_count in legacy.ATLAS_HISTORY_INVENTORY_V1:
            raw = subprocess.check_output([
                "git", "show", "{}:{}".format(legacy.ATLAS_HISTORY_CUTOFF_COMMIT_V1, path)
            ], cwd=REPOSITORY)
            if hashlib.sha256(raw).hexdigest() != expected_sha or len(raw) != expected_count:
                raise AssertionError("frozen history blob mismatch")
            for value in _definition_values(json.loads(raw)):
                cls.occurrences += 1
                cls.values[dsl.definition_hash(dsl.parse_definition(value))] = value
        namespace = runpy.run_path(str(REPOSITORY / "tests/test_agency_benchmark.py"))
        cls.fixtures = {row["fixture_id"]: copy.deepcopy(row["definition"]) for row in namespace["FIXTURES"]}
        cls.values.update({dsl.definition_hash(dsl.parse_definition(value)): value for value in cls.fixtures.values()})

    def test_all_frozen_definitions_match_authoritative_normal_form_exact_and_d4(self):
        self.assertEqual(self.occurrences, 2243)
        self.assertEqual(len(self.values), 1179)
        for expected_hash, source in self.values.items():
            with self.subTest(definition=expected_hash):
                parsed = dsl.parse_definition(source)
                self.assertEqual(wire.normalize_definition_v1(source), parsed.to_dict())
                self.assertEqual(wire.definition_hash_v1(source), expected_hash)
                self.assertEqual(wire.d4_definition_hash_v1(source), symmetry.d4_canonical_hash(parsed))

    def test_normalization_reorders_and_detaches_without_changing_input(self):
        source = copy.deepcopy(self.fixtures["initial-stuck-zero-v1"])
        source["name"] = "  表示名  "
        source["initial_pieces"].reverse()
        for role in source["roles"].values():
            if "vectors" in role["action"]:
                role["action"]["vectors"].reverse()
            if "edges" in role["goal"]:
                role["goal"]["edges"].reverse()
        before = copy.deepcopy(source)
        normalized = wire.normalize_definition_v1(source)
        self.assertEqual(normalized, dsl.parse_definition(source).to_dict())
        self.assertEqual(source, before)
        normalized["roles"]["A"]["action"]["piece"] = "detached"
        normalized["initial_pieces"][0]["position"][0] = 99
        self.assertEqual(source, before)

    def test_schema_action_goal_admission_matches_authoritative_parser(self):
        prototype = next(iter(self.fixtures.values()))
        actions = tuple(kind.value for kind in dsl.ActionKind)
        goals = tuple(kind.value for kind in dsl.GoalKind)
        admitted = rejected = 0
        for version, aa, ab, ga, gb in itertools.product(range(1, 5), actions, actions, goals, goals):
            source = copy.deepcopy(prototype)
            source["schema_version"] = version
            if version == 2:
                source["terminal_policy"] = {"no_legal_action": "DRAW"}
            for owner, action, goal in (("A", aa, ga), ("B", ab, gb)):
                role = source["roles"][owner]
                role["action"] = {"kind": action, "piece": owner.lower()}
                if action != "PLACE":
                    role["action"]["vectors"] = [[1, 0], [-1, 0]]
                role["goal"] = {"kind": goal, "piece": owner.lower()}
                if goal == "CONNECT_EDGES":
                    role["goal"]["edges"] = ["TOP", "BOTTOM"]
                elif goal == "REACH_EDGE":
                    role["goal"]["edge"] = "BOTTOM"
            try:
                expected = dsl.parse_definition(source).to_dict()
            except dsl.DefinitionError:
                rejected += 1
                with self.assertRaises(wire.WireDefinitionError):
                    wire.normalize_definition_v1(source)
            else:
                admitted += 1
                self.assertEqual(wire.normalize_definition_v1(source), expected)
        self.assertEqual((admitted, rejected), (457, 1307))

    def test_neutral_matches_independent_oracle_all_seven_fixtures_and_d4(self):
        for source in self.fixtures.values():
            expected = _neutral_oracle(source)
            self.assertEqual(wire.role_neutral_definition_hash_v1(source), expected)
            for transform in symmetry.D4_TRANSFORMS:
                transformed = symmetry.transform_definition(dsl.parse_definition(source), transform).to_dict()
                self.assertEqual(wire.role_neutral_definition_hash_v1(transformed), expected)
                self.assertEqual(wire.role_neutral_definition_hash_v1(_swap(transformed)), expected)

    def test_neutral_complete_role_swap_includes_compiler_piece_relabeling(self):
        source = {
            "schema_version": 4, "name": "compiler-R-witness", "board_size": 3,
            "first_player": "A", "max_plies": 18,
            "roles": {
                "A": {"action": {"kind": "CONVERT", "piece": "a", "vectors": [[1, 0]]}, "goal": {"kind": "ELIMINATE", "piece": "b"}},
                "B": {"action": {"kind": "HOP", "piece": "b", "vectors": [[-1, 0], [0, 1]]}, "goal": {"kind": "REACH_EDGE", "piece": "b", "edge": "TOP"}},
            },
            "initial_pieces": [{"owner": "A", "piece": "a", "position": [0, 1]}, {"owner": "B", "piece": "b", "position": [2, 2]}],
        }
        expected = wire.role_neutral_definition_hash_v1(source)
        self.assertEqual(expected, wire.role_neutral_definition_hash_v1(_swap(source, rename=True)))
        toggled = copy.deepcopy(source)
        toggled["first_player"] = "B"
        self.assertNotEqual(expected, wire.role_neutral_definition_hash_v1(toggled))
        owner_only = copy.deepcopy(source)
        for piece in owner_only["initial_pieces"]:
            piece["owner"] = "B" if piece["owner"] == "A" else "A"
        self.assertNotEqual(expected, wire.role_neutral_definition_hash_v1(owner_only))

    def test_neutral_preserves_global_kind_equality_and_extra_kinds(self):
        source = copy.deepcopy(self.fixtures["capture-eliminate-one-sided-b-v1"])
        # Two extra inert kinds and a foreign-owned actor kind require a global
        # injective rename; merely rewriting each owner's kind would merge games.
        source["initial_pieces"] = [
            {"owner": "A", "piece": "extra_x", "position": [0, 0]},
            {"owner": "B", "piece": "extra_y", "position": [0, 2]},
            {"owner": "A", "piece": source["roles"]["B"]["action"]["piece"], "position": [2, 1]},
        ]
        labels = set(piece["piece"] for piece in source["initial_pieces"])
        labels.update(role[field]["piece"] for role in source["roles"].values() for field in ("action", "goal"))
        renamed = _rename(source, {label: "renamed{}".format(index) for index, label in enumerate(sorted(labels, reverse=True))})
        expected = wire.role_neutral_definition_hash_v1(source)
        self.assertEqual(expected, wire.role_neutral_definition_hash_v1(renamed))
        self.assertEqual(expected, _neutral_oracle(source))
        merged = copy.deepcopy(source)
        merged["initial_pieces"][1]["piece"] = "extra_x"
        self.assertNotEqual(expected, wire.role_neutral_definition_hash_v1(merged))
        for transform in symmetry.D4_TRANSFORMS:
            transformed = symmetry.transform_definition(dsl.parse_definition(source), transform).to_dict()
            self.assertEqual(expected, wire.role_neutral_definition_hash_v1(transformed))

    def test_names_are_exact_only_and_real_rule_fields_remain_distinct(self):
        source = copy.deepcopy(self.fixtures["push-win-draw-loss-v1"])
        renamed = copy.deepcopy(source)
        renamed["name"] += " renamed"
        self.assertNotEqual(wire.definition_hash_v1(source), wire.definition_hash_v1(renamed))
        self.assertEqual(wire.d4_definition_hash_v1(source), wire.d4_definition_hash_v1(renamed))
        self.assertEqual(wire.role_neutral_definition_hash_v1(source), wire.role_neutral_definition_hash_v1(renamed))
        for key, value in (("max_plies", source["max_plies"] + 1), ("board_size", 5)):
            changed = copy.deepcopy(source)
            changed[key] = value
            self.assertNotEqual(wire.role_neutral_definition_hash_v1(source), wire.role_neutral_definition_hash_v1(changed))

    def test_unknown_fields_invalid_scalars_and_invalid_shape_fail_closed(self):
        source = self.fixtures["push-win-draw-loss-v1"]
        mutations = [
            lambda x: x.update(winner="A"),
            lambda x: x.update(schema_version=True),
            lambda x: x.update(board_size=3.0),
            lambda x: x.update(max_plies=0),
            lambda x: x.update(first_player="C"),
            lambda x: x.update(name=" " * 3),
            lambda x: x.update(name="x" * 121),
            lambda x: x.update(terminal_policy={"no_legal_action": "DRAW"}),
            lambda x: x["roles"]["A"]["action"].update(piece="Bad"),
            lambda x: x["roles"]["A"]["action"].update(vectors=[[0, 0]]),
            lambda x: x["roles"]["A"]["action"].update(vectors=[[1, 0], [1, 0]]),
            lambda x: x["roles"]["A"]["action"].update(vectors=[[2, 0]]),
            lambda x: x["roles"]["A"]["goal"].update(extra=True),
            lambda x: x["initial_pieces"].append(copy.deepcopy(x["initial_pieces"][0])),
            lambda x: x["initial_pieces"][0].update(position=[3, 0]),
            lambda x: x["initial_pieces"][0].update(owner=None),
        ]
        for index, mutate in enumerate(mutations):
            changed = copy.deepcopy(source)
            mutate(changed)
            with self.subTest(mutation=index):
                with self.assertRaises(dsl.DefinitionError):
                    dsl.parse_definition(changed)
                for operation in (wire.normalize_definition_v1, wire.definition_hash_v1, wire.d4_definition_hash_v1, wire.role_neutral_definition_hash_v1):
                    with self.assertRaises(wire.WireDefinitionError):
                        operation(changed)

    def test_bounded_wire_rejects_subclasses_cycles_non_json_and_oversize(self):
        class HostileDict(dict):
            def items(self):
                raise AssertionError("untrusted override called")

        source = self.fixtures["push-win-draw-loss-v1"]
        variants = [HostileDict(source)]
        for value in (tuple(source["initial_pieces"]), HostileDict(), float("nan"), 1 << 100_000, "\ud800", "x" * 65_537):
            changed = copy.deepcopy(source)
            changed["initial_pieces"] = value
            variants.append(changed)
        cyclic = copy.deepcopy(source)
        cyclic["initial_pieces"] = [cyclic]
        variants.append(cyclic)
        deep = copy.deepcopy(source)
        for _ in range(15):
            deep = {"x": deep}
        variants.append(deep)
        wide = copy.deepcopy(source)
        wide["initial_pieces"] = [None] * 2049
        variants.append(wide)
        for value in variants:
            with self.assertRaises(wire.WireDefinitionError):
                wire.normalize_definition_v1(value)

    def test_wire_production_imports_are_stdlib_and_no_outcome_capability(self):
        source = (REPOSITORY / "research/parity_forge_history/wire_identity.py").read_text()
        tree = ast.parse(source)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, {"open", "eval", "exec", "compile", "__import__"})
        self.assertEqual(imports, {"__future__", "hashlib", "json", "re"})


if __name__ == "__main__":
    unittest.main()
