from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "authoring/source-acquisition/m8v_build_ct_cryo_registration_scaffold.py"
SPEC = importlib.util.spec_from_file_location("m8v_registration", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RegistrationScaffoldTests(unittest.TestCase):
    def bone_report(self) -> dict:
        return {
            "schema": "ph-a06-multimodality-bone-candidate-report.v1",
            "status": {
                "validationLevel": "V0",
                "candidateOnly": True,
            },
            "coordinateSpace": {
                "kind": "source-image-stack",
                "patientSpaceClaim": False,
                "ctRegistrationEstablished": False,
            },
            "support": {
                "firstSourceFilename": "avf1567a.png",
                "lastSourceFilename": "avf1685c.png",
                "supportedFrameCount": 357,
            },
            "sameCadaverCtEvidence": {
                "nominalIndexStart": 1567,
                "nominalIndexStop": 1685,
                "affineCorroboration": {
                    "directMeanResidualPixels": 9.0,
                    "directMedianResidualPixels": 6.0,
                    "swappedMeanResidualPixels": 75.0,
                    "swappedMedianResidualPixels": 60.0,
                    "directToSwappedMeanRatio": 0.12,
                    "directAssignmentClearlyPreferred": True,
                    "transformCtPixelsToCryosectionCropPixels": [
                        [2.3, -0.4],
                        [0.45, -2.7],
                        [-950.0, 1150.0],
                    ],
                },
            },
            "structures": [
                {
                    "draftLabel": "radius",
                    "semanticId": "structure.radius.left",
                },
                {
                    "draftLabel": "ulna",
                    "semanticId": "structure.ulna.left",
                },
            ],
            "claims": {
                "patientSpaceGeometry": False,
                "medicalValidation": False,
                "automaticPromotionAllowed": False,
            },
        }

    def provenance(self) -> dict:
        return {
            "schema": "ph-a06-bone-candidate-provenance.v1",
            "source": {
                "sameCadaverCt": {
                    "archiveSha256": "a" * 64,
                    "archiveByteSize": 123,
                    "persistentStorage": {
                        "provider": "Google Drive",
                        "fileId": "ct-file",
                        "readBackByteSizeVerified": True,
                        "readBackSha256Verified": True,
                    },
                }
            },
            "execution": {
                "outputArchiveSha256": "b" * 64,
                "outputArchiveByteSize": 456,
                "persistentStorage": {
                    "provider": "Google Drive",
                    "fileId": "output-file",
                    "readBackByteSizeVerified": True,
                    "readBackSha256Verified": True,
                },
            },
            "identityCorroboration": {
                "directMeanResidualPixels": 9.0,
                "directMedianResidualPixels": 6.0,
                "swappedMeanResidualPixels": 75.0,
                "swappedMedianResidualPixels": 60.0,
                "directToSwappedMeanRatio": 0.12,
                "directAssignmentClearlyPreferred": True,
            },
        }

    def build(self, bone_report: dict | None = None, provenance: dict | None = None) -> dict:
        return MODULE.build_scaffold(
            bone_report or self.bone_report(),
            provenance or self.provenance(),
            provenance_path="authoring/outputs/a06-support-aware-radius-ulna-provenance-20260909.json",
            provenance_git_blob_sha="0" * 40,
            recorded_at="2026-09-10",
        )

    def test_builds_bone_only_fail_closed_scaffold(self) -> None:
        result = self.build()
        self.assertEqual(result["decision"]["registrationState"], "bounded-bone-landmark-scaffold")
        self.assertEqual(result["landmarkPolicy"]["landmarks"], ["structure.radius.left", "structure.ulna.left"])
        self.assertFalse(result["landmarkPolicy"]["vesselLandmarksUsed"])
        self.assertTrue(result["claims"]["boundedRegistrationScaffoldEstablished"])
        self.assertFalse(result["claims"]["ctCryosectionMedicalRegistrationEstablished"])
        self.assertFalse(result["claims"]["patientSpaceGeometry"])
        self.assertFalse(result["claims"]["radialArteryIdentityEstablished"])
        self.assertFalse(result["claims"]["superficialVeinIdentityEstablished"])
        self.assertEqual(result["support"]["fitLandmarkObservationCount"], 238)

    def test_rejects_patient_space_input(self) -> None:
        report = copy.deepcopy(self.bone_report())
        report["coordinateSpace"]["patientSpaceClaim"] = True
        with self.assertRaises(MODULE.RegistrationScaffoldError):
            self.build(bone_report=report)

    def test_rejects_weak_direct_assignment(self) -> None:
        report = copy.deepcopy(self.bone_report())
        report["sameCadaverCtEvidence"]["affineCorroboration"]["directToSwappedMeanRatio"] = 0.5
        provenance = copy.deepcopy(self.provenance())
        provenance["identityCorroboration"]["directToSwappedMeanRatio"] = 0.5
        with self.assertRaises(MODULE.RegistrationScaffoldError):
            self.build(report, provenance)

    def test_rejects_vessel_substitution_as_landmark(self) -> None:
        report = copy.deepcopy(self.bone_report())
        report["structures"][0]["semanticId"] = "structure.radial_artery.left"
        with self.assertRaises(MODULE.RegistrationScaffoldError):
            self.build(bone_report=report)

    def test_committed_v02_record_validates(self) -> None:
        schema_path = ROOT / "schemas/assets/m8v-ct-cryo-registration-scaffold.v1.schema.json"
        record_path = ROOT / "authoring/outputs/m8v-v02-ct-cryo-registration-scaffold-20260910.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        record = json.loads(record_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(record)
        self.assertFalse(record["claims"]["ctCryosectionMedicalRegistrationEstablished"])
        self.assertFalse(record["claims"]["patientSpaceGeometry"])


if __name__ == "__main__":
    unittest.main()
