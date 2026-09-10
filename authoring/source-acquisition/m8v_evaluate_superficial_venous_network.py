from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
from statistics import median
from typing import Any


class SuperficialNetworkEvidenceError(RuntimeError):
    pass


MAX_FRAME_DELTA = 4
MAX_JUMP_PER_FRAME_PIXELS = 7.0
JUMP_SLACK_PIXELS = 3.0
PROCEDURE_RELEVANT_MINIMUM_SPAN_FRAMES = 90


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SuperficialNetworkEvidenceError(f"{path} must contain a JSON object")
    return value


def _sha256_path(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SuperficialNetworkEvidenceError(message)


def _source_ref(path: Path, data: dict[str, Any]) -> dict[str, str]:
    schema = data.get("schema")
    _require(isinstance(schema, str) and schema, f"{path} must declare schema")
    return {
        "path": str(path).replace("\\", "/"),
        "sha256": _sha256_path(path),
        "schema": schema,
    }


def _validate_track_graph(data: dict[str, Any]) -> None:
    _require(
        data.get("schema") == "ph-m8v-candidate-vessel-track-graph.v1",
        "unexpected TASK-V04 schema",
    )
    _require(data.get("task") == "TASK-V04", "track graph must be TASK-V04")
    _require(data.get("status") == "complete", "TASK-V04 must be complete")
    _require(
        data.get("decision", {}).get("taskV06InputAvailable") is True,
        "TASK-V04 does not authorize TASK-V06",
    )
    claims = data.get("claims", {})
    _require(
        claims.get("sourceIndex3DTrackGraphEstablished") is True,
        "TASK-V04 source-index graph is required",
    )
    for key in (
        "physical3DGeometry",
        "patientSpaceGeometry",
        "superficialVeinClassEstablished",
        "namedSuperficialVeinIdentityEstablished",
        "procedureRoleEstablished",
        "medicalValidation",
        "automaticPromotionAllowed",
    ):
        _require(claims.get(key) is False, f"TASK-V04 claim {key} must remain false")


def _validate_landmark_graph(data: dict[str, Any]) -> None:
    _require(
        data.get("schema") == "ph-m8v-upper-extremity-landmark-graph.v1",
        "unexpected TASK-V03 schema",
    )
    _require(data.get("task") == "TASK-V03", "landmark graph must be TASK-V03")
    _require(data.get("status") == "complete", "TASK-V03 must be complete")
    claims = data.get("claims", {})
    for key in (
        "patientSpaceGeometry",
        "superficialVeinIdentityEstablished",
        "medicalValidation",
        "automaticPromotionAllowed",
    ):
        _require(claims.get(key) is False, f"TASK-V03 claim {key} must remain false")


def _validate_continuity(data: dict[str, Any]) -> None:
    _require(
        data.get("schema") == "ph-as06-same-subject-continuity-provenance.v1",
        "unexpected AS06 continuity schema",
    )
    _require(data.get("task") == "TASK-AS06", "continuity provenance must be TASK-AS06")
    superficial = data.get("phase2", {}).get("superficialVenousSearch", {})
    _require(
        superficial.get("anonymousTrackCount") == 8,
        "AS06 superficial anonymous track count must remain 8 for this evidence record",
    )
    _require(
        superficial.get("continuousAnonymousCandidateCount") == 0,
        "AS06 unexpectedly reports a promoted continuous superficial candidate",
    )
    claims = data.get("claims", {})
    _require(
        claims.get("namedSuperficialVeinIdentityEstablished") is False,
        "AS06 cannot pre-establish named superficial vein identity",
    )
    _require(
        claims.get("automaticPromotionAllowed") is False,
        "AS06 cannot authorize automatic promotion",
    )


def _superficial_tracks(track_graph: dict[str, Any]) -> list[dict[str, Any]]:
    tracks = [
        track
        for track in track_graph.get("tracks", [])
        if track.get("trackClass") == "anonymous-superficial-search"
    ]
    _require(tracks, "TASK-V04 contains no anonymous superficial tracks")
    competitor_set = next(
        (
            item
            for item in track_graph.get("competitorSets", [])
            if item.get("id") == "vhf.m8v.competitors.superficial-structure"
        ),
        None,
    )
    _require(competitor_set is not None, "TASK-V04 superficial competitor set is missing")
    ids = {str(track["id"]) for track in tracks}
    _require(
        ids == set(competitor_set.get("trackIds", [])),
        "superficial competitor set must exactly cover anonymous superficial tracks",
    )
    return sorted(tracks, key=lambda track: str(track["id"]))


def _mean_jump_per_frame(track: dict[str, Any]) -> float:
    observations = track.get("observations", [])
    if len(observations) < 2:
        return math.inf
    values: list[float] = []
    for left, right in zip(observations, observations[1:]):
        frame_delta = abs(
            int(right["wholeBodyFrameIndex"]) - int(left["wholeBodyFrameIndex"])
        )
        _require(frame_delta >= 1, f"{track['id']} contains duplicate observation frames")
        distance = math.hypot(
            float(right["xFullImagePixels"]) - float(left["xFullImagePixels"]),
            float(right["yFullImagePixels"]) - float(left["yFullImagePixels"]),
        )
        values.append(distance / frame_delta)
    return sum(values) / len(values)


def _median_metric(track: dict[str, Any], key: str) -> float | None:
    values = [
        float(observation[key])
        for observation in track.get("observations", [])
        if observation.get(key) is not None
    ]
    return median(values) if values else None


def _audit_track(track: dict[str, Any]) -> dict[str, Any]:
    identity = track.get("identity", {})
    _require(
        identity.get("namedIdentityStatus") == "anonymous-unresolved",
        f"{track.get('id')} must remain anonymously identified",
    )
    _require(
        identity.get("vesselClassStatus") == "superficial-vessel-like-unknown",
        f"{track.get('id')} must not arrive with vein class pre-established",
    )
    span = int(track["spanFrameCount"])
    coverage = float(track["coverageFraction"])
    max_missing = int(track["maxMissingFrameCount"])
    circularity = _median_metric(track, "circularity")
    contrast = _median_metric(track, "contrast")
    depth = _median_metric(track, "depthPixels")
    mean_jump = _mean_jump_per_frame(track)

    direct_extent = span >= PROCEDURE_RELEVANT_MINIMUM_SPAN_FRAMES
    continuity = (
        direct_extent
        and coverage >= 0.78
        and max_missing <= 3
        and circularity is not None
        and circularity >= 0.38
        and contrast is not None
        and contrast >= 18.0
        and mean_jump <= 4.5
        and depth is not None
        and 4.0 <= depth <= 30.0
    )
    return {
        "trackId": str(track["id"]),
        "sourceClassification": str(track["sourceClassification"]),
        "observationCount": int(track["observationCount"]),
        "spanFrameCount": span,
        "coverageFraction": coverage,
        "maxMissingFrameCount": max_missing,
        "medianDepthPixels": depth,
        "directProcedureRelevantExtent": direct_extent,
        "meetsDirectContinuityCriteria": continuity,
        "vesselClassStatus": str(identity["vesselClassStatus"]),
        "namedIdentityStatus": "anonymous-unresolved",
        "reviewStatus": str(track["reviewStatus"]),
    }


def _endpoint(track: dict[str, Any], *, last: bool) -> dict[str, Any]:
    observations = list(track.get("observations", []))
    _require(observations, f"{track.get('id')} has no observations")
    return max(observations, key=lambda row: int(row["wholeBodyFrameIndex"])) if last else min(
        observations, key=lambda row: int(row["wholeBodyFrameIndex"])
    )


def _continuation_hypotheses(tracks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hypotheses: list[dict[str, Any]] = []
    ordinal = 1
    for left_index, first in enumerate(tracks):
        for second in tracks[left_index + 1 :]:
            first_min = int(first["minWholeBodyFrameIndex"])
            first_max = int(first["maxWholeBodyFrameIndex"])
            second_min = int(second["minWholeBodyFrameIndex"])
            second_max = int(second["maxWholeBodyFrameIndex"])
            if first_max < second_min:
                earlier, later = first, second
            elif second_max < first_min:
                earlier, later = second, first
            else:
                continue

            from_observation = _endpoint(earlier, last=True)
            to_observation = _endpoint(later, last=False)
            frame_delta = int(to_observation["wholeBodyFrameIndex"]) - int(
                from_observation["wholeBodyFrameIndex"]
            )
            if not 1 <= frame_delta <= MAX_FRAME_DELTA:
                continue
            distance = math.hypot(
                float(to_observation["xFullImagePixels"])
                - float(from_observation["xFullImagePixels"]),
                float(to_observation["yFullImagePixels"])
                - float(from_observation["yFullImagePixels"]),
            )
            if distance > MAX_JUMP_PER_FRAME_PIXELS * frame_delta + JUMP_SLACK_PIXELS:
                continue
            hypotheses.append(
                {
                    "id": f"vhf.m8v.superficial-continuation-hypothesis.{ordinal:02d}",
                    "fromTrackId": str(earlier["id"]),
                    "toTrackId": str(later["id"]),
                    "frameDelta": frame_delta,
                    "missingFrameCount": frame_delta - 1,
                    "endpointDistancePixels": distance,
                    "status": "derived-continuation-hypothesis-only",
                    "directContinuityClaim": False,
                    "identityImplicationAllowed": False,
                }
            )
            ordinal += 1
    return hypotheses


def evaluate(
    track_graph: dict[str, Any],
    landmarks: dict[str, Any],
    continuity: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    _validate_track_graph(track_graph)
    _validate_landmark_graph(landmarks)
    _validate_continuity(continuity)

    tracks = _superficial_tracks(track_graph)
    audit = [_audit_track(track) for track in tracks]
    hypotheses = _continuation_hypotheses(tracks)
    competitor_set = next(
        item
        for item in track_graph["competitorSets"]
        if item["id"] == "vhf.m8v.competitors.superficial-structure"
    )

    direct_relevant = sum(row["directProcedureRelevantExtent"] for row in audit)
    direct_continuous = sum(row["meetsDirectContinuityCriteria"] for row in audit)
    depth_supported = sum(
        row["medianDepthPixels"] is not None
        and 4.0 <= float(row["medianDepthPixels"]) <= 30.0
        for row in audit
    )
    vein_supported = sum(row["vesselClassStatus"] == "superficial-vein" for row in audit)
    summary = {
        "anonymousTrackCount": len(audit),
        "directProcedureRelevantTrackCount": direct_relevant,
        "directContinuousCandidateCount": direct_continuous,
        "hypothesisLinkCount": len(hypotheses),
        "maxDirectSpanFrames": max(row["spanFrameCount"] for row in audit),
        "superficialDepthSupportedTrackCount": depth_supported,
        "veinClassSupportedTrackCount": vein_supported,
        "competitorResolutionStatus": str(competitor_set["resolutionStatus"]),
    }

    gates = [
        {
            "id": "direct-observation-over-procedure-relevant-extent",
            "requirement": "Direct same-subject vessel observations must cover a procedure-relevant extent.",
            "status": "pass" if direct_relevant else "fail",
            "evidence": [
                f"The longest direct superficial track spans {summary['maxDirectSpanFrames']} frames.",
                f"{direct_relevant} track(s) meet the inherited {PROCEDURE_RELEVANT_MINIMUM_SPAN_FRAMES}-frame minimum extent.",
            ],
            "reason": (
                "At least one direct track reaches the inherited procedure-relevant extent."
                if direct_relevant
                else "No direct superficial track reaches the predeclared AS06 procedure-relevant extent; derived link hypotheses cannot fill that gap."
            ),
        },
        {
            "id": "single-structure-continuity",
            "requirement": "Continuity must establish one observed superficial structure rather than isolated blobs or derived links.",
            "status": "pass" if direct_continuous else "fail",
            "evidence": [
                f"{direct_continuous} track(s) meet the unchanged AS06 direct continuity criteria.",
                f"{len(hypotheses)} inter-track continuation hypothesis link(s) were found, but they are explicitly non-observational.",
            ],
            "reason": (
                "A direct track satisfies the existing continuity criteria."
                if direct_continuous
                else "The observed tracks remain fragmented; hypothesis links are inspection cues only and are not counted as source continuity."
            ),
        },
        {
            "id": "superficial-subcutaneous-relationship",
            "requirement": "The structure must have a defensible source-supported superficial/subcutaneous relationship.",
            "status": "insufficient",
            "evidence": [
                f"{depth_supported} of {len(audit)} tracks have median source-derived boundary depth within the inherited 4-30 pixel superficial window.",
                "TASK-V03 tissue-region evidence remains V0/unvalidated and does not establish a reviewed subcutaneous anatomical relationship.",
            ],
            "reason": "Shallow source-image depth is useful supporting evidence, but it is not yet equivalent to an anatomically reviewed subcutaneous-plane relationship.",
        },
        {
            "id": "vein-class-evidence",
            "requirement": "The observed structure must have defensible vessel-class evidence as a vein.",
            "status": "pass" if vein_supported else "fail",
            "evidence": [
                f"{vein_supported} of {len(audit)} tracks currently carry vein-specific class support.",
                "TASK-V04 intentionally labels the superficial tracks as superficial-vessel-like-unknown.",
            ],
            "reason": (
                "At least one track has explicit vein-class support."
                if vein_supported
                else "Static superficial vessel-like appearance and shallow depth do not by themselves distinguish a vein from another vascular or nonvascular lumen-like structure."
            ),
        },
        {
            "id": "competing-track-conflict-review",
            "requirement": "Competing tracks and conflicts must be resolved for the proposed observed structure.",
            "status": "pass" if competitor_set["resolutionStatus"] == "resolved" else "fail",
            "evidence": [
                f"The superficial competitor set contains {len(audit)} anonymous tracks.",
                f"Its resolution status is {competitor_set['resolutionStatus']}.",
            ],
            "reason": "No single observed superficial structure can be promoted while the candidate set remains explicitly unresolved.",
        },
        {
            "id": "explicit-human-anatomical-review",
            "requirement": "The observed structure, vessel class, and superficial relationship require explicit human anatomical review.",
            "status": "fail",
            "evidence": [
                "TASK-V04 tracks remain unreviewed as complete tracks.",
                "No TASK-V06 human review receipt is present in the current inputs.",
            ],
            "reason": "Algorithmic source evidence can prioritize review but cannot substitute for the required anatomy-level human review.",
        },
    ]

    blocking = [gate["id"] for gate in gates if gate["status"] != "pass"]
    observed_structure = not blocking
    decision = {
        "state": "promotable-observed-structure" if observed_structure else "blocked-unresolved",
        "observedSuperficialVeinStructureEstablished": observed_structure,
        "namedSuperficialVeinIdentityEstablished": False,
        "candidateSelected": None,
        "nextTask": "TASK-V07",
        "blockingGateIds": blocking,
    }
    claims = {
        "sameSubjectSuperficialNetworkEvidenceAssessed": True,
        "superficialVeinClassEstablished": vein_supported > 0,
        "observedSuperficialVeinStructureEstablished": observed_structure,
        "namedSuperficialVeinIdentityEstablished": False,
        "procedureRoleEstablished": False,
        "patientSpaceGeometry": False,
        "physical3DGeometry": False,
        "medicalValidation": False,
        "automaticPromotionAllowed": False,
    }
    return audit, hypotheses, summary, gates, decision, claims


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--track-graph", type=Path, required=True)
    parser.add_argument("--landmarks", type=Path, required=True)
    parser.add_argument("--continuity", type=Path, required=True)
    parser.add_argument("--recorded-at", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    track_graph = _read_json(args.track_graph)
    landmarks = _read_json(args.landmarks)
    continuity = _read_json(args.continuity)
    audit, hypotheses, summary, gates, decision, claims = evaluate(
        track_graph, landmarks, continuity
    )
    output = {
        "schema": "ph-m8v-superficial-venous-network-evidence.v1",
        "schemaVersion": "1",
        "task": "TASK-V06",
        "recordedAt": args.recorded_at,
        "status": "complete",
        "sourceEvidence": {
            "trackGraph": _source_ref(args.track_graph, track_graph),
            "landmarkGraph": _source_ref(args.landmarks, landmarks),
            "sameSubjectContinuity": _source_ref(args.continuity, continuity),
        },
        "continuityPolicy": {
            "origin": "TASK-AS06-fixed-superficial-search-criteria",
            "maxFrameDelta": MAX_FRAME_DELTA,
            "maxJumpPerFramePixels": MAX_JUMP_PER_FRAME_PIXELS,
            "jumpSlackPixels": JUMP_SLACK_PIXELS,
            "procedureRelevantMinimumSpanFrames": PROCEDURE_RELEVANT_MINIMUM_SPAN_FRAMES,
            "hypothesesCountAsDirectObservation": False,
        },
        "trackAudit": audit,
        "continuationHypotheses": hypotheses,
        "networkSummary": summary,
        "promotionGateEvaluations": gates,
        "decision": decision,
        "claims": claims,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"networkSummary": summary, "decision": decision}, indent=2))


if __name__ == "__main__":
    main()
