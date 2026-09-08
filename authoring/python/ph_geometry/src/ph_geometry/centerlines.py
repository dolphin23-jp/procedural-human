from __future__ import annotations

from typing import Mapping, Any


class CenterlineAuthoringError(ValueError):
    pass


def build_vessel_centerline_authoring_report(
    *,
    recorded_at: str,
    vascular_feasibility: Mapping[str, Mapping[str, Any]],
    manual_correction_complete: bool,
    semantic_ids: Mapping[str, str | None],
) -> dict[str, object]:
    expected = (
        "radial_artery",
        "ulnar_artery",
        "superficial_target_vein",
    )
    structures: list[dict[str, object]] = []
    centerlines_created = False

    for label in expected:
        if label not in vascular_feasibility:
            raise CenterlineAuthoringError(
                f"missing vascular feasibility for {label}"
            )
        classification = vascular_feasibility[label].get("classification")
        if classification not in {
            "continuous-candidate",
            "intermittent-candidate",
            "not-established",
        }:
            raise CenterlineAuthoringError(
                f"unsupported vascular feasibility classification for {label}: {classification}"
            )

        semantic_id = semantic_ids.get(label)
        reasons: list[str] = []
        if classification != "continuous-candidate":
            reasons.append(
                f"source feasibility is {classification}, not continuous-candidate"
            )
        if not manual_correction_complete:
            reasons.append("TASK-A06 human manual anatomical correction is not complete")
        if semantic_id is None:
            reasons.append("named anatomical identity is unresolved")

        blocked = bool(reasons)
        if not blocked:
            # The actual extraction implementation is intentionally not guessed here.
            # A future established/manual-corrected representation may reach this branch.
            raise CenterlineAuthoringError(
                f"{label} is eligible for centerline extraction, but no extraction implementation is configured"
            )

        structures.append(
            {
                "draftLabel": label,
                "anatomicalId": semantic_id,
                "feasibilityClassification": classification,
                "centerlineStatus": "blocked",
                "centerlineUri": None,
                "reason": "; ".join(reasons),
            }
        )

    return {
        "schema": "ph-vessel-centerline-authoring-report.v1",
        "schemaVersion": "1",
        "task": "TASK-A08",
        "recordedAt": recorded_at,
        "coordinateSpace": {
            "kind": "source-image-stack",
            "patientSpaceClaim": False,
            "ctRegistrationEstablished": False,
        },
        "structures": structures,
        "claims": {
            "centerlinesCreated": centerlines_created,
            "patientSpaceGeometry": False,
            "medicalValidation": False,
            "automaticPromotionAllowed": False,
        },
    }
