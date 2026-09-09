from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[5]

VALIDATION_TARGETS = (
    (
        "procedure-definition",
        "schemas/procedures/procedure-definition.v1.schema.json",
        "fixtures/schemas/procedure-definition.v1.valid.json",
    ),
    (
        "source-archive-record",
        "schemas/assets/source-archive-record.v1.schema.json",
        "authoring/source-archives/visible-human-female.json",
    ),
    (
        "authoring-roi",
        "schemas/assets/authoring-roi.v1.schema.json",
        "authoring/rois/mvp0-left-distal-forearm-wrist.json",
    ),
    (
        "manual-edit-provenance",
        "schemas/assets/manual-edit-provenance.v1.schema.json",
        "authoring/manual-inputs/a06-manual-correction-status-20260909.json",
    ),
    (
        "a06-bone-candidate-provenance",
        "schemas/assets/a06-bone-candidate-provenance.v1.schema.json",
        "authoring/outputs/a06-support-aware-radius-ulna-provenance-20260909.json",
    ),
    (
        "semantic-structure-mapping",
        "schemas/assets/semantic-structure-mapping.v1.schema.json",
        "authoring/semantic/a07-semantic-structure-mapping-20260909.json",
    ),
    (
        "vessel-centerline-authoring-report",
        "schemas/assets/vessel-centerline-authoring-report.v1.schema.json",
        "authoring/outputs/a08-vessel-centerline-authoring-report-20260909.json",
    ),
    (
        "boundary-lumen-authoring-report",
        "schemas/assets/boundary-lumen-authoring-report.v1.schema.json",
        "authoring/outputs/a09-boundary-lumen-authoring-report-20260909.json",
    ),
    (
        "medical-master-readiness",
        "schemas/assets/medical-master-readiness.v1.schema.json",
        "authoring/outputs/a10-medical-master-readiness-20260909.json",
    ),
)


def main() -> None:
    for name, schema_relative, data_relative in VALIDATION_TARGETS:
        schema = json.loads((ROOT / schema_relative).read_text(encoding="utf-8"))
        data = json.loads((ROOT / data_relative).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(data)
        print(f"Python validated {name}: {data_relative}")


if __name__ == "__main__":
    main()
