from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ph_assets import (  # noqa: E402
    ManualCorrectionValidationError,
    validate_manual_correction_record,
)


EXPECTED_LABELS = (
    "skin",
    "subcutaneous_soft_tissue",
    "major_muscle_tendon_region",
    "radius",
    "ulna",
    "radial_artery",
    "ulnar_artery",
    "superficial_target_vein",
)


def _digest(payload: bytes) -> str:
    return "sha256:" + sha256(payload).hexdigest()


def _record(
    skin_payload: bytes,
    subcutaneous_payload: bytes,
) -> dict[str, object]:
    structures: list[dict[str, object]] = []
    for label in EXPECTED_LABELS:
        if label == "skin":
            structures.append(
                {
                    "draftLabel": label,
                    "status": "edited",
                    "reason": "human correction recorded",
                    "outputUri": "drive://example/skin.zip",
                    "outputDigest": _digest(skin_payload),
                }
            )
        elif label == "subcutaneous_soft_tissue":
            structures.append(
                {
                    "draftLabel": label,
                    "status": "reviewed-no-change",
                    "reason": "reviewed against source photographs",
                    "outputUri": "drive://example/subcutaneous.zip",
                    "outputDigest": _digest(subcutaneous_payload),
                }
            )
        else:
            structures.append(
                {
                    "draftLabel": label,
                    "status": "blocked-source-evidence",
                    "reason": "source evidence remains insufficient",
                    "outputUri": None,
                    "outputDigest": None,
                }
            )

    return {
        "schema": "ph-manual-edit-provenance.v1",
        "schemaVersion": "1",
        "task": "TASK-A06",
        "recordedAt": "2026-09-10",
        "coordinateSpace": {
            "kind": "source-image-stack",
            "patientSpaceClaim": False,
            "ctRegistrationEstablished": False,
        },
        "source": {
            "sourceFrameCount": 451,
            "sourceFilenameShaAggregate": "sha256:" + "1" * 64,
            "cropFilenameShaAggregate": "sha256:" + "2" * 64,
            "candidateOutputDigest": "sha256:" + "3" * 64,
            "supplementalCandidateOutputs": [],
        },
        "manualCorrection": {
            "status": "human-correction-recorded",
            "editorReference": "editor:test",
            "tool": "3D Slicer test fixture",
            "completedAt": "2026-09-10T00:30:00+09:00",
        },
        "structures": structures,
        "claims": {
            "humanEdited": True,
            "anatomicallyReviewed": False,
            "medicalValidation": False,
            "patientSpaceGeometry": False,
            "automaticPromotionAllowed": False,
        },
    }


