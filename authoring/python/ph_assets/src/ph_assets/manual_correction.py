from __future__ import annotations

import argparse
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
from typing import Mapping

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError


ROOT = Path(__file__).resolve().parents[5]
MANUAL_EDIT_SCHEMA_PATH = (
    ROOT / "schemas/assets/manual-edit-provenance.v1.schema.json"
)

EXPECTED_DRAFT_LABELS = frozenset(
    {
        "skin",
        "subcutaneous_soft_tissue",
        "major_muscle_tendon_region",
        "radius",
        "ulna",
        "radial_artery",
        "ulnar_artery",
        "superficial_target_vein",
    }
)

REVIEWED_STATUSES = frozenset({"edited", "reviewed-no-change"})
BLOCKED_STATUS = "blocked-source-evidence"
PENDING_STATUS = "pending-human-edit"


class ManualCorrectionValidationError(RuntimeError):
    pass


def _require_nonempty_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ManualCorrectionValidationError(
            f"{field} must be a non-empty string"
        )
    return value


def _parse_iso_datetime(value: object, field: str) -> datetime:
    text = _require_nonempty_string(value, field)
    if "T" not in text:
        raise ManualCorrectionValidationError(
            f"{field} must include an ISO-8601 time"
        )
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ManualCorrectionValidationError(
            f"{field} must be an ISO-8601 datetime"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ManualCorrectionValidationError(
            f"{field} must include an explicit timezone"
        )
    return parsed


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _structure_rows(
    record: Mapping[str, object],
) -> dict[str, Mapping[str, object]]:
    raw_structures = record.get("structures")
    if not isinstance(raw_structures, list):
        raise ManualCorrectionValidationError(
            "structures must be an array"
        )

    rows: dict[str, Mapping[str, object]] = {}
    for index, raw_row in enumerate(raw_structures):
        if not isinstance(raw_row, dict):
            raise ManualCorrectionValidationError(
                f"structures[{index}] must be an object"
            )
        label = _require_nonempty_string(
            raw_row.get("draftLabel"),
            f"structures[{index}].draftLabel",
        )
        if label in rows:
            raise ManualCorrectionValidationError(
                f"duplicate draftLabel: {label}"
            )
        rows[label] = raw_row

    missing = EXPECTED_DRAFT_LABELS - set(rows)
    extra = set(rows) - EXPECTED_DRAFT_LABELS
    if missing or extra:
        parts: list[str] = []
        if missing:
            parts.append(
                "missing=" + ",".join(sorted(missing))
            )
        if extra:
            parts.append(
                "unexpected=" + ",".join(sorted(extra))
            )
        raise ManualCorrectionValidationError(
            "TASK-A06 structure set mismatch: " + "; ".join(parts)
        )
    return rows


def _validate_schema(record: Mapping[str, object]) -> None:
    try:
        schema = json.loads(
            MANUAL_EDIT_SCHEMA_PATH.read_text(encoding="utf-8")
        )
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(record)
    except OSError as exc:
        raise ManualCorrectionValidationError(
            f"cannot read TASK-A06 schema: {MANUAL_EDIT_SCHEMA_PATH}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise ManualCorrectionValidationError(
            "TASK-A06 schema is not valid JSON"
        ) from exc
    except SchemaError as exc:
        raise ManualCorrectionValidationError(
            f"TASK-A06 schema is invalid: {exc.message}"
        ) from exc
    except ValidationError as exc:
        location = ".".join(str(part) for part in exc.absolute_path)
        where = location or "<root>"
        raise ManualCorrectionValidationError(
            "manual-correction record violates "
            f"manual-edit-provenance.v1 at {where}: {exc.message}"
        ) from exc


def _validate_fixed_claims(record: Mapping[str, object]) -> None:
    coordinate_space = record.get("coordinateSpace")
    if not isinstance(coordinate_space, dict):
        raise ManualCorrectionValidationError(
            "coordinateSpace must be an object"
        )
    if coordinate_space.get("kind") != "source-image-stack":
        raise ManualCorrectionValidationError(
            "TASK-A06 must remain in source-image-stack coordinates"
        )
    if coordinate_space.get("patientSpaceClaim") is not False:
        raise ManualCorrectionValidationError(
            "TASK-A06 must not claim Patient Space geometry"
        )
    if coordinate_space.get("ctRegistrationEstablished") is not False:
        raise ManualCorrectionValidationError(
            "TASK-A06 must not claim CT registration"
        )

    claims = record.get("claims")
    if not isinstance(claims, dict):
        raise ManualCorrectionValidationError("claims must be an object")
    for field in (
        "anatomicallyReviewed",
        "medicalValidation",
        "patientSpaceGeometry",
        "automaticPromotionAllowed",
    ):
        if claims.get(field) is not False:
            raise ManualCorrectionValidationError(
                f"claims.{field} must remain false at TASK-A06"
            )


def validate_manual_correction_record(
    record: Mapping[str, object],
    *,
    output_files: Mapping[str, Path],
) -> None:
    """Validate a completed TASK-A06 record against materialized outputs.

    This is an authoring/provenance gate only. Passing it does not establish
    anatomical review, medical validation, Patient Space, or CT registration.
    """

    _validate_schema(record)

    if record.get("schema") != "ph-manual-edit-provenance.v1":
        raise ManualCorrectionValidationError(
            "unexpected manual-correction schema"
        )
    if record.get("schemaVersion") != "1":
        raise ManualCorrectionValidationError(
            "unexpected manual-correction schemaVersion"
        )
    if record.get("task") != "TASK-A06":
        raise ManualCorrectionValidationError(
            "manual-correction record is not TASK-A06"
        )

    _validate_fixed_claims(record)

    source = record.get("source")
    if not isinstance(source, dict):
        raise ManualCorrectionValidationError("source must be an object")
    if source.get("sourceFrameCount") != 451:
        raise ManualCorrectionValidationError(
            "TASK-A06 sourceFrameCount must remain 451"
        )

    manual = record.get("manualCorrection")
    if not isinstance(manual, dict):
        raise ManualCorrectionValidationError(
            "manualCorrection must be an object"
        )
    if manual.get("status") != "human-correction-recorded":
        raise ManualCorrectionValidationError(
            "manualCorrection.status must be human-correction-recorded"
        )
    _require_nonempty_string(
        manual.get("editorReference"),
        "manualCorrection.editorReference",
    )
    _require_nonempty_string(
        manual.get("tool"),
        "manualCorrection.tool",
    )
    _parse_iso_datetime(
        manual.get("completedAt"),
        "manualCorrection.completedAt",
    )

    rows = _structure_rows(record)

    reviewed_labels: set[str] = set()
    edited_labels: set[str] = set()
    for label, row in rows.items():
        status = row.get("status")
        if status == PENDING_STATUS:
            raise ManualCorrectionValidationError(
                f"{label} remains pending-human-edit"
            )
        if status in REVIEWED_STATUSES:
            reviewed_labels.add(label)
            if status == "edited":
                edited_labels.add(label)
            _require_nonempty_string(
                row.get("outputUri"),
                f"{label}.outputUri",
            )
            expected_digest = _require_nonempty_string(
                row.get("outputDigest"),
                f"{label}.outputDigest",
            )
            if not expected_digest.startswith("sha256:"):
                raise ManualCorrectionValidationError(
                    f"{label}.outputDigest must use sha256:<hex>"
                )
            expected_hex = expected_digest.removeprefix("sha256:")
            if len(expected_hex) != 64 or any(
                char not in "0123456789abcdef" for char in expected_hex
            ):
                raise ManualCorrectionValidationError(
                    f"{label}.outputDigest has invalid SHA-256 hex"
                )

            path = output_files.get(label)
            if path is None:
                raise ManualCorrectionValidationError(
                    f"materialized output file is required for {label}"
                )
            path = Path(path)
            if not path.is_file():
                raise ManualCorrectionValidationError(
                    f"materialized output for {label} is not a file: {path}"
                )
            actual_hex = _sha256_file(path)
            if actual_hex != expected_hex:
                raise ManualCorrectionValidationError(
                    f"SHA-256 mismatch for {label}: "
                    f"expected {expected_hex}, got {actual_hex}"
                )
            continue

        if status == BLOCKED_STATUS:
            reason = row.get("reason")
            _require_nonempty_string(
                reason,
                f"{label}.reason",
            )
            if row.get("outputUri") is not None:
                raise ManualCorrectionValidationError(
                    f"blocked structure {label} must not have outputUri"
                )
            if row.get("outputDigest") is not None:
                raise ManualCorrectionValidationError(
                    f"blocked structure {label} must not have outputDigest"
                )
            if label in output_files:
                raise ManualCorrectionValidationError(
                    f"blocked structure {label} must not have materialized output"
                )
            continue

        raise ManualCorrectionValidationError(
            f"unsupported completion status for {label}: {status!r}"
        )

    supplied_labels = set(output_files)
    if supplied_labels != reviewed_labels:
        missing = reviewed_labels - supplied_labels
        extra = supplied_labels - reviewed_labels
        parts: list[str] = []
        if missing:
            parts.append(
                "missing=" + ",".join(sorted(missing))
            )
        if extra:
            parts.append(
                "unexpected=" + ",".join(sorted(extra))
            )
        raise ManualCorrectionValidationError(
            "materialized output mapping mismatch: " + "; ".join(parts)
        )

    claims = record["claims"]
    assert isinstance(claims, dict)
    expected_human_edited = bool(edited_labels)
    if claims.get("humanEdited") is not expected_human_edited:
        raise ManualCorrectionValidationError(
            "claims.humanEdited must equal whether any structure "
            "has status=edited"
        )


def _parse_output_mapping(values: list[str]) -> dict[str, Path]:
    output: dict[str, Path] = {}
    for value in values:
        label, separator, raw_path = value.partition("=")
        if not separator or not label or not raw_path:
            raise ManualCorrectionValidationError(
                "--output must use draftLabel=/path/to/materialized-file"
            )
        if label in output:
            raise ManualCorrectionValidationError(
                f"duplicate --output mapping for {label}"
            )
        output[label] = Path(raw_path)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a completed TASK-A06 manual-correction provenance "
            "record against materialized structure outputs."
        )
    )
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument(
        "--output",
        action="append",
        default=[],
        metavar="DRAFT_LABEL=FILE",
        help=(
            "Materialized file corresponding to one edited or "
            "reviewed-no-change structure. Repeat for each reviewed structure."
        ),
    )
    args = parser.parse_args()

    record = json.loads(args.record.read_text(encoding="utf-8"))
    if not isinstance(record, dict):
        raise ManualCorrectionValidationError(
            "manual-correction JSON root must be an object"
        )
    output_files = _parse_output_mapping(args.output)
    validate_manual_correction_record(
        record,
        output_files=output_files,
    )
    print(
        json.dumps(
            {
                "task": "TASK-A06",
                "status": "human-correction-recorded",
                "materializedOutputCount": len(output_files),
                "medicalValidation": False,
                "patientSpaceGeometry": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
