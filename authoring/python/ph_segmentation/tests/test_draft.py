from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ph_segmentation.draft import (
    DraftSegment,
    DraftSegmentationManifest,
    mvp0_required_draft_segments,
)


class DraftSegmentationTests(unittest.TestCase):
    def manifest(self, segments=None) -> DraftSegmentationManifest:
        return DraftSegmentationManifest(
            segmentation_id="draft.mvp0.left-wrist.v0",
            roi_id="mvp0-left-distal-forearm-wrist-v0",
            source_archive_id="source.nlm.vhp-female",
            source_stack_hash="sha256:" + "0" * 64,
            coordinate_space="source-image-stack",
            registration_status="unverified",
            segments=tuple(segments or mvp0_required_draft_segments()),
        )

    def test_required_labels_are_present_without_canonical_ids(self) -> None:
        manifest = self.manifest()
        names = {segment.local_name for segment in manifest.segments}
        self.assertEqual(
            names,
            {
                "skin",
                "subcutaneous-soft-tissue",
                "radius",
                "ulna",
                "radial-artery",
                "ulnar-artery",
                "superficial-target-vein",
                "major-muscle-tendon-region",
            },
        )
        self.assertTrue(
            all(segment.validation_level == "V0" for segment in manifest.segments)
        )
        self.assertTrue(
            all(segment.review_status == "unreviewed" for segment in manifest.segments)
        )

    def test_unestablished_vessels_are_blocked_not_fabricated(self) -> None:
        manifest = self.manifest()
        vessels = {
            segment.local_name: segment
            for segment in manifest.segments
            if "artery" in segment.local_name or "vein" in segment.local_name
        }
        self.assertTrue(vessels)
        self.assertTrue(
            all(segment.generation_status == "blocked" for segment in vessels.values())
        )
        self.assertTrue(
            all(segment.source_support == "not-established" for segment in vessels.values())
        )

    def test_patient_space_claim_is_rejected_before_registration(self) -> None:
        with self.assertRaises(ValueError):
            DraftSegmentationManifest(
                segmentation_id="bad",
                roi_id="roi",
                source_archive_id="source",
                source_stack_hash="sha256:" + "0" * 64,
                coordinate_space="patient-space",
                registration_status="unverified",
                segments=mvp0_required_draft_segments(),
            )

    def test_mask_for_unestablished_anatomy_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.manifest(
                [
                    DraftSegment(
                        1,
                        "invented-vessel",
                        "unknown vessel",
                        "left",
                        "mask-created",
                        "not-established",
                    )
                ]
            )


if __name__ == "__main__":
    unittest.main()
