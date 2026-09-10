import copy
import math
import unittest
from contextlib import ExitStack, contextmanager
from typing import Any, Dict, Iterator, Mapping
from unittest.mock import Mock, patch

from parity_forge.dsl import Player, definition_hash, parse_definition
from parity_forge.engine import apply_action, initial_state, legal_actions
from parity_forge.landscape_evaluation import evaluate_landscape_cases
from parity_forge.stalemate import (
    STALEMATE_SOURCE_MANIFEST_ID,
    STALEMATE_SOURCE_MANIFEST_SHA256,
    build_stalemate_paired_manifest,
    evaluate_stalemate_pairs,
    select_stalemate_inspection_cases,
    select_stalemate_stress_candidates,
    stress_stalemate_draws,
    stalemate_natural_exhaustion_bound,
    validate_stalemate_baseline_replay,
    validate_stalemate_paired_manifest,
    validate_stalemate_paired_result,
    validate_stalemate_stress_result,
)
from parity_forge.symmetry import d4_canonical_hash

from tests.support import crossing_definition


class StepClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        self.value += 1.0
        return self.value


class FakeProfile:
    def __init__(self, decisive_a_share: float) -> None:
        self.decisive_a_share = decisive_a_share

    def to_dict(self, include_records: bool = True) -> Dict[str, Any]:
        del include_records
        a_wins = 15 if self.decisive_a_share == 0.5 else 16
        b_wins = 15 if self.decisive_a_share == 0.5 else 14
        decisive = a_wins + b_wins
        z = 1.959963984540054
        proportion = a_wins / decisive
        denominator = 1.0 + z * z / decisive
        center = (proportion + z * z / (2.0 * decisive)) / denominator
        margin = z * math.sqrt(
            proportion * (1.0 - proportion) / decisive
            + z * z / (4.0 * decisive * decisive)
        ) / denominator
        return {
            "profile": "stress-minimax-depth5",
            "agent_a": "minimax-v1-depth5",
            "agent_b": "minimax-v1-depth5",
            "samples": 30,
            "a_wins": a_wins,
            "b_wins": b_wins,
            "draws": 0,
            "a_win_rate": a_wins / 30,
            "b_win_rate": b_wins / 30,
            "draw_rate": 0.0,
            "average_plies": 8.0,
            "decisive_a_share": self.decisive_a_share,
            "decisive_a_wilson_95": [
                max(0.0, center - margin),
                min(1.0, center + margin),
            ],
            "terminal_reasons": {"GOAL": 30},
            "seeds": list(range(30)),
        }


@contextmanager
def tiny_manifest_contract(
    source_count: int, pair_count: int, stratum_count: int, quota: int
) -> Iterator[None]:
    with ExitStack() as stack:
        stack.enter_context(
            patch("parity_forge.stalemate.STALEMATE_SOURCE_CASE_COUNT", source_count)
        )
        stack.enter_context(
            patch("parity_forge.stalemate.STALEMATE_PAIR_COUNT", pair_count)
        )
        stack.enter_context(
            patch("parity_forge.stalemate.STALEMATE_STRATUM_COUNT", stratum_count)
        )
        stack.enter_context(
            patch("parity_forge.stalemate.STALEMATE_QUOTA_PER_STRATUM", quota)
        )
        yield


def _source_case(index: int, first_player: str) -> Dict[str, Any]:
    raw = crossing_definition()
    raw["name"] = "Stalemate fixture {}".format(index)
    raw["first_player"] = first_player
    raw["max_plies"] = 18
    definition = parse_definition(raw)
    return {
        "case_id": "source-{}".format(index),
        "stratum": {
            "first_player": first_player,
            "goal_axis_relation": "ALIGNED",
            "runner_start_class": "EDGE_MIDPOINT",
            "max_plies": 18,
            "vector_count_band": "4_TO_5",
        },
        "vector_count": len(definition.role(Player.B).action.vectors),
        "selection_score": "{:064x}".format(index + 1),
        "selection_rank": 1,
        "definition_hash": definition_hash(definition),
        "d4_canonical_hash": d4_canonical_hash(definition),
        "definition": definition.to_dict(),
    }


def _landscape_case(source: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        key: copy.deepcopy(source[key])
        for key in (
            "case_id",
            "stratum",
            "vector_count",
            "definition_hash",
            "d4_canonical_hash",
            "definition",
        )
    }


