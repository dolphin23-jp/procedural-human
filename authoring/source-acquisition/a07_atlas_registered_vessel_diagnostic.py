from __future__ import annotations

import argparse
import json
from math import hypot
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

import a06_detect_vessel_candidates as base


FRAME_COUNT = 357
PROXIMAL_ATLAS_Z_CANDIDATES = (0.95, 0.955, 0.96, 0.965)
DISTAL_ATLAS_Z_CANDIDATES = (0.875, 0.88, 0.885)
CALIBRATION_FIRST = 237
CALIBRATION_LAST = 289
VALIDATION_FIRST = 290
VALIDATION_LAST = 342
SUPPORT_FIRST = 237
SUPPORT_LAST = 342
SUPPORT_COUNT = SUPPORT_LAST - SUPPORT_FIRST + 1
DISK_RADIUS = 5

# These thresholds only reject a grossly inconsistent registration before a
# human overlay review. They are not anatomical or medical acceptance limits.
TRIAGE_MEDIAN_MAX_PX = 25.0
TRIAGE_P90_MAX_PX = 50.0

STRUCTURES = (
    "radial_artery",
    "ulnar_artery",
    "cephalic_vein",
    "basilic_vein",
)

SEMANTIC_IDS = {
    "radial_artery": "structure.radial_artery.left",
    "ulnar_artery": "structure.ulnar_artery.left",
    "cephalic_vein": "structure.cephalic_vein.left",
    "basilic_vein": "structure.basilic_vein.left",
}


class AtlasFallbackDiagnosticError(RuntimeError):
    pass


def source_filename(index: int) -> str:
    nominal_offset, suffix_index = divmod(index, 3)
    suffix = ("a", "b", "c")[suffix_index]
    return f"avf{1567 + nominal_offset:04d}{suffix}.png"


def load_bone_tracks(report: dict[str, object]) -> dict[str, np.ndarray]:
    structures = report.get("structures")
    if not isinstance(structures, list):
        raise AtlasFallbackDiagnosticError("bone report has no structures")

    tracks: dict[str, np.ndarray] = {}
    for row in structures:
        if not isinstance(row, dict):
            continue
        label = row.get("draftLabel")
        if label not in {"radius", "ulna"}:
            continue
        files = row.get("files")
        if not isinstance(files, list):
            raise AtlasFallbackDiagnosticError(f"{label} files missing")
        by_frame: dict[int, tuple[float, float]] = {}
        for item in files:
            if not isinstance(item, dict):
                continue
            frame = item.get("globalFrameIndex")
            centroid = item.get("centroidSourcePixels")
            if (
                isinstance(frame, int)
                and 0 <= frame < FRAME_COUNT
                and isinstance(centroid, dict)
            ):
                by_frame[frame] = (
                    float(centroid["x"]),
                    float(centroid["y"]),
                )
        if set(by_frame) != set(range(FRAME_COUNT)):
            raise AtlasFallbackDiagnosticError(
                f"expected {FRAME_COUNT} {label} frames, got {len(by_frame)}"
            )
        tracks[str(label)] = np.asarray(
            [by_frame[index] for index in range(FRAME_COUNT)],
            dtype=float,
        )

    if set(tracks) != {"radius", "ulna"}:
        raise AtlasFallbackDiagnosticError("radius and ulna tracks required")
    return tracks


def load_ulnar_reference(report: dict[str, object]) -> dict[int, np.ndarray]:
    rows = report.get("maskFiles")
    if not isinstance(rows, list):
        raise AtlasFallbackDiagnosticError("ulnar report has no maskFiles")
    result: dict[int, np.ndarray] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        frame = row.get("globalFrameIndex")
        centroid = row.get("centroidSourcePixels")
        if isinstance(frame, int) and isinstance(centroid, dict):
            result[frame] = np.asarray(
                [float(centroid["x"]), float(centroid["y"])],
                dtype=float,
            )
    expected = set(range(SUPPORT_FIRST, SUPPORT_LAST + 1))
    if set(result) != expected:
        raise AtlasFallbackDiagnosticError(
            f"expected {SUPPORT_COUNT} reviewed ulnar frames, got {len(result)}"
        )
    return result


