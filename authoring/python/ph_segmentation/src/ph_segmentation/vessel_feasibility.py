from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from math import hypot
from typing import Iterable

from .manifest_io import write_json_atomic
from .reports import BLOCKED_VESSEL_LABELS, DRAFT_STATUS, SOURCE_SPACE_ONLY


class VesselGenerationBlocked(RuntimeError):
    pass


@dataclass(frozen=True)
class VesselSliceObservation:
    slice_index: int
    candidate_present: bool
    centroid_x: float | None = None
    centroid_y: float | None = None


@dataclass(frozen=True)
class FeasibilityThresholds:
    continuous_min_fraction: float = 0.70
    intermittent_min_fraction: float = 0.20
    continuous_min_run: int = 6
    continuous_max_gap: int = 1
    max_centroid_step_px: float = 20.0


def request_vessel_mask_generation(structure: str) -> None:
    if structure not in BLOCKED_VESSEL_LABELS:
        raise ValueError(f"unknown TASK-A05 vessel label: {structure}")
    raise VesselGenerationBlocked(
        f"{structure} mask generation is fail-closed in TASK-A05; feasibility reporting does not authorize a vessel mask"
    )


def _longest_run(indices: list[int]) -> int:
    if not indices:
        return 0
    best = current = 1
    for previous, current_index in zip(indices, indices[1:]):
        if current_index == previous + 1:
            current += 1
        else:
            current = 1
        best = max(best, current)
    return best


def _max_internal_gap(indices: list[int]) -> int:
    if len(indices) < 2:
        return 0
    return max(current - previous - 1 for previous, current in zip(indices, indices[1:]))


def _centroid_continuity(
    observations: list[VesselSliceObservation], threshold: float
) -> tuple[bool, float | None]:
    candidates = [item for item in observations if item.candidate_present]
    if not candidates:
        return False, None
    if any(item.centroid_x is None or item.centroid_y is None for item in candidates):
        return False, None
    max_step = 0.0
    for left, right in zip(candidates, candidates[1:]):
        if right.slice_index != left.slice_index + 1:
            continue
        step = hypot(
            float(right.centroid_x) - float(left.centroid_x),
            float(right.centroid_y) - float(left.centroid_y),
        )
        max_step = max(max_step, step)
    return max_step <= threshold, max_step


def analyze_structure_feasibility(
    structure: str,
    observations: Iterable[VesselSliceObservation],
    total_slices: int,
    thresholds: FeasibilityThresholds = FeasibilityThresholds(),
) -> dict[str, object]:
    if structure not in BLOCKED_VESSEL_LABELS:
        raise ValueError(f"unknown TASK-A05 vessel label: {structure}")
    if total_slices <= 0:
        raise ValueError("total_slices must be positive")

    ordered = sorted(observations, key=lambda item: item.slice_index)
    seen: set[int] = set()
    for item in ordered:
        if not 0 <= item.slice_index < total_slices:
            raise ValueError(f"slice index outside source stack: {item.slice_index}")
        if item.slice_index in seen:
            raise ValueError(f"duplicate vessel observation for slice {item.slice_index}")
        seen.add(item.slice_index)
        if (item.centroid_x is None) != (item.centroid_y is None):
            raise ValueError("vessel centroid must provide both x and y or neither")

    candidate_indices = [item.slice_index for item in ordered if item.candidate_present]
    coverage = len(candidate_indices) / total_slices
    longest_run = _longest_run(candidate_indices)
    max_gap = _max_internal_gap(candidate_indices)
    centroid_ok, max_step = _centroid_continuity(
        ordered, thresholds.max_centroid_step_px
    )

    continuous = (
        coverage >= thresholds.continuous_min_fraction
        and longest_run >= min(thresholds.continuous_min_run, total_slices)
        and max_gap <= thresholds.continuous_max_gap
        and centroid_ok
    )
    intermittent = (
        coverage >= thresholds.intermittent_min_fraction or longest_run >= 3
    )

    if continuous:
        classification = "continuous-candidate"
        review_disposition = "may-proceed-to-manual-review"
    elif intermittent:
        classification = "intermittent-candidate"
        review_disposition = "may-proceed-to-manual-review"
    else:
        classification = "not-established"
        review_disposition = "remain-blocked"

    return {
        "draftLabel": structure,
        "classification": classification,
        "reviewDisposition": review_disposition,
        "maskGenerationBlocked": True,
        "automaticPromotionAllowed": False,
        "validatedSegmentation": False,
        "status": DRAFT_STATUS.copy(),
        "metrics": {
            "totalSlices": total_slices,
            "observedSlices": len(ordered),
            "candidateSlices": len(candidate_indices),
            "candidateCoverageFraction": coverage,
            "longestConsecutiveCandidateRun": longest_run,
            "maxInternalGapSlices": max_gap,
            "centroidContinuityEstablished": centroid_ok,
            "maxAdjacentCentroidStepPx": max_step,
        },
    }


def build_vascular_feasibility_report(
    observations_by_structure: dict[str, Iterable[VesselSliceObservation]],
    total_slices: int,
    source_manifest_digest_sha256: str,
    thresholds: FeasibilityThresholds = FeasibilityThresholds(),
) -> dict[str, object]:
    structures = []
    for structure in BLOCKED_VESSEL_LABELS:
        structures.append(
            analyze_structure_feasibility(
                structure,
                observations_by_structure.get(structure, ()),
                total_slices,
                thresholds,
            )
        )
    return {
        "schema": "ph-vascular-feasibility-report.v1",
        "task": "TASK-A05",
        "status": DRAFT_STATUS.copy(),
        "coordinateSpace": SOURCE_SPACE_ONLY.copy(),
        "sourceManifestDigestSha256": source_manifest_digest_sha256,
        "structures": structures,
        "claims": {
            "patientSpaceGeometry": False,
            "medicalValidation": False,
            "vesselMasksCreated": False,
            "feasibilityIsSegmentationValidation": False,
        },
    }


def write_vascular_feasibility_report(
    path: str | Path, report: dict[str, object]
) -> None:
    write_json_atomic(path, report)
