from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "authoring/source-acquisition/m8v_evaluate_superficial_venous_network.py"
SPEC = importlib.util.spec_from_file_location("m8v_superficial_network", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SuperficialVenousNetworkEvidenceTests(unittest.TestCase):
    def track(self, rank: int, start: int, x: float) -> dict:
        track_id = f"vhf.m8v.superficial-anonymous.{rank:02d}"
        observations = []
        for ordinal, frame in enumerate((start, start + 1), start=1):
            observations.append(
                {
                    "id": f"{track_id}.obs.{ordinal:04d}",
                    "wholeBodyFrameIndex": frame,
                    "xFullImagePixels": x + ordinal - 1,
                    "yFullImagePixels": 500.0,
                    "circularity": 0.6,
                    "contrast": 25.0,
                    "depthPixels": 8.0,
                    "directSourceObservation": True,
                }
            )
        return {
            "id": track_id,
            "trackClass": "anonymous-superficial-search",
            "sourceClassification": "anonymous-superficial-diagnostic-track",
            "identity": {
                "namedIdentityStatus": "anonymous-unresolved",
                "vesselClassStatus": "superficial-vessel-like-unknown",
            },
            "reviewStatus": "unreviewed-as-complete-track",
            "observationCount": 2,
            "spanFrameCount": 2,
            "coverageFraction": 1.0,
            "minWholeBodyFrameIndex": start,
            "maxWholeBodyFrameIndex": start + 1,
            "gapLinkCount": 0,
            "maxMissingFrameCount": 0,
            "observations": observations,
            "links": [],
        }

    def track_graph(self) -> dict:
        tracks = [
            self.track(1, 100, 100.0),
            self.track(2, 103, 103.0),
        ]
        for rank in range(3, 9):
            tracks.append(self.track(rank, 200 + rank * 20, 400.0 + rank * 40))
        ids = [track["id"] for track in tracks]
        return {
            "schema": "ph-m8v-candidate-vessel-track-graph.v1",
            "task": "TASK-V04",
            "status": "complete",
            "tracks": tracks,
            "competitorSets": [
                {
                    "id": "vhf.m8v.competitors.superficial-structure",
                    "trackIds": ids,
                    "resolutionStatus": "unresolved",
                }
            ],
            "decision": {"taskV06InputAvailable": True},
            "claims": {
                "sourceIndex3DTrackGraphEstablished": True,
                "physical3DGeometry": False,
                "patientSpaceGeometry": False,
                "superficialVeinClassEstablished": False,
                "namedSuperficialVeinIdentityEstablished": False,
                "procedureRoleEstablished": False,
                "medicalValidation": False,
                "automaticPromotionAllowed": False,
            },
        }

    def landmarks(self) -> dict:
        return {
            "schema": "ph-m8v-upper-extremity-landmark-graph.v1",
            "task": "TASK-V03",
            "status": "complete",
            "claims": {
                "patientSpaceGeometry": False,
                "superficialVeinIdentityEstablished": False,
                "medicalValidation": False,
                "automaticPromotionAllowed": False,
            },
        }

    def continuity(self) -> dict:
        return {
            "schema": "ph-as06-same-subject-continuity-provenance.v1",
            "task": "TASK-AS06",
            "phase2": {
                "superficialVenousSearch": {
                    "anonymousTrackCount": 8,
                    "continuousAnonymousCandidateCount": 0,
                }
            },
            "claims": {
                "namedSuperficialVeinIdentityEstablished": False,
                "automaticPromotionAllowed": False,
            },
        }

    def test_fragmented_tracks_and_hypotheses_do_not_promote_structure(self) -> None:
        audit, hypotheses, summary, gates, decision, claims = MODULE.evaluate(
            self.track_graph(), self.landmarks(), self.continuity()
        )
        self.assertEqual(len(audit), 8)
        self.assertEqual(summary["directProcedureRelevantTrackCount"], 0)
        self.assertEqual(summary["directContinuousCandidateCount"], 0)
        self.assertGreaterEqual(len(hypotheses), 1)
        self.assertTrue(all(item["directContinuityClaim"] is False for item in hypotheses))
        statuses = {gate["id"]: gate["status"] for gate in gates}
        self.assertEqual(statuses["direct-observation-over-procedure-relevant-extent"], "fail")
        self.assertEqual(statuses["single-structure-continuity"], "fail")
        self.assertEqual(statuses["superficial-subcutaneous-relationship"], "insufficient")
        self.assertEqual(statuses["vein-class-evidence"], "fail")
        self.assertEqual(statuses["competing-track-conflict-review"], "fail")
        self.assertEqual(statuses["explicit-human-anatomical-review"], "fail")
        self.assertEqual(decision["state"], "blocked-unresolved")
        self.assertIsNone(decision["candidateSelected"])
        self.assertFalse(claims["observedSuperficialVeinStructureEstablished"])
        self.assertFalse(claims["namedSuperficialVeinIdentityEstablished"])

    def test_rejects_preestablished_vein_class(self) -> None:
        graph = copy.deepcopy(self.track_graph())
        graph["tracks"][0]["identity"]["vesselClassStatus"] = "superficial-vein"
        with self.assertRaises(MODULE.SuperficialNetworkEvidenceError):
            MODULE.evaluate(graph, self.landmarks(), self.continuity())

    def test_overlapping_tracks_are_not_linked_as_continuation(self) -> None:
        graph = self.track_graph()
        graph["tracks"][1] = self.track(2, 100, 103.0)
        graph["competitorSets"][0]["trackIds"] = [track["id"] for track in graph["tracks"]]
        _, hypotheses, _, _, _, _ = MODULE.evaluate(
            graph, self.landmarks(), self.continuity()
        )
        linked_pairs = {
            (item["fromTrackId"], item["toTrackId"]) for item in hypotheses
        }
        self.assertNotIn(
            ("vhf.m8v.superficial-anonymous.01", "vhf.m8v.superficial-anonymous.02"),
            linked_pairs,
        )


if __name__ == "__main__":
    unittest.main()
