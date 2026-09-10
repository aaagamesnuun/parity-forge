import copy
import hashlib
import json
import unittest
from pathlib import Path
from unittest import mock

import parity_forge.two_runner as two_runner
from parity_forge.capture_boundary import (
    CAPTURE_BOUNDARY_LANDSCAPE_SOURCE,
    CAPTURE_BOUNDARY_PRIOR_SOURCES,
    project_boundary_definitions,
)
from parity_forge.dsl import canonical_json, parse_definition
from parity_forge.landscape import _canonical_orbit_representatives
from parity_forge.symmetry import canonicalize_d4, mechanical_json
from parity_forge.two_runner import (
    TWO_RUNNER_EVALUATED_D4_COUNT,
    TWO_RUNNER_GATE_VALID_D4_COUNT,
    TWO_RUNNER_PAIR_COUNT,
    TWO_RUNNER_RELEVANT_D4_COUNT,
    TWO_RUNNER_SOURCE_STATE_BOUND,
    TWO_RUNNER_STRATUM_COUNT,
    TWO_RUNNER_TREATMENT_STATE_BOUND,
    TWO_RUNNER_TREATMENT_UNIQUE_D4_COUNT,
    TWO_RUNNER_UNUSED_RELEVANT_D4_COUNT,
    build_two_runner_evaluated_orbit_projection,
    build_two_runner_closed_projection_bundle,
    build_two_runner_historical_definition_projection,
    build_two_runner_manifest,
    build_two_runner_planning_snapshot,
    derive_two_runner_treatment,
    revert_two_runner_pair,
    two_runner_added_position,
    two_runner_natural_terminal_ply_bound,
    two_runner_state_upper_bound,
    two_runner_stratum,
    validate_two_runner_d4_equivariance,
    validate_two_runner_closed_projection_bundle,
    validate_two_runner_evaluated_orbit_projection,
    validate_two_runner_historical_definition_projection,
    validate_two_runner_manifest,
    validate_two_runner_pair,
    validate_two_runner_searched_states,
)


REPOSITORY = Path(__file__).resolve().parents[1]
LEDGER_PATH = Path("experiments/corpora/capture-boundary-v1/exclusion-ledger.json")
PLAN0009_MANIFEST_PATH = Path(
    "experiments/corpora/capture-boundary-v1/manifest.json"
)


def _load(path):
    return json.loads((REPOSITORY / path).read_text(encoding="utf-8"))


def _canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _domain_digest(domain, value):
    return hashlib.sha256(domain + b"\0" + _canonical(value)).hexdigest()


def _provenance():
    return {
        "freezer_git_commit": "0" * 40,
        "freezer_git_dirty": False,
        "created_at": "2026-08-31T00:00:00Z",
        "protocol_id": two_runner.TWO_RUNNER_MANIFEST_PROTOCOL_ID,
        "protocol_plan": {
            "path": "docs/plans/active/0010-two-runner-existing-dsl-family-viability.md",
            "sha256": "1" * 64,
            "git_blob_sha": "2" * 40,
        },
        "protocol_fingerprints": {
            "docs/plans/active/0010-two-runner-existing-dsl-family-viability.md": "1"
            * 64,
        },
        "executable_fingerprints": {
            path: "3" * 64
            for path in two_runner.TWO_RUNNER_EXECUTABLE_FINGERPRINT_PATHS
        },
        "closed_projection_bundle": {
            "path": "experiments/corpora/two-runner-v1/exclusion-ledger.json",
            "bundle_root": two_runner.TWO_RUNNER_CLOSED_PROJECTION_BUNDLE_ROOT,
            "sha256": "4" * 64,
            "bytes": 1,
        },
        "plan0009_manifest_chain": [
            dict(record) for record in two_runner.TWO_RUNNER_PLAN0009_MANIFEST_CHAIN
        ],
        "selection_inputs": "authenticated-definition-projections-only",
        "independent_review": "PASSED",
    }


