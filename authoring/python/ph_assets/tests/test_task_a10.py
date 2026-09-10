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

    def test_reviewed_a06_still_fails_closed_for_missing_vessels(self) -> None:
        import json

        repo_root = Path(__file__).resolve().parents[4]
        manual = json.loads(
            (
                repo_root
                / "authoring/manual-inputs/"
                "a06-manual-correction-status-20260910.json"
            ).read_text()
        )
        semantic = json.loads(
            (
                repo_root
                / "authoring/semantic/"
                "a07-semantic-structure-mapping-20260910.json"
            ).read_text()
        )
        centerlines = json.loads(
            (
                repo_root
                / "authoring/outputs/"
                "a08-vessel-centerline-authoring-report-20260910.json"
            ).read_text()
        )
        boundaries = json.loads(
            (
                repo_root
                / "authoring/outputs/"
                "a09-boundary-lumen-authoring-report-20260910.json"
            ).read_text()
        )
        as06 = json.loads(
            (
                repo_root
                / "authoring/outputs/"
                "as06-same-subject-continuity-provenance-20260910.json"
            ).read_text()
        )

        readiness = evaluate_medical_master_readiness(
            recorded_at="2026-09-10",
            manual_correction_record=manual,
            semantic_mapping_record=semantic,
            centerline_report=centerlines,
            boundary_lumen_report=boundaries,
        )

        self.assertEqual(
            as06["disposition"]["status"],
            "complete-unresolved-with-stronger-same-subject-evidence",
        )
        self.assertTrue(as06["disposition"]["feedForwardToAS07Allowed"])
        self.assertFalse(
            as06["disposition"]["automaticMedicalMasterPromotionAllowed"]
        )
        self.assertEqual(readiness["status"], "blocked")
        joined = "\n".join(readiness["blockers"])
        self.assertNotIn(
            "TASK-A06 human manual anatomical correction is incomplete",
            joined,
        )
        self.assertIn("radial_artery", joined)
        self.assertIn("superficial_target_vein", joined)
        self.assertFalse(readiness["claims"]["medicalMasterCreated"])


if __name__ == "__main__":
    unittest.main()
