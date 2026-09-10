from __future__ import annotations

import json
from pathlib import Path


path = Path("schemas/assets/m8v-candidate-vessel-track-graph.v1.schema.json")
schema = json.loads(path.read_text())
link = schema["$defs"]["link"]
explicit_gap_then = link["allOf"][1]["then"]["properties"]["missingFrameCount"]
explicit_gap_then["type"] = "integer"
explicit_gap_then["minimum"] = 1
path.write_text(json.dumps(schema, indent=2) + "\n")
print("TASK-V04 Ajv strictTypes patch applied")
