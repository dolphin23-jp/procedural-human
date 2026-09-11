"""Evaluate TASK-V09 vessel-identity promotion gates independently and fail closed.

TASK-V09 does not create anatomy and does not auto-promote anything. It re-derives
promotion readiness from the claim-level TASK-V08 ledger, checks target consistency
against the TASK-V04 competitor sets, verifies the ledger's immutable source snapshot,
and rejects any inconsistency between claim state and aggregate readiness flags.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
V2_OR_HIGHER = {"V2", "V3", "V4"}

RADIAL_REQUIRED = [
    "radial.gate.same-subject-anchor",
    "radial.gate.continuity",
    "radial.gate.branch-topology",
    "radial.gate.landmark-relationships",
    "radial.gate.competitor-resolution",
    "radial.gate.human-review",
]
SUPERFICIAL_REQUIRED = [
    "superficial.gate.direct-extent",
    "superficial.gate.continuity",
    "superficial.gate.subcutaneous-relationship",
    "superficial.gate.vein-class",
    "superficial.gate.competitor-resolution",
    "superficial.gate.human-review",
]
STRUCTURE_CLAIM = "superficial.structure.observed"
NAMED_TOPOLOGY_CLAIM = "superficial.identity.named-topology"
NAMED_IDENTITY_CLAIM = "superficial.identity.named"
NAMED_REQUIRED = SUPERFICIAL_REQUIRED + [
    STRUCTURE_CLAIM,
    NAMED_TOPOLOGY_CLAIM,
    NAMED_IDENTITY_CLAIM,
]

EXPECTED_DOMAINS = {
    **{claim_id: "radial-artery" for claim_id in RADIAL_REQUIRED},
    **{claim_id: "superficial-vein" for claim_id in SUPERFICIAL_REQUIRED},
    STRUCTURE_CLAIM: "superficial-vein",
    NAMED_TOPOLOGY_CLAIM: "named-superficial-vein",
    NAMED_IDENTITY_CLAIM: "named-superficial-vein",
}
EXPECTED_SOURCE_ROLES = {
    "candidate-vessel-track-graph",
    "upper-extremity-landmarks",
    "radial-promotion-gate-evidence",
    "superficial-promotion-gate-evidence",
    "multimodal-review-surface",
}


class IdentityPromotionEvaluationError(ValueError):
    """Raised when promotion evidence is stale, inconsistent, or unsafe to evaluate."""


def load(path: Path) -> dict:
    return json.loads(Path(path).read_text())


def file_hash(path: Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def portable_path(path: Path) -> str:
    value = Path(path)
    if value.is_absolute():
        try:
            return value.resolve().relative_to(ROOT).as_posix()
        except ValueError:
            return value.as_posix()
    return value.as_posix()


def source_ref(path: Path, role: str) -> dict:
    value = load(path)
    return {
        "path": portable_path(path),
        "schema": value["schema"],
        "sha256": file_hash(path),
        "role": role,
    }


def resolve_repo_source(path_value: str) -> Path:
    relative = Path(path_value)
    if relative.is_absolute() or ".." in relative.parts:
        raise IdentityPromotionEvaluationError(
            f"ledger source path is not repository-relative: {path_value}"
        )
    resolved = (ROOT / relative).resolve()
    try:
        resolved.relative_to(ROOT)
    except ValueError as exc:
        raise IdentityPromotionEvaluationError(
            f"ledger source escapes repository root: {path_value}"
        ) from exc
    return resolved


def verify_ledger_source_snapshot(ledger: dict) -> None:
    rows = ledger.get("sourceEvidence", [])
    roles = [row.get("role") for row in rows]
    if len(rows) != len(EXPECTED_SOURCE_ROLES) or set(roles) != EXPECTED_SOURCE_ROLES:
        raise IdentityPromotionEvaluationError(
            "TASK-V08 source-evidence roles changed; explicit TASK-V09 review required"
        )
    if len(set(roles)) != len(roles):
        raise IdentityPromotionEvaluationError("duplicate TASK-V08 source-evidence role")

    for row in rows:
        source_path = resolve_repo_source(row["path"])
        if not source_path.is_file():
            raise IdentityPromotionEvaluationError(
                f"TASK-V08 source evidence is missing: {row['path']}"
            )
        if file_hash(source_path) != row["sha256"]:
            raise IdentityPromotionEvaluationError(
                f"TASK-V08 source evidence hash mismatch: {row['path']}"
            )
        source = load(source_path)
        if source.get("schema") != row["schema"]:
            raise IdentityPromotionEvaluationError(
                f"TASK-V08 source evidence schema mismatch: {row['path']}"
            )


def claim_index(ledger: dict) -> dict[str, dict]:
    claims = ledger.get("claims", [])
    ids = [row.get("id") for row in claims]
    if len(ids) != len(set(ids)):
        raise IdentityPromotionEvaluationError("TASK-V08 ledger contains duplicate claim ids")
    if set(ids) != set(EXPECTED_DOMAINS):
        missing = sorted(set(EXPECTED_DOMAINS) - set(ids))
        extra = sorted(set(ids) - set(EXPECTED_DOMAINS))
        raise IdentityPromotionEvaluationError(
            f"TASK-V08 claim set changed; missing={missing}, extra={extra}"
        )
    indexed = {row["id"]: row for row in claims}
    for claim_id, expected_domain in EXPECTED_DOMAINS.items():
        if indexed[claim_id].get("domain") != expected_domain:
            raise IdentityPromotionEvaluationError(
                f"claim domain mismatch for {claim_id}: {indexed[claim_id].get('domain')}"
            )
    return indexed


def competitor_sets(track_graph: dict) -> tuple[set[str], set[str]]:
    if track_graph.get("schema") != "ph-m8v-candidate-vessel-track-graph.v1":
        raise IdentityPromotionEvaluationError("unexpected TASK-V04 track graph schema")
    if track_graph.get("task") != "TASK-V04" or track_graph.get("status") != "complete":
        raise IdentityPromotionEvaluationError("TASK-V04 track graph is not complete")

    sets = {row["id"]: set(row["trackIds"]) for row in track_graph["competitorSets"]}
    radial = sets.get("vhf.m8v.competitors.branch-identity")
    superficial = sets.get("vhf.m8v.competitors.superficial-structure")
    if not radial or not superficial:
        raise IdentityPromotionEvaluationError("required TASK-V04 competitor set is missing")
    if radial & superficial:
        raise IdentityPromotionEvaluationError("TASK-V04 competitor domains overlap")

    tracks = {row["id"]: row for row in track_graph["tracks"]}
    if not radial <= set(tracks) or not superficial <= set(tracks):
        raise IdentityPromotionEvaluationError("competitor set references an unknown track")
    if any(tracks[track_id]["trackClass"] != "anonymous-branch-search" for track_id in radial):
        raise IdentityPromotionEvaluationError("radial competitor set contains a non-branch track")
    if any(
        tracks[track_id]["trackClass"] != "anonymous-superficial-search"
        for track_id in superficial
    ):
        raise IdentityPromotionEvaluationError(
            "superficial competitor set contains a non-superficial track"
        )
    return radial, superficial


def reviewed_claim_result(claim: dict, allowed_targets: set[str]) -> dict:
    reasons: list[str] = []
    if claim.get("state") != "supported":
        reasons.append(f"claim state is {claim.get('state')}, not supported")
    if claim.get("humanReviewStatus") != "accepted":
        reasons.append(
            f"human review is {claim.get('humanReviewStatus')}, not accepted"
        )
    if claim.get("validationLevel") not in V2_OR_HIGHER:
        reasons.append(
            f"validation level is {claim.get('validationLevel')}, below explicit human anatomical review"
        )
    target_id = claim.get("humanReviewTargetId")
    if target_id is None:
        reasons.append("no reviewed target track is bound to the claim")
    elif target_id not in allowed_targets:
        raise IdentityPromotionEvaluationError(
            f"claim {claim['id']} references a target outside its TASK-V04 competitor set: {target_id}"
        )
    return {
        "claimId": claim["id"],
        "state": claim["state"],
        "humanReviewStatus": claim["humanReviewStatus"],
        "validationLevel": claim["validationLevel"],
        "humanReviewTargetId": target_id,
        "promotionEligible": claim["promotionEligible"],
        "pass": not reasons,
        "reasons": reasons,
    }


def aggregate_structure_result(claim: dict, allowed_targets: set[str]) -> dict:
    reasons: list[str] = []
    if claim.get("state") != "supported":
        reasons.append(f"aggregate structure state is {claim.get('state')}, not supported")
    target_id = claim.get("humanReviewTargetId")
    if target_id is None:
        reasons.append("aggregate structure has no reviewed target track")
    elif target_id not in allowed_targets:
        raise IdentityPromotionEvaluationError(
            f"aggregate superficial structure references an invalid target: {target_id}"
        )
    return {
        "claimId": claim["id"],
        "state": claim["state"],
        "humanReviewStatus": claim["humanReviewStatus"],
        "validationLevel": claim["validationLevel"],
        "humanReviewTargetId": target_id,
        "promotionEligible": claim["promotionEligible"],
        "pass": not reasons,
        "reasons": reasons,
    }


def target_consistency(
    results: list[dict], allowed_targets: set[str]
) -> tuple[bool, bool, str | None, list[str]]:
    reasons: list[str] = []
    targets = [row["humanReviewTargetId"] for row in results]
    non_null = {target for target in targets if target is not None}
    if len(non_null) != 1:
        if not non_null:
            reasons.append("no single reviewed target is present across required claims")
        else:
            reasons.append("required claims reference multiple target tracks")
        return False, False, None, reasons
    target_id = next(iter(non_null))
    if any(target != target_id for target in targets):
        reasons.append("one or more required claims are not bound to the shared target")
        return False, target_id in allowed_targets, None, reasons
    if target_id not in allowed_targets:
        reasons.append("shared target is outside the allowed TASK-V04 competitor set")
        return True, False, None, reasons
    return True, True, target_id, reasons


def make_evaluation(
    target_claim: str,
    competitor_set_id: str,
    required_claim_ids: list[str],
    results: list[dict],
    allowed_targets: set[str],
) -> dict:
    consistency_pass, membership_pass, target_id, target_reasons = target_consistency(
        results, allowed_targets
    )
    all_claims_pass = all(row["pass"] for row in results)
    promotion_pass = all_claims_pass and consistency_pass and membership_pass
    blocking_claim_ids = [row["claimId"] for row in results if not row["pass"]]
    blocking_reasons = list(target_reasons)
    if not all_claims_pass:
        blocking_reasons.append("one or more required claim-level gates do not pass")
    return {
        "targetClaim": target_claim,
        "competitorSetId": competitor_set_id,
        "requiredClaimIds": required_claim_ids,
        "claimResults": results,
        "targetId": target_id,
        "targetConsistencyPass": consistency_pass,
        "targetInAllowedCompetitorSet": membership_pass,
        "allRequiredClaimsPass": all_claims_pass,
        "promotionGatePassed": promotion_pass,
        "decision": "promotable" if promotion_pass else "blocked-unresolved",
        "blockingClaimIds": blocking_claim_ids,
        "blockingReasons": blocking_reasons,
    }


def evaluate(ledger: dict, track_graph: dict) -> tuple[dict, dict]:
    if ledger.get("schema") != "ph-m8v-evidence-ledger.v1":
        raise IdentityPromotionEvaluationError("unexpected TASK-V08 evidence ledger schema")
    if ledger.get("task") != "TASK-V08" or ledger.get("status") != "complete":
        raise IdentityPromotionEvaluationError("TASK-V08 evidence ledger is not complete")

    assertions = ledger.get("assertions", {})
    prohibited = (
        "medicalValidation",
        "patientSpaceGeometry",
        "procedureRoleEstablished",
        "automaticPromotionAllowed",
    )
    if any(assertions.get(key) is not False for key in prohibited):
        raise IdentityPromotionEvaluationError(
            "TASK-V08 contains a prohibited validation, Patient Space, procedure-role, or automatic-promotion assertion"
        )

    claims = claim_index(ledger)
    radial_targets, superficial_targets = competitor_sets(track_graph)

    radial_results = [
        reviewed_claim_result(claims[claim_id], radial_targets)
        for claim_id in RADIAL_REQUIRED
    ]
    radial = make_evaluation(
        "structure.radial_artery.left",
        "vhf.m8v.competitors.branch-identity",
        list(RADIAL_REQUIRED),
        radial_results,
        radial_targets,
    )

    superficial_results = [
        reviewed_claim_result(claims[claim_id], superficial_targets)
        for claim_id in SUPERFICIAL_REQUIRED
    ]
    superficial = make_evaluation(
        "subject-scoped-superficial-vein-structure",
        "vhf.m8v.competitors.superficial-structure",
        list(SUPERFICIAL_REQUIRED),
        superficial_results,
        superficial_targets,
    )

    named_results = list(superficial_results)
    named_results.append(aggregate_structure_result(claims[STRUCTURE_CLAIM], superficial_targets))
    named_results.append(reviewed_claim_result(claims[NAMED_TOPOLOGY_CLAIM], superficial_targets))
    named_results.append(reviewed_claim_result(claims[NAMED_IDENTITY_CLAIM], superficial_targets))
    named = make_evaluation(
        "named-superficial-vein-identity",
        "vhf.m8v.competitors.superficial-structure",
        list(NAMED_REQUIRED),
        named_results,
        superficial_targets,
    )

    # Aggregate claim flags are cross-checks, never trusted as the source of truth.
    for claim_id in RADIAL_REQUIRED:
        if claims[claim_id]["promotionEligible"] is not radial["promotionGatePassed"]:
            raise IdentityPromotionEvaluationError(
                f"TASK-V08 radial promotionEligible mismatch for {claim_id}"
            )
    for claim_id in SUPERFICIAL_REQUIRED:
        if claims[claim_id]["promotionEligible"] is not superficial["promotionGatePassed"]:
            raise IdentityPromotionEvaluationError(
                f"TASK-V08 superficial promotionEligible mismatch for {claim_id}"
            )
    if claims[STRUCTURE_CLAIM]["promotionEligible"] is not superficial["promotionGatePassed"]:
        raise IdentityPromotionEvaluationError(
            "TASK-V08 aggregate superficial structure promotionEligible mismatch"
        )
    for claim_id in (NAMED_TOPOLOGY_CLAIM, NAMED_IDENTITY_CLAIM):
        if claims[claim_id]["promotionEligible"] is not named["promotionGatePassed"]:
            raise IdentityPromotionEvaluationError(
                f"TASK-V08 named promotionEligible mismatch for {claim_id}"
            )

    declared = ledger.get("decision", {})
    computed_flags = {
        "radialPromotionReady": radial["promotionGatePassed"],
        "superficialStructurePromotionReady": superficial["promotionGatePassed"],
        "namedSuperficialPromotionReady": named["promotionGatePassed"],
    }
    for key, computed in computed_flags.items():
        if declared.get(key) is not computed:
            raise IdentityPromotionEvaluationError(
                f"TASK-V08 aggregate decision mismatch for {key}"
            )

    sessions_present = bool(ledger.get("humanReviewSessions"))
    if declared.get("humanAdjudicationEvidencePresent") is not sessions_present:
        raise IdentityPromotionEvaluationError(
            "TASK-V08 human-adjudication presence flag does not match review receipts"
        )
    if any(computed_flags.values()) and not sessions_present:
        raise IdentityPromotionEvaluationError(
            "promotion readiness cannot exist without explicit human review receipts"
        )

    expected_ledger_state = (
        "promotion-ready"
        if any(computed_flags.values())
        else "partially-adjudicated"
        if sessions_present
        else "blocked-unresolved"
    )
    if declared.get("ledgerState") != expected_ledger_state:
        raise IdentityPromotionEvaluationError(
            "TASK-V08 ledgerState is inconsistent with independently recomputed readiness"
        )

    evaluations = {
        "radialArtery": radial,
        "superficialStructure": superficial,
        "namedSuperficialVein": named,
    }
    cross_checks = {
        "ledgerDecisionConsistency": True,
        "targetDomainMembershipVerified": True,
        "prohibitedAssertionsRemainFalse": True,
        "procedureRoleExcluded": True,
    }
    return evaluations, cross_checks


def build_evaluation(
    ledger_path: Path,
    track_path: Path,
    recorded_at: str,
) -> dict:
    ledger = load(ledger_path)
    track_graph = load(track_path)
    verify_ledger_source_snapshot(ledger)

    track_refs = [
        row
        for row in ledger["sourceEvidence"]
        if row["role"] == "candidate-vessel-track-graph"
    ]
    if len(track_refs) != 1:
        raise IdentityPromotionEvaluationError(
            "TASK-V08 must reference exactly one candidate-vessel track graph"
        )
    track_ref = track_refs[0]
    if track_ref["path"] != portable_path(track_path):
        raise IdentityPromotionEvaluationError(
            "TASK-V09 track graph path differs from TASK-V08 evidence snapshot"
        )
    if track_ref["sha256"] != file_hash(track_path):
        raise IdentityPromotionEvaluationError(
            "TASK-V09 track graph hash differs from TASK-V08 evidence snapshot"
        )

    evaluations, cross_checks = evaluate(ledger, track_graph)
    passes = [row["promotionGatePassed"] for row in evaluations.values()]
    return {
        "schema": "ph-m8v-identity-promotion-evaluation.v1",
        "schemaVersion": "1",
        "task": "TASK-V09",
        "recordedAt": recorded_at,
        "status": "complete",
        "sourceEvidence": [
            source_ref(ledger_path, "evidence-ledger"),
            source_ref(track_path, "candidate-vessel-track-graph"),
        ],
        "crossChecks": {
            **cross_checks,
            "ledgerSourceSnapshotHashesVerified": True,
        },
        "evaluations": evaluations,
        "decision": {
            "state": "promotion-ready" if any(passes) else "blocked-unresolved",
            "anyPromotionGatePassed": any(passes),
            "nextTask": "TASK-V10",
        },
        "claims": {
            "radialArteryPromotionGatePassed": evaluations["radialArtery"]["promotionGatePassed"],
            "superficialStructurePromotionGatePassed": evaluations["superficialStructure"]["promotionGatePassed"],
            "namedSuperficialVeinPromotionGatePassed": evaluations["namedSuperficialVein"]["promotionGatePassed"],
            "medicalValidation": False,
            "patientSpaceGeometry": False,
            "procedureRoleEstablished": False,
            "automaticPromotionAllowed": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--tracks", type=Path, required=True)
    parser.add_argument("--recorded-at", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = build_evaluation(args.ledger, args.tracks, args.recorded_at)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result["decision"], indent=2))


if __name__ == "__main__":
    main()
