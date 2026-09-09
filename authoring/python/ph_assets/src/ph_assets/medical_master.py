from __future__ import annotations

from typing import Any, Mapping


class MedicalMasterPromotionBlocked(RuntimeError):
    def __init__(self, blockers: tuple[str, ...]) -> None:
        self.blockers = blockers
        super().__init__("Medical Master promotion blocked: " + "; ".join(blockers))


def evaluate_medical_master_readiness(
    *,
    recorded_at: str,
    manual_correction_record: Mapping[str, Any],
    semantic_mapping_record: Mapping[str, Any],
    centerline_report: Mapping[str, Any],
    boundary_lumen_report: Mapping[str, Any],
) -> dict[str, object]:
    blockers: list[str] = []

    manual_status = (
        manual_correction_record.get("manualCorrection", {})
        if isinstance(manual_correction_record.get("manualCorrection"), Mapping)
        else {}
    ).get("status")
    if manual_status != "human-correction-recorded":
        blockers.append("TASK-A06 human manual anatomical correction is incomplete")

    unresolved = semantic_mapping_record.get("unresolved", [])
    if unresolved:
        blockers.append("TASK-A07 contains unresolved anatomical identities")

    centerline_rows = centerline_report.get("structures", [])
    unavailable_centerlines = [
        row.get("anatomicalId") or row.get("draftLabel")
        for row in centerline_rows
        if isinstance(row, Mapping) and row.get("centerlineStatus") != "generated"
    ]
    if unavailable_centerlines:
        blockers.append(
            "TASK-A08 required vessel centerlines are unavailable: "
            + ", ".join(str(item) for item in unavailable_centerlines)
        )
    elif not (
        isinstance(centerline_report.get("claims"), Mapping)
        and centerline_report["claims"].get("centerlinesCreated") is True
    ):
        blockers.append("TASK-A08 required vessel centerlines are unavailable")

    boundary_rows = boundary_lumen_report.get("structures", [])
    unavailable_boundaries = [
        row.get("anatomicalId") or row.get("draftLabel")
        for row in boundary_rows
        if isinstance(row, Mapping)
        and row.get("representationStatus") != "generated"
    ]
    if unavailable_boundaries:
        blockers.append(
            "TASK-A09 boundary/lumen representations are unavailable: "
            + ", ".join(str(item) for item in unavailable_boundaries)
        )
    elif not (
        isinstance(boundary_lumen_report.get("claims"), Mapping)
        and boundary_lumen_report["claims"].get(
            "boundaryLumenRepresentationsCreated"
        )
        is True
    ):
        blockers.append("TASK-A09 boundary/lumen representations are unavailable")

    representation_missing = [
        row.get("anatomicalId")
        for row in semantic_mapping_record.get("mappings", [])
        if isinstance(row, Mapping)
        and row.get("representationAvailable") is not True
    ]
    if representation_missing:
        blockers.append(
            "required semantic identities lack candidate representations: "
            + ", ".join(str(item) for item in representation_missing)
        )

    ready = not blockers
    return {
        "schema": "ph-medical-master-readiness.v1",
        "schemaVersion": "1",
        "task": "TASK-A10",
        "recordedAt": recorded_at,
        "status": "ready" if ready else "blocked",
        "blockers": blockers,
        "claims": {
            "medicalMasterCreated": False,
            "medicalValidation": False,
            "patientSpaceGeometry": False,
            "automaticPromotionAllowed": False,
        },
    }


def require_medical_master_ready(readiness: Mapping[str, Any]) -> None:
    blockers = readiness.get("blockers", [])
    if readiness.get("status") != "ready" or blockers:
        raise MedicalMasterPromotionBlocked(tuple(str(item) for item in blockers))
    raise MedicalMasterPromotionBlocked(
        ("Medical Master creation implementation is not configured",)
    )
