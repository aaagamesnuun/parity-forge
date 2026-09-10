"""Outcome-blind, bounded selection for Plan 0018; no engine or file I/O.

The public no-draw checker proves a structural property of a strict wire. It
does not establish historical novelty, fairness, or the absence of easy wins.
"""

from collections import Counter
import hashlib
from itertools import product
import json

from parity_forge_universe import initial_structure as initial
from parity_forge_universe import schema_v4_compiler as compiler
from parity_forge_universe import static_census_reconstruction as reconstruction
from parity_forge_universe import typed_occupancy as universe
from research.parity_forge_history import wire_identity


PROTOCOL_ID = "plan0018-no-draw-selection-v1"
CERTIFICATE_ID = "plan0018-convert-capture-no-draw-v1"
REPORT_SHA256 = "fa7daf48992f2b186fd980d42f670beda651b1adc7fe4c1fb62b67d1fdc05f97"
REPORT_BYTES = 17_284_867
PREVIOUS_MANIFEST_SHA256 = "3c54f7b753ce56d2d6fc28e77c6d8eddc0a5ebd8df11d151bc15a6068cb6814b"
PREVIOUS_MANIFEST_BYTES = 2_400_534
PREVIOUS_CARRIER_COUNT = 23
HISTORY_PROJECTION_ROOT = "00973dcc6447697fae4639442bfe2fa93a5d0ff7c62f279688fa38dac1e2e3c9"
GOALS = ("CONNECT_EDGES", "ELIMINATE", "REACH_EDGE")
# Ordered by mechanism, not by owner or an unordered pair of goal labels.
GOAL_PAIRS = tuple(pair for pair in product(GOALS, repeat=2)
                   if pair != ("ELIMINATE", "ELIMINATE"))
CONTACT_CLASSES = ("CONTACT", "SEPARATED")
ATTEMPTS_PER_SLOT = 64
IDENTITY_FIELDS = ("exact_hash", "d4_hash", "role_neutral_hash")
RANK_DOMAINS = {
    kind: ("parity-forge:plan0018:pilot:" + kind + ":v1\0").encode("utf-8")
    for kind in ("skeleton", "cell")
}


class SelectionError(RuntimeError):
    """A stopped attempt, including every available outcome-blind prefix."""

    def __init__(self, message, partial_selection):
        super().__init__(message)
        self.partial_selection = partial_selection


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _rank(kind, value):
    encoded = _canonical(value)
    return hashlib.sha256(RANK_DOMAINS[kind] + encoded).hexdigest(), encoded


def _rank_record(key):
    return {"rank_hash": key[0], "canonical_rank_json": key[1].decode("utf-8")}


def certify_no_draw(definition_mapping: dict) -> dict:
    """Fail closed outside the finite-decisive CONVERT/capture wire theorem.

    Let m count ALL opposing-owner pieces. CONVERT decreases m by one and
    MOVE_CAPTURE cannot increase it. The converter's m-th turn is terminal;
    earlier goals or immobility only shorten the play. This is an upper bound,
    not a minimax result, a shortest-win distance, or a fairness certificate.
    Historical exclusion (including E/E) belongs to selection, not this theorem.
    """
    value = wire_identity.normalize_definition_v1(definition_mapping)
    if (value["schema_version"], value["board_size"], value["max_plies"]) != (4, 3, 18):
        raise ValueError("no-draw certificate requires schema 4, board 3, max_plies 18")
    roles = value["roles"]
    actions = {owner: roles[owner]["action"]["kind"] for owner in ("A", "B")}
    if set(actions.values()) != {"CONVERT", "MOVE_CAPTURE"}:
        raise ValueError("no-draw certificate requires CONVERT versus MOVE_CAPTURE")
    converter = next(owner for owner in ("A", "B") if actions[owner] == "CONVERT")
    opponent = "B" if converter == "A" else "A"
    kinds = {owner: roles[owner]["action"]["piece"] for owner in ("A", "B")}
    if kinds["A"] == kinds["B"]:
        raise ValueError("no-draw certificate requires two distinct owner piece kinds")
    for owner in ("A", "B"):
        goal = roles[owner]["goal"]
        other = "B" if owner == "A" else "A"
        expected = kinds[other] if goal["kind"] == "ELIMINATE" else kinds[owner]
        if goal["piece"] != expected:
            raise ValueError("goal piece does not match the typed owner/opponent kind")
    counts = {"A": 0, "B": 0}
    for piece in value["initial_pieces"]:
        if piece["piece"] != kinds[piece["owner"]]:
            raise ValueError("initial piece kind does not match its owner action")
        counts[piece["owner"]] += 1
    if not counts[converter] or not counts[opponent]:
        raise ValueError("no-draw certificate requires both initial owners nonempty")
    m = counts[opponent]
    bound = 2 * m - (value["first_player"] == converter)
    if not 1 <= bound < value["max_plies"]:
        raise ValueError("natural termination bound must precede the ply limit")
    return {
        "certificate_id": CERTIFICATE_ID,
        "definition_hash": wire_identity.definition_hash_v1(value),
        "converter_role": converter, "opponent_role": opponent,
        "first_player": value["first_player"], "initial_counts": counts,
        "initial_opponent_count": m, "max_natural_plies": bound,
        "max_plies": value["max_plies"],
        "every_legal_play_finite_decisive": True,
        "ply_limit_unreachable": True,
    }


