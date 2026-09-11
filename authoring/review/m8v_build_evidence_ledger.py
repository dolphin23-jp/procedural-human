"""Build TASK-V08 vessel identity evidence ledger without promoting missing evidence.

Human adjudication is optional. Any supplied review session must reference the exact
committed TASK-V07 review-surface hash and the exact evidence snapshot presented by
that surface. Stale or mismatched review input fails closed.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def portable_path(path: Path) -> str:
    value = Path(path)
    if value.is_absolute():
        try:
            return value.resolve().relative_to(ROOT).as_posix()
        except ValueError:
            return value.as_posix()
    return value.as_posix()


RADIAL_GATE_IDS = {
    "unique-same-subject-arterial-anchor": "radial.gate.same-subject-anchor",
    "bounded-gap-continuity-to-target": "radial.gate.continuity",
    "compatible-branch-topology": "radial.gate.branch-topology",
    "compatible-landmark-relationships": "radial.gate.landmark-relationships",
    "no-equal-or-better-competing-candidate": "radial.gate.competitor-resolution",
    "explicit-human-anatomical-review": "radial.gate.human-review",
}

SUPERFICIAL_GATE_IDS = {
    "direct-observation-over-procedure-relevant-extent": "superficial.gate.direct-extent",
    "single-structure-continuity": "superficial.gate.continuity",
    "superficial-subcutaneous-relationship": "superficial.gate.subcutaneous-relationship",
    "vein-class-evidence": "superficial.gate.vein-class",
    "competing-track-conflict-review": "superficial.gate.competitor-resolution",
    "explicit-human-anatomical-review": "superficial.gate.human-review",
}

RADIAL_CLAIM_IDS = set(RADIAL_GATE_IDS.values())
SUPERFICIAL_TARGET_CLAIM_IDS = set(SUPERFICIAL_GATE_IDS.values()) | {
    "superficial.structure.observed",
    "superficial.identity.named-topology",
    "superficial.identity.named",
}
CLAIM_KIND_BY_ID = {
    "radial.gate.same-subject-anchor": "radial-artery-identity",
    "radial.gate.continuity": "track-continuity",
    "radial.gate.branch-topology": "branch-topology",
    "radial.gate.landmark-relationships": "landmark-relationship",
    "radial.gate.competitor-resolution": "competitor-resolution",
    "radial.gate.human-review": "radial-artery-identity",
    "superficial.gate.direct-extent": "track-continuity",
    "superficial.gate.continuity": "track-continuity",
    "superficial.gate.subcutaneous-relationship": "landmark-relationship",
    "superficial.gate.vein-class": "vessel-class",
    "superficial.gate.competitor-resolution": "competitor-resolution",
    "superficial.gate.human-review": "superficial-vein-structure",
    "superficial.structure.observed": "superficial-vein-structure",
    "superficial.identity.named-topology": "branch-topology",
    "superficial.identity.named": "named-superficial-vein-identity",
}



def load(path: Path) -> dict:
    return json.loads(Path(path).read_text())


def file_hash(path: Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def evidence_ref(path: Path, role: str) -> dict:
    value = load(path)
    return {
        "path": portable_path(path),
        "schema": value["schema"],
        "sha256": file_hash(path),
        "role": role,
    }


def gate_state(status: str) -> str:
    return {"pass": "supported", "fail": "blocked", "insufficient": "unresolved"}[status]


def claim_from_gate(domain: str, claim_id: str, gate: dict, source: str) -> dict:
    status = gate["status"]
    evidence = [
        {"source": source, "description": description}
        for description in gate.get("evidence", [])
    ]
    return {
        "id": claim_id,
        "domain": domain,
        "requirement": gate["requirement"],
        "state": gate_state(status),
        "supportingEvidence": evidence if status == "pass" else [],
        "conflictingEvidence": evidence if status == "fail" else [],
        "missingEvidence": [] if status == "pass" else [gate["reason"]],
        "humanReviewStatus": "not-reviewed",
        "validationLevel": "V0",
        "promotionEligible": False,
    }


def verify_review_session(
    session_path: Path, v07_path: Path, v07: dict, track: dict
) -> dict:
    session = load(session_path)
    if session.get("schema") != "ph-m8v-human-adjudication-session.v1":
        raise ValueError("unexpected human adjudication session schema")
    if session.get("task") != "TASK-V08":
        raise ValueError("unexpected human adjudication task")
    expected_surface_hash = file_hash(v07_path)
    review_surface = session.get("reviewSurface", {})
    if review_surface.get("path") != portable_path(v07_path):
        raise ValueError("human review references a different TASK-V07 path")
    if review_surface.get("sha256") != expected_surface_hash:
        raise ValueError("stale human review: TASK-V07 hash mismatch")

    expected_snapshot = {
        (row["path"], row["schema"], row["sha256"]) for row in v07["inputEvidence"]
    }
    actual_rows = session.get("evidenceSnapshot", [])
    actual_snapshot = {
        (row["path"], row["schema"], row["sha256"]) for row in actual_rows
    }
    if actual_snapshot != expected_snapshot or len(actual_rows) != len(v07["inputEvidence"]):
        raise ValueError("stale human review: evidence snapshot mismatch")

    competitor_sets = {row["id"]: set(row["trackIds"]) for row in track["competitorSets"]}
    radial_targets = competitor_sets.get("vhf.m8v.competitors.branch-identity")
    superficial_targets = competitor_sets.get("vhf.m8v.competitors.superficial-structure")
    if not radial_targets or not superficial_targets:
        raise ValueError("TASK-V04 competitor sets are missing or empty")
    if radial_targets & superficial_targets:
        raise ValueError("TASK-V04 radial and superficial competitor sets overlap")

    first_frame = v07["frameCoverage"]["firstWholeBodyFrameIndex"]
    last_frame = v07["frameCoverage"]["lastWholeBodyFrameIndex"]
    per_domain_targets: dict[str, set[str]] = {"radial": set(), "superficial": set()}
    seen_claims: set[str] = set()
    for decision in session.get("decisions", []):
        claim_id = decision.get("claimId")
        if claim_id not in CLAIM_KIND_BY_ID:
            raise ValueError(f"unknown human adjudication claim: {claim_id}")
        if claim_id in seen_claims:
            raise ValueError(f"duplicate human adjudication claim in one session: {claim_id}")
        seen_claims.add(claim_id)
        if decision.get("kind") != CLAIM_KIND_BY_ID[claim_id]:
            raise ValueError(f"human adjudication kind mismatch for claim: {claim_id}")

        target_id = decision.get("targetId")
        if claim_id in RADIAL_CLAIM_IDS:
            if target_id not in radial_targets:
                raise ValueError(f"radial claim references non-radial competitor track: {target_id}")
            per_domain_targets["radial"].add(target_id)
        elif claim_id in SUPERFICIAL_TARGET_CLAIM_IDS:
            if target_id not in superficial_targets:
                raise ValueError(
                    f"superficial claim references non-superficial competitor track: {target_id}"
                )
            per_domain_targets["superficial"].add(target_id)

        frames = decision.get("evidenceFrameIndices", [])
        if decision.get("verdict") == "accepted" and not frames:
            raise ValueError("accepted human adjudication requires at least one evidence frame")
        if any(frame < first_frame or frame > last_frame for frame in frames):
            raise ValueError("human adjudication references a frame outside TASK-V07 coverage")

    for domain, targets in per_domain_targets.items():
        if len(targets) > 1:
            raise ValueError(f"human adjudication mixes multiple {domain} target tracks")
    return session


def apply_human_reviews(claims: list[dict], sessions: list[tuple[Path, dict]]) -> None:
    by_claim = {claim["id"]: claim for claim in claims}
    seen: dict[str, tuple[str, str]] = {}
    for _, session in sessions:
        for decision in session["decisions"]:
            claim_id = decision["claimId"]
            verdict = decision["verdict"]
            target_id = decision["targetId"]
            current = (verdict, target_id)
            previous = seen.get(claim_id)
            claim = by_claim[claim_id]
            if previous is not None and previous != current:
                claim["humanReviewStatus"] = "unresolved"
                claim["humanReviewTargetId"] = None
                claim["state"] = "conflicting"
                claim["validationLevel"] = "V2"
                claim["conflictingEvidence"].append(
                    {
                        "source": "TASK-V08 human adjudication",
                        "description": "Human adjudication sessions contain conflicting verdicts or target tracks for this claim.",
                    }
                )
                continue

            seen[claim_id] = current
            claim["humanReviewStatus"] = verdict
            claim["humanReviewTargetId"] = target_id
            description = decision.get("note") or f"Human anatomical adjudication verdict: {verdict}."
            description += f" Target track: {target_id}. Evidence frames: " + ", ".join(
                str(frame) for frame in decision.get("evidenceFrameIndices", [])
            )
            if verdict == "accepted":
                claim["state"] = "supported"
                claim["supportingEvidence"].append(
                    {"source": "TASK-V08 human adjudication", "description": description}
                )
                claim["missingEvidence"] = []
                claim["validationLevel"] = "V2"
            elif verdict == "rejected":
                claim["state"] = "conflicting"
                claim["conflictingEvidence"].append(
                    {"source": "TASK-V08 human adjudication", "description": description}
                )
                claim["validationLevel"] = "V2"
            else:
                claim["state"] = "unresolved"
                claim["conflictingEvidence"].append(
                    {"source": "TASK-V08 human adjudication", "description": description}
                )
                claim["validationLevel"] = "V2"


def build_ledger(
    radial_path: Path,
    superficial_path: Path,
    v07_path: Path,
    track_path: Path,
    landmark_path: Path,
    recorded_at: str,
    review_paths: list[Path] | None = None,
) -> dict:
    radial = load(radial_path)
    superficial = load(superficial_path)
    v07 = load(v07_path)
    track = load(track_path)
    landmarks = load(landmark_path)

    if radial.get("schema") != "ph-m8v-radial-artery-identity-evidence.v1":
        raise ValueError("unexpected TASK-V05 record")
    if superficial.get("schema") != "ph-m8v-superficial-venous-network-evidence.v1":
        raise ValueError("unexpected TASK-V06 record")
    if v07.get("schema") != "ph-m8v-multimodal-review-surface.v1":
        raise ValueError("unexpected TASK-V07 record")
    if track.get("schema") != "ph-m8v-candidate-vessel-track-graph.v1":
        raise ValueError("unexpected TASK-V04 record")
    if landmarks.get("schema") != "ph-m8v-upper-extremity-landmark-graph.v1":
        raise ValueError("unexpected TASK-V03 record")
    if v07["claims"]["humanAnatomicalReviewCompleted"] is not False:
        raise ValueError("TASK-V07 must not itself claim human anatomical review")

    radial_gates = {row["id"]: row for row in radial["promotionGateEvaluations"]}
    superficial_gates = {row["id"]: row for row in superficial["promotionGateEvaluations"]}
    if set(radial_gates) != set(RADIAL_GATE_IDS):
        raise ValueError("radial gate set changed; explicit ledger mapping review required")
    if set(superficial_gates) != set(SUPERFICIAL_GATE_IDS):
        raise ValueError("superficial gate set changed; explicit ledger mapping review required")

    claims = [
        claim_from_gate("radial-artery", RADIAL_GATE_IDS[gate_id], radial_gates[gate_id], "TASK-V05")
        for gate_id in RADIAL_GATE_IDS
    ]
    claims.extend(
        claim_from_gate(
            "superficial-vein",
            SUPERFICIAL_GATE_IDS[gate_id],
            superficial_gates[gate_id],
            "TASK-V06",
        )
        for gate_id in SUPERFICIAL_GATE_IDS
    )
    claims.extend(
        [
            {
                "id": "superficial.structure.observed",
                "domain": "superficial-vein",
                "requirement": "All subject-scoped superficial-vein structure promotion gates must be supported.",
                "state": "blocked",
                "supportingEvidence": [],
                "conflictingEvidence": [],
                "missingEvidence": [
                    "TASK-V06 does not establish a procedure-relevant directly continuous superficial vein structure."
                ],
                "humanReviewStatus": "not-reviewed",
                "validationLevel": "V0",
                "promotionEligible": False,
            },
            {
                "id": "superficial.identity.named-topology",
                "domain": "named-superficial-vein",
                "requirement": "Named cephalic/basilic identity requires source-supported course and connection topology appropriate to that name.",
                "state": "missing",
                "supportingEvidence": [],
                "conflictingEvidence": [],
                "missingEvidence": [
                    "No source-supported named superficial-vein course or connection topology is established."
                ],
                "humanReviewStatus": "not-reviewed",
                "validationLevel": "V0",
                "promotionEligible": False,
            },
            {
                "id": "superficial.identity.named",
                "domain": "named-superficial-vein",
                "requirement": "Named superficial-vein identity requires an established observed structure, compatible named course/topology, and explicit identity-level human review.",
                "state": "blocked",
                "supportingEvidence": [],
                "conflictingEvidence": [],
                "missingEvidence": [
                    "No subject-scoped superficial vein structure is established.",
                    "No source-supported named superficial-vein course/topology is established.",
                    "No named superficial-vein human adjudication is recorded."
                ],
                "humanReviewStatus": "not-reviewed",
                "validationLevel": "V0",
                "promotionEligible": False,
            },
        ]
    )

    for claim in claims:
        claim.setdefault("humanReviewTargetId", None)

    verified_sessions: list[tuple[Path, dict]] = []
    for review_path in review_paths or []:
        verified_sessions.append(
            (review_path, verify_review_session(review_path, v07_path, v07, track))
        )
    apply_human_reviews(claims, verified_sessions)

    by_id = {claim["id"]: claim for claim in claims}
    radial_required = list(RADIAL_GATE_IDS.values())
    superficial_required = list(SUPERFICIAL_GATE_IDS.values())

    def accepted_shared_target(claim_ids: list[str]) -> str | None:
        if not all(
            by_id[claim_id]["state"] == "supported"
            and by_id[claim_id]["humanReviewStatus"] == "accepted"
            for claim_id in claim_ids
        ):
            return None
        targets = {by_id[claim_id]["humanReviewTargetId"] for claim_id in claim_ids}
        if len(targets) != 1 or None in targets:
            return None
        return next(iter(targets))

    radial_target = accepted_shared_target(radial_required)
    superficial_target = accepted_shared_target(superficial_required)
    radial_ready = radial_target is not None
    superficial_ready = superficial_target is not None

    structure_claim = by_id["superficial.structure.observed"]
    structure_claim["promotionEligible"] = superficial_ready
    if superficial_ready:
        structure_claim["state"] = "supported"
        structure_claim["humanReviewTargetId"] = superficial_target
        structure_claim["missingEvidence"] = []
        structure_claim["supportingEvidence"].append(
            {
                "source": "TASK-V08 aggregate",
                "description": "All six subject-scoped superficial-vein structure gates are supported independently.",
            }
        )

    named_topology_claim = by_id["superficial.identity.named-topology"]
    named_identity_claim = by_id["superficial.identity.named"]
    named_topology = (
        named_topology_claim["state"] == "supported"
        and named_topology_claim["humanReviewStatus"] == "accepted"
        and named_topology_claim["humanReviewTargetId"] == superficial_target
    )
    named_identity_review = (
        named_identity_claim["humanReviewStatus"] == "accepted"
        and named_identity_claim["humanReviewTargetId"] == superficial_target
    )
    named_ready = superficial_ready and named_topology and named_identity_review
    named_claim = by_id["superficial.identity.named"]
    named_claim["promotionEligible"] = named_ready
    if named_ready:
        named_claim["state"] = "supported"
        named_claim["missingEvidence"] = []

    for claim_id in radial_required:
        by_id[claim_id]["promotionEligible"] = radial_ready
    for claim_id in superficial_required:
        by_id[claim_id]["promotionEligible"] = superficial_ready
    by_id["superficial.identity.named-topology"]["promotionEligible"] = named_ready

    human_refs = [
        {
            "path": portable_path(path),
            "sha256": file_hash(path),
            "reviewerReference": session["reviewerReference"],
            "decisionCount": len(session["decisions"]),
        }
        for path, session in verified_sessions
    ]

    if radial_ready or superficial_ready or named_ready:
        ledger_state = "promotion-ready"
    elif verified_sessions:
        ledger_state = "partially-adjudicated"
    else:
        ledger_state = "blocked-unresolved"

    return {
        "schema": "ph-m8v-evidence-ledger.v1",
        "schemaVersion": "1",
        "task": "TASK-V08",
        "recordedAt": recorded_at,
        "status": "complete",
        "sourceEvidence": [
            evidence_ref(track_path, "candidate-vessel-track-graph"),
            evidence_ref(landmark_path, "upper-extremity-landmarks"),
            evidence_ref(radial_path, "radial-promotion-gate-evidence"),
            evidence_ref(superficial_path, "superficial-promotion-gate-evidence"),
            evidence_ref(v07_path, "multimodal-review-surface"),
        ],
        "humanReviewSessions": human_refs,
        "claims": claims,
        "decision": {
            "ledgerState": ledger_state,
            "humanAdjudicationEvidencePresent": bool(verified_sessions),
            "radialPromotionReady": radial_ready,
            "superficialStructurePromotionReady": superficial_ready,
            "namedSuperficialPromotionReady": named_ready,
            "nextTask": "TASK-V09",
        },
        "assertions": {
            "medicalValidation": False,
            "patientSpaceGeometry": False,
            "procedureRoleEstablished": False,
            "automaticPromotionAllowed": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--radial", type=Path, required=True)
    parser.add_argument("--superficial", type=Path, required=True)
    parser.add_argument("--review-surface", type=Path, required=True)
    parser.add_argument("--tracks", type=Path, required=True)
    parser.add_argument("--landmarks", type=Path, required=True)
    parser.add_argument("--human-review", type=Path, action="append", default=[])
    parser.add_argument("--recorded-at", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_ledger(
        args.radial,
        args.superficial,
        args.review_surface,
        args.tracks,
        args.landmarks,
        args.recorded_at,
        args.human_review,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result["decision"], indent=2))


if __name__ == "__main__":
    main()
