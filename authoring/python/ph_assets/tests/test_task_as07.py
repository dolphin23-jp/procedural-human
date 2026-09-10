from __future__ import annotations

import json
from pathlib import Path
import unittest


class TaskAS07Tests(unittest.TestCase):
    def test_feed_forward_preserves_fail_closed_vascular_state(self) -> None:
        repo_root = Path(__file__).resolve().parents[4]

        feed_forward = json.loads(
            (
                repo_root
                / "authoring/outputs/as07-continuity-feed-forward-20260910.json"
            ).read_text()
        )
        as06 = json.loads(
            (
                repo_root
                / "authoring/outputs/as06-same-subject-continuity-provenance-20260910.json"
            ).read_text()
        )
        a06 = json.loads(
            (
                repo_root
                / "authoring/manual-inputs/a06-manual-correction-status-20260910.json"
            ).read_text()
        )
        a07 = json.loads(
            (
                repo_root
                / "authoring/semantic/a07-semantic-structure-mapping-20260910.json"
            ).read_text()
        )
        a08 = json.loads(
            (
                repo_root
                / "authoring/outputs/a08-vessel-centerline-authoring-report-20260910.json"
            ).read_text()
        )
        a09 = json.loads(
            (
                repo_root
                / "authoring/outputs/a09-boundary-lumen-authoring-report-20260910.json"
            ).read_text()
        )
        a10 = json.loads(
            (
                repo_root
                / "authoring/outputs/a10-medical-master-readiness-20260910.json"
            ).read_text()
        )

        self.assertEqual(feed_forward["task"], "TASK-AS07")
        self.assertEqual(feed_forward["gateS"]["status"], "complete")
        self.assertTrue(
            feed_forward["gateS"][
                "missingMvpVascularIdentitiesReevaluatedFromSameSubjectEvidence"
            ]
        )
        self.assertFalse(feed_forward["gateS"]["wholeBodyMedicalMasterImplied"])

        self.assertEqual(
            as06["disposition"]["status"],
            feed_forward["sourceEvidence"]["as06Disposition"],
        )
        self.assertEqual(as06["disposition"]["radialArteryIdentity"], "unresolved")
        self.assertEqual(as06["disposition"]["superficialVeinIdentity"], "unresolved")

        a06_by_label = {row["draftLabel"]: row for row in a06["structures"]}
        self.assertEqual(
            a06_by_label["radial_artery"]["status"],
            feed_forward["updates"]["a06"]["radialArteryStatus"],
        )
        self.assertEqual(
            a06_by_label["ulnar_artery"]["status"],
            feed_forward["updates"]["a06"]["ulnarArteryStatus"],
        )
        self.assertEqual(
            a06_by_label["superficial_target_vein"]["status"],
            feed_forward["updates"]["a06"]["superficialTargetVeinStatus"],
        )

        a07_by_label = {row["draftLabel"]: row for row in a07["mappings"]}
        self.assertEqual(
            a07_by_label["radial_artery"]["mappingStatus"],
            feed_forward["updates"]["a07"]["radialArteryMappingStatus"],
        )
        self.assertFalse(a07_by_label["radial_artery"]["representationAvailable"])
        self.assertIsNone(a07["unresolved"][0]["anatomicalId"])
        self.assertFalse(a07["claims"]["procedureRoleUsedAsAnatomicalIdentity"])

        a08_by_label = {row["draftLabel"]: row for row in a08["structures"]}
        self.assertEqual(a08_by_label["radial_artery"]["centerlineStatus"], "blocked")
        self.assertEqual(a08_by_label["ulnar_artery"]["centerlineStatus"], "generated")
        self.assertEqual(
            a08_by_label["superficial_target_vein"]["centerlineStatus"], "blocked"
        )

        a09_by_label = {row["draftLabel"]: row for row in a09["structures"]}
        self.assertEqual(a09_by_label["radial_artery"]["representationStatus"], "blocked")
        self.assertEqual(a09_by_label["ulnar_artery"]["representationStatus"], "generated")
        self.assertEqual(
            a09_by_label["superficial_target_vein"]["representationStatus"], "blocked"
        )

        self.assertEqual(a10["status"], "blocked")
        self.assertFalse(a10["claims"]["medicalMasterCreated"])
        self.assertFalse(a10["claims"]["automaticPromotionAllowed"])
        self.assertFalse(feed_forward["claims"]["newHumanReviewPerformed"])
        self.assertFalse(feed_forward["claims"]["medicalValidation"])
        self.assertFalse(feed_forward["claims"]["patientSpaceGeometry"])
        self.assertFalse(feed_forward["claims"]["automaticPromotionAllowed"])


if __name__ == "__main__":
    unittest.main()
