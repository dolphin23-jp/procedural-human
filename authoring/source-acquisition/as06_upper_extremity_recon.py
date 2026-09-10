"""TASK-AS06 phase 1: same-subject proximal continuity reconnaissance.

This tool deliberately stays in Visible Human Female source-image-stack
coordinates. It extends from already reviewed distal source evidence and uses
same-subject cryosection continuity only. It does not create a Medical Master,
Patient Space geometry, or medical validation.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import io
import json
from math import hypot, log, pi
from pathlib import Path
from zipfile import ZipFile

import cv2
import numpy as np
from PIL import Image

A05_CROP_ORIGIN = np.asarray([1450.0, 250.0], dtype=float)
BONE_START_FILENAME = "avf1567a.png"
DEFAULT_FIRST_FILENAME = "avf1300a.png"
DEFAULT_LAST_FILENAME = "avf1646a.png"

BONE_SEEDS_FULL = {
    "radius": np.asarray([1787.0, 401.0], dtype=float),
    "ulna": np.asarray([1756.0, 505.0], dtype=float),
}
BONE_RULES = (
    (140.0, 115, 145),
    (135.0, 135, 135),
    (125.0, 150, 120),
)
BONE_SEARCH_RADIUS = 65
BONE_MIN_PIXELS = 300
BONE_MIN_SEPARATION = 16.0

VESSEL_SEARCH_RADIUS = 42
VESSEL_AREA_MIN = 6
VESSEL_AREA_MAX = 420
VESSEL_MAX_MISSES = 6


class ReconError(RuntimeError):
    pass


@dataclass(frozen=True)
class BoneComponent:
    area: int
    x: float
    y: float
    rule_index: int


@dataclass(frozen=True)
class VesselCandidate:
    area: int
    circularity: float
    contrast: float
    prior_distance: float
    x: float
    y: float
    mean_rgb: tuple[float, float, float]
    threshold: float


def path_sha256(path: Path) -> str:
    h = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def nominal_index(filename: str) -> int:
    if len(filename) != 12 or not filename.startswith("avf") or not filename.endswith(".png"):
        raise ReconError(f"unexpected source filename: {filename}")
    return int(filename[3:7])


class SourceArchive:
    def __init__(self, inventory_path: Path, index_path: Path, archive_root: Path):
        self.inventory_path = Path(inventory_path)
        self.index_path = Path(index_path)
        self.archive_root = Path(archive_root)
        self.inventory = json.loads(self.inventory_path.read_text())
        self.index = json.loads(self.index_path.read_text())
        if self.inventory["kind"] != "vhf-whole-body-inventory":
            raise ReconError("unexpected inventory kind")
        if self.index["kind"] != "vhf-source-archive-index" or not self.index["complete"]:
            raise ReconError("whole-body archive index is not complete")
        if self.index["inventorySha256"] != path_sha256(self.inventory_path):
            raise ReconError("archive index does not match inventory bytes")
        self.frames = self.inventory["frames"]
        self.by_name = {row["filename"]: row for row in self.frames}
        self.chunk_records = {row["index"]: row for row in self.index["chunks"]}
        self._verified: set[int] = set()
        self._zips: dict[int, ZipFile] = {}

    def close(self) -> None:
        for archive in self._zips.values():
            archive.close()

    def verify_chunk(self, chunk_index: int) -> Path:
        record = self.chunk_records.get(chunk_index)
        if record is None:
            raise ReconError(f"chunk {chunk_index} absent from verified index")
        path = self.archive_root / record["filename"]
        if not path.exists():
            raise ReconError(f"required source chunk not downloaded: {path.name}")
        if chunk_index not in self._verified:
            if path.stat().st_size != record["byteSize"]:
                raise ReconError(f"chunk byte-size mismatch: {path.name}")
            if path_sha256(path) != record["sha256"]:
                raise ReconError(f"chunk SHA-256 mismatch: {path.name}")
            self._verified.add(chunk_index)
        return path

    def read_rgb(self, filename: str) -> np.ndarray:
        row = self.by_name.get(filename)
        if row is None:
            raise ReconError(f"source filename absent from inventory: {filename}")
        if row["source"]["listedByteSize"] == 0:
            raise ReconError(f"source filename is provider-listed zero-byte: {filename}")
        chunk_index = row["chunkIndex"]
        if chunk_index not in self._zips:
            self._zips[chunk_index] = ZipFile(self.verify_chunk(chunk_index))
        data = self._zips[chunk_index].read(row["source"]["path"])
        if len(data) != row["source"]["listedByteSize"]:
            raise ReconError(f"source member byte-size mismatch: {filename}")
        with Image.open(io.BytesIO(data)) as image:
            if image.format != "PNG" or image.size != (2048, 1216):
                raise ReconError(f"unexpected source PNG geometry: {filename}")
            return np.asarray(image.convert("RGB"))


def bone_mask(image: np.ndarray, rule: tuple[float, int, int]) -> np.ndarray:
    brightness_min, saturation_max, red_min = rule
    rgb = image.astype(np.int16)
    brightness = rgb.mean(axis=2)
    saturation = rgb.max(axis=2) - rgb.min(axis=2)
    return (
        (brightness >= brightness_min)
        & (saturation <= saturation_max)
        & (rgb[:, :, 0] >= red_min)
    ).astype(np.uint8)


def local_bone_component(image: np.ndarray, prediction: np.ndarray) -> BoneComponent | None:
    height, width = image.shape[:2]
    radius = BONE_SEARCH_RADIUS
    x0 = max(0, int(prediction[0]) - radius)
    x1 = min(width, int(prediction[0]) + radius + 1)
    y0 = max(0, int(prediction[1]) - radius)
    y1 = min(height, int(prediction[1]) + radius + 1)
    crop = image[y0:y1, x0:x1]
    if crop.size == 0:
        return None
    yy, xx = np.ogrid[y0:y1, x0:x1]
    disk = (xx - prediction[0]) ** 2 + (yy - prediction[1]) ** 2 <= radius**2

    fallback: BoneComponent | None = None
    for rule_index, rule in enumerate(BONE_RULES):
        mask = bone_mask(crop, rule)
        mask[~disk] = 0
        count, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)
        options: list[tuple[float, BoneComponent]] = []
        for label in range(1, count):
            area = int(stats[label, cv2.CC_STAT_AREA])
            if area < 5:
                continue
            cx, cy = map(float, centroids[label])
            x = x0 + cx
            y = y0 + cy
            distance = hypot(x - prediction[0], y - prediction[1])
            component = BoneComponent(area=area, x=x, y=y, rule_index=rule_index)
            options.append((distance - min(area, 2500) / 700.0, component))
        if not options:
            continue
        component = min(options, key=lambda item: item[0])[1]
        if component.area >= BONE_MIN_PIXELS:
            return component
        fallback = component
    return fallback if fallback is not None and fallback.area >= 120 else None


def previous_a_filename(filename: str) -> str:
    return f"avf{nominal_index(filename)-1:04d}a.png"


def track_forearm_bones(source: SourceArchive, first_nominal: int) -> dict[str, object]:
    current = {key: value.copy() for key, value in BONE_SEEDS_FULL.items()}
    velocity = {key: np.zeros(2, dtype=float) for key in current}
    rows: list[dict[str, object]] = [
        {
            "sourceFilename": BONE_START_FILENAME,
            "nominalIndex": nominal_index(BONE_START_FILENAME),
            "radius": {"x": float(current["radius"][0]), "y": float(current["radius"][1])},
            "ulna": {"x": float(current["ulna"][0]), "y": float(current["ulna"][1])},
            "separationPixels": float(np.linalg.norm(current["radius"] - current["ulna"])),
            "evidenceKind": "existing-source-supported-cryo-seed",
        }
    ]
    stop_reason = "range-exhausted"
    failed_filename: str | None = None

    for position in range(nominal_index(BONE_START_FILENAME) - 1, first_nominal - 1, -1):
        filename = f"avf{position:04d}a.png"
        if filename not in source.by_name:
            stop_reason = "source-filename-missing"
            failed_filename = filename
            break
        image = source.read_rgb(filename)
        chosen: dict[str, BoneComponent] = {}
        for key in ("radius", "ulna"):
            prediction = current[key] + velocity[key]
            component = local_bone_component(image, prediction)
            if component is None:
                stop_reason = f"{key}-bone-support-ended"
                failed_filename = filename
                break
            chosen[key] = component
        if len(chosen) != 2:
            break

        radius_point = np.asarray([chosen["radius"].x, chosen["radius"].y])
        ulna_point = np.asarray([chosen["ulna"].x, chosen["ulna"].y])
        separation = float(np.linalg.norm(radius_point - ulna_point))
        if separation < BONE_MIN_SEPARATION:
            stop_reason = "radius-ulna-components-converged-or-ambiguous"
            failed_filename = filename
            break

        for key, point in (("radius", radius_point), ("ulna", ulna_point)):
            delta = point - current[key]
            velocity[key] = velocity[key] * 0.55 + delta * 0.45
            current[key] = point

        rows.append(
            {
                "sourceFilename": filename,
                "nominalIndex": position,
                "radius": {
                    "x": chosen["radius"].x,
                    "y": chosen["radius"].y,
                    "candidatePixels": chosen["radius"].area,
                    "appearanceRuleIndex": chosen["radius"].rule_index,
                },
                "ulna": {
                    "x": chosen["ulna"].x,
                    "y": chosen["ulna"].y,
                    "candidatePixels": chosen["ulna"].area,
                    "appearanceRuleIndex": chosen["ulna"].rule_index,
                },
                "separationPixels": separation,
                "evidenceKind": "same-subject-source-continuity",
            }
        )

    observed = rows[1:] if len(rows) > 1 else rows
    separations = [float(row["separationPixels"]) for row in observed]
    earliest = rows[-1]["sourceFilename"]
    return {
        "startSourceFilename": BONE_START_FILENAME,
        "earliestSupportedSourceFilename": earliest,
        "supportedASliceCount": len(rows),
        "stopReason": stop_reason,
        "firstUnsupportedOrAmbiguousSourceFilename": failed_filename,
        "minimumObservedSeparationPixels": min(separations) if separations else None,
        "medianObservedSeparationPixels": float(np.median(separations)) if separations else None,
        "rows": rows,
        "claims": {
            "completeRadiusExtent": False,
            "completeUlnaExtent": False,
            "humerusIdentityEstablished": False,
            "elbowLandmarkMedicallyValidated": False,
        },
    }


def is_tissue(rgb: np.ndarray) -> np.ndarray:
    values = rgb.astype(np.int16)
    red, green, blue = values[:, :, 0], values[:, :, 1], values[:, :, 2]
    blue_background = (blue > red + 18) & (blue > green + 8) & (blue > 55)
    too_dark = red + green + blue < 45
    return (~blue_background) & (~too_dark)


def vessel_candidates(
    image: np.ndarray,
    prior: np.ndarray,
    radius: int = VESSEL_SEARCH_RADIUS,
) -> list[VesselCandidate]:
    height, width = image.shape[:2]
    x, y = map(float, prior)
    x0 = max(0, int(np.floor(x - radius)))
    x1 = min(width, int(np.ceil(x + radius + 1)))
    y0 = max(0, int(np.floor(y - radius)))
    y1 = min(height, int(np.ceil(y + radius + 1)))
    crop = image[y0:y1, x0:x1]
    if crop.size == 0:
        return []

    yy, xx = np.ogrid[y0:y1, x0:x1]
    disk = (xx - x) ** 2 + (yy - y) ** 2 <= radius**2
    values = crop.astype(np.float32)
    red, green, blue = values[:, :, 0], values[:, :, 1], values[:, :, 2]
    luminance = 0.299 * red + 0.587 * green + 0.114 * blue
    tissue = is_tissue(crop)
    support = luminance[disk & tissue]
    if len(support) < 20:
        return []
    threshold = min(105.0, float(np.quantile(support, 0.18)))
    dark = (luminance <= threshold) & disk & tissue
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(
        dark.astype(np.uint8) * 255, 8
    )
    output: list[VesselCandidate] = []
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if not VESSEL_AREA_MIN <= area <= VESSEL_AREA_MAX:
            continue
        component = (labels == label).astype(np.uint8)
        contours, _ = cv2.findContours(component, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        contour = max(contours, key=cv2.contourArea)
        perimeter = float(cv2.arcLength(contour, True))
        circularity = 4.0 * pi * area / (perimeter * perimeter) if perimeter > 0 else 0.0
        cx, cy = map(float, centroids[label])
        gx, gy = x0 + cx, y0 + cy
        distance = hypot(gx - x, gy - y)
        dilated = cv2.dilate(component, np.ones((3, 3), np.uint8), iterations=3).astype(bool)
        inside = component.astype(bool)
        ring = dilated & ~inside
        contrast = float(luminance[ring].mean() - luminance[inside].mean()) if ring.any() else 0.0
        mean = crop[inside].astype(float).mean(axis=0)
        if contrast < 8.0 or circularity < 0.12 or mean[2] > mean[0] + 35:
            continue
        output.append(
            VesselCandidate(
                area=area,
                circularity=float(circularity),
                contrast=contrast,
                prior_distance=distance,
                x=gx,
                y=gy,
                mean_rgb=(float(mean[0]), float(mean[1]), float(mean[2])),
                threshold=threshold,
            )
        )
    return output


def vessel_score(candidate: VesselCandidate, previous_area: int | None) -> float:
    area_change = (
        abs(log((candidate.area + 1) / (previous_area + 1)))
        if previous_area is not None
        else 0.0
    )
    return (
        0.04 * min(candidate.contrast, 85.0)
        + 0.75 * min(candidate.circularity, 1.2)
        - 0.085 * candidate.prior_distance
        - 0.30 * area_change
        - max(0, candidate.area - 200) / 500.0
    )


def anchor_start(ulnar_report_path: Path) -> tuple[str, np.ndarray, dict[str, object]]:
    report = json.loads(Path(ulnar_report_path).read_text())
    if report.get("anatomicalId") != "structure.ulnar_artery.left":
        raise ReconError("unexpected ulnar anchor anatomical identity")
    if report.get("classification") != "continuous-candidate":
        raise ReconError("ulnar anchor is not the reviewed continuous candidate")
    rows = report.get("maskFiles")
    if not isinstance(rows, list) or len(rows) != 106:
        raise ReconError("unexpected ulnar anchor support")
    first = rows[0]
    filename = first["sourceFilename"]
    centroid = first["centroidSourcePixels"]
    local = np.asarray([float(centroid["x"]), float(centroid["y"])])
    if not (0 <= local[0] < 550 and 0 <= local[1] < 750):
        raise ReconError("ulnar anchor centroid is not in A05 crop coordinates")
    full = local + A05_CROP_ORIGIN
    lineage = {
        "anatomicalId": report["anatomicalId"],
        "classification": report["classification"],
        "sourceFilename": filename,
        "sourceCentroidA05CropPixels": {"x": float(local[0]), "y": float(local[1])},
        "sourceCentroidFullImagePixels": {"x": float(full[0]), "y": float(full[1])},
        "a05CropOriginFullImagePixels": {"x": 1450, "y": 250},
        "anchorFrameCount": len(rows),
        "completeVesselExtentClaim": bool(report["claims"]["completeUlnarArteryExtent"]),
    }
    return filename, full, lineage


def track_ulnar_proximally(
    source: SourceArchive,
    anchor_filename: str,
    anchor_point: np.ndarray,
    first_filename: str,
) -> dict[str, object]:
    start_index = source.by_name[anchor_filename]["index"]
    first_index = source.by_name[first_filename]["index"]
    if first_index >= start_index:
        raise ReconError("proximal search range must precede ulnar anchor")

    current = anchor_point.copy()
    velocity = np.zeros(2, dtype=float)
    previous_area: int | None = None
    misses = 0
    rows: list[dict[str, object]] = [
        {
            "sourceFilename": anchor_filename,
            "wholeBodyFrameIndex": start_index,
            "xFullImagePixels": float(current[0]),
            "yFullImagePixels": float(current[1]),
            "evidenceKind": "reviewed-ulnar-anchor-start",
        }
    ]
    stop_reason = "range-exhausted"
    stop_filename: str | None = None

    for whole_index in range(start_index - 1, first_index - 1, -1):
        frame = source.frames[whole_index]
        filename = frame["filename"]
        if frame["source"]["listedByteSize"] == 0:
            misses += 1
            if misses > VESSEL_MAX_MISSES:
                stop_reason = "provider-gap-exceeded"
                stop_filename = filename
                break
            continue

        image = source.read_rgb(filename)
        prediction = current + velocity
        candidates = vessel_candidates(image, prediction)
        candidates = [
            candidate
            for candidate in candidates
            if candidate.prior_distance <= 36.0
            and candidate.circularity >= 0.20
            and candidate.contrast >= 10.0
        ]
        if not candidates:
            misses += 1
            if misses > VESSEL_MAX_MISSES:
                stop_reason = "source-continuity-gate-failed"
                stop_filename = filename
                break
            continue

        chosen = max(candidates, key=lambda item: vessel_score(item, previous_area))
        point = np.asarray([chosen.x, chosen.y])
        delta = point - current
        if np.linalg.norm(delta) > 13.0:
            misses += 1
            if misses > VESSEL_MAX_MISSES:
                stop_reason = "jump-gate-failed"
                stop_filename = filename
                break
            continue

        velocity = velocity * 0.60 + delta * 0.40
        current = point
        previous_area = chosen.area
        misses = 0
        rows.append(
            {
                "sourceFilename": filename,
                "wholeBodyFrameIndex": whole_index,
                "xFullImagePixels": chosen.x,
                "yFullImagePixels": chosen.y,
                "areaPixels": chosen.area,
                "circularity": chosen.circularity,
                "contrast": chosen.contrast,
                "priorDistancePixels": chosen.prior_distance,
                "meanRgb": {
                    "r": chosen.mean_rgb[0],
                    "g": chosen.mean_rgb[1],
                    "b": chosen.mean_rgb[2],
                },
                "localDarkThreshold": chosen.threshold,
                "evidenceKind": "same-subject-retrograde-source-continuity",
            }
        )

    detected = rows[1:]
    if detected:
        indices = np.asarray([row["wholeBodyFrameIndex"] for row in detected], dtype=int)
        points = np.asarray(
            [[row["xFullImagePixels"], row["yFullImagePixels"]] for row in detected],
            dtype=float,
        )
        jumps = np.linalg.norm(np.diff(points, axis=0), axis=1) if len(points) > 1 else np.asarray([])
        circularity = [float(row["circularity"]) for row in detected]
        contrast = [float(row["contrast"]) for row in detected]
        earliest = detected[-1]["sourceFilename"]
        span = start_index - int(indices[-1]) + 1
        coverage = len(detected) / max(1, span - 1)
        metrics = {
            "detectedNodeCount": len(detected),
            "spanFromAnchorFrameCount": span,
            "coverageFractionExcludingAnchor": coverage,
            "medianCircularity": float(np.median(circularity)),
            "p25Circularity": float(np.quantile(circularity, 0.25)),
            "medianContrast": float(np.median(contrast)),
            "p25Contrast": float(np.quantile(contrast, 0.25)),
            "meanJumpObservedPixels": float(jumps.mean()) if len(jumps) else 0.0,
            "maxJumpObservedPixels": float(jumps.max()) if len(jumps) else 0.0,
        }
    else:
        earliest = anchor_filename
        metrics = {
            "detectedNodeCount": 0,
            "spanFromAnchorFrameCount": 1,
            "coverageFractionExcludingAnchor": 0.0,
            "medianCircularity": None,
            "p25Circularity": None,
            "medianContrast": None,
            "p25Contrast": None,
            "meanJumpObservedPixels": None,
            "maxJumpObservedPixels": None,
        }

    return {
        "anchorSourceFilename": anchor_filename,
        "earliestContinuouslyTrackedSourceFilename": earliest,
        "stopReason": stop_reason,
        "firstFrameAfterContinuityFailure": stop_filename,
        "metrics": metrics,
        "nodes": rows,
        "claims": {
            "identityBeyondObservedContinuityAutomaticallyEstablished": False,
            "brachialArteryEstablished": False,
            "bifurcationEstablished": False,
            "radialArteryEstablished": False,
            "medicalValidation": False,
        },
    }



def bridge_ulnar_to_bone_transition(
    source: SourceArchive,
    proximal_start: str,
    distal_track: dict[str, object],
    target_filename: str,
) -> dict[str, object]:
    nodes = distal_track["nodes"]
    if not isinstance(nodes, list) or len(nodes) < 2:
        raise ReconError("distal continuity track is too short for bridge search")
    endpoint = nodes[-1]
    start_filename = str(endpoint["sourceFilename"])
    start_index = int(endpoint["wholeBodyFrameIndex"])
    target_index = source.by_name[target_filename]["index"]
    proximal_limit = source.by_name[proximal_start]["index"]
    if not proximal_limit <= target_index < start_index:
        raise ReconError("bridge search bounds are inconsistent")

    start_point = np.asarray(
        [float(endpoint["xFullImagePixels"]), float(endpoint["yFullImagePixels"])],
        dtype=float,
    )
    previous = nodes[-2]
    previous_point = np.asarray(
        [float(previous["xFullImagePixels"]), float(previous["yFullImagePixels"])],
        dtype=float,
    )
    previous_frame = int(previous["wholeBodyFrameIndex"])
    frame_delta = max(1, previous_frame - start_index)
    initial_velocity = (start_point - previous_point) / frame_delta
    initial_area = int(endpoint.get("areaPixels", 0)) or None

    states: list[dict[str, object]] = [
        {
            "point": start_point,
            "velocity": initial_velocity,
            "previousArea": initial_area,
            "score": 0.0,
            "misses": 0,
            "observations": [],
            "lastObservedFrame": start_index,
        }
    ]
    stop_index = start_index
    beam_width = 14
    max_misses = 5

    for whole_index in range(start_index - 1, proximal_limit - 1, -1):
        frame = source.frames[whole_index]
        if frame["source"]["listedByteSize"] == 0:
            candidates_for_frame = None
            image = None
        else:
            image = source.read_rgb(frame["filename"])
            candidates_for_frame = True

        expanded: list[dict[str, object]] = []
        for state in states:
            point = np.asarray(state["point"], dtype=float)
            velocity = np.asarray(state["velocity"], dtype=float)
            prediction = point + velocity
            previous_area = state["previousArea"]
            local_candidates = (
                vessel_candidates(image, prediction, radius=58)
                if candidates_for_frame
                else []
            )
            acceptable = [
                candidate
                for candidate in local_candidates
                if candidate.prior_distance <= 48.0
                and candidate.circularity >= 0.14
                and candidate.contrast >= 8.0
                and hypot(candidate.x - point[0], candidate.y - point[1]) <= 20.0
            ]
            acceptable.sort(
                key=lambda item: vessel_score(
                    item,
                    int(previous_area) if previous_area is not None else None,
                ),
                reverse=True,
            )

            for candidate in acceptable[:5]:
                new_point = np.asarray([candidate.x, candidate.y])
                delta = new_point - point
                observations = list(state["observations"])
                observations.append(
                    {
                        "sourceFilename": frame["filename"],
                        "wholeBodyFrameIndex": whole_index,
                        "xFullImagePixels": candidate.x,
                        "yFullImagePixels": candidate.y,
                        "areaPixels": candidate.area,
                        "circularity": candidate.circularity,
                        "contrast": candidate.contrast,
                        "priorDistancePixels": candidate.prior_distance,
                    }
                )
                expanded.append(
                    {
                        "point": new_point,
                        "velocity": velocity * 0.65 + delta * 0.35,
                        "previousArea": candidate.area,
                        "score": float(state["score"])
                        + vessel_score(
                            candidate,
                            int(previous_area) if previous_area is not None else None,
                        )
                        + 1.0,
                        "misses": 0,
                        "observations": observations,
                        "lastObservedFrame": whole_index,
                    }
                )

            misses = int(state["misses"]) + 1
            if misses <= max_misses:
                expanded.append(
                    {
                        "point": point + velocity,
                        "velocity": velocity * 0.9,
                        "previousArea": previous_area,
                        "score": float(state["score"]) - 2.2 - 0.4 * misses,
                        "misses": misses,
                        "observations": list(state["observations"]),
                        "lastObservedFrame": state["lastObservedFrame"],
                    }
                )

        if not expanded:
            stop_index = whole_index
            break

        # Preserve distinct hypotheses instead of allowing many near-identical
        # states to crowd out alternative same-subject paths.
        expanded.sort(
            key=lambda state: (
                int(state["lastObservedFrame"]) <= target_index,
                len(state["observations"]),
                float(state["score"]),
            ),
            reverse=True,
        )
        deduped: list[dict[str, object]] = []
        occupied: set[tuple[int, int, int]] = set()
        for state in expanded:
            point = np.asarray(state["point"])
            key = (
                int(round(point[0] / 4.0)),
                int(round(point[1] / 4.0)),
                int(state["misses"]),
            )
            if key in occupied:
                continue
            occupied.add(key)
            deduped.append(state)
            if len(deduped) >= beam_width:
                break
        states = deduped
        stop_index = whole_index

    best = max(
        states,
        key=lambda state: (
            int(state["lastObservedFrame"]) <= target_index,
            -int(state["lastObservedFrame"]),
            len(state["observations"]),
            float(state["score"]),
        ),
    )
    observations = list(best["observations"])
    reached_target = int(best["lastObservedFrame"]) <= target_index
    if observations:
        frame_indices = np.asarray(
            [int(row["wholeBodyFrameIndex"]) for row in observations],
            dtype=int,
        )
        points = np.asarray(
            [[float(row["xFullImagePixels"]), float(row["yFullImagePixels"])] for row in observations],
            dtype=float,
        )
        gaps = np.abs(np.diff(frame_indices))
        jumps = np.linalg.norm(np.diff(points, axis=0), axis=1)
        per_frame_jump = jumps / gaps if len(gaps) else np.asarray([])
        span = start_index - int(frame_indices[-1]) + 1
        coverage = len(observations) / max(1, span - 1)
        max_gap = int(gaps.max()) if len(gaps) else 0
        metrics = {
            "observedNodeCount": len(observations),
            "spanFromBridgeStartFrameCount": span,
            "coverageFractionExcludingBridgeStart": coverage,
            "maxObservedGapFrames": max_gap,
            "medianCircularity": float(np.median([row["circularity"] for row in observations])),
            "p25Circularity": float(np.quantile([row["circularity"] for row in observations], 0.25)),
            "medianContrast": float(np.median([row["contrast"] for row in observations])),
            "p25Contrast": float(np.quantile([row["contrast"] for row in observations], 0.25)),
            "meanJumpPerFramePixels": float(per_frame_jump.mean()) if len(per_frame_jump) else 0.0,
            "maxJumpPerFramePixels": float(per_frame_jump.max()) if len(per_frame_jump) else 0.0,
        }
    else:
        metrics = {
            "observedNodeCount": 0,
            "spanFromBridgeStartFrameCount": 1,
            "coverageFractionExcludingBridgeStart": 0.0,
            "maxObservedGapFrames": 0,
            "medianCircularity": None,
            "p25Circularity": None,
            "medianContrast": None,
            "p25Contrast": None,
            "meanJumpPerFramePixels": None,
            "maxJumpPerFramePixels": None,
        }

    continuity_supported = bool(
        reached_target
        and metrics["coverageFractionExcludingBridgeStart"] >= 0.72
        and metrics["maxObservedGapFrames"] <= 6
        and metrics["medianCircularity"] >= 0.45
        and metrics["medianContrast"] >= 18.0
        and metrics["meanJumpPerFramePixels"] <= 4.5
    )

    return {
        "bridgeStartSourceFilename": start_filename,
        "targetBoneTransitionSourceFilename": target_filename,
        "proximalSearchLimitSourceFilename": proximal_start,
        "lastObservedSourceFilename": (
            source.frames[int(best["lastObservedFrame"])]["filename"]
        ),
        "searchStoppedAtSourceFilename": source.frames[stop_index]["filename"],
        "reachedBoneTransitionTarget": reached_target,
        "sameSubjectContinuitySupportedToBoneTransition": continuity_supported,
        "metrics": metrics,
        "observations": observations,
        "claims": {
            "sameNamedVesselBeyondSourceContinuityClaim": False,
            "brachialArteryEstablished": False,
            "bifurcationEstablished": False,
            "radialArteryEstablished": False,
            "medicalValidation": False,
        },
    }

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--archive-index", type=Path, required=True)
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--ulnar-report", type=Path, required=True)
    parser.add_argument("--first", default=DEFAULT_FIRST_FILENAME)
    parser.add_argument("--last", default=DEFAULT_LAST_FILENAME)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    source = SourceArchive(args.inventory, args.archive_index, args.archive_root)
    try:
        if args.first not in source.by_name or args.last not in source.by_name:
            raise ReconError("requested reconnaissance range is outside the inventory")
        if source.by_name[args.first]["index"] >= source.by_name[args.last]["index"]:
            raise ReconError("reconnaissance range must be proximal-to-distal")

        anchor_filename, anchor_point, anchor_lineage = anchor_start(args.ulnar_report)
        if anchor_filename != args.last:
            raise ReconError(
                f"workflow last frame must equal reviewed ulnar anchor start {anchor_filename}"
            )

        bones = track_forearm_bones(source, nominal_index(args.first))
        ulnar = track_ulnar_proximally(source, anchor_filename, anchor_point, args.first)

        bone_target = str(bones["earliestSupportedSourceFilename"])
        bridge = bridge_ulnar_to_bone_transition(
            source,
            args.first,
            ulnar,
            bone_target,
        )
        bone_earliest = nominal_index(bone_target)
        ulnar_earliest = nominal_index(str(ulnar["earliestContinuouslyTrackedSourceFilename"]))
        distance_nominal = abs(ulnar_earliest - bone_earliest)
        reaches_bone_transition_neighborhood = bool(
            bridge["sameSubjectContinuitySupportedToBoneTransition"]
        )

        report = {
            "schema": "ph-as06-upper-extremity-continuity-recon.v1",
            "schemaVersion": "1",
            "task": "TASK-AS06",
            "phase": "proximal-source-reconnaissance",
            "coordinateSpace": {
                "kind": "source-image-stack",
                "patientSpaceClaim": False,
                "physicalXyClaim": False,
            },
            "source": {
                "inventoryPath": str(args.inventory),
                "inventorySha256": path_sha256(args.inventory),
                "archiveIndexPath": str(args.archive_index),
                "archiveIndexSha256": path_sha256(args.archive_index),
                "firstSourceFilename": args.first,
                "lastSourceFilename": args.last,
                "firstWholeBodyFrameIndex": source.by_name[args.first]["index"],
                "lastWholeBodyFrameIndex": source.by_name[args.last]["index"],
                "verifiedChunkIndices": sorted(source._verified),
            },
            "anchorLineage": anchor_lineage,
            "boneContinuity": bones,
            "ulnarArteryRetrogradeContinuity": ulnar,
            "ulnarBridgeSearch": bridge,
            "nextSearchReadiness": {
                "bonePairEarliestNominalIndex": bone_earliest,
                "ulnarTrackEarliestNominalIndex": ulnar_earliest,
                "nominalIndexSeparation": distance_nominal,
                "ulnarTrackReachesBoneTransitionNeighborhood": reaches_bone_transition_neighborhood,
                "bifurcationSearchAuthorized": reaches_bone_transition_neighborhood,
                "bifurcationSearchAuthorizationBasis": (
                    "beam-search same-subject ulnar continuity reaches the proximal radius/ulna pair-support transition"
                    if reaches_bone_transition_neighborhood
                    else "same-subject ulnar continuity remains discontinuous from the proximal radius/ulna pair-support transition"
                ),
                "radialIdentityPromotionAuthorized": False,
                "superficialVeinIdentityPromotionAuthorized": False,
                "note": (
                    "This readiness flag only bounds a later source-first branch search. "
                    "It is not evidence that a brachial bifurcation or radial artery has been identified."
                ),
            },
            "claims": {
                "humanEdited": False,
                "anatomicallyReviewed": False,
                "medicalValidation": False,
                "patientSpaceGeometry": False,
                "ctRegistrationEstablished": False,
                "crossSubjectGeometryUsed": False,
                "brachialArteryIdentityEstablished": False,
                "radialArteryIdentityEstablished": False,
                "namedSuperficialVeinIdentityEstablished": False,
                "automaticPromotionAllowed": False,
            },
            "software": {
                "numpyVersion": np.__version__,
                "opencvVersion": cv2.__version__,
                "pillowVersion": Image.__version__ if hasattr(Image, "__version__") else None,
            },
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(
            json.dumps(
                {
                    "boneContinuity": {
                        key: bones[key]
                        for key in (
                            "earliestSupportedSourceFilename",
                            "supportedASliceCount",
                            "stopReason",
                            "firstUnsupportedOrAmbiguousSourceFilename",
                            "minimumObservedSeparationPixels",
                        )
                    },
                    "ulnarArteryRetrogradeContinuity": {
                        "earliestContinuouslyTrackedSourceFilename": ulnar[
                            "earliestContinuouslyTrackedSourceFilename"
                        ],
                        "stopReason": ulnar["stopReason"],
                        "firstFrameAfterContinuityFailure": ulnar[
                            "firstFrameAfterContinuityFailure"
                        ],
                        "metrics": ulnar["metrics"],
                    },
                    "ulnarBridgeSearch": {
                        "bridgeStartSourceFilename": bridge["bridgeStartSourceFilename"],
                        "targetBoneTransitionSourceFilename": bridge["targetBoneTransitionSourceFilename"],
                        "lastObservedSourceFilename": bridge["lastObservedSourceFilename"],
                        "reachedBoneTransitionTarget": bridge["reachedBoneTransitionTarget"],
                        "sameSubjectContinuitySupportedToBoneTransition": bridge[
                            "sameSubjectContinuitySupportedToBoneTransition"
                        ],
                        "metrics": bridge["metrics"],
                    },
                    "nextSearchReadiness": report["nextSearchReadiness"],
                },
                indent=2,
            )
        )
    finally:
        source.close()


if __name__ == "__main__":
    main()
