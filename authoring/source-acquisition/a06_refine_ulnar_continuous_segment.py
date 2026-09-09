from __future__ import annotations

import argparse
from hashlib import sha256
import json
from math import hypot, log
from pathlib import Path

import numpy as np
from PIL import Image

import a06_detect_vessel_candidates as base


STRICT_JUMP_PER_FRAME = 5.0
STRICT_JUMP_BUFFER = 1.0
STRICT_JUMP_PENALTY = 0.4
STRICT_GAP_PENALTY = 1.0
STRICT_AREA_CHANGE_PENALTY = 0.4
STRICT_PRIOR_PENALTY = 0.03
MAX_STRICT_GAP = 3

RECOVERY_MAX_PRIOR_DISTANCE = 2.0
RECOVERY_MIN_CIRCULARITY = 0.8
RECOVERY_MIN_CONTRAST = 40.0
RECOVERY_MAX_AREA_PIXELS = 100

EXPECTED_FIRST_FRAME = 237
EXPECTED_LAST_FRAME = 342
EXPECTED_FRAME_COUNT = EXPECTED_LAST_FRAME - EXPECTED_FIRST_FRAME + 1


class UlnarContinuousSegmentError(RuntimeError):
    pass


def _strict_node_score(candidate: base.Candidate) -> float:
    area_penalty = max(0.0, (candidate.area - 150) / 100.0)
    return (
        1.0
        + 0.04 * min(candidate.contrast, 80.0)
        + 0.7 * min(candidate.circularity, 1.2)
        - STRICT_PRIOR_PENALTY * candidate.prior_distance
        - 0.25 * area_penalty
    )


