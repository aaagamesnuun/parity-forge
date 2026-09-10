"""Small, deterministic, outcome-blind Plan-0016 pilot selector.

The sole input is the already sealed static report.  This module has no file
I/O, gameplay, solver, agent, or production-census capability.  A manifest
writer must persist this result before any selected definition is played.
"""

from collections import Counter
import hashlib
from itertools import combinations_with_replacement
import json

from parity_forge_universe import initial_structure as initial
from parity_forge_universe import schema_v4_compiler as compiler
from parity_forge_universe import static_census_reconstruction as reconstruction
from parity_forge_universe import typed_occupancy as universe
from research.parity_forge_history import wire_identity


PROTOCOL_ID = "plan0016-small-exploratory-selection-v1"
REPORT_SHA256 = "fa7daf48992f2b186fd980d42f670beda651b1adc7fe4c1fb62b67d1fdc05f97"
REPORT_BYTES = 17_284_867
HISTORY_PROJECTION_ROOT = (
    "00973dcc6447697fae4639442bfe2fa93a5d0ff7c62f279688fa38dac1e2e3c9"
)
GOAL_PAIRS = tuple(combinations_with_replacement(
    ("CONNECT_EDGES", "ELIMINATE", "REACH_EDGE"), 2
))
CONTACT_CLASSES = ("CONTACT", "SEPARATED")
ATTEMPTS_PER_SLOT = 64
RANK_DOMAINS = {
    kind: ("parity-forge:plan0016:pilot:" + kind + ":v1\0").encode("utf-8")
    for kind in ("semantic", "skeleton", "cell")
}


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _rank(kind, value):
    encoded = _canonical(value)
    return hashlib.sha256(RANK_DOMAINS[kind] + encoded).hexdigest(), encoded


def _rank_record(key):
    return {"rank_hash": key[0], "canonical_rank_json": key[1].decode("utf-8")}


def _group_report(report):
    groups = {}
    for shard in report["skeleton_shards"]:
        saved = shard["skeleton"]
        source = json.loads(saved["canonical_profiled_skeleton_json"])
        goals = tuple(sorted(source["roles"][owner]["goal_primitive"]
                             for owner in ("A", "B")))
        semantic = saved["role_neutral_semantic_hash"]
        group = groups.setdefault(semantic, {
            "semantic_hash": semantic,
            "goal_pair": goals,
            "shards": [],
            "supply": {contact: 0 for contact in CONTACT_CLASSES},
        })
        if group["goal_pair"] != goals:
            raise ValueError("one semantic class acquired different goal pairs")
        group["shards"].append(shard)
        for contact in CONTACT_CLASSES:
            group["supply"][contact] += (
                shard["contact"][contact]["eligible_representative_count"]
            )
    return groups


def _ranked_skeletons(group, goal_pair, contact, slot):
    ranked = []
    for shard in group["shards"]:
        if not shard["contact"][contact]["eligible_representative_count"]:
            continue
        skeleton_hash = shard["skeleton"]["role_neutral_skeleton_hash"]
        key = _rank("skeleton", {
            "goal_pair": list(goal_pair), "contact_class": contact, "slot": slot,
            "semantic_hash": group["semantic_hash"], "skeleton_hash": skeleton_hash,
        })
        pairs = sorted({
            (row["initial_counts"]["A"], row["initial_counts"]["B"])
            for row in shard["eligible_supply_by_count_pair_and_contact"]
            if row["contact_class"] == contact and row["representative_count"] > 0
        })
        if not pairs:
            raise ValueError("positive skeleton supply has no positive resource pair")
        ranked.append((key, shard, pairs))
    ranked.sort(key=lambda row: row[0])
    return ranked


