from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
from typing import Any
from zipfile import BadZipFile, ZipFile

FIRST_NUMERIC_POSITION = 1567
LAST_NUMERIC_POSITION = 1717
EXPECTED_FRAME_COUNT = 451
EXPECTED_CHUNK_COUNT = 10
EXPECTED_CROP_WIDTH = 550
EXPECTED_CROP_HEIGHT = 750
EXPECTED_CROP = {
    "left": 1450,
    "top": 250,
    "rightExclusive": 2000,
    "bottomExclusive": 1000,
}


class HandoffVerificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExpectedChunk:
    index: int
    library_filename: str
    byte_size: int
    sha256: str


def expected_frame_names() -> tuple[str, ...]:
    names: list[str] = []
    for position in range(FIRST_NUMERIC_POSITION, LAST_NUMERIC_POSITION):
        for suffix in ("a", "b", "c"):
            names.append(f"avf{position:04d}{suffix}.png")
    names.append(f"avf{LAST_NUMERIC_POSITION:04d}a.png")
    if len(names) != EXPECTED_FRAME_COUNT:
        raise AssertionError("unexpected Visible Human bounded frame count")
    return tuple(names)


def sha256_path(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalise_digest(value: Any, *, context: str) -> str:
    if not isinstance(value, str):
        raise HandoffVerificationError(f"{context} is missing SHA-256")
    digest = value.lower().removeprefix("sha256:")
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise HandoffVerificationError(f"{context} has invalid SHA-256")
    return digest


def load_expected_chunks(source_archive_record: Path) -> tuple[ExpectedChunk, ...]:
    raw = json.loads(source_archive_record.read_text(encoding="utf-8"))
    handoff = raw.get("persistentHandoff")
    if not isinstance(handoff, dict):
        raise HandoffVerificationError("source archive record has no persistentHandoff")
    coverage = handoff.get("frameCoverage")
    if not isinstance(coverage, dict):
        raise HandoffVerificationError("persistentHandoff has no frameCoverage")
    if coverage.get("expectedFrameCount") != EXPECTED_FRAME_COUNT:
        raise HandoffVerificationError("unexpected persistent handoff frame count")
    if coverage.get("chunkCount") != EXPECTED_CHUNK_COUNT:
        raise HandoffVerificationError("unexpected persistent handoff chunk count")
    rows = handoff.get("chunks")
    if not isinstance(rows, list) or len(rows) != EXPECTED_CHUNK_COUNT:
        raise HandoffVerificationError("persistent handoff must record exactly 10 chunks")

    chunks: list[ExpectedChunk] = []
    seen: set[int] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise HandoffVerificationError("chunk record must be an object")
        index = row.get("index")
        if not isinstance(index, int) or index in seen:
            raise HandoffVerificationError("chunk indices must be unique integers")
        seen.add(index)
        library_filename = row.get("libraryFilename") or row.get("name")
        if not isinstance(library_filename, str) or not library_filename:
            raise HandoffVerificationError(f"chunk {index} has no library filename")
        byte_size = row.get("byteSize")
        if not isinstance(byte_size, int) or byte_size <= 0:
            raise HandoffVerificationError(f"chunk {index} has invalid byte size")
        chunks.append(
            ExpectedChunk(
                index=index,
                library_filename=library_filename,
                byte_size=byte_size,
                sha256=_normalise_digest(row.get("digest"), context=f"chunk {index}"),
            )
        )
    chunks.sort(key=lambda item: item.index)
    if [item.index for item in chunks] != list(range(EXPECTED_CHUNK_COUNT)):
        raise HandoffVerificationError("chunk indices must be exactly 0 through 9")
    return tuple(chunks)


def _safe_members(archive: ZipFile) -> dict[str, str]:
    result: dict[str, str] = {}
    for info in archive.infolist():
        if info.is_dir():
            continue
        path = PurePosixPath(info.filename)
        if path.is_absolute() or ".." in path.parts:
            raise HandoffVerificationError(f"unsafe ZIP member: {info.filename}")
        basename = path.name
        if basename in result:
            raise HandoffVerificationError(f"duplicate ZIP basename: {basename}")
        result[basename] = info.filename
    return result


def _png_dimensions(payload: bytes, *, context: str) -> tuple[int, int]:
    if len(payload) < 24 or payload[:8] != b"\x89PNG\r\n\x1a\n":
        raise HandoffVerificationError(f"{context} is not a PNG")
    if payload[12:16] != b"IHDR":
        raise HandoffVerificationError(f"{context} has no leading PNG IHDR")
    width = int.from_bytes(payload[16:20], "big")
    height = int.from_bytes(payload[20:24], "big")
    return width, height


def _read_chunk_manifest(archive: ZipFile, members: dict[str, str]) -> dict[str, Any]:
    member = members.get("manifest.json")
    if member is None:
        raise HandoffVerificationError("chunk ZIP does not contain manifest.json")
    try:
        raw = json.loads(archive.read(member).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HandoffVerificationError("chunk manifest is not valid UTF-8 JSON") from exc
    if not isinstance(raw, dict):
        raise HandoffVerificationError("chunk manifest root must be an object")
    return raw


def reconstruct_handoff(
    handoff_dir: Path,
    source_archive_record: Path,
    output_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    expected_chunks = load_expected_chunks(source_archive_record)
    expected_names = expected_frame_names()
    expected_name_set = set(expected_names)
    output_frames = output_dir / "frames"
    output_frames.mkdir(parents=True, exist_ok=True)

    combined: dict[str, dict[str, Any]] = {}
    verified_chunks: list[dict[str, Any]] = []

    for expected in expected_chunks:
        zip_path = handoff_dir / expected.library_filename
        if not zip_path.is_file():
            raise HandoffVerificationError(f"missing handoff chunk: {zip_path}")
        actual_size = zip_path.stat().st_size
        if actual_size != expected.byte_size:
            raise HandoffVerificationError(
                f"chunk {expected.index} byte-size mismatch: expected {expected.byte_size}, got {actual_size}"
            )
        actual_digest = sha256_path(zip_path)
        if actual_digest != expected.sha256:
            raise HandoffVerificationError(
                f"chunk {expected.index} SHA-256 mismatch: expected {expected.sha256}, got {actual_digest}"
            )
        try:
            archive = ZipFile(zip_path)
        except BadZipFile as exc:
            raise HandoffVerificationError(f"chunk {expected.index} is not a valid ZIP") from exc

        with archive:
            members = _safe_members(archive)
            manifest = _read_chunk_manifest(archive, members)
            chunk = manifest.get("chunk")
            files = manifest.get("files")
            if not isinstance(chunk, dict) or chunk.get("index") != expected.index:
                raise HandoffVerificationError(f"chunk {expected.index} manifest index mismatch")
            if chunk.get("fullStackFrameCount") != EXPECTED_FRAME_COUNT:
                raise HandoffVerificationError(f"chunk {expected.index} manifest frame-count mismatch")
            if not isinstance(files, list) or chunk.get("frameCount") != len(files):
                raise HandoffVerificationError(f"chunk {expected.index} manifest files mismatch")

            manifest_indices: list[int] = []
            first_index = chunk.get("firstGlobalFrameIndex")
            if not isinstance(first_index, int):
                raise HandoffVerificationError(f"chunk {expected.index} has no firstGlobalFrameIndex")
            for offset, row in enumerate(files):
                if not isinstance(row, dict):
                    raise HandoffVerificationError(f"chunk {expected.index} contains invalid file record")
                expected_global_index = first_index + offset
                global_frame_index = row.get("globalFrameIndex")
                if global_frame_index != expected_global_index:
                    raise HandoffVerificationError(
                        f"chunk {expected.index} frame {offset} global index mismatch: "
                        f"expected {expected_global_index}, got {global_frame_index}"
                    )
                filename = row.get("filename")
                if not isinstance(filename, str) or filename not in expected_name_set:
                    raise HandoffVerificationError(f"chunk {expected.index} has unexpected frame {filename}")
                if expected_global_index >= len(expected_names) or filename != expected_names[expected_global_index]:
                    raise HandoffVerificationError(
                        f"chunk {expected.index} frame ordering mismatch at global index "
                        f"{expected_global_index}: {filename}"
                    )
                if filename in combined:
                    raise HandoffVerificationError(f"duplicate reconstructed frame: {filename}")
                member = members.get(filename)
                if member is None:
                    raise HandoffVerificationError(f"chunk {expected.index} is missing PNG {filename}")

                crop_digest = _normalise_digest(row.get("cropSha256"), context=f"crop {filename}")
                source_digest = _normalise_digest(row.get("sourceSha256"), context=f"source {filename}")
                source_byte_size = row.get("sourceByteSize")
                if not isinstance(source_byte_size, int) or source_byte_size <= 0:
                    raise HandoffVerificationError(f"source byte size missing for {filename}")
                source_url = row.get("sourceUrl")
                if not isinstance(source_url, str) or not source_url.endswith("/" + filename):
                    raise HandoffVerificationError(f"source URL missing or inconsistent for {filename}")
                if row.get("sourceSpaceOnly") is not True:
                    raise HandoffVerificationError(f"source-space-only status missing for {filename}")
                if row.get("cropPixels") != EXPECTED_CROP:
                    raise HandoffVerificationError(f"crop coordinates mismatch for {filename}")
                payload = archive.read(member)
                if sha256(payload).hexdigest() != crop_digest:
                    raise HandoffVerificationError(f"crop SHA-256 mismatch for {filename}")
                dimensions = _png_dimensions(payload, context=filename)
                if dimensions != (EXPECTED_CROP_WIDTH, EXPECTED_CROP_HEIGHT):
                    raise HandoffVerificationError(
                        f"crop dimensions mismatch for {filename}: {dimensions}"
                    )
                crop_byte_size = row.get("cropByteSize")
                if isinstance(crop_byte_size, int) and crop_byte_size != len(payload):
                    raise HandoffVerificationError(f"crop byte-size mismatch for {filename}")

                (output_frames / filename).write_bytes(payload)
                manifest_indices.append(global_frame_index)
                combined[filename] = {
                    "filename": filename,
                    "globalFrameIndex": global_frame_index,
                    "sha256": crop_digest,
                    "cropSha256": crop_digest,
                    "sourceSha256": source_digest,
                    "sourceByteSize": source_byte_size,
                    "sourceUrl": source_url,
                    "cropByteSize": len(payload),
                    "nominalSourcePositionMm": row.get("nominalSourcePositionMm"),
                    "cropPixels": EXPECTED_CROP.copy(),
                    "cropDimensionsPixels": {
                        "width": EXPECTED_CROP_WIDTH,
                        "height": EXPECTED_CROP_HEIGHT,
                    },
                    "sourceSpaceOnly": True,
                    "chunkIndex": expected.index,
                }

            last_index = chunk.get("lastGlobalFrameIndex")
            if manifest_indices and (
                manifest_indices[0] != first_index or manifest_indices[-1] != last_index
            ):
                raise HandoffVerificationError(f"chunk {expected.index} global index range mismatch")
            verified_chunks.append(
                {
                    "index": expected.index,
                    "libraryFilename": expected.library_filename,
                    "byteSize": actual_size,
                    "sha256": actual_digest,
                    "frameCount": len(files),
                    "firstGlobalFrameIndex": first_index,
                    "lastGlobalFrameIndex": last_index,
                }
            )

    actual_names = tuple(sorted(combined))
    if len(actual_names) != EXPECTED_FRAME_COUNT:
        raise HandoffVerificationError(
            f"reconstructed frame count mismatch: expected {EXPECTED_FRAME_COUNT}, got {len(actual_names)}"
        )
    if actual_names != expected_names:
        missing = sorted(expected_name_set - set(actual_names))
        extra = sorted(set(actual_names) - expected_name_set)
        raise HandoffVerificationError(
            f"reconstructed frame ordering mismatch; missing={missing}, extra={extra}"
        )

    combined_rows = [combined[name] for name in expected_names]
    source_manifest = {
        "schema": "ph-a05-source-stack-reconstruction.v1",
        "dataset": "NLM Visible Human Project — Visible Human Female bounded left distal forearm/wrist crop",
        "sliceCount": EXPECTED_FRAME_COUNT,
        "coordinateSpace": {
            "kind": "source-image-stack",
            "patientSpaceClaim": False,
            "registrationStatus": "not-established",
        },
        "files": combined_rows,
        "claims": {
            "medicalMaster": False,
            "runtimeAssetStore": False,
            "ctRegistrationEstablished": False,
        },
    }
    verification = {
        "schema": "ph-a05-handoff-verification.v1",
        "sourceArchiveRecord": str(source_archive_record),
        "chunkCount": len(verified_chunks),
        "frameCount": len(combined_rows),
        "allChunkHashesVerified": True,
        "allCropHashesVerified": True,
        "noMissingFrames": True,
        "noDuplicateFrames": True,
        "filenameOrderingVerified": True,
        "globalFrameIndexOrderingVerified": True,
        "sourceSha256MetadataPresent": True,
        "identicalCropDimensionsVerified": True,
        "cropDimensionsPixels": {
            "width": EXPECTED_CROP_WIDTH,
            "height": EXPECTED_CROP_HEIGHT,
        },
        "coordinateSpace": "source-image-stack-only",
        "patientSpaceClaim": False,
        "medicalValidation": False,
        "chunks": verified_chunks,
    }
    (output_dir / "source-stack-manifest.json").write_text(
        json.dumps(source_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "handoff-verification.json").write_text(
        json.dumps(verification, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return source_manifest, verification


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify and reconstruct the persistent A05 Visible Human handoff."
    )
    parser.add_argument("--handoff-dir", type=Path, required=True)
    parser.add_argument("--source-archive-record", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    reconstruct_handoff(args.handoff_dir, args.source_archive_record, args.output)


if __name__ == "__main__":
    main()