def _authenticate(raw, size, sha256, label):
    if type(raw) is not bytes:
        raise TypeError(label + " must be exact bytes")
    if len(raw) != size:
        raise ValueError(label + " byte count differs from the pinned artifact")
    if hashlib.sha256(raw).hexdigest() != sha256:
        raise ValueError(label + " SHA-256 differs from the pinned artifact")


def _definition_identities(definitions):
    if type(definitions) is not list or len(definitions) != 2:
        raise ValueError("expected exactly two first-player definitions")
    if [row["first_player"] for row in definitions] != ["A", "B"]:
        raise ValueError("expected separate A-first/B-first definitions")
    return [{
        "first_player": value["first_player"],
        "exact_hash": wire_identity.definition_hash_v1(value),
        "d4_hash": wire_identity.d4_definition_hash_v1(value),
        "role_neutral_hash": wire_identity.role_neutral_definition_hash_v1(value),
    } for value in definitions]


def _read_previous(raw):
    envelope = json.loads(raw)
    if (type(envelope) is not dict or set(envelope) != {"payload", "sha256"}
            or _canonical(envelope) != raw
            or hashlib.sha256(_canonical(envelope["payload"])).hexdigest() != envelope["sha256"]):
        raise ValueError("prior manifest canonical envelope or payload digest differs")
    manifest = envelope["payload"]
    if manifest["protocol_id"] != "plan0016-exploratory-pilot-v1":
        raise ValueError("unexpected previous manifest protocol")
    carriers = manifest["selection"]["selected"]
    if type(carriers) is not list or len(carriers) != PREVIOUS_CARRIER_COUNT:
        raise ValueError("previous manifest carrier count differs")
    seen = {field: {} for field in IDENTITY_FIELDS}
    evidence = []
    for index, carrier in enumerate(carriers):
        identities = _definition_identities(carrier["definitions"])
        if identities != carrier["definition_identities"]:
            raise ValueError("previous definition identities do not reconstruct")
        evidence.append({"carrier_index": index, "carrier_id": carrier["carrier_id"],
                         "definition_identities": identities})
        for field in IDENTITY_FIELDS:
            for identity in identities:
                seen[field].setdefault(identity[field], set()).add(carrier["carrier_id"])
    return seen, evidence


