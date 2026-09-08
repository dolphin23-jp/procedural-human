from __future__ import annotations

from dataclasses import dataclass
from math import inf
from typing import Iterable

from .ingest import DicomSourceRecord


@dataclass(frozen=True)
class PixelCrop:
    column_start: int
    column_end_exclusive: int
    row_start: int
    row_end_exclusive: int


@dataclass(frozen=True)
class PatientSpaceExtent:
    minimum_mm: tuple[float, float, float]
    maximum_mm: tuple[float, float, float]
    semantics: str = "selected-voxel-center-aabb"


def _add(
    a: tuple[float, float, float],
    b: tuple[float, float, float],
) -> tuple[float, float, float]:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _scale(
    a: tuple[float, float, float],
    amount: float,
) -> tuple[float, float, float]:
    return (a[0] * amount, a[1] * amount, a[2] * amount)


def patient_point_for_pixel(
    record: DicomSourceRecord,
    *,
    column: int,
    row: int,
) -> tuple[float, float, float]:
    spatial = record.spatial
    if not (0 <= column < spatial.columns and 0 <= row < spatial.rows):
        raise ValueError("pixel index lies outside the DICOM image")

    # DICOM PixelSpacing is [row spacing, column spacing]. The first IOP
    # triplet points along increasing columns; the second along increasing rows.
    column_direction = spatial.image_orientation_patient[:3]
    row_direction = spatial.image_orientation_patient[3:]
    row_spacing, column_spacing = spatial.pixel_spacing_mm
    return _add(
        spatial.image_position_patient_mm,
        _add(
            _scale(column_direction, column * column_spacing),
            _scale(row_direction, row * row_spacing),
        ),
    )


def patient_extent_for_crop(
    records: Iterable[DicomSourceRecord],
    crop: PixelCrop,
) -> PatientSpaceExtent:
    items = tuple(records)
    if not items:
        raise ValueError("at least one DICOM source record is required")
    if crop.column_start < 0 or crop.row_start < 0:
        raise ValueError("crop starts must be non-negative")
    if (
        crop.column_end_exclusive <= crop.column_start
        or crop.row_end_exclusive <= crop.row_start
    ):
        raise ValueError("crop must contain at least one pixel")

    minimum = [inf, inf, inf]
    maximum = [-inf, -inf, -inf]
    for item in items:
        if (
            crop.column_end_exclusive > item.spatial.columns
            or crop.row_end_exclusive > item.spatial.rows
        ):
            raise ValueError("crop exceeds DICOM image dimensions")
        for column, row in (
            (crop.column_start, crop.row_start),
            (crop.column_end_exclusive - 1, crop.row_start),
            (crop.column_start, crop.row_end_exclusive - 1),
            (crop.column_end_exclusive - 1, crop.row_end_exclusive - 1),
        ):
            point = patient_point_for_pixel(
                item,
                column=column,
                row=row,
            )
            for axis in range(3):
                minimum[axis] = min(minimum[axis], point[axis])
                maximum[axis] = max(maximum[axis], point[axis])

    return PatientSpaceExtent(tuple(minimum), tuple(maximum))
