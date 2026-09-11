from __future__ import annotations

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "authoring/review/m8v_build_evidence_ledger.py"
SPEC = importlib.util.spec_from_file_location("m8v_build_evidence_ledger", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

RADIAL = ROOT / "authoring/outputs/m8v-v05-radial-artery-identity-evidence-20260911.json"
SUPERFICIAL = ROOT / "authoring/outputs/m8v-v06-superficial-venous-network-evidence-20260911.json"
V07 = ROOT / "authoring/outputs/m8v-v07-multimodal-review-surface-20260911.json"
TRACKS = ROOT / "authoring/outputs/m8v-v04-candidate-vessel-track-graph-20260910.json"
LANDMARKS = ROOT / "authoring/outputs/m8v-v03-upper-extremity-landmark-graph-20260910.json"
LEDGER_SCHEMA = ROOT / "schemas/assets/m8v-evidence-ledger.v1.schema.json"
SESSION_SCHEMA = ROOT / "schemas/assets/m8v-human-adjudication-session.v1.schema.json"


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def build(review_paths: list[Path] | None = None) -> dict:
    return MODULE.build_ledger(
        RADIAL,
        SUPERFICIAL,
        V07,
        TRACKS,
        LANDMARKS,
        "2026-09-11",
        review_paths or [],
    )


def valid_session(claim_id: str = "radial.gate.human-review") -> dict:
    v07 = json.loads(V07.read_text())
    return {
        "schema": "ph-m8v-human-adjudication-session.v1",
        "schemaVersion": "1",
        "task": "TASK-V08",
        "reviewerReference": "test-reviewer",
        "startedAt": "2026-09-11T00:00:00Z",
        "exportedAt": "2026-09-11T00:10:00Z",
        "reviewTool": {
            "name": "Procedural Human M8V Adjudication",
            "version": "1",
            "route": "?m8v-adjudicate=1",
        },
        "reviewSurface": {
            "path": V07.relative_to(ROOT).as_posix(),
            "schema": "ph-m8v-multimodal-review-surface.v1",
            "sha256": digest(V07),
        },
        "evidenceSnapshot": v07["inputEvidence"],
        "decisions": [
            {
                "claimId": claim_id,
                "kind": "radial-artery-identity",
                "targetId": "vhf.m8v.branch-anonymous.01",
                "verdict": "accepted",
                "evidenceFrameIndices": [1800],
                "note": "Test-only explicit claim adjudication.",
            }
        ],
        "claims": {
            "humanReviewInputRecorded": True,
            "medicalValidation": False,
            "procedureRoleEstablished": False,
            "automaticPromotionAllowed": False,
        },
    }


class EvidenceLedgerTests(unittest.TestCase):
    def test_initial_ledger_is_complete_but_fail_closed(self) -> None:
        ledger = build()
        self.assertEqual(ledger["status"], "complete")
        self.assertEqual(len(ledger["claims"]), 15)
        self.assertEqual(ledger["decision"]["ledgerState"], "blocked-unresolved")
        self.assertFalse(ledger["decision"]["humanAdjudicationEvidencePresent"])
        self.assertFalse(ledger["decision"]["radialPromotionReady"])
        self.assertFalse(ledger["decision"]["superficialStructurePromotionReady"])
        self.assertFalse(ledger["decision"]["namedSuperficialPromotionReady"])
        self.assertFalse(ledger["assertions"]["automaticPromotionAllowed"])

    def test_initial_ledger_validates_against_schema(self) -> None:
        ledger = build()
        schema = json.loads(LEDGER_SCHEMA.read_text())
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(ledger)

    def test_valid_human_review_satisfies_only_reviewed_claim(self) -> None:
        session = valid_session()
        session_schema = json.loads(SESSION_SCHEMA.read_text())
        Draft202012Validator.check_schema(session_schema)
        Draft202012Validator(session_schema).validate(session)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "review.json"
            path.write_text(json.dumps(session))
            ledger = build([path])
        reviewed = next(
            claim for claim in ledger["claims"] if claim["id"] == "radial.gate.human-review"
        )
        anchor = next(
            claim
            for claim in ledger["claims"]
            if claim["id"] == "radial.gate.same-subject-anchor"
        )
        self.assertEqual(reviewed["state"], "supported")
        self.assertEqual(reviewed["humanReviewStatus"], "accepted")
        self.assertEqual(reviewed["validationLevel"], "V2")
        self.assertNotEqual(anchor["state"], "supported")
        self.assertEqual(anchor["humanReviewStatus"], "not-reviewed")
        self.assertFalse(ledger["decision"]["radialPromotionReady"])
        self.assertEqual(ledger["decision"]["ledgerState"], "partially-adjudicated")

    def test_stale_review_surface_hash_is_rejected(self) -> None:
        session = valid_session()
        session["reviewSurface"]["sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "review.json"
            path.write_text(json.dumps(session))
            with self.assertRaisesRegex(ValueError, "TASK-V07 hash mismatch"):
                build([path])

    def test_accepted_review_requires_evidence_frame(self) -> None:
        session = valid_session()
        session["decisions"][0]["evidenceFrameIndices"] = []
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "review.json"
            path.write_text(json.dumps(session))
            with self.assertRaisesRegex(ValueError, "requires at least one evidence frame"):
                build([path])

    def test_unknown_claim_is_rejected(self) -> None:
        session = valid_session("radial.unknown")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "review.json"
            path.write_text(json.dumps(session))
            with self.assertRaisesRegex(ValueError, "unknown human adjudication claim"):
                build([path])

    def test_kind_mismatch_is_rejected(self) -> None:
        session = valid_session()
        session["decisions"][0]["kind"] = "vessel-class"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "review.json"
            path.write_text(json.dumps(session))
            with self.assertRaisesRegex(ValueError, "kind mismatch"):
                build([path])

    def test_radial_claim_cannot_target_superficial_track(self) -> None:
        session = valid_session()
        session["decisions"][0]["targetId"] = "vhf.m8v.superficial-anonymous.01"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "review.json"
            path.write_text(json.dumps(session))
            with self.assertRaisesRegex(ValueError, "non-radial competitor track"):
                build([path])

    def test_review_frame_outside_v07_coverage_is_rejected(self) -> None:
        session = valid_session()
        session["decisions"][0]["evidenceFrameIndices"] = [999999]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "review.json"
            path.write_text(json.dumps(session))
            with self.assertRaisesRegex(ValueError, "outside TASK-V07 coverage"):
                build([path])

    def test_duplicate_claim_in_one_session_is_rejected(self) -> None:
        session = valid_session()
        session["decisions"].append(dict(session["decisions"][0]))
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "review.json"
            path.write_text(json.dumps(session))
            with self.assertRaisesRegex(ValueError, "duplicate human adjudication claim"):
                build([path])


if __name__ == "__main__":
    unittest.main()