def _paired_fixture():
    sources = [_source_case(0, "A"), _source_case(1, "B")]
    manifest = build_stalemate_paired_manifest(
        {"manifest_id": STALEMATE_SOURCE_MANIFEST_ID, "cases": sources},
        STALEMATE_SOURCE_MANIFEST_SHA256,
        {"fixture": True},
    )
    baseline = evaluate_landscape_cases(
        tuple(_landscape_case(source) for source in sources),
        play_seeds=(0,),
        max_exact_states=100000,
        clock=StepClock(),
    )
    return sources, manifest, baseline


def _treatment_mapping(name: str) -> Dict[str, Any]:
    raw = crossing_definition()
    raw["name"] = name
    raw["max_plies"] = 18
    raw["schema_version"] = 2
    raw["terminal_policy"] = {"no_legal_action": "DRAW"}
    return parse_definition(raw).to_dict()


def _raw_candidate(
    index: int,
    *,
    static_passes: bool = True,
    analysis_gate_passes: bool = True,
    cheap_failure_codes=(),
    outcome: str = "DRAW",
    terminal_reason: str = "NO_LEGAL_ACTION",
    principal_variation_plies: int = 3,
    baseline_outcome: str = "A_WIN",
    stratum_index: int = 0,
) -> Dict[str, Any]:
    mapping = _treatment_mapping("Stress fixture {}".format(index))
    definition = parse_definition(mapping)
    weak_profile = FakeProfile(0.5).to_dict(include_records=False)
    weak_profile.update(
        {
            "profile": "weak-random",
            "agent_a": "random-v1-weak",
            "agent_b": "random-v1-weak",
        }
    )
    directed_profile = FakeProfile(0.5).to_dict(include_records=False)
    directed_profile.update(
        {
            "profile": "medium-goal-directed",
            "agent_a": "goal_directed-v1-medium",
            "agent_b": "goal_directed-v1-medium",
        }
    )
    shape_clean = bool(
        static_passes
        and analysis_gate_passes
        and outcome == "DRAW"
        and terminal_reason == "NO_LEGAL_ACTION"
        and principal_variation_plies > 0
        and not cheap_failure_codes
    )
    cheap_profiles = [weak_profile, directed_profile] if static_passes else []
    stored_failures = list(cheap_failure_codes) if static_passes else []
    return {
        "pair_id": "pair-{}".format(index),
        "source_case_id": "source-{}".format(index),
        "definition_hash": definition_hash(definition),
        "d4_canonical_hash": "orbit-{}".format(index),
        "stratum": {
            "first_player": "A",
            "goal_axis_relation": "ALIGNED",
            "runner_start_class": "EDGE_MIDPOINT",
            "max_plies": 18,
            "vector_count_band": "4_TO_5",
            "fixture_stratum": stratum_index,
        },
        "vector_count": 4,
        "definition": mapping,
        "static": {"passes": static_passes},
        "analysis_gate_passes": analysis_gate_passes,
        "cheap_profiles": cheap_profiles,
        "cheap_failure_codes": stored_failures,
        "shape_clean_stalemate_draw": shape_clean,
        "exact": {
            "status": "COMPLETED",
            "result": {
                "forced_result": outcome,
                "terminal_reason": terminal_reason,
                "principal_variation_plies": principal_variation_plies,
            },
            "budget_observation": None,
        },
        "baseline_exact": {
            "status": "COMPLETED",
            "result": {
                "forced_result": baseline_outcome,
                "terminal_reason": "GOAL",
                "principal_variation_plies": 2,
            },
            "budget_observation": None,
        },
    }


