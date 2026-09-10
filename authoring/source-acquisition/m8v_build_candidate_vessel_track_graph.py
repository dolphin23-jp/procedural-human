from __future__ import annotations

import argparse
from datetime import date
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any, Iterable


class TrackGraphError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TrackGraphError(f"{path} must contain a JSON object")
    return value


def _sha256_path(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise TrackGraphError(message)


def _require_false_claims(claims: dict[str, Any], keys: Iterable[str], *, source: str) -> None:
    for key in keys:
        _require(claims.get(key) is False, f"{source} claim {key} must remain false")


def _validate_landmark_graph(graph: dict[str, Any]) -> None:
    _require(graph.get("schema") == "ph-m8v-upper-extremity-landmark-graph.v1", "unexpected V03 landmark graph schema")
    _require(graph.get("task") == "TASK-V03", "landmark graph must come from TASK-V03")
    _require(graph.get("status") == "complete", "V03 landmark graph must be complete")
    _require(graph.get("coordinateSpace", {}).get("patientSpaceClaim") is False, "V03 must not claim Patient Space")
    _require(graph.get("decision", {}).get("usableForTaskV04") is True, "V03 does not authorize TASK-V04")
    _require_false_claims(
        graph.get("claims", {}),
        (
            "patientSpaceGeometry",
            "namedMuscleIdentityEstablished",
            "radialArteryIdentityEstablished",
            "superficialVeinIdentityEstablished",
            "medicalValidation",
            "automaticPromotionAllowed",
        ),
        source="V03",
    )


def _validate_phase1(phase1: dict[str, Any]) -> None:
    _require(phase1.get("schema") == "ph-as06-upper-extremity-continuity-recon.v1", "unexpected AS06 phase-1 schema")
    _require(phase1.get("task") == "TASK-AS06", "phase-1 report must be TASK-AS06")
    coordinate = phase1.get("coordinateSpace", {})
    _require(coordinate.get("kind") == "source-image-stack", "phase-1 must remain in source-image-stack coordinates")
    _require(coordinate.get("patientSpaceClaim") is False, "phase-1 must not claim Patient Space")
    _require(coordinate.get("physicalXyClaim") is False, "phase-1 must not claim physical XY geometry")
    _require_false_claims(
        phase1.get("claims", {}),
        (
            "automaticPromotionAllowed",
            "brachialArteryIdentityEstablished",
            "crossSubjectGeometryUsed",
            "ctRegistrationEstablished",
            "medicalValidation",
            "namedSuperficialVeinIdentityEstablished",
            "patientSpaceGeometry",
            "radialArteryIdentityEstablished",
        ),
        source="AS06 phase-1",
    )
    anchor = phase1.get("anchorLineage", {})
    _require(anchor.get("anatomicalId") == "structure.ulnar_artery.left", "phase-1 anchor must be the preserved left ulnar artery anchor")
    _require(anchor.get("completeVesselExtentClaim") is False, "ulnar anchor must not claim complete vessel extent")
    retro = phase1.get("ulnarArteryRetrogradeContinuity", {})
    _require(isinstance(retro.get("nodes"), list) and len(retro["nodes"]) >= 2, "phase-1 retrograde continuity nodes are required")
    _require(retro.get("claims", {}).get("identityBeyondObservedContinuityAutomaticallyEstablished") is False, "phase-1 cannot auto-extend named identity")
    bridge = phase1.get("ulnarBridgeSearch", {})
    _require(isinstance(bridge.get("observations"), list) and len(bridge["observations"]) >= 1, "phase-1 bridge observations are required")
    _require(bridge.get("sameSubjectContinuitySupportedToBoneTransition") is True, "phase-1 bridge must reach the bounded bone transition")
    _require(bridge.get("claims", {}).get("sameNamedVesselBeyondSourceContinuityClaim") is False, "phase-1 bridge cannot auto-extend named identity")
    readiness = phase1.get("nextSearchReadiness", {})
    _require(readiness.get("radialIdentityPromotionAuthorized") is False, "phase-1 must not authorize radial identity promotion")
    _require(readiness.get("superficialVeinIdentityPromotionAuthorized") is False, "phase-1 must not authorize superficial-vein identity promotion")


def _validate_phase2(phase2: dict[str, Any]) -> None:
    _require(phase2.get("schema") == "ph-as06-branch-superficial-recon.v1", "unexpected AS06 phase-2 schema")
    _require(phase2.get("task") == "TASK-AS06", "phase-2 report must be TASK-AS06")
    coordinate = phase2.get("coordinateSpace", {})
    _require(coordinate.get("kind") == "source-image-stack", "phase-2 must remain in source-image-stack coordinates")
    _require(coordinate.get("patientSpaceClaim") is False, "phase-2 must not claim Patient Space")
    _require_false_claims(
        phase2.get("claims", {}),
        (
            "automaticPromotionAllowed",
            "brachialArteryIdentityEstablished",
            "crossSubjectGeometryUsed",
            "ctRegistrationEstablished",
            "medicalValidation",
            "namedSuperficialVeinIdentityEstablished",
            "patientSpaceGeometry",
            "procedureRoleUsedAsAnatomicalIdentity",
            "radialArteryIdentityEstablished",
        ),
        source="AS06 phase-2",
    )
    arterial = phase2.get("arterialBranchTopologySearch", {})
    _require(arterial.get("knownUlnarContinuityUsedAsAnchor") is True, "phase-2 arterial search must retain the ulnar continuity anchor")
    _require(arterial.get("crossSubjectAtlasUsed") is False, "cross-subject atlas geometry must not enter the track graph")
    arterial_tracks = arterial.get("tracks")
    _require(isinstance(arterial_tracks, list) and len(arterial_tracks) >= 1, "phase-2 arterial anonymous tracks are required")
    _require(int(arterial.get("anonymousTrackCount", -1)) == len(arterial_tracks), "phase-2 arterial track count mismatch")
    venous = phase2.get("superficialVenousSearch", {})
    _require(venous.get("namedVeinAtlasUsed") is False, "named-vein atlas must not define same-subject superficial tracks")
    _require(venous.get("procedureRoleUsedAsIdentity") is False, "procedure role must not define superficial vessel identity")
    superficial_tracks = venous.get("tracks")
    _require(isinstance(superficial_tracks, list) and len(superficial_tracks) >= 1, "phase-2 superficial anonymous tracks are required")
    _require(int(venous.get("anonymousTrackCount", -1)) == len(superficial_tracks), "phase-2 superficial track count mismatch")


def _finite_number(value: Any, *, field: str) -> float:
    _require(isinstance(value, (int, float)) and not isinstance(value, bool), f"{field} must be numeric")
    result = float(value)
    _require(math.isfinite(result), f"{field} must be finite")
    return result


def _normalize_observation(track_id: str, ordinal: int, row: dict[str, Any], *, default_evidence_kind: str) -> dict[str, Any]:
    _require(isinstance(row, dict), "track observations must be objects")
    frame = row.get("wholeBodyFrameIndex")
    _require(isinstance(frame, int) and not isinstance(frame, bool) and frame >= 0, "wholeBodyFrameIndex must be a non-negative integer")
    result: dict[str, Any] = {
        "id": f"{track_id}.obs.{ordinal:04d}",
        "wholeBodyFrameIndex": frame,
        "xFullImagePixels": _finite_number(row.get("xFullImagePixels"), field="xFullImagePixels"),
        "yFullImagePixels": _finite_number(row.get("yFullImagePixels"), field="yFullImagePixels"),
        "evidenceKind": str(row.get("evidenceKind") or default_evidence_kind),
        "directSourceObservation": True,
    }
    source_filename = row.get("sourceFilename")
    if source_filename is not None:
        _require(isinstance(source_filename, str) and source_filename, "sourceFilename must be a non-empty string")
        result["sourceFilename"] = source_filename
    if "areaPixels" in row:
        area = row["areaPixels"]
        _require(isinstance(area, int) and not isinstance(area, bool) and area >= 1, "areaPixels must be a positive integer")
        result["areaPixels"] = area
    if "circularity" in row:
        result["circularity"] = _finite_number(row["circularity"], field="circularity")
        _require(result["circularity"] >= 0, "circularity must be non-negative")
    if "contrast" in row:
        result["contrast"] = _finite_number(row["contrast"], field="contrast")
    if "depthPixels" in row:
        depth = row["depthPixels"]
        if depth is None:
            result["depthPixels"] = None
        else:
            result["depthPixels"] = _finite_number(depth, field="depthPixels")
            _require(result["depthPixels"] >= 0, "depthPixels must be non-negative")
    return result


def _normalize_track(
    track_id: str,
    raw_rows: list[dict[str, Any]],
    *,
    track_class: str,
    search_context: str,
    source_classification: str,
    identity: dict[str, Any],
    default_evidence_kind: str,
) -> dict[str, Any]:
    _require(len(raw_rows) >= 2, f"{track_id} must contain at least two observations")
    observations = [
        _normalize_observation(track_id, index, row, default_evidence_kind=default_evidence_kind)
        for index, row in enumerate(raw_rows, start=1)
    ]
    frames = [int(row["wholeBodyFrameIndex"]) for row in observations]
    deltas = [b - a for a, b in zip(frames, frames[1:])]
    _require(all(delta != 0 for delta in deltas), f"{track_id} contains duplicate consecutive frame indices")
    increasing = all(delta > 0 for delta in deltas)
    decreasing = all(delta < 0 for delta in deltas)
    _require(increasing or decreasing, f"{track_id} frame ordering must be strictly monotonic")

    links: list[dict[str, Any]] = []
    for ordinal, (left, right) in enumerate(zip(observations, observations[1:]), start=1):
        frame_delta = abs(int(right["wholeBodyFrameIndex"]) - int(left["wholeBodyFrameIndex"]))
        missing = frame_delta - 1
        links.append(
            {
                "id": f"{track_id}.link.{ordinal:04d}",
                "fromObservationId": left["id"],
                "toObservationId": right["id"],
                "kind": "direct-continuation" if missing == 0 else "explicit-gap",
                "frameDelta": frame_delta,
                "missingFrameCount": missing,
                "interpolatedObservationCount": 0,
            }
        )

    minimum = min(frames)
    maximum = max(frames)
    span = maximum - minimum + 1
    gap_links = [link for link in links if link["kind"] == "explicit-gap"]
    max_missing = max((int(link["missingFrameCount"]) for link in links), default=0)
    return {
        "id": track_id,
        "trackClass": track_class,
        "searchContext": search_context,
        "sourceClassification": source_classification,
        "identity": identity,
        "reviewStatus": "unreviewed-as-complete-track",
        "ordering": "increasing-frame-index" if increasing else "decreasing-frame-index",
        "observationCount": len(observations),
        "spanFrameCount": span,
        "coverageFraction": len(observations) / span,
        "minWholeBodyFrameIndex": minimum,
        "maxWholeBodyFrameIndex": maximum,
        "gapLinkCount": len(gap_links),
        "maxMissingFrameCount": max_missing,
        "observations": observations,
        "links": links,
    }


def _build_ulnar_track(phase1: dict[str, Any]) -> dict[str, Any]:
    retro = phase1["ulnarArteryRetrogradeContinuity"]
    bridge = phase1["ulnarBridgeSearch"]
    rows = list(retro["nodes"]) + list(bridge["observations"])
    return _normalize_track(
        "vhf.m8v.ulnar-anchor-linked.01",
        rows,
        track_class="ulnar-anchor-linked-continuity",
        search_context="preserved-reviewed-ulnar-anchor-plus-same-subject-retrograde-and-bridge-continuity",
        source_classification="reviewed-anchor-linked-bounded-source-continuity",
        identity={
            "anchorAnatomicalId": "structure.ulnar_artery.left",
            "namedIdentityStatus": "reviewed-anchor-linked-continuity",
            "namedIdentityAppliesToEntireTrack": False,
            "vesselClassStatus": "anchor-linked-arterial-candidate",
        },
        default_evidence_kind="same-subject-ulnar-anchor-linked-source-observation",
    )


def _build_anonymous_tracks(phase2: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    arterial_tracks: list[dict[str, Any]] = []
    branch_candidates: list[dict[str, Any]] = []
    for raw in phase2["arterialBranchTopologySearch"]["tracks"]:
        rank = int(raw["rank"])
        track_id = f"vhf.m8v.branch-anonymous.{rank:02d}"
        classification = str(raw["branchTopologyClassification"])
        track = _normalize_track(
            track_id,
            list(raw["nodes"]),
            track_class="anonymous-branch-search",
            search_context="same-subject-arterial-branch-topology-search-near-ulnar-continuity",
            source_classification=classification,
            identity={
                "anchorAnatomicalId": None,
                "namedIdentityStatus": "anonymous-unresolved",
                "namedIdentityAppliesToEntireTrack": False,
                "vesselClassStatus": "vessel-like-unknown",
            },
            default_evidence_kind="same-subject-anonymous-branch-search-observation",
        )
        _require(track["observationCount"] == int(raw["nodeCount"]), f"{track_id} node count mismatch")
        _require(track["spanFrameCount"] == int(raw["spanFrameCount"]), f"{track_id} span mismatch")
        arterial_tracks.append(track)
        if classification == "distinct-distal-track-with-proximal-convergence-candidate":
            branch_candidates.append(
                {
                    "id": f"vhf.m8v.branch-candidate.{rank:02d}",
                    "kind": "branch-candidate",
                    "anchorTrackId": "vhf.m8v.ulnar-anchor-linked.01",
                    "candidateTrackId": track_id,
                    "status": "candidate-unreviewed",
                    "identityImplicationAllowed": False,
                }
            )

    superficial_tracks: list[dict[str, Any]] = []
    for raw in phase2["superficialVenousSearch"]["tracks"]:
        rank = int(raw["rank"])
        track_id = f"vhf.m8v.superficial-anonymous.{rank:02d}"
        track = _normalize_track(
            track_id,
            list(raw["nodes"]),
            track_class="anonymous-superficial-search",
            search_context="same-subject-superficial-vessel-search-without-named-vein-prior",
            source_classification=str(raw["classification"]),
            identity={
                "anchorAnatomicalId": None,
                "namedIdentityStatus": "anonymous-unresolved",
                "namedIdentityAppliesToEntireTrack": False,
                "vesselClassStatus": "superficial-vessel-like-unknown",
            },
            default_evidence_kind="same-subject-anonymous-superficial-search-observation",
        )
        _require(track["observationCount"] == int(raw["nodeCount"]), f"{track_id} node count mismatch")
        _require(track["spanFrameCount"] == int(raw["spanFrameCount"]), f"{track_id} span mismatch")
        superficial_tracks.append(track)
    return arterial_tracks, superficial_tracks, branch_candidates


def build_track_graph(
    phase1: dict[str, Any],
    phase2: dict[str, Any],
    landmark_graph: dict[str, Any],
    *,
    artifact_id: int,
    artifact_sha256: str,
    phase1_filename: str,
    phase1_sha256: str,
    phase2_filename: str,
    phase2_sha256: str,
    landmark_graph_path: str,
    recorded_at: str,
) -> dict[str, Any]:
    _validate_landmark_graph(landmark_graph)
    _validate_phase1(phase1)
    _validate_phase2(phase2)
    _require(artifact_id > 0, "artifact id must be positive")
    _require(len(artifact_sha256) == 64 and all(ch in "0123456789abcdef" for ch in artifact_sha256), "artifact SHA-256 must be lowercase hexadecimal")
    for digest, label in ((phase1_sha256, "phase1"), (phase2_sha256, "phase2")):
        _require(len(digest) == 64 and all(ch in "0123456789abcdef" for ch in digest), f"{label} SHA-256 must be lowercase hexadecimal")

    ulnar = _build_ulnar_track(phase1)
    arterial, superficial, branch_candidates = _build_anonymous_tracks(phase2)
    tracks = [ulnar, *arterial, *superficial]
    ids = [str(track["id"]) for track in tracks]
    _require(len(ids) == len(set(ids)), "track ids must be unique")

    arterial_ids = [str(track["id"]) for track in arterial]
    superficial_ids = [str(track["id"]) for track in superficial]
    competitor_sets = [
        {
            "id": "vhf.m8v.competitors.branch-identity",
            "competingClaim": "radial-brachial-or-bifurcation-identity-among-anonymous-branch-search-tracks",
            "trackIds": arterial_ids,
            "resolutionStatus": "unresolved",
        },
        {
            "id": "vhf.m8v.competitors.superficial-structure",
            "competingClaim": "procedure-relevant-same-subject-superficial-vessel-structure-among-anonymous-tracks",
            "trackIds": superficial_ids,
            "resolutionStatus": "unresolved",
        },
    ]

    all_links = [link for track in tracks for link in track["links"]]
    return {
        "schema": "ph-m8v-candidate-vessel-track-graph.v1",
        "schemaVersion": "1",
        "task": "TASK-V04",
        "recordedAt": recorded_at,
        "status": "complete",
        "coordinateSpace": {
            "kind": "source-image-stack-index-3d",
            "patientSpaceClaim": False,
            "physicalXyClaim": False,
            "physicalZClaim": False,
            "axisSemantics": {
                "x": "full-image-pixels",
                "y": "full-image-pixels",
                "z": "whole-body-frame-index-discrete",
            },
        },
        "sourceEvidence": {
            "as06Artifact": {
                "artifactId": artifact_id,
                "archiveSha256": f"sha256:{artifact_sha256}",
                "expiredAtBuildTime": False,
            },
            "phase1Report": {
                "filename": phase1_filename,
                "sha256": phase1_sha256,
                "schema": str(phase1["schema"]),
            },
            "phase2Report": {
                "filename": phase2_filename,
                "sha256": phase2_sha256,
                "schema": str(phase2["schema"]),
            },
        },
        "landmarkGraph": {
            "path": landmark_graph_path,
            "schema": str(landmark_graph["schema"]),
            "usableForTaskV04": True,
        },
        "tracks": tracks,
        "competitorSets": competitor_sets,
        "branchMergeCandidates": branch_candidates,
        "gapSummary": {
            "trackCount": len(tracks),
            "observationCount": sum(int(track["observationCount"]) for track in tracks),
            "linkCount": len(all_links),
            "explicitGapLinkCount": sum(link["kind"] == "explicit-gap" for link in all_links),
            "maxMissingFrameCount": max((int(link["missingFrameCount"]) for link in all_links), default=0),
        },
        "decision": {
            "graphState": "source-index-track-graph-established",
            "taskV05InputAvailable": True,
            "taskV06InputAvailable": True,
            "radialIdentityStillRequiresEvaluation": True,
            "superficialVeinStillRequiresEvaluation": True,
            "nextTask": "TASK-V05",
        },
        "claims": {
            "sourceIndex3DTrackGraphEstablished": True,
            "physical3DGeometry": False,
            "patientSpaceGeometry": False,
            "radialArteryIdentityEstablished": False,
            "brachialArteryIdentityEstablished": False,
            "bifurcationIdentityEstablished": False,
            "superficialVeinClassEstablished": False,
            "namedSuperficialVeinIdentityEstablished": False,
            "procedureRoleEstablished": False,
            "medicalValidation": False,
            "automaticPromotionAllowed": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase1", type=Path, required=True)
    parser.add_argument("--phase2", type=Path, required=True)
    parser.add_argument("--landmark-graph", type=Path, required=True)
    parser.add_argument("--artifact-id", type=int, required=True)
    parser.add_argument("--artifact-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--recorded-at", default=date.today().isoformat())
    args = parser.parse_args()

    phase1 = _read_json(args.phase1)
    phase2 = _read_json(args.phase2)
    landmark_graph = _read_json(args.landmark_graph)
    record = build_track_graph(
        phase1,
        phase2,
        landmark_graph,
        artifact_id=args.artifact_id,
        artifact_sha256=args.artifact_sha256.removeprefix("sha256:"),
        phase1_filename=args.phase1.name,
        phase1_sha256=_sha256_path(args.phase1),
        phase2_filename=args.phase2.name,
        phase2_sha256=_sha256_path(args.phase2),
        landmark_graph_path=str(args.landmark_graph),
        recorded_at=args.recorded_at,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "trackCount": record["gapSummary"]["trackCount"],
                "observationCount": record["gapSummary"]["observationCount"],
                "explicitGapLinkCount": record["gapSummary"]["explicitGapLinkCount"],
                "branchMergeCandidateCount": len(record["branchMergeCandidates"]),
                "nextTask": record["decision"]["nextTask"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
