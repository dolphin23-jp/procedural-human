from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ph_assets import (  # noqa: E402
    MedicalMasterPromotionBlocked,
    evaluate_medical_master_readiness,
    require_medical_master_ready,
)


class TaskA10Tests(unittest.TestCase):
    def test_incomplete_authoring_cannot_create_medical_master(self) -> None:
        readiness = evaluate_medical_master_readiness(
            recorded_at="2026-09-09",
            manual_correction_record={
                "manualCorrection": {"status": "pending-human-edit"}
            },
            semantic_mapping_record={
                "mappings": [
                    {
                        "anatomicalId": "structure.skin.left_distal_forearm_wrist",
                        "representationAvailable": True,
                    },
                    {
                        "anatomicalId": "structure.radius.left",
                        "representationAvailable": False,
                    },
                ],
                "unresolved": [
                    {
                        "draftLabel": "superficial_target_vein",
                    }
                ],
            },
            centerline_report={"claims": {"centerlinesCreated": False}},
            boundary_lumen_report={
                "claims": {
                    "boundaryLumenRepresentationsCreated": False,
                }
            },
        )
        self.assertEqual(readiness["status"], "blocked")
        self.assertGreaterEqual(len(readiness["blockers"]), 4)
        self.assertFalse(readiness["claims"]["medicalMasterCreated"])
        self.assertFalse(readiness["claims"]["medicalValidation"])
        with self.assertRaises(MedicalMasterPromotionBlocked):
            require_medical_master_ready(readiness)

    def test_even_ready_inputs_do_not_synthesize_medical_master(self) -> None:
        readiness = evaluate_medical_master_readiness(
            recorded_at="2026-09-09",
            manual_correction_record={
                "manualCorrection": {
                    "status": "human-correction-recorded",
                }
            },
            semantic_mapping_record={
                "mappings": [
                    {
                        "anatomicalId": "structure.skin.left_distal_forearm_wrist",
                        "representationAvailable": True,
                    }
                ],
                "unresolved": [],
            },
            centerline_report={"claims": {"centerlinesCreated": True}},
            boundary_lumen_report={
                "claims": {
                    "boundaryLumenRepresentationsCreated": True,
                }
            },
        )
        self.assertEqual(readiness["status"], "ready")
        self.assertEqual(readiness["blockers"], [])
        with self.assertRaisesRegex(
            MedicalMasterPromotionBlocked,
            "creation implementation is not configured",
        ):
            require_medical_master_ready(readiness)


if __name__ == "__main__":
    unittest.main()