def _make_carrier(saved, goal_pair, contact, slot, attempt, counts, skeleton):
    skeleton_hash = saved["role_neutral_skeleton_hash"]
    ranked_cells = []
    for cell in range(9):
        key = _rank("cell", {
            "goal_pair": list(goal_pair), "contact_class": contact, "slot": slot,
            "attempt": attempt, "skeleton_hash": skeleton_hash, "cell": cell,
        })
        ranked_cells.append((key, cell))
    ranked_cells.sort(key=lambda row: row[0])
    cells = [cell for _, cell in ranked_cells]
    a_count, b_count = counts
    positions_a = tuple(sorted(divmod(cell, 3) for cell in cells[:a_count]))
    positions_b = tuple(sorted(divmod(cell, 3)
                               for cell in cells[a_count:a_count + b_count]))
    source = compiler.TypedSetupV1(1, positions_a, positions_b)
    images = [
        compiler.transform_typed_setup_v1(source, universe.D4Transform(name))
        for name in saved["exact_stabilizer"]
    ]
    if not images:
        raise ValueError("authenticated stabilizer became empty")
    canonical_setup = min(
        images, key=lambda setup: compiler.canonical_typed_setup_json_v1(
            setup).encode("utf-8")
    )
    carrier = compiler.TypedSetupCarrierV1(1, skeleton, canonical_setup)
    source_record = {
        "cell_order": cells,
        "cell_ranks": [
            {"cell": cell, **_rank_record(key)} for key, cell in ranked_cells
        ],
        "source_positions": {
            "A": [list(position) for position in positions_a],
            "B": [list(position) for position in positions_b],
        },
        "canonical_setup": canonical_setup.to_dict(),
        "exact_stabilizer": list(saved["exact_stabilizer"]),
    }
    return carrier, source_record


def _compile_pair(carrier):
    return [
        json.loads(compiler.compile_schema_v4_json_v1(member))
        for member in compiler.expand_first_player_pair_v1(carrier)
    ]


def _definition_identities(definitions):
    if [row["first_player"] for row in definitions] != ["A", "B"]:
        raise ValueError("compiler changed the separate A-first/B-first pair")
    return [{
        "first_player": definition["first_player"],
        "exact_hash": wire_identity.definition_hash_v1(definition),
        "d4_hash": wire_identity.d4_definition_hash_v1(definition),
        "role_neutral_hash": wire_identity.role_neutral_definition_hash_v1(definition),
    } for definition in definitions]


