import unittest
from pathlib import Path
from unittest.mock import patch

import parity_forge.__main__ as cli


class StalemateCliTests(unittest.TestCase):
    def test_stalemate_command_defaults_are_frozen(self) -> None:
        parser = cli.build_parser()

        freeze = parser.parse_args(["freeze-stalemate-manifest"])
        self.assertEqual(
            freeze.source_manifest, cli.SOURCE_LANDSCAPE_MANIFEST_RELATIVE
        )
        self.assertEqual(freeze.corpus_directory, cli.STALEMATE_CORPUS_RELATIVE)

        paired = parser.parse_args(["run-stalemate-paired"])
        self.assertEqual(paired.manifest, cli.STALEMATE_MANIFEST_RELATIVE)
        self.assertEqual(paired.lock, cli.STALEMATE_LOCK_RELATIVE)
        self.assertEqual(paired.source_raw, cli.SOURCE_LANDSCAPE_RAW_RELATIVE)

        stress = parser.parse_args(
            ["run-stalemate-draw-stress", "experiments/runs/raw/run.json"]
        )
        self.assertEqual(stress.manifest, cli.STALEMATE_MANIFEST_RELATIVE)
        self.assertEqual(stress.lock, cli.STALEMATE_LOCK_RELATIVE)

    def test_stalemate_commands_dispatch_in_runner_signature_order(self) -> None:
        output = Path("experiments/runs")
        repository = Path.cwd()
        raw_run = Path("experiments/runs/raw/run.json")

        with patch.object(cli, "_freeze_stalemate_manifest", return_value=0) as run:
            self.assertEqual(cli.main(["freeze-stalemate-manifest"]), 0)
            run.assert_called_once_with(
                cli.SOURCE_LANDSCAPE_MANIFEST_RELATIVE,
                cli.STALEMATE_CORPUS_RELATIVE,
                repository,
            )

        with patch.object(cli, "_run_stalemate_paired", return_value=0) as run:
            self.assertEqual(cli.main(["run-stalemate-paired"]), 0)
            run.assert_called_once_with(
                cli.STALEMATE_MANIFEST_RELATIVE,
                cli.STALEMATE_LOCK_RELATIVE,
                cli.SOURCE_LANDSCAPE_RAW_RELATIVE,
                output,
                repository,
            )

        with patch.object(cli, "_run_stalemate_draw_stress", return_value=0) as run:
            self.assertEqual(
                cli.main(["run-stalemate-draw-stress", str(raw_run)]), 0
            )
            run.assert_called_once_with(
                raw_run,
                cli.STALEMATE_MANIFEST_RELATIVE,
                cli.STALEMATE_LOCK_RELATIVE,
                output,
                repository,
            )


class CaptureCliTests(unittest.TestCase):
    def test_capture_command_defaults_are_frozen(self) -> None:
        parser = cli.build_parser()

        freeze = parser.parse_args(["freeze-capture-manifest"])
        self.assertEqual(
            freeze.source_manifest, cli.SOURCE_LANDSCAPE_MANIFEST_RELATIVE
        )
        self.assertEqual(freeze.corpus_directory, cli.CAPTURE_CORPUS_RELATIVE)

        paired = parser.parse_args(["run-capture-paired"])
        self.assertEqual(paired.manifest, cli.CAPTURE_MANIFEST_RELATIVE)
        self.assertEqual(paired.lock, cli.CAPTURE_LOCK_RELATIVE)
        self.assertEqual(paired.source_raw, cli.SOURCE_LANDSCAPE_RAW_RELATIVE)

        stress = parser.parse_args(
            ["run-capture-interaction-stress", "experiments/runs/raw/run.json"]
        )
        self.assertEqual(stress.manifest, cli.CAPTURE_MANIFEST_RELATIVE)
        self.assertEqual(stress.lock, cli.CAPTURE_LOCK_RELATIVE)

    def test_capture_commands_dispatch_in_runner_signature_order(self) -> None:
        output = Path("experiments/runs")
        repository = Path.cwd()
        raw_run = Path("experiments/runs/raw/run.json")

        with patch.object(cli, "_freeze_capture_manifest", return_value=0) as run:
            self.assertEqual(cli.main(["freeze-capture-manifest"]), 0)
            run.assert_called_once_with(
                cli.SOURCE_LANDSCAPE_MANIFEST_RELATIVE,
                cli.CAPTURE_CORPUS_RELATIVE,
                repository,
            )

        with patch.object(cli, "_run_capture_paired", return_value=0) as run:
            self.assertEqual(cli.main(["run-capture-paired"]), 0)
            run.assert_called_once_with(
                cli.CAPTURE_MANIFEST_RELATIVE,
                cli.CAPTURE_LOCK_RELATIVE,
                cli.SOURCE_LANDSCAPE_RAW_RELATIVE,
                output,
                repository,
            )

        with patch.object(
            cli, "_run_capture_interaction_stress", return_value=0
        ) as run:
            self.assertEqual(
                cli.main(["run-capture-interaction-stress", str(raw_run)]),
                0,
            )
            run.assert_called_once_with(
                raw_run,
                cli.CAPTURE_MANIFEST_RELATIVE,
                cli.CAPTURE_LOCK_RELATIVE,
                output,
                repository,
            )


