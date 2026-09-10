"""Six deterministic directional carriers; static development exposure only.

No gameplay, solver, file I/O, census, or private compiler API is used here.
The public DSL4 parser permits these one-step vector subsets and boards 3..5;
the older typed compiler's three symmetric profiles are not this generator.
MOVE_CAPTURE/REACH_EDGE versus PUSH/REACH_EDGE is outside every old-six
semantic region, including role swaps (typed_occupancy's public predicate).
That exclusion is not a claim of global novelty or untouched confirmation.
"""

import hashlib
import json

from parity_forge.dsl import canonical_json, definition_hash, parse_definition


CERTIFICATE_ID = "plan0020-directional-capture-push-no-draw-v1"
BOARD_SIZES = (4, 5)
COUNT_PAIRS = ((2, 3), (2, 4), (3, 4))
FORWARD = ((1, -1), (1, 0), (1, 1))
BACKWARD = ((-1, -1), (-1, 0), (-1, 1))


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _potential(size, pieces):
    return sum(size - 1 - p["position"][0] if p["owner"] == "A"
               else 2 * p["position"][0] for p in pieces)


def certify_no_draw(raw: dict) -> dict:
    """Certify all legal play, not minimax, difficulty, balance, or enjoyment.

    Phi = sum_A(n-1-row) + 2*sum_B(row) is nonnegative. An A move
    decreases Phi by 1, and capturing removes an additional nonnegative term.
    A B move decreases it by 2; pushing an A back adds 1, leaving decrease 1.
    Goals or immobility may end earlier. The strict cap inequality matters:
    the engine checks PLY_LIMIT before next-player immobility.
    """
    definition = parse_definition(raw)
    value = json.loads(canonical_json(definition))
    if value["schema_version"] != 4:
        raise ValueError("directional certificate requires schema 4")
    expected = {
        "A": ("MOVE_CAPTURE", "a", FORWARD, "BOTTOM"),
        "B": ("PUSH", "b", BACKWARD, "TOP"),
    }
    for owner, (kind, piece, vectors, edge) in expected.items():
        role = value["roles"][owner]
        if role != {
            "action": {"kind": kind, "piece": piece,
                       "vectors": [list(v) for v in vectors]},
            "goal": {"kind": "REACH_EDGE", "piece": piece, "edge": edge},
        }:
            raise ValueError("role differs from the directional capture/push theorem")
    counts = {"A": 0, "B": 0}
    for piece in value["initial_pieces"]:
        if piece["piece"] != expected[piece["owner"]][1]:
            raise ValueError("initial piece type must match its owner's action")
        counts[piece["owner"]] += 1
    if not all(counts.values()):
        raise ValueError("both initial owners must be nonempty")
    bound = _potential(value["board_size"], value["initial_pieces"])
    if not 0 <= bound < value["max_plies"]:
        raise ValueError("natural termination bound must strictly precede ply limit")
    return {
        "certificate_id": CERTIFICATE_ID,
        "definition_hash": definition_hash(definition),
        "board_size": value["board_size"],
        "first_player": value["first_player"], "initial_counts": counts,
        "initial_potential": bound, "max_natural_plies": bound,
        "max_plies": value["max_plies"],
        "every_legal_play_finite_decisive": True,
        "ply_limit_unreachable": True,
    }


def build_candidates() -> list[dict]:
    """Return six board/count ordered B-first wires without playing any game.

    Each role's columns are ranked by SHA256(canonical(["plan0020", n,
    [a,b], role, column])), with column as the deterministic collision tie-break.
    A-first was excluded before gameplay by a direct winning-strategy proof.
    Carrier identity excludes first player; each returned game is B-first only.
    """
    result = []
    for size in BOARD_SIZES:
        for counts in COUNT_PAIRS:
            pieces = []
            for owner, count, row in (("A", counts[0], 0),
                                      ("B", counts[1], size - 1)):
                columns = sorted(range(size), key=lambda column: (
                    hashlib.sha256(_canonical(
                        ["plan0020", size, list(counts), owner, column]
                    )).hexdigest(), column))
                pieces.extend({"owner": owner, "piece": owner.lower(),
                               "position": [row, column]}
                              for column in columns[:count])
            raw = {
                "schema_version": 4,
                "name": "plan0020-{}x{}-{}v{}".format(size, size, *counts),
                "board_size": size, "first_player": "B",
                "max_plies": _potential(size, pieces) + 1,
                "roles": {
                    owner: {
                        "action": {"kind": kind, "piece": owner.lower(),
                                   "vectors": [list(v) for v in vectors]},
                        "goal": {"kind": "REACH_EDGE", "piece": owner.lower(),
                                 "edge": edge},
                    } for owner, kind, vectors, edge in (
                        ("A", "MOVE_CAPTURE", FORWARD, "BOTTOM"),
                        ("B", "PUSH", BACKWARD, "TOP"))
                },
                "initial_pieces": pieces,
            }
            value = json.loads(canonical_json(parse_definition(raw)))
            carrier_wire = {k: v for k, v in value.items() if k != "first_player"}
            carrier_id = hashlib.sha256(
                b"parity-forge:plan0020:carrier:v1\0" + _canonical(carrier_wire)
            ).hexdigest()
            result.append({"definition": value,
                           "certificate": certify_no_draw(value),
                           "carrier_id": carrier_id, "first_player": "B"})
    return result
