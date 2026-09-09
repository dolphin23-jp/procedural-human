from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from math import hypot, log, pi
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


FRAME_COUNT = 451
MAX_TRACK_GAP = 3
MAX_CANDIDATES_PER_FRAME = 80
SEARCH_DEPTH_MIN = 3.0
SEARCH_DEPTH_MAX = 75.0
COMPONENT_AREA_MIN = 5
COMPONENT_AREA_MAX = 320
BASE_JUMP_PER_FRAME = 5.0
JUMP_BUFFER = 2.0


class SuperficialVeinDiscoveryError(RuntimeError):
    pass


@dataclass
class Candidate:
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
    threshold: float
    score: float


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
    if mask.shape != (750, 550):
        raise SuperficialVeinDiscoveryError(
            f"unexpected mask dimensions for {path}: {mask.shape}"
        )
    return mask


def _local_ring_contrast(
    luminance: np.ndarray,
    component_mask: np.ndarray,
) -> float:
    kernel = np.ones((3, 3), dtype=np.uint8)
    dilated = cv2.dilate(
        component_mask.astype(np.uint8),
        kernel,
        iterations=3,
    ).astype(bool)
    ring = dilated & ~component_mask
    if not bool(ring.any()):
        return 0.0
    return float(luminance[ring].mean() - luminance[component_mask].mean())


def _candidate_score(candidate: Candidate) -> float:
    area_target = 45.0
    area_penalty = abs(log((candidate.area + 1) / area_target))
    depth_penalty = abs(candidate.skin_depth - 28.0) / 28.0
    chroma = max(
        candidate.mean_r,
        candidate.mean_g,
        candidate.mean_b,
    ) - min(
        candidate.mean_r,
        candidate.mean_g,
        candidate.mean_b,
    )
    dark_red_blue_bonus = max(
        0.0,
        (candidate.mean_r - candidate.mean_g) / 30.0,
    ) + max(
        0.0,
        (candidate.mean_b - candidate.mean_g) / 30.0,
    )
    return (
        1.0
        + 0.045 * min(candidate.contrast, 80.0)
        + 0.9 * min(candidate.circularity, 1.2)
        + 0.15 * min(chroma / 20.0, 2.0)
        + 0.20 * min(dark_red_blue_bonus, 2.0)
        - 0.45 * area_penalty
        - 0.35 * depth_penalty
    )


def _extract_candidates(
    frame_index: int,
    source_filename: str,
    image: np.ndarray,
    skin: np.ndarray,
    subcutaneous: np.ndarray,
) -> list[Candidate]:
    if image.shape != (750, 550, 3):
        raise SuperficialVeinDiscoveryError(
            f"unexpected source dimensions for {source_filename}: {image.shape}"
        )

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
        & (skin_distance >= SEARCH_DEPTH_MIN)
        & (skin_distance <= SEARCH_DEPTH_MAX)
    )
    eligible_values = luminance[eligible]
    if len(eligible_values) < 100:
        return []

    threshold = min(
        115.0,
        float(np.quantile(eligible_values, 0.16)),
    )
    dark = eligible & (luminance <= threshold)

    count, labels, stats, centroids = cv2.connectedComponentsWithStats(
        dark.astype(np.uint8),
        connectivity=8,
    )
    candidates: list[Candidate] = []
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if not COMPONENT_AREA_MIN <= area <= COMPONENT_AREA_MAX:
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
        if circularity < 0.10:
            continue

        contrast = _local_ring_contrast(luminance, component)
        if contrast < 7.0:
            continue

        cx, cy = map(float, centroids[label])
        xi = int(round(cx))
        yi = int(round(cy))
        if not (0 <= xi < 550 and 0 <= yi < 750):
            continue
        depth = float(skin_distance[yi, xi])

        pixels = values[component]
        mean_rgb = pixels.mean(axis=0)
        mean_r, mean_g, mean_b = map(float, mean_rgb)
        if mean_b > mean_r + 45 and mean_b > mean_g + 35:
            continue

        candidate = Candidate(
            frame_index=frame_index,
            source_filename=source_filename,
            x=cx,
            y=cy,
            area=area,
            circularity=float(circularity),
            contrast=contrast,
            skin_depth=depth,
            mean_r=mean_r,
            mean_g=mean_g,
            mean_b=mean_b,
            threshold=threshold,
            score=0.0,
        )
        candidate.score = _candidate_score(candidate)
        candidates.append(candidate)

    candidates.sort(key=lambda item: item.score, reverse=True)
    return candidates[:MAX_CANDIDATES_PER_FRAME]


