import ast
import copy
import hashlib
import json
import subprocess
import unittest
from collections import Counter
from pathlib import Path

import parity_forge.atlas_agent_benchmark as benchmark_module
import parity_forge.atlas_protocol as protocol_module
from parity_forge.atlas import (
    ATLAS_CANONICAL_SELECTION_SHA256_V1,
    ATLAS_COLLISION_ROOT_V1,
    ATLAS_FINAL_REGISTRY_ROOT_V1,
    ATLAS_HISTORY_BINDING_ROOT_V1,
    ATLAS_PAIRED_UNIVERSE_WITNESS_ROOT_V1,
    ATLAS_SEARCH_ENVELOPE_ROOT_V1,
    ATLAS_SELECTION_PARTITION_ROOT_V1,
    build_frozen_atlas_selection_snapshot_v1,
)
from parity_forge.atlas_history import (
    ATLAS_HISTORY_INVENTORY_V1,
    build_prior_gameplay_exposure_projection_v1,
    build_synthetic_fixture_exposure_projection_v1,
)
from parity_forge.atlas_protocol import (
    ATLAS_DEFINITION_ORIENTATION_COUNT_V1,
    ATLAS_DEVELOPMENT_DEFINITION_COUNT_V1,
    ATLAS_DEVELOPMENT_PAIR_COUNT_V1,
    ATLAS_EXACT_STATE_CAP_TOTAL_V1,
    ATLAS_MATCHED_START_BLOCK_COUNT_V1,
    ATLAS_PROTOCOL_CANONICAL_SHA256_V1,
    ATLAS_PROTOCOL_ROOT_V1,
    ATLAS_SAMPLED_GAME_COUNT_V1,
    ATLAS_SAMPLED_PROFILE_COUNT_V1,
    ATLAS_SAMPLED_ROLE_SLOT_COUNT_V1,
    ATLAS_TERMINAL_DEPTH1_NODE_CAP_TOTAL_V1,
    build_frozen_atlas_protocol_v1,
    canonical_frozen_atlas_protocol_json_v1,
    iter_frozen_atlas_game_schedule_v1,
    iter_frozen_atlas_game_schedule_from_protocol_v1,
    validate_frozen_atlas_protocol_v1,
)


def _nested_keys(value):
    if type(value) is dict:
        for key, child in value.items():
            yield key
            yield from _nested_keys(child)


def _nested_sha256_strings(value):
    if type(value) is dict:
        for child in value.values():
            yield from _nested_sha256_strings(child)
    elif type(value) is list:
        for child in value:
            yield from _nested_sha256_strings(child)
    elif (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    ):
        yield value
    elif type(value) is list:
        for child in value:
            yield from _nested_keys(child)


def _exact(status="COMPLETE", result="A_WIN", reason="GOAL"):
    if status != "COMPLETE":
        result = None
        reason = None
    return {
        "status": status,
        "forced_result": result,
        "terminal_reason": reason,
    }


def _sampled(
    *,
    status="COMPLETE",
    completed=128,
    a_wins=48,
    b_wins=48,
    draws=32,
):
    return {
        "status": status,
        "scheduled_games": 128,
        "completed_games": completed,
        "a_wins": a_wins,
        "b_wins": b_wins,
        "draws": draws,
    }


def _pair_record(index, assessment, stratum=None):
    return {
        "paired_mechanical_d4_identity": hashlib.sha256(
            "pair-{}".format(index).encode("ascii")
        ).hexdigest(),
        "paired_stratum_id": stratum or "stratum-{}".format(index % 4),
        "assessment": assessment,
    }


def _fraction(numerator, denominator):
    return protocol_module._defined_fraction_v1(
        numerator, denominator, "test inspection fraction"
    )


def _missing(reason="INCOMPLETE_TELEMETRY"):
    return protocol_module._missing_fraction_v1(reason)