def error_summary(errors: np.ndarray) -> dict[str, float | int]:
    if errors.size == 0 or not np.isfinite(errors).all():
        raise AtlasFallbackDiagnosticError("registration errors are invalid")
    return {
        "count": int(errors.size),
        "meanSourcePixels": float(np.mean(errors)),
        "medianSourcePixels": float(np.median(errors)),
        "p90SourcePixels": float(np.quantile(errors, 0.90)),
        "maximumSourcePixels": float(np.max(errors)),
    }


def map_structures(
    atlas: dict[str, np.ndarray],
    bones: dict[str, np.ndarray],
    proximal_z: float,
    distal_z: float,
    orientation: int,
) -> dict[str, np.ndarray]:
    z_values = np.linspace(proximal_z, distal_z, FRAME_COUNT)
    return {
        label: base._local_pair_map(
            atlas["radius"],
            atlas["ulna"],
            atlas[label],
            bones["radius"],
            bones["ulna"],
            z_values,
            orientation=orientation,
        )
        for label in STRUCTURES
    }


def fit_registration(
    atlas: dict[str, np.ndarray],
    bones: dict[str, np.ndarray],
    ulnar_reference: dict[int, np.ndarray],
) -> tuple[
    float,
    float,
    int,
    np.ndarray,
    dict[str, np.ndarray],
    list[dict[str, object]],
]:
    calibration_frames = np.arange(CALIBRATION_FIRST, CALIBRATION_LAST + 1)
    actual = np.asarray(
        [ulnar_reference[int(frame)] for frame in calibration_frames],
        dtype=float,
    )

    candidates: list[
        tuple[
            tuple[float, float, float],
            float,
            float,
            int,
            np.ndarray,
            dict[str, np.ndarray],
            dict[str, object],
        ]
    ] = []

    for proximal_z in PROXIMAL_ATLAS_Z_CANDIDATES:
        for distal_z in DISTAL_ATLAS_Z_CANDIDATES:
            for orientation in (1, -1):
                mapped = map_structures(
                    atlas,
                    bones,
                    proximal_z,
                    distal_z,
                    orientation,
                )
                predicted = mapped["ulnar_artery"][calibration_frames]
                raw_residuals = actual - predicted
                translation = np.median(raw_residuals, axis=0)
                corrected = predicted + translation
                errors = np.linalg.norm(corrected - actual, axis=1)
                summary = error_summary(errors)
                key = (
                    float(summary["medianSourcePixels"]),
                    float(summary["p90SourcePixels"]),
                    float(summary["meanSourcePixels"]),
                )
                candidates.append(
                    (
                        key,
                        proximal_z,
                        distal_z,
                        orientation,
                        translation,
                        mapped,
                        {
                            "proximalAtlasZ": proximal_z,
                            "distalAtlasZ": distal_z,
                            "orientation": orientation,
                            "calibrationCorrectedError": summary,
                        },
                    )
                )

    candidates.sort(key=lambda item: item[0])
    best = candidates[0]
    diagnostics = [item[6] for item in candidates]
    return best[1], best[2], best[3], best[4], best[5], diagnostics


def load_mask(root: Path, label: str, filename: str) -> np.ndarray:
    path = root / "masks" / label / f"{Path(filename).stem}.pgm"
    mask = np.asarray(Image.open(path).convert("L")) > 0
    if mask.shape != (750, 550):
        raise AtlasFallbackDiagnosticError(
            f"unexpected mask shape for {path}: {mask.shape}"
        )
    return mask