def _strict_track(
    candidates_by_frame: list[list[base.Candidate]],
) -> list[tuple[int, int]]:
    states: dict[
        tuple[int, int],
        tuple[float, tuple[int, int] | None],
    ] = {}
    best_end: tuple[int, int] | None = None

    for frame_index, frame_candidates in enumerate(candidates_by_frame):
        for candidate_index, candidate in enumerate(frame_candidates):
            node_score = _strict_node_score(candidate)
            best_score = node_score
            predecessor: tuple[int, int] | None = None

            for gap in range(1, MAX_STRICT_GAP + 1):
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
                    if (
                        jump
                        > STRICT_JUMP_PER_FRAME * gap
                        + STRICT_JUMP_BUFFER
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
                        + node_score
                        - STRICT_JUMP_PENALTY * jump
                        - STRICT_AREA_CHANGE_PENALTY * area_change
                        - STRICT_GAP_PENALTY * (gap - 1)
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
            if (
                best_end is None
                or best_score > states[best_end][0]
            ):
                best_end = (frame_index, candidate_index)

    if best_end is None:
        return []

    path: list[tuple[int, int]] = []
    current: tuple[int, int] | None = best_end
    while current is not None:
        path.append(current)
        current = states[current][1]
    return list(reversed(path))


def _missing_runs(
    first_frame: int,
    last_frame: int,
    selected_frames: set[int],
) -> list[list[int]]:
    missing = [
        frame
        for frame in range(first_frame, last_frame + 1)
        if frame not in selected_frames
    ]
    if not missing:
        return []

    runs: list[list[int]] = []
    current = [missing[0]]
    for frame in missing[1:]:
        if frame == current[-1] + 1:
            current.append(frame)
        else:
            runs.append(current)
            current = [frame]
    runs.append(current)
    return runs


def _recover_single_frame_gap(
    frame_index: int,
    selected: dict[int, base.Candidate],
    candidates_by_frame: list[list[base.Candidate]],
    cryo_root: Path,
) -> base.Candidate:
    previous = frame_index - 1
    following = frame_index + 1
    if previous not in selected or following not in selected:
        raise UlnarContinuousSegmentError(
            f"gap {frame_index} is not bracketed by direct source detections"
        )

    left = selected[previous]
    right = selected[following]
    expected = np.asarray(
        [
            (left.x + right.x) / 2.0,
            (left.y + right.y) / 2.0,
        ],
        dtype=float,
    )

    image = np.asarray(
        Image.open(
            cryo_root / base._source_filename(frame_index)
        ).convert("RGB")
    )
    candidates = base._extract_candidates(image, expected)
    eligible = [
        candidate
        for candidate in candidates
        if candidate.prior_distance <= RECOVERY_MAX_PRIOR_DISTANCE
        and candidate.circularity >= RECOVERY_MIN_CIRCULARITY
        and candidate.contrast >= RECOVERY_MIN_CONTRAST
        and candidate.area <= RECOVERY_MAX_AREA_PIXELS
    ]
    if not eligible:
        raise UlnarContinuousSegmentError(
            f"no high-confidence source candidate recovers frame {frame_index}"
        )

    return min(
        eligible,
        key=lambda candidate: (
            candidate.prior_distance,
            -candidate.contrast,
            -candidate.circularity,
        ),
    )


def _write_pgm(
    path: Path,
    candidate: base.Candidate,
) -> str:
    canvas = np.zeros((750, 550), dtype=np.uint8)
    height, width = candidate.mask.shape
    canvas[
        candidate.y0 : candidate.y0 + height,
        candidate.x0 : candidate.x0 + width,
    ][candidate.mask.astype(bool)] = 255

    payload = b"P5\n550 750\n255\n" + canvas.tobytes()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return sha256(payload).hexdigest()


def _candidate_record(
    frame_index: int,
    candidate: base.Candidate,
    evidence_kind: str,
    mask_path: str,
    mask_sha256: str,
) -> dict[str, object]:
    return {
        "globalFrameIndex": frame_index,
        "sourceFilename": base._source_filename(frame_index),
        "centroidSourcePixels": {
            "x": candidate.x,
            "y": candidate.y,
        },
        "areaPixels": candidate.area,
        "circularity": candidate.circularity,
        "contrast": candidate.contrast,
        "atlasPriorDistanceSourcePixels": candidate.prior_distance,
        "evidenceKind": evidence_kind,
        "maskPath": mask_path,
        "maskSha256": mask_sha256,
    }


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
    for global_index in range(base.FRAME_COUNT):
        image = np.asarray(
            Image.open(
                args.cryo_root / base._source_filename(global_index)
            ).convert("RGB")
        )
        candidates_by_frame.append(
            base._extract_candidates(
                image,
                priors["ulnar_artery"][global_index],
            )
        )

    path = _strict_track(candidates_by_frame)
    metrics = base._track_metrics(path, candidates_by_frame)
    if metrics is None:
        raise UlnarContinuousSegmentError(
            "strict ulnar track was not established"
        )

    if (
        metrics.first_global_frame_index != EXPECTED_FIRST_FRAME
        or metrics.last_global_frame_index != EXPECTED_LAST_FRAME
        or metrics.span_frame_count != EXPECTED_FRAME_COUNT
        or metrics.coverage_fraction < 0.95
        or metrics.max_jump_pixels > 6.0
        or metrics.median_circularity < 0.90
        or metrics.p25_circularity < 0.70
        or metrics.median_contrast < 55.0
        or metrics.p25_contrast < 45.0
    ):
        raise UlnarContinuousSegmentError(
            "strict source-supported segment does not meet continuity thresholds"
        )

    selected = {
        frame_index: candidates_by_frame[frame_index][candidate_index]
        for frame_index, candidate_index in path
    }
    direct_frames = set(selected)
    gap_runs = _missing_runs(
        EXPECTED_FIRST_FRAME,
        EXPECTED_LAST_FRAME,
        direct_frames,
    )
    if any(len(run) != 1 for run in gap_runs):
        raise UlnarContinuousSegmentError(
            f"only isolated one-frame gaps may be source-recovered: {gap_runs}"
        )

    recovered_frames: list[int] = []
    for run in gap_runs:
        frame_index = run[0]
        recovered = _recover_single_frame_gap(
            frame_index,
            selected,
            candidates_by_frame,
            args.cryo_root,
        )
        selected[frame_index] = recovered
        recovered_frames.append(frame_index)

    if set(selected) != set(
        range(EXPECTED_FIRST_FRAME, EXPECTED_LAST_FRAME + 1)
    ):
        raise UlnarContinuousSegmentError(
            "continuous segment still contains unsupported frame gaps"
        )

    ordered = [
        selected[frame]
        for frame in range(
            EXPECTED_FIRST_FRAME,
            EXPECTED_LAST_FRAME + 1,
        )
    ]
    jumps = np.asarray(
        [
            hypot(right.x - left.x, right.y - left.y)
            for left, right in zip(ordered[:-1], ordered[1:])
        ],
        dtype=float,
    )
    circularity = np.asarray(
        [candidate.circularity for candidate in ordered],
        dtype=float,
    )
    contrast = np.asarray(
        [candidate.contrast for candidate in ordered],
        dtype=float,
    )

    final_metrics = {
        "frameCount": len(ordered),
        "firstGlobalFrameIndex": EXPECTED_FIRST_FRAME,
        "lastGlobalFrameIndex": EXPECTED_LAST_FRAME,
        "firstSourceFilename": base._source_filename(EXPECTED_FIRST_FRAME),
        "lastSourceFilename": base._source_filename(EXPECTED_LAST_FRAME),
        "directDetectionFrameCount": len(direct_frames),
        "sourceRecoveredGapFrameCount": len(recovered_frames),
        "sourceRecoveredGapFrames": recovered_frames,
        "coverageFraction": 1.0,
        "meanJumpSourcePixels": float(jumps.mean()),
        "maxJumpSourcePixels": float(jumps.max()),
        "medianCircularity": float(np.median(circularity)),
        "p25Circularity": float(np.quantile(circularity, 0.25)),
        "medianContrast": float(np.median(contrast)),
        "p25Contrast": float(np.quantile(contrast, 0.25)),
        "minimumContrast": float(contrast.min()),
    }

    if (
        final_metrics["frameCount"] != EXPECTED_FRAME_COUNT
        or final_metrics["maxJumpSourcePixels"] > 6.0
        or final_metrics["medianCircularity"] < 0.90
        or final_metrics["p25Circularity"] < 0.70
        or final_metrics["medianContrast"] < 55.0
        or final_metrics["p25Contrast"] < 45.0
        or final_metrics["minimumContrast"] < 25.0
    ):
        raise UlnarContinuousSegmentError(
            "recovered segment failed final source-evidence thresholds"
        )

    mask_records: list[dict[str, object]] = []
    centerline_points: list[dict[str, object]] = []
    for frame_index in range(
        EXPECTED_FIRST_FRAME,
        EXPECTED_LAST_FRAME + 1,
    ):
        candidate = selected[frame_index]
        evidence_kind = (
            "source-recovered-isolated-gap"
            if frame_index in recovered_frames
            else "strict-source-detection"
        )
        filename = base._source_filename(frame_index)
        target = (
            args.output_root
            / "masks"
            / "ulnar_artery"
            / f"{Path(filename).stem}.pgm"
        )
        digest = _write_pgm(target, candidate)
        record = _candidate_record(
            frame_index,
            candidate,
            evidence_kind,
            str(target.relative_to(args.output_root)),
            digest,
        )
        mask_records.append(record)
        centerline_points.append(
            {
                "globalFrameIndex": frame_index,
                "sourceFilename": filename,
                "xSourcePixels": candidate.x,
                "ySourcePixels": candidate.y,
                "evidenceKind": evidence_kind,
            }
        )

    report = {
        "schema": "ph-a06-ulnar-continuous-segment-report.v1",
        "schemaVersion": "1",
        "task": "TASK-A06",
        "recordedAt": "2026-09-09",
        "classification": "continuous-candidate",
        "anatomicalId": "structure.ulnar_artery.left",
        "coordinateSpace": {
            "kind": "source-image-stack",
            "patientSpaceClaim": False,
        },
        "registration": {
            "method": (
                "slice-local radius-ulna pair atlas prior "
                "with source-image support optimization"
            ),
            "proximalAtlasZ": proximal_z,
            "distalAtlasZ": distal_z,
            "orientation": orientation,
            "atlasGeometryUsedAsSubjectGeometry": False,
            "atlasPriorTissueSupport": diagnostics["ulnar_artery"],
        },
        "strictTrackBeforeRecovery": {
            "nodeCount": metrics.node_count,
            "spanFrameCount": metrics.span_frame_count,
            "coverageFraction": metrics.coverage_fraction,
            "firstGlobalFrameIndex": metrics.first_global_frame_index,
            "lastGlobalFrameIndex": metrics.last_global_frame_index,
            "meanJumpSourcePixels": metrics.mean_jump_pixels,
            "maxJumpSourcePixels": metrics.max_jump_pixels,
            "medianCircularity": metrics.median_circularity,
            "p25Circularity": metrics.p25_circularity,
            "medianContrast": metrics.median_contrast,
            "p25Contrast": metrics.p25_contrast,
        },
        "continuousSegment": final_metrics,
        "maskFrameCount": len(mask_records),
        "maskFiles": mask_records,
        "claims": {
            "humanEdited": False,
            "anatomicallyReviewed": False,
            "medicalValidation": False,
            "completeUlnarArteryExtent": False,
            "continuousCandidateWithinBoundedSegment": True,
            "patientSpaceGeometry": False,
            "automaticPromotionAllowed": False,
        },
    }

    centerline = {
        "schema": "ph-a08-source-stack-centerline-candidate.v1",
        "schemaVersion": "1",
        "task": "TASK-A08",
        "recordedAt": "2026-09-09",
        "anatomicalId": "structure.ulnar_artery.left",
        "status": "generated-v0-candidate",
        "coordinateSpace": {
            "kind": "source-image-stack",
            "patientSpaceClaim": False,
            "nominalSliceIntervalMm": 0.33,
            "physicalXyClaim": False,
        },
        "support": {
            "firstGlobalFrameIndex": EXPECTED_FIRST_FRAME,
            "lastGlobalFrameIndex": EXPECTED_LAST_FRAME,
            "firstSourceFilename": base._source_filename(EXPECTED_FIRST_FRAME),
            "lastSourceFilename": base._source_filename(EXPECTED_LAST_FRAME),
            "pointCount": len(centerline_points),
            "completeVesselExtentClaim": False,
        },
        "points": centerline_points,
        "lineage": {
            "sourceReport": "a06-ulnar-continuous-segment-report.v0.json",
            "pointDerivation": (
                "mask centroid on every source frame in bounded continuous segment"
            ),
        },
        "claims": {
            "medicalValidation": False,
            "patientSpaceGeometry": False,
            "runtimeCenterline": False,
            "automaticPromotionAllowed": False,
        },
    }

    args.output_root.mkdir(parents=True, exist_ok=True)
    (
        args.output_root
        / "a06-ulnar-continuous-segment-report.v0.json"
    ).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (
        args.output_root
        / "a08-ulnar-source-stack-centerline-v0.json"
    ).write_text(
        json.dumps(centerline, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "classification": report["classification"],
                "continuousSegment": final_metrics,
                "strictTrackBeforeRecovery": report[
                    "strictTrackBeforeRecovery"
                ],
                "centerlinePointCount": len(centerline_points),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
