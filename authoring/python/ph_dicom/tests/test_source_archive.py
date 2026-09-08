from __future__ import annotations

from hashlib import sha256
from io import BytesIO
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ph_dicom import (  # noqa: E402
    AlignedSourceArchiveSpec,
    acquire_archive,
    scaffold_manifest,
)


class _Response(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()


class SourceArchiveTests(unittest.TestCase):
    def test_aligned_source_scaffold_makes_no_registration_claim(
        self,
    ) -> None:
        payload = b"small-test-archive"
        spec = AlignedSourceArchiveSpec(
            archive_id="aligned-source-test",
            dataset="development-fixture",
            source_identifier="fixture-aligned-source",
            url="https://example.invalid/source.bin",
            expected_sha256=sha256(payload).hexdigest(),
            license_summary="test fixture only",
        )
        manifest = scaffold_manifest(spec)
        self.assertEqual(
            manifest["alignmentClaim"],
            "not-established",
        )
        self.assertFalse(manifest["patientSpaceClaim"])
        self.assertFalse(
            manifest["registrationCorrectnessClaim"]
        )

        with tempfile.TemporaryDirectory() as directory:
            receipt = acquire_archive(
                spec,
                Path(directory) / "source.bin",
                opener=lambda _: _Response(payload),
            )
            self.assertEqual(
                receipt["acquisitionStatus"],
                "acquired-unregistered",
            )
            self.assertEqual(
                receipt["alignmentClaim"],
                "not-established",
            )
            self.assertFalse(
                receipt["registrationCorrectnessClaim"]
            )


if __name__ == "__main__":
    unittest.main()
