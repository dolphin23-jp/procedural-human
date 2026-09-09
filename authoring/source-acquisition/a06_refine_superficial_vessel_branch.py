from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
from math import hypot, pi
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


FRAME_COUNT = 451
SOURCE_WIDTH = 550
SOURCE_HEIGHT = 750

SELECT_MAX_MEDIAN_SKIN_DEPTH = 20.0
SELECT_MIN_MEDIAN_CONTRAST = 25.0
SELECT_MIN_COVERAGE = 0.85

STRICT_NODE_MAX_SKIN_DEPTH = 25.0
STRICT_NODE_MIN_CONTRAST = 20.0
STRICT_NODE_MIN_CIRCULARITY = 0.25
STRICT_NODE_MAX_AREA = 160

STRICT_MAX_GAP = 3
STRICT_MAX_JUMP_PER_FRAME = 4.5
STRICT_MAX_DEPTH_CHANGE_PER_FRAME = 8.0

RECOVERY_MAX_DISTANCE = 5.0
RECOVERY_MIN_CONTRAST = 20.0
RECOVERY_MIN_CIRCULARITY = 0.30
RECOVERY_MAX_SKIN_DEPTH = 25.0
RECOVERY_MAX_AREA = 160

MIN_CONTINUOUS_FRAME_COUNT = 60
FINAL_MAX_JUMP = 5.0
FINAL_MAX_MEAN_JUMP = 2.5
FINAL_MAX_MEDIAN_SKIN_DEPTH = 15.0
FINAL_MIN_MEDIAN_CONTRAST = 30.0
FINAL_MIN_P25_CONTRAST = 20.0
FINAL_MIN_MEDIAN_CIRCULARITY = 0.40
FINAL_MIN_P25_CIRCULARITY = 0.30


class SuperficialBranchRefinementError(RuntimeError):
    pass


@dataclass
class SourceCandidate:
    frame_index: int
    source_filename: str
    x: float
    y: float
    area: int
    circularity: float
    contrast: float
    skin_depth: float
    mean_r: float
    mean_g: float
    mean_b: float
    mask: np.ndarray


def _source_filenames() -> list[str]:
    names: list[str] = []
    for position in range(1567, 1717):
        for suffix in ("a", "b", "c"):
            names.append(f"avf{position:04d}{suffix}.png")
    names.append("avf1717a.png")
    if len(names) != FRAME_COUNT:
        raise AssertionError("unexpected source frame count")
    return names


def _mask_filename(source_filename: str) -> str:
    return f"{Path(source_filename).stem}.pgm"


def _load_mask(path: Path) -> np.ndarray:
    mask = np.asarray(Image.open(path).convert("L")) > 0
    if mask.shape != (SOURCE_HEIGHT, SOURCE_WIDTH):
        raise SuperficialBranchRefinementError(
            f"unexpected mask dimensions for {path}: {mask.shape}"
        )
    return mask


def _ring_contrast(
    luminance: np.ndarray,
    component: np.ndarray,
) -> float:
    dilated = cv2.dilate(
        component.astype(np.uint8),
        np.ones((3, 3), dtype=np.uint8),
        iterations=3,
    ).astype(bool)
    ring = dilated & ~component
    if not bool(ring.any()):
        return 0.0
    return float(
        luminance[ring].mean() - luminance[component].mean()
    )


