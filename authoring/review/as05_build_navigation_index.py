"""Build the transient TASK-AS05 browser navigation index.

The committed whole-body inventory remains authoritative. This compact file is a
derived navigation cache for GitHub Pages and must never be treated as a second
source archive or as medical validation.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

REGION_ORDER = ("head", "thorax", "abdomen", "pelvis", "thighs", "legs")
A05_FIRST = "avf1567a.png"
A05_LAST = "avf1717a.png"


def file_hash(path: Path) -> str:
    h = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def build_navigation_index(inventory_path: Path) -> dict:
    inventory_path = Path(inventory_path)
    inventory = json.loads(inventory_path.read_text())
    frames = inventory["frames"]

    if inventory["kind"] != "vhf-whole-body-inventory":
        raise ValueError("unexpected inventory kind")
    if inventory["coordinateSpace"] != "source-image-stack":
        raise ValueError("AS05 requires source-image-stack inventory")
    if len(frames) != inventory["frameCount"]:
        raise ValueError("inventory frame count mismatch")
    if [row["index"] for row in frames] != list(range(len(frames))):
        raise ValueError("inventory indices are not contiguous")

    names = [row["filename"] for row in frames]
    if len(names) != len(set(names)):
        raise ValueError("duplicate source filenames")

    name_to_index = {row["filename"]: row["index"] for row in frames}
    if A05_FIRST not in name_to_index or A05_LAST not in name_to_index:
        raise ValueError("A05 reference range is absent")

    provider_partitions = []
    for region in REGION_ORDER:
        indices = [
            row["index"]
            for row in frames
            if region in row.get("navigationRegions", ())
        ]
        if not indices:
            continue
        provider_partitions.append(
            {
                "name": region,
                "firstIndex": min(indices),
                "lastIndex": max(indices),
                "frameCount": len(indices),
            }
        )

    compact_frames = []
    unavailable = []
    for row in frames:
        size = row["source"]["listedByteSize"]
        availability = (
            "provider-listed-zero-byte" if size == 0 else "source-image"
        )
        if size == 0:
            unavailable.append(row["index"])
        compact_frames.append(
            {
                "index": row["index"],
                "filename": row["filename"],
                "sourcePath": row["source"]["path"],
                "sourceUrl": row["source"]["url"],
                "listedByteSize": size,
                "navigationRegions": row.get("navigationRegions", []),
                "availability": availability,
            }
        )

    usable = len(frames) - len(unavailable)
    if unavailable != [3297, 3298]:
        raise ValueError(
            "provider availability changed; review source snapshot before AS05 build"
        )

    claims = inventory["claims"]
    if any(claims.values()):
        raise ValueError("source inventory carries an unsupported positive claim")

    return {
        "schema": "ph-as05-source-navigation.v1",
        "schemaVersion": "1",
        "task": "TASK-AS05",
        "generatedFrom": {
            "inventoryPath": inventory_path.as_posix(),
            "inventorySha256": file_hash(inventory_path),
            "sourceArchiveId": inventory["sourceArchiveId"],
            "snapshotAt": inventory["snapshotAt"],
        },
        "coordinateSpace": "source-image-stack",
        "claims": {
            "patientSpace": False,
            "registeredCT": False,
            "medicalValidation": False,
            "medicalMaster": False,
            "runtimeAsset": False,
            "segmentation": False,
        },
        "terms": {
            "attribution": inventory["terms"]["attribution"],
            "conditions": inventory["terms"]["conditions"],
            "url": inventory["terms"]["url"],
        },
        "counts": {
            "listedSourceCount": len(frames),
            "usableImageCount": usable,
            "unavailableSourceCount": len(unavailable),
        },
        "providerPartitions": provider_partitions,
        "knownGaps": inventory["knownGaps"],
        "a05Reference": {
            "label": "A05 distal left forearm/wrist source range",
            "firstIndex": name_to_index[A05_FIRST],
            "lastIndex": name_to_index[A05_LAST],
            "firstFilename": A05_FIRST,
            "lastFilename": A05_LAST,
        },
        "frames": compact_frames,
    }


def write_index(inventory_path: Path, output_path: Path) -> dict:
    result = build_navigation_index(inventory_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp = output_path.with_suffix(output_path.suffix + ".partial")
    temp.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    temp.replace(output_path)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = write_index(args.inventory, args.output)
    print(
        json.dumps(
            {
                "task": result["task"],
                "inventorySha256": result["generatedFrom"]["inventorySha256"],
                "listedSourceCount": result["counts"]["listedSourceCount"],
                "usableImageCount": result["counts"]["usableImageCount"],
                "unavailableSourceCount": result["counts"]["unavailableSourceCount"],
            }
        )
    )


if __name__ == "__main__":
    main()