class StalemateManifestTests(unittest.TestCase):
    def test_builder_is_deterministic_and_treatment_outcome_free(self) -> None:
        with tiny_manifest_contract(2, 2, 2, 1):
            sources, first, _ = _paired_fixture()
            second = build_stalemate_paired_manifest(
                {"manifest_id": STALEMATE_SOURCE_MANIFEST_ID, "cases": sources},
                STALEMATE_SOURCE_MANIFEST_SHA256,
                {"fixture": True},
            )
            validated = validate_stalemate_paired_manifest(first)

        self.assertEqual(first, second)
        self.assertEqual(len(validated), 2)
        self.assertTrue(first["selection_protocol"]["baseline_informed"])
        self.assertTrue(first["selection_protocol"]["treatment_outcome_free"])
        for pair in first["pairs"]:
            treatment = copy.deepcopy(pair["treatment_definition"])
            policy = treatment.pop("terminal_policy")
            treatment["schema_version"] = 1
            self.assertEqual(policy, {"no_legal_action": "DRAW"})
            self.assertEqual(treatment, pair["source_definition"])
            self.assertNotIn("result", pair)
            self.assertNotIn("outcome", pair)

    def test_public_validator_enforces_production_census(self) -> None:
        with tiny_manifest_contract(2, 2, 2, 1):
            _, manifest, _ = _paired_fixture()
        with self.assertRaisesRegex(ValueError, "exactly 128 pairs"):
            validate_stalemate_paired_manifest(manifest)

    def test_builder_fails_closed_on_extra_initial_piece(self) -> None:
        source = _source_case(0, "A")
        source["definition"]["initial_pieces"].append(
            {"owner": "A", "piece": "seed", "position": [0, 0]}
        )
        definition = parse_definition(source["definition"])
        source["definition"] = definition.to_dict()
        source["definition_hash"] = definition_hash(definition)
        source["d4_canonical_hash"] = d4_canonical_hash(definition)
        with tiny_manifest_contract(1, 1, 1, 1):
            with self.assertRaisesRegex(ValueError, "one-runner"):
                build_stalemate_paired_manifest(
                    {"manifest_id": STALEMATE_SOURCE_MANIFEST_ID, "cases": [source]},
                    STALEMATE_SOURCE_MANIFEST_SHA256,
                    {"fixture": True},
                )

        source = _source_case(0, "A")
        source["stratum"]["terminal_reason"] = "NO_LEGAL_ACTION"
        with tiny_manifest_contract(1, 1, 1, 1):
            with self.assertRaisesRegex(ValueError, "frozen stratum schema"):
                build_stalemate_paired_manifest(
                    {"manifest_id": STALEMATE_SOURCE_MANIFEST_ID, "cases": [source]},
                    STALEMATE_SOURCE_MANIFEST_SHA256,
                    {"fixture": True},
                )


class StalemateNaturalBoundTests(unittest.TestCase):
    def test_a_and_b_first_bounds_hold_for_every_reachable_state(self) -> None:
        for first_player, expected_bound in (("A", 15), ("B", 16)):
            with self.subTest(first_player=first_player):
                mapping = _treatment_mapping("Bound {}".format(first_player))
                mapping["first_player"] = first_player
                definition = parse_definition(mapping)
                canonical = definition.to_dict()
                bound = stalemate_natural_exhaustion_bound(canonical)
                self.assertEqual(bound, expected_bound)

                frontier = [initial_state(definition)]
                seen = set()
                terminal_plies = []
                while frontier:
                    state = frontier.pop()
                    if state in seen:
                        continue
                    seen.add(state)
                    self.assertLessEqual(state.ply, bound)
                    if state.terminal:
                        terminal_plies.append(state.ply)
                        self.assertNotEqual(state.outcome.reason, "PLY_LIMIT")
                        continue
                    self.assertLess(state.ply, bound)
                    frontier.extend(
                        apply_action(definition, state, action)
                        for action in legal_actions(definition, state)
                    )
                self.assertTrue(terminal_plies)
                self.assertLessEqual(max(terminal_plies), bound)

    def test_bound_rejects_each_material_structural_deviation(self) -> None:
        deviations = []
        wrong_max = _treatment_mapping("Wrong max")
        wrong_max["max_plies"] = 17
        deviations.append(wrong_max)

        extra_piece = _treatment_mapping("Extra piece")
        extra_piece["initial_pieces"].append(
            {"owner": "A", "piece": "seed", "position": [0, 0]}
        )
        deviations.append(extra_piece)

        wrong_board = _treatment_mapping("Wrong board")
        wrong_board["board_size"] = 4
        deviations.append(wrong_board)

        for mapping in deviations:
            with self.subTest(name=mapping["name"]):
                with self.assertRaisesRegex(ValueError, "exhaustion proof"):
                    stalemate_natural_exhaustion_bound(mapping)


