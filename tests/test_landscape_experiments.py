import hashlib
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from parity_forge.landscape_experiments import (
    LANDSCAPE_MANIFEST_ID,
    LANDSCAPE_MANIFEST_PROTOCOL_ID,
    _EXPECTED_MANIFEST_CENSUS,
    _FROZEN_EXECUTABLE_RELATIVES,
    _FROZEN_PROTOCOL_RELATIVES,
    _assert_no_outcome_keys,
    _load_preregistered_sources,
    _reserve_protocol,
    _scan_prior_protocol,
    _validate_completed_run_attempt,
    _validate_exact_principal_variation,
    _validate_manifest_lock,
    _validate_protocol_reservation,
    _validate_preregistered_manifest_shape,
    default_landscape_source_paths,
)
from parity_forge.dsl import parse_definition
from parity_forge.solver import solve_game

from tests.support import crossing_definition


ROOT = Path(__file__).resolve().parents[1]


class LandscapeExperimentTests(unittest.TestCase):
    def test_preregistered_sources_have_exact_identity_and_300_definitions(self) -> None:
        definitions, metadata = _load_preregistered_sources(
            default_landscape_source_paths(ROOT), ROOT
        )
        self.assertEqual(len(definitions), 300)
        self.assertEqual(len(metadata), 3)
        self.assertEqual([item["definition_count"] for item in metadata], [100] * 3)
        self.assertTrue(all("resolved_path" not in item for item in metadata))
        self.assertEqual(
            [item["label"] for item in metadata],
            [
                "generator-v1-development",
                "generator-v2-development",
                "generator-v2-heldout-20260901",
            ],
        )

    def test_manifest_lock_validates_exact_bytes(self) -> None:
        manifest = {"manifest_id": LANDSCAPE_MANIFEST_ID}
        manifest_bytes = (json.dumps(manifest) + "\n").encode("utf-8")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path = root / "manifest.json"
            lock_path = root / "manifest.lock.json"
            manifest_path.write_bytes(manifest_bytes)
            lock = {
                "manifest_id": LANDSCAPE_MANIFEST_ID,
                "protocol_id": LANDSCAPE_MANIFEST_PROTOCOL_ID,
                "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                "manifest_bytes": len(manifest_bytes),
            }
            lock_path.write_text(json.dumps(lock), encoding="utf-8")
            loaded_bytes, loaded, _ = _validate_manifest_lock(
                manifest_path, lock_path
            )
            self.assertEqual(loaded_bytes, manifest_bytes)
            self.assertEqual(loaded, manifest)

            lock["manifest_sha256"] = "0" * 64
            lock_path.write_text(json.dumps(lock), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "does not match"):
                _validate_manifest_lock(manifest_path, lock_path)

    def test_prior_evidence_scan_fails_closed_on_malformed_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary) / "run"
            run.mkdir()
            (run / "attempt.json").write_text("{", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "cannot read"):
                _scan_prior_protocol(Path(temporary), "protocol")

    def test_prior_attempt_failure_or_run_blocks_protocol(self) -> None:
        for filename in ("attempt.json", "failure.json", "run.json"):
            with self.subTest(filename=filename):
                with tempfile.TemporaryDirectory() as temporary:
                    run = Path(temporary) / "run"
                    run.mkdir()
                    (run / filename).write_text(
                        json.dumps({"protocol_id": "target"}), encoding="utf-8"
                    )
                    with self.assertRaisesRegex(ValueError, "already has evidence"):
                        _scan_prior_protocol(Path(temporary), "target")

    def test_outcome_fields_are_forbidden_recursively(self) -> None:
        _assert_no_outcome_keys({"selection": {"outcome_blind": True}})
        for key in ("forced_result", "winner", "play_profiles", "solve"):
            with self.subTest(key=key):
                with self.assertRaisesRegex(ValueError, "forbidden"):
                    _assert_no_outcome_keys({"cases": [{key: "leak"}]})

    def test_atomic_reservation_blocks_every_later_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            reservation = _reserve_protocol(
                output,
                "protocol",
                "run-id",
                "a" * 40,
                "2026-08-31T00:00:00.000000Z",
            )
            self.assertTrue(reservation.exists())
            with patch(
                "parity_forge.landscape_experiments._require_tracked"
            ):
                _validate_protocol_reservation(
                    output,
                    "protocol",
                    "run-id",
                    "a" * 40,
                    "2026-08-31T00:00:00.000000Z",
                    output,
                )
            with self.assertRaisesRegex(ValueError, "already has evidence"):
                _scan_prior_protocol(output, "protocol")
            with self.assertRaises(FileExistsError):
                _reserve_protocol(
                    output,
                    "protocol",
                    "other-run",
                    "a" * 40,
                    "2026-08-31T00:00:01.000000Z",
                )

    def test_completed_run_must_match_its_attempt(self) -> None:
        attempt = {
            "run_id": "run-id",
            "protocol_id": "protocol",
            "experiment_type": "experiment",
            "status": "STARTED",
            "started_at": "2026-08-31T00:00:00.000000Z",
            "git_commit": "a" * 40,
            "git_dirty": False,
            "environment": {"python": "test", "platform": "test"},
            "component_versions": {"component": 1},
            "configuration": {"fixed": True},
        }
        with tempfile.TemporaryDirectory() as temporary:
            run_directory = Path(temporary) / "run-id"
            run_directory.mkdir()
            run_path = run_directory / "run.json"
            (run_directory / "attempt.json").write_text(
                json.dumps(attempt), encoding="utf-8"
            )
            run_path.write_text("{}", encoding="utf-8")
            record = {
                **attempt,
                "status": "COMPLETED",
                "completed_at": "2026-08-31T00:00:01.000000Z",
            }
            with patch(
                "parity_forge.landscape_experiments._require_tracked"
            ), patch(
                "parity_forge.landscape_experiments._require_commit_ancestor"
            ):
                loaded = _validate_completed_run_attempt(
                    run_path,
                    record,
                    Path(temporary),
                    {"component": 1},
                )
                self.assertEqual(loaded, attempt)
                changed = dict(record)
                changed["configuration"] = {"fixed": False}
                with self.assertRaisesRegex(ValueError, "configuration"):
                    _validate_completed_run_attempt(
                        run_path,
                        changed,
                        Path(temporary),
                        {"component": 1},
                    )

    def test_manifest_shape_pins_every_predeclared_census_value(self) -> None:
        strata = []
        cases = []
        for stratum_index in range(96):
            case_ids = []
            for rank in range(4):
                case_id = "case-{:02d}-{}".format(stratum_index, rank)
                case_ids.append(case_id)
                cases.append(
                    {
                        "case_id": case_id,
                        "d4_canonical_hash": "{:064x}".format(
                            stratum_index * 4 + rank
                        ),
                    }
                )
            strata.append(
                {
                    "stratum_id": "stratum-{:02d}".format(stratum_index),
                    "quota": 4,
                    "eligible_d4_orbit_count": (
                        19 if stratum_index == 0 else 92 if stratum_index == 95 else 20
                    ),
                    "selected_case_ids": case_ids,
                }
            )
        manifest = {
            "census": dict(_EXPECTED_MANIFEST_CENSUS),
            "strata": strata,
            "cases": cases,
        }
        _validate_preregistered_manifest_shape(manifest)
        for key in _EXPECTED_MANIFEST_CENSUS:
            with self.subTest(key=key):
                changed = json.loads(json.dumps(manifest))
                changed["census"][key] += 1
                with self.assertRaisesRegex(ValueError, key):
                    _validate_preregistered_manifest_shape(changed)

    def test_protocol_blob_and_current_executables_are_fingerprinted_separately(self) -> None:
        self.assertEqual(
            _FROZEN_PROTOCOL_RELATIVES,
            (Path("docs/plans/active/0006-three-by-three-outcome-landscape.md"),),
        )
        self.assertNotIn(_FROZEN_PROTOCOL_RELATIVES[0], _FROZEN_EXECUTABLE_RELATIVES)
        self.assertIn(
            Path("src/parity_forge/landscape_experiments.py"),
            _FROZEN_EXECUTABLE_RELATIVES,
        )

    def test_exact_principal_variation_must_replay_to_recorded_terminal(self) -> None:
        raw = crossing_definition()
        raw["max_plies"] = 1
        definition = parse_definition(raw)
        exact = solve_game(definition).to_dict()
        _validate_exact_principal_variation(definition, exact)

        illegal = copy.deepcopy(exact)
        illegal["principal_variation"][0]["to"] = [99, 99]
        with self.assertRaisesRegex(ValueError, "legal replay"):
            _validate_exact_principal_variation(definition, illegal)

        wrong_terminal = copy.deepcopy(exact)
        wrong_terminal["terminal_reason"] = "GOAL"
        with self.assertRaisesRegex(ValueError, "terminal evidence"):
            _validate_exact_principal_variation(definition, wrong_terminal)


if __name__ == "__main__":
    unittest.main()
