from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "authoring/source-acquisition/m8v_build_candidate_vessel_track_graph.py"
SPEC = importlib.util.spec_from_file_location("m8v_track_graph", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CandidateVesselTrackGraphTests(unittest.TestCase):
    def landmark_graph(self) -> dict:
        return {
            "schema": "ph-m8v-upper-extremity-landmark-graph.v1",
            "task": "TASK-V03",
            "status": "complete",
            "coordinateSpace": {"patientSpaceClaim": False},
            "decision": {"usableForTaskV04": True},
            "claims": {
                "patientSpaceGeometry": False,
                "namedMuscleIdentityEstablished": False,
                "radialArteryIdentityEstablished": False,
                "superficialVeinIdentityEstablished": False,
                "medicalValidation": False,
                "automaticPromotionAllowed": False,
            },
        }

    def phase1(self) -> dict:
        return {
            "schema": "ph-as06-upper-extremity-continuity-recon.v1",
            "task": "TASK-AS06",
            "coordinateSpace": {
                "kind": "source-image-stack",
                "patientSpaceClaim": False,
                "physicalXyClaim": False,
            },
            "claims": {
                "anatomicallyReviewed": False,
                "automaticPromotionAllowed": False,
                "brachialArteryIdentityEstablished": False,
                "crossSubjectGeometryUsed": False,
                "ctRegistrationEstablished": False,
                "humanEdited": False,
                "medicalValidation": False,
                "namedSuperficialVeinIdentityEstablished": False,
                "patientSpaceGeometry": False,
                "radialArteryIdentityEstablished": False,
            },
            "anchorLineage": {
                "anatomicalId": "structure.ulnar_artery.left",
                "completeVesselExtentClaim": False,
            },
            "ulnarArteryRetrogradeContinuity": {
                "claims": {
                    "identityBeyondObservedContinuityAutomaticallyEstablished": False,
                },
                "nodes": [
                    {
                        "wholeBodyFrameIndex": 20,
                        "sourceFilename": "avf0001a.png",
                        "xFullImagePixels": 100.0,
                        "yFullImagePixels": 200.0,
                        "evidenceKind": "reviewed-ulnar-anchor-start",
                    },
                    {
                        "wholeBodyFrameIndex": 19,
                        "sourceFilename": "avf0000c.png",
                        "xFullImagePixels": 101.0,
                        "yFullImagePixels": 201.0,
                        "areaPixels": 10,
                        "circularity": 0.8,
                        "contrast": 20.0,
                    },
                ],
            },
            "ulnarBridgeSearch": {
                "sameSubjectContinuitySupportedToBoneTransition": True,
                "claims": {"sameNamedVesselBeyondSourceContinuityClaim": False},
                "observations": [
                    {
                        "wholeBodyFrameIndex": 16,
                        "sourceFilename": "avf0000a.png",
                        "xFullImagePixels": 102.0,
                        "yFullImagePixels": 202.0,
                        "areaPixels": 11,
                        "circularity": 0.7,
                        "contrast": 18.0,
                    },
                    {
                        "wholeBodyFrameIndex": 15,
                        "sourceFilename": "avf-0001c.png",
                        "xFullImagePixels": 103.0,
                        "yFullImagePixels": 203.0,
                        "areaPixels": 12,
                        "circularity": 0.9,
                        "contrast": 22.0,
                    },
                ],
            },
            "nextSearchReadiness": {
                "radialIdentityPromotionAuthorized": False,
                "superficialVeinIdentityPromotionAuthorized": False,
            },
        }

    def phase2(self) -> dict:
        return {
            "schema": "ph-as06-branch-superficial-recon.v1",
            "task": "TASK-AS06",
            "coordinateSpace": {
                "kind": "source-image-stack",
                "patientSpaceClaim": False,
            },
            "claims": {
                "anatomicallyReviewed": False,
                "automaticPromotionAllowed": False,
                "brachialArteryIdentityEstablished": False,
                "crossSubjectGeometryUsed": False,
                "ctRegistrationEstablished": False,
                "humanEdited": False,
                "medicalValidation": False,
                "namedSuperficialVeinIdentityEstablished": False,
                "patientSpaceGeometry": False,
                "procedureRoleUsedAsAnatomicalIdentity": False,
                "radialArteryIdentityEstablished": False,
            },
            "arterialBranchTopologySearch": {
                "knownUlnarContinuityUsedAsAnchor": True,
                "crossSubjectAtlasUsed": False,
                "anonymousTrackCount": 1,
                "tracks": [
                    {
                        "rank": 1,
                        "nodeCount": 3,
                        "spanFrameCount": 4,
                        "branchTopologyClassification": "anonymous-vessel-like-track-only",
                        "nodes": [
                            {
                                "wholeBodyFrameIndex": 30,
                                "xFullImagePixels": 300.0,
                                "yFullImagePixels": 400.0,
                                "areaPixels": 8,
                                "circularity": 0.7,
                                "contrast": 15.0,
                                "depthPixels": None,
                            },
                            {
                                "wholeBodyFrameIndex": 31,
                                "xFullImagePixels": 301.0,
                                "yFullImagePixels": 401.0,
                                "areaPixels": 9,
                                "circularity": 0.8,
                                "contrast": 16.0,
                                "depthPixels": None,
                            },
                            {
                                "wholeBodyFrameIndex": 33,
                                "xFullImagePixels": 303.0,
                                "yFullImagePixels": 403.0,
                                "areaPixels": 10,
                                "circularity": 0.9,
                                "contrast": 17.0,
                                "depthPixels": None,
                            },
                        ],
                    }
                ],
            },
            "superficialVenousSearch": {
                "namedVeinAtlasUsed": False,
                "procedureRoleUsedAsIdentity": False,
                "anonymousTrackCount": 1,
                "tracks": [
                    {
                        "rank": 1,
                        "nodeCount": 2,
                        "spanFrameCount": 2,
                        "classification": "anonymous-superficial-diagnostic-track",
                        "nodes": [
                            {
                                "wholeBodyFrameIndex": 40,
                                "xFullImagePixels": 500.0,
                                "yFullImagePixels": 600.0,
                                "areaPixels": 7,
                                "circularity": 0.6,
                                "contrast": 12.0,
                                "depthPixels": 5.0,
                            },
                            {
                                "wholeBodyFrameIndex": 41,
                                "xFullImagePixels": 501.0,
                                "yFullImagePixels": 601.0,
                                "areaPixels": 8,
                                "circularity": 0.7,
                                "contrast": 13.0,
                                "depthPixels": 6.0,
                            },
                        ],
                    }
                ],
            },
        }

    def build(self, *, phase1: dict | None = None, phase2: dict | None = None, landmarks: dict | None = None) -> dict:
        return MODULE.build_track_graph(
            self.phase1() if phase1 is None else phase1,
            self.phase2() if phase2 is None else phase2,
            self.landmark_graph() if landmarks is None else landmarks,
            artifact_id=123,
            artifact_sha256="a" * 64,
            phase1_filename="phase1.json",
            phase1_sha256="b" * 64,
            phase2_filename="phase2.json",
            phase2_sha256="c" * 64,
            landmark_graph_path="authoring/outputs/m8v-v03.json",
            recorded_at="2026-09-10",
        )

    def test_builds_source_index_3d_graph_with_explicit_gaps_and_competitors(self) -> None:
        graph = self.build()
        self.assertEqual(graph["coordinateSpace"]["kind"], "source-image-stack-index-3d")
        self.assertFalse(graph["coordinateSpace"]["physicalZClaim"])
        self.assertEqual(len(graph["tracks"]), 3)
        self.assertEqual(len(graph["competitorSets"]), 2)
        self.assertTrue(graph["claims"]["sourceIndex3DTrackGraphEstablished"])
        self.assertFalse(graph["claims"]["physical3DGeometry"])
        self.assertFalse(graph["claims"]["radialArteryIdentityEstablished"])
        ulnar = graph["tracks"][0]
        self.assertEqual(ulnar["identity"]["anchorAnatomicalId"], "structure.ulnar_artery.left")
        self.assertFalse(ulnar["identity"]["namedIdentityAppliesToEntireTrack"])
        self.assertGreaterEqual(ulnar["gapLinkCount"], 1)
        anonymous_branch = graph["tracks"][1]
        self.assertEqual(anonymous_branch["identity"]["namedIdentityStatus"], "anonymous-unresolved")
        self.assertEqual(anonymous_branch["links"][-1]["kind"], "explicit-gap")
        self.assertEqual(anonymous_branch["links"][-1]["missingFrameCount"], 1)

    def test_branch_topology_candidate_stays_unreviewed_and_has_no_identity_implication(self) -> None:
        phase2 = self.phase2()
        phase2["arterialBranchTopologySearch"]["tracks"][0]["branchTopologyClassification"] = "distinct-distal-track-with-proximal-convergence-candidate"
        graph = self.build(phase2=phase2)
        self.assertEqual(len(graph["branchMergeCandidates"]), 1)
        candidate = graph["branchMergeCandidates"][0]
        self.assertEqual(candidate["kind"], "branch-candidate")
        self.assertFalse(candidate["identityImplicationAllowed"])
        self.assertFalse(graph["claims"]["bifurcationIdentityEstablished"])

    def test_rejects_any_upstream_radial_identity_promotion(self) -> None:
        phase2 = copy.deepcopy(self.phase2())
        phase2["claims"]["radialArteryIdentityEstablished"] = True
        with self.assertRaises(MODULE.TrackGraphError):
            self.build(phase2=phase2)

    def test_rejects_cross_subject_atlas_geometry(self) -> None:
        phase2 = copy.deepcopy(self.phase2())
        phase2["arterialBranchTopologySearch"]["crossSubjectAtlasUsed"] = True
        with self.assertRaises(MODULE.TrackGraphError):
            self.build(phase2=phase2)

    def test_rejects_procedure_role_as_superficial_identity(self) -> None:
        phase2 = copy.deepcopy(self.phase2())
        phase2["superficialVenousSearch"]["procedureRoleUsedAsIdentity"] = True
        with self.assertRaises(MODULE.TrackGraphError):
            self.build(phase2=phase2)

    def test_rejects_patient_space_landmark_graph(self) -> None:
        landmarks = copy.deepcopy(self.landmark_graph())
        landmarks["coordinateSpace"]["patientSpaceClaim"] = True
        with self.assertRaises(MODULE.TrackGraphError):
            self.build(landmarks=landmarks)

    def test_schema_accepts_builder_output(self) -> None:
        schema = json.loads(
            (ROOT / "schemas/assets/m8v-candidate-vessel-track-graph.v1.schema.json").read_text(encoding="utf-8")
        )
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(self.build())


if __name__ == "__main__":
    unittest.main()
