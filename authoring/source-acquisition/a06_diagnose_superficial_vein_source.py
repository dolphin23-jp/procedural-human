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


MIN_AREA = 8
MAX_AREA = 500
MIN_CIRCULARITY = 0.10
MIN_CONTRAST = 10.0
MIN_RING_SUBCUT_FRACTION = 0.30
MAX_RING_MUSCLE_FRACTION = 0.45
MIN_SKIN_DISTANCE = 4.0
MAX_SKIN_DISTANCE = 70.0

MAX_GAP = 3
MAX_JUMP_PER_FRAME = 6.0
MAX_JUMP_BUFFER = 1.5

ACCEPT_MIN_SPAN = 75
ACCEPT_MIN_COVERAGE = 0.80
ACCEPT_MIN_MEDIAN_CIRCULARITY = 0.25
ACCEPT_MIN_P25_CIRCULARITY = 0.15
ACCEPT_MIN_MEDIAN_CONTRAST = 20.0
ACCEPT_MIN_P25_CONTRAST = 12.0
ACCEPT_MIN_MEDIAN_RING_SUBCUT = 0.45
ACCEPT_MIN_P25_RING_SUBCUT = 0.30
ACCEPT_MAX_MEDIAN_RING_MUSCLE = 0.30
ACCEPT_MIN_MEDIAN_SKIN_DISTANCE = 5.0
ACCEPT_MAX_MEDIAN_SKIN_DISTANCE = 55.0
ACCEPT_MAX_MEAN_JUMP_PER_FRAME = 3.5
ACCEPT_MAX_JUMP_PER_FRAME = 6.0
ACCEPT_MAX_LOCAL_IQR = 0.25

TOP_TRACK_COUNT = 6
TRACK_EXCLUSION_RADIUS = 8.0


@dataclass
class VeinCandidate:
    area: int
    circularity: float
    contrast: float
    x: float
    y: float
    ring_subcut_fraction: float
    ring_muscle_fraction: float
    skin_distance: float
    normalized_axis_offset: float
    normalized_perpendicular_offset: float


def _load_mask(path: Path) -> np.ndarray:
    image = np.asarray(Image.open(path).convert("L"))
    if image.shape != (750, 550):
        raise RuntimeError(f"unexpected mask dimensions for {path}: {image.shape}")
    return image > 0


def _candidate_components(
    image: np.ndarray,
    subcutaneous: np.ndarray,
    muscle: np.ndarray,
    skin: np.ndarray,
    radius_point: np.ndarray,
    ulna_point: np.ndarray,
) -> list[VeinCandidate]:
    values = image.astype(np.float32)
    red, green, blue = values[:, :, 0], values[:, :, 1], values[:, :, 2]
    luminance = 0.299 * red + 0.587 * green + 0.114 * blue

    blue_background = (
        (blue > red + 18)
        & (blue > green + 8)
        & (blue > 55)
    )

    tissue_reference = subcutaneous | muscle
    reference_values = luminance[tissue_reference]
    if len(reference_values) < 100:
        return []

    threshold = min(
        105.0,
        float(np.quantile(reference_values, 0.12)),
    )
    dark = (luminance <= threshold) & ~blue_background

    count, labels, stats, centroids = cv2.connectedComponentsWithStats(
        dark.astype(np.uint8) * 255,
        8,
    )

    distance_to_skin = cv2.distanceTransform(
        (~skin).astype(np.uint8),
        cv2.DIST_L2,
        5,
    )

    bone_axis = radius_point - ulna_point
    bone_separation = float(np.linalg.norm(bone_axis))
    if bone_separation <= 1e-8:
        return []
    axis = bone_axis / bone_separation
    perp = np.asarray([-axis[1], axis[0]], dtype=float)
    midpoint = (radius_point + ulna_point) / 2.0

    candidates: list[VeinCandidate] = []
    kernel = np.ones((3, 3), np.uint8)

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
        xi = int(round(cx))
        yi = int(round(cy))
        if not (0 <= xi < 550 and 0 <= yi < 750):
            continue

        skin_distance = float(distance_to_skin[yi, xi])
        if not MIN_SKIN_DISTANCE <= skin_distance <= MAX_SKIN_DISTANCE:
            continue

        dilated = cv2.dilate(
            component_mask,
            kernel,
            iterations=5,
        ).astype(bool)
        component_bool = component_mask.astype(bool)
        ring = dilated & ~component_bool & ~blue_background
        if int(ring.sum()) < 20:
            continue

        ring_subcut_fraction = float(subcutaneous[ring].mean())
        ring_muscle_fraction = float(muscle[ring].mean())
        if (
            ring_subcut_fraction < MIN_RING_SUBCUT_FRACTION
            or ring_muscle_fraction > MAX_RING_MUSCLE_FRACTION
        ):
            continue

        contrast = float(
            luminance[ring].mean()
            - luminance[component_bool].mean()
        )
        if contrast < MIN_CONTRAST:
            continue

        component_pixels = image[component_bool].astype(float)
        mean_rgb = component_pixels.mean(axis=0)
        if mean_rgb[2] > mean_rgb[0] + 35:
            continue

        relative = np.asarray([cx, cy], dtype=float) - midpoint
        normalized_axis = float(
            np.dot(relative, axis) / bone_separation
        )
        normalized_perpendicular = float(
            np.dot(relative, perp) / bone_separation
        )

        candidates.append(
            VeinCandidate(
                area=area,
                circularity=float(circularity),
                contrast=contrast,
                x=cx,
                y=cy,
                ring_subcut_fraction=ring_subcut_fraction,
                ring_muscle_fraction=ring_muscle_fraction,
                skin_distance=skin_distance,
                normalized_axis_offset=normalized_axis,
                normalized_perpendicular_offset=normalized_perpendicular,
            )
        )
    return candidates


