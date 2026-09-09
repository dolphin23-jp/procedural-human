from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

ALLOWED_STRUCTURE_STATUSES = {
    "pending-human-edit",
    "edited",
    "reviewed-no-change",
    "blocked-source-evidence",
}


class ManualCorrectionRecordError(ValueError):
    pass


@dataclass(frozen=True)
class SupplementalCandidateOutput:
    labels: tuple[str, ...]
    uri: str
    digest: str
    support_status: str


@dataclass(frozen=True)
class ManualCorrectionStructure:
    draft_label: str
    status: str
    reason: str | None = None
    output_uri: str | None = None
    output_digest: str | None = None


def _normalise_digest(value: str, *, field: str) -> str:
    digest = value.lower().removeprefix("sha256:")
    if not _SHA256_RE.fullmatch(digest):
        raise ManualCorrectionRecordError(f"{field} must be a SHA-256 digest")
    return f"sha256:{digest}"


def build_manual_correction_record(
    *,
    recorded_at: str,
    source_frame_count: int,
    source_filename_sha_aggregate: str,
    crop_filename_sha_aggregate: str,
    candidate_output_digest: str,
    structures: Iterable[ManualCorrectionStructure],
    supplemental_candidate_outputs: Iterable[SupplementalCandidateOutput] = (),
    editor_reference: str | None = None,
    tool: str | None = None,
    completed_at: str | None = None,
) -> dict[str, object]:
    rows = tuple(structures)
    supplemental = tuple(supplemental_candidate_outputs)
    if source_frame_count <= 0:
        raise ManualCorrectionRecordError("source_frame_count must be positive")
    if not rows:
        raise ManualCorrectionRecordError("manual correction record requires structures")

    labels: set[str] = set()
    has_completed_human_action = False
    has_edit = False
    payload_rows: list[dict[str, object]] = []
    for row in rows:
        if not row.draft_label or row.draft_label in labels:
            raise ManualCorrectionRecordError(
                "draft labels must be unique non-empty strings"
            )
        labels.add(row.draft_label)
        if row.status not in ALLOWED_STRUCTURE_STATUSES:
            raise ManualCorrectionRecordError(
                f"unsupported manual correction status: {row.status}"
            )
        if row.status in {"edited", "reviewed-no-change"}:
            has_completed_human_action = True
            if not row.output_uri or not row.output_digest:
                raise ManualCorrectionRecordError(
                    f"completed structure {row.draft_label} requires output_uri and output_digest"
                )
        if row.status == "edited":
            has_edit = True
        if row.status == "blocked-source-evidence" and not row.reason:
            raise ManualCorrectionRecordError(
                f"blocked structure {row.draft_label} requires a reason"
            )
        if row.status in {"pending-human-edit", "blocked-source-evidence"} and (
            row.output_uri is not None or row.output_digest is not None
        ):
            raise ManualCorrectionRecordError(
                f"incomplete structure {row.draft_label} cannot claim corrected output"
            )
        payload_rows.append(
            {
                "draftLabel": row.draft_label,
                "status": row.status,
                "reason": row.reason,
                "outputUri": row.output_uri,
                "outputDigest": (
                    _normalise_digest(
                        row.output_digest,
                        field=f"{row.draft_label}.output_digest",
                    )
                    if row.output_digest is not None
                    else None
                ),
            }
        )

    if has_completed_human_action and not editor_reference:
        raise ManualCorrectionRecordError(
            "completed manual correction/review requires editor_reference"
        )
    if completed_at is not None and not has_completed_human_action:
        raise ManualCorrectionRecordError(
            "completed_at cannot be recorded before human correction/review"
        )

    supplemental_rows: list[dict[str, object]] = []
    for item in supplemental:
        if not item.labels or len(set(item.labels)) != len(item.labels):
            raise ManualCorrectionRecordError(
                "supplemental candidate labels must be non-empty and unique"
            )
        if not item.uri:
            raise ManualCorrectionRecordError("supplemental candidate output requires uri")
        supplemental_rows.append(
            {
                "labels": list(item.labels),
                "uri": item.uri,
                "digest": _normalise_digest(
                    item.digest,
                    field="supplemental_candidate_output.digest",
                ),
                "supportStatus": item.support_status,
            }
        )

    overall_status = (
        "human-correction-recorded"
        if has_completed_human_action
        else "pending-human-edit"
    )
    return {
        "schema": "ph-manual-edit-provenance.v1",
        "schemaVersion": "1",
        "task": "TASK-A06",
        "recordedAt": recorded_at,
        "coordinateSpace": {
            "kind": "source-image-stack",
            "patientSpaceClaim": False,
            "ctRegistrationEstablished": False,
        },
        "source": {
            "sourceFrameCount": source_frame_count,
            "sourceFilenameShaAggregate": _normalise_digest(
                source_filename_sha_aggregate,
                field="source_filename_sha_aggregate",
            ),
            "cropFilenameShaAggregate": _normalise_digest(
                crop_filename_sha_aggregate,
                field="crop_filename_sha_aggregate",
            ),
            "candidateOutputDigest": _normalise_digest(
                candidate_output_digest,
                field="candidate_output_digest",
            ),
            "supplementalCandidateOutputs": supplemental_rows,
        },
        "manualCorrection": {
            "status": overall_status,
            "editorReference": editor_reference,
            "tool": tool,
            "completedAt": completed_at,
        },
        "structures": payload_rows,
        "claims": {
            "humanEdited": has_edit,
            "anatomicallyReviewed": False,
            "medicalValidation": False,
            "patientSpaceGeometry": False,
            "automaticPromotionAllowed": False,
        },
    }