def _inspection_pair(
    index,
    *,
    assessment=None,
    channel_statuses=None,
    exact_label=None,
    random_label=None,
    terminal_label=None,
    metrics=None,
):
    family = protocol_module.ATLAS_FAMILY_ORDER_V1[index // 24]
    statuses = channel_statuses or {
        "exact": "COMPLETE",
        "random": "COMPLETE",
        "terminal_depth1": "COMPLETE",
        "telemetry": "COMPLETE",
    }
    if assessment == "PAIR_FRONTIER_SIGNAL_V1":
        exact_label = exact_label or "FIRST_PLAYER_DOMINANT"
        random_label = random_label or "WEAK_BALANCE_SIGNAL_V1"
        terminal_label = terminal_label or "WEAK_BALANCE_SIGNAL_V1"
    elif assessment == "HORIZON_UNRESOLVED":
        exact_label = exact_label or "HORIZON_UNRESOLVED"
        random_label = random_label or "WEAK_BALANCE_SIGNAL_V1"
        terminal_label = terminal_label or "WEAK_BALANCE_SIGNAL_V1"
    else:
        exact_label = exact_label or "A_ROLE_DOMINANT"
        random_label = random_label or "WEAK_BALANCE_SIGNAL_V1"
        terminal_label = terminal_label or "WEAK_BALANCE_SIGNAL_V1"
    assessment = assessment or protocol_module._classify_atlas_pair_frontier_v1(
        exact_label, random_label, terminal_label
    )
    default_metrics = {
        "exact_state_utilization": _fraction(index % 17, 17),
        "strength_role_share_gap": _fraction(index % 11, 11),
        "d4_outcome_range": {
            "random-v1-weak": _fraction(index % 7, 7),
            "terminal_only_minimax-v1-depth1": _fraction(index % 5, 5),
        },
        "depth1_ply_limit_rate": _fraction(index % 9, 9),
        "forced_decision_fraction": {
            "A": _fraction(index % 13, 13),
            "B": _fraction(index % 3, 3),
        },
        "depth1_reciprocal_dependency_fraction": _fraction(index % 8, 8),
    }
    return {
        "pair_index": index,
        "paired_mechanical_d4_identity": hashlib.sha256(
            "inspection-pair-{}".format(index).encode("ascii")
        ).hexdigest(),
        "family_id": family,
        "paired_stratum_id": "inspection-stratum-{:02d}".format(index % 44),
        "channel_statuses": statuses,
        "exact_label": exact_label,
        "random_label": random_label,
        "terminal_depth1_label": terminal_label,
        "pair_assessment": assessment,
        "metrics": metrics or default_metrics,
    }


class AtlasProtocolFrozenScheduleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repository = Path(__file__).resolve().parents[1]
        raw_history = {
            source_path: (repository / source_path).read_bytes()
            for source_path, _digest, _byte_count in ATLAS_HISTORY_INVENTORY_V1
        }
        prior = build_prior_gameplay_exposure_projection_v1(raw_history)
        synthetic = build_synthetic_fixture_exposure_projection_v1()
        cls.selection = build_frozen_atlas_selection_snapshot_v1(prior, synthetic)
        cls.protocol = build_frozen_atlas_protocol_v1(cls.selection)

    def test_protocol_binds_reviewed_sources_without_an_outcome(self):
        protocol = self.protocol
        self.assertEqual(protocol["status"], "OUTCOME_FREE_EVALUATION_PROTOCOL")
        self.assertEqual(
            protocol["upstream"]["selector_roots"]["ordered_registry_root"],
            ATLAS_FINAL_REGISTRY_ROOT_V1,
        )
        self.assertEqual(
            protocol["upstream"]["selector_roots"]["search_envelope_root"],
            ATLAS_SEARCH_ENVELOPE_ROOT_V1,
        )
        self.assertEqual(
            protocol["upstream"]["selector_roots"][
                "paired_universe_witness_root"
            ],
            ATLAS_PAIRED_UNIVERSE_WITNESS_ROOT_V1,
        )
        self.assertEqual(
            protocol["upstream"]["selector_roots"]["history_binding_root"],
            ATLAS_HISTORY_BINDING_ROOT_V1,
        )
        self.assertEqual(
            protocol["upstream"]["selector_roots"]["collision_root"],
            ATLAS_COLLISION_ROOT_V1,
        )
        self.assertEqual(
            protocol["upstream"]["selector_roots"]["selection_partition_root"],
            ATLAS_SELECTION_PARTITION_ROOT_V1,
        )
        self.assertEqual(
            protocol["upstream"]["selector_roots"][
                "selection_canonical_sha256"
            ],
            ATLAS_CANONICAL_SELECTION_SHA256_V1,
        )
        boundary = protocol["capability_boundary"]
        self.assertEqual(boundary["development_definition_body_emitted_count"], 0)
        self.assertEqual(boundary["candidate_definition_emitted_count"], 0)
        self.assertEqual(boundary["candidate_definition_scheduled_count"], 0)
        self.assertEqual(boundary["candidate_definition_evaluated_count"], 0)
        self.assertEqual(boundary["candidate_outcome_count"], 0)
        self.assertEqual(boundary["development_outcome_count"], 0)
        self.assertEqual(boundary["outcome_producing_call_count"], 0)

    def test_complete_schedule_counts_caps_and_phase_order_are_frozen(self):
        schedule = self.protocol["schedule"]
        cardinality = schedule["cardinality"]
        self.assertEqual(
            cardinality["development_pair_count"],
            ATLAS_DEVELOPMENT_PAIR_COUNT_V1,
        )
        self.assertEqual(
            cardinality["exact_definition_slot_count"],
            ATLAS_DEVELOPMENT_DEFINITION_COUNT_V1,
        )
        self.assertEqual(
            cardinality["definition_orientation_slot_count"],
            ATLAS_DEFINITION_ORIENTATION_COUNT_V1,
        )
        self.assertEqual(
            cardinality["sampled_profile_slot_count"],
            ATLAS_SAMPLED_PROFILE_COUNT_V1,
        )
        self.assertEqual(
            cardinality["sampled_role_slot_count"],
            ATLAS_SAMPLED_ROLE_SLOT_COUNT_V1,
        )
        self.assertEqual(
            cardinality["sampled_game_slot_count"],
            ATLAS_SAMPLED_GAME_COUNT_V1,
        )
        self.assertEqual(
            cardinality["matched_start_block_count"],
            ATLAS_MATCHED_START_BLOCK_COUNT_V1,
        )
        self.assertEqual(schedule["exact_state_cap_total"], 19_722_000)
        self.assertEqual(
            schedule["exact_state_action_candidate_cap_total"], 592_781_760
        )
        self.assertEqual(
            schedule["terminal_depth1_node_cap_total"],
            ATLAS_TERMINAL_DEPTH1_NODE_CAP_TOTAL_V1,
        )
        self.assertEqual(schedule["sampled_ply_cap_total"], 663_552)
        self.assertEqual(
            schedule["strength_phase_seal_order"],
            ["random-v1-weak", "terminal_only_minimax-v1-depth1"],
        )
        self.assertEqual(
            self.protocol["sampled_protocol"]["stronger_route"]["status"],
            "NO_STRONGER_STAGE_AUTHORIZED_V1",
        )

    def test_exact_and_orientation_slots_bind_full_identity_and_individual_caps(self):
        exact = self.protocol["schedule"]["exact_slots"]
        orientations = self.protocol["schedule"]["orientation_slots"]
        self.assertEqual(len(exact), ATLAS_DEVELOPMENT_DEFINITION_COUNT_V1)
        self.assertEqual(len(orientations), ATLAS_DEFINITION_ORIENTATION_COUNT_V1)
        self.assertEqual(
            [slot["definition_index"] for slot in exact],
            list(range(ATLAS_DEVELOPMENT_DEFINITION_COUNT_V1)),
        )
        self.assertEqual(sum(slot["max_states"] for slot in exact), 19_722_000)
        self.assertEqual(
            sum(
                slot["max_state_action_candidate_evaluations"] for slot in exact
            ),
            592_781_760,
        )
        self.assertTrue(
            all(
                slot["max_state_action_candidate_evaluations"]
                == slot["max_states"] * slot["max_action_candidates_per_state"]
                for slot in exact
            )
        )
        self.assertEqual(
            Counter(slot["max_states"] for slot in exact),
            {31_920: 144, 67_032: 96, 181_051: 48},
        )
        self.assertEqual(
            Counter(slot["member"] for slot in exact),
            {"A_FIRST": 144, "B_FIRST": 144},
        )
        self.assertTrue(all(slot["goal_frame"] for slot in exact))
        self.assertTrue(
            all(set(slot["vector_profiles"]) == {"A", "B"} for slot in exact)
        )
        self.assertEqual(len({slot["slot_id"] for slot in exact}), len(exact))
        self.assertEqual(
            len({slot["slot_id"] for slot in orientations}), len(orientations)
        )
        self.assertTrue(
            all(
                slot["first_duplicate_transform_index"]
                <= slot["transform_index"]
                for slot in orientations
            )
        )

    def test_game_iterator_reconstructs_profiles_roles_and_matched_blocks(self):
        games = list(iter_frozen_atlas_game_schedule_from_protocol_v1(self.protocol))
        self.assertEqual(len(games), ATLAS_SAMPLED_GAME_COUNT_V1)
        self.assertEqual(len({game["slot_id"] for game in games}), len(games))
        self.assertEqual(
            Counter(game["strength"]["identity"] for game in games),
            {"random-v1-weak": 18_432, "terminal_only_minimax-v1-depth1": 18_432},
        )
        self.assertEqual(
            len({game["profile_slot_id"] for game in games}),
            ATLAS_SAMPLED_PROFILE_COUNT_V1,
        )
        self.assertEqual(
            len(
                {
                    role_slot_id
                    for game in games
                    for role_slot_id in game["ordered_role_slot_ids"]
                }
            ),
            ATLAS_SAMPLED_ROLE_SLOT_COUNT_V1,
        )
        blocks = Counter(game["matched_start_block_id"] for game in games)
        self.assertEqual(len(blocks), ATLAS_MATCHED_START_BLOCK_COUNT_V1)
        self.assertEqual(set(blocks.values()), {2})
        first_strength_two = games[18_432]["strength"]["identity"]
        self.assertEqual(first_strength_two, "terminal_only_minimax-v1-depth1")

    def test_protocol_does_not_emit_candidate_or_definition_bodies(self):
        encoded = json.dumps(self.protocol, sort_keys=True, separators=(",", ":"))
        self.assertNotIn("representative_definition", set(_nested_keys(self.protocol)))
        candidate_identities = set()
        for pair in self.selection["confirmation_candidate_pairs"]:
            candidate_identities.add(pair["paired_mechanical_d4_identity"])
            for member in pair["members"].values():
                candidate_identities.add(member["representative_definition_hash"])
                candidate_identities.add(member["d4_canonical_hash"])
                candidate_identities.update(
                    member["representative_d4_slot_definition_hashes"]
                )
        development_hashes = set(
            _nested_sha256_strings(self.selection["development_pairs"])
        )
        candidate_unique_hashes = set(
            _nested_sha256_strings(self.selection["confirmation_candidate_pairs"])
        ).difference(development_hashes)
        candidate_identities.update(candidate_unique_hashes)
        self.assertFalse(any(identity in encoded for identity in candidate_identities))

    def test_cached_schedule_columns_are_resealed_against_stored_and_fixed_roots(self):
        selection_json = protocol_module._canonical_bytes(self.selection).decode(
            "utf-8"
        )
        context = protocol_module._cached_schedule_context(selection_json)
        columns = (
            "exact",
            "orientations",
            "profiles",
            "roles",
            "games",
            "blocks",
        )
        for column in columns:
            with self.subTest(column=column):
                original = context[column][0]
                poisoned = dict(original)
                poisoned["cache_poison"] = column
                context[column][0] = poisoned
                with self.assertRaises(ValueError):
                    protocol_module._require_frozen_context_roots(context)
                context[column][0] = original

        saved_exact_root = context["roots"]["exact"]
        context["roots"]["exact"] = {
            **saved_exact_root,
            "count": True,
        }
        with self.assertRaises(ValueError):
            protocol_module._require_frozen_context_roots(context)
        context["roots"]["exact"] = saved_exact_root

        original_exact = context["exact"][0]
        context["exact"][0] = {**original_exact, "cache_poison": "re-signed"}
        context["roots"]["exact"] = protocol_module._ordered_record_root(
            "exact", context["exact"]
        )
        with self.assertRaises(ValueError):
            protocol_module._require_frozen_context_roots(context)
        context["exact"][0] = original_exact
        context["roots"]["exact"] = saved_exact_root
        protocol_module._require_frozen_context_roots(context)

    def test_poisoned_cache_rejects_then_reconstructs_for_iterator_and_build(self):
        selection_json = protocol_module._canonical_bytes(self.selection).decode(
            "utf-8"
        )
        context = protocol_module._cached_schedule_context(selection_json)
        context["games"][0] = {**context["games"][0], "seed": 99}
        with self.assertRaises(ValueError):
            protocol_module.iter_frozen_atlas_exact_schedule_v1(self.selection)

        first_game = next(iter_frozen_atlas_game_schedule_v1(self.selection))
        self.assertEqual(first_game["seed"], 0)

        rebuilt_context = protocol_module._cached_schedule_context(selection_json)
        rebuilt_context["blocks"][0] = {
            **rebuilt_context["blocks"][0],
            "cache_poison": "build",
        }
        with self.assertRaises(ValueError):
            build_frozen_atlas_protocol_v1(self.selection)
        rebuilt_protocol = build_frozen_atlas_protocol_v1(self.selection)
        self.assertEqual(rebuilt_protocol["protocol_root"], ATLAS_PROTOCOL_ROOT_V1)

    def test_all_public_schedule_iterators_enter_the_checked_context_boundary(self):
        tree = ast.parse(Path(protocol_module.__file__).read_text())
        expected = {
            "iter_frozen_atlas_exact_schedule_v1",
            "iter_frozen_atlas_orientation_schedule_v1",
            "iter_frozen_atlas_profile_schedule_v1",
            "iter_frozen_atlas_role_schedule_v1",
            "iter_frozen_atlas_game_schedule_v1",
            "iter_frozen_atlas_matched_start_blocks_v1",
        }
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name in expected
        }
        self.assertEqual(set(functions), expected)
        for name, function in functions.items():
            with self.subTest(iterator=name):
                context_calls = [
                    node
                    for node in ast.walk(function)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "_context_from_frozen_selection"
                ]
                self.assertEqual(len(context_calls), 1)

        protocol_expected = {
            "iter_frozen_atlas_exact_schedule_from_protocol_v1",
            "iter_frozen_atlas_orientation_schedule_from_protocol_v1",
            "iter_frozen_atlas_profile_schedule_from_protocol_v1",
            "iter_frozen_atlas_role_schedule_from_protocol_v1",
            "iter_frozen_atlas_game_schedule_from_protocol_v1",
            "iter_frozen_atlas_matched_start_blocks_from_protocol_v1",
        }
        protocol_functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name in protocol_expected
        }
        self.assertEqual(set(protocol_functions), protocol_expected)
        for name, function in protocol_functions.items():
            with self.subTest(protocol_iterator=name):
                context_calls = [
                    node
                    for node in ast.walk(function)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "_context_from_frozen_protocol"
                ]
                self.assertEqual(len(context_calls), 1)

        build_function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_build_protocol_value"
        )
        checked_calls = [
            node
            for node in ast.walk(build_function)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_checked_schedule_context"
        ]
        self.assertEqual(len(checked_calls), 1)

    def test_roots_canonical_bytes_validation_and_mutation_isolation(self):
        canonical = canonical_frozen_atlas_protocol_json_v1(
            self.selection, self.protocol
        )
        self.assertEqual(
            hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            ATLAS_PROTOCOL_CANONICAL_SHA256_V1,
        )
        self.assertEqual(self.protocol["protocol_root"], ATLAS_PROTOCOL_ROOT_V1)
        validate_frozen_atlas_protocol_v1(self.protocol, self.selection)

        changed = build_frozen_atlas_protocol_v1(self.selection)
        changed["status"] = "MUTATED"
        rebuilt = build_frozen_atlas_protocol_v1(self.selection)
        self.assertEqual(rebuilt["status"], "OUTCOME_FREE_EVALUATION_PROTOCOL")

    def test_validator_rejects_tamper_inner_resign_and_selection_drift(self):
        tampered = copy.deepcopy(self.protocol)
        tampered["assessment_protocol"]["family_frontier_rule"][
            "minimum_pair_frontier_count"
        ] = 1
        tampered["assessment_protocol"]["assessment_root"] = (
            protocol_module._digest(
                protocol_module._ASSESSMENT_ROOT_DOMAIN_V1,
                {
                    key: value
                    for key, value in tampered["assessment_protocol"].items()
                    if key != "assessment_root"
                },
            )
        )
        unsigned = dict(tampered)
        unsigned.pop("protocol_root")
        tampered["protocol_root"] = protocol_module._digest(
            protocol_module._PROTOCOL_ROOT_DOMAIN_V1, unsigned
        )
        with self.assertRaises(ValueError):
            validate_frozen_atlas_protocol_v1(tampered, self.selection)

        changed_selection = copy.deepcopy(self.selection)
        changed_selection["selection_partition_root"] = "0" * 64
        with self.assertRaises(ValueError):
            build_frozen_atlas_protocol_v1(changed_selection)

    def test_hostile_protocol_inputs_fail_before_reconstruction(self):
        cyclic = {}
        cyclic["self"] = cyclic
        with self.assertRaises(ValueError):
            validate_frozen_atlas_protocol_v1(cyclic, self.selection)

        too_deep = None
        for _ in range(60):
            too_deep = [too_deep]
        with self.assertRaises(ValueError):
            validate_frozen_atlas_protocol_v1(too_deep, self.selection)

        with self.assertRaises(ValueError):
            validate_frozen_atlas_protocol_v1({"integer": 1 << 200}, self.selection)

    def test_protocol_module_has_no_outcome_capability_import(self):
        source_path = Path(protocol_module.__file__)
        tree = ast.parse(source_path.read_text())
        forbidden = {
            "agency",
            "agents",
            "engine",
            "experiments",
            "play",
            "solver",
            "terminal_search",
        }
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.rsplit(".", 1)[-1] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.rsplit(".", 1)[-1])
        self.assertFalse(imported.intersection(forbidden))

    def test_checkpoint_closures_include_package_initializer_and_local_import_graph(self):
        repository = Path(__file__).resolve().parents[1]
        upstream = self.protocol["upstream"]
        self.assertEqual(
            upstream["selector_commit"],
            "5bce4c031ee674b8a95f7b786ad46d77a3a75161",
        )
        self.assertEqual(
            upstream["selector_tree"],
            "3b136ef38fc2752b20596fde13bd223ecba347b6",
        )
        self.assertEqual(
            upstream["evaluator_commit"],
            "d34c383ea68d5356972c15073090f518ba842cfd",
        )
        self.assertEqual(
            upstream["evaluator_tree"],
            "0cc614e1992029177a504a186b050b8c1635afb0",
        )
        checkpoints = (
            (
                "selector_closure_paths",
                upstream["selector_commit"],
                upstream["selector_tree"],
            ),
            (
                "evaluator_closure_paths",
                upstream["evaluator_commit"],
                upstream["evaluator_tree"],
            ),
        )
        for _closure_key, commit, expected_tree in checkpoints:
            observed_tree = subprocess.run(
                ["git", "rev-parse", "{}^{{tree}}".format(commit)],
                cwd=repository,
                shell=False,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            self.assertEqual(observed_tree, expected_tree)

        ancestry = subprocess.run(
            [
                "git",
                "merge-base",
                "--is-ancestor",
                upstream["selector_commit"],
                upstream["evaluator_commit"],
            ],
            cwd=repository,
            shell=False,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(
            upstream["selector_commit"], upstream["evaluator_commit"]
        )
        self.assertEqual(
            ancestry.returncode,
            0,
            "selector checkpoint must be a strict ancestor of evaluator checkpoint",
        )

        for closure_key, commit, _expected_tree in checkpoints:
            with self.subTest(closure=closure_key):
                closure = set(upstream[closure_key])
                self.assertIn("src/parity_forge/__init__.py", closure)
                for relative_path in closure:
                    source_path = repository / relative_path
                    self.assertTrue(source_path.is_file())
                    pinned_blob = subprocess.run(
                        ["git", "rev-parse", "{}:{}".format(commit, relative_path)],
                        cwd=repository,
                        shell=False,
                        check=True,
                        capture_output=True,
                        text=True,
                    ).stdout.strip()
                    current_blob = subprocess.run(
                        ["git", "hash-object", relative_path],
                        cwd=repository,
                        shell=False,
                        check=True,
                        capture_output=True,
                        text=True,
                    ).stdout.strip()
                    self.assertEqual(
                        current_blob,
                        pinned_blob,
                        "{} differs from pinned checkpoint {}".format(
                            relative_path, commit
                        ),
                    )
                    source_tree = ast.parse(source_path.read_text())
                    for node in ast.walk(source_tree):
                        if (
                            isinstance(node, ast.ImportFrom)
                            and node.level == 1
                            and node.module
                        ):
                            imported_module = node.module.split(".", 1)[0]
                            dependency = "src/parity_forge/{}.py".format(
                                imported_module
                            )
                            if (repository / dependency).is_file():
                                self.assertIn(
                                    dependency,
                                    closure,
                                    "{} omits local import {} from {}".format(
                                        closure_key, dependency, relative_path
                                    ),
                                )

    def test_stage_reservation_retry_and_resume_boundaries_are_frozen(self):
        provenance = self.protocol["manifest_and_run_provenance"]
        self.assertEqual(provenance["evidence_protocol_version"], 2)
        self.assertEqual(
            provenance["evidence_protocol_id"],
            "plan0013-atlas-development-evidence-v2",
        )
        self.assertEqual(
            provenance["evidence_store_relative_path"],
            "experiments/runs/plan0013-atlas-development-evidence-v2",
        )
        unsigned = dict(provenance)
        root = unsigned.pop("execution_evidence_root")
        self.assertEqual(
            root,
            protocol_module._digest(
                protocol_module._EXECUTION_EVIDENCE_ROOT_DOMAIN_V1, unsigned
            ),
        )
        self.assertEqual(
            provenance["candidate_block_access"]["evaluation"], "FORBIDDEN"
        )
        self.assertEqual(
            provenance["candidate_block_access"][
                "protocol_and_manifest_canonical_validation_read"
            ],
            "ALLOWED",
        )
        reservation = provenance["reservation_contract"]
        self.assertEqual(reservation["maximum_reservations_per_stage_protocol_id"], 1)
        self.assertIn("MUST-BE-RECOVERY-SEALED", reservation["orphan_reservation"])
        self.assertEqual(
            reservation["orphan_recovery"]["deterministic_precedence"][-1]["action"],
            "WRITE-ONE-IMMUTABLE-STAGE_ORPHANED_ID-AND-ORPHANED-TERMINAL-SEAL",
        )
        self.assertIn("blocked", reservation["required_prior_evidence_scan"])
        self.assertIn(
            ["blocked", "terminal-seal-BLOCKED"],
            provenance["artifact_contract"]["exclusive_lifecycles"],
        )
        self.assertIn(
            "ORPHANED",
            provenance["artifact_identity_schemas"]["stage_terminal_seal"][
                "lifecycle_values"
            ],
        )
        self.assertIn(
            "nonnull",
            provenance["artifact_identity_schemas"]["stage_orphaned_id"][
                "partial_evidence_stage_policy"
            ]["EXACT_ALL_288"],
        )
        retry = provenance["retry_and_resume_contract"]
        self.assertEqual(
            retry["pre_reservation_failure"],
            "RETRY_ALLOWED_AFTER_SAFE_CORRECTION",
        )
        self.assertEqual(
            retry["post_reservation_same_protocol_retry"], "FORBIDDEN"
        )
        self.assertEqual(retry["post_reservation_resume"], "FORBIDDEN_V1")

        schemas = provenance["artifact_identity_schemas"]
        domains = {
            "production_closure_root": (
                protocol_module._PRODUCTION_CLOSURE_ROOT_DOMAIN_V1
            ),
            "stage_reservation_id": protocol_module._STAGE_RESERVATION_ID_DOMAIN_V1,
            "stage_attempt_id": protocol_module._STAGE_ATTEMPT_ID_DOMAIN_V1,
            "stage_blocked_id": protocol_module._STAGE_BLOCKED_ID_DOMAIN_V1,
            "stage_orphaned_id": protocol_module._STAGE_ORPHANED_ID_DOMAIN_V1,
            "stage_terminal_seal": protocol_module._STAGE_TERMINAL_SEAL_DOMAIN_V1,
        }
        for schema_name, domain in domains.items():
            with self.subTest(identity_schema=schema_name):
                self.assertEqual(schemas[schema_name]["domain_hex"], domain.hex())
                self.assertEqual(
                    schemas[schema_name]["payload_keys"],
                    sorted(schemas[schema_name]["payload_keys"]),
                )
        self.assertEqual(
            schemas["production_closure_root"]["ordered_file_record_keys"],
            sorted(schemas["production_closure_root"]["ordered_file_record_keys"]),
        )

        stages = provenance["stages"]
        self.assertEqual(
            [stage["stage_index"] for stage in stages], list(range(len(stages)))
        )
        self.assertEqual(
            [stage["stage_id"] for stage in stages], self.protocol["stage_sequence"]
        )
        self.assertEqual(
            len({stage["stage_protocol_id"] for stage in stages}), len(stages)
        )
        self.assertTrue(
            all(stage["resume_policy"] == "NO_RESUME_V1" for stage in stages)
        )
        random_stage = stages[2]
        depth1_stage = stages[3]
        self.assertEqual(
            random_stage["reservation_scope"],
            "ALL_18432_RANDOM_GAME_SLOTS",
        )
        self.assertEqual(
            depth1_stage["prerequisite_stage_id"],
            "RANDOM_ALL_18432_GAMES",
        )
        self.assertEqual(random_stage["scheduled_game_count"], 18_432)
        self.assertEqual(depth1_stage["scheduled_game_count"], 18_432)
        self.assertIn("TERMINAL-SEALS", stages[4]["prerequisite_gate"])
        self.assertIn("TERMINAL-SEALS", stages[5]["prerequisite_gate"])
        self.assertIn(
            "AFTER_COMPLETE_CANDIDATE_NEUTRAL_BOOTSTRAP",
            stages[0]["reservation_timing"],
        )
        self.assertIn(
            "BEFORE_FIRST-DEFINITION-BODY-EXPORT",
            stages[0]["reservation_timing"],
        )
        self.assertEqual(stages[0]["required_parent_terminal_stage_ids"], [])
        self.assertEqual(
            stages[4]["required_parent_terminal_stage_ids"],
            [stage["stage_id"] for stage in stages[:4]],
        )
        self.assertEqual(
            stages[5]["required_parent_terminal_stage_ids"],
            [stage["stage_id"] for stage in stages[:5]],
        )
        for stage in stages:
            self.assertEqual(
                set(stage["required_parent_terminal_predicates"]),
                set(stage["required_parent_terminal_stage_ids"]),
            )
        for stage in stages:
            closure = stage["source_closure_policy"]
            self.assertEqual(closure["stage_id"], stage["stage_id"])
            self.assertFalse(
                set(closure["required_known_paths"]).intersection(
                    closure["forbidden_known_paths"]
                )
            )
            checkpoint = closure["checkpoint_blob_equivalence"]
            self.assertTrue(
                set(checkpoint["paths"]).issubset(
                    closure["required_known_paths"]
                )
            )
            self.assertNotIn(
                "src/parity_forge/atlas_protocol.py", checkpoint["paths"]
            )
        self.assertEqual(
            stages[0]["source_closure_policy"]["protocol_blob_binding"],
            "freeze-current-atlas_protocol.py-blob-in-bootstrap-and-completed-"
            "manifest-copy",
        )
        self.assertTrue(
            all(
                stage["source_closure_policy"]["protocol_blob_binding"]
                == "require-byte-identity-with-bootstrap-frozen-atlas_protocol.py-blob"
                for stage in stages[1:]
            )
        )
        self.assertTrue(
            all(
                stage["source_closure_policy"][
                    "concrete_entrypoint_and_recursive_imports_must_be_bootstrap_frozen"
                ]
                for stage in stages
            )
        )
        self.assertIn(
            "before-manifest-reservation",
            provenance["production_source_binding"]["future_stage_modules"],
        )
        plan_freeze = provenance["production_source_binding"][
            "experiment_plan_freeze"
        ]
        self.assertEqual(
            plan_freeze["downstream_input"], "bootstrap-frozen-artifact-only"
        )
        self.assertIn(
            "only-from-the-authenticated-pre-reservation-bootstrap",
            plan_freeze["manifest_crash_recovery"],
        )
        self.assertIn("never-runner-input", plan_freeze["live_document_after_manifest"])
        relations = provenance["production_source_binding"][
            "required_clean_commit_relations"
        ]
        self.assertIn("frozen-evaluator-d34c383", relations[0])

        bootstrap = provenance["outcome_free_manifest_bootstrap"]
        self.assertIn("before-manifest-stage-reservation", bootstrap["publication_order"])
        self.assertIn("partial-bootstrap-grants-no-stage-capability", bootstrap["crash_policy"])
        self.assertEqual(
            bootstrap["identity_schema"]["domain_hex"],
            protocol_module._MANIFEST_BOOTSTRAP_ROOT_DOMAIN_V1.hex(),
        )
        self.assertEqual(
            bootstrap["identity_schema"]["payload_keys"],
            sorted(bootstrap["identity_schema"]["payload_keys"]),
        )
        self.assertIn(
            "fixed-recursive-parent-chain",
            provenance["reservation_contract"]["orphan_recovery"][
                "bootstrap_authentication_gate"
            ],
        )
        completion_gates = provenance["artifact_contract"][
            "completed_ledger_revalidation"
        ]
        self.assertTrue(
            completion_gates["recovery_and_downstream_gate_use_same_validator"]
        )
        self.assertIn(
            "exact:288-COMPLETE",
            completion_gates["stage_status_gates"]["EXACT_ALL_288"],
        )
        self.assertIn(
            "INVALID-PROOF_CONTRADICTION-and-BLOCKED-forbidden",
            completion_gates["stage_status_gates"]
            ["REPLAY_TELEMETRY_COMPLETE_TRACES_ONLY"],
        )
        assessment_revalidation = provenance["artifact_contract"][
            "completed_assessment_summary_revalidation"
        ]
        self.assertEqual(
            assessment_revalidation["trigger"],
            "assessment-completed-body-already-present",
        )
        self.assertIn(
            "without-reading-raw-outcomes",
            assessment_revalidation["manifest_unavailable_path"],
        )
        self.assertEqual(
            assessment_revalidation["mismatch_policy"],
            "IMMUTABLE-EXTERNAL-CONTRADICTION-FAIL-CLOSED",
        )

        meta = self.protocol["assessment_protocol"][
            "manifest_unavailable_meta_report"
        ]
        self.assertEqual(meta["raw_parent_result_read_count"], 0)
        self.assertEqual(meta["gameplay_outcome_record_count"], 0)
        self.assertEqual(meta["candidate_definition_read_or_export_count"], 0)
        self.assertEqual(
            meta["status"], "EXPERIMENT_INVALID_BEFORE_DEVELOPMENT_OUTCOMES"
        )

        join = self.protocol["assessment_protocol"][
            "formal_reconstruction_boundary"
        ]["status_ledger_join"]
        self.assertIn("2304", join["exact_pv_replay"])
        self.assertIn("36864", join["telemetry"])
        self.assertEqual(
            join["exact_pv_replay_statuses"],
            [
                "VALID",
                "INCOMPLETE",
                "INVALID",
                "PROOF_CONTRADICTION",
                "NOT_RUN",
                "BLOCKED",
            ],
        )
        self.assertIn("PROOF_CONTRADICTION", join["telemetry_slot_statuses"])
        self.assertIn(
            "proof_contradiction_traces",
            self.protocol["assessment_protocol"]["assessment_reporting"][
                "count_fields"
            ]["telemetry"],
        )
        self.assertIn(
            "blocked_traces",
            self.protocol["assessment_protocol"]["assessment_reporting"][
                "count_fields"
            ]["telemetry"],
        )
        self.assertEqual(
            self.protocol["assessment_protocol"]["assessment_reporting"][
                "fixed_denominators"
            ]["exact_pv_replay_slots"],
            2_304,
        )
        self.assertIn("all-2304-PV-replays-VALID", join["support_claim_gate"])

    def test_protocol_pins_live_agent_benchmark_roots(self):
        roots = self.protocol["upstream"]["evaluator_roots"]
        self.assertEqual(
            roots["benchmark_root"],
            benchmark_module.ATLAS_AGENT_BENCHMARK_ROOT_V1,
        )
        self.assertEqual(
            roots["benchmark_canonical_sha256"],
            benchmark_module.ATLAS_AGENT_BENCHMARK_CANONICAL_SHA256_V1,
        )
        self.assertEqual(
            roots["ladder_root"],
            benchmark_module.ATLAS_AGENT_BENCHMARK_LADDER_ROOT_V1,
        )


class AtlasProtocolAssessmentTests(unittest.TestCase):
    def test_exact_pair_truth_table_and_horizon_priority(self):
        self.assertEqual(
            protocol_module._classify_atlas_exact_pair_v1(_exact(), _exact()),
            "A_ROLE_DOMINANT",
        )
        self.assertEqual(
            protocol_module._classify_atlas_exact_pair_v1(
                _exact(result="B_WIN"), _exact(result="B_WIN")
            ),
            "B_ROLE_DOMINANT",
        )
        self.assertEqual(
            protocol_module._classify_atlas_exact_pair_v1(
                _exact(), _exact(result="B_WIN")
            ),
            "FIRST_PLAYER_DOMINANT",
        )
        self.assertEqual(
            protocol_module._classify_atlas_exact_pair_v1(
                _exact(result="B_WIN"), _exact()
            ),
            "SECOND_PLAYER_DOMINANT",
        )
        self.assertEqual(
            protocol_module._classify_atlas_exact_pair_v1(
                _exact(result="DRAW", reason="PLY_LIMIT"), _exact()
            ),
            "HORIZON_UNRESOLVED",
        )
        self.assertEqual(
            protocol_module._classify_atlas_exact_pair_v1(
                _exact(status="INCOMPLETE"), _exact()
            ),
            "EVIDENCE_INCOMPLETE",
        )
        self.assertEqual(
            protocol_module._classify_atlas_exact_pair_v1(
                _exact(status="INVALID"), _exact()
            ),
            "EVIDENCE_INVALID",
        )
        with self.assertRaises(ValueError):
            protocol_module._classify_atlas_exact_pair_v1(
                _exact(result="DRAW", reason="NO_LEGAL_ACTION"), _exact()
            )

    def test_sampled_gate_uses_complete_128_and_exact_integer_thresholds(self):
        self.assertEqual(
            protocol_module._classify_atlas_sampled_strength_v1(_sampled()),
            "WEAK_BALANCE_SIGNAL_V1",
        )
        self.assertEqual(
            protocol_module._classify_atlas_sampled_strength_v1(
                _sampled(a_wins=41, b_wins=23, draws=64)
            ),
            "WEAK_BALANCE_SIGNAL_V1",
        )
        self.assertEqual(
            protocol_module._classify_atlas_sampled_strength_v1(
                _sampled(a_wins=42, b_wins=22, draws=64)
            ),
            "ROLE_IMBALANCE_SIGNAL",
        )
        self.assertEqual(
            protocol_module._classify_atlas_sampled_strength_v1(
                _sampled(a_wins=32, b_wins=31, draws=65)
            ),
            "EXCESSIVE_HORIZON_SIGNAL",
        )
        self.assertEqual(
            protocol_module._classify_atlas_sampled_strength_v1(
                _sampled(
                    status="INCOMPLETE",
                    completed=7,
                    a_wins=3,
                    b_wins=2,
                    draws=2,
                )
            ),
            "EVIDENCE_INCOMPLETE",
        )
        with self.assertRaises(ValueError):
            protocol_module._classify_atlas_sampled_strength_v1(
                _sampled(completed=127, a_wins=48, b_wins=47, draws=32)
            )

    def test_pair_frontier_requires_exact_and_both_weak_signals(self):
        self.assertEqual(
            protocol_module._classify_atlas_pair_frontier_v1(
                "FIRST_PLAYER_DOMINANT",
                "WEAK_BALANCE_SIGNAL_V1",
                "WEAK_BALANCE_SIGNAL_V1",
            ),
            "PAIR_FRONTIER_SIGNAL_V1",
        )
        self.assertEqual(
            protocol_module._classify_atlas_pair_frontier_v1(
                "A_ROLE_DOMINANT",
                "WEAK_BALANCE_SIGNAL_V1",
                "WEAK_BALANCE_SIGNAL_V1",
            ),
            "NO_PAIR_FRONTIER_EXACT",
        )
        self.assertEqual(
            protocol_module._classify_atlas_pair_frontier_v1(
                "SECOND_PLAYER_DOMINANT",
                "WEAK_BALANCE_SIGNAL_V1",
                "ROLE_IMBALANCE_SIGNAL",
            ),
            "NO_PAIR_FRONTIER_WEAK_PLAY",
        )
        self.assertEqual(
            protocol_module._classify_atlas_pair_frontier_v1(
                "HORIZON_UNRESOLVED",
                "WEAK_BALANCE_SIGNAL_V1",
                "WEAK_BALANCE_SIGNAL_V1",
            ),
            "HORIZON_UNRESOLVED",
        )

    def test_family_frontier_requires_two_pairs_across_two_strata(self):
        records = [
            _pair_record(index, "NO_PAIR_FRONTIER_EXACT") for index in range(24)
        ]
        records[0] = _pair_record(0, "PAIR_FRONTIER_SIGNAL_V1", "alpha")
        records[1] = _pair_record(1, "PAIR_FRONTIER_SIGNAL_V1", "beta")
        assessment = protocol_module._assess_atlas_family_frontier_v1(records)
        self.assertFalse(assessment["formal_evidence"])
        self.assertEqual(assessment["status"], "SUPPORTED_FAMILY_FRONTIER")
        self.assertEqual(assessment["frontier_pair_count"], 2)
        self.assertEqual(assessment["frontier_distinct_stratum_count"], 2)

        records[1] = _pair_record(1, "PAIR_FRONTIER_SIGNAL_V1", "alpha")
        self.assertEqual(
            protocol_module._assess_atlas_family_frontier_v1(records)["status"],
            "NOT_SUPPORTED_COMPLETE",
        )
        records[2] = _pair_record(2, "EVIDENCE_INCOMPLETE", "gamma")
        self.assertEqual(
            protocol_module._assess_atlas_family_frontier_v1(records)["status"],
            "INCONCLUSIVE_INCOMPLETE",
        )
        records[3] = _pair_record(3, "EVIDENCE_INVALID", "delta")
        self.assertEqual(
            protocol_module._assess_atlas_family_frontier_v1(records)["status"],
            "EVIDENCE_INVALID",
        )

    def test_assessment_rejects_bool_counts_duplicates_and_unknown_labels(self):
        with self.assertRaises(ValueError):
            protocol_module._classify_atlas_sampled_strength_v1(
                {
                    **_sampled(),
                    "a_wins": True,
                    "b_wins": 95,
                    "draws": 32,
                }
            )
        records = [
            _pair_record(index, "NO_PAIR_FRONTIER_EXACT") for index in range(24)
        ]
        records[1]["paired_mechanical_d4_identity"] = records[0][
            "paired_mechanical_d4_identity"
        ]
        with self.assertRaises(ValueError):
            protocol_module._assess_atlas_family_frontier_v1(records)
        with self.assertRaises(ValueError):
            protocol_module._classify_atlas_pair_frontier_v1(
                "UNKNOWN",
                "WEAK_BALANCE_SIGNAL_V1",
                "WEAK_BALANCE_SIGNAL_V1",
            )


class AtlasProtocolInspectionTests(unittest.TestCase):
    def test_metric_calculators_use_exact_pooled_rationals(self):
        self.assertEqual(
            protocol_module._calculate_exact_state_utilization_v1(
                {
                    "A_FIRST": {
                        "status": "COMPLETE",
                        "searched_states": 50,
                        "max_states": 100,
                    },
                    "B_FIRST": {
                        "status": "COMPLETE",
                        "searched_states": 60,
                        "max_states": 200,
                    },
                }
            ),
            _fraction(1, 2),
        )
        self.assertEqual(
            protocol_module._calculate_strength_role_share_gap_v1(
                {
                    "random-v1-weak": {
                        "status": "COMPLETE",
                        "scheduled_games": 128,
                        "completed_games": 128,
                        "a_wins": 75,
                        "b_wins": 25,
                        "draw_ply_limit": 28,
                    },
                    "terminal_only_minimax-v1-depth1": {
                        "status": "COMPLETE",
                        "scheduled_games": 128,
                        "completed_games": 128,
                        "a_wins": 25,
                        "b_wins": 75,
                        "draw_ply_limit": 28,
                    },
                }
            ),
            _fraction(1, 2),
        )

        orientations = {
            transform: {
                "status": "COMPLETE",
                "scheduled_games": 16,
                "completed_games": 16,
                "a_wins": 8,
                "b_wins": 8,
                "draw_ply_limit": 0,
            }
            for transform in protocol_module.ATLAS_D4_TRANSFORMS_V1
        }
        orientations["I"] = {
            "status": "COMPLETE",
            "scheduled_games": 16,
            "completed_games": 16,
            "a_wins": 16,
            "b_wins": 0,
            "draw_ply_limit": 0,
        }
        self.assertEqual(
            protocol_module._calculate_d4_outcome_range_v1(
                orientations, "random-v1-weak"
            ),
            _fraction(1, 2),
        )
        zero_decisive = copy.deepcopy(orientations)
        zero_decisive["R90"] = {
            "status": "COMPLETE",
            "scheduled_games": 16,
            "completed_games": 16,
            "a_wins": 0,
            "b_wins": 0,
            "draw_ply_limit": 16,
        }
        self.assertEqual(
            protocol_module._calculate_d4_outcome_range_v1(
                zero_decisive, "random-v1-weak"
            ),
            _missing("ZERO_DECISIVE_ORIENTATION"),
        )
        depth1 = {
            "status": "COMPLETE",
            "scheduled_games": 128,
            "completed_games": 128,
            "a_wins": 48,
            "b_wins": 48,
            "draw_ply_limit": 32,
        }
        self.assertEqual(
            protocol_module._calculate_depth1_ply_limit_rate_v1(depth1),
            _fraction(1, 4),
        )
        self.assertEqual(
            protocol_module._calculate_forced_decision_fractions_v1(
                {
                    "A": {
                        "status": "COMPLETE",
                        "decision_count": 8,
                        "forced_decision_count": 2,
                    },
                    "B": {
                        "status": "COMPLETE",
                        "decision_count": 4,
                        "forced_decision_count": 0,
                    },
                }
            ),
            {"A": _fraction(1, 4), "B": _fraction(0, 1)},
        )
        self.assertEqual(
            protocol_module._calculate_depth1_reciprocal_dependency_fraction_v1(
                {
                    "status": "COMPLETE",
                    "scheduled_games": 128,
                    "completed_games": 128,
                    "reciprocal_games": 16,
                }
            ),
            _fraction(1, 8),
        )

        self.assertEqual(
            protocol_module._calculate_exact_state_utilization_v1(
                {
                    "A_FIRST": {
                        "status": "INCOMPLETE",
                        "searched_states": None,
                        "max_states": None,
                    },
                    "B_FIRST": {
                        "status": "INVALID",
                        "searched_states": None,
                        "max_states": None,
                    },
                }
            ),
            _missing("INVALID_EVIDENCE"),
        )
        invalid_strengths = {
            "random-v1-weak": {
                "status": "INCOMPLETE",
                "scheduled_games": 128,
                "completed_games": 0,
                "a_wins": 0,
                "b_wins": 0,
                "draw_ply_limit": 0,
            },
            "terminal_only_minimax-v1-depth1": {
                "status": "INVALID",
                "scheduled_games": 128,
                "completed_games": 0,
                "a_wins": 0,
                "b_wins": 0,
                "draw_ply_limit": 0,
            },
        }
        self.assertEqual(
            protocol_module._calculate_strength_role_share_gap_v1(
                invalid_strengths
            ),
            _missing("INVALID_EVIDENCE"),
        )
        invalid_orientations = copy.deepcopy(orientations)
        invalid_orientations["I"] = {
            "status": "INCOMPLETE",
            "scheduled_games": 16,
            "completed_games": 0,
            "a_wins": 0,
            "b_wins": 0,
            "draw_ply_limit": 0,
        }
        invalid_orientations["FA"] = {
            "status": "INVALID",
            "scheduled_games": 16,
            "completed_games": 0,
            "a_wins": 0,
            "b_wins": 0,
            "draw_ply_limit": 0,
        }
        self.assertEqual(
            protocol_module._calculate_d4_outcome_range_v1(
                invalid_orientations, "random-v1-weak"
            ),
            _missing("INVALID_EVIDENCE"),
        )
        self.assertEqual(
            protocol_module._calculate_forced_decision_fractions_v1(
                {
                    "A": {
                        "status": "INCOMPLETE",
                        "decision_count": None,
                        "forced_decision_count": None,
                    },
                    "B": {
                        "status": "INVALID",
                        "decision_count": None,
                        "forced_decision_count": None,
                    },
                }
            ),
            {
                "A": _missing("INVALID_EVIDENCE"),
                "B": _missing("INVALID_EVIDENCE"),
            },
        )

    def test_inspection_selection_is_exact_deterministic_and_manifest_ordered(self):
        records = [_inspection_pair(index) for index in range(144)]
        records[0] = _inspection_pair(0, assessment="PAIR_FRONTIER_SIGNAL_V1")
        records[1] = _inspection_pair(
            1,
            assessment="HORIZON_UNRESOLVED",
        )
        records[2] = _inspection_pair(
            2,
            exact_label="FIRST_PLAYER_DOMINANT",
            random_label="EXCESSIVE_HORIZON_SIGNAL",
        )
        records[3] = _inspection_pair(
            3,
            channel_statuses={
                "exact": "COMPLETE",
                "random": "COMPLETE",
                "terminal_depth1": "COMPLETE",
                "telemetry": "INCOMPLETE",
            },
        )
        first = protocol_module._calculate_atlas_inspection_selection_v1(records)
        second = protocol_module._calculate_atlas_inspection_selection_v1(
            copy.deepcopy(records)
        )
        self.assertEqual(first, second)
        self.assertEqual(first["pair_record_count"], 144)
        self.assertEqual(first["class_group_summary_count"], 118)
        selected_indices = [row["pair_index"] for row in first["selected_pairs"]]
        self.assertEqual(selected_indices, sorted(selected_indices))
        selected = {row["pair_index"]: row for row in first["selected_pairs"]}
        self.assertIn(
            "PAIR_FRONTIER", {reason["class"] for reason in selected[0]["reasons"]}
        )
        self.assertIn(
            "MANDATORY_EXCEPTION",
            {reason["class"] for reason in selected[1]["reasons"]},
        )
        self.assertIn(
            "MANDATORY_EXCEPTION",
            {reason["class"] for reason in selected[2]["reasons"]},
        )
        self.assertNotIn(
            "ORDINARY_CONTROL",
            {reason["class"] for reason in selected[2]["reasons"]},
        )
        self.assertEqual(
            records[3]["metrics"]["exact_state_utilization"]["status"],
            "DEFINED",
        )
        self.assertIn(
            "MANDATORY_EXCEPTION",
            {reason["class"] for reason in selected[3]["reasons"]},
        )
        self.assertFalse(first["formal_evidence"])
        self.assertNotIn("inspection_protocol_root", first)
        self.assertNotIn("inspection_selection_root", first)

    def test_extreme_ties_use_domain_hash_and_missing_has_no_replacement(self):
        records = [_inspection_pair(index) for index in range(144)]
        for index in range(24):
            records[index]["metrics"]["exact_state_utilization"] = _fraction(1, 2)
        selection = protocol_module._calculate_atlas_inspection_selection_v1(records)
        family_id = protocol_module.ATLAS_FAMILY_ORDER_V1[0]
        summary = next(
            row
            for row in selection["class_group_summaries"]
            if row["class"] == "EXACT_STATE_UTILIZATION"
            and row["group"] == {"kind": "FAMILY", "family_id": family_id}
        )
        group = {"kind": "FAMILY", "family_id": family_id}
        expected = min(
            records[:24],
            key=lambda record: (
                protocol_module._inspection_score_v1(
                    "EXACT_STATE_UTILIZATION",
                    "HIGH",
                    group,
                    record["paired_mechanical_d4_identity"],
                ),
                record["paired_mechanical_d4_identity"],
            ),
        )
        self.assertEqual(
            summary["selected_pair_identities"],
            [expected["paired_mechanical_d4_identity"]],
        )

        for index in range(24, 48):
            records[index] = _inspection_pair(
                index,
                channel_statuses={
                    "exact": "INCOMPLETE",
                    "random": "COMPLETE",
                    "terminal_depth1": "COMPLETE",
                    "telemetry": "COMPLETE",
                },
                exact_label="EVIDENCE_INCOMPLETE",
            )
            records[index]["metrics"]["exact_state_utilization"] = _missing(
                "INCOMPLETE_EXACT"
            )
        selection = protocol_module._calculate_atlas_inspection_selection_v1(records)
        missing_family = protocol_module.ATLAS_FAMILY_ORDER_V1[1]
        summary = next(
            row
            for row in selection["class_group_summaries"]
            if row["class"] == "EXACT_STATE_UTILIZATION"
            and row["group"]
            == {"kind": "FAMILY", "family_id": missing_family}
        )
        self.assertEqual(summary["metric_defined_count"], 0)
        self.assertEqual(summary["metric_missing_count"], 24)
        self.assertEqual(summary["selected_count"], 0)

    def test_inspection_rejects_unbound_shapes_and_noncanonical_fractions(self):
        records = [_inspection_pair(index) for index in range(144)]
        with self.assertRaises(ValueError):
            protocol_module._calculate_atlas_inspection_selection_v1(records[:-1])
        duplicate = copy.deepcopy(records)
        duplicate[1]["paired_mechanical_d4_identity"] = duplicate[0][
            "paired_mechanical_d4_identity"
        ]
        with self.assertRaises(ValueError):
            protocol_module._calculate_atlas_inspection_selection_v1(duplicate)
        noncanonical = copy.deepcopy(records)
        noncanonical[0]["metrics"]["exact_state_utilization"] = {
            "status": "DEFINED",
            "numerator": 2,
            "denominator": 4,
        }
        with self.assertRaises(ValueError):
            protocol_module._calculate_atlas_inspection_selection_v1(noncanonical)

    def test_formal_boundary_and_reporting_are_machine_readable_and_private(self):
        assessment = protocol_module._assessment_protocol()
        boundary = assessment["formal_reconstruction_boundary"]
        self.assertFalse(boundary["caller_supplied_aggregate_or_label_is_authoritative"])
        self.assertFalse(
            boundary["leaf_arithmetic_helpers_are_formal_evidence_boundaries"]
        )
        self.assertEqual(
            assessment["family_frontier_rule"]["status_priority"][0],
            "EVIDENCE_INVALID",
        )
        reporting = assessment["assessment_reporting"]
        self.assertIn("goal_frame", reporting["dimensions"])
        self.assertIn("not_run", reporting["count_fields"]["sampled"])
        self.assertIn("blocked", reporting["count_fields"]["sampled"])
        self.assertIn(
            "not_admissible_traces", reporting["count_fields"]["telemetry"]
        )
        self.assertIn("exact_pv_replay", reporting["count_fields"])
        channels = boundary["pair_channel_reconstruction"]
        self.assertEqual(
            channels["telemetry"]["scope_per_pair"].split("-")[1], "256"
        )
        self.assertEqual(reporting["universal_score"], "FORBIDDEN")
        inspection = protocol_module._inspection_protocol()
        self.assertFalse(
            inspection["input_contract"][
                "pair_channel_status_is_metric_admission_input"
            ]
        )
        self.assertIn(
            "random-telemetry-excluded",
            inspection["metric_definitions"]["forced_decision_fraction"][
                "raw_status_scope"
            ],
        )
        self.assertEqual(inspection["direction_expansion_order"], ["LOW", "HIGH"])
        self.assertEqual(
            inspection["classes"][-2]["group"], "FAMILY_X_ROLE"
        )
        self.assertNotIn("classify_atlas_sampled_strength_v1", protocol_module.__all__)
        self.assertNotIn("assess_atlas_family_frontier_v1", protocol_module.__all__)
        self.assertNotIn("iter_frozen_atlas_game_schedule_v1", protocol_module.__all__)
        self.assertIn(
            "iter_frozen_atlas_game_schedule_from_protocol_v1",
            protocol_module.__all__,
        )


if __name__ == "__main__":
    unittest.main()
