"""TASK-AS06 phase 2: branch-topology and superficial-vessel reconnaissance.

Consumes the phase-1 same-subject continuity report and verified VHF cryosection
archive. Candidate tracks remain anonymous unless topology and review justify a
name. No procedure role or cross-subject atlas is used as anatomical identity.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from math import hypot, log, pi
from pathlib import Path

import cv2
import numpy as np

import as06_upper_extremity_recon as recon


@dataclass(frozen=True)
class AnonymousCandidate:
    x: float
    y: float
    area: int
    circularity: float
    contrast: float
    depth: float | None = None


def candidate_score(candidate: AnonymousCandidate) -> float:
    area_penalty = max(0.0, (candidate.area - 220) / 180.0)
    return (
        1.0
        + 0.045 * min(candidate.contrast, 85.0)
        + 0.75 * min(candidate.circularity, 1.2)
        - 0.25 * area_penalty
    )


def build_tracks(
    frame_indices: list[int],
    candidates_by_frame: list[list[AnonymousCandidate]],
    *,
    max_gap: int,
    max_jump_per_frame: float,
    repeat: int,
) -> list[dict[str, object]]:
    banned: set[tuple[int, int]] = set()
    results: list[dict[str, object]] = []

    for rank in range(1, repeat + 1):
        states: dict[
            tuple[int, int],
            tuple[float, tuple[int, int] | None],
        ] = {}
        best_end: tuple[int, int] | None = None

        for local_frame, candidates in enumerate(candidates_by_frame):
            for candidate_index, candidate in enumerate(candidates):
                if (local_frame, candidate_index) in banned:
                    continue
                best_score = candidate_score(candidate)
                predecessor: tuple[int, int] | None = None

                for gap in range(1, max_gap + 1):
                    previous_frame = local_frame - gap
                    if previous_frame < 0:
                        continue
                    for previous_index, previous in enumerate(
                        candidates_by_frame[previous_frame]
                    ):
                        if (previous_frame, previous_index) in banned:
                            continue
                        state = states.get((previous_frame, previous_index))
                        if state is None:
                            continue
                        jump = hypot(candidate.x - previous.x, candidate.y - previous.y)
                        if jump > max_jump_per_frame * gap + 3.0:
                            continue
                        area_change = abs(log((candidate.area + 1) / (previous.area + 1)))
                        score = (
                            state[0]
                            + candidate_score(candidate)
                            - 0.11 * jump
                            - 0.35 * area_change
                            - 0.65 * (gap - 1)
                        )
                        if score > best_score:
                            best_score = score
                            predecessor = (previous_frame, previous_index)

                states[(local_frame, candidate_index)] = (best_score, predecessor)
                if best_end is None or best_score > states[best_end][0]:
                    best_end = (local_frame, candidate_index)

        if best_end is None:
            break

        path: list[tuple[int, int]] = []
        current: tuple[int, int] | None = best_end
        while current is not None:
            path.append(current)
            current = states[current][1]
        path.reverse()
        if not path:
            break

        nodes = [
            {
                "wholeBodyFrameIndex": frame_indices[local_frame],
                "xFullImagePixels": candidates_by_frame[local_frame][candidate_index].x,
                "yFullImagePixels": candidates_by_frame[local_frame][candidate_index].y,
                "areaPixels": candidates_by_frame[local_frame][candidate_index].area,
                "circularity": candidates_by_frame[local_frame][candidate_index].circularity,
                "contrast": candidates_by_frame[local_frame][candidate_index].contrast,
                "depthPixels": candidates_by_frame[local_frame][candidate_index].depth,
            }
            for local_frame, candidate_index in path
        ]
        indices = np.asarray([row["wholeBodyFrameIndex"] for row in nodes], dtype=int)
        points = np.asarray(
            [[row["xFullImagePixels"], row["yFullImagePixels"]] for row in nodes],
            dtype=float,
        )
        gaps = np.diff(indices)
        jumps = np.linalg.norm(np.diff(points, axis=0), axis=1) if len(points) > 1 else np.asarray([])
        per_frame = jumps / gaps if len(gaps) else np.asarray([])
        span = int(indices[-1] - indices[0] + 1)
        result = {
            "rank": rank,
            "nodeCount": len(nodes),
            "spanFrameCount": span,
            "coverageFraction": len(nodes) / span,
            "firstWholeBodyFrameIndex": int(indices[0]),
            "lastWholeBodyFrameIndex": int(indices[-1]),
            "maxGapFrames": int(gaps.max()) if len(gaps) else 0,
            "meanJumpPerFramePixels": float(per_frame.mean()) if len(per_frame) else 0.0,
            "maxJumpPerFramePixels": float(per_frame.max()) if len(per_frame) else 0.0,
            "medianAreaPixels": float(np.median([row["areaPixels"] for row in nodes])),
            "medianCircularity": float(np.median([row["circularity"] for row in nodes])),
            "p25Circularity": float(np.quantile([row["circularity"] for row in nodes], 0.25)),
            "medianContrast": float(np.median([row["contrast"] for row in nodes])),
            "p25Contrast": float(np.quantile([row["contrast"] for row in nodes], 0.25)),
            "nodes": nodes,
        }
        depths = [row["depthPixels"] for row in nodes if row["depthPixels"] is not None]
        if depths:
            result["medianDepthPixels"] = float(np.median(depths))
            result["p25DepthPixels"] = float(np.quantile(depths, 0.25))
            result["p75DepthPixels"] = float(np.quantile(depths, 0.75))
        results.append(result)

        selected = {
            local_frame: candidates_by_frame[local_frame][candidate_index]
            for local_frame, candidate_index in path
        }
        for local_frame, candidates in enumerate(candidates_by_frame):
            reference = selected.get(local_frame)
            if reference is None:
                continue
            for candidate_index, candidate in enumerate(candidates):
                if hypot(candidate.x - reference.x, candidate.y - reference.y) <= 10.0:
                    banned.add((local_frame, candidate_index))

    return results


def primary_ulnar_points(phase1: dict[str, object]) -> dict[int, np.ndarray]:
    rows: dict[int, np.ndarray] = {}
    for node in phase1["ulnarArteryRetrogradeContinuity"]["nodes"]:
        rows[int(node["wholeBodyFrameIndex"])] = np.asarray(
            [float(node["xFullImagePixels"]), float(node["yFullImagePixels"])],
            dtype=float,
        )
    for node in phase1["ulnarBridgeSearch"]["observations"]:
        rows[int(node["wholeBodyFrameIndex"])] = np.asarray(
            [float(node["xFullImagePixels"]), float(node["yFullImagePixels"])],
            dtype=float,
        )
    return rows


def interpolate_track(points: dict[int, np.ndarray], indices: list[int]) -> dict[int, np.ndarray]:
    known = sorted(points)
    if len(known) < 2:
        raise recon.ReconError("not enough ulnar source-continuity points")
    x = np.asarray(known, dtype=float)
    px = np.asarray([points[index][0] for index in known])
    py = np.asarray([points[index][1] for index in known])
    result: dict[int, np.ndarray] = {}
    for index in indices:
        if index < known[0] or index > known[-1]:
            continue
        result[index] = np.asarray(
            [float(np.interp(index, x, px)), float(np.interp(index, x, py))]
        )
    return result


def branch_candidates(
    image: np.ndarray,
    ulnar_point: np.ndarray,
) -> list[AnonymousCandidate]:
    raw = recon.vessel_candidates(image, ulnar_point, radius=125)
    result: list[AnonymousCandidate] = []
    for candidate in raw:
        distance = hypot(candidate.x - ulnar_point[0], candidate.y - ulnar_point[1])
        if (
            10.0 <= distance <= 120.0
            and candidate.circularity >= 0.16
            and candidate.contrast >= 10.0
            and candidate.x >= 1450
            and 180 <= candidate.y <= 1030
        ):
            result.append(
                AnonymousCandidate(
                    x=candidate.x,
                    y=candidate.y,
                    area=candidate.area,
                    circularity=candidate.circularity,
                    contrast=candidate.contrast,
                )
            )
    result.sort(key=candidate_score, reverse=True)
    return result[:28]


def add_branch_topology_metrics(
    tracks: list[dict[str, object]],
    ulnar: dict[int, np.ndarray],
) -> None:
    for track in tracks:
        distances: list[tuple[int, float]] = []
        for node in track["nodes"]:
            index = int(node["wholeBodyFrameIndex"])
            point = ulnar.get(index)
            if point is None:
                continue
            distances.append(
                (
                    index,
                    hypot(
                        float(node["xFullImagePixels"]) - point[0],
                        float(node["yFullImagePixels"]) - point[1],
                    ),
                )
            )
        distances.sort()
        values = [distance for _, distance in distances]
        third = max(1, len(values) // 3)
        proximal = values[:third]
        distal = values[-third:]
        track["distanceToUlnar"] = {
            "overlapFrameCount": len(values),
            "minimumPixels": min(values) if values else None,
            "proximalThirdMedianPixels": float(np.median(proximal)) if proximal else None,
            "distalThirdMedianPixels": float(np.median(distal)) if distal else None,
        }
        d = track["distanceToUlnar"]
        strong_track = (
            track["spanFrameCount"] >= 55
            and track["coverageFraction"] >= 0.72
            and track["maxGapFrames"] <= 4
            and track["medianCircularity"] >= 0.40
            and track["medianContrast"] >= 18.0
            and track["meanJumpPerFramePixels"] <= 4.5
        )
        convergence = (
            d["overlapFrameCount"] >= 40
            and d["minimumPixels"] is not None
            and d["minimumPixels"] <= 12.0
            and d["proximalThirdMedianPixels"] is not None
            and d["distalThirdMedianPixels"] is not None
            and d["distalThirdMedianPixels"] >= d["proximalThirdMedianPixels"] + 8.0
        )
        track["branchTopologyClassification"] = (
            "distinct-distal-track-with-proximal-convergence-candidate"
            if strong_track and convergence
            else "anonymous-vessel-like-track-only"
        )


def superficial_candidates(image: np.ndarray) -> list[AnonymousCandidate]:
    x0, x1 = 1450, 2048
    y0, y1 = 150, 1100
    crop = image[y0:y1, x0:x1]
    tissue = recon.is_tissue(crop).astype(np.uint8)
    depth = cv2.distanceTransform(tissue, cv2.DIST_L2, 5)
    values = crop.astype(np.float32)
    luminance = (
        0.299 * values[:, :, 0]
        + 0.587 * values[:, :, 1]
        + 0.114 * values[:, :, 2]
    )
    support = luminance[tissue.astype(bool)]
    if len(support) < 100:
        return []
    threshold = min(108.0, float(np.quantile(support, 0.16)))
    shallow = (depth >= 3.0) & (depth <= 34.0)
    dark = (luminance <= threshold) & tissue.astype(bool) & shallow
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(
        dark.astype(np.uint8) * 255, 8
    )
    result: list[AnonymousCandidate] = []
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if not 6 <= area <= 420:
            continue
        component = (labels == label).astype(np.uint8)
        contours, _ = cv2.findContours(component, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        contour = max(contours, key=cv2.contourArea)
        perimeter = float(cv2.arcLength(contour, True))
        circularity = 4.0 * pi * area / (perimeter * perimeter) if perimeter > 0 else 0.0
        cx, cy = map(float, centroids[label])
        gx, gy = x0 + cx, y0 + cy
        if gx < 1510 or gy < 190 or gy > 1060:
            continue
        inside = component.astype(bool)
        dilated = cv2.dilate(component, np.ones((3, 3), np.uint8), iterations=3).astype(bool)
        ring = dilated & ~inside
        contrast = float(luminance[ring].mean() - luminance[inside].mean()) if ring.any() else 0.0
        pixels = crop[inside].astype(float)
        mean = pixels.mean(axis=0)
        median_depth = float(np.median(depth[inside]))
        if (
            circularity < 0.14
            or contrast < 10.0
            or mean[2] > mean[0] + 35
        ):
            continue
        result.append(
            AnonymousCandidate(
                x=gx,
                y=gy,
                area=area,
                circularity=float(circularity),
                contrast=contrast,
                depth=median_depth,
            )
        )
    result.sort(key=candidate_score, reverse=True)
    return result[:45]


def classify_superficial_tracks(tracks: list[dict[str, object]]) -> None:
    for track in tracks:
        strong = (
            track["spanFrameCount"] >= 90
            and track["coverageFraction"] >= 0.78
            and track["maxGapFrames"] <= 4
            and track["medianCircularity"] >= 0.38
            and track["medianContrast"] >= 18.0
            and track["meanJumpPerFramePixels"] <= 4.5
            and 4.0 <= track.get("medianDepthPixels", 999.0) <= 30.0
        )
        track["classification"] = (
            "anonymous-continuous-superficial-vessel-candidate"
            if strong
            else "anonymous-superficial-diagnostic-track"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--archive-index", type=Path, required=True)
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--phase1", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    phase1 = json.loads(args.phase1.read_text())
    if phase1.get("task") != "TASK-AS06":
        raise recon.ReconError("phase-1 report is not TASK-AS06")
    if not phase1["nextSearchReadiness"]["bifurcationSearchAuthorized"]:
        raise recon.ReconError("phase-1 evidence does not authorize branch search")

    source = recon.SourceArchive(args.inventory, args.archive_index, args.archive_root)
    try:
        ulnar_points = primary_ulnar_points(phase1)

        branch_first = source.by_name["avf1538a.png"]["index"]
        branch_last = source.by_name["avf1575c.png"]["index"]
        branch_indices = list(range(branch_first, branch_last + 1))
        ulnar_interp = interpolate_track(ulnar_points, branch_indices)
        branch_frames: list[int] = []
        branch_candidates_by_frame: list[list[AnonymousCandidate]] = []
        for index in branch_indices:
            point = ulnar_interp.get(index)
            if point is None:
                continue
            frame = source.frames[index]
            if frame["source"]["listedByteSize"] == 0:
                continue
            image = source.read_rgb(frame["filename"])
            branch_frames.append(index)
            branch_candidates_by_frame.append(branch_candidates(image, point))

        branch_tracks = build_tracks(
            branch_frames,
            branch_candidates_by_frame,
            max_gap=4,
            max_jump_per_frame=7.0,
            repeat=8,
        )
        add_branch_topology_metrics(branch_tracks, ulnar_interp)
        topology_candidates = [
            track for track in branch_tracks
            if track["branchTopologyClassification"]
            == "distinct-distal-track-with-proximal-convergence-candidate"
        ]

        superficial_first = source.by_name["avf1498a.png"]["index"]
        superficial_last = source.by_name["avf1605c.png"]["index"]
        superficial_frames: list[int] = []
        superficial_candidates_by_frame: list[list[AnonymousCandidate]] = []
        for index in range(superficial_first, superficial_last + 1):
            frame = source.frames[index]
            if frame["source"]["listedByteSize"] == 0:
                continue
            image = source.read_rgb(frame["filename"])
            superficial_frames.append(index)
            superficial_candidates_by_frame.append(superficial_candidates(image))

        superficial_tracks = build_tracks(
            superficial_frames,
            superficial_candidates_by_frame,
            max_gap=4,
            max_jump_per_frame=7.0,
            repeat=8,
        )
        classify_superficial_tracks(superficial_tracks)
        strong_superficial = [
            track for track in superficial_tracks
            if track["classification"]
            == "anonymous-continuous-superficial-vessel-candidate"
        ]

        radial_status = (
            "unresolved-branch-topology-candidate-needs-human-review"
            if topology_candidates
            else "unresolved-after-same-subject-branch-topology-search"
        )
        superficial_status = (
            "unresolved-anonymous-continuous-candidates-without-named-identity"
            if strong_superficial
            else "unresolved-after-wider-same-subject-superficial-search"
        )

        report = {
            "schema": "ph-as06-branch-superficial-recon.v1",
            "schemaVersion": "1",
            "task": "TASK-AS06",
            "coordinateSpace": {
                "kind": "source-image-stack",
                "patientSpaceClaim": False,
            },
            "source": {
                "inventorySha256": recon.path_sha256(args.inventory),
                "archiveIndexSha256": recon.path_sha256(args.archive_index),
                "phase1Report": str(args.phase1),
                "phase1SourceInventorySha256": phase1["source"]["inventorySha256"],
                "verifiedChunkIndices": sorted(source._verified),
            },
            "arterialBranchTopologySearch": {
                "searchFirstSourceFilename": "avf1538a.png",
                "searchLastSourceFilename": "avf1575c.png",
                "knownUlnarContinuityUsedAsAnchor": True,
                "crossSubjectAtlasUsed": False,
                "anonymousTrackCount": len(branch_tracks),
                "topologyCandidateCount": len(topology_candidates),
                "tracks": branch_tracks,
                "disposition": {
                    "radialArteryStatus": radial_status,
                    "radialArteryIdentityEstablished": False,
                    "brachialArteryIdentityEstablished": False,
                    "bifurcationIdentityEstablished": False,
                    "automaticPromotionAllowed": False,
                    "reason": (
                        "A source-continuous second-branch topology candidate requires human anatomical review before naming."
                        if topology_candidates
                        else "No anonymous same-subject track met the fixed distinct-distal/proximal-convergence gate; radial/brachial identity remains unresolved."
                    ),
                },
            },
            "superficialVenousSearch": {
                "searchFirstSourceFilename": "avf1498a.png",
                "searchLastSourceFilename": "avf1605c.png",
                "namedVeinAtlasUsed": False,
                "procedureRoleUsedAsIdentity": False,
                "anonymousTrackCount": len(superficial_tracks),
                "continuousAnonymousCandidateCount": len(strong_superficial),
                "tracks": superficial_tracks,
                "disposition": {
                    "status": superficial_status,
                    "namedVeinIdentityEstablished": False,
                    "proceduralTargetIdentityEstablished": False,
                    "automaticPromotionAllowed": False,
                    "reason": (
                        "Continuous shallow same-subject candidates may be reviewed as observed tracks, but course/connectivity evidence is still insufficient to call cephalic or basilic."
                        if strong_superficial
                        else "The wider proximal same-subject search did not produce a track meeting fixed superficial continuity gates."
                    ),
                },
            },
            "taskDisposition": {
                "status": "complete-unresolved-with-stronger-same-subject-evidence",
                "radialArteryIdentity": "unresolved",
                "superficialVeinIdentity": "unresolved",
                "feedForwardToAS07Allowed": True,
                "automaticMedicalMasterPromotionAllowed": False,
                "basis": (
                    "AS06 now includes same-subject proximal bone continuity, reviewed-ulnar-anchor extension across the pair-support transition, "
                    "an anonymous branch-topology search, and a wider anonymous superficial-vessel search. Unresolved identities stay fail-closed."
                ),
            },
            "claims": {
                "humanEdited": False,
                "anatomicallyReviewed": False,
                "medicalValidation": False,
                "patientSpaceGeometry": False,
                "ctRegistrationEstablished": False,
                "radialArteryIdentityEstablished": False,
                "brachialArteryIdentityEstablished": False,
                "namedSuperficialVeinIdentityEstablished": False,
                "procedureRoleUsedAsAnatomicalIdentity": False,
                "crossSubjectGeometryUsed": False,
                "automaticPromotionAllowed": False,
            },
        }

        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(
            json.dumps(
                {
                    "arterialBranchTopologySearch": {
                        "anonymousTrackCount": len(branch_tracks),
                        "topologyCandidateCount": len(topology_candidates),
                        "topTracks": [
                            {
                                k: track[k]
                                for k in (
                                    "rank",
                                    "nodeCount",
                                    "spanFrameCount",
                                    "coverageFraction",
                                    "maxGapFrames",
                                    "meanJumpPerFramePixels",
                                    "medianCircularity",
                                    "medianContrast",
                                    "distanceToUlnar",
                                    "branchTopologyClassification",
                                )
                            }
                            for track in branch_tracks[:5]
                        ],
                        "disposition": report["arterialBranchTopologySearch"]["disposition"],
                    },
                    "superficialVenousSearch": {
                        "anonymousTrackCount": len(superficial_tracks),
                        "continuousAnonymousCandidateCount": len(strong_superficial),
                        "topTracks": [
                            {
                                k: track[k]
                                for k in (
                                    "rank",
                                    "nodeCount",
                                    "spanFrameCount",
                                    "coverageFraction",
                                    "maxGapFrames",
                                    "meanJumpPerFramePixels",
                                    "medianCircularity",
                                    "medianContrast",
                                    "medianDepthPixels",
                                    "classification",
                                )
                                if k in track
                            }
                            for track in superficial_tracks[:5]
                        ],
                        "disposition": report["superficialVenousSearch"]["disposition"],
                    },
                    "taskDisposition": report["taskDisposition"],
                },
                indent=2,
            )
        )
    finally:
        source.close()


if __name__ == "__main__":
    main()
