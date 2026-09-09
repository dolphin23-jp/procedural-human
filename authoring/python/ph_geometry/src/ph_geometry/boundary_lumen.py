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
    candidate_representations: Mapping[str, Mapping[str, str]] | None = None,
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
    candidates = candidate_representations or {}
    any_created = False

    for label in expected:
        centerline = by_label.get(label)
        if centerline is None:
            raise BoundaryLumenAuthoringError(
                f"missing centerline authoring disposition for {label}"
            )
        hard_reasons: list[str] = []
        if centerline.get("centerlineStatus") != "generated":
            hard_reasons.append("vessel centerline is not generated")
        if not vessel_mask_available.get(label, False):
            hard_reasons.append("vessel segmentation/lumen mask is unavailable")

        candidate = candidates.get(label)
        required_keys = {"outsideRegion", "wallBoundary", "lumenRegion"}
        if not hard_reasons and candidate is not None:
            if set(candidate) != required_keys or any(
                not candidate[key] for key in required_keys
            ):
                raise BoundaryLumenAuthoringError(
                    f"{label} candidate representation must provide outsideRegion, wallBoundary, and lumenRegion"
                )
            any_created = True
            review_note = (
                "TASK-A06 human manual anatomical correction is not complete; "
                if not manual_correction_complete
                else ""
            )
            structures.append(
                {
                    "draftLabel": label,
                    "anatomicalId": centerline.get("anatomicalId"),
                    "representationStatus": "generated",
                    "outsideRegion": candidate["outsideRegion"],
                    "wallBoundary": candidate["wallBoundary"],
                    "lumenRegion": candidate["lumenRegion"],
                    "reason": (
                        "bounded V0/source-space topology candidate is generated; "
                        + review_note
                        + "wallBoundary denotes the lumen/outside interface and does not "
                        "claim anatomical wall thickness, complete vessel extent, Patient Space, "
                        "anatomical review, or medical validation"
                    ),
                }
            )
            continue

        reasons = list(hard_reasons)
        if not manual_correction_complete:
            reasons.append("TASK-A06 human manual anatomical correction is not complete")
        if not reasons and candidate is None:
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
            "boundaryLumenRepresentationsCreated": any_created,
            "patientSpaceGeometry": False,
            "medicalValidation": False,
            "automaticPromotionAllowed": False,
        },
    }
