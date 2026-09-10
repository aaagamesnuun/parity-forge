import copy
import hashlib
import json
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from parity_forge.capture_boundary import (
    CAPTURE_BOUNDARY_COVERED_D4_ROOT,
    CAPTURE_BOUNDARY_COVERAGE_ROOT,
    CAPTURE_BOUNDARY_ELIGIBLE_POOL_ROOT,
    CAPTURE_BOUNDARY_MANIFEST_ID,
    CAPTURE_BOUNDARY_PAIR_COUNT,
    CAPTURE_BOUNDARY_SELECTION_FINGERPRINT,
    CAPTURE_BOUNDARY_STRATUM_COUNT,
    CAPTURE_BOUNDARY_PRIOR_SOURCES,
    CAPTURE_BOUNDARY_LANDSCAPE_SOURCE,
    CAPTURE_BOUNDARY_LEDGER_ROOT,
    build_boundary_projection_bundle,
    build_capture_boundary_manifest,
    capture_boundary_state_upper_bound,
    derive_capture_boundary_treatment,
    project_boundary_definitions,
    project_boundary_exclusion_sources,
    resolve_boundary_dependency_closure,
    validate_boundary_coverage_projection,
    validate_boundary_definition_projection,
    validate_boundary_exclusion_ledger,
    validate_capture_boundary_manifest,
    validate_capture_boundary_move_containment,
    validate_capture_boundary_pair,
)
from parity_forge.capture import CAPTURE_STATE_BOUND
from parity_forge.dsl import InitialPiece, Player, parse_definition
from parity_forge.engine import GameState
from parity_forge.symmetry import canonicalize_d4, mechanical_json


REPOSITORY = Path(__file__).resolve().parents[1]
FULL_CUTOFF = "034759a0f8072db7462b009b3f160ec176212fd1"
REGISTRY_DOMAIN = b"capture-boundary-v1-evaluated-run-registry-v1\0"
COVERAGE_DOMAIN = b"capture-boundary-v1-coverage-projection-v1\0"
LEDGER_DOMAIN = b"capture-boundary-v1-exclusion-ledger-v1\0"
DEFINITION_KEYS = {
    "schema_version",
    "name",
    "board_size",
    "first_player",
    "max_plies",
    "roles",
    "initial_pieces",
}


def _load(path):
    return json.loads((REPOSITORY / path).read_text(encoding="utf-8"))


def _sha(path):
    return hashlib.sha256((REPOSITORY / path).read_bytes()).hexdigest()


def _canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _domain_digest(domain, value):
    return hashlib.sha256(domain + _canonical(value)).hexdigest()


