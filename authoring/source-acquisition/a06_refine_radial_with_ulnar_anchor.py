from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

import a06_detect_vessel_candidates as base
import a06_refine_radial_source_diagnostic as radial


SMOOTHING_HALF_WINDOW = 4


class RadialUlnarAnchorDiagnosticError(RuntimeError):
    pass


def _rolling_median(values: np.ndarray, half_window: int) -> np.ndarray:
    if values.ndim != 2 or values.shape[1] != 2:
        raise RadialUlnarAnchorDiagnosticError(
            "residual correction values must be Nx2"
        )
    output = np.zeros_like(values, dtype=float)
    for index in range(len(values)):
        start = max(0, index - half_window)
        stop = min(len(values), index + half_window + 1)
        output[index] = np.median(values[start:stop], axis=0)
    return output


def _ulnar_source_points(
    report: dict[str, object],
) -> tuple[np.ndarray, np.ndarray]:
    if report.get("anatomicalId") != "structure.ulnar_artery.left":
        raise RadialUlnarAnchorDiagnosticError(
            "ulnar source report has unexpected anatomicalId"
        )

    coordinate_space = report.get("coordinateSpace")
    if (
        not isinstance(coordinate_space, dict)
        or coordinate_space.get("kind") != "source-image-stack"
        or coordinate_space.get("patientSpaceClaim") is not False
    ):
        raise RadialUlnarAnchorDiagnosticError(
            "ulnar source report must remain source-image-stack only"
        )

    rows = report.get("maskFiles")
    if not isinstance(rows, list) or not rows:
        raise RadialUlnarAnchorDiagnosticError(
            "ulnar source report has no mask evidence rows"
        )

    frames: list[int] = []
    points: list[list[float]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise RadialUlnarAnchorDiagnosticError(
                "invalid ulnar mask evidence row"
            )
        frame = row.get("globalFrameIndex")
        centroid = row.get("centroidSourcePixels")
        if not isinstance(frame, int) or not isinstance(centroid, dict):
            raise RadialUlnarAnchorDiagnosticError(
                "ulnar mask evidence row lacks source centroid"
            )
        frames.append(frame)
        points.append(
            [float(centroid["x"]), float(centroid["y"])]
        )

    frame_array = np.asarray(frames, dtype=int)
    point_array = np.asarray(points, dtype=float)
    if (
        len(frame_array) != 106
        or frame_array[0] != 237
        or frame_array[-1] != 342
        or not np.array_equal(
            frame_array,
            np.arange(frame_array[0], frame_array[-1] + 1),
        )
        or point_array.shape != (106, 2)
        or not np.isfinite(point_array).all()
    ):
        raise RadialUlnarAnchorDiagnosticError(
            "ulnar source anchor must be the verified 106-frame bounded segment"
        )

    return frame_array, point_array


def _correction_statistics(
    raw_residuals: np.ndarray,
    smoothed_residuals: np.ndarray,
) -> dict[str, object]:
    raw_norm = np.linalg.norm(raw_residuals, axis=1)
    smooth_norm = np.linalg.norm(smoothed_residuals, axis=1)
    roughness = np.linalg.norm(
        smoothed_residuals[1:] - smoothed_residuals[:-1],
        axis=1,
    )
    return {
        "frameCount": int(len(raw_residuals)),
        "rawResidualMedianSourcePixels": float(np.median(raw_norm)),
        "rawResidualP90SourcePixels": float(np.quantile(raw_norm, 0.9)),
        "rawResidualMaximumSourcePixels": float(raw_norm.max()),
        "smoothedCorrectionMedianSourcePixels": float(np.median(smooth_norm)),
        "smoothedCorrectionP90SourcePixels": float(
            np.quantile(smooth_norm, 0.9)
        ),
        "smoothedCorrectionMaximumSourcePixels": float(smooth_norm.max()),
        "smoothedStepMedianSourcePixels": float(np.median(roughness)),
        "smoothedStepMaximumSourcePixels": float(roughness.max()),
    }


def _promotion_diagnostic(
    tier_results: list[dict[str, object]],
) -> dict[str, object]:
    qualifying: list[dict[str, object]] = []
    for tier_result in tier_results:
        tier = tier_result["tier"]
        if not isinstance(tier, dict):
            continue
        for segment in tier_result["strictSegments"]:
            if not isinstance(segment, dict):
                continue
            metrics = segment.get("metrics")
            if not isinstance(metrics, dict):
                continue
            if (
                int(metrics["spanFrameCount"]) >= 24
                and int(metrics["nodeCount"]) >= 20
                and float(metrics["coverageFraction"]) >= 0.80
                and float(metrics["maxJumpSourcePixels"]) <= 6.0
                and float(metrics["medianCircularity"]) >= 0.40
                and float(metrics["medianContrast"]) >= 15.0
                and float(metrics["meanPriorDistanceSourcePixels"]) <= 20.0
            ):
                qualifying.append(
                    {
                        "tier": str(tier["name"]),
                        "metrics": metrics,
                    }
                )
    return {
        "boundedSegmentWorthDedicatedSourceBuilder": bool(qualifying),
        "qualifyingSegments": qualifying[:5],
        "automaticPromotionAllowed": False,
        "note": (
            "This is a diagnostic trigger for a dedicated fail-closed "
            "source builder, not an anatomical or medical validation claim."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bone-report", type=Path, required=True)
    parser.add_argument("--atlas-root", type=Path, required=True)
    parser.add_argument("--cryo-root", type=Path, required=True)
    parser.add_argument("--ulnar-report", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()

    bone_report = json.loads(
        args.bone_report.read_text(encoding="utf-8")
    )
    ulnar_report = json.loads(
        args.ulnar_report.read_text(encoding="utf-8")
    )
    frame_indices, source_ulnar_points = _ulnar_source_points(
        ulnar_report
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

    atlas_ulnar_points = priors["ulnar_artery"][frame_indices]
    raw_residuals = source_ulnar_points - atlas_ulnar_points
    smoothed_residuals = _rolling_median(
        raw_residuals,
        SMOOTHING_HALF_WINDOW,
    )
    corrected_radial_priors = (
        priors["radial_artery"][frame_indices]
        + smoothed_residuals
    )

    raw_candidates: list[list[base.Candidate]] = [
        [] for _ in range(base.FRAME_COUNT)
    ]
    for local_index, global_index in enumerate(frame_indices):
        image = np.asarray(
            Image.open(
                args.cryo_root / base._source_filename(int(global_index))
            ).convert("RGB")
        )
        raw_candidates[int(global_index)] = base._extract_candidates(
            image,
            corrected_radial_priors[local_index],
        )

    tier_results: list[dict[str, object]] = []
    for tier in radial.QUALITY_TIERS:
        candidates = radial._filtered(raw_candidates, tier)
        path = base._best_track(candidates)
        tier_results.append(
            {
                "tier": tier,
                "framesWithCandidate": int(
                    sum(bool(frame) for frame in candidates)
                ),
                "candidateCount": int(
                    sum(len(frame) for frame in candidates)
                ),
                "trackMetrics": radial._metrics_json(
                    path,
                    candidates,
                ),
                "pathNodes": radial._path_nodes(
                    path,
                    candidates,
                ),
                "strictSegments": radial._segment_summaries(
                    path,
                    candidates,
                ),
            }
        )

    report = {
        "schema": "ph-a06-radial-ulnar-anchor-diagnostic.v1",
        "schemaVersion": "1",
        "task": "TASK-A06",
        "recordedAt": "2026-09-09",
        "anatomicalId": "structure.radial_artery.left",
        "coordinateSpace": {
            "kind": "source-image-stack",
            "patientSpaceClaim": False,
        },
        "registration": {
            "baseMethod": (
                "slice-local radius-ulna pair atlas prior with "
                "VHP source-image candidate extraction"
            ),
            "localCorrectionMethod": (
                "per-slice translation residual from verified bounded "
                "source-supported ulnar artery centroid to mapped atlas "
                "ulnar artery prior, rolling-median smoothed and applied "
                "to the mapped radial artery prior"
            ),
            "proximalAtlasZ": proximal_z,
            "distalAtlasZ": distal_z,
            "orientation": orientation,
            "smoothingWindowFrameCount": 2 * SMOOTHING_HALF_WINDOW + 1,
            "atlasGeometryUsedAsSubjectGeometry": False,
            "ulnarAnchorAnatomicalId": "structure.ulnar_artery.left",
            "ulnarAnchorFirstGlobalFrameIndex": int(frame_indices[0]),
            "ulnarAnchorLastGlobalFrameIndex": int(frame_indices[-1]),
            "ulnarAnchorFrameCount": int(len(frame_indices)),
            "ulnarAtlasPriorTissueSupport": diagnostics["ulnar_artery"],
            "radialAtlasPriorTissueSupport": diagnostics["radial_artery"],
            "correctionStatistics": _correction_statistics(
                raw_residuals,
                smoothed_residuals,
            ),
        },
        "tiers": tier_results,
        "promotionDiagnostic": _promotion_diagnostic(tier_results),
        "disposition": {
            "radialArteryRepresentationEstablished": False,
            "maskGenerationAllowed": False,
            "reason": (
                "third-anchor registration diagnostic only; a dedicated "
                "bounded source builder with explicit continuity and "
                "image-quality gates is required before accepting masks"
            ),
        },
        "claims": {
            "humanEdited": False,
            "anatomicallyReviewed": False,
            "medicalValidation": False,
            "completeVesselExtent": False,
            "patientSpaceGeometry": False,
            "automaticPromotionAllowed": False,
        },
    }

    args.output_root.mkdir(parents=True, exist_ok=True)
    target = (
        args.output_root
        / "a06-radial-ulnar-anchor-diagnostic.v0.json"
    )
    target.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "registration": report["registration"],
                "tiers": [
                    {
                        "tier": row["tier"],
                        "framesWithCandidate": row[
                            "framesWithCandidate"
                        ],
                        "candidateCount": row["candidateCount"],
                        "trackMetrics": row["trackMetrics"],
                        "strictSegments": row["strictSegments"][:3],
                    }
                    for row in tier_results
                ],
                "promotionDiagnostic": report[
                    "promotionDiagnostic"
                ],
                "disposition": report["disposition"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
