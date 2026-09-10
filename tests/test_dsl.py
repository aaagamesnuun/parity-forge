import copy
import json
import unittest
from dataclasses import replace

from parity_forge.dsl import (
    ActionKind,
    ActionSpec,
    DefinitionError,
    Edge,
    GoalKind,
    GoalSpec,
    MOVEMENT_ACTION_KINDS,
    NoLegalActionOutcome,
    Player,
    TerminalPolicy,
    VECTOR_ACTION_KINDS,
    canonical_json,
    definition_hash,
    describe_rules,
    parse_definition,
)

from tests.support import crossing_definition


class DefinitionTests(unittest.TestCase):
    def test_schema_v1_canonical_identity_and_prose_are_frozen(self) -> None:
        definition = parse_definition(crossing_definition())
        self.assertEqual(
            canonical_json(definition),
            '{"board_size":3,"first_player":"A","initial_pieces":['
            '{"owner":"B","piece":"runner","position":[2,1]}],'
            '"max_plies":20,"name":"Crossing Seeds","roles":{'
            '"A":{"action":{"kind":"PLACE","piece":"seed"},"goal":{'
            '"edges":["BOTTOM","TOP"],"kind":"CONNECT_EDGES",'
            '"piece":"seed"}},"B":{"action":{"kind":"MOVE",'
            '"piece":"runner","vectors":[[-1,0],[0,-1],[0,1],[1,0]]},'
            '"goal":{"edge":"TOP","kind":"REACH_EDGE",'
            '"piece":"runner"}}},"schema_version":1}',
        )
        self.assertEqual(
            definition_hash(definition),
            "1c478ea40b8c950ab23e6eb31d46a21b247a2f44d01adcb7adb418022ea0e465",
        )
        self.assertEqual(
            describe_rules(definition),
            (
                "Use a 3 by 3 board.",
                "Start with B runner at (2, 1).",
                "A moves first; turns alternate.",
                "A places one seed in any empty cell.",
                "A wins after its action by orthogonally connecting bottom and top with seed pieces.",
                "B moves one owned runner by one of [(-1, 0), (0, -1), (0, 1), (1, 0)] to an empty in-bounds cell.",
                "B wins after its action when an owned runner reaches the top edge.",
                "A player with no legal action loses.",
                "If no one wins within 20 plies, the game is a draw.",
            ),
        )

    def test_schema_v2_requires_and_canonicalizes_stalemate_draw_policy(self) -> None:
        raw = crossing_definition()
        raw["schema_version"] = 2
        raw["terminal_policy"] = {"no_legal_action": "DRAW"}

        definition = parse_definition(raw)
        reparsed = parse_definition(json.loads(canonical_json(definition)))

        self.assertEqual(definition, reparsed)
        self.assertEqual(definition.to_dict(), reparsed.to_dict())
        self.assertEqual(definition.name, raw["name"])
        self.assertEqual(
            definition.to_dict()["terminal_policy"],
            {"no_legal_action": "DRAW"},
        )
        self.assertEqual(
            canonical_json(definition),
            '{"board_size":3,"first_player":"A","initial_pieces":['
            '{"owner":"B","piece":"runner","position":[2,1]}],'
            '"max_plies":20,"name":"Crossing Seeds","roles":{'
            '"A":{"action":{"kind":"PLACE","piece":"seed"},"goal":{'
            '"edges":["BOTTOM","TOP"],"kind":"CONNECT_EDGES",'
            '"piece":"seed"}},"B":{"action":{"kind":"MOVE",'
            '"piece":"runner","vectors":[[-1,0],[0,-1],[0,1],[1,0]]},'
            '"goal":{"edge":"TOP","kind":"REACH_EDGE",'
            '"piece":"runner"}}},"schema_version":2,'
            '"terminal_policy":{"no_legal_action":"DRAW"}}',
        )
        self.assertEqual(
            definition_hash(definition),
            "84058248624548bff2a0a7f3289cfeebe9e15854888faf2c2233a1133f279173",
        )
        self.assertNotEqual(
            definition_hash(definition),
            definition_hash(parse_definition(crossing_definition())),
        )
        self.assertEqual(
            describe_rules(definition)[-2:],
            (
                "If no one wins within 20 plies, the game is a draw.",
                "If a player has no legal action, the game is a draw; after an "
                "action, goal and ply-limit endings take precedence.",
            ),
        )

    def test_schema_v3_canonical_identity_and_prose_are_frozen(self) -> None:
        raw = crossing_definition()
        raw["schema_version"] = 3
        raw["roles"]["B"]["action"]["kind"] = "MOVE_CAPTURE"

        definition = parse_definition(raw)

        self.assertEqual(
            canonical_json(definition),
            '{"board_size":3,"first_player":"A","initial_pieces":['
            '{"owner":"B","piece":"runner","position":[2,1]}],'
            '"max_plies":20,"name":"Crossing Seeds","roles":{'
            '"A":{"action":{"kind":"PLACE","piece":"seed"},"goal":{'
            '"edges":["BOTTOM","TOP"],"kind":"CONNECT_EDGES",'
            '"piece":"seed"}},"B":{"action":{"kind":"MOVE_CAPTURE",'
            '"piece":"runner","vectors":[[-1,0],[0,-1],[0,1],[1,0]]},'
            '"goal":{"edge":"TOP","kind":"REACH_EDGE",'
            '"piece":"runner"}}},"schema_version":3}',
        )
        self.assertEqual(
            definition_hash(definition),
            "8eff6699c4baa64cfd20ae3e2e9ba4fe3f5a16c1e2686ca8025fb6ba41fa59eb",
        )
        self.assertEqual(
            describe_rules(definition),
            (
                "Use a 3 by 3 board.",
                "Start with B runner at (2, 1).",
                "A moves first; turns alternate.",
                "A places one seed in any empty cell.",
                "A wins after its action by orthogonally connecting bottom and top with seed pieces.",
                "B moves one owned runner by one of [(-1, 0), (0, -1), (0, 1), (1, 0)] to an empty in-bounds cell.",
                "B may also move that runner by one of those vectors into an "
                "in-bounds cell occupied by one opponent piece, remove that "
                "piece, and finish the move there.",
                "B wins after its action when an owned runner reaches the top edge.",
                "A player with no legal action loses.",
                "If no one wins within 20 plies, the game is a draw.",
            ),
        )

    def test_schema_v4_push_is_canonical_and_describes_cross_role_terminals(self) -> None:
        raw = crossing_definition()
        raw["schema_version"] = 4
        raw["name"] = "Pushing Crossing"
        raw["roles"]["A"]["action"] = {
            "kind": "PUSH",
            "piece": "seed",
            "vectors": [[1, 0], [0, 1], [-1, 0], [0, -1]],
        }

        definition = parse_definition(raw)
        reparsed = parse_definition(json.loads(canonical_json(definition)))

        self.assertEqual(definition, reparsed)
        self.assertEqual(
            canonical_json(definition),
            '{"board_size":3,"first_player":"A","initial_pieces":['
            '{"owner":"B","piece":"runner","position":[2,1]}],'
            '"max_plies":20,"name":"Pushing Crossing","roles":{'
            '"A":{"action":{"kind":"PUSH","piece":"seed","vectors":'
            '[[-1,0],[0,-1],[0,1],[1,0]]},"goal":{"edges":'
            '["BOTTOM","TOP"],"kind":"CONNECT_EDGES","piece":"seed"}},'
            '"B":{"action":{"kind":"MOVE","piece":"runner","vectors":'
            '[[-1,0],[0,-1],[0,1],[1,0]]},"goal":{"edge":"TOP",'
            '"kind":"REACH_EDGE","piece":"runner"}}},"schema_version":4}',
        )
        self.assertEqual(
            definition_hash(definition),
            "e81605ebb3709c1b97069b141ea2ee70e58c3c74130f0403293493e0a9fe1c3f",
        )
        self.assertEqual(
            describe_rules(definition),
            (
                "Use a 3 by 3 board.",
                "Start with B runner at (2, 1).",
                "A moves first; turns alternate.",
                "A moves one owned seed by one of [(-1, 0), (0, -1), (0, 1), (1, 0)] to an empty in-bounds cell.",
                "A may instead use one of those vectors to push one adjacent "
                "opponent piece: the seed enters the opponent piece's cell, "
                "and that piece moves one more cell along the same vector; the "
                "landing cell must be in bounds and empty.",
                "A's goal is to orthogonally connect bottom and top with owned seed pieces.",
                "B moves one owned runner by one of [(-1, 0), (0, -1), (0, 1), (1, 0)] to an empty in-bounds cell.",
                "B's goal is for an owned runner to reach the top edge.",
                "Initially, check A's goal first and B's goal second; the owner "
                "of the first satisfied goal wins.",
                "If neither initial goal is satisfied and A has no legal action, B wins.",
                "After each action, check the actor's goal first and the "
                "opponent's goal second; the owner of the first satisfied goal "
                "wins.",
                "If neither goal is satisfied, reaching 20 plies is a draw "
                "before checking the next player's legal actions.",
                "Otherwise, a next player with no legal action loses.",
            ),
        )

    def test_schema_v4_swap_is_canonical_and_describes_exchange(self) -> None:
        raw = crossing_definition()
        raw["schema_version"] = 4
        raw["name"] = "Swapping Crossing"
        raw["roles"]["A"]["action"] = {
            "kind": "SWAP",
            "piece": "seed",
            "vectors": [[1, 0], [0, 1], [-1, 0], [0, -1]],
        }

        definition = parse_definition(raw)
        reparsed = parse_definition(json.loads(canonical_json(definition)))

        self.assertEqual(definition, reparsed)
        self.assertEqual(
            canonical_json(definition),
            '{"board_size":3,"first_player":"A","initial_pieces":['
            '{"owner":"B","piece":"runner","position":[2,1]}],'
            '"max_plies":20,"name":"Swapping Crossing","roles":{'
            '"A":{"action":{"kind":"SWAP","piece":"seed","vectors":'
            '[[-1,0],[0,-1],[0,1],[1,0]]},"goal":{"edges":'
            '["BOTTOM","TOP"],"kind":"CONNECT_EDGES","piece":"seed"}},'
            '"B":{"action":{"kind":"MOVE","piece":"runner","vectors":'
            '[[-1,0],[0,-1],[0,1],[1,0]]},"goal":{"edge":"TOP",'
            '"kind":"REACH_EDGE","piece":"runner"}}},"schema_version":4}',
        )
        self.assertEqual(
            definition_hash(definition),
            "c8dba41bb2e97e5fcc5dd119a415da2ee74b68e196f38c70d2aada292de73ba2",
        )
        self.assertEqual(
            describe_rules(definition),
            (
                "Use a 3 by 3 board.",
                "Start with B runner at (2, 1).",
                "A moves first; turns alternate.",
                "A moves one owned seed by one of [(-1, 0), (0, -1), (0, 1), (1, 0)] to an empty in-bounds cell.",
                "A may instead use one of those vectors to swap that seed with "
                "one adjacent opponent piece; the two pieces exchange positions.",
                "A's goal is to orthogonally connect bottom and top with owned seed pieces.",
                "B moves one owned runner by one of [(-1, 0), (0, -1), (0, 1), (1, 0)] to an empty in-bounds cell.",
                "B's goal is for an owned runner to reach the top edge.",
                "Initially, check A's goal first and B's goal second; the owner "
                "of the first satisfied goal wins.",
                "If neither initial goal is satisfied and A has no legal action, B wins.",
                "After each action, check the actor's goal first and the "
                "opponent's goal second; the owner of the first satisfied goal "
                "wins.",
                "If neither goal is satisfied, reaching 20 plies is a draw "
                "before checking the next player's legal actions.",
                "Otherwise, a next player with no legal action loses.",
            ),
        )

    def test_schema_v4_hop_is_canonical_and_describes_leap_dependency(self) -> None:
        raw = crossing_definition()
        raw["schema_version"] = 4
        raw["name"] = "Hopping Crossing"
        raw["roles"]["A"]["action"] = {
            "kind": "HOP",
            "piece": "seed",
            "vectors": [[1, 0], [0, 1], [-1, 0], [0, -1]],
        }

        definition = parse_definition(raw)
        reparsed = parse_definition(json.loads(canonical_json(definition)))

        self.assertEqual(definition, reparsed)
        self.assertEqual(
            canonical_json(definition),
            '{"board_size":3,"first_player":"A","initial_pieces":['
            '{"owner":"B","piece":"runner","position":[2,1]}],'
            '"max_plies":20,"name":"Hopping Crossing","roles":{'
            '"A":{"action":{"kind":"HOP","piece":"seed","vectors":'
            '[[-1,0],[0,-1],[0,1],[1,0]]},"goal":{"edges":'
            '["BOTTOM","TOP"],"kind":"CONNECT_EDGES","piece":"seed"}},'
            '"B":{"action":{"kind":"MOVE","piece":"runner","vectors":'
            '[[-1,0],[0,-1],[0,1],[1,0]]},"goal":{"edge":"TOP",'
            '"kind":"REACH_EDGE","piece":"runner"}}},"schema_version":4}',
        )
        self.assertEqual(
            definition_hash(definition),
            "4ad5598c0b5a15cb24fa9b79747634c7a8ea87fa909f40cb23ad2181528015ce",
        )
        self.assertEqual(
            describe_rules(definition),
            (
                "Use a 3 by 3 board.",
                "Start with B runner at (2, 1).",
                "A moves first; turns alternate.",
                "A moves one owned seed by one of [(-1, 0), (0, -1), (0, 1), (1, 0)] to an empty in-bounds cell.",
                "A may instead use one of those vectors to hop that seed over "
                "exactly one adjacent occupied piece, regardless of owner or "
                "kind, to the empty in-bounds cell one more step along the same "
                "vector; the jumped piece is unchanged, and chained hops are "
                "not allowed.",
                "A's goal is to orthogonally connect bottom and top with owned seed pieces.",
                "B moves one owned runner by one of [(-1, 0), (0, -1), (0, 1), (1, 0)] to an empty in-bounds cell.",
                "B's goal is for an owned runner to reach the top edge.",
                "Initially, check A's goal first and B's goal second; the owner "
                "of the first satisfied goal wins.",
                "If neither initial goal is satisfied and A has no legal action, B wins.",
                "After each action, check the actor's goal first and the "
                "opponent's goal second; the owner of the first satisfied goal "
                "wins.",
                "If neither goal is satisfied, reaching 20 plies is a draw "
                "before checking the next player's legal actions.",
                "Otherwise, a next player with no legal action loses.",
            ),
        )

    def test_schema_v4_convert_is_canonical_and_describes_ownership_transfer(self) -> None:
        raw = crossing_definition()
        raw["schema_version"] = 4
        raw["name"] = "Converting Crossing"
        raw["roles"]["A"]["action"] = {
            "kind": "CONVERT",
            "piece": "seed",
            "vectors": [[1, 0], [0, 1], [-1, 0], [0, -1]],
        }

        definition = parse_definition(raw)
        reparsed = parse_definition(json.loads(canonical_json(definition)))

        self.assertEqual(definition, reparsed)
        self.assertEqual(
            canonical_json(definition),
            '{"board_size":3,"first_player":"A","initial_pieces":['
            '{"owner":"B","piece":"runner","position":[2,1]}],'
            '"max_plies":20,"name":"Converting Crossing","roles":{'
            '"A":{"action":{"kind":"CONVERT","piece":"seed","vectors":'
            '[[-1,0],[0,-1],[0,1],[1,0]]},"goal":{"edges":'
            '["BOTTOM","TOP"],"kind":"CONNECT_EDGES","piece":"seed"}},'
            '"B":{"action":{"kind":"MOVE","piece":"runner","vectors":'
            '[[-1,0],[0,-1],[0,1],[1,0]]},"goal":{"edge":"TOP",'
            '"kind":"REACH_EDGE","piece":"runner"}}},"schema_version":4}',
        )
        self.assertEqual(
            definition_hash(definition),
            "9233c363533156baa3553832d277810658256b65ddac28490af19b15e5478429",
        )
        self.assertEqual(
            describe_rules(definition),
            (
                "Use a 3 by 3 board.",
                "Start with B runner at (2, 1).",
                "A moves first; turns alternate.",
                "A uses one owned seed, which stays in its cell, to convert "
                "exactly one adjacent opponent piece, regardless of kind, by "
                "one of [(-1, 0), (0, -1), (0, 1), (1, 0)] into an A-owned "
                "seed in that same target cell; both positions are unchanged, "
                "and empty cells, friendly pieces, ranged conversions, and "
                "multi-target conversions are not allowed.",
                "A's goal is to orthogonally connect bottom and top with owned seed pieces.",
                "B moves one owned runner by one of [(-1, 0), (0, -1), (0, 1), (1, 0)] to an empty in-bounds cell.",
                "B's goal is for an owned runner to reach the top edge.",
                "Initially, check A's goal first and B's goal second; the owner "
                "of the first satisfied goal wins.",
                "If neither initial goal is satisfied and A has no legal action, B wins.",
                "After each action, check the actor's goal first and the "
                "opponent's goal second; the owner of the first satisfied goal "
                "wins.",
                "If neither goal is satisfied, reaching 20 plies is a draw "
                "before checking the next player's legal actions.",
                "Otherwise, a next player with no legal action loses.",
            ),
        )

    def test_schema_v4_eliminate_is_canonical_and_describes_opponent_target(self) -> None:
        raw = crossing_definition()
        raw["schema_version"] = 4
        raw["name"] = "Elimination Crossing"
        raw["roles"]["A"]["goal"] = {
            "kind": "ELIMINATE",
            "piece": "runner",
        }

        definition = parse_definition(raw)
        reparsed = parse_definition(json.loads(canonical_json(definition)))

        self.assertEqual(definition, reparsed)
        self.assertEqual(definition.role(Player.A).goal.edges, ())
        self.assertIsNone(definition.role(Player.A).goal.edge)
        self.assertEqual(
            canonical_json(definition),
            '{"board_size":3,"first_player":"A","initial_pieces":['
            '{"owner":"B","piece":"runner","position":[2,1]}],'
            '"max_plies":20,"name":"Elimination Crossing","roles":{'
            '"A":{"action":{"kind":"PLACE","piece":"seed"},"goal":{'
            '"kind":"ELIMINATE","piece":"runner"}},"B":{"action":{'
            '"kind":"MOVE","piece":"runner","vectors":['
            '[-1,0],[0,-1],[0,1],[1,0]]},"goal":{"edge":"TOP",'
            '"kind":"REACH_EDGE","piece":"runner"}}},"schema_version":4}',
        )
        self.assertEqual(
            definition_hash(definition),
            "6c1aa7c031eaf54772f128bfdfd6dc0305a3e3b18c9b9f0898875c03f51f94c4",
        )
        self.assertEqual(
            describe_rules(definition),
            (
                "Use a 3 by 3 board.",
                "Start with B runner at (2, 1).",
                "A moves first; turns alternate.",
                "A places one seed in any empty cell.",
                "A's goal is to have no opponent-owned runner pieces remaining.",
                "B moves one owned runner by one of [(-1, 0), (0, -1), (0, 1), (1, 0)] to an empty in-bounds cell.",
                "B's goal is for an owned runner to reach the top edge.",
                "Initially, check A's goal first and B's goal second; the owner "
                "of the first satisfied goal wins.",
                "If neither initial goal is satisfied and A has no legal action, B wins.",
                "After each action, check the actor's goal first and the "
                "opponent's goal second; the owner of the first satisfied goal "
                "wins.",
                "If neither goal is satisfied, reaching 20 plies is a draw "
                "before checking the next player's legal actions.",
                "Otherwise, a next player with no legal action loses.",
            ),
        )

    def test_direct_construction_requires_a_supported_schema_policy_pair(self) -> None:
        v1 = parse_definition(crossing_definition())
        policy = TerminalPolicy(no_legal_action=NoLegalActionOutcome.DRAW)

        with self.assertRaisesRegex(DefinitionError, "require.*MOVE_CAPTURE"):
            replace(v1, schema_version=3)
        with self.assertRaisesRegex(DefinitionError, "unsupported schema_version"):
            replace(v1, schema_version=True)
        with self.assertRaisesRegex(DefinitionError, "schema-v1.*terminal_policy"):
            replace(v1, terminal_policy=policy)
        with self.assertRaisesRegex(DefinitionError, "schema-v2.*require"):
            replace(v1, schema_version=2)

        v2_raw = crossing_definition()
        v2_raw["schema_version"] = 2
        v2_raw["terminal_policy"] = {"no_legal_action": "DRAW"}
        v2 = parse_definition(v2_raw)
        with self.assertRaisesRegex(DefinitionError, "schema-v2.*require"):
            replace(v2, terminal_policy=None)
        with self.assertRaisesRegex(DefinitionError, "schema-v1.*terminal_policy"):
            replace(v2, schema_version=1)

        capture_roles = tuple(
            (
                player,
                replace(
                    role,
                    action=replace(role.action, kind=ActionKind.MOVE_CAPTURE),
                ),
            )
            if player.value == "B"
            else (player, role)
            for player, role in v1.roles
        )
        with self.assertRaisesRegex(DefinitionError, "unsupported action kind"):
            replace(v1, roles=capture_roles)
        with self.assertRaisesRegex(DefinitionError, "unsupported action kind"):
            replace(v2, roles=capture_roles)
        v3 = replace(v1, schema_version=3, roles=capture_roles)
        self.assertEqual(v3.schema_version, 3)
        self.assertIsNone(v3.terminal_policy)
        with self.assertRaisesRegex(DefinitionError, "schema-v3.*terminal_policy"):
            replace(v3, terminal_policy=policy)

        push_roles = tuple(
            (
                player,
                replace(role, action=replace(role.action, kind=ActionKind.PUSH)),
            )
            if player.value == "B"
            else (player, role)
            for player, role in v1.roles
        )
        v4 = replace(v1, schema_version=4, roles=push_roles)
        self.assertEqual(v4.schema_version, 4)
        self.assertIsNone(v4.terminal_policy)
        with self.assertRaisesRegex(DefinitionError, "schema-v4.*terminal_policy"):
            replace(v4, terminal_policy=policy)
        with self.assertRaisesRegex(
            DefinitionError, "schema-v4.*require.*PUSH, SWAP, HOP, or CONVERT"
        ):
            replace(v1, schema_version=4)
        with self.assertRaisesRegex(DefinitionError, "unsupported action kind"):
            replace(v3, schema_version=3, roles=push_roles)

        swap_roles = tuple(
            (
                player,
                replace(role, action=replace(role.action, kind=ActionKind.SWAP)),
            )
            if player.value == "B"
            else (player, role)
            for player, role in v1.roles
        )
        v4_swap = replace(v1, schema_version=4, roles=swap_roles)
        self.assertIs(v4_swap.role(Player.B).action.kind, ActionKind.SWAP)
        with self.assertRaisesRegex(DefinitionError, "schema-v4.*terminal_policy"):
            replace(v4_swap, terminal_policy=policy)
        with self.assertRaisesRegex(DefinitionError, "unsupported action kind"):
            replace(v3, schema_version=3, roles=swap_roles)

        hop_roles = tuple(
            (
                player,
                replace(role, action=replace(role.action, kind=ActionKind.HOP)),
            )
            if player.value == "B"
            else (player, role)
            for player, role in v1.roles
        )
        v4_hop = replace(v1, schema_version=4, roles=hop_roles)
        self.assertIs(v4_hop.role(Player.B).action.kind, ActionKind.HOP)
        with self.assertRaisesRegex(DefinitionError, "schema-v4.*terminal_policy"):
            replace(v4_hop, terminal_policy=policy)
        with self.assertRaisesRegex(DefinitionError, "unsupported action kind"):
            replace(v3, schema_version=3, roles=hop_roles)

        convert_roles = tuple(
            (
                player,
                replace(role, action=replace(role.action, kind=ActionKind.CONVERT)),
            )
            if player.value == "B"
            else (player, role)
            for player, role in v1.roles
        )
        v4_convert = replace(v1, schema_version=4, roles=convert_roles)
        self.assertIs(v4_convert.role(Player.B).action.kind, ActionKind.CONVERT)
        with self.assertRaisesRegex(DefinitionError, "schema-v4.*terminal_policy"):
            replace(v4_convert, terminal_policy=policy)
        with self.assertRaisesRegex(DefinitionError, "unsupported action kind"):
            replace(v3, schema_version=3, roles=convert_roles)

    def test_direct_eliminate_goal_is_strict_and_schema_v4_only(self) -> None:
        class StringSubclass(str):
            pass

        eliminate = GoalSpec(kind=GoalKind.ELIMINATE, piece="runner")
        self.assertEqual(
            eliminate.to_dict(),
            {"kind": "ELIMINATE", "piece": "runner"},
        )
        self.assertEqual(eliminate.edges, ())
        self.assertIsNone(eliminate.edge)

        v1 = parse_definition(crossing_definition())
        eliminate_roles = tuple(
            (
                player,
                replace(role, goal=eliminate),
            )
            if player is Player.A
            else (player, role)
            for player, role in v1.roles
        )
        with self.assertRaisesRegex(DefinitionError, "schema-v1.*unsupported goal"):
            replace(v1, roles=eliminate_roles)

        v2_raw = crossing_definition()
        v2_raw["schema_version"] = 2
        v2_raw["terminal_policy"] = {"no_legal_action": "DRAW"}
        v2 = parse_definition(v2_raw)
        with self.assertRaisesRegex(DefinitionError, "schema-v2.*unsupported goal"):
            replace(v2, roles=eliminate_roles)

        v3_raw = crossing_definition()
        v3_raw["schema_version"] = 3
        v3_raw["roles"]["B"]["action"]["kind"] = "MOVE_CAPTURE"
        v3 = parse_definition(v3_raw)
        v3_eliminate_roles = tuple(
            (player, replace(role, goal=eliminate))
            if player is Player.A
            else (player, role)
            for player, role in v3.roles
        )
        with self.assertRaisesRegex(DefinitionError, "schema-v3.*unsupported goal"):
            replace(v3, roles=v3_eliminate_roles)

        v4 = replace(v1, schema_version=4, roles=eliminate_roles)
        self.assertIs(v4.role(Player.A).goal.kind, GoalKind.ELIMINATE)
        invalid_goals = (
            (
                GoalSpec(
                    kind=GoalKind.ELIMINATE,
                    piece="runner",
                    edges=(Edge.BOTTOM, Edge.TOP),
                ),
                "cannot define edges",
            ),
            (
                GoalSpec(
                    kind=GoalKind.ELIMINATE,
                    piece="runner",
                    edge=Edge.TOP,
                ),
                "cannot define edge",
            ),
            (
                GoalSpec(kind=GoalKind.ELIMINATE, piece="Runner"),
                "piece must match",
            ),
            (
                GoalSpec(
                    kind=GoalKind.ELIMINATE,
                    piece=StringSubclass("runner"),
                ),
                "piece must match",
            ),
            (
                GoalSpec(  # type: ignore[arg-type]
                    kind=GoalKind.ELIMINATE,
                    piece="runner",
                    edges=[],
                ),
                "edges must be a tuple",
            ),
            (
                GoalSpec(  # type: ignore[arg-type]
                    kind="ELIMINATE",
                    piece="runner",
                ),
                "kind must be a GoalKind",
            ),
        )
        for goal, message in invalid_goals:
            with self.subTest(goal=goal):
                bad_roles = tuple(
                    (player, replace(role, goal=goal))
                    if player is Player.A
                    else (player, role)
                    for player, role in v4.roles
                )
                with self.assertRaisesRegex(DefinitionError, message):
                    replace(v4, roles=bad_roles)

        with self.assertRaisesRegex(DefinitionError, "goal kind must be a GoalKind"):
            GoalSpec(  # type: ignore[arg-type]
                kind="ELIMINATE",
                piece="runner",
            ).to_dict()

    def test_schema_v4_eliminate_hidden_goal_field_is_rejected_at_boundaries(self) -> None:
        raw = crossing_definition()
        raw["schema_version"] = 4
        raw["roles"]["A"]["goal"] = {
            "kind": "ELIMINATE",
            "piece": "runner",
        }
        definition = parse_definition(raw)
        object.__setattr__(
            definition.role(Player.A).goal,
            "predicate",
            lambda: True,
        )

        for operation in (canonical_json, definition_hash, describe_rules):
            with self.subTest(operation=operation.__name__):
                with self.assertRaisesRegex(DefinitionError, "parser-normalized"):
                    operation(definition)

    def test_direct_push_action_requires_canonical_one_step_vectors(self) -> None:
        class StringSubclass(str):
            pass

        with self.assertRaisesRegex(DefinitionError, "must be an ActionKind"):
            ActionSpec(
                kind="PUSH",  # type: ignore[arg-type]
                piece="pusher",
                vectors=((-1, 0),),
            )
        with self.assertRaisesRegex(DefinitionError, "non-empty tuple"):
            ActionSpec(kind=ActionKind.PUSH, piece="pusher")
        with self.assertRaisesRegex(DefinitionError, "two-integer tuples"):
            ActionSpec(
                kind=ActionKind.PUSH,
                piece="pusher",
                vectors=((True, 0),),
            )
        with self.assertRaisesRegex(DefinitionError, "one-step"):
            ActionSpec(
                kind=ActionKind.PUSH,
                piece="pusher",
                vectors=((2, 0),),
            )
        with self.assertRaisesRegex(DefinitionError, "duplicates"):
            ActionSpec(
                kind=ActionKind.PUSH,
                piece="pusher",
                vectors=((-1, 0), (-1, 0)),
            )
        with self.assertRaisesRegex(DefinitionError, "canonically sorted"):
            ActionSpec(
                kind=ActionKind.PUSH,
                piece="pusher",
                vectors=((1, 0), (-1, 0)),
            )
        with self.assertRaisesRegex(DefinitionError, "piece must match"):
            ActionSpec(
                kind=ActionKind.PUSH,
                piece="Pusher",
                vectors=((-1, 0),),
            )
        with self.assertRaisesRegex(DefinitionError, "piece must match"):
            ActionSpec(
                kind=ActionKind.PUSH,
                piece=StringSubclass("pusher"),
                vectors=((-1, 0),),
            )

    def test_direct_swap_action_requires_canonical_one_step_vectors(self) -> None:
        class StringSubclass(str):
            pass

        valid = ActionSpec(
            kind=ActionKind.SWAP,
            piece="swapper",
            vectors=((-1, 0), (0, 1)),
        )
        self.assertEqual(
            valid.to_dict(),
            {
                "kind": "SWAP",
                "piece": "swapper",
                "vectors": [[-1, 0], [0, 1]],
            },
        )
        cases = (
            ({"vectors": ()}, "non-empty tuple"),
            ({"vectors": ((True, 0),)}, "two-integer tuples"),
            ({"vectors": ((0, 0),)}, "cannot contain"),
            ({"vectors": ((2, 0),)}, "one-step"),
            ({"vectors": ((-1, 0), (-1, 0))}, "duplicates"),
            ({"vectors": ((1, 0), (-1, 0))}, "canonically sorted"),
            ({"piece": "Swapper", "vectors": ((-1, 0),)}, "piece must match"),
            (
                {"piece": StringSubclass("swapper"), "vectors": ((-1, 0),)},
                "piece must match",
            ),
        )
        for changes, message in cases:
            with self.subTest(changes=changes):
                arguments = {
                    "kind": ActionKind.SWAP,
                    "piece": "swapper",
                    "vectors": ((-1, 0),),
                }
                arguments.update(changes)
                with self.assertRaisesRegex(DefinitionError, message):
                    ActionSpec(**arguments)

    def test_direct_hop_action_requires_canonical_one_step_vectors(self) -> None:
        class StringSubclass(str):
            pass

        valid = ActionSpec(
            kind=ActionKind.HOP,
            piece="hopper",
            vectors=((-1, 0), (0, 1)),
        )
        self.assertEqual(
            valid.to_dict(),
            {
                "kind": "HOP",
                "piece": "hopper",
                "vectors": [[-1, 0], [0, 1]],
            },
        )
        cases = (
            ({"vectors": ()}, "non-empty tuple"),
            ({"vectors": ((True, 0),)}, "two-integer tuples"),
            ({"vectors": ((0, 0),)}, "cannot contain"),
            ({"vectors": ((2, 0),)}, "one-step"),
            ({"vectors": ((-1, 0), (-1, 0))}, "duplicates"),
            ({"vectors": ((1, 0), (-1, 0))}, "canonically sorted"),
            ({"piece": "Hopper", "vectors": ((-1, 0),)}, "piece must match"),
            (
                {"piece": StringSubclass("hopper"), "vectors": ((-1, 0),)},
                "piece must match",
            ),
        )
        for changes, message in cases:
            with self.subTest(changes=changes):
                arguments = {
                    "kind": ActionKind.HOP,
                    "piece": "hopper",
                    "vectors": ((-1, 0),),
                }
                arguments.update(changes)
                with self.assertRaisesRegex(DefinitionError, message):
                    ActionSpec(**arguments)

    def test_direct_convert_action_requires_canonical_one_step_vectors(self) -> None:
        class StringSubclass(str):
            pass

        valid = ActionSpec(
            kind=ActionKind.CONVERT,
            piece="converter",
            vectors=((-1, 0), (0, 1)),
        )
        self.assertEqual(
            valid.to_dict(),
            {
                "kind": "CONVERT",
                "piece": "converter",
                "vectors": [[-1, 0], [0, 1]],
            },
        )
        self.assertEqual(
            MOVEMENT_ACTION_KINDS,
            frozenset(
                (
                    ActionKind.MOVE,
                    ActionKind.MOVE_CAPTURE,
                    ActionKind.PUSH,
                    ActionKind.SWAP,
                    ActionKind.HOP,
                )
            ),
        )
        self.assertNotIn(ActionKind.CONVERT, MOVEMENT_ACTION_KINDS)
        self.assertEqual(
            VECTOR_ACTION_KINDS,
            MOVEMENT_ACTION_KINDS | frozenset((ActionKind.CONVERT,)),
        )
        with self.assertRaisesRegex(DefinitionError, "must be an ActionKind"):
            ActionSpec(
                kind="CONVERT",  # type: ignore[arg-type]
                piece="converter",
                vectors=((-1, 0),),
            )
        cases = (
            ({"vectors": ()}, "non-empty tuple"),
            ({"vectors": ((True, 0),)}, "two-integer tuples"),
            ({"vectors": ((0, 0),)}, "cannot contain"),
            ({"vectors": ((2, 0),)}, "one-step"),
            ({"vectors": ((-1, 0), (-1, 0))}, "duplicates"),
            ({"vectors": ((1, 0), (-1, 0))}, "canonically sorted"),
            ({"piece": "Converter", "vectors": ((-1, 0),)}, "piece must match"),
            (
                {"piece": StringSubclass("converter"), "vectors": ((-1, 0),)},
                "piece must match",
            ),
        )
        for changes, message in cases:
            with self.subTest(changes=changes):
                arguments = {
                    "kind": ActionKind.CONVERT,
                    "piece": "converter",
                    "vectors": ((-1, 0),),
                }
                arguments.update(changes)
                with self.assertRaisesRegex(DefinitionError, message):
                    ActionSpec(**arguments)

    def test_schema_v4_direct_construction_requires_parser_normalized_fields(self) -> None:
        raw = crossing_definition()
        raw["schema_version"] = 4
        raw["roles"]["A"]["action"] = {
            "kind": "PUSH",
            "piece": "seed",
            "vectors": [[-1, 0]],
        }
        definition = parse_definition(raw)

        bad_move = ActionSpec(
            kind=ActionKind.MOVE,
            piece="BAD!",
            vectors=((True, 0),),
        )
        bad_roles = tuple(
            (player, replace(role, action=bad_move))
            if player.value == "B"
            else (player, role)
            for player, role in definition.roles
        )
        invalid_replacements = (
            {"roles": bad_roles},
            {"roles": list(definition.roles)},
            {"roles": ((definition.roles[0][0], definition.roles[0][1]),) * 2},
            {
                "roles": (
                    ("A", definition.roles[0][1]),
                    ("B", definition.roles[1][1]),
                )
            },
            {"initial_pieces": list(definition.initial_pieces)},
            {"board_size": True},
            {"max_plies": float("nan")},
            {"first_player": "A"},
        )
        for changes in invalid_replacements:
            with self.subTest(changes=changes):
                with self.assertRaises(DefinitionError):
                    replace(definition, **changes)

    def test_canonical_and_prose_boundaries_reject_forged_definitions(self) -> None:
        raw = crossing_definition()
        raw["schema_version"] = 4
        raw["roles"]["A"]["action"] = {
            "kind": "PUSH",
            "piece": "seed",
            "vectors": [[-1, 0], [0, -1]],
        }
        definition = parse_definition(raw)
        role_a = definition.role(Player.A)
        object.__setattr__(
            role_a.action,
            "vectors",
            tuple(reversed(role_a.action.vectors)),
        )

        for operation in (canonical_json, definition_hash, describe_rules):
            with self.subTest(operation=operation.__name__):
                with self.assertRaisesRegex(DefinitionError, "parser-normalized"):
                    operation(definition)

        mutable_definition = parse_definition(raw)
        object.__setattr__(
            mutable_definition,
            "initial_pieces",
            list(mutable_definition.initial_pieces),
        )
        with self.assertRaisesRegex(DefinitionError, "parser-normalized"):
            definition_hash(mutable_definition)

        hidden_definition = parse_definition(raw)
        object.__setattr__(
            hidden_definition.role(Player.A).action,
            "effect",
            lambda: None,
        )
        for operation in (canonical_json, definition_hash, describe_rules):
            with self.subTest(operation=operation.__name__, mutation="hidden"):
                with self.assertRaisesRegex(DefinitionError, "parser-normalized"):
                    operation(hidden_definition)

        class FakeDefinition:
            def to_dict(self):
                return raw

        with self.assertRaises(TypeError):
            canonical_json(FakeDefinition())  # type: ignore[arg-type]

    def test_legacy_canonical_boundaries_reject_mutable_or_hidden_fields(self) -> None:
        definition = parse_definition(crossing_definition())
        mutable = replace(
            definition,
            initial_pieces=list(definition.initial_pieces),
        )
        hidden_vectors = tuple(
            (
                player,
                replace(
                    role,
                    action=replace(role.action, vectors=((1, 0),)),
                ),
            )
            if player is Player.A
            else (player, role)
            for player, role in definition.roles
        )
        hidden = replace(definition, roles=hidden_vectors)

        for forged in (mutable, hidden):
            with self.subTest(forged=forged):
                for operation in (canonical_json, definition_hash, describe_rules):
                    with self.assertRaisesRegex(
                        DefinitionError, "parser-normalized"
                    ):
                        operation(forged)

    def test_schema_versions_reject_implicit_or_unknown_terminal_policy(self) -> None:
        missing = crossing_definition()
        missing["schema_version"] = 2
        with self.assertRaisesRegex(DefinitionError, "missing.*terminal_policy"):
            parse_definition(missing)

        v1_extension = crossing_definition()
        v1_extension["terminal_policy"] = {"no_legal_action": "DRAW"}
        with self.assertRaisesRegex(DefinitionError, "unknown.*terminal_policy"):
            parse_definition(v1_extension)

        invalid = crossing_definition()
        invalid["schema_version"] = 2
        invalid["terminal_policy"] = {"no_legal_action": "LOSS"}
        with self.assertRaisesRegex(DefinitionError, "must be one of.*DRAW"):
            parse_definition(invalid)

        wrong_type = crossing_definition()
        wrong_type["schema_version"] = 2
        wrong_type["terminal_policy"] = ["DRAW"]
        with self.assertRaisesRegex(DefinitionError, "terminal_policy must be an object"):
            parse_definition(wrong_type)

        extended = crossing_definition()
        extended["schema_version"] = 2
        extended["terminal_policy"] = {
            "no_legal_action": "DRAW",
            "repetition": "DRAW",
        }
        with self.assertRaisesRegex(DefinitionError, "unknown.*repetition"):
            parse_definition(extended)

        v4_policy = crossing_definition()
        v4_policy["schema_version"] = 4
        v4_policy["roles"]["A"]["action"] = {
            "kind": "PUSH",
            "piece": "seed",
            "vectors": [[-1, 0]],
        }
        v4_policy["terminal_policy"] = {"no_legal_action": "DRAW"}
        with self.assertRaisesRegex(DefinitionError, "unknown.*terminal_policy"):
            parse_definition(v4_policy)

        bool_version = crossing_definition()
        bool_version["schema_version"] = True
        with self.assertRaisesRegex(DefinitionError, "must be an integer"):
            parse_definition(bool_version)

        unsupported = crossing_definition()
        unsupported["schema_version"] = 5
        with self.assertRaisesRegex(DefinitionError, "one of.*1, 2, 3, 4"):
            parse_definition(unsupported)

    def test_schema_v4_requires_a_special_action_and_rejects_unknown_fields(self) -> None:
        no_special = crossing_definition()
        no_special["schema_version"] = 4
        with self.assertRaisesRegex(
            DefinitionError, "require.*PUSH, SWAP, HOP, or CONVERT"
        ):
            parse_definition(no_special)

        push_in_v3 = crossing_definition()
        push_in_v3["schema_version"] = 3
        push_in_v3["roles"]["B"]["action"]["kind"] = "PUSH"
        with self.assertRaisesRegex(DefinitionError, "must be one of"):
            parse_definition(push_in_v3)

        extended = crossing_definition()
        extended["schema_version"] = 4
        extended["roles"]["A"]["action"] = {
            "kind": "PUSH",
            "piece": "seed",
            "vectors": [[-1, 0]],
            "chain": True,
        }
        with self.assertRaisesRegex(DefinitionError, "unknown.*chain"):
            parse_definition(extended)

        swap_in_v3 = crossing_definition()
        swap_in_v3["schema_version"] = 3
        swap_in_v3["roles"]["B"]["action"]["kind"] = "SWAP"
        with self.assertRaisesRegex(DefinitionError, "must be one of"):
            parse_definition(swap_in_v3)

        swap_extended = crossing_definition()
        swap_extended["schema_version"] = 4
        swap_extended["roles"]["A"]["action"] = {
            "kind": "SWAP",
            "piece": "seed",
            "vectors": [[-1, 0]],
            "multi_piece": False,
        }
        with self.assertRaisesRegex(DefinitionError, "unknown.*multi_piece"):
            parse_definition(swap_extended)

        hop_extended = crossing_definition()
        hop_extended["schema_version"] = 4
        hop_extended["roles"]["A"]["action"] = {
            "kind": "HOP",
            "piece": "seed",
            "vectors": [[-1, 0]],
            "chain": False,
        }
        with self.assertRaisesRegex(DefinitionError, "unknown.*chain"):
            parse_definition(hop_extended)

        convert_extended = crossing_definition()
        convert_extended["schema_version"] = 4
        convert_extended["roles"]["A"]["action"] = {
            "kind": "CONVERT",
            "piece": "seed",
            "vectors": [[-1, 0]],
            "target_kind": "runner",
        }
        with self.assertRaisesRegex(DefinitionError, "unknown.*target_kind"):
            parse_definition(convert_extended)

    def test_schema_v1_through_v3_reject_hop(self) -> None:
        for schema_version in (1, 2, 3):
            with self.subTest(schema_version=schema_version):
                raw = crossing_definition()
                raw["schema_version"] = schema_version
                raw["roles"]["B"]["action"]["kind"] = "HOP"
                if schema_version == 2:
                    raw["terminal_policy"] = {"no_legal_action": "DRAW"}
                with self.assertRaisesRegex(DefinitionError, "must be one of"):
                    parse_definition(raw)

    def test_schema_v1_through_v3_reject_convert(self) -> None:
        for schema_version in (1, 2, 3):
            with self.subTest(schema_version=schema_version):
                raw = crossing_definition()
                raw["schema_version"] = schema_version
                raw["roles"]["B"]["action"]["kind"] = "CONVERT"
                if schema_version == 2:
                    raw["terminal_policy"] = {"no_legal_action": "DRAW"}
                with self.assertRaisesRegex(DefinitionError, "must be one of"):
                    parse_definition(raw)

    def test_schema_v1_through_v3_reject_eliminate(self) -> None:
        for schema_version in (1, 2, 3):
            with self.subTest(schema_version=schema_version):
                raw = crossing_definition()
                raw["schema_version"] = schema_version
                raw["roles"]["A"]["goal"] = {
                    "kind": "ELIMINATE",
                    "piece": "runner",
                }
                if schema_version == 2:
                    raw["terminal_policy"] = {"no_legal_action": "DRAW"}
                elif schema_version == 3:
                    raw["roles"]["B"]["action"]["kind"] = "MOVE_CAPTURE"
                with self.assertRaisesRegex(
                    DefinitionError,
                    "goal.kind must be one of.*CONNECT_EDGES.*REACH_EDGE",
                ):
                    parse_definition(raw)

    def test_schema_v4_eliminate_requires_exact_fields_and_allows_zero_targets(self) -> None:
        def raw_with_goal(goal):
            raw = crossing_definition()
            raw["schema_version"] = 4
            raw["roles"]["A"]["goal"] = goal
            return raw

        cases = (
            ({"kind": "ELIMINATE"}, "missing.*piece"),
            (
                {"kind": "ELIMINATE", "piece": "runner", "edge": "TOP"},
                "unknown.*edge",
            ),
            (
                {
                    "kind": "ELIMINATE",
                    "piece": "runner",
                    "edges": ["BOTTOM", "TOP"],
                },
                "unknown.*edges",
            ),
            (
                {"kind": "ELIMINATE", "piece": "Runner"},
                "piece must match",
            ),
            (
                {"kind": True, "piece": "runner"},
                "kind must be a string",
            ),
            (
                {"kind": "DESTROY", "piece": "runner"},
                "kind must be one of",
            ),
        )
        for goal, message in cases:
            with self.subTest(goal=goal):
                with self.assertRaisesRegex(DefinitionError, message):
                    parse_definition(raw_with_goal(goal))

        zero_target = raw_with_goal(
            {"kind": "ELIMINATE", "piece": "runner"}
        )
        zero_target["initial_pieces"] = []
        definition = parse_definition(zero_target)
        self.assertEqual(definition.initial_pieces, ())
        self.assertIs(definition.role(Player.A).goal.kind, GoalKind.ELIMINATE)

    def test_schema_v4_admission_covers_all_action_and_goal_pairs(self) -> None:
        action_kinds = (
            "PLACE",
            "MOVE",
            "MOVE_CAPTURE",
            "PUSH",
            "SWAP",
            "HOP",
            "CONVERT",
        )
        special_kinds = frozenset(("PUSH", "SWAP", "HOP", "CONVERT"))
        goal_kinds = ("CONNECT_EDGES", "REACH_EDGE", "ELIMINATE")

        def action_value(kind, piece):
            result = {"kind": kind, "piece": piece}
            if kind != "PLACE":
                result["vectors"] = [[-1, 0]]
            return result

        def goal_value(kind, piece):
            result = {"kind": kind, "piece": piece}
            if kind == "CONNECT_EDGES":
                result["edges"] = ["BOTTOM", "TOP"]
            elif kind == "REACH_EDGE":
                result["edge"] = "TOP"
            return result

        accepted = 0
        rejected = 0
        for first_kind in action_kinds:
            for second_kind in action_kinds:
                for first_goal in goal_kinds:
                    for second_goal in goal_kinds:
                        with self.subTest(
                            first_kind=first_kind,
                            second_kind=second_kind,
                            first_goal=first_goal,
                            second_goal=second_goal,
                        ):
                            raw = crossing_definition()
                            raw["schema_version"] = 4
                            raw["roles"]["A"]["action"] = action_value(
                                first_kind, "seed"
                            )
                            raw["roles"]["B"]["action"] = action_value(
                                second_kind, "runner"
                            )
                            raw["roles"]["A"]["goal"] = goal_value(
                                first_goal, "runner"
                            )
                            raw["roles"]["B"]["goal"] = goal_value(
                                second_goal, "seed"
                            )

                            has_v4_feature = bool(
                                {first_kind, second_kind} & special_kinds
                            ) or "ELIMINATE" in (first_goal, second_goal)
                            if not has_v4_feature:
                                with self.assertRaisesRegex(
                                    DefinitionError,
                                    "require.*PUSH, SWAP, HOP, or CONVERT.*ELIMINATE",
                                ):
                                    parse_definition(raw)
                                rejected += 1
                                continue

                            definition = parse_definition(raw)
                            accepted += 1
                            self.assertIs(
                                definition.roles[0][1].action.kind,
                                ActionKind(first_kind),
                            )
                            self.assertIs(
                                definition.roles[1][1].action.kind,
                                ActionKind(second_kind),
                            )
                            self.assertIs(
                                definition.roles[0][1].goal.kind,
                                GoalKind(first_goal),
                            )
                            self.assertIs(
                                definition.roles[1][1].goal.kind,
                                GoalKind(second_goal),
                            )
        self.assertEqual(accepted, 405)
        self.assertEqual(rejected, 36)

    def test_schema_v4_push_vectors_reject_bool_empty_zero_long_and_duplicates(self) -> None:
        def raw_with_vectors(vectors):
            raw = crossing_definition()
            raw["schema_version"] = 4
            raw["roles"]["A"]["action"] = {
                "kind": "PUSH",
                "piece": "seed",
                "vectors": vectors,
            }
            return raw

        cases = (
            ([], "non-empty"),
            ([[True, 0]], "must be an integer"),
            ([[0, 0]], "cannot contain"),
            ([[2, 0]], "one-step"),
            ([[-1, 0], [-1, 0]], "duplicates"),
        )
        for vectors, message in cases:
            with self.subTest(vectors=vectors):
                with self.assertRaisesRegex(DefinitionError, message):
                    parse_definition(raw_with_vectors(vectors))

    def test_schema_v4_swap_vectors_reject_bool_empty_zero_long_and_duplicates(self) -> None:
        def raw_with_vectors(vectors):
            raw = crossing_definition()
            raw["schema_version"] = 4
            raw["roles"]["A"]["action"] = {
                "kind": "SWAP",
                "piece": "seed",
                "vectors": vectors,
            }
            return raw

        cases = (
            ([], "non-empty"),
            ([[True, 0]], "must be an integer"),
            ([[0, 0]], "cannot contain"),
            ([[2, 0]], "one-step"),
            ([[-1, 0], [-1, 0]], "duplicates"),
        )
        for vectors, message in cases:
            with self.subTest(vectors=vectors):
                with self.assertRaisesRegex(DefinitionError, message):
                    parse_definition(raw_with_vectors(vectors))

    def test_schema_v4_hop_vectors_reject_bool_empty_zero_long_and_duplicates(self) -> None:
        def raw_with_vectors(vectors):
            raw = crossing_definition()
            raw["schema_version"] = 4
            raw["roles"]["A"]["action"] = {
                "kind": "HOP",
                "piece": "seed",
                "vectors": vectors,
            }
            return raw

        cases = (
            ([], "non-empty"),
            ([[True, 0]], "must be an integer"),
            ([[0, 0]], "cannot contain"),
            ([[2, 0]], "one-step"),
            ([[-1, 0], [-1, 0]], "duplicates"),
        )
        for vectors, message in cases:
            with self.subTest(vectors=vectors):
                with self.assertRaisesRegex(DefinitionError, message):
                    parse_definition(raw_with_vectors(vectors))

    def test_schema_v4_convert_vectors_reject_bool_empty_zero_long_and_duplicates(self) -> None:
        def raw_with_vectors(vectors):
            raw = crossing_definition()
            raw["schema_version"] = 4
            raw["roles"]["A"]["action"] = {
                "kind": "CONVERT",
                "piece": "seed",
                "vectors": vectors,
            }
            return raw

        cases = (
            ([], "non-empty"),
            ([[True, 0]], "must be an integer"),
            ([[0, 0]], "cannot contain"),
            ([[2, 0]], "one-step"),
            ([[-1, 0], [-1, 0]], "duplicates"),
        )
        for vectors, message in cases:
            with self.subTest(vectors=vectors):
                with self.assertRaisesRegex(DefinitionError, message):
                    parse_definition(raw_with_vectors(vectors))

    def test_schema_v4_swap_hidden_action_field_is_rejected_at_boundaries(self) -> None:
        raw = crossing_definition()
        raw["schema_version"] = 4
        raw["roles"]["A"]["action"] = {
            "kind": "SWAP",
            "piece": "seed",
            "vectors": [[-1, 0]],
        }
        definition = parse_definition(raw)
        object.__setattr__(
            definition.role(Player.A).action,
            "ranged_callback",
            lambda: None,
        )

        for operation in (canonical_json, definition_hash, describe_rules):
            with self.subTest(operation=operation.__name__):
                with self.assertRaisesRegex(DefinitionError, "parser-normalized"):
                    operation(definition)

    def test_schema_v4_hop_hidden_action_field_is_rejected_at_boundaries(self) -> None:
        raw = crossing_definition()
        raw["schema_version"] = 4
        raw["roles"]["A"]["action"] = {
            "kind": "HOP",
            "piece": "seed",
            "vectors": [[-1, 0]],
        }
        definition = parse_definition(raw)
        object.__setattr__(
            definition.role(Player.A).action,
            "landing_callback",
            lambda: None,
        )

        for operation in (canonical_json, definition_hash, describe_rules):
            with self.subTest(operation=operation.__name__):
                with self.assertRaisesRegex(DefinitionError, "parser-normalized"):
                    operation(definition)

    def test_schema_v4_convert_hidden_action_field_is_rejected_at_boundaries(self) -> None:
        raw = crossing_definition()
        raw["schema_version"] = 4
        raw["roles"]["A"]["action"] = {
            "kind": "CONVERT",
            "piece": "seed",
            "vectors": [[-1, 0]],
        }
        definition = parse_definition(raw)
        object.__setattr__(
            definition.role(Player.A).action,
            "conversion_callback",
            lambda: None,
        )

        for operation in (canonical_json, definition_hash, describe_rules):
            with self.subTest(operation=operation.__name__):
                with self.assertRaisesRegex(DefinitionError, "parser-normalized"):
                    operation(definition)

    def test_round_trip_is_canonical(self) -> None:
        raw = crossing_definition()
        raw["roles"]["B"]["action"]["vectors"] = [[1, 0], [0, 1], [-1, 0], [0, -1]]
        raw["initial_pieces"].append({"owner": "A", "piece": "seed", "position": [1, 2]})
        raw["initial_pieces"].append({"owner": "A", "piece": "seed", "position": [0, 2]})
        parsed = parse_definition(raw)
        reparsed = parse_definition(json.loads(canonical_json(parsed)))
        self.assertEqual(parsed, reparsed)
        self.assertEqual(canonical_json(parsed), canonical_json(reparsed))
        self.assertEqual(definition_hash(parsed), definition_hash(reparsed))

    def test_hash_ignores_mapping_and_set_like_array_order(self) -> None:
        left = crossing_definition()
        right = copy.deepcopy(left)
        right["roles"]["B"]["action"]["vectors"].reverse()
        self.assertEqual(definition_hash(parse_definition(left)), definition_hash(parse_definition(right)))

    def test_hash_changes_with_semantics(self) -> None:
        left = crossing_definition()
        right = copy.deepcopy(left)
        right["max_plies"] = 21
        self.assertNotEqual(definition_hash(parse_definition(left)), definition_hash(parse_definition(right)))

    def test_unknown_fields_are_rejected(self) -> None:
        raw = crossing_definition()
        raw["executable_callback"] = "do_bad_thing()"
        with self.assertRaisesRegex(DefinitionError, "unknown"):
            parse_definition(raw)

    def test_duplicate_and_zero_vectors_are_rejected(self) -> None:
        duplicate = crossing_definition()
        duplicate["roles"]["B"]["action"]["vectors"].append([-1, 0])
        with self.assertRaisesRegex(DefinitionError, "duplicates"):
            parse_definition(duplicate)
        zero = crossing_definition()
        zero["roles"]["B"]["action"]["vectors"] = [[0, 0]]
        with self.assertRaisesRegex(DefinitionError, "cannot contain"):
            parse_definition(zero)

    def test_positions_and_edges_are_validated(self) -> None:
        outside = crossing_definition()
        outside["initial_pieces"][0]["position"] = [3, 0]
        with self.assertRaisesRegex(DefinitionError, "outside"):
            parse_definition(outside)
        adjacent_edges = crossing_definition()
        adjacent_edges["roles"]["A"]["goal"]["edges"] = ["TOP", "LEFT"]
        with self.assertRaisesRegex(DefinitionError, "opposite"):
            parse_definition(adjacent_edges)


if __name__ == "__main__":
    unittest.main()
