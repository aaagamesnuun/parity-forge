import unittest

from parity_forge.agents import RandomAgent
from parity_forge.audit import exact_audit
from parity_forge.dsl import Player, definition_hash, parse_definition
from parity_forge.play import evaluate_matchup

from tests.support import crossing_definition


class AuditTests(unittest.TestCase):
    def test_exact_audit_is_reproducible_and_preserves_sampled_direction(self) -> None:
        definition = parse_definition(crossing_definition())
        agent = RandomAgent()
        profile = evaluate_matchup(
            definition,
            "weak-random",
            {Player.A: agent, Player.B: agent},
            range(10),
        )
        candidate = {
            "definition_hash": definition_hash(definition),
            "definition": definition.to_dict(),
            "failure_codes": [],
            "play_profiles": [profile.to_dict(include_records=False)],
        }
        first = exact_audit([candidate])
        second = exact_audit([candidate])
        self.assertEqual(first, second)
        self.assertEqual(first["audited_count"], 1)
        self.assertEqual(sum(first["forced_result_histogram"].values()), 1)


if __name__ == "__main__":
    unittest.main()
