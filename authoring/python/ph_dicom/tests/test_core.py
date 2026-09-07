from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from ph_dicom.archive import snapshot_source_archive
from ph_dicom.ingest import (
    DicomSourceRecord,
    SpatialMetadataConflict,
    SpatialMetadataUnavailable,
    extract_spatial_metadata,
    read_dicom_record,
    validate_and_sort_series,
)
from ph_dicom.roi import (
    PixelCrop,
    patient_extent_for_crop,
    patient_point_for_pixel,
)
from ph_dicom.vhp import parse_visible_human_female_fullcolor_name


def dataset(
    z: float = 0.0,
    frame: str | None = "1.2.3",
) -> SimpleNamespace:
    return SimpleNamespace(
        Rows=3,
        Columns=4,
        PixelSpacing=[2.0, 3.0],
        ImagePositionPatient=[10.0, 20.0, z],
        ImageOrientationPatient=[1.0, 0.0, 0.0, 0.0, 1.0, 0.0],
        FrameOfReferenceUID=frame,
        SpacingBetweenSlices=5.0,
        SliceThickness=5.0,
    )


def record(
    z: float,
    frame: str | None = "1.2.3",
) -> DicomSourceRecord:
    return DicomSourceRecord(
        source_path=f"slice-{z}.dcm",
        sha256="0" * 64,
        byte_size=1,
        sop_instance_uid=f"1.2.3.{z}",
        study_instance_uid="1.2.study",
        series_instance_uid="1.2.series",
        modality="CT",
        spatial=extract_spatial_metadata(dataset(z, frame)),
    )


class IngestTests(unittest.TestCase):
    def test_extract_preserves_spatial_fields(self) -> None:
        spatial = extract_spatial_metadata(dataset())
        self.assertEqual(spatial.pixel_spacing_mm, (2.0, 3.0))
        self.assertEqual(
            spatial.image_position_patient_mm,
            (10.0, 20.0, 0.0),
        )
        self.assertEqual(spatial.frame_of_reference_uid, "1.2.3")

    def test_missing_position_fails_instead_of_assuming_identity(self) -> None:
        source = dataset()
        del source.ImagePositionPatient
        with self.assertRaises(SpatialMetadataUnavailable):
            extract_spatial_metadata(source)

    def test_mixed_frames_fail(self) -> None:
        with self.assertRaises(SpatialMetadataConflict):
            validate_and_sort_series(
                [record(0, "1.2.3"), record(5, "9.9.9")]
            )

    def test_series_is_sorted_by_patient_space_slice_coordinate(self) -> None:
        ordered = validate_and_sort_series(
            [record(10), record(0), record(5)]
        )
        self.assertEqual(
            [
                item.spatial.image_position_patient_mm[2]
                for item in ordered
            ],
            [0, 5, 10],
        )

    def test_read_dicom_record_preserves_geometry_and_hashes_source(self) -> None:
        from pydicom.dataset import FileDataset, FileMetaDataset
        from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage

        with TemporaryDirectory() as directory:
            path = Path(directory) / "source.dcm"
            file_meta = FileMetaDataset()
            file_meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
            file_meta.MediaStorageSOPInstanceUID = "1.2.826.0.1.3680043.10.99.1"
            file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
            dataset_file = FileDataset(
                path.name,
                {},
                file_meta=file_meta,
                preamble=b"\0" * 128,
            )
            dataset_file.SOPClassUID = SecondaryCaptureImageStorage
            dataset_file.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
            dataset_file.StudyInstanceUID = "1.2.826.0.1.3680043.10.99.2"
            dataset_file.SeriesInstanceUID = "1.2.826.0.1.3680043.10.99.3"
            dataset_file.Modality = "XC"
            dataset_file.Rows = 3
            dataset_file.Columns = 4
            dataset_file.PixelSpacing = [2.0, 3.0]
            dataset_file.ImagePositionPatient = [10.0, 20.0, 30.0]
            dataset_file.ImageOrientationPatient = [
                1.0,
                0.0,
                0.0,
                0.0,
                1.0,
                0.0,
            ]
            dataset_file.FrameOfReferenceUID = (
                "1.2.826.0.1.3680043.10.99.4"
            )
            dataset_file.save_as(path, enforce_file_format=True)

            source_bytes = path.read_bytes()
            result = read_dicom_record(path)
            self.assertEqual(
                result.sha256,
                sha256(source_bytes).hexdigest(),
            )
            self.assertEqual(result.byte_size, len(source_bytes))
            self.assertEqual(
                result.spatial.image_position_patient_mm,
                (10.0, 20.0, 30.0),
            )


class RoiTests(unittest.TestCase):
    def test_pixel_to_patient_uses_dicom_spacing_order(self) -> None:
        point = patient_point_for_pixel(record(0), column=2, row=1)
        self.assertEqual(point, (16.0, 22.0, 0.0))

    def test_crop_extent_across_slices(self) -> None:
        extent = patient_extent_for_crop(
            [record(0), record(5)],
            PixelCrop(
                column_start=1,
                column_end_exclusive=3,
                row_start=1,
                row_end_exclusive=3,
            ),
        )
        self.assertEqual(extent.minimum_mm, (13.0, 22.0, 0.0))
        self.assertEqual(extent.maximum_mm, (16.0, 24.0, 5.0))


class VhpTests(unittest.TestCase):
    def test_female_fullcolor_suffix_mapping(self) -> None:
        self.assertEqual(
            str(
                parse_visible_human_female_fullcolor_name(
                    "avf1703a.png"
                ).nominal_source_z_mm
            ),
            "1703",
        )
        self.assertEqual(
            str(
                parse_visible_human_female_fullcolor_name(
                    "avf1703b.raw.Z"
                ).nominal_source_z_mm
            ),
            "1703.3333333333",
        )
        self.assertEqual(
            str(
                parse_visible_human_female_fullcolor_name(
                    "avf1703c.dcm"
                ).nominal_source_z_mm
            ),
            "1703.6666666667",
        )


class ArchiveTests(unittest.TestCase):
    def test_snapshot_records_sha256_and_size(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.bin").write_bytes(b"abc")
            snapshot = snapshot_source_archive(
                root,
                ["a.bin"],
                source_archive_id="test",
                retrieved_at=datetime(
                    2026,
                    9,
                    8,
                    tzinfo=timezone.utc,
                ),
            )
            self.assertEqual(
                snapshot.files[0].sha256,
                "ba7816bf8f01cfea414140de5dae2223"
                "b00361a396177a9cb410ff61f20015ad",
            )
            self.assertEqual(snapshot.files[0].byte_size, 3)
            self.assertEqual(
                snapshot.retrieved_at,
                "2026-09-08T00:00:00Z",
            )


if __name__ == "__main__":
    unittest.main()
