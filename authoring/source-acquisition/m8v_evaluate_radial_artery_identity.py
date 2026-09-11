from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Any


class RadialIdentityEvidenceError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RadialIdentityEvidenceError(f"{path} must contain a JSON object")
    return value


def _sha256_path(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RadialIdentityEvidenceError(message)


def _source_ref(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    schema = data.get("schema")
    _require(isinstance(schema, str) and schema, f"{path} must declare schema")
    return {
        "path": str(path).replace("\\", "/"),
        "sha256": _sha256_path(path),
        "schema": schema,
    }


def _validate_registration_scaffold(data: dict[str, Any]) -> None:
    _require(
        data.get("schema") == "ph-m8v-ct-cryo-registration-scaffold.v1",
        "unexpected TASK-V02 schema",
    )
    _require(data.get("task") == "TASK-V02", "registration scaffold must be TASK-V02")
    _require(data.get("status") == "complete", "TASK-V02 must be complete")
    decision = data.get("decision", {})
    _require(
        decision.get("registrationState") == "bounded-bone-landmark-scaffold",
        "TASK-V02 registration must remain bounded bone-landmark scaffold",
    )
    _require(
        decision.get("identityCorrespondence")
        == "direct-radius-ulna-correspondence-supported",
        "TASK-V02 direct radius/ulna correspondence is required",
    )
    _require(
        "candidate-vessel-evidence-support" in decision.get("usableFor", []),
        "TASK-V02 must explicitly allow candidate-vessel evidence support",
    )
    claims = data.get("claims", {})
    for key in (
        "ctCryosectionMedicalRegistrationEstablished",
        "patientSpaceGeometry",
        "radialArteryIdentityEstablished",
        "medicalValidation",
        "automaticPromotionAllowed",
    ):
        _require(claims.get(key) is False, f"TASK-V02 claim {key} must remain false")


def _validate_landmark_graph(data: dict[str, Any]) -> None:
    _require(
        data.get("schema") == "ph-m8v-upper-extremity-landmark-graph.v1",
        "unexpected TASK-V03 schema",
    )
    _require(data.get("task") == "TASK-V03", "landmark graph must be TASK-V03")
    _require(data.get("status") == "complete", "TASK-V03 must be complete")
    claims = data.get("claims", {})
    _require(claims.get("radialArteryIdentityEstablished") is False, "TASK-V03 cannot establish radial identity")
    _require(claims.get("patientSpaceGeometry") is False, "TASK-V03 cannot claim Patient Space")


def _validate_track_graph(data: dict[str, Any]) -> None:
    _require(
        data.get("schema") == "ph-m8v-candidate-vessel-track-graph.v1",
        "unexpected TASK-V04 schema",
    )
    _require(data.get("task") == "TASK-V04", "track graph must be TASK-V04")
    _require(data.get("status") == "complete", "TASK-V04 must be complete")
    decision = data.get("decision", {})
    _require(decision.get("taskV05InputAvailable") is True, "TASK-V04 does not authorize TASK-V05")
    claims = data.get("claims", {})
    _require(claims.get("sourceIndex3DTrackGraphEstablished") is True, "TASK-V04 source-index graph is required")
    for key in (
        "physical3DGeometry",
        "patientSpaceGeometry",
        "radialArteryIdentityEstablished",
        "brachialArteryIdentityEstablished",
        "bifurcationIdentityEstablished",
        "medicalValidation",
        "automaticPromotionAllowed",
    ):
        _require(claims.get(key) is False, f"TASK-V04 claim {key} must remain false")


def _validate_same_subject_continuity(data: dict[str, Any]) -> None:
    _require(
        data.get("schema") == "ph-as06-same-subject-continuity-provenance.v1",
        "unexpected AS06 continuity provenance schema",
    )
    _require(data.get("task") == "TASK-AS06", "continuity provenance must be TASK-AS06")
    anchor = data.get("reviewedUlnarAnchor", {})
    _require(
        anchor.get("anatomicalId") == "structure.ulnar_artery.left",
        "the preserved reviewed anchor must be the left ulnar artery",
    )
    claims = data.get("claims", {})
    for key in (
        "radialArteryIdentityEstablished",
        "brachialArteryIdentityEstablished",
        "bifurcationIdentityEstablished",
        "patientSpaceGeometry",
        "medicalValidation",
        "automaticPromotionAllowed",
    ):
        _require(claims.get(key) is False, f"AS06 claim {key} must remain false")


def _find_competitor_set(track_graph: dict[str, Any]) -> dict[str, Any]:
    for competitor_set in track_graph.get("competitorSets", []):
        if competitor_set.get("id") == "vhf.m8v.competitors.branch-identity":
            return competitor_set
    raise RadialIdentityEvidenceError("TASK-V04 branch identity competitor set is missing")


def _candidate_audit(track_graph: dict[str, Any]) -> list[dict[str, Any]]:
    tracks = [
        track
        for track in track_graph.get("tracks", [])
        if track.get("trackClass") == "anonymous-branch-search"
    ]
    _require(tracks, "TASK-V04 contains no anonymous arterial branch-search tracks")
    tracks.sort(key=lambda track: str(track.get("id", "")))
    result: list[dict[str, Any]] = []
    for track in tracks:
        identity = track.get("identity", {})
        _require(
            identity.get("namedIdentityStatus") == "anonymous-unresolved",
            f"{track.get('id')} must remain anonymously identified",
        )
        result.append(
            {
                "trackId": track["id"],
                "sourceClassification": str(track["sourceClassification"]),
                "observationCount": int(track["observationCount"]),
                "spanFrameCount": int(track["spanFrameCount"]),
                "coverageFraction": float(track["coverageFraction"]),
                "gapLinkCount": int(track["gapLinkCount"]),
                "maxMissingFrameCount": int(track["maxMissingFrameCount"]),
                "namedIdentityStatus": "anonymous-unresolved",
                "reviewStatus": str(track["reviewStatus"]),
                "selectionStatus": "not-selected-competing-candidate",
            }
        )
    return result


def evaluate(
    registration: dict[str, Any],
    landmarks: dict[str, Any],
    track_graph: dict[str, Any],
    continuity: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    _validate_registration_scaffold(registration)
    _validate_landmark_graph(landmarks)
    _validate_track_graph(track_graph)
    _validate_same_subject_continuity(continuity)

    audit = _candidate_audit(track_graph)
    competitor_set = _find_competitor_set(track_graph)
    competitor_ids = list(competitor_set.get("trackIds", []))
    _require(set(competitor_ids) == {row["trackId"] for row in audit}, "branch competitor set must exactly cover audited anonymous tracks")

    unresolved_landmarks = set(landmarks.get("unresolvedRequiredLandmarks", []))
    required_radial_landmarks = {
        "structure.radial_styloid.left",
        "structure.brachioradialis.left",
        "structure.flexor_carpi_radialis.left",
        "structure.pronator_quadratus.left",
    }
    named_landmarks_missing = sorted(required_radial_landmarks & unresolved_landmarks)
    branch_candidates = list(track_graph.get("branchMergeCandidates", []))

    gates = [
        {
            "id": "unique-same-subject-arterial-anchor",
            "requirement": "A defensible same-subject proximal or otherwise unique arterial anchor for the radial path is required.",
            "status": "fail",
            "evidence": [
                "AS06 preserves a reviewed left ulnar-artery anchor.",
                "AS06 explicitly leaves radial, brachial, and bifurcation identity unresolved.",
            ],
            "reason": "The ulnar anchor is valuable competing anatomy but is not a unique radial or brachial anchor and cannot establish the radial path by itself.",
        },
        {
            "id": "bounded-gap-continuity-to-target",
            "requirement": "The radial identity must be followed by continuous or explicitly bounded-gap same-subject tracking to the target region.",
            "status": "insufficient",
            "evidence": [
                f"TASK-V04 contains {len(audit)} anonymous arterial branch-search tracks with direct observations and explicit gaps.",
                "None of those tracks is bound to structure.radial_artery.left.",
            ],
            "reason": "Track continuity exists as anonymous candidate evidence, but identity continuity from a unique radial anchor to the target cannot be demonstrated while no candidate is selected or named.",
        },
        {
            "id": "compatible-branch-topology",
            "requirement": "The candidate must have compatible radial/ulnar/brachial branch topology where topology is used as identity evidence.",
            "status": "fail",
            "evidence": [
                f"TASK-V04 has {len(branch_candidates)} branch/merge candidates meeting the carried-forward topology gate.",
                "TASK-V04 explicitly leaves brachial and bifurcation identity unestablished.",
            ],
            "reason": "No source-supported branch topology currently distinguishes one anonymous branch-search track as the radial artery.",
        },
        {
            "id": "compatible-landmark-relationships",
            "requirement": "The candidate must have compatible source-supported landmark relationships.",
            "status": "insufficient" if named_landmarks_missing else "pass",
            "evidence": [
                "TASK-V02 supports bounded same-subject radius/ulna correspondence for inspection, not vessel identity by itself.",
                (
                    "Unresolved radial-localizing landmarks: " + ", ".join(named_landmarks_missing)
                    if named_landmarks_missing
                    else "Required radial-localizing landmarks are no longer listed as unresolved."
                ),
            ],
            "reason": (
                "Radius/ulna orientation constrains the search, but the named local landmarks needed for a defensible radial relationship remain unresolved."
                if named_landmarks_missing
                else "Current landmark inputs no longer expose the named radial-localizing landmarks as unresolved."
            ),
        },
        {
            "id": "no-equal-or-better-competing-candidate",
            "requirement": "No competing candidate with equal or better evidence may remain unresolved.",
            "status": "fail" if len(competitor_ids) > 1 or competitor_set.get("resolutionStatus") != "resolved" else "pass",
            "evidence": [
                f"TASK-V04 branch identity competitor set contains {len(competitor_ids)} candidates.",
                f"Competitor-set resolution status is {competitor_set.get('resolutionStatus')}.",
            ],
            "reason": "Multiple anonymous arterial candidates remain explicitly competing; choosing one now would convert algorithmic preference into anatomical truth.",
        },
        {
            "id": "explicit-human-anatomical-review",
            "requirement": "The radial identity claim requires explicit human anatomical review.",
            "status": "fail",
            "evidence": [
                "TASK-V04 anonymous branch-search tracks are not reviewed as complete named tracks.",
                "No V05 human anatomical review receipt is present in the current evidence inputs.",
            ],
            "reason": "The required identity-level human review has not occurred; prior review of the ulnar anchor cannot be transferred to a radial candidate.",
        },
    ]

    blocking = [gate["id"] for gate in gates if gate["status"] != "pass"]
    all_pass = not blocking
    decision = {
        "state": "promotable" if all_pass else "blocked-unresolved",
        "allRequiredGatesPass": all_pass,
        "radialArteryPromotionAllowed": all_pass,
        "candidateSelected": None,
        "nextTask": "TASK-V06",
        "blockingGateIds": blocking,
    }
    claims = {
        "radialArteryIdentityEstablished": False,
        "brachialArteryIdentityEstablished": False,
        "bifurcationIdentityEstablished": False,
        "patientSpaceGeometry": False,
        "physical3DGeometry": False,
        "medicalValidation": False,
        "automaticPromotionAllowed": False,
    }
    return audit, gates, decision, claims


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registration", type=Path, required=True)
    parser.add_argument("--landmarks", type=Path, required=True)
    parser.add_argument("--track-graph", type=Path, required=True)
    parser.add_argument("--continuity", type=Path, required=True)
    parser.add_argument("--recorded-at", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    registration = _read_json(args.registration)
    landmarks = _read_json(args.landmarks)
    track_graph = _read_json(args.track_graph)
    continuity = _read_json(args.continuity)
    audit, gates, decision, claims = evaluate(
        registration, landmarks, track_graph, continuity
    )

    output = {
        "schema": "ph-m8v-radial-artery-identity-evidence.v1",
        "schemaVersion": "1",
        "task": "TASK-V05",
        "recordedAt": args.recorded_at,
        "status": "complete",
        "targetIdentity": "structure.radial_artery.left",
        "sourceEvidence": {
            "registrationScaffold": _source_ref(args.registration, registration),
            "landmarkGraph": _source_ref(args.landmarks, landmarks),
            "trackGraph": _source_ref(args.track_graph, track_graph),
            "sameSubjectContinuity": _source_ref(args.continuity, continuity),
        },
        "candidateAudit": audit,
        "promotionGateEvaluations": gates,
        "decision": decision,
        "claims": claims,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"candidateCount": len(audit), "decision": decision}, indent=2))


if __name__ == "__main__":
    main()