def disk_fraction(mask: np.ndarray, x: float, y: float) -> float:
    yy, xx = np.ogrid[: mask.shape[0], : mask.shape[1]]
    disk = (xx - x) ** 2 + (yy - y) ** 2 <= DISK_RADIUS**2
    if not bool(disk.any()):
        return 0.0
    return float(mask[disk].mean())


def trajectory_support(
    points: np.ndarray,
    a05_root: Path,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    in_crop = 0
    subq_values: list[float] = []
    muscle_values: list[float] = []
    skin_depth_values: list[float] = []
    rows: list[dict[str, object]] = []

    for frame, point in enumerate(points):
        filename = source_filename(frame)
        x, y = map(float, point)
        inside = 0 <= x < 550 and 0 <= y < 750
        row: dict[str, object] = {
            "globalFrameIndex": frame,
            "sourceFilename": filename,
            "xSourcePixels": x,
            "ySourcePixels": y,
            "inCrop": inside,
        }
        if inside:
            in_crop += 1
            skin = load_mask(a05_root, "skin", filename)
            subq = load_mask(a05_root, "subcutaneous_soft_tissue", filename)
            muscle = load_mask(a05_root, "major_muscle_tendon_region", filename)
            non_skin = (~skin).astype(np.uint8)
            distance = cv2.distanceTransform(non_skin, cv2.DIST_L2, 5)
            xi = min(549, max(0, int(round(x))))
            yi = min(749, max(0, int(round(y))))
            subq_fraction = disk_fraction(subq, x, y)
            muscle_fraction = disk_fraction(muscle, x, y)
            skin_depth = float(distance[yi, xi])
            subq_values.append(subq_fraction)
            muscle_values.append(muscle_fraction)
            skin_depth_values.append(skin_depth)
            row.update(
                {
                    "subcutaneousDiskFraction": subq_fraction,
                    "muscleTendonDiskFraction": muscle_fraction,
                    "skinDepthSourcePixels": skin_depth,
                }
            )
        rows.append(row)

    def median_or_none(values: list[float]) -> float | None:
        return float(np.median(values)) if values else None

    stats: dict[str, object] = {
        "pointCount": int(len(points)),
        "inCropCount": in_crop,
        "inCropFraction": float(in_crop / len(points)),
        "medianSubcutaneousDiskFraction": median_or_none(subq_values),
        "medianMuscleTendonDiskFraction": median_or_none(muscle_values),
        "medianSkinDepthSourcePixels": median_or_none(skin_depth_values),
    }
    return stats, rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bone-report", type=Path, required=True)
    parser.add_argument("--atlas-root", type=Path, required=True)
    parser.add_argument("--a05-root", type=Path, required=True)
    parser.add_argument("--ulnar-report", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()

    bone_report = json.loads(args.bone_report.read_text(encoding="utf-8"))
    ulnar_report = json.loads(args.ulnar_report.read_text(encoding="utf-8"))
    bones = load_bone_tracks(bone_report)
    ulnar_reference = load_ulnar_reference(ulnar_report)
    atlas = {
        label: base._read_ascii_ply_vertices(args.atlas_root / f"{label}.ply")
        for label in ("radius", "ulna", *STRUCTURES)
    }

    (
        proximal_z,
        distal_z,
        orientation,
        translation,
        raw_mapped,
        candidate_diagnostics,
    ) = fit_registration(atlas, bones, ulnar_reference)

    corrected_mapped = {
        label: points + translation
        for label, points in raw_mapped.items()
    }

    calibration_frames = np.arange(CALIBRATION_FIRST, CALIBRATION_LAST + 1)
    validation_frames = np.arange(VALIDATION_FIRST, VALIDATION_LAST + 1)
    support_frames = np.arange(SUPPORT_FIRST, SUPPORT_LAST + 1)

    actual_calibration = np.asarray(
        [ulnar_reference[int(frame)] for frame in calibration_frames],
        dtype=float,
    )
    actual_validation = np.asarray(
        [ulnar_reference[int(frame)] for frame in validation_frames],
        dtype=float,
    )
    actual_all = np.asarray(
        [ulnar_reference[int(frame)] for frame in support_frames],
        dtype=float,
    )

    predicted_raw = raw_mapped["ulnar_artery"]
    predicted_corrected = corrected_mapped["ulnar_artery"]

    registration_validation = {
        "calibrationFrameRange": {
            "firstGlobalFrameIndex": CALIBRATION_FIRST,
            "lastGlobalFrameIndex": CALIBRATION_LAST,
            "frameCount": int(len(calibration_frames)),
        },
        "holdoutFrameRange": {
            "firstGlobalFrameIndex": VALIDATION_FIRST,
            "lastGlobalFrameIndex": VALIDATION_LAST,
            "frameCount": int(len(validation_frames)),
        },
        "translationSourcePixels": {
            "x": float(translation[0]),
            "y": float(translation[1]),
        },
        "calibrationRawError": error_summary(
            np.linalg.norm(
                predicted_raw[calibration_frames] - actual_calibration,
                axis=1,
            )
        ),
        "calibrationCorrectedError": error_summary(
            np.linalg.norm(
                predicted_corrected[calibration_frames] - actual_calibration,
                axis=1,
            )
        ),
        "holdoutRawError": error_summary(
            np.linalg.norm(
                predicted_raw[validation_frames] - actual_validation,
                axis=1,
            )
        ),
        "holdoutCorrectedError": error_summary(
            np.linalg.norm(
                predicted_corrected[validation_frames] - actual_validation,
                axis=1,
            )
        ),
        "allReviewedSupportCorrectedError": error_summary(
            np.linalg.norm(
                predicted_corrected[support_frames] - actual_all,
                axis=1,
            )
        ),
    }

    holdout = registration_validation["holdoutCorrectedError"]
    review_overlay_allowed = (
        float(holdout["medianSourcePixels"]) <= TRIAGE_MEDIAN_MAX_PX
        and float(holdout["p90SourcePixels"]) <= TRIAGE_P90_MAX_PX
    )

    structure_rows: list[dict[str, object]] = []
    trajectory_rows: dict[str, list[dict[str, object]]] = {}
    for label in STRUCTURES:
        support, points = trajectory_support(
            corrected_mapped[label],
            args.a05_root,
        )
        trajectory_rows[label] = points
        structure_rows.append(
            {
                "draftLabel": label,
                "anatomicalId": SEMANTIC_IDS[label],
                "sourceClass": "atlas-derived",
                "representationKind": "registered-reference-trajectory",
                "supportMetricsAgainstA05DraftMasks": support,
                "candidateForHumanOverlayReview": bool(
                    review_overlay_allowed
                    and float(support["inCropFraction"]) >= 0.80
                ),
                "sourceImageSupportEstablished": False,
            }
        )

    report = {
        "schema": "ph-a07-atlas-registered-vessel-diagnostic.v1",
        "schemaVersion": "1",
        "tasks": ["TASK-A07", "TASK-A12", "TASK-A13"],
        "recordedAt": "2026-09-10",
        "purpose": (
            "Evaluate whether a lower-authority atlas-derived vessel fallback "
            "can be rendered for explicit human anatomical review after "
            "same-subject source evidence failed closed for required vessels."
        ),
        "coordinateSpace": {
            "kind": "source-image-stack",
            "patientSpaceClaim": False,
            "ctRegistrationEstablished": False,
        },
        "atlasSource": {
            "name": "Z-Anatomy Models-of-human-anatomy",
            "sourceClass": "atlas-derived",
            "upstreamAttribution": "BodyParts3D - DBCLS",
            "artifactId": 10081007930,
            "artifactArchiveSha256": (
                "9b1c58de04f78e533e2d339f4ad6d3d93dc32d9f74c5d14d6c816b3cab2aa625"
            ),
            "atlasGeometryUsedAsAcquiredCadaverGeometry": False,
        },
        "registrationTarget": {
            "dataset": "NLM Visible Human Female",
            "sourceClass": "cadaver-derived",
            "boneCandidateArtifactId": 10088808577,
            "reviewedUlnarCandidateArtifactId": 10092590748,
        },
        "registration": {
            "method": (
                "slice-local radius-ulna normalized atlas mapping; discrete "
                "atlas-z/orientation fit plus one constant source-stack "
                "translation calibrated on the first 53 human-reviewed ulnar "
                "artery frames; final registration quality measured on the "
                "disjoint last 53 reviewed ulnar artery frames"
            ),
            "proximalAtlasZ": proximal_z,
            "distalAtlasZ": distal_z,
            "orientation": orientation,
            "candidateSearchCount": len(candidate_diagnostics),
            "registrationValidation": registration_validation,
            "technicalTriageThresholds": {
                "meaning": (
                    "gross-mismatch screen for whether an overlay is worth "
                    "human review; not an anatomical or medical acceptance limit"
                ),
                "holdoutMedianMaxSourcePixels": TRIAGE_MEDIAN_MAX_PX,
                "holdoutP90MaxSourcePixels": TRIAGE_P90_MAX_PX,
            },
            "reviewOverlayGenerationAllowed": review_overlay_allowed,
        },
        "structures": structure_rows,
        "disposition": {
            "atlasFallbackRepresentationPromoted": False,
            "a07SemanticMappingChanged": False,
            "a10MedicalMasterReadinessChanged": False,
            "humanOverlayReviewNext": review_overlay_allowed,
            "reason": (
                "Atlas-derived trajectories remain review candidates only. "
                "They cannot replace missing same-subject evidence or become "
                "Medical Master anatomy without explicit downstream review "
                "and provenance-preserving source-strategy revision."
            ),
        },
        "claims": {
            "atlasDerived": True,
            "sourceImageSupportEstablished": False,
            "humanAnatomicalReview": False,
            "procedureSpecificReview": False,
            "medicalValidation": False,
            "patientSpaceGeometry": False,
            "superficialTargetVeinSelected": False,
            "automaticPromotionAllowed": False,
        },
    }

    trajectories = {
        "schema": "ph-a07-atlas-registered-vessel-trajectories.v1",
        "schemaVersion": "1",
        "recordedAt": "2026-09-10",
        "coordinateSpace": {
            "kind": "source-image-stack",
            "patientSpaceClaim": False,
        },
        "registrationReference": (
            "a07-atlas-registered-vessel-diagnostic.v0.json"
        ),
        "structures": [
            {
                "draftLabel": label,
                "anatomicalId": SEMANTIC_IDS[label],
                "sourceClass": "atlas-derived",
                "points": trajectory_rows[label],
            }
            for label in STRUCTURES
        ],
        "claims": {
            "sourceImageSupportEstablished": False,
            "humanAnatomicalReview": False,
            "medicalValidation": False,
            "patientSpaceGeometry": False,
            "automaticPromotionAllowed": False,
        },
    }

    args.output_root.mkdir(parents=True, exist_ok=True)
    report_path = (
        args.output_root
        / "a07-atlas-registered-vessel-diagnostic.v0.json"
    )
    trajectory_path = (
        args.output_root
        / "a07-atlas-registered-vessel-trajectories.v0.json"
    )
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    trajectory_path.write_text(
        json.dumps(trajectories, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "selectedRegistration": {
                    "proximalAtlasZ": proximal_z,
                    "distalAtlasZ": distal_z,
                    "orientation": orientation,
                    "translationSourcePixels": registration_validation[
                        "translationSourcePixels"
                    ],
                },
                "registrationValidation": registration_validation,
                "reviewOverlayGenerationAllowed": review_overlay_allowed,
                "structures": structure_rows,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