def _node_score(candidate: VeinCandidate) -> float:
    area_penalty = max(0.0, (candidate.area - 180.0) / 150.0)
    preferred_skin_distance = abs(candidate.skin_distance - 24.0) / 24.0
    return (
        1.0
        + 0.035 * min(candidate.contrast, 80.0)
        + 0.65 * min(candidate.circularity, 1.2)
        + 1.2 * candidate.ring_subcut_fraction
        - 0.8 * candidate.ring_muscle_fraction
        - 0.25 * preferred_skin_distance
        - 0.20 * area_penalty
    )


def _best_path(
    candidates_by_frame: list[list[VeinCandidate]],
    excluded: dict[int, list[tuple[float, float]]],
) -> list[tuple[int, int]]:
    states: dict[
        tuple[int, int],
        tuple[float, tuple[int, int] | None],
    ] = {}
    best_end: tuple[int, int] | None = None

    for frame_index, frame_candidates in enumerate(candidates_by_frame):
        for candidate_index, candidate in enumerate(frame_candidates):
            if any(
                hypot(candidate.x - x, candidate.y - y)
                <= TRACK_EXCLUSION_RADIUS
                for x, y in excluded.get(frame_index, [])
            ):
                continue

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

                    local_shift = hypot(
                        candidate.normalized_axis_offset
                        - previous.normalized_axis_offset,
                        candidate.normalized_perpendicular_offset
                        - previous.normalized_perpendicular_offset,
                    )
                    area_change = abs(
                        log(
                            (candidate.area + 1)
                            / (previous.area + 1)
                        )
                    )
                    depth_change = abs(
                        candidate.skin_distance - previous.skin_distance
                    ) / 20.0

                    score = (
                        state[0]
                        + _node_score(candidate)
                        - 0.28 * jump_per_frame
                        - 1.25 * local_shift
                        - 0.25 * area_change
                        - 0.20 * depth_change
                        - 0.65 * (gap - 1)
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
    path: list[tuple[int, int]],
    candidates_by_frame: list[list[VeinCandidate]],
) -> dict[str, object]:
    frames = np.asarray([frame for frame, _ in path], dtype=int)
    candidates = [
        candidates_by_frame[frame][index]
        for frame, index in path
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
    subcut = np.asarray(
        [candidate.ring_subcut_fraction for candidate in candidates],
        dtype=float,
    )
    muscle = np.asarray(
        [candidate.ring_muscle_fraction for candidate in candidates],
        dtype=float,
    )
    depth = np.asarray(
        [candidate.skin_distance for candidate in candidates],
        dtype=float,
    )
    axis = np.asarray(
        [candidate.normalized_axis_offset for candidate in candidates],
        dtype=float,
    )
    perp = np.asarray(
        [
            candidate.normalized_perpendicular_offset
            for candidate in candidates
        ],
        dtype=float,
    )

    return {
        "nodeCount": len(path),
        "spanFrameCount": span,
        "coverageFraction": float(len(path) / span),
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
        "medianAreaPixels": float(
            np.median([candidate.area for candidate in candidates])
        ),
        "medianCircularity": float(np.median(circularity)),
        "p25Circularity": float(np.quantile(circularity, 0.25)),
        "medianContrast": float(np.median(contrast)),
        "p25Contrast": float(np.quantile(contrast, 0.25)),
        "medianRingSubcutaneousFraction": float(np.median(subcut)),
        "p25RingSubcutaneousFraction": float(np.quantile(subcut, 0.25)),
        "medianRingMuscleFraction": float(np.median(muscle)),
        "medianSkinDistancePixels": float(np.median(depth)),
        "p25SkinDistancePixels": float(np.quantile(depth, 0.25)),
        "p75SkinDistancePixels": float(np.quantile(depth, 0.75)),
        "medianNormalizedAxisOffset": float(np.median(axis)),
        "medianNormalizedPerpendicularOffset": float(np.median(perp)),
        "normalizedAxisIqr": float(
            np.quantile(axis, 0.75) - np.quantile(axis, 0.25)
        ),
        "normalizedPerpendicularIqr": float(
            np.quantile(perp, 0.75) - np.quantile(perp, 0.25)
        ),
    }


def _accepted(metrics: dict[str, object]) -> bool:
    return (
        int(metrics["spanFrameCount"]) >= ACCEPT_MIN_SPAN
        and float(metrics["coverageFraction"]) >= ACCEPT_MIN_COVERAGE
        and float(metrics["medianCircularity"])
        >= ACCEPT_MIN_MEDIAN_CIRCULARITY
        and float(metrics["p25Circularity"])
        >= ACCEPT_MIN_P25_CIRCULARITY
        and float(metrics["medianContrast"])
        >= ACCEPT_MIN_MEDIAN_CONTRAST
        and float(metrics["p25Contrast"])
        >= ACCEPT_MIN_P25_CONTRAST
        and float(metrics["medianRingSubcutaneousFraction"])
        >= ACCEPT_MIN_MEDIAN_RING_SUBCUT
        and float(metrics["p25RingSubcutaneousFraction"])
        >= ACCEPT_MIN_P25_RING_SUBCUT
        and float(metrics["medianRingMuscleFraction"])
        <= ACCEPT_MAX_MEDIAN_RING_MUSCLE
        and ACCEPT_MIN_MEDIAN_SKIN_DISTANCE
        <= float(metrics["medianSkinDistancePixels"])
        <= ACCEPT_MAX_MEDIAN_SKIN_DISTANCE
        and float(metrics["meanJumpPerFrameSourcePixels"])
        <= ACCEPT_MAX_MEAN_JUMP_PER_FRAME
        and float(metrics["maxJumpPerFrameSourcePixels"])
        <= ACCEPT_MAX_JUMP_PER_FRAME
        and float(metrics["normalizedAxisIqr"]) <= ACCEPT_MAX_LOCAL_IQR
        and float(metrics["normalizedPerpendicularIqr"])
        <= ACCEPT_MAX_LOCAL_IQR
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--a05-mask-root", type=Path, required=True)
    parser.add_argument("--bone-report", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()

    bone_report = json.loads(
        args.bone_report.read_text(encoding="utf-8")
    )
    bone_tracks = base._bone_tracks(bone_report)

    candidates_by_frame: list[list[VeinCandidate]] = []
    for global_index in range(base.FRAME_COUNT):
        filename = base._source_filename(global_index)
        stem = Path(filename).stem
        image = np.asarray(
            Image.open(args.source_root / filename).convert("RGB")
        )
        subcutaneous = _load_mask(
            args.a05_mask_root
            / "subcutaneous_soft_tissue"
            / f"{stem}.pgm"
        )
        muscle = _load_mask(
            args.a05_mask_root
            / "major_muscle_tendon_region"
            / f"{stem}.pgm"
        )
        skin = _load_mask(
            args.a05_mask_root / "skin" / f"{stem}.pgm"
        )
        candidates_by_frame.append(
            _candidate_components(
                image,
                subcutaneous,
                muscle,
                skin,
                bone_tracks["radius"][global_index],
                bone_tracks["ulna"][global_index],
            )
        )

    excluded: dict[int, list[tuple[float, float]]] = {}
    tracks: list[dict[str, object]] = []

    for track_index in range(TOP_TRACK_COUNT):
        path = _best_path(candidates_by_frame, excluded)
        if not path:
            break
        metrics = _metrics(path, candidates_by_frame)
        metrics["trackIndex"] = track_index
        metrics["acceptedByFixedThresholds"] = _accepted(metrics)
        tracks.append(metrics)

        for frame_index, candidate_index in path:
            candidate = candidates_by_frame[frame_index][candidate_index]
            excluded.setdefault(frame_index, []).append(
                (candidate.x, candidate.y)
            )

    accepted = [
        track for track in tracks
        if bool(track["acceptedByFixedThresholds"])
    ]

    report = {
        "schema": "ph-a06-superficial-vein-source-diagnostic.v1",
        "schemaVersion": "1",
        "task": "TASK-A06",
        "recordedAt": "2026-09-09",
        "status": "diagnostic-only",
        "searchModel": {
            "namedVeinAtlasUsed": False,
            "sourceImageUsed": True,
            "a05SubcutaneousCandidateUsed": True,
            "a05MuscleCandidateUsedAsExclusionEvidence": True,
            "a05SkinCandidateUsedForDepth": True,
            "radiusUlnaTracksUsedForStableLocalCoordinates": True,
            "candidateDefinition": (
                "dark component whose surrounding ring is predominantly "
                "A05 subcutaneous candidate tissue, is relatively non-muscular, "
                "and lies at a superficial bounded depth"
            ),
        },
        "fixedThresholds": {
            "candidateAreaPixels": [MIN_AREA, MAX_AREA],
            "candidateMinCircularity": MIN_CIRCULARITY,
            "candidateMinContrast": MIN_CONTRAST,
            "candidateMinRingSubcutaneousFraction": (
                MIN_RING_SUBCUT_FRACTION
            ),
            "candidateMaxRingMuscleFraction": MAX_RING_MUSCLE_FRACTION,
            "candidateSkinDistancePixels": [
                MIN_SKIN_DISTANCE,
                MAX_SKIN_DISTANCE,
            ],
            "acceptedMinSpanFrames": ACCEPT_MIN_SPAN,
            "acceptedMinCoverage": ACCEPT_MIN_COVERAGE,
            "acceptedMinMedianCircularity": (
                ACCEPT_MIN_MEDIAN_CIRCULARITY
            ),
            "acceptedMinP25Circularity": (
                ACCEPT_MIN_P25_CIRCULARITY
            ),
            "acceptedMinMedianContrast": ACCEPT_MIN_MEDIAN_CONTRAST,
            "acceptedMinP25Contrast": ACCEPT_MIN_P25_CONTRAST,
            "acceptedMinMedianRingSubcutaneousFraction": (
                ACCEPT_MIN_MEDIAN_RING_SUBCUT
            ),
            "acceptedMinP25RingSubcutaneousFraction": (
                ACCEPT_MIN_P25_RING_SUBCUT
            ),
            "acceptedMaxMedianRingMuscleFraction": (
                ACCEPT_MAX_MEDIAN_RING_MUSCLE
            ),
            "acceptedMedianSkinDistancePixels": [
                ACCEPT_MIN_MEDIAN_SKIN_DISTANCE,
                ACCEPT_MAX_MEDIAN_SKIN_DISTANCE,
            ],
            "acceptedMaxNormalizedLocalIqr": ACCEPT_MAX_LOCAL_IQR,
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
        "topDisjointTracks": tracks,
        "decision": {
            "classification": (
                "anonymous-superficial-vein-candidate-signal"
                if accepted
                else "not-established"
            ),
            "acceptedTrackCount": len(accepted),
            "bestAcceptedTrackIndex": (
                int(accepted[0]["trackIndex"])
                if accepted
                else None
            ),
            "namedVeinIdentityEstablished": False,
            "representationGenerated": False,
            "automaticPromotionAllowed": False,
        },
        "claims": {
            "superficialVeinRepresentationGenerated": False,
            "namedVeinIdentityEstablished": False,
            "proceduralTargetBindingEstablished": False,
            "humanEdited": False,
            "anatomicallyReviewed": False,
            "medicalValidation": False,
            "patientSpaceGeometry": False,
            "automaticPromotionAllowed": False,
        },
    }

    args.output_root.mkdir(parents=True, exist_ok=True)
    (
        args.output_root
        / "a06-superficial-vein-source-diagnostic.v0.json"
    ).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "candidateAvailability": report["candidateAvailability"],
                "topDisjointTracks": tracks,
                "decision": report["decision"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
