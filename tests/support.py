from typing import Any, Dict


def crossing_definition() -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "name": "Crossing Seeds",
        "board_size": 3,
        "first_player": "A",
        "max_plies": 20,
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
                    "vectors": [[-1, 0], [0, -1], [0, 1], [1, 0]],
                },
                "goal": {"kind": "REACH_EDGE", "piece": "runner", "edge": "TOP"},
            },
        },
        "initial_pieces": [{"owner": "B", "piece": "runner", "position": [2, 1]}],
    }
