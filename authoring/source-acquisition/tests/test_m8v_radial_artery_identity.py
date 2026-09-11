from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "authoring/source-acquisition/m8v_evaluate_radial_artery_identity.py"
SPEC = importlib.util.spec_from_file_location("m8v_radial_identity", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RadialArteryIdentityEvidenceTests(unittest.TestCase):
    def registration(self) -> dict:
        return {
            "schema": "ph-m8v-ct-cryo-registration-scaffold.v1",
            "task": "TASK-V02",
            "status": "complete",
            "decision": {
                "registrationState": "bounded-bone-landmark-scaffold",
                "identityCorrespondence": "direct-radius-ulna-correspondence-supported",
                "usableFor": ["candidate-vessel-evidence-support"],
            },
            "claims": {
                "ctCryosectionMedicalRegistrationEstablished": False,
                "patientSpaceGeometry": False,
                "radialArteryIdentityEstablished": False,
                "medicalValidation": False,
                "automaticPromotionAllowed": False,
            },
        }

    def landmarks(self) -> dict:
        return {
            "schema": "ph-m8v-upper-extremity-landmark-graph.v1",
            "task": "TASK-V03",
            "status": "complete",
            "unresolvedRequiredLandmarks": [
                "structure.radial_styloid.left",
                "structure.brachioradialis.left",
                "structure.flexor_carpi_radialis.left",
                "structure.pronator_quadratus.left",
            ],
            "claims": {
                "radialArteryIdentityEstablished": False,
                "patientSpaceGeometry": False,
            },
        }

    def track_graph(self) -> dict:
        tracks = []
        ids = []
        for index in range(1, 3):
            track_id = f"vhf.m8v.branch-anonymous.{index:02d}"
            ids.append(track_id)
            tracks.append(
                {
                    "id": track_id,
                    "trackClass": "anonymous-branch-search",
                    "sourceClassification": "anonymous-vessel-like-track-only",
                    "observationCount": 50 + index,
                    "spanFrameCount": 60 + index,
                    "coverageFraction": 0.8,
                    "gapLinkCount": 4,
                    "maxMissingFrameCount": 2,
                    "identity": {"namedIdentityStatus": "anonymous-unresolved"},
                    "reviewStatus": "unreviewed-as-complete-track",
                }
            )
        return {
            "schema": "ph-m8v-candidate-vessel-track-graph.v1",
            "task": "TASK-V04",
            "status": "complete",
            "tracks": tracks,
            "competitorSets": [
                {
                    "id": "vhf.m8v.competitors.branch-identity",
                    "trackIds": ids,
                    "resolutionStatus": "unresolved",
                }
            ],
            "branchMergeCandidates": [],
            "decision": {"taskV05InputAvailable": True},
            "claims": {
                "sourceIndex3DTrackGraphEstablished": True,
                "physical3DGeometry": False,
                "patientSpaceGeometry": False,
                "radialArteryIdentityEstablished": False,
                "brachialArteryIdentityEstablished": False,
                "bifurcationIdentityEstablished": False,
                "medicalValidation": False,
                "automaticPromotionAllowed": False,
            },
        }

    def continuity(self) -> dict:
        return {
            "schema": "ph-as06-same-subject-continuity-provenance.v1",
            "task": "TASK-AS06",
            "reviewedUlnarAnchor": {
                "anatomicalId": "structure.ulnar_artery.left",
            },
            "claims": {
                "radialArteryIdentityEstablished": False,
                "brachialArteryIdentityEstablished": False,
                "bifurcationIdentityEstablished": False,
                "patientSpaceGeometry": False,
                "medicalValidation": False,
                "automaticPromotionAllowed": False,
            },
        }

    def test_current_evidence_fails_closed_without_selecting_candidate(self) -> None:
        audit, gates, decision, claims = MODULE.evaluate(
            self.registration(),
            self.landmarks(),
            self.track_graph(),
            self.continuity(),
        )
        self.assertEqual(len(audit), 2)
        self.assertTrue(all(row["selectionStatus"] == "not-selected-competing-candidate" for row in audit))
        statuses = {gate["id"]: gate["status"] for gate in gates}
        self.assertEqual(statuses["unique-same-subject-arterial-anchor"], "fail")
        self.assertEqual(statuses["bounded-gap-continuity-to-target"], "insufficient")
        self.assertEqual(statuses["compatible-branch-topology"], "fail")
        self.assertEqual(statuses["compatible-landmark-relationships"], "insufficient")
        self.assertEqual(statuses["no-equal-or-better-competing-candidate"], "fail")
        self.assertEqual(statuses["explicit-human-anatomical-review"], "fail")
        self.assertEqual(decision["state"], "blocked-unresolved")
        self.assertIsNone(decision["candidateSelected"])
        self.assertFalse(decision["radialArteryPromotionAllowed"])
        self.assertFalse(claims["radialArteryIdentityEstablished"])

    def test_rejects_upstream_radial_identity_promotion(self) -> None:
        track_graph = copy.deepcopy(self.track_graph())
        track_graph["claims"]["radialArteryIdentityEstablished"] = True
        with self.assertRaises(MODULE.RadialIdentityEvidenceError):
            MODULE.evaluate(
                self.registration(),
                self.landmarks(),
                track_graph,
                self.continuity(),
            )

    def test_rejects_competitor_set_that_drops_anonymous_track(self) -> None:
        track_graph = copy.deepcopy(self.track_graph())
        track_graph["competitorSets"][0]["trackIds"] = [
            "vhf.m8v.branch-anonymous.01"
        ]
        with self.assertRaises(MODULE.RadialIdentityEvidenceError):
            MODULE.evaluate(
                self.registration(),
                self.landmarks(),
                track_graph,
                self.continuity(),
            )


if __name__ == "__main__":
    unittest.main()
