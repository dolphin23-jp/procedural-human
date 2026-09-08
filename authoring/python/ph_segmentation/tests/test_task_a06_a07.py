from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ph_segmentation import (  # noqa: E402
    ManualCorrectionRecordError,
    ManualCorrectionStructure,
    SemanticMappingError,
    build_manual_correction_record,
    build_semantic_mapping_record,
)


class TaskA06A07Tests(unittest.TestCase):
    def test_pending_manual_correction_does_not_claim_human_edit_or_review(self) -> None:
        record = build_manual_correction_record(
            recorded_at="2026-09-09",
            source_frame_count=451,
            source_filename_sha_aggregate="a" * 64,
            crop_filename_sha_aggregate="b" * 64,
            candidate_output_digest="c" * 64,
            structures=(
                ManualCorrectionStructure("skin", "pending-human-edit"),
                ManualCorrectionStructure(
                    "radius",
                    "blocked-source-evidence",
                    "full source-space track not established",
                ),
            ),
        )
        self.assertEqual(
            record["manualCorrection"]["status"],
            "pending-human-edit",
        )
        self.assertIsNone(record["manualCorrection"]["editorReference"])
        self.assertFalse(record["claims"]["humanEdited"])
        self.assertFalse(record["claims"]["anatomicallyReviewed"])
        self.assertFalse(record["claims"]["medicalValidation"])
        self.assertFalse(record["claims"]["automaticPromotionAllowed"])

    def test_completed_manual_action_requires_editor_reference(self) -> None:
        with self.assertRaisesRegex(
            ManualCorrectionRecordError,
            "requires editor_reference",
        ):
            build_manual_correction_record(
                recorded_at="2026-09-09",
                source_frame_count=451,
                source_filename_sha_aggregate="a" * 64,
                crop_filename_sha_aggregate="b" * 64,
                candidate_output_digest="c" * 64,
                structures=(
                    ManualCorrectionStructure(
                        "skin",
                        "edited",
                        output_uri="corrected://skin",
                        output_digest="d" * 64,
                    ),
                ),
            )

    def test_completed_structure_requires_hashed_corrected_output(self) -> None:
        with self.assertRaisesRegex(
            ManualCorrectionRecordError,
            "requires output_uri and output_digest",
        ):
            build_manual_correction_record(
                recorded_at="2026-09-09",
                source_frame_count=451,
                source_filename_sha_aggregate="a" * 64,
                crop_filename_sha_aggregate="b" * 64,
                candidate_output_digest="c" * 64,
                editor_reference="qualified-human-editor",
                completed_at="2026-09-09T12:00:00+09:00",
                structures=(
                    ManualCorrectionStructure("skin", "edited"),
                ),
            )

    def test_semantic_mapping_separates_identity_from_representation(self) -> None:
        record = build_semantic_mapping_record(
            recorded_at="2026-09-09",
            generated_labels=(
                "skin",
                "subcutaneous_soft_tissue",
                "major_muscle_tendon_region",
            ),
            blocked_labels=(
                "radius",
                "ulna",
                "radial_artery",
                "ulnar_artery",
            ),
            target_superficial_vein_established=False,
        )
        by_label = {
            row["draftLabel"]: row
            for row in record["mappings"]
        }
        self.assertTrue(by_label["skin"]["representationAvailable"])
        self.assertFalse(by_label["radius"]["representationAvailable"])
        self.assertEqual(
            by_label["radial_artery"]["anatomicalId"],
            "structure.radial_artery.left",
        )
        self.assertEqual(
            record["unresolved"][0]["draftLabel"],
            "superficial_target_vein",
        )
        self.assertIsNone(record["unresolved"][0]["anatomicalId"])
        self.assertFalse(
            record["claims"]["procedureRoleUsedAsAnatomicalIdentity"]
        )
        self.assertFalse(
            record["claims"]["representationPresenceImpliedByIdentity"]
        )

    def test_named_superficial_vein_identity_must_be_explicit(self) -> None:
        with self.assertRaisesRegex(
            SemanticMappingError,
            "explicit named anatomical identity",
        ):
            build_semantic_mapping_record(
                recorded_at="2026-09-09",
                generated_labels=("skin",),
                blocked_labels=(),
                target_superficial_vein_established=True,
            )


if __name__ == "__main__":
    unittest.main()
