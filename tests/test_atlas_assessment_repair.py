import copy
import inspect
import unittest
from types import SimpleNamespace
from unittest import mock

import parity_forge.atlas_assessment_core as assessment_stage
import parity_forge.atlas_stage_data as stage_data
from parity_forge.atlas_stage_data import (
    ATLAS_DEPTH1_STRENGTH_ID_V1,
    ATLAS_RANDOM_STRENGTH_ID_V1,
)


_RANDOM_SLOT_ID = "random-slot"
_DEPTH1_SLOT_ID = "depth1-slot"


def _parent_terminal_seals():
    return [
        {"payload": {"stage_id": stage_id}}
        for stage_id, _stage_protocol_id in assessment_stage._META_PARENT_ORDER_V1
    ]


def _game_slots():
    return [
        {
            "slot_id": _RANDOM_SLOT_ID,
            "strength": {"identity": ATLAS_RANDOM_STRENGTH_ID_V1},
        },
        {
            "slot_id": _DEPTH1_SLOT_ID,
            "strength": {"identity": ATLAS_DEPTH1_STRENGTH_ID_V1},
        },
    ]


def _metric_record():
    return {
        "telemetry_or_null": {
            "roles": {
                "A": {
                    "decision_count": 1,
                    "legal_observation_count": 1,
                    "legal_count_bins": {"0": 0, "1": 1, "2+": 0},
                    "opponent_dependency_actions": 0,
                },
                "B": {
                    "decision_count": 0,
                    "legal_observation_count": 1,
                    "legal_count_bins": {"0": 1, "1": 0, "2+": 0},
                    "opponent_dependency_actions": 0,
                },
            },
            "decisions": [{}],
            "repetition": {"repeat_event_count": 0},
            "terminal": {
                "ply": 1,
                "winner": "A",
                "reason": "NO_LEGAL_ACTION",
            },
            "work": {
                "replayed_actions": 1,
                "decision_count": 1,
                "state_observation_count": 2,
                "successor_evaluations": 1,
                "next_action_observations": 0,
            },
        }
    }


def _non_stalemate_metric_record(reason):
    record = _metric_record()
    record["telemetry_or_null"]["roles"]["B"]["legal_observation_count"] = 0
    record["telemetry_or_null"]["roles"]["B"]["legal_count_bins"]["0"] = 0
    record["telemetry_or_null"]["terminal"] = {
        "ply": 1,
        "winner": "A" if reason == "GOAL" else None,
        "reason": reason,
    }
    return record


def _zero_decision_no_legal_action_record():
    record = _metric_record()
    record["telemetry_or_null"]["roles"] = {
        "A": {
            "decision_count": 0,
            "legal_observation_count": 1,
            "legal_count_bins": {"0": 1, "1": 0, "2+": 0},
            "opponent_dependency_actions": 0,
        },
        "B": {
            "decision_count": 0,
            "legal_observation_count": 0,
            "legal_count_bins": {"0": 0, "1": 0, "2+": 0},
            "opponent_dependency_actions": 0,
        },
    }
    record["telemetry_or_null"]["decisions"] = []
    record["telemetry_or_null"]["terminal"] = {
        "ply": 0,
        "winner": "B",
        "reason": "NO_LEGAL_ACTION",
    }
    record["telemetry_or_null"]["work"] = {
        "replayed_actions": 0,
        "decision_count": 0,
        "state_observation_count": 1,
        "successor_evaluations": 0,
        "next_action_observations": 0,
    }
    return record


