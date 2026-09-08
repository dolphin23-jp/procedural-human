from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ph_segmentation import (  # noqa: E402
    AnchorTrack,
    FeasibilityThresholds,
    NonvascularConfig,
    RgbRule,
    SourceAnchor,
    SourceSliceRecord,
    SourceStackManifest,
    VesselGenerationBlocked,
    VesselSliceObservation,
    build_vascular_feasibility_report,
    generate_nonvascular_draft,
    request_vessel_mask_generation,
)
from ph_segmentation.manifest_io import (  # noqa: E402
    ManifestError,
    load_source_stack_manifest,
)


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def write_rgb_png(
    path: Path,
    width: int,
    height: int,
    pixels: list[tuple[int, int, int]],
) -> None:
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):
            rows.extend(pixels[y * width + x])
    content = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(
            b"IHDR",
            struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0),
        )
        + _png_chunk(b"IDAT", zlib.compress(bytes(rows)))
        + _png_chunk(b"IEND", b"")
    )
    path.write_bytes(content)


def fixture_config() -> NonvascularConfig:
    return NonvascularConfig(
        profile_id="test-source-space-v0",
        skin_rule=RgbRule(
            r_min=100,
            g_max=80,
            b_max=80,
            red_over_green=1.2,
            red_over_blue=1.2,
        ),
        subcutaneous_rule=RgbRule(r_min=180, g_min=130, b_max=100),
        bone_rule=RgbRule(brightness_min=180, saturation_max=20),
        muscle_tendon_rule=RgbRule(
            r_min=100,
            g_max=90,
            b_max=90,
            red_over_green=1.3,
        ),
        radius_track=AnchorTrack(
            (SourceAnchor(0, 2, 2), SourceAnchor(1, 2, 2)),
            max_component_distance_px=2,
        ),
        ulna_track=AnchorTrack(
            (SourceAnchor(0, 5, 2), SourceAnchor(1, 5, 2)),
            max_component_distance_px=2,
        ),
    )


