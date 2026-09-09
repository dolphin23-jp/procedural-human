from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from math import hypot, log
from pathlib import Path

import numpy as np
from PIL import Image

import a06_detect_vessel_candidates as base


MIN_SEGMENT_SPAN = 45
QUALITY_MIN_CIRCULARITY = 0.45
QUALITY_MIN_CONTRAST = 20.0
QUALITY_MAX_PRIOR_DISTANCE = 35.0
QUALITY_MAX_AREA = 220
MAX_TRACK_GAP = 2
MAX_JUMP_PER_FRAME = 5.0
MAX_JUMP_BUFFER = 1.0

ACCEPT_MIN_COVERAGE = 0.90
ACCEPT_MIN_MEDIAN_CIRCULARITY = 0.70
ACCEPT_MIN_P25_CIRCULARITY = 0.55
ACCEPT_MIN_MEDIAN_CONTRAST = 35.0
ACCEPT_MIN_P25_CONTRAST = 25.0
ACCEPT_MAX_MEAN_JUMP_PER_FRAME = 3.0
ACCEPT_MAX_JUMP_PER_FRAME = 5.0


@dataclass(frozen=True)
class WindowMetrics:
    start_node: int
    end_node: int
    node_count: int
    span_frame_count: int
    coverage_fraction: float
    first_global_frame_index: int
    last_global_frame_index: int
    mean_jump_per_frame: float
    max_jump_per_frame: float
    median_circularity: float
    p25_circularity: float
    median_contrast: float
    p25_contrast: float
    median_prior_distance: float
    p75_prior_distance: float
    median_area: float

    @property
    def accepted(self) -> bool:
        return (
            self.span_frame_count >= MIN_SEGMENT_SPAN
            and self.coverage_fraction >= ACCEPT_MIN_COVERAGE
            and self.median_circularity >= ACCEPT_MIN_MEDIAN_CIRCULARITY
            and self.p25_circularity >= ACCEPT_MIN_P25_CIRCULARITY
            and self.median_contrast >= ACCEPT_MIN_MEDIAN_CONTRAST
            and self.p25_contrast >= ACCEPT_MIN_P25_CONTRAST
            and self.mean_jump_per_frame <= ACCEPT_MAX_MEAN_JUMP_PER_FRAME
            and self.max_jump_per_frame <= ACCEPT_MAX_JUMP_PER_FRAME
        )


def _eligible(candidate: base.Candidate) -> bool:
    return (
        candidate.circularity >= QUALITY_MIN_CIRCULARITY
        and candidate.contrast >= QUALITY_MIN_CONTRAST
        and candidate.prior_distance <= QUALITY_MAX_PRIOR_DISTANCE
        and candidate.area <= QUALITY_MAX_AREA
    )


def _node_score(candidate: base.Candidate) -> float:
    area_penalty = max(0.0, (candidate.area - 120.0) / 100.0)
    return (
        1.0
        + 0.04 * min(candidate.contrast, 80.0)
        + 0.8 * min(candidate.circularity, 1.2)
        - 0.03 * candidate.prior_distance
        - 0.2 * area_penalty
    )


def _best_strict_path(
    candidates_by_frame: list[list[base.Candidate]],
) -> list[tuple[int, int]]:
    states: dict[tuple[int, int], tuple[float, tuple[int, int] | None]] = {}
    best_end: tuple[int, int] | None = None

    for frame_index, frame_candidates in enumerate(candidates_by_frame):
        for candidate_index, candidate in enumerate(frame_candidates):
            if not _eligible(candidate):
                continue

            best_score = _node_score(candidate)
            predecessor: tuple[int, int] | None = None

            for gap in range(1, MAX_TRACK_GAP + 1):
                previous_frame = frame_index - gap
                if previous_frame < 0:
                    continue

                for previous_index, previous_candidate in enumerate(
                    candidates_by_frame[previous_frame]
                ):
                    state = states.get((previous_frame, previous_index))
                    if state is None:
                        continue

                    jump = hypot(
                        candidate.x - previous_candidate.x,
                        candidate.y - previous_candidate.y,
                    )
                    jump_per_frame = jump / gap
                    if (
                        jump
                        > MAX_JUMP_PER_FRAME * gap + MAX_JUMP_BUFFER
                    ):
                        continue

                    area_change = abs(
                        log(
                            (candidate.area + 1)
                            / (previous_candidate.area + 1)
                        )
                    )
                    score = (
                        state[0]
                        + _node_score(candidate)
                        - 0.35 * jump_per_frame
                        - 0.35 * area_change
                        - 0.75 * (gap - 1)
                    )
                    if score > best_score:
                        best_score = score
                        predecessor = (previous_frame, previous_index)

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


