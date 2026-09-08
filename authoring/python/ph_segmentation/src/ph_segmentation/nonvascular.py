from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from math import hypot, isfinite

from .manifest_io import SourceStackManifest, verify_source_slice, write_json_atomic
from .reports import (
    BLOCKED_VESSEL_LABELS,
    DRAFT_STATUS,
    SOURCE_SPACE_ONLY,
    nonvascular_label_record,
    vessel_block_record,
)
from .slice_io import RgbImage, read_png_rgb, write_pgm_mask

NONVASCULAR_LABELS = (
    "skin",
    "subcutaneous_soft_tissue",
    "radius",
    "ulna",
    "major_muscle_tendon_region",
)


class CandidateGenerationBlocked(RuntimeError):
    pass


@dataclass(frozen=True)
class RgbRule:
    r_min: int = 0
    g_min: int = 0
    b_min: int = 0
    r_max: int = 255
    g_max: int = 255
    b_max: int = 255
    brightness_min: float = 0.0
    brightness_max: float = 255.0
    saturation_min: int = 0
    saturation_max: int = 255
    red_over_green: float = 0.0
    red_over_blue: float = 0.0

    def matches(self, r: int, g: int, b: int) -> bool:
        brightness = (r + g + b) / 3.0
        saturation = max(r, g, b) - min(r, g, b)
        return (
            self.r_min <= r <= self.r_max
            and self.g_min <= g <= self.g_max
            and self.b_min <= b <= self.b_max
            and self.brightness_min <= brightness <= self.brightness_max
            and self.saturation_min <= saturation <= self.saturation_max
            and (self.red_over_green == 0.0 or r >= g * self.red_over_green)
            and (self.red_over_blue == 0.0 or r >= b * self.red_over_blue)
        )


@dataclass(frozen=True)
class SourceAnchor:
    slice_index: int
    x: float
    y: float


@dataclass(frozen=True)
class AnchorTrack:
    anchors: tuple[SourceAnchor, ...]
    max_component_distance_px: float = 28.0

    def point_for_slice(self, slice_index: int) -> tuple[float, float]:
        if not self.anchors:
            raise CandidateGenerationBlocked("bone anchor track is empty")
        anchors = tuple(sorted(self.anchors, key=lambda item: item.slice_index))
        if slice_index < anchors[0].slice_index or slice_index > anchors[-1].slice_index:
            raise CandidateGenerationBlocked(
                "bone anchor track extrapolation is prohibited in source-image-stack coordinates"
            )
        if slice_index == anchors[0].slice_index:
            return anchors[0].x, anchors[0].y
        if slice_index == anchors[-1].slice_index:
            return anchors[-1].x, anchors[-1].y
        for left, right in zip(anchors, anchors[1:]):
            if left.slice_index <= slice_index <= right.slice_index:
                span = right.slice_index - left.slice_index
                t = 0.0 if span == 0 else (slice_index - left.slice_index) / span
                return (
                    left.x + (right.x - left.x) * t,
                    left.y + (right.y - left.y) * t,
                )
        raise AssertionError("unreachable anchor interpolation")


@dataclass(frozen=True)
class NonvascularConfig:
    profile_id: str
    skin_rule: RgbRule
    subcutaneous_rule: RgbRule
    bone_rule: RgbRule
    muscle_tendon_rule: RgbRule
    radius_track: AnchorTrack
    ulna_track: AnchorTrack


DEFAULT_VISIBLE_HUMAN_V0_RULES = {
    "skin_rule": RgbRule(
        r_min=45,
        brightness_min=30,
        brightness_max=190,
        saturation_min=12,
        red_over_green=1.05,
        red_over_blue=1.10,
    ),
    "subcutaneous_rule": RgbRule(
        r_min=95,
        g_min=65,
        b_max=180,
        brightness_min=75,
        brightness_max=220,
        saturation_min=12,
    ),
    "bone_rule": RgbRule(
        brightness_min=145,
        brightness_max=255,
        saturation_max=95,
    ),
    "muscle_tendon_rule": RgbRule(
        r_min=55,
        brightness_min=35,
        brightness_max=185,
        saturation_min=22,
        red_over_green=1.16,
        red_over_blue=1.10,
    ),
}


def _rule_mask(image: RgbImage, rule: RgbRule) -> bytearray:
    mask = bytearray(image.width * image.height)
    pixels = image.pixels
    for index in range(image.width * image.height):
        offset = index * 3
        if rule.matches(pixels[offset], pixels[offset + 1], pixels[offset + 2]):
            mask[index] = 1
    return mask


