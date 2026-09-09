from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from math import ceil
from pathlib import Path

import numpy as np


ATLAS_Z_MIN = 0.86
ATLAS_Z_MAX = 1.09
ATLAS_Z_STEP = 0.005
ATLAS_MIN_SPAN = 0.08
ATLAS_MAX_SPAN = 0.18
CENTERLINE_NEAREST_VERTEX_COUNT = 30
VESSEL_NEAREST_VERTEX_COUNT = 36
CROP_WIDTH = 550
CROP_HEIGHT = 750
FIRST_GLOBAL_FRAME = 0
LAST_GLOBAL_FRAME = 354
FRAME_COUNT = LAST_GLOBAL_FRAME - FIRST_GLOBAL_FRAME + 1
FIRST_SOURCE_FILE = "avf1567a.png"
LAST_SOURCE_FILE = "avf1685a.png"

VESSELS = {
    "radial_artery": "structure.radial_artery.left",
    "ulnar_artery": "structure.ulnar_artery.left",
    "cephalic_vein": "structure.cephalic_vein.left",
    "basilic_vein": "structure.basilic_vein.left",
}


class VesselAtlasPriorError(RuntimeError):
    pass


@dataclass(frozen=True)
class AffineFit:
    transform: np.ndarray
    mean_residual: float
    median_residual: float
    p95_residual: float
    max_residual: float


@dataclass(frozen=True)
class LongitudinalFit:
    proximal_atlas_z: float
    distal_atlas_z: float
    affine: AffineFit


def _read_ascii_ply_vertices(path: Path) -> np.ndarray:
    with path.open("r", encoding="ascii") as stream:
        if stream.readline().strip() != "ply":
            raise VesselAtlasPriorError(f"{path.name} is not an ASCII PLY")
        vertex_count: int | None = None
        while True:
            line = stream.readline()
            if not line:
                raise VesselAtlasPriorError(f"{path.name} PLY header is incomplete")
            line = line.strip()
            if line.startswith("format ") and line != "format ascii 1.0":
                raise VesselAtlasPriorError(f"{path.name} must use ASCII PLY")
            if line.startswith("element vertex "):
                vertex_count = int(line.split()[-1])
            if line == "end_header":
                break
        if vertex_count is None or vertex_count <= 0:
            raise VesselAtlasPriorError(f"{path.name} has no vertices")
        vertices = np.asarray(
            [
                [float(value) for value in stream.readline().split()[:3]]
                for _ in range(vertex_count)
            ],
            dtype=float,
        )
    if vertices.shape != (vertex_count, 3) or not np.isfinite(vertices).all():
        raise VesselAtlasPriorError(f"{path.name} contains invalid vertices")
    return vertices


def _local_xy_curve(vertices: np.ndarray, z_values: np.ndarray, nearest_count: int) -> np.ndarray:
    if nearest_count <= 0 or nearest_count > len(vertices):
        raise VesselAtlasPriorError("invalid nearest vertex count")
    result: list[np.ndarray] = []
    for z_value in z_values:
        indices = np.argpartition(
            np.abs(vertices[:, 2] - z_value),
            nearest_count - 1,
        )[:nearest_count]
        result.append(np.median(vertices[indices, :2], axis=0))
    return np.asarray(result, dtype=float)


def _a_slice_centroids(report: dict[str, object]) -> dict[str, np.ndarray]:
    structures = report.get("structures")
    if not isinstance(structures, list):
        raise VesselAtlasPriorError("bone candidate report is missing structures")
    output: dict[str, np.ndarray] = {}
    for item in structures:
        if not isinstance(item, dict):
            continue
        label = item.get("draftLabel")
        if label not in {"radius", "ulna"}:
            continue
        files = item.get("files")
        if not isinstance(files, list):
            raise VesselAtlasPriorError(f"{label} candidate report is missing files")
        points: list[list[float]] = []
        for row in files:
            if not isinstance(row, dict):
                continue
            filename = row.get("sourceFilename")
            centroid = row.get("centroidSourcePixels")
            if (
                isinstance(filename, str)
                and filename.endswith("a.png")
                and isinstance(centroid, dict)
            ):
                points.append([float(centroid["x"]), float(centroid["y"])])
        output[str(label)] = np.asarray(points, dtype=float)

    if set(output) != {"radius", "ulna"}:
        raise VesselAtlasPriorError("radius and ulna A-slice centroid tracks are required")
    if output["radius"].shape != output["ulna"].shape:
        raise VesselAtlasPriorError("radius/ulna A-slice track lengths differ")
    if output["radius"].shape != (119, 2):
        raise VesselAtlasPriorError(
            f"expected 119 A-slice centroid pairs, got {output['radius'].shape}"
        )
    return output


def _fit_affine(source: np.ndarray, target: np.ndarray) -> AffineFit:
    x = np.column_stack([source, np.ones(len(source), dtype=float)])
    transform, *_ = np.linalg.lstsq(x, target, rcond=None)
    predicted = x @ transform
    residuals = np.linalg.norm(predicted - target, axis=1)
    return AffineFit(
        transform=transform,
        mean_residual=float(np.mean(residuals)),
        median_residual=float(np.median(residuals)),
        p95_residual=float(np.quantile(residuals, 0.95)),
        max_residual=float(np.max(residuals)),
    )


