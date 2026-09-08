from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import BinaryIO, Callable
from urllib.request import urlopen

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class SourceArchiveError(RuntimeError):
    pass


@dataclass(frozen=True)
class AlignedSourceArchiveSpec:
    archive_id: str
    dataset: str
    source_identifier: str
    url: str
    expected_sha256: str
    license_summary: str

    def validate(self) -> None:
        digest = self.expected_sha256.lower().removeprefix("sha256:")
        if not _SHA256_RE.fullmatch(digest):
            raise SourceArchiveError(
                "aligned source archive requires an explicit SHA-256"
            )
        if not self.url.startswith(("https://", "http://")):
            raise SourceArchiveError(
                "aligned source archive URL must be explicit HTTP(S)"
            )
        if not all(
            (
                self.archive_id,
                self.dataset,
                self.source_identifier,
                self.license_summary,
            )
        ):
            raise SourceArchiveError(
                "aligned source archive metadata may not be blank"
            )


def scaffold_manifest(
    spec: AlignedSourceArchiveSpec,
) -> dict[str, object]:
    spec.validate()
    return {
        "schema": "ph-source-archive-manifest.v1",
        "archiveId": spec.archive_id,
        "dataset": spec.dataset,
        "sourceIdentifier": spec.source_identifier,
        "url": spec.url,
        "expectedSha256": (
            spec.expected_sha256.lower().removeprefix("sha256:")
        ),
        "licenseSummary": spec.license_summary,
        "acquisitionStatus": "not-acquired",
        "coordinateSpace": "source-archive-only",
        "alignmentClaim": "not-established",
        "patientSpaceClaim": False,
        "registrationCorrectnessClaim": False,
    }


def write_manifest_scaffold(
    path: str | Path,
    spec: AlignedSourceArchiveSpec,
) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(
            scaffold_manifest(spec),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def acquire_archive(
    spec: AlignedSourceArchiveSpec,
    destination: str | Path,
    *,
    opener: Callable[[str], BinaryIO] = urlopen,
) -> dict[str, object]:
    spec.validate()
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(
        destination.suffix + ".partial"
    )
    digest = sha256()
    try:
        with opener(spec.url) as response, temporary.open(
            "wb"
        ) as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
                digest.update(chunk)
        actual = digest.hexdigest()
        expected = (
            spec.expected_sha256.lower().removeprefix("sha256:")
        )
        if actual != expected:
            temporary.unlink(missing_ok=True)
            raise SourceArchiveError(
                "aligned source archive hash mismatch: "
                f"expected {expected}, got {actual}"
            )
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise

    return {
        "schema": "ph-source-archive-acquisition-receipt.v1",
        "archiveId": spec.archive_id,
        "dataset": spec.dataset,
        "sourceIdentifier": spec.source_identifier,
        "sha256": digest.hexdigest(),
        "acquisitionStatus": "acquired-unregistered",
        "alignmentClaim": "not-established",
        "patientSpaceClaim": False,
        "registrationCorrectnessClaim": False,
    }
