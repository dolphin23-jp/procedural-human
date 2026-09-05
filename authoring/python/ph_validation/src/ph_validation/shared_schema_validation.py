from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[5]
SCHEMA_PATH = ROOT / "schemas/procedures/procedure-definition.v1.schema.json"
FIXTURE_PATH = ROOT / "fixtures/schemas/procedure-definition.v1.valid.json"


def main() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(fixture)
    print("Python validated shared procedure-definition v1 fixture.")


if __name__ == "__main__":
    main()
