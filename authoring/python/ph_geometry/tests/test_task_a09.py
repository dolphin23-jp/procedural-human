from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ph_geometry import (  # noqa: E402
    BoundaryLumenAuthoringError,
    build_boundary_lumen_authoring_report,
)


class TaskA09Tests(unittest.TestCase):
    def test_missing_vessel_geometry_blocks_boundary_lumen_representation(self) -> None:
        centerline_report = {
            "structures": [
                {
                    "draftLabel": "radial_artery",
                    "anatomicalId": "structure.radial_artery.left",
                    "centerlineStatus": "blocked",
                },
                {
                    "draftLabel": "ulnar_artery",
                    "anatomicalId": "structure.ulnar_artery.left",
                    "centerlineStatus": "blocked",
                },
                {
                    "draftLabel": "superficial_target_vein",
                    "anatomicalId": None,
                    "centerlineStatus": "blocked",
                },
            ]
        }
        report = build_boundary_lumen_authoring_report(
            recorded_at="2026-09-09",
            centerline_report=centerline_report,
            vessel_mask_available={
                "radial_artery": False,
                "ulnar_artery": False,
                "superficial_target_vein": False,
            },
            manual_correction_complete=False,
        )
        self.assertFalse(
            report["claims"]["boundaryLumenRepresentationsCreated"]
        )
        self.assertFalse(report["claims"]["patientSpaceGeometry"])
        for row in report["structures"]:
            self.assertEqual(row["representationStatus"], "blocked")
            self.assertIsNone(row["outsideRegion"])
            self.assertIsNone(row["wallBoundary"])
            self.assertIsNone(row["lumenRegion"])

    def test_eligible_representation_does_not_invent_boundary_geometry(self) -> None:
        centerline_report = {
            "structures": [
                {
                    "draftLabel": name,
                    "anatomicalId": f"structure.{name}.left",
                    "centerlineStatus": "generated",
                }
                for name in (
                    "radial_artery",
                    "ulnar_artery",
                    "superficial_target_vein",
                )
            ]
        }
        with self.assertRaisesRegex(
            BoundaryLumenAuthoringError,
            "no representation implementation is configured",
        ):
            build_boundary_lumen_authoring_report(
                recorded_at="2026-09-09",
                centerline_report=centerline_report,
                vessel_mask_available={
                    "radial_artery": True,
                    "ulnar_artery": True,
                    "superficial_target_vein": True,
                },
                manual_correction_complete=True,
            )


if __name__ == "__main__":
    unittest.main()