class TaskA05Tests(unittest.TestCase):
    def _make_source_stack(self, root: Path) -> SourceStackManifest:
        records = []
        for index in range(2):
            pixels = [(0, 0, 0)] * 64
            for x in range(1, 7):
                pixels[1 * 8 + x] = (140, 40, 35)
            pixels[2 * 8 + 2] = (220, 220, 220)
            pixels[2 * 8 + 5] = (220, 220, 220)
            pixels[4 * 8 + 2] = (210, 150, 60)
            pixels[4 * 8 + 3] = (130, 45, 40)
            filename = f"slice-{index:03d}.png"
            path = root / filename
            write_rgb_png(path, 8, 8, pixels)
            records.append(
                SourceSliceRecord(
                    filename=filename,
                    sha256=sha256(path.read_bytes()).hexdigest(),
                )
            )
        return SourceStackManifest(
            dataset="development-fixture",
            slices=tuple(records),
        )

    def test_manifest_invariants_reject_missing_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(
                json.dumps(
                    {
                        "dataset": "x",
                        "files": [{"filename": "a.png"}],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ManifestError):
                load_source_stack_manifest(path)

    def test_nonvascular_output_is_v0_candidate_only_and_source_space_only(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            output = root / "authoring-output"
            source.mkdir()
            manifest = self._make_source_stack(source)
            result = generate_nonvascular_draft(
                source,
                manifest,
                output,
                fixture_config(),
            )

            self.assertEqual(result["status"]["validationLevel"], "V0")
            self.assertEqual(result["status"]["reviewStatus"], "unreviewed")
            self.assertTrue(result["status"]["candidateOnly"])
            self.assertFalse(result["coordinateSpace"]["patientSpaceClaim"])
            self.assertEqual(
                result["coordinateSpace"]["kind"],
                "source-image-stack",
            )
            self.assertFalse(result["claims"]["patientSpaceGeometry"])
            self.assertFalse(result["claims"]["medicalValidation"])
            self.assertEqual(
                {item["draftLabel"] for item in result["labels"]},
                {
                    "skin",
                    "subcutaneous_soft_tissue",
                    "radius",
                    "ulna",
                    "major_muscle_tendon_region",
                },
            )
            for label in result["labels"]:
                self.assertEqual(label["status"]["validationLevel"], "V0")
                self.assertEqual(
                    label["status"]["reviewStatus"],
                    "unreviewed",
                )
                self.assertTrue(label["status"]["candidateOnly"])
                self.assertEqual(
                    label["semanticMappingStatus"],
                    "not-assigned-task-a07",
                )
            for vessel in result["blockedVesselLabels"]:
                self.assertEqual(vessel["maskGeneration"], "blocked")
            self.assertTrue(
                (output / "coverage-statistics.v0.json").exists()
            )
            self.assertTrue(
                (
                    output
                    / "masks"
                    / "radius"
                    / "slice-000.pgm"
                ).exists()
            )

    def test_nonvascular_generation_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            manifest = self._make_source_stack(source)
            first = generate_nonvascular_draft(
                source,
                manifest,
                root / "out-a",
                fixture_config(),
            )
            second = generate_nonvascular_draft(
                source,
                manifest,
                root / "out-b",
                fixture_config(),
            )
            self.assertEqual(first, second)
            self.assertEqual(
                (
                    root
                    / "out-a"
                    / "draft-segmentation-manifest.v0.json"
                ).read_bytes(),
                (
                    root
                    / "out-b"
                    / "draft-segmentation-manifest.v0.json"
                ).read_bytes(),
            )

    def test_vessel_mask_generation_is_fail_closed(self) -> None:
        for structure in (
            "radial_artery",
            "ulnar_artery",
            "superficial_target_vein",
        ):
            with self.assertRaises(VesselGenerationBlocked):
                request_vessel_mask_generation(structure)

    def test_feasibility_report_never_promotes_to_validated_segmentation(
        self,
    ) -> None:
        observations = {
            "radial_artery": [
                VesselSliceObservation(
                    i,
                    True,
                    10.0 + i * 0.5,
                    12.0,
                )
                for i in range(8)
            ],
            "ulnar_artery": [
                VesselSliceObservation(
                    i,
                    i in {0, 2, 4},
                    20.0,
                    20.0,
                )
                for i in range(8)
            ],
        }
        report = build_vascular_feasibility_report(
            observations,
            total_slices=8,
            source_manifest_digest_sha256="a" * 64,
            thresholds=FeasibilityThresholds(continuous_min_run=5),
        )
        by_name = {
            item["draftLabel"]: item
            for item in report["structures"]
        }
        self.assertEqual(
            by_name["radial_artery"]["classification"],
            "continuous-candidate",
        )
        self.assertEqual(
            by_name["radial_artery"]["reviewDisposition"],
            "may-proceed-to-manual-review",
        )
        self.assertEqual(
            by_name["ulnar_artery"]["classification"],
            "intermittent-candidate",
        )
        self.assertEqual(
            by_name["superficial_target_vein"]["classification"],
            "not-established",
        )
        for item in by_name.values():
            self.assertTrue(item["maskGenerationBlocked"])
            self.assertFalse(item["validatedSegmentation"])
            self.assertFalse(item["automaticPromotionAllowed"])
            self.assertEqual(item["status"]["validationLevel"], "V0")
            self.assertEqual(
                item["status"]["reviewStatus"],
                "unreviewed",
            )
            self.assertTrue(item["status"]["candidateOnly"])
        self.assertEqual(
            report["status"]["reviewStatus"],
            "unreviewed",
        )
        self.assertTrue(report["status"]["candidateOnly"])
        self.assertFalse(report["claims"]["vesselMasksCreated"])
        self.assertFalse(report["claims"]["patientSpaceGeometry"])


if __name__ == "__main__":
    unittest.main()
