from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "authoring/review/m8v_feed_promotion_to_m8a.py"
SPEC = importlib.util.spec_from_file_location("m8v_m8a_feed_forward", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

V09 = ROOT / "authoring/outputs/m8v-v09-identity-promotion-evaluation-20260911.json"
AS07 = ROOT / "authoring/outputs/as07-continuity-feed-forward-20260910.json"
A07 = ROOT / "authoring/semantic/a07-semantic-structure-mapping-20260910.json"
A08 = ROOT / "authoring/outputs/a08-vessel-centerline-authoring-report-20260910.json"
A09 = ROOT / "authoring/outputs/a09-boundary-lumen-authoring-report-20260910.json"
A10 = ROOT / "authoring/outputs/a10-medical-master-readiness-20260910.json"


def build(v09_path: Path = V09) -> dict:
    return MODULE.build_feed_forward(
        v09_path,
        AS07,
        A07,
        A08,
        A09,
        A10,
        "2026-09-11",
    )


class M8VToM8AFeedForwardTests(unittest.TestCase):
    def test_current_evidence_feeds_no_new_identity_or_geometry(self) -> None:
        result = build()
        self.assertEqual(result["gateV"]["status"], "complete")
        self.assertEqual(result["gateV"]["outcome"], "fail-closed-documented")
        self.assertEqual(result["a10Reevaluation"]["status"], "blocked")
        self.assertFalse(result["a10Reevaluation"]["medicalMasterCreationAllowed"])
        self.assertFalse(result["promotionInput"]["anyPromotionGatePassed"])
        self.assertEqual(
            result["feedForwardActions"]["radialArtery"]["identityClaimStatus"],
            "blocked",
        )
        self.assertEqual(
            result["feedForwardActions"]["superficialStructure"]["identityClaimStatus"],
            "blocked",
        )
        self.assertFalse(result["claims"]["newRadialIdentityApplied"])
        self.assertFalse(result["claims"]["newSuperficialStructureIdentityApplied"])
        self.assertFalse(result["claims"]["newNamedSuperficialVeinIdentityApplied"])
        self.assertFalse(result["claims"]["newGeometryPromoted"])
        self.assertTrue(result["claims"]["existingUlnarEvidencePreserved"])
        self.assertFalse(result["claims"]["medicalMasterCreated"])
        self.assertFalse(result["claims"]["medicalValidation"])
        self.assertFalse(result["claims"]["patientSpaceGeometry"])
        self.assertFalse(result["claims"]["automaticPromotionAllowed"])

    def test_future_identity_pass_is_only_authoring_eligible_not_geometry(self) -> None:
        v09 = json.loads(V09.read_text())
        v09 = copy.deepcopy(v09)
        radial = v09["evaluations"]["radialArtery"]
        radial["promotionGatePassed"] = True
        radial["decision"] = "promotable"
        radial["targetId"] = "vhf.m8v.branch-anonymous.01"
        radial["blockingClaimIds"] = []
        radial["blockingReasons"] = []
        v09["claims"]["radialArteryPromotionGatePassed"] = True
        v09["decision"]["anyPromotionGatePassed"] = True
        v09["decision"]["state"] = "promotion-ready"

        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "v09.json"
            path.write_text(json.dumps(v09))
            result = build(path)

        self.assertEqual(result["gateV"]["outcome"], "promotion-fed")
        self.assertEqual(
            result["feedForwardActions"]["radialArtery"]["identityClaimStatus"],
            "eligible-for-a07-authoring",
        )
        self.assertEqual(
            result["feedForwardActions"]["radialArtery"]["targetId"],
            "vhf.m8v.branch-anonymous.01",
        )
        self.assertFalse(
            result["feedForwardActions"]["radialArtery"]["geometryPromotionApplied"]
        )
        self.assertFalse(result["claims"]["newGeometryPromoted"])
        self.assertEqual(result["a10Reevaluation"]["status"], "blocked")
        self.assertFalse(result["claims"]["medicalMasterCreated"])

    def test_rejects_failed_v09_cross_check(self) -> None:
        v09 = json.loads(V09.read_text())
        v09["crossChecks"]["ledgerDecisionConsistency"] = False
        with self.assertRaisesRegex(MODULE.M8VFeedForwardError, "cross-checks"):
            MODULE.verify_inputs(
                v09,
                json.loads(AS07.read_text()),
                json.loads(A07.read_text()),
                json.loads(A08.read_text()),
                json.loads(A09.read_text()),
                json.loads(A10.read_text()),
            )

    def test_rejects_v09_automatic_promotion(self) -> None:
        v09 = json.loads(V09.read_text())
        v09["claims"]["automaticPromotionAllowed"] = True
        with self.assertRaisesRegex(MODULE.M8VFeedForwardError, "prohibited claim"):
            MODULE.verify_inputs(
                v09,
                json.loads(AS07.read_text()),
                json.loads(A07.read_text()),
                json.loads(A08.read_text()),
                json.loads(A09.read_text()),
                json.loads(A10.read_text()),
            )

    def test_rejects_loss_of_existing_ulnar_centerline(self) -> None:
        a08 = json.loads(A08.read_text())
        for row in a08["structures"]:
            if row["draftLabel"] == "ulnar_artery":
                row["centerlineStatus"] = "blocked"
        with self.assertRaisesRegex(MODULE.M8VFeedForwardError, "ulnar A08"):
            MODULE.verify_inputs(
                json.loads(V09.read_text()),
                json.loads(AS07.read_text()),
                json.loads(A07.read_text()),
                a08,
                json.loads(A09.read_text()),
                json.loads(A10.read_text()),
            )

    def test_rejects_a10_automatic_promotion(self) -> None:
        a10 = json.loads(A10.read_text())
        a10["claims"]["automaticPromotionAllowed"] = True
        with self.assertRaisesRegex(MODULE.M8VFeedForwardError, "A10 automatic promotion"):
            MODULE.verify_inputs(
                json.loads(V09.read_text()),
                json.loads(AS07.read_text()),
                json.loads(A07.read_text()),
                json.loads(A08.read_text()),
                json.loads(A09.read_text()),
                a10,
            )


if __name__ == "__main__":
    unittest.main()
