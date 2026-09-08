from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from math import isclose, sqrt
from pathlib import Path
from typing import Any, Iterable, Sequence


class SpatialMetadataUnavailable(ValueError):
    """Raised when a source cannot establish image geometry without guessing."""


class SpatialMetadataConflict(ValueError):
    """Raised when images that claim to be one series disagree spatially."""


@dataclass(frozen=True)
class DicomSpatialMetadata:
    rows: int
    columns: int
    pixel_spacing_mm: tuple[float, float]
    image_position_patient_mm: tuple[float, float, float]
    image_orientation_patient: tuple[float, float, float, float, float, float]
    frame_of_reference_uid: str | None
    spacing_between_slices_mm: float | None
    slice_thickness_mm: float | None


@dataclass(frozen=True)
class DicomSourceRecord:
    source_path: str
    sha256: str
    byte_size: int
    sop_instance_uid: str
    study_instance_uid: str | None
    series_instance_uid: str | None
    modality: str | None
    spatial: DicomSpatialMetadata

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)


def sha256_file(path: str | Path, *, chunk_size: int = 1024 * 1024) -> str:
    source = Path(path)
    digest = sha256()
    with source.open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require(dataset: Any, name: str) -> Any:
    value = getattr(dataset, name, None)
    if value is None or value == "":
        raise SpatialMetadataUnavailable(f"required DICOM attribute {name} is unavailable")
    return value