def _skin_boundary_only(image: RgbImage, raw_skin: bytearray) -> bytearray:
    body = bytearray(image.width * image.height)
    for index in range(image.width * image.height):
        offset = index * 3
        r, g, b = image.pixels[offset : offset + 3]
        if (r + g + b) / 3.0 >= 12.0:
            body[index] = 1

    output = bytearray(len(body))
    width = image.width
    height = image.height
    for y in range(height):
        for x in range(width):
            index = y * width + x
            if not body[index] or not raw_skin[index]:
                continue
            is_boundary = x == 0 or y == 0 or x == width - 1 or y == height - 1
            if not is_boundary:
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if not body[ny * width + nx]:
                        is_boundary = True
                        break
            if is_boundary:
                output[index] = 1
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if 0 <= nx < width and 0 <= ny < height and raw_skin[ny * width + nx]:
                        output[ny * width + nx] = 1
    return output


def _nearest_candidate_index(
    mask: bytearray,
    width: int,
    height: int,
    anchor: tuple[float, float],
    max_distance: float,
) -> int | None:
    ax, ay = anchor
    radius = int(max_distance) + 1
    min_x = max(0, int(ax) - radius)
    max_x = min(width - 1, int(ax) + radius)
    min_y = max(0, int(ay) - radius)
    max_y = min(height - 1, int(ay) + radius)
    best: tuple[float, int] | None = None
    for y in range(min_y, max_y + 1):
        for x in range(min_x, max_x + 1):
            index = y * width + x
            if not mask[index]:
                continue
            distance = hypot(x - ax, y - ay)
            if distance > max_distance:
                continue
            candidate = (distance, index)
            if best is None or candidate < best:
                best = candidate
    return None if best is None else best[1]


def _component_from_seed(mask: bytearray, width: int, height: int, seed: int) -> bytearray:
    output = bytearray(width * height)
    queue = [seed]
    output[seed] = 1
    cursor = 0
    while cursor < len(queue):
        index = queue[cursor]
        cursor += 1
        x = index % width
        y = index // width
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            neighbor = ny * width + nx
            if mask[neighbor] and not output[neighbor]:
                output[neighbor] = 1
                queue.append(neighbor)
    return output


def _anchored_component(
    mask: bytearray,
    image: RgbImage,
    track: AnchorTrack,
    slice_index: int,
) -> bytearray:
    seed = _nearest_candidate_index(
        mask,
        image.width,
        image.height,
        track.point_for_slice(slice_index),
        track.max_component_distance_px,
    )
    if seed is None:
        return bytearray(image.width * image.height)
    return _component_from_seed(mask, image.width, image.height, seed)


def candidate_masks_for_image(
    image: RgbImage,
    slice_index: int,
    config: NonvascularConfig,
) -> tuple[dict[str, bytearray], list[str]]:
    raw_skin = _rule_mask(image, config.skin_rule)
    bone = _rule_mask(image, config.bone_rule)
    radius = _anchored_component(bone, image, config.radius_track, slice_index)
    ulna = _anchored_component(bone, image, config.ulna_track, slice_index)
    warnings: list[str] = []
    if any(a and b for a, b in zip(radius, ulna)):
        radius = bytearray(image.width * image.height)
        ulna = bytearray(image.width * image.height)
        warnings.append("radius-ulna-components-not-separable")

    return (
        {
            "skin": _skin_boundary_only(image, raw_skin),
            "subcutaneous_soft_tissue": _rule_mask(image, config.subcutaneous_rule),
            "radius": radius,
            "ulna": ulna,
            "major_muscle_tendon_region": _rule_mask(image, config.muscle_tendon_rule),
        },
        warnings,
    )


def _coverage_record(pixel_counts: list[int], total_pixels_per_slice: int) -> dict[str, int | float]:
    slices_with_candidate = sum(1 for value in pixel_counts if value > 0)
    total_candidate_pixels = sum(pixel_counts)
    total_pixels = total_pixels_per_slice * len(pixel_counts)
    return {
        "sliceCount": len(pixel_counts),
        "slicesWithCandidate": slices_with_candidate,
        "totalCandidatePixels": total_candidate_pixels,
        "candidatePixelFraction": 0.0 if total_pixels == 0 else total_candidate_pixels / total_pixels,
        "maxCandidatePixelsPerSlice": max(pixel_counts, default=0),
    }


