"""Feed TASK-V09 promotion decisions into M8A and re-evaluate TASK-A10.

This step is deliberately provenance-only. It never fabricates or mutates an anatomical
representation. Claims whose TASK-V09 promotion gate did not pass are carried into M8A
as explicit blockers. Existing valid ulnar work is preserved without expanding its
identity or extent. If a future V09 record contains a passed gate, this builder records
that claim as eligible for the corresponding M8A authoring step but still does not invent
A08/A09 geometry or create a Medical Master by itself.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class M8VFeedForwardError(ValueError):
    """Raised when upstream M8V/M8A evidence is inconsistent or unsafe."""


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


def require(condition: bool, message: str) -> None:
    if not condition:
        raise M8VFeedForwardError(message)


def find_by_label(rows: list[dict], label: str) -> dict:
    matches = [row for row in rows if row.get("draftLabel") == label]
    if len(matches) != 1:
        raise M8VFeedForwardError(f"expected exactly one {label} row, found {len(matches)}")
    return matches[0]


def verify_inputs(
    v09: dict,
    as07: dict,
    a07: dict,
    a08: dict,
    a09: dict,
    a10: dict,
) -> None:
    require(
        v09.get("schema") == "ph-m8v-identity-promotion-evaluation.v1"
        and v09.get("task") == "TASK-V09"
        and v09.get("status") == "complete",
        "TASK-V09 promotion evaluation is not complete",
    )
    require(
        all(v09.get("crossChecks", {}).values()),
        "TASK-V09 cross-checks are not all satisfied",
    )
    for key in (
        "medicalValidation",
        "patientSpaceGeometry",
        "procedureRoleEstablished",
        "automaticPromotionAllowed",
    ):
        require(v09["claims"].get(key) is False, f"TASK-V09 prohibited claim is true: {key}")

    require(
        as07.get("schema") == "ph-as07-continuity-feed-forward.v1"
        and as07.get("task") == "TASK-AS07",
        "unexpected TASK-AS07 feed-forward evidence",
    )
    require(
        a07.get("schema") == "ph-semantic-structure-mapping.v1"
        and a07.get("task") == "TASK-A07",
        "unexpected TASK-A07 semantic mapping",
    )
    require(
        a08.get("schema") == "ph-vessel-centerline-authoring-report.v1"
        and a08.get("task") == "TASK-A08",
        "unexpected TASK-A08 centerline report",
    )
    require(
        a09.get("schema") == "ph-boundary-lumen-authoring-report.v1"
        and a09.get("task") == "TASK-A09",
        "unexpected TASK-A09 boundary/lumen report",
    )
    require(
        a10.get("schema") == "ph-medical-master-readiness.v1"
        and a10.get("task") == "TASK-A10",
        "unexpected TASK-A10 readiness record",
    )

    for source, name in ((a07, "A07"), (a08, "A08"), (a09, "A09")):
        claims = source.get("claims", {})
        require(claims.get("medicalValidation") is False, f"{name} medical validation unexpectedly true")
        require(claims.get("patientSpaceGeometry") is False, f"{name} Patient Space unexpectedly true")
    require(a10.get("claims", {}).get("medicalMasterCreated") is False, "A10 already claims a Medical Master")
    require(a10.get("claims", {}).get("automaticPromotionAllowed") is False, "A10 automatic promotion unexpectedly allowed")

    a07_ulnar = find_by_label(a07["mappings"], "ulnar_artery")
    a08_ulnar = find_by_label(a08["structures"], "ulnar_artery")
    a09_ulnar = find_by_label(a09["structures"], "ulnar_artery")
    require(a07_ulnar.get("representationAvailable") is True, "existing ulnar A07 representation disappeared")
    require(a08_ulnar.get("centerlineStatus") == "generated", "existing ulnar A08 centerline disappeared")
    require(a09_ulnar.get("representationStatus") == "generated", "existing ulnar A09 representation disappeared")


def promotion_state(v09: dict, key: str, claim_key: str) -> dict:
    evaluation = v09["evaluations"][key]
    passed = v09["claims"][claim_key]
    require(
        evaluation["promotionGatePassed"] is passed,
        f"TASK-V09 evaluation/claim mismatch for {key}",
    )
    if passed:
        require(evaluation.get("targetId") is not None, f"passed {key} gate has no targetId")
        require(evaluation.get("decision") == "promotable", f"passed {key} gate is not promotable")
    else:
        require(evaluation.get("decision") == "blocked-unresolved", f"blocked {key} gate has wrong decision")
    return {
        "promotionGatePassed": passed,
        "targetId": evaluation.get("targetId"),
        "blockingClaimIds": evaluation.get("blockingClaimIds", []),
        "blockingReasons": evaluation.get("blockingReasons", []),
    }


def build_feed_forward(
    v09_path: Path,
    as07_path: Path,
    a07_path: Path,
    a08_path: Path,
    a09_path: Path,
    a10_path: Path,
    recorded_at: str,
) -> dict:
    v09 = load(v09_path)
    as07 = load(as07_path)
    a07 = load(a07_path)
    a08 = load(a08_path)
    a09 = load(a09_path)
    a10 = load(a10_path)
    verify_inputs(v09, as07, a07, a08, a09, a10)

    radial = promotion_state(v09, "radialArtery", "radialArteryPromotionGatePassed")
    superficial = promotion_state(
        v09,
        "superficialStructure",
        "superficialStructurePromotionGatePassed",
    )
    named = promotion_state(
        v09,
        "namedSuperficialVein",
        "namedSuperficialVeinPromotionGatePassed",
    )

    any_passed = radial["promotionGatePassed"] or superficial["promotionGatePassed"] or named["promotionGatePassed"]
    require(
        v09["decision"]["anyPromotionGatePassed"] is any_passed,
        "TASK-V09 anyPromotionGatePassed is inconsistent with target gates",
    )

    radial_a07 = find_by_label(a07["mappings"], "radial_artery")
    radial_a08 = find_by_label(a08["structures"], "radial_artery")
    radial_a09 = find_by_label(a09["structures"], "radial_artery")
    require(
        not radial["promotionGatePassed"]
        or radial_a07.get("anatomicalId") == "structure.radial_artery.left",
        "radial promotion no longer matches the reserved A07 semantic identity",
    )

    superficial_unresolved = find_by_label(a07["unresolved"], "superficial_target_vein")
    superficial_a08 = find_by_label(a08["structures"], "superficial_target_vein")
    superficial_a09 = find_by_label(a09["structures"], "superficial_target_vein")

    actions = {
        "radialArtery": {
            "identityClaimStatus": "eligible-for-a07-authoring" if radial["promotionGatePassed"] else "blocked",
            "targetId": radial["targetId"],
            "existingA07RepresentationAvailable": radial_a07["representationAvailable"],
            "existingA08CenterlineStatus": radial_a08["centerlineStatus"],
            "existingA09RepresentationStatus": radial_a09["representationStatus"],
            "geometryPromotionApplied": False,
            "blockers": radial["blockingClaimIds"] + radial["blockingReasons"],
        },
        "superficialStructure": {
            "identityClaimStatus": "eligible-for-subject-scoped-a07-authoring" if superficial["promotionGatePassed"] else "blocked",
            "targetId": superficial["targetId"],
            "existingA07AnatomicalId": superficial_unresolved["anatomicalId"],
            "existingA08CenterlineStatus": superficial_a08["centerlineStatus"],
            "existingA09RepresentationStatus": superficial_a09["representationStatus"],
            "geometryPromotionApplied": False,
            "blockers": superficial["blockingClaimIds"] + superficial["blockingReasons"],
        },
        "namedSuperficialVein": {
            "identityClaimStatus": "eligible-for-named-a07-authoring" if named["promotionGatePassed"] else "blocked",
            "targetId": named["targetId"],
            "procedureRoleUsedAsIdentity": False,
            "geometryPromotionApplied": False,
            "blockers": named["blockingClaimIds"] + named["blockingReasons"],
        },
    }

    missing_geometry_after_identity = any(
        (
            radial["promotionGatePassed"]
            and (radial_a08["centerlineStatus"] != "generated" or radial_a09["representationStatus"] != "generated")
        ,
            superficial["promotionGatePassed"]
            and (
                superficial_a08["centerlineStatus"] != "generated"
                or superficial_a09["representationStatus"] != "generated"
            )
        )
    )
    # Even a passed identity gate does not invent A08/A09 geometry. Current A10 therefore
    # cannot become ready solely from TASK-V09.
    a10_ready = False
    blockers = list(a10.get("blockers", []))
    blockers.append(
        "TASK-V09 independently re-evaluated radial-artery, subject-scoped superficial-structure, and named-superficial identity promotion gates; only passed claim-level gates may feed into M8A."
    )
    if not radial["promotionGatePassed"]:
        blockers.append("TASK-V09 radial-artery promotion gate remains blocked-unresolved; no radial identity or representation is injected into A07/A08/A09.")
    if not superficial["promotionGatePassed"]:
        blockers.append("TASK-V09 subject-scoped superficial-structure promotion gate remains blocked-unresolved; no superficial target identity or representation is injected into A07/A08/A09.")
    if superficial["promotionGatePassed"] and not named["promotionGatePassed"]:
        blockers.append("A subject-scoped superficial structure may be eligible for authoring, but named superficial-vein identity remains independently blocked.")
    if missing_geometry_after_identity:
        blockers.append("Identity eligibility does not establish required A08 centerline or A09 lumen/boundary geometry; those representations require separate source-supported authoring and review.")
    blockers.append("Existing source-supported ulnar A07/A08/A09 work is preserved without expanding its named identity, extent, validation level, or coordinate-space claims.")

    return {
        "schema": "ph-m8v-m8a-feed-forward.v1",
        "schemaVersion": "1",
        "task": "TASK-V10",
        "recordedAt": recorded_at,
        "status": "complete",
        "sourceEvidence": [
            source_ref(v09_path, "m8v-promotion-evaluation"),
            source_ref(as07_path, "prior-m8a-feed-forward"),
            source_ref(a07_path, "a07-semantic-mapping"),
            source_ref(a08_path, "a08-centerline-report"),
            source_ref(a09_path, "a09-boundary-lumen-report"),
            source_ref(a10_path, "a10-readiness-record"),
        ],
        "promotionInput": {
            "anyPromotionGatePassed": any_passed,
            "radialArtery": radial,
            "superficialStructure": superficial,
            "namedSuperficialVein": named,
        },
        "feedForwardActions": actions,
        "preservedExistingEvidence": [
            {
                "anatomicalId": "structure.ulnar_artery.left",
                "a07RepresentationAvailable": True,
                "a08CenterlineStatus": "generated",
                "a09RepresentationStatus": "generated",
                "scope": "existing bounded source-supported representation only",
            }
        ],
        "a10Reevaluation": {
            "priorStatus": a10["status"],
            "status": "ready" if a10_ready else "blocked",
            "medicalMasterCreationAllowed": a10_ready,
            "blockers": blockers,
        },
        "gateV": {
            "status": "complete",
            "outcome": "promotion-fed" if any_passed else "fail-closed-documented",
            "allPassedClaimsFedWithoutGeometryFabrication": True,
            "unresolvedClaimsRemainBlocked": True,
            "a10Reevaluated": True,
        },
        "claims": {
            "newRadialIdentityApplied": radial["promotionGatePassed"],
            "newSuperficialStructureIdentityApplied": superficial["promotionGatePassed"],
            "newNamedSuperficialVeinIdentityApplied": named["promotionGatePassed"],
            "newGeometryPromoted": False,
            "existingUlnarEvidencePreserved": True,
            "medicalMasterCreated": a10_ready,
            "medicalValidation": False,
            "patientSpaceGeometry": False,
            "procedureRoleUsedAsAnatomicalIdentity": False,
            "automaticPromotionAllowed": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v09", type=Path, required=True)
    parser.add_argument("--as07", type=Path, required=True)
    parser.add_argument("--a07", type=Path, required=True)
    parser.add_argument("--a08", type=Path, required=True)
    parser.add_argument("--a09", type=Path, required=True)
    parser.add_argument("--a10", type=Path, required=True)
    parser.add_argument("--recorded-at", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = build_feed_forward(
        args.v09,
        args.as07,
        args.a07,
        args.a08,
        args.a09,
        args.a10,
        args.recorded_at,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "gateV": result["gateV"],
                "a10Status": result["a10Reevaluation"]["status"],
                "claims": result["claims"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