def _transition_score(left: Candidate, right: Candidate, gap: int) -> float | None:
    jump = hypot(right.x - left.x, right.y - left.y)
    if jump > BASE_JUMP_PER_FRAME * gap + JUMP_BUFFER:
        return None

    area_change = abs(log((right.area + 1) / (left.area + 1)))
    depth_change = abs(right.skin_depth - left.skin_depth)
    color_change = (
        abs(right.mean_r - left.mean_r)
        + abs(right.mean_g - left.mean_g)
        + abs(right.mean_b - left.mean_b)
    ) / 3.0

    return (
        -0.28 * jump
        -0.35 * area_change
        -0.025 * depth_change
        -0.012 * color_change
        -0.85 * (gap - 1)
    )


def _best_track(
    candidates_by_frame: list[list[Candidate]],
    banned: set[tuple[int, int]],
) -> list[tuple[int, int]]:
    states: dict[
        tuple[int, int],
        tuple[float, tuple[int, int] | None],
    ] = {}
    best_end: tuple[int, int] | None = None

    for frame_index, candidates in enumerate(candidates_by_frame):
        for candidate_index, candidate in enumerate(candidates):
            key = (frame_index, candidate_index)
            if key in banned:
                continue

            best_score = candidate.score
            predecessor: tuple[int, int] | None = None

            for gap in range(1, MAX_TRACK_GAP + 1):
                previous_frame = frame_index - gap
                if previous_frame < 0:
                    continue
                for previous_index, previous_candidate in enumerate(
                    candidates_by_frame[previous_frame]
                ):
                    previous_key = (previous_frame, previous_index)
                    if previous_key in banned:
                        continue
                    state = states.get(previous_key)
                    if state is None:
                        continue
                    transition = _transition_score(
                        previous_candidate,
                        candidate,
                        gap,
                    )
                    if transition is None:
                        continue
                    score = state[0] + candidate.score + transition
                    if score > best_score:
                        best_score = score
                        predecessor = previous_key

            states[key] = (best_score, predecessor)
            if best_end is None or best_score > states[best_end][0]:
                best_end = key

    if best_end is None:
        return []

    path: list[tuple[int, int]] = []
    current: tuple[int, int] | None = best_end
    while current is not None:
        path.append(current)
        current = states[current][1]
    return list(reversed(path))


