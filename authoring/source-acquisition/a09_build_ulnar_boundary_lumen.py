from __future__ import annotations

import argparse
from hashlib import sha256
import json
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
    centroid_inside_count = 0

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

        x = float(centerline_point["xSourcePixels"])
        y = float(centerline_point["ySourcePixels"])
        xi = int(round(x))
        yi = int(round(y))
        if not (0 <= xi < 550 and 0 <= yi < 750):
            raise BoundaryLumenCandidateError(
                f"centerline point leaves source crop at frame {frame_index}"
            )
        centerline_inside = bool(mask[yi, xi])
        if centerline_inside:
            centroid_inside_count += 1
        else:
            raise BoundaryLumenCandidateError(
                f"centerline point is outside lumen candidate at frame {frame_index}"
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
                "centerlinePointInsideLumen": centerline_inside,
                **metrics,
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
            "centerlinePointInsideLumenEveryFrame": (
                centroid_inside_count == EXPECTED_FRAME_COUNT
            ),
            "consecutiveFrameCoverage": True,
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
            "derivation": (
                "lumen candidate is copied byte-for-byte from the bounded "
                "continuous A06 mask; boundary is a reproducible 1-pixel "
                "inner morphological edge; outside is defined as its "
                "source-crop complement"
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

    args.output_root.mkdir(parents=True, exist_ok=True)
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
