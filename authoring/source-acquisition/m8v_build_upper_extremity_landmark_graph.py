from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
from typing import Any


BONE_IDS = ("structure.radius.left", "structure.ulna.left")
REGION_LABELS = (
    "skin",
    "subcutaneous_soft_tissue",
    "major_muscle_tendon_region",
)
UNRESOLVED_NAMED_LANDMARKS = (
    "structure.radial_styloid.left",
    "structure.ulnar_styloid.left",
    "structure.brachioradialis.left",
    "structure.flexor_carpi_radialis.left",
    "structure.pronator_quadratus.left",
)


class LandmarkGraphError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise LandmarkGraphError(f"{path} must contain a JSON object")
    return value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise LandmarkGraphError(message)


def _validate_v02(registration: dict[str, Any]) -> int:
    _require(
        registration.get("schema") == "ph-m8v-ct-cryo-registration-scaffold.v1",
        "unexpected V02 registration schema",
    )
    _require(registration.get("status") == "complete", "V02 must be complete")

    coordinate_claims = registration.get("claims", {})
    _require(
        coordinate_claims.get("boundedRegistrationScaffoldEstablished") is True,
        "V02 bounded registration scaffold must be established",
    )
    for key in (
        "ctCryosectionMedicalRegistrationEstablished",
        "patientSpaceGeometry",
        "radialArteryIdentityEstablished",
        "superficialVeinIdentityEstablished",
        "medicalValidation",
        "automaticPromotionAllowed",
    ):
        _require(coordinate_claims.get(key) is False, f"V02 claim {key} must remain false")

    policy = registration.get("landmarkPolicy", {})
    _require(tuple(policy.get("landmarks", [])) == BONE_IDS, "V02 landmarks must be radius/ulna only")
    _require(policy.get("vesselLandmarksUsed") is False, "vessel landmarks are forbidden")
    _require(
        policy.get("selfConfirmingVesselEvidenceAllowed") is False,
        "self-confirming vessel evidence is forbidden",
    )

    decision = registration.get("decision", {})
    _require(
        decision.get("registrationState") == "bounded-bone-landmark-scaffold",
        "unexpected V02 registration state",
    )
    support = registration.get("support", {})
    frame_count = int(support.get("supportedCryosectionFrameCount", 0))
    _require(frame_count > 0, "V02 must contain bounded cryosection support")
    return frame_count


def _validate_a05(a05: dict[str, Any]) -> tuple[int, dict[str, dict[str, Any]]]:
    _require(a05.get("schema") == "ph-a05-real-output-provenance.v1", "unexpected A05 provenance schema")
    claims = a05.get("claims", {})
    _require(claims.get("validationLevel") == "V0", "A05 nonvascular evidence must remain V0")
    _require(claims.get("reviewStatus") == "unreviewed", "A05 nonvascular evidence must remain unreviewed")
    _require(claims.get("candidateOnly") is True, "A05 nonvascular evidence must remain candidate-only")
    for key in ("patientSpaceGeometry", "ctRegistrationEstablished", "medicalValidation", "medicalMaster", "runtimeAsset", "vesselMasksCreated"):
        _require(claims.get(key) is False, f"A05 claim {key} must remain false")

    persistent = a05.get("persistentOutput", {})
    _require(persistent.get("complete") is True, "A05 persistent output must be complete")
    verification = persistent.get("postUploadVerification", {})
    _require(verification.get("readBackFromPersistentStorage") is True, "A05 persistent output must be read back")
    _require(verification.get("byteSizeMatches") is True, "A05 persistent output byte size must verify")
    _require(verification.get("sha256Matches") is True, "A05 persistent output digest must verify")

    frame_count = int(a05.get("execution", {}).get("sourceFrameCount", 0))
    _require(frame_count > 0, "A05 source frame count must be positive")

    generated = a05.get("nonvascular", {}).get("generated")
    _require(isinstance(generated, list), "A05 nonvascular generated list is required")
    by_label: dict[str, dict[str, Any]] = {}
    for row in generated:
        _require(isinstance(row, dict), "A05 generated entries must be objects")
        label = row.get("draftLabel")
        _require(label in REGION_LABELS, f"unexpected or named nonvascular landmark label: {label}")
        _require(label not in by_label, f"duplicate nonvascular label: {label}")
        _require(int(row.get("sliceCount", 0)) == frame_count, f"{label} sliceCount must cover A05 source extent")
        _require(int(row.get("slicesWithCandidate", 0)) == frame_count, f"{label} must have a candidate on every bounded A05 frame")
        by_label[str(label)] = row
    _require(tuple(by_label.keys()) == REGION_LABELS, "A05 nonvascular labels must be the expected generic regions in canonical order")
    return frame_count, by_label


