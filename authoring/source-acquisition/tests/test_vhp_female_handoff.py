from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
import unittest
from zipfile import ZIP_STORED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vhp_female_handoff import (  # noqa: E402
    EXPECTED_FRAME_COUNT,
    HandoffVerificationError,
    expected_frame_names,
    reconstruct_handoff,
)


def make_handoff(root: Path) -> Path:
    handoff = root / "handoff"
    handoff.mkdir()
    names = expected_frame_names()
    chunk_rows = []
    chunk_size = 46
    for chunk_index in range(10):
        start = chunk_index * chunk_size
        stop = min(start + chunk_size, len(names))
        selected = names[start:stop]
        manifest_files = []
        zip_path = handoff / f"chunk-{chunk_index}.zip"
        with ZipFile(zip_path, "w", compression=ZIP_STORED) as archive:
            for offset, filename in enumerate(selected):
                payload = f"crop:{filename}".encode()
                archive.writestr(filename, payload)
                manifest_files.append(
                    {
                        "filename": filename,
                        "nominalSourcePositionMm": float(start + offset),
                        "sourceSha256": sha256(f"source:{filename}".encode()).hexdigest(),
                        "sourceByteSize": len(filename) + 100,
                        "cropSha256": sha256(payload).hexdigest(),
                        "cropByteSize": len(payload),
                    }
                )
            manifest = {
                "chunk": {
                    "index": chunk_index,
                    "size": chunk_size,
                    "firstGlobalFrameIndex": start,
                    "lastGlobalFrameIndex": stop - 1,
                    "frameCount": len(selected),
                    "fullStackFrameCount": EXPECTED_FRAME_COUNT,
                    "firstFilename": selected[0],
                    "lastFilename": selected[-1],
                },
                "files": manifest_files,
            }
            archive.writestr("manifest.json", json.dumps(manifest))
        chunk_rows.append(
            {
                "index": chunk_index,
                "libraryFilename": zip_path.name,
                "byteSize": zip_path.stat().st_size,
                "digest": "sha256:" + sha256(zip_path.read_bytes()).hexdigest(),
            }
        )

    record = root / "source-record.json"
    record.write_text(
        json.dumps(
            {
                "persistentHandoff": {
                    "frameCoverage": {
                        "expectedFrameCount": EXPECTED_FRAME_COUNT,
                        "chunkCount": 10,
                    },
                    "chunks": chunk_rows,
                }
            }
        ),
        encoding="utf-8",
    )
    return record


class HandoffTests(unittest.TestCase):
    def test_reconstructs_exact_451_frame_stack(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = make_handoff(root)
            manifest, verification = reconstruct_handoff(
                root / "handoff", record, root / "out"
            )
            self.assertEqual(manifest["sliceCount"], EXPECTED_FRAME_COUNT)
            self.assertEqual(verification["frameCount"], EXPECTED_FRAME_COUNT)
            self.assertTrue(verification["allChunkHashesVerified"])
            self.assertTrue(verification["allCropHashesVerified"])
            self.assertEqual(
                [row["filename"] for row in manifest["files"]],
                list(expected_frame_names()),
            )
            self.assertEqual(
                len(list((root / "out" / "frames").glob("*.png"))),
                EXPECTED_FRAME_COUNT,
            )
            self.assertFalse(manifest["coordinateSpace"]["patientSpaceClaim"])
            self.assertFalse(manifest["claims"]["medicalMaster"])

    def test_rejects_tampered_chunk_before_extraction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = make_handoff(root)
            with (root / "handoff" / "chunk-3.zip").open("ab") as stream:
                stream.write(b"tamper")
            with self.assertRaisesRegex(
                HandoffVerificationError,
                "byte-size mismatch",
            ):
                reconstruct_handoff(root / "handoff", record, root / "out")


if __name__ == "__main__":
    unittest.main()