def _group_report(report):
    groups = {}
    for shard in report["skeleton_shards"]:
        saved = shard["skeleton"]
        roles = json.loads(saved["canonical_profiled_skeleton_json"])["roles"]
        mechanism = {owner: roles[owner]["action_primitive"] for owner in ("A", "B")}
        applicable = set(mechanism.values()) == {"CONVERT", "MOVE_CAPTURE"}
        converter = next((owner for owner in ("A", "B")
                          if mechanism[owner] == "CONVERT"), None) if applicable else None
        opponent = ("B" if converter == "A" else "A") if applicable else None
        goal_pair = tuple(roles[owner]["goal_primitive"] for owner in (converter, opponent)) if applicable else None
        in_scope = applicable and goal_pair in GOAL_PAIRS
        semantic = saved["role_neutral_semantic_hash"]
        signature = {owner: {key: roles[owner][key]
                            for key in ("action_primitive", "goal_primitive")}
                     for owner in ("A", "B")}
        group = groups.setdefault(semantic, {
            "semantic_hash": semantic, "role_signatures": signature,
            "goal_pair": goal_pair, "in_scope": in_scope, "shards": [],
            "supply": {contact: 0 for contact in CONTACT_CLASSES},
        })
        if group["goal_pair"] != goal_pair or group["in_scope"] != in_scope:
            raise ValueError("one semantic class acquired incompatible mechanism goals")
        group["shards"].append(shard)
        for contact in CONTACT_CLASSES:
            group["supply"][contact] += shard["contact"][contact]["eligible_representative_count"]
    return groups


def _ranked_skeletons(groups, goal_pair, slot):
    ranked = []
    for semantic, group in groups.items():
        if not group["in_scope"] or group["goal_pair"] != goal_pair:
            continue
        for shard in group["shards"]:
            if not shard["contact"]["CONTACT"]["eligible_representative_count"]:
                continue
            saved = shard["skeleton"]
            key = _rank("skeleton", {
                "goal_pair": list(goal_pair), "contact_class": "CONTACT", "slot": slot,
                "semantic_hash": semantic, "skeleton_hash": saved["role_neutral_skeleton_hash"],
            })
            pairs = sorted({(row["initial_counts"]["A"], row["initial_counts"]["B"])
                            for row in shard["eligible_supply_by_count_pair_and_contact"]
                            if row["contact_class"] == "CONTACT" and row["representative_count"] > 0})
            if not pairs:
                raise ValueError("positive contact skeleton has no positive resource pair")
            ranked.append((key, shard, pairs))
    return sorted(ranked, key=lambda row: row[0])


def _make_carrier(saved, goal_pair, slot, attempt, counts, skeleton):
    ranked_cells = sorted(((_rank("cell", {
        "goal_pair": list(goal_pair), "contact_class": "CONTACT", "slot": slot,
        "attempt": attempt, "skeleton_hash": saved["role_neutral_skeleton_hash"], "cell": cell,
    }), cell) for cell in range(9)), key=lambda row: row[0])
    cells = [cell for _, cell in ranked_cells]
    a_count, b_count = counts
    positions_a = tuple(sorted(divmod(cell, 3) for cell in cells[:a_count]))
    positions_b = tuple(sorted(divmod(cell, 3) for cell in cells[a_count:a_count + b_count]))
    setup = compiler.TypedSetupV1(1, positions_a, positions_b)
    images = [compiler.transform_typed_setup_v1(setup, universe.D4Transform(name))
              for name in saved["exact_stabilizer"]]
    if not images:
        raise ValueError("authenticated skeleton stabilizer became empty")
    canonical_setup = min(images, key=lambda value:
                          compiler.canonical_typed_setup_json_v1(value).encode("utf-8"))
    return compiler.TypedSetupCarrierV1(1, skeleton, canonical_setup), {
        "cell_order": cells,
        "cell_ranks": [{"cell": cell, **_rank_record(key)} for key, cell in ranked_cells],
        "source_positions": {"A": [list(p) for p in positions_a], "B": [list(p) for p in positions_b]},
        "canonical_setup": canonical_setup.to_dict(),
        "exact_stabilizer": list(saved["exact_stabilizer"]),
    }


def _compile_pair(carrier):
    # Yield each observed wire so a later compilation failure retains its prefix.
    for member in compiler.expand_first_player_pair_v1(carrier):
        yield json.loads(compiler.compile_schema_v4_json_v1(member))


def _collisions(identities, seen):
    result = {}
    for field in IDENTITY_FIELDS:
        matches = set()
        for identity in identities:
            matches.update(seen[field].get(identity[field], ()))
        if matches:
            result[field] = sorted(matches)
    return result