class StalemateRawEvaluationTests(unittest.TestCase):
    def test_public_baseline_replay_validator_rebuilds_aggregate(self) -> None:
        with tiny_manifest_contract(2, 2, 2, 1):
            _, manifest, baseline = _paired_fixture()
            validated = validate_stalemate_baseline_replay(
                baseline,
                manifest,
                baseline,
                play_seeds=(0,),
                max_exact_states=100000,
            )
            self.assertEqual(len(validated), 2)

            altered = copy.deepcopy(baseline)
            altered["aggregate"]["exact_completed"] = 0
            with self.assertRaisesRegex(ValueError, "aggregate mismatch"):
                validate_stalemate_baseline_replay(
                    altered,
                    manifest,
                    baseline,
                    play_seeds=(0,),
                    max_exact_states=100000,
                )

            altered = copy.deepcopy(baseline)
            profile = altered["candidates"][0]["cheap_profiles"][0]
            decisive = profile["a_wins"] + profile["b_wins"]
            profile["terminal_reasons"] = (
                {"PLY_LIMIT": profile["samples"]}
                if decisive
                else {"GOAL": profile["samples"]}
            )
            with self.assertRaisesRegex(
                ValueError, "terminal reasons contradict outcome counts"
            ):
                validate_stalemate_baseline_replay(
                    altered,
                    manifest,
                    altered,
                    play_seeds=(0,),
                    max_exact_states=100000,
                )

    def test_raw_evaluation_replays_v1_before_treatment_and_reports_deltas(self) -> None:
        with tiny_manifest_contract(2, 2, 2, 1):
            _, manifest, baseline = _paired_fixture()
            result = evaluate_stalemate_pairs(
                manifest,
                baseline,
                play_seeds=(0,),
                max_exact_states=100000,
                clock=StepClock(),
            )

        aggregate = result["aggregate"]
        self.assertEqual(aggregate["v1_replay_match_count"], 2)
        self.assertEqual(aggregate["exact_completion_rate"], 1.0)
        self.assertEqual(aggregate["exact_censored_hashes"], [])
        self.assertEqual(
            aggregate["baseline_to_treatment_terminal_reason_transition_histogram"],
            {"GOAL->GOAL": 2},
        )
        self.assertEqual(aggregate["principal_variation_plies_delta_histogram"], {"0": 2})
        self.assertEqual(aggregate["principal_variation_plies_unchanged_count"], 2)
        self.assertTrue(
            all(candidate["principal_variation_plies_delta"] == 0 for candidate in result["candidates"])
        )
        self.assertEqual(
            aggregate["predeclared_assessment"]["overall_treatment_discovery"]["status"],
            "INCONCLUSIVE",
        )
        self.assertIn("descriptive only", result["configuration"]["duration_interpretation"])

    def test_v1_mismatch_stops_before_treatment_evaluation(self) -> None:
        with tiny_manifest_contract(2, 2, 2, 1):
            _, manifest, baseline = _paired_fixture()
            altered = copy.deepcopy(baseline)
            altered["candidates"][0]["exact"]["result"]["cache_hits"] += 1
            evaluator = Mock(wraps=evaluate_landscape_cases)
            with self.assertRaisesRegex(ValueError, "v1 baseline replay mismatch"):
                evaluate_stalemate_pairs(
                    manifest,
                    altered,
                    play_seeds=(0,),
                    max_exact_states=100000,
                    clock=StepClock(),
                    case_evaluator=evaluator,
                )
            self.assertEqual(evaluator.call_count, 1)

    def test_short_v1_replay_stops_before_treatment_evaluation(self) -> None:
        with tiny_manifest_contract(2, 2, 2, 1):
            _, manifest, baseline = _paired_fixture()

            def short_replay(cases, **kwargs):
                result = evaluate_landscape_cases(cases, **kwargs)
                result["candidates"] = result["candidates"][:-1]
                return result

            evaluator = Mock(side_effect=short_replay)
            with self.assertRaisesRegex(ValueError, "candidate count"):
                evaluate_stalemate_pairs(
                    manifest,
                    baseline,
                    play_seeds=(0,),
                    max_exact_states=100000,
                    clock=StepClock(),
                    case_evaluator=evaluator,
                )
            self.assertEqual(evaluator.call_count, 1)

    def test_baseline_source_denominator_is_exact_before_replay(self) -> None:
        with tiny_manifest_contract(2, 2, 2, 1):
            _, manifest, baseline = _paired_fixture()
            baseline["candidates"] = baseline["candidates"][:-1]
            evaluator = Mock()
            with self.assertRaisesRegex(ValueError, "exactly 2 source candidates"):
                evaluate_stalemate_pairs(
                    manifest,
                    baseline,
                    play_seeds=(0,),
                    max_exact_states=100000,
                    clock=StepClock(),
                    case_evaluator=evaluator,
                )
            evaluator.assert_not_called()

    def test_short_treatment_result_never_zip_truncates_pairs(self) -> None:
        with tiny_manifest_contract(2, 2, 2, 1):
            _, manifest, baseline = _paired_fixture()
            calls = 0

            def short_treatment(cases, **kwargs):
                nonlocal calls
                calls += 1
                result = evaluate_landscape_cases(cases, **kwargs)
                if calls == 2:
                    result["candidates"] = result["candidates"][:-1]
                return result

            evaluator = Mock(side_effect=short_treatment)
            with self.assertRaisesRegex(ValueError, "candidate count"):
                evaluate_stalemate_pairs(
                    manifest,
                    baseline,
                    play_seeds=(0,),
                    max_exact_states=100000,
                    clock=StepClock(),
                    case_evaluator=evaluator,
                )
            self.assertEqual(evaluator.call_count, 2)

    def test_treatment_exact_result_requires_complete_replayable_schema(self) -> None:
        with tiny_manifest_contract(2, 2, 2, 1):
            _, manifest, baseline = _paired_fixture()
            calls = 0

            def missing_exact_field(cases, **kwargs):
                nonlocal calls
                calls += 1
                result = evaluate_landscape_cases(cases, **kwargs)
                if calls == 2:
                    del result["candidates"][0]["exact"]["result"]["cache_hits"]
                return result

            evaluator = Mock(side_effect=missing_exact_field)
            with self.assertRaisesRegex(ValueError, "exact result schema"):
                evaluate_stalemate_pairs(
                    manifest,
                    baseline,
                    play_seeds=(0,),
                    max_exact_states=100000,
                    clock=StepClock(),
                    case_evaluator=evaluator,
                )

    def test_partial_treatment_cheap_profiles_are_rejected(self) -> None:
        with tiny_manifest_contract(2, 2, 2, 1):
            _, manifest, baseline = _paired_fixture()
            calls = 0

            def partial_profiles(cases, **kwargs):
                nonlocal calls
                calls += 1
                result = evaluate_landscape_cases(cases, **kwargs)
                if calls == 2:
                    result["candidates"][0]["cheap_profiles"] = result[
                        "candidates"
                    ][0]["cheap_profiles"][:1]
                return result

            evaluator = Mock(side_effect=partial_profiles)
            with self.assertRaisesRegex(ValueError, "cheap profile count"):
                evaluate_stalemate_pairs(
                    manifest,
                    baseline,
                    play_seeds=(0,),
                    max_exact_states=100000,
                    clock=StepClock(),
                    case_evaluator=evaluator,
                )

    def test_treatment_aggregate_is_rebuilt_from_candidate_evidence(self) -> None:
        with tiny_manifest_contract(2, 2, 2, 1):
            _, manifest, baseline = _paired_fixture()
            calls = 0

            def corrupt_aggregate(cases, **kwargs):
                nonlocal calls
                calls += 1
                result = evaluate_landscape_cases(cases, **kwargs)
                if calls == 2:
                    result["aggregate"].update(
                        {
                            "exact_completed": 0,
                            "static_pass_count": 999,
                            "exact_work_states_total": -7,
                        }
                    )
                return result

            result = evaluate_stalemate_pairs(
                manifest,
                baseline,
                play_seeds=(0,),
                max_exact_states=100000,
                clock=StepClock(),
                case_evaluator=Mock(side_effect=corrupt_aggregate),
            )

        aggregate = result["aggregate"]
        self.assertEqual(aggregate["exact_completed"], 2)
        self.assertEqual(aggregate["static_pass_count"], 2)
        self.assertGreater(aggregate["exact_work_states_total"], 0)
        self.assertEqual(
            aggregate["predeclared_assessment"]["exact_completed_count"],
            aggregate["exact_completed"],
        )

    def test_public_raw_validator_rejects_enriched_candidate_tampering(self) -> None:
        with tiny_manifest_contract(2, 2, 2, 1):
            _, manifest, baseline = _paired_fixture()
            result = evaluate_stalemate_pairs(
                manifest,
                baseline,
                play_seeds=(0,),
                max_exact_states=100000,
                clock=StepClock(),
            )
            validated = validate_stalemate_paired_result(
                result,
                manifest,
                baseline,
                play_seeds=(0,),
                max_exact_states=100000,
            )
            self.assertEqual(len(validated), 2)

            altered = copy.deepcopy(result)
            altered["candidates"][0]["manifest_index"] = False
            with self.assertRaisesRegex(ValueError, "integer identity"):
                validate_stalemate_paired_result(
                    altered,
                    manifest,
                    baseline,
                    play_seeds=(0,),
                    max_exact_states=100000,
                )

            altered = copy.deepcopy(result)
            altered["timing"]["treatment"] = {
                "static_asymmetry_simplicity_seconds": 0.0,
                "cheap_play_seconds": 0.0,
                "exact_seconds": 0.0,
                "total_seconds": 0.0,
            }
            with self.assertRaisesRegex(ValueError, "timing totals"):
                validate_stalemate_paired_result(
                    altered,
                    manifest,
                    baseline,
                    play_seeds=(0,),
                    max_exact_states=100000,
                )

            altered = copy.deepcopy(result)
            altered["aggregate"]["exact_censored_count"] = False
            with self.assertRaisesRegex(ValueError, "aggregate mismatch"):
                validate_stalemate_paired_result(
                    altered,
                    manifest,
                    baseline,
                    play_seeds=(0,),
                    max_exact_states=100000,
                )

            altered = copy.deepcopy(result)
            altered["candidates"][0]["principal_variation_plies_delta"] += 1
            with self.assertRaisesRegex(ValueError, "paired delta mismatch"):
                validate_stalemate_paired_result(
                    altered,
                    manifest,
                    baseline,
                    play_seeds=(0,),
                    max_exact_states=100000,
                )

            altered = copy.deepcopy(result)
            profile = altered["candidates"][0]["cheap_profiles"][0]
            decisive = profile["a_wins"] + profile["b_wins"]
            profile["terminal_reasons"] = (
                {"NO_LEGAL_ACTION": profile["samples"]}
                if decisive
                else {"GOAL": profile["samples"]}
            )
            with self.assertRaisesRegex(
                ValueError, "terminal reasons contradict outcome counts"
            ):
                validate_stalemate_paired_result(
                    altered,
                    manifest,
                    baseline,
                    play_seeds=(0,),
                    max_exact_states=100000,
                )

            altered = copy.deepcopy(result)
            profile = altered["candidates"][0]["cheap_profiles"][0]
            profile.update(
                {
                    "a_wins": 0,
                    "b_wins": 0,
                    "draws": profile["samples"],
                    "a_win_rate": 0.0,
                    "b_win_rate": 0.0,
                    "draw_rate": 1.0,
                    "average_plies": 18.0,
                    "decisive_a_share": None,
                    "decisive_a_wilson_95": None,
                    "terminal_reasons": {"PLY_LIMIT": profile["samples"]},
                }
            )
            with self.assertRaisesRegex(ValueError, "natural exhaustion bound"):
                validate_stalemate_paired_result(
                    altered,
                    manifest,
                    baseline,
                    play_seeds=(0,),
                    max_exact_states=100000,
                )

            altered = copy.deepcopy(result)
            altered["candidates"][0]["timing"]["cheap_play_seconds"] = float(
                "nan"
            )
            with self.assertRaisesRegex(ValueError, "candidate timing"):
                validate_stalemate_paired_result(
                    altered,
                    manifest,
                    baseline,
                    play_seeds=(0,),
                    max_exact_states=100000,
                )