def _select_discovery_track(
    discovery: dict[str, object],
) -> dict[str, object]:
    tracks = discovery.get("tracks")
    if not isinstance(tracks, list):
        raise SuperficialBranchRefinementError(
            "discovery report has no tracks"
        )

    eligible: list[dict[str, object]] = []
    for track in tracks:
        if not isinstance(track, dict):
            continue
        if (
            float(track["medianSkinDepthPixels"])
            <= SELECT_MAX_MEDIAN_SKIN_DEPTH
            and float(track["medianContrast"])
            >= SELECT_MIN_MEDIAN_CONTRAST
            and float(track["coverageFraction"])
            >= SELECT_MIN_COVERAGE
        ):
            eligible.append(track)

    if not eligible:
        raise SuperficialBranchRefinementError(
            "no shallow high-contrast source-derived track qualifies for refinement"
        )

    eligible.sort(
        key=lambda track: (
            float(track["medianContrast"])
            * float(track["medianCircularity"])
            * float(track["coverageFraction"])
            * min(float(track["spanFrameCount"]), 120.0)
            / max(float(track["medianSkinDepthPixels"]), 3.0)
        ),
        reverse=True,
    )
    selected = eligible[0]
    if int(selected["rank"]) != 3:
        raise SuperficialBranchRefinementError(
            f"expected deterministic shallow source track rank 3, got rank {selected['rank']}"
        )
    return selected


def _strict_segments(
    track: dict[str, object],
) -> list[list[dict[str, object]]]:
    raw_nodes = track.get("nodes")
    if not isinstance(raw_nodes, list):
        raise SuperficialBranchRefinementError(
            "selected discovery track has no nodes"
        )

    nodes: list[dict[str, object]] = []
    for node in raw_nodes:
        if not isinstance(node, dict):
            continue
        if (
            float(node["skinDepthPixels"])
            <= STRICT_NODE_MAX_SKIN_DEPTH
            and float(node["contrast"])
            >= STRICT_NODE_MIN_CONTRAST
            and float(node["circularity"])
            >= STRICT_NODE_MIN_CIRCULARITY
            and int(node["areaPixels"])
            <= STRICT_NODE_MAX_AREA
        ):
            nodes.append(node)

    nodes.sort(key=lambda node: int(node["globalFrameIndex"]))
    if not nodes:
        return []

    segments: list[list[dict[str, object]]] = []
    current = [nodes[0]]
    for node in nodes[1:]:
        left = current[-1]
        left_frame = int(left["globalFrameIndex"])
        right_frame = int(node["globalFrameIndex"])
        gap = right_frame - left_frame

        left_xy = left["centroidSourcePixels"]
        right_xy = node["centroidSourcePixels"]
        if not isinstance(left_xy, dict) or not isinstance(right_xy, dict):
            raise SuperficialBranchRefinementError(
                "track centroid is malformed"
            )
        jump = hypot(
            float(right_xy["x"]) - float(left_xy["x"]),
            float(right_xy["y"]) - float(left_xy["y"]),
        )
        depth_change = abs(
            float(node["skinDepthPixels"])
            - float(left["skinDepthPixels"])
        )

        acceptable = (
            1 <= gap <= STRICT_MAX_GAP
            and jump / gap <= STRICT_MAX_JUMP_PER_FRAME
            and depth_change / gap <= STRICT_MAX_DEPTH_CHANGE_PER_FRAME
        )
        if acceptable:
            current.append(node)
        else:
            segments.append(current)
            current = [node]
    segments.append(current)

    return sorted(
        segments,
        key=lambda segment: (
            int(segment[-1]["globalFrameIndex"])
            - int(segment[0]["globalFrameIndex"])
            + 1,
            len(segment),
        ),
        reverse=True,
    )


def _expected_position(
    frame_index: int,
    direct: dict[int, dict[str, object]],
) -> tuple[float, float, str]:
    if frame_index in direct:
        centroid = direct[frame_index]["centroidSourcePixels"]
        if not isinstance(centroid, dict):
            raise SuperficialBranchRefinementError(
                "direct centroid is malformed"
            )
        return (
            float(centroid["x"]),
            float(centroid["y"]),
            "direct-track-node",
        )

    left_frames = [frame for frame in direct if frame < frame_index]
    right_frames = [frame for frame in direct if frame > frame_index]
    if not left_frames or not right_frames:
        raise SuperficialBranchRefinementError(
            f"frame {frame_index} is not bracketed by direct track nodes"
        )
    left_frame = max(left_frames)
    right_frame = min(right_frames)
    if right_frame - left_frame > STRICT_MAX_GAP:
        raise SuperficialBranchRefinementError(
            f"gap around frame {frame_index} is too wide for source recovery"
        )

    left = direct[left_frame]["centroidSourcePixels"]
    right = direct[right_frame]["centroidSourcePixels"]
    if not isinstance(left, dict) or not isinstance(right, dict):
        raise SuperficialBranchRefinementError(
            "bracketing centroid is malformed"
        )

    fraction = (frame_index - left_frame) / (right_frame - left_frame)
    return (
        float(left["x"])
        + (float(right["x"]) - float(left["x"])) * fraction,
        float(left["y"])
        + (float(right["y"]) - float(left["y"])) * fraction,
        "interpolated-track-prior",
    )