def _validate_anchor_track(
    track: AnchorTrack,
    label: str,
    slice_count: int,
) -> None:
    if not track.anchors:
        raise CandidateGenerationBlocked(
            f"{label} requires an explicit source-space anchor track"
        )
    if not isfinite(track.max_component_distance_px) or track.max_component_distance_px <= 0:
        raise CandidateGenerationBlocked(
            f"{label} anchor search distance must be finite and positive"
        )

    anchors = tuple(sorted(track.anchors, key=lambda item: item.slice_index))
    seen: set[int] = set()
    for anchor in anchors:
        if not isinstance(anchor.slice_index, int):
            raise CandidateGenerationBlocked(
                f"{label} anchor slice index must be an integer"
            )
        if not 0 <= anchor.slice_index < slice_count:
            raise CandidateGenerationBlocked(
                f"{label} anchor slice {anchor.slice_index} is outside the source stack"
            )
        if anchor.slice_index in seen:
            raise CandidateGenerationBlocked(
                f"{label} has duplicate anchors on source slice {anchor.slice_index}"
            )
        seen.add(anchor.slice_index)
        if not isfinite(anchor.x) or not isfinite(anchor.y):
            raise CandidateGenerationBlocked(
                f"{label} anchor coordinates must be finite source-image pixels"
            )

    if anchors[0].slice_index != 0 or anchors[-1].slice_index != slice_count - 1:
        raise CandidateGenerationBlocked(
            f"{label} anchor track must cover source slices 0 through {slice_count - 1}; "
            "endpoint extrapolation is prohibited"
        )


def generate_tissue_only_draft(
    source_root: str | Path,
    source_manifest: SourceStackManifest,
    output_root: str | Path,
    *,
    profile_id: str = "vhp-female-source-space-tissue-v0",
    skin_rule: RgbRule = DEFAULT_VISIBLE_HUMAN_V0_RULES["skin_rule"],
    subcutaneous_rule: RgbRule = DEFAULT_VISIBLE_HUMAN_V0_RULES["subcutaneous_rule"],
    muscle_tendon_rule: RgbRule = DEFAULT_VISIBLE_HUMAN_V0_RULES["muscle_tendon_rule"],
    blocked_nonvascular_labels: tuple[str, ...] = ("radius", "ulna"),
    blocked_reason: str = (
        "explicit source-space radius/ulna anchor tracks spanning the complete source "
        "stack are not established without prohibited extrapolation"
    ),
    verify_hashes: bool = True,
) -> dict[str, object]:
    """Generate only tissue candidates when bone identity cannot be safely tracked.

    This deliberately does not emit the five-label draft-segmentation-manifest.v1,
    because that contract represents successful generation of all five nonvascular
    candidate masks. Blocked anatomy stays explicit instead of being represented by
    fabricated or empty masks.
    """
    allowed_blocked = {"radius", "ulna"}
    blocked_set = set(blocked_nonvascular_labels)
    if not blocked_set or not blocked_set.issubset(allowed_blocked):
        raise CandidateGenerationBlocked(
            "tissue-only execution may block only radius and/or ulna"
        )

    source_root = Path(source_root)
    output_root = Path(output_root)
    generated_labels = (
        "skin",
        "subcutaneous_soft_tissue",
        "major_muscle_tendon_region",
    )
    coverage: dict[str, list[int]] = {label: [] for label in generated_labels}
    dimensions: tuple[int, int] | None = None

    for record in source_manifest.slices:
        source_path = source_root / record.filename
        if verify_hashes:
            verify_source_slice(source_path, record.sha256)
        image = read_png_rgb(source_path)
        if dimensions is None:
            dimensions = (image.width, image.height)
        elif dimensions != (image.width, image.height):
            raise CandidateGenerationBlocked(
                f"source slice dimensions changed at {record.filename}; no resampling is authorized"
            )

        raw_skin = _rule_mask(image, skin_rule)
        masks = {
            "skin": _skin_boundary_only(image, raw_skin),
            "subcutaneous_soft_tissue": _rule_mask(image, subcutaneous_rule),
            "major_muscle_tendon_region": _rule_mask(image, muscle_tendon_rule),
        }
        for label, mask in masks.items():
            coverage[label].append(sum(mask))
            destination = output_root / "masks" / label / f"{Path(record.filename).stem}.pgm"
            write_pgm_mask(destination, image.width, image.height, mask)

    if dimensions is None:
        raise CandidateGenerationBlocked("source stack is empty")
    width, height = dimensions
    coverage_records = {
        label: _coverage_record(counts, width * height) for label, counts in coverage.items()
    }
    report: dict[str, object] = {
        "schema": "ph-a05-real-nonvascular-execution.v1",
        "task": "TASK-A05",
        "pipelineProfile": profile_id,
        "status": DRAFT_STATUS.copy(),
        "coordinateSpace": SOURCE_SPACE_ONLY.copy(),
        "source": {
            "dataset": source_manifest.dataset,
            "sourceManifestDigestSha256": source_manifest.digest,
            "sliceCount": source_manifest.slice_count,
            "firstSourceFile": source_manifest.slices[0].filename,
            "lastSourceFile": source_manifest.slices[-1].filename,
            "sourceFilesVerified": verify_hashes,
        },
        "generatedLabels": [
            nonvascular_label_record(label, coverage_records[label])
            for label in generated_labels
        ],
        "blockedNonvascularLabels": [
            {
                "draftLabel": label,
                "maskGeneration": "blocked",
                "reason": blocked_reason,
                "status": DRAFT_STATUS.copy(),
            }
            for label in blocked_nonvascular_labels
        ],
        "blockedVesselLabels": [
            vessel_block_record(label) for label in BLOCKED_VESSEL_LABELS
        ],
        "claims": {
            "patientSpaceGeometry": False,
            "medicalValidation": False,
            "automaticPromotion": False,
            "completeFiveClassDraft": False,
        },
    }
    write_json_atomic(output_root / "real-nonvascular-execution.v0.json", report)
    write_json_atomic(
        output_root / "coverage-statistics.v0.json",
        {
            "schema": "ph-draft-segmentation-coverage.v1",
            "status": DRAFT_STATUS.copy(),
            "coordinateSpace": SOURCE_SPACE_ONLY.copy(),
            "labels": coverage_records,
            "blockedNonvascularLabels": list(blocked_nonvascular_labels),
        },
    )
    return report


