from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ph_geometry import (  # noqa: E402
    CenterlineAuthoringError,
    build_vessel_centerline_authoring_report,
)


class TaskA08Tests(unittest.TestCase):
    def test_not_established_vessels_fail_closed_without_centerlines(self) -> None:
        feasibility = {
            name: {"classification": "not-established"}
            for name in (
                "radial_artery",
                "ulnar_artery",
                "superficial_target_vein",
            )
        }
        report = build_vessel_centerline_authoring_report(
            recorded_at="2026-09-09",
            vascular_feasibility=feasibility,
            manual_correction_complete=False,
            semantic_ids={
                "radial_artery": "structure.radial_artery.left",
                "ulnar_artery": "structure.ulnar_artery.left",
                "superficial_target_vein": None,
            },
        )
        self.assertFalse(report["claims"]["centerlinesCreated"])
        self.assertFalse(report["claims"]["patientSpaceGeometry"])
        self.assertFalse(report["claims"]["medicalValidation"])
        for row in report["structures"]:
            self.assertEqual(row["centerlineStatus"], "blocked")
            self.assertIsNone(row["centerlineUri"])

    def test_eligible_centerline_does_not_silently_invent_geometry(self) -> None:
        feasibility = {
            name: {"classification": "continuous-candidate"}
            for name in (
                "radial_artery",
                "ulnar_artery",
                "superficial_target_vein",
            )
        }
        with self.assertRaisesRegex(
            CenterlineAuthoringError,
            "no extraction implementation is configured",
        ):
            build_vessel_centerline_authoring_report(
                recorded_at="2026-09-09",
                vascular_feasibility=feasibility,
                manual_correction_complete=True,
                semantic_ids={
                    "radial_artery": "structure.radial_artery.left",
                    "ulnar_artery": "structure.ulnar_artery.left",
                    "superficial_target_vein": "structure.cephalic_vein.left",
                },
            )

    def test_missing_feasibility_is_an_error(self) -> None:
        with self.assertRaisesRegex(
            CenterlineAuthoringError,
            "missing vascular feasibility",
        ):
            build_vessel_centerline_authoring_report(
                recorded_at="2026-09-09",
                vascular_feasibility={},
                manual_correction_complete=False,
                semantic_ids={},
            )


if __name__ == "__main__":
    unittest.main()