def _track_summary(
    rank: int,
    path: list[tuple[int, int]],
    candidates_by_frame: list[list[Candidate]],
) -> dict[str, object]:
    nodes = [
        candidates_by_frame[frame][index]
        for frame, index in path
    ]
    frames = np.asarray([node.frame_index for node in nodes], dtype=int)
    points = np.asarray([[node.x, node.y] for node in nodes], dtype=float)
    gaps = np.diff(frames)
    jumps = (
        np.linalg.norm(np.diff(points, axis=0), axis=1)
        if len(points) > 1
        else np.asarray([], dtype=float)
    )
    span = int(frames[-1] - frames[0] + 1)

    summary = {
        "rank": rank,
        "nodeCount": len(nodes),
        "spanFrameCount": span,
        "coverageFraction": float(len(nodes) / span),
        "firstGlobalFrameIndex": int(frames[0]),
        "lastGlobalFrameIndex": int(frames[-1]),
        "firstSourceFilename": nodes[0].source_filename,
        "lastSourceFilename": nodes[-1].source_filename,
        "meanGap": float(gaps.mean()) if len(gaps) else 0.0,
        "maxGap": int(gaps.max()) if len(gaps) else 0,
        "meanJumpSourcePixels": float(jumps.mean()) if len(jumps) else 0.0,
        "maxJumpSourcePixels": float(jumps.max()) if len(jumps) else 0.0,
        "medianAreaPixels": float(np.median([node.area for node in nodes])),
        "medianCircularity": float(
            np.median([node.circularity for node in nodes])
        ),
        "p25Circularity": float(
            np.quantile([node.circularity for node in nodes], 0.25)
        ),
        "medianContrast": float(
            np.median([node.contrast for node in nodes])
        ),
        "p25Contrast": float(
            np.quantile([node.contrast for node in nodes], 0.25)
        ),
        "medianSkinDepthPixels": float(
            np.median([node.skin_depth for node in nodes])
        ),
        "p25SkinDepthPixels": float(
            np.quantile([node.skin_depth for node in nodes], 0.25)
        ),
        "p75SkinDepthPixels": float(
            np.quantile([node.skin_depth for node in nodes], 0.75)
        ),
        "meanNodeScore": float(
            np.mean([node.score for node in nodes])
        ),
        "nodes": [
            {
                "globalFrameIndex": node.frame_index,
                "sourceFilename": node.source_filename,
                "centroidSourcePixels": {
                    "x": node.x,
                    "y": node.y,
                },
                "areaPixels": node.area,
                "circularity": node.circularity,
                "contrast": node.contrast,
                "skinDepthPixels": node.skin_depth,
                "meanRgb": {
                    "r": node.mean_r,
                    "g": node.mean_g,
                    "b": node.mean_b,
                },
                "localDarkThreshold": node.threshold,
                "nodeScore": node.score,
            }
            for node in nodes
        ],
    }

    strong = (
        summary["spanFrameCount"] >= 90
        and summary["coverageFraction"] >= 0.75
        and summary["medianCircularity"] >= 0.35
        and summary["medianContrast"] >= 15.0
        and summary["meanJumpSourcePixels"] <= 3.5
        and summary["maxGap"] <= 3
        and 4.0 <= summary["medianSkinDepthPixels"] <= 65.0
    )
    summary["discoveryClassification"] = (
        "continuous-superficial-vessel-track-candidate"
        if strong
        else "diagnostic-track-only"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--a05-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()

    names = _source_filenames()
    candidates_by_frame: list[list[Candidate]] = []
    candidate_counts: list[int] = []

    for frame_index, source_filename in enumerate(names):
        image = np.asarray(
            Image.open(args.source_root / source_filename).convert("RGB")
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
        candidates = _extract_candidates(
            frame_index,
            source_filename,
            image,
            skin,
            subcutaneous,
        )
        candidates_by_frame.append(candidates)
        candidate_counts.append(len(candidates))

    tracks: list[dict[str, object]] = []
    banned: set[tuple[int, int]] = set()
    for rank in range(1, 6):
        path = _best_track(candidates_by_frame, banned)
        if not path:
            break
        summary = _track_summary(rank, path, candidates_by_frame)
        tracks.append(summary)

        selected_points = [
            candidates_by_frame[frame][index]
            for frame, index in path
        ]
        selected_by_frame = {
            node.frame_index: node for node in selected_points
        }
        for frame_index, candidates in enumerate(candidates_by_frame):
            reference = selected_by_frame.get(frame_index)
            if reference is None:
                continue
            for candidate_index, candidate in enumerate(candidates):
                if hypot(
                    candidate.x - reference.x,
                    candidate.y - reference.y,
                ) <= 12.0:
                    banned.add((frame_index, candidate_index))

    report = {
        "schema": "ph-a06-superficial-vessel-source-discovery.v1",
        "schemaVersion": "1",
        "task": "TASK-A06",
        "recordedAt": "2026-09-09",
        "coordinateSpace": {
            "kind": "source-image-stack",
            "patientSpaceClaim": False,
        },
        "searchDefinition": {
            "sourceConstraint": (
                "A05 V0 subcutaneous_soft_tissue candidate mask"
            ),
            "skinDepthRangePixels": [
                SEARCH_DEPTH_MIN,
                SEARCH_DEPTH_MAX,
            ],
            "componentAreaRangePixels": [
                COMPONENT_AREA_MIN,
                COMPONENT_AREA_MAX,
            ],
            "maxTrackGapFrames": MAX_TRACK_GAP,
            "maxCandidatesPerFrame": MAX_CANDIDATES_PER_FRAME,
            "atlasPriorUsed": False,
            "namedVeinIdentityUsed": False,
        },
        "candidateStatistics": {
            "frameCount": FRAME_COUNT,
            "framesWithAtLeastOneCandidate": int(
                sum(count > 0 for count in candidate_counts)
            ),
            "meanCandidatesPerFrame": float(np.mean(candidate_counts)),
            "medianCandidatesPerFrame": float(np.median(candidate_counts)),
            "maxCandidatesPerFrameObserved": int(max(candidate_counts)),
        },
        "tracks": tracks,
        "disposition": {
            "superficialTargetVeinAnatomicalId": None,
            "targetIdentityEstablished": False,
            "maskGenerationAllowed": False,
            "reason": (
                "discovery pass only; a stable source-derived superficial vessel "
                "track may justify a later bounded candidate pass, but this pass "
                "does not establish named vein identity or procedural target binding"
            ),
        },
        "claims": {
            "humanEdited": False,
            "anatomicallyReviewed": False,
            "medicalValidation": False,
            "namedVeinIdentityEstablished": False,
            "superficialTargetVeinIdentityEstablished": False,
            "vesselMaskGenerated": False,
            "centerlineGenerated": False,
            "patientSpaceGeometry": False,
            "automaticPromotionAllowed": False,
        },
    }

    args.output_root.mkdir(parents=True, exist_ok=True)
    (
        args.output_root
        / "a06-superficial-vessel-source-discovery.v0.json"
    ).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "candidateStatistics": report["candidateStatistics"],
                "tracks": [
                    {
                        key: track[key]
                        for key in (
                            "rank",
                            "discoveryClassification",
                            "nodeCount",
                            "spanFrameCount",
                            "coverageFraction",
                            "firstSourceFilename",
                            "lastSourceFilename",
                            "meanJumpSourcePixels",
                            "maxJumpSourcePixels",
                            "medianAreaPixels",
                            "medianCircularity",
                            "medianContrast",
                            "medianSkinDepthPixels",
                        )
                    }
                    for track in tracks
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