class AssessmentParentInputRepairTests(unittest.TestCase):
    def _read_parent_inputs(self, telemetry_lifecycle):
        phases = {
            assessment_stage._EXACT_PARENT[0]: ["exact", "exact-pv"],
            assessment_stage._RANDOM_PARENT[0]: ["random"],
            assessment_stage._DEPTH1_PARENT[0]: ["depth1"],
            assessment_stage._TELEMETRY_PARENT[0]: ["telemetry"],
        }

        def sealed_parent(
            _store,
            _protocol,
            _terminal,
            stage_id,
            stage_protocol_id,
        ):
            lifecycle = (
                telemetry_lifecycle
                if stage_id == assessment_stage._TELEMETRY_PARENT[0]
                else "COMPLETED"
            )
            ledger_set = None if lifecycle == "BLOCKED" else {
                "phase_ids": phases[stage_id]
            }
            contract = SimpleNamespace(
                stage_id=stage_id,
                stage_protocol_id=stage_protocol_id,
            )
            return ledger_set, lifecycle, contract

        def sampled_ledger(_protocol, strength, _observed, _started, **_kwargs):
            if strength == ATLAS_RANDOM_STRENGTH_ID_V1:
                return {
                    "rows": [
                        {"slot_id": _RANDOM_SLOT_ID, "status": "COMPLETE"}
                    ]
                }
            self.assertEqual(strength, ATLAS_DEPTH1_STRENGTH_ID_V1)
            return {
                "rows": [
                    {"slot_id": _DEPTH1_SLOT_ID, "status": "INCOMPLETE"}
                ]
            }

        phase_projection = mock.Mock(return_value=([], [], []))
        telemetry_reconciliation = mock.Mock(
            return_value={"kind": "telemetry-ledger"}
        )
        with mock.patch.multiple(
            assessment_stage,
            iter_frozen_atlas_exact_schedule_from_protocol_v1=mock.Mock(
                return_value=[{"slot_id": "exact-slot"}]
            ),
            iter_frozen_atlas_orientation_schedule_from_protocol_v1=mock.Mock(
                return_value=[{"slot_id": "pv-slot"}]
            ),
            iter_frozen_atlas_game_schedule_from_protocol_v1=mock.Mock(
                return_value=_game_slots()
            ),
            _sealed_parent_ledger_set_v1=mock.Mock(side_effect=sealed_parent),
            _phase_projection_v1=phase_projection,
            reconcile_atlas_exact_status_ledger_v1=mock.Mock(
                return_value={"kind": "exact-ledger"}
            ),
            reconcile_atlas_pv_status_ledger_v1=mock.Mock(
                return_value={"kind": "pv-ledger"}
            ),
            reconcile_atlas_sampled_status_ledger_v1=mock.Mock(
                side_effect=sampled_ledger
            ),
            reconcile_atlas_telemetry_status_ledger_v1=(
                telemetry_reconciliation
            ),
        ):
            result = assessment_stage._assessment_parent_inputs_v1(
                object(), {}, _parent_terminal_seals()
            )
        return result, phase_projection, telemetry_reconciliation

    def test_completed_telemetry_parent_uses_exact_lists_at_both_boundaries(self):
        result, projection, reconciliation = self._read_parent_inputs("COMPLETED")

        telemetry_projection = [
            call for call in projection.call_args_list if call.args[3] == "telemetry"
        ]
        self.assertEqual(len(telemetry_projection), 1)
        nonadmissible = telemetry_projection[0].kwargs[
            "preclassified_slot_ids"
        ]
        self.assertIs(type(nonadmissible), list)
        self.assertEqual(nonadmissible, [_DEPTH1_SLOT_ID])

        admissible = reconciliation.call_args.args[3]
        self.assertIs(type(admissible), list)
        self.assertEqual(admissible, [_RANDOM_SLOT_ID])
        self.assertNotIn("blocked", reconciliation.call_args.kwargs)
        self.assertEqual(result[4], {"kind": "telemetry-ledger"})

    def test_blocked_telemetry_parent_uses_exact_list_at_strict_consumer(self):
        result, projection, reconciliation = self._read_parent_inputs("BLOCKED")

        self.assertFalse(
            any(call.args[3] == "telemetry" for call in projection.call_args_list)
        )
        admissible = reconciliation.call_args.args[3]
        self.assertIs(type(admissible), list)
        self.assertEqual(admissible, [_RANDOM_SLOT_ID])
        self.assertIs(reconciliation.call_args.kwargs["blocked"], True)
        self.assertEqual(result[4], {"kind": "telemetry-ledger"})

    def test_real_strict_ledger_boundary_still_rejects_tuple_admissibility(self):
        slot_id = "0" * 64
        with self.assertRaisesRegex(
            TypeError, "admissible slots must be an exact array"
        ):
            stage_data._reconcile_ledger(
                "TELEMETRY",
                [slot_id],
                "1" * 64,
                "2" * 64,
                None,
                [],
                [],
                blocked=False,
                admissible_value=(slot_id,),
            )


