from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from math import hypot, log, pi
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

import a06_detect_vessel_candidates as base


SEARCH_RADIUS_FROM_RADIUS_BONE = 90.0
MIN_RADIUS_DISTANCE = 8.0
MIN_AREA = 6
MAX_AREA = 180
MIN_CIRCULARITY = 0.55
MIN_CONTRAST = 30.0
MAX_GAP = 2
MAX_JUMP_PER_FRAME = 5.0
MAX_JUMP_BUFFER = 1.0

MIN_ACCEPTED_SPAN = 60
MIN_ACCEPTED_COVERAGE = 0.90
MIN_ACCEPTED_MEDIAN_CIRCULARITY = 0.80
MIN_ACCEPTED_P25_CIRCULARITY = 0.60
MIN_ACCEPTED_MEDIAN_CONTRAST = 50.0
MIN_ACCEPTED_P25_CONTRAST = 35.0
MAX_ACCEPTED_MEAN_JUMP_PER_FRAME = 3.0
MAX_ACCEPTED_JUMP_PER_FRAME = 5.0


@dataclass
class SourceCandidate:
    area: int
    circularity: float
    contrast: float
    x: float
    y: float
    distance_to_radius: float
    distance_to_ulna: float
    normalized_radial_offset: float
    normalized_perpendicular_offset: float