def _search_longitudinal_registration(
    atlas_radius: np.ndarray,
    atlas_ulna: np.ndarray,
    vhp_tracks: dict[str, np.ndarray],
    *,
    swapped: bool,
) -> LongitudinalFit:
    count = len(vhp_tracks["radius"])
    t = np.linspace(0.0, 1.0, count)
    values = np.arange(
        ATLAS_Z_MIN,
        ATLAS_Z_MAX + ATLAS_Z_STEP / 2.0,
        ATLAS_Z_STEP,
    )
    best: LongitudinalFit | None = None

    for proximal_z in values:
        for distal_z in values:
            span = abs(float(distal_z - proximal_z))
            if not ATLAS_MIN_SPAN <= span <= ATLAS_MAX_SPAN:
                continue
            z_values = proximal_z + (distal_z - proximal_z) * t
            radius_curve = _local_xy_curve(
                atlas_radius,
                z_values,
                CENTERLINE_NEAREST_VERTEX_COUNT,
            )
            ulna_curve = _local_xy_curve(
                atlas_ulna,
                z_values,
                CENTERLINE_NEAREST_VERTEX_COUNT,
            )
            source = np.vstack([radius_curve, ulna_curve])
            if swapped:
                target = np.vstack([vhp_tracks["ulna"], vhp_tracks["radius"]])
            else:
                target = np.vstack([vhp_tracks["radius"], vhp_tracks["ulna"]])
            fit = _fit_affine(source, target)
            candidate = LongitudinalFit(
                proximal_atlas_z=float(proximal_z),
                distal_atlas_z=float(distal_z),
                affine=fit,
            )
            if best is None or candidate.affine.mean_residual < best.affine.mean_residual:
                best = candidate

    if best is None:
        raise VesselAtlasPriorError("no atlas longitudinal registration candidate was found")
    return best


def _transform_xy(points: np.ndarray, transform: np.ndarray) -> np.ndarray:
    x = np.column_stack([points, np.ones(len(points), dtype=float)])
    return x @ transform


