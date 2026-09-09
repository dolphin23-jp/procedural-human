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
    candidate_centerline_uris: Mapping[str, str] | None = None,
) -> dict[str, object]:
    expected = (
        "radial_artery",
        "ulnar_artery",
        "superficial_target_vein",
    )
    structures: list[dict[str, object]] = []
    centerlines_created = False
    candidate_uris = candidate_centerline_uris or {}

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
        hard_reasons: list[str] = []
        if classification != "continuous-candidate":
            hard_reasons.append(
                f"source feasibility is {classification}, not continuous-candidate"
            )
        if semantic_id is None:
            hard_reasons.append("named anatomical identity is unresolved")

        candidate_uri = candidate_uris.get(label)
        if not hard_reasons and candidate_uri:
            centerlines_created = True
            review_note = (
                "TASK-A06 human manual anatomical correction is not complete; "
                if not manual_correction_complete
                else ""
            )
            structures.append(
                {
                    "draftLabel": label,
                    "anatomicalId": semantic_id,
                    "feasibilityClassification": classification,
                    "centerlineStatus": "generated",
                    "centerlineUri": candidate_uri,
                    "reason": (
                        "bounded V0/source-space centerline candidate is generated; "
                        + review_note
                        + "no Patient Space, complete-vessel-extent, anatomical-review, "
                        "or medical-validation claim is implied"
                    ),
                }
            )
            continue

        reasons = list(hard_reasons)
        if not manual_correction_complete:
            reasons.append("TASK-A06 human manual anatomical correction is not complete")
        if not candidate_uri and not hard_reasons:
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