class StalemateStressTests(unittest.TestCase):
    def test_static_rejected_draw_needs_no_cheap_profiles(self) -> None:
        rejected = _raw_candidate(
            0, static_passes=False, analysis_gate_passes=False
        )
        self.assertEqual(rejected["cheap_profiles"], [])
        self.assertEqual(rejected["cheap_failure_codes"], [])
        with patch("parity_forge.stalemate.evaluate_matchup") as evaluator:
            result = stress_stalemate_draws(
                {"candidates": [rejected]}, clock=StepClock()
            )

        evaluator.assert_not_called()
        self.assertEqual(result["aggregate"]["eligible_draw_count"], 0)

    def test_selection_uses_static_validity_and_shape_clean_first(self) -> None:
        clean = _raw_candidate(0)
        static_only = _raw_candidate(1, analysis_gate_passes=False)
        static_rejected = _raw_candidate(
            2, static_passes=False, analysis_gate_passes=False
        )
        initial = _raw_candidate(3, principal_variation_plies=0)
        selection = select_stalemate_stress_candidates(
            (static_only, static_rejected, initial, clean), max_candidates=2
        )

        self.assertEqual(len(selection["eligible"]), 2)
        self.assertIs(selection["selected"][0]["candidate"], clean)
        self.assertEqual(selection["selected"][1]["selection_group"], "OTHER_DRAW")

    def test_strict_directional_error_precedes_small_sample(self) -> None:
        candidate = _raw_candidate(0)
        with patch(
            "parity_forge.stalemate.evaluate_matchup",
            return_value=FakeProfile(16 / 30),
        ), patch("parity_forge.stalemate.classify_play_failures", return_value=set()):
            result = stress_stalemate_draws(
                {"candidates": [candidate]},
                max_candidates=32,
                clock=StepClock(),
            )

        assessments = result["aggregate"]["predeclared_assessment"]
        self.assertEqual(result["candidates"][0]["sampled_direction"], "A_WIN")
        self.assertEqual(assessments["general_draw_stress"]["status"], "NOT_SUPPORTED")
        self.assertEqual(assessments["overall_treatment_discovery"]["status"], "INCONCLUSIVE")
        self.assertEqual(result["aggregate"]["next_branch"], "PRIORITIZE_INDEPENDENT_SOLVER_OR_LEAF_FAMILY")

    def test_public_stress_validator_rejects_direction_tampering(self) -> None:
        raw_result = {"candidates": [_raw_candidate(0)]}
        with patch(
            "parity_forge.stalemate.evaluate_matchup",
            return_value=FakeProfile(16 / 30),
        ), patch("parity_forge.stalemate.classify_play_failures", return_value=set()):
            result = stress_stalemate_draws(raw_result, clock=StepClock())

        validated = validate_stalemate_stress_result(result, raw_result)
        self.assertEqual(len(validated), 1)

        altered = copy.deepcopy(result)
        altered["candidates"][0]["selection_rank"] = True
        with self.assertRaisesRegex(ValueError, "selection rank"):
            validate_stalemate_stress_result(altered, raw_result)

        altered = copy.deepcopy(result)
        altered["timing"]["total_seconds"] = 0.0
        with self.assertRaisesRegex(ValueError, "total timing"):
            validate_stalemate_stress_result(altered, raw_result)

        altered = copy.deepcopy(result)
        altered["aggregate"]["directional_error_count"] = True
        with self.assertRaisesRegex(ValueError, "aggregate mismatch"):
            validate_stalemate_stress_result(altered, raw_result)

        altered = copy.deepcopy(result)
        altered["candidates"][0]["sampled_direction"] = "DRAW_OR_BALANCED"
        with self.assertRaisesRegex(ValueError, "assessment evidence mismatch"):
            validate_stalemate_stress_result(altered, raw_result)

        altered = copy.deepcopy(result)
        altered["candidates"][0]["profile"]["terminal_reasons"] = {
            "NO_LEGAL_ACTION": 30
        }
        with self.assertRaisesRegex(
            ValueError, "terminal reasons contradict outcome counts"
        ):
            validate_stalemate_stress_result(altered, raw_result)

        altered = copy.deepcopy(result)
        profile = altered["candidates"][0]["profile"]
        profile.update(
            {
                "a_wins": 0,
                "b_wins": 0,
                "draws": 30,
                "a_win_rate": 0.0,
                "b_win_rate": 0.0,
                "draw_rate": 1.0,
                "average_plies": 18.0,
                "decisive_a_share": None,
                "decisive_a_wilson_95": None,
                "terminal_reasons": {"PLY_LIMIT": 30},
            }
        )
        with self.assertRaisesRegex(ValueError, "natural exhaustion bound"):
            validate_stalemate_stress_result(altered, raw_result)

    def test_ply_limit_precedes_exact_censor_and_skips_adaptive_play(self) -> None:
        ply_limit = _raw_candidate(
            0,
            outcome="DRAW",
            terminal_reason="PLY_LIMIT",
            principal_variation_plies=18,
        )
        censored = _raw_candidate(1)
        censored["exact"] = {
            "status": "CENSORED_STATE_BUDGET",
            "result": None,
            "budget_observation": {"searched_states": 100000, "max_states": 100000},
        }
        censored["shape_clean_stalemate_draw"] = False
        with patch("parity_forge.stalemate.evaluate_matchup") as evaluator:
            result = stress_stalemate_draws(
                {"candidates": [censored, ply_limit]}, clock=StepClock()
            )

        evaluator.assert_not_called()
        assessments = result["aggregate"]["predeclared_assessment"]
        self.assertEqual(assessments["clean_non_horizon"]["status"], "NOT_SUPPORTED")
        self.assertEqual(assessments["overall_treatment_discovery"]["status"], "NOT_SUPPORTED")
        self.assertEqual(result["aggregate"]["next_branch"], "AUDIT_SEMANTICS_AND_EXHAUSTION_PROOF")

    def test_complete_balanced_stress_can_support_frontier(self) -> None:
        candidates = [
            _raw_candidate(index, stratum_index=index % 2) for index in range(15)
        ]
        with patch(
            "parity_forge.stalemate.evaluate_matchup", return_value=FakeProfile(0.5)
        ), patch("parity_forge.stalemate.classify_play_failures", return_value=set()):
            result = stress_stalemate_draws(
                {"candidates": candidates}, clock=StepClock()
            )

        assessments = result["aggregate"]["predeclared_assessment"]
        self.assertEqual(assessments["general_draw_stress"]["status"], "SUPPORTED")
        self.assertEqual(assessments["frontier_response"]["status"], "SUPPORTED")
        self.assertEqual(assessments["overall_treatment_discovery"]["status"], "SUPPORTED")
        self.assertEqual(result["aggregate"]["diagnostic_frontier_count"], 15)
        self.assertEqual(result["aggregate"]["diagnostic_frontier_stratum_count"], 2)
        self.assertEqual(result["aggregate"]["next_branch"], "FREEZE_OUTCOME_BLIND_VALIDATION_CORPUS")

    def test_candidate_cap_censoring_keeps_frontier_inconclusive(self) -> None:
        candidates = [_raw_candidate(0), _raw_candidate(1)]
        with patch(
            "parity_forge.stalemate.evaluate_matchup", return_value=FakeProfile(0.5)
        ), patch("parity_forge.stalemate.classify_play_failures", return_value=set()):
            result = stress_stalemate_draws(
                {"candidates": candidates},
                max_candidates=1,
                clock=StepClock(),
            )

        assessments = result["aggregate"]["predeclared_assessment"]
        self.assertEqual(result["aggregate"]["unselected_draw_count"], 1)
        self.assertEqual(assessments["general_draw_stress"]["status"], "INCONCLUSIVE")
        self.assertIn(
            "DRAW_CANDIDATE_CAP_CENSORING",
            assessments["general_draw_stress"]["reasons"],
        )
        self.assertEqual(assessments["frontier_response"]["status"], "INCONCLUSIVE")
        self.assertEqual(assessments["overall_treatment_discovery"]["status"], "INCONCLUSIVE")

    def test_inspection_reports_pool_shortfall_and_overlapping_reasons(self) -> None:
        changed = [_raw_candidate(0), _raw_candidate(1)]
        unchanged = _raw_candidate(2, baseline_outcome="DRAW")
        stress = [
            {
                "definition_hash": changed[0]["definition_hash"],
                "status": "EVALUATED",
                "diagnostic_frontier": True,
            }
        ]
        selection = select_stalemate_inspection_cases(
            changed + [unchanged], stress, change_count=16, control_count=16
        )

        aggregate = selection["aggregate"]
        self.assertEqual(aggregate["changed_pool_count"], 2)
        self.assertEqual(aggregate["unchanged_pool_count"], 1)
        self.assertEqual(aggregate["changed_hash_sample_shortfall"], 14)
        self.assertEqual(aggregate["unchanged_hash_control_shortfall"], 15)
        first = next(
            record
            for record in selection["cases"]
            if record["treatment_definition_hash"] == changed[0]["definition_hash"]
        )
        self.assertEqual(
            first["reasons"],
            ["DIAGNOSTIC_FRONTIER", "OUTCOME_CHANGED_HASH_SAMPLE", "STRESS_SELECTED"],
        )


if __name__ == "__main__":
    unittest.main()