def _extract_near_expected(
    *,
    frame_index: int,
    source_filename: str,
    image: np.ndarray,
    skin: np.ndarray,
    subcutaneous: np.ndarray,
    expected_x: float,
    expected_y: float,
) -> SourceCandidate:
    values = image.astype(np.float32)
    red, green, blue = (
        values[:, :, 0],
        values[:, :, 1],
        values[:, :, 2],
    )
    luminance = 0.299 * red + 0.587 * green + 0.114 * blue

    non_skin = (~skin).astype(np.uint8)
    skin_distance = cv2.distanceTransform(
        non_skin,
        cv2.DIST_L2,
        5,
    )
    eligible = (
        subcutaneous
        & (skin_distance >= 3.0)
        & (skin_distance <= RECOVERY_MAX_SKIN_DEPTH)
    )
    eligible_values = luminance[eligible]
    if len(eligible_values) < 100:
        raise SuperficialBranchRefinementError(
            f"insufficient subcutaneous evidence at {source_filename}"
        )

    threshold = min(
        115.0,
        float(np.quantile(eligible_values, 0.16)),
    )
    dark = eligible & (luminance <= threshold)
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(
        dark.astype(np.uint8),
        connectivity=8,
    )

    candidates: list[SourceCandidate] = []
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if not 5 <= area <= RECOVERY_MAX_AREA:
            continue

        component = labels == label
        contours, _ = cv2.findContours(
            component.astype(np.uint8),
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
        if circularity < RECOVERY_MIN_CIRCULARITY:
            continue

        contrast = _ring_contrast(luminance, component)
        if contrast < RECOVERY_MIN_CONTRAST:
            continue

        cx, cy = map(float, centroids[label])
        prior_distance = hypot(cx - expected_x, cy - expected_y)
        if prior_distance > RECOVERY_MAX_DISTANCE:
            continue

        xi = int(round(cx))
        yi = int(round(cy))
        if not (0 <= xi < SOURCE_WIDTH and 0 <= yi < SOURCE_HEIGHT):
            continue
        depth = float(skin_distance[yi, xi])
        if depth > RECOVERY_MAX_SKIN_DEPTH:
            continue

        mean_rgb = values[component].mean(axis=0)
        candidates.append(
            SourceCandidate(
                frame_index=frame_index,
                source_filename=source_filename,
                x=cx,
                y=cy,
                area=area,
                circularity=float(circularity),
                contrast=contrast,
                skin_depth=depth,
                mean_r=float(mean_rgb[0]),
                mean_g=float(mean_rgb[1]),
                mean_b=float(mean_rgb[2]),
                mask=component,
            )
        )

    if not candidates:
        raise SuperficialBranchRefinementError(
            f"no source-image candidate recovers {source_filename} near "
            f"({expected_x:.2f}, {expected_y:.2f})"
        )

    return min(
        candidates,
        key=lambda candidate: (
            hypot(
                candidate.x - expected_x,
                candidate.y - expected_y,
            ),
            -candidate.contrast,
            -candidate.circularity,
        ),
    )


def _write_pgm(path: Path, mask: np.ndarray) -> str:
    payload = mask.astype(np.uint8) * 255
    header = b"P5\n550 750\n255\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + payload.tobytes())
    return sha256(header + payload.tobytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--discovery-report", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--a05-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()

    discovery = json.loads(
        args.discovery_report.read_text(encoding="utf-8")
    )
    selected_track = _select_discovery_track(discovery)
    segments = _strict_segments(selected_track)
    if not segments:
        raise SuperficialBranchRefinementError(
            "selected source track has no strict continuous segment"
        )

    segment = segments[0]
    first_frame = int(segment[0]["globalFrameIndex"])
    last_frame = int(segment[-1]["globalFrameIndex"])
    span = last_frame - first_frame + 1
    if span < MIN_CONTINUOUS_FRAME_COUNT:
        raise SuperficialBranchRefinementError(
            f"strict superficial segment is too short: {span} frames"
        )

    direct = {
        int(node["globalFrameIndex"]): node
        for node in segment
    }
    names = _source_filenames()

    recovered: list[SourceCandidate] = []
    evidence_kinds: list[str] = []
    mask_records: list[dict[str, object]] = []
    for frame_index in range(first_frame, last_frame + 1):
        source_filename = names[frame_index]
        expected_x, expected_y, prior_kind = _expected_position(
            frame_index,
            direct,
        )

        image = np.asarray(
            Image.open(
                args.source_root / source_filename
            ).convert("RGB")
        )
        skin = _load_mask(
            args.a05_root
            / "masks"
            / "skin"
            / _mask_filename(source_filename)
        )
        subcutaneous = _load_mask(
            args.a05_root
            / "masks"
            / "subcutaneous_soft_tissue"
            / _mask_filename(source_filename)
        )
        candidate = _extract_near_expected(
            frame_index=frame_index,
            source_filename=source_filename,
            image=image,
            skin=skin,
            subcutaneous=subcutaneous,
            expected_x=expected_x,
            expected_y=expected_y,
        )
        recovered.append(candidate)
        evidence_kind = (
            "source-redetected-direct-track-node"
            if prior_kind == "direct-track-node"
            else "source-recovered-interpolated-gap"
        )
        evidence_kinds.append(evidence_kind)

        mask_path = (
            args.output_root
            / "masks"
            / "superficial_vessel_branch_candidate_1"
            / f"{Path(source_filename).stem}.pgm"
        )
        mask_sha = _write_pgm(mask_path, candidate.mask)
        mask_records.append(
            {
                "globalFrameIndex": frame_index,
                "sourceFilename": source_filename,
                "evidenceKind": evidence_kind,
                "centroidSourcePixels": {
                    "x": candidate.x,
                    "y": candidate.y,
                },
                "areaPixels": candidate.area,
                "circularity": candidate.circularity,
                "contrast": candidate.contrast,
                "skinDepthPixels": candidate.skin_depth,
                "meanRgb": {
                    "r": candidate.mean_r,
                    "g": candidate.mean_g,
                    "b": candidate.mean_b,
                },
                "maskPath": str(
                    mask_path.relative_to(args.output_root)
                ),
                "maskSha256": mask_sha,
            }
        )

    points = np.asarray(
        [[item.x, item.y] for item in recovered],
        dtype=float,
    )
    jumps = np.linalg.norm(np.diff(points, axis=0), axis=1)
    circularity = np.asarray(
        [item.circularity for item in recovered],
        dtype=float,
    )
    contrast = np.asarray(
        [item.contrast for item in recovered],
        dtype=float,
    )
    depth = np.asarray(
        [item.skin_depth for item in recovered],
        dtype=float,
    )
    area = np.asarray(
        [item.area for item in recovered],
        dtype=float,
    )

    metrics = {
        "frameCount": len(recovered),
        "firstGlobalFrameIndex": first_frame,
        "lastGlobalFrameIndex": last_frame,
        "firstSourceFilename": names[first_frame],
        "lastSourceFilename": names[last_frame],
        "directDiscoveryNodeCount": len(direct),
        "sourceRecoveredGapFrameCount": int(
            sum(
                kind == "source-recovered-interpolated-gap"
                for kind in evidence_kinds
            )
        ),
        "coverageFraction": 1.0,
        "meanJumpSourcePixels": float(jumps.mean()),
        "maxJumpSourcePixels": float(jumps.max()),
        "medianAreaPixels": float(np.median(area)),
        "medianCircularity": float(np.median(circularity)),
        "p25Circularity": float(np.quantile(circularity, 0.25)),
        "medianContrast": float(np.median(contrast)),
        "p25Contrast": float(np.quantile(contrast, 0.25)),
        "minimumContrast": float(contrast.min()),
        "medianSkinDepthPixels": float(np.median(depth)),
        "p25SkinDepthPixels": float(np.quantile(depth, 0.25)),
        "p75SkinDepthPixels": float(np.quantile(depth, 0.75)),
        "maxSkinDepthPixels": float(depth.max()),
    }

    continuous = (
        metrics["frameCount"] >= MIN_CONTINUOUS_FRAME_COUNT
        and metrics["maxJumpSourcePixels"] <= FINAL_MAX_JUMP
        and metrics["meanJumpSourcePixels"] <= FINAL_MAX_MEAN_JUMP
        and metrics["medianSkinDepthPixels"]
        <= FINAL_MAX_MEDIAN_SKIN_DEPTH
        and metrics["medianContrast"] >= FINAL_MIN_MEDIAN_CONTRAST
        and metrics["p25Contrast"] >= FINAL_MIN_P25_CONTRAST
        and metrics["medianCircularity"]
        >= FINAL_MIN_MEDIAN_CIRCULARITY
        and metrics["p25Circularity"]
        >= FINAL_MIN_P25_CIRCULARITY
    )
    if not continuous:
        raise SuperficialBranchRefinementError(
            f"source-recovered bounded superficial segment fails final thresholds: {metrics}"
        )

    report = {
        "schema": "ph-a06-superficial-vessel-branch-candidate.v1",
        "schemaVersion": "1",
        "task": "TASK-A06",
        "recordedAt": "2026-09-09",
        "draftLabel": "superficial_vessel_branch_candidate_1",
        "classification": "continuous-superficial-vessel-branch-candidate",
        "coordinateSpace": {
            "kind": "source-image-stack",
            "patientSpaceClaim": False,
        },
        "selection": {
            "sourceDiscoveryArtifactId": 10106905106,
            "selectedDiscoveryRank": int(selected_track["rank"]),
            "selectionBasis": (
                "shallow subcutaneous depth, high local contrast, high coverage, "
                "and source-only continuity; no atlas or named-vein identity prior"
            ),
            "atlasPriorUsed": False,
            "namedVeinIdentityUsed": False,
        },
        "continuousSegment": metrics,
        "maskFrameCount": len(mask_records),
        "maskFiles": mask_records,
        "identityDisposition": {
            "anatomicalId": None,
            "vesselClass": "superficial-vessel-branch",
            "venousIdentityEstablished": False,
            "namedVeinIdentityEstablished": False,
            "proceduralTargetBindingAllowed": False,
            "reason": (
                "source evidence establishes a bounded superficial vascular-appearing "
                "branch candidate, but does not independently distinguish vein from a "
                "rare superficial arterial variant or establish cephalic/basilic identity"
            ),
        },
        "claims": {
            "humanEdited": False,
            "anatomicallyReviewed": False,
            "medicalValidation": False,
            "venousIdentityEstablished": False,
            "namedVeinIdentityEstablished": False,
            "completeVesselExtent": False,
            "patientSpaceGeometry": False,
            "automaticPromotionAllowed": False,
        },
    }

    args.output_root.mkdir(parents=True, exist_ok=True)
    (
        args.output_root
        / "a06-superficial-vessel-branch-candidate-v0.json"
    ).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "classification": report["classification"],
                "continuousSegment": metrics,
                "identityDisposition": report["identityDisposition"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
