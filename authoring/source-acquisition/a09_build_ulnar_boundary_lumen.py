from __future__ import annotations

import argparse
from hashlib import sha256
import json
from math import hypot
from pathlib import Path
import shutil

import cv2
import numpy as np
from PIL import Image


EXPECTED_FRAME_COUNT = 106
EXPECTED_FIRST_GLOBAL_FRAME = 237
EXPECTED_LAST_GLOBAL_FRAME = 342
EXPECTED_FIRST_SOURCE = "avf1646a.png"
EXPECTED_LAST_SOURCE = "avf1681a.png"


class BoundaryLumenCandidateError(RuntimeError):
    pass


def _sha256_path(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_binary_mask(path: Path) -> np.ndarray:
    image = np.asarray(Image.open(path).convert("L"))
    if image.shape != (750, 550):
        raise BoundaryLumenCandidateError(
            f"{path.name} has unexpected dimensions {image.shape}"
        )
    mask = image > 0
    if not bool(mask.any()):
        raise BoundaryLumenCandidateError(f"{path.name} lumen mask is empty")
    return mask


def _single_outer_contour(mask: np.ndarray) -> np.ndarray:
    count, labels = cv2.connectedComponents(mask.astype(np.uint8), connectivity=8)
    if count != 2:
        raise BoundaryLumenCandidateError(
            f"expected exactly one connected lumen component, got {count - 1}"
        )

    contours, hierarchy = cv2.findContours(
        mask.astype(np.uint8),
        cv2.RETR_CCOMP,
        cv2.CHAIN_APPROX_NONE,
    )
    if not contours or hierarchy is None:
        raise BoundaryLumenCandidateError("no lumen boundary contour found")

    hierarchy_rows = hierarchy[0]
    outer_indices = [
        index
        for index, row in enumerate(hierarchy_rows)
        if int(row[3]) == -1
    ]
    if len(outer_indices) != 1:
        raise BoundaryLumenCandidateError(
            f"expected one outer lumen contour, got {len(outer_indices)}"
        )

    contour = contours[outer_indices[0]][:, 0, :]
    if len(contour) < 4:
        raise BoundaryLumenCandidateError("lumen boundary contour is degenerate")
    return contour.astype(int)


def _write_boundary_mask(path: Path, mask: np.ndarray) -> str:
    eroded = cv2.erode(
        mask.astype(np.uint8),
        np.ones((3, 3), dtype=np.uint8),
        iterations=1,
    ).astype(bool)
    boundary = mask & ~eroded
    if not bool(boundary.any()):
        raise BoundaryLumenCandidateError("derived lumen boundary mask is empty")

    payload = (boundary.astype(np.uint8) * 255)
    path.parent.mkdir(parents=True, exist_ok=True)
    header = b"P5\n550 750\n255\n"
    path.write_bytes(header + payload.tobytes())
    return _sha256_path(path)


def _interior_center(mask: np.ndarray) -> tuple[float, float, float]:
    distance = cv2.distanceTransform(
        mask.astype(np.uint8),
        cv2.DIST_L2,
        5,
    )
    flat_index = int(np.argmax(distance))
    y, x = np.unravel_index(flat_index, distance.shape)
    clearance = float(distance[y, x])
    if clearance <= 0 or not bool(mask[y, x]):
        raise BoundaryLumenCandidateError(
            "failed to derive an interior lumen center"
        )
    return float(x), float(y), clearance


def _frame_metrics(mask: np.ndarray, contour: np.ndarray) -> dict[str, float | int]:
    area = int(mask.sum())
    perimeter = float(cv2.arcLength(contour[:, None, :].astype(np.int32), True))
    equivalent_radius = float(np.sqrt(area / np.pi))
    return {
        "lumenAreaPixels": area,
        "boundaryPointCount": int(len(contour)),
        "boundaryPerimeterPixels": perimeter,
        "equivalentLumenRadiusPixels": equivalent_radius,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--continuous-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()

    report_path = (
        args.continuous_root
        / "a06-ulnar-continuous-segment-report.v0.json"
    )
    centerline_path = (
        args.continuous_root
        / "a08-ulnar-source-stack-centerline-v0.json"
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    centerline = json.loads(centerline_path.read_text(encoding="utf-8"))

    segment = report["continuousSegment"]
    if (
        report["classification"] != "continuous-candidate"
        or segment["frameCount"] != EXPECTED_FRAME_COUNT
        or segment["firstGlobalFrameIndex"] != EXPECTED_FIRST_GLOBAL_FRAME
        or segment["lastGlobalFrameIndex"] != EXPECTED_LAST_GLOBAL_FRAME
        or segment["firstSourceFilename"] != EXPECTED_FIRST_SOURCE
        or segment["lastSourceFilename"] != EXPECTED_LAST_SOURCE
    ):
        raise BoundaryLumenCandidateError(
            "continuous ulnar source segment does not match the bounded A09 input contract"
        )

    points_by_frame = {
        int(point["globalFrameIndex"]): point
        for point in centerline["points"]
    }
    if len(points_by_frame) != EXPECTED_FRAME_COUNT:
        raise BoundaryLumenCandidateError(
            "centerline point count does not match continuous segment"
        )

    output_frames: list[dict[str, object]] = []
    corrected_centerline_points: list[dict[str, object]] = []
    input_centerline_outside_frames: list[int] = []
    input_to_corrected_distances: list[float] = []

    for mask_record in report["maskFiles"]:
        frame_index = int(mask_record["globalFrameIndex"])
        source_filename = str(mask_record["sourceFilename"])
        source_mask_path = (
            args.continuous_root / str(mask_record["maskPath"])
        )
        mask = _load_binary_mask(source_mask_path)
        contour = _single_outer_contour(mask)

        centerline_point = points_by_frame.get(frame_index)
        if centerline_point is None:
            raise BoundaryLumenCandidateError(
                f"centerline point missing for frame {frame_index}"
            )

        input_x = float(centerline_point["xSourcePixels"])
        input_y = float(centerline_point["ySourcePixels"])
        input_xi = int(round(input_x))
        input_yi = int(round(input_y))
        if not (0 <= input_xi < 550 and 0 <= input_yi < 750):
            raise BoundaryLumenCandidateError(
                f"input centerline point leaves source crop at frame {frame_index}"
            )
        input_centerline_inside = bool(mask[input_yi, input_xi])
        if not input_centerline_inside:
            input_centerline_outside_frames.append(frame_index)

        corrected_x, corrected_y, corrected_clearance = _interior_center(mask)
        corrected_xi = int(round(corrected_x))
        corrected_yi = int(round(corrected_y))
        if not bool(mask[corrected_yi, corrected_xi]):
            raise BoundaryLumenCandidateError(
                f"corrected centerline point is outside lumen candidate at frame {frame_index}"
            )
        input_to_corrected_distance = hypot(
            corrected_x - input_x,
            corrected_y - input_y,
        )
        input_to_corrected_distances.append(input_to_corrected_distance)
        if input_to_corrected_distance > 10.0:
            raise BoundaryLumenCandidateError(
                f"lumen-centered correction exceeds 10 source pixels at frame {frame_index}: "
                f"{input_to_corrected_distance:.3f}"
            )

        lumen_target = (
            args.output_root
            / "lumen"
            / "ulnar_artery"
            / f"{Path(source_filename).stem}.pgm"
        )
        lumen_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_mask_path, lumen_target)
        lumen_digest = _sha256_path(lumen_target)

        if lumen_digest != str(mask_record["maskSha256"]):
            raise BoundaryLumenCandidateError(
                f"lumen mask hash changed while copying {source_filename}"
            )

        boundary_target = (
            args.output_root
            / "boundary"
            / "ulnar_artery"
            / f"{Path(source_filename).stem}.pgm"
        )
        boundary_digest = _write_boundary_mask(boundary_target, mask)

        metrics = _frame_metrics(mask, contour)
        output_frames.append(
            {
                "globalFrameIndex": frame_index,
                "sourceFilename": source_filename,
                "evidenceKind": mask_record["evidenceKind"],
                "lumenMaskPath": str(
                    lumen_target.relative_to(args.output_root)
                ),
                "lumenMaskSha256": lumen_digest,
                "boundaryMaskPath": str(
                    boundary_target.relative_to(args.output_root)
                ),
                "boundaryMaskSha256": boundary_digest,
                "outsideRegionDefinition": (
                    "source-crop complement of lumen candidate mask"
                ),
                "inputCenterlinePointInsideLumen": input_centerline_inside,
                "correctedCenterlinePointInsideLumen": True,
                "correctedCenterlineSourcePixels": {
                    "x": corrected_x,
                    "y": corrected_y,
                },
                "correctedCenterlineClearancePixels": corrected_clearance,
                "inputToCorrectedCenterlineDistancePixels": (
                    input_to_corrected_distance
                ),
                **metrics,
            }
        )
        corrected_centerline_points.append(
            {
                "globalFrameIndex": frame_index,
                "sourceFilename": source_filename,
                "xSourcePixels": corrected_x,
                "ySourcePixels": corrected_y,
                "evidenceKind": mask_record["evidenceKind"],
            }
        )

    output_frames.sort(key=lambda row: int(row["globalFrameIndex"]))
    if [
        int(row["globalFrameIndex"]) for row in output_frames
    ] != list(
        range(EXPECTED_FIRST_GLOBAL_FRAME, EXPECTED_LAST_GLOBAL_FRAME + 1)
    ):
        raise BoundaryLumenCandidateError(
            "A09 frame coverage is not exactly consecutive over the bounded segment"
        )

    lumen_areas = np.asarray(
        [int(row["lumenAreaPixels"]) for row in output_frames],
        dtype=float,
    )
    radii = np.asarray(
        [float(row["equivalentLumenRadiusPixels"]) for row in output_frames],
        dtype=float,
    )
    perimeter = np.asarray(
        [float(row["boundaryPerimeterPixels"]) for row in output_frames],
        dtype=float,
    )

    corrected_centerline_points.sort(
        key=lambda row: int(row["globalFrameIndex"])
    )
    if [
        int(row["globalFrameIndex"]) for row in corrected_centerline_points
    ] != list(
        range(EXPECTED_FIRST_GLOBAL_FRAME, EXPECTED_LAST_GLOBAL_FRAME + 1)
    ):
        raise BoundaryLumenCandidateError(
            "corrected centerline does not cover the exact bounded segment"
        )

    centerline_jumps = np.asarray(
        [
            hypot(
                float(right["xSourcePixels"]) - float(left["xSourcePixels"]),
                float(right["ySourcePixels"]) - float(left["ySourcePixels"]),
            )
            for left, right in zip(
                corrected_centerline_points[:-1],
                corrected_centerline_points[1:],
            )
        ],
        dtype=float,
    )
    if float(centerline_jumps.max()) > 6.0:
        raise BoundaryLumenCandidateError(
            f"corrected lumen-centered centerline jump exceeds 6 pixels: "
            f"{float(centerline_jumps.max()):.3f}"
        )

    result = {
        "schema": "ph-a09-boundary-lumen-candidate.v1",
        "schemaVersion": "1",
        "task": "TASK-A09",
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
            "firstGlobalFrameIndex": EXPECTED_FIRST_GLOBAL_FRAME,
            "lastGlobalFrameIndex": EXPECTED_LAST_GLOBAL_FRAME,
            "firstSourceFilename": EXPECTED_FIRST_SOURCE,
            "lastSourceFilename": EXPECTED_LAST_SOURCE,
            "frameCount": EXPECTED_FRAME_COUNT,
            "completeVesselExtentClaim": False,
        },
        "semantics": {
            "lumenRegion": (
                "V0 source-image dark-component lumen candidate mask"
            ),
            "outsideRegion": (
                "source-crop complement of lumen candidate mask"
            ),
            "wallBoundary": (
                "topological interface between candidate lumen and outside; "
                "does not represent anatomical wall thickness"
            ),
            "anatomicalWallThicknessClaim": False,
        },
        "topologyValidation": {
            "singleConnectedLumenComponentEveryFrame": True,
            "closedOuterBoundaryEveryFrame": True,
            "correctedCenterlinePointInsideLumenEveryFrame": True,
            "consecutiveFrameCoverage": True,
        },
        "sourceCenterlineDiagnostic": {
            "inputCenterlineOutsideLumenFrameCount": len(
                input_centerline_outside_frames
            ),
            "inputCenterlineOutsideLumenFrames": (
                input_centerline_outside_frames
            ),
            "maxInputToCorrectedCenterlineDistancePixels": float(
                max(input_to_corrected_distances)
            ),
            "meanInputToCorrectedCenterlineDistancePixels": float(
                np.mean(input_to_corrected_distances)
            ),
            "maxCorrectedCenterlineJumpPixels": float(
                centerline_jumps.max()
            ),
            "meanCorrectedCenterlineJumpPixels": float(
                centerline_jumps.mean()
            ),
        },
        "summary": {
            "medianLumenAreaPixels": float(np.median(lumen_areas)),
            "minLumenAreaPixels": int(lumen_areas.min()),
            "maxLumenAreaPixels": int(lumen_areas.max()),
            "medianEquivalentLumenRadiusPixels": float(np.median(radii)),
            "minEquivalentLumenRadiusPixels": float(radii.min()),
            "maxEquivalentLumenRadiusPixels": float(radii.max()),
            "medianBoundaryPerimeterPixels": float(np.median(perimeter)),
        },
        "frames": output_frames,
        "lineage": {
            "sourceContinuousSegmentReport": (
                "a06-ulnar-continuous-segment-report.v0.json"
            ),
            "sourceCenterlineCandidate": (
                "a08-ulnar-source-stack-centerline-v0.json"
            ),
            "correctedCenterlineCandidate": (
                "a08-ulnar-lumen-centered-source-stack-centerline-v0.json"
            ),
            "derivation": (
                "lumen candidate is copied byte-for-byte from the bounded "
                "continuous A06 mask; boundary is a reproducible 1-pixel "
                "inner morphological edge; outside is defined as its "
                "source-crop complement; a corrected A08 centerline is "
                "derived as the maximum Euclidean distance-to-boundary "
                "point inside each lumen mask"
            ),
        },
        "claims": {
            "humanEdited": False,
            "anatomicallyReviewed": False,
            "medicalValidation": False,
            "completeVesselExtent": False,
            "anatomicalWallThickness": False,
            "patientSpaceGeometry": False,
            "runtimeRepresentation": False,
            "automaticPromotionAllowed": False,
        },
    }

    corrected_centerline = {
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
            "firstGlobalFrameIndex": EXPECTED_FIRST_GLOBAL_FRAME,
            "lastGlobalFrameIndex": EXPECTED_LAST_GLOBAL_FRAME,
            "firstSourceFilename": EXPECTED_FIRST_SOURCE,
            "lastSourceFilename": EXPECTED_LAST_SOURCE,
            "pointCount": EXPECTED_FRAME_COUNT,
            "completeVesselExtentClaim": False,
        },
        "points": corrected_centerline_points,
        "lineage": {
            "sourceReport": "a06-ulnar-continuous-segment-report.v0.json",
            "pointDerivation": (
                "maximum Euclidean distance-to-boundary point inside each "
                "bounded A06 lumen candidate mask; supersedes raw mask-centroid "
                "points for lumen-membership topology"
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
        / "a08-ulnar-lumen-centered-source-stack-centerline-v0.json"
    ).write_text(
        json.dumps(corrected_centerline, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    destination = (
        args.output_root / "a09-ulnar-boundary-lumen-v0.json"
    )
    destination.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "status": result["status"],
                "support": result["support"],
                "topologyValidation": result["topologyValidation"],
                "summary": result["summary"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
