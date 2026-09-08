from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE_URL = "https://data.lhncbc.nlm.nih.gov/public/Visible-Human/Female-Images/PNG_format/abdomen"
SOURCE_ARCHIVE_ID = "source.nlm.vhp-female"
ATTRIBUTION = "Courtesy of the U.S. National Library of Medicine"


def download(url: str, output: Path, *, attempts: int = 4) -> dict[str, object]:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            request = Request(
                url,
                headers={"User-Agent": "procedural-human-authoring/0.0 (+source-acquisition)"},
            )
            with urlopen(request, timeout=120) as response:
                digest = sha256()
                size = 0
                with output.open("wb") as stream:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        stream.write(chunk)
                        digest.update(chunk)
                        size += len(chunk)
                return {
                    "url": url,
                    "sha256": digest.hexdigest(),
                    "byteSize": size,
                    "contentType": response.headers.get("Content-Type"),
                    "lastModified": response.headers.get("Last-Modified"),
                    "etag": response.headers.get("ETag"),
                }
        except (HTTPError, URLError, TimeoutError) as exc:
            last_error = exc
            if output.exists():
                output.unlink()
            if attempt < attempts:
                time.sleep(attempt * 2)
    raise RuntimeError(f"failed to acquire {url}: {last_error}") from last_error


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Acquire a sparse Visible Human Female locator set without committing source data."
    )
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--stop", type=int, required=True)
    parser.add_argument("--step", type=int, default=10)
    parser.add_argument("--suffix", choices=("a", "b", "c"), default="a")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.step <= 0 or args.stop < args.start:
        raise SystemExit("invalid locator range")

    args.output.mkdir(parents=True, exist_ok=True)
    files: list[dict[str, object]] = []

    for position in range(args.start, args.stop + 1, args.step):
        filename = f"avf{position:04d}{args.suffix}.png"
        url = f"{BASE_URL}/{filename}"
        target = args.output / filename
        record = download(url, target)
        record["filename"] = filename
        record["nominalSourcePositionMm"] = (
            float(position)
            + {"a": 0.0, "b": 1.0 / 3.0, "c": 2.0 / 3.0}[args.suffix]
        )
        files.append(record)
        print(f"acquired {filename} {record['byteSize']} bytes {record['sha256']}")

    retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    manifest = {
        "schemaVersion": "1",
        "purpose": "TASK-A05 sparse locator acquisition for left distal forearm/wrist",
        "sourceArchiveId": SOURCE_ARCHIVE_ID,
        "sourceFolder": BASE_URL + "/",
        "retrievedAt": retrieved_at,
        "attribution": ATTRIBUTION,
        "termsUrl": "https://www.nlm.nih.gov/databases/download/terms_and_conditions.html",
        "sampling": {
            "startNumericPosition": args.start,
            "stopNumericPosition": args.stop,
            "stepNumericPosition": args.step,
            "suffix": args.suffix,
            "note": (
                "Visible Human filename positions are source-index coordinates only. "
                "They are not treated as DICOM Patient Space or as a verified CT registration."
            ),
        },
        "files": files,
    }
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
