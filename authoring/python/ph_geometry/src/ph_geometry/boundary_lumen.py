from __future__ import annotations

from typing import Mapping, Any


class BoundaryLumenAuthoringError(ValueError):
    pass


def build_boundary_lumen_authoring_report(
    *,
    recorded_at: str,
    centerline_report: Mapping[str, Any],
    vessel_mask_available: Mapping[str, bool],
    manual_correction_complete: bool,
) -> dict[str, object]:
    expected = (
        "radial_artery",
        "ulnar_artery",
        "superficial_target_vein",
    )
    by_label = {
        row.get("draftLabel"): row
        for row in centerline_report.get("structures", [])
        if isinstance(row, Mapping)
    }
    structures: list[dict[str, object]] = []

    for label in expected:
        centerline = by_label.get(label)
        if centerline is None:
            raise BoundaryLumenAuthoringError(
                f"missing centerline authoring disposition for {label}"
            )
        reasons: list[str] = []
        if centerline.get("centerlineStatus") != "generated":
            reasons.append("vessel centerline is not generated")
        if not vessel_mask_available.get(label, False):
            reasons.append("vessel segmentation/lumen mask is unavailable")
        if not manual_correction_complete:
            reasons.append("TASK-A06 human manual anatomical correction is not complete")

        if not reasons:
            raise BoundaryLumenAuthoringError(
                f"{label} is eligible for boundary/lumen authoring, but no representation implementation is configured"
            )

        structures.append(
            {
                "draftLabel": label,
                "anatomicalId": centerline.get("anatomicalId"),
                "representationStatus": "blocked",
                "outsideRegion": None,
                "wallBoundary": None,
                "lumenRegion": None,
                "reason": "; ".join(reasons),
            }
        )

    return {
        "schema": "ph-boundary-lumen-authoring-report.v1",
        "schemaVersion": "1",
        "task": "TASK-A09",
        "recordedAt": recorded_at,
        "coordinateSpace": {
            "kind": "source-image-stack",
            "patientSpaceClaim": False,
            "ctRegistrationEstablished": False,
        },
        "structures": structures,
        "claims": {
            "boundaryLumenRepresentationsCreated": False,
            "patientSpaceGeometry": False,
            "medicalValidation": False,
            "automaticPromotionAllowed": False,
        },
    }
