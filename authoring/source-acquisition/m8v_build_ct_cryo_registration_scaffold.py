from __future__ import annotations

import argparse
from datetime import date
import json
from math import isfinite
from pathlib import Path
from typing import Any


DIRECT_PREFERENCE_THRESHOLD = 0.35
EXPECTED_LANDMARKS = ("structure.radius.left", "structure.ulna.left")


class RegistrationScaffoldError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RegistrationScaffoldError(f"{path} must contain a JSON object")
    return value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RegistrationScaffoldError(message)


def _matrix3x2(value: Any) -> list[list[float]]:
    _require(isinstance(value, list) and len(value) == 3, "affine matrix must have 3 rows")
    result: list[list[float]] = []
    for row in value:
        _require(isinstance(row, list) and len(row) == 2, "affine matrix rows must have 2 columns")
        converted = [float(row[0]), float(row[1])]
        _require(all(isfinite(item) for item in converted), "affine matrix must be finite")
        result.append(converted)
    return result


def build_scaffold(
    bone_report: dict[str, Any],
    provenance: dict[str, Any],
    *,
    provenance_path: str,
    provenance_git_blob_sha: str,
    recorded_at: str,
) -> dict[str, Any]:
    _require(
        bone_report.get("schema") == "ph-a06-multimodality-bone-candidate-report.v1",
        "unexpected bone report schema",
    )
    status = bone_report.get("status", {})
    coordinate_space = bone_report.get("coordinateSpace", {})
    claims = bone_report.get("claims", {})
    _require(status.get("validationLevel") == "V0", "bone report must remain V0")
    _require(status.get("candidateOnly") is True, "bone report must remain candidate-only")
    _require(coordinate_space.get("kind") == "source-image-stack", "bone report must remain in source-image-stack coordinates")
    _require(coordinate_space.get("patientSpaceClaim") is False, "Patient Space claim is forbidden")
    _require(coordinate_space.get("ctRegistrationEstablished") is False, "input must not claim established CT registration")
    _require(claims.get("patientSpaceGeometry") is False, "input must not claim Patient Space geometry")
    _require(claims.get("medicalValidation") is False, "input must not claim medical validation")
    _require(claims.get("automaticPromotionAllowed") is False, "input must not allow automatic promotion")

    structures = bone_report.get("structures")
    _require(isinstance(structures, list) and len(structures) == 2, "exactly two bone landmarks are required")
    landmark_ids = tuple(item.get("semanticId") for item in structures if isinstance(item, dict))
    _require(landmark_ids == EXPECTED_LANDMARKS, "registration landmarks must be radius and ulna, in that order")

    ct_evidence = bone_report.get("sameCadaverCtEvidence", {})
    affine = ct_evidence.get("affineCorroboration", {})
    direct_mean = float(affine.get("directMeanResidualPixels"))
    direct_median = float(affine.get("directMedianResidualPixels"))
    swapped_mean = float(affine.get("swappedMeanResidualPixels"))
    swapped_median = float(affine.get("swappedMedianResidualPixels"))
    ratio = float(affine.get("directToSwappedMeanRatio"))
    _require(all(isfinite(value) and value >= 0 for value in (direct_mean, direct_median, swapped_mean, swapped_median, ratio)), "residual metrics must be finite and non-negative")
    _require(swapped_mean > 0, "swapped mean residual must be positive")
    _require(affine.get("directAssignmentClearlyPreferred") is True, "direct landmark assignment must be clearly preferred")
    _require(ratio < DIRECT_PREFERENCE_THRESHOLD, "direct-to-swapped residual ratio does not meet the predeclared gate")
    transform = _matrix3x2(affine.get("transformCtPixelsToCryosectionCropPixels"))

    support = bone_report.get("support", {})
    start = int(ct_evidence.get("nominalIndexStart"))
    stop = int(ct_evidence.get("nominalIndexStop"))
    _require(stop >= start, "invalid nominal index interval")
    fit_landmark_count = (stop - start + 1) * len(EXPECTED_LANDMARKS)
    _require(int(support.get("supportedFrameCount")) >= fit_landmark_count, "supported cryosection extent is unexpectedly small")

    _require(provenance.get("schema") == "ph-a06-bone-candidate-provenance.v1", "unexpected provenance schema")
    source = provenance.get("source", {})
    source_ct = source.get("sameCadaverCt", {})
    execution = provenance.get("execution", {})
    ct_storage = source_ct.get("persistentStorage", {})
    output_storage = execution.get("persistentStorage", {})
    _require(ct_storage.get("provider") == "Google Drive", "same-cadaver CT must have recorded persistent storage")
    _require(ct_storage.get("readBackByteSizeVerified") is True and ct_storage.get("readBackSha256Verified") is True, "same-cadaver CT persistent read-back must be verified")
    _require(output_storage.get("provider") == "Google Drive", "A06 output must have recorded persistent storage")
    _require(output_storage.get("readBackByteSizeVerified") is True and output_storage.get("readBackSha256Verified") is True, "A06 output persistent read-back must be verified")

    reported_identity = provenance.get("identityCorroboration", {})
    for key, expected in (
        ("directMeanResidualPixels", direct_mean),
        ("directMedianResidualPixels", direct_median),
        ("swappedMeanResidualPixels", swapped_mean),
        ("swappedMedianResidualPixels", swapped_median),
        ("directToSwappedMeanRatio", ratio),
    ):
        _require(abs(float(reported_identity.get(key)) - expected) < 1e-9, f"provenance mismatch for {key}")
    _require(reported_identity.get("directAssignmentClearlyPreferred") is True, "provenance does not preserve direct-assignment decision")

    return {
        "schema": "ph-m8v-ct-cryo-registration-scaffold.v1",
        "schemaVersion": "1",
        "task": "TASK-V02",
        "recordedAt": recorded_at,
        "status": "complete",
        "sourceEvidence": {
            "boneCandidateReport": {
                "schema": bone_report["schema"],
                "sourceClass": "same-subject-cadaver-derived-plus-radiological",
                "validationLevel": "V0",
            },
            "boneProvenance": {
                "path": provenance_path,
                "gitBlobSha": provenance_git_blob_sha,
            },
            "sameCadaverCt": {
                "archiveSha256": source_ct["archiveSha256"],
                "archiveByteSize": int(source_ct["archiveByteSize"]),
                "persistentProvider": ct_storage["provider"],
                "persistentFileId": ct_storage["fileId"],
                "readBackVerified": True,
            },
            "persistedA06Output": {
                "archiveSha256": execution["outputArchiveSha256"],
                "archiveByteSize": int(execution["outputArchiveByteSize"]),
                "persistentProvider": output_storage["provider"],
                "persistentFileId": output_storage["fileId"],
                "readBackVerified": True,
            },
        },
        "landmarkPolicy": {
            "landmarks": list(EXPECTED_LANDMARKS),
            "vesselLandmarksUsed": False,
            "selfConfirmingVesselEvidenceAllowed": False,
        },
        "support": {
            "nominalIndexStart": start,
            "nominalIndexStop": stop,
            "firstSourceFilename": support["firstSourceFilename"],
            "lastSourceFilename": support["lastSourceFilename"],
            "supportedCryosectionFrameCount": int(support["supportedFrameCount"]),
            "fitLandmarkObservationCount": fit_landmark_count,
            "outsideSupportDisposition": "unknown-not-registered-by-this-scaffold",
        },
        "transform": {
            "model": "least-squares-affine-2d",
            "from": "ct-source-pixels",
            "to": "cryosection-crop-source-pixels",
            "matrix3x2": transform,
            "patientSpaceTransform": False,
        },
        "residualEvidence": {
            "directMeanPixels": direct_mean,
            "directMedianPixels": direct_median,
            "swappedMeanPixels": swapped_mean,
            "swappedMedianPixels": swapped_median,
            "directToSwappedMeanRatio": ratio,
            "predeclaredPreferenceThreshold": DIRECT_PREFERENCE_THRESHOLD,
            "directAssignmentClearlyPreferred": True,
        },
        "decision": {
            "registrationState": "bounded-bone-landmark-scaffold",
            "identityCorrespondence": "direct-radius-ulna-correspondence-supported",
            "usableFor": [
                "landmark-constrained-same-subject-inspection",
                "candidate-vessel-evidence-support",
                "registration-method-development",
            ],
            "notUsableFor": [
                "patient-space",
                "vessel-identity-by-itself",
                "medical-validation",
                "automatic-medical-master-promotion",
                "whole-body-registration-claim",
            ],
            "nextTask": "TASK-V03",
        },
        "claims": {
            "sameSubject": True,
            "boneOnlyRegistrationLandmarks": True,
            "boundedRegistrationScaffoldEstablished": True,
            "ctCryosectionMedicalRegistrationEstablished": False,
            "patientSpaceGeometry": False,
            "radialArteryIdentityEstablished": False,
            "superficialVeinIdentityEstablished": False,
            "medicalValidation": False,
            "automaticPromotionAllowed": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the fail-closed M8V V02 CT/cryo registration scaffold from persisted A06 bone evidence.")
    parser.add_argument("--bone-report", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    parser.add_argument("--provenance-git-blob-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--recorded-at", default=date.today().isoformat())
    args = parser.parse_args()

    result = build_scaffold(
        _read_json(args.bone_report),
        _read_json(args.provenance),
        provenance_path=str(args.provenance.as_posix()),
        provenance_git_blob_sha=args.provenance_git_blob_sha,
        recorded_at=args.recorded_at,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "registrationState": result["decision"]["registrationState"], "directToSwappedMeanRatio": result["residualEvidence"]["directToSwappedMeanRatio"], "patientSpaceGeometry": result["claims"]["patientSpaceGeometry"]}, indent=2))


if __name__ == "__main__":
    main()