def select_pilot(raw_report: bytes) -> dict:
    """Select at most 24 carriers without producing any gameplay outcome."""
    if type(raw_report) is not bytes:
        raise TypeError("raw_report must be exact bytes")
    if len(raw_report) != REPORT_BYTES:
        raise ValueError("static report byte count does not match the sealed report")
    if hashlib.sha256(raw_report).hexdigest() != REPORT_SHA256:
        raise ValueError("static report SHA-256 does not match the sealed report")
    proof = reconstruction.reconstruct_static_census_report_artifact_v1(raw_report)
    if proof["report_ref"] != {"byte_count": REPORT_BYTES, "sha256": REPORT_SHA256}:
        raise ValueError("public reconstruction changed the authenticated report reference")
    groups = _group_report(proof["report"])
    slots, attempts, selected, macro_coverage = [], [], [], []
    fields = ("exact_hash", "d4_hash", "role_neutral_hash")
    seen = {field: {} for field in fields}
    class_slot_count = Counter()

    for goal_pair in GOAL_PAIRS:
        for contact in CONTACT_CLASSES:
            ranked_classes = []
            for semantic, group in groups.items():
                if group["goal_pair"] != goal_pair or not group["supply"][contact]:
                    continue
                key = _rank("semantic", {
                    "goal_pair": list(goal_pair), "contact_class": contact,
                    "semantic_hash": semantic,
                })
                ranked_classes.append((key, semantic))
            ranked_classes.sort(key=lambda row: row[0])
            macro = {
                "goal_pair": list(goal_pair), "contact_class": contact,
                "positive_semantic_count": len(ranked_classes),
                "semantic_ranking": [
                    {"semantic_hash": semantic, **_rank_record(key)}
                    for key, semantic in ranked_classes
                ],
            }
            macro_coverage.append(macro)
            for slot in range(2):
                slot_record = {
                    "goal_pair": list(goal_pair), "contact_class": contact,
                    "slot": slot, "semantic_hash": None, "skeleton_ranking": [],
                    "attempt_count": 0, "disposition": "STATIC_ZERO",
                    "selected_carrier_id": None,
                }
                slots.append(slot_record)
                if not ranked_classes:
                    continue
                semantic_rank, semantic = ranked_classes[min(slot, len(ranked_classes) - 1)]
                group = groups[semantic]
                class_slot_count[semantic] += 1
                slot_record.update({
                    "semantic_hash": semantic,
                    "semantic_rank": _rank_record(semantic_rank),
                    "saved_eligible_supply": group["supply"][contact],
                    "disposition": "BOUNDED_SAMPLE_EMPTY",
                })
                ranked_skeletons = _ranked_skeletons(group, goal_pair, contact, slot)
                if not ranked_skeletons:
                    raise ValueError("positive semantic supply has no positive skeleton")
                slot_record["skeleton_ranking"] = [{
                    "skeleton_hash": shard["skeleton"]["role_neutral_skeleton_hash"],
                    "resource_pairs": [list(pair) for pair in pairs],
                    **_rank_record(key),
                } for key, shard, pairs in ranked_skeletons]
                # Operational tokens are local to this slot, never public inputs.
                prepared, skeletons = {}, {}
                for attempt in range(ATTEMPTS_PER_SLOT):
                    index = attempt % len(ranked_skeletons)
                    visit = attempt // len(ranked_skeletons)
                    _, shard, pairs = ranked_skeletons[index]
                    saved = shard["skeleton"]
                    skeleton_hash = saved["role_neutral_skeleton_hash"]
                    counts = pairs[visit % len(pairs)]
                    if skeleton_hash not in skeletons:
                        skeletons[skeleton_hash] = universe.parse_profiled_skeleton(
                            json.loads(saved["canonical_profiled_skeleton_json"]))
                    carrier, source_record = _make_carrier(
                        saved, goal_pair, contact, slot, attempt, counts,
                        skeletons[skeleton_hash],
                    )
                    carrier_id = compiler.typed_setup_carrier_hash_v1(carrier)
                    if skeleton_hash not in prepared:
                        prepared[skeleton_hash] = (
                            initial.prepare_initial_structure_skeleton_v1(carrier)
                        )
                    encoded, result_hash = (
                        initial.derive_prepared_initial_structure_snapshot_v1(
                            prepared[skeleton_hash], carrier
                        )
                    )
                    facts = json.loads(encoded)
                    if (
                        facts["identities"]["typed_carrier_hash"] != carrier_id
                        or facts["identities"]["typed_skeleton_hash"]
                        != saved["typed_skeleton_hash"]
                    ):
                        raise ValueError("static snapshot changed its source identity")
                    observed_contact = facts["descriptor_groups"]["contact"]["contact_class"]
                    record = {
                        "ordinal": len(attempts), "goal_pair": list(goal_pair),
                        "contact_class": contact, "slot": slot, "attempt": attempt,
                        "semantic_hash": semantic, "skeleton_hash": skeleton_hash,
                        "skeleton_visit": visit, "initial_counts": list(counts),
                        "carrier_id": carrier_id, **source_record,
                        "static_result_hash": result_hash,
                        "static_evidence_digest": facts["evidence_digest"],
                        "static_reasons": facts["rejection_reasons"],
                        "static_eligible": facts["eligible"],
                        "observed_contact_class": observed_contact,
                        "disposition": "STATIC_REJECTED",
                    }
                    attempts.append(record)
                    slot_record["attempt_count"] += 1
                    if not facts["eligible"]:
                        continue
                    if observed_contact != contact:
                        record["disposition"] = "CONTACT_MISMATCH"
                        continue
                    definitions = _compile_pair(carrier)
                    identities = _definition_identities(definitions)
                    collisions = {
                        field: sorted({
                            seen[field][identity[field]]
                            for identity in identities if identity[field] in seen[field]
                        })
                        for field in fields
                    }
                    collisions = {field: values for field, values in collisions.items()
                                  if values}
                    record["definition_identities"] = identities
                    if collisions:
                        record["disposition"] = "DUPLICATE_ACCEPTED_CARRIER"
                        record["duplicate_relations"] = collisions
                        continue
                    record["disposition"] = "ACCEPTED"
                    selected.append({
                        "selection_index": len(selected), "carrier_id": carrier_id,
                        "goal_pair": list(goal_pair), "contact_class": contact,
                        "slot": slot, "semantic_hash": semantic,
                        "skeleton_hash": skeleton_hash,
                        "typed_skeleton_hash": saved["typed_skeleton_hash"],
                        "accepted_attempt": attempt, "definitions": definitions,
                        "definition_identities": identities, "static_facts": facts,
                    })
                    for field in fields:
                        for identity in identities:
                            seen[field][identity[field]] = carrier_id
                    slot_record.update({
                        "disposition": "SELECTED", "selected_carrier_id": carrier_id,
                    })
                    break
                slot_record["unattempted_after_acceptance"] = (
                    ATTEMPTS_PER_SLOT - slot_record["attempt_count"]
                    if slot_record["disposition"] == "SELECTED" else 0
                )

    class_coverage = []
    for semantic, group in sorted(groups.items()):
        positive = sum(group["supply"].values()) > 0
        class_coverage.append({
            "semantic_hash": semantic, "goal_pair": list(group["goal_pair"]),
            "saved_eligible_supply": dict(group["supply"]),
            "assigned_slot_count": class_slot_count[semantic],
            "disposition": ("STATIC_ZERO" if not positive else
                            "ASSIGNED" if class_slot_count[semantic] else
                            "NOT_ASSIGNED_BY_FIXED_RANK"),
        })
    return {
        "protocol_id": PROTOCOL_ID,
        "report_ref": dict(proof["report_ref"]),
        "exposure_boundary": {
            "history_projection_root": HISTORY_PROJECTION_ROOT,
            "history_checkpoint": "1fe53927c",
            "scope": "NAMED_HISTORICAL_BOUNDARY_NOT_EXHAUSTIVE_LATER_CUTOFF",
            "prior_legacy_schema_versions": [1, 2, 3],
            "prior_calibration_max_plies": [1, 2, 3, 4],
            "compiler_schema_version": 4, "compiler_max_plies": 18,
            "old_six_semantic_regions_excluded": True,
            "static_compiler_exposure_disclosed": True,
            "gameplay_outcomes_used_for_selection": False,
        },
        "rank_contract": {
            "domains": {kind: domain.decode("utf-8")
                        for kind, domain in RANK_DOMAINS.items()},
            "canonical_json": "sorted keys; compact; UTF-8; ensure_ascii=False; allow_nan=False",
            "tie_break": "canonical rank-object UTF-8 bytes",
            "attempts_per_slot": ATTEMPTS_PER_SLOT,
        },
        "coverage": {
            "semantic_class_count": len(groups), "classes": class_coverage,
            "macro_strata": macro_coverage, "slot_count": len(slots),
            "slot_dispositions": dict(sorted(Counter(
                row["disposition"] for row in slots).items())),
            "attempt_count": len(attempts),
            "attempt_dispositions": dict(sorted(Counter(
                row["disposition"] for row in attempts).items())),
            "selected_carrier_count": len(selected),
            "selected_definition_count": 2 * len(selected),
        },
        "slots": slots, "attempts": attempts, "selected": selected,
    }