def build_landmark_graph(
    registration: dict[str, Any],
    a05: dict[str, Any],
    *,
    registration_path: str,
    a05_path: str,
    recorded_at: str,
) -> dict[str, Any]:
    bone_frame_count = _validate_v02(registration)
    region_frame_count, regions = _validate_a05(a05)

    nodes: list[dict[str, Any]] = [
        {
            "id": "structure.radius.left",
            "label": "left radius",
            "kind": "observed-bone-landmark",
            "evidenceStatus": "supported-bounded",
            "sourceClass": "same-subject-cadaver-plus-radiological",
            "validationLevel": "V0",
            "reviewStatus": "unreviewed",
            "support": {"frameCount": bone_frame_count, "extentDisposition": "bounded-observed-support"},
            "vesselIdentificationUse": "same-subject-landmark-constraint",
        },
        {
            "id": "structure.ulna.left",
            "label": "left ulna",
            "kind": "observed-bone-landmark",
            "evidenceStatus": "supported-bounded",
            "sourceClass": "same-subject-cadaver-plus-radiological",
            "validationLevel": "V0",
            "reviewStatus": "unreviewed",
            "support": {"frameCount": bone_frame_count, "extentDisposition": "bounded-observed-support"},
            "vesselIdentificationUse": "same-subject-landmark-constraint",
        },
    ]

    region_specs = (
        ("vhf.left.forearm.region.skin.v0", "skin candidate region", "skin"),
        ("vhf.left.forearm.region.subcutaneous-soft-tissue.v0", "subcutaneous soft-tissue candidate region", "subcutaneous_soft_tissue"),
        ("vhf.left.forearm.region.major-muscle-tendon.v0", "major muscle/tendon candidate region", "major_muscle_tendon_region"),
    )
    for node_id, label, source_label in region_specs:
        row = regions[source_label]
        _require(int(row.get("slicesWithCandidate", 0)) == region_frame_count, f"{source_label} support changed unexpectedly")
        nodes.append(
            {
                "id": node_id,
                "label": label,
                "kind": "algorithm-derived-region-candidate",
                "evidenceStatus": "candidate-only",
                "sourceClass": "same-subject-algorithm-derived",
                "validationLevel": "V0",
                "reviewStatus": "unreviewed",
                "support": {"frameCount": region_frame_count, "extentDisposition": "candidate-present-all-bounded-frames"},
                "vesselIdentificationUse": "candidate-search-compartment-prior",
            }
        )

    unresolved_labels = {
        "structure.radial_styloid.left": "left radial styloid region",
        "structure.ulnar_styloid.left": "left ulnar styloid region",
        "structure.brachioradialis.left": "left brachioradialis",
        "structure.flexor_carpi_radialis.left": "left flexor carpi radialis",
        "structure.pronator_quadratus.left": "left pronator quadratus",
    }
    for node_id in UNRESOLVED_NAMED_LANDMARKS:
        nodes.append(
            {
                "id": node_id,
                "label": unresolved_labels[node_id],
                "kind": "unresolved-named-landmark",
                "evidenceStatus": "unresolved",
                "sourceClass": "none-established",
                "validationLevel": "V0",
                "reviewStatus": "unreviewed",
                "support": {"frameCount": 0, "extentDisposition": "unknown"},
                "vesselIdentificationUse": "not-usable-until-observed",
            }
        )

    return {
        "schema": "ph-m8v-upper-extremity-landmark-graph.v1",
        "schemaVersion": "1",
        "task": "TASK-V03",
        "recordedAt": recorded_at,
        "status": "complete",
        "coordinateSpace": {
            "kind": "source-image-stack-with-bounded-ct-scaffold",
            "patientSpaceClaim": False,
        },
        "sources": [
            {
                "path": registration_path,
                "role": "bone-registration-scaffold",
                "validationLevel": "V0",
            },
            {
                "path": a05_path,
                "role": "nonvascular-candidate-provenance",
                "validationLevel": "V0",
            },
        ],
        "nodes": nodes,
        "relations": [
            {
                "from": "structure.radius.left",
                "type": "paired-with",
                "to": "structure.ulna.left",
                "evidenceStatus": "supported-bounded",
                "use": "registration-orientation-constraint",
            },
            {
                "from": "vhf.left.forearm.region.skin.v0",
                "type": "bounds-candidate-compartment",
                "to": "vhf.left.forearm.region.subcutaneous-soft-tissue.v0",
                "evidenceStatus": "candidate-only",
                "use": "superficiality-search-prior",
            },
            {
                "from": "vhf.left.forearm.region.subcutaneous-soft-tissue.v0",
                "type": "contrasts-with-candidate-region",
                "to": "vhf.left.forearm.region.major-muscle-tendon.v0",
                "evidenceStatus": "candidate-only",
                "use": "deep-soft-tissue-search-prior",
            },
        ],
        "unresolvedRequiredLandmarks": list(UNRESOLVED_NAMED_LANDMARKS),
        "decision": {
            "graphState": "bounded-mixed-evidence-landmark-graph",
            "usableForTaskV04": True,
            "namedMuscleLandmarksEstablished": False,
            "nextTask": "TASK-V04",
        },
        "claims": {
            "patientSpaceGeometry": False,
            "namedMuscleIdentityEstablished": False,
            "radialArteryIdentityEstablished": False,
            "superficialVeinIdentityEstablished": False,
            "medicalValidation": False,
            "automaticPromotionAllowed": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registration", type=Path, required=True)
    parser.add_argument("--a05-provenance", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--recorded-at", default=date.today().isoformat())
    args = parser.parse_args()

    record = build_landmark_graph(
        _read_json(args.registration),
        _read_json(args.a05_provenance),
        registration_path=str(args.registration),
        a05_path=str(args.a05_provenance),
        recorded_at=args.recorded_at,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"nodes": len(record["nodes"]), "unresolved": len(record["unresolvedRequiredLandmarks"]), "nextTask": record["decision"]["nextTask"]}, indent=2))


if __name__ == "__main__":
    main()