class TelemetryMetricRepairTests(unittest.TestCase):
    def test_no_legal_action_zero_observation_is_valid_but_not_forced(self):
        values = assessment_stage._telemetry_metric_values(
            _zero_decision_no_legal_action_record()
        )

        self.assertEqual(values["roles"]["A"], {"decisions": 0, "forced": 0})
        self.assertEqual(values["roles"]["B"], {"decisions": 0, "forced": 0})

    def test_goal_and_ply_limit_have_no_zero_legal_observation(self):
        for reason in ("GOAL", "PLY_LIMIT"):
            with self.subTest(reason=reason):
                record = _non_stalemate_metric_record(reason)
                for role in ("A", "B"):
                    self.assertEqual(
                        record["telemetry_or_null"]["roles"][role][
                            "legal_count_bins"
                        ]["0"],
                        0,
                    )
                values = assessment_stage._telemetry_metric_values(record)
                self.assertEqual(values["roles"]["A"]["forced"], 1)
                self.assertEqual(values["roles"]["B"]["forced"], 0)

    def test_forced_count_uses_only_the_one_legal_action_bin(self):
        record = _metric_record()
        role_a = record["telemetry_or_null"]["roles"]["A"]
        role_a["decision_count"] = 2
        role_a["legal_observation_count"] = 3
        role_a["legal_count_bins"] = {"0": 1, "1": 1, "2+": 1}
        role_b = record["telemetry_or_null"]["roles"]["B"]
        role_b["legal_observation_count"] = 0
        role_b["legal_count_bins"] = {"0": 0, "1": 0, "2+": 0}
        record["telemetry_or_null"]["decisions"] = [{}, {}]
        record["telemetry_or_null"]["work"] = {
            "replayed_actions": 2,
            "decision_count": 2,
            "state_observation_count": 3,
            "successor_evaluations": 2,
            "next_action_observations": 0,
        }

        values = assessment_stage._telemetry_metric_values(record)

        self.assertEqual(values["roles"]["A"], {"decisions": 2, "forced": 1})

    def test_cross_field_inconsistencies_are_rejected(self):
        cases = []

        bin_total = _metric_record()
        bin_total["telemetry_or_null"]["roles"]["B"][
            "legal_observation_count"
        ] = 0
        cases.append(("bin total", bin_total, "sum to observations"))

        positive_bins = _metric_record()
        positive_bins["telemetry_or_null"]["roles"]["B"]["decision_count"] = 1
        cases.append(("positive bins", positive_bins, "sum to decisions"))

        observation_decomposition = _metric_record()
        observation_decomposition["telemetry_or_null"]["roles"]["A"][
            "legal_count_bins"
        ]["0"] = 1
        cases.append(
            (
                "observation decomposition",
                observation_decomposition,
                "sum to observations",
            )
        )

        for label, record, message in cases:
            with self.subTest(label=label):
                with self.assertRaisesRegex(ValueError, message):
                    assessment_stage._telemetry_metric_values(record)

        source = inspect.getsource(assessment_stage._telemetry_metric_values)
        self.assertIn(
            'if observations != decisions + bin_counts["0"]:',
            source,
        )

    def test_legal_observation_count_requires_an_exact_integer(self):
        for invalid in (True, 1.0):
            with self.subTest(invalid=invalid):
                record = copy.deepcopy(_metric_record())
                record["telemetry_or_null"]["roles"]["A"][
                    "legal_observation_count"
                ] = invalid
                with self.assertRaisesRegex(ValueError, "exact integer"):
                    assessment_stage._telemetry_metric_values(record)

    def test_negative_role_counts_are_rejected_individually(self):
        mutations = (
            ("decision", "decision_count", -1),
            ("observation", "legal_observation_count", -1),
        )
        for label, field, invalid in mutations:
            with self.subTest(label=label):
                record = copy.deepcopy(_metric_record())
                record["telemetry_or_null"]["roles"]["A"][field] = invalid
                with self.assertRaisesRegex(ValueError, "exact integer"):
                    assessment_stage._telemetry_metric_values(record)

        record = copy.deepcopy(_metric_record())
        record["telemetry_or_null"]["roles"]["A"]["legal_count_bins"][
            "1"
        ] = -1
        with self.assertRaisesRegex(ValueError, "exact integer"):
            assessment_stage._telemetry_metric_values(record)

    def test_boolean_decision_and_bin_counts_are_rejected_individually(self):
        decision = copy.deepcopy(_metric_record())
        decision["telemetry_or_null"]["roles"]["A"]["decision_count"] = True
        with self.assertRaisesRegex(ValueError, "exact integer"):
            assessment_stage._telemetry_metric_values(decision)

        bin_value = copy.deepcopy(_metric_record())
        bin_value["telemetry_or_null"]["roles"]["A"]["legal_count_bins"][
            "1"
        ] = True
        with self.assertRaisesRegex(ValueError, "exact integer"):
            assessment_stage._telemetry_metric_values(bin_value)

    def test_legal_count_bin_keys_reject_unknown_and_missing_entries(self):
        unknown = copy.deepcopy(_metric_record())
        unknown["telemetry_or_null"]["roles"]["A"]["legal_count_bins"][
            "unknown"
        ] = 0
        with self.assertRaisesRegex(ValueError, "bins drifted"):
            assessment_stage._telemetry_metric_values(unknown)

        missing = copy.deepcopy(_metric_record())
        del missing["telemetry_or_null"]["roles"]["A"]["legal_count_bins"][
            "2+"
        ]
        with self.assertRaisesRegex(ValueError, "bins drifted"):
            assessment_stage._telemetry_metric_values(missing)


if __name__ == "__main__":
    unittest.main()
