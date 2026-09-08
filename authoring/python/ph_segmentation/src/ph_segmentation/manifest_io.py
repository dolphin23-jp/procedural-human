from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ManifestError(ValueError):
    pass


@dataclass(frozen=True)
class SourceSliceRecord:
    filename: str
    sha256: str


@dataclass(frozen=True)
class SourceStackManifest:
    dataset: str
    slices: tuple[SourceSliceRecord, ...]
    source_manifest_path: str | None = None

    @property
    def slice_count(self) -> int:
        return len(self.slices)

    @property
    def digest(self) -> str:
        payload = {
            "dataset": self.dataset,
            "slices": [
                {"filename": item.filename, "sha256": item.sha256}
                for item in self.slices
            ],
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return sha256(encoded).hexdigest()


def _extract_slice_rows(raw: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("slices", "files", "source_files", "sourceFiles"):
        value = raw.get(key)
        if isinstance(value, list):
            return value
    raise ManifestError("source manifest must contain a slices/files list")


def load_source_stack_manifest(path: str | Path) -> SourceStackManifest:
    manifest_path = Path(path)
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ManifestError("source manifest root must be an object")

    dataset = raw.get("dataset") or raw.get("sourceDataset") or raw.get("datasetId")
    if not isinstance(dataset, str) or not dataset.strip():
        raise ManifestError("source manifest must identify its dataset")

    rows = _extract_slice_rows(raw)
    records: list[SourceSliceRecord] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ManifestError("every source slice record must be an object")
        filename = row.get("filename") or row.get("name") or row.get("path")
        digest = row.get("sha256") or row.get("sha-256") or row.get("contentHash")
        if not isinstance(filename, str) or not filename:
            raise ManifestError("every source slice requires a filename")
        if Path(filename).is_absolute() or ".." in Path(filename).parts:
            raise ManifestError(f"unsafe source slice path: {filename}")
        if not isinstance(digest, str):
            raise ManifestError(f"missing SHA-256 for source slice {filename}")
        digest = digest.lower().removeprefix("sha256:")
        if not _SHA256_RE.fullmatch(digest):
            raise ManifestError(f"invalid SHA-256 for source slice {filename}")
        if filename in seen:
            raise ManifestError(f"duplicate source slice filename: {filename}")
        seen.add(filename)
        records.append(SourceSliceRecord(filename=filename, sha256=digest))

    declared_count = raw.get("slice_count") or raw.get("sliceCount")
    if declared_count is not None and declared_count != len(records):
        raise ManifestError(
            f"declared slice count {declared_count} does not match {len(records)} records"
        )
    if not records:
        raise ManifestError("source stack may not be empty")

    return SourceStackManifest(
        dataset=dataset,
        slices=tuple(records),
        source_manifest_path=str(manifest_path),
    )


def verify_source_slice(path: str | Path, expected_sha256: str) -> None:
    actual = sha256(Path(path).read_bytes()).hexdigest()
    if actual != expected_sha256:
        raise ManifestError(
            f"source hash mismatch for {Path(path).name}: expected {expected_sha256}, got {actual}"
        )


def write_json_atomic(path: str | Path, payload: dict[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)