def _source(first_player="A"):
    return parse_definition(
        {
            "schema_version": 1,
            "name": "Two Runner Unit Fixture",
            "board_size": 3,
            "first_player": first_player,
            "max_plies": 18,
            "roles": {
                "A": {
                    "action": {"kind": "PLACE", "piece": "seed"},
                    "goal": {
                        "kind": "CONNECT_EDGES",
                        "piece": "seed",
                        "edges": ["TOP", "BOTTOM"],
                    },
                },
                "B": {
                    "action": {
                        "kind": "MOVE",
                        "piece": "runner",
                        "vectors": [[-1, 0], [0, 1], [1, 1]],
                    },
                    "goal": {
                        "kind": "REACH_EDGE",
                        "piece": "runner",
                        "edge": "TOP",
                    },
                },
            },
            "initial_pieces": [
                {"owner": "B", "piece": "runner", "position": [2, 0]}
            ],
        }
    )


class TwoRunnerTransformTests(unittest.TestCase):
    def test_one_variable_derivation_and_source_witnessed_reversion(self):
        source = _source()
        treatment = derive_two_runner_treatment(source)

        self.assertEqual(two_runner_added_position(source), (2, 2))
        self.assertEqual(
            [piece.position for piece in treatment.initial_pieces],
            [(2, 0), (2, 2)],
        )
        self.assertEqual(treatment.schema_version, source.schema_version)
        self.assertEqual(treatment.roles, source.roles)
        self.assertEqual(treatment.first_player, source.first_player)
        validate_two_runner_pair(source, treatment)
        restored = revert_two_runner_pair(source, treatment)
        self.assertEqual(canonical_json(restored), canonical_json(source))

        altered = treatment.to_dict()
        altered["roles"]["B"]["action"]["vectors"].append([1, 0])
        with self.assertRaises(ValueError):
            validate_two_runner_pair(source, altered)

    def test_derivation_and_reversion_commute_with_all_d4_transforms(self):
        validate_two_runner_d4_equivariance(_source())

    def test_same_frame_treatment_is_not_independently_canonicalized(self):
        source_hash = (
            "00a01fd914bb0cb882ec1dc31d595e9945324453dea44a357cc9a0653302a30f"
        )
        source = dict(_canonical_orbit_representatives())[source_hash]
        treatment = derive_two_runner_treatment(source)

        self.assertEqual(canonicalize_d4(treatment).transform, "R90")
        self.assertNotEqual(
            mechanical_json(treatment), canonicalize_d4(treatment).mechanical_json
        )
        canonical_treatment = parse_definition(
            json.loads(canonicalize_d4(treatment).mechanical_json)
            | {"name": treatment.name}
        )
        with self.assertRaises(ValueError):
            validate_two_runner_pair(source, canonical_treatment)

    def test_state_and_natural_termination_bounds_are_exact_and_typed(self):
        source_a = _source("A")
        source_b = _source("B")
        treatment_a = derive_two_runner_treatment(source_a)
        treatment_b = derive_two_runner_treatment(source_b)

        self.assertEqual(
            two_runner_state_upper_bound(source_a), TWO_RUNNER_SOURCE_STATE_BOUND
        )
        self.assertEqual(
            two_runner_state_upper_bound(treatment_a),
            TWO_RUNNER_TREATMENT_STATE_BOUND,
        )
        self.assertEqual(two_runner_natural_terminal_ply_bound(source_a), 15)
        self.assertEqual(two_runner_natural_terminal_ply_bound(source_b), 16)
        self.assertEqual(two_runner_natural_terminal_ply_bound(treatment_a), 13)
        self.assertEqual(two_runner_natural_terminal_ply_bound(treatment_b), 14)
        self.assertEqual(
            validate_two_runner_searched_states(69_120, treatment_a), 69_120
        )
        with self.assertRaises(ValueError):
            validate_two_runner_searched_states(True, treatment_a)
        with self.assertRaises(ValueError):
            validate_two_runner_searched_states(69_121, treatment_a)

    def test_strata_use_only_first_player_axis_relation_and_vector_band(self):
        self.assertEqual(
            two_runner_stratum(_source()),
            {
                "first_player": "A",
                "goal_axis_relation": "ALIGNED",
                "vector_band": "v1_3",
            },
        )


class TwoRunnerProductionCensusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ledger_bundle = _load(LEDGER_PATH)
        cls.coverage = ledger_bundle["coverage_projection"]
        cls.plan0009_manifest = _load(PLAN0009_MANIFEST_PATH)
        source_paths = [Path(path) for path, _ in CAPTURE_BOUNDARY_PRIOR_SOURCES]
        source_paths.append(Path(CAPTURE_BOUNDARY_LANDSCAPE_SOURCE[0]))
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
            _load(Path(metadata["path"]))
            for metadata in cls.supporting_dependency_metadata
        )
        cls.coverage_registry = tuple(
            {
                "path": record["path"],
                "sha256": record["sha256"],
            }
            for record in cls.coverage["records"]
        )
        cls.coverage_records = tuple(
            _load(Path(entry["path"])) for entry in cls.coverage_registry
        )
        cls.closed_inputs = {
            "source_records": cls.source_records,
            "source_metadata": cls.source_metadata,
            "supporting_dependency_records": cls.supporting_dependency_records,
            "supporting_dependency_metadata": cls.supporting_dependency_metadata,
            "coverage_records": cls.coverage_records,
            "coverage_registry": cls.coverage_registry,
            "plan0009_manifest": cls.plan0009_manifest,
        }
        cls.closed_bundle = build_two_runner_closed_projection_bundle(
            **cls.closed_inputs
        )
        cls.plan0009_source_projection = project_boundary_definitions(
            [pair["source_definition"] for pair in cls.plan0009_manifest["pairs"]]
        )
        cls.evaluated = cls.closed_bundle["evaluated_orbit_projection"]
        cls.historical = cls.closed_bundle["historical_definition_projection"]
        cls.dependencies = cls.evaluated["dependency_artifacts"]

        cls.synthetic_historical_source_projection = project_boundary_definitions(
            [_source().to_dict()]
        )
        cls.synthetic_historical_sources = [
            {
                "artifact": {
                    "path": "tests/closed-history-definition-projection.json",
                    "sha256": "0" * 64,
                    "identity_kind": "projection_id",
                    "identity": "two-runner-test-closed-history",
                },
                "definition_projection": cls.synthetic_historical_source_projection,
            }
        ]
        with mock.patch.object(
            two_runner, "TWO_RUNNER_HISTORICAL_PROJECTION_ROOT", ""
        ):
            cls.synthetic_historical = (
                build_two_runner_historical_definition_projection(
                    cls.synthetic_historical_sources
                )
            )
        cls.snapshot = build_two_runner_planning_snapshot(
            cls.evaluated, cls.historical
        )
        cls.frozen_roots = {
            "TWO_RUNNER_EVALUATED_PROJECTION_ROOT": cls.evaluated[
                "projection_root"
            ],
            "TWO_RUNNER_HISTORICAL_PROJECTION_ROOT": cls.historical[
                "projection_root"
            ],
            "TWO_RUNNER_RELEVANT_D4_ROOT": cls.snapshot[
                "relevant_source_d4_root"
            ],
            "TWO_RUNNER_REPRESENTATIVE_CHOICE_ROOT": cls.snapshot[
                "representative_choice_root"
            ],
            "TWO_RUNNER_ELIGIBLE_POOL_ROOT": cls.snapshot["eligible_pool_root"],
            "TWO_RUNNER_SELECTION_FINGERPRINT": cls.snapshot[
                "selection_fingerprint"
            ],
        }
        with mock.patch.multiple(two_runner, **cls.frozen_roots):
            cls.manifest = build_two_runner_manifest(
                cls.evaluated,
                cls.historical,
                _provenance(),
            )

    def _validate_manifest(self, value):
        with mock.patch.multiple(two_runner, **self.frozen_roots):
            return validate_two_runner_manifest(
                value, self.evaluated, self.historical
            )

    def _build_manifest(self, provenance=None):
        with mock.patch.multiple(two_runner, **self.frozen_roots):
            return build_two_runner_manifest(
                self.evaluated,
                self.historical,
                _provenance() if provenance is None else provenance,
            )

    def test_closed_evaluated_projection_is_439_plus_64_disjoint_orbits(self):
        self.assertEqual(self.evaluated["base_d4_count"], 439)
        self.assertEqual(self.evaluated["plan0009_source_d4_count"], 64)
        self.assertEqual(self.evaluated["intersection_count"], 0)
        self.assertEqual(
            self.evaluated["evaluated_d4_count"], TWO_RUNNER_EVALUATED_D4_COUNT
        )
        validate_two_runner_evaluated_orbit_projection(
            self.evaluated,
            self.coverage,
            self.plan0009_source_projection,
            dependency_artifacts=self.dependencies,
        )

        whole_manifest_projection = project_boundary_definitions(
            self.plan0009_manifest
        )
        with self.assertRaisesRegex(ValueError, "exactly 64"):
            build_two_runner_evaluated_orbit_projection(
                self.coverage,
                whole_manifest_projection,
                self.dependencies,
            )

    def test_closed_bundle_authenticates_the_fixed_graph_and_plan0009_sources(self):
        reconstructed = validate_two_runner_closed_projection_bundle(
            self.closed_bundle, **self.closed_inputs
        )
        self.assertEqual(
            reconstructed["evaluated_orbit_projection"], self.evaluated
        )
        self.assertEqual(
            reconstructed["historical_definition_projection"], self.historical
        )
        self.assertEqual(self.closed_bundle["historical_artifact_count"], 21)
        self.assertEqual(
            self.closed_bundle["historical_artifact_paths"][-1],
            "experiments/runs/20260830T230308952280Z-capture-stress-e4fc6e97/run.json",
        )
        self.assertIn(
            str(PLAN0009_MANIFEST_PATH),
            self.closed_bundle["historical_artifact_paths"],
        )
        self.assertEqual(
            self.closed_bundle["bundle_root"],
            "755b5a5d8ae35d8222873275e87860effbdf7ec2266de3799814d20385b12ca3",
        )
        self.assertEqual(
            self.evaluated["projection_root"],
            "7064501b4514b34420e6fe7f0d4927cb6b3fb84e8610cabb510f6265520471d6",
        )
        self.assertEqual(
            self.evaluated["evaluated_d4_root"],
            "0c83885bf5eb1e670327ae6618b67805ba3b023a4bab206e7d98d753544ff05a",
        )
        self.assertEqual(
            self.historical["projection_root"],
            "0a4a38245c3666f215041d10383112e65c82f40bc5d2f510df2d4418d65c2f91",
        )
        self.assertEqual(
            self.historical["unique_d4_root"],
            "9c8b2d54659c5021fbc47dfa38cb435ed068132e6e790e5057d86a13f93c07ba",
        )
        self.assertEqual(self.historical["definition_occurrence_count"], 2_115)
        self.assertEqual(self.historical["unique_definition_count"], 1_044)
        self.assertEqual(self.historical["unique_d4_count"], 1_040)

        static_record = next(
            record
            for record in self.historical["sources"]
            if record["artifact"]["path"]
            == "experiments/corpora/static-v1/corpus.json"
        )
        self.assertEqual(static_record["definition_occurrence_count"], 6)
        self.assertEqual(static_record["unique_definition_count"], 6)
        self.assertEqual(static_record["unique_d4_count"], 6)
        self.assertEqual(
            static_record["definition_projection_root"],
            "07a2436373ee4f15b88b9c5aec5757484d4ac3bb80e3b0dd99e7ebfc88489e3a",
        )
        self.assertEqual(
            static_record["unique_d4_root"],
            "b996b415f2bd1dceb100f249606896b4c4e64fa49046ac1a403aed898ca01d7c",
        )

        shortened = dict(self.closed_inputs)
        shortened["coverage_records"] = shortened["coverage_records"][:-1]
        with self.assertRaises(ValueError):
            build_two_runner_closed_projection_bundle(**shortened)

        altered = dict(self.closed_inputs)
        altered_manifest = copy.deepcopy(self.plan0009_manifest)
        altered_manifest["pairs"][0]["source_definition"]["name"] += " changed"
        altered["plan0009_manifest"] = altered_manifest
        with self.assertRaisesRegex(ValueError, "Plan-0009 manifest"):
            build_two_runner_closed_projection_bundle(**altered)

    def test_historical_projection_accepts_only_strict_definition_capabilities(self):
        with mock.patch.object(
            two_runner, "TWO_RUNNER_HISTORICAL_PROJECTION_ROOT", ""
        ):
            hashes = validate_two_runner_historical_definition_projection(
                self.synthetic_historical, self.synthetic_historical_sources
            )
        self.assertEqual(len(hashes), 1)
        poisoned = copy.deepcopy(self.synthetic_historical_sources[0])
        poisoned["outcome"] = "B_WIN"
        with mock.patch.object(
            two_runner, "TWO_RUNNER_HISTORICAL_PROJECTION_ROOT", ""
        ), self.assertRaises(ValueError):
            build_two_runner_historical_definition_projection([poisoned])

        full_record = {
            "run_id": "not-a-definition-projection",
            "status": "COMPLETED",
            "results": [],
        }
        with mock.patch.object(
            two_runner, "TWO_RUNNER_HISTORICAL_PROJECTION_ROOT", ""
        ), self.assertRaises(ValueError):
            build_two_runner_historical_definition_projection(
                [
                    {
                        "artifact": self.synthetic_historical_sources[0]["artifact"],
                        "definition_projection": full_record,
                    }
                ]
            )

    def test_planning_census_reproduces_all_registered_counts(self):
        census = self.snapshot["census"]
        self.assertEqual(census["relevant_source_d4_count"], TWO_RUNNER_RELEVANT_D4_COUNT)
        self.assertEqual(
            census["unused_relevant_source_d4_count"],
            TWO_RUNNER_UNUSED_RELEVANT_D4_COUNT,
        )
        self.assertEqual(
            census["paired_gate_valid_d4_count"],
            TWO_RUNNER_GATE_VALID_D4_COUNT,
        )
        self.assertEqual(census["source_treatment_gate_disagreement_count"], 59)
        self.assertEqual(census["source_fail_treatment_pass_count"], 59)
        self.assertEqual(census["source_pass_treatment_fail_count"], 0)
        self.assertEqual(census["both_gate_fail_count"], 110)
        self.assertEqual(
            census["treatment_unique_d4_count"],
            TWO_RUNNER_TREATMENT_UNIQUE_D4_COUNT,
        )
        self.assertEqual(census["treatment_singleton_count"], 216)
        self.assertEqual(census["treatment_double_count"], 261)
        self.assertEqual(census["minimum_eligible_stratum_count"], 19)
        self.assertEqual(census["maximum_eligible_stratum_count"], 36)
        self.assertEqual(census["stratum_count"], TWO_RUNNER_STRATUM_COUNT)
        self.assertEqual(census["pair_count"], TWO_RUNNER_PAIR_COUNT)
        self.assertEqual(census["historical_collision_count"], 0)
        self.assertEqual(census["d4_equivariance_check_count"], 8_128)
        self.assertEqual(
            {pool["stratum_id"]: pool["eligible_count"] for pool in self.snapshot["eligible_pools"]},
            {
                "fA-aligned-v1_3": 36,
                "fA-aligned-v4": 35,
                "fA-aligned-v5": 30,
                "fA-aligned-v6_7": 20,
                "fA-orthogonal-v1_3": 35,
                "fA-orthogonal-v4": 34,
                "fA-orthogonal-v5": 30,
                "fA-orthogonal-v6_7": 21,
                "fB-aligned-v1_3": 35,
                "fB-aligned-v4": 33,
                "fB-aligned-v5": 29,
                "fB-aligned-v6_7": 19,
                "fB-orthogonal-v1_3": 36,
                "fB-orthogonal-v4": 34,
                "fB-orthogonal-v5": 29,
                "fB-orthogonal-v6_7": 21,
            },
        )

    def test_selected_pairs_are_same_frame_unique_and_fresh(self):
        pairs = self.snapshot["pairs"]
        self.assertEqual(len(pairs), 64)
        self.assertEqual(len({pair["source_d4_canonical_hash"] for pair in pairs}), 64)
        self.assertEqual(len({pair["treatment_d4_canonical_hash"] for pair in pairs}), 64)
        historical = set(self.historical["unique_d4_hashes"])
        for pair in pairs:
            source = parse_definition(pair["source_definition"])
            treatment = parse_definition(pair["treatment_definition"])
            self.assertEqual(
                mechanical_json(source), canonicalize_d4(source).mechanical_json
            )
            validate_two_runner_pair(source, treatment)
            self.assertNotIn(pair["source_d4_canonical_hash"], historical)
            self.assertNotIn(pair["treatment_d4_canonical_hash"], historical)

    def test_duplicate_treatment_representative_is_chosen_before_score_order(self):
        treatment_d4 = (
            "000bf5812277edacbca970896a09be35655814972175bc75a05672a69381a34d"
        )
        expected_sources = [
            "51b3f5c91ffbab391de2b61edc7f6e85d77d1e8e3559e73aaeb86cf66e60780b",
            "6b9c2723ddea044255b5e3924f38f06d1c776d446a7132c95b30722a4f548331",
        ]
        choices = {
            choice["treatment_d4_canonical_hash"]: choice
            for choice in self.snapshot["representative_choices"]
        }
        self.assertEqual(
            choices[treatment_d4]["eligible_source_d4_canonical_hashes"],
            expected_sources,
        )
        self.assertEqual(
            choices[treatment_d4]["selected_source_d4_canonical_hash"],
            expected_sources[0],
        )

    def test_manifest_publicly_reconstructs_and_rejects_tampering(self):
        pairs = self._validate_manifest(self.manifest)
        self.assertEqual(len(pairs), TWO_RUNNER_PAIR_COUNT)
        self.assertEqual(
            self.manifest["source"]["closed_projection_bundle_root"],
            two_runner.TWO_RUNNER_CLOSED_PROJECTION_BUNDLE_ROOT,
        )
        round_tripped = json.loads(
            json.dumps(self.manifest, sort_keys=True, separators=(",", ":"))
        )
        self.assertEqual(len(self._validate_manifest(round_tripped)), TWO_RUNNER_PAIR_COUNT)
        second = self._build_manifest()
        self.assertEqual(self.manifest, second)

        detached = build_two_runner_planning_snapshot(
            self.evaluated, self.historical
        )
        detached["pairs"][0]["selection_rank"] = 999
        rebuilt = build_two_runner_planning_snapshot(
            self.evaluated, self.historical
        )
        self.assertEqual(rebuilt["pairs"][0]["selection_rank"], 0)

        altered = copy.deepcopy(self.manifest)
        altered["pairs"][0]["selection_rank"] = 1
        with self.assertRaises(ValueError):
            self._validate_manifest(altered)

        poisoned = copy.deepcopy(self.manifest)
        poisoned["provenance"]["winner"] = "B"
        with self.assertRaises(ValueError):
            self._validate_manifest(poisoned)

        mutations = (
            lambda value: value["provenance"].update(
                {"nested": {"result": "B_WIN"}}
            ),
            lambda value: value["pairs"][0].update({"elapsed_seconds": 0.1}),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                value = copy.deepcopy(self.manifest)
                mutation(value)
                with self.assertRaises(ValueError):
                    self._validate_manifest(value)

        typed_mutations = (
            lambda value: value.update({"manifest_version": True}),
            lambda value: value["census"].update({"pair_count": True}),
            lambda value: value["selection_protocol"].update(
                {"case_membership_outcome_fields_consulted": 0}
            ),
        )
        for mutation in typed_mutations:
            with self.subTest(mutation=mutation):
                value = copy.deepcopy(self.manifest)
                mutation(value)
                with self.assertRaises(ValueError):
                    self._validate_manifest(value)

        alternate_outcome_keys = ("treatment_outcome", "actual_outcome", "Outcome")
        for key in alternate_outcome_keys:
            with self.subTest(key=key):
                provenance = _provenance()
                provenance[key] = "B_WIN"
                with self.assertRaises(ValueError):
                    self._build_manifest(provenance)

        provenance_mutations = (
            lambda value: value.update({"freezer_git_dirty": 0}),
            lambda value: value["protocol_plan"].update({"sha256": "f" * 64}),
            lambda value: value["closed_projection_bundle"].update({"bytes": True}),
            lambda value: value["closed_projection_bundle"].update(
                {"bundle_root": "f" * 64}
            ),
            lambda value: value["plan0009_manifest_chain"][0].update(
                {"sha256": "f" * 64}
            ),
            lambda value: value["executable_fingerprints"].pop(
                two_runner.TWO_RUNNER_EXECUTABLE_FINGERPRINT_PATHS[0]
            ),
        )
        for mutation in provenance_mutations:
            with self.subTest(provenance_mutation=mutation):
                provenance = _provenance()
                mutation(provenance)
                with self.assertRaises(ValueError):
                    self._build_manifest(provenance)

    def test_manifest_build_is_disabled_if_any_root_is_not_frozen(self):
        for constant in self.frozen_roots:
            with self.subTest(constant=constant, failure="missing"), mock.patch.object(
                two_runner, constant, ""
            ), self.assertRaisesRegex(ValueError, "disabled until"):
                build_two_runner_manifest(
                    self.evaluated, self.historical, _provenance()
                )
            with self.subTest(constant=constant, failure="mismatch"), mock.patch.object(
                two_runner, constant, "f" * 64
            ), self.assertRaisesRegex(ValueError, "frozen"):
                build_two_runner_manifest(
                    self.evaluated, self.historical, _provenance()
                )

    def test_planning_and_manifest_builders_never_call_solver_or_play(self):
        with mock.patch(
            "parity_forge.solver.solve_game",
            side_effect=AssertionError("solver must remain unavailable"),
        ), mock.patch(
            "parity_forge.play.play_game",
            side_effect=AssertionError("play must remain unavailable"),
        ):
            snapshot = build_two_runner_planning_snapshot(
                self.evaluated, self.historical
            )
            manifest = self._build_manifest()
        self.assertEqual(len(snapshot["pairs"]), TWO_RUNNER_PAIR_COUNT)
        self.assertEqual(len(manifest["pairs"]), TWO_RUNNER_PAIR_COUNT)

    def test_projection_roots_reject_tampering_and_reconstruction_mismatch(self):
        altered = copy.deepcopy(self.evaluated)
        altered["evaluated_d4_hashes"][0] = "f" * 64
        with self.assertRaises(ValueError):
            validate_two_runner_evaluated_orbit_projection(altered)

        altered = copy.deepcopy(self.historical)
        altered["sources"][0]["definition_occurrence_count"] += 1
        with self.assertRaises(ValueError):
            validate_two_runner_historical_definition_projection(altered)

        resigned_evaluated = copy.deepcopy(self.evaluated)
        resigned_evaluated["evaluated_d4_hashes"][-1] = "f" * 64
        resigned_evaluated["evaluated_d4_root"] = _domain_digest(
            b"two-runner-v1-evaluated-orbits-v1",
            resigned_evaluated["evaluated_d4_hashes"],
        )
        unsigned = dict(resigned_evaluated)
        unsigned.pop("projection_root")
        resigned_evaluated["projection_root"] = _domain_digest(
            b"two-runner-v1-evaluated-projection-v1", unsigned
        )
        with mock.patch.object(
            two_runner, "TWO_RUNNER_EVALUATED_PROJECTION_ROOT", ""
        ), self.assertRaisesRegex(ValueError, "reconstruction"):
            validate_two_runner_evaluated_orbit_projection(
                resigned_evaluated,
                self.coverage,
                self.plan0009_source_projection,
                dependency_artifacts=self.dependencies,
            )

        resigned_bundle = copy.deepcopy(self.closed_bundle)
        resigned_historical = resigned_bundle["historical_definition_projection"]
        resigned_historical["unique_d4_hashes"][-1] = "f" * 64
        resigned_historical["unique_d4_root"] = _domain_digest(
            b"two-runner-v1-historical-d4-v1",
            resigned_historical["unique_d4_hashes"],
        )
        unsigned = dict(resigned_historical)
        unsigned.pop("projection_root")
        resigned_historical["projection_root"] = _domain_digest(
            b"two-runner-v1-historical-projection-v1", unsigned
        )
        unsigned_bundle = dict(resigned_bundle)
        unsigned_bundle.pop("bundle_root")
        resigned_bundle["bundle_root"] = _domain_digest(
            b"two-runner-v1-closed-projection-bundle-v1", unsigned_bundle
        )
        with mock.patch.multiple(
            two_runner,
            TWO_RUNNER_HISTORICAL_PROJECTION_ROOT="",
            TWO_RUNNER_CLOSED_PROJECTION_BUNDLE_ROOT="",
        ), self.assertRaisesRegex(ValueError, "reconstruction"):
            validate_two_runner_closed_projection_bundle(
                resigned_bundle, **self.closed_inputs
            )

    def test_frozen_selection_roots_fail_closed_when_pinned(self):
        constants = (
            "TWO_RUNNER_RELEVANT_D4_ROOT",
            "TWO_RUNNER_REPRESENTATIVE_CHOICE_ROOT",
            "TWO_RUNNER_ELIGIBLE_POOL_ROOT",
            "TWO_RUNNER_SELECTION_FINGERPRINT",
        )
        for constant in constants:
            with self.subTest(constant=constant), mock.patch.object(
                two_runner, constant, "f" * 64
            ):
                with self.assertRaisesRegex(ValueError, "frozen"):
                    build_two_runner_planning_snapshot(
                        self.evaluated, self.historical
                    )


if __name__ == "__main__":
    unittest.main()