class CaptureBoundaryCliTests(unittest.TestCase):
    def test_capture_boundary_command_defaults_are_frozen(self) -> None:
        parser = cli.build_parser()

        freeze = parser.parse_args(["freeze-capture-boundary-manifest"])
        self.assertEqual(
            freeze.corpus_directory, cli.CAPTURE_BOUNDARY_CORPUS_RELATIVE
        )

        exact = parser.parse_args(["run-capture-boundary-paired-exact"])
        self.assertEqual(exact.manifest, cli.CAPTURE_BOUNDARY_MANIFEST_RELATIVE)
        self.assertEqual(exact.lock, cli.CAPTURE_BOUNDARY_LOCK_RELATIVE)

        exact_run = Path("experiments/runs/exact/run.json")
        depth5 = parser.parse_args(
            ["run-capture-boundary-fixed-depth5", str(exact_run)]
        )
        self.assertEqual(depth5.exact_run, exact_run)
        self.assertEqual(depth5.manifest, cli.CAPTURE_BOUNDARY_MANIFEST_RELATIVE)
        self.assertEqual(depth5.lock, cli.CAPTURE_BOUNDARY_LOCK_RELATIVE)

    def test_capture_boundary_commands_dispatch_in_runner_order(self) -> None:
        output = Path("experiments/runs")
        repository = Path.cwd()
        exact_run = Path("experiments/runs/exact/run.json")

        with patch.object(
            cli, "_freeze_capture_boundary_manifest", return_value=0
        ) as run:
            self.assertEqual(cli.main(["freeze-capture-boundary-manifest"]), 0)
            run.assert_called_once_with(
                cli.CAPTURE_BOUNDARY_CORPUS_RELATIVE,
                repository,
            )

        with patch.object(
            cli, "_run_capture_boundary_paired_exact", return_value=0
        ) as run:
            self.assertEqual(cli.main(["run-capture-boundary-paired-exact"]), 0)
            run.assert_called_once_with(
                cli.CAPTURE_BOUNDARY_MANIFEST_RELATIVE,
                cli.CAPTURE_BOUNDARY_LOCK_RELATIVE,
                output,
                repository,
            )

        with patch.object(
            cli, "_run_capture_boundary_fixed_depth5", return_value=0
        ) as run:
            self.assertEqual(
                cli.main(
                    ["run-capture-boundary-fixed-depth5", str(exact_run)]
                ),
                0,
            )
            run.assert_called_once_with(
                exact_run,
                cli.CAPTURE_BOUNDARY_MANIFEST_RELATIVE,
                cli.CAPTURE_BOUNDARY_LOCK_RELATIVE,
                output,
                repository,
            )


class TwoRunnerCliTests(unittest.TestCase):
    def test_two_runner_command_defaults_are_frozen(self) -> None:
        parser = cli.build_parser()

        freeze = parser.parse_args(["freeze-two-runner-manifest"])
        self.assertEqual(freeze.corpus_directory, cli.TWO_RUNNER_CORPUS_RELATIVE)

        exact = parser.parse_args(["run-two-runner-paired-exact"])
        self.assertEqual(exact.manifest, cli.TWO_RUNNER_MANIFEST_RELATIVE)
        self.assertEqual(exact.lock, cli.TWO_RUNNER_LOCK_RELATIVE)
        self.assertFalse(hasattr(exact, "max_states"))

        exact_run = Path("experiments/runs/exact/run.json")
        depth5 = parser.parse_args(
            ["run-two-runner-fixed-depth5", str(exact_run)]
        )
        self.assertEqual(depth5.exact_run, exact_run)
        self.assertEqual(depth5.manifest, cli.TWO_RUNNER_MANIFEST_RELATIVE)
        self.assertEqual(depth5.lock, cli.TWO_RUNNER_LOCK_RELATIVE)
        for scientific_override in ("seeds", "depth", "max_nodes", "gates"):
            self.assertFalse(hasattr(depth5, scientific_override))

    def test_two_runner_commands_dispatch_in_runner_order(self) -> None:
        output = Path("experiments/runs")
        repository = Path.cwd()
        exact_run = Path("experiments/runs/exact/run.json")

        with patch.object(cli, "_freeze_two_runner_manifest", return_value=0) as run:
            self.assertEqual(cli.main(["freeze-two-runner-manifest"]), 0)
            run.assert_called_once_with(cli.TWO_RUNNER_CORPUS_RELATIVE, repository)

        with patch.object(cli, "_run_two_runner_paired_exact", return_value=0) as run:
            self.assertEqual(cli.main(["run-two-runner-paired-exact"]), 0)
            run.assert_called_once_with(
                cli.TWO_RUNNER_MANIFEST_RELATIVE,
                cli.TWO_RUNNER_LOCK_RELATIVE,
                output,
                repository,
            )

        with patch.object(cli, "_run_two_runner_fixed_depth5", return_value=0) as run:
            self.assertEqual(
                cli.main(["run-two-runner-fixed-depth5", str(exact_run)]), 0
            )
            run.assert_called_once_with(
                exact_run,
                cli.TWO_RUNNER_MANIFEST_RELATIVE,
                cli.TWO_RUNNER_LOCK_RELATIVE,
                output,
                repository,
            )


if __name__ == "__main__":
    unittest.main()