def _source_filename(global_frame_index: int) -> str:
    nominal_offset, suffix_index = divmod(global_frame_index, 3)
    suffix = ("a", "b", "c")[suffix_index]
    return f"avf{1567 + nominal_offset:04d}{suffix}.png"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bone-report", type=Path, required=True)
    parser.add_argument("--atlas-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()

    bone_report = json.loads(args.bone_report.read_text(encoding="utf-8"))
    vhp_tracks = _a_slice_centroids(bone_report)

    atlas_radius = _read_ascii_ply_vertices(args.atlas_root / "radius.ply")
    atlas_ulna = _read_ascii_ply_vertices(args.atlas_root / "ulna.ply")

    direct = _search_longitudinal_registration(
        atlas_radius,
        atlas_ulna,
        vhp_tracks,
        swapped=False,
    )
    swapped = _search_longitudinal_registration(
        atlas_radius,
        atlas_ulna,
        vhp_tracks,
        swapped=True,
    )

    if direct.affine.mean_residual > 25.0:
        raise VesselAtlasPriorError(
            f"atlas-to-VHP bone registration residual is too high: "
            f"{direct.affine.mean_residual:.3f}px"
        )
    if direct.proximal_atlas_z <= direct.distal_atlas_z:
        raise VesselAtlasPriorError(
            "best direct atlas mapping does not follow the expected proximal-to-distal z direction"
        )

    cross_atlas_buffer = 20.0
    search_radius = int(
        ceil(max(40.0, direct.affine.p95_residual + cross_atlas_buffer))
    )

    global_frames = np.arange(FIRST_GLOBAL_FRAME, LAST_GLOBAL_FRAME + 1)
    t = global_frames / LAST_GLOBAL_FRAME
    atlas_z_values = (
        direct.proximal_atlas_z
        + (direct.distal_atlas_z - direct.proximal_atlas_z) * t
    )

    structures: list[dict[str, object]] = []
    for label, semantic_id in VESSELS.items():
        vertices = _read_ascii_ply_vertices(args.atlas_root / f"{label}.ply")
        atlas_curve = _local_xy_curve(
            vertices,
            atlas_z_values,
            VESSEL_NEAREST_VERTEX_COUNT,
        )
        source_points = _transform_xy(atlas_curve, direct.affine.transform)
        frames: list[dict[str, object]] = []
        in_crop_count = 0
        for global_index, atlas_z, point in zip(
            global_frames,
            atlas_z_values,
            source_points,
        ):
            x = float(point[0])
            y = float(point[1])
            in_crop = 0.0 <= x < CROP_WIDTH and 0.0 <= y < CROP_HEIGHT
            if in_crop:
                in_crop_count += 1
            frames.append(
                {
                    "globalFrameIndex": int(global_index),
                    "sourceFilename": _source_filename(int(global_index)),
                    "atlasZ": float(atlas_z),
                    "priorCenterSourcePixels": {"x": x, "y": y},
                    "searchRadiusSourcePixels": search_radius,
                    "inCrop": in_crop,
                }
            )

        in_crop_fraction = in_crop_count / len(frames)
        if in_crop_fraction < 0.95:
            raise VesselAtlasPriorError(
                f"{label} atlas prior leaves the source crop too often: "
                f"{in_crop_fraction:.3f}"
            )
        structures.append(
            {
                "draftLabel": label,
                "anatomicalId": semantic_id,
                "role": (
                    "arterial-reference-prior"
                    if label.endswith("_artery")
                    else "named-superficial-vein-reference-prior"
                ),
                "priorStatus": "atlas-derived-search-prior-only",
                "supportedFrameCount": len(frames),
                "inCropFrameCount": in_crop_count,
                "inCropFraction": in_crop_fraction,
                "frames": frames,
            }
        )

    report = {
        "schema": "ph-a06-vessel-atlas-prior-report.v1",
        "schemaVersion": "1",
        "task": "TASK-A06",
        "recordedAt": "2026-09-09",
        "status": {
            "validationLevel": "V0",
            "reviewStatus": "unreviewed",
            "candidateOnly": True,
        },
        "coordinateSpace": {
            "kind": "source-image-stack",
            "patientSpaceClaim": False,
            "ctRegistrationEstablished": False,
        },
        "sourceEvidence": {
            "vhpBoneCandidateReport": str(args.bone_report),
            "sameCadaverBoneIdentityCorroborated": True,
            "atlas": {
                "name": "Z-Anatomy Models-of-human-anatomy",
                "sourceArchiveSha256": "e029688545627bd0214b269e1063143abb580aad72b2c2445d6d8a9a0d9da736",
                "referenceArchiveSha256": "9b1c58de04f78e533e2d339f4ad6d3d93dc32d9f74c5d14d6c816b3cab2aa625",
                "license": "CC BY-SA 4.0",
                "upstreamModelAttribution": "BodyParts3D - DBCLS - CC BY-SA 2.1 Japan",
            },
        },
        "registration": {
            "method": "cross-subject atlas bone-trajectory affine search prior",
            "direct": {
                "proximalAtlasZ": direct.proximal_atlas_z,
                "distalAtlasZ": direct.distal_atlas_z,
                "atlasSpan": abs(direct.distal_atlas_z - direct.proximal_atlas_z),
                "meanResidualSourcePixels": direct.affine.mean_residual,
                "medianResidualSourcePixels": direct.affine.median_residual,
                "p95ResidualSourcePixels": direct.affine.p95_residual,
                "maxResidualSourcePixels": direct.affine.max_residual,
                "transformAtlasXYToSourcePixels": direct.affine.transform.tolist(),
            },
            "swappedIdentityDiagnostic": {
                "notUsedForIdentityAssignment": True,
                "meanResidualSourcePixels": swapped.affine.mean_residual,
                "proximalAtlasZ": swapped.proximal_atlas_z,
                "distalAtlasZ": swapped.distal_atlas_z,
                "reason": (
                    "cross-subject atlas morphology may fit a swapped two-bone trajectory; "
                    "radius/ulna identity is inherited from same-cadaver CT corroboration, "
                    "not selected from this atlas diagnostic"
                ),
            },
            "searchUncertainty": {
                "p95BoneRegistrationResidualSourcePixels": direct.affine.p95_residual,
                "crossAtlasBufferSourcePixels": cross_atlas_buffer,
                "searchRadiusSourcePixels": search_radius,
            },
        },
        "support": {
            "firstGlobalFrameIndex": FIRST_GLOBAL_FRAME,
            "lastGlobalFrameIndex": LAST_GLOBAL_FRAME,
            "firstSourceFilename": FIRST_SOURCE_FILE,
            "lastSourceFilename": LAST_SOURCE_FILE,
            "supportedFrameCount": FRAME_COUNT,
            "outsideSupportDisposition": "no-atlas-prior-from-this-pass",
        },
        "structures": structures,
        "targetVeinDisposition": {
            "superficialTargetVeinAnatomicalId": None,
            "candidateNamedVeinPriors": [
                "structure.cephalic_vein.left",
                "structure.basilic_vein.left",
            ],
            "status": "unresolved-until-vhp-source-evidence-is-evaluated",
        },
        "claims": {
            "atlasGeometryUsedAsSubjectGeometry": False,
            "vesselMaskGenerated": False,
            "vesselCenterlineEstablished": False,
            "superficialTargetVeinIdentityEstablished": False,
            "humanEdited": False,
            "anatomicallyReviewed": False,
            "medicalValidation": False,
            "patientSpaceGeometry": False,
            "automaticPromotionAllowed": False,
        },
    }

    args.output_root.mkdir(parents=True, exist_ok=True)
    destination = args.output_root / "a06-vessel-atlas-prior-report.v0.json"
    destination.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "directRegistration": report["registration"]["direct"],
                "searchRadiusSourcePixels": search_radius,
                "structures": [
                    {
                        "draftLabel": item["draftLabel"],
                        "inCropFraction": item["inCropFraction"],
                    }
                    for item in structures
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
