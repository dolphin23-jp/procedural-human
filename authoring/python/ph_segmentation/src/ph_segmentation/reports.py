from __future__ import annotations

DRAFT_STATUS = {
    "validationLevel": "V0",
    "reviewStatus": "unreviewed",
    "candidateOnly": True,
    "medicalValidation": False,
}

SOURCE_SPACE_ONLY = {
    "kind": "source-image-stack",
    "patientSpaceClaim": False,
    "registrationStatus": "not-established",
}

BLOCKED_VESSEL_LABELS = (
    "radial_artery",
    "ulnar_artery",
    "superficial_target_vein",
)


def nonvascular_label_record(label: str, coverage: dict[str, int | float]) -> dict[str, object]:
    return {
        "draftLabel": label,
        "semanticMappingStatus": "not-assigned-task-a07",
        "status": DRAFT_STATUS.copy(),
        "maskEncoding": "pgm8-binary-candidate-mask",
        "coverage": coverage,
    }


def vessel_block_record(label: str) -> dict[str, object]:
    return {
        "draftLabel": label,
        "maskGeneration": "blocked",
        "reason": "TASK-A05 permits feasibility analysis only; vessel masks require explicit later review/authorization",
        "status": DRAFT_STATUS.copy(),
    }