def _radial_side_candidates(
    image: np.ndarray,
    radius_point: np.ndarray,
    ulna_point: np.ndarray,
) -> list[SourceCandidate]:
    height, width = image.shape[:2]
    radius_x, radius_y = map(float, radius_point)
    ulna_x, ulna_y = map(float, ulna_point)

    bone_axis = radius_point - ulna_point
    bone_separation = float(np.linalg.norm(bone_axis))
    if bone_separation <= 1e-8:
        return []
    axis = bone_axis / bone_separation
    perp = np.asarray([-axis[1], axis[0]], dtype=float)

    yy, xx = np.ogrid[:height, :width]
    distance_radius = np.sqrt(
        (xx - radius_x) ** 2 + (yy - radius_y) ** 2
    )
    distance_ulna = np.sqrt(
        (xx - ulna_x) ** 2 + (yy - ulna_y) ** 2
    )

    tissue = base._is_tissue(image)
    corridor = (
        tissue
        & (distance_radius <= SEARCH_RADIUS_FROM_RADIUS_BONE)
        & (distance_radius >= MIN_RADIUS_DISTANCE)
        & (distance_radius + 2.0 < distance_ulna)
    )

    values = image.astype(np.float32)
    red, green, blue = values[:, :, 0], values[:, :, 1], values[:, :, 2]
    luminance = 0.299 * red + 0.587 * green + 0.114 * blue
    support = luminance[corridor]
    if len(support) < 100:
        return []

    threshold = min(105.0, float(np.quantile(support, 0.18)))
    dark = corridor & (luminance <= threshold)

    count, labels, stats, centroids = cv2.connectedComponentsWithStats(
        dark.astype(np.uint8) * 255,
        8,
    )

    candidates: list[SourceCandidate] = []
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if not MIN_AREA <= area <= MAX_AREA:
            continue

        component_mask = (labels == label).astype(np.uint8)
        contours, _ = cv2.findContours(
            component_mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        if not contours:
            continue
        contour = max(contours, key=cv2.contourArea)
        perimeter = float(cv2.arcLength(contour, True))
        if perimeter <= 0:
            continue
        circularity = 4.0 * pi * area / (perimeter * perimeter)
        if circularity < MIN_CIRCULARITY:
            continue

        cx, cy = map(float, centroids[label])
        dr = hypot(cx - radius_x, cy - radius_y)
        du = hypot(cx - ulna_x, cy - ulna_y)
        if not (
            MIN_RADIUS_DISTANCE <= dr <= SEARCH_RADIUS_FROM_RADIUS_BONE
            and dr + 2.0 < du
        ):
            continue

        component_bool = component_mask.astype(bool)
        dilated = cv2.dilate(
            component_mask,
            np.ones((3, 3), np.uint8),
            iterations=3,
        ).astype(bool)
        ring = dilated & ~component_bool & tissue
        if not bool(ring.any()):
            continue
        contrast = float(
            luminance[ring].mean()
            - luminance[component_bool].mean()
        )
        if contrast < MIN_CONTRAST:
            continue

        relative = np.asarray(
            [cx - radius_x, cy - radius_y],
            dtype=float,
        )
        normalized_radial = float(
            np.dot(relative, axis) / bone_separation
        )
        normalized_perpendicular = float(
            np.dot(relative, perp) / bone_separation
        )

        candidates.append(
            SourceCandidate(
                area=area,
                circularity=float(circularity),
                contrast=contrast,
                x=cx,
                y=cy,
                distance_to_radius=dr,
                distance_to_ulna=du,
                normalized_radial_offset=normalized_radial,
                normalized_perpendicular_offset=normalized_perpendicular,
            )
        )
    return candidates


def _node_score(candidate: SourceCandidate) -> float:
    return (
        1.0
        + 0.045 * min(candidate.contrast, 90.0)
        + 0.9 * min(candidate.circularity, 1.2)
        - 0.008 * candidate.distance_to_radius
    )


def _best_path(
    candidates_by_frame: list[list[SourceCandidate]],
) -> list[tuple[int, int]]:
    states: dict[
        tuple[int, int],
        tuple[float, tuple[int, int] | None],
    ] = {}
    best_end: tuple[int, int] | None = None

    for frame_index, frame_candidates in enumerate(candidates_by_frame):
        for candidate_index, candidate in enumerate(frame_candidates):
            best_score = _node_score(candidate)
            predecessor: tuple[int, int] | None = None

            for gap in range(1, MAX_GAP + 1):
                previous_frame = frame_index - gap
                if previous_frame < 0:
                    continue
                for previous_index, previous in enumerate(
                    candidates_by_frame[previous_frame]
                ):
                    state = states.get((previous_frame, previous_index))
                    if state is None:
                        continue

                    jump = hypot(
                        candidate.x - previous.x,
                        candidate.y - previous.y,
                    )
                    jump_per_frame = jump / gap
                    if (
                        jump
                        > MAX_JUMP_PER_FRAME * gap + MAX_JUMP_BUFFER
                    ):
                        continue

                    normalized_shift = hypot(
                        candidate.normalized_radial_offset
                        - previous.normalized_radial_offset,
                        candidate.normalized_perpendicular_offset
                        - previous.normalized_perpendicular_offset,
                    )
                    area_change = abs(
                        log(
                            (candidate.area + 1)
                            / (previous.area + 1)
                        )
                    )
                    score = (
                        state[0]
                        + _node_score(candidate)
                        - 0.35 * jump_per_frame
                        - 1.5 * normalized_shift
                        - 0.35 * area_change
                        - 0.8 * (gap - 1)
                    )
                    if score > best_score:
                        best_score = score
                        predecessor = (
                            previous_frame,
                            previous_index,
                        )

            states[(frame_index, candidate_index)] = (
                best_score,
                predecessor,
            )
            if best_end is None or best_score > states[best_end][0]:
                best_end = (frame_index, candidate_index)

    if best_end is None:
        return []

    path: list[tuple[int, int]] = []
    current: tuple[int, int] | None = best_end
    while current is not None:
        path.append(current)
        current = states[current][1]
    return list(reversed(path))


def _metrics(
    selected: list[tuple[int, int]],
    candidates_by_frame: list[list[SourceCandidate]],
) -> dict[str, object]:
    frames = np.asarray([frame for frame, _ in selected], dtype=int)
    candidates = [
        candidates_by_frame[frame][index]
        for frame, index in selected
    ]
    points = np.asarray(
        [[candidate.x, candidate.y] for candidate in candidates],
        dtype=float,
    )
    gaps = np.diff(frames)
    jumps = (
        np.linalg.norm(np.diff(points, axis=0), axis=1)
        if len(points) > 1
        else np.asarray([], dtype=float)
    )
    jump_per_frame = (
        jumps / gaps
        if len(jumps)
        else np.asarray([], dtype=float)
    )
    span = int(frames[-1] - frames[0] + 1)
    circularity = np.asarray(
        [candidate.circularity for candidate in candidates],
        dtype=float,
    )
    contrast = np.asarray(
        [candidate.contrast for candidate in candidates],
        dtype=float,
    )
    radius_distance = np.asarray(
        [candidate.distance_to_radius for candidate in candidates],
        dtype=float,
    )
    radial_offset = np.asarray(
        [candidate.normalized_radial_offset for candidate in candidates],
        dtype=float,
    )
    perpendicular_offset = np.asarray(
        [
            candidate.normalized_perpendicular_offset
            for candidate in candidates
        ],
        dtype=float,
    )

    return {
        "nodeCount": len(selected),
        "spanFrameCount": span,
        "coverageFraction": float(len(selected) / span),
        "firstGlobalFrameIndex": int(frames[0]),
        "lastGlobalFrameIndex": int(frames[-1]),
        "firstSourceFilename": base._source_filename(int(frames[0])),
        "lastSourceFilename": base._source_filename(int(frames[-1])),
        "meanJumpPerFrameSourcePixels": (
            float(jump_per_frame.mean()) if len(jump_per_frame) else 0.0
        ),
        "maxJumpPerFrameSourcePixels": (
            float(jump_per_frame.max()) if len(jump_per_frame) else 0.0
        ),
        "medianCircularity": float(np.median(circularity)),
        "p25Circularity": float(np.quantile(circularity, 0.25)),
        "medianContrast": float(np.median(contrast)),
        "p25Contrast": float(np.quantile(contrast, 0.25)),
        "medianDistanceToRadiusPixels": float(np.median(radius_distance)),
        "medianNormalizedRadialOffset": float(np.median(radial_offset)),
        "medianNormalizedPerpendicularOffset": float(
            np.median(perpendicular_offset)
        ),
        "p25NormalizedPerpendicularOffset": float(
            np.quantile(perpendicular_offset, 0.25)
        ),
        "p75NormalizedPerpendicularOffset": float(
            np.quantile(perpendicular_offset, 0.75)
        ),
    }


def _accepted(metrics: dict[str, object]) -> bool:
    return (
        int(metrics["spanFrameCount"]) >= MIN_ACCEPTED_SPAN
        and float(metrics["coverageFraction"]) >= MIN_ACCEPTED_COVERAGE
        and float(metrics["medianCircularity"])
        >= MIN_ACCEPTED_MEDIAN_CIRCULARITY
        and float(metrics["p25Circularity"])
        >= MIN_ACCEPTED_P25_CIRCULARITY
        and float(metrics["medianContrast"])
        >= MIN_ACCEPTED_MEDIAN_CONTRAST
        and float(metrics["p25Contrast"])
        >= MIN_ACCEPTED_P25_CONTRAST
        and float(metrics["meanJumpPerFrameSourcePixels"])
        <= MAX_ACCEPTED_MEAN_JUMP_PER_FRAME
        and float(metrics["maxJumpPerFrameSourcePixels"])
        <= MAX_ACCEPTED_JUMP_PER_FRAME
    )


def _scan_windows(
    path: list[tuple[int, int]],
    candidates_by_frame: list[list[SourceCandidate]],
) -> list[dict[str, object]]:
    accepted: list[dict[str, object]] = []
    for start in range(len(path)):
        for stop in range(start, len(path)):
            span = path[stop][0] - path[start][0] + 1
            if span < MIN_ACCEPTED_SPAN:
                continue
            metrics = _metrics(
                path[start : stop + 1],
                candidates_by_frame,
            )
            if _accepted(metrics):
                accepted.append(metrics)
    accepted.sort(
        key=lambda row: (
            int(row["spanFrameCount"]),
            float(row["coverageFraction"]),
            float(row["medianContrast"]),
            float(row["medianCircularity"]),
        ),
        reverse=True,
    )
    return accepted


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bone-report", type=Path, required=True)
    parser.add_argument("--cryo-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()

    bone_report = json.loads(
        args.bone_report.read_text(encoding="utf-8")
    )
    bone_tracks = base._bone_tracks(bone_report)

    candidates_by_frame: list[list[SourceCandidate]] = []
    for global_index in range(base.FRAME_COUNT):
        image = np.asarray(
            Image.open(
                args.cryo_root / base._source_filename(global_index)
            ).convert("RGB")
        )
        candidates_by_frame.append(
            _radial_side_candidates(
                image,
                bone_tracks["radius"][global_index],
                bone_tracks["ulna"][global_index],
            )
        )

    path = _best_path(candidates_by_frame)
    accepted = _scan_windows(path, candidates_by_frame)
    whole = _metrics(path, candidates_by_frame) if path else None

    report = {
        "schema": "ph-a06-radial-source-first-diagnostic.v1",
        "schemaVersion": "1",
        "task": "TASK-A06",
        "recordedAt": "2026-09-09",
        "status": "diagnostic-only",
        "searchModel": {
            "atlasCenterUsed": False,
            "radiusUlnaBoneTracksUsed": True,
            "searchRadiusFromRadiusBonePixels": (
                SEARCH_RADIUS_FROM_RADIUS_BONE
            ),
            "radialSideDefinition": (
                "candidate center is closer to radius than ulna"
            ),
            "appearancePrior": (
                "small dark circular high-contrast component, using "
                "thresholds fixed from the successfully source-supported "
                "ulnar artery phenotype"
            ),
        },
        "fixedThresholds": {
            "candidateAreaPixels": [MIN_AREA, MAX_AREA],
            "candidateMinCircularity": MIN_CIRCULARITY,
            "candidateMinContrast": MIN_CONTRAST,
            "maxTrackGapFrames": MAX_GAP,
            "maxJumpPerFrameSourcePixels": MAX_JUMP_PER_FRAME,
            "acceptedMinSpanFrames": MIN_ACCEPTED_SPAN,
            "acceptedMinCoverage": MIN_ACCEPTED_COVERAGE,
            "acceptedMinMedianCircularity": (
                MIN_ACCEPTED_MEDIAN_CIRCULARITY
            ),
            "acceptedMinP25Circularity": (
                MIN_ACCEPTED_P25_CIRCULARITY
            ),
            "acceptedMinMedianContrast": (
                MIN_ACCEPTED_MEDIAN_CONTRAST
            ),
            "acceptedMinP25Contrast": (
                MIN_ACCEPTED_P25_CONTRAST
            ),
        },
        "candidateAvailability": {
            "supportedFrameCount": base.FRAME_COUNT,
            "framesWithCandidate": int(
                sum(bool(frame) for frame in candidates_by_frame)
            ),
            "totalCandidateCount": int(
                sum(len(frame) for frame in candidates_by_frame)
            ),
        },
        "bestPath": whole,
        "acceptedBoundedSegments": accepted[:20],
        "decision": {
            "classification": (
                "source-first-bounded-segment-signal"
                if accepted
                else "not-established"
            ),
            "acceptedSegmentCount": len(accepted),
            "longestAcceptedSpanFrames": (
                int(accepted[0]["spanFrameCount"])
                if accepted
                else 0
            ),
            "representationGenerated": False,
            "automaticPromotionAllowed": False,
        },
        "claims": {
            "radialArteryIdentityEstablishedByThisDiagnostic": False,
            "radialArteryRepresentationGenerated": False,
            "humanEdited": False,
            "anatomicallyReviewed": False,
            "medicalValidation": False,
            "completeVesselExtent": False,
            "patientSpaceGeometry": False,
            "automaticPromotionAllowed": False,
        },
    }

    args.output_root.mkdir(parents=True, exist_ok=True)
    (
        args.output_root
        / "a06-radial-source-first-diagnostic.v0.json"
    ).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "candidateAvailability": report["candidateAvailability"],
                "bestPath": whole,
                "decision": report["decision"],
                "topAcceptedSegments": accepted[:5],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