def _select_pilot(raw_report, raw_previous_manifest, progress):
    _authenticate(raw_report, REPORT_BYTES, REPORT_SHA256, "static report")
    _authenticate(raw_previous_manifest, PREVIOUS_MANIFEST_BYTES,
                  PREVIOUS_MANIFEST_SHA256, "previous manifest")
    progress.update(stage="HISTORY", report_ref={"byte_count": REPORT_BYTES, "sha256": REPORT_SHA256},
                    previous_manifest_ref={"byte_count": PREVIOUS_MANIFEST_BYTES, "sha256": PREVIOUS_MANIFEST_SHA256})
    prior_seen, prior_identities = _read_previous(raw_previous_manifest)
    progress.update(stage="RECONSTRUCTION", previous_definition_identities=prior_identities)
    proof = reconstruction.reconstruct_static_census_report_artifact_v1(raw_report)
    if proof["report_ref"] != {"byte_count": REPORT_BYTES, "sha256": REPORT_SHA256}:
        raise ValueError("public reconstruction changed the authenticated report reference")
    groups = _group_report(proof["report"])
    progress.update(stage="SAMPLING", semantic_class_count=len(groups))
    slots, attempts, selected = progress["slots"], progress["attempts"], progress["selected"]
    seen = {field: {} for field in IDENTITY_FIELDS}
    for goal_pair in GOAL_PAIRS:
        for slot in range(2):
            ranked = _ranked_skeletons(groups, goal_pair, slot)
            slot_record = {
                "goal_pair": list(goal_pair), "contact_class": "CONTACT", "slot": slot,
                "skeleton_ranking": [{
                    "semantic_hash": shard["skeleton"]["role_neutral_semantic_hash"],
                    "skeleton_hash": shard["skeleton"]["role_neutral_skeleton_hash"],
                    "resource_pairs": [list(pair) for pair in pairs], **_rank_record(key),
                } for key, shard, pairs in ranked],
                "saved_eligible_supply": sum(shard["contact"]["CONTACT"]["eligible_representative_count"]
                                              for _, shard, _ in ranked),
                "attempt_count": 0, "disposition": "BOUNDED_SAMPLE_EMPTY" if ranked else "STATIC_ZERO",
                "selected_carrier_id": None, "unattempted_after_acceptance": 0,
            }
            slots.append(slot_record)
            prepared, skeletons = {}, {}
            for attempt in range(ATTEMPTS_PER_SLOT if ranked else 0):
                _, shard, pairs = ranked[attempt % len(ranked)]
                visit = attempt // len(ranked)
                saved = shard["skeleton"]
                semantic = saved["role_neutral_semantic_hash"]
                skeleton_hash = saved["role_neutral_skeleton_hash"]
                counts = pairs[visit % len(pairs)]
                slot_record["attempt_count"] += 1
                record = {
                    "ordinal": len(attempts), "goal_pair": list(goal_pair), "contact_class": "CONTACT",
                    "slot": slot, "attempt": attempt, "semantic_hash": semantic,
                    "skeleton_hash": skeleton_hash, "skeleton_visit": visit,
                    "initial_counts": list(counts), "disposition": "STARTED",
                }
                progress["current_attempt"] = record
                if skeleton_hash not in skeletons:
                    skeletons[skeleton_hash] = universe.parse_profiled_skeleton(
                        json.loads(saved["canonical_profiled_skeleton_json"]))
                carrier, source_record = _make_carrier(
                    saved, goal_pair, slot, attempt, counts, skeletons[skeleton_hash])
                record.update(source_record)
                carrier_id = compiler.typed_setup_carrier_hash_v1(carrier)
                record["carrier_id"] = carrier_id
                if skeleton_hash not in prepared:
                    prepared[skeleton_hash] = initial.prepare_initial_structure_skeleton_v1(carrier)
                encoded, result_hash = initial.derive_prepared_initial_structure_snapshot_v1(
                    prepared[skeleton_hash], carrier)
                facts = json.loads(encoded)
                record.update(static_result_hash=result_hash, static_facts=facts)
                if (facts["identities"]["typed_carrier_hash"] != carrier_id
                        or facts["identities"]["typed_skeleton_hash"] != saved["typed_skeleton_hash"]):
                    raise ValueError("static snapshot changed its source identity")
                contact = facts["descriptor_groups"]["contact"]["contact_class"]
                record.update(static_evidence_digest=facts["evidence_digest"],
                              static_reasons=facts["rejection_reasons"], static_eligible=facts["eligible"],
                              observed_contact_class=contact, disposition="STATIC_REJECTED")
                # Complete judgments retain compact evidence. Full static facts
                # remain only on accepted carriers or a failing validation step.
                record.pop("static_facts")
                attempts.append(record)
                if not facts["eligible"]:
                    progress["current_attempt"] = None
                    continue
                if contact != "CONTACT":
                    record["disposition"] = "CONTACT_MISMATCH"
                    progress["current_attempt"] = None
                    continue
                record["disposition"] = "COMPILING"
                definitions = []
                record["definitions"] = definitions
                definitions.extend(_compile_pair(carrier))
                identities = _definition_identities(definitions)
                record["definition_identities"] = identities
                record["disposition"] = "CERTIFYING"
                certificates = []
                record["no_draw_certificates"] = certificates
                for value in definitions:
                    certificates.append(certify_no_draw(value))
                for value, certificate in zip(definitions, certificates):
                    converter, opponent = certificate["converter_role"], certificate["opponent_role"]
                    if tuple(value["roles"][owner]["goal"]["kind"] for owner in (converter, opponent)) != goal_pair:
                        raise ValueError("compiled member escaped its mechanism-ordered goal pair")
                prior_collisions = _collisions(identities, prior_seen)
                accepted_collisions = _collisions(identities, seen)
                record.update(definition_identities=identities, no_draw_certificates=certificates)
                if prior_collisions or accepted_collisions:
                    record["disposition"] = "DUPLICATE_PREVIOUS_MANIFEST" if prior_collisions else "DUPLICATE_ACCEPTED_CARRIER"
                    record["duplicate_relations"] = {"previous_manifest": prior_collisions,
                                                      "accepted_carriers": accepted_collisions}
                    progress["current_attempt"] = None
                    continue
                record["disposition"] = "ACCEPTED"
                selected.append({
                    "selection_index": len(selected), "carrier_id": carrier_id,
                    "goal_pair": list(goal_pair), "contact_class": "CONTACT", "slot": slot,
                    "semantic_hash": semantic, "skeleton_hash": skeleton_hash,
                    "typed_skeleton_hash": saved["typed_skeleton_hash"], "accepted_attempt": attempt,
                    "definitions": definitions, "definition_identities": identities,
                    "static_facts": facts, "no_draw_certificates": certificates,
                    "converter_role": certificates[0]["converter_role"],
                    "opponent_role": certificates[0]["opponent_role"],
                })
                for field in IDENTITY_FIELDS:
                    for identity in identities:
                        seen[field].setdefault(identity[field], set()).add(carrier_id)
                slot_record.update(disposition="SELECTED", selected_carrier_id=carrier_id,
                                   unattempted_after_acceptance=ATTEMPTS_PER_SLOT - slot_record["attempt_count"])
                progress["current_attempt"] = None
                break
    progress["current_attempt"] = None

    assigned_counts = Counter()
    for slot in slots:
        assigned_counts.update({row["semantic_hash"] for row in slot["skeleton_ranking"]})
    represented_counts = Counter(row["semantic_hash"] for row in selected)
    attempt_counts = Counter(row["semantic_hash"] for row in attempts)
    class_coverage = [{
        "semantic_hash": semantic, "role_signatures": group["role_signatures"],
        "goal_pair": list(group["goal_pair"]) if group["goal_pair"] is not None else None,
        "scope": "IN_SCOPE" if group["in_scope"] else "OUT_OF_SCOPE",
        "saved_eligible_supply": group["supply"],
        "assigned_slot_count": assigned_counts[semantic],
        "represented_carrier_count": represented_counts[semantic],
        "attempt_count": attempt_counts[semantic],
        "disposition": ("OUT_OF_SCOPE" if not group["in_scope"] else
                        "REPRESENTED" if represented_counts[semantic] else
                        "ASSIGNED" if assigned_counts[semantic] else "STATIC_ZERO"),
    } for semantic, group in sorted(groups.items())]
    return {
        "protocol_id": PROTOCOL_ID, "report_ref": dict(proof["report_ref"]),
        "previous_manifest_ref": {"byte_count": PREVIOUS_MANIFEST_BYTES, "sha256": PREVIOUS_MANIFEST_SHA256},
        "exposure_boundary": {
            "history_projection_root": HISTORY_PROJECTION_ROOT,
            "history_checkpoint": "1fe53927c",
            "scope": "NAMED_HISTORICAL_BOUNDARY_PLUS_PLAN0016_NOT_EXHAUSTIVE_CUTOFF",
            "old_six_semantic_regions_excluded": True,
            "prior_legacy_schema_versions": [1, 2, 3], "prior_calibration_max_plies": [1, 2, 3, 4],
            "compiler_schema_version": 4, "compiler_max_plies": 18,
            "previous_carrier_count": len(prior_identities),
            "previous_definition_count": 2 * len(prior_identities),
            "previous_definition_identities": prior_identities,
            "static_compiler_and_prior_pilot_exposure_disclosed": True,
            "gameplay_outcomes_used_for_member_ranking": False,
            "family_choice_is_post_outcome": True,
        },
        "rank_contract": {
            "domains": {kind: domain.decode("utf-8") for kind, domain in RANK_DOMAINS.items()},
            "canonical_json": "sorted keys; compact; UTF-8; ensure_ascii=False; allow_nan=False",
            "tie_break": "canonical rank-object UTF-8 bytes", "attempts_per_slot": ATTEMPTS_PER_SLOT,
            "goal_pair_order": "converter goal, capture-mover goal",
            "resource_pair_order": "lexical canonical owner A count, owner B count",
        },
        "coverage": {
            "semantic_class_count": len(groups), "expected_production_semantic_class_count": 109,
            "classes": class_coverage,
            "in_scope_semantic_class_count": sum(group["in_scope"] for group in groups.values()),
            "out_of_scope_semantic_class_count": sum(not group["in_scope"] for group in groups.values()),
            "ordered_goal_pairs": [list(pair) for pair in GOAL_PAIRS],
            "excluded_goal_pairs": [["ELIMINATE", "ELIMINATE"]],
            "contact_classes_attempted": ["CONTACT"],
            "separated_exclusion": "INITIAL_CONVERT_LEGALITY_IMPLIES_VECTOR_CONTACT",
            "slot_count": len(slots), "slot_dispositions": dict(sorted(Counter(row["disposition"] for row in slots).items())),
            "attempt_count": len(attempts), "attempt_dispositions": dict(sorted(Counter(row["disposition"] for row in attempts).items())),
            "selected_carrier_count": len(selected), "selected_definition_count": 2 * len(selected),
        },
        "slots": slots, "attempts": attempts, "selected": selected,
    }


def select_pilot(raw_report: bytes, raw_previous_manifest: bytes) -> dict:
    """Select at most sixteen carriers, or retain the failed observed prefix.

    No caller may retry a failed production attempt. SelectionError preserves
    accepted definitions, prior completed judgments and the in-progress source.
    """
    progress = {"protocol_id": PROTOCOL_ID, "completed": False, "stage": "AUTHENTICATION",
                "slots": [], "attempts": [], "selected": [], "current_attempt": None}
    try:
        return _select_pilot(raw_report, raw_previous_manifest, progress)
    except Exception as error:
        progress["failure"] = {"type": type(error).__name__, "message": str(error)}
        if progress["current_attempt"] is not None:
            current = progress["current_attempt"]
            current.update(failed_during=current["disposition"], disposition="FAILED",
                           failure=progress["failure"])
        raise SelectionError(str(error), progress) from error


__all__ = ["SelectionError", "certify_no_draw", "select_pilot"]
