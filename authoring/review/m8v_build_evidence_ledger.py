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


RADIAL_GATE_IDS = {
    "same-subject-proximal-or-unique-anchor": "radial.gate.same-subject-anchor",
    "same-subject-continuity-to-target": "radial.gate.continuity",
    "compatible-branch-topology": "radial.gate.branch-topology",
    "compatible-source-supported-landmarks": "radial.gate.landmark-relationships",
    "no-equal-or-better-unresolved-competitor": "radial.gate.competitor-resolution",
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


def load(path: Path) -> dict:
    return json.loads(Path(path).read_text())


def file_hash(path: Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def evidence_ref(path: Path, role: str) -> dict:
    value = load(path)
    return {
        "path": Path(path).as_posix(),
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


def verify_review_session(session_path: Path, v07_path: Path, v07: dict) -> dict:
    session = load(session_path)
    if session.get("schema") != "ph-m8v-human-adjudication-session.v1":
        raise ValueError("unexpected human adjudication session schema")
    if session.get("task") != "TASK-V08":
        raise ValueError("unexpected human adjudication task")
    expected_surface_hash = file_hash(v07_path)
    review_surface = session.get("reviewSurface", {})
    if review_surface.get("path") != Path(v07_path).as_posix():
        raise ValueError("human review references a different TASK-V07 path")
    if review_surface.get("sha256") != expected_surface_hash:
        raise ValueError("stale human review: TASK-V07 hash mismatch")

    expected_snapshot = {
        (row["path"], row["schema"], row["sha256"])
        for row in v07["inputEvidence"]
    }
    actual_snapshot = {
        (row["path"], row["schema"], row["sha256"])
        for row in session.get("evidenceSnapshot", [])
    }
    if actual_snapshot != expected_snapshot:
        raise ValueError("stale human review: evidence snapshot mismatch")
    return session


def apply_human_reviews(claims: list[dict], sessions: list[tuple[Path, dict]]) -> None:
    by_claim = {claim["id"]: claim for claim in claims}
    seen: dict[str, str] = {}
    for _, session in sessions:
        for decision in session["decisions"]:
            claim_id = decision["claimId"]
            if claim_id not in by_claim:
                continue
            verdict = decision["verdict"]
            previous = seen.get(claim_id)
            if previous is not None and previous != verdict:
                claim = by_claim[claim_id]
                claim["humanReviewStatus"] = "unresolved"
                claim["state"] = "conflicting"
                claim["conflictingEvidence"].append(
                    {
                        "source": "TASK-V08 human adjudication",
                        "description": "Human adjudication sessions contain conflicting verdicts for this claim.",
                    }
                )
                continue
            seen[claim_id] = verdict
            claim = by_claim[claim_id]
            claim["humanReviewStatus"] = verdict
            claim["supportingEvidence" if verdict == "accepted" else "conflictingEvidence"].append(
                {
                    "source": "TASK-V08 human adjudication",
                    "description": decision.get("note")
                    or f"Human anatomical adjudication verdict: {verdict}.",
                }
            )

            # Human review can satisfy only the explicit human-review gates.
            if claim_id in {"radial.gate.human-review", "superficial.gate.human-review"}:
                if verdict == "accepted":
                    claim["state"] = "supported"
                    claim["missingEvidence"] = []
                    claim["validationLevel"] = "V2"
                elif verdict == "rejected":
                    claim["state"] = "conflicting"
                else:
                    claim["state"] = "unresolved"


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
                "id": "superficial.identity.named",
                "domain": "named-superficial-vein",
                "requirement": "Named cephalic/basilic identity requires source-supported named course/topology beyond superficial position.",
                "state": "blocked",
                "supportingEvidence": [],
                "conflictingEvidence": [],
                "missingEvidence": [
                    "No subject-scoped superficial vein structure is established.",
                    "No source-supported named superficial-vein course/topology is established."
                ],
                "humanReviewStatus": "not-reviewed",
                "validationLevel": "V0",
                "promotionEligible": False,
            },
        ]
    )

    verified_sessions: list[tuple[Path, dict]] = []
    for review_path in review_paths or []:
        verified_sessions.append((review_path, verify_review_session(review_path, v07_path, v07)))
    apply_human_reviews(claims, verified_sessions)

    by_id = {claim["id"]: claim for claim in claims}
    radial_required = [RADIAL_GATE_IDS[key] for key in RADIAL_GATE_IDS]
    superficial_required = [SUPERFICIAL_GATE_IDS[key] for key in SUPERFICIAL_GATE_IDS]
    radial_ready = all(by_id[claim_id]["state"] == "supported" for claim_id in radial_required)
    superficial_ready = all(by_id[claim_id]["state"] == "supported" for claim_id in superficial_required)

    by_id["superficial.structure.observed"]["promotionEligible"] = superficial_ready
    if superficial_ready:
        by_id["superficial.structure.observed"]["state"] = "supported"
        by_id["superficial.structure.observed"]["missingEvidence"] = []

    named_ready = False  # Named topology is not established in V01–V07.

    human_refs = [
        {
            "path": path.as_posix(),
            "sha256": file_hash(path),
            "reviewerReference": session["reviewerReference"],
            "decisionCount": len(session["decisions"]),
        }
        for path, session in verified_sessions
    ]

    states = {claim["state"] for claim in claims}
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
