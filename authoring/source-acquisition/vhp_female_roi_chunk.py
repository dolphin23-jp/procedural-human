from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, __version__ as pillow_version

from vhp_female_locator import ATTRIBUTION, BASE_URL, SOURCE_ARCHIVE_ID, download


FIRST_NUMERIC_POSITION = 1567
LAST_NUMERIC_POSITION = 1717
EXPECTED_FRAME_COUNT = 451
CROP = (1450, 250, 2000, 1000)
CROP_WIDTH = CROP[2] - CROP[0]
CROP_HEIGHT = CROP[3] - CROP[1]
COORDINATE_STATUS = (
    "source-image-stack only; filename position is not DICOM Patient Space "
    "and CT registration is not established"
)


def frame_sequence() -> list[tuple[str, float]]:
    frames: list[tuple[str, float]] = []
    for position in range(FIRST_NUMERIC_POSITION, LAST_NUMERIC_POSITION):
        for suffix, offset in (("a", 0.0), ("b", 1.0 / 3.0), ("c", 2.0 / 3.0)):
            frames.append((f"avf{position:04d}{suffix}.png", position + offset))
    frames.append((f"avf{LAST_NUMERIC_POSITION:04d}a.png", float(LAST_NUMERIC_POSITION)))
    if len(frames) != EXPECTED_FRAME_COUNT:
        raise AssertionError("unexpected bounded Visible Human Female frame count")
    return frames


def sha256_path(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Acquire one persistable chunk of the bounded Visible Human Female wrist stack."
    )
    parser.add_argument("--chunk-index", type=int, required=True)
    parser.add_argument("--chunk-size", type=int, default=46)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.chunk_index < 0 or args.chunk_size <= 0:
        raise SystemExit("chunk index must be non-negative and chunk size must be positive")

    frames = frame_sequence()
    start = args.chunk_index * args.chunk_size
    stop = min(start + args.chunk_size, len(frames))
    if start >= len(frames):
        raise SystemExit(f"chunk {args.chunk_index} is outside {len(frames)}-frame stack")

    selected = frames[start:stop]
    args.output.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    aggregate = sha256()

    with TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        for offset, (filename, nominal_position) in enumerate(selected):
            global_frame_index = start + offset
            source_url = f"{BASE_URL}/{filename}"
            source_path = temp_root / filename
            source_record = download(source_url, source_path)

            with Image.open(source_path) as image:
                image.load()
                if (
                    CROP[0] < 0
                    or CROP[1] < 0
                    or CROP[2] > image.width
                    or CROP[3] > image.height
                ):
                    raise RuntimeError(
                        f"crop {CROP} exceeds {filename} source dimensions {image.size}"
                    )
                cropped = image.crop(CROP)
                if cropped.size != (CROP_WIDTH, CROP_HEIGHT):
                    raise RuntimeError(
                        f"unexpected crop dimensions for {filename}: {cropped.size}"
                    )
                target = args.output / filename
                cropped.save(target, format="PNG", optimize=False)

            crop_sha = sha256_path(target)
            crop_size = target.stat().st_size
            aggregate.update(filename.encode("utf-8"))
            aggregate.update(str(source_record["sha256"]).encode("ascii"))
            records.append(
                {
                    "filename": filename,
                    "globalFrameIndex": global_frame_index,
                    "nominalSourcePositionMm": nominal_position,
                    "sourceUrl": source_url,
                    "sourceSha256": source_record["sha256"],
                    "sourceByteSize": source_record["byteSize"],
                    "cropSha256": crop_sha,
                    "cropByteSize": crop_size,
                    "cropPixels": {
                        "left": CROP[0],
                        "top": CROP[1],
                        "rightExclusive": CROP[2],
                        "bottomExclusive": CROP[3],
                    },
                    "cropDimensionsPixels": {
                        "width": CROP_WIDTH,
                        "height": CROP_HEIGHT,
                    },
                    "attribution": ATTRIBUTION,
                    "sourceSpaceOnly": True,
                }
            )
            print(
                f"acquired index={global_frame_index} {filename} "
                f"source={source_record['sha256']} crop={crop_sha}"
            )

    manifest = {
        "schemaVersion": "1",
        "acquisitionId": "a05-vhp-female-left-wrist-roi-20260908",
        "sourceArchiveId": SOURCE_ARCHIVE_ID,
        "sourceFolder": BASE_URL + "/",
        "retrievedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "attribution": ATTRIBUTION,
        "termsUrl": "https://www.nlm.nih.gov/databases/download/terms_and_conditions.html",
        "chunk": {
            "index": args.chunk_index,
            "size": args.chunk_size,
            "firstGlobalFrameIndex": start,
            "lastGlobalFrameIndex": stop - 1,
            "frameCount": len(selected),
            "fullStackFrameCount": len(frames),
            "firstFilename": selected[0][0],
            "lastFilename": selected[-1][0],
            "aggregateSourceHash": f"sha256:{aggregate.hexdigest()}",
        },
        "crop": {
            "left": CROP[0],
            "top": CROP[1],
            "rightExclusive": CROP[2],
            "bottomExclusive": CROP[3],
            "width": CROP_WIDTH,
            "height": CROP_HEIGHT,
        },
        "coordinateStatus": COORDINATE_STATUS,
        "claims": {
            "patientSpaceGeometry": False,
            "ctRegistrationEstablished": False,
            "medicalValidation": False,
            "medicalMaster": False,
            "runtimeAsset": False,
        },
        "derivation": {
            "method": "lossless PNG rectangular crop",
            "software": "Pillow",
            "softwareVersion": pillow_version,
            "deterministicEncodingConfiguration": {
                "format": "PNG",
                "optimize": False,
            },
        },
        "files": records,
    }
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
