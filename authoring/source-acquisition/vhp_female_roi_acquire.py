from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, __version__ as pillow_version

from vhp_female_locator import ATTRIBUTION, BASE_URL, SOURCE_ARCHIVE_ID, download


def sha256_path(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_names(start: int, stop: int) -> list[tuple[str, float]]:
    if stop < start:
        raise ValueError("stop must be >= start")
    result: list[tuple[str, float]] = []
    for position in range(start, stop):
        for suffix, offset in (("a", 0.0), ("b", 1.0 / 3.0), ("c", 2.0 / 3.0)):
            result.append((f"avf{position:04d}{suffix}.png", position + offset))
    result.append((f"avf{stop:04d}a.png", float(stop)))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Acquire and losslessly crop the bounded Visible Human Female wrist authoring stack."
    )
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--stop", type=int, required=True)
    parser.add_argument("--crop", type=int, nargs=4, metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    left, top, right, bottom = args.crop
    if min(left, top) < 0 or right <= left or bottom <= top:
        raise SystemExit("invalid crop box")

    frames_dir = args.output / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    aggregate = sha256()

    with TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        for filename, nominal_position in source_names(args.start, args.stop):
            source_url = f"{BASE_URL}/{filename}"
            source_path = temp_root / filename
            source_record = download(source_url, source_path)

            with Image.open(source_path) as image:
                if right > image.width or bottom > image.height:
                    raise RuntimeError(
                        f"crop {args.crop} exceeds {filename} dimensions {image.size}"
                    )
                cropped = image.crop((left, top, right, bottom))
                crop_path = frames_dir / filename
                cropped.save(crop_path, format="PNG", optimize=False)

            crop_sha = sha256_path(crop_path)
            crop_size = crop_path.stat().st_size
            aggregate.update(filename.encode("utf-8"))
            aggregate.update(str(source_record["sha256"]).encode("ascii"))

            records.append(
                {
                    "filename": filename,
                    "nominalSourcePositionMm": nominal_position,
                    "source": source_record,
                    "derivedCrop": {
                        "relativePath": f"frames/{filename}",
                        "sha256": crop_sha,
                        "byteSize": crop_size,
                    },
                }
            )
            print(
                f"acquired {filename}: source={source_record['byteSize']} "
                f"crop={crop_size} sha256={source_record['sha256']}"
            )

    retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    manifest = {
        "schemaVersion": "1",
        "purpose": "TASK-A05 draft segmentation source stack",
        "sourceArchiveId": SOURCE_ARCHIVE_ID,
        "sourceFolder": BASE_URL + "/",
        "retrievedAt": retrieved_at,
        "attribution": ATTRIBUTION,
        "termsUrl": "https://www.nlm.nih.gov/databases/download/terms_and_conditions.html",
        "sourceRange": {
            "start": f"avf{args.start:04d}a.png",
            "stop": f"avf{args.stop:04d}a.png",
            "nominalIntervalMm": 1.0 / 3.0,
            "frameCount": len(records),
            "aggregateSourceHash": f"sha256:{aggregate.hexdigest()}",
            "coordinateWarning": (
                "Nominal filename positions are source indexing only. Original female "
                "cryosections contain transverse offsets. This stack is not DICOM Patient "
                "Space and is not a verified CT registration."
            ),
        },
        "crop": {
            "pixelBox": {
                "left": left,
                "top": top,
                "rightExclusive": right,
                "bottomExclusive": bottom,
            },
            "sourcePixelSpacingMm": [0.33, 0.33],
            "semantics": (
                "bounded source-image crop containing the patient-left distal forearm/wrist "
                "with conservative background margin; not yet the TASK-A04 patient-space crop"
            ),
        },
        "derivation": {
            "method": "lossless PNG rectangular crop",
            "software": "Pillow",
            "softwareVersion": pillow_version,
        },
        "files": records,
    }
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
