from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "authoring/review/m8v_evaluate_identity_promotion.py"
SPEC = importlib.util.spec_from_file_location("m8v_identity_promotion", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

LEDGER_PATH = ROOT / "authoring/outputs/m8v-v08-evidence-ledger-20260911.json"
TRACK_PATH = ROOT / "authoring/outputs/m8v-v04-candidate-vessel-track-graph-20260910.json"


class IdentityPromotionEvaluationTests(unittest.TestCase):
    def ledger(self) -> dict:
        return json.loads(LEDGER_PATH.read_text())

    def tracks(self) -> dict:
        return json.loads(TRACK_PATH.read_text())

    def write_ledger(self, value: dict, directory: str) -> Path:
        path = Path(directory) / "ledger.json"
        path.write_text(json.dumps(value))
        return path

    def promote_all_claims(self, ledger: dict) -> dict:
        value = copy.deepcopy(ledger)
        claims = {row["id"]: row for row in value["claims"]}
        radial_target = "vhf.m8v.branch-anonymous.01"
        superficial_target = "vhf.m8v.superficial-anonymous.01"

        for claim_id in MODULE.RADIAL_REQUIRED:
            claim = claims[claim_id]
            claim["state"] = "supported"
            claim["humanReviewStatus"] = "accepted"
            claim["humanReviewTargetId"] = radial_target
            claim["validationLevel"] = "V2"
            claim["promotionEligible"] = True

        for claim_id in MODULE.SUPERFICIAL_REQUIRED:
            claim = claims[claim_id]
            claim["state"] = "supported"
            claim["humanReviewStatus"] = "accepted"
            claim["humanReviewTargetId"] = superficial_target
            claim["validationLevel"] = "V2"
            claim["promotionEligible"] = True

        structure = claims[MODULE.STRUCTURE_CLAIM]
        structure["state"] = "supported"
        structure["humanReviewTargetId"] = superficial_target
        structure["promotionEligible"] = True

        for claim_id in (MODULE.NAMED_TOPOLOGY_CLAIM, MODULE.NAMED_IDENTITY_CLAIM):
            claim = claims[claim_id]
            claim["state"] = "supported"
            claim["humanReviewStatus"] = "accepted"
            claim["humanReviewTargetId"] = superficial_target
            claim["validationLevel"] = "V2"
            claim["promotionEligible"] = True

        value["humanReviewSessions"] = [
            {
                "path": "authoring/manual-inputs/test-review.json",
                "sha256": "0" * 64,
                "reviewerReference": "test-reviewer",
                "decisionCount": len(value["claims"]),
            }
        ]
        value["decision"].update(
            {
                "ledgerState": "promotion-ready",
                "humanAdjudicationEvidencePresent": True,
                "radialPromotionReady": True,
                "superficialStructurePromotionReady": True,
                "namedSuperficialPromotionReady": True,
            }
        )
        return value

    def test_current_committed_evidence_remains_fail_closed(self) -> None:
        result = MODULE.build_evaluation(LEDGER_PATH, TRACK_PATH, "2026-09-11")
        self.assertEqual(result["decision"]["state"], "blocked-unresolved")
        self.assertFalse(result["decision"]["anyPromotionGatePassed"])
        self.assertFalse(result["evaluations"]["radialArtery"]["promotionGatePassed"])
        self.assertFalse(
            result["evaluations"]["superficialStructure"]["promotionGatePassed"]
        )
        self.assertFalse(
            result["evaluations"]["namedSuperficialVein"]["promotionGatePassed"]
        )
        self.assertFalse(result["claims"]["medicalValidation"])
        self.assertFalse(result["claims"]["patientSpaceGeometry"])
        self.assertFalse(result["claims"]["procedureRoleEstablished"])
        self.assertFalse(result["claims"]["automaticPromotionAllowed"])

    def test_fully_reviewed_same_target_claims_can_pass_without_auto_promotion(self) -> None:
        ledger = self.promote_all_claims(self.ledger())
        evaluations, cross_checks = MODULE.evaluate(ledger, self.tracks())
        self.assertTrue(evaluations["radialArtery"]["promotionGatePassed"])
        self.assertEqual(
            evaluations["radialArtery"]["targetId"],
            "vhf.m8v.branch-anonymous.01",
        )
        self.assertTrue(evaluations["superficialStructure"]["promotionGatePassed"])
        self.assertTrue(evaluations["namedSuperficialVein"]["promotionGatePassed"])
        self.assertTrue(cross_checks["ledgerDecisionConsistency"])
        self.assertFalse(ledger["assertions"]["automaticPromotionAllowed"])

    def test_rejects_stale_ledger_source_hash(self) -> None:
        ledger = self.ledger()
        ledger["sourceEvidence"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(
            MODULE.IdentityPromotionEvaluationError, "hash mismatch"
        ):
            MODULE.verify_ledger_source_snapshot(ledger)

    def test_rejects_prohibited_automatic_promotion_assertion(self) -> None:
        ledger = self.ledger()
        ledger["assertions"]["automaticPromotionAllowed"] = True
        with self.assertRaisesRegex(
            MODULE.IdentityPromotionEvaluationError, "prohibited"
        ):
            MODULE.evaluate(ledger, self.tracks())

    def test_rejects_missing_claim(self) -> None:
        ledger = self.ledger()
        ledger["claims"] = ledger["claims"][:-1]
        with self.assertRaisesRegex(
            MODULE.IdentityPromotionEvaluationError, "claim set changed"
        ):
            MODULE.evaluate(ledger, self.tracks())

    def test_rejects_aggregate_readiness_that_does_not_match_claims(self) -> None:
        ledger = self.ledger()
        ledger["decision"]["radialPromotionReady"] = True
        with self.assertRaisesRegex(
            MODULE.IdentityPromotionEvaluationError, "aggregate decision mismatch"
        ):
            MODULE.evaluate(ledger, self.tracks())

    def test_rejects_target_outside_competitor_domain(self) -> None:
        ledger = self.promote_all_claims(self.ledger())
        claims = {row["id"]: row for row in ledger["claims"]}
        claims[MODULE.RADIAL_REQUIRED[0]]["humanReviewTargetId"] = (
            "vhf.m8v.superficial-anonymous.01"
        )
        with self.assertRaisesRegex(
            MODULE.IdentityPromotionEvaluationError, "outside its TASK-V04 competitor set"
        ):
            MODULE.evaluate(ledger, self.tracks())

    def test_rejects_mixed_targets_even_when_each_target_is_in_domain(self) -> None:
        ledger = self.promote_all_claims(self.ledger())
        claims = {row["id"]: row for row in ledger["claims"]}
        claims[MODULE.RADIAL_REQUIRED[0]]["humanReviewTargetId"] = (
            "vhf.m8v.branch-anonymous.02"
        )
        ledger["decision"]["radialPromotionReady"] = False
        for claim_id in MODULE.RADIAL_REQUIRED:
            claims[claim_id]["promotionEligible"] = False
        evaluations, _ = MODULE.evaluate(ledger, self.tracks())
        self.assertFalse(evaluations["radialArtery"]["promotionGatePassed"])
        self.assertFalse(evaluations["radialArtery"]["targetConsistencyPass"])
        self.assertIsNone(evaluations["radialArtery"]["targetId"])


if __name__ == "__main__":
    unittest.main()
