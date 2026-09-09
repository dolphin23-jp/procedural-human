from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
from math import hypot, log, pi
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

FRAME_COUNT = 355
FIRST_GLOBAL_FRAME = 0
LAST_GLOBAL_FRAME = 354
FIRST_SOURCE_FILE = "avf1567a.png"
LAST_SOURCE_FILE = "avf1685a.png"
CENTERLINE_NEAREST_VERTEX_COUNT = 30
VESSEL_NEAREST_VERTEX_COUNT = 36
PRIOR_TISSUE_RADIUS = 10
SEARCH_RADIUS = 40
COMPONENT_AREA_MIN = 6
COMPONENT_AREA_MAX = 350
MAX_TRACK_GAP = 3
BASE_TRACK_JUMP = 7.0

PROXIMAL_ATLAS_Z_CANDIDATES = (0.95, 0.955, 0.96, 0.965)
DISTAL_ATLAS_Z_CANDIDATES = (0.875, 0.88, 0.885)

VESSELS = (
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


class VesselCandidateError(RuntimeError):
    pass


@dataclass
class Candidate:
    area: int
    circularity: float
    contrast: float
    prior_distance: float
    x: float
    y: float
    mean_r: float
    mean_g: float
    mean_b: float
    threshold: float
    x0: int
    y0: int
    mask: np.ndarray


@dataclass(frozen=True)
class TrackMetrics:
    node_count: int
    span_frame_count: int
    coverage_fraction: float
    first_global_frame_index: int
    last_global_frame_index: int
    mean_gap: float
    max_gap: int
    mean_jump_pixels: float
    max_jump_pixels: float
    median_area_pixels: float
    median_circularity: float
    p25_circularity: float
    median_contrast: float
    p25_contrast: float
    mean_prior_distance_pixels: float


def _read_ascii_ply_vertices(path: Path) -> np.ndarray:
    with path.open("r", encoding="ascii") as stream:
        if stream.readline().strip() != "ply":
            raise VesselCandidateError(f"{path.name} is not an ASCII PLY")
        vertex_count: int | None = None
        while True:
            line = stream.readline()
            if not line:
                raise VesselCandidateError(f"{path.name} PLY header is incomplete")
            line = line.strip()
            if line.startswith("format ") and line != "format ascii 1.0":
                raise VesselCandidateError(f"{path.name} must use ASCII PLY")
            if line.startswith("element vertex "):
                vertex_count = int(line.split()[-1])
            if line == "end_header":
                break
        if vertex_count is None or vertex_count <= 0:
            raise VesselCandidateError(f"{path.name} has no vertices")
        vertices = np.asarray(
            [
                [float(value) for value in stream.readline().split()[:3]]
                for _ in range(vertex_count)
            ],
            dtype=float,
        )
    if vertices.shape != (vertex_count, 3) or not np.isfinite(vertices).all():
        raise VesselCandidateError(f"{path.name} contains invalid vertices")
    return vertices


def _local_xy_curve(
    vertices: np.ndarray,
    z_values: np.ndarray,
    nearest_count: int,
) -> np.ndarray:
    result: list[np.ndarray] = []
    for z_value in z_values:
        indices = np.argpartition(
            np.abs(vertices[:, 2] - z_value),
            nearest_count - 1,
        )[:nearest_count]
        result.append(np.median(vertices[indices, :2], axis=0))
    return np.asarray(result, dtype=float)


def _bone_tracks(report: dict[str, object]) -> dict[str, np.ndarray]:
    structures = report.get("structures")
    if not isinstance(structures, list):
        raise VesselCandidateError("bone candidate report is missing structures")
    output: dict[str, np.ndarray] = {}
    for item in structures:
        if not isinstance(item, dict):
            continue
        label = item.get("draftLabel")
        if label not in {"radius", "ulna"}:
            continue
        rows = item.get("files")
        if not isinstance(rows, list):
            raise VesselCandidateError(f"{label} files are missing")
        points: list[list[float]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            global_index = row.get("globalFrameIndex")
            centroid = row.get("centroidSourcePixels")
            if (
                isinstance(global_index, int)
                and FIRST_GLOBAL_FRAME <= global_index <= LAST_GLOBAL_FRAME
                and isinstance(centroid, dict)
            ):
                points.append([float(centroid["x"]), float(centroid["y"])])
        array = np.asarray(points, dtype=float)
        if array.shape != (FRAME_COUNT, 2):
            raise VesselCandidateError(
                f"expected {FRAME_COUNT} {label} centroids, got {array.shape}"
            )
        output[str(label)] = array
    if set(output) != {"radius", "ulna"}:
        raise VesselCandidateError("radius and ulna tracks are required")
    return output


def _source_filename(global_frame_index: int) -> str:
    nominal_offset, suffix_index = divmod(global_frame_index, 3)
    suffix = ("a", "b", "c")[suffix_index]
    return f"avf{1567 + nominal_offset:04d}{suffix}.png"


def _local_pair_map(
    atlas_radius: np.ndarray,
    atlas_ulna: np.ndarray,
    atlas_structure: np.ndarray,
    source_radius: np.ndarray,
    source_ulna: np.ndarray,
    z_values: np.ndarray,
    *,
    orientation: int,
) -> np.ndarray:
    atlas_radius_curve = _local_xy_curve(
        atlas_radius,
        z_values,
        CENTERLINE_NEAREST_VERTEX_COUNT,
    )
    atlas_ulna_curve = _local_xy_curve(
        atlas_ulna,
        z_values,
        CENTERLINE_NEAREST_VERTEX_COUNT,
    )
    structure_curve = _local_xy_curve(
        atlas_structure,
        z_values,
        VESSEL_NEAREST_VERTEX_COUNT,
    )
    result: list[np.ndarray] = []
    for index in range(len(z_values)):
        atlas_mid = (atlas_radius_curve[index] + atlas_ulna_curve[index]) / 2.0
        atlas_axis = atlas_radius_curve[index] - atlas_ulna_curve[index]
        atlas_distance = float(np.linalg.norm(atlas_axis))
        if atlas_distance <= 1e-8:
            raise VesselCandidateError("atlas radius/ulna separation collapsed")
        atlas_axis = atlas_axis / atlas_distance
        atlas_perp = np.asarray([-atlas_axis[1], atlas_axis[0]], dtype=float)

        source_mid = (source_radius[index] + source_ulna[index]) / 2.0
        source_axis = source_radius[index] - source_ulna[index]
        source_distance = float(np.linalg.norm(source_axis))
        if source_distance <= 1e-8:
            raise VesselCandidateError("source radius/ulna separation collapsed")
        source_axis = source_axis / source_distance
        source_perp = np.asarray([-source_axis[1], source_axis[0]], dtype=float)

        relative = structure_curve[index] - atlas_mid
        normalized_parallel = float(np.dot(relative, atlas_axis) / atlas_distance)
        normalized_perpendicular = float(
            np.dot(relative, atlas_perp) / atlas_distance
        )
        mapped = source_mid + source_distance * (
            normalized_parallel * source_axis
            + orientation * normalized_perpendicular * source_perp
        )
        result.append(mapped)
    return np.asarray(result, dtype=float)


def _is_tissue(rgb: np.ndarray) -> np.ndarray:
    values = rgb.astype(np.int16)
    red, green, blue = values[:, :, 0], values[:, :, 1], values[:, :, 2]
    blue_background = (blue > red + 18) & (blue > green + 8) & (blue > 55)
    too_dark = red + green + blue < 45
    return (~blue_background) & (~too_dark)


def _is_muscle_like(rgb: np.ndarray) -> np.ndarray:
    values = rgb.astype(np.int16)
    red, green, blue = values[:, :, 0], values[:, :, 1], values[:, :, 2]
    blue_background = (blue > red + 18) & (blue > green + 8)
    brightness = (red + green + blue) / 3.0
    saturation = np.maximum.reduce([red, green, blue]) - np.minimum.reduce(
        [red, green, blue]
    )
    return (
        (~blue_background)
        & (red >= green - 5)
        & (green >= blue - 15)
        & (brightness < 150)
        & (brightness > 20)
        & (saturation > 10)
    )


def _disk_fraction(mask: np.ndarray, center: np.ndarray, radius: int) -> float:
    x, y = map(float, center)
    height, width = mask.shape
    yy, xx = np.ogrid[:height, :width]
    disk = (xx - x) ** 2 + (yy - y) ** 2 <= radius**2
    if not bool(disk.any()):
        return 0.0
    return float(mask[disk].mean())


def _optimize_local_pair_prior(
    cryo_root: Path,
    atlas: dict[str, np.ndarray],
    bone_tracks: dict[str, np.ndarray],
) -> tuple[
    float,
    float,
    int,
    dict[str, np.ndarray],
    dict[str, dict[str, float]],
]:
    a_indices = np.arange(0, FRAME_COUNT, 3)
    source_radius = bone_tracks["radius"][a_indices]
    source_ulna = bone_tracks["ulna"][a_indices]
    images = [
        np.asarray(
            Image.open(cryo_root / _source_filename(int(index))).convert("RGB")
        )
        for index in a_indices
    ]
    tissue_masks = [_is_tissue(image) for image in images]
    muscle_masks = [_is_muscle_like(image) for image in images]

    best: tuple[
        float,
        float,
        float,
        int,
        dict[str, np.ndarray],
        dict[str, dict[str, float]],
    ] | None = None

    for proximal_z in PROXIMAL_ATLAS_Z_CANDIDATES:
        for distal_z in DISTAL_ATLAS_Z_CANDIDATES:
            z_values = np.linspace(proximal_z, distal_z, len(a_indices))
            for orientation in (1, -1):
                mapped: dict[str, np.ndarray] = {}
                diagnostics: dict[str, dict[str, float]] = {}
                score_terms: list[float] = []
                for label in VESSELS:
                    points = _local_pair_map(
                        atlas["radius"],
                        atlas["ulna"],
                        atlas[label],
                        source_radius,
                        source_ulna,
                        z_values,
                        orientation=orientation,
                    )
                    mapped[label] = points
                    tissue_values: list[float] = []
                    muscle_values: list[float] = []
                    in_crop = 0
                    for index, point in enumerate(points):
                        x, y = point
                        if 0 <= x < 550 and 0 <= y < 750:
                            in_crop += 1
                            tissue_values.append(
                                _disk_fraction(
                                    tissue_masks[index],
                                    point,
                                    PRIOR_TISSUE_RADIUS,
                                )
                            )
                            muscle_values.append(
                                _disk_fraction(
                                    muscle_masks[index],
                                    point,
                                    PRIOR_TISSUE_RADIUS,
                                )
                            )
                        else:
                            tissue_values.append(0.0)
                            muscle_values.append(0.0)
                    diagnostics[label] = {
                        "meanTissueSupport": float(np.mean(tissue_values)),
                        "medianTissueSupport": float(np.median(tissue_values)),
                        "meanMuscleLikeSupport": float(
                            np.mean(muscle_values)
                        ),
                        "medianMuscleLikeSupport": float(
                            np.median(muscle_values)
                        ),
                        "inCropFraction": in_crop / len(points),
                    }
                    if label in {"radial_artery", "ulnar_artery"}:
                        score_terms.extend(tissue_values)
                        score_terms.extend(
                            (0.35 * np.asarray(muscle_values)).tolist()
                        )
                score = float(np.mean(score_terms))
                candidate = (
                    score,
                    float(proximal_z),
                    float(distal_z),
                    orientation,
                    mapped,
                    diagnostics,
                )
                if best is None or candidate[0] > best[0]:
                    best = candidate

    if best is None:
        raise VesselCandidateError(
            "no local-pair atlas prior registration candidate found"
        )

    _, proximal_z, distal_z, orientation, _, diagnostics = best
    z_values_all = np.linspace(proximal_z, distal_z, FRAME_COUNT)
    mapped_all = {
        label: _local_pair_map(
            atlas["radius"],
            atlas["ulna"],
            atlas[label],
            bone_tracks["radius"],
            bone_tracks["ulna"],
            z_values_all,
            orientation=orientation,
        )
        for label in VESSELS
    }
    return (
        proximal_z,
        distal_z,
        orientation,
        mapped_all,
        diagnostics,
    )


def _extract_candidates(
    image: np.ndarray,
    prior: np.ndarray,
) -> list[Candidate]:
    height, width = image.shape[:2]
    x, y = map(float, prior)
    x0 = max(0, int(np.floor(x - SEARCH_RADIUS)))
    x1 = min(width, int(np.ceil(x + SEARCH_RADIUS + 1)))
    y0 = max(0, int(np.floor(y - SEARCH_RADIUS)))
    y1 = min(height, int(np.ceil(y + SEARCH_RADIUS + 1)))
    crop = image[y0:y1, x0:x1]
    if crop.size == 0:
        return []

    yy, xx = np.ogrid[y0:y1, x0:x1]
    disk = (xx - x) ** 2 + (yy - y) ** 2 <= SEARCH_RADIUS**2
    values = crop.astype(np.float32)
    red, green, blue = values[:, :, 0], values[:, :, 1], values[:, :, 2]
    luminance = 0.299 * red + 0.587 * green + 0.114 * blue
    tissue = _is_tissue(crop)
    support_values = luminance[disk & tissue]
    if len(support_values) < 20:
        return []

    threshold = min(100.0, float(np.quantile(support_values, 0.18)))
    dark = (luminance <= threshold) & disk & tissue
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(
        dark.astype(np.uint8) * 255,
        8,
    )

    candidates: list[Candidate] = []
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if not COMPONENT_AREA_MIN <= area <= COMPONENT_AREA_MAX:
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
        circularity = (
            4.0 * pi * area / (perimeter * perimeter)
            if perimeter > 0
            else 0.0
        )
        cx, cy = map(float, centroids[label])
        global_x = x0 + cx
        global_y = y0 + cy
        prior_distance = hypot(global_x - x, global_y - y)

        dilated = cv2.dilate(
            component_mask,
            np.ones((3, 3), np.uint8),
            iterations=3,
        ).astype(bool)
        component_bool = component_mask.astype(bool)
        ring = dilated & ~component_bool
        contrast = (
            float(
                luminance[ring].mean()
                - luminance[component_bool].mean()
            )
            if bool(ring.any())
            else 0.0
        )
        pixels = crop[component_bool].astype(float)
        mean_rgb = pixels.mean(axis=0)
        if (
            contrast < 8.0
            or circularity < 0.12
            or mean_rgb[2] > mean_rgb[0] + 35
        ):
            continue

        candidates.append(
            Candidate(
                area=area,
                circularity=float(circularity),
                contrast=contrast,
                prior_distance=prior_distance,
                x=global_x,
                y=global_y,
                mean_r=float(mean_rgb[0]),
                mean_g=float(mean_rgb[1]),
                mean_b=float(mean_rgb[2]),
                threshold=threshold,
                x0=x0,
                y0=y0,
                mask=component_mask,
            )
        )
    return candidates


def _node_score(candidate: Candidate) -> float:
    area_penalty = max(0.0, (candidate.area - 180) / 100.0)
    circularity = min(candidate.circularity, 1.2)
    return (
        1.0
        + 0.035 * min(candidate.contrast, 80.0)
        + 0.5 * circularity
        - 0.025 * candidate.prior_distance
        - 0.25 * area_penalty
    )


def _best_track(
    candidates_by_frame: list[list[Candidate]],
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

            for gap in range(1, MAX_TRACK_GAP + 1):
                previous_frame = frame_index - gap
                if previous_frame < 0:
                    continue
                for previous_index, previous_candidate in enumerate(
                    candidates_by_frame[previous_frame]
                ):
                    state = states.get(
                        (previous_frame, previous_index)
                    )
                    if state is None:
                        continue
                    jump = hypot(
                        candidate.x - previous_candidate.x,
                        candidate.y - previous_candidate.y,
                    )
                    if jump > BASE_TRACK_JUMP * gap + 3.0:
                        continue
                    area_change = abs(
                        log(
                            (candidate.area + 1)
                            / (previous_candidate.area + 1)
                        )
                    )
                    transition = (
                        -0.10 * jump
                        - 0.30 * area_change
                        - 0.60 * (gap - 1)
                    )
                    score = (
                        state[0]
                        + _node_score(candidate)
                        + transition
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


def _track_metrics(
    path: list[tuple[int, int]],
    candidates_by_frame: list[list[Candidate]],
) -> TrackMetrics | None:
    if not path:
        return None

    frames = np.asarray(
        [frame for frame, _ in path],
        dtype=int,
    )
    nodes = [
        candidates_by_frame[frame][index]
        for frame, index in path
    ]
    points = np.asarray(
        [[node.x, node.y] for node in nodes],
        dtype=float,
    )
    gaps = np.diff(frames)
    jumps = (
        np.linalg.norm(np.diff(points, axis=0), axis=1)
        if len(points) > 1
        else np.asarray([])
    )

    return TrackMetrics(
        node_count=len(nodes),
        span_frame_count=int(frames[-1] - frames[0] + 1),
        coverage_fraction=float(
            len(nodes) / (frames[-1] - frames[0] + 1)
        ),
        first_global_frame_index=int(frames[0]),
        last_global_frame_index=int(frames[-1]),
        mean_gap=float(gaps.mean()) if len(gaps) else 0.0,
        max_gap=int(gaps.max()) if len(gaps) else 0,
        mean_jump_pixels=(
            float(jumps.mean()) if len(jumps) else 0.0
        ),
        max_jump_pixels=(
            float(jumps.max()) if len(jumps) else 0.0
        ),
        median_area_pixels=float(
            np.median([node.area for node in nodes])
        ),
        median_circularity=float(
            np.median([node.circularity for node in nodes])
        ),
        p25_circularity=float(
            np.quantile(
                [node.circularity for node in nodes],
                0.25,
            )
        ),
        median_contrast=float(
            np.median([node.contrast for node in nodes])
        ),
        p25_contrast=float(
            np.quantile(
                [node.contrast for node in nodes],
                0.25,
            )
        ),
        mean_prior_distance_pixels=float(
            np.mean(
                [node.prior_distance for node in nodes]
            )
        ),
    )


def _classify_track(metrics: TrackMetrics | None) -> str:
    if metrics is None:
        return "not-established"

    if (
        metrics.span_frame_count >= 120
        and metrics.coverage_fraction >= 0.80
        and metrics.median_circularity >= 0.65
        and metrics.p25_circularity >= 0.50
        and metrics.median_contrast >= 30.0
        and metrics.p25_contrast >= 20.0
        and metrics.mean_jump_pixels <= 4.0
        and metrics.max_gap <= 3
    ):
        return "intermittent-candidate"

    return "not-established"


def _write_pgm(
    path: Path,
    mask: np.ndarray,
    x0: int,
    y0: int,
) -> str:
    canvas = np.zeros((750, 550), dtype=np.uint8)
    height, width = mask.shape
    canvas[
        y0 : y0 + height,
        x0 : x0 + width,
    ][mask.astype(bool)] = 255

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        b"P5\n550 750\n255\n"
        + canvas.tobytes()
    )
    path.write_bytes(payload)
    return sha256(payload).hexdigest()


def _metrics_json(
    metrics: TrackMetrics | None,
) -> dict[str, object] | None:
    if metrics is None:
        return None

    return {
        "nodeCount": metrics.node_count,
        "spanFrameCount": metrics.span_frame_count,
        "coverageFraction": metrics.coverage_fraction,
        "firstGlobalFrameIndex": metrics.first_global_frame_index,
        "lastGlobalFrameIndex": metrics.last_global_frame_index,
        "firstSourceFilename": _source_filename(
            metrics.first_global_frame_index
        ),
        "lastSourceFilename": _source_filename(
            metrics.last_global_frame_index
        ),
        "meanGap": metrics.mean_gap,
        "maxGap": metrics.max_gap,
        "meanJumpSourcePixels": metrics.mean_jump_pixels,
        "maxJumpSourcePixels": metrics.max_jump_pixels,
        "medianAreaPixels": metrics.median_area_pixels,
        "medianCircularity": metrics.median_circularity,
        "p25Circularity": metrics.p25_circularity,
        "medianContrast": metrics.median_contrast,
        "p25Contrast": metrics.p25_contrast,
        "meanPriorDistanceSourcePixels": (
            metrics.mean_prior_distance_pixels
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bone-report",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--atlas-root",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--cryo-root",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        required=True,
    )
    args = parser.parse_args()

    bone_report = json.loads(
        args.bone_report.read_text(encoding="utf-8")
    )
    bone_tracks = _bone_tracks(bone_report)
    atlas = {
        label: _read_ascii_ply_vertices(
            args.atlas_root / f"{label}.ply"
        )
        for label in (
            "radius",
            "ulna",
            *VESSELS,
        )
    }

    (
        proximal_z,
        distal_z,
        orientation,
        priors,
        diagnostics,
    ) = _optimize_local_pair_prior(
        args.cryo_root,
        atlas,
        bone_tracks,
    )

    arterial_results: list[dict[str, object]] = []

    for label in ("radial_artery", "ulnar_artery"):
        candidates_by_frame: list[list[Candidate]] = []
        for global_index in range(FRAME_COUNT):
            image = np.asarray(
                Image.open(
                    args.cryo_root
                    / _source_filename(global_index)
                ).convert("RGB")
            )
            candidates_by_frame.append(
                _extract_candidates(
                    image,
                    priors[label][global_index],
                )
            )

        path = _best_track(candidates_by_frame)
        metrics = _track_metrics(
            path,
            candidates_by_frame,
        )
        classification = _classify_track(metrics)

        mask_files: list[dict[str, object]] = []
        if classification == "intermittent-candidate":
            for frame_index, candidate_index in path:
                candidate = candidates_by_frame[
                    frame_index
                ][candidate_index]
                filename = _source_filename(frame_index)
                target = (
                    args.output_root
                    / "masks"
                    / label
                    / f"{Path(filename).stem}.pgm"
                )
                digest = _write_pgm(
                    target,
                    candidate.mask,
                    candidate.x0,
                    candidate.y0,
                )
                mask_files.append(
                    {
                        "globalFrameIndex": frame_index,
                        "sourceFilename": filename,
                        "centroidSourcePixels": {
                            "x": candidate.x,
                            "y": candidate.y,
                        },
                        "areaPixels": candidate.area,
                        "circularity": candidate.circularity,
                        "contrast": candidate.contrast,
                        "priorDistanceSourcePixels": (
                            candidate.prior_distance
                        ),
                        "maskPath": str(
                            target.relative_to(
                                args.output_root
                            )
                        ),
                        "maskSha256": digest,
                    }
                )

        arterial_results.append(
            {
                "draftLabel": label,
                "anatomicalId": SEMANTIC_IDS[label],
                "classification": classification,
                "candidateTrackStatus": (
                    "source-image-supported-intermittent-v0-track"
                    if classification
                    == "intermittent-candidate"
                    else "diagnostic-track-rejected"
                ),
                "atlasPriorTissueSupport": (
                    diagnostics[label]
                ),
                "trackMetrics": _metrics_json(metrics),
                "maskFrameCount": len(mask_files),
                "maskFiles": mask_files,
            }
        )

    vein_results = [
        {
            "draftLabel": label,
            "anatomicalId": SEMANTIC_IDS[label],
            "classification": "not-established",
            "priorStatus": (
                "rejected-by-source-tissue-support"
            ),
            "atlasPriorTissueSupport": diagnostics[label],
            "reason": (
                "cross-subject named-vein atlas prior is "
                "insufficiently supported by VHP source-image "
                "tissue at the predicted trajectory"
            ),
        }
        for label in ("cephalic_vein", "basilic_vein")
    ]

    report = {
        "schema": (
            "ph-a06-source-evidence-vessel-candidate-report.v1"
        ),
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
        "registration": {
            "method": (
                "slice-local radius-ulna pair atlas prior "
                "with source-image support optimization"
            ),
            "proximalAtlasZ": proximal_z,
            "distalAtlasZ": distal_z,
            "orientation": orientation,
            "searchRadiusSourcePixels": SEARCH_RADIUS,
            "selectionEvidence": (
                "arterial tissue and muscle-like support "
                "on VHP a-slices"
            ),
            "atlasGeometryUsedAsSubjectGeometry": False,
        },
        "support": {
            "firstGlobalFrameIndex": FIRST_GLOBAL_FRAME,
            "lastGlobalFrameIndex": LAST_GLOBAL_FRAME,
            "firstSourceFilename": FIRST_SOURCE_FILE,
            "lastSourceFilename": LAST_SOURCE_FILE,
            "supportedFrameCount": FRAME_COUNT,
            "outsideSupportDisposition": (
                "not-evaluated-by-this-pass"
            ),
        },
        "arteries": arterial_results,
        "namedSuperficialVeinPriors": vein_results,
        "superficialTargetVein": {
            "classification": "not-established",
            "anatomicalId": None,
            "reason": (
                "cephalic and basilic atlas priors are not "
                "sufficiently source-supported to assign the "
                "procedural target vein identity"
            ),
        },
        "claims": {
            "humanEdited": False,
            "anatomicallyReviewed": False,
            "medicalValidation": False,
            "completeVesselExtent": False,
            "vesselCenterlineEstablished": False,
            "boundaryLumenEstablished": False,
            "superficialTargetVeinIdentityEstablished": False,
            "patientSpaceGeometry": False,
            "automaticPromotionAllowed": False,
        },
        "software": {
            "numpyVersion": np.__version__,
            "opencvVersion": cv2.__version__,
        },
    }

    args.output_root.mkdir(
        parents=True,
        exist_ok=True,
    )
    destination = (
        args.output_root
        / "a06-source-evidence-vessel-candidate-report.v0.json"
    )
    destination.write_text(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "registration": report["registration"],
                "arteries": [
                    {
                        "draftLabel": row["draftLabel"],
                        "classification": row["classification"],
                        "trackMetrics": row["trackMetrics"],
                        "maskFrameCount": row["maskFrameCount"],
                    }
                    for row in arterial_results
                ],
                "namedSuperficialVeinPriors": (
                    vein_results
                ),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