def generate_nonvascular_draft(
    source_root: str | Path,
    source_manifest: SourceStackManifest,
    output_root: str | Path,
    config: NonvascularConfig,
    *,
    verify_hashes: bool = True,
) -> dict[str, object]:
    _validate_anchor_track(config.radius_track, "radius", source_manifest.slice_count)
    _validate_anchor_track(config.ulna_track, "ulna", source_manifest.slice_count)

    source_root = Path(source_root)
    output_root = Path(output_root)
    coverage: dict[str, list[int]] = {label: [] for label in NONVASCULAR_LABELS}
    ambiguity_slices: list[dict[str, object]] = []
    dimensions: tuple[int, int] | None = None

    for slice_index, record in enumerate(source_manifest.slices):
        source_path = source_root / record.filename
        if verify_hashes:
            verify_source_slice(source_path, record.sha256)
        image = read_png_rgb(source_path)
        if dimensions is None:
            dimensions = (image.width, image.height)
        elif dimensions != (image.width, image.height):
            raise CandidateGenerationBlocked(
                f"source slice dimensions changed at {record.filename}; no resampling is authorized"
            )

        masks, warnings = candidate_masks_for_image(image, slice_index, config)
        if warnings:
            ambiguity_slices.append(
                {
                    "sliceIndex": slice_index,
                    "sourceFile": record.filename,
                    "warnings": warnings,
                }
            )
        for label, mask in masks.items():
            coverage[label].append(sum(mask))
            destination = output_root / "masks" / label / f"{Path(record.filename).stem}.pgm"
            write_pgm_mask(destination, image.width, image.height, mask)

    if dimensions is None:
        raise CandidateGenerationBlocked("source stack is empty")
    width, height = dimensions
    coverage_records = {
        label: _coverage_record(counts, width * height) for label, counts in coverage.items()
    }

    manifest: dict[str, object] = {
        "schema": "ph-draft-segmentation-manifest.v1",
        "task": "TASK-A05",
        "pipelineProfile": config.profile_id,
        "status": DRAFT_STATUS.copy(),
        "coordinateSpace": SOURCE_SPACE_ONLY.copy(),
        "source": {
            "dataset": source_manifest.dataset,
            "sourceManifestDigestSha256": source_manifest.digest,
            "sliceCount": source_manifest.slice_count,
            "firstSourceFile": source_manifest.slices[0].filename,
            "lastSourceFile": source_manifest.slices[-1].filename,
            "sourceFilesVerified": verify_hashes,
        },
        "labels": [
            nonvascular_label_record(label, coverage_records[label])
            for label in NONVASCULAR_LABELS
        ],
        "blockedVesselLabels": [
            vessel_block_record(label) for label in BLOCKED_VESSEL_LABELS
        ],
        "ambiguities": ambiguity_slices,
        "claims": {
            "patientSpaceGeometry": False,
            "medicalValidation": False,
            "automaticPromotion": False,
        },
    }
    write_json_atomic(output_root / "draft-segmentation-manifest.v0.json", manifest)
    write_json_atomic(
        output_root / "coverage-statistics.v0.json",
        {
            "schema": "ph-draft-segmentation-coverage.v1",
            "status": DRAFT_STATUS.copy(),
            "coordinateSpace": SOURCE_SPACE_ONLY.copy(),
            "labels": coverage_records,
        },
    )
    return manifest