def _window_metrics(
    path: list[tuple[int, int]],
    candidates_by_frame: list[list[base.Candidate]],
    start_node: int,
    end_node: int,
) -> WindowMetrics:
    selected = path[start_node : end_node + 1]
    frames = np.asarray([frame for frame, _ in selected], dtype=int)
    candidates = [
        candidates_by_frame[frame][candidate_index]
        for frame, candidate_index in selected
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

    return WindowMetrics(
        start_node=start_node,
        end_node=end_node,
        node_count=len(selected),
        span_frame_count=span,
        coverage_fraction=float(len(selected) / span),
        first_global_frame_index=int(frames[0]),
        last_global_frame_index=int(frames[-1]),
        mean_jump_per_frame=(
            float(jump_per_frame.mean()) if len(jump_per_frame) else 0.0
        ),
        max_jump_per_frame=(
            float(jump_per_frame.max()) if len(jump_per_frame) else 0.0
        ),
        median_circularity=float(
            np.median([candidate.circularity for candidate in candidates])
        ),
        p25_circularity=float(
            np.quantile(
                [candidate.circularity for candidate in candidates],
                0.25,
            )
        ),
        median_contrast=float(
            np.median([candidate.contrast for candidate in candidates])
        ),
        p25_contrast=float(
            np.quantile(
                [candidate.contrast for candidate in candidates],
                0.25,
            )
        ),
        median_prior_distance=float(
            np.median([candidate.prior_distance for candidate in candidates])
        ),
        p75_prior_distance=float(
            np.quantile(
                [candidate.prior_distance for candidate in candidates],
                0.75,
            )
        ),
        median_area=float(
            np.median([candidate.area for candidate in candidates])
        ),
    )


def _metrics_json(metrics: WindowMetrics) -> dict[str, object]:
    return {
        "nodeCount": metrics.node_count,
        "spanFrameCount": metrics.span_frame_count,
        "coverageFraction": metrics.coverage_fraction,
        "firstGlobalFrameIndex": metrics.first_global_frame_index,
        "lastGlobalFrameIndex": metrics.last_global_frame_index,
        "firstSourceFilename": base._source_filename(
            metrics.first_global_frame_index
        ),
        "lastSourceFilename": base._source_filename(
            metrics.last_global_frame_index
        ),
        "meanJumpPerFrameSourcePixels": metrics.mean_jump_per_frame,
        "maxJumpPerFrameSourcePixels": metrics.max_jump_per_frame,
        "medianCircularity": metrics.median_circularity,
        "p25Circularity": metrics.p25_circularity,
        "medianContrast": metrics.median_contrast,
        "p25Contrast": metrics.p25_contrast,
        "medianPriorDistanceSourcePixels": metrics.median_prior_distance,
        "p75PriorDistanceSourcePixels": metrics.p75_prior_distance,
        "medianAreaPixels": metrics.median_area,
        "acceptedByFixedThresholds": metrics.accepted,
    }


def _scan_windows(
    path: list[tuple[int, int]],
    candidates_by_frame: list[list[base.Candidate]],
) -> list[WindowMetrics]:
    windows: list[WindowMetrics] = []
    for start_node in range(len(path)):
        for end_node in range(start_node, len(path)):
            first_frame = path[start_node][0]
            last_frame = path[end_node][0]
            span = last_frame - first_frame + 1
            if span < MIN_SEGMENT_SPAN:
                continue
            metrics = _window_metrics(
                path,
                candidates_by_frame,
                start_node,
                end_node,
            )
            if metrics.accepted:
                windows.append(metrics)
    windows.sort(
        key=lambda item: (
            item.span_frame_count,
            item.coverage_fraction,
            item.median_contrast,
            item.median_circularity,
        ),
        reverse=True,
    )
    return windows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bone-report", type=Path, required=True)
    parser.add_argument("--atlas-root", type=Path, required=True)
    parser.add_argument("--cryo-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()

    bone_report = json.loads(
        args.bone_report.read_text(encoding="utf-8")
    )
    bone_tracks = base._bone_tracks(bone_report)
    atlas = {
        label: base._read_ascii_ply_vertices(
            args.atlas_root / f"{label}.ply"
        )
        for label in (
            "radius",
            "ulna",
            *base.VESSELS,
        )
    }

    (
        proximal_z,
        distal_z,
        orientation,
        priors,
        diagnostics,
    ) = base._optimize_local_pair_prior(
        args.cryo_root,
        atlas,
        bone_tracks,
    )

    candidates_by_frame: list[list[base.Candidate]] = []
    eligible_counts: list[int] = []

    for global_index in range(base.FRAME_COUNT):
        image = np.asarray(
            Image.open(
                args.cryo_root / base._source_filename(global_index)
            ).convert("RGB")
        )
        candidates = base._extract_candidates(
            image,
            priors["radial_artery"][global_index],
        )
        candidates_by_frame.append(candidates)
        eligible_counts.append(sum(_eligible(candidate) for candidate in candidates))

    path = _best_strict_path(candidates_by_frame)
    windows = _scan_windows(path, candidates_by_frame)

    whole_path_metrics = (
        _window_metrics(path, candidates_by_frame, 0, len(path) - 1)
        if path
        else None
    )

    report = {
        "schema": "ph-a06-radial-bounded-segment-diagnostic.v1",
        "schemaVersion": "1",
        "task": "TASK-A06",
        "recordedAt": "2026-09-09",
        "status": "diagnostic-only",
        "coordinateSpace": {
            "kind": "source-image-stack",
            "patientSpaceClaim": False,
        },
        "fixedRegistration": {
            "method": (
                "existing slice-local radius-ulna pair atlas prior "
                "with source-image support optimization"
            ),
            "proximalAtlasZ": proximal_z,
            "distalAtlasZ": distal_z,
            "orientation": orientation,
            "atlasGeometryUsedAsSubjectGeometry": False,
            "radialAtlasPriorTissueSupport": diagnostics["radial_artery"],
        },
        "fixedThresholds": {
            "candidateMinCircularity": QUALITY_MIN_CIRCULARITY,
            "candidateMinContrast": QUALITY_MIN_CONTRAST,
            "candidateMaxPriorDistanceSourcePixels": QUALITY_MAX_PRIOR_DISTANCE,
            "candidateMaxAreaPixels": QUALITY_MAX_AREA,
            "maxTrackGapFrames": MAX_TRACK_GAP,
            "maxJumpPerFrameSourcePixels": MAX_JUMP_PER_FRAME,
            "acceptedSegmentMinSpanFrames": MIN_SEGMENT_SPAN,
            "acceptedSegmentMinCoverage": ACCEPT_MIN_COVERAGE,
            "acceptedSegmentMinMedianCircularity": ACCEPT_MIN_MEDIAN_CIRCULARITY,
            "acceptedSegmentMinP25Circularity": ACCEPT_MIN_P25_CIRCULARITY,
            "acceptedSegmentMinMedianContrast": ACCEPT_MIN_MEDIAN_CONTRAST,
            "acceptedSegmentMinP25Contrast": ACCEPT_MIN_P25_CONTRAST,
            "acceptedSegmentMaxMeanJumpPerFrameSourcePixels": (
                ACCEPT_MAX_MEAN_JUMP_PER_FRAME
            ),
            "acceptedSegmentMaxJumpPerFrameSourcePixels": (
                ACCEPT_MAX_JUMP_PER_FRAME
            ),
        },
        "candidateAvailability": {
            "supportedFrameCount": base.FRAME_COUNT,
            "framesWithAnyExtractedCandidate": int(
                sum(bool(frame) for frame in candidates_by_frame)
            ),
            "framesWithAnyFixedQualityCandidate": int(
                sum(count > 0 for count in eligible_counts)
            ),
            "totalFixedQualityCandidates": int(sum(eligible_counts)),
        },
        "bestStrictPath": (
            _metrics_json(whole_path_metrics)
            if whole_path_metrics is not None
            else None
        ),
        "acceptedBoundedSegments": [
            _metrics_json(window)
            for window in windows[:20]
        ],
        "decision": {
            "classification": (
                "bounded-continuous-candidate-found"
                if windows
                else "not-established"
            ),
            "acceptedSegmentCount": len(windows),
            "longestAcceptedSpanFrames": (
                windows[0].span_frame_count if windows else 0
            ),
            "automaticPromotionAllowed": False,
        },
        "claims": {
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
    destination = (
        args.output_root
        / "a06-radial-bounded-segment-diagnostic.v0.json"
    )
    destination.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "fixedRegistration": report["fixedRegistration"],
                "candidateAvailability": report["candidateAvailability"],
                "bestStrictPath": report["bestStrictPath"],
                "decision": report["decision"],
                "topAcceptedSegments": report["acceptedBoundedSegments"][:5],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