class TaskA06ManualCorrectionTests(unittest.TestCase):
    def test_completed_record_requires_real_matching_outputs(self) -> None:
        skin_payload = b"skin-corrected-archive"
        subcutaneous_payload = b"subcutaneous-reviewed-archive"

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skin = root / "skin.zip"
            subcutaneous = root / "subcutaneous.zip"
            skin.write_bytes(skin_payload)
            subcutaneous.write_bytes(subcutaneous_payload)

            validate_manual_correction_record(
                _record(skin_payload, subcutaneous_payload),
                output_files={
                    "skin": skin,
                    "subcutaneous_soft_tissue": subcutaneous,
                },
            )

    def test_pending_structure_keeps_task_open(self) -> None:
        skin_payload = b"skin"
        subcutaneous_payload = b"subcutaneous"
        record = _record(skin_payload, subcutaneous_payload)
        structures = record["structures"]
        assert isinstance(structures, list)
        structures[2]["status"] = "pending-human-edit"

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skin = root / "skin.zip"
            subcutaneous = root / "subcutaneous.zip"
            skin.write_bytes(skin_payload)
            subcutaneous.write_bytes(subcutaneous_payload)

            with self.assertRaisesRegex(
                ManualCorrectionValidationError,
                "remains pending-human-edit",
            ):
                validate_manual_correction_record(
                    record,
                    output_files={
                        "skin": skin,
                        "subcutaneous_soft_tissue": subcutaneous,
                    },
                )

    def test_digest_mismatch_fails_closed(self) -> None:
        skin_payload = b"skin"
        subcutaneous_payload = b"subcutaneous"

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skin = root / "skin.zip"
            subcutaneous = root / "subcutaneous.zip"
            skin.write_bytes(b"tampered")
            subcutaneous.write_bytes(subcutaneous_payload)

            with self.assertRaisesRegex(
                ManualCorrectionValidationError,
                "SHA-256 mismatch for skin",
            ):
                validate_manual_correction_record(
                    _record(skin_payload, subcutaneous_payload),
                    output_files={
                        "skin": skin,
                        "subcutaneous_soft_tissue": subcutaneous,
                    },
                )

    def test_blocked_structure_cannot_carry_output(self) -> None:
        skin_payload = b"skin"
        subcutaneous_payload = b"subcutaneous"
        record = _record(skin_payload, subcutaneous_payload)
        structures = record["structures"]
        assert isinstance(structures, list)
        radial = next(
            row
            for row in structures
            if row["draftLabel"] == "radial_artery"
        )
        radial["outputUri"] = "drive://example/radial.zip"

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skin = root / "skin.zip"
            subcutaneous = root / "subcutaneous.zip"
            skin.write_bytes(skin_payload)
            subcutaneous.write_bytes(subcutaneous_payload)

            with self.assertRaisesRegex(
                ManualCorrectionValidationError,
                "blocked structure radial_artery must not have outputUri",
            ):
                validate_manual_correction_record(
                    record,
                    output_files={
                        "skin": skin,
                        "subcutaneous_soft_tissue": subcutaneous,
                    },
                )

    def test_structure_set_is_exact_for_mvp0_a06(self) -> None:
        record = _record(b"skin", b"subcutaneous")
        structures = record["structures"]
        assert isinstance(structures, list)
        structures.pop()

        with self.assertRaisesRegex(
            ManualCorrectionValidationError,
            "TASK-A06 structure set mismatch",
        ):
            validate_manual_correction_record(
                record,
                output_files={},
            )

    def test_human_edited_claim_must_match_edit_statuses(self) -> None:
        skin_payload = b"skin"
        subcutaneous_payload = b"subcutaneous"
        record = _record(skin_payload, subcutaneous_payload)
        claims = record["claims"]
        assert isinstance(claims, dict)
        claims["humanEdited"] = False

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skin = root / "skin.zip"
            subcutaneous = root / "subcutaneous.zip"
            skin.write_bytes(skin_payload)
            subcutaneous.write_bytes(subcutaneous_payload)

            with self.assertRaisesRegex(
                ManualCorrectionValidationError,
                "claims.humanEdited",
            ):
                validate_manual_correction_record(
                    record,
                    output_files={
                        "skin": skin,
                        "subcutaneous_soft_tissue": subcutaneous,
                    },
                )

    def test_schema_validation_runs_before_completion_invariants(self) -> None:
        skin_payload = b"skin"
        subcutaneous_payload = b"subcutaneous"
        record = _record(skin_payload, subcutaneous_payload)
        source = record["source"]
        assert isinstance(source, dict)
        del source["sourceFilenameShaAggregate"]

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skin = root / "skin.zip"
            subcutaneous = root / "subcutaneous.zip"
            skin.write_bytes(skin_payload)
            subcutaneous.write_bytes(subcutaneous_payload)

            with self.assertRaisesRegex(
                ManualCorrectionValidationError,
                "violates manual-edit-provenance.v1",
            ):
                validate_manual_correction_record(
                    record,
                    output_files={
                        "skin": skin,
                        "subcutaneous_soft_tissue": subcutaneous,
                    },
                )

    def test_completion_time_requires_timezone(self) -> None:
        skin_payload = b"skin"
        subcutaneous_payload = b"subcutaneous"
        record = _record(skin_payload, subcutaneous_payload)
        manual = record["manualCorrection"]
        assert isinstance(manual, dict)
        manual["completedAt"] = "2026-09-10T00:30:00"

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skin = root / "skin.zip"
            subcutaneous = root / "subcutaneous.zip"
            skin.write_bytes(skin_payload)
            subcutaneous.write_bytes(subcutaneous_payload)

            with self.assertRaisesRegex(
                ManualCorrectionValidationError,
                "must include an explicit timezone",
            ):
                validate_manual_correction_record(
                    record,
                    output_files={
                        "skin": skin,
                        "subcutaneous_soft_tissue": subcutaneous,
                    },
                )


if __name__ == "__main__":
    unittest.main()