def _poison_nondefinitions(value):
    if isinstance(value, dict):
        if DEFINITION_KEYS <= set(value):
            return copy.deepcopy(value)
        return {key: _poison_nondefinitions(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_poison_nondefinitions(item) for item in value]
    if value is None:
        return "POISON_NULL"
    if type(value) is bool:
        return not value
    if type(value) is int:
        return value + 10_003
    if type(value) is float:
        return value + 10_003.25
    if isinstance(value, str):
        return "POISON:" + value
    raise AssertionError("test poison encountered a non-JSON value")


class CaptureBoundaryProductionFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source_paths = [path for path, _ in CAPTURE_BOUNDARY_PRIOR_SOURCES]
        source_paths.append(CAPTURE_BOUNDARY_LANDSCAPE_SOURCE[0])
        cls.source_records = tuple(_load(path) for path in source_paths)
        cls.source_metadata = (
            {
                "label": "generator-v1-development",
                "path": CAPTURE_BOUNDARY_PRIOR_SOURCES[0][0],
                "sha256": CAPTURE_BOUNDARY_PRIOR_SOURCES[0][1],
                "run_id": "20260830T154155824053Z-batch-g20260831",
            },
            {
                "label": "generator-v2-development",
                "path": CAPTURE_BOUNDARY_PRIOR_SOURCES[1][0],
                "sha256": CAPTURE_BOUNDARY_PRIOR_SOURCES[1][1],
                "run_id": "20260830T154309225370Z-batch-g20260831",
            },
            {
                "label": "generator-v2-heldout-20260901",
                "path": CAPTURE_BOUNDARY_PRIOR_SOURCES[2][0],
                "sha256": CAPTURE_BOUNDARY_PRIOR_SOURCES[2][1],
                "run_id": "20260830T184008717197Z-strong-g20260901",
            },
            {
                "label": "landscape-v1-manifest",
                "path": CAPTURE_BOUNDARY_LANDSCAPE_SOURCE[0],
                "sha256": CAPTURE_BOUNDARY_LANDSCAPE_SOURCE[1],
                "manifest_id": "generator-v2-3x3-landscape-v1",
            },
        )
        cls.supporting_dependency_metadata = (
            {
                "path": "experiments/corpora/static-v1/corpus.json",
                "sha256": "4ad81a4019f072a6f47d88e86f1761c0f55ef792f647d1348d292085496ce208",
                "identity_kind": "corpus_id",
                "identity": "static-v1-2026-08-31",
            },
            {
                "path": "experiments/corpora/stalemate-v1/manifest.json",
                "sha256": "ed9a9b93ad234f4375ded0e135f5436c82fb127988784a86aa33ab4f776ff176",
                "identity_kind": "manifest_id",
                "identity": "generator-v2-3x3-stalemate-paired-v1",
            },
            {
                "path": "experiments/corpora/capture-v1/manifest.json",
                "sha256": "6bc466453f60bc4ae2a6401fc76a77eebe4a7ebee82111e53ac4463400588f4f",
                "identity_kind": "manifest_id",
                "identity": "generator-v2-3x3-capture-paired-v1",
            },
        )
        cls.supporting_dependency_records = tuple(
            _load(metadata["path"])
            for metadata in cls.supporting_dependency_metadata
        )
        output = subprocess.run(
            [
                "git",
                "ls-tree",
                "-r",
                "--name-only",
                FULL_CUTOFF,
                "--",
                "experiments/runs",
            ],
            cwd=REPOSITORY,
            check=True,
            stdout=subprocess.PIPE,
            text=True,
        ).stdout
        paths = sorted(path for path in output.splitlines() if path.endswith("/run.json"))
        cls.coverage_records = tuple(_load(path) for path in paths)
        entries = [{"path": path, "sha256": _sha(path)} for path in paths]
        registry_root = hashlib.sha256(REGISTRY_DOMAIN + _canonical(entries)).hexdigest()
        cls.coverage_registry = {
            "cutoff_commit": FULL_CUTOFF,
            "run_count": len(entries),
            "root_sha256": registry_root,
            "entries": entries,
        }
        cls.bundle = project_boundary_exclusion_sources(
            cls.source_records,
            cls.source_metadata,
            cls.supporting_dependency_records,
            cls.supporting_dependency_metadata,
            cls.coverage_records,
            cls.coverage_registry,
        )
        cls.ledger = cls.bundle["exclusion_ledger"]
        cls.coverage = cls.bundle["coverage_projection"]
        cls.source_projections = tuple(
            project_boundary_definitions(record) for record in cls.source_records
        )
        cls.run_projections = {
            entry["path"]: project_boundary_definitions(record)
            for entry, record in zip(entries, cls.coverage_records)
        }
        cls.resolution_records = {
            record["path"]: {
                "projection_kind": record["projection_kind"],
                "direct_dependencies": record["direct_dependencies"],
                "dependencies": record["dependencies"],
                "projected_d4_hashes": record["projected_d4_hashes"],
            }
            for record in cls.coverage["records"]
        }
        cls.plan0008_manifest = _load("experiments/corpora/capture-v1/manifest.json")
        cls.manifest = build_capture_boundary_manifest(
            cls.ledger,
            cls.coverage,
            cls.plan0008_manifest,
            {"fixture": "production-outcome-free-selection"},
        )

    def _assert_manifest_rejected(self, mutation):
        value = copy.deepcopy(self.manifest)
        mutation(value)
        with self.assertRaises(ValueError):
            validate_capture_boundary_manifest(
                value,
                self.ledger,
                self.coverage,
                self.plan0008_manifest,
            )

    def test_production_coverage_and_exclusion_census_and_roots(self):
        self.assertEqual(set(self.bundle), {"exclusion_ledger", "coverage_projection"})
        self.assertEqual(self.coverage["registry_count"], 16)
        self.assertEqual(self.coverage["definition_occurrence_count"], 1085)
        self.assertEqual(self.coverage["schema1_occurrence_count"], 827)
        self.assertEqual(self.coverage["covered_vocabulary_d4_count"], 439)
        self.assertEqual(
            self.coverage["covered_vocabulary_d4_root"],
            CAPTURE_BOUNDARY_COVERED_D4_ROOT,
        )
        self.assertEqual(self.coverage["coverage_root"], CAPTURE_BOUNDARY_COVERAGE_ROOT)
        self.assertEqual(self.ledger["ledger_root"], CAPTURE_BOUNDARY_LEDGER_ROOT)
        self.assertEqual(
            self.ledger["evaluated_coverage"]["coverage_root"],
            CAPTURE_BOUNDARY_COVERAGE_ROOT,
        )
        self.assertEqual(
            self.ledger["census"],
            {
                "prior_definition_occurrences": 300,
                "prior_unique_definition_hashes": 270,
                "prior_unique_d4_hashes": 266,
                "prior_board3_d4_hashes": 77,
                "prior_vocabulary_d4_hashes": 55,
                "landscape_d4_hashes": 384,
                "declared_exclusion_d4_hashes": 650,
                "vocabulary_intersection_d4_hashes": 439,
            },
        )
        validate_boundary_coverage_projection(self.coverage)
        validate_boundary_exclusion_ledger(self.ledger)

        run_projections = {
            entry["path"]: project_boundary_definitions(record)
            for entry, record in zip(
                self.coverage_registry["entries"], self.coverage_records
            )
        }
        validate_boundary_coverage_projection(
            self.coverage,
            self.coverage_registry["entries"],
            run_projections,
        )
        source_projections = [
            project_boundary_definitions(record) for record in self.source_records
        ]
        validate_boundary_exclusion_ledger(
            self.ledger,
            source_projections[:3],
            source_projections[3],
            self.coverage,
        )

    def test_coverage_is_closed_world_and_records_dependencies(self):
        by_path = {record["path"]: record for record in self.coverage["records"]}
        static = by_path[
            "experiments/runs/20260830T153256441950Z-static-4ad81a40/run.json"
        ]
        play = by_path[
            "experiments/runs/20260830T153616787888Z-play-1c478ea4/run.json"
        ]
        solve = by_path[
            "experiments/runs/20260830T153746479973Z-solve-1c478ea4/run.json"
        ]
        self.assertEqual(len(static["dependencies"]), 1)
        self.assertEqual(len(play["dependencies"]), 1)
        self.assertEqual(len(solve["dependencies"]), 1)
        capture_stress = by_path[
            "experiments/runs/20260830T230308952280Z-capture-stress-e4fc6e97/run.json"
        ]
        self.assertEqual(capture_stress["projection_kind"], "REFERENCE_CAPTURE_SOURCE_CLOSURE")
        self.assertEqual(capture_stress["projected_d4_count"], 384)
        self.assertEqual(len(capture_stress["direct_dependencies"]), 2)
        self.assertEqual(len(capture_stress["dependencies"]), 4)
        self.assertEqual(
            set(self.coverage["dependency_artifacts"][0]),
            {"path", "sha256", "identity_kind", "identity"},
        )

    def test_production_manifest_census_roots_and_public_reconstruction(self):
        pairs = validate_capture_boundary_manifest(
            self.manifest,
            self.ledger,
            self.coverage,
            self.plan0008_manifest,
        )
        self.assertEqual(self.manifest["manifest_id"], CAPTURE_BOUNDARY_MANIFEST_ID)
        self.assertEqual(len(pairs), CAPTURE_BOUNDARY_PAIR_COUNT)
        self.assertEqual(len(self.manifest["eligible_pools"]), CAPTURE_BOUNDARY_STRATUM_COUNT)
        self.assertEqual(self.manifest["census"]["unused_relevant_d4_count"], 724)
        self.assertEqual(self.manifest["census"]["paired_analysis_valid_d4_count"], 563)
        self.assertEqual(self.manifest["census"]["source_treatment_gate_disagreement_count"], 0)
        self.assertEqual(self.manifest["census"]["minimum_eligible_stratum_count"], 16)
        self.assertEqual(
            self.manifest["selection_protocol"]["eligible_pool_root"],
            CAPTURE_BOUNDARY_ELIGIBLE_POOL_ROOT,
        )
        self.assertEqual(
            self.manifest["selection_protocol"]["selection_fingerprint"],
            CAPTURE_BOUNDARY_SELECTION_FINGERPRINT,
        )
        self.assertEqual(
            [pool["stratum_id"] for pool in self.manifest["eligible_pools"]],
            sorted(pool["stratum_id"] for pool in self.manifest["eligible_pools"]),
        )
        self.assertTrue(all(pool["quota"] == 4 for pool in self.manifest["eligible_pools"]))

    def test_pairs_are_one_variable_canonical_bounded_and_plan0008_fresh(self):
        old_hashes = {
            pair[field]
            for pair in self.plan0008_manifest["pairs"]
            for field in ("source_d4_canonical_hash", "treatment_d4_canonical_hash")
        }
        selected_hashes = set()
        for pair in self.manifest["pairs"]:
            source = parse_definition(pair["source_definition"])
            treatment = parse_definition(pair["treatment_definition"])
            validate_capture_boundary_pair(source, treatment)
            self.assertEqual(derive_capture_boundary_treatment(source), treatment)
            reverted = treatment.to_dict()
            reverted["schema_version"] = 1
            reverted["roles"]["B"]["action"]["kind"] = "MOVE"
            self.assertEqual(_canonical(reverted), _canonical(source.to_dict()))
            self.assertEqual(capture_boundary_state_upper_bound(source), CAPTURE_STATE_BOUND)
            self.assertEqual(capture_boundary_state_upper_bound(treatment), CAPTURE_STATE_BOUND)
            self.assertEqual(mechanical_json(source), canonicalize_d4(source).mechanical_json)
            self.assertEqual(mechanical_json(treatment), canonicalize_d4(treatment).mechanical_json)
            selected_hashes.add(pair["source_d4_canonical_hash"])
            selected_hashes.add(pair["treatment_d4_canonical_hash"])
        self.assertTrue(selected_hashes.isdisjoint(old_hashes))

    def test_recursive_projection_is_poison_invariant_but_definition_sensitive(self):
        source = self.coverage_records[3]
        projection = project_boundary_definitions(source)
        poisoned = project_boundary_definitions(_poison_nondefinitions(source))
        self.assertEqual(_canonical(projection), _canonical(poisoned))
        changed = copy.deepcopy(source)
        changed["results"]["candidates"][0]["definition"]["name"] += " changed"
        self.assertNotEqual(
            projection["projection_root"],
            project_boundary_definitions(changed)["projection_root"],
        )

    def test_authenticated_adapter_rejects_poison_even_when_pure_projection_is_stable(self):
        records = list(copy.deepcopy(self.coverage_records))
        records[3] = _poison_nondefinitions(records[3])
        with self.assertRaises(ValueError):
            project_boundary_exclusion_sources(
                self.source_records,
                self.source_metadata,
                self.supporting_dependency_records,
                self.supporting_dependency_metadata,
                records,
                self.coverage_registry,
            )

    def test_supporting_dependencies_are_required_and_authenticated(self):
        tampered_records = list(copy.deepcopy(self.supporting_dependency_records))
        tampered_records[0]["frozen"] = False
        with self.assertRaises(ValueError):
            project_boundary_exclusion_sources(
                self.source_records,
                self.source_metadata,
                tampered_records,
                self.supporting_dependency_metadata,
                self.coverage_records,
                self.coverage_registry,
            )
        tampered_metadata = list(copy.deepcopy(self.supporting_dependency_metadata))
        tampered_metadata[1]["identity"] = "false-stalemate-manifest"
        with self.assertRaises(ValueError):
            project_boundary_exclusion_sources(
                self.source_records,
                self.source_metadata,
                self.supporting_dependency_records,
                tampered_metadata,
                self.coverage_records,
                self.coverage_registry,
            )

    def test_full_record_adapter_and_pure_projection_capabilities_are_separated(self):
        rebuilt = build_boundary_projection_bundle(
            self.source_projections,
            self.coverage_registry["entries"],
            self.run_projections,
            self.resolution_records,
            self.coverage["dependency_artifacts"],
        )
        self.assertEqual(_canonical(rebuilt), _canonical(self.bundle))
        with self.assertRaises(ValueError):
            build_boundary_projection_bundle(
                self.source_records,
                self.coverage_registry["entries"],
                self.run_projections,
                self.resolution_records,
                self.coverage["dependency_artifacts"],
            )
        poisoned_projections = dict(self.run_projections)
        poisoned_projections[self.coverage_registry["entries"][3]["path"]] = (
            project_boundary_definitions(
                _poison_nondefinitions(self.coverage_records[3])
            )
        )
        poison_rebuilt = build_boundary_projection_bundle(
            self.source_projections,
            self.coverage_registry["entries"],
            poisoned_projections,
            self.resolution_records,
            self.coverage["dependency_artifacts"],
        )
        self.assertEqual(_canonical(poison_rebuilt), _canonical(self.bundle))

    def test_dependency_closure_rejects_unknown_unresolved_cycles_and_false_identity(self):
        first = {
            "path": "experiments/a.json",
            "sha256": "1" * 64,
            "identity_kind": "manifest_id",
            "identity": "a",
        }
        second = {
            "path": "experiments/b.json",
            "sha256": "2" * 64,
            "identity_kind": "manifest_id",
            "identity": "b",
        }
        with self.assertRaises(ValueError):
            resolve_boundary_dependency_closure(
                {first["path"]: [], "experiments/unknown.json": []}, [first]
            )
        with self.assertRaises(ValueError):
            resolve_boundary_dependency_closure(
                {first["path"]: [second]}, [first]
            )
        with self.assertRaises(ValueError):
            resolve_boundary_dependency_closure(
                {first["path"]: [second], second["path"]: [first]},
                [first, second],
            )
        false_second = dict(second)
        false_second["sha256"] = "3" * 64
        with self.assertRaises(ValueError):
            resolve_boundary_dependency_closure(
                {first["path"]: [false_second], second["path"]: []},
                [first, second],
            )

    def test_frozen_coverage_and_ledger_roots_reject_self_consistent_resigning(self):
        coverage = copy.deepcopy(self.coverage)
        coverage["records"][0]["definition_projection_root"] = "0" * 64
        unsigned_coverage = dict(coverage)
        unsigned_coverage.pop("coverage_root")
        coverage["coverage_root"] = _domain_digest(
            COVERAGE_DOMAIN, unsigned_coverage
        )
        with self.assertRaises(ValueError):
            validate_boundary_coverage_projection(coverage)

        ledger = copy.deepcopy(self.ledger)
        ledger["sources"][0]["definition_projection_root"] = "0" * 64
        unsigned_ledger = dict(ledger)
        unsigned_ledger.pop("ledger_root")
        ledger["ledger_root"] = _domain_digest(LEDGER_DOMAIN, unsigned_ledger)
        with self.assertRaises(ValueError):
            validate_boundary_exclusion_ledger(ledger)

        registry = copy.deepcopy(self.coverage)
        registry["records"][0]["sha256"] = "0" * 64
        entries = [
            {"path": record["path"], "sha256": record["sha256"]}
            for record in registry["records"]
        ]
        registry["registry_root"] = _domain_digest(
            b"capture-boundary-v1-evaluated-run-registry-v1", entries
        )
        unsigned_registry = dict(registry)
        unsigned_registry.pop("coverage_root")
        registry["coverage_root"] = _domain_digest(
            COVERAGE_DOMAIN, unsigned_registry
        )
        with self.assertRaises(ValueError):
            validate_boundary_coverage_projection(registry)

    def test_definition_coverage_and_ledger_validators_reject_type_tampering(self):
        projection = project_boundary_definitions(self.coverage_records[3])
        for mutation in (
            lambda value: value.__setitem__("projection_version", True),
            lambda value: value.__setitem__("occurrence_count", True),
            lambda value: value["records"][0].__setitem__("schema_version", True),
            lambda value: value["records"][0].__setitem__("board_size", True),
        ):
            with self.subTest(mutation=mutation):
                tampered = copy.deepcopy(projection)
                mutation(tampered)
                with self.assertRaises(ValueError):
                    validate_boundary_definition_projection(tampered)
        coverage = copy.deepcopy(self.coverage)
        coverage["registry_count"] = True
        with self.assertRaises(ValueError):
            validate_boundary_coverage_projection(coverage)
        ledger = copy.deepcopy(self.ledger)
        ledger["census"]["declared_exclusion_d4_hashes"] = True
        with self.assertRaises(ValueError):
            validate_boundary_exclusion_ledger(ledger)

    def test_manifest_validator_rejects_type_and_recursive_schema_tampering(self):
        mutations = (
            lambda value: value.__setitem__("manifest_version", True),
            lambda value: value["census"].__setitem__("pair_count", True),
            lambda value: value["pairs"][0].__setitem__("selection_rank", True),
            lambda value: value["pairs"][0].__setitem__("vector_count", True),
            lambda value: value["selection_protocol"].__setitem__(
                "case_membership_outcome_fields_consulted", 0
            ),
            lambda value: value["provenance"].__setitem__(
                "nested", {"outcome": "POISON"}
            ),
            lambda value: value["pairs"][0].__setitem__("elapsed_seconds", 0.0),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self._assert_manifest_rejected(mutation)

    def test_manifest_builder_never_calls_solver_or_play(self):
        with mock.patch("parity_forge.solver.solve_game", side_effect=AssertionError), mock.patch(
            "parity_forge.play.play_game", side_effect=AssertionError
        ):
            rebuilt = build_capture_boundary_manifest(
                self.ledger,
                self.coverage,
                self.plan0008_manifest,
                {"fixture": "no-outcome-call"},
            )
        self.assertEqual(len(rebuilt["pairs"]), 64)

    def test_manifest_builder_and_cached_strata_are_mutation_isolated(self):
        first = build_capture_boundary_manifest(
            self.ledger,
            self.coverage,
            self.plan0008_manifest,
            {"fixture": "production-outcome-free-selection"},
        )
        original = copy.deepcopy(first)
        first_pair = first["pairs"][0]
        first_pool = first["eligible_pools"][0]
        self.assertIsNot(first_pair["stratum"], first_pool["stratum"])
        first_pair["stratum"]["first_player"] = "MUTATED"
        first_pair["source_definition"]["name"] = "MUTATED"
        self.assertNotEqual(
            first_pair["stratum"]["first_player"],
            first_pool["stratum"]["first_player"],
        )
        second = build_capture_boundary_manifest(
            self.ledger,
            self.coverage,
            self.plan0008_manifest,
            {"fixture": "production-outcome-free-selection"},
        )
        self.assertEqual(_canonical(second), _canonical(original))
        self.assertEqual(_canonical(self.manifest), _canonical(original))

    def test_engine_move_containment_all_2304_arrangements_for_v3_and_v4(self):
        pair_v3 = next(
            pair
            for pair in self.manifest["pairs"]
            if pair["vector_count"] == 3 and pair["source_definition"]["first_player"] == "A"
        )
        pair_v4 = next(
            pair
            for pair in self.manifest["pairs"]
            if pair["vector_count"] == 4 and pair["source_definition"]["first_player"] == "B"
        )
        checked = 0
        positions = [(row, column) for row in range(3) for column in range(3)]
        for pair in (pair_v3, pair_v4):
            source = parse_definition(pair["source_definition"])
            treatment = parse_definition(pair["treatment_definition"])
            ply = 1 if source.first_player is Player.A else 0
            for runner_position in positions:
                remaining = [position for position in positions if position != runner_position]
                for mask in range(1 << len(remaining)):
                    pieces = [InitialPiece(Player.B, "runner", runner_position)]
                    pieces.extend(
                        InitialPiece(Player.A, "seed", position)
                        for bit, position in enumerate(remaining)
                        if mask & (1 << bit)
                    )
                    state = GameState(
                        ply=ply,
                        to_move=Player.B,
                        pieces=tuple(sorted(pieces, key=lambda item: item.position)),
                    )
                    validate_capture_boundary_move_containment(source, treatment, state)
                    checked += 1
        self.assertEqual(checked, 2 * 9 * (2 ** 8))


if __name__ == "__main__":
    unittest.main()