def _tuple_of_float(value: Any, *, length: int, name: str) -> tuple[float, ...]:
    try:
        result = tuple(float(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise SpatialMetadataUnavailable(f"DICOM attribute {name} is not numeric") from exc
    if len(result) != length:
        raise SpatialMetadataUnavailable(
            f"DICOM attribute {name} must contain {length} values; got {len(result)}"
        )
    return result


def _optional_float(dataset: Any, name: str) -> float | None:
    value = getattr(dataset, name, None)
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise SpatialMetadataUnavailable(f"DICOM attribute {name} is not numeric") from exc


def _optional_text(dataset: Any, name: str) -> str | None:
    value = getattr(dataset, name, None)
    if value is None or value == "":
        return None
    return str(value)


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def _norm(a: Sequence[float]) -> float:
    return sqrt(_dot(a, a))


def _cross(a: Sequence[float], b: Sequence[float]) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def extract_spatial_metadata(dataset: Any) -> DicomSpatialMetadata:
    try:
        rows = int(_require(dataset, "Rows"))
        columns = int(_require(dataset, "Columns"))
    except (TypeError, ValueError) as exc:
        raise SpatialMetadataUnavailable("DICOM Rows/Columns must be integers") from exc
    if rows <= 0 or columns <= 0:
        raise SpatialMetadataUnavailable("DICOM Rows/Columns must be positive")

    pixel_spacing = _tuple_of_float(
        _require(dataset, "PixelSpacing"), length=2, name="PixelSpacing"
    )
    if pixel_spacing[0] <= 0 or pixel_spacing[1] <= 0:
        raise SpatialMetadataUnavailable("DICOM PixelSpacing must be positive")

    position = _tuple_of_float(
        _require(dataset, "ImagePositionPatient"), length=3, name="ImagePositionPatient"
    )
    orientation = _tuple_of_float(
        _require(dataset, "ImageOrientationPatient"), length=6, name="ImageOrientationPatient"
    )
    row_direction = orientation[:3]
    column_direction = orientation[3:]
    if not isclose(_norm(row_direction), 1.0, rel_tol=0.0, abs_tol=1e-4):
        raise SpatialMetadataUnavailable(
            "first ImageOrientationPatient direction is not unit length"
        )
    if not isclose(_norm(column_direction), 1.0, rel_tol=0.0, abs_tol=1e-4):
        raise SpatialMetadataUnavailable(
            "second ImageOrientationPatient direction is not unit length"
        )
    if not isclose(
        _dot(row_direction, column_direction), 0.0, rel_tol=0.0, abs_tol=1e-4
    ):
        raise SpatialMetadataUnavailable(
            "ImageOrientationPatient directions are not orthogonal"
        )

    return DicomSpatialMetadata(
        rows=rows,
        columns=columns,
        pixel_spacing_mm=(pixel_spacing[0], pixel_spacing[1]),
        image_position_patient_mm=(position[0], position[1], position[2]),
        image_orientation_patient=(
            orientation[0],
            orientation[1],
            orientation[2],
            orientation[3],
            orientation[4],
            orientation[5],
        ),
        frame_of_reference_uid=_optional_text(dataset, "FrameOfReferenceUID"),
        spacing_between_slices_mm=_optional_float(dataset, "SpacingBetweenSlices"),
        slice_thickness_mm=_optional_float(dataset, "SliceThickness"),
    )


def read_dicom_record(path: str | Path) -> DicomSourceRecord:
    """Read immutable source metadata; pixel data is intentionally not decoded."""
    try:
        from pydicom import dcmread
    except ImportError as exc:  # pragma: no cover - installation failure
        raise RuntimeError("pydicom is required for DICOM ingest") from exc

    source = Path(path)
    dataset = dcmread(source, stop_before_pixels=True, force=False)
    spatial = extract_spatial_metadata(dataset)
    return DicomSourceRecord(
        source_path=source.as_posix(),
        sha256=sha256_file(source),
        byte_size=source.stat().st_size,
        sop_instance_uid=str(_require(dataset, "SOPInstanceUID")),
        study_instance_uid=_optional_text(dataset, "StudyInstanceUID"),
        series_instance_uid=_optional_text(dataset, "SeriesInstanceUID"),
        modality=_optional_text(dataset, "Modality"),
        spatial=spatial,
    )


def slice_normal(spatial: DicomSpatialMetadata) -> tuple[float, float, float]:
    return _cross(
        spatial.image_orientation_patient[:3],
        spatial.image_orientation_patient[3:],
    )


def slice_coordinate_mm(spatial: DicomSpatialMetadata) -> float:
    return _dot(spatial.image_position_patient_mm, slice_normal(spatial))


def validate_and_sort_series(
    records: Iterable[DicomSourceRecord],
) -> tuple[DicomSourceRecord, ...]:
    items = tuple(records)
    if not items:
        raise ValueError("at least one DICOM source record is required")

    first = items[0].spatial
    for item in items[1:]:
        current = item.spatial
        if current.rows != first.rows or current.columns != first.columns:
            raise SpatialMetadataConflict(
                "Rows/Columns differ within the candidate series"
            )
        for current_value, first_value in zip(
            current.pixel_spacing_mm, first.pixel_spacing_mm, strict=True
        ):
            if not isclose(
                current_value, first_value, rel_tol=0.0, abs_tol=1e-6
            ):
                raise SpatialMetadataConflict(
                    "PixelSpacing differs within the candidate series"
                )
        for current_value, first_value in zip(
            current.image_orientation_patient,
            first.image_orientation_patient,
            strict=True,
        ):
            if not isclose(
                current_value, first_value, rel_tol=0.0, abs_tol=1e-6
            ):
                raise SpatialMetadataConflict(
                    "ImageOrientationPatient differs within the candidate series"
                )

    frame_uids = {item.spatial.frame_of_reference_uid for item in items}
    non_null_frame_uids = {uid for uid in frame_uids if uid is not None}
    if len(non_null_frame_uids) > 1:
        raise SpatialMetadataConflict(
            "FrameOfReferenceUID differs within the candidate series"
        )
    if None in frame_uids and non_null_frame_uids:
        raise SpatialMetadataConflict(
            "FrameOfReferenceUID is missing for only part of the candidate series"
        )

    series_uids = {
        item.series_instance_uid
        for item in items
        if item.series_instance_uid is not None
    }
    if len(series_uids) > 1:
        raise SpatialMetadataConflict(
            "SeriesInstanceUID differs within the candidate series"
        )

    return tuple(
        sorted(items, key=lambda item: slice_coordinate_mm(item.spatial))
    )
